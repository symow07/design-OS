"""Phase 2C-2A — Complete Product pilot candidate selection (read-only).

Deterministic scoring + the human authorization packet. Never creates a
project or task, never calls a provider, never mutates product or reference
records. The packet's five decisions belong to the human, separately.
"""
from __future__ import annotations
from apps.pipeline.targets.container import archetypes as _declared

PACKET_SCHEMA = "complete_product_pilot_authorization_packet/1.0"

#: §5 bounded weighted categories (sum = 100).
WEIGHTS = {
    "exact_container_reference": 20,
    "confirmed_dimensions_profile": 15,
    "reference_authority": 15,
    "product_copy_completeness": 10,
    "container_pipeline_compatibility": 10,
    "packaging_pipeline_compatibility": 10,
    "qualified_structural_path": 10,
    "visual_simplicity": 5,
    "production_data_completeness": 5,
}

#: §3 stable exclusion codes.
EXCLUSIONS = (
    "PILOT_EXACT_CONTAINER_REFERENCE_MISSING",
    "PILOT_CONTAINER_DIMENSIONS_MISSING",
    "PILOT_REFERENCE_AUTHORITY_INSUFFICIENT",
    "PILOT_PRODUCT_COPY_INCOMPLETE",
    "PILOT_UNSUPPORTED_CONTAINER_ARCHETYPE",
    "PILOT_UNQUALIFIED_PACKAGING_STRUCTURE",
    "PILOT_HUMAN_REJECTION_ACTIVE",
    "PILOT_PRODUCTION_DATA_INSUFFICIENT",
)


def candidate_evidence(product) -> dict:
    """Read-only §4 evidence for one Product row. Facts carry their source;
    inferred values are labelled, never presented as production data."""
    dims = (product.width_mm, product.depth_mm, product.height_mm)
    has_dims = all(v is not None for v in dims)
    dims_text = str(product.dimensions or "")
    dims_referent_ambiguous = "carton" in dims_text.lower()
    copy_fields = {
        "description": bool(product.description),
        "ingredients": bool(getattr(product, "ingredients", "")),
        "how_to_use": bool(getattr(product, "how_to_use", "")),
        "notes": bool(product.notes),
    }
    ptype = (product.product_type or "").lower()
    # §BH70(1): the container's OWN reading of form words. This read "compact" as a JAR, "mascara" and "stick" as a
    # TUBE and anything it did not recognise as a BOTTLE — a lipstick, an eyeliner, even a carton — so the pilot
    # scored a palette as a jar and a pencil as a bottle. An unnamed form is now None, and unsupported by name.
    from apps.pipeline.targets.container import form_named_in
    archetype = form_named_in(ptype)
    return {
        "product_id": product.product_id,
        "name": product.name,
        "category": product.category,
        "brand_id": product.brand_id,
        "record_dims_mm": [float(v) for v in dims] if has_dims else None,
        "dims_source": "PRODUCT_RECORD" if has_dims else "MISSING",
        "dims_referent_ambiguous": dims_referent_ambiguous,
        "dims_referent_note": (dims_text[:120] if dims_referent_ambiguous
                               else ""),
        "inferred_container_archetype": archetype,
        "archetype_source": "INFERRED_FROM_PRODUCT_TYPE — human confirms",
        "copy_fields": copy_fields,
        "copy_complete": all(copy_fields.values()),
        "exact_container_reference": False,   # 2B-3V-PRE: none in the corpus
        "exact_reference_source": ("full-corpus resolver "
                                   "product_container_asset_resolution/1.0 "
                                   "(2B-3V-PRE): exact_asset_found=False"),
        # §BH61(a), ruled: "`complete_product_pilot.py:73` gains compact. A pilot calling my own palette
        # an unsupported form is the same defect wearing a different hat." Reads the declaration so a
        # fifth form is supported here the moment it is drawable.
        "supported_archetype": _declared.is_known(archetype),
    }


def evaluate_candidate(evidence: dict, *, human_rejection_active=False,
                       reference_authority_ok=True) -> dict:
    """§3 hard exclusions + §5 deterministic transparent scoring."""
    exclusions: list[str] = []
    if not evidence["copy_complete"]:
        exclusions.append("PILOT_PRODUCT_COPY_INCOMPLETE")
    if evidence["record_dims_mm"] is None:
        exclusions.append("PILOT_CONTAINER_DIMENSIONS_MISSING")
    if not evidence["supported_archetype"]:
        exclusions.append("PILOT_UNSUPPORTED_CONTAINER_ARCHETYPE")
    if human_rejection_active:
        exclusions.append("PILOT_HUMAN_REJECTION_ACTIVE")
    if not reference_authority_ok:
        exclusions.append("PILOT_REFERENCE_AUTHORITY_INSUFFICIENT")

    scores = {
        # no exact physical container reference exists anywhere in the corpus
        "exact_container_reference":
            0 if not evidence["exact_container_reference"] else 20,
        "confirmed_dimensions_profile":
            (15 if evidence["record_dims_mm"] and
             not evidence["dims_referent_ambiguous"]
             else 9 if evidence["record_dims_mm"] else 0),
        "reference_authority": 12 if reference_authority_ok else 0,
        "product_copy_completeness":
            10 if evidence["copy_complete"]
            else 2 * sum(evidence["copy_fields"].values()),
        "container_pipeline_compatibility":
            10 if evidence["supported_archetype"] else 0,
        "packaging_pipeline_compatibility": 10,   # shared pipeline, validated
        "qualified_structural_path": 10,          # STE/RTE 1.2 domain (2A-9)
        "visual_simplicity":
            2 if evidence["inferred_container_archetype"] == "tube" else 4,
        "production_data_completeness":
            3 if evidence["copy_complete"] else 1,
    }
    total = sum(scores.values())
    return {"evidence": evidence, "scores": scores, "total": total,
            "hard_exclusions": exclusions,
            "recommendable": not exclusions}


def build_authorization_packet(recommended: dict, alternate: dict,
                               rejected: dict, *, preflight: dict,
                               spend_plan: dict) -> dict:
    """§8 complete_product_pilot_authorization_packet/1.0 — every decision
    stays PENDING_HUMAN_APPROVAL; nothing here implies authorization."""
    return {
        "schema_version": PACKET_SCHEMA,
        "recommended_product": recommended,
        "alternate_product": alternate,
        "rejected_or_deferred_example": rejected,
        "provider_call_proposal": spend_plan,
        "expected_human_gates": [
            "direction selection (container)", "Gate-1 concept (container)",
            "profile + decoration-zone confirmation",
            "human design acceptance (container)", "Gate-2 (container)",
            "direction selection (packaging)", "Gate-1 concept (packaging)",
            "dimension/structure confirmation", "Gate-2 (packaging)"],
        "expected_external_blockers": [
            "MISSING_OUTPUT_INTENT (production ICC)",
            "font licence confirmation",
            "manufacturer production-method evidence",
            "verified regulatory data"],
        "success_criteria": "per 2C-2A §9 (persisted verbatim in the report)",
        "abort_criteria": "per 2C-2A §10 (persisted verbatim in the report)",
        "proposed_project_name": (
            f"Complete Product — {recommended['evidence']['name']}"),
        "proposed_recipe": "complete_product/1.0",
        "preflight": {"result": preflight.get("result"),
                      "schema_version": preflight.get("schema_version")},
        "authorization_status": "PENDING_HUMAN_APPROVAL",
        "required_human_decisions": [
            "1. product selection",
            "2. reference approval (incl. supplying/confirming a container "
            "reference or explicitly accepting LIBRARY_GROUNDED mode)",
            "3. provider-call budget",
            "4. regeneration allowance",
            "5. permission to create the DesignProject"],
    }


__all__ = ["PACKET_SCHEMA", "WEIGHTS", "EXCLUSIONS", "candidate_evidence",
           "evaluate_candidate", "build_authorization_packet"]
