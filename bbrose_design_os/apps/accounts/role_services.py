"""Protected reviewer-role lifecycle services (DIP-1A-5A).

Granting, revoking, enabling and disabling reviewer authority are **protected security
decisions**: each authorizes the acting user, mutates the role/profile state, and appends a
signed DecisionEvent — atomically, so the state and the ledger can never diverge.

Invariants (each enforced and tested):

* **The acting user comes from the authenticated caller, never from a request body.** The
  caller supplies the *target*, the requested role, expiry and reason — never the actor id,
  never `role_used`, never an authorization result.
* **Deny is audited OUTSIDE the mutation transaction.** Authorization (and the
  self-elevation guard) run first; a denial writes a best-effort AuthorizationAudit and
  raises, so the audit survives even though nothing was mutated. Only an *allowed* call
  opens the atomic block, and the ALLOWED audit is written *inside* it — an audit-write
  failure then rolls the whole decision back (fail closed, the 1A-3 discipline).
* **Lock order is fixed: target rows (assignment/profile) → chain head → bootstrap state.**
  The append service locks the head; this module always locks the target rows first and
  closes bootstrap last, so concurrent role operations serialise without deadlock.
* **role_used is derived by the append service and cross-checked** against this service's
  own authorization — a divergence fails closed.
* **Nothing is deleted.** A revocation writes onto the assignment; history is preserved.
"""
from __future__ import annotations

import dataclasses

from django.db import transaction
from django.utils import timezone

from . import authz_policy as authz
from .authorization import (
    SELF_ELEVATION_FORBIDDEN,
    AuthorizationResult,
    authorize_actor,
    build_authorization_snapshot,
    record_authorization,
)
from .decision_chain import append_decision
from .models import (
    GRANT_AUTHORIZED_SERVICE,
    BootstrapState,
    ReviewerProfile,
    ReviewerRoleAssignment,
)

ROLE_MGMT_ACTIONS = (authz.GRANT_REVIEWER_ROLE, authz.REVOKE_REVIEWER_ROLE,
                     authz.ENABLE_REVIEWER_PROFILE, authz.DISABLE_REVIEWER_PROFILE)
SUBJECT_TYPE = "ReviewerUser"


class RoleServiceError(RuntimeError):
    """A protected role operation is invalid. FAIL CLOSED — nothing is mutated."""


class RoleServiceDenied(RoleServiceError):
    """The acting user is not authorized (or may not target this user)."""


class RevocationConflict(RoleServiceError):
    """A second, DIFFERENT revocation of an already-revoked assignment."""


def _subject(target_user):
    return (SUBJECT_TYPE, str(target_user.pk))


def _endpoint(fn_name):
    return f"accounts.role_services.{fn_name}"


def _deny(result, action, *, reason, endpoint):
    """Record a DENIED audit OUTSIDE any transaction and raise. Survives the non-mutation."""
    denied = dataclasses.replace(result, allowed=False, reason_code=reason,
                                 role_used=None, authorizing_roles=(),
                                 selection_rule=None)
    _best_effort_deny_audit(denied, endpoint)
    raise RoleServiceDenied(f"{action}: {reason}")


def _best_effort_deny_audit(denied_result, endpoint):
    from .authorization import _best_effort_record
    _best_effort_record(denied_result, None, endpoint, "SERVICE")


def _authorize(actor, action, target_user, fn_name, *, at) -> AuthorizationResult:
    """Authorize the acting user for `action`. Deny (audited) if not allowed."""
    endpoint = _endpoint(fn_name)
    result = authorize_actor(actor, action, subject=_subject(target_user), at=at)
    if not result.allowed:
        _best_effort_deny_audit(result, endpoint)
        raise RoleServiceDenied(f"{action}: {result.reason_code}")
    return result


def _append_and_check(*, actor, action, target_user, payload, result):
    """Append the protected event and cross-check the derived role against ours."""
    event = append_decision(user=actor, action=action, payload=payload,
                            subject=_subject(target_user))
    if event.role_used != result.role_used:
        # the append service authorized independently; a divergence means the actor's
        # authority shifted between our check and the append — fail closed.
        raise RoleServiceError(
            f"role_used skew: service saw {result.role_used!r}, append derived "
            f"{event.role_used!r}")
    return event


def _close_bootstrap(event):
    """Permanently close pre-ledger bootstrap on the first protected role event. Idempotent
    (False->True only); locks the singleton (seeded by migration 0005) to avoid a
    check/close race with the bootstrap command."""
    state = BootstrapState.objects.select_for_update().get(pk=1)
    if not state.closed:
        state.closed = True
        state.closed_at = timezone.now()
        state.closed_by_event = event
        state.save()


def _audit_allowed(result, endpoint, *, target_user, event):
    record_authorization(
        result, request=None, endpoint=endpoint, method="SERVICE",
        metadata={"target_user_id": target_user.pk, "event_id": event.event_id,
                  "sequence_number": event.sequence_number})


# =================================================================================
# Grant
# =================================================================================
def grant_reviewer_role(*, actor, target_user, role, expires_at, reason,
                        granted_at=None):
    """Grant `role` to `target_user`. Non-idempotent: a duplicate active grant is REJECTED
    (fail closed), not silently returned. Returns (event, assignment)."""
    fn = "grant_reviewer_role"
    endpoint = _endpoint(fn)
    evaluated_at = timezone.now()
    result = _authorize(actor, authz.GRANT_REVIEWER_ROLE, target_user, fn,
                        at=evaluated_at)

    # self-elevation guard: a grant may not target the acting user. Self-appointment is the
    # classic elevation path; the policy says WHO may grant, this says they may not grant
    # to themselves.
    if target_user.pk == actor.pk:
        _deny(result, authz.GRANT_REVIEWER_ROLE,
              reason=SELF_ELEVATION_FORBIDDEN, endpoint=endpoint)

    if role not in authz.ROLES:
        raise RoleServiceError(f"unknown role {role!r}")
    if not (reason or "").strip():
        raise RoleServiceError("a grant must record a reason")
    now = evaluated_at
    granted_at = granted_at or now
    if expires_at is None or expires_at <= granted_at:
        raise RoleServiceError("expiry is required and must be after granted_at")
    if not target_user.is_active:
        raise RoleServiceError("target user is inactive")

    with transaction.atomic():
        # LOCK ORDER 1: target's assignments for this role (before the head)
        prior = list(ReviewerRoleAssignment.objects.select_for_update()
                     .filter(user=target_user, role=role))
        profile = (ReviewerProfile.objects.select_for_update()
                   .filter(user=target_user).first())
        if profile is None or not profile.reviewer_enabled:
            raise RoleServiceError(
                "target has no enabled reviewer profile — enable it first")
        # overlap: refuse a second live grant of the same role
        if any(a.is_active_at(now) for a in prior):
            raise RoleServiceError(
                f"target already holds an active {role} assignment")

        prior_ids = [a.pk for a in prior]
        payload = {
            "target_user_id": target_user.pk, "role": role,
            "granted_at": granted_at.isoformat(), "expires_at": expires_at.isoformat(),
            "reason": reason, "prior_assignment_ids": prior_ids,
            "authz_snapshot": build_authorization_snapshot(actor, result, evaluated_at),
        }
        # LOCK ORDER 2: the chain head (inside append_decision)
        event = _append_and_check(actor=actor, action=authz.GRANT_REVIEWER_ROLE,
                                  target_user=target_user, payload=payload, result=result)
        assignment = ReviewerRoleAssignment(
            user=target_user, role=role, granted_by=actor, granted_at=granted_at,
            expires_at=expires_at, grant_source=GRANT_AUTHORIZED_SERVICE,
            grant_reason=reason)
        assignment.save()
        # LOCK ORDER 3: bootstrap state
        _close_bootstrap(event)
        _audit_allowed(result, endpoint, target_user=target_user, event=event)
    return event, assignment


# =================================================================================
# Revoke
# =================================================================================
def revoke_reviewer_role(*, actor, assignment, reason):
    """Revoke a specific assignment. Idempotent for an identical repeat (same actor+reason);
    a conflicting second revocation fails closed. Never deletes. Returns (event|None,
    assignment)."""
    fn = "revoke_reviewer_role"
    endpoint = _endpoint(fn)
    target_user = assignment.user
    evaluated_at = timezone.now()
    result = _authorize(actor, authz.REVOKE_REVIEWER_ROLE, target_user, fn,
                        at=evaluated_at)
    if not (reason or "").strip():
        raise RoleServiceError("a revocation must record a reason")

    with transaction.atomic():
        a = ReviewerRoleAssignment.objects.select_for_update().get(pk=assignment.pk)
        if a.revoked_at is not None:
            # idempotent iff the SAME actor gave the SAME reason; otherwise a conflict
            if a.revoked_by_id == actor.pk and (a.revocation_reason or "") == reason:
                return None, a
            raise RevocationConflict(
                "assignment already revoked by a different actor or for a different "
                "reason")
        now = timezone.now()
        payload = {
            "assignment_id": a.pk, "target_user_id": target_user.pk, "role": a.role,
            "revoked_at": now.isoformat(), "reason": reason,
            "authz_snapshot": build_authorization_snapshot(actor, result, evaluated_at),
        }
        event = _append_and_check(actor=actor, action=authz.REVOKE_REVIEWER_ROLE,
                                  target_user=target_user, payload=payload, result=result)
        a.revoked_at = now
        a.revoked_by = actor
        a.revocation_reason = reason
        a.save()
        _close_bootstrap(event)
        _audit_allowed(result, endpoint, target_user=target_user, event=event)
    return event, a


# =================================================================================
# Enable / disable profile
# =================================================================================
def _set_profile_enabled(*, actor, target_user, enabled, reason, action, fn):
    endpoint = _endpoint(fn)
    evaluated_at = timezone.now()
    result = _authorize(actor, action, target_user, fn, at=evaluated_at)
    if not (reason or "").strip():
        raise RoleServiceError("a profile change must record a reason")
    with transaction.atomic():
        profile = (ReviewerProfile.objects.select_for_update()
                   .filter(user=target_user).first())
        if profile is None:
            if not enabled:
                raise RoleServiceError("no profile to disable")
            profile = ReviewerProfile(user=target_user, reviewer_enabled=False)
            profile.save()
        if profile.reviewer_enabled == enabled:
            return None, profile              # idempotent no-op
        payload = {
            "target_user_id": target_user.pk, "enabled": enabled, "reason": reason,
            "authz_snapshot": build_authorization_snapshot(actor, result, evaluated_at),
        }
        event = _append_and_check(actor=actor, action=action, target_user=target_user,
                                  payload=payload, result=result)
        profile.reviewer_enabled = enabled
        profile.save()
        _close_bootstrap(event)
        _audit_allowed(result, endpoint, target_user=target_user, event=event)
    return event, profile


def enable_reviewer_profile(*, actor, target_user, reason):
    return _set_profile_enabled(actor=actor, target_user=target_user, enabled=True,
                                reason=reason, action=authz.ENABLE_REVIEWER_PROFILE,
                                fn="enable_reviewer_profile")


def disable_reviewer_profile(*, actor, target_user, reason):
    return _set_profile_enabled(actor=actor, target_user=target_user, enabled=False,
                                reason=reason, action=authz.DISABLE_REVIEWER_PROFILE,
                                fn="disable_reviewer_profile")
