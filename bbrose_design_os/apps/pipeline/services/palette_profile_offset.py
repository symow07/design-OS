"""PALT-M4B-A3F — signed normal offset of a meridional profile.

A3R proved the cup wall was built by offsetting the pocket profile in
RADIUS. On an arc that delivers ``w * cos(obliquity)``, which collapsed to
0.6007 mm on the floor fillet. This kernel offsets along the profile
NORMAL instead, analytically per primitive.

Conventions (changing any of them changes the geometry identity):

* the profile is a meridional ``(r, z)`` polyline of typed primitives,
  ordered from the deck downward;
* ``side="MATERIAL"`` offsets away from the cavity, i.e. toward larger r
  for a wall and toward smaller z for a floor;
* a LINE offsets to a parallel line at exactly ``distance``;
* an ARC keeps its centre and takes ``radius +/- distance`` by whether the
  material lies away from or toward the centre. Toward-the-centre is the
  dangerous direction: when ``distance >= radius`` the offset degenerates
  and the kernel FAILS CLOSED rather than clamping.

Nothing is silently clamped, smoothed, trimmed or moved.
"""
from __future__ import annotations

import hashlib
import math

SCHEMA = "palette_profile_offset/1.0"

OFFSET_TOPOLOGY = {
    "version": "meridional_normal_offset/1.0",
    "profile_orientation": "DECK_DOWNWARD",
    "material_side_convention": "AWAY_FROM_CAVITY",
    "signed_offset_convention": "POSITIVE_INTO_MATERIAL",
    "join_policy": "PRESERVE_ANALYTIC_TANGENCY_NO_TRIM_NO_FILLET",
    "curvature_policy": "FAIL_WHEN_DISTANCE_REACHES_LOCAL_RADIUS",
    "cusp_policy": "FAIL_CLOSED",
    "self_intersection_policy": "FAIL_CLOSED",
    "adaptive_chord_tolerance_mm": 0.002,
    "coordinate_quantization": 1e-9,
    "arc_sample_count": 5,
    "tangent_continuity_tolerance_mm": 1e-6,
}

LINE = "LINE"
ARC = "ARC"

OFFSET_SINGULARITY = "OFFSET_SINGULARITY"
OFFSET_CUSP = "OFFSET_CUSP"
OFFSET_SELF_INTERSECTION = "OFFSET_SELF_INTERSECTION"
OFFSET_NORMAL_REVERSAL = "OFFSET_NORMAL_REVERSAL"
OFFSET_TANGENT_DISCONTINUITY = "OFFSET_TANGENT_DISCONTINUITY"
OFFSET_NON_MONOTONIC = "OFFSET_NON_MONOTONIC"
OFFSET_SIDE_ERROR = "OFFSET_SIDE_ERROR"


class ProfileOffsetError(ValueError):
    """Raised when a valid normal offset cannot be constructed."""


def line(r0, z0, r1, z1):
    return {"kind": LINE, "start": (float(r0), float(z0)),
            "end": (float(r1), float(z1))}


def arc(centre_r, centre_z, radius, start_deg, end_deg, *,
        material_toward_centre):
    """Circular primitive. ``material_toward_centre`` states which side the
    plastic is on and therefore the sign of the radius change."""
    if radius <= 0:
        raise ProfileOffsetError(f"arc radius {radius} is not positive")
    return {"kind": ARC, "centre": (float(centre_r), float(centre_z)),
            "radius": float(radius), "start_deg": float(start_deg),
            "end_deg": float(end_deg),
            "material_toward_centre": bool(material_toward_centre)}


def _arc_point(a, deg):
    t = math.radians(deg)
    return (a["centre"][0] + a["radius"] * math.cos(t),
            a["centre"][1] + a["radius"] * math.sin(t))


def _line_normal(seg):
    (r0, z0), (r1, z1) = seg["start"], seg["end"]
    dr, dz = r1 - r0, z1 - z0
    ln = math.hypot(dr, dz)
    if ln < 1e-12:
        raise ProfileOffsetError("degenerate zero-length line segment")
    # right-hand normal of the downward direction points into the material
    return (-dz / ln, dr / ln), ln


def offset_primitive(prim, distance, *, side="MATERIAL"):
    """Exact analytic offset of one primitive."""
    if side != "MATERIAL":
        raise ProfileOffsetError(
            f"unknown offset side {side!r}; only MATERIAL is defined")
    if distance < 0:
        raise ProfileOffsetError(
            f"negative offset {distance}; the sign convention is "
            "POSITIVE_INTO_MATERIAL")
    if prim["kind"] == LINE:
        (nr, nz), _ = _line_normal(prim)
        # material is at larger r for a descending wall
        if nr < 0:
            nr, nz = -nr, -nz
        return {"kind": LINE,
                "start": (prim["start"][0] + nr * distance,
                          prim["start"][1] + nz * distance),
                "end": (prim["end"][0] + nr * distance,
                        prim["end"][1] + nz * distance),
                "offset_applied_mm": distance,
                "normal": (nr, nz)}
    if prim["kind"] == ARC:
        toward = prim["material_toward_centre"]
        new_r = prim["radius"] - distance if toward \
            else prim["radius"] + distance
        if toward and new_r <= OFFSET_TOPOLOGY[
                "tangent_continuity_tolerance_mm"]:
            raise ProfileOffsetError(
                f"{OFFSET_SINGULARITY}: offsetting a concave arc of radius "
                f"{prim['radius']} by {distance} collapses it to "
                f"{new_r:.6f}. The offset distance has reached the local "
                "curvature radius; no valid offset curve exists.")
        return {"kind": ARC, "centre": prim["centre"], "radius": new_r,
                "start_deg": prim["start_deg"], "end_deg": prim["end_deg"],
                "material_toward_centre": toward,
                "offset_applied_mm": distance}
    raise ProfileOffsetError(f"unknown primitive {prim['kind']!r}")


def sample_primitive(prim, count=None):
    """Deterministic (r, z) samples, start inclusive to end inclusive."""
    if prim["kind"] == LINE:
        return [prim["start"], prim["end"]]
    n = count or OFFSET_TOPOLOGY["arc_sample_count"]
    a, b = prim["start_deg"], prim["end_deg"]
    return [_arc_point(prim, a + (b - a) * i / n) for i in range(n + 1)]


def _segments_cross(p, q, r, s):
    def o(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-12 else (1 if v > 0 else -1)
    o1, o2, o3, o4 = o(p, q, r), o(p, q, s), o(r, s, p), o(r, s, q)
    return o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4)


def offset_meridional_profile_normal(profile, distance, side="MATERIAL",
                                     *, monotonic=True) -> dict:
    """Offset a typed meridional profile and validate the result."""
    if distance <= 0:
        raise ProfileOffsetError("offset distance must be positive")
    offsets = [offset_primitive(p, distance, side=side) for p in profile]

    pts = []
    for i, off in enumerate(offsets):
        s = sample_primitive(off)
        if i and _dist(pts[-1], s[0]) > OFFSET_TOPOLOGY[
                "tangent_continuity_tolerance_mm"]:
            raise ProfileOffsetError(
                f"{OFFSET_TANGENT_DISCONTINUITY}: offset primitive {i} "
                f"starts {_dist(pts[-1], s[0]):.6f} mm from where primitive "
                f"{i - 1} ended; tangency was not preserved")
        pts.extend(s if not pts else s[1:])

    for i in range(len(pts) - 1):
        for j in range(i + 2, len(pts) - 1):
            if _segments_cross(pts[i], pts[i + 1], pts[j], pts[j + 1]):
                raise ProfileOffsetError(
                    f"{OFFSET_SELF_INTERSECTION}: offset segment {i} crosses "
                    f"segment {j}")

    if monotonic:
        for (r0, z0), (r1, z1) in zip(pts, pts[1:]):
            if z1 > z0 + 1e-9:
                raise ProfileOffsetError(
                    f"{OFFSET_NON_MONOTONIC}: offset profile rises from "
                    f"z={z0:.6f} to z={z1:.6f}")
            if r1 > r0 + 1e-9:
                raise ProfileOffsetError(
                    f"{OFFSET_CUSP}: offset profile turns outward at "
                    f"z={z1:.6f}, which is a cusp")

    ident = hashlib.sha256(
        (repr([(round(r, 9), round(z, 9)) for r, z in pts])
         + repr(sorted(OFFSET_TOPOLOGY.items()))
         + f"|{distance}|{side}").encode()).hexdigest()[:16]
    return {"record_type": SCHEMA, "distance_mm": distance, "side": side,
            "primitives": offsets, "points": pts,
            "topology": dict(OFFSET_TOPOLOGY),
            "profile_identity": ident,
            "singularities": [], "self_intersections": []}


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def pocket_profile_primitives(*, sharp_r, deck_z, floor_z, draft_deg,
                              rim_fillet, floor_fillet, core_top_z):
    """The cavity profile BELOW the core ceiling, as typed primitives.

    The rim fillet is deliberately absent: it lies above the core ceiling,
    is never part of the cup, and — being concave with a 0.35 mm radius —
    could not be offset by 1 mm anyway.
    """
    th = math.radians(draft_deg)
    wall_r = lambda z: sharp_r - (deck_z - z) * math.tan(th)   # noqa: E731
    z_t2 = floor_z + floor_fillet * (1.0 - math.sin(th))
    c_r2 = wall_r(z_t2) - floor_fillet * math.cos(th)
    c_z2 = floor_z + floor_fillet
    top = min(core_top_z, deck_z)
    prims = [line(wall_r(top), top, wall_r(z_t2), z_t2)]
    prims.append(arc(c_r2, c_z2, floor_fillet,
                     math.degrees(-th), -90.0,
                     material_toward_centre=False))
    return prims, {"wall_bottom_z_mm": z_t2, "fillet_centre": (c_r2, c_z2),
                   "flat_floor_radius_mm": c_r2}
