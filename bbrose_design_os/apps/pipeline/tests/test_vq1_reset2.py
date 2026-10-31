"""VQ-1-RESET-2 §17 — two-authority geometry, normalized concept envelope,
independent visualizer loop and the supplier-request boundary."""
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_reset2 as r2
from apps.pipeline.services import visual_inspector as vi

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R2 = os.path.join(DOCS, "vq1_reset2")
PACKET = json.load(open(os.path.join(R2, "vq1_reset2_visual_review.json")))
ENV = json.load(open(os.path.join(R2, "concept_visual_envelope.json")))
LOOP = json.load(open(os.path.join(R2, "visual_correction_loop.json")))


class TestTwoAuthorityModel:
    def test_concept_and_production_authorities_are_separate(self):
        a = r2.geometry_authority(False)
        assert a["schema_version"] == "container_geometry_authority/1.0"
        concept = a["modes"][r2.CONCEPT_VISUAL]
        prod = a["modes"][r2.PRODUCTION]
        assert concept["state"] == "AUTHORIZED"
        assert prod["state"] == "NOT_AVAILABLE"
        assert r2.VQ_PRODUCTION_GEOMETRY_EVIDENCE_REQUIRED in \
            prod["blocked_by"]
        for claim in ("manufacturable", "supplier-confirmed",
                      "production dimension", "tooling dimension",
                      "verified closure construction"):
            assert claim in concept["prohibited_claims"]

    def test_packet_never_claims_manufacturable(self):
        assert PACKET["production_geometry"] == "BLOCKED"
        assert PACKET["approved_physical_dimensions"] == "NONE"
        assert PACKET["manufacturable_claim"] is False

    def test_visible_semantic_only_and_forbidden_classifications(self):
        a = r2.geometry_authority()
        assert a["visible_component_semantic"] == \
            r2.APPROVED_VISIBLE_SEMANTIC
        assert a["internal_closure_mechanism"] == "UNRESOLVED / HIDDEN"
        for bad in ("exposed conventional pipette bulb", "narrow-stem bulb",
                    "outer overcap", "actuator",
                    "complete closure mechanism"):
            assert bad in a["forbidden_classifications"]


class TestRejectedDimensionsFrozen:
    def test_corr5_values_are_frozen_and_unused(self):
        rej = r2.REJECTED_INTERNAL_ASSUMPTIONS
        assert rej["state"] == "REJECTED_INTERNAL_ASSUMPTIONS"
        assert rej["may_drive_new_fixture"] is False
        assert rej["web_grounded"] is False
        for key in ("body_diameter", "body_height", "collar_diameter",
                    "collar_height", "bulb_max_width", "total_height"):
            assert key in rej["values_mm"]
        # preserved, not deleted
        assert os.path.exists(os.path.join(
            DOCS, "vq1_corr5", "vq1_corr5_fixture.json"))

    def test_envelope_uses_no_millimetre_authority(self):
        assert ENV["coordinate_system"]["millimetres_used"] is False
        assert ENV["coordinate_system"]["units"] == "NORMALIZED_NONE"
        assert ENV["coordinate_system"]["assembly_height"] == 1.0
        assert ENV["coordinate_system"]["body_visible_width"] == 1.0
        assert ENV["coordinate_system"]["shared_centerline"] == 0.0
        for comp in ENV["components"].values():
            for x, y in comp["normalized_points"]:
                assert 0.0 <= y <= 1.0 and 0.0 <= x <= 1.0

    def test_no_rejected_dimension_appears_in_the_envelope(self):
        blob = json.dumps(ENV["components"])
        for mm in ("31.3", "61.0", "15.9", "12.1", "92.9"):
            assert mm not in blob


class TestEnvelopeShape:
    def test_dark_closure_has_a_constant_width_region(self):
        f = r2.closure_envelope_findings(ENV)
        assert f["checks"]["constant_width_region_present"] is True
        assert r2.VQ_CLOSURE_CONSTANT_WIDTH_REGION_MISSING not in \
            f["findings"]

    def test_dark_closure_has_a_short_lower_flare(self):
        f = r2.closure_envelope_findings(ENV)
        assert f["checks"]["lower_flare_present"] is True
        assert f["peak_at_fraction"] >= 0.75

    def test_no_long_external_stem(self):
        f = r2.closure_envelope_findings(ENV)
        assert f["checks"]["no_external_stem"] is True
        assert r2.VQ_UNSUPPORTED_EXTERNAL_STEM_EMITTED not in f["findings"]

    def test_spear_and_leaf_profiles_are_rejected(self):
        spear = {"components": {"DARK_CLOSURE": {"normalized_points":
                 [(0.30 - 0.02 * i, i / 14) for i in range(15)]}}}
        assert r2.VQ_CLOSURE_ENVELOPE_SPEAR_SHAPE in \
            r2.closure_envelope_findings(spear)["findings"]
        leaf = {"components": {"DARK_CLOSURE": {"normalized_points":
                [(0.05 + 0.25 * (1 - abs(i - 7) / 7), i / 14)
                 for i in range(15)]}}}
        assert r2.VQ_CLOSURE_ENVELOPE_LEAF_SHAPE in \
            r2.closure_envelope_findings(leaf)["findings"]

    def test_collar_ratio_follows_pixel_evidence(self):
        ratios = r2.envelope_ratios(ENV)
        assert abs(ratios["collar_body_ratio"] - 0.633) <= 0.025
        assert abs(ratios["dark_body_ratio"] - 0.318) <= 0.025
        # the rejected 0.45-0.55 window is NOT reused
        assert ratios["collar_body_ratio"] > 0.55

    def test_occlusion_and_symmetry_are_explicit(self):
        assert ENV["occluded_regions"][0]["side"] == "LEFT"
        assert ENV["occluded_regions"][0]["measurable"] is False
        assert ENV["mirrored_regions"][0]["authority"] == \
            "HUMAN_APPROVED_CONCEPT_ONLY_ASSUMPTION"
        assert r2.geometry_authority()["bilateral_symmetry"] == \
            "HUMAN_APPROVED_CONCEPT_ONLY_ASSUMPTION"
        assert ENV["reference_pixel_relationships"][
            "is_physical_dimension"] is False


class TestDeterministicGates:
    def test_aspect_gate_catches_a_squat_render(self):
        pairs = [(i / 50, 0.5) for i in range(51)]
        good = r2.compare_to_reference(
            pairs, pairs, reference_ratios={}, candidate_ratios={},
            candidate_aspect=r2.ASPECT_W_OVER_H)
        assert good["gates"]["assembly_aspect"] is True
        bad = r2.compare_to_reference(
            pairs, pairs, reference_ratios={}, candidate_ratios={},
            candidate_aspect=1.0)
        assert bad["gates"]["assembly_aspect"] is False
        assert bad["gates_pass"] is False

    def test_gate_thresholds_match_the_mandate(self):
        g = r2.GATES
        assert g["silhouette_iou_min"] == 0.90
        assert g["mean_contour_max"] == 0.020
        assert g["p95_contour_max"] == 0.045
        assert g["max_contour_max"] == 0.070
        assert g["collar_ratio_error_max"] == 0.025
        assert g["dark_ratio_error_max"] == 0.025

    def test_failing_gates_block_assembly_release(self):
        it4 = PACKET["iterations"][-1]["comparison"]
        assert it4["gates_pass"] is False
        assert PACKET["assembly_released"] is False
        assert LOOP["assembly_released"] is False

    def test_occluded_side_is_excluded_from_scoring(self):
        m = PACKET["iterations"][-1]["comparison"]["metrics"]
        assert m["occluded_side_excluded_from_scoring"] == "LEFT"


class TestVisualizerLoop:
    def test_renderer_and_inspector_are_separate(self):
        insp = open(vi.__file__).read()
        assert "vq1_reset2" not in insp
        assert "draw_assembly" not in insp
        rend = open(r2.__file__).read()
        assert "run_vision_inspection" not in rend

    def test_actual_pngs_were_supplied_to_the_inspector(self):
        for n in (1, 3, 4):
            v = PACKET["multimodal"][f"iteration_{n}"]
            assert v.get("output_description")
            assert os.path.exists(os.path.join(R2, f"iteration_{n}.png"))

    def test_inspector_calls_are_bounded_to_three(self):
        assert LOOP["inspector_calls_used"] == 3
        assert LOOP["inspector_calls_max"] == 3
        assert LOOP["stop"] is True
        assert LOOP["reason"] == "ALL_INSPECTOR_CALLS_CONSUMED"

    def test_worse_output_stops_the_loop(self):
        worse = {"verdict": vi.VISUALLY_WORSE, "critical_blockers": [],
                 "component_semantics": {"generation_blocked": False},
                 "improvement_against_previous": {}}
        assert vi.loop_should_stop([worse])["reason"] == \
            "RESULT_BECAME_WORSE"

    def test_repeated_blocker_stops_the_loop(self):
        a = {"verdict": vi.VISUALLY_REJECTED,
             "critical_blockers": ["VQ_CLOSURE_ENVELOPE_SPEAR_SHAPE"],
             "component_semantics": {"generation_blocked": False},
             "improvement_against_previous": {
                 "contour_distance_delta": 0.5}}
        assert vi.loop_should_stop([dict(a), dict(a)])["reason"] == \
            "SAME_BLOCKER_REPEATED_TWICE"

    def test_multimodal_cannot_override_pixel_measurements(self):
        rule = __import__(
            "apps.pipeline.services.geometry_evidence", fromlist=["x"]
        ).visualizer_authority_rule()
        assert rule["multimodal_may_override_measured_ratios"] is False

    def test_every_iteration_is_preserved(self):
        assert len(PACKET["iterations"]) == 4
        assert LOOP["iterations"] == ["RESET2-IT1", "RESET2-IT2",
                                      "RESET2-IT3", "RESET2-IT4"]
        assert len(PACKET["correction_plans"]) == 4

    def test_never_auto_accepted(self):
        assert LOOP["never_auto_accepted"] is True
        assert "AUTO_ACCEPTED" not in json.dumps(PACKET)


class TestSupplierBoundary:
    def test_discovery_respected_same_domain_and_access_limits(self):
        d = PACKET["same_domain_discovery"]
        assert d["limits"]["same_domain_only"] is True
        assert d["limits"]["max_domains"] == 5
        assert d["limits"]["max_pages"] == 20
        assert d["pages_attempted"] <= 20
        assert len(d["domains"]) <= 5
        for p in ("no login", "no quote-form submission",
                  "no portal bypass", "no CAPTCHA defeat"):
            assert p in d["policy"]
        for a in d["attempts"]:
            host = a["url"].split("/")[2]
            assert host in d["domains"]

    def test_no_public_specification_was_found(self):
        assert PACKET["same_domain_discovery"]["result"] == \
            "NO_PUBLIC_SPECIFICATION_AVAILABLE"

    def test_supplier_requests_are_drafted_but_not_sent(self):
        s = PACKET["supplier_requests"]
        assert s["sent"] is False
        assert s["state"] == "DRAFTED_NOT_SENT"
        assert s["requires_human_approval_before_sending"] is True
        assert len(s["requests"]) >= 3
        domains = {r["domain"] for r in s["requests"]}
        assert "liquidbottles.com" in domains
        assert "sks-bottle.com" in domains
        for r in s["requests"]:
            assert r["status"] == "DRAFTED_NOT_SENT"
        for item in ("dimensional drawing", "neck finish", "collar diameter",
                     "pipette length", "total assembled height",
                     "MOQ and sample availability"):
            assert item in s["requested_items"]


class TestBoundaries:
    def test_no_image_generation_call_occurred(self):
        assert PACKET["image_generation_calls"] == 0
        assert LOOP["image_generation_calls"] == 0
        src = open(r2.__file__).read().lower()
        for banned in ("images.generate", "dall-e", "generate_image",
                       "image_producer"):
            assert banned not in src

    def test_prior_fixtures_and_findings_preserved(self):
        rec = json.load(open(os.path.join(
            DOCS, "vq1", "vq1_human_structural_review.json")))
        assert rec["state"] == "REVISION_REQUIRED"
        assert len(rec["history"]) == 4
        sem = json.load(open(os.path.join(
            DOCS, "vq1_reset1", "component_semantic_finding.json")))
        assert sem["generation_blocked"] is True

    def test_artifacts_are_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("reset2-review-png", "reset2-review-pdf",
                    "reset2-review-json", "reset2-authority",
                    "reset2-envelope", "reset2-loop", "reset2-plans",
                    "reset2-discovery", "reset2-supplier-requests",
                    "reset2-it4-png"):
            assert key in ARTIFACTS
            rel, _m = ARTIFACTS[key]
            assert os.path.exists(os.path.join(DOCS, "vq1", rel)), key

    @pytest.mark.django_db
    def test_live_pilot_records_untouched(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for tid, status in ((52, "container_stage_visually_rejected"),
                            (51, "awaiting_gate_2")):
            t = DesignTask.objects.filter(id=tid).first()
            assert t is None or t.status == status
        p = DesignProject.objects.filter(id=7).first()
        assert p is None or p.status == "container_rejected"
