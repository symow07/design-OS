"""PALT-M4 — fail-closed 3D palette geometry validators.

Nineteen checks over the composed states. Nothing is repaired: a failing
palette is reported, never resized. The validators also guard the two
structural promises of the state engine — identical component identities
across states, and manifold meshes.
"""
from __future__ import annotations


from apps.pipeline.services import mesh_diagnostics as md
from apps.pipeline.services.palette_mechanism_geometry import (
    HINGE, LID_GROUP, compose_state)
from apps.pipeline.services.palette_stackup_engine import ALLOWANCES

VALIDATOR_VERSION = "palette_geometry_validators/1.0"

PAN_TO_PAN_COLLISION = "PAN_TO_PAN_COLLISION"
PAN_POCKET_COLLISION = "PAN_POCKET_COLLISION"
POCKET_BREAKTHROUGH = "POCKET_BREAKTHROUGH"
INSUFFICIENT_TRAY_FLOOR = "INSUFFICIENT_TRAY_FLOOR"
INSUFFICIENT_CASE_WALL = "INSUFFICIENT_CASE_WALL"
HINGE_TO_PAN_COLLISION = "HINGE_TO_PAN_COLLISION"
CLASP_TO_PAN_COLLISION = "CLASP_TO_PAN_COLLISION"
MIRROR_TO_HINGE_COLLISION = "MIRROR_TO_HINGE_COLLISION"
MIRROR_TO_CLASP_COLLISION = "MIRROR_TO_CLASP_COLLISION"
LID_TO_POWDER_COLLISION = "LID_TO_POWDER_COLLISION"
OPEN_STATE_SELF_INTERSECTION = "OPEN_STATE_SELF_INTERSECTION"
CLOSED_STATE_PARTING_GAP_FAILURE = "CLOSED_STATE_PARTING_GAP_FAILURE"
MISALIGNED_HINGE_AXIS = "MISALIGNED_HINGE_AXIS"
INVALID_PIN_ENGAGEMENT = "INVALID_PIN_ENGAGEMENT"
CLASP_HOOK_WITHOUT_DETENT = "CLASP_HOOK_WITHOUT_DETENT"
COMPONENT_OUTSIDE_ENVELOPE = "COMPONENT_OUTSIDE_ENVELOPE"
NEGATIVE_OR_ZERO_CLEARANCE = "NEGATIVE_OR_ZERO_CLEARANCE"
NON_MANIFOLD_MESH = "NON_MANIFOLD_MESH"
INCONSISTENT_STATE_IDENTITIES = "INCONSISTENT_STATE_IDENTITIES"

MIN_WALL_MM = {"ABS": 1.5, "PP": 1.0}


def _bounds(component):
    v = component["vertices"]
    return (v[:, 0].min(), v[:, 1].min(), v[:, 2].min(),
            v[:, 0].max(), v[:, 1].max(), v[:, 2].max())


def _aabb_overlap(a, b, tol=0.0):
    return not (a[3] <= b[0] + tol or b[3] <= a[0] + tol
                or a[4] <= b[1] + tol or b[4] <= a[1] + tol
                or a[5] <= b[2] + tol or b[5] <= a[2] + tol)


def validate_assembly(components, dims, *,
                      open_angle_deg=None, label="PALT-P1") -> dict:
    findings = []

    def add(code, message, **extra):
        findings.append({"code": code, "message": message, **extra})

    w, d, h = dims["envelope_mm"]
    wall = dims["case_wall_mm"]
    angle = open_angle_deg or dims["open_review_angle_deg"]

    # --- 1. mesh integrity -------------------------------------------------
    for name, c in components.items():
        diag = md.diagnose_mesh(c["vertices"], c["faces"])
        if diag["non_manifold_edges"] or "MESH_DEGENERATE_FACE" in \
                diag["codes"]:
            add(NON_MANIFOLD_MESH,
                f"{name}: {diag['codes']} non_manifold="
                f"{diag['non_manifold_edges']}", component=name)

    # --- 2. envelope containment (CLOSED) ---------------------------------
    for name, c in components.items():
        x0, y0, z0, x1, y1, z1 = _bounds(c)
        if (x0 < -w / 2 - 1e-3 or x1 > w / 2 + 1e-3
                or y0 < -d / 2 - 1e-3 or y1 > d / 2 + 1e-3
                or z0 < -1e-3 or z1 > h + 1e-3):
            add(COMPONENT_OUTSIDE_ENVELOPE,
                f"{name} exceeds the {w}x{d}x{h} envelope: "
                f"({round(x0,2)},{round(y0,2)},{round(z0,2)})-"
                f"({round(x1,2)},{round(y1,2)},{round(z1,2)})",
                component=name)

    # --- 3. walls and floors ----------------------------------------------
    material = dims["spec"].case.material.upper()
    min_wall = MIN_WALL_MM.get(material, 1.5)
    if wall < min_wall:
        add(INSUFFICIENT_CASE_WALL,
            f"case wall {wall} mm below the {material} minimum {min_wall}")
    if dims["tray_floor_mm"] <= 0:
        add(INSUFFICIENT_TRAY_FLOOR, "tray floor is not positive")
    elif dims["tray_floor_mm"] < 0.8:
        add(INSUFFICIENT_TRAY_FLOOR,
            f"tray floor {dims['tray_floor_mm']} mm is below a mouldable "
            "0.8 mm")

    # --- 4. pockets: breakthrough and pan fit ------------------------------
    pocket_floor_z = dims["base_thickness_mm"] + dims["tray_floor_mm"]
    if pocket_floor_z <= dims["base_thickness_mm"] + 1e-9:
        add(POCKET_BREAKTHROUGH,
            "pocket floor coincides with the outer base skin — the pocket "
            "would break through")
    pan_clear = (dims["pocket_diameter_mm"] - dims["pan_diameter_mm"]) / 2.0
    if pan_clear <= 0:
        add(PAN_POCKET_COLLISION,
            f"pan {dims['pan_diameter_mm']} mm does not fit pocket "
            f"{dims['pocket_diameter_mm']} mm")
    if pan_clear <= 0:
        add(NEGATIVE_OR_ZERO_CLEARANCE, "pan/pocket radial clearance <= 0")

    # --- 5. pan-to-pan ------------------------------------------------------
    pans = {n: c for n, c in components.items()
            if n.startswith("pan_")}
    names = sorted(pans)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if _aabb_overlap(_bounds(pans[names[i]]),
                             _bounds(pans[names[j]]), tol=1e-6):
                add(PAN_TO_PAN_COLLISION,
                    f"{names[i]} and {names[j]} overlap",
                    pans=[names[i], names[j]])

    # --- 6. mechanism vs pans ---------------------------------------------
    hinge_parts = [c for n, c in components.items()
                   if n.startswith("hinge_")]
    clasp_parts = [c for n, c in components.items()
                   if n.startswith("clasp_")]
    for pan_name, pan in pans.items():
        pb = _bounds(pan)
        for hp in hinge_parts:
            if _aabb_overlap(pb, _bounds(hp), tol=1e-6):
                add(HINGE_TO_PAN_COLLISION,
                    f"{hp['name']} collides with {pan_name}")
        for cp in clasp_parts:
            if _aabb_overlap(pb, _bounds(cp), tol=1e-6):
                add(CLASP_TO_PAN_COLLISION,
                    f"{cp['name']} collides with {pan_name}")

    # --- 7. mirror vs mechanism -------------------------------------------
    if "mirror" in components:
        mb = _bounds(components["mirror"])
        for hp in hinge_parts:
            if _aabb_overlap(mb, _bounds(hp), tol=1e-6):
                add(MIRROR_TO_HINGE_COLLISION,
                    f"mirror collides with {hp['name']}")
        for cp in clasp_parts:
            if _aabb_overlap(mb, _bounds(cp), tol=1e-6):
                add(MIRROR_TO_CLASP_COLLISION,
                    f"mirror collides with {cp['name']}")

    # --- 8. closed state: lid vs powder + parting gap ----------------------
    if pans and "mirror" in components:
        pan_top = max(_bounds(p)[5] for p in pans.values())
        powder_top = pan_top + ALLOWANCES["powder_crown_mm"]
        mirror_bottom = _bounds(components["mirror"])[2]
        clearance = mirror_bottom - powder_top
        if clearance <= 0:
            add(LID_TO_POWDER_COLLISION,
                f"mirror underside {round(mirror_bottom,2)} sits at or below "
                f"the powder crown {round(powder_top,2)} when closed",
                clearance_mm=round(clearance, 3))
    base_top = dims["base_height_mm"]
    lid_bottom = min((_bounds(components[n])[2] for n in LID_GROUP
                      if n in components and n != "clasp_hook"),
                     default=None)
    if lid_bottom is not None:
        gap = lid_bottom - base_top
        if gap < 0 or abs(gap - dims["parting_gap_mm"]) > 0.35:
            add(CLOSED_STATE_PARTING_GAP_FAILURE,
                f"closed parting gap {round(gap,3)} mm deviates from the "
                f"declared {dims['parting_gap_mm']} mm",
                measured_mm=round(gap, 3))

    # --- 9. hinge axis alignment and pin engagement ------------------------
    barrels = {n: c for n, c in components.items()
               if n.startswith("hinge_barrel_")}
    if barrels:
        centres = []
        for c in barrels.values():
            b = _bounds(c)
            centres.append(((b[1] + b[4]) / 2.0, (b[2] + b[5]) / 2.0))
        ys = [c[0] for c in centres]
        zs = [c[1] for c in centres]
        if max(ys) - min(ys) > 1e-3 or max(zs) - min(zs) > 1e-3:
            add(MISALIGNED_HINGE_AXIS,
                f"hinge barrels are not co-axial: y spread "
                f"{round(max(ys)-min(ys),4)}, z spread "
                f"{round(max(zs)-min(zs),4)}")
        if "hinge_pin" in components:
            pb = _bounds(components["hinge_pin"])
            pin_y, pin_z = (pb[1] + pb[4]) / 2.0, (pb[2] + pb[5]) / 2.0
            if abs(pin_y - ys[0]) > 1e-3 or abs(pin_z - zs[0]) > 1e-3:
                add(MISALIGNED_HINGE_AXIS,
                    "hinge pin axis does not coincide with the barrel axis")
            pin_span = pb[3] - pb[0]
            barrel_span = (max(_bounds(c)[3] for c in barrels.values())
                           - min(_bounds(c)[0] for c in barrels.values()))
            if pin_span + 1e-6 < barrel_span:
                add(INVALID_PIN_ENGAGEMENT,
                    f"pin length {round(pin_span,2)} mm does not span the "
                    f"barrel set {round(barrel_span,2)} mm")
            if HINGE["pin_radius_mm"] >= HINGE["barrel_radius_mm"]:
                add(INVALID_PIN_ENGAGEMENT,
                    "pin radius is not smaller than the barrel radius")
        else:
            add(INVALID_PIN_ENGAGEMENT, "hinge barrels exist with no pin")

    # --- 10. clasp hook needs a matching detent ----------------------------
    has_hook = "clasp_hook" in components
    has_detent = "clasp_detent" in components
    if has_hook != has_detent:
        add(CLASP_HOOK_WITHOUT_DETENT,
            f"clasp hook present={has_hook}, detent present={has_detent}")
    elif has_hook:
        hb, db = _bounds(components["clasp_hook"]), \
            _bounds(components["clasp_detent"])
        overlap_x = min(hb[3], db[3]) - max(hb[0], db[0])
        if overlap_x <= 0:
            add(CLASP_HOOK_WITHOUT_DETENT,
                "clasp hook and detent do not overlap in x — they could "
                "never engage")

    # --- 11. open state: self-intersection ---------------------------------
    open_state = compose_state(components, dims, "OPEN_REVIEW_ANGLE",
                               open_angle_deg=angle)
    lid_names = [n for n in LID_GROUP if n in open_state]
    base_names = [n for n in open_state
                  if n not in LID_GROUP and not n.startswith("hinge_")]
    # near the hinge the lid skirt and base wall are DESIGNED to be
    # adjacent, so a coarse AABB test there is a false positive. Test
    # actual vertex penetration outside a hinge-proximity band instead.
    hinge_band_y = dims["hinge_axis_y_mm"] - 4 * HINGE["barrel_radius_mm"]
    for ln in lid_names:
        lv = open_state[ln]["vertices"]
        lv = lv[lv[:, 1] < hinge_band_y]
        if not len(lv):
            continue
        for bn in base_names:
            b = _bounds(open_state[bn])
            inside = ((lv[:, 0] > b[0] + 0.05) & (lv[:, 0] < b[3] - 0.05)
                      & (lv[:, 1] > b[1] + 0.05) & (lv[:, 1] < b[4] - 0.05)
                      & (lv[:, 2] > b[2] + 0.05) & (lv[:, 2] < b[5] - 0.05))
            if inside.sum() > 0:
                add(OPEN_STATE_SELF_INTERSECTION,
                    f"open state: {ln} penetrates {bn} "
                    f"({int(inside.sum())} vertices inside)",
                    components=[ln, bn])

    # --- 12. state identity consistency ------------------------------------
    closed = compose_state(components, dims, "CLOSED")
    for n, c in open_state.items():
        if n in closed and closed[n]["mesh_identity"] != c["mesh_identity"]:
            add(INCONSISTENT_STATE_IDENTITIES,
                f"{n} identity differs between CLOSED and OPEN")

    return {
        "record_type": "palt_p1_open_closed_validation/1.0",
        "validator_version": VALIDATOR_VERSION,
        "label": label,
        "open_angle_deg": angle,
        "component_count": len(components),
        "valid": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "fail_closed": True,
        "never_auto_repairs": "no pan, wall, clearance or mechanism "
                              "envelope is shrunk to make geometry pass",
    }


def geometry_diagnostics(components) -> dict:
    per = {}
    for name, c in sorted(components.items()):
        diag = md.diagnose_mesh(c["vertices"], c["faces"])
        per[name] = {"mesh_identity": c["mesh_identity"],
                     "vertices": diag["vertex_count"],
                     "faces": diag["face_count"],
                     "components": diag["components"],
                     "non_manifold_edges": diag["non_manifold_edges"],
                     "signed_volume_mm3": diag["signed_volume_mm3"],
                     "codes": diag["codes"]}
    total_v = sum(len(c["vertices"]) for c in components.values())
    total_f = sum(len(c["faces"]) for c in components.values())
    return {
        "record_type": "palt_p1_geometry_diagnostics/1.0",
        "component_count": len(components),
        "total_vertices": total_v,
        "total_faces": total_f,
        "per_component": per,
        "note": "open surfaces (tray tiles, wall rings) are intentional "
                "shells, not solids — their diagnostic codes are reported "
                "verbatim rather than suppressed",
    }
