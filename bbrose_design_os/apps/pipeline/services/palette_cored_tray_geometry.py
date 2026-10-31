"""PALT-M4B-A3 — cored moulded tray.

A2 left a solid 5.65 mm outer floor and a 5.85:1 section ratio. This
builder replaces the flat underside cap with a real cored underside,
using exactly the same shared-index strip machinery as the deck — the
underside decomposes into the same square-to-circle strips, mirrored.

An injection-moulded tray cannot carry a SEALED internal void: the core
has to pull. So every strategy here cores the underside OPEN. What the
owner's brief calls a "base skin" is realised as the pocket floors
(1.0 mm) and the deck skin (1.0 mm); there is no separate closed base
skin, and that is a declared engineering constraint rather than an
omission.

Every strategy cores the perimeter band. The 11.3 mm wide outer margin is
where the 5.65 mm mass actually lives, so a strategy that only cored the
interstitial regions would leave the ratio untouched and the matrix would
carry no information.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from apps.pipeline.services.palette_recessed_tray_geometry import (
    TOPOLOGY, RecessedTrayError, VertexTable, _cell_boundary_points,
    _circle_points, _fan, _pocket_profile, _rounded_rect_uniform, _strip)

SCHEMA = "palette_cored_tray/1.0"

CORE_TOPOLOGY = {
    "version": "cored_tray_topology/1.0",
    "inherits": TOPOLOGY["version"],
    "cup_profile_from": "POCKET_PROFILE_OFFSET_BY_CUP_WALL",
    "underside_decomposition": "CELL_LATTICE_MIRRORING_THE_DECK",
    "sealed_void_permitted": False,
    "coordinate_quantization": TOPOLOGY["coordinate_quantization"],
    "weld_tolerance": None,
}

# genus 0: the cored recess is a DENT, not a through-hole, in every
# strategy — so the closed shell keeps chi = 2. Asserted, not relaxed.
EXPECTED_EULER = 2

# §6 rib system. Every value DESIGN_DEFAULT / NOT_MANUFACTURER_CONFIRMED.
# Structural sufficiency is NOT claimed: no FEA and no physical part.
RIB_POLICY = {
    "version": "palette_rib_policy/1.0",
    "rib_thickness_mm": 1.0,
    "rib_thickness_rule": "at or below the adjoining nominal wall so the "
                          "rib root does not read through as a sink line",
    "rib_height_mm": 4.65,
    "rib_draft_deg": 1.5,
    "rib_root_radius_mm": 0.4,
    "rib_spacing_mm": 30.6,
    "rib_termination": "RUN_OUT_INTO_THE_PERIMETER_WALL_NO_FREE_ENDS",
    "pocket_support_relationship": "ribs must not touch a pocket cup",
    "outer_wall_relationship": "every rib terminates in the perimeter wall",
    "hinge_interface_placeholder": "TOP_EDGE band, DECLARED_NOT_MODELLED",
    "clasp_interface_placeholder": "BOTTOM_EDGE band, DECLARED_NOT_MODELLED",
    "minimum_rib_to_pocket_clearance_mm": 0.5,
    "viable_placement": "DIAGONAL_INTERSTITIAL_ONLY — at pitch 30.6 the "
                        "cup circles leave ~13.8 mm between DIAGONAL "
                        "neighbours but under 0.1 mm on the cell grid, so "
                        "an orthogonal cell-grid rib is excluded and a "
                        "diagonal rib lattice is the viable option. "
                        "Meshing it is deferred to M4B-B.",
    "authority": "DESIGN_DEFAULT",
    "manufacturing_authority": "NOT_MANUFACTURER_CONFIRMED",
    "structural_sufficiency": "NOT_DEMONSTRATED_NO_FEA_NO_PHYSICAL_PART",
}


PRIMARY_FACE_CLASSES = (
    "OUTER_DECK_TOP", "OUTER_DECK_UNDERSIDE", "POCKET_RIM_FILLET",
    "POCKET_DRAFTED_WALL", "POCKET_FLOOR_FILLET", "POCKET_FLOOR",
    "BASE_SKIN_TOP", "BASE_SKIN_UNDERSIDE", "OUTER_SIDE_WALL",
    "OUTER_CORNER", "CORE_CEILING", "CORE_WALL", "CORE_FLOOR",
    "CORE_TRANSITION", "PERIMETER_STRUCTURE",
    "HINGE_INTERFACE_PLACEHOLDER", "CLASP_INTERFACE_PLACEHOLDER",
    "UNKNOWN_FACE_CLASS")

CUP_WALL_CLASSES = ("POCKET_DRAFTED_WALL", "POCKET_FLOOR_FILLET",
                    "POCKET_RIM_FILLET")


class FaceProvenanceError(RecessedTrayError):
    """Raised when a face carries no class or more than one."""


class FaceLog(list):
    """A face list that stamps every appended face with the class that was
    active when the builder emitted it.

    A3M classified faces by elevation band, which put deck-skin faces at
    z=6.15 inside the cup-wall band and made the cup-wall proof
    unusable. Provenance is recorded at BUILD time instead: the builder
    knows exactly which surface it is emitting, so nothing is inferred
    from geometry afterwards.
    """

    def __init__(self):
        super().__init__()
        self.classes: list = []
        self._active = None

    def begin(self, klass):
        if klass not in PRIMARY_FACE_CLASSES:
            raise FaceProvenanceError(f"unknown face class {klass!r}")
        self._active = klass

    def append(self, item):
        if self._active is None:
            raise FaceProvenanceError(
                "a face was emitted with no active class — provenance would "
                "be lost")
        super().append(item)
        self.classes.append(self._active)

    def audit(self):
        if len(self) != len(self.classes):
            raise FaceProvenanceError(
                f"{len(self)} faces but {len(self.classes)} classes")
        for i, k in enumerate(self.classes):
            if k not in PRIMARY_FACE_CLASSES or k == "UNKNOWN_FACE_CLASS":
                raise FaceProvenanceError(
                    f"face {i} has class {k!r}")
        return {k: self.classes.count(k) for k in sorted(set(self.classes))}


class CoredTrayError(RecessedTrayError):
    """Raised when a coring strategy cannot be built (fail closed)."""


CORE_STRATEGIES = {
    "A_UNIFORM_UNDERSIDE_CORE": {
        "description": "one continuous underside recess with a controlled "
                       "outer perimeter; the core's inner face is a plain "
                       "cylinder at the pocket's widest radius, so it "
                       "pulls straight but the cup wall thickens downward",
        "follow_draft": False, "rib_width_mm": 0.0,
    },
    "B_CELLULAR_UNDERSIDE_CORE": {
        "description": "nine cell voids separated by ribs on the 3x3 cell "
                       "grid, plus the perimeter band; straight-pull core "
                       "faces as in A",
        "follow_draft": False, "rib_width_mm": 1.0,
    },
    "C_POCKET_FOLLOWING_CORE": {
        "description": "the core's inner face is the pocket profile offset "
                       "by the cup wall, so the wall is uniform by "
                       "construction; single interstitial void plus the "
                       "perimeter band",
        "follow_draft": True, "rib_width_mm": 0.0,
    },
    "D_HYBRID_CORE": {
        "description": "pocket-following cups for a uniform wall, plus "
                       "cell-grid ribs and the perimeter band",
        "follow_draft": True, "rib_width_mm": 1.0,
    },
}

DEFAULT_CORE = {
    "deck_skin_mm": 1.0,
    "cup_wall_mm": 1.0,
    "perimeter_wall_mm": 1.8,
    "rib_width_mm": 0.0,
    "follow_draft": True,
    "cup_offset_mode": "RADIAL",
    "strategy": "C_POCKET_FOLLOWING_CORE",
}


def _cup_profile_true_normal(spec, cup_wall, core_top_z, under_z):
    """A3F: cup outer profile as a TRUE NORMAL offset of the cavity.

    A3R proved the radial offset delivers w*cos(obliquity) and collapsed to
    0.6007 mm on the floor fillet. The normal offset delivers exactly w.
    Points below the tray underside are TRIMMED there — the 1.0 mm pocket
    floor is an owner-preserved value and is not thickened to suit the
    wall, so a wall thicker than 1.0 mm simply meets the underside early.
    """
    from apps.pipeline.services import palette_profile_offset as po
    prims, _meta = po.pocket_profile_primitives(
        sharp_r=float(
            spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"]) / 2.0,
        deck_z=float(spec["deck_z_mm"]),
        floor_z=float(spec["pocket_floor_z_mm"]),
        draft_deg=float(spec["pocket_draft_deg"]),
        rim_fillet=float(spec["rim_fillet_mm"]),
        floor_fillet=float(spec["floor_fillet_mm"]),
        core_top_z=core_top_z)
    got = po.offset_meridional_profile_normal(prims, cup_wall)
    out = []
    for (r, z) in got["points"]:
        if z < under_z - 1e-12:
            if out and out[-1][1] > under_z + 1e-12:
                r0, z0 = out[-1]
                t = (z0 - under_z) / (z0 - z)
                out.append((r0 + (r - r0) * t, under_z))
            break
        out.append((r, z))
    if not out or abs(out[-1][1] - under_z) > 1e-9:
        out.append((out[-1][0] if out else got["points"][-1][0], under_z))
    return out, got["profile_identity"]


def _cup_profile(rings, cup_wall, core_top_z, follow_draft):
    """Outer (radius, z) profile of one pocket cup, TOP DOWN.

    Runs from the core ceiling elevation down to the floor-disc edge at
    the tray underside.
    """
    widest = max(r for r, _ in rings)
    out = []
    if follow_draft:
        for r, z in rings:
            if z > core_top_z:
                continue
            out.append((r + cup_wall, z))
        top_r = _profile_r(rings, core_top_z)
        if top_r is None:
            raise CoredTrayError(
                f"core ceiling z={core_top_z} is outside the pocket profile")
        out.insert(0, (top_r + cup_wall, core_top_z))
    else:
        out.append((widest + cup_wall, core_top_z))
        out.append((widest + cup_wall, rings[-1][1]))
    # close down to the floor-disc plane
    return out


def _profile_r(rings, z):
    for (r0, z0), (r1, z1) in zip(rings, rings[1:]):
        if z1 - 1e-9 <= z <= z0 + 1e-9:
            if abs(z0 - z1) < 1e-12:
                return max(r0, r1)
            t = (z0 - z) / (z0 - z1)
            return r0 + (r1 - r0) * t
    return None


def build_cored_palette_tray(spec: dict, core: dict | None = None) -> dict:
    """One continuous, manifold, watertight cored moulded tray."""
    cfg = dict(DEFAULT_CORE)
    cfg.update(core or {})
    if "pocket_diameter_mm" in spec:
        raise CoredTrayError(
            "'pocket_diameter_mm' is retired as ambiguous — name the datum")

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

    deck_skin = float(cfg["deck_skin_mm"])
    cup_wall = float(cfg["cup_wall_mm"])
    perim_wall = float(cfg["perimeter_wall_mm"])
    rib_w = float(cfg["rib_width_mm"])
    follow = bool(cfg["follow_draft"])
    core_top_z = deck_z - deck_skin

    if not (under_z < floor_z < core_top_z < deck_z):
        raise CoredTrayError(
            f"elevations must satisfy underside {under_z} < pocket floor "
            f"{floor_z} < core ceiling {core_top_z} < deck {deck_z}")

    cells_x, cells_y = TOPOLOGY["cells_x"], TOPOLOGY["cells_y"]
    S = TOPOLOGY["cell_edge_samples"]
    N = TOPOLOGY["pocket_segments"]
    K = TOPOLOGY["fillet_arc_samples"]
    rings, r_floor, tangents = _pocket_profile(
        pocket_r, deck_z, floor_z, draft, rim_fil, floor_fil, K)
    opening_r = tangents["deck_tangent_radius_mm"]
    field = cells_x * pitch
    if field > min(w, d) - 1e-9:
        raise CoredTrayError(f"pan field {field} does not fit {w} x {d}")
    if 2 * opening_r >= pitch - 1e-9:
        raise CoredTrayError(
            f"pocket opening {2 * opening_r:.4f} does not fit pitch {pitch}")

    offset_mode = cfg.get("cup_offset_mode", "RADIAL")
    if offset_mode == "TRUE_NORMAL":
        cup, cup_profile_identity = _cup_profile_true_normal(
            spec, cup_wall, core_top_z, under_z)
    elif offset_mode == "RADIAL":
        cup = _cup_profile(rings, cup_wall, core_top_z, follow)
        cup_profile_identity = None
    else:
        raise CoredTrayError(f"unknown cup_offset_mode {offset_mode!r}")
    cup_max_r = max(r for r, _ in cup)
    half_cell = pitch / 2.0
    cell_inner_half = half_cell - rib_w / 2.0
    if rib_w > 0:
        # §6: ribs must not collide with the pockets. At the PALT-P1 pitch
        # the cups very nearly fill their cells, so a cell-grid rib is
        # measured against a credibility floor rather than mere
        # non-intersection: a rib clearing a cavity by a few hundredths of
        # a millimetre is not a manufacturable feature.
        margin = cell_inner_half - cup_max_r
        if margin < RIB_POLICY["minimum_rib_to_pocket_clearance_mm"]:
            raise CoredTrayError(
                f"cell-grid rib of {rib_w} mm leaves {margin:.4f} mm to the "
                f"pocket cup (cup reaches {cup_max_r:.4f} mm, cell inner "
                f"half-width {cell_inner_half:.4f} mm). The policy floor is "
                f"{RIB_POLICY['minimum_rib_to_pocket_clearance_mm']} mm. At "
                "the PALT-P1 pitch the cups nearly fill their cells, so "
                "CELL-GRID rib placement is geometrically excluded — see "
                "RIB_POLICY['viable_placement'] for the diagonal "
                "alternative, which is deferred to M4B-B.")
    if cup[-1][0] >= r_floor + cup_wall + 1e-9 and follow:
        raise CoredTrayError("cup profile is inconsistent with the floor")

    table = VertexTable()
    faces = FaceLog()
    pockets = []

    # ---------------- deck + pockets (unchanged from the A2 kernel) -----
    for row in range(cells_y):
        for col in range(cells_x):
            cx = (col - (cells_x - 1) / 2.0) * pitch
            cy = (row - (cells_y - 1) / 2.0) * pitch
            boundary = [table.add(x, y, deck_z)
                        for x, y in _cell_boundary_points(cx, cy, half_cell,
                                                          S)]
            prev = [table.add(x, y, deck_z)
                    for x, y in _circle_points(cx, cy, opening_r, N)]
            faces.begin("OUTER_DECK_TOP")
            _strip(faces, boundary, prev)
            # rings = [rim fillet arc K+1][floor fillet arc K+1]; the
            # straight drafted run is the single span between them
            for j, (r_ring, z_ring) in enumerate(rings[1:]):
                if j < K:
                    faces.begin("POCKET_RIM_FILLET")
                elif j == K:
                    faces.begin("POCKET_DRAFTED_WALL")
                else:
                    faces.begin("POCKET_FLOOR_FILLET")
                ring = [table.add(x, y, z_ring)
                        for x, y in _circle_points(cx, cy, r_ring, N)]
                _strip(faces, prev, ring)
                prev = ring
            centre = table.add(cx, cy, floor_z)
            faces.begin("POCKET_FLOOR")
            _fan(faces, prev, centre, flip=True)
            pockets.append({"row": row, "col": col,
                            "centre_mm": [round(cx, 6), round(cy, 6)],
                            "sharp_corner_radius_mm": round(pocket_r, 6),
                            "opening_radius_mm": round(opening_r, 6),
                            "floor_radius_mm": round(r_floor, 6),
                            "depth_mm": round(deck_z - floor_z, 6),
                            **tangents})

    # ---------------- lattice outer loop + tray outer wall --------------
    lattice = [table.add(x, y, deck_z) for x, y in
               _cell_boundary_points(0.0, 0.0, field / 2.0, cells_x * S)]
    outer_count = TOPOLOGY["outer_loop_samples"]
    outer_pts = _rounded_rect_uniform(w, d, corner_r, outer_count)
    outer_top = [table.add(x, y, deck_z) for x, y, _, _ in outer_pts]
    faces.begin("OUTER_DECK_TOP")
    _strip(faces, outer_top, lattice)

    inset = (deck_z - under_z) * math.tan(math.radians(tray_draft))
    if inset >= corner_r or 2 * inset >= min(w, d) - field:
        raise CoredTrayError(
            f"tray draft {tray_draft} insets the underside by {inset:.4f}")
    outer_bottom = [table.add(x + nx * inset, y + ny * inset, under_z)
                    for x, y, nx, ny in outer_pts]
    faces.begin("OUTER_SIDE_WALL")
    _strip(faces, outer_bottom, outer_top)

    # ---------------- cored underside -----------------------------------
    # traversed edge-inward. _strip emits loop_a backwards and loop_b
    # forwards, so each shared loop must alternate role along the chain.
    perim = [table.add(x + (nx * (inset + perim_wall)),
                       y + (ny * (inset + perim_wall)), under_z)
             for x, y, nx, ny in outer_pts]
    faces.begin("BASE_SKIN_UNDERSIDE")
    _strip(faces, perim, outer_bottom)          # perimeter band underface

    core_rise = core_top_z - under_z
    perim_top_inset = inset + perim_wall + core_rise * math.tan(
        math.radians(tray_draft))
    perim_top = [table.add(x + nx * perim_top_inset,
                           y + ny * perim_top_inset, core_top_z)
                 for x, y, nx, ny in outer_pts]
    faces.begin("PERIMETER_STRUCTURE")
    _strip(faces, perim_top, perim)             # perimeter inner face

    lattice_ring = [table.add(x, y, core_top_z) for x, y in
                    _cell_boundary_points(0.0, 0.0, field / 2.0,
                                          cells_x * S)]
    faces.begin("CORE_CEILING")
    _strip(faces, lattice_ring, perim_top)       # core ceiling border

    for row in range(cells_y):
        for col in range(cells_x):
            cx = (col - (cells_x - 1) / 2.0) * pitch
            cy = (row - (cells_y - 1) / 2.0) * pitch
            top_ring = [table.add(x, y, cup[0][1])
                        for x, y in _circle_points(cx, cy, cup[0][0], N)]
            cell_sq = [table.add(x, y, core_top_z) for x, y in
                       _cell_boundary_points(cx, cy, half_cell, S)]
            faces.begin("CORE_CEILING")
            _strip(faces, top_ring, cell_sq)
            prev = top_ring
            for r_c, z_c in cup[1:]:
                ring = [table.add(x, y, z_c)
                        for x, y in _circle_points(cx, cy, r_c, N)]
                faces.begin("CORE_WALL")
                _strip(faces, ring, prev)
                prev = ring
            base = [table.add(x, y, under_z)
                    for x, y in _circle_points(cx, cy, cup[-1][0], N)]
            if not math.isclose(cup[-1][1], under_z, abs_tol=1e-9):
                faces.begin("CORE_TRANSITION")
                _strip(faces, base, prev)
                prev = base
            centre_b = table.add(cx, cy, under_z)
            faces.begin("BASE_SKIN_UNDERSIDE")
            _fan(faces, prev, centre_b, flip=False)

    face_class_counts = faces.audit()
    face_classes = list(faces.classes)
    vertices = np.asarray(table.vertices, dtype=float)
    faces_arr = np.asarray(faces, dtype=np.int64)
    mesh = {"vertices": vertices, "faces": faces_arr}
    a = mesh["vertices"][mesh["faces"][:, 0]]
    signed = float(np.einsum(
        "ij,ij->i", a,
        np.cross(mesh["vertices"][mesh["faces"][:, 1]] - a,
                 mesh["vertices"][mesh["faces"][:, 2]] - a)).sum() / 6.0)
    if signed < 0:
        mesh["faces"] = mesh["faces"][:, [0, 2, 1]]

    identity = hashlib.sha256(
        np.round(mesh["vertices"], 6).tobytes() + mesh["faces"].tobytes()
        + repr(sorted(TOPOLOGY.items())).encode()
        + repr(sorted(CORE_TOPOLOGY.items())).encode()
        + repr(sorted(cfg.items())).encode()).hexdigest()[:16]

    ligament = pitch - 2 * opening_r
    return {
        "name": "cored_palette_tray", "schema": SCHEMA,
        "vertices": mesh["vertices"], "faces": mesh["faces"],
        "mesh_identity": identity,
        "authority": "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION",
        "blender_role": "VISUALIZATION_AND_RENDERING_ONLY",
        "boolean_free": True,
        "topology": dict(TOPOLOGY), "core_topology": dict(CORE_TOPOLOGY),
        "core": dict(cfg),
        "shared_vertex_reuse_count": table.reuse_count, "weld_count": 0,
        "pockets": pockets,
        "elevations_mm": {"underside": under_z, "pocket_floor": floor_z,
                          "core_ceiling": core_top_z, "deck": deck_z},
        "pocket_floor_thickness_mm": round(floor_z - under_z, 6),
        "deck_skin_mm": round(deck_skin, 6),
        "cup_profile": [[round(r, 9), round(z, 9)] for r, z in cup],
        "cup_max_radius_mm": round(cup_max_r, 6),
        "face_classes": face_classes,
        "face_class_counts": face_class_counts,
        "primary_face_classes": list(PRIMARY_FACE_CLASSES),
        "cup_offset_mode": offset_mode,
        "cup_profile_identity": cup_profile_identity,
        "rib_clearance_to_pocket_mm": round(cell_inner_half - cup_max_r, 6)
        if rib_w > 0 else None,
        "draft": {"tray_draft_deg": tray_draft, "pocket_draft_deg": draft,
                  "tray_underside_inset_mm": round(inset, 6),
                  "release_direction": "UPWARD",
                  "core_pull_direction": "DOWNWARD"},
        "fillets_mm": {"rim": rim_fil, "floor": floor_fil,
                       "strategy": TOPOLOGY["fillet_strategy"]},
        "pocket_profile_rings": [[round(r, 9), round(z, 9)]
                                 for r, z in rings],
        "deck_ligament_mm": round(ligament, 6),
        # A2's metric, UNCHANGED, so the A3 result is comparable
        "pocket_wall_at_mouth_mm": round(ligament / 2.0, 6),
        # a second, separately named observation for owner ruling — the
        # material section between two cavities is the full ligament
        "inter_pocket_material_section_mm": round(ligament, 6),
        "spec": dict(spec),
    }
