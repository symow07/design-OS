"""DECISION-EVENT KEY EPOCH RESET — lost-key epochs are a classified state.

Contract under a formally declared lost key (incident DEKEYLOSS-2026-07-25-001):
events signed under it are UNVERIFIABLE_DUE_TO_LOST_KEY_MATERIAL — never VALID,
never TAMPERED without evidence, never able to authorize a new action — while
the CHAIN stays verifiable so reaffirmed decisions under the active epoch can
restore authority. Tamper evidence on a legacy event is still fatal.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from . import authz_policy as authz
from . import chain_verification
from .decision_chain import (
    append_decision,
    event_integrity_state,
    verify_chain,
    verify_event,
)
from .models import (
    GRANT_TEST_FIXTURE,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from .security import key_epochs, signing

pytestmark = pytest.mark.django_db
User = get_user_model()
ACTION = authz.CONFIRM_DESIGN_QUALITY
KEY1 = "a" * 32           # the epoch whose material the tests declare lost
KEY2 = "b" * 32           # the active replacement epoch


@pytest.fixture()
def epochs(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"old-epoch": KEY1, "new-epoch": KEY2}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "old-epoch"
    signing.reset_registry()
    yield settings
    signing.reset_registry()


def _reviewer(username="epoch-reviewer"):
    granter = User.objects.create_user(username=f"{username}-granter")
    user = User.objects.create_user(username=username)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=authz.DESIGN_REVIEWER, granted_by=granter,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="epoch test")
    return user


def _legacy_event(settings, user):
    """One event signed under old-epoch, then the environment moves on: only
    new-epoch key material remains (the old material is GONE, exactly like
    the real incident) and old-epoch is declared lost."""
    ev = append_decision(user=user, action=ACTION, payload={"note": "legacy"})
    settings.DECISION_EVENT_HMAC_KEYS = {"new-epoch": KEY2}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "new-epoch"
    signing.reset_registry()
    return ev


def _declare_lost(monkeypatch, key_id="old-epoch"):
    monkeypatch.setitem(key_epochs.LOST_KEY_INCIDENTS, key_id, {
        "schema_version": key_epochs.INCIDENT_SCHEMA,
        "incident_id": "DEKEYLOSS-TEST-001",
        "declared_on": "2026-07-25",
        "affected_event_sequence_numbers": [1],
    })


def test_legacy_event_fails_closed_with_classification(epochs, monkeypatch):
    ev = _legacy_event(epochs, _reviewer())
    _declare_lost(monkeypatch)
    ok, problems = verify_event(ev)
    assert ok is False                       # can never authorize again
    assert problems and all(key_epochs.is_legacy_problem(p)
                            for p in problems)
    assert all("HMAC does not verify" not in p for p in problems)
    assert event_integrity_state(ev) == \
        "UNVERIFIABLE_DUE_TO_LOST_KEY_MATERIAL"


def test_undeclared_missing_key_is_still_a_plain_failure(epochs):
    ev = _legacy_event(epochs, _reviewer())
    # no incident declared: a missing key is an ordinary fatal key problem —
    # the legacy state is a HUMAN declaration, never inferred from absence
    ok, problems = verify_event(ev)
    assert ok is False
    assert not any(key_epochs.is_legacy_problem(p) for p in problems)
    assert event_integrity_state(ev) == "INVALID"


def test_chain_reports_legacy_notices_without_failing(epochs, monkeypatch):
    _legacy_event(epochs, _reviewer())
    _declare_lost(monkeypatch)
    res = verify_chain()
    assert res.ok is True                    # chain classified, not bricked
    assert res.problems == ()
    # the event and the head (also signed under the lost epoch) are notices
    assert len(res.legacy_notices) == 2
    assert all(key_epochs.LEGACY_STATE in n for n in res.legacy_notices)


def test_reaffirmed_decision_under_new_epoch_restores_authority(
        epochs, monkeypatch):
    _legacy_event(epochs, _reviewer())
    _declare_lost(monkeypatch)
    replacement = append_decision(user=_reviewer("epoch-reviewer-2"),
                                  action=ACTION,
                                  payload={"note": "reaffirmed"})
    ok, _ = verify_event(replacement)
    assert ok is True
    assert event_integrity_state(replacement) == "VERIFIED"
    res = verify_chain()
    assert res.ok is True
    # the append re-signed the head under the active epoch — only the
    # legacy EVENT remains a notice
    assert len(res.legacy_notices) == 1
    assert "seq 1" in res.legacy_notices[0]


def test_tampered_legacy_event_is_still_fatal(epochs, monkeypatch):
    ev = _legacy_event(epochs, _reviewer())
    _declare_lost(monkeypatch)
    with connection.cursor() as cur:         # bypass ORM append-only guards
        cur.execute(
            "UPDATE accounts_decisionevent SET payload = %s WHERE id = %s",
            [json.dumps({"note": "forged"}), ev.pk])
    ev.refresh_from_db()
    assert event_integrity_state(ev) == "INVALID"    # never absorbed as legacy
    res = verify_chain()
    assert res.ok is False
    assert any("content hash" in p for p in res.problems)


def test_chain_verification_classifies_legacy_as_warnings(epochs, monkeypatch):
    _legacy_event(epochs, _reviewer())
    _declare_lost(monkeypatch)
    report = chain_verification.verify_decision_chain()
    assert report.ok is True
    assert report.fatal == ()
    codes = {f.code for f in report.warnings}
    assert key_epochs.LEGACY_SIGNATURE_UNVERIFIABLE in codes
    assert key_epochs.LEGACY_DECISION_REAFFIRMATION_REQUIRED in codes
    # the legacy event's payload semantics are NOT re-validated for authority
    legacy_findings = [f for f in report.warnings
                       if f.code == key_epochs.LEGACY_SIGNATURE_UNVERIFIABLE]
    assert legacy_findings


def test_corpus_metadata_assertion_suspended_not_invalid(epochs, monkeypatch):
    from apps.intelligence.metadata_history import (
        REVIEW_REQUIRED,
        resolve_effective_assertion_from_verified_history,
    )
    from apps.intelligence.semantic_metadata_service import (
        record_human_semantic_metadata,
    )
    from apps.intelligence.test_human_semantic_metadata import (
        _payload,
        _scoped_item,
    )
    from apps.intelligence.models import EvidenceReference

    item, source_ref = _scoped_item("asset:epoch-0001")
    unit = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source_ref.source_artifact,
        evidence_kind="FILE_PAGE_UNIT",
        locator={"page": 0, "unit_key": "asset:epoch-0001-p0-u01"},
        locator_schema_version="file_page/1.0", evidence_hash="e0" * 32)
    reviewer = _reviewer("epoch-metadata-reviewer")
    record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))

    epochs.DECISION_EVENT_HMAC_KEYS = {"new-epoch": KEY2}
    epochs.DECISION_EVENT_ACTIVE_KEY_ID = "new-epoch"
    signing.reset_registry()
    _declare_lost(monkeypatch)

    resolved = resolve_effective_assertion_from_verified_history(item)
    assert resolved.state == REVIEW_REQUIRED
    assert resolved.reason == \
        key_epochs.CORPUS_AUTHORIZATION_REAFFIRMATION_REQUIRED


def test_real_incident_registry_and_record():
    assert key_epochs.is_lost_key_id("dip1c-dev-key-1")
    inc = key_epochs.incident_for("dip1c-dev-key-1")
    assert inc["incident_id"] == "DEKEYLOSS-2026-07-25-001"
    record = json.loads(Path(
        "docs/security/decision_event_key_loss_incident.json").read_text())
    assert record["incident_id"] == inc["incident_id"]
    assert set(record["classification"]) == {
        "DECISION_EVENT_ORIGINAL_KEY_MATERIAL_UNRECOVERABLE",
        "LEGACY_DECISION_SIGNATURE_UNVERIFIABLE",
        "DECISION_EVENT_KEY_EPOCH_RESET_REQUIRED"}
    assert record["affected_historical_events"]["count"] == 3
    packet = json.loads(Path(
        "docs/security/decision_event_reaffirmation_packet.json").read_text())
    assert [d["sequence_number"] for d in packet["decisions"]] == [1, 2, 3]
    # the packet lifecycle: PENDING_HUMAN_DECISION (undecided) → COMPLETE
    # (every decision recorded with lineage) — never anything in between
    if packet["status"] == "PENDING_HUMAN_DECISION":
        assert all(d["human_decision"] is None for d in packet["decisions"])
    else:
        assert packet["status"] == "COMPLETE"
        assert {d["sequence_number"]: d["human_decision"]
                for d in packet["decisions"]} == {
            1: "NO_LONGER_REQUIRED", 2: "SUPERSEDED", 3: "SUPERSEDED"}
        assert all("lineage" in d for d in packet["decisions"])
    blob = json.dumps(record) + json.dumps(packet)
    assert KEY1 not in blob and KEY2 not in blob
    assert "DECISION_EVENT_HMAC_KEYS={" not in blob


def test_new_epoch_crypto_fail_closed(epochs):
    epochs.DECISION_EVENT_HMAC_KEYS = {"new-epoch": KEY2}
    epochs.DECISION_EVENT_ACTIVE_KEY_ID = "new-epoch"
    signing.reset_registry()
    payload = {"probe": 1}
    sig, key_id = signing.sign(payload)
    assert signing.verify(payload, sig, key_id) is True
    assert signing.verify({"probe": 2}, sig, key_id) is False
    with pytest.raises(signing.SigningConfigurationError):
        signing.verify(payload, sig, "unknown-epoch-id")


def test_immutability_of_persisted_legacy_rows(epochs, monkeypatch):
    ev = _legacy_event(epochs, _reviewer())
    _declare_lost(monkeypatch)
    before = DecisionEvent.objects.values().get(pk=ev.pk)
    verify_event(ev)
    event_integrity_state(ev)
    verify_chain()
    chain_verification.verify_decision_chain()
    assert DecisionEvent.objects.values().get(pk=ev.pk) == before
