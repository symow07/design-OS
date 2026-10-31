"""VQ-1-RESET-2-CORR-2 §16 — collar/neck envelope replacement scope,
single-sleeve geometry, hidden internals and the IT6 boundaries."""
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_reset2 as r2

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R2D = os.path.join(DOCS, "vq1_reset2")
REV = os.path.join(DOCS, "vq1_it6_review")
ENV5 = json.load(open(os.path.join(R2D, "concept_visual_envelope_it5.json")))
ENV6 = json.load(open(os.path.join(R2D, "concept_visual_envelope_it6.json")))
PACKET = json.load(open(os.path.join(
    REV, "vq1_it6_collar_neck_review.json")))


class TestScope:
    def test_only_collar_neck_and_interface_changed(self):
        s = r2.it6_unchanged_report(ENV5, ENV6)
        assert s["body_identical"] and s["shoulder_identical"]
        assert s["base_identical"] and s["neck_band_identical"]
        assert s["centerline_identical"] and s["aspect_identical"]
        assert s["collar_replaced"] is True
        assert PACKET["authorized_change"] == [
            "COLLAR_VISIBLE_ENVELOPE", "VISIBLE_NECK_TRANSITION",
            "DARK_COMPONENT_TO_COLLAR_INTERFACE"]

    def test_it5_dome_is_byte_identical(self):
        cap = ENV6["dome_cap"]["samples"]
        assert ENV5["components"]["DARK_CLOSURE"]["normalized_points"][:cap] \
            == ENV6["components"]["DARK_CLOSURE"]["normalized_points"][:cap]
        assert ENV6["dome_cap"]["apex_half_width"] == 0.0
        assert r2.dome_findings(ENV6)["status"] == "DOME_TERMINATION_VALID"

    def test_shaft_identical_except_the_interface_point(self):
        s = r2.it6_unchanged_report(ENV5, ENV6)
        assert s["shaft_identical_except_interface"] is True
        assert s["interface_points_added"] == 1

    def test_body_and_shoulder_points_match_exactly(self):
        for name in ("BODY", "SHOULDER", "BASE", "NECK_VISIBLE"):
            assert ENV5["components"][name]["normalized_points"] == \
                ENV6["components"][name]["normalized_points"]


class TestSingleSleeve:
    def test_no_visible_contour_steps(self):
        f = r2.it6_collar_findings(ENV6)
        assert f["visible_steps"] == 0
        assert f["checks"]["visible_contour_steps_zero"] is True
        assert r2.VQ_COLLAR_STEPPED_TOWER_FALLBACK not in f["findings"]
        assert f["status"] == "COLLAR_SINGLE_SLEEVE_VALID"

    def test_collar_is_one_continuous_envelope(self):
        f = r2.it6_collar_findings(ENV6)
        assert f["checks"]["single_sleeve"] is True
        assert f["checks"]["walls_near_vertical"] is True
        assert len(ENV6["components"]["COLLAR"]["normalized_points"]) >= 12

    def test_white_spacer_ring_absent(self):
        info = ENV6["it6_collar_neck"]
        assert info["neck_drawn_as_separate_object"] is False
        assert info["glass_is_one_contour"] is True
        assert "NECK_VISIBLE" in info["glass_bands_merged"]
        assert "NECK_VISIBLE" not in r2.IT6_VISIBLE_ORDER
        f = r2.it6_collar_findings(ENV6)
        assert r2.VQ_NECK_SPACER_RING_FALLBACK not in f["findings"]

    def test_only_three_visible_objects(self):
        assert r2.IT6_VISIBLE_ORDER == (
            "GLASS_ASSEMBLY", "COLLAR_SLEEVE", "DARK_CLOSURE")
        g = r2.it6_component_paths(ENV6, 0, 0, 100)
        assert set(g) == set(r2.IT6_VISIBLE_ORDER)

    def test_internal_adapter_is_hidden(self):
        info = ENV6["it6_collar_neck"]
        assert info["internals_affect_visible_contour"] is False
        assert set(info["nonprinting_technical_internals"]) == \
            set(r2.NONPRINTING_TECHNICAL_INTERNALS)
        f = r2.it6_collar_findings(ENV6)
        assert r2.VQ_VISIBLE_INTERNAL_ADAPTER_UNSUPPORTED not in f["findings"]
        assert PACKET["metrics"][
            "unsupported_visible_internal_adapter"] is False

    def test_dark_flare_connects_to_the_collar(self):
        f = r2.it6_collar_findings(ENV6)
        assert f["checks"]["dark_flare_overlaps_collar"] is True
        assert r2.VQ_DARK_CLOSURE_LOWER_INTERFACE_FAILED not in f["findings"]
        assert ENV6["it6_collar_neck"]["flare_overlap_norm"] > 0

    def test_a_stepped_collar_is_still_detected(self):
        bad = {"components": {"COLLAR": {"normalized_points":
               [(0.20, 0.0), (0.20, 0.05), (0.31, 0.06), (0.31, 0.16)]},
               "DARK_CLOSURE": {"normalized_points": [(0.1, 0.0)]}},
               "it6_collar_neck": {"glass_is_one_contour": True,
                                   "neck_drawn_as_separate_object": False,
                                   "internals_affect_visible_contour": False}}
        f = r2.it6_collar_findings(bad)
        assert r2.VQ_COLLAR_STEPPED_TOWER_FALLBACK in f["findings"]
        assert f["status"] == "COLLAR_ENVELOPE_FAILED"


class TestMetricsAndInspection:
    def test_metrics_come_from_actual_png_pixels(self):
        m = PACKET["metrics"]
        assert m["measured_on"] == "ACTUAL_EMITTED_PNG"
        assert m["row_aligned"] is True
        assert m["averaged_with_body"] is False
        assert "resampler" in m["harness_note"]

    def test_collar_improved_over_it5(self):
        m = PACKET["metrics"]
        assert m["collar_outer_contour_iou"] > m["it5_comparison"]["iou"]
        assert m["mean_collar_contour_distance"] < \
            m["it5_comparison"]["mean"]

    def test_collar_gates_recorded_and_one_still_fails(self):
        g = PACKET["metrics"]["gates"]
        assert g["collar_body_ratio"] and g["collar_outer_contour_iou"]
        assert g["mean_collar_contour_distance"]
        assert g["visible_contour_steps_zero"]
        assert g["max_collar_junction_distance"] is False
        assert PACKET["metrics"]["gates_pass"] is False

    def test_reference_pixels_are_concept_visual_only(self):
        rp = PACKET["reference_pixels"]
        assert rp["authority"] == "CONCEPT_VISUAL_PIXEL_EVIDENCE"
        assert rp["is_physical_dimension"] is False
        assert rp["collar_visible_width_px"] == 217.0
        assert abs(rp["collar_body_ratio"] - 0.633) < 1e-9

    def test_visualizer_received_legible_crops(self):
        q = PACKET["input_quality"]
        assert q["quality_gate"] == "PASSED"
        assert q["findings"] == []
        for c in PACKET["visualizer"]["manifest"]["images"]:
            assert c["sha256"] and os.path.exists(c["path"])

    def test_exactly_one_inspector_call(self):
        assert PACKET["visualizer"]["calls"] == 1
        assert PACKET["visualizer"]["manifest"]["call_permitted"] is True

    def test_visualizer_confirms_ledges_removed(self):
        v = PACKET["visualizer"]
        assert v["stepped_ledges_removed"] is True
        assert v["better_than_previous"] is True
        assert v["verdict"] in (
            "VISUALLY_WORSE_THAN_PREVIOUS", "VISUALLY_REJECTED",
            "VISUALLY_IMPROVED_BUT_INSUFFICIENT",
            "PASSES_VISUAL_INSPECTION_PENDING_HUMAN_REVIEW")


class TestBoundaries:
    def test_no_it7_and_not_released(self):
        assert PACKET["it7_generated"] is False
        assert PACKET["assembly_released"] is False
        assert PACKET["vq1_state"] == "REVISION_REQUIRED"
        assert not os.path.exists(os.path.join(R2D, "iteration_7.png"))

    def test_no_manufacturable_claim(self):
        assert PACKET["manufacturable_claim"] is False
        assert PACKET["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_RESPONSE"

    def test_no_supplier_request_sent(self):
        assert PACKET["supplier_requests_sent"] is False
        out = json.load(open(os.path.join(
            R2D, "vq1_supplier_specification_outreach.json")))
        for s in out["suppliers"]:
            assert s["sent"] is False
            assert s["status"] == "DRAFTED_READY_FOR_HUMAN_SEND"

    def test_no_image_generation_call(self):
        assert PACKET["image_generation_calls"] == 0

    def test_iterations_1_to_5_preserved(self):
        for n in (1, 2, 3, 4, 5):
            assert os.path.exists(
                os.path.join(R2D, f"iteration_{n}_metrics.json"))
        assert os.path.exists(os.path.join(R2D, "iteration_5.png"))

    def test_artifacts_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("it6-review-png", "it6-review-pdf", "it6-review-json",
                    "it6-png", "it6-envelope", "it6-reference-pixels"):
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
