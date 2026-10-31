"""DIP-1C-5C — pilot scope and operational preflight.

Both are pure reads. The tests that matter most here are the negative ones: selecting a
pilot and inspecting the environment must not create authority state, must not configure
signing, and must never surface a key value.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)

from .models import (
    CorpusItem, GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection, ReviewCandidate,
)
from .semantic_metadata_pilot import (
    EXPECTED_DOMAINS, PILOT_SCHEMA, PROHIBITED_CONCLUSIONS, TARGET, build_pilot_document,
    is_in_pilot, pilot_hash,
)
from .semantic_metadata_preflight import build_preflight
from .semantic_metadata_scope import scope_item_ids
from .test_human_semantic_metadata import _candidate_for, _scoped_item

pytestmark = pytest.mark.django_db
User = get_user_model()


def _authority_counts():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count())


def _pilot_ready_item(external_key):
    item, evidence = _scoped_item(external_key)
    _candidate_for(item)
    return item, evidence


# --- scope ------------------------------------------------------------------------

def test_pilot_document_is_deterministic_and_hash_stable():
    _pilot_ready_item("asset:pilot-0001")
    first, second = build_pilot_document(), build_pilot_document()
    assert first == second
    assert pilot_hash(first) == pilot_hash(second) == pilot_hash()
    assert first["schema_version"] == PILOT_SCHEMA
    assert first["target"] == TARGET


def test_pilot_is_a_strict_subset_of_the_accepted_review_scope():
    for index in range(3):
        _pilot_ready_item(f"asset:pilot-100{index}")
    document = build_pilot_document()
    ids = {entry["corpus_item_id"] for entry in document["entries"]}
    assert ids and ids <= scope_item_ids()
    for entry in document["entries"]:
        assert len(entry["expected_descriptor_domains"]) > 0
        assert entry["expected_descriptor_domains"] == list(
            EXPECTED_DOMAINS[entry["segment"]])
        assert entry["prohibited_conclusions"] == list(PROHIBITED_CONCLUSIONS)
        assert entry["selection_reason"] and entry["required_reviewer_role"]


def test_pilot_excludes_items_a_reviewer_could_not_complete():
    """No evidence, or no review candidate, means no usable review — such an item must not
    reach a reviewer's list."""
    reachable, _ = _pilot_ready_item("asset:pilot-2001")
    no_candidate, _ = _scoped_item("asset:pilot-2002")        # evidence, but no candidate
    document = build_pilot_document()
    ids = {entry["corpus_item_id"] for entry in document["entries"]}
    assert str(reachable.pk) in ids
    assert str(no_candidate.pk) not in ids
    assert is_in_pilot(reachable) and not is_in_pilot(no_candidate)
    for entry in document["entries"]:
        assert entry["review_candidate_id"]


def test_a_short_segment_is_reported_not_padded_from_elsewhere():
    _pilot_ready_item("asset:pilot-3001")
    document = build_pilot_document()
    for segment, count in document["segment_counts"].items():
        assert count <= TARGET[segment]
        if count < TARGET[segment]:
            assert document["unfilled_segments"][segment] == TARGET[segment] - count
    assert document["actual_total"] == sum(document["segment_counts"].values())


def test_building_the_pilot_creates_nothing_and_grants_nothing():
    _pilot_ready_item("asset:pilot-4001")
    before = (CorpusItem.objects.count(), ReviewCandidate.objects.count(),
              _authority_counts())
    build_pilot_document()
    pilot_hash()
    assert (CorpusItem.objects.count(), ReviewCandidate.objects.count(),
            _authority_counts()) == before


# --- preflight --------------------------------------------------------------------

def test_preflight_is_read_only_and_never_reveals_key_material(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"pilot-test": "9" * 32}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "pilot-test"
    _pilot_ready_item("asset:pilot-5001")
    before = _authority_counts()
    report = build_preflight()

    assert report["signing"]["keys_configured"] is True
    assert report["signing"]["key_count"] == 1
    serialized = repr(report)
    assert "9" * 32 not in serialized          # no key value, anywhere in the report
    assert "pilot-test" not in serialized      # not even the active key id
    assert _authority_counts() == before


def test_preflight_reports_missing_signing_and_missing_reviewer_as_blocking(settings):
    settings.DECISION_EVENT_HMAC_KEYS = ""
    settings.DECISION_EVENT_ACTIVE_KEY_ID = ""
    _pilot_ready_item("asset:pilot-6001")
    report = build_preflight()
    assert report["signing"]["registry_resolves"] is False
    assert "NO_USABLE_DECISION_EVENT_SIGNING_KEY" in report["blocking_conditions"]
    assert "NO_REVIEWER_AUTHORIZED_FOR_SEMANTIC_METADATA" in (
        report["blocking_conditions"])
    assert report["reviewers"]["metadata_eligible_count"] == 0
    assert report["authority_counts"]["decision_events"] == 0


def test_preflight_recognizes_an_eligible_reviewer_without_creating_one(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"pilot-test": "9" * 32}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "pilot-test"
    _pilot_ready_item("asset:pilot-7001")
    granter = User.objects.create_user(username="pilot-granter")
    user = User.objects.create_user(username="pilot-reviewer")
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=authz.DESIGN_REVIEWER, granted_by=granter,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="preflight fixture")
    before = _authority_counts()

    report = build_preflight()
    assert report["reviewers"]["metadata_eligible_count"] == 1
    assert report["reviewers"]["metadata_eligible_reviewers"][0]["role"] == (
        authz.DESIGN_REVIEWER)
    assert "NO_REVIEWER_AUTHORIZED_FOR_SEMANTIC_METADATA" not in (
        report["blocking_conditions"])
    assert _authority_counts() == before


def test_preflight_ignores_a_reviewer_whose_role_cannot_record_metadata(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"pilot-test": "9" * 32}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "pilot-test"
    _pilot_ready_item("asset:pilot-8001")
    granter = User.objects.create_user(username="observer-granter")
    for role in (authz.OBSERVER, authz.SYSTEM_ADMIN):
        user = User.objects.create_user(username=f"user-{role}")
        ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
        ReviewerRoleAssignment.objects.create(
            user=user, role=role, granted_by=granter, granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=1),
            grant_source=GRANT_TEST_FIXTURE, grant_reason="preflight fixture")
    report = build_preflight()
    assert report["reviewers"]["metadata_eligible_count"] == 0
    assert "NO_REVIEWER_AUTHORIZED_FOR_SEMANTIC_METADATA" in (
        report["blocking_conditions"])
