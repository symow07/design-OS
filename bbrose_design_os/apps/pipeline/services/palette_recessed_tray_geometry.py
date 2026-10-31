"""PALT-M4B-A — deterministic recessed-tray kernel.

Authority (owner decision 2026-08-06):

* ``PALETTE_TRAY_GEOMETRY_AUTHORITY: DETERMINISTIC_PYTHON_MESH_CONSTRUCTION``
* ``BLENDER_ROLE: VISUALIZATION_AND_RENDERING_ONLY``
* ``BLENDER_BOOLEAN_MODIFIERS: NOT_AUTHORITY_FOR_CORE_TRAY_GEOMETRY``

There is **no silent Boolean fallback**: if the builder cannot produce a
watertight tray it raises :class:`RecessedTrayError`.

Topology strategy (versioned — changing any constant changes the mesh
identity):

The tray field is a 3x3 cell lattice, one pocket per cell. Every lattice
boundary vertex is generated **once** into a global index map and reused
by both adjacent cells, so there are no cracks and no T-junctions by
construction — exact shared indices, not tolerance welding.

Surfaces, each sharing its boundary loop with the next:

    deck strips (cell boundary -> pocket rim)
    pocket walls (rim -> drafted floor circle)
    pocket floor caps
    border strip (lattice outer loop -> tray outer loop)
    outer side wall (tray outer loop -> underside loop)
    underside cap

Every manifold edge therefore has exactly two incident faces.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "palette_recessed_tray/1.0"

# --- versioned topology constants -----------------------------------------
TOPOLOGY = {
    "version": "recessed_tray_topology/1.0",
    "cells_x": 3,
    "cells_y": 3,
    "cell_edge_samples": 16,        # S — samples per cell edge
    "pocket_segments": 64,          # N = 4 * S (exact strip correspondence)
    "fillet_arc_samples": 5,        # K — segments per tangent fillet arc
    "draft_strategy": "LINEAR_TAPER_FROM_RIM_TO_FLOOR",
    "fillet_strategy": "TANGENT_ARC_RIM_AND_FLOOR_FILLETS",
    "coordinate_quantization": 1e-6,
    "weld_tolerance": None,         # exact shared indices — no welding
    "outer_loop_samples": 192,      # 4 * 3 * S — matches the lattice loop
}
assert TOPOLOGY["pocket_segments"] == 4 * TOPOLOGY["cell_edge_samples"]
assert TOPOLOGY["outer_loop_samples"] == \
    4 * TOPOLOGY["cells_x"] * TOPOLOGY["cell_edge_samples"]

QUANT = TOPOLOGY["coordinate_quantization"]


class RecessedTrayError(ValueError):
    """Raised when the deterministic tray cannot be built (fail closed)."""


class VertexTable:
    """Exact shared-index vertex store keyed by quantized coordinates."""

    def __init__(self, quant=QUANT):
        self._index = {}
        self.vertices = []
        self.quant = quant
        self.reuse_count = 0

    def key(self, x, y, z):
        q = self.quant
        return (round(x / q), round(y / q), round(z / q))

    def add(self, x, y, z) -> int:
        k = self.key(x, y, z)
        idx = self._index.get(k)
        if idx is not None:
            self.reuse_count += 1
            return idx
        idx = len(self.vertices)
        self._index[k] = idx
        self.vertices.append((float(x), float(y), float(z)))
        return idx


def _cell_boundary_points(cx, cy, half, samples):
    """Cell boundary, CCW, starting at the (+x,+y) corner. Exactly
    ``4 * samples`` points; adjacent cells produce identical coordinates
    on their shared edge, so the table returns identical indices."""
    corners = [(cx + half, cy + half), (cx - half, cy + half),
               (cx - half, cy - half), (cx + half, cy - half)]
    pts = []
    for i in range(4):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % 4]
        for s in range(samples):
            t = s / samples
            pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    return pts


def _circle_points(cx, cy, r, segments, start_deg=45.0):
    """Pocket rim, CCW, starting at 45 deg so index correspondence with the
    cell boundary (which starts at the +x,+y corner) is monotonic in
    angle — the strip can never self-cross."""
    a0 = math.radians(start_deg)
    return [(cx + r * math.cos(a0 + 2 * math.pi * i / segments),
             cy + r * math.sin(a0 + 2 * math.pi * i / segments))
            for i in range(segments)]


def _rounded_rect_uniform(w, d, radius, count):
    """Rounded rectangle sampled at ``count`` points by uniform perimeter
    parameter, starting at the (+x,+y) corner region and running CCW so it
    corresponds index-for-index with the lattice outer loop.

    The parameter origin is the 45 deg point of the (+x,+y) arc, which is
    the same direction as the lattice loop's (+x,+y) corner — so the border
    strip between them is not sheared.

    Yields ``(x, y, nx, ny)`` where ``(nx, ny)`` is the unit INWARD normal.
    Offsetting along it is an exact rounded-rect offset, so the drafted
    outer wall corresponds index-for-index with zero shear."""
    r = max(0.0, min(radius, min(w, d) / 2.0 - 1e-9))
    hw, hd = w / 2.0 - r, d / 2.0 - r
    straight_x, straight_y = 2 * hw, 2 * hd
    arc = (math.pi / 2) * r
    perim = 2 * straight_x + 2 * straight_y + 4 * arc
    # segment table starting at the +x,+y corner arc, CCW
    segs = [("arc", (hw, hd), 0.0), ("line_top", None, straight_x),
            ("arc", (-hw, hd), math.pi / 2), ("line_left", None, straight_y),
            ("arc", (-hw, -hd), math.pi), ("line_bottom", None, straight_x),
            ("arc", (hw, -hd), 3 * math.pi / 2),
            ("line_right", None, straight_y)]
    lengths = [arc if s[0] == "arc" else s[2] for s in segs]
    origin = arc / 2.0                   # 45 deg into the (+x,+y) arc
    pts = []
    for i in range(count):
        s = (origin + (i / count) * perim) % perim
        acc = 0.0
        for (kind, data, extent), ln in zip(segs, lengths):
            if s <= acc + ln or ln == 0.0:
                local = (s - acc) / ln if ln else FT.traced_zero("palette_recessed_tray_geometry.py:_rounded_rect_uniform", "guard")
                if kind == "arc":
                    ax, ay = data
                    a = extent + local * (math.pi / 2)
                    ca, sa = math.cos(a), math.sin(a)
                    pts.append((ax + r * ca, ay + r * sa, -ca, -sa))
                elif kind == "line_top":
                    pts.append((hw - local * straight_x, hd + r, 0.0, -1.0))
                elif kind == "line_left":
                    pts.append((-hw - r, hd - local * straight_y, 1.0, 0.0))
                elif kind == "line_bottom":
                    pts.append((-hw + local * straight_x, -hd - r, 0.0, 1.0))
                else:
                    pts.append((hw + r, -hd + local * straight_y, -1.0, 0.0))
                break
            acc += ln
        else:                                    # pragma: no cover
            raise RecessedTrayError("perimeter parameterisation failed")
    return pts


def _pocket_profile(pocket_r, deck_z, floor_z, draft_deg, rim_fil, floor_fil,
                    samples):
    """The pocket's (radius, z) profile rings, deck tangent -> floor tangent.

    ``pocket_r`` is the THEORETICAL SHARP-CORNER radius at the deck plane:
    the drafted wall line extrapolated up to ``deck_z``. Both fillets are
    tangent to that same wall line, so changing a fillet radius never moves
    the wall — only the extent of the flat deck and flat floor.

    Returns ``(rings, flat_floor_radius, tangents)``.
    """
    th = math.radians(draft_deg)
    sin_t, cos_t, tan_t = math.sin(th), math.cos(th), math.tan(th)
    wall_r = lambda z: pocket_r - (deck_z - z) * tan_t     # noqa: E731

    # rim fillet — convex, tangent to the horizontal deck and to the wall
    a = rim_fil
    z_t1 = deck_z - a * (1.0 - sin_t)
    c_r1, c_z1 = wall_r(z_t1) + a * cos_t, deck_z - a
    # floor fillet — concave, tangent to the wall and to the flat floor
    b = floor_fil
    z_t2 = floor_z + b * (1.0 - sin_t)
    c_r2, c_z2 = wall_r(z_t2) - b * cos_t, floor_z + b

    if z_t2 >= z_t1:
        raise RecessedTrayError(
            f"rim fillet {a} and floor fillet {b} overlap: the wall tangents "
            f"meet at z {z_t1:.4f} and {z_t2:.4f} over a {deck_z - floor_z} "
            "mm pocket")
    if c_r2 <= 0.2:
        raise RecessedTrayError(
            f"floor fillet {b} collapses the flat pocket floor "
            f"(radius {c_r2:.4f} mm)")

    rings = []
    for i in range(samples + 1):                      # 90 deg -> 180-th
        ang = math.pi / 2 + (math.pi / 2 - th) * i / samples
        rings.append((c_r1 + a * math.cos(ang), c_z1 + a * math.sin(ang)))
    for i in range(samples + 1):                      # -th -> -90 deg
        ang = -th + (-math.pi / 2 + th) * i / samples
        rings.append((c_r2 + b * math.cos(ang), c_z2 + b * math.sin(ang)))

    for (r0, z0), (r1, z1) in zip(rings, rings[1:]):
        if r1 > r0 + 1e-9 or z1 > z0 + 1e-9:
            raise RecessedTrayError(
                "pocket profile is not monotonic — it would self-intersect")
    return rings, c_r2, {"deck_tangent_radius_mm": round(c_r1, 6),
                         "wall_top_z_mm": round(z_t1, 6),
                         "wall_bottom_z_mm": round(z_t2, 6),
                         "flat_floor_radius_mm": round(c_r2, 6)}


def _strip(faces, loop_a, loop_b):
    """Two triangles per quad between two equal-length ordered loops."""
    n = len(loop_a)
    if n != len(loop_b):
        raise RecessedTrayError("strip loops differ in length")
    for i in range(n):
        j = (i + 1) % n
        faces.append((loop_a[i], loop_b[i], loop_b[j]))
        faces.append((loop_a[i], loop_b[j], loop_a[j]))


def _fan(faces, loop, centre, flip=False):
    n = len(loop)
    for i in range(n):
        j = (i + 1) % n
        if flip:
            faces.append((loop[j], loop[i], centre))
        else:
            faces.append((loop[i], loop[j], centre))


def build_recessed_palette_tray(spec: dict) -> dict:
    """One continuous, manifold, watertight moulded tray with nine
    recessed pockets. Pure Python — no Blender, no Boolean."""
    required = ("tray_width_mm", "tray_depth_mm", "deck_z_mm",
                "underside_z_mm", "pocket_floor_z_mm",
                "pocket_sharp_wall_theoretical_diameter_at_deck_mm",
                "pitch_mm", "pocket_draft_deg", "tray_draft_deg",
                "corner_radius_mm", "rim_fillet_mm", "floor_fillet_mm")
    # M4B-A2 §2: a bare "pocket diameter" is ambiguous across five distinct
    # datums (see palette_pocket_datums). Two active contracts assigned it
    # different meanings — 26.6 as a layout module, 26.8 as a cavity — and
    # M4B-A fed the layout value into the fit dimension. The field name is
    # retired rather than reinterpreted, so the confusion cannot recur.
    if "pocket_diameter_mm" in spec:
        raise RecessedTrayError(
            "'pocket_diameter_mm' is retired as ambiguous — name the datum: "
            "pocket_sharp_wall_theoretical_diameter_at_deck_mm is this "
            "kernel's input; POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM is "
            "what controls pan fit. See palette_pocket_datums.solve_sharp_"
            "wall_for_functional().")
    for key in required:
        if key not in spec:
            raise RecessedTrayError(f"missing required spec key {key!r}")
    w = float(spec["tray_width_mm"])
    d = float(spec["tray_depth_mm"])
    deck_z = float(spec["deck_z_mm"])
    under_z = float(spec["underside_z_mm"])
    floor_z = float(spec["pocket_floor_z_mm"])
    pocket_r = float(
        spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"]) / 2.0
    pitch = float(spec["pitch_mm"])
    draft = float(spec["pocket_draft_deg"])
    tray_draft = float(spec["tray_draft_deg"])
    corner_r = float(spec["corner_radius_mm"])
    rim_fil = float(spec["rim_fillet_mm"])
    floor_fil = float(spec["floor_fillet_mm"])

    if not (under_z < floor_z < deck_z):
        raise RecessedTrayError(
            f"elevations must satisfy underside {under_z} < pocket floor "
            f"{floor_z} < deck {deck_z}")
    depth = deck_z - floor_z
    cells_x, cells_y = TOPOLOGY["cells_x"], TOPOLOGY["cells_y"]
    S = TOPOLOGY["cell_edge_samples"]
    N = TOPOLOGY["pocket_segments"]
    K = TOPOLOGY["fillet_arc_samples"]
    rings, r_floor, tangents = _pocket_profile(
        pocket_r, deck_z, floor_z, draft, rim_fil, floor_fil, K)
    opening_r = tangents["deck_tangent_radius_mm"]
    field = cells_x * pitch
    if field > min(w, d) - 1e-9:
        raise RecessedTrayError(
            f"pan field {field} does not fit the tray {w} x {d}")
    if 2 * opening_r >= pitch - 1e-9:
        raise RecessedTrayError(
            f"pocket opening diameter {2 * opening_r:.4f} (sharp-corner "
            f"{2 * pocket_r} plus the {rim_fil} mm rim fillet) does not fit "
            f"the pitch {pitch}")

    table = VertexTable()
    faces: list = []
    half = pitch / 2.0
    pockets = []

    # --- deck strips + pocket walls + floors -----------------------------
    for row in range(cells_y):
        for col in range(cells_x):
            cx = (col - (cells_x - 1) / 2.0) * pitch
            cy = (row - (cells_y - 1) / 2.0) * pitch
            boundary = [table.add(x, y, deck_z)
                        for x, y in _cell_boundary_points(cx, cy, half, S)]
            # flat deck -> pocket opening (the rim fillet's upper tangent)
            prev = [table.add(x, y, deck_z)
                    for x, y in _circle_points(cx, cy, opening_r, N)]
            _strip(faces, boundary, prev)
            # rim fillet -> drafted wall -> floor fillet, ring by ring
            for r_ring, z_ring in rings[1:]:
                ring = [table.add(x, y, z_ring)
                        for x, y in _circle_points(cx, cy, r_ring, N)]
                _strip(faces, prev, ring)
                prev = ring
            centre = table.add(cx, cy, floor_z)
            _fan(faces, prev, centre, flip=True)
            pockets.append({"row": row, "col": col,
                            "centre_mm": [round(cx, 6), round(cy, 6)],
                            "sharp_corner_radius_mm": round(pocket_r, 6),
                            "opening_radius_mm": round(opening_r, 6),
                            "floor_radius_mm": round(r_floor, 6),
                            "depth_mm": round(depth, 6),
                            **tangents})

    # --- lattice outer loop (reuses the same boundary vertices) ----------
    lattice = []
    hf = field / 2.0
    for x, y in _cell_boundary_points(0.0, 0.0, hf, cells_x * S):
        lattice.append(table.add(x, y, deck_z))
    outer_count = TOPOLOGY["outer_loop_samples"]
    if len(lattice) != outer_count:
        raise RecessedTrayError(
            f"lattice loop {len(lattice)} != expected {outer_count}")

    outer_pts = _rounded_rect_uniform(w, d, corner_r, outer_count)
    outer_top = [table.add(x, y, deck_z) for x, y, _, _ in outer_pts]
    # loop order matters: ``_strip`` emits loop_a's edges backwards and
    # loop_b's forwards. The lattice loop is SHARED with the perimeter cell
    # boundaries, which already emitted it backwards, so it must appear as
    # loop_b here — otherwise both faces traverse it the same way and the
    # surface is not consistently oriented.
    _strip(faces, outer_top, lattice)

    # --- drafted outer side wall + underside ------------------------------
    # the tray releases upward, so the underside section is INSET
    inset = (deck_z - under_z) * math.tan(math.radians(tray_draft))
    if inset >= corner_r or 2 * inset >= min(w, d) - field:
        raise RecessedTrayError(
            f"tray draft {tray_draft} deg over height {deck_z - under_z} "
            f"insets the underside by {inset:.4f} mm, which collapses the "
            "outer wall")
    outer_bottom = [table.add(x + nx * inset, y + ny * inset, under_z)
                    for x, y, nx, ny in outer_pts]
    _strip(faces, outer_bottom, outer_top)
    under_centre = table.add(0.0, 0.0, under_z)
    _fan(faces, outer_bottom, under_centre, flip=False)

    vertices = np.asarray(table.vertices, dtype=float)
    faces_arr = np.asarray(faces, dtype=np.int64)
    mesh = {"vertices": vertices, "faces": faces_arr}
    _orient_outward(mesh)

    identity = hashlib.sha256(
        np.round(mesh["vertices"], 6).tobytes()
        + mesh["faces"].tobytes()
        + repr(sorted(TOPOLOGY.items())).encode()).hexdigest()[:16]
    return {
        "name": "recessed_palette_tray",
        "schema": SCHEMA,
        "vertices": mesh["vertices"],
        "faces": mesh["faces"],
        "mesh_identity": identity,
        "authority": "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION",
        "blender_role": "VISUALIZATION_AND_RENDERING_ONLY",
        "boolean_free": True,
        "topology": dict(TOPOLOGY),
        "shared_vertex_reuse_count": table.reuse_count,
        "weld_count": 0,
        "pockets": pockets,
        "elevations_mm": {"underside": under_z, "pocket_floor": floor_z,
                          "deck": deck_z},
        "pocket_floor_thickness_mm": round(floor_z - under_z, 6),
        "draft": {"tray_draft_deg": tray_draft,
                  "pocket_draft_deg": draft,
                  "tray_underside_inset_mm": round(inset, 6),
                  "release_direction": "UPWARD"},
        "fillets_mm": {"rim": rim_fil, "floor": floor_fil,
                       "strategy": TOPOLOGY["fillet_strategy"]},
        # 9 dp, not 6: the wall draft is measured from this profile as a
        # ratio of small differences, and 6 dp rounding alone shifts it by
        # ~2e-6 deg — enough to trip an exact draft validator
        "pocket_profile_rings": [[round(r, 9), round(z, 9)]
                                 for r, z in rings],
        "spec": dict(spec),
    }


def _orient_outward(mesh):
    """Consistent outward winding (positive signed volume)."""
    v, f = mesh["vertices"], mesh["faces"]
    a = v[f[:, 0]]
    signed = float(np.einsum("ij,ij->i", a,
                             np.cross(v[f[:, 1]] - a,
                                      v[f[:, 2]] - a)).sum() / 6.0)
    if signed < 0:
        mesh["faces"] = f[:, [0, 2, 1]]
