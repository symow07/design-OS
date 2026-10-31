"""Day 9, direction C-1 ("Signed Baguette"): one gold bar cut like a baguette stone, drawn by our engine as vectors.

WHAT IT DRAWS (docs/audit/day-9/directions/C-1.json, the chosen sketch C-1.1 with J1's repair "reduce the bar to 0.75
of the width"). A long table with straight sides between two long bevels; each end cut in THREE facets coming to a
point at the angles of the house's rose cut. The rose cut's facet is the equilateral triangle (``orn_b1``: the facet
of the house's rose cut is the equilateral triangle, 60 degrees), so the whole stone lies on that lattice:

- the tip is the rose cut's hexagon corner, 120 degrees (each outer end edge 60 degrees to the bar's axis);
- the end's middle facet is the rose cut's own facet, an equilateral triangle on the table's end (apex 60 degrees);
- its two side facets are the half-facets, 30-60-90 triangles: the edge from the outer corner to the table's corner
  is square to the outer edge, which puts every edge of the stone at 0, 30, 60 or 90 degrees to the axis and makes
  the bevel one sixth of the bar's height.

Nine planes: the table, two long bevels and three facets at each end. Every plane is ENGINE-TURNED in gold foil with
straight lines of ``line_mm`` at ``pitch_mm``, at its own angle (HATCH_ANGLES), the lines' phase set so the plane's
parallel edge falls mid-gap; a solid foil ridge runs along every facet edge and round the girdle, and the lines run
into it as an engraver's lines run into a bright-cut edge (the joins filleted where a line meets an edge at a slant
closer than the foil gap allows). The name is cut THROUGH the table: ``cutouts_mm`` (the face's own outlines, from
``name_cutouts``) are openings with no ink of ours — the hero picture shows in them — each edged OUTSIDE its outline by
a solid gold rim ``rim_mm`` wide, so an opening is exactly the letter the face draws. Between the foil lines the bar
prints one flat process ink (BODY_HEX: printed, never "metallic"; there is no metallic ink). Each plane is its own
emboss pillow (``emboss``), the pillows parted by valleys under the ridges; the table's pillow stops short of the
letters' openings.

PRINT LIMITS (D-D9-3) by construction and measured: foil lines >= FOIL_LINE_MIN_MM and gaps >= FOIL_GAP_MIN_MM — the
foil union is closed at CLOSE_R_MM (every gap under the limit filled: the fillets) and opened at OPEN_R_MM (every part
under the limit removed), and ``measures['foil_limits_geometry']`` reads what each would still change.

OUTPUT (the Day 9 generators' shared form): ``{'kind', 'marks', 'regions', 'params', 'measures'}``, millimetres on the
190 x 120 mm lid, y down. Every mark and every region polygon is ONE hole-free ring, oriented anticlockwise on the page
(a shape with a hole is given as hole-free pieces cut through the hole, a hair of overlap between pieces of one ink,
whose union is the shape), so marks of one ink drawn as one compound path at nonzero winding unite and never cancel.
"""
from __future__ import annotations

import math

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

KIND = 'c1_signed_baguette'
LID_W_MM, LID_H_MM = 190.0, 120.0
LID_AREA_MM2 = LID_W_MM * LID_H_MM

GOLD = 'gold_foil'
BLIND = 'blind'
#: the spec's gold (C-1 colours: gold_foil) — the foil's depiction on page 1
GOLD_HEX = '#C9A55C'
#: the flat process ink the bar prints between its foil lines: a deep warm ochre, so the engine-turning reads as cut
#: gold on gold (a printed colour; D-D9-3: anything finer than foil allows is printed ink, never "metallic")
BODY_HEX = '#94733F'
BODY_INK = 'ink:' + BODY_HEX

#: the press's foil limits (D-D9-3)
FOIL_LINE_MIN_MM = 0.1
FOIL_GAP_MIN_MM = 0.2
#: the morphology that holds them: closing fills every gap under 2 x CLOSE_R_MM, the foil gap limit (the
#: engine-turning's own gap, pitch - line = 0.28 mm, and a ridge's clearance to the next line, 0.22 mm, untouched); opening removes every part under 2 x OPEN_R_MM (under the 0.12 mm line)
CLOSE_R_MM = 0.1
OPEN_R_MM = 0.052
#: closing then opening, this many times (an opening can leave a gap a closing must fill again)
MORPH_PASSES = 2
#: what a morphology check may still change and be called nothing (boolean noise)
MORPH_SLACK_MM2 = 0.002
#: the foil ridge along every facet edge (centred on the edge) and the girdle band round the bar (inside it)
RIDGE_MM = 0.24
GIRDLE_MM = 0.36
#: a hatch parallel to the girdle puts a line this far inside the bar's edge: wholly under the girdle band, and the
#: next line clears the band's inner edge by pitch - this - line/2 (0.4 - 0.26 - 0.06 = 0.08 past it: 0.24 mm gap)
GIRDLE_LINE_MM = 0.26
#: each plane's emboss pillow is the plane inset by this: a valley 2 x this wide under every ridge
EMBOSS_INSET_MM = 0.3
#: the table's pillow keeps this clear of a letter's opening: the opening sits in a narrow moat, and the relief's
#: page-1 depiction (pdf_ai: its outline stroked 0.3 mm wide, 0.25 mm off on each axis) stays under the body ink
EMBOSS_LETTER_CLEAR_MM = 0.5
#: a pillow narrower than this is no pillow the die can strike (the table's slivers between close letters)
EMBOSS_MIN_MM = 0.6
#: the name must lie this far inside the table's own edges (rims included)
TABLE_CLEAR_MM = 1.5
#: a counter island must be at least this wide (C-1's print limits: the letters' counters at least 0.4 mm)
COUNTER_MIN_MM = 0.4
#: hole-free pieces of one ink overlap by this, so no anti-aliased seam shows where they meet
PIECE_OVERLAP_MM = 0.01
#: curves flattened to within this of the face's own cubic (lettering.FLATTEN_TOL_MM)
FLATTEN_TOL_MM = 0.005
#: buffers drawn with this many segments a quarter circle
QUAD_SEGS = 12
#: ring pieces of less area than this are dust from boolean operations, not drawing
DUST_MM2 = 1e-4
#: the one end shape the spec draws: three facets coming to a point
END_FACET_COUNT = 3

#: each plane's engine-turning, degrees from the bar's axis (y down), and the edge that sets its phase. The left end is
#: drawn and the right end is its mirror. Neighbouring planes differ by at least 30 degrees, so each takes the light
#: its own way: the table runs with the bar; the bevels stand square to it; each side facet runs with its outer edge
#: (the rose cut's 60); the middle facet runs with its base, the table's end — chevrons closing on the point.
HATCH_ANGLES = {'table': 0.0, 'bevel_top': 90.0, 'bevel_bottom': 90.0,
                'end_upper': -60.0, 'end_middle': 90.0, 'end_lower': 60.0}


# --- geometry helpers ------------------------------------------------------------------------------------------------

def _pieces(geom) -> list:
    """The polygons of ``geom`` (a Polygon, MultiPolygon or collection), dust dropped."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return [geom] if geom.area > DUST_MM2 else []
    if geom.geom_type in ('MultiPolygon', 'GeometryCollection'):
        return [p for g in geom.geoms for p in _pieces(g)]
    return []


def _polys_of(geom):
    """``geom`` as a (Multi)Polygon of its polygon parts — a boolean's stray lines and points dropped."""
    parts = _pieces(geom)
    if not parts:
        return Polygon()
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def _opened(geom, radius_mm):
    """Morphological opening: every part narrower than twice ``radius_mm`` removed."""
    return _polys_of(geom.buffer(-radius_mm, quad_segs=QUAD_SEGS).buffer(radius_mm, quad_segs=QUAD_SEGS))


def _closed(geom, radius_mm):
    """Morphological closing: every gap narrower than twice ``radius_mm`` filled."""
    return _polys_of(geom.buffer(radius_mm, quad_segs=QUAD_SEGS).buffer(-radius_mm, quad_segs=QUAD_SEGS))


def _holefree(geom, *, overlap_mm: float) -> list:
    """``geom`` as hole-free polygons whose union is ``geom``: a polygon with holes is cut by a vertical line through
    its middle hole's centre, each side kept ``overlap_mm`` past the cut, and cut again until no piece holds a hole."""
    out, todo = [], list(_pieces(geom))
    while todo:
        poly = todo.pop()
        if not poly.interiors:
            out.append(poly)
            continue
        xs = sorted(Polygon(h).centroid.x for h in poly.interiors)
        cx = xs[len(xs) // 2]
        x0, y0, x1, y1 = poly.bounds
        todo.extend(_pieces(poly.intersection(box(x0 - 1.0, y0 - 1.0, cx + overlap_mm, y1 + 1.0))))
        todo.extend(_pieces(poly.intersection(box(cx - overlap_mm, y0 - 1.0, x1 + 1.0, y1 + 1.0))))
    return out


def _ring(poly) -> list:
    """A hole-free polygon's ring, anticlockwise on the page (y down), the closing point not repeated."""
    coords = list(orient(Polygon(poly.exterior), sign=-1.0).exterior.coords)[:-1]
    return [(round(float(x), 4), round(float(y), 4)) for x, y in coords]


def _mark(points, *, width_mm, ink, fill, closed, finishes) -> dict:
    return {'points': [(float(x), float(y)) for x, y in points], 'closed': closed, 'width': width_mm, 'ink': ink,
            'fill': fill, 'finishes': list(finishes)}


def signed_area(ring) -> float:
    """The ring's signed area by the shoelace sum (positive anticlockwise in y-up axes)."""
    pts = list(ring)
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


def rings_sha256(rings) -> str:
    """The cutouts' identity: sha256 of their points rounded to 0.1 micrometre, ring by ring."""
    import hashlib
    text = ';'.join(','.join('%.4f %.4f' % (float(x), float(y)) for x, y in ring) for ring in rings)
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def letters_of(rings):
    """The cutouts as one geometry, filled as the face fills them (nonzero): the rings of the outer orientation (that
    of the largest ring) unite, and the rings turning the other way are cut from them."""
    if not rings:
        raise ValueError('no cutouts: the name is cut through the table, so its outlines are required')
    largest = max(rings, key=lambda r: abs(signed_area(r)))
    outer_sign = math.copysign(1.0, signed_area(largest))
    outs, holes = [], []
    for ring in rings:
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        (outs if math.copysign(1.0, signed_area(ring)) == outer_sign else holes).append(poly)
    shape = unary_union(outs)
    if holes:
        shape = shape.difference(unary_union(holes))
    return _polys_of(shape)


def inscribed_mm(poly) -> float:
    """The width of the widest disk ``poly`` holds (twice its pole of inaccessibility's distance), to 0.005 mm."""
    lo, hi = 0.0, max(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
    while hi - lo > 0.005:
        mid = 0.5 * (lo + hi)
        if poly.buffer(-mid / 2.0, quad_segs=QUAD_SEGS).is_empty:
            hi = mid
        else:
            lo = mid
    return lo


# --- the stone -------------------------------------------------------------------------------------------------------

def _ray_hit(p, u, q, v):
    """Where the line p + s u meets the line q + t v."""
    det = u[0] * (-v[1]) - u[1] * (-v[0])
    if abs(det) < 1e-12:
        raise ValueError('the facet edges are parallel: no table corner')
    dx, dy = q[0] - p[0], q[1] - p[1]
    s = (dx * (-v[1]) - dy * (-v[0])) / det
    return (p[0] + s * u[0], p[1] + s * u[1])


def stone(*, centre_mm, length_mm, height_mm, end_facets) -> dict:
    """The baguette's planes as polygons (mm, y down) and its edges as segments.

    ``end_facets``: ``{'count': 3, 'tip_deg': 120.0, 'apex_deg': 60.0}`` — the tip's angle (the outer end edges each
    half of it to the axis) and the middle facet's apex at the tip; the table's corner is where the middle facet's side
    meets the line from the outer corner square to the outer edge (the rose cut's 30-60-90 half-facet)."""
    if end_facets['count'] != END_FACET_COUNT:
        raise ValueError('the baguette ends in %d facets coming to a point; %r asked'
                         % (END_FACET_COUNT, end_facets['count']))
    cx, cy = float(centre_mm[0]), float(centre_mm[1])
    half_l, half_h = length_mm / 2.0, height_mm / 2.0
    alpha = math.radians(end_facets['tip_deg'] / 2.0)        # the outer edge to the axis
    beta = math.radians(end_facets['apex_deg'] / 2.0)        # the middle facet's side to the axis
    if not 0.0 < beta < alpha < math.pi / 2.0:
        raise ValueError('the middle facet (apex %g) must lie inside the tip (%g), both under 180 degrees'
                         % (end_facets['apex_deg'], end_facets['tip_deg']))
    tip = (cx - half_l, cy)
    outer_tl = (tip[0] + half_h / math.tan(alpha), cy - half_h)
    # the line from the outer corner, square to the outer edge, meets the middle facet's upper side at the table corner
    u_side = (math.cos(beta), -math.sin(beta))
    u_out = (math.cos(alpha), -math.sin(alpha))
    square = (u_out[1], -u_out[0])                          # the outer edge turned a quarter, pointing in and down
    table_tl = _ray_hit(tip, u_side, outer_tl, square)
    half_t = cy - table_tl[1]
    if not 0.0 < half_t < half_h or not table_tl[0] < cx:
        raise ValueError('the end facets leave no table (corner at %r)' % (table_tl,))

    def mirror_y(p):
        return (p[0], 2.0 * cy - p[1])

    def mirror_x(p):
        return (2.0 * cx - p[0], p[1])

    outer_bl, table_bl = mirror_y(outer_tl), mirror_y(table_tl)
    left = {'end_upper': [tip, outer_tl, table_tl], 'end_middle': [tip, table_tl, table_bl],
            'end_lower': [tip, table_bl, outer_bl]}
    planes = {}
    for name, pts in left.items():
        planes['left_' + name] = Polygon(pts)
        planes['right_' + name] = Polygon([mirror_x(p) for p in pts])
    tr, br = mirror_x(table_tl), mirror_x(table_bl)
    otr, obr = mirror_x(outer_tl), mirror_x(outer_bl)
    planes['table'] = Polygon([table_tl, tr, br, table_bl])
    planes['bevel_top'] = Polygon([outer_tl, otr, tr, table_tl])
    planes['bevel_bottom'] = Polygon([table_bl, br, obr, outer_bl])
    outline = Polygon([tip, outer_tl, otr, mirror_x(tip), obr, outer_bl])
    inner_edges = [(table_tl, tr), (table_bl, br), (tip, table_tl), (tip, table_bl), (outer_tl, table_tl),
                   (outer_bl, table_bl), (table_tl, table_bl)]
    inner_edges += [(mirror_x(a), mirror_x(b)) for a, b in inner_edges[2:]]
    return {'planes': planes, 'outline': outline, 'inner_edges': inner_edges, 'tip': tip, 'outer_tl': outer_tl,
            'table_tl': table_tl, 'half_table_mm': half_t, 'bevel_mm': half_h - half_t,
            'table_box_mm': [table_tl[0], table_tl[1], tr[0], table_bl[1]]}


def _phase_anchor(name: str, geo: dict, plane):
    """The point a plane's lines are counted from (a line runs through it), or None: the plane is phased on the bar's
    centre. A plane whose hatch runs parallel to one of its edges puts a line where that edge's foil hides it whole:
    ON a ridge (the next line then clears the ridge by pitch - line/2 - RIDGE_MM/2), or GIRDLE_LINE_MM inside the
    girdle's outer edge (wholly under the girdle band, the next line clearing its inner edge)."""
    tip, otl, ttl = geo['tip'], geo['outer_tl'], geo['table_tl']
    cy = tip[1]
    if name in ('table', 'left_end_middle'):
        return ttl                                           # the table's long edges and its end: ridges
    if name in ('left_end_upper', 'left_end_lower'):
        far = otl if name == 'left_end_upper' else (otl[0], 2.0 * cy - otl[1])
        ex, ey = far[0] - tip[0], far[1] - tip[1]
        n = (-ey / math.hypot(ex, ey), ex / math.hypot(ex, ey))
        c = plane.centroid
        if (c.x - tip[0]) * n[0] + (c.y - tip[1]) * n[1] < 0:
            n = (-n[0], -n[1])
        return (tip[0] + GIRDLE_LINE_MM * n[0], tip[1] + GIRDLE_LINE_MM * n[1])
    return None


def _hatch(field, *, angle_deg, pitch_mm, line_mm, anchor) -> list:
    """Straight lines ``line_mm`` wide at ``pitch_mm`` across ``field`` at ``angle_deg``: each line a band cut to the
    field (its ends exactly on the field's edges), at whole pitches from ``anchor`` along the normal."""
    if field.is_empty:
        return []
    a = math.radians(angle_deg)
    d = (math.cos(a), math.sin(a))
    n = (-math.sin(a), math.cos(a))
    x0, y0, x1, y1 = field.bounds
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    t_of = [(c[0] - anchor[0]) * n[0] + (c[1] - anchor[1]) * n[1] for c in corners]
    s_of = [(c[0] - anchor[0]) * d[0] + (c[1] - anchor[1]) * d[1] for c in corners]
    s_lo, s_hi = min(s_of) - 1.0, max(s_of) + 1.0
    k_lo = int(math.floor(min(t_of) / pitch_mm)) - 1
    k_hi = int(math.ceil(max(t_of) / pitch_mm)) + 1
    hw = line_mm / 2.0
    out = []
    for k in range(k_lo, k_hi + 1):
        t = k * pitch_mm
        c = (anchor[0] + t * n[0], anchor[1] + t * n[1])
        band = Polygon([(c[0] + s_lo * d[0] - hw * n[0], c[1] + s_lo * d[1] - hw * n[1]),
                        (c[0] + s_hi * d[0] - hw * n[0], c[1] + s_hi * d[1] - hw * n[1]),
                        (c[0] + s_hi * d[0] + hw * n[0], c[1] + s_hi * d[1] + hw * n[1]),
                        (c[0] + s_lo * d[0] + hw * n[0], c[1] + s_lo * d[1] + hw * n[1])])
        out.extend(_pieces(band.intersection(field)))
    return out


# --- the name's outlines ---------------------------------------------------------------------------------------------

def _flatten_segments(segments, *, tol_mm) -> list:
    """A Path's segments (MoveTo, LineTo, CubicTo, ClosePath; mm, y down) as rings of points, in drawing order and
    orientation; each cubic flattened to within ``tol_mm``."""
    rings, ring = [], []
    for s in segments:
        if s.op == 'M':
            if len(ring) > 2:
                rings.append(ring)
            ring = [(s.x, s.y)]
        elif s.op == 'L':
            ring.append((s.x, s.y))
        elif s.op == 'C':
            p0 = ring[-1]
            d = max(math.hypot(p0[0] - 2 * s.x1 + s.x2, p0[1] - 2 * s.y1 + s.y2),
                    math.hypot(s.x1 - 2 * s.x2 + s.x, s.y1 - 2 * s.y2 + s.y))
            n = max(2, int(math.ceil(math.sqrt(0.75 * d / tol_mm))))
            for i in range(1, n + 1):
                t = i / n
                a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
                ring.append((a * p0[0] + b * s.x1 + c * s.x2 + e * s.x, a * p0[1] + b * s.y1 + c * s.y2 + e * s.y))
        elif s.op == 'Z':
            if len(ring) > 2:
                rings.append(ring)
            ring = []
    if len(ring) > 2:
        rings.append(ring)
    return [[(round(x, 5), round(y, 5)) for x, y in r] for r in rings]


def name_cutouts(*, text, face, cap_mm, centre_mm) -> dict:
    """The name's outlines as the cutouts ``baguette`` takes: ``lettering.logotype`` sets ``text`` in ``face`` (a
    licensed, granted stem such as 'Marcellus-Regular'; optical kerning, no operations) at ``cap_mm``, once to measure
    its ink width and once placed: centred on ``centre_mm`` across, its cap band (cap line to baseline) centred on it
    down. Returns ``{'rings', 'record', 'group'}``: the rings in mm, y down, each closed ring in the face's own
    orientation (outsides one way, counters the other: fill them nonzero), and the logotype's record and Group."""
    from apps.ire import lettering
    probe, rec0 = lettering.logotype(text, face, [], cap_mm=cap_mm, x_mm=0.0, top_mm=0.0, colour=GOLD_HEX,
                                     finishes=[])
    width = float(rec0['width_mm'])
    cap = float(rec0['cap_mm_measured'])
    x_mm = float(centre_mm[0]) - width / 2.0
    top_mm = float(centre_mm[1]) - cap / 2.0
    group, record = lettering.logotype(text, face, [], cap_mm=cap_mm, x_mm=x_mm, top_mm=top_mm, colour=GOLD_HEX,
                                       finishes=[])
    paths = [c for c in group.children if c.type == 'path']
    if len(paths) != 1:
        raise ValueError('the logotype holds %d paths; one compound path was expected' % len(paths))
    rings = _flatten_segments(paths[0].segments, tol_mm=FLATTEN_TOL_MM)
    return {'rings': rings, 'record': record, 'group': group}


# --- the generator ---------------------------------------------------------------------------------------------------

def _foil_marks(geom) -> list:
    return [_mark(_ring(p), width_mm=0.0, ink=GOLD, fill=GOLD, closed=True, finishes=['foil'])
            for p in _holefree(geom, overlap_mm=PIECE_OVERLAP_MM)]


def baguette(*, centre_mm, length_mm, height_mm, end_facets, line_mm, pitch_mm, rim_mm, cutouts_mm, emboss) -> dict:
    """The Signed Baguette: one gold bar, its nine planes engine-turned in gold foil, the name cut through its table.

    ``centre_mm``: the bar's centre (x, y) on the lid; ``length_mm`` tip to tip; ``height_mm`` girdle to girdle;
    ``end_facets``: ``{'count': 3, 'tip_deg': 120.0, 'apex_deg': 60.0}`` (``stone``); ``line_mm`` and ``pitch_mm``: the
    engine-turning's foil line and its pitch; ``rim_mm``: each opening's foil rim (outside the letter's outline);
    ``cutouts_mm``: the name's outlines as closed rings (``name_cutouts(...)['rings']``); ``emboss``: True to raise each
    plane as its own pillow.

    Regions: ``paint`` — where the image model paints the hero (the lid outside the bar, and the letters' openings,
    where the shagreen shows through); ``relief`` — the emboss pillows (each plane's pillow, the table's in hole-free
    pieces round the letters); ``footprint`` — the bar's silhouette (what the type keeps clear of); ``openings`` — the
    letters' openings; ``body`` — where the bar prints BODY_HEX (the bar less the openings)."""
    if line_mm < FOIL_LINE_MIN_MM:
        raise ValueError('a foil line of %g mm is under the press limit %g mm' % (line_mm, FOIL_LINE_MIN_MM))
    if pitch_mm - line_mm < FOIL_GAP_MIN_MM:
        raise ValueError('a gap of %g mm is under the press limit %g mm' % (pitch_mm - line_mm, FOIL_GAP_MIN_MM))
    if rim_mm < FOIL_LINE_MIN_MM:
        raise ValueError('a rim of %g mm is under the press limit %g mm' % (rim_mm, FOIL_LINE_MIN_MM))
    geo = stone(centre_mm=centre_mm, length_mm=length_mm, height_mm=height_mm, end_facets=end_facets)
    bar = geo['outline']
    planes = geo['planes']
    lid = box(0.0, 0.0, LID_W_MM, LID_H_MM)
    if not lid.contains(bar):
        raise ValueError('the bar %r leaves the lid' % (bar.bounds,))
    letters = letters_of(cutouts_mm)
    rims = _polys_of(letters.buffer(rim_mm, quad_segs=QUAD_SEGS).difference(letters))
    table = planes['table']
    holds_name = table.buffer(-TABLE_CLEAR_MM, join_style='mitre').contains(letters.buffer(rim_mm))
    if not holds_name:
        raise ValueError('the name (with its rims) does not lie %g mm inside the table %r'
                         % (TABLE_CLEAR_MM, table.bounds))

    # the engine-turning, plane by plane (the left end drawn, the right its mirror)
    cx = float(centre_mm[0])
    lines, per_plane = [], {}
    for name, poly in planes.items():
        if name.startswith('right_'):
            continue
        key = name[len('left_'):] if name.startswith('left_') else name
        field = poly.difference(letters) if name == 'table' else poly
        anchor = _phase_anchor(name, geo, poly)
        if anchor is None:
            anchor = (cx, float(centre_mm[1]))
        drawn = _hatch(field, angle_deg=HATCH_ANGLES[key], pitch_mm=pitch_mm, line_mm=line_mm, anchor=anchor)
        per_plane[name] = {'angle_deg': HATCH_ANGLES[key], 'lines': len(drawn)}
        lines.extend(drawn)
        if name.startswith('left_'):
            twin = 'right_' + key
            lines.extend(affinity.scale(p, xfact=-1.0, yfact=1.0, origin=(cx, 0.0)) for p in drawn)
            per_plane[twin] = {'angle_deg': -HATCH_ANGLES[key], 'lines': len(drawn)}

    # the ridges along every facet edge, the girdle round the bar
    ridges = unary_union([LineString([a, b]).buffer(RIDGE_MM / 2.0, quad_segs=QUAD_SEGS)
                          for a, b in geo['inner_edges']])
    girdle = bar.difference(bar.buffer(-GIRDLE_MM, join_style='mitre'))
    drawn_foil = unary_union([unary_union(lines), ridges, girdle, rims]).intersection(bar).difference(letters)
    # the press's limits by construction: fillets into every gap under the limit (where a line meets an edge at a
    # slant, and in the very tips of an opening's acute corners, where the press fills them anyway), then every part
    # under the line limit removed
    foil = drawn_foil
    for _ in range(MORPH_PASSES):
        foil = _opened(_closed(foil, CLOSE_R_MM).intersection(bar), OPEN_R_MM)
    tip_fillets = foil.intersection(letters).area
    openings = _polys_of(letters.difference(foil))
    gap_pieces = _pieces(_closed(foil, FOIL_GAP_MIN_MM / 2.0 - 0.005).difference(foil))
    still_gaps = sum(p.area for p in gap_pieces)
    worst_gaps = [[round(p.centroid.x, 2), round(p.centroid.y, 2), round(p.area, 5)]
                  for p in sorted(gap_pieces, key=lambda q: -q.area)[:6]]
    still_thin = foil.difference(_opened(foil, FOIL_LINE_MIN_MM / 2.0 - 0.005)).area
    fillets = foil.difference(drawn_foil).area

    # the counters: islands of table inside a letter, at least COUNTER_MIN_MM wide
    counters = []
    for p in _pieces(letters):
        for h in p.interiors:
            island = Polygon(h)
            counters.append({'at_mm': [round(island.centroid.x, 2), round(island.centroid.y, 2)],
                             'width_mm': round(inscribed_mm(island), 3), 'area_mm2': round(island.area, 3)})
    narrowest_opening = min(inscribed_mm(p) for p in _pieces(letters))

    # the relief: each plane its own pillow
    pillows = {}
    if emboss:
        for name, poly in planes.items():
            pillow = poly.buffer(-EMBOSS_INSET_MM, join_style='mitre')
            if name == 'table':
                pillow = _opened(pillow.difference(letters.buffer(EMBOSS_LETTER_CLEAR_MM, quad_segs=QUAD_SEGS)),
                                 EMBOSS_MIN_MM / 2.0)
            pillows[name] = _polys_of(pillow)
    # the openings debossed: the letters pressed below the board, so the name is cut down through the raised table
    sunk = openings if emboss else Polygon()
    relief = unary_union(list(pillows.values()) + [sunk])
    emboss_area = unary_union([Polygon()] + list(pillows.values())).area

    body = _polys_of(bar.difference(openings))
    marks = [_mark(_ring(p), width_mm=0.0, ink=BODY_INK, fill=BODY_INK, closed=True, finishes=[])
             for p in _holefree(body, overlap_mm=PIECE_OVERLAP_MM)]
    marks += _foil_marks(foil)
    relief_rings = []
    for name, pillow in pillows.items():
        for p in _holefree(pillow, overlap_mm=PIECE_OVERLAP_MM):
            ring = _ring(p)
            relief_rings.append(ring)
            marks.append(_mark(ring, width_mm=0.0, ink=BLIND, fill=BLIND, closed=True, finishes=['emboss']))
    deboss_rings = [_ring(p) for p in _holefree(sunk, overlap_mm=PIECE_OVERLAP_MM)]
    marks += [_mark(r, width_mm=0.0, ink=BLIND, fill=BLIND, closed=True, finishes=['deboss']) for r in deboss_rings]
    paint = _polys_of(lid.difference(bar).union(openings))

    foil_area = foil.area
    relief_area = relief.area
    densest = 10.0 / pitch_mm
    measures = {
        'lines_per_cm_densest': {'value': round(densest, 3),
                                 'where': 'every plane alike, each at its own angle: one pitch across the bar',
                                 'how': 'by construction: one line every %g mm, read square to the lines (the '
                                        'measured figure is finish_proof.line_density on the FOIL_GOLD plate)'
                                        % pitch_mm,
                                 'angles_deg': sorted({round(v['angle_deg'], 1) for v in per_plane.values()})},
        'planes': {k: dict(v, area_mm2=round(planes[k].area, 3)) for k, v in sorted(per_plane.items())},
        'foil_limits_geometry': {
            'min_line_mm': FOIL_LINE_MIN_MM, 'min_gap_mm': FOIL_GAP_MIN_MM,
            'gaps_left_mm2': round(still_gaps, 5), 'largest_gaps_left': worst_gaps, 'thin_left_mm2': round(still_thin, 5),
            'fillets_added_mm2': round(fillets, 4),
            'fillets_canary': 'about 20 mm2 when the name is centred on the bar at height 30 (the cap line and the '
                              'baseline then sit 0.25 mm from a table line, inside the rims); a much larger figure '
                              'means rims fused with lines into thick bands along the cap line and the baseline',
            'holds': all(p.area <= MORPH_SLACK_MM2 for p in gap_pieces) and still_thin <= MORPH_SLACK_MM2,
            'how': 'the foil closed with a disk a hair under the gap limit and opened with one a hair under the line '
                   'limit, the area each would still change; holds when no gap piece and no thin part is more than '
                   'MORPH_SLACK_MM2 (boolean noise, a 0.045 mm square)'},
        'foil_area_mm2': round(foil_area, 2), 'foil_pct': round(100.0 * foil_area / LID_AREA_MM2, 3),
        'relief_area_mm2': round(relief_area, 2), 'relief_pct': round(100.0 * relief_area / LID_AREA_MM2, 3),
        'emboss_area_mm2': round(emboss_area, 2), 'deboss_area_mm2': round(sunk.area, 2),
        'relief_pillows': len(pillows), 'relief_pieces': len(relief_rings),
        'bar_area_mm2': round(bar.area, 2), 'bar_pct': round(100.0 * bar.area / LID_AREA_MM2, 3),
        'bar_box_mm': [round(v, 3) for v in bar.bounds],
        'table_box_mm': [round(v, 3) for v in geo['table_box_mm']],
        'bevel_mm': round(geo['bevel_mm'], 4), 'half_table_mm': round(geo['half_table_mm'], 4),
        'name_box_mm': [round(v, 3) for v in letters.bounds],
        'name_clear_of_table_edge_mm': round(min(
            letters.bounds[0] - geo['table_box_mm'][0], geo['table_box_mm'][2] - letters.bounds[2],
            letters.bounds[1] - geo['table_box_mm'][1], geo['table_box_mm'][3] - letters.bounds[3]), 3),
        'openings_area_mm2': round(letters.area, 3), 'narrowest_opening_mm': round(narrowest_opening, 3),
        'counters': counters, 'counters_hold': all(c['width_mm'] >= COUNTER_MIN_MM for c in counters),
        'foil_lines_inside_letters_mm2': round(unary_union(lines).intersection(letters).area, 6),
        'opening_tip_fillets_mm2': round(tip_fillets, 4),
        'body_ink': BODY_HEX,
    }
    return {
        'kind': KIND,
        'marks': marks,
        'regions': {'paint': [_ring(p) for p in _holefree(paint, overlap_mm=0.0)],
                    'relief': relief_rings,
                    'deboss': deboss_rings,
                    'footprint': [_ring(bar)],
                    'openings': [_ring(p) for p in _holefree(openings, overlap_mm=0.0)],
                    'body': [_ring(p) for p in _holefree(body, overlap_mm=0.0)]},
        'params': {'centre_mm': [float(centre_mm[0]), float(centre_mm[1])], 'length_mm': length_mm,
                   'height_mm': height_mm, 'end_facets': dict(end_facets), 'line_mm': line_mm, 'pitch_mm': pitch_mm,
                   'rim_mm': rim_mm, 'cutouts_rings': len(cutouts_mm), 'cutouts_sha256': rings_sha256(cutouts_mm),
                   'emboss': emboss},
        'measures': measures,
    }


# --- through the engine ----------------------------------------------------------------------------------------------

def _segments(rings) -> list:
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    segs = []
    for ring in rings:
        segs.append(MoveTo(x=ring[0][0], y=ring[0][1]))
        segs.extend(LineTo(x=x, y=y) for x, y in ring[1:])
        segs.append(ClosePath())
    return segs


def united_rings(rings) -> list:
    """Rings of one ink (hole-free, one orientation) united: each piece's outside anticlockwise on the page and its
    holes clockwise, so the set fills at nonzero winding exactly as the union."""
    shape = _polys_of(unary_union([Polygon(r).buffer(0) for r in rings]))
    out = []
    for p in _pieces(shape):
        outside = _ring(p)
        out.append(outside)
        for h in p.interiors:
            ring = [(round(float(x), 4), round(float(y), 4)) for x, y in Polygon(h).exterior.coords][:-1]
            if signed_area(ring) * signed_area(outside) > 0:
                ring.reverse()
            out.append(ring)
    return out


def document(*, result, ground_hex, title):
    """The generator's marks as an engine Document on the 190 x 120 lid: the relief first (EMBOSS and DEBOSS, no ink:
    pdf_ai depicts a relief on page 1 by stroking its outline, and drawn first that stroke lies under everything), a
    plain ground of ``ground_hex`` (standing in for the painted hero), the bar's body ink, the gold foil (FOIL_GOLD)
    on top. One ink's marks are united again and drawn as one compound path with its true holes, at nonzero."""
    from apps.ire.graph import Color, Document, Finish, Group, Path as VPath, SolidFill
    gold = Color.from_hex(GOLD_HEX)
    by_ink = {}
    for m in result['marks']:
        by_ink.setdefault((m['ink'], tuple(m['finishes'])), []).append(m['points'])
    # one ink's pieces united again and drawn with their true holes (a relief's page-1 depiction strokes each path's
    # outline, so the cuts that made the pieces hole-free must not reach the page)
    by_ink = {k: united_rings(v) for k, v in by_ink.items()}
    lid = [[(0.0, 0.0), (LID_W_MM, 0.0), (LID_W_MM, LID_H_MM), (0.0, LID_H_MM)]]
    ground = VPath(name='ground', segments=_segments(lid), fill=SolidFill(color=Color.from_hex(ground_hex)))
    children = []
    # the relief first (its page-1 depiction — pdf_ai strokes a relief's outline, lit and shadowed — then lies under
    # the ground and the body ink), then the ground, the body ink, the foil on top
    order = sorted(by_ink, key=lambda k: (k[0] != BLIND, k[0] == GOLD))
    for ink, finishes in order:
        rings = by_ink[(ink, finishes)]
        if ink == GOLD:
            children.append(VPath(name='c1-foil-gold', segments=_segments(rings), fill=SolidFill(color=gold),
                                  fill_rule='nonzero',
                                  finishes=[Finish(kind='foil', plate='FOIL_GOLD', appearance=gold)]))
        elif ink == BLIND:
            kinds = [f for f in finishes if f in ('emboss', 'deboss')]
            children.append(VPath(name='c1-relief-' + '-'.join(kinds), segments=_segments(rings), fill=None,
                                  fill_rule='nonzero', finishes=[Finish(kind=k, plate=k.upper()) for k in kinds]))
        elif ink.startswith('ink:'):
            children.append(VPath(name='c1-body-ink', segments=_segments(rings),
                                  fill=SolidFill(color=Color.from_hex(ink[len('ink:'):])), fill_rule='nonzero'))
        else:
            raise ValueError('an ink role this document cannot draw: %r' % ink)
    relief = [c for c in children if c.name.startswith('c1-relief')]
    children = relief + [ground] + [c for c in children if not c.name.startswith('c1-relief')]
    root = Group(name='C1_SIGNED_BAGUETTE', role='artwork', children=children)
    return Document(page_w=LID_W_MM, page_h=LID_H_MM, title=title, root=root)
