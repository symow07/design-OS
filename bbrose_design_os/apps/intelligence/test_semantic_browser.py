"""Semantic search UI + rebuild command — DIP-1C-1.

The browser surface must stay authorized-only and GET-only, never trigger an external call,
label lexical fallback honestly, and never present lexical results as semantic. The rebuild
command must be dry-run by default and fail closed before any external transfer.
"""
from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    GRANT_TEST_FIXTURE, DecisionEvent, ReviewerProfile, ReviewerRoleAssignment,
)

from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import SemanticDocumentEmbedding, SemanticIndexGeneration
from .test_review_campaign import asset

pytestmark = pytest.mark.django_db
_seq = 0


def _reviewer(*, role=authz.DESIGN_REVIEWER, enabled=True, active=True):
    global _seq
    _seq += 1
    User = get_user_model()
    granter = User.objects.create_user(username=f"sem-granter-{_seq}")
    user = User.objects.create_user(username=f"sem-reviewer-{_seq}", is_active=active)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=enabled)
    ReviewerRoleAssignment.objects.create(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="semantic browser fixture")
    return user


# === browser ====================================================================
def test_search_page_states_semantic_is_not_authorization(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    body = client.get(reverse("intelligence:search")).content.decode()
    assert "SEMANTIC SIMILARITY DOES NOT AUTHORIZE OPERATIONAL USE." in body


def test_semantic_request_with_no_index_is_labelled_lexical_only(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    response = client.get(reverse("intelligence:search"),
                          {"query": "asset", "ranking": "HYBRID"})
    assert response.status_code == 200
    assert response.context["search"]["result_label"] == "LEXICAL_ONLY"
    assert response.context["search"]["ranking_is_semantic"] is False
    assert b"LEXICAL_ONLY" in response.content


def test_search_get_writes_nothing_and_calls_nothing_external(client):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    client.force_login(_reviewer())
    before = (DecisionEvent.objects.count(),
              SemanticIndexGeneration.objects.count(),
              SemanticDocumentEmbedding.objects.count())
    client.get(reverse("intelligence:search"), {"query": "asset", "ranking": "SEMANTIC"})
    assert (DecisionEvent.objects.count(),
            SemanticIndexGeneration.objects.count(),
            SemanticDocumentEmbedding.objects.count()) == before


def test_unknown_ranking_is_refused(client):
    client.force_login(_reviewer())
    assert client.get(reverse("intelligence:search"),
                      {"ranking": "MAGIC"}).status_code == 400


def test_unauthenticated_is_denied(client):
    assert client.get(reverse("intelligence:search")).status_code == 403


# === rebuild command ============================================================
def test_dry_run_writes_nothing_and_says_so():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    out = StringIO()
    call_command("rebuild_intelligence_semantic_index", "--json", stdout=out)
    assert SemanticIndexGeneration.objects.count() == 0     # nothing written
    assert "DRY RUN" in out.getvalue()
    assert "no data was sent" in out.getvalue()


def test_openai_apply_without_confirmation_fails_closed():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    with pytest.raises(CommandError):
        call_command("rebuild_intelligence_semantic_index",
                     "--apply", "--provider", "openai")
    assert SemanticIndexGeneration.objects.count() == 0


def test_stub_apply_builds_a_test_encoder_generation():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    out = StringIO()
    call_command("rebuild_intelligence_semantic_index", "--apply",
                 "--provider", "stub", "--json", stdout=out)
    gen = SemanticIndexGeneration.objects.get()
    assert gen.is_test_encoder is True
    assert gen.status == SemanticIndexGeneration.Status.BUILT


def test_command_output_never_contains_a_key(settings):
    settings.OPENAI_API_KEY = "sk-should-never-appear-in-output"
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    out = StringIO()
    call_command("rebuild_intelligence_semantic_index", "--json", stdout=out)
    assert "sk-should-never-appear" not in out.getvalue()
