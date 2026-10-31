"""Surface-artwork descriptors (DIP-0B4).

Descriptive historical memory, never templates. These fields describe how a
historical design *behaved*: where its ink sat, how dense its decoration was,
whether it was symmetric. They deliberately do not persist reusable coordinates,
complete panel layouts, exact object-placement recipes, or historical path
geometry — nothing here can be replayed as a layout.

Every value is HEURISTIC and derived from a bounded raster of the unit.
"""
from __future__ import annotations

import fitz
import numpy as np

from . import config as C
from .cluster import area as _area

MASK_LONG_EDGE = 320          # descriptors need shape, not resolution
INK_TOL = 28


def _unit_mask(page, bbox) -> tuple[np.ndarray, float]:
    rect = fitz.Rect(*bbox) & page.rect
    if rect.is_empty:
        return np.zeros((1, 1), dtype=bool), 0.0
    z = min(1.0, MASK_LONG_EDGE / max(rect.width, rect.height, 1.0))
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=rect, alpha=False)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3).astype(np.int16)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    return (np.abs(a - bg).sum(axis=2) > INK_TOL), z


def _symmetry(mask: np.ndarray) -> float:
    if mask.size == 0 or not mask.any():
        return 0.0
    flipped = mask[:, ::-1]
    inter = np.logical_and(mask, flipped).sum()
    union = np.logical_or(mask, flipped).sum()
    return float(inter / union) if union else 0.0


def _border_presence(mask: np.ndarray) -> float:
    """Fraction of ink lying in the outer 12 % ring of the unit."""
    if not mask.any():
        return 0.0
    h, w = mask.shape
    mh, mw = max(1, int(0.12 * h)), max(1, int(0.12 * w))
    ring = mask.copy()
    ring[mh:h - mh, mw:w - mw] = False
    return float(ring.sum() / mask.sum())


def describe_unit(page, unit: dict, members: list[dict],
                  rasters: list[dict]) -> dict:
    """Composition descriptors for one DesignUnitCandidate."""
    bbox = unit["bbox_pt"]
    mask, z = _unit_mask(page, bbox)
    h, w = mask.shape
    ink = int(mask.sum())
    area_px = max(h * w, 1)

    if ink:
        ys, xs = np.nonzero(mask)
        cx, cy = float(xs.mean() / w), float(ys.mean() / h)
        thirds = [float(mask[int(i * h / 3):int((i + 1) * h / 3)].sum() / ink)
                  for i in range(3)]
    else:
        cx = cy = 0.5
        thirds = [0.0, 0.0, 0.0]

    unit_area_pt2 = max(_area(tuple(bbox)), 1e-6)
    raster_area = sum(_area(tuple(r["rect"])) for r in rasters)
    glyphs = [m for m in members if m.get("glyph")]

    # repeated motif: equal-size non-glyph fills recurring
    sizes: dict[tuple[int, int], int] = {}
    for m in members:
        if m["type"] not in ("f", "fs") or m.get("glyph"):
            continue
        bw = round((m["rect"][2] - m["rect"][0]) / 2) * 2
        bh = round((m["rect"][3] - m["rect"][1]) / 2) * 2
        if bw > 0 and bh > 0:
            sizes[(bw, bh)] = sizes.get((bw, bh), 0) + 1
    repeated = max(sizes.values(), default=0)

    aspect = (bbox[2] - bbox[0]) / max(bbox[3] - bbox[1], 1e-6)
    return {
        "tier": C.TIER_HEURISTIC,
        "visual_centre_normalised": [round(cx, 3), round(cy, 3)],
        "whitespace_ratio": round(1.0 - ink / area_px, 4),
        "ink_coverage": round(ink / area_px, 4),
        "hierarchy_zones": {"top": round(thirds[0], 3),
                            "middle": round(thirds[1], 3),
                            "bottom": round(thirds[2], 3)},
        "decoration_density_paths_per_cm2": round(
            len(members) / max(unit_area_pt2 * (25.4 / 72) ** 2 / 100.0, 1e-6), 2),
        "symmetry_score_vertical_axis": round(_symmetry(mask), 3),
        "border_frame_presence": round(_border_presence(mask), 3),
        "repeated_motif_max_recurrence": repeated,
        "image_vector_balance": {
            "raster_area_fraction": round(min(1.0, raster_area / unit_area_pt2), 4),
            "vector_paths": len(members),
            "rasters": len(rasters),
        },
        "glyph_scale_fill_fraction": round(len(glyphs) / max(len(members), 1), 4),
        "composition_direction": ("horizontal" if aspect > 1.3
                                  else "vertical" if aspect < 0.77 else "square"),
        "aspect_ratio": round(aspect, 3),
        "policy": ("descriptive historical memory only — no reusable coordinates, "
                   "panel layouts, placement recipes or path geometry are persisted; "
                   "historical designs are reference memory, not templates"),
    }


def logo_placement_candidate(unit: dict, members: list[dict],
                             rasters: list[dict]) -> dict:
    """Approximate location of the largest non-glyph vector cluster.

    A *candidate*, never a claim: this may equally be an ornament or a motif.
    """
    cands = [m for m in members
             if m["type"] in ("f", "fs") and not m.get("glyph")]
    if not cands:
        return {"value": None, "tier": C.TIER_HEURISTIC,
                "reason": "no non-glyph vector fills in this unit"}
    biggest = max(cands, key=lambda m: m["area"])
    bx = unit["bbox_pt"]
    uw = max(bx[2] - bx[0], 1e-6)
    uh = max(bx[3] - bx[1], 1e-6)
    cx = ((biggest["rect"][0] + biggest["rect"][2]) / 2 - bx[0]) / uw
    cy = ((biggest["rect"][1] + biggest["rect"][3]) / 2 - bx[1]) / uh
    zone_x = "left" if cx < 0.33 else "right" if cx > 0.67 else "centre"
    zone_y = "top" if cy < 0.33 else "bottom" if cy > 0.67 else "middle"
    return {"value": f"{zone_y}-{zone_x}",
            "normalised_centre": [round(cx, 3), round(cy, 3)],
            "area_pt2": round(biggest["area"], 2),
            "tier": C.TIER_HEURISTIC, "confidence": 0.3,
            "reason": ("largest non-glyph vector fill; may equally be an "
                       "ornament, motif or decorative shape")}
