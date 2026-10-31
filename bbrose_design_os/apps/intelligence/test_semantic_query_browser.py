"""Interactive semantic search over HTTP — DIP-1C-2.

Defends the seam that matters most: a GET can never cause an outbound call, a POST needs
authorization + CSRF + explicit per-request consent, and semantic similarity never bypasses
the permission gate. No test contacts OpenAI.
"""
from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    GRANT_TEST_FIXTURE, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
)

from . import semantic_query as SQ
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection, SemanticIndexGeneration,
)
from .test_review_campaign import asset, brand
from .test_semantic_query import _MockOpenAIEncoder, _publish_openai_index

pytestmark = pytest.mark.django_db
_seq = 0

URL = "intelligence:semantic-search"


def _reviewer(*, role=authz.DESIGN_REVIEWER, enabled=True, active=True):
    global _seq
    _seq += 1
    User = get_user_model()
    granter = User.objects.create_user(username=f"sq-granter-{_seq}")
    user = User.objects.create_user(username=f"sq-reviewer-{_seq}", is_active=active)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="semantic query fixture")
    return user


def _authority_counts():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count())


def _post(client, **over):
    data = {"query_text": "luxury floral cosmetic packaging", "ranking": "SEMANTIC",
            "confirm_external_query_transfer": "true"}
    data.update(over)
    return client.post(reverse(URL), data)


# === authorization + HTTP method =================================================
def test_unauthenticated_inactive_disabled_and_unauthorized_are_denied(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    assert _post(client).status_code == 403
    for user in (_reviewer(active=False), _reviewer(enabled=False),
                 _reviewer(role=authz.OBSERVER)):
        client.force_login(user)
        assert _post(client).status_code == 403
        client.logout()


def test_semantic_endpoint_is_post_only(client):
    client.force_login(_reviewer())
    assert client.get(reverse(URL)).status_code == 405


def test_csrf_is_enforced():
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(_reviewer())
    response = csrf_client.post(reverse(URL), {"query_text": "x", "ranking": "SEMANTIC",
                                               "confirm_external_query_transfer": "true"})
    assert response.status_code == 403          # no CSRF token -> refused


def test_lexical_get_still_works_and_never_calls_the_provider(client, settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    client.force_login(_reviewer())
    with mock.patch.object(SQ, "get_encoder") as ge:
        response = client.get(reverse("intelligence:search"), {"query": "asset"})
    assert response.status_code == 200
    ge.assert_not_called()                      # a GET never embeds anything


def test_request_body_cannot_supply_actor_or_role(client, settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    client.force_login(_reviewer(role=authz.OBSERVER))     # unauthorized role
    # claiming a privileged role in the body must not help
    response = _post(client, role=authz.SYSTEM_ADMIN, user="admin", actor="admin")
    assert response.status_code == 403


# === consent over HTTP ===========================================================
def test_unchecked_confirmation_prevents_the_external_call(client, settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    client.force_login(_reviewer())
    with mock.patch.object(SQ, "get_encoder") as ge:
        response = client.post(reverse(URL), {"query_text": "floral",
                                              "ranking": "SEMANTIC"})
    assert response.status_code == 200
    assert response.context["semantic_failure_code"] == SQ.EXTERNAL_TRANSFER_NOT_CONFIRMED
    ge.assert_not_called()


def test_confirmed_post_runs_semantic_search(client, settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    client.force_login(_reviewer())
    with mock.patch.object(
            SQ, "get_encoder",
            return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        response = _post(client)
    assert response.status_code == 200
    assert not response.context["semantic_failure_code"]
    search = response.context["search"]
    assert search["ranking_is_semantic"] is True
    assert search["ranking_engaged"] == "SEMANTIC"


# === semantic never bypasses the permission gate (POST path) =====================
def test_semantic_post_never_makes_a_denied_item_retrievable(client, settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    _publish_openai_index(settings)
    client.force_login(_reviewer())
    with mock.patch.object(
            SQ, "get_encoder",
            return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        reviewer = _post(client, ranking="HYBRID")
    results = reviewer.context["search"]["results"]
    assert results
    assert all(r["retrieval"]["allowed"] is False for r in results)
    assert all(r["automatic_use"]["allowed"] is False for r in results)


def test_semantic_only_ordering_excludes_lexical_weight(client, settings):
    """Ranker 1.1: SEMANTIC orders on the semantic score alone; the lexical score is a
    diagnostic only."""
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    client.force_login(_reviewer())
    with mock.patch.object(
            SQ, "get_encoder",
            return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        response = _post(client, ranking="SEMANTIC")
    row = response.context["search"]["results"][0]
    assert row["semantic_score"] is not None
    assert "lexical_score" in row and "final_hybrid_score" in row
    # ordering value is a pure function of the semantic score in SEMANTIC mode
    from .hybrid_ranker import _SEMANTIC_WEIGHT
    assert row["final_hybrid_score"] == pytest.approx(
        _SEMANTIC_WEIGHT * row["semantic_score"])


def test_repeated_query_is_deterministic(client, settings):
    for _ in range(3):
        asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    client.force_login(_reviewer())
    with mock.patch.object(
            SQ, "get_encoder",
            return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        a = _post(client).context["search"]["results"]
        b = _post(client).context["search"]["results"]
    assert [r["corpus_item_id"] for r in a] == [r["corpus_item_id"] for r in b]


# === failure surfacing ===========================================================
def test_unavailable_index_shows_precise_cause_and_keeps_lexical(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    response = _post(client)
    assert response.context["semantic_failure_code"] == SQ.SEMANTIC_INDEX_UNAVAILABLE
    assert response.context["search"] is None       # no lexical dressed as semantic
    # lexical search still works
    assert client.get(reverse("intelligence:search"),
                      {"query": "asset"}).status_code == 200


def test_stale_index_fails_closed_over_http(client, settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    brand()                                         # corpus drifts
    client.force_login(_reviewer())
    with mock.patch.object(SQ, "get_encoder") as ge:
        response = _post(client)
    assert response.context["semantic_failure_code"] == SQ.SEMANTIC_INDEX_STALE
    ge.assert_not_called()


def test_bad_ranking_is_refused(client):
    client.force_login(_reviewer())
    assert _post(client, ranking="LEXICAL").status_code == 400
    assert _post(client, ranking="MAGIC").status_code == 400


# === read-only ===================================================================
def test_semantic_post_writes_no_authority_and_no_history(client, settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    client.force_login(_reviewer())
    before = _authority_counts()
    generations_before = SemanticIndexGeneration.objects.count()
    with mock.patch.object(
            SQ, "get_encoder",
            return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        _post(client)
    assert _authority_counts() == before
    assert SemanticIndexGeneration.objects.count() == generations_before
