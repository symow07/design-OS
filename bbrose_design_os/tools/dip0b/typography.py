"""Level-A typography from outlined-glyph geometry (DIP-0B4).

Measured across the whole pilot: **0 live text spans, 0 embedded fonts**. All
typography is outlined. Level B — exact wording, language, font family, precise
type style — is therefore unavailable without OCR, and DIP-0B uses no OCR.

Glyph-scale geometry may equally be icons, ornaments, motifs or decorative
linework, so a detected cluster is a `TEXT_LIKE_GEOMETRY_CANDIDATE`, never a
"text region", and the largest one is a "primary typography candidate position",
never a "product-name position". Font-family identity is never inferred from
visual resemblance.
"""
from __future__ import annotations

from . import config as C

CANDIDATE_LABEL = "TEXT_LIKE_GEOMETRY_CANDIDATE"

LINE_OVERLAP_FRAC = 0.4        # vertical overlap that makes two glyphs one line
MIN_GLYPHS_PER_LINE = 2
ALIGN_TOL_FRAC = 0.02          # of region width
CAPS_CV_MAX = 0.18             # coefficient of variation of glyph heights


def _group_lines(glyphs: list[dict]) -> list[list[dict]]:
    """Group glyph-scale fills into apparent lines by vertical overlap."""
    rows: list[list[dict]] = []
    for g in sorted(glyphs, key=lambda m: (m["rect"][1], m["rect"][0])):
        gy0, gy1 = g["rect"][1], g["rect"][3]
        gh = max(gy1 - gy0, 1e-6)
        placed = False
        for row in rows:
            ry0 = min(m["rect"][1] for m in row)
            ry1 = max(m["rect"][3] for m in row)
            overlap = min(gy1, ry1) - max(gy0, ry0)
            if overlap > LINE_OVERLAP_FRAC * min(gh, ry1 - ry0):
                row.append(g)
                placed = True
                break
        if not placed:
            rows.append([g])
    return [r for r in rows if len(r) >= MIN_GLYPHS_PER_LINE]


def _cv(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean <= 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return (var ** 0.5) / mean


def analyse_region(glyphs: list[dict], unit_bbox: list[float]) -> dict | None:
    """Level-A descriptors of one text-like geometry cluster."""
    if len(glyphs) < MIN_GLYPHS_PER_LINE:
        return None
    xs0 = min(m["rect"][0] for m in glyphs)
    ys0 = min(m["rect"][1] for m in glyphs)
    xs1 = max(m["rect"][2] for m in glyphs)
    ys1 = max(m["rect"][3] for m in glyphs)
    rw = max(xs1 - xs0, 1e-6)
    rh = max(ys1 - ys0, 1e-6)

    lines = _group_lines(glyphs)
    if not lines:
        return None

    heights = []
    lefts, rights, centres, tops = [], [], [], []
    for row in lines:
        hs = [m["rect"][3] - m["rect"][1] for m in row]
        heights.append(sorted(hs)[len(hs) // 2])          # median cap-height proxy
        lefts.append(min(m["rect"][0] for m in row))
        rights.append(max(m["rect"][2] for m in row))
        centres.append((lefts[-1] + rights[-1]) / 2)
        tops.append(min(m["rect"][1] for m in row))

    tol = ALIGN_TOL_FRAC * rw
    spread = {"left": max(lefts) - min(lefts),
              "right": max(rights) - min(rights),
              "centre": max(centres) - min(centres)}
    alignment = min(spread, key=spread.get) if len(lines) > 1 else "single_line"
    if len(lines) > 1 and spread[alignment] > tol * 4:
        alignment = "irregular"

    gaps = [tops[i + 1] - tops[i] for i in range(len(tops) - 1)]
    ink = sum(m["area"] for m in glyphs)

    # Uniform glyph heights *look* like all-caps; it is an appearance, not a fact.
    caps_cv = _cv([m["rect"][3] - m["rect"][1] for m in glyphs])

    ux0, uy0, ux1, uy1 = unit_bbox
    uw = max(ux1 - ux0, 1e-6)
    uh = max(uy1 - uy0, 1e-6)

    return {
        "candidate_label": CANDIDATE_LABEL,
        "tier": C.TIER_HEURISTIC,
        "bbox_pt": [round(xs0, 2), round(ys0, 2), round(xs1, 2), round(ys1, 2)],
        "glyph_scale_fills": len(glyphs),
        "apparent_line_count": len(lines),
        "relative_type_scale": [round(h, 2) for h in heights],
        "largest_apparent_scale_pt": round(max(heights), 2),
        "alignment": alignment,
        "line_spacing_pt": (round(sorted(gaps)[len(gaps) // 2], 2) if gaps else None),
        "capitalisation_appearance": ("uniform_height_appears_all_caps"
                                      if caps_cv <= CAPS_CV_MAX
                                      else "mixed_height_appears_mixed_case"),
        "capitalisation_cv": round(caps_cv, 3),
        "text_density": round(min(1.0, ink / (rw * rh)), 4),
        "placement_in_unit": [round(((xs0 + xs1) / 2 - ux0) / uw, 3),
                              round(((ys0 + ys1) / 2 - uy0) / uh, 3)],
        "caveat": ("glyph-scale geometry may be outlined type OR icons, ornaments, "
                   "motifs or decorative linework; nothing here asserts it is text"),
    }


def level_b_unavailable() -> dict:
    """Level B is recorded explicitly as unavailable — never guessed."""
    return {
        "exact_wording": {"value": None, "tier": C.TIER_REQUIRES_HUMAN,
                          "status": "unavailable / requires OCR",
                          "confidence": None},
        "language": {"value": None, "tier": C.TIER_REQUIRES_HUMAN,
                     "status": "unavailable / requires OCR or human confirmation",
                     "confidence": None},
        "font_family": {"value": None, "tier": C.TIER_REQUIRES_ILLUSTRATOR,
                        "status": "unavailable",
                        "note": "never inferred from visual resemblance",
                        "confidence": None},
        "precise_type_style": {"value": None, "tier": C.TIER_REQUIRES_HUMAN,
                               "status": "uncertain", "confidence": None},
        "confidence": None,          # not assessed
        "ocr_used": False,
        "future_milestone": ("DIP-0E — Multilingual Text Recognition and "
                             "Typography Enrichment"),
    }


def analyse_unit(unit: dict, members: list[dict], regions: list[list[dict]]) -> dict:
    """Level-A typography for one design unit."""
    analysed = [r for r in (analyse_region(g, unit["bbox_pt"]) for g in regions) if r]
    analysed.sort(key=lambda r: -r["largest_apparent_scale_pt"])
    for rank, r in enumerate(analysed):
        r["hierarchy_rank"] = rank                # 0 = largest apparent scale

    primary = None
    if analysed:
        p = analysed[0]
        primary = {"value": p["placement_in_unit"],
                   "bbox_pt": p["bbox_pt"],
                   "apparent_scale_pt": p["largest_apparent_scale_pt"],
                   "tier": C.TIER_HEURISTIC, "confidence": 0.3,
                   "label": "primary typography candidate position",
                   "caveat": ("largest apparent type scale; not asserted to be a "
                              "product name, and may not be type at all")}

    return {
        "all_typography_outlined": True,
        "live_text_spans": 0,
        "embedded_fonts": 0,
        "text_like_geometry_candidates": analysed,
        "candidate_count": len(analysed),
        "primary_typography_candidate_position": primary,
        "level_b": level_b_unavailable(),
    }
