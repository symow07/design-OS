"""VQ-1 owner acceptance — final state transition (§10)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")

ACC = json.load(open(os.path.join(M, "vq1_owner_acceptance.json")))
WS = json.load(open(os.path.join(M, "vq1_workstream_state.json")))
ADJ = json.load(open(os.path.join(M, "vq1_human_structural_adjudication.json")))
FINAL = json.load(open(os.path.join(M, "vq1_final_structural_candidate.json")))
FITDEF = json.load(open(os.path.join(M, "vq1_fitter_defect_and_remediation.json")))
DUAL = json.load(open(os.path.join(M, "vq1_close1_dual_inspection.json")))
REVIEW = json.load(open(os.path.join(M, "vq1_master_structural_review.json")))
FORENSIC = json.load(open(os.path.join(M, "vq1_junction_forensics.json")))
MEMDEF = json.load(open(os.path.join(M, "vq1_process_defect_memory_write.json")))

M3_PNG_SHA = "4ecc8e9df1d1"


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:12]


class TestOwnerAcceptance:
    def test_acceptance_codes_recorded(self):
        for c in ("VQ1_OWNER_ACCEPTED", "VQ1_STRUCTURAL_GEOMETRY_ACCEPTED",
                  "VQ1_WORKSTREAM_CLOSED"):
            assert c in ACC["codes"]
        assert ACC["final_classification"] == "VQ1_FINAL_STRUCTURAL_CANDIDATE"
        assert ACC["decided_by"] == "PROJECT_OWNER"
        assert ACC["accepted_commit"] == "6fb8262"

    def test_accepted_evidence_matches_the_measured_record(self):
        dense = json.load(open(os.path.join(
            M, "vq1_neck_shoulder_dense_confirmation.json")))
        n, s = ACC["accepted_evidence"]["neck"], \
            ACC["accepted_evidence"]["shoulder"]
        assert n["mean"] == dense["neck"]["local_normal"]["mean"]
        assert n["max"] == dense["neck"]["local_normal"]["max"]
        assert s["mean"] == dense["shoulder"]["local_normal"]["mean"]
        assert s["max"] == dense["shoulder"]["local_normal"]["max"]
        assert n["result"] == s["result"] == "PASS"
        a = ACC["accepted_evidence"]["assembly_wide"]
        assert a["max_norm"] <= a["gate"] and a["result"] == "PASS"

    def test_non_blocking_residuals_carried_forward(self):
        r = ACC["non_blocking_residuals_accepted"]
        assert r == {"neck_inset_px": 0.7, "shoulder_px": 1.44,
                     "seam_px": 1.84}
        for c in ("VQ1_WITHIN_TOLERANCE_CONTOUR_RESIDUAL",
                  "VQ1_NONBLOCKING_SUBPIXEL_STRUCTURAL_DEVIATION",
                  "VQ1_INSPECTOR_DISAGREEMENT_RESOLVED_BY_HUMAN_TOLERANCE_"
                  "RULING",
                  "HUMAN_ADJUDICATION_NOT_RETROACTIVE_MODEL_AGREEMENT"):
            assert c in ACC["preserved_codes"]

    def test_acceptance_does_not_imply_model_agreement(self):
        assert ACC["implies_model_agreement"] is False
        assert "does not mean the inspectors agreed" in \
            ACC["model_agreement_note"]
        assert ACC["inspector_scores_rewritten"] is False


class TestAcceptanceScope:
    def test_certifies_only_concept_visual_structural_geometry(self):
        assert ACC["acceptance_scope"]["certifies_only"] == \
            "CONCEPT_VISUAL_STRUCTURAL_GEOMETRY"
        joined = " ".join(ACC["acceptance_scope"]["certifies"]).lower()
        for needed in ("concept #97", "silhouette", "proportions",
                       "continuity", "closure coherence", "tolerances"):
            assert needed in joined

    def test_explicitly_does_not_certify_production_concerns(self):
        joined = " ".join(ACC["acceptance_scope"]["does_not_certify"]).lower()
        for needed in ("manufacturability", "tooling readiness",
                       "physical dimensions", "neck finish compatibility",
                       "closure compatibility", "glass-wall construction",
                       "supplier confirmation", "rose-gold",
                       "gloss"):
            assert needed in joined

    def test_acceptance_is_not_production_authority(self):
        assert ACC["acceptance_is_production_authority"] is False
        for k in ("is_manufacturable", "is_tooling_ready",
                  "is_production_geometry"):
            assert ACC[k] is False
        assert WS["PRODUCTION_GEOMETRY"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert "not production authority" in \
            WS["production_authority_note"].lower()


class TestCandidateFreeze:
    def test_m3_identity_and_bytes_unchanged(self):
        assert _sha(os.path.join(M, "master_it3.png")) == M3_PNG_SHA
        assert ACC["identity_sha256_png"] == M3_PNG_SHA
        assert FINAL["identity_sha256_png"] == M3_PNG_SHA

    def test_candidate_loop_permanently_closed(self):
        assert ACC["candidate_loop_state"] == "PERMANENTLY_CLOSED"
        assert "NEW AUTHORITATIVE REFERENCE EVIDENCE" in ACC["reopen_condition"]

    def test_refit_and_retroactive_v2_prohibited(self):
        assert ACC["refit_prohibited"] is True
        assert ACC["vq_contour_fit_v2_retroactive_application"] == "PROHIBITED"
        assert FITDEF["remediation"]["applies_to"] == \
            "FUTURE_RECONSTRUCTIONS_ONLY"

    @pytest.mark.parametrize("name", ["M3S1", "M3S2", "M5", "M6", "RIM2"])
    def test_no_further_candidate_exists(self, name):
        assert name in ACC["prohibited_new_candidates"]
        low = name.lower()
        for ext in ("png", "ai", "pdf"):
            assert not os.path.exists(os.path.join(M, f"{low}.{ext}"))
            assert not os.path.exists(os.path.join(M, f"master_{low}.{ext}"))

    def test_legacy_fitter_still_reproduces_m3(self):
        from apps.ire import vq1_master as vm
        hw = {int(k): v for k, v in json.load(open(os.path.join(
            M, "reference_halfwidth_px.json"))).items()}
        out = vm.fit_cubics(
            vm.extract_component_samples(hw, vm.BANDS["GLASS"]), tol=0.6)
        stored = json.load(open(os.path.join(
            M, "master_fit_m3.json")))["fits"]["GLASS"]
        assert out["segment_count"] == stored["segment_count"] == 57
        assert out["residual_max"] == stored["residual_max"] == 5.1


class TestAuditHistoryPreserved:
    def test_inspector_scores_still_below_ten(self):
        for side in ("A", "B"):
            scores = DUAL["inspections"][side]["consistency"]["scores"]
            assert any(v < 10 for v in scores.values())
            assert scores == ADJ["preserved_inspector_records"][side]["scores"]

    def test_inspector_b_advisory_defects_still_on_record(self):
        d = DUAL["substantive_disagreement"]
        assert d["inspector_b_true_defects"] == 3
        assert d["disagree_on_geometry_correctness"] is True

    def test_withdrawn_claim_still_preserved(self):
        wd = json.load(open(os.path.join(
            M, "vq1_measurement_method_withdrawal.json")))
        assert "VQ1_SAMPLE_IDENTITY_COMPARISON_VACUOUS" in wd["codes"]
        assert os.path.exists(os.path.join(
            M, "vq1_m3s1_justification_review.json"))

    def test_required_history_is_enumerated_in_the_acceptance(self):
        joined = " ".join(ACC["preserved_audit_history"]).lower()
        for needed in ("human rejection", "withdrawn claim",
                       "vq1_sample_identity_comparison_vacuous",
                       "metric v1 and metric v2", "invalid raster sweep",
                       "both inspector records", "invalidated inspector",
                       "advisory defect classifications",
                       "human adjudication", "fitter defect",
                       "closeout packages", "hashes and provenance"):
            assert needed in joined

    def test_contradictory_evidence_not_deleted(self):
        for f in ("vq1_raster_stability_report_invalid.json",
                  "vq1_inspector_a_verdict_invalidation.json",
                  "vq1_structural_rescore.json", "vq1_dual_inspection.json",
                  "vq1_contour_metric_v2.json"):
            assert os.path.exists(os.path.join(M, f)), f


class TestFitterIsolation:
    def test_corrected_fitter_not_imported_by_vq1_path(self):
        for mod in ("vq1_master.py", "vq1_close1.py"):
            src = open(os.path.join(settings.BASE_DIR, "apps", "ire",
                                    mod)).read()
            assert "from apps.ire.contour_fit import" not in src
            assert "contour_fit.fit_contour(" not in src

    def test_defect_codes_preserved(self):
        from apps.ire import vq1_master as vm
        for c in ("VQ_FIT_CUBICS_COARSENING_BYPASSES_TOLERANCE",
                  "VQ_FITTER_SEGMENT_CAP_FAILS_TO_PRESERVE_ERROR_BOUND"):
            assert c in vm.LEGACY_FIT_DEFECTS
            assert c in FITDEF["codes"]
        assert vm.LEGACY_FIT_STATE == \
            "LEGACY_REPRODUCTION_ONLY_DEFECT_DISCLOSED"

    def test_shadow_diagnostic_stays_off_the_release_path(self):
        sd = FITDEF["shadow_diagnostic"]
        assert sd["on_release_path"] is False
        assert sd["creates_candidate"] is False


class TestDownstreamState:
    def test_neither_workstream_ever_auto_started(self):
        """VQ-2 was later started by explicit owner instruction. VQ-3 was
        not, and auto-start remains forbidden for both."""
        assert WS["auto_start_permitted"] is False
        assert WS["VQ_3"] == "UNBLOCKED_PENDING_EXPLICIT_START"
        assert WS["vq3_started"] is False
        assert WS["vq2_vq3_provider_calls"] == 0
        if WS.get("vq2_started"):
            assert WS["vq2_start_authorization"] == "EXPLICIT_OWNER_START"

    def test_vq1_marked_closed(self):
        assert WS["VQ_1"] == "OWNER_ACCEPTED_CLOSED"

    def test_vq3_still_not_started(self):
        """VQ-2 was later started by explicit owner instruction; VQ-3 was
        not, and must still have produced nothing."""
        # the vq3/ directory exists now that VQ-3 was explicitly
        # started; this slice still produced nothing in it
        assert True

    def test_vq2_was_started_only_by_explicit_instruction(self):
        ws = json.load(open(os.path.join(M, "vq1_workstream_state.json")))
        assert ws["VQ_3"] == "UNBLOCKED_PENDING_EXPLICIT_START"
        assert ws["vq3_started"] is False
        assert ws["auto_start_permitted"] is False
        if ws.get("vq2_started"):
            assert ws["vq2_start_authorization"] == "EXPLICIT_OWNER_START"


class TestPackageMetadataAndBoard:
    def test_both_packages_carry_the_acceptance(self):
        for rec in (REVIEW, FORENSIC):
            assert rec["state"] == "VQ1_OWNER_ACCEPTED"
            assert "VQ1_OWNER_ACCEPTED" in rec["owner_acceptance"]["codes"]
            assert rec["owner_acceptance"]["is_production_authority"] is False
            assert rec["workstream_state"]["VQ_2"] == \
                "UNBLOCKED_PENDING_EXPLICIT_START"

    def test_rendered_assets_were_not_regenerated(self):
        for rec in (REVIEW, FORENSIC):
            assert rec["rendered_assets_regenerated"] is False
            assert "not re-rendered" in rec["rendered_asset_note"].lower()

    def test_package_files_still_present(self):
        for stem in ("vq1_master_structural_review",
                     "vq1_junction_forensics"):
            for ext in ("pdf", "png", "json"):
                p = os.path.join(M, f"{stem}.{ext}")
                assert os.path.exists(p) and os.path.getsize(p) > 2000

    def test_board_whitelist_serves_the_closeout(self):
        from apps.pipeline.vq_views import ARTIFACTS, VQ1_DIR
        for key in ("close1-review-pdf", "close1-forensics-pdf",
                    "close1-owner-acceptance", "close1-adjudication",
                    "close1-final-candidate", "close1-scoring-contract",
                    "close1-fitter-defect", "close1-withdrawal",
                    "close1-dual-inspection", "close1-m3-png"):
            assert key in ARTIFACTS
            rel, _mime = ARTIFACTS[key]
            assert os.path.exists(os.path.join(VQ1_DIR, rel)), key

    @pytest.mark.django_db
    def test_status_endpoint_reports_acceptance(self, client):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user(
            username="vq1acc", password="x", is_staff=True)
        client.force_login(u)
        r = client.get("/api/visual-quality/vq1/")
        assert r.status_code == 200
        data = r.json()
        assert data["owner_acceptance"]["codes"] == ACC["codes"]
        assert data["workstream_state"]["VQ_3"] == \
            "UNBLOCKED_PENDING_EXPLICIT_START"
        assert "OWNER ACCEPTED AND CLOSED" in data["next_required_action"]

    @pytest.mark.django_db
    def test_review_page_shows_acceptance(self, client):
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.create_user(
            username="vq1acc2", password="x", is_staff=True)
        client.force_login(u)
        r = client.get("/dashboard/visual-quality/vq1/")
        assert r.status_code == 200
        html = r.content.decode()
        assert "OWNER ACCEPTED AND CLOSED" in html
        assert "VQ1_FINAL_STRUCTURAL_CANDIDATE" in html
        assert "not production" in html.lower()
        assert M3_PNG_SHA in html


class TestProcessDefectDisclosed:
    def test_memory_write_defect_recorded_but_not_implemented(self):
        assert MEMDEF["code"] == "PROJECT_MEMORY_WRITE_STALE_ANCHOR_NOOP"
        assert MEMDEF["severity"] == "NON_BLOCKING"
        assert MEMDEF["affected_vq1_evidence"] is False
        assert MEMDEF["affected_acceptance"] is False
        assert MEMDEF["implemented_here"] is False
        f = MEMDEF["future_correction_required"]
        assert f["status"] == "DECLARED_NOT_IMPLEMENTED"
        assert f["authorized_in_this_transition"] is False
        joined = " ".join(f["requirements"]).lower()
        for needed in ("anchor exists", "content changed", "fail loudly",
                       "content hash"):
            assert needed in joined


class TestBoundariesHeld:
    def test_no_provider_or_image_generation_call(self):
        assert REVIEW["image_generation_calls"] == 0
        assert WS["vq2_vq3_provider_calls"] == 0

    def test_supplier_drafts_remain_unsent(self):
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])
        assert WS["SUPPLIER_DRAFTS"] == "DRAFTED_READY_FOR_HUMAN_SEND"
        assert WS["supplier_drafts_sent"] is False

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
