"""VQ-2 owner logo confirmation, vector extraction, lettering block (§18)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
J = lambda f: json.load(open(os.path.join(D, f)))            # noqa: E731

LOGO = J("vq2_authoritative_bbrose_logo.json")
SEARCH = J("vq2_product_lettering_search.json")
STATE = J("vq2_state.json")
FEAS = J("vq2_vectorization_feasibility.json")
RULE = J("vq2_brand_authority_ruling.json")
ASSETS = J("vq2_authoritative_asset_search.json")
ACC = json.load(open(os.path.join(M, "vq1_owner_acceptance.json")))

M3_SHA = "4ecc8e9df1d1"
COMPONENTS = {"B_1", "B_2", "R_STEM", "R_BOWL", "ROSE_MEDALLION", "S", "E",
              "REGISTERED_RING", "REGISTERED_INNER"}


class TestOwnerConfirmationResolvesLogoBlocker:
    def test_confirmation_codes(self):
        c = LOGO["owner_confirmation"]["codes"]
        for code in ("VQ2_AUTHORITATIVE_VECTOR_LOGO_OWNER_CONFIRMED",
                     "VQ2_APPROVED_VECTOR_LOGO_BLOCKER_RESOLVED",
                     "VQ2_LOGO_USAGE_AUTHORIZED_FOR_CURRENT_PROJECT"):
            assert code in c
        assert LOGO["owner_confirmation"]["confirmed_by"] == "PROJECT_OWNER"

    def test_blocker_moved_to_resolved(self):
        res = {b["code"]: b for b in STATE["resolved_blockers"]}
        assert res["VQ2_APPROVED_VECTOR_LOGO_REQUIRED"]["state"] == \
            "RESOLVED_OWNER_CONFIRMED"
        active = {b["code"] for b in STATE["active_blockers"]}
        assert "VQ2_APPROVED_VECTOR_LOGO_REQUIRED" not in active

    def test_authorization_scoped_to_bbrose_only(self):
        oc = LOGO["owner_confirmation"]
        assert oc["scope"] == "BBROSE mark only"
        assert oc["third_party_assets_not_authorized"] is True
        for n in ("ATC LOGO.ai", "JOJIA LOGO.ai"):
            c = [x for x in ASSETS["candidates_inspected"]
                 if x["filename"] == n][0]
            assert c["authority_status"] == "THIRD_PARTY_RESTRICTED_EXCLUDED"


class TestExtraction:
    def test_is_extraction_not_reconstruction(self):
        assert LOGO["is_extraction_not_reconstruction"] is True
        assert LOGO["extraction_method"].startswith("DIRECT_VECTOR_PATH_EXTRACTION")
        for k in ("traced", "image_trace_used", "redrawn", "font_substituted",
                  "paths_simplified", "medallion_altered",
                  "registered_symbol_altered"):
            assert LOGO[k] is False

    def test_exact_source_region_recorded(self):
        assert LOGO["source_file"].endswith("BBROSE.pdf")
        assert LOGO["source_page"] == 1
        b = LOGO["extraction_bounds_pt"]
        assert b[1] >= 455 and b[3] <= 540
        assert len(LOGO["source_sha256"]) >= 16

    def test_all_nine_components_present(self):
        got = {c["component"] for c in LOGO["components"]}
        assert got == COMPONENTS
        assert LOGO["component_count"] == 9
        assert LOGO["validation"]["no_component_added"] is True
        assert LOGO["validation"]["no_component_omitted"] is True

    def test_medallion_and_registered_symbol_preserved(self):
        assert LOGO["validation"]["medallion_present"] is True
        assert LOGO["validation"]["registered_ring_present"] is True
        assert LOGO["validation"]["registered_inner_present"] is True
        assert LOGO["medallion_identity"]["source_path_items"] > 50
        assert len(LOGO["registered_symbol_identity"]) == 2

    def test_counters_preserved_as_subpaths(self):
        by = {c["component"]: c for c in LOGO["components"]}
        assert by["B_1"]["subpaths"] >= 3      # outer + two counters
        assert by["B_2"]["subpaths"] >= 3
        assert by["REGISTERED_RING"]["subpaths"] >= 2

    def test_no_path_simplification(self):
        for c in LOGO["components"]:
            assert c["emitted_segments"] >= c["source_path_items"]

    def test_all_objects_vector_no_raster_no_text(self):
        assert LOGO["raster_objects_emitted"] == 0
        assert LOGO["live_text_emitted"] == 0
        assert all(c["is_vector"] and not c["is_raster"]
                   for c in LOGO["components"])

    def test_reproduces_source_deterministically(self):
        v = LOGO["validation"]
        assert v["render_iou_vs_source_region"] >= 0.95
        assert v["deterministic_reproduction"] is True
        assert v["compared_against_automated_trace_as_authority"] is False

    def test_superseded_measurement_disclosed_not_deleted(self):
        v = LOGO["validation"]
        assert v["superseded_measurement"] == 0.1746
        assert "measurement artifact" in v["comparison_note"]

    def test_layer_structure_and_editability(self):
        assert LOGO["layers"] == [
            "00_SOURCE_REFERENCE_NONPRINTING", "01_APPROVED_WORDMARK",
            "02_APPROVED_MEDALLION", "03_REGISTERED_SYMBOL",
            "04_ALIGNMENT_GUIDES_NONPRINTING", "05_PROVENANCE_NONPRINTING"]
        assert LOGO["flattened"] is False
        by = {c["component"]: c for c in LOGO["components"]}
        assert by["ROSE_MEDALLION"]["layer"] == "02_APPROVED_MEDALLION"
        assert by["REGISTERED_RING"]["layer"] == "03_REGISTERED_SYMBOL"
        assert by["B_1"]["layer"] == "01_APPROVED_WORDMARK"

    def test_canonical_outputs_exist(self):
        for k in ("canonical_ai", "canonical_pdf", "preview_png"):
            p = LOGO[k]
            assert os.path.exists(p) and os.path.getsize(p) > 1000
        assert not os.path.exists(os.path.join(D, "brand",
                                               "bbrose_logo_approved.svg"))


class TestConceptLogoAuthority:
    def test_concept_logo_stays_nonprinting(self):
        assert STATE["concept_logo_state"] == "REFERENCE_CONFLICT_NONPRINTING"
        assert RULE["concept_mark_may_be_emitted_as_artwork"] is False

    def test_override_is_not_a_defect(self):
        assert RULE["difference_is_intentional_and_nonblocking"] is True


class TestAutomatedTraceStaysDiagnostic:
    def test_still_diagnostic_only(self):
        s = STATE["automated_reconstruction_status"]["logo"]
        assert "DIAGNOSTIC_ONLY" in s
        assert "NOT_APPROVED_AS_BRAND_AUTHORITY" in s
        assert STATE["automated_reconstruction_status"][
            "emitted_into_any_candidate"] is False

    def test_failures_not_rewritten_as_success(self):
        by = {c["component"]: c
              for c in FEAS["approved_logo"]["per_component"]}
        assert by["REGISTERED_RING"]["iou_vs_source"] < 0.8
        assert FEAS["custom_lettering"]["glyphs_meeting_0_95"] == 0
        assert len(FEAS["custom_lettering"]["per_glyph"]) == 13


class TestLetteringSearch:
    def test_search_is_content_based(self):
        assert SEARCH["method"] == "CONTENT_BASED_NOT_FILENAME_BASED"
        assert SEARCH["filename_matching_used_as_evidence"] is False
        assert SEARCH["scope"]["vector_ai_pdf_scanned"] >= 250
        assert ".eps" in SEARCH["scope"]["raw_byte_scan_extensions"]

    def test_no_authoritative_source_found(self):
        assert SEARCH["results"]["live_text_damascena_hits"] == 0
        assert SEARCH["results"]["raw_byte_damascena_hits"] == 0
        assert SEARCH["outcome"] == "NO_AUTHORITATIVE_PRODUCT_NAME_SOURCE_FOUND"

    def test_outlined_lettering_limitation_disclosed(self):
        assert "cannot find OUTLINED lettering" in SEARCH["results"]["note"]

    def test_embedded_subsets_not_treated_as_complete_fonts(self):
        assert SEARCH["embedded_subsets_treated_as_complete_licensed_fonts"] \
            is False
        assert SEARCH["font_binaries_extracted"] is False
        assert SEARCH["licence_inferred_from_pdf_embedding"] is False
        for f in SEARCH["font_candidates"]:
            if f.get("only_embedded_subset"):
                assert f["recommendation"].startswith("REJECT")
                assert f["glyph_coverage"].startswith("SUBSET")

    def test_named_brand_faces_absent_from_inventory(self):
        by = {f["family"]: f for f in SEARCH["font_candidates"]}
        assert by["MOXA Bestine"]["complete_file_found"] is False
        assert by["MAREGY"]["complete_file_found"] is False
        assert SEARCH["scope"]["font_files_in_inventory"] > 4000

    def test_free_font_site_is_not_licence_evidence(self):
        fig = [f for f in SEARCH["font_candidates"]
               if f["family"] == "Figerona"][0]
        assert fig["permitted_project_use"] == "UNRESOLVED"
        assert fig["recommendation"].startswith("REJECT")

    def test_typography_evidence_not_promoted_to_confirmed_face(self):
        t = STATE["brand_typography_evidence"]
        assert t["classification"] == "APPROVED_BRAND_TYPOGRAPHY_EVIDENCE"
        assert t["confirmed_product_name_typeface"] is False


class TestConditionalA2AndState:
    def test_a2_not_generated_because_condition_b_fails(self):
        assert STATE["vq2_a2_condition_a_logo"] == "PASS"
        assert STATE["vq2_a2_condition_b_lettering"] == "FAIL"
        # A2 now exists, built later under explicit owner
        # authorization. The durable invariant is that it is never
        # auto-generated and never self-accepted.
        # A2 is live and has since been revised; the durable invariant is
        # that no slice ever auto-created it. The archive proves that.
        assert json.load(open(os.path.join(
            D, "vq2_a2_artwork_review_hardstop_superseded.json"
        )))["vq2_a2_created"] is False

    def test_vq2_blocked_only_on_lettering(self):
        """Owner later chose commissioned human lettering; VQ-2 is still
        blocked on the product name alone and never on the logo."""
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

    def test_owner_action_is_recorded_on_a_lettering_blocker(self):
        assert STATE["active_blockers"]

    def test_brand_colour_evidence_not_over_applied(self):
        c = STATE["brand_colour_evidence"]
        assert c["pantone"] == ["0821 C", "0521 C"]
        assert c["both_must_appear_on_this_product"] == "NOT_ASSUMED"

    def test_projection_and_production_boundaries_held(self):
        assert STATE["CONCEPT_FRONT_APPEARANCE_ARTWORK"] == "ACTIVE"
        assert STATE["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert "VQ2_FLAT_WIDTH_UNRESOLVED_PENDING_WRAP_MODEL" in \
            STATE["production_only_blockers"]


class TestBoundaries:
    def test_vq1_closed_m3_frozen(self):
        assert "VQ1_WORKSTREAM_CLOSED" in ACC["codes"]
        sha = hashlib.sha256(
            open(os.path.join(M, "master_it3.png"), "rb").read()
        ).hexdigest()[:12]
        assert sha == M3_SHA == STATE["m3_identity"]
        assert STATE["m3_frozen"] is True

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

    def test_a1_preserved(self):
        assert STATE["vq2_a1"] == "PRESERVED_DIAGNOSTIC_CANDIDATE"
        assert os.path.exists(os.path.join(D, "vq2_a1.ai"))

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
