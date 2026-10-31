"""P1 provisional pilot — contract, authority law, rejection rules and the
V3 owner-revision validation list (§22).

Mask-pipeline tests run real Blender at small resolution; everything else
guards the deterministic geometry/contract layer.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import mesh_diagnostics as md
from apps.pipeline.services import p1_pilot_geometry as p1

INTAKE = os.path.join("docs", "visual_quality", "rbv", "owner_inputs",
                      "2026-08-04", "normalized_measurements.json")
CLOSEOUT = os.path.join("docs", "visual_quality", "rbv", "owner_inputs",
                        "2026-08-27", "a1_closeout.json")
ACCEPTED_DIMS = {
    "total_assembled_height_mm": 114.3,
    "bottle_height_mm": 91.6,
    "body_diameter_mm": 37.4,
    "base_diameter_mm": 37.35,
    "neck_outside_diameter_mm": 15.6,
    "opening_inside_diameter_mm": 10.3,
    "thread_outside_diameter_mm": 17.4,
    "collar_outside_diameter_mm": 21.4,
    "collar_height_mm": 16.5,
    "bulb_max_diameter_mm": 10.57,
    "bulb_height_mm": 19.2,
    "pipette_length_mm": 88.74,
    "pipette_outside_diameter_mm": 6.9,
    "pipette_tip_to_base_mm": 9.16,
}


class P1ContractTests(SimpleTestCase):
    def test_contract_builds_and_passes_consistency(self):
        c = p1.build_p1_contract()
        assert c["schema"] == "p1_provisional_geometry/1.0"
        assert c["revision"] == "V4"
        assert c["consistency_status"] == "PASS"
        assert c["geometry_class"] == "AXISYMMETRIC_REVOLUTION"

    def test_accepted_owner_dimensions_unchanged(self):
        for key, value in ACCEPTED_DIMS.items():
            assert p1.OWNER[key] == value, key

    def test_accuracy_status_recorded_exactly(self):
        status = p1.build_p1_contract()["accuracy_status"]
        assert status["P1_GEOMETRY_AUTHORITY"] == \
            "PROVISIONAL_OWNER_MEASURED_PLUS_INFERRED"
        assert status["P1_MATERIAL_AUTHORITY"] == \
            "OWNER_CONFIRMED_EXTERNAL_MATERIALS_PLUS_VISUALIZATION_" \
            "PARAMETERS"
        assert status["P1_INTERNAL_GLASS_AUTHORITY"] == \
            "VISUALIZATION_ONLY_GEOMETRY"
        assert status["P1_MANUFACTURING_AUTHORITY"] == "NOT_ESTABLISHED"
        assert status["P1_OWNER_APPROVAL"] == "PENDING_VISUAL_REVIEW"
        assert status["GATE_2"] == "BLOCKED"
        assert status["PACKAGING_PRODUCTION"] == "NOT_STARTED"

    def test_derived_values_match_hand_calculation(self):
        d = {k: v["value"] for k, v in p1.derived_values().items()}
        assert d["neck_base_z_mm"] == 73.49
        assert d["collar_top_z_mm"] == 95.1
        assert d["collar_bottom_z_mm"] == 78.6
        assert d["pipette_top_z_mm"] == 97.9
        assert d["glass_wall_neck_mm"] == 2.65

    def test_every_non_owner_value_carries_confidence_and_authority(self):
        for name, rec in p1.derived_values().items():
            assert rec["authority"] in p1.AUTHORITY_CLASSES, name
            assert rec["authority"] not in ("OWNER_MEASURED",
                                            "OWNER_CONFIRMED"), name
            assert rec.get("confidence") in p1.CONFIDENCES, name

    def test_shoulder_control_points_are_visual_estimates(self):
        c = p1.build_p1_contract()
        for pt in (c["shoulder_control_points_v3"]
                   + c["bulb_control_points_v3"]
                   + c["shoulder_control_points_v4"]
                   + c["bulb_control_points_v4"]):
            assert pt["authority"] == "VISUAL_ESTIMATE_FROM_OWNER_PHOTO"
            assert pt["confidence"] in ("LOW", "MEDIUM")
            assert pt["note"] == "NOT_MANUFACTURING_AUTHORITATIVE"

    def test_owner_fields_pin_the_intake_record(self):
        intake = json.load(open(INTAKE))["products"]["P1"]["fields"]
        pins = {
            "total_assembled_height_mm": "total_assembled_height",
            "bottle_height_mm": "bottle_height_without_dropper",
            "body_diameter_mm": "maximum_body_diameter",
            "base_diameter_mm": "base_diameter",
            "neck_outside_diameter_mm": "neck_outside_diameter",
            "opening_inside_diameter_mm": "bottle_opening_inside_diameter",
            "collar_outside_diameter_mm": "collar_outside_diameter",
            "collar_height_mm": "collar_height",
            "bulb_max_diameter_mm": "bulb_maximum_diameter",
            "bulb_height_mm": "bulb_visible_height",
            "pipette_length_mm": "pipette_total_length",
        }
        for ours, theirs in pins.items():
            assert p1.OWNER[ours] == intake[theirs]["value"], ours

    def test_owner_confirmed_materials_recorded(self):
        m = p1.MATERIALS
        assert m["authority"] == "OWNER_CONFIRMED_MATERIAL_EVIDENCE"
        assert m["bottle"]["transparency"] == "TRANSPARENT_NOT_OPAQUE"
        assert m["bottle"]["finish"] == "MATTE_FROSTED_EXTERIOR"
        assert m["bulb"] == {"material": "PLASTIC", "finish": "GLOSSY",
                             "colour": "ORANGE", "transparency": "OPAQUE"}
        assert m["pipette"]["material"] == "CLEAR_GLASS"


class A1CloseoutTests(SimpleTestCase):
    """The owner's A1 rulings of 2026-08-27, pinned so they cannot drift.

    Two of these rulings REVERSED an earlier ruling in the same sitting, and
    the reversals are the reason the pins exist: 66 mm was retired and then
    restored, and 18.11 mm was declared a diameter and then re-declared a
    height. Anything that re-retires 66 or re-reads 18.11 as a diameter is a
    regression against a typed owner ruling, not a refinement.
    """

    def test_both_shoulder_landmarks_survive_as_distinct(self):
        # A1/A2: 66 and 69 are two separately measured caliper landmarks.
        # The owner reversed the retirement of 66 on 2026-08-27.
        assert p1.OWNER["straight_wall_end_mm"] == 66.0
        assert p1.OWNER["shoulder_landmark_69_mm"] == 69.0
        assert (p1.OWNER["straight_wall_end_mm"]
                < p1.OWNER["shoulder_landmark_69_mm"])
        assert not p1.validate_consistency()

    def test_neck_height_is_a_height_not_a_diameter(self):
        # A3: 18.11 mm is a HEIGHT (shoulder/neck junction -> glass mouth).
        # It cannot be a misfiled diameter: both diameter fields are
        # separately populated with different values.
        assert p1.OWNER["neck_height_mm"] == 18.11
        assert p1.OWNER["neck_outside_diameter_mm"] == 15.6
        assert p1.OWNER["thread_outside_diameter_mm"] == 17.4
        assert p1.OWNER["neck_height_mm"] not in (
            p1.OWNER["neck_outside_diameter_mm"],
            p1.OWNER["thread_outside_diameter_mm"])
        # consumed downstream as an axial length
        d = {k: v["value"] for k, v in p1.derived_values().items()}
        assert d["neck_base_z_mm"] == round(
            p1.OWNER["bottle_height_mm"] - p1.OWNER["neck_height_mm"], 2)

    def test_four_assumptions_are_owner_resolved(self):
        a = p1.build_p1_contract()["provisional_assumptions"]
        assert set(a) == {"A1", "A2", "A3", "A4"}
        for key, text in a.items():
            assert "2026-08-27" in text, key
            assert text.startswith(("RESOLVED", "CONFIRMED")), key
            assert "pending" not in text.lower(), key

    def test_neck_finish_is_owner_confirmed_outside_the_derived_layer(self):
        nf = p1.build_p1_contract()["owner_confirmed_neck_finish"]
        assert nf["authority"] == "OWNER_CONFIRMED"
        assert nf["confirmed_on"] == "2026-08-27"
        assert nf["classification"].startswith("GL18")
        # a CLASS, never a supplier part
        assert "NOT an exact-product" in nf["scope_limit"]
        # the owner ruled on the finish CLASS, not on the pitch field, which
        # stays owner-UNKNOWN with a non-owner authority
        d = p1.derived_values()
        assert d["thread_pitch_mm"]["authority"] == \
            "ONLINE_ANALOGOUS_REFERENCE"

    def test_derived_layer_never_carries_owner_authority(self):
        # the guard that caught the first attempt at the ruling above: the
        # evidence beneath an owner ruling must not inherit its authority
        corr = p1.derived_values()["neck_finish_corroboration"]
        assert corr["authority"] == "ONLINE_ANALOGOUS_REFERENCE"
        assert corr["confidence"] == "MEDIUM"
        assert "SUPERSEDED AS AUTHORITY" in corr["provenance"]

    def test_closeout_record_exists_and_the_code_agrees_with_it(self):
        # the owner's typed rulings live in the record; the code must not
        # drift from it, and the record must not quietly vanish
        assert os.path.exists(CLOSEOUT), CLOSEOUT
        rec = json.load(open(CLOSEOUT))
        assert rec["record_type"] == "rbv_a1_closeout/1.0"
        r = rec["owner_rulings"]
        assert set(r) >= {"R1_canonical_path", "Q1_66mm", "Q2_69mm",
                          "Q3_18_11mm", "Q4_105mm", "side_view",
                          "scale_question", "a1_closure"}
        # the reversals are recorded, not smoothed over
        assert "history" in r["Q1_66mm"]
        assert rec["corrections_to_derived_claims"]
        # the prohibition the owner typed: no "neck height 15.6" entry
        assert "15.6" in r["Q3_18_11mm"]["prohibition"]
        assert not any(
            v["value"] == 15.6 and "height" in k
            for k, v in p1.derived_values().items())

    def test_photography_is_corroborating_never_measured(self):
        status = p1.build_p1_contract()["accuracy_status"]
        conf = status["P1_VISUAL_COMPARISON_CONFIDENCE"]
        assert "CORROBORATING_ONLY" in conf
        assert "DERIVED_INDICATIVE" in conf
        assert "OWNER_MEASURED" not in conf
        # A1 closing never touched these
        assert status["P1_OWNER_APPROVAL"] == "PENDING_VISUAL_REVIEW"
        assert status["GATE_2"] == "BLOCKED"
        assert status["P1_MANUFACTURING_AUTHORITY"] == "NOT_ESTABLISHED"


class P1RejectionRuleTests(SimpleTestCase):
    def _with(self, **overrides):
        patched = dict(p1.OWNER, **overrides)
        return mock.patch.object(p1, "OWNER", patched)

    def test_pipette_through_base_rejected(self):
        with self._with(pipette_tip_to_base_mm=1.5):
            assert any("penetrates" in f for f in p1.validate_consistency())

    def test_collar_shoulder_collision_rejected(self):
        with self._with(collar_height_mm=30.0):
            assert any("collision" in f for f in p1.validate_consistency())

    def test_floating_collar_rejected(self):
        with self._with(bulb_height_mm=5.0):
            assert any("floats" in f for f in p1.validate_consistency())

    def test_pipette_wider_than_opening_rejected(self):
        with self._with(pipette_outside_diameter_mm=11.0):
            assert any("negative clearance" in f
                       for f in p1.validate_consistency())


class P1RevisionReproductionTests(SimpleTestCase):
    """Owner review decisions reference exact mesh identities — the
    historical V1/V2 profiles must stay reproducible forever."""

    def test_v1_identities_reproduced_exactly(self):
        _, meshes, _ = p1.build_p1_assembly("V1")
        assert {n: m["mesh_identity"] for n, m in meshes.items()} == \
            p1.V1_MESH_IDENTITIES

    def test_v2_identities_reproduced_exactly(self):
        _, meshes, _ = p1.build_p1_assembly("V2")
        assert {n: m["mesh_identity"] for n, m in meshes.items()} == \
            p1.V2_MESH_IDENTITIES

    def test_v3_identities_reproduced_exactly(self):
        _, meshes, _ = p1.build_p1_assembly("V3")
        assert {n: m["mesh_identity"] for n, m in meshes.items()} == \
            p1.V3_MESH_IDENTITIES

    def test_v3_glass_solid_still_reproducible(self):
        assert p1.build_p1_glass_solid("V3")["mesh_identity"] == \
            "e3bf976cabe0fcc5"

    def test_v4_identities_deterministic_and_new(self):
        _, m1, _ = p1.build_p1_assembly("V4")
        _, m2, _ = p1.build_p1_assembly("V4")
        ids1 = {n: m["mesh_identity"] for n, m in m1.items()}
        assert ids1 == {n: m["mesh_identity"] for n, m in m2.items()}
        assert ids1["body"] != p1.V3_MESH_IDENTITIES["body"]
        assert ids1["bulb"] != p1.V3_MESH_IDENTITIES["bulb"]
        # collar geometry retained (owner: keep accepted dimensions)
        assert ids1["collar"] == p1.V3_MESH_IDENTITIES["collar"]


class P1V3ShoulderTests(SimpleTestCase):
    ZS = np.linspace(66.0 + 1e-6, 73.49 - 1e-6, 800)

    def _r(self, z):
        return p1.shoulder_radius(float(z), p1.REVISION)

    def test_ends_exactly_on_owner_values(self):
        assert p1.shoulder_radius(66.0, p1.REVISION) == 18.7
        assert p1.shoulder_radius(73.49, p1.REVISION) == 7.8

    def test_first_and_second_derivative_continuity(self):
        # first-derivative continuity holds EVERYWHERE incl. the wall and
        # neck junctions (clamped horizontal tangents = G1 tangency);
        # second-derivative continuity holds across every interior spline
        # knot (a line-to-curve tangency has a curvature step by nature —
        # same as any real moulded-glass wall/arc junction)
        h = 0.005
        zs_all = np.arange(65.8, 73.7, 0.01)
        d1 = np.array([(self._r(z + h) - self._r(z - h)) / (2 * h)
                       for z in zs_all])
        # slope steps must stay consistent with the bounded curvature
        # (|d2| < ~30 → |Δd1| ≈ d2·Δz < 0.45); a true kink jumps by >>1
        assert np.max(np.abs(np.diff(d1))) < 0.45
        zs_in = np.arange(66.05, 73.44, 0.01)
        d2 = np.array([(self._r(z + h) - 2 * self._r(z)
                        + self._r(z - h)) / (h * h) for z in zs_in])
        assert np.max(np.abs(np.diff(d2))) < 3.5      # no curvature jump

    def test_no_ridge_at_body_junction_and_no_kink_at_neck(self):
        h = 0.02
        for z in (66.0, 73.49):
            d1 = (self._r(z + h) - self._r(z - h)) / (2 * h)
            assert abs(d1) < 0.35, z    # clamped ~horizontal tangents

    def test_no_straight_diagonal_segment(self):
        # a straight diagonal = sustained |d1|>0.3 with |d2|~0
        h = 0.01
        run = 0
        for z in np.arange(66.3, 73.3, 0.05):
            d1 = (self._r(z + h) - self._r(z - h)) / (2 * h)
            d2 = (self._r(z + h) - 2 * self._r(z) + self._r(z - h)) \
                / (h * h)
            run = run + 1 if (abs(d1) > 0.3 and abs(d2) < 0.02) else 0
            assert run * 0.05 <= 1.0, f"straight segment at z≈{z}"

    def test_no_flat_shelf_inside_the_shoulder(self):
        # sustained near-zero slope INSIDE the curve = shelf
        h = 0.01
        run = 0
        for z in np.arange(67.2, 73.1, 0.05):
            d1 = (self._r(z + h) - self._r(z - h)) / (2 * h)
            run = run + 1 if abs(d1) < 0.05 else 0
            assert run * 0.05 <= 0.8, f"flat shelf at z≈{z}"

    def test_fuller_than_rejected_v2_and_monotone(self):
        rs = np.array([self._r(z) for z in self.ZS])
        # V4 must narrow EARLIER than the rejected V3 (owner: no
        # swollen upper shoulder) while staying fuller than flat V2
        assert p1.shoulder_radius(67.0, "V4") < \
            p1.shoulder_radius(67.0, "V3")
        assert p1.shoulder_radius(69.0, "V4") < \
            p1.shoulder_radius(69.0, "V3")
        assert np.all(np.diff(rs) <= 1e-6)
        assert rs.max() <= 18.7 + 1e-6 and rs.min() >= 7.8 - 1e-6


class P1V3BulbTests(SimpleTestCase):
    def test_max_diameter_and_height_unchanged(self):
        _, meshes, _ = p1.build_p1_assembly(p1.REVISION)
        v = meshes["bulb"]["vertices"]
        assert abs(2 * float(abs(v[:, 0]).max()) - 10.57) < 0.06
        assert abs((float(v[:, 2].max()) - float(v[:, 2].min())) - 19.2) \
            < 1e-6
        assert abs(float(v[:, 2].max()) - 114.3) < 1e-6

    def test_apex_rounded_no_conical_nipple(self):
        # rounded dome keeps substantial radius near the apex; the
        # rejected V1 cone collapsed to ~1.5 mm at 1 mm below the top
        assert p1.bulb_radius(18.2, p1.REVISION) > 2.0
        assert p1.bulb_radius(18.2, p1.REVISION) > \
            p1.bulb_radius(18.2, "V1") + 0.5
        # slope keeps increasing toward the apex (dome, not cone)
        h = 0.05
        s1 = (p1.bulb_radius(17.0 + h, p1.REVISION)
              - p1.bulb_radius(17.0 - h, p1.REVISION)) / (2 * h)
        s2 = (p1.bulb_radius(18.8 + h, p1.REVISION)
              - p1.bulb_radius(18.8 - h, p1.REVISION)) / (2 * h)
        assert s2 < s1 < 0

    def test_lower_transition_narrowed_and_continuous(self):
        # V3 owner revision: subtle narrowing where the bulb enters the
        # collar (V2 was a straight cylinder at max radius)
        assert p1.bulb_radius(0.0, p1.REVISION) < 5.285 - 0.15
        h = 0.02
        zs = np.arange(0.1, 19.0, 0.05)
        d1 = np.array([(p1.bulb_radius(z + h, p1.REVISION)
                        - p1.bulb_radius(z - h, p1.REVISION)) / (2 * h)
                       for z in zs])
        assert np.max(np.abs(np.diff(d1))) < 0.4   # no discontinuity

    def test_v4_sides_are_near_vertical_over_most_of_the_height(self):
        # owner V4 requirement: fuller body, nearly vertical sides —
        # the rejected V3 egg tapered continuously
        zs = np.arange(1.0, 19.2, 0.05)
        near_max = sum(1 for z in zs
                       if p1.bulb_radius(z, "V4") >= 5.285 - 0.15)
        v3_near_max = sum(1 for z in zs
                          if p1.bulb_radius(z, "V3") >= 5.285 - 0.15)
        assert near_max * 0.05 > 9.0        # >9 mm of ~full width
        assert near_max > v3_near_max


class P1V3GlassSolidTests(SimpleTestCase):
    def test_closed_manifold_valid_normals_deterministic(self):
        g1 = p1.build_p1_glass_solid(p1.REVISION)
        g2 = p1.build_p1_glass_solid(p1.REVISION)
        assert g1["mesh_identity"] == g2["mesh_identity"]
        diag = md.diagnose_mesh(g1["vertices"], g1["faces"])
        assert diag["codes"] == []
        assert diag["non_manifold_edges"] == 0
        assert diag["components"] == 1
        assert diag["signed_volume_mm3"] > 0
        assert g1["authority"] == "VISUALIZATION_ONLY_GEOMETRY"

    def test_inner_outer_surfaces_do_not_intersect(self):
        g = p1.build_p1_glass_solid(p1.REVISION)
        inner = {round(z, 2): r for z, r in g["inner_points"]}
        for z, r_inner in inner.items():
            if z <= 3.0 or z >= 91.6:
                continue
            if z <= 66.0:
                r_outer = 18.7 if z > 6.0 else None
            else:
                r_outer = p1.shoulder_radius(z, p1.REVISION)
            if r_outer is not None:
                assert r_outer - r_inner > 0.5, z

    def test_base_and_neck_walls_positive(self):
        assert p1.BOTTOM_GLASS_THICKNESS_MM > 0
        assert p1.GLASS_WALL_NECK_MM > 0
        assert p1.GLASS_WALL_BODY_MM > 0


@unittest.skipUnless(os.path.exists(os.path.expanduser(
    "~/Applications/Blender-4.5.12-LTS.app/Contents/MacOS/Blender")),
    "pinned Blender runtime not installed")
class P1MaskPipelineTests(SimpleTestCase):
    """Owner-mandated mask authority: unlit alpha, deterministic, no
    highlight holes, lighting-independent by construction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.pipeline.services import p1_v3_evidence as ev
        cls.ev = ev
        cls.td = tempfile.mkdtemp(prefix="p1mask")
        cls.addClassCleanup(shutil.rmtree, cls.td, True)
        _, meshes, cls.facts = p1.build_p1_assembly(p1.REVISION)
        out = {"front": os.path.join(cls.td, "front_a.png")}
        ev.render_masks(meshes, out, resolution=(400, 550), samples=8)
        ev.render_masks(meshes,
                        {"front": os.path.join(cls.td, "front_b.png")},
                        resolution=(400, 550), samples=8)
        cls.mask_a = ev.load_mask(os.path.join(cls.td, "front_a.png"))
        cls.mask_b = ev.load_mask(os.path.join(cls.td, "front_b.png"))

    def test_mask_hashes_deterministic(self):
        assert self.ev.mask_hash(self.mask_a) == \
            self.ev.mask_hash(self.mask_b)

    def test_mask_has_no_internal_highlight_holes(self):
        mm_per_px = 114.3 * 1.12 / 550
        metrics = self.ev.mask_metrics(self.mask_a, mm_per_px)
        assert metrics["internal_hole_pixels"] == 0

    def test_mask_dimensions_match_geometry_bounds(self):
        mm_per_px = 114.3 * 1.12 / 550
        metrics = self.ev.mask_metrics(self.mask_a, mm_per_px)
        assert abs(metrics["height_mm"] - 114.3) < 0.8
        assert abs(metrics["width_mm"] - 37.4) < 0.8
        assert metrics["cx_offset_fraction"] < 0.01

    def test_mask_scene_is_lighting_independent_by_construction(self):
        # structural guarantee: the mask scene creates NO lights and uses
        # a pure emission shader on transparent film
        src = open(self.ev.MASK_SCRIPT).read()
        assert "lights.new" not in src
        assert "film_transparent = True" in src
        assert "ShaderNodeEmission" in src
