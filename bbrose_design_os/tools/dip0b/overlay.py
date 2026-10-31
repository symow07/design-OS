"""Numbered region overlays and candidate crops (DIP-0B2).

Two overlays per page:
  * `*.regions.png`   — the ArtBox surface with numbered primary candidates
  * `*.workspace.png` — the full extent (ArtBox ∪ off-canvas) when workspace
                        candidates exist, so a reviewer can see what lives
                        outside the artboard

Crops are bounded by `Limits.max_crops_per_page`. All output lands outside
`materials/`.
"""
from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from . import config as C
from .cluster import union_bbox
from .limits import Budget

PRIMARY = (214, 69, 65)      # candidate boxes
WORKSPACE = (54, 123, 191)   # off-canvas boxes
ARTBOX = (40, 160, 90)


def _render(page, clip, budget: Budget) -> tuple[Image.Image, float, tuple]:
    z = budget.render_zoom(clip[2] - clip[0], clip[3] - clip[1])
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=fitz.Rect(*clip),
                          alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img, z, clip


def _box(draw, rect, clip, z, color, label, width=3):
    x0 = (rect[0] - clip[0]) * z
    y0 = (rect[1] - clip[1]) * z
    x1 = (rect[2] - clip[0]) * z
    y1 = (rect[3] - clip[1]) * z
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    draw.rectangle([x0, y0, x1, y1], outline=color, width=width)
    if not label:
        return
    # A candidate flush with the clip edge would otherwise produce an inverted
    # label rectangle; place the tag inside the box when there is no room above.
    tw = 7 * len(label) + 8
    tag_h = 15
    ty1 = y0 if y0 - tag_h >= 0 else min(y1, y0 + tag_h)
    ty0 = ty1 - tag_h
    if ty0 < 0:
        ty0, ty1 = 0.0, float(tag_h)
    draw.rectangle([x0, ty0, x0 + tw, ty1], fill=color)
    draw.text((x0 + 4, ty0 + 1), label, fill=(255, 255, 255))


def render_overlays(doc, page, page_index: int, rel_path: str, seg: dict,
                    budget: Budget, out_dir: Path | None = None) -> dict:
    out_dir = Path(out_dir or C.OUT_OVERLAYS)
    C.assert_output_safe(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(rel_path).stem
    surface = tuple(seg["artbox_pt"])
    written = {}

    # --- primary: ArtBox-clipped ------------------------------------------
    clip = tuple(fitz.Rect(*surface) & page.rect)
    img, z, clip = _render(page, clip, budget)
    d = ImageDraw.Draw(img)
    for i, c in enumerate(seg["candidates"]):
        t = c["candidate_type"]["value"]
        _box(d, c["bbox_pt"], clip, z, PRIMARY, f"{i}:{t}")
    p = out_dir / f"{stem}-p{page_index}.regions.png"
    C.assert_output_safe(p)
    img.save(p)
    written["regions"] = {"path": C.relpath(p), "bytes": p.stat().st_size,
                          "candidates_drawn": len(seg["candidates"])}

    # --- workspace: full extent incl. off-canvas ---------------------------
    ws = seg["workspace_candidates"]
    if ws:
        boxes = [surface] + [tuple(c["bbox_pt"]) for c in ws]
        full = union_bbox(boxes, range(len(boxes)))
        full = (full[0] - 10, full[1] - 10, full[2] + 10, full[3] + 10)
        img2, z2, clip2 = _render(page, full, budget)
        d2 = ImageDraw.Draw(img2)
        _box(d2, surface, clip2, z2, ARTBOX, "ArtBox", width=4)
        for i, c in enumerate(ws):
            _box(d2, c["bbox_pt"], clip2, z2, WORKSPACE,
                 f"w{i}:{c['candidate_type']['value']}")
        p2 = out_dir / f"{stem}-p{page_index}.workspace.png"
        C.assert_output_safe(p2)
        img2.save(p2)
        written["workspace"] = {"path": C.relpath(p2), "bytes": p2.stat().st_size,
                                "workspace_candidates_drawn": len(ws)}
    return written


def render_crops(doc, page, page_index: int, rel_path: str, seg: dict,
                 budget: Budget, out_dir: Path | None = None) -> list[dict]:
    out_dir = Path(out_dir or C.OUT_CROPS)
    C.assert_output_safe(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_c = seg["candidates"] + seg["workspace_candidates"]
    capped = budget.sample(all_c, budget.limits.max_crops_per_page,
                           "max_crops_per_page", "crops")
    out = []
    lim = budget.limits
    for c in capped:
        rect = fitz.Rect(*c["bbox_pt"]) & page.rect
        if rect.is_empty:
            continue
        # Crops are review thumbnails. Rendering a page-spanning candidate at
        # preview resolution is what made the pilot run time out (YB-1025 holds
        # 9,630 transparency groups, so every rasterisation is expensive).
        z = min(1.0, lim.max_crop_px / max(rect.width, rect.height, 1.0))
        pix = page.get_pixmap(matrix=fitz.Matrix(z, z), clip=rect, alpha=False)
        p = out_dir / f"{c['unit_id']}.png"
        C.assert_output_safe(p)
        pix.save(p)
        c["preview_crop"] = C.relpath(p)
        out.append({"unit_id": c["unit_id"], "path": C.relpath(p),
                    "bytes": p.stat().st_size})
    return out
