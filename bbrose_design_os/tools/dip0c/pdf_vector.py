"""PDF-backed vector audit for `.ai` / `.pdf` (DIP-0C1).

Reuses the DIP-0B PDF machinery. Adds the JPEG-shell detector (a `.ai` that is
mostly an embedded raster) and an axis-A-only technical readiness verdict —
rights are never considered here.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from tools.dip0.provenance import Inferred
from tools.dip0b.boxes import build_boxes, classify_off_canvas, pt_to_mm
from tools.dip0b.inspect import scan_xrefs
from tools.dip0b.limits import Budget
from tools.dip0b.separation import build_separation_table

from . import config as C

PARSER = f"{C.TOOL_NAME}.pdf_vector/{C.TOOL_VERSION}+pymupdf"

JPEG_SHELL_COVERAGE = 0.85       # embedded raster covers >= this of the surface
JPEG_SHELL_MAX_PATHS = 60        # ...with few real vector paths
HIGH_COMPLEXITY_PATHS = 20_000


def _inf(value, tier, source, evidence, confidence):
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(confidence, 3), parser=PARSER).to_dict()
    d["tier"] = tier
    return d


def audit(rel_path: str, budget: Budget) -> dict:
    full = C.physical_path(rel_path, C.REPO_ROOT)
    doc = fitz.open(full)
    try:
        page = doc[0]
        raw = doc.xref_object(page.xref, compressed=False)
        boxes = build_boxes(page, raw)
        surface = boxes["design_surface_pt"]
        surface_area = max((surface[2] - surface[0]) * (surface[3] - surface[1]), 1e-6)

        drawings = [d for d in page.get_drawings(extended=True)
                    if d["type"] in ("f", "s", "fs")]
        clips = [d for d in page.get_drawings(extended=True) if d["type"] == "clip"]
        groups = [d for d in page.get_drawings(extended=True) if d["type"] == "group"]

        images = page.get_images(full=True)
        img_area = 0.0
        for im in images:
            try:
                bb = page.get_image_bbox(im)
                img_area += abs(bb.width * bb.height)
            except Exception:  # noqa: BLE001
                pass
        raster_coverage = min(img_area / surface_area, 5.0)  # can exceed 1 (overlap)

        n = len(drawings)
        jpeg_shell = raster_coverage >= JPEG_SHELL_COVERAGE and n <= JPEG_SHELL_MAX_PATHS

        td = page.get_text("dict")
        spans = sum(len(ln["spans"]) for b in td["blocks"] if b["type"] == 0
                    for ln in b["lines"])
        fonts = doc.get_page_fonts(0)

        scan = scan_xrefs(doc, budget)
        seps = build_separation_table(doc, budget, scan["raw_separations"],
                                      scan["devicen"])
        xobj = scan["xobjects"]
        off = classify_off_canvas([d["rect"] for d in drawings], list(surface))

        editability = _editability(n, raster_coverage, jpeg_shell, len(clips),
                                    len(groups))
        return {
            "format": Path(rel_path).suffix.lower(),
            "parser": PARSER,
            "page_count": doc.page_count,
            "boxes": {"design_surface": boxes["design_surface"],
                      "surface_pt": [round(v, 2) for v in surface],
                      "surface_mm": [round(pt_to_mm(v), 2) for v in surface]},
            "path_count": _inf(n, C.TIER_DIRECT, "get_drawings",
                               [f"{n} f/s/fs paths"], 1.0),
            "clip_count": len(clips), "group_count": len(groups),
            "raster": {
                "image_count": len(images),
                "coverage_fraction": _inf(round(raster_coverage, 3), C.TIER_DIRECT,
                                          "image_bbox_area",
                                          [f"{len(images)} images cover "
                                           f"{raster_coverage:.0%} of surface"], 1.0),
                "jpeg_shell": _inf(jpeg_shell, C.TIER_HEURISTIC, "coverage_vs_paths",
                                   [f"coverage={raster_coverage:.0%}, paths={n}",
                                    "a vector file that is mostly an embedded image"
                                    if jpeg_shell else "vector content dominates"],
                                   0.8 if jpeg_shell else 0.6),
            },
            "live_text_spans": spans,
            "embedded_fonts": len(fonts),
            "separations": {"spot_names": seps["spot_names"],
                            "has_registration": seps["has_registration"],
                            "count": seps["count"]},
            "gradients_masks_transparency": _inf(
                {"shadings": xobj["shadings"], "soft_masks": xobj["smasks"],
                 "transparency_groups": xobj["transparency_groups"],
                 "tiling_patterns": xobj["patterns"]},
                C.TIER_DIRECT, "xref_census",
                [f"{xobj['shadings']} gradients, {xobj['smasks']} soft masks, "
                 f"{xobj['transparency_groups']} transparency groups"], 1.0),
            "off_canvas": _inf(
                {"total": off["total_off_canvas"],
                 "fully_outside": off["fully_outside"],
                 "partially_outside": off["partially_outside"]},
                C.TIER_DIRECT, "off_canvas_geometry",
                [f"{off['total_off_canvas']} paths lie outside the design surface"],
                1.0),
            "ai_private_present": _inf(
                scan["ai"]["objects"] > 0, C.TIER_REQUIRES_ILLUSTRATOR,
                "ai_private_census",
                [f"{scan['ai']['objects']} AI-private objects, "
                 f"{scan['ai']['bytes']} bytes; native semantics unavailable"],
                0.0),
            "editability_score": editability,
            "complexity": _complexity(n, len(clips), len(groups)),
            "technical_readiness": _readiness(jpeg_shell, n, editability["value"]),
            "limits": budget.to_dict(),
        }
    finally:
        doc.close()


def _editability(paths, raster_cov, jpeg_shell, clips, groups):
    """Axis A only. High raster coverage / few paths → low editability."""
    if jpeg_shell:
        return _inf(0.1, C.TIER_HEURISTIC, "jpeg_shell",
                    ["mostly an embedded raster; little editable vector"], 0.8)
    if paths == 0:
        return _inf(0.0, C.TIER_HEURISTIC, "no_paths", ["no vector paths"], 0.7)
    score = max(0.0, min(1.0, 1.0 - raster_cov * 0.5))
    return _inf(round(score, 2), C.TIER_HEURISTIC, "paths_vs_raster",
                [f"{paths} paths, raster coverage {raster_cov:.0%}"], 0.6)


def _complexity(paths, clips, groups):
    band = ("trivial" if paths < 50 else "low" if paths < 500
            else "medium" if paths < 5000
            else "high" if paths < HIGH_COMPLEXITY_PATHS else "extreme")
    return _inf(band, C.TIER_DIRECT, "path_count",
                [f"{paths} paths, {clips} clips, {groups} groups",
                 "operationally heavy to edit" if band in ("high", "extreme")
                 else "tractable"], 1.0)


def _readiness(jpeg_shell, paths, editability):
    """Technical readiness (axis A). Never a rights judgement."""
    if jpeg_shell:
        return _inf(C.READY_NEEDS_VECTOR_RECONSTRUCTION, C.TIER_HEURISTIC,
                    "jpeg_shell", ["vector file is an embedded-raster shell"], 0.75)
    if paths == 0:
        return _inf(C.READY_REFERENCE_ONLY, C.TIER_HEURISTIC, "no_paths",
                    ["no editable vector geometry"], 0.6)
    if editability >= 0.6:
        return _inf(C.readiness_value(C.READY_TECHNICALLY_USABLE_WITH_CAVEATS),
                    C.TIER_HEURISTIC, "editable_vector",
                    ["clean editable vector geometry"], 0.6)
    return _inf(C.READY_NEEDS_CLEANUP, C.TIER_HEURISTIC, "mixed",
                ["editable but raster-heavy or complex"], 0.5)
