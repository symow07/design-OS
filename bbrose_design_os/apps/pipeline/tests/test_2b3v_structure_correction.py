"""Task #51 structural correction — rigid wand-applicator bottle, not a tube.

The proposed profile classified the Rosé Nectar container as a crimped squeeze
tube with CYLINDRICAL front/back faces. The user corrected it: a rigid
wand-applicator BOTTLE, 35×25×95, ROUNDED_RECT cross-section — flat readable
central front/back faces, curved corner transitions, bottom code area, no
crimp. These tests pin the contract behaviour that correction relies on."""
from __future__ import annotations

from apps.pipeline.services import container_contract as cc


def _rounded_rect_bottle():
    rec = cc.build_inferred_profile("bottle", "slim", estimates={
        "body_width_mm": 35.0, "body_height_mm": 95.0,
        "body_depth_mm": 25.0})
    rec["fields"]["base_geometry"] = {
        "value": "RECTANGULAR_WITH_ROUNDED_CORNERS",
        "source": cc.SRC_USER_FACT, "verification": cc.UNVERIFIED}
    rec["profile_hash"] = cc.profile_hash(rec)
    return rec


def test_bottle_has_a_bottom_surface():
    # a rigid bottle carries a bottom code area — no crimp required
    assert "BOTTOM" in cc.surfaces_for("bottle")
    assert "CRIMP_ZONE" not in cc.surfaces_for("bottle")


def test_rounded_rect_cross_section_gives_flat_readable_faces():
    geom = cc.surface_geometry(_rounded_rect_bottle())
    assert geom["BODY_FRONT"]["curvature"] == cc.FLAT      # never CYLINDRICAL
    assert geom["BODY_BACK"]["curvature"] == cc.FLAT
    # the curved corner transitions live on the sides
    assert geom["BODY_LEFT"]["curvature"] == cc.ROUNDED_RECT
    assert geom["BODY_RIGHT"]["curvature"] == cc.ROUNDED_RECT


def test_without_recorded_cross_section_variant_mapping_is_unchanged():
    rec = cc.build_inferred_profile("bottle", "cylindrical", estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0, "body_depth_mm": 40.0})
    geom = cc.surface_geometry(rec)
    assert geom["BODY_FRONT"]["curvature"] == cc.CYLINDRICAL   # legacy intact


def test_corrected_zone_set_validates_on_the_bottle():
    rec = _rounded_rect_bottle()
    geom = cc.surface_geometry(rec)
    fx = geom["BODY_FRONT"]
    bx = geom["BOTTOM"]
    zones = [
        cc.make_zone("z_front", "FRONT_PRINT_ZONE", "BODY_FRONT",
                     x=5.2, y=19.0, width=round(fx["w"] * 0.7, 1),
                     height=round(fx["h"] * 0.6, 1), curvature_type=fx["curvature"],
                     source=cc.SRC_USER_FACT, verification=cc.UNVERIFIED),
        cc.make_zone("z_bottom_code", "BOTTOM_CODE_ZONE", "BOTTOM",
                     x=round(bx["w"] * 0.25, 1), y=round(bx["h"] * 0.25, 1),
                     width=round(bx["w"] * 0.5, 1), height=round(bx["h"] * 0.5, 1),
                     curvature_type=bx["curvature"], safe_margin_mm=1.0,
                     max_artwork_coverage=0.2,
                     permitted_techniques=("pad_printing",),
                     source=cc.SRC_USER_FACT, verification=cc.UNVERIFIED),
    ]
    assert cc.validate_zone_set(zones, rec) == []
    assert zones[0]["curvature_type"] == cc.FLAT


def test_bottom_code_zone_derives_inkjet_method_with_user_authority():
    from apps.ire import container_production_method as pm
    rec = _rounded_rect_bottle()
    bx = cc.surface_geometry(rec)["BOTTOM"]
    zone = cc.make_zone(
        "z_bottom_code", "BOTTOM_CODE_ZONE", "BOTTOM",
        x=6.0, y=6.0, width=round(bx["w"] * 0.5, 1),
        height=round(bx["h"] * 0.5, 1), curvature_type=bx["curvature"],
        safe_margin_mm=1.0, max_artwork_coverage=0.2,
        permitted_techniques=("pad_printing",),
        source=cc.SRC_USER_FACT, verification=cc.UNVERIFIED)
    methods = pm.build_production_methods([zone], rec)
    (m,) = methods["methods"]
    assert m["method_type"] == "BOTTOM_INKJET_CODE"
    # design intent only — never a manufacturer capability
    assert m["verification_source"] == "EXPLICIT_USER_REQUEST"
    assert m["authority_state"] == "USER_REQUESTED_UNVERIFIED"
    assert methods["all_manufacturer_verified"] is False


def test_crimp_zone_is_invalid_on_a_bottle():
    rec = _rounded_rect_bottle()
    zone = cc.make_zone(
        "z_crimp_code", "BOTTOM_CODE_ZONE", "CRIMP_ZONE",
        x=1.0, y=0.0, width=5.0, height=3.0, curvature_type=cc.FLAT,
        safe_margin_mm=1.0, permitted_techniques=("pad_printing",))
    problems = cc.validate_zone_set([zone], rec)
    assert any(p.startswith(cc.ZONE_SURFACE_MISMATCH) for p in problems)


# --- unbounded-cap gate (correction items 1/4) --------------------------------

def _cap_zone(rec, curvature):
    geom = cc.surface_geometry(rec)
    cg = geom["CAP_FRONT"]
    return cc.make_zone(
        "z_cap", "CAP_PRINT_ZONE", "CAP_FRONT",
        x=1.0, y=1.0, width=round(cg["w"] * 0.5, 1),
        height=round(cg["h"] * 0.4, 1), curvature_type=curvature,
        safe_margin_mm=1.0, max_artwork_coverage=0.3,
        permitted_techniques=("pad_printing",),
        user_confirmation_state=cc.ZONE_USER_CONFIRMED)


def test_unbounded_cap_makes_cap_surfaces_unknown():
    rec = _rounded_rect_bottle()                       # cap dims MISSING
    geom = cc.surface_geometry(rec)
    for s in ("CAP_FRONT", "CAP_BACK", "CAP_TOP", "CAP_WRAP"):
        assert geom[s]["curvature"] == cc.CURVATURE_UNKNOWN, s


def _confirmable_bottle():
    """A rounded-rect bottle whose BODY dims are user-confirmed, so the
    ordered refusal reaches the ZONE stage (profile → zones → curvature)."""
    return cc.merge_user_profile(_rounded_rect_bottle(), {
        "body_width_mm": 35.0, "body_depth_mm": 25.0, "body_height_mm": 95.0})


def test_unbounded_cap_zone_refuses_with_projection_review():
    # item 4: even a zone CLAIMING cylindrical refuses on an unbounded cap
    rec = _confirmable_bottle()
    zone = _cap_zone(rec, cc.CYLINDRICAL)
    assert cc.evaluate_confirmation(rec, [zone]) == \
        cc.SURFACE_PROJECTION_REVIEW_REQUIRED


def test_supplied_cap_dims_make_the_cap_zone_confirmable():
    rec = cc.merge_user_profile(_confirmable_bottle(), {
        "cap_width_mm": 30.0, "cap_depth_mm": 20.0, "cap_height_mm": 25.0})
    assert cc.surface_geometry(rec)["CAP_FRONT"]["curvature"] == cc.CYLINDRICAL
    zone = _cap_zone(rec, cc.CYLINDRICAL)
    assert cc.evaluate_confirmation(rec, [zone]) is None


def test_bottom_inkjet_code_is_a_valid_zone_technique():
    rec = _rounded_rect_bottle()
    bx = cc.surface_geometry(rec)["BOTTOM"]
    zone = cc.make_zone(
        "z_bottom_code", "BOTTOM_CODE_ZONE", "BOTTOM",
        x=6.0, y=6.0, width=round(bx["w"] * 0.5, 1),
        height=round(bx["h"] * 0.5, 1), curvature_type=bx["curvature"],
        safe_margin_mm=1.0, max_artwork_coverage=0.2,
        permitted_techniques=("BOTTOM_INKJET_CODE",))
    assert cc.validate_zone_set([zone], rec) == []
