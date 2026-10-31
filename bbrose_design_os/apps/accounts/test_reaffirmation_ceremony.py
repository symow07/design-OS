"""DECISION-EVENT HUMAN REAFFIRMATION CEREMONY — events 1–3 (DEKEYLOSS-2026-07-25-001).

Recreates the real world shape in miniature: a genesis single-operator
bootstrap grant + two independent semantic-metadata records, all signed under
an epoch that is then declared lost; then the ceremony runs under the new
epoch and every §5/§6 property is asserted.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts import bootstrap_registry as reg
from apps.accounts import chain_verification, reaffirmation
from apps.accounts.bootstrap_ceremony import perform_single_operator_ceremony
from apps.accounts.decision_chain import (
    append_decision,
    event_integrity_state,
    verify_chain,
    verify_event,
)
from apps.accounts.models import (
    GRANT_TEST_FIXTURE,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from apps.accounts.security import key_epochs, signing

pytestmark = pytest.mark.django_db
User = get_user_model()
KEY1 = "c" * 32          # the epoch the tests declare lost
KEY2 = "d" * 32          # the active replacement epoch


@pytest.fixture()
def epochs(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"lost-epoch": KEY1,
                                         "live-epoch": KEY2}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "lost-epoch"
    settings.BOOTSTRAP_ENABLED = True
    settings.BOOTSTRAP_SINGLE_OPERATOR_ENABLED = True
    settings.DEBUG = True
    settings.ENVIRONMENT = "LOCAL_DEVELOPMENT"
    settings.LOCAL_DEVELOPMENT_DATABASES = [
        settings.DATABASES["default"]["NAME"]]
    signing.reset_registry()
    yield settings
    signing.reset_registry()


def _declare_lost(monkeypatch, key_id="lost-epoch"):
    monkeypatch.setitem(key_epochs.LOST_KEY_INCIDENTS, key_id, {
        "schema_version": key_epochs.INCIDENT_SCHEMA,
        "incident_id": "DEKEYLOSS-2026-07-25-001",
        "declared_on": "2026-07-25",
        "affected_event_sequence_numbers": [1, 2, 3],
    })


def _legacy_world(settings):
    """Genesis bootstrap grant + two RECORD metadata events under the
    soon-to-be-lost epoch, then the environment moves to the live epoch."""
    from apps.intelligence.models import EvidenceReference
    from apps.intelligence.semantic_metadata_service import (
        _signed_metadata_payload,
        _subject,
        record_human_semantic_metadata,
    )
    from apps.intelligence.test_human_semantic_metadata import (
        _payload,
        _scoped_item,
    )

    operator = User.objects.create_superuser(
        username="reaffirm-op", password="x")
    perform_single_operator_ceremony(
        authenticated_user=operator, role="DESIGN_REVIEWER",
        expires_days=14, reason="epoch-reset ceremony test",
        account_control_basis=reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE)

    item, source_ref = _scoped_item("asset:reaffirm-0001")
    unit = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source_ref.source_artifact,
        evidence_kind="FILE_PAGE_UNIT",
        locator={"page": 0, "unit_key": "asset:reaffirm-0001-p0-u01"},
        locator_schema_version="file_page/1.0", evidence_hash="f1" * 32)
    first = record_human_semantic_metadata(user=operator, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    # the second independent RECORD replicates the real pre-CORR-3 fork:
    # appended directly, exactly as the historical data stands
    from apps.intelligence.human_semantic_metadata import build_metadata_bundle
    signed = _signed_metadata_payload(
        action=authz.RECORD_HUMAN_SEMANTIC_METADATA, user=operator, item=item,
        bundle=build_metadata_bundle(_payload(item, unit)["bundle"]),
        evidence=[{
            "evidence_reference_id": str(unit.pk),
            **{k: v for k, v in _evidence_row(item, unit).items()},
        }])
    second = append_decision(
        user=operator, action=authz.RECORD_HUMAN_SEMANTIC_METADATA,
        subject=_subject(item), payload=signed)

    settings.DECISION_EVENT_HMAC_KEYS = {"live-epoch": KEY2}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "live-epoch"
    signing.reset_registry()
    return operator, item, first, second


def _evidence_row(item, unit):
    from apps.intelligence.semantic_metadata_service import _evidence_payload
    row = _evidence_payload(item, [str(unit.pk)])[0]
    row.pop("evidence_reference_id", None)
    return row


def _packet_copy():
    tmp = tempfile.mkdtemp(prefix="reaffirm_")
    path = str(Path(tmp) / "packet.json")
    shutil.copyfile(reaffirmation.PACKET_PATH, path)
    return tmp, path


class TestCeremony:
    def test_full_ceremony_end_state(self, epochs, monkeypatch):
        operator, item, first, second = _legacy_world(epochs)
        _declare_lost(monkeypatch)
        unrelated = User.objects.create_user(username="unrelated-rev")
        ReviewerProfile.objects.create(user=unrelated, reviewer_enabled=True)
        other_assignment = ReviewerRoleAssignment.objects.create(
            user=unrelated, role=authz.DESIGN_REVIEWER,
            granted_by=operator, granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=5),
            grant_source=GRANT_TEST_FIXTURE, grant_reason="unrelated")
        originals = {e["id"]: e for e in DecisionEvent.objects.filter(
            sequence_number__lte=3).values()}
        tmp, packet_path = _packet_copy()
        try:
            with patch("apps.pipeline.agents.image_producer.openai") as prov:
                result = reaffirmation.perform_reaffirmation_ceremony(
                    actor=operator, packet_path=packet_path)
            assert not prov.mock_calls                # no provider call, ever

            # replacements: one per legacy event, correct targets, epoch-2
            reps = list(DecisionEvent.objects.filter(
                event_id__in=result["replacement_event_ids"]).order_by(
                "sequence_number"))
            assert [r.supersedes_event.event_id for r in reps] == [
                first.event_id, second.event_id]
            for r in reps:
                assert r.signing_key_id == "live-epoch"
                assert verify_event(r)[0] is True
                assert event_integrity_state(r) == "VERIFIED"
                block = r.payload["reaffirmation"]
                assert block["schema"] == reaffirmation.REAFFIRMATION_SCHEMA
                assert block["human_decision"] == "SUPERSEDE"
                # §2: exact bounded semantic meaning preserved
                legacy = DecisionEvent.objects.get(
                    event_id=block["legacy_event_id"])
                assert r.payload["metadata_bundle"] == \
                    legacy.payload["metadata_bundle"]
                assert r.payload["evidence_source_hashes"] == \
                    legacy.payload["evidence_source_hashes"]
                # §3: no operational permissions granted
                assert not any("permission" in k for k in r.payload)

            # closure: signed epoch-2, references the grant, statements exact
            closure = DecisionEvent.objects.get(
                event_id=result["closure_event_id"])
            assert closure.action == reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE
            assert closure.signing_key_id == "live-epoch"
            assert verify_event(closure)[0] is True
            assert tuple(closure.payload["statements"]) == \
                reg.CLOSURE_REQUIRED_STATEMENTS

            # assignment revoked; profile disabled; superuser intact;
            # unrelated assignment untouched
            assignment = ReviewerRoleAssignment.objects.get(
                grant_source="BOOTSTRAP_SINGLE_OPERATOR")
            assert assignment.revoked_at is not None
            profile = ReviewerProfile.objects.get(user=operator)
            assert profile.reviewer_enabled is False
            operator.refresh_from_db()
            assert operator.is_superuser and operator.is_active
            other_assignment.refresh_from_db()
            assert other_assignment.revoked_at is None

            # originals byte-identical and still classified legacy
            now_rows = {e["id"]: e for e in DecisionEvent.objects.filter(
                sequence_number__lte=3).values()}
            assert now_rows == originals
            for ev in DecisionEvent.objects.filter(sequence_number__lte=3):
                assert event_integrity_state(ev) == key_epochs.LEGACY_STATE

            # §5 chain: verifies with legacy notices, head under epoch 2
            res = verify_chain()
            assert res.ok is True
            assert len(res.legacy_notices) == 3       # 3 events; head re-signed
            report = chain_verification.verify_decision_chain()
            assert report.ok is True and report.fatal == ()

            # §6 corpus: blocker cleared → pre-incident MULTIPLE_ACTIVE posture
            from apps.intelligence.metadata_history import (
                REVIEW_REQUIRED,
                resolve_effective_assertion_from_verified_history,
            )
            resolved = resolve_effective_assertion_from_verified_history(item)
            assert resolved.state == REVIEW_REQUIRED
            assert resolved.reason == "MULTIPLE_ACTIVE_METADATA_EVENTS"
            assert resolved.reason != \
                key_epochs.CORPUS_AUTHORIZATION_REAFFIRMATION_REQUIRED

            # §7 packet
            packet = json.load(open(packet_path))
            assert packet["status"] == "COMPLETE"
            outcomes = {d["sequence_number"]: d["human_decision"]
                        for d in packet["decisions"]}
            assert outcomes == {1: "NO_LONGER_REQUIRED", 2: "SUPERSEDED",
                                3: "SUPERSEDED"}
            assert all("lineage" in d for d in packet["decisions"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ceremony_is_idempotent(self, epochs, monkeypatch):
        operator, item, first, second = _legacy_world(epochs)
        _declare_lost(monkeypatch)
        tmp, packet_path = _packet_copy()
        try:
            r1 = reaffirmation.perform_reaffirmation_ceremony(
                actor=operator, packet_path=packet_path)
            count = DecisionEvent.objects.count()
            r2 = reaffirmation.perform_reaffirmation_ceremony(
                actor=operator, packet_path=packet_path)
            assert r1["closure_event_id"] == r2["closure_event_id"]
            assert r1["replacement_event_ids"] == r2["replacement_event_ids"]
            assert DecisionEvent.objects.count() == count
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_applicability_blocks_on_changed_evidence(self, epochs,
                                                      monkeypatch):
        operator, item, first, second = _legacy_world(epochs)
        _declare_lost(monkeypatch)
        from apps.intelligence.models import EvidenceReference
        ref = EvidenceReference.objects.get(
            pk=first.payload["evidence_reference_ids"][0])
        ref.evidence_hash = "0" * 64
        ref.save()
        with pytest.raises(reaffirmation.ReaffirmationError) as exc:
            reaffirmation.perform_reaffirmation_ceremony(actor=operator)
        assert exc.value.code == \
            reaffirmation.CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED
        # nothing was appended
        assert not DecisionEvent.objects.filter(
            action=reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE).exists()
        assert not DecisionEvent.objects.filter(
            action=authz.CORRECT_HUMAN_SEMANTIC_METADATA).exists()

    def test_closure_reserved_for_declared_lost_epochs(self, epochs):
        operator, *_ = _legacy_world(epochs)
        # key absent but NOT declared lost → the grant is INVALID, not legacy,
        # and the ceremony refuses to touch it
        with pytest.raises(reaffirmation.ReaffirmationError) as exc:
            reaffirmation.close_legacy_reviewer_grant(actor=operator)
        assert exc.value.code == "LEGACY_STATE_REQUIRED"

    def test_closure_never_creates_authority(self, epochs, monkeypatch):
        operator, item, first, second = _legacy_world(epochs)
        _declare_lost(monkeypatch)
        tmp, packet_path = _packet_copy()
        try:
            reaffirmation.perform_reaffirmation_ceremony(
                actor=operator, packet_path=packet_path)
            from apps.accounts.authorization import authorize_actor
            res = authorize_actor(operator,
                                  authz.RECORD_HUMAN_SEMANTIC_METADATA)
            assert res.allowed is False               # reviewer authority gone
            from apps.intelligence.models import (
                OperationalPermissionProjection,
            )
            assert OperationalPermissionProjection.objects.count() == 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
