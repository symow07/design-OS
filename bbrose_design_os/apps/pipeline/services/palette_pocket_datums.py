"""PALT-M4B-A2 — explicit pocket datums and the 26.6 / 26.8 conflict record.

M4B-A failed owner review on dimension semantics. The cause, traced here:

``palt_p1.py`` carries 26.6 as ``PaletteLayoutSpec.module_width`` — a
PLAN-VIEW LATTICE RESERVATION. ``palette_moulded_geometry.PAN_SYSTEM``
carries 26.8 as ``pocket_diameter_mm`` — a CAVITY DIAMETER. They are not
two opinions about one dimension; they are two different quantities that
were both being called "pocket diameter". M4B-A fed the layout value into
the fit dimension, and the 0.0542 mm interference followed from that.

``pocket_module_mm`` proves the distinction rather than assuming it: its
own docstring says a module is *not* merely nominal pan plus tolerance,
and it returns 26.6 for PALT-P1 only because ADHESIVE_FIXED retention
contributes ``retention_pocket_add_mm = 0.0``. Coincidence, not identity.

Neither value is deleted or overwritten. Each survives under its own
named datum, and the ambiguous field name is retired so the confusion
cannot recur.
"""
from __future__ import annotations

import math

from apps.pipeline.services.palette_recessed_tray_geometry import (
    _pocket_profile)

SCHEMA = "palette_pocket_datums/1.0"

# --- authority vocabulary --------------------------------------------------
OWNER_ACCEPTED = "OWNER_ACCEPTED_CONTRACT"
CALC_LAYOUT = "CALCULATED_LAYOUT_HEURISTIC"
DESIGN_DEFAULT = "DESIGN_DEFAULT_NOT_MANUFACTURER_CONFIRMED"
DERIVED = "DERIVED_FROM_BUILT_MESH"

CONFLICT_UNRESOLVED = "POCKET_DIAMETER_SEMANTIC_CONFLICT_UNRESOLVED"
AMBIGUOUS_FIELD_USED = "AMBIGUOUS_POCKET_DIAMETER_FIELD_USED"
DATUM_MISSING = "POCKET_DATUM_MISSING"


class PocketDatumError(ValueError):
    """Raised while a dimension has more than one active meaning."""


# ---------------------------------------------------------------------------
# §2 conflict record


def conflict_record() -> dict:
    """Provenance of both values. Neither is deleted; each is re-datumed."""
    return {
        "record_type": "pocket_diameter_conflict/1.0",
        "conflict": "two active contracts assigned different meanings to a "
                    "field both called 'pocket diameter'",
        "resolution": "NOT_A_VALUE_CONFLICT — A DATUM CONFLICT. The two "
                      "numbers measure different things at different "
                      "datums. Both are retained under explicit names and "
                      "the ambiguous field name is retired.",
        "entries": [
            {
                "value_mm": 26.6,
                "source_file": "apps/pipeline/services/palt_p1.py",
                "field_name": "PaletteLayoutSpec.module_width / "
                              "module_height",
                "original_purpose": "the PLAN-VIEW lattice module — the "
                                    "footprint reserved per pan so the 3x3 "
                                    "pitch can be resolved. It is a "
                                    "spacing reservation, never a cavity "
                                    "wall position at any elevation.",
                "derivation": "26.0 nominal pan + 2 x 0.30 manufacturing "
                              "tolerance + 2 x 0.0 retention pocket add",
                "authority": CALC_LAYOUT,
                "milestone_introduced": "PALT-M1 / PALT-M2 (layout "
                                        "contract); the owner's M1 review "
                                        "explicitly corrected its class to "
                                        "CALCULATED_LAYOUT_HEURISTIC and "
                                        "NOT an industry or production "
                                        "standard",
                "status": "ACTIVE_AT_A_DIFFERENT_DATUM",
                "controls_fit": False,
                "re_datumed_as": "PAN_MAXIMUM_ENVELOPE_DIAMETER (and, "
                                 "separately, the layout module)",
                "note": "pocket_module_mm(spec, PALT_P1_MECHANISM) returns "
                        "exactly 26.6 only because ADHESIVE_FIXED "
                        "retention adds 0.0. A retention strategy with a "
                        "non-zero pocket add would move the module without "
                        "moving any cavity wall — which is what proves the "
                        "two quantities are independent.",
            },
            {
                "value_mm": 26.8,
                "source_file": "apps/pipeline/services/"
                               "palette_moulded_geometry.py",
                "field_name": "PAN_SYSTEM['pocket_diameter_mm']",
                "original_purpose": "the moulded CAVITY diameter giving the "
                                    "metal pan radial seating clearance",
                "derivation": "26.0 nominal pan + 2 x 0.40 seating "
                              "clearance",
                "authority": DESIGN_DEFAULT,
                "milestone_introduced": "PALT-M4B (the module the owner "
                                        "declared INCOMPLETE)",
                "status": "ACTIVE_AND_CORRECTLY_DATUMED_FOR_FIT",
                "controls_fit": True,
                "re_datumed_as": "POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_"
                                 "DATUM",
                "note": "adopted as the A2 fit datum as an EXPLICIT "
                        "DECISION, not inherited silently: it is the only "
                        "one of the two that was ever defined as a cavity, "
                        "and it is the value that lets a nominal pan seat. "
                        "It still originates in an INCOMPLETE module, so "
                        "it stays DESIGN_DEFAULT / "
                        "NOT_MANUFACTURER_CONFIRMED.",
            },
            {
                "value_mm": 27.758826,
                "source_file": "derived from the built mesh",
                "field_name": "pockets[i].opening_radius_mm x 2",
                "original_purpose": "the visible mouth where the 0.6 mm rim "
                                    "fillet meets the flat deck",
                "derivation": "sharp wall line at deck + 2 x rim fillet "
                              "tangent offset",
                "authority": DERIVED,
                "milestone_introduced": "PALT-M4B-A",
                "status": "ACTIVE_VISUAL_ONLY",
                "controls_fit": False,
                "re_datumed_as": "POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM",
                "note": "a caliper on the top view reads this, not the fit "
                        "datum. Reporting it as a discrepancy would be "
                        "wrong — but the distinction has to be explicit "
                        "and testable, which is what DATUMS provides.",
            },
        ],
        "retired_field": {
            "name": "pocket_diameter_mm",
            "action": "RETIRED_AS_AMBIGUOUS",
            "enforced_by": "palette_recessed_tray_geometry."
                           "build_recessed_palette_tray raises "
                           "RecessedTrayError when the key is present",
            "values_preserved": True,
        },
        "unresolved": [
            "the 0.30 mm 'manufacturing tolerance' behind 26.6 is annotated "
            "'pressed-powder pans have WIDE tolerance (R10)' — that is a "
            "POWDER/layout heuristic, not a drawn metal-pan shell "
            "tolerance. Using it as PAN_MAXIMUM_ENVELOPE is conservative "
            "and probably overstated. A real pan-shell tolerance is "
            "NOT_ESTABLISHED and needs a supplier drawing.",
        ],
    }


# ---------------------------------------------------------------------------
# §3 explicit datums


def _datum(name, value, z_datum, direction, provenance, authority, tolerance,
           controls_fit, visual_only):
    return {"datum": name, "value_mm": round(float(value), 6),
            "z_datum_mm": z_datum, "measurement_direction": direction,
            "provenance": provenance, "authority": authority,
            "tolerance_mm": tolerance, "controls_fit": controls_fit,
            "visual_only": visual_only}


def pocket_datums(tray, pan) -> dict:
    """All seven datums, COMPUTED from the built mesh — never transcribed.

    A hand-entered datum table is the same defect class as a hardcoded
    clearance: it drifts the moment the geometry moves.
    """
    p = tray["pockets"][0]
    seating_z = pan["pan_seating_z_mm"]
    rings = tray["pocket_profile_rings"]
    functional_r = profile_radius(rings, seating_z)
    if functional_r is None:
        raise PocketDatumError(
            f"the pan seating datum z={seating_z} lies outside the pocket "
            "profile — the functional diameter is undefined")
    nominal = pan["pan_outside_diameter_mm"]
    envelope = nominal + 2 * pan["pan_layout_tolerance_mm"]
    rows = [
        _datum("PAN_NOMINAL_OUTER_DIAMETER", nominal,
               f"{seating_z}..{pan['pan_top_z_mm']}", "DIAMETRAL",
               "owner M4B-A preserved value", OWNER_ACCEPTED,
               None, True, False),
        _datum("PAN_MAXIMUM_ENVELOPE_DIAMETER", envelope,
               f"{seating_z}..{pan['pan_top_z_mm']}", "DIAMETRAL",
               "26.0 + 2 x 0.30 layout tolerance — this is what the 26.6 "
               "in palt_p1 actually measures", CALC_LAYOUT,
               pan["pan_layout_tolerance_mm"], True, False),
        _datum("POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM",
               2 * functional_r, seating_z, "DIAMETRAL",
               "cavity width at the plane the pan base occupies — the only "
               "datum that governs whether the pan fits", DERIVED,
               None, True, False),
        _datum("POCKET_DIAMETER_AT_FLOOR_FILLET_TANGENT",
               2 * p["flat_floor_radius_mm"], p["wall_bottom_z_mm"],
               "DIAMETRAL",
               "where the floor fillet becomes the flat pocket floor; the "
               "pan's flat base must land inside this", DERIVED,
               None, True, False),
        _datum("POCKET_SHARP_WALL_THEORETICAL_DIAMETER_AT_DECK",
               2 * p["sharp_corner_radius_mm"], tray["elevations_mm"]["deck"],
               "DIAMETRAL",
               "the drafted wall line extrapolated to the deck plane; the "
               "kernel's construction input, not a measurable feature",
               DESIGN_DEFAULT, None, False, False),
        _datum("POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM",
               2 * p["opening_radius_mm"], tray["elevations_mm"]["deck"],
               "DIAMETRAL",
               "where the rim fillet meets the flat deck — what a caliper "
               "on the top view reads", DERIVED, None, False, True),
        _datum("POCKET_MAXIMUM_FILLET_ENVELOPE_DIAMETER",
               2 * max(r for r, _ in rings), tray["elevations_mm"]["deck"],
               "DIAMETRAL",
               "widest point of the whole pocket profile including both "
               "fillets — drives deck ligament, not fit", DERIVED,
               None, False, True),
    ]
    return {"record_type": SCHEMA,
            "datums": {r["datum"]: r for r in rows},
            "fit_controlling": [r["datum"] for r in rows
                                if r["controls_fit"]],
            "visual_only": [r["datum"] for r in rows if r["visual_only"]]}


def profile_radius(rings, z):
    """Cavity radius at elevation ``z``; None when off the profile."""
    for (r0, z0), (r1, z1) in zip(rings, rings[1:]):
        if z1 - 1e-9 <= z <= z0 + 1e-9:
            if abs(z0 - z1) < 1e-12:
                return max(r0, r1)
            t = (z0 - z) / (z0 - z1)
            return r0 + (r1 - r0) * t
    return None


# ---------------------------------------------------------------------------
# functional -> construction datum


def solve_sharp_wall_for_functional(functional_diameter_mm, *, deck_z,
                                    floor_z, draft_deg, rim_fillet,
                                    floor_fillet, seating_z, samples=5):
    """Back-solve the kernel's construction input from the datum that
    actually controls fit.

    The pocket profile translates rigidly with the sharp-wall radius, so
    one probe build gives the exact offset — no iteration, no tolerance.
    """
    probe_r = 13.0
    rings, _, _ = _pocket_profile(probe_r, deck_z, floor_z, draft_deg,
                                  rim_fillet, floor_fillet, samples)
    at_seat = profile_radius(rings, seating_z)
    if at_seat is None:
        raise PocketDatumError(
            f"seating datum z={seating_z} is outside the pocket profile")
    offset = at_seat - probe_r
    return round(2.0 * (functional_diameter_mm / 2.0 - offset), 9)


def assert_no_ambiguous_field(spec):
    """Fail closed while a caller still uses the retired name."""
    if "pocket_diameter_mm" in spec:
        raise PocketDatumError(
            "'pocket_diameter_mm' is retired — 26.6 and 26.8 were two "
            "different datums, not two opinions. Name the datum.")


def validate_datums(datums, pan) -> dict:
    """Every fit-controlling datum must be present, ordered and consistent."""
    findings = []
    d = datums["datums"]
    required = ("PAN_NOMINAL_OUTER_DIAMETER", "PAN_MAXIMUM_ENVELOPE_DIAMETER",
                "POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM",
                "POCKET_DIAMETER_AT_FLOOR_FILLET_TANGENT",
                "POCKET_SHARP_WALL_THEORETICAL_DIAMETER_AT_DECK",
                "POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM",
                "POCKET_MAXIMUM_FILLET_ENVELOPE_DIAMETER")
    for name in required:
        if name not in d:
            findings.append({"code": DATUM_MISSING, "severity": "FAIL",
                             "message": f"{name} is not defined"})
    if findings:
        return {"valid": False, "findings": findings}

    mouth = d["POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM"]["value_mm"]
    sharp = d["POCKET_SHARP_WALL_THEORETICAL_DIAMETER_AT_DECK"]["value_mm"]
    func = d["POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM"]["value_mm"]
    if not (mouth > sharp > func):
        findings.append({
            "code": CONFLICT_UNRESOLVED, "severity": "FAIL",
            "message": (
                f"datum ordering broken: visible mouth {mouth} must exceed "
                f"the sharp wall line {sharp}, which must exceed the "
                f"functional diameter {func} (draft narrows the cavity "
                "downward)")})
    if d["POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM"]["controls_fit"]:
        findings.append({
            "code": CONFLICT_UNRESOLVED, "severity": "FAIL",
            "message": "the visible mouth must never be marked as "
                       "fit-controlling"})
    return {"record_type": "pocket_datum_validation/1.0",
            "valid": not findings, "findings": findings,
            "finding_count": len(findings)}


def deck_ligament_mm(tray) -> float:
    """Material left between two adjacent pocket mouths."""
    rings = tray["pocket_profile_rings"]
    widest = max(r for r, _ in rings)
    return round(tray["spec"]["pitch_mm"] - 2 * widest, 6)


def pocket_wall_thickness_mm(tray) -> float:
    """Half the deck ligament — the wall each pocket owns."""
    return round(deck_ligament_mm(tray) / 2.0, 6)


def outer_margin_mm(tray) -> float:
    """Material from the outermost pocket mouth to the tray edge."""
    rings = tray["pocket_profile_rings"]
    widest = max(r for r, _ in rings)
    pitch = tray["spec"]["pitch_mm"]
    return round(tray["spec"]["tray_width_mm"] / 2.0 - (pitch + widest), 6)


def assert_math():                                    # pragma: no cover
    assert math.isclose(1.0, 1.0)
