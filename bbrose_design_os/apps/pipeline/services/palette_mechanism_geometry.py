"""PALT-M4 — PALT-P1 assembly builder and state engine.

Builds every component independently from the accepted contracts, then
composes deterministic states. The lid group is articulated about the
hinge axis, so OPEN and CLOSED share identical component identities by
construction — they cannot drift.

Owner decisions applied (2026-08-05):
  envelope 116 x 116 x 15 (PROVISIONALLY_APPROVED_FOR_GEOMETRY_DEVELOPMENT)
  hinge WALL_INTEGRATED_PIN_HINGE at TOP_EDGE
  clasp WALL_INTEGRATED_SNAP_CLASP at BOTTOM_EDGE
  opening UPWARD, front artwork with the clasp at the bottom
  OPEN_REVIEW_ANGLE 110 deg (DESIGN_DEFAULT, NOT_MANUFACTURER_CONFIRMED)
"""
from __future__ import annotations

from apps.pipeline.services import palette_geometry as pg
from apps.pipeline.services.palette_contracts import to_jsonable
from apps.pipeline.services.palette_stackup_engine import (
    ALLOWANCES, height_stackup, pocket_module_mm)
from apps.pipeline.services.palt_p1 import build_palt_p1
from apps.pipeline.services.palette_mechanism_contracts import (
    MechanismStrategySpec)

ASSEMBLY_SCHEMA = "palt_p1_assembly/1.0"

STATES = ("CLOSED", "OPEN_90", "OPEN_REVIEW_ANGLE", "EXPLODED",
          "BASE_ONLY", "LID_ONLY", "TRAY_ONLY", "MECHANISM_DETAIL")

OPEN_REVIEW_ANGLE_DEG = 110.0          # DESIGN_DEFAULT, configurable
PREMIUM_ENVELOPE = (116.0, 116.0, 15.0)

# PALT-P1 mechanism, per the owner's correction of the ambiguous "long edge"
PALT_P1_MECHANISM = MechanismStrategySpec(
    hinge_strategy="WALL_INTEGRATED_PIN_HINGE",
    clasp_strategy="WALL_INTEGRATED_SNAP_CLASP",
    retention_strategy="ADHESIVE_FIXED",
    hinge_edge="TOP_EDGE", clasp_edge="BOTTOM_EDGE",
    case_orientation="LANDSCAPE", opening_direction="UPWARD",
    notes=("square pilot: hinge TOP_EDGE, clasp BOTTOM_EDGE, opening "
           "UPWARD, front artwork orientation CLASP_AT_BOTTOM",),
)

# mechanism geometry estimates (all DESIGN_DEFAULT)
HINGE = {
    "barrel_radius_mm": 1.6,
    "barrel_length_mm": 14.0,
    "barrel_count": 3,
    "pin_radius_mm": 0.8,
    "pin_overhang_mm": 2.0,
}
CLASP = {
    "hook_width_mm": 16.0,
    "hook_depth_mm": 2.2,
    "hook_height_mm": 2.6,
    "detent_width_mm": 18.0,
    "detent_depth_mm": 1.4,
    "detent_height_mm": 2.0,
}
CORNER_R = 6.0
EDGE_R = 1.2


def resolve_dimensions(envelope=PREMIUM_ENVELOPE, *, gap=4.0, margin=5.0):
    """Every internal dimension RESOLVED from the contracts — never eyeballed."""
    w, d, h = envelope
    spec = build_palt_p1(outer_width=w, outer_depth=d, outer_height=h,
                         inter_pan_gap=gap, outer_margin=margin)
    stack = height_stackup(spec, PALT_P1_MECHANISM)
    mod_w, mod_h = pocket_module_mm(spec, PALT_P1_MECHANISM)
    pitch = mod_w + spec.tray.inter_pan_gap.mm
    pan = spec.layout.pans[0]

    case_wall = spec.case.wall_thickness.mm
    base_th = spec.case.base_thickness.mm
    tray_floor = spec.tray.floor_thickness.mm
    lid_th = spec.lid.thickness.mm
    mirror_th = spec.mirror.thickness.mm
    parting = ALLOWANCES["cosmetic_parting_gap_mm"]

    # vertical partition of the 15 mm envelope (derived, not authored)
    base_height = base_th + tray_floor + pan.depth.mm + \
        ALLOWANCES["pan_proud_recess_mm"] + 1.6
    lid_height = h - base_height - parting
    return {
        "spec": spec,
        "envelope_mm": [w, d, h],
        "case_wall_mm": case_wall,
        "base_thickness_mm": base_th,
        "tray_floor_mm": tray_floor,
        "lid_thickness_mm": lid_th,
        "mirror_thickness_mm": mirror_th,
        "parting_gap_mm": parting,
        "base_height_mm": round(base_height, 3),
        "lid_height_mm": round(lid_height, 3),
        "pan_diameter_mm": pan.width.mm,
        "pan_depth_mm": pan.depth.mm,
        "pocket_diameter_mm": mod_w,
        "pitch_mm": round(pitch, 3),
        "inter_pan_gap_mm": spec.tray.inter_pan_gap.mm,
        "outer_margin_mm": spec.tray.outer_margin.mm,
        "height_stackup": stack.as_dict(),
        "hinge": dict(HINGE),
        "hinge_wall_mm": None,   # filled by build_components
        "clasp_wall_mm": None,
        "clasp": dict(CLASP),
        "open_review_angle_deg": OPEN_REVIEW_ANGLE_DEG,
        "provenance": "resolved from PALT-M2 contracts + PALT-M3 stack-up; "
                      "mechanism figures are DESIGN_DEFAULT estimates",
    }


def build_components(envelope=PREMIUM_ENVELOPE, *, gap=4.0, margin=5.0,
                     label="PALT-P1"):
    """All components, each with an independent identity. Never merged."""
    dims = resolve_dimensions(envelope, gap=gap, margin=margin)
    w, d, h = dims["envelope_mm"]
    wall = dims["case_wall_mm"]
    base_h = dims["base_height_mm"]
    lid_h = dims["lid_height_mm"]
    parting = dims["parting_gap_mm"]
    pitch = dims["pitch_mm"]
    pocket_r = dims["pocket_diameter_mm"] / 2.0
    pan_r = dims["pan_diameter_mm"] / 2.0
    pan_depth = dims["pan_depth_mm"]
    tray_floor = dims["tray_floor_mm"]
    base_th = dims["base_thickness_mm"]

    comps = {}

    # --- base group --------------------------------------------------------
    comps["base_outer_shell"] = pg.filleted_slab(
        "base_outer_shell", w, d, base_th, CORNER_R, EDGE_R, z0=0.0,
        role="outer base shell (floor slab)")
    hinge_wall = wall + PALT_P1_MECHANISM.hinge_envelope.wall_add.mm
    clasp_wall = wall + PALT_P1_MECHANISM.clasp_envelope.wall_add.mm
    comps["base_wall_ring"] = pg.wall_ring(
        "base_wall_ring", w, d, w - 2 * wall, d - 2 * wall,
        base_h - base_th, CORNER_R, z0=base_th,
        role="outer base shell (side walls)")
    # the wall-integrated strategies THICKEN their own edge locally — the
    # M3 envelope, applied rather than shrinking the mechanism to fit
    comps["hinge_wall_thickening"] = pg.filleted_slab(
        "hinge_wall_thickening", w - 2 * CORNER_R,
        PALT_P1_MECHANISM.hinge_envelope.wall_add.mm, base_h - base_th,
        0.4, 0.3, z0=base_th,
        role="local rear-wall thickening carrying the hinge barrels")
    comps["hinge_wall_thickening"]["vertices"][:, 1] += \
        d / 2.0 - wall - PALT_P1_MECHANISM.hinge_envelope.wall_add.mm / 2.0
    comps["clasp_wall_thickening"] = pg.filleted_slab(
        "clasp_wall_thickening", CLASP["detent_width_mm"] + 6.0,
        PALT_P1_MECHANISM.clasp_envelope.wall_add.mm, base_h - base_th,
        0.4, 0.3, z0=base_th,
        role="local front-wall thickening carrying the clasp detent")
    comps["clasp_wall_thickening"]["vertices"][:, 1] -= \
        d / 2.0 - wall - PALT_P1_MECHANISM.clasp_envelope.wall_add.mm / 2.0

    # --- inner tray: a manifold floor slab + nine annular pocket rings ---
    # (each ring is its own solid with its own identity — the palette is
    # never merged into one irreversible mesh)
    centres = [((c - 1) * pitch, (r - 1) * pitch)
               for r in range(3) for c in range(3)]
    comps["inner_tray"] = pg.filleted_slab(
        "inner_tray", w - 2 * wall, d - 2 * wall, tray_floor, 
        max(CORNER_R - wall, 1.0), 0.3, z0=base_th,
        role="inner tray floor")
    web = (pitch - dims["pocket_diameter_mm"]) / 2.0
    for i, (cx, cy) in enumerate(centres):
        comps[f"pocket_ring_{i+1}"] = pg.annulus_solid(
            f"pocket_ring_{i+1}", pocket_r, pocket_r + web,
            pan_depth + ALLOWANCES["pan_proud_recess_mm"],
            centre=(cx, cy), z0=base_th + tray_floor,
            role=f"pocket web wall {i+1} (forms pan well {i+1})")

    # --- nine provisional pan solids (independent identities) --------------
    for i, (cx, cy) in enumerate(centres):
        comps[f"pan_{i+1}"] = pg.cylinder(
            f"pan_{i+1}", pan_r, pan_depth - 0.2, centre=(cx, cy),
            z0=base_th + tray_floor + 0.1,
            role=f"provisional pan solid {i+1} (adhesive-fixed)")

    # --- lid group (built in CLOSED position, articulated later) -----------
    lid_z0 = base_h + parting
    comps["lid_outer_shell"] = pg.filleted_slab(
        "lid_outer_shell", w, d, dims["lid_thickness_mm"], CORNER_R, EDGE_R,
        z0=lid_z0 + lid_h - dims["lid_thickness_mm"],
        role="outer lid shell")
    comps["lid_inner_structure"] = pg.wall_ring(
        "lid_inner_structure", w, d, w - 2 * wall, d - 2 * wall,
        lid_h - dims["lid_thickness_mm"], CORNER_R, z0=lid_z0,
        role="inner lid structure (skirt)")
    border = ALLOWANCES["lid_structural_border_mm"]
    mirror_w = w - 2 * wall - 2 * border
    mirror_d = d - 2 * wall - 2 * border
    comps["mirror_recess"] = pg.wall_ring(
        "mirror_recess", mirror_w + 2 * 1.2, mirror_d + 2 * 1.2,
        mirror_w, mirror_d, dims["mirror_thickness_mm"] + 0.4,
        max(CORNER_R - wall - border, 1.0), z0=lid_z0,
        role="mirror recess frame")
    comps["mirror"] = pg.filleted_slab(
        "mirror", mirror_w, mirror_d, dims["mirror_thickness_mm"],
        max(CORNER_R - wall - border, 1.0), 0.15,
        z0=lid_z0 + 0.2, role="provisional mirror solid")

    # --- wall-integrated hinge (TOP_EDGE = +y) -----------------------------
    hinge_y = d / 2.0 - hinge_wall / 2.0
    hinge_z = base_h + parting / 2.0
    # the TOP_EDGE hinge axis runs along X at y = +d/2, so barrels and pin
    # are cylinders extruded along X (not Y)
    span = w - 2 * CORNER_R
    spacing = span / HINGE["barrel_count"]
    for i in range(HINGE["barrel_count"]):
        x0 = -span / 2.0 + i * spacing + \
            (spacing - HINGE["barrel_length_mm"]) / 2.0
        comps[f"hinge_barrel_{i+1}"] = pg.cylinder(
            f"hinge_barrel_{i+1}", HINGE["barrel_radius_mm"],
            HINGE["barrel_length_mm"], centre=(x0, hinge_y),
            z0=hinge_z, axis="x",
            role=f"wall-integrated hinge barrel {i+1}")
    comps["hinge_pin"] = pg.cylinder(
        "hinge_pin", HINGE["pin_radius_mm"], span, centre=(-span / 2.0,
                                                           hinge_y),
        z0=hinge_z, axis="x", role="hinge pin")

    # --- wall-integrated snap clasp (BOTTOM_EDGE = -y) ---------------------
    clasp_y = -d / 2.0 + clasp_wall / 2.0
    comps["clasp_hook"] = pg.filleted_slab(
        "clasp_hook", CLASP["hook_width_mm"], CLASP["hook_depth_mm"],
        CLASP["hook_height_mm"], 0.6, 0.3,
        z0=lid_z0 - CLASP["hook_height_mm"] / 2.0,
        role="wall-integrated snap clasp hook (lid side)")
    comps["clasp_hook"]["vertices"][:, 1] += clasp_y
    comps["clasp_detent"] = pg.filleted_slab(
        "clasp_detent", CLASP["detent_width_mm"], CLASP["detent_depth_mm"],
        CLASP["detent_height_mm"], 0.6, 0.3,
        z0=base_h - CLASP["detent_height_mm"],
        role="wall-integrated snap clasp detent (base side)")
    comps["clasp_detent"]["vertices"][:, 1] += clasp_y

    dims["hinge_wall_mm"] = hinge_wall
    dims["clasp_wall_mm"] = clasp_wall
    dims["hinge_axis_y_mm"] = hinge_y
    dims["hinge_axis_z_mm"] = hinge_z
    return comps, dims


LID_GROUP = ("lid_outer_shell", "lid_inner_structure", "mirror_recess",
             "mirror", "clasp_hook")


def compose_state(components, dims, state: str,
                  open_angle_deg: float = OPEN_REVIEW_ANGLE_DEG) -> dict:
    """Deterministic state composition. The lid group is ARTICULATED about
    the hinge axis — never re-authored — so identities are shared."""
    if state not in STATES:
        raise ValueError(f"unknown state {state!r}")
    hinge_axis = (dims["hinge_axis_y_mm"], dims["hinge_axis_z_mm"])

    def lid_open(angle):
        # opening_direction UPWARD: the front edge sweeps up and over the
        # hinge, which is a NEGATIVE rotation about +x in this frame
        return {n: pg.transform(c, rotate_x_about=hinge_axis,
                                angle_deg=-abs(angle))
                for n, c in components.items() if n in LID_GROUP}

    out = {}
    if state == "CLOSED":
        out = dict(components)
    elif state == "OPEN_90":
        out = dict(components)
        out.update(lid_open(90.0))
    elif state == "OPEN_REVIEW_ANGLE":
        out = dict(components)
        out.update(lid_open(open_angle_deg))
    elif state == "EXPLODED":
        out = {}
        lifts = {"lid_outer_shell": 46.0, "lid_inner_structure": 38.0,
                 "mirror_recess": 32.0, "mirror": 28.0,
                 "clasp_hook": 38.0, "inner_tray": 10.0}
        for n, c in components.items():
            lift = lifts.get(n, 0.0)
            if n.startswith("pocket_ring_"):
                lift = 14.0
            elif n.startswith("pan_"):
                lift = 22.0
            out[n] = pg.transform(c, translate=(0, 0, lift))
    elif state == "BASE_ONLY":
        out = {n: c for n, c in components.items()
               if n not in LID_GROUP and not n.startswith("hinge_pin")}
    elif state == "LID_ONLY":
        out = {n: c for n, c in components.items() if n in LID_GROUP}
    elif state == "TRAY_ONLY":
        out = {n: c for n, c in components.items()
               if n == "inner_tray" or n.startswith("pocket_ring_")
               or n.startswith("pan_")}
    elif state == "MECHANISM_DETAIL":
        out = {n: c for n, c in components.items()
               if n.startswith("hinge_") or n.startswith("clasp_")
               or n in ("base_wall_ring", "lid_inner_structure")}
    return out


def assembly_manifest(components, dims, label="PALT-P1") -> dict:
    return {
        "record_type": "palt_p1_component_manifest/1.0",
        "schema": ASSEMBLY_SCHEMA,
        "label": label,
        "envelope_mm": dims["envelope_mm"],
        "component_count": len(components),
        "components": [
            {"name": n, "mesh_identity": c["mesh_identity"],
             "authority": c["authority"], "role": c["role"],
             "vertex_count": int(len(c["vertices"])),
             "face_count": int(len(c["faces"]))}
            for n, c in sorted(components.items())],
        "mechanism": {
            "hinge_strategy": PALT_P1_MECHANISM.hinge_strategy,
            "clasp_strategy": PALT_P1_MECHANISM.clasp_strategy,
            "retention_strategy": PALT_P1_MECHANISM.retention_strategy,
            "hinge_edge": PALT_P1_MECHANISM.hinge_edge,
            "clasp_edge": PALT_P1_MECHANISM.clasp_edge,
            "opening_direction": PALT_P1_MECHANISM.opening_direction,
            "front_artwork_orientation": "CLASP_AT_BOTTOM",
            "open_review_angle_deg": dims["open_review_angle_deg"],
            "open_angle_provenance": "DESIGN_DEFAULT — "
                                     "NOT_MANUFACTURER_CONFIRMED",
            "authority": "MECHANISM_ASSUMPTIONS — engineering estimates",
        },
        "resolved_dimensions": {k: v for k, v in dims.items()
                                if k not in ("spec",)},
        "contract_identity": dims["spec"].identity(),
        "contract_spec": to_jsonable(dims["spec"]),
        "authority": {
            "CONTRACT_GEOMETRY": "resolved from PALT-M2/M3 contracts",
            "VISUALIZATION_GEOMETRY": "meshes for review only",
            "MECHANISM_ASSUMPTIONS": "DESIGN_DEFAULT estimates",
            "MANUFACTURING_GEOMETRY": "NOT_ESTABLISHED",
            "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
            "PALT_P1_OWNER_APPROVAL": "PENDING_VISUAL_REVIEW",
        },
    }
