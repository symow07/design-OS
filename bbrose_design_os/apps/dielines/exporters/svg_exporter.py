"""Print-ready SVG exporter for STE dielines.

The SVG contains four and only four layer groups, in this order:
  - g#bleed        green dashed, offset outline           (#00FF00)
  - g#cut-lines    blue solid, full cut outline           (#0000FF)
  - g#fold-lines   red dashed, 6 crease lines             (#FF0000)
  - g#safe-area    green short-dashed, inward inset       (#00FF00)

Colors follow industry-standard print conventions and are non-negotiable
for print-shop compatibility (see docs/geometry_decisions.md DECISION-006).

No text, no labels, no legend. Designers add typography in Illustrator.
"""
from __future__ import annotations

import os

import svgwrite
from shapely.geometry import Polygon

from ..geometry.coordinates import DielineCoordinates
from ..geometry.primitives import path_to_svg_d


def _polygon_to_d(
    poly: Polygon, dx: float = 0.0, dy: float = 0.0,
    include_interiors: bool = True,
) -> str:
    """Convert a shapely.Polygon to an SVG path `d`, translating by (dx, dy).

    When `include_interiors=False`, only the exterior ring is emitted —
    used for component polygons whose interior holes are drawn separately
    as stadium paths with real SVG `A` (elliptical-arc) commands.
    """
    parts: list[str] = []
    rings = [list(poly.exterior.coords)]
    if include_interiors:
        rings += [list(r.coords) for r in poly.interiors]
    for ring in rings:
        if not ring:
            continue
        x0, y0 = ring[0]
        parts.append(f"M {x0 + dx:.4f} {y0 + dy:.4f}")
        for x, y in ring[1:]:
            parts.append(f"L {x + dx:.4f} {y + dy:.4f}")
        parts.append("Z")
    return " ".join(parts)


def _stadium_to_d(
    cx: float, cy: float, width: float, height: float,
    dx: float = 0.0, dy: float = 0.0,
) -> str:
    """SVG path for a stadium using `A` (elliptical-arc) commands.

    `width` is the total horizontal extent (long axis). The two
    semicircular ends have radius `height / 2`.
    """
    r = height / 2.0
    half = (width - height) / 2.0
    cx += dx
    cy += dy
    x_left  = cx - half
    x_right = cx + half
    y_top    = cy - r
    y_bottom = cy + r
    # Start at top-left of the straight, go right along top, arc down
    # the right end, go left along bottom, arc back up the left end.
    return (
        f"M {x_left:.4f} {y_top:.4f} "
        f"L {x_right:.4f} {y_top:.4f} "
        f"A {r:.4f} {r:.4f} 0 0 1 {x_right:.4f} {y_bottom:.4f} "
        f"L {x_left:.4f} {y_bottom:.4f} "
        f"A {r:.4f} {r:.4f} 0 0 1 {x_left:.4f} {y_top:.4f} Z"
    )


_STROKE = {
    "cut":   0.5,
    "fold":  0.25,
    "bleed": 0.25,
    "safe":  0.25,
}

_PAGE_MARGIN_MM = 1.0

_LAYER_LABELS = {
    "bleed": "Bleed",
    "cut-lines": "Cut Lines",
    "fold-lines": "Fold Lines",
    "safe-area": "Safe Area",
}


def export_svg(coords: DielineCoordinates, job_id: str) -> str:
    # Page/artboard bounds must include the full bleed outline. The cut-line
    # geometry still emits in absolute contract coordinates; only the viewBox
    # is expanded so the green bleed is not clipped by the SVG canvas.
    min_x, min_y, max_x, max_y = coords.bleed_polygon.bounds
    view_x = min_x - _PAGE_MARGIN_MM
    view_y = min_y - _PAGE_MARGIN_MM
    view_w = (max_x - min_x) + 2 * _PAGE_MARGIN_MM
    view_h = (max_y - min_y) + 2 * _PAGE_MARGIN_MM
    dx = dy = 0.0

    dwg = svgwrite.Drawing(
        filename=f"exports/{job_id}.svg",
        size=(f"{view_w:.4f}mm", f"{view_h:.4f}mm"),
        viewBox=f"{view_x:.4f} {view_y:.4f} {view_w:.4f} {view_h:.4f}",
        profile="full",
        debug=False,
    )

    dwg.attribs["xmlns:inkscape"] = "http://www.inkscape.org/namespaces/inkscape"
    dwg.attribs["xmlns:sodipodi"] = "http://sodipodi.sourceforge.net/DTD/sodipodi-0.0.dtd"
    dwg.attribs["xmlns:xlink"] = "http://www.w3.org/1999/xlink"
    dwg.attribs["shape-rendering"] = "crispEdges"

    # --- bleed (green dashed) ---------------------------------------------
    g_bleed = dwg.g(id="bleed", fill="none",
                    stroke="#00FF00", stroke_width=_STROKE["bleed"],
                    stroke_dasharray="3 2")
    g_bleed.attribs["inkscape:label"] = _LAYER_LABELS["bleed"]
    g_bleed.attribs["vector-effect"] = "non-scaling-stroke"
    g_bleed.add(dwg.path(d=_polygon_to_d(coords.bleed_polygon, dx, dy)))
    dwg.add(g_bleed)

    # --- cut lines (blue solid) -------------------------------------------
    g_cut = dwg.g(id="cut-lines", fill="none",
                  stroke="#0000FF", stroke_width=_STROKE["cut"])
    g_cut.attribs["inkscape:label"] = _LAYER_LABELS["cut-lines"]
    g_cut.attribs["vector-effect"] = "non-scaling-stroke"
    # Each carton component as its own closed <path>; interiors (friction
    # slits, lock slot) are drawn separately below with real arc commands
    # for clean prepress geometry.
    for component_id, poly in coords.components:
        primitives = coords.component_paths.get(component_id)
        if primitives:
            d = path_to_svg_d(primitives, dx, dy)
        else:
            d = _polygon_to_d(poly, dx, dy, include_interiors=False)
        g_cut.add(dwg.path(id=component_id, d=d))
    # Stadium cutouts (friction-lock slits + auto-bottom lock slot).
    for slot_id, cx, cy, sw, sh in coords.stadium_cutouts:
        g_cut.add(dwg.path(
            id=slot_id,
            d=_stadium_to_d(cx, cy, sw, sh, dx, dy),
        ))
    dwg.add(g_cut)

    # --- fold (crease) lines (red dashed) ---------------------------------
    g_fold = dwg.g(id="fold-lines", fill="none",
                   stroke="#FF0000", stroke_width=_STROKE["fold"],
                   stroke_dasharray="5 2")
    g_fold.attribs["inkscape:label"] = _LAYER_LABELS["fold-lines"]
    g_fold.attribs["vector-effect"] = "non-scaling-stroke"
    for x1, y1, x2, y2 in coords.fold_lines:
        g_fold.add(dwg.line(start=(x1 + dx, y1 + dy), end=(x2 + dx, y2 + dy)))
    dwg.add(g_fold)

    # --- safe area (green short-dashed) -----------------------------------
    g_safe = dwg.g(id="safe-area", fill="none",
                   stroke="#00FF00", stroke_width=_STROKE["safe"],
                   stroke_dasharray="2 2")
    g_safe.attribs["inkscape:label"] = _LAYER_LABELS["safe-area"]
    g_safe.attribs["vector-effect"] = "non-scaling-stroke"
    g_safe.add(dwg.path(d=_polygon_to_d(coords.safe_polygon, dx, dy)))
    dwg.add(g_safe)

    svg_string = dwg.tostring()

    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"\n'
        '  "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
    )
    full_svg = header + svg_string
    write_svg(full_svg, job_id)
    return full_svg


def write_svg(svg_string: str, job_id: str) -> str:
    path = f"exports/{job_id}.svg"
    os.makedirs("exports", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg_string)
    return path
