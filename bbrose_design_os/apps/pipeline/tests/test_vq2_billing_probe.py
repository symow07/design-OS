"""VQ-2 Stage-1 billing probe — failed on billing, so Stage 2 never ran.

The probe is deliberately NOT an inspection: text only, tiny output, no images,
no project records, no typography evidence. It failed with the same
credit-balance error, which under the mandate means classify, preserve the
request id, and stop before either inspector.

The load-bearing assertion in this file is the secret one: no test, record or
API response may ever contain the API key. Only an irreversible fingerprint.
"""
import json
import os

import pytest
from django.conf import settings

D = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")
PRB = json.load(open(os.path.join(D, "vq2_anthropic_billing_probe.json")))
BLK = json.load(open(os.path.join(D, "vq2_typography_provider_blocker.json")))
ST = json.load(open(os.path.join(D, "vq2_state.json")))
PROBE_REQ = "req_011CdVyjuaL48Mppm1xUT5aK"


class TestProbeWasAProbe:
    """Not an inspection, and minimal by construction."""

    def test_not_an_inspector_call(self):
        assert PRB["is_inspector_call"] is False
        assert "NEITHER" in PRB["inspector_a_or_b"]
        assert PRB["converted_into_typography_finding"] is False

    def test_carried_no_evidence(self):
        assert PRB["images_sent"] == 0
        assert PRB["project_records_sent"] == 0
        assert PRB["typography_evidence_sent"] == 0

    def test_used_the_same_auth_path_as_the_inspectors(self):
        assert PRB["secret_source"]["setting"] == "settings.ANTHROPIC_API_KEY"
        assert PRB["secret_source"]["loaded_from"].endswith(".env")


class TestSecretNeverExposed:
    """Fingerprint only — never the key, in any artefact the board can serve."""

    def test_record_holds_only_an_irreversible_fingerprint(self):
        src = PRB["secret_source"]
        assert len(src["key_fingerprint_sha256_12"]) == 12
        assert src["key_never_printed_or_committed"] is True
        assert "key" not in src or not isinstance(src.get("key"), str)

    def test_no_key_material_anywhere_in_the_committed_records(self):
        """A live key starts sk-ant-; no committed VQ-2 record may contain one."""
        for name in os.listdir(D):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(D, name)) as f:
                assert "sk-ant-" not in f.read(), name

    def test_settings_key_is_not_echoed_into_the_record(self):
        live = settings.ANTHROPIC_API_KEY or ""
        blob = json.dumps(PRB)
        assert not live or live not in blob


class TestBillingOutcomeClassified:

    def test_classified_as_balance_not_confirmed(self):
        assert PRB["outcome"] == "PROBE_FAILED"
        assert PRB["error_class"] == "BILLING"
        assert PRB["code"] == \
            "VQ2_ANTHROPIC_FUNDED_KEY_OR_BALANCE_NOT_CONFIRMED"
        assert PRB["code"] in BLK["codes"]

    def test_billing_not_confused_with_authentication(self):
        """The key authenticates; the organization has no balance."""
        assert PRB["credential_valid"] is True
        assert BLK["authentication_error"] is False
        assert PRB["http_status"] == 400

    def test_request_id_preserved(self):
        assert PRB["request_id"] == PROBE_REQ
        assert BLK["latest_request_id"] == PROBE_REQ
        assert BLK["attempts"][-1]["request_id"] == PROBE_REQ
        assert ST["probe_attempts"][0]["request_id"] == PROBE_REQ

    def test_probe_recorded_separately_from_inspector_retries(self):
        assert BLK["probe_attempts"] == 1
        assert BLK["attempts"][-1]["inspector"].startswith("NONE")
        assert BLK["retry_count"] == 1        # unchanged by the probe

    def test_root_cause_is_the_uninstalled_key(self):
        assert BLK["root_cause"] == "FUNDED_KEY_NOT_INSTALLED_IN_SECRET_SOURCE"
        assert PRB["secret_source"][
            "env_file_unchanged_since_before_authorization"] is True


class TestStage2NeverRan:

    def test_no_inspections_performed(self):
        assert PRB["inspections_run"] == 0
        assert PRB["stage_2_typography_inspections"] == "NOT_RUN"
        assert PRB["inspector_a_status"] == "NOT_PERFORMED_PROBE_FAILED"
        assert PRB["inspector_b_status"] == "NOT_PERFORMED_PROBE_FAILED"

    def test_this_probe_fabricated_nothing(self):
        """Scoped to probe 1. The inspections that exist now ran later, after
        a NEW key and a PASSING probe — not off the back of this failure."""
        assert PRB["inspections_run"] == 0
        assert PRB["model_output_received"] is False
        assert PRB["billable"] is False

    def test_no_lf2_or_a2_created(self):
        assert not os.path.exists(os.path.join(D, "lf2"))
        assert not os.path.exists(os.path.join(D, "a2"))


@pytest.mark.django_db
class TestBoardShowsTheProbe:

    @pytest.fixture
    def client_in(self, client, django_user_model):
        u = django_user_model.objects.create_user(
            "vq2probetester", password="x", is_staff=True, is_superuser=True)
        client.force_login(u)
        return client

    def test_api_exposes_the_probe_without_the_key(self, client_in):
        """The board tracks the LATEST probe; only the fingerprint escapes."""
        v = client_in.get("/api/visual-quality/vq1/").json()["vq2"]
        p = v["billing_probe"]
        assert p["request_id"]
        assert p["credential_valid"] is True
        assert len(p["key_fingerprint"]) == 12
        live = settings.ANTHROPIC_API_KEY or ""
        assert live and live not in json.dumps(v)
        # probe 1's own record keeps its failure verbatim
        assert PRB["request_id"] == PROBE_REQ
        assert PRB["code"] == \
            "VQ2_ANTHROPIC_FUNDED_KEY_OR_BALANCE_NOT_CONFIRMED"

    def test_root_cause_preserved_and_no_key_on_the_page(self, client_in):
        """The root cause is now RESOLVED, so it need not still be on screen —
        but it must remain in the record, and no key may ever render."""
        assert BLK["root_cause"] == "FUNDED_KEY_NOT_INSTALLED_IN_SECRET_SOURCE"
        html = client_in.get(
            "/dashboard/visual-quality/vq1/").content.decode()
        assert "sk-ant-" not in html
        assert (settings.ANTHROPIC_API_KEY or "@@") not in html

    def test_probe_record_is_fetchable(self, client_in):
        r = client_in.get("/api/visual-quality/vq1/vq2-billing-probe/")
        assert r.status_code == 200
