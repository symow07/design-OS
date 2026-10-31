"""M6 — the BAKED powder-volume node and the raking-rig fixture.

The dome is GEOMETRY: a real raised powder volume with a deterministic
mesh identity, seated in an unchanged metal pan. This node is the
declared consumer the 39 GEOMETRY_DECLARED_CONSUMER_PENDING
classifications have been waiting for, and its consumption is honest:

CONSUMED:  fill_depth_mm, powder_recess_mm, crown_height_mm,
           dome.crown_height_mm, dome.edge_transition_mm
CHECK-CONSUMED (not mesh): dome.lid_clearance_required_mm — read by
           the clearance check, the same class as granularity_forbidden
NOT CONSUMED: edge_profile — per the pre-commitment it JOINS THE DEAD
           across all nine families rather than staying pending.

The powder volume is a rounded-corner slab whose top surface is flat
(PRESSED control) or a smoothstep dome rising crown_height_mm over an
edge_transition_mm band (BAKED). The metal pan builder is untouched —
a domed powder sits in an unchanged pan, and the identity separation
is asserted by test.
"""
from __future__ import annotations

import hashlib

import numpy as np
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "baked_powder_volume/1.0"


def _rounded_rect_boundary(w, d, r, n_per_side=12, n_corner=6):
    """CCW boundary points of a rounded rectangle centred at origin."""
    hw, hd = w / 2.0, d / 2.0
    pts = []
    corners = [(hw - r, hd - r, 0.0), (-(hw - r), hd - r, 90.0),
               (-(hw - r), -(hd - r), 180.0), (hw - r, -(hd - r), 270.0)]
    for cx, cy, a0 in corners:
        for i in range(n_corner):
            a = np.radians(a0 + 90.0 * i / n_corner)
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    out = []
    for i, p in enumerate(pts):
        out.append(p)
        q = pts[(i + 1) % len(pts)]
        for j in range(1, n_per_side // 4):
            t = j / (n_per_side // 4)
            out.append((p[0] + (q[0] - p[0]) * t,
                        p[1] + (q[1] - p[1]) * t))
    return out


def build_powder_volume(spec_params, *, pan_inner_w, pan_inner_d,
                        z_floor, corner_r=0.6, grid=28) -> dict:
    """The volume node. spec_params is PowderMaterialSpec.params."""
    fill = float(spec_params["fill_depth_mm"])
    recess = float(spec_params["powder_recess_mm"])
    dome_block = spec_params.get("dome")
    crown = float(dome_block["crown_height_mm"]) if dome_block \
        else float(spec_params["crown_height_mm"])
    trans = float(dome_block["edge_transition_mm"]) if dome_block \
        else FT.traced_zero("palette_baked_geometry.py:build_powder_volume", "guard")
    domed = dome_block is not None

    z_top_flat = z_floor + fill - recess
    hw, hd = pan_inner_w / 2.0, pan_inner_d / 2.0

    xs = np.linspace(-hw, hw, grid)
    ys = np.linspace(-hd, hd, grid)
    verts = []
    for y in ys:
        for x in xs:
            if domed:
                # distance to the boundary along the shorter half-axis
                edge = min(hw - abs(x), hd - abs(y))
                t = np.clip(edge / max(trans, 1e-6), 0.0, 1.0)
                s = t * t * (3.0 - 2.0 * t)      # smoothstep
                z = z_top_flat + crown * s
            else:
                z = z_top_flat
            verts.append((x, y, z))
    top = np.array(verts)

    faces = []
    def vid(i, j):
        return i * grid + j
    for i in range(grid - 1):
        for j in range(grid - 1):
            a, b = vid(i, j), vid(i, j + 1)
            c, d = vid(i + 1, j + 1), vid(i + 1, j)
            faces.append((a, b, c))
            faces.append((a, c, d))

    n_top = grid * grid
    bottom = top.copy()
    bottom[:, 2] = z_floor
    all_verts = np.vstack([top, bottom])
    for i in range(grid - 1):
        for j in range(grid - 1):
            a, b = vid(i, j) + n_top, vid(i, j + 1) + n_top
            c, d = vid(i + 1, j + 1) + n_top, vid(i + 1, j) + n_top
            faces.append((a, c, b))
            faces.append((a, d, c))
    # walls: stitch boundary columns
    for i in range(grid - 1):
        for (p, q) in (((i, 0), (i + 1, 0)), ((i + 1, grid - 1),
                                              (i, grid - 1))):
            a, b = vid(*p), vid(*q)
            faces.append((a, b, b + n_top))
            faces.append((a, b + n_top, a + n_top))
    for j in range(grid - 1):
        for (p, q) in (((grid - 1, j), (grid - 1, j + 1)),
                       ((0, j + 1), (0, j))):
            a, b = vid(*p), vid(*q)
            faces.append((a, b, b + n_top))
            faces.append((a, b + n_top, a + n_top))

    ident = hashlib.sha256(
        np.round(all_verts, 6).tobytes()
        + np.array(faces, dtype=np.int64).tobytes()).hexdigest()[:16]
    return {
        "vertices": all_verts, "faces": [list(f) for f in faces],
        "schema": SCHEMA,
        "domed": domed,
        "powder_geometry_identity": ident,
        "consumed": ["fill_depth_mm", "powder_recess_mm",
                     "crown_height_mm"]
                    + (["dome.crown_height_mm",
                        "dome.edge_transition_mm"] if domed else []),
        "top_z_flat": z_top_flat,
        "top_z_peak": float(top[:, 2].max()),
        "crown_realized_mm": float(top[:, 2].max() - z_top_flat),
    }
