"""D-D9-5 (Day 9, the owner's prompt of 20 October): "Enchanted Rose" becomes a LOGOTYPE built by our engine from a
licensed face's own outlines — ligatures, cut-ins, swash or custom terminals, optical kerning — never a default setting
and never traced: every shape is the face's own outline or geometry the engine computes.

THE FACE is a catalogue stem as the directions write it ('PlayfairDisplay-Italic[wght]@700', 'GreatVibes-Regular'). It
must be LICENSED — in ``font_roles.catalogue()``, the house's granted faces and the D-D7-1 GRANTED pool (a face without
licence evidence is never there) — and GRANTED: its record verified for production through the owner-grant channel
(``font_roles.verify_candidate``). Anything else is refused by name (``LetteringRefused``). A variable face draws at a
static instance of the weight it names (``font_roles.instance_at``), never its default. WHICH face sets the name is the
D-D8-5 match to the sketch — ``concept_design_map.set_display``, the one closest-face matcher: ``face_from_match`` turns
its record into the stem a logotype takes (its ``face`` where its state is SET; refused where it TRACED). This module
never measures a face against a picture.

THE OUTLINES (``glyph_outline``): the glyph's own contours read with fontTools — TrueType quadratics raised to cubics
exactly (BasePen's 2/3 rule, drawn into ``vq2_glyph_pen.CubicSink``), CFF cubics as they are, components decomposed —
scaled to millimetres, y down. Every glyph fills by the NONZERO rule, its contours turned so its outside runs the way
every engine-drawn shape's outside runs (``OUTER_SIGN``): pieces that overlap unite, never cancel.

THE SETTING (``set_word``): characters to glyphs through the cmap, then the face's own GSUB — 'liga' always; 'dlig',
'salt', the stylistic sets, 'swsh', 'init' and 'fina' on request — single, alternate and ligature substitutions (lookup
types 1, 3 and 4, and their extensions; a contextual lookup is not applied, and the record says so); placed by advance
(kerning 'none'), by advance plus the face's GPOS pair kerning ('font': ``concept_design_map._pair_kerning``, the reader
the D-D8-5 matcher sets its lines with), or OPTICALLY: each adjacent pair's facing outline profiles read on scanlines
across the x-height band (the cap band for two capitals), upright (sheared back by the face's own italic angle); its
visual gap the closest approach plus the white beyond it, each line's counted no deeper than a share of the band (an
open side reads as space only so far); the pair moved until that gap equals the face's own 'nn' ('HH', 'Hn', 'nH') at
the plain advance — the move clamped, never closer than a foil gap; a pair the face already joins (its outlines meet at
the plain advance) kept as the face drew it, and in a connecting script every pair of small letters.

THE OPERATIONS (``logotype``), each recorded with what it measured:
- ``alternate``: a glyph's stylistic alternate from the face's GSUB, under the feature named, where the face has one;
- ``join``: two adjacent glyphs bridged by an engine-drawn stroke (a ligature the face does not have, as thick as the
  left glyph's own ink where the stroke leaves it), or moved to overlap so their contours unite under nonzero fill;
- ``cut_in``: a shape subtracted from a glyph — an inline at an inset from its outline, a slot, or a polygon — a boolean
  difference on the outlines flattened at <= 0.005 mm (shapely), written back as LineTo paths;
- ``swash``: a calligraphic swash — a filled shape round a cubic centreline with a tapering, swelling width — begun
  inside a named glyph's terminal at the stroke's own measured width, its tip never finer than a foil line (D-D9-3).

THE LOGOTYPE is the Group LOGOTYPE: one compound path at nonzero winding (a join and a swash unite with their glyph and
nothing paints twice), and ``Group.actual_text`` = the words, which the emitter writes as the ActualText of a marked-
content span, so the drawn copy extracts as text. PyMuPDF reads such a span over vector content when it collects
vectors (``extracted_text``: ``fitz.TEXT_COLLECT_VECTORS``); its default text extraction does not.

Millimetres, y down, as the Design Graph; a word is set from its own origin (pen at x 0 on the baseline y 0).
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

SCHEMA = 'ire_lettering_logotype/1'
SETTING_SCHEMA = 'ire_lettering_setting/1'
SPECIMEN_SCHEMA = 'ire_lettering_specimen/1'
#: the logotype's group, by the name the build looks it up by
GROUP_NAME = 'LOGOTYPE'
ROOT = Path(__file__).resolve().parents[3]
DAY9_FONTS = ROOT / 'docs' / 'audit' / 'day-9' / 'fonts'

# --- refusals, by name --------------------------------------------------------------------------------------------
FACE_NOT_LICENSED = 'LETTERING_FACE_NOT_LICENSED'
FACE_NOT_GRANTED = 'LETTERING_FACE_NOT_GRANTED'
FACE_NO_LATIN = 'LETTERING_FACE_CARRIES_NO_LATIN'
FACE_WEIGHT_UNNAMED = 'LETTERING_VARIABLE_FACE_WEIGHT_UNNAMED'
FACE_WEIGHT_OFF_AXIS = 'LETTERING_FACE_WEIGHT_OFF_ITS_AXIS'
GLYPH_MISSING = 'LETTERING_GLYPH_MISSING'
TEXT_RIGHT_TO_LEFT = 'LETTERING_TEXT_RIGHT_TO_LEFT'
NO_CAPITAL = 'LETTERING_NO_CAPITAL_TO_SIZE_BY'
KERNING_UNKNOWN = 'LETTERING_KERNING_MODE_UNKNOWN'
OP_UNKNOWN = 'LETTERING_OPERATION_UNKNOWN'
OP_TARGET = 'LETTERING_OPERATION_TARGET_NOT_IN_TEXT'
#: an operation whose own numbers cannot do what it is named for (an overlap that does not overlap, a swash whose width
#: would fall under its tip, two alternates on one character)
OP_PARAMETER = 'LETTERING_OPERATION_PARAMETER_REFUSED'
TERMINAL_NOT_MEASURED = 'LETTERING_TERMINAL_NOT_MEASURED'
BRIDGE_NOT_MEASURED = 'LETTERING_BRIDGE_NOT_MEASURED'
MATCH_NOT_SET = 'LETTERING_MATCH_SET_NO_FACE'

# --- the executor's numbers, stated -------------------------------------------------------------------------------
#: a cut-in's outlines are flattened at this tolerance before the boolean difference (the build's own words)
FLATTEN_TOL_MM = 0.005
#: a cubic split this many times is flat whatever its control points say (a guard, never reached at 0.005 mm)
FLATTEN_MAX_SPLITS = 24
#: an outside contour's signed area (shoelace, page millimetres, y down) is positive; a counter's negative
OUTER_SIGN = 1.0
#: D-D9-3's print limits: a foil line at least this wide, a gap in foil at least this wide (finer goes to 9244 C)
FOIL_LINE_MIN_MM = 0.1
FOIL_GAP_MIN_MM = 0.2
#: the largest spots of each kind a logotype's record lists
PRINT_LIMIT_SPOTS = 5
#: the features every setting applies (the face's own ligatures)
DEFAULT_FEATURES = ('liga',)
#: features applied by a glyph's place in its word, not everywhere
POSITIONAL = {'init': 'first', 'fina': 'last'}
KERNING_MODES = ('none', 'font', 'optical')
#: optical kerning: scanlines across a band; a pair's white beyond its closest approach counted no deeper than this
#: share of the band (an open side — R's leg, E's arms, r's shoulder — reads as space only so far); a pair never moved
#: more than this (em), and never brought closer than this (em, and never under a foil gap) where it stood apart
OPTICAL_SCANLINES = 64
OPTICAL_DEPTH_OF_BAND = 0.25
OPTICAL_CLAMP_EM = 0.05
OPTICAL_MIN_CLEAR_EM = 0.012
#: the reference pairs each class of pair is spaced to — the face's own, at its plain advance
OPTICAL_REFERENCE = {'lower-lower': ('n', 'n', 'x'), 'upper-upper': ('H', 'H', 'cap'),
                     'upper-lower': ('H', 'n', 'x'), 'lower-upper': ('n', 'H', 'x')}
#: scanlines for a pair's closest approach over its whole height (optical kerning's guard, an overlap join)
CONTACT_SCANLINES = 160
#: a swash: its centre stepped this far between two circles of its width; its circles' quarter segments; a swash's tip
#: no finer than a foil line (D-D9-3), drawn round; its width tapering by this exponent and swelling in its middle by
#: this much (em) as a pen pressed and lifted
SWASH_STEP_MM = 0.08
SWASH_QUAD_SEGS = 16
SWASH_TIP_MM = 0.12
SWASH_TAPER = 1.3
SWASH_BELLY_EM = 0.03
#: a swash begins inside its terminal, at the widest inscribed circle found within this depth (em) back along its first
#: direction, probed in these steps (em): its first circle sits in the stroke, as wide as the stroke there
SWASH_START_DEPTH_EM = 0.06
SWASH_PROBE_STEP_EM = 0.004
#: a swash's start never wider than this (em): a calligraphic stroke leaves a heavy leg at a pen's width
SWASH_START_MAX_EM = 0.07
#: an inline's core smaller than this (em squared) is a serif's bracket, not a stroke: no inline is cut round it
INLINE_MIN_ISLAND_EM2 = 0.0015
#: a bridge leaves its left glyph this far inside its ink and enters the right glyph as far (em); its stroke no
#: thicker than this (em) — a bar's end, never a stem's length
BRIDGE_BURY_EM = 0.012
BRIDGE_MAX_EM = 0.06
#: a bridge's height searched this far up and down (em) for the left glyph's furthest ink and the right glyph's
BRIDGE_SEARCH_EM = 0.12
#: named terminals: the outline point furthest along this direction (page x right, y down)
TERMINALS = {'bottom_right': (1.0, 1.0), 'bottom_left': (-1.0, 1.0), 'top_right': (1.0, -1.0),
             'top_left': (-1.0, -1.0), 'right': (1.0, 0.0), 'left': (-1.0, 0.0), 'bottom': (0.0, 1.0),
             'top': (0.0, -1.0)}
OPS = ('alternate', 'join', 'cut_in', 'swash')
JOINS = ('bridge', 'overlap', 'stem')
#: a stem is a run of ink across the band at these shares of its height that stands over itself at this many of them
STEM_HEIGHTS = (0.2, 0.35, 0.5, 0.65, 0.8)
STEM_MIN_HEIGHTS = 3
#: a stroke in its own paint (a foil swash on ink letters) runs this far onto the letters it leaves, as a printer traps
#: two inks, so no line of board shows between them
SEPARATE_PAINT_TRAP_MM = 0.1
NEVER_TRACED = ('every shape is the face\'s own outline (fontTools, its file named and hashed) or geometry the engine '
                'computes from measured anchors and stated parameters — no picture is read')


class LetteringRefused(ValueError):
    """A logotype that cannot be built as asked, refused by name: ``code`` and the words why."""

    def __init__(self, code: str, why: str):
        super().__init__('%s: %s' % (code, why))
        self.code = code
        self.why = why


# =====================================================================================================================
# The face: licensed, granted, at the weight it names
# =====================================================================================================================

def _stem_and_weight(stem_text: str) -> tuple:
    """'Montserrat[wght]@500' → ('Montserrat[wght]', 500.0); a stem without a weight → (stem, None)."""
    if '@' in stem_text:
        stem, weight = stem_text.rsplit('@', 1)
        return stem, float(weight)
    return stem_text, None


def resolve_face(stem_text: str) -> dict:
    """The face ``stem_text`` names, licensed and granted, with the file its outlines are read from; refused by name.

    ``{"stem", "stem_text", "family", "postscript", "weight", "weight_named", "weight_class", "path" (the file drawn: a
    variable face's static instance), "granted_path", "sha256" (the granted file, re-hashed by the seam),
    "drawn_sha256", "instance", "origin", "licence", "licence_evidence", "grant": {verification, production_use_status,
    redistribution_status, approved_by, approved_at, source}}``. A static face draws as it is granted, whatever weight
    its stem names — as ``font_roles.resolve_line_face`` draws it — and both are kept: ``weight_named`` (the stem's
    '@', None where it names none) beside ``weight_class`` (the file's own OS/2 class); ``weight`` is the one named,
    else the file's own."""
    from apps.ire import font_roles
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    stem, weight = _stem_and_weight(stem_text)
    entry = font_roles.catalogue().get(stem)
    if entry is None:
        raise LetteringRefused(FACE_NOT_LICENSED, '%s is not in the licensed catalogue (font_roles.catalogue: the '
                                                  'house\'s granted faces and the D-D7-1 GRANTED pool) — a face '
                                                  'without licence evidence is never used' % stem)
    if not entry.get('latin'):
        raise LetteringRefused(FACE_NO_LATIN, '%s carries no Latin alphabet (its cmap, read when the catalogue was '
                                              'built): it cannot letter "%s"' % (stem, 'Enchanted Rose'))
    record = font_roles.verify_candidate('display', stem)
    if record is None or record['verification'] != VERIFIED_FOR_PRODUCTION:
        state = record['verification'] if record is not None else 'NO_RECORD'
        raise LetteringRefused(FACE_NOT_GRANTED, '%s is not granted for production: its record reads %s through the '
                                                 'owner-grant channel (font_roles.verify_candidate)' % (stem, state))
    drawn, instance = entry['path'], None
    if entry.get('variable'):
        if weight is None:
            raise LetteringRefused(FACE_WEIGHT_UNNAMED, '%s is variable and names no weight: a variable face never '
                                                        'draws its default instance (§BH33(2)) — name one, '
                                                        '"%s@700"' % (stem, stem))
        instance = font_roles.instance_at(stem, weight)
        if instance is None:
            raise LetteringRefused(FACE_WEIGHT_OFF_AXIS, '%s has no instance at weight %g (its wght axis %r)' % (
                stem, weight, (entry.get('axes') or {}).get('wght')))
        drawn = instance['path']
    font = _font(drawn, instance['sha256'] if instance is not None else record['sha256'])
    declared = float(font['OS/2'].usWeightClass) if 'OS/2' in font else None
    return {'stem': stem, 'stem_text': stem_text, 'family': entry.get('family') or record.get('font_family'),
            'postscript': instance['postscript'] if instance is not None else entry.get('postscript'),
            'weight': weight if weight is not None else declared, 'weight_named': weight, 'weight_class': declared,
            'path': str(drawn),
            'granted_path': str(entry['path']), 'sha256': record['sha256'],
            'drawn_sha256': instance['sha256'] if instance is not None else record['sha256'],
            'instance': ({k: instance[k] for k in ('postscript', 'path', 'sha256', 'axes', 'derived_from',
                                                    'derived_from_sha256')} if instance is not None else None),
            'origin': entry.get('origin'), 'outlines': 'CFF' if 'CFF ' in font else 'TrueType',
            'licence': record.get('licence_id') or entry.get('licence'),
            'licence_evidence': record.get('licence_evidence'),
            'grant': {k: record.get(k) for k in ('verification', 'production_use_status', 'redistribution_status',
                                                 'approved_by', 'approved_at', 'source')}}


@lru_cache(maxsize=16)
def _font(path: str, sha256: str):
    """The face's file, read whole (outlines, GSUB, GPOS) — once per file and digest."""
    from fontTools.ttLib import TTFont
    return TTFont(path)


@lru_cache(maxsize=16)
def _kerning(path: str, sha256: str) -> dict:
    """The face's GPOS pair kerning, ``{(left, right): font units}`` — ``concept_design_map._pair_kerning``, the reader
    the D-D8-5 matcher sets its lines with (formats 1 and 2 under 'kern')."""
    from apps.pipeline.services.concept_design_map import _pair_kerning
    return _pair_kerning(_font(path, sha256))


def _face_font(face: dict):
    return _font(face['path'], face['drawn_sha256'])


# =====================================================================================================================
# Outlines: the face's own, raised to cubics exactly, in millimetres
# =====================================================================================================================

def glyph_outline(face: dict, glyph: str) -> list:
    """``glyph``'s own contours in font units (y up): each ``[('M', p), ('L', p) | ('C', (p1, p2, p3)) ..., ('Z',
    None)]`` — TrueType quadratics raised to cubics exactly (BasePen's 2/3 rule: c1 = p0 + 2/3 (q − p0), c2 = p2 +
    2/3 (q − p2)), CFF cubics as they are, components decomposed through the glyph set."""
    from apps.ire.vq2_glyph_pen import CubicSink
    glyphs = _face_font(face).getGlyphSet()
    if glyph not in glyphs:
        raise LetteringRefused(GLYPH_MISSING, '%s has no glyph %r' % (face['stem'], glyph))
    sink = CubicSink(glyphs)
    glyphs[glyph].draw(sink)
    return sink.result()


def glyph_bounds_fu(face: dict, glyph: str):
    """The glyph's tight bounds in font units (fontTools BoundsPen: its curves' extremes); None for an empty glyph."""
    from fontTools.pens.boundsPen import BoundsPen
    glyphs = _face_font(face).getGlyphSet()
    pen = BoundsPen(glyphs)
    glyphs[glyph].draw(pen)
    return pen.bounds


def placed_contours(raw: list, *, scale_mm_per_unit: float, x_mm: float, baseline_mm: float) -> list:
    """Font-unit contours placed on the page: each contour a list of segments ``('L', p0, p1)`` or ``('C', p0, c1, c2,
    p3)`` in millimetres, y down, closed (a closing line added where the contour's last point is not its first)."""
    out = []
    for contour in raw:
        segs, start, cur = [], None, None
        for op, pts in contour:
            if op == 'M':
                start = cur = (x_mm + pts[0] * scale_mm_per_unit, baseline_mm - pts[1] * scale_mm_per_unit)
            elif op == 'L':
                p = (x_mm + pts[0] * scale_mm_per_unit, baseline_mm - pts[1] * scale_mm_per_unit)
                segs.append(('L', cur, p))
                cur = p
            elif op == 'C':
                c1, c2, p = ((x_mm + q[0] * scale_mm_per_unit, baseline_mm - q[1] * scale_mm_per_unit) for q in pts)
                segs.append(('C', cur, c1, c2, p))
                cur = p
            elif op == 'Z' and segs and cur != start:
                segs.append(('L', cur, start))
        if segs:
            out.append(segs)
    return out


def _translated(contours: list, dx_mm: float, dy_mm: float) -> list:
    return [[(seg[0],) + tuple((p[0] + dx_mm, p[1] + dy_mm) for p in seg[1:]) for seg in c] for c in contours]


def _reversed(contour: list) -> list:
    """The contour run the other way: the same points, the other winding."""
    return [(seg[0],) + tuple(reversed(seg[1:])) for seg in reversed(contour)]


def _flat_cubic(p0, c1, c2, p3, tol_mm: float, out: list) -> None:
    """The cubic's points appended to ``out`` (``p0`` excluded): split in half until both control points lie within
    ``tol_mm`` of the chord — the curve lies in its control points' hull, so it lies within ``tol_mm`` of the chords."""
    stack = [(p0, c1, c2, p3, 0)]
    while stack:
        a, b, c, d, depth = stack.pop()
        if depth >= FLATTEN_MAX_SPLITS or max(_to_segment(b, a, d), _to_segment(c, a, d)) <= tol_mm:
            out.append(d)
            continue
        ab, bc, cd = _mid(a, b), _mid(b, c), _mid(c, d)
        abc, bcd = _mid(ab, bc), _mid(bc, cd)
        m = _mid(abc, bcd)
        stack.append((m, bcd, cd, d, depth + 1))
        stack.append((a, ab, abc, m, depth + 1))


def _mid(p, q):
    return ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)


def _to_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    den = dx * dx + dy * dy
    if den == 0.0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / den))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def flattened(contour: list, tol_mm: float) -> list:
    """The contour as a ring of points within ``tol_mm`` of its curves (its first point not repeated at the end)."""
    pts = [contour[0][1]]
    for seg in contour:
        if seg[0] == 'L':
            pts.append(seg[2])
        else:
            _flat_cubic(seg[1], seg[2], seg[3], seg[4], tol_mm, pts)
    if len(pts) > 1 and math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) < 1e-12:
        pts.pop()
    return pts


def signed_area(ring: list) -> float:
    """The shoelace area of a ring of points (page millimetres, y down): positive for an outside (``OUTER_SIGN``)."""
    total = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        total += x0 * y1 - x1 * y0
    return total / 2.0


def _oriented(contours: list) -> tuple:
    """A glyph's contours turned, all together, so its largest contour — always an outside — runs as ``OUTER_SIGN``
    says: the face's own winding kept between its contours, made consistent with every engine-drawn shape."""
    if not contours:
        return contours, False
    areas = [signed_area(flattened(c, FLATTEN_TOL_MM * 4)) for c in contours]
    largest = max(range(len(areas)), key=lambda i: abs(areas[i]))
    if areas[largest] * OUTER_SIGN < 0:
        return [_reversed(c) for c in contours], True
    return contours, False


def tight_bbox(contours: list) -> tuple:
    """``(x0, y0, x1, y1)`` mm of the curves themselves (fontTools calcCubicBounds: a cubic's extremes, never its
    control points)."""
    from fontTools.misc.bezierTools import calcCubicBounds
    x0 = y0 = math.inf
    x1 = y1 = -math.inf
    for c in contours:
        for seg in c:
            if seg[0] == 'L':
                bx0, by0 = min(seg[1][0], seg[2][0]), min(seg[1][1], seg[2][1])
                bx1, by1 = max(seg[1][0], seg[2][0]), max(seg[1][1], seg[2][1])
            else:
                bx0, by0, bx1, by1 = calcCubicBounds(seg[1], seg[2], seg[3], seg[4])
            x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
    return x0, y0, x1, y1


def graph_segments(contours: list) -> list:
    """Contours as the Design Graph's own segments: MoveTo, LineTo / CubicTo, ClosePath."""
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    out = []
    for c in contours:
        out.append(MoveTo(x=c[0][1][0], y=c[0][1][1]))
        for seg in c:
            if seg[0] == 'L':
                out.append(LineTo(x=seg[2][0], y=seg[2][1]))
            else:
                out.append(CubicTo(x1=seg[2][0], y1=seg[2][1], x2=seg[3][0], y2=seg[3][1], x=seg[4][0], y=seg[4][1]))
        out.append(ClosePath())
    return out


def region(contours: list):
    """The area ``contours`` fill by the NONZERO rule (shapely): the outlines flattened at ``FLATTEN_TOL_MM``, noded,
    every face of the arrangement kept where the contours' winding numbers sum to anything but zero — overlapping
    outsides unite, a counter stays open."""
    import numpy as np
    from shapely.geometry import LineString
    from shapely.geometry import Polygon as _Polygon
    from shapely.ops import polygonize, unary_union
    rings = [r for r in (flattened(c, FLATTEN_TOL_MM) for c in contours) if len(r) >= 3]
    if not rings:
        return _Polygon()
    arrays = [np.asarray(r, dtype=float) for r in rings]
    noded = unary_union([LineString(r + [r[0]]) for r in rings])
    kept = [f for f in polygonize(noded) if _winding(f.representative_point().coords[0], arrays) != 0]
    return unary_union(kept)


def _winding(point, arrays) -> int:
    """The winding number of the rings about ``point`` (Sunday's crossing rule, signed by each edge's direction)."""
    import numpy as np
    x, y = point
    total = 0
    for p in arrays:
        q = np.roll(p, -1, axis=0)
        side = (q[:, 0] - p[:, 0]) * (y - p[:, 1]) - (x - p[:, 0]) * (q[:, 1] - p[:, 1])
        up = (p[:, 1] <= y) & (q[:, 1] > y) & (side > 0)
        down = (p[:, 1] > y) & (q[:, 1] <= y) & (side < 0)
        total += int(up.sum()) - int(down.sum())
    return total


def _polygons(geom) -> list:
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return [geom]
    return [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'Polygon' and not g.is_empty]


def ring_contours(geom) -> list:
    """A shapely area as LineTo contours: each outside run as ``OUTER_SIGN`` says, each hole the other way."""
    from shapely.geometry.polygon import orient
    out = []
    for poly in _polygons(geom):
        poly = orient(poly, sign=OUTER_SIGN)
        for ring in [poly.exterior] + list(poly.interiors):
            pts = [(float(x), float(y)) for x, y in list(ring.coords)[:-1]]
            if len(pts) >= 3:
                out.append([('L', p, q) for p, q in zip(pts, pts[1:] + pts[:1])])
    return out


# =====================================================================================================================
# The setting: cmap, the face's own GSUB, advance + kerning or optical kerning
# =====================================================================================================================

def _features_of_script(table) -> list:
    """The feature records the face lists for its Latin script (else its default script, else every record)."""
    records = list(table.FeatureList.FeatureRecord) if table.FeatureList else []
    scripts = {r.ScriptTag: r.Script for r in table.ScriptList.ScriptRecord} if table.ScriptList else {}
    for tag in ('latn', 'DFLT'):
        script = scripts.get(tag)
        if script is not None and script.DefaultLangSys is not None:
            return [records[i] for i in script.DefaultLangSys.FeatureIndex if i < len(records)]
    return records


def feature_lookups(face: dict, tag: str) -> list:
    """The GSUB lookup indices the face lists under ``tag`` for its Latin script — [] where it has none."""
    font = _face_font(face)
    if 'GSUB' not in font or not font['GSUB'].table.LookupList:
        return []
    out = set()
    for record in _features_of_script(font['GSUB'].table):
        if record.FeatureTag == tag:
            out.update(record.Feature.LookupListIndex)
    return sorted(out)


def _subtables(lookup) -> list:
    out = []
    for st in lookup.SubTable:
        kind = lookup.LookupType
        if kind == 7:
            kind, st = st.ExtensionLookupType, st.ExtSubTable
        out.append((kind, st))
    return out


def _apply_lookup(font, index: int, run: list, allowed, tag: str) -> list:
    """One GSUB lookup over ``run`` (``[{glyph, cluster, subs}]``): single (1), alternate (3, its first alternate) and
    ligature (4) substitutions, the first subtable that covers a glyph applying; ``allowed`` (character indices, or None
    for every glyph) limits it to the glyphs standing for those characters."""
    subs = _subtables(font['GSUB'].table.LookupList.Lookup[index])
    out, i = [], 0
    while i < len(run):
        item = run[i]
        if item['space'] or (allowed is not None and not set(item['cluster']) & allowed):
            out.append(item)
            i += 1
            continue
        done = False
        for kind, st in subs:
            g = item['glyph']
            if kind == 1 and g in st.mapping:
                out.append(dict(item, glyph=st.mapping[g], subs=item['subs'] + [
                    {'feature': tag, 'lookup': index, 'type': 'single', 'from': g, 'to': st.mapping[g]}]))
                i, done = i + 1, True
            elif kind == 3 and g in st.alternates and st.alternates[g]:
                to = st.alternates[g][0]
                out.append(dict(item, glyph=to, subs=item['subs'] + [
                    {'feature': tag, 'lookup': index, 'type': 'alternate', 'from': g, 'to': to}]))
                i, done = i + 1, True
            elif kind == 4 and g in st.ligatures:
                for lig in st.ligatures[g]:
                    comps = list(lig.Component)
                    nxt = run[i + 1:i + 1 + len(comps)]
                    if len(nxt) == len(comps) and all(not n['space'] and n['glyph'] == c for n, c in zip(nxt, comps)):
                        cluster = [k for n in [item] + nxt for k in n['cluster']]
                        out.append({'glyph': lig.LigGlyph, 'cluster': cluster, 'space': False,
                                    'subs': item['subs'] + [{'feature': tag, 'lookup': index, 'type': 'ligature',
                                                             'from': [item['glyph']] + comps, 'to': lig.LigGlyph}]})
                        i, done = i + 1 + len(comps), True
                        break
            if done:
                break
        if not done:
            out.append(item)
            i += 1
    return out


def _positional_chars(text: str, where: str) -> set:
    """The characters standing first (or last) in their word."""
    out = set()
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        if where == 'first' and (i == 0 or text[i - 1].isspace()):
            out.add(i)
        if where == 'last' and (i == len(text) - 1 or text[i + 1].isspace()):
            out.add(i)
    return out


def _substitute(face: dict, text: str, run: list, features, alternates: dict) -> tuple:
    """The face's own GSUB over the run, every lookup in the order the face lists them (as OpenType applies them).
    ``alternates``: ``{character index: feature}`` — a feature applied to that character's glyph alone."""
    font = _face_font(face)
    plan = {}                                   # lookup index -> (feature, the characters it may change)
    asked, contextual = [], []
    everything = None
    for tag in features:
        allowed = _positional_chars(text, POSITIONAL[tag]) if tag in POSITIONAL else everything
        lookups = feature_lookups(face, tag)
        asked.append({'feature': tag, 'lookups': lookups, 'in_face': bool(lookups)})
        for index in lookups:
            plan[index] = _widened(plan.get(index), tag, allowed)
    for char_index, tag in sorted(alternates.items()):
        lookups = feature_lookups(face, tag)
        asked.append({'feature': tag, 'at': char_index, 'lookups': lookups, 'in_face': bool(lookups)})
        for index in lookups:
            plan[index] = _widened(plan.get(index), tag, {char_index})
    for index in sorted(plan):
        kinds = {k for k, _st in _subtables(font['GSUB'].table.LookupList.Lookup[index])}
        if kinds - {1, 3, 4}:
            contextual.append({'feature': plan[index][0], 'lookup': index, 'types': sorted(kinds - {1, 3, 4}),
                               'why': 'a contextual or chaining lookup: not applied by this setter'})
        tag, allowed = plan[index]
        run = _apply_lookup(font, index, run, allowed, tag)
    return run, asked, contextual


def _widened(current, tag, allowed):
    """A lookup's plan widened: every character where any feature naming it may change it (None: everywhere)."""
    if current is None:
        return tag, allowed
    if current[1] is None or allowed is None:
        return current[0], None
    return current[0], current[1] | allowed


def _is_rtl(text: str) -> bool:
    return any(unicodedata.bidirectional(ch) in ('R', 'AL') for ch in text)


def _case(ch: str) -> str | None:
    if ch.isupper():
        return 'upper'
    if ch.islower():
        return 'lower'
    return None


def set_word(text: str, face, *, cap_mm: float, features=DEFAULT_FEATURES, alternates=None, kerning: str = 'optical',
             cap_char=None) -> dict:
    """``text`` set in ``face`` (a stem, resolved and checked here, or ``resolve_face``'s record) so the capital it is
    sized by stands ``cap_mm`` above the baseline — the capital's own outline top, measured (fontTools BoundsPen) on
    the glyph actually drawn. The pen starts at x 0 on the baseline y 0 (mm, y down).

    ``features``: the face's GSUB features applied ('liga' always; 'dlig', 'salt', 'ssNN', 'swsh'; 'init' and 'fina' at
    a word's first and last glyph). ``alternates``: ``{character index: feature}`` for one glyph. ``kerning``: 'none'
    (advances), 'font' (advances plus the face's GPOS pair kerning) or 'optical'. ``cap_char``: the capital to size by
    (the text's first capital where None; 'H' where the text has none).

    Returns ``{"schema", "text", "face", "em_mm", "scale_mm_per_unit", "cap_mm", "cap_reference", "x_height_mm",
    "cap_height_mm", "kerning", "features", "contextual_not_applied", "glyphs": [placement], "advance_mm", "optical"}``
    — each placement ``{"index", "glyph", "chars", "cluster", "space", "x_mm", "advance_mm", "kern_mm", "optical_mm",
    "substitutions", "contours"}``, its contours placed (mm, y down) and turned to ``OUTER_SIGN``."""
    if not text.strip():
        raise LetteringRefused(GLYPH_MISSING, 'no words to letter: %r' % text)
    if isinstance(face, str):
        face = resolve_face(face)
    if kerning not in KERNING_MODES:
        raise LetteringRefused(KERNING_UNKNOWN, 'kerning %r is not one of %s' % (kerning, ', '.join(KERNING_MODES)))
    if _is_rtl(text):
        raise LetteringRefused(TEXT_RIGHT_TO_LEFT, 'a logotype here is set left to right; the Arabic line is set in '
                                                   'its display face through the emitter\'s Arabic path')
    font = _face_font(face)
    cmap = font.getBestCmap()
    run = []
    for i, ch in enumerate(text):
        if ord(ch) not in cmap:
            raise LetteringRefused(GLYPH_MISSING, '%s has no glyph for %r' % (face['stem'], ch))
        run.append({'glyph': cmap[ord(ch)], 'cluster': [i], 'space': ch.isspace(), 'subs': []})
    run, asked, contextual = _substitute(face, text, run, tuple(features), dict(alternates) if alternates else {})
    upm = float(font['head'].unitsPerEm)
    hmtx = font['hmtx']
    reference = _reference_capital(face, text, run, cap_char, cmap)
    em_mm = cap_mm * upm / reference['top_fu']
    scale = em_mm / upm
    kern = _kerning(face['path'], face['drawn_sha256']) if kerning == 'font' else {}
    glyphs, pen_fu = [], 0.0
    for k, item in enumerate(run):
        kern_fu = 0.0
        if k and (run[k - 1]['glyph'], item['glyph']) in kern:
            kern_fu = float(kern[(run[k - 1]['glyph'], item['glyph'])])
        pen_fu += kern_fu
        raw = [] if item['space'] else glyph_outline(face, item['glyph'])
        contours, turned = _oriented(placed_contours(raw, scale_mm_per_unit=scale, x_mm=pen_fu * scale,
                                                     baseline_mm=0.0))
        glyphs.append({'index': k, 'glyph': item['glyph'], 'chars': ''.join(text[i] for i in item['cluster']),
                       'cluster': list(item['cluster']), 'space': item['space'], 'x_mm': pen_fu * scale,
                       'advance_mm': hmtx[item['glyph']][0] * scale, 'kern_mm': kern_fu * scale, 'optical_mm': 0.0,
                       'substitutions': item['subs'], 'turned': turned, 'contours': contours})
        pen_fu += hmtx[item['glyph']][0]
    bands = _bands(face, cmap, scale)
    optical = None
    if kerning == 'optical':
        optical = _optical(face, text, glyphs, cmap, scale, bands)
    advance = glyphs[-1]['x_mm'] + glyphs[-1]['advance_mm']
    return {'schema': SETTING_SCHEMA, 'text': text, 'face': face, 'em_mm': em_mm, 'scale_mm_per_unit': scale,
            'cap_mm': cap_mm, 'cap_reference': reference, 'x_height_mm': bands['x'], 'cap_height_mm': bands['cap'],
            'kerning': kerning, 'features': asked, 'contextual_not_applied': contextual, 'glyphs': glyphs,
            'advance_mm': advance, 'optical': optical}


def _reference_capital(face, text, run, cap_char, cmap) -> dict:
    """The capital the setting is sized by: ``cap_char``'s first occurrence, else the text's first capital — the glyph
    drawn for it (after its substitutions) — else the face's 'H'; its outline top in font units."""
    index = None
    if cap_char is not None:
        if cap_char not in text:
            raise LetteringRefused(NO_CAPITAL, '%r is not in %r' % (cap_char, text))
        index = text.index(cap_char)
    else:
        index = next((i for i, ch in enumerate(text) if ch.isupper()), None)
    if index is not None:
        item = next(it for it in run if index in it['cluster'])
        glyph, char = item['glyph'], text[index]
    elif ord('H') in cmap:
        glyph, char = cmap[ord('H')], 'H'
    else:
        raise LetteringRefused(NO_CAPITAL, '%r has no capital and %s no H to size by' % (text, face['stem']))
    bounds = glyph_bounds_fu(face, glyph)
    if bounds is None or bounds[3] <= 0:
        raise LetteringRefused(NO_CAPITAL, 'the capital %r (%s) of %s stands no height above the baseline' % (
            char, glyph, face['stem']))
    return {'char': char, 'char_index': index, 'glyph': glyph, 'top_fu': float(bounds[3]),
            'in_text': index is not None}


def _bands(face, cmap, scale) -> dict:
    """The face's own x-height and cap height in mm at this setting: the tops of its 'x' and 'H' outlines (None where
    the face has no such glyph)."""
    out = {}
    for key, ch in (('x', 'x'), ('cap', 'H')):
        out[key] = None
        if ord(ch) in cmap:
            b = glyph_bounds_fu(face, cmap[ord(ch)])
            if b is not None and b[3] > 0:
                out[key] = b[3] * scale
    return out


# --- optical kerning ------------------------------------------------------------------------------------------------

def _rings(contours: list, tol_mm: float) -> list:
    import numpy as np
    return [np.asarray(r, dtype=float) for r in (flattened(c, tol_mm) for c in contours) if len(r) >= 3]


def profile(rings: list, ys):
    """The ink's leftmost and rightmost x on each scanline ``ys`` (page mm, y down): ``(lo, hi)``, +inf / -inf on a
    line with no ink."""
    import numpy as np
    ys = np.asarray(ys, dtype=float)
    lo = np.full(len(ys), np.inf)
    hi = np.full(len(ys), -np.inf)
    yy = ys[:, None]
    for p in rings:
        q = np.roll(p, -1, axis=0)
        y0, y1 = p[:, 1][None, :], q[:, 1][None, :]
        cross = ((y0 <= yy) & (y1 > yy)) | ((y1 <= yy) & (y0 > yy))
        dy = np.where(y1 == y0, 1.0, y1 - y0)
        x = p[:, 0][None, :] + (yy - y0) / dy * (q[:, 0] - p[:, 0])[None, :]
        lo = np.minimum(lo, np.where(cross, x, np.inf).min(axis=1))
        hi = np.maximum(hi, np.where(cross, x, -np.inf).max(axis=1))
    return lo, hi


def _scanlines(top_mm: float):
    import numpy as np
    return -(np.arange(OPTICAL_SCANLINES) + 0.5) / OPTICAL_SCANLINES * top_mm


def _lean(face: dict) -> float:
    """The face's own slant as a shear (tan of its italic angle, post table): profiles are read upright."""
    font = _face_font(face)
    angle = float(font['post'].italicAngle)          # the post table is required in every face
    return math.tan(math.radians(-angle))


def facing(contours_local: list, top_mm: float, lean: float):
    """A glyph's two profiles across a band (its own frame: origin at x 0), read upright — sheared back by ``lean``, the
    face's own slant: ``(lo, hi)`` per scanline, +inf / -inf where the glyph has no ink on the line."""
    ys = _scanlines(top_mm)
    lo, hi = profile(_rings(contours_local, FLATTEN_TOL_MM * 4), ys)
    return lo + ys * lean, hi + ys * lean


def visual_gap(right_of_first, left_of_second, distance_mm: float, depth_mm: float):
    """A pair's visual gap (mm) when the origins stand ``distance_mm`` apart: its closest approach across the band,
    plus the mean of each scanline's white beyond that approach counted no deeper than ``depth_mm`` (a line where
    either glyph has no ink counts the full depth) — the white of an open side (R's leg, E's arms, r's shoulder) read
    only so far as the eye reads it. It grows one for one with the distance, so a pair is brought to a target by one
    subtraction. None where the two glyphs face each other on no scanline."""
    import numpy as np
    both = np.isfinite(right_of_first) & np.isfinite(left_of_second)
    if not both.any():
        return None
    gaps = distance_mm + left_of_second[both] - right_of_first[both]
    closest = float(gaps.min())
    beyond = np.full(len(right_of_first), depth_mm)
    beyond[both] = np.minimum(gaps - closest, depth_mm)
    return closest + float(beyond.mean())


def _closest(left_contours: list, right_contours: list) -> float:
    """The two glyphs' closest approach (mm, as placed): over their whole height, the least white between the left
    glyph's rightmost ink and the right glyph's leftmost on a scanline; +inf where they share no height."""
    import numpy as np
    boxes = [tight_bbox(left_contours), tight_bbox(right_contours)]
    ys = np.linspace(min(b[1] for b in boxes), max(b[3] for b in boxes), CONTACT_SCANLINES)
    _l, hi = profile(_rings(left_contours, FLATTEN_TOL_MM * 4), ys)
    lo, _r = profile(_rings(right_contours, FLATTEN_TOL_MM * 4), ys)
    both = np.isfinite(hi) & np.isfinite(lo)
    if not both.any():
        return math.inf
    return float((lo[both] - hi[both]).min())


def _pair_class(text: str, left: dict, right: dict):
    lc, rc = _case(text[left['cluster'][-1]]), _case(text[right['cluster'][0]])
    if lc is None or rc is None:
        return None
    return '%s-%s' % (lc, rc)


def _optical(face, text, glyphs, cmap, scale, bands) -> dict:
    """Optical kerning in place (``glyphs``' x and contours moved): every pair of letters spaced so its visual gap
    (``visual_gap``) equals its class's reference pair at the face's own advance — 'nn', 'HH', 'Hn' or 'nH' — the move
    clamped to ``OPTICAL_CLAMP_EM`` and never closer than ``OPTICAL_MIN_CLEAR_EM`` where the pair stood apart; a pair
    whose outlines meet at the plain advance is a join the face drew, kept — and in a connecting script (its own 'nn'
    meets at the plain advance) every pair of small letters stands as the face joins it."""
    em_mm = scale * float(_face_font(face)['head'].unitsPerEm)
    clamp_mm, clear_mm = OPTICAL_CLAMP_EM * em_mm, max(OPTICAL_MIN_CLEAR_EM * em_mm, FOIL_GAP_MIN_MM)
    lean = _lean(face)
    depth = {band: (OPTICAL_DEPTH_OF_BAND * bands[band] if bands[band] is not None else None) for band in bands}
    cache = {}

    def face_of(glyph_name, contours_local, band):
        key = (glyph_name, band)
        if key not in cache:
            cache[key] = facing(contours_local, bands[band], lean)
        return cache[key]

    targets, missing = {}, []
    for cls, (a, b, band) in OPTICAL_REFERENCE.items():
        if bands[band] is None or ord(a) not in cmap or ord(b) not in cmap:
            missing.append(cls)
            continue
        ga, gb = cmap[ord(a)], cmap[ord(b)]
        _la, ra = face_of(ga, placed_contours(glyph_outline(face, ga), scale_mm_per_unit=scale, x_mm=0.0,
                                              baseline_mm=0.0), band)
        lb, _rb = face_of(gb, placed_contours(glyph_outline(face, gb), scale_mm_per_unit=scale, x_mm=0.0,
                                              baseline_mm=0.0), band)
        gap = visual_gap(ra, lb, _face_font(face)['hmtx'][ga][0] * scale, depth[band])
        if gap is None:
            missing.append(cls)
            continue
        targets[cls] = {'pair': a + b, 'band': band, 'band_mm': bands[band], 'depth_mm': depth[band], 'gap_mm': gap}
    connecting = False
    if ord('n') in cmap:
        n_glyph = cmap[ord('n')]
        n_local = placed_contours(glyph_outline(face, n_glyph), scale_mm_per_unit=scale, x_mm=0.0, baseline_mm=0.0)
        n_advance = _face_font(face)['hmtx'][n_glyph][0] * scale
        connecting = _closest(n_local, _translated(n_local, n_advance, 0.0)) <= 0.0
    pairs, shift = [], 0.0
    for k in range(1, len(glyphs)):
        left, right = glyphs[k - 1], glyphs[k]
        right['x_mm'] += shift
        right['contours'] = _translated(right['contours'], shift, 0.0)
        if left['space'] or right['space']:
            continue
        cls = _pair_class(text, left, right)
        row = {'pair': left['chars'] + right['chars'], 'glyphs': [left['glyph'], right['glyph']], 'class': cls}
        if cls is None or cls not in targets:
            row.update({'kept': 'no reference pair for this class in the face' if cls in missing else 'not two letters',
                        'adjust_mm': float(0)})
            pairs.append(row)
            continue
        if cls == 'lower-lower' and connecting:
            row.update({'kept': ('a connecting script (its own "nn" meets at the plain advance): its small letters '
                                 'stand as the face joins them'), 'adjust_mm': float(0)})
            pairs.append(row)
            continue
        target = targets[cls]
        _la, ra = face_of(left['glyph'], _translated(left['contours'], -left['x_mm'], 0.0), target['band'])
        lb, _rb = face_of(right['glyph'], _translated(right['contours'], -right['x_mm'], 0.0), target['band'])
        distance = right['x_mm'] - left['x_mm']
        plain = visual_gap(ra, lb, distance, target['depth_mm'])
        if plain is None:
            row.update({'kept': 'the two glyphs face each other nowhere in the band', 'adjust_mm': 0.0})
            pairs.append(row)
            continue
        closest = _closest(left['contours'], right['contours'])
        row.update({'target_mm': target['gap_mm'], 'plain_mm': plain, 'closest_plain_mm': closest})
        if closest <= 0.0:
            row.update({'kept': 'joined by the face: its outlines meet at the plain advance', 'adjust_mm': 0.0,
                        'set_mm': plain})
            pairs.append(row)
            continue
        wanted = target['gap_mm'] - plain
        adjust = max(-clamp_mm, min(clamp_mm, wanted))
        guarded = math.isfinite(closest) and closest + adjust < clear_mm
        if guarded:
            adjust = clear_mm - closest
        row.update({'adjust_mm': adjust, 'clamped': adjust != wanted and not guarded, 'guarded': guarded,
                    'set_mm': visual_gap(ra, lb, distance + adjust, target['depth_mm'])})
        pairs.append(row)
        right['optical_mm'] = adjust
        right['x_mm'] += adjust
        right['contours'] = _translated(right['contours'], adjust, 0.0)
        shift += adjust
    return {'targets': targets, 'pairs': pairs, 'clamp_mm': clamp_mm, 'min_clear_mm': clear_mm,
            'connecting_script': connecting, 'scanlines': OPTICAL_SCANLINES, 'depth_of_band': OPTICAL_DEPTH_OF_BAND,
            'lean': lean,
            'measure': ('the closest approach across the band plus each scanline\'s white beyond it to a depth, read '
                        'upright')}


def pair_gaps(setting: dict) -> list:
    """Each pair of letters' visual gap (mm) as set, by optical kerning's own measure against its class's band:
    ``[{"pair", "class", "gap_mm"}]``."""
    face = setting['face']
    cmap = _face_font(face).getBestCmap()
    scale = setting['scale_mm_per_unit']
    bands = _bands(face, cmap, scale)
    lean = _lean(face)
    text, glyphs = setting['text'], setting['glyphs']
    out = []
    for k in range(1, len(glyphs)):
        left, right = glyphs[k - 1], glyphs[k]
        if left['space'] or right['space']:
            continue
        cls = _pair_class(text, left, right)
        if cls is None or bands[OPTICAL_REFERENCE[cls][2]] is None:
            continue
        band = OPTICAL_REFERENCE[cls][2]
        _la, ra = facing(_translated(left['contours'], -left['x_mm'], 0.0), bands[band], lean)
        lb, _rb = facing(_translated(right['contours'], -right['x_mm'], 0.0), bands[band], lean)
        gap = visual_gap(ra, lb, right['x_mm'] - left['x_mm'], OPTICAL_DEPTH_OF_BAND * bands[band])
        if gap is not None:
            out.append({'pair': left['chars'] + right['chars'], 'class': cls, 'gap_mm': gap})
    return out


# =====================================================================================================================
# Engine geometry: a stroke round a cubic centreline, its width a profile along it
# =====================================================================================================================

def cubic_point(p0, p1, p2, p3, t: float) -> tuple:
    u = 1.0 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def swash_width_mm(t: float, *, start_mm: float, tip_mm: float, taper: float, belly_mm: float) -> float:
    """A calligraphic stroke's width a share ``t`` along it: from ``start_mm`` to ``tip_mm``, falling by ``taper`` and
    swelling by ``belly_mm`` in its middle as a pen pressed and lifted — never under ``tip_mm``."""
    return tip_mm + (start_mm - tip_mm) * (1.0 - t) ** taper + belly_mm * math.sin(math.pi * t)


def stroke_centres(p0, p1, p2, p3, *, start_mm: float, tip_mm: float, taper: float, belly_mm: float) -> list:
    """The stroke's centre points and widths, ``[(x, y, width)]``, stepped ``SWASH_STEP_MM`` apart along the cubic."""
    probe = [cubic_point(p0, p1, p2, p3, k / 256.0) for k in range(257)]
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(probe, probe[1:]))
    n = max(16, int(math.ceil(length / SWASH_STEP_MM)))
    out = []
    for k in range(n + 1):
        t = k / float(n)
        x, y = cubic_point(p0, p1, p2, p3, t)
        out.append((x, y, swash_width_mm(t, start_mm=start_mm, tip_mm=tip_mm, taper=taper, belly_mm=belly_mm)))
    return out


def stroke_outline(centres: list):
    """The filled stroke: the union of the hulls of each two neighbouring circles of its width (shapely) — round where
    it ends, never crossing itself. Computed from the centres alone: no picture is read."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    discs = [Point(x, y).buffer(w / 2.0, quad_segs=SWASH_QUAD_SEGS) for x, y, w in centres]
    hulls = [unary_union([a, b]).convex_hull for a, b in zip(discs, discs[1:])]
    return unary_union(hulls)


def swash_geometry(p0, p1, p2, p3, *, start_mm: float, tip_mm: float, taper: float, belly_mm: float) -> dict:
    """A swash from its cubic centreline (mm, y down) and width profile: ``{"centreline", "centres", "outline"
    (LineTo contours, ``OUTER_SIGN``), "area_mm2", "min_width_mm"}``."""
    centres = stroke_centres(p0, p1, p2, p3, start_mm=start_mm, tip_mm=tip_mm, taper=taper, belly_mm=belly_mm)
    shape = stroke_outline(centres)
    return {'centreline': [list(p0), list(p1), list(p2), list(p3)], 'centres': centres,
            'outline': ring_contours(shape), 'area_mm2': shape.area, 'min_width_mm': min(w for _x, _y, w in centres)}


# =====================================================================================================================
# The logotype
# =====================================================================================================================

def _char_index(text: str, at) -> int:
    """An operation's character: an index into the text (negative from its end) or a character (its first place)."""
    if isinstance(at, str):
        if at not in text:
            raise LetteringRefused(OP_TARGET, '%r is not in %r' % (at, text))
        return text.index(at)
    index = int(at)
    if not -len(text) <= index < len(text):
        raise LetteringRefused(OP_TARGET, 'character %d is not in %r' % (index, text))
    return index % len(text)


def _glyph_at(glyphs: list, char_index: int) -> int:
    return next(k for k, g in enumerate(glyphs) if char_index in g['cluster'])


def _em(op: dict, key: str, standing: float) -> float:
    """An operation's number: its own where it gives one, else the standing value the module states."""
    if key in op and op[key] is not None:
        return float(op[key])
    return standing


def _vertical_run(geom, x_mm: float, y_mm: float, reach_mm: float):
    """The run of ink on the vertical line x = ``x_mm`` nearest ``y_mm``: ``(top, bottom)`` mm, or None."""
    from shapely.geometry import LineString, Point
    cut = geom.intersection(LineString([(x_mm, y_mm - reach_mm), (x_mm, y_mm + reach_mm)]))
    parts = [g for g in ([cut] if cut.geom_type == 'LineString' else list(getattr(cut, 'geoms', [])))
             if g.geom_type == 'LineString' and g.length > 0]
    if not parts:
        return None
    best = min(parts, key=lambda g: g.distance(Point(x_mm, y_mm)))
    ys = [c[1] for c in best.coords]
    return min(ys), max(ys)


def _inscribed(geom, point) -> float:
    """The radius (mm) of the largest circle about ``point`` inside the ink; 0 where the point is outside it."""
    from shapely.geometry import Point
    here = Point(point)
    if not geom.contains(here):
        return float(0)
    return float(geom.boundary.distance(here))


def _inscribed_start(geom, anchor, heading, em_mm: float):
    """Where a stroke leaving ``anchor`` along ``heading`` starts inside the ink: the point back along the heading,
    within ``SWASH_START_DEPTH_EM``, whose inscribed circle is widest — ``(point, radius, depth)`` — or None."""
    best = None
    steps = int(round(SWASH_START_DEPTH_EM / SWASH_PROBE_STEP_EM))
    for k in range(1, steps + 1):
        depth = k * SWASH_PROBE_STEP_EM * em_mm
        point = (anchor[0] - heading[0] * depth, anchor[1] - heading[1] * depth)
        radius = _inscribed(geom, point)
        if radius > 0.0 and (best is None or radius > best[1]):
            best = (point, radius, depth / em_mm)
    return best


def _terminal(rings: list, terminal) -> tuple:
    """The outline point furthest along a named terminal's direction (``TERMINALS``) or a given ``[dx, dy]``."""
    import numpy as np
    direction = TERMINALS[terminal] if isinstance(terminal, str) else (float(terminal[0]), float(terminal[1]))
    pts = np.vstack(rings)
    k = int(np.argmax(pts @ np.asarray(direction, dtype=float)))
    return float(pts[k][0]), float(pts[k][1])


def _em_point(anchor, offset_em, em_mm: float) -> tuple:
    """A point given in em from an anchor, y UP as a type designer reads it, on the page (mm, y down)."""
    return anchor[0] + float(offset_em[0]) * em_mm, anchor[1] - float(offset_em[1]) * em_mm


def _do_swash(op: dict, glyph: dict, em_mm: float) -> dict:
    """A swash attached at a glyph's terminal: its anchor the terminal's outline point; its start inside the ink, the
    widest inscribed circle back along the swash's first direction (``_inscribed_start``) — the stroke's own width
    there, unless ``width_em`` says — its centreline the cubic the operation gives in em from the anchor (``c1_em``,
    ``c2_em``, ``to_em``, y up), its tip ``SWASH_TIP_MM`` round."""
    geom = region(glyph['contours'])
    rings = _rings(glyph['contours'], FLATTEN_TOL_MM)
    terminal = op['terminal'] if 'terminal' in op else 'bottom_right'
    anchor = _terminal(rings, terminal)
    c1 = _em_point(anchor, op['c1_em'], em_mm)
    c2 = _em_point(anchor, op['c2_em'], em_mm)
    end = _em_point(anchor, op['to_em'], em_mm)
    heading = (c1[0] - anchor[0], c1[1] - anchor[1])
    norm = math.hypot(*heading)
    if norm == 0.0:
        raise LetteringRefused(TERMINAL_NOT_MEASURED, 'the swash at %r leaves its terminal in no direction (c1_em '
                                                      'is the anchor itself)' % glyph['chars'])
    heading = (heading[0] / norm, heading[1] / norm)
    found = _inscribed_start(geom, anchor, heading, em_mm)
    if found is None:
        raise LetteringRefused(TERMINAL_NOT_MEASURED, 'the %s terminal of %r: no ink within %s em of its outline '
                                                      'point back along the swash\'s first direction — name another '
                                                      'terminal' % (terminal, glyph['chars'], SWASH_START_DEPTH_EM))
    start, radius, depth = found
    width = _em(op, 'width_em', 2.0 * radius / em_mm) * em_mm
    tip_mm = max(SWASH_TIP_MM, _em(op, 'tip_em', SWASH_TIP_MM / em_mm) * em_mm)
    start_mm = max(tip_mm, min(width, SWASH_START_MAX_EM * em_mm))
    taper, belly = _em(op, 'taper', SWASH_TAPER), _em(op, 'belly_em', SWASH_BELLY_EM) * em_mm
    built = swash_geometry(start, c1, c2, end, start_mm=start_mm, tip_mm=tip_mm, taper=taper, belly_mm=belly)
    built.update({'anchor_mm': list(anchor), 'terminal': terminal, 'start_mm': list(start), 'start_depth_em': depth,
                  'stroke_width_mm': 2.0 * radius, 'start_width_mm': start_mm, 'tip_width_mm': tip_mm,
                  'taper': taper, 'belly_mm': belly})
    return built


def _do_bridge(op: dict, left: dict, right: dict, em_mm: float) -> dict:
    """A join the face does not have: a stroke from the left glyph's furthest ink near ``height_em`` (a bar's end, a
    terminal) to the right glyph's nearest ink near ``to_height_em`` (the same height where none is given) — as thick
    as the left glyph's own stroke where it leaves it (its vertical run there, never more than the stroke's body: the
    widest circle that fits in it within ``SWASH_START_DEPTH_EM`` back from its end, so a flared or wedged bar end
    neither pinches the bridge nor swells it — nor ``BRIDGE_MAX_EM``) unless ``thickness_em`` says; its handles a third
    of the way along, bowed by ``sag_em`` (negative: arching up), or ``c1_em`` / ``c2_em`` from its two ends (y up);
    buried a little in both."""
    import numpy as np
    y_asked = -float(op['height_em']) * em_mm
    reach = BRIDGE_SEARCH_EM * em_mm
    ys = np.linspace(y_asked - reach, y_asked + reach, 97)
    _llo, lhi = profile(_rings(left['contours'], FLATTEN_TOL_MM), ys)
    if not np.isfinite(lhi).any():
        raise LetteringRefused(BRIDGE_NOT_MEASURED, 'no ink of %r within %s em of the bridge\'s height' % (
            left['chars'], BRIDGE_SEARCH_EM))
    k = int(np.argmax(np.where(np.isfinite(lhi), lhi, -np.inf)))
    lgeom = region(left['contours'])
    bury = BRIDGE_BURY_EM * em_mm
    x_leave = float(lhi[k])
    run = _vertical_run(lgeom, x_leave - bury, float(ys[k]), 0.25 * em_mm)
    if run is None:
        raise LetteringRefused(BRIDGE_NOT_MEASURED, 'the furthest ink of %r near the bridge\'s height holds no stroke '
                                                    'to leave from' % left['chars'])
    top, bottom = run
    y_leave = (top + bottom) / 2.0
    # the stroke's body: the widest circle inside it back from its end along the bridge's own line (a circle taken at
    # the end itself is bounded by the end, and would pinch the bridge to a wire)
    body = _inscribed_start(lgeom, (x_leave, y_leave), (1.0, 0.0), em_mm)
    fits = 2.0 * body[1] if body is not None else float(0)
    measured = min(bottom - top, fits) if fits > 0.0 else bottom - top
    thickness = min(_em(op, 'thickness_em', measured / em_mm) * em_mm, BRIDGE_MAX_EM * em_mm)
    y_enter = -_em(op, 'to_height_em', -y_leave / em_mm) * em_mm
    rys = np.linspace(y_enter - reach, y_enter + reach, 97)
    rlo, _rhi = profile(_rings(right['contours'], FLATTEN_TOL_MM), rys)
    order = np.argsort(np.abs(rys - y_enter))
    enter = next(((float(rlo[i]), float(rys[i])) for i in order if np.isfinite(rlo[i])), None)
    if enter is None:
        raise LetteringRefused(BRIDGE_NOT_MEASURED, 'no ink of %r within %s em of the bridge\'s end' % (
            right['chars'], BRIDGE_SEARCH_EM))
    p0 = (x_leave - bury, y_leave)
    p3 = (enter[0] + bury, enter[1])
    sag = _em(op, 'sag_em', float(0)) * em_mm
    span = p3[0] - p0[0]
    p1 = _em_point(p0, op['c1_em'], em_mm) if 'c1_em' in op else (p0[0] + span / 3.0, p0[1] + sag)
    p2 = _em_point(p3, op['c2_em'], em_mm) if 'c2_em' in op else (p3[0] - span / 3.0, p3[1] + sag)
    built = swash_geometry(p0, p1, p2, p3, start_mm=thickness, tip_mm=thickness, taper=1.0, belly_mm=float(0))
    built.update({'leaves_mm': [x_leave, y_leave], 'enters_mm': [enter[0], enter[1]], 'thickness_mm': thickness,
                  'measured_run_mm': [top, bottom], 'inscribed_mm': fits})
    return built


def _do_overlap(op: dict, glyphs: list, k: int, em_mm: float) -> dict:
    """Two glyphs moved together until their outlines overlap by ``overlap_em`` where they come closest — so their
    contours unite under the nonzero rule — and every glyph after them with them."""
    import numpy as np
    left, right = glyphs[k], glyphs[k + 1]
    boxes = [tight_bbox(left['contours']), tight_bbox(right['contours'])]
    ys = np.linspace(min(b[1] for b in boxes), max(b[3] for b in boxes), CONTACT_SCANLINES)
    _l, lhi = profile(_rings(left['contours'], FLATTEN_TOL_MM), ys)
    rlo, _r = profile(_rings(right['contours'], FLATTEN_TOL_MM), ys)
    both = np.isfinite(lhi) & np.isfinite(rlo)
    if not both.any():
        raise LetteringRefused(BRIDGE_NOT_MEASURED, '%r and %r share no height to overlap at' % (
            left['chars'], right['chars']))
    closest = float((rlo[both] - lhi[both]).min())
    overlap = float(op['overlap_em']) * em_mm
    move = -(closest + overlap)
    for g in glyphs[k + 1:]:
        g['x_mm'] += move
        g['contours'] = _translated(g['contours'], move, 0.0)
    return {'closest_before_mm': closest, 'moved_mm': move, 'overlap_mm': overlap}


def _runs_across(geom, y_mm: float) -> list:
    """The runs of ink on the horizontal line y = ``y_mm``: ``[(x0, x1)]`` left to right."""
    from shapely.geometry import LineString
    x0, _y0, x1, _y1 = geom.bounds
    cut = geom.intersection(LineString([(x0 - 1.0, y_mm), (x1 + 1.0, y_mm)]))
    parts = [g for g in ([cut] if cut.geom_type == 'LineString' else list(getattr(cut, 'geoms', [])))
             if g.geom_type == 'LineString' and g.length > 0]
    return sorted((min(c[0] for c in g.coords), max(c[0] for c in g.coords)) for g in parts)


def stems(geom, top_mm: float, lean: float) -> list:
    """A glyph's vertical stems: the runs of ink across the band at ``STEM_HEIGHTS`` (shares of ``top_mm``), read
    upright (sheared back by ``lean``), gathered where one stands over another — a run is a stem where it holds at
    ``STEM_MIN_HEIGHTS`` heights or more. ``[{"centre_mm", "width_mm", "heights"}]`` left to right (upright x)."""
    clusters = []
    for share in STEM_HEIGHTS:
        y = -share * top_mm
        for x0, x1 in _runs_across(geom, y):
            centre, width = (x0 + x1) / 2.0 + y * lean, x1 - x0
            near = [c for c in clusters if abs(c['centre'] - centre) <= 0.5 * max(width, c['width'])
                    and share not in c['heights']]
            if near:
                c = min(near, key=lambda c: abs(c['centre'] - centre))
                n = len(c['heights'])
                c['centre'] = (c['centre'] * n + centre) / (n + 1)
                c['width'] = (c['width'] * n + width) / (n + 1)
                c['heights'].append(share)
            else:
                clusters.append({'centre': centre, 'width': width, 'heights': [share]})
    found = [{'centre_mm': c['centre'], 'width_mm': c['width'], 'heights': c['heights']}
             for c in clusters if len(c['heights']) >= STEM_MIN_HEIGHTS]
    return sorted(found, key=lambda c: c['centre_mm'])


def _do_stem(op: dict, glyphs: list, k: int, em_mm: float, bands: dict, text: str, lean: float) -> dict:
    """A ligature the face lacks, made of a shared stem: the right glyph moved (and every glyph after it) until its
    first stem stands on the left glyph's last (``stems``: runs of ink that stand over one another across the band —
    the cap band for a capital, the x-height band for a small letter): the T's stem on the N's right stem — so their
    contours unite under the nonzero rule. Refused by name where either glyph has no stem there."""
    left, right = glyphs[k], glyphs[k + 1]
    band = 'cap' if _case(text[left['cluster'][-1]]) == 'upper' else 'x'
    if bands[band] is None:
        raise LetteringRefused(BRIDGE_NOT_MEASURED, 'the face has no %s height to find a stem at' % band)
    left_stems = stems(region(left['contours']), bands[band], lean)
    right_stems = stems(region(right['contours']), bands[band], lean)
    if not left_stems or not right_stems:
        raise LetteringRefused(BRIDGE_NOT_MEASURED, '%r and %r do not both stand on a stem to share' % (
            left['chars'], right['chars']))
    mine, theirs = left_stems[-1], right_stems[0]
    move = mine['centre_mm'] - theirs['centre_mm']
    for g in glyphs[k + 1:]:
        g['x_mm'] += move
        g['contours'] = _translated(g['contours'], move, 0.0)
    return {'band': band, 'lean': lean, 'left_stem': mine,
            'right_stem': dict(theirs, centre_mm=theirs['centre_mm'] + move), 'moved_mm': move}


def _do_cut(op: dict, glyph: dict, em_mm: float, glyphs: list, text: str) -> dict:
    """A shape subtracted from a glyph, on its outlines flattened at ``FLATTEN_TOL_MM`` (shapely), the glyph written
    back as LineTo contours. 'inline': a line ``width_em`` wide at ``inset_em`` inside the outline, where the stroke has
    room for it; 'slot': a bar ``width_em`` wide at ``angle_deg`` through a point (em from the glyph's origin, y up);
    'polygon': ``points_em`` from the glyph's origin, y up; 'knockout': the glyph ``by`` names (a character of the
    text, or its index) grown by ``gap_em`` — a letter cut in under its neighbour, a white line between them."""
    from shapely.affinity import rotate
    from shapely.geometry import Polygon as _Polygon
    from shapely.geometry import box
    geom = region(glyph['contours'])
    shape = op['shape'] if 'shape' in op else 'inline'
    origin = (glyph['x_mm'], 0.0)
    measured = {'shape': shape}
    if shape == 'inline':
        inset, width = float(op['inset_em']) * em_mm, float(op['width_em']) * em_mm
        core = geom.buffer(-inset, quad_segs=16)
        core = core.buffer(-width / 2.0, quad_segs=16).buffer(width / 2.0, quad_segs=16)
        # an island of core in a serif's bracket would draw a speck of a loop: only cores of a stroke's size are kept
        from shapely.ops import unary_union
        kept = [g for g in _polygons(core) if g.area >= INLINE_MIN_ISLAND_EM2 * em_mm * em_mm]
        core = unary_union(kept) if kept else _Polygon()
        cut = core.boundary.buffer(width / 2.0, quad_segs=16)
        measured.update({'inset_mm': inset, 'line_mm': width, 'rim_mm': inset - width / 2.0})
    elif shape == 'slot':
        width = float(op['width_em']) * em_mm
        cx, cy = _em_point(origin, op['through_em'], em_mm)
        reach = 2.0 * em_mm
        cut = rotate(box(cx - reach, cy - width / 2.0, cx + reach, cy + width / 2.0), -float(op['angle_deg']),
                     origin=(cx, cy))
        measured.update({'line_mm': width, 'through_mm': [cx, cy], 'angle_deg': float(op['angle_deg'])})
    elif shape == 'polygon':
        cut = _Polygon([_em_point(origin, p, em_mm) for p in op['points_em']])
        measured.update({'points_mm': [list(_em_point(origin, p, em_mm)) for p in op['points_em']]})
    elif shape == 'knockout':
        other = glyphs[_glyph_at(glyphs, _char_index(text, op['by']))]
        if other is glyph:
            raise LetteringRefused(OP_TARGET, 'a glyph is not knocked out by itself (%r)' % glyph['chars'])
        width = float(op['gap_em']) * em_mm
        cut = region(other['contours']).buffer(width, quad_segs=16)
        measured.update({'by': other['chars'], 'line_mm': width})
    else:
        raise LetteringRefused(OP_UNKNOWN, 'a cut-in shape %r is not inline, slot, polygon or knockout' % shape)
    taken = geom.intersection(cut)
    after = geom.difference(cut)
    glyph['contours'] = ring_contours(after)
    measured.update({'area_before_mm2': geom.area, 'area_cut_mm2': taken.area, 'area_after_mm2': after.area,
                     'flattened_at_mm': FLATTEN_TOL_MM, 'written_as': 'LineTo'})
    if 'line_mm' in measured:
        measured['foil_gap_ok'] = measured['line_mm'] >= FOIL_GAP_MIN_MM
    if 'rim_mm' in measured:
        measured['foil_rim_ok'] = measured['rim_mm'] >= FOIL_LINE_MIN_MM
    return measured


def _spots(geom, n: int) -> list:
    """The ``n`` largest pieces of an area: ``[[area mm2, [x0, y0, x1, y1] mm]]``."""
    pieces = sorted(_polygons(geom), key=lambda g: -g.area)[:n]
    return [[g.area, list(g.bounds)] for g in pieces]


def print_limits(geom) -> dict:
    """D-D9-3's print limits read on the drawn logotype: the area of its parts finer than a foil line
    (``FOIL_LINE_MIN_MM``: what an opening at that width takes away) and of its gaps narrower than a foil gap
    (``FOIL_GAP_MIN_MM``: what a closing at that width fills), each with its largest spots. A sharp corner and the apex
    of a wedge (an n's crotch, a serif's bracket) always give a little: a spot along a stroke is the finding."""
    thin = geom.difference(geom.buffer(-FOIL_LINE_MIN_MM / 2.0, quad_segs=8).buffer(FOIL_LINE_MIN_MM / 2.0,
                                                                                     quad_segs=8))
    closed = geom.buffer(FOIL_GAP_MIN_MM / 2.0, quad_segs=8).buffer(-FOIL_GAP_MIN_MM / 2.0, quad_segs=8)
    narrow = closed.difference(geom)
    return {'foil_line_min_mm': FOIL_LINE_MIN_MM, 'finer_than_foil_line_mm2': thin.area,
            'finest_spots': _spots(thin, PRINT_LIMIT_SPOTS), 'foil_gap_min_mm': FOIL_GAP_MIN_MM,
            'narrower_than_foil_gap_mm2': narrow.area, 'narrowest_spots': _spots(narrow, PRINT_LIMIT_SPOTS)}


def _colour(colour):
    from apps.ire.graph import Color
    if isinstance(colour, Color):
        return colour
    return Color.from_hex(str(colour))


def face_from_match(match: dict, *, weight=None) -> str:
    """The stem the D-D8-5 match names — ``concept_design_map.set_display``'s record, the one closest-face matcher — as
    ``logotype`` takes it: its ``face`` where its state is SET (at ``weight`` for a variable face: the matcher reads a
    face's default instance and names no weight); refused by name where the lettering was TRACED (no licensed face
    came close enough to set it)."""
    from apps.pipeline.services.concept_design_map import LETTERING_SET
    if match.get('state') != LETTERING_SET or not match.get('face'):
        raise LetteringRefused(MATCH_NOT_SET, 'the D-D8-5 match set no face (%s): %s' % (
            match.get('state'), match.get('why')))
    return match['face'] if weight is None else '%s@%g' % (match['face'], float(weight))


def _moved(measured: dict, dx_mm: float, dy_mm: float) -> dict:
    """An operation's measured points carried from the word's frame onto the page."""
    out = dict(measured)
    for key in ('anchor_mm', 'start_mm', 'leaves_mm', 'enters_mm', 'through_mm'):
        if key in out:
            out[key] = [out[key][0] + dx_mm, out[key][1] + dy_mm]
    for key in ('centreline', 'points_mm'):
        if key in out:
            out[key] = [[q[0] + dx_mm, q[1] + dy_mm] for q in out[key]]
    if 'measured_run_mm' in out:
        out['measured_run_mm'] = [out['measured_run_mm'][0] + dy_mm, out['measured_run_mm'][1] + dy_mm]
    return out


def logotype(text: str, face, ops, *, cap_mm: float, x_mm: float, top_mm: float, colour, finishes,
             features=DEFAULT_FEATURES, kerning: str = 'optical', upper: bool = False, match=None) -> tuple:
    """The name as lettering: ``(Group, record)``.

    ``face``: a stem ('PlayfairDisplay-Italic[wght]@700'; ``face_from_match`` turns the D-D8-5 match into one) —
    licensed and granted, or refused by name — or ``resolve_face``'s record. ``ops``: a list of operations, each a
    dict — ``{"op": "alternate", "at", "feature"}``; ``{"op": "join", "kind": "bridge", "after", "height_em",
    ["to_height_em", "thickness_em", "sag_em", "c1_em", "c2_em"]}``; ``{"op": "join", "kind": "overlap", "after",
    "overlap_em"}``; ``{"op": "join", "kind": "stem", "after"}`` (the next glyph's first stem stood on this one's last);
    ``{"op": "cut_in", "at", "shape": "inline", "inset_em", "width_em"}``; ``{"op": "cut_in", "at", "shape": "slot",
    "width_em", "through_em", "angle_deg"}``; ``{"op": "cut_in", "at", "shape": "polygon", "points_em"}``; ``{"op":
    "cut_in", "at", "shape": "knockout", "by", "gap_em"}`` (the glyph cut in under the letter ``by`` names, a white line
    ``gap_em`` wide between them); ``{"op": "swash", "at", "terminal", "c1_em", "c2_em", "to_em", ["width_em",
    "tip_em", "taper", "belly_em"]}`` — a bridge or a swash may name its own ``colour`` and ``finishes`` (its own path,
    trapped onto the letters) — ``at``, ``after`` and ``by`` a character's index in ``text`` (negative from its end) or
    the character itself (its first place); every offset in em, y up, from the glyph's terminal (a swash), a bridge's
    ends, or the glyph's origin (a cut). Joins that move letters (overlap, stem) apply first, then the cut-ins, then
    the bridges and swashes. ``cap_mm``: the
    capital's outline top above the baseline (the first capital's, measured on the glyph drawn). ``x_mm``: the left of
    the logotype's ink; ``top_mm``: its cap line (the capital's top). ``colour``: a Color or '#RRGGBB'. ``finishes``:
    the letters' own (a foil puts them on its plate; a stroke naming its own ``colour`` / ``finishes`` is its own
    path). ``upper``: the words drawn in capitals — ``at`` and ``after`` then name the capitals drawn — while the
    group's ``actual_text`` keeps the words as given, as a run's ``text_case`` keeps its record's words. ``match``: the
    D-D8-5 match's record, kept beside the face it named.

    The Group is named LOGOTYPE, role typography, ``actual_text`` = ``text``; it holds ONE compound path at nonzero
    winding. The record (``SCHEMA``): the face (family, stem, file, sha256, licence, grant), the operations as applied
    with what each measured (points on the page, mm), the cap height measured back from the drawn capital's outline,
    the ink box, the width, the glyphs used, the kerning, D-D9-3's print limits."""
    from apps.ire.graph import Finish, Group, Path as VPath, SolidFill
    if isinstance(face, str):
        face = resolve_face(face)
    ops = [dict(o) for o in ops]
    for o in ops:
        if o.get('op') not in OPS:
            raise LetteringRefused(OP_UNKNOWN, 'operation %r is not one of %s' % (o.get('op'), ', '.join(OPS)))
        if o['op'] == 'join' and o.get('kind') not in JOINS:
            raise LetteringRefused(OP_UNKNOWN, 'a join is %s, not %r' % (', '.join(JOINS), o.get('kind')))
        if o['op'] == 'join' and o['kind'] == 'overlap' and not float(o['overlap_em']) > 0:
            raise LetteringRefused(OP_PARAMETER, 'an overlap of %r em unites nothing: overlap_em must be above 0' % o['overlap_em'])
        if o['op'] == 'swash' and ('belly_em' in o and float(o['belly_em']) < 0 or 'taper' in o and not float(o['taper']) > 0):
            raise LetteringRefused(OP_PARAMETER, 'a swash needs belly_em >= 0 and taper > 0 (its width never under its tip)')
    words, text = text, (text.upper() if upper else text)
    alternates = {}
    for o in ops:
        if o['op'] == 'alternate':
            ci = _char_index(text, o['at'])
            if ci in alternates:
                raise LetteringRefused(OP_PARAMETER, 'two alternates (%s, %s) on one character %r' % (alternates[ci], o['feature'], text[ci]))
            alternates[ci] = o['feature']
    setting = set_word(text, face, cap_mm=cap_mm, features=features, alternates=alternates, kerning=kerning)
    glyphs = setting['glyphs']
    em_mm = setting['em_mm']
    bands = {'x': setting['x_height_mm'], 'cap': setting['cap_height_mm']}
    applied, extra = [], []
    for o in ops:
        if o['op'] == 'alternate':
            ci = _char_index(text, o['at'])
            g = glyphs[_glyph_at(glyphs, ci)]
            if g['space']:
                raise LetteringRefused(OP_TARGET, 'an alternate cannot stand on a space')
            hit = [sub for sub in g['substitutions'] if sub['feature'] == o['feature']]
            applied.append(dict(o, applied=bool(hit), glyph=g['glyph'],
                                why=None if hit else 'the face has no %s alternate for this glyph' % o['feature']))
    # the spacing joins first (they move letters), then the cuts (on letters where they stand), then the strokes
    for o in ops:
        if o['op'] == 'join' and o['kind'] in ('overlap', 'stem'):
            k = _glyph_at(glyphs, _char_index(text, o['after']))
            if k + 1 >= len(glyphs) or glyphs[k + 1]['space']:
                raise LetteringRefused(OP_TARGET, 'no letter follows %r to join' % glyphs[k]['chars'])
            done = (_do_overlap(o, glyphs, k, em_mm) if o['kind'] == 'overlap'
                    else _do_stem(o, glyphs, k, em_mm, bands, text, _lean(face)))
            applied.append(dict(o, applied=True, pair=glyphs[k]['chars'] + glyphs[k + 1]['chars'], measured=done))
    for o in ops:
        if o['op'] == 'cut_in':
            k = _glyph_at(glyphs, _char_index(text, o['at']))
            if glyphs[k]['space']:
                raise LetteringRefused(OP_TARGET, 'a cut cannot be made in a space')
            measured = _do_cut(o, glyphs[k], em_mm, glyphs, text)
            # applied only where it took ink: a cut that removes nothing is said, never claimed, and its foil
            # flags read nothing
            cut = measured['area_cut_mm2'] > 1e-9
            if not cut:
                measured.update({flag: None for flag in ('foil_gap_ok', 'foil_rim_ok') if flag in measured})
            applied.append(dict(o, applied=cut, glyph=glyphs[k]['glyph'], measured=measured,
                                **({} if cut else {'why': 'the cut meets no ink of this glyph'})))
    regions = {}

    def glyph_region(j):
        if j not in regions:
            regions[j] = region(glyphs[j]['contours'])
        return regions[j]

    def clearance(outline, own: tuple) -> dict:
        """How far an engine-drawn shape stands from the letters it is not attached to (nor they to its own): the
        least distance (mm, 0 where it touches) and the letters it touches — a foil gap is at least
        ``FOIL_GAP_MIN_MM``."""
        shape = region(outline)
        united = set(own)
        for j in own:
            for i, g in enumerate(glyphs):
                if not g['space'] and i not in united and glyph_region(i).distance(glyph_region(j)) <= 1e-6:
                    united.add(i)
        least, touches = math.inf, []
        for j, g in enumerate(glyphs):
            if j in united or g['space']:
                continue
            d = float(shape.distance(glyph_region(j)))
            least = min(least, d)
            if d <= 1e-6:
                touches.append(g['chars'])
        return {'clear_of_others_mm': least, 'touches': touches,
                'foil_gap_ok': not touches and least >= FOIL_GAP_MIN_MM}

    def stroke(o, built, own: tuple, name: str) -> dict:
        """An engine-drawn stroke into the logotype: in the letters' own paint, or — where the operation names its own
        colour or finishes — on its own path, cut back to the letters' edge but for a trap of
        ``SEPARATE_PAINT_TRAP_MM`` running onto them, so the two paints meet with no board between."""
        if 'colour' not in o and 'finishes' not in o:
            extra.append({'contours': built['outline'], 'paint': None})
            return {'paint': 'the letters\''}
        from shapely.ops import unary_union
        letters = unary_union([glyph_region(j).buffer(-SEPARATE_PAINT_TRAP_MM, quad_segs=8) for j in own])
        cut = region(built['outline']).difference(letters)
        extra.append({'contours': ring_contours(cut), 'name': name,
                      'paint': {'colour': o['colour'] if 'colour' in o else colour,
                                'finishes': list(o['finishes']) if 'finishes' in o else []}})
        return {'paint': 'its own', 'trap_mm': SEPARATE_PAINT_TRAP_MM, 'own_area_mm2': cut.area}

    for o in ops:
        if o['op'] == 'join' and o['kind'] == 'bridge':
            k = _glyph_at(glyphs, _char_index(text, o['after']))
            if k + 1 >= len(glyphs) or glyphs[k + 1]['space']:
                raise LetteringRefused(OP_TARGET, 'no letter follows %r to bridge to' % glyphs[k]['chars'])
            built = _do_bridge(o, glyphs[k], glyphs[k + 1], em_mm)
            measured = {key: built[key] for key in ('centreline', 'leaves_mm', 'enters_mm', 'thickness_mm',
                                                    'measured_run_mm', 'inscribed_mm', 'area_mm2')}
            measured.update(clearance(built['outline'], (k, k + 1)))
            measured.update(stroke(o, built, (k, k + 1), 'logotype-bridge-%s%s' % (
                glyphs[k]['chars'], glyphs[k + 1]['chars'])))
            applied.append(dict(o, applied=True, pair=glyphs[k]['chars'] + glyphs[k + 1]['chars'], measured=measured))
    for o in ops:
        if o['op'] == 'swash':
            k = _glyph_at(glyphs, _char_index(text, o['at']))
            if glyphs[k]['space']:
                raise LetteringRefused(OP_TARGET, 'a swash cannot leave a space')
            built = _do_swash(o, glyphs[k], em_mm)
            measured = {key: built[key] for key in (
                'centreline', 'anchor_mm', 'terminal', 'start_mm', 'start_depth_em', 'stroke_width_mm',
                'start_width_mm', 'tip_width_mm', 'min_width_mm', 'taper', 'belly_mm', 'area_mm2')}
            measured.update(clearance(built['outline'], (k,)))
            measured.update(stroke(o, built, (k,), 'logotype-swash-%s' % glyphs[k]['chars']))
            applied.append(dict(o, applied=True, glyph=glyphs[k]['glyph'], measured=measured))
    letters = [c for g in glyphs for c in g['contours']]
    shared = [c for e in extra if e['paint'] is None for c in e['contours']]
    painted = [e for e in extra if e['paint'] is not None]
    every = letters + shared + [c for e in painted for c in e['contours']]
    if not letters:
        raise LetteringRefused(GLYPH_MISSING, '%r draws no ink in %s' % (text, face['stem']))
    x0, _y0, _x1, _y1 = tight_bbox(every)
    reference = setting['cap_reference']
    capital = glyphs[_glyph_at(glyphs, reference['char_index'])] if reference['in_text'] else None
    cap_top = tight_bbox(capital['contours'])[1] if capital is not None else -cap_mm
    dx, dy = x_mm - x0, top_mm - cap_top
    letters, shared = _translated(letters, dx, dy), _translated(shared, dx, dy)
    painted = [dict(e, contours=_translated(e['contours'], dx, dy)) for e in painted]
    every = letters + shared + [c for e in painted for c in e['contours']]
    ink = tight_bbox(every)
    baseline = dy
    if capital is not None:
        measured_cap = baseline - tight_bbox(_translated(capital['contours'], dx, dy))[1]
        measured_on = {'char': reference['char'], 'glyph': reference['glyph'],
                       'how': "the drawn capital's outline top (its curves' extremes) above the baseline"}
    else:
        measured_cap = reference['top_fu'] * setting['scale_mm_per_unit']
        measured_on = {'char': reference['char'], 'glyph': reference['glyph'],
                       'how': "the face's own H outline top (BoundsPen): the text holds no capital"}
    applied = [dict(o, measured=_moved(o['measured'], dx, dy)) if 'measured' in o else o for o in applied]
    drawn = region(every)
    children = [VPath(name='logotype-outlines', segments=graph_segments(letters + shared),
                      fill=SolidFill(color=_colour(colour)), fill_rule='nonzero', finishes=list(finishes))]
    for e in painted:
        children.append(VPath(name=e['name'], segments=graph_segments(e['contours']),
                              fill=SolidFill(color=_colour(e['paint']['colour'])), fill_rule='nonzero',
                              finishes=[f if isinstance(f, Finish) else Finish(**f) for f in e['paint']['finishes']]))
    group = Group(name=GROUP_NAME, role='typography', children=children, actual_text=words)
    record = {
        'schema': SCHEMA, 'text': words, 'drawn_text': text,
        'face': {k: face[k] for k in ('family', 'stem', 'stem_text', 'postscript', 'weight', 'weight_named',
                                      'weight_class', 'path', 'granted_path', 'sha256', 'drawn_sha256', 'instance',
                                      'origin', 'outlines', 'licence', 'licence_evidence', 'grant')},
        'match': match,
        'em_mm': em_mm, 'cap_mm_asked': cap_mm, 'cap_mm_measured': measured_cap, 'cap_measured_on': measured_on,
        'x_height_mm': setting['x_height_mm'], 'baseline_mm': baseline, 'cap_line_mm': top_mm,
        'box_mm': list(ink), 'width_mm': ink[2] - ink[0], 'height_mm': ink[3] - ink[1],
        'glyphs': [{'chars': g['chars'], 'glyph': g['glyph'], 'x_mm': g['x_mm'] + dx, 'advance_mm': g['advance_mm'],
                    'kern_mm': g['kern_mm'], 'optical_mm': g['optical_mm'], 'substitutions': g['substitutions']}
                   for g in glyphs],
        'features': setting['features'], 'contextual_not_applied': setting['contextual_not_applied'],
        'kerning': {'mode': kerning, 'optical': setting['optical']},
        'ops': applied, 'print_limits': print_limits(drawn), 'ink_area_mm2': drawn.area,
        'paths': [{'name': c.name, 'contours': sum(1 for sg in c.segments if sg.op == 'M'), 'fill_rule': 'nonzero',
                   'colour': c.fill.color.to_hex(), 'finishes': [f.model_dump() for f in c.finishes]}
                  for c in children],
        'outer_sign': OUTER_SIGN, 'actual_text': words, 'never_traced': NEVER_TRACED,
    }
    return group, record


def extracted_text(pdf_path, page_index: int) -> str:
    """A page's text as PyMuPDF extracts it with vectors collected — the reading in which a logotype's ActualText span
    over its outlines comes back as its words (the default extraction drops a span over vector content)."""
    import fitz
    with fitz.open(str(pdf_path)) as pdf:
        return pdf[page_index].get_text('text', flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_COLLECT_VECTORS)


def default_extracted_text(pdf_path, page_index: int) -> str:
    """A page's text as PyMuPDF extracts it by default (``page.get_text()``, no flags): live text only — kept beside
    ``extracted_text`` in the specimen's record, so what a default reader sees of a logotype is on file, not assumed."""
    import fitz
    with fitz.open(str(pdf_path)) as pdf:
        return pdf[page_index].get_text()


def record_json(record: dict) -> str:
    """A record as JSON (tuples as lists, numbers as they are)."""
    return json.dumps(record, ensure_ascii=False, indent=1, default=list)


# =====================================================================================================================
# The specimen: three licensed display faces, each lettered, emitted and rasterised for a look
# =====================================================================================================================

#: the lid (190 x 120 mm) and its working scale: 1536 px across (about 8.08 px/mm)
SPECIMEN_PAGE_MM = (190.0, 120.0)
SPECIMEN_LID_PX = 1536
#: a detail render this many times the lid's working scale; the engine's file rasterised at this many times it first
SPECIMEN_DETAIL = 3
SPECIMEN_SUPERSAMPLE = 4
SPECIMEN_CAP_MM = 11.0
SPECIMEN_WORDS = 'Enchanted Rose'
SPECIMEN_GROUND = '#F5EDE3'
SPECIMEN_INK = '#3A1A2B'
SPECIMEN_CAPTION_INK = '#7A6A70'
SPECIMEN_CAPTION_PT = 6.5
#: each row a lettering plan of the Day 9 directions (docs/audit/day-9/directions/*.json, "lettering"), in its own
#: licensed face — the faces prove the operations; a build letters in the face its spec names: A-1's inscriptional
#: capitals with the N and T sharing a stem (the N's point, which dips below the baseline, cut at it where the T's foot
#: stands); B-2's fat didone with the R cut in under the o; C-2's book roman with the t's bar drawn on into the e (a
#: bridge as thick as the bar's body) and the R's own long-legged alternate drawn out in gold foil. Between them every
#: join (stem, overlap, bridge), two cut-ins (polygon, knockout), a swash in the letters' paint and one in its own foil,
#: and a stylistic alternate from the face's GSUB.
SPECIMEN_ROWS = (
    {'face': 'Cinzel[wght]@700', 'cap_mm': 9.0, 'upper': True,
     'caption': ('A-1 - Cinzel 700 capitals: the N and T share a stem (the N\'s point cut at the baseline), the R\'s '
                 'leg drawn out under OSE, optical kerning'),
     'ops': [{'op': 'join', 'kind': 'stem', 'after': 5},
             {'op': 'cut_in', 'at': 5, 'shape': 'polygon',
              'points_em': [[0.55, 0.0], [0.95, 0.0], [0.95, -0.06], [0.55, -0.06]]},
             {'op': 'swash', 'at': 'R', 'terminal': 'bottom_right', 'c1_em': [0.2, -0.06], 'c2_em': [1.0, -0.22],
              'to_em': [2.2, -0.1]}]},
    {'face': 'AbrilFatface-Regular', 'cap_mm': 10.0,
     'caption': ('B-2 - Abril Fatface: the R\'s leg cut in under the o, a sharp terminal drawn from the final e, '
                 'optical kerning'),
     'ops': [{'op': 'join', 'kind': 'overlap', 'after': 'R', 'overlap_em': 0.05},
             {'op': 'cut_in', 'at': 'R', 'shape': 'knockout', 'by': 'o', 'gap_em': 0.018},
             {'op': 'swash', 'at': -1, 'terminal': 'bottom_right', 'c1_em': [0.1, 0.02], 'c2_em': [0.24, 0.08],
              'to_em': [0.34, 0.2], 'belly_em': 0.0}]},
    {'face': 'CormorantGaramond[wght]@700', 'cap_mm': 10.0,
     'caption': ('C-2 - Cormorant Garamond 700: the t\'s bar drawn on into the e, its own long-legged R.ss01 drawn '
                 'out in gold foil on the ink, optical kerning'),
     'ops': [{'op': 'alternate', 'at': 'R', 'feature': 'ss01'},
             {'op': 'join', 'kind': 'bridge', 'after': 't', 'height_em': 0.36},
             {'op': 'swash', 'at': 'R', 'terminal': 'bottom_right', 'c1_em': [0.12, -0.2], 'c2_em': [0.8, -0.36],
              'to_em': [1.7, -0.18], 'colour': '#B8913E',
              'finishes': [{'kind': 'foil', 'plate': 'FOIL_GOLD'}]}]},
)


def specimen(out_dir, *, rows=SPECIMEN_ROWS, cap_mm: float = SPECIMEN_CAP_MM) -> dict:
    """The lettering specimen: each row's logotype on one lid-sized sheet (190 x 120 mm), centred, its caption below —
    emitted through the engine (``lettering-specimen.ai``), rasterised at the lid's working scale
    (``lettering-specimen.png``, 1536 px across) and at ``SPECIMEN_DETAIL`` times it
    (``lettering-specimen-detail.png``),
    each row read back by OCR (tesseract, project tessdata) and the drawn copy by PyMuPDF; the records in
    ``lettering-specimen.json``. $0: nothing leaves the machine."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group, Rect, SolidFill, TextRun
    from apps.ire.rasterize import pdf_to_png
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    page_w, page_h = SPECIMEN_PAGE_MM
    band = page_h / len(rows)
    children = [Rect(name='ground', x=0.0, y=0.0, w=page_w, h=page_h, fill=SolidFill(color=_colour(SPECIMEN_GROUND)))]
    records = []
    for i, row in enumerate(rows):
        features = row['features'] if 'features' in row else DEFAULT_FEATURES
        cap = row['cap_mm'] if 'cap_mm' in row else cap_mm
        upper = bool(row['upper']) if 'upper' in row else False
        top = i * band + 0.22 * band
        _probe, measured = logotype(SPECIMEN_WORDS, row['face'], row['ops'], cap_mm=cap, x_mm=0.0, top_mm=top,
                                    colour=SPECIMEN_INK, finishes=[], features=features, upper=upper)
        left = (page_w - measured['width_mm']) / 2.0
        group, record = logotype(SPECIMEN_WORDS, row['face'], row['ops'], cap_mm=cap, x_mm=left, top_mm=top,
                                 colour=SPECIMEN_INK, finishes=[], features=features, upper=upper)
        group.name = '%s %d' % (GROUP_NAME, i + 1)
        children.append(group)
        children.append(TextRun(name='caption-%d' % (i + 1), text=row['caption'], x=page_w / 2.0,
                                y=(i + 1) * band - 0.09 * band, size_pt=SPECIMEN_CAPTION_PT,
                                color=_colour(SPECIMEN_CAPTION_INK), font='caption', align='center'))
        records.append(record)
    doc = Document(page_w=page_w, page_h=page_h, title='Enchanted Rose - lettering specimen (D-D9-5)',
                   metadata={'typography_surface': 'apps/ire/lettering.py::specimen'},
                   root=Group(name='root', role='artwork', children=children))
    ai = out_dir / 'lettering-specimen.ai'
    emit_pdf_ai(doc, str(ai))
    # as the truthful build renders a lid: the engine's file rasterised at 4 x (a whole dpi), brought down by Lanczos
    # to the lid's working scale — and to the detail's
    from PIL import Image as PILImage
    lid_px = (SPECIMEN_LID_PX, int(round(SPECIMEN_LID_PX * page_h / page_w)))
    big_dpi = int(round(SPECIMEN_LID_PX * SPECIMEN_SUPERSAMPLE / (page_w / 25.4)))
    png, detail = out_dir / 'lettering-specimen.png', out_dir / 'lettering-specimen-detail.png'
    big = out_dir / 'lettering-specimen-render.tmp.png'
    if not pdf_to_png(ai, big, dpi=big_dpi):
        raise RuntimeError('the specimen did not rasterise at %d dpi' % big_dpi)
    try:
        with PILImage.open(big) as im:
            rgb = im.convert('RGB')
            rgb.resize(lid_px, PILImage.LANCZOS).save(png)
            rgb.resize((lid_px[0] * SPECIMEN_DETAIL, lid_px[1] * SPECIMEN_DETAIL), PILImage.LANCZOS).save(detail)
    finally:
        big.unlink()
    px_per_mm = lid_px[0] / page_w
    reads = _specimen_reads(png, records, px_per_mm)
    out = {'schema': SPECIMEN_SCHEMA, 'decision': 'D-D9-5', 'page_mm': [page_w, page_h], 'cap_mm': cap_mm,
           'lid_px': list(lid_px), 'px_per_mm': px_per_mm, 'rendered_dpi': big_dpi,
           'detail_px_per_mm': px_per_mm * SPECIMEN_DETAIL,
           'files': {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                     for name, path in (('ai', ai), ('png', png), ('detail_png', detail))},
           'drawn_copy': extracted_text(ai, 0),
           'drawn_copy_how': 'PyMuPDF page.get_text("text", flags=TEXTFLAGS_TEXT | TEXT_COLLECT_VECTORS)',
           'default_extraction': default_extracted_text(ai, 0),
           'default_extraction_how': 'PyMuPDF page.get_text() (no flags): live text only',
           'rows': [dict(r, ocr=o) for r, o in zip(records, reads)], 'cost_usd': 0.0}
    (out_dir / 'lettering-specimen.json').write_text(record_json(out) + '\n', encoding='utf-8')
    return out


def _specimen_reads(png, records, px_per_mm: float) -> list:
    """Each row's logotype as tesseract reads it on the lid-scale render: its words, and whether 'Enchanted' and 'Rose'
    read (``_near``: exact, or one letter off on a long word); the failure named where OCR fails."""
    import tempfile

    from PIL import Image as PILImage

    out = []
    px = px_per_mm
    with PILImage.open(png) as im, tempfile.TemporaryDirectory() as tmp:
        for i, rec in enumerate(records):
            x0, y0, x1, y1 = rec['box_mm']
            pad = 3.0
            crop = im.crop((max(0, int((x0 - pad) * px)), max(0, int((y0 - pad) * px)),
                            min(im.width, int((x1 + pad) * px)), min(im.height, int((y1 + pad) * px))))
            path = Path(tmp) / ('row-%d.png' % i)
            crop.convert('L').save(path)
            try:
                words = ocr_words(path, psm=7)
            except (OCRFailed, OSError) as failed:              # a failed read is recorded, never "no words"
                out.append({'ocr_failed': '%s: %s' % (type(failed).__name__, failed)})
                continue
            texts = [t for t, _c, _b in words]
            out.append({'words': [[t, round(c, 1)] for t, c, _b in words],
                        'reads': {w: any(_near(t, w) for t in texts) for w in ('Enchanted', 'Rose')},
                        'psm': 7})
    return out


# --- OCR (from pipeline.services.concept_sketches, the consolidation of 2026-10-28) ------------------------------------

#: the project's tesseract data
TESSDATA = Path(__file__).resolve().parents[2] / 'var' / 'tessdata'
#: tesseract's TSV header: the twelve columns ``ocr_words`` reads by position
TSV_HEADER = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext'


class OCRFailed(RuntimeError):
    """Tesseract did not read the picture (a non-zero exit, or no TSV header): no word was read at all, which is never
    "no copy found"."""


def ocr_words(png, *, lang='eng', psm=11) -> list:
    """Tesseract's words on ``png`` (project tessdata): [(text, confidence, (x0, y0, x1, y1) px)]. Raises ``OCRFailed``
    with the exit code and stderr's tail when tesseract fails."""
    out = subprocess.run(['tesseract', str(png), '-', '--tessdata-dir', str(TESSDATA), '-l', lang, '--psm', str(psm), '-c', 'tessedit_create_tsv=1'],
                         capture_output=True, text=True, timeout=120)
    rows = out.stdout.splitlines()
    # The gate review of Day 8 (ocr_words): the exit code and the header are read. A failed read came back as no words:
    # "no copy found" on the plate proof (a false pass), "missing every word" on a sketch. Measured on tesseract 5.5.3:
    # an unreadable picture exits 1 yet prints the header; a language that does not load exits 1 and prints nothing.
    if out.returncode != 0 or rows[:1] != [TSV_HEADER]:
        tail = ' | '.join(out.stderr.strip().splitlines()[-3:])[-400:]
        raise OCRFailed('tesseract (%s, psm %s) did not read %s: exit %d, %s; stderr %r' % (
            lang, psm, Path(png).name, out.returncode, 'TSV header present' if rows[:1] == [TSV_HEADER] else 'no TSV header', tail))
    words = []
    for row in rows[1:]:
        parts = row.split('\t')
        if len(parts) == 12 and parts[11].strip() and float(parts[10]) > 0:
            x, y, w, h = (int(v) for v in parts[6:10])
            words.append((parts[11].strip(), float(parts[10]), (x, y, x + w, y + h)))
    return words


def _near(a, b):
    a, b = a.lower().strip('.,;:·'), b.lower()
    if a == b:
        return True
    if len(b) < 5 or abs(len(a) - len(b)) > 1:
        return False
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8
