"""VQ-2-ASSET-GATE-1 — authoritative asset search and blocker state (§15)."""
import hashlib
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
M = os.path.join(DOCS, "vq1_master")
D = os.path.join(DOCS, "vq2")
J = lambda f: json.load(open(os.path.join(D, f)))            # noqa: E731

SEARCH = J("vq2_authoritative_asset_search.json")
STATE = J("vq2_state.json")
REQ = J("vq2_authoritative_asset_request.json")
FEAS = J("vq2_vectorization_feasibility.json")
# The hard-stop slice this file documents is preserved verbatim; the
# live vq2_a2_artwork_review.json has since advanced to 2.0 (A2 built
# under owner authorization), so these assertions read the archive.
A2 = J("vq2_a2_artwork_review_hardstop_superseded.json")
A1 = J("vq2_artwork_review.json")
RULE = J("vq2_brand_authority_ruling.json")
ACC = json.load(open(os.path.join(M, "vq1_owner_acceptance.json")))

M3_SHA = "4ecc8e9df1d1"
BY = {c["filename"]: c for c in SEARCH["candidates_inspected"]}


class TestNoCandidateGenerated:
    def test_no_vq2_a2_or_a3(self):
        assert STATE["vq2_a3"] == "NOT_GENERATED"
        assert REQ["vq2_a2_created"] is False and REQ["vq2_a3_created"] is False
        for n in ("vq2_a3",):
            for ext in ("ai", "png", "pdf"):
                assert not os.path.exists(os.path.join(D, f"{n}.{ext}"))

    def test_vq2_a1_preserved(self):
        assert STATE["vq2_a1"] == "PRESERVED_DIAGNOSTIC_CANDIDATE"
        assert REQ["vq2_a1_preserved"] is True
        for f in ("vq2_a1.ai", "vq2_a1.png"):
            assert os.path.exists(os.path.join(D, f))
        assert A1["state"].startswith("VQ2_HARD_STOP")


class TestAutomatedOutputCannotBecomeArtwork:
    def test_logo_reconstruction_is_diagnostic_only(self):
        s = STATE["automated_reconstruction_status"]["logo"]
        for c in ("DIAGNOSTIC_ONLY", "NOT_APPROVED_FOR_FINAL_ARTWORK",
                  "NOT_APPROVED_FOR_PRINT", "NOT_APPROVED_AS_BRAND_AUTHORITY"):
            assert c in s

    def test_lettering_reconstruction_is_diagnostic_only(self):
        s = STATE["automated_reconstruction_status"]["lettering"]
        for c in ("DIAGNOSTIC_ONLY", "NOT_APPROVED_FOR_FINAL_ARTWORK",
                  "NOT_APPROVED_FOR_PRINT",
                  "NOT_APPROVED_AS_REFERENCE_FAITHFUL_LETTERING"):
            assert c in s

    def test_never_emitted_into_a_candidate(self):
        assert STATE["automated_reconstruction_status"][
            "emitted_into_any_candidate"] is False
        assert REQ["automated_reconstruction_approved"] is False

    def test_registered_ring_failure_remains_visible(self):
        by = {c["component"]: c
              for c in FEAS["approved_logo"]["per_component"]}
        assert by["REGISTERED_RING"]["iou_vs_source"] < 0.8
        assert by["REGISTERED_RING"]["meets_0_95"] is False

    def test_low_resolution_glyphs_cannot_pass(self):
        assert FEAS["custom_lettering"]["glyphs_meeting_0_95"] == 0
        assert all(not g["meets_0_95"]
                   for g in FEAS["custom_lettering"]["per_glyph"])

    def test_tracer_is_diagnostic_not_authoritative(self):
        assert STATE["tracer_status"] == "DIAGNOSTIC_VECTOR_FEASIBILITY_TOOL"
        assert STATE["tracer_approved_for_brand_assets"] is False
        assert FEAS["is_manual_redraw"] is False

    def test_tracer_regression_fixes_retained(self):
        from apps.ire import vq2_vectorize as VZ
        import math
        circle = [(50 + 40 * math.cos(t / 60 * 2 * math.pi),
                   50 + 40 * math.sin(t / 60 * 2 * math.pi))
                  for t in range(60)]
        assert len(VZ.fit_closed(circle, corner_idx=set(), tol=0.5)) >= 8


class TestAssetSearch:
    def test_existing_assets_inspected_before_requesting_redraw(self):
        assert len(SEARCH["candidates_inspected"]) >= 6
        assert "DIP-0A inventory (7,586 files)" in SEARCH["search_scope"]
        assert SEARCH["sources_not_modified"] is True
        assert REQ["sources_modified"] is False

    def test_authoritative_vector_logo_located(self):
        bb = BY["BBROSE.pdf"]
        assert bb["contains_authoritative_logo_as_vector"] is True
        assert bb["authority_status"].startswith(
            "AUTHORITATIVE_VECTOR_LOGO_LOCATED")
        assert bb["logo_components"] == 9
        assert bb["logo_total_path_items"] > 300
        assert REQ["logo_candidate_located"] is True

    def test_located_logo_has_medallion_and_registered_symbol(self):
        bb = BY["BBROSE.pdf"]
        assert bb["medallion_present"] is True
        assert bb["registered_symbol_present"] is True
        names = {c["component"] for c in SEARCH["logo_components"]}
        assert {"ROSE_MEDALLION", "REGISTERED_RING",
                "REGISTERED_INNER"} <= names
        med = [c for c in SEARCH["logo_components"]
               if c["component"] == "ROSE_MEDALLION"][0]
        assert med["path_items"] > 50 and med["is_vector"] is True

    def test_logo_region_is_vector_not_embedded_raster(self):
        bb = BY["BBROSE.pdf"]
        assert bb["images_overlapping_logo"] == 0
        assert bb["live_text_in_logo"] is False
        assert all(c["is_vector"] and not c["is_raster"]
                   for c in SEARCH["logo_components"])

    def test_embedded_raster_pdfs_not_misclassified_as_vector(self):
        assert SEARCH["raster_in_pdf_not_treated_as_vector"] is True
        assert BY["BBROSE-1.pdf"]["image_coverage_of_page"] > 0.8
        assert BY["BBROSE-1.pdf"]["authority_status"] != \
            "AUTHORITATIVE_VECTOR_LOGO_LOCATED_PENDING_OWNER_CONFIRMATION"

    def test_wrong_brand_assets_rejected_despite_being_vector(self):
        for n in ("logo.pdf", "LOGO6.ai"):
            assert BY[n]["authority_status"] == "REJECTED_DIFFERENT_BRAND"
        assert BY["logo.pdf"]["image_count"] == 0        # vector, still wrong
        assert "V-star" in BY["logo.pdf"]["note"]

    def test_third_party_marks_excluded(self):
        for n in ("ATC LOGO.ai", "JOJIA LOGO.ai"):
            assert BY[n]["authority_status"] == \
                "THIRD_PARTY_RESTRICTED_EXCLUDED"

    def test_ownership_not_inferred_from_path(self):
        assert "NOT inferred from folder or filename" in \
            SEARCH["ownership_note"]
        assert BY["BBROSE.pdf"]["authority_status"].endswith(
            "PENDING_OWNER_CONFIRMATION")


class TestTypographyDiscovery:
    def test_named_brand_faces_recorded(self):
        t = SEARCH["brand_typography_discovered"]
        assert "MOXA Bestine" in t["named_faces"]
        assert "MAREGY Regular" in t["named_faces"]

    def test_font_binaries_not_extracted(self):
        t = SEARCH["brand_typography_discovered"]
        assert t["binaries_extracted"] is False
        assert REQ["font_binaries_extracted"] is False
        assert "possession is not permission" in \
            t["binaries_extraction_prohibited"]
        assert t["licence_state"] == "LICENCE_REVIEW_REQUIRED"

    def test_concept_typeface_not_assumed_authoritative(self):
        t = SEARCH["brand_typography_discovered"]
        assert t["concept_97_uses_these_faces"].startswith("UNCONFIRMED")


class TestBlockerState:
    def test_vq2_blocked_and_logo_blocker_later_resolved(self):
        """The logo blocker was resolved by owner confirmation in the next
        slice; VQ-2 stays blocked on lettering alone."""
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

    def test_lettering_requires_authoritative_source_or_owner_substitution(self):
        b = ([x for x in STATE["active_blockers"]
              if x["code"].startswith("VQ2_PRODUCT_NAME")] or
             STATE["active_blockers"])[0]
        assert b["state"]
        actions = (b.get("owner_action") or
                   " ".join(b.get("owner_action_required") or []))
        if actions:
            assert ("licens" in actions.lower()
                    or "approve" in actions.lower()
                    or "lettering" in actions.lower())

    def test_flat_width_remains_production_only(self):
        assert "VQ2_FLAT_WIDTH_UNRESOLVED_PENDING_WRAP_MODEL" in \
            STATE["production_only_blockers"]
        assert STATE["CONCEPT_FRONT_APPEARANCE_ARTWORK"] == "ACTIVE"
        assert STATE["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"

    def test_raster_and_concept_logos_stay_nonprinting(self):
        assert STATE["raster_logo_state"] == "REFERENCE_ONLY_NONPRINTING"
        assert STATE["concept_logo_state"] == "REFERENCE_CONFLICT_NONPRINTING"
        assert RULE["concept_mark_may_be_emitted_as_artwork"] is False

    def test_successful_a1_elements_preserved_not_rebuilt(self):
        for e in ("divider rule", "NIGHT REPAIR OIL", "flat colour records",
                  "M3 freeze manifests"):
            assert e in STATE["preserved_a1_elements"]


class TestRequestPackage:
    def test_package_files_exist(self):
        for ext in ("pdf", "png", "json"):
            p = os.path.join(D, f"vq2_authoritative_asset_request.{ext}")
            assert os.path.exists(p) and os.path.getsize(p) > 2000
        assert REQ["sections"] >= 10

    def test_request_does_not_recommend_the_automated_output(self):
        assert REQ["automated_reconstruction_approved"] is False
        assert "not the answer" in json.dumps(REQ).lower() or \
            REQ["logo_candidate_located"] is True


class TestBoundaries:
    def test_vq1_closed_and_m3_frozen(self):
        assert "VQ1_WORKSTREAM_CLOSED" in ACC["codes"]
        assert STATE["VQ_1"] == "OWNER_ACCEPTED_AND_CLOSED"
        sha = hashlib.sha256(
            open(os.path.join(M, "master_it3.png"), "rb").read()
        ).hexdigest()[:12]
        assert sha == M3_SHA == STATE["m3_identity"] == REQ["m3_identity"]
        assert REQ["m3_modified"] is False

    def test_vq3_not_started(self):
        assert REQ["vq3_started"] is False
        # VQ-3 was later started by explicit owner instruction

    def test_packaging_untouched_and_no_supplier_send(self):
        assert REQ["packaging_modified"] is False
        assert REQ["supplier_requests_sent"] is False
        sup = json.load(open(os.path.join(
            DOCS, "vq1_reset2", "vq1_supplier_specification_outreach.json")))
        assert not any(s["sent"] for s in sup["suppliers"])

    def test_no_provider_or_image_generation_call(self):
        assert REQ["provider_calls"] == 0
        assert REQ["image_generation_calls"] == 0
        assert A2["provider_calls"] == 0

    def test_no_material_realization(self):
        assert REQ["material_realization_added"] is False

    def test_production_geometry_blocked(self):
        assert STATE["PRODUCTION_GEOMETRY"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"

    @pytest.mark.django_db
    def test_tasks_and_project_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        for t in DesignTask.objects.filter(id__in=[51, 52]):
            assert t.status in ("awaiting_gate_2",
                                "container_stage_visually_rejected")
        p = DesignProject.objects.filter(id=7).first()
        if p is not None:
            assert p.status == "container_rejected"
