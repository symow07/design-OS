"""FINAL VISUAL QUALITY AND CREATIVE PERFORMANCE PROGRAM — registry only.

The live pilot's container stage failed VISUAL fidelity after three human
Gate-2 rejections (2C-2 closeout). This module registers the mandatory
visual-regression fixtures and the deferred engine backlog. The program
itself is DELIBERATELY NOT implemented here — implementing it is its own
reviewed roadmap arc.
"""
from __future__ import annotations

import hashlib as _hl
import json as _json

#: Both tasks are MANDATORY visual-regression fixtures for the program.
VISUAL_REGRESSION_FIXTURES = (
    {"task_id": 51, "role": "CONTAINER_STRUCTURAL_CORRECTION_FIXTURE"},
    {"task_id": 52, "role": "REJECTED_LIVE_PILOT_FIXTURE",
     "selected_image_id": 97, "variation": "B_ROSE_SMOKE",
     "rejections": 4, "never_an_accepted_fixture": True},
)

#: Deferred engine work (2C-2 closeout §6) — recorded, not implemented.
ENGINE_BACKLOG = (
    "true cylindrical bottle projection and rendering",
    "realistic frosted-glass material realization",
    "physically coherent neck/collar/bulb assembly",
    "polished-metal vector material recipes",
    "selected-concept typography extraction and grouping",
    "palette and material fidelity validation",
    "actual visual-image comparison rather than nominal geometry ratios",
    "prevention of generic schematic fallbacks",
    "designer-grade concept-sheet rendering",
    "human rejection regression fixtures",
)

# ===========================================================================
# VQ-0 — VISUAL FAILURE BASELINE, ENGINE DIAGNOSTICS AND IMPROVEMENT
# ARCHITECTURE (2026-07-27). Architecture + executable diagnostic seeds
# only — no provider, no reconstruction, no engine changes.
# ===========================================================================
PROGRAM_SCHEMA = "final_visual_quality_program/1.0"
DECOMPOSITION_SCHEMA = "selected_concept_visual_decomposition/1.0"
PERCEIVED_GEOMETRY_SCHEMA = "container_perceived_geometry_contract/1.0"
TYPOGRAPHY_CONTRACT_SCHEMA = "container_typography_visual_contract/1.0"
REGRESSION_FIXTURE_SCHEMA = "human_visual_regression_fixture/1.0"

#: §3 stable visual-failure taxonomy (family → codes)
FAILURE_TAXONOMY = {
    "REFERENCE_INTERPRETATION": (
        "VQ_PHOTOGRAPHIC_STYLING_AS_PRINT", "VQ_PHYSICAL_OBJECT_AS_ARTWORK",
        "VQ_LABEL_VS_DIRECT_PRINT_CONFUSION",
        "VQ_FILL_VS_WALL_CONFUSION", "VQ_BACKGROUND_AS_DESIGN_CONTENT"),
    "STRUCTURAL_FORM": (
        "VQ_ARCHETYPE_MISMATCH", "VQ_CYLINDER_AS_ROUNDED_RECTANGLE",
        "VQ_CLOSURE_DISCONTINUITY", "VQ_GENERIC_SILHOUETTE_FALLBACK",
        "VQ_ASPECT_PERCEPTUAL_MISMATCH", "VQ_CAP_BODY_RELATIONSHIP_FAILED"),
    "MATERIAL_REALIZATION": (
        "VQ_TRANSPARENT_RENDERED_OPAQUE", "VQ_FROST_AS_STRIPES",
        "VQ_METAL_AS_FLAT_COLOR", "VQ_FILL_COLLAPSED_INTO_WALL",
        "VQ_REFRACTION_AS_GRAPHIC_BARS", "VQ_VIZ_MIXED_INTO_SEPARATIONS"),
    "TYPOGRAPHY": (
        "VQ_NAME_GROUPING_FAILED", "VQ_LOGO_SCALE_FAILED",
        "VQ_HIERARCHY_INVERSION", "VQ_LEADING_FAILED",
        "VQ_FONT_CHARACTER_MISMATCH", "VQ_LIVE_TEXT_VISUALLY_WRONG"),
    "COMPOSITION": (
        "VQ_LABEL_CARD_FALLBACK", "VQ_ARTWORK_DETACHED_FROM_MATERIAL",
        "VQ_EXCESSIVE_EMPTY_ZONES", "VQ_FOCAL_POINT_MISMATCH",
        "VQ_NEGATIVE_SPACE_LOST"),
    "VALIDATION": (
        "VQ_LABEL_SELF_CERTIFICATION", "VQ_NOMINAL_PASSES_GENERIC_GEOMETRY",
        "VQ_METADATA_WITHOUT_VISUAL_AGREEMENT",
        "VQ_REJECTION_NOT_IN_REGRESSIONS", "VQ_PREVIEW_GRAPH_DIVERGENCE"),
}

#: §4 required decomposition components (each carries bounds/proportions/
#: confidence/source/classification/production-relevance/authority/review)
DECOMPOSITION_COMPONENTS = (
    "physical_silhouette_mask", "body_mask", "shoulder_mask", "neck_mask",
    "collar_cap_mask", "bulb_closure_mask", "transparent_wall_region",
    "product_fill_region", "printed_artwork_region", "attached_label_region",
    "typography_regions", "logo_region", "product_name_region",
    "supporting_copy_region", "material_highlight_regions",
    "photographic_styling_regions", "background_prop_regions",
    "uncertainty_regions")

#: §5 perceived-form checks (nominal ratios can NEVER stand in for these)
PERCEIVED_FORM_CHECKS = (
    "cylindrical_readability", "shoulder_continuity", "neck_visibility",
    "closure_coherence", "body_slenderness", "top_heaviness",
    "visual_center_of_mass", "edge_curvature_continuity",
    "material_dependent_silhouette_perception")

#: §6 material contracts: unacceptable fallback descriptors per material
MATERIAL_CONTRACTS = {
    "FROSTED_GLASS": {"forbidden_fallbacks": (
        "single_opaque_fill", "broad_white_bars", "flat_rect_gradients",
        "footer_base_band")},
    "POLISHED_ROSE_GOLD": {"forbidden_fallbacks": (
        "flat_pink_fill", "rect_tonal_panels", "yellow_gold_substitution")},
    "TRANSPARENT_GLASS": {"forbidden_fallbacks": ("single_opaque_fill",)},
    "TINTED_GLASS": {"forbidden_fallbacks": ("single_opaque_fill",)},
    "TRANSLUCENT_PLASTIC": {"forbidden_fallbacks": ("single_opaque_fill",)},
    "OPAQUE_PLASTIC": {"forbidden_fallbacks": ()},
    "POLISHED_GOLD": {"forbidden_fallbacks": ("flat_yellow_fill",)},
    "BRUSHED_METAL": {"forbidden_fallbacks": ("flat_grey_fill",)},
    "SOFT_TOUCH_CARTON": {"forbidden_fallbacks": ()},
    "MATTE_CARTON": {"forbidden_fallbacks": ()},
    "FOIL": {"forbidden_fallbacks": ("flat_fill_no_specular",)},
    "SPOT_UV": {"forbidden_fallbacks": ("visible_opaque_overlay",)},
}
MATERIAL_CONTRACT_FIELDS = (
    "editable_object_structure", "highlight_behavior", "shadow_behavior",
    "edge_behavior", "transparency", "refraction", "curvature_dependency",
    "production_vs_visualization_layers", "unacceptable_fallback_forms",
    "actual_preview_validation")

#: §7 missing deterministic bottle backbones (audit result)
MISSING_BOTTLE_BACKBONES = (
    "cylindrical_dropper_bottle", "cylindrical_pump_bottle",
    "rectangular_rigid_bottle", "oval_bottle", "airless_bottle",
    "serum_bottle_flat_shoulder", "serum_bottle_rounded_shoulder")

#: §9 bounded preview-comparison metrics (evidence for humans, never a
#: replacement for human judgment; pixel identity never required)
PREVIEW_COMPARISON_METRICS = (
    "silhouette_overlap", "component_centroid_difference",
    "normalized_component_ratios", "material_area_distribution",
    "palette_distance_bands", "typography_region_alignment",
    "negative_space_distribution", "closure_body_visual_relationship",
    "direct_print_vs_label_relationship")

#: §11 scorecard (human rejection overrides; never auto-approves Gate 2)
SCORECARD = {
    "structural_form": {"max": 20, "critical_min": 14},
    "closure_cap_fidelity": {"max": 15, "critical_min": None},
    "material_realization": {"max": 20, "critical_min": 14},
    "typography": {"max": 15, "critical_min": None},
    "composition": {"max": 10, "critical_min": None},
    "palette": {"max": 10, "critical_min": None},
    "selected_concept_preservation": {"max": 10, "critical_min": 7},
}

#: §12 bounded workstreams (NOT implemented in VQ-0)
WORKSTREAMS = {
    "VQ-1": {"title": "Cylindrical Bottle Backbone and Closure Assembly",
             "depends_on": [], "targets": [
                 "apps/pipeline/targets/container/silhouettes.py",
                 "apps/ire/compose_dropper.py"],
             "schema_impact": "none", "migration": "none",
             "fixtures": [52], "stop": "human visual review",
             "providers": "none", "effort": "L"},
    "VQ-2": {"title": "Glass, Frosted Glass and Product-Fill Rendering",
             "depends_on": ["VQ-1"], "targets": ["apps/ire/compose_dropper.py",
                                                 "apps/ire/design_language.py"],
             "schema_impact": "material contracts", "migration": "none",
             "fixtures": [51, 52], "stop": "human visual review",
             "providers": "none", "effort": "L"},
    "VQ-3": {"title": "Metallic Collar and Cap Material Realization",
             "depends_on": ["VQ-1"], "targets": ["apps/ire/compose_dropper.py"],
             "schema_impact": "material contracts", "migration": "none",
             "fixtures": [52], "stop": "human visual review",
             "providers": "none", "effort": "M"},
    "VQ-4": {"title": "Selected-Concept Typography Extraction and Grouping",
             "depends_on": [], "targets": [
                 "apps/pipeline/services/selected_concept_contract.py",
                 "apps/ire/container_motif_fidelity.py"],
             "schema_impact": TYPOGRAPHY_CONTRACT_SCHEMA,
             "migration": "none", "fixtures": [51, 52],
             "stop": "human visual review", "providers": "none",
             "effort": "M"},
    "VQ-5": {"title": "Direct Print, Label and Photographic-Styling "
                      "Classification",
             "depends_on": [], "targets": [
                 "apps/pipeline/services/container_visual_graph.py"],
             "schema_impact": DECOMPOSITION_SCHEMA, "migration": "none",
             "fixtures": [51], "stop": "human visual review",
             "providers": "none", "effort": "M"},
    "VQ-6": {"title": "Actual Preview Comparison and Perceived Geometry "
                      "Validation",
             "depends_on": ["VQ-1", "VQ-2"], "targets": [
                 "apps/ire/container_concept_fidelity.py"],
             "schema_impact": PERCEIVED_GEOMETRY_SCHEMA,
             "migration": "none", "fixtures": [51, 52],
             "stop": "human visual review", "providers": "none",
             "effort": "L"},
    "VQ-7": {"title": "Designer-Grade Concept Sheet and Review Board",
             "depends_on": ["VQ-1", "VQ-2", "VQ-3"],
             "targets": ["apps/ire/compose_dropper.py",
                         "apps/pipeline/review_board.py"],
             "schema_impact": "none", "migration": "none",
             "fixtures": [52], "stop": "human visual review",
             "providers": "none", "effort": "M"},
    "VQ-8": {"title": "Real Regression Rebuild of task #52",
             "depends_on": ["VQ-1", "VQ-2", "VQ-3", "VQ-4", "VQ-6", "VQ-7"],
             "targets": ["live re-render, human Gate-2 review"],
             "schema_impact": "none", "migration": "none",
             "fixtures": [52], "stop": "human acceptance decision",
             "providers": "none", "effort": "M"},
    "VQ-9": {"title": "Real Regression Rebuild of task #51",
             "depends_on": ["VQ-2", "VQ-5", "VQ-6"],
             "targets": ["live re-render, human review"],
             "schema_impact": "none", "migration": "none",
             "fixtures": [51], "stop": "human acceptance decision",
             "providers": "none", "effort": "M"},
}

SUCCESS_CRITERIA = (
    "task #52 reconstructs as a visibly cylindrical premium serum bottle",
    "closure reads as a physically coherent neck/collar/bulb assembly",
    "frosted glass reads as material, not vector bands",
    "rose gold reads as metal, not pink plastic",
    "Rose/Damascena remains one coherent typographic block",
    "task #51 no longer turns photographic condensation into printed artwork",
    "generic label and silhouette fallbacks fail closed",
    "actual-preview comparison supports the human visual verdict",
    "native editability remains intact",
    "decorative raster count stays zero (controlled fallbacks only)",
    "human review approves the replacement output",
)


# --- executable diagnostic seeds (pure, deterministic) ----------------------

def classify_reference_region(kind: str) -> str:
    """§3-A: photographic phenomena are STYLING, never printable artwork."""
    styling = ("condensation", "droplet", "dewdrop", "reflection", "shadow",
               "highlight", "glare", "backdrop", "prop", "water")
    return ("PHOTOGRAPHIC_STYLING_NOT_PRINTED_ARTWORK"
            if any(s in (kind or "").lower() for s in styling)
            else "CANDIDATE_DESIGN_CONTENT")


def perceived_form_findings(descriptor: dict) -> list[str]:
    """§5 seed: a silhouette descriptor {curve_segments, top_width_ratio,
    has_shoulder_transition} — nominal bounding boxes never satisfy this."""
    out = []
    if descriptor.get("curve_segments", 0) < 4 or             descriptor.get("top_width_ratio", 1.0) > 0.45:
        out.append("VQ_CYLINDER_AS_ROUNDED_RECTANGLE")
    if not descriptor.get("has_shoulder_transition"):
        out.append("VQ_CLOSURE_DISCONTINUITY")
    return out


def material_realization_findings(material: str, objects: list[dict]
                                  ) -> list[str]:
    """§6 seed: reject fallback-only realizations. ``objects`` carry
    {shape: rect|path_curved, opacity, role}."""
    out = []
    rects = [o for o in objects if o.get("shape") == "rect"]
    curved = [o for o in objects if o.get("shape") == "path_curved"]
    if material == "FROSTED_GLASS":
        if len(objects) <= 1 or (rects and not curved):
            out.append("VQ_FROST_AS_STRIPES")
        if objects and all(float(o.get("opacity", 1)) >= 0.95
                           for o in objects):
            out.append("VQ_TRANSPARENT_RENDERED_OPAQUE")
    if material == "POLISHED_ROSE_GOLD":
        roles = {o.get("role") for o in objects}
        if not ({"highlight", "shadow"} <= roles) or                 all(o.get("paint") == "solid" for o in objects):
            out.append("VQ_METAL_AS_FLAT_COLOR")
    return out


def typography_grouping_findings(runs: list[dict]) -> list[str]:
    """§8 seed: name runs {y, size_pt, kind}; a gap > 1.45×size splits the
    semantic block even when both live runs exist inside the zone."""
    name = sorted((r for r in runs if r.get("kind") == "product_name"),
                  key=lambda r: r["y"])
    if len(name) >= 2:
        gap = name[1]["y"] - name[0]["y"]
        if gap > name[0]["size_pt"] * 1.45:
            return ["VQ_NAME_GROUPING_FAILED"]
    return []


#: A217/A224 — a disposition is a TOKEN, not a substring. The prior
#: form tested `"REJECTED" in human_state`, which also fires on any
#: state merely CONTAINING the word (a NEVER_REJECTED or
#: NOT_REJECTED state would have read as a rejection). Human states
#: arrive compound ("REJECTED / REVISION_REQUIRED"), so the fix is
#: token equality against an enumerated set, never substring.
HUMAN_REJECTION_STATES = frozenset({
    "REJECTED", "REJECTED_BY_HUMAN", "HUMAN_REJECTED",
    "REVISION_REQUIRED"})


def _state_tokens(state: str) -> set:
    """Split a compound human state into its enumerable tokens."""
    import re as _re
    return {t for t in _re.split(r"[^A-Za-z_]+", state.upper()) if t}


def visual_verdict(*, perceived: list[str], material: list[str],
                   typography: list[str], nominal_ok: bool,
                   human_state: str) -> str:
    """§5/§10: nominal geometry can never self-certify, and a human
    rejection is authoritative over every automated result."""
    if _state_tokens(human_state or "") & HUMAN_REJECTION_STATES:
        return "REJECTED_BY_HUMAN"
    if perceived or material or typography:
        return "VISUAL_FIDELITY_FAILED"
    return "PASSES_PENDING_HUMAN_REVIEW" if nominal_ok else         "NOMINAL_GEOMETRY_FAILED"


def build_program_record() -> dict:
    """§2 the deterministic final_visual_quality_program/1.0 record."""
    record = {
        "schema_version": PROGRAM_SCHEMA,
        "status": "BASELINE_AND_ARCHITECTURE",
        "human_review_state": "PENDING_PROGRAM_ARCHITECTURE_REVIEW",
        "fixtures": [
            {"task_id": 51, "selected_image_id": 95,
             "selected_variation": "C_DEWDROP_CONSTELLATION",
             "state": "HUMAN_REJECTED / NEVER_ACCEPTED_FIXTURE",
             "lessons": [
                 "photographic condensation misclassified as printed artwork",
                 "generic label fallback appeared",
                 "transparent wall and product fill visually collapsed",
                 "selected container geometry not preserved",
                 "technical validators passed visually unrelated output"]},
            {"task_id": 52, "selected_image_id": 97,
             "selected_variation": "B_ROSE_SMOKE",
             "state": "HUMAN_REJECTED / NEVER_ACCEPTED_FIXTURE",
             "rejection_outputs": ["qJ5Rt23", "3raQ6aB", "oeWjCvc",
                                   "SmTqI0A"],
             "lessons": [
                 "cylindrical bottle became a rectangular schematic",
                 "collar/neck/bulb failed perceived closure fidelity",
                 "frosted glass became vector bands and flat fills",
                 "rose-gold roles did not create metallic appearance",
                 "product-name grouping and hierarchy not preserved",
                 "repeated dimension tuning did not solve the visual problem",
                 "automated geometry passes inconsistent with human "
                 "judgment"]},
        ],
        "engine_components": [
            "targets/container/silhouettes.py", "ire/compose_dropper.py",
            "ire/compose_container.py", "ire/container_concept_fidelity.py",
            "ire/container_motif_fidelity.py",
            "services/container_visual_graph.py",
            "services/selected_concept_contract.py"],
        "failure_taxonomy": {k: list(v) for k, v in
                             FAILURE_TAXONOMY.items()},
        "decomposition_schema": DECOMPOSITION_SCHEMA,
        "decomposition_components": list(DECOMPOSITION_COMPONENTS),
        "perceived_geometry_contract": {
            "schema": PERCEIVED_GEOMETRY_SCHEMA,
            "distinguishes": ["nominal_technical", "emitted_vector",
                              "perceived_visual"],
            "checks": list(PERCEIVED_FORM_CHECKS)},
        "material_contracts": {k: {"forbidden_fallbacks": list(
            v["forbidden_fallbacks"]), "fields": list(
            MATERIAL_CONTRACT_FIELDS)} for k, v in
            MATERIAL_CONTRACTS.items()},
        "missing_bottle_backbones": list(MISSING_BOTTLE_BACKBONES),
        "typography_contract": TYPOGRAPHY_CONTRACT_SCHEMA,
        "preview_comparison": {"metrics": list(PREVIEW_COMPARISON_METRICS),
                               "authority": "evidence for human review — "
                                            "never a replacement"},
        "regression_fixture_schema": REGRESSION_FIXTURE_SCHEMA,
        "scorecard": SCORECARD,
        "workstreams": WORKSTREAMS,
        "success_criteria": list(SUCCESS_CRITERIA),
        "stop_conditions": ["human rejection is always authoritative",
                            "no automated Gate-2 approval",
                            "each workstream stops for human visual review"],
    }
    record["program_hash"] = _hl.sha256(_json.dumps(
        record, sort_keys=True, default=str).encode()).hexdigest()
    return record


__all__ = ["VISUAL_REGRESSION_FIXTURES", "ENGINE_BACKLOG", "PROGRAM_SCHEMA",
           "FAILURE_TAXONOMY", "DECOMPOSITION_COMPONENTS",
           "PERCEIVED_FORM_CHECKS", "MATERIAL_CONTRACTS", "SCORECARD",
           "WORKSTREAMS", "SUCCESS_CRITERIA", "build_program_record",
           "classify_reference_region", "perceived_form_findings",
           "material_realization_findings", "typography_grouping_findings",
           "visual_verdict"]
