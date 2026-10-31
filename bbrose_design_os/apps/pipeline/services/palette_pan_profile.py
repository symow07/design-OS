"""PALT-M4B-A2 §4 — versioned metal-pan cross-section contract.

M4B-A modelled the pan as a sharp-cornered cup. That is not a real drawn
pan, and the sharp outer base corner is what fouled the moulded floor
fillet. The profile is parametric here, with the base corner radius as a
first-class contract field.

Every value is DESIGN_DEFAULT / NOT_MANUFACTURER_CONFIRMED. No supplier
radius is assumed: the selected radius is chosen by a documented
engineering constraint in ``palt_m4b_a2``, not by plausibility.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

SCHEMA = "metal_pan_cross_section/1.0"

PAN_EDGE_PROFILE_AUTHORITY = "PROVISIONAL_DESIGN_DEFAULT"
PAN_MANUFACTURING_AUTHORITY = "NOT_ESTABLISHED"

TOPOLOGY = {
    "version": "metal_pan_topology/1.0",
    "radial_segments": 64,          # matches the pocket ring count
    "base_corner_samples": 6,
    "coordinate_quantization": 1e-6,
}

# --- the contract ----------------------------------------------------------
PAN_CONTRACT = {
    "pan_outside_diameter_mm": (26.0, "owner M4B-A preserved value"),
    "pan_depth_mm": (3.5, "owner M4B-A preserved value"),
    "metal_wall_thickness_mm": (0.25, "PAN_SYSTEM drawn-pan wall"),
    "metal_floor_thickness_mm": (0.25, "PAN_SYSTEM drawn-pan floor"),
    "side_wall_draft_deg": (0.0, "drawn pans are near-straight-walled; a "
                                 "non-zero value is available but "
                                 "unestablished"),
    "base_corner_radius_mm": (0.40, "PAN_BASE_CORNER_RADIUS — selected in "
                                    "M4B-A2 by the flat-seating "
                                    "constraint, not assumed"),
    "floor_radius_mm": (0.20, "inner floor-to-wall radius of the drawn "
                              "cup"),
    "upper_wall_terminates_at": ("PAN_TOP_Z", "the rim is a plain cut edge; "
                                              "no bead or curl is modelled"),
    "pan_layout_tolerance_mm": (0.30, "the palt_p1 layout allowance — see "
                                      "the datum conflict record; it is "
                                      "NOT a verified shell tolerance"),
}

TESTED_BASE_RADII_MM = (0.30, 0.40, 0.50)


class PanProfileError(ValueError):
    """Raised when a pan cross-section is not physically constructible."""


def contract_values() -> dict:
    return {k: v[0] for k, v in PAN_CONTRACT.items()}


def contract_provenance() -> dict:
    return {k: {"value": v[0], "basis": v[1],
                "authority": PAN_EDGE_PROFILE_AUTHORITY,
                "manufacturing_authority": PAN_MANUFACTURING_AUTHORITY}
            for k, v in PAN_CONTRACT.items()}


def outer_profile(*, outside_diameter, depth, base_corner_radius,
                  side_wall_draft_deg=0.0, z0=0.0, samples=None):
    """Outer (r, z) profile of the pan, bottom-up.

    The flat base runs to ``R - base_corner_radius``; the corner arc is
    tangent to both the base plane and the side wall.
    """
    samples = samples or TOPOLOGY["base_corner_samples"]
    r_out = outside_diameter / 2.0
    br = float(base_corner_radius)
    if br < 0:
        raise PanProfileError(f"base corner radius {br} is negative")
    if br > depth:
        raise PanProfileError(
            f"base corner radius {br} exceeds the pan depth {depth}")
    if br >= r_out:
        raise PanProfileError(
            f"base corner radius {br} exceeds the pan radius {r_out}")
    pts = [(r_out - br, z0)]
    if br > 0:
        cx, cz = r_out - br, z0 + br
        for i in range(1, samples + 1):
            a = -math.pi / 2 + (math.pi / 2) * i / samples
            pts.append((cx + br * math.cos(a), cz + br * math.sin(a)))
    th = math.radians(side_wall_draft_deg)
    top_r = r_out + (depth - br) * math.tan(th)
    pts.append((top_r, z0 + depth))
    for (r0, za), (r1, zb) in zip(pts, pts[1:]):
        if zb < za - 1e-12 or r1 < r0 - 1e-12:
            raise PanProfileError("pan outer profile is not monotonic")
    return pts


def inner_profile(*, outside_diameter, depth, wall, floor, floor_radius,
                  z0=0.0, samples=None):
    """Inner cavity profile, bottom-up, from the floor face to the rim."""
    samples = samples or TOPOLOGY["base_corner_samples"]
    r_in = outside_diameter / 2.0 - wall
    fr = min(float(floor_radius), r_in - 1e-6, depth - floor - 1e-6)
    if r_in <= 0:
        raise PanProfileError(
            f"wall {wall} consumes the pan radius {outside_diameter / 2.0}")
    if depth - floor <= 0:
        raise PanProfileError(
            f"floor {floor} consumes the pan depth {depth}")
    zf = z0 + floor
    pts = [(0.0, zf)]
    if fr > 0:
        pts.append((r_in - fr, zf))
        cx, cz = r_in - fr, zf + fr
        for i in range(1, samples + 1):
            a = -math.pi / 2 + (math.pi / 2) * i / samples
            pts.append((cx + fr * math.cos(a), cz + fr * math.sin(a)))
    else:
        pts.append((r_in, zf))
    pts.append((r_in, z0 + depth))
    return pts


def _ring(cx, cy, r, z, segments, table):
    out = []
    for i in range(segments):
        a = math.radians(45.0) + 2 * math.pi * i / segments
        out.append(table(cx + r * math.cos(a), cy + r * math.sin(a), z))
    return out


def build_metal_pan(name, *, centre=(0.0, 0.0), z0=0.0, role="",
                    **overrides) -> dict:
    """A closed, manifold drawn-pan shell with a radiused outer base.

    Built as one surface: outer profile bottom-up, across the rim, inner
    profile top-down, closed by the base cap — so it is watertight without
    welding, the same discipline as the tray kernel.
    """
    cfg = contract_values()
    cfg.update(overrides)
    seg = TOPOLOGY["radial_segments"]
    quant = TOPOLOGY["coordinate_quantization"]
    verts, index = [], {}

    def add(x, y, z):
        key = (round(x / quant), round(y / quant), round(z / quant))
        if key not in index:
            index[key] = len(verts)
            verts.append((float(x), float(y), float(z)))
        return index[key]

    outer = outer_profile(outside_diameter=cfg["pan_outside_diameter_mm"],
                          depth=cfg["pan_depth_mm"],
                          base_corner_radius=cfg["base_corner_radius_mm"],
                          side_wall_draft_deg=cfg["side_wall_draft_deg"],
                          z0=z0)
    inner = inner_profile(outside_diameter=cfg["pan_outside_diameter_mm"],
                          depth=cfg["pan_depth_mm"],
                          wall=cfg["metal_wall_thickness_mm"],
                          floor=cfg["metal_floor_thickness_mm"],
                          floor_radius=cfg["floor_radius_mm"], z0=z0)

    cx, cy = centre
    faces: list = []
    # outer skin, bottom-up
    loops = [_ring(cx, cy, r, z, seg, add) for r, z in outer]
    for a, b in zip(loops, loops[1:]):
        _strip(faces, a, b)
    # rim: outer top -> inner top
    rim_in = _ring(cx, cy, inner[-1][0], inner[-1][1], seg, add)
    _strip(faces, loops[-1], rim_in)
    # inner skin, top-down
    inner_loops = [rim_in] + [_ring(cx, cy, r, z, seg, add)
                              for r, z in reversed(inner[1:-1])]
    for a, b in zip(inner_loops, inner_loops[1:]):
        _strip(faces, a, b)
    # cap directions follow from _strip's convention: it emits loop_a's
    # edges backwards and loop_b's forwards. inner_loops[-1] is a loop_B
    # (forward), so its cap must run backwards; loops[0] is a loop_A
    # (backward), so its cap must run forwards. Getting either wrong leaves
    # the surface inconsistently oriented while still looking closed.
    centre_in = add(cx, cy, inner[0][1])
    _fan(faces, inner_loops[-1], centre_in, flip=True)
    # base cap
    centre_out = add(cx, cy, z0)
    _fan(faces, loops[0], centre_out, flip=False)

    v = np.asarray(verts, dtype=float)
    f = np.asarray(faces, dtype=np.int64)
    a = v[f[:, 0]]
    signed = float(np.einsum("ij,ij->i", a,
                             np.cross(v[f[:, 1]] - a,
                                      v[f[:, 2]] - a)).sum() / 6.0)
    if signed < 0:
        f = f[:, [0, 2, 1]]
    identity = hashlib.sha256(
        np.round(v, 6).tobytes() + f.tobytes()
        + repr(sorted(TOPOLOGY.items())).encode()).hexdigest()[:16]
    return {"name": name, "schema": SCHEMA, "vertices": v, "faces": f,
            "mesh_identity": identity, "role": role,
            "outer_profile": [[round(r, 9), round(z, 9)] for r, z in outer],
            "inner_profile": [[round(r, 9), round(z, 9)] for r, z in inner],
            "config": cfg, "centre_mm": [cx, cy], "z0_mm": z0,
            "flat_base_radius_mm": round(
                cfg["pan_outside_diameter_mm"] / 2.0
                - cfg["base_corner_radius_mm"], 9),
            "pan_edge_profile_authority": PAN_EDGE_PROFILE_AUTHORITY,
            "pan_manufacturing_authority": PAN_MANUFACTURING_AUTHORITY}


def _strip(faces, a, b):
    n = len(a)
    for i in range(n):
        j = (i + 1) % n
        faces.append((a[i], b[i], b[j]))
        faces.append((a[i], b[j], a[j]))


def _fan(faces, loop, centre, flip=False):
    n = len(loop)
    for i in range(n):
        j = (i + 1) % n
        faces.append((loop[j], loop[i], centre) if flip
                     else (loop[i], loop[j], centre))
