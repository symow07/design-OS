"""Authenticated dual-control attestations and historical authorization (DIP-1A-5B).

An **attestation** is a protected, signed DecisionEvent in which one authenticated reviewer
asserts a half of a proposed decision. Two complementary attestations, from two DISTINCT
authenticated users, over the IDENTICAL decision binding, form a valid dual-control pair.

**This slice records and validates only — it activates nothing.** A valid pair proves two
authorized reviewers attested to the same proposal; it does not confirm ownership, approve
a licence, select a canonical master, or activate a palette.

Design decisions (from the 1A-5B review):

* Attestations reuse the EXISTING per-category `ATTEST_*` policy actions (already role-
  scoped and already in `SYSTEM_ADMIN_FORBIDDEN`) — no new policy action, and SYSTEM_ADMIN
  is forbidden from substantive attestation by construction. The signed `action` and the
  signed `attestation_category` are cross-checked both ways.
* The authorization snapshot is generated INTERNALLY (`build_authorization_snapshot`) and
  signed in the payload; a caller can never supply it (reserved-field rejection).
* The `decision_scope_hash` (binding) is SERVICE-COMPUTED over canonical bytes; a caller
  cannot supply it. Two attestations combine only when their binding hashes are identical.
* Lifecycle invalidation (revoke / supersede / quarantine / re-review) is a signed-payload
  reference (`invalidates_event_id`), NOT the `supersedes_event` FK — so it does not collide
  with the 1A-4 same-action supersession rule, and it reuses existing reduce-only actions.
* Expiry is COMPUTED and fails closed at read time (`at >= review_expiry`); reading never
  writes.
"""
from __future__ import annotations

import dataclasses
import datetime as dt

from django.db import transaction
from django.utils import timezone

from . import authz_policy as authz
from .authorization import (
    authorize_actor,
    build_authorization_snapshot,
    record_authorization,
)
from .decision_chain import append_decision, verify_event
from .models import DecisionEvent
from .security import canonical

# --- schema + categories ---------------------------------------------------------
ATTESTATION_SCHEMA = "attestation/1.0"
BINDING_SCHEMA = "attestation_binding/1.0"

CATEGORY_TECHNICAL_AND_BRAND = "TECHNICAL_AND_BRAND"
CATEGORY_RIGHTS_AND_OWNERSHIP = "RIGHTS_AND_OWNERSHIP"
CATEGORY_COLOR_AND_BRAND = "COLOR_AND_BRAND"
CATEGORY_RIGHTS_AND_USE = "RIGHTS_AND_USE"

# category -> the existing canonical ATTEST_* action that authorizes it
CATEGORY_ACTION = {
    CATEGORY_TECHNICAL_AND_BRAND: authz.ATTEST_CANONICAL_TECHNICAL,
    CATEGORY_RIGHTS_AND_OWNERSHIP: authz.ATTEST_CANONICAL_LEGAL,
    CATEGORY_COLOR_AND_BRAND: authz.ATTEST_PALETTE_COLOR,
    CATEGORY_RIGHTS_AND_USE: authz.ATTEST_PALETTE_RIGHTS,
}
CATEGORIES = frozenset(CATEGORY_ACTION)
ATTEST_ACTIONS = frozenset(CATEGORY_ACTION.values())

# the complementary pairs that a dual-control decision requires (a substance half + a
# rights half), one for canonical masters, one for palettes
COMPLEMENTARY_PAIRS = frozenset({
    frozenset({CATEGORY_TECHNICAL_AND_BRAND, CATEGORY_RIGHTS_AND_OWNERSHIP}),
    frozenset({CATEGORY_COLOR_AND_BRAND, CATEGORY_RIGHTS_AND_USE}),
})

# --- lifecycle -------------------------------------------------------------------
LIFECYCLE_REVOKED = "ATTESTATION_REVOKED"
LIFECYCLE_SUPERSEDED = "ATTESTATION_SUPERSEDED"
LIFECYCLE_QUARANTINED = "ATTESTATION_QUARANTINED"
LIFECYCLE_RE_REVIEW = "ATTESTATION_RE_REVIEW_REQUIRED"
# ATTESTATION_EXPIRED is COMPUTED (no event) — see effective_attestation_state.

LIFECYCLE_ACTION = {
    LIFECYCLE_REVOKED: authz.REVOKE_DECISION,
    LIFECYCLE_SUPERSEDED: authz.REVOKE_DECISION,
    LIFECYCLE_QUARANTINED: authz.QUARANTINE_ASSET,
    LIFECYCLE_RE_REVIEW: authz.REQUIRE_RE_REVIEW,
}
# every recorded lifecycle event invalidates the target for dual-control purposes (fail
# closed — re-review required is also "do not rely on this until reviewed")
INVALIDATING_LIFECYCLE = frozenset(LIFECYCLE_ACTION)

# --- reserved fields a caller may never supply -----------------------------------
RESERVED_PAYLOAD_FIELDS = frozenset({
    "actor_id", "role_used", "active_roles", "authorizing_roles", "authorization_snapshot",
    "authz_snapshot", "created_at", "sequence_number", "previous_event_hash",
    "signing_key_id", "signature_algorithm", "content_hash", "hmac_signature", "hmac",
    "policy_id", "policy_version", "decision_scope_hash", "attestation_status",
})

# policy versions this build can interpret historically
KNOWN_POLICY_VERSIONS = frozenset(authz.POLICY_VERSIONS)

# review-warning codes (not fatal, but a reviewer must see them)
POLICY_REVIEW_REQUIRED = "POLICY_REVIEW_REQUIRED"
IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY = "IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY"


class AttestationError(RuntimeError):
    """The attestation request is invalid. FAIL CLOSED — nothing is recorded."""


class AttestationDenied(AttestationError):
    """The actor is not authorized to attest in this category."""


def _endpoint(name):
    return f"accounts.attestation.{name}"


def _reject_reserved(extras):
    if not extras:
        return
    bad = set(extras) & (RESERVED_PAYLOAD_FIELDS | {
        "attestation_schema", "attestation_category", "decision_type", "decision_version",
        "evidence_refs", "valid_from", "review_expiry", "contradiction_present",
        "contradiction_refs", "contradiction_acknowledged",
        "contradiction_acknowledgement_reason", "normalized_scope", "invalidates_event_id",
        "lifecycle_kind"})
    if bad:
        raise AttestationError(
            f"payload may not supply reserved/managed fields: {sorted(bad)} — these are "
            "computed and signed by the service, never accepted from the caller.")


# --- decision/scope binding ------------------------------------------------------
def binding_hash(*, subject_type, subject_id, decision_type, decision_version,
                 normalized_scope, evidence_refs, contradiction_present) -> str:
    """SERVICE-computed binding over canonical bytes. Two attestations combine only when
    these hashes are identical — never on human-readable names alone."""
    doc = {
        "binding_schema": BINDING_SCHEMA,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "decision_type": decision_type,
        "decision_version": decision_version,
        "normalized_scope": normalized_scope,
        "evidence_refs": sorted(evidence_refs or []),
        "contradiction_present": bool(contradiction_present),
    }
    return canonical.content_hash(doc)


# =================================================================================
# Record an attestation
# =================================================================================
def _authorize_or_deny(user, action, subject, endpoint):
    result = authorize_actor(user, action, subject=subject)
    if not result.allowed:
        from .authorization import _best_effort_record
        _best_effort_record(result, None, endpoint, "SERVICE")
        raise AttestationDenied(f"{action}: {result.reason_code}")
    return result


def record_attestation(*, user, subject_type, subject_id, decision_type, decision_version,
                       attestation_category, normalized_scope, evidence_refs, review_expiry,
                       valid_from=None, contradiction_present=False, contradiction_refs=None,
                       contradiction_acknowledged=False,
                       contradiction_acknowledgement_reason="", payload_extras=None
                       ) -> DecisionEvent:
    """Record one protected attestation. The service derives actor/role/snapshot internally;
    the caller supplies decision facts only."""
    fn = "record_attestation"
    endpoint = _endpoint(fn)
    if attestation_category not in CATEGORIES:
        raise AttestationError(f"unknown attestation_category {attestation_category!r}")
    action = CATEGORY_ACTION[attestation_category]
    _reject_reserved(payload_extras)

    if contradiction_present and not contradiction_acknowledged:
        raise AttestationError("a present contradiction must be acknowledged")

    now = timezone.now()
    valid_from = valid_from or now
    if review_expiry is None or review_expiry <= valid_from:
        raise AttestationError("review_expiry is required and must be after valid_from")

    scope_hash = binding_hash(
        subject_type=subject_type, subject_id=subject_id, decision_type=decision_type,
        decision_version=decision_version, normalized_scope=normalized_scope,
        evidence_refs=evidence_refs, contradiction_present=contradiction_present)

    subject = (subject_type, subject_id)
    result = _authorize_or_deny(user, action, subject, endpoint)

    with transaction.atomic():
        snapshot = build_authorization_snapshot(user, result, now)
        payload = {
            "attestation_schema": ATTESTATION_SCHEMA,
            "decision_type": decision_type,
            "decision_version": decision_version,
            "attestation_category": attestation_category,
            "decision_scope_hash": scope_hash,
            "normalized_scope": normalized_scope,
            "evidence_refs": list(evidence_refs or []),
            "valid_from": valid_from.isoformat(),
            "review_expiry": review_expiry.isoformat(),
            "contradiction_present": bool(contradiction_present),
            "contradiction_refs": list(contradiction_refs or []),
            "contradiction_acknowledged": bool(contradiction_acknowledged),
            "contradiction_acknowledgement_reason": contradiction_acknowledgement_reason,
            "attestation_status": "RECORDED",
            "authz_snapshot": snapshot,
        }
        if payload_extras:
            payload.update(payload_extras)
        event = append_decision(user=user, action=action, payload=payload, subject=subject)
        if event.role_used != result.role_used:
            raise AttestationError(
                f"role_used skew: service {result.role_used!r} vs append "
                f"{event.role_used!r}")
        # the signed category must match the signed action — this reuse's key seam
        if CATEGORY_ACTION[attestation_category] != event.action:
            raise AttestationError("attestation_category does not match its action")
        record_authorization(result, request=None, endpoint=endpoint, method="SERVICE",
                             metadata={"event_id": event.event_id,
                                       "category": attestation_category})
    return event


def record_attestation_lifecycle(*, user, target_event, lifecycle_kind, reason
                                 ) -> DecisionEvent:
    """Append a lifecycle event (revoke/supersede/quarantine/re-review) that invalidates a
    prior attestation via a SIGNED payload reference. Never edits the original."""
    fn = "record_attestation_lifecycle"
    endpoint = _endpoint(fn)
    if lifecycle_kind not in LIFECYCLE_ACTION:
        raise AttestationError(f"unknown lifecycle_kind {lifecycle_kind!r}")
    if not _is_attestation(target_event):
        raise AttestationError("target is not an attestation event")
    if not (reason or "").strip():
        raise AttestationError("a lifecycle event must record a reason")
    action = LIFECYCLE_ACTION[lifecycle_kind]
    subject = (target_event.subject_type, target_event.subject_id)
    result = _authorize_or_deny(user, action, subject, endpoint)

    with transaction.atomic():
        snapshot = build_authorization_snapshot(user, result, timezone.now())
        payload = {
            "lifecycle_kind": lifecycle_kind,
            "invalidates_event_id": target_event.event_id,
            "reason": reason,
            "authz_snapshot": snapshot,
        }
        event = append_decision(user=user, action=action, payload=payload, subject=subject)
        if event.role_used != result.role_used:
            raise AttestationError("role_used skew")
        record_authorization(result, request=None, endpoint=endpoint, method="SERVICE",
                             metadata={"event_id": event.event_id,
                                       "invalidates": target_event.event_id})
    return event


# =================================================================================
# Read-only evaluation (writes nothing)
# =================================================================================
def _is_attestation(event) -> bool:
    return (event.action in ATTEST_ACTIONS
            and isinstance(event.payload, dict)
            and event.payload.get("attestation_schema") == ATTESTATION_SCHEMA)


def _parse_dt(value):
    return dt.datetime.fromisoformat(value)


@dataclasses.dataclass(frozen=True)
class EffectiveState:
    effective: bool
    status: str
    reasons: tuple[str, ...]


def effective_attestation_state(event, at=None) -> EffectiveState:
    """The current effective state of an attestation — READ ONLY, writes nothing. Fails
    closed on any invalidation: a non-verifying event, computed expiry, or a recorded
    lifecycle event referencing it."""
    at = at or timezone.now()
    if not _is_attestation(event):
        return EffectiveState(False, "NOT_AN_ATTESTATION", ("not an attestation event",))
    ok, problems = verify_event(event)
    if not ok:
        return EffectiveState(False, "CHAIN_INVALID", problems)

    # expiry is COMPUTED and fails closed — no event required
    review_expiry = _parse_dt(event.payload["review_expiry"])
    if at >= review_expiry:
        return EffectiveState(False, "EXPIRED", ("past review_expiry",))

    # any verifiable lifecycle event that references this attestation invalidates it
    for inv in (DecisionEvent.objects
                .filter(action__in=set(LIFECYCLE_ACTION.values()))
                .filter(payload__invalidates_event_id=event.event_id)):
        kind = inv.payload.get("lifecycle_kind")
        if kind in INVALIDATING_LIFECYCLE and verify_event(inv)[0]:
            return EffectiveState(False, kind, (f"invalidated by {inv.event_id}",))

    return EffectiveState(True, "EFFECTIVE", ())


@dataclasses.dataclass(frozen=True)
class HistoricalRoleResult:
    valid: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def historical_role_validity(event) -> HistoricalRoleResult:
    """Was the actor's `role_used` genuinely valid AT the event's signed timestamp? Uses the
    signed snapshot's assignment ids + the assignment rows; evaluates under the event's
    PINNED policy version. A later revocation does not retro-invalidate a then-valid event.
    """
    reasons: list[str] = []
    warnings: list[str] = [IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY]
    snap = event.payload.get("authz_snapshot") if isinstance(event.payload, dict) else None
    if not isinstance(snap, dict):
        return HistoricalRoleResult(False, ("missing authorization snapshot",),
                                    tuple(warnings))

    if snap.get("policy_version") not in KNOWN_POLICY_VERSIONS:
        # do NOT silently reinterpret under the current policy
        return HistoricalRoleResult(False, (POLICY_REVIEW_REQUIRED,), tuple(warnings))

    if snap.get("role_used") != event.role_used:
        reasons.append("snapshot role_used != event role_used")

    # the recorded role must have authorized the recorded action under the pinned policy
    policy = authz.policy_for_version(snap.get("policy_version"))
    if event.role_used not in policy.get(event.action, ()):
        reasons.append("role_used did not authorize the action under the pinned policy")

    # a live assignment (at event time) backing role_used must exist among the snapshot ids
    from .models import ReviewerRoleAssignment
    created = event.created_at
    backing = (ReviewerRoleAssignment.objects
               .filter(pk__in=snap.get("assignment_ids", []), user_id=event.actor_id,
                       role=event.role_used))
    if not any(a.granted_at <= created
               and created < a.expires_at
               and (a.revoked_at is None or created < a.revoked_at)
               for a in backing):
        reasons.append("no role assignment was valid at the event timestamp")

    return HistoricalRoleResult(not reasons, tuple(reasons), tuple(warnings))


# =================================================================================
# Dual control (pure validator — writes nothing)
# =================================================================================
@dataclasses.dataclass(frozen=True)
class DualControlResult:
    valid: bool
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def validate_dual_control(attestation_a, attestation_b, at=None) -> DualControlResult:
    """Pure validator. A valid pair requires two verified, currently-effective attestations
    from two DISTINCT authenticated users, in complementary categories, over an IDENTICAL
    decision binding. Writes nothing."""
    at = at or timezone.now()
    reasons: list[str] = []
    warnings: list[str] = []

    for ev in (attestation_a, attestation_b):
        if not _is_attestation(ev):
            reasons.append(f"{getattr(ev, 'event_id', ev)} is not an attestation")
    if reasons:
        return DualControlResult(False, tuple(reasons), ())

    # distinct AUTHENTICATED actors — one user with several roles is still one actor
    if attestation_a.actor_id == attestation_b.actor_id:
        reasons.append("the same authenticated user cannot satisfy both halves")

    ca = attestation_a.payload.get("attestation_category")
    cb = attestation_b.payload.get("attestation_category")
    if not ca or not cb:
        reasons.append("an attestation is missing its category")
    elif frozenset({ca, cb}) not in COMPLEMENTARY_PAIRS:
        reasons.append(f"categories {ca}/{cb} are not a complementary dual-control pair")

    # each event's signed category must match its signed action
    for ev in (attestation_a, attestation_b):
        cat = ev.payload.get("attestation_category")
        if CATEGORY_ACTION.get(cat) != ev.action:
            reasons.append(f"{ev.event_id}: category/action mismatch")

    # identical decision binding — same subject / type / version / scope hash
    for key in ("subject_type", "subject_id"):
        if getattr(attestation_a, key) != getattr(attestation_b, key):
            reasons.append(f"{key} differs between the two attestations")
    for key in ("decision_type", "decision_version", "decision_scope_hash"):
        if attestation_a.payload.get(key) != attestation_b.payload.get(key):
            reasons.append(f"{key} differs between the two attestations")

    # compatible policy version
    pa = attestation_a.payload.get("authz_snapshot", {}).get("policy_version")
    pb = attestation_b.payload.get("authz_snapshot", {}).get("policy_version")
    if pa != pb:
        reasons.append("attestations were made under different policy versions")

    # both currently effective (chain-valid, not expired/revoked/superseded/quarantined)
    for ev in (attestation_a, attestation_b):
        es = effective_attestation_state(ev, at)
        if not es.effective:
            reasons.append(f"{ev.event_id} is not effective: {es.status}")

    # historical role validity for each
    for ev in (attestation_a, attestation_b):
        hv = historical_role_validity(ev)
        warnings = list(warnings) + list(hv.warnings)
        if not hv.valid:
            reasons.append(f"{ev.event_id} historical role invalid: {hv.reasons}")

    return DualControlResult(not reasons, tuple(reasons), tuple(dict.fromkeys(warnings)))
