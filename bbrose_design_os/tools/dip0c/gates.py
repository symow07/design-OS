"""The retrieval gate and the (stricter) automatic-use gate (DIP-0C5).

**They are two permissions, and they never collapse into one.**

Retrieval means *a human may find this and look at it*. Automatic use means *the system
may reach for it without anyone deciding*. The second is strictly harder, and it requires
the first **plus** an explicit separate grant — a retrievable asset may still require
manual selection, and usually should.

Both default to `false`. Both fail closed. Both are pure: they read state and decide;
they write nothing and grant nothing.
"""
from __future__ import annotations

from . import config as C
from . import review_domains as RD

PARSER = f"{C.TOOL_NAME}.gates/{C.TOOL_VERSION}"
SCHEMA_VERSION = "gate/1.0"

RETRIEVAL = "retrieval_allowed"
AUTOMATIC_USE = "automatic_use_allowed"

# The conditions each domain must satisfy before RETRIEVAL is even askable.
RETRIEVAL_CONDITIONS = {
    RD.HISTORICAL_DESIGN_UNIT: (
        "human_approved_for_reference_memory",
        "posture_is_reference_only",
        "no_template_reuse",
        "source_provenance_recorded",
        "design_unit_role_reviewed",
        "restricted_geometry_excluded",
    ),
    RD.REUSABLE_ASSET: (
        "asset_type_human_confirmed",
        "technical_readiness_accepted",
        "ownership_and_licence_reviewed",
        "retrieval_explicitly_granted",
        "scope_recorded_brand_product_market_media",
        "restrictions_and_expiry_recorded",
    ),
    RD.FONT_FACE: (
        "technical_family_confirmed",
        "source_provenance_confirmed",
        "licence_decision_reviewed",
        "retrieval_explicitly_granted",
    ),
    RD.BRAND_ASSET: (
        "brand_association_confirmed",
        "ownership_or_limited_use_confirmed",
        "dual_control_where_required",
        "retrieval_granted_separately_from_approval",
    ),
    RD.COLOR_PALETTE: (
        "brand_association_confirmed",
        "ownership_or_limited_use_confirmed",
        "dual_control_where_required",
        "retrieval_granted_separately_from_approval",
    ),
    RD.CANONICAL_MASTER_CANDIDATE: (
        "brand_association_confirmed",
        "ownership_or_limited_use_confirmed",
        "dual_control_where_required",
        "retrieval_granted_separately_from_approval",
    ),
}

# Automatic use requires ALL of these, ON TOP OF a satisfied retrieval gate.
AUTOMATIC_USE_CONDITIONS = (
    "retrieval_already_allowed",
    "automatic_use_explicitly_granted",
    "technical_readiness_suitable",
    "valid_rights_decision",
    "review_period_active",
    "scope_matches_brand_product_market_media",
    "no_unresolved_contradiction",
    "not_quarantined",
    "no_expired_evidence",
    "no_canonical_conflict",
)

# Font install / embed / production are handled SEPARATELY, and are not implied by
# retrieval or by automatic use.
FONT_SEPARATE_PERMISSIONS = ("installation", "embedding_allowed",
                             "production_use_allowed")


def retrieval_gate(domain: str, state: dict) -> dict:
    """May this record be retrieved? Default NO."""
    conditions = RETRIEVAL_CONDITIONS.get(domain)
    if conditions is None:
        return {
            "permission": RETRIEVAL,
            "allowed": False,
            "domain": domain,
            "unmet": ["domain has no retrieval path"],
            "reason": f"{domain} is not a retrievable domain — evidence, quarantine "
                      "batches and provenance groups are reviewed, never retrieved",
            "parser": PARSER,
        }
    unmet = [c for c in conditions if not state.get(c)]
    return {
        "permission": RETRIEVAL,
        "allowed": not unmet,
        "domain": domain,
        "required_conditions": list(conditions),
        "unmet": unmet,
        "reason": ("every condition is satisfied" if not unmet else
                   f"{len(unmet)} condition(s) unmet — retrieval stays FALSE"),
        "default": False,
        "parser": PARSER,
    }


def automatic_use_gate(domain: str, state: dict) -> dict:
    """May the system reach for this WITHOUT a human choosing it? Strictly harder."""
    r = retrieval_gate(domain, state)
    unmet = []
    if not r["allowed"]:
        unmet.append("retrieval_already_allowed")
    unmet += [c for c in AUTOMATIC_USE_CONDITIONS
              if c != "retrieval_already_allowed" and not state.get(c)]

    return {
        "permission": AUTOMATIC_USE,
        "allowed": not unmet,
        "domain": domain,
        "retrieval_gate": {"allowed": r["allowed"], "unmet": r.get("unmet", [])},
        "required_conditions": list(AUTOMATIC_USE_CONDITIONS),
        "unmet": sorted(set(unmet)),
        "strictly_harder_than_retrieval": True,
        "reason": ("every condition is satisfied" if not unmet else
                   "automatic use requires retrieval PLUS an explicit separate grant. "
                   "A retrievable asset may still require manual selection — and "
                   "usually should."),
        "default": False,
        "parser": PARSER,
    }


def gates_are_independent() -> dict:
    """Retrieval and automatic use are never one permission."""
    return {
        "retrieval": RETRIEVAL,
        "automatic_use": AUTOMATIC_USE,
        "collapsed": False,
        "note": "Retrieval means a human may FIND it. Automatic use means the system "
                "may REACH for it unasked. Granting the first never grants the second.",
    }


def font_permissions_are_separate() -> dict:
    """Installation, embedding and production use are their own decisions."""
    return {
        "separate": list(FONT_SEPARATE_PERMISSIONS),
        "implied_by_retrieval": False,
        "implied_by_automatic_use": False,
        "note": "a font may be retrievable for reference and still not installable, "
                "embeddable or usable in production. fsType is metadata, not a grant.",
    }


# --- Historical Design Memory: what may be persisted, and what may never be --------
MEMORY_ALLOWED = (
    "descriptive_layout_observations", "hierarchy", "spacing_tendencies",
    "color_relationships", "typography_structure", "decoration_density",
    "product_category_context", "design_era", "approved_reference_previews",
    "semantic_tags", "confidence", "provenance",
)
MEMORY_EXCLUDED = (
    "exact_reusable_placement_coordinates", "complete_historical_layouts",
    "reusable_dieline_paths", "copied_artwork_paths", "template_instructions",
    "automatic_reproduction_of_old_designs",
)
REFERENCE_MEMORY_ONLY = "REFERENCE_MEMORY_ONLY"


def memory_contract(fields: list) -> dict:
    """What DIP-1 may persist from a historical design — and what it may never."""
    excluded = [f for f in fields if f in MEMORY_EXCLUDED]
    unknown = [f for f in fields
               if f not in MEMORY_ALLOWED and f not in MEMORY_EXCLUDED]
    return {
        "posture": REFERENCE_MEMORY_ONLY,
        "allowed": [f for f in fields if f in MEMORY_ALLOWED],
        "excluded_present": excluded,
        "unknown_fields": unknown,
        "valid": not excluded and not unknown,
        "reason": ("only descriptive observations may be persisted"
                   if not excluded else
                   f"REFUSED: {excluded} would make a historical design REPRODUCIBLE. "
                   "Reference memory teaches; it does not template."),
        "parser": PARSER,
    }


class MemoryContractViolation(C.HumanOnlyStateViolation):
    """A historical design may never become a template."""


def assert_memory_safe(fields: list) -> None:
    r = memory_contract(fields)
    if not r["valid"]:
        raise MemoryContractViolation(r["reason"])
