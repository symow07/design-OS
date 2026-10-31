"""VQ-VISUALIZER-CORR-2 §15 — component legibility floor, fail-closed
input gate, crop lineage and verdict authority."""
import json
import os

import pytest
from django.conf import settings

from apps.pipeline.services import visual_input_quality as q

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
R2 = os.path.join(DOCS, "vq1_reset2")
GATE = os.path.join(DOCS, "vq1_visualizer_gate")
AUD = os.path.join(DOCS, "vq1_it5_audit")
IT5 = os.path.join(R2, "iteration_5.png")
REF = os.path.join(DOCS, "vq1_corr5", "ref97_closure.png")
FULL_REF = os.path.join(DOCS, "vq1_corr4", "ref97_bottle_crop.png")
RECORD = json.load(open(os.path.join(
    GATE, "vq_visualizer_input_quality_gate.json")))


def _minimal_evidence(candidate):
    return {"full_reference": FULL_REF, "full_candidate": candidate}


class TestLegibilityFloors:
    def test_floors_cover_every_inspected_component(self):
        for c in ("FULL_ASSEMBLY", "CLOSURE", "DARK_CLOSURE", "DOME_APEX",
                  "COLLAR", "NECK_VISIBLE", "SHOULDER"):
            assert c in q.LEGIBILITY_FLOORS
        f = q.LEGIBILITY_FLOORS
        assert f["FULL_ASSEMBLY"]["min_height_px"] == 512
        assert f["CLOSURE"]["min_height_px"] == 420
        assert f["DARK_CLOSURE"]["min_height_px"] == 300
        assert f["DOME_APEX"]["min_height_px"] == 120
        assert f["DOME_APEX"]["min_distinguishable_top_rows"] == 20
        assert f["COLLAR"]["min_height_px"] == 160
        assert f["NECK_VISIBLE"]["min_height_px"] == 80
        assert f["SHOULDER"]["min_width_px"] == 300

    def test_floors_are_declared_non_dimensional(self):
        assert RECORD["floors_are"] == \
            "MODEL_INPUT_LEGIBILITY_ONLY_NOT_PRODUCTION_DIMENSIONS"

    def test_thresholds_are_not_lowered_silently(self):
        r = q.evaluate_input_quality(
            component="DOME_APEX", candidate_path=IT5,
            evidence=_minimal_evidence(IT5),
            override_record={"floors": {"min_height_px": 1}})
        # no reviewed flag and no reason -> the override is ignored
        assert r["floors_applied"]["min_height_px"] == 120
        assert r["quality_gate"] == q.FAILED
        ok = q.evaluate_input_quality(
            component="DOME_APEX", candidate_path=IT5,
            evidence=_minimal_evidence(IT5),
            override_record={"floors": {"min_height_px": 1},
                             "reviewed": True, "reason": "documented"})
        assert ok["floors_applied"]["min_height_px"] == 1


class TestFailClosed:
    def test_a_27_pixel_dome_is_rejected_before_the_model_call(self):
        calls = []
        out = q.gated_inspection(
            component="DOME_APEX", candidate_path=IT5, reference_path=REF,
            evidence=_minimal_evidence(IT5),
            run_fn=lambda: calls.append(1))
        assert calls == [], "the model must not be called"
        assert out["model_called"] is False
        assert out["verdict"] == q.INSPECTION_NOT_PERFORMED
        assert out["result"] is None

    def test_failed_input_never_yields_a_rejection_verdict(self):
        out = q.gated_inspection(
            component="DOME_APEX", candidate_path=IT5, reference_path=REF,
            evidence=_minimal_evidence(IT5), run_fn=lambda: "UNREACHABLE")
        assert out["verdict"] != "VISUALLY_REJECTED"
        assert q.VQ_VERDICT_NOT_ACTIONABLE in out["findings"]
        assert "cannot produce a verdict" in out["note"]

    def test_the_original_it5_payload_fails_the_gate(self):
        r = q.evaluate_input_quality(
            component="DOME_APEX", candidate_path=IT5, reference_path=REF,
            evidence=_minimal_evidence(IT5))
        assert r["quality_gate"] == q.FAILED
        assert r["verdict_if_failed"] == q.INSPECTION_NOT_PERFORMED
        assert r["measurement"]["height_px"] < 120
        for code in (q.VQ_TARGET_COMPONENT_TOO_SMALL,
                     q.VQ_COMPONENT_LEGIBILITY_FAILED,
                     q.VQ_INPUT_RESOLUTION_INSUFFICIENT):
            assert code in r["findings"]

    def test_missing_component_crop_is_a_finding(self):
        r = q.evaluate_input_quality(
            component="DOME_APEX", candidate_path=IT5,
            evidence=_minimal_evidence(IT5))
        assert r["checks"]["evidence_candidate_component_crop"] is False
        assert q.VQ_REQUIRED_CROP_MISSING in r["findings"]

    def test_hash_mismatch_is_detected(self):
        r = q.evaluate_input_quality(
            component="FULL_ASSEMBLY", candidate_path=IT5,
            evidence={"full_candidate": IT5},
            expected_hashes={"full_candidate": "0" * 64})
        assert r["checks"]["labels_match_bytes"] is False
        assert q.VQ_INPUT_HASH_MISMATCH in r["findings"]

    def test_valid_replay_inputs_pass(self):
        rep = os.path.join(AUD, "replay_it5_closure.png")
        ref = os.path.join(AUD, "replay_reference_closure.png")
        r = q.evaluate_input_quality(
            component="FULL_ASSEMBLY", candidate_path=rep,
            reference_path=ref,
            evidence={"full_reference": ref,
                      "reference_component_crop": ref,
                      "full_candidate": rep,
                      "candidate_component_crop": rep})
        assert r["quality_gate"] == q.PASSED
        assert r["findings"] == []


class TestCropGeneration:
    def test_crops_preserve_identity_lineage_and_scale(self, tmp_path):
        c = q.generate_component_crop(IT5, "DOME_APEX", str(tmp_path))
        assert c["created"] is True
        assert c["source_sha256"] == q.sha256(IT5)
        assert c["crop_sha256"] and c["crop_sha256"] != c["source_sha256"]
        assert c["scale_factor"] >= 1.0
        assert c["scaling_algorithm"] in ("LANCZOS", "NONE")
        assert c["generative_upscaling"] is False
        assert c["original_dimensions"] and c["output_dimensions"]
        assert c["crop_bounds"] and c["component_bbox"]

    def test_crop_lifts_the_component_over_its_floor(self, tmp_path):
        c = q.generate_component_crop(IT5, "DOME_APEX", str(tmp_path))
        assert c["output_dimensions"][1] >= \
            q.LEGIBILITY_FLOORS["DOME_APEX"]["min_height_px"]

    def test_crops_are_not_clipped(self, tmp_path):
        for comp in ("DARK_CLOSURE", "COLLAR", "DOME_APEX"):
            c = q.generate_component_crop(IT5, comp, str(tmp_path))
            m = q.measure_component(c["path"], "FULL_ASSEMBLY")
            assert m["truncated_sides"] is False

    def test_crops_declare_they_are_not_new_evidence(self, tmp_path):
        c = q.generate_component_crop(IT5, "CLOSURE", str(tmp_path))
        assert c["evidence_status"] == \
            "LEGIBILITY_ONLY_NOT_NEW_GEOMETRIC_EVIDENCE"
        assert "ORIGINAL image governs topology" in c["topology_authority"]

    def test_all_suggested_crops_are_available(self):
        crops = json.load(open(os.path.join(GATE,
                                            "it5_component_crops.json")))
        for comp in ("FULL_ASSEMBLY", "CLOSURE", "DARK_CLOSURE",
                     "DOME_APEX", "COLLAR", "NECK_VISIBLE", "SHOULDER"):
            assert crops[comp]["created"] is True
            assert os.path.exists(crops[comp]["path"])


class TestManifestAndAuthority:
    def test_manifest_records_the_gate_and_permission(self):
        good = {"quality_gate": q.PASSED, "findings": []}
        m = q.build_manifest(
            inspection_id="x", purpose="structural comparison",
            component="DOME_APEX",
            images=[{"label": "full_candidate", "path": IT5,
                     "sha256": q.sha256(IT5)}],
            quality=good, model="m", prompt_version="v",
            semantic_state="ENVELOPE")
        assert m["schema_version"] == q.MANIFEST_SCHEMA
        assert m["call_permitted"] is True
        assert m["credentials_persisted"] is False
        bad = q.build_manifest(
            inspection_id="x", purpose="p", component="DOME_APEX",
            images=[], quality={"quality_gate": q.FAILED,
                                "findings": ["x"]},
            model="m", prompt_version="v", semantic_state="s")
        assert bad["call_permitted"] is False

    def test_multimodal_cannot_override_deterministic_topology(self):
        a = q.VERDICT_AUTHORITY
        assert a["multimodal_may_override_deterministic_pixel_topology"] \
            is False
        for item in ("apex topology", "numeric ratios", "symmetry",
                     "component bounds"):
            assert item in a["deterministic_output_pixel_analysis_governs"]
        for item in ("semantic resemblance", "perceived form"):
            assert item in a["multimodal_inspection_governs"]
        assert "final structural acceptance" in a["human_governs"]

    def test_apex_topology_stays_governed_by_original_pixels(self):
        proof = json.load(open(os.path.join(
            AUD, "it5_output_pixel_apex_proof.json")))
        assert proof["image_sha256"] == q.sha256(IT5)
        assert "ACTUAL emitted PNG" in proof["analysis"]


class TestRetroactiveRecordsAndBoundaries:
    def test_original_inspection_invalidated_but_preserved(self):
        r = RECORD["retroactive_it5_original_inspection"]
        assert r["annotation"] == "INVALIDATED_INPUT_QUALITY_INSUFFICIENT"
        assert r["deleted"] is False
        assert r["replayed_gate_result"] == q.FAILED
        assert r["would_be_verdict_today"] == q.INSPECTION_NOT_PERFORMED
        assert os.path.exists(os.path.join(R2, "vision_iteration_5.json"))

    def test_replay_preserved_as_valid_diagnostic_only(self):
        b = RECORD["bounded_replay"]
        assert b["annotation"] == "VALID_DIAGNOSTIC_REPLAY"
        assert b["gate_result"] == q.PASSED
        assert b["constitutes_human_acceptance"] is False
        assert b["deleted"] is False

    def test_geometry_unchanged_and_no_it6(self):
        assert RECORD["geometry_changed"] is False
        assert RECORD["it6_generated"] is False
        # IT6 was authorized by a LATER mandate; what this slice must
        # prove is that IT6 was not generated BY IT — its own record
        env = json.load(open(os.path.join(
            R2, "concept_visual_envelope_it5.json")))
        assert env["dome_cap"]["apex_half_width"] == 0.0

    def test_collar_neck_remains_unresolved(self):
        c = RECORD["collar_neck"]
        assert c["finding"] == "VQ_COLLAR_NECK_JUNCTION_DEVIATION"
        assert c["max_contour_distance"] > c["permitted_maximum"]
        assert c["resolved"] is False
        assert c["geometry_changed_this_slice"] is False

    def test_no_supplier_request_sent(self):
        assert RECORD["supplier_requests_sent"] is False
        out = json.load(open(os.path.join(
            R2, "vq1_supplier_specification_outreach.json")))
        for s in out["suppliers"]:
            assert s["sent"] is False
            assert s["status"] == "DRAFTED_READY_FOR_HUMAN_SEND"

    def test_no_image_generation_call(self):
        assert RECORD["image_generation_calls"] == 0
        assert RECORD["multimodal_calls_this_slice"] == 0
        src = open(q.__file__).read().lower()
        for banned in ("images.generate", "dall-e", "generate_image",
                       "image_producer"):
            assert banned not in src

    def test_artifacts_servable(self):
        from apps.pipeline.vq_views import ARTIFACTS
        for key in ("gate-record", "gate-crops", "gate-dome-crop",
                    "gate-closure-crop"):
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
