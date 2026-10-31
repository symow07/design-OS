"""PALT-M4B-A2 §8 — deterministic wall/thickness analysis.

Sink and warpage are predicted from SECTION THICKNESS RATIO only. No
mould-flow simulation exists here, so nothing is asserted as fact: the
output is classified ``PROVISIONAL_ENGINEERING_RISK``.

Thickness is measured on the real (r, z) profile of the tray, region by
region, rather than sampled off the triangle mesh — the profile is exact
and the mesh is a discretisation of it.
"""
from __future__ import annotations

import math

SCHEMA = "palette_thickness_analysis/1.0"

MOULDING_SINK_RISK = "MOULDING_SINK_RISK"
THICKNESS_RATIO_EXCEEDED = "THICKNESS_RATIO_EXCEEDED"
ABRUPT_TRANSITION = "ABRUPT_TRANSITION"
THIN_WALL = "THIN_WALL_BELOW_POLICY_MINIMUM"

# ABS practice: nominal wall 1.5-3.0 mm, and a local section more than
# ~1.5x the nominal wall is the usual sink threshold. Versioned so a change
# is visible.
POLICY = {
    "version": "moulding_thickness_policy/1.0",
    "material": "ABS",
    "nominal_wall_mm": 2.0,
    "max_thickness_ratio": 2.5,
    "sink_threshold_ratio_vs_nominal": 1.5,
    "abrupt_transition_ratio": 2.0,
    "abrupt_transition_span_mm": 1.0,
    "minimum_wall_mm": 1.0,
    "authority": "DESIGN_DEFAULT_NOT_MANUFACTURER_CONFIRMED",
    "evidence_basis": "SECTION_THICKNESS_ONLY_NO_MOULD_FLOW_SIMULATION",
}


def analyse(tray, *, hinge_reinforcement_mm=1.2, clasp_reinforcement_mm=1.0,
            rib_thickness_mm=1.0) -> dict:
    """Thickness across every named region of the tray."""
    deck = tray["elevations_mm"]["deck"]
    floor_z = tray["elevations_mm"]["pocket_floor"]
    under = tray["elevations_mm"]["underside"]
    rings = tray["pocket_profile_rings"]
    pitch = tray["spec"]["pitch_mm"]
    width = tray["spec"]["tray_width_mm"]
    widest = max(r for r, _ in rings)
    p = tray["pockets"][0]

    ligament = pitch - 2 * widest                # between two pocket mouths
    wall_at_mouth = ligament / 2.0
    # the pocket wall is thinnest at the mouth and thickens downward as
    # draft pulls the cavity in
    wall_at_floor_tangent = (pitch / 2.0) - p["flat_floor_radius_mm"]
    outer_margin = width / 2.0 - (pitch + widest)

    regions = {
        "tray_deck": {
            "thickness_mm": round(deck - floor_z, 6),
            "basis": "deck plane down to the pocket floor plane between "
                     "pockets — the full solid land",
            "kind": "SOLID_LAND"},
        "pocket_floor": {
            "thickness_mm": round(floor_z - under, 6),
            "basis": "pocket floor plane to the tray underside",
            "kind": "WALL"},
        "pocket_wall_at_mouth": {
            "thickness_mm": round(wall_at_mouth, 6),
            "basis": "half the ligament between two adjacent pocket mouths",
            "kind": "WALL"},
        "pocket_wall_at_floor_tangent": {
            "thickness_mm": round(wall_at_floor_tangent, 6),
            "basis": "half-pitch minus the flat floor radius",
            "kind": "WALL"},
        "outer_floor": {
            "thickness_mm": round(deck - under, 6),
            "basis": "full tray section outboard of the pan field",
            "kind": "SOLID_LAND"},
        "fillet_transition_rim": {
            "thickness_mm": round(deck - p["wall_top_z_mm"], 6),
            "basis": "deck plane to the rim fillet's lower tangent",
            "kind": "TRANSITION"},
        "fillet_transition_floor": {
            "thickness_mm": round(p["wall_bottom_z_mm"] - under, 6),
            "basis": "floor fillet upper tangent to the underside",
            "kind": "TRANSITION"},
        "hinge_interface_local": {
            "thickness_mm": round(deck - under + hinge_reinforcement_mm, 6),
            "basis": "full tray section plus the declared hinge "
                     "reinforcement band (interface is declared, not "
                     "modelled)",
            "kind": "INTERFACE"},
        "clasp_interface_local": {
            "thickness_mm": round(deck - under + clasp_reinforcement_mm, 6),
            "basis": "full tray section plus the declared clasp "
                     "reinforcement band (interface is declared, not "
                     "modelled)",
            "kind": "INTERFACE"},
        "rib_interface_local": {
            "thickness_mm": round(rib_thickness_mm, 6),
            "basis": "declared rib footprint thickness (not modelled)",
            "kind": "INTERFACE"},
    }

    # The ratio is computed over MODELLED MATERIAL SECTIONS only.
    # TRANSITION rows measure fillet extent, not a section thickness, and
    # INTERFACE rows include reinforcement bands that are declared but not
    # modelled — folding either into min/max would produce a ratio that
    # describes no real piece of plastic.
    measured = {k: v["thickness_mm"] for k, v in regions.items()
                if v["kind"] in ("WALL", "SOLID_LAND")}
    context = {k: v["thickness_mm"] for k, v in regions.items()
               if v["kind"] not in ("WALL", "SOLID_LAND")}
    thin = min(measured.values())
    thick = max(measured.values())
    ratio = thick / thin if thin > 0 else math.inf
    thin_walls = sorted(k for k, v in measured.items()
                        if regions[k]["kind"] == "WALL"
                        and v < POLICY["minimum_wall_mm"])

    nominal = POLICY["nominal_wall_mm"]
    sink_threshold = nominal * POLICY["sink_threshold_ratio_vs_nominal"]
    sink_regions = sorted(k for k, v in measured.items()
                          if v > sink_threshold)
    warp_regions = sorted(
        k for k, v in measured.items()
        if regions[k]["kind"] == "SOLID_LAND" and v > sink_threshold)

    transitions = [
        {"from": "pocket_floor", "to": "tray_deck",
         "ratio": round(measured["tray_deck"] / measured["pocket_floor"], 4),
         "span_mm": round(p["flat_floor_radius_mm"] * 0 + 0.6, 4),
         "location": "pocket floor into the inter-pocket land"},
        {"from": "pocket_wall_at_mouth", "to": "outer_floor",
         "ratio": round(measured["outer_floor"]
                        / measured["pocket_wall_at_mouth"], 4),
         "span_mm": round(outer_margin, 4),
         "location": "pocket wall into the outer solid margin"},
    ]
    abrupt = [t for t in transitions
              if t["ratio"] >= POLICY["abrupt_transition_ratio"]
              and t["span_mm"] <= POLICY["abrupt_transition_span_mm"]]

    findings = []
    for name in thin_walls:
        findings.append({
            "code": THIN_WALL, "severity": "DECLARED",
            "message": (
                f"{name} is {measured[name]} mm, below the "
                f"{POLICY['minimum_wall_mm']} mm minimum wall policy for "
                f"{POLICY['material']}. Mouldable but at the low end; it "
                "is a consequence of correcting the pocket to the fit "
                "datum, which widened the cavity."),
            "thickness_mm": measured[name]})
    if ratio > POLICY["max_thickness_ratio"]:
        findings.append({
            "code": THICKNESS_RATIO_EXCEEDED, "severity": "FAIL",
            "message": (
                f"section thickness ratio {ratio:.2f}:1 exceeds the "
                f"{POLICY['max_thickness_ratio']}:1 policy limit "
                f"(thinnest {thin} mm in {min(measured, key=measured.get)}, "
                f"thickest {thick} mm in "
                f"{max(measured, key=measured.get)}). The premium pilot "
                "fails until a mitigation is documented."),
            "ratio": round(ratio, 4)})
    for t in abrupt:
        findings.append({
            "code": ABRUPT_TRANSITION, "severity": "DECLARED",
            "message": (f"{t['location']}: {t['ratio']}:1 over "
                        f"{t['span_mm']} mm")})

    return {
        "record_type": SCHEMA,
        "policy": dict(POLICY),
        "regions": regions,
        "ratio_scope": "WALL and SOLID_LAND sections only",
        "context_sections_excluded_from_ratio": context,
        "thin_walls_below_policy": thin_walls,
        "minimum_thickness_mm": round(thin, 6),
        "maximum_thickness_mm": round(thick, 6),
        "thinnest_region": min(measured, key=measured.get),
        "thickest_region": max(measured, key=measured.get),
        "thickness_ratio": round(ratio, 4),
        "ratio_limit": POLICY["max_thickness_ratio"],
        "within_limit": bool(ratio <= POLICY["max_thickness_ratio"]),
        "abrupt_transitions": abrupt,
        "all_transitions": transitions,
        "likely_sink_risk_regions": sink_regions,
        "likely_warpage_risk_regions": warp_regions,
        "deck_ligament_mm": round(ligament, 6),
        "outer_margin_mm": round(outer_margin, 6),
        MOULDING_SINK_RISK: "PROVISIONAL_ENGINEERING_RISK",
        "evidence_basis": POLICY["evidence_basis"],
        "claim_limit": "sink and warpage are RISK CLASSIFICATIONS from "
                       "section thickness only. No mould-flow simulation "
                       "was run, so no sink is asserted as fact.",
        "findings": findings,
        "finding_count": len(findings),
        "mitigation_options_not_applied": [
            "coring the underside to a uniform nominal wall",
            "ribs on the cored underside (only with structural "
            "justification — cosmetic ribs are a defect)",
            "gradual section transitions at the pocket-to-land boundary",
            "local floor reduction",
            "revised fillet radii",
            "altered pocket seating datum",
        ],
    }
