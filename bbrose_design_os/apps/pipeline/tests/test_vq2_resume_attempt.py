"""VQ-2 LF1-R1 resume attempt 1 — the contract retry rule was honoured.

The resume contract permits one retry after credit is restored — a single
scalar, so the budget is global, not per inspector. Credit was not in fact
restored: Inspector A's retry returned the same billing error, so the rule
required preserving the new request id, keeping the blocker active and
stopping. These tests assert that is what happened — and, just as importantly,
that nothing was invented in its place, and that the owner can SEE it on the
board rather than only in a committed file.
"""
import hashlib
import json
import os

import pytest
from django.conf import settings

DOCS = os.path.join(settings.BASE_DIR, "docs", "visual_quality")
D = os.path.join(DOCS, "vq2")
BLK = json.load(open(os.path.join(D, "vq2_typography_provider_blocker.json")))
RES = json.load(open(os.path.join(
    D, "vq2_lf1_r1_inspection_resume_contract.json")))
ATT = json.load(open(os.path.join(D, "vq2_lf1_resume_attempt_1.json")))
ST = json.load(open(os.path.join(D, "vq2_state.json")))
LF1R1_AI = os.path.join(D, "lf1_r1", "vq2_rose_damascena_lf1_r1.ai")

FIRST = "req_011CdVuiNaWaRAponJhPTXpk"
SECOND = "req_011CdVwoXHG75nMC5iqDDVDT"


class TestPreconditionsWereVerifiedFirst:
    """Every precondition was checked BEFORE the provider was called."""

    def test_all_eight_preconditions_passed(self):
        p = ATT["preconditions"]
        assert p["all_preconditions"] == "PASS"
        assert p["matched"] is True
        assert p["five_input_hashes_matched"] is True
        assert p["prompts_matched"] is True
        assert p["input_quality_manifest"] == "PASS"

    def test_lf1_r1_still_byte_identical(self):
        """The artefact under inspection did not move while we waited."""
        live = hashlib.sha256(open(LF1R1_AI, "rb").read()).hexdigest()[:16]
        assert live == "fcd8003994d52028"
        assert ATT["preconditions"]["lf1_r1_hash"] == live

    def test_prompt_hashes_unchanged(self):
        p = ATT["preconditions"]
        assert p["prompt_a"] == "589d9d142150bb6f"
        assert p["prompt_b"] == "f7cd3805fd161d81"

    def test_blocker_is_therefore_unambiguously_external(self):
        assert ATT["outcome"] == "BLOCKED_SAME_BILLING_ERROR"
        assert BLK["credit_restored"] is False


class TestRetryRuleHonoured:
    """One retry was permitted, one was used, none remain."""

    def test_exactly_one_retry_permitted(self):
        assert RES["retry_rule"]["retries_permitted_after_credit_restored"] == 1

    def test_exactly_one_retry_consumed(self):
        assert BLK["retry_count"] == 1
        assert BLK["retries_remaining"] == 0
        assert BLK["retry_permitted_by_contract"] == 1

    def test_no_third_inspector_attempt(self):
        """Invariant, not a pinned count: the attempt list may grow with
        owner-authorized probes, but inspector attempts must stay at two."""
        inspector_attempts = [a for a in BLK["attempts"]
                              if a.get("inspector") in ("A", "B")]
        assert len(inspector_attempts) == 2
        assert BLK["retry_count"] == 1
        assert BLK["further_automatic_retry"] == "PROHIBITED_BY_CONTRACT"
        assert ATT["contract_compliance"]["further_retry"] == \
            "STOPPED_PER_CONTRACT"

    def test_both_request_ids_preserved_distinctly(self):
        """Neither inspector request id may ever be overwritten or reordered."""
        ids = [a["request_id"] for a in BLK["attempts"]]
        assert ids[:2] == [FIRST, SECOND]
        assert len(set(ids)) == len(ids)
        assert BLK["latest_request_id"] == ids[-1]

    def test_inspector_b_retry_untouched(self):
        """A failed before B was reached, so B's retry is still unspent."""
        assert BLK["inspector_b_never_attempted"] is True
        assert ATT["inspector_b"]["called"] is False
        assert ATT["contract_compliance"]["retry_used_by_A"] == 1
        assert ATT["contract_compliance"]["retry_used_by_B"] == 0

    def test_no_provider_substitution(self):
        assert BLK["provider_substituted"] is False
        assert "NOT_PERFORMED" in \
            ATT["contract_compliance"]["provider_substitution"]


class TestNothingFabricated:
    """No inspector output existed, so none may appear anywhere."""

    def test_no_model_output_and_nothing_billable(self):
        for a in BLK["attempts"]:
            assert a["model_output_received"] is False
        assert ATT["inspector_a"]["model_output_received"] is False

    def test_no_raw_outputs_persisted_by_the_failed_attempt(self):
        """Scoped to resume attempt 1. Inspections that ran LATER, under a
        separate owner authorization and a passing billing probe, are not a
        contradiction — this asserts the failed attempt invented nothing."""
        assert ATT["raw_outputs_persisted"] == 0
        assert ATT["inspector_a"]["model_output_received"] is False
        assert ATT["inspector_b"]["called"] is False

    def test_no_consistency_validation_or_final_package(self):
        assert ATT["consistency_validation_run"] is False
        assert ATT["final_package_generated"] is False

    def test_rose_width_remains_unadjudicated(self):
        assert ATT["rose_width_classification"] == \
            "UNADJUDICATED_PENDING_DUAL_TYPOGRAPHY_INSPECTION"


class TestStandingProhibitionsIntact:

    def test_no_evidence_rebuilt_and_no_geometry_touched(self):
        assert ATT["evidence_rebuilt"] is False
        assert ATT["lettering_geometry_changed"] is False
        assert ATT["axes_or_tracking_changed"] is False

    def test_no_lf2_and_no_vq2_a2(self):
        assert ATT["lf2_created"] is False
        assert ATT["vq2_a2_created"] is False
        assert not os.path.exists(os.path.join(D, "lf2"))
        assert not os.path.exists(os.path.join(D, "a2"))

    def test_state_still_blocked_and_records_the_attempt(self):
        assert ST["provider_retries_used"] == 1
        assert ST["resume_attempts"][0]["request_id"] == SECOND
        assert ST["resume_attempts"][0]["outcome"] == \
            "BLOCKED_SAME_BILLING_ERROR"

    def test_owner_action_is_the_only_way_forward(self):
        assert "Fund" in ATT["owner_action_required"]


class TestRetryBudgetScopeIsResolved:
    """The contract's budget is a scalar, so it is global — say so."""

    def test_retry_rule_has_no_per_inspector_map(self):
        rule = RES["retry_rule"]
        assert isinstance(rule["retries_permitted_after_credit_restored"], int)
        assert not any(k in rule for k in ("per_inspector", "inspector_a",
                                           "inspector_b"))

    def test_scope_recorded_as_global(self):
        assert BLK["retry_budget_scope"] == "GLOBAL_NOT_PER_INSPECTOR"
        assert ATT["contract_compliance"]["retry_budget_scope"] == \
            "GLOBAL_NOT_PER_INSPECTOR"

    def test_a_new_owner_instruction_reauthorizes(self):
        """retries_remaining: 0 must not read as 'never again'."""
        for rec in (BLK, ATT):
            assert "AUTOMATIC" in rec["retries_remaining_scope"]
            assert "owner instruction" in rec["retries_remaining_scope"]


class TestPendingSnapshotMarkedSuperseded:

    def test_hold_slice_snapshot_labelled(self):
        import os as _os
        p = json.load(open(_os.path.join(
            D, "typeface", "vq2_imbue_lf1_r1_review_pending.json")))
        pb = p["provider_blocker"]
        assert "POINT_IN_TIME_SNAPSHOT" in pb["snapshot_note"]
        assert pb["retry_count"] == 0          # history, deliberately stale
        assert BLK["retry_count"] == 1         # the live record
        assert pb["superseded_by"].endswith(
            "vq2_typography_provider_blocker.json")


@pytest.mark.django_db
class TestBoardServesTheHold:
    """The CORR-1 lesson: a committed file is not a human review boundary."""

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2boardtester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_still_reports_the_spent_retry_budget(self, client_in):
        """The hold has since been lifted, but its accounting must survive."""
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]
        assert v["started"] is True
        assert v["blocker"]["reason"] == "ANTHROPIC_API_CREDIT"
        assert v["blocker"]["retry_count"] == 1
        assert v["blocker"]["retries_remaining"] == 0
        assert v["blocker"]["latest_request_id"] == BLK["latest_request_id"]
        assert v["blocker"]["attempts"] == len(BLK["attempts"]) >= 2
        assert v["blocker"]["provider_substituted"] is False

    def test_next_action_no_longer_says_vq2_unstarted(self, client_in):
        """Originally this pinned "VQ-2 IS STARTED AND BLOCKED", which was true
        during the provider-credit hold. VQ-2 has since been owner-accepted and
        closed, so that string would now be a falsehood — the enduring point is
        that the headline never describes VQ-2 as unstarted or still blocked."""
        nxt = client_in.get("/api/visual-quality/vq1/").json()[
            "next_required_action"]
        assert "VQ-2 and VQ-3 are unblocked" not in nxt
        assert "VQ-2 IS STARTED AND BLOCKED" not in nxt
        assert "OWNER ACCEPTED AND CLOSED" in nxt

    def test_review_page_always_states_an_owner_action(self, client_in):
        """Whether blocked or awaiting approval, the board names the ask."""
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "Owner action:" in html
        assert "sk-ant-" not in html

    def test_vq2_records_are_fetchable(self, client_in):
        for name in ("vq2-provider-blocker", "vq2-resume-attempt-1",
                     "vq2-resume-contract", "vq2-certification",
                     "vq2-state"):
            r = client_in.get(f"/api/visual-quality/vq1/{name}/")
            assert r.status_code == 200, name

    def test_whitelist_still_rejects_arbitrary_paths(self, client_in):
        assert client_in.get(
            "/api/visual-quality/vq1/vq2-does-not-exist/").status_code == 404
