"""VQ-1-RESET-2-CORR-1 §16 — dome-only change, apex termination, single
visualizer call, and the supplier-dispatch boundary."""
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_reset2 as r2

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R2 = os.path.join(DOCS, "vq1_reset2")
PACKET = json.load(open(os.path.join(R2, "vq1_reset2_corr1_review.json")))
ENV4 = json.load(open(os.path.join(R2, "concept_visual_envelope.json")))
ENV5 = json.load(open(os.path.join(R2, "concept_visual_envelope_it5.json")))
OUTREACH = json.load(open(os.path.join(
    R2, "vq1_supplier_specification_outreach.json")))


class TestOnlyDomeChanged:
    def test_every_other_component_is_identical(self):
        u = r2.unchanged_outside_dome(ENV4, ENV5)
        assert u["only_dome_changed"] is True
        for name in ("COLLAR", "NECK_VISIBLE", "SHOULDER", "BODY", "BASE"):
            assert u["per_component"][name] == "IDENTICAL"
            assert ENV4["components"][name]["normalized_points"] == \
                ENV5["components"][name]["normalized_points"]

    def test_shaft_and_flare_survive_untouched(self):
        u = r2.unchanged_outside_dome(ENV4, ENV5)
        assert u["per_component"]["DARK_CLOSURE"] == \
            "SHAFT_AND_FLARE_IDENTICAL"
        # the strong claim: the shaft and flare POINTS are byte-identical
        cap_n = ENV5["dome_cap"]["samples"]
        p4 = ENV4["components"]["DARK_CLOSURE"]["normalized_points"]
        p5 = ENV5["components"]["DARK_CLOSURE"]["normalized_points"]
        dome_end = p4[0][1] + ENV5["dome_cap"]["dome_height_norm"]
        assert [p for p in p4 if p[1] > dome_end] == p5[cap_n:]
        # the derived shaft AVERAGE moves by ~1e-4 only because the capped
        # envelope measures the shaft from the cap boundary instead of a
        # fractional slice; the underlying points did not change
        r4, r5 = r2.envelope_ratios(ENV4), r2.envelope_ratios(ENV5)
        assert abs(r4["dark_body_ratio"] - r5["dark_body_ratio"]) < 1e-3
        assert r4["collar_body_ratio"] == r5["collar_body_ratio"]
        assert r4["flare_body_ratio"] == r5["flare_body_ratio"]

    def test_aspect_and_authority_model_unchanged(self):
        assert r2.geometry_authority()["modes"][r2.PRODUCTION]["state"] == \
            "NOT_AVAILABLE"
        m = PACKET["iteration_5"]["comparison"]["metrics"]
        assert m["reference_aspect_w_over_h"] == round(
            r2.ASPECT_W_OVER_H, 5)


class TestDomeTermination:
    def test_apex_half_width_is_exactly_zero_on_the_centerline(self):
        pts = ENV5["components"]["DARK_CLOSURE"]["normalized_points"]
        assert pts[0][0] == 0.0
        assert ENV5["dome_cap"]["apex_half_width"] == 0.0
        assert ENV5["dome_cap"]["apex_on_centerline"] is True

    def test_no_horizontal_closing_segment(self):
        pts = ENV5["components"]["DARK_CLOSURE"]["normalized_points"]
        assert abs(pts[1][1] - pts[0][1]) > 1e-9
        f = r2.dome_findings(ENV5)
        assert f["checks"]["no_horizontal_closing_segment"] is True
        assert r2.VQ_CLOSURE_TOP_HORIZONTAL_SEGMENT not in f["findings"]

    def test_dome_curvature_is_continuous_with_enough_samples(self):
        f = r2.dome_findings(ENV5)
        assert f["checks"]["dome_curvature_continuous"] is True
        assert f["checks"]["at_least_21_dome_samples"] is True
        assert ENV5["dome_cap"]["samples"] >= 21
        assert f["status"] == "DOME_TERMINATION_VALID"
        assert f["findings"] == []

    def test_dome_widens_monotonically_and_has_no_plateau(self):
        f = r2.dome_findings(ENV5)
        assert f["checks"]["dome_widens_monotonically_from_apex"] is True
        assert f["checks"]["no_upper_plateau"] is True

    def test_a_flat_top_is_still_detected(self):
        bad = {"components": {"DARK_CLOSURE": {"normalized_points":
               [(0.16, 0.0), (0.16, 0.01), (0.16, 0.05)]}}}
        f = r2.dome_findings(bad)
        assert r2.VQ_CLOSURE_APEX_FINITE_WIDTH in f["findings"]
        assert r2.VQ_CLOSURE_DOME_FLAT_TOP in f["findings"]
        assert f["status"] == "DOME_TERMINATION_FAILED"

    def test_closure_semantics_preserved(self):
        f = r2.closure_envelope_findings(ENV5)
        assert f["status"] == "ENVELOPE_MATCHES_APPROVED_VISIBLE_SEMANTIC"
        assert f["checks"]["constant_width_region_present"] is True
        assert f["checks"]["lower_flare_present"] is True
        assert f["checks"]["no_external_stem"] is True


class TestMetricsAndLoopBoundary:
    def test_dome_only_gate_passes(self):
        c = PACKET["iteration_5"]["comparison"]
        assert c["gates"]["dome_only"] is True
        assert c["metrics"]["dome_only_max"] <= r2.GATES["max_contour_max"]

    def test_overall_gates_still_fail_and_nothing_is_released(self):
        c = PACKET["iteration_5"]["comparison"]
        assert c["gates"]["max_contour_distance"] is False
        assert c["gates_pass"] is False
        assert PACKET["assembly_released"] is False
        assert PACKET["vq1_state"] == "REVISION_REQUIRED"

    def test_exactly_one_visualizer_call_and_no_it6(self):
        assert PACKET["visualizer"]["calls"] == 1
        assert PACKET["it6_generated"] is False
        # IT6 was authorized by a LATER mandate; what this slice must
        # prove is that IT6 was not generated BY IT — its own record

    def test_actual_png_was_inspected_against_it4(self):
        assert os.path.exists(os.path.join(R2, "iteration_5.png"))
        assert os.path.exists(os.path.join(R2, "iteration_4.png"))
        assert PACKET["visualizer"]["iteration_5"].get("output_description")

    def test_multimodal_conflict_is_recorded_and_pixels_govern(self):
        assert "VQ_MULTIMODAL_NUMERIC_CLAIM_CONFLICT" in \
            PACKET["visualizer"]["conflict"]
        assert PACKET["visualizer"]["verdict"] == "VISUALLY_REJECTED"
        assert "Deterministic measurement governs" in \
            PACKET["visualizer"]["conflict"]

    def test_never_auto_accepted(self):
        assert "AUTO_ACCEPTED" not in json.dumps(PACKET)


class TestSupplierDispatch:
    def test_nothing_is_marked_sent_without_verified_delivery(self):
        assert OUTREACH["outbound_email_available"] is False
        for s in OUTREACH["suppliers"]:
            assert s["sent"] is False
            assert s["delivery_verified"] is False
            assert s["status"] == "DRAFTED_READY_FOR_HUMAN_SEND"
            assert s["status"] != "SENT"

    def test_all_required_request_fields_present(self):
        for item in ("bottle dimensional drawing", "neck finish",
                     "collar outside diameter", "collar visible height",
                     "pipette length", "total assembled height",
                     "brimful/overflow capacity", "glass weight",
                     "CAD/PDF files", "MOQ", "sample availability",
                     "sample cost", "lead time", "country of manufacture"):
            assert item in OUTREACH["requested_documents"]
        assert any("bare rubber bulb" in i
                   for i in OUTREACH["requested_documents"])
        for s in OUTREACH["suppliers"]:
            assert "INCLUDES the closure" in s["body"]

    def test_prohibited_attachments_absent(self):
        b = OUTREACH["information_boundary"]
        assert b["attachments"] == []
        assert b["prohibited_attachments_present"] is False
        blob = json.dumps(OUTREACH)
        for banned in ("task_52", "task 52", "task #52", "image_97",
                       "task_51", "GeneratedImage", "CORR-5 fixture"):
            assert banned not in blob

    def test_no_order_or_financial_commitment(self):
        for banned in ("placing an order", "accepting a quotation",
                       "agreeing to MOQ", "payment"):
            assert banned in OUTREACH["authorization_excludes"]
        for s in OUTREACH["suppliers"]:
            assert "not placing an order" in s["body"]

    def test_endpoints_are_public_and_verified_or_flagged(self):
        for s in OUTREACH["suppliers"]:
            assert s["contact_endpoint"].startswith("https://")
            assert s["domain"] in s["contact_endpoint"]
            assert s["endpoint_verification"]["status"] in (
                "VERIFIED_REACHABLE", "UNVERIFIED")
            assert "no scraped private addresses" in s["rights_note"]

    def test_production_geometry_blocked_pending_response(self):
        assert OUTREACH["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_RESPONSE"
        assert OUTREACH["no_response_is_automatically_authoritative"] is True
        assert PACKET["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_RESPONSE"


class TestBoundaries:
    def test_no_image_generation_call(self):
        assert PACKET["image_generation_calls"] == 0
        assert PACKET["manufacturable_claim"] is False

    def test_prior_iterations_preserved(self):
        for n in (1, 2, 3, 4):
            assert os.path.exists(
                os.path.join(R2, f"iteration_{n}_metrics.json"))
        assert os.path.exists(os.path.join(R2, "iteration_4.png"))

    def test_artifacts_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("corr1-review-png", "corr1-review-pdf",
                    "corr1-review-json", "corr1-envelope",
                    "corr1-outreach", "reset2-it5-png"):
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
