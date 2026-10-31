"""Full-surface artwork placement (2026-07-07).

Real production cartons carry the motif across EVERY surface — sides, tuck
flaps, dust flaps, glue tab — not just the two display faces. This module
decides, for one dieline, which surface gets what:

    front panel        -> "full"    (the approved artwork, text and all)
    back panel         -> "sticker" when regulatory info exists, else "motif"
    other body panels  -> "motif"   (the text-free background variant)
    every flap + tab   -> "motif"

and provides the clipping helpers the raster preview exporter (design_preview.py)
uses and the targets the vector composers read. Flap clipping prefers the
engine's primitive Bézier paths (real curves on tuck shoulders) over the
sampled polygon.

[The clean-up of 2026-10-04 (E2), approved by the owner: no carton is given a
motif any more; ``cover_box`` left with the composer's motif nodes, and the
raster preview exporter that still uses the rest has no caller but its tests.]
"""
from __future__ import annotations

from dataclasses import dataclass

# Flap/tab components that receive the motif. "main-body" is excluded (the
# body is covered per-panel) and "glue-tab" is covered by its panel rect.
_FLAP_PREFIXES = ("top-", "bottom-")


@dataclass(frozen=True)
class Target:
    kind: str                 # "full" | "motif" | "sticker"
    panel: object | None      # Panel (rect) target...
    comp_id: str | None       # ...or component (polygon/path) target


def artwork_targets(coords, panel_info_present: bool) -> list[Target]:
    targets: list[Target] = []
    for p in coords.panels:
        if p.name == "front":
            targets.append(Target("full", p, None))
        elif p.name == "back":
            targets.append(Target("sticker" if panel_info_present else "motif",
                                  p, None))
        else:                                   # side_left, side_right, glue_tab
            targets.append(Target("motif", p, None))
    for comp_id, _poly in coords.components:
        if comp_id.startswith(_FLAP_PREFIXES):
            targets.append(Target("motif", None, comp_id))
    return targets


def component_polygon(coords, comp_id):
    for cid, poly in coords.components:
        if cid == comp_id:
            return poly
    return None


def rl_clip_component(c, coords, comp_id, X, Y) -> bool:
    """Set the reportlab clip to the component outline. True on success.
    Must be called inside c.saveState()/restoreState()."""
    from apps.dielines.geometry.primitives import CubicSeg

    prims = coords.component_paths.get(comp_id)
    path = c.beginPath()
    if prims:
        x0, y0 = prims[0].p0
        path.moveTo(X(x0), Y(y0))
        for seg in prims:
            if isinstance(seg, CubicSeg):
                path.curveTo(X(seg.c1[0]), Y(seg.c1[1]),
                             X(seg.c2[0]), Y(seg.c2[1]),
                             X(seg.p1[0]), Y(seg.p1[1]))
            else:
                path.lineTo(X(seg.p1[0]), Y(seg.p1[1]))
    else:
        poly = component_polygon(coords, comp_id)
        if poly is None:
            return False
        ext = list(poly.exterior.coords)
        path.moveTo(X(ext[0][0]), Y(ext[0][1]))
        for x, y in ext[1:]:
            path.lineTo(X(x), Y(y))
    path.close()
    c.clipPath(path, stroke=0, fill=0)
    return True


def svg_clip_defs(coords, targets) -> str:
    """<clipPath> defs for every target (panel rects + component outlines),
    ids clip-t{index}, in dieline mm coordinates."""
    from apps.dielines.geometry.primitives import path_to_svg_d

    parts = []
    for i, t in enumerate(targets):
        if t.panel is not None:
            p = t.panel
            shape = (f'<rect x="{p.x:.2f}" y="{p.y:.2f}" '
                     f'width="{p.width:.2f}" height="{p.height:.2f}"/>')
        else:
            prims = coords.component_paths.get(t.comp_id)
            if prims:
                shape = f'<path d="{path_to_svg_d(prims)}"/>'
            else:
                poly = component_polygon(coords, t.comp_id)
                if poly is None:
                    continue
                pts = " ".join(f"{x:.2f},{y:.2f}"
                               for x, y in poly.exterior.coords)
                shape = f'<polygon points="{pts}"/>'
        parts.append(f'<clipPath id="clip-t{i}">{shape}</clipPath>')
    return "".join(parts)


def target_bounds(coords, t: Target) -> tuple[float, float, float, float] | None:
    """(x, y, w, h) bounding box of a target in dieline mm space (y-down)."""
    if t.panel is not None:
        p = t.panel
        return p.x, p.y, p.width, p.height
    poly = component_polygon(coords, t.comp_id)
    if poly is None:
        return None
    x0, y0, x1, y1 = poly.bounds
    return x0, y0, x1 - x0, y1 - y0
