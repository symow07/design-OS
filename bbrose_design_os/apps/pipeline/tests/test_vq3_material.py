"""VQ-3 material realization — three candidates, frozen geometry, no redesign.

A rendering stage on top of three closed workstreams, so the tests are mostly
non-regression: the accepted geometry and artwork must be reproduced exactly,
the candidates may differ only in listed material parameters, and the image-
generation budget must not be exceeded. Ranking is advisory and must never read
as approval.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
W3 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq3")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa
REV = J(W3, "vq3_material_review.json")
RES = J(W3, "vq3_material_research.json")
ST = J(VQ2, "vq2_state.json")
KEYS = ("M1", "M2", "M3")


class TestUpstreamClosedAndFrozen:

    def test_all_three_workstreams_closed(self):
        assert REV["upstream"] == {"VQ_1": "CLOSED", "VQ_2": "CLOSED",
                                   "COMPLETE_PRODUCT_REVIEW": "CLOSED"}
        assert ST["VQ_1_CLOSED"] is True
        assert ST["VQ_2_CLOSED"] is True

    def test_frozen_identities_live_on_disk(self):
        f = REV["frozen"]
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == f["m3"] == "4ecc8e9df1d1"
        for rel, want in (("lf1_r1/vq2_rose_damascena_lf1_r1.ai", f["lf1_r1"]),
                          ("brand/bbrose_logo_approved.ai",
                           f["approved_logo"]),
                          ("vq2_a2_r2_final_clean.png", f["clean_preview"])):
            p = os.path.join(VQ2, rel)
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:16] == want, rel

    def test_font_unit_hash_reproduced_exactly(self):
        assert REV["masks"]["font_unit_contour_hash"] == "5db4403984ba6f75"

    def test_no_accepted_asset_changed(self):
        assert REV["accepted_geometry_changed"] is False
        assert REV["accepted_artwork_changed"] is False

    def test_no_drift_record(self):
        assert not os.path.exists(
            os.path.join(W3, "vq3_frozen_complete_product_drift.json"))


class TestMasksDeriveFromVectors:

    def test_masks_are_rasterised_geometry_not_hand_drawn(self):
        assert "no mask was drawn by hand" in REV["masks"]["derived_from"]
        assert "accepted vector geometry" in REV["masks"]["derived_from"]

    def test_every_component_mask_exists_and_is_hashed(self):
        for n in ("BODY", "COLLAR", "DARK_CLOSURE", "LOGO", "DIVIDER", "ROSE",
                  "DAMASCENA", "SUPPORTING_COPY"):
            assert n in REV["masks"]["mask_sha"], n
            assert len(REV["masks"]["mask_sha"][n]) == 16
            p = os.path.join(W3, "masks", f"mask_{n.lower()}.png")
            assert os.path.exists(p), n

    def test_zero_artwork_spill_outside_the_product(self):
        assert REV["masks"]["artwork_spill_outside_product"] == 0


class TestGeometryPreservation:

    def test_all_gates_pass_for_every_candidate(self):
        assert REV["all_geometry_gates_pass"] is True
        for k in KEYS:
            assert REV["gates"][k]["pass"] is True, k

    def test_silhouette_and_drift_exact(self):
        for k in KEYS:
            g = REV["gates"][k]
            assert g["silhouette_iou"] >= 0.9995
            assert g["centerline_drift_px"] <= 1
            for w in ("body_width_drift_px", "collar_width_drift_px",
                      "closure_width_drift_px"):
                assert abs(g[w]) <= 1, (k, w)
            assert g["artwork_anchor_drift_px"] == 0
            assert g["logo_drift"] == 0
            assert g["glyph_drift"] == 0
            assert g["mask_spill"] == 0
            assert g["clipping"] == 0
            assert g["internal_mechanism_visible"] == 0

    def test_silhouette_measured_against_the_real_background_frame(self):
        """A colour-threshold proxy reported false drift; this pins the fix."""
        for k in KEYS:
            note = REV["gates"][k]["measurement_note"]
            assert "background-only frame" in note
            assert "masquerade as" in note

    def test_text_identity_exact(self):
        for k in KEYS:
            assert REV["gates"][k]["line_break_identity"] == "EXACT"
            assert REV["gates"][k]["spelling_identity"] == "EXACT"
            assert REV["gates"][k]["artwork_pixel_coverage"] >= 0.999


class TestCandidateBudget:

    def test_exactly_three_candidates_no_fourth(self):
        assert REV["candidate_count"] == 3
        assert REV["fourth_candidate_created"] is False
        assert set(REV["candidates"]) == set(KEYS)
        assert not any(n.startswith("vq3_m4") for n in os.listdir(W3))

    def test_image_generation_budget_not_exceeded(self):
        rm = REV["render_method"]
        assert rm["image_generation_calls"] == 0
        assert rm["image_generation_calls"] <= rm["image_generation_budget"]
        assert rm["image_generation_budget"] == 3

    def test_stage_b_declared_not_used_with_a_reason(self):
        rm = REV["render_method"]
        assert rm["stage_b_image_model_enhancement"] == "NOT_USED"
        assert "optional" in rm["stage_b_reason"]
        for k in KEYS:
            assert REV["candidates"][k]["image_model_enhanced"] is False
            assert REV["candidates"][k]["deterministic_render"] is True

    def test_candidates_differ_only_in_permitted_material_parameters(self):
        allowed = {"M1": set(),
                   "M2": {"body_gloss", "body_sigma", "body_edge",
                          "body_grain"},
                   "M3": {"collar_warm", "collar_contrast"}}
        for k in KEYS:
            assert set(REV["candidates"][k]["differs_from_m1_in"]) == \
                allowed[k], k

    def test_all_candidate_files_exist(self):
        for k in KEYS:
            p = REV["candidates"][k]["path"]
            assert os.path.getsize(
                os.path.join(settings.BASE_DIR, p)) > 50_000, k


class TestMaterialSemantics:

    def test_collar_is_metal_not_brown_plastic(self):
        for k in KEYS:
            m = REV["gates"][k]["materials"]
            assert m["collar_warmer_than_body"] is True, k
            assert m["collar_more_reflective_than_body"] is True, k
            assert m["collar_blown_highlight_px"] == 0, k
            for s in ("A", "B"):
                r = REV["inspections"][k][s]["result"]
                assert r["collar_rose_gold_metal"] == "PASS", (k, s)
                assert r["looks_like_brown_plastic_collar"] is False, (k, s)

    def test_body_reads_frosted_not_opaque_plastic(self):
        for k in KEYS:
            assert REV["gates"][k]["materials"]["body_frosted_not_flat"] is True
            for s in ("A", "B"):
                r = REV["inspections"][k][s]["result"]
                assert r["body_frosted_glass"] == "PASS", (k, s)
                assert r["looks_like_opaque_plastic_body"] is False, (k, s)

    def test_closure_is_satin_rubber_not_metal(self):
        for k in KEYS:
            assert REV["gates"][k]["materials"]["closure_not_metallic"] is True
            for s in ("A", "B"):
                assert REV["inspections"][k][s]["result"][
                    "closure_satin_rubber"] == "PASS", (k, s)

    def test_collar_base_shift_is_disclosed(self):
        cb = REV["collar_body_integration"]
        assert "starting point" in cb["collar_base_shift"]
        assert cb["collar_material_base"].startswith("#")

    def test_carried_integration_item_resolved_with_evidence(self):
        cb = REV["collar_body_integration"]
        assert cb["carried_item"] == \
            "VQ3_COLLAR_BODY_MATERIAL_INTEGRATION_REQUIRED"
        assert cb["resolved"] is True
        assert cb["resolved_code"] == \
            "VQ3_COLLAR_BODY_MATERIAL_INTEGRATION_RESOLVED"
        assert cb["evidence"]


class TestDualInspection:

    def test_two_independent_inspections_per_candidate(self):
        assert REV["provider_calls"] == 6
        for k in KEYS:
            for s in ("A", "B"):
                i = REV["inspections"][k][s]
                assert i["status"] == "COMPLETED", (k, s)
                assert i["request_id"]
                assert i["raw_output"]
                assert hashlib.sha256(
                    i["raw_output"].encode()).hexdigest()[:16] == i["raw_sha"]

    def test_inspectors_are_distinct_and_isolated(self):
        for k in KEYS:
            a, b = REV["inspections"][k]["A"], REV["inspections"][k]["B"]
            assert a["identity"] != b["identity"]
            assert a["request_id"] != b["request_id"]
            assert a["raw_output"] not in b["raw_output"]

    def test_artwork_legible_in_every_candidate(self):
        for k in KEYS:
            for s in ("A", "B"):
                assert REV["inspections"][k][s]["result"][
                    "artwork_legible"] is True, (k, s)


class TestRankingIsAdvisory:

    def test_all_criteria_ranked_for_each_candidate(self):
        for k in KEYS:
            assert len(REV["ranking"][k]["criteria"]) == 9
            assert 1 <= REV["ranking"][k]["mean"] <= 10
            assert REV["ranking"][k]["rank"] in (1, 2, 3)

    def test_result_is_pending_owner_selection_not_approval(self):
        assert REV["result_classification"] == \
            "VQ3_MATERIAL_CANDIDATES_PENDING_OWNER_SELECTION"
        assert REV["human_accepted"] is False
        assert REV["owner_selection_required"] is True

    def test_top_rank_is_not_recorded_as_selected(self):
        blob = json.dumps(REV["ranking"])
        for f in ("SELECTED", "APPROVED", "OWNER_ACCEPTED"):
            assert f not in blob


class TestGovernedResearch:

    def test_within_the_bounded_caps(self):
        assert len(RES["domains_used"]) <= RES["domain_cap"]
        assert RES["pages_fetched"] <= RES["page_cap"]
        assert RES["pdfs_fetched"] <= RES["pdf_cap"]

    def test_only_official_or_recognised_sources(self):
        for s in RES["sources"]:
            assert "official" in s["category"] or "recognised" in s["category"]
            assert s["url"].startswith("https://")
            for k in ("publisher", "title", "accessed", "rights",
                      "confidence"):
                assert s[k], (s["url"], k)

    def test_no_prohibited_action_taken(self):
        for k, v in RES["prohibited_actions_taken"].items():
            assert v is False, k

    def test_research_does_not_establish_production_authority(self):
        assert RES["establishes_production_authority"] is False
        assert RES["informs"] == "visual material treatment only"


class TestProductionBoundary:

    def test_all_gates_blocked(self):
        p = REV["production_boundary"]
        assert p["PRODUCTION_MATERIAL_SPECIFICATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["PRODUCTION_GEOMETRY"] == "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["PRODUCTION_COLOR_SEPARATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["ILLUSTRATOR_EXECUTION_VERIFICATION"] == \
            "REQUIRED_BEFORE_PRODUCTION_AUTHORITY"
        assert ST["PRODUCTION_MATERIAL_SPECIFICATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"

    def test_render_is_visualization_only(self):
        for c in ("VQ3_RENDER_IS_VISUALIZATION_ONLY",
                  "VQ2_AI_REMAINS_ARTWORK_SOURCE_OF_TRUTH",
                  "VQ3_NOT_PRODUCTION_MATERIAL_AUTHORITY"):
            assert c in REV["codes"], c

    def test_nothing_material_is_claimed(self):
        for n in ("exact glass formulation", "exact Pantone",
                  "tooling readiness", "supplier compatibility",
                  "production feasibility"):
            assert n in REV["not_claimed"], n
        blob = json.dumps({k: v for k, v in REV.items()
                           if k != "inspections"})
        for f in ("MANUFACTURABLE", "PRODUCTION_READY"):
            assert f not in blob


class TestScopeBoundaries:

    def test_packaging_not_started_and_no_supplier_request(self):
        assert REV["packaging_started"] is False
        assert REV["supplier_requests_sent"] == 0
        assert ST["PACKAGING"] == "NOT_STARTED"

    def test_vq3_started_state(self):
        """This slice started VQ-3; it has since advanced to owner selection,
        so the durable check is that VQ-3 is underway, not a pinned string."""
        assert ST["VQ_3"] != "NOT_STARTED"
        assert REV["state"] == "MATERIAL_TRIALS_IN_PROGRESS"


class TestPackage:

    def test_all_twenty_one_sections(self):
        titles = REV["section_titles"]
        for i in range(1, 22):
            assert any(t.startswith(f"{i}.") for t in titles), i

    def test_files_exist(self):
        for n, floor in (("vq3_material_review.pdf", 100_000),
                         ("vq3_material_review.png", 5_000),
                         ("vq3_material_review.json", 1_000),
                         ("vq3_material_research.json", 500)):
            assert os.path.getsize(os.path.join(W3, n)) > floor, n

    def test_renders_are_large(self):
        from PIL import Image
        for k in KEYS:
            im = Image.open(os.path.join(settings.BASE_DIR,
                                         REV["candidates"][k]["path"]))
            assert im.height >= 2000, k


@pytest.mark.django_db
class TestBoardServesVQ3:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq3tester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_vq3(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]["vq3"]
        # the board shows the latest VQ-3 state; the build-time state of this
        # slice stays visible beside it
        assert v["build_time_state"] == "MATERIAL_TRIALS_IN_PROGRESS"
        assert v["candidates"] == 3
        assert v["image_generation_calls"] == 0
        assert v["build_time_human_accepted"] is False

    def test_artifacts_serve(self, client_in):
        for n in ("vq3-m1", "vq3-m2", "vq3-m3", "vq3-review-pdf",
                  "vq3-review-json", "vq3-research"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
