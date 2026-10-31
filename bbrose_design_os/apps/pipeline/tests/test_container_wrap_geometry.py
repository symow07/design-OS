"""Phase 2B-3C §7-§10 — true seam-aware wrap production geometry.

A production-geometry data record (radius / circumference / seam / arc-mapping /
anchors / exclusions), never a re-emission of the concept sheet. Cylindrical
maps flat x → arc degrees with an explicit seam; tapered/oval/custom flag a
distortion/projection review; alignment measurement fires when a mark runs into
the seam-safe band.
"""
from __future__ import annotations

import pytest

from apps.ire import container_wrap_geometry as wg
from apps.ire.graph import Document, Group
from apps.pipeline.services import container_contract as cc


def _jar_zones():
    prof = cc.build_inferred_profile("jar", estimates={
        "body_width_mm": 70.0, "body_height_mm": 60.0})
    return prof, cc.propose_zones(prof)


def test_cylindrical_wrap_has_seam_arc_and_circumference():
    prof, zones = _jar_zones()
    geo = wg.build_wrap_geometry(zones, prof)
    wraps = {w["surface"]: w for w in geo["wraps"]}
    assert "BODY_WRAP" in wraps
    w = wraps["BODY_WRAP"]
    assert w["curvature_type"] == cc.CYLINDRICAL
    assert w["circumference_mm"] > 0
    assert w["seam_position"] == "trailing_edge"
    assert w["arc_mapping"]["seam_deg"] == 0.0
    assert 0 <= w["arc_mapping"]["artwork_end_deg"] <= 360
    assert w["projection_hash"] and geo["wrap_set_hash"]


def test_tapered_flags_distortion_review():
    prof = cc.build_inferred_profile("tube", estimates={
        "body_width_mm": 35.0, "body_height_mm": 120.0})
    zones = cc.propose_zones(prof)
    # force a body zone onto a tapered surface
    for z in zones:
        if z["parent_surface"] == "BODY_FRONT":
            z["curvature_type"] = cc.TAPERED_CYLINDRICAL
    geo = wg.build_wrap_geometry(zones, prof)
    rep = wg.validate_wrap_alignment(geo, _empty_doc(), zones)
    codes = rep["codes"]
    assert wg.PROJECTION_DISTORTION_REVIEW_REQUIRED in codes
    # §BH50(f)(6): a tube's zones are projected faces, so the seam check
    # places itself off them — while the distortion review, a rule that
    # describes a tapered face whether or not it wraps, keeps firing on it
    assert rep["seam_check"]["state"] == wg.NOT_APPLICABLE
    assert rep["aligned"] is None


def test_custom_curvature_reviews():
    prof, zones = _jar_zones()
    for z in zones:
        if z["parent_surface"] == "BODY_WRAP":
            z["curvature_type"] = cc.CUSTOM_PROFILE
    geo = wg.build_wrap_geometry(zones, prof)
    assert geo["review_required"] is True
    codes = wg.validate_wrap_alignment(geo, _empty_doc(), zones)["codes"]
    assert wg.SURFACE_PROJECTION_REVIEW_REQUIRED in codes


def _doc_with_placement(zone_id, nx, nw, kind="product_name"):
    doc = Document(page_w=210, page_h=297,
                   root=Group(name="Artwork", role="artwork", children=[]))
    doc.metadata["placements"] = [{"zone_id": zone_id, "kind": kind,
                                   "nx": nx, "ny": 0.2, "nw": nw, "nh": 0.3}]
    return doc


def _empty_doc():
    return Document(page_w=210, page_h=297,
                    root=Group(name="Artwork", role="artwork", children=[]))


def test_text_into_seam_safe_band_conflicts():
    prof, zones = _jar_zones()
    geo = wg.build_wrap_geometry(zones, prof)
    wrap_zone = next(w["zone_id"] for w in geo["wraps"]
                     if w["surface"] == "BODY_WRAP")
    # a name running to the trailing edge crosses the seam-safe band
    doc = _doc_with_placement(wrap_zone, nx=0.5, nw=0.55)
    rep = wg.validate_wrap_alignment(geo, doc, zones)
    assert wg.TEXT_CROSSES_SEAM in rep["codes"]
    assert rep["aligned"] is False
    assert rep["seam_check"]["state"] == wg.APPLICABLE       # §BH50(f)(6)


def test_contained_placement_is_aligned():
    prof, zones = _jar_zones()
    geo = wg.build_wrap_geometry(zones, prof)
    wrap_zone = next(w["zone_id"] for w in geo["wraps"]
                     if w["surface"] == "BODY_WRAP")
    doc = _doc_with_placement(wrap_zone, nx=0.3, nw=0.4)   # well inside
    rep = wg.validate_wrap_alignment(geo, doc, zones)
    assert wg.TEXT_CROSSES_SEAM not in rep["codes"]
    assert rep["aligned"] is True
    assert rep["seam_check"]["state"] == wg.APPLICABLE       # §BH50(f)(6)


# --- §BH50(f)(6): WRAP ALIGNMENT PLACED ON WRAPPED SURFACES ------------------


def _dropper_zone(surface="BODY_FRONT", zone_id="z_front", **over):
    """Task 52's confirmed front-zone geometry (22.0 × 40.0 at x 5.5, safe
    margin 3.0, USER_CONFIRMED) as a hand-built zone, so the rule is exercised
    on the product's own numbers."""
    z = {"zone_id": zone_id, "zone_type": "FRONT_PRINT_ZONE",
         "parent_surface": surface, "curvature_type": cc.CYLINDRICAL,
         "x": 5.5, "y": 10.0, "width": 22.0, "height": 40.0,
         "safe_margin_mm": 3.0, "max_artwork_coverage": 0.8,
         "permitted_techniques": ["screen_printing"],
         "user_confirmation_state": cc.ZONE_USER_CONFIRMED}
    z.update(over)
    return z


def test_the_seam_check_places_itself_off_a_face_and_on_a_wrap_with_the_same_placement():
    """The discriminating pair. Task 52's own placement record (nx 0.15 /
    nw 0.70, ``compose_dropper.place``) on the dropper's front-zone geometry:
    on BODY_FRONT the seam rule has nothing to place itself on — NOT_APPLICABLE
    with a reason naming the surface and its confirmation, no code, ``aligned``
    None. The same placement on a BODY_WRAP zone of the same geometry crosses
    the 4.0 mm seam band (4/22 = 0.1818 > 0.15): TEXT_CROSSES_SEAM fires, and a
    motif placement fires WRAP_SEAM_CONFLICT — the first pin of that code."""
    prof, _ = _jar_zones()      # a jar carries both faces and a wrap
    face = [_dropper_zone()]
    geo = wg.build_wrap_geometry(face, prof)
    assert geo["wraps"][0]["wrapped"] is False and geo["wrapped_zone_ids"] == []
    rep = wg.validate_wrap_alignment(
        geo, _doc_with_placement("z_front", nx=0.15, nw=0.70), face)
    assert rep["seam_check"]["state"] == wg.NOT_APPLICABLE
    assert "BODY_FRONT" in rep["seam_check"]["reason"]
    assert cc.ZONE_USER_CONFIRMED in rep["seam_check"]["reason"]
    assert rep["codes"] == [] and rep["aligned"] is None

    wrap = [_dropper_zone(surface="BODY_WRAP", zone_id="z_wrap",
                          zone_type="WRAP_LABEL_ZONE",
                          permitted_techniques=["wrap_label"])]
    geo = wg.build_wrap_geometry(wrap, prof)
    assert geo["wraps"][0]["wrapped"] is True
    assert geo["wrapped_zone_ids"] == ["z_wrap"]
    rep = wg.validate_wrap_alignment(
        geo, _doc_with_placement("z_wrap", nx=0.15, nw=0.70), wrap)
    assert rep["seam_check"]["state"] == wg.APPLICABLE
    assert wg.TEXT_CROSSES_SEAM in rep["codes"] and rep["aligned"] is False
    rep = wg.validate_wrap_alignment(
        geo, _doc_with_placement("z_wrap", nx=0.15, nw=0.70, kind="motif"), wrap)
    assert wg.WRAP_SEAM_CONFLICT in rep["codes"] and rep["aligned"] is False


def test_applicability_is_never_decided_by_absence():
    """An empty zone set used to return ``aligned`` True over nothing. Now:
    no zones → UNMEASURED; a zone with no surface → UNMEASURED naming it; the
    alias spelling → the WI-R raise; a PROPOSED face set → NOT_APPLICABLE
    whose reason records PROPOSED; a PROPOSED wrap with a crossing placement
    still fires, because applying the rule never needs confirmation."""
    prof, _ = _jar_zones()
    for empty in ([], None):
        rep = wg.validate_wrap_alignment(
            wg.build_wrap_geometry(empty, prof), _empty_doc(), empty)
        assert rep["seam_check"]["state"] == wg.UNMEASURED
        assert rep["aligned"] is None and rep["codes"] == []
    bare = [_dropper_zone()]
    del bare[0]["parent_surface"]
    rep = wg.validate_wrap_alignment(
        wg.build_wrap_geometry(bare, prof), _empty_doc(), bare)
    assert rep["seam_check"]["state"] == wg.UNMEASURED
    assert "z_front" in rep["seam_check"]["reason"]
    alias = [{("surface" if k == "parent_surface" else k): v
              for k, v in _dropper_zone().items()}]
    with pytest.raises(cc.ZoneSurfaceSpellingError):
        wg.seam_applicability(alias)
    proposed = [_dropper_zone(user_confirmation_state=cc.ZONE_PROPOSED),
                _dropper_zone(surface="BODY_BACK", zone_id="z_back",
                              zone_type="BACK_PRINT_ZONE",
                              user_confirmation_state=cc.ZONE_PROPOSED)]
    rep = wg.validate_wrap_alignment(
        wg.build_wrap_geometry(proposed, prof), _empty_doc(), proposed)
    assert rep["seam_check"]["state"] == wg.NOT_APPLICABLE
    assert cc.ZONE_PROPOSED in rep["seam_check"]["reason"]
    assert "BODY_BACK" in rep["seam_check"]["reason"]
    wrap = [_dropper_zone(surface="BODY_WRAP", zone_id="z_wrap",
                          zone_type="WRAP_LABEL_ZONE",
                          permitted_techniques=["wrap_label"],
                          user_confirmation_state=cc.ZONE_PROPOSED)]
    rep = wg.validate_wrap_alignment(
        wg.build_wrap_geometry(wrap, prof),
        _doc_with_placement("z_wrap", nx=0.15, nw=0.70), wrap)
    assert rep["seam_check"]["state"] == wg.APPLICABLE
    assert wg.TEXT_CROSSES_SEAM in rep["codes"]


def test_a_wrap_declared_by_type_or_technique_on_a_face_is_still_wrapped():
    """The contradiction guard: the confirm endpoint checks neither the zone
    type nor the technique against the surface, so a WRAP_LABEL_ZONE with the
    wrap_label technique confirmed on BODY_FRONT is read as wrapped and the
    seam check fires. The guard only ever makes the rule apply."""
    prof, _ = _jar_zones()
    zones = [_dropper_zone(zone_type="WRAP_LABEL_ZONE",
                           permitted_techniques=["wrap_label"])]
    assert wg.is_wrapped_zone(zones[0]) is True
    rep = wg.validate_wrap_alignment(
        wg.build_wrap_geometry(zones, prof),
        _doc_with_placement("z_front", nx=0.15, nw=0.70), zones)
    assert rep["seam_check"]["state"] == wg.APPLICABLE
    assert wg.TEXT_CROSSES_SEAM in rep["codes"]


def test_a_confirmed_cap_wrap_is_a_wrapped_surface_and_is_checked():
    """CAP_WRAP had no wrap record at all before §BH50(f)(6). A confirmed cap
    wrap is a wrapped surface (the contract develops its width by π), so it
    gets its record and the seam check reads it."""
    prof, _ = _jar_zones()
    zones = [_dropper_zone(surface="CAP_WRAP", zone_id="z_cap_wrap",
                           zone_type="CAP_WRAP_ZONE", width=30.0, height=8.0,
                           permitted_techniques=["pad_printing"])]
    geo = wg.build_wrap_geometry(zones, prof)
    assert [w["surface"] for w in geo["wraps"]] == ["CAP_WRAP"]
    assert geo["wrapped_zone_ids"] == ["z_cap_wrap"]
    rep = wg.validate_wrap_alignment(
        geo, _doc_with_placement("z_cap_wrap", nx=0.05, nw=0.70), zones)
    assert rep["seam_check"]["state"] == wg.APPLICABLE
    assert wg.TEXT_CROSSES_SEAM in rep["codes"] and rep["aligned"] is False


def test_a_wrapped_record_without_a_seam_band_is_unmeasured_not_aligned():
    """A zero-width wrap used to read aligned through the ``[0.0, 1.0]``
    default band. It is UNMEASURED now, with the zone named."""
    prof, _ = _jar_zones()
    zones = [_dropper_zone(surface="BODY_WRAP", zone_id="z_wrap",
                           zone_type="WRAP_LABEL_ZONE", width=0.0,
                           permitted_techniques=["wrap_label"])]
    rep = wg.validate_wrap_alignment(
        wg.build_wrap_geometry(zones, prof),
        _doc_with_placement("z_wrap", nx=0.3, nw=0.4), zones)
    assert rep["seam_check"]["state"] == wg.UNMEASURED
    assert "z_wrap" in rep["seam_check"]["reason"]
    assert rep["aligned"] is None and rep["codes"] == []


def test_not_applicable_refuses_to_exist_without_a_reason():
    with pytest.raises(ValueError):
        wg._not_applicable("")
    assert wg._not_applicable("named")["state"] == wg.NOT_APPLICABLE


def test_the_face_records_keep_their_projection_hashes():
    """Placing the seam check moves no recorded identity: the flag is not a
    projection_hash input, and a bottle's face records hash as before."""
    prof = cc.build_inferred_profile("bottle", estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0})
    zones = cc.propose_zones(prof)
    geo = wg.build_wrap_geometry(zones, prof)
    assert sorted(w["surface"] for w in geo["wraps"]) == ["BODY_BACK", "BODY_FRONT"]
    assert all(w["wrapped"] is False for w in geo["wraps"])
    for w in geo["wraps"]:
        assert "wrapped" not in wg._canonical(
            {k: w.get(k) for k in ("zone_id", "surface", "curvature_type", "method",
                                   "usable_width_mm", "usable_height_mm",
                                   "seam_position", "seam_safe_mm", "radius_mm",
                                   "circumference_mm", "arc_deg")})
