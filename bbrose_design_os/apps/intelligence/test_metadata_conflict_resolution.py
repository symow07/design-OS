"""DIP-1C-5C-CORR-4 — resolving multiple active metadata events.

Supersession has a single parent. Correcting each duplicate separately leaves one active
correction per duplicate and resolves nothing, so a duplicate incident needs an event that
names the whole active set. These tests defend that the set-invalidation power is confined
to exactly that action and schema, and that a partial or padded set is refused.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.accounts.decision_chain import verify_chain
from apps.accounts.security import signing

from .human_semantic_metadata import RESOLUTION_SCHEMA
from .metadata_history import (
    EFFECTIVE, REVIEW_REQUIRED, resolve_effective_assertion_from_verified_history,
)
from .models import (
    EvidenceReference, GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection,
)
from .projection import rebuild_assertion_projections
from .review_services import AssertionValidationError, ReviewAuthorizationDenied
from .semantic_metadata_service import (
    REVIEW_SCOPE_ID, record_human_semantic_metadata,
    resolve_human_semantic_metadata_conflict,
)
from .test_human_semantic_metadata import _bundle, _candidate_for, _payload, _scoped_item

pytestmark = pytest.mark.django_db
User = get_user_model()
REASON = "DUPLICATE_ACTIVE_EVENTS_FROM_STALE_APPLICATION_PROCESS"
INCIDENT = "STALE_SERVER_DUPLICATE_RECORD_RECOVERY"
EXPLANATION = "Two identical records were appended by a stale server process."


@pytest.fixture(autouse=True)
def _signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"corr4": "6" * 32}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "corr4"
    signing.reset_registry()
    yield
    signing.reset_registry()


def _reviewer(role=authz.DESIGN_REVIEWER, username="corr4-reviewer"):
    granter = User.objects.create_user(username=f"{username}-granter")
    user = User.objects.create_user(username=username)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="CORR-4 test")
    return user


def _conflicted_item(key="asset:corr4-0001"):
    """The real incident shape: two identical active records, both citing the page unit.

    The second record is appended with the CORR-3 guard patched out, which is exactly what
    the stale server process did — it was running code that predated the guard.
    """
    from unittest import mock

    from .metadata_history import NONE, EffectiveAssertion

    item, source_ref = _scoped_item(key)
    unit = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source_ref.source_artifact,
        evidence_kind="FILE_PAGE_UNIT",
        locator={"page": 0, "unit_key": f"{key}-p0-u06"},
        locator_schema_version="file_page/1.0", evidence_hash="c6" * 32)
    candidate = _candidate_for(item)
    reviewer = _reviewer()
    evidence = [str(unit.pk)]
    first = record_human_semantic_metadata(
        user=reviewer, payload=_payload(item, unit, evidence_reference_ids=evidence))
    with mock.patch(
            "apps.intelligence.metadata_history."
            "resolve_effective_assertion_from_verified_history",
            lambda item: EffectiveAssertion(NONE, "NO_METADATA_EVENT")):
        second = record_human_semantic_metadata(
            user=reviewer, payload=_payload(item, unit, evidence_reference_ids=evidence))
    return item, source_ref, unit, candidate, reviewer, first, second


def _resolution_payload(item, source_ref, event_ids, **changes):
    payload = {
        "corpus_item_uuid": str(item.pk),
        "bundle": _bundle(),
        "evidence_reference_ids": [str(source_ref.pk)],
        "review_scope_id": REVIEW_SCOPE_ID,
        "resolved_event_ids": list(event_ids),
        "resolution_reason": REASON,
        "incident_type": INCIDENT,
        "reviewer_explanation": EXPLANATION,
    }
    payload.update(changes)
    return payload


def _authority():
    return (GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count())


# === the conflict state ==========================================================

def test_two_active_records_report_review_required():
    item, _, _, _, _, first, second = _conflicted_item()
    resolved = resolve_effective_assertion_from_verified_history(item)
    assert resolved.state == REVIEW_REQUIRED
    assert resolved.reason == "MULTIPLE_ACTIVE_METADATA_EVENTS"
    assert set(resolved.active_event_ids) == {first.event_id, second.event_id}


def test_no_ordinary_mutation_form_renders_and_the_resolution_form_does(client):
    item, source_ref, unit, candidate, reviewer, first, second = _conflicted_item()
    client.force_login(reviewer)
    body = client.get(reverse(
        "intelligence:review-detail", args=[candidate.pk])).content.decode()
    section = body.split("HUMAN SEARCH METADATA", 1)[1]
    assert "REVIEW_REQUIRED · MULTIPLE_ACTIVE_METADATA_EVENTS" in section
    assert "Record signed descriptive metadata" not in section
    assert "Correct signed descriptive metadata" not in section
    assert "RESOLVE DESCRIPTIVE METADATA CONFLICT" in section
    assert "THIS ACTION PRESERVES ALL PRIOR EVENTS AND CREATES ONE SIGNED EFFECTIVE " \
           "METADATA BUNDLE." in section
    assert "Resolve signed metadata conflict" in section
    # both active events displayed, with their evidence
    assert section.count("ACTIVE · sequence") == 2
    assert first.event_id in section and second.event_id in section
    assert "u06" in section
    # identical bundles are prefilled; evidence stays explicitly selectable
    assert "logically identical" in section
    assert '<option value="FLORAL" selected>' in section
    assert str(source_ref.pk) in section


def test_active_event_ids_are_signed_in_stable_sorted_order():
    item, source_ref, _, _, reviewer, first, second = _conflicted_item()
    event = resolve_human_semantic_metadata_conflict(
        user=reviewer, payload=_resolution_payload(
            item, source_ref, [second.event_id, first.event_id]))   # unsorted input
    assert event.payload["resolved_event_ids"] == sorted(
        [first.event_id, second.event_id])
    assert event.payload["resolved_event_sequence_numbers"] == sorted(
        [DecisionEvent.objects.get(event_id=first.event_id).sequence_number,
         DecisionEvent.objects.get(event_id=second.event_id).sequence_number])


# === the resolution ==============================================================

def test_resolution_produces_exactly_one_effective_bundle_and_preserves_history():
    item, source_ref, unit, _, reviewer, first, second = _conflicted_item()
    event = resolve_human_semantic_metadata_conflict(
        user=reviewer, payload=_resolution_payload(
            item, source_ref, [first.event_id, second.event_id]))

    assert event.action == authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT
    assert event.payload["resolution_schema"] == RESOLUTION_SCHEMA
    assert event.role_used == authz.DESIGN_REVIEWER
    assert event.payload["final_evidence_reference_ids"] == [str(source_ref.pk)]
    assert set(event.payload["prior_bundle_hashes"]) == {
        first.event_id, second.event_id}
    assert verify_chain().ok

    resolved = resolve_effective_assertion_from_verified_history(item)
    assert resolved.state == EFFECTIVE
    assert resolved.event.event_id == event.event_id
    assert set(resolved.superseded_event_ids) == {first.event_id, second.event_id}
    # originals preserved, not deleted, and u06 survives only there
    for original in (first, second):
        assert DecisionEvent.objects.filter(event_id=original.event_id).exists()
        assert str(unit.pk) in str(
            DecisionEvent.objects.get(event_id=original.event_id).payload)
    assert str(unit.pk) not in str(event.payload)
    assert _authority() == (0, 0)


def test_the_projection_publishes_one_effective_row_with_the_final_evidence():
    item, source_ref, unit, _, reviewer, first, second = _conflicted_item()
    resolution = resolve_human_semantic_metadata_conflict(
        user=reviewer, payload=_resolution_payload(
            item, source_ref, [first.event_id, second.event_id]))
    rebuild_assertion_projections(apply=True)

    rows = HumanAssertionProjection.objects.filter(
        corpus_item=item, assertion_domain="human_semantic_metadata")
    assert rows.count() == 1
    row = rows.get()
    assert row.effective_state == HumanAssertionProjection.EffectiveState.ASSERTED
    assert row.source_decision_event.event_id == resolution.event_id
    cited = [entry["evidence_reference_id"]
             for entry in row.projection_metadata["evidence_sources"]]
    assert cited == [str(source_ref.pk)]
    assert str(unit.pk) not in str(cited)
    history = row.projection_metadata["history_event_ids"]
    assert first.event_id in history and second.event_id in history
    assert set(row.projection_metadata["superseded_event_ids"]) == {
        first.event_id, second.event_id}
    assert _authority() == (0, 0)


# === refusals ====================================================================

def test_a_partial_or_padded_active_set_is_refused():
    item, source_ref, _, _, reviewer, first, second = _conflicted_item()
    other_item, other_ref = _scoped_item("asset:corr4-0002")
    unrelated = record_human_semantic_metadata(user=reviewer, payload=_payload(
        other_item, other_ref, evidence_reference_ids=[str(other_ref.pk)]))
    before = DecisionEvent.objects.count()

    for event_ids in ([first.event_id],                              # partial
                      [first.event_id, second.event_id, unrelated.event_id],  # padded
                      [first.event_id, first.event_id]):             # duplicated
        with pytest.raises(AssertionValidationError):
            resolve_human_semantic_metadata_conflict(
                user=reviewer, payload=_resolution_payload(item, source_ref, event_ids))
    with pytest.raises(AssertionValidationError):
        resolve_human_semantic_metadata_conflict(
            user=reviewer, payload=_resolution_payload(item, source_ref, []))
    assert DecisionEvent.objects.count() == before


def test_cross_item_evidence_and_already_resolved_events_are_refused():
    item, source_ref, _, _, reviewer, first, second = _conflicted_item()
    _, other_ref = _scoped_item("asset:corr4-0003")
    with pytest.raises(AssertionValidationError):
        resolve_human_semantic_metadata_conflict(
            user=reviewer, payload=_resolution_payload(
                item, source_ref, [first.event_id, second.event_id],
                evidence_reference_ids=[str(other_ref.pk)]))
    resolve_human_semantic_metadata_conflict(
        user=reviewer, payload=_resolution_payload(
            item, source_ref, [first.event_id, second.event_id]))
    before = DecisionEvent.objects.count()
    with pytest.raises(AssertionValidationError):      # nothing left to resolve
        resolve_human_semantic_metadata_conflict(
            user=reviewer, payload=_resolution_payload(
                item, source_ref, [first.event_id, second.event_id]))
    assert DecisionEvent.objects.count() == before


def test_invalid_reason_incident_or_missing_explanation_is_refused():
    item, source_ref, _, _, reviewer, first, second = _conflicted_item()
    ids = [first.event_id, second.event_id]
    for changes in ({"resolution_reason": "BECAUSE_I_SAID_SO"},
                    {"incident_type": "WHATEVER"},
                    {"reviewer_explanation": "   "},
                    {"reviewer_explanation": "x" * 2001},
                    {"review_scope_id": "other/1.0"}):
        with pytest.raises(AssertionValidationError):
            resolve_human_semantic_metadata_conflict(
                user=reviewer, payload=_resolution_payload(
                    item, source_ref, ids, **changes))


def test_system_admin_cannot_resolve_and_the_caller_cannot_supply_derived_fields():
    item, source_ref, _, _, _, first, second = _conflicted_item()
    admin = _reviewer(role=authz.SYSTEM_ADMIN, username="corr4-admin")
    ids = [first.event_id, second.event_id]
    with pytest.raises(ReviewAuthorizationDenied):
        resolve_human_semantic_metadata_conflict(
            user=admin, payload=_resolution_payload(item, source_ref, ids))
    reviewer = _reviewer(username="corr4-second")
    with pytest.raises(AssertionValidationError):
        resolve_human_semantic_metadata_conflict(
            user=reviewer, payload=_resolution_payload(
                item, source_ref, ids, role_used=authz.BRAND_ADMIN))
    assert not DecisionEvent.objects.filter(
        action=authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT).exists()


def test_ordinary_record_and_correction_remain_refused_while_ambiguous():
    item, source_ref, unit, candidate, reviewer, first, second = _conflicted_item()
    from .semantic_metadata_service import correct_human_semantic_metadata
    before = DecisionEvent.objects.count()
    with pytest.raises(AssertionValidationError):
        record_human_semantic_metadata(user=reviewer, payload=_payload(
            item, source_ref, evidence_reference_ids=[str(source_ref.pk)]))
    with pytest.raises(AssertionValidationError):
        correct_human_semantic_metadata(user=reviewer, payload=_payload(
            item, source_ref, evidence_reference_ids=[str(source_ref.pk)],
            supersedes_event_id=first.event_id))
    assert DecisionEvent.objects.count() == before

    client_before = DecisionEvent.objects.count()
    from django.test import Client
    client = Client()
    client.force_login(reviewer)
    response = client.post(
        reverse("intelligence:review-record-semantic-metadata", args=[candidate.pk]),
        {"review_scope_id": REVIEW_SCOPE_ID, "metadata_design_styles": ["MINIMAL"],
         "evidence_reference_ids": [str(source_ref.pk)]})
    assert response.status_code == 400
    assert DecisionEvent.objects.count() == client_before


def test_endpoint_enforces_post_authorization_and_csrf(client):
    item, source_ref, _, candidate, reviewer, first, second = _conflicted_item()
    url = reverse("intelligence:review-resolve-semantic-metadata-conflict",
                  args=[candidate.pk])
    assert client.post(url, {}).status_code == 403          # unauthenticated
    client.force_login(reviewer)
    assert client.get(url).status_code == 405               # POST only
    from django.test import Client
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(reviewer)
    assert csrf_client.post(url, {}).status_code == 403     # CSRF enforced
    assert not DecisionEvent.objects.filter(
        action=authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT).exists()


def test_no_path_like_or_authority_claim_can_enter_the_resolution():
    item, source_ref, _, _, reviewer, first, second = _conflicted_item()
    ids = [first.event_id, second.event_id]
    for bad in ({"search_synonyms": ["materials/secret/design.ai"]},
                {"brand_observations": ["OFFICIAL_LOGO"]},
                {"design_styles": ["NOT_A_REAL_STYLE"]}):
        with pytest.raises(AssertionValidationError):
            resolve_human_semantic_metadata_conflict(
                user=reviewer, payload=_resolution_payload(
                    item, source_ref, ids, bundle=_bundle(**bad)))
