"""The stand family's die templates (owner's part 2, 2026-10-31), on the stand die's own Part and Die: each solved from the
product records and the envelope, never from a picture; each read back through one fold model (stand_fold); its rules in
docs/research/stands/rules (stand_types).

The construction the family shares, from the research (docs/research/stands/SUMMARY.md):
- no glue where a lock can do it: a wall's corner flaps are trapped between the leaves of the next wall, rolled double
  (US10144549, US10159361), and each inner leaf locks through the floor (US11286080);
- every panel's size by FEFCO Rec. 101: crease centres = outside − one caliper; a panel that butts against another stops
  short of its surface by the fit gap, so it can neither bind nor leave more than the owner's 0.5 mm;
- a product stands on a seat and passes an opening above it, so the depth between them, not a tight hole, holds its lean;
- the printed faces wrap their neighbours, so no raw edge faces the shopper."""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Polygon, box

from . import counter_display as cd
from . import stand_fold as sf
from . import stand_types as st
from .counter_display import Die, Part, _rect, _seg

SCHEMA = "stand_template/1"
PART_GAP_MM = 20.0


def _r(value, nd=3):
    return round(float(value), nd) + 0.0


class Rules:
    """The numbers one solve reads, for one board."""

    def __init__(self, board):
        common = st.common()
        self.t = common["boards"][board]["caliper_mm"]
        self.board = board
        value = lambda name: common["rules"][name]["value"]  # noqa: E731
        self.g = value("fit_gap_mm")
        self.play = value("slot_play_mm")
        self.end = value("slot_end_play_mm")
        self.clear = max(value("cut_to_crease_mm"), 2 * self.t)
        self.min_panel = max(value("min_panel_calipers") * self.t, 3.0)
        self.web = max(value("web_calipers") * self.t, 3.0)
        self.clearance = value("clearance_total_mm")
        self.lean = value("max_lean_deg")
        self.tab_w = value("floor_tab_w_mm")
        self.barb = value("barb_overhang_mm")
        self.neck = value("tongue_neck_mm")
        self.head = value("tongue_head_mm")
        self.taper = value("tongue_taper_mm")
        self.flap = value("flap_w_mm")
        self.cap = max(value("cap_calipers") * self.t, 3.0)
        self.tall = value("header_tall_ratio")
        self.brace = value("brace_foot_mm")
        # a slot for two plies (a doubled header's tongues) with a land each side of it
        self.back_cap = 2 * self.t + self.play + 2 * self.clear
        self.hold = math.ceil(self.clearance / math.tan(math.radians(self.lean)))


def face_bar(rules_common, product_h, cap_h):
    """How much of a product's front is seen whole, from its top. The owner's shade rule (part 3, 2026-10-31): at least half of its colour
    window, the body below its cap, as well as the cap itself; never under the older bar of cap + 8 mm."""
    r = rules_common["rules"]
    window = (product_h - cap_h) * r["shade_window_share"]["value"] + sf.FACE_STEP_MM    # read to the millimetre: a step more, so half is truly seen
    if cap_h:
        return min(product_h, cap_h + max(r["face_bar_cap_plus_mm"]["value"], window))
    return min(product_h, max(r["face_bar_min_mm"]["value"], window))


def _pair(span, a, b, r):
    """A pair of tabs at shares ``a`` and ``b`` of a span, or one in the middle if two would touch."""
    if (b - a) * span < r.tab_w + 2 * r.clear:
        return [_r(span * (a + b) / 2)]
    return [_r(span * a), _r(span * b)]


def _tab_slot(part, slot_id, x, y, length, width, on, plies=1):
    """A slot centred on (x, y), its long side along x."""
    part.slots.append({"id": slot_id, "polygon": _rect(x - length / 2, y - width / 2, x + length / 2, y + width / 2),
                       "length_mm": length, "width_mm": width, "on": on, "plies": plies})


def _tab(x0, y0, x1, y1, root):
    return cd._tab(x0, y0, x1, y1, root)


# --- the parts the family shares --------------------------------------------------------------------------------------

def _tray(v, g, r):
    """The tray: floor, the double front and back walls, the side walls with their trapped flaps. Flat frame: the floor's
    corner at the origin, x as the shopper sees it, y from front to back; the board's inner side is local +z."""
    t, gap = r.t, r.g
    fw, fd = g["floor_mm"]
    h_f, h_b, c_f, c_b = g["front_crease_mm"], g["back_crease_mm"], g["front_cap_mm"], g["back_cap_mm"]
    cx0, cx1 = t / 2 + gap, fw - t / 2 - gap
    tray = Part("tray", "TRAY — no glue: walls up, flaps in, rims over, tabs through the floor")
    f_leaf, b_leaf = h_f - t / 2 - gap, h_b - t / 2 - gap
    tab = t + gap                                       # a floor tab stops level with the floor's underside
    y_front_cap, y_front_in = -h_f - c_f, -h_f - c_f - f_leaf
    y_back_top, y_back_cap = fd + h_b, fd + h_b + c_b
    y_back_in = y_back_cap + b_leaf
    y_f0, y_r0 = t + gap, fd - t - gap
    floor = _rect(0, 0, fw, fd)
    tray.faces = [("floor", floor, False),
                  ("front panel", _rect(-t / 2, -h_f, fw + t / 2, 0), True),
                  ("front cap", _rect(cx0, y_front_cap, cx1, -h_f), False),
                  ("front inner", _rect(cx0, y_front_in, cx1, y_front_cap), False),
                  ("back panel", _rect(-t / 2, fd, fw + t / 2, y_back_top), True),
                  ("back cap", _rect(cx0, y_back_top, cx1, y_back_cap), False),
                  ("back inner", _rect(cx0, y_back_cap, cx1, y_back_in), False)]
    top_f, top_b = h_f + t / 2, h_b + t / 2
    # each side wall covers the rims' ends: level along the front rim, a straight rise, then level along the back wall's rim
    y_s0, y_s1 = c_f + t / 2 + gap, fd - c_b - t / 2 - gap
    profile = [(y_f0, top_f), (y_s0, top_f)] + [tuple(point) for point in g.get("side_steps", [])] + [(y_s1, top_b), (y_r0, top_b)]
    tray.faces += [("left side", Polygon([(0, y_f0), (0, y_r0)] + [(-z, y) for y, z in reversed(profile)]), True),
                   ("right side", Polygon([(fw, y_f0)] + [(fw + z, y) for y, z in profile] + [(fw, y_r0)]), True)]
    tray.creases = [("floor / front", _seg(0, 0, fw, 0)), ("floor / back", _seg(0, fd, fw, fd)),
                    ("floor / left", _seg(0, y_f0, 0, y_r0)), ("floor / right", _seg(fw, y_f0, fw, y_r0)),
                    ("front / cap", _seg(cx0, -h_f, cx1, -h_f)), ("front cap / inner", _seg(cx0, y_front_cap, cx1, y_front_cap)),
                    ("back / cap", _seg(cx0, y_back_top, cx1, y_back_top)), ("back cap / inner", _seg(cx0, y_back_cap, cx1, y_back_cap))]
    hinges = [sf.Hinge("front panel", "floor", "floor / front", 90), sf.Hinge("front cap", "front panel", "front / cap", 90),
              sf.Hinge("front inner", "front cap", "front cap / inner", 90), sf.Hinge("back panel", "floor", "floor / back", 90),
              sf.Hinge("back cap", "back panel", "back / cap", 90), sf.Hinge("back inner", "back cap", "back cap / inner", 90),
              sf.Hinge("left side", "floor", "floor / left", 90), sf.Hinge("right side", "floor", "floor / right", 90)]
    # the corner flaps, tapered, between each wall's leaves: clear of the floor and the rim
    w = g["flap_mm"]
    for side, wall, sign, hinge_x in (("left", "left side", -1, 0.0), ("right", "right side", 1, fw)):
        low = t / 2 + gap + r.clear              # the die's corner: room for a knife between flap and panel
        for end, y0, inward, high in (("front", y_f0, -1, h_f - t / 2 - gap), ("back", y_r0, 1, h_b - t / 2 - gap)):
            name = "%s %s flap" % (end, side)
            a, b = hinge_x + sign * low, hinge_x + sign * high
            cut = min(w / 3, (high - low) / 3)
            polygon = Polygon([(a, y0), (b, y0), (b - sign * cut, y0 + inward * w), (a + sign * cut, y0 + inward * w)])
            crease = "%s %s fold" % (end, side)
            tray.faces.append((name, polygon, False))
            tray.creases.append((crease, _seg(a, y0, b, y0)))
            hinges.append(sf.Hinge(name, wall, crease, 90))
    # the inner leaves' tabs, through the floor
    locks = []
    for leaf, y_edge, direction, y_slot, tag in (("front inner", y_front_in, -1, c_f, "front"),
                                                 ("back inner", y_back_in, 1, fd - c_b, "back")):
        for index, x in enumerate(g["leaf_tab_x_mm"], 1):
            name = "%s tab %d" % (tag, index)
            x0, x1 = x - r.tab_w / 2, x + r.tab_w / 2
            polygon = _tab(x0, y_edge - tab, x1, y_edge, "bottom") if direction < 0 else _tab(x0, y_edge, x1, y_edge + tab, "top")
            tray.faces.append((name, polygon, False))
            join = "%s join" % name
            tray.joins.append((join, _seg(x0, y_edge, x1, y_edge)))
            hinges.append(sf.Hinge(name, leaf, join, 0))
            slot = "floor slot %s %d" % (tag, index)
            _tab_slot(tray, slot, x, y_slot, r.tab_w + 2 * r.end, t + r.play, "floor")
            locks.append(sf.Lock("%s wall into the floor %d" % (tag, index), ("tray", name), ("tray", slot), "flush", t))
    # the floor's four corners: the walls' creases and their relief cuts meet there, by construction
    from shapely.geometry import MultiPoint
    tray.corner_relief = MultiPoint([(0, 0), (fw, 0), (0, fd), (fw, fd), (0, y_f0), (fw, y_f0), (0, y_r0), (fw, y_r0)]).buffer(2 * t + gap)
    root = sf.translation(t / 2, t / 2, t / 2)
    joints = [sf.Joint(("tray", "front left flap"), ("tray", "front panel"), "lap", "flap against the front panel"),
              sf.Joint(("tray", "front right flap"), ("tray", "front panel"), "lap", "flap against the front panel"),
              sf.Joint(("tray", "back left flap"), ("tray", "back panel"), "lap", "flap against the back panel"),
              sf.Joint(("tray", "back right flap"), ("tray", "back panel"), "lap", "flap against the back panel"),
              sf.Joint(("tray", "front inner"), ("tray", "floor"), "edge", "inner leaf on the floor"),
              sf.Joint(("tray", "back inner"), ("tray", "floor"), "edge", "inner leaf on the floor"),
              sf.Joint(("tray", "front cap"), ("tray", "left side"), "edge", "rim against the side wall"),
              sf.Joint(("tray", "front cap"), ("tray", "right side"), "edge", "rim against the side wall"),
              sf.Joint(("tray", "back cap"), ("tray", "left side"), "edge", "rim against the side wall"),
              sf.Joint(("tray", "back cap"), ("tray", "right side"), "edge", "rim against the side wall"),
              sf.Joint(("tray", "front inner"), ("tray", "left side"), "edge", "inner leaf against the side wall"),
              sf.Joint(("tray", "back inner"), ("tray", "right side"), "edge", "inner leaf against the side wall")]
    return tray, sf.PartPlan("floor", root, hinges), locks, joints


def _header(v, g, r):
    """The header: two leaves doubled on a half-cut at the top, each with barbed tongues through the slots of the back
    wall's rim. Flat: the fold at y = 0, the shopper's leaf below it, the back leaf above it."""
    t, gap = r.t, r.g
    W, hh = v["width_mm"], g["header_leaf_mm"]
    header = Part("header", "HEADER — fold double; press the tongues through the rim's slots until they click")
    outline = g.get("header_outline")
    front, back = _rect(0, 0, W, hh), _rect(0, -hh, W, 0)
    fold = _seg(0, 0, W, 0)
    if outline and outline.get("shape") != "square":
        back_o, front_o, fold = cd.header_polygons(W, 0.0, hh, hh, outline)
        back = Polygon([(x, y - hh) for x, y in back_o.exterior.coords])
        front = Polygon([(x, y - hh) for x, y in front_o.exterior.coords])
        fold = _seg(fold.coords[0][0], 0, fold.coords[-1][0], 0)
    header.faces = [("header front", front, True), ("header back", back, True)]
    header.half_cuts = [("header fold", fold)]
    hinges = [sf.Hinge("header back", "header front", "header fold", 180, t)]
    n, b, reach = r.neck, r.barb, g["tongue_neck_length_mm"]
    head, taper = r.head, r.taper
    for index, x in enumerate(g["tongue_x_mm"], 1):
        for leaf, sign, tag in (("header front", 1, "front"), ("header back", -1, "back")):
            name = "tongue %s %d" % (tag, index)
            y0 = sign * hh
            ys = [y0, y0 + sign * reach, y0 + sign * (reach + head), y0 + sign * (reach + head + taper)]
            header.faces.append((name, Polygon([(x - n / 2, ys[0]), (x - n / 2, ys[1]), (x - n / 2 - b, ys[1]), (x - n / 2 - b, ys[2]),
                                                (x - n / 2 + 1, ys[3]), (x + n / 2 - 1, ys[3]), (x + n / 2 + b, ys[2]), (x + n / 2 + b, ys[1]),
                                                (x + n / 2, ys[1]), (x + n / 2, ys[0])]), False))
            join = name + " join"
            header.joins.append((join, _seg(x - n / 2, ys[0], x + n / 2, ys[0])))
            hinges.append(sf.Hinge(name, leaf, join, 0))
    y_h = g["header_plane_y_mm"]
    z_top = g["header_top_z_mm"]
    pose = sf.pose((0.0, y_h - t / 2, z_top), (1, 0, 0), (0, 0, -1))
    return header, sf.PartPlan("header front", pose, hinges)


def _stair(name, label, xs_part, r, *, seats_z, y_front, ys_rise, y_end, leg_to, holes=None, rear_slots=None, floor_tab_x=None, rear_feet=None):
    """A strip folded into a stair: a leg down to the floor (its tabs through it), then tread, riser, tread… rising to the
    back, the last tread's tabs through the back wall's inner leaf. ``seats_z``: each tread's mid-plane above the floor's;
    ``ys_rise``: where each riser stands; flat y runs along the strip from the first tread's front edge."""
    t, gap = r.t, r.g
    width = xs_part[1] - xs_part[0]
    part = Part(name, label, hole_shape="square")
    # the stair's print side is up, toward the shopper: on the die, x runs from the stand's right
    x_on_die = lambda x: xs_part[1] - x  # noqa: E731
    leg = seats_z[0] - t / 2 - gap
    flat = 0.0
    hinges = []
    faces = []
    creases = []
    y_at = {}
    y0 = y_front
    previous = None
    for index, z in enumerate(seats_z):
        y1 = ys_rise[index] if index < len(ys_rise) else y_end
        tread = "%s tread %d" % (name, index + 1)
        faces.append((tread, _rect(0, flat, width, flat + (y1 - y0)), False))
        y_at[index] = (flat, y0)
        if previous:
            crease = "%s / %s" % (previous, tread)
            creases.append((crease, _seg(0, flat, width, flat)))
            hinges.append(sf.Hinge(tread, previous, crease, 90))
        flat += y1 - y0
        y0 = y1
        if index + 1 < len(seats_z):
            riser = "%s riser %d" % (name, index + 1)
            rise = seats_z[index + 1] - z
            faces.append((riser, _rect(0, flat, width, flat + rise), False))
            crease = "%s / %s" % (tread, riser)
            creases.append((crease, _seg(0, flat, width, flat)))
            hinges.append(sf.Hinge(riser, tread, crease, -90))
            previous = riser
            flat += rise
    root_face = "%s tread 1" % name
    leg_name = "%s leg" % name
    faces.append((leg_name, _rect(0, -leg, width, 0), False))
    creases.append((leg_name + " fold", _seg(0, 0, width, 0)))
    hinges.append(sf.Hinge(leg_name, root_face, leg_name + " fold", 90))
    part.faces, part.creases = faces, creases
    tab = t + gap
    for index, x in enumerate(floor_tab_x or [], 1):
        tab_name = "%s foot %d" % (name, index)
        x0, x1 = x_on_die(x) - r.tab_w / 2, x_on_die(x) + r.tab_w / 2
        part.faces.append((tab_name, _tab(x0, -leg - tab, x1, -leg, "bottom"), False))
        join = tab_name + " join"
        part.joins.append((join, _seg(x0, -leg, x1, -leg)))
        hinges.append(sf.Hinge(tab_name, leg_name, join, 0))
    last = "%s tread %d" % (name, len(seats_z))
    through = t + gap + r.clear / 2
    for index, x in enumerate(rear_slots or [], 1):
        tab_name = "%s rear tab %d" % (name, index)
        x0, x1 = x_on_die(x) - r.tab_w / 2, x_on_die(x) + r.tab_w / 2
        part.faces.append((tab_name, _tab(x0, flat, x1, flat + through, "top"), False))
        join = tab_name + " join"
        part.joins.append((join, _seg(x0, flat, x1, flat)))
        hinges.append(sf.Hinge(tab_name, last, join, 0))
    if rear_feet:
        # the last tread folds down to the floor: a stair with no inner wall to lock into
        back_leg = seats_z[-1] - t / 2 - gap
        leg2 = "%s rear leg" % name
        part.faces.append((leg2, _rect(0, flat, width, flat + back_leg), False))
        part.creases.append((leg2 + " fold", _seg(0, flat, width, flat)))
        hinges.append(sf.Hinge(leg2, last, leg2 + " fold", 90))
        for index, x in enumerate(rear_feet, 1):
            tab_name = "%s rear foot %d" % (name, index)
            x0, x1 = x_on_die(x) - r.tab_w / 2, x_on_die(x) + r.tab_w / 2
            part.faces.append((tab_name, _tab(x0, flat + back_leg, x1, flat + back_leg + tab, "top"), False))
            join = tab_name + " join"
            part.joins.append((join, _seg(x0, flat + back_leg, x1, flat + back_leg)))
            hinges.append(sf.Hinge(tab_name, leg2, join, 0))
    if holes:
        for hole in holes:
            f, y_world = y_at[hole["row"] - 1]
            y = f + (hole["y_mm"] - y_world)
            x = x_on_die(hole["x_mm"])
            half_w, half_d = hole["w_mm"] / 2, hole["d_mm"] / 2
            part.slots.append({"id": "opening %d" % hole["index"], "kind": "opening",
                               "polygon": _rect(x - half_w, y - half_d, x + half_w, y + half_d)})
    pose = sf.pose((xs_part[1] + t / 2, y_front + t / 2, seats_z[0] + t / 2), (-1, 0, 0), (0, 1, 0))
    return part, sf.PartPlan(root_face, pose, hinges)


def _place(parts, title, board_mm, plan, *, row_width=None):
    """The parts on one sheet, in rows, each with its label."""
    width = row_width or max(part.outline().bounds[2] - part.outline().bounds[0] for part in parts)
    placed, moves = [], {}
    x, row_y, row_bottom = cd.SHEET_MARGIN_MM, cd.SHEET_MARGIN_MM + cd.LABEL_MM + 4, 0.0
    for part in parts:
        minx, miny, maxx, maxy = part.outline().bounds
        if x > cd.SHEET_MARGIN_MM and x + maxx - minx > cd.SHEET_MARGIN_MM + width:
            x, row_y = cd.SHEET_MARGIN_MM, row_bottom + PART_GAP_MM + cd.LABEL_MM + 4
        moved = part.moved(x - minx, row_y - miny)
        moves[part.name] = (x - minx, row_y - miny)
        placed.append(moved)
        row_bottom = max(row_bottom, moved.outline().bounds[3])
        x = moved.outline().bounds[2] + PART_GAP_MM
    bounds = [part.outline().bounds for part in placed]
    sheet_w = math.ceil(max(b[2] for b in bounds) + cd.SHEET_MARGIN_MM)
    sheet_h = math.ceil(max(b[3] for b in bounds) + cd.SHEET_MARGIN_MM + 20)
    labels = [(part.label, (part.outline().bounds[0], part.outline().bounds[1] - cd.DIE_BLEED_MM - 3), cd.LABEL_MM) for part in placed]
    die = Die(placed, sheet_w, sheet_h, labels, (cd.SHEET_MARGIN_MM, sheet_h - 18.0, 50.0), title)
    die.moves, die.board_mm, die.plan = moves, board_mm, plan
    die.glue = []
    # the board the shopper sees that is not a design face: its print side carries the flat ground
    die.ground_faces = [(part.name, name) for part in placed for name, _f, printed in part.faces
                        if not printed and any(word in name for word in ("cap", "inner", "tread", "riser", "leg", "deck", "liner")) and " tab " not in name]
    return die


# --- template 1: the counter tray with a header ------------------------------------------------------------------------

def _tray_geometry(v, rows, columns, r, *, rise, back_z, front_h):
    """Template 1's numbers from the envelope. Every length is the rule's; the checks read the die drawn from them."""
    t, gap = r.t, r.g
    W, D = v["width_mm"], v["depth_mm"]
    fw, fd = W - t, D - t
    c_f, c_b = r.cap, r.back_cap
    o = v["product_width_mm"] + r.clearance
    o_d = v["product_depth_mm"] + r.clearance
    y_leg = c_f + t + gap                     # the collar's leg against the front inner leaf
    y_rear = fd - c_b - t / 2 - gap           # the last tread against the back inner leaf
    first = y_leg + r.clear + o_d / 2
    last = y_rear - r.web - o_d / 2
    pitch = (last - first) / (rows - 1) if rows > 1 else 0.0
    cw0, cw1 = t / 2 + gap, fw - t / 2 - gap
    x_pitch = (cw1 - cw0) / columns
    xs = [cw0 + x_pitch * (c + .5) for c in range(columns)]
    ys = [first + pitch * i for i in range(rows)] if rows > 1 else [(first + last) / 2]
    hold = r.hold
    seats = [i * rise for i in range(rows)]        # each row's seat, mid-plane above the floor's
    collars = [hold + s for s in seats]            # each row's deck, mid-plane
    b = [(ys[i] + ys[i + 1]) / 2 for i in range(rows - 1)]
    holes = []
    for row, y in enumerate(ys):
        for column, x in enumerate(xs):
            holes.append({"index": row * columns + column + 1, "row": row + 1, "column": column + 1, "x_mm": _r(x), "y_mm": _r(y),
                          "w_mm": _r(o), "d_mm": _r(o_d), "size_mm": _r(max(o, o_d))})
    g = {"floor_mm": [fw, fd], "front_crease_mm": front_h - t, "back_crease_mm": back_z - t, "front_cap_mm": c_f, "back_cap_mm": c_b,
         "flap_mm": min(r.flap, fd / 4), "leaf_tab_x_mm": _pair(fw, .2, .8, r), "seat_tab_x_mm": _pair(fw, .35, .65, r),
         "rear_tab_x_mm": _pair(fw, .25, .75, r), "hold_mm": hold, "rise_mm": rise, "row_pitch_mm": _r(pitch),
         "column_pitch_mm": _r(x_pitch), "y_leg_mm": _r(y_leg), "y_rear_mm": _r(y_rear), "risers_y_mm": [_r(v) for v in b],
         "seats_z_mm": [_r(s) for s in seats], "collars_z_mm": [_r(c) for c in collars], "holes": holes,
         "collar_x_mm": [_r(cw0), _r(cw1)], "opening_mm": [_r(o), _r(o_d)],
         "web_between_openings_mm": _r(pitch - o_d) if rows > 1 else None}
    return g


def _with_header(g, v, r, back_z, header_h):
    t, gap = r.t, r.g
    fd = g["floor_mm"][1]
    g["header_leaf_mm"] = header_h
    g["header_plane_y_mm"] = _r(fd - g["back_cap_mm"] / 2 + t / 2)
    g["header_top_z_mm"] = _r(back_z + gap + header_h)
    g["tongue_neck_length_mm"] = _r(gap + t + .5)
    W = v["width_mm"]
    g["tongue_x_mm"] = [_r(W * .3), _r(W * .7)]
    return g


def build_counter_tray(record):
    g, v = record["geometry"], record["inputs"]
    r = Rules(record["board"]["preset"])
    t, gap = r.t, r.g
    tray, tray_plan, locks, joints = _tray(v, g, r)
    header, header_plan = _header(v, g, r)
    fw, fd = g["floor_mm"]
    h_b, c_b = g["back_crease_mm"], g["back_cap_mm"]
    # the header's slots in the back wall's rim: tray flat x = stand x − caliper/2
    y_back_top = fd + h_b
    y_cap = y_back_top + c_b / 2
    for index, x in enumerate(g["tongue_x_mm"], 1):
        length, width = r.neck + 2 * r.end, 2 * t + r.play
        _tab_slot(tray, "rim slot %d" % index, x - t / 2, y_cap, length, width, "back cap", plies=2)
        locks.append(sf.Lock("header front leaf into the rim %d" % index, ("header", "tongue front %d" % index),
                             ("tray", "rim slot %d" % index), "barbed", r.head))
        locks.append(sf.Lock("header back leaf into the rim %d" % index, ("header", "tongue back %d" % index),
                             ("tray", "rim slot %d" % index), "barbed", r.head))
    parts = [tray, header]
    plans = {"tray": tray_plan, "header": header_plan}
    joints = list(joints) + [sf.Joint(("header", "header front"), ("tray", "back cap"), "edge", "the header's shopper leaf on the rim"),
                             sf.Joint(("header", "header back"), ("tray", "back cap"), "edge", "the header's back leaf on the rim")]
    # the stairs: the collar holds each product's neck, the seat stair carries it
    rows = record["layout"]["rows"]
    x0, x1 = g["collar_x_mm"]
    collars, seats = g["collars_z_mm"], g["seats_z_mm"]
    risers = g["risers_y_mm"]
    y_inner_at = lambda z: y_back_top + c_b + (h_b - z)  # noqa: E731
    collar, collar_plan = _stair("collar", "COLLAR — fold the stair; its rear tabs into the back wall, its feet into the floor",
                                 (x0, x1), r, seats_z=collars, y_front=g["y_leg_mm"], ys_rise=risers, y_end=g["y_rear_mm"], leg_to=0.0,
                                 holes=g["holes"], rear_slots=g["rear_tab_x_mm"], floor_tab_x=g["seat_tab_x_mm"])
    parts.append(collar)
    plans["collar"] = collar_plan
    for index, x in enumerate(g["seat_tab_x_mm"], 1):
        slot = "floor slot collar %d" % index
        _tab_slot(tray, slot, x, g["y_leg_mm"], r.tab_w + 2 * r.end, t + r.play, "floor")
        locks.append(sf.Lock("collar into the floor %d" % index, ("collar", "collar foot %d" % index), ("tray", slot), "flush", t))
    for index, x in enumerate(g["rear_tab_x_mm"], 1):
        slot = "inner slot collar %d" % index
        _tab_slot(tray, slot, x, y_inner_at(collars[-1]), r.tab_w + 2 * r.end, t + r.play, "back inner")
        locks.append(sf.Lock("collar into the back wall %d" % index, ("collar", "collar rear tab %d" % index), ("tray", slot), "through", t))
    joints += [sf.Joint(("collar", "collar leg"), ("tray", "floor"), "edge", "the collar's leg on the floor"),
               sf.Joint(("collar", "collar leg"), ("tray", "front inner"), "lap", "the collar's leg against the front wall"),
               sf.Joint(("collar", "collar tread %d" % rows), ("tray", "back inner"), "edge", "the collar's last deck against the back wall"),
               sf.Joint(("collar", "collar tread 1"), ("tray", "left side"), "edge", "the collar against the side wall"),
               sf.Joint(("collar", "collar tread 1"), ("tray", "right side"), "edge", "the collar against the side wall")]
    if rows > 1:
        y_seat = risers[0] + t + gap
        seat_risers = [y + t + gap for y in risers[1:]]
        seat, seat_plan = _stair("seat", "SEATS — fold the stair; its rear tabs into the back wall, its feet into the floor",
                                 (x0, x1), r, seats_z=seats[1:], y_front=y_seat, ys_rise=seat_risers, y_end=g["y_rear_mm"], leg_to=0.0,
                                 rear_slots=g["rear_tab_x_mm"], floor_tab_x=g["seat_tab_x_mm"])
        parts.append(seat)
        plans["seat"] = seat_plan
        for index, x in enumerate(g["seat_tab_x_mm"], 1):
            slot = "floor slot seat %d" % index
            _tab_slot(tray, slot, x, y_seat, r.tab_w + 2 * r.end, t + r.play, "floor")
            locks.append(sf.Lock("seats into the floor %d" % index, ("seat", "seat foot %d" % index), ("tray", slot), "flush", t))
        for index, x in enumerate(g["rear_tab_x_mm"], 1):
            slot = "inner slot seat %d" % index
            _tab_slot(tray, slot, x, y_inner_at(seats[-1]), r.tab_w + 2 * r.end, t + r.play, "back inner")
            locks.append(sf.Lock("seats into the back wall %d" % index, ("seat", "seat rear tab %d" % index), ("tray", slot), "through", t))
        joints += [sf.Joint(("seat", "seat leg"), ("tray", "floor"), "edge", "the seat stair's leg on the floor"),
                   sf.Joint(("seat", "seat tread %d" % (rows - 1)), ("tray", "back inner"), "edge", "the seat stair against the back wall")]
        if seats[1] > collars[0]:                 # the leg reaches up behind the collar's first riser
            joints.append(sf.Joint(("seat", "seat leg"), ("collar", "collar riser 1"), "lap", "the seat stair's leg behind the collar's riser"))
    products = []
    pw, pd, ph = v["product_width_mm"], v["product_depth_mm"], v["product_height_mm"]
    for hole in g["holes"]:
        row = hole["row"]
        z = t / 2 + seats[row - 1] + t / 2
        frame = sf.translation(hole["x_mm"] + t / 2, hole["y_mm"] + t / 2, z)
        products.append({"index": hole["index"], "row": row, "column": hole["column"], "frame": frame, "w": pw, "d": pd, "h": ph,
                         "cap": v.get("product_cap_mm") or 0.0,
                         "plate": ("collar", "collar tread %d" % row),
                         "seat": ("tray", "floor") if row == 1 else ("seat", "seat tread %d" % (row - 1))})
    brace_plan = None
    if g.get("brace"):
        brace_plan = _add_brace(parts, plans, locks, joints, tray, header, v, g, r)
    plan = sf.Plan(plans, joints, locks, _tray_steps(rows, bool(brace_plan), [p.name for p in parts]), products)
    title = "%s %s — flat die at 100 %%" % (st.label(record["template"]["id"]), record["template"]["version"])
    return _place(parts, title, t, plan, row_width=max(tray.outline().bounds[2] - tray.outline().bounds[0], 420))


def _turn(wanted, y_axis, z_axis, sign=1.0):
    """The hinge angle that turns a child running along ``sign`` × y_axis (each a (y, z) pair in the stand's section) onto ``wanted``."""
    return math.degrees(math.atan2(wanted @ z_axis, wanted @ (sign * y_axis)))


def _add_brace(parts, plans, locks, joints, tray, header, v, g, r):
    """A tall header's back-brace, one strip closing a triangle with the back of the stand: a tab through the header's back leaf, a
    strut out and down, a second strut back in, a tab through the back wall. It covers no art: only its two tabs touch the stand.
    It stands behind the tray's footprint, and the record says so."""
    t, gap = r.t, r.g
    W, D = v["width_mm"], v["depth_mm"]
    bw = g["brace"]["width_mm"]
    x0 = (W - bw) / 2
    z_top, z_low = g["brace"]["top_z_mm"], g["brace"]["low_z_mm"]
    y_top = g["header_plane_y_mm"] + t + gap            # a gap behind the header's back leaf's surface
    y_far = D + g["brace"]["foot_mm"]
    y_low = D + gap
    z_far = (z_top + z_low) / 2
    upper = np.array([y_far - y_top, z_far - z_top])
    lower = np.array([y_low - y_far, z_low - z_far])
    len_upper, len_lower = float(np.linalg.norm(upper)), float(np.linalg.norm(lower))
    y_axis = upper / len_upper
    z_axis = np.array([-y_axis[1], y_axis[0]])           # the strut's inner side, up and back
    into = np.array([-1.0, 0.0])
    theta = _turn(lower / len_lower, y_axis, z_axis)
    a = math.radians(theta)
    y_lower, z_lower = math.cos(a) * y_axis + math.sin(a) * z_axis, -math.sin(a) * y_axis + math.cos(a) * z_axis
    brace = Part("brace", "BACK-BRACE — its top tab into the header, its lower tab into the back wall")
    tab_w = r.tab_w
    x_mid = bw / 2
    y1, y2 = len_upper, len_upper + len_lower
    brace.faces = [("brace upper strut", _rect(0, 0, bw, y1), False), ("brace lower strut", _rect(0, y1, bw, y2), False),
                   ("brace top tab", _tab(x_mid - tab_w / 2, -(t + gap), x_mid + tab_w / 2, 0, "bottom"), False),
                   ("brace low tab", _tab(x_mid - tab_w / 2, y2, x_mid + tab_w / 2, y2 + t + gap + r.clear / 2, "top"), False)]
    brace.creases = [("brace strut fold", _seg(0, y1, bw, y1)), ("brace top fold", _seg(x_mid - tab_w / 2, 0, x_mid + tab_w / 2, 0)),
                     ("brace low fold", _seg(x_mid - tab_w / 2, y2, x_mid + tab_w / 2, y2))]
    hinges = [sf.Hinge("brace lower strut", "brace upper strut", "brace strut fold", theta),
              sf.Hinge("brace low tab", "brace lower strut", "brace low fold", _turn(into, y_lower, z_lower)),
              sf.Hinge("brace top tab", "brace upper strut", "brace top fold", _turn(into, y_axis, z_axis, -1.0))]
    plans["brace"] = sf.PartPlan("brace upper strut", sf.pose((x0, y_top, z_top), (1, 0, 0), (0, y_axis[0], y_axis[1])), hinges)
    parts.append(brace)
    _tab_slot(header, "brace slot", W / 2, -(g["header_top_z_mm"] - z_top), tab_w + 2 * r.end, t + r.play, "header back")
    locks.append(sf.Lock("brace into the header", ("brace", "brace top tab"), (header.name, "brace slot"), "flush", t))
    _tab_slot(tray, "brace wall slot", W / 2 - t / 2, g["floor_mm"][1] + (z_low - t / 2), tab_w + 2 * r.end, t + r.play, "back panel")
    locks.append(sf.Lock("brace into the back wall", ("brace", "brace low tab"), ("tray", "brace wall slot"), "through", t))
    return plans["brace"]


def _tray_steps(rows, braced, names):
    steps = [sf.Step("Lay the tray flat, print side down."),
             sf.Step("Fold the two side walls up, and fold each wall's corner flaps in.",
                     close={"tray": ["left side", "right side", "front left flap", "front right flap", "back left flap", "back right flap"]}),
             sf.Step("Fold the front panel up, over the flaps. Roll its rim in and down, and push its two tabs through the floor.",
                     close={"tray": ["front panel", "front cap", "front inner", "front tab 1", "front tab 2"]}),
             sf.Step("Do the same with the back wall. The flaps are now trapped: no glue.",
                     close={"tray": ["back panel", "back cap", "back inner", "back tab 1", "back tab 2"]})]
    if rows > 1:
        steps.append(sf.Step("Fold the seat stair. Slide its rear tabs into the back wall, then push its feet through the floor.",
                             part="seat", approach=(0.0, 0.0, 80.0)))
    steps.append(sf.Step("Fold the collar stair the same way, over the seats: rear tabs first, then its feet.", part="collar",
                         approach=(0.0, 0.0, 80.0)))
    steps.append(sf.Step("Fold the header double. Press its tongues through the slots in the back wall's rim until they click.",
                         part="header", approach=(0.0, 0.0, 50.0)))
    if braced:
        steps.append(sf.Step("Hook the back-brace into the header and into the foot of the back wall.", part="brace", approach=(0.0, 50.0, 0.0)))
    steps.append(sf.Step("Stand one product in each opening.", products=True))
    return steps


def _solve_counter_tray(brief_product, *, rows, columns, envelope, board, provisional, header_height=None, front_height=None, outline=None,
                        material=None, template="counter_tray_header", bar=None, profile=None):
    """Template 1 from the product records and the envelope. Rows rise until every product's bar is seen; the header stands
    above what the rear row hides; each measure the eyes force is the least change that holds, and is listed."""
    common = st.common()
    r = Rules(board)
    t = r.t
    pw, pd, ph, cap = (brief_product[key] for key in ("width_mm", "depth_mm", "height_mm", "cap_mm"))
    W = float(envelope.get("width_mm") or 0.0)
    D = float(envelope.get("depth_mm") or 0.0)
    H = float(envelope.get("height_mm") or 0.0)
    changes = []
    bar = bar or face_bar(common, ph, cap)
    o, o_d = pw + r.clearance, pd + r.clearance
    need_w = t + columns * (o + 2 * r.clear) + 2 * (t / 2 + r.g)
    y_used = r.cap + t + r.g + r.clear + o_d / 2 + r.web + o_d / 2 + r.back_cap + t / 2 + r.g
    need_d = t + y_used + (rows - 1) * (o_d + 2 * r.clear)
    for name, value, need in (("width", W, need_w), ("depth", D, need_d)):
        if value < need - 1e-9:
            changes.append({"measure": name + "_mm", "from_mm": value or None, "to_mm": math.ceil(need),
                            "why": "the openings, the webs between them and the walls' rims need it"})
    W, D = max(W, math.ceil(need_w)), max(D, math.ceil(need_d))
    front = float(front_height or min(common["rules"]["front_lip_mm"]["value"][1], ph * .25))
    # room for a flap between the floor and the rim, and a rim to roll
    front = max(front, 2 * t + 2 * r.g + r.clear + 6.0)
    header = float(header_height or ph * common["rules"]["header_share_of_product"]["value"])
    v = {"product_width_mm": float(pw), "product_depth_mm": float(pd), "product_height_mm": float(ph), "product_cap_mm": float(cap),
         "width_mm": float(W), "depth_mm": float(D), "height_mm": float(H), "board_mm": t, "clearance_mm": r.clearance,
         "header_height_mm": header, "front_height_mm": front, "face_bar_mm": bar}

    def record_for(rise, back_z):
        g = _tray_geometry(v, rows, columns, r, rise=rise, back_z=back_z, front_h=front)
        _with_header(g, v, r, back_z, header)
        if outline:
            g["header_outline"] = outline
        if profile == "stair":
            g["side_steps"] = _stair_profile(g, v, r)
        vv = dict(v, height_mm=_r(g["header_top_z_mm"]))
        free = header
        if free > r.tall * D:
            g["brace"] = {"width_mm": _r(max(min(W * .4, 60.0), r.tab_w + 2 * r.clear)), "top_z_mm": _r(g["header_top_z_mm"] - free * .35),
                          "foot_mm": r.brace, "low_z_mm": _r(back_z * .55)}
        return _record(template, board, vv, g, rows, columns)

    def seen(rec):
        die = build_counter_tray(rec)
        return sf.sightlines_report(die.plan, sf.fold(die, die.plan), width=rec["inputs"]["width_mm"], face_bar_mm=bar)

    def lowest_back(rise_):
        return max(t + rise_ * (rows - 1) + ph - 12.0, front + r.min_panel + t, r.hold + rise_ * (rows - 1) + t + 2 * r.clear)

    # the rise: the least that shows every product's bar from every eye (0.5 mm steps, on the die itself)
    low_back = r.hold + ph                       # the back wall stands well above while the rows are searched
    rise = 0.0
    if rows > 1:
        high = float(ph)
        lo, hi = 0.0, high
        for _step in range(9):
            middle = (lo + hi) / 2
            rec = record_for(middle, middle * (rows - 1) + ph + 60.0)
            if all(row["products_passed"] for row in seen(rec)["eyes"]):
                hi = middle
            else:
                lo = middle
        rise = math.ceil(hi * 2) / 2
    rear_top = t + rise * (rows - 1) + ph
    # the back wall's top: the lowest that keeps the header's safe area clear of the rear row, from every eye
    lowest = max(rear_top - 12.0, front + r.min_panel + t, r.hold + rise * (rows - 1) + t + 2 * r.clear)
    back_z = lowest
    target = (H - r.g - header) if H else None
    if target is not None and target >= lowest:
        rec = record_for(rise, target)
        if seen(rec)["passed"]:
            back_z = target
    if back_z != target:
        while back_z < rear_top + ph:
            rec = record_for(rise, back_z)
            if seen(rec)["passed"]:
                break
            back_z += 1.0
        back_z = math.ceil(back_z)
    record = record_for(rise, back_z)
    closed_h = record["inputs"]["height_mm"]
    if H and abs(closed_h - H) > cd.TOL_MM:
        changes.append({"measure": "height_mm", "from_mm": H, "to_mm": closed_h,
                        "why": "the least height that shows every product's top %.0f mm and the whole header's safe area from both eyes, "
                               "the header kept at %.0f mm" % (bar, header)})
    elif not H:
        changes.append({"measure": "height_mm", "from_mm": None, "to_mm": closed_h, "why": "the brief gave none: solved from the eyes"})
    record["changes"] = changes
    return record


def _record(template, board, v, g, rows, columns):
    common = st.common()
    preset = common["boards"][board]
    t = v["board_mm"]
    r = Rules(board)
    t_rule = "crease centres = outside − one caliper (FEFCO Rec. 101)"
    compensation = [
        {"fold": "floor to each wall", "matches": ["floor / "], "allowance_mm": t, "rule": t_rule + "; each front and back panel runs half a caliper past its crease each end, over the side wall's edge"},
        {"fold": "rims and inner leaves", "matches": ["/ cap", "cap / inner"], "allowance_mm": _r(t / 2 + r.g),
         "rule": "a rim and its leaf stop half a caliper plus the fit gap short of the side walls, each end, and the leaf the same above the floor"},
        {"fold": "side wall's corner folds", "matches": [" fold"], "allowance_mm": _r(t + r.g), "rule": "set in one caliper plus the fit gap, so the flap lies on the panel's inner face"},
        {"fold": "header fold (180°, half-cut)", "matches": ["header fold"], "allowance_mm": t, "rule": "the back leaf lands one caliper off the shopper's leaf; the leaves are the same height"},
        {"fold": "stair folds", "matches": ["tread", "riser", "leg fold"], "allowance_mm": 0.0, "rule": "mid-plane to mid-plane: a stair is drawn at its own crease centres; it stops half a caliper plus the fit gap short of each wall"},
        {"fold": "back-brace folds", "matches": ["strut", "brace"], "allowance_mm": 0.0, "rule": "drawn at the strut's true length, from the triangle it closes"},
        {"fold": "the lid's hinge", "matches": ["back / lid"], "allowance_mm": 0.0, "rule": "the lid's depth is the floor's crease to crease: it closes on the walls"},
        {"fold": "the liner's lock", "matches": ["header lock"], "allowance_mm": _r(t + r.clear + (t + r.play) / 2), "rule": "the liner stops this far short of the lid's hinge: one caliper to close flat, the rest to keep its slot clear of the fold"},
        {"fold": "tear lines", "matches": ["tear line"], "allowance_mm": 0.0, "rule": "a tear runs on the panel's own line; nothing folds on it"},
    ]
    compensation.sort(key=lambda row: -len(row["matches"][0]))
    holes = [dict(h, centre_mm=[h["x_mm"], h["y_mm"]], product_centre_mm=[_r(h["x_mm"] + t / 2), _r(h["y_mm"] + t / 2)],
                  seat_z_mm=h.get("seat_z_mm", _r(t + g["seats_z_mm"][h["row"] - 1]) if "seats_z_mm" in g else 0.0)) for h in g["holes"]]
    return {"schema": SCHEMA, "template": {"id": template, "version": st.version(template), "provisional": True, "production_ready": False},
            "type": template, "product": "bottle", "board": dict(name=preset["name"], caliper_mm=t, grain=preset["grain"], preset=board),
            "hole_shape": "square", "inputs": v, "layout": {"rows": rows, "columns": columns, "count": rows * columns},
            "holes": holes, "geometry": g,
            "production": {"opening_mm": g["opening_mm"], "compensation": compensation,
                           "grain": preset["grain"], "grain_axis": "y", "main_folds": _main_folds(template),
                           "glue": "small zones on the four corner flaps, marked: a tear-away wall leaves nothing to trap them" if template == "lid_header_tray" else "no glue: every joint is a lock or a trapped flap",
                           "rules": _rules_read(r)},
            "provisional": True,
            "provisional_notes": st.provisional_notes(template),
            "assembly": st.record(template).get("one_line", "")}


def _rules_read(r):
    return {"fit_gap_mm": r.g, "slot_play_mm": r.play, "slot_end_play_mm": r.end, "cut_to_crease_mm": r.clear, "web_mm": r.web,
            "min_panel_mm": r.min_panel, "hold_mm": r.hold, "max_lean_deg": r.lean, "clearance_total_mm": r.clearance}


def _main_folds(template):
    if template == "lid_header_tray":
        return ["floor / front", "floor / back", "back / lid", "header fold"]
    return ["floor / front", "floor / back", "front / cap", "back / cap", "header fold"]


# --- template 6: the house flat tray with testers ------------------------------------------------------------------------

def _flat_geometry(v, rows, columns, r, *, back_z, front_h, testers=True):
    """Every product at one height: one deck holds them all, on the floor; a tester, wider-holed, at the front of each column. A liner stands
    inside each side wall, its print side in, so the deck stops a liner's width short of the walls."""
    t, gap = r.t, r.g
    W, D = v["width_mm"], v["depth_mm"]
    fw, fd = W - t, D - t
    c_f, c_b = r.cap, r.back_cap
    o, o_d = v["product_width_mm"] + r.clearance, v["product_depth_mm"] + r.clearance
    o_t, o_t_d = v["product_width_mm"] + v["tester_clearance_mm"], v["product_depth_mm"] + v["tester_clearance_mm"]
    y_leg = c_f + t + gap                      # the deck's leg against the front inner leaf
    y_rear = fd - c_b - t / 2 - gap            # the deck against the back inner leaf
    x_liner = t + gap                          # a liner's mid-plane, off the side wall's
    cw0, cw1 = x_liner + t / 2 + gap, fw - x_liner - t / 2 - gap
    x_pitch = (cw1 - cw0) / columns
    xs = [cw0 + x_pitch * (c + .5) for c in range(columns)]
    first = y_leg + r.clear + (o_t_d if testers else o_d) / 2
    last = y_rear - r.web - o_d / 2
    y_testers = first if testers else None
    y0 = first + o_t_d / 2 + v["tester_web_mm"] + o_d / 2 if testers else first
    pitch = (last - y0) / (rows - 1) if rows > 1 else 0.0
    ys = [y0 + pitch * i for i in range(rows)] if rows > 1 else [(y0 + last) / 2]
    hold = r.hold
    holes = []
    for row, y in enumerate(ys):
        for column, x in enumerate(xs):
            holes.append({"index": row * columns + column + 1, "row": row + 1, "column": column + 1, "x_mm": _r(x), "y_mm": _r(y),
                          "w_mm": _r(o), "d_mm": _r(o_d), "size_mm": _r(max(o, o_d))})
    tester_holes = [{"index": rows * columns + column + 1, "row": 0, "column": column + 1, "x_mm": _r(x), "y_mm": _r(y_testers), "w_mm": _r(o_t), "d_mm": _r(o_t_d),
                     "size_mm": _r(max(o_t, o_t_d)), "tester": True} for column, x in enumerate(xs)] if testers else []
    return {"floor_mm": [fw, fd], "front_crease_mm": front_h - t, "back_crease_mm": back_z - t, "front_cap_mm": c_f, "back_cap_mm": c_b,
            "flap_mm": min(r.flap, fd / 4), "leaf_tab_x_mm": _pair(fw, .2, .8, r), "seat_tab_x_mm": _pair(fw, .35, .65, r),
            "rear_tab_x_mm": _pair(fw, .25, .75, r), "hold_mm": hold, "rise_mm": 0.0, "row_pitch_mm": _r(pitch), "column_pitch_mm": _r(x_pitch),
            "y_leg_mm": _r(y_leg), "y_rear_mm": _r(y_rear), "seats_z_mm": [0.0] * rows, "collars_z_mm": [_r(hold)], "holes": holes, "tester_holes": tester_holes,
            "testers": bool(testers), "x_liner_mm": _r(x_liner), "collar_x_mm": [_r(cw0), _r(cw1)], "opening_mm": [_r(o), _r(o_d)], "tester_opening_mm": [_r(o_t), _r(o_t_d)],
            "web_between_openings_mm": _r(pitch - o_d) if rows > 1 else None, "web_tester_to_row_mm": _r(y0 - o_d / 2 - y_testers - o_t_d / 2) if testers else None,
            "web_between_columns_mm": _r(x_pitch - (o_t if testers else o)), "tester_row_y_mm": _r(y_testers) if testers else None}


def _liner(name, side, g, r):
    """A side wall's liner: the wall's own outline, standing on the floor inside it, between the two inner leaves, its print side in. It doubles the
    wall and carries the art the shopper sees there; the deck's tabs lock it. Flat: u along the stand from the shopper's left as it is read."""
    t, gap = r.t, r.g
    fw, fd = g["floor_mm"]
    h_f, h_b, c_f, c_b = g["front_crease_mm"], g["back_crease_mm"], g["front_cap_mm"], g["back_cap_mm"]
    y0, y1 = c_f + t / 2 + gap, fd - c_b - t / 2 - gap
    top_f, top_b = h_f + t / 2, h_b + t / 2                    # level with the wall's own top: no sliver of its back shows between them
    low = t / 2 + gap
    y_s0, y_s1 = c_f + t / 2 + gap, fd - c_b - t / 2 - gap
    u = (lambda y: y - y0) if side == "left" else (lambda y: y1 - y)
    profile = [(y0, low), (y0, top_f), (y_s0, top_f), (y_s1, top_b), (y1, top_b), (y1, low)]
    part = Part(name, "%s — stand it inside the %s wall, its print side in" % (name.upper(), side))
    polygon = Polygon([(u(y), top_b - z) for y, z in profile]).buffer(0)
    part.faces = [(name, polygon, False)]
    x = g["x_liner_mm"] if side == "left" else fw - g["x_liner_mm"]
    world = (x + t / 2, (y0 if side == "left" else y1) + t / 2, t / 2 + top_b)
    along = (0, 1, 0) if side == "left" else (0, -1, 0)
    return part, sf.PartPlan(name, sf.pose(world, along, (0, 0, -1)), []), u, top_b


def build_flat_tray(record):
    g, v = record["geometry"], record["inputs"]
    r = Rules(record["board"]["preset"])
    t, gap = r.t, r.g
    tray, tray_plan, locks, joints = _tray(v, g, r)
    header, header_plan = _header(v, g, r)
    fw, fd = g["floor_mm"]
    h_b, c_b = g["back_crease_mm"], g["back_cap_mm"]
    y_back_top = fd + h_b
    y_cap = y_back_top + c_b / 2
    for index, x in enumerate(g["tongue_x_mm"], 1):
        _tab_slot(tray, "rim slot %d" % index, x - t / 2, y_cap, r.neck + 2 * r.end, 2 * t + r.play, "back cap", plies=2)
        locks.append(sf.Lock("header front leaf into the rim %d" % index, ("header", "tongue front %d" % index), ("tray", "rim slot %d" % index), "barbed", r.head))
        locks.append(sf.Lock("header back leaf into the rim %d" % index, ("header", "tongue back %d" % index), ("tray", "rim slot %d" % index), "barbed", r.head))
    parts = [tray, header]
    plans = {"tray": tray_plan, "header": header_plan}
    joints = list(joints) + [sf.Joint(("header", "header front"), ("tray", "back cap"), "edge", "the header's shopper leaf on the rim"),
                             sf.Joint(("header", "header back"), ("tray", "back cap"), "edge", "the header's back leaf on the rim")]
    x0, x1 = g["collar_x_mm"]
    z = g["collars_z_mm"][0]
    all_holes = [dict(hole, row=1) for hole in list(g["tester_holes"]) + list(g["holes"])]
    deck, deck_plan = _stair("deck", "DECK — fold its leg down; its side tabs into the liners, its rear tabs into the back wall, its feet into the floor", (x0, x1), r, seats_z=[z],
                             y_front=g["y_leg_mm"], ys_rise=[], y_end=g["y_rear_mm"], leg_to=0.0, holes=all_holes, rear_slots=g["rear_tab_x_mm"], floor_tab_x=g["seat_tab_x_mm"])
    parts.append(deck)
    plans["deck"] = deck_plan
    for index, x in enumerate(g["seat_tab_x_mm"], 1):
        slot = "floor slot deck %d" % index
        _tab_slot(tray, slot, x, g["y_leg_mm"], r.tab_w + 2 * r.end, t + r.play, "floor")
        locks.append(sf.Lock("deck into the floor %d" % index, ("deck", "deck foot %d" % index), ("tray", slot), "flush", t))
    for index, x in enumerate(g["rear_tab_x_mm"], 1):
        slot = "inner slot deck %d" % index
        _tab_slot(tray, slot, x, y_back_top + c_b + (h_b - z), r.tab_w + 2 * r.end, t + r.play, "back inner")
        locks.append(sf.Lock("deck into the back wall %d" % index, ("deck", "deck rear tab %d" % index), ("tray", slot), "through", t))
    joints += [sf.Joint(("deck", "deck leg"), ("tray", "floor"), "edge", "the deck's leg on the floor"),
               sf.Joint(("deck", "deck leg"), ("tray", "front inner"), "lap", "the deck's leg against the front wall"),
               sf.Joint(("deck", "deck tread 1"), ("tray", "back inner"), "edge", "the deck against the back wall")]
    # the liners: each locked by two of the deck's side tabs, through the liner to the wall
    width = x1 - x0
    tread_y = lambda y: y - g["y_leg_mm"]  # noqa: E731
    ys_tab = [g["y_leg_mm"] + (g["y_rear_mm"] - g["y_leg_mm"]) * share for share in (.3, .75)]
    reach = t + gap
    hinges = deck_plan.hinges
    for side, die_x, die_root in (("left", (width, width + reach), "left"), ("right", (-reach, 0.0), "right")):
        name = "%s liner" % side
        liner, plan, u, top = _liner(name, side, g, r)
        for index, y in enumerate(ys_tab, 1):
            tab = "deck tab %s %d" % (side, index)
            a, b = tread_y(y) - r.tab_w / 2, tread_y(y) + r.tab_w / 2
            deck.faces.append((tab, _tab(die_x[0], a, die_x[1], b, die_root), False))
            edge = die_x[0] if side == "left" else die_x[1]
            deck.joins.append((tab + " join", _seg(edge, a, edge, b)))
            hinges.append(sf.Hinge(tab, "deck tread 1", tab + " join", 0))
            slot = "liner slot %d" % index
            _tab_slot(liner, slot, u(y), top - z, r.tab_w + 2 * r.end, t + r.play, name)
            locks.append(sf.Lock("deck into the %s %d" % (name, index), ("deck", tab), (name, slot), "flush", t))
        parts.append(liner)
        plans[name] = plan
        joints += [sf.Joint((name, name), ("tray", "%s side" % side), "lap", "the liner flat against its wall"),
                   sf.Joint((name, name), ("tray", "front inner"), "edge", "the liner against the front wall"),
                   sf.Joint((name, name), ("tray", "back inner"), "edge", "the liner against the back wall"),
                   sf.Joint((name, name), ("tray", "floor"), "edge", "the liner on the floor"),
                   sf.Joint(("deck", "deck tread 1"), (name, name), "edge", "the deck against the liner")]
    products = []
    pw, pd, ph = v["product_width_mm"], v["product_depth_mm"], v["product_height_mm"]
    for hole in list(g["holes"]) + list(g["tester_holes"]):
        frame = sf.translation(hole["x_mm"] + t / 2, hole["y_mm"] + t / 2, t)
        tester = bool(hole.get("tester"))
        carries = tester or (not g["testers"] and hole["row"] == 1)
        products.append({"index": hole["index"], "row": hole["row"], "column": hole["column"], "frame": frame, "w": pw, "d": pd, "h": ph, "tester": tester,
                         "cap": v.get("product_cap_mm") or 0.0, "plate": ("deck", "deck tread 1"), "seat": ("tray", "floor"), "carries_shade": carries,
                         "clearance_mm": v["tester_clearance_mm"] if tester else v["clearance_mm"],
                         # a sealed product behind the column's carrier is reported, and its bar is the carrier's: the owner's "the testers carry it"
                         "bar_mm": v["face_bar_mm"] if carries else 0.0})
    brace_plan = _add_brace(parts, plans, locks, joints, tray, header, v, g, r) if g.get("brace") else None
    steps = [sf.Step("Lay the tray flat, print side down."),
             sf.Step("Fold the two side walls up, and fold each wall's corner flaps in.",
                     close={"tray": ["left side", "right side", "front left flap", "front right flap", "back left flap", "back right flap"]}),
             sf.Step("Fold the front panel up, over the flaps. Roll its rim in and down, and push its two tabs through the floor.",
                     close={"tray": ["front panel", "front cap", "front inner", "front tab 1", "front tab 2"]}),
             sf.Step("Do the same with the back wall. The flaps are now trapped: no glue.", close={"tray": ["back panel", "back cap", "back inner", "back tab 1", "back tab 2"]}),
             sf.Step("Stand a liner inside each side wall, its print side in.", part="left liner", approach=(0.0, 0.0, 60.0)),
             sf.Step("The other liner the same way.", part="right liner", approach=(0.0, 0.0, 60.0)),
             sf.Step("Fold the deck's leg down. Slide its rear tabs into the back wall and its side tabs into the liners, then push its feet through the floor.", part="deck", approach=(0.0, 0.0, 60.0)),
             sf.Step("Fold the header double. Press its tongues through the slots in the back wall's rim until they click.", part="header", approach=(0.0, 0.0, 50.0))]
    if brace_plan:
        steps.append(sf.Step("Hook the back-brace into the header and into the foot of the back wall.", part="brace", approach=(0.0, 50.0, 0.0)))
    steps.append(sf.Step("Stand one product in each opening, and a tester in each front opening." if g["testers"] else "Stand one product in each opening.", products=True))
    plan = sf.Plan(plans, joints, locks, steps, products)
    title = "%s %s — flat die at 100 %%" % (st.label(record["template"]["id"]), record["template"]["version"])
    return _place(parts, title, t, plan, row_width=max(tray.outline().bounds[2] - tray.outline().bounds[0], 420))


def _solve_flat(brief_product, *, rows, columns, envelope, board, provisional, header_height=None, front_height=None, outline=None, testers=True):
    """Template 6: no rise to search. The width and depth are the least the openings and webs need; the back wall the lowest that shows the whole
    header above the rear row, from both eyes; each change from the brief is listed. A column's shade is carried by its tester, or with testers
    off by its front product."""
    common = st.common()
    limits = st.record("flat_tray_testers")["limits"]
    r = Rules(board)
    t = r.t
    pw, pd, ph, cap = (brief_product[key] for key in ("width_mm", "depth_mm", "height_mm", "cap_mm"))
    W, D, H = (float(envelope.get(key) or 0.0) for key in ("width_mm", "depth_mm", "height_mm"))
    changes = []
    bar = face_bar(common, ph, cap)
    tester_clear = float(limits["tester_clearance_total_mm"])
    o, o_d = pw + r.clearance, pd + r.clearance
    o_t, o_t_d = pw + tester_clear, pd + tester_clear
    wall = 2 * (1.5 * t + 2 * r.g)
    web, tester_web = float(limits["web_mm"]), float(limits["tester_web_mm"])
    need_w = t + wall + columns * ((o_t if testers else o) + web)
    y_used = r.cap + t + r.g + r.clear + (rows - 1) * (o_d + web) + o_d + r.web + r.back_cap + t / 2 + r.g
    if testers:
        y_used += o_t_d + tester_web
    need_d = t + y_used
    for name, value, need in (("width", W, need_w), ("depth", D, need_d)):
        if value < need - 1e-9:
            changes.append({"measure": name + "_mm", "from_mm": value or None, "to_mm": math.ceil(need),
                            "why": "the openings, %sthe webs between them and the walls' rims need it" % ("the tester row, " if testers and name == "depth" else "")})
    W, D = max(W, math.ceil(need_w)), max(D, math.ceil(need_d))
    front = float(front_height or min(common["rules"]["front_lip_mm"]["value"][1], ph * .25))
    front = max(front, 2 * t + 2 * r.g + r.clear + 6.0, r.hold + t / 2 + r.g + t / 2)
    header = float(header_height or ph * common["rules"]["header_share_of_product"]["value"])
    v = {"product_width_mm": float(pw), "product_depth_mm": float(pd), "product_height_mm": float(ph), "product_cap_mm": float(cap),
         "width_mm": float(W), "depth_mm": float(D), "height_mm": float(H), "board_mm": t, "clearance_mm": r.clearance, "tester_clearance_mm": tester_clear,
         "header_height_mm": header, "front_height_mm": front, "face_bar_mm": bar, "tester_web_mm": tester_web}

    def record_for(back_z):
        g = _flat_geometry(v, rows, columns, r, back_z=back_z, front_h=front, testers=testers)
        _with_header(g, v, r, back_z, header)
        if outline:
            g["header_outline"] = outline
        if header > r.tall * D:
            g["brace"] = {"width_mm": _r(max(min(W * .4, 60.0), r.tab_w + 2 * r.clear)), "top_z_mm": _r(g["header_top_z_mm"] - header * .35),
                          "foot_mm": r.brace, "low_z_mm": _r(back_z * .55)}
        return _record("flat_tray_testers", board, dict(v, height_mm=_r(g["header_top_z_mm"])), g, rows, columns)

    def seen(rec):
        die = build_flat_tray(rec)
        return sf.sightlines_report(die.plan, sf.fold(die, die.plan), width=rec["inputs"]["width_mm"], face_bar_mm=bar)

    rear_top = t + ph
    lowest = max(rear_top - 12.0, front + r.min_panel + t, r.hold + t + 2 * r.clear)
    target = (H - r.g - header) if H else None
    back_z = None
    if target is not None and target >= lowest and seen(record_for(target))["passed"]:
        back_z = target
    if back_z is None:
        back_z = lowest
        while back_z < rear_top + ph and not seen(record_for(back_z))["passed"]:
            back_z += 1.0
        back_z = math.ceil(back_z)
    record = record_for(back_z)
    closed_h = record["inputs"]["height_mm"]
    if H and abs(closed_h - H) > cd.TOL_MM:
        changes.append({"measure": "height_mm", "from_mm": H, "to_mm": closed_h, "why": "the least height that shows the whole header's safe area above the rear row from both eyes, the header kept at %.0f mm" % header})
    elif not H:
        changes.append({"measure": "height_mm", "from_mm": None, "to_mm": closed_h, "why": "the brief gave none: solved from the eyes"})
    record["changes"] = changes
    return record


# --- template 2: the stepped display --------------------------------------------------------------------------------------

def _stair_profile(g, v, r):
    """The stepped display's side wall: it follows the stair, a margin above each deck, so it hides nothing and reads as stairs."""
    t = r.t
    out = []
    margin = r.min_panel + 3.0
    for y, z in zip(g["risers_y_mm"], g["collars_z_mm"]):
        out += [(y - 1.0, z + margin), (y + 1.0, z + margin + g["rise_mm"])]
    return [row for row in out]


def _solve_stepped(brief_product, *, rows, columns, envelope, board, provisional, header_height=None, front_height=None, outline=None):
    """Template 2: rows high enough to show most of each product, the walls cut to the stair. A stair of its own bar, not the tray's."""
    common = st.common()
    share = st.record("stepped_tiered")["limits"]["face_share_of_product"]
    bar = max(face_bar(common, brief_product["height_mm"], brief_product["cap_mm"]), share * brief_product["height_mm"])
    front = float(front_height or st.record("stepped_tiered")["limits"]["front_lip_mm"])
    return _solve_counter_tray(brief_product, rows=rows, columns=columns, envelope=envelope, board=board, provisional=provisional, header_height=header_height,
                               front_height=front, outline=outline, template="stepped_tiered", bar=bar, profile="stair")


# --- templates 4 and 5: rows that lean back ---------------------------------------------------------------------------------

def _lean_stair(name, label, xs_part, r, *, section, angle, holes=None, feet=None, rear_x=None):
    """A strip through ``section``: [(y, z), …] its leg's foot, then each tread's front and rear edge in turn (floor-local), the treads
    falling to the back at ``angle`` so what stands on them leans back toward the eye, the risers between them upright. Its print side is
    up. The last tread's tabs turn level, to pass straight through the back wall's inner leaf. ``holes``: (x in the stand, tread, distance
    along the tread, w, d)."""
    t, gap = r.t, r.g
    width = xs_part[1] - xs_part[0]
    x_on_die = lambda x: xs_part[1] - x  # noqa: E731
    points = [np.array(point, float) for point in section]
    part = Part(name, label, hole_shape="square")
    a = math.radians(angle)
    tread_dir = np.array([math.cos(a), -math.sin(a)])
    y_axis = tread_dir.copy()
    z_axis = np.array([-math.sin(a), -math.cos(a)])       # inner side: down and to the front
    root = name + " tread 1"
    hinges, faces, creases = [], [], []
    # the leg first: it hangs from the first tread's front edge
    foot_at, first_front = points[0], points[1]
    leg_len = float(first_front[1] - foot_at[1])
    leg = name + " leg"
    faces.append((leg, _rect(0, -leg_len, width, 0), False))
    creases.append((leg + " fold", _seg(0, 0, width, 0)))
    hinges.append(sf.Hinge(leg, root, leg + " fold", _turn(np.array([0.0, -1.0]), y_axis, z_axis, -1.0)))
    tab = t + gap
    for index, x in enumerate(feet or [], 1):
        x0, x1 = x_on_die(x) - r.tab_w / 2, x_on_die(x) + r.tab_w / 2
        foot = "%s foot %d" % (name, index)
        faces.append((foot, _tab(x0, -leg_len - tab, x1, -leg_len, "bottom"), False))
        part.joins.append((foot + " join", _seg(x0, -leg_len, x1, -leg_len)))
        hinges.append(sf.Hinge(foot, leg, foot + " join", 0))
    flat = 0.0
    tread_at = {}
    previous = None
    current_y, current_z = y_axis, z_axis
    treads = (len(points) - 1) // 2
    for index in range(treads):
        front, rear = points[1 + 2 * index], points[2 + 2 * index]
        length = float(np.linalg.norm(rear - front))
        tread = "%s tread %d" % (name, index + 1)
        faces.append((tread, _rect(0, flat, width, flat + length), False))
        tread_at[index] = flat
        if previous:
            crease = "%s / %s" % (previous, tread)
            creases.append((crease, _seg(0, flat, width, flat)))
            theta = _turn(tread_dir, current_y, current_z)
            hinges.append(sf.Hinge(tread, previous, crease, theta))
            c, n = math.cos(math.radians(theta)), math.sin(math.radians(theta))
            current_y, current_z = c * current_y + n * current_z, -n * current_y + c * current_z
        flat += length
        if index + 1 < treads:
            next_front = points[3 + 2 * index]
            rise = float(next_front[1] - rear[1])
            riser = "%s riser %d" % (name, index + 1)
            faces.append((riser, _rect(0, flat, width, flat + rise), False))
            crease = "%s / %s" % (tread, riser)
            creases.append((crease, _seg(0, flat, width, flat)))
            theta = _turn(np.array([0.0, 1.0]), current_y, current_z)
            hinges.append(sf.Hinge(riser, tread, crease, theta))
            c, n = math.cos(math.radians(theta)), math.sin(math.radians(theta))
            current_y, current_z = c * current_y + n * current_z, -n * current_y + c * current_z
            previous = riser
            flat += rise
    last = "%s tread %d" % (name, treads)
    for index, x in enumerate(rear_x or [], 1):
        x0, x1 = x_on_die(x) - r.tab_w / 2, x_on_die(x) + r.tab_w / 2
        tab_name = "%s rear tab %d" % (name, index)
        faces.append((tab_name, _tab(x0, flat, x1, flat + t + gap + r.clear / 2, "top"), False))
        creases.append((tab_name + " fold", _seg(x0, flat, x1, flat)))
        hinges.append(sf.Hinge(tab_name, last, tab_name + " fold", _turn(np.array([1.0, 0.0]), current_y, current_z)))
    part.faces, part.creases = faces, creases
    for index, (x, tread_index, along, w, d) in enumerate(holes or [], 1):
        cx, cy = x_on_die(x), tread_at[tread_index] + along
        part.slots.append({"id": "opening %d" % index, "kind": "opening", "polygon": _rect(cx - w / 2, cy - d / 2, cx + w / 2, cy + d / 2)})
    pose = sf.pose((xs_part[1] + t / 2, first_front[0] + t / 2, first_front[1] + t / 2), (-1, 0, 0), (0, y_axis[0], y_axis[1]))
    return part, sf.PartPlan(root, pose, hinges)


def _lean_geometry(v, rows, columns, r, *, angle, rise, back_z, front_h, clearance, cap_row):
    """Each row's tread: long enough that a product passes its deck, reaches its seat ahead of the hole, and leans back past it without
    touching the riser behind or, in the last row, the back wall."""
    t, gap = r.t, r.g
    W, D = v["width_mm"], v["depth_mm"]
    fw, fd = W - t, D - t
    c_f, c_b = r.cap, r.back_cap
    a = math.radians(angle)
    sn, cs = math.sin(a), math.cos(a)
    o, o_d = v["product_width_mm"] + clearance, v["product_depth_mm"] + clearance
    lean = float(st.record("tester_unit")["limits"]["max_lean_deg"]) if cap_row else r.lean      # a tester leans further than a sealed product
    hold = math.ceil(clearance / math.tan(math.radians(lean)))
    h = v["product_height_mm"]
    y_leg = c_f + t + gap
    y_rear = fd - c_b - t / 2 - gap
    ahead = r.clear + hold * sn                     # along the tread: from the riser in front to the hole
    behind = r.clear + (rise + t) * sn / cs         # the lean over the rise behind it
    behind_last = r.clear + (h - hold) * sn         # the lean over the last deck
    cap_slot = (o_d + r.clear) if cap_row else 0.0
    lengths = [ahead + o_d + behind] * (rows - 1) + [ahead + o_d + cap_slot + behind_last]
    need_run = sum(length * cs for length in lengths)
    spare = (y_rear - y_leg) - need_run
    if spare > 0:                                  # the rows spread over what the envelope gives
        lengths = [length + spare / rows / cs for length in lengths]
    run = [length * cs for length in lengths]
    y_edges = [y_leg]
    for row in run:
        y_edges.append(y_edges[-1] + row)
    drop = [length * sn for length in lengths]
    # the seat under the first tread's low end stands clear of the floor
    seat_gap = hold * cs
    z0 = max(front_h - t, seat_gap + drop[0] + t / 2 + gap + r.min_panel + (t + gap) * sn / cs)
    x0, x1 = t / 2 + gap, fw - t / 2 - gap
    x_pitch = (x1 - x0) / columns
    xs = [x0 + x_pitch * (c + .5) for c in range(columns)]
    fronts = [z0 + i * rise for i in range(rows)]
    collar = [(y_leg, t / 2 + gap)]
    for row in range(rows):
        collar += [(y_edges[row], fronts[row]), (y_edges[row + 1], fronts[row] - drop[row])]
    # the seat stair: one hold under the deck, each edge a caliper and the gap behind the collar's riser
    shift = t + gap
    seat = None
    seat_points = []
    for row in range(rows):
        y_a = y_edges[row] + shift
        y_b = y_edges[row + 1] + shift if row + 1 < rows else y_rear
        z_a = fronts[row] - (y_a - y_edges[row]) * sn / cs - hold / cs
        z_b = fronts[row] - (y_b - y_edges[row]) * sn / cs - hold / cs
        seat_points += [(y_a, z_a), (y_b, z_b)]
    seat = [(y_edges[0] + shift, t / 2 + gap)] + seat_points
    holes, deck_holes = [], []
    along = ahead + o_d / 2
    for row in range(rows):
        for column, x in enumerate(xs):
            py, pz = y_edges[row] + along * cs, fronts[row] - along * sn
            holes.append({"index": row * columns + column + 1, "row": row + 1, "column": column + 1, "x_mm": _r(x), "y_mm": _r(py), "z_mm": _r(pz), "w_mm": _r(o), "d_mm": _r(o_d),
                          "size_mm": _r(max(o, o_d)), "along_mm": _r(along),
                          "seat_z_mm": _r(pz - (hold - t / 2) * cs + t / 2)})
            deck_holes.append((x, row, along, o, o_d))
    if cap_row:
        for x in xs:
            deck_holes.append((x, rows - 1, along + o_d + r.clear, o, o_d))
    g = {"floor_mm": [fw, fd], "front_crease_mm": front_h - t, "back_crease_mm": back_z - t, "front_cap_mm": c_f, "back_cap_mm": c_b, "flap_mm": min(r.flap, fd / 4),
         "leaf_tab_x_mm": _pair(fw, .2, .8, r), "seat_tab_x_mm": _pair(fw, .35, .65, r), "rear_tab_x_mm": _pair(fw, .25, .75, r), "angle_deg": angle, "rise_mm": rise, "hold_mm": hold,
         "collar_section": [[_r(a_), _r(b_)] for a_, b_ in collar], "seat_section": [[_r(a_), _r(b_)] for a_, b_ in seat], "deck_holes": deck_holes, "collar_x_mm": [_r(x0), _r(x1)],
         "row_pitch_mm": _r(run[0]) if rows > 1 else 0.0, "column_pitch_mm": _r(x_pitch), "opening_mm": [_r(o), _r(o_d)], "holes": holes, "cap_row": bool(cap_row),
         "web_between_openings_mm": _r(run[0] - o_d) if rows > 1 else None, "clearance_mm": clearance, "need_depth_mm": _r(need_run + y_leg + c_b + t / 2 + gap + t)}
    return g


def build_slanted(record):
    g, v = record["geometry"], record["inputs"]
    r = Rules(record["board"]["preset"])
    t, gap = r.t, r.g
    tray, tray_plan, locks, joints = _tray(v, g, r)
    header, header_plan = _header(v, g, r)
    fd = g["floor_mm"][1]
    h_b, c_b = g["back_crease_mm"], g["back_cap_mm"]
    y_back_top = fd + h_b
    y_cap = y_back_top + c_b / 2
    y_inner_at = lambda z: y_back_top + c_b + (h_b - z)  # noqa: E731
    for index, x in enumerate(g["tongue_x_mm"], 1):
        _tab_slot(tray, "rim slot %d" % index, x - t / 2, y_cap, r.neck + 2 * r.end, 2 * t + r.play, "back cap", plies=2)
        locks.append(sf.Lock("header front leaf into the rim %d" % index, ("header", "tongue front %d" % index), ("tray", "rim slot %d" % index), "barbed", r.head))
        locks.append(sf.Lock("header back leaf into the rim %d" % index, ("header", "tongue back %d" % index), ("tray", "rim slot %d" % index), "barbed", r.head))
    joints = list(joints) + [sf.Joint(("header", "header front"), ("tray", "back cap"), "edge", "the header's shopper leaf on the rim"),
                             sf.Joint(("header", "header back"), ("tray", "back cap"), "edge", "the header's back leaf on the rim")]
    x0, x1 = g["collar_x_mm"]
    rows = record["layout"]["rows"]
    collar, collar_plan = _lean_stair("collar", "COLLAR — fold the stair; its rear tabs into the back wall, its feet into the floor", (x0, x1), r, section=g["collar_section"],
                                      angle=g["angle_deg"], holes=[tuple(row) for row in g["deck_holes"]], feet=g["seat_tab_x_mm"], rear_x=g["rear_tab_x_mm"])
    seat, seat_plan = _lean_stair("seat", "SEATS — fold the stair; its rear tabs into the back wall, its feet into the floor", (x0, x1), r, section=g["seat_section"],
                                  angle=g["angle_deg"], feet=g["seat_tab_x_mm"], rear_x=g["rear_tab_x_mm"])
    plans = {"tray": tray_plan, "header": header_plan, "collar": collar_plan, "seat": seat_plan}
    for name, section in (("collar", g["collar_section"]), ("seat", g["seat_section"])):
        y_leg = section[0][0]
        z_end = section[-1][1]
        for index, x in enumerate(g["seat_tab_x_mm"], 1):
            slot = "floor slot %s %d" % (name, index)
            _tab_slot(tray, slot, x, y_leg, r.tab_w + 2 * r.end, t + r.play, "floor")
            locks.append(sf.Lock("%s into the floor %d" % (name, index), (name, "%s foot %d" % (name, index)), ("tray", slot), "flush", t))
        for index, x in enumerate(g["rear_tab_x_mm"], 1):
            slot = "inner slot %s %d" % (name, index)
            _tab_slot(tray, slot, x, y_inner_at(z_end), r.tab_w + 2 * r.end, t + r.play, "back inner")
            locks.append(sf.Lock("%s into the back wall %d" % (name, index), (name, "%s rear tab %d" % (name, index)), ("tray", slot), "through", t))
    joints += [sf.Joint(("collar", "collar leg"), ("tray", "floor"), "edge", "the collar's leg on the floor"), sf.Joint(("collar", "collar leg"), ("tray", "front inner"), "lap", "the collar's leg against the front wall"),
               sf.Joint(("seat", "seat leg"), ("tray", "floor"), "edge", "the seat stair's leg on the floor"), sf.Joint(("seat", "seat leg"), ("collar", "collar leg"), "lap", "the seat stair's leg behind the collar's"),
               sf.Joint(("collar", "collar tread 1"), ("tray", "left side"), "edge", "the collar against the side wall"), sf.Joint(("collar", "collar tread 1"), ("tray", "right side"), "edge", "the collar against the side wall")]
    a = math.radians(g["angle_deg"])
    sn, cs = math.sin(a), math.cos(a)
    hold = g["hold_mm"]
    products = []
    pw, pd, ph = v["product_width_mm"], v["product_depth_mm"], v["product_height_mm"]
    for hole in g["holes"]:
        # from the hole down the product's own axis to the seat's top surface
        down = hold - t / 2
        by, bz = hole["y_mm"] - sn * down, hole["z_mm"] - cs * down
        frame = np.eye(4)
        frame[:3, 0], frame[:3, 1], frame[:3, 2] = (1, 0, 0), (0, cs, -sn), (0, sn, cs)
        frame[:3, 3] = (hole["x_mm"] + t / 2, by + t / 2, bz + t / 2)
        products.append({"index": hole["index"], "row": hole["row"], "column": hole["column"], "frame": frame, "w": pw, "d": pd, "h": ph, "cap": v.get("product_cap_mm") or 0.0,
                         "plate": ("collar", "collar tread %d" % hole["row"]), "seat": ("seat", "seat tread %d" % hole["row"])})
    parts = [tray, header, collar, seat]
    plan = sf.Plan(plans, joints, locks, _lean_steps(record["template"]["id"]), products)
    title = "%s %s — flat die at 100 %%" % (st.label(record["template"]["id"]), record["template"]["version"])
    return _place(parts, title, t, plan, row_width=max(tray.outline().bounds[2] - tray.outline().bounds[0], 420))


def _lean_steps(template):
    stand = "Stand one tester in each front opening, its cap in the opening behind it." if template == "tester_unit" else "Stand one product in each opening: it leans back with its deck."
    return [sf.Step("Lay the tray flat, print side down."),
            sf.Step("Fold the two side walls up, and fold each wall's corner flaps in.", close={"tray": ["left side", "right side", "front left flap", "front right flap", "back left flap", "back right flap"]}),
            sf.Step("Fold the front panel up, over the flaps. Roll its rim in and down, and push its two tabs through the floor.", close={"tray": ["front panel", "front cap", "front inner", "front tab 1", "front tab 2"]}),
            sf.Step("Do the same with the back wall. The flaps are now trapped: no glue.", close={"tray": ["back panel", "back cap", "back inner", "back tab 1", "back tab 2"]}),
            sf.Step("Fold the seat stair. Slide its rear tabs into the back wall, then push its feet through the floor.", part="seat", approach=(0.0, 0.0, 80.0)),
            sf.Step("Fold the collar stair the same way, over the seats: rear tabs first, then its feet.", part="collar", approach=(0.0, 0.0, 80.0)),
            sf.Step("Fold the header double. Press its tongues through the slots in the back wall's rim until they click.", part="header", approach=(0.0, 0.0, 50.0)),
            sf.Step(stand, products=True)]


def _solve_slanted(brief_product, *, rows, columns, envelope, board, provisional, header_height=None, front_height=None, outline=None, template="slanted_front", cap_row=False):
    """Templates 4 and 5: the rows lean back at the type's angle. The rise is the least that shows every product from both eyes; the tray
    takes the depth their lean needs; the back wall stands just above what the rear row hides. Each change from the brief is listed."""
    common = st.common()
    r = Rules(board)
    t = r.t
    limits = st.record(template)["limits"]
    angle = float(limits["angle_deg"])
    clearance = float(limits.get("clearance_total_mm", r.clearance))
    pw, pd, ph, cap = (brief_product[key] for key in ("width_mm", "depth_mm", "height_mm", "cap_mm"))
    W, D, H = (float(envelope.get(key) or 0.0) for key in ("width_mm", "depth_mm", "height_mm"))
    changes = []
    bar = face_bar(common, ph, cap)
    o = pw + clearance
    need_w = t + columns * (o + 2 * r.clear) + 2 * (t / 2 + r.g)
    if W < need_w - 1e-9:
        changes.append({"measure": "width_mm", "from_mm": W or None, "to_mm": math.ceil(need_w), "why": "the openings and the webs between them need it"})
    W = max(W, math.ceil(need_w))
    front = max(float(front_height or limits["front_lip_mm"]), 2 * t + 2 * r.g + r.clear + 6.0)
    header = float(header_height or ph * common["rules"]["header_share_of_product"]["value"])
    base = {"product_width_mm": float(pw), "product_depth_mm": float(pd), "product_height_mm": float(ph), "product_cap_mm": float(cap), "width_mm": float(W), "board_mm": t, "clearance_mm": clearance,
            "header_height_mm": header, "front_height_mm": front, "face_bar_mm": bar}

    def depth_for(rise):
        probe = dict(base, depth_mm=max(D, 1.0))
        need = _lean_geometry(probe, rows, columns, r, angle=angle, rise=rise, back_z=1000.0, front_h=front, clearance=clearance, cap_row=cap_row)["need_depth_mm"]
        return max(D, float(math.ceil(need)))

    def record_for(rise, back_z):
        vv = dict(base, depth_mm=depth_for(rise), height_mm=0.0)
        g = _lean_geometry(vv, rows, columns, r, angle=angle, rise=rise, back_z=back_z, front_h=front, clearance=clearance, cap_row=cap_row)
        _with_header(g, vv, r, back_z, header)
        if outline:
            g["header_outline"] = outline
        vv["height_mm"] = _r(g["header_top_z_mm"])
        return _record(template, board, vv, g, rows, columns)

    def seen(rec):
        die = build_slanted(rec)
        return sf.sightlines_report(die.plan, sf.fold(die, die.plan), width=W, face_bar_mm=bar)

    def rear_top(rec):
        die = build_slanted(rec)
        return max((p["frame"] @ np.array([0.0, 0.0, ph, 1.0]))[2] for p in die.plan.products)

    rise = 0.0
    if rows > 1:
        lo, hi = 0.0, float(ph)
        for _step in range(9):
            middle = (lo + hi) / 2
            rec = record_for(middle, 1000.0)
            if all(row["products_passed"] for row in seen(rec)["eyes"]):
                hi = middle
            else:
                lo = middle
        rise = math.ceil(hi * 2) / 2
    top = rear_top(record_for(rise, 1000.0))
    back_z = max(math.ceil(top - 12.0), math.ceil(front + r.min_panel + t))
    target = (H - r.g - header) if H else None
    if target is not None and target >= back_z and seen(record_for(rise, target))["passed"]:
        back_z = target
    else:
        start, tallest = back_z, back_z + 2 * ph   # a bar no wall can meet fails in its qualification, in words; it never hangs the solve
        while back_z < tallest and not seen(record_for(rise, back_z))["passed"]:
            back_z += 1.0
        back_z = back_z if back_z < tallest else start
    record = record_for(rise, back_z)
    final = record["inputs"]
    if D and final["depth_mm"] != D:
        changes.append({"measure": "depth_mm", "from_mm": D, "to_mm": final["depth_mm"], "why": "the products' lean and their seats need it"})
    if H and abs(final["height_mm"] - H) > cd.TOL_MM:
        changes.append({"measure": "height_mm", "from_mm": H, "to_mm": final["height_mm"], "why": "the least height that shows every product's top %.0f mm and the whole header's safe area from both eyes, the header kept at %.0f mm" % (bar, header)})
    record["changes"] = changes
    return record


def _solve_tester(brief_product, *, rows, columns, envelope, board, provisional, header_height=None, front_height=None, outline=None):
    """Template 5: a wider opening (a tester is taken out and put back all day), the gentler lean of the tester fixtures, and a row of
    openings behind for the testers' caps."""
    return _solve_slanted(brief_product, rows=rows, columns=columns, envelope=envelope, board=board, provisional=provisional, header_height=header_height,
                          front_height=front_height, outline=outline, template="tester_unit", cap_row=True)


# --- template 3: the lid that becomes the header --------------------------------------------------------------------------------

def build_lid_tray(record):
    """It ships as a closed box: walls to the lid's height, the upper walls perforated. Opened: the upper walls tear away, the lid (its
    liner doubled under it) swings up to stand on the back wall's line, its liner's print side now facing the shopper, a brace closes the
    triangle behind it. Glue only where no lock can reach: the back corners."""
    g, v = record["geometry"], record["inputs"]
    r = Rules(record["board"]["preset"])
    t, gap = r.t, r.g
    fw, fd = g["floor_mm"]
    h_b = g["back_crease_mm"]
    lip = g["front_crease_mm"]
    lid = g["lid_mm"]
    liner = lid - t - r.clear - (t + r.play) / 2     # its tab lands far enough above the hinge that its slot does not weaken the fold
    cx0, cx1 = t / 2 + gap, fw - t / 2 - gap
    tray = Part("tray", "TRAY AND LID — it ships closed; tear the walls along the perforations, swing the lid up")
    y_top = fd + h_b
    y_fold = y_top + lid
    y_liner = y_fold + liner
    y_f0, y_r0 = t + gap, fd - t - gap
    # the walls: printed up to the tear line; above it, the part that tears away. The side wall's tear runs from the lip to the back wall's top
    tray.faces = [("floor", _rect(0, 0, fw, fd), False),
                  ("front panel", _rect(-t / 2, -lip, fw + t / 2, 0), True),
                  ("front tear", _rect(-t / 2, -h_b, fw + t / 2, -lip), False),
                  ("back panel", _rect(-t / 2, fd, fw + t / 2, y_top), True),
                  ("header back", _rect(-t / 2, y_top, fw + t / 2, y_fold), True),
                  ("header front", _rect(-t / 2, y_fold, fw + t / 2, y_liner), True)]
    top_f = lip + t / 2
    top_b = h_b + t / 2
    tray.faces += [("left side", Polygon([(0, y_f0), (0, y_r0), (-top_b, y_r0), (-top_f, y_f0)]), True),
                   ("right side", Polygon([(fw, y_f0), (fw + top_f, y_f0), (fw + top_b, y_r0), (fw, y_r0)]), True),
                   ("left tear", Polygon([(-top_f, y_f0), (-top_b, y_r0), (-top_b, y_f0)]), False),
                   ("right tear", Polygon([(fw + top_f, y_f0), (fw + top_b, y_f0), (fw + top_b, y_r0)]), False)]
    tray.creases = [("floor / front", _seg(0, 0, fw, 0)), ("floor / back", _seg(0, fd, fw, fd)),
                    ("floor / left", _seg(0, y_f0, 0, y_r0)), ("floor / right", _seg(fw, y_f0, fw, y_r0)),
                    ("back / lid", _seg(-t / 2, y_top, fw + t / 2, y_top))]
    tray.half_cuts = [("header fold", _seg(-t / 2, y_fold, fw + t / 2, y_fold))]
    tray.perfs = [("front tear line", _seg(-t / 2, -lip, fw + t / 2, -lip)), ("left tear line", _seg(-top_f, y_f0, -top_b, y_r0)),
                  ("right tear line", _seg(fw + top_f, y_f0, fw + top_b, y_r0))]
    hinges = [sf.Hinge("front panel", "floor", "floor / front", 90), sf.Hinge("front tear", "front panel", "front tear line", 0),
              sf.Hinge("back panel", "floor", "floor / back", 90), sf.Hinge("left side", "floor", "floor / left", 90), sf.Hinge("right side", "floor", "floor / right", 90),
              sf.Hinge("left tear", "left side", "left tear line", 0), sf.Hinge("right tear", "right side", "right tear line", 0),
              sf.Hinge("header back", "back panel", "back / lid", 0), sf.Hinge("header front", "header back", "header fold", 180, t)]
    locks, glue = [], []
    w = g["flap_mm"]
    low = t / 2 + gap + r.clear
    for side, wall, sign, hinge_x in (("left", "left side", -1, 0.0), ("right", "right side", 1, fw)):
        for end, y0, inward, high in (("front", y_f0, -1, lip + t / 2 - r.clear), ("back", y_r0, 1, h_b + t / 2 - r.clear)):
            name = "%s %s flap" % (end, side)
            a, b = hinge_x + sign * low, hinge_x + sign * high
            cut = min(w / 3, (high - low) / 3)
            polygon = Polygon([(a, y0), (b, y0), (b - sign * cut, y0 + inward * w), (a + sign * cut, y0 + inward * w)])
            tray.faces.append((name, polygon, False))
            crease = "%s %s fold" % (end, side)
            tray.creases.append((crease, _seg(a, y0, b, y0)))
            hinges.append(sf.Hinge(name, wall, crease, 90))
            zone = polygon.buffer(-1.5, join_style=2).difference(_seg(a, y0, b, y0).buffer(2.0, cap_style=1))
            if not zone.is_empty:
                glue.append((name, zone))
    from shapely.geometry import MultiPoint
    tray.corner_relief = MultiPoint([(0, 0), (fw, 0), (0, fd), (fw, fd), (0, y_f0), (fw, y_f0), (0, y_r0), (fw, y_r0)]).buffer(2 * t + gap)
    # the liner's lock: a tab at its free edge turns through the lid just above its hinge
    root = y_liner
    tab_len = t + gap
    tab_name = "header lock tab"
    x_mid = fw / 2
    tab_w = max(20.0, fw * .4)
    tray.faces.append((tab_name, _tab(x_mid - tab_w / 2, root, x_mid + tab_w / 2, root + tab_len + t / 2, "top"), False))
    tray.creases.append(("header lock fold", _seg(x_mid - tab_w / 2, root, x_mid + tab_w / 2, root)))
    hinges.append(sf.Hinge(tab_name, "header front", "header lock fold", 90))
    # the liner's free edge lands one caliper above the hinge: the tab, turned, passes the lid at that height
    y_slot = y_fold - liner
    _tab_slot(tray, "header lock slot", x_mid, y_slot, tab_w + 2 * r.end, t + r.play, "header back")
    locks.append(sf.Lock("the header's liner into the lid", ("tray", tab_name), ("tray", "header lock slot"), "flush", t))
    # the stairs, each with a rear leg
    rows = record["layout"]["rows"]
    x0, x1 = g["collar_x_mm"]
    collars, seats, risers = g["collars_z_mm"], g["seats_z_mm"], g["risers_y_mm"]
    collar, collar_plan = _stair("collar", "COLLAR — fold the stair; push its feet through the floor", (x0, x1), r, seats_z=collars, y_front=g["y_leg_mm"], ys_rise=risers,
                                 y_end=g["y_rear_mm"], leg_to=0.0, holes=g["holes"], floor_tab_x=g["seat_tab_x_mm"], rear_feet=g["rear_tab_x_mm"])
    parts = [tray, collar]
    plans = {"tray": sf.PartPlan("floor", sf.translation(t / 2, t / 2, t / 2), hinges), "collar": collar_plan}
    for index, x in enumerate(g["seat_tab_x_mm"], 1):
        slot = "floor slot collar %d" % index
        _tab_slot(tray, slot, x, g["y_leg_mm"], r.tab_w + 2 * r.end, t + r.play, "floor")
        locks.append(sf.Lock("collar into the floor %d" % index, ("collar", "collar foot %d" % index), ("tray", slot), "flush", t))
    for index, x in enumerate(g["rear_tab_x_mm"], 1):
        slot = "floor slot collar rear %d" % index
        _tab_slot(tray, slot, x, g["y_rear_mm"], r.tab_w + 2 * r.end, t + r.play, "floor")
        locks.append(sf.Lock("collar into the floor, rear %d" % index, ("collar", "collar rear foot %d" % index), ("tray", slot), "flush", t))
    joints = [sf.Joint(("tray", "front left flap"), ("tray", "front panel"), "lap", "flap against the front panel"),
              sf.Joint(("tray", "front right flap"), ("tray", "front panel"), "lap", "flap against the front panel"),
              sf.Joint(("tray", "back left flap"), ("tray", "back panel"), "lap", "flap against the back panel"),
              sf.Joint(("tray", "back right flap"), ("tray", "back panel"), "lap", "flap against the back panel"),
              sf.Joint(("collar", "collar leg"), ("tray", "floor"), "edge", "the collar's leg on the floor"),
              sf.Joint(("collar", "collar tread 1"), ("tray", "left side"), "edge", "the collar against the side wall"),
              sf.Joint(("collar", "collar tread 1"), ("tray", "right side"), "edge", "the collar against the side wall"),
              sf.Joint(("collar", "collar rear leg"), ("tray", "floor"), "edge", "the collar's rear leg on the floor")]
    if rows > 1:
        y_seat = risers[0] + t + gap
        seat_risers = [y + t + gap for y in risers[1:]]
        y_seat_end = g["y_rear_mm"] - t - gap
        seat, seat_plan = _stair("seat", "SEATS — fold the stair; push its feet through the floor", (x0, x1), r, seats_z=seats[1:], y_front=y_seat, ys_rise=seat_risers,
                                 y_end=y_seat_end, leg_to=0.0, floor_tab_x=g["seat_tab_x_mm"], rear_feet=g["seat_rear_x_mm"])
        parts.append(seat)
        plans["seat"] = seat_plan
        for index, x in enumerate(g["seat_tab_x_mm"], 1):
            slot = "floor slot seat %d" % index
            _tab_slot(tray, slot, x, y_seat, r.tab_w + 2 * r.end, t + r.play, "floor")
            locks.append(sf.Lock("seats into the floor %d" % index, ("seat", "seat foot %d" % index), ("tray", slot), "flush", t))
        for index, x in enumerate(g["seat_rear_x_mm"], 1):
            slot = "floor slot seat rear %d" % index
            _tab_slot(tray, slot, x, y_seat_end, r.tab_w + 2 * r.end, t + r.play, "floor")
            locks.append(sf.Lock("seats into the floor, rear %d" % index, ("seat", "seat rear foot %d" % index), ("tray", slot), "flush", t))
        joints.append(sf.Joint(("seat", "seat leg"), ("tray", "floor"), "edge", "the seat stair's leg on the floor"))
    header_stub = tray
    _add_brace(parts, plans, locks, joints, tray, header_stub, v, g, r)
    # the brace's slot on the lid, at its height above the hinge (flat y grows up the lid)
    brace_slot = next(row for row in tray.slots if row["id"] == "brace slot")
    y_lid = y_top + (g["brace"]["top_z_mm"] - (g["back_z_mm"] - t / 2))
    x_lid = v["width_mm"] / 2 - t / 2
    half_l, half_w = brace_slot["length_mm"] / 2, brace_slot["width_mm"] / 2
    brace_slot["polygon"] = _rect(x_lid - half_l, y_lid - half_w, x_lid + half_l, y_lid + half_w)
    products = []
    pw, pd, ph = v["product_width_mm"], v["product_depth_mm"], v["product_height_mm"]
    for hole in g["holes"]:
        row = hole["row"]
        z = t + seats[row - 1]
        products.append({"index": hole["index"], "row": row, "column": hole["column"], "frame": sf.translation(hole["x_mm"] + t / 2, hole["y_mm"] + t / 2, z), "w": pw, "d": pd, "h": ph,
                         "cap": v.get("product_cap_mm") or 0.0, "plate": ("collar", "collar tread %d" % row),
                         "seat": ("tray", "floor") if row == 1 else ("seat", "seat tread %d" % (row - 1))})
    walls = ["left side", "right side", "front panel", "back panel", "front tear", "left tear", "right tear"] + \
        ["%s %s flap" % (end, side) for end in ("front", "back") for side in ("left", "right")]
    shut = {"header back": 90.0}
    steps = [sf.Step("At the factory: lay the tray flat, print side down.", torn=False),
             sf.Step("Fold the walls up and fold the corner flaps in. Glue each flap to its panel, in the marked zones.", close={"tray": walls}, torn=False),
             sf.Step("Fold the collar stair over it and push its feet through the floor.", part="collar", approach=(0.0, 0.0, 60.0), torn=False),
             sf.Step("Double the lid's liner under it and turn its tab through the slot.", close={"tray": ["header front", tab_name]}, torn=False),
             sf.Step("Stand the products in their openings and close the lid: it ships as a closed box.", products=True, angles=shut, torn=False),
             sf.Step("In the store: tear the front wall along its perforation and each side wall along its slope. Swing the lid up in line with the back wall.", angles={"header back": 0.0}),
             sf.Step("Hook the brace into the lid and into the back wall: it holds the lid upright.", part="brace", approach=(0.0, 40.0, 0.0)),
             sf.Step("Check every product is seated, and it is ready.", products=True)]
    if rows > 1:
        steps[2:2] = [sf.Step("Fold the seat stair and push its feet through the floor.", part="seat", approach=(0.0, 0.0, 60.0), torn=False)]
    plan = sf.Plan(plans, joints, locks, steps, products)
    plan.removed = {("tray", "front tear"), ("tray", "left tear"), ("tray", "right tear")}
    title = "%s %s — flat die at 100 %%" % (st.label(record["template"]["id"]), record["template"]["version"])
    die = _place(parts, title, t, plan, row_width=max(tray.outline().bounds[2] - tray.outline().bounds[0], 420))
    mx, my = die.moves["tray"]
    from shapely.affinity import translate
    die.glue = [(name, translate(zone, mx, my)) for name, zone in glue]
    return die


def ship_report(record, die):
    """The same die as it ships: the lid over the tray, the walls whole. It must close: the walls at the lid's height, the lid on them, the
    products under it."""
    import copy
    plan = copy.copy(die.plan)
    plan.removed = set()
    plan.parts = {name: copy.copy(row) for name, row in die.plan.parts.items() if name != "brace"}
    tray = plan.parts["tray"]
    tray.hinges = [sf.Hinge(h.child, h.parent, h.crease, 90 if h.child == "header back" else h.angle, h.offset) for h in tray.hinges]
    folded = sf.fold(die, plan)
    size = sf.closed_size(folded)
    tops = [(p["frame"] @ np.array([0.0, 0.0, p["h"], 1.0]))[2] for p in plan.products]
    lid = folded["tray", "header back"]
    lid_z = float(lid.corners()[:, 2].mean())
    v = record["inputs"]
    closed = {"width_mm": _r(size["x"][1] - size["x"][0]), "depth_mm": _r(size["y"][1] - size["y"][0]), "height_mm": _r(size["z"][1] - size["z"][0])}
    return {"closed_mm": closed, "lid_z_mm": _r(lid_z), "tallest_product_mm": _r(max(tops)), "head_room_mm": _r(lid_z - t_half(v) - max(tops)),
            "passed": lid_z - t_half(v) >= max(tops) and abs(closed["width_mm"] - v["width_mm"]) <= cd.TOL_MM + v["board_mm"]}


def t_half(v):
    return v["board_mm"] / 2


def _solve_lid(brief_product, *, rows, columns, envelope, board, provisional, header_height=None, front_height=None, outline=None):
    """Template 3: the walls stand to the rear row's top so the lid clears it in the box; the lid's depth is the tray's, so the header is as
    tall as the tray is deep; the brace is always there, since a hinge holds nothing up."""
    common = st.common()
    r = Rules(board)
    t = r.t
    pw, pd, ph, cap = (brief_product[key] for key in ("width_mm", "depth_mm", "height_mm", "cap_mm"))
    W, D, H = (float(envelope.get(key) or 0.0) for key in ("width_mm", "depth_mm", "height_mm"))
    changes = []
    bar = face_bar(common, ph, cap)
    o, o_d = pw + r.clearance, pd + r.clearance
    need_w = t + columns * (o + 2 * r.clear) + 2 * (t / 2 + r.g)
    inset = max(2 * (t + r.g), r.clear + (t + r.play) / 2)
    need_d = t + inset + r.clear + o_d + r.web + inset + (rows - 1) * (o_d + 2 * r.clear)
    for name, value, need in (("width", W, need_w), ("depth", D, need_d)):
        if value < need - 1e-9:
            changes.append({"measure": name + "_mm", "from_mm": value or None, "to_mm": math.ceil(need), "why": "the openings, the webs between them and the walls need it"})
    W, D = max(W, math.ceil(need_w)), max(D, math.ceil(need_d))
    front = max(float(front_height or st.record("lid_header_tray")["limits"]["front_lip_mm"]), 2 * t + 2 * r.g + r.clear + 6.0)
    v = {"product_width_mm": float(pw), "product_depth_mm": float(pd), "product_height_mm": float(ph), "product_cap_mm": float(cap), "width_mm": float(W), "depth_mm": float(D),
         "height_mm": float(H), "board_mm": t, "clearance_mm": r.clearance, "front_height_mm": front, "face_bar_mm": bar}

    def record_for(rise, back_z):
        vv = dict(v)
        fw, fd = W - t, D - t
        x0, x1 = t / 2 + r.g, fw - t / 2 - r.g
        # the stair stands clear of the corner flaps, front and back
        inset = max(2 * (t + r.g), r.clear + (t + r.play) / 2)    # its feet's slots clear of the floor's folds
        y_leg = inset
        y_rear = fd - inset
        first, last = y_leg + r.clear + o_d / 2, y_rear - r.web - o_d / 2
        pitch = (last - first) / (rows - 1) if rows > 1 else 0.0
        ys = [first + pitch * i for i in range(rows)] if rows > 1 else [(first + last) / 2]
        x_pitch = (x1 - x0) / columns
        xs = [x0 + x_pitch * (c + .5) for c in range(columns)]
        seats = [i * rise for i in range(rows)]
        collars = [r.hold + s for s in seats]
        risers = [(ys[i] + ys[i + 1]) / 2 for i in range(rows - 1)]
        holes = [{"index": rw * columns + c + 1, "row": rw + 1, "column": c + 1, "x_mm": _r(xs[c]), "y_mm": _r(ys[rw]), "w_mm": _r(o), "d_mm": _r(o_d), "size_mm": _r(max(o, o_d))}
                 for rw in range(rows) for c in range(columns)]
        lid = fd
        g = {"floor_mm": [fw, fd], "front_crease_mm": front - t, "back_crease_mm": back_z - t, "lid_mm": lid, "back_z_mm": back_z, "flap_mm": min(r.flap, fd / 4), "seat_tab_x_mm": _pair(fw, .35, .65, r),
             "rear_tab_x_mm": _pair(fw, .15, .85, r), "seat_rear_x_mm": _pair(fw, .35, .65, r), "hold_mm": r.hold, "rise_mm": rise, "row_pitch_mm": _r(pitch),
             "column_pitch_mm": _r(x_pitch), "y_leg_mm": _r(y_leg), "y_rear_mm": _r(y_rear), "risers_y_mm": [_r(y) for y in risers], "seats_z_mm": [_r(s) for s in seats], "collars_z_mm": [_r(c) for c in collars],
             "holes": holes, "collar_x_mm": [_r(x0), _r(x1)], "opening_mm": [_r(o), _r(o_d)], "web_between_openings_mm": _r(pitch - o_d) if rows > 1 else None,
             "header_leaf_mm": lid, "header_plane_y_mm": _r(D - t), "header_top_z_mm": _r(back_z - t / 2 + lid)}
        g["brace"] = {"width_mm": _r(max(min(W * .4, 60.0), r.tab_w + 2 * r.clear)), "top_z_mm": _r(back_z + lid * .55), "foot_mm": r.brace, "low_z_mm": _r(back_z * .55)}
        vv["height_mm"] = _r(back_z - t / 2 + lid)
        vv["header_height_mm"] = lid
        return _record("lid_header_tray", board, vv, g, rows, columns)

    def seen(rec):
        die = build_lid_tray(rec)
        return sf.sightlines_report(die.plan, sf.fold(die, die.plan), width=W, face_bar_mm=bar)

    rise = 0.0
    if rows > 1:
        lo, hi = 0.0, float(ph)
        for _step in range(9):
            middle = (lo + hi) / 2
            if all(row["products_passed"] for row in seen(record_for(middle, middle * (rows - 1) + ph + 60.0))["eyes"]):
                hi = middle
            else:
                lo = middle
        rise = math.ceil(hi * 2) / 2
    # the lid must clear the rear row in the box: the back wall stands above its top
    back_z = math.ceil(t + rise * (rows - 1) + ph + t + 1.0)
    start, tallest = back_z, back_z + 2 * ph
    while back_z < tallest and not seen(record_for(rise, back_z))["passed"]:
        back_z += 1.0
    back_z = back_z if back_z < tallest else start
    record = record_for(rise, back_z)
    closed = record["inputs"]["height_mm"]
    if H and abs(closed - H) > cd.TOL_MM:
        changes.append({"measure": "height_mm", "from_mm": H, "to_mm": closed, "why": "the walls must clear the rear row in the box, and the lid is as tall as the tray is deep"})
    record["changes"] = changes
    return record


BUILDERS = {"counter_tray_header": build_counter_tray, "stepped_tiered": build_counter_tray, "slanted_front": build_slanted, "tester_unit": build_slanted,
            "lid_header_tray": build_lid_tray, "flat_tray_testers": build_flat_tray}


def layer_law(die):
    """The die's own layers, per the file's law: cut, crease, perforation, half-cut, glue, safe, bleed, each apart, and no line of the die on
    two of them."""
    geo = cd.layer_geometry(die)
    keys = ("cut", "crease", "perf", "half_cut", "glue", "safe", "bleed")
    missing = [key for key in keys if key not in geo]
    creases = {tuple(map(tuple, line)) for line in geo["crease"]}
    cuts = {tuple(map(tuple, line)) for line in geo["cut"]}
    return {"layers": list(keys), "missing": missing, "shared": len(creases & cuts), "counts": {key: len(geo[key]) for key in keys}, "passed": not missing and not creases & cuts}


def is_template_record(record):
    return record.get("schema") == SCHEMA


def build_die(record):
    return BUILDERS[record["template"]["id"]](record)


def solve(template, *, product, rows, columns, envelope=None, board="e_flute", provisional=True, **options):
    """A template's record. ``product``: {width_mm, depth_mm, height_mm, cap_mm}; ``envelope``: the stand's {width_mm, depth_mm,
    height_mm}, each optional."""
    if template not in SOLVERS:
        raise ValueError("The engine has no working die for %s yet" % template)
    if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in (rows, columns)) or rows * columns > 100:
        raise ValueError("A stand needs whole rows and columns, at most 100 products")
    return SOLVERS[template](product, rows=rows, columns=columns, envelope=envelope or {}, board=board, provisional=provisional, **options)


#: a template that must show no bare board from the owner's eyes (part 3, §1). Where this is False the view is reported on the page and does not fail it
INSIDE_PRINTED = {"flat_tray_testers": True}
SOLVERS = {"counter_tray_header": _solve_counter_tray, "stepped_tiered": _solve_stepped, "slanted_front": _solve_slanted, "tester_unit": _solve_tester,
           "lid_header_tray": _solve_lid, "flat_tray_testers": _solve_flat}


def rules_report(record, die):
    """The type's rules file against its die: every panel, fold and lock kind it names is on the die, so the file cannot drift."""
    entry = st.record(record["template"]["id"])
    panels = {name for part in die.parts for name, _f, _p in part.faces}
    folds = {name for part in die.parts for name, _l in list(part.creases) + list(part.half_cuts) + list(part.perfs)}
    kinds = {lock.kind for lock in die.plan.locks}
    missing = {"panels": sorted(set(entry.get("panels", [])) - panels), "folds": sorted({row["fold"] for row in entry.get("folds", [])} - folds),
               "locks": sorted({row["kind"] for row in entry.get("locks", [])} - kinds)}
    return {"file": record["template"]["id"] + ".json", "missing": missing, "passed": not any(missing.values())}


def better_than_house(record, report, nesting):
    """What this die does better than the house's measured display dies and where it does not: one row per point, each from a number
    the engine measured against one measured on the references (apps/dielines/docs/research/counter_display_references.json)."""
    import json
    from pathlib import Path
    from django.conf import settings
    refs = json.loads((Path(settings.BASE_DIR) / cd.REFERENCES).read_text())
    fold = report["fold"]
    sight = report["sightlines"]
    worst = min(row["top_band_mm"] for eye in sight["eyes"] for row in eye["products"])
    v = record["inputs"]
    glue = record["production"].get("glue", "")
    rows = [
        {"point": "strength", "ours": "double front and back walls, corner flaps trapped between their leaves, %d locks, no hinge left free" % fold["locks"]["count"],
         "house": "single-ply winged trays held by lock stubs, with nothing standing above the end wall on any of the dies measured", "better": True},
        {"point": "assembly", "ours": "%d numbered steps, one person, no tools; %s" % (len(build_die(record).plan.steps), glue),
         "house": "the references are glueless too, but none carries instructions with its die", "better": True},
        {"point": "product show", "ours": "every product's top %.0f mm and the whole header's safe area seen from both of the owner's eyes (least %.0f mm), by rows risen %s mm" % (
            sight["face_bar_mm"], worst, record["geometry"].get("rise_mm", 0)),
         "house": "flat inserts: one level, every row at the same height; no sightline was ever measured", "better": True} if not record["geometry"].get("testers") else
        {"point": "product show", "ours": "one level, as the house's; every shade's colour measured from both eyes (worst %.0f %% of its window, the tester's), and the whole header above the rear row" % (
            100 * report["shades"]["worst_share"]),
         "house": "flat inserts: one level; no sightline was ever measured, and no die here holds a tester", "better": True},
        {"point": "holding", "ours": "a product stands on a seat and passes a deck %s mm above it; clearance %.1f mm; lean ≤ %.0f°" % (record["geometry"].get("hold_mm"), v["clearance_mm"], record["production"]["rules"]["max_lean_deg"]),
         "house": "two plies, the second 3 mm larger (LP-2015, BL-2050), on the floor", "better": True},
        {"point": "material use", "ours": "%.0f %% of a %d × %d mm sheet, %d sets, parts nested in each other's waste" % (100 * nesting["best"]["yield"], nesting["best"]["sheet_mm"][0], nesting["best"]["sheet_mm"][1], nesting["best"]["sets"]),
         "house": "not measured: the references carry no nest, and a tall header costs board they never spent", "better": None},
        {"point": "fold allowances", "ours": "every fold stated, closed size measured at %s" % ", ".join("%.1f" % fold["dimensions"]["closed_mm"][k] for k in ("width_mm", "depth_mm", "height_mm")),
         "house": refs["common"]["wall_crease_inset_mm"], "better": True},
        {"point": "die files", "ours": "cut, crease, perforation, half-cut each its own layer and spot", "house": "cut near-black, crease red, both solid; no spot names", "better": True},
        {"point": "where it does not beat them", "ours": "taller, and more board than a single-ply tray: a double back wall costs its area twice", "house": "the white-card trays use a fraction of the board for a flat product", "better": False}]
    return {"references": [ref["id"] for ref in refs["references"]], "rows": rows}


def qualify(record, die=None):
    """Every proof of the owner's §3 and §4 that a number can settle, read from the die folded. ``passed`` only if all hold."""
    die = die or build_die(record)
    plan = die.plan
    folded = sf.fold(die, plan)
    v = record["inputs"]
    size = sf.closed_size(folded)
    closed = {"width_mm": size["x"][1] - size["x"][0], "depth_mm": size["y"][1] - size["y"][0], "height_mm": size["z"][1] - size["z"][0]}
    limits = {key: (v[key] + (record["geometry"]["brace"]["foot_mm"] if key == "depth_mm" and record["geometry"].get("brace") else 0.0)) for key in closed}
    # a brace's strut stands at an angle: its board's own thickness reaches a little past its crease
    slack = {"depth_mm": v["board_mm"]} if record["geometry"].get("brace") else {}
    dims = {"closed_mm": {k: _r(a) for k, a in closed.items()}, "envelope_mm": limits,
            "passed": all(abs(closed[k] - limits[k]) <= cd.TOL_MM + slack.get(k, 0.0) for k in closed)}
    collisions = sf.interference(plan, folded)
    joints = sf.joints_report(plan, folded)
    locks = sf.locks_report(plan, folded, die)
    fit = sf.fit_report(plan, folded, clearance_mm=v["clearance_mm"])
    art = sf.art_report(folded, die)
    sight = sf.sightlines_report(plan, folded, width=v["width_mm"], face_bar_mm=v["face_bar_mm"])
    grain = sf.grain_report(die, record)
    allowances = sf.allowances_report(die, record)
    trade = cd.trade_rules(record, die)
    slots = sf.slots_report(die, Rules(record["board"]["preset"]).clear)
    common = st.common()["rules"]
    tip = sf.tip_report(plan, folded, mass_each_g=common["product_mass_g"]["value"])
    Z = 2 * (v["width_mm"] + v["depth_mm"])
    bct = common["mckee_constant"]["value"] * common["ect_e_flute_kn_m"]["value"] * math.sqrt(Z * v["board_mm"])
    strength = {"box_compression_n": round(bct), "at_80_rh_n": round(bct * (1 - common["humid_loss_80rh"]["value"])), "load_n": round(tip["mass_g"] * 0.00981, 1),
                "tip": tip, "provisional": True,
                "words": "⟪PROVISIONAL⟫ McKee on the tray as a closed box, ECT assumed, the product's mass assumed: an estimate until a loaded sample is tested"}
    rules = rules_report(record, die)
    shades = sf.shade_report(plan, folded, width=v["width_mm"], names=record.get("column_shades"))
    view = sf.view_report(plan, folded, die)
    header_locks = [row for row in locks["locks"] if "header" in row["id"]]
    locks["header_locked"] = bool(header_locks) and all(row["ok"] for row in header_locks)
    fold_ok = dims["passed"] and joints["passed"] and not collisions and locks["passed"] and locks["header_locked"] and fit["passed"] and art["passed"]
    ship = None
    if record["template"]["id"] == "lid_header_tray":
        ship = ship_report(record, die)
        fold_ok = fold_ok and ship["passed"]
    return {"schema": "stand_template/qualification-1", "ship": ship, "rules_file": rules, "template": "%s/%s" % (record["template"]["id"], record["template"]["version"]),
            "fold": {"passed": fold_ok, "dimensions": dims, "joints": joints, "collisions": collisions, "locks": locks, "fit": fit, "art": art},
            "sightlines": sight, "grain": grain, "allowances": allowances, "trade_rules": trade, "slots": slots, "strength": strength,
            "shades": shades, "view": view,
            "passed": fold_ok and sight["passed"] and grain["passed"] and allowances["passed"] and trade["passed"] and slots["passed"] and rules["passed"]
            and shades["passed"] and (view["passed"] or not INSIDE_PRINTED.get(record["template"]["id"]))}
