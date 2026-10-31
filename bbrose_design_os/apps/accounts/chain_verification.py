"""Comprehensive, read-only verification of the decision chain (DIP-1A-5C).

This composes the existing primitives — `verify_chain` (whole-chain crypto/linkage/head),
`verify_event` (single-event crypto), `effective_attestation_state`, and the historical
role logic — and CLASSIFIES their outputs. It computes no hash or HMAC of its own (the
single-definition serializer/signer stays the only one) and it **writes nothing, ever**.

Classification is deliberate, because a verification tool that calls everything "VALID" or
everything "INVALID" is useless:

* **FATAL** (fails the command): a cryptographic/chain-integrity failure, an event whose key
  is unavailable, an internally-contradictory *signed* event (its snapshot disagrees with
  its own envelope), or a signed snapshot whose `role_used` did not authorize the action
  under the pinned policy. These rest on SIGNED evidence.
* **WARNING** (reported, qualified, non-fatal): a policy version this build cannot
  interpret; live (unsigned) assignment rows that fail to corroborate the signed snapshot —
  which is evidence the assignment TABLE may have been mutated, NOT that the original event
  was unauthorized (letting an out-of-chain mutation fail verification would be a cheap
  denial-of-verification); the append-time-only nature of identity state; and an
  attestation that is expired/revoked/superseded (a normal lifecycle state, not an integrity
  fault).

**Bounded mode** verifies only a slice; whole-chain properties (previous-hash linkage,
head-vs-terminal reconciliation) cannot be established from a slice, so bounded output is
labelled diagnostic and never reports a bare "VALID".
"""
from __future__ import annotations

import dataclasses

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import authz_policy as authz
from . import bootstrap_registry, bootstrap_verification
from .attestation import (
    IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY,
    KNOWN_POLICY_VERSIONS,
    LIFECYCLE_ACTION,
    POLICY_REVIEW_REQUIRED,
    _is_attestation,
    effective_attestation_state,
)
from .decision_chain import verify_chain, verify_event
from .authorization import AUTHORIZED, AUTHZ_SNAPSHOT_FIELDS, AUTHZ_SNAPSHOT_SCHEMA
from .models import DecisionChainHead, DecisionEvent, ReviewerRoleAssignment
from .security import key_epochs

# --- result codes ----------------------------------------------------------------
VALID = "VALID"
CHAIN_INVALID = "CHAIN_INVALID"                              # fatal
KEY_UNAVAILABLE = "KEY_UNAVAILABLE"                          # fatal
INVALID = "INVALID"                                          # fatal (snapshot != envelope)
ROLE_HISTORY_INVALID = "ROLE_HISTORY_INVALID"               # fatal (signed snapshot)
ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE = "ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE"  # warning
ATTESTATION_INEFFECTIVE = "ATTESTATION_INEFFECTIVE"         # warning
# DECISION-EVENT KEY EPOCH RESET (2026-07-25) — both WARNINGS: a formally
# declared lost-key epoch is an auditable classification, not a chain failure;
# the affected events individually stay fail-closed (verify_event refuses).
LEGACY_SIGNATURE_UNVERIFIABLE = key_epochs.LEGACY_SIGNATURE_UNVERIFIABLE
LEGACY_DECISION_REAFFIRMATION_REQUIRED = (
    key_epochs.LEGACY_DECISION_REAFFIRMATION_REQUIRED)
# DIP-1A-BOOTSTRAP-CORR-2 — fatal. The bootstrap ceremony is verified by its own module;
# these classify its failures in the shared vocabulary.
BOOTSTRAP_EVENT_INVALID = bootstrap_verification.BOOTSTRAP_EVENT_INVALID
BOOTSTRAP_SENTINEL_MISUSED = bootstrap_verification.BOOTSTRAP_SENTINEL_MISUSED
BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN = (
    bootstrap_verification.BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN)
# (POLICY_REVIEW_REQUIRED and IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY are imported from
#  attestation — one vocabulary.)

FATAL_CODES = frozenset({
    CHAIN_INVALID, KEY_UNAVAILABLE, INVALID, ROLE_HISTORY_INVALID,
    BOOTSTRAP_EVENT_INVALID, BOOTSTRAP_SENTINEL_MISUSED,
    BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN})
SEV_FATAL = "FATAL"
SEV_WARNING = "WARNING"

ROLE_LIFECYCLE_ACTIONS = frozenset({
    authz.GRANT_REVIEWER_ROLE,
    authz.REVOKE_REVIEWER_ROLE,
    authz.ENABLE_REVIEWER_PROFILE,
    authz.DISABLE_REVIEWER_PROFILE,
})
INTELLIGENCE_ASSERTION_ACTIONS = frozenset({
    authz.RECORD_INTELLIGENCE_CLASSIFICATION,
    authz.CORRECT_INTELLIGENCE_CLASSIFICATION,
    authz.RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT,
    authz.REQUEST_INTELLIGENCE_CLARIFICATION,
})
GOVERNANCE_ACTIONS = frozenset({
    authz.FINALIZE_CANONICAL_BRAND_ASSET,
    authz.REVOKE_CANONICAL_BRAND_ASSET,
    authz.FINALIZE_PRIMARY_BRAND_PALETTE,
    authz.REVOKE_PRIMARY_BRAND_PALETTE,
})


@dataclasses.dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    sequence_number: int | None
    event_id: str | None
    detail: str

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class ChainVerificationReport:
    ok: bool                       # no FATAL findings
    mode: str                      # "full" | "bounded"
    verified_events: int           # events inspected in this run
    total_events: int              # events in the whole chain
    head_checked: bool
    fatal: tuple[Finding, ...]
    warnings: tuple[Finding, ...]

    @property
    def status(self) -> str:
        if self.fatal:
            return "FATAL"
        if self.mode == "bounded":
            # a slice cannot establish whole-chain integrity — never a bare VALID
            return "DIAGNOSTIC_OK" if not self.warnings else "DIAGNOSTIC_WARNINGS"
        return VALID if not self.warnings else "VALID_WITH_WARNINGS"

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "ok": self.ok,
            "mode": self.mode,
            "verified_events": self.verified_events,
            "total_events": self.total_events,
            "head_checked": self.head_checked,
            "fatal": [f.as_dict() for f in self.fatal],
            "warnings": [f.as_dict() for f in self.warnings],
        }


def _fatal(code, ev, detail):
    return Finding(SEV_FATAL, code,
                   getattr(ev, "sequence_number", None) if ev else None,
                   getattr(ev, "event_id", None) if ev else None, detail)


def _warn(code, ev, detail):
    return Finding(SEV_WARNING, code, ev.sequence_number, ev.event_id, detail)


def _snapshot_contract_error(ev, snap) -> str | None:
    """Validate the explicit signed ``authz_snapshot/1.0`` vocabulary.

    A schema marker does not make a partial mapping safe. Version 1.0 has one exact field
    set and fixed internal relationships; a producer must bump the schema before changing
    that vocabulary. Verification never fills a gap from mutable current database state.
    """
    schema = snap.get("snapshot_schema")
    if schema != AUTHZ_SNAPSHOT_SCHEMA:
        return (f"unsupported authorization snapshot schema {schema!r}; "
                f"expected {AUTHZ_SNAPSHOT_SCHEMA!r}")

    fields = set(snap)
    missing = sorted(AUTHZ_SNAPSHOT_FIELDS - fields)
    unexpected = sorted(fields - AUTHZ_SNAPSHOT_FIELDS)
    if missing or unexpected:
        return (f"authorization snapshot fields do not match {AUTHZ_SNAPSHOT_SCHEMA}: "
                f"missing={missing}, unexpected={unexpected}")

    scalar_types = {
        "policy_id": str,
        "policy_version": str,
        "actor_id": int,
        "user_is_active": bool,
        "reviewer_enabled": bool,
        "role_used": str,
        "reason_code": str,
        "action": str,
        "subject_type": str,
        "subject_id": str,
        "evaluation_timestamp": str,
    }
    for field, expected_type in scalar_types.items():
        if type(snap[field]) is not expected_type:
            return f"authorization snapshot field {field!r} has the wrong type"
    for field in ("active_roles", "authorizing_roles", "assignment_ids"):
        if not isinstance(snap[field], list):
            return f"authorization snapshot field {field!r} must be a list"

    if snap["policy_id"] != authz.POLICY_ID:
        return "authorization snapshot policy_id is not recognized"
    if not snap["user_is_active"] or not snap["reviewer_enabled"]:
        return "an allowed event snapshot records inactive reviewer identity state"
    if snap["reason_code"] != AUTHORIZED:
        return "an allowed event snapshot does not record AUTHORIZED"

    active = snap["active_roles"]
    authorizing = snap["authorizing_roles"]
    assignments = snap["assignment_ids"]
    if (any(type(role) is not str or role not in authz.ROLES for role in active)
            or len(active) != len(set(active)) or active != sorted(active)):
        return "authorization snapshot active_roles are not canonical"
    if (any(type(role) is not str or role not in authz.ROLES for role in authorizing)
            or len(authorizing) != len(set(authorizing))):
        return "authorization snapshot authorizing_roles are not canonical"
    if (any(type(pk) is not int or pk <= 0 for pk in assignments)
            or len(assignments) != len(set(assignments))
            or assignments != sorted(assignments)):
        return "authorization snapshot assignment_ids are not canonical"
    if snap["role_used"] not in active or snap["role_used"] not in authorizing:
        return "authorization snapshot role_used is not active and authorizing"

    evaluated_at = parse_datetime(snap["evaluation_timestamp"])
    if evaluated_at is None or not timezone.is_aware(evaluated_at):
        return "authorization snapshot evaluation_timestamp is not timezone-aware ISO-8601"
    if evaluated_at > ev.created_at:
        return "authorization snapshot evaluation_timestamp is after the event timestamp"

    return None


def _verify_snapshot(ev, snap) -> list[Finding]:
    findings: list[Finding] = []

    contract_error = _snapshot_contract_error(ev, snap)
    if contract_error:
        return [_fatal(INVALID, ev, contract_error)]

    # snapshot vs ENVELOPE — both are signed, so a mismatch is not tampering (that would
    # fail the HMAC) but an internally contradictory event: a snapshot built for a
    # different decision than the envelope records. Fatal.
    if (snap.get("actor_id") != ev.actor_id
            or snap.get("role_used") != ev.role_used
            or snap.get("action") != ev.action
            or (snap.get("subject_type") or "") != ev.subject_type
            or (snap.get("subject_id") or "") != ev.subject_id):
        findings.append(_fatal(
            INVALID, ev,
            "signed authorization snapshot disagrees with the signed envelope"))

    pv = snap.get("policy_version")
    if pv not in KNOWN_POLICY_VERSIONS:
        # never silently reinterpret under the current policy
        findings.append(_warn(POLICY_REVIEW_REQUIRED, ev, f"policy version {pv!r}"))
    else:
        expected_authorizing = list(authz.authorizing_roles_for_version(
            pv, ev.action, snap["active_roles"]))
        if snap["authorizing_roles"] != expected_authorizing:
            findings.append(_fatal(
                ROLE_HISTORY_INVALID, ev,
                "signed authorizing_roles disagree with the pinned policy"))
        if ev.role_used != authz.select_role_used_for_version(
                pv, ev.action, snap["active_roles"]):
            findings.append(_fatal(
                ROLE_HISTORY_INVALID, ev,
                "signed role_used disagrees with the pinned selection rule"))
        # signed evidence: did role_used authorize the action under the pinned policy?
        policy = authz.policy_for_version(pv)
        if ev.role_used not in policy.get(ev.action, ()):
            findings.append(_fatal(
                ROLE_HISTORY_INVALID, ev,
                "signed role_used did not authorize the action under the pinned policy"))
        else:
            # live (unsigned) corroboration — a disagreement points at a mutated
            # assignment table, NOT at a forged event, so it is a WARNING that names the
            # source, not a fatal that lets an out-of-chain edit deny verification.
            created = ev.created_at
            backing = ReviewerRoleAssignment.objects.filter(
                pk__in=snap.get("assignment_ids", []), user_id=ev.actor_id,
                role=ev.role_used)
            corroborated = any(
                a.granted_at <= created < a.expires_at
                and (a.revoked_at is None or created < a.revoked_at)
                for a in backing)
            if not corroborated:
                findings.append(_warn(
                    ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE, ev,
                    "live ReviewerRoleAssignment rows do not corroborate the signed "
                    "snapshot at the event timestamp — investigate a possible "
                    "out-of-chain mutation of the (unsigned) assignment table"))

    # identity state is append-time observed only — always a review signal, never a pass
    findings.append(_warn(IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY, ev,
                          "user_is_active / reviewer_enabled are append-time observations"))
    return findings


def _verify_event_semantics(ev) -> list[Finding]:
    # single-event crypto first — if it fails, the payload is not trustworthy for semantics
    ok, problems = verify_event(ev)
    if not ok:
        legacy = [p for p in problems if key_epochs.is_legacy_problem(p)]
        others = [p for p in problems if not key_epochs.is_legacy_problem(p)]
        if legacy and not others:
            # declared lost-key epoch, no tamper evidence: auditable warnings,
            # never VALID — and the payload's semantics are NOT re-checked
            # (they cannot carry authority without an authentic signature)
            return [
                Finding(SEV_WARNING, LEGACY_SIGNATURE_UNVERIFIABLE,
                        ev.sequence_number, ev.event_id, p) for p in legacy
            ] + [Finding(SEV_WARNING, LEGACY_DECISION_REAFFIRMATION_REQUIRED,
                         ev.sequence_number, ev.event_id,
                         "equivalent authority must be reaffirmed by a new "
                         "signed decision under the active key epoch")]
        out = []
        for p in others or problems:
            code = KEY_UNAVAILABLE if "key" in p.lower() else CHAIN_INVALID
            out.append(_fatal(code, ev, p))
        return out

    findings: list[Finding] = []

    # DIP-1A-BOOTSTRAP-CORR-2: the sentinel role is valid on exactly one action. Checked for
    # EVERY event, so it cannot be borrowed to make an ordinary event look exempt.
    for problem in bootstrap_verification.sentinel_misuse_problems(ev):
        findings.append(_fatal(BOOTSTRAP_SENTINEL_MISUSED, ev, problem))

    if bootstrap_registry.is_bootstrap_event(ev):
        # Routed to its OWN verifier — stricter, not laxer. The general snapshot/role path
        # below is skipped because it asks a question that has no honest answer at genesis
        # (which role authorized this?), and the dedicated verifier proves instead every
        # fact the general path would have inferred from a role.
        for problem in bootstrap_verification.verify_bootstrap_event(ev):
            findings.append(_fatal(BOOTSTRAP_EVENT_INVALID, ev, problem))
        return findings

    payload = ev.payload if isinstance(ev.payload, dict) else {}
    snapshot_present = "authz_snapshot" in payload
    snap = payload.get("authz_snapshot")
    lifecycle_kind = payload.get("lifecycle_kind")
    snapshot_required = (
        ev.action in ROLE_LIFECYCLE_ACTIONS
        or ev.action in INTELLIGENCE_ASSERTION_ACTIONS
        or ev.action in GOVERNANCE_ACTIONS
        or _is_attestation(ev)
        or (isinstance(lifecycle_kind, str) and lifecycle_kind in LIFECYCLE_ACTION)
    )
    if snapshot_required and not snapshot_present:
        findings.append(_fatal(
            INVALID, ev, "protected service event is missing authz_snapshot"))
    elif snapshot_present and not isinstance(snap, dict):
        findings.append(_fatal(
            INVALID, ev, "authz_snapshot must be an object"))
    elif snapshot_present:
        findings += _verify_snapshot(ev, snap)

    if _is_attestation(ev):
        es = effective_attestation_state(ev)
        # CHAIN_INVALID is already covered by verify_event; here we report lifecycle/expiry
        if not es.effective and es.status not in ("EFFECTIVE", "CHAIN_INVALID"):
            findings.append(Finding(SEV_WARNING, ATTESTATION_INEFFECTIVE,
                                    ev.sequence_number, ev.event_id, es.status))
    return findings


def verify_decision_chain(*, from_seq: int = None, limit: int = None
                          ) -> ChainVerificationReport:
    """Verify the chain and classify. Read-only. In FULL mode the whole-chain structural
    pass runs (head signature, count, linkage, sequence); BOUNDED mode inspects only a
    slice and cannot establish those whole-chain properties."""
    bounded = from_seq is not None or limit is not None
    findings: list[Finding] = []

    total = DecisionEvent.objects.count()
    head_checked = False
    if not bounded:
        head_checked = True
        vr = verify_chain()          # whole-chain crypto + linkage + head reconciliation
        for p in vr.problems:
            code = KEY_UNAVAILABLE if "key" in p.lower() else CHAIN_INVALID
            findings.append(_fatal(code, None, p))
        for p in vr.legacy_notices:
            findings.append(Finding(SEV_WARNING,
                                    LEGACY_SIGNATURE_UNVERIFIABLE, None,
                                    None, p))

    if not bounded:
        # Chain-vs-database consistency for the bootstrap ceremony. Only meaningful over
        # the whole chain: an assignment with no event, or a closure anchored elsewhere,
        # cannot be seen from a slice.
        for problem in bootstrap_verification.verify_bootstrap_consistency():
            findings.append(_fatal(BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN, None, problem))

    qs = DecisionEvent.objects.order_by("sequence_number")
    if from_seq is not None:
        qs = qs.filter(sequence_number__gte=from_seq)
    events = list(qs[:limit] if limit is not None else qs)
    for ev in events:
        findings += _verify_event_semantics(ev)

    fatal = tuple(f for f in findings if f.severity == SEV_FATAL)
    warnings = tuple(f for f in findings if f.severity == SEV_WARNING)
    return ChainVerificationReport(
        ok=not fatal, mode="bounded" if bounded else "full",
        verified_events=len(events), total_events=total, head_checked=head_checked,
        fatal=fatal, warnings=warnings)


def genesis_head_summary() -> dict:
    """A convenience for the command: the head state (read-only)."""
    try:
        head = DecisionChainHead.objects.get(pk=1)
    except DecisionChainHead.DoesNotExist:
        return {"present": False}
    return {
        "present": True, "is_genesis": head.is_genesis,
        "terminal_sequence_number": head.terminal_sequence_number,
        "event_count": head.event_count, "signed": bool(head.head_signature),
        "checked_at": timezone.now().isoformat(),
    }
