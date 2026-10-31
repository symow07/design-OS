"""Day 9, direction B-2 "Damascene" — the inlay drawn by our engine (D-D9-3/4/5): one damascened inlay laid into
black lacquer. Two straps, one gold and one rose gold, each three open foil wires with printed glaze in the channels
between them, cross once on each arm of a diagonal band and pass through a ten-fold knot medallion at the lid's centre;
the band ends at each end in a cut jeweller's finial. Every wire, every crossing and every hatch line is a vector at a
measured position; nothing is traced and nothing is counted from a picture.

THE KNOT. ``folds`` petal loops (two-wire ribbons, gold and rose gold in turn) ring a boss. The two straps come in
from the band side by side, between two petals, and part: the gold strap runs round the medallion's upper half, the
rose-gold strap round its lower half, at one radius, so together they are the ring every petal loops over and under;
each strap leaves on the far side into the other arm. On each arm the two straps cross once (a flat inlay, never a
plait). The whole medallion is turned by one radial twist — a point at radius r turns by
TWIST_DEG * (1 - r / R)**2, nil at the rim and growing inward, clockwise on the lid (y down) — which curls each petal
the way the strokes of the BBROSE O curl as they run in from their tails. Nothing is traced from the logo: the curves
are superellipses, a circle and Bezier joins, turned by that twist (a homeomorphism, so it keeps every crossing). The
over-under is solved as a knot diagram: along every strand the crossings alternate, and every crossing is one strand
over and one under (``_alternate``). An under strand's wires and glaze stop together BREAK_MM short of the over strand's
outer wire, cut parallel to it. Strands that do not cross keep at least BREAK_MM apart; the petal width is the widest
of PETAL_WIDTH_SHARES that does.

THE FLOOR (>= 12 lines/cm where densest, foil lines >= 0.1 mm and gaps >= 0.2 mm). J1 asked for channels wide enough
for the colour to read at 2 m (about 1 mm); three wires with 1 mm channels are under 10 lines/cm across a strap. So the
straps keep their wide channels and the fine line lives where a jeweller puts it: each finial is a bezel-set lance-head
leaf hatched with straight foil lines HATCH_LINE_MM wide at HATCH_PITCH_MM (22 lines/cm; measured 19/cm on a 10 mm
window), every line stopping HATCH_INSET_MM short of its bezel; and the boss is an engine-turned sunburst of curved
rays turning like the petals, ranked so the rays step inward only where their pitch, measured square to the rays,
stays at least HATCH_PITCH_MM. Where two foil shapes of one metal meet at an angle, the wedge of air narrower than the
press's gap is filled (a closing of FILLET_CLOSE_MM).

There is no metallic ink: every gold element is a foil shape (FOIL_GOLD or FOIL_ROSE_GOLD); the glaze is printed
process ink; the relief is one emboss plate under the whole inlay.

Output: ``{'kind', 'marks', 'regions', 'params', 'measures'}`` (the shared Day 9 generator format). A region polygon is
``{'exterior': [(x, y), ...], 'holes': [[(x, y), ...], ...]}`` in mm on the 190 x 120 lid, y down.

``document(device, *, ground_hex)`` builds an apps/ire/graph.py Document of the marks (lacquer ground, relief, glaze,
foil on top); ``prove(device, *, ground_hex, out_dir, key, work_dir, zones)`` emits it, renders it, renders its finish
proof and measures it with the shared tools of apps/pipeline/services/finish_proof.py. $0: nothing here calls a
provider.
"""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import split, unary_union

from apps.pipeline.services.lid_devices import LID_H, LID_W, _polygons

KIND = 'b2_damascene'
LID_MM2 = LID_W * LID_H                     # 22,800 mm2

GOLD_HEX = '#C9A55C'
ROSE_GOLD_HEX = '#C99A84'
GLAZE_ROSE_HEX = '#E3A9B4'
GLAZE_LILAC_HEX = '#9B7BC0'
GLAZE_TEAL_HEX = '#5FB3AE'
GLAZE_TURNS = (GLAZE_ROSE_HEX, GLAZE_LILAC_HEX, GLAZE_TEAL_HEX)
GLAZE_BY_METAL = {'gold_foil': GLAZE_ROSE_HEX, 'rose_gold_foil': GLAZE_TEAL_HEX}
GLAZES = ('turns', 'by_strap')
FINIALS = ('pointed', 'lobed')

#: the gap an under strand leaves each side of the strand over it (the owner's floor: at least 0.6 mm)
BREAK_MM = 0.7
#: black kept between a strap's outer wire and the band's edge wire
EDGE_CLEAR_MM = 0.6
#: wires of the petal loops (a petal is a two-wire ribbon with one glaze channel)
PETAL_WIRES = 2
STRAP_WIRES = 3
#: the medallion's twist at its centre (degrees, clockwise on the lid as it runs inward)
TWIST_DEG = 80.0
#: the hatch: line, pitch (22.2 lines/cm), the air between a hatch line's end and its frame, the shortest line kept
HATCH_LINE_MM = 0.2
HATCH_PITCH_MM = 0.45
HATCH_INSET_MM = 0.3
HATCH_SHORTEST_MM = 0.8
#: the boss: its frame wire, its spokes, its solid centre, the spokes' own turn across the boss (degrees)
BOSS_WIRE_MM = 0.3
SPOKE_WIRE_MM = 0.25
BOSS_CORE_MM = 1.1
SPOKE_TURN_DEG = 30.0
#: rays in each fold of the boss (a power of two: one bold ray to the core, the rest stepping in by rank)
RAYS_PER_FOLD = 8
#: the finial: its leaf's bezel wire, the air between the band's edge wire and the bezel; the leaf follows the point
#: and ends in a hollowed base (a lance-head: its barbs LEAF_BARB_MM past the point's shoulder, its base hollowed
#: LEAF_HOLLOW_MM towards the tip on the axis), its corners rounded
BEZEL_WIRE_MM = 0.3
BEZEL_GAP_MM = 0.5
LEAF_BARB_MM = 1.0
LEAF_HOLLOW_MM = 5.5
LEAF_OGEE = 1.6
LEAF_ROUND_MM = 0.6
#: the band's outline: its concave corners filleted, its convex points blunted (a jeweller's cut point)
FILLET_MM = 2.5
POINT_ROUND_MM = 0.5
#: where the straps sit at the finial (fraction of their offset in the medallion)
COLLAR_SHARE = 0.6
#: the finial's point: its length (x the band's half width) and the power of its smoothstep profile (an ogee)
POINT_LENGTH = 1.9
POINT_POWER = 0.6
#: the lobed finial: its bead and shoulder lobes (shares of the band's half width), where the lobes sit along the
#: point (a share of its length), the fillet joining them
LOBE_BEAD = 0.36
LOBE_SIDE = 0.4
LOBE_AT = 0.62
LOBE_NECK = 0.3
LOBE_FILLET_MM = 0.9
#: the boss's radius as a share of the medallion's
BOSS_SHARE = 0.26
#: the petals: their width across (centreline), their egg (fuller outward), how far they loop past the strap ring
PETAL_WIDTH_SHARES = (0.23, 0.22, 0.21, 0.2, 0.19, 0.18)
PETAL_EGG = 0.25
#: the petal's superellipse exponent (2: an ellipse; more: blunter ends, so its inner wire never kinks)
PETAL_ROUND = 2.3
#: where the petals sit round the ring (a share of one fold's angle from the band's axis)
PETAL_PHASE = 0.5
#: each petal's lean off its radius before the twist (degrees; the twist then curls it further the same way)
PETAL_LEAN_DEG = 0.0
LOOP_OUT_MM = 2.4
LOOP_IN_MM = 3.0
#: the straps' offset from the axis as they enter the medallion (side by side, between the two petals either side of
#: the axis), where their bend begins (this far outside the petal ring), the angle from the axis at which they meet the ring, the
#: run over which they finish crossing each other on the arm, and the bend's handle
ENTRY_MM = 2.1
JOIN_OUT_MM = 0.0
JOIN_DEG = 40.0
JOIN_RUN_MM = 3.0
JOIN_HANDLE = 0.45
#: the closing that fills a too-narrow wedge of air between two foil shapes of one metal, and the least fillet kept
FILLET_CLOSE_MM = 0.12
FILLET_LEAST_MM2 = 0.001
#: the sampling of every curve
STEP_MM = 0.08
#: a wire piece shorter than this is dropped (no foil crumb)
SHORTEST_WIRE_MM = 0.5
#: the petal ring: air kept inside it (to the boss) and outside it (to the medallion's edge wire)
RING_AIR_MM = 1.0


# =====================================================================================================================
# Small geometry
# =====================================================================================================================

def _resample(points, *, closed):
    """A polyline resampled every STEP_MM along its length (closed: the ring, without repeating its first point)."""
    pts = np.asarray(points, dtype=float)
    if closed:
        pts = np.vstack([pts, pts[:1]])
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(int(math.ceil(s[-1] / STEP_MM)), 8)
    t = np.linspace(0.0, s[-1], n + 1)
    out = np.column_stack([np.interp(t, s, pts[:, 0]), np.interp(t, s, pts[:, 1])])
    return out[:-1] if closed else out


def _normals(pts, *, closed):
    """Unit normals (left of travel, y down) of a resampled polyline."""
    if closed:
        d = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
    else:
        d = np.gradient(pts, axis=0)
    d /= np.hypot(d[:, 0], d[:, 1])[:, None]
    return np.column_stack([d[:, 1], -d[:, 0]])


def _offset(pts, normals, by):
    return pts + by * normals


def _twist(points, centre, radius_mm, twist_deg):
    """The medallion's twist: a point at radius r < R turns by twist * (1 - r/R)**2 about the centre."""
    p = np.asarray(points, dtype=float) - centre
    r = np.hypot(p[:, 0], p[:, 1])
    k = np.clip(1.0 - r / radius_mm, 0.0, None) ** 2
    a = np.radians(twist_deg) * k
    c, s = np.cos(a), np.sin(a)
    return np.column_stack([c * p[:, 0] - s * p[:, 1], s * p[:, 0] + c * p[:, 1]]) + centre


def _ring_geom(geom):
    """A polygon as {'exterior', 'holes'}."""
    return {'exterior': [(round(x, 4), round(y, 4)) for x, y in geom.exterior.coords],
            'holes': [[(round(x, 4), round(y, 4)) for x, y in ring.coords] for ring in geom.interiors]}


def _without_holes(geom):
    """Every polygon of ``geom`` cut, where it has holes, into hole-free pieces (a mark is one ring)."""
    out = []
    todo = list(_polygons(geom))
    while todo:
        poly = todo.pop()
        if poly.area < 1e-4:
            continue
        if not poly.interiors:
            out.append(poly)
            continue
        hole = Polygon(poly.interiors[0])
        cx = hole.representative_point().x
        x0, y0, x1, y1 = poly.bounds
        knife = LineString([(cx, y0 - 1.0), (cx, y1 + 1.0)])
        pieces = list(split(poly, knife).geoms)
        if len(pieces) < 2:
            raise RuntimeError('a glaze piece with a hole could not be split')
        todo.extend(p for p in pieces if p.geom_type == 'Polygon')
    return out


def _mark(points, *, width, ink, fill, closed, finishes):
    return {'points': [(round(float(x), 4), round(float(y), 4)) for x, y in points], 'closed': closed,
            'width': width, 'ink': ink, 'fill': fill, 'finishes': list(finishes)}


def _mark_geom(mark):
    """The area a mark inks."""
    if mark['width'] > 0.0:
        line = LineString(mark['points'] + ([mark['points'][0]] if mark['closed'] else []))
        return line.buffer(mark['width'] / 2.0, cap_style=2, join_style=2, mitre_limit=3.0)
    poly = Polygon(mark['points'])
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def _lines_of(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'LineString':
        return [geom]
    if geom.geom_type == 'MultiLineString':
        return list(geom.geoms)
    if geom.geom_type == 'GeometryCollection':
        return [g for part in geom.geoms for g in _lines_of(part)]
    return []


# =====================================================================================================================
# The design
# =====================================================================================================================

class _Frame:
    """The band's own frame: ``a`` along the axis from the medallion's centre (towards p1), ``v`` across it."""

    def __init__(self, p0, p1, centre):
        self.p0, self.p1 = np.asarray(p0, float), np.asarray(p1, float)
        self.c = np.asarray(centre, float)
        d = self.p1 - self.p0
        self.length = float(np.hypot(*d))
        self.u = d / self.length
        self.n = np.array([-self.u[1], self.u[0]])
        self.a0 = float(np.dot(self.p0 - self.c, self.u))
        self.a1 = float(np.dot(self.p1 - self.c, self.u))
        self.off_axis_mm = float(abs(np.dot(self.c - self.p0, self.n)))

    def world(self, a, v):
        a, v = np.asarray(a, float), np.asarray(v, float)
        return self.c + a[..., None] * self.u + v[..., None] * self.n

    def local(self, pts):
        p = np.asarray(pts, float) - self.c
        return np.column_stack([p @ self.u, p @ self.n])


def _smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _finial_outline(kind, half_mm):
    """One finial's outline in arm coordinates (s from the tip towards the medallion, v across), and where its band
    begins (s). The other side of the band is drawn by the caller."""
    if kind not in FINIALS:
        raise ValueError('finial must be one of %s; got %r' % (FINIALS, kind))
    s_band = POINT_LENGTH * half_mm
    t = np.linspace(0.0, 1.0, 240)
    h = half_mm * _smoothstep(t) ** POINT_POWER
    s = t * s_band
    upper = np.column_stack([s, h])
    lower = np.column_stack([s[::-1], -h[::-1]])
    shape = Polygon(np.vstack([lower, upper, [(s_band + 1.0, half_mm), (s_band + 1.0, -half_mm)]]))
    if kind == 'pointed':
        return shape, s_band
    # lobed: the point ends in a round bead and carries a lobe on each shoulder (a trefoil terminal), joined by
    # fillets of LOBE_FILLET_MM
    r_bead, r_lobe = LOBE_BEAD * half_mm, LOBE_SIDE * half_mm
    s_lobe, v_lobe = LOBE_AT * s_band, half_mm - r_lobe
    shape = unary_union([Point(r_bead, 0.0).buffer(r_bead, quad_segs=64),
                         Point(s_lobe, v_lobe).buffer(r_lobe, quad_segs=64),
                         Point(s_lobe, -v_lobe).buffer(r_lobe, quad_segs=64),
                         Polygon([(r_bead, -LOBE_NECK * half_mm), (s_lobe, -LOBE_NECK * half_mm),
                                  (s_lobe, LOBE_NECK * half_mm), (r_bead, LOBE_NECK * half_mm)]),
                         box(s_lobe, -half_mm, s_band + 1.0, half_mm)])
    shape = shape.buffer(LOBE_FILLET_MM, quad_segs=32).buffer(-LOBE_FILLET_MM, quad_segs=32)
    return shape, s_band


def _strand(name, metal, points, *, closed, wires, wire_mm, channel_mm):
    pts = _resample(points, closed=closed)
    half_mm = (wires - 1) * (wire_mm + channel_mm) / 2.0 + wire_mm / 2.0
    line = LineString(np.vstack([pts, pts[:1]]) if closed else pts)
    ribbon = line.buffer(half_mm, cap_style=2, join_style=1, quad_segs=16)
    return {'name': name, 'metal': metal, 'pts': pts, 'closed': closed, 'wires': wires, 'line': line,
            'half_mm': half_mm, 'ribbon': ribbon, 'glaze_half_mm': (wires - 1) * (wire_mm + channel_mm) / 2.0}


def _crossings(strands):
    """Every crossing of two strands' centrelines: where, the parameter along each, and the angle between them."""
    out = []
    for i in range(len(strands)):
        for j in range(i + 1, len(strands)):
            hit = strands[i]['line'].intersection(strands[j]['line'])
            if hit.is_empty:
                continue
            if hit.geom_type == 'Point':
                points = [hit]
            elif hit.geom_type == 'MultiPoint':
                points = list(hit.geoms)
            else:
                raise RuntimeError('strands %s and %s overlap along a run' % (strands[i]['name'], strands[j]['name']))
            for p in points:
                ti, tj = strands[i]['line'].project(p), strands[j]['line'].project(p)
                di, dj = _tangent(strands[i]['line'], ti), _tangent(strands[j]['line'], tj)
                angle = math.degrees(math.acos(min(1.0, abs(float(np.dot(di, dj))))))
                out.append({'at': (p.x, p.y), 'strands': (i, j), 't': (ti, tj), 'angle_deg': angle})
    return out


def _tangent(line, t):
    a = line.interpolate(max(t - 0.2, 0.0))
    b = line.interpolate(min(t + 0.2, line.length))
    d = np.array([b.x - a.x, b.y - a.y])
    return d / np.hypot(*d)


def _alternate(strands, crossings):
    """Over and under as a knot diagram: along every strand the crossings alternate; every crossing is one strand
    over and one under. Each strand's phase is solved from the crossings (x_i xor x_j = n_i + n_j + 1, mod 2); a
    diagram that cannot alternate is refused."""
    order = {i: [] for i in range(len(strands))}
    for k, c in enumerate(crossings):
        for side in (0, 1):
            order[c['strands'][side]].append((c['t'][side], k))
    index = {}
    for i, rows in order.items():
        rows.sort()
        if strands[i]['closed'] and len(rows) % 2:
            raise RuntimeError('closed strand %s has an odd number of crossings' % strands[i]['name'])
        for n, (_t, k) in enumerate(rows):
            index[(i, k)] = n
    edges = {i: [] for i in range(len(strands))}
    for k, c in enumerate(crossings):
        i, j = c['strands']
        want = (index[(i, k)] + index[(j, k)] + 1) % 2
        edges[i].append((j, want))
        edges[j].append((i, want))
    phase = {}
    for start in range(len(strands)):
        if start in phase:
            continue
        phase[start] = 0
        queue = deque([start])
        while queue:
            i = queue.popleft()
            for j, want in edges[i]:
                if j not in phase:
                    phase[j] = phase[i] ^ want
                    queue.append(j)
                elif phase[j] != phase[i] ^ want:
                    raise RuntimeError('the knot cannot alternate at strands %s and %s'
                                       % (strands[i]['name'], strands[j]['name']))
    for k, c in enumerate(crossings):
        i, j = c['strands']
        i_over = (index[(i, k)] + phase[i]) % 2 == 0
        c['over'], c['under'] = (i, j) if i_over else (j, i)
        c['order'] = (index[(i, k)], index[(j, k)])
    return crossings


def _bezier(b0, b1, b2, b3):
    t = np.linspace(0.0, 1.0, 400)[:, None]
    return ((1 - t) ** 3) * b0 + 3 * ((1 - t) ** 2) * t * b1 + 3 * (1 - t) * t * t * b2 + t ** 3 * b3


def _strap_path(frame, *, s_leaf, s_start, v0_mm, entry_mm, a_join, ring_mm):
    """The gold strap's centreline in the band's frame (a, v): from under the first finial's leaf at v = -v0, across
    the rose strap once (an S to v = +entry), in between the two petals either side of the band's axis, then up into
    the ring round the medallion's upper side (a Bezier meeting the circle of radius ``ring_mm``
    tangentially at JOIN_DEG from the axis), along the ring, and out the same way on the other side (the path is its
    own mirror across the medallion's centre line, a -> -a). The rose strap is its mirror across the axis (v -> -v)."""
    join = math.radians(JOIN_DEG)
    pj = np.array([-ring_mm * math.cos(join), ring_mm * math.sin(join)])
    tj = np.array([math.sin(join), math.cos(join)])
    a_start = frame.a0 + s_start
    a_s0 = frame.a0 + s_leaf + 2.5
    a_s1 = a_join - JOIN_RUN_MM
    a = np.arange(a_start, a_join, STEP_MM)
    arm = np.column_stack([a, -v0_mm + (v0_mm + entry_mm) * _smoothstep((a - a_s0) / (a_s1 - a_s0))])
    b0 = np.array([a_join, entry_mm])
    reach = float(np.hypot(*(pj - b0))) * JOIN_HANDLE
    bend = _bezier(b0, b0 + reach * np.array([1.0, 0.0]), pj - reach * tj, pj)
    th = np.arange(join, math.pi / 2.0, STEP_MM / ring_mm)
    arc = np.column_stack([-ring_mm * np.cos(th), ring_mm * np.sin(th)])
    half_path = np.vstack([arm, bend[1:], arc[1:]])
    other = np.column_stack([-half_path[::-1, 0], half_path[::-1, 1]])
    return np.vstack([half_path, other[1:]])


def damascene(*, p0_mm, p1_mm, band_mm, medallion_centre_mm, medallion_mm, folds, wire_mm, channel_mm, edge_wire_mm,
              glaze, finial):
    """The B-2 inlay (see the module's text). Refuses folds that could draw a six-pointed star (6, any multiple of 3),
    odd folds (the two metals alternate round the ring) and fewer than 8."""
    if not isinstance(folds, int) or folds % 3 == 0 or folds % 2 or folds < 8:
        raise ValueError('folds must be an even count of at least 8 and never a multiple of 3 (no six-pointed star '
                         'can be drawn); got %r' % (folds,))
    if glaze not in GLAZES:
        raise ValueError('glaze must be one of %s; got %r' % (GLAZES, glaze))
    if finial not in FINIALS:
        raise ValueError('finial must be one of %s; got %r' % (FINIALS, finial))
    for name, value, floor in (('wire_mm', wire_mm, 0.1), ('edge_wire_mm', edge_wire_mm, 0.1),
                               ('channel_mm', channel_mm, 0.2)):
        if not value >= floor:
            raise ValueError('%s must be at least %g mm (the foil limits); got %r' % (name, floor, value))
    params = {'p0_mm': tuple(p0_mm), 'p1_mm': tuple(p1_mm), 'band_mm': band_mm,
              'medallion_centre_mm': tuple(medallion_centre_mm), 'medallion_mm': medallion_mm, 'folds': folds,
              'wire_mm': wire_mm, 'channel_mm': channel_mm, 'edge_wire_mm': edge_wire_mm, 'glaze': glaze,
              'finial': finial}
    frame = _Frame(p0_mm, p1_mm, medallion_centre_mm)
    if frame.off_axis_mm > 0.5:
        raise ValueError('the medallion centre is %.2f mm off the band\'s axis' % frame.off_axis_mm)
    radius = medallion_mm / 2.0
    half = band_mm / 2.0
    pitch = wire_mm + channel_mm
    strap_half = (STRAP_WIRES - 1) * pitch / 2.0 + wire_mm / 2.0
    petal_half = (PETAL_WIRES - 1) * pitch / 2.0 + wire_mm / 2.0
    e_mm = half - edge_wire_mm - EDGE_CLEAR_MM - strap_half
    v0_mm = COLLAR_SHARE * e_mm
    boss_r = BOSS_SHARE * radius
    ring_in = boss_r + BOSS_WIRE_MM / 2.0 + RING_AIR_MM + petal_half
    ring_out = radius - edge_wire_mm - RING_AIR_MM - petal_half
    ring_mm = ring_out - petal_half - LOOP_OUT_MM - strap_half
    if ring_mm - strap_half - LOOP_IN_MM - petal_half < ring_in or ring_mm < e_mm + strap_half:
        raise ValueError('a %g mm medallion cannot hold its petals and its strap ring round a %.1f mm boss'
                         % (medallion_mm, boss_r))
    petal_mid, petal_half_len = (ring_in + ring_out) / 2.0, (ring_out - ring_in) / 2.0
    centre = frame.c

    # --- the outline: band + medallion + the two finials, filleted and its points blunted ----------------------------
    fin_shape, s_band = _finial_outline(finial, half)
    a_band_end = frame.a1 - s_band
    arm_body = Polygon([(frame.a0 + s_band, -half), (frame.a1 - s_band, -half), (frame.a1 - s_band, half),
                        (frame.a0 + s_band, half)])
    fin1 = Polygon(np.column_stack([np.asarray(fin_shape.exterior.coords)[:, 0] + frame.a0,
                                    np.asarray(fin_shape.exterior.coords)[:, 1]]))
    fin2 = Polygon(-np.asarray(fin1.exterior.coords))
    local_outline = unary_union([arm_body, fin1, fin2, Point(0.0, 0.0).buffer(radius, quad_segs=128)])
    outline = Polygon(frame.world(*np.asarray(local_outline.exterior.coords).T))
    outline = outline.buffer(FILLET_MM, quad_segs=32).buffer(-FILLET_MM, quad_segs=32)
    outline = outline.buffer(-POINT_ROUND_MM, quad_segs=32).buffer(POINT_ROUND_MM, quad_segs=32)
    if a_band_end <= radius:
        raise ValueError('the band is too short for its finials and medallion')

    # --- the finials' leaves (the hatched, bezel-set ends) -----------------------------------------------------------
    inner = outline.buffer(-(edge_wire_mm + BEZEL_GAP_MM), quad_segs=32)
    leaves = []
    for sign, a_tip in ((1.0, frame.a0), (-1.0, frame.a1)):
        v_ = np.linspace(-half - 3.0, half + 3.0, 400)
        back = s_band + LEAF_BARB_MM - LEAF_HOLLOW_MM * (1.0 - np.clip(np.abs(v_) / half, 0.0, 1.0) ** LEAF_OGEE)
        ring_ = np.vstack([[(-2.0, v_[0])], np.column_stack([back, v_]), [(-2.0, v_[-1])]])
        cap_a = a_tip + sign * ring_[:, 0]
        cap_poly = Polygon(frame.world(cap_a, ring_[:, 1] * sign))
        leaf = inner.intersection(cap_poly)
        leaf = leaf.buffer(-LEAF_ROUND_MM, quad_segs=32).buffer(LEAF_ROUND_MM, quad_segs=32)
        leaves.append(max(_polygons(leaf), key=lambda g: g.area))

    # --- the strands: two straps, then the petal loops; the medallion twisted ---------------------------------------
    a_join = -(ring_out + petal_half + strap_half + JOIN_OUT_MM)
    s_start = s_band + LEAF_BARB_MM - LEAF_HOLLOW_MM * (1.0 - min(v0_mm / half, 1.0) ** LEAF_OGEE) - 2.0
    gold_local = _strap_path(frame, s_leaf=s_band, s_start=s_start, v0_mm=v0_mm, entry_mm=ENTRY_MM, a_join=a_join, ring_mm=ring_mm)
    rose_local = np.column_stack([gold_local[:, 0], -gold_local[:, 1]])
    strands = []
    for name, metal, loc in (('strap-gold', 'gold_foil', gold_local), ('strap-rose-gold', 'rose_gold_foil', rose_local)):
        pts = _twist(frame.world(loc[:, 0], loc[:, 1]), centre, radius, TWIST_DEG)
        strands.append(_strand(name, metal, pts, closed=False, wires=STRAP_WIRES, wire_mm=wire_mm,
                               channel_mm=channel_mm))
    axis_deg = math.degrees(math.atan2(frame.u[1], frame.u[0]))
    # the widest petal (PETAL_WIDTH_SHARES of the medallion's radius, widest first) whose strands all keep BREAK_MM
    # clear wherever they do not cross
    straps = strands
    refused = ''
    for share in PETAL_WIDTH_SHARES:
        strands = list(straps)
        t = np.linspace(0.0, 2.0 * math.pi, 2400, endpoint=False)
        for k in range(folds):
            phi = math.radians(axis_deg + (k + PETAL_PHASE) * 360.0 / folds)
            radial, across = np.array([math.cos(phi), math.sin(phi)]), np.array([-math.sin(phi), math.cos(phi)])
            lean = math.radians(PETAL_LEAN_DEG)
            along = math.cos(lean) * radial + math.sin(lean) * across
            side = -math.sin(lean) * radial + math.cos(lean) * across
            x = petal_half_len * np.sign(np.cos(t)) * np.abs(np.cos(t)) ** (2.0 / PETAL_ROUND)
            y = share * radius / 2.0 * np.sign(np.sin(t)) * np.abs(np.sin(t)) ** (2.0 / PETAL_ROUND) * (1.0 + PETAL_EGG * np.cos(t))
            loop = centre + petal_mid * radial + x[:, None] * along + y[:, None] * side
            metal = 'gold_foil' if k % 2 == 0 else 'rose_gold_foil'
            strands.append(_strand('petal-%d' % k, metal, _twist(loop, centre, radius, TWIST_DEG), closed=True,
                                   wires=PETAL_WIRES, wire_mm=wire_mm, channel_mm=channel_mm))

        crossings = _alternate(strands, _crossings(strands))
        crossing_pairs = {tuple(sorted(c['strands'])) for c in crossings}
        loose = [s_['name'] for i, s_ in enumerate(strands) if not any(i in pair for pair in crossing_pairs)]
        if loose:
            raise RuntimeError('strands woven through nothing: %s' % ', '.join(loose))
        clear = []
        for i in range(len(strands)):
            for j in range(i + 1, len(strands)):
                if (i, j) not in crossing_pairs:
                    clear.append((strands[i]['ribbon'].distance(strands[j]['ribbon']), strands[i]['name'], strands[j]['name']))
        boss_edge = Point(*centre).buffer(BOSS_SHARE * radius + BOSS_WIRE_MM / 2.0)
        for s_ in strands:
            clear.append((s_['ribbon'].distance(boss_edge), s_['name'], 'boss'))
        if min(clear)[0] < BREAK_MM - 0.05:
            refused = '%s and %s come %.2f mm apart without crossing (at least %.1f mm asked)' % (
                min(clear)[1], min(clear)[2], min(clear)[0], BREAK_MM)
            continue
        break
    else:
        raise RuntimeError('no petal width keeps the knot clear: ' + refused)

    # --- cut every under strand at its crossings: its wires and its glaze stop together, BREAK_MM clear of the over
    # strand's outer wire, cut parallel to it (a flat-cut end, as a jeweller cuts an inlaid wire) -------------------
    cuts = {i: [] for i in range(len(strands))}
    for c in crossings:
        over, under = strands[c['over']], strands[c['under']]
        here = Point(c['at'])
        local = [g for g in _polygons(over['ribbon'].intersection(under['ribbon'])) if g.distance(here) < 1e-6]
        if not local:
            raise RuntimeError('no overlap found at a crossing of %s and %s' % (over['name'], under['name']))
        near = local[0].buffer(BREAK_MM + wire_mm + 0.5)
        cuts[c['under']].append(over['ribbon'].buffer(BREAK_MM, quad_segs=16, join_style=2).intersection(near))
    leaf_union = unary_union(leaves)
    for i, s in enumerate(strands):
        if not s['closed']:
            cuts[i].append(leaf_union.buffer(BREAK_MM, quad_segs=16))

    glaze_marks, glaze_parts, foil_marks = [], [], []
    turn = 0
    for i, s in enumerate(strands):
        normals = _normals(s['pts'], closed=s['closed'])
        cut = unary_union(cuts[i])
        for w in range(s['wires']):
            off = (w - (s['wires'] - 1) / 2.0) * pitch
            wp = _offset(s['pts'], normals, off)
            line = LineString(np.vstack([wp, wp[:1]]) if s['closed'] else wp)
            wire = line.buffer(wire_mm / 2.0, cap_style=2, join_style=1, quad_segs=8).difference(cut)
            for piece in _without_holes(wire):
                if piece.area >= wire_mm * SHORTEST_WIRE_MM:
                    foil_marks.append((s['metal'], _mark(list(piece.exterior.coords), width=0.0, ink=s['metal'],
                                                         fill=s['metal'], closed=True, finishes=['foil']), s['name']))
        body = s['line'].buffer(s['glaze_half_mm'], cap_style=2, join_style=1, quad_segs=16)
        pieces = _without_holes(body.difference(cut))
        pieces.sort(key=lambda g: s['line'].project(g.representative_point()))
        for n, g in enumerate(pieces):
            if g.area < 0.05:
                continue
            hex_value = GLAZE_BY_METAL[s['metal']] if glaze == 'by_strap' else GLAZE_TURNS[(turn + n) % 3]
            glaze_marks.append(_mark(list(g.exterior.coords), width=0.0, ink='ink:' + hex_value,
                                     fill='ink:' + hex_value, closed=True, finishes=[]))
            glaze_parts.append(s['name'])
        turn += 1

    # --- the edge wire round the whole inlay (gold) -----------------------------------------------------------------
    edge_line = outline.buffer(-edge_wire_mm / 2.0, quad_segs=32).exterior
    foil_marks.append(('gold_foil', _mark(list(edge_line.coords), width=edge_wire_mm, ink='gold_foil', fill=None,
                                          closed=True, finishes=['foil']), 'edge-wire'))

    # --- the finials: a bezel wire round each leaf and its hatch across ---------------------------------------------
    hatch_rows = []
    for leaf, metal in zip(leaves, ('gold_foil', 'rose_gold_foil')):
        bezel = leaf.buffer(-BEZEL_WIRE_MM / 2.0, quad_segs=32).exterior
        foil_marks.append((metal, _mark(list(bezel.coords), width=BEZEL_WIRE_MM, ink=metal, fill=None, closed=True,
                                        finishes=['foil']), 'finial-bezel'))
        room = leaf.buffer(-(BEZEL_WIRE_MM + HATCH_INSET_MM + HATCH_LINE_MM / 2.0), quad_segs=32)
        lines = _hatch(room, direction=frame.n, pitch_mm=HATCH_PITCH_MM)
        hatch_rows.append({'where': 'finial', 'lines': len(lines), 'angle_deg': _deg(frame.n)})
        for piece in lines:
            foil_marks.append((metal, _mark(list(piece.coords), width=HATCH_LINE_MM, ink=metal, fill=None,
                                            closed=False, finishes=['foil']), 'finial-hatch'))

    # --- the boss: frame wire, solid core, a ranked sunburst of curved rays turning like the petals ---------------
    boss_ring = Point(*centre).buffer(boss_r, quad_segs=128).exterior
    foil_marks.append(('gold_foil', _mark(list(boss_ring.coords), width=BOSS_WIRE_MM, ink='gold_foil', fill=None,
                                          closed=True, finishes=['foil']), 'boss-ring'))
    core = Point(*centre).buffer(BOSS_CORE_MM, quad_segs=64)
    foil_marks.append(('gold_foil', _mark(list(core.exterior.coords), width=0.0, ink='gold_foil', fill='gold_foil',
                                          closed=True, finishes=['foil']), 'boss-core'))
    # the rays: RAYS_PER_FOLD * folds curved rays turning like the petals; every 2**j-th ray reaches further in, from
    # where its neighbours of that rank are a full HATCH_PITCH_MM apart measured square to the rays (an engine-turned
    # sunburst: the pitch never closes below the press's gap); the folds' own rays, the boldest, reach the core
    n_rays = RAYS_PER_FOLD * folds
    delta = 2.0 * math.pi / n_rays
    r0, r1 = BOSS_CORE_MM - 0.15, boss_r
    rate = math.radians(SPOKE_TURN_DEG) / (r1 - r0)
    ranks = int(round(math.log2(RAYS_PER_FOLD)))
    rr = np.linspace(r0, r1, 400)
    square = rr / np.sqrt(1.0 + (rr * rate) ** 2)
    ray_rows = []
    for k in range(n_rays):
        j = 0
        while j < ranks and k % (2 ** (j + 1)) == 0:
            j += 1
        if j >= ranks:
            start = r0
        else:
            ok = square * delta * (2 ** j) >= HATCH_PITCH_MM
            if not ok.any():
                continue
            start = float(rr[np.argmax(ok)])
            if r1 - start < HATCH_SHORTEST_MM:
                continue
        r = np.linspace(start, r1, 160)
        ang = math.radians(axis_deg) + k * delta + rate * (r1 - r)
        ray = np.column_stack([centre[0] + r * np.cos(ang), centre[1] + r * np.sin(ang)])
        width = SPOKE_WIRE_MM if j >= ranks else HATCH_LINE_MM
        ray_rows.append(round(start, 3))
        foil_marks.append(('gold_foil', _mark(ray, width=width, ink='gold_foil', fill=None, closed=False,
                                              finishes=['foil']), 'boss-ray'))
    hatch_rows.append({'where': 'boss', 'rays': len(ray_rows), 'rays_per_fold': RAYS_PER_FOLD,
                       'starts_mm': sorted(set(ray_rows)),
                       'pitch_at_rim_mm': round(boss_r * 2.0 * math.pi / len(ray_rows)
                                                / math.sqrt(1.0 + (boss_r * rate) ** 2), 3)})

    # --- foil fillets: where two foil shapes of one metal meet at an angle, the wedge of air narrower than the press's
    # gap is filled (a closing of radius FILLET_CLOSE_MM), as a jeweller solders a join; nothing else moves ----------
    fillet_area = 0.0
    for metal in ('gold_foil', 'rose_gold_foil'):
        laid = unary_union([_mark_geom(m) for mm, m, _n in foil_marks if mm == metal])
        closed = laid.buffer(FILLET_CLOSE_MM, quad_segs=8).buffer(-FILLET_CLOSE_MM, quad_segs=8)
        for g in _without_holes(closed.difference(laid)):
            if g.area >= FILLET_LEAST_MM2:
                fillet_area += g.area
                foil_marks.append((metal, _mark(list(g.exterior.coords), width=0.0, ink=metal, fill=metal, closed=True,
                                                finishes=['foil']), 'fillet'))

    # --- relief: the whole inlay, one raised object ------------------------------------------------------------------
    relief_mark = _mark(list(outline.exterior.coords), width=0.0, ink='blind', fill='blind', closed=True,
                        finishes=['emboss'])
    marks = [relief_mark] + glaze_marks + [m for _metal, m, _name in foil_marks]

    # --- regions and measures ---------------------------------------------------------------------------------------
    lid = box(0.0, 0.0, LID_W, LID_H)
    ink_geoms = [_mark_geom(m) for m in glaze_marks] + [_mark_geom(m) for _metal, m, _name in foil_marks]
    footprint = unary_union([outline] + ink_geoms).intersection(lid)
    paint = lid.difference(footprint)
    inlay_ground = outline.difference(unary_union(ink_geoms))
    foil_by_metal = {metal: unary_union([_mark_geom(m) for mm, m, _n in foil_marks if mm == metal])
                     for metal in ('gold_foil', 'rose_gold_foil')}
    foil_area = unary_union(list(foil_by_metal.values())).area
    glaze_area = unary_union([_mark_geom(m) for m in glaze_marks]).area
    regions = {'paint': [_ring_geom(g) for g in _polygons(paint)],
               'relief': [_ring_geom(outline)],
               'footprint': [_ring_geom(g) for g in _polygons(footprint)],
               'inlay_ground': [_ring_geom(g) for g in _polygons(inlay_ground)],
               'medallion': [_ring_geom(Point(*centre).buffer(radius, quad_segs=64))],
               'finials': [_ring_geom(g) for g in leaves]}
    rows = []
    for c in crossings:
        rows.append({'at_mm': [round(c['at'][0], 3), round(c['at'][1], 3)],
                     'over': strands[c['over']]['name'], 'under': strands[c['under']]['name'],
                     'angle_deg': round(c['angle_deg'], 1)})
    by_strand = {}
    for i, s in enumerate(strands):
        seq = sorted((c['t'][c['strands'].index(i)], 'over' if c['over'] == i else 'under')
                     for c in crossings if i in c['strands'])
        by_strand[s['name']] = [state for _t, state in seq]
    alternates = all(all(a != b for a, b in zip(seq, seq[1:])) and
                     (not strands[i]['closed'] or not seq or seq[0] != seq[-1])
                     for i, (name, seq) in enumerate(by_strand.items()))
    strap_cross = [r_ for r_ in rows if r_['over'].startswith('strap') and r_['under'].startswith('strap')]
    measures = {
        'lid_mm2': LID_MM2,
        'twist': {'deg_at_centre': TWIST_DEG, 'law': 'turn(r) = twist * (1 - r/R)**2, clockwise on the lid (y down) '
                                                      'as it runs inward, like the BBROSE O\'s strokes'},
        'medallion': {'diameter_mm': medallion_mm, 'folds': folds, 'boss_diameter_mm': round(2.0 * boss_r, 3),
                      'petal_ring_mm': [round(ring_in - petal_half, 3), round(ring_out + petal_half, 3)],
                      'strap_ring_radius_mm': round(ring_mm, 3), 'petal_width_mm': round(share * radius, 3)},
        'straps': {'offset_in_medallion_mm': round(e_mm, 3), 'offset_at_finial_mm': round(v0_mm, 3),
                   'width_mm': round(2.0 * strap_half, 3), 'wires': STRAP_WIRES, 'wire_mm': wire_mm,
                   'channel_mm': channel_mm,
                   'lines_per_cm_across': round(STRAP_WIRES / (2.0 * strap_half) * 10.0, 2),
                   'crossings_with_each_other': len(strap_cross)},
        'clearance': {'least_mm': round(min(c_[0] for c_ in clear), 3),
                      'least_between': list(min(clear)[1:]), 'floor_mm': BREAK_MM},
        'crossings': {'count': len(rows), 'min_angle_deg': round(min(r_['angle_deg'] for r_ in rows), 1),
                      'alternate_on_every_strand': alternates, 'by_strand': by_strand, 'rows': rows,
                      'break_mm': BREAK_MM},
        'hatch': {'line_mm': HATCH_LINE_MM, 'pitch_mm': HATCH_PITCH_MM, 'gap_mm': round(HATCH_PITCH_MM - HATCH_LINE_MM, 3),
                  'lines_per_cm': round(10.0 / HATCH_PITCH_MM, 2), 'inset_mm': HATCH_INSET_MM, 'fields': hatch_rows},
        'designed_limits': {'thinnest_foil_mm': min(wire_mm, edge_wire_mm, HATCH_LINE_MM, BEZEL_WIRE_MM,
                                                    SPOKE_WIRE_MM, BOSS_WIRE_MM),
                            'narrowest_designed_gap_mm': min(channel_mm, HATCH_PITCH_MM - HATCH_LINE_MM,
                                                             HATCH_INSET_MM, BEZEL_GAP_MM, BREAK_MM)},
        'foil_ink_area_mm2': round(foil_area, 2), 'foil_ink_pct': round(100.0 * foil_area / LID_MM2, 3),
        'foil_by_metal_mm2': {k: round(g.area, 2) for k, g in foil_by_metal.items()},
        'glaze_area_mm2': round(glaze_area, 2), 'glaze_pct': round(100.0 * glaze_area / LID_MM2, 3),
        'relief_area_mm2': round(outline.area, 2), 'relief_pct': round(100.0 * outline.area / LID_MM2, 3),
        'footprint_bounds_mm': [round(v_, 3) for v_ in footprint.bounds],
        'parts': ['relief'] + glaze_parts + [name for _metal, _m, name in foil_marks],
        'marks': {'relief': 1, 'glaze': len(glaze_marks), 'foil': len(foil_marks),
                  'fillets': sum(1 for _m, _k, n in foil_marks if n == 'fillet'), 'fillet_area_mm2': round(fillet_area, 4)},
    }
    return {'kind': KIND, 'marks': marks, 'regions': regions, 'params': params, 'measures': measures}


def _deg(d):
    return round(math.degrees(math.atan2(d[1], d[0])) % 180.0, 2)


def _hatch(room, *, direction, pitch_mm):
    """Straight parallel lines along ``direction`` every ``pitch_mm`` across ``room``; runs shorter than
    HATCH_SHORTEST_MM dropped."""
    if room.is_empty:
        return []
    d = np.asarray(direction, float) / np.hypot(*direction)
    n = np.array([-d[1], d[0]])
    x0, y0, x1, y1 = room.bounds
    mid = np.array([(x0 + x1) / 2.0, (y0 + y1) / 2.0])
    reach = math.hypot(x1 - x0, y1 - y0)
    out = []
    count = int(reach / pitch_mm) + 2
    for k in range(-count, count + 1):
        o = mid + k * pitch_mm * n
        seg = LineString([tuple(o - reach * d), tuple(o + reach * d)])
        for piece in _lines_of(seg.intersection(room)):
            if piece.length >= HATCH_SHORTEST_MM:
                out.append(piece)
    return out


# =====================================================================================================================
# The engine's document, its render, its proof and its measures
# =====================================================================================================================

def document(device, *, ground_hex):
    """An apps/ire/graph.py Document of the marks: the lacquer ground, the relief (lacquer-coloured, embossed), the
    glaze inks, then every foil shape on top."""
    from apps.ire.graph import (ClosePath, Color, Document, Finish, Group, LineTo, MoveTo, Path as VPath, SolidFill,
                                Stroke)
    ground = Color.from_hex(ground_hex)
    foil = {'gold_foil': (Color.from_hex(GOLD_HEX), Finish(kind='foil', plate='FOIL_GOLD',
                                                            appearance=Color.from_hex(GOLD_HEX))),
            'rose_gold_foil': (Color.from_hex(ROSE_GOLD_HEX), Finish(kind='foil', plate='FOIL_ROSE_GOLD',
                                                                      appearance=Color.from_hex(ROSE_GOLD_HEX)))}
    emboss = Finish(kind='emboss', plate='EMBOSS')

    def segs(points, closed):
        out = [MoveTo(x=points[0][0], y=points[0][1])] + [LineTo(x=x, y=y) for x, y in points[1:]]
        return out + [ClosePath()] if closed else out

    children = [VPath(name='lacquer', fill=SolidFill(color=ground),
                      segments=segs([(0.0, 0.0), (LID_W, 0.0), (LID_W, LID_H), (0.0, LID_H)], True))]
    for i, m in enumerate(device['marks']):
        name = 'b2-%04d' % i
        if m['ink'] == 'blind':
            children.append(VPath(name=name + '-relief', fill=SolidFill(color=ground), finishes=[emboss],
                                  segments=segs(m['points'], True)))
        elif m['ink'].startswith('ink:'):
            children.append(VPath(name=name + '-glaze', fill=SolidFill(color=Color.from_hex(m['ink'][4:])),
                                  segments=segs(m['points'], True)))
        else:
            colour, finish = foil[m['ink']]
            if m['width'] > 0.0:
                children.append(VPath(name=name + '-foil', stroke=Stroke(color=colour, width_mm=m['width']),
                                      finishes=[finish], segments=segs(m['points'], m['closed'])))
            else:
                children.append(VPath(name=name + '-foil', fill=SolidFill(color=colour), finishes=[finish],
                                      segments=segs(m['points'], True)))
    return Document(page_w=LID_W, page_h=LID_H, title='B-2 damascene ornament',
                    root=Group(name='b2-damascene', role='decoration', children=children))


def zone_clearances(device, zones):
    """The distance (mm) from each text zone (lid fractions x0, y0, x1, y1) to the inlay's footprint."""
    foot = unary_union([Polygon(p['exterior'], p['holes']) for p in device['regions']['footprint']])
    return {name: round(foot.distance(box(z[0] * LID_W, z[1] * LID_H, z[2] * LID_W, z[3] * LID_H)), 3)
            for name, z in zones.items()}


def prove(device, *, ground_hex, out_dir, key, work_dir, zones, dpi):
    """Emit the Document, render page 1 at ``dpi`` (``<key>.png``), render the finish proof (``<key>-proof.png``) and
    measure with the shared tools — foil limits, coverage, line density on the foil plates read at 40 px/mm — and
    write ``<key>.json``. Returns the record."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png
    from apps.pipeline.services import finish_proof as fp
    out_dir, work_dir = Path(out_dir), Path(work_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    ai_path = work_dir / ('%s.ai' % key)
    emit_pdf_ai(document(device, ground_hex=ground_hex), str(ai_path))
    flat = out_dir / ('%s.png' % key)
    if not pdf_to_png(ai_path, flat, dpi=dpi):
        raise RuntimeError('page 1 of %s did not render' % ai_path)
    proof = fp.render_proof(flat, ai_path, out_dir / ('%s-proof.png' % key))
    limits = fp.foil_limits(ai_path)
    cover = fp.coverage(ai_path)
    px_per_mm = fp.LINE_DENSITY_PX_PER_MM
    masks = [row for row in fp.plate_masks(ai_path, px_per_mm=px_per_mm) if row['kind'] == 'foil']
    foil_mask = np.logical_or.reduce([row['mask'] for row in masks])
    density = fp.line_density(foil_mask, px_per_mm=px_per_mm)
    density.pop('map')
    record = {
        'kind': device['kind'], 'params': device['params'], 'measures': device['measures'],
        'measured': {
            'line_density_foil': density,
            'foil_limits': {'holds': limits['holds'], 'limits': limits['limits'],
                            'plates': [{k: v for k, v in row.items() if k != 'page'} for row in limits['foil_plates']],
                            'metallic_ink_plates': limits['metallic_ink_plates']},
            'coverage': cover,
            'zone_clearances_mm': zone_clearances(device, zones),
        },
        'renders': {'flat': str(flat), 'proof': str(out_dir / ('%s-proof.png' % key)), 'ai': str(ai_path),
                    'dpi': dpi, 'ground_hex': ground_hex, 'proof_sha256': proof['out']['sha256'],
                    'proof_coverage': proof['coverage']},
    }
    (out_dir / ('%s.json' % key)).write_text(json.dumps(record, indent=1, default=str))
    return record
