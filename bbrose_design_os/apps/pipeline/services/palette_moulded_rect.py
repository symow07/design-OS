"""M4B-B — the PALT-P1B moulded assembly for the ES3083 palette.

PALT-P1A stays exactly as it is. This is a separate family, so nothing
here can move the round assembly's pinned identities.

Two things differ from P1A beyond the pan shape.

*Boolean-free throughout.* P1A recesses its pockets with Blender Boolean
cutters. ``PALETTE_TRAY_GEOMETRY_AUTHORITY`` is
``DETERMINISTIC_PYTHON_MESH_CONSTRUCTION``, so P1B's tray comes from
``build_rect_recessed_tray`` and its lid is a genuinely hollow shell
constructed as triangles. No component here is a cutter.

*Concept-sensitive.* §3 says visible proportions come from the confirmed
design intent where available and generic defaults may only fill
unresolved hidden construction. The case footprint follows the derived
tray envelope, which follows the ES3083 pan field; wall thickness, draft,
fillets, knuckle counts and clearances are hidden construction and stay
generic. Every dimension records which of the two it is.

The lid is a real moulded part — outer shell, inner shell, controlled
wall, draft, interior fillet, structural rim, hinge roots, clasp hook
interface and a mirror recess when configured. It is not a floating
plate.
"""
from __future__ import annotations

import math

import numpy as np

from apps.pipeline.services import palette_geometry as pg
from apps.pipeline.services import palette_identity as PI
from apps.pipeline.services import palette_moulded_geometry as MG
from apps.pipeline.services import palette_rect_pan as RP
from apps.pipeline.services import palette_rect_tray_geometry as RT
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "palt_p1b_moulded_assembly/1.0"
REVISION = "M4B-B"

STATES = ("CLOSED", "OPEN_90", "OPEN_REVIEW_ANGLE", "EXPLODED")
OPEN_REVIEW_ANGLE_DEG = 110.0

VISIBLE = "FROM_CONFIRMED_DESIGN_INTENT"
HIDDEN = "GENERIC_DEFAULT_HIDDEN_CONSTRUCTION"

#: Hidden construction. Generic by policy — none of it is visible in the
#: ES3083 sheet, so none of it may claim to come from the design.
CONSTRUCTION = {
    "case_wall_mm": 2.0,
    "base_floor_mm": 1.5,
    "lid_wall_mm": 1.6,
    "lid_roof_mm": 1.5,
    "lid_interior_fillet_mm": 1.0,
    "lid_rim_height_mm": 1.2,
    "lid_rim_inset_mm": 0.6,
    "draft_deg": 1.5,
    "parting_gap_mm": 0.2,
    "lid_interior_clearance_mm": 0.8,
}

HINGE = {
    "knuckle_count": 5,
    "knuckle_gap_mm": 0.35,
    "barrel_outer_radius_mm": 1.9,
    "pin_radius_mm": 0.7,
    "pin_clearance_mm": 0.10,
    "rotational_clearance_mm": 0.25,
    "root_fillet_mm": 0.8,
    "pin_cap_radius_mm": 1.0,
    "pin_cap_length_mm": 1.2,
    "reinforcement_depth_mm": 3.0,
    "open_stop_deg": 118.0,
}

CLASP = {
    "hook_width_mm": 18.0, "hook_thickness_mm": 1.6, "hook_drop_mm": 3.2,
    "hook_lip_mm": 0.9, "lead_in_chamfer_mm": 0.7,
    "detent_width_mm": 20.0, "detent_height_mm": 2.4,
    "detent_depth_mm": 1.1, "release_clearance_mm": 0.25,
    "flex_zone_width_mm": 24.0, "flex_zone_thickness_mm": 1.1,
    "finger_notch_width_mm": 22.0, "finger_notch_depth_mm": 2.6,
    "engagement_depth_mm": 0.9,
}

MIRROR = {
    "thickness_mm": 1.0, "adhesive_pad_mm": 0.20, "recess_depth_mm": 1.4,
    "retaining_border_mm": 2.0, "perimeter_clearance_mm": 0.30,
    "safety_gap_mm": 0.30, "lid_backing_mm": 1.2,
}

CONFIRMED, PROVISIONAL, UNRESOLVED = (
    "CONFIRMED", "PROVISIONAL", "UNRESOLVED_FROM_CONCEPT")

CORNER_R = 6.0
EDGE_R = 1.2


class RectAssemblyError(ValueError):
    """Raised when the P1B assembly cannot be built exactly."""


# --------------------------------------------------------------------------
# deterministic hollow shells
# --------------------------------------------------------------------------

def _loop(w, d, r, z, *, centre=(0.0, 0.0)):
    """A rounded-rect ring at one elevation, with inward normals."""
    pts = RT._rounded_rect_uniform(w, d, r, RECT_LOOP_SAMPLES)
    return [(centre[0] + x, centre[1] + y, z, nx, ny) for x, y, nx, ny in pts]


RECT_LOOP_SAMPLES = 96


def _mirror_z(component, about):
    """Reflect a component in z. A lid is a shell whose cavity opens
    DOWNWARD; building it opening upward produces a shallow tray that is
    perfectly manifold and obviously wrong the moment it is rendered."""
    v = component["vertices"].copy()
    v[:, 2] = 2.0 * about - v[:, 2]
    out = dict(component)
    out["vertices"] = v
    out["faces"] = component["faces"][:, [0, 2, 1]]
    return MG._normalized(pg._component(component["name"], v, out["faces"],
                                        role=component["role"]))


def _shell(name, *, w, d, h, corner_r, wall, floor, draft_deg, z0,
           open_top=True, open_down=False, role=""):
    """A genuinely hollow drafted box: outer wall, rim, inner wall, floor.

    Not a slab with a cutter — the cavity is real triangles, so the part
    is manifold without any Boolean ever running.
    """
    if wall <= 0 or wall * 2 >= min(w, d):
        raise RectAssemblyError(f"{name}: wall {wall} does not fit {w}x{d}")
    if floor <= 0 or floor >= h:
        raise RectAssemblyError(f"{name}: floor {floor} does not fit {h}")
    inset = h * math.tan(math.radians(draft_deg))
    if inset >= corner_r:
        raise RectAssemblyError(f"{name}: draft collapses the corner")

    verts: list = []
    faces: list = []

    def ring(ww, dd, rr, z):
        base = len(verts)
        for x, y, _z, _nx, _ny in _loop(ww, dd, rr, z):
            verts.append([x, y, z])
        return list(range(base, len(verts)))

    n = RECT_LOOP_SAMPLES

    def strip(a, b):
        for i in range(n):
            j = (i + 1) % n
            faces.append((a[i], b[i], b[j]))
            faces.append((a[i], b[j], a[j]))

    def fan(loop, centre_idx, flip=False):
        for i in range(n):
            j = (i + 1) % n
            faces.append((loop[j], loop[i], centre_idx) if flip
                         else (loop[i], loop[j], centre_idx))

    # outer surface: bottom (inset by draft) -> top
    out_bot = ring(w - 2 * inset, d - 2 * inset, corner_r - inset, z0)
    out_top = ring(w, d, corner_r, z0 + h)
    strip(out_bot, out_top)

    iw, idp = w - 2 * wall, d - 2 * wall
    ir = max(corner_r - wall, 0.4)
    if open_top:
        # rim across the wall thickness, then the inner cavity wall down
        # Role discipline: _strip emits loop_a backwards and loop_b
        # forwards, so a loop shared by two strips must alternate roles,
        # and a cap must traverse its loop the way the strip did NOT.
        cav = (h - floor) * math.tan(math.radians(draft_deg))
        in_top = ring(iw, idp, ir, z0 + h)
        strip(out_top, in_top)
        in_bot = ring(iw - 2 * cav, idp - 2 * cav,
                      max(ir - cav, 0.3), z0 + floor)
        strip(in_top, in_bot)
        c_in = len(verts)
        verts.append([0.0, 0.0, z0 + floor])
        fan(in_bot, c_in, flip=True)      # in_bot arrived as a loop_b
    else:
        c_top = len(verts)
        verts.append([0.0, 0.0, z0 + h])
        fan(out_top, c_top, flip=False)
    c_bot = len(verts)
    verts.append([0.0, 0.0, z0])
    fan(out_bot, c_bot, flip=False)       # out_bot arrived as a loop_a

    comp = MG._normalized(pg._component(name, np.asarray(verts, float),
                                        np.asarray(faces, np.int64),
                                        role=role))
    return _mirror_z(comp, z0 + h / 2.0) if open_down else comp


def _barrel(name, radius, length, *, x_centre, y, z, segments=48, role=""):
    """A cylinder whose AXIS lies along X — the hinge axis.

    pg.cylinder builds a Z-axis cylinder and pg.transform only rotates
    about X, so a hinge barrel has to be constructed directly. A knuckle
    standing on end would read as a boss, not a hinge.
    """
    x0, x1 = x_centre - length / 2.0, x_centre + length / 2.0
    verts, faces = [], []
    for x in (x0, x1):
        for i in range(segments):
            a = 2 * math.pi * i / segments
            verts.append([x, y + radius * math.cos(a),
                          z + radius * math.sin(a)])
    for i in range(segments):
        j = (i + 1) % segments
        a0, a1 = i, j
        b0, b1 = segments + i, segments + j
        faces.append((a0, b0, b1))
        faces.append((a0, b1, a1))
    c0, c1 = len(verts), len(verts) + 1
    verts.append([x0, y, z])
    verts.append([x1, y, z])
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, c0))
        faces.append((segments + j, segments + i, c1))
    return MG._normalized(pg._component(
        name, np.asarray(verts, float), np.asarray(faces, np.int64),
        role=role))


def _rect_prism(name, w, d, h, *, centre=(0.0, 0.0), z0=0.0, corner_r=0.0,
                role=""):
    """A filleted slab placed at ``centre`` — the shared primitive for
    clasp hooks, detents, ribs and mirror layers."""
    comp = pg.filleted_slab(name, w, d, h, corner_r,
                            min(0.3, h / 3.0, w / 3.0, d / 3.0),
                            z0=z0, role=role)
    if centre != (0.0, 0.0):
        comp = pg.transform(comp, translate=(centre[0], centre[1], 0.0))
    return MG._normalized(comp)


# --------------------------------------------------------------------------
# dimensions — visible from intent, hidden from policy
# --------------------------------------------------------------------------

def resolve_rect(intent=None, *, tray_spec=None) -> dict:
    """Resolve the P1B envelope, recording where each number came from."""
    tray = RT.build_rect_recessed_tray(tray_spec)
    ts = tray["spec"]
    c = CONSTRUCTION
    wall = c["case_wall_mm"]
    tray_w, tray_d = ts["tray_width_mm"], ts["tray_depth_mm"]
    # visible: the case follows the pan field the design established
    case_w = tray_w + 2 * wall
    case_d = tray_d + 2 * wall
    tray_h = ts["deck_z_mm"] - ts["underside_z_mm"]
    pan_depth = RP.contract_values()["pan_depth_mm"]
    base_h = c["base_floor_mm"] + tray_h + pan_depth \
        + c["lid_interior_clearance_mm"]
    mirror_stack = (MIRROR["thickness_mm"] + MIRROR["adhesive_pad_mm"]
                    + MIRROR["lid_backing_mm"])
    lid_h = max(c["lid_roof_mm"] + mirror_stack + 1.0, 5.0)
    return {
        "record_type": "palt_p1b_dimensions/1.0",
        "tray": tray,
        "case_width_mm": round(case_w, 6),
        "case_depth_mm": round(case_d, 6),
        "case_height_mm": round(base_h + lid_h + c["parting_gap_mm"], 6),
        "base_height_mm": round(base_h, 6),
        "lid_height_mm": round(lid_h, 6),
        "tray_height_mm": round(tray_h, 6),
        "pan_depth_mm": pan_depth,
        "parting_z_mm": round(base_h, 6),
        "hinge_axis_y_mm": round(-case_d / 2.0
                                 + HINGE["barrel_outer_radius_mm"], 6),
        "hinge_axis_z_mm": round(base_h + c["parting_gap_mm"] / 2.0, 6),
        "provenance": {
            "case_width_mm": VISIBLE, "case_depth_mm": VISIBLE,
            "pan_field": VISIBLE, "pan_shape": VISIBLE,
            "case_height_mm": HIDDEN, "lid_height_mm": HIDDEN,
            "wall_thickness": HIDDEN, "draft": HIDDEN,
            "hinge_geometry": HIDDEN, "clasp_geometry": HIDDEN,
        },
        "construction": dict(c),
        "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
        "PALT_P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
    }


def mirror_state(intent) -> str:
    """§6 — never invent a mirror the concept does not establish."""
    if intent is None:
        return UNRESOLVED
    f = intent.get("mirror_presence")
    if f is None:
        return UNRESOLVED
    if f.confirmation_state in ("HUMAN_CONFIRMED_DESIGN_INTENT",
                                "OWNER_CORRECTED") and f.value is True:
        return CONFIRMED
    if f.value is True:
        return PROVISIONAL
    return UNRESOLVED


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def build_rect_components(intent=None, *, tray_spec=None,
                          include_mirror=None) -> tuple:
    """Every P1B component. No cutters, no Booleans."""
    dims = resolve_rect(intent, tray_spec=tray_spec)
    c = CONSTRUCTION
    # M6-LID-ROOF-REPAIR: the contract's lid_roof_mm flows to
    # every consumer through dims — ONE statement of the value
    # (the contract), no in-code default anywhere downstream
    dims["lid_roof_mm"] = c["lid_roof_mm"]
    tray = dims["tray"]
    cw, cd = dims["case_width_mm"], dims["case_depth_mm"]
    base_h, lid_h = dims["base_height_mm"], dims["lid_height_mm"]
    parting = dims["parting_z_mm"] + c["parting_gap_mm"]
    comps: dict = {}

    # --- base shell: a real hollow moulded box --------------------------
    comps["base_outer_shell"] = _shell(
        "base_outer_shell", w=cw, d=cd, h=base_h, corner_r=CORNER_R,
        wall=c["case_wall_mm"], floor=c["base_floor_mm"],
        draft_deg=c["draft_deg"], z0=0.0, open_top=True,
        role="moulded base shell (hollow, drafted, Boolean-free)")

    # --- the deterministic recessed tray, seated on the base floor ------
    comps["moulded_tray"] = MG._normalized(pg.transform(
        pg._component("moulded_tray", tray["vertices"], tray["faces"],
                      role="deterministic recessed rectangular tray"),
        translate=(0.0, 0.0, c["base_floor_mm"])))

    # --- rectangular metal pans and powder ------------------------------
    z_seat = c["base_floor_mm"] + tray["elevations_mm"]["pocket_floor"]
    pan_c = RP.contract_values()
    for i, p in enumerate(tray["pockets"], start=1):
        cx, cy = p["centre_mm"]
        pan = RP.build_rect_pan(f"metal_pan_{i}", centre=(cx, cy),
                                z0=z_seat, role=f"rectangular metal pan {i}")
        comps[f"metal_pan_{i}"] = MG._normalized(
            pg._component(f"metal_pan_{i}", pan["vertices"], pan["faces"],
                          role=f"rectangular metal pan {i}"))
        pw = pan_c["pan_width_mm"] - 2 * pan_c["metal_wall_thickness_mm"]
        ph = pan_c["pan_height_mm"] - 2 * pan_c["metal_wall_thickness_mm"]
        comps[f"powder_{i}"] = _rect_prism(
            f"powder_{i}", pw, ph,
            pan_c["pan_depth_mm"] - pan_c["metal_floor_thickness_mm"]
            + pan_c["powder_crown_mm"],
            centre=(cx, cy),
            z0=z_seat + pan_c["metal_floor_thickness_mm"],
            corner_r=max(pan_c["corner_radius_mm"]
                         - pan_c["metal_wall_thickness_mm"], 0.2),
            role=f"provisional pressed powder {i}")

    # --- lid: outer shell, inner shell, rim ------------------------------
    comps["lid_outer_shell"] = _shell(
        "lid_outer_shell", w=cw, d=cd, h=lid_h, corner_r=CORNER_R,
        wall=c["lid_wall_mm"], floor=c["lid_roof_mm"],
        draft_deg=c["draft_deg"], z0=parting, open_top=True,
        open_down=True,
        role="moulded lid shell — hollow, drafted, cavity opening DOWN "
             "onto the base")
    comps["lid_structural_rim"] = _shell(
        "lid_structural_rim",
        w=cw - 2 * c["lid_wall_mm"] - 2 * c["lid_rim_inset_mm"],
        d=cd - 2 * c["lid_wall_mm"] - 2 * c["lid_rim_inset_mm"],
        h=c["lid_rim_height_mm"], corner_r=max(CORNER_R - 2.0, 1.0),
        wall=0.9, floor=0.5, draft_deg=0.0, z0=parting, open_top=True,
        open_down=True,
        role="lid structural rim — closes onto the base wall")

    # --- mirror stack ----------------------------------------------------
    state = mirror_state(intent) if include_mirror is None else (
        CONFIRMED if include_mirror else UNRESOLVED)
    if state in (CONFIRMED, PROVISIONAL):
        mw = cw - 2 * c["lid_wall_mm"] - 2 * MIRROR["retaining_border_mm"]
        md = cd - 2 * c["lid_wall_mm"] - 2 * MIRROR["retaining_border_mm"]
        # the roof is at the top of the lid, so the stack hangs DOWN from
        # it rather than sitting on the parting line
        z_m = (parting + lid_h - c["lid_roof_mm"]
               - MIRROR["lid_backing_mm"] - MIRROR["recess_depth_mm"])
        comps["mirror_adhesive_pad"] = _rect_prism(
            "mirror_adhesive_pad", mw, md, MIRROR["adhesive_pad_mm"],
            z0=z_m, corner_r=1.0, role="mirror mounting layer")
        comps["mirror"] = _rect_prism(
            "mirror", mw, md, MIRROR["thickness_mm"],
            z0=z_m + MIRROR["adhesive_pad_mm"], corner_r=1.0,
            role="provisional mirror solid")
        comps["mirror_retaining_border"] = _shell(
            "mirror_retaining_border",
            w=mw + 2 * MIRROR["retaining_border_mm"],
            d=md + 2 * MIRROR["retaining_border_mm"],
            h=MIRROR["recess_depth_mm"],
            corner_r=max(CORNER_R - 2.0, 1.0),
            wall=MIRROR["retaining_border_mm"], floor=0.4, draft_deg=0.0,
            z0=z_m, open_top=True, role="mirror retaining border")

    # --- hinge: alternating knuckles on one continuous axis --------------
    axis_y, axis_z = dims["hinge_axis_y_mm"], dims["hinge_axis_z_mm"]
    kn = HINGE["knuckle_count"]
    span = min(cw * 0.44, 48.0)
    pitch = span / kn
    width = pitch - HINGE["knuckle_gap_mm"]
    for i in range(kn):
        x = (i - (kn - 1) / 2.0) * pitch
        owner = "base" if i % 2 == 0 else "lid"
        comps[f"hinge_knuckle_{owner}_{i + 1}"] = _barrel(
            f"hinge_knuckle_{owner}_{i + 1}",
            HINGE["barrel_outer_radius_mm"], width,
            x_centre=x, y=axis_y, z=axis_z,
            role=f"{owner} hinge knuckle {i + 1} — alternating on one axis")
    comps["hinge_pin"] = _barrel(
        "hinge_pin", HINGE["pin_radius_mm"], span + 2.4,
        x_centre=0.0, y=axis_y, z=axis_z,
        role="steel hinge pin — one continuous axis through every knuckle")
    for k, sign in ((1, -1.0), (2, 1.0)):
        comps[f"hinge_pin_cap_{k}"] = _barrel(
            f"hinge_pin_cap_{k}", HINGE["pin_cap_radius_mm"],
            HINGE["pin_cap_length_mm"],
            x_centre=sign * (span / 2.0 + 1.2
                             + HINGE["pin_cap_length_mm"] / 2.0),
            y=axis_y, z=axis_z,
            role=f"hinge pin retention cap {k}")
    comps["hinge_reinforcement"] = _rect_prism(
        "hinge_reinforcement", span + 8.0,
        HINGE["reinforcement_depth_mm"], 2.2,
        centre=(0.0, axis_y + HINGE["reinforcement_depth_mm"] / 2 + 0.6),
        z0=dims["base_height_mm"] - 2.2, corner_r=0.6,
        role="local wall reinforcement at the hinge roots")

    # --- clasp -----------------------------------------------------------
    front_y = cd / 2.0 - c["case_wall_mm"] / 2.0
    comps["clasp_hook"] = _rect_prism(
        "clasp_hook", CLASP["hook_width_mm"], CLASP["hook_thickness_mm"],
        CLASP["hook_drop_mm"], centre=(0.0, front_y),
        z0=parting - CLASP["hook_drop_mm"], corner_r=0.4,
        role="lid clasp hook")
    comps["clasp_hook_lip"] = _rect_prism(
        "clasp_hook_lip", CLASP["hook_width_mm"], CLASP["hook_lip_mm"],
        CLASP["engagement_depth_mm"],
        centre=(0.0, front_y - CLASP["hook_lip_mm"] / 2
                - CLASP["hook_thickness_mm"] / 2),
        z0=parting - CLASP["hook_drop_mm"], corner_r=0.2,
        role="clasp engagement undercut")
    comps["clasp_detent"] = _rect_prism(
        "clasp_detent", CLASP["detent_width_mm"], CLASP["detent_depth_mm"],
        CLASP["detent_height_mm"],
        centre=(0.0, front_y - CLASP["detent_depth_mm"] / 2
                - CLASP["hook_thickness_mm"] - CLASP["release_clearance_mm"]),
        z0=dims["base_height_mm"] - CLASP["detent_height_mm"],
        corner_r=0.3, role="base clasp detent")
    comps["clasp_flex_zone"] = _rect_prism(
        "clasp_flex_zone", CLASP["flex_zone_width_mm"],
        CLASP["flex_zone_thickness_mm"], 3.0, centre=(0.0, front_y),
        z0=parting, corner_r=0.3, role="clasp flex region")
    comps["clasp_finger_notch"] = _rect_prism(
        "clasp_finger_notch", CLASP["finger_notch_width_mm"],
        CLASP["finger_notch_depth_mm"], 1.4,
        centre=(0.0, front_y + 0.4), z0=parting + 3.0, corner_r=0.5,
        role="opening affordance (finger notch)")
    comps["clasp_reinforcement"] = _rect_prism(
        "clasp_reinforcement", CLASP["detent_width_mm"] + 6.0, 2.4, 2.0,
        centre=(0.0, front_y - 1.8),
        z0=dims["base_height_mm"] - CLASP["detent_height_mm"] - 2.0,
        corner_r=0.4, role="local reinforcement behind the detent")

    dims["mirror_state"] = state
    return comps, dims


LID_GROUP = ("lid_outer_shell", "lid_structural_rim", "mirror",
             "mirror_adhesive_pad", "mirror_retaining_border",
             "clasp_hook", "clasp_hook_lip", "clasp_flex_zone",
             "clasp_finger_notch")


def lid_knuckles(components):
    return [n for n in components if n.startswith("hinge_knuckle_lid_")]


def compose_rect_state(components, dims, state, *,
                       open_angle_deg=OPEN_REVIEW_ANGLE_DEG):
    """Articulate the assembly about the real hinge axis."""
    if state not in STATES:
        raise RectAssemblyError(f"unknown state {state!r}")
    axis = (dims["hinge_axis_y_mm"], dims["hinge_axis_z_mm"])
    lid_names = set(LID_GROUP) | set(lid_knuckles(components))
    if state == "CLOSED":
        return dict(components)
    if state == "EXPLODED":
        out = {}
        for n, comp in components.items():
            dz = 26.0 if n in lid_names else (
                14.0 if n.startswith(("metal_pan_", "powder_")) else FT.traced_zero("palette_moulded_rect.py:compose_rect_state", "guard"))
            out[n] = pg.transform(comp, translate=(0.0, 0.0, dz)) if dz \
                else comp
        return out
    angle = 90.0 if state == "OPEN_90" else open_angle_deg
    if angle > HINGE["open_stop_deg"]:
        raise RectAssemblyError(
            f"{angle} deg exceeds the {HINGE['open_stop_deg']} deg open stop")
    # POSITIVE about the rear hinge axis lifts the lid up and back. The
    # negative sign P1A uses would swing it down through the base — which
    # renders as a closed palette from most angles and is why this needs a
    # test that looks at where the lid ends up, not just that it moved.
    return {n: (pg.transform(c, rotate_x_about=axis, angle_deg=abs(angle))
                if n in lid_names else c)
            for n, c in components.items()}


def rect_manifest(components, dims) -> dict:
    ids = {n: PI.mesh_geometry_identity(c)
           for n, c in sorted(components.items())}
    return {
        "record_type": SCHEMA, "revision": REVISION,
        "pilot": "PALT-P1B", "concept": "ES3083 OUTER GLOW",
        "boolean_free": True,
        "cutters": [],
        "geometry_authority": "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION",
        "blender_role": "VISUALIZATION_AND_RENDERING_ONLY",
        "component_count": len(components),
        "components": ids,
        "aggregate_identity": __import__("hashlib").sha256(
            repr(sorted(ids.items())).encode()).hexdigest()[:16],
        "case_mm": [dims["case_width_mm"], dims["case_depth_mm"],
                    dims["case_height_mm"]],
        "pan_count": sum(1 for n in components
                         if n.startswith("metal_pan_")),
        "pan_shape": "RECTANGULAR",
        "mirror_state": dims["mirror_state"],
        "provenance": dims["provenance"],
        "hinge": dict(HINGE), "clasp": dict(CLASP), "mirror": dict(MIRROR),
        "states": list(STATES),
        "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
        "PALT_P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
        "PALT_P1_OWNER_APPROVAL": "NOT_GRANTED",
    }
