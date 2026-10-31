"""PALT-M4C §8 — rectangular metal pans.

ES3083 uses RECTANGULAR pans. The owner's rule is explicit: do not
approximate them by circles or by bounding boxes alone. This builds a
real rounded-rectangle drawn pan with the same discipline as the round
one — exact shared indices, closed manifold shell, analytic corner
radius, drafted side wall and a radiused base corner.

The round implementation in ``palette_pan_profile`` is untouched and
remains the PALT-P1A regression family.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

SCHEMA = "metal_pan_rectangular/1.0"

TOPOLOGY = {
    "version": "rect_pan_topology/1.0",
    "corner_samples": 8,          # per 90 deg corner arc
    "base_corner_samples": 6,     # per base-radius arc, in section
    "coordinate_quantization": 1e-6,
    "loop_samples": 32,           # 4 * corner_samples
}

RECT_PAN_CONTRACT = {
    # F1 2026-08-14 (f1_pan_redimension_ingestion.json): the owner ADOPTED
    # the measured cavity. Pan dims are SOLVED so the DERIVED sharp wall
    # at deck equals the calipered 20.40 x 20.30 at pocket depth 3.40 —
    # the pan is never assigned a pocket number (datum guard honoured).
    "pan_width_mm": (19.278392, "F1 MEASURED-adopted: solved for cavity "
                     "20.40 at deck (MEASURED_CALIPER_PHYSICAL_SAMPLE_"
                     "2026_08_14)"),
    "pan_height_mm": (19.178392, "F1 MEASURED-adopted: solved for cavity "
                      "20.30 at deck"),
    "pan_depth_mm": (3.40, "F1 MEASURED-adopted: the calipered cavity "
                     "depth; the drawn pan fills it (interpretation "
                     "recorded in the ingestion record)"),
    "corner_radius_mm": (2.0, "plan-view corner of the rectangle"),
    "side_wall_draft_deg": (0.0, "drawn pans are near straight-walled"),
    "base_corner_radius_mm": (0.30, "carried from the A3F selection"),
    "metal_wall_thickness_mm": (0.25, "PAN_SYSTEM drawn-pan wall"),
    "metal_floor_thickness_mm": (0.25, "PAN_SYSTEM drawn-pan floor"),
    "pocket_tolerance_mm": (0.40, "radial seating clearance per side"),
    "pocket_draft_deg": (2.0, "carried from the round pocket"),
    "adhesive_allowance_mm": (0.15, "carried"),
    "powder_crown_mm": (0.30, "carried"),
}

PAN_EDGE_PROFILE_AUTHORITY = "PROVISIONAL_DESIGN_DEFAULT"
PAN_MANUFACTURING_AUTHORITY = "NOT_ESTABLISHED"


class RectPanError(ValueError):
    """Raised when a rectangular pan is not constructible."""


def contract_values() -> dict:
    return {k: v[0] for k, v in RECT_PAN_CONTRACT.items()}


def rounded_rect_loop(w, d, radius, *, samples=None, centre=(0.0, 0.0)):
    """Plan-view rounded rectangle, CCW, exact corner arcs.

    Emits ``4 * samples`` points: each 90 deg corner is sampled and the
    straight runs are the arc endpoints, so the corner is a true radius
    rather than a chamfer or a bounding box.
    """
    n = samples or TOPOLOGY["corner_samples"]
    r = float(radius)
    hw, hd = w / 2.0 - r, d / 2.0 - r
    if r < 0 or hw < 0 or hd < 0:
        raise RectPanError(
            f"corner radius {r} does not fit a {w} x {d} rectangle")
    cx, cy = centre
    corners = [(hw, hd, 0.0), (-hw, hd, 90.0), (-hw, -hd, 180.0),
               (hw, -hd, 270.0)]
    pts = []
    for ox, oy, start in corners:
        for i in range(n):
            a = math.radians(start + 90.0 * i / n)
            ca, sa = math.cos(a), math.sin(a)
            # (x, y, inward normal). Every point sits on a corner arc, so
            # its normal is radial FROM ITS OWN ARC CENTRE - never radial
            # from the rectangle centre, which is the A3R defect: on a
            # straight run the centre direction is not perpendicular to
            # the edge, so a centre-radial offset thins the wall.
            pts.append((cx + ox + r * ca, cy + oy + r * sa, -ca, -sa))
    return pts


def section_profile(*, depth, base_corner_radius, side_wall_draft_deg,
                    z0=0.0, samples=None):
    """(inset, z) section of the pan wall, bottom-up.

    ``inset`` is how far the surface sits INSIDE the nominal rectangle, so
    the same profile drives every point of the rounded-rect loop.
    """
    n = samples or TOPOLOGY["base_corner_samples"]
    br = float(base_corner_radius)
    if br < 0 or br > depth:
        raise RectPanError(
            f"base corner radius {br} does not fit depth {depth}")
    pts = [(br, z0)]
    if br > 0:
        for i in range(1, n + 1):
            a = -math.pi / 2 + (math.pi / 2) * i / n
            pts.append((br - br * math.cos(a) * 0 - (br + br * math.cos(
                a + math.pi)) * 0 + br * (1 - math.sin(a + math.pi / 2)
                                          ) * 0 + br - br * math.sin(
                a + math.pi / 2) * 0, z0))
    # analytic: inset(z) = br - sqrt(br^2 - (br - (z - z0))^2) for the arc
    pts = [(br, z0)]
    if br > 0:
        for i in range(1, n + 1):
            dz = br * i / n
            pts.append((br - math.sqrt(max(br * br - (br - dz) ** 2, 0.0)),
                        z0 + dz))
    th = math.radians(side_wall_draft_deg)
    pts.append((-(depth - br) * math.tan(th), z0 + depth))
    return pts


def _offset_loop(loop, inset, centre=(0.0, 0.0)):
    """Exact parallel offset along each point's own inward normal."""
    return [(x + nx * inset, y + ny * inset) for x, y, nx, ny in loop]


def _plain(loop):
    return [(x, y) for x, y, _, _ in loop]


def build_rect_pan(name, *, centre=(0.0, 0.0), z0=0.0, role="",
                   **overrides) -> dict:
    """Closed, manifold rounded-rectangle drawn pan."""
    cfg = contract_values()
    cfg.update(overrides)
    w, d = cfg["pan_width_mm"], cfg["pan_height_mm"]
    depth = cfg["pan_depth_mm"]
    wall = cfg["metal_wall_thickness_mm"]
    floor = cfg["metal_floor_thickness_mm"]
    if wall * 2 >= min(w, d):
        raise RectPanError("wall consumes the pan")
    if floor >= depth:
        raise RectPanError("floor consumes the depth")

    quant = TOPOLOGY["coordinate_quantization"]
    verts, index = [], {}

    def add(x, y, z):
        k = (round(x / quant), round(y / quant), round(z / quant))
        if k not in index:
            index[k] = len(verts)
            verts.append((float(x), float(y), float(z)))
        return index[k]

    base = rounded_rect_loop(w, d, cfg["corner_radius_mm"], centre=centre)
    sect = section_profile(depth=depth,
                           base_corner_radius=cfg["base_corner_radius_mm"],
                           side_wall_draft_deg=cfg["side_wall_draft_deg"],
                           z0=z0)
    faces = []

    def strip(a, b):
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            faces.append((a[i], b[i], b[j]))
            faces.append((a[i], b[j], a[j]))

    def fan(loop, c, flip=False):
        n = len(loop)
        for i in range(n):
            j = (i + 1) % n
            faces.append((loop[j], loop[i], c) if flip
                         else (loop[i], loop[j], c))

    outer = [[add(x, y, z) for x, y in _offset_loop(base, inset, centre)]
             for inset, z in sect]
    for a, b in zip(outer, outer[1:]):
        strip(a, b)

    inner_loop = _offset_loop(base, wall, centre)
    rim_in = [add(x, y, z0 + depth) for x, y in inner_loop]
    strip(outer[-1], rim_in)
    floor_in = [add(x, y, z0 + floor) for x, y in inner_loop]
    strip(rim_in, floor_in)
    # cap direction follows strip's convention: it emits loop_a backwards
    # and loop_b forwards. floor_in arrived as a loop_B, outer[0] as a
    # loop_A, so their caps run the opposite way to each other.
    c_in = add(centre[0], centre[1], z0 + floor)
    fan(floor_in, c_in, flip=True)
    c_out = add(centre[0], centre[1], z0)
    fan(outer[0], c_out, flip=False)

    v = np.asarray(verts, float)
    f = np.asarray(faces, np.int64)
    a0 = v[f[:, 0]]
    signed = float(np.einsum("ij,ij->i", a0,
                             np.cross(v[f[:, 1]] - a0,
                                      v[f[:, 2]] - a0)).sum() / 6.0)
    if signed < 0:
        f = f[:, [0, 2, 1]]
    ident = hashlib.sha256(
        np.round(v, 6).tobytes() + f.tobytes()
        + repr(sorted(TOPOLOGY.items())).encode()
        + repr(sorted(cfg.items())).encode()).hexdigest()[:16]
    return {"name": name, "schema": SCHEMA, "vertices": v, "faces": f,
            "mesh_identity": ident, "role": role, "config": cfg,
            "pan_shape": "RECTANGULAR",
            "plan_loop_points": len(base),
            "section_profile": [[round(i, 9), round(z, 9)]
                                for i, z in sect],
            "flat_base_inset_mm": round(cfg["base_corner_radius_mm"], 9),
            "pan_edge_profile_authority": PAN_EDGE_PROFILE_AUTHORITY,
            "pan_manufacturing_authority": PAN_MANUFACTURING_AUTHORITY}


def pocket_envelope(cfg=None) -> dict:
    """The FUNCTIONAL cross-section the pan seats in — a named datum.

    This is measured AT THE SEATING DATUM, not at the deck plane. A
    drafted pocket narrows downward, so these numbers are smaller than the
    tray kernel's construction input; passing them straight into
    ``palette_rect_tray_geometry`` as sharp-wall-at-deck would tighten the
    real fit by the draft taken over the pocket depth. Convert with
    ``palette_rect_tray_geometry.solve_rect_sharp_wall_for_functional()``.
    """
    c = dict(contract_values())
    c.update(cfg or {})
    tol = c["pocket_tolerance_mm"]
    return {"record_type": "rect_pocket_envelope/1.0",
            "datum": "FUNCTIONAL_CLEARANCE_AT_SEATING_DATUM",
            "functional_width_at_seating_datum_mm": round(
                c["pan_width_mm"] + 2 * tol, 6),
            "functional_height_at_seating_datum_mm": round(
                c["pan_height_mm"] + 2 * tol, 6),
            "functional_corner_radius_at_seating_datum_mm": round(
                c["corner_radius_mm"] + tol, 6),
            "pocket_draft_deg": c["pocket_draft_deg"],
            "seating_clearance_per_side_mm": tol,
            "adhesive_allowance_mm": c["adhesive_allowance_mm"],
            "note": "the pocket corner radius grows with the tolerance, so "
                    "the offset stays a true rounded rectangle rather than "
                    "a scaled one",
            "authority": "PROVISIONAL_DESIGN_DEFAULT"}
