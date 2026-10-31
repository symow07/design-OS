"""Full-canvas previews, clipped to the design surface (safeguard 4).

Previews and primary statistics are ArtBox-clipped; off-canvas geometry is
recorded separately by `boxes.classify_off_canvas` and never discarded.
Render size is bounded by `Limits.max_render_px` / `max_mask_pixels`.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from . import config as C
from .limits import Budget


def render_page(doc, page, page_index: int, rel_path: str, budget: Budget,
                out_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir or C.OUT_PREVIEWS)
    C.assert_output_safe(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    surface = fitz.Rect(*_surface_pt(doc, page))
    clip = surface & page.rect          # never render outside the page
    if clip.is_empty:
        clip = page.rect

    z = budget.render_zoom(clip.width, clip.height)
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=clip, alpha=False)

    stem = Path(rel_path).stem.replace("/", "_")
    name = f"{stem}-p{page_index}.full.png"
    path = out_dir / name
    C.assert_output_safe(path)
    pix.save(path)

    return {
        "path": C.relpath(path),
        "width_px": pix.width, "height_px": pix.height,
        "zoom": round(z, 5),
        "clipped_to": "design_surface",
        "clip_pt": [round(v, 2) for v in clip],
        "bytes": path.stat().st_size,
    }


def _surface_pt(doc, page) -> list[float]:
    from .boxes import build_boxes
    raw = doc.xref_object(page.xref, compressed=False)
    return build_boxes(page, raw)["design_surface_pt"]
