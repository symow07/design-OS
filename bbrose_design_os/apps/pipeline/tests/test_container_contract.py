"""Phase 2B-1 — container_profile/1.0 + container_decoration_zones/1.0.

Pure-contract tests (no DB, no provider): schema shape, per-archetype
surfaces, zone containment/margins/overlap, deterministic hashing against the
golden fixtures, §8 photo-safety, §9 hash invalidation, §10 ordered refusals,
§14 legacy compatibility. The endpoint gate + Review Board rows are covered in
test_container_target.py.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from apps.pipeline.services import container_contract as cc

_GOLDEN = json.loads(
    (Path(__file__).parent / "fixtures" / "container_golden.json").read_text())
_ARCHES = ("bottle", "jar", "tube")


def _profile(name):
    g = _GOLDEN[name]
    return cc.build_inferred_profile(g["archetype"], g["variant"],
                                     estimates=g["estimates"])


# --- schema + surfaces -------------------------------------------------------

def test_schema_versions_are_pinned():
    assert cc.PROFILE_SCHEMA == "container_profile/1.0"
    assert cc.ZONES_SCHEMA == "container_decoration_zones/1.0"


@pytest.mark.parametrize("name", _ARCHES)
def test_inferred_profile_shape(name):
    rec = _profile(name)
    assert rec["schema_version"] == cc.PROFILE_SCHEMA
    assert rec["confirmation_state"] == "UNCONFIRMED"
    # every declared field carries a valid source + verification state
    for f in rec["fields"].values():
        assert f["source"] in cc.SOURCES
        assert f["verification"] in cc.VERIFICATION_STATES


@pytest.mark.parametrize("name", _ARCHES)
def test_surfaces_match_golden(name):
    g = _GOLDEN[name]
    assert list(cc.surfaces_for(g["archetype"], g["variant"])) == g["surfaces"]


def test_square_variant_prunes_wrap():
    assert "BODY_WRAP" not in cc.surfaces_for("jar", "square")
    assert "BODY_WRAP" in cc.surfaces_for("jar", "")


# --- photo-safety (§8) -------------------------------------------------------

@pytest.mark.parametrize("name", _ARCHES)
def test_inferred_values_are_never_verified(name):
    rec = _profile(name)
    assert not [n for n, f in rec["fields"].items()
                if f["verification"] == cc.VERIFIED]
    # inferred dimensions do not authorise production geometry
    assert cc.profile_is_confirmable(rec)          # non-empty = blocked


def test_manufacturer_constraints_never_inferred_as_verified():
    rec = _profile("bottle")
    mc = rec["fields"]["manufacturer_constraints"]
    assert mc["verification"] == cc.UNVERIFIED
    assert mc["source"] == cc.SRC_UNKNOWN


# --- proposals + validation (§11/§12) ---------------------------------------

@pytest.mark.parametrize("name", _ARCHES)
def test_proposals_match_golden_and_validate(name):
    g = _GOLDEN[name]
    rec = _profile(name)
    zones = cc.propose_zones(rec)
    assert len(zones) == g["zone_count"]
    assert [z["zone_type"] for z in zones] == g["zone_types"]
    assert [z["parent_surface"] for z in zones] == g["zone_surfaces"]
    assert cc.validate_zone_set(zones, rec) == []          # self-consistent
    # a proposal is never authority
    assert all(z["user_confirmation_state"] == cc.ZONE_PROPOSED for z in zones)


def test_out_of_bounds_zone_rejected():
    rec = cc.merge_user_profile(_profile("jar"),
                                {"body_width_mm": 70.0, "body_depth_mm": 70.0, "body_height_mm": 60.0})
    z = cc.propose_zones(rec)[0]
    z["x"] = 9999
    problems = cc.validate_zone_set([z], rec)
    assert any(p.startswith(cc.ZONE_OUT_OF_BOUNDS) for p in problems)


def test_zone_on_wrong_surface_rejected():
    rec = _profile("tube")
    z = cc.make_zone("z", "FRONT_PRINT_ZONE", "SHOULDER", x=1, y=1,
                     width=5, height=5, curvature_type=cc.FLAT)
    assert any(p.startswith(cc.ZONE_SURFACE_MISMATCH)
               for p in cc.validate_zone(z, rec))          # tube has no SHOULDER


def test_bad_safe_margin_rejected():
    rec = cc.merge_user_profile(_profile("jar"),
                                {"body_width_mm": 70.0, "body_depth_mm": 70.0, "body_height_mm": 60.0})
    z = cc.propose_zones(rec)[0]
    z["safe_margin_mm"] = z["width"]                       # margin swallows zone
    assert any(p.startswith(cc.ZONE_SAFE_MARGIN_INVALID)
               for p in cc.validate_zone(z, rec))


def test_overlap_without_compatible_technique_rejected():
    rec = cc.merge_user_profile(_profile("bottle"),
                                {"body_width_mm": 40.0, "body_depth_mm": 40.0, "body_height_mm": 110.0})
    geom = cc.surface_geometry(rec)["BODY_FRONT"]
    a = cc.make_zone("a", "FRONT_PRINT_ZONE", "BODY_FRONT", x=1, y=1,
                     width=geom["w"] * 0.5, height=geom["h"] * 0.5,
                     curvature_type=geom["curvature"])
    b = cc.make_zone("b", "FRONT_PRINT_ZONE", "BODY_FRONT", x=2, y=2,
                     width=geom["w"] * 0.5, height=geom["h"] * 0.5,
                     curvature_type=geom["curvature"])
    assert any(p.startswith(cc.ZONE_OVERLAP)
               for p in cc.validate_zone_set([a, b], rec))


# --- projection (§6) ---------------------------------------------------------

def test_projection_cylindrical_wrap_keeps_arc_and_reports_radius():
    rec = cc.merge_user_profile(_profile("jar"),
                                {"body_width_mm": 70.0, "body_depth_mm": 70.0, "body_height_mm": 60.0})
    surf = cc.surface_geometry(rec)["BODY_WRAP"]        # circumference width
    zone = {"width": 50.0, "height": 20.0}
    out = cc.projected_dimensions(zone, surf)
    assert out["flat"]["width_mm"] == 50.0               # flat width = arc length
    assert out["projected"]["width_mm"] == 50.0
    # surf["w"] is circumference (π·bw); radius ≈ bw/2 = 35
    assert out["projected"]["wrap_radius_mm"] == pytest.approx(35.0, abs=0.5)


def test_projection_flat_surface_is_one_to_one():
    # a BOUNDED cap top is FLAT (an unbounded cap is UNKNOWN — item 4)
    rec = cc.merge_user_profile(_profile("jar"), {"cap_width_mm": 60.0,
                                                  "cap_height_mm": 20.0})
    surf = cc.surface_geometry(rec)["CAP_TOP"]           # FLAT
    zone = {"width": 12.0, "height": 8.0}
    out = cc.projected_dimensions(zone, surf)
    assert out["projected"] == {"width_mm": 12.0, "height_mm": 8.0}


def test_projection_unknown_curvature_returns_no_dims():
    out = cc.projected_dimensions(
        {"width": 10.0, "height": 5.0}, {"w": 10.0, "curvature": cc.CURVATURE_UNKNOWN})
    assert out["projected"]["width_mm"] is None
    assert out["projected"]["height_mm"] is None


# --- hashing (§9) ------------------------------------------------------------

@pytest.mark.parametrize("name", _ARCHES)
def test_hashes_match_golden(name):
    g = _GOLDEN[name]
    rec = _profile(name)
    zones = cc.propose_zones(rec)
    assert rec["profile_hash"] == g["profile_hash"]
    assert cc.zone_set_hash(zones) == g["zone_set_hash"]
    assert cc.combined_confirmation_hash(rec, zones) == g["combined_hash"]


def test_profile_hash_excludes_timestamps():
    rec = _profile("bottle")
    h = rec["profile_hash"]
    rec2 = copy.deepcopy(rec)
    rec2["confirmed_at"] = "2026-07-23T00:00:00Z"
    rec2["confirmed_by"] = "someone"
    assert cc.profile_hash(rec2) == h                     # metadata is not identity


def test_load_bearing_change_invalidates_hash():
    rec = cc.merge_user_profile(_profile("jar"),
                                {"body_width_mm": 70.0, "body_depth_mm": 70.0, "body_height_mm": 60.0})
    rec2 = cc.merge_user_profile(rec, {"body_width_mm": 80.0})
    assert rec2["profile_hash"] != rec["profile_hash"]


def test_zone_set_hash_is_order_independent():
    rec = _profile("bottle")
    zones = cc.propose_zones(rec)
    assert cc.zone_set_hash(zones) == cc.zone_set_hash(list(reversed(zones)))


# --- ordered refusals (§10) --------------------------------------------------

def test_refusal_order_profile_then_zones_then_curvature():
    rec = _profile("jar")
    zones = cc.propose_zones(rec)
    # 1) inferred dims -> profile blocks even with valid zones
    assert cc.evaluate_confirmation(rec, zones) == cc.PROFILE_CONFIRMATION_REQUIRED
    # 2) profile confirmed, zones still PROPOSED
    rec = cc.merge_user_profile(rec, {"body_width_mm": 70.0,
                                      "body_depth_mm": 70.0,
                                      "body_height_mm": 60.0})
    zones = cc.propose_zones(rec)
    assert cc.evaluate_confirmation(rec, zones) == cc.ZONE_CONFIRMATION_REQUIRED
    # 3) zones user-confirmed but one has UNKNOWN curvature
    zc = copy.deepcopy(zones)
    for z in zc:
        z["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
    zc[0]["curvature_type"] = cc.CURVATURE_UNKNOWN
    assert cc.evaluate_confirmation(rec, zc) == cc.SURFACE_PROJECTION_REVIEW_REQUIRED
    # 4) all zones user-confirmed + valid -> ready
    zc2 = copy.deepcopy(zones)
    for z in zc2:
        z["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
    assert cc.evaluate_confirmation(rec, zc2) is None


def test_empty_zone_set_refuses():
    rec = cc.merge_user_profile(_profile("bottle"),
                                {"body_width_mm": 40.0, "body_depth_mm": 40.0, "body_height_mm": 110.0})
    assert cc.evaluate_confirmation(rec, []) == cc.ZONE_CONFIRMATION_REQUIRED


# --- merge / authority (§3) --------------------------------------------------

def test_merge_promotes_to_user_visual_only():
    rec = cc.merge_user_profile(_profile("bottle"),
                                {"body_width_mm": 40.0, "body_depth_mm": 40.0, "body_height_mm": 110.0})
    f = rec["fields"]["body_width_mm"]
    assert f["verification"] == cc.VERIFIED
    assert f["source"] == cc.SRC_USER_VISUAL          # visual, not manufacturer
    # a user-confirmed visual profile authorises concept reconstruction
    assert f["source"] in cc.CONCEPT_RECONSTRUCTION_SOURCES
    assert f["source"] not in cc.PRODUCTION_GEOMETRY_SOURCES


def test_visual_profile_does_not_forge_manufacturer_constraints():
    rec = cc.merge_user_profile(
        _profile("bottle"),
        {"body_width_mm": 40.0, "manufacturer_constraints": {"wall_mm": 1.2}})
    mc = rec["fields"]["manufacturer_constraints"]
    assert mc["verification"] == cc.UNVERIFIED         # never VERIFIED via visual


def test_bh70_a_record_says_which_fields_its_form_does_not_have():
    """§BH70(1), item 17 of the list he was sent: "The records are shaped like a bottle. Every product record has neck,
    shoulder and cap fields" — a compact's record held a neck and a cap's sizes as MISSING, fields owed and never to
    come. A neck and its shoulder are a bottle's; a cap's sizes a form's with a cap (his §BH61(b)). The record names
    the fields its form does not have, OUTSIDE the profile hash — his §AH4 (LIVE) holds a jar's hashes byte-identical,
    "No jar in flight is disturbed" — so every hash stays as it was and the record still validates."""
    from apps.pipeline.targets.container import archetypes as A
    neck = {"neck_width_mm", "neck_ratio", "shoulder_type", "shoulder_height_mm"}
    caps = {"cap_width_mm", "cap_depth_mm", "cap_height_mm"}
    for form in A.ARCHETYPES:
        record = cc.build_inferred_profile(form)
        want = (set() if "neck_ratio" in A.proportions_of(form) else neck) | \
               (set() if A.VOCABULARY[form]["has_cap_dimensions"] else caps)
        assert record["not_applying"] == sorted(want), (form, record["not_applying"])
        assert record["profile_hash"] == cc.profile_hash({k: v for k, v in record.items() if k != "not_applying"})
        assert cc.validate_profile(record) == [], form
    assert cc.fields_not_applying("bottle") == frozenset()
    assert cc.fields_not_applying("compact") == neck | caps
    assert cc.fields_not_applying("not-a-form") == frozenset()


def test_bh70_the_stage_hand_off_carries_no_cap_for_a_form_without_one():
    """§BH70(1), item 17: the hand-off between a Complete Product's stages carried "cap dimensions" for every form. A
    compact's says they do not apply; a bottle's carries its cap's sizes as before."""
    from types import SimpleNamespace

    from apps.pipeline.targets import composite

    def hand_off(form):
        output = SimpleNamespace(id=1, design_preview=None, spec_sheet={
            "backend": "container", "container_profile/1.0": cc.build_inferred_profile(form)})
        # the stage's source task, read as every door reads it: by its current output (his test blocker on 124, (4))
        source = SimpleNamespace(id=2, design_target="product_container", current_output=lambda: output)
        return composite.build_stage_handoff(SimpleNamespace(id=1), source,
                                             SimpleNamespace(id=3, design_target="packaging"))
    assert hand_off("compact")["cap_dimensions_mm"] == cc.NOT_APPLICABLE
    assert set(hand_off("bottle")["cap_dimensions_mm"]) == {"width", "depth", "height"}


def test_his_yes_a_tubes_front_is_proposed_from_its_concepts_map():
    """His yes of 2026-09-30 (transcribed at 5d23649): 117's print area re-proposed from his concept, which prints edge to
    edge where his confirmed front was 35 x 99 mm in the middle. A tube's FRONT_PRINT_ZONE is laid over the parts its
    concept's map prints (never its fields, its cap or a window), in the front face's millimetres, its foot above the
    cap; with no map, and for any other form, the proposal is the contract's, byte for byte; and a zone the map
    proposed, carried unchanged after the depth moved, is the proposal — never named as proposed for other sizes."""
    import math
    rec = cc.build_inferred_profile("tube", "standard", {"body_width_mm": 50.0, "body_height_mm": 180.0,
                                                          "body_depth_mm": 20.0})
    parts = [{"kind": "field", "box": [0.03, 0.0, 0.97, 0.35]}, {"kind": "closure", "box": [0.08, 0.84, 0.92, 1.0]},
             {"kind": "rule", "box": [0.116, 0.347, 0.94, 0.355]}, {"kind": "mark", "box": [0.151, 0.217, 0.863, 0.299]},
             {"kind": "type", "box": [0.335, 0.814, 0.669, 0.837]}]
    zones = cc.propose_zones_with_map(rec, parts, cap_top_share=0.8323)
    front = next(z for z in zones if z["zone_type"] == "FRONT_PRINT_ZONE")
    w = round(math.pi / 2.0 * 50.0, 2)
    assert (front["x"], front["y"]) == (round(0.116 * w, 1), round(0.217 * 180.0, 1)), front
    assert front["width"] == round((0.94 - 0.116) * w, 1) and front["height"] == round((0.8323 - 0.217) * 180.0, 1)
    assert "map" in front["proposed_from"]
    assert cc.validate_zone_set(zones, rec) == []
    plain = cc.augment_code_zones(rec, cc.propose_zones(rec))
    assert cc.propose_zones_with_map(rec, []) == plain
    bottle = cc.build_inferred_profile("bottle", "cylindrical", {"body_width_mm": 40.0, "body_height_mm": 110.0})
    # [his go of 2026-10-02 (a18911a): the map path for every new design, a wand vial among them — a bottle drawn
    # standing has its front proposed from its map since; the dropper and a face form keep the contract's, pinned in
    # test_his_go_a_wand_vials_front_is_proposed_from_its_concepts_map]
    assert cc.propose_zones_with_map(bottle, parts) != cc.augment_code_zones(bottle, cc.propose_zones(bottle))
    deeper = cc.build_inferred_profile("tube", "standard", {"body_width_mm": 50.0, "body_height_mm": 180.0,
                                                             "body_depth_mm": 50.0})
    block = cc.zone_set_record(zones, rec, confirmation_state="PROPOSED")
    carried = cc.propose_zones_with_map(deeper, parts, cap_top_share=0.8323)
    assert cc.zone_profile_divergence(block, carried, deeper, proposal=carried) == []
    assert any(cc.ZONE_PROPOSED_FOR_OTHER_SIZES in f for f in cc.zone_profile_divergence(block, carried, deeper))


def test_his_go_a_wand_vials_front_is_proposed_from_its_concepts_map():
    """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design, for a wand vial and a carton". A wand vial's FRONT_PRINT_ZONE is laid over the parts its
    concept's map prints, as a tube's is — kept below its cap, which stands on top — and so is any form drawn standing
    with a front; a face form and the dropper keep their own proposals, byte for byte."""
    rec = cc.build_inferred_profile("mascara", "square", {"body_width_mm": 16.0, "body_height_mm": 80.0})
    parts = [{"kind": "closure", "box": [0.05, 0.0, 0.95, 0.35]}, {"kind": "field", "box": [0.0, 0.35, 1.0, 1.0]},
             {"kind": "type", "box": [0.1, 0.47, 0.92, 0.61]}, {"kind": "rule", "box": [0.2, 0.64, 0.8, 0.65]},
             {"kind": "type", "box": [0.19, 0.68, 0.8, 0.70]}]
    assert cc.map_zone_form(rec)
    zones = cc.propose_zones_with_map(rec, parts, body_top_share=0.35)
    front = next(z for z in zones if z["zone_type"] == "FRONT_PRINT_ZONE")
    assert (front["x"], front["y"], front["width"], front["height"]) == (
        round(0.1 * 16.0, 1), round(0.47 * 80.0, 1), round(0.82 * 16.0, 1), round(0.23 * 80.0, 1)), front
    assert "map" in front["proposed_from"] and cc.validate_zone_set(zones, rec) == []
    on_the_cap = cc.propose_zones_with_map(rec, parts + [{"kind": "mark", "box": [0.2, 0.1, 0.8, 0.15]}],
                                           body_top_share=0.35)
    assert next(z for z in on_the_cap if z["zone_type"] == "FRONT_PRINT_ZONE")["y"] == round(0.35 * 80.0, 1)
    dropper = cc.build_inferred_profile("bottle", "cylindrical", {"body_width_mm": 40.0, "body_height_mm": 110.0,
                                                                   "cap_type": "dropper"})
    compact = cc.build_inferred_profile("compact", "round", {"body_width_mm": 60.0, "body_height_mm": 14.0})
    for kept in (dropper, compact):
        assert not cc.map_zone_form(kept)
        assert cc.propose_zones_with_map(kept, parts) == cc.augment_code_zones(kept, cc.propose_zones(kept))



# [His test blocker on design 122 at the shape step, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md): "I set height 120 mm,
# diameter 35 mm, ticked the front, back and batch-code print areas and pressed 'Confirm the shape and print areas'. The
# page came back at the shape step ... Find why, fix it for every design".] MEASURED: at 120 x 35 mm the shape step's
# own proposal put 122's front at 55.0 mm on a 54.98 mm face — its size rounded up past the surface the confirm door
# checks it against — and the door refused it and handed the same area back: no confirm at those sizes could pass.

#: the extent of a concept that prints edge to edge (122's 149, its engraving), as its map's parts name it
_EDGE_TO_EDGE = [{"kind": "motif", "name": "an all-over engraving", "box": [0.0, 0.0, 1.0, 1.0]}]


def _sizes_of(archetype):
    """Each of a form's sizes the shape step admits worth trying: its least, its nominal and its greatest, and the odd
    ones a person types (122's 35 mm round) — (width, depth, height) in millimetres."""
    from apps.pipeline.targets.container import archetypes as A
    ranges, nominal = A.ranges_of(archetype), A.nominal_of(archetype)
    out = []
    for pick in ("min", "nominal", "max", 35.0, 33.3, 47.7):
        size = {}
        for key in ("width_mm", "depth_mm", "height_mm"):
            if key not in ranges:
                continue
            lo, hi = ranges[key]
            if pick == "min":
                size[key] = lo
            elif pick == "max":
                size[key] = hi
            elif pick == "nominal":
                size[key] = (nominal or {}).get(key)
            else:
                size[key] = pick if lo <= pick <= hi else lo
        out.append(size)
    return out


def test_his_shape_step_122_every_proposed_area_lies_inside_its_surface_at_every_size():
    """For every form and every variant, at the sizes a person can set, every print area the shape step proposes — the
    contract's own and the concept's map's, an edge-to-edge concept's among them — lies inside the surface the confirm
    door checks it against, and a back grown with its front overlaps no other area on its surface (a slim form's code
    place stands on its back), so a confirm at any size a form admits can pass."""
    from apps.pipeline.targets.container import archetypes as A
    seen = 0
    for archetype in A.ARCHETYPES:
        for variant in [v[0] for v in A.variants_of(archetype)] or [""]:
            for size in _sizes_of(archetype):
                estimates = {"body_" + k: v for k, v in size.items() if v is not None}
                record = cc.build_inferred_profile(archetype, variant, estimates=estimates)
                for zones in (cc.augment_code_zones(record, cc.propose_zones(record)),
                              cc.propose_zones_with_map(record, _EDGE_TO_EDGE)):
                    out = [p for p in cc.validate_zone_set(zones, record)
                           if p.startswith((cc.ZONE_OUT_OF_BOUNDS, cc.ZONE_OVERLAP))]
                    assert out == [], (archetype, variant, size, out)
                    seen += len(zones)
    assert seen > 200, seen


def test_his_shape_step_122_at_his_sizes_the_front_lies_on_its_face_and_the_back_grows_with_it():
    """122 at his 120 x 35 mm, its concept printing edge to edge: its front is the face's own width to the tenth
    inside it (54.9 mm on 54.98, never 55.0) and the back — "the back carries the most text and should grow with the
    tube" — takes the front's extent on its own surface, where it stood at 38.5 x 66.0 mm."""
    record = cc.build_inferred_profile("tube", "standard", estimates={"body_height_mm": 120.0, "body_width_mm": 35.0})
    zones = {z["zone_id"]: z for z in cc.propose_zones_with_map(record, _EDGE_TO_EDGE)}
    face = cc.surface_geometry(record)["BODY_FRONT"]
    front, back = zones["z_front"], zones["z_back"]
    assert front["width"] == 54.9 and front["x"] + front["width"] <= face["w"], (front, face)
    assert (back["x"], back["y"], back["width"], back["height"]) == (front["x"], front["y"], front["width"],
                                                                     front["height"]), (back, front)
    assert back["proposed_from"] == "the front's extent, on the back: the back carries the most text"
    assert [p for p in cc.validate_zone_set(list(zones.values()), record) if p.startswith(cc.ZONE_OUT_OF_BOUNDS)] == []


def test_his_shape_step_122_an_area_rounded_past_its_surface_is_held_inside_and_nothing_else_moves():
    record = cc.build_inferred_profile("tube", "standard", estimates={"body_height_mm": 120.0, "body_width_mm": 35.0})
    face = cc.surface_geometry(record)["BODY_FRONT"]
    over = cc.make_zone("z_front", "FRONT_PRINT_ZONE", "BODY_FRONT", x=0.0, y=0.0, width=55.0, height=99.9,
                        curvature_type=face["curvature"])
    wide = cc.make_zone("z_wide", "FRONT_PRINT_ZONE", "BODY_FRONT", x=0.0, y=0.0, width=70.0, height=99.9,
                        curvature_type=face["curvature"])
    held, untouched = cc.held_inside(record, [over, wide])
    assert held["width"] == 54.9 and held["height"] == 99.9
    assert untouched == wide          # far past its surface: a real refusal, never trimmed away
