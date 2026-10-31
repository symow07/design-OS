"""Temporary web-reference review authority — owner-authorized ceremony
(temporary_web_reference_reviewer_grant/1.0, 2026-07-25).

Grants the authenticated administrator a 14-day WEB_REFERENCE_REVIEWER
assignment: endpoint-side authority over the ARIA web-source review UI, and
nothing else. The role is deliberately absent from every decision-chain
action policy, so the assignment can never record metadata, resolve the
corpus fork, decide gates, or administer roles. This is a NEW epoch-2
authorization — not a recovery, continuation or reaffirmation of the revoked
legacy reviewer grant, which stays closed.

Idempotent: while an active grant exists, a repeat invocation reconciles and
returns it. Independently revocable via `revoke_temporary_web_reviewer`.
"""
from __future__ import annotations

import dataclasses

from django.db import transaction
from django.utils import timezone

from . import authz_policy as authz
from . import bootstrap_registry as reg
from .bootstrap_environment import classify_environment
from .decision_chain import (
    _BOOTSTRAP_APPEND_TOKEN,
    append_temporary_web_reviewer_grant_event,
)
from .models import (
    GRANT_OWNER_TEMPORARY_WEB_REVIEW,
    RESULT_ALLOWED,
    AuthorizationAudit,
    DecisionChainHead,
    DecisionEvent,
    ReviewerRoleAssignment,
)

GRANT_ENDPOINT = "cli:temporary_web_reference_reviewer_grant"
REVOCATION_MECHANISM = (
    "independently revocable at any time: revoke_temporary_web_reviewer sets "
    "revoked_at/revoked_by/revocation_reason on the assignment row; expiry "
    "is enforced natively by the assignment window")


class WebReviewGrantError(RuntimeError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclasses.dataclass(frozen=True)
class GrantResult:
    status: str                       # PERFORMED | ALREADY_GRANTED
    event_id: str
    assignment_id: int
    expires_at: object


def active_temporary_web_review_assignment(user=None, at=None):
    at = at or timezone.now()
    qs = ReviewerRoleAssignment.objects.filter(
        role=authz.WEB_REFERENCE_REVIEWER,
        grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW,
        granted_at__lte=at, expires_at__gt=at, revoked_at__isnull=True)
    if user is not None:
        qs = qs.filter(user=user)
    return qs.first()


def grant_temporary_web_reviewer(*, actor, reason=None) -> GrantResult:
    """Perform the owner-authorized grant ceremony, or reconcile the active
    one. Superuser status, staff status, unrelated roles, bootstrap-closure
    state: untouched."""
    if not actor.is_superuser or not actor.is_active:
        raise WebReviewGrantError("ACTOR_NOT_SUPERUSER_OR_INACTIVE")
    closure = DecisionEvent.objects.filter(
        action=reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE).order_by(
        "sequence_number").first()
    if closure is None:
        raise WebReviewGrantError(
            "REAFFIRMATION_CLOSURE_REQUIRED",
            "the grant exists only in the post-reaffirmation world")
    reason = (reason or
              "OWNER_AUTHORIZED_TEMPORARY_REVIEWER_GRANT — review and "
              "classify Web Research session #3 sources and perform the "
              "bounded Complete Product pilot-reference authorization "
              "process").strip()
    classification, environment_evidence = classify_environment()

    with transaction.atomic():
        User = type(actor)
        user = User.objects.select_for_update().get(pk=actor.pk)
        list(ReviewerRoleAssignment.objects.select_for_update().filter(
            user=user, role=authz.WEB_REFERENCE_REVIEWER))
        head = DecisionChainHead.objects.select_for_update().get(pk=1)

        existing = active_temporary_web_review_assignment(user)
        if existing is not None:
            event = DecisionEvent.objects.filter(
                action=reg.TEMPORARY_WEB_REVIEWER_GRANT,
                payload__assignment_id=existing.pk).first()
            if event is None:
                raise WebReviewGrantError(
                    "GRANT_STATE_INCONSISTENT",
                    "an active assignment exists with no ceremony event")
            return GrantResult("ALREADY_GRANTED", event.event_id,
                               existing.pk, existing.expires_at)

        now = timezone.now()
        expires_at = now + timezone.timedelta(
            days=reg.TEMP_GRANT_MAX_DAYS)
        assignment = ReviewerRoleAssignment(
            user=user, role=authz.WEB_REFERENCE_REVIEWER, granted_by=user,
            granted_at=now, expires_at=expires_at,
            grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW,
            grant_reason=reason)
        assignment.full_clean()
        assignment.save()

        payload = {
            "bootstrap_schema": reg.TEMP_GRANT_SCHEMA,
            "single_operator": True,
            "dual_control": False,
            "actor_user_id": user.pk,
            "target_user_id": user.pk,
            "granted_role": authz.WEB_REFERENCE_REVIEWER,
            "purpose": reg.TEMP_GRANT_PURPOSE,
            "granted_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "reason": reason,
            "assignment_id": assignment.pk,
            "capability_inventory": list(reg.TEMP_GRANT_CAPABILITIES),
            "statements": list(reg.TEMP_GRANT_REQUIRED_STATEMENTS),
            "revocation_mechanism": REVOCATION_MECHANISM,
            "incident_id": (closure.payload or {}).get("incident_id"),
            "reaffirmation_closure_event_id": closure.event_id,
            "environment_classification": classification,
            "environment_evidence": environment_evidence,
            "account_control_basis": reg.TEMP_GRANT_ACCOUNT_CONTROL_BASIS,
            "observed_user_is_active": bool(user.is_active),
            "observed_user_is_superuser": bool(user.is_superuser),
            "authorization_basis": reg.TEMP_GRANT_AUTHORIZATION_BASIS,
        }
        event = append_temporary_web_reviewer_grant_event(
            capability=_BOOTSTRAP_APPEND_TOKEN, user=user, payload=payload,
            head=head, now=now)
        AuthorizationAudit.objects.create(
            user=user, action=reg.TEMPORARY_WEB_REVIEWER_GRANT,
            subject_type="User", subject_id=str(user.pk),
            result=RESULT_ALLOWED, reason_code="AUTHORIZED",
            active_roles=[], authorizing_roles=[],
            role_used=reg.BOOTSTRAP_OPERATOR,
            selection_rule="OWNER_AUTHORIZED_TEMPORARY_REVIEWER_GRANT",
            endpoint=GRANT_ENDPOINT, request_method="",
            metadata={
                "severity": "CRITICAL",
                "ceremony": reg.TEMP_GRANT_SCHEMA,
                "purpose": reg.TEMP_GRANT_PURPOSE,
                "decision_event_id": event.event_id,
                "assignment_id": assignment.pk,
                "expires_at": expires_at.isoformat(),
            })
        return GrantResult("PERFORMED", event.event_id, assignment.pk,
                           expires_at)


def revoke_temporary_web_reviewer(*, actor, reason) -> int:
    """Independent revocation — de-escalation only, superuser-executable."""
    if not actor.is_superuser or not actor.is_active:
        raise WebReviewGrantError("ACTOR_NOT_SUPERUSER_OR_INACTIVE")
    if not (reason or "").strip():
        raise WebReviewGrantError("REASON_REQUIRED")
    now = timezone.now()
    revoked = 0
    with transaction.atomic():
        for a in ReviewerRoleAssignment.objects.select_for_update().filter(
                role=authz.WEB_REFERENCE_REVIEWER,
                grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW,
                revoked_at__isnull=True):
            a.revoked_at = now
            a.revoked_by = actor
            a.revocation_reason = reason.strip()
            a.save()
            revoked += 1
    return revoked


__all__ = [
    "GrantResult", "WebReviewGrantError",
    "active_temporary_web_review_assignment",
    "grant_temporary_web_reviewer", "revoke_temporary_web_reviewer",
]
