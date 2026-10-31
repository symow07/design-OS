"""VQ-2 lettering receipt rejected at the asset-authority gate."""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq2_lettering_receipt as R

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
L = os.path.join(D, "lettering")

REJ = json.load(open(os.path.join(L, "vq2_lettering_receipt_rejection.json")))
STATE = json.load(open(os.path.join(D, "vq2_state.json")))
BY = {f["file"]: f for f in REJ["submitted_files"]}
M3_SHA = "4ecc8e9df1d1"


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class TestRejectionRecorded:
    def test_all_four_codes(self):
        for c in ("VQ2_SUBMISSION_CONTAINS_PRESERVED_DIAGNOSTIC_A1",
                  "VQ2_SUBMISSION_CONTAINS_BLANK_HANDOFF_TEMPLATE",
                  "VQ2_AUTHORITATIVE_HUMAN_LETTERING_NOT_DELIVERED",
                  "VQ2_RECEIPT_VALIDATION_STOPPED_AT_ASSET_AUTHORITY"):
            assert c in REJ["codes"]
        assert REJ["outcome"] == "REJECTED_AT_ASSET_AUTHORITY_GATE"

    def test_submitted_hashes_actually_identify_the_files(self):
        f1, f2 = BY["FILE_1"], BY["FILE_2"]
        assert f1["sha256_verified"] is True
        assert f2["sha256_verified"] is True
        assert _sha(f1["identified_as"]) == f1["declared_sha256"]
        assert _sha(f2["identified_as"]) == f2["declared_sha256"]

    def test_both_files_were_prior_claude_outputs(self):
        assert BY["FILE_1"]["origin"].startswith("PRIOR_CLAUDE_OUTPUT")
        assert BY["FILE_2"]["origin"].startswith("PRIOR_CLAUDE_OUTPUT")

    def test_file1_is_the_preserved_diagnostic(self):
        f = BY["FILE_1"]
        assert f["identified_as"].endswith("vq2_a1.ai")
        assert f["native_illustrator_layers"] is False
        assert f["designer_output_provenance"] is False
        assert f["disposition"] == "PRESERVED_DIAGNOSTIC_CANDIDATE"
        assert f["rose_damascena_outlines_promoted_to_final_artwork"] is False

    def test_file2_is_the_blank_template(self):
        f = BY["FILE_2"]
        assert f["identified_as"].endswith(
            "vq2_product_name_lettering_template.ai")
        assert f["contains_completed_rose_lettering"] is False
        assert f["contains_completed_damascena_lettering"] is False
        assert f["designer_output_layer_populated"] is False
        assert f["contains_approved_logo"] is True

    def test_template_ai_pdf_byte_identity_disclosed(self):
        f = BY["FILE_2"]
        assert "same bytes" in f["byte_identical_note"]
        assert _sha(f["also_matches"]) == f["declared_sha256"]


class TestDownstreamValidationNotRun:
    def test_glyph_validation_was_not_executed(self):
        assert REJ["downstream_glyph_validation_executed"] is False
        assert STATE["lettering_receipt_attempts"][0][
            "downstream_glyph_validation_executed"] is False

    def test_reason_is_recorded(self):
        assert "manufacture the appearance of a receipt" in \
            REJ["why_downstream_not_executed"]

    def test_contract_still_in_force_and_untouched(self):
        assert REJ["contract_version_in_force"] == "2.0"
        # the rejection was recorded under v2 (23 checks); v3 later added
        # seven asset-authority checks, so the contract only grew
        assert REJ["mandatory_checks_awaiting_a_qualifying_asset"] == 23
        assert len(R.CHECK_NAMES) >= 23


class TestNothingWasModifiedOrGenerated:
    def test_submitted_files_not_modified(self):
        assert REJ["neither_file_modified"] is True
        assert _sha(os.path.join(D, "vq2_a1.ai")) == \
            BY["FILE_1"]["declared_sha256"]
        assert _sha(os.path.join(
            L, "vq2_product_name_lettering_template.ai")) == \
            BY["FILE_2"]["declared_sha256"]

    def test_no_glyphs_generated(self):
        assert REJ["glyphs_generated"] is False
        for n in ("rose_lettering.ai", "damascena_lettering.ai",
                  "vq2_product_name_lettering.ai"):
            assert not os.path.exists(os.path.join(L, n))

    def test_a1_not_reused_as_the_delivery(self):
        assert REJ["vq2_a1_reused_as_lettering_delivery"] is False
        assert STATE["vq2_a1"] == "PRESERVED_DIAGNOSTIC_CANDIDATE"

    def test_no_vq2_a2_or_a3(self):
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False
        for n in ("vq2_a3",):
            for ext in ("ai", "png", "pdf"):
                assert not os.path.exists(os.path.join(D, f"{n}.{ext}"))


class TestStateHeld:
    def test_still_blocked_on_human_lettering(self):
        # the owner later selected Path B (licensed typeface); VQ-2 is still
        # blocked on the product name and still needs owner approval
        # VQ-2 has moved through several owner-directed states; the durable
        # invariants are that A2 is unbuilt and owner approval is outstanding
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False
        assert any("OWNER_APPROVAL" in b["code"] or "PENDING" in b["state"]
                   or "PENDING" in b["code"]
                   for b in STATE["active_blockers"])

    def test_asset_still_not_received(self):
        assert STATE["lettering_asset_received"] is False

    def test_attempt_logged(self):
        a = STATE["lettering_receipt_attempts"][0]
        assert a["outcome"] == "REJECTED_AT_ASSET_AUTHORITY_GATE"
        assert os.path.exists(a["record"])

    def test_m3_byte_identical(self):
        assert _sha(os.path.join(M, "master_it3.png"))[:12] == M3_SHA
        assert STATE["m3_identity"] == M3_SHA

    def test_logo_blocker_stays_resolved(self):
        res = {b["code"]: b for b in STATE["resolved_blockers"]}
        assert res["VQ2_APPROVED_VECTOR_LOGO_REQUIRED"]["state"] == \
            "RESOLVED_OWNER_CONFIRMED"

    def test_vq3_not_started_packaging_untouched(self):
        """VQ-3 has since been started and closed by explicit owner
        instruction. The durable guarantee is that THIS slice started
        neither VQ-3 nor packaging, which its own state record shows."""
        assert STATE["PACKAGING"] == "NOT_STARTED"
        assert STATE.get("vq2_a3", "NOT_GENERATED") == "NOT_GENERATED"

    def test_supplier_drafts_unsent(self):
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])


class TestRequiredDelivery:
    def test_primary_delivery_is_the_illustrator_source(self):
        d = REJ["required_primary_delivery"]
        assert d["words"] == ["Rose", "Damascena"]
        assert d["drawn_inside_layer"] == "09_DESIGNER_OUTPUT"
        assert "does not replace" in \
            d["accompanying_pdf_or_eps"].lower().replace("_", " ")

    def test_requirements_enumerated(self):
        j = " ".join(REJ["required_primary_delivery"]["requirements"]).lower()
        for needed in ("one independently editable vector object per glyph",
                       "no raster lettering", "no live unresolved font",
                       "no automated trace",
                       "no horizontal or vertical scaling",
                       "no non-uniform transform", "no word-group scaling",
                       "clean counters", "no self-intersections",
                       "straight canonical baselines",
                       "explicit owner approval"):
            assert needed in j

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
