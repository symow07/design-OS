"""PALT-M4B-A — contract, assembly, validation and evidence manifests.

The contract below is written as EXPLICIT LITERALS with per-value
provenance. It is deliberately not derived from
``palette_moulded_geometry.resolve()``: that module is the one the owner
declared INCOMPLETE, and it carries a pocket diameter (26.8) that
contradicts the owner-accepted PALT-M2/M3 layout module (26.6). Deriving
the contract from it would silently reintroduce the divergence.

Authority: PALETTE_TRAY_GEOMETRY_AUTHORITY =
DETERMINISTIC_PYTHON_MESH_CONSTRUCTION. Blender is visualisation only and
no Boolean operation participates in any geometry or section here.
"""
from __future__ import annotations

import json
import os

import numpy as np

from apps.pipeline.services import palette_mesh_section as ms
from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services.palette_moulded_geometry import (
    metal_pan, powder_volume)
from apps.pipeline.services.palette_recessed_tray_geometry import (
    TOPOLOGY, build_recessed_palette_tray)

SCHEMA = "palt_m4b_a_geometry_contract/1.0"
MILESTONE = "PALT-M4B-A"

O = "OWNER_STATED_M4B_A_PRESERVED_VALUE"          # noqa: E741
C = "CALCULATED_FROM_OWNER_ACCEPTED_CONTRACT"
D = "DESIGN_DEFAULT_NOT_MANUFACTURER_CONFIRMED"

TRAY = {
    "tray_width_mm": (112.0, C, "PALT-M3 envelope 116.0 minus 2 x 2.0 mm "
                                "case wall"),
    "tray_depth_mm": (112.0, C, "PALT-M3 envelope 116.0 minus 2 x 2.0 mm "
                                "case wall"),
    "deck_z_mm": (7.15, O, "tray deck elevation"),
    "underside_z_mm": (1.5, C, "PALT-M3 base thickness"),
    "pocket_floor_z_mm": (2.50, O, "pocket floor elevation"),
    "pocket_sharp_wall_theoretical_diameter_at_deck_mm": (
        26.6, O,
        "M4B-A applied 26.6 as the sharp wall line at the deck plane, and "
        "is kept here unchanged so the M4B-A record reproduces exactly. "
        "PALT-M4B-A2 SUPERSEDES THIS READING: 26.6 is the pan maximum "
        "envelope / layout module and was never a cavity dimension — see "
        "palette_pocket_datums.conflict_record(). The corrected fit datum "
        "is POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM = 26.8. Note also "
        "that the visible mouth measures 27.76 mm because the 0.6 mm rim "
        "fillet bulges outward from the wall line."),
    "pitch_mm": (30.6, C, "26.6 module + 4.0 mm inter-pan gap"),
    "pocket_draft_deg": (2.0, O, "pocket draft"),
    "tray_draft_deg": (1.5, O, "tray draft"),
    "corner_radius_mm": (4.0, C, "PALT-M4 corner radius 6.0 minus the "
                                 "2.0 mm case wall"),
    "rim_fillet_mm": (0.6, D, "MOULDING.internal_fillet_mm applied to the "
                              "deck-to-pocket-wall transition"),
    "floor_fillet_mm": (0.6, D, "MOULDING.internal_fillet_mm applied to "
                                "the pocket-wall-to-floor transition — see "
                                "the declared interpretation finding"),
}

PAN = {
    "pan_outside_diameter_mm": (26.0, O, "pan nominal diameter"),
    "pan_depth_mm": (3.5, O, "pan depth"),
    "pan_seating_z_mm": (2.65, O, "pan seating elevation"),
    "pan_top_z_mm": (6.15, O, "pan top elevation"),
    "pan_recess_mm": (1.00, O, "pan recess below deck"),
    "adhesive_allowance_mm": (0.15, D, "PAN_SYSTEM adhesive allowance "
                                       "(2.65 - 2.50)"),
    "metal_pan_wall_mm": (0.25, D, "PAN_SYSTEM drawn-pan wall"),
    "metal_pan_floor_mm": (0.25, D, "PAN_SYSTEM drawn-pan floor"),
    "powder_crown_mm": (0.3, D, "PAN_SYSTEM pressed-powder crown"),
    "powder_to_lid_clearance_mm": (0.8, D, "PAN_SYSTEM requirement"),
    "lid_inner_z_mm": (8.55, C, "PALT-M3 base height — the lid seating "
                                "plane, used only as the section's "
                                "clearance reference"),
}

EXPECTED = {
    "pocket_count": 9,
    "pitch_mm": 30.6,
    "pocket_depth_mm": 4.65,
    "pocket_draft_deg": 2.0,
    "tray_draft_deg": 1.5,
    "pocket_floor_thickness_mm": 1.0,
}

SECTION_LAYERS = ("tray_deck", "pocket_wall", "pocket_floor", "metal_pan",
                  "powder_placeholder", "tray_underside", "pan_recess",
                  "powder_to_lid_clearance_reference")


def _values(table):
    return {k: v[0] for k, v in table.items()}


def contract() -> dict:
    """The full contract, values plus provenance."""
    return {
        "schema": SCHEMA, "milestone": MILESTONE,
        "tray_spec": _values(TRAY),
        "pan": _values(PAN),
        "expected": dict(EXPECTED),
        "provenance": {
            k: {"value": v[0], "authority": v[1], "basis": v[2]}
            for table in (TRAY, PAN) for k, v in table.items()},
        "topology": dict(TOPOLOGY),
        "authority": {
            "PALETTE_TRAY_GEOMETRY_AUTHORITY":
                "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION",
            "BLENDER_ROLE": "VISUALIZATION_AND_RENDERING_ONLY",
            "BLENDER_BOOLEAN_MODIFIERS":
                "NOT_AUTHORITY_FOR_CORE_TRAY_GEOMETRY",
            "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
            "PALT_P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
            "PALT_P1_OWNER_APPROVAL": "REJECTED_PENDING_M4B",
            "PALT_M5": "BLOCKED"},
        "section_layers_required": list(SECTION_LAYERS),
    }


def build_assembly() -> dict:
    """The tray plus its nine pans and nine powder placeholders."""
    spec = _values(TRAY)
    pan = _values(PAN)
    tray = build_recessed_palette_tray(spec)
    comps = {"recessed_palette_tray": tray}
    pan_r = pan["pan_outside_diameter_mm"] / 2.0
    for p in tray["pockets"]:
        i = p["row"] * 3 + p["col"] + 1
        cx, cy = p["centre_mm"]
        comps[f"metal_pan_{i}"] = metal_pan(
            f"metal_pan_{i}", pan_r, pan["pan_depth_mm"],
            pan["metal_pan_wall_mm"], pan["metal_pan_floor_mm"],
            centre=(cx, cy), z0=pan["pan_seating_z_mm"],
            role=f"provisional metal pan {i}")
        comps[f"powder_{i}"] = powder_volume(
            f"powder_{i}",
            pan_r - pan["metal_pan_wall_mm"] - 0.05,
            pan["pan_depth_mm"] - pan["metal_pan_floor_mm"] - 0.15,
            pan["powder_crown_mm"], centre=(cx, cy),
            z0=pan["pan_seating_z_mm"] + pan["metal_pan_floor_mm"],
            role=f"provisional powder volume {i}")
    return {"tray": tray, "components": comps,
            "component_count": len(comps)}


def centre_section(assembly, *, axis="y", at=0.0, cap=True) -> dict:
    """The centre section through the middle pan row."""
    return ms.section_assembly(assembly["components"], axis, at, cap=cap)


def _layers_exposed(section, tray, pan) -> dict:
    """Which of the owner's required layers the section actually reaches,
    proven from section coordinates rather than asserted."""
    tray_loop = section["components"]["recessed_palette_tray"]
    zs = set(ms.loop_elevations(tray_loop))
    deck = tray["elevations_mm"]["deck"]
    floor = tray["elevations_mm"]["pocket_floor"]
    under = tray["elevations_mm"]["underside"]
    wall_top = tray["pockets"][0]["wall_top_z_mm"]
    wall_bot = tray["pockets"][0]["wall_bottom_z_mm"]
    pan_names = [n for n in section["components"] if n.startswith("metal_pan")]
    pow_names = [n for n in section["components"] if n.startswith("powder_")]
    pan_zs = set()
    for n in pan_names:
        pan_zs |= set(ms.loop_elevations(section["components"][n]))
    powder_zs = set()
    for n in pow_names:
        powder_zs |= set(ms.loop_elevations(section["components"][n]))
    # the powder crown is measured FROM THE SECTION; the lid seating plane
    # is a contract reference because the lid is not modelled in M4B-A
    crown = max(powder_zs) if powder_zs else None
    return {
        "tray_deck": any(abs(z - deck) < 1e-6 for z in zs),
        "pocket_wall": any(abs(z - wall_top) < 1e-4 for z in zs)
        and any(abs(z - wall_bot) < 1e-4 for z in zs),
        "pocket_floor": any(abs(z - floor) < 1e-6 for z in zs),
        "metal_pan": len(pan_names) == 3,
        "powder_placeholder": len(pow_names) == 3,
        "tray_underside": any(abs(z - under) < 1e-6 for z in zs),
        "pan_recess": any(abs(z - pan["pan_top_z_mm"]) < 1e-6
                          for z in pan_zs)
        and any(abs(z - deck) < 1e-6 for z in zs),
        "powder_to_lid_clearance_reference":
            crown is not None
            and (pan["lid_inner_z_mm"] - crown
                 >= pan["powder_to_lid_clearance_mm"]),
    }


def validate(assembly, section=None) -> dict:
    """Every validator the owner listed, plus the declared-scope findings."""
    ct = contract()
    tray = assembly["tray"]
    reports = [
        mv.validate_mesh("recessed_palette_tray", tray),
        mv.validate_recessed_tray(tray, ct),
        mv.validate_pan_seating(tray, ct),
    ]
    for name in sorted(assembly["components"]):
        if name == "recessed_palette_tray":
            continue
        reports.append(mv.validate_mesh(name, assembly["components"][name],
                                        check_self_intersection=False))
    if section is not None:
        layers = _layers_exposed(section, tray, _values(PAN))
        reports.append(mv.validate_section(section, layers))
    merged = mv.merge_reports(*reports)
    merged["declared"] = declared_findings(tray)
    merged["findings"] = merged["findings"] + merged["declared"]
    merged["finding_count"] = len(merged["findings"])
    merged["declared_count"] = len(merged["declared"])
    return merged


def declared_findings(tray) -> list:
    """Scope boundaries and contract conflicts the owner must rule on.

    These are recorded as declared items rather than silent omissions —
    the owner rejected M4B partly on things discovered in the render
    rather than in the report.
    """
    pan = _values(PAN)
    pan_r = pan["pan_outside_diameter_mm"] / 2.0
    spec = _values(TRAY)
    max_fillet = mv.max_floor_fillet_for_pan(
        spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"] / 2.0, spec["deck_z_mm"],
        spec["pocket_floor_z_mm"], spec["pocket_draft_deg"], pan_r,
        pan["pan_seating_z_mm"])
    min_pocket = mv.min_pocket_diameter_for_pan(
        spec["floor_fillet_mm"], spec["deck_z_mm"], spec["pocket_floor_z_mm"],
        spec["pocket_draft_deg"], pan_r, pan["pan_seating_z_mm"])
    land = spec["pitch_mm"] - 2 * tray["pockets"][0]["opening_radius_mm"]
    # every clearance quoted below is MEASURED from a real build, never
    # asserted — a hand-written figure here would drift the moment a
    # fillet or a diameter moved
    grid = {}
    for fil in (0.0001, 0.6, 0.8):
        for pd in (26.6, 26.8):
            probe = dict(spec)
            probe["floor_fillet_mm"] = fil
            probe["pocket_sharp_wall_theoretical_diameter_at_deck_mm"] = pd
            built = build_recessed_palette_tray(probe)
            grid[(fil, pd)] = mv.validate_pan_seating(
                built, contract())["measured"]["min_radial_clearance_mm"]
    sharp = grid[(0.0001, spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"])]
    return [
        {"code": mv.CONTRACT_VALUE_DIVERGENCE, "severity": "DECLARED",
         "source": "contract",
         "message": (
             "pocket diameter: the owner-accepted PALT-M2/M3 layout module "
             "is 26.6 mm (26.0 pan + 2 x 0.30 tolerance) while "
             "palette_moulded_geometry.PAN_SYSTEM carries 26.8 mm "
             "(26.0 + 2 x 0.40 seating clearance). M4B-A uses 26.6 per the "
             "owner's explicit M4B-A instruction and the accepted contract; "
             "PAN_SYSTEM was NOT modified. Minimum radial pan clearance, "
             "measured at the pan base where draft makes the pocket "
             "narrowest: with a SHARP pocket corner "
             f"{grid[(0.0001, 26.6)]:+.4f} mm at 26.6 and "
             f"{grid[(0.0001, 26.8)]:+.4f} mm at 26.8; with the 0.6 mm "
             "moulded floor fillet this milestone actually builds, "
             f"{grid[(0.6, 26.6)]:+.4f} mm at 26.6 and "
             f"{grid[(0.6, 26.8)]:+.4f} mm at 26.8 — so the fillet, not "
             "the diameter, is what consumes the clearance. 26.6 also "
             "makes the moulded inter-pocket gap exactly the 4.0 mm the "
             "layout reserves; 26.8 would leave 3.8 mm."),
         "min_radial_clearance_mm": {
             "sharp_corner_pocket_26_6": round(grid[(0.0001, 26.6)], 4),
             "sharp_corner_pocket_26_8": round(grid[(0.0001, 26.8)], 4),
             "fillet_0_6_pocket_26_6": round(grid[(0.6, 26.6)], 4),
             "fillet_0_6_pocket_26_8": round(grid[(0.6, 26.8)], 4)},
         "owner_decision_required": True},
        {"code": mv.UNMODELLED_CONTRACT_FEATURE, "severity": "DECLARED",
         "source": "contract",
         "message": (
             "MOULDING.wall_to_floor_radius_mm (0.8) is NOT applied to the "
             "pocket. M4B-A interprets it as the base-cavity wall-to-floor "
             "radius and applies MOULDING.internal_fillet_mm (0.6) to both "
             "pocket transitions. Neither value seats the pan at 26.6: at "
             f"0.8 mm the clearance is {grid[(0.8, 26.6)]:+.4f} mm and at "
             f"0.6 mm it is {grid[(0.6, 26.6)]:+.4f} mm. This "
             "interpretation requires owner confirmation."),
         "clearance_at_fillet_0_8_mm": round(grid[(0.8, 26.6)], 4),
         "clearance_at_fillet_0_6_mm": round(grid[(0.6, 26.6)], 4),
         "owner_decision_required": True},
        {"code": mv.UNMODELLED_CONTRACT_FEATURE, "severity": "DECLARED",
         "source": "geometry",
         "message": (
             "structural rib interfaces, hinge reinforcement interface and "
             "clasp reinforcement interface are recorded as declared "
             "interface regions, not raised geometry. The tray is currently "
             "a solid moulded block between pockets, so ribs would sit "
             "inside solid material and carry no load. Raised interfaces "
             "belong with the hinge and clasp rebuild in M4B-B."),
         "interface_regions": interface_regions(tray)},
        {"code": mv.SECTION_THICKNESS_RISK, "severity": "DECLARED",
         "source": "moulding",
         "message": (
             f"nominal wall variation: the pocket floor is 1.0 mm while the "
             f"inter-pocket land is up to {land:.2f} mm wide and the tray "
             f"is {tray['elevations_mm']['deck'] - tray['elevations_mm']['underside']:.2f} mm "
             "thick as a solid block. That is a section variation above 5:1, "
             "which would sink and distort in ABS. Hollowing the underside "
             "to a uniform wall is proposed for M4B-B; it changes no "
             "elevation in this contract."),
         "owner_decision_required": True},
        {"code": mv.PAN_POCKET_INTERSECTION, "severity": "DECLARED",
         "source": "solved_envelope",
         "message": (
             "solved envelope for the pan interference. The conflict is "
             "between three contract values that were never checked "
             "together before: a 26.6 mm pocket, a 0.6 mm moulded floor "
             "fillet, and a 26.0 mm pan modelled with a SHARP bottom "
             "corner. Three independent resolutions, none applied: "
             f"(a) reduce the pocket floor fillet to <= {max_fillet} mm; "
             f"(b) keep 0.6 mm and open the pocket to >= {min_pocket} mm; "
             "(c) give the metal pan its true drawn base radius — a real "
             "drawn pan carries roughly 0.3-0.5 mm there, and a convex pan "
             "base radius nests inside the concave pocket fillet, "
             f"restoring the full {sharp:+.4f} mm sharp-corner clearance. "
             "(c) is the most likely correct answer because it corrects a "
             "known simplification in the PAN model rather than changing "
             "any tray dimension, but it is a pan-supplier fact and is "
             "NOT_MANUFACTURER_CONFIRMED. No dimension was altered to make "
             "validation pass."),
         "max_floor_fillet_mm": max_fillet,
         "min_pocket_diameter_mm": min_pocket,
         "sharp_corner_clearance_mm": round(sharp, 4),
         "measured_interference_mm": round(-grid[(0.6, 26.6)], 4),
         "owner_decision_required": True},
    ]


def interface_regions(tray) -> dict:
    """Declared (not modelled) reinforcement interface coordinates."""
    w = tray["spec"]["tray_width_mm"]
    d = tray["spec"]["tray_depth_mm"]
    pitch = tray["spec"]["pitch_mm"]
    return {
        "hinge_reinforcement_interface": {
            "edge": "TOP_EDGE", "y_mm": round(d / 2.0, 3),
            "band_mm": 1.2, "status": "DECLARED_NOT_MODELLED"},
        "clasp_reinforcement_interface": {
            "edge": "BOTTOM_EDGE", "y_mm": round(-d / 2.0, 3),
            "band_mm": 1.0, "status": "DECLARED_NOT_MODELLED"},
        "structural_rib_interfaces": {
            "x_mm": [round(-pitch / 2.0, 3), round(pitch / 2.0, 3)],
            "span_y_mm": [round(-d / 2.0 + 3.0, 3),
                          round(d / 2.0 - 3.0, 3)],
            "thickness_mm": 1.0, "status": "DECLARED_NOT_MODELLED"},
        "tray_footprint_mm": [w, d],
    }


# ---------------------------------------------------------------------------
# manifests


def topology_manifest(assembly) -> dict:
    tray = assembly["tray"]
    return {"record_type": "tray_topology_manifest/1.0",
            "milestone": MILESTONE,
            "mesh_identity": tray["mesh_identity"],
            "topology": tray["topology"],
            "shared_vertex_reuse_count": tray["shared_vertex_reuse_count"],
            "weld_count": tray["weld_count"],
            "weld_tolerance": tray["topology"]["weld_tolerance"],
            "authority": tray["authority"],
            "blender_role": tray["blender_role"],
            "boolean_free": tray["boolean_free"],
            "elevations_mm": tray["elevations_mm"],
            "draft": tray["draft"],
            "fillets_mm": tray["fillets_mm"],
            "pocket_profile_rings": tray["pocket_profile_rings"],
            "pockets": tray["pockets"],
            "interface_regions": interface_regions(tray),
            "component_count": assembly["component_count"]}


def mesh_diagnostics_manifest(report) -> dict:
    return {"record_type": "tray_mesh_diagnostics/1.0",
            "milestone": MILESTONE,
            "validator": mv.VALIDATOR_VERSION,
            "valid": report["valid"],
            "failure_count": report["failure_count"],
            "declared_count": report["declared_count"],
            "findings": report["findings"],
            "per_component": {
                name: rep.get("diagnostics")
                for name, rep in report["reports"].items()
                if rep.get("diagnostics")}}


def section_manifest(section, layers) -> dict:
    comps = {}
    for name, joined in section["components"].items():
        comps[name] = {
            "loop_count": joined["loop_count"],
            "coplanar_face_count": joined["coplanar_face_count"],
            "point_contact_count": joined["point_contact_count"],
            "loops": [{"role": lp["role"], "closed": lp["closed"],
                       "point_count": lp["point_count"],
                       "signed_area_mm2": round(lp["signed_area_mm2"], 6),
                       "cap_triangles": lp.get("cap", {}).get(
                           "triangle_count")}
                      for lp in joined["loops"]]}
    return {"record_type": "tray_section_manifest/1.0",
            "milestone": MILESTONE,
            "method": section["authority"],
            "boolean_free": section["boolean_free"],
            "axis": section["axis"], "at_mm": section["at"],
            "section_identity": section["section_identity"],
            "topology": section["topology"],
            "component_count": section["component_count"],
            "loop_count": section["loop_count"],
            "open_loop_count": section["open_loop_count"],
            "layers_exposed": layers,
            "components": comps}


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return _jsonable(obj.tolist())
    return obj


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(_jsonable(payload), fh, indent=2, sort_keys=False)
        fh.write("\n")
    return path
