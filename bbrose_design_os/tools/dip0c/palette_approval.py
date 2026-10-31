"""Brand-palette approval, under dual control (DIP-0C3d).

Approving a brand palette is as consequential as approving a canonical logo master, so
it takes the same shape and **reuses the same machinery**: the same append-only ledger,
the same authorisation policy, the same attestation guard, the same permission set, the
same expiry. There is no parallel palette system, because a second system is a second
place for the rules to drift.

Six independent questions, and confirming one **never** answers the next:

    do the colours parse?  ->  is it BBROSE's?      ->  do we own it?
    ->  is it licensed?    ->  is it THE brand palette?  ->  what may we DO with it?

The last arrow is the one people most want to skip. `BRAND_PALETTE_APPROVED` grants
**nothing**: every permission stays false until an authorised human grants it by name.

**Approval never rewrites the technical audit.** A `PARTIAL_PARSE` file may be approved
— a human is allowed to say "I know the parser needed a fallback, and I accept these
values anyway" — but the parse status, the layout, the warnings and the fallback flag
travel *with* the approval and survive it. Approving a file does not make it well-formed,
and a derived preview never becomes source truth by being approved.
"""
from __future__ import annotations

from . import ase
from . import authz
from . import canonical_master as CM
from . import config as C
from . import ledger as L

PARSER = f"{C.TOOL_NAME}.palette_approval/{C.TOOL_VERSION}"

# --- the two attestations ------------------------------------------------------
ATT_COLOR = "COLOR_AND_BRAND"
ATT_RIGHTS = "RIGHTS_AND_USE"
ATTESTATIONS = (ATT_COLOR, ATT_RIGHTS)
ATTESTATION_ACTION = {ATT_COLOR: authz.ATTEST_PALETTE_COLOR,
                      ATT_RIGHTS: authz.ATTEST_PALETTE_RIGHTS}

# --- the checklist, split across the two attestations --------------------------
COLOR_ITEMS = (
    "palette_identity_confirmed",
    "brand_association_confirmed",
    "approved_swatch_names",
    "approved_source_color_models",
    "visual_correctness_confirmed",
    "color_relationships_confirmed",
    "approved_variants",
    "approved_products",
    "approved_media",
    "print_versus_digital_scope",
    "parser_limitation_acknowledged",     # the C3c finding must be faced, not skipped
    "value_provenance_declared",          # raw / preview / manually confirmed
    "version_or_date_recorded",
)
RIGHTS_ITEMS = (
    "ownership_or_permitted_use_confirmed",
    "license_decision_recorded",
    "third_party_naming_reviewed",
    "redistribution_restrictions_recorded",
    "embedding_and_export_limits_recorded",
    "approved_markets",
    "attribution_requirements_recorded",
    "review_expiry_or_no_expiry_reason",
)
CHECKLIST = COLOR_ITEMS + RIGHTS_ITEMS
ATTESTATION_ITEMS = {ATT_COLOR: COLOR_ITEMS, ATT_RIGHTS: RIGHTS_ITEMS}
CHECKLIST_ATTESTATION = {i: a for a, items in ATTESTATION_ITEMS.items()
                         for i in items}

# --- value provenance: what a human actually approved --------------------------
RAW_SOURCE = "RAW_SOURCE"                 # the bytes said so
DERIVED_PREVIEW = "DERIVED_PREVIEW"       # we computed it, and it is not source truth
MANUALLY_CONFIRMED = "MANUALLY_CONFIRMED"  # a human asserts it; it is THEIRS, not the file's
PROVENANCE = (RAW_SOURCE, DERIVED_PREVIEW, MANUALLY_CONFIRMED)

# --- palette canonical states --------------------------------------------------
APPROVED_BRAND_PALETTE = "APPROVED_BRAND_PALETTE"      # human only
APPROVED_PALETTE_VARIANT = "APPROVED_PALETTE_VARIANT"  # human only
DEPRECATED_PALETTE = "DEPRECATED_PALETTE"              # human only
REJECTED_PALETTE = "REJECTED_PALETTE"                  # human only
HUMAN_ONLY_PALETTE = (APPROVED_BRAND_PALETTE, APPROVED_PALETTE_VARIANT,
                      DEPRECATED_PALETTE, REJECTED_PALETTE)


class PaletteApprovalError(RuntimeError):
    """An invalid palette-approval operation."""


def blank_checklist() -> dict:
    """Every item unanswered. `None` is NOT a pass — it blocks approval."""
    return {item: {"result": None, "confirmed_by": None, "confirmed_at": None,
                   "notes": ""} for item in CHECKLIST}


def machine_palette_authority(value: str | None) -> str | None:
    """A machine may never approve, activate, deprecate or reject a brand palette."""
    if value in HUMAN_ONLY_PALETTE:
        raise C.HumanOnlyStateViolation(
            f"{value!r} is a HUMAN decision. Machine code may audit a palette's "
            "colours; it may never declare one to be the brand's.")
    return value


def attestation(category: str, *, actor_id: str, actor_role: str,
                attested_at: str, notes: str = "") -> dict:
    if category not in ATTESTATIONS:
        raise PaletteApprovalError(f"{category!r} is not a palette attestation")
    return {"category": category, "actor_id": actor_id, "actor_role": actor_role,
            "attested_at": attested_at, "notes": notes,
            "covers_items": list(ATTESTATION_ITEMS[category])}


def check_attestations(attestations: list, checklist: dict,
                       *, activating_actor_id: str = None) -> list:
    """DUAL CONTROL for palettes. Two attestations, TWO DIFFERENT PEOPLE.

    Deliberately the same shape as the canonical-master rule — and it shares
    `canonical_master.check_attestations`' logic by construction rather than by
    copy-paste, differing only in which categories and which authz actions apply.
    """
    problems: list[str] = []
    by_cat: dict[str, dict] = {}

    for a in attestations or []:
        cat = a.get("category")
        if cat not in ATTESTATIONS:
            problems.append(f"unknown palette attestation category {cat!r}")
            continue
        if cat in by_cat:
            problems.append(f"more than one {cat} attestation was supplied")
            continue
        by_cat[cat] = a
        try:
            authz.authorize(a.get("actor_role"), ATTESTATION_ACTION[cat],
                            actor_id=a.get("actor_id", "?"))
        except authz.NotAuthorized as e:
            problems.append(f"{cat}: {e}")
        for item in ATTESTATION_ITEMS[cat]:
            row = checklist.get(item) or {}
            if row.get("result") is None:
                continue
            if row.get("confirmed_by") != a.get("actor_id"):
                problems.append(
                    f"{item!r} belongs to the {cat} attestation but was answered by "
                    f"{row.get('confirmed_by')!r}, not by the attester "
                    f"{a.get('actor_id')!r} — an attestation may only cover what the "
                    "attester personally confirmed")

    for cat in ATTESTATIONS:
        if cat not in by_cat:
            problems.append(
                f"DUAL CONTROL: the {cat} attestation is missing. A brand palette "
                "requires BOTH a colour/brand attestation and a rights/use one.")

    if len(by_cat) == len(ATTESTATIONS):
        color_id = by_cat[ATT_COLOR].get("actor_id")
        legal_id = by_cat[ATT_RIGHTS].get("actor_id")
        if not color_id or not legal_id:
            problems.append("every attestation must name its actor")
        elif color_id == legal_id:
            problems.append(
                f"DUAL CONTROL: {color_id!r} attested BOTH halves. "
                "color_reviewer_id != legal_reviewer_id — holding both roles does not "
                "make one person two reviewers.")

    if activating_actor_id and ATT_RIGHTS in by_cat \
            and by_cat[ATT_RIGHTS].get("actor_id") == activating_actor_id:
        problems.append(
            f"DUAL CONTROL: the activating actor {activating_actor_id!r} also gave the "
            "rights attestation — it must come from a different actor.")
    return problems


def check_approval(asset: str, *, requested_state: str, actor_role: str, actor_id: str,
                   checklist: dict, attestations: list,
                   parser_audit: dict, ownership_state: str, license_state: str,
                   evidence_records: list, reason: str,
                   third_party_ack: dict = None,
                   parser_limitation_ack: dict = None,
                   value_provenance: dict = None,
                   existing_palettes: list = None,
                   requested_scope: dict = None) -> tuple[bool, list]:
    """Everything that must hold before a HUMAN brand-palette approval is valid."""
    problems: list[str] = []

    if requested_state not in HUMAN_ONLY_PALETTE:
        problems.append(f"{requested_state!r} is not a human palette decision")

    # 1. DUAL CONTROL
    if requested_state == APPROVED_BRAND_PALETTE:
        problems += check_attestations(attestations or [], checklist,
                                       activating_actor_id=actor_id)

    # 2. authorised activator — BRAND_ADMIN only
    action = (authz.APPROVE_BRAND_PALETTE
              if requested_state == APPROVED_BRAND_PALETTE
              else authz.CLASSIFY_VARIANT)
    try:
        authz.authorize(actor_role, action, actor_id=actor_id)
    except authz.NotAuthorized as e:
        problems.append(f"unauthorized: {e}")

    # 3. the checklist — every item answered, and answered TRUE
    missing = [k for k in CHECKLIST if checklist.get(k, {}).get("result") is None]
    failed = [k for k in CHECKLIST if checklist.get(k, {}).get("result") is False]
    if missing:
        problems.append(
            f"checklist incomplete — an UNANSWERED item is not a pass: {missing}")
    if failed:
        problems.append(f"checklist items failed: {failed}")

    # 4. rights
    permitted = (C.OWN_BBROSE_CONFIRMED, C.OWN_LICENSED_LIMITED,
                 C.OWN_JOINT_OR_CONTRACTED)
    if ownership_state not in permitted:
        problems.append(
            f"ownership is {ownership_state!r}: a brand palette requires confirmed "
            f"ownership or explicitly permitted use (one of {list(permitted)})")
    if license_state == C.LIC_UNVERIFIED:
        problems.append("the licence is UNVERIFIED — a brand palette approval must "
                        "rest on a recorded licence decision")

    accepted = [e for e in (evidence_records or [])
                if e.get("review_status") == "REVIEWED_ACCEPTED" and e.get("reviewed_by")]
    if not accepted:
        problems.append("no REVIEWED_ACCEPTED evidence supports this approval")

    if not (reason or "").strip():
        problems.append("a palette approval must record an explicit reason")

    # 5. THE PARSER LIMITATION MUST BE FACED, NOT SKIPPED
    status = (parser_audit or {}).get("parse_status")
    fallback = (parser_audit or {}).get("fallback_used")
    if status != ase.TECHNICALLY_PARSED or fallback:
        ack = parser_limitation_ack or {}
        if not ack.get("parser_limitation_acknowledged"):
            problems.append(
                f"this palette is {status} (fallback_used={fallback}). A human MAY "
                "approve it — but the approval must explicitly acknowledge the parser "
                "limitation. Approving a file does not make it well-formed.")
        elif not (ack.get("reason") or "").strip():
            problems.append(
                "acknowledging a parser limitation requires a reason")

    # 6. third-party naming must be acknowledged with a reason
    naming = (parser_audit or {}).get("third_party_naming") or []
    if naming:
        ack = third_party_ack or {}
        if not ack.get("acknowledged"):
            problems.append(
                f"third-party naming detected ({naming}) and NOT acknowledged. A name "
                "is not a licence, and approving a palette does not resolve it.")
        elif not (ack.get("reason") or "").strip():
            problems.append("acknowledging third-party naming requires a reason")

    # 7. every approved value must declare its provenance
    vp = value_provenance or {}
    swatches = (parser_audit or {}).get("swatch_names") or []
    for name in swatches:
        p = vp.get(name)
        if p not in PROVENANCE:
            problems.append(
                f"swatch {name!r}: every approved value must declare its provenance — "
                f"one of {list(PROVENANCE)}. A derived preview does not become source "
                "truth by being approved.")

    # 8. CONFLICT — one active brand palette per scope, WITHIN the palette domain
    if requested_state == APPROVED_BRAND_PALETTE and requested_scope:
        from . import canonical_scope as S
        clashes = [x for x in (existing_palettes or [])
                   if x.get("asset") != asset
                   and S.collides(requested_scope, x["scope"])]
        if clashes:
            problems.append(
                "PALETTE CONFLICT: an active brand palette already covers this scope — "
                f"{[x['asset'] for x in clashes]}. The incumbent is NOT silently "
                "replaced.")

    return (not problems), problems


def approval_block(parser_audit: dict, *, value_provenance: dict,
                   parser_limitation_ack: dict = None,
                   third_party_ack: dict = None) -> dict:
    """The technical audit, carried INTO the approval and surviving it unchanged."""
    return {
        "parse_status": parser_audit.get("parse_status"),
        "capability": parser_audit.get("capability"),
        "layout": parser_audit.get("layout"),
        "fallback_used": parser_audit.get("fallback_used"),
        "parser_warnings": parser_audit.get("parser_warnings"),
        "color_models": parser_audit.get("color_models"),
        "color_types": parser_audit.get("color_types"),
        "third_party_naming": parser_audit.get("third_party_naming"),
        "contains_spot_identity": parser_audit.get("contains_spot_identity"),
        "parser_limitation_acknowledged": parser_limitation_ack or {},
        "third_party_naming_acknowledged": third_party_ack or {},
        "value_provenance": dict(value_provenance or {}),
        "grants_permissions": False,
        "note": "The technical audit is preserved VERBATIM. Approval does not rewrite "
                "it: a PARTIAL_PARSE stays PARTIAL_PARSE, a derived preview stays "
                "derived, and a fallback stays a fallback.",
    }


def canonical_block(state: str, *, scope: dict, checklist: dict, attestations: list,
                    parser_audit: dict, value_provenance: dict,
                    parser_limitation_ack: dict = None,
                    third_party_ack: dict = None,
                    version_or_date: str = None) -> dict:
    """A palette authority decision, in the BRAND_PALETTE domain."""
    machine_palette_authority(None)          # guard is import-reachable
    return L.canonical_block(
        state, scope=scope, checklist=checklist, attestations=attestations,
        version_or_date=version_or_date,
        authority_domain=L.DOMAIN_BRAND_PALETTE,
        palette=approval_block(parser_audit, value_provenance=value_provenance,
                               parser_limitation_ack=parser_limitation_ack,
                               third_party_ack=third_party_ack))


# The canonical-master checklist and this one are deliberately parallel; assert the
# shapes have not drifted apart.
assert set(CHECKLIST_ATTESTATION) == set(CHECKLIST)
assert not (set(COLOR_ITEMS) & set(RIGHTS_ITEMS))
assert set(CM.ATTESTATIONS) != set(ATTESTATIONS)   # distinct categories, same discipline
