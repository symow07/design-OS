"""The canonical authorization service (DIP-1A-3).

`authorize_actor(user, action, subject=None, at=None)` is the ONE place a request is turned
into an authorization decision. It is a **pure** function of the authenticated user, the
persisted role assignments, and the canonical policy — it reads, it never writes, and it
authorizes nothing by side effect. Persisting the attempt is a separate step
(`record_authorization`), so a decision and its audit can be composed under one transaction
by the enforcement layer without the decision itself depending on the database being
writable.

**The caller never chooses the answer.** Not the actor id (it is `request.user.pk`), not
the active roles (they are the persisted assignments), not `role_used` (policy selects it),
not the result. A request body may contain an `actor_id` or a `role` field; this service
ignores both, by construction — it never reads them.

**Deny by default.** Every path that is not an explicit allow returns a denial with a
structured `reason_code`. The order of checks is fixed so the reason is stable and
meaningful: identity first, then reviewer standing, then the action, then the roles.
"""
from __future__ import annotations

import dataclasses
import functools
import logging
import re
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from . import authz_policy as authz
from .models import (
    RESULT_ALLOWED,
    RESULT_DENIED,
    USER_AGENT_MAX,
    AuthorizationAudit,
    ReviewerRoleAssignment,
    active_roles,
)

log = logging.getLogger("accounts.authorization")

# The authorization-snapshot schema. Bumped only if the snapshot's fields change; the
# verifier keys historical interpretation off it.
AUTHZ_SNAPSHOT_SCHEMA = "authz_snapshot/1.0"
AUTHZ_SNAPSHOT_FIELDS = frozenset({
    "snapshot_schema",
    "policy_id",
    "policy_version",
    "actor_id",
    "user_is_active",
    "reviewer_enabled",
    "active_roles",
    "authorizing_roles",
    "role_used",
    "assignment_ids",
    "reason_code",
    "action",
    "subject_type",
    "subject_id",
    "evaluation_timestamp",
})

# --- structured reason codes -----------------------------------------------------
# Stable strings, safe to store, filter and alert on. NEVER free-form exception text.
UNAUTHENTICATED = "UNAUTHENTICATED"
USER_INACTIVE = "USER_INACTIVE"
REVIEWER_PROFILE_MISSING = "REVIEWER_PROFILE_MISSING"
REVIEWER_DISABLED = "REVIEWER_DISABLED"
NO_ACTIVE_ROLE = "NO_ACTIVE_ROLE"
ACTION_UNKNOWN = "ACTION_UNKNOWN"
ROLE_NOT_AUTHORIZED = "ROLE_NOT_AUTHORIZED"
SYSTEM_ADMIN_FORBIDDEN = "SYSTEM_ADMIN_FORBIDDEN"
# A service-layer denial (the actor is authorized for the action in general, but not for
# THIS target) — recorded so a self-appointment attempt leaves an audit trail.
SELF_ELEVATION_FORBIDDEN = "SELF_ELEVATION_FORBIDDEN"
AUTHORIZED = "AUTHORIZED"

DENIAL_REASONS = (
    UNAUTHENTICATED, USER_INACTIVE, REVIEWER_PROFILE_MISSING, REVIEWER_DISABLED,
    NO_ACTIVE_ROLE, ACTION_UNKNOWN, ROLE_NOT_AUTHORIZED, SYSTEM_ADMIN_FORBIDDEN,
    SELF_ELEVATION_FORBIDDEN,
)
ALL_REASONS = DENIAL_REASONS + (AUTHORIZED,)


@dataclasses.dataclass(frozen=True)
class AuthorizationResult:
    """The decision. Immutable — nothing downstream may edit an authorization outcome."""

    allowed: bool
    reason_code: str
    action: str
    actor_id: int | None
    active_roles: tuple[str, ...]
    authorizing_roles: tuple[str, ...]
    role_used: str | None
    subject_type: str | None
    subject_id: str | None
    selection_rule: str | None

    def __post_init__(self):
        # An allow MUST name the role it was granted under; a denial MUST NOT.
        if self.allowed:
            assert self.reason_code == AUTHORIZED and self.role_used is not None
        else:
            assert self.reason_code in DENIAL_REASONS and self.role_used is None


def _subject_parts(subject):
    """(subject_type, subject_id) from a (type, id) pair, or (None, None)."""
    if subject is None:
        return None, None
    if isinstance(subject, (tuple, list)) and len(subject) == 2:
        st, si = subject
        return (None if st is None else str(st)), (None if si is None else str(si))
    # a bare id with no type carries no meaning for audit; require the pair
    raise ValueError("subject must be a (subject_type, subject_id) pair or None")


def _deny(reason, *, action, actor_id, active, authorizing, subject):
    st, si = _subject_parts(subject)
    return AuthorizationResult(
        allowed=False, reason_code=reason, action=action, actor_id=actor_id,
        active_roles=tuple(active), authorizing_roles=tuple(authorizing),
        role_used=None, subject_type=st, subject_id=si, selection_rule=None)


def authorize_actor(user, action, subject=None, at=None) -> AuthorizationResult:
    """Decide whether `user` may perform `action`. Pure; deny by default.

    `subject` is an optional `(subject_type, subject_id)` pair, recorded for audit only —
    object-level scoping is a later concern and never loosens this decision.
    """
    at = at or timezone.now()
    actor_id = getattr(user, "pk", None) if getattr(user, "is_authenticated", False) \
        else None

    # 1) identity
    if user is None or not getattr(user, "is_authenticated", False):
        return _deny(UNAUTHENTICATED, action=action, actor_id=None,
                     active=(), authorizing=(), subject=subject)
    if not getattr(user, "is_active", False):
        return _deny(USER_INACTIVE, action=action, actor_id=actor_id,
                     active=(), authorizing=(), subject=subject)

    # 2) reviewer standing
    profile = getattr(user, "reviewer_profile", None)
    if profile is None:
        return _deny(REVIEWER_PROFILE_MISSING, action=action, actor_id=actor_id,
                     active=(), authorizing=(), subject=subject)
    if not profile.reviewer_enabled:
        return _deny(REVIEWER_DISABLED, action=action, actor_id=actor_id,
                     active=(), authorizing=(), subject=subject)

    # 3) the action must be a known policy action BEFORE we consult roles
    if action not in authz.ACTIONS:
        return _deny(ACTION_UNKNOWN, action=action, actor_id=actor_id,
                     active=(), authorizing=(), subject=subject)

    # 4) roles — resolved from persisted assignments, never from the request
    active = active_roles(user, at=at)
    if not active:
        return _deny(NO_ACTIVE_ROLE, action=action, actor_id=actor_id,
                     active=(), authorizing=(), subject=subject)

    authorizing = authz.authorizing_roles(action, active)
    if not authorizing:
        # Distinguish "admin power is not authority" from a plain lack of standing: if the
        # actor holds SYSTEM_ADMIN and the action is one SYSTEM_ADMIN may NEVER perform,
        # say so explicitly — even if they also hold another (also-unauthorized) role.
        if authz.SYSTEM_ADMIN in active and action in authz.SYSTEM_ADMIN_FORBIDDEN:
            reason = SYSTEM_ADMIN_FORBIDDEN
        else:
            reason = ROLE_NOT_AUTHORIZED
        return _deny(reason, action=action, actor_id=actor_id,
                     active=active, authorizing=(), subject=subject)

    role_used = authz.select_role_used(action, active)
    # select_role_used draws from the same policy as authorizing_roles, so this holds; the
    # assert makes a future policy/precedence divergence fail loudly rather than silently
    # authorize under a role that does not appear in `authorizing`.
    assert role_used in authorizing, "role_used must be one of the authorizing roles"
    st, si = _subject_parts(subject)
    return AuthorizationResult(
        allowed=True, reason_code=AUTHORIZED, action=action, actor_id=actor_id,
        active_roles=active, authorizing_roles=authorizing, role_used=role_used,
        subject_type=st, subject_id=si, selection_rule=authz.ROLE_SELECTION_RULE)


# =================================================================================
# Persisting the attempt — separate from deciding it
# =================================================================================
_CORRELATION_RE = re.compile(r"\A[A-Za-z0-9._-]{1,64}\Z")


def _correlation_id(request, supplied) -> str:
    """A safe correlation id. Prefer an explicit value, then the request's own id, then a
    fresh UUID. Anything malformed or over-long is DISCARDED, not truncated-and-stored —
    the middleware honours an inbound X-Request-ID with no length cap, so we never trust
    it blindly here."""
    for candidate in (supplied, getattr(request, "request_id", None)):
        if candidate and _CORRELATION_RE.match(str(candidate)):
            return str(candidate)
    return uuid.uuid4().hex


def _client_ip(request):
    """The client IP, honouring forwarded headers ONLY from configured trusted proxies.

    Off by default (`AUTHORIZATION_AUDIT_RECORD_IP=False`): source IP is personal data and
    is recorded only when operationally required and permitted. `X-Forwarded-For` is
    trusted only when the direct peer (`REMOTE_ADDR`) is in `AUTHORIZATION_TRUSTED_PROXIES`
    — never on the say-so of an arbitrary header, which any client can forge.
    """
    if request is None or not getattr(settings, "AUTHORIZATION_AUDIT_RECORD_IP", False):
        return None
    remote = request.META.get("REMOTE_ADDR")
    trusted = set(getattr(settings, "AUTHORIZATION_TRUSTED_PROXIES", ()) or ())
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff and remote in trusted:
        return xff.split(",")[0].strip() or remote
    return remote


def record_authorization(result: AuthorizationResult, *, request=None, endpoint: str,
                         method: str = "", metadata: dict | None = None
                         ) -> AuthorizationAudit:
    """Write ONE audit row from a decided result. Server-side only; nothing here is taken
    from the request body. Raises if the row cannot be written — callers decide whether
    that is fail-closed (allowed decision-class action) or best-effort (a denial)."""
    ua = ""
    if request is not None:
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:USER_AGENT_MAX]
    row = AuthorizationAudit(
        user_id=result.actor_id,
        action=result.action,
        subject_type=result.subject_type or "",
        subject_id=result.subject_id or "",
        result=RESULT_ALLOWED if result.allowed else RESULT_DENIED,
        reason_code=result.reason_code,
        active_roles=list(result.active_roles),
        authorizing_roles=list(result.authorizing_roles),
        role_used=result.role_used or "",
        selection_rule=result.selection_rule or "",
        endpoint=endpoint[:200],
        request_method=(method or "")[:8],
        correlation_id=_correlation_id(request, None),
        source_ip=_client_ip(request),
        user_agent=ua,
        metadata=metadata or {},
    )
    row.save()
    return row


def _best_effort_record(result, request, endpoint, method=""):
    """Audit a DENIAL. A failed write must NOT turn a denial into an allow, so we swallow
    the error (logged, without leaking internals to the requester) — the request stays
    denied regardless."""
    try:
        record_authorization(result, request=request, endpoint=endpoint, method=method)
    except Exception:  # noqa: BLE001 - denial stands even if audit fails
        log.exception("authorization-audit write failed for a DENIED attempt "
                      "(action=%s reason=%s endpoint=%s)",
                      result.action, result.reason_code, endpoint)


def build_authorization_snapshot(user, result: AuthorizationResult, at) -> dict:
    """The signed authorization snapshot: evidence of exactly what the application verified
    at append time. Generated INTERNALLY by the protected service (a caller can never
    supply it — reserved-field rejection blocks that), then signed as part of the event
    payload. It records the *observed* mutable identity state (User.is_active,
    ReviewerProfile.reviewer_enabled) so a historical check reads the append-time truth
    rather than the account's current status.
    """
    profile = getattr(user, "reviewer_profile", None)
    assignment_ids = list(
        ReviewerRoleAssignment.objects.filter(user=user).active_at(at)
        .order_by("pk").values_list("pk", flat=True))
    return {
        "snapshot_schema": AUTHZ_SNAPSHOT_SCHEMA,
        "policy_id": authz.POLICY_ID,
        "policy_version": authz.POLICY_VERSION,
        "actor_id": user.pk,
        "user_is_active": bool(getattr(user, "is_active", False)),
        "reviewer_enabled": bool(profile and profile.reviewer_enabled),
        "active_roles": list(result.active_roles),
        "authorizing_roles": list(result.authorizing_roles),
        "role_used": result.role_used,
        "assignment_ids": assignment_ids,
        "reason_code": result.reason_code,
        "action": result.action,
        "subject_type": result.subject_type or "",
        "subject_id": result.subject_id or "",
        "evaluation_timestamp": at.isoformat(),
    }


# =================================================================================
# Enforcement — the server-side decision boundary
# =================================================================================
# Every protected endpoint declares exactly ONE canonical action here at import time. The
# policy-drift system check validates the set against authz.ACTIONS; a test proves the set
# is non-empty and that an unknown action is caught. This is the DIP *reviewer* policy — it
# is deliberately separate from the legacy pipeline Group permissions in
# apps/pipeline/permissions.py, which are a different system and out of scope.
PROTECTED_ACTIONS: set[str] = set()


def register_protected_action(action: str) -> None:
    PROTECTED_ACTIONS.add(action)


class PermissionDeniedWithReason(PermissionDenied):
    """A denial that carries the structured reason code (not the internal detail)."""

    def __init__(self, result: AuthorizationResult):
        self.reason_code = result.reason_code
        self.action = result.action
        super().__init__(f"not authorized: {result.reason_code}")


def _endpoint_name(fn) -> str:
    return f"{getattr(fn, '__module__', '?')}.{getattr(fn, '__qualname__', fn)}"


def require_reviewer_action(action: str, *, subject_resolver=None):
    """Decorator for function views. Enforces ONE canonical action.

    Denial: the attempt is audited best-effort and the request is refused. Allowed: the
    view runs and the audit row is written in the SAME transaction, so an audit-write
    failure rolls the action back — an allowed decision never commits unaudited.
    """
    register_protected_action(action)

    def decorator(view):
        endpoint = _endpoint_name(view)

        @functools.wraps(view)
        def wrapped(request, *args, **kwargs):
            subject = subject_resolver(request, *args, **kwargs) \
                if subject_resolver else None
            result = authorize_actor(getattr(request, "user", None), action,
                                     subject=subject)
            if not result.allowed:
                _best_effort_record(result, request, endpoint, request.method)
                raise PermissionDeniedWithReason(result)
            # allowed: action + audit share one transaction. The view's writes happen
            # first, then the audit; if the audit cannot be written the whole thing rolls
            # back and nothing commits. Fail closed.
            with transaction.atomic():
                response = view(request, *args, **kwargs)
                record_authorization(result, request=request, endpoint=endpoint,
                                     method=request.method)
                return response
        wrapped.required_action = action
        return wrapped
    return decorator


class ReviewerActionMixin:
    """CBV/APIView mixin. Set `required_action` on the view. Same transactional,
    fail-closed guarantee as the decorator, applied around `dispatch`."""

    required_action: str | None = None
    subject_resolver = None

    def get_authorization_subject(self, request, *args, **kwargs):
        if callable(self.subject_resolver):
            return self.subject_resolver(request, *args, **kwargs)
        return None

    def dispatch(self, request, *args, **kwargs):
        action = self.required_action
        assert action, f"{type(self).__name__} must set required_action"
        register_protected_action(action)
        endpoint = f"{type(self).__module__}.{type(self).__qualname__}"
        subject = self.get_authorization_subject(request, *args, **kwargs)
        result = authorize_actor(getattr(request, "user", None), action, subject=subject)
        if not result.allowed:
            _best_effort_record(result, request, endpoint, request.method)
            raise PermissionDeniedWithReason(result)
        with transaction.atomic():
            response = super().dispatch(request, *args, **kwargs)
            record_authorization(result, request=request, endpoint=endpoint,
                                 method=request.method)
            return response


try:  # DRF is installed; the permission class is optional sugar for read-only gates.
    from rest_framework.permissions import BasePermission

    class ReviewerActionPermission(BasePermission):
        """DRF gate for endpoints WITHOUT a transactional side effect (reads, queries).

        Reads `view.required_action`, runs the full fail-closed pipeline itself (so an
        unauthenticated attempt is audited with user=NULL rather than being rejected
        upstream by IsAuthenticated), and audits the attempt in `has_permission`.

        It does NOT provide the allowed-path transaction guarantee — a side-effecting
        decision-class endpoint MUST use `require_reviewer_action` or `ReviewerActionMixin`
        so the action and its audit commit together. Protected views should set
        `permission_classes = [ReviewerActionPermission]` explicitly to override the global
        IsAuthenticated default, or the pipeline's unauth audit row would never be written.
        """

        message = "not authorized"

        def has_permission(self, request, view):
            action = getattr(view, "required_action", None)
            assert action, f"{type(view).__name__} must set required_action"
            register_protected_action(action)
            endpoint = f"{type(view).__module__}.{type(view).__qualname__}"
            result = authorize_actor(getattr(request, "user", None), action)
            # A read gate has no side effect to roll back, so a best-effort audit is
            # correct for BOTH outcomes here.
            _best_effort_record(result, request, endpoint, request.method)
            if not result.allowed:
                self.message = f"not authorized: {result.reason_code}"
            return result.allowed
except ImportError:  # pragma: no cover - DRF is a hard dependency in this project
    ReviewerActionPermission = None
