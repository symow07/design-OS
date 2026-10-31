"""Day 9, direction A-2 ("Golden Hour"): the louvred light of the BBROSE O, drawn by our engine as vectors (D-D9-3/4/5).

WHAT IT DRAWS. Late sun through a round louvred window — the O of BBROSE, a circle — falls obliquely on the wall and
lies there as an OVAL (a circle cast at an angle is an ellipse: 146 x 84 mm is the O seen at about 55 degrees). The
window's louvre cuts the light into parallel BARS that run along the oval's long axis. Inside each bar the light is
ENGINE-TURNED: straight gold-foil lines along the bar (``line_mm`` wide at ``pitch_mm``), and within ``fade_mm`` of each
long edge of a bar the lines step SHORTER, so the bar's light softens at its edges as light does on plaster. There is
no rim and no halo: the oval exists only as the place where the bars stop (J1: "light, not a glow frame"). The bars
are embossed (one raised piece per bar, a hair larger than its lines, so the foil sits on the crown).

THE RHYTHM (J1's lift: "a FIXED, OWNABLE BAR RHYTHM reused on every product"). The bar widths are ``rhythm`` units and
the gaps between bars ``gap_ratio`` units, the whole stack exactly filling the oval's short diameter, so the outermost
bars are the oval's own caps. The house rhythm offered with this module is RHYTHM_FIVE = (1, 3, 1, 3, 1): its CORE
is 3-1-3 — two broad bars of light parted by a slit that lies on the O's own diameter — with a slit at each rim. The
core is the signature: it is what survives every crop (on the 146 x 84 oval cropped by the lid's top edge, as in both
chosen sketches, the top slit falls off the lid and the lid reads 3-1-3-1; a lipstick's sliver reads 3-1-3), it is
not the even louvre every window casts, nor the 1-2-3-2-1 swell of a generic sunset. RHYTHM_FOUR = (3, 1, 3, 1) keeps
the same core with four broader bars (cropped the same way it also reads 3-1-3-1). ``measures`` says what the lid
actually shows: ``bars_visible`` and ``visible_rhythm``.

THE PRINT (D-D9-3): every line a filled foil rectangle with square ends, never a stroke cap; each line's ends are where
its centre line meets the oval, pulled in by the fade, then kept whole inside the lid (a line the lid crops ends square
inside the edge — a cut along the edge would leave a foil wedge finer than the press allows). Lines shorter than
MIN_LINE_MM are not drawn. The foil limits hold by construction: lines ``line_mm`` >= FOIL_LINE_MIN_MM, gaps
``pitch_mm - line_mm`` >= FOIL_GAP_MIN_MM, and between bars the gap is millimetres. No metallic ink anywhere.

OUTPUT (the Day 9 generators' shared form): ``{'kind', 'marks', 'regions', 'params', 'measures'}``; millimetres on the
190 x 120 mm lid, y down. Every region polygon is ONE hole-free ring (a list of points); a region with a hole is given
as hole-free pieces cut through each hole, whose union is the region. Regions:
- ``lit``: each bar of light as the outline of its lines (the plate's guide: paint warm light here);
- ``oval``: the whole oval of light, clipped to the lid (light and the shadow between the bars);
- ``shadow``: the lid minus the oval — the wall in shadow, where the type sits;
- ``slats``: the oval minus the bars — the louvre's own shadows inside the light (paint them as shadow, softer than
  the wall's: with them the oval has no rim, it is only where the bars stop);
- ``deep_shadow``: the deepest shadow, the spec's lower type zones (top below DEEP_FROM of the lid) grown by
  DEEP_GROW_MM, each cluster's hull, minus the oval
  (the plate pushes this to the deep teal-ink, J1's repair);
- ``relief``: the emboss pieces, one per bar ([] when ``emboss`` is False);
- ``footprint``: everything drawn (the bars with their emboss margin), for the type to keep clear of;
- ``paint``: the whole lid minus the foil lines (the model paints the plaster everywhere, light and shadow).

$0: geometry only (shapely). Nothing here calls a provider.
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

KIND = 'a2_golden_hour'
LID_W_MM, LID_H_MM = 190.0, 120.0
LID_AREA_MM2 = LID_W_MM * LID_H_MM

GOLD = 'gold_foil'
#: the house rhythms (see the module's text): five bars, and four
RHYTHM_FIVE = (1, 3, 1, 3, 1)
RHYTHM_FOUR = (3, 1, 3, 1)

#: the press's foil limits (D-D9-3)
FOIL_LINE_MIN_MM = 0.1
FOIL_GAP_MIN_MM = 0.2
#: the shortest engraved line drawn (the spec asks at least 0.5 mm; a 1 mm dash reads as a line, not a dot)
MIN_LINE_MM = 1.0
#: the fade: within ``fade_mm`` of a bar's long edge each end of a line is pulled in along an elliptical quarter whose
#: reach along the bar is FADE_REACH times ``fade_mm`` — the bar's corners soften over a long, light curve
FADE_REACH = 4.0
#: every foil line and every emboss piece stays this far inside the lid's edge: a line the edge crops ends square here,
#: never on the fold, where neither foil nor a relief registers
EDGE_MARGIN_MM = 1.5
#: a bar the lid crops to less light than this is not drawn at all (a crumb of a bar reads as a mistake, not as light)
MIN_BAR_MM2 = 40.0
#: every type zone keeps at least this from the oval (spec: "every text zone at least 6 mm clear of it")
CLEAR_MM = 6.0
#: the deep shadow holds the type zones whose top lies below this share of the lid's height (the lower right: the
#: name, the descriptors, the shades and the net — not the logo, which keeps its clearance but lies in the plain shadow)
DEEP_FROM = 0.5
#: the deep shadow: the type zones grown by this
DEEP_GROW_MM = 6.0
#: the emboss piece is the bar's outline grown by this, so every foil line sits on the crown, not on the shoulder
RELIEF_MARGIN_MM = 0.35
#: the oval and the bar outlines are sampled at this step along the short axis (mm)
SAMPLE_MM = 0.05
#: ellipse polygons drawn with this many points
OVAL_POINTS = 720
#: buffers drawn with this many segments a quarter circle
QUAD_SEGS = 16
#: region rings are written to this many decimals of a millimetre (a nanometre: unions of the pieces stay exact)
RING_DECIMALS = 6
#: ring pieces of less area than this are dust from boolean operations, not drawing
DUST_MM2 = 1e-4


# --- geometry helpers --------------------------------------------------------------------------------------------------

def _pieces(geom) -> list:
    """The polygons of ``geom`` (a Polygon, MultiPolygon or collection), dust dropped."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return [geom] if geom.area > DUST_MM2 else []
    if geom.geom_type in ('MultiPolygon', 'GeometryCollection'):
        return [p for g in geom.geoms for p in _pieces(g)]
    return []


def _holefree(geom) -> list:
    """``geom`` as hole-free polygons whose union is ``geom``: a polygon with a hole is cut by a vertical line through
    the hole's centre, and cut again until no piece holds a hole (an exact partition)."""
    out, todo = [], list(_pieces(geom))
    while todo:
        poly = todo.pop()
        if not poly.interiors:
            out.append(poly)
            continue
        cx = Polygon(poly.interiors[0]).centroid.x
        x0, y0, x1, y1 = poly.bounds
        todo.extend(_pieces(poly.intersection(box(x0 - 1.0, y0 - 1.0, cx, y1 + 1.0))))
        todo.extend(_pieces(poly.intersection(box(cx, y0 - 1.0, x1 + 1.0, y1 + 1.0))))
    return out


def _ring(poly) -> list:
    return [(round(float(x), RING_DECIMALS), round(float(y), RING_DECIMALS))
            for x, y in list(poly.exterior.coords)[:-1]]


def _rings(geom) -> list:
    return [_ring(p) for p in _holefree(geom)]


def _mark(points, *, width_mm, ink, fill, closed, finishes) -> dict:
    return {'points': [(float(x), float(y)) for x, y in points], 'closed': closed, 'width': width_mm, 'ink': ink,
            'fill': fill, 'finishes': list(finishes)}


class _Frame:
    """The oval's own frame: u along the long axis, v across it; ``turn_deg`` counter-clockwise as seen (y up), so
    a negative turn descends to the right on the lid (y down), as in the sketches."""

    def __init__(self, centre_mm, turn_deg):
        t = math.radians(turn_deg)
        self.cx, self.cy = float(centre_mm[0]), float(centre_mm[1])
        self.eu = (math.cos(t), -math.sin(t))
        self.ev = (math.sin(t), math.cos(t))

    def at(self, u, v) -> tuple:
        return (self.cx + u * self.eu[0] + v * self.ev[0], self.cy + u * self.eu[1] + v * self.ev[1])

    def u_range_in_lid(self, v) -> tuple:
        """The centre-line parameters u for which the point (u, v) lies inside the lid, EDGE_MARGIN_MM in."""
        lo, hi = -math.inf, math.inf
        for (p, e, top) in ((self.cx + v * self.ev[0], self.eu[0], LID_W_MM),
                            (self.cy + v * self.ev[1], self.eu[1], LID_H_MM)):
            if abs(e) < 1e-12:
                if not EDGE_MARGIN_MM <= p <= top - EDGE_MARGIN_MM:
                    return (1.0, -1.0)
                continue
            a, b = (EDGE_MARGIN_MM - p) / e, (top - EDGE_MARGIN_MM - p) / e
            lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
        return (lo, hi)


def _length(corners) -> float:
    """A line's length: its rectangle's first side (the corners run along the line, then across)."""
    (x0, y0), (x1, y1) = corners[0], corners[1]
    return math.hypot(x1 - x0, y1 - y0)


def _half_chord(a_mm, b_mm, v) -> float:
    q = 1.0 - (v / b_mm) ** 2
    if q <= 0.0:
        return 0.0
    return a_mm * math.sqrt(q)


def _fade_pull(d_mm, fade_mm) -> float:
    """How far each end of a line is pulled in at distance ``d_mm`` (its centre) from its bar's long edge: an
    elliptical quarter, 0 at ``fade_mm`` and beyond, FADE_REACH x ``fade_mm`` at the edge itself."""
    if fade_mm <= 0.0 or d_mm >= fade_mm:
        return 0.0
    x = (fade_mm - max(d_mm, 0.0)) / fade_mm
    return FADE_REACH * fade_mm * (1.0 - math.sqrt(max(1.0 - x * x, 0.0)))


def _oval_polygon(frame, a_mm, b_mm) -> Polygon:
    pts = []
    for k in range(OVAL_POINTS):
        th = 2.0 * math.pi * k / OVAL_POINTS
        pts.append(frame.at(a_mm * math.cos(th), b_mm * math.sin(th)))
    return Polygon(pts)


def _zone_boxes(type_zones) -> dict:
    """The spec's type zones (lid fractions x0, y0, x1, y1) as boxes in mm."""
    out = {}
    for name, z in type_zones.items():
        x0, y0, x1, y1 = (float(c) for c in z)
        if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
            raise ValueError('type zone %r is not a box in lid fractions: %r' % (name, z))
        out[name] = box(x0 * LID_W_MM, y0 * LID_H_MM, x1 * LID_W_MM, y1 * LID_H_MM)
    return out


# --- the generator -----------------------------------------------------------------------------------------------------

def golden_hour(*, oval_centre_mm, oval_mm, turn_deg, bars, rhythm, gap_ratio, line_mm, pitch_mm, fade_mm, emboss,
                type_zones) -> dict:
    """The oval of louvred light, engine-turned in gold foil, its bars embossed.

    ``oval_centre_mm`` (x, y) on the lid; ``oval_mm`` (long, short) diameters; ``turn_deg`` the long axis from the lid's
    horizontal, counter-clockwise as seen (−20 descends to the right); ``bars`` 4 or 5; ``rhythm`` the bars' relative
    widths across the oval (len == bars); ``gap_ratio`` the gap between two bars in rhythm units; ``line_mm`` and
    ``pitch_mm`` the engraved lines; ``fade_mm`` the soft edge of each bar; ``emboss`` True raises every bar;
    ``type_zones`` the spec's zones {name: (x0, y0, x1, y1) in lid fractions} — the oval keeps CLEAR_MM from each.
    Refuses (ValueError) anything the press or the spec does not allow."""
    long_mm, short_mm = (float(c) for c in oval_mm)
    rhythm = tuple(float(r) for r in rhythm)
    if bars not in (4, 5) or len(rhythm) != bars or min(rhythm) <= 0.0:
        raise ValueError('bars is 4 or 5 and rhythm gives each a positive width: bars %r, rhythm %r' % (bars, rhythm))
    if not long_mm >= short_mm > 0.0:
        raise ValueError('oval_mm is (long, short) with long >= short > 0: %r' % (oval_mm,))
    if line_mm < FOIL_LINE_MIN_MM:
        raise ValueError('a foil line of %.3f mm is under the press limit %.2f mm' % (line_mm, FOIL_LINE_MIN_MM))
    if pitch_mm - line_mm < FOIL_GAP_MIN_MM:
        raise ValueError('a foil gap of %.3f mm is under the press limit %.2f mm' % (pitch_mm - line_mm,
                                                                                    FOIL_GAP_MIN_MM))
    if gap_ratio <= 0.0 or fade_mm < 0.0:
        raise ValueError('gap_ratio must be positive and fade_mm not negative: %r, %r' % (gap_ratio, fade_mm))
    a_mm, b_mm = long_mm / 2.0, short_mm / 2.0
    frame = _Frame(oval_centre_mm, turn_deg)
    lid = box(0.0, 0.0, LID_W_MM, LID_H_MM)
    face = box(EDGE_MARGIN_MM, EDGE_MARGIN_MM, LID_W_MM - EDGE_MARGIN_MM, LID_H_MM - EDGE_MARGIN_MM)
    oval = _oval_polygon(frame, a_mm, b_mm)
    zones = _zone_boxes(type_zones)
    clearance = {name: round(oval.distance(z), 3) for name, z in zones.items()}
    near = {k: d for k, d in clearance.items() if d < CLEAR_MM}
    if near:
        raise ValueError('the oval comes within %.0f mm of type zone(s): %r' % (CLEAR_MM, near))
    if not oval.intersects(lid):
        raise ValueError('the oval does not fall on the lid')

    # the stack of bars across the short diameter
    unit_mm = short_mm / (sum(rhythm) + (bars - 1) * gap_ratio)
    gap_mm = gap_ratio * unit_mm
    if 2.0 * fade_mm > unit_mm * min(rhythm):
        raise ValueError('fade_mm %.2f is more than half the narrowest bar (%.2f mm)' % (fade_mm, unit_mm * min(rhythm)))
    edges, v = [], -b_mm
    for r in rhythm:
        edges.append((v, v + r * unit_mm))
        v += r * unit_mm + gap_mm

    marks, lit, relief, bar_rows, dropped = [], [], [], [], []
    half_w = line_mm / 2.0
    shortest = math.inf
    for k, (v0, v1) in enumerate(edges):
        width = v1 - v0
        n_lines = int(math.floor((width - line_mm) / pitch_mm + 1e-9)) + 1
        first = v0 + (width - (n_lines - 1) * pitch_mm) / 2.0
        e0, e1 = first - half_w, first + (n_lines - 1) * pitch_mm + half_w      # the bar's foil edges
        bar_marks = []
        for j in range(n_lines):
            vc = first + j * pitch_mm
            d = min(vc - e0, e1 - vc) - half_w                                    # the line's centre from the edge
            # the oval: the shorter chord of the line's two long sides, so no corner leaves the oval by more than
            # a hair of the line's own half width
            half = min(_half_chord(a_mm, b_mm, vc - half_w), _half_chord(a_mm, b_mm, vc + half_w))
            half -= _fade_pull(d + half_w, fade_mm)
            lo, hi = -half, half
            for side in (vc - half_w, vc + half_w):                               # the whole line inside the lid
                l_lo, l_hi = frame.u_range_in_lid(side)
                lo, hi = max(lo, l_lo), min(hi, l_hi)
            if hi - lo < MIN_LINE_MM:
                continue
            corners = [frame.at(lo, vc - half_w), frame.at(hi, vc - half_w), frame.at(hi, vc + half_w),
                       frame.at(lo, vc + half_w)]
            bar_marks.append(_mark(corners, width_mm=0.0, ink=GOLD, fill=GOLD, closed=True, finishes=('foil',)))
        # the bar's outline: the same profile read continuously across the bar
        left, right = [], []
        steps = max(2, int(math.ceil((e1 - e0) / SAMPLE_MM)))
        for i in range(steps + 1):
            vs = e0 + (e1 - e0) * i / steps
            d = min(vs - e0, e1 - vs)
            half = _half_chord(a_mm, b_mm, vs) - _fade_pull(d, fade_mm)
            if half <= 0.0:
                continue
            left.append(frame.at(-half, vs))
            right.append(frame.at(half, vs))
        outline = Polygon(right + left[::-1]).buffer(0) if len(right) >= 2 else Polygon()
        outline = outline.intersection(face)
        kept, crumbs = [], []
        for piece in _pieces(outline):
            (kept if piece.area >= MIN_BAR_MM2 else crumbs).append(piece)
        for piece in crumbs:
            dropped.append({'bar': k + 1, 'lit_area_mm2': round(piece.area, 2)})
        if not kept:
            continue
        keep = unary_union(kept).buffer(SAMPLE_MM)
        bar_marks = [m for m in bar_marks if keep.intersects(Polygon(m['points']))]
        if not bar_marks:
            continue
        marks.extend(bar_marks)
        shortest = min(shortest, min(_length(m['points']) for m in bar_marks))
        outline = unary_union(kept)
        lit.append(outline)
        if emboss:
            relief.extend(_pieces(outline.buffer(RELIEF_MARGIN_MM, quad_segs=QUAD_SEGS).intersection(face)))
        bar_rows.append({'bar': k + 1, 'rhythm': rhythm[k], 'width_mm': round(width, 3),
                         'lines': len(bar_marks), 'v_mm': [round(v0, 3), round(v1, 3)],
                         'lit_area_mm2': round(outline.area, 2)})

    foil_geoms = [Polygon(m['points']) for m in marks]
    foil = unary_union(foil_geoms)
    lit_u = unary_union(lit)
    relief_u = unary_union(relief) if relief else Polygon()
    footprint = unary_union([lit_u.buffer(RELIEF_MARGIN_MM, quad_segs=QUAD_SEGS), foil]).intersection(lid)
    oval_on_lid = oval.intersection(lid)
    shadow = lid.difference(oval)
    lower = [z for z in zones.values() if z.bounds[1] >= DEEP_FROM * LID_H_MM]
    grown = unary_union([z.buffer(DEEP_GROW_MM, join_style=2) for z in lower])
    deep = unary_union([p.convex_hull for p in _pieces(grown)]).intersection(lid).difference(oval)

    return {
        'kind': KIND,
        'marks': marks,
        'regions': {
            'lit': _rings(lit_u),
            'oval': _rings(oval_on_lid),
            'shadow': _rings(shadow),
            'slats': _rings(oval_on_lid.difference(lit_u)),
            'deep_shadow': _rings(deep),
            'relief': [_ring(q) for p in relief for q in _holefree(p)],
            'footprint': _rings(footprint),
            'paint': _rings(lid.difference(foil)),
        },
        'params': {'oval_centre_mm': [float(c) for c in oval_centre_mm], 'oval_mm': [long_mm, short_mm],
                   'turn_deg': float(turn_deg), 'bars': bars, 'rhythm': list(rhythm), 'gap_ratio': float(gap_ratio),
                   'line_mm': float(line_mm), 'pitch_mm': float(pitch_mm), 'fade_mm': float(fade_mm),
                   'emboss': bool(emboss), 'type_zones': {k: list(v) for k, v in type_zones.items()}},
        'measures': {
            'descends_right': math.sin(math.radians(turn_deg)) < 0.0,
            'bars_visible': len(bar_rows), 'visible_rhythm': [row['rhythm'] for row in bar_rows],
            'unit_mm': round(unit_mm, 4), 'gap_between_bars_mm': round(gap_mm, 4), 'bars': bar_rows, 'bars_not_drawn': dropped,
            'lines': len(marks), 'shortest_line_mm': round(shortest, 3) if marks else None,
            'lines_per_cm_densest': {'value': round(10.0 / pitch_mm, 3), 'across_deg': float(turn_deg) - 90.0,
                                     'where': 'inside every bar, across its lines (geometric: 10 mm / pitch)'},
            'foil_limits_geometric': {'line_mm': line_mm, 'gap_mm': round(pitch_mm - line_mm, 4),
                                      'between_bars_mm': round(gap_mm, 3), 'shortest_line_mm':
                                      round(shortest, 3) if marks else None,
                                      'holds': line_mm >= FOIL_LINE_MIN_MM and pitch_mm - line_mm >= FOIL_GAP_MIN_MM},
            'foil_area_mm2': round(foil.area, 2), 'foil_pct': round(100.0 * foil.area / LID_AREA_MM2, 3),
            'relief_area_mm2': round(relief_u.area, 2), 'relief_pct': round(100.0 * relief_u.area / LID_AREA_MM2, 3),
            'lit_area_mm2': round(lit_u.area, 2), 'oval_on_lid_mm2': round(oval_on_lid.area, 2),
            'oval_cropped': not oval.within(lid),
            'type_zone_clearance_mm': clearance,
        },
    }
