"""The die writer's sheets for a stand (owner's part 2, 2026-10-31), every line from the die folded (stand_fold): the fold-up
proof, drawn step by step and then front, side, top and three-quarter, with the products seated at their true sizes; the
assembly sheet in plain words; the 1:1 cut-and-fold PDF tiled over A3 (the tiling carried from the archived
counter_tray_header_sheets.write_tiles_pdf); the nest on its press sheet. Line drawings by our own code: no 3D scene."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from reportlab.lib.colors import Color, HexColor, black
from reportlab.pdfgen import canvas
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from apps.dielines.geometry import counter_display as cd
from apps.dielines.geometry import stand_fold as sf
from apps.dielines.geometry import stand_templates as templates
from apps.dielines.geometry import stand_types as st

PT = 72 / 25.4
A3 = (420.0, 297.0)
OVERLAP_MM = 10.0
TILE_MARGIN_MM = 12.0
DRAWING_WORDS = "drawing, not a render"
INK = HexColor("#26262E")
BOARD = HexColor("#FFFFFF")
PRINTED = HexColor("#F1EBDD")
PRODUCT = HexColor("#DCDCE2")
CAP = HexColor("#B9B6A6")
RULE = HexColor("#8A8A92")
#: a view: the page's right, the page's up, and toward the reader, in the stand's frame
VIEWS = {"front": ((1, 0, 0), (0, 0, 1), (0, -1, 0)), "side": ((0, 1, 0), (0, 0, 1), (1, 0, 0)), "top": ((1, 0, 0), (0, 1, 0), (0, 0, 1))}


def three_quarter(azimuth=35.0, elevation=28.0):
    a, e = math.radians(azimuth), math.radians(elevation)
    w = np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])
    u = np.array([math.cos(a), math.sin(a), 0.0])
    v = np.cross(w, u)
    return tuple(u), tuple(v), tuple(w)


VIEWS["three-quarter"] = three_quarter()


def _rings_world(face):
    rings = []
    for piece in getattr(face.solid, "geoms", [face.solid]):
        rings.append([face.world(np.asarray(piece.exterior.coords))] + [face.world(np.asarray(ring.coords)) for ring in piece.interiors])
    return rings


def _product_faces(product):
    """A product as two boxes, body and cap, its sides as flat quads in the stand's frame."""
    w, d, h, cap = product["w"], product["d"], product["h"], product.get("cap") or 0.0
    out = []
    for z0, z1, fill in ((0.0, h - cap, PRODUCT), (h - cap, h, CAP)) if cap else ((0.0, h, PRODUCT),):
        c = np.array([[x, y, z, 1.0] for x in (-w / 2, w / 2) for y in (-d / 2, d / 2) for z in (z0, z1)])
        c = (product["frame"] @ c.T).T[:, :3]
        for idx, normal in (((0, 1, 3, 2), (-1, 0, 0)), ((4, 5, 7, 6), (1, 0, 0)), ((0, 1, 5, 4), (0, -1, 0)), ((2, 3, 7, 6), (0, 1, 0)),
                            ((0, 2, 6, 4), (0, 0, -1)), ((1, 3, 7, 5), (0, 0, 1))):
            n = product["frame"][:3, :3] @ np.array(normal, float)
            out.append((c[list(idx)], n, fill))
    return out


def project(folded, products, view):
    """The stand as flat polygons for one view, hidden faces taken out by drawing far to near. Each row: its polygon (holes
    kept), fill, and how near it stands."""
    u, v, w = (np.asarray(a, float) for a in view)
    rows = []

    def add(rings, fill, depth_at):
        exterior = rings[0]
        polygon = Polygon(np.c_[exterior @ u, exterior @ v], [np.c_[ring @ u, ring @ v] for ring in rings[1:]])
        if polygon.is_valid and polygon.area > 1e-6:
            rows.append({"polygon": polygon, "fill": fill, "depth": depth_at})

    for face in folded.values():
        fill = PRINTED if face.printed else BOARD
        n = face.normal
        for rings in _rings_world(face):
            if abs(n @ w) < 1e-6:
                # edge-on: the board's own thickness
                outline = rings[0]
                polygon = _edge_on(np.c_[outline @ u, outline @ v], face.t)
                if polygon.area > 1e-6:
                    depth = float((outline @ w).mean())
                    rows.append({"polygon": polygon, "fill": fill, "depth": _plane_depth(None, depth)})
                continue
            p0 = rings[0][0]
            add(rings, fill, _plane_depth((p0, n, u, v, w), None))
    for product in products:
        for quad, n, fill in _product_faces(product):
            if n @ w <= 1e-9:
                continue
            polygon = Polygon(np.c_[quad @ u, quad @ v])
            if polygon.area > 1e-6:
                rows.append({"polygon": polygon, "fill": fill, "depth": _plane_depth((quad[0], n, u, v, w), None)})
    return _far_to_near(rows)


def _edge_on(points, t):
    """A panel seen on its edge: the rectangle of its extent, one caliper thick."""
    a = points[np.argmax(np.linalg.norm(points - points[0], axis=1))] - points[0]
    length = np.linalg.norm(a)
    if length < 1e-9:
        return Polygon()
    a = a / length
    n = np.array([-a[1], a[0]])
    along = (points - points[0]) @ a
    p0, p1 = points[0] + a * along.min(), points[0] + a * along.max()
    return Polygon([p0 - n * t / 2, p1 - n * t / 2, p1 + n * t / 2, p0 + n * t / 2])


def _plane_depth(plane, flat):
    if plane is None:
        return lambda x, y: flat
    p0, n, u, v, w = plane
    a, b, c = n @ u, n @ v, n @ w

    def at(x, y):
        # p = x u + y v + d w lies on the plane through p0 with normal n
        return ((p0 @ n) - a * x - b * y) / c
    return at


def _far_to_near(rows):
    """Order by true overlap: wherever two polygons overlap on the page, the one farther at that spot goes first."""
    n = len(rows)
    bounds = [row["polygon"].bounds for row in rows]
    later = [set() for _ in range(n)]
    count = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            a, b = bounds[i], bounds[j]
            if a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]:
                continue
            common = rows[i]["polygon"].intersection(rows[j]["polygon"])
            if common.is_empty or common.area < 1e-3:
                continue
            spot = common.representative_point()
            near_i, near_j = rows[i]["depth"](spot.x, spot.y), rows[j]["depth"](spot.x, spot.y)
            if abs(near_i - near_j) < 1e-6:
                continue
            first, second = (i, j) if near_i < near_j else (j, i)
            if second not in later[first]:
                later[first].add(second)
                count[second] += 1
    centre = [row["polygon"].representative_point() for row in rows]
    mean = [row["depth"](c.x, c.y) for row, c in zip(rows, centre)]
    remaining = set(range(n))
    out = []
    while remaining:
        free = [i for i in remaining if count[i] == 0]
        pick = min(free or remaining, key=lambda i: mean[i])     # a cycle is broken at the farthest
        remaining.discard(pick)
        out.append(rows[pick])
        for k in later[pick]:
            count[k] -= 1
    return out


def _poly_path(c, polygon, tx, ty):
    p = c.beginPath()
    for ring in [polygon.exterior] + list(polygon.interiors):
        coords = list(ring.coords)
        p.moveTo(tx(coords[0][0]), ty(coords[0][1]))
        for x, y in coords[1:]:
            p.lineTo(tx(x), ty(y))
        p.close()
    return p


def draw_rows(c, rows, x, y, w, h, *, line=0.45, centre=True):
    """The projected rows fitted into the box (x, y, w, h, points). Returns the scale (points per mm) and the frame's corner."""
    if not rows:
        return 1.0, (x, y)
    union = unary_union([row["polygon"] for row in rows]).bounds
    k = min(w / max(union[2] - union[0], 1e-6), h / max(union[3] - union[1], 1e-6))
    ox = x + (w - (union[2] - union[0]) * k) / 2 - union[0] * k
    oy = y + (h - (union[3] - union[1]) * k) / 2 - union[1] * k
    tx, ty = (lambda v: ox + v * k), (lambda v: oy + v * k)
    c.setLineWidth(line)
    c.setStrokeColor(INK)
    for row in rows:
        c.setFillColor(row["fill"])
        c.drawPath(_poly_path(c, row["polygon"], tx, ty), stroke=1, fill=1, fillMode=0)
    return k, (ox, oy)


def _font():
    from apps.dielines.exporters.counter_display_files import _resolve_fonts
    return _resolve_fonts()


def provisional(c, x, y, size, regular):
    """⟪PROVISIONAL⟫, its brackets drawn, so the mark prints in any font."""
    c.saveState()
    c.setFont(regular, size)
    c.setStrokeColor(HexColor("#A33A2A"))
    c.setFillColor(HexColor("#A33A2A"))
    c.setLineWidth(size * .07)
    h = size * .7
    for dx in (0.0, size * .22):
        c.line(x + dx + size * .2, y + h, x + dx, y + h / 2)
        c.line(x + dx, y + h / 2, x + dx + size * .2, y)
    tx = x + size * .55
    c.drawString(tx, y, "PROVISIONAL")
    end = tx + c.stringWidth("PROVISIONAL", regular, size) + size * .1
    for dx in (0.0, size * .22):
        c.line(end + dx, y + h, end + dx + size * .2, y + h / 2)
        c.line(end + dx + size * .2, y + h / 2, end + dx, y)
    c.restoreState()
    return end + size * .5


def _header(c, die, record, title, page_w, page_h, regular, bold):
    c.setFillColor(INK)
    c.setFont(bold, 13)
    c.drawString(28, page_h - 30, title)
    c.setFont(regular, 8)
    v = record["inputs"]
    c.drawString(28, page_h - 42, "%s %s · %d products, %d rows × %d · product %.0f × %.0f × %.0f mm · closed %.1f × %.1f × %.1f mm · %s" % (
        st.label(record["template"]["id"]), record["template"]["version"], record["layout"]["count"], record["layout"]["rows"], record["layout"]["columns"],
        v["product_width_mm"], v["product_depth_mm"], v["product_height_mm"], v["width_mm"], v["depth_mm"], v["height_mm"], record["board"]["name"]))
    x = provisional(c, page_w - 150, page_h - 30, 9, regular)
    c.setFont(regular, 7)
    c.setFillColor(INK)
    c.drawRightString(page_w - 28, page_h - 42, DRAWING_WORDS)
    return x


def step_states(plan):
    """For each assembly step, what stands folded: the shares closed and the parts in, the parts brought in held off along their
    approach. Step by step, so each sheet's little drawings all come from one sequence."""
    closed = {}
    parts_in = ["tray"]
    states = []
    angles = {}
    for step in plan.steps:
        angles = dict(angles, **step.angles)
        moving = {}
        for part, names in step.close.items():
            moving[part] = names
        shares = {part: {name: 1.0 for name in names} for part, names in closed.items()}
        for part, names in moving.items():
            shares.setdefault(part, {}).update({name: .72 for name in names})
        approach = {}
        current = list(parts_in)
        if step.part:
            current.append(step.part)
            shares[step.part] = {hinge.child: 1.0 for hinge in plan.parts[step.part].hinges}
            approach[step.part] = step.approach
        states.append({"step": step, "closed": shares, "parts": current, "approach": approach, "products": step.products, "angles": dict(angles),
                       "keep_torn": not step.torn})
        for part, names in moving.items():
            closed.setdefault(part, []).extend(names)
        if step.part:
            closed[step.part] = [hinge.child for hinge in plan.parts[step.part].hinges]
            parts_in.append(step.part)
    return states


def _state_rows(die, plan, state):
    folded = sf.fold(die, plan, closed=state["closed"], approach=state["approach"], only=state["parts"], angles=state["angles"], keep_torn=state["keep_torn"])
    return project(folded, plan.products if state["products"] else [], VIEWS["three-quarter"])


def _dimensions(c, k, origin, size, view, regular):
    """The closed sizes beside a view."""
    ox, oy = origin
    c.setFont(regular, 7)
    c.setFillColor(INK)
    c.setStrokeColor(RULE)
    c.setLineWidth(.3)
    if view == "front":
        x0, x1, z0, z1 = size["x"][0], size["x"][1], size["z"][0], size["z"][1]
        c.line(ox + x0 * k, oy + z0 * k - 7, ox + x1 * k, oy + z0 * k - 7)
        c.drawCentredString(ox + (x0 + x1) / 2 * k, oy + z0 * k - 15, "%.1f" % (x1 - x0))
        c.line(ox + x1 * k + 7, oy + z0 * k, ox + x1 * k + 7, oy + z1 * k)
        c.drawString(ox + x1 * k + 10, oy + (z0 + z1) / 2 * k, "%.1f" % (z1 - z0))
    elif view == "side":
        y0, y1 = size["y"]
        z0, z1 = size["z"]
        c.line(ox + y0 * k, oy + z0 * k - 7, ox + y1 * k, oy + z0 * k - 7)
        c.drawCentredString(ox + (y0 + y1) / 2 * k, oy + z0 * k - 15, "%.1f" % (y1 - y0))


def write_fold_up(die, record, report, path):
    """The fold-up proof: one A3 page. Its four big views, the checks that were measured from them, and the die folded step
    by step."""
    regular, bold = _font()
    page_w, page_h = A3[0] * PT, A3[1] * PT
    c = canvas.Canvas(str(path), pagesize=(page_w, page_h), invariant=1, initialFontName=regular)
    c.setTitle("Fold-up proof, %s" % record["template"]["id"])
    _header(c, die, record, "Fold-up proof: the die folded by our own code", page_w, page_h, regular, bold)
    plan = die.plan
    folded = sf.fold(die, plan)
    size = sf.closed_size(folded)
    cell_h = 420
    top_y = page_h - 62 - cell_h
    cell_w = (page_w - 56) / 4
    for index, (view, words) in enumerate((("front", "Front"), ("side", "Side (shopper to the left)"), ("top", "Top"),
                                           ("three-quarter", "Three-quarter"))):
        x = 28 + index * cell_w
        c.setFillColor(INK)
        c.setFont(bold, 9)
        c.drawString(x, top_y + cell_h + 4, words)
        rows = project(folded, plan.products, VIEWS[view])
        k, origin = draw_rows(c, rows, x + 8, top_y + 16, cell_w - 34, cell_h - 22)
        _dimensions(c, k, origin, size, view, regular)
    steps = step_states(plan)
    strip_h = 250
    strip_y = top_y - strip_h - 20
    per = (page_w - 56) / len(steps)
    c.setFont(bold, 9)
    c.setFillColor(INK)
    c.drawString(28, strip_y + strip_h + 4, "Step by step, flat to built")
    for index, state in enumerate(steps):
        x = 28 + index * per
        draw_rows(c, _state_rows(die, plan, state), x + 3, strip_y + 16, per - 6, strip_h - 18, line=.3)
        c.setFont(bold, 8)
        c.setFillColor(INK)
        c.drawString(x + 3, strip_y + 4, str(index + 1))
    fold = report["fold"]
    sight = report["sightlines"]
    testers = sum(1 for product in plan.products if product.get("tester"))
    lines = ["Measured on the die folded: closed %s mm against the envelope; %d joints, each %.1f mm or less; %d collisions; %d locks engaged; "
             "%s fit, clearance %.1f mm%s" % (
                 " × ".join("%.1f" % fold["dimensions"]["closed_mm"][key] for key in ("width_mm", "depth_mm", "height_mm")),
                 len(fold["joints"]["joints"]), fold["joints"]["bar_mm"], len(fold["collisions"]), fold["locks"]["count"],
                 ("%d sealed products and %d testers" % (fold["fit"]["count"] - testers, testers)) if testers else "%d products" % fold["fit"]["count"],
                 fold["fit"]["clearance_mm"], ", a tester's 2.0 mm" if testers else "")]
    if testers:
        lines.append("Sightlines: " + "; ".join("%d/%d mm eye: the rear rows are seen by their tops (least %.0f mm), header's safe area %.0f %% seen" % (
            eye["eye_mm"]["in_front"], eye["eye_mm"]["above_counter"], min(row["top_band_mm"] for row in eye["products"] if row["row"]),
            100 * eye.get("header", {"seen_share": 1})["seen_share"]) for eye in sight["eyes"]))
    else:
        lines.append("Sightlines: " + "; ".join("%d/%d mm eye: least top band %.0f mm of the %.0f mm bar, header's safe area %.0f %% seen" % (
            eye["eye_mm"]["in_front"], eye["eye_mm"]["above_counter"], min(row["top_band_mm"] for row in eye["products"]), sight["face_bar_mm"],
            100 * eye.get("header", {"seen_share": 1})["seen_share"]) for eye in sight["eyes"]))
    if report.get("shades"):
        carried = "its tester" if testers else "each product"
        lines.append("Every shade shows: least %.0f %% of %s's colour window seen, from both eyes (the rule: at least 50 %%). No bare board in view: %s." % (
            100 * report["shades"]["worst_share"], carried, "holds" if report["view"]["passed"] else "not on this type: " + ", ".join(row["face"] for row in report["view"]["faults"])[:90]))
    c.setFont(regular, 7.5)
    c.setFillColor(INK)
    y = 52
    for line in lines:
        c.drawString(28, y, line)
        y -= 10
    x = provisional(c, 28, y - 1, 7, regular)
    c.setFont(regular, 7)
    c.setFillColor(INK)
    c.drawString(x, y, "; ".join(record.get("provisional_notes", []))[:190])
    c.showPage()
    c.save()
    return {"views": ["front", "side", "top", "three-quarter"], "steps": len(steps), "labelled": DRAWING_WORDS}


def write_assembly(die, record, path):
    """The assembly sheet: numbered steps in plain words with small drawings, flat to built."""
    regular, bold = _font()
    page_w, page_h = A3[0] * PT, A3[1] * PT
    c = canvas.Canvas(str(path), pagesize=(page_w, page_h), invariant=1, initialFontName=regular)
    c.setTitle("Assembly sheet, %s" % record["template"]["id"])
    _header(c, die, record, "Assembly: flat to built", page_w, page_h, regular, bold)
    plan = die.plan
    states = step_states(plan)
    columns = 3 if len(states) <= 6 else 4
    rows_n = math.ceil(len(states) / columns)
    cell_w = (page_w - 56) / columns
    cell_h = (page_h - 90) / rows_n
    for index, state in enumerate(states):
        col, row = index % columns, index // columns
        x, y = 28 + col * cell_w, page_h - 56 - (row + 1) * cell_h
        c.setStrokeColor(RULE)
        c.setLineWidth(.3)
        c.rect(x + 3, y + 3, cell_w - 6, cell_h - 6)
        c.setFillColor(INK)
        c.setFont(bold, 15)
        c.drawString(x + 10, y + cell_h - 23, str(index + 1))
        words = _wrap(state["step"].words, regular, 9.5, cell_w - 50, c)
        c.setFont(regular, 9.5)
        yy = y + cell_h - 18
        for line in words:
            c.drawString(x + 32, yy, line)
            yy -= 11.5
        draw_rows(c, _state_rows(die, plan, state), x + 10, y + 10, cell_w - 20, cell_h - 60, line=.4)
    c.setFont(regular, 7.5)
    c.setFillColor(INK)
    words = record["production"].get("glue", "")
    c.drawString(28, 16, "One person, no tools. %s. %s" % (words[:1].upper() + words[1:], DRAWING_WORDS))
    c.showPage()
    c.save()
    return {"steps": [state["step"].words for state in states], "labelled": DRAWING_WORDS}


def _wrap(words, font, size, width, c):
    out, line = [], ""
    for word in words.split():
        trial = (line + " " + word).strip()
        if c.stringWidth(trial, font, size) > width and line:
            out.append(line)
            line = word
        else:
            line = trial
    if line:
        out.append(line)
    return out


LINE_STYLE = {"CUT": (HexColor("#111111"), .5, ()), "CREASE": (HexColor("#0A6FB5"), .5, (3, 1.6)), "PERF": (HexColor("#C0561B"), .5, (1, 1)),
              "HALF-CUT": (HexColor("#8A2BB5"), .5, ([5, 1.5, 1, 1.5], 0))}


def tile_grid(sheet_w, sheet_h):
    usable_w, usable_h = A3[0] - 2 * TILE_MARGIN_MM, A3[1] - 2 * TILE_MARGIN_MM - 14
    step_w, step_h = usable_w - OVERLAP_MM, usable_h - OVERLAP_MM
    cols = 1 if sheet_w <= usable_w else 1 + math.ceil((sheet_w - usable_w) / step_w)
    rows = 1 if sheet_h <= usable_h else 1 + math.ceil((sheet_h - usable_h) / step_h)
    return {"cols": cols, "rows": rows, "win_w": usable_w, "win_h": usable_h, "step_w": step_w, "step_h": step_h}


def write_tiles(die, record, path):
    """The die at 100 % on A3 landscape sheets, cut solid, fold dashed, perforation dotted, half-cut dash-dot, overlap marks where
    it takes more than one: each tile a window of the die, 10 mm shared with each neighbour; lay the circled crosses on each
    other. A 50 mm bar on every sheet proves the print scale."""
    from apps.dielines.exporters.counter_display_files import layers
    regular, bold = _font()
    tg = tile_grid(die.sheet_w, die.sheet_h)
    lines, _words = layers(die, record)
    c = canvas.Canvas(str(path), pagesize=(A3[0] * PT, A3[1] * PT), invariant=1, initialFontName=regular)
    c.setTitle("Cut and fold at 100 %%, %s" % record["template"]["id"])
    m, ww, wh = TILE_MARGIN_MM, tg["win_w"], tg["win_h"]
    top = A3[1] - m
    labels = [(part.label, part.outline().bounds[:2]) for part in die.parts]
    for r in range(tg["rows"]):
        for col in range(tg["cols"]):
            wx, wy = col * tg["step_w"], r * tg["step_h"]
            tx, ty = (lambda x, wx=wx: (m + x - wx) * PT), (lambda y, wy=wy: (top - (y - wy)) * PT)
            c.saveState()
            clip = c.beginPath()
            clip.rect(m * PT, (top - wh) * PT, ww * PT, wh * PT)
            c.clipPath(clip, stroke=0, fill=0)
            for layer, (colour, width, dash) in LINE_STYLE.items():
                c.setStrokeColor(colour)
                c.setLineWidth(width)
                c.setDash(*dash) if dash else c.setDash()
                for poly in lines.get(layer, []):
                    p = c.beginPath()
                    p.moveTo(tx(poly[0][0]), ty(poly[0][1]))
                    for x, y in poly[1:]:
                        p.lineTo(tx(x), ty(y))
                    c.drawPath(p, stroke=1, fill=0)
            c.setDash()
            c.setFillColor(RULE)
            c.setFont(regular, 8)
            for words, (x, y) in labels:
                c.drawString(tx(x), ty(y - 6), words)
            c.restoreState()
            c.setStrokeColor(RULE)
            c.setLineWidth(.3)
            c.rect(m * PT, (top - wh) * PT, ww * PT, wh * PT)
            c.setStrokeColor(black)
            marks = []
            if col > 0:
                marks.append((m + OVERLAP_MM / 2, top - wh / 2))
            if col < tg["cols"] - 1:
                marks.append((m + ww - OVERLAP_MM / 2, top - wh / 2))
            if r > 0:
                marks.append((m + ww / 2, top - OVERLAP_MM / 2))
            if r < tg["rows"] - 1:
                marks.append((m + ww / 2, top - wh + OVERLAP_MM / 2))
            for mx, my in marks:
                c.circle(mx * PT, my * PT, 3 * PT, stroke=1, fill=0)
                c.line((mx - 4.5) * PT, my * PT, (mx + 4.5) * PT, my * PT)
                c.line(mx * PT, (my - 4.5) * PT, mx * PT, (my + 4.5) * PT)
            c.setFillColor(INK)
            c.setFont(bold, 9)
            c.drawString(m * PT, (m + 6) * PT, "Sheet %d of %d (row %d, column %d) · print at 100 %%, no fit" % (
                r * tg["cols"] + col + 1, tg["rows"] * tg["cols"], r + 1, col + 1))
            c.setFont(regular, 7)
            c.drawString(m * PT, (m + 1) * PT, "Solid: cut. Dashed: fold. Dotted: tear. Dash-dot: half-cut, from the unprinted side. %s %s" % (
                st.label(record["template"]["id"]), record["template"]["version"]))
            x = provisional(c, (A3[0] - 150) * PT, (m + 1) * PT, 7, regular)
            bar_x = (A3[0] - m - 50) * PT
            c.setLineWidth(1)
            c.line(bar_x, (m + 8) * PT, bar_x + 50 * PT, (m + 8) * PT)
            c.setFont(regular, 7)
            c.drawString(bar_x, (m + 3) * PT, "50 mm")
            c.showPage()
    c.save()
    return dict(tg, tiles=tg["rows"] * tg["cols"], page_mm=list(A3), overlap_mm=OVERLAP_MM)


def write_nest(die, nest_report, path):
    """The parts laid out on the press sheet the nest chose, each outline at its place, with its material use in words."""
    regular, bold = _font()
    best = nest_report["best"]
    sheet_w, sheet_h = best["sheet_mm"]
    page_w, page_h = A3[0] * PT, A3[1] * PT
    c = canvas.Canvas(str(path), pagesize=(page_w, page_h), invariant=1, initialFontName=regular)
    c.setTitle("Nest on the press sheet")
    c.setFillColor(INK)
    c.setFont(bold, 13)
    c.drawString(28, page_h - 30, "Nest: %d × %d mm press sheet, %s" % (sheet_w, sheet_h, nest_report["board"]))
    c.setFont(regular, 9)
    c.drawString(28, page_h - 44, "%d whole sets on a sheet · %.1f %% of the sheet is the stand's board · %s" % (
        best["sets"], 100 * best["yield"], best["method"]))
    k = min((page_w - 60) / sheet_w, (page_h - 90) / sheet_h)
    ox, oy = 30, 30
    c.setLineWidth(.6)
    c.setStrokeColor(INK)
    c.rect(ox, oy, sheet_w * k, sheet_h * k)
    by_name = {part.name: part for part in die.parts}
    for row in best.get("placements", []):
        part = by_name[row["part"]]
        x0, y0, x1, y1 = part.outline().bounds
        if row.get("half_turn"):
            tx = lambda x, row=row, x1=x1: ox + (row["x_mm"] + x1 - x + best["margin_mm"]) * k  # noqa: E731
            ty = lambda y, row=row, y1=y1: oy + (sheet_h - (row["y_mm"] + y1 - y + best["gripper_mm"])) * k  # noqa: E731
        else:
            tx = lambda x, row=row, x0=x0: ox + (row["x_mm"] + x - x0 + best["margin_mm"]) * k  # noqa: E731
            ty = lambda y, row=row, y0=y0: oy + (sheet_h - (row["y_mm"] + y - y0 + best["gripper_mm"])) * k  # noqa: E731
        c.setLineWidth(.3)
        for line in cd.cut_polygons(part):
            pts = list(line.coords)
            p = c.beginPath()
            p.moveTo(tx(pts[0][0]), ty(pts[0][1]))
            for x, y in pts[1:]:
                p.lineTo(tx(x), ty(y))
            c.drawPath(p, stroke=1, fill=0)
    c.showPage()
    c.save()
    return {"sheet_mm": [sheet_w, sheet_h], "sets": best["sets"]}


def write_sheets(die, record, report, folder, nest_report):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = {"fold_up": write_fold_up(die, record, report, folder / "fold-up.pdf"),
           "assembly_sheet": write_assembly(die, record, folder / "assembly.pdf"),
           "cut_and_fold": write_tiles(die, record, folder / "cut-and-fold-1to1.pdf"),
           "nest_sheet": write_nest(die, nest_report, folder / "nest.pdf")}
    _previews(folder)
    return out


def _previews(folder):
    """A PNG of each one-page sheet for the round's page."""
    import fitz
    for name in ("fold-up", "assembly", "nest"):
        with fitz.open(folder / (name + ".pdf")) as doc:
            doc[0].get_pixmap(dpi=110, alpha=False).save(str(folder / (name + ".png")))


def die_preview(die, record, png):
    """The flat die for the round's page, its lines heavy enough to read small: cut, fold, half-cut and tear each its own, the printed faces
    tinted, each part named."""
    from PIL import Image, ImageDraw
    from apps.dielines.exporters.counter_display_files import layers, _resolve_fonts
    k = min(1400 / die.sheet_w, 1400 / die.sheet_h)
    image = Image.new("RGB", (int(die.sheet_w * k), int(die.sheet_h * k)), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for part in die.parts:
        for _name, polygon, printed in part.faces:
            if printed:
                draw.polygon([(x * k, y * k) for x, y in polygon.exterior.coords], fill=(241, 235, 221))
    lines, _words = layers(die, record)

    def stroke(poly, colour, width, dash=None):
        for (xa, ya), (xb, yb) in zip(poly, poly[1:]):
            if dash is None:
                draw.line([(xa * k, ya * k), (xb * k, yb * k)], fill=colour, width=width)
                continue
            length = math.dist((xa, ya), (xb, yb))
            at = 0.0
            while at < length:
                end = min(length, at + dash[0])
                draw.line([((xa + (xb - xa) * at / length) * k, (ya + (yb - ya) * at / length) * k),
                           ((xa + (xb - xa) * end / length) * k, (ya + (yb - ya) * end / length) * k)], fill=colour, width=width)
                at += dash[0] + dash[1]
    for poly in lines["CUT"]:
        stroke(poly, (20, 20, 24), 2)
    for poly in lines["CREASE"]:
        stroke(poly, (10, 111, 181), 2, (4.0, 2.5))
    for poly in lines["HALF-CUT"]:
        stroke(poly, (138, 43, 181), 2, (7.0, 2.0))
    for poly in lines["PERF"]:
        stroke(poly, (192, 86, 27), 2, (1.2, 1.2))
    for poly in lines.get("GLUE", []):
        stroke(poly, (51, 160, 80), 2)
    image.save(png)


def type_svg(record, die):
    """A small line drawing of a stand type: its three-quarter view as one SVG, for New design's cards."""
    folded = sf.fold(die, die.plan)
    rows = project(folded, die.plan.products, VIEWS["three-quarter"])
    union = unary_union([row["polygon"] for row in rows]).bounds
    w, h = union[2] - union[0], union[3] - union[1]
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %.1f %.1f" role="img" aria-label="%s" fill="none" stroke="#26262e" stroke-width="%.2f">' % (
        w, h, st.label(record["template"]["id"]) + ", a drawing", max(w, h) / 260)]
    for row in rows:
        d = []
        polygon = row["polygon"]
        for ring in [polygon.exterior] + list(polygon.interiors):
            coords = list(ring.coords)
            d.append("M" + " L".join("%.1f %.1f" % (x - union[0], union[3] - y) for x, y in coords) + " Z")
        fill = "#%02x%02x%02x" % tuple(int(255 * v) for v in (row["fill"].red, row["fill"].green, row["fill"].blue))
        out.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (" ".join(d), fill))
    out.append("</svg>")
    return "".join(out)
