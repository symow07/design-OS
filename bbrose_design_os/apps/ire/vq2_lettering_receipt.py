"""VQ-2 product-name lettering — receipt validation contract.

Frozen BEFORE any asset arrives, so the criteria cannot be tailored to a
submitted file. ``MANDATORY_CHECKS`` is the single source of truth: both the
resume contract and the detailed validation specification are generated from
it, so neither file can end up weaker than the other.

Nothing here draws, traces or generates lettering. It only judges a delivered
asset description.
"""
from __future__ import annotations

CONTRACT_VERSION = "3.1"
NORMALIZED = "VQ2_PRE_RECEIPT_VALIDATION_CONTRACT_NORMALIZED"

#: v3 — the handoff template is PDF-compatible artwork, not a native layered
#: .ai. The designer therefore authors a NEW native Illustrator document and
#: may place the template as a locked, non-printing reference.
NATIVE_SOURCE_REQUIRED = "VQ2_NATIVE_ILLUSTRATOR_SOURCE_REQUIRED"
REQUIRED_LAYER_MISSING = "VQ2_REQUIRED_NATIVE_LAYER_MISSING"
OUTPUT_ONLY_IN_REFERENCE = "VQ2_DESIGNER_OUTPUT_FOUND_ONLY_IN_IMPORTED_REFERENCE"
PDF_COMPATIBLE_NOT_SOURCE = "VQ2_PDF_COMPATIBLE_FILE_NOT_AUTHORITATIVE_AI_SOURCE"
EXPANDED_AFTER_DISTORTION = "VQ2_GEOMETRY_EXPANDED_AFTER_DISTORTION"

#: the layer structure the DESIGNER must build in their own document
REQUIRED_DESIGNER_LAYERS = (
    "00_REFERENCE_NONPRINTING", "01_M3_STRUCTURE_LOCKED",
    "02_APPROVED_BBROSE_LOGO_LOCKED", "03_ARTWORK_ZONE_GUIDES_NONPRINTING",
    "04_ROSE_LETTERING", "05_DAMASCENA_LETTERING",
    "06_SUPPORTING_COPY_LOCKED", "07_DIVIDER_RULE_LOCKED",
    "08_MEASUREMENT_GUIDES_NONPRINTING", "09_DESIGNER_NOTES_NONPRINTING",
    "10_AUDIT_METADATA_NONPRINTING")

WORD_LAYER = {"Rose": "04_ROSE_LETTERING",
              "Damascena": "05_DAMASCENA_LETTERING"}

REQUIRED_WORDS = ("Rose", "Damascena")
REQUIRED_LINE_ORDER = ("Rose", "Damascena")

# --- stable findings ----------------------------------------------------------
HORIZONTAL_SCALING = "VQ2_HORIZONTAL_GLYPH_SCALING_DETECTED"
VERTICAL_SCALING = "VQ2_VERTICAL_GLYPH_SCALING_DETECTED"
NONUNIFORM_SCALING = "VQ2_NONUNIFORM_GLYPH_SCALING_DETECTED"
WORD_GROUP_SCALING = "VQ2_WORD_GROUP_SCALING_DETECTED"
CAPITALIZATION_MISMATCH = "VQ2_PRODUCT_NAME_CAPITALIZATION_MISMATCH"
COUNTER_COLLAPSED = "VQ2_GLYPH_COUNTER_COLLAPSED"
COUNTER_MISSING = "VQ2_GLYPH_COUNTER_MISSING"
COUNTER_DUPLICATED = "VQ2_GLYPH_COUNTER_DUPLICATED"
FILL_RULE_INVALID = "VQ2_GLYPH_FILL_RULE_INVALID"
WORDING_MISMATCH = "VQ2_PRODUCT_NAME_WORDING_MISMATCH"
LINE_ORDER_MISMATCH = "VQ2_PRODUCT_NAME_LINE_ORDER_MISMATCH"
RASTER_CONTENT = "VQ2_RASTER_CONTENT_DETECTED"
LIVE_FONT = "VQ2_UNRESOLVED_LIVE_FONT_DETECTED"
GLYPH_NOT_EDITABLE = "VQ2_GLYPH_NOT_INDEPENDENTLY_EDITABLE"
GLYPH_COLLISION = "VQ2_GLYPH_COLLISION_DETECTED"
SELF_INTERSECTION = "VQ2_SELF_INTERSECTION_DETECTED"
OPEN_PATH = "VQ2_UNINTENDED_OPEN_PATH_DETECTED"
CURVED_BASELINE = "VQ2_CANONICAL_BASELINE_NOT_STRAIGHT"
WIDTH_OUT_OF_TOLERANCE = "VQ2_APPARENT_WIDTH_OUT_OF_TOLERANCE"
CENTERLINE_OUT_OF_TOLERANCE = "VQ2_CENTERLINE_OUT_OF_TOLERANCE"
CAP_HEIGHT_OUT_OF_TOLERANCE = "VQ2_CAP_HEIGHT_OUT_OF_TOLERANCE"
LINE_SPACING_OUT_OF_TOLERANCE = "VQ2_LINE_SPACING_OUT_OF_TOLERANCE"
LAYER_STRUCTURE_INVALID = "VQ2_LAYER_STRUCTURE_INVALID"
BEZIER_CONSTRUCTION_INVALID = "VQ2_BEZIER_CONSTRUCTION_INVALID"
OWNER_APPROVAL_MISSING = "VQ2_OWNER_APPROVAL_MISSING"

ACCEPTED = "VQ2_PRODUCT_NAME_LETTERING: RESOLVED_OWNER_APPROVED"
REJECTED = "VQ2_LETTERING_RECEIPT_REJECTED"

#: §5 — the authoritative checklist. Both contract files are generated from
#: this, so they cannot diverge.
MANDATORY_CHECKS = (
    ("exact_wording", WORDING_MISMATCH),
    ("exact_capitalization", CAPITALIZATION_MISMATCH),
    ("correct_line_order", LINE_ORDER_MISMATCH),
    ("vector_only_construction", RASTER_CONTENT),
    ("one_independently_editable_object_per_glyph", GLYPH_NOT_EDITABLE),
    ("no_raster_content", RASTER_CONTENT),
    ("no_unresolved_live_fonts", LIVE_FONT),
    ("no_horizontal_scaling", HORIZONTAL_SCALING),
    ("no_vertical_scaling", VERTICAL_SCALING),
    ("no_nonuniform_scaling", NONUNIFORM_SCALING),
    ("no_scaled_word_groups", WORD_GROUP_SCALING),
    ("no_colliding_glyphs", GLYPH_COLLISION),
    ("no_self_intersections", SELF_INTERSECTION),
    ("no_unintended_open_paths", OPEN_PATH),
    ("valid_counters_and_fill_rules", COUNTER_COLLAPSED),
    ("clean_cubic_bezier_construction", BEZIER_CONSTRUCTION_INVALID),
    ("clean_layer_structure", LAYER_STRUCTURE_INVALID),
    ("straight_canonical_baselines", CURVED_BASELINE),
    ("apparent_front_width_compliance", WIDTH_OUT_OF_TOLERANCE),
    ("centerline_compliance", CENTERLINE_OUT_OF_TOLERANCE),
    ("cap_height_compliance", CAP_HEIGHT_OUT_OF_TOLERANCE),
    ("line_spacing_compliance", LINE_SPACING_OUT_OF_TOLERANCE),
    ("owner_approval", OWNER_APPROVAL_MISSING),
    # --- v3 asset-authority checks -------------------------------------
    ("native_illustrator_source_provenance", NATIVE_SOURCE_REQUIRED),
    ("native_layer_inventory_present", REQUIRED_LAYER_MISSING),
    ("required_layer_names_present", REQUIRED_LAYER_MISSING),
    ("rose_and_damascena_in_designated_layers", REQUIRED_LAYER_MISSING),
    ("reference_template_isolated_locked_nonprinting",
     OUTPUT_ONLY_IN_REFERENCE),
    ("no_final_glyphs_only_in_imported_reference", OUTPUT_ONLY_IN_REFERENCE),
    ("pdf_compatible_file_not_accepted_as_source", PDF_COMPATIBLE_NOT_SOURCE),
    ("no_geometry_expanded_after_distortion", EXPANDED_AFTER_DISTORTION),
)
CHECK_NAMES = tuple(n for n, _ in MANDATORY_CHECKS)

TOLERANCES = {
    "apparent_width_err_max": 0.025,
    "centerline_err_max_of_body_width": 0.010,
    "cap_height_err_max": 0.020,
    "line_spacing_err_max": 0.020,
    "baseline_angle_err_max_deg": 0.5,
    "scale_unity_tolerance": 0.005,
}

#: §2 — drawn proportions are NOT distortion
PROPORTION_RULE = {
    "A_NATIVE_DRAWN_GEOMETRY": {
        "permitted": True,
        "description": "Bezier outlines authored directly at their intended "
                       "proportions, object transform normalized, no "
                       "post-construction horizontal or vertical compression.",
        "narrow_proportions_alone_are_a_defect": False,
    },
    "B_TRANSFORMED_OR_DISTORTED_GEOMETRY": {
        "permitted": False,
        "description": "A font or outline scaled horizontally or vertically, "
                       "a non-uniform transform applied to a glyph, word or "
                       "group, or geometry expanded only after distortion to "
                       "conceal the transform.",
    },
    "rule": "A correctly drawn condensed letterform must NOT be rejected "
            "merely because its visual proportions are narrow. What is "
            "prohibited is a TRANSFORM, not a proportion.",
}

#: v3.1 owner ruling — derivation history governs, not the delivered matrix
DERIVATION_RULE = {
    "permitted": [
        "ordinary UNIFORM conversion from font design units to a working "
        "size (any magnitude, sx == sy)",
        "native human-drawn condensed geometry",
        "a genuinely condensed licensed typeface used without non-uniform "
        "distortion",
        "glyph paths authored directly at their intended final proportions",
    ],
    "prohibited": [
        "horizontal compression of an existing font outline",
        "vertical distortion of an existing font outline",
        "unequal x/y scaling",
        "different compression factors applied per glyph",
        "word-group scaling used to force composition",
        "expanding or baking distorted geometry to remove visible transform "
        "matrices",
    ],
    "applies_to": ["active transforms",
                   "distortion expanded or baked into the final paths"],
    "zero_active_transforms_proves":
        "only that the submitted files contain NORMALIZED paths. It does not "
        "prove those paths were natively authored at their final proportions.",
    "vertical_finding_clarification":
        "A non-unit sy is NOT prohibited by itself. VQ2_VERTICAL_GLYPH_"
        "SCALING_DETECTED fires only on evidence of vertical distortion "
        "independent of canonical uniform size conversion.",
}

#: §4 — letters whose forms carry counters. The DELIVERED construction is the
#: authority; this is the minimum set to inspect.
COUNTER_LETTERS_MINIMUM = ("R", "o", "e", "D", "a")


def _scale_findings(obj: dict) -> list:
    """Transform analysis for one glyph or group.

    v3.1 clarification (owner ruling): a UNIFORM scale from font design units
    to a working size is ordinary vector construction and is NOT a defect,
    however far from 1.0 it is. What is prohibited is DISTORTION — unequal
    x/y scaling — whether it survives as an active transform or was baked
    into the paths afterwards.
    """
    out = []
    tol = TOLERANCES["scale_unity_tolerance"]
    sx = obj.get("scale_x", 1.0)
    sy = obj.get("scale_y", 1.0)
    kind = obj.get("kind", "glyph")
    baked = bool(obj.get("expanded_after_distortion"))

    if abs(sy) < 1e-12:
        return [NONUNIFORM_SCALING]
    ratio = sx / sy
    distorted = abs(ratio - 1.0) > tol

    if distorted:
        out.append(NONUNIFORM_SCALING)
        # name the compressed/stretched axis relative to uniform sizing
        if ratio < 1.0:
            out.append(HORIZONTAL_SCALING)
        else:
            out.append(VERTICAL_SCALING)
    elif obj.get("vertical_distortion_evidence"):
        out.extend([VERTICAL_SCALING, NONUNIFORM_SCALING])

    # Scaling a WORD GROUP forces composition and is prohibited even when
    # uniform — unlike a glyph, where uniform scaling is ordinary sizing.
    if kind in ("word_group", "group") and (abs(sx - 1.0) > tol
                                            or abs(sy - 1.0) > tol):
        out.append(WORD_GROUP_SCALING)

    # Baking distorted geometry never cures the derivation.
    if baked:
        out.append(EXPANDED_AFTER_DISTORTION)
        if NONUNIFORM_SCALING not in out:
            out.append(NONUNIFORM_SCALING)
    return out


def check_capitalization(words) -> list:
    """§3 — exact strings, no case conversion, no punctuation, no omission."""
    if list(words) != list(REQUIRED_WORDS):
        return [CAPITALIZATION_MISMATCH]
    return []


def check_counters(glyphs) -> list:
    """§4 — counters open, coherent, not duplicated, fill rules valid."""
    out = []
    for g in glyphs:
        ch = g.get("char", "")
        if ch not in COUNTER_LETTERS_MINIMUM and not g.get("has_counter"):
            continue
        if g.get("counter_collapsed"):
            out.append(COUNTER_COLLAPSED)
        if g.get("has_counter") and g.get("counter_count", 0) < 1:
            out.append(COUNTER_MISSING)
        if g.get("counter_count", 0) > g.get("expected_counters", 9):
            out.append(COUNTER_DUPLICATED)
        if g.get("fill_rule") not in (None, "evenodd", "nonzero"):
            out.append(FILL_RULE_INVALID)
        if g.get("fill_rule_invalid"):
            out.append(FILL_RULE_INVALID)
        if g.get("counter_simulated_by_clipping"):
            out.append(FILL_RULE_INVALID)
    return out


def check_native_source(asset: dict) -> list:
    """v3 §4 — asset authority.

    The delivery must be a NEW native Illustrator document. A PDF-compatible
    file renamed to .ai is not the authoritative source, and final glyphs must
    live in the designer's own layers rather than inside a placed reference.

    A valid native file is NOT rejected merely because its binary structure
    differs from our ReportLab-emitted template — only the recorded provenance
    facts are judged.
    """
    out = []
    if not asset.get("native_illustrator_source", False):
        out.append(NATIVE_SOURCE_REQUIRED)
    if asset.get("pdf_compatible_only") or asset.get("renamed_pdf"):
        out.append(PDF_COMPATIBLE_NOT_SOURCE)

    layers = asset.get("native_layers")
    if layers is None:
        out.append(REQUIRED_LAYER_MISSING)
    else:
        missing = [n for n in REQUIRED_DESIGNER_LAYERS if n not in layers]
        if missing:
            out.append(REQUIRED_LAYER_MISSING)

    placement = asset.get("glyph_layer_placement", {})
    for word, layer in WORD_LAYER.items():
        if placement and placement.get(word) != layer:
            out.append(REQUIRED_LAYER_MISSING)
    if not placement and layers is not None:
        out.append(REQUIRED_LAYER_MISSING)

    ref = asset.get("reference_template", {})
    if ref:
        if not (ref.get("locked") and ref.get("nonprinting")):
            out.append(OUTPUT_ONLY_IN_REFERENCE)
    if asset.get("final_glyphs_only_in_imported_reference"):
        out.append(OUTPUT_ONLY_IN_REFERENCE)
    return out


def validate_receipt(asset: dict) -> dict:
    """Judge a delivered lettering asset against the frozen contract.

    ``asset`` is a description, not artwork. This function never draws.
    """
    f = []
    words = asset.get("words", [])
    if [w.lower() for w in words] != [w.lower() for w in REQUIRED_WORDS]:
        f.append(WORDING_MISMATCH)
    else:
        f += check_capitalization(words)
    if list(asset.get("line_order", words)) != list(REQUIRED_LINE_ORDER):
        f.append(LINE_ORDER_MISMATCH)

    if asset.get("raster_object_count", 0) > 0:
        f.append(RASTER_CONTENT)
    if asset.get("live_font_object_count", 0) > 0:
        f.append(LIVE_FONT)
    if not asset.get("one_object_per_glyph", False):
        f.append(GLYPH_NOT_EDITABLE)
    if asset.get("glyph_collisions", 0) > 0:
        f.append(GLYPH_COLLISION)
    if asset.get("self_intersections", 0) > 0:
        f.append(SELF_INTERSECTION)
    if asset.get("unintended_open_paths", 0) > 0:
        f.append(OPEN_PATH)
    if not asset.get("clean_layer_structure", False):
        f.append(LAYER_STRUCTURE_INVALID)
    if not asset.get("cubic_bezier_construction", True):
        f.append(BEZIER_CONSTRUCTION_INVALID)
    if not asset.get("baselines_straight", False):
        f.append(CURVED_BASELINE)
    if not asset.get("owner_approved", False):
        f.append(OWNER_APPROVAL_MISSING)

    for obj in asset.get("transforms", []):
        f += _scale_findings(obj)
    f += check_counters(asset.get("glyphs", []))
    f += check_native_source(asset)

    m = asset.get("metrics", {})
    if m:
        for w in ("Rose", "Damascena"):
            wm = m.get(w, {})
            if wm.get("apparent_width_err", 0.0) > \
                    TOLERANCES["apparent_width_err_max"]:
                f.append(WIDTH_OUT_OF_TOLERANCE)
            if wm.get("centerline_err", 0.0) > \
                    TOLERANCES["centerline_err_max_of_body_width"]:
                f.append(CENTERLINE_OUT_OF_TOLERANCE)
            if wm.get("cap_height_err", 0.0) > \
                    TOLERANCES["cap_height_err_max"]:
                f.append(CAP_HEIGHT_OUT_OF_TOLERANCE)
        if m.get("line_spacing_err", 0.0) > \
                TOLERANCES["line_spacing_err_max"]:
            f.append(LINE_SPACING_OUT_OF_TOLERANCE)

    findings = sorted(set(f))
    return {
        "contract_version": CONTRACT_VERSION,
        "findings": findings,
        "accepted": not findings,
        "state": ACCEPTED if not findings else REJECTED,
        "narrow_proportions_alone_rejected": False,
        "asset_processed": True,
    }


def contract_summary() -> dict:
    """The resume-contract view — generated from MANDATORY_CHECKS."""
    return {
        "contract_version": CONTRACT_VERSION,
        "mandatory_checks": list(CHECK_NAMES),
        "finding_for_check": {n: c for n, c in MANDATORY_CHECKS},
        "tolerances": dict(TOLERANCES),
        "required_words": list(REQUIRED_WORDS),
        "required_line_order": list(REQUIRED_LINE_ORDER),
        "proportion_rule": PROPORTION_RULE,
        "counter_letters_minimum": list(COUNTER_LETTERS_MINIMUM),
        "on_pass_classify": ACCEPTED,
        "on_fail_classify": REJECTED,
    }


#: §5 — the emitted handoff files, kept unchanged as reference artifacts
TEMPLATE_CLASSIFICATION = {
    "classification": ["DESIGNER_REFERENCE_TEMPLATE", "PDF_COMPATIBLE",
                       "NOT_AUTHORITATIVE_NATIVE_AI_SOURCE"],
    "designer_may_use_as": "REFERENCE_AND_PLACEMENT_GUIDE",
    "designer_must_edit_it_directly": False,
    "may_be_placed_as": "locked, non-printing reference layer",
    "delete_rename_or_overwrite": False,
    "codes": ["VQ2_HANDOFF_AI_IS_PDF_COMPATIBLE_NOT_NATIVE_LAYERED_AI",
              "VQ2_TEMPLATE_AI_AND_PDF_BYTES_IDENTICAL",
              "VQ2_EXISTING_DESIGNER_OUTPUT_LAYER_NOT_TECHNICALLY_ENFORCEABLE"],
}

#: guard against over-strict rejection (mirrors the condensed-proportion rule)
BINARY_STRUCTURE_RULE = (
    "A valid native designer file must NOT be rejected merely because its "
    "binary structure differs from the ReportLab-emitted template. Only the "
    "recorded provenance facts are judged: native source, native layer "
    "inventory, required layer names, word placement, reference isolation."
)
