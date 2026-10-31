from __future__ import annotations

import dataclasses
import re

from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.decision_chain import verify_chain, verify_event
from apps.accounts.models import DecisionChainHead

from .models import CorpusItem, OperationalPermissionProjection as Projection

PERMISSION_PROJECTION_VERSION = "operational_permission/1.0"
_SCOPE_TYPE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
# DIP-1B-1 defines only the global scope (represented by ``None``). A later slice must
# register each scoped domain explicitly before callers can use it.
SUPPORTED_SCOPE_TYPES = frozenset()


@dataclasses.dataclass(frozen=True)
class OperationalPermissionResult:
    allowed: bool
    permission_type: str
    item_id: str | None
    scope_type: str
    scope_id: str
    effective_state: str
    reason_code: str
    projection_id: str | None
    projection_chain_head_hash: str | None
    evaluated_at: object


def _result(*, allowed, permission_type, item, scope_type="", scope_id="",
            state=Projection.State.DENIED, reason, projection=None, at):
    return OperationalPermissionResult(
        allowed=allowed, permission_type=str(permission_type or ""),
        item_id=str(item.pk) if item is not None else None,
        scope_type=scope_type, scope_id=scope_id, effective_state=state,
        reason_code=reason,
        projection_id=str(projection.pk) if projection else None,
        projection_chain_head_hash=(projection.projected_chain_head_hash
                                    if projection else None), evaluated_at=at)


def _scope_parts(scope):
    if scope is None:
        return "", ""
    if isinstance(scope, (tuple, list)) and len(scope) == 2:
        parts = str(scope[0]), str(scope[1])
    elif isinstance(scope, dict) and set(scope) == {"scope_type", "scope_id"}:
        parts = str(scope["scope_type"]), str(scope["scope_id"])
    else:
        return None
    scope_type, scope_id = parts
    if not scope_type or not scope_id or len(scope_id) > 255:
        return None
    if not _SCOPE_TYPE.fullmatch(scope_type):
        return None
    if scope_type not in SUPPORTED_SCOPE_TYPES:
        return None
    return parts


def _projection_event_valid(projection):
    event = projection.source_decision_event
    if event is None or projection.source_sequence_number != event.sequence_number:
        return False
    if event.action not in (authz.GRANT_PERMISSION, authz.GRANT_LEGAL_PERMISSION):
        return False
    payload = event.payload if isinstance(event.payload, dict) else {}
    if (payload.get("corpus_item_id") != str(projection.corpus_item_id)
            or payload.get("permission_type") != projection.permission_type
            or (payload.get("scope_type") or "") != projection.scope_type
            or (payload.get("scope_id") or "") != projection.scope_id):
        return False
    if projection.projection_version != PERMISSION_PROJECTION_VERSION:
        return False
    if not verify_event(event)[0] or not verify_chain().ok:
        return False
    try:
        head = DecisionChainHead.objects.get(pk=1)
    except DecisionChainHead.DoesNotExist:
        return False
    return bool(head.terminal_event_hash) and (
        projection.projected_chain_head_hash == head.terminal_event_hash)


def evaluate_operational_permission(item, permission_type, scope=None, at=None):
    """Canonical fail-closed operational permission boundary."""
    at = at or timezone.now()
    if item is None or not isinstance(item, CorpusItem) or item.pk is None:
        return _result(allowed=False, permission_type=permission_type, item=None,
                       reason="ITEM_REQUIRED", at=at)
    if permission_type not in Projection.Permission.values:
        return _result(allowed=False, permission_type=permission_type, item=item,
                       reason="UNKNOWN_PERMISSION", at=at)
    parts = _scope_parts(scope)
    if parts is None:
        return _result(allowed=False, permission_type=permission_type, item=item,
                       reason="UNKNOWN_SCOPE", at=at)
    scope_type, scope_id = parts
    projection = Projection.objects.filter(
        corpus_item=item, permission_type=permission_type,
        scope_type=scope_type, scope_id=scope_id).first()
    if projection is None:
        return _result(allowed=False, permission_type=permission_type, item=item,
                       scope_type=scope_type, scope_id=scope_id,
                       reason="PROJECTION_ABSENT", at=at)
    if projection.effective_state != Projection.State.ALLOWED:
        return _result(allowed=False, permission_type=permission_type, item=item,
                       scope_type=scope_type, scope_id=scope_id,
                       state=projection.effective_state,
                       reason=f"STATE_{projection.effective_state}",
                       projection=projection, at=at)
    if projection.expires_at is not None and at >= projection.expires_at:
        return _result(allowed=False, permission_type=permission_type, item=item,
                       scope_type=scope_type, scope_id=scope_id,
                       state=Projection.State.EXPIRED, reason="PERMISSION_EXPIRED",
                       projection=projection, at=at)
    if not _projection_event_valid(projection):
        return _result(allowed=False, permission_type=permission_type, item=item,
                       scope_type=scope_type, scope_id=scope_id,
                       state=Projection.State.REVIEW_REQUIRED,
                       reason="UNVERIFIED_PROJECTION_CHECKPOINT",
                       projection=projection, at=at)
    if permission_type == Projection.Permission.AUTOMATIC_USE:
        retrieval = evaluate_operational_permission(
            item, Projection.Permission.RETRIEVAL, scope=scope, at=at)
        if not retrieval.allowed:
            return _result(allowed=False, permission_type=permission_type, item=item,
                           scope_type=scope_type, scope_id=scope_id,
                           state=Projection.State.DENIED,
                           reason="AUTOMATIC_USE_REQUIRES_RETRIEVAL",
                           projection=projection, at=at)
    return _result(allowed=True, permission_type=permission_type, item=item,
                   scope_type=scope_type, scope_id=scope_id,
                   state=Projection.State.ALLOWED, reason="VERIFIED_ALLOW",
                   projection=projection, at=at)
