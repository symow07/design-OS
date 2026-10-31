"""VQ-2 final typography inspection — both inspectors ran, once each.

What these tests guard is not the verdict (a machine verdict is not authority)
but the conditions under which it may be believed: that the evidence was
frozen, that the two calls were genuinely independent, that no prohibited
correction was recommended, that divergence was recorded rather than resolved,
and that a passing machine result is never dressed up as human acceptance.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

D = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
T = os.path.join(D, "typeface")
REV = json.load(open(os.path.join(T, "vq2_imbue_lf1_r1_review.json")))
CONS = json.load(open(os.path.join(
    D, "vq2_lf1_typography_inspection_consistency.json")))
INS = json.load(open(os.path.join(D, "vq2_lf1_typography_inspection.json")))
PRB = json.load(open(os.path.join(D, "vq2_anthropic_billing_probe_2.json")))
PRE = json.load(open(os.path.join(D, "vq2_lf1_inspection_preflight.json")))
ST = json.load(open(os.path.join(D, "vq2_state.json")))

A_REQ = "req_011CdW1hCQznBoLM2TpT4VST"
B_REQ = "req_011CdW1kNamXSPhnxt7QAM6a"
PROBE_REQ = "req_011CdW1NuzXKyS2pLAyLJf7p"


class TestKeySwapAndProbe:

    def test_fingerprint_changed_from_the_old_key(self):
        s = PRB["secret_source"]
        assert PRB["old_key_fingerprint_sha256_12"] == "7f581a372e1e"
        assert s["key_fingerprint_sha256_12"] != "7f581a372e1e"
        assert len(s["key_fingerprint_sha256_12"]) == 12

    def test_probe_passed_and_is_not_an_inspector_call(self):
        assert PRB["outcome"] == "PROBE_SUCCEEDED"
        assert PRB["http_status"] == 200
        assert PRB["request_id"] == PROBE_REQ
        assert set(PRB["codes"]) == {"VQ2_ANTHROPIC_BILLING_PROBE_PASSED",
                                     "VQ2_ANTHROPIC_FUNDED_KEY_CONFIRMED"}
        assert PRB["is_inspector_call"] is False
        assert PRB["is_inspector_retry"] is False

    def test_probe_stayed_minimal(self):
        assert PRB["images_sent"] == 0
        assert PRB["project_records_sent"] == 0
        assert PRB["typography_evidence_sent"] == 0
        assert PRB["output_tokens"] <= 8


class TestSecretNeverExposed:

    def test_no_key_material_in_any_committed_vq2_record(self):
        for root, _dirs, files in os.walk(D):
            for n in files:
                if not n.endswith(".json"):
                    continue
                with open(os.path.join(root, n)) as f:
                    assert "sk-ant-" not in f.read(), n

    def test_live_key_absent_from_the_review_package(self):
        live = settings.ANTHROPIC_API_KEY or ""
        assert live
        assert live not in json.dumps(REV)
        assert live not in json.dumps(CONS)

    def test_package_declares_no_secret_or_environment_content(self):
        assert REV["billing_probe"]["api_key_included"] is False
        assert REV["billing_probe"]["environment_contents_included"] is False
        assert REV["font_binary_included"] is False


class TestFrozenPreconditions:

    def test_all_preconditions_passed_before_the_calls(self):
        assert PRE["all_pass"] is True
        assert PRE["checks"]["lf1_r1_hash"]["actual"] == "fcd8003994d52028"
        assert PRE["checks"]["prompt_a_hash"]["actual"] == "589d9d142150bb6f"
        assert PRE["checks"]["prompt_b_hash"]["actual"] == "f7cd3805fd161d81"

    def test_lf1_r1_is_still_byte_identical_now(self):
        p = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")
        assert hashlib.sha256(
            open(p, "rb").read()).hexdigest()[:16] == "fcd8003994d52028"

    def test_all_five_frozen_images_matched(self):
        imgs = PRE["checks"]["five_input_images"]
        assert len(imgs) == 5
        assert all(v["pass"] for v in imgs.values())
        assert {v["actual"] for v in imgs.values()} == {
            "a381ead75b5afb4a", "d5fc167c225204ec", "0a97c0d1bc2d7f9f",
            "3deba66ce7288e01", "c321c1bea4c69e27"}

    def test_frozen_prompt_hash_defect_disclosed_not_hidden(self):
        """The frozen hashes pin the inspector identity, not the prompt body.

        That is weaker than the name implies, so it is disclosed and true body
        hashes are recorded — the check is not quietly redefined to pass.
        """
        assert "IDENTITY_NOT_BODY" in PRE["frozen_prompt_hash_defect"]
        assert PRE["checks"]["prompt_a_hash"]["hashed_input"] == \
            "inspector identity string"
        assert len(PRE["prompt_body_hashes"]["A"]) == 16
        assert PRE["prompt_body_hashes"]["A"] != \
            PRE["prompt_body_hashes"]["B"]

    def test_nothing_was_rebuilt(self):
        for k in ("no_crop_rebuilt", "no_prompt_rewritten",
                  "no_evidence_regenerated", "no_geometry_changed",
                  "no_axes_or_tracking_changed"):
            assert PRE[k] is True


class TestBothInspectorsRanOnceIndependently:

    def test_each_ran_exactly_once(self):
        assert REV["inspections_performed"] == 2
        assert REV["provider_calls"] == {"billing_probe": 1, "inspector_a": 1,
                                         "inspector_b": 1, "total": 3}
        assert INS["inspections"]["A"]["status"] == "COMPLETED"
        assert INS["inspections"]["B"]["status"] == "COMPLETED"

    def test_distinct_requests_identities_and_outputs(self):
        a, b = REV["inspector_a"], REV["inspector_b"]
        assert a["request_id"] == A_REQ
        assert b["request_id"] == B_REQ
        assert a["request_id"] != b["request_id"]
        assert a["identity"] != b["identity"]
        assert a["prompt_hash"] != b["prompt_hash"]
        assert a["raw_output_sha256_16"] != b["raw_output_sha256_16"]

    def test_raw_outputs_persisted_and_hash_correctly(self):
        for side in ("inspector_a", "inspector_b"):
            raw = REV[side]["raw_output"]
            assert raw
            assert hashlib.sha256(raw.encode()).hexdigest()[:16] == \
                REV[side]["raw_output_sha256_16"]

    def test_b_did_not_receive_a_output(self):
        ev = REV["independence_verification"]
        assert ev["a_output_not_in_b_payload"] is True
        assert ev["finding_texts_differ"] is True
        assert CONS["checks"]["inspection_independence_proven"] is True
        # A's verdict string must not appear inside B's raw output
        assert REV["inspector_a"]["raw_output"] not in \
            REV["inspector_b"]["raw_output"]


class TestConsistencyValidation:

    def test_every_mandated_check_ran_and_passed(self):
        for k in ("each_verdict_agrees_with_its_findings",
                  "no_passing_verdict_contains_an_actionable_defect",
                  "neither_recommends_prohibited_scaling_or_glyph_modification",
                  "material_realization_did_not_drive_typography_judgment",
                  "deterministic_measurements_represented_accurately",
                  "rose_width_classifications_explicit",
                  "inspection_independence_proven"):
            assert CONS["checks"][k] is True, k
        assert CONS["all_checks_pass"] is True

    def test_no_prohibited_correction_was_recommended(self):
        for n in "AB":
            scan = CONS["per_inspector"][n]["prohibited_correction_scan"]
            assert scan["recommends_prohibited_correction"] is False
            assert scan["prohibited_matches"] == []

    def test_divergence_is_recorded_not_resolved(self):
        """One divergence exists and it is preserved, not silently reconciled."""
        assert CONS["divergence_count"] >= 1
        d = CONS["divergences"][0]
        assert d["field"] == "description_of_the_approved_BBROSE_logo"
        assert d["severity"] == "OBSERVATIONAL_NOT_A_TYPOGRAPHY_DEFECT"
        assert "A" in d and "B" in d

    def test_no_verdict_or_rose_disagreement(self):
        fields = [d["field"] for d in CONS["divergences"]]
        assert "verdict" not in fields
        assert "rose_width_classification" not in fields


class TestRoseWidthAndResult:

    def test_both_classified_nonactionable(self):
        assert REV["rose_width"]["A"] == "NONACTIONABLE"
        assert REV["rose_width"]["B"] == "NONACTIONABLE"
        assert REV["rose_width"]["code"] == (
            "VQ2_ROSE_NATIVE_WIDTH_DIFFERENCE_NONACTIONABLE_"
            "PENDING_OWNER_APPROVAL")

    def test_rose_was_not_touched_in_any_way(self):
        r = REV["rose_width"]
        for k in ("word_modified", "scaled", "tracked", "distorted",
                  "redesigned"):
            assert r[k] is False
        assert r["rose_px"] == 128.85
        assert r["reference_px"] == 134

    def test_result_classification(self):
        assert REV["result_classification"] == \
            "VQ2_PRODUCT_NAME_LETTERING_VALIDATED_PENDING_OWNER_APPROVAL"
        assert REV["inspector_a_result"]["actionable_defect_count"] == 0
        assert REV["inspector_b_result"]["actionable_defect_count"] == 0


class TestPassingMachineResultIsNotAcceptance:
    """The single most important guard in this file."""

    def test_human_approval_is_not_granted(self):
        assert REV["human_approval_state"] == "NOT_GRANTED"
        assert REV["owner_decision_required"] is True
        assert ST["human_visual_approval"] == "PENDING"

    def test_never_claims_gate2_production_or_manufacturability(self):
        assert REV["is_gate_2"] is False
        assert REV["is_production_authority"] is False
        assert REV["is_manufacturable_claim"] is False
        blob = json.dumps(REV)
        for forbidden in ("HUMAN_ACCEPTED", "MANUFACTURABLE",
                          "PRODUCTION_READY"):
            assert forbidden not in blob

    def test_nothing_fabricated(self):
        assert REV["fabricated_scorecards"] is False
        assert REV["is_final_review"] is True
        assert REV["is_pending_package"] is False


class TestBoundariesHeld:

    def test_no_geometry_axes_or_tracking_change(self):
        for k in ("lf1_r1_geometry_changed", "axes_changed",
                  "tracking_changed"):
            assert REV[k] is False
        assert REV["lf1_r1_hash"] == "fcd8003994d52028"

    def test_nothing_else_was_started_or_modified(self):
        for k in ("lf2_created", "vq2_a2_created", "m3_modified",
                  "packaging_modified", "vq3_started"):
            assert REV[k] is False
        assert REV["supplier_requests_sent"] == 0
        assert REV["image_generation_calls"] == 0

    def test_no_lf2_or_a2_directory(self):
        assert not os.path.exists(os.path.join(D, "lf2"))
        assert not os.path.exists(os.path.join(D, "a2"))


class TestPackageArtefacts:

    def test_all_three_files_exist_and_are_non_trivial(self):
        pdf = os.path.join(T, "vq2_imbue_lf1_r1_review.pdf")
        png = os.path.join(T, "vq2_imbue_lf1_r1_review.png")
        js = os.path.join(T, "vq2_imbue_lf1_r1_review.json")
        assert os.path.getsize(pdf) > 50_000
        assert os.path.getsize(png) > 5_000
        assert os.path.exists(js)

    def test_pending_package_is_superseded_not_deleted(self):
        assert REV["supersedes"] == "vq2_imbue_lf1_r1_review_pending/1.0"
        assert os.path.exists(
            os.path.join(T, "vq2_imbue_lf1_r1_review_pending.json"))


@pytest.mark.django_db
class TestBoardServesTheFinalReview:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2finaltester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_reports_the_completed_review(self, client_in):
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]
        fr = v["final_review"]
        assert fr["result_classification"] == \
            "VQ2_PRODUCT_NAME_LETTERING_VALIDATED_PENDING_OWNER_APPROVAL"
        assert fr["inspector_a"]["request_id"] == A_REQ
        assert fr["inspector_b"]["request_id"] == B_REQ
        assert fr["consistency_all_pass"] is True
        assert fr["human_approval_state"] == "NOT_GRANTED"
        assert fr["is_gate_2"] is False
        assert "COMPLETE" in v["typography_inspection"]

    def test_page_shows_approval_pending_not_approved(self, client_in):
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "AWAITING YOUR VISUAL APPROVAL" in html
        assert "This is not acceptance" in html
        assert "sk-ant-" not in html

    def test_package_endpoints_serve(self, client_in):
        for name in ("vq2-review-pdf", "vq2-review-png", "vq2-review-json",
                     "vq2-consistency", "vq2-preflight", "vq2-inspection",
                     "vq2-billing-probe-2"):
            assert client_in.get(
                f"/api/visual-quality/vq1/{name}/").status_code == 200, name
