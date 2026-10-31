"""PALT-M4B-A2 — pan/pocket fit and dimension authority.

The correction slice for the M4B-A rejection. Three strategies are
evaluated on equal terms and one is selected by a stated engineering
constraint — not by whichever preserves the existing mesh identity.

The headline finding of the slice: the M4B-A interference was NOT a
physical conflict. It came from feeding ``palt_p1``'s 26.6 mm LAYOUT
MODULE into the kernel's fit dimension. At the correct fit datum
(26.8 mm, the only value ever defined as a cavity) even a sharp-cornered
pan clears. So strategy B is a no-op at the corrected datum, and the real
question is not "does it fit" but "does it fit with engineering margin and
does it seat flat".
"""
from __future__ import annotations

import json
import os

import numpy as np

from apps.pipeline.services import palette_clearance_policy as cp
from apps.pipeline.services import palette_mesh_section as ms
from apps.pipeline.services import palette_pan_profile as pp
from apps.pipeline.services import palette_pocket_datums as pd
from apps.pipeline.services import palette_thickness_analysis as ta
from apps.pipeline.services.palette_moulded_geometry import powder_volume
from apps.pipeline.services.palette_recessed_tray_geometry import (
    _pocket_profile, build_recessed_palette_tray)

SCHEMA = "palt_m4b_a2_contract/1.0"
MILESTONE = "PALT-M4B-A2"

# --- fixed pilot geometry (unchanged from M4B-A) ---------------------------
BASE = {
    "tray_width_mm": 112.0,
    "tray_depth_mm": 112.0,
    "deck_z_mm": 7.15,
    "underside_z_mm": 1.5,
    "pocket_floor_z_mm": 2.50,
    "pitch_mm": 30.6,
    "pocket_draft_deg": 2.0,
    "tray_draft_deg": 1.5,
    "corner_radius_mm": 4.0,
    "rim_fillet_mm": 0.6,
    "floor_fillet_mm": 0.6,
}

PAN = {
    "pan_outside_diameter_mm": 26.0,
    "pan_depth_mm": 3.5,
    "pan_seating_z_mm": 2.65,
    "pan_top_z_mm": 6.15,
    "pan_recess_mm": 1.00,
    "adhesive_allowance_mm": 0.15,
    "powder_crown_mm": 0.3,
    "powder_to_lid_clearance_mm": 0.8,
    "lid_inner_z_mm": 8.55,
    "pan_layout_tolerance_mm": 0.30,
}

# the corrected fit datum — an explicit decision, see the conflict record
FUNCTIONAL_DIAMETER_MM = 26.8
LAYOUT_MODULE_MM = 26.6


def tray_spec(*, functional_diameter_mm=FUNCTIONAL_DIAMETER_MM,
              floor_fillet_mm=None) -> dict:
    """Kernel spec derived from the FIT datum, not from a layout module."""
    spec = dict(BASE)
    if floor_fillet_mm is not None:
        spec["floor_fillet_mm"] = floor_fillet_mm
    spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"] = (
        pd.solve_sharp_wall_for_functional(
            functional_diameter_mm,
            deck_z=spec["deck_z_mm"], floor_z=spec["pocket_floor_z_mm"],
            draft_deg=spec["pocket_draft_deg"],
            rim_fillet=spec["rim_fillet_mm"],
            floor_fillet=spec["floor_fillet_mm"],
            seating_z=PAN["pan_seating_z_mm"]))
    return spec


# ---------------------------------------------------------------------------
# §5 resolution matrix


STRATEGIES = {
    "A_FILLET_REDUCTION": {
        "description": "keep the current pocket functional diameter and a "
                       "sharp-cornered pan; cut the floor fillet to the "
                       "calculated non-interference maximum",
        "functional_diameter_mm": LAYOUT_MODULE_MM,
        "floor_fillet_mm": 0.5063,
        "base_corner_radius_mm": 0.0,
    },
    "B_POCKET_ENLARGEMENT": {
        "description": "keep the 0.6 mm floor fillet and a sharp-cornered "
                       "pan; enlarge the functional pocket diameter to the "
                       "calculated minimum",
        "functional_diameter_mm": 26.7084,
        "floor_fillet_mm": 0.6,
        "base_corner_radius_mm": 0.0,
    },
    "C_ROUNDED_PAN_BASE_0_30": {
        "description": "keep the intended pocket and moulded fillet; give "
                       "the pan a 0.30 mm drawn base radius",
        "functional_diameter_mm": FUNCTIONAL_DIAMETER_MM,
        "floor_fillet_mm": 0.6, "base_corner_radius_mm": 0.30,
    },
    "C_ROUNDED_PAN_BASE_0_40": {
        "description": "keep the intended pocket and moulded fillet; give "
                       "the pan a 0.40 mm drawn base radius",
        "functional_diameter_mm": FUNCTIONAL_DIAMETER_MM,
        "floor_fillet_mm": 0.6, "base_corner_radius_mm": 0.40,
    },
    "C_ROUNDED_PAN_BASE_0_50": {
        "description": "keep the intended pocket and moulded fillet; give "
                       "the pan a 0.50 mm drawn base radius",
        "functional_diameter_mm": FUNCTIONAL_DIAMETER_MM,
        "floor_fillet_mm": 0.6, "base_corner_radius_mm": 0.50,
    },
}


def evaluate_strategy(name, cfg) -> dict:
    """Every metric §5 asks for, measured from real built geometry.

    ``sharp_wall_diameter_at_deck_mm`` bypasses the functional-datum solve.
    It exists so the M4B-A configuration can be reproduced EXACTLY — M4B-A
    applied 26.6 as the sharp wall line, not as a functional diameter, and
    a control that quietly re-datumed it would not be a reproduction.
    """
    if "sharp_wall_diameter_at_deck_mm" in cfg:
        spec = dict(BASE)
        spec["floor_fillet_mm"] = cfg["floor_fillet_mm"]
        spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"] = (
            cfg["sharp_wall_diameter_at_deck_mm"])
    else:
        spec = tray_spec(
            functional_diameter_mm=cfg["functional_diameter_mm"],
            floor_fillet_mm=cfg["floor_fillet_mm"])
    tray = build_recessed_palette_tray(spec)
    pan_mesh = pp.build_metal_pan(
        "metal_pan_probe", z0=PAN["pan_seating_z_mm"],
        base_corner_radius_mm=cfg["base_corner_radius_mm"])
    rings = tray["pocket_profile_rings"]
    p = tray["pockets"][0]

    meas = cp.measure(rings, pan_mesh["outer_profile"],
                      z_lo=PAN["pan_seating_z_mm"],
                      z_hi=PAN["pan_top_z_mm"])
    seat = cp.seating_assessment(
        p["flat_floor_radius_mm"], pan_mesh["flat_base_radius_mm"],
        adhesive_gap_mm=PAN["pan_seating_z_mm"]
        - tray["elevations_mm"]["pocket_floor"])
    tiers = cp.classify(meas, seat)

    ligament = pd.deck_ligament_mm(tray)
    wall = pd.pocket_wall_thickness_mm(tray)
    thick = ta.analyse(tray)

    # max-material pan check: the layout allowance taken literally
    envelope_pan = pp.build_metal_pan(
        "envelope_probe", z0=PAN["pan_seating_z_mm"],
        base_corner_radius_mm=cfg["base_corner_radius_mm"],
        pan_outside_diameter_mm=PAN["pan_outside_diameter_mm"]
        + 2 * PAN["pan_layout_tolerance_mm"])
    env_meas = cp.measure(rings, envelope_pan["outer_profile"],
                          z_lo=PAN["pan_seating_z_mm"],
                          z_hi=PAN["pan_top_z_mm"])

    valid = (tiers[cp.GEOMETRIC]["established"] and seat["stable"])
    return {
        "strategy": name,
        "description": cfg["description"],
        "inputs": {"functional_diameter_mm": cfg["functional_diameter_mm"],
                   "floor_fillet_mm": cfg["floor_fillet_mm"],
                   "base_corner_radius_mm": cfg["base_corner_radius_mm"],
                   "sharp_wall_diameter_at_deck_mm":
                       spec["pocket_sharp_wall_theoretical_diameter_at_"
                            "deck_mm"]},
        "valid": bool(valid),
        "verdict": "VALID" if valid else "INVALID",
        "min_radial_clearance_mm": meas["min_radial_clearance_mm"],
        "min_normal_clearance_mm": meas["min_normal_clearance_mm"],
        "min_vertical_clearance_mm": meas["min_vertical_clearance_mm"],
        "governing_clearance_mm": meas["governing_clearance_mm"],
        "pan_seating_elevation_mm": PAN["pan_seating_z_mm"],
        "pan_recess_mm": round(tray["elevations_mm"]["deck"]
                               - PAN["pan_top_z_mm"], 6),
        "seating": seat,
        "clearance_tiers": tiers,
        "deck_ligament_mm": ligament,
        "pocket_wall_thickness_mm": wall,
        "layout_impact_3x3": {
            "pitch_mm": spec["pitch_mm"],
            "pitch_changed": False,
            "field_mm": round(3 * spec["pitch_mm"], 6),
            "outer_margin_mm": pd.outer_margin_mm(tray),
            "note": "no strategy moves the 3x3 pitch; the pan field and "
                    "the 116 mm external envelope are untouched"},
        "max_material_pan_check": {
            "envelope_diameter_mm": PAN["pan_outside_diameter_mm"]
            + 2 * PAN["pan_layout_tolerance_mm"],
            "min_radial_clearance_mm":
                env_meas["min_radial_clearance_mm"],
            "fits": bool(env_meas["governing_clearance_mm"] > 0),
            "note": "the 0.30 mm layout allowance taken literally as a pan "
                    "shell tolerance; see the datum conflict record — it is "
                    "a powder/layout heuristic, so this is a conservative "
                    "bound, not a verified requirement"},
        "visual_implications": _visual_note(cfg, ligament),
        "moulding_implications": {
            "thickness_ratio": thick["thickness_ratio"],
            "within_limit": thick["within_limit"],
            "sink_regions": thick["likely_sink_risk_regions"],
            "note": _moulding_note(cfg)},
        "authority": "PROVISIONAL_DESIGN_DEFAULT",
        "confidence": _confidence(cfg),
        "tray_mesh_identity": tray["mesh_identity"],
        "pan_mesh_identity": pan_mesh["mesh_identity"],
    }


def _visual_note(cfg, ligament):
    if cfg["base_corner_radius_mm"] > 0:
        return ("no visible change to the moulded tray: the pan's own base "
                "radius is hidden inside the pocket once seated")
    if cfg["floor_fillet_mm"] < 0.6:
        return ("a smaller internal fillet is not visible from above, but "
                "it sharpens the pocket's internal corner")
    return (f"a wider pocket narrows the deck ligament to {ligament:.3f} mm, "
            "which IS visible as a thinner land between pans")


def _moulding_note(cfg):
    if cfg["floor_fillet_mm"] < 0.6:
        return ("a smaller internal corner radius raises the local stress "
                "concentration and makes the cavity harder to polish; "
                "internal radii are usually increased, not reduced")
    if cfg["base_corner_radius_mm"] > 0:
        return ("no change to the moulded part at all — the correction is "
                "entirely in the pressed metal pan")
    return ("a wider cavity removes material from the deck land and moves "
            "the wall thickness the wrong way")


def _confidence(cfg):
    if cfg["base_corner_radius_mm"] > 0:
        return ("MODERATE — the geometry is exact, but a real drawn-pan "
                "base radius is NOT_MANUFACTURER_CONFIRMED")
    if cfg["floor_fillet_mm"] < 0.6:
        return "LOW — trades a moulding-quality feature for fit"
    return "MODERATE — dimensionally sound, weakens the deck land"


CONTROL = {
    "description": "CONTROL, not a strategy: the M4B-A sharp-cornered pan "
                   "placed in a pocket built at the CORRECTED fit datum. "
                   "Demonstrates whether the M4B-A interference was "
                   "physical or a datum error.",
    "functional_diameter_mm": FUNCTIONAL_DIAMETER_MM,
    "floor_fillet_mm": 0.6,
    "base_corner_radius_mm": 0.0,
}

M4B_A_REPRODUCTION = {
    "description": "CONTROL, not a strategy: the EXACT M4B-A "
                   "configuration — 26.6 fed in as the sharp wall line at "
                   "the deck, which is what M4B-A did, with a "
                   "sharp-cornered pan. Must reproduce the rejected "
                   "-0.0542 mm radial interference.",
    "sharp_wall_diameter_at_deck_mm": LAYOUT_MODULE_MM,
    "functional_diameter_mm": None,
    "floor_fillet_mm": 0.6,
    "base_corner_radius_mm": 0.0,
}


def resolution_matrix() -> dict:
    rows = [evaluate_strategy(n, c) for n, c in STRATEGIES.items()]
    control = evaluate_strategy("CONTROL_SHARP_PAN_AT_CORRECTED_DATUM",
                                CONTROL)
    repro = evaluate_strategy("CONTROL_M4B_A_REPRODUCTION",
                              M4B_A_REPRODUCTION)
    return {"record_type": "palt_m4b_a2_resolution_matrix/1.0",
            "milestone": MILESTONE,
            "engineering_minimum_radial_mm": cp.engineering_minimum_mm(),
            "tolerance_stack": cp.tolerance_stack(),
            "strategies": rows,
            "controls": [repro, control],
            "datum_error_demonstrated": {
                "m4b_a_reproduction_governing_clearance_mm":
                    repro["governing_clearance_mm"],
                "corrected_datum_governing_clearance_mm":
                    control["governing_clearance_mm"],
                "sharp_pan_clears_at_corrected_datum":
                    control["governing_clearance_mm"] > 0,
                "sharp_pan_meets_engineering_minimum":
                    control["clearance_tiers"][
                        cp.ENGINEERING]["established"],
                "conclusion": (
                    "the M4B-A interference was a DATUM ERROR, not a "
                    "physical conflict: the same sharp pan clears once the "
                    "pocket is built at the fit datum instead of the "
                    "layout module. It still does not reach the "
                    "engineering minimum, which is what the pan base "
                    "radius is for.")},
            "note": "strategy B is evaluated at its own stated minimum "
                    "(26.7084). At the corrected fit datum of 26.8 the "
                    "pocket already exceeds that, so 'enlargement' is a "
                    "no-op — see the controls."}


# ---------------------------------------------------------------------------
# §6 decision rule


def select_strategy(matrix) -> dict:
    """Smallest tested pan base radius that clears a documented engineering
    minimum AND seats on its flat base, with no external dimension change.

    The rule is applied, not narrated: candidates are filtered by the
    owner's six conditions and the smallest surviving radius wins.
    """
    minimum = matrix["engineering_minimum_radial_mm"]
    conditions = []
    candidates = []
    for row in matrix["strategies"]:
        if not row["strategy"].startswith("C_"):
            continue
        checks = {
            "positive_clearance": row["governing_clearance_mm"] > 0.0,
            "no_external_dimension_change":
                not row["layout_impact_3x3"]["pitch_changed"],
            "deck_not_weakened":
                row["deck_ligament_mm"] >= _reference_ligament(),
            "stable_seating": row["seating"]["stable"],
            "recess_preserved": abs(row["pan_recess_mm"] - 1.0) < 1e-9,
            "tagged_design_default":
                row["authority"] == "PROVISIONAL_DESIGN_DEFAULT",
            "meets_engineering_minimum":
                row["governing_clearance_mm"] >= minimum,
        }
        conditions.append({"strategy": row["strategy"], "checks": checks,
                           "eligible": all(checks.values())})
        if all(checks.values()):
            candidates.append(row)

    if not candidates:
        return {"selected": None,
                "reason": "no rounded-pan-base radius satisfies every "
                          "condition; the owner's preferred strategy is "
                          "unavailable and A or B must be ruled on",
                "conditions": conditions}

    chosen = min(candidates,
                 key=lambda r: r["inputs"]["base_corner_radius_mm"])
    rejected = [c["strategy"] for c in conditions if not c["eligible"]]
    control = evaluate_strategy("CONTROL_SHARP_PAN_AT_CORRECTED_DATUM",
                                CONTROL)
    ctrl_gov = control["governing_clearance_mm"]
    ctrl_eng = control["clearance_tiers"][cp.ENGINEERING]["established"]
    return {
        "record_type": "palt_m4b_a2_selection/1.0",
        "selected": chosen["strategy"],
        "base_corner_radius_mm": chosen["inputs"]["base_corner_radius_mm"],
        "functional_diameter_mm": chosen["inputs"]["functional_diameter_mm"],
        "governing_clearance_mm": chosen["governing_clearance_mm"],
        "engineering_minimum_radial_mm": minimum,
        "rule": "smallest tested base radius meeting every condition in "
                "the owner's decision rule",
        # derived from the measured rows, never narrated ahead of them
        "decided_by": (
            f"all tested radii {sorted(r['inputs']['base_corner_radius_mm'] for r in candidates)} "
            f"satisfy every condition, so the rule's own tie-break — the "
            f"SMALLEST tested radius — selects "
            f"{chosen['inputs']['base_corner_radius_mm']} mm at "
            f"{chosen['governing_clearance_mm']} mm governing clearance "
            f"against a {minimum} mm engineering minimum. A radius is "
            f"needed at all because the sharp-cornered control reaches only "
            f"{ctrl_gov} mm, which is "
            f"{'above' if ctrl_eng else 'BELOW'} that minimum."),
        "why_a_radius_is_required": (
            f"at the corrected fit datum a sharp-cornered pan does clear "
            f"({ctrl_gov} mm) and does seat flat, but by "
            f"{control['seating']['flat_seating_margin_mm']} mm — so it "
            f"establishes GEOMETRIC clearance and fails ENGINEERING "
            f"clearance. The base radius buys margin, it does not rescue a "
            f"collision."),
        "rejected_strategies": rejected,
        "not_decided_by": "mesh identity preservation, visual plausibility, "
                          "or ease of implementation",
        "conditions": conditions,
        "PAN_EDGE_PROFILE_AUTHORITY": pp.PAN_EDGE_PROFILE_AUTHORITY,
        "PAN_MANUFACTURING_AUTHORITY": pp.PAN_MANUFACTURING_AUTHORITY,
    }


def _reference_ligament():
    """Deck ligament of the corrected pilot — strategies must not go below."""
    tray = build_recessed_palette_tray(tray_spec())
    return pd.deck_ligament_mm(tray)


# ---------------------------------------------------------------------------
# selected pilot


def build_selected(selection) -> dict:
    """The corrected PALT-P1 pilot assembly."""
    cfg = STRATEGIES[selection["selected"]]
    spec = tray_spec(functional_diameter_mm=cfg["functional_diameter_mm"],
                     floor_fillet_mm=cfg["floor_fillet_mm"])
    tray = build_recessed_palette_tray(spec)
    comps = {"recessed_palette_tray": tray}
    for p in tray["pockets"]:
        i = p["row"] * 3 + p["col"] + 1
        cx, cy = p["centre_mm"]
        comps[f"metal_pan_{i}"] = pp.build_metal_pan(
            f"metal_pan_{i}", centre=(cx, cy), z0=PAN["pan_seating_z_mm"],
            base_corner_radius_mm=cfg["base_corner_radius_mm"],
            role=f"drawn metal pan {i} with a "
                 f"{cfg['base_corner_radius_mm']} mm base radius")
        comps[f"powder_{i}"] = powder_volume(
            f"powder_{i}",
            PAN["pan_outside_diameter_mm"] / 2.0
            - pp.contract_values()["metal_wall_thickness_mm"] - 0.05,
            PAN["pan_depth_mm"]
            - pp.contract_values()["metal_floor_thickness_mm"] - 0.15,
            PAN["powder_crown_mm"], centre=(cx, cy),
            z0=PAN["pan_seating_z_mm"]
            + pp.contract_values()["metal_floor_thickness_mm"],
            role=f"provisional powder volume {i}")
    return {"tray": tray, "components": comps,
            "component_count": len(comps), "strategy": selection["selected"],
            "spec": spec, "pan_config": cfg}


def centre_section(assembly, *, axis="y", at=0.0, cap=True):
    return ms.section_assembly(assembly["components"], axis, at, cap=cap)


def pocket_profile_for(functional_diameter_mm, floor_fillet_mm):
    spec = tray_spec(functional_diameter_mm=functional_diameter_mm,
                     floor_fillet_mm=floor_fillet_mm)
    return _pocket_profile(
        spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"] / 2.0,
        spec["deck_z_mm"], spec["pocket_floor_z_mm"],
        spec["pocket_draft_deg"], spec["rim_fillet_mm"],
        spec["floor_fillet_mm"], 5)


def contract(selection, matrix) -> dict:
    return {
        "schema": SCHEMA, "milestone": MILESTONE,
        "conflict_record": pd.conflict_record(),
        "pan_contract": pp.contract_provenance(),
        "tolerance_stack": cp.tolerance_stack(),
        "clearance_tier_status": dict(cp.CLEARANCE_TIER_STATUS),
        "fit_datum_decision": {
            "POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM":
                FUNCTIONAL_DIAMETER_MM,
            "rejected_for_this_role": LAYOUT_MODULE_MM,
            "reason": "26.6 is a plan-view layout module; it was never a "
                      "cavity dimension. M4B-A used it as one.",
            "authority": "DESIGN_DEFAULT_NOT_MANUFACTURER_CONFIRMED"},
        "selection": selection,
        "resolution_matrix": matrix,
        "authority": {
            "PALT_M4B_A2_SELECTED_STRATEGY_AUTHORITY":
                "PROVISIONAL_DESIGN_DEFAULT",
            "PAN_EDGE_PROFILE_AUTHORITY": pp.PAN_EDGE_PROFILE_AUTHORITY,
            "PAN_MANUFACTURING_AUTHORITY": pp.PAN_MANUFACTURING_AUTHORITY,
            "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
            "PALT_P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
            "PALT_P1_OWNER_APPROVAL": "REJECTED_PENDING_M4B",
            "PALT_M5": "BLOCKED"},
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
