"""PALT-M4B-A — deterministic mesh-plane section extraction.

Authority (owner decision 2026-08-06): Blender Boolean cutting is **not**
the section authority. Sections are solved here, in Python, from the same
triangles the geometry kernel emitted.

Exactness strategy
------------------
Every section point carries a *combinatorial* identity rather than a
rounded coordinate:

* ``("V", vertex_index)``      — the plane passes exactly through a vertex
* ``("E", lo_index, hi_index)`` — the plane crosses an edge

Crossings are always interpolated from the lower vertex index to the
higher, so the two triangles sharing an edge compute bit-identical
coordinates. Segments therefore join by *index equality* — there is no
join tolerance anywhere, and no risk that a tolerance silently merges two
genuinely distinct points.

This matters because the centre sections are exactly degenerate by
construction: middle-row pocket centres sit at y=0, and the 64-segment
pocket rings start at 45 deg, so ring vertices land exactly on y=0. A
naive sign-classification cutter emits zero-length and duplicate segments
there and then reports a perfectly good section as an open loop.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

SCHEMA = "palette_mesh_section/1.0"

SECTION_TOPOLOGY = {
    "version": "mesh_section_topology/1.0",
    "on_plane_epsilon_mm": 1e-9,
    "point_identity": "COMBINATORIAL_VERTEX_AND_EDGE_KEYS",
    "join_tolerance": None,          # exact key equality — no tolerance
    "cap_strategy": "EAR_CLIPPING_SIMPLE_POLYGON",
}

AXES = {"x": 0, "y": 1, "z": 2}
# in-plane 2D basis for each section axis, so caps and areas are consistent
PLANE_BASIS = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}


class SectionError(ValueError):
    """Raised when a section is open, ambiguous or otherwise unusable."""


def _classify(dist, eps):
    if dist > eps:
        return 1
    if dist < -eps:
        return -1
    return 0


def _crossing_key(i, j):
    return ("E", i, j) if i < j else ("E", j, i)


def _crossing_point(vertices, i, j, axis_i, at):
    """Interpolate low-index -> high-index so both incident triangles agree
    to the last bit."""
    lo, hi = (i, j) if i < j else (j, i)
    a, b = vertices[lo], vertices[hi]
    da, db = a[axis_i] - at, b[axis_i] - at
    t = da / (da - db)
    return a + (b - a) * t


def section_component(name, vertices, faces, axis, at, *,
                      eps=None) -> dict:
    """Intersect one component with the plane ``axis = at``.

    Returns segments keyed combinatorially, the source face index for every
    segment (component identity and source-face references are preserved),
    and a count of coplanar faces — which is a topology fact about the mesh,
    NOT a failure.
    """
    if axis not in AXES:
        raise SectionError(f"unknown section axis {axis!r}")
    eps = SECTION_TOPOLOGY["on_plane_epsilon_mm"] if eps is None else eps
    ai = AXES[axis]
    v = np.asarray(vertices, dtype=float)
    f = np.asarray(faces, dtype=np.int64)
    side = np.array([_classify(d, eps) for d in (v[:, ai] - at)])

    points = {}
    segments = {}
    coplanar_faces = []
    point_contacts = 0

    def point(key, coord):
        if key not in points:
            points[key] = np.asarray(coord, dtype=float)
        return key

    for fi, tri in enumerate(f):
        s = [side[k] for k in tri]
        on = [k for k, sv in zip(tri, s) if sv == 0]
        pos = [k for k, sv in zip(tri, s) if sv > 0]
        neg = [k for k, sv in zip(tri, s) if sv < 0]

        if len(on) == 3:
            coplanar_faces.append(int(fi))
            continue
        if not pos or not neg:
            # entirely on one side, possibly touching at a vertex or edge
            if len(on) == 2:
                # an edge lying in the plane with the body on one side is a
                # genuine silhouette edge of the section
                a, b = on
                key_a = point(("V", int(a)), v[a])
                key_b = point(("V", int(b)), v[b])
                _add(segments, key_a, key_b, fi)
            elif len(on) == 1:
                point_contacts += 1
            continue

        # the triangle genuinely straddles: 0 or 1 vertex on the plane
        ends = []
        if len(on) == 1:
            ends.append(point(("V", int(on[0])), v[on[0]]))
        for a in pos:
            for b in neg:
                ends.append(point(_crossing_key(int(a), int(b)),
                                  _crossing_point(v, int(a), int(b),
                                                  ai, at)))
        if len(ends) != 2:
            raise SectionError(
                f"{name}: face {fi} produced {len(ends)} section points "
                "(expected 2) — ambiguous intersection")
        _add(segments, ends[0], ends[1], fi)

    return {"component": name, "axis": axis, "at": float(at),
            "points": points, "segments": segments,
            "coplanar_face_count": len(coplanar_faces),
            "coplanar_faces": coplanar_faces,
            "point_contact_count": point_contacts}


def _add(segments, a, b, face_index):
    if a == b:
        return                                     # zero-length, discard
    key = (a, b) if a <= b else (b, a)
    segments.setdefault(key, []).append(int(face_index))


def join_loops(sec) -> dict:
    """Join deduplicated segments into closed loops. Open or ambiguous
    loops are reported as failures, per the owner's requirement."""
    adj = {}
    for a, b in sec["segments"]:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    dangling = sorted((str(k), len(nb)) for k, nb in adj.items()
                      if len(nb) != 2)
    if dangling:
        raise SectionError(
            f"{sec['component']}: section is open or ambiguous — "
            f"{len(dangling)} point(s) do not have exactly two incident "
            f"segments; first: {dangling[:4]}")

    unvisited = set(sec["segments"])
    loops = []
    while unvisited:
        start_seg = min(unvisited)              # deterministic seed
        unvisited.discard(start_seg)
        start, nxt = start_seg
        loop = [start, nxt]
        while True:
            a, b = loop[-2], loop[-1]
            step = [n for n in adj[b] if n != a]
            if len(step) != 1:
                raise SectionError(
                    f"{sec['component']}: ambiguous continuation at {b}")
            nxt = step[0]
            seg = (b, nxt) if b <= nxt else (nxt, b)
            if nxt == loop[0]:
                unvisited.discard(seg)
                break
            if seg not in unvisited:
                raise SectionError(
                    f"{sec['component']}: segment {seg} revisited — the "
                    "section self-intersects or is ambiguous")
            unvisited.discard(seg)
            loop.append(nxt)
        loops.append(loop)

    u, w = PLANE_BASIS[sec["axis"]]
    out = []
    for loop in loops:
        pts = np.array([[sec["points"][k][u], sec["points"][k][w]]
                        for k in loop])
        area = 0.5 * float(np.sum(pts[:, 0] * np.roll(pts[:, 1], -1)
                                  - np.roll(pts[:, 0], -1) * pts[:, 1]))
        out.append({"keys": loop, "points_2d": pts,
                    "signed_area_mm2": area, "closed": True,
                    "point_count": len(loop)})
    out.sort(key=lambda d: -abs(d["signed_area_mm2"]))
    for i, loop in enumerate(out):
        loop["role"] = "OUTER" if i == 0 else "INNER"
    return {"component": sec["component"], "loops": out,
            "loop_count": len(out),
            "coplanar_face_count": sec["coplanar_face_count"],
            "point_contact_count": sec["point_contact_count"]}


def _segments_cross(a, b, c, d):
    def orient(p, q, r):
        val = ((q[0] - p[0]) * (r[1] - p[1])
               - (q[1] - p[1]) * (r[0] - p[0]))
        if abs(val) < 1e-12:
            return 0
        return 1 if val > 0 else -1

    o1, o2 = orient(a, b, c), orient(a, b, d)
    o3, o4 = orient(c, d, a), orient(c, d, b)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


def _assert_simple(pts):
    """A cap is only meaningful for a non-self-intersecting loop. Ear
    clipping alone will happily triangulate a bow-tie, so the polygon is
    checked before it is capped rather than after."""
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue
            if _segments_cross(a, b, pts[j], pts[(j + 1) % n]):
                raise SectionError(
                    f"section loop is self-intersecting: edge {i} crosses "
                    f"edge {j} — it cannot be capped")


def _ear_clip(points_2d):
    """Deterministic ear clipping for a simple polygon."""
    pts = [tuple(p) for p in points_2d]
    n = len(pts)
    if n < 3:
        return []
    _assert_simple(pts)
    area2 = sum(pts[i][0] * pts[(i + 1) % n][1]
                - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    idx = list(range(n)) if area2 > 0 else list(range(n))[::-1]

    def cross(o, a, b):
        return ((pts[a][0] - pts[o][0]) * (pts[b][1] - pts[o][1])
                - (pts[a][1] - pts[o][1]) * (pts[b][0] - pts[o][0]))

    def inside(a, b, c, p):
        # strictly interior only: section loops carry long collinear runs
        # (the flat deck, the underside), and a vertex lying ON an ear's
        # edge must not veto that ear
        return (cross(a, b, p) > 1e-12 and cross(b, c, p) > 1e-12
                and cross(c, a, p) > 1e-12)

    tris = []
    guard = 0
    while len(idx) > 3 and guard < 4 * n * n:
        guard += 1
        clipped = False
        for i in range(len(idx)):
            a = idx[(i - 1) % len(idx)]
            b = idx[i]
            c = idx[(i + 1) % len(idx)]
            if cross(a, b, c) <= 1e-15:
                continue
            if any(inside(a, b, c, p) for p in idx
                   if p not in (a, b, c)):
                continue
            tris.append((a, b, c))
            idx.pop(i)
            clipped = True
            break
        if not clipped:
            raise SectionError("ear clipping failed — the section loop is "
                               "not a simple polygon")
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def cap_loop(loop) -> dict:
    """Deterministic cap mesh for one closed loop."""
    tris = _ear_clip(loop["points_2d"])
    return {"triangle_count": len(tris), "triangles": tris}


def section_assembly(components, axis, at, *, cap=False) -> dict:
    """Section every component and join loops. ``components`` maps a name
    to a dict with ``vertices`` and ``faces``."""
    results = {}
    failures = []
    for name in sorted(components):
        comp = components[name]
        sec = section_component(name, comp["vertices"], comp["faces"],
                                axis, at)
        if not sec["segments"]:
            continue                       # component misses the plane
        try:
            joined = join_loops(sec)
        except SectionError as exc:
            failures.append(str(exc))
            continue
        if cap:
            for loop in joined["loops"]:
                loop["cap"] = cap_loop(loop)
        joined["source_faces"] = {str(k): v
                                  for k, v in sec["segments"].items()}
        results[name] = joined
    if failures:
        raise SectionError("; ".join(failures))

    payload = []
    for name in sorted(results):
        for loop in results[name]["loops"]:
            payload.append(f"{name}:{loop['role']}:{loop['point_count']}:"
                           f"{loop['signed_area_mm2']:.9f}")
    identity = hashlib.sha256(
        ("|".join(payload)
         + repr(sorted(SECTION_TOPOLOGY.items()))).encode()).hexdigest()[:16]
    return {"schema": SCHEMA, "axis": axis, "at": float(at),
            "components": results,
            "component_count": len(results),
            "loop_count": sum(r["loop_count"] for r in results.values()),
            "open_loop_count": 0,
            "section_identity": identity,
            "topology": dict(SECTION_TOPOLOGY),
            "authority": "DETERMINISTIC_PYTHON_MESH_PLANE_INTERSECTION",
            "boolean_free": True}


def span(loop, index):
    """Min/max of a loop along in-plane axis ``index`` (0 = horizontal)."""
    p = loop["points_2d"]
    return float(p[:, index].min()), float(p[:, index].max())


def loop_elevations(joined):
    """Distinct z levels present in a joined section, rounded — used to
    prove which layers the section actually exposes."""
    out = set()
    for loop in joined["loops"]:
        for _, z in loop["points_2d"]:
            out.add(round(float(z), 4))
    return sorted(out)


def polygon_area(points_2d):
    p = np.asarray(points_2d, dtype=float)
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1)
                              - np.roll(p[:, 0], -1) * p[:, 1]))


def bounding_box(joined):
    xs, zs = [], []
    for loop in joined["loops"]:
        xs += list(loop["points_2d"][:, 0])
        zs += list(loop["points_2d"][:, 1])
    return (min(xs), min(zs), max(xs), max(zs)) if xs else None


def assert_math_sane():                          # pragma: no cover
    assert math.isclose(polygon_area([[0, 0], [1, 0], [1, 1], [0, 1]]), 1.0)
