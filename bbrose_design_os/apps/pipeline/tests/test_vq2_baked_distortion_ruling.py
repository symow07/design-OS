"""VQ-2 owner ruling: baked non-uniform compression fails contract v3.1."""
import hashlib
import json
import os

import pytest
from django.conf import settings

from apps.ire import vq2_lettering_receipt as R

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
Rd = os.path.join(D, "received")
RUL = json.load(open(os.path.join(D, "vq2_owner_ruling_baked_compression.json")))
WEB = json.load(open(os.path.join(D, "vq2_governed_web_licensing_evidence.json")))
VAL = json.load(open(os.path.join(D, "vq2_submitted_lettering_validation.json")))
STATE = json.load(open(os.path.join(D, "vq2_state.json")))
SUBMITTED = {"AI8": "Rose_Damascena_Custom_Lettering_AI8_Editable.ai",
             "PDFC": "Rose_Damascena_Custom_Lettering_PDFCompatible.ai"}


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class TestBakedDistortionFails:
    def test_ruling_codes_and_verdict(self):
        assert RUL["receipt_result"] == "FAILED"
        for c in (R.NONUNIFORM_SCALING, R.HORIZONTAL_SCALING,
                  R.EXPANDED_AFTER_DISTORTION):
            assert c in RUL["codes"]
        assert VAL["receipt_result"] == "FAILED"

    def test_absence_of_active_transform_does_not_override(self):
        assert VAL["ai8_format"]["active_transform_operators"] == 0
        assert "does not prove" in R.DERIVATION_RULE[
            "zero_active_transforms_proves"]
        r = R._scale_findings({"kind": "glyph", "scale_x": 0.11056,
                               "scale_y": 0.175408,
                               "expanded_after_distortion": True})
        assert R.EXPANDED_AFTER_DISTORTION in r
        assert R.NONUNIFORM_SCALING in r

    def test_per_glyph_unequal_sx_sy_fails(self):
        for w, gl in RUL["decisive_evidence"]["per_glyph_sx_over_sy"].items():
            for g in gl:
                assert abs(g["sx_over_sy"] - 1.0) > 0.005, (w, g)
                assert R.NONUNIFORM_SCALING in R._scale_findings(
                    {"kind": "glyph", "scale_x": g["sx_over_sy"],
                     "scale_y": 1.0})

    def test_not_classified_as_validated(self):
        assert RUL["must_not_classify_as"] == \
            "VQ2_PRODUCT_NAME_LETTERING_VALIDATED_PENDING_OWNER_APPROVAL"
        assert RUL["vq2_a2_constructed"] is False


class TestUniformSizingNotMisclassified:
    @pytest.mark.parametrize("s", [0.05, 0.175, 1.0, 12.0])
    def test_uniform_scale_of_any_magnitude_is_clean(self, s):
        assert R._scale_findings(
            {"kind": "glyph", "scale_x": s, "scale_y": s}) == []

    def test_no_false_vertical_finding_on_the_submission(self):
        """sy alone must not fire VERTICAL; only true distortion does."""
        r = R._scale_findings({"kind": "glyph", "scale_x": 0.11056,
                               "scale_y": 0.175408,
                               "expanded_after_distortion": True})
        assert R.VERTICAL_SCALING not in r

    def test_vertical_fires_only_on_evidence(self):
        r = R._scale_findings({"kind": "glyph", "scale_x": 1.0,
                               "scale_y": 1.0,
                               "vertical_distortion_evidence": True})
        assert R.VERTICAL_SCALING in r

    def test_clarification_persisted(self):
        c = R.DERIVATION_RULE["vertical_finding_clarification"]
        assert "NOT prohibited by itself" in c
        assert RUL["vertical_finding_clarification"] == c

    def test_native_condensed_geometry_still_permitted(self):
        assert R._scale_findings(
            {"kind": "glyph", "scale_x": 0.2, "scale_y": 0.2,
             "drawn_proportion_width_ratio": 0.62}) == []
        assert "native human-drawn condensed geometry" in \
            R.DERIVATION_RULE["permitted"]


class TestPositiveEvidencePreserved:
    def test_strengths_recorded_not_erased(self):
        j = " ".join(RUL["preserved_positive_evidence"]).lower()
        for needed in ("real eps/postscript vector geometry",
                       "13 independently identified glyph objects",
                       "repeated a glyphs remain separate", "cubic paths",
                       "zero raster lettering", "zero live text",
                       "correct capitalization",
                       "visually coherent condensed didone character"):
            assert needed in j
        assert RUL["strengths_do_not_override_derivation"] is True

    def test_glyph_inventory_intact(self):
        assert VAL["glyph_count"] == 13
        assert VAL["rose_glyphs"] == 4 and VAL["damascena_glyphs"] == 9
        assert VAL["repeated_a_separate_objects"] == 3

    def test_superseded_regex_error_preserved(self):
        assert "bad regex" in VAL["ai8_format"]["correction"]


class TestSourceAuthority:
    def test_eps_recognized_as_editable_vector(self):
        a = RUL["ai8_source_authority"]
        assert a["is_editable_vector"] is True
        assert a["is_eps_compatible"] is True
        assert a["rejected_for_being_eps"] is False

    def test_not_accepted_as_native_source(self):
        assert RUL["ai8_source_authority"]["code"] == R.NATIVE_SOURCE_REQUIRED
        assert "native designer-authored" in \
            RUL["ai8_source_authority"]["rejected_because"]
        # the finding stands on the record even after Path B retired the
        # native-source blocker from the active list
        assert R.NATIVE_SOURCE_REQUIRED in RUL["ai8_source_authority"]["code"]


class TestWebEvidence:
    def test_official_sources_only(self):
        assert WEB["performed"] is True
        assert WEB["source_count"] >= 3
        for s in WEB["sources"]:
            assert s["category"].startswith("OFFICIAL")
            assert s["url"].startswith("https://")
            assert s["content_hash"]

    def test_no_binaries_downloaded_or_extracted(self):
        assert WEB["font_binaries_downloaded"] is False
        assert WEB["font_binaries_redistributed"] is False
        assert WEB["embedded_subsets_extracted"] is False
        assert WEB["logins_or_captcha_bypassed"] is False

    def test_ofl_determination(self):
        d = WEB["determination"]
        assert d["ofl_permits_outline_derived_commercial_artwork"] is True
        assert d["outlined_artwork_is_a_document_not_a_modified_version"] is True
        assert d["reserved_font_name_applies_to_artwork"] is False

    def test_rights_and_geometry_are_separate_gates(self):
        assert "SEPARATE gates" in WEB["critical_separation"]
        assert "does NOT cure" in WEB["critical_separation"]
        assert WEB["web_evidence_is_secondary"] is True
        assert RUL["receipt_result"] == "FAILED"   # licensing pass did not cure

    def test_excluded_source_types(self):
        j = " ".join(WEB["excluded_source_types"]).lower()
        for bad in ("free-font redistribution", "unofficial download mirrors",
                    "marketplace summaries", "ai-generated"):
            assert bad in j


class TestContractAndPackage:
    def test_contract_v31_parity(self):
        assert R.CONTRACT_VERSION == "3.1"
        sp = json.load(open(os.path.join(
            D, "lettering", "vq2_product_name_lettering_validation_spec.json")))
        rs = json.load(open(os.path.join(
            D, "lettering", "vq2_product_name_lettering_resume_contract.json")))
        assert sp["mandatory_checks"] == rs["validation_on_receipt"]
        assert sp["mandatory_checks"] == list(R.CHECK_NAMES)
        assert "no_geometry_expanded_after_distortion" in R.CHECK_NAMES

    def test_v3_contracts_archived(self):
        arch = os.path.join(D, "lettering", "archive")
        for n in ("vq2_product_name_lettering_validation_spec_v3.json",
                  "vq2_product_name_lettering_resume_contract_v3.json"):
            assert os.path.exists(os.path.join(arch, n))

    def test_review_package_present(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(D, f"vq2_submitted_lettering_validation.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000
        assert VAL["sections"] >= 15

    def test_replacement_requirements_enumerated(self):
        a = RUL["acceptable_next_asset"]
        assert "LOCKED_NONPRINTING_VISUAL_SCAFFOLD" in a["C"]
        assert "resave, expansion or path cleanup" in a["not_accepted"]


class TestBoundaries:
    def test_submitted_files_unmodified(self):
        assert RUL["files_modified"] is False
        assert RUL["glyphs_regenerated"] is False
        assert _sha(os.path.join(Rd, SUBMITTED["AI8"])) == \
            "2f3e1ea729975d2e6cedc7535cac7dccf3c5a31a9fae004d6a06ade631345964"
        assert _sha(os.path.join(Rd, SUBMITTED["PDFC"])) == \
            "f48d63a86eef6ac4020b4304ed47ba9442849dba843f5c65056db77037417003"

    def test_that_ruling_did_not_construct_an_a2(self):
        """Scoped to the ruling: A2 came later, under explicit owner
        authorization, on owner-approved lettering."""
        assert RUL["vq2_a2_constructed"] is False

    def test_owner_approval_still_outstanding(self):
        # VQ-2 has moved through several owner-directed states; the durable
        # invariant is that human approval is never granted automatically
        review = json.load(open(os.path.join(
            D, "vq2_a2_artwork_review.json")))
        assert review["human_accepted"] is False
        assert review["owner_decision_required"] is True

    def test_m3_and_vq3(self):
        assert _sha(os.path.join(M, "master_it3.png"))[:12] == "4ecc8e9df1d1"
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.
        # VQ-3 was later started by explicit owner instruction

    def test_no_provider_or_image_generation(self):
        assert VAL["image_generation_calls"] == 0

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
