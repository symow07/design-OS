"""VQ2-A2-R1 — one bounded revision: ink, supporting copy, clean preview.

The revision is only legitimate if it changed exactly what was authorized. So
the load-bearing tests here are the negative ones: protected geometry did not
move, the clean preview has no guides in it (checked as pixels, not as a
claim), and an unidentified fallback could not have passed the supporting-copy
authority gate.
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
R1 = J("vq2_a2_r1.json")
A2 = J("vq2_a2.json")
REVIEW = J("vq2_a2_r1_artwork_review.json")
AUTH = J("vq2_supporting_copy_source_authority.json")
COLOUR = J("vq2_product_specific_logo_ink.json")
MEAS = J("vq2_supporting_copy_remeasure.json")
GATES = J("vq2_a2_r1_deterministic_gates.json")
ST = J("vq2_state.json")
CLEAN = os.path.join(D, "vq2_a2_r1_clean.png")
GUIDES = os.path.join(D, "vq2_a2_r1_guides.png")


class TestProtectedArtworkFrozen:

    def test_m3_byte_identical(self):
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        assert R1["m3_identity"] == "4ecc8e9df1d1"
        assert R1["m3_modified"] is False
        assert GATES["m3_drift"] == 0

    def test_lf1_r1_byte_identical(self):
        p = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == "fcd8003994d52028"
        assert R1["lf1_r1_ai_sha256_16"] == "fcd8003994d52028"
        assert GATES["lf1_r1_drift"] == 0

    def test_product_name_geometry_identical_to_a2(self):
        assert R1["lettering"]["font_unit_contour_hash"] == \
            A2["lettering"]["font_unit_contour_hash"]
        assert GATES["product_name_drift"] == 0
        for k in ("rose_scaled", "outlines_modified", "tracking_changed",
                  "axes_changed"):
            assert R1["lettering"][k] is False

    def test_approved_logo_geometry_identical(self):
        assert R1["logo"]["canonical_ai_sha256_16"] == \
            A2["logo"]["canonical_ai_sha256_16"]
        assert R1["logo"]["component_count"] == A2["logo"]["component_count"]
        assert R1["logo"]["emitted_segments"] == A2["logo"]["emitted_segments"]
        assert R1["logo"]["geometry_altered"] is False
        assert GATES["approved_logo_path_drift"] == 0

    def test_drift_was_checked_against_the_committed_a2_not_a_rerun(self):
        assert R1["protected_artwork_drift"] is None
        assert "COMMITTED vq2_a2.ai" in R1["protected_drift_method"]
        assert "not a rerun" in R1["protected_drift_method"]
        assert not os.path.exists(
            os.path.join(D, "vq2_a2_r1_protected_drift.json"))


class TestProductSpecificLogoInk:

    def test_colour_changed_without_geometry_changing(self):
        assert COLOUR["selected_product_ink"] == R1["product_ink"]
        assert COLOUR["logo_geometry_altered"] is False
        assert R1["logo"]["ink"] == R1["product_ink"]
        # geometry identical while ink differs from A2's logo ink
        assert COLOUR["a2_previous_inks"]["logo"] != R1["product_ink"]
        assert R1["logo"]["emitted_segments"] == A2["logo"]["emitted_segments"]

    def test_codes_recorded(self):
        for c in ("VQ2_APPROVED_LOGO_GEOMETRY_WITH_PRODUCT_SPECIFIC_FLAT_INK",
                  "VQ2_CYAN_LOGO_COLOUR_NOT_SELECTED_FOR_THIS_PRODUCT"):
            assert c in COLOUR["codes"]
        assert COLOUR["guideline_colour_used"] is False

    def test_one_shared_flat_colour_across_all_five_elements(self):
        assert COLOUR["shared_single_flat_colour"] is True
        assert set(COLOUR["applied_to"]) == {
            "approved BBROSE logo", "divider rule", "Rose", "Damascena",
            "NIGHT REPAIR OIL"}

    def test_no_cyan_in_the_final_artwork(self):
        assert COLOUR["cyan_pixels_in_final_artwork"] == 0
        arr = np.asarray(Image.open(CLEAN).convert("RGB")).astype(int)
        cyan = ((arr[:, :, 2] > 180) & (arr[:, :, 1] > 150) &
                (arr[:, :, 0] < 140)).sum()
        assert int(cyan) == 0

    def test_no_prohibited_colour_treatment(self):
        for k, v in COLOUR["prohibited_absent"].items():
            assert v is True, k


class TestCleanPreviewSeparation:

    def test_clean_document_has_zero_nonprinting_objects(self):
        assert R1["clean_preview_nonprinting_objects"] == 0
        assert GATES["clean_preview_measurement_objects"] == 0

    def test_clean_png_contains_no_guide_pixels(self):
        """Pixels, not a claim."""
        arr = np.asarray(Image.open(CLEAN).convert("RGB")).astype(int)
        for ref in ((58, 123, 213), (192, 57, 43)):
            hits = (np.abs(arr - np.array(ref)).sum(2) < 26).sum()
            assert int(hits) == 0, ref
        assert GATES["clean_preview_technical_guides"] == 0

    def test_guide_overlay_still_exists_and_does_show_guides(self):
        arr = np.asarray(Image.open(GUIDES).convert("RGB")).astype(int)
        hits = (np.abs(arr - np.array((58, 123, 213))).sum(2) < 26).sum()
        assert int(hits) > 0
        assert R1["guides_overlay_nonprinting_objects"] > 0

    def test_roles_are_distinct_and_hashed(self):
        assert R1["clean_png_role"] == "OWNER_REVIEW_CANDIDATE"
        assert R1["guides_png_role"] == "DIAGNOSTIC_ONLY"
        assert R1["clean_sha256_16"] != R1["guides_sha256_16"]
        assert len(R1["clean_sha256_16"]) == 16


class TestSupportingCopyAuthority:

    def test_authority_is_explicit_and_passes(self):
        assert AUTH["authority"] == "PASS"
        assert AUTH["selected_source"].startswith("Noto Sans")
        assert AUTH["unidentified_fallback_retained"] is False
        assert GATES["supporting_copy_source_authority"] == "PASS"

    def test_licence_evidence_is_a_committed_file_not_an_inference(self):
        sel = next(c for c in AUTH["candidates"] if c.get("selected"))
        assert sel["licence"] == "SIL Open Font License 1.1"
        assert "OFL.txt" in sel["licence_evidence"]
        assert sel["licence_evidence_strength"] == \
            "DIRECT_COMMITTED_LICENCE_FILE"
        assert os.path.exists(os.path.join(
            settings.BASE_DIR, "static", "fonts", "OFL.txt"))

    def test_unlicensed_fonts_were_rejected_on_evidence_not_taste(self):
        rej = next(c for c in AUTH["candidates"]
                   if c["licence_evidence_strength"] == "ABSENT")
        assert rej["selected"] is False
        assert rej["owner_permission"] == "NOT ESTABLISHED"
        assert "possession is not permission" in rej["rejection_reason"]

    def test_no_prohibited_technique_used(self):
        for k, v in AUTH["prohibited_techniques_used"].items():
            assert v is False, k
        sel = next(c for c in AUTH["candidates"] if c.get("selected"))
        assert sel["source_complete"] is True
        assert sel["is_subset"] is False
        assert sel["horizontally_compressed"] is False

    def test_imperfect_match_is_disclosed_not_hidden(self):
        assert AUTH["is_ideal_stylistic_match"] is False
        assert "NOT_IDEAL_STYLISTIC_MATCH" in AUTH["open_stylistic_finding"]
        assert R1["supporting_copy"]["is_ideal_stylistic_match"] is False

    def test_wording_and_capitalization_unchanged(self):
        assert AUTH["visible_wording"] == "NIGHT REPAIR OIL"
        assert AUTH["wording_changed"] is False
        assert AUTH["capitalization_changed"] is False
        assert R1["supporting_copy"]["text"] == "NIGHT REPAIR OIL"


class TestSupportingCopyComposition:

    def test_remeasured_from_the_native_reference(self):
        assert "native reference" in MEAS["measured_from"]
        assert MEAS["reference"]["ink_width_px"] == 205
        assert MEAS["reference"]["cap_height_px"] == 15

    def test_correction_narrows_and_enlarges(self):
        prev, now = MEAS["previous_a2"], MEAS["r1"]
        assert now["target_width_px"] < prev["width_px"]
        assert now["cap_height_px"] > prev["cap_height_px"]

    def test_no_collisions_and_positive_tracking(self):
        assert MEAS["r1"]["collisions"] == 0
        assert GATES["supporting_copy_collisions"] == 0
        assert MEAS["r1"]["tracking_sign"] == "POSITIVE"

    def test_clearly_subordinate_to_damascena(self):
        assert MEAS["subordinate_to_damascena"] is True
        assert MEAS["cap_ratio_to_damascena"] < 0.3

    def test_product_name_was_not_moved_to_accommodate_it(self):
        assert MEAS["rose_or_damascena_modified_to_accommodate"] is False


class TestCompositionNonRegression:

    def test_hierarchy_preserved(self):
        assert R1["hierarchy_order_top_to_bottom"] == \
            A2["hierarchy_order_top_to_bottom"]
        assert R1["hierarchy_matches_required"] is True

    def test_zone_and_object_counts(self):
        assert R1["front_artwork_zone_compliant"] is True
        assert GATES["artwork_zone_violations"] == 0
        assert R1["artwork_objects"] == A2["layer_manifest"]["artwork_objects"]

    def test_no_live_text_or_raster_logo(self):
        assert GATES["live_product_name_text"] == 0
        assert GATES["logo_raster_vector_objects"] == 0


class TestMaterialBoundary:

    def test_no_material_effect(self):
        assert R1["material_realization_added"] is False
        for k in ("gradients", "shadows", "highlights", "reflections",
                  "texture", "gloss", "photographic_lighting"):
            assert R1[k] == 0, k
        assert GATES["material_effect_count"] == 0


class TestScopeBoundaries:

    def test_exactly_one_r1_and_no_a3(self):
        assert R1["exactly_one_r1"] is True
        assert R1["vq2_a3_created"] is False
        assert not any(n.startswith("vq2_a3") for n in os.listdir(D))
        # R2 is a later authorized revision, not a second R1

    def test_no_lf2(self):
        assert R1["lf2_created"] is False
        assert not os.path.exists(os.path.join(D, "lf2"))

    def test_a2_preserved_and_superseded(self):
        assert ST["vq2_a2"] == "PRESERVED_SUPERSEDED_BY_A2_R1"
        # R1 has itself since been superseded by R2; the invariant is that
        # each revision is preserved rather than replaced in place
        assert ST["vq2_a2_r1"] in ("BUILT_PENDING_OWNER_REVIEW",
                                   "PRESERVED_SUPERSEDED_BY_A2_R2")
        assert os.path.exists(os.path.join(D, "vq2_a2.ai"))
        assert os.path.exists(os.path.join(D, "vq2_a2.png"))

    def test_state_boundaries_held(self):
        assert ST["VQ_1"] == "OWNER_ACCEPTED_AND_CLOSED"
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.
        assert ST["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert ST["PRODUCTION_GEOMETRY"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert R1["vq3_started"] is False

    def test_packaging_supplier_and_providers_untouched(self):
        assert R1["packaging_modified"] is False
        assert R1["supplier_requests_sent"] == 0
        assert R1["image_generation_calls"] == 0
        assert R1["provider_calls"] == 0
        assert REVIEW["image_generation_calls"] == 0

    def test_not_acceptance(self):
        assert R1["human_accepted"] is False
        assert R1["owner_decision_required"] is True
        assert REVIEW["state"] == "VQ2_A2_R1_BUILT_PENDING_OWNER_REVIEW"
        blob = json.dumps(REVIEW)
        for f in ("HUMAN_ACCEPTED", "MANUFACTURABLE", "PRODUCTION_READY"):
            assert f not in blob


class TestReviewPackage:

    def test_seventeen_required_sections(self):
        titles = REVIEW["section_titles"]
        for i in range(1, 18):
            assert any(t.startswith(f"{i}.") for t in titles), i

    def test_files_exist(self):
        for n, floor in (("vq2_a2_r1.ai", 10_000),
                         ("vq2_a2_r1_clean.png", 10_000),
                         ("vq2_a2_r1_guides.png", 10_000),
                         ("vq2_a2_r1_artwork_review.pdf", 100_000),
                         ("vq2_a2_r1_artwork_review.png", 5_000)):
            assert os.path.getsize(os.path.join(D, n)) > floor, n

    def test_all_three_owner_issues_addressed(self):
        a = REVIEW["owner_issues_addressed"]
        assert a["1_logo_colour_integration"].startswith("FIXED")
        assert a["2_visible_technical_guides"].startswith("FIXED")
        assert a["3_supporting_copy"].startswith("PARTIALLY RESOLVED")


@pytest.mark.django_db
class TestBoardServesR1:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2r1tester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_r1(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]
        a = v["a2"]
        # the board surfaces the LATEST VQ-2 front-artwork candidate; the
        # durable invariant is that it always awaits the owner
        assert a["state"].startswith("VQ2_")
        assert "PENDING_OWNER" in a["state"]
        # VQ-2 has since been owner approved; the durable invariant is that
        # the BUILD-TIME record was never self-accepted
        assert a["build_time_human_accepted"] is False

    def test_r1_artifacts_serve(self, client_in):
        for n in ("vq2-a2-r1-ai", "vq2-a2-r1-clean", "vq2-a2-r1-guides",
                  "vq2-a2-r1-review-pdf", "vq2-a2-r1-review-json",
                  "vq2-supporting-authority"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
