"""P1 real-bottle pilot — owner-authorized provisional best-effort geometry.

``p1_provisional_geometry/1.0`` is a PROVISIONAL geometry contract for the
P1 dropper serum bottle built from the 2026-08-04 owner intake. Authority
law (owner instruction, verbatim consequences):

* owner measurements are NEVER overwritten by online values;
* every non-owner value carries provenance, source/formula, confidence and
  an explicit authority class;
* an inferred value is never labelled measured or manufacturer-confirmed;
* the output is suitable for visual review and pipeline validation only —
  it must not be sent to a supplier as manufacturing geometry.

REVISIONS (each historical profile stays reproducible — owner review
decisions reference their exact mesh identities):

* V1 — first pilot. Owner visual review: visual fidelity FAIL, material
  realism FAIL (cosine shoulder "mechanical"; conical bulb cap).
* V2 — capsule bulb + smootherstep shoulder. Owner review: bulb
  PASS_WITH_MINOR_REVISION, shoulder FAIL ("too geometric/flat" — C2
  continuity alone is not visual correctness), material FAIL (opaque).
* V3 — CURRENT: authored clamped-cubic-spline shoulder from visually
  estimated control points; bulb with lower narrowing + fuller upper
  body; V2 collar/base retained; plus a VISUALIZATION_ONLY closed hollow
  glass solid (real wall thickness) for material renders only.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

from apps.pipeline.services.container_geometry import (
    CIRCULAR, build_geometry_record, build_mesh)

SCHEMA = "p1_provisional_geometry/1.0"
REVISION = "V4"
REVISIONS = ("V1", "V2", "V3", "V4")

AUTHORITY_CLASSES = (
    "OWNER_MEASURED", "OWNER_CONFIRMED", "ONLINE_EXACT_MATCH",
    "ONLINE_ANALOGOUS_REFERENCE", "CALCULATED_FROM_OWNER_DATA",
    "VISUAL_ESTIMATE_FROM_PHOTO", "GENERIC_RENDERING_DEFAULT",
    "VISUALIZATION_ONLY_GEOMETRY", "UNKNOWN")
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")

V1_MESH_IDENTITIES = {"body": "e7b0236deb66715e",
                      "collar": "7175cb33d5cd7375",
                      "bulb": "491a134981dd9506"}
V2_MESH_IDENTITIES = {"body": "b301a10969b4e943",
                      "collar": "0c0b5a6edcd33875",
                      "bulb": "edfac8571aea80b8"}
V3_MESH_IDENTITIES = {"body": "3d81bf24ac44bfea",
                      "collar": "0c0b5a6edcd33875",
                      "bulb": "931cb17e89f86322"}

# owner intake values (docs/visual_quality/rbv/owner_inputs/2026-08-04/) —
# verbatim; the coupling test pins these against the intake record
OWNER = {
    "total_assembled_height_mm": 114.3,
    "bottle_height_mm": 91.6,
    "straight_wall_end_mm": 66.0,          # A1 OWNER-RULED 2026-08-27
    "shoulder_landmark_69_mm": 69.0,       # A2 OWNER-RULED 2026-08-27
    "body_diameter_mm": 37.4,
    "base_diameter_mm": 37.35,
    "neck_height_mm": 18.11,               # A3 OWNER-CONFIRMED (a HEIGHT)
    "neck_outside_diameter_mm": 15.6,
    "opening_inside_diameter_mm": 10.3,
    "thread_outside_diameter_mm": 17.4,
    "thread_turns_visible": 3,
    "dropper_assembly_height_mm": 105.0,   # A4 OWNER-CONFIRMED definition
    "collar_outside_diameter_mm": 21.4,
    "collar_height_mm": 16.5,
    "bulb_max_diameter_mm": 10.57,
    "bulb_height_mm": 19.2,
    "pipette_length_mm": 88.74,
    "pipette_outside_diameter_mm": 6.9,
    "pipette_tip_to_base_mm": 9.16,
}

# owner-confirmed material facts (OWNER_CONFIRMED_MATERIAL_EVIDENCE) —
# appearance only; never geometry. V3 owner clarification: the bottle is
# TRANSPARENT orange-tinted glass with a matte/frosted EXTERIOR — the
# frost is a surface treatment and must never remove light transmission.
MATERIALS = {
    "bottle": {"material": "GLASS", "finish": "MATTE_FROSTED_EXTERIOR",
               "colour": "ORANGE_TINTED_AMBER",
               "transparency": "TRANSPARENT_NOT_OPAQUE"},
    "collar": {"material": "PLASTIC", "finish": "GLOSSY",
               "colour": "ORANGE"},
    "bulb": {"material": "PLASTIC", "finish": "GLOSSY", "colour": "ORANGE",
             "transparency": "OPAQUE"},
    "pipette": {"material": "CLEAR_GLASS", "finish": None, "colour": None},
    "authority": "OWNER_CONFIRMED_MATERIAL_EVIDENCE",
    "correction_2026_08_04": "bulb corrected CLEAR/TRANSPARENT -> "
                             "GLOSSY/ORANGE/OPAQUE by owner review of the "
                             "photographs (deviation D1 resolved)",
    "clarification_v3": "bottle = TRANSPARENT orange-tinted glass with "
                        "matte/frosted exterior; V2 opaque rendering "
                        "owner-REJECTED",
}

# owner-confirmed neck finish CLASS (OWNER_CONFIRMED) — raised out of the
# derived layer by owner ruling 2026-08-27 (A1 closeout, Q3): "the finish is
# GL18 / DIN 168 as the record holds; raise it from MEDIUM to confirmed on
# the thread-OD/pitch corroboration". A CLASS, not a measurement and not a
# supplier part: it does not license manufacturing procurement, and the
# evidence beneath it stays in derived_values()["neck_finish_corroboration"].
NECK_FINISH = {
    "classification": "GL18 / DIN 18 (DIN 168 knuckle thread)",
    "authority": "OWNER_CONFIRMED",
    "confirmed_on": "2026-08-27",
    "confirmed_by": "owner ruling, A1 closeout (Q3)",
    "confirmed_against": "thread-OD and pitch corroboration — owner thread "
                         "OD 17.4 vs GL18 17.50–18.00, owner neck OD 15.6 "
                         "vs GL18 bolt-minor 15.48–15.98, DIN 168 pitch "
                         "3.00 vs ~3.0 mm measured from the captures",
    "prior_state": "ONLINE_ANALOGOUS_REFERENCE / MEDIUM",
    "scope_limit": "CLASS ONLY — NOT an exact-product or supplier match; "
                   "confers no manufacturing authority",
    "thread_pitch_note": "the owner ruled on the FINISH CLASS, not on the "
                         "thread_pitch field; that field remains owner-"
                         "UNKNOWN and the 3.0 mm value stays "
                         "ONLINE_ANALOGOUS_REFERENCE",
    "record": "docs/visual_quality/rbv/owner_inputs/2026-08-27/"
              "a1_closeout.json",
}

# provisional non-owner inputs
BOTTOM_GLASS_THICKNESS_MM = 3.0     # GENERIC default (2–4 mm typical)
BASE_BOTTOM_RADIUS_MM = 2.5         # GENERIC: soft external bottom round
BASE_SETTLE_MM = 6.0                # weighted-glass taper zone above it
COLLAR_EDGE_RADIUS_MM = 0.8         # GENERIC: subtle collar edge rounding
SHOULDER_FULLNESS_EXPONENT = 1.35   # V2 parameter (owner-rejected profile)
V1_BASE_EDGE_BLEND_MM = 1.2         # V1 parameter (owner-rejected profile)
V1_BULB_DOME_FRACTION = 0.275       # V1 parameter (owner-rejected profile)

# visualization-only glass construction (V3 material renders ONLY — never
# manufacturing geometry, never a measured internal dimension)
GLASS_WALL_BODY_MM = 1.8            # VISUALIZATION_ONLY default
GLASS_WALL_NECK_MM = round(
    (OWNER["neck_outside_diameter_mm"]
     - OWNER["opening_inside_diameter_mm"]) / 2.0, 3)   # 2.65 CALCULATED

# V4: the real bottle is FILLED with orange serum (IMG_3120/3121) — the
# even warm body colour and the lighter empty neck come from the contents,
# not from the glass alone. Modelled as a VISUALIZATION_ONLY liquid volume.
LIQUID_FILL_FRACTION = 0.86        # VISUAL_ESTIMATE of the fill line
LIQUID_SURFACE_DROP_MM = 0.6       # slight meniscus dip at the surface

# ---------------------------------------------------------------------------
# V3 authored shoulder profile — visually estimated control points
# (VISUAL_ESTIMATE_FROM_OWNER_PHOTO; every point LOW/MEDIUM confidence;
# NOT_MANUFACTURING_AUTHORITATIVE). z from base; r radial.

SHOULDER_CONTROL_POINTS_V3 = [
    # (z_mm, r_mm, confidence)
    (66.00, 18.700, "MEDIUM"),   # owner A1 landmark — wall departure
    (67.60, 18.520, "LOW"),      # gradual departure from the straight wall
    (69.00, 17.900, "LOW"),      # owner A2 landmark region — full shoulder
    (70.40, 16.550, "LOW"),
    (71.60, 14.300, "LOW"),
    (72.70, 11.200, "LOW"),
    (73.10, 9.450, "LOW"),       # entry of the neck fillet
    (73.49, 7.800, "MEDIUM"),    # calculated neck base = 91.6 - 18.11
]

# V3 bulb profile — rounded dome retained (V2 PASS), lower narrowing +
# fuller upper body added per owner minor revision (z from bulb bottom)
# V4 owner-strict revision (V3 REJECTED: shoulder "inflated then
# pinched"; bulb "narrow egg"): narrowing departs EARLIER after the wall,
# curvature distributed progressively, soft neck-root blend; bulb keeps
# nearly vertical sides with only slight collar-entry narrowing
SHOULDER_CONTROL_POINTS_V4 = [
    (66.00, 18.700, "MEDIUM"),
    (67.00, 18.420, "LOW"),      # narrowing already visible at 67
    (68.00, 17.750, "LOW"),
    (69.00, 16.800, "LOW"),      # owner A2 landmark region
    (70.20, 15.100, "LOW"),
    (71.40, 12.900, "LOW"),
    (72.60, 10.000, "LOW"),
    (73.10, 8.650, "LOW"),       # gentle neck-root blend (no pinch)
    (73.49, 7.800, "MEDIUM"),
]

BULB_CONTROL_POINTS_V4 = [
    (0.00, 5.000, "LOW"),        # only SLIGHT narrowing at the collar
    (1.20, 5.200, "LOW"),
    (2.60, 5.285, "MEDIUM"),     # near-vertical sides ...
    (13.00, 5.285, "MEDIUM"),    # ... through most of the height
    (14.80, 5.100, "LOW"),
    (16.40, 4.550, "LOW"),
    (17.80, 3.550, "LOW"),
    (18.80, 2.050, "LOW"),
    (19.20, 0.600, "LOW"),       # rounded dome, no point
]

# collar fine vertical ribbing — visible in IMG_3120 (photo-supported);
# subtle inward ripple, crest diameter stays exactly at the owner 21.4
COLLAR_RIB_COUNT = 60
COLLAR_RIB_DEPTH_MM = 0.12       # VISUAL_ESTIMATE, LOW — never exaggerated

BULB_CONTROL_POINTS_V3 = [
    (0.00, 4.600, "LOW"),        # narrowed entry into the collar
    (0.90, 4.980, "LOW"),        # small natural fillet
    (2.50, 5.180, "LOW"),
    (5.50, 5.285, "MEDIUM"),     # owner max diameter 10.57 (held)
    (8.50, 5.285, "MEDIUM"),
    (11.00, 5.160, "LOW"),       # slightly fuller upper body
    (13.50, 4.750, "LOW"),
    (15.60, 4.050, "LOW"),
    (17.30, 3.050, "LOW"),
    (18.50, 1.850, "LOW"),
    (19.20, 0.500, "LOW"),       # rounded apex cap ring (no nipple)
]


def _clamped_cubic_spline(xs, ys, s0=None, sn=None):
    """C2 cubic spline through (xs, ys). ``s0``/``sn`` clamp the end
    slopes; None = natural end (zero second derivative). Returns f(x)."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    n = len(xs) - 1
    h = np.diff(xs)
    A = np.zeros((n + 1, n + 1))
    b = np.zeros(n + 1)
    if s0 is None:
        A[0, 0] = 1.0
    else:
        A[0, 0], A[0, 1] = 2 * h[0], h[0]
        b[0] = 6 * ((ys[1] - ys[0]) / h[0] - s0)
    if sn is None:
        A[n, n] = 1.0
    else:
        A[n, n - 1], A[n, n] = h[-1], 2 * h[-1]
        b[n] = 6 * (sn - (ys[n] - ys[n - 1]) / h[-1])
    for i in range(1, n):
        A[i, i - 1] = h[i - 1]
        A[i, i] = 2 * (h[i - 1] + h[i])
        A[i, i + 1] = h[i]
        b[i] = 6 * ((ys[i + 1] - ys[i]) / h[i]
                    - (ys[i] - ys[i - 1]) / h[i - 1])
    M = np.linalg.solve(A, b)

    def f(x):
        x = float(x)
        i = int(np.clip(np.searchsorted(xs, x) - 1, 0, n - 1))
        t = x - xs[i]
        hi = h[i]
        return (M[i] * (xs[i + 1] - x) ** 3 / (6 * hi)
                + M[i + 1] * t ** 3 / (6 * hi)
                + (ys[i] / hi - M[i] * hi / 6) * (xs[i + 1] - x)
                + (ys[i + 1] / hi - M[i + 1] * hi / 6) * t)
    return f


_V3_SHOULDER = _clamped_cubic_spline(
    [p[0] for p in SHOULDER_CONTROL_POINTS_V3],
    [p[1] for p in SHOULDER_CONTROL_POINTS_V3], s0=0.0, sn=0.0)
_V3_BULB = _clamped_cubic_spline(
    [p[0] for p in BULB_CONTROL_POINTS_V3],
    [p[1] for p in BULB_CONTROL_POINTS_V3], s0=0.9, sn=None)
_V4_SHOULDER = _clamped_cubic_spline(
    [p[0] for p in SHOULDER_CONTROL_POINTS_V4],
    [p[1] for p in SHOULDER_CONTROL_POINTS_V4], s0=0.0, sn=0.0)
_V4_BULB = _clamped_cubic_spline(
    [p[0] for p in BULB_CONTROL_POINTS_V4],
    [p[1] for p in BULB_CONTROL_POINTS_V4], s0=0.7, sn=None)


def _f(value, authority, provenance, *, confidence=None, source_url=None,
       formula=None, unit="mm"):
    if authority not in AUTHORITY_CLASSES:
        raise ValueError(f"unknown authority class {authority!r}")
    if authority not in ("OWNER_MEASURED", "OWNER_CONFIRMED", "UNKNOWN") \
            and confidence not in CONFIDENCES:
        raise ValueError(f"non-owner value requires confidence: {provenance}")
    rec = {"value": value, "unit": unit, "authority": authority,
           "provenance": provenance}
    if confidence:
        rec["confidence"] = confidence
    if source_url:
        rec["source_url"] = source_url
    if formula:
        rec["formula"] = formula
    return rec


def shoulder_radius(z: float, revision: str = REVISION) -> float:
    """Shoulder radial profile per revision (V1/V2 preserved so their
    review decisions stay reproducible)."""
    o = OWNER
    r_body = o["body_diameter_mm"] / 2.0
    r_neck = o["neck_outside_diameter_mm"] / 2.0
    z0 = o["straight_wall_end_mm"]
    z1 = o["bottle_height_mm"] - o["neck_height_mm"]
    if z <= z0:
        return r_body
    if z >= z1:
        return r_neck
    if revision == "V1":                       # owner-rejected (mechanical)
        t = (z - z0) / (z1 - z0)
        return r_body - (r_body - r_neck) * (1 - math.cos(math.pi * t)) / 2
    if revision == "V2":                       # owner-rejected (too flat)
        t = (z - z0) / (z1 - z0)
        s = 6 * t ** 5 - 15 * t ** 4 + 10 * t ** 3
        return r_body - (r_body - r_neck) * s ** SHOULDER_FULLNESS_EXPONENT
    if revision == "V3":                       # owner-rejected (inflated)
        return float(_V3_SHOULDER(z))
    return float(_V4_SHOULDER(z))              # V4 authored spline


def bulb_radius(z_local: float, revision: str = REVISION) -> float:
    """Bulb radial profile per revision; ``z_local`` from bulb bottom."""
    o = OWNER
    h = o["bulb_height_mm"]
    r = o["bulb_max_diameter_mm"] / 2.0
    z_local = min(max(z_local, 0.0), h)
    if revision == "V1":                       # owner-rejected (conical)
        dome_h = h * V1_BULB_DOME_FRACTION
        if z_local <= h - dome_h:
            return r
        t = (z_local - (h - dome_h)) / dome_h
        return max(r * math.cos(t * math.pi / 2), 0.55)
    if revision == "V2":                       # capsule (minor-revision)
        dome_h = r
        if z_local <= h - dome_h:
            return r
        d = z_local - (h - dome_h)
        return max(math.sqrt(max(r * r - d * d, 0.0)), 0.45)
    if revision == "V3":                       # owner-rejected (egg)
        return float(min(_V3_BULB(z_local), r))
    return float(min(_V4_BULB(z_local), r))    # V4 (max dia held exactly)


def derived_values() -> dict:
    """Every calculated dimension with formula + confidence."""
    o = OWNER
    neck_base = round(o["bottle_height_mm"] - o["neck_height_mm"], 2)
    collar_top = round(o["total_assembled_height_mm"] - o["bulb_height_mm"], 2)
    collar_bottom = round(collar_top - o["collar_height_mm"], 2)
    collar_above = round(collar_top - o["bottle_height_mm"], 2)
    engagement = round(o["bottle_height_mm"] - collar_bottom, 2)
    pipette_top = round(o["pipette_tip_to_base_mm"]
                        + o["pipette_length_mm"], 2)
    tip_clearance = round(o["pipette_tip_to_base_mm"]
                          - BOTTOM_GLASS_THICKNESS_MM, 2)
    return {
        "neck_base_z_mm": _f(neck_base, "CALCULATED_FROM_OWNER_DATA",
                             "neck starts where the bottle height minus neck "
                             "height ends", confidence="HIGH",
                             formula="91.6 - 18.11 = 73.49"),
        "collar_top_z_mm": _f(collar_top, "CALCULATED_FROM_OWNER_DATA",
                              "bulb sits fully proud of the collar (intake: "
                              "visible height = removed height)",
                              confidence="HIGH",
                              formula="114.3 - 19.2 = 95.1"),
        "collar_bottom_z_mm": _f(collar_bottom, "CALCULATED_FROM_OWNER_DATA",
                                 "collar top minus collar height",
                                 confidence="HIGH",
                                 formula="95.1 - 16.5 = 78.6"),
        "collar_above_glass_mm": _f(collar_above,
                                    "CALCULATED_FROM_OWNER_DATA",
                                    "collar standing proud of the glass mouth",
                                    confidence="HIGH",
                                    formula="95.1 - 91.6 = 3.5"),
        "collar_neck_engagement_mm": _f(engagement,
                                        "CALCULATED_FROM_OWNER_DATA",
                                        "neck length covered by the collar",
                                        confidence="HIGH",
                                        formula="91.6 - 78.6 = 13.0"),
        "pipette_top_z_mm": _f(pipette_top, "CALCULATED_FROM_OWNER_DATA",
                               "assembled pipette top position",
                               confidence="HIGH",
                               formula="9.16 + 88.74 = 97.9"),
        "bottom_glass_thickness_mm": _f(
            BOTTOM_GLASS_THICKNESS_MM, "GENERIC_RENDERING_DEFAULT",
            "owner value UNKNOWN; typical moulded 50 ml glass base 2–4 mm; "
            "used for clearance math + visualization-only inner floor",
            confidence="LOW"),
        "pipette_tip_interior_clearance_mm": _f(
            tip_clearance, "CALCULATED_FROM_OWNER_DATA",
            "tip height above the PROVISIONAL interior floor",
            confidence="MEDIUM", formula="9.16 - 3.0 = 6.16"),
        # The CLASSIFICATION itself was raised to OWNER_CONFIRMED by owner
        # ruling 2026-08-27 and now lives in NECK_FINISH (owner layer). This
        # entry is retained as the derived CORROBORATION that the owner
        # confirmed on — it must keep a non-owner authority, because the
        # derived layer may never carry owner authority.
        "neck_finish_corroboration": _f(
            "GL18 / DIN 18 (DIN 168 knuckle thread)",
            "ONLINE_ANALOGOUS_REFERENCE",
            "SUPERSEDED AS AUTHORITY by NECK_FINISH (OWNER_CONFIRMED, "
            "2026-08-27); retained as the evidence beneath that ruling. "
            "Owner thread OD 17.4 (±0.2) vs GL18 external thread "
            "17.50–18.00; owner neck OD 15.6 vs GL18 bolt-minor "
            "15.48–15.98; DIN 168 pitch 3.00 vs ~3.0 mm measured from the "
            "2026-08-27 captures (DERIVED_INDICATIVE); 3 visible turns × "
            "3 mm ≈ 9 mm thread band fits the 18.11 mm neck HEIGHT. "
            "Dimensional corroboration only — NOT an exact-product match.",
            confidence="MEDIUM", unit=None,
            source_url="https://www.gewinde-normen.de/en/"
                       "knuckle-thread-din-168.html"),
        "thread_pitch_mm": _f(
            3.0, "ONLINE_ANALOGOUS_REFERENCE",
            "DIN 168 GL18 pitch — analogous standard value; owner value "
            "remains UNKNOWN and is not overwritten",
            confidence="MEDIUM",
            source_url="https://www.gewinde-normen.de/en/"
                       "knuckle-thread-din-168.html"),
        "analogous_bottle_check": _f(
            "50 ml GL18 dropper bottle ≈ H 92 × Ø 37, pipette 87",
            "ONLINE_ANALOGOUS_REFERENCE",
            "commodity 50 ml GL18/DIN18 serum bottles corroborate the owner "
            "set (owner: 91.6 × 37.4, pipette 88.74) — sanity check only, "
            "no owner value replaced", confidence="MEDIUM", unit=None,
            source_url="https://www.cwynnejones.com/gl18-clear-bottles/"
                       "699-50ml-clear-bottle-90.html"),
        "shoulder_curve_model": _f(
            "V3 authored clamped cubic spline through visually estimated "
            "control points (C2; convex; wall + neck tangents clamped "
            "horizontal)", "VISUAL_ESTIMATE_FROM_PHOTO",
            "V1 cosine and V2 smootherstep owner-REJECTED — mathematical "
            "smoothness alone is not visual correctness; V3 control points "
            "authored from IMG_3120/3121. A1/A2 landmark DEFINITIONS were "
            "owner-resolved 2026-08-27 (66 and 69 are two distinct caliper "
            "landmarks, both standing) — the CURVE BETWEEN them remains a "
            "visual estimate and was NOT ruled on; "
            "NOT_MANUFACTURING_AUTHORITATIVE",
            confidence="LOW", unit=None,
            formula="clamped natural cubic spline, s(66)=0, s(73.49)=0, "
                    "control points in SHOULDER_CONTROL_POINTS_V3"),
        "shoulder_r_at_69_mm": _f(
            round(shoulder_radius(69.0), 2), "CALCULATED_FROM_OWNER_DATA",
            "model radius at the owner's 69 mm caliper landmark "
            "(shoulder_start_height_from_base; A2 owner-ruled 2026-08-27)",
            confidence="MEDIUM",
            formula="r(69) via the V3 shoulder spline"),
        "base_bottom_radius_mm": _f(
            BASE_BOTTOM_RADIUS_MM, "GENERIC_RENDERING_DEFAULT",
            "soft external bottom round + weighted-glass settle to "
            f"{BASE_SETTLE_MM}; embossing/dot ring still NOT modelled; "
            "owner base diameter 37.35 read just above the radius",
            confidence="LOW"),
        "collar_edge_radius_mm": _f(
            COLLAR_EDGE_RADIUS_MM, "GENERIC_RENDERING_DEFAULT",
            "subtle collar top/bottom edge rounding (physically plausible "
            "small radius; owner diameter/height unchanged)",
            confidence="LOW"),
        "bulb_profile_model": _f(
            "V3 spline capsule: narrowed collar entry (r 4.60) + fillet + "
            "max-diameter hold + slightly fuller upper body + rounded "
            "dome, apex ring 0.5", "VISUAL_ESTIMATE_FROM_PHOTO",
            "V2 perfect capsule owner-noted as too mathematical; V3 per "
            "owner minor revision from IMG_3120/3123",
            confidence="LOW", unit=None),
        "glass_wall_body_mm": _f(
            GLASS_WALL_BODY_MM, "VISUALIZATION_ONLY_GEOMETRY",
            "hollow-glass wall for material renders ONLY — never measured, "
            "never manufacturing geometry", confidence="LOW"),
        "glass_wall_neck_mm": _f(
            GLASS_WALL_NECK_MM, "CALCULATED_FROM_OWNER_DATA",
            "neck wall from owner ODs — used only to shape the "
            "visualization glass shell", confidence="MEDIUM",
            formula="(15.6 - 10.3) / 2 = 2.65"),
    }


def validate_consistency() -> list[str]:
    """Owner rejection rules — every finding is a blocking defect."""
    o = OWNER
    d = {k: v["value"] for k, v in derived_values().items()}
    findings: list[str] = []
    if abs((o["bottle_height_mm"] + d["collar_above_glass_mm"]
            + o["bulb_height_mm"]) - o["total_assembled_height_mm"]) > 0.01:
        findings.append("assembled height inconsistent with owner 114.3")
    if d["collar_bottom_z_mm"] < d["neck_base_z_mm"]:
        findings.append("closure/body collision: collar reaches below the "
                        "neck base onto the shoulder")
    if d["collar_bottom_z_mm"] >= o["bottle_height_mm"]:
        findings.append("collar floats above the glass mouth — impossible "
                        "component overlap")
    if d["pipette_tip_interior_clearance_mm"] <= 0:
        findings.append("pipette penetrates the bottle base")
    if d["pipette_top_z_mm"] >= o["total_assembled_height_mm"]:
        findings.append("pipette taller than the assembled product")
    if o["pipette_outside_diameter_mm"] >= o["opening_inside_diameter_mm"]:
        findings.append("negative clearance: pipette vs bottle opening")
    if o["bulb_max_diameter_mm"] >= o["collar_outside_diameter_mm"]:
        findings.append("bulb wider than its collar")
    if o["neck_outside_diameter_mm"] >= o["body_diameter_mm"]:
        findings.append("implausible neck/body proportion")
    if not (o["straight_wall_end_mm"] < o["shoulder_landmark_69_mm"]
            < d["neck_base_z_mm"]):
        findings.append("implausible shoulder landmarks (66 / 69 / neck "
                        "base ordering)")
    return findings


# ---------------------------------------------------------------------------
# meshes (visible-structure scope: body + collar + bulb; the pipette is a
# hidden interior component — contract math only, never fabricated detail)


def _profile_top_down(points_z_r, height):
    """[(z_mm, r_mm)] bottom-up → normalized top-down profile."""
    max_r = max(r for _, r in points_z_r)
    prof = [((height - z) / height, r / max_r) for z, r in points_z_r]
    return sorted(prof), max_r


def _outer_body_points(revision: str):
    """Bottom-up (z, r) points of the bottle exterior."""
    o = OWNER
    h = o["bottle_height_mm"]
    r_base = o["base_diameter_mm"] / 2.0
    r_wall = o["body_diameter_mm"] / 2.0
    z1 = h - o["neck_height_mm"]
    pts = []
    if revision == "V1":
        pts.append((0.0, r_base - 0.9))
        pts.append((V1_BASE_EDGE_BLEND_MM, r_base))
        pts.append((o["straight_wall_end_mm"], r_wall))
        for i in range(1, 25):
            z = o["straight_wall_end_mm"] \
                + (z1 - o["straight_wall_end_mm"]) * i / 24.0
            pts.append((round(z, 3),
                        round(shoulder_radius(z, "V1"), 4)))
    else:
        R = BASE_BOTTOM_RADIUS_MM
        for i in range(9):
            z = R * i / 8.0
            pts.append((round(z, 3),
                        round(r_base - R + math.sqrt(max(R * R
                              - (R - z) ** 2, 0.0)), 4)))
        pts.append((BASE_SETTLE_MM, r_wall))
        pts.append((o["straight_wall_end_mm"], r_wall))
        n = 32 if revision == "V2" else 48
        for i in range(1, n + 1):
            z = o["straight_wall_end_mm"] \
                + (z1 - o["straight_wall_end_mm"]) * i / (n + 0.0)
            pts.append((round(z, 3),
                        round(shoulder_radius(z, revision), 4)))
    pts.append((h, o["neck_outside_diameter_mm"] / 2.0))
    return pts


def body_record(revision: str = REVISION) -> dict:
    o = OWNER
    pts = _outer_body_points(revision)
    profile, _ = _profile_top_down(pts, o["bottle_height_mm"])
    return build_geometry_record(
        source_authority="PROVISIONAL_OWNER_MEASURED_PLUS_INFERRED",
        dimensions={"height_mm": o["bottle_height_mm"],
                    "front_width_mm": o["body_diameter_mm"],
                    "side_depth_mm": o["body_diameter_mm"]},
        cross_section={"family": CIRCULAR},
        front_profile=profile,
        uncertainty=["shoulder profile is a VISUAL_ESTIMATE (A1/A2 "
                     f"landmarks provisional; revision {revision})",
                     "GL18-class thread not modelled (silhouette shows the "
                     "15.6 neck, not the 17.4 thread crests)",
                     "base bottom radius + weighted-glass settle are "
                     "GENERIC visual defaults"])


def collar_record(revision: str = REVISION) -> dict:
    o = OWNER
    h = o["collar_height_mm"]
    r = o["collar_outside_diameter_mm"] / 2.0
    if revision == "V1":
        profile = [(0.0, 1.0), (1.0, 1.0)]
    else:
        e = COLLAR_EDGE_RADIUS_MM
        pts = []
        for i in range(6):
            d = e * i / 5.0
            pts.append((round(d, 3),
                        round(r - e + math.sqrt(max(e * e - (e - d) ** 2,
                                                    0.0)), 4)))
        pts.append((h - e, r))
        for i in range(1, 6):
            d = e * i / 5.0
            pts.append((round(h - e + d, 3),
                        round(r - e + math.sqrt(max(e * e - d * d, 0.0)),
                              4)))
        profile, _ = _profile_top_down(pts, h)
    return build_geometry_record(
        source_authority="PROVISIONAL_OWNER_MEASURED_PLUS_INFERRED",
        dimensions={"height_mm": h,
                    "front_width_mm": o["collar_outside_diameter_mm"],
                    "side_depth_mm": o["collar_outside_diameter_mm"]},
        cross_section={"family": CIRCULAR},
        front_profile=profile,
        uncertainty=["collar knurling/ribs not modelled",
                     "edge rounding 0.8 is a GENERIC plausibility default"])


def bulb_record(revision: str = REVISION) -> dict:
    o = OWNER
    h = o["bulb_height_mm"]
    r = o["bulb_max_diameter_mm"] / 2.0
    # V1/V2 replicate their HISTORICAL point lists exactly so the pinned
    # mesh identities stay reproducible; V3 samples its spline densely
    if revision == "V1":
        dome_h = h * V1_BULB_DOME_FRACTION
        pts = [(0.0, r), (h - dome_h, r)]
        for i in range(1, 12):
            t = i / 12.0
            z = (h - dome_h) + dome_h * t
            pts.append((round(z, 3),
                        round(max(r * math.cos(t * math.pi / 2), 0.55), 4)))
        pts.append((h, 0.55))
    elif revision == "V2":
        dome_h = r
        pts = [(0.0, r), (h - dome_h, r)]
        for i in range(1, 15):
            d = dome_h * i / 15.0
            pts.append((round(h - dome_h + d, 3),
                        round(max(math.sqrt(max(r * r - d * d, 0.0)),
                                  0.45), 4)))
        pts.append((h, 0.45))
    else:
        pts = [(round(z, 3), round(bulb_radius(z, revision), 4))
               for z in np.linspace(0.0, h, 40)]
    profile, _ = _profile_top_down(pts, h)
    return build_geometry_record(
        source_authority="PROVISIONAL_OWNER_MEASURED_PLUS_INFERRED",
        dimensions={"height_mm": h,
                    "front_width_mm": o["bulb_max_diameter_mm"],
                    "side_depth_mm": o["bulb_max_diameter_mm"]},
        cross_section={"family": CIRCULAR},
        front_profile=profile,
        uncertainty=["bulb profile is a VISUAL_ESTIMATE from IMG_3120/3123 "
                     f"(revision {revision})"])


def _flip(mesh: dict, span: float) -> dict:
    # profile axis (index 0 = top) → z-up; winding re-normalized (same
    # construction convention as build_positioned_assembly)
    mesh["vertices"] = mesh["vertices"].copy()
    mesh["vertices"][:, 2] = span - mesh["vertices"][:, 2]
    mesh["faces"] = mesh["faces"][:, [0, 2, 1]].copy()
    return mesh


def build_p1_assembly(revision: str = REVISION):
    """(records, meshes z-up positioned, assembly facts). Collar OVERLAPS
    the neck (engagement 13.0) — P1's real construction."""
    if revision not in REVISIONS:
        raise ValueError(f"unknown revision {revision!r}")
    o = OWNER
    d = {k: v["value"] for k, v in derived_values().items()}
    records = {"body": body_record(revision),
               "collar": collar_record(revision),
               "bulb": bulb_record(revision)}
    body = _flip(build_mesh(records["body"]), o["bottle_height_mm"])
    collar = _flip(build_mesh(records["collar"]), o["collar_height_mm"])
    collar["vertices"][:, 2] += d["collar_bottom_z_mm"]
    bulb = _flip(build_mesh(records["bulb"]), o["bulb_height_mm"])
    bulb["vertices"][:, 2] += d["collar_top_z_mm"]
    meshes = {"body": body, "collar": collar, "bulb": bulb}
    facts = {
        "assembly_height_mm": o["total_assembled_height_mm"],
        "closure_center_mm": round((d["collar_bottom_z_mm"]
                                    + o["total_assembled_height_mm"]) / 2, 2),
        "closure_height_mm": round(o["total_assembled_height_mm"]
                                   - d["collar_bottom_z_mm"], 2),
        "neck_detail_center_mm": 76.0,
        "neck_detail_height_mm": 24.0,
        "shoulder_detail_center_mm": 70.0,
        "shoulder_detail_height_mm": 20.0,
        "bulb_detail_center_mm": 104.7,
        "bulb_detail_height_mm": 24.0,
        "base_detail_center_mm": 6.0,
        "base_detail_height_mm": 20.0,
    }
    return records, meshes, facts


# ---------------------------------------------------------------------------
# VISUALIZATION-ONLY hollow glass solid (V3 material renders)


def _inner_cavity_points(revision: str = REVISION):
    """Bottom-up (z, r) of the visualization-only inner glass surface."""
    o = OWNER
    h = o["bottle_height_mm"]
    z1 = h - o["neck_height_mm"]
    r_open = o["opening_inside_diameter_mm"] / 2.0     # 5.15 OWNER
    floor_z = BOTTOM_GLASS_THICKNESS_MM
    pts = [(floor_z, 0.0)]
    # inner floor blend + inner wall
    inner_wall = o["body_diameter_mm"] / 2.0 - GLASS_WALL_BODY_MM
    pts.append((floor_z + 0.8, inner_wall * 0.55))
    pts.append((floor_z + 2.0, inner_wall))
    pts.append((o["straight_wall_end_mm"], inner_wall))
    # inner shoulder: outer shoulder minus an interpolated wall thickness
    for i in range(1, 25):
        z = o["straight_wall_end_mm"] \
            + (z1 - o["straight_wall_end_mm"]) * i / 25.0
        t = (z - o["straight_wall_end_mm"]) / (z1 - o["straight_wall_end_mm"])
        wall = GLASS_WALL_BODY_MM + (GLASS_WALL_NECK_MM
                                     - GLASS_WALL_BODY_MM) * t
        r = max(shoulder_radius(z, revision) - wall, r_open)
        pts.append((round(z, 3), round(r, 4)))
    pts.append((z1, r_open))
    pts.append((h, r_open))
    return pts


def _revolve_path(path_rz, n_s: int = 96) -> dict:
    """Revolve an open (r, z) path whose both ends sit on the axis into a
    closed manifold solid. Deterministic; winding normalized outward."""
    deduped = [path_rz[0]]
    for r, z in path_rz[1:]:
        pr, pz = deduped[-1]
        if abs(r - pr) > 1e-9 or abs(z - pz) > 1e-9:
            deduped.append((r, z))
    rings = [(r, z) for r, z in deduped if r > 1e-9]
    path_rz = deduped
    t = np.linspace(0.0, 2 * np.pi, n_s, endpoint=False)
    cos_t, sin_t = np.cos(t), np.sin(t)
    verts = []
    for r, z in rings:
        ring = np.stack([r * cos_t, r * sin_t, np.full(n_s, z)], axis=1)
        verts.append(ring)
    vertices = np.concatenate(verts, axis=0)
    faces = []
    n_rings = len(rings)
    for i in range(n_rings - 1):
        a, b = i * n_s, (i + 1) * n_s
        for j in range(n_s):
            k = (j + 1) % n_s
            faces.append((a + j, a + k, b + j))
            faces.append((a + k, b + k, b + j))
    start_pole = len(vertices)
    end_pole = start_pole + 1
    vertices = np.concatenate([
        vertices,
        [[0.0, 0.0, path_rz[0][1]]],
        [[0.0, 0.0, path_rz[-1][1]]]], axis=0)
    last = (n_rings - 1) * n_s
    for j in range(n_s):
        k = (j + 1) % n_s
        faces.append((j, start_pole, k))
        faces.append((last + j, last + k, end_pole))
    faces = np.asarray(faces, dtype=np.int64)

    # normalize winding to outward normals (construction convention)
    v = vertices
    a = v[faces[:, 0]]
    signed = float(np.einsum("ij,ij->i", a,
                             np.cross(v[faces[:, 1]] - a,
                                      v[faces[:, 2]] - a)).sum() / 6.0)
    if signed < 0:
        faces = faces[:, [0, 2, 1]]
    identity = hashlib.sha256(
        np.round(vertices, 6).tobytes() + faces.tobytes()).hexdigest()[:16]
    return {"vertices": vertices, "faces": faces, "mesh_identity": identity,
            "geometry_class": "VISUALIZATION_ONLY_REVOLVED_SOLID"}


def build_p1_glass_solid(revision: str = REVISION) -> dict:
    """Closed hollow bottle-glass solid — VISUALIZATION_ONLY_GEOMETRY.

    One revolved path: outer bottom centre → outer wall/shoulder/neck →
    mouth rim → inner neck/shoulder/wall → inner floor centre. Used ONLY
    in material renders; never classified as manufacturing geometry."""
    outer = _outer_body_points(revision)
    inner = _inner_cavity_points(revision)
    o = OWNER
    rim_outer = (o["neck_outside_diameter_mm"] / 2.0, o["bottle_height_mm"])
    rim_inner = (o["opening_inside_diameter_mm"] / 2.0,
                 o["bottle_height_mm"])
    path = [(0.0, 0.0)]
    path += [(r, z) for z, r in outer]
    path += [rim_outer, rim_inner]
    path += [(r, z) for z, r in reversed(inner)]
    path += [(0.0, BOTTOM_GLASS_THICKNESS_MM)]
    solid = _revolve_path(path)
    solid["authority"] = "VISUALIZATION_ONLY_GEOMETRY"
    solid["outer_points"] = outer
    solid["inner_points"] = inner
    return solid


def build_p1_liquid_solid(revision: str = REVISION) -> dict:
    """Serum body inside the cavity — VISUALIZATION_ONLY_GEOMETRY.

    Revolved from the inner cavity profile up to a visually estimated
    fill line. Never a measured volume, never manufacturing geometry."""
    inner = _inner_cavity_points(revision)
    floor_z = BOTTOM_GLASS_THICKNESS_MM
    top_inner = max(z for z, _ in inner)
    fill_z = floor_z + (top_inner - floor_z) * LIQUID_FILL_FRACTION
    path = [(0.0, floor_z + 0.02)]
    for z, r in inner:
        if z <= fill_z:
            path.append((max(r - 0.02, 0.01), z))
    r_at_fill = min(r for z, r in inner if z >= fill_z - 2.0)
    path.append((max(r_at_fill - 0.02, 0.01), fill_z))
    path.append((0.0, fill_z - LIQUID_SURFACE_DROP_MM))
    solid = _revolve_path(path)
    solid["authority"] = "VISUALIZATION_ONLY_GEOMETRY"
    solid["fill_line_mm"] = round(fill_z, 2)
    return solid


def build_p1_contract(revision: str = REVISION) -> dict:
    """The full versioned P1 contract with authority separation."""
    owner_fields = {k: _f(v, "OWNER_MEASURED",
                          "owner intake 2026-08-04 (raw_measurements.json)",
                          unit="mm" if k != "thread_turns_visible"
                          else "turns")
                    for k, v in OWNER.items()}
    findings = validate_consistency()
    records, meshes, facts = build_p1_assembly(revision)
    glass = (build_p1_glass_solid(revision)
             if revision in ("V3", "V4") else None)
    liquid = build_p1_liquid_solid(revision) if revision == "V4" else None
    contract = {
        "schema": SCHEMA,
        "revision": revision,
        "v1_mesh_identities": dict(V1_MESH_IDENTITIES),
        "v2_mesh_identities": dict(V2_MESH_IDENTITIES),
        "v3_mesh_identities": dict(V3_MESH_IDENTITIES),
        "review_history": {
            "V1": "owner visual review: pipeline PASS / dimensional "
                  "PASS_PROVISIONAL / visual FAIL / material FAIL",
            "V2": "owner visual review: bulb PASS_WITH_MINOR_REVISION / "
                  "shoulder FAIL / material FAIL / REJECTED_PENDING_V3",
            "V3": "owner visual review: technical PASS / visual quality "
                  "UNACCEPTABLE / realism UNACCEPTABLE / match POOR / "
                  "REJECTED — strict standard: judged against the real "
                  "photographs, never against the previous revision",
        },
        "product": "P1 — Dropper Serum Bottle (BBROSE Vitamin C Facial "
                   "Serum 50 ml)",
        "pilot_mode": "PROVISIONAL_BEST_EFFORT_GEOMETRY_PILOT",
        "owner_measurements": owner_fields,
        "owner_confirmed_materials": MATERIALS,
        "owner_confirmed_neck_finish": dict(NECK_FINISH),
        "derived_and_inferred": derived_values(),
        "shoulder_control_points_v3": [
            {"z_mm": z, "r_mm": r,
             "authority": "VISUAL_ESTIMATE_FROM_OWNER_PHOTO",
             "confidence": c,
             "note": "NOT_MANUFACTURING_AUTHORITATIVE"}
            for z, r, c in SHOULDER_CONTROL_POINTS_V3],
        "bulb_control_points_v3": [
            {"z_mm": z, "r_mm": r,
             "authority": "VISUAL_ESTIMATE_FROM_OWNER_PHOTO",
             "confidence": c,
             "note": "NOT_MANUFACTURING_AUTHORITATIVE"}
            for z, r, c in BULB_CONTROL_POINTS_V3],
        "shoulder_control_points_v4": [
            {"z_mm": z, "r_mm": r,
             "authority": "VISUAL_ESTIMATE_FROM_OWNER_PHOTO",
             "confidence": c,
             "note": "NOT_MANUFACTURING_AUTHORITATIVE"}
            for z, r, c in SHOULDER_CONTROL_POINTS_V4],
        "bulb_control_points_v4": [
            {"z_mm": z, "r_mm": r,
             "authority": "VISUAL_ESTIMATE_FROM_OWNER_PHOTO",
             "confidence": c,
             "note": "NOT_MANUFACTURING_AUTHORITATIVE"}
            for z, r, c in BULB_CONTROL_POINTS_V4],
        "collar_ribbing_v4": {
            "representation": "MATERIAL BUMP ONLY (procedural wave "
            "normal) — geometric ribs would alias the 64-sample section; "
            "silhouette impact sub-pixel; clay validation unaffected",
            "rib_count": COLLAR_RIB_COUNT,
            "depth_mm": COLLAR_RIB_DEPTH_MM,
            "authority": "VISUAL_ESTIMATE_FROM_OWNER_PHOTO",
            "confidence": "LOW",
        },
        # key name retained for manifest continuity; all four were RESOLVED
        # by owner ruling on 2026-08-27 (A1 closeout) and are no longer
        # provisional. See docs/visual_quality/rbv/owner_inputs/2026-08-27/
        # a1_closeout.json.
        "provisional_assumptions": {
            "A1": "RESOLVED — OWNER RULING 2026-08-27: 66 mm is "
                  "body_height_before_shoulder_begins, a caliper landmark "
                  "in its own right. The intra-sitting proposal to RETIRE "
                  "66 was REVERSED by the owner. Caliper authority.",
            "A2": "RESOLVED — OWNER RULING 2026-08-27: 69 mm is "
                  "shoulder_start_height_from_base, a SECOND and DISTINCT "
                  "caliper landmark. 66 and 69 both stand; neither "
                  "supersedes the other. Photographs corroborate both "
                  "within a ±3.5 mm bar and separate neither — that, and "
                  "only that, is the photographs' contribution here.",
            "A3": "CONFIRMED — OWNER RULING 2026-08-27: 18.11 mm is a "
                  "HEIGHT (owner caliper submission, verbatim-preserved), "
                  "running shoulder/neck junction → glass mouth. It is NOT "
                  "a misfiled diameter.",
            "A4": "CONFIRMED — OWNER RULING 2026-08-27: 105 mm is the "
                  "overall dropper ASSEMBLY length, bulb top → pipette "
                  "tip, closure included.",
        },
        "modelling_simplifications": {
            "S1": "GL18-class thread NOT modelled (pitch from DIN 168, "
                  "turns owner-counted; silhouette shows neck Ø15.6)",
            "S2": "collar knurling/ribs NOT modelled",
            "S3": "base embossing ('50ml', '46', dot ring) NOT modelled",
            "S4": "label artwork NOT modelled (deferred to artwork phase "
                  "per owner)",
            "S5": "pipette EXCLUDED from the rendered assembly (hidden "
                  "interior component; clearances proven in contract math)",
            "S6": "hollow glass interior is VISUALIZATION_ONLY_GEOMETRY "
                  "(material renders only; never measured, never "
                  "manufacturing authority)",
            "S7": "serum fill volume is VISUALIZATION_ONLY_GEOMETRY — the "
                  "real bottle is filled (IMG_3120); fill line is a "
                  "VISUAL_ESTIMATE, never a measured capacity",
        },
        "consistency_findings": findings,
        "consistency_status": "PASS" if not findings else "REJECTED",
        "mesh_identities": {n: m["mesh_identity"]
                            for n, m in meshes.items()},
        "glass_solid_identity": glass["mesh_identity"] if glass else None,
        "liquid_solid_identity": (liquid["mesh_identity"] if liquid
                                  else None),
        "liquid_fill_line_mm": liquid["fill_line_mm"] if liquid else None,
        "geometry_class": records["body"]["geometry_class"],
        "assembly": facts,
        "accuracy_status": {
            "P1_GEOMETRY_AUTHORITY":
                "PROVISIONAL_OWNER_MEASURED_PLUS_INFERRED",
            "P1_MATERIAL_AUTHORITY":
                "OWNER_CONFIRMED_EXTERNAL_MATERIALS_PLUS_VISUALIZATION_"
                "PARAMETERS",
            "P1_INTERNAL_GLASS_AUTHORITY": "VISUALIZATION_ONLY_GEOMETRY",
            "P1_MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
            # 2026-08-27: calibrated (ruler-in-plane) frames now exist, but
            # the owner ruled that every pixel-derived number is
            # DERIVED_INDICATIVE with an error bar and NEVER OWNER_MEASURED,
            # and closed the residual 4–5% scale discrepancy as
            # UNRESOLVED_ACCEPTABLE. Comparison gates must consume the error
            # bars, not false precision.
            "P1_VISUAL_COMPARISON_CONFIDENCE":
                "CALIBRATED_PHOTOGRAPHY_CORROBORATING_ONLY_DERIVED_"
                "INDICATIVE_WITH_ERROR_BARS",
            "P1_OWNER_APPROVAL": "PENDING_VISUAL_REVIEW",
            "GATE_2": "BLOCKED",
            "PACKAGING_PRODUCTION": "NOT_STARTED",
        },
        "usage_restriction": "visual review and pipeline validation only — "
                             "NEVER supplier/manufacturing geometry",
    }
    return contract
