"""Human-review manifest logic (DIP-0B5).

Turns per-unit B1–B4 findings into a scalable, unit-centred review manifest:
one primary row per DesignUnitCandidate, batch metadata so 80 review-required
units are not 80 unrelated tasks, a priority tier, an include/exclude
recommendation, and colour ambiguity aggregated to the unit (never 24,609
path-level rows).

Pure functions over already-computed unit dicts — no PDF access — so the review
policy is testable in isolation. Machine inference is read, never written; the
human block is emitted blank and a reviewer's later edits never touch machine
fields.
"""
from __future__ import annotations

import hashlib
import json

MANIFEST_VERSION = "b5-manifest-1"

PRIORITIES = ("HIGH", "MEDIUM", "LOW", "OPTIONAL")
RECOMMENDATIONS = ("RECOMMEND_INCLUDE", "RECOMMEND_EXCLUDE", "REVIEW_REQUIRED")

# Unit types that are historical *reference* material but not surface artwork.
EXCLUDE_TYPES = {"SPEC_TABLE", "TECHNICAL_NOTES", "BARCODE", "LEGAL_TEXT",
                 "DIELINE_CANDIDATE"}
INCLUDE_TYPES = {"SURFACE_ARTWORK", "PRODUCT_PHOTO"}
# Everything else (MOCKUP, COLOR_PALETTE_STRIP, ALTERNATE_VERSION,
# REFERENCE_MATERIAL, UNKNOWN, MOCKUP) defaults to REVIEW_REQUIRED.

# The blank human block. A reviewer fills these; machine code never does.
HUMAN_FIELDS = (
    "reviewer", "reviewed_at", "review_version", "product_category",
    "sku_product_code", "design_year_era", "market", "language", "region_role",
    "primary_artwork_confirmed", "dieline_confirmed", "front_back_side_role",
    "style_tags", "palette_confirmed", "typography_character",
    "decoration_density_confirmed", "layout_quality_rating", "approval_status",
    "include_in_historical_memory", "disposition", "correction_reason", "notes",
)


def blank_human_block() -> dict:
    return {k: None for k in HUMAN_FIELDS} | {"style_tags": [], "notes": ""}


# --- density bands ----------------------------------------------------------

def density_band(value: float, lo: float, hi: float) -> str:
    return "low" if value < lo else "high" if value > hi else "medium"


def typography_density_band(unit: dict) -> str:
    n = unit["typography"]["candidate_count"]
    return "none" if n == 0 else "sparse" if n <= 2 else "moderate" if n <= 6 else "dense"


def decoration_density_band(unit: dict) -> str:
    d = unit["descriptors"]["decoration_density_paths_per_cm2"]
    return density_band(d, 5.0, 40.0)


# --- ambiguity aggregation (decision 3) -------------------------------------

def aggregate_ambiguity(unit: dict) -> dict:
    """Unit-level colour ambiguity. Never exposes path-level records."""
    amb = unit.get("_colour", {})
    dominant = unit["palette"]["artwork"]["dominant"]
    dom_ambiguous = bool(dominant and (dominant[0].get("spot_match") or {}).get("ambiguous"))
    return {
        "ambiguous_colour_count": amb.get("ambiguous_colours", 0),
        "ambiguous_path_count": amb.get("ambiguous_paths", 0),
        "near_black_ambiguity_count": amb.get("flagged_black_paths", 0),
        "dominant_ambiguous_families": amb.get("dominant_ambiguous_families", []),
        "ambiguity_affects_dominant_palette": dom_ambiguous,
        "human_review_required": bool(dom_ambiguous
                                      or amb.get("flagged_black_paths", 0) > 0),
    }


def colour_class_counts(unit: dict) -> dict:
    """Keep the six colour states distinct (decision 3): an unattributed process
    colour is valid colour information, NOT a failed spot match."""
    c = unit.get("_colour", {})
    return {
        "named_ink_matched": c.get("named_ink_matched", 0),
        "named_ink_ambiguous": c.get("named_ink_ambiguous", 0),
        "present_but_unattributed": c.get("unattributed", 0),
        "technical_colour": unit["palette"].get("technical_excluded", 0),
        "raster_only_colour": c.get("raster_colours", 0),
        "unresolved_or_ambiguous": unit["palette"].get("unresolved_or_ambiguous", 0),
    }


# --- include / exclude recommendation (decision 6) --------------------------

def include_recommendation(unit: dict) -> tuple[str, list[str]]:
    t = unit["candidate_type"]
    reasons = []
    mixed = bool(unit.get("_dieline_overlaps") and t in INCLUDE_TYPES)
    if mixed:
        reasons.append("mixed artwork/dieline region")
        return "REVIEW_REQUIRED", reasons
    if t in INCLUDE_TYPES:
        reasons.append(f"{t} is primary surface artwork / product imagery")
        if not unit["palette"]["artwork"]["dominant"]:
            reasons.append("but has no dominant artwork colour")
            return "REVIEW_REQUIRED", reasons
        return "RECOMMEND_INCLUDE", reasons
    if t in EXCLUDE_TYPES:
        reasons.append(f"{t} is technical/non-artwork reference material")
        return "RECOMMEND_EXCLUDE", reasons
    reasons.append(f"{t} is not clearly artwork or technical")
    return "REVIEW_REQUIRED", reasons


# --- review priority (decision 5) -------------------------------------------

def review_priority(unit: dict) -> tuple[str, list[str]]:
    t = unit["candidate_type"]
    seg = unit.get("_segmentation_status")
    dieline = unit.get("_dieline_outcome")
    amb = aggregate_ambiguity(unit)
    has_dominant = bool(unit["palette"]["artwork"]["dominant"])

    high, medium, low = [], [], []
    if seg == "MANUAL_REQUIRED":
        high.append("segmentation MANUAL_REQUIRED")
    if dieline == "BORDERLINE_REVIEW_REQUIRED":
        high.append("dieline BORDERLINE_REVIEW_REQUIRED")
    if amb["ambiguity_affects_dominant_palette"]:
        high.append("dominant palette materially affected by ambiguity")
    if t in INCLUDE_TYPES and not has_dominant:
        high.append("artwork unit with no dominant colour")
    if unit.get("_dieline_overlaps") and t in INCLUDE_TYPES:
        high.append("mixed artwork/dieline region")
    if t == "UNKNOWN":
        high.append("candidate classification is UNKNOWN")
    if unit.get("_off_canvas") and unit.get("_proposed_for_inclusion"):
        high.append("off-canvas candidate proposed for inclusion")

    if colour_class_counts(unit)["present_but_unattributed"] > 0:
        medium.append("unnamed process colours present")
    if 0 < unit["typography"]["candidate_count"] and t not in (
            "TECHNICAL_NOTES", "LEGAL_TEXT"):
        medium.append("uncertain text-like geometry")
    if unit.get("_alternate_version"):
        medium.append("alternate-version relationship")

    if t in ("SPEC_TABLE", "TECHNICAL_NOTES", "BARCODE", "LEGAL_TEXT"):
        low.append("recommended for exclusion — light-touch confirmation")

    if high:
        return "HIGH", high
    if medium:
        return "MEDIUM", medium
    if t in EXCLUDE_TYPES:
        return "OPTIONAL", (low or ["exclusion candidate"])
    return "LOW", (low or ["high-confidence unit, minor metadata gaps only"])


# --- machine review reasons -------------------------------------------------

def machine_review_reasons(unit: dict) -> list[str]:
    r = []
    if not unit["palette"]["artwork"]["dominant"]:
        r.append("no_dominant_artwork_colour")
    if aggregate_ambiguity(unit)["ambiguity_affects_dominant_palette"]:
        r.append("dominant_palette_ambiguous")
    if unit.get("_segmentation_status") == "MANUAL_REQUIRED":
        r.append("segmentation_manual_required")
    if unit.get("_dieline_outcome") == "BORDERLINE_REVIEW_REQUIRED":
        r.append("dieline_borderline")
    if unit["candidate_type"] == "UNKNOWN":
        r.append("unclassified")
    return r


# --- row + batch ------------------------------------------------------------

def build_row(unit: dict) -> dict:
    rec, rec_reasons = include_recommendation(unit)
    prio, prio_reasons = review_priority(unit)
    d = unit["descriptors"]
    typo = unit["typography"]
    art = unit["palette"]["artwork"]

    return {
        "file": unit["file"], "page": unit["page"], "unit_id": unit["unit_id"],
        "preview_crop": unit.get("_preview_crop"),
        "candidate_type": unit["candidate_type"],
        "candidate_confidence": unit.get("_candidate_confidence"),
        "segmentation_status": unit.get("_segmentation_status"),
        "primary_or_off_canvas": "off_canvas" if unit.get("_off_canvas") else "primary",
        "vector_count": unit.get("_vector_count", 0),
        "raster_count": unit.get("_raster_count", 0),
        "likely_dieline_outcome": unit.get("_dieline_outcome"),
        "dieline_score": unit.get("_dieline_score"),
        "dominant_artwork_colours": [c["srgb_255"] for c in art["dominant"]],
        "supporting_artwork_colours": [c["srgb_255"] for c in art["supporting"]],
        "colour_classes": colour_class_counts(unit),
        "colour_ambiguity": aggregate_ambiguity(unit),
        "flagged_near_black_artwork": unit.get("_colour", {}).get("flagged_black_paths", 0),
        "text_like_geometry_summary": {
            "candidate_count": typo["candidate_count"],
            "all_typography_outlined": typo["all_typography_outlined"],
            "level_b": "unavailable",
        },
        "hierarchy_summary": d["hierarchy_zones"],
        "alignment_summary": [r["alignment"] for r in
                              typo["text_like_geometry_candidates"][:3]],
        "decoration_density_paths_per_cm2": d["decoration_density_paths_per_cm2"],
        "whitespace_ratio": d["whitespace_ratio"],
        "symmetry_score": d["symmetry_score_vertical_axis"],
        "image_vector_balance": d["image_vector_balance"],
        "machine_review_reasons": machine_review_reasons(unit),
        "include_in_historical_memory_recommendation": rec,
        "recommendation_reasons": rec_reasons,
        "review_priority": prio,
        "review_priority_reasons": prio_reasons,
        "confidence": unit.get("_candidate_confidence"),
        "provenance": unit.get("_provenance", {}),
        # blank human block — never machine-written; a reviewer fills it and the
        # machine fields above are never overwritten.
        "human": blank_human_block(),
    }


def batch_key(row: dict) -> dict:
    """Grouping metadata (decision 2). A batch is a review convenience only; a
    human decision is never auto-applied across it."""
    dom = row["dominant_artwork_colours"][0] if row["dominant_artwork_colours"] else None
    return {
        "source_file": row["file"],
        "candidate_type": row["candidate_type"],
        "segmentation_status": row["segmentation_status"],
        "dieline_outcome": row["likely_dieline_outcome"],
        "typography_density_band": row["_typo_band"],
        "decoration_density_band": row["_deco_band"],
        "shared_dominant_colour": dom,
        "priority": row["review_priority"],
    }


def build_batches(rows: list[dict]) -> dict:
    """Group review-required rows by shared reason. Deterministic."""
    groups: dict[str, dict] = {}
    for row in rows:
        if row["review_priority"] == "LOW":
            continue
        for dim in ("candidate_type", "segmentation_status", "likely_dieline_outcome"):
            val = row.get(dim)
            if val is None:
                continue
            gid = f"{dim}={val}"
            g = groups.setdefault(gid, {
                "group_id": gid, "dimension": dim, "value": val,
                "unit_ids": [], "priorities": set()})
            g["unit_ids"].append(row["unit_id"])
            g["priorities"].add(row["review_priority"])

    out = []
    for g in sorted(groups.values(), key=lambda x: (-len(x["unit_ids"]), x["group_id"])):
        prio = ("HIGH" if "HIGH" in g["priorities"]
                else "MEDIUM" if "MEDIUM" in g["priorities"] else "OPTIONAL")
        out.append({
            "group_id": g["group_id"], "dimension": g["dimension"],
            "shared_value": g["value"], "units": len(g["unit_ids"]),
            "unit_ids": sorted(g["unit_ids"]), "review_priority": prio,
            "shared_reason": f"all units share {g['dimension']} = {g['value']}",
            "recommended_batch_action": _batch_action(g["dimension"], g["value"]),
        })
    return {
        "total_groups": len(out),
        "note": ("a batch is a review convenience only; a human decision is "
                 "never applied automatically across a batch"),
        "groups": out,
    }


def _batch_action(dimension: str, value) -> str:
    if dimension == "candidate_type" and value in EXCLUDE_TYPES:
        return "confirm exclusion for the batch, unit by unit"
    if dimension == "candidate_type" and value in INCLUDE_TYPES:
        return "confirm inclusion + capture SKU/era/market per unit"
    if dimension == "segmentation_status" and value == "MANUAL_REQUIRED":
        return "manually split/merge each unit's regions"
    if dimension == "likely_dieline_outcome" and value == "BORDERLINE_REVIEW_REQUIRED":
        return "confirm or reject the dieline, then reclassify lines"
    return "review each unit; shared context only"


def fingerprint(rows: list[dict]) -> str:
    blob = json.dumps([{k: r[k] for k in ("unit_id", "candidate_type",
                                          "review_priority",
                                          "include_in_historical_memory_recommendation")}
                       for r in rows], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
