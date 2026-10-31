"""Attachment comparison overlay (Phase 2A-9-CORR-2 §3).

Makes the major-flap panel attachment visually unambiguous — three flats
side by side, with the flaps color-coded and labelled:

    left    REFERENCE attachment schematic (drawn from the attachment
            map's stated facts — a schematic, never a trace of the
            Pacdora screenshot)
    middle  REJECTED archetype (both tucks on the first main panel) —
            tucks marked red
    right   CORRECTED opposing archetype (top tuck MAIN A, bottom tuck
            MAIN B) — tucks marked green

Dust flaps (blue), glue flap (grey), entry slits (amber) and fold
direction arrows are drawn on every flat.
"""
from __future__ import annotations

_TUCK_BAD = "#D04040"
_TUCK_GOOD = "#207040"
_DUST = "#3060C0"
_GLUE = "#BBBBBB"
_SLIT = "#C08000"


def _draw_flat(draw, coords, ox, oy, scale, tuck_color, title, subtitle,
               tuck_labels):
    def T(p):
        return (ox + p[0] * scale, oy + p[1] * scale)

    def poly(polygon, outline, fill=None, width=2):
        pts = [T(p) for p in polygon.exterior.coords]
        if fill:
            draw.polygon(pts, fill=fill, outline=outline)
        else:
            draw.line(pts, fill=outline, width=width)

    # flap fills first, then the cut contour on top
    poly(coords.glue_tab_polygon, "#888888", fill=_GLUE)
    for dust_poly in coords.dust_flap_polygons:
        poly(dust_poly, _DUST, fill="#D5E0F5")
    for tuck_poly in coords.tuck_flap_polygons:
        poly(tuck_poly, tuck_color,
             fill="#F5D5D5" if tuck_color == _TUCK_BAD else "#D5EAD5")
    poly(coords.cut_polygon, "#333333", width=2)
    for (x1, y1, x2, y2) in coords.fold_lines:
        draw.line([T((x1, y1)), T((x2, y2))], fill="#CC3333", width=1)
    for (x1, y1, x2, y2) in coords.slit_lines:
        draw.line([T((x1, y1)), T((x2, y2))], fill=_SLIT, width=3)

    for panel in coords.panels:
        cx, cy = panel.center
        name = {"back": "MAIN A", "front": "MAIN B",
                "main_a": "MAIN A", "main_b": "MAIN B",
                "side_left": "SIDE A", "side_right": "SIDE B",
                "side_a": "SIDE A", "side_b": "SIDE B",
                "glue_tab": "GLUE"}.get(panel.name, panel.name)
        x, y = T((cx, cy))
        draw.text((x - 4 * len(name), y), name, fill="#555555")

    for (polygon, text) in zip(coords.tuck_flap_polygons, tuck_labels):
        cx, cy = polygon.centroid.coords[0]
        x, y = T((cx, cy))
        draw.text((x - 4 * len(text), y - 6), text, fill=tuck_color)
        # fold-direction arrow toward the body
        bx, by = coords.body_polygon.centroid.coords[0]
        ax, ay = T((cx, cy))
        tx, ty = T((cx + (bx - cx) * 0.25, cy + (by - cy) * 0.25))
        draw.line([(ax, ay + 10), (tx, ty)], fill=tuck_color, width=2)

    for dust_poly in coords.dust_flap_polygons[:2]:
        cx, cy = dust_poly.centroid.coords[0]
        x, y = T((cx, cy))
        draw.text((x - 16, y), "DUST", fill=_DUST)

    draw.text((ox, oy - 44), title, fill="black")
    draw.text((ox, oy - 26), subtitle,
              fill=_TUCK_BAD if tuck_color == _TUCK_BAD else "#207040")


def _reference_schematic(draw, amap, ox, oy, scale):
    """Schematic of the reference attachment (stated facts, no tracing)."""
    widths = [12, 90, 32, 90, 32]
    names = ["GLUE", "MAIN A", "SIDE A", "MAIN B", "SIDE B"]
    body_h = 92 * scale
    x = ox
    for width, name in zip(widths, names):
        w = width * scale
        draw.rectangle([x, oy, x + w, oy + body_h], outline="#333333",
                       fill="#F7F2EA")
        draw.text((x + w / 2 - 4 * len(name), oy + body_h / 2), name,
                  fill="#555555")
        x += w
    # upper tuck on MAIN A, lower tuck on MAIN B (with closure faces)
    ax0 = ox + 12 * scale
    ax1 = ax0 + 90 * scale
    draw.rectangle([ax0, oy - 50 * scale, ax1, oy], outline=_TUCK_GOOD,
                   fill="#D5EAD5")
    draw.text((ax0 + 12, oy - 25 * scale), "UPPER TUCK <- MAIN A",
              fill=_TUCK_GOOD)
    bx0 = ax1 + 32 * scale
    bx1 = bx0 + 90 * scale
    draw.rectangle([bx0, oy + body_h, bx1, oy + body_h + 50 * scale],
                   outline=_TUCK_GOOD, fill="#D5EAD5")
    draw.text((bx0 + 12, oy + body_h + 25 * scale),
              "LOWER TUCK <- MAIN B", fill=_TUCK_GOOD)
    for (sx0, w) in ((ax1, 32), (bx1, 32)):
        for (top, ymin, ymax) in ((True, oy - 25 * scale, oy),
                                  (False, oy + body_h,
                                   oy + body_h + 25 * scale)):
            draw.rectangle([sx0 + 3, ymin, sx0 + w * scale - 3, ymax],
                           outline=_DUST, fill="#D5E0F5")
    draw.text((ox + 60, oy + body_h + 46 * scale),
              "dust flaps: both SIDE panels, top and bottom", fill=_DUST)
    draw.text((ox, oy - 66 * scale if scale > 1 else oy - 78),
              "REFERENCE ATTACHMENT (schematic from the attachment map — "
              "not a trace)", fill="black")


def export_attachment_overlay(rejected_coords, corrected_coords,
                              attachment_map: dict, out_path: str
                              ) -> str | None:
    """Render the three-way attachment comparison PNG."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    scale = 2.1
    flat_w = max(rejected_coords.flat_width_mm,
                 corrected_coords.flat_width_mm) * scale
    flat_h = max(rejected_coords.flat_height_mm,
                 corrected_coords.flat_height_mm) * scale
    col = int(flat_w + 60)
    img = Image.new("RGB", (col * 3 + 40, int(flat_h + 260)), "white")
    draw = ImageDraw.Draw(img)

    _reference_schematic(draw, attachment_map, 40, 150, scale)
    _draw_flat(draw, rejected_coords, col + 40, 120, scale, _TUCK_BAD,
               "REJECTED — ecma_a20_20_01_01_ste_carton/0.1",
               "both major tucks on the FIRST main panel — "
               "PROVISIONAL_CLOSURE_TOPOLOGY_MISMATCH",
               ["TUCK <- MAIN A (rejected)", "TUCK <- MAIN A (rejected)"])
    _draw_flat(draw, corrected_coords, col * 2 + 40, 120, scale,
               _TUCK_GOOD,
               "CORRECTED — reference_opposed_tuck_carton/0.1",
               "OPPOSING: top tuck MAIN A, bottom tuck MAIN B "
               "(matches the reference attachment map)",
               ["TOP TUCK <- MAIN A", "BOTTOM TUCK <- MAIN B"])

    draw.text((40, 20),
              "MAJOR-FLAP ATTACHMENT COMPARISON — reference map vs "
              "rejected vs corrected", fill="black")
    draw.text((40, 44),
              "amber = entry slits · blue = dust flaps (side panels) · "
              "red/green = major tucks · grey = glue flap · red dashes = "
              "creases · arrows = fold direction", fill="#555555")
    draw.text((40, int(flat_h + 230)),
              "PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED — NOT "
              "APPROVED FOR MASS PRODUCTION", fill="#B03030")
    img.save(out_path)
    return out_path


__all__ = ["export_attachment_overlay"]
