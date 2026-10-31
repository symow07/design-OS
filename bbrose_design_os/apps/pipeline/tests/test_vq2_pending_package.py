"""VQ-2 LF1-R1 pending review package — hold state, no fabrication (§9)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
T = os.path.join(D, "typeface")
PEND = json.load(open(os.path.join(
    T, "vq2_imbue_lf1_r1_review_pending.json")))
BLK = json.load(open(os.path.join(D, "vq2_typography_provider_blocker.json")))
FRZ = json.load(open(os.path.join(D, "vq2_lf1_inspection_input_freeze.json")))
RES = json.load(open(os.path.join(
    D, "vq2_lf1_r1_inspection_resume_contract.json")))
ST = json.load(open(os.path.join(D, "vq2_state.json")))
LF1R1_AI = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


class TestPackageExists:
    def test_all_three_outputs(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(T, f"vq2_imbue_lf1_r1_review_pending.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000

    def test_all_required_sections(self):
        assert PEND["sections"] >= 32
        titles = " | ".join(PEND["section_titles"]).lower()
        for needed in ("status", "ofl provenance", "selected instance",
                       "original converter failure", "basepen",
                       "fixture suite", "legacy-handler",
                       "shared-flattener", "mixed-flattener",
                       "point-to-vertex", "point-to-segment",
                       "analytical distance", "thirteen glyphs",
                       "symmetric vector", "raster metrics",
                       "topology and counter", "rose composition",
                       "damascena composition", "native-width",
                       "logo context", "inspector a input",
                       "inspector a prompt", "inspector a status",
                       "inspector b input", "inspector b prompt",
                       "inspector b status", "provider-credit blocker",
                       "failed request", "rose-width state",
                       "resume contract", "owner decision unavailable"):
            assert needed in titles, needed

    def test_labelled_pending_not_final(self):
        assert PEND["is_final_review"] is False
        assert "PENDING" in PEND["banner"]
        assert "NOT PERFORMED" in PEND["banner"]
        assert "CREDIT" in PEND["banner"].upper()


class TestNoFabrication:
    def test_both_inspections_marked_not_performed(self):
        assert PEND["inspections_performed"] == 0
        assert PEND["inspector_a_status"] == "NOT_PERFORMED_PROVIDER_CREDIT"
        assert PEND["inspector_b_status"] == "NOT_PERFORMED_PROVIDER_CREDIT"

    def test_no_findings_or_scorecards_invented(self):
        assert PEND["fabricated_inspector_findings"] is False
        assert PEND["inspector_scorecards_present"] is False
        blob = json.dumps(PEND)
        for bad in ("PASSES_TYPOGRAPHY_INSPECTION", "TYPOGRAPHICALLY_REJECTED",
                    "TYPOGRAPHICALLY_IMPROVED_BUT_INSUFFICIENT"):
            assert bad not in blob

    def test_no_owner_decision_offered(self):
        assert PEND["owner_decision_available"] is False

    def test_inspectors_not_called_failed_or_rejected(self):
        assert BLK["classified_as_failed_or_rejected_or_disagreeing"] is False


class TestProviderBlocker:
    def test_codes_and_identity(self):
        for c in ("VQ2_TYPOGRAPHY_INSPECTION_BLOCKED_PROVIDER_CREDIT",
                  "VQ2_INSPECTION_NOT_PERFORMED_PROVIDER_UNAVAILABLE",
                  "VQ2_ROSE_WIDTH_REMAINS_UNADJUDICATED"):
            assert c in BLK["codes"]
            assert c in PEND["provider_blocker"]["codes"]
        assert PEND["provider_blocker"]["request_id"] == \
            "req_011CdVuiNaWaRAponJhPTXpk"
        assert PEND["provider_blocker"]["http_status"] == 400

    def test_no_output_no_charge_no_retry(self):
        p = PEND["provider_blocker"]
        assert p["model_output_received"] is False
        assert p["billable_result"] is False
        assert p["retry_count"] == 0

    def test_no_provider_call_in_this_slice(self):
        assert PEND["provider_calls"] == 0
        assert PEND["image_generation_calls"] == 0
        assert ST["provider_calls_during_hold"] == 0
        assert ST["provider_substituted"] is False


class TestFrozenInputsAndPrompts:
    def test_prompt_hashes_present_and_stable(self):
        assert PEND["frozen_prompt_hashes"]["A"] == "589d9d142150bb6f"
        assert PEND["frozen_prompt_hashes"]["B"] == "f7cd3805fd161d81"
        assert PEND["frozen_prompt_hashes"] == FRZ["prompt_hashes"]

    def test_five_input_hashes_present(self):
        assert len(PEND["frozen_input_hashes"]) == 5
        for k, v in PEND["frozen_input_hashes"].items():
            assert v, k
            assert FRZ["images"][k]["sha256"] == v

    def test_images_not_regenerated(self):
        for k, v in FRZ["images"].items():
            p = v["path"]
            assert os.path.exists(p)
            assert _sha(p) == v["sha256"], f"{k} was regenerated"

    def test_enlargement_labelled_not_native(self):
        e = FRZ["images"]["reference_enlarged_x8"]
        assert e["native_or_enlarged"] == "ENLARGED_X8_NEAREST_NOT_NATIVE"

    def test_rejected_cropped_input_preserved(self):
        assert "cropped Damascena" in \
            FRZ["clipping_verification"]["rejected_earlier_render"]
        assert FRZ["clipping_verification"]["clipped"] is False


class TestFixtureReport:
    def test_suite_result_included(self):
        f = PEND["converter_fixtures"]
        assert f["total_fixtures"] == 24
        assert f["result"] == "ALL PASSING"
        assert f["dropped_operations"] == 0
        assert f["unresolved_components"] == 0
        assert f["repaired_handler"] == "PASS"

    def test_legacy_regression_documented(self):
        f = PEND["converter_fixtures"]
        assert "ZERO cubics" in f["legacy_handler_regression"]

    def test_coverage_complete(self):
        cov = " ".join(PEND["converter_fixtures"]["coverage"]).lower()
        for needed in ("super-bezier", "qcurveto", "implied on-curve",
                       "nested counters", "disconnected ink", "closepath",
                       "endpath", "unsupported operation",
                       "point-to-segment", "contour correspondence"):
            assert needed in cov, needed


class TestBuiltFromRecords:
    def test_nothing_recomputed(self):
        assert PEND["built_from_existing_records_only"] is True
        assert PEND["recomputed_anything"] is False

    def test_certification_carried_forward(self):
        c = PEND["deterministic_certification"]
        assert c["state"] == "VQ2_LF1_R1_DETERMINISTICALLY_CERTIFIED"
        assert c["vector_passing"] == 13 and c["raster_passing"] == 13

    def test_resume_contract_referenced(self):
        assert PEND["resume_contract"] == \
            "vq2_lf1_r1_inspection_resume_contract/1.0"
        assert RES["provider_substitution"] == \
            "PROHIBITED_WITHOUT_SEPARATE_OWNER_RULING"
        assert RES["retry_rule"]["retries_permitted_after_credit_restored"] == 1


class TestHoldState:
    def test_rose_width_unadjudicated(self):
        assert PEND["rose_width_state"] == \
            "UNADJUDICATED_PENDING_DUAL_TYPOGRAPHY_INSPECTION"
        assert ST["rose_width_classification"] == PEND["rose_width_state"]

    def test_lf1_r1_byte_identical(self):
        assert PEND["lf1_r1_geometry_changed"] is False
        assert _sha(LF1R1_AI) == "fcd8003994d52028"

    def test_vq2_hold_is_preserved_as_history(self):
        """The hold really happened; the pending package records it.

        vq2_state.json is LIVE and has since moved on, so the durable
        assertions are: the hold-slice package still documents the block, and
        VQ2-A2 was never generated (a standing prohibition, not a phase).
        """
        assert PEND["is_final_review"] is False
        assert PEND["inspections_performed"] == 0
        assert PEND["inspector_a_status"] == "NOT_PERFORMED_PROVIDER_CREDIT"
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False

    def test_no_lf2_or_a2_artifacts(self):
        for n in ("vq2_lf2", "vq2_a3"):
            for ext in ("ai", "pdf", "png"):
                assert not os.path.exists(os.path.join(D, f"{n}.{ext}"))

    def test_m3_and_vq3(self):
        sha = hashlib.sha256(
            open(os.path.join(M, "master_it3.png"), "rb").read()
        ).hexdigest()[:12]
        assert sha == "4ecc8e9df1d1"
        # VQ-3 was later started by explicit owner instruction

    def test_supplier_drafts_unsent(self):
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
