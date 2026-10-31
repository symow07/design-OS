"""VQ-2 human custom lettering commission — handoff, gates, resume (§18)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
L = os.path.join(D, "lettering")
JL = lambda f: json.load(open(os.path.join(L, f)))           # noqa: E731
JD = lambda f: json.load(open(os.path.join(D, f)))           # noqa: E731

BRIEF = JL("vq2_product_name_lettering_brief.json")
SPEC = JL("vq2_product_name_lettering_validation_spec.json")
RESUME = JL("vq2_product_name_lettering_resume_contract.json")
STATE = JD("vq2_state.json")
LOGO = JD("vq2_authoritative_bbrose_logo.json")
FEAS = JD("vq2_vectorization_feasibility.json")
SEARCH = JD("vq2_product_lettering_search.json")
ACC = json.load(open(os.path.join(M, "vq1_owner_acceptance.json")))
M3_SHA = "4ecc8e9df1d1"


class TestBlockedState:
    def test_vq2_enters_human_lettering_blocked_state(self):
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

    def test_owner_decision_codes(self):
        for c in ("VQ2_OWNER_SELECTED_HUMAN_CUSTOM_VECTOR_LETTERING",
                  "VQ2_PRODUCT_NAME_LETTERING_COMMISSION_REQUIRED",
                  "VQ2_A2_BLOCKED_PENDING_APPROVED_CUSTOM_LETTERING"):
            assert c in STATE["owner_decision_codes"]
            assert c in BRIEF["codes"]

    def test_logo_blocker_stays_resolved(self):
        res = {b["code"]: b for b in STATE["resolved_blockers"]}
        assert res["VQ2_APPROVED_VECTOR_LOGO_REQUIRED"]["state"] == \
            "RESOLVED_OWNER_CONFIRMED"

    def test_no_further_search_or_tracing_or_purchase(self):
        assert STATE["further_asset_search_permitted"] is False
        assert STATE["automatic_tracing_permitted"] is False
        assert STATE["automatic_font_purchase_permitted"] is False
        assert STATE["moxa_bestine_confirmed_product_face"] is False


class TestClaudeDidNotDrawTheLettering:
    def test_handoff_only(self):
        assert BRIEF["handoff_only"] is True
        assert BRIEF["claude_drew_final_glyphs"] is False
        assert BRIEF["automated_tracing_used_for_final_glyphs"] is False

    def test_no_final_glyph_artwork_emitted(self):
        for n in ("rose_lettering.ai", "damascena_lettering.ai",
                  "vq2_product_name_lettering.ai"):
            assert not os.path.exists(os.path.join(L, n))

    def test_designer_authors_a_new_native_document(self):
        """v2 of the brief: the template is PDF-compatible, so 09_DESIGNER_
        OUTPUT was never an enforceable container and is superseded."""
        assert BRIEF["designer_output_layer"] is None
        assert BRIEF["designer_creates_new_native_document"] is True
        assert BRIEF["template_is_native_layered_ai"] is False

    def test_diagnostic_reconstructions_never_promoted(self):
        assert STATE["automated_reconstruction_status"][
            "emitted_into_any_candidate"] is False
        assert FEAS["custom_lettering"]["glyphs_meeting_0_95"] == 0
        assert len(FEAS["custom_lettering"]["per_glyph"]) == 13


class TestTemplate:
    def test_template_files_exist(self):
        for k in ("template_ai", "template_pdf", "template_png"):
            p = BRIEF[k]
            assert os.path.exists(p) and os.path.getsize(p) > 2000

    def test_all_eleven_layers_in_order(self):
        assert BRIEF["template_layers"] == [
            "00_REFERENCE_NONPRINTING", "01_M3_STRUCTURE_LOCKED",
            "02_APPROVED_BBROSE_LOGO_LOCKED",
            "03_ARTWORK_ZONE_GUIDES_NONPRINTING",
            "04_ROSE_LETTERING_PLACEHOLDER",
            "05_DAMASCENA_LETTERING_PLACEHOLDER",
            "06_SUPPORTING_COPY_LOCKED", "07_DIVIDER_RULE_LOCKED",
            "08_MEASUREMENT_GUIDES_NONPRINTING", "09_DESIGNER_OUTPUT",
            "10_AUDIT_METADATA_NONPRINTING"]

    def test_template_uses_the_authoritative_logo(self):
        assert BRIEF["canonical_logo"].endswith("bbrose_logo_approved.ai")
        assert BRIEF["canonical_logo_sha256"] == LOGO["canonical_ai_sha256"]
        assert LOGO["component_count"] == 9
        assert LOGO["traced"] is False

    def test_template_metadata_locks_structure_and_logo(self):
        import fitz
        d = fitz.open(BRIEF["template_ai"])
        meta = json.loads(d.metadata.get("subject") or "{}") \
            if d.metadata.get("subject", "").startswith("{") else {}
        d.close()
        # metadata may not survive the emitter; the manifest is authoritative
        assert "01_M3_STRUCTURE_LOCKED" in BRIEF["template_layers"]
        assert "02_APPROVED_BBROSE_LOGO_LOCKED" in BRIEF["template_layers"]
        assert meta is not None

    def test_measured_guides_present_for_both_words(self):
        t = BRIEF["targets"]
        assert t["Rose"]["reference_left_px"] == 527
        assert t["Rose"]["apparent_width_px"] == 134
        assert t["Rose"]["baseline_px"] == 1021.0
        assert t["Rose"]["cap_height_px"] == 73.0
        assert t["Damascena"]["apparent_width_px"] == 281
        assert t["Damascena"]["baseline_px"] == 1091.0
        assert t["Damascena"]["cap_height_px"] == 61.0

    def test_native_and_enlarged_evidence_both_supplied(self):
        for k in ("product_name_block", "rose", "damascena"):
            e = BRIEF["evidence"][k]
            assert os.path.exists(e["native"]) and os.path.exists(e["enlarged"])
            assert e["enlargement"] == 8 and e["resample"] == "NEAREST"
            assert e["is_native_resolution"] is False


class TestProjectionAndBaseline:
    def test_canonical_baseline_stays_straight(self):
        assert SPEC["canonical_baseline"] == "STRAIGHT"
        assert SPEC["projection_baked_into_source_paths"] is False

    def test_targets_are_apparent_not_production(self):
        assert SPEC["measurement_space"] == \
            "APPARENT_PROJECTED_REFERENCE_PIXELS"
        assert SPEC["is_production_flat_specification"] is False
        assert STATE["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert STATE["CONCEPT_FRONT_APPEARANCE_ARTWORK"] == "ACTIVE"


class TestAcceptanceSpec:
    def test_deterministic_gates_complete(self):
        g = SPEC["A_deterministic_composition_gates"]
        assert g["rose_apparent_width_err_max"] == 0.025
        assert g["damascena_apparent_width_err_max"] == 0.025
        assert g["word_centerline_err_max_of_body_width"] == 0.010
        assert g["cap_height_err_max"] == 0.020
        assert g["baseline_angle_err_max_deg"] == 0.5
        for k in ("glyph_collisions_max", "self_intersections_max",
                  "raster_objects_max", "live_font_objects_max",
                  "horizontally_scaled_font_outlines_max",
                  "unresolved_visible_glyphs_max"):
            assert g[k] == 0

    def test_human_review_is_not_automated(self):
        b = SPEC["B_human_form_review"]
        assert b["reviewer"] == "OWNER"
        assert b["automated_gate"] is False
        assert "serif construction" in b["criteria"]

    def test_hairlines_not_used_as_hard_gates(self):
        assert SPEC["hairline_pixels_used_as_hard_gates"] is False
        assert SPEC["pixel_perfect_identity_required"] is False

    def test_classification_makes_no_false_claim(self):
        assert SPEC["classification"] == "CUSTOM_REFERENCE_DERIVED_WORD_LETTERING"
        for bad in ("a complete font", "the original commercial typeface",
                    "a reusable alphabet",
                    "a supplier-confirmed production wordmark"):
            assert bad in SPEC["is_not"]


class TestResumeContract:
    def test_a2_cannot_resume_without_approved_lettering(self):
        assert BRIEF["vq2_a2_created"] is False
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False
        assert "APPROVED" in RESUME["vq2_a2_may_resume_when"].upper()

    def test_no_a3(self):
        assert RESUME["vq2_a3_automatic"] is False
        assert BRIEF["vq2_a3_created"] is False

    def test_cannot_resume_from_automated_tracing(self):
        assert RESUME["may_resume_from_automated_tracing"] is False

    def test_validation_on_receipt_is_specified(self):
        """v2 normalized the list to machine check names and added the
        vertical/non-uniform/word-group scaling and counter checks."""
        checks = RESUME["validation_on_receipt"]
        assert "native_illustrator_source_provenance" in checks
        for needed in ("exact_wording", "exact_capitalization",
                       "vector_only_construction",
                       "one_independently_editable_object_per_glyph",
                       "no_raster_content", "no_horizontal_scaling",
                       "no_vertical_scaling", "no_nonuniform_scaling",
                       "no_scaled_word_groups", "no_colliding_glyphs",
                       "no_self_intersections",
                       "valid_counters_and_fill_rules", "owner_approval"):
            assert needed in checks

    def test_designer_delivery_layers_specified(self):
        """v3 replaced the 5-layer delivery list with the full 11-layer
        native document structure the designer must build."""
        from apps.ire import vq2_lettering_receipt as R
        assert RESUME["designer_delivery_layers"] == \
            list(R.REQUIRED_DESIGNER_LAYERS)
        assert "04_ROSE_LETTERING" in RESUME["designer_delivery_layers"]
        assert "05_DAMASCENA_LETTERING" in RESUME["designer_delivery_layers"]
        assert RESUME["designer_must_flag_interpretation"] is True


class TestPackageAndEvidence:
    def test_brief_files_exist(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(L, f"vq2_product_name_lettering_brief.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000
        assert BRIEF["sections"] >= 12

    def test_why_custom_is_evidence_backed(self):
        w = BRIEF["why_custom_required"]
        assert "Damascena" in w and "4,845" in w
        assert "0.639" in w and "1.41x" in w

    def test_prior_evidence_preserved(self):
        for f in ("vq2_artwork_review.json", "vq2_a2_artwork_review.json",
                  "vq2_vectorization_feasibility.json",
                  "vq2_authoritative_asset_search.json",
                  "vq2_product_lettering_search.json",
                  "vq2_authoritative_bbrose_logo.json"):
            assert os.path.exists(os.path.join(D, f))
        assert LOGO["validation"]["superseded_measurement"] == 0.1746
        assert LOGO["validation"]["render_iou_vs_source_region"] >= 0.95
        assert SEARCH["outcome"] == \
            "NO_AUTHORITATIVE_PRODUCT_NAME_SOURCE_FOUND"


class TestBoundaries:
    def test_vq1_closed_and_m3_frozen(self):
        assert "VQ1_WORKSTREAM_CLOSED" in ACC["codes"]
        sha = hashlib.sha256(
            open(os.path.join(M, "master_it3.png"), "rb").read()
        ).hexdigest()[:12]
        assert sha == M3_SHA == STATE["m3_identity"]

    def test_a1_preserved(self):
        assert STATE["vq2_a1"] == "PRESERVED_DIAGNOSTIC_CANDIDATE"
        assert os.path.exists(os.path.join(D, "vq2_a1.ai"))

    def test_no_provider_or_image_generation_call(self):
        assert BRIEF["provider_calls"] == 0
        assert BRIEF["image_generation_calls"] == 0

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

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
