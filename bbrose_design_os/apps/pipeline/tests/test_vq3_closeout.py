"""VQ-3 closeout — evidence artefacts only, then workstream closure.

Everything here had to be produced WITHOUT touching the selected render, so the
tests are almost entirely about what did not happen: no regeneration, no
provider call, no material change. The one substantive addition is a recorded
correction — my earlier prose reported Inspector A's actionable counts as if
they were two-inspector totals.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings


VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
W3 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq3")
J = lambda n: json.load(open(os.path.join(W3, n)))                    # noqa
CO = J("vq3_material_closeout.json")
VER = J("vq3_closeout_verification.json")
MS = J("vq3_m3_component_mask_sheet.json")
GO = J("vq3_m3_geometry_overlay.json")
CU = J("vq3_m3_material_closeups.json")
REV = J("vq3_material_review.json")
SEL = J("vq3_owner_selection.json")
ST = json.load(open(os.path.join(VQ2, "vq2_state.json")))
M3 = os.path.join(settings.BASE_DIR, REV["candidates"]["M3"]["path"])
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]  # noqa


class TestFrozenInputs:

    def test_selected_render_byte_identical(self):
        assert sha(M3) == "fbdedc5b23e31745"
        assert CO["selected_sha256_16"] == "fbdedc5b23e31745"
        assert VER["selected_render_hash_unchanged"] is True

    def test_no_frozen_input_drift(self):
        assert VER["frozen_input_drift"] == []
        assert VER["frozen_inputs_checked"] >= 16
        for k, v in VER["frozen_inputs"].items():
            assert v["match"] is True, k
        assert not os.path.exists(
            os.path.join(W3, "vq3_closeout_frozen_input_drift.json"))

    def test_alternates_preserved(self):
        for k in ("M1", "M2"):
            p = os.path.join(settings.BASE_DIR,
                             REV["candidates"][k]["path"])
            assert os.path.exists(p), k
            assert sha(p) == SEL["alternates"][k]["sha256_16"]
            assert "PRESERVED_FOR_AUDIT" in CO["alternates"][k]

    def test_all_eight_masks_unchanged(self):
        assert VER["all_eight_mask_hashes_unchanged"] is True
        for n, want in REV["masks"]["mask_sha"].items():
            assert sha(os.path.join(W3, "masks", f"mask_{n.lower()}.png")) \
                == want, n

    def test_upstream_identities_live(self):
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        for rel, want in (("lf1_r1/vq2_rose_damascena_lf1_r1.ai",
                           "fcd8003994d52028"),
                          ("brand/bbrose_logo_approved.ai",
                           "a2b2a82969389ac2"),
                          ("vq2_a2_r2_final_clean.png", "94ec944326889c20")):
            assert sha(os.path.join(VQ2, rel)) == want, rel


class TestComponentMaskSheet:

    def test_built_from_frozen_masks_only(self):
        assert "frozen vector-derived mask PNGs" in MS["source"]
        assert MS["regenerated_from_colour_threshold"] is False
        assert MS["hand_drawn"] is False
        assert MS["inferred_from_render"] is False
        assert MS["mask_hashes_match_frozen_records"] is True

    def test_all_required_panels(self):
        for n in ("BODY", "COLLAR", "DARK_CLOSURE", "LOGO", "DIVIDER", "ROSE",
                  "DAMASCENA", "SUPPORTING_COPY"):
            assert n in MS["panels"], n
        assert MS["mask_dimensions_match_m3"] is True

    def test_spill_and_gap_statistics_clean(self):
        assert MS["artwork_spill_outside_product"] == 0
        assert MS["structure_gap_px"] == 0
        assert MS["artwork_masks_pixel_identical_to_accepted_geometry"] is True

    def test_sheet_exists_and_is_hashed(self):
        p = os.path.join(W3, "vq3_m3_component_mask_sheet.png")
        assert os.path.getsize(p) > 10_000
        assert sha(p) == MS["sheet_sha256_16"]


class TestGeometryOverlay:

    def test_underlying_render_untouched(self):
        assert GO["underlying_render_modified"] is False
        assert GO["underlying_render_sha256_16"] == "fbdedc5b23e31745"
        assert sha(M3) == GO["underlying_render_sha256_16"]

    def test_derived_from_frozen_vectors_not_pixels(self):
        assert "no geometry inferred from pixels" in GO["derived_from"]
        assert VER["geometry_overlay_derived_from_frozen_vectors"] is True

    def test_every_gate_exact(self):
        g = GO["gates"]
        assert g["silhouette_iou"] == 1.0
        for k in ("centerline_drift_px", "body_width_drift_px",
                  "collar_width_drift_px", "closure_width_drift_px",
                  "artwork_anchor_drift_px", "logo_drift", "glyph_drift",
                  "clipping", "unsupported_objects", "mask_spill"):
            assert g[k] == 0, k

    def test_shows_everything_required(self):
        for s in ("bottle outer silhouette", "closure silhouette",
                  "collar silhouette", "centerline", "artwork anchors",
                  "logo bounds", "Rose bounds", "Damascena bounds",
                  "supporting-copy bounds", "component boundaries"):
            assert s in GO["shows"], s
        for n in ("LOGO", "ROSE", "DAMASCENA", "SUPPORTING_COPY", "DIVIDER"):
            assert n in GO["artwork_bounds_px"], n

    def test_not_a_replacement_preview(self):
        assert GO["is_not_a_replacement_clean_preview"] is True


class TestMaterialCloseups:

    def test_crops_of_the_frozen_render_only(self):
        assert CU["source_sha256_16"] == "fbdedc5b23e31745"
        assert VER["closeups_derived_from_frozen_m3_pixels"] is True

    def test_nothing_was_enhanced(self):
        for k in ("repainted", "enhanced", "sharpened", "recoloured",
                  "regenerated"):
            assert CU[k] is False, k
        assert CU["resample"].startswith("NEAREST")

    def test_all_four_panels_measured(self):
        for p in ("A_BODY", "B_COLLAR", "C_DARK_CLOSURE", "D_ARTWORK"):
            assert p in CU["panels"], p
            assert CU["panels"][p]["mean"]

    def test_material_readings_hold(self):
        assert CU["body_frosted_not_plastic"] is True
        assert CU["collar_blown_highlight_px"] == 0
        assert CU["collar_warmer_than_body"] is True
        assert CU["collar_more_reflective_than_body"] is True
        assert CU["closure_not_metallic"] is True


class TestActionableCountCorrection:
    """My earlier prose reported A-only counts as two-inspector totals."""

    def test_correction_recorded(self):
        c = VER["actionable_count_correction"]
        assert c["code"] == "VQ3_ACTIONABLE_COUNT_MISREPORTED_IN_PRIOR_SUMMARY"
        assert c["previously_reported"] == {"M1": 2, "M2": 5, "M3": 0}
        assert c["correct"] == {"M1": 4, "M2": 7, "M3": 0}
        assert c["records_were_always_correct"] is True

    def test_correct_totals_match_the_raw_inspector_results(self):
        for k, want in VER["actionable_counts_true"].items():
            got = sum(REV["inspections"][k][s]["result"][
                "actionable_defect_count"] for s in ("A", "B"))
            assert got == want, k

    def test_correction_does_not_change_the_selection(self):
        c = VER["actionable_count_correction"]
        assert c["affects_selection"] is False
        assert VER["actionable_counts_true"]["M3"] == 0
        assert CO["selected"] == "M3"


class TestNothingHappenedThatShouldNot:

    def test_no_regeneration_or_modification(self):
        for k in ("render_regenerated", "material_modified",
                  "typography_modified", "logo_modified", "m4_created",
                  "packaging_started"):
            assert VER[k] is False, k
        assert CO["m4_created"] is False

    def test_no_provider_or_image_generation_calls(self):
        assert VER["new_provider_calls"] == 0
        assert VER["new_image_generation_calls"] == 0
        assert CO["provider_calls"] == 0
        assert CO["image_generation_calls"] == 0

    def test_no_supplier_request(self):
        assert VER["supplier_requests_sent"] == 0
        assert CO["supplier_requests_sent"] == 0

    def test_no_m4_on_disk(self):
        assert not any(n.startswith("vq3_m4") for n in os.listdir(W3))

    def test_ranking_preserved(self):
        assert VER["ranking_preserved"] == ["M3", "M1", "M2"]
        assert REV["rank_order"] == ["M3", "M1", "M2"]


class TestCollarIntegrationStillSupported:

    def test_supported_by_six_independent_strands(self):
        c = VER["collar_body_integration"]
        assert c["code"] == "VQ3_COLLAR_BODY_MATERIAL_INTEGRATION_RESOLVED"
        assert c["still_supported"] is True
        assert len(c["supported_by"]) >= 6
        joined = " ".join(c["supported_by"]).lower()
        for need in ("owner selection", "inspections", "close-up",
                     "warmer", "reflective", "lighting"):
            assert need in joined, need


class TestClosure:

    def test_workstream_closed_with_all_codes(self):
        assert CO["state"] == "OWNER_APPROVED_AND_CLOSED"
        assert CO["vq3_state"] == "VQ3_WORKSTREAM_CLOSED"
        for c in ("VQ3_OWNER_SELECTED_M3",
                  "VQ3_MATERIAL_CANDIDATE_M3_ACCEPTED",
                  "VQ3_MATERIAL_SELECTION_RESOLVED_BY_OWNER",
                  "VQ3_COLLAR_BODY_MATERIAL_INTEGRATION_RESOLVED",
                  "VQ3_CLOSEOUT_EVIDENCE_COMPLETE",
                  "VQ3_WORKSTREAM_CLOSED"):
            assert c in CO["codes"], c
        assert ST["VQ_3"] == "OWNER_APPROVED_AND_CLOSED"
        assert ST["VQ3_STATE"] == "VQ3_WORKSTREAM_CLOSED"
        assert ST["VQ3_CLOSED"] is True

    def test_closed_only_because_all_three_artefacts_exist(self):
        assert CO["evidence_complete"] is True
        for n in ("vq3_m3_component_mask_sheet.png",
                  "vq3_m3_geometry_overlay.png",
                  "vq3_m3_material_closeups.png"):
            assert os.path.getsize(os.path.join(W3, n)) > 10_000, n
        assert set(CO["evidence_artifacts"]) == {
            "component_mask_sheet", "geometry_overlay", "material_closeups"}

    def test_upstream_still_closed(self):
        assert CO["upstream"] == {"VQ_1": "CLOSED", "VQ_2": "CLOSED",
                                  "COMPLETE_PRODUCT_REVIEW": "CLOSED"}
        assert ST["VQ_1_CLOSED"] is True
        assert ST["VQ_2_CLOSED"] is True

    def test_packaging_still_not_started(self):
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert CO["packaging_started"] is False


class TestProductionBoundary:

    def test_all_five_gates_blocked(self):
        p = CO["production_boundaries"]
        assert p["PRODUCTION_GEOMETRY"] == "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert p["PRODUCTION_COLOR_SEPARATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["PRODUCTION_MATERIAL_SPECIFICATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["ILLUSTRATOR_EXECUTION_VERIFICATION"] == \
            "REQUIRED_BEFORE_PRODUCTION_AUTHORITY"
        for k, v in p.items():
            if k == "ILLUSTRATOR_EXECUTION_VERIFICATION":
                # this has since PASSED on a human Illustrator round trip;
                # VQ-3 closeout neither conferred nor depends on it
                assert ST[k] == "PASSED"
            else:
                assert ST[k] == v, k

    def test_closure_disclaims_production_meaning(self):
        for n in ("manufacturability", "supplier compatibility",
                  "material formulation", "anodized-colour specification",
                  "Pantone or CMYK authority", "production readiness"):
            assert n in CO["closure_does_not_imply"], n

    def test_never_claims_readiness(self):
        blob = json.dumps(CO)
        for f in ("MANUFACTURABLE", "PRODUCTION_READY", "GATE_2_APPROVED"):
            assert f not in blob


class TestPackage:

    def test_all_eighteen_required_sections_covered(self):
        titles = " ".join(CO["section_titles"])
        for n in ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.",
                  "10-13.", "14.", "15.", "16.", "17.", "18."):
            assert n in titles, n

    def test_files_exist(self):
        for n, floor in (("vq3_material_closeout.pdf", 100_000),
                         ("vq3_material_closeout.png", 5_000),
                         ("vq3_material_closeout.json", 1_000),
                         ("vq3_closeout_verification.json", 500)):
            assert os.path.getsize(os.path.join(W3, n)) > floor, n


@pytest.mark.django_db
class TestBoardShowsClosure:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq3cotester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_closure(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]["vq3"]
        assert v["state"] == "OWNER_APPROVED_AND_CLOSED"
        assert v["selected"] == "M3"
        assert v["remaining_closeout_items"] == 0
        assert v["evidence_complete"] is True
        assert v["grants_production_authority"] is False

    def test_closeout_artifacts_serve(self, client_in):
        for n in ("vq3-closeout-pdf", "vq3-closeout-json", "vq3-mask-sheet",
                  "vq3-geometry-overlay", "vq3-material-closeups",
                  "vq3-closeout-verification"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
