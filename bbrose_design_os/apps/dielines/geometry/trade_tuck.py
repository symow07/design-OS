"""Tuck-end folding cartons drawn to the trade's rules — version 1.4 of the straight and the reverse tuck end.

[His second goal of 2026-10-06 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c34a518), item 2: "TOP-TIER DIELINES ... Do
NOT rely on what the system already believes about dielines. If the existing dieline rules, templates or code are wrong
or weaker than the professional standard, replace them".] Every number below is a rule of ``docs/TRADE_RULES.md`` (its
id beside it), researched from the ECMA Code, converters' technical sheets and two licensed professional generators
(Box Blanks, Die Cut Studio) — never a ratio this system measured off one file. Versions 1.0–1.3 (``engine.py``) are
kept, untouched, so a historical job draws as it shipped.

THE STYLES (S1, S2; ECMA p.17, panels numbered from the glue seam):
    straight_tuck_end_carton 1.4 — ECMA A20.20.01.01: both tucks hang from panel 1 (the back).
    reverse_tuck_end_carton  1.4 — ECMA A20.20.03.01: the top tuck from panel 1 (the back), the bottom tuck from
                                   panel 3 (the front) — the opposed layout of the house's approved reference.
    Panel order (S5): glue flap | 1 back (A) | 2 left side (B) | 3 front (A) | 4 right side (B, free edge).

DIMENSIONS (D1–D5, T7): the width W, depth D and height H he confirms are the carton's INSIDE dimensions — what the
product needs. Every crease sits at inside + t (t the board's caliper): panel crease widths A = W + t, B = D + t and
the height between the dust-flap hinges H + t. Inside W × D × H, crease-to-crease (W+t) × (D+t) × (H+t), outside
(W+2t) × (D+2t) × (H+2t).

CONTRACT (x right, y down; origin the flat's top-left):
    x0 = 0                  glue flap free edge
    x1 = G                  crease: glue flap | back
    x2 = x1 + A             crease: back | left side
    x3 = x2 + B             crease: left side | front
    x4 = x3 + A             crease: front | right side
    x5 = x4 + B             right side's free edge (laps over the glue flap)
    y1                      the dust flaps' top hinges (body top)
    y2 = y1 + H + t         the dust flaps' bottom hinges (body bottom)
    off = t                 (T3) a tuck's hinge crease sits one caliper further out than the dust flaps' — the lid
                            closes over their ply and lies flat
    Ld  = B                 (K1, K3) the lid's depth, hinge to tuck fold: it spans the opening and folds over the far
                            wall's top edge
    Tl  = clamp(0.26·Ld, 8, 20)   (K4) the tongue, tuck fold to tip
    lid width = A − t       (T4) inset t/2 from each vertical crease: a t-wide relief slot between neighbouring flaps
    tongue width = lid − 2t (T4) set back t each side; its corners rounded r = min(0.6·Tl, ¼ tongue width) (K5)
    sd  = clamp(0.075·B, 1.25, 3)  (F3) the dust flap's 45° shoulder — straight up sd, in sd
    s   = sd + 1            (K6) the lock slit cut along each end of the tuck fold — the shoulder catches in it
    d   = min(B − t, A/2 − 1)      (F2) the dust flap's depth: never two meeting across the opening, always under the lid
    dust flap: straight on the side of the panel carrying the lid, its shoulder and a taper to a tip 0.21 of its width
               in, on the side of the panel the tongue enters (F3)
    glue flap G (G1–G3): its ends tapered G/3 over its width (≈18°), its crease the body height
    thumb notch (N1): a half round r = clamp(0.18·A, 3.5, 9) in the top edge of the panel the top tongue enters
"""
from __future__ import annotations

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .coordinates import DielineCoordinates, DimensionSet
from .panels import Panel
from .primitives import CubicSeg, LineSeg, sample_path

VERSION = "1.4"
#: (template id) -> (the panel each tuck hangs from, its ECMA code, its words)
STYLES = {
    "straight_tuck_end_carton": {"top": "back", "bottom": "back", "ecma": "A20.20.01.01",
                                 "label": "Straight Tuck End (ECMA A20.20.01.01): both tucks on the back"},
    "reverse_tuck_end_carton": {"top": "back", "bottom": "front", "ecma": "A20.20.03.01",
                                "label": "Reverse Tuck End (ECMA A20.20.03.01): top tuck on the back, bottom on the front"},
}
TONGUE_SHARE = 0.26           # K4: of the lid's depth (Box Blanks; ECMA ≈ 0.25–0.30; the house reference ≈ 0.23)
TONGUE_MIN_MM = 8.0
TONGUE_MAX_MM = 20.0
TONGUE_RADIUS_SHARE = 0.6     # K5: of the tongue's length
SHOULDER_SHARE = 0.075        # F3: of the side panel's crease width (ECMA ≈ 0.07–0.08 B)
SHOULDER_MIN_MM = 1.25
SHOULDER_MAX_MM = 3.0
SLIT_CLEARANCE_MM = 1.0       # K6: the slit runs this much past the shoulder it catches
DUST_COLLISION_MM = 1.0       # F2: each dust flap stops this short of the opening's middle
DUST_TIP_SHARE = 0.21         # F3: the tip's inset on the tongue's side, of the flap's width (Box Blanks)
GLUE_TAPER_SHARE = 1.0 / 3.0  # G3: the end taper, of the glue flap's width (≈18°: Box Blanks 4 over 12; ECMA ≈15°)
GLUE_MIN_MM = 8.0             # G2
GLUE_CLEAR_MM = 3.0           # G2/M4: the glue flap stays this far clear of the next crease
NOTCH_SHARE = 0.18            # N1: the thumb notch's radius, of the panel's width
NOTCH_MIN_MM = 3.5
NOTCH_MAX_MM = 9.0
_K = 0.55228474983            # a cubic's quarter-circle handle


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def is_trade(template: str, version: str | None) -> bool:
    return template in STYLES and version == VERSION


def calculate_trade_tuck(params) -> DielineCoordinates:
    style = STYLES[params.template]
    d_ = params.dimensions
    W, D, H = float(d_.width_mm), float(d_.depth_mm), float(d_.height_mm)
    t = float(params.construction.board_thickness_mm)
    G = float(params.construction.glue_tab_mm)
    bleed = float(params.print_settings.bleed_mm)
    safe = float(params.print_settings.safe_margin_mm)
    notes: list[str] = []

    A, B, Hc = W + t, D + t, H + t                     # crease-to-crease (T7)
    off = t                                           # T3
    Ld = B                                            # K3
    Tl = _clamp(TONGUE_SHARE * Ld, TONGUE_MIN_MM, TONGUE_MAX_MM)
    sd = _clamp(SHOULDER_SHARE * B, SHOULDER_MIN_MM, SHOULDER_MAX_MM)
    s = sd + SLIT_CLEARANCE_MM
    dust = min(B - t, A / 2.0 - DUST_COLLISION_MM)
    glue_max = B - GLUE_CLEAR_MM
    if G > glue_max:
        notes.append("glue flap narrowed from %g mm to %g mm to stay %g mm clear of the crease it laps beside (G2)"
                     % (G, glue_max, GLUE_CLEAR_MM))
        G = glue_max
    if G < GLUE_MIN_MM:
        notes.append("glue flap widened from %g mm to %g mm, the narrowest a folder-gluer holds (G2)" % (G, GLUE_MIN_MM))
        G = GLUE_MIN_MM
    zone = off + Ld + Tl                              # each end's flap zone, from the dust hinge out

    x0, x1 = 0.0, G
    x2 = x1 + A
    x3 = x2 + B
    x4 = x3 + A
    x5 = x4 + B
    y0 = 0.0
    y1 = zone
    y2 = y1 + Hc
    y3 = y2 + zone
    cols = {"back": (x1, x2), "side_left": (x2, x3), "front": (x3, x4), "side_right": (x4, x5)}
    top_panel, bottom_panel = style["top"], style["bottom"]
    entered = {"back": "front", "front": "back"}         # the panel a tongue tucks behind, by the panel carrying it

    # ---- the body: four columns, a tuck's carrier one caliper taller at that end (T3) ----
    def col_top(name):
        return y1 - off if name == top_panel else y1

    def col_bottom(name):
        return y2 + off if name == bottom_panel else y2
    body = unary_union([Polygon([(xl, col_top(n)), (xr, col_top(n)), (xr, col_bottom(n)), (xl, col_bottom(n))])
                        for n, (xl, xr) in cols.items()])
    # N1: the thumb notch, in the top edge of the panel the top tongue enters
    nl, nr = cols[entered[top_panel]]
    notch_r = _clamp(NOTCH_SHARE * A, NOTCH_MIN_MM, NOTCH_MAX_MM)
    notch_cx = (nl + nr) / 2.0
    body = body.difference(Point(notch_cx, y1).buffer(notch_r, quad_segs=16))
    body = Polygon(body.exterior.coords)
    thumb_notch = {"panel": entered[top_panel], "cx": notch_cx, "y": y1, "r": notch_r}

    # ---- the glue flap (G1–G3) ----
    taper = G * GLUE_TAPER_SHARE
    glue = Polygon([(x1, y1), (x0, y1 + taper), (x0, y2 - taper), (x1, y2)])

    # ---- the tucks: lid, tuck fold with its lock slits, tongue (K1–K6, T4) ----
    def tuck(end, panel):
        xl, xr = cols[panel]
        sign = -1.0 if end == "top" else 1.0           # outward from the body
        hinge = (y1 - off) if end == "top" else (y2 + off)
        fold = hinge + sign * Ld
        tip = fold + sign * Tl
        ll, lr = xl + t / 2.0, xr - t / 2.0            # the lid
        a, b = ll + t, lr - t                          # the tongue
        r = min(TONGUE_RADIUS_SHARE * Tl, (b - a) / 4.0)
        k = _K * r
        path = [
            LineSeg((ll, hinge), (ll, fold)),
            LineSeg((ll, fold), (a, fold)),
            LineSeg((a, fold), (a, tip - sign * r)),
            CubicSeg((a, tip - sign * r), (a, tip - sign * (r - k)), (a + r - k, tip), (a + r, tip)),
            LineSeg((a + r, tip), (b - r, tip)),
            CubicSeg((b - r, tip), (b - r + k, tip), (b, tip - sign * (r - k)), (b, tip - sign * r)),
            LineSeg((b, tip - sign * r), (b, fold)),
            LineSeg((b, fold), (lr, fold)),
            LineSeg((lr, fold), (lr, hinge)),
            LineSeg((lr, hinge), (ll, hinge)),
        ]
        poly = Polygon(sample_path(path, cubic_segments=20))
        record = {"end": end, "panel": panel, "enters": entered[panel], "hinge_y": hinge, "fold_y": fold,
                  "tip_y": tip, "x_l": ll, "x_r": lr, "tongue_x_l": a, "tongue_x_r": b, "lid_depth_mm": Ld,
                  "tongue_mm": Tl, "tongue_radius_mm": r, "slit_mm": s, "hinge_offset_mm": off}
        creases = [(ll, hinge, lr, hinge), (ll + s, fold, lr - s, fold)]
        slits = [(a, fold, ll + s, fold), (lr - s, fold, b, fold)]
        return poly, path, record, creases, slits

    # ---- the dust flaps (F1–F4) ----
    def dust_flap(end, side, enters):
        xl, xr = cols[side]
        sign = -1.0 if end == "top" else 1.0
        base = y1 if end == "top" else y2
        tip_y = base + sign * dust
        fl, fr = xl + t / 2.0, xr - t / 2.0
        width = fr - fl
        tip_in = max(sd + 0.5, DUST_TIP_SHARE * width)
        # the shoulder faces the panel the tongue enters: the left side's right edge faces the front, the right
        # side's left edge faces the front; the back is the left side's left and the right side's right (via the glue)
        toward_right = (side == "side_left") == (enters == "front")
        if toward_right:
            pts = [(fl, base), (fr, base), (fr, base + sign * sd), (fr - sd, base + sign * 2 * sd),
                   (fr - tip_in, tip_y), (fl, tip_y)]
        else:
            pts = [(fr, base), (fl, base), (fl, base + sign * sd), (fl + sd, base + sign * 2 * sd),
                   (fl + tip_in, tip_y), (fr, tip_y)]
        record = {"end": end, "panel": side, "x_l": fl, "x_r": fr, "hinge_y": base, "depth_mm": dust,
                  "shoulder_mm": sd, "shoulder_toward": enters, "tip_inset_mm": tip_in}
        return Polygon(pts), record, (fl, base, fr, base)

    tucks, components, component_paths, fold_lines, slit_lines = [], [], {}, [], []
    tuck_polys, dust_polys, dust_records = [], [], []
    for end, panel in (("top", top_panel), ("bottom", bottom_panel)):
        poly, path, record, creases, slits = tuck(end, panel)
        cid = "%s-%s-tuck" % (end, panel)
        components.append((cid, poly))
        component_paths[cid] = path
        tuck_polys.append(poly)
        tucks.append(record)
        fold_lines += creases
        slit_lines += slits
        for side, label in (("side_left", "left"), ("side_right", "right")):
            dpoly, drecord, crease = dust_flap(end, side, entered[panel])
            components.append(("%s-%s-dust" % (end, label), dpoly))
            dust_polys.append(dpoly)
            dust_records.append(drecord)
            fold_lines.append(crease)
    # the body's four upright creases, where the panels either side of them both stand (D1, L3)
    fold_lines = [(x1, y1, x1, y2), (x2, y1, x2, y2), (x3, y1, x3, y2), (x4, y1, x4, y2)] + fold_lines

    cut = unary_union([body, glue] + tuck_polys + dust_polys)
    if cut.geom_type != "Polygon" or not cut.is_valid:
        raise ValueError("the trade tuck's cut outline is not one valid polygon (%s)" % cut.geom_type)
    bleed_polygon = cut.buffer(bleed, join_style=1, quad_segs=16)
    safe_polygon = Polygon([(x1 + safe, y1 + safe), (x5 - safe, y1 + safe), (x5 - safe, y2 - safe),
                            (x1 + safe, y2 - safe)])
    panels = [Panel("glue_tab", x=x0, y=y1, width=G, height=Hc)]
    for name, (xl, xr) in cols.items():
        panels.append(Panel(name, x=xl, y=col_top(name), width=xr - xl, height=col_bottom(name) - col_top(name)))
    ordered = [c for c in components if c[0].startswith("top-")] + [c for c in components if c[0].startswith("bottom-")]
    components = [("main-body", body), ("glue-tab", glue)] + ordered
    if t <= 0:
        notes.append("no board caliper given: creases at the inside dimensions — confirm the board (T7)")
    coords = DielineCoordinates(
        flat_width_mm=round(x5 - x0, 4), flat_height_mm=round(y3 - y0, 4), panels=panels, fold_lines=fold_lines,
        cut_polygon=cut, bleed_polygon=bleed_polygon, safe_polygon=safe_polygon, tuck_flap_polygons=tuck_polys,
        dust_flap_polygons=dust_polys, glue_tab_polygon=glue, body_polygon=body, slit_lines=slit_lines,
        components=components, component_paths=component_paths, stadium_cutouts=[],
        dimensions=DimensionSet(manufacture=(round(A, 4), round(B, 4), round(Hc, 4)), inner=(W, D, H),
                                outer=(round(W + 2 * t, 4), round(D + 2 * t, 4), round(H + 2 * t, 4))),
        board_thickness_mm=t, body_top_y=y1, body_bottom_y=y2,
        derived={
            "structure_type": params.template, "template_version": VERSION, "ecma_code": style["ecma"],
            "style_words": style["label"], "rules": "apps/dielines/docs/TRADE_RULES.md",
            "dimension_semantics": "inside", "crease_mm": [round(A, 4), round(B, 4), round(Hc, 4)],
            "x0": x0, "x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5, "y0": y0, "y1": y1, "y2": y2, "y3": y3,
            "top_tuck_panel": top_panel, "bottom_tuck_panel": bottom_panel, "bottom_mode": "tuck",
            "provisional": False, "per_hinge_creases": True,
            "tucks": tucks, "dust_flaps": dust_records,
            "glue": {"width_mm": G, "taper_mm": taper, "crease": [x1, y1, x1, y2]},
            "thumb_notch": thumb_notch,
            # the shape 1.3's readers know: each tuck fold, its slits and its tongue
            "tuck_folds": [{"tuck": r["end"], "y": r["fold_y"], "x_l": r["x_l"], "x_r": r["x_r"],
                            "slit_mm": r["slit_mm"], "tongue_mm": r["tongue_mm"]} for r in tucks],
            "tuck_flap_height_mm": off + Ld + Tl, "dust_flap_height_mm": dust, "lock_notch_mm": 0.0,
            "slit_width_mm": 0.0, "thickness_compensation": True,
            "grain": "parallel to the height: the four body creases run with the grain (Iggesund; the converter "
                     "confirms, R1–R3)",
            "notes": notes,
        },
    )
    coords.validate()
    return coords
