"""DIP-1C-5C-CORR-3 — correction must be reachable from verified signed history.

The defect was a read-model dependency in a write path: the correction form was gated on the
published projection, so a stale projection made an existing signed event uncorrectable and
silently offered the record form instead — which would have appended a second active bundle
rather than a supersession. The signed chain, not the projection, is the authority on what
exists.
"""
from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.accounts.security import signing

from .metadata_history import (
    EFFECTIVE, INVALID, NONE, REVIEW_REQUIRED,
    resolve_effective_assertion_from_verified_history,
)
from .models import (
    EvidenceReference, GovernanceDecisionProjection,
    OperationalPermissionProjection,
)
from .review_services import AssertionValidationError
from .semantic_metadata_service import (
    REVIEW_SCOPE_ID, correct_human_semantic_metadata, record_human_semantic_metadata,
)
from .test_human_semantic_metadata import _bundle, _candidate_for, _payload, _scoped_item

pytestmark = pytest.mark.django_db
User = get_user_model()
KEY = "3" * 32


@pytest.fixture(autouse=True)
def _signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"corr3": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "corr3"
    signing.reset_registry()
    yield
    signing.reset_registry()


def _reviewer(username="corr3-reviewer"):
    granter = User.objects.create_user(username=f"{username}-granter")
    user = User.objects.create_user(username=username)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=authz.DESIGN_REVIEWER, granted_by=granter,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="CORR-3 test")
    return user


def _item_with_source_and_unit(external_key="asset:corr3-0001"):
    """Item-1 shape: one SOURCE_FILE plus one page unit, so the correction can move the
    citation from one to the other exactly as the real case did."""
    item, source_ref = _scoped_item(external_key)
    unit = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=source_ref.source_artifact,
        evidence_kind="FILE_PAGE_UNIT",
        locator={"page": 0, "unit_key": f"{external_key}-p0-u06"},
        locator_schema_version="file_page/1.0", evidence_hash="c6" * 32)
    candidate = _candidate_for(item)
    return item, source_ref, unit, candidate


def _authority():
    return (GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count())


# === the resolver ================================================================

def test_resolver_reports_none_then_effective_then_follows_supersession():
    item, source_ref, unit, _ = _item_with_source_and_unit()
    reviewer = _reviewer()
    assert resolve_effective_assertion_from_verified_history(item).state == NONE

    first = record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    resolved = resolve_effective_assertion_from_verified_history(item)
    assert resolved.state == EFFECTIVE
    assert resolved.event.event_id == first.event_id
    assert resolved.reason == "RESOLVED_FROM_VERIFIED_EVENT_HISTORY"

    second = correct_human_semantic_metadata(user=reviewer, payload=_payload(
        item, source_ref, evidence_reference_ids=[str(source_ref.pk)],
        supersedes_event_id=first.event_id))
    resolved = resolve_effective_assertion_from_verified_history(item)
    assert resolved.state == EFFECTIVE
    assert resolved.event.event_id == second.event_id, "supersession was not applied"
    assert first.event_id in resolved.superseded_event_ids
    assert len(resolved.history) == 2, "the superseded event was dropped from history"


def test_resolver_ignores_events_about_another_item():
    item, _, unit, _ = _item_with_source_and_unit()
    other_item, other_ref = _scoped_item("asset:corr3-0002")
    reviewer = _reviewer()
    record_human_semantic_metadata(user=reviewer, payload=_payload(
        other_item, other_ref, evidence_reference_ids=[str(other_ref.pk)]))
    assert resolve_effective_assertion_from_verified_history(item).state == NONE
    assert resolve_effective_assertion_from_verified_history(other_item).state == EFFECTIVE


def test_resolver_refuses_on_an_invalid_chain(settings):
    item, _, unit, _ = _item_with_source_and_unit()
    record_human_semantic_metadata(user=_reviewer(), payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    settings.DECISION_EVENT_HMAC_KEYS = {"corr3": "9" * 32}   # key rotated away
    signing.reset_registry()
    resolved = resolve_effective_assertion_from_verified_history(item)
    assert resolved.state == INVALID
    assert resolved.event is None


# === form behaviour with a stale projection ======================================

def _metadata_section(client, candidate):
    body = client.get(reverse(
        "intelligence:review-detail", args=[candidate.pk])).content.decode()
    return body.split("HUMAN SEARCH METADATA", 1)[1]


def test_stale_projection_still_offers_the_correction_form_prefilled(client):
    item, source_ref, unit, candidate = _item_with_source_and_unit()
    reviewer = _reviewer()
    original = record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, bundle=_bundle(motifs=["FLORAL"]),
        evidence_reference_ids=[str(unit.pk)]))
    # deliberately NOT rebuilding the projection: this is the stale state
    from .projection_reader import read_published_assertions
    assert read_published_assertions(item).state != "CURRENT"

    client.force_login(reviewer)
    section = _metadata_section(client, candidate)
    form = section.split("</form>", 1)[0]

    assert "PROJECTION IS STALE. THIS CORRECTION TARGET IS RESOLVED FROM VERIFIED " \
           "SIGNED EVENT HISTORY." in section
    # the record URL is a string PREFIX of the correction URL, so compare the action
    # attribute exactly rather than by substring
    action = re.search(r'<form method="post" action="([^"]+)"', form).group(1)
    assert action == reverse("intelligence:review-correct-semantic-metadata",
                             args=[candidate.pk])
    assert action != reverse("intelligence:review-record-semantic-metadata",
                             args=[candidate.pk])
    assert f'name="supersedes_event_id" value="{original.event_id}"' in form
    assert "Correct signed descriptive metadata" in form
    assert "Record signed descriptive metadata" not in form
    # prefilled from the prior bundle
    assert '<option value="FLORAL" selected>' in form
    assert "Soft floral packaging observed" in form            # reviewer notes
    assert "rose gold carton" in form                          # synonyms
    # the prior event's evidence is preselected, and only that
    checked = re.findall(r'name="evidence_reference_ids" value="([^"]+)" checked>', form)
    assert checked == [str(unit.pk)]
    assert str(source_ref.pk) in form                          # available as a distinct row


def test_ambiguous_history_offers_no_mutation_form(client, monkeypatch):
    item, _, unit, candidate = _item_with_source_and_unit()
    reviewer = _reviewer()
    record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    from . import metadata_history, views
    ambiguous = metadata_history.EffectiveAssertion(
        REVIEW_REQUIRED, "MULTIPLE_ACTIVE_METADATA_EVENTS")
    monkeypatch.setattr(
        views, "resolve_effective_assertion_from_verified_history", lambda item: ambiguous)
    client.force_login(reviewer)
    section = _metadata_section(client, candidate)
    assert "REVIEW_REQUIRED · MULTIPLE_ACTIVE_METADATA_EVENTS" in section
    assert "<form" not in section.split("IMMUTABLE DESCRIPTIVE METADATA HISTORY")[0]
    assert "Record signed descriptive metadata" not in section
    assert "Correct signed descriptive metadata" not in section


# === server-side enforcement =====================================================

def test_a_direct_record_post_is_refused_once_an_event_is_effective(client):
    item, source_ref, unit, candidate = _item_with_source_and_unit()
    reviewer = _reviewer()
    record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    before = DecisionEvent.objects.count()

    # the template no longer offers it; a crafted POST must still be refused
    client.force_login(reviewer)
    response = client.post(
        reverse("intelligence:review-record-semantic-metadata", args=[candidate.pk]),
        {"review_scope_id": REVIEW_SCOPE_ID, "metadata_design_styles": ["MINIMAL"],
         "evidence_reference_ids": [str(source_ref.pk)]})
    assert response.status_code == 400
    assert b"EXISTING_METADATA_EVENT_REQUIRES_CORRECTION" in response.content
    assert DecisionEvent.objects.count() == before

    with pytest.raises(AssertionValidationError) as exc:
        record_human_semantic_metadata(user=reviewer, payload=_payload(
            item, source_ref, evidence_reference_ids=[str(source_ref.pk)]))
    assert "EXISTING_METADATA_EVENT_REQUIRES_CORRECTION" in str(exc.value)


def test_correction_succeeds_without_rebuilding_the_projection(client):
    item, source_ref, unit, candidate = _item_with_source_and_unit()
    reviewer = _reviewer()
    original = record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    from .models import HumanAssertionProjection
    assert HumanAssertionProjection.objects.count() == 0      # never rebuilt

    client.force_login(reviewer)
    response = client.post(
        reverse("intelligence:review-correct-semantic-metadata", args=[candidate.pk]),
        {"review_scope_id": REVIEW_SCOPE_ID,
         "supersedes_event_id": original.event_id,
         "metadata_design_styles": ["MINIMAL"],
         "evidence_reference_ids": [str(source_ref.pk)]})
    assert response.status_code == 302, response.content[:300]
    correction = DecisionEvent.objects.order_by("sequence_number").last()
    assert correction.action == authz.CORRECT_HUMAN_SEMANTIC_METADATA
    assert correction.supersedes_event_id == DecisionEvent.objects.get(
        event_id=original.event_id).pk
    assert correction.payload["evidence_reference_ids"] == [str(source_ref.pk)]
    assert str(unit.pk) not in str(correction.payload)
    assert DecisionEvent.objects.filter(event_id=original.event_id).exists()
    assert _authority() == (0, 0)


def test_a_second_correction_of_an_already_superseded_event_fails_closed():
    item, source_ref, unit, _ = _item_with_source_and_unit()
    reviewer = _reviewer()
    original = record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    correct_human_semantic_metadata(user=reviewer, payload=_payload(
        item, source_ref, evidence_reference_ids=[str(source_ref.pk)],
        supersedes_event_id=original.event_id))
    before = DecisionEvent.objects.count()
    with pytest.raises(AssertionValidationError) as exc:
        correct_human_semantic_metadata(user=reviewer, payload=_payload(
            item, source_ref, evidence_reference_ids=[str(source_ref.pk)],
            supersedes_event_id=original.event_id))
    assert "SUPERSESSION_TARGET_ALREADY_SUPERSEDED" in str(exc.value)
    assert DecisionEvent.objects.count() == before
    assert resolve_effective_assertion_from_verified_history(item).state == EFFECTIVE


def test_get_writes_nothing_and_authorization_is_enforced(client):
    item, _, unit, candidate = _item_with_source_and_unit()
    reviewer = _reviewer()
    record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    before = (DecisionEvent.objects.count(), _authority())
    url = reverse("intelligence:review-detail", args=[candidate.pk])
    assert client.get(url).status_code == 403                 # unauthenticated
    client.force_login(reviewer)
    assert client.get(url).status_code == 200
    assert (DecisionEvent.objects.count(), _authority()) == before
    # correction endpoint keeps POST-only + CSRF enforcement
    assert client.get(reverse("intelligence:review-correct-semantic-metadata",
                              args=[candidate.pk])).status_code == 405


def test_the_current_projection_flow_is_unchanged(client):
    """When the projection IS current, the target comes from it and nothing is labelled as
    history-resolved."""
    from .projection import rebuild_assertion_projections
    item, source_ref, unit, candidate = _item_with_source_and_unit()
    reviewer = _reviewer()
    original = record_human_semantic_metadata(user=reviewer, payload=_payload(
        item, unit, evidence_reference_ids=[str(unit.pk)]))
    rebuild_assertion_projections(apply=True)
    client.force_login(reviewer)
    section = _metadata_section(client, candidate)
    assert "PROJECTION IS STALE" not in section
    assert "CURRENT DESCRIPTIVE METADATA" in section
    form = section.split("</form>", 1)[0]
    assert f'name="supersedes_event_id" value="{original.event_id}"' in form
    assert "Correct signed descriptive metadata" in form
