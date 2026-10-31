"""PALT-M4B — moulded palette geometry and mechanism correction.

PALT-M4 was owner-REJECTED: pans read as discs sitting on a flat slab, the
mechanisms could not be inspected, and the "section" was a clipped
exterior view. This module rebuilds the interior as a genuinely moulded
tray with recessed pockets, builds inspectable hinge and clasp mechanisms,
and defines real CSG operands so true sections can be cut.

CSG contract: components may declare ``csg`` = {"op": "DIFFERENCE",
"cutters": [names]}. Operands are deterministic Python meshes (hashed and
tested); the Boolean itself is solved in Blender at render time. A tray
with recessed pockets is *defined* as blank minus cutters — that is a real
construction, not a visual trick.

Every mechanism and moulding figure is DESIGN_DEFAULT /
NOT_MANUFACTURER_CONFIRMED. No tooling authority is claimed.
"""
from __future__ import annotations

import math

import numpy as np

from apps.pipeline.services import palette_geometry as pg
from apps.pipeline.services.palette_contracts import to_jsonable
from apps.pipeline.services.palette_stackup_engine import (
    ALLOWANCES, height_stackup, pocket_module_mm)
from apps.pipeline.services.palette_mechanism_geometry import (
    PALT_P1_MECHANISM, PREMIUM_ENVELOPE)
from apps.pipeline.services.palt_p1 import build_palt_p1

SCHEMA = "palt_p1_moulded_assembly/1.0"
REVISION = "M4B"

STATES = ("CLOSED", "OPEN_90", "OPEN_REVIEW_ANGLE", "EXPLODED",
          "BASE_ONLY", "LID_ONLY", "TRAY_ONLY", "MECHANISM_DETAIL",
          "HINGE_ONLY", "CLASP_ONLY", "MIRROR_STACK")

OPEN_REVIEW_ANGLE_DEG = 110.0

# --- moulding parameters (DESIGN_DEFAULT, NOT_MANUFACTURER_CONFIRMED) ------
MOULDING = {
    "tray_draft_deg": 1.5,          # ABS cosmetic parts commonly 1-3 deg
    "pocket_draft_deg": 2.0,
    "internal_fillet_mm": 0.6,
    "wall_to_floor_radius_mm": 0.8,
    "pocket_floor_thickness_mm": 1.0,
    "exterior_wall_mm": 2.0,
    "rib_thickness_mm": 1.0,        # 0.4-0.6 x wall (R14 guidance)
    "rib_height_mm": 2.4,
    "hinge_reinforcement_mm": 1.2,
    "clasp_reinforcement_mm": 1.0,
}

# --- pan / pocket system --------------------------------------------------
PAN_SYSTEM = {
    "pan_outside_diameter_mm": 26.0,
    "metal_pan_wall_mm": 0.25,
    "metal_pan_floor_mm": 0.25,
    "pocket_diameter_mm": 26.8,
    "pocket_depth_mm": 4.3,          # pan depth + seating + adhesive
    "seating_clearance_mm": 0.40,
    "adhesive_allowance_mm": 0.15,
    "pan_recess_mm": 0.60,           # pan rim BELOW the deck => recessed
    "powder_crown_mm": 0.30,
    "powder_to_lid_clearance_mm": 0.80,
}
PRIMARY_PAN_DEPTH_MM = 3.5
COMPARISON_PAN_DEPTH_MM = 5.0

# --- hinge (alternating knuckles, real pin) -------------------------------
HINGE = {
    "knuckle_count": 5,              # 3 base + 2 lid, alternating
    "knuckle_gap_mm": 0.35,
    "barrel_outer_radius_mm": 1.9,
    "pin_radius_mm": 0.7,
    "pin_clearance_mm": 0.10,
    "rotational_clearance_mm": 0.25,
    "root_fillet_mm": 0.8,
    "pin_cap_radius_mm": 1.0,
    "pin_cap_length_mm": 1.2,
    "open_stop_deg": 118.0,
}

# --- clasp (hook + detent with lead-in and undercut) ----------------------
CLASP = {
    "hook_width_mm": 18.0,
    "hook_thickness_mm": 1.6,
    "hook_drop_mm": 3.2,
    "hook_lip_mm": 0.9,              # engagement undercut
    "lead_in_chamfer_mm": 0.7,
    "detent_width_mm": 20.0,
    "detent_height_mm": 2.4,
    "detent_depth_mm": 1.1,
    "release_clearance_mm": 0.25,
    "flex_zone_width_mm": 24.0,
    "flex_zone_thickness_mm": 1.1,
    "finger_notch_width_mm": 22.0,
    "finger_notch_depth_mm": 2.6,
    "engagement_depth_mm": 0.9,
}

# --- mirror mounting stack ------------------------------------------------
MIRROR = {
    "thickness_mm": 1.0,
    "adhesive_pad_mm": 0.20,
    "recess_depth_mm": 1.4,
    "retaining_border_mm": 2.0,
    "perimeter_clearance_mm": 0.30,
    "safety_gap_mm": 0.30,
    "lid_backing_mm": 1.2,
}

CORNER_R = 6.0
EDGE_R = 1.2


def _normalized(component):
    """Force outward normals. An inverted cutter makes a Boolean silently
    do nothing — a defect that is invisible until you look at the render."""
    v, f = component["vertices"], component["faces"]
    a = v[f[:, 0]]
    signed = float(np.einsum("ij,ij->i", a,
                             np.cross(v[f[:, 1]] - a,
                                      v[f[:, 2]] - a)).sum() / 6.0)
    if signed < 0:
        f = f[:, [0, 2, 1]]
        return pg._component(component["name"], v, f,
                             role=component["role"],
                             authority=component["authority"])
    return component


def _draft_inset(depth_mm, draft_deg):
    """Horizontal inset produced by a draft angle over a given depth."""
    return depth_mm * math.tan(math.radians(draft_deg))


def drafted_cylinder(name, r_top, depth, draft_deg, *, centre=(0.0, 0.0),
                     z_top=0.0, role="", segments=pg.CIRCLE_SEGMENTS,
                     close_bottom=True):
    """A cylinder that tapers with draft (narrower at the bottom) — the
    shape a moulded pocket cutter actually needs."""
    r_bot = r_top - _draft_inset(depth, draft_deg)
    cx, cy = centre
    top = pg.circle_outline(r_top, segments)
    bot = pg.circle_outline(max(r_bot, 0.2), segments)
    n = segments
    verts = np.concatenate([
        np.column_stack([top[:, 0] + cx, top[:, 1] + cy, np.full(n, z_top)]),
        np.column_stack([bot[:, 0] + cx, bot[:, 1] + cy,
                         np.full(n, z_top - depth)]),
        [[cx, cy, z_top]], [[cx, cy, z_top - depth]]], axis=0)
    faces = pg._ring_faces(n, 0, n, n)
    faces += pg._cap_faces(0, n, 2 * n)
    if close_bottom:
        faces += pg._cap_faces(n, n, 2 * n + 1, flip=True)
    return _normalized(pg._component(name, verts, faces, role=role))


def drafted_box(name, w, d, h, corner_r, draft_deg, *, z0=0.0, role="",
                edge_r=0.4, centre=(0.0, 0.0)):
    """A slab whose walls taper outward toward the top (mould draft)."""
    inset = _draft_inset(h, draft_deg)
    levels = [(z0, inset), (z0 + h - edge_r, 0.0)]
    for i in range(1, 5):
        t = i / 4
        dz = edge_r * t
        e = edge_r - math.sqrt(max(edge_r ** 2 - (edge_r - dz) ** 2, 0.0))
        levels.append((z0 + h - edge_r + dz, e))
    rings, n = [], None
    for z, ins in levels:
        outline = pg.rounded_rect_outline(max(w - 2 * ins, 0.5),
                                          max(d - 2 * ins, 0.5),
                                          max(corner_r - ins, 0.0))
        n = len(outline)
        rings.append(np.column_stack([outline[:, 0] + centre[0],
                                      outline[:, 1] + centre[1],
                                      np.full(n, z)]))
    verts = np.concatenate(rings, axis=0)
    faces = []
    for k in range(len(rings) - 1):
        faces += pg._ring_faces(n, k * n, (k + 1) * n, n)
    bc, tc = len(verts), len(verts) + 1
    verts = np.concatenate([verts, [[centre[0], centre[1], levels[0][0]]],
                            [[centre[0], centre[1], levels[-1][0]]]], axis=0)
    faces += pg._cap_faces(0, n, bc, flip=True)
    faces += pg._cap_faces((len(rings) - 1) * n, n, tc)
    return pg._component(name, verts, faces, role=role)


def metal_pan(name, outer_r, depth, wall, floor, *, centre=(0.0, 0.0),
              z0=0.0, role="", segments=pg.CIRCLE_SEGMENTS):
    """A real metal pan: an open-topped cup (outer wall, rim, inner wall,
    inner floor, outer floor) — not a solid disc."""
    cx, cy = centre
    ro, ri = outer_r, outer_r - wall
    n = segments
    co = pg.circle_outline(ro, n)
    ci = pg.circle_outline(ri, n)
    rings = [
        np.column_stack([co[:, 0] + cx, co[:, 1] + cy, np.full(n, z0)]),
        np.column_stack([co[:, 0] + cx, co[:, 1] + cy,
                         np.full(n, z0 + depth)]),
        np.column_stack([ci[:, 0] + cx, ci[:, 1] + cy,
                         np.full(n, z0 + depth)]),
        np.column_stack([ci[:, 0] + cx, ci[:, 1] + cy,
                         np.full(n, z0 + floor)]),
    ]
    verts = np.concatenate(rings, axis=0)
    faces = []
    faces += pg._ring_faces(n, 0, n, n)            # outer wall
    faces += pg._ring_faces(n, n, 2 * n, n)        # rim
    faces += pg._ring_faces(n, 2 * n, 3 * n, n)    # inner wall
    inner_c = len(verts)
    outer_c = inner_c + 1
    verts = np.concatenate([verts, [[cx, cy, z0 + floor]],
                            [[cx, cy, z0]]], axis=0)
    faces += pg._cap_faces(3 * n, n, inner_c)      # inner floor
    faces += pg._cap_faces(0, n, outer_c, flip=True)   # outer floor
    return pg._component(name, verts, faces, role=role)


def powder_volume(name, r, thickness, crown, *, centre=(0.0, 0.0), z0=0.0,
                  role="", segments=pg.CIRCLE_SEGMENTS):
    """Pressed powder: a disc with a slight crown (never a flat plate)."""
    cx, cy = centre
    n = segments
    base = pg.circle_outline(r, n)
    rings = [np.column_stack([base[:, 0] + cx, base[:, 1] + cy,
                              np.full(n, z0)])]
    steps = 5
    for i in range(1, steps + 1):
        t = i / steps
        rr = r * math.cos(t * math.pi / 2) if t == 1 else r * (1 - 0.06 * t)
        zz = z0 + thickness + crown * math.sin(t * math.pi / 2)
        ring = pg.circle_outline(max(rr, 0.4), n)
        rings.append(np.column_stack([ring[:, 0] + cx, ring[:, 1] + cy,
                                      np.full(n, zz)]))
    verts = np.concatenate(rings, axis=0)
    faces = []
    for k in range(len(rings) - 1):
        faces += pg._ring_faces(n, k * n, (k + 1) * n, n)
    bc = len(verts)
    tc = bc + 1
    verts = np.concatenate([verts, [[cx, cy, z0]],
                            [[cx, cy, z0 + thickness + crown]]], axis=0)
    faces += pg._cap_faces(0, n, bc, flip=True)
    faces += pg._cap_faces((len(rings) - 1) * n, n, tc)
    return pg._component(name, verts, faces, role=role)


def resolve(envelope=PREMIUM_ENVELOPE, *, gap=4.0, margin=5.0,
            pan_depth=PRIMARY_PAN_DEPTH_MM):
    w, d, h = envelope
    spec = build_palt_p1(outer_width=w, outer_depth=d, outer_height=h,
                         inter_pan_gap=gap, outer_margin=margin)
    stack = height_stackup(spec, PALT_P1_MECHANISM)
    mod_w, _ = pocket_module_mm(spec, PALT_P1_MECHANISM)
    pitch = mod_w + gap
    wall = MOULDING["exterior_wall_mm"]
    base_th = spec.case.base_thickness.mm
    floor = MOULDING["pocket_floor_thickness_mm"]
    pocket_depth = (pan_depth + PAN_SYSTEM["seating_clearance_mm"]
                    + PAN_SYSTEM["adhesive_allowance_mm"]
                    + PAN_SYSTEM["pan_recess_mm"])
    deck_z = base_th + floor + pocket_depth
    base_height = deck_z + 1.4
    parting = ALLOWANCES["cosmetic_parting_gap_mm"]
    lid_height = h - base_height - parting
    return {
        "spec": spec, "envelope_mm": [w, d, h], "pitch_mm": round(pitch, 3),
        "case_wall_mm": wall, "base_thickness_mm": base_th,
        "pocket_floor_mm": floor, "pocket_depth_mm": round(pocket_depth, 3),
        "pocket_floor_z_mm": round(deck_z - pocket_depth, 3),
        "deck_z_mm": round(deck_z, 3), "base_height_mm": round(base_height, 3),
        "lid_height_mm": round(lid_height, 3), "parting_gap_mm": parting,
        "pan_depth_mm": pan_depth,
        "hinge_wall_mm": wall + MOULDING["hinge_reinforcement_mm"],
        "clasp_wall_mm": wall + MOULDING["clasp_reinforcement_mm"],
        "hinge_axis_y_mm": d / 2.0 - (wall
                                      + MOULDING["hinge_reinforcement_mm"]) / 2.0,
        "hinge_axis_z_mm": round(base_height + parting / 2.0, 3),
        "open_review_angle_deg": OPEN_REVIEW_ANGLE_DEG,
        "moulding": dict(MOULDING), "pan_system": dict(PAN_SYSTEM),
        "hinge": dict(HINGE), "clasp": dict(CLASP), "mirror": dict(MIRROR),
        "height_stackup": stack.as_dict(),
        "provenance": "resolved from PALT-M2/M3 contracts; every moulding "
                      "and mechanism figure is DESIGN_DEFAULT / "
                      "NOT_MANUFACTURER_CONFIRMED",
    }


# ---------------------------------------------------------------------------
# assembly


def build_moulded_components(envelope=PREMIUM_ENVELOPE, *, gap=4.0,
                             margin=5.0,
                             pan_depth=PRIMARY_PAN_DEPTH_MM):
    """All M4B components. The tray is a CSG definition (blank minus
    drafted pocket cutters), so the pockets are genuinely recessed."""
    dims = resolve(envelope, gap=gap, margin=margin, pan_depth=pan_depth)
    w, d, h = dims["envelope_mm"]
    wall = dims["case_wall_mm"]
    base_th = dims["base_thickness_mm"]
    deck_z = dims["deck_z_mm"]
    base_h = dims["base_height_mm"]
    lid_h = dims["lid_height_mm"]
    parting = dims["parting_gap_mm"]
    pitch = dims["pitch_mm"]
    pocket_depth = dims["pocket_depth_mm"]
    ps = PAN_SYSTEM
    centres = [((c - 1) * pitch, (r - 1) * pitch)
               for r in range(3) for c in range(3)]
    comps = {}

    # --- base shell (drafted, filleted) ---------------------------------
    comps["base_outer_shell"] = drafted_box(
        "base_outer_shell", w, d, base_h, CORNER_R,
        MOULDING["tray_draft_deg"], z0=0.0, edge_r=EDGE_R,
        role="outer base shell (drafted moulded body)")
    comps["base_cavity_cutter"] = drafted_box(
        "base_cavity_cutter", w - 2 * wall, d - 2 * wall, base_h,
        max(CORNER_R - wall, 1.0), MOULDING["tray_draft_deg"], z0=base_th,
        edge_r=0.3, role="CSG cutter: base cavity")
    comps["base_outer_shell"]["csg"] = {
        "op": "DIFFERENCE", "cutters": ["base_cavity_cutter"]}

    # --- moulded tray: ONE continuous deck minus nine drafted pockets ----
    comps["moulded_tray"] = drafted_box(
        "moulded_tray", w - 2 * wall, d - 2 * wall, deck_z - base_th,
        max(CORNER_R - wall, 1.0), MOULDING["tray_draft_deg"], z0=base_th,
        edge_r=MOULDING["internal_fillet_mm"],
        role="moulded tray — one continuous upper deck")
    cutters = []
    for i, (cx, cy) in enumerate(centres):
        name = f"pocket_cutter_{i+1}"
        comps[name] = drafted_cylinder(
            name, ps["pocket_diameter_mm"] / 2.0, pocket_depth,
            MOULDING["pocket_draft_deg"], centre=(cx, cy), z_top=deck_z,
            role=f"CSG cutter: recessed pocket {i+1} (drafted)")
        cutters.append(name)
    comps["moulded_tray"]["csg"] = {"op": "DIFFERENCE", "cutters": cutters}

    # --- structural ribs under the deck ---------------------------------
    for i, x in enumerate((-pitch / 2.0, pitch / 2.0)):
        comps[f"tray_rib_{i+1}"] = pg.filleted_slab(
            f"tray_rib_{i+1}", MOULDING["rib_thickness_mm"],
            d - 2 * wall - 6.0, MOULDING["rib_height_mm"], 0.3, 0.2,
            z0=base_th, role=f"structural rib {i+1} under the tray deck")
        comps[f"tray_rib_{i+1}"]["vertices"][:, 0] += x

    # --- pans and powder, seated ON THE POCKET FLOOR ---------------------
    pocket_floor_z = deck_z - pocket_depth
    pan_z = pocket_floor_z + ps["adhesive_allowance_mm"]
    for i, (cx, cy) in enumerate(centres):
        comps[f"metal_pan_{i+1}"] = metal_pan(
            f"metal_pan_{i+1}", ps["pan_outside_diameter_mm"] / 2.0,
            pan_depth, ps["metal_pan_wall_mm"], ps["metal_pan_floor_mm"],
            centre=(cx, cy), z0=pan_z,
            role=f"provisional metal pan {i+1} (seated in pocket {i+1})")
        comps[f"powder_{i+1}"] = powder_volume(
            f"powder_{i+1}",
            ps["pan_outside_diameter_mm"] / 2.0 - ps["metal_pan_wall_mm"]
            - 0.05,
            pan_depth - ps["metal_pan_floor_mm"] - 0.15,
            ps["powder_crown_mm"],
            centre=(cx, cy), z0=pan_z + ps["metal_pan_floor_mm"],
            role=f"provisional powder volume {i+1}")

    # --- lid shell + backing --------------------------------------------
    lid_z0 = base_h + parting
    comps["lid_outer_shell"] = drafted_box(
        "lid_outer_shell", w, d, lid_h, CORNER_R,
        MOULDING["tray_draft_deg"], z0=lid_z0, edge_r=EDGE_R,
        role="outer lid shell (drafted)")
    comps["lid_cavity_cutter"] = drafted_box(
        "lid_cavity_cutter", w - 2 * wall, d - 2 * wall,
        lid_h - MIRROR["lid_backing_mm"], max(CORNER_R - wall, 1.0),
        MOULDING["tray_draft_deg"], z0=lid_z0 - 0.2, edge_r=0.3,
        role="CSG cutter: lid cavity")
    comps["lid_outer_shell"]["csg"] = {
        "op": "DIFFERENCE", "cutters": ["lid_cavity_cutter"]}

    # --- mirror mounting stack ------------------------------------------
    mb = MIRROR
    mirror_w = w - 2 * wall - 2 * mb["retaining_border_mm"]
    mirror_d = d - 2 * wall - 2 * mb["retaining_border_mm"]
    recess_top = lid_z0 + mb["recess_depth_mm"]
    comps["mirror_retaining_border"] = pg.wall_ring(
        "mirror_retaining_border",
        mirror_w + 2 * mb["retaining_border_mm"],
        mirror_d + 2 * mb["retaining_border_mm"],
        mirror_w + 2 * mb["perimeter_clearance_mm"],
        mirror_d + 2 * mb["perimeter_clearance_mm"],
        mb["recess_depth_mm"], max(CORNER_R - wall, 1.0), z0=lid_z0,
        role="mirror retaining border (recess wall)")
    comps["mirror_adhesive_pad"] = pg.filleted_slab(
        "mirror_adhesive_pad", mirror_w - 1.0, mirror_d - 1.0,
        mb["adhesive_pad_mm"], max(CORNER_R - wall - 1, 1.0), 0.05,
        z0=recess_top - mb["thickness_mm"] - mb["adhesive_pad_mm"],
        role="mirror adhesive pad / mounting layer")
    comps["mirror"] = pg.filleted_slab(
        "mirror", mirror_w, mirror_d, mb["thickness_mm"],
        max(CORNER_R - wall - 1, 1.0), 0.1,
        z0=recess_top - mb["thickness_mm"], role="provisional mirror solid")

    # --- hinge: alternating knuckles + real pin + caps -------------------
    hy, hz = dims["hinge_axis_y_mm"], dims["hinge_axis_z_mm"]
    hk = HINGE
    span = w - 2 * CORNER_R - 6.0
    k = hk["knuckle_count"]
    seg = span / k
    for i in range(k):
        x0 = -span / 2.0 + i * seg + hk["knuckle_gap_mm"] / 2.0
        length = seg - hk["knuckle_gap_mm"]
        owner_part = "base" if i % 2 == 0 else "lid"
        name = f"hinge_knuckle_{owner_part}_{i+1}"
        comps[name] = pg.cylinder(
            name, hk["barrel_outer_radius_mm"], length,
            centre=(x0, hy), z0=hz, axis="x",
            role=f"{owner_part} hinge knuckle {i+1} (alternating)")
        bore = f"hinge_bore_{i+1}"
        comps[bore] = pg.cylinder(
            bore, hk["pin_radius_mm"] + hk["pin_clearance_mm"],
            length + 0.4, centre=(x0 - 0.2, hy), z0=hz, axis="x",
            role=f"CSG cutter: knuckle bore {i+1}")
        comps[name]["csg"] = {"op": "DIFFERENCE", "cutters": [bore]}
    comps["hinge_pin"] = pg.cylinder(
        "hinge_pin", hk["pin_radius_mm"], span + 2.0,
        centre=(-span / 2.0 - 1.0, hy), z0=hz, axis="x",
        role="hinge pin (continuous axis)")
    for i, x in enumerate((-span / 2.0 - 1.0 - hk["pin_cap_length_mm"],
                           span / 2.0 + 1.0)):
        comps[f"hinge_pin_cap_{i+1}"] = pg.cylinder(
            f"hinge_pin_cap_{i+1}", hk["pin_cap_radius_mm"],
            hk["pin_cap_length_mm"], centre=(x, hy), z0=hz, axis="x",
            role=f"hinge pin end capture {i+1}")
    comps["hinge_reinforcement"] = pg.filleted_slab(
        "hinge_reinforcement", w - 2 * CORNER_R,
        MOULDING["hinge_reinforcement_mm"], base_h - base_th, 0.4,
        MOULDING["root_fillet_mm"] if "root_fillet_mm" in MOULDING else 0.3,
        z0=base_th, role="hinge-zone wall reinforcement (root support)")
    comps["hinge_reinforcement"]["vertices"][:, 1] += \
        d / 2.0 - wall - MOULDING["hinge_reinforcement_mm"] / 2.0

    # --- clasp: hook (lid) + detent (base) + flex zone + finger notch ----
    cl = CLASP
    clasp_y = -d / 2.0 + wall / 2.0
    comps["clasp_hook"] = pg.filleted_slab(
        "clasp_hook", cl["hook_width_mm"], cl["hook_thickness_mm"],
        cl["hook_drop_mm"], 0.4, cl["lead_in_chamfer_mm"],
        z0=lid_z0 - cl["hook_drop_mm"] + 0.2, role="lid snap hook")
    comps["clasp_hook"]["vertices"][:, 1] += clasp_y - 0.4
    comps["clasp_hook_lip"] = pg.filleted_slab(
        "clasp_hook_lip", cl["hook_width_mm"], cl["hook_lip_mm"], 1.0, 0.3,
        0.25, z0=lid_z0 - cl["hook_drop_mm"] + 0.2,
        role="hook engagement undercut (lip)")
    comps["clasp_hook_lip"]["vertices"][:, 1] += \
        clasp_y - 0.4 - cl["hook_thickness_mm"] / 2.0 - cl["hook_lip_mm"] / 2.0
    comps["clasp_detent"] = pg.filleted_slab(
        "clasp_detent", cl["detent_width_mm"], cl["detent_depth_mm"],
        cl["detent_height_mm"], 0.4, cl["lead_in_chamfer_mm"],
        z0=base_h - cl["detent_height_mm"], role="base snap detent")
    comps["clasp_detent"]["vertices"][:, 1] += \
        clasp_y - 0.4 - cl["hook_thickness_mm"] / 2.0 - cl["hook_lip_mm"] \
        - cl["release_clearance_mm"]
    comps["clasp_flex_zone"] = pg.filleted_slab(
        "clasp_flex_zone", cl["flex_zone_width_mm"],
        cl["flex_zone_thickness_mm"], base_h - base_th - 1.0, 0.4, 0.3,
        z0=base_th, role="local flex zone (thinned wall behind the detent)")
    comps["clasp_flex_zone"]["vertices"][:, 1] += clasp_y
    comps["finger_notch_cutter"] = drafted_box(
        "finger_notch_cutter", cl["finger_notch_width_mm"],
        cl["finger_notch_depth_mm"] * 2, 4.0, 2.0, 0.0,
        z0=base_h - 2.0, edge_r=1.4,
        centre=(0.0, -d / 2.0 - cl["finger_notch_depth_mm"] / 2.0 + 0.6),
        role="CSG cutter: finger-opening notch (opening affordance)")
    comps["base_outer_shell"]["csg"]["cutters"].append("finger_notch_cutter")
    comps["clasp_reinforcement"] = pg.filleted_slab(
        "clasp_reinforcement", cl["detent_width_mm"] + 8.0,
        MOULDING["clasp_reinforcement_mm"], base_h - base_th, 0.4, 0.3,
        z0=base_th, role="clasp-zone wall reinforcement")
    comps["clasp_reinforcement"]["vertices"][:, 1] -= \
        d / 2.0 - wall - MOULDING["clasp_reinforcement_mm"] / 2.0

    return comps, dims


LID_GROUP = ("lid_outer_shell", "lid_cavity_cutter", "mirror",
             "mirror_adhesive_pad", "mirror_retaining_border", "clasp_hook",
             "clasp_hook_lip")
CUTTERS = ("base_cavity_cutter", "lid_cavity_cutter", "finger_notch_cutter")


def is_cutter(name):
    return (name in CUTTERS or name.startswith("pocket_cutter_")
            or name.startswith("hinge_bore_"))


def lid_knuckles(components):
    return [n for n in components if n.startswith("hinge_knuckle_lid_")]


def compose_moulded_state(components, dims, state, *,
                          open_angle_deg=OPEN_REVIEW_ANGLE_DEG):
    if state not in STATES:
        raise ValueError(f"unknown state {state!r}")
    axis = (dims["hinge_axis_y_mm"], dims["hinge_axis_z_mm"])
    lid_names = set(LID_GROUP) | set(lid_knuckles(components))

    def rotate(angle):
        return {n: pg.transform(c, rotate_x_about=axis,
                                angle_deg=-abs(angle))
                for n, c in components.items() if n in lid_names}

    if state == "CLOSED":
        return dict(components)
    if state == "OPEN_90":
        out = dict(components)
        out.update(rotate(90.0))
        return out
    if state == "OPEN_REVIEW_ANGLE":
        out = dict(components)
        out.update(rotate(open_angle_deg))
        return out
    if state == "EXPLODED":
        lifts = {"lid_outer_shell": 54.0, "lid_cavity_cutter": 54.0,
                 "mirror_retaining_border": 44.0,
                 "mirror_adhesive_pad": 38.0, "mirror": 34.0,
                 "clasp_hook": 44.0, "clasp_hook_lip": 44.0,
                 "moulded_tray": 12.0}
        out = {}
        for n, c in components.items():
            lift = lifts.get(n, 0.0)
            if n.startswith("metal_pan_"):
                lift = 24.0
            elif n.startswith("powder_"):
                lift = 30.0
            elif n.startswith("pocket_cutter_"):
                lift = 12.0
            out[n] = pg.transform(c, translate=(0, 0, lift))
        return out
    if state == "BASE_ONLY":
        return {n: c for n, c in components.items() if n not in lid_names}
    if state == "LID_ONLY":
        return {n: c for n, c in components.items() if n in lid_names}
    if state == "TRAY_ONLY":
        return {n: c for n, c in components.items()
                if n == "moulded_tray" or n.startswith("pocket_cutter_")
                or n.startswith("metal_pan_") or n.startswith("powder_")
                or n.startswith("tray_rib_")}
    if state == "HINGE_ONLY":
        return {n: c for n, c in components.items()
                if n.startswith("hinge_")}
    if state == "CLASP_ONLY":
        return {n: c for n, c in components.items()
                if n.startswith("clasp_") or n == "finger_notch_cutter"}
    if state == "MIRROR_STACK":
        return {n: c for n, c in components.items()
                if n.startswith("mirror")}
    return {n: c for n, c in components.items()
            if n.startswith("hinge_") or n.startswith("clasp_")}


def moulded_manifest(components, dims) -> dict:
    return {
        "record_type": "palt_p1_m4b_component_manifest/1.0",
        "schema": SCHEMA, "revision": REVISION,
        "envelope_mm": dims["envelope_mm"],
        "component_count": len(components),
        "csg_definitions": {n: c["csg"] for n, c in components.items()
                            if "csg" in c},
        "components": [
            {"name": n, "mesh_identity": c["mesh_identity"],
             "role": c["role"], "is_cutter": is_cutter(n),
             "vertex_count": int(len(c["vertices"])),
             "face_count": int(len(c["faces"]))}
            for n, c in sorted(components.items())],
        "pan_system": dims["pan_system"],
        "moulding": dims["moulding"],
        "hinge": dims["hinge"], "clasp": dims["clasp"],
        "mirror": dims["mirror"],
        "resolved_dimensions": {k: v for k, v in dims.items()
                                if k not in ("spec",)},
        "contract_identity": dims["spec"].identity(),
        "contract_spec": to_jsonable(dims["spec"]),
        "authority": {
            "CONTRACT_GEOMETRY": "resolved from PALT-M2/M3 contracts",
            "VISUALIZATION_GEOMETRY": "review only",
            "MECHANISM_ASSUMPTIONS": "DESIGN_DEFAULT, "
                                     "NOT_MANUFACTURER_CONFIRMED",
            "MOULDING_ASSUMPTIONS": "DESIGN_DEFAULT draft/fillet/rib "
                                    "figures — no tooling authority",
            "MANUFACTURING_GEOMETRY": "NOT_ESTABLISHED",
            "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
            "PALT_P1_OWNER_APPROVAL": "REJECTED_PENDING_M4B",
        },
    }
