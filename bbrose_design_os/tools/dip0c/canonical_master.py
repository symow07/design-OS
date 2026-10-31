"""The canonical brand-master workflow (DIP-0C3b3).

**Canonical status answers "WHICH FILE IS AUTHORITATIVE?".
Permissions answer "WHAT MAY THE SYSTEM DO WITH IT?".**

They are never the same question, and this module never touches the second one. A
file may be approved as the canonical BBROSE master while **every operational
permission remains false** — that is a tested scenario, not an oversight.

Machine code may only ever say `BRAND_MASTER_CANDIDATE`, `POSSIBLE_VARIANT`,
`POSSIBLE_CONFLICT` or `REQUIRES_HUMAN`. Declaring the canonical master, an
approved variant, a lockup, a deprecation or a rejection is a **human judgement
about the brand**, and it is unreachable from machine code.
"""
from __future__ import annotations

from . import authz
from . import canonical_scope as S
from . import config as C

PARSER = f"{C.TOOL_NAME}.canonical_master/{C.TOOL_VERSION}"

# --- the checklist -----------------------------------------------------------
# Every item must be answered explicitly. A MISSING item blocks approval — an
# unanswered question is not a pass.
#
# The checklist is split into the TWO ATTESTATIONS that dual control requires. The
# split is not cosmetic: it is what makes "one person cannot do this alone"
# enforceable, because neither half is answerable by the other's attester.
TECHNICAL_ITEMS = (
    "brand_identity_confirmed",
    "technical_readiness_appropriate",
    "editable_vector_confirmed",
    "official_proportions_confirmed",
    "symbol_wordmark_relationship_confirmed",
    "approved_lockup_type",
    "approved_color_variants",
    "version_or_date_recorded",
)
LEGAL_ITEMS = (
    "ownership_or_permitted_use_confirmed",
    "reviewed_accepted_evidence_present",
    "license_status_confirmed",
    "restrictions_and_attribution_recorded",
    "approved_product_scope",
    "approved_market_scope",
    "review_expiry_or_no_expiry_reason",
)
CHECKLIST = TECHNICAL_ITEMS + LEGAL_ITEMS

# --- the two attestations ----------------------------------------------------
ATT_TECHNICAL = "TECHNICAL_AND_BRAND"
ATT_LEGAL = "RIGHTS_AND_OWNERSHIP"
ATTESTATIONS = (ATT_TECHNICAL, ATT_LEGAL)
ATTESTATION_ITEMS = {ATT_TECHNICAL: TECHNICAL_ITEMS, ATT_LEGAL: LEGAL_ITEMS}
ATTESTATION_ACTION = {ATT_TECHNICAL: authz.ATTEST_CANONICAL_TECHNICAL,
                      ATT_LEGAL: authz.ATTEST_CANONICAL_LEGAL}
# Which attestation each item belongs to. Every item belongs to exactly one.
CHECKLIST_ATTESTATION = {item: att
                         for att, items in ATTESTATION_ITEMS.items()
                         for item in items}


class CanonicalError(RuntimeError):
    """Raised on an invalid canonical-master operation."""


def blank_checklist() -> dict:
    """Every item unanswered. `None` is NOT a pass — it blocks approval."""
    return {item: {"result": None, "confirmed_by": None, "confirmed_at": None,
                   "notes": ""} for item in CHECKLIST}


def machine_canonical(value: str | None) -> str | None:
    """Guard — the ONLY canonical values a machine may produce."""
    return C.machine_brand_master(value)


def attestation(category: str, *, actor_id: str, actor_role: str,
                attested_at: str, notes: str = "") -> dict:
    """One half of a canonical approval, signed by a named person."""
    if category not in ATTESTATIONS:
        raise CanonicalError(f"{category!r} is not an attestation category")
    return {"category": category, "actor_id": actor_id, "actor_role": actor_role,
            "attested_at": attested_at, "notes": notes,
            "covers_items": list(ATTESTATION_ITEMS[category])}


def check_attestations(attestations: list, checklist: dict,
                       *, activating_actor_id: str = None) -> list:
    """DUAL CONTROL. A canonical master needs BOTH attestations, from TWO DIFFERENT
    PEOPLE, each authorised for their half and each having actually answered it.

    Separation is by **actor identity**, not merely by role: one person wearing two
    hats is still one person, and one person is exactly what dual control exists to
    prevent. Identity is asserted, not authenticated (DIP-1) — but the event model
    already refuses to record an approval that only one human touched.
    """
    problems: list[str] = []
    by_cat: dict[str, dict] = {}

    for a in attestations or []:
        cat = a.get("category")
        if cat not in ATTESTATIONS:
            problems.append(f"unknown attestation category {cat!r}")
            continue
        if cat in by_cat:
            problems.append(f"more than one {cat} attestation was supplied")
            continue
        by_cat[cat] = a
        # authorised for THIS half — the legal half is LEGAL_REVIEWER's alone
        try:
            authz.authorize(a.get("actor_role"), ATTESTATION_ACTION[cat],
                            actor_id=a.get("actor_id", "?"))
        except authz.NotAuthorized as e:
            problems.append(f"{cat}: {e}")
        # the attester must have ANSWERED their own items — every one of them
        for item in ATTESTATION_ITEMS[cat]:
            row = checklist.get(item) or {}
            if row.get("result") is None:
                continue        # the incomplete-checklist gate reports this
            if row.get("confirmed_by") != a.get("actor_id"):
                problems.append(
                    f"{item!r} belongs to the {cat} attestation but was answered by "
                    f"{row.get('confirmed_by')!r}, not by the attester "
                    f"{a.get('actor_id')!r} — an attestation may only cover what "
                    "the attester personally confirmed")

    for cat in ATTESTATIONS:
        if cat not in by_cat:
            problems.append(
                f"DUAL CONTROL: the {cat} attestation is missing. A canonical master "
                "requires BOTH a technical/brand attestation and a rights/ownership "
                "attestation before it can be activated.")

    # THE separation rule: two DISTINCT humans, not two hats on one human
    if len(by_cat) == len(ATTESTATIONS):
        tech_id = by_cat[ATT_TECHNICAL].get("actor_id")
        legal_id = by_cat[ATT_LEGAL].get("actor_id")
        if not tech_id or not legal_id:
            problems.append("every attestation must name its actor")
        elif tech_id == legal_id:
            problems.append(
                f"DUAL CONTROL: {tech_id!r} attested BOTH halves. The technical and "
                "legal attestations must come from two DIFFERENT people — holding "
                "both roles does not make one person two reviewers.")

    # the activator may be the technical attester, but NEVER the legal one
    if activating_actor_id and ATT_LEGAL in by_cat \
            and by_cat[ATT_LEGAL].get("actor_id") == activating_actor_id:
        problems.append(
            f"DUAL CONTROL: the activating actor {activating_actor_id!r} also gave "
            "the legal attestation. The legal attestation must come from a "
            "different actor than the one activating the master.")
    return problems


def scope(brand: str, *, lockup: str = "PRIMARY", products=None, markets=None,
          effective_from: str = None, effective_to: str = None, **kw) -> dict:
    """The scope a canonical master is canonical *for*.

    C3b4 moved scope into `canonical_scope`, where an axis carries its MODE (ALL is
    not the same fact as "we don't know") and comparison runs against a per-axis
    taxonomy. This delegates, so there is exactly one scope shape in the system.
    `effective_from`/`effective_to` are the C3b3 names for the validity period.
    """
    return S.scope(brand, lockup=lockup, products=products, markets=markets,
                   valid_from=effective_from, valid_until=effective_to, **kw)


def collides(a: dict, b: dict) -> bool:
    """FAIL CLOSED: identical, overlapping AND uncertain all collide. Only a PROVEN
    disjointness lets two canonical masters coexist.

    The C3b3 boolean overlap helper is gone. It answered a question the system can
    no longer afford to ask — "do these overlap, yes or no?" — when the honest answer
    is sometimes "the taxonomy cannot say", and that answer must block.
    """
    return S.collides(a, b)


# --- approval prerequisites --------------------------------------------------
def check_canonical_approval(asset: str, *, requested_state: str, actor_role: str,
                             actor_id: str, checklist: dict,
                             ownership_state: str, evidence_records: list,
                             reason: str, contradiction: dict = None,
                             existing_canonicals: list = None,
                             requested_scope: dict = None,
                             attestations: list = None) -> tuple[bool, list]:
    """Everything that must be true before a HUMAN canonical approval is valid."""
    problems: list[str] = []

    # 0. DUAL CONTROL — two attestations, two people. Required for the canonical
    #    master and for replacing one; NOT for variants or lockups.
    if requested_state == C.CANONICAL_BRAND_MASTER:
        problems += check_attestations(attestations or [], checklist,
                                       activating_actor_id=actor_id)

    if requested_state not in C.HUMAN_ONLY_CANONICAL:
        problems.append(f"{requested_state!r} is not a human canonical decision")

    # 1. authorised actor
    action = (authz.APPROVE_CANONICAL_MASTER
              if requested_state == C.CANONICAL_BRAND_MASTER
              else authz.CLASSIFY_VARIANT)
    try:
        authz.authorize(actor_role, action, actor_id=actor_id)
    except authz.NotAuthorized as e:
        problems.append(f"unauthorized: {e}")

    # 2. the checklist — EVERY item answered, and answered TRUE
    missing = [k for k in CHECKLIST if checklist.get(k, {}).get("result") is None]
    failed = [k for k in CHECKLIST
              if checklist.get(k, {}).get("result") is False]
    if missing:
        problems.append(
            f"checklist incomplete — an UNANSWERED item is not a pass: {missing}")
    if failed:
        problems.append(f"checklist items failed: {failed}")

    # 3. confirmed ownership or explicitly permitted use
    permitted = (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED,
                 C.OWN_JOINT_OR_CONTRACTED)
    if ownership_state not in permitted:
        problems.append(
            f"ownership is {ownership_state!r}: a canonical master requires "
            f"CONFIRMED ownership or explicitly permitted use (one of "
            f"{list(permitted)})")

    # 4. reviewed + accepted evidence
    accepted = [e for e in (evidence_records or [])
                if e.get("review_status") == "REVIEWED_ACCEPTED"
                and e.get("reviewed_by")]
    if not accepted:
        problems.append("no REVIEWED_ACCEPTED evidence supports this approval")

    # 5. an explicit reason
    if not (reason or "").strip():
        problems.append("a canonical approval must record an explicit reason")

    # 6. contradictions acknowledged
    c = contradiction or {"contradiction_present": False,
                          "contradiction_acknowledged": False,
                          "acknowledgement_reason": None}
    if c["contradiction_present"] and not c["contradiction_acknowledged"]:
        problems.append(
            "a contradiction is present and has NOT been acknowledged")
    if c["contradiction_present"] and c["contradiction_acknowledged"] \
            and not (c.get("acknowledgement_reason") or "").strip():
        problems.append("acknowledging a contradiction requires a reason")

    # 7. CONFLICT — only one active canonical per brand+lockup+product+market+period
    if requested_state == C.CANONICAL_BRAND_MASTER and requested_scope:
        clashes = [x for x in (existing_canonicals or [])
                   if x.get("asset") != asset
                   and collides(requested_scope, x["scope"])]
        if clashes:
            problems.append(
                "CANONICAL CONFLICT: an active canonical master already covers this "
                f"scope — {[x['asset'] for x in clashes]}. The existing master is "
                "NOT silently replaced. A human must deprecate it, narrow one "
                "scope, reclassify one as a variant, or reject this request.")

    return (not problems), problems


def detect_conflict(requested_scope: dict, existing_canonicals: list) -> dict:
    """Machine-side conflict FLAG. It may say POSSIBLE_CONFLICT; it never resolves
    one, and it never replaces an existing master."""
    clashes = [x for x in (existing_canonicals or [])
               if collides(requested_scope, x["scope"])]
    return {
        "state": machine_canonical(C.POSSIBLE_CONFLICT if clashes else None),
        "conflicting_assets": [x["asset"] for x in clashes],
        "resolution_is_human_only": True,
        "permitted_resolutions": [
            "deprecate the former master (CANONICAL_MASTER_DEPRECATED)",
            "narrow one asset's scope (SCOPE_REDUCED)",
            "reclassify one as a variant (VARIANT_RECLASSIFIED)",
            "reject the new request (REJECTED_CANDIDATE)",
        ],
        "note": "the existing canonical master is never silently replaced",
        "parser": PARSER,
    }
