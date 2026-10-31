"""Controlled query embedding — DIP-1C-2.

The claims defended here: no external call without explicit per-request consent AND a
current, compatible, published index; only the bounded query phrase + facet ever leave; the
raw query and vector are never persisted; every refusal is a distinct bounded code; and
semantic similarity never bypasses the permission gate on the POST path.

No test ever contacts OpenAI — the client is mocked inside `OpenAIEncoder.encode`.
"""
from __future__ import annotations

from unittest import mock

import pytest

from apps.accounts.models import DecisionEvent

from . import semantic_query as SQ
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection, SemanticDocumentEmbedding,
    SemanticIndexGeneration, SemanticIndexPublicationState,
)
from .semantic_encoder import OPENAI_MODEL, OpenAIEncoder
from .semantic_index import build_generation
from .test_review_campaign import asset, brand

pytestmark = pytest.mark.django_db

DIM = 8


class _MockOpenAIEncoder(OpenAIEncoder):
    """The real OpenAIEncoder with its network call replaced. Its construct-guard, key
    check, provider identity and model identity are all still exercised."""
    dimension = DIM

    def __init__(self, *, external_transfer_confirmed):
        super().__init__(external_transfer_confirmed=external_transfer_confirmed)
        self.calls = []

    def encode(self, texts):
        self.calls.extend(texts)
        # deterministic + content-discriminating, never a network call
        out = []
        for t in texts:
            v = [0.0] * DIM
            for i, ch in enumerate((t or "x").lower()):
                v[i % DIM] += (ord(ch) % 17) / 17.0
            norm = sum(c * c for c in v) ** 0.5 or 1.0
            out.append([c / norm for c in v])
        return out


def _publish_openai_index(settings):
    """Build + publish a production-shaped OpenAI index using the mocked encoder, so the
    document and query vectors share a provider, model and dimension by construction."""
    settings.OPENAI_API_KEY = "sk-test-key-never-printed"
    encoder = _MockOpenAIEncoder(external_transfer_confirmed=True)
    gen = build_generation(encoder)
    SemanticIndexGeneration.objects.filter(pk=gen.pk).update(
        status=SemanticIndexGeneration.Status.PUBLISHED)
    gen.refresh_from_db()
    state, _ = SemanticIndexPublicationState.objects.get_or_create(pk=1)
    state.current_generation = gen
    state.corpus_manifest_hash = gen.corpus_manifest_hash
    state.provider, state.model_identifier = gen.provider, gen.model_identifier
    state.save()
    return gen


def _query(**over):
    raw = {"query_text": "luxury floral cosmetic packaging",
           "confirm_external_query_transfer": True}
    raw.update(over)
    return SQ.build_semantic_query(raw)


def _authority_counts():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count())


# === contract ===================================================================
def test_valid_query_normalizes():
    q = _query(query_text="  Luxury   Floral  ")
    assert q.query_text == "Luxury Floral"
    assert q.facet == SQ.GENERAL_CONCEPT
    assert q.schema_version == "intelligence_semantic_query/1.0"


@pytest.mark.parametrize("raw", [
    {"query_text": ""},
    {"query_text": "   "},
    {"query_text": "a" * 201},
    {"query_text": " ".join(["w"] * 41)},
    {"query_text": "bad\x00control"},
    {"query_text": "/Users/secret/materials/x.ai"},     # filesystem path
    {"query_text": "../../etc/passwd"},
    {"query_text": "ok", "facet": "MAGIC_FACET"},
    {"query_text": "ok", "scope": "EVERYTHING"},
    {"query_text": "ok", "limit": 0},
    {"query_text": "ok", "limit": 9999},
    {"query_text": "ok", "item_kinds": ["NOT_A_KIND"]},
    {"query_text": "ok", "sql": "1=1"},                 # arbitrary field
])
def test_unhonourable_queries_are_refused(raw):
    raw.setdefault("confirm_external_query_transfer", True)
    with pytest.raises(SQ.SemanticQueryError):
        SQ.build_semantic_query(raw)


def test_transmitted_payload_is_only_phrase_and_facet():
    q = _query(facet=SQ.DESIGN_STYLE)
    assert set(q.transmitted_payload()) == {"query_text", "facet"}
    blob = repr(q.transmitted_payload())
    for forbidden in ("/Users", "materials/", "sk-", "reviewer", "corpus_item_id"):
        assert forbidden not in blob


# === consent gate: no call without explicit per-request confirmation =============
@pytest.mark.parametrize("value", [None, False, "", "false", "0", "no"])
def test_absent_or_false_confirmation_prevents_any_external_call(settings, value):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    raw = {"query_text": "floral"}
    if value is not None:
        raw["confirm_external_query_transfer"] = value
    q = SQ.build_semantic_query(raw)
    assert q.external_transfer_confirmed is False
    with mock.patch.object(SQ, "get_encoder") as ge:
        result = SQ.encode_semantic_query(q)
    assert result.ok is False
    assert result.failure_code == SQ.EXTERNAL_TRANSFER_NOT_CONFIRMED
    ge.assert_not_called()                 # the encoder was never even constructed


def test_confirmation_is_required_for_each_request(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    with mock.patch.object(SQ, "get_encoder",
                           return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        assert SQ.encode_semantic_query(_query()).ok is True
    # a second query without confirmation is refused — consent never carries over
    second = SQ.build_semantic_query({"query_text": "floral"})
    assert SQ.encode_semantic_query(second).failure_code == (
        SQ.EXTERNAL_TRANSFER_NOT_CONFIRMED)


# === index preconditions: every one refuses BEFORE any call =====================
def test_unavailable_index_denies_without_calling(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    with mock.patch.object(SQ, "get_encoder") as ge:
        r = SQ.encode_semantic_query(_query())
    assert r.failure_code == SQ.SEMANTIC_INDEX_UNAVAILABLE
    ge.assert_not_called()


def test_stale_index_denies_without_calling(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    brand()                                   # corpus changes -> index stale
    with mock.patch.object(SQ, "get_encoder") as ge:
        r = SQ.encode_semantic_query(_query())
    assert r.failure_code == SQ.SEMANTIC_INDEX_STALE
    ge.assert_not_called()                    # never embed against stale documents


def test_model_mismatch_denies_without_calling(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    gen = _publish_openai_index(settings)
    SemanticIndexGeneration.objects.filter(pk=gen.pk).update(
        model_identifier="text-embedding-3-large")
    with mock.patch.object(SQ, "get_encoder") as ge:
        r = SQ.encode_semantic_query(_query())
    assert r.failure_code == SQ.MODEL_MISMATCH
    ge.assert_not_called()


def test_generation_and_corpus_hash_mismatch_deny(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    gen = _publish_openai_index(settings)
    assert SQ.encode_semantic_query(
        _query(generation_id="00000000-0000-0000-0000-000000000000")
    ).failure_code == SQ.GENERATION_MISMATCH
    assert SQ.encode_semantic_query(
        _query(expected_corpus_hash="f" * 64)).failure_code == SQ.CORPUS_HASH_MISMATCH
    # the matching generation and hash are accepted (proves the guard discriminates)
    with mock.patch.object(SQ, "get_encoder",
                           return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        ok = SQ.encode_semantic_query(_query(
            generation_id=str(gen.pk), expected_corpus_hash=gen.corpus_manifest_hash))
    assert ok.ok is True


def test_missing_provider_key_fails_closed(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    settings.OPENAI_API_KEY = ""              # key gone at query time
    r = SQ.encode_semantic_query(_query())
    assert r.failure_code == SQ.PROVIDER_CONFIGURATION_MISSING
    assert r.vector is None


def test_provider_error_yields_bounded_code_and_no_raw_response(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    boom = _MockOpenAIEncoder(external_transfer_confirmed=True)
    boom.encode = lambda texts: (_ for _ in ()).throw(
        RuntimeError("openai secret internal detail"))
    with mock.patch.object(SQ, "get_encoder", return_value=boom):
        r = SQ.encode_semantic_query(_query())
    assert r.failure_code == SQ.PROVIDER_ERROR
    assert "secret internal detail" not in repr(r)    # no raw provider response leaks


def test_dimension_mismatch_from_provider_is_rejected(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    wrong = _MockOpenAIEncoder(external_transfer_confirmed=True)
    wrong.encode = lambda texts: [[0.1] * (DIM + 3)]
    with mock.patch.object(SQ, "get_encoder", return_value=wrong):
        r = SQ.encode_semantic_query(_query())
    assert r.failure_code == SQ.DIMENSION_MISMATCH


# === success path ===============================================================
def test_confirmed_query_against_current_index_embeds_and_returns_a_vector(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    gen = _publish_openai_index(settings)
    encoder = _MockOpenAIEncoder(external_transfer_confirmed=True)
    with mock.patch.object(SQ, "get_encoder", return_value=encoder):
        r = SQ.encode_semantic_query(_query(facet=SQ.PRODUCT_CATEGORY))
    assert r.ok is True
    assert len(r.vector) == DIM
    assert r.model_identifier == OPENAI_MODEL
    assert r.generation_id == str(gen.pk)
    # exactly the bounded phrase + facet was transmitted, nothing else
    assert encoder.calls == ["PRODUCT_CATEGORY: luxury floral cosmetic packaging"]


def test_query_and_vector_are_never_persisted_and_no_authority_created(settings):
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    _publish_openai_index(settings)
    before = _authority_counts()
    embeddings_before = SemanticDocumentEmbedding.objects.count()
    with mock.patch.object(SQ, "get_encoder",
                           return_value=_MockOpenAIEncoder(external_transfer_confirmed=True)):
        r = SQ.encode_semantic_query(_query())
    assert r.ok is True
    assert _authority_counts() == before
    assert SemanticDocumentEmbedding.objects.count() == embeddings_before
    # the result carries only bounded metadata — no raw query text, no vector, no key
    assert r.query_char_count == len("luxury floral cosmetic packaging")
