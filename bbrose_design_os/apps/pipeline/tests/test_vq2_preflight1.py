"""VQ-2-FINAL-PREFLIGHT-1 — source normalisation, logo scale, Jost, manifest.

This pass answers an external audit, so the tests are written against the
audit's own numbers: 8,934 flattened line items, a 0.6035 logo/Rose ratio, a
43-vs-40 object discrepancy, and a supporting face that was rights-cleared but
stylistically unresolved. Each has to be provably closed, and the two places
where a claim could quietly overreach — "native Illustrator" and "production
colour" — must stay explicitly disclaimed.
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
AUD = J("vq2_a2_r2_final_audit.json")
REV = J("vq2_a2_r2_final_review.json")
SUP = J("vq2_supporting_copy_source_authority_v2.json")
MAN = J("vq2_a2_r2_final_object_manifest.json")
HAND = J("vq2_complete_product_handoff.json")
ST = J("vq2_state.json")
CLEAN = os.path.join(D, "vq2_a2_r2_final_clean.png")
GUIDES = os.path.join(D, "vq2_a2_r2_final_guides.png")
AI = os.path.join(D, "vq2_a2_r2_final.ai")


class TestStructuralNormalisation:

    def test_flattening_removed(self):
        sp = AUD["structural_paths"]
        assert sp["before"]["total"] == 8934
        assert sp["after"]["GLASS"] <= 128
        assert sp["after"]["COLLAR"] <= 64
        assert sp["after"]["DARK_CLOSURE"] <= 64
        assert sum(sp["after"].values()) < 400

    def test_anchor_ceiling_respected(self):
        for name, n in AUD["structural_paths"]["anchors_after"].items():
            assert n <= 128, name

    def test_deviation_is_zero_by_construction(self):
        sp = AUD["structural_paths"]
        assert sp["max_normal_deviation_mm"] == 0.0
        assert "already stored clean cubics" in sp["why_zero"]
        for v in sp["method"].values():
            assert v["refitted"] is False

    def test_symmetry_preserved_exactly(self):
        for name, mm in AUD["structural_paths"]["mirror_mismatch_mm"].items():
            assert mm == 0.0, name
        assert AUD["structural_paths"]["post_mirror_adjustment"] is False

    def test_all_density_gates_pass_and_no_failure_record(self):
        assert AUD["structural_paths"]["all_gates_pass"] is True
        assert not os.path.exists(
            os.path.join(D, "vq2_structural_path_density_failure.json"))


class TestLogoScale:

    def test_ratio_corrected_toward_the_measured_reference(self):
        lg = AUD["logo"]
        assert lg["previous_logo_to_rose_ratio"] == 0.6035
        assert abs(lg["logo_to_rose_ratio"] - 0.8134) < 0.002
        assert lg["uniform_scale"] > lg["previous_scale"]

    def test_geometry_untouched(self):
        lg = AUD["logo"]
        assert lg["components"] == 9
        assert lg["source_path_items"] == 314
        assert lg["distorted"] is False
        assert lg["redrawn"] is False

    def test_datums_preserved(self):
        assert AUD["logo"]["left_datum_px"] == 528
        assert AUD["logo"]["bottom_datum_px"] == 855


class TestSupportingCopyResolved:

    def test_resolved_with_a_geometric_sans(self):
        assert SUP["resolved"] is True
        assert SUP["authority"] == "PASS"
        assert SUP["selected"]["family"] == "Jost"
        assert "geometric" in SUP["selected"]["character"]
        assert SUP["style_compromise_code"] is None

    def test_licence_from_official_source_only(self):
        assert SUP["research_governed"] is True
        assert SUP["mirrors_or_free_font_sites_used"] is False
        assert SUP["permission_inferred_from_possession"] is False
        assert all("google/fonts" in s for s in SUP["sources_used"])
        assert SUP["selected"]["licence"] == \
            "SIL Open Font License, Version 1.1"
        assert SUP["selected"]["licence_evidence_strength"] == \
            "DIRECT_OFFICIAL_SOURCE_LICENCE_FILE"

    def test_binary_present_but_never_redistributed(self):
        assert SUP["selected"]["binary_committed"] is False
        assert os.path.exists(os.path.join(
            settings.BASE_DIR, "vendor", "fonts", "jost", "OFL.txt"))
        gi = open(os.path.join(os.path.dirname(settings.BASE_DIR), ".gitignore")).read()  # the one .gitignore
        assert "/bbrose_design_os/vendor/fonts/" in gi

    def test_complete_font_not_a_subset(self):
        assert SUP["selected"]["source_complete"] is True
        assert SUP["selected"]["is_subset"] is False
        assert SUP["selected"]["embedded_subset_extracted"] is False

    def test_no_transformed_typography(self):
        for k, v in SUP["prohibited_techniques_used"].items():
            assert v is False, k

    def test_wording_unchanged(self):
        assert SUP["visible_wording"] == "NIGHT REPAIR OIL"
        assert SUP["wording_changed"] is False
        assert SUP["capitalization_changed"] is False


class TestObjectManifest:

    def test_forty_objects_matching_the_audit(self):
        assert MAN["emitted_drawing_objects"] == 40 == MAN["audited_r2_count"]
        assert MAN["manifest_matches_emitted_file"] is True
        assert sum(MAN["groups"].values()) == 40

    def test_the_43_claim_is_reconciled_not_dropped(self):
        assert MAN["record_claimed_43_reconciled"] is True
        assert "fill AND a contour stroke" in MAN["reconciliation"]

    def test_no_raster_or_live_text(self):
        assert MAN["raster_images"] == 0
        assert MAN["live_text_objects"] == 0
        assert MAN["unsupported_visible_objects"] == 0


class TestCleanVersusTechnical:

    def test_clean_has_no_structural_contour_strokes(self):
        chk = AUD["clean_vs_technical"]
        assert chk["clean_structural_contour_strokes"] == 0
        assert chk["clean_stroked_is_divider_rule_only"] is True
        assert chk["clean_stroked_objects"] == 1   # the divider rule itself
        assert chk["clean_nonprinting_objects"] == 0

    def test_clean_png_has_no_guide_pixels(self):
        arr = np.asarray(Image.open(CLEAN).convert("RGB")).astype(int)
        for ref in ((58, 123, 213), (192, 57, 43)):
            assert int((np.abs(arr - np.array(ref)).sum(2) < 26).sum()) == 0

    def test_technical_proof_does_carry_guides(self):
        arr = np.asarray(Image.open(GUIDES).convert("RGB")).astype(int)
        assert int((np.abs(arr - np.array((58, 123, 213))).sum(2)
                    < 26).sum()) > 0
        assert AUD["clean_vs_technical"]["guides_nonprinting_objects"] > 0


class TestSourceFormatHonesty:

    def test_ai8_eps_source_with_named_layers(self):
        sf = AUD["source_format"]
        assert sf["ai_file"] == "ILLUSTRATOR_COMPATIBLE_AI8_EPS_VECTOR_SOURCE"
        assert sf["independent_selectable_objects"] is True
        assert len(sf["named_layers"]) == 8
        head = open(AI, "rb").read(2048).decode("latin-1")
        assert head.startswith("%!PS-Adobe-3.0 EPSF-3.0")
        assert "Adobe Illustrator(R) 8.0" in head
        body = open(AI, "rb").read().decode("latin-1")
        assert "%AI5_BeginLayer" in body
        for layer in sf["named_layers"]:
            assert layer in body, layer

    def test_never_claims_a_native_illustrator_cc_file(self):
        note = AUD["source_format"]["honest_note"]
        assert "NOT a native Illustrator CC document" in note
        assert AUD["readiness"]["native_illustrator_round_trip"] == \
            "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED"


class TestColourAuthority:

    def test_srgb_concept_only_and_production_blocked(self):
        c = AUD["colour_authority"]
        assert c["space"] == "sRGB concept colours only"
        assert c["code"] == \
            "PRODUCTION_COLOR_SEPARATION_BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        for k in ("cmyk_readiness_claimed", "pantone_equivalence_claimed",
                  "spot_colour_readiness_claimed",
                  "print_process_suitability_claimed"):
            assert c[k] is False, k

    def test_approved_flat_colours_preserved(self):
        c = AUD["colour_authority"]
        assert c["body"] == "#D9BDB5"
        assert c["collar"] == "#705242"
        assert c["closure"] == "#493034"
        assert c["artwork_ink"] == "#502525"


class TestFrozenInputs:

    def test_lf1_r1_and_typography_unchanged(self):
        p = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == "fcd8003994d52028"
        t = AUD["typography"]
        assert t["font_unit_contour_hash"] == "5db4403984ba6f75"
        assert t["unchanged_since_a2"] is True

    def test_m3_untouched(self):
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        assert AUD["m3_file_modified"] is False


class TestReleaseGateAndNoAutoAdvance:

    def test_final_state(self):
        """The preflight record is immutable; vq2_state has since advanced
        to owner approval, which is the point of the release gate."""
        assert REV["state"] == \
            "VQ2_FINAL_FRONT_ARTWORK_CANDIDATE_PENDING_OWNER_APPROVAL"
        assert ST["VQ_2"].startswith("VQ2_FINAL_FRONT_ARTWORK")

    def test_nothing_advanced_automatically(self):
        assert HAND["complete_product_review_started"] is False
        assert HAND["state"] == "PREPARED_NOT_STARTED"
        assert HAND["starts_only_on"] == "EXPLICIT_OWNER_APPROVAL"
        # the preflight handoff itself never started the next stage
        assert REV["packaging_started"] is False
        assert REV["vq3_started"] is False
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.

    def test_no_provider_or_image_generation(self):
        assert REV["provider_calls"] == 0
        assert REV["image_generation_calls"] == 0

    def test_not_acceptance(self):
        assert REV["human_accepted"] is False
        assert HAND["human_accepted"] is False
        blob = json.dumps(REV)
        for f in ("HUMAN_ACCEPTED", "MANUFACTURABLE", "PRODUCTION_READY"):
            assert f not in blob

    def test_carried_blockers_present(self):
        joined = " ".join(HAND["carried_blockers"])
        for need in ("PRODUCTION_FLAT_ARTWORK", "PRODUCTION_GEOMETRY",
                     "PRODUCTION_COLOR_SEPARATION",
                     "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED", "VQ-3"):
            assert need in joined, need


class TestOutputs:

    def test_all_required_files_exist(self):
        for n, floor in (("vq2_a2_r2_final.ai", 20_000),
                         ("vq2_a2_r2_final.pdf", 20_000),
                         ("vq2_a2_r2_final_clean.png", 10_000),
                         ("vq2_a2_r2_final_guides.png", 10_000),
                         ("vq2_a2_r2_final_audit.json", 1_000),
                         ("vq2_a2_r2_final_review.pdf", 100_000),
                         ("vq2_a2_r2_final_review.png", 5_000),
                         ("vq2_a2_r2_final_review.json", 1_000),
                         ("vq2_complete_product_handoff.json", 500)):
            assert os.path.getsize(os.path.join(D, n)) > floor, n

    def test_prior_revisions_preserved(self):
        for n in ("vq2_a2.ai", "vq2_a2_r1.ai", "vq2_a2_r2.ai"):
            assert os.path.exists(os.path.join(D, n)), n


@pytest.mark.django_db
class TestBoardServesFinal:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2pf1tester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_artifacts_serve(self, client_in):
        for n in ("vq2-final-ai", "vq2-final-pdf", "vq2-final-clean",
                  "vq2-final-guides", "vq2-final-audit",
                  "vq2-final-review-pdf", "vq2-final-review-json",
                  "vq2-handoff"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
