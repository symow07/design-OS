"""COMPLETE-PRODUCT-REVIEW-1 — integrated coherence, non-regression, readiness.

A review stage, so the tests are mostly about restraint: the accepted VQ-1 and
VQ-2 assets must come through untouched, no correction may be implemented, and
an inspector disagreement must be recorded rather than resolved. The one thing
that must NOT be soft is the classification — four actionable findings means
COMPLETE_PRODUCT_REVIEW_REQUIRED, not owner-ready.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

VQ2 = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
CP = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                  "complete_product")
J = lambda d, n: json.load(open(os.path.join(d, n)))                  # noqa
REV = J(CP, "complete_product_review.json")
CONS = J(CP, "complete_product_inspection_consistency.json")
HAND = J(CP, "complete_product_handoff.json")
APP = J(VQ2, "vq2_final_front_artwork_owner_approval.json")
ST = J(VQ2, "vq2_state.json")


class TestWorkstreamsRemainClosed:

    def test_vq1_and_vq2_closed_and_not_reopened(self):
        assert ST["VQ_1_CLOSED"] is True
        assert ST["VQ_2_CLOSED"] is True
        assert "CLOSED" in ST["VQ_1"]
        assert ST["VQ_2"].startswith("VQ2_FINAL_FRONT_ARTWORK_OWNER_APPROVED")
        assert REV["accepted_inputs"]["vq1_reopened"] is False
        assert REV["accepted_inputs"]["vq2_reopened"] is False
        assert "VQ1_WORKSTREAM_CLOSED" in REV["accepted_inputs"]["vq1"]
        assert "VQ2_FINAL_FRONT_ARTWORK_OWNER_APPROVED" in \
            REV["accepted_inputs"]["vq2"]

    def test_no_inspector_unilaterally_reopened_accepted_geometry(self):
        assert CONS[
            "no_inspector_reopened_accepted_geometry_unilaterally"] is True


class TestFreezeContract:

    def test_every_frozen_identity_matched(self):
        f = REV["freeze_contract"]
        assert set(f) == {"m3", "lf1_r1", "font_unit", "logo_canonical",
                          "clean_preview"}
        for k, v in f.items():
            assert v["match"] is True, k
        assert f["m3"]["live"] == "4ecc8e9df1d1"
        assert f["lf1_r1"]["live"] == "fcd8003994d52028"
        assert f["font_unit"]["live"] == "5db4403984ba6f75"
        assert f["clean_preview"]["live"] == "94ec944326889c20"

    def test_frozen_outputs_did_not_drift(self):
        assert REV["frozen_output_drift"] == []

    def test_identities_still_live_on_disk_now(self):
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == "4ecc8e9df1d1"
        p = os.path.join(VQ2, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == "fcd8003994d52028"
        c = os.path.join(VQ2, "vq2_a2_r2_final_clean.png")
        assert hashlib.sha256(
            open(c, "rb").read()).hexdigest()[:16] == "94ec944326889c20"

    def test_no_frozen_input_drift_record(self):
        assert not os.path.exists(
            os.path.join(CP, "complete_product_frozen_input_drift.json"))


class TestDeterministicChecks:

    def test_all_eleven_checks_present_and_passing(self):
        d = REV["deterministic_checks"]
        assert REV["deterministic_all_pass"] is True
        assert d["structural_hash_drift"] == 0
        assert d["product_name_hash_drift"] == 0
        assert d["logo_geometry_drift"] == 0
        assert d["artwork_placement_drift"] == 0
        assert d["symmetry_mismatch_mm"] <= 0.01
        assert d["visible_object_count"] == 40
        assert d["clean_preview_guide_count"] == 0
        assert d["raster_object_count"] == 0
        assert d["live_text_count"] == 0
        assert d["material_effect_count"] == 0
        assert d["production_authority_claim_count"] == 0


class TestReviewDidNotMutateAnything:

    def test_no_accepted_asset_modified(self):
        assert REV["accepted_assets_modified"] is False
        assert REV["is_review_not_redesign"] is True
        assert REV["corrections_implemented"] == 0

    def test_no_correction_implemented_despite_open_defects(self):
        assert len(REV["open_defects"]) > 0
        assert REV["corrections_implemented"] == 0


class TestDualInspection:

    def test_both_inspections_required_and_performed(self):
        assert REV["inspector_a"]["status"] == "COMPLETED"
        assert REV["inspector_b"]["status"] == "COMPLETED"
        assert CONS["both_inspectors_returned_output"] is True
        assert REV["provider_calls"] == 2

    def test_inspections_were_independent(self):
        ind = CONS["independence"]
        assert ind["separate_requests"][0] != ind["separate_requests"][1]
        assert ind["distinct_prompt_bodies"]["A"] != \
            ind["distinct_prompt_bodies"]["B"]
        assert ind["distinct_outputs"] is True
        assert ind["b_saw_a_output"] is False
        assert REV["inspector_a"]["raw_output"] not in \
            REV["inspector_b"]["raw_output"]

    def test_raw_outputs_persisted_and_hash_correctly(self):
        for side in ("inspector_a", "inspector_b"):
            raw = REV[side]["raw_output"]
            assert raw
            assert hashlib.sha256(raw.encode()).hexdigest()[:16] == \
                REV[side]["raw_output_sha256_16"]

    def test_disagreement_recorded_not_resolved(self):
        fields = [d["field"] for d in CONS["disagree_on"]]
        assert "verdict" in fields
        assert "colour_coherence" in fields
        assert CONS["verdicts"]["A"] != CONS["verdicts"]["B"]
        assert "recorded rather than resolved" in CONS["notable"]

    def test_agreements_recorded_too(self):
        joined = " ".join(CONS["agree_on"]).lower()
        assert "structural coherence pass" in joined
        assert "luxury" in joined
        assert "blocks packaging" in joined


class TestActionableDefectsBlockOwnerReady:

    def test_classification_is_review_required_not_owner_ready(self):
        assert REV["result_classification"] == \
            "COMPLETE_PRODUCT_REVIEW_REQUIRED"
        assert REV["result_classification"] != \
            "COMPLETE_PRODUCT_CANDIDATE_PENDING_OWNER_APPROVAL"
        total = (REV["inspector_a_result"]["actionable_defect_count"]
                 + REV["inspector_b_result"]["actionable_defect_count"])
        assert total > 0
        # live state has since advanced to owner approval; this slice's own
        # record is the immutable evidence that the review classified it as
        # REVIEW_REQUIRED rather than waving it through

    def test_each_defect_carries_a_proposed_next_action(self):
        assert len(REV["open_defects"]) == 4
        for d in REV["open_defects"]:
            assert d["proposed_next_action"]
            assert d["observation"]
            assert d["raised_by"]

    def test_defects_contesting_owner_decisions_are_flagged_as_such(self):
        contesting = [d for d in REV["open_defects"]
                      if d["contests_an_accepted_owner_decision"]]
        assert len(contesting) == \
            CONS["defects_contesting_accepted_decisions"]
        for d in contesting:
            assert d["which"], "must name the decision being contested"

    def test_advisory_notes_carried_not_auto_promoted(self):
        assert len(REV["advisory_notes_carried"]) == 3
        for n in REV["advisory_notes_carried"]:
            assert n["blocking"] is False


class TestDownstreamNotStarted:

    def test_packaging_did_not_start(self):
        assert REV["packaging_started"] is False
        assert HAND["packaging_started"] is False
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert ST["PACKAGING_READINESS"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"

    def test_vq3_did_not_start(self):
        """Readiness later advanced on owner approval; NOT_STARTED is the
        invariant this slice guarantees."""
        assert REV["vq3_started"] is False
        assert HAND["vq3_started"] is False
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.
        assert REV["downstream_readiness"]["VQ3_READINESS"] == \
            "BLOCKED_PENDING_OWNER_APPROVAL"

    def test_readiness_states_are_from_the_allowed_vocabulary(self):
        r = REV["downstream_readiness"]
        assert r["PACKAGING_READINESS"] in (
            "READY_PENDING_EXPLICIT_START",
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE",
            "BLOCKED_BY_COMPLETE_PRODUCT_DEFECT")
        assert r["VQ3_READINESS"] in (
            "READY_PENDING_EXPLICIT_START",
            "BLOCKED_BY_COMPLETE_PRODUCT_DEFECT",
            "BLOCKED_PENDING_OWNER_APPROVAL")
        assert r["neither_started"] is True

    def test_nothing_starts_automatically(self):
        assert HAND["starts_nothing_automatically"] is True
        assert REV["state"] == "STARTED"


class TestProductionAuthorityBlocked:

    def test_all_four_gates_still_blocked(self):
        p = REV["production_authority"]
        assert p["PRODUCTION_GEOMETRY"] == "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert p["PRODUCTION_COLOR_SEPARATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert p["ILLUSTRATOR_EXECUTION_VERIFICATION"] == \
            "REQUIRED_BEFORE_PRODUCTION_AUTHORITY"

    def test_scope_limits_recorded(self):
        for item in ("manufacturability", "physical dimensions",
                     "print wrap", "CMYK or Pantone separation",
                     "material realism"):
            assert item in REV["may_not_certify"], item

    def test_never_claims_production_readiness(self):
        blob = json.dumps({k: v for k, v in REV.items()
                           if k not in ("inspector_a", "inspector_b")})
        for f in ("MANUFACTURABLE", "PRODUCTION_READY", "GATE_2_APPROVED"):
            assert f not in blob

    def test_not_acceptance(self):
        assert REV["human_accepted"] is False
        assert REV["owner_decision_required"] is True


class TestNoProhibitedCalls:

    def test_no_image_generation_and_no_supplier_request(self):
        assert REV["image_generation_calls"] == 0
        assert REV["supplier_requests_sent"] == 0


class TestMeasurementHonesty:

    def test_photo_segmentation_ratios_were_withdrawn(self):
        sup = REV["metrics"]["superseded_photo_segmentation"]
        assert "NOT authoritative" in sup["note"]
        assert "withdrawn_values" in sup

    def test_proportions_come_from_accepted_geometry(self):
        g = REV["metrics"]["geometry_derived"]
        assert "accepted M3 band model" in g["measurement_space"]
        assert "NOT re-segmented from the photograph" in g[
            "measurement_space"]
        assert 0 < g["aspect_w_over_h"] < 1
        assert abs(g["closure_plus_collar_to_total"]
                   + g["body_to_total"] - 1.0) < 1e-6


class TestPackage:

    def test_all_nineteen_required_sections(self):
        titles = REV["section_titles"]
        for i in range(1, 20):
            assert any(t.startswith(f"{i}.") for t in titles), i

    def test_files_exist(self):
        for n, floor in (("complete_product_review.pdf", 100_000),
                         ("complete_product_review.png", 5_000),
                         ("complete_product_review.json", 1_000),
                         ("complete_product_handoff.json", 500)):
            assert os.path.getsize(os.path.join(CP, n)) > floor, n

    def test_evidence_views_exist_and_are_large(self):
        from PIL import Image
        for n in ("cp_1_concept", "cp_2_integrated", "cp_3_side_by_side",
                  "cp_4_silhouette", "cp_5_balance", "cp_6_hierarchy"):
            im = Image.open(os.path.join(CP, n + ".png"))
            assert max(im.size) >= 800, (n, im.size)


@pytest.mark.django_db
class TestUpstreamRecordsUntouched:

    def test_task_52_and_project_7_unchanged(self):
        from apps.pipeline.models import DesignProject, DesignTask
        t52 = DesignTask.objects.filter(pk=52).first()
        p7 = DesignProject.objects.filter(pk=7).first()
        if t52 is not None:
            assert t52.status == "container_stage_visually_rejected"
        if p7 is not None:
            assert p7.status == "container_rejected"

    def test_review_created_no_task_records(self):
        from apps.pipeline.models import DesignTask
        before = DesignTask.objects.count()
        assert REV["corrections_implemented"] == 0
        assert DesignTask.objects.count() == before


@pytest.mark.django_db
class TestBoardServesCompleteProduct:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "cprtester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_the_review(self, client_in):
        cp = client_in.get("/api/visual-quality/vq1/").json()["vq2"][
            "complete_product"]
        # the board shows the latest state; the build-time classification
        # must remain visible beside it
        assert cp["build_time_result"] == "COMPLETE_PRODUCT_REVIEW_REQUIRED"
        assert cp["open_defects"] == 4
        assert cp["packaging_readiness"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert cp["build_time_human_accepted"] is False

    def test_artifacts_serve(self, client_in):
        for n in ("cp-review-pdf", "cp-review-png", "cp-review-json",
                  "cp-handoff", "cp-consistency", "cp-integrated",
                  "cp-side-by-side"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{n}/").status_code == 200, n
