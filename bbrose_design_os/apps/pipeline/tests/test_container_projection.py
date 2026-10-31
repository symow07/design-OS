"""Phase 2B-2 slice 3 — curved-surface projection + decoration containment.

Deterministic geometry: each curvature class projects predictably; CUSTOM /
UNKNOWN and an unsafe oval full-wrap fail closed; and every emitted artwork
placement must sit inside its confirmed zone (bounds, safe margin, coverage,
surface, wrap seam, cap/body) with precise, stable §6 codes.
"""
from __future__ import annotations

from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_projection as cp


def _zone(**kw):
    z = {"zone_id": "z", "zone_type": "FRONT_PRINT_ZONE",
         "parent_surface": "BODY_FRONT", "x": 0, "y": 0, "width": 40,
         "height": 60, "curvature_type": cc.FLAT, "safe_margin_mm": 3.0,
         "max_artwork_coverage": 0.8}
    z.update(kw)
    return z


# --- §7 projection -----------------------------------------------------------

def test_flat_is_one_to_one():
    out = cp.project_zone(_zone(), {"w": 40, "curvature": cc.FLAT})
    assert out["method"] == "direct_1_1"
    assert out["projected"] == {"width_mm": 40.0, "height_mm": 60.0}
    assert out["distortion"] == 0.0 and out["review_required"] is False


def test_cylindrical_maps_width_to_arc_and_reports_radius():
    surf = {"w": round(3.14159 * 50, 2), "curvature": cc.CYLINDRICAL}
    out = cp.project_zone(_zone(curvature_type=cc.CYLINDRICAL, width=50),
                          surf)
    assert out["method"] == "cylindrical_arc"
    assert out["projected"]["width_mm"] == 50.0        # arc length
    assert out["projected"]["wrap_radius_mm"] > 0
    assert out["projected"]["wrap_arc_deg"] > 0
    assert out["distortion"] >= 0                       # reported, not hidden


def test_tapered_produces_trapezoid_with_distortion():
    surf = {"w": round(3.14159 * 40, 2), "curvature": cc.TAPERED_CYLINDRICAL}
    out = cp.project_zone(
        _zone(curvature_type=cc.TAPERED_CYLINDRICAL, width=30), surf)
    assert out["projected"]["field_shape"] == "trapezoid"
    assert out["projected"]["top_width_mm"] < out["projected"]["bottom_width_mm"]
    assert out["distortion"] > 0


def test_oval_front_ok_but_full_wrap_reviews():
    front = cp.project_zone(
        _zone(curvature_type=cc.OVAL, parent_surface="BODY_FRONT"),
        {"w": 40, "curvature": cc.OVAL})
    assert front["review_required"] is False
    wrap = cp.project_zone(
        _zone(curvature_type=cc.OVAL, parent_surface="BODY_WRAP"),
        {"w": 120, "curvature": cc.OVAL})
    assert wrap["review_required"] is True
    assert wrap["code"] == cp.SURFACE_PROJECTION_REVIEW_REQUIRED


def test_rounded_rect_has_flat_centre_inset():
    out = cp.project_zone(_zone(curvature_type=cc.ROUNDED_RECT),
                          {"w": 40, "curvature": cc.ROUNDED_RECT})
    assert out["projected"]["flat_centre_inset_mm"] > 0
    assert out["review_required"] is False


def test_custom_and_unknown_fail_closed():
    for curve in (cc.CUSTOM_PROFILE, cc.CURVATURE_UNKNOWN):
        out = cp.project_zone(_zone(curvature_type=curve),
                              {"w": 40, "curvature": curve})
        assert out["review_required"] is True
        assert out["code"] == cp.SURFACE_PROJECTION_REVIEW_REQUIRED
        assert out["projected"] is None


def test_project_zones_flags_review_when_any_zone_reviews():
    prof = cc.build_inferred_profile("bottle")
    zones = cc.propose_zones(prof)
    zones[0]["curvature_type"] = cc.CURVATURE_UNKNOWN
    rep = cp.project_zones(zones, prof)
    assert rep["review_required"] is True
    assert rep["code"] == cp.SURFACE_PROJECTION_REVIEW_REQUIRED


# --- §6 containment ----------------------------------------------------------

def _profile():
    # cap estimates keep the optional cap zone proposed (bounded cap)
    return cc.build_inferred_profile("bottle", estimates={
        "cap_width_mm": 20.0, "cap_height_mm": 13.0})


def test_contained_placement_passes():
    prof = _profile()
    zones = cc.propose_zones(prof)
    zid = zones[0]["zone_id"]
    placements = [
        {"zone_id": zid, "kind": "field", "nx": 0, "ny": 0, "nw": 1, "nh": 1},
        {"zone_id": zid, "kind": "product_name", "nx": 0.2, "ny": 0.25,
         "nw": 0.6, "nh": 0.3, "surface_family": "body"}]
    assert cp.validate_zone_containment(placements, zones, prof) == []


def test_out_of_zone_is_flagged():
    prof = _profile()
    zones = cc.propose_zones(prof)
    placements = [{"zone_id": zones[0]["zone_id"], "kind": "product_name",
                   "nx": 0.8, "ny": 0.2, "nw": 0.5, "nh": 0.3}]
    probs = cp.validate_zone_containment(placements, zones, prof)
    assert any(p.startswith(cp.DECORATION_OUTSIDE_ZONE) for p in probs)


def test_unknown_zone_reference_is_flagged():
    prof = _profile()
    zones = cc.propose_zones(prof)
    probs = cp.validate_zone_containment(
        [{"zone_id": "ghost", "kind": "product_name", "nx": 0.2, "ny": 0.2,
          "nw": 0.4, "nh": 0.3}], zones, prof)
    assert any(p.startswith(cp.DECORATION_OUTSIDE_ZONE) for p in probs)


def test_coverage_cap_enforced():
    prof = _profile()
    zones = cc.propose_zones(prof)
    zones[0]["max_artwork_coverage"] = 0.2
    placements = [{"zone_id": zones[0]["zone_id"], "kind": "product_name",
                   "nx": 0.05, "ny": 0.05, "nw": 0.9, "nh": 0.9}]
    probs = cp.validate_zone_containment(placements, zones, prof)
    assert any(p.startswith(cp.DECORATION_COVERAGE_EXCEEDED) for p in probs)


def test_cap_body_family_mismatch_flagged():
    prof = _profile()
    zones = cc.propose_zones(prof)
    # z_cap_top is a CAP surface; a body-declared placement there conflicts
    cap = next(z for z in zones if z["parent_surface"] == "CAP_TOP")
    probs = cp.validate_zone_containment(
        [{"zone_id": cap["zone_id"], "kind": "product_name", "nx": 0.2,
          "ny": 0.2, "nw": 0.4, "nh": 0.3, "surface_family": "body"}],
        zones, prof)
    assert any(p.startswith(cp.CAP_BODY_ZONE_CONFLICT) for p in probs)


def test_his_answer_a_part_placed_as_pictured_inside_the_margin_is_a_production_note():
    """His answer on the print area's safe margin (2026-10-01, transcribed at f23b9e8): "The picture (Recommended)". A
    part that a front drawn from its concept's measured layout places where the picture prints it, inside its zone but
    within the zone's safe margin, is a production note, never the margin's violation; past the zone's own edge it is
    refused as before; any other placement inside the margin is the violation, as before, and the margin is 3.0 mm."""
    from apps.ire.container_production_readiness import is_production_note
    prof = _profile()
    zones = cc.propose_zones(prof)
    edge = {"zone_id": zones[0]["zone_id"], "kind": "band", "nx": 0.0, "ny": 0.3, "nw": 1.0, "nh": 0.2,
            "surface_family": "body"}
    (note,) = cp.validate_zone_containment([dict(edge, as_pictured=True)], zones, prof)
    assert note.startswith(cp.ZONE_SAFE_MARGIN_AS_PICTURED) and is_production_note(note), note
    (plain,) = cp.validate_zone_containment([edge], zones, prof)
    assert plain.startswith(cp.ZONE_SAFE_MARGIN_VIOLATION) and not is_production_note(plain), plain
    past = cp.validate_zone_containment([dict(edge, as_pictured=True, nw=1.2)], zones, prof)
    assert any(p.startswith(cp.DECORATION_OUTSIDE_ZONE) and not is_production_note(p) for p in past), past
    assert zones[0]["safe_margin_mm"] == 3.0

