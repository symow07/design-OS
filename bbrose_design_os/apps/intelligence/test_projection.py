from __future__ import annotations

import copy
import io
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.decision_chain import append_decision
from apps.accounts.models import DecisionChainHead, DecisionEvent
from apps.accounts.security import canonical, signing

from .models import (
    EvidenceReference, HumanAssertionProjection, IntelligenceProjectionGeneration,
    OperationalPermissionProjection, ProjectionPublicationState, SourceArtifact,
)
from .projection import (
    GENESIS_EVALUATION_TIMESTAMP, PROJECTOR_IDENTIFIER, PROJECTOR_VERSION,
    PROJECTION_SCHEMA_VERSION, ProjectionPublicationError,
    ProjectionValidationError, ProjectionVerificationError, _classification_rows,
    _verify_evidence, build_projection, rebuild_assertion_projections,
)
from .projection_reader import read_published_assertions
from .review_services import (
    claim_review_candidate, correct_intelligence_classification,
    record_intelligence_classification, record_intelligence_evidence_assessment,
)
from .test_review_workflow import _candidate, _payload, _reviewer

pytestmark = pytest.mark.django_db
KEY = "7" * 32


@pytest.fixture(autouse=True)
def _projection_signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"projection-test": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "projection-test"
    signing.reset_registry()
    yield
    signing.reset_registry()


def _classification():
    item, candidate, evidence, machine = _candidate()
    reviewer = _reviewer()
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    event = record_intelligence_classification(
        user=reviewer, payload=_payload(item, candidate, evidence, machine))
    return item, candidate, evidence, machine, reviewer, event


def _assert_no_permissions():
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()


def test_empty_chain_dry_run_is_deterministic_and_write_free():
    before = (
        IntelligenceProjectionGeneration.objects.count(),
        HumanAssertionProjection.objects.count(),
        ProjectionPublicationState.objects.count())
    first = rebuild_assertion_projections()
    second = rebuild_assertion_projections(
        evaluation_at=GENESIS_EVALUATION_TIMESTAMP, expected_chain_head="GENESIS")
    assert first["projection_row_count"] == 0
    assert first["projection_output_hash"] == second["projection_output_hash"]
    assert first["source_terminal_sequence"] == 0
    assert before == (
        IntelligenceProjectionGeneration.objects.count(),
        HumanAssertionProjection.objects.count(),
        ProjectionPublicationState.objects.count())


def test_empty_apply_publishes_once_and_repeat_is_idempotent():
    first = rebuild_assertion_projections(apply=True, expected_chain_head="GENESIS")
    second = rebuild_assertion_projections(apply=True, expected_chain_head="GENESIS")
    assert first["published"] is True and first["rows_created"] == 0
    assert second["idempotent"] is True and second["rows_created"] == 0
    assert IntelligenceProjectionGeneration.objects.count() == 1
    generation = IntelligenceProjectionGeneration.objects.get()
    assert generation.status == IntelligenceProjectionGeneration.Status.PUBLISHED
    assert ProjectionPublicationState.objects.get(pk=1).current_generation == generation
    _assert_no_permissions()


def test_one_classification_projects_exact_source_and_no_permission():
    item, _, _, _, reviewer, event = _classification()
    report = rebuild_assertion_projections(apply=True)
    row = HumanAssertionProjection.objects.get()
    assert report["projection_row_count"] == 1
    assert row.corpus_item == item
    assert row.assertion_domain == "design_asset_type"
    assert row.effective_state == HumanAssertionProjection.EffectiveState.ASSERTED
    assert row.asserted_label == "PACKAGING_CANDIDATE"
    assert row.normalized_value == {"type": "packaging"}
    assert row.source_decision_event == event
    assert row.source_sequence_number == event.sequence_number
    assert row.source_reviewer == reviewer
    assert row.source_policy_version == "authz/1.4"
    assert read_published_assertions(item).state == "CURRENT"
    _assert_no_permissions()


def test_correction_supersedes_and_preserves_event_and_generation_history():
    item, candidate, evidence, machine, reviewer, first = _classification()
    rebuild_assertion_projections(apply=True)
    old = ProjectionPublicationState.objects.get(pk=1).current_generation
    second = correct_intelligence_classification(user=reviewer, payload=_payload(
        item, candidate, evidence, machine,
        classification_label="REFERENCE_MATERIAL",
        normalized_value={"type": "reference"},
        supersedes_event_id=first.event_id))
    rebuild_assertion_projections(apply=True)
    old.refresh_from_db()
    current = ProjectionPublicationState.objects.get(pk=1).current_generation
    result = read_published_assertions(item)
    assert old.status == IntelligenceProjectionGeneration.Status.SUPERSEDED
    assert old.assertion_projections.count() == 1
    assert current != old and current.status == IntelligenceProjectionGeneration.Status.PUBLISHED
    assert result.current_by_domain["design_asset_type"]["event_id"] == second.event_id
    assert [(entry["event_id"], entry["effective"]) for entry in result.history] == [
        (first.event_id, False), (second.event_id, True)]


def test_cross_item_supersession_is_refused_by_reducer():
    item1, _, _, _ = _candidate(external_key="projection:one")
    item2, _, _, _ = _candidate(external_key="projection:two")
    first_event = SimpleNamespace(
        pk=10, sequence_number=1, action=authz.RECORD_INTELLIGENCE_CLASSIFICATION,
        supersedes_event_id=None)
    correction = SimpleNamespace(
        pk=11, sequence_number=2, action=authz.CORRECT_INTELLIGENCE_CLASSIFICATION,
        supersedes_event_id=10)
    rows = [
        {"event": first_event, "item": item1, "domain": "design_asset_type"},
        {"event": correction, "item": item2, "domain": "design_asset_type"},
    ]
    with pytest.raises(
            ProjectionValidationError, match="CORRECTION_SUBJECT_DOMAIN_MISMATCH"):
        _classification_rows(rows)


def test_two_active_assertions_project_review_required_without_winner():
    item, _, _, _, reviewer, first = _classification()
    payload = copy.deepcopy(first.payload)
    payload["asserted_label"] = "REFERENCE_MATERIAL"
    payload["normalized_value"] = {"type": "reference"}
    payload["explanation"] = "Independent active assertion for conflict testing."
    append_decision(
        user=reviewer, action=authz.RECORD_INTELLIGENCE_CLASSIFICATION,
        subject=("CorpusItem", str(item.pk)), payload=payload)
    rebuild_assertion_projections(apply=True)
    row = HumanAssertionProjection.objects.get()
    assert row.effective_state == HumanAssertionProjection.EffectiveState.REVIEW_REQUIRED
    assert row.source_decision_event is None
    assert row.warning_codes == ["ACTIVE_ASSERTION_CONFLICT"]
    assert read_published_assertions(item).state == "REVIEW_REQUIRED"


@pytest.mark.parametrize("assessment", [
    "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT", "CLARIFICATION_REQUIRED",
])
def test_evidence_assessment_projects_separately_and_grants_nothing(assessment):
    item, candidate, evidence, _ = _candidate(external_key=f"evidence:{assessment}")
    reviewer = _reviewer()
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    event = record_intelligence_evidence_assessment(user=reviewer, payload={
        "corpus_item_uuid": str(item.pk), "review_candidate_uuid": str(candidate.pk),
        "assessment": assessment, "explanation": "Bounded evidence assessment.",
        "evidence_reference_ids": [str(evidence.pk)],
    })
    rebuild_assertion_projections(apply=True)
    row = HumanAssertionProjection.objects.get()
    result = read_published_assertions(item)
    assert row.assertion_domain == "evidence_assessment"
    assert row.effective_state == assessment
    assert row.evidence_assessment == assessment
    assert row.asserted_label == ""
    assert row.source_decision_event == event
    assert result.evidence_assessment["state"] == assessment
    assert result.current_by_domain == {}
    _assert_no_permissions()


def test_signed_unknown_assertion_schema_and_policy_version_fail_closed():
    item, _, _, _, reviewer, event = _classification()
    unknown_schema = copy.deepcopy(event.payload)
    unknown_schema["assertion_schema"] = "intelligence_assertion/999"
    append_decision(
        user=reviewer, action=authz.RECORD_INTELLIGENCE_CLASSIFICATION,
        subject=("CorpusItem", str(item.pk)), payload=unknown_schema)
    with pytest.raises(ProjectionVerificationError, match="UNSUPPORTED_ASSERTION_SCHEMA"):
        build_projection()

    # The first failure is independent; put the latest payload back in the supported
    # assertion schema while pinning an unknown historical policy.
    latest = DecisionEvent.objects.order_by("-sequence_number").first()
    policy_payload = copy.deepcopy(latest.payload)
    policy_payload["assertion_schema"] = "intelligence_assertion/1.0"
    policy_payload["policy_version"] = "authz/999"
    policy_payload["authz_snapshot"]["policy_version"] = "authz/999"
    append_decision(
        user=reviewer, action=authz.RECORD_INTELLIGENCE_CLASSIFICATION,
        subject=("CorpusItem", str(item.pk)), payload=policy_payload)
    # Earlier unsupported-schema event still wins first; the policy-specific case is
    # exercised directly against the signed latest event contract.
    from .projection import _classification_event
    with pytest.raises(ProjectionVerificationError, match="UNSUPPORTED_POLICY_VERSION"):
        _classification_event(DecisionEvent.objects.order_by("-sequence_number").first())


def test_signed_unknown_decision_event_schema_fails_closed():
    _, _, _, _, _, event = _classification()
    registry = signing.get_registry()
    unknown = "decision_event/999"
    doc = canonical.signed_payload(
        event_id=event.event_id, sequence_number=event.sequence_number,
        actor_id=event.actor_id, role_used=event.role_used, action=event.action,
        subject_type=event.subject_type, subject_id=event.subject_id,
        payload=event.payload, previous_event_hash=event.previous_event_hash,
        created_at=event.created_at, signing_key_id=event.signing_key_id,
        schema_version=unknown)
    event_hash = canonical.content_hash(doc)
    event_signature, _ = registry.sign(doc)
    head = DecisionChainHead.objects.get(pk=1)
    head_doc = canonical.signed_head_payload(
        chain_id=head.chain_id, terminal_sequence_number=head.terminal_sequence_number,
        terminal_event_hash=event_hash, event_count=head.event_count,
        signing_key_id=head.signing_key_id, schema_version=head.schema_version)
    head_signature, _ = registry.sign(head_doc)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE accounts_decisionevent SET schema_version=%s, content_hash=%s, "
            "hmac_signature=%s WHERE id=%s",
            [unknown, event_hash, event_signature, event.pk])
        cursor.execute(
            "UPDATE accounts_decisionchainhead SET terminal_event_hash=%s, "
            "head_signature=%s WHERE id=1", [event_hash, head_signature])
    with pytest.raises(ProjectionVerificationError, match="UNSUPPORTED_DECISION_EVENT_SCHEMA"):
        build_projection()


def test_tampered_event_and_invalid_head_abort_and_mark_failed_safely():
    _classification()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE accounts_decisionevent SET hmac_signature=%s", ["0" * 64])
    with pytest.raises(ProjectionVerificationError, match="DECISION_CHAIN_INVALID"):
        rebuild_assertion_projections(apply=True)
    failed = IntelligenceProjectionGeneration.objects.get()
    assert failed.status == IntelligenceProjectionGeneration.Status.FAILED
    assert failed.failure_summary == "DECISION_CHAIN_INVALID"
    assert ProjectionPublicationState.objects.count() == 0


def test_invalid_signed_head_aborts_generation():
    _classification()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE accounts_decisionchainhead SET head_signature=%s WHERE id=1",
            ["0" * 64])
    with pytest.raises(ProjectionVerificationError, match="DECISION_CHAIN_INVALID"):
        build_projection()


def test_unsupported_intelligence_action_fails_closed():
    item, _, _, _ = _candidate(external_key="unsupported:intelligence-action")
    reviewer = _reviewer()
    append_decision(
        user=reviewer, action=authz.CLAIM_INTELLIGENCE_REVIEW,
        subject=("CorpusItem", str(item.pk)), payload={})
    with pytest.raises(
            ProjectionValidationError, match="UNSUPPORTED_INTELLIGENCE_EVENT_ACTION"):
        build_projection()


def test_deterministic_rebuild_and_source_order_normalization():
    item, _, evidence, _, _, _ = _classification()
    first = build_projection()
    second = build_projection(evaluation_at=first.evaluation_timestamp)
    assert first.output_hash == second.output_hash
    assert [row.logical_document() for row in first.rows] == [
        row.logical_document() for row in second.rows]
    other_source = SourceArtifact.objects.create(
        source_identifier="projection-order-two", source_location="logical:order-two",
        source_type=SourceArtifact.SourceType.FILE, sha256="d" * 64,
        parser_identifier="test", parser_version="1", source_schema_version="1")
    other = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=other_source, evidence_kind="SOURCE_FILE",
        locator={"path": "bounded/order-two.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="e" * 64)
    evidence_ids = tuple(sorted((evidence.pk, other.pk), key=str))
    sources = [{
        "evidence_reference_id": str(row.pk),
        "evidence_hash": row.evidence_hash,
        "source_artifact_id": str(row.source_artifact_id),
        "source_sha256": row.source_artifact.sha256,
    } for row in (evidence, other)]
    expected = sorted(sources, key=lambda row: row["evidence_reference_id"])
    assert _verify_evidence(item, evidence_ids, list(reversed(sources)), "TEST") \
        == expected


def test_failed_publication_does_not_replace_current_and_atomic_pointer_rolls_back(
        monkeypatch):
    _classification()
    rebuild_assertion_projections(apply=True)
    publication = ProjectionPublicationState.objects.get(pk=1)
    old_id = publication.current_generation_id
    original_save = IntelligenceProjectionGeneration.save

    def fail_published_save(instance, *args, **kwargs):
        if (instance.pk != old_id
                and instance.status == IntelligenceProjectionGeneration.Status.PUBLISHED):
            raise ProjectionPublicationError("TEST_PUBLICATION_FAILURE")
        return original_save(instance, *args, **kwargs)

    # Explicit evaluation time forces a distinct generation on the unchanged chain.
    monkeypatch.setattr(IntelligenceProjectionGeneration, "save", fail_published_save)
    with pytest.raises(ProjectionPublicationError, match="TEST_PUBLICATION_FAILURE"):
        rebuild_assertion_projections(
            apply=True, evaluation_at=timezone.now() + timezone.timedelta(seconds=1))
    publication.refresh_from_db()
    assert publication.current_generation_id == old_id
    assert IntelligenceProjectionGeneration.objects.get(pk=old_id).status \
        == IntelligenceProjectionGeneration.Status.PUBLISHED
    assert IntelligenceProjectionGeneration.objects.filter(
        status=IntelligenceProjectionGeneration.Status.FAILED).count() == 1


def test_new_event_makes_projection_stale_and_expected_head_mismatch_cannot_publish():
    item, _, _, _, reviewer, event = _classification()
    rebuild_assertion_projections(apply=True)
    current_generation = ProjectionPublicationState.objects.get(pk=1).current_generation_id
    payload = copy.deepcopy(event.payload)
    payload["asserted_label"] = "REFERENCE_MATERIAL"
    payload["normalized_value"] = {"type": "reference"}
    append_decision(
        user=reviewer, action=authz.RECORD_INTELLIGENCE_CLASSIFICATION,
        subject=("CorpusItem", str(item.pk)), payload=payload)
    stale = read_published_assertions(item)
    assert stale.state == "STALE" and stale.current_by_domain == {}
    with pytest.raises(ProjectionVerificationError, match="EXPECTED_CHAIN_HEAD_MISMATCH"):
        rebuild_assertion_projections(apply=True, expected_chain_head="0" * 64)
    assert ProjectionPublicationState.objects.get(pk=1).current_generation_id \
        == current_generation


def test_workflow_machine_and_direct_rows_never_become_published_truth():
    item, _, _, _ = _candidate()
    build = build_projection()
    assert build.rows == ()
    direct_generation = IntelligenceProjectionGeneration.objects.create(
        projector_identifier=PROJECTOR_IDENTIFIER, projector_version=PROJECTOR_VERSION,
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
        evaluation_timestamp=GENESIS_EVALUATION_TIMESTAMP)
    HumanAssertionProjection.objects.create(
        projection_generation=direct_generation, corpus_item=item,
        assertion_domain="design_asset_type",
        effective_state=HumanAssertionProjection.EffectiveState.REVIEW_REQUIRED,
        warning_codes=["DIRECT_NON_AUTHORITY"])
    with pytest.raises(ValidationError, match="immutable"):
        HumanAssertionProjection.objects.filter(
            projection_generation=direct_generation).update(
                warning_codes=["MUTATED"])
    with pytest.raises(ValidationError, match="atomic projector service"):
        ProjectionPublicationState.objects.create(
            id=1, current_generation=direct_generation,
            projector_identifier=PROJECTOR_IDENTIFIER,
            projector_version=PROJECTOR_VERSION,
            projection_schema_version=PROJECTION_SCHEMA_VERSION,
            published_at=timezone.now())
    with pytest.raises(ValidationError, match="atomic projector service"):
        ProjectionPublicationState.objects.filter(pk=1).update(
            published_terminal_sequence=99)
    result = read_published_assertions(item)
    assert result.state == "NOT_BUILT" and result.current_by_domain == {}
    _assert_no_permissions()


def test_command_dry_run_and_browser_reads_write_nothing():
    item, candidate, _, _ = _candidate()
    reviewer = _reviewer()
    before = (
        DecisionEvent.objects.count(), IntelligenceProjectionGeneration.objects.count(),
        HumanAssertionProjection.objects.count(), OperationalPermissionProjection.objects.count())
    output = io.StringIO()
    call_command(
        "rebuild_intelligence_assertions", "--json",
        "--evaluation-timestamp", "1970-01-01T00:00:00+00:00", stdout=output)
    assert '"mode": "dry-run"' in output.getvalue()
    client = Client()
    client.force_login(reviewer)
    response = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk]), secure=True)
    assert response.status_code == 200
    assert b"PROJECTION STATUS" in response.content
    assert b"HUMAN ASSERTION PROJECTION" in response.content
    assert b"MACHINE CLASSIFICATION" in response.content
    assert b"OPERATIONAL PERMISSION" in response.content
    assert before == (
        DecisionEvent.objects.count(), IntelligenceProjectionGeneration.objects.count(),
        HumanAssertionProjection.objects.count(), OperationalPermissionProjection.objects.count())
    assert read_published_assertions(item).state == "NOT_BUILT"
