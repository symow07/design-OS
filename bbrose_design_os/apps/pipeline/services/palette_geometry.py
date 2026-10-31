"""PALT-M4 — deterministic parametric palette geometry.

Every component is generated independently and keeps its own identity;
the palette is never merged into one irreversible mesh. Component
positions are RESOLVED from the PALT-M2 layout kernel and the PALT-M3
stack-up — never placed by eye.

Authority separation (unchanged law):

* CONTRACT_GEOMETRY        — dimensions resolved from the contracts
* VISUALIZATION_GEOMETRY   — meshes built for review only
* MECHANISM_ASSUMPTIONS    — DESIGN_DEFAULT engineering estimates
* MANUFACTURING_GEOMETRY   — NOT_ESTABLISHED, never produced here

Nothing in this module may shrink a pan, wall, clearance or mechanism
envelope to make geometry pass.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

SCHEMA = "palette_component_geometry/1.0"

# mesh resolution (deterministic)
CORNER_SEGMENTS = 10
FILLET_SEGMENTS = 5
CIRCLE_SEGMENTS = 48


def mesh_identity(vertices: np.ndarray, faces: np.ndarray) -> str:
    return hashlib.sha256(
        np.round(vertices, 6).tobytes() + np.asarray(faces).tobytes()
    ).hexdigest()[:16]


def _component(name, vertices, faces, *, authority="VISUALIZATION_GEOMETRY",
               role="", parent=None):
    v = np.asarray(vertices, dtype=float)
    f = np.asarray(faces, dtype=np.int64)
    return {"name": name, "vertices": v, "faces": f,
            "mesh_identity": mesh_identity(v, f),
            "authority": authority, "role": role, "parent": parent,
            "schema": SCHEMA}


# ---------------------------------------------------------------------------
# outline primitives


def rounded_rect_outline(w: float, d: float, r: float,
                         segments: int = CORNER_SEGMENTS) -> np.ndarray:
    """Closed CCW outline of a rounded rectangle centred on the origin."""
    r = max(0.0, min(r, min(w, d) / 2.0 - 1e-6))
    hw, hd = w / 2.0 - r, d / 2.0 - r
    pts = []
    for cx, cy, a0 in ((hw, hd, 0.0), (-hw, hd, math.pi / 2),
                       (-hw, -hd, math.pi), (hw, -hd, 3 * math.pi / 2)):
        for i in range(segments + 1):
            a = a0 + (math.pi / 2) * i / segments
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    # drop duplicated corner joins
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    return np.asarray(out, dtype=float)


def circle_outline(r: float, segments: int = CIRCLE_SEGMENTS) -> np.ndarray:
    t = np.linspace(0.0, 2 * math.pi, segments, endpoint=False)
    return np.stack([r * np.cos(t), r * np.sin(t)], axis=1)


# ---------------------------------------------------------------------------
# solid builders


def _ring_faces(n_outer, ring_a_start, ring_b_start, n):
    faces = []
    for i in range(n):
        j = (i + 1) % n
        a0, a1 = ring_a_start + i, ring_a_start + j
        b0, b1 = ring_b_start + i, ring_b_start + j
        faces.append((a0, a1, b0))
        faces.append((a1, b1, b0))
    return faces


def _cap_faces(ring_start, n, centre_index, flip=False):
    faces = []
    for i in range(n):
        j = (i + 1) % n
        if flip:
            faces.append((ring_start + j, ring_start + i, centre_index))
        else:
            faces.append((ring_start + i, ring_start + j, centre_index))
    return faces


def filleted_slab(name, w, d, h, corner_r, edge_r, *, z0=0.0,
                  role="", authority="VISUALIZATION_GEOMETRY",
                  segments=CORNER_SEGMENTS, fillet_segments=FILLET_SEGMENTS):
    """A moulded-looking slab: rounded vertical corners AND filleted top and
    bottom edges. Built as a loft of inset rounded-rect outlines, so it
    never reads as a crude box."""
    edge_r = max(0.0, min(edge_r, h / 2.0 - 1e-6, corner_r - 1e-6
                          if corner_r > 0 else edge_r))
    levels = []
    # bottom fillet
    for i in range(fillet_segments + 1):
        t = i / fillet_segments
        dz = edge_r * t
        inset = edge_r - math.sqrt(max(edge_r ** 2 - (edge_r - dz) ** 2, 0.0))
        levels.append((z0 + dz, inset))
    # straight wall
    levels.append((z0 + h - edge_r, 0.0))
    # top fillet
    for i in range(1, fillet_segments + 1):
        t = i / fillet_segments
        dz = edge_r * t
        inset = edge_r - math.sqrt(max(edge_r ** 2 - (edge_r - dz) ** 2, 0.0))
        levels.append((z0 + h - edge_r + dz, inset))

    rings, n = [], None
    for z, inset in levels:
        outline = rounded_rect_outline(max(w - 2 * inset, 1e-3),
                                       max(d - 2 * inset, 1e-3),
                                       max(corner_r - inset, 0.0), segments)
        n = len(outline)
        rings.append(np.column_stack([outline, np.full(n, z)]))
    verts = np.concatenate(rings, axis=0)
    faces = []
    for k in range(len(rings) - 1):
        faces += _ring_faces(n, k * n, (k + 1) * n, n)
    bottom_c = len(verts)
    top_c = bottom_c + 1
    verts = np.concatenate([verts, [[0.0, 0.0, levels[0][0]]],
                            [[0.0, 0.0, levels[-1][0]]]], axis=0)
    faces += _cap_faces(0, n, bottom_c, flip=True)
    faces += _cap_faces((len(rings) - 1) * n, n, top_c)
    return _component(name, verts, faces, role=role, authority=authority)


def wall_ring(name, outer_w, outer_d, inner_w, inner_d, h, corner_r,
              *, z0=0.0, role="", authority="VISUALIZATION_GEOMETRY",
              segments=CORNER_SEGMENTS):
    """A closed rectangular wall ring (a tub wall or a lid skirt)."""
    inner_r = max(corner_r - (outer_w - inner_w) / 2.0, 0.5)
    o = rounded_rect_outline(outer_w, outer_d, corner_r, segments)
    i = rounded_rect_outline(inner_w, inner_d, inner_r, segments)
    n = min(len(o), len(i))
    o, i = o[:n], i[:n]
    rings = [np.column_stack([o, np.full(n, z0)]),
             np.column_stack([o, np.full(n, z0 + h)]),
             np.column_stack([i, np.full(n, z0 + h)]),
             np.column_stack([i, np.full(n, z0)])]
    verts = np.concatenate(rings, axis=0)
    faces = []
    faces += _ring_faces(n, 0, n, n)              # outer wall
    faces += _ring_faces(n, n, 2 * n, n)          # top face
    faces += _ring_faces(n, 2 * n, 3 * n, n)      # inner wall
    faces += _ring_faces(n, 3 * n, 0, n)          # bottom face
    return _component(name, verts, faces, role=role, authority=authority)


def cylinder(name, r, h, *, centre=(0.0, 0.0), z0=0.0, role="",
             authority="VISUALIZATION_GEOMETRY", segments=CIRCLE_SEGMENTS,
             axis="z"):
    c = circle_outline(r, segments)
    cx, cy = centre
    if axis == "z":
        low = np.column_stack([c[:, 0] + cx, c[:, 1] + cy,
                               np.full(segments, z0)])
        high = np.column_stack([c[:, 0] + cx, c[:, 1] + cy,
                                np.full(segments, z0 + h)])
        lc, hc = [cx, cy, z0], [cx, cy, z0 + h]
    elif axis == "x":          # hinge barrels/pin: circle in (y,z), run x
        low = np.column_stack([np.full(segments, cx),
                               c[:, 0] + cy, c[:, 1] + z0])
        high = np.column_stack([np.full(segments, cx + h),
                                c[:, 0] + cy, c[:, 1] + z0])
        lc, hc = [cx, cy, z0], [cx + h, cy, z0]
    else:                                  # axis == "y"
        low = np.column_stack([c[:, 0] + cx, np.full(segments, cy),
                               c[:, 1] + z0])
        high = np.column_stack([c[:, 0] + cx, np.full(segments, cy + h),
                                c[:, 1] + z0])
        lc, hc = [cx, cy, z0], [cx, cy + h, z0]
    verts = np.concatenate([low, high, [lc], [hc]], axis=0)
    faces = _ring_faces(segments, 0, segments, segments)
    faces += _cap_faces(0, segments, 2 * segments, flip=True)
    faces += _cap_faces(segments, segments, 2 * segments + 1)
    return _component(name, verts, faces, role=role, authority=authority)


def tile_with_hole(cx, cy, cell_w, cell_d, hole_r, z, segments=CIRCLE_SEGMENTS):
    """Top-face tile: a cell rectangle minus a circular hole, triangulated
    by projecting each circle sample outward to the cell boundary."""
    circle = circle_outline(hole_r, segments)
    outer = []
    for x, y in circle:
        ang = math.atan2(y, x)
        # ray-box intersection with the cell half-extents
        hw, hd = cell_w / 2.0, cell_d / 2.0
        dx, dy = math.cos(ang), math.sin(ang)
        tx = hw / abs(dx) if abs(dx) > 1e-9 else float("inf")
        ty = hd / abs(dy) if abs(dy) > 1e-9 else float("inf")
        t = min(tx, ty)
        outer.append((dx * t, dy * t))
    inner_v = np.column_stack([circle[:, 0] + cx, circle[:, 1] + cy,
                               np.full(segments, z)])
    outer_v = np.column_stack([np.asarray(outer)[:, 0] + cx,
                               np.asarray(outer)[:, 1] + cy,
                               np.full(segments, z)])
    verts = np.concatenate([inner_v, outer_v], axis=0)
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, segments + i, segments + j))
        faces.append((i, segments + j, j))
    return verts, faces


def transform(component, *, translate=(0.0, 0.0, 0.0), rotate_x_about=None,
              angle_deg=0.0):
    """Return a transformed copy. Identity is preserved on the ORIGINAL
    component (states share component identities by construction)."""
    v = component["vertices"].copy()
    if rotate_x_about is not None and angle_deg:
        y0, z0 = rotate_x_about
        a = math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)
        y, z = v[:, 1] - y0, v[:, 2] - z0
        v[:, 1] = y0 + y * ca - z * sa
        v[:, 2] = z0 + y * sa + z * ca
    v[:, 0] += translate[0]
    v[:, 1] += translate[1]
    v[:, 2] += translate[2]
    out = dict(component)
    out["vertices"] = v
    return out


def rect_ring_faces(inner_pts, outer_pts, z, base_index=0):
    """Triangulate the region between two closed polylines of equal length."""
    n = len(inner_pts)
    verts = np.concatenate([
        np.column_stack([inner_pts, np.full(n, z)]),
        np.column_stack([outer_pts, np.full(n, z)])], axis=0)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((base_index + i, base_index + n + i, base_index + n + j))
        faces.append((base_index + i, base_index + n + j, base_index + j))
    return verts, faces


def tray_solid(name, tray_w, tray_d, top_z, floor_z, bottom_z, centres,
               pocket_r, corner_r, *, role="", segments=CIRCLE_SEGMENTS,
               grid_w=None, grid_d=None):
    """A closed tray solid: top face (pocket tiles + border ring), pocket
    walls and floors, outer side wall and bottom face."""
    verts, faces = [], []
    off = 0

    def emit(v, f):
        nonlocal off
        verts.append(np.asarray(v, dtype=float))
        faces.extend([(a + off, b + off, c + off) for a, b, c in f])
        off += len(v)

    cell = grid_w / 3.0 if grid_w else tray_w / 3.0
    cell_d = grid_d / 3.0 if grid_d else tray_d / 3.0
    for cx, cy in centres:
        v, f = tile_with_hole(cx, cy, cell, cell_d, pocket_r, top_z,
                              segments)
        emit(v, f)
    # border ring between the tile grid and the tray outer outline
    gw = grid_w or tray_w
    gd = grid_d or tray_d
    inner = rounded_rect_outline(gw, gd, 0.01, CORNER_SEGMENTS)
    outer = rounded_rect_outline(tray_w, tray_d, corner_r, CORNER_SEGMENTS)
    n = min(len(inner), len(outer))
    v, f = rect_ring_faces(inner[:n], outer[:n], top_z)
    emit(v, f)
    # pocket walls + floors
    for cx, cy in centres:
        circ = circle_outline(pocket_r, segments)
        top = np.column_stack([circ[:, 0] + cx, circ[:, 1] + cy,
                               np.full(segments, top_z)])
        bot = np.column_stack([circ[:, 0] + cx, circ[:, 1] + cy,
                               np.full(segments, floor_z)])
        v = np.concatenate([top, bot, [[cx, cy, floor_z]]], axis=0)
        f = _ring_faces(segments, 0, segments, segments)
        f += _cap_faces(segments, segments, 2 * segments, flip=True)
        emit(v, f)
    # outer side wall + bottom face
    ring = rounded_rect_outline(tray_w, tray_d, corner_r, CORNER_SEGMENTS)
    m = len(ring)
    v = np.concatenate([
        np.column_stack([ring, np.full(m, top_z)]),
        np.column_stack([ring, np.full(m, bottom_z)]),
        [[0.0, 0.0, bottom_z]]], axis=0)
    f = _ring_faces(m, 0, m, m)
    f += _cap_faces(m, m, 2 * m)
    emit(v, f)
    return _component(name, np.concatenate(verts, axis=0), faces, role=role)


def annulus_solid(name, r_inner, r_outer, h, *, centre=(0.0, 0.0), z0=0.0,
                  role="", segments=CIRCLE_SEGMENTS):
    """A closed annular ring solid (a pocket web wall). Manifold by
    construction: outer wall + inner wall + top annulus + bottom annulus."""
    cx, cy = centre
    ci = circle_outline(r_inner, segments)
    co = circle_outline(r_outer, segments)
    n = segments
    rings = []
    for pts, z in ((co, z0), (co, z0 + h), (ci, z0 + h), (ci, z0)):
        rings.append(np.column_stack([pts[:, 0] + cx, pts[:, 1] + cy,
                                      np.full(n, z)]))
    verts = np.concatenate(rings, axis=0)
    faces = []
    faces += _ring_faces(n, 0, n, n)          # outer wall
    faces += _ring_faces(n, n, 2 * n, n)      # top annulus
    faces += _ring_faces(n, 2 * n, 3 * n, n)  # inner wall
    faces += _ring_faces(n, 3 * n, 0, n)      # bottom annulus
    return _component(name, verts, faces, role=role)
