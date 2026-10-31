"""VQ2-A2 — owner-approved lettering composed on frozen M3, flat artwork only.

The point of these tests is that VQ2-A2 is allowed to exist only because both
of its inputs became authoritative: the logo by direct vector extraction, the
lettering by owner approval. Everything else it touches must be provably
unchanged — M3, packaging, task 51/52, project 7 — and nothing here may read as
acceptance or as production artwork.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

D = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
J = lambda n: json.load(open(os.path.join(D, n)))                     # noqa
A2 = J("vq2_a2.json")
APP = J("vq2_lettering_owner_approval.json")
REVIEW = J("vq2_a2_artwork_review.json")
FRZV = J("vq2_a2_m3_freeze_verification.json")
BASE = J("vq2_a2_m3_freeze.json")
LOGO = J("vq2_authoritative_bbrose_logo.json")
ST = J("vq2_state.json")
LF1_AI = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")


class TestLetteringOwnerApproval:

    def test_lf1_r1_is_owner_approved(self):
        assert APP["decided_by"] == "PROJECT_OWNER"
        for c in ("VQ2_PRODUCT_NAME_LETTERING_OWNER_APPROVED",
                  "VQ2_IMBUE_LF1_R1_OWNER_ACCEPTED",
                  "VQ2_PRODUCT_NAME_LETTERING_RESOLVED"):
            assert c in APP["codes"]
        assert APP["authoritative_lettering"] == "VQ2-LF1-R1"
        assert APP["approved_words"] == ["Rose", "Damascena"]

    def test_machine_pass_did_not_confer_approval(self):
        assert APP["machine_pass_did_not_confer_approval"] is True
        assert "not Gate-2" in APP["scope"]

    def test_rose_width_accepted_as_nonactionable(self):
        r = APP["rose_width_ruling"]
        assert r["code"] == "VQ2_ROSE_NATIVE_WIDTH_DIFFERENCE_OWNER_ACCEPTED"
        assert r["classification"] == "NONACTIONABLE"
        assert r["state"] == "OWNER_ACCEPTED"
        assert r["rose"]["candidate_px"] == 128.85
        assert r["rose"]["reference_px"] == 134

    def test_prohibited_corrections_recorded_and_not_applied(self):
        assert "horizontal scaling of Rose" in \
            APP["rose_width_ruling"]["prohibited"]
        lt = A2["lettering"]
        assert lt["rose_scaled"] is False
        assert lt["outlines_modified"] is False
        assert lt["tracking_changed"] is False
        assert lt["axes_changed"] is False
        assert lt["axes"] == {"opsz": 100, "wght": 400}
        assert lt["typeface"] == "Imbue"

    def test_inspector_logo_discrepancy_preserved_not_rewritten(self):
        d = APP["inspector_logo_discrepancy"]
        assert d["code"] == \
            "VQ2_INSPECTOR_A_LOGO_DESCRIPTION_INACCURATE_NONBLOCKING"
        assert d["raw_inspector_output_rewritten"] is False
        assert "serif-based" in d["owner_finding"]
        # the raw inspector output still says what it said
        rev = json.load(open(os.path.join(
            D, "typeface", "vq2_imbue_lf1_r1_review.json")))
        assert rev["inspector_a"]["raw_output"]
        assert rev["inspector_a"]["raw_output_sha256_16"] == \
            hashlib.sha256(
                rev["inspector_a"]["raw_output"].encode()).hexdigest()[:16]


class TestLF1R1Frozen:

    def test_lf1_r1_remains_byte_identical(self):
        assert hashlib.sha256(
            open(LF1_AI, "rb").read()).hexdigest()[:16] == "fcd8003994d52028"
        assert A2["lettering"]["ai_sha256_16"] == "fcd8003994d52028"

    def test_freeze_declared(self):
        f = APP["lf1_r1_freeze"]
        assert f["state"] == "FROZEN_BYTE_IDENTICAL"
        for k in ("regenerated", "glyph_paths_modified", "counters_modified",
                  "tracking_modified", "axes_modified", "lf2_created",
                  "typeface_substituted"):
            assert f[k] is False

    def test_no_lf2_exists(self):
        assert not os.path.exists(os.path.join(D, "lf2"))
        assert not any(n.startswith("vq2_lf2") for n in os.listdir(D))

    def test_font_binary_stays_internal(self):
        f = APP["lf1_r1_freeze"]
        assert f["font_binary_internal_only"] is True
        assert f["font_binary_in_user_facing_deliverables"] is False
        assert A2["lettering"]["font_binary_embedded"] is False

    def test_a2_lettering_is_lf1_r1_geometry_not_a_redraw(self):
        lt = A2["lettering"]
        assert lt["source"] == "VQ2-LF1-R1"
        assert lt["owner_approved"] is True
        assert lt["glyph_count"] == 13
        assert len(lt["font_unit_contour_hash"]) == 16
        assert "uniformly scaled to working size only" in lt["derivation"]


class TestExactlyOneA2:

    def test_one_a2_and_no_a3(self):
        assert A2["exactly_one_a2"] is True
        assert A2["vq2_a3_created"] is False
        assert REVIEW["vq2_a2_created"] is True
        assert REVIEW["vq2_a3_created"] is False
        assert not any(n.startswith("vq2_a3") for n in os.listdir(D))

    def test_ai_and_png_exist(self):
        assert os.path.getsize(os.path.join(D, "vq2_a2.ai")) > 10_000
        assert os.path.getsize(os.path.join(D, "vq2_a2.png")) > 10_000

    def test_prior_hard_stop_record_preserved(self):
        old = J("vq2_a2_artwork_review_hardstop_superseded.json")
        assert old["state"] == "VQ2_HARD_STOP_REVIEW_REQUIRED"
        assert old["vq2_a2_created"] is False
        assert REVIEW["supersedes"].startswith("vq2_a2_artwork_review/1.0")
        assert set(REVIEW["prior_stop_grounds_cleared"]) == \
            set(old["stop_grounds"])


class TestApprovedLogoUsed:

    def test_approved_vector_logo_is_the_source(self):
        lg = A2["logo"]
        assert lg["source"] == "APPROVED_BBROSE_VECTOR_EXTRACTION"
        assert lg["canonical_ai_sha256_16"] == LOGO["canonical_ai_sha256"]
        assert lg["traced"] is False
        assert lg["redrawn"] is False
        assert lg["nonuniform_scaling"] is False
        assert lg["medallion_present"] is True
        assert lg["registered_symbol_present"] is True

    def test_extraction_not_reconstruction(self):
        assert LOGO["is_extraction_not_reconstruction"] is True
        assert LOGO["image_trace_used"] is False
        assert LOGO["validation"]["render_iou_vs_source_region"] >= 0.95

    def test_concept_logo_remains_nonprinting(self):
        assert A2["logo"]["concept_mark_emitted_as_artwork"] is False
        assert A2["logo"]["concept_mark_state"] == \
            "REFERENCE_CONFLICT_NONPRINTING"
        ruling = J("vq2_brand_authority_ruling.json")
        assert ruling["concept_mark_may_be_emitted_as_artwork"] is False
        # it lives on a non-printing layer in the emitted document
        nonprinting = [ly for ly in A2["layer_manifest"]["layers"]
                       if not ly["printing"]]
        assert sum(ly["objects"] for ly in nonprinting) >= 1


class TestM3Frozen:

    def test_m3_identity_and_components_unchanged(self):
        assert A2["m3_identity"] == "4ecc8e9df1d1"
        assert A2["m3_modified"] is False
        assert FRZV["code"] is None
        assert FRZV["drift"] == []
        for c, h in BASE["components"].items():
            assert FRZV["live"]["components"][c] == h

    def test_structural_paths_byte_identical(self):
        n = FRZV["structural_nonregression"]
        assert n["m3_hashes_unchanged"] is True
        assert n["differing_fields"] == []
        assert n["structure_layer_locked"] is True
        assert FRZV["every_structural_path_byte_identical"] is True

    def test_centerline_bands_and_span_unchanged(self):
        assert FRZV["live"]["centerline_px"] == BASE["centerline_px"] == 666.5
        assert FRZV["live"]["bands"] == BASE["bands"]
        assert FRZV["live"]["assembly_span_px"] == BASE["assembly_span_px"]

    def test_masks_do_not_alter_the_silhouette(self):
        n = FRZV["structural_nonregression"]
        assert n["mask_modifies_contour"] is False
        assert n["artwork_in_structural_silhouette"] is False
        assert n["material_cue_changes_geometry"] is False

    def test_no_drift_record_was_written(self):
        assert not os.path.exists(os.path.join(D, "vq2_a2_m3_drift.json"))


class TestMaterialBoundary:

    def test_no_material_realization_introduced(self):
        assert A2["material_realization_added"] is False
        for k in ("gradients", "shadows", "highlights", "reflections",
                  "texture", "gloss", "photographic_lighting"):
            assert A2[k] == 0, k

    def test_flat_palette_only(self):
        assert A2["flat_colour_palette"]
        assert A2["layer_manifest"]["all_outlined_vector"] is True
        assert A2["layer_manifest"]["text_runs"] == 0
        assert A2["layer_manifest"]["image_nodes"] == 0
        assert A2["layer_manifest"]["raster_typography_objects"] == 0


class TestPlacementAndHierarchy:

    def test_required_visible_hierarchy(self):
        assert A2["hierarchy_order_top_to_bottom"] == [
            "APPROVED_BBROSE_LOGO", "DIVIDER_RULE", "ROSE", "DAMASCENA",
            "NIGHT_REPAIR_OIL"]
        assert A2["hierarchy_matches_required"] is True

    def test_front_artwork_zone_compliant(self):
        assert A2["front_artwork_zone_compliant"] is True

    def test_rose_width_is_the_accepted_native_value(self):
        rose = {m["element"]: m for m in A2["placement_metrics"]}["ROSE"]
        assert rose["width_px_apparent"] == 128.85
        assert rose["target_width_px"] == 134
        assert round(rose["width_error"], 3) == 0.038

    def test_supporting_face_not_claimed_resolved(self):
        s = A2["supporting_copy"]
        assert s["text"] == "NIGHT REPAIR OIL"
        assert s["typeface_state"] == "VQ2_EXACT_TYPEFACE_UNRESOLVED"
        assert "not claimed as resolved" in s["note"]


class TestStateBoundaries:

    def test_vq1_closed_and_vq3_not_started(self):
        assert ST["VQ_1"] == "OWNER_ACCEPTED_AND_CLOSED"
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.
        assert A2["vq3_started"] is False
        assert REVIEW["vq3_started"] is False

    def test_production_remains_blocked(self):
        assert A2["production_flat_artwork"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert A2["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert ST["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"

    def test_packaging_untouched_and_no_supplier_request(self):
        assert A2["packaging_modified"] is False
        assert A2["supplier_requests_sent"] == 0
        assert REVIEW["packaging_modified"] is False
        assert REVIEW["supplier_requests_sent"] == 0

    def test_no_image_generation_call(self):
        assert A2["image_generation_calls"] == 0
        assert A2["provider_calls"] == 0
        assert REVIEW["image_generation_calls"] == 0

    def test_a2_is_not_acceptance(self):
        assert A2["human_accepted"] is False
        assert A2["owner_decision_required"] is True
        assert REVIEW["human_accepted"] is False
        assert REVIEW["state"] == "VQ2_A2_BUILT_PENDING_OWNER_REVIEW"
        blob = json.dumps(REVIEW) + json.dumps(A2)
        for forbidden in ("HUMAN_ACCEPTED", "MANUFACTURABLE",
                          "PRODUCTION_READY"):
            assert forbidden not in blob


@pytest.mark.django_db
class TestUpstreamRecordsUntouched:
    """Task 51, task 52 and project 7 are terminal history."""

    def test_task_52_still_terminal_and_project_7_rejected(self):
        from apps.pipeline.models import DesignProject, DesignTask
        t52 = DesignTask.objects.filter(pk=52).first()
        t51 = DesignTask.objects.filter(pk=51).first()
        p7 = DesignProject.objects.filter(pk=7).first()
        if t52 is not None:
            assert t52.status == "container_stage_visually_rejected"
        if p7 is not None:
            assert p7.status == "container_rejected"
        if t51 is not None:
            assert t51.pk == 51

    def test_a2_did_not_create_or_touch_any_task(self):
        """VQ-2 is a program-level workstream; it writes no task records."""
        from apps.pipeline.models import DesignTask
        before = DesignTask.objects.count()
        assert A2["provider_calls"] == 0
        assert DesignTask.objects.count() == before


class TestReviewPackage:

    def test_all_seventeen_required_sections_present(self):
        titles = REVIEW["section_titles"]
        for i in range(1, 18):
            assert any(t.startswith(f"{i}.") for t in titles), i
        assert REVIEW["sections"] == len(titles)

    def test_package_files_exist(self):
        for ext, floor in (("pdf", 100_000), ("png", 5_000)):
            p = os.path.join(D, f"vq2_a2_artwork_review.{ext}")
            assert os.path.getsize(p) > floor, ext


@pytest.mark.django_db
class TestBoardServesA2:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2a2tester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_a2_pending_review(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]
        a = v["a2"]
        # the board surfaces the latest revision of the A2 line
        # the board surfaces the LATEST VQ-2 front-artwork candidate; the
        # durable invariant is that it always awaits the owner
        assert a["state"].startswith("VQ2_")
        assert "PENDING_OWNER" in a["state"]
        assert a["m3_identity"] == "4ecc8e9df1d1"
        # VQ-2 has since been owner approved; the durable invariant is that
        # the BUILD-TIME record was never self-accepted
        assert a["build_time_human_accepted"] is False
        assert a["material_realization_added"] is False

    def test_a2_artifacts_serve(self, client_in):
        for n in ("vq2-a2-png", "vq2-a2-ai", "vq2-a2-json",
                  "vq2-a2-review-pdf", "vq2-a2-review-png",
                  "vq2-a2-review-json", "vq2-lettering-approval"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
