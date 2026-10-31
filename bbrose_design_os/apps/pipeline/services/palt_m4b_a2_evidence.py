"""PALT-M4B-A2 §9 — focused fit evidence.

Micron-scale fit decisions are not readable in neutral clay, so the
diagnostic views use contrasting technical colours with a fixed key:
tray, pocket cavity, metal pan, powder, adhesive allowance, clearance and
interference each own a colour and never share one.

Every drawing is generated from the same (r, z) profiles the validators
measure, at true proportion with uniform magnification.
"""
from __future__ import annotations

import os
import subprocess
import tempfile

from PIL import Image, ImageDraw

from apps.pipeline.services import palette_clearance_policy as cp
from apps.pipeline.services import palette_pan_profile as pp
from apps.pipeline.services import palette_pocket_datums as pd
from apps.pipeline.services import palette_thickness_analysis as ta
from apps.pipeline.services import palt_m4b_a2 as A2
from apps.pipeline.services.geometry_validation_render import (
    BLENDER, export_obj, pixel_hash)
from apps.pipeline.services.palette_review_fonts import font

SCRIPT = os.path.join(os.path.dirname(__file__), "blender_scripts",
                      "m4b_a_tray_views.py")

PAPER = (250, 249, 246)
INK = (28, 28, 32)
GREY = (110, 110, 118)

# --- the technical key: one colour each, never shared -----------------------
KEY = {
    "tray": (108, 122, 140),
    "pocket_cavity": (232, 236, 241),
    "metal_pan": (38, 96, 156),
    "powder": (120, 74, 52),
    "adhesive": (224, 158, 44),
    "clearance": (44, 150, 92),
    "interference": (198, 48, 42),
    "datum": (140, 60, 160),
}

NOT_AUTH = ("PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED · "
            "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED · "
            "PAN_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED · "
            "PALT_M5: BLOCKED")


def _legend(d, x, y, items, size=24):
    for i, (label, colour) in enumerate(items):
        yy = y + i * 32
        d.rectangle([x, yy, x + 26, yy + 20], fill=colour, outline=INK)
        d.text((x + 36, yy - 2), label, font=font(size), fill=INK)


def _hatch_poly(img, poly, colour, spacing=9):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    layer = Image.new("RGB", img.size, colour)
    hatch = Image.new("L", img.size, 0)
    hd = ImageDraw.Draw(hatch)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    for off in range(int(min(xs) - (max(ys) - min(ys))), int(max(xs)) + 1,
                     spacing):
        hd.line([(off, max(ys)), (off + (max(ys) - min(ys)), min(ys))],
                fill=110, width=1)
    hatch = Image.composite(hatch, Image.new("L", img.size, 0), mask)
    img.paste(layer, (0, 0), hatch)


def _fit_panel(img, d, *, pocket_rings, pan, powder_top, box, r_lo, r_hi,
               z_lo, z_hi, title, subtitle=""):
    """One magnified fit view: tray material, cavity, pan, clearance."""
    x0, y0, x1, y1 = box
    w, h = int(x1 - x0), int(y1 - y0)
    # Everything is drawn into a panel-sized sub-image so it is CLIPPED to
    # the frame. Drawing straight onto the page lets the pan and powder
    # polygons — which start at r=0, far outside the magnified window —
    # run across the whole sheet.
    panel = Image.new("RGB", (w, h), KEY["pocket_cavity"])
    pdraw = ImageDraw.Draw(panel)
    scale = min(w / (r_hi - r_lo), h / (z_hi - z_lo))

    def L(r, z):
        return ((r - r_lo) * scale, h - (z - z_lo) * scale)

    floor_z = pocket_rings[-1][1]
    # adhesive allowance: the 0.15 mm layer between pocket floor and pan
    pdraw.rectangle([L(r_lo, pan[0][1])[0], L(0, pan[0][1])[1],
                     L(pan[0][0], 0)[0], L(0, floor_z)[1]],
                    fill=KEY["adhesive"])
    # pan body, closed back to the axis
    pan_poly = [L(r, z) for r, z in pan]
    pan_poly += [L(r_lo - 1.0, pan[-1][1]), L(r_lo - 1.0, pan[0][1])]
    pdraw.polygon(pan_poly, fill=KEY["metal_pan"])
    if powder_top is not None:
        wall = pp.contract_values()["metal_wall_thickness_mm"]
        floor = pp.contract_values()["metal_floor_thickness_mm"]
        pdraw.polygon([L(r_lo - 1.0, powder_top),
                       L(pan[-1][0] - wall, powder_top),
                       L(pan[-1][0] - wall, pan[0][1] + floor),
                       L(r_lo - 1.0, pan[0][1] + floor)],
                      fill=KEY["powder"])
    # tray material: everything outboard of the pocket profile
    tray_poly = [L(r, z) for r, z in pocket_rings]
    tray_poly += [L(r_hi + 1.0, pocket_rings[-1][1]),
                  L(r_hi + 1.0, pocket_rings[0][1])]
    pdraw.polygon(tray_poly, fill=KEY["tray"])
    _hatch_poly(panel, tray_poly, (150, 162, 178))
    pdraw.line([L(r, z) for r, z in pocket_rings], fill=INK, width=3)

    img.paste(panel, (int(x0), int(y0)))
    d.rectangle([x0, y0, x1, y1], outline=GREY, width=2)
    d.text((x0, y0 - 62), title, font=font(30), fill=INK)
    if subtitle:
        d.text((x0, y0 - 28), subtitle, font=font(23), fill=GREY)

    def P(r, z):
        lx, ly = L(r, z)
        return (x0 + lx, y0 + ly)

    return P, scale


def _clearance_marks(d, P, pocket_rings, pan, measurement):
    z = measurement["min_radial_at_z_mm"]
    pr = cp._radius_at([tuple(p) for p in pocket_rings], z)
    qr = cp._radius_at([tuple(p) for p in pan], z)
    if pr is None or qr is None:
        return
    gap = measurement["min_radial_clearance_mm"]
    col = KEY["clearance"] if gap > 0 else KEY["interference"]
    a, b = P(qr, z), P(pr, z)
    d.line([a, b], fill=col, width=7)
    d.line([(a[0], a[1] - 14), (a[0], a[1] + 14)], fill=col, width=4)
    d.line([(b[0], b[1] - 14), (b[0], b[1] + 14)], fill=col, width=4)
    label = f"{gap:+.4f} mm @ z {z:.3f}"
    d.text((min(a[0], b[0]) - 10, a[1] + 22), label, font=font(26), fill=col)


def strategy_section(name, row, out_dir) -> str:
    """One strategy's fit section, magnified on the seating corner."""
    W, H = 2200, 1500
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 40), f"PALT-M4B-A2 — {name}", font=font(44), fill=INK)
    d.text((60, 96), row["description"], font=font(24), fill=GREY)

    cfg = dict(row["inputs"])
    rings, _, _ = A2.pocket_profile_for(
        cfg["functional_diameter_mm"] or A2.FUNCTIONAL_DIAMETER_MM,
        cfg["floor_fillet_mm"]) if cfg.get("functional_diameter_mm") \
        else (None, None, None)
    if rings is None:
        from apps.pipeline.services.palette_recessed_tray_geometry import (
            _pocket_profile)
        rings, _, _ = _pocket_profile(
            cfg["sharp_wall_diameter_at_deck_mm"] / 2.0, A2.BASE["deck_z_mm"],
            A2.BASE["pocket_floor_z_mm"], A2.BASE["pocket_draft_deg"],
            A2.BASE["rim_fillet_mm"], cfg["floor_fillet_mm"], 5)
    pan = pp.outer_profile(
        outside_diameter=A2.PAN["pan_outside_diameter_mm"],
        depth=A2.PAN["pan_depth_mm"],
        base_corner_radius=cfg["base_corner_radius_mm"],
        z0=A2.PAN["pan_seating_z_mm"])
    meas = cp.measure(rings, pan, z_lo=A2.PAN["pan_seating_z_mm"],
                      z_hi=A2.PAN["pan_top_z_mm"])

    P, _ = _fit_panel(img, d, pocket_rings=rings, pan=pan,
                      powder_top=A2.PAN["pan_top_z_mm"]
                      + A2.PAN["powder_crown_mm"],
                      box=(60, 240, 1340, 1280),
                      r_lo=11.6, r_hi=14.4, z_lo=2.2, z_hi=4.6,
                      title="SEATING CORNER — magnified",
                      subtitle="radius 11.6-14.4 mm, elevation 2.2-4.6 mm, "
                               "uniform scale")
    _clearance_marks(d, P, rings, pan, meas)

    seat = row["seating"]
    rows = [
        ("verdict", row["verdict"],
         KEY["clearance"] if row["valid"] else KEY["interference"]),
        ("min radial clearance", f"{row['min_radial_clearance_mm']:+.4f} mm",
         INK),
        ("min normal clearance", f"{row['min_normal_clearance_mm']:+.4f} mm",
         INK),
        ("governing clearance", f"{row['governing_clearance_mm']:+.4f} mm",
         KEY["clearance"] if row["governing_clearance_mm"] > 0
         else KEY["interference"]),
        ("min vertical clearance",
         f"{row['min_vertical_clearance_mm']:+.4f} mm", INK),
        ("flat seating margin",
         f"{seat['flat_seating_margin_mm']:+.4f} mm",
         KEY["clearance"] if seat["stable"] else KEY["interference"]),
        ("contact mode",
         "FLAT FACE" if seat["stable"] else "RING CONTACT ON FILLET",
         KEY["clearance"] if seat["stable"] else KEY["interference"]),
        ("pan recess", f"{row['pan_recess_mm']:.4f} mm", INK),
        ("deck ligament", f"{row['deck_ligament_mm']:.4f} mm", INK),
        ("pocket wall", f"{row['pocket_wall_thickness_mm']:.4f} mm", INK),
        ("GEOMETRIC clearance",
         str(row["clearance_tiers"][cp.GEOMETRIC]["established"]), INK),
        ("ENGINEERING clearance",
         str(row["clearance_tiers"][cp.ENGINEERING]["established"]), INK),
        ("MANUFACTURING clearance", "NOT_ESTABLISHED", GREY),
    ]
    for i, (k, v, col) in enumerate(rows):
        d.text((1420, 250 + i * 40), k, font=font(26), fill=GREY)
        d.text((1830, 250 + i * 40), v, font=font(26), fill=col)

    _legend(d, 1420, 810, [
        ("tray material", KEY["tray"]), ("pocket cavity", KEY["pocket_cavity"]),
        ("metal pan", KEY["metal_pan"]), ("powder", KEY["powder"]),
        ("adhesive allowance", KEY["adhesive"]),
        ("clearance", KEY["clearance"]),
        ("interference", KEY["interference"])])
    for i, chunk in enumerate(_wrap(
            row["moulding_implications"]["note"], 118)[:2]):
        d.text((60, H - 106 + i * 30), chunk, font=font(23), fill=GREY)
    d.text((60, H - 40), NOT_AUTH, font=font(22), fill=KEY["interference"])
    path = os.path.join(out_dir, f"{_slug(name)}_section.png")
    img.save(path)
    return path


def _slug(name):
    return {"A_FILLET_REDUCTION": "strategy_A",
            "B_POCKET_ENLARGEMENT": "strategy_B",
            "C_ROUNDED_PAN_BASE_0_30": "strategy_C_030",
            "C_ROUNDED_PAN_BASE_0_40": "strategy_C_040",
            "C_ROUNDED_PAN_BASE_0_50": "strategy_C_050"}.get(name, name)


def clearance_overlay(matrix, out_dir) -> str:
    """All configurations on one clearance axis against the tiers."""
    W, H = 2400, 1250
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 40), "PALT-M4B-A2 — PAN / POCKET CLEARANCE OVERLAY",
           font=font(46), fill=INK)
    minimum = matrix["engineering_minimum_radial_mm"]
    worst = matrix["tolerance_stack"]["worst_case_mm"]
    d.text((60, 100), f"GEOMETRIC > 0 · ENGINEERING >= {minimum:.4f} mm "
                      f"(RSS) · worst-case reference {worst:.4f} mm · "
                      "MANUFACTURING NOT_ESTABLISHED",
           font=font(25), fill=GREY)

    rows = matrix["controls"] + matrix["strategies"]
    lo, hi = -0.12, 0.70
    x0, x1 = 620, 2280
    sc = (x1 - x0) / (hi - lo)

    def X(v):
        return x0 + (v - lo) * sc

    d.line([(X(0), 190), (X(0), 190 + len(rows) * 78 + 30)],
           fill=INK, width=3)
    d.text((X(0) - 10, 160), "0", font=font(24), fill=INK)
    for v, lab, col in ((minimum, "ENGINEERING min", KEY["clearance"]),
                        (worst, "worst case", GREY)):
        d.line([(X(v), 190), (X(v), 190 + len(rows) * 78 + 30)],
               fill=col, width=3)
        d.text((X(v) - 60, 160), lab, font=font(23), fill=col)

    for i, r in enumerate(rows):
        y = 230 + i * 78
        g = r["governing_clearance_mm"]
        col = KEY["clearance"] if g >= minimum else (
            KEY["interference"] if g <= 0 else KEY["adhesive"])
        d.text((60, y - 14), r["strategy"], font=font(25), fill=INK)
        d.rectangle([min(X(0), X(g)), y - 12, max(X(0), X(g)), y + 12],
                    fill=col)
        d.text((X(g) + 14 if g > 0 else X(g) - 150, y - 12),
               f"{g:+.4f}", font=font(25), fill=col)
        if not r["seating"]["stable"]:
            d.text((X(hi) - 300, y - 12), "RING CONTACT",
                   font=font(23), fill=KEY["interference"])
    _legend(d, 60, H - 250, [
        ("meets ENGINEERING minimum", KEY["clearance"]),
        ("positive but below minimum", KEY["adhesive"]),
        ("interference", KEY["interference"])])
    d.text((60, H - 40), NOT_AUTH, font=font(22), fill=KEY["interference"])
    path = os.path.join(out_dir, "pan_pocket_clearance_overlay.png")
    img.save(path)
    return path


def pan_edge_profile_comparison(out_dir) -> str:
    W, H = 2200, 1150
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 40), "PALT-M4B-A2 — PAN EDGE PROFILE COMPARISON",
           font=font(46), fill=INK)
    d.text((60, 100), "drawn metal pan base corner — "
                      f"{pp.PAN_EDGE_PROFILE_AUTHORITY} · "
                      f"{pp.PAN_MANUFACTURING_AUTHORITY}",
           font=font(25), fill=GREY)
    r_lo, r_hi, z_lo, z_hi = 12.2, 13.3, 2.5, 3.6
    box = (60, 200, 1500, 1080)
    scale = min((box[2] - box[0]) / (r_hi - r_lo),
                (box[3] - box[1]) / (z_hi - z_lo))
    ox, oy = box[0], box[3]

    def P(r, z):
        return (ox + (r - r_lo) * scale, oy - (z - z_lo) * scale)

    d.rectangle(box, fill=(244, 246, 249), outline=GREY)
    cols = [(0.0, (150, 150, 156)), (0.30, (60, 130, 190)),
            (0.40, KEY["metal_pan"]), (0.50, (18, 60, 110))]
    for br, col in cols:
        prof = pp.outer_profile(
            outside_diameter=A2.PAN["pan_outside_diameter_mm"],
            depth=A2.PAN["pan_depth_mm"], base_corner_radius=br,
            z0=A2.PAN["pan_seating_z_mm"])
        pts = [P(r, z) for r, z in prof if z <= z_hi]
        d.line(pts, fill=col, width=6)
    rings, _, _ = A2.pocket_profile_for(A2.FUNCTIONAL_DIAMETER_MM, 0.6)
    d.line([P(r, z) for r, z in rings if z <= z_hi], fill=KEY["tray"],
           width=6)
    _legend(d, 1560, 240,
            [(f"base radius {br} mm", c) for br, c in cols]
            + [("pocket wall (0.6 fillet)", KEY["tray"])])
    d.text((1560, 460), "the sharp profile's flat base overhangs the",
           font=font(24), fill=GREY)
    d.text((1560, 492), "flat pocket floor; a radius pulls it inboard",
           font=font(24), fill=GREY)
    d.text((60, H - 40), NOT_AUTH, font=font(22), fill=KEY["interference"])
    path = os.path.join(out_dir, "pan_edge_profile_comparison.png")
    img.save(path)
    return path


def pocket_datum_diagram(tray, datums, out_dir) -> str:
    W, H = 2400, 1400
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 40), "PALT-M4B-A2 — POCKET DATUM DIAGRAM", font=font(46),
           fill=INK)
    d.text((60, 100), "every pocket dimension has a named datum, an "
                      "elevation and a fit/visual flag — 26.6 and 26.8 were "
                      "never the same measurement", font=font(25), fill=GREY)
    rings = tray["pocket_profile_rings"]
    r_lo, r_hi = 11.5, 15.6
    z_lo, z_hi = 2.2, 7.6
    box = (60, 210, 1180, 1210)
    scale = min((box[2] - box[0]) / (r_hi - r_lo),
                (box[3] - box[1]) / (z_hi - z_lo))
    ox, oy = box[0], box[3]

    def P(r, z):
        return (ox + (r - r_lo) * scale, oy - (z - z_lo) * scale)

    d.rectangle(box, fill=KEY["pocket_cavity"], outline=GREY)
    poly = [P(r, z) for r, z in rings] + [P(r_hi, rings[-1][1]),
                                          P(r_hi, rings[0][1])]
    d.polygon(poly, fill=KEY["tray"])
    _hatch_poly(img, poly, (150, 162, 178))
    d.line([P(r, z) for r, z in rings], fill=INK, width=4)

    marks = [
        ("POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM", rings[0][0],
         tray["elevations_mm"]["deck"], True),
        ("POCKET_SHARP_WALL_THEORETICAL_DIAMETER_AT_DECK",
         tray["pockets"][0]["sharp_corner_radius_mm"],
         tray["elevations_mm"]["deck"], False),
        ("POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM",
         pd.profile_radius(rings, A2.PAN["pan_seating_z_mm"]),
         A2.PAN["pan_seating_z_mm"], False),
        ("POCKET_DIAMETER_AT_FLOOR_FILLET_TANGENT",
         tray["pockets"][0]["flat_floor_radius_mm"],
         tray["pockets"][0]["wall_bottom_z_mm"], False),
    ]
    for i, (name, r, z, dashed) in enumerate(marks):
        y = P(r, z)[1]
        d.line([(box[0], y), (box[2] + 30, y)], fill=KEY["datum"], width=2)
        d.ellipse([P(r, z)[0] - 7, y - 7, P(r, z)[0] + 7, y + 7],
                  fill=KEY["datum"])
    for i, (name, row) in enumerate(datums["datums"].items()):
        y = 240 + i * 132
        col = KEY["datum"] if row["controls_fit"] else GREY
        d.text((1250, y), name, font=font(25), fill=col)
        d.text((1250, y + 34), f"{row['value_mm']:.4f} mm  @ z "
                               f"{row['z_datum_mm']}  ·  "
                               f"{row['measurement_direction']}",
               font=font(24), fill=INK)
        tag = ("CONTROLS FIT" if row["controls_fit"]
               else ("VISUAL ONLY" if row["visual_only"] else "CONSTRUCTION"))
        d.text((1250, y + 66), f"{tag}  ·  {row['authority']}",
               font=font(22), fill=col)
    d.text((60, H - 40), NOT_AUTH, font=font(22), fill=KEY["interference"])
    path = os.path.join(out_dir, "pocket_datum_diagram.png")
    img.save(path)
    return path


def thickness_map(thick, out_dir, *, sink=False) -> str:
    W, H = 2200, 1250
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    title = "SINK / WARPAGE RISK MAP" if sink else "SECTION THICKNESS MAP"
    d.text((60, 40), f"PALT-M4B-A2 — {title}", font=font(46), fill=INK)
    d.text((60, 100),
           f"{thick['MOULDING_SINK_RISK']} · {thick['evidence_basis']} · "
           f"ratio {thick['thickness_ratio']}:1 against a "
           f"{thick['ratio_limit']}:1 limit", font=font(25), fill=GREY)
    nominal = thick["policy"]["nominal_wall_mm"]
    threshold = nominal * thick["policy"]["sink_threshold_ratio_vs_nominal"]
    items = sorted(thick["regions"].items(),
                   key=lambda kv: -kv[1]["thickness_mm"])
    x0, x1 = 760, 2100
    mx = max(v["thickness_mm"] for _, v in items)
    for i, (name, row) in enumerate(items):
        y = 200 + i * 92
        t = row["thickness_mm"]
        excluded = row["kind"] not in ("WALL", "SOLID_LAND")
        if sink:
            col = (KEY["interference"] if t > threshold
                   else KEY["clearance"])
        else:
            col = GREY if excluded else (
                KEY["interference"] if t > threshold else KEY["clearance"])
        d.text((60, y - 12), name, font=font(26), fill=INK)
        d.text((60, y + 20), row["kind"] + ("  (context only)" if excluded
                                            else ""),
               font=font(21), fill=GREY)
        w = (x1 - x0) * t / mx
        d.rectangle([x0, y - 14, x0 + w, y + 22], fill=col)
        d.text((x0 + w + 16, y - 8), f"{t:.3f} mm", font=font(26), fill=col)
    d.line([(x0 + (x1 - x0) * threshold / mx, 180),
            (x0 + (x1 - x0) * threshold / mx, 180 + len(items) * 92)],
           fill=INK, width=3)
    d.text((x0 + (x1 - x0) * threshold / mx - 90, 150),
           f"sink threshold {threshold} mm", font=font(23), fill=INK)
    _legend(d, 60, H - 210, [
        ("above sink threshold", KEY["interference"]),
        ("at or below threshold", KEY["clearance"]),
        ("context only, excluded from ratio", GREY)])
    d.text((60, H - 40), thick["claim_limit"][:150], font=font(22),
           fill=GREY)
    path = os.path.join(out_dir,
                        "sink_risk_map.png" if sink else "thickness_map.png")
    img.save(path)
    return path


def annotated_selected_section(row, selection, out_dir) -> str:
    W, H = 2400, 1500
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.text((60, 40), "PALT-M4B-A2 — SELECTED STRATEGY, ANNOTATED SECTION",
           font=font(44), fill=INK)
    d.text((60, 96), f"{selection['selected']} · "
                     f"base corner radius "
                     f"{selection['base_corner_radius_mm']} mm · "
                     f"{selection['PAN_EDGE_PROFILE_AUTHORITY']}",
           font=font(26), fill=KEY["metal_pan"])
    rings, _, _ = A2.pocket_profile_for(
        row["inputs"]["functional_diameter_mm"],
        row["inputs"]["floor_fillet_mm"])
    pan = pp.outer_profile(
        outside_diameter=A2.PAN["pan_outside_diameter_mm"],
        depth=A2.PAN["pan_depth_mm"],
        base_corner_radius=row["inputs"]["base_corner_radius_mm"],
        z0=A2.PAN["pan_seating_z_mm"])
    meas = cp.measure(rings, pan, z_lo=A2.PAN["pan_seating_z_mm"],
                      z_hi=A2.PAN["pan_top_z_mm"])
    P, _ = _fit_panel(img, d, pocket_rings=rings, pan=pan,
                      powder_top=A2.PAN["pan_top_z_mm"]
                      + A2.PAN["powder_crown_mm"],
                      box=(60, 250, 1500, 1300),
                      r_lo=11.4, r_hi=14.6, z_lo=2.2, z_hi=4.8,
                      title="SEATING CORNER — magnified, uniform scale",
                      subtitle="the only region where the pan and the "
                               "moulded fillet can foul")
    _clearance_marks(d, P, rings, pan, meas)
    lines = [
        ("selected by", selection["rule"]),
        ("why a radius at all", selection["why_a_radius_is_required"]),
        ("governing clearance",
         f"{row['governing_clearance_mm']:+.4f} mm  (radial "
         f"{row['min_radial_clearance_mm']:+.4f}, normal "
         f"{row['min_normal_clearance_mm']:+.4f})"),
        ("engineering minimum",
         f"{selection['engineering_minimum_radial_mm']:.4f} mm RSS"),
        ("flat seating margin",
         f"{row['seating']['flat_seating_margin_mm']:+.4f} mm  "
         f"({row['seating']['contact_mode']})"),
        ("pan recess", f"{row['pan_recess_mm']:.4f} mm — preserved"),
        ("MANUFACTURING clearance", "NOT_ESTABLISHED"),
    ]
    y = 260
    for k, v in lines:
        d.text((1560, y), k, font=font(25), fill=GREY)
        y += 34
        for chunk in _wrap(v, 44):
            d.text((1560, y), chunk, font=font(24), fill=INK)
            y += 30
        y += 12
    d.text((60, H - 40), NOT_AUTH, font=font(22), fill=KEY["interference"])
    path = os.path.join(out_dir, "selected_strategy_section_annotated.png")
    img.save(path)
    return path


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out


def selected_neutral_closeup(assembly, out_dir) -> str:
    """The one Blender view — visualisation only, Boolean-free."""
    import json
    obj_dir = os.path.join(out_dir, "_obj")
    os.makedirs(obj_dir, exist_ok=True)
    meshes = {}
    for name, comp in assembly["components"].items():
        path = os.path.join(obj_dir, f"{name}.obj")
        export_obj(comp, path)
        meshes[name] = path
    pitch = assembly["tray"]["spec"]["pitch_mm"]
    out = os.path.join(out_dir, "selected_strategy_neutral_closeup.png")
    cfg = {"meshes": meshes, "mode": "clay", "samples": 64,
           "resolution": [2000, 2000], "ortho_scale": 132.0,
           "centre": [0.0, 0.0, assembly["tray"]["elevations_mm"]["deck"] / 2],
           "camera_distance": 700.0, "smooth_angle_deg": 31.0,
           "detail_views": {"closeup": {"az": 26, "el": 19, "scale": 26.0,
                                        "target": [-pitch, 0.0, 4.4]}},
           "views": {"closeup": out}}
    with tempfile.NamedTemporaryFile("w", suffix=".json",
                                     delete=False) as fh:
        json.dump(cfg, fh)
        cfg_path = fh.name
    proc = subprocess.run(
        [BLENDER, "-b", "--factory-startup", "-noaudio", "-P", SCRIPT,
         "--", cfg_path], capture_output=True, text=True, timeout=3600)
    if "M4B_A_TRAY_VIEWS_OK" not in proc.stdout:
        raise RuntimeError(f"closeup render failed:\n{proc.stdout[-2500:]}")
    return out


def build_evidence(out_dir, *, render=True) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    matrix = A2.resolution_matrix()
    selection = A2.select_strategy(matrix)
    assembly = A2.build_selected(selection)
    section = A2.centre_section(assembly)
    datums = pd.pocket_datums(assembly["tray"], A2.PAN)
    thick = ta.analyse(assembly["tray"])

    paths = []
    for row in matrix["strategies"]:
        paths.append(strategy_section(row["strategy"], row, out_dir))
    paths.append(clearance_overlay(matrix, out_dir))
    paths.append(pan_edge_profile_comparison(out_dir))
    paths.append(pocket_datum_diagram(assembly["tray"], datums, out_dir))
    paths.append(thickness_map(thick, out_dir))
    paths.append(thickness_map(thick, out_dir, sink=True))
    chosen = next(r for r in matrix["strategies"]
                  if r["strategy"] == selection["selected"])
    paths.append(annotated_selected_section(chosen, selection, out_dir))
    if render:
        paths.append(selected_neutral_closeup(assembly, out_dir))

    return {"matrix": matrix, "selection": selection, "assembly": assembly,
            "section": section, "datums": datums, "thickness": thick,
            "paths": [os.path.basename(p) for p in paths],
            "pixel_hashes": {os.path.basename(p): pixel_hash(p)
                             for p in paths},
            "out_dir": out_dir}
