"""Index lifecycle + hybrid search — DIP-1C-1.

The claims that matter most: building writes only index tables and zero authority rows; a
test-encoder generation can never publish; a failed build never replaces a published one;
semantic similarity never bypasses the permission gate; and no published index degrades to
lexical without mislabelling.
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import search_contract as SC
from . import semantic_index as SI
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection, SemanticDocumentEmbedding,
    SemanticIndexGeneration, SemanticIndexPublicationState,
)
from .search_service import execute_search
from .semantic_encoder import DeterministicStubEncoder
from .semantic_index import SemanticIndexError, build_generation, publish_generation
from .test_review_campaign import asset, brand

pytestmark = pytest.mark.django_db


def _run(**raw):
    return execute_search(SC.build_search_query(raw))


def _authority_counts():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count())


# === build lifecycle ============================================================
def test_stub_build_writes_only_index_tables_and_zero_authority_rows():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    before = _authority_counts()
    gen = build_generation(DeterministicStubEncoder(), invoked_by="tester")
    assert gen.status == SemanticIndexGeneration.Status.BUILT
    assert gen.is_test_encoder is True
    assert gen.embedded_count == gen.document_count == 2
    assert SemanticDocumentEmbedding.objects.filter(generation=gen).count() == 2
    assert _authority_counts() == before          # no decision, projection, or permission


def test_rebuild_is_idempotent_by_corpus_hash():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    a = build_generation(DeterministicStubEncoder())
    b = build_generation(DeterministicStubEncoder())
    assert a.corpus_manifest_hash == b.corpus_manifest_hash    # unchanged corpus


def test_changed_corpus_changes_the_manifest_hash():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    first = SI.corpus_manifest_hash()
    brand()                                        # add an item
    assert SI.corpus_manifest_hash() != first


def test_test_encoder_generation_can_never_publish():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    gen = build_generation(DeterministicStubEncoder())
    with pytest.raises(SemanticIndexError):
        publish_generation(gen)
    # and the publication state stays empty
    assert SI.published_generation() is None


def test_failed_build_does_not_replace_a_published_generation():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    # simulate a published OpenAI generation by constructing one directly, then publishing
    gen = build_generation(DeterministicStubEncoder())
    # forge it into an openai-shaped BUILT generation so publish is allowed, then publish
    SemanticIndexGeneration.objects.filter(pk=gen.pk).update(
        provider="openai", is_test_encoder=False, model_identifier="text-embedding-3-small")
    gen.refresh_from_db()
    publish_generation(gen)
    assert SI.published_generation().pk == gen.pk
    # a subsequent failing build must not disturb the published one
    encoder = DeterministicStubEncoder()
    encoder.encode = lambda texts: (_ for _ in ()).throw(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        build_generation(encoder)
    assert SI.published_generation().pk == gen.pk       # unchanged


def test_publish_refuses_a_non_openai_provider():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    gen = build_generation(DeterministicStubEncoder())
    SemanticIndexGeneration.objects.filter(pk=gen.pk).update(is_test_encoder=False)
    gen.refresh_from_db()
    with pytest.raises(SemanticIndexError):
        publish_generation(gen)             # provider is still the stub provider


# === index status ===============================================================
def test_index_status_unavailable_then_current_then_stale():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    assert SI.index_status()[0] == SI.STATUS_UNAVAILABLE
    gen = build_generation(DeterministicStubEncoder())
    SemanticIndexGeneration.objects.filter(pk=gen.pk).update(
        provider="openai", is_test_encoder=False, model_identifier="text-embedding-3-small")
    gen.refresh_from_db()
    publish_generation(gen)
    assert SI.index_status()[0] == SI.STATUS_CURRENT
    brand()                                         # corpus changes
    assert SI.index_status()[0] == SI.STATUS_STALE


# === hybrid search: semantic NEVER bypasses the gate ============================
def _publish_stub_index():
    """Publish a stub-built index forged into openai shape, so browser queries can embed
    locally (the stub provider embeds without external calls) and semantic engages."""
    gen = build_generation(DeterministicStubEncoder())
    # keep provider as the stub so query embedding stays local; publish path needs openai,
    # so publish directly via the state to exercise the SEARCH side deterministically
    state, _ = SemanticIndexPublicationState.objects.get_or_create(pk=1)
    gen.status = SemanticIndexGeneration.Status.PUBLISHED
    gen.save()
    state.current_generation = gen
    state.corpus_manifest_hash = gen.corpus_manifest_hash
    state.save()
    return gen


def test_semantic_ranking_never_makes_a_denied_item_retrievable():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    _publish_stub_index()
    reviewer = _run(query="brand", ranking="HYBRID", mode="REVIEWER_CANDIDATE_SEARCH")
    assert reviewer["ranking_is_semantic"] is True
    # every reviewer result still shows RETRIEVAL denied ...
    assert all(r["retrieval"]["allowed"] is False for r in reviewer["results"])
    # ... and the operational modes return nothing regardless of similarity
    assert _run(query="brand", ranking="HYBRID",
                mode="OPERATIONAL_RETRIEVAL")["total_results"] == 0
    assert _run(query="brand", ranking="HYBRID",
                mode="AUTOMATIC_USE")["total_results"] == 0


def test_reviewer_hybrid_reports_lexical_and_semantic_scores_separately():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_stub_index()
    result = _run(query="asset", ranking="HYBRID")
    assert result["results"]
    row = result["results"][0]
    assert "lexical_score" in row and "semantic_score" in row
    assert row["semantic_score"] is not None           # real vector score
    assert "SEMANTIC_SIMILARITY" in row["match_reasons"]


def test_search_writes_nothing_even_with_a_published_index():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_stub_index()
    before = _authority_counts()
    _run(query="asset", ranking="HYBRID")
    _run(query="asset", ranking="SEMANTIC")
    assert _authority_counts() == before


# === fallback + honesty =========================================================
def test_no_index_lexical_is_preserved_and_semantic_falls_back_labelled():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    lexical = _run(query="asset")                       # DIP-1B-6 default
    assert lexical["ranking_is_semantic"] is False
    assert lexical["result_label"] == "LEXICAL"
    hybrid = _run(query="asset", ranking="HYBRID")      # no index -> lexical fallback
    assert hybrid["ranking_is_semantic"] is False
    assert hybrid["result_label"] == "LEXICAL_ONLY"     # labelled, never called semantic


def test_semantic_only_without_fallback_fails_clearly():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    result = _run(query="asset", ranking="SEMANTIC", allow_lexical_fallback=False)
    assert result["total_results"] == 0
    assert result["result_label"] == "SEMANTIC_UNAVAILABLE"
