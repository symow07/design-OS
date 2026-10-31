"""VQ-1-MASTER-CLOSE-1 §20 — geometry closure and evidence-presentation."""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq1_close1 as c1
from apps.pipeline.services import vq1_close1_inspection as insp

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
E = os.path.join(M, "close1")

DENSE = json.load(open(os.path.join(M, "vq1_neck_shoulder_dense_confirmation.json")))
ASSEMBLY = json.load(open(os.path.join(M, "vq1_assembly_wide_dense_confirmation.json")))
DUAL = json.load(open(os.path.join(M, "vq1_close1_dual_inspection.json")))
WD = json.load(open(os.path.join(M, "vq1_measurement_method_withdrawal.json")))
REVIEW = json.load(open(os.path.join(M, "vq1_master_structural_review.json")))
FORENSIC = json.load(open(os.path.join(M, "vq1_junction_forensics.json")))
EVIDENCE = json.load(open(os.path.join(E, "evidence_manifest.json")))

#: the frozen candidate identity this whole slice is defined against
M3_PNG_SHA = "4ecc8e9df1d1"


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


class TestCandidateUntouched:
    def test_m3_png_is_byte_identical(self):
        assert _sha(os.path.join(M, "master_it3.png")) == M3_PNG_SHA
        assert REVIEW["candidate_png_sha256"].startswith(M3_PNG_SHA)

    def test_m3_ai_source_still_present_and_unmodified_by_this_slice(self):
        ai = os.path.join(M, "master_it3.ai")
        assert os.path.exists(ai)
        fit = json.load(open(os.path.join(M, "master_fit_m3.json")))
        assert fit["fits"]["GLASS"]["segment_count"] == 57
        assert fit["fits"]["GLASS"]["residual_max"] == 5.1

    def test_no_geometry_change_is_claimed_anywhere(self):
        for rec in (DENSE, ASSEMBLY, REVIEW):
            assert rec.get("geometry_modified") is False
        assert REVIEW["new_geometry_candidates"] == 0

    def test_no_edge_darkening_or_material_simulation(self):
        assert REVIEW["edge_darkening_applied"] is False
        assert REVIEW["material_simulated"] is False
        assert REVIEW["metallic_material_added"] is False

    def test_annotations_live_outside_the_candidate_files(self):
        candidate = {os.path.join(M, "master_it3.png"),
                     os.path.join(M, "master_it3.ai")}
        for item in EVIDENCE["evidence"].values():
            assert os.path.abspath(item["path"]) not in \
                {os.path.abspath(p) for p in candidate}
            assert os.path.dirname(os.path.abspath(item["path"])) == \
                os.path.abspath(E)
        assert EVIDENCE["annotations_outside_candidate"] is True
        assert EVIDENCE["candidate_modified"] is False


class TestNoNewCandidate:
    @pytest.mark.parametrize("name", c1.PROHIBITED_CANDIDATES)
    def test_prohibited_candidate_has_no_artifact(self, name):
        low = name.lower()
        for ext in ("png", "ai", "pdf", "json"):
            assert not os.path.exists(os.path.join(M, f"{low}.{ext}"))
            assert not os.path.exists(os.path.join(M, f"master_{low}.{ext}"))

    def test_withdrawal_code_is_recorded(self):
        assert c1.M3S1_WITHDRAWN.startswith("M3S1_AUTHORIZATION_WITHDRAWN")
        assert REVIEW["prohibited_candidates_absent"] is True

    def test_only_withdrawal_records_may_name_a_prohibited_candidate(self):
        """A record ABOUT the withdrawal is allowed; an ARTIFACT is not."""
        allowed = {"vq1_m3s1_justification_review.json"}
        for f in os.listdir(M):
            low = f.lower()
            if "m3s1" in low or "m3s2" in low:
                assert f in allowed, f
                assert f.endswith(".json"), f


class TestDenseVerificationIsRequired:
    def test_dense_confirmation_uses_every_row_not_the_fit_samples(self):
        assert DENSE["row_density"] == "EVERY_AVAILABLE_ROW_STEP_1"
        assert DENSE["fit_sampling_density"] == "STEP_3"
        assert DENSE["density_ratio"] == 3
        rows = [r["row_px"] for r in DENSE["rows"]]
        assert rows == sorted(rows)
        assert len(rows) == len(set(rows))
        # contiguous: denser data may not be silently thinned
        assert rows == list(range(rows[0], rows[-1] + 1))

    def test_sparse_sample_identity_claim_is_withdrawn_as_vacuous(self):
        assert c1.VACUOUS_METHOD in WD["codes"]
        assert WD["superseded_numbers"]["status"] == "WITHDRAWN_DO_NOT_CITE"
        assert WD["superseded_numbers"]["neck"]["mean"] == 0.00078
        assert "own source" in WD["why_the_claim_was_vacuous"]

    def test_corrected_numbers_are_larger_than_the_withdrawn_ones(self):
        """The correction must not flatter the candidate."""
        old = WD["superseded_numbers"]
        new = WD["corrected_numbers_local_normal_canonical"]
        # both worst-case figures grew: the correction is not flattering
        assert new["neck"]["max"] > old["neck"]["max"]
        assert new["shoulder"]["max"] > old["shoulder"]["max"]
        assert new["neck"]["mean"] > old["neck"]["mean"]

    def test_prior_record_is_preserved_not_rewritten(self):
        assert WD["prior_records_not_rewritten"] is True
        assert os.path.exists(os.path.join(
            M, "vq1_m3s1_justification_review.json"))

    def test_dense_gates_all_pass_on_the_canonical_measure(self):
        assert DENSE["canonical_correspondence"] == "LOCAL_NORMAL_DIRECTION"
        assert DENSE["same_row_retained_as"] == "DIAGNOSTIC_ONLY"
        assert DENSE["all_gates_pass"] is True
        for k, v in DENSE["gate_results"].items():
            assert v is True, k

    def test_same_row_is_never_used_as_the_governing_measure(self):
        for r in DENSE["rows"]:
            assert r["same_row_is_diagnostic_only"] is True
        # the shoulder same-row max is far worse than the canonical one;
        # if same-row ever governed, the conclusion would flip
        assert DENSE["shoulder"]["same_row_diagnostic"]["max"] > \
            DENSE["shoulder"]["local_normal"]["max"] * 3

    def test_no_one_row_spikes(self):
        assert DENSE["neck"]["spikes"]["count"] == 0
        assert DENSE["shoulder"]["spikes"]["count"] == 0

    def test_reference_features_remain_expressed(self):
        assert DENSE["neck_inset"]["m3_inset_px_per_side"] >= 4.0
        assert DENSE["shoulder_convexity"]["both_outward_convex"] is True

    def test_per_row_confidence_is_declared_absent_not_invented(self):
        assert DENSE["contour_confidence_available"] is False
        for r in DENSE["rows"]:
            assert r["contour_confidence"] == c1.NO_CONFIDENCE

    def test_mirrored_far_edge_is_labelled_and_scoped(self):
        for r in DENSE["rows"]:
            assert r["reference_right_edge_provenance"] == c1.MIRROR
        assert "cannot be audited" in DENSE["asymmetry_scope_limit"]

    def test_coarsened_glass_fit_is_disclosed(self):
        assert c1.COARSENED_FIT in WD["codes"]
        d = WD["second_defect_found_while_correcting"]
        assert "max_seg=48" in d["detail"] and "5.1 px" in d["detail"]
        assert "prohibit" in d["why_not_fixed_here"].lower()

    def test_inspector_claim_outside_the_bounded_region_was_measured(self):
        claim = ASSEMBLY["inspector_b_flare_claim"]
        assert claim["verdict"].startswith("CLAIM_CONFIRMED")
        assert claim["measured_local_normal_px_row_495"] == pytest.approx(
            1.842, abs=0.01)
        assert ASSEMBLY["all_bands_within_gates"] is True


class TestScorecardRules:
    IQ = {"passes": True}
    DET = {"neck_is_smooth_waist": True}

    def _card(self, **over):
        base = {c: {"structural_score": 10, "structural_finding": "matches",
                    "critical_structural_blocker": False, "confidence": 0.9,
                    "low_salience_observation": False,
                    "material_observation_excluded": True,
                    "deterministic_evidence_consulted": ["overlay"]}
                for c in insp.CATEGORIES}
        base.update(over)
        return {"scores": base, "verdict": insp.PASSES_PENDING_HUMAN}

    def test_clean_10s_pass(self):
        r = insp.check_scorecard("X", self._card(), self.IQ, self.DET)
        assert r["consistent"] is True
        assert r["all_categories_10"] is True

    def test_low_salience_alone_cannot_lower_a_score(self):
        r = insp.check_scorecard("X", self._card(neck_transition={
            "structural_score": 7,
            "structural_finding": "correct contour but reads faintly",
            "critical_structural_blocker": False, "confidence": 0.8,
            "low_salience_observation": True,
            "material_observation_excluded": True,
            "deterministic_evidence_consulted": ["overlay"]}),
            self.IQ, self.DET)
        assert insp.C_SALIENCE_PENALTY in r["codes"]
        assert r["consistent"] is False

    def test_genuine_contour_criticism_invalidates_a_10(self):
        r = insp.check_scorecard("X", self._card(shoulder_transition={
            "structural_score": 10,
            "structural_finding": "the shoulder roll is missing entirely",
            "critical_structural_blocker": False, "confidence": 0.8,
            "low_salience_observation": False,
            "material_observation_excluded": True,
            "deterministic_evidence_consulted": ["overlay"]}),
            self.IQ, self.DET)
        assert insp.C_TEN_WITH_DEFECT in r["codes"]

    def test_material_observation_may_not_reduce_a_structural_score(self):
        r = insp.check_scorecard("X", self._card(collar_sleeve={
            "structural_score": 6,
            "structural_finding": "no rose-gold metallic finish is present",
            "critical_structural_blocker": False, "confidence": 0.8,
            "low_salience_observation": False,
            "material_observation_excluded": False,
            "deterministic_evidence_consulted": ["overlay"]}),
            self.IQ, self.DET)
        assert insp.C_MATERIAL_LEAK in r["codes"]

    def test_pass_verdict_with_a_sub_10_score_is_rejected(self):
        card = self._card(overall={
            "structural_score": 9, "structural_finding": "good",
            "critical_structural_blocker": False, "confidence": 0.9,
            "low_salience_observation": False,
            "material_observation_excluded": True,
            "deterministic_evidence_consulted": ["overlay"]})
        r = insp.check_scorecard("X", card, self.IQ, self.DET)
        assert insp.C_SCORE_BELOW_10 in r["codes"]

    def test_a_complete_scorecard_is_required(self):
        card = self._card()
        card["scores"].pop("overall")
        r = insp.check_scorecard("X", card, self.IQ, self.DET)
        assert insp.C_MISSING_CATEGORY in r["codes"]
        assert r["all_categories_10"] is False

    def test_every_required_field_is_required(self):
        card = self._card()
        card["scores"]["rounded_dome"].pop("confidence")
        r = insp.check_scorecard("X", card, self.IQ, self.DET)
        assert insp.C_MISSING_FIELD in r["codes"]

    def test_failed_input_quality_blocks_the_scorecard(self):
        r = insp.check_scorecard("X", self._card(), {"passes": False},
                                 self.DET)
        assert insp.C_INPUT_FAILED in r["codes"]

    def test_a_claim_the_dense_reference_refutes_is_flagged(self):
        r = insp.check_scorecard("X", self._card(neck_transition={
            "structural_score": 4,
            "structural_finding": "the stepped ledge is absent",
            "critical_structural_blocker": True, "confidence": 0.8,
            "low_salience_observation": False,
            "material_observation_excluded": True,
            "deterministic_evidence_consulted": []}),
            self.IQ, self.DET)
        assert insp.C_CONTRADICTS_DETERMINISTIC in r["codes"]


class TestInspectorIndependence:
    def test_two_distinct_identities_and_prompts(self):
        assert insp.INSPECTOR_A_ID != insp.INSPECTOR_B_ID
        assert insp.INSPECTOR_A_SYSTEM != insp.INSPECTOR_B_SYSTEM
        assert DUAL["inspections"]["A"]["identity"] == insp.INSPECTOR_A_ID
        assert DUAL["inspections"]["B"]["identity"] == insp.INSPECTOR_B_ID

    def test_b_was_not_shown_a_result(self):
        assert DUAL["inspector_b_saw_inspector_a_result"] is False
        assert DUAL["inspectors_independent"] is True
        for p in (insp.INSPECTOR_A_SYSTEM, insp.INSPECTOR_B_SYSTEM):
            assert "9/10" not in p and "8/10" not in p

    def test_neither_prompt_leaks_a_prior_verdict(self):
        for p in (insp.INSPECTOR_A_SYSTEM, insp.INSPECTOR_B_SYSTEM):
            assert "PASSES_STRUCTURAL_INSPECTION_PENDING_HUMAN_REVIEW" in p
            assert "previously" not in p.lower()

    def test_scope_and_salience_rules_are_in_both_prompts(self):
        for p in (insp.INSPECTOR_A_SYSTEM, insp.INSPECTOR_B_SYSTEM):
            assert insp.SCOPE_RULE in p
            assert insp.SALIENCE_RULE in p
            assert "must NOT judge colour" in p

    def test_no_prompt_permits_a_forbidden_classification(self):
        for p in (insp.INSPECTOR_A_SYSTEM, insp.INSPECTOR_B_SYSTEM):
            assert "Never output HUMAN_ACCEPTED" in p

    def test_matching_verdict_strings_are_not_treated_as_agreement(self):
        a = {"scores": {}, "defect_classifications": [],
             "verdict": insp.PASSES_PENDING_HUMAN}
        b = {"scores": {}, "verdict": insp.PASSES_PENDING_HUMAN,
             "defect_classifications": [
                 {"observation": "x", "classification": insp.TRUE_DEFECT}]}
        d = insp.substantive_disagreement(a, b)
        assert d["disagree_on_geometry_correctness"] is True

    def test_recorded_run_detected_the_real_disagreement(self):
        d = DUAL["substantive_disagreement"]
        assert d["disagree_on_geometry_correctness"] is True
        assert d["inspector_a_true_defects"] == 0
        assert d["inspector_b_true_defects"] == 3


class TestReleaseAndStop:
    def test_the_automatic_layer_hard_stopped_and_that_stays_on_record(self):
        """The owner later accepted VQ-1, but the automatic release layer
        must still show that it refused to pass on its own."""
        assert DUAL["release"]["state"] == c1.HARD_STOP
        assert REVIEW["automatic_release_state_at_close1"] == c1.HARD_STOP
        r = DUAL["release"]["blocking_reasons"]
        assert "INSPECTORS_DISAGREE_ON_GEOMETRY_CORRECTNESS" in r
        assert "INSPECTOR_A_SCORECARD_INCONSISTENT" in r
        assert "INSPECTOR_B_SCORECARD_INCONSISTENT" in r

    def test_acceptance_came_from_the_owner_not_the_automatic_layer(self):
        assert REVIEW["state"] == "VQ1_OWNER_ACCEPTED"
        assert REVIEW["owner_acceptance"]["decided_by"] == "PROJECT_OWNER"
        assert REVIEW["state"] != REVIEW["automatic_release_state_at_close1"]

    def test_release_requires_everything(self):
        ok = {"consistent": True, "verdict": insp.PASSES_PENDING_HUMAN,
              "all_categories_10": True}
        good = insp.release_decision(ok, ok, {"all_gates_pass": True}, True,
                                     {"disagree_on_geometry_correctness":
                                      False})
        assert good["state"] == c1.RELEASE_STATE
        assert good["blocking_reasons"] == []
        bad = insp.release_decision(ok, ok, {"all_gates_pass": False}, True,
                                    {})
        assert bad["state"] == c1.HARD_STOP

    def test_release_never_asserts_forbidden_states(self):
        for rec in (DUAL["release"], REVIEW):
            assert rec["human_accepted"] is False
            assert rec["manufacturable"] is False
            assert rec["production_ready"] is False

    def test_no_record_contains_a_forbidden_classification(self):
        blob = json.dumps([DUAL, REVIEW, FORENSIC, DENSE, ASSEMBLY])
        for bad in ("HUMAN_ACCEPTED", "PRODUCTION_READY"):
            assert bad not in blob


class TestInputQualityFloors:
    def test_close1_floors_are_additive_not_a_mutation_of_v1(self):
        from apps.pipeline.services.visual_input_quality import \
            LEGIBILITY_FLOORS
        assert c1.CLOSE1_FLOORS is not LEGIBILITY_FLOORS
        assert c1.CLOSE1_FLOORS["full_reference"]["min_h"] == 900

    def test_floors_are_checked_against_delivered_bytes(self):
        for slot, row in DUAL["input_quality"]["slots"].items():
            assert row["passes"] is True, slot
            need = row["requirement"]
            dw, dh = row["delivered_size"]
            if "min_h" in need:
                assert dh >= need["min_h"]
            if "min_w" in need:
                assert dw >= need["min_w"]

    def test_a_downscaled_delivery_fails_even_if_native_is_large(self):
        ev = {"wide": {"size": [9000, 400], "sha256": "x"}}
        res = insp.check_floors(ev, {"neck_crop": {"min_h": 600}},
                                {"neck_crop": "wide"})
        assert res["passes"] is False
        assert res["failures"][0]["code"] == "VQ1_INPUT_RESOLUTION_INSUFFICIENT"

    def test_missing_evidence_fails_closed(self):
        res = insp.check_floors({}, {"neck_crop": {"min_h": 600}},
                                {"neck_crop": "absent"})
        assert res["passes"] is False

    def test_enlarged_crops_cannot_pose_as_native(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "a.png")
            Image.new("RGB", (40, 30), (255, 255, 255)).save(src)
            out = c1.enlarge(src, os.path.join(td, "b.png"), 8)
        assert out["is_native_resolution"] is False
        assert out["native_size"] == [40, 30]
        assert out["size"] == [320, 240]
        assert out["resample"] == "NEAREST"


class TestPackages:
    def test_review_package_files_exist(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(M, f"vq1_master_structural_review.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000

    def test_forensic_package_files_exist(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(M, f"vq1_junction_forensics.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000

    def test_all_required_sections_present(self):
        assert REVIEW["sections_present"] >= REVIEW["required_sections"]
        titles = " | ".join(REVIEW["section_titles"]).lower()
        for needed in ("concept #97", "silhouette", "contour overlay",
                       "component mask", "dome", "shaft", "lower-flare",
                       "flare-symmetry", "collar-sleeve", "junction",
                       "neck reference", "enlarged neck", "neck width",
                       "8-pixel inset", "shoulder reference",
                       "enlarged shoulder", "shoulder curvature",
                       "dense row", "deterministic gate", "raster",
                       "inspector a input", "inspector a scorecard",
                       "inspector b input", "inspector b scorecard",
                       "consistency", "low-salience", "vq-3",
                       "production-geometry", "supplier", "human decision"):
            assert needed in titles, needed

    def test_negative_evidence_is_not_hidden(self):
        titles = " | ".join(REVIEW["section_titles"]).lower()
        assert "withdrawal" in titles
        assert REVIEW["blocking_reasons"]
        assert DUAL["substantive_disagreement"][
            "inspector_b_true_defects"] > 0
        assert "TRUE_STRUCTURAL_DEFECT" in json.dumps(DUAL["inspections"])

    def test_forensic_package_covers_the_required_history(self):
        for key in ("historic_junction_failures",
                    "metric_correspondence_correction",
                    "rasterizer_defect_and_fix",
                    "contaminated_inspections_preserved",
                    "structural_only_inspections_preserved",
                    "neck_shoulder_perceptual_diagnosis",
                    "dense_geometry_confirmation",
                    "final_inspection_evidence"):
            assert key in FORENSIC


class TestBoundariesHeld:
    def test_no_image_generation_call(self):
        assert REVIEW["image_generation_calls"] == 0

    def test_supplier_drafts_remain_unsent(self):
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"

    def test_legacy_generators_stay_frozen(self):
        from apps.ire import (vq1_backbone, vq1_corr4, vq1_corr5,
                              vq1_render)
        for mod in (vq1_backbone, vq1_corr4, vq1_corr5, vq1_render):
            assert mod.MAY_EMIT_NEW_CANDIDATE is False

    def test_rendering_evidence_leaves_the_candidate_untouched(self):
        """Re-render the heaviest evidence view and prove M3 is unchanged."""
        import tempfile
        before = _sha(os.path.join(M, "master_it3.png"))
        hw = {int(k): v for k, v in json.load(open(os.path.join(
            M, "reference_halfwidth_px.json"))).items()}
        fit = json.load(open(os.path.join(M, "master_fit_m3.json")))
        with tempfile.TemporaryDirectory() as td:
            out = c1.draw_contour_overlay(os.path.join(td, "o.png"), hw, fit)
            assert os.path.exists(out["path"])
            c1.draw_component_mask(os.path.join(td, "m.png"), fit)
        assert _sha(os.path.join(M, "master_it3.png")) == before == M3_PNG_SHA
