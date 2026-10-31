"""PALT-M4C §8 — recessed RECTANGULAR pockets for the ES3083 pilot tray.

PALT-P1A's tray kernel recesses nine circular pockets in a 3x3 square
lattice and its mesh identity is frozen as an engineering regression
fixture. ES3083 uses rectangular pans in a wider grid, so this is a
SEPARATE family rather than an edit to that kernel: nothing here can move
``palette_recessed_tray_geometry``'s identity, and the round pilot keeps
its meaning.

The construction discipline is inherited unchanged — exact shared-index
vertices, no tolerance welding, no Boolean, fail closed.

The pocket wall is a TRUE NORMAL OFFSET. A rounded rectangle offset
inwards by ``t`` along its own normals is another rounded rectangle of
``(W - 2t) x (H - 2t)`` with corner radius ``R - t``; scaling the loop
instead would deliver ``t`` on the straight walls and something smaller
in the corners. That is the defect PALT-M4B-A3R localized in the round
pocket and PALT-M4C §8 found again in the rectangular pan, so the offset
is asserted, not assumed.

No dimension here is authoritative. The ES3083 sheet carries no readable
millimetre value (see ``palette_es3083_intent`` unresolved_regions), so
every default is a PROVISIONAL_DESIGN_DEFAULT and the record says so.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from apps.pipeline.services import palette_rect_pan as rect_pan
from apps.pipeline.services.palette_recessed_tray_geometry import (
    RecessedTrayError, VertexTable, _fan, _orient_outward,
    _pocket_profile, _rounded_rect_uniform, _strip,
)

SCHEMA = "palette_recessed_tray_rectangular/1.0"

TOPOLOGY = {
    "version": "rect_tray_topology/1.0",
    "cell_edge_samples_x": 12,        # samples along a cell's x edge
    "cell_edge_samples_y": 10,
    "fillet_arc_samples": 5,
    "coordinate_quantization": 1e-6,
    "join_tolerance": None,
    "weld_strategy": "EXACT_SHARED_INDEX_NO_TOLERANCE_WELD",
    "fillet_strategy": "TANGENT_ARC_WALL_LINE_PRESERVED",
    "pocket_wall_offset": "TRUE_NORMAL_OFFSET",
}
POCKET_SEGMENTS = 2 * (TOPOLOGY["cell_edge_samples_x"]
                       + TOPOLOGY["cell_edge_samples_y"])

# Provisional geometry. NOT owner-approved, NOT manufacturing authority.
RECT_TRAY_DEFAULTS = {
    "cells_x": 4, "cells_y": 3,        # ES3083 SOFT reading, overridable
    # derived at import from the pan field and the inter-pocket land so the
    # border follows the design's "tight margins"; see _derive_pocket_defaults
    "tray_width_mm": 118.0, "tray_depth_mm": 70.0,
    # F1 2026-08-14: pitch is the calipered centre-to-centre (MEASURED,
    # owner-adopted); deck/floor elevations moved so the tray carries the
    # measured 3.40 pocket depth — the elevations themselves stay HIDDEN
    # generic construction (f1_pan_redimension_ingestion.json).
    "deck_z_mm": 4.4, "underside_z_mm": 0.0, "pocket_floor_z_mm": 1.0,
    "pitch_x_mm": 22.0, "pitch_y_mm": 21.9,
    "pocket_draft_deg": 3.0, "tray_draft_deg": 2.0,
    # F1 consequence: at the measured pitch the derived border margin
    # tightens to 0.936 mm and the old 4.0 outline corner produced two
    # deck T-junctions (caught by the mesh validator, verified by sweep:
    # 4.0 -> 2, {2.0, 0.9, 0.5} -> 0). 2.0 matches the pan's own corner
    # radius. HIDDEN generic construction, moved with its cause named.
    "corner_radius_mm": 2.0, "rim_fillet_mm": 0.35, "floor_fillet_mm": 0.35,
}

# The grid is a SOFT reading at confidence 0.55 whose source explicitly
# records "exact pan count and grid (4x3 assumed, SOFT)". It is parametric
# so the soft reading cannot harden into a constant.
GRID_AUTHORITY = {
    "source": "ES3083 rendered open case, counted from a small render",
    "constraint_level": "SOFT_VISUAL_CONSTRAINT",
    "confidence": 0.55,
    "confirmation_state": "PENDING_OWNER_CONFIRMATION",
    "why": "palette_es3083_intent records rows=3 / columns=4 as SOFT and "
           "lists the exact grid among its unresolved regions",
}

DIMENSIONAL_AUTHORITY = {
    "source": "MEASURED_CALIPER_OWNER_ADOPTED_F1_2026_08_14",
    "why": "the production sheet still carries no readable millimetre "
           "value, but the PHYSICAL SAMPLE was calipered (cavity "
           "20.40 x 20.30 x 3.40, pitch 22.00 x 21.90) and the owner "
           "ADOPTED the measurement (OWNER_BLOCKER_CLEARANCE.md §F1, "
           "f1_pan_redimension_ingestion.json); the pocket envelope "
           "still DERIVES from the pan contract plus tolerance — the "
           "pan dims were solved so the derived deck cavity equals the "
           "measurement",
    "elevations": "deck/underside/floor z remain HIDDEN generic "
                  "construction; only depth (3.40) is measured",
    "final_dimensions": "NOT_APPROVED",
    "final_dimensions_note": "pan/pitch adoption is not a case-level "
                             "final-dimension approval",
    "manufacturing_authority": "NOT_ESTABLISHED",
    "owner_approval": "NOT_GRANTED",
    "owner_approval_note": "F1 grants the pan cavity + pitch adoption "
                           "ONLY",
}


def _derive_pocket_defaults():
    """Solve the deck-plane construction input from the pan contract.

    Hand-copying the pocket dimensions would let the pan tolerance change
    without the tray following — the two modules would silently
    desynchronise. Deriving them makes the link explicit and checkable.
    """
    d = RECT_TRAY_DEFAULTS
    sol = solve_rect_sharp_wall_for_functional(
        rect_pan.pocket_envelope(), deck_z=d["deck_z_mm"],
        floor_z=d["pocket_floor_z_mm"], draft_deg=d["pocket_draft_deg"],
        rim_fillet=d["rim_fillet_mm"], floor_fillet=d["floor_fillet_mm"])
    for key in ("pocket_sharp_wall_width_at_deck_mm",
                "pocket_sharp_wall_height_at_deck_mm",
                "pocket_sharp_wall_corner_radius_at_deck_mm"):
        RECT_TRAY_DEFAULTS[key] = sol[key]

    # M4C-8 finding: an arbitrary tray envelope gave 3.8 mm border margins
    # against a 1.18 mm inter-pocket land, which is not the "tight margins"
    # the ES3083 intent reads. The envelope is a PROVISIONAL default with
    # no authoritative source, so it follows the design rather than sitting
    # at a number nobody chose. The fidelity THRESHOLD was not touched —
    # the metric still fails for an envelope that contradicts the intent.
    open_off = sol["deck_opening_offset_mm"]
    land_x = d["pitch_x_mm"] - (sol["pocket_sharp_wall_width_at_deck_mm"]
                                + 2 * open_off)
    land_y = d["pitch_y_mm"] - (sol["pocket_sharp_wall_height_at_deck_mm"]
                                + 2 * open_off)
    margin = round(min(land_x, land_y), 6)
    d["tray_width_mm"] = round(d["cells_x"] * d["pitch_x_mm"] + 2 * margin, 6)
    d["tray_depth_mm"] = round(d["cells_y"] * d["pitch_y_mm"] + 2 * margin, 6)
    sol["derived_border_margin_mm"] = margin
    sol["derived_tray_width_mm"] = d["tray_width_mm"]
    sol["derived_tray_depth_mm"] = d["tray_depth_mm"]
    return sol


class RectTrayError(ValueError):
    """Raised when a rectangular tray cannot be built exactly."""


# Bare pocket dimensions are ambiguous across the same datums that made
# 26.6 and 26.8 look like a disagreement when they were two different
# measurements. The round kernel retired ``pocket_diameter_mm`` for this
# reason; the rectangular family refuses the equivalent names rather than
# inheriting the confusion.
RETIRED_AMBIGUOUS_KEYS = {
    "pocket_width_mm": "pocket_sharp_wall_width_at_deck_mm",
    "pocket_height_mm": "pocket_sharp_wall_height_at_deck_mm",
    "pocket_corner_radius_mm": "pocket_sharp_wall_corner_radius_at_deck_mm",
    "pocket_diameter_mm": "this family is rectangular; there is no diameter",
}


def solve_rect_sharp_wall_for_functional(envelope, *, deck_z, floor_z,
                                         draft_deg, rim_fillet, floor_fillet,
                                         seating_z=None, samples=None):
    """Convert a FUNCTIONAL clearance at the seating datum into the
    kernel's SHARP-WALL-AT-DECK construction input.

    ``palette_rect_pan.pocket_envelope()`` reports the cross-section the
    pan actually seats in. Feeding those numbers in as the deck-plane
    input would tighten the real fit by the draft taken over the pocket
    depth, because the cavity narrows downward — the same class of error
    as feeding a layout module into a fit dimension.

    The meridional profile translates rigidly with the wall dimension, so
    one probe build gives the exact offset with no iteration.
    """
    K = samples if samples is not None else TOPOLOGY["fillet_arc_samples"]
    probe = 12.0
    try:
        rings, _, tangents = _pocket_profile(
            probe, deck_z, floor_z, draft_deg, rim_fillet, floor_fillet, K)
    except RecessedTrayError as exc:
        raise RectTrayError(f"probe profile is not constructible: {exc}") \
            from exc
    # the fit-critical section is the LOWEST straight wall, where the
    # drafted cavity is narrowest
    z_seat = tangents["wall_bottom_z_mm"] if seating_z is None else seating_z
    at_seat = None
    for (r0, z0), (r1, z1) in zip(rings, rings[1:]):
        if z1 - 1e-9 <= z_seat <= z0 + 1e-9 and abs(z0 - z1) > 1e-12:
            at_seat = r0 + (r1 - r0) * (z0 - z_seat) / (z0 - z1)
            break
    if at_seat is None:
        raise RectTrayError(
            f"seating datum z={z_seat} is outside the pocket profile")
    off = at_seat - probe                       # negative: narrows downward
    fw = float(envelope["functional_width_at_seating_datum_mm"])
    fh = float(envelope["functional_height_at_seating_datum_mm"])
    fr = float(envelope["functional_corner_radius_at_seating_datum_mm"])
    return {
        "record_type": "rect_pocket_datum_solution/1.0",
        "seating_datum_z_mm": round(z_seat, 9),
        "profile_offset_at_seating_datum_mm": round(off, 9),
        "pocket_sharp_wall_width_at_deck_mm": round(fw - 2 * off, 6),
        "pocket_sharp_wall_height_at_deck_mm": round(fh - 2 * off, 6),
        "pocket_sharp_wall_corner_radius_at_deck_mm": round(fr - off, 6),
        "deck_opening_offset_mm": round(
            tangents["deck_tangent_radius_mm"] - probe, 9),
        "input_datum": "FUNCTIONAL_CLEARANCE_AT_SEATING_DATUM",
        "output_datum": "SHARP_WALL_THEORETICAL_AT_DECK_PLANE",
    }


def functional_section(tray, z):
    """The BUILT pocket's cross-section at elevation ``z``.

    Measured from the tray's own profile rings, so a fit check tests the
    geometry that exists rather than the numbers that were requested.
    """
    rings = tray["pocket_profile_rings"]
    p = tray["pockets"][0]
    pr = p["sharp_corner_radius_at_deck_mm"]
    for (r0, z0), (r1, z1) in zip(rings, rings[1:]):
        if z1 - 1e-9 <= z <= z0 + 1e-9 and abs(z0 - z1) > 1e-12:
            r = r0 + (r1 - r0) * (z0 - z) / (z0 - z1)
            inward = pr - r
            return {"z_mm": z,
                    "width_mm": p["sharp_wall_width_at_deck_mm"] - 2 * inward,
                    "height_mm": p["sharp_wall_height_at_deck_mm"]
                    - 2 * inward,
                    "corner_radius_mm": r}
    raise RectTrayError(f"z={z} is outside the built pocket profile")


def _rect_cell_boundary(cx, cy, hx, hy, sx, sy):
    """``2*(sx+sy)`` points CCW from the (+x,+y) corner.

    Adjacent cells emit identical coordinates on a shared edge, so the
    vertex table shares them by exact index and the lattice has neither
    cracks nor T-junctions.
    """
    pts = []
    for s in range(sx):                                   # top, -x
        pts.append((cx + hx - 2 * hx * s / sx, cy + hy))
    for s in range(sy):                                   # left, -y
        pts.append((cx - hx, cy + hy - 2 * hy * s / sy))
    for s in range(sx):                                   # bottom, +x
        pts.append((cx - hx + 2 * hx * s / sx, cy - hy))
    for s in range(sy):                                   # right, +y
        pts.append((cx + hx, cy - hy + 2 * hy * s / sy))
    return pts


def rect_pocket_loop(cx, cy, w, h, radius, count):
    """Rounded-rectangle pocket rim as ``(x, y, nx, ny)``, CCW from the
    (+x,+y) corner arc, where ``(nx, ny)`` is the unit INWARD normal.

    Shares ``_rounded_rect_uniform``'s parameterisation so the deck strip
    to the cell boundary corresponds index-for-index and is not sheared.
    """
    return [(cx + x, cy + y, nx, ny)
            for x, y, nx, ny in _rounded_rect_uniform(w, h, radius, count)]


def offset_pocket_loop(rim, inward, *, corner_radius):
    """``rim`` offset inwards by ``inward`` along each point's OWN normal.

    Re-sampling a smaller rounded rectangle by perimeter parameter would
    also land on the correct offset SHAPE, but point ``i`` would no longer
    be the offset image of point ``i`` — the parameterisation drifts as
    the perimeter shrinks and the wall quads shear. Carrying the rim's own
    normals down gives the exact offset surface AND an exact
    correspondence, so ring-to-ring distance is the wall offset everywhere.
    """
    if corner_radius - inward <= 1e-9:
        raise RectTrayError(
            f"pocket corner radius {corner_radius} cannot absorb a "
            f"{inward:.4f} mm normal offset — the drafted wall would cusp "
            "in the corners")
    return [(x + nx * inward, y + ny * inward) for x, y, nx, ny in rim]


def build_rect_recessed_tray(spec: dict | None = None) -> dict:
    """One continuous manifold tray with a grid of rectangular pockets."""
    cfg = dict(RECT_TRAY_DEFAULTS)
    for key in (spec or {}):
        if key in RETIRED_AMBIGUOUS_KEYS:
            raise RectTrayError(
                f"{key!r} does not name a datum — use "
                f"{RETIRED_AMBIGUOUS_KEYS[key]!r}. A bare pocket dimension "
                "is ambiguous between the deck opening, the theoretical "
                "sharp wall and the functional section the pan seats in.")
        if key not in RECT_TRAY_DEFAULTS:
            raise RectTrayError(f"unknown spec key {key!r}")
        cfg[key] = float(spec[key])

    w, d = cfg["tray_width_mm"], cfg["tray_depth_mm"]
    deck_z, under_z = cfg["deck_z_mm"], cfg["underside_z_mm"]
    floor_z = cfg["pocket_floor_z_mm"]
    pw = cfg["pocket_sharp_wall_width_at_deck_mm"]
    ph = cfg["pocket_sharp_wall_height_at_deck_mm"]
    pr = cfg["pocket_sharp_wall_corner_radius_at_deck_mm"]
    px, py = cfg["pitch_x_mm"], cfg["pitch_y_mm"]
    draft, tray_draft = cfg["pocket_draft_deg"], cfg["tray_draft_deg"]
    corner_r = cfg["corner_radius_mm"]
    rim_fil, floor_fil = cfg["rim_fillet_mm"], cfg["floor_fillet_mm"]

    if not (under_z < floor_z < deck_z):
        raise RectTrayError(
            f"elevations must satisfy underside {under_z} < pocket floor "
            f"{floor_z} < deck {deck_z}")
    if 2 * pr >= min(pw, ph) - 1e-9:
        raise RectTrayError(
            f"pocket corner radius {pr} does not fit {pw} x {ph}")
    if int(cfg["cells_x"]) < 1 or int(cfg["cells_y"]) < 1:
        raise RectTrayError("the pan grid needs at least one cell per axis")

    cx_n, cy_n = int(cfg["cells_x"]), int(cfg["cells_y"])
    sx, sy = TOPOLOGY["cell_edge_samples_x"], TOPOLOGY["cell_edge_samples_y"]
    K = TOPOLOGY["fillet_arc_samples"]
    N = POCKET_SEGMENTS

    # The meridional profile is identical on every straight wall and in
    # every corner, so it is solved once against the CORNER radius and
    # re-applied as a normal offset.
    try:
        rings, r_floor, tangents = _pocket_profile(
            pr, deck_z, floor_z, draft, rim_fil, floor_fil, K)
    except RecessedTrayError as exc:
        # the meridional solver is shared with the round kernel; its
        # failures are this family's failures too, and must not surface as
        # a foreign exception type
        raise RectTrayError(f"pocket profile is not constructible: {exc}") \
            from exc
    opening_r = tangents["deck_tangent_radius_mm"]
    open_off = pr - opening_r                 # negative: the rim flares out
    depth = deck_z - floor_z

    field_x, field_y = cx_n * px, cy_n * py
    if field_x > w - 1e-9 or field_y > d - 1e-9:
        raise RectTrayError(
            f"pan field {field_x} x {field_y} does not fit the tray {w} x {d}")
    if pw - 2 * open_off >= px - 1e-9 or ph - 2 * open_off >= py - 1e-9:
        raise RectTrayError(
            f"pocket opening {pw - 2 * open_off:.4f} x "
            f"{ph - 2 * open_off:.4f} (including the {rim_fil} mm rim "
            f"fillet) does not fit the pitch {px} x {py}")

    table = VertexTable()
    faces: list = []
    pockets = []
    hx, hy = px / 2.0, py / 2.0

    for row in range(cy_n):
        for col in range(cx_n):
            cx = (col - (cx_n - 1) / 2.0) * px
            cy = (row - (cy_n - 1) / 2.0) * py
            boundary = [table.add(x, y, deck_z)
                        for x, y in _rect_cell_boundary(cx, cy, hx, hy,
                                                        sx, sy)]
            rim = rect_pocket_loop(cx, cy, pw, ph, pr, N)
            prev = [table.add(x, y, deck_z) for x, y in
                    offset_pocket_loop(rim, open_off, corner_radius=pr)]
            _strip(faces, boundary, prev)
            for r_ring, z_ring in rings[1:]:
                ring = [table.add(x, y, z_ring) for x, y in
                        offset_pocket_loop(rim, pr - r_ring, corner_radius=pr)]
                _strip(faces, prev, ring)
                prev = ring
            _fan(faces, prev, table.add(cx, cy, floor_z), flip=True)
            pockets.append({
                "row": row, "col": col,
                "centre_mm": [round(cx, 6), round(cy, 6)],
                "sharp_wall_width_at_deck_mm": round(pw, 6),
                "sharp_wall_height_at_deck_mm": round(ph, 6),
                "sharp_corner_radius_at_deck_mm": round(pr, 6),
                "opening_width_mm": round(pw - 2 * open_off, 6),
                "opening_height_mm": round(ph - 2 * open_off, 6),
                "floor_width_mm": round(pw - 2 * (pr - r_floor), 6),
                "floor_height_mm": round(ph - 2 * (pr - r_floor), 6),
                "floor_corner_radius_mm": round(r_floor, 6),
                "depth_mm": round(depth, 6), **tangents})

    lattice = [table.add(x, y, deck_z) for x, y in
               _rect_cell_boundary(0.0, 0.0, field_x / 2.0, field_y / 2.0,
                                   cx_n * sx, cy_n * sy)]
    outer_count = 2 * (cx_n * sx + cy_n * sy)
    if len(lattice) != outer_count:                    # pragma: no cover
        raise RectTrayError("lattice loop length disagrees with the topology")

    outer_pts = _rounded_rect_uniform(w, d, corner_r, outer_count)
    outer_top = [table.add(x, y, deck_z) for x, y, _, _ in outer_pts]
    # the lattice was already emitted backwards by the perimeter cells, so
    # it must appear here as loop_b or the surface loses orientation
    _strip(faces, outer_top, lattice)

    inset = (deck_z - under_z) * math.tan(math.radians(tray_draft))
    if inset >= corner_r or 2 * inset >= min(w - field_x, d - field_y):
        raise RectTrayError(
            f"tray draft {tray_draft} deg insets the underside by "
            f"{inset:.4f} mm, which collapses the outer wall")
    outer_bottom = [table.add(x + nx * inset, y + ny * inset, under_z)
                    for x, y, nx, ny in outer_pts]
    _strip(faces, outer_bottom, outer_top)
    _fan(faces, outer_bottom, table.add(0.0, 0.0, under_z), flip=False)

    mesh = {"vertices": np.asarray(table.vertices, dtype=float),
            "faces": np.asarray(faces, dtype=np.int64)}
    _orient_outward(mesh)
    identity = hashlib.sha256(
        np.round(mesh["vertices"], 6).tobytes() + mesh["faces"].tobytes()
        + repr(sorted(TOPOLOGY.items())).encode()
        + repr((cx_n, cy_n)).encode()).hexdigest()[:16]

    return {
        "name": "recessed_palette_tray_rectangular",
        "schema": SCHEMA,
        "vertices": mesh["vertices"], "faces": mesh["faces"],
        "mesh_identity": identity,
        "pocket_shape": "RECTANGULAR",
        "authority": "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION",
        "blender_role": "VISUALIZATION_AND_RENDERING_ONLY",
        "boolean_free": True,
        "topology": dict(TOPOLOGY),
        "pocket_segments": N,
        "shared_vertex_reuse_count": table.reuse_count,
        "weld_count": 0,
        "pocket_count": len(pockets),
        "pockets": pockets,
        "grid": {"columns": cx_n, "rows": cy_n,
                 "pitch_x_mm": px, "pitch_y_mm": py,
                 **GRID_AUTHORITY},
        "elevations_mm": {"underside": under_z, "pocket_floor": floor_z,
                          "deck": deck_z},
        "pocket_floor_thickness_mm": round(floor_z - under_z, 6),
        "draft": {"tray_draft_deg": tray_draft, "pocket_draft_deg": draft,
                  "tray_underside_inset_mm": round(inset, 6),
                  "release_direction": "UPWARD"},
        "fillets_mm": {"rim": rim_fil, "floor": floor_fil,
                       "strategy": TOPOLOGY["fillet_strategy"]},
        "pocket_profile_rings": [[round(r, 9), round(z, 9)] for r, z in rings],
        "dimensional_authority": dict(DIMENSIONAL_AUTHORITY),
        "spec": cfg,
    }


#: Solved at import so the pocket can never drift from the pan contract.
POCKET_DATUM_SOLUTION = _derive_pocket_defaults()
