"""Complete Product — owner approval, adjudication and closeout.

The owner resolved a genuine inspector disagreement. The discipline that
matters here is that resolving it did NOT edit the model output: Inspector B's
four findings survive verbatim, each with a ruling recorded beside it. And
approval closes a review — it does not unblock production or start a stage.
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
OA = J(CP, "complete_product_owner_approval.json")
REV = J(CP, "complete_product_review.json")
HAND = J(CP, "complete_product_handoff.json")
ST = J(VQ2, "vq2_state.json")


class TestOwnerApproval:

    def test_decision_and_codes(self):
        assert OA["decided_by"] == "PROJECT_OWNER"
        assert OA["decision"] == "APPROVED"
        for c in ("COMPLETE_PRODUCT_OWNER_APPROVED",
                  "COMPLETE_PRODUCT_CANDIDATE_ACCEPTED",
                  "COMPLETE_PRODUCT_REVIEW_CLOSED",
                  "COMPLETE_PRODUCT_INSPECTOR_DISAGREEMENT_RESOLVED_BY_OWNER",
                  "COMPLETE_PRODUCT_INSPECTOR_B_FINDINGS_NONBLOCKING_ADVISORY"):
            assert c in OA["codes"], c

    def test_state_closed(self):
        assert ST["COMPLETE_PRODUCT_REVIEW"] == "OWNER_ACCEPTED_AND_CLOSED"
        assert ST["COMPLETE_PRODUCT_RESULT"] == \
            "COMPLETE_PRODUCT_OWNER_APPROVED"
        assert HAND["complete_product_review"] == "OWNER_ACCEPTED_AND_CLOSED"

    def test_nine_pass_criteria_recorded(self):
        assert len(OA["passes"]) == 9
        for need in ("structural coherence", "artwork coherence", "symmetry",
                     "concept-front fidelity"):
            assert need in OA["passes"], need

    def test_closure_is_not_production_authority(self):
        for phrase in ("production authority", "Gate-2", "manufacturability"):
            assert phrase in OA["closure_is_not"]


class TestInspectorOutputPreserved:
    """Adjudication is added BESIDE the model output, never over it."""

    def test_model_output_not_rewritten(self):
        assert OA["inspection_results_preserved"][
            "model_output_rewritten"] is False
        assert OA["inspection_results_preserved"][
            "adjudication_added_beside_not_over"] is True

    def test_inspector_b_verdict_and_count_unchanged(self):
        b = OA["inspection_results_preserved"]["inspector_b"]
        assert b["verdict"] == "COMPLETE_PRODUCT_REVIEW_REQUIRED"
        assert b["actionable"] == 4
        assert b["verdict"] == REV["inspector_b_result"]["verdict"]

    def test_raw_outputs_still_hash_to_their_recorded_values(self):
        for side in ("inspector_a", "inspector_b"):
            raw = REV[side]["raw_output"]
            assert hashlib.sha256(raw.encode()).hexdigest()[:16] == \
                REV[side]["raw_output_sha256_16"]
        pres = OA["inspection_results_preserved"]
        assert pres["inspector_a"]["raw_output_sha256_16"] == \
            REV["inspector_a"]["raw_output_sha256_16"]
        assert pres["inspector_b"]["raw_output_sha256_16"] == \
            REV["inspector_b"]["raw_output_sha256_16"]

    def test_build_time_review_record_untouched(self):
        assert REV["result_classification"] == \
            "COMPLETE_PRODUCT_REVIEW_REQUIRED"
        assert REV["human_accepted"] is False


class TestAdjudication:

    def test_every_actionable_finding_was_ruled_on(self):
        assert OA["adjudications_count"] == 4
        assert OA["all_inspector_b_findings_adjudicated"] is True
        for a in OA["owner_adjudication"]:
            assert a["inspector_observation_preserved_verbatim"]
            assert a["owner"]["ruling"]
            assert a["owner"]["reason"]
            assert a["owner"]["artwork_changed"] is False

    def test_observations_match_the_review_record_verbatim(self):
        for a in OA["owner_adjudication"]:
            src = REV["open_defects"][a["finding_index"]]
            assert a["inspector_observation_preserved_verbatim"] == \
                src["observation"]
            assert a["area"] == src["area"]

    def test_collar_colour_deferred_to_vq3(self):
        collar = [a for a in OA["owner_adjudication"]
                  if "VQ3_COLLAR_BODY_MATERIAL_INTEGRATION_REQUIRED"
                  in a["owner"]["codes"]]
        assert len(collar) == 2      # the observation and its system restatement
        for a in collar:
            assert a["owner"]["ruling"] == "NONBLOCKING_FOR_COMPLETE_PRODUCT"
            assert a["owner"]["disposition"] == \
                "DEFERRED_TO_VQ3_MATERIAL_INTEGRATION"
            assert "COMPLETE_PRODUCT_COLLAR_COLOUR_SPLIT_ACCEPTED_FOR_FLAT" \
                "_CONCEPT" in a["owner"]["codes"]

    def test_logo_scale_reopening_rejected(self):
        lg = next(a for a in OA["owner_adjudication"]
                  if "COMPLETE_PRODUCT_LOGO_SCALE_OWNER_CONFIRMED"
                  in a["owner"]["codes"])
        assert lg["owner"]["ruling"] == "APPROVED_AND_FROZEN"
        assert lg["owner"]["disposition"] == "REOPENING_REJECTED"
        assert "COMPLETE_PRODUCT_LOGO_SCALE_REOPENING_REJECTED" in \
            lg["owner"]["codes"]

    def test_left_datum_confirmed(self):
        ld = next(a for a in OA["owner_adjudication"]
                  if "COMPLETE_PRODUCT_ARTWORK_LEFT_DATUM_OWNER_CONFIRMED"
                  in a["owner"]["codes"])
        assert ld["owner"]["ruling"] == "APPROVED_AND_FROZEN"


class TestFrozen:

    def test_nothing_was_modified_or_rerendered(self):
        assert OA["artwork_modified_by_this_closeout"] is False
        assert OA["rerendered"] is False
        assert HAND["artwork_rerendered"] is False

    def test_frozen_identities_still_live(self):
        f = OA["frozen"]
        assert f["m3"] == "4ecc8e9df1d1"
        assert f["lf1_r1"] == "fcd8003994d52028"
        assert f["font_unit_contour_hash"] == "5db4403984ba6f75"
        assert f["approved_logo"] == "a2b2a82969389ac2"
        assert f["clean_preview"] == "94ec944326889c20"
        m = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                         "vq1_master", "master_it3.png")
        assert hashlib.sha256(
            open(m, "rb").read()).hexdigest()[:12] == f["m3"]
        for rel, want in (("lf1_r1/vq2_rose_damascena_lf1_r1.ai",
                           f["lf1_r1"]),
                          ("brand/bbrose_logo_approved.ai",
                           f["approved_logo"]),
                          ("vq2_a2_r2_final_clean.png", f["clean_preview"])):
            p = os.path.join(VQ2, rel)
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:16] == want, rel

    def test_logo_scale_and_left_datum_frozen_at_accepted_values(self):
        f = OA["frozen"]
        assert f["logo_to_rose_ratio"] == 0.8133
        assert f["left_datum_px"] == 528
        assert f["logo_uniform_scale"] == 0.970431

    def test_flat_colours_and_symmetry_frozen(self):
        f = OA["frozen"]
        assert f["flat_colours"] == {"body": "#D9BDB5", "collar": "#705242",
                                     "closure": "#493034",
                                     "artwork_ink": "#502525"}
        assert all(v == 0.0 for v in f["symmetry_mirror_mm"].values())

    def test_all_vq2_frozen_outputs_still_match(self):
        for name, want in OA["frozen"]["vq2_frozen_outputs"].items():
            p = os.path.join(VQ2, name)
            assert hashlib.sha256(
                open(p, "rb").read()).hexdigest()[:16] == want, name

    def test_frozen_scope_covers_the_whole_product(self):
        for need in ("M3", "approved BBROSE logo", "logo scale", "Rose",
                     "Damascena", "flat colours", "final clean preview"):
            assert need in OA["frozen_scope"], need


class TestWorkstreamsClosed:

    def test_vq1_and_vq2_not_reopened(self):
        assert OA["vq1_reopened"] is False
        assert OA["vq2_reopened"] is False
        assert ST["VQ_1_CLOSED"] is True
        assert ST["VQ_2_CLOSED"] is True

    def test_no_second_candidate_created(self):
        assert OA["another_candidate_created"] is False
        assert OA["new_candidate_requires"] == \
            "new authoritative owner evidence"


class TestDownstream:

    def test_vq3_ready_but_not_started(self):
        assert ST["VQ3_READINESS"] == "READY_PENDING_EXPLICIT_START"
        # VQ-3 was later STARTED by explicit owner instruction. The
        # durable invariant is that THIS slice did not start it.
        assert OA["vq3_started"] is False
        assert HAND["vq3_started"] is False

    def test_packaging_still_blocked_and_not_started(self):
        assert ST["PACKAGING_READINESS"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert ST["PACKAGING"] == "NOT_STARTED"
        assert OA["packaging_started"] is False

    def test_production_authority_all_blocked(self):
        d = OA["downstream"]
        assert d["PRODUCTION_GEOMETRY"] == "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert d["PRODUCTION_FLAT_ARTWORK"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert d["PRODUCTION_COLOR_SEPARATION"] == \
            "BLOCKED_PENDING_SUPPLIER_EVIDENCE"
        assert d["ILLUSTRATOR_EXECUTION_VERIFICATION"] == \
            "REQUIRED_BEFORE_PRODUCTION_AUTHORITY"

    def test_nothing_starts_automatically(self):
        assert OA["starts_nothing_automatically"] is True

    def test_no_calls_and_no_supplier_request(self):
        assert OA["provider_calls"] == 0
        assert OA["image_generation_calls"] == 0
        assert OA["supplier_requests_sent"] == 0

    def test_never_claims_production_readiness(self):
        blob = json.dumps(OA)
        for f in ("MANUFACTURABLE", "PRODUCTION_READY", "GATE_2_APPROVED"):
            assert f not in blob


@pytest.mark.django_db
class TestBoardShowsCloseout:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "cproatester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_closeout(self, client_in):
        cp = client_in.get("/api/visual-quality/vq1/").json()["vq2"][
            "complete_product"]
        assert cp["state"] == "OWNER_ACCEPTED_AND_CLOSED"
        assert cp["owner_decision"] == "APPROVED"
        assert cp["inspector_disagreement"] == "RESOLVED_BY_OWNER"
        assert cp["adjudications"] == 4
        assert cp["collar_colour"] == "DEFERRED_TO_VQ3_MATERIAL_INTEGRATION"
        assert cp["vq3_readiness"] == "READY_PENDING_EXPLICIT_START"
        assert cp["packaging_readiness"] == \
            "BLOCKED_PENDING_WRAP_AND_SUPPLIER_EVIDENCE"
        assert cp["human_accepted"] is True
        # the build-time classification is still visible, unaltered
        assert cp["build_time_result"] == "COMPLETE_PRODUCT_REVIEW_REQUIRED"

    def test_approval_record_serves(self, client_in):
        assert client_in.get(
            "/api/visual-quality/vq1/cp-owner-approval/").status_code == 200
