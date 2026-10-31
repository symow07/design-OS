from __future__ import annotations

import json
from pathlib import Path
import threading

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.accounts.security import signing

from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, MachineClassification,
    OperationalPermissionProjection, ProvenanceRecord, ReviewCandidate, SourceArtifact,
)
from . import review_manifest
from .review_manifest import (
    DEFAULT_MANIFEST, MANIFEST_ID, PreparedReviewManifest, import_review_candidates,
)
from .review_services import (
    AssertionValidationError, ReviewAuthorizationDenied, ReviewConflict,
    claim_review_candidate, correct_intelligence_classification,
    read_current_assertions, record_intelligence_classification,
    record_intelligence_evidence_assessment, release_review_candidate,
)

pytestmark = pytest.mark.django_db
User = get_user_model()
KEY = "1" * 32


@pytest.fixture(autouse=True)
def _signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"review-test": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "review-test"
    signing.reset_registry()
    yield
    signing.reset_registry()


def _reviewer(role=authz.DESIGN_REVIEWER, username=None):
    username = username or f"reviewer-{role}-{User.objects.count()}"
    granter = User.objects.create_user(username=f"grant-{username}")
    user = User.objects.create_user(username=username)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="DIP-1B-3 test")
    return user


def _candidate(*, external_key="asset:test", review_type=ReviewCandidate.ReviewType.DESIGN_ASSET):
    kind = {
        ReviewCandidate.ReviewType.DESIGN_ASSET: CorpusItem.Kind.DESIGN_ASSET,
        ReviewCandidate.ReviewType.FONT_TECHNICAL: CorpusItem.Kind.FONT,
        ReviewCandidate.ReviewType.BRAND_IDENTITY: CorpusItem.Kind.BRAND_ASSET,
    }.get(review_type, CorpusItem.Kind.HISTORICAL_DESIGN)
    item = CorpusItem.objects.create(item_kind=kind, external_key=external_key)
    source = SourceArtifact.objects.create(
        source_identifier=f"source-{external_key}", source_location=f"logical:{external_key}",
        source_type=SourceArtifact.SourceType.FILE, sha256="a" * 64,
        parser_identifier="test", parser_version="1", source_schema_version="1")
    evidence = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source, evidence_kind="SOURCE_FILE",
        locator={"path": f"bounded/{external_key}.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="b" * 64)
    if kind == CorpusItem.Kind.DESIGN_ASSET:
        DesignAssetProfile.objects.create(
            corpus_item=item, primary_source_artifact=source,
            candidate_source_key=item.pk.hex[:16],
            source_manifest_entry_key=f"test:{item.pk}",
            dataset_identifier="dip0c2_asset_candidate_pilot/1.0",
            candidate_asset_kind=DesignAssetProfile.CandidateKind.UNKNOWN,
            representation_state=DesignAssetProfile.Representation.UNKNOWN,
            technical_readiness=DesignAssetProfile.Readiness.REVIEW_REQUIRED,
            extraction_state="TEST_FIXTURE", dimensions_media={})
    machine = MachineClassification.objects.create(
        corpus_item=item, classification_type="TECHNICAL_READINESS", label="UNKNOWN",
        confidence="0.5000", classifier_identifier="test", classifier_version="1",
        classification_schema_version="1", source_artifact=source,
        evidence_reference=evidence, structured_explanation={},
        classification_hash="c" * 64)
    candidate = ReviewCandidate.objects.create(
        corpus_item=item, review_type=review_type, priority=50,
        review_manifest_id=MANIFEST_ID, machine_confidence_summary={})
    return item, candidate, evidence, machine


def _payload(item, candidate, evidence, machine, **changes):
    payload = {
        "corpus_item_uuid": str(item.pk),
        "review_candidate_uuid": str(candidate.pk),
        "classification_domain": "design_asset_type",
        "classification_label": "PACKAGING_CANDIDATE",
        "normalized_value": {"type": "packaging"},
        "explanation": "Observed packaging geometry and dieline evidence.",
        "evidence_reference_ids": [str(evidence.pk)],
        "machine_classification_ids": [str(machine.pk)],
    }
    payload.update(changes)
    return payload


def test_official_review_manifest_is_exact_and_contains_canonical_reconciled_uuid():
    document = json.loads(Path(DEFAULT_MANIFEST).read_text())
    assert document["manifest_id"] == MANIFEST_ID
    assert document["expected_counts"] == {
        "total": 46,
        "by_review_type": {
            "HISTORICAL_MEMORY": 14, "DESIGN_ASSET": 14, "FONT_TECHNICAL": 10,
            "BRAND_IDENTITY": 7, "PALETTE_OBSERVATION": 1,
        },
    }
    ids = [entry["corpus_item_uuid"] for entry in document["entries"]]
    assert len(ids) == len(set(ids)) == 46
    assert "fa90d60c-6f58-4f96-9223-4743af3a8234" in ids
    assert "5a0a2de8-d65a-4de1-a058-a5e94b883690" not in ids


def test_review_task_creation_dry_run_apply_and_repeat_are_idempotent(monkeypatch):
    item, candidate, _, _ = _candidate()
    candidate.delete()
    prepared = PreparedReviewManifest(
        path=Path("bounded-test.json"), manifest_hash="d" * 64,
        entries=({
            "corpus_item": item, "review_type": ReviewCandidate.ReviewType.DESIGN_ASSET,
            "priority": 50, "selection_reason": "Bounded idempotence test.",
        },), counts={ReviewCandidate.ReviewType.DESIGN_ASSET: 1})
    monkeypatch.setattr(review_manifest, "prepare_review_manifest", lambda path: prepared)
    dry = import_review_candidates("ignored", apply=False)
    assert dry["would_create"] == 1 and ReviewCandidate.objects.count() == 0
    first = import_review_candidates("ignored", apply=True)
    second = import_review_candidates("ignored", apply=True)
    assert first["created"] == 1
    assert second["created"] == 0 and second["unchanged"] == 1
    assert ReviewCandidate.objects.count() == 1
    assert DecisionEvent.objects.count() == 0


def test_claim_release_are_workflow_only_and_do_not_steal():
    _, candidate, _, _ = _candidate()
    first = _reviewer(username="first")
    second = _reviewer(username="second")
    claim_review_candidate(user=first, candidate_id=candidate.pk)
    candidate.refresh_from_db()
    assert candidate.assigned_to == first
    assert candidate.workflow_status == ReviewCandidate.Status.CLAIMED
    with pytest.raises(ReviewConflict):
        claim_review_candidate(user=second, candidate_id=candidate.pk)
    with pytest.raises(ReviewConflict):
        release_review_candidate(user=second, candidate_id=candidate.pk)
    release_review_candidate(user=first, candidate_id=candidate.pk)
    candidate.refresh_from_db()
    assert candidate.assigned_to is None and candidate.assigned_at is None
    assert DecisionEvent.objects.count() == 0
    assert OperationalPermissionProjection.objects.count() == 0


def test_signed_classification_payload_reader_and_correction_supersession():
    item, candidate, evidence, machine = _candidate()
    reviewer = _reviewer()
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    first = record_intelligence_classification(
        user=reviewer, payload=_payload(item, candidate, evidence, machine))
    assert first.payload["assertion_schema"] == "intelligence_assertion/1.0"
    assert first.payload["asserted_label"] == "PACKAGING_CANDIDATE"
    assert first.payload["evidence_reference_ids"] == [str(evidence.pk)]
    assert first.payload["evidence_source_hashes"][0]["source_sha256"] == "a" * 64
    assert first.payload["authz_snapshot"]["policy_version"] == "authz/1.4"
    assert first.subject_id == str(item.pk)
    assert first.actor == reviewer and first.role_used == authz.DESIGN_REVIEWER
    machine_before = list(MachineClassification.objects.values_list(
        "pk", "classification_hash", "label"))
    assert read_current_assertions(item).current_by_domain[
        "design_asset_type"].event_id == first.event_id

    corrected = _payload(
        item, candidate, evidence, machine,
        classification_label="REFERENCE_MATERIAL",
        normalized_value={"type": "reference"},
        supersedes_event_id=first.event_id)
    second = correct_intelligence_classification(user=reviewer, payload=corrected)
    result = read_current_assertions(item)
    assert second.supersedes_event == first
    assert result.state == "CURRENT"
    assert result.current_by_domain["design_asset_type"].event_id == second.event_id
    assert [(entry.event_id, entry.effective) for entry in result.history] == [
        (first.event_id, False), (second.event_id, True)]
    assert list(MachineClassification.objects.values_list(
        "pk", "classification_hash", "label")) == machine_before
    assert OperationalPermissionProjection.objects.count() == 0


def test_strict_payload_canonical_subject_evidence_and_supersession_guards():
    item, candidate, evidence, machine = _candidate()
    other_item, other_candidate, other_evidence, _ = _candidate(external_key="asset:other")
    reviewer = _reviewer()
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    with pytest.raises(AssertionValidationError, match="server-derived"):
        record_intelligence_classification(
            user=reviewer,
            payload=_payload(item, candidate, evidence, machine, actor_id=reviewer.pk))
    with pytest.raises(AssertionValidationError, match="same corpus item"):
        record_intelligence_classification(
            user=reviewer, payload=_payload(
                item, candidate, other_evidence, machine))
    with pytest.raises(AssertionValidationError, match="domain"):
        record_intelligence_classification(
            user=reviewer, payload=_payload(
                item, candidate, evidence, machine,
                classification_domain="arbitrary_domain"))
    legacy = "5a0a2de8-d65a-4de1-a058-a5e94b883690"
    ProvenanceRecord.objects.create(
        corpus_item=item, source_artifact=evidence.source_artifact,
        provenance_type="CORPUS_IDENTITY_RECONCILIATION",
        normalized_machine_interpretation={
            "legacy_corpus_item_id": legacy, "canonical_corpus_item_id": str(item.pk)})
    with pytest.raises(AssertionValidationError, match="deprecated"):
        record_intelligence_classification(
            user=reviewer, payload=_payload(
                item, candidate, evidence, machine, corpus_item_uuid=legacy))
    first = record_intelligence_classification(
        user=reviewer, payload=_payload(item, candidate, evidence, machine))
    with pytest.raises(AssertionValidationError, match="same item/domain"):
        correct_intelligence_classification(
            user=reviewer, payload=_payload(
                item, candidate, evidence, machine,
                supersedes_event_id="missing"))
    with pytest.raises(AssertionValidationError, match="same item/domain"):
        correct_intelligence_classification(
            user=reviewer, payload=_payload(
                other_item, other_candidate, other_evidence,
                other_item.machine_classifications.first(),
                supersedes_event_id=first.event_id))
    assert first and other_candidate and other_item


def test_evidence_assessment_is_signed_non_authority_and_insufficient_needs_information():
    item, candidate, evidence, _ = _candidate()
    reviewer = _reviewer()
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    event = record_intelligence_evidence_assessment(user=reviewer, payload={
        "corpus_item_uuid": str(item.pk),
        "review_candidate_uuid": str(candidate.pk),
        "assessment": "EVIDENCE_INSUFFICIENT",
        "explanation": "The source does not establish the candidate boundary.",
        "evidence_reference_ids": [str(evidence.pk)],
    })
    candidate.refresh_from_db()
    assert event.payload["authority_effect"] == "NONE"
    assert candidate.workflow_status == ReviewCandidate.Status.NEEDS_INFORMATION
    assert OperationalPermissionProjection.objects.count() == 0


def test_domain_role_and_system_admin_are_denied_substantive_actions():
    item, candidate, evidence, machine = _candidate(
        review_type=ReviewCandidate.ReviewType.FONT_TECHNICAL)
    payload = _payload(
        item, candidate, evidence, machine,
        classification_domain="font_technical_suitability",
        classification_label="SUITABLE_FOR_REVIEW")
    brand = _reviewer(authz.BRAND_ADMIN, username="brand")
    claim_review_candidate(user=brand, candidate_id=candidate.pk)
    with pytest.raises(ReviewAuthorizationDenied):
        record_intelligence_classification(user=brand, payload=payload)
    admin = _reviewer(authz.SYSTEM_ADMIN, username="admin")
    with pytest.raises(ReviewAuthorizationDenied):
        claim_review_candidate(user=admin, candidate_id=candidate.pk)


def test_review_ui_is_authorized_csrf_protected_and_keeps_layers_separate():
    item, candidate, _, _ = _candidate()
    reviewer = _reviewer()
    client = Client(enforce_csrf_checks=True)
    client.force_login(reviewer)
    queue = client.get(reverse("intelligence:review-queue"), secure=True)
    assert queue.status_code == 200
    assert b"HUMAN INTELLIGENCE ASSERTIONS DO NOT AUTHORIZE OPERATIONAL USE" in queue.content
    detail_url = reverse("intelligence:review-detail", args=[candidate.pk])
    detail = client.get(detail_url, secure=True)
    assert detail.status_code == 200
    assert b"OBSERVED FACTS" in detail.content
    assert b"MACHINE CLASSIFICATION" in detail.content
    assert b"OPERATIONAL PERMISSION" in detail.content
    claim_url = reverse("intelligence:review-claim", args=[candidate.pk])
    assert client.post(claim_url, secure=True).status_code == 403
    token = client.cookies["csrftoken"].value
    assert client.post(
        claim_url, secure=True, HTTP_X_CSRFTOKEN=token,
        HTTP_REFERER=f"https://testserver{detail_url}").status_code == 302
    assert DecisionEvent.objects.count() == 0
    assert OperationalPermissionProjection.objects.count() == 0


def test_inbox_denies_unauthenticated_inactive_and_disabled_reviewers():
    _candidate()
    url = reverse("intelligence:review-queue")
    client = Client()
    assert client.get(url, secure=True).status_code == 403
    inactive = _reviewer(username="inactive-reviewer")
    inactive.is_active = False
    inactive.save(update_fields=("is_active",))
    client.force_login(inactive)
    assert client.get(url, secure=True).status_code == 403
    disabled = _reviewer(username="disabled-reviewer")
    disabled.reviewer_profile.reviewer_enabled = False
    disabled.reviewer_profile.save(update_fields=("reviewer_enabled", "updated_at"))
    client.force_login(disabled)
    assert client.get(url, secure=True).status_code == 403


def test_get_cannot_mutate_claim_or_assertion_endpoints():
    _, candidate, _, _ = _candidate()
    reviewer = _reviewer()
    client = Client()
    client.force_login(reviewer)
    for name in (
        "review-claim", "review-release", "review-classify", "review-correct",
        "review-assess-evidence", "review-request-clarification",
    ):
        assert client.get(
            reverse(f"intelligence:{name}", args=[candidate.pk]), secure=True,
        ).status_code == 405
    candidate.refresh_from_db()
    assert candidate.workflow_status == ReviewCandidate.Status.OPEN
    assert DecisionEvent.objects.count() == 0


def test_invalid_chain_fails_current_reader_closed_and_reading_writes_nothing():
    item, candidate, evidence, machine = _candidate()
    reviewer = _reviewer()
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    record_intelligence_classification(
        user=reviewer, payload=_payload(item, candidate, evidence, machine))
    before = (
        DecisionEvent.objects.count(), ReviewCandidate.objects.count(),
        OperationalPermissionProjection.objects.count())
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE accounts_decisionevent SET hmac_signature = %s",
            ["0" * 64])
    result = read_current_assertions(item)
    assert result.state == "REVIEW_REQUIRED"
    assert result.reason == "DECISION_CHAIN_INVALID"
    assert (
        DecisionEvent.objects.count(), ReviewCandidate.objects.count(),
        OperationalPermissionProjection.objects.count()) == before


class CompetingClaimTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.item, self.candidate, _, _ = _candidate()
        self.first = _reviewer(username="thread-first")
        self.second = _reviewer(username="thread-second")

    def test_competing_claims_serialize_and_one_actor_wins(self):
        barrier = threading.Barrier(2)
        outcomes = []

        def attempt(user_id):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                user = User.objects.get(pk=user_id)
                claimed = claim_review_candidate(
                    user=user, candidate_id=self.candidate.pk)
                outcomes.append(("claimed", claimed.assigned_to_id))
            except ReviewConflict:
                outcomes.append(("conflict", user_id))
            finally:
                close_old_connections()

        threads = [
            threading.Thread(target=attempt, args=(self.first.pk,)),
            threading.Thread(target=attempt, args=(self.second.pk,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.candidate.refresh_from_db()
        assert sorted(result[0] for result in outcomes) == ["claimed", "conflict"]
        assert self.candidate.assigned_to_id in {self.first.pk, self.second.pk}
        assert DecisionEvent.objects.count() == 0
