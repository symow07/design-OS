"""Single-operator initial reviewer ceremony — DIP-1A-BOOTSTRAP-CORR-2.

One honest, one-shot, local-development bootstrap of a time-limited `DESIGN_REVIEWER`,
which permanently closes bootstrap in the same transaction.

**Why this exists.** `grant_reviewer_role` requires `BUSINESS_OWNER`/`BRAND_ADMIN` and
forbids self-elevation, so a protected grant needs two distinct authenticated humans. In a
genuinely single-operator environment there is no honest way to satisfy that: the two
alternatives are a puppet second account (which writes a false two-party trail into an
immutable record) or the legacy direct bootstrap (which leaves `BootstrapState` open
forever). This ceremony is the third option — visibly weaker, and truthful about it.

**What it is not.** Not dual control. Not a protected role grant. Not production. Not a
path to `BRAND_ADMIN`/`BUSINESS_OWNER`/`LEGAL_REVIEWER`/`SYSTEM_ADMIN`. Not reachable from
the web. Not a reusable "skip authorization" mechanism: the append path it uses can only
ever emit this one event shape.

The caller must have already proved account control (password challenge in the command
layer, before the transaction opens). This module owns locks, preconditions, writes and
closure.
"""
from __future__ import annotations

import dataclasses

from django.db import transaction
from django.utils import timezone

from . import bootstrap_registry as reg
from .bootstrap_environment import classify_environment
from .decision_chain import (
    _BOOTSTRAP_APPEND_TOKEN, append_bootstrap_initial_reviewer_event, verify_chain,
)
from .models import (
    GRANT_BOOTSTRAP_SINGLE_OPERATOR, RESULT_ALLOWED, AuthorizationAudit, BootstrapState,
    DecisionChainHead, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
)

CEREMONY_ENDPOINT = "cli:bootstrap_single_operator_reviewer"
ALREADY_COMPLETED = "ALREADY_COMPLETED"
STATE_INCONSISTENT = "BOOTSTRAP_STATE_INCONSISTENT"


class CeremonyError(RuntimeError):
    """A precondition failed. Nothing was written."""

    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclasses.dataclass(frozen=True)
class CeremonyResult:
    status: str                      # PERFORMED | ALREADY_COMPLETED
    event_id: str
    assignment_id: int | None
    role: str
    expires_at: object
    username: str


def _existing_ceremony_event():
    return DecisionEvent.objects.filter(
        action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE).order_by("sequence_number").first()


def _reconcile_completed(event, user):
    """A repeat invocation reports ALREADY_COMPLETED **only** when event, assignment and
    state reconcile exactly. Anything else is an inconsistency, not a no-op."""
    state = BootstrapState.objects.get(pk=1)
    payload = event.payload if isinstance(event.payload, dict) else {}
    problems = []
    if DecisionEvent.objects.filter(
            action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE).count() != 1:
        problems.append("more than one bootstrap ceremony event exists")
    if not state.closed:
        problems.append("bootstrap state is open despite a ceremony event")
    if state.closed_by_event_id != event.pk:
        problems.append("bootstrap closure is not anchored to the ceremony event")
    if state.break_glass_count != 0:
        problems.append("break_glass_count is not zero")
    if payload.get("target_user_id") != user.pk:
        problems.append("ceremony event targets a different user")
    assignment = ReviewerRoleAssignment.objects.filter(
        user_id=payload.get("target_user_id"), role=payload.get("granted_role"),
        grant_source=GRANT_BOOTSTRAP_SINGLE_OPERATOR).first()
    if assignment is None:
        problems.append("no matching single-operator role assignment exists")
    elif assignment.expires_at.isoformat() != payload.get("expires_at"):
        problems.append("assignment expiry does not match the signed event")
    if problems:
        raise CeremonyError(STATE_INCONSISTENT, "; ".join(problems))
    return CeremonyResult(
        status=ALREADY_COMPLETED, event_id=event.event_id,
        assignment_id=assignment.pk, role=assignment.role,
        expires_at=assignment.expires_at, username=user.get_username())


def _check_preconditions(user, role, expires_days, reason):
    if role not in reg.ALLOWED_BOOTSTRAP_ROLES:
        # allow-list of exactly one: a future role cannot arrive through a permissive
        # default, it has to be added here on purpose
        raise CeremonyError("ROLE_NOT_PERMITTED_IN_CEREMONY", role)
    if not isinstance(expires_days, int) or expires_days <= 0:
        raise CeremonyError("EXPIRY_REQUIRED")
    if expires_days > reg.MAX_EXPIRY_DAYS:
        raise CeremonyError("EXPIRY_EXCEEDS_BOUND", f"max {reg.MAX_EXPIRY_DAYS} days")
    if not (reason or "").strip():
        raise CeremonyError("REASON_REQUIRED")
    if len(reason.strip()) > reg.MAX_REASON_LENGTH:
        raise CeremonyError("REASON_TOO_LONG")
    if not user.is_active:
        raise CeremonyError("ACCOUNT_INACTIVE")
    if not user.is_superuser:
        raise CeremonyError("ACCOUNT_NOT_SUPERUSER")


def _check_database_preconditions(user):
    """Re-checked INSIDE the transaction under the locks — the pre-flight copy of these
    checks is a courtesy, this one is the guarantee."""
    if not verify_chain().ok:
        raise CeremonyError("DECISION_CHAIN_NOT_VERIFIED")
    if DecisionEvent.objects.exists():
        raise CeremonyError("CHAIN_IS_NOT_AT_GENESIS")
    if ReviewerRoleAssignment.objects.exists():
        raise CeremonyError("REVIEWER_ROLE_ASSIGNMENTS_ALREADY_EXIST")
    from apps.intelligence.models import OperationalPermissionProjection
    if OperationalPermissionProjection.objects.exists():
        raise CeremonyError("OPERATIONAL_PERMISSIONS_ALREADY_EXIST")


def perform_single_operator_ceremony(*, authenticated_user, role, expires_days, reason,
                                     account_control_basis, display_name=""):
    """Perform the ceremony, or fail closed having written nothing.

    `authenticated_user` MUST be the user object returned by a completed account-control
    challenge — not one looked up from a username argument. The command layer owns that
    challenge and passes its result here; this module refuses a basis it does not know.
    """
    if account_control_basis != reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE:
        raise CeremonyError("UNSUPPORTED_ACCOUNT_CONTROL_BASIS")
    _check_preconditions(authenticated_user, role, expires_days, reason)
    classification, environment_evidence = classify_environment()

    with transaction.atomic():
        # LOCK 1: the target user row (serialises ceremonies against the same account)
        User = type(authenticated_user)
        user = User.objects.select_for_update().get(pk=authenticated_user.pk)
        # LOCK 2: that user's profile and assignment rows
        list(ReviewerRoleAssignment.objects.select_for_update().filter(user=user))
        profile = ReviewerProfile.objects.select_for_update().filter(user=user).first()
        # LOCK 3: the chain head (serialises ceremonies against DIFFERENT accounts too)
        head = DecisionChainHead.objects.select_for_update().get(pk=1)
        # LOCK 4: the bootstrap singleton
        state = BootstrapState.objects.select_for_update().get(pk=1)

        # an already-performed ceremony reconciles or fails; it never silently re-runs
        existing = _existing_ceremony_event()
        if existing is not None:
            return _reconcile_completed(existing, user)
        if state.closed:
            raise CeremonyError("BOOTSTRAP_PERMANENTLY_CLOSED")
        if state.break_glass_count != 0:
            raise CeremonyError("BREAK_GLASS_COUNT_IS_NOT_ZERO")
        _check_database_preconditions(user)

        now = timezone.now()
        expires_at = now + timezone.timedelta(days=expires_days)
        prior_profile_state = {
            "exists": profile is not None,
            "reviewer_enabled": bool(profile and profile.reviewer_enabled),
        }
        prior_state = {"closed": state.closed,
                       "break_glass_count": state.break_glass_count}

        if profile is None:
            profile = ReviewerProfile.objects.create(
                user=user, display_name=display_name, reviewer_enabled=True)
        elif not profile.reviewer_enabled:
            profile.reviewer_enabled = True
            profile.save()

        # granted_by is the authenticated actor, NOT null: this is an explicit
        # self-bootstrap and the actor stays nameable through the PROTECT FK. The
        # distinct grant_source, not a null granter, is what marks it as extraordinary.
        assignment = ReviewerRoleAssignment(
            user=user, role=role, granted_by=user, granted_at=now,
            expires_at=expires_at, grant_source=GRANT_BOOTSTRAP_SINGLE_OPERATOR,
            grant_reason=reason.strip())
        # full validation, nothing excluded: the model's clean() enforces role validity,
        # expiry ordering, a named granter and a recorded reason, and all four must hold
        # here exactly as they do for an ordinary grant
        assignment.full_clean()
        assignment.save()

        payload = {
            "bootstrap_schema": reg.BOOTSTRAP_CEREMONY_SCHEMA,
            "single_operator": True,
            "dual_control": False,
            "actor_user_id": user.pk,
            "target_user_id": user.pk,
            "granted_role": role,
            "granted_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "reason": reason.strip(),
            "environment_classification": classification,
            "environment_evidence": environment_evidence,
            "account_control_basis": account_control_basis,
            "observed_user_is_active": bool(user.is_active),
            "observed_user_is_superuser": bool(user.is_superuser),
            "prior_reviewer_profile_state": prior_profile_state,
            "resulting_reviewer_profile_state": {
                "exists": True, "reviewer_enabled": True},
            "prior_bootstrap_state": prior_state,
            "resulting_bootstrap_state": {"closed": True, "break_glass_count": 0},
            "authorization_basis": reg.AUTHORIZATION_BASIS,
        }
        event = append_bootstrap_initial_reviewer_event(
            capability=_BOOTSTRAP_APPEND_TOKEN, user=user, payload=payload, head=head,
            now=now)

        # closure, anchored to the signed event through a PROTECT FK — the event cannot
        # be deleted while it anchors the closure
        state.closed = True
        state.closed_at = now
        state.closed_by_event = event
        state.save()

        # CRITICAL audit. `reason_code` reads AUTHORIZED because the table's check
        # constraint requires exactly that for an ALLOWED row; the real basis is in
        # `metadata`, and `role_used` is the sentinel, so nothing here reads as a role
        # decision.
        AuthorizationAudit.objects.create(
            user=user, action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE,
            subject_type="User", subject_id=str(user.pk),
            result=RESULT_ALLOWED, reason_code="AUTHORIZED",
            active_roles=[], authorizing_roles=[],
            role_used=reg.BOOTSTRAP_OPERATOR,
            selection_rule="SINGLE_OPERATOR_BOOTSTRAP_CEREMONY",
            endpoint=CEREMONY_ENDPOINT, request_method="",
            metadata={
                "severity": "CRITICAL",
                "ceremony": reg.BOOTSTRAP_CEREMONY_SCHEMA,
                "single_operator": True,
                "dual_control": False,
                "authorization_basis": reg.AUTHORIZATION_BASIS,
                "account_control_basis": account_control_basis,
                "environment_classification": classification,
                "decision_event_id": event.event_id,
                "granted_role": role,
                "expires_at": expires_at.isoformat(),
            })

        return CeremonyResult(
            status="PERFORMED", event_id=event.event_id, assignment_id=assignment.pk,
            role=role, expires_at=expires_at, username=user.get_username())
