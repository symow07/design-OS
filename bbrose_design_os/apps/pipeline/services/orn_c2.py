"""Day 9, direction C-2 ("Taʿshīq"): the dovetail seam drawn by our engine as vectors (D-D9-3/4/5).

WHAT IT DRAWS. Two lacquer pages locked by a through-dovetail, the carpenter's joint the Levant calls taʿshīq (the root
of ʿishq, love). The seam is a vertical band from ``seam_x0_mm`` to ``seam_x1_mm``, the full height of the lid. The LEFT
page's ``tails`` reach right across the band; the RIGHT page's pins reach left between them. Every tail is a true
dovetail: a trapezoid whose neck lies on the left edge of the band and which flares toward its end on the right edge,
each slanted side running ``slope`` across for 1 up (``slope`` 7.0 is the classic 1:7; 6 to 8 is the joiner's range).
The joint opens and closes with a half-pin at the lid's top and bottom edges, so the tails sit at an even pitch
(lid height / tails) and the joint is symmetric about the lid's middle. Each pin's narrow end (on the band's right edge)
is PIN_NECK_SHARE of the pitch: the fine pins of hand-cut work, never square fingers, never crenellation.

THE JOINT LINE. The joint's shoulder line (the pins' wide ends, the tails' necks) lies ``outline_mm`` right of
``seam_x0_mm``, so everything drawn stays inside the seam zone. The outline, ``outline_mm`` wide, lies INSIDE the left
board along the whole joint line: the pin ends on the shoulder line, each tail's two slanted sides and its end on
``seam_x1_mm``. It is open at every tail's neck, so each tail grows out of its own page as a real tail does; and it
breaks METAL_BREAK_MM wide at each pin's middle, where one tail's metal hands over to the next (two foil passes never
touch, whatever their register). Corners are mitred, never rounded.

EACH TAIL is foil, alternating gold and rose gold from the top (TAIL_INKS): its share of the joint line, and
engine-turning across the tail: straight bars ``line_mm`` wide at ``pitch_mm`` pitch, square to the tail's length
(vertical on the lid), each bar a filled rectangle with square ends stopping ``inset_mm`` short of the outline's inner
edge (and starting ``inset_mm`` right of the shoulder line at the neck). The bars stand at the same x in every tail
(one phase for the seam), centred so the margin at the neck equals the margin at the end. Between the bars the left
page's own lacquer shows (the tail IS the left board). Each slanted side meets the bars at about 82 degrees (1:7).

THE RELIEF (``emboss``): the whole band, tails and pins, one raised piece (the seam "slightly raised").

OUTPUT (the Day 9 generators' shared form): ``{'kind', 'marks', 'regions', 'params', 'measures'}``; millimetres on the
190 x 120 mm lid, y down. Every region polygon is ONE hole-free ring (a list of points); a region with holes is given
as hole-free pieces (cut through each hole by a vertical line), whose union is the region. Regions:
- ``left_page``: the left lacquer's polygon, the lid left of the band PLUS the tails, its boundary the dovetail line
  exactly (for the plate's guide: the left lacquer is painted there, the tails included, under their foil);
- ``right_page``: the rest of the lid, the pins included, its boundary the same dovetail line;
- ``paint``: the lid minus the seam's foil (the outlines and every bar) — where the image model may paint;
- ``relief``: the emboss band (one piece; empty when ``emboss`` is False);
- ``footprint``: the band, which the type keeps clear of;
- ``tails`` and ``pins``: each dovetail's own polygon (top to bottom), for the build's checks.

$0: geometry only; nothing here calls a provider.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, MultiLineString, Polygon, box
from shapely.ops import split, unary_union

KIND = 'c2_tashiq'
LID_W_MM, LID_H_MM = 190.0, 120.0
LID_AREA_MM2 = LID_W_MM * LID_H_MM

GOLD = 'gold_foil'
ROSE_GOLD = 'rose_gold_foil'
BLIND = 'blind'
#: the tails' metals, alternating from the top
TAIL_INKS = (GOLD, ROSE_GOLD)
#: a pin's narrow end (on the band's right edge) as a share of the tails' pitch: 3.6 mm at six tails on 120 mm
PIN_NECK_SHARE = 0.18
#: the press's foil limits (D-D9-3)
FOIL_LINE_MIN_MM = 0.1
FOIL_GAP_MIN_MM = 0.2
#: the joiner's slope range (1:6 to 1:8 is the classic; outside 1:5 to 1:9 a dovetail reads as a wedge or a finger)
SLOPE_MIN, SLOPE_MAX = 5.0, 9.0
#: the joint line breaks this wide at each pin's middle, where the gold hands over to the rose gold (two foil passes:
#: the break keeps them from touching under the passes' register)
METAL_BREAK_MM = 0.5
#: the shortest bar worth stamping (a bar shorter than this is a dot, not engine-turning)
BAR_MIN_MM = 1.0
#: mitre joins for every offset (shapely's join_style 2) and its limit
MITRE = 2
MITRE_LIMIT = 10.0
#: ring pieces of less area than this are dust from boolean operations, not drawing
DUST_MM2 = 1e-6
#: a vertical cut line runs this far past the lid on both sides
CUT_OVERRUN_MM = 1.0
#: comparisons of computed lengths against stated ones
EPS_MM = 1e-9


def _mark(points, *, width_mm, ink, fill, closed, finishes) -> dict:
    return {'points': [(round(float(x), 6), round(float(y), 6)) for x, y in points], 'closed': closed,
            'width': width_mm, 'ink': ink, 'fill': fill, 'finishes': list(finishes)}


def _ring(poly) -> list:
    """A hole-free polygon's exterior as a point list, without the repeated closing point."""
    return [(round(float(x), 6), round(float(y), 6)) for x, y in list(poly.exterior.coords)[:-1]]


def _polys(geom) -> list:
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return [geom]
    return [g for part in geom.geoms for g in _polys(part)]


def _holefree(geom) -> list:
    """``geom`` as hole-free polygons whose union is ``geom``: every polygon with holes is split by a vertical line
    through each hole's centre (repeated until none is left)."""
    out, todo = [], [p for p in _polys(geom) if p.area > DUST_MM2]
    while todo:
        poly = todo.pop()
        if not poly.interiors:
            out.append(poly)
            continue
        _x0, y0, _x1, y1 = poly.bounds
        xs = sorted({round(Polygon(hole).centroid.x, 9) for hole in poly.interiors})
        cutter = MultiLineString([[(x, y0 - CUT_OVERRUN_MM), (x, y1 + CUT_OVERRUN_MM)] for x in xs])
        todo.extend(p for p in _polys(split(poly, cutter)) if p.area > DUST_MM2)
    return sorted(out, key=lambda p: (round(p.bounds[0], 6), round(p.bounds[1], 6)))


def _y_span(poly, x) -> tuple:
    """The (top, bottom) of a convex polygon's section at ``x``."""
    _a, top, _b, bottom = poly.intersection(LineString([(x, -CUT_OVERRUN_MM), (x, LID_H_MM + CUT_OVERRUN_MM)])).bounds
    return top, bottom


def _check(*, seam_x0_mm, seam_x1_mm, tails, slope, line_mm, pitch_mm, outline_mm, inset_mm, emboss) -> None:
    if not 0.0 <= seam_x0_mm < seam_x1_mm <= LID_W_MM:
        raise ValueError('the seam runs within the lid, left to right: got x %r to %r mm' % (seam_x0_mm, seam_x1_mm))
    if not isinstance(tails, int) or isinstance(tails, bool) or tails < 2:
        raise ValueError('a dovetail seam has at least two tails; got %r' % (tails,))
    if not SLOPE_MIN <= slope <= SLOPE_MAX:
        raise ValueError('a dovetail slope is 1:%g to 1:%g; got 1:%r' % (SLOPE_MIN, SLOPE_MAX, slope))
    if line_mm < FOIL_LINE_MIN_MM - EPS_MM or outline_mm < FOIL_LINE_MIN_MM - EPS_MM:
        raise ValueError('foil lines are at least %g mm: line %r, outline %r' % (FOIL_LINE_MIN_MM, line_mm, outline_mm))
    if pitch_mm - line_mm < FOIL_GAP_MIN_MM - EPS_MM or inset_mm < FOIL_GAP_MIN_MM - EPS_MM:
        raise ValueError('foil gaps are at least %g mm: between bars %r, short of the outline %r' % (
            FOIL_GAP_MIN_MM, pitch_mm - line_mm, inset_mm))
    if not isinstance(emboss, bool):
        raise ValueError('emboss is True or False; got %r' % (emboss,))


def tashiq(*, seam_x0_mm, seam_x1_mm, tails, slope, line_mm, pitch_mm, outline_mm, inset_mm, emboss) -> dict:
    """The C-2 dovetail seam. See the module's docstring for every input's meaning and every region's."""
    params = {'seam_x0_mm': seam_x0_mm, 'seam_x1_mm': seam_x1_mm, 'tails': tails, 'slope': slope, 'line_mm': line_mm,
              'pitch_mm': pitch_mm, 'outline_mm': outline_mm, 'inset_mm': inset_mm, 'emboss': emboss}
    _check(**params)
    shoulder_x_mm = seam_x0_mm + outline_mm            # the joint's shoulder line: the pins' wide ends, the tails' necks
    length_mm = seam_x1_mm - shoulder_x_mm
    flare_mm = length_mm / slope                       # each slanted side's rise over the tail's length
    tail_pitch_mm = LID_H_MM / tails
    pin_neck_mm = PIN_NECK_SHARE * tail_pitch_mm       # a pin's narrow end, on the band's right edge
    tail_end_mm = tail_pitch_mm - pin_neck_mm          # a tail's wide end, on the band's right edge
    tail_neck_mm = tail_end_mm - 2.0 * flare_mm        # a tail's neck, on the shoulder line
    keep_mm = outline_mm + inset_mm                    # the bars stop this far inside the joint line
    if tail_neck_mm < 2.0 * keep_mm + BAR_MIN_MM:
        raise ValueError('at 1:%g over %.2f mm a tail\'s neck is %.2f mm: too narrow for its outline and bars' % (
            slope, length_mm, tail_neck_mm))

    band = box(seam_x0_mm, 0.0, seam_x1_mm, LID_H_MM)
    lid = box(0.0, 0.0, LID_W_MM, LID_H_MM)
    tail_polys = []
    for i in range(tails):
        yc = (i + 0.5) * tail_pitch_mm
        tail_polys.append(Polygon([(shoulder_x_mm, yc - tail_neck_mm / 2.0), (seam_x1_mm, yc - tail_end_mm / 2.0),
                                   (seam_x1_mm, yc + tail_end_mm / 2.0), (shoulder_x_mm, yc + tail_neck_mm / 2.0)]))
    # the left board: its page and its tails, run past the lid's top and bottom so no line is drawn along them
    board = unary_union([box(-CUT_OVERRUN_MM - LID_W_MM, -CUT_OVERRUN_MM, shoulder_x_mm,
                             LID_H_MM + CUT_OVERRUN_MM)] + tail_polys)
    # the joint line, a meander: the outline lies inside the left board along the whole joint (pin ends, slants,
    # tail ends), open at the necks so each tail grows from its own page; broken at each pin's middle where one
    # metal hands over to the other
    eroded = board.buffer(-outline_mm, join_style=MITRE, mitre_limit=MITRE_LIMIT)
    meander = board.difference(eroded).intersection(box(seam_x0_mm, 0.0, seam_x1_mm, LID_H_MM))
    breaks = unary_union([box(seam_x0_mm - CUT_OVERRUN_MM, k * tail_pitch_mm - METAL_BREAK_MM / 2.0,
                              shoulder_x_mm + CUT_OVERRUN_MM, k * tail_pitch_mm + METAL_BREAK_MM / 2.0)
                          for k in range(1, tails)])
    lines = _polys(meander.difference(breaks))
    inner_all = board.buffer(-keep_mm, join_style=MITRE, mitre_limit=MITRE_LIMIT)

    # the bars' one phase: centred between the shoulder line (+ inset) and the tail end's outline (+ inset)
    inner_x0, inner_x1 = shoulder_x_mm + inset_mm, seam_x1_mm - keep_mm
    half = line_mm / 2.0
    span_mm = (inner_x1 - half) - (inner_x0 + half)
    n_bars = int(math.floor(span_mm / pitch_mm + EPS_MM)) + 1
    first_x = inner_x0 + half + (span_mm - (n_bars - 1) * pitch_mm) / 2.0
    bar_xs = [first_x + k * pitch_mm for k in range(n_bars)]

    marks, foil_parts, bar_lengths, end_gaps = [], [], [], []
    if emboss:
        marks.append(_mark(_ring(band), width_mm=0.0, ink=BLIND, fill=BLIND, closed=True, finishes=('emboss',)))
    for i, tail in enumerate(tail_polys):
        ink = TAIL_INKS[i % len(TAIL_INKS)]
        y_lo, y_hi = i * tail_pitch_mm, (i + 1) * tail_pitch_mm
        mine = [p for p in lines if y_lo <= p.centroid.y < y_hi]
        for piece in mine:
            for ring_poly in _holefree(piece):
                marks.append(_mark(_ring(ring_poly), width_mm=0.0, ink=ink, fill=ink, closed=True,
                                   finishes=('foil',)))
            foil_parts.append(piece)
        outline_here = unary_union(mine)
        inner = inner_all.intersection(box(inner_x0, y_lo, seam_x1_mm, y_hi))
        for x in bar_xs:
            top_a, bottom_a = _y_span(inner, x - half)
            top_b, bottom_b = _y_span(inner, x + half)
            top, bottom = max(top_a, top_b), min(bottom_a, bottom_b)   # square ends, both corners inside
            if bottom - top < BAR_MIN_MM:
                continue
            bar = [(x - half, top), (x + half, top), (x + half, bottom), (x - half, bottom)]
            marks.append(_mark(bar, width_mm=0.0, ink=ink, fill=ink, closed=True, finishes=('foil',)))
            foil_parts.append(Polygon(bar))
            bar_lengths.append(bottom - top)
            end_gaps.append(Polygon(bar).distance(outline_here))      # the bar's nearest approach to the joint line

    foil = unary_union(foil_parts)
    left = board.intersection(lid)
    right = lid.difference(left)
    pin_polys = _polys(box(shoulder_x_mm, 0.0, seam_x1_mm, LID_H_MM).difference(unary_union(tail_polys)))
    pin_polys.sort(key=lambda p: p.bounds[1])
    paint = lid.difference(foil)

    regions = {'left_page': [_ring(p) for p in _holefree(left)],
               'right_page': [_ring(p) for p in _holefree(right)],
               'paint': [_ring(p) for p in _holefree(paint)],
               'relief': [_ring(band)] if emboss else [],
               'footprint': [_ring(band)],
               'tails': [_ring(p) for p in tail_polys],
               'pins': [_ring(p) for p in pin_polys]}

    relief_mm2 = sum(Polygon(ring).area for ring in regions['relief'])
    gold_mm2 = sum(p.area for i, t in enumerate(tail_polys) for p in _polys(foil.intersection(t))
                   if TAIL_INKS[i % len(TAIL_INKS)] == GOLD)
    measures = {
        'method': 'shapely geometry of the marks themselves (the engine render is measured apart by finish_proof)',
        'joint': {'shoulder_x_mm': round(shoulder_x_mm, 4), 'length_mm': round(length_mm, 4), 'slope': '1:%g' % slope, 'flare_per_side_mm': round(flare_mm, 4),
                  'side_angle_deg': round(math.degrees(math.atan(1.0 / slope)), 3),
                  'tail_pitch_mm': round(tail_pitch_mm, 4), 'tail_neck_mm': round(tail_neck_mm, 4),
                  'tail_end_mm': round(tail_end_mm, 4), 'pin_neck_mm': round(pin_neck_mm, 4),
                  'pin_wide_mm': round(pin_neck_mm + 2.0 * flare_mm, 4), 'half_pins': 2, 'metal_break_mm': METAL_BREAK_MM,
                  'tail_inks': [TAIL_INKS[i % len(TAIL_INKS)] for i in range(tails)]},
        'engine_turning': {'bars_per_tail': n_bars, 'bars': len(bar_lengths), 'angle_deg': 90,
                           'first_bar_x_mm': round(first_x, 4), 'bar_min_mm': round(min(bar_lengths), 4),
                           'bar_max_mm': round(max(bar_lengths), 4)},
        'lines_per_cm_densest': {'value': round(10.0 / pitch_mm, 3), 'angle_deg': 0,
                                 'where': 'across the bars (a horizontal transect) in every tail, densest at a '
                                          'tail\'s wide end; window x %.1f to %.1f mm' % (seam_x1_mm - 10.0,
                                                                                          seam_x1_mm)},
        'foil_limits': {'min_line_mm': round(min(line_mm, outline_mm), 4),
                        'min_gap_mm': round(min(pitch_mm - line_mm, min(end_gaps)), 4),
                        'gap_bar_to_outline_min_mm': round(min(end_gaps), 4),
                        'gap_between_metals_mm': METAL_BREAK_MM,
                        'holds': bool(min(line_mm, outline_mm) >= FOIL_LINE_MIN_MM - EPS_MM
                                      and min(pitch_mm - line_mm, min(end_gaps))
                                      >= FOIL_GAP_MIN_MM - EPS_MM),
                        'limits': {'line_mm': FOIL_LINE_MIN_MM, 'gap_mm': FOIL_GAP_MIN_MM}},
        'foil_ink_mm2': round(foil.area, 3), 'foil_ink_pct': round(foil.area / LID_AREA_MM2 * 100.0, 4),
        'foil_gold_mm2': round(gold_mm2, 3), 'foil_rose_gold_mm2': round(foil.area - gold_mm2, 3),
        'relief_mm2': round(relief_mm2, 3),
        'relief_pct': round(relief_mm2 / LID_AREA_MM2 * 100.0, 4),
        'band_mm2': round(band.area, 3),
        'region_areas_mm2': {'left_page': round(left.area, 3), 'right_page': round(right.area, 3),
                             'paint': round(paint.area, 3)},
    }
    return {'kind': KIND, 'marks': marks, 'regions': regions, 'params': params, 'measures': measures}


# --- the engine's own document ------------------------------------------------------------------------------------------

def _segments(points, closed):
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    segs = [MoveTo(x=points[0][0], y=points[0][1])] + [LineTo(x=x, y=y) for x, y in points[1:]]
    return segs + [ClosePath()] if closed else segs


def document(result: dict, *, left_page_hex: str, right_page_hex: str, gold_hex: str, rose_gold_hex: str):
    """An ``apps/ire/graph.Document`` of ``result``: the two pages flat in their colours (from ``left_page`` and
    ``right_page``), the foil on its two plates (FOIL_GOLD, FOIL_ROSE_GOLD), the band on the EMBOSS plate."""
    from apps.ire.graph import Color, Document, Finish, Group, Path, SolidFill, Stroke
    metals = {GOLD: ('FOIL_GOLD', Color.from_hex(gold_hex)), ROSE_GOLD: ('FOIL_ROSE_GOLD', Color.from_hex(rose_gold_hex))}
    pages = []
    for name, hexv in (('left_page', left_page_hex), ('right_page', right_page_hex)):
        for k, ring in enumerate(result['regions'][name]):
            pages.append(Path(name='%s-%d' % (name, k), segments=_segments(ring, True),
                              fill=SolidFill(color=Color.from_hex(hexv))))
    relief, foil = [], []
    for k, m in enumerate(result['marks']):
        if 'emboss' in m['finishes'] or 'deboss' in m['finishes']:
            kind = 'emboss' if 'emboss' in m['finishes'] else 'deboss'
            relief.append(Path(name='seam-%s-%d' % (kind, k), segments=_segments(m['points'], m['closed']),
                               finishes=[Finish(kind=kind, plate=kind.upper())]))
            continue
        plate, colour = metals[m['ink']]
        finish = Finish(kind='foil', plate=plate, appearance=colour)
        if m['width'] > 0.0:
            foil.append(Path(name='tail-outline-%d' % k, segments=_segments(m['points'], m['closed']),
                             stroke=Stroke(color=colour, width_mm=m['width']), finishes=[finish]))
        else:
            foil.append(Path(name='tail-bar-%d' % k, segments=_segments(m['points'], m['closed']),
                             fill=SolidFill(color=colour), finishes=[finish]))
    root = Group(name='root', role='artwork', children=[
        Group(name='PAGES', role='background', children=pages),
        Group(name='SEAM RELIEF', role='decoration', children=relief),
        Group(name='SEAM FOIL', role='decoration', children=foil)])
    return Document(page_w=LID_W_MM, page_h=LID_H_MM, title='C-2 Tashiq seam', root=root)
