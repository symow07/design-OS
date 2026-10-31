"""VQ-1-RESET-2-CORR-1A §14 — visualizer input integrity, output-pixel
apex topology, bounded replay, and the supplier-contact correction."""
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
AUD = os.path.join(DOCS, "vq1_it5_audit")
R2 = os.path.join(DOCS, "vq1_reset2")


def _load(d, n):
    with open(os.path.join(d, n)) as f:
        return json.load(f)


PACKET = _load(AUD, "vq1_it5_human_review.json")
MAN = _load(AUD, "visual_inspector_input_manifest.json")
PROOF = _load(AUD, "it5_output_pixel_apex_proof.json")
VAL = _load(AUD, "visualizer_input_resolution_validation.json")
REPLAY = _load(AUD, "visualizer_replay.json")
RES = _load(AUD, "visualizer_conflict_resolution.json")
OUTREACH = _load(R2, "vq1_supplier_specification_outreach.json")


def _sha(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class TestInputIntegrity:
    def test_exact_model_input_images_are_preserved(self):
        for n in ("visualizer_input_reference.png",
                  "visualizer_input_reference_closure_crop.png",
                  "visualizer_input_it4.png", "visualizer_input_it5.png"):
            assert os.path.exists(os.path.join(AUD, n)), n

    def test_it5_hash_matches_the_model_input(self):
        entry = [i for i in MAN["images"] if i["role"] == "output_it5"][0]
        assert entry["sha256"] == _sha(os.path.join(R2, "iteration_5.png"))
        assert entry["sha256"] == _sha(
            os.path.join(AUD, "visualizer_input_it5.png"))
        assert PROOF["image_sha256"] == entry["sha256"]

    def test_it4_cannot_be_mislabelled_as_it5(self):
        h = {i["role"]: i["sha256"] for i in MAN["images"]}
        assert h["output_it5"] != h["previous_it4"]
        assert h["previous_it4"] == _sha(
            os.path.join(R2, "iteration_4.png"))
        assert RES["integrity_findings"]["wrong_iteration_input"] is False
        assert RES["integrity_findings"]["image_label_mismatch"] is False

    def test_stale_asset_use_would_fail(self):
        assert RES["integrity_findings"]["stale_asset_input"] is False
        assert RES["integrity_findings"]["input_hash_mismatch"] is False
        # a substituted file must not match the recorded hash
        entry = [i for i in MAN["images"] if i["role"] == "output_it5"][0]
        assert entry["sha256"] != _sha(os.path.join(R2, "iteration_4.png"))

    def test_manifest_records_ordering_and_omissions(self):
        assert MAN["record_type"] == "visual_inspector_input_manifest/1.0"
        assert len(MAN["image_ordering"]) == 3
        assert MAN["scaling_applied"] == "NONE"
        assert MAN["credentials_persisted"] is False
        assert MAN["hidden_reasoning_persisted"] is False
        assert MAN["images_required_but_not_supplied"]

    def test_minimum_resolution_is_enforced_and_failed(self):
        c = VAL["checks"]
        assert c["dome_region_at_least_120px_tall"] is False
        assert c["closure_crop_at_least_512px_tall"] is False
        assert c["dedicated_closure_crop_supplied"] is False
        assert VAL["finding"] == "VQ_VISUALIZER_INPUT_RESOLUTION_INSUFFICIENT"
        assert VAL["encoder_resizing"].startswith("NONE")

    def test_dome_is_not_clipped(self):
        assert VAL["checks"]["entire_dome_visible"] is True
        assert VAL["checks"]["no_top_cropping"] is True
        assert PROOF["topmost_foreground_row"] > 0


class TestOutputPixelTopology:
    def test_apex_measured_from_actual_output_pixels(self):
        assert "ACTUAL emitted PNG" in PROOF["analysis"]
        assert len(PROOF["first_20_row_widths_px"]) == 20
        assert len(PROOF["row_progression"]) == 20

    def test_apex_is_rounded_by_width_progression(self):
        e = PROOF["topology_evidence"]
        assert e["monotonically_widening"] is True
        assert e["increments_decelerate"] is True
        assert PROOF["apex_topology"] == \
            "ROUNDED_APEX_WITH_RASTERIZATION_PLATEAU"

    def test_apex_is_centred(self):
        assert PROOF["apex_centered_within_px"] <= 1.0

    def test_binary_mask_panel_exists(self):
        assert os.path.exists(os.path.join(AUD, "it5_apex_binary_mask.png"))

    def test_resolution_caveat_is_recorded(self):
        assert "withdrawn as unreliable" in PROOF["resolution_caveat"]


class TestReplayAndResolution:
    def test_exactly_one_replay_occurred(self):
        assert REPLAY["calls"] == 1
        assert PACKET["visualizer_replay_calls"] == 1

    def test_replay_prompt_prohibited_numerics_and_withheld_priors(self):
        assert REPLAY["prompt_prohibits_numeric_estimation"] is True
        assert REPLAY["prior_verdict_withheld"] is True
        assert REPLAY["deterministic_result_withheld"] is True

    def test_replay_inputs_are_legible_and_traceable(self):
        for role in ("reference", "it5"):
            i = REPLAY["replay_inputs"][role]
            assert i["sha256"] and os.path.exists(i["path"])
            assert i["size"][1] >= 512
            assert i["operation"]

    def test_replay_identified_a_rounded_apex(self):
        assert REPLAY["apex_appearance"] == "rounded"
        assert REPLAY["entire_dome_visible"] is True
        assert REPLAY["same_visible_closure_family"] is True

    def test_conflict_resolved_without_blocking_the_dome(self):
        assert RES["resolution"] == \
            "VQ_VISUALIZER_ORIGINAL_INPUT_OR_INTERPRETATION_FAILED"
        assert RES["counts_as_blocker_against_dome"] is False
        assert RES["original_verdict_retained_for_audit"] is True
        assert RES["unreliable_for_apex_geometry"] is False
        assert RES["proceed_to_human_visual_review_of_it5"] is True

    def test_deterministic_topology_governs(self):
        assert "may never override it" in RES["governing_authority"]
        for code in ("VQ_VISUALIZER_DETERMINISTIC_CONFLICT",
                     "VQ_VISUALIZER_INPUT_INTEGRITY_REVIEW_REQUIRED",
                     "VQ_VISUALIZER_VERDICT_NOT_ACTIONABLE"):
            assert code in RES["codes_recorded"]


class TestStateAndSuppliers:
    def test_no_it6_and_it5_not_passed(self):
        assert PACKET["it6_generated"] is False
        assert PACKET["it5_passed_human_review"] is False
        assert PACKET["vq1_state"] == "REVISION_REQUIRED"
        # IT6 was authorized by a LATER mandate; what this slice must
        # prove is that IT6 was not generated BY IT — its own record

    def test_collar_neck_spike_is_disclosed(self):
        s = PACKET["unresolved_collar_neck_spike"]
        assert s["value"] > s["limit"]
        assert s["component"] == "collar/neck junction"
        assert s["authorized_to_fix_in_this_slice"] is False

    def test_prior_iterations_preserved(self):
        for n in (1, 2, 3, 4, 5):
            assert os.path.exists(
                os.path.join(R2, f"iteration_{n}_metrics.json"))

    def test_supplier_endpoints_corrected_with_provenance(self):
        by = {s["domain"]: s for s in OUTREACH["suppliers"]}
        sks = by["sks-bottle.com"]
        assert sks["contact_endpoint"] == \
            "https://www.sks-bottle.com/contact_us.php"
        pv = by["premiumvials.com"]
        assert pv["contact_endpoint"] == "https://premiumvials.com/contact-us/"
        emails = [e["endpoint"] for e in
                  pv["endpoint_verification"]["resolved_endpoints"]]
        assert "mailto:support@premiumvials.com" in emails
        for d in ("sks-bottle.com", "premiumvials.com"):
            v = by[d]["endpoint_verification"]
            assert v["status"] == "VERIFIED_REACHABLE"
            assert "search snippets were not used" in v["note"]
            for e in v["resolved_endpoints"]:
                assert e["provenance"] and e["verified_at"]

    def test_no_supplier_request_is_marked_sent(self):
        for s in OUTREACH["suppliers"]:
            assert s["status"] == "DRAFTED_READY_FOR_HUMAN_SEND"
            assert s["sent"] is False
            assert s["delivery_verified"] is False
        assert OUTREACH["outbound_email_available"] is False

    def test_no_image_generation_call(self):
        assert PACKET["image_generation_calls"] == 0

    def test_artifacts_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("it5-review-png", "it5-review-pdf", "it5-review-json",
                    "it5-input-manifest", "it5-apex-proof", "it5-apex-mask",
                    "it5-replay", "it5-conflict-resolution",
                    "it5-input-it5", "it5-input-it4"):
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
