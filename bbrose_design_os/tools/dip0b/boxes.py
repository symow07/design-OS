"""Page boxes, unit conversion, and off-canvas geometry (safeguard 4).

The ArtBox is the primary design surface; MediaBox/CropBox/TrimBox/BleedBox are
all preserved. Geometry outside the ArtBox is recorded separately — counted and
bounded — never discarded.

Coordinates: MuPDF hands us a top-left origin with y increasing downward, in
points. Raw PDF box arrays are bottom-left origin, y up. We convert once, here,
into the mm / y-down convention the Design Graph already speaks.
"""
from __future__ import annotations

import re

PT_PER_MM = 72.0 / 25.4

BOX_NAMES = ("MediaBox", "CropBox", "ArtBox", "TrimBox", "BleedBox")


def pt_to_mm(v: float) -> float:
    return v * 25.4 / 72.0


def rect_pt_to_mm(r) -> list[float]:
    return [round(pt_to_mm(v), 3) for v in (r[0], r[1], r[2], r[3])]


def pdf_box_to_ydown(arr: list[float], page_height_pt: float) -> list[float]:
    """[llx, lly, urx, ury] (y-up, bottom-left) → [x0, y0, x1, y1] (y-down).

    A raw PDF box is expressed in the PDF user space; MuPDF's page rect is
    already flipped. Converting here keeps every downstream consumer in one
    coordinate system.
    """
    llx, lly, urx, ury = arr
    return [round(llx, 3), round(page_height_pt - ury, 3),
            round(urx, 3), round(page_height_pt - lly, 3)]


_NUM = r"[-+]?\d*\.?\d+"


def parse_raw_boxes(raw_page_obj: str) -> dict[str, list[float] | None]:
    """Pull box arrays straight out of the page dictionary source."""
    out: dict[str, list[float] | None] = {}
    for name in BOX_NAMES:
        m = re.search(rf"/{name}\s*\[\s*({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})\s*\]",
                      raw_page_obj)
        out[name] = [float(m.group(i)) for i in range(1, 5)] if m else None
    return out


def build_boxes(page, raw_page_obj: str) -> dict:
    """All five boxes in pt (y-down) and mm, plus the design surface choice."""
    h = page.rect.height
    raw = parse_raw_boxes(raw_page_obj)

    boxes: dict[str, dict] = {}
    for name, arr in raw.items():
        if arr is None:
            boxes[name.lower()] = None
            continue
        pt = pdf_box_to_ydown(arr, h)
        boxes[name.lower()] = {
            "pt": pt,
            "mm": [round(pt_to_mm(v), 3) for v in pt],
            "width_pt": round(pt[2] - pt[0], 3),
            "height_pt": round(pt[3] - pt[1], 3),
            "width_mm": round(pt_to_mm(pt[2] - pt[0]), 2),
            "height_mm": round(pt_to_mm(pt[3] - pt[1]), 2),
        }

    # MuPDF's own rect is authoritative for the visible page.
    r = page.rect
    boxes["page_rect"] = {
        "pt": [round(r.x0, 3), round(r.y0, 3), round(r.x1, 3), round(r.y1, 3)],
        "mm": rect_pt_to_mm([r.x0, r.y0, r.x1, r.y1]),
        "width_pt": round(r.width, 3), "height_pt": round(r.height, 3),
        "width_mm": round(pt_to_mm(r.width), 2),
        "height_mm": round(pt_to_mm(r.height), 2),
    }

    surface = "artbox" if boxes.get("artbox") else "page_rect"
    boxes["design_surface"] = surface
    boxes["design_surface_pt"] = boxes[surface]["pt"]
    boxes["rotation"] = page.rotation
    return boxes


def _rect_of(box_pt: list[float]):
    import fitz
    return fitz.Rect(*box_pt)


def classify_off_canvas(rects, surface_pt: list[float], tol: float = 0.5) -> dict:
    """Count and bound geometry lying outside the design surface.

    Returns counts and the union bounds of off-canvas objects. Nothing is
    dropped: a reviewer may later choose to include off-canvas alternates,
    production notes or assets.
    """
    import fitz

    surface = _rect_of(surface_pt)
    grown = fitz.Rect(surface.x0 - tol, surface.y0 - tol,
                      surface.x1 + tol, surface.y1 + tol)

    fully_outside = 0
    partially_outside = 0
    degenerate = 0
    union = None
    for r in rects:
        rr = fitz.Rect(r)
        if rr.is_infinite:
            continue
        # A hairline rule has zero height and a vertical rule zero width. Both
        # are real geometry: skipping `is_empty` rects silently omitted 95 of
        # ES3083's in-ArtBox rules from the off-canvas accounting entirely.
        if rr.is_empty:
            degenerate += 1
        disjoint = (rr.x1 < grown.x0 or rr.x0 > grown.x1
                    or rr.y1 < grown.y0 or rr.y0 > grown.y1)
        contained = (rr.x0 >= grown.x0 and rr.y0 >= grown.y0
                     and rr.x1 <= grown.x1 and rr.y1 <= grown.y1)
        if disjoint:
            fully_outside += 1
        elif not contained:
            partially_outside += 1
        else:
            continue
        union = fitz.Rect(rr) if union is None else (union | rr)

    return {
        "fully_outside": fully_outside,
        "partially_outside": partially_outside,
        "degenerate_rects_counted": degenerate,
        "total_off_canvas": fully_outside + partially_outside,
        "union_bounds_pt": ([round(v, 2) for v in union] if union else None),
        "union_bounds_mm": ([round(pt_to_mm(v), 2) for v in union] if union else None),
        "surface_pt": [round(v, 2) for v in surface_pt],
        "policy": ("preserved, not discarded; previews and primary statistics are "
                   "clipped to the design surface"),
    }
