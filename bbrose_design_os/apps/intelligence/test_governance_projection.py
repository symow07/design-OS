from __future__ import annotations

import copy
import io
import json

from django.core.management import call_command
from django.db import connection
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.decision_chain import append_decision
from apps.accounts.security import signing

from .governance import GovernanceEligibilityError
from .governance_projection import (
    GENESIS_EVALUATION_TIMESTAMP,
    GovernanceProjectionPublicationError,
    GovernanceProjectionVerificationError,
    build_governance_projection,
    rebuild_governance_projections,
)
from .governance_reader import read_published_governance
from .models import (
    GovernanceDecisionProjection,
    GovernanceProjectionGeneration,
    GovernanceProjectionPublicationState,
    OperationalPermissionProjection,
)
from .test_governance import candidate, finalize, reviewer

pytestmark = pytest.mark.django_db
KEY = "4" * 32


@pytest.fixture(autouse=True)
def _projection_signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"governance-projection-test": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "governance-projection-test"
    signing.reset_registry()
    yield
    signing.reset_registry()


def no_allowed_permissions():
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()


def test_empty_chain_dry_run_is_write_free_deterministic_and_empty_apply_idempotent():
    before = (
        GovernanceProjectionGeneration.objects.count(),
        GovernanceDecisionProjection.objects.count(),
        GovernanceProjectionPublicationState.objects.count())
    first = rebuild_governance_projections()
    second = rebuild_governance_projections(
        evaluation_at=GENESIS_EVALUATION_TIMESTAMP, expected_chain_head="GENESIS")
    assert first["projection_row_count"] == 0
    assert first["projection_output_hash"] == second["projection_output_hash"]
    assert before == (
        GovernanceProjectionGeneration.objects.count(),
        GovernanceDecisionProjection.objects.count(),
        GovernanceProjectionPublicationState.objects.count())
    applied = rebuild_governance_projections(apply=True, expected_chain_head="GENESIS")
    repeated = rebuild_governance_projections(apply=True, expected_chain_head="GENESIS")
    assert applied["published"] is True and applied["rows_created"] == 0
    assert repeated["idempotent"] is True and repeated["rows_created"] == 0
    assert GovernanceProjectionGeneration.objects.count() == 1
    assert GovernanceProjectionPublicationState.objects.get(pk=1).current_generation \
        == GovernanceProjectionGeneration.objects.get()
    no_allowed_permissions()


def test_one_final_projects_active_and_reader_is_current():
    item, _review, evidence = candidate()
    event, _attestations, _finalizer = finalize(item, evidence)
    report = rebuild_governance_projections(apply=True)
    row = GovernanceDecisionProjection.objects.get()
    assert report["projected_decision_count"] == 1
    assert row.selected_corpus_item == item
    assert row.effective_state == GovernanceDecisionProjection.EffectiveState.ACTIVE
    assert row.source_final_decision_event == event
    assert row.source_sequence_number == event.sequence_number
    assert row.source_policy_version == "authz/1.4"
    result = read_published_governance(item)
    assert result.state == "CURRENT"
    assert result.projections[0]["effective_state"] == "ACTIVE"
    no_allowed_permissions()


def test_replacement_projects_prior_superseded_and_new_active():
    first_item, _review1, first_evidence = candidate()
    first, _pair1, _finalizer1 = finalize(first_item, first_evidence)
    rebuild_governance_projections(apply=True)
    old_generation = GovernanceProjectionPublicationState.objects.get(
        pk=1).current_generation
    second_item, _review2, second_evidence = candidate()
    second, _pair2, _finalizer2 = finalize(
        second_item, second_evidence, supersedes=first.event_id)
    rebuild_governance_projections(apply=True)
    old_generation.refresh_from_db()
    rows = list(GovernanceDecisionProjection.objects.filter(
        projection_generation=GovernanceProjectionPublicationState.objects.get(
            pk=1).current_generation).order_by("source_sequence_number"))
    assert [(row.source_final_decision_event_id, row.effective_state) for row in rows] == [
        (first.pk, GovernanceDecisionProjection.EffectiveState.SUPERSEDED),
        (second.pk, GovernanceDecisionProjection.EffectiveState.ACTIVE),
    ]
    assert old_generation.status == GovernanceProjectionGeneration.Status.SUPERSEDED
    assert read_published_governance(first_item).projections[0][
        "effective_state"] == "SUPERSEDED"
    assert read_published_governance(second_item).projections[0][
        "effective_state"] == "ACTIVE"


def test_revocation_projects_revoked_without_mutating_final():
    item, _review, evidence = candidate()
    final, _pair, _finalizer = finalize(item, evidence)
    original_hash = final.content_hash
    from .governance import revoke_governance_decision
    revocation = revoke_governance_decision(
        user=reviewer(authz.SYSTEM_ADMIN), final_event_id=final.event_id,
        reason="Emergency governance withdrawal")
    rebuild_governance_projections(apply=True)
    row = GovernanceDecisionProjection.objects.get()
    final.refresh_from_db()
    assert row.effective_state == GovernanceDecisionProjection.EffectiveState.REVOKED
    assert row.revoked_at == revocation.created_at
    assert row.projection_metadata["revocation_event_id"] == revocation.event_id
    assert final.content_hash == original_hash


def test_multiple_unsuperseded_finals_project_review_required_without_latest_winner():
    item, _review, evidence = candidate()
    first, _pair, finalizer = finalize(item, evidence)
    payload = copy.deepcopy(first.payload)
    second = append_decision(
        user=finalizer, action=authz.FINALIZE_CANONICAL_BRAND_ASSET,
        subject=(first.subject_type, first.subject_id), payload=payload)
    rebuild_governance_projections(apply=True)
    rows = list(GovernanceDecisionProjection.objects.order_by("source_sequence_number"))
    assert [row.source_final_decision_event_id for row in rows] == [first.pk, second.pk]
    assert {row.effective_state for row in rows} == {
        GovernanceDecisionProjection.EffectiveState.REVIEW_REQUIRED}
    assert all(row.warning_codes == ["ACTIVE_GOVERNANCE_CONFLICT"] for row in rows)
    assert read_published_governance(item).state == "REVIEW_REQUIRED"


def test_evidence_failure_projects_integrity_blocked(monkeypatch):
    item, _review, evidence = candidate()
    finalize(item, evidence)

    def blocked(*args, **kwargs):
        raise GovernanceEligibilityError(
            "EVIDENCE_INTEGRITY_NOT_VERIFIED:REVIEW_REQUIRED:HASH_MISMATCH")

    monkeypatch.setattr(
        "apps.intelligence.governance_projection.verify_governance_evidence", blocked)
    rebuild_governance_projections(apply=True)
    row = GovernanceDecisionProjection.objects.get()
    assert row.effective_state \
        == GovernanceDecisionProjection.EffectiveState.EVIDENCE_INTEGRITY_BLOCKED
    assert read_published_governance(item).state == "EVIDENCE_INTEGRITY_BLOCKED"
    no_allowed_permissions()


def test_unknown_governance_schema_fails_closed():
    item, _review, evidence = candidate()
    event, _pair, finalizer = finalize(item, evidence)
    payload = copy.deepcopy(event.payload)
    payload["governance_decision_schema"] = "intelligence_governance_decision/999"
    append_decision(
        user=finalizer, action=event.action,
        subject=(event.subject_type, event.subject_id), payload=payload)
    with pytest.raises(
            GovernanceProjectionVerificationError,
            match="UNSUPPORTED_GOVERNANCE_DECISION_SCHEMA"):
        build_governance_projection()


def test_tampered_chain_aborts_and_failed_generation_preserves_publication():
    item, _review, evidence = candidate()
    finalize(item, evidence)
    rebuild_governance_projections(apply=True)
    publication = GovernanceProjectionPublicationState.objects.get(pk=1)
    current_id = publication.current_generation_id
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE accounts_decisionevent SET hmac_signature=%s "
            "WHERE sequence_number=(SELECT max(sequence_number) "
            "FROM accounts_decisionevent)", ["0" * 64])
    with pytest.raises(
            GovernanceProjectionVerificationError, match="DECISION_CHAIN_INVALID"):
        rebuild_governance_projections(apply=True)
    publication.refresh_from_db()
    assert publication.current_generation_id == current_id
    assert GovernanceProjectionGeneration.objects.get(
        pk=current_id).status == GovernanceProjectionGeneration.Status.PUBLISHED
    assert GovernanceProjectionGeneration.objects.filter(
        status=GovernanceProjectionGeneration.Status.FAILED).count() == 1


def test_publication_failure_rolls_back_pointer(monkeypatch):
    item, _review, evidence = candidate()
    finalize(item, evidence)
    rebuild_governance_projections(apply=True)
    publication = GovernanceProjectionPublicationState.objects.get(pk=1)
    old_id = publication.current_generation_id
    original_save = GovernanceProjectionGeneration.save

    def fail_new_publish(instance, *args, **kwargs):
        if (instance.pk != old_id
                and instance.status == GovernanceProjectionGeneration.Status.PUBLISHED):
            raise GovernanceProjectionPublicationError("TEST_GOVERNANCE_PUBLICATION_FAILURE")
        return original_save(instance, *args, **kwargs)

    monkeypatch.setattr(GovernanceProjectionGeneration, "save", fail_new_publish)
    with pytest.raises(
            GovernanceProjectionPublicationError,
            match="TEST_GOVERNANCE_PUBLICATION_FAILURE"):
        rebuild_governance_projections(
            apply=True, evaluation_at=timezone.now() + timezone.timedelta(seconds=1))
    publication.refresh_from_db()
    assert publication.current_generation_id == old_id
    assert GovernanceProjectionGeneration.objects.get(
        pk=old_id).status == GovernanceProjectionGeneration.Status.PUBLISHED


def test_rebuild_is_deterministic_expected_head_protected_and_later_event_is_stale():
    item, _review, evidence = candidate()
    _event, _pair, finalizer = finalize(item, evidence)
    first = build_governance_projection()
    second = build_governance_projection(evaluation_at=first.evaluation_timestamp)
    assert first.output_hash == second.output_hash
    assert [row.logical_document() for row in first.rows] == [
        row.logical_document() for row in second.rows]
    rebuild_governance_projections(apply=True)
    generation_id = GovernanceProjectionPublicationState.objects.get(
        pk=1).current_generation_id
    append_decision(
        user=finalizer, action=authz.CONFIRM_BRAND_IDENTITY,
        subject=("CorpusItem", str(item.pk)), payload={"note": "later event"})
    assert read_published_governance(item).state == "STALE"
    with pytest.raises(
            GovernanceProjectionVerificationError,
            match="EXPECTED_CHAIN_HEAD_MISMATCH"):
        rebuild_governance_projections(
            apply=True, expected_chain_head="0" * 64)
    assert GovernanceProjectionPublicationState.objects.get(
        pk=1).current_generation_id == generation_id


def test_governance_final_never_creates_any_allowed_permission_projection():
    brand, _brand_review, brand_evidence = candidate()
    palette, _palette_review, palette_evidence = candidate(palette=True)
    finalize(brand, brand_evidence)
    finalize(palette, palette_evidence, palette=True)
    rebuild_governance_projections(apply=True)
    assert GovernanceDecisionProjection.objects.filter(
        effective_state=GovernanceDecisionProjection.EffectiveState.ACTIVE).count() == 2
    no_allowed_permissions()


def test_management_command_defaults_to_json_dry_run_and_apply_is_explicit():
    output = io.StringIO()
    call_command(
        "rebuild_intelligence_governance", "--json",
        "--evaluation-timestamp", GENESIS_EVALUATION_TIMESTAMP.isoformat(),
        "--expected-chain-head", "GENESIS", stdout=output)
    report = json.loads(output.getvalue())
    assert report["mode"] == "dry-run"
    assert GovernanceProjectionGeneration.objects.count() == 0
    output = io.StringIO()
    call_command(
        "rebuild_intelligence_governance", "--apply", "--json",
        "--evaluation-timestamp", GENESIS_EVALUATION_TIMESTAMP.isoformat(),
        "--expected-chain-head", "GENESIS", stdout=output)
    report = json.loads(output.getvalue())
    assert report["mode"] == "apply" and report["published"] is True
