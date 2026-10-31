"""The fold check: does this dieline fold and close as the trade draws it — pure geometry, no 3D render, well under a
second, run on every dieline before he sees it.

[His second goal of 2026-10-06 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c34a518), item 2: "A FAST FOLD CHECK INSIDE
THE SYSTEM: pure geometry, no Blender, no 3D renders, under a second, run on every dieline before I see it: every flap
matches the edge it closes onto, panels close square, no gaps or overlaps, the tuck reaches its slot, every rule above
holds. A failure is fixed or shown to me, never hidden."]

It reads the die as drawn — its cut outline, its creases, its slits and its named parts — never the engine's own claims
about them: each panel's width between its creases, each flap's reach, measured. Folding is the rigid 90° turn about a
crease, so where a flap lands is plain arithmetic on the flat: a lid hinged on one wall reaches across the opening by
its depth (it must land on the far wall's top edge — the tuck reaches its slot); two dust flaps hinged on opposite
walls meet in the middle unless each stays short of half the opening; the glue flap, turned in, lies on the last panel's
inside and must stay clear of that panel's far crease. Each finding is ``{"id", "rule", "ok", "measured", "expected",
"words"}``; the rules are ``apps/dielines/docs/TRADE_RULES.md``'s.
"""
from __future__ import annotations

import re
import time

from shapely.geometry import LineString, Point

SCHEMA = "fold_check/1.0"
#: a measure agrees with what it closes onto within this (mm) — a die-maker's working tolerance (B3)
TOL_MM = 0.15
FAILED = "DIELINE_FOLD_CHECK_FAILED"
BODY = ("back", "side_left", "front", "side_right")


def _finding(out, fid, rule, ok, measured, expected, words):
    out.append({"id": fid, "rule": rule, "ok": bool(ok), "measured": measured, "expected": expected, "words": words})


def _r(v):
    return round(float(v), 3)


def check(coords) -> dict:
    """``{"schema", "passed", "findings": [...], "failed": [...], "ms"}`` for the die ``coords`` (a
    ``DielineCoordinates``)."""
    t0 = time.perf_counter()
    f: list = []
    panels = {p.name: p for p in coords.panels}
    t = float(getattr(coords, "board_thickness_mm", 0.0) or 0.0)
    cut = coords.cut_polygon
    comps = dict(coords.components or [])
    verticals = sorted({round(x0, 4) for x0, y0, x1, y1 in coords.fold_lines if abs(x0 - x1) < 1e-6})
    horizontals = [(x0, y0, x1, y1) for x0, y0, x1, y1 in coords.fold_lines if abs(y0 - y1) < 1e-6]

    # -- the outline itself: one closed cut, nothing overlapping in the flat (L3, M10) ------------------------------
    _finding(f, "cut_one_outline", "L3", cut.geom_type == "Polygon" and cut.is_valid,
             cut.geom_type, "one valid polygon", "The die's cut is one closed outline.")
    names = [n for n in comps if n != "main-body"]
    overlap = 0.0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = max(overlap, comps[a].intersection(comps[b]).area)
    _finding(f, "no_flat_overlap", "M3", overlap < 1e-4, _r(overlap), 0.0,
             "No two flaps overlap on the flat sheet (largest overlap %.3f mm²)." % overlap)

    # -- every crease scores board, never a cut edge or thin air (L3, M10) ----------------------------------------
    inner = cut.buffer(-1e-4)
    bad = []
    for x0, y0, x1, y1 in coords.fold_lines:
        line = LineString([(x0, y0), (x1, y1)])
        if line.length < 1e-6:
            bad.append((x0, y0, x1, y1))
            continue
        for k in (0.1, 0.5, 0.9):
            if not inner.contains(line.interpolate(k, normalized=True)):
                bad.append((_r(x0), _r(y0), _r(x1), _r(y1)))
                break
    _finding(f, "creases_on_board", "L3", not bad, bad[:4], [],
             "Every crease runs across board, never along a cut edge%s." % (
                 "" if not bad else " — %d do not: %s" % (len(bad), bad[:3])))

    if not all(n in panels for n in BODY):
        _finding(f, "tube_panels", "S5", False, sorted(panels), list(BODY),
                 "The die has no four-panel tube this check can fold.")
        return _done(f, t0)

    # -- the tube closes square (S5, T2, M5): opposite panels equal between their creases ----------------------------
    pb, ps1, pf, ps2 = (panels[n] for n in BODY)
    widths = {n: panels[n].width for n in BODY}
    _finding(f, "tube_square", "T7", abs(pb.width - pf.width) <= TOL_MM and abs(ps1.width - ps2.width) <= TOL_MM,
             {k: _r(v) for k, v in widths.items()}, "back = front, left side = right side (± %g)" % TOL_MM,
             "The tube closes square: back %.2f / front %.2f mm, sides %.2f / %.2f mm between their creases."
             % (pb.width, pf.width, ps1.width, ps2.width))
    for name in ("back", "side_left", "front"):
        x_right = panels[name].x + panels[name].width
        _finding(f, "crease_%s" % name, "D1", any(abs(x_right - v) < 1e-3 for v in verticals), _r(x_right),
                 "a body crease", "The %s panel's right edge is creased." % name.replace("_", " "))

    # -- the glue flap lands on the last panel, clear of its far crease (G1–G3, M4) ----------------------------------
    glue = getattr(coords, "glue_tab_polygon", None)
    if glue is not None:
        gx0, gy0, gx1, gy1 = glue.bounds
        gw = gx1 - gx0
        free = [y for x, y in glue.exterior.coords if abs(x - gx0) < 1e-6]
        free_len = (max(free) - min(free)) if free else 0.0
        crease_len = gy1 - gy0
        _finding(f, "glue_clear", "G2", 8.0 - 1e-6 <= gw <= ps2.width - 3.0 + 1e-6, _r(gw),
                 "8 to %.2f mm (the right side %.2f less 3)" % (ps2.width - 3.0, ps2.width),
                 "The glue flap (%.2f mm) turned in lies on the right side's inside, clear of its far crease." % gw)
        _finding(f, "glue_within_panel", "G1", gy0 >= ps2.y - 1e-6 and gy1 <= ps2.y + ps2.height + 1e-6,
                 [_r(gy0), _r(gy1)], [_r(ps2.y), _r(ps2.y + ps2.height)],
                 "The glue flap stays within the height of the panel it is glued to.")
        _finding(f, "glue_tapered", "G3", free_len < crease_len - 1.0, _r(crease_len - free_len), "> 1 mm",
                 "The glue flap's ends are tapered (its free edge %.2f mm shorter than its crease)."
                 % (crease_len - free_len))

    # -- each end: the lid, its tongue, its slits, the dust flaps under it (K1–K6, F1–F4, T3, T4, M1–M3, M6) ---------
    top_y, bottom_y = coords.body_top_y, coords.body_bottom_y
    for end in ("top", "bottom"):
        tucks = [n for n in comps if re.match(r"^%s-(back|front)-tuck$" % end, n)]
        dusts = {side: comps.get("%s-%s-dust" % (end, side)) for side in ("left", "right")}
        locks = [n for n in comps if n.startswith("%s-" % end) and n.endswith("-lock")]
        if locks and not tucks:
            _finding(f, "%s_closure" % end, "S3", False, locks, "a modelled closure",
                     "The %s is a crash-lock base this system does not model to lock (ECMA A60.20.00.03 needs its hook "
                     "flaps, glue creases and lock notches)." % end)
            continue
        if len(tucks) != 1:
            _finding(f, "%s_tuck" % end, "S1", False, tucks, "one tuck", "The %s has no one tuck lid." % end)
            continue
        name = tucks[0]
        carrier = name.split("-")[1]
        enters = "front" if carrier == "back" else "back"
        lid = comps[name]
        lx0, ly0, lx1, ly1 = lid.bounds
        sign = -1.0 if end == "top" else 1.0
        within = [h for h in horizontals if h[0] >= lx0 - 1e-6 and h[2] <= lx1 + 1e-6
                  and (ly0 - 1e-6) <= h[1] <= (ly1 + 1e-6)]
        if len(within) < 2:
            _finding(f, "%s_tuck_fold" % end, "K1", False, len(within), 2,
                     "The %s lid has no creased hinge and tuck fold to fold on." % end)
            continue
        hinge = max(within, key=lambda h: h[1]) if end == "top" else min(within, key=lambda h: h[1])
        fold = min(within, key=lambda h: h[1]) if end == "top" else max(within, key=lambda h: h[1])
        hinge_y, fold_y = hinge[1], fold[1]
        tip_y = ly0 if end == "top" else ly1
        depth = abs(hinge_y - fold_y)
        tongue = abs(fold_y - tip_y)
        side_w = (ps1.width + ps2.width) / 2.0
        # the lid spans the opening: folded about its hinge it reaches the far wall's top edge — the tuck reaches its slot
        _finding(f, "%s_tuck_reaches" % end, "K3", abs(depth - side_w) <= TOL_MM, _r(depth), _r(side_w),
                 "The %s lid (%.2f mm deep) reaches across the opening (%.2f mm between the walls' creases) and its "
                 "tongue drops behind the %s." % (end, depth, side_w, enters))
        lid_w = LineString([(hinge[0], hinge_y), (hinge[2], hinge_y)]).length
        carrier_w = panels[carrier].width
        _finding(f, "%s_lid_width" % end, "T4", carrier_w - t - TOL_MM <= lid_w <= carrier_w - t + TOL_MM + 1e-6,
                 _r(lid_w), _r(carrier_w - t),
                 "The %s lid's hinge (%.2f mm) is the %s's width less one caliper: it closes between the side walls."
                 % (end, lid_w, carrier))
        _finding(f, "%s_tongue" % end, "K4", 8.0 - 1e-6 <= tongue <= min(depth, (bottom_y - top_y) / 3.0) + 1e-6,
                 _r(tongue), "8 mm to the lid's depth",
                 "The %s tongue is %.2f mm: long enough to hold, short of the lid's depth." % (end, tongue))
        # the tongue is narrower than the lid (set back t each side) so it slides behind the far wall
        band = lid.intersection(LineString([(lx0 - 1, fold_y + sign * tongue / 2.0),
                                            (lx1 + 1, fold_y + sign * tongue / 2.0)]))
        tw = band.length if not band.is_empty else 0.0
        _finding(f, "%s_tongue_width" % end, "T4", tw <= lid_w - 2 * t + TOL_MM, _r(tw), "≤ %.2f" % (lid_w - 2 * t),
                 "The %s tongue (%.2f mm) is set back from the lid's edges, so it slides in past the walls." % (end, tw))
        # the hinge sits one caliper further out than the dust flaps' — the lid lies flat over their ply (T3)
        dust_hinge_y = top_y if end == "top" else bottom_y
        offset = (dust_hinge_y - hinge_y) * (1 if end == "top" else -1)
        _finding(f, "%s_lid_over_dust" % end, "T3", abs(offset - t) <= 0.05 + 1e-6, _r(offset), _r(t),
                 "The %s lid's hinge sits %.2f mm outside the dust flaps' hinges (one caliper: %.2f mm)."
                 % (end, offset, t))
        # the lock slits at the tuck fold's ends, each at least the dust flap's shoulder long (K6, F3)
        slits = [s for s in coords.slit_lines if abs(s[1] - fold_y) < 1e-6 and abs(s[3] - fold_y) < 1e-6]
        # each slit's reach in from the lid's own edge (the cut runs from the edge along the fold)
        mid_x = (lx0 + lx1) / 2.0
        slit_len = min(((max(s[0], s[2]) - lx0) if max(s[0], s[2]) <= mid_x else (lx1 - min(s[0], s[2]))
                        for s in slits), default=0.0)
        # -- the dust flaps at this end ---------------------------------------------------------------------------
        front_w = panels["front"].width
        reach = {}
        for side, poly in dusts.items():
            if poly is None:
                _finding(f, "%s_%s_dust" % (end, side), "F1", False, None, "a dust flap",
                         "The %s %s side has no dust flap." % (end, side))
                continue
            dx0, dy0, dx1, dy1 = poly.bounds
            reach[side] = dy1 - dy0
            panel = panels["side_%s" % side]
            _finding(f, "%s_%s_dust_fits" % (end, side), "T4", (dx1 - dx0) <= panel.width - t + TOL_MM,
                     _r(dx1 - dx0), "≤ %.2f" % (panel.width - t),
                     "The %s %s dust flap (%.2f mm across) folds in between the front and the back."
                     % (end, side, dx1 - dx0))
            # its shoulder faces the panel the tongue enters (F3): measured as the inset of each edge halfway out —
            # past the shoulder's step: the straight edge stays on its crease's line, the shouldered one has stepped in
            base_y = dy1 if end == "top" else dy0
            probe_y = base_y + sign * (0.5 * (dy1 - dy0))
            row = poly.intersection(LineString([(dx0 - 1, probe_y), (dx1 + 1, probe_y)]))
            rx0, _a, rx1, _b = row.bounds if not row.is_empty else (dx0, 0, dx1, 0)
            left_in, right_in = rx0 - dx0, dx1 - rx1
            toward_right = (side == "left") == (enters == "front")
            ok = (right_in > left_in + 0.2) if toward_right else (left_in > right_in + 0.2)
            _finding(f, "%s_%s_dust_shoulder" % (end, side), "F3", ok, [_r(left_in), _r(right_in)],
                     "shouldered toward the %s" % enters,
                     "The %s %s dust flap is shouldered on the side the tongue enters (the %s)."
                     % (end, side, enters))
            # the shoulder's tab: how far from the hinge its shouldered edge runs full width before it steps in — the
            # length of board the lid's slit must take (K6)
            tab, step = 0.0, 0.05
            while tab < (dy1 - dy0):
                y = base_y + sign * (tab + step)
                cut_row = poly.intersection(LineString([(dx0 - 1, y), (dx1 + 1, y)]))
                if cut_row.is_empty:
                    break
                cx0, _c, cx1, _d = cut_row.bounds
                if ((dx1 - cx1) if toward_right else (cx0 - dx0)) > 0.05:
                    break
                tab += step
            _finding(f, "%s_%s_slit_catches" % (end, side), "K6", bool(slits) and slit_len >= tab - 1e-6,
                     _r(slit_len), "≥ the shoulder's tab %.2f" % tab,
                     "The %s lid's lock slits (%.2f mm) take the %s dust flap's shoulder (%.2f mm)."
                     % (end, slit_len, side, tab))
        if len(reach) == 2:
            meet = reach["left"] + reach["right"]
            _finding(f, "%s_dust_no_collision" % end, "F2", meet <= front_w - 1.0 + 1e-6, _r(meet),
                     "≤ %.2f (the opening %.2f less 1)" % (front_w - 1.0, front_w),
                     "The %s dust flaps (%.2f + %.2f mm) fold in without meeting across the %.2f mm opening."
                     % (end, reach["left"], reach["right"], front_w))
            _finding(f, "%s_dust_under_lid" % end, "F2", max(reach.values()) < depth, _r(max(reach.values())),
                     "< %.2f" % depth, "The %s lid covers its dust flaps." % end)
    # -- the thumb notch, in the top edge of the panel the top tongue enters (N1) ----------------------------------
    top_tuck = next((n for n in comps if re.match(r"^top-(back|front)-tuck$", n)), None)
    if top_tuck:
        enters = "front" if top_tuck.split("-")[1] == "back" else "back"
        p = panels[enters]
        probe = Point(p.x + p.width / 2.0, top_y + 0.5)
        _finding(f, "thumb_notch", "N1", not cut.contains(probe), "cut away" if not cut.contains(probe) else "board",
                 "a half-round notch", "The %s's top edge has its thumb notch, where the lid is lifted." % enters)
    # -- the bleed runs past every cut (B1) -------------------------------------------------------------------------
    bleed = getattr(coords, "bleed_polygon", None)
    if bleed is not None:
        margin = min(Point(c).distance(bleed.exterior) for c in cut.exterior.coords)
        _finding(f, "bleed", "B1", margin >= 3.0 - 0.05, _r(margin), "≥ 3",
                 "The bleed runs %.2f mm past every cut." % margin)
    return _done(f, t0)


def _done(f, t0) -> dict:
    failed = [x for x in f if not x["ok"]]
    return {"schema": SCHEMA, "passed": not failed, "findings": f, "failed": failed,
            "ms": round((time.perf_counter() - t0) * 1000.0, 2)}


def said(record: dict) -> list:
    """His words for a failed check: one line each, for the page beside Approve."""
    return ["The die does not fold as the trade draws it: %s" % x["words"] for x in record.get("failed") or []]
