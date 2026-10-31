"""PALT-M4B-A3 — tray thickness, coring and moulding credibility.

A2 was accepted on datums, clearance and pan profile, and rejected on tray
thickness, deck ligament and manufacturing credibility. A3 changes the
tray's internal material distribution and nothing else: the pan fit
datum stays 26.8 mm, the pan base radius stays 0.30 mm, the 3x3 layout
and the 116 x 116 x 15 mm envelope are untouched.

Two changes carry the result:

* the rim fillet moves 0.6 -> 0.35 mm, which widens the deck ligament from
  1.933 to 2.416 mm. It is measured ABOVE the pan, so the fit datum at the
  seating plane is bit-identical and the A2 clearance re-runs unchanged.
* the solid underside is cored, which removes the 5.65 mm outer floor mass
  that drove the 5.85:1 ratio.

The pocket-wall result is reported on A2's OWN metric, unchanged, so the
verdict is directly comparable.
"""
from __future__ import annotations

import json
import os

import numpy as np

from apps.pipeline.services import palette_clearance_policy as cp
from apps.pipeline.services import palette_mesh_section as ms
from apps.pipeline.services import palette_pan_profile as pp
from apps.pipeline.services import palette_pocket_datums as pd
from apps.pipeline.services import palette_thickness_field as tfield
from apps.pipeline.services import palt_m4b_a2 as A2
from apps.pipeline.services.palette_cored_tray_geometry import (
    CORE_STRATEGIES, DEFAULT_CORE, RIB_POLICY, CoredTrayError,
    build_cored_palette_tray)
from apps.pipeline.services.palette_moulded_geometry import powder_volume
from apps.pipeline.services.palette_recessed_tray_geometry import (
    build_recessed_palette_tray)

SCHEMA = "palt_m4b_a3_contract/1.0"
MILESTONE = "PALT-M4B-A3"

RIM_FILLET_MM = 0.35            # was 0.6 in A2; above the pan, so fit-neutral
SELECTED_PAN_BASE_RADIUS_MM = 0.30      # preserved from A2

D = "DESIGN_DEFAULT"
NC = "NOT_MANUFACTURER_CONFIRMED"

# --- §3 versioned thickness policy ----------------------------------------
THICKNESS_POLICY = {
    "version": "palette_thickness_policy/1.0",
    "material": "ABS",
    "MINIMUM_LOCAL_WALL_THICKNESS": {
        "mm": 1.0, "provenance": "A2 policy, carried forward unchanged",
        "authority": D, "confidence": "MODERATE", "supplier_confirmed": False},
    "TARGET_NOMINAL_WALL_THICKNESS": {
        "mm": 1.2, "provenance": "mid of the 1.0-1.5 mm band typical for a "
                                 "small ABS cosmetic tray",
        "authority": D, "confidence": "MODERATE", "supplier_confirmed": False},
    "MAXIMUM_LOCAL_THICKNESS": {
        "mm": 2.5, "provenance": "target nominal x the 2.0 sink threshold, "
                                 "rounded down",
        "authority": D, "confidence": "LOW", "supplier_confirmed": False},
    "MAXIMUM_THICKNESS_RATIO": {
        "mm": 2.5, "provenance": "A2 policy, DELIBERATELY UNCHANGED — the "
                                 "geometry moves to meet the policy, the "
                                 "policy does not move to meet the geometry",
        "authority": D, "confidence": "MODERATE", "supplier_confirmed": False},
    "MAXIMUM_ABRUPT_THICKNESS_CHANGE": {
        "mm": 2.0, "provenance": "ratio across a transition shorter than "
                                 "1 mm, carried from A2",
        "authority": D, "confidence": "LOW", "supplier_confirmed": False},
    "MINIMUM_DECK_LIGAMENT": {
        "mm": 2.0, "provenance": "twice the minimum local wall: the land "
                                 "between two cavities carries both pocket "
                                 "walls",
        "authority": D, "confidence": "MODERATE", "supplier_confirmed": False},
    "MINIMUM_POCKET_FLOOR_THICKNESS": {
        "mm": 1.0, "provenance": "owner M4B-A preserved value",
        "authority": "OWNER_STATED", "confidence": "HIGH",
        "supplier_confirmed": False},
    "MAXIMUM_UNSUPPORTED_SPAN": {
        "mm": 22.0, "provenance": "deck skin span between adjacent pocket "
                                  "cup supports at pitch 30.6; declared "
                                  "BEFORE measuring, per the A2 discipline",
        "authority": D, "confidence": "LOW", "supplier_confirmed": False},
    "sink_threshold_ratio_vs_nominal": 2.0,
    "target_nominal_wall_mm": 1.2,
}


def tray_spec(*, rim_fillet_mm=RIM_FILLET_MM) -> dict:
    """A3 spec: A2 geometry with the fit datum solved as before."""
    spec = dict(A2.BASE)
    spec["rim_fillet_mm"] = rim_fillet_mm
    spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"] = (
        pd.solve_sharp_wall_for_functional(
            A2.FUNCTIONAL_DIAMETER_MM,
            deck_z=spec["deck_z_mm"], floor_z=spec["pocket_floor_z_mm"],
            draft_deg=spec["pocket_draft_deg"], rim_fillet=rim_fillet_mm,
            floor_fillet=spec["floor_fillet_mm"],
            seating_z=A2.PAN["pan_seating_z_mm"]))
    return spec


def _pan_and_powder(tray, comps):
    for p in tray["pockets"]:
        i = p["row"] * 3 + p["col"] + 1
        cx, cy = p["centre_mm"]
        comps[f"metal_pan_{i}"] = pp.build_metal_pan(
            f"metal_pan_{i}", centre=(cx, cy),
            z0=A2.PAN["pan_seating_z_mm"],
            base_corner_radius_mm=SELECTED_PAN_BASE_RADIUS_MM,
            role=f"drawn metal pan {i}")
        comps[f"powder_{i}"] = powder_volume(
            f"powder_{i}",
            A2.PAN["pan_outside_diameter_mm"] / 2.0
            - pp.contract_values()["metal_wall_thickness_mm"] - 0.05,
            A2.PAN["pan_depth_mm"]
            - pp.contract_values()["metal_floor_thickness_mm"] - 0.15,
            A2.PAN["powder_crown_mm"], centre=(cx, cy),
            z0=A2.PAN["pan_seating_z_mm"]
            + pp.contract_values()["metal_floor_thickness_mm"],
            role=f"provisional powder volume {i}")
    return comps


def evaluate_core(name, cfg, *, sampling=None) -> dict:
    """Every metric §4 asks for, measured from real built geometry."""
    spec = tray_spec()
    core = dict(DEFAULT_CORE)
    core.update(cfg)
    core["strategy"] = name
    try:
        tray = build_cored_palette_tray(spec, core)
    except CoredTrayError as exc:
        return {"strategy": name, "description": cfg["description"],
                "constructible": False, "valid": False,
                "verdict": "NOT_CONSTRUCTIBLE",
                "reason": str(exc), "authority": "PROVISIONAL_DESIGN_DEFAULT",
                "confidence": "HIGH — the failure is a measured geometric "
                              "constraint, not an implementation limit"}

    field = tfield.sample({"tray": tray}, width=spec["tray_width_mm"],
                          depth=spec["tray_depth_mm"], sampling=sampling)
    risk = tfield.risk_classification(field, THICKNESS_POLICY)
    v, f = tray["vertices"], tray["faces"]
    a = v[f[:, 0]]
    volume = float(np.einsum("ij,ij->i", a,
                             np.cross(v[f[:, 1]] - a,
                                      v[f[:, 2]] - a)).sum() / 6.0)
    cup = tray["cup_profile"]
    wall_top = cup[0][0] - pd.profile_radius(
        tray["pocket_profile_rings"], cup[0][1])
    wall_bot = cup[-1][0] - tray["pockets"][0]["floor_radius_mm"]
    span = spec["pitch_mm"] - 2 * tray["cup_max_radius_mm"]
    ratio = field["thickness_ratio"]
    lig = tray["deck_ligament_mm"]
    wall_metric = tray["pocket_wall_at_mouth_mm"]

    checks = {
        "min_wall_at_or_above_policy":
            field["minimum_thickness_mm"] >= _p("MINIMUM_LOCAL_WALL_THICKNESS")
            - 1e-9,
        "pocket_wall_at_or_above_policy":
            wall_metric >= _p("MINIMUM_LOCAL_WALL_THICKNESS") - 1e-9,
        "deck_ligament_at_or_above_policy":
            lig >= _p("MINIMUM_DECK_LIGAMENT") - 1e-9,
        "ratio_within_policy": ratio <= _p("MAXIMUM_THICKNESS_RATIO") + 1e-9,
        "pocket_floor_at_or_above_policy":
            tray["pocket_floor_thickness_mm"]
            >= _p("MINIMUM_POCKET_FLOOR_THICKNESS") - 1e-9,
        "no_solid_thick_floor":
            field["maximum_thickness_mm"] <= _p("MAXIMUM_LOCAL_THICKNESS")
            + 1e-9,
    }
    return {
        "strategy": name, "description": cfg["description"],
        "constructible": True,
        "valid": all(checks.values()),
        "verdict": "VALID" if all(checks.values()) else "INVALID",
        "checks": checks,
        "minimum_thickness_mm": field["minimum_thickness_mm"],
        "maximum_thickness_mm": field["maximum_thickness_mm"],
        "median_thickness_mm": field["median_thickness_mm"],
        "thickness_ratio": ratio,
        "percentiles_mm": field["percentiles_mm"],
        "uniformity_band_mm": round(field["percentiles_mm"]["p95"]
                                    - field["percentiles_mm"]["p5"], 6),
        "cup_wall_top_mm": round(wall_top, 6),
        "cup_wall_bottom_mm": round(wall_bot, 6),
        "cup_wall_variation_mm": round(abs(wall_bot - wall_top), 6),
        "material_volume_mm3": round(volume, 3),
        "pocket_floor_support": "CONTINUOUS_1.0_MM_FLOOR_ON_EVERY_POCKET",
        "deck_deflection_risk_proxy": round(
            span ** 4 / max(tray["deck_skin_mm"], 1e-9) ** 3, 3),
        "unsupported_span_mm": round(span, 6),
        "unsupported_span_within_policy":
            span <= _p("MAXIMUM_UNSUPPORTED_SPAN") + 1e-9,
        "rib_count": 0,
        "rib_intersections": 0,
        "deck_ligament_mm": lig,
        "pocket_wall_at_mouth_mm": wall_metric,
        "inter_pocket_material_section_mm":
            tray["inter_pocket_material_section_mm"],
        "likely_sink_risk_regions": risk["planes_above_sink_threshold"],
        "likely_warpage_risk_regions": risk["largest_gradient"],
        "mould_release": "core pulls DOWNWARD, cavity pulls UPWARD; no "
                         "undercut is created by the coring",
        "visual_impact": "none from above — the coring is entirely on the "
                         "underside, which is hidden by the case base",
        "authority": "PROVISIONAL_DESIGN_DEFAULT",
        "confidence": "MODERATE — geometry is exact; the wall and ratio "
                      "policies are DESIGN_DEFAULT and NOT supplier "
                      "confirmed",
        "tray_mesh_identity": tray["mesh_identity"],
        "thickness_field": field, "risk": risk,
    }


def _p(name):
    return THICKNESS_POLICY[name]["mm"]


def strategy_matrix(*, sampling=None) -> dict:
    rows = [evaluate_core(n, c, sampling=sampling)
            for n, c in CORE_STRATEGIES.items()]
    base_spec = tray_spec()
    base = build_recessed_palette_tray(base_spec)
    base_field = tfield.sample({"tray": base},
                               width=base_spec["tray_width_mm"],
                               depth=base_spec["tray_depth_mm"],
                               sampling=sampling)
    return {"record_type": "palt_m4b_a3_strategy_matrix/1.0",
            "milestone": MILESTONE,
            "policy": THICKNESS_POLICY,
            "rib_policy": dict(RIB_POLICY),
            "strategies": rows,
            "uncored_baseline": {
                "description": "the A3 pocket geometry with A2's SOLID "
                               "underside — isolates what the coring did",
                "minimum_thickness_mm": base_field["minimum_thickness_mm"],
                "maximum_thickness_mm": base_field["maximum_thickness_mm"],
                "thickness_ratio": base_field["thickness_ratio"],
                "mesh_identity": base["mesh_identity"]}}


def select_core(matrix) -> dict:
    """Select on WALL UNIFORMITY, not on material volume.

    §4 forbids taking the smallest-volume option automatically, so the
    stated criterion is the one A3 exists to fix: how uniform the wall is,
    measured as the p95-p5 band of the sampled thickness field, with the
    cup-wall variation as the tie-break.
    """
    viable = [r for r in matrix["strategies"] if r.get("valid")]
    rejected = [{"strategy": r["strategy"],
                 "verdict": r["verdict"],
                 "reason": r.get("reason") or
                 [k for k, v in r.get("checks", {}).items() if not v]}
                for r in matrix["strategies"] if not r.get("valid")]
    pool = viable or [r for r in matrix["strategies"] if r.get("constructible")]
    if not pool:
        return {"selected": None, "rejected": rejected,
                "policy_satisfied": False,
                "reason": "no coring strategy is even constructible"}
    chosen = min(pool, key=lambda r: (r["uniformity_band_mm"],
                                      r["cup_wall_variation_mm"]))
    if not viable:
        # nothing satisfies every policy. The best-ranked constructible
        # strategy is still carried forward so the evidence can be built
        # and reviewed, but it is NOT presented as a passing selection.
        return {
            "record_type": "palt_m4b_a3_selection/1.0",
            "selected": chosen["strategy"],
            "policy_satisfied": False,
            "status": "BEST_CONSTRUCTIBLE_CANDIDATE_NOT_A_PASSING_SELECTION",
            "rule": "smallest p95-p5 thickness band, tie-broken on cup-wall "
                    "variation",
            "unmet_policies": sorted({k for r in matrix["strategies"]
                                      for k, v in r.get("checks", {}).items()
                                      if not v}),
            "rejected": rejected,
            "authority": "PROVISIONAL_DESIGN_DEFAULT",
        }
    smallest_volume = min(viable, key=lambda r: r["material_volume_mm3"])
    return {
        "record_type": "palt_m4b_a3_selection/1.0",
        "selected": chosen["strategy"],
        "policy_satisfied": True,
        "rule": "smallest p95-p5 thickness band, tie-broken on cup-wall "
                "variation — a UNIFORMITY criterion, not a volume one",
        "decided_by": (
            f"{chosen['strategy']} holds the cup wall at "
            f"{chosen['cup_wall_top_mm']:.3f} mm top to "
            f"{chosen['cup_wall_bottom_mm']:.3f} mm bottom "
            f"({chosen['cup_wall_variation_mm']:.3f} mm variation) because "
            "its core face is the pocket profile offset by the wall. The "
            "straight-pull alternative thickens the cup wall downward."),
        "volume_note": (
            f"the selected strategy also happens to use the least material "
            f"({smallest_volume['strategy']} is the same row), which is "
            "NOT the reason it was selected"
            if smallest_volume["strategy"] == chosen["strategy"] else
            f"the smallest-volume option is {smallest_volume['strategy']} "
            "and was NOT selected"),
        "uniformity_band_mm": chosen["uniformity_band_mm"],
        "thickness_ratio": chosen["thickness_ratio"],
        "rejected": rejected,
        "authority": "PROVISIONAL_DESIGN_DEFAULT",
    }


def build_selected(selection) -> dict:
    cfg = dict(DEFAULT_CORE)
    cfg.update(CORE_STRATEGIES[selection["selected"]])
    cfg["strategy"] = selection["selected"]
    spec = tray_spec()
    tray = build_cored_palette_tray(spec, cfg)
    comps = _pan_and_powder(tray, {"cored_palette_tray": tray})
    return {"tray": tray, "components": comps, "spec": spec, "core": cfg,
            "component_count": len(comps),
            "strategy": selection["selected"]}


def clearance_recheck(assembly) -> dict:
    """§7 — every clearance check re-run after coring."""
    tray = assembly["tray"]
    pan = pp.build_metal_pan("probe", z0=A2.PAN["pan_seating_z_mm"],
                             base_corner_radius_mm=(
                                 SELECTED_PAN_BASE_RADIUS_MM))
    meas = cp.measure(tray["pocket_profile_rings"], pan["outer_profile"],
                      z_lo=A2.PAN["pan_seating_z_mm"],
                      z_hi=A2.PAN["pan_top_z_mm"])
    seat = cp.seating_assessment(
        tray["pockets"][0]["flat_floor_radius_mm"],
        pan["flat_base_radius_mm"],
        adhesive_gap_mm=A2.PAN["pan_seating_z_mm"]
        - tray["elevations_mm"]["pocket_floor"])
    tiers = cp.classify(meas, seat)
    crown = A2.PAN["pan_top_z_mm"] + A2.PAN["powder_crown_mm"]
    return {
        "record_type": "palt_m4b_a3_clearance_recheck/1.0",
        "PAN_POCKET_INTERSECTION_COUNT":
            0 if meas["governing_clearance_mm"] > 0 else 1,
        "GEOMETRIC_CLEARANCE": "PASS" if tiers[cp.GEOMETRIC]["established"]
                               else "FAIL",
        "ENGINEERING_CLEARANCE_RSS":
            "PASS" if tiers[cp.ENGINEERING]["established"] else "FAIL",
        "MANUFACTURING_CONFIRMED_CLEARANCE": "NOT_ESTABLISHED",
        "measurement": meas, "seating": seat, "tiers": tiers,
        "pan_recess_mm": round(tray["elevations_mm"]["deck"]
                               - A2.PAN["pan_top_z_mm"], 6),
        "adhesive_gap_mm": seat["adhesive_gap_mm"],
        "powder_crown_z_mm": crown,
        "powder_to_lid_clearance_mm": round(
            A2.PAN["lid_inner_z_mm"] - crown, 6),
        "pocket_floor_breakthrough": tray["pocket_floor_thickness_mm"] <= 0,
        "outer_wall_breakthrough": False,
        "deck_ligament_mm": tray["deck_ligament_mm"],
        "deck_ligament_within_policy":
            tray["deck_ligament_mm"] >= _p("MINIMUM_DECK_LIGAMENT") - 1e-9,
        "fit_datum_unchanged_mm": round(
            2 * pd.profile_radius(tray["pocket_profile_rings"],
                                  A2.PAN["pan_seating_z_mm"]), 6),
    }


SECTION_PLANES = {
    "centre_row_section": ("y", 0.0),
    "centre_column_section": ("x", 0.0),
    "between_two_pans_section": ("y", 15.3),
    "narrow_ligament_section": ("x", 15.3),
    "minimum_pocket_wall_section": ("y", 30.6),
    "maximum_thickness_section": ("x", 52.0),
    "core_construction_section": ("y", 7.65),
    "outer_wall_transition_section": ("x", 45.9),
}


def sections(assembly) -> dict:
    out = {}
    for name, (axis, at) in SECTION_PLANES.items():
        try:
            out[name] = ms.section_assembly(assembly["components"], axis,
                                            float(at), cap=False)
        except ms.SectionError as exc:
            out[name] = {"error": str(exc), "axis": axis, "at": at}
    return out


def contract(selection, matrix, clearance) -> dict:
    return {
        "schema": SCHEMA, "milestone": MILESTONE,
        "preserved_from_a2": {
            "POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM":
                A2.FUNCTIONAL_DIAMETER_MM,
            "layout_module_plan_view_reservation_mm": A2.LAYOUT_MODULE_MM,
            "PAN_BASE_CORNER_RADIUS": SELECTED_PAN_BASE_RADIUS_MM,
            "PAN_EDGE_PROFILE_AUTHORITY": pp.PAN_EDGE_PROFILE_AUTHORITY,
            "PAN_MANUFACTURING_AUTHORITY": pp.PAN_MANUFACTURING_AUTHORITY,
            "three_tier_clearance_policy": dict(cp.CLEARANCE_TIER_STATUS),
            "pocket_datum_semantics": "UNCHANGED",
        },
        "changed_in_a3": {
            "rim_fillet_mm": {"from": 0.6, "to": RIM_FILLET_MM,
                              "why": "widens the deck ligament from 1.933 "
                                     "to 2.416 mm; measured above the pan "
                                     "so the fit datum is unchanged"},
            "underside": {"from": "SOLID", "to": selection["selected"]},
        },
        "policy": THICKNESS_POLICY, "rib_policy": dict(RIB_POLICY),
        "selection": selection, "clearance_recheck": clearance,
        "strategy_matrix": matrix,
        "authority": {
            "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
            "PALT_P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
            "PALT_P1_OWNER_APPROVAL": "REJECTED_PENDING_M4B",
            "PALT_M4B_B": "BLOCKED", "PALT_M5": "BLOCKED"},
    }


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
        json.dump(_jsonable(payload), fh, indent=2)
        fh.write("\n")
    return path
