"""PALT-M4B-A2 §7 — pan/pocket clearance policy and measurement.

Zero intersection is not sufficient. Three tiers are kept strictly apart:

``GEOMETRIC_CLEARANCE``
    the built meshes do not overlap. Establishable here.

``ENGINEERING_CLEARANCE``
    the geometric clearance survives a declared radial tolerance stack.
    Establishable here, as a PROVISIONAL DESIGN DEFAULT.

``MANUFACTURING_CONFIRMED_CLEARANCE``
    a supplier has confirmed the stack against real process capability.
    NOT establishable in this milestone, and nothing here may be called
    production-ready.

Measurement note: radial-at-elevation is the conservative metric and is
what gates the decision, but once the pan base is an arc running against a
concave floor fillet, radial-at-z can read clearance where the two arcs
actually foul. Both are reported; the minimum of the two governs.
"""
from __future__ import annotations

import math

import numpy as np

SCHEMA = "palette_clearance_policy/1.0"

GEOMETRIC = "GEOMETRIC_CLEARANCE"
ENGINEERING = "ENGINEERING_CLEARANCE"
MANUFACTURING = "MANUFACTURING_CONFIRMED_CLEARANCE"

CLEARANCE_TIER_STATUS = {
    GEOMETRIC: "ESTABLISHABLE_IN_M4B_A2",
    ENGINEERING: "ESTABLISHABLE_IN_M4B_A2_AS_PROVISIONAL_DESIGN_DEFAULT",
    MANUFACTURING: "NOT_ESTABLISHED",
}

# --- radial tolerance stack ------------------------------------------------
# Every contributor is a RADIAL (per-side) allowance in mm. All are
# DESIGN_DEFAULT. The pan-shell figure is deliberately NOT the 0.30 mm
# layout allowance from palt_p1 — that one is annotated "pressed-powder
# pans have WIDE tolerance (R10)" and is a powder/layout heuristic, not a
# drawn metal shell tolerance.
TOLERANCE_STACK = {
    "pan_shell_radial_tolerance_mm": (
        0.05, "drawn metal pan shell, provisional; NOT the 0.30 mm palt_p1 "
              "layout allowance. A real shell tolerance needs a supplier "
              "drawing and is NOT_ESTABLISHED."),
    "pocket_moulding_radial_tolerance_mm": (
        0.10, "half of ALLOWANCES.moulding_tolerance_mm (0.20 diametral)"),
    "coating_or_plating_radial_mm": (
        0.015, "decorative plating build, 10-20 um typical"),
    "assembly_placement_radial_mm": (
        0.10, "pick-and-place of the pan into an adhesive bed"),
    "adhesive_placement_radial_mm": (
        0.05, "adhesive squeeze-out beside the pan base"),
    "thermal_dimensional_radial_mm": (
        0.036, "differential expansion over a 40 K excursion: ABS at "
               "9.0e-5/K on a 13.3 mm radius against a metal pan at "
               "2.3e-5/K on 13.0 mm"),
}

STACK_METHODS = ("ROOT_SUM_SQUARE", "WORST_CASE_ARITHMETIC")
GOVERNING_METHOD = "ROOT_SUM_SQUARE"


def tolerance_stack() -> dict:
    values = {k: v[0] for k, v in TOLERANCE_STACK.items()}
    rss = math.sqrt(sum(v * v for v in values.values()))
    worst = sum(values.values())
    return {
        "record_type": "pan_pocket_radial_tolerance_stack/1.0",
        "contributors": {k: {"radial_mm": v[0], "basis": v[1],
                             "authority": "DESIGN_DEFAULT_NOT_"
                                          "MANUFACTURER_CONFIRMED"}
                         for k, v in TOLERANCE_STACK.items()},
        "root_sum_square_mm": round(rss, 6),
        "worst_case_mm": round(worst, 6),
        "governing_method": GOVERNING_METHOD,
        "engineering_minimum_radial_mm": round(rss, 6),
        "note": "RSS governs because the six contributors are independent "
                "and a worst-case stack on a decorative pocket would be "
                "unreasonably conservative. The worst-case figure is "
                "reported alongside so the owner can overrule.",
    }


def engineering_minimum_mm() -> float:
    return tolerance_stack()["engineering_minimum_radial_mm"]


# --- measurement -----------------------------------------------------------


def _densify(profile, per_segment=40):
    out = []
    for a, b in zip(profile, profile[1:]):
        for i in range(per_segment):
            t = i / per_segment
            out.append((a[0] + (b[0] - a[0]) * t,
                        a[1] + (b[1] - a[1]) * t))
    out.append(tuple(profile[-1]))
    return np.asarray(out, dtype=float)


def _radius_at(profile, z):
    """Radius of an (r, z) polyline at elevation z; None when off-range."""
    best = None
    for (r0, z0), (r1, z1) in zip(profile, profile[1:]):
        lo, hi = (z0, z1) if z0 <= z1 else (z1, z0)
        if lo - 1e-9 <= z <= hi + 1e-9:
            if abs(z1 - z0) < 1e-12:
                cand = max(r0, r1)
            else:
                t = (z - z0) / (z1 - z0)
                cand = r0 + (r1 - r0) * t
            best = cand if best is None else max(best, cand)
    return best


def measure(pocket_rings, pan_outer, *, z_lo, z_hi, samples=600) -> dict:
    """Clearance between one pocket profile and one pan outer profile.

    Positive means the pan is inside the cavity.
    """
    pocket = [tuple(p) for p in pocket_rings]
    pan = [tuple(p) for p in pan_outer]

    radial = []
    for z in np.linspace(z_lo, z_hi, samples):
        pr = _radius_at(pocket, float(z))
        qr = _radius_at(pan, float(z))
        if pr is None or qr is None:
            continue
        radial.append((pr - qr, float(z)))
    min_radial, at_z = min(radial, key=lambda t: t[0])

    # signed normal distance: nearest pocket point to each pan point,
    # negatived when the pan point sits outside the cavity
    P = _densify(pan)
    Q = _densify(pocket)
    d = np.hypot(P[:, 0][:, None] - Q[:, 0][None, :],
                 P[:, 1][:, None] - Q[:, 1][None, :])
    nearest = d.min(axis=1)
    signs = np.ones(len(P))
    for i, (r, z) in enumerate(P):
        pr = _radius_at(pocket, float(z))
        if pr is not None and r > pr + 1e-12:
            signs[i] = -1.0
    normal = float((nearest * signs).min())

    # vertical: pan base above the pocket floor
    pocket_floor_z = min(z for _, z in pocket)
    pan_base_z = min(z for _, z in pan)
    vertical = round(pan_base_z - pocket_floor_z, 9)

    return {"min_radial_clearance_mm": round(float(min_radial), 6),
            "min_radial_at_z_mm": round(at_z, 6),
            "min_normal_clearance_mm": round(normal, 6),
            "min_vertical_clearance_mm": vertical,
            "governing_clearance_mm": round(min(float(min_radial), normal),
                                            6),
            "metric_note": "governing = min(radial-at-elevation, signed "
                           "normal distance); radial alone can read "
                           "clearance where two arcs foul"}


def seating_assessment(pocket_flat_floor_radius_mm, pan_flat_base_radius_mm,
                       *, adhesive_gap_mm) -> dict:
    """Is the pan supported on its flat base, or only on a line?

    The pan's flat bottom face must land entirely inside the pocket's flat
    floor. When it overhangs onto the floor fillet the pan is carried on a
    ring contact — stable-looking in a render, unstable in reality, and
    explicitly prohibited by the owner's decision rule.
    """
    margin = round(pocket_flat_floor_radius_mm - pan_flat_base_radius_mm, 9)
    seats_flat = margin >= 0.0
    return {
        "pocket_flat_floor_radius_mm": round(pocket_flat_floor_radius_mm, 6),
        "pan_flat_base_radius_mm": round(pan_flat_base_radius_mm, 6),
        "flat_seating_margin_mm": margin,
        "seats_on_flat_base": seats_flat,
        "contact_mode": "FLAT_FACE_SEATING" if seats_flat
                        else "RING_CONTACT_ON_FLOOR_FILLET",
        "adhesive_gap_mm": adhesive_gap_mm,
        "stable": seats_flat,
        "note": "a positive margin means the whole flat base is carried by "
                "the flat pocket floor; negative means the base overhangs "
                "onto the fillet and the pan is carried on a ring",
    }


def classify(measurement, seating, *, minimum=None) -> dict:
    """Which clearance tiers this configuration establishes."""
    minimum = engineering_minimum_mm() if minimum is None else minimum
    governing = measurement["governing_clearance_mm"]
    geometric_ok = governing > 0.0
    engineering_ok = geometric_ok and governing >= minimum
    stack = tolerance_stack()
    return {
        "record_type": "clearance_classification/1.0",
        GEOMETRIC: {
            "established": bool(geometric_ok),
            "value_mm": governing,
            "criterion": "governing clearance > 0"},
        ENGINEERING: {
            "established": bool(engineering_ok and seating["stable"]),
            "value_mm": governing,
            "required_mm": minimum,
            "method": GOVERNING_METHOD,
            "worst_case_required_mm": stack["worst_case_mm"],
            "survives_worst_case": bool(governing >= stack["worst_case_mm"]),
            "criterion": "governing clearance >= the RSS tolerance stack "
                         "AND the pan seats on its flat base"},
        MANUFACTURING: {
            "established": False,
            "reason": "no supplier has confirmed the pan shell tolerance, "
                      "the moulding capability or the plating build",
            "status": "NOT_ESTABLISHED"},
        "production_ready": False,
        "authority": "PROVISIONAL_DESIGN_DEFAULT",
    }
