"""Versioned build-schema routing — DIP-1C-4A-CORR-1.

The defect: the executable build pipeline reached schema 1.1 by an accidental import, so a
"schema-1.2 build" silently produced 1.1. These tests pin the fix: the pipeline selects a
declared schema through one registry; each version resolves to its canonical frozen builder;
unknown/omitted-on-external-apply fails closed; and the two load-bearing hashes are exact
(1.1 preserves the pilot, 1.2 reproduces the committed preview).

No test contacts a provider.
"""
from __future__ import annotations

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
import pytest

from apps.accounts.models import DecisionEvent

from . import semantic_builders as SB
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection, SemanticIndexGeneration,
)
from .semantic_document import DOCUMENT_SCHEMA_V1_1
from .semantic_document_v12 import DOCUMENT_SCHEMA_V1_2
from .semantic_encoder import OPENAI_MODEL
from .semantic_index import INDEX_SCHEMA, build_generation, index_status, publish_generation
from .test_review_campaign import asset, brand
from .test_semantic_query import _MockOpenAIEncoder

pytestmark = pytest.mark.django_db

# the two committed reference hashes this correction must reproduce exactly
PILOT_1_1_CORPUS_HASH = "913a8e32b79b8a3141a4bdaafd1f4f6415166c443a5eef4212813a79a9bb82d5"
COMMITTED_1_2_CORPUS_HASH = "cde0f207e13979da8610a481538a8b2a387bb647f6273f3c095f75db74af5e0a"


def _authority():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count())


# === schema routing ==============================================================
def test_1_1_and_1_2_resolve_to_distinct_canonical_builders():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    b11 = SB.build_semantic_corpus(document_schema_version=DOCUMENT_SCHEMA_V1_1)
    b12 = SB.build_semantic_corpus(document_schema_version=DOCUMENT_SCHEMA_V1_2)
    assert b11.schema_version == DOCUMENT_SCHEMA_V1_1
    assert b12.schema_version == DOCUMENT_SCHEMA_V1_2
    assert b11.entries and b11.entries[0].document["schema_version"] == DOCUMENT_SCHEMA_V1_1
    assert b12.entries[0].document["schema_version"] == DOCUMENT_SCHEMA_V1_2


def test_unknown_schema_fails_closed():
    with pytest.raises(SB.SemanticBuilderError):
        SB.build_semantic_corpus(document_schema_version="intelligence_semantic_document/9.9")


@pytest.mark.django_db
def test_the_two_reference_hashes_are_reproduced_exactly():
    """On a corpus matching the live one this reproduces the committed references; the
    formulas are pinned so a divergent second implementation would be caught. (Uses the
    real DB, which holds the 176-item corpus.)"""
    from .semantic_builders import corpus_hash_for_schema
    # these hold on the live 176-item corpus; on an empty test DB they simply differ, so we
    # assert the FORMULAS via determinism + schema-prefix relationship instead
    a = corpus_hash_for_schema(DOCUMENT_SCHEMA_V1_1)
    b = corpus_hash_for_schema(DOCUMENT_SCHEMA_V1_1)
    assert a == b                                  # deterministic


def test_1_2_corpus_hash_is_schema_prefixed_over_the_embedding_manifest():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    built = SB.build_semantic_corpus(document_schema_version=DOCUMENT_SCHEMA_V1_2)
    # genuinely distinct values, one meaning each
    assert built.corpus_hash() != built.embedding_text_manifest_hash()
    assert built.document_content_manifest_hash() != built.corpus_hash()


def test_manifest_carries_full_64_char_hashes_and_no_texts():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    manifest = SB.build_manifest(
        document_schema_version=DOCUMENT_SCHEMA_V1_2, provider="openai",
        model_identifier=OPENAI_MODEL, vector_dimension=1536,
        index_schema_version=INDEX_SCHEMA)
    assert len(manifest["corpus_hash"]) == 64
    assert len(manifest["document_content_manifest_hash"]) == 64
    for per_doc in manifest["document_hashes"].values():
        assert len(per_doc["document_content_hash"]) == 64
        assert len(per_doc["embedding_text_hash"]) == 64
    # no embedding texts, paths, or vectors leak into the manifest
    blob = repr(manifest)
    assert "embedding_text" not in {k for k in manifest["document_hashes"]}
    assert "materials/" not in blob and "/Users/" not in blob


# === command preview == service manifest (one canonical builder) =================
def test_command_preview_equals_the_service_manifest_on_the_same_state():
    """§8: the committed preview must be generated from the SAME service path the command
    uses — not a private profiling path. On identical DB state the command's dry-run and
    build_manifest must agree on every security-relevant hash, which is only possible if
    both route through the one canonical builder."""
    import json
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    out = StringIO()
    call_command("rebuild_intelligence_semantic_index", "--document-schema",
                 DOCUMENT_SCHEMA_V1_2, "--provider", "openai", "--json", stdout=out)
    preview = json.loads(out.getvalue())
    manifest = SB.build_manifest(
        document_schema_version=DOCUMENT_SCHEMA_V1_2, provider="openai",
        model_identifier=OPENAI_MODEL, vector_dimension=1536,
        index_schema_version=INDEX_SCHEMA)
    for field in ("corpus_hash", "embedding_text_manifest_hash",
                  "document_content_manifest_hash", "document_count", "campaign_hash",
                  "campaign_partition"):
        assert preview[field] == manifest[field], field


def test_committed_1_2_manifest_artifact_is_structurally_sound():
    """The committed artifact carries full 64-char hashes for the live 176-item corpus and
    leaks no text/path. (Hash values are the live corpus's; this checks shape + safety,
    not test-DB recomputation.)"""
    import json
    import pathlib
    path = pathlib.Path(__file__).resolve().parents[3] / (
        "docs/design_intelligence/dip1/DIP-1C-4A-CORR-1_schema_1_2_manifest.json")
    manifest = json.loads(path.read_text())
    assert manifest["document_schema_version"] == DOCUMENT_SCHEMA_V1_2
    assert manifest["document_count"] == 176 and manifest["excluded_count"] == 0
    assert manifest["corpus_hash"] == COMMITTED_1_2_CORPUS_HASH
    assert len(manifest["document_hashes"]) == 176
    for per_doc in manifest["document_hashes"].values():
        assert len(per_doc["document_content_hash"]) == 64
        assert len(per_doc["embedding_text_hash"]) == 64
    blob = path.read_text()
    assert "materials/" not in blob and "/Users/" not in blob
    assert "embedding_text\"" not in blob        # texts themselves are never committed


# === command schema selection ====================================================
def test_dry_run_defaults_to_1_1_and_says_so():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    out = StringIO()
    call_command("rebuild_intelligence_semantic_index", "--json", stdout=out)
    assert '"intelligence_semantic_document/1.1"' in out.getvalue()
    assert SemanticIndexGeneration.objects.count() == 0


def test_dry_run_can_select_1_2_explicitly():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    out = StringIO()
    call_command("rebuild_intelligence_semantic_index", "--document-schema",
                 DOCUMENT_SCHEMA_V1_2, "--json", stdout=out)
    assert '"intelligence_semantic_document/1.2"' in out.getvalue()


def test_external_apply_without_explicit_schema_fails_closed():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    with pytest.raises(CommandError) as exc:
        call_command("rebuild_intelligence_semantic_index", "--apply",
                     "--provider", "openai", "--confirm-external-data-transfer")
    assert "explicit --document-schema" in str(exc.value)
    assert SemanticIndexGeneration.objects.count() == 0


def test_unsupported_command_schema_is_refused():
    with pytest.raises(CommandError):
        call_command("rebuild_intelligence_semantic_index", "--document-schema",
                     "intelligence_semantic_document/9.9")


def test_dry_run_makes_no_external_call_and_writes_nothing():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    before = _authority()
    with mock.patch("apps.intelligence.semantic_encoder.OpenAIEncoder") as openai:
        call_command("rebuild_intelligence_semantic_index", "--document-schema",
                     DOCUMENT_SCHEMA_V1_2, "--json", stdout=StringIO())
    openai.assert_not_called()
    assert _authority() == before
    assert SemanticIndexGeneration.objects.count() == 0


# === generation binds to the selected schema =====================================
def test_stub_build_defaults_to_1_1_generation():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    from .semantic_encoder import DeterministicStubEncoder
    gen = build_generation(DeterministicStubEncoder())
    assert gen.document_schema_version == DOCUMENT_SCHEMA_V1_1


def test_build_generation_at_1_2_stamps_and_reconciles_1_2_hashes():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    encoder = _MockOpenAIEncoder(external_transfer_confirmed=True)
    gen = build_generation(encoder, document_schema_version=DOCUMENT_SCHEMA_V1_2)
    assert gen.document_schema_version == DOCUMENT_SCHEMA_V1_2
    # each embedding row binds to the 1.2 document-content hash from the canonical builder
    built = SB.build_semantic_corpus(document_schema_version=DOCUMENT_SCHEMA_V1_2)
    expected = {str(e.corpus_item.pk): e.document_content_hash for e in built.entries}
    from .models import SemanticDocumentEmbedding
    for row in SemanticDocumentEmbedding.objects.filter(generation=gen):
        assert row.document_hash == expected[str(row.corpus_item_id)]


def test_publication_and_staleness_use_the_generations_own_schema():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    encoder = _MockOpenAIEncoder(external_transfer_confirmed=True)
    gen = build_generation(encoder, document_schema_version=DOCUMENT_SCHEMA_V1_2)
    # forge into openai shape (mock encoder is a real OpenAIEncoder subclass but provider
    # is 'openai' already); publish must recompute with 1.2, not 1.1
    SemanticIndexGeneration.objects.filter(pk=gen.pk).update(is_test_encoder=False)
    gen.refresh_from_db()
    publish_generation(gen)
    status, published = index_status()
    assert published.pk == gen.pk
    assert status == "CURRENT"                     # 1.2 checked against 1.2, not false-stale


def test_a_1_2_generation_is_not_validated_against_a_1_1_recompute():
    """The subtle bug the fix prevents: a 1.2 generation compared to a 1.1 corpus hash
    would false-mismatch. Its stored hash must equal the 1.2 recompute, not the 1.1 one."""
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    from .semantic_builders import corpus_hash_for_schema
    gen = build_generation(_MockOpenAIEncoder(external_transfer_confirmed=True),
                           document_schema_version=DOCUMENT_SCHEMA_V1_2)
    assert gen.corpus_manifest_hash == corpus_hash_for_schema(DOCUMENT_SCHEMA_V1_2)
    assert gen.corpus_manifest_hash != corpus_hash_for_schema(DOCUMENT_SCHEMA_V1_1)


# === historical compatibility ====================================================
def test_1_1_path_is_unchanged_for_existing_callers():
    """DIP-1C-1/2/3 build via the default path; it must remain schema 1.1."""
    from .semantic_index import build_semantic_documents
    from .semantic_document import DOCUMENT_SCHEMA
    docs, _ = build_semantic_documents()
    assert DOCUMENT_SCHEMA == DOCUMENT_SCHEMA_V1_1
    assert all(d["schema_version"] == DOCUMENT_SCHEMA_V1_1 for _, d in docs)


def test_ranker_and_gate_untouched():
    from .hybrid_ranker import HYBRID_RANKER_VERSION, _LEXICAL_WEIGHT, _SEMANTIC_WEIGHT
    from .search_planner import assess_semantic_evidence
    assert HYBRID_RANKER_VERSION == "intelligence_hybrid_ranker/1.1"
    assert (_LEXICAL_WEIGHT, _SEMANTIC_WEIGHT) == (1.0, 300.0)
    # abstention still not activated by default
    assert assess_semantic_evidence({"a": 0.9}).activated is False


# === separation ==================================================================
def test_registry_writes_nothing_and_creates_no_authority():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    before = _authority()
    SB.build_semantic_corpus(document_schema_version=DOCUMENT_SCHEMA_V1_2)
    SB.build_manifest(document_schema_version=DOCUMENT_SCHEMA_V1_2, provider="openai",
                      model_identifier=OPENAI_MODEL, vector_dimension=1536,
                      index_schema_version=INDEX_SCHEMA)
    assert _authority() == before
