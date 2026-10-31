"""The append-only decision ledger (DIP-0C3b2).

**The immutable event files are the source of truth. `index.json` is a generated
convenience and is never authoritative.**

Storage:

    docs/design_intelligence/dip0c/decisions/
        events/<event_id>.json         one immutable file per decision
        evidence/<evidence_id>.json    one immutable file per evidence record
        assertions/<assertion_id>.json one immutable file per business assertion
        index.json                     GENERATED — also a deletion tripwire

Rules:

* an existing file is **never** edited or deleted;
* a correction is a **new superseding event**, never an overwrite;
* history is complete: nothing that was ever true disappears;
* the ledger holds only HUMAN decisions, evidence and assertions — it never
  modifies machine inference, which lives elsewhere and immutably beside it;
* the effective state is a **read model** derived from all of it, and is not
  itself the ledger.

Content hashes exclude the fields that would make regeneration unstable
(`content_hash` itself, `recorded_at`, `repository_commit`), so a file can be
re-hashed deterministically and any edit to its substance is detectable.
"""
from __future__ import annotations

import hashlib
import json

from tools.dip0.provenance import now_iso

from . import authz
from . import config as C
from . import rights_model as RM

PARSER = f"{C.TOOL_NAME}.ledger/{C.TOOL_VERSION}"
SCHEMA_VERSION = "ledger/1.0"

# The ledger is a milestone artifact — written to the injectable output root (a temp dir
# under test), never the frozen tree during a normal run.
LEDGER_ROOT = C.MILESTONE_OUTPUT_ROOT / "decisions"
EVENTS_DIR = LEDGER_ROOT / "events"
EVIDENCE_DIR = LEDGER_ROOT / "evidence"
ASSERTIONS_DIR = LEDGER_ROOT / "assertions"
INDEX_PATH = LEDGER_ROOT / "index.json"

# fields excluded from the content hash (they would make it unstable)
HASH_EXCLUDED = ("content_hash", "recorded_at", "repository_commit")

# --- event types ------------------------------------------------------------
ASSERTION_SUBMITTED = "ASSERTION_SUBMITTED"
ASSERTION_WITHDRAWN = "ASSERTION_WITHDRAWN"
EVIDENCE_SUBMITTED = "EVIDENCE_SUBMITTED"
EVIDENCE_ACCEPTED = "EVIDENCE_ACCEPTED"
EVIDENCE_REJECTED = "EVIDENCE_REJECTED"
OWNERSHIP_CONFIRMED = "OWNERSHIP_CONFIRMED"
THIRD_PARTY_CONFIRMED = "THIRD_PARTY_CONFIRMED"
LICENSE_APPROVED = "LICENSE_APPROVED"
LIMITED_USE_APPROVED = "LIMITED_USE_APPROVED"
OWNERSHIP_REVOKED = "OWNERSHIP_REVOKED"
LICENSE_REVOKED = "LICENSE_REVOKED"
DECISION_SUPERSEDED = "DECISION_SUPERSEDED"
RE_REVIEW_REQUIRED = "RE_REVIEW_REQUIRED"
# --- C3b3: canonical + permission events ------------------------------------
CANONICAL_MASTER_APPROVED = "CANONICAL_MASTER_APPROVED"
VARIANT_CLASSIFIED = "VARIANT_CLASSIFIED"
CANONICAL_MASTER_DEPRECATED = "CANONICAL_MASTER_DEPRECATED"
CANONICAL_MASTER_REPLACED = "CANONICAL_MASTER_REPLACED"
VARIANT_RECLASSIFIED = "VARIANT_RECLASSIFIED"
PERMISSION_GRANTED = "PERMISSION_GRANTED"
PERMISSION_REVOKED = "PERMISSION_REVOKED"
PERMISSION_EXPIRED = "PERMISSION_EXPIRED"
SCOPE_REDUCED = "SCOPE_REDUCED"
ASSET_QUARANTINED = "ASSET_QUARANTINED"

# --- palette decisions (C3d) — HUMAN events, in the SAME ledger --------------
PALETTE_ASSOCIATION_CONFIRMED = "PALETTE_ASSOCIATION_CONFIRMED"
PALETTE_OWNERSHIP_CONFIRMED = "PALETTE_OWNERSHIP_CONFIRMED"
PALETTE_LICENSE_CONFIRMED = "PALETTE_LICENSE_CONFIRMED"
BRAND_PALETTE_APPROVED = "BRAND_PALETTE_APPROVED"
PALETTE_VARIANT_APPROVED = "PALETTE_VARIANT_APPROVED"
PALETTE_DEPRECATED = "PALETTE_DEPRECATED"
PALETTE_SUPERSEDED = "PALETTE_SUPERSEDED"
PALETTE_QUARANTINED = "PALETTE_QUARANTINED"
PALETTE_APPROVAL_REVOKED = "PALETTE_APPROVAL_REVOKED"
PALETTE_RE_REVIEW_REQUIRED = "PALETTE_RE_REVIEW_REQUIRED"
PALETTE_EVENTS = (PALETTE_ASSOCIATION_CONFIRMED, PALETTE_OWNERSHIP_CONFIRMED,
                  PALETTE_LICENSE_CONFIRMED, BRAND_PALETTE_APPROVED,
                  PALETTE_VARIANT_APPROVED, PALETTE_DEPRECATED, PALETTE_SUPERSEDED,
                  PALETTE_QUARANTINED, PALETTE_APPROVAL_REVOKED,
                  PALETTE_RE_REVIEW_REQUIRED)
# Palette events that carry a canonical block (a scope-bearing authority decision).
PALETTE_CANONICAL_EVENTS = (BRAND_PALETTE_APPROVED, PALETTE_VARIANT_APPROVED,
                            PALETTE_DEPRECATED, PALETTE_SUPERSEDED)

EVENT_TYPES = (ASSERTION_SUBMITTED, ASSERTION_WITHDRAWN, EVIDENCE_SUBMITTED,
               EVIDENCE_ACCEPTED, EVIDENCE_REJECTED, OWNERSHIP_CONFIRMED,
               THIRD_PARTY_CONFIRMED, LICENSE_APPROVED, LIMITED_USE_APPROVED,
               OWNERSHIP_REVOKED, LICENSE_REVOKED, DECISION_SUPERSEDED,
               RE_REVIEW_REQUIRED,
               CANONICAL_MASTER_APPROVED, VARIANT_CLASSIFIED,
               CANONICAL_MASTER_DEPRECATED, CANONICAL_MASTER_REPLACED,
               VARIANT_RECLASSIFIED, PERMISSION_GRANTED, PERMISSION_REVOKED,
               PERMISSION_EXPIRED, SCOPE_REDUCED, ASSET_QUARANTINED) + PALETTE_EVENTS

DECISION_EVENTS = (OWNERSHIP_CONFIRMED, THIRD_PARTY_CONFIRMED, LICENSE_APPROVED,
                   LIMITED_USE_APPROVED)
CANONICAL_EVENTS = (CANONICAL_MASTER_APPROVED, VARIANT_CLASSIFIED,
                    CANONICAL_MASTER_DEPRECATED, CANONICAL_MASTER_REPLACED,
                    VARIANT_RECLASSIFIED) + PALETTE_CANONICAL_EVENTS
# Dual control applies to BECOMING the canonical master — by approval or by
# replacement. It does NOT apply to machine nomination, variant classification,
# deprecation, business assertions, evidence, or quarantine.
DUAL_CONTROL_EVENTS = (CANONICAL_MASTER_APPROVED, CANONICAL_MASTER_REPLACED,
                       BRAND_PALETTE_APPROVED, PALETTE_SUPERSEDED)
CORRECTIVE_EVENTS = (OWNERSHIP_REVOKED, LICENSE_REVOKED, DECISION_SUPERSEDED,
                     RE_REVIEW_REQUIRED, EVIDENCE_REJECTED, ASSERTION_WITHDRAWN,
                     CANONICAL_MASTER_DEPRECATED, CANONICAL_MASTER_REPLACED,
                     VARIANT_RECLASSIFIED, PERMISSION_REVOKED, PERMISSION_EXPIRED,
                     SCOPE_REDUCED,
                     PALETTE_DEPRECATED, PALETTE_SUPERSEDED,
                     PALETTE_APPROVAL_REVOKED, PALETTE_RE_REVIEW_REQUIRED)

EVENT_ACTION = {
    ASSERTION_SUBMITTED: authz.SUBMIT_ASSERTION,
    ASSERTION_WITHDRAWN: authz.WITHDRAW_ASSERTION,
    EVIDENCE_SUBMITTED: authz.SUBMIT_EVIDENCE,
    EVIDENCE_ACCEPTED: authz.REVIEW_EVIDENCE,
    EVIDENCE_REJECTED: authz.REVIEW_EVIDENCE,
    OWNERSHIP_CONFIRMED: authz.CONFIRM_OWNERSHIP,
    THIRD_PARTY_CONFIRMED: authz.CONFIRM_THIRD_PARTY,
    LICENSE_APPROVED: authz.APPROVE_LICENSE,
    LIMITED_USE_APPROVED: authz.APPROVE_LIMITED_USE,
    OWNERSHIP_REVOKED: authz.REVOKE_DECISION,
    LICENSE_REVOKED: authz.REVOKE_DECISION,
    DECISION_SUPERSEDED: authz.REVOKE_DECISION,
    RE_REVIEW_REQUIRED: authz.REQUIRE_RE_REVIEW,
    # --- C3b3 ---
    CANONICAL_MASTER_APPROVED: authz.APPROVE_CANONICAL_MASTER,
    VARIANT_CLASSIFIED: authz.CLASSIFY_VARIANT,
    CANONICAL_MASTER_DEPRECATED: authz.DEPRECATE_CANONICAL,
    # a replacement ACTIVATES a new master, so it takes the activation authority
    # (BRAND_ADMIN) — not merely the authority to retire the old one
    CANONICAL_MASTER_REPLACED: authz.APPROVE_CANONICAL_MASTER,
    VARIANT_RECLASSIFIED: authz.CLASSIFY_VARIANT,
    PERMISSION_GRANTED: authz.GRANT_PERMISSION,
    PERMISSION_REVOKED: authz.REVOKE_PERMISSION,
    PERMISSION_EXPIRED: authz.EXECUTE_EXPIRY,
    SCOPE_REDUCED: authz.REVOKE_PERMISSION,
    ASSET_QUARANTINED: authz.QUARANTINE_ASSET,
    # --- C3d: palette decisions ---
    PALETTE_ASSOCIATION_CONFIRMED: authz.CONFIRM_PALETTE_ASSOCIATION,
    PALETTE_OWNERSHIP_CONFIRMED: authz.CONFIRM_OWNERSHIP,
    PALETTE_LICENSE_CONFIRMED: authz.APPROVE_LICENSE,
    BRAND_PALETTE_APPROVED: authz.APPROVE_BRAND_PALETTE,
    PALETTE_VARIANT_APPROVED: authz.CLASSIFY_VARIANT,
    PALETTE_DEPRECATED: authz.DEPRECATE_PALETTE,
    # a palette supersession ACTIVATES a new palette -> activation authority
    PALETTE_SUPERSEDED: authz.APPROVE_BRAND_PALETTE,
    PALETTE_QUARANTINED: authz.QUARANTINE_ASSET,
    PALETTE_APPROVAL_REVOKED: authz.REVOKE_DECISION,
    PALETTE_RE_REVIEW_REQUIRED: authz.REQUIRE_RE_REVIEW,
}


def permission_block(flag: str, *, previous_value, requested_value,
                     purpose: str = None, approved_brands=None,
                     approved_products=None, approved_markets=None,
                     approved_media=None,
                     attribution_required=None, validity_start: str = None,
                     review_expiry: str = None, restrictions=None,
                     ownership_decision_ref: str = None,
                     license_decision_ref: str = None) -> dict:
    """ONE permission, named explicitly. There are no implicit bundles: a single
    event may carry several permissions only by naming and validating each."""
    return {
        "flag": flag,
        "previous_value": previous_value,
        "requested_value": requested_value,
        "purpose": purpose,
        "approved_brands": sorted(approved_brands or []),
        "approved_products": sorted(approved_products or []),
        "approved_markets": sorted(approved_markets or []),
        # MEDIA is independent of products: a grant for DIGITAL is not a grant for
        # the press. An empty list means unrestricted on this axis.
        "approved_media": sorted(approved_media or []),
        "attribution_required": attribution_required,
        "validity_start": validity_start,
        "review_expiry": review_expiry,
        "restrictions": list(restrictions or []),
        "ownership_decision_ref": ownership_decision_ref,
        "license_decision_ref": license_decision_ref,
    }


# --- authority domains (C3d) ---------------------------------------------------
# A brand palette and a logo master are DIFFERENT KINDS OF AUTHORITY. They may cover
# the same brand, product, market and period without contradicting each other — the
# palette says which colours are the brand's, the master says which file is. Uniqueness
# is therefore evaluated WITHIN a domain, never across all of them.
DOMAIN_BRAND_MASTER = "BRAND_MASTER"
DOMAIN_BRAND_PALETTE = "BRAND_PALETTE"
AUTHORITY_DOMAINS = (DOMAIN_BRAND_MASTER, DOMAIN_BRAND_PALETTE)


def canonical_block(state: str, *, scope: dict, checklist: dict,
                    version_or_date: str = None, attestations: list = None,
                    authority_domain: str = DOMAIN_BRAND_MASTER,
                    palette: dict = None) -> dict:
    """The canonical decision and the checklist that justified it — persisted with
    an explicit result for EVERY item, and with the TWO attestations that authorised
    it. The approval can never be read apart from who signed for which half."""
    if authority_domain not in AUTHORITY_DOMAINS:
        raise LedgerError(f"{authority_domain!r} is not an authority domain")
    return {
        "authority_domain": authority_domain,
        "palette": palette,          # the C3c technical audit, carried unchanged
        "canonical_state": state,
        "scope": scope,
        "checklist": checklist,
        "attestations": list(attestations or []),
        "version_or_date": version_or_date,
        "grants_permissions": False,
        "note": "canonical status says WHICH FILE IS AUTHORITATIVE. It says nothing "
                "about what the system may DO with it — every permission remains "
                "false until separately granted.",
    }

# --- evidence ---------------------------------------------------------------
EVIDENCE_TYPES = (
    "SOURCE_FILE", "DESIGNER_DELIVERY", "CONTRACT", "INVOICE", "PURCHASE_RECORD",
    "TRADEMARK_REGISTRATION", "INTERNAL_CREATION_RECORD", "EMAIL_OR_APPROVAL",
    "VENDOR_OR_SOURCE_INFORMATION", "LICENSE_DOCUMENT", "USAGE_HISTORY",
    "OFFICIAL_WEBSITE_OR_PACKAGING_USAGE", "BUSINESS_OWNER_DECLARATION",
    "LEGAL_REVIEW", "OTHER",
)
EV_SUBMITTED = "SUBMITTED"
EV_ACCEPTED = "REVIEWED_ACCEPTED"
EV_REJECTED = "REVIEWED_REJECTED"
EV_EXPIRED = "EXPIRED"
EV_SUPERSEDED = "SUPERSEDED"
EV_QUARANTINED = "QUARANTINED"
EVIDENCE_STATUSES = (EV_SUBMITTED, EV_ACCEPTED, EV_REJECTED, EV_EXPIRED,
                     EV_SUPERSEDED, EV_QUARANTINED)


class LedgerError(RuntimeError):
    """Raised on an invalid or unauthorized ledger operation."""


# --- hashing / ids ----------------------------------------------------------
def canonical(record: dict) -> str:
    body = {k: v for k, v in record.items() if k not in HASH_EXCLUDED}
    return json.dumps(body, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def content_hash(record: dict) -> str:
    return hashlib.sha256(canonical(record).encode("utf-8")).hexdigest()


def make_id(prefix: str, record: dict) -> str:
    """Deterministic and collision-safe: derived from the record's substance."""
    return f"{prefix}-{content_hash(record)[:20]}"


# --- record builders ---------------------------------------------------------
def assertion(asset: str, *, asserted_state: str, asserted_by: str,
              actor_role: str, asserted_at: str, notes: str = "",
              supporting_refs=None, supersedes_assertion_id=None) -> dict:
    """A business assertion. It is a BELIEF: it confirms nothing, approves nothing,
    grants nothing, and selects no canonical master. Withdrawal never deletes it."""
    authz.authorize(actor_role, authz.SUBMIT_ASSERTION, actor_id=asserted_by)
    rec = {
        "schema_version": SCHEMA_VERSION,
        "assertion_id": None,
        "asset": asset,
        "asserted_state": asserted_state,
        "asserted_by": asserted_by,
        "actor_role": actor_role,
        "asserted_at": asserted_at,
        "assertion_notes": notes,
        "supporting_refs": list(supporting_refs or []),
        "withdrawn_by": None,
        "withdrawn_at": None,
        "withdrawal_reason": None,
        "supersedes_assertion_id": supersedes_assertion_id,
        "is_confirmation": False,
        "grants_permissions": False,
        "recorded_at": now_iso(),
        "content_hash": None,
    }
    rec["assertion_id"] = make_id("asr", rec)
    rec["content_hash"] = content_hash(rec)
    return rec


def evidence(asset: str, *, evidence_type: str, title: str, submitted_by: str,
             actor_role: str, submitted_at: str, description: str = "",
             reference: str = "", file_hash: str = None,
             validity_start: str = None, validity_end: str = None,
             confidence: float = 0.0, ownership_relevance: str = "UNKNOWN",
             license_relevance: str = "UNKNOWN", restrictions_observed=None,
             supersedes_evidence_id: str = None) -> dict:
    """Evidence is SUBMITTED, never self-approving. Its status changes only through
    a ledger event, and its status NEVER automatically changes an ownership or
    licence state."""
    authz.authorize(actor_role, authz.SUBMIT_EVIDENCE, actor_id=submitted_by)
    if evidence_type not in EVIDENCE_TYPES:
        raise LedgerError(f"unknown evidence type: {evidence_type!r}")
    rec = {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": None,
        "evidence_type": evidence_type,
        "asset": asset,
        "title": title,
        "description": description,
        "submitted_by": submitted_by,
        "actor_role": actor_role,
        "submitted_at": submitted_at,
        "reference": reference,          # a path or URI — sensitive files by ref only
        "file_hash": file_hash,
        "validity_start": validity_start,
        "validity_end": validity_end,
        "confidence": round(float(confidence), 3),
        "reviewed_by": None,
        "reviewed_at": None,
        "review_status": EV_SUBMITTED,
        "review_notes": None,
        "ownership_relevance": ownership_relevance,
        "license_relevance": license_relevance,
        "restrictions_observed": list(restrictions_observed or []),
        "supersedes_evidence_id": supersedes_evidence_id,
        "recorded_at": now_iso(),
        "content_hash": None,
    }
    rec["evidence_id"] = make_id("evd", rec)
    rec["content_hash"] = content_hash(rec)
    return rec


def event(asset: str, *, event_type: str, actor_id: str, actor_role: str,
          occurred_at: str, previous_state=None, requested_state=None,
          decision_reason: str = "", evidence_refs=None, assertion_refs=None,
          supersedes_event_id: str = None, review_expiry: str = None,
          repository_commit: str = None, notes: str = "",
          contradiction=None, permission=None, canonical=None) -> dict:
    """A ledger event. Authorised at construction; validated again on append."""
    if event_type not in EVENT_TYPES:
        raise LedgerError(f"unknown event type: {event_type!r}")
    authz.authorize(actor_role, EVENT_ACTION[event_type], actor_id=actor_id)

    # a corrective event MUST say what it changes — history stays complete
    _no_ref_needed = (ASSERTION_WITHDRAWN, EVIDENCE_REJECTED, RE_REVIEW_REQUIRED)
    if event_type in CORRECTIVE_EVENTS and event_type not in _no_ref_needed \
            and not supersedes_event_id:
        raise LedgerError(
            f"{event_type} is a corrective event and MUST reference the event it "
            "supersedes or revokes — history stays complete")

    # a permission grant must NAME the permission: no implicit bundles
    if event_type == PERMISSION_GRANTED and not (permission or {}).get("flag"):
        raise LedgerError(
            "a PERMISSION_GRANTED event must name exactly one permission. There "
            "are no implicit bundles, and no permission becomes true by defaulting "
            "or inference.")
    if event_type in CANONICAL_EVENTS and not (canonical or {}).get(
            "canonical_state"):
        raise LedgerError(f"{event_type} must carry a canonical block")

    # DUAL CONTROL, enforced at the point of RECORDING. Approving or replacing a
    # canonical master takes two attestations from two DIFFERENT people. Checking
    # this only in check_canonical_approval() would leave a path that writes the
    # event without ever calling it.
    if event_type in DUAL_CONTROL_EVENTS:
        atts = (canonical or {}).get("attestations") or []
        cats = {a.get("category") for a in atts}
        ids = {a.get("actor_id") for a in atts}
        if len(cats) < 2 or None in cats:
            raise LedgerError(
                f"{event_type} is under DUAL CONTROL and must carry BOTH a "
                "technical/brand attestation and a rights/ownership attestation")
        if len(ids) < 2:
            raise LedgerError(
                f"{event_type} is under DUAL CONTROL: its attestations name only "
                f"{ids} — the two attestations must come from two DIFFERENT people. "
                "Holding both roles does not make one person two reviewers.")
        if actor_id in {a.get("actor_id") for a in atts
                        if a.get("category") == "RIGHTS_AND_OWNERSHIP"}:
            raise LedgerError(
                f"{event_type}: the activating actor {actor_id!r} also gave the "
                "legal attestation — it must come from a different actor")
    rec = {
        "schema_version": SCHEMA_VERSION,
        "event_id": None,
        "event_type": event_type,
        "asset": asset,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "occurred_at": occurred_at,
        "previous_state": previous_state,
        "requested_state": requested_state,
        "decision_reason": decision_reason,
        "evidence_refs": list(evidence_refs or []),
        "assertion_refs": list(assertion_refs or []),
        "supersedes_event_id": supersedes_event_id,
        "review_expiry": review_expiry,
        "contradiction": contradiction or contradiction_block(),
        "permission": permission,       # exactly ONE named permission, or None
        "canonical": canonical,         # the canonical decision + its checklist
        "notes": notes,
        "recorded_at": now_iso(),
        "repository_commit": repository_commit,
        "content_hash": None,
    }
    rec["event_id"] = make_id("evt", rec)
    rec["content_hash"] = content_hash(rec)
    return rec


def contradiction_block(present=False, refs=None, acknowledged=False,
                        reason=None) -> dict:
    """A reviewer may confirm *despite* contradicting evidence — but only by saying
    so explicitly and on the record. LOGO6.ai is the case this exists for: the
    business believes it owns the logo, and the artwork's own live text reads
    'global logistics services'."""
    return {
        "contradiction_present": present,
        "contradiction_refs": list(refs or []),
        "contradiction_acknowledged": acknowledged,
        "acknowledgement_reason": reason,
    }


# --- confirmation prerequisites ---------------------------------------------
def check_confirmation(asset: str, *, requested_state: str, actor_role: str,
                       actor_id: str, current_state: str, axis: str,
                       evidence_records: list, reason: str,
                       contradiction: dict = None) -> tuple[bool, list[str]]:
    """Everything that must be true before a human confirmation is valid."""
    problems = []

    # 1. an AUTHORIZED reviewer
    try:
        authz.authorize(actor_role, authz.action_for_state(requested_state),
                        actor_id=actor_id)
    except authz.NotAuthorized as e:
        problems.append(f"unauthorized: {e}")

    # 2. at least one REVIEWED AND ACCEPTED evidence record
    accepted = [e for e in evidence_records
                if e.get("review_status") == EV_ACCEPTED
                and e.get("reviewed_by")]
    if not accepted:
        problems.append(
            "no REVIEWED_ACCEPTED evidence: a confirmation needs evidence a "
            "reviewer has actually accepted. A business assertion is a BELIEF, "
            "not evidence, and can never on its own support a confirmation.")

    # 3. an explicit reason
    if not (reason or "").strip():
        problems.append("a confirmation must record an explicit reason")

    # 4. evidence references
    if accepted and not any(e.get("evidence_id") for e in accepted):
        problems.append("confirmation must reference the evidence it relies on")

    # 5. a LEGAL transition from the current state (the matrix is authoritative)
    try:
        RM.validate_transition(axis, current_state, requested_state,
                               RM.ACTOR_HUMAN)
    except (RM.IllegalTransition, RM.MachineMayNotIncrease,
            C.HumanOnlyStateViolation) as e:
        problems.append(f"illegal transition: {e}")

    # 6. no unresolved blocking contradiction
    c = contradiction or contradiction_block()
    if c["contradiction_present"] and not c["contradiction_acknowledged"]:
        problems.append(
            "a contradiction is present and has NOT been acknowledged. The "
            "reviewer must explicitly acknowledge it, with a reason, before "
            "confirming.")
    if c["contradiction_present"] and c["contradiction_acknowledged"] \
            and not (c["acknowledgement_reason"] or "").strip():
        problems.append("acknowledging a contradiction requires a reason")

    return (not problems), problems
