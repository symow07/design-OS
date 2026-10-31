"""VQ-1 final human adjudication and geometry closeout — §10 tests."""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.ire import contour_fit as cf
from apps.ire import vq1_master as vm

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")

ADJ = json.load(open(os.path.join(M, "vq1_human_structural_adjudication.json")))
CONTRACT = json.load(open(os.path.join(M, "vq1_structural_scoring_contract.json")))
FINAL = json.load(open(os.path.join(M, "vq1_final_structural_candidate.json")))
FITDEF = json.load(open(os.path.join(M, "vq1_fitter_defect_and_remediation.json")))
WS = json.load(open(os.path.join(M, "vq1_workstream_state.json")))
WD = json.load(open(os.path.join(M, "vq1_measurement_method_withdrawal.json")))
DENSE = json.load(open(os.path.join(M, "vq1_neck_shoulder_dense_confirmation.json")))
DUAL = json.load(open(os.path.join(M, "vq1_close1_dual_inspection.json")))
REVIEW = json.load(open(os.path.join(M, "vq1_master_structural_review.json")))
FORENSIC = json.load(open(os.path.join(M, "vq1_junction_forensics.json")))

M3_PNG_SHA = "4ecc8e9df1d1"
GATES = {"mean": 0.006, "p95": 0.018, "max": 0.035}


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]


class TestWithdrawalPreserved:
    def test_vacuous_comparison_remains_withdrawn_and_preserved(self):
        assert "VQ1_SAMPLE_IDENTITY_COMPARISON_VACUOUS" in WD["codes"]
        assert WD["superseded_numbers"]["status"] == "WITHDRAWN_DO_NOT_CITE"
        assert os.path.exists(os.path.join(
            M, "vq1_m3s1_justification_review.json"))
        assert WD["prior_records_not_rewritten"] is True

    def test_withdrawal_is_visible_in_both_packages(self):
        titles = " | ".join(REVIEW["section_titles"]).lower()
        assert "withdrawal" in titles
        assert "VQ1_SAMPLE_IDENTITY_COMPARISON_VACUOUS" in json.dumps(FORENSIC)


class TestCorrectedMetricsAreAuthoritative:
    def test_authoritative_values_match_the_ruling(self):
        n = DENSE["neck"]["local_normal"]
        s = DENSE["shoulder"]["local_normal"]
        assert n["mean"] == pytest.approx(0.001996, abs=1e-6)
        assert n["p95"] == pytest.approx(0.003370, abs=1e-6)
        assert n["max"] == pytest.approx(0.004073, abs=1e-6)
        assert s["mean"] == pytest.approx(0.001011, abs=1e-6)
        assert s["p95"] == pytest.approx(0.003673, abs=1e-6)
        assert s["max"] == pytest.approx(0.004197, abs=1e-6)

    def test_authority_is_the_emitted_curve_not_the_input_samples(self):
        method = WD["corrected_numbers_local_normal_canonical"]["method"]
        assert "fitted Bezier" in method and "EVERY reference row" in method
        assert DENSE["canonical_correspondence"] == "LOCAL_NORMAL_DIRECTION"

    def test_all_gates_pass_under_the_authoritative_measure(self):
        for block in (DENSE["neck"]["local_normal"],
                      DENSE["shoulder"]["local_normal"]):
            assert block["mean"] <= GATES["mean"]
            assert block["p95"] <= GATES["p95"]
            assert block["max"] <= GATES["max"]

    def test_final_record_carries_the_same_authoritative_metrics(self):
        m = FINAL["authoritative_metrics"]
        assert m["neck_local_normal"] == DENSE["neck"]["local_normal"]
        assert m["shoulder_local_normal"] == DENSE["shoulder"]["local_normal"]
        assert m["result"] == "PASS"


class TestNoThresholdLoweredNoRowExcluded:
    def test_gates_are_unchanged(self):
        assert DENSE["gates"]["neck_mean"] == GATES["mean"]
        assert DENSE["gates"]["neck_max"] == GATES["max"]
        assert DENSE["gates"]["shoulder_p95"] == GATES["p95"]
        assert CONTRACT["gates"] == GATES
        assert CONTRACT["gates_lowered"] is False

    def test_no_row_was_excluded(self):
        assert CONTRACT["rows_excluded"] is False
        rows = [r["row_px"] for r in DENSE["rows"]]
        assert rows == list(range(rows[0], rows[-1] + 1))

    def test_sub_threshold_residuals_remain_visible_in_reports(self):
        vals = {d["measured_px"] for d in ADJ["disputed_deviations"]}
        assert {0.7, 1.44, 1.84} <= vals
        blob = json.dumps(REVIEW) + json.dumps(FORENSIC)
        for v in ("0.7", "1.44", "1.84"):
            assert v in blob
        assert "sub-2-pixel residual table" in " | ".join(
            REVIEW["closeout_sections"]).lower()


class TestHumanAdjudication:
    def test_ruling_codes_recorded(self):
        for c in ("VQ1_WITHIN_TOLERANCE_CONTOUR_RESIDUAL",
                  "VQ1_NONBLOCKING_SUBPIXEL_STRUCTURAL_DEVIATION",
                  "VQ1_INSPECTOR_DISAGREEMENT_RESOLVED_BY_HUMAN_TOLERANCE_"
                  "RULING"):
            assert c in ADJ["codes"]
        assert ADJ["determination"] == "NON_BLOCKING"
        assert ADJ["record_type"] == "human_structural_adjudication/1.0"

    def test_adjudication_does_not_rewrite_inspector_responses(self):
        assert ADJ["inspector_responses_rewritten"] is False
        assert ADJ["inspector_scores_changed"] is False
        assert ADJ["inspector_observations_removed"] is False
        # the live inspection record still holds the original sub-10 scores
        for side in ("A", "B"):
            scores = DUAL["inspections"][side]["consistency"]["scores"]
            assert any(v < 10 for v in scores.values())
            assert scores == ADJ["preserved_inspector_records"][side]["scores"]

    def test_pass_verdicts_remain_invalid_under_the_automatic_rule(self):
        p = ADJ["preserved_inspector_records"]
        assert p["both_pass_verdicts_remain_invalid_under_automatic_rule"] \
            is True
        for side in ("A", "B"):
            assert DUAL["inspections"][side]["consistency"]["codes"]

    def test_acceptance_layer_is_human_not_model_agreement(self):
        assert ADJ["acceptance_layer"] == \
            "HUMAN_ADJUDICATION_NOT_RETROACTIVE_MODEL_AGREEMENT"
        assert ADJ["may_not_be_classified_as"] == "TRUE_STRUCTURAL_DEFECT"

    def test_every_disputed_deviation_is_inside_its_gate(self):
        assert len(ADJ["disputed_deviations"]) == 3
        for d in ADJ["disputed_deviations"]:
            assert d["inside_gate"] is True
            assert d["measured_against_gate"] <= GATES["max"]
            assert d["reference_uncertainty_px"] == 0.5

    def test_absence_of_topological_failure_is_recorded_explicitly(self):
        a = ADJ["absence_of_topological_or_semantic_failure"]
        for k in ("incorrect_component", "topology_change", "gap", "step",
                  "discontinuity", "asymmetry", "visible_fallback",
                  "unsupported_visible_object", "one_row_spike"):
            assert a[k] is False
        assert a["neck_inset_present"] is True
        assert a["shoulder_convex_outward"] is True

    def test_adjudication_never_asserts_forbidden_states(self):
        for k in ("human_accepted", "manufacturable", "production_ready"):
            assert ADJ[k] is False


class TestScoringContract:
    def test_ten_means_within_declared_tolerance(self):
        assert CONTRACT["ten_of_ten_means"] == \
            "MEETS_REFERENCE_WITHIN_DECLARED_STRUCTURAL_TOLERANCE"
        assert "pixel-for-pixel identity" in CONTRACT["ten_of_ten_does_not_mean"]
        assert CONTRACT["sub_threshold_residual_alone_blocks_ten"] is False

    def test_all_qualifying_conditions_present(self):
        joined = " ".join(CONTRACT["qualifying_conditions"]).lower()
        for needed in ("deterministic gates pass", "reference uncertainty",
                       "actionable visible structural defect",
                       "component-family mismatch", "topology error",
                       "unsupported visible object",
                       "human-rejected fallback"):
            assert needed in joined

    def test_historical_scores_not_rewritten(self):
        assert CONTRACT["historical_inspector_scores_rewritten"] is False

    def test_contract_never_licenses_forbidden_states(self):
        for bad in ("HUMAN_ACCEPTED", "MANUFACTURABLE", "PRODUCTION_READY"):
            assert bad in CONTRACT["ten_of_ten_does_not_mean"]


class TestM3FinalState:
    def test_m3_byte_identical(self):
        assert _sha(os.path.join(M, "master_it3.png")) == M3_PNG_SHA
        assert FINAL["identity_sha256_png"] == M3_PNG_SHA
        assert FINAL["frozen_byte_identical"] is True

    def test_final_classification(self):
        assert "VQ1_FINAL_STRUCTURAL_CANDIDATE" in FINAL["classification"]
        assert "VQ1_GEOMETRY_COMPLETE_PENDING_OWNER_ACCEPTANCE" in \
            FINAL["classification"]
        assert FINAL["candidate_loop_state"] == "CLOSED"

    def test_m3_is_not_production_geometry(self):
        assert FINAL["geometry_authority"] == "CONCEPT_VISUAL_GEOMETRY_ONLY"
        for k in ("is_manufacturable", "is_tooling_ready",
                  "is_production_geometry", "human_accepted"):
            assert FINAL[k] is False

    @pytest.mark.parametrize("name", ["M3S1", "M3S2", "M5", "M6", "RIM2"])
    def test_no_new_candidate_artifact_exists(self, name):
        assert name in FINAL["prohibited_new_candidates"]
        low = name.lower()
        for ext in ("png", "ai", "pdf"):
            assert not os.path.exists(os.path.join(M, f"{low}.{ext}"))
            assert not os.path.exists(os.path.join(M, f"master_{low}.{ext}"))

    def test_no_stray_candidate_files_appeared(self):
        allowed = {"vq1_m3s1_justification_review.json"}
        for f in os.listdir(M):
            low = f.lower()
            if any(t in low for t in ("m3s1", "m3s2", "rim2", "master_m5",
                                      "master_m6")):
                assert f in allowed, f


class TestFitterDefectDisclosed:
    def test_defect_codes_recorded(self):
        for c in ("VQ_FIT_CUBICS_COARSENING_BYPASSES_TOLERANCE",
                  "VQ_FITTER_SEGMENT_CAP_FAILS_TO_PRESERVE_ERROR_BOUND"):
            assert c in FITDEF["codes"]
            assert c in vm.LEGACY_FIT_DEFECTS
        assert FITDEF["defect"]["is_real_tooling_defect"] is True

    def test_legacy_fitter_is_marked_but_left_byte_stable(self):
        assert vm.LEGACY_FIT_STATE == "LEGACY_REPRODUCTION_ONLY_DEFECT_DISCLOSED"
        assert vm.CORRECTED_FITTER == "apps.ire.contour_fit.fit_contour"
        assert "DO NOT USE FOR NEW RECONSTRUCTIONS" in vm.fit_cubics.__doc__

    def test_legacy_behaviour_is_unchanged_so_m3_reproduces(self):
        """The v1 coarsening branch must still fire exactly as it did."""
        hw = {int(k): v for k, v in json.load(open(os.path.join(
            M, "reference_halfwidth_px.json"))).items()}
        s = vm.extract_component_samples(hw, vm.BANDS["GLASS"])
        out = vm.fit_cubics(s, tol=0.6)
        stored = json.load(open(os.path.join(
            M, "master_fit_m3.json")))["fits"]["GLASS"]
        assert out["segment_count"] == stored["segment_count"] == 57
        assert out["residual_max"] == stored["residual_max"] == 5.1
        assert out["sample_count"] == 229

    def test_why_m3_remains_valid_is_recorded(self):
        joined = " ".join(FITDEF["why_m3_remains_valid"]).lower()
        assert "74 degrees" in joined and "noncanonical" in joined
        assert "1.44" in joined


class TestCorrectedFitter:
    #: a long, steep, high-curvature contour that exceeds the default cap
    @staticmethod
    def _hard_samples():
        import math
        return [(60 + 40 * math.sin(i / 9.0) + i * 0.35, float(i))
                for i in range(240)]

    def test_never_uses_uniform_chunking(self):
        r = cf.fit_contour(self._hard_samples(), tol=0.6)
        assert r["uniform_chunking_used"] is False

    def test_cap_growth_preserves_tolerance(self):
        r = cf.fit_contour(self._hard_samples(), tol=0.6, max_seg=48,
                           allow_cap_growth=True)
        assert r["segment_count"] > 48
        assert r["segment_cap_raised"] is True
        assert r["status"] == "SEGMENT_CAP_RAISED_TOLERANCE_PRESERVED"
        assert r["tolerance_enforced"] is True
        assert r["residual_max_parameter_matched"] <= 0.6

    def test_fails_closed_when_tolerance_cannot_be_met(self):
        r = cf.fit_contour(self._hard_samples(), tol=0.05, max_seg=8,
                           allow_cap_growth=False)
        assert r["status"] == cf.TOLERANCE_NOT_ACHIEVED
        assert r["tolerance_enforced"] is False
        assert r["diagnostic"] == cf.TOLERANCE_NOT_ACHIEVED
        assert "silently substituted uniform chunks" in r["diagnostic_detail"]

    def test_hard_ceiling_also_fails_closed(self):
        r = cf.fit_contour(self._hard_samples(), tol=0.01, max_seg=4,
                           allow_cap_growth=True, hard_ceiling=6)
        assert r["status"] == cf.TOLERANCE_NOT_ACHIEVED
        assert r["tolerance_enforced"] is False

    def test_reports_the_full_provenance_contract(self):
        r = cf.fit_contour(self._hard_samples(), tol=0.6)
        for k in ("segment_count", "residual_max_parameter_matched",
                  "residual_max_local_normal", "correspondence_method",
                  "tolerance_enforced", "provenance"):
            assert k in r
        assert r["correspondence_method"] == cf.LOCAL_NORMAL
        p = r["provenance"]
        for k in ("fitter", "policy", "tolerance_px", "tolerance_enforced",
                  "segment_count", "correspondence_method"):
            assert k in p

    def test_steep_transition_local_normal_is_below_same_row(self):
        """At a steep contour SAME_ROW overstates the gap; the corrected
        fitter reports the canonical perpendicular distance."""
        steep = [(float(i) * 6.0, float(i)) for i in range(40)]
        r = cf.fit_contour(steep, tol=0.6)
        poly = cf._polyline(r["start"], r["segments"])
        pt = (steep[20][0] + 3.0, steep[20][1])
        normal = cf.point_to_polyline(pt, poly)
        assert normal < 3.0

    def test_high_curvature_region_meets_tolerance(self):
        import math
        arc = [(30 * math.cos(t / 60.0 * math.pi / 2),
                30 * math.sin(t / 60.0 * math.pi / 2)) for t in range(61)]
        r = cf.fit_contour(arc, tol=0.3)
        assert r["tolerance_enforced"] is True
        assert r["residual_max_parameter_matched"] <= 0.3

    def test_glass_length_input_exceeding_max_seg(self):
        hw = {int(k): v for k, v in json.load(open(os.path.join(
            M, "reference_halfwidth_px.json"))).items()}
        s = vm.extract_component_samples(hw, vm.BANDS["GLASS"])
        r = cf.fit_contour(s, tol=0.6, max_seg=48)
        assert r["sample_count"] == 229
        assert r["tolerance_enforced"] is True
        assert r["uniform_chunking_used"] is False
        assert r["residual_max_local_normal"] < 5.1

    def test_short_input_is_handled(self):
        r = cf.fit_contour([(0.0, 0.0), (1.0, 1.0)], tol=0.6)
        assert r["segment_count"] == 0
        assert r["tolerance_enforced"] is True


class TestFitterFixDoesNotTouchM3:
    def test_shadow_diagnostic_is_non_authoritative(self):
        sd = FITDEF["shadow_diagnostic"]
        assert sd["authoritative"] is False
        assert sd["creates_candidate"] is False
        assert sd["changes_candidate_status"] is False
        assert sd["on_release_path"] is False

    def test_shadow_quantifies_the_defect_without_licensing_a_refit(self):
        sd = FITDEF["shadow_diagnostic"]
        assert sd["legacy"]["tolerance_enforced"] is False
        assert sd["legacy"]["uniform_chunking_used"] is True
        assert sd["corrected"]["tolerance_enforced"] is True
        assert sd["corrected"]["residual_max_local_normal"] < \
            sd["legacy"]["measured_residual_max_local_normal"]
        assert "does not reopen VQ-1" in sd["interpretation"]

    def test_m3_was_not_regenerated(self):
        assert FITDEF["remediation"]["applies_to"] == \
            "FUTURE_RECONSTRUCTIONS_ONLY"
        assert FITDEF["remediation"]["legacy_left_byte_stable"] is True
        assert REVIEW["m3_regenerated"] is False
        assert _sha(os.path.join(M, "master_it3.png")) == M3_PNG_SHA

    def test_prohibited_side_effects_listed(self):
        joined = " ".join(FITDEF["must_not"]).lower()
        for needed in ("regenerate m3", "change m3 paths",
                       "reopen the vq-1 candidate loop",
                       "change historical hashes"):
            assert needed in joined

    def test_corrected_fitter_is_not_wired_into_the_vq1_path(self):
        src = open(os.path.join(settings.BASE_DIR, "apps", "ire",
                                "vq1_master.py")).read()
        assert "from apps.ire.contour_fit import" not in src
        assert "contour_fit.fit_contour(" not in src


class TestPackagesAndWorkstream:
    def test_all_twelve_closeout_sections_present(self):
        titles = " | ".join(REVIEW["closeout_sections"]).lower()
        for needed in ("withdrawal", "corrected fitted-curve",
                       "dense assembly-wide", "sub-2-pixel residual table",
                       "deterministic gates", "inspector disagreement",
                       "human tolerance ruling", "final m3 geometry freeze",
                       "fit_cubics tooling defect",
                       "future-only fitter remediation",
                       "production-geometry blocker", "owner acceptance"):
            assert needed in titles, needed
        assert len(REVIEW["closeout_sections"]) == 12

    def test_package_files_regenerated(self):
        for stem in ("vq1_master_structural_review",
                     "vq1_junction_forensics"):
            for ext in ("pdf", "png", "json"):
                p = os.path.join(M, f"{stem}.{ext}")
                assert os.path.exists(p) and os.path.getsize(p) > 2000

    def test_original_error_is_not_hidden(self):
        blob = json.dumps(REVIEW) + json.dumps(FORENSIC)
        assert "VQ1_SAMPLE_IDENTITY_COMPARISON_VACUOUS" in blob
        assert "VQ_FIT_CUBICS_COARSENING_BYPASSES_TOLERANCE" in blob

    def test_workstream_states_after_owner_acceptance(self):
        """Owner acceptance unblocked VQ-2/VQ-3 but started neither, and it
        is explicitly not production authority."""
        assert WS["PRODUCTION_GEOMETRY"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert WS["VQ_2"].startswith("STARTED_VQ2")  # explicit owner start
        assert WS["VQ_3"] == "UNBLOCKED_PENDING_EXPLICIT_START"
        assert WS["auto_start_permitted"] is False
        assert WS["vq3_started"] is False
        assert WS["supplier_drafts_sent"] is False

    def test_no_record_asserts_a_forbidden_state(self):
        """Naming a forbidden state in order to prohibit it is fine; the
        test is that nothing ever ASSERTS one."""
        blob = json.dumps([ADJ, CONTRACT, FINAL, FITDEF, WS, REVIEW]).lower()
        for field in ("human_accepted", "manufacturable", "production_ready",
                      "is_manufacturable", "is_production_geometry",
                      "is_tooling_ready"):
            assert f'"{field}": true' not in blob
        # and the contract names them only to exclude them
        assert "PRODUCTION_READY" in CONTRACT["ten_of_ten_does_not_mean"]


class TestBoundariesHeld:
    def test_no_image_generation_call(self):
        assert REVIEW["image_generation_calls"] == 0

    def test_supplier_drafts_remain_unsent(self):
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])
        assert WS["SUPPLIER_DRAFTS"] == "DRAFTED_READY_FOR_HUMAN_SEND"

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
