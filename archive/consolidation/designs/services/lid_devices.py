"""The directions' devices, drawn by our engine as vectors (Day 8 §4–§5, D-D8-4): generative and engraved line systems
are never asked of an image model. Millimetres on the 190 × 120 lid, y down. A device is ``{"kind", "marks", "params"}``
where every mark is ``{"points": [(x, y), ...], "closed": bool, "width": mm, "ink": role, "fill": role | None,
"finishes": [name, ...]}`` — clipped exactly (shapely) to the lid and out of the boxes the type lives in, so no line
of a device ever runs under a word (15 Oct, 10-13).

- ``gravure`` (A, round 2): about 130 fine wave lines in the secondary ink, pressed blind, whose spacing swells round
  an off-centre lens; one of them — the hero line — is a filled rose-gold foil shape swelling from 0.2 to 1.4 mm
  through the lens and leaving the lid by its right edge.
- ``interference`` (B, round 2): two ring families about two centres off the lid — one printed, its twin pressed
  blind — clipped to one great circular field that clears the type.
- ``astrolabe`` (C, round 2): one engraved instrument cropped by the lid's edges — graduated rim, eccentric ecliptic,
  rete, plate arcs and an eight-point wind-rose whose hatched halves are the second foil.
"""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

LID_W, LID_H = 190.0, 120.0
LID_BOX = (0.0, 0.0, LID_W, LID_H)


# --- geometry ------------------------------------------------------------------------------------------------------

def zone_mm(zone, grow=0.0):
    """A zone in lid fractions (x0, y0, x1, y1) as millimetres, grown by ``grow`` mm each side."""
    x0, y0, x1, y1 = zone
    return (x0 * LID_W - grow, y0 * LID_H - grow, x1 * LID_W + grow, y1 * LID_H + grow)


def grown(rect, by):
    x0, y0, x1, y1 = rect
    return (x0 - by, y0 - by, x1 + by, y1 + by)


def region(bounds=LID_BOX, keepouts=(), within=None):
    """Where a device may draw: ``bounds`` (and ``within``, a shapely shape) less every keep-out rectangle."""
    area = box(*bounds)
    if within is not None:
        area = area.intersection(within)
    if keepouts:
        area = area.difference(unary_union([box(*k) for k in keepouts]))
    return area


def _lines(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'LineString':
        return [list(geom.coords)]
    if geom.geom_type in ('MultiLineString', 'GeometryCollection'):
        return [c for g in geom.geoms for c in _lines(g)]
    return []


def _polygons(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return [geom]
    if geom.geom_type in ('MultiPolygon', 'GeometryCollection'):
        return [p for g in geom.geoms for p in _polygons(g)]
    return []


def clip(points, area):
    """A polyline cut into the runs that lie inside ``area``, cut exactly at its edges."""
    if len(points) < 2:
        return []
    return [run for run in _lines(LineString(points).intersection(area)) if len(run) > 1]


def clip_shape(points, area):
    """A filled outline cut to ``area``: the exterior rings of what is left."""
    shape = Polygon(points)
    if not shape.is_valid:
        shape = shape.buffer(0)
    return [list(p.exterior.coords) for p in _polygons(shape.intersection(area)) if p.area > 1e-4]


def _mark(points, *, width, ink, fill=None, closed=False, finishes=()):
    return {'points': [(float(x), float(y)) for x, y in points], 'closed': closed, 'width': width, 'ink': ink,
            'fill': fill, 'finishes': list(finishes)}


def _circle(cx, cy, r, step=0.5):
    n = max(48, int(2 * math.pi * r / step))
    t = np.linspace(0, 2 * math.pi, n + 1)
    return list(zip((cx + r * np.cos(t)).tolist(), (cy + r * np.sin(t)).tolist()))


# --- A: the gravure (round 2) -------------------------------------------------------------------------------------

def gravure(*, zone=(0.0, 0.36, 1.0, 1.0), clear_band=None, lens=(0.62, 0.64), pitch=0.6, width=0.18, hero_min=0.2,
            hero_max=1.4, hero_radius=24.0, keepouts=(), wave=38.0, amplitude=1.6, fine_wave=11.0, fine_amplitude=0.25,
            lens_radius=30.0, swell=0.35, step=0.4, phase_step=0.11, hero_finishes=('foil',), lens_weight=None,
            lens_weight_radius=None, select_before_lens=False):
    """About ``height / pitch`` wave lines across ``zone`` whose spacing swells round ``lens``. The field's edges are
    whole lines, never ragged cuts: a line that crosses the zone's top or ``clear_band`` (a (y0, y1) pair in mm) is
    left out whole, and a line that touches a keep-out is cut across the keep-out's full width — so a cleared corner's
    top edge is itself a wave. The line nearest the lens is the hero: a filled outline whose width swells from
    ``hero_min`` to ``hero_max`` round the lens, running to the lid's right edge."""
    x0, y0, x1, y1 = zone_mm(zone)
    cx, cy = lens[0] * LID_W, lens[1] * LID_H
    xs = np.arange(-2.0, LID_W + 2.0 + step, step)
    bases = np.arange(y0 - 6.0, y1 + 6.0, pitch)
    hero_index = int(np.argmin(np.abs(bases - cy)))
    lid = box(*LID_BOX)
    marks, kept = [], 0

    def centreline(i, base, lens=True):
        phase = i * phase_step
        y = (base + amplitude * np.sin(2 * math.pi * xs / wave + phase)
             + fine_amplitude * np.sin(2 * math.pi * xs / fine_wave + phase * 2.3))
        if not lens:
            return y
        r2 = (xs - cx) ** 2 + (y - cy) ** 2
        return y + swell * (y - cy) * np.exp(-r2 / lens_radius ** 2)

    for i, base in enumerate(bases):
        if i == hero_index:
            continue
        # Stage 3's repair: chosen by the line's own course before the lens bends it, so the lens bulges the field's
        # edge instead of emptying it
        sel = centreline(i, base, lens=not select_before_lens)
        y = centreline(i, base)
        if sel.min() - width / 2 < y0 or (zone[3] < 1.0 and sel.max() + width / 2 > y1):
            continue
        if clear_band is not None and sel.max() + width / 2 > clear_band[0] and sel.min() - width / 2 < clear_band[1]:
            continue
        strips = []
        for kx0, ky0, kx1, ky1 in keepouts:
            inside = (xs >= kx0) & (xs <= kx1)
            if inside.any() and ((y[inside] + width / 2 >= ky0) & (y[inside] - width / 2 <= ky1)).any():
                strips.append(box(kx0, -10.0, kx1, LID_H + 10.0))
        area = lid.difference(unary_union(strips)) if strips else lid
        kept += 1
        if lens_weight and lens_weight > width:
            # Stage 3's repair: the lens as LIGHT — each line's weight swells where it crosses it (engraver's shading),
            # drawn as a filled outline; the lines stay where they are
            lw = width + (lens_weight - width) * np.exp(-((xs - cx) ** 2 + (y - cy) ** 2) / (lens_weight_radius or lens_radius) ** 2)
            ddx, ddy = np.gradient(xs), np.gradient(y)
            nrm = np.hypot(ddx, ddy)
            ux, uy = -ddy / nrm, ddx / nrm
            upper = list(zip((xs + ux * lw / 2).tolist(), (y + uy * lw / 2).tolist()))
            lower = list(zip((xs - ux * lw / 2).tolist(), (y - uy * lw / 2).tolist()))
            for outline in clip_shape(upper + lower[::-1], area):
                marks.append(_mark(outline, width=0.0, ink='secondary', fill='secondary', closed=True, finishes=('deboss',)))
            continue
        for run in clip(list(zip(xs.tolist(), y.tolist())), area):
            marks.append(_mark(run, width=width, ink='secondary', finishes=('deboss',)))
    # the hero line: offset either side of its centreline by half its swelling width
    y = centreline(hero_index, bases[hero_index])
    dx, dy = np.gradient(xs), np.gradient(y)
    norm = np.hypot(dx, dy)
    nx, ny = -dy / norm, dx / norm
    w = hero_min + (hero_max - hero_min) * np.exp(-((xs - cx) ** 2 + (y - cy) ** 2) / hero_radius ** 2)
    left = list(zip((xs + nx * w / 2).tolist(), (y + ny * w / 2).tolist()))
    right = list(zip((xs - nx * w / 2).tolist(), (y - ny * w / 2).tolist()))
    for outline in clip_shape(left + right[::-1], region(LID_BOX, keepouts)):
        marks.append(_mark(outline, width=0.0, ink='accent', fill='accent', closed=True, finishes=hero_finishes))
    return {'kind': 'gravure', 'marks': marks, 'lines': kept + 1, 'hero_index': hero_index,
            'hero_width_mm': [round(float(w.min()), 3), round(float(w.max()), 3)],
            'params': {'zone': list(zone), 'clear_band': clear_band, 'lens': list(lens), 'pitch': pitch, 'width': width,
                       'hero': [hero_min, hero_max], 'wave': wave, 'amplitude': amplitude, 'lens_radius': lens_radius,
                       'swell': swell}}


# --- B: the interference (round 2) --------------------------------------------------------------------------------

def field_radius(centre, keepouts, cap=None):
    """The largest circle about ``centre`` that touches no keep-out rectangle (the type's plain ground)."""
    c = Point(centre)
    r = min((c.distance(box(*k)) for k in keepouts), default=cap or 400.0)
    return r if cap is None else min(r, cap)


def interference(*, centres=((1.18, 0.382), (1.236, 0.618)), pitch=0.85, width=0.24, keepouts=(), inks=('secondary', 'blind'),
                 finishes=((), ('deboss',)), radius=None, step=0.6, pitches=None, widths=None, field_centre=None):
    """Two ring families, one about each centre (lid fractions; off the lid), clipped to ONE great circle about their
    midpoint (or ``field_centre``) whose radius clears every keep-out — so the rings fill a field and the type stands on
    plain ground. ``pitches`` / ``widths`` give each family its own (a pitch offset blooms the moiré into broad
    rounded fringes instead of fine radial spokes — Stage 3's repair)."""
    pts = [(c[0] * LID_W, c[1] * LID_H) for c in centres]
    mid = ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
    if field_centre is not None:
        mid = (field_centre[0] * LID_W, field_centre[1] * LID_H)
    R = radius if radius is not None else field_radius(mid, keepouts)
    field = Point(mid).buffer(R, quad_segs=256)
    area = region(LID_BOX, keepouts, field)
    marks = []
    if area.is_empty:
        return {'kind': 'interference', 'marks': marks, 'field_radius_mm': R, 'field_area_mm2': 0.0,
                'params': {'centres': [list(c) for c in centres], 'pitch': pitch, 'width': width}}
    pitches = pitches or (pitch, pitch)
    widths = widths or (width, width)
    for (cx, cy), ink, fin, pitch, width in zip(pts, inks, finishes, pitches, widths):
        near = Point(cx, cy).distance(area)
        far = max(math.dist((cx, cy), p) for p in area.exterior.coords) if area.geom_type == 'Polygon' else \
            max(math.dist((cx, cy), p) for g in area.geoms for p in g.exterior.coords)
        r = max(pitch, near - near % pitch)
        while r <= far + pitch:
            for run in clip(_circle(cx, cy, r, step), area):
                marks.append(_mark(run, width=width, ink=ink, finishes=fin))
            r += pitch
    return {'kind': 'interference', 'marks': marks, 'field_radius_mm': round(R, 2), 'field_area_mm2': round(area.area, 1),
            'field_centre_mm': [round(mid[0], 2), round(mid[1], 2)],
            'params': {'centres': [list(c) for c in centres], 'pitches': list(pitches), 'widths': list(widths), 'inks': list(inks),
                       'field_centre': list(field_centre) if field_centre else None}}


# --- C: the astrolabe (round 2) -----------------------------------------------------------------------------------

def _hatch(polygon, pitch=0.35, angle=0.0):
    """Parallel hatch lines across a polygon (the engraver's shading), cut exactly to it."""
    shape = Polygon(polygon)
    ca, sa = math.cos(angle), math.sin(angle)
    x0, y0, x1, y1 = shape.bounds
    reach = math.hypot(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lines, k = [], -reach / 2 + pitch / 2
    while k < reach / 2:
        p = (cx - sa * k, cy + ca * k)
        a = (p[0] - ca * reach, p[1] - sa * reach)
        b = (p[0] + ca * reach, p[1] + sa * reach)
        lines += _lines(LineString([a, b]).intersection(shape))
        k += pitch
    return lines


def astrolabe(*, centre=(0.86, 0.80), diameter=124.0, keepouts=(), foil='secondary', second_foil='accent', second_solid=False,
              rete_width=0.14, limb_width=0.32, interior=None, rose_scale=1.0, alidade=None):
    """One engraved instrument at ``diameter`` mm about ``centre`` (lid fractions), cropped by the lid and kept out of
    the type: rim, graduated ring (360 ticks, every fifth long), an eccentric ecliptic, three plate arcs, a rete of
    twelve star-pointers, and an eight-point wind-rose whose bright halves are the foil and whose hatched halves are the
    second foil. Every mark is foil over a blind deboss in register (relief)."""
    cx, cy = centre[0] * LID_W, centre[1] * LID_H
    R = diameter / 2.0
    area = region(LID_BOX, keepouts)
    marks = []
    fin = ('foil', 'deboss')

    def line(pts, w, ink=foil):
        for run in clip(pts, area):
            marks.append(_mark(run, width=w, ink=ink, finishes=fin))

    def shape(pts, ink=foil):
        for outline in clip_shape(pts, area):
            marks.append(_mark(outline, width=0.0, ink=ink, fill=ink, closed=True, finishes=fin))

    if interior:                                           # Stage 3's repair: the plate inside the rim printed in ink
        for outline in clip_shape(_circle(cx, cy, R - 4.6, 0.4), area):
            marks.append(_mark(outline, width=0.0, ink=interior, fill=interior, closed=True))
    line(_circle(cx, cy, R - limb_width / 2 + 0.16, 0.4), limb_width)
    line(_circle(cx, cy, R - 1.2, 0.4), 0.15)
    line(_circle(cx, cy, R - 4.6, 0.4), 0.15)
    for deg in range(360):
        a = math.radians(deg)
        length = 2.6 if deg % 10 == 0 else (1.7 if deg % 5 == 0 else 0.9)
        r0, r1 = R - 1.2, R - 1.2 - length
        line([(cx + r0 * math.cos(a), cy + r0 * math.sin(a)), (cx + r1 * math.cos(a), cy + r1 * math.sin(a))], 0.12)
    er, ey = 0.62 * R, cy - 0.20 * R                       # the ecliptic: eccentric, with its own ticks
    line(_circle(cx, ey, er, 0.4), 0.24)
    line(_circle(cx, ey, er - 0.9, 0.4), 0.12)
    for deg in range(0, 360, 6):
        a = math.radians(deg)
        line([(cx + er * math.cos(a), ey + er * math.sin(a)), (cx + (er - 0.9) * math.cos(a), ey + (er - 0.9) * math.sin(a))], 0.12)
    inner = Point(cx, cy).buffer(R - 4.9, quad_segs=128)  # plate arcs (almucantars), inside the inner disc
    for rr, off in ((0.95, 0.42), (0.70, 0.30), (0.46, 0.18)):
        for run in _lines(LineString(_circle(cx, cy + off * (R - 4.6), rr * (R - 4.6), 0.4)).intersection(inner)):
            line(run, 0.10)
    for k in range(12):                                    # the rete: twelve flame-shaped star-pointers
        a = math.radians(30 * k + 15)
        base_r, tip_r = er + 0.6, R - 5.6
        bx, by = cx + base_r * math.cos(a), ey + base_r * math.sin(a)
        tx, ty = cx + tip_r * math.cos(a + 0.10), cy + tip_r * math.sin(a + 0.10)
        nx, ny = -math.sin(a), math.cos(a)
        t = np.linspace(0, 1, 40)
        m1 = ((bx + tx) / 2 + nx * 1.6, (by + ty) / 2 + ny * 1.6)
        m2 = ((bx + tx) / 2 + nx * 0.4, (by + ty) / 2 + ny * 0.4)
        left = [((1 - u) ** 2 * bx + 2 * (1 - u) * u * m1[0] + u ** 2 * tx, (1 - u) ** 2 * by + 2 * (1 - u) * u * m1[1] + u ** 2 * ty) for u in t]
        right = [((1 - u) ** 2 * tx + 2 * (1 - u) * u * m2[0] + u ** 2 * bx, (1 - u) ** 2 * ty + 2 * (1 - u) * u * m2[1] + u ** 2 * by) for u in t]
        line(left + right[1:] + [left[0]], rete_width)
        shape(_circle(tx, ty, 0.45, 0.2))
    for k in range(8):                                     # the wind-rose: bright half foil, hatched half second foil
        a = math.radians(45 * k - 90)
        length = (0.42 if k % 2 == 0 else 0.27) * R * rose_scale
        half = (0.075 if k % 2 == 0 else 0.06) * R * rose_scale
        tip = (cx + length * math.cos(a), cy + length * math.sin(a))
        lft = (cx + half * math.cos(a - math.pi / 2), cy + half * math.sin(a - math.pi / 2))
        rgt = (cx + half * math.cos(a + math.pi / 2), cy + half * math.sin(a + math.pi / 2))
        shape([(cx, cy), lft, tip, (cx, cy)])
        if second_solid:                                   # Stage 3's repair: the rose-gold half as a solid foil
            shape([(cx, cy), tip, rgt, (cx, cy)], second_foil)
        else:
            line([(cx, cy), tip, rgt, (cx, cy)], 0.12, second_foil)
            for run in _hatch([(cx, cy), tip, rgt], pitch=0.32, angle=a):
                line(run, 0.10, second_foil)
    line(_circle(cx, cy, 0.05 * R, 0.2), 0.15)
    if alidade is not None:                                # Stage 3's repair: the sighting rule across the instrument
        a = math.radians(alidade)
        ux, uy, nx2, ny2 = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
        reach, half_w, tip = R - 1.6, 1.3, 9.0
        body = [(cx + ux * t + nx2 * w, cy + uy * t + ny2 * w) for t, w in
                ((-reach, 0.0), (-reach + tip, half_w), (reach - tip, half_w), (reach, 0.0), (reach - tip, -half_w), (-reach + tip, -half_w))]
        shape(body + [body[0]])
        for t in (-0.55 * R, 0.55 * R):                    # its two sighting vanes
            vx, vy = cx + ux * t, cy + uy * t
            shape([(vx + nx2 * 3.2 - ux * 1.0, vy + ny2 * 3.2 - uy * 1.0), (vx + nx2 * 3.2 + ux * 1.0, vy + ny2 * 3.2 + uy * 1.0),
                   (vx - nx2 * 3.2 + ux * 1.0, vy - ny2 * 3.2 + uy * 1.0), (vx - nx2 * 3.2 - ux * 1.0, vy - ny2 * 3.2 - uy * 1.0),
                   (vx + nx2 * 3.2 - ux * 1.0, vy + ny2 * 3.2 - uy * 1.0)])
        line(_circle(cx, cy, 2.4, 0.2), 0.5)              # the pin
    return {'kind': 'astrolabe', 'marks': marks, 'params': {'centre': list(centre), 'diameter': diameter},
            'centre_mm': [round(cx, 2), round(cy, 2)], 'radius_mm': R}


def bbox(device):
    """The device's ink extent in millimetres (x0, y0, x1, y1)."""
    pts = np.array([p for m in device['marks'] for p in m['points']])
    return tuple(float(v) for v in (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()))


def intrusions(device, boxes):
    """Every mark that enters one of ``boxes`` (each (x0, y0, x1, y1)): [(mark index, box index)] — empty by
    construction; the build asserts it."""
    shapes = [box(*b) for b in boxes]
    out = []
    for i, m in enumerate(device['marks']):
        geom = Polygon(m['points']) if m['fill'] and len(m['points']) > 3 else LineString(m['points']).buffer(m['width'] / 2)
        for j, s in enumerate(shapes):
            if geom.intersection(s).area > 1e-6:
                out.append((i, j))
    return out
