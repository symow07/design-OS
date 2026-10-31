"""PALT-M3 — mechanism strategy validators and the PALT-P1 matrix.

Fail-closed, non-mutating: a configuration that does not fit is reported
with codes, never resized to pass. The matrix explicitly does NOT pick the
smallest option.
"""
from __future__ import annotations

from apps.pipeline.services.palette_mechanism_contracts import (
    AUTHORITY_STATEMENT, MechanismStrategySpec)
from apps.pipeline.services.palette_stackup_engine import (
    ENGINE_VERSION, evaluate_configuration)
from apps.pipeline.services.palt_p1 import PROPOSED_OUTER, build_palt_p1

VALIDATOR_VERSION = "palette_mechanism_validators/1.0"

MECHANISM_MATERIAL_CONFLICT = "MECHANISM_MATERIAL_CONFLICT"
MECHANISM_ENVELOPE_UNDEFINED = "MECHANISM_ENVELOPE_UNDEFINED"
TARGET_WIDTH_EXCEEDED = "TARGET_WIDTH_EXCEEDED"
TARGET_DEPTH_EXCEEDED = "TARGET_DEPTH_EXCEEDED"
TARGET_HEIGHT_BELOW_ENGINEERING_MINIMUM = \
    "TARGET_HEIGHT_BELOW_ENGINEERING_MINIMUM"


def validate_strategy(spec, strategy: MechanismStrategySpec) -> dict:
    """Structural checks that do not depend on a target envelope."""
    findings = []
    conflict = strategy.material_conflict(spec.case.material)
    if conflict:
        findings.append({"code": MECHANISM_MATERIAL_CONFLICT,
                         "message": conflict})
    if strategy.retention_pocket_add_mm is None:
        findings.append({
            "code": MECHANISM_ENVELOPE_UNDEFINED,
            "message": f"{strategy.retention_strategy} has an undefined "
                       "pocket envelope"})
    for name, env in (("hinge", strategy.hinge_envelope),
                      ("clasp", strategy.clasp_envelope)):
        if env.is_unknown:
            findings.append({
                "code": MECHANISM_ENVELOPE_UNDEFINED,
                "message": f"{name} strategy envelope is undefined "
                           "(placeholder)"})
    return {"valid": not findings, "findings": findings,
            "validator_version": VALIDATOR_VERSION}


def palt_p1_strategy_matrix() -> dict:
    """The owner-mandated configuration comparison for PALT-P1.

    Group A tests the 116 x 92 TARGET_DESIGN_ENVELOPE under several
    mechanism strategies and both hinge edges — the comparison PALT-M2
    never made. Groups B and C test the near-square and compact options.
    """
    target_w, target_d, target_h = PROPOSED_OUTER
    rows = cols = 3

    def spec_for(gap=4.0, margin=5.0):
        return build_palt_p1(inter_pan_gap=gap, outer_margin=margin)

    configs = []

    # --- A: the 116 x 92 target envelope, several strategies -------------
    a_specs = spec_for()
    a_cases = [
        ("A1 reserved-band hinge + clasp, hinge on LONG edge (depth axis)",
         MechanismStrategySpec("INTERNAL_RESERVED_BAND_PIN_HINGE",
                               "INTERNAL_RESERVED_BAND_SNAP_CLASP",
                               "ADHESIVE_FIXED", "TOP_EDGE", "BOTTOM_EDGE",
                               "LANDSCAPE")),
        ("A2 wall-integrated hinge + clasp, hinge on LONG edge",
         MechanismStrategySpec("WALL_INTEGRATED_PIN_HINGE",
                               "WALL_INTEGRATED_SNAP_CLASP",
                               "ADHESIVE_FIXED", "TOP_EDGE", "BOTTOM_EDGE",
                               "LANDSCAPE")),
        ("A3 external barrel hinge + wall-integrated clasp, LONG edge",
         MechanismStrategySpec("EXTERNAL_BARREL_HINGE",
                               "WALL_INTEGRATED_SNAP_CLASP",
                               "ADHESIVE_FIXED", "TOP_EDGE", "BOTTOM_EDGE",
                               "LANDSCAPE")),
        ("A4 reserved-band hinge + clasp, hinge on SHORT edge (width axis)",
         MechanismStrategySpec("INTERNAL_RESERVED_BAND_PIN_HINGE",
                               "INTERNAL_RESERVED_BAND_SNAP_CLASP",
                               "ADHESIVE_FIXED", "LEFT_EDGE", "RIGHT_EDGE",
                               "LANDSCAPE")),
        ("A5 wall-integrated hinge + magnetic clasp, hinge on SHORT edge",
         MechanismStrategySpec("WALL_INTEGRATED_PIN_HINGE",
                               "MAGNETIC_CLOSURE", "ADHESIVE_FIXED",
                               "LEFT_EDGE", "RIGHT_EDGE", "LANDSCAPE")),
        ("A6 living hinge (PP) + friction closure, LONG edge — material "
         "conflict expected on an ABS case",
         MechanismStrategySpec("LIVING_HINGE", "FRICTION_CLOSURE",
                               "ADHESIVE_FIXED", "TOP_EDGE", "BOTTOM_EDGE",
                               "LANDSCAPE")),
    ]
    for label, strat in a_cases:
        configs.append(evaluate_configuration(
            a_specs, strat, rows, cols, label=label,
            target_width_mm=target_w, target_depth_mm=target_d,
            target_height_mm=target_h))

    # --- B: the near-square option, judged against ITS OWN envelope -----
    # (PALT-M2's analytical minimum, so "valid" here means "fits the
    # near-square envelope", never "fits 116 x 92")
    near_square = (101.8, 113.3, 15.0)
    for label, strat in [
        ("B1 near-square envelope, reserved-band mechanism",
         MechanismStrategySpec("INTERNAL_RESERVED_BAND_PIN_HINGE",
                               "INTERNAL_RESERVED_BAND_SNAP_CLASP",
                               "ADHESIVE_FIXED", "TOP_EDGE", "BOTTOM_EDGE",
                               "PORTRAIT")),
        ("B2 near-square envelope, wall-integrated mechanism",
         MechanismStrategySpec("WALL_INTEGRATED_PIN_HINGE",
                               "WALL_INTEGRATED_SNAP_CLASP",
                               "ADHESIVE_FIXED", "TOP_EDGE", "BOTTOM_EDGE",
                               "PORTRAIT")),
    ]:
        configs.append(evaluate_configuration(
            a_specs, strat, rows, cols, label=label,
            target_width_mm=near_square[0], target_depth_mm=near_square[1],
            target_height_mm=near_square[2]))
        configs[-1]["judged_against_envelope_mm"] = list(near_square)

    # --- C: compact optimised — realistic minimum gaps, mirror retained --
    c_spec = spec_for(gap=2.0, margin=3.0)
    for label, strat in [
        ("C1 compact optimised, wall-integrated hinge + clasp, SHORT edge",
         MechanismStrategySpec("WALL_INTEGRATED_PIN_HINGE",
                               "WALL_INTEGRATED_SNAP_CLASP",
                               "ADHESIVE_FIXED", "LEFT_EDGE", "RIGHT_EDGE",
                               "LANDSCAPE")),
        ("C2 compact optimised, reserved-band mechanism, SHORT edge",
         MechanismStrategySpec("INTERNAL_RESERVED_BAND_PIN_HINGE",
                               "INTERNAL_RESERVED_BAND_SNAP_CLASP",
                               "ADHESIVE_FIXED", "LEFT_EDGE", "RIGHT_EDGE",
                               "LANDSCAPE")),
    ]:
        configs.append(evaluate_configuration(
            c_spec, strat, rows, cols, label=label,
            target_width_mm=target_w, target_depth_mm=target_d,
            target_height_mm=target_h))

    for c in configs:
        c.setdefault("judged_against_envelope_mm", list(PROPOSED_OUTER))
    target_group = [c for c in configs
                    if c["judged_against_envelope_mm"] == list(PROPOSED_OUTER)]
    feasible = [c for c in target_group if c["valid"]]
    min_depth = min(c["minimum_depth_mm"] for c in configs
                    if c["minimum_depth_mm"])
    min_width = min(c["minimum_width_mm"] for c in configs
                    if c["minimum_width_mm"])
    return {
        "record_type": "palt_p1_strategy_matrix/1.0",
        "created_at": "2026-08-05",
        "engine_version": ENGINE_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "authority": AUTHORITY_STATEMENT,
        "pan_layout": "3 x 3 OF 26 MM ROUND PANS — RETAINED (owner: not "
                      "reduced to 3x2 to preserve a footprint)",
        "target_envelope_mm": list(PROPOSED_OUTER),
        "target_envelope_classification": [
            "TARGET_DESIGN_ENVELOPE",
            "tested here under MULTIPLE mechanism strategies and both hinge "
            "edges — PALT-M2 tested only the internal reserved band"],
        "configurations": configs,
        "feasible_within_target_envelope": [c["label"] for c in feasible],
        "target_envelope_result": {
            "any_tested_strategy_fits_116x92": bool(feasible),
            "smallest_depth_any_strategy_mm": round(min_depth, 2),
            "smallest_width_any_strategy_mm": round(min_width, 2),
            "shortfall_on_depth_mm": round(min_depth - PROPOSED_OUTER[1], 2),
            "classification": (
                "INFEASIBLE_UNDER_ALL_TESTED_MECHANISM_STRATEGIES — the "
                "depth axis is short by about "
                f"{round(min_depth - PROPOSED_OUTER[1], 1)} mm even in the "
                "most compact wall-integrated configuration"),
            "explicitly_not": "NOT proven infeasible under ALL POSSIBLE "
                              "strategies; six hinge/clasp combinations and "
                              "both hinge edges were tested, not every "
                              "conceivable mechanism",
        },
        "selection_rule": "the smallest configuration is NEVER chosen "
                          "automatically; see palt_p1_mechanism_decision.md",
        "manufacturing_readiness": "NOT_ESTABLISHED",
    }
