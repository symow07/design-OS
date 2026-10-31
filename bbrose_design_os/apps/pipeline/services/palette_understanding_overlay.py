"""PALT-M4C-4 §2 — "WHAT THE ENGINE UNDERSTOOD FROM ES3083", drawn.

This is a SCHEMATIC of the engine's reading, drawn from the confirmed
intent and the built geometry. It is deliberately NOT registered onto the
source photograph: the ES3083 sheet carries no calibrated scale, so an
overlay laid on the image would imply an alignment that cannot be
established. The schematic is presented BESIDE the reference instead, and
says so on its face.

No Image Trace is used, and no raster is vectorised. Every annotated
region comes from a value in the intent or a coordinate in the mesh.

Regions annotated, as the directive lists them: outer silhouette, pan
positions, the 4 x 3 grouping, case margins, hinge region, clasp region,
the lid/base relationship, artwork zones, typography zones, colour zones,
and unresolved geometry.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services.palette_review_fonts import font

SCHEMA = "palette_understanding_overlay/1.0"

PAPER = (250, 249, 246)
INK = (28, 28, 32)
GREY = (122, 122, 130)
SILHOUETTE = (38, 96, 156)
PAN = (44, 150, 92)
GROUPING = (150, 96, 176)
MARGIN = (214, 152, 38)
HINGE = (198, 48, 42)
CLASP = (232, 112, 44)
ARTWORK = (24, 150, 168)
TYPO = (92, 92, 190)
COLOUR = (200, 60, 140)
UNRESOLVED = (150, 150, 156)

LEGEND = (
    ("outer silhouette", SILHOUETTE),
    ("pan positions", PAN),
    ("4 x 3 grouping", GROUPING),
    ("case margins", MARGIN),
    ("hinge region", HINGE),
    ("clasp region", CLASP),
    ("artwork zones", ARTWORK),
    ("typography zones", TYPO),
    ("colour zones", COLOUR),
    ("unresolved geometry", UNRESOLVED),
)


def _dashed(d, box, colour, width=3, dash=14):
    x0, y0, x1, y1 = box
    for x in range(int(x0), int(x1), dash * 2):
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=colour, width=width)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=colour, width=width)
    for y in range(int(y0), int(y1), dash * 2):
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=colour, width=width)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=colour, width=width)


def render_understanding(intent, tray, out_path, *, width=1700) -> str:
    """Draw the schematic. Returns the path written."""
    spec, g = tray["spec"], tray["grid"]
    w_mm, h_mm = spec["tray_width_mm"], spec["tray_depth_mm"]
    pad = 150
    scale = (width - 2 * pad) / w_mm
    body_h = int(h_mm * scale)
    header, legend_h = 250, 40 * len(LEGEND) + 190
    img = Image.new("RGB", (width, header + body_h + 2 * pad + legend_h),
                    PAPER)
    d = ImageDraw.Draw(img)

    d.text((pad, 44), "WHAT THE ENGINE UNDERSTOOD FROM ES3083",
           font=font(46), fill=INK)
    d.text((pad, 104),
           "A schematic of the engine's reading, drawn from the confirmed "
           "intent and the built mesh.", font=font(25), fill=GREY)
    d.text((pad, 140),
           "It is NOT registered onto the source image: that sheet carries "
           "no calibrated scale, so an", font=font(25), fill=GREY)
    d.text((pad, 172), "overlay would imply an alignment that cannot be "
           "established.", font=font(25), fill=GREY)

    ox, oy = pad, header + pad // 2

    def px(x_mm, y_mm):
        return (ox + x_mm * scale, oy + (h_mm - y_mm) * scale)

    # outer silhouette
    d.rounded_rectangle([ox, oy, ox + w_mm * scale, oy + body_h],
                        radius=int(spec["corner_radius_mm"] * scale),
                        outline=SILHOUETTE, width=6)
    d.text((ox + 8, oy - 40),
           f"outer silhouette {w_mm:.2f} x {h_mm:.2f} mm (PROVISIONAL)",
           font=font(24), fill=SILHOUETTE)

    # case margins
    mx = (w_mm - g["columns"] * g["pitch_x_mm"]) / 2.0
    my = (h_mm - g["rows"] * g["pitch_y_mm"]) / 2.0
    _dashed(d, [ox + mx * scale, oy + my * scale,
                ox + (w_mm - mx) * scale, oy + body_h - my * scale], MARGIN)
    d.text((ox + mx * scale + 8, oy + my * scale - 34),
           f"case margins {mx:.3f} / {my:.3f} mm", font=font(22),
           fill=MARGIN)

    # 4 x 3 grouping — row and column bands
    for r in range(g["rows"]):
        cy = (r - (g["rows"] - 1) / 2.0) * g["pitch_y_mm"] + h_mm / 2
        y0, y1 = px(0, cy + g["pitch_y_mm"] / 2)[1], \
            px(0, cy - g["pitch_y_mm"] / 2)[1]
        d.rectangle([ox + mx * scale, y0, ox + (w_mm - mx) * scale, y1],
                    outline=GROUPING, width=2)
    d.text((ox + 8, oy + body_h + 12),
           f"grouping {g['columns']} x {g['rows']} — "
           f"{tray['pocket_count']} pans", font=font(24), fill=GROUPING)

    # pan positions, from the built mesh
    for p in tray["pockets"]:
        cx, cy = p["centre_mm"]
        pw, ph = p["opening_width_mm"], p["opening_height_mm"]
        x0, y0 = px(w_mm / 2 + cx - pw / 2, h_mm / 2 + cy + ph / 2)
        x1, y1 = px(w_mm / 2 + cx + pw / 2, h_mm / 2 + cy - ph / 2)
        d.rounded_rectangle([x0, y0, x1, y1],
                            radius=max(2, int(
                                p["sharp_corner_radius_at_deck_mm"] * scale)),
                            outline=PAN, width=4)

    # hinge and clasp regions — declared, geometry NOT_BUILT
    hinge_box = [ox, oy - 26, ox + w_mm * scale, oy + 16]
    _dashed(d, hinge_box, HINGE)
    d.text((ox + w_mm * scale - 430, oy - 62),
           "hinge region — geometry NOT_BUILT (PALT-M4B-B)",
           font=font(22), fill=HINGE)
    clasp_box = [ox + w_mm * scale / 2 - 90, oy + body_h - 16,
                 ox + w_mm * scale / 2 + 90, oy + body_h + 26]
    _dashed(d, clasp_box, CLASP)
    d.text((ox + w_mm * scale / 2 + 104, oy + body_h - 6),
           "clasp region — NOT_BUILT", font=font(22), fill=CLASP)

    # lid / base relationship
    opening = intent.get("opening_direction")
    d.text((ox + 8, oy + body_h + 46),
           "lid / base: lid hinges "
           f"{(opening.value if opening else 'UNRESOLVED')} from the base; "
           "the base carries this tray. Neither is built yet.",
           font=font(23), fill=GREY)

    # artwork, typography, colour zones
    y = oy + body_h + 86
    for label, colour, field_name in (
            ("artwork zones", ARTWORK, "logo_position"),
            ("typography zones", TYPO, "typography_zones"),
            ("colour zones", COLOUR, "colour_zones")):
        f = intent.get(field_name)
        val = "UNRESOLVED" if f is None else f.value
        d.rectangle([ox, y, ox + 26, y + 20], fill=colour, outline=INK)
        d.text((ox + 38, y - 3), f"{label}: {val}", font=font(23),
               fill=INK)
        y += 34

    # unresolved geometry
    y += 8
    d.text((ox, y), "unresolved geometry:", font=font(24), fill=UNRESOLVED)
    for i, item in enumerate(intent.unresolved_regions[:5]):
        d.text((ox + 30, y + 32 + i * 30), f"— {item}", font=font(21),
               fill=UNRESOLVED)

    # legend, two columns so it never reaches the footer
    ly = y + 32 + 30 * min(5, len(intent.unresolved_regions)) + 46
    d.text((ox, ly - 34), "legend", font=font(24), fill=INK)
    half = (len(LEGEND) + 1) // 2
    for i, (label, colour) in enumerate(LEGEND):
        col, rowi = divmod(i, half)
        xx = ox + col * 460
        yy = ly + rowi * 34
        d.rectangle([xx, yy, xx + 26, yy + 20], fill=colour, outline=INK)
        d.text((xx + 38, yy - 3), label, font=font(22), fill=INK)

    d.text((pad, img.height - 52),
           "PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED · "
           "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED · "
           "no Image Trace used", font=font(21), fill=GREY)
    img.save(out_path)
    return out_path


def annotation_record(intent, tray) -> dict:
    """The same understanding as data, so a reviewer can check the drawing
    against numbers rather than trusting the picture."""
    spec, g = tray["spec"], tray["grid"]
    mx = (spec["tray_width_mm"] - g["columns"] * g["pitch_x_mm"]) / 2.0
    my = (spec["tray_depth_mm"] - g["rows"] * g["pitch_y_mm"]) / 2.0
    def val(name):
        f = intent.get(name)
        return None if f is None or f.confirmation_state == di.REMOVED \
            else f.value
    return {
        "record_type": SCHEMA,
        "registered_onto_source_image": False,
        "why_not_registered": "the ES3083 sheet carries no calibrated "
                              "scale; a registered overlay would imply an "
                              "alignment that cannot be established",
        "image_trace_used": False,
        "outer_silhouette": {"width_mm": spec["tray_width_mm"],
                             "depth_mm": spec["tray_depth_mm"],
                             "corner_radius_mm": spec["corner_radius_mm"],
                             "authority": "PROVISIONAL_DESIGN_DEFAULT"},
        "pan_positions": [{"row": p["row"], "col": p["col"],
                           "centre_mm": p["centre_mm"],
                           "opening_mm": [p["opening_width_mm"],
                                          p["opening_height_mm"]]}
                          for p in tray["pockets"]],
        "grouping": {"columns": g["columns"], "rows": g["rows"],
                     "pan_count": tray["pocket_count"]},
        "case_margins_mm": {"x": round(mx, 6), "y": round(my, 6)},
        "hinge_region": {"declared": True, "geometry_state": "NOT_BUILT",
                         "built_by": "PALT-M4B-B"},
        "clasp_region": {"declared": True, "geometry_state": "NOT_BUILT",
                         "built_by": "PALT-M4B-B"},
        "lid_base_relationship": {
            "opening_direction": val("opening_direction"),
            "geometry_state": "NOT_BUILT"},
        "artwork_zones": val("logo_position"),
        "typography_zones": val("typography_zones"),
        "colour_zones": val("colour_zones"),
        "unresolved_geometry": list(intent.unresolved_regions),
        "owner_approved": False,
    }
