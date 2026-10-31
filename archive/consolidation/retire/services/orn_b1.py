"""Day 9, direction B-1 ("Ẓilāl"): the Arabic lockup drawn by our engine as vectors (D-D9-3/4/5).

WHAT IT DRAWS. ظلال — "shadows" — as hero lettering, and باليت above its right end and العيون below its left end,
so the brief's descriptor "باليت ظلال العيون" reads word for word from the top right to the lower left. Every letter
is the licensed face's OWN outline: El Messiri PF Bold (``apps/ire/arabic_display.ensure_chosen``: the OFL face made
emitter-capable today), shaped by HarfBuzz with the face's own GSUB/GPOS (``arabic_display.shape``), each glyph's
quadratic contours read with fontTools and flattened at FLATTEN_TOL_MM — never a raster, never traced.

THE LETTERING OPERATIONS, each geometry on the outlines and each switchable; none changes a letter's identity:
- ``level_uprights``: the uprights of ظلال brought to ONE height, the isolated alif's (so ``alif_mm`` stays exactly
  true). Measured in this face: the ظ's stem, the lam of لا and the last lam already stand at the alif's height (660
  units); the alef of لا stands at 519, so it alone moves — its own head lifted 141 units and its stem's own section
  (upright to 0.0 units at the cut) carried across the lift, as the canonical lam-alef rises to the lam's height. The
  gap after it (alef never joins on) still reads it as an alef. A stroke counts as an upright when, cut at UPRIGHT_PROBE
  of the alif, it rises past UPRIGHT_SHARE of it (the bowls of ظ top out at 480, below).
- ``lozenge_dot``: the ownable terminal (J1's lift), polished metal at every top of the word. The ظ's round dot becomes
  the rose-cut LOZENGE — the house rose cut's facet is the equilateral triangle, two of them base to base make a
  lozenge with 60 degrees at its tips — at the dot's own area and centre, laid level, in SOLID rose-gold foil; and the
  four uprights' heads (the face's own heads, outline untouched) are CROWNED in the same solid polished foil, cut from
  the hatched stem along one of the hatch's own lines (the one nearest CAP_SHARE of the alif below the top: level with
  a level hatch, the qalam's bevel with a 45-degree one), so no wedge or stub is left between crown and hatch. The
  small words' dots are left round: their paired dots, as lozenges of equal area, would come closer than a foil gap.
- ``join_mm``: the join between ظ and لا drawn out by that many millimetres (a kashida: the baseline stroke's own
  section, level for 30 units each side of the cut, carried across); 0 keeps the face's join.

EACH HERO LETTER (D-D9-3, B-1's print plan): its body in ``fill_hex`` ink; open rose-gold FOIL hatching at
``hatch_angle_deg`` (0 level, 45), lines ``hatch_line_mm`` at ``hatch_pitch_mm``, clipped inside a rose-gold FOIL
contour ``contour_mm`` wide lying just inside the outline; a ``keyline_hex`` keyline ``keyline_mm`` wide outside, which
the foil overlaps by KEYLINE_FOIL_OVERLAP_MM (register trap: the keyline band runs from 0.4 mm inside the outline to
0.6 mm outside); and an EMBOSS piece inset ``emboss_inset_mm``. A LEVEL hatch is locked to the word's level stroke (the
baseline stroke at the join of ظ and لا): the most lines that keep a foil gap to the contour at both edges, centred, so
the stroke's top and bottom read alike; any other angle takes the phase the limits disturb least among HATCH_PHASES.
Then every foil part finer than a foil line is opened away and every gap finer than a foil gap closed (a fillet where
a line meets the contour, as an engraver finishes it). The small words are solid rose-gold foil.

OUTPUT (the Day 9 generators' shared form): ``{'kind', 'marks', 'regions', 'params', 'measures'}``; millimetres on the
190 x 120 mm lid, y down. Every region polygon is ONE hole-free ring (a list of points); a region with a hole (the
paint area round the lockup, a counter) is given as hole-free pieces cut through each hole, whose union is the region.
"""
from __future__ import annotations

import math
import unicodedata

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.ops import unary_union

KIND = 'b1_zilal'
LID_W_MM, LID_H_MM = 190.0, 120.0
LID_AREA_MM2 = LID_W_MM * LID_H_MM

HERO = 'ظلال'
ABOVE = 'باليت'
BELOW = 'العيون'
DESCRIPTOR = 'باليت ظلال العيون'          # arabic_display.DESCRIPTOR, the brief's copy verbatim
ALIF_GLYPH = 'uni0627'                    # the isolated alif: what ``alif_mm`` measures

#: the build's values (B-1's spec, its chosen sketch B-1.3 and J1's lift): alif 22 mm, the hatch level, the join drawn
#: out 6 mm; 26 mm and 45 degrees are the spec's alternatives and keep working. The zone is B-1's arabic_hero zone.
BUILD_PARAMS = {'zone_mm': (0.38 * 190.0, 0.13 * 120.0, 0.95 * 190.0, 0.6 * 120.0), 'alif_mm': 22.0,
                'small_alif_mm': 8.0, 'hatch_angle_deg': 0.0, 'hatch_line_mm': 0.30, 'hatch_pitch_mm': 0.62,
                'contour_mm': 0.4, 'keyline_mm': 1.0, 'keyline_hex': '#22205A', 'fill_hex': '#22205A',
                'emboss_inset_mm': 0.3, 'level_uprights': True, 'lozenge_dot': True, 'join_mm': 6.0}
#: the spec's colours for the render (ground and rose-gold foil)
GROUND_HEX = '#22205A'
ROSE_GOLD_HEX = '#C99A84'

ROSE_GOLD = 'rose_gold_foil'
BLIND = 'blind'

#: curves flattened to within this of the face's own quadratic (lettering.FLATTEN_TOL_MM)
FLATTEN_TOL_MM = 0.005
#: the press's foil limits (D-D9-3) and the margin our own geometry keeps inside them
FOIL_LINE_MIN_MM = 0.1
FOIL_GAP_MIN_MM = 0.2
MORPH_MARGIN_MM = 0.025
#: the foil overlaps the keyline by this (B-1's print plan: "the foil overlapping it by 0.4 mm to trap register")
KEYLINE_FOIL_OVERLAP_MM = 0.4
#: 'paint' leaves the keyline footprint grown by this; 'calm' is the footprint grown by that
PAINT_GROW_MM = 1.0
CALM_GROW_MM = 4.0
#: the clear space between a small word's foil and the hero's keyline
SMALL_CLEAR_MM = 1.8
#: the hatch's phase is chosen among this many offsets across one pitch
HATCH_PHASES = 24
#: the hatch runs this far under the contour, so the two foils overlap and no seam shows
HATCH_TUCK_MM = 0.1
#: the uprights: the part above this share of the alif's height is the upright's top
SHOULDER_SHARE = 0.78
#: a crown's chevron apex lies this share of the alif below the upright's top
CAP_SHARE = 0.2
#: the rose cut's facet is the equilateral triangle; the lozenge is two of them base to base
FACET_APEX_DEG = 60.0
#: buffers drawn with this many segments a quarter circle
QUAD_SEGS = 16
#: ring pieces of less area than this are dust from boolean operations, not drawing
DUST_MM2 = 1e-4


# --- the face's own outlines -------------------------------------------------------------------------------------------

def face() -> dict:
    """The chosen display face's provenance: ``{'path', 'sha256', 'postscript', 'licence', ...}``."""
    from apps.ire import arabic_display
    return arabic_display.ensure_chosen()


class _FlatPen:
    """A fontTools pen collecting a glyph's contours as flattened rings in font units (y up), components decomposed."""

    def __new__(cls, glyph_set, tol_units):
        from fontTools.pens.basePen import BasePen

        class Pen(BasePen):
            def __init__(self):
                super().__init__(glyph_set)
                self.rings, self.ring = [], []

            def _moveTo(self, p):
                self.ring = [p]

            def _lineTo(self, p):
                self.ring.append(p)

            def _qCurveToOne(self, p1, p2):
                p0 = self.ring[-1]
                dx, dy = p0[0] - 2 * p1[0] + p2[0], p0[1] - 2 * p1[1] + p2[1]
                n = max(2, int(math.ceil(math.sqrt(math.hypot(dx, dy) / (8.0 * tol_units)))))
                for i in range(1, n + 1):
                    t = i / n
                    a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
                    self.ring.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))

            def _curveToOne(self, p1, p2, p3):
                p0 = self.ring[-1]
                d = max(math.hypot(p0[0] - 2 * p1[0] + p2[0], p0[1] - 2 * p1[1] + p2[1]),
                        math.hypot(p1[0] - 2 * p2[0] + p3[0], p1[1] - 2 * p2[1] + p3[1]))
                n = max(2, int(math.ceil(math.sqrt(0.75 * d / tol_units))))
                for i in range(1, n + 1):
                    t = i / n
                    a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
                    self.ring.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0],
                                      a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))

            def _closePath(self):
                if len(self.ring) > 2:
                    self.rings.append(self.ring)
                self.ring = []

            _endPath = _closePath

        return Pen()


def _signed_area(ring) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def glyph_shape(glyph_set, name: str, *, tol_units: float):
    """The glyph's own outline as one shapely geometry in font units (y up), filled by the NONZERO rule: TrueType
    draws an outside clockwise and a counter anticlockwise, so the outsides unite and the counters are cut from them."""
    pen = _FlatPen(glyph_set, tol_units)
    glyph_set[name].draw(pen)
    outs, holes = [], []
    for ring in pen.rings:
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        (outs if _signed_area(ring) < 0 else holes).append(poly)
    shape = unary_union(outs)
    if holes:
        shape = shape.difference(unary_union(holes))
    return shape


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


def _filled(geom):
    """``geom`` with every hole filled (a counter kept clear as a whole)."""
    return unary_union([Polygon(p.exterior) for p in _pieces(geom)])


def _holefree(geom, *, overlap_mm: float) -> list:
    """``geom`` as hole-free polygons whose union is ``geom``: a polygon with a hole is cut by a vertical line through
    the hole's centre, each side kept to ``overlap_mm`` past the cut (0 for an exact partition; a hair for two pieces of
    one ink, so no anti-aliased seam shows where they meet), and cut again until no piece holds a hole."""
    out, todo = [], list(_pieces(geom))
    while todo:
        poly = todo.pop()
        if not poly.interiors:
            out.append(poly)
            continue
        cx = Polygon(poly.interiors[0]).centroid.x
        x0, y0, x1, y1 = poly.bounds
        todo.extend(_pieces(poly.intersection(box(x0 - 1.0, y0 - 1.0, cx + overlap_mm, y1 + 1.0))))
        todo.extend(_pieces(poly.intersection(box(cx - overlap_mm, y0 - 1.0, x1 + 1.0, y1 + 1.0))))
    return out


def _ring(poly) -> list:
    return [(round(float(x), 4), round(float(y), 4)) for x, y in poly.exterior.coords]


def _boundary_rings(geom) -> list:
    """Every boundary ring (outsides and counters) of ``geom``, as point lists."""
    rings = []
    for p in _pieces(geom):
        rings.append([(round(float(x), 4), round(float(y), 4)) for x, y in p.exterior.coords])
        rings.extend([(round(float(x), 4), round(float(y), 4)) for x, y in h.coords] for h in p.interiors)
    return rings


def _mark(points, *, width_mm, ink, fill, closed, finishes) -> dict:
    return {'points': [(float(x), float(y)) for x, y in points], 'closed': closed, 'width': width_mm, 'ink': ink,
            'fill': fill, 'finishes': list(finishes)}


# --- setting a word --------------------------------------------------------------------------------------------------

def _glyph_set(face_path):
    from fontTools.ttLib import TTFont
    font = TTFont(str(face_path))
    return font, font.getGlyphSet()


def alif_units(glyph_set) -> float:
    """The isolated alif's height in font units (its top above the baseline): what ``alif_mm`` measures."""
    from fontTools.pens.boundsPen import BoundsPen
    pen = BoundsPen(glyph_set)
    glyph_set[ALIF_GLYPH].draw(pen)
    return float(pen.bounds[3])


def set_word(face_path, glyph_set, text: str, *, tol_units: float) -> list:
    """``text`` shaped by HarfBuzz with the face's own features (``arabic_display.shape``), each glyph's own outline
    placed where shaping puts it — font units, y up, visual order: ``[{'name', 'cluster', 'char', 'geom'}]``, where
    ``char`` is the glyph's character read back from its name (the face names each glyph by its cmap code point)."""
    from apps.ire import arabic_display
    out = []
    for g in arabic_display.shape(face_path, text):
        geom = affinity.translate(glyph_shape(glyph_set, g['name'], tol_units=tol_units), g['x'], g['y'])
        out.append({'name': g['name'], 'cluster': g['cluster'], 'char': glyph_char(g['name']), 'geom': geom})
    return out


def glyph_char(name: str) -> str:
    """The character a glyph stands for, read from its name ('uniFEC7' -> U+FEC7, 'space' -> ' ')."""
    if name == 'space':
        return ' '
    if name.startswith('uni') and len(name) == 7:
        return chr(int(name[3:], 16))
    raise ValueError('glyph %r is not named by its code point' % name)


def reextract(words: list) -> str:
    """The words' text read back from their shaped glyphs alone: each word's glyph names to characters (NFKC turns a
    presentation form and a lam-alef ligature back into its letters), in logical order by cluster; the words joined by
    a space in the order given (reading order)."""
    spelled = []
    for glyphs in words:
        ordered = sorted(glyphs, key=lambda g: g['cluster'])
        spelled.append(unicodedata.normalize('NFKC', ''.join(glyph_char(g['name']) for g in ordered)))
    return ' '.join(spelled)


# --- the lettering operations (font units, y up) -----------------------------------------------------------------------

def _line_parts(geom) -> list:
    """The line strings of a boolean's result (a LineString, a MultiLineString or a collection)."""
    if geom.is_empty:
        return []
    if hasattr(geom, 'geoms'):
        return [p for g in geom.geoms for p in _line_parts(g)]
    return [geom]


def _intervals_at_y(geom, y_units) -> list:
    """The runs of ``geom`` along the horizontal line at ``y_units``: ``[(x0, x1)]``, left to right."""
    x0, _, x1, _ = geom.bounds
    cut = geom.intersection(LineString([(x0 - 10.0, y_units), (x1 + 10.0, y_units)]))
    runs = []
    for part in _line_parts(cut):
        if part.geom_type == 'LineString' and part.length > 0:
            xs = [c[0] for c in part.coords]
            runs.append((min(xs), max(xs)))
    return sorted(runs)


def _intervals_at_x(geom, x_units) -> list:
    """The runs of ``geom`` along the vertical line at ``x_units``: ``[(y0, y1)]``, bottom to top."""
    _, y0, _, y1 = geom.bounds
    cut = geom.intersection(LineString([(x_units, y0 - 10.0), (x_units, y1 + 10.0)]))
    runs = []
    for part in _line_parts(cut):
        if part.geom_type == 'LineString' and part.length > 0:
            ys = [c[1] for c in part.coords]
            runs.append((min(ys), max(ys)))
    return sorted(runs)


#: an upright is a stroke that, cut at UPRIGHT_PROBE of the alif's height, rises above UPRIGHT_SHARE of it
UPRIGHT_PROBE = 0.45
UPRIGHT_SHARE = 0.76


def uprights(body, alif_u: float) -> list:
    """The uprights of a word's letter bodies (dots excluded): every run the body makes at UPRIGHT_PROBE of the alif's
    height whose part above that line rises past UPRIGHT_SHARE of it. ``[{'x0', 'x1', 'top', 'head'}]`` in font units,
    ``head`` the upright's own part above the probe line."""
    probe = UPRIGHT_PROBE * alif_u
    above = body.intersection(box(body.bounds[0] - 10.0, probe, body.bounds[2] + 10.0, body.bounds[3] + 10.0))
    found = []
    for x0, x1 in _intervals_at_y(body, probe):
        mid = 0.5 * (x0 + x1)
        heads = [p for p in _pieces(above) if p.intersects(LineString([(mid, probe - 1.0), (mid, probe + 1.0)]))]
        if not heads:
            continue
        head = heads[0]
        if head.bounds[3] >= UPRIGHT_SHARE * alif_u:
            found.append({'x0': x0, 'x1': x1, 'top': head.bounds[3], 'head': head})
    return found


def level(body, alif_u: float) -> tuple:
    """Every upright of ``body`` brought to the alif's height: the upright's own head (its part above the probe line)
    moved up or down by the difference and the stem's own section at the probe line carried across the move, so the
    head keeps the face's drawing and the stem its width. Returns ``(body, rows)`` — rows the heights before and after."""
    rows, probe = [], UPRIGHT_PROBE * alif_u
    for up in uprights(body, alif_u):
        lift = alif_u - up['top']
        row = {'x0_units': round(up['x0'], 1), 'x1_units': round(up['x1'], 1), 'top_units': round(up['top'], 1),
               'lift_units': round(lift, 1)}
        if abs(lift) > 0.5:
            # the stem's sides must be upright where it is carried: its run at the probe and a little above and below
            runs = [_intervals_at_y(body, probe + dy) for dy in (-0.05 * alif_u, 0.05 * alif_u)]
            near = [min(r, key=lambda iv: abs(0.5 * (iv[0] + iv[1]) - 0.5 * (up['x0'] + up['x1']))) for r in runs]
            drift = max(abs(n[0] - up['x0']) + abs(n[1] - up['x1']) for n in near)
            if drift > 1.0:
                raise ValueError('the upright at x %.0f-%.0f is not upright at its probe (sides drift %.1f units)'
                                 % (up['x0'], up['x1'], drift))
            rest = body.difference(up['head'].buffer(0.01))
            moved = affinity.translate(up['head'], 0.0, lift)
            if lift > 0:
                section = box(up['x0'], probe - 0.5, up['x1'], probe + lift + 0.5)
            else:
                section = box(up['x0'], probe - 0.5, up['x1'], probe + 0.5)
                rest = rest.difference(box(up['x0'] - 1.0, probe + lift, up['x1'] + 1.0, probe + 0.01))
            body = _polys_of(unary_union([rest, moved, section]))
            row['side_drift_units'] = round(drift, 2)
        row['top_after_units'] = round(alif_u if abs(lift) > 0.5 else up['top'], 1)
        rows.append(row)
    return body, rows


def lozenge(cx, cy, area, *, tip_deg: float) -> Polygon:
    """The rose-cut lozenge: two facets base to base, its long diagonal level, ``tip_deg`` at its two tips, ``area``."""
    half = math.radians(tip_deg) / 2.0
    # area = long x short / 2, short = long x tan(half)
    long_ = math.sqrt(2.0 * area / math.tan(half))
    short = long_ * math.tan(half)
    return Polygon([(cx - long_ / 2, cy), (cx, cy - short / 2), (cx + long_ / 2, cy), (cx, cy + short / 2)])


def draw_out(glyphs: list, at_index: int, extra_units: float) -> tuple:
    """The join on the right of glyph ``at_index`` (visual order) drawn out by ``extra_units``: every glyph left of the
    cut moved left, and the joining stroke's own section at the cut carried across the gap (a kashida). The cut is the
    boundary between the two glyphs' advances, where the face joins them on its baseline stroke."""
    right = glyphs[at_index + 1]
    cut_x = right['geom'].bounds[0]
    word = unary_union([g['geom'] for g in glyphs])
    runs = _intervals_at_x(word, cut_x + 0.5)
    if len(runs) != 1:
        raise ValueError('the join at x %.0f is not one stroke (%d runs)' % (cut_x, len(runs)))
    y0, y1 = runs[0]
    for dx in (-30.0, 30.0):                 # the stroke must run level through the cut to be carried
        probe = _intervals_at_x(word, cut_x + dx)
        if not probe or abs(probe[0][0] - y0) > 1.0 or abs(probe[0][1] - y1) > 1.0:
            raise ValueError('the join at x %.0f does not run level through its cut' % cut_x)
    out = []
    for i, g in enumerate(glyphs):
        moved = affinity.translate(g['geom'], -extra_units, 0.0) if i <= at_index else g['geom']
        out.append(dict(g, geom=moved))
    stroke = box(cut_x - extra_units - 1.0, y0, cut_x + 1.0, y1)
    out[at_index + 1] = dict(out[at_index + 1], geom=_polys_of(unary_union([out[at_index + 1]['geom'], stroke])))
    return out, {'cut_x_units': round(cut_x, 1), 'stroke_y_units': [round(y0, 1), round(y1, 1)],
                 'extra_units': round(extra_units, 1)}


# --- the hatch ----------------------------------------------------------------------------------------------------------

def _bands(bounds, *, angle_deg, pitch_mm, phase_mm, width_mm) -> list:
    """Bands ``width_mm`` wide on the lines of a hatch at ``angle_deg`` (0 level, rising to the right as it grows; y
    down), one every ``pitch_mm`` along the normal, offset ``phase_mm`` from the lid's origin, covering ``bounds``."""
    a = math.radians(angle_deg)
    u = (math.cos(a), -math.sin(a))
    n = (math.sin(a), math.cos(a))
    x0, y0, x1, y1 = bounds
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    ds = [x * n[0] + y * n[1] for x, y in corners]
    ts = [x * u[0] + y * u[1] for x, y in corners]
    t0, t1 = min(ts) - 1.0, max(ts) + 1.0
    k0 = int(math.floor((min(ds) - phase_mm) / pitch_mm)) - 1
    k1 = int(math.ceil((max(ds) - phase_mm) / pitch_mm)) + 1
    out = []
    for k in range(k0, k1 + 1):
        d = phase_mm + k * pitch_mm
        lo, hi = d - width_mm / 2.0, d + width_mm / 2.0
        out.append(Polygon([(lo * n[0] + t0 * u[0], lo * n[1] + t0 * u[1]), (lo * n[0] + t1 * u[0], lo * n[1] + t1 * u[1]),
                            (hi * n[0] + t1 * u[0], hi * n[1] + t1 * u[1]), (hi * n[0] + t0 * u[0], hi * n[1] + t0 * u[1])]))
    return out


def _clean_foil(foil):
    """The foil held to the press's limits by construction: every part finer than a foil line (with the margin) opened
    away, then every gap finer than a foil gap closed."""
    line_r = FOIL_LINE_MIN_MM / 2.0 + MORPH_MARGIN_MM
    gap_r = FOIL_GAP_MIN_MM / 2.0 + MORPH_MARGIN_MM
    return _closed(_opened(foil, line_r), gap_r)


def _locked_phase(band_mm, *, line_mm, pitch_mm, contour_mm) -> dict:
    """A level hatch's phase locked to the word's level stroke (``band_mm``: its top and bottom, y down): the most
    lines whose gaps to the contour at both edges hold the foil gap with the margin, centred in the stroke, so its top
    and bottom edges read alike and no line runs beside the contour closer than a gap."""
    top, bottom = band_mm
    inside = (bottom - top) - 2.0 * contour_mm
    least = FOIL_GAP_MIN_MM + MORPH_MARGIN_MM
    lines = int(math.floor((inside - 2.0 * least - line_mm) / pitch_mm)) + 1
    if lines < 1:
        raise ValueError('the level stroke (%.2f mm inside its contour) holds no hatch line' % inside)
    edge = 0.5 * (inside - ((lines - 1) * pitch_mm + line_mm))
    first = 0.5 * (top + bottom) - 0.5 * (lines - 1) * pitch_mm
    return {'phase_mm': first % pitch_mm, 'lines_in_stroke': lines, 'edge_gap_mm': round(edge, 4),
            'stroke_mm': round(bottom - top, 4)}


def _strip(bounds, *, angle_deg, lo_mm, hi_mm) -> Polygon:
    """The strip between two hatch lines' offsets ``lo_mm`` and ``hi_mm`` along the hatch's normal, covering ``bounds``."""
    a = math.radians(angle_deg)
    u, n = (math.cos(a), -math.sin(a)), (math.sin(a), math.cos(a))
    x0, y0, x1, y1 = bounds
    ts = [x * u[0] + y * u[1] for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    t0, t1 = min(ts) - 1.0, max(ts) + 1.0
    return Polygon([(lo_mm * n[0] + t0 * u[0], lo_mm * n[1] + t0 * u[1]), (lo_mm * n[0] + t1 * u[0], lo_mm * n[1] + t1 * u[1]),
                    (hi_mm * n[0] + t1 * u[0], hi_mm * n[1] + t1 * u[1]), (hi_mm * n[0] + t0 * u[0], hi_mm * n[1] + t0 * u[1])])


def crowns(heads, *, phase_mm, angle_deg, line_mm, pitch_mm, depth_mm) -> list:
    """The crowns: each upright's head cut off as solid polished foil along a hatch line's own lower edge — the one
    nearest ``depth_mm`` below the upright's top on its centre line — so the cut runs with the hatch (level, or the
    qalam's bevel at 45 degrees) and the next line below starts one full hatch gap away: no wedge, no stub."""
    a = math.radians(angle_deg)
    n = (math.sin(a), math.cos(a))
    out = []
    for head in heads:
        d0 = head['cx_mm'] * n[0] + (head['top_mm'] + depth_mm) * n[1]
        k = round((d0 - phase_mm) / pitch_mm)
        edge = phase_mm + k * pitch_mm + line_mm / 2.0
        top_side = _strip(head['geom'].bounds, angle_deg=angle_deg, lo_mm=edge - 1000.0, hi_mm=edge)
        out.append(_polys_of(head['geom'].intersection(top_side)))
    return out


def _hatch(letters, solid_of, *, angle_deg, line_mm, pitch_mm, contour_mm, level_band_mm) -> dict:
    """The open hatch inside ``letters`` (one geometry, mm): bands at the angle and pitch, run HATCH_TUCK_MM under the
    contour; the solid foil beside it from ``solid_of(phase)`` (the crowns are cut on the hatch's own lines). A level
    hatch is locked to the word's level stroke (``_locked_phase``); any other takes the phase the press's limits
    disturb least among HATCH_PHASES offsets. The foil is cleaned to the limits with the contour and the solid foil.
    Returns the hatch as pieces (each one band's own foil, its fillets with it, tucked under the solid), the solid, the
    phase and what cleaning moved."""
    ring = letters.difference(letters.buffer(-contour_mm, join_style='mitre'))
    clip = letters.buffer(-(contour_mm - HATCH_TUCK_MM), join_style='mitre')
    trials, locked = [], None
    phases = [pitch_mm * i / HATCH_PHASES for i in range(HATCH_PHASES)]
    if angle_deg % 180.0 == 0.0:
        locked = _locked_phase(level_band_mm, line_mm=line_mm, pitch_mm=pitch_mm, contour_mm=contour_mm)
        phases = [locked['phase_mm']]
    for phase in phases:
        bands = unary_union(_bands(letters.bounds, angle_deg=angle_deg, pitch_mm=pitch_mm, phase_mm=phase,
                                   width_mm=line_mm))
        solid = solid_of(phase)
        raw = unary_union([ring, bands.intersection(clip), solid])
        clean = _clean_foil(raw)
        trials.append((clean.symmetric_difference(raw).area, phase, raw, clean, solid))
    moved, phase, raw, clean, solid = min(trials, key=lambda t: (round(t[0], 6), t[1]))
    open_clip = clip.difference(solid.buffer(-HATCH_TUCK_MM / 2.0)) if not solid.is_empty else clip
    pieces = []
    for cell in _bands(letters.bounds, angle_deg=angle_deg, pitch_mm=pitch_mm, phase_mm=phase, width_mm=pitch_mm):
        part = clean.intersection(cell).intersection(open_clip)
        pieces.extend(_holefree(part, overlap_mm=0.02))
    return {'pieces': pieces, 'solid': solid, 'phase_mm': phase, 'moved_mm2': moved, 'raw': raw, 'clean': clean,
            'phases_tried': len(trials), 'locked': locked}


# --- the lockup ---------------------------------------------------------------------------------------------------------

def _to_mm(geom, scale_mm):
    """Font units (y up, on the baseline) to millimetres (y down, the baseline at 0)."""
    return affinity.affine_transform(geom, [scale_mm, 0.0, 0.0, -scale_mm, 0.0, 0.0])


def _nest(small, big, *, clear_mm, downward: bool):
    """``small`` moved vertically toward ``big`` (down when ``downward``) until it stands ``clear_mm`` from it."""
    if downward:
        start = big.bounds[1] - (small.bounds[3] - small.bounds[1]) - 4.0 * clear_mm - small.bounds[1]
        sign = 1.0
    else:
        start = big.bounds[3] + 4.0 * clear_mm - small.bounds[1]
        sign = -1.0
    far, near = 0.0, (big.bounds[3] - big.bounds[1]) + (small.bounds[3] - small.bounds[1])
    for _ in range(48):
        mid = 0.5 * (far + near)
        trial = affinity.translate(small, 0.0, start + sign * mid)
        if trial.distance(big) >= clear_mm:
            far = mid
        else:
            near = mid
    return start + sign * far


def _densest(ups, *, s, dx, dy, alif_mm, hatch_angle_deg, pitch_mm, contour_mm) -> dict:
    """Where the lettering is densest, by construction: inside the widest upright's hatched stem (from below its crown
    to the baseline), read across the hatch. ``prove`` reads it again with the shared reader on the foil plate."""
    up = max(ups, key=lambda u: u['x1'] - u['x0'])
    cx, w = dx + 0.5 * (up['x0'] + up['x1']) * s, (up['x1'] - up['x0']) * s
    top = dy - up['top'] * s
    return {'lines_per_cm': round(10.0 / pitch_mm, 2), 'transect_angle_deg': (hatch_angle_deg + 90.0) % 180.0,
            'where_mm': [round(cx - w / 2.0 + contour_mm, 3), round(top + CAP_SHARE * alif_mm, 3),
                         round(cx + w / 2.0 - contour_mm, 3), round(dy, 3)]}


def zilal(*, zone_mm, alif_mm, small_alif_mm, hatch_angle_deg, hatch_line_mm, hatch_pitch_mm, contour_mm, keyline_mm,
          keyline_hex, fill_hex, emboss_inset_mm, level_uprights, lozenge_dot, join_mm) -> dict:
    """B-1's lockup: ظلال as hero lettering, باليت above its right end, العيون below its left end, in ``zone_mm``
    (x0, y0, x1, y1 in mm on the lid). See the module's docstring for what each argument draws."""
    params = {'zone_mm': [float(v) for v in zone_mm], 'alif_mm': alif_mm, 'small_alif_mm': small_alif_mm,
              'hatch_angle_deg': hatch_angle_deg, 'hatch_line_mm': hatch_line_mm, 'hatch_pitch_mm': hatch_pitch_mm,
              'contour_mm': contour_mm, 'keyline_mm': keyline_mm, 'keyline_hex': keyline_hex, 'fill_hex': fill_hex,
              'emboss_inset_mm': emboss_inset_mm, 'level_uprights': bool(level_uprights),
              'lozenge_dot': bool(lozenge_dot), 'join_mm': join_mm}
    if hatch_pitch_mm - hatch_line_mm < FOIL_GAP_MIN_MM or hatch_line_mm < FOIL_LINE_MIN_MM:
        raise ValueError('a hatch of %.2f mm lines at %.2f mm pitch is outside the foil limits'
                         % (hatch_line_mm, hatch_pitch_mm))
    if keyline_mm <= KEYLINE_FOIL_OVERLAP_MM or contour_mm < KEYLINE_FOIL_OVERLAP_MM:
        raise ValueError('the keyline must be wider than the foil overlaps it, the contour at least that overlap')
    zx0, zy0, zx1, zy1 = [float(v) for v in zone_mm]
    held = face()
    font, glyph_set = _glyph_set(held['path'])
    alif_u = alif_units(glyph_set)
    s = alif_mm / alif_u
    s_small = small_alif_mm / alif_u
    words = {w: set_word(held['path'], glyph_set, w, tol_units=FLATTEN_TOL_MM / (s if w == HERO else s_small))
             for w in (ABOVE, HERO, BELOW)}
    ops = {}

    # the hero, in font units: the join, the dot apart from the bodies, the uprights levelled, the dot cut
    hero = words[HERO]
    zah = next(i for i, g in enumerate(hero) if unicodedata.name(g['char']).startswith('ARABIC LETTER ZAH'))
    zah_left = hero[zah]['geom'].bounds[0]                 # where the face joins ظ to لا (ظ never moves)
    if join_mm > 0:
        hero, ops['join'] = draw_out(hero, zah - 1, join_mm / s)
        ops['join']['mm'] = join_mm
    zah_parts = sorted(_pieces(hero[zah]['geom']), key=lambda p: p.area)
    dot_u = zah_parts[0]
    body_u = _polys_of(unary_union([g['geom'] for g in hero]).difference(dot_u.buffer(0.01)))
    dot_round_u = dot_u
    if level_uprights:
        body_u, ops['level'] = level(body_u, alif_u)
    if lozenge_dot:
        c = dot_u.centroid
        dot_u = lozenge(c.x, c.y, dot_u.area, tip_deg=FACET_APEX_DEG)
        ops['lozenge'] = {'dot_area_units2': round(dot_round_u.area, 1), 'lozenge_area_units2': round(dot_u.area, 1),
                          'centre_units': [round(c.x, 1), round(c.y, 1)], 'tip_deg': FACET_APEX_DEG}

    # the word's level stroke (the baseline stroke at the join of ظ and لا), which a level hatch is locked to
    level_run_u = _intervals_at_x(body_u, zah_left + 1.0)[0]

    # the uprights' heads, which the crowns are cut from once the hatch's phase is known
    heads_u = uprights(body_u, alif_u) if lozenge_dot else []

    # to millimetres, the hero's baseline at y 0 and its origin at x 0
    body = _to_mm(body_u, s)
    dot = _to_mm(dot_u, s)
    letters = _polys_of(unary_union([body, dot]))
    key_out = keyline_mm - KEYLINE_FOIL_OVERLAP_MM            # how far the keyline reaches outside the letter
    keyfoot = letters.buffer(key_out)

    # flush right in the zone; the small words nested above the right end and below the left end
    dx = zx1 - keyfoot.bounds[2]
    shift = lambda g, ddx, ddy: affinity.translate(g, ddx, ddy)
    body, dot, letters, keyfoot = [shift(g, dx, 0.0) for g in (body, dot, letters, keyfoot)]
    above = _polys_of(unary_union([_to_mm(g['geom'], s_small) for g in words[ABOVE]]))
    below = _polys_of(unary_union([_to_mm(g['geom'], s_small) for g in words[BELOW]]))
    above = shift(above, letters.bounds[2] - above.bounds[2], 0.0)
    below = shift(below, letters.bounds[0] - below.bounds[0], 0.0)
    above = shift(above, 0.0, _nest(above, keyfoot, clear_mm=SMALL_CLEAR_MM, downward=True))
    below = shift(below, 0.0, _nest(below, keyfoot, clear_mm=SMALL_CLEAR_MM, downward=False))
    foot_all = unary_union([keyfoot, above, below])
    dy = 0.5 * (zy0 + zy1) - 0.5 * (foot_all.bounds[1] + foot_all.bounds[3])
    body, dot, letters, keyfoot, above, below = [
        shift(g, 0.0, dy) for g in (body, dot, letters, keyfoot, above, below)]
    heads = [{'geom': shift(_to_mm(h['head'], s), dx, dy), 'cx_mm': dx + 0.5 * (h['x0'] + h['x1']) * s,
              'top_mm': dy - h['top'] * s} for h in heads_u]

    # the foil: contour, hatch, crowns and lozenge on the hero; the small words solid
    lozenge_foil = Polygon()
    if lozenge_dot:
        lozenge_foil = dot
        hatched = body
    else:
        hatched = letters

    def solid_of(phase_mm):
        cut = crowns(heads, phase_mm=phase_mm, angle_deg=hatch_angle_deg, line_mm=hatch_line_mm,
                     pitch_mm=hatch_pitch_mm, depth_mm=CAP_SHARE * alif_mm)
        return _polys_of(unary_union(cut + [lozenge_foil]))

    hatch = _hatch(hatched, solid_of, angle_deg=hatch_angle_deg, line_mm=hatch_line_mm,
                   pitch_mm=hatch_pitch_mm, contour_mm=contour_mm,
                   level_band_mm=(dy - level_run_u[1] * s, dy - level_run_u[0] * s))

    fill_ink, key_ink = 'ink:%s' % fill_hex.upper(), 'ink:%s' % keyline_hex.upper()
    marks = []
    for piece in _holefree(letters, overlap_mm=0.03):                                   # the letters' body ink
        marks.append(_mark(_ring(piece), width_mm=0.0, ink=fill_ink, fill=fill_ink, closed=True, finishes=()))
    for ring in _boundary_rings(letters.buffer(keyline_mm / 2.0 - KEYLINE_FOIL_OVERLAP_MM)):   # the keyline
        marks.append(_mark(ring, width_mm=keyline_mm, ink=key_ink, fill=None, closed=True, finishes=()))
    for ring in _boundary_rings(hatched.buffer(-contour_mm / 2.0, join_style='mitre')):          # the foil contour
        marks.append(_mark(ring, width_mm=contour_mm, ink=ROSE_GOLD, fill=None, closed=True, finishes=('foil',)))
    for piece in hatch['pieces']:                                                        # the open hatch
        marks.append(_mark(_ring(piece), width_mm=0.0, ink=ROSE_GOLD, fill=ROSE_GOLD, closed=True, finishes=('foil',)))
    solid = hatch['solid']
    if lozenge_dot:
        ops['crowns'] = {'count': len(heads), 'depth_share_of_alif': CAP_SHARE,
                         'cut': "along a hatch line's lower edge, the one nearest that depth below the upright's top"}
    for piece in _holefree(solid, overlap_mm=0.02):                                       # crowns and lozenge
        marks.append(_mark(_ring(piece), width_mm=0.0, ink=ROSE_GOLD, fill=ROSE_GOLD, closed=True, finishes=('foil',)))
    for piece in _holefree(unary_union([above, below]), overlap_mm=0.02):                # the small words
        marks.append(_mark(_ring(piece), width_mm=0.0, ink=ROSE_GOLD, fill=ROSE_GOLD, closed=True, finishes=('foil',)))
    relief = _polys_of(letters.buffer(-emboss_inset_mm, join_style='mitre'))
    relief_pieces = _holefree(relief, overlap_mm=0.0)
    for piece in _holefree(relief, overlap_mm=0.05):                                                          # the blind emboss
        marks.append(_mark(_ring(piece), width_mm=0.0, ink=BLIND, fill=BLIND, closed=True, finishes=('emboss',)))

    # the regions
    footprint = _filled(unary_union([keyfoot, above, below]))
    zone = box(zx0, zy0, zx1, zy1)
    paint = zone.difference(footprint.buffer(PAINT_GROW_MM))
    calm = _filled(footprint.buffer(CALM_GROW_MM))
    regions = {'paint': [_ring(p) for p in _holefree(paint, overlap_mm=0.0)],
               'relief': [_ring(p) for p in relief_pieces],
               'footprint': [_ring(p) for p in _holefree(footprint, overlap_mm=0.0)],
               'calm': [_ring(p) for p in _holefree(calm, overlap_mm=0.0)]}

    # the measures
    contour_band = hatched.difference(hatched.buffer(-contour_mm, join_style='mitre'))
    foil = _polys_of(unary_union([contour_band] + hatch['pieces'] + [solid, above, below]))
    thin = foil.difference(_opened(foil, FOIL_LINE_MIN_MM / 2.0)).area
    gaps = _closed(foil, FOIL_GAP_MIN_MM / 2.0).difference(foil).area
    shaping = {w: [{'name': g['name'], 'cluster': g['cluster']} for g in words[w]] for w in (ABOVE, HERO, BELOW)}
    measures = {
        'face': {'path': held['path'], 'sha256': held['sha256'], 'postscript': held['postscript'],
                 'licence': held['licence'], 'alif_units': alif_u, 'mm_per_unit_hero': s,
                 'mm_per_unit_small': s_small},
        'text': {'reading_order': [ABOVE, HERO, BELOW], 'shaped': shaping,
                 'reextracted': reextract([words[ABOVE], words[HERO], words[BELOW]]), 'descriptor': DESCRIPTOR},
        'operations': ops,
        'uprights_height_mm': [round(u['top'] * s, 3) for u in uprights(body_u, alif_u)],
        'upright_axes_mm': [{'cx_mm': round(dx + 0.5 * (u['x0'] + u['x1']) * s, 3), 'top_mm': round(dy - u['top'] * s, 3),
                             'width_mm': round((u['x1'] - u['x0']) * s, 3)} for u in uprights(body_u, alif_u)],
        'hero_mm': {'ink_bounds': [round(v, 2) for v in letters.bounds],
                    'width': round(letters.bounds[2] - letters.bounds[0], 2),
                    'height': round(letters.bounds[3] - letters.bounds[1], 2)},
        'lockup_bounds_mm': [round(v, 2) for v in footprint.bounds],
        'fits_zone': bool(zone.buffer(1e-6).contains(footprint)),
        'small_clear_mm': {'above': round(above.distance(keyfoot), 3), 'below': round(below.distance(keyfoot), 3)},
        'hatch': {'angle_deg': hatch_angle_deg, 'line_mm': hatch_line_mm, 'pitch_mm': hatch_pitch_mm,
                  'gap_mm': round(hatch_pitch_mm - hatch_line_mm, 3),
                  'lines_per_cm': round(10.0 / hatch_pitch_mm, 2), 'phase_mm': round(hatch['phase_mm'], 4),
                  'phase_rule': ('locked to the level stroke' if hatch['locked'] else
                                 'the least disturbed of %d offsets' % HATCH_PHASES),
                  'locked': hatch['locked'], 'phases_tried': hatch['phases_tried'],
                  'cleaned_mm2': round(hatch['moved_mm2'], 4),
                  'pieces': len(hatch['pieces'])},
        'densest_geometric': _densest(uprights(body_u, alif_u), s=s, dx=dx, dy=dy, alif_mm=alif_mm, hatch_angle_deg=hatch_angle_deg,
                                      pitch_mm=hatch_pitch_mm, contour_mm=contour_mm),
        'foil_limits_geometric': {'thinner_than_line_mm2': round(thin, 5), 'narrower_than_gap_mm2': round(gaps, 5),
                                  'min_line_mm': FOIL_LINE_MIN_MM, 'min_gap_mm': FOIL_GAP_MIN_MM},
        'foil_ink_mm2': round(foil.area, 2), 'foil_ink_pct': round(100.0 * foil.area / LID_AREA_MM2, 3),
        'relief_mm2': round(relief.area, 2), 'relief_pct': round(100.0 * relief.area / LID_AREA_MM2, 3),
        'marks': len(marks),
    }
    font.close()
    return {'kind': KIND, 'marks': marks, 'regions': regions, 'params': params, 'measures': measures}


# --- through the engine: the document, the render, the engine's own measures -------------------------------------------

FOIL_PLATE = 'FOIL_ROSE_GOLD'
#: a typography surface tag: the engine then draws by the non-exempt path, where a group's opacity reaches its
#: shapes, so the emboss carriers (opacity 0) print nothing on page 1 and only make their plate
SURFACE = {'typography_surface': 'apps/pipeline/services/orn_b1.py::document'}
EMBOSS_PLATE = 'EMBOSS'
#: the flat render's resolution and the mask line_density reads (D-D9-3: 40 px/mm or finer)
RENDER_DPI = 400
DENSITY_PX_PER_MM = 40.0
OUT_DIR = 'docs/audit/day-9/ornaments'


def _segments(points, *, closed: bool) -> list:
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    segs = [MoveTo(x=points[0][0], y=points[0][1])] + [LineTo(x=x, y=y) for x, y in points[1:]]
    if closed:
        segs.append(ClosePath())
    return segs


def document(result: dict, *, ground_hex: str, rose_gold_hex: str):
    """The lockup as an engine Document on the 190 x 120 lid over a plain ``ground_hex`` ground: printed inks as their
    colours, foil marks as ``rose_gold_hex`` with the FOIL_ROSE_GOLD finish, the emboss on zero-opacity carriers
    (Day 8's way for a clear finish), and the lockup group's ActualText the descriptor in logical order."""
    from apps.ire.graph import Color, Document, Finish, Group, Path, SolidFill, Stroke
    foil = Finish(kind='foil', plate=FOIL_PLATE, appearance=Color.from_hex(rose_gold_hex))
    emboss = Finish(kind='emboss', plate=EMBOSS_PLATE)
    ground = Path(name='ground', fill=SolidFill(color=Color.from_hex(ground_hex)),
                  segments=_segments([(0.0, 0.0), (LID_W_MM, 0.0), (LID_W_MM, LID_H_MM), (0.0, LID_H_MM)], closed=True))
    inks, foils, carriers = [], [], []
    for i, mk in enumerate(result['marks']):
        if mk['ink'] == BLIND:
            carriers.append(Path(name='emboss %d' % i, fill=SolidFill(color=Color.from_hex(ground_hex)),
                                 finishes=[emboss], segments=_segments(mk['points'], closed=True)))
            continue
        is_foil = mk['ink'] == ROSE_GOLD
        colour = Color.from_hex(rose_gold_hex if is_foil else mk['ink'].split(':', 1)[1])
        if mk['width'] > 0:
            node = Path(name='line %d' % i, stroke=Stroke(color=colour, width_mm=mk['width']),
                        segments=_segments(mk['points'], closed=mk['closed']), finishes=[foil] if is_foil else [])
        else:
            node = Path(name='shape %d' % i, fill=SolidFill(color=colour),
                        segments=_segments(mk['points'], closed=True), finishes=[foil] if is_foil else [])
        (foils if is_foil else inks).append(node)
    lockup = Group(name='ARABIC LOCKUP', role='typography', actual_text=DESCRIPTOR,
                   children=[Group(name='INK', children=inks), Group(name='FOIL', children=foils)])
    children = [ground, lockup]
    if carriers:
        children.append(Group(name='FINISH CARRIERS', role='effects', opacity=0.0, children=carriers))
    return Document(page_w=LID_W_MM, page_h=LID_H_MM, title='orn_b1 zilal', metadata=dict(SURFACE),
                    root=Group(name='Artwork', role='artwork', children=children))


def prove(result: dict, *, out_dir, key: str, ground_hex: str, rose_gold_hex: str) -> dict:
    """Render ``result`` through the engine and measure it with the shared tools: the .ai (emit_pdf_ai), page 1 at
    RENDER_DPI (``<key>.png``), the finish proof (``<key>-proof.png``), ``foil_limits``, ``coverage`` and
    ``line_density`` on the foil plate read at DENSITY_PX_PER_MM; the record written to ``<key>.json``."""
    import json
    from pathlib import Path as FsPath

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png
    from apps.pipeline.services import finish_proof
    out = FsPath(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ai = out / ('%s.ai' % key)
    emit_pdf_ai(document(result, ground_hex=ground_hex, rose_gold_hex=rose_gold_hex), str(ai))
    flat = out / ('%s.png' % key)
    if not pdf_to_png(ai, flat, dpi=RENDER_DPI):
        raise RuntimeError('page 1 of %s did not render' % ai)
    proof = finish_proof.render_proof(flat, ai, out / ('%s-proof.png' % key))
    limits = finish_proof.foil_limits(ai)
    cover = finish_proof.coverage(ai)
    masks = [m for m in finish_proof.plate_masks(ai, px_per_mm=DENSITY_PX_PER_MM) if m['kind'] == 'foil']
    density = finish_proof.line_density(masks[0]['mask'], px_per_mm=DENSITY_PX_PER_MM)
    del density['map']
    # where densest INSIDE the lettering: the same reader on one upright's hatched stem alone (its window clipped to
    # the stem, which the record says), beside the reading over the lid's 10 mm windows
    axis = max(result['measures']['upright_axes_mm'], key=lambda a: a['width_mm'])
    half = axis['width_mm'] / 2.0 - result['params']['contour_mm'] - FOIL_LINE_MIN_MM
    rows = (int((axis['top_mm'] + 0.5 * axis['width_mm'] + 6.0) * DENSITY_PX_PER_MM),
            int((axis['top_mm'] + 0.5 * axis['width_mm'] + 16.0) * DENSITY_PX_PER_MM))
    cols = (int((axis['cx_mm'] - half) * DENSITY_PX_PER_MM), int((axis['cx_mm'] + half) * DENSITY_PX_PER_MM))
    in_stem = finish_proof.line_density(masks[0]['mask'][rows[0]:rows[1], cols[0]:cols[1]], px_per_mm=DENSITY_PX_PER_MM)
    del in_stem['map']
    in_stem['crop_mm'] = [round(cols[0] / DENSITY_PX_PER_MM, 3), round(rows[0] / DENSITY_PX_PER_MM, 3),
                          round(cols[1] / DENSITY_PX_PER_MM, 3), round(rows[1] / DENSITY_PX_PER_MM, 3)]
    record = {'key': key, 'kind': result['kind'], 'params': result['params'], 'measures': result['measures'],
              'engine': {'foil_limits': limits, 'coverage': cover, 'line_density': density,
                         'line_density_in_stem': in_stem,
                         'proof': {k: v for k, v in proof.items() if k != 'flat_against_page_1'}},
              'files': {'ai': str(ai), 'flat': str(flat), 'proof': str(out / ('%s-proof.png' % key))}}
    (out / ('%s.json' % key)).write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str))
    return record
