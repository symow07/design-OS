"""VQ2-A2-R2 — symmetry correction, logo subpath repair, flat artwork.

Both owner rejections of R1 were real defects, and both are fixed here. These
tests pin the fixes to the evidence that proves them, and — just as important —
pin the two places where a naive check would have reported a false pass: a
self-derived centreline, and a logo segment count that only matches 341 while
the subpath defect is still present.
"""
import hashlib
import json
import os

import numpy as np
import pytest
from PIL import Image
from django.conf import settings

D = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
J = lambda n: json.load(open(os.path.join(D, n)))                     # noqa
R2 = J("vq2_a2_r2.json")
R1 = J("vq2_a2_r1.json")
REVIEW = J("vq2_a2_r2_artwork_review.json")
SYM = J("vq2_a2_r2_symmetry_proof.json")
LOGOV = J("vq2_a2_r2_logo_validation.json")
DIAG = J("vq2_a2_r1_defect_diagnosis.json")
LOGO = J("vq2_authoritative_bbrose_logo.json")
ST = J("vq2_state.json")
CLEAN = os.path.join(D, "vq2_a2_r2_clean.png")
GUIDES = os.path.join(D, "vq2_a2_r2_guides.png")


class TestBilateralSymmetry:

    def test_every_component_within_tolerance(self):
        assert SYM["all_pass"] is True
        for name in ("GLASS", "COLLAR", "DARK_CLOSURE"):
            c = SYM["components"][name]
            assert c["worst_lr_mm"] == 0.0, name
            assert c["bbox_mid_deviation_mm"] == 0.0, name
            assert c["pass"] is True
            assert c["worst_lr_mm"] <= SYM["tolerance_mm"]

    def test_the_closure_defect_is_actually_fixed(self):
        before = DIAG["defect_1_structural_symmetry"]["DARK_CLOSURE"]
        assert before["verdict"] == "FAIL"
        assert before["worst_lr_mm"] == 8.531533
        assert SYM["components"]["DARK_CLOSURE"]["worst_lr_mm"] == 0.0

    def test_required_architecture(self):
        assert SYM["architecture"] == \
            "MASTER_LEFT_PROFILE -> MIRROR_ACROSS_CENTERLINE"
        for k in ("independently_authored_sides", "post_mirror_adjustment",
                  "separate_shoulder_construction",
                  "separate_base_construction"):
            assert SYM[k] is False, k

    def test_measured_against_the_canonical_centreline(self):
        """A self-derived centre cannot detect centreline deviation."""
        assert SYM["canonical_centerline_mm"] == 36.541193
        assert "self-derived" in SYM["method_note"]
        assert "wrongly passed" in SYM["method_note"]


class TestLogoExtractionFidelity:

    def test_all_source_path_items_preserved(self):
        assert LOGOV["path_items_match"] is True
        assert LOGOV["emitted_line_and_curve_items"] == \
            LOGO["source_path_items"] == 314

    def test_all_nine_components_present(self):
        assert LOGOV["component_count_match"] is True
        assert LOGOV["components_emitted"] == 9

    def test_counters_preserved(self):
        for part, ok in LOGOV["counters_preserved"].items():
            assert ok is True, part
        assert LOGOV["medallion_subpaths"] >= 4
        assert LOGOV["subpaths_emitted"] == 18

    def test_subpath_repair_means_the_count_must_exceed_341(self):
        """341 here would mean the R1 defect was still present.

        The canonical figure counts one MoveTo per COMPONENT (9). R2 correctly
        emits one per SUBPATH (18), so it must be nine higher.
        """
        assert LOGOV["total_segments"] == 350
        assert LOGOV["canonical_emitted_segments_figure"] == 341
        assert LOGOV["total_segments"] - 341 == 9
        assert "would mean the defect was still present" in \
            LOGOV["segment_count_reconciliation"]

    def test_no_tracing_reconstruction_or_approximation(self):
        for k in ("traced", "reconstructed", "approximated", "redrawn",
                  "image_trace_used", "nonuniform_scaling"):
            assert LOGOV[k] is False, k

    def test_source_is_the_canonical_extraction(self):
        assert LOGOV["canonical_ai_sha256_16"] == LOGO["canonical_ai_sha256"]
        assert "BBROSE.pdf page 1" in LOGOV["source"]


class TestTypographyFrozen:

    def test_lf1_r1_file_byte_identical(self):
        p = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == "fcd8003994d52028"
        assert R2["lf1_r1_ai_sha256_16"] == "fcd8003994d52028"

    def test_glyph_geometry_unchanged_across_a2_r1_r2(self):
        assert R2["lettering"]["font_unit_contour_hash"] == \
            "5db4403984ba6f75" == R1["lettering"]["font_unit_contour_hash"]

    def test_axes_and_outlines_untouched(self):
        lt = R2["lettering"]
        assert lt["axes"] == {"opsz": 100, "wght": 400}
        for k in ("axes_changed", "rose_scaled", "outlines_modified",
                  "tracking_changed"):
            assert lt[k] is False, k

    def test_freeze_method_is_honest_about_the_unusable_check(self):
        assert R2["typography_frozen"] is True
        assert "NOT reusable" in R2["typography_freeze_method"]
        assert "dense polylines" in R2["typography_freeze_method"]


class TestFlatArtworkAndMaterialBoundary:

    def test_flat_fills_present(self):
        fa = R2["flat_artwork"]
        for k in ("body_fill", "collar_fill", "closure_fill"):
            assert fa[k].startswith("#") and len(fa[k]) == 7, k

    def test_one_flat_tone_each_so_no_gradient_exists(self):
        fa = R2["flat_artwork"]
        assert "single flat tone" in fa["derivation"]
        for k in ("gradients", "reflections", "shadows", "gloss", "lighting",
                  "texture", "glass_realism"):
            assert fa[k] == 0, k
        assert fa["material_realization_added"] is False

    def test_fills_are_concept_derived(self):
        assert "concept #97" in R2["flat_artwork"]["derivation"]

    def test_artwork_object_count_grew_only_by_the_three_fills(self):
        assert R2["artwork_objects"] == R1["artwork_objects"] + 3


class TestCleanPreview:

    def test_zero_nonprinting_objects(self):
        assert R2["clean_preview_nonprinting_objects"] == 0

    def test_zero_guide_pixels_in_the_render(self):
        arr = np.asarray(Image.open(CLEAN).convert("RGB")).astype(int)
        for ref in ((58, 123, 213), (192, 57, 43)):
            assert int((np.abs(arr - np.array(ref)).sum(2) < 26).sum()) == 0
        assert R2["clean_preview_guide_pixels"] == 0
        assert R2["clean_preview_red_guide_pixels"] == 0

    def test_guide_overlay_kept_separate_and_populated(self):
        arr = np.asarray(Image.open(GUIDES).convert("RGB")).astype(int)
        assert int((np.abs(arr - np.array((58, 123, 213))).sum(2)
                    < 26).sum()) > 0
        assert R2["guides_overlay_nonprinting_objects"] > 0
        assert R2["clean_sha256_16"] != R2["guides_sha256_16"]

    def test_roles_declared(self):
        assert R2["clean_png_role"] == "OWNER_REVIEW_CANDIDATE"
        assert R2["guides_png_role"] == "DIAGNOSTIC_ONLY"


class TestM3Freeze:

    def test_m3_file_untouched(self):
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        assert R2["m3_file_identity"] == "4ecc8e9df1d1"
        assert R2["m3_file_modified"] is False

    def test_closure_divergence_is_disclosed_not_hidden(self):
        assert R2["m3_rendered_closure_differs"] is True
        note = R2["m3_divergence_note"]
        assert "asymmetric" in note
        assert "not an edit to M3" in note


class TestStateAndScope:

    def test_final_state(self):
        """R2's own record is immutable history; vq2_state is live."""
        assert R2["state"] == "VQ2_A2_R2_BUILT_PENDING_OWNER_REVIEW"
        assert ST["VQ_2"].startswith("VQ2_")
        assert ST["vq2_a2_r2"] in ("BUILT_PENDING_OWNER_REVIEW",
                                   "PRESERVED_SUPERSEDED_BY_A2_R2_FINAL")
        assert ST["vq2_a2_r1"] == "PRESERVED_SUPERSEDED_BY_A2_R2"

    def test_nothing_forbidden_was_created(self):
        assert R2["exactly_one_r2"] is True
        assert R2["vq2_a3_created"] is False
        assert R2["lf2_created"] is False
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.
        assert R2["vq3_started"] is False
        assert not any(n.startswith("vq2_a3") for n in os.listdir(D))

    def test_r1_preserved_on_disk(self):
        for n in ("vq2_a2_r1.ai", "vq2_a2_r1_clean.png",
                  "vq2_a2_r1_guides.png"):
            assert os.path.exists(os.path.join(D, n)), n

    def test_packaging_supplier_and_providers_untouched(self):
        assert R2["packaging_modified"] is False
        assert R2["supplier_requests_sent"] == 0
        assert R2["image_generation_calls"] == 0
        assert R2["provider_calls"] == 0

    def test_production_still_blocked(self):
        assert R2["production_flat_artwork"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert R2["production_geometry"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"

    def test_not_acceptance(self):
        assert R2["human_accepted"] is False
        assert R2["owner_decision_required"] is True
        blob = json.dumps(REVIEW)
        for f in ("HUMAN_ACCEPTED", "MANUFACTURABLE", "PRODUCTION_READY"):
            assert f not in blob


class TestReviewPackage:

    def test_required_content_present(self):
        titles = " ".join(REVIEW["section_titles"]).lower()
        for need in ("r1 defects", "r2 corrections", "symmetry proof",
                     "logo extraction proof", "typography freeze proof",
                     "clean preview", "guide overlay", "vq-3 blockers"):
            assert need in titles, need

    def test_files_exist(self):
        for n, floor in (("vq2_a2_r2.ai", 10_000),
                         ("vq2_a2_r2_clean.png", 10_000),
                         ("vq2_a2_r2_guides.png", 10_000),
                         ("vq2_a2_r2_artwork_review.pdf", 100_000),
                         ("vq2_a2_r2_artwork_review.png", 5_000)):
            assert os.path.getsize(os.path.join(D, n)) > floor, n


@pytest.mark.django_db
class TestBoardServesR2:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2r2tester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_r2(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]
        # latest candidate; R2 has since been normalised into A2-R2-FINAL
        assert v["a2"]["state"].startswith("VQ2_")
        assert "PENDING_OWNER" in v["a2"]["state"]
        assert v["a2"]["build_time_human_accepted"] is False

    def test_artifacts_serve(self, client_in):
        for n in ("vq2-a2-r2-ai", "vq2-a2-r2-clean", "vq2-a2-r2-guides",
                  "vq2-a2-r2-review-pdf", "vq2-a2-r2-review-json",
                  "vq2-a2-r2-symmetry", "vq2-a2-r2-logo-validation"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
