"""Bounded semantic document + encoder + similarity — DIP-1C-1.

The document is the external boundary: it must carry only allow-listed bounded metadata,
keep machine and human labels distinguishable, hash deterministically, and never leak a
path, secret, binary, or authority signal. The stub encoder must be deterministic and
content-discriminating. Cosine similarity must reject degenerate input.
"""
from __future__ import annotations

import math

import pytest

from . import semantic_document as SD
from . import semantic_similarity as SS
from .semantic_encoder import (
    DeterministicStubEncoder, EncoderConfigurationError, OpenAIEncoder,
    TEST_ENCODER_PROVIDER, get_encoder,
)
from .test_review_campaign import asset, brand, historical
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET

pytestmark = pytest.mark.django_db


# === bounded document ===========================================================
def test_document_is_bounded_and_only_allowlisted_fields():
    doc = SD.build_semantic_document(brand().corpus_item)
    assert doc["schema_version"] == SD.DOCUMENT_SCHEMA
    assert set(doc) - {"schema_version"} == set(SD.INCLUDED_FIELDS)
    for prohibited in SD.PROHIBITED_FIELDS:
        assert prohibited not in doc


def test_document_never_carries_a_path_or_secret_value():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    doc = SD.build_semantic_document(rc.corpus_item)
    blob = repr(doc)
    assert "/Users/" not in blob and "materials/" not in blob


def test_machine_and_human_labels_stay_distinguishable():
    doc = SD.build_semantic_document(brand().corpus_item)
    assert "machine_classification_labels" in doc
    assert "human_assertion_labels" in doc
    assert doc["machine_classification_labels"] is not doc["human_assertion_labels"]


def test_document_hash_is_deterministic():
    item = historical().corpus_item
    a = SD.build_semantic_document(item)
    b = SD.build_semantic_document(item)
    assert SD.document_hash(a) == SD.document_hash(b)
    assert a == b


def test_semantic_text_is_deterministic_and_label_only():
    doc = SD.build_semantic_document(brand().corpus_item)
    assert SD.semantic_text(doc) == SD.semantic_text(doc)
    assert "/Users/" not in SD.semantic_text(doc)


# === stub encoder ===============================================================
def test_stub_encoder_is_deterministic_and_content_discriminating():
    enc = DeterministicStubEncoder()
    assert enc.is_test_encoder is True
    assert enc.provider == TEST_ENCODER_PROVIDER
    a1, a2 = enc.encode(["luxury floral packaging"]), enc.encode(["luxury floral packaging"])
    assert a1 == a2                                       # deterministic
    b = enc.encode(["minimal geometric wordmark"])
    assert a1 != b                                        # content-discriminating
    assert len(a1[0]) == enc.dimension
    assert all(math.isfinite(x) for x in a1[0])


# === openai encoder is gated ====================================================
def test_openai_encoder_refuses_without_external_confirmation():
    with pytest.raises(EncoderConfigurationError):
        OpenAIEncoder(external_transfer_confirmed=False)


def test_get_encoder_never_implicitly_returns_openai():
    # a search request (no confirmation) can never get an encoder that calls out
    assert get_encoder("stub").is_test_encoder is True
    with pytest.raises(EncoderConfigurationError):
        get_encoder("openai")                            # not confirmed -> refused
    with pytest.raises(EncoderConfigurationError):
        get_encoder("nonsense")


def test_openai_encoder_fails_closed_on_missing_key(settings):
    settings.OPENAI_API_KEY = ""
    with pytest.raises(EncoderConfigurationError):
        OpenAIEncoder(external_transfer_confirmed=True)


# === cosine similarity ==========================================================
def test_cosine_is_deterministic_and_bounded():
    v = [0.1, 0.2, 0.3, 0.4]
    assert SS.cosine_similarity(v, v) == pytest.approx(1.0)
    assert -1.0 <= SS.cosine_similarity(v, [0.4, 0.3, 0.2, 0.1]) <= 1.0


@pytest.mark.parametrize("a,b", [
    ([], [1.0]),
    ([0.0, 0.0], [1.0, 1.0]),              # zero-length has no direction
    ([1.0, 2.0], [1.0]),                   # dimension mismatch
    ([float("nan"), 1.0], [1.0, 1.0]),     # NaN
    ([float("inf"), 1.0], [1.0, 1.0]),     # Infinity
])
def test_cosine_rejects_degenerate_input(a, b):
    with pytest.raises(SS.SimilarityError):
        SS.cosine_similarity(a, b)


def test_rank_by_similarity_breaks_ties_on_uuid():
    q = [1.0, 0.0]
    # two identical vectors -> identical score -> UUID decides
    ranked = SS.rank_by_similarity(q, [
        ("00000000-0000-0000-0000-000000000002", [1.0, 0.0]),
        ("00000000-0000-0000-0000-000000000001", [1.0, 0.0])])
    assert [r[0] for r in ranked] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002"]
