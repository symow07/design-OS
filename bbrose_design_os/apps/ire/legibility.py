"""[His goal after the pitch page, 2026-10-15, A (5): "CONTRAST: logos and small text are always readable against what's
behind them."] Every mark and every line of type on the product read against what the drawing paints beneath it, and its
ink moved the least it must to read — on the Design Graph, before it is drawn, for every product type.

Before (2026-10-15): the mark's ink was the median of the photo's gold pixels in its box (``concept_design_map
.trace_mark``), never lit-corrected and never set against its ground; the drawing's own check (``self_check.inspect``)
read type only over the traced solids (``shape-map-*``) — never over a window, a lid's art, a mesh ground, the cap or
the body, and never the mark.

- ``ground_under(doc, targets)`` — what lies under each target's box: a grid of points over the box (GRID), at each the
  topmost filled node painted before the target (a solid's colour, a gradient's at the point, each corner of a mesh
  near it; the paper, white, where nothing is), its colours each kept where they cover GROUND_MIN_SHARE of the points or
  more — a thin line crossing the box is not its ground.
- ``least_move(ink, grounds, ratio)`` — the ink's lightness (CIE L*) moved the least either way, its hue kept (a* and b*,
  its chroma pulled in only where the move leaves sRGB), until it reads ``ratio`` to 1 against every ground (WCAG 2
  contrast); a gold kept gold where any lightness that reads does (``is_gold``); else the lightness that reads best.
- ``repair(doc)`` — each mark (an ``AssetRef`` the composer recoloured) and each line of type on the product, moved by
  ``least_move`` where it reads under ``needed`` (MARK_RATIO, SMALL_TYPE_RATIO under SMALL_TYPE_PT, TYPE_RATIO) — each
  move a finding said beside Approve ("Fixed: ..."), each it cannot make shown.
- ``remaining(doc)`` — what still reads under its ratio, for the drawing's own check to show.

Pure: nothing written, nothing paid. The ratios are WCAG 2's (3:1 for a graphic and large type, 4.5:1 for small type);
a larger line keeps the drawing's own check's floor (``self_check.LEGIBLE_RATIO``); the grid, the share and the
step are the executor's, new with this module."""
from __future__ import annotations

import math

#: a mark (a logo) reads at this contrast to its ground or more — WCAG 2's for a graphic object …
MARK_RATIO = 3.0
#: … a line of type set under SMALL_TYPE_PT at this — WCAG 2's for body text …
SMALL_TYPE_PT = 9.0
SMALL_TYPE_RATIO = 4.5
#: … and a larger line at the drawing's own check's floor (``self_check.LEGIBLE_RATIO``): a display line keeps the
#: concept's own colour wherever it reads at all — the designer's eye matches it to the concept
from apps.ire.self_check import LEGIBLE_RATIO as TYPE_RATIO  # noqa: E402
#: [his goal after the pitch page, A (5), first redraw of 128] a line reads where its luminance contrast reaches its ratio
#: OR its colour stands this far from its ground (CIE76 ΔE): white capitals on a clear aqua read 1.7:1 by luminance and
#: plainly read, as the concept sets them — the luminance ratio alone turned them grey (128's "TIDE GLASS") and its
#: white mark navy. A line under both is moved, the least that reaches either
READ_DE = {MARK_RATIO: 20.0, SMALL_TYPE_RATIO: 40.0, TYPE_RATIO: 20.0}
#: … and an ink is moved only the way it already stands from its ground — a dark line darker, a light one lighter, as the
#: concept sets it: 128's white capitals were turned grey, 127's dark "3.5 g", read in its ground's speckle, left faint
#: the points read over a target's box: this many along it, this many across it
GRID = (7, 3)
#: a colour under a target is its ground where it covers this share of the points or more
GROUND_MIN_SHARE = 0.2
#: a fill fainter than this (its opacity) is not a ground: a glow, a soft room — what is beneath it shows
OPAQUE_MIN = 0.5
#: a lightness move is searched in steps of this many L* …
L_STEP = 0.5
#: … and the colour said moved where it moved this far or more (CIE76)
MOVED_DE = 0.5
#: the drawing's record of each ink moved to read: ``{its hex now: the hex it was chosen in}``
MOVED_KEY = "legibility_moved/1.0"
#: the paper, where nothing is painted
PAPER = "#FFFFFF"
#: a line's letters stand this many sizes above its baseline and this many below
CAP_UP, CAP_DOWN = 0.70, 0.15
#: a group with one of these roles holds the sheet round the product, never its print
SHEET_ROLES = ("info", "structure", "generic")
_MM_PER_PT = 25.4 / 72.0
#: gold, as the map's tracers find it (``concept_design_map.SHAPE_PARAMS``): b* above GOLD_B_MIN, above a* by
#: GOLD_B_OVER_A, L* above GOLD_L_MIN
GOLD_B_MIN, GOLD_B_OVER_A, GOLD_L_MIN = 28.0, 4.0, 45.0


# ------------------------------------------------------------------------------------------------ colour arithmetic

def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055


def _rgb(hx: str) -> tuple:
    h = str(hx).lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def luminance(hx: str) -> float:
    """WCAG 2's relative luminance of one hex colour."""
    r, g, b = (_lin(v) for v in _rgb(hx))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    """WCAG 2's contrast ratio of two hex colours, lighter over darker: 1 to 21."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


_WHITE = (0.95047, 1.0, 1.08883)


def to_lab(hx: str) -> tuple:
    """CIE L*a*b* (D65) of one hex colour."""
    r, g, b = (_lin(v) for v in _rgb(hx))
    xyz = (0.4124 * r + 0.3576 * g + 0.1805 * b, 0.2126 * r + 0.7152 * g + 0.0722 * b,
           0.0193 * r + 0.1192 * g + 0.9505 * b)

    def f(t):
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (24389.0 / 27.0 * t + 16.0) / 116.0
    fx, fy, fz = (f(v / w) for v, w in zip(xyz, _WHITE))
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def _lab_rgb(lab: tuple):
    """sRGB (0–1) of a L*a*b*, or None where it lies outside sRGB."""
    L, a, b = lab
    fy = (L + 16.0) / 116.0
    fx, fz = fy + a / 500.0, fy - b / 200.0

    def finv(t):
        return t ** 3 if t ** 3 > 216.0 / 24389.0 else (116.0 * t - 16.0) * 27.0 / 24389.0
    x, y, z = (finv(t) * w for t, w in zip((fx, fy, fz), _WHITE))
    rgb = (3.2406 * x - 1.5372 * y - 0.4986 * z, -0.9689 * x + 1.8758 * y + 0.0415 * z,
           0.0557 * x - 0.2040 * y + 1.0570 * z)
    out = tuple(_gam(max(0.0, c)) if c > 0 else 0.0 for c in rgb)
    if any(c < -1e-4 for c in rgb) or any(c > 1.0 + 1e-4 for c in out):
        return None
    return out


def from_lab(lab: tuple) -> str:
    """The hex of a L*a*b*, its chroma pulled in (its hue kept) until it lies inside sRGB."""
    L, a, b = lab
    for k in range(101):
        rgb = _lab_rgb((L, a * (1.0 - k / 100.0), b * (1.0 - k / 100.0)))
        if rgb is not None:
            return "#%02X%02X%02X" % tuple(int(round(min(1.0, max(0.0, c)) * 255)) for c in rgb)
    grey = _lab_rgb((L, 0.0, 0.0))
    return "#%02X%02X%02X" % tuple(int(round(min(1.0, max(0.0, c)) * 255)) for c in grey)


def is_gold(hx: str) -> bool:
    """A gold, as the map's tracers find one: yellow over red, lit or in its shade."""
    L, a, b = to_lab(hx)
    return b > GOLD_B_MIN and b > a + GOLD_B_OVER_A and L > GOLD_L_MIN


def colour_distance(a: str, b: str) -> float:
    """CIE76 ΔE between two colours."""
    return math.dist(to_lab(a), to_lab(b))


def reads(hx: str, grounds: list, needed: float) -> bool:
    """Whether ``hx`` reads against every one of ``grounds``: its luminance contrast at ``needed`` or more, or its colour
    READ_DE[needed] or more away (``READ_DE``)."""
    de = READ_DE[needed] if needed in READ_DE else max(READ_DE.values())
    return all(ratio(hx, g) >= needed or colour_distance(hx, g) >= de for g in grounds if g)


def least_move(ink: str, grounds: list, needed: float) -> dict:
    """``{"hex", "ratio", "reads", "kept_gold", "moved_l"}`` — ``ink`` moved the least in lightness, its hue kept, to read
    (``reads``) against every one of ``grounds`` (module docstring); ``ink`` itself where it already reads."""
    grounds = [g for g in grounds if g]
    if not grounds:
        return {"hex": ink, "ratio": None, "reads": True, "kept_gold": is_gold(ink), "moved_l": 0.0}

    def worst(hx):
        return min(ratio(hx, g) for g in grounds)
    now = worst(ink)
    gold = is_gold(ink)
    if reads(ink, grounds, needed):
        return {"hex": ink, "ratio": round(now, 2), "reads": True, "kept_gold": gold, "moved_l": 0.0}
    L, a, b = to_lab(ink)
    reading, best = [], (now, ink, 0.0)
    steps = int(100.0 / L_STEP) + 1
    ground_l = sum(to_lab(g)[0] for g in grounds) / len(grounds)
    for i in range(1, steps):
        for sign in ((1.0,) if L >= ground_l else (-1.0,)):
            target = L + sign * i * L_STEP
            if not 0.0 <= target <= 100.0:
                continue
            hx = from_lab((target, a, b))
            r = worst(hx)
            if r > best[0]:
                best = (r, hx, sign * i * L_STEP)
            if reads(hx, grounds, needed):
                reading.append((i * L_STEP, hx, r, sign * i * L_STEP))
    if reading:
        golds = [c for c in reading if is_gold(c[1])] if gold else []
        moved, hx, r, dl = min(golds or reading, key=lambda c: c[0])
        return {"hex": hx, "ratio": round(r, 2), "reads": True, "kept_gold": bool(golds), "moved_l": round(dl, 2)}
    return {"hex": best[1], "ratio": round(best[0], 2), "reads": False, "kept_gold": gold and is_gold(best[1]),
            "moved_l": round(best[2], 2)}


# ----------------------------------------------------------------------------------------------- what lies beneath

def _apply(t, x: float, y: float) -> tuple:
    a, b, c, d, e, f = t
    return a * x + c * y + e, b * x + d * y + f


def _then(outer, inner):
    """The turn ``inner`` (a child's own frame onto its parent's) followed by ``outer``."""
    a, b, c, d, e, f = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e,
            b * e2 + d * f2 + f)


_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def walk(doc):
    """``(node, turn, ancestor roles)`` over the outside, in the order it is painted — each node's turn onto the page."""
    from apps.ire.graph import Group

    def _walk(node, turn, roles):
        yield node, turn, roles
        if isinstance(node, Group):
            inner = _then(turn, tuple(node.turn)) if node.turn is not None else turn
            for child in node.children:
                yield from _walk(child, inner, roles + (node.role,))
    yield from _walk(doc.root, _IDENTITY, ())


def _fill_colours(fill, point=None) -> list:
    """The colours a fill paints: a solid's colour; each stop of a gradient; each corner of the mesh patches whose
    corners' box holds ``point``. [] — not a ground: a pattern, a fill fainter than OPAQUE_MIN, a fading mesh."""
    kind = getattr(fill, "type", None)
    if kind == "solid":
        return [fill.color.to_hex()] if float(fill.opacity) >= OPAQUE_MIN else []
    if kind == "gradient":
        if point is None:
            return [s.color.to_hex() for s in fill.stops]
        return [_gradient_at(fill, point)]
    if kind == "mesh":
        if fill.alphas is not None:
            return []
        out = []
        for p in fill.patches:
            xs, ys = [float(v) for v in p[0:8:2]], [float(v) for v in p[1:8:2]]
            if point is None or (min(xs) <= point[0] <= max(xs) and min(ys) <= point[1] <= max(ys)):
                out += [str(h) for h in p[8:12]]
        return out
    return []


def _gradient_at(fill, point) -> str:
    """The colour a gradient paints at ``point`` (page millimetres): its stops blended at the point's place along its
    axis (linear) or out from its centre (radial)."""
    if fill.kind == "radial":
        t = math.hypot(point[0] - fill.cx, point[1] - fill.cy) / fill.r if fill.r > 0 else 0.0
    else:
        dx, dy = fill.x2 - fill.x1, fill.y2 - fill.y1
        span = dx * dx + dy * dy
        t = ((point[0] - fill.x1) * dx + (point[1] - fill.y1) * dy) / span if span > 0 else 0.0
    t = min(1.0, max(0.0, t))
    stops = sorted(fill.stops, key=lambda st: float(st.offset))
    if t <= float(stops[0].offset):
        return stops[0].color.to_hex()
    for a, b in zip(stops, stops[1:]):
        if t <= float(b.offset):
            k = (t - float(a.offset)) / max(1e-9, float(b.offset) - float(a.offset))
            ra, rb = _rgb(a.color.to_hex()), _rgb(b.color.to_hex())
            return "#%02X%02X%02X" % tuple(int(round((x + (y - x) * k) * 255)) for x, y in zip(ra, rb))
    return stops[-1].color.to_hex()


#: a path's curves are read as this many straight steps each, to tell what lies inside it
CURVE_STEPS = 8


def _rings(node, turn) -> list:
    """A filled node's rings on the page, each an array of its points (its curves in CURVE_STEPS steps)."""
    import numpy as np

    from apps.ire.graph import Path, Rect
    from apps.ire.self_check import _sample
    if isinstance(node, Rect):
        rings = [[(node.x, node.y), (node.x + node.w, node.y), (node.x + node.w, node.y + node.h),
                  (node.x, node.y + node.h)]]
    elif isinstance(node, Path):
        rings = _sample(node.segments, CURVE_STEPS)
    else:
        return []
    return [np.array([_apply(turn, x, y) for x, y in ring], float) for ring in rings if len(ring) >= 3]


def _covers(rings, evenodd: bool, pt) -> bool:
    """Whether ``pt`` lies inside the rings, by their winding (nonzero) or their crossings (even-odd)."""
    import numpy as np
    x, y = pt
    wind = cross = 0
    for r in rings:
        a, b = r, np.roll(r, -1, axis=0)
        up = (a[:, 1] <= y) & (b[:, 1] > y)
        down = (a[:, 1] > y) & (b[:, 1] <= y)
        side = (b[:, 0] - a[:, 0]) * (y - a[:, 1]) - (x - a[:, 0]) * (b[:, 1] - a[:, 1])
        wind += int(np.count_nonzero(up & (side > 0))) - int(np.count_nonzero(down & (side < 0)))
        dy = np.where(b[:, 1] == a[:, 1], 1.0, b[:, 1] - a[:, 1])
        cross += int(np.count_nonzero((up | down) & (a[:, 0] + (y - a[:, 1]) * (b[:, 0] - a[:, 0]) / dy > x)))
    return cross % 2 == 1 if evenodd else wind != 0


def _bounds(node, turn):
    from apps.ire.graph import Path, Rect
    if isinstance(node, Rect):
        pts = [(node.x, node.y), (node.x + node.w, node.y + node.h)]
    elif isinstance(node, Path):
        pts = [(v[0], v[1]) for s in node.segments for v in ((getattr(s, "x", None), getattr(s, "y", None)),
                                                                 (getattr(s, "x1", None), getattr(s, "y1", None)),
                                                                 (getattr(s, "x2", None), getattr(s, "y2", None)))
               if v[0] is not None]
    else:
        return None
    if not pts:
        return None
    pts = [_apply(turn, x, y) for x, y in pts]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def text_quad(node, turn) -> list:
    """A line of type's letters on the page: the four corners of the band from CAP_DOWN under its baseline to CAP_UP
    over it, along its set width (estimated as its wrap reads it), turned as it is set."""
    from apps.ire.compose_container import name_width_estimate_mm
    size = float(node.size_pt) * _MM_PER_PT
    width = name_width_estimate_mm(node.text, float(node.size_pt), tracking_em=float(node.tracking_em or 0.0),
                                   upper=node.text_case == "upper")
    start = {"left": 0.0, "center": -width / 2.0, "right": -width}[node.align]
    th = math.radians(float(node.rotation_deg))
    along, up = (math.cos(th), -math.sin(th)), (-math.sin(th), -math.cos(th))

    def at(u, v):
        return _apply(turn, node.x + along[0] * u + up[0] * v, node.y + along[1] * u + up[1] * v)
    return [at(start, -CAP_DOWN * size), at(start + width, -CAP_DOWN * size), at(start + width, CAP_UP * size),
            at(start, CAP_UP * size)]


def _grid(quad) -> list:
    """GRID points over a quad (its corners in order round it), inset half a step from its edges."""
    nu, nv = GRID
    (x0, y0), (x1, y1), _c, (x3, y3) = quad
    out = []
    for i in range(nu):
        for j in range(nv):
            u, v = (i + 0.5) / nu, (j + 0.5) / nv
            out.append((x0 + (x1 - x0) * u + (x3 - x0) * v, y0 + (y1 - y0) * u + (y3 - y0) * v))
    return out


def targets(doc) -> list:
    """``[{"node", "order", "quad", "ink", "needed", "what"}]`` — every mark the composer recoloured and every line of
    type printed on the product (a sheet's own words, a schematic of its copy, and every undeclared line in a group of
    a SHEET_ROLES role, left out)."""
    from apps.ire.graph import AssetRef, TextRun
    from apps.ire.graph import DEPICTION_OF_PRODUCT_COPY, SHEET_ANNOTATION
    out = []
    for order, (node, turn, roles) in enumerate(walk(doc)):
        if isinstance(node, AssetRef) and node.recolor is not None and node.w > 0 and node.h > 0:
            if any(r in SHEET_ROLES for r in roles):
                continue
            quad = [_apply(turn, node.x, node.y), _apply(turn, node.x + node.w, node.y),
                    _apply(turn, node.x + node.w, node.y + node.h), _apply(turn, node.x, node.y + node.h)]
            out.append({"node": node, "order": order, "quad": quad, "ink": node.recolor.to_hex(),
                        "needed": MARK_RATIO, "what": "the mark %s" % node.name})
        elif isinstance(node, TextRun) and node.text.strip():
            scope = node.print_scope.kind if node.print_scope is not None else None
            # the sheet's own words, and a schematic of the product's copy at diagram size (``print_scope``), never
            # its print
            if scope in (SHEET_ANNOTATION, DEPICTION_OF_PRODUCT_COPY) or (
                    scope is None and any(r in SHEET_ROLES for r in roles)):
                continue
            small = float(node.size_pt) < SMALL_TYPE_PT
            out.append({"node": node, "order": order, "quad": text_quad(node, turn), "ink": node.color.to_hex(),
                        "needed": SMALL_TYPE_RATIO if small else TYPE_RATIO,
                        "what": "%r (%g pt)" % (node.text[:30], round(float(node.size_pt), 2))})
    return out


def ground_under(doc, wanted: list) -> list:
    """For each of ``wanted`` (``targets``), the colours under it that are its ground (module docstring)."""
    from apps.ire.graph import Path, Rect
    if not wanted:
        return []
    xs = [p[0] for t in wanted for p in t["quad"]]
    ys = [p[1] for t in wanted for p in t["quad"]]
    reach = (min(xs), min(ys), max(xs), max(ys))
    filled = []
    for order, (node, turn, _roles) in enumerate(walk(doc)):
        if not isinstance(node, (Path, Rect)) or node.fill is None or not _fill_colours(node.fill):
            continue
        b = _bounds(node, turn)
        if b is None or b[2] < reach[0] or b[0] > reach[2] or b[3] < reach[1] or b[1] > reach[3]:
            continue
        filled.append((order, b, node, turn))
    out = []
    for t in wanted:
        counts, points = {}, _grid(t["quad"])
        for pt in points:
            hit = None
            # the topmost painted before the target: read from the top down, the first that holds the point
            for order, b, node, turn in reversed(filled):
                if order >= t["order"] or not (b[0] <= pt[0] <= b[2] and b[1] <= pt[1] <= b[3]):
                    continue
                if _covers(_rings(node, turn), getattr(node, "fill_rule", None) == "evenodd", pt):
                    hit = (node.fill, turn == _IDENTITY)
                    break
            for hx in set(_fill_colours(hit[0], pt if hit[1] else None) if hit is not None else [PAPER]):
                counts[hx] = counts.get(hx, 0) + 1
        out.append([hx for hx, n in counts.items() if n >= GROUND_MIN_SHARE * len(points)])
    return out


# ---------------------------------------------------------------------------------------------- repair and remaining

def repair(doc) -> list:
    """``[finding]``, each ``{"kind": "contrast", "what", "fixed": True}``: every mark and line of type on ``doc`` that
    reads under its ratio, its ink moved (``least_move``) in place — where no lightness of its hue reads, to the one that
    reads best, said so; what it still lacks is shown by ``remaining``."""
    from apps.ire.graph import AssetRef, Color
    wanted = targets(doc)
    fixed = []
    for t, grounds in zip(wanted, ground_under(doc, wanted)):
        got = least_move(t["ink"], grounds, t["needed"])
        if (got["hex"].upper() == t["ink"].upper()
                or math.dist(to_lab(got["hex"]), to_lab(t["ink"])) < MOVED_DE):
            if not got['reads']:
                fixed.append({'kind': 'contrast', 'fixed': False, 'status': 'attempted',
                              'before_ratio': min(ratio(t['ink'], g) for g in grounds),
                              'after_ratio': got['ratio'], 'required_ratio': t['needed'],
                              'what': t['what'] + ' remains unreadable; no permitted ink move passed the check'})
            continue
        colour = Color.from_hex(got["hex"])
        # the colour it moved from, kept on the drawing: its record (``colour_sources``) is that colour's own
        moved = doc.metadata.setdefault(MOVED_KEY, {})
        moved[colour.to_hex().upper()] = moved.get(t["ink"].upper(), t["ink"].upper())
        if isinstance(t["node"], AssetRef):
            t["node"].recolor = colour
        else:
            t["node"].color = colour
        before = min(ratio(t["ink"], g) for g in grounds)
        what = ("%s read %.1f:1 against what lies behind it (%s) — its ink %s made %s %s, %.1f:1%s" % (
            t["what"], before, ", ".join(grounds), t["ink"], "lighter" if got["moved_l"] > 0 else "darker",
            got["hex"], got["ratio"],
            "" if got["kept_gold"] or not is_gold(t["ink"]) else " (no gold of its hue reads there: no longer gold)"))
        if is_gold(t["ink"]) and not is_gold(got["hex"]):
            # a gold the line could not stay is printed in its ink: its foil (or metallic) plate taken off, said
            from apps.ire.container_finishes import INK_FINISHES
            plated = [f for f in t["node"].finishes if f.kind in INK_FINISHES and str(f.plate).endswith("_GOLD")]
            if plated:
                t["node"].finishes = [f for f in t["node"].finishes if f not in plated]
                what += "; its %s plate taken off — it prints in its ink" % plated[0].kind
        if not got["reads"]:
            # the most its hue reads; what it still lacks is shown by the drawing's own check (``remaining``)
            what += ", the most its hue reads — still under %g:1" % t["needed"]
        fixed.append({"kind": "contrast", "fixed": bool(got['reads']),
                      "status": 'passed' if got['reads'] else 'improved' if got['ratio'] > before else 'attempted',
                      "before_ratio": before, "after_ratio": got['ratio'], "required_ratio": t['needed'],
                      "what": what})
    return fixed


def remaining(doc) -> list:
    """``[finding]`` — every mark and line of type on ``doc`` that still reads under its ratio, shown, never fixed."""
    wanted = targets(doc)
    out = []
    for t, grounds in zip(wanted, ground_under(doc, wanted)):
        if not grounds:
            continue
        worst = min(ratio(t["ink"], g) for g in grounds)
        if not reads(t["ink"], grounds, t["needed"]):
            out.append({"kind": "contrast", "fixed": False,
                        "what": "%s reads %.1f:1 against what lies behind it (%s), under the %g:1 it needs" % (
                            t["what"], worst, ", ".join(grounds), t["needed"])})
    return out
