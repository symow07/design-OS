"""Schema 1.2, identity planning, abstention and performance — DIP-1C-4A.

Pins the four things this slice exists to fix, all measured in the DIP-1C-3 pilot:
identity/embedding-text separation, honest absence of unsupported concepts, exact identity
as a pin rather than a weight, and the removal of the per-request full-corpus rebuild.

No test contacts a provider.
"""
from __future__ import annotations

import pytest
from django.test import TestCase

from apps.accounts.models import DecisionEvent

from . import search_planner as SP
from . import semantic_document as SD
from . import semantic_document_v12 as V12
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection, SemanticIndexGeneration,
)
from .semantic_corpus import build_corpus_snapshot
from .test_review_campaign import asset, brand, historical, palette

pytestmark = pytest.mark.django_db


def _authority():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.count())


# === schema versioning ===========================================================
def test_schemas_1_0_and_1_1_remain_frozen():
    assert SD.DOCUMENT_SCHEMA_V1_0 == "intelligence_semantic_document/1.0"
    assert SD.DOCUMENT_SCHEMA_V1_1 == "intelligence_semantic_document/1.1"
    assert V12.DOCUMENT_SCHEMA_V1_2 == "intelligence_semantic_document/1.2"
    # 1.1's builder still emits 1.1 — this slice did not touch it
    assert SD.build_semantic_document(
        brand().corpus_item)["schema_version"] == SD.DOCUMENT_SCHEMA_V1_1


def test_1_2_is_deterministic():
    snapshot = build_corpus_snapshot()
    again = build_corpus_snapshot()
    assert [d["embedding_text"] for _, d in snapshot.documents] == [
        d["embedding_text"] for _, d in again.documents]
    assert snapshot.manifest_hash() == again.manifest_hash()


# === metadata vs embedding text ==================================================
def test_metadata_and_embedding_text_are_separate():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    snapshot = build_corpus_snapshot()
    document = next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id)
    assert set(document["metadata"]) == set(V12.METADATA_FIELDS)
    assert "embedding_text" in document and "channels" in document


@pytest.mark.parametrize("kind", ["asset", "historical", "brand", "palette"])
def test_identifiers_never_enter_the_embedding_text(kind):
    """Stable keys, UUIDs and dataset identifiers are identity, not topic."""
    rc = {"asset": lambda: asset(DIP0C2_ASSET_CANDIDATE_DATASET),
          "historical": historical, "brand": brand, "palette": palette}[kind]()
    snapshot = build_corpus_snapshot()
    document = next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id)
    text = document["embedding_text"]
    assert document["metadata"]["external_key"] not in text
    assert str(rc.corpus_item_id) not in text
    if document["metadata"]["dataset_identifier"]:
        assert document["metadata"]["dataset_identifier"] not in text


def test_readiness_blockers_and_workflow_vocabulary_are_absent_from_embedding_text():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    for _, document in build_corpus_snapshot().documents:
        text = document["embedding_text"].upper()
        for noise in ("READY_FOR_CLASSIFICATION", "RIGHTS_UNREVIEWED", "WAVE_",
                      "EVIDENCE_READINESS_DIMENSIONS", "BLOCKED_BY", "DIP0C2",
                      "SEMANTIC_DOCUMENT", "CURATED_STARTER_CANDIDATE"):
            assert noise not in text


# === controlled phrases render existing facts ====================================
def test_controlled_phrases_render_real_facts():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)          # candidate_asset_kind=MOTIF
    snapshot = build_corpus_snapshot()
    document = next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id)
    assert "cosmetics design asset" in document["embedding_text"]
    assert "decorative motif graphic" in document["embedding_text"]


def test_unknown_asset_kind_yields_no_invented_category():
    from .models import DesignAssetProfile
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    DesignAssetProfile.objects.filter(corpus_item=rc.corpus_item).update(
        candidate_asset_kind="UNKNOWN")
    snapshot = build_corpus_snapshot()
    document = next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id)
    # an unknown asset has no topical evidence; nothing is manufactured for it
    assert document["channels"]["asset_category_terms"] == []
    assert document["embedding_text"] == "cosmetics design asset"


def test_our_controlled_vocabulary_never_introduces_an_unsupported_concept():
    """The pilot showed semantic similarity manufacturing luxury/minimal/geometric over a
    corpus that records none of them. Our own phrases must never seed those words."""
    for name in V12.CONTROLLED_VOCABULARIES:
        vocabulary = getattr(V12, name)
        blob = " ".join(vocabulary.values()).lower()
        for concept in V12.UNSUPPORTED_CONCEPTS:
            assert concept not in blob, f"{name} introduces {concept!r}"


def test_documents_gain_no_unsupported_adjectives():
    import re
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    historical()
    brand()
    for _, document in build_corpus_snapshot().documents:
        # exclude the item's own recorded name — that is its name, not our claim
        generated = " ".join(
            t["term"] for channel, terms in document["channels"].items()
            for t in terms if channel != "font_family_terms").lower()
        for concept in V12.UNSUPPORTED_CONCEPTS:
            assert not re.search(rf"\b{concept}\b", generated)


def test_no_phrase_is_derived_from_a_path_or_filename():
    from .models import DesignAssetProfile
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    DesignAssetProfile.objects.filter(corpus_item=rc.corpus_item).update(
        collection_family_label="materials/DOWNLOADE 2026/9993170.ai")
    snapshot = build_corpus_snapshot()
    document = next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id)
    assert "materials" not in document["embedding_text"]
    assert "9993170" not in document["embedding_text"]


def test_a_path_like_machine_family_cannot_become_a_phrase():
    from .models import HistoricalDesignProfile
    rc = historical()
    HistoricalDesignProfile.objects.filter(corpus_item=rc.corpus_item).update(
        product_family_machine_label="materials/x/y.ai")
    snapshot = build_corpus_snapshot()
    document = next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id)
    assert document["channels"]["product_family_terms"] == []
    assert "materials" not in document["embedding_text"]


# === provenance ==================================================================
def test_machine_and_human_terms_carry_distinct_provenance():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    snapshot = build_corpus_snapshot()
    document = next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id)
    for term in document["channels"]["asset_category_terms"]:
        assert term["provenance"] == V12.PROV_MACHINE
    for term in document["channels"]["item_type_terms"]:
        assert term["provenance"] == V12.PROV_TECHNICAL
    assert V12.PROV_HUMAN != V12.PROV_MACHINE       # never one unlabelled source


# === dedup + ordering ============================================================
def test_embedding_text_is_deduplicated_and_stably_ordered():
    channels = {name: [] for name in V12.CHANNELS}
    channels["item_type_terms"] = [{"term": "font typeface", "provenance": "T"}]
    channels["font_style_terms"] = [{"term": "font typeface", "provenance": "T"},
                                    {"term": "italic typeface", "provenance": "T"}]
    text = V12.render_embedding_text(channels)
    assert text == "font typeface. italic typeface"        # no phrase repeated
    assert V12.render_embedding_text(channels) == text     # stable


def test_no_term_is_repeated_to_simulate_weighting():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    for _, document in build_corpus_snapshot().documents:
        phrases = [p.strip() for p in document["embedding_text"].split(".") if p.strip()]
        assert len(phrases) == len(set(phrases))


def test_empty_channels_are_omitted():
    channels = {name: [] for name in V12.CHANNELS}
    assert V12.render_embedding_text(channels) == ""


# === boundary ====================================================================
def test_1_2_documents_pass_the_recursive_value_boundary():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    historical()
    brand()
    palette()
    for _, document in build_corpus_snapshot().documents:
        V12._assert_within_boundary_v12(document)


def test_an_unexpected_field_or_channel_is_refused():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    snapshot = build_corpus_snapshot()
    document = dict(next(d for i, d in snapshot.documents if i.pk == rc.corpus_item_id))
    document["sneaky"] = "x"
    with pytest.raises(V12.SemanticDocumentV12Error):
        V12._assert_within_boundary_v12(document)


# === identity planner ============================================================
def test_exact_stable_key_resolves_to_its_canonical_item():
    keys = {"a": "asset:dip0c2:abc", "b": "font:x:1"}
    labels = {"a": "", "b": "almarai"}
    assert SP.plan_exact_identity("asset:dip0c2:abc", keys_by_id=keys,
                                  labels_by_id=labels) == ("a", SP.EXACT_STABLE_KEY)
    assert SP.plan_exact_identity("almarai", keys_by_id=keys,
                                  labels_by_id=labels) == ("b", SP.EXACT_DISPLAY_LABEL)
    assert SP.plan_exact_identity("something else", keys_by_id=keys,
                                  labels_by_id=labels) is None


def test_identity_pin_ranks_the_exact_match_first_with_an_explicit_reason():
    rows = [{"corpus_item_id": "x", "match_reasons": ["SEMANTIC_SIMILARITY"]},
            {"corpus_item_id": "a", "match_reasons": ["TOKEN_OVERLAP"]}]
    pinned = SP.apply_identity_pin(rows, "a")
    assert pinned[0]["corpus_item_id"] == "a"
    assert pinned[0]["match_reasons"][0] == SP.EXACT_IDENTITY_MATCH
    assert pinned[0]["exact_identity_match"] is True


def test_identity_pin_beats_any_semantic_score_without_a_hidden_weight():
    """Q29 failed in the pilot because cosine outranked the exact key. A pin is an answer,
    not a nudge a strong enough similarity can outvote — and no score is inflated."""
    rows = [{"corpus_item_id": "x", "match_score": 999999,
             "match_reasons": ["SEMANTIC_SIMILARITY"]},
            {"corpus_item_id": "a", "match_score": 1, "match_reasons": []}]
    pinned = SP.apply_identity_pin(rows, "a")
    assert pinned[0]["corpus_item_id"] == "a"
    assert pinned[0]["match_score"] == 1        # the score was NOT inflated to win


def test_identity_pin_is_a_noop_without_a_match():
    rows = [{"corpus_item_id": "x", "match_reasons": []}]
    assert SP.apply_identity_pin(rows, None) == rows


# === abstention gate (defined + measured, NOT activated) ==========================
def test_gate_abstains_on_a_flat_undifferentiated_score_field():
    """Every query has a vector, so cosine always ranks something. A field where the top
    barely exceeds the median is the shape of 'nothing here matches'."""
    scores = {f"i{n}": 0.40 + n * 0.0001 for n in range(20)}
    assessment = SP.assess_semantic_evidence(scores)
    assert assessment.verdict == SP.SEMANTIC_NO_EVIDENTIAL_BASIS


def test_gate_passes_a_strong_well_separated_signal():
    scores = {"top": 0.88}
    scores.update({f"i{n}": 0.30 for n in range(20)})
    assert SP.assess_semantic_evidence(scores).verdict == SP.SEMANTIC_EVIDENCE_SUFFICIENT


def test_gate_abstains_on_a_low_top_score():
    scores = {"top": 0.31}
    scores.update({f"i{n}": 0.10 for n in range(10)})
    assert SP.assess_semantic_evidence(scores).verdict == SP.SEMANTIC_NO_EVIDENTIAL_BASIS


def test_gate_abstains_on_facet_mismatch():
    scores = {"a": 0.90}
    scores.update({f"i{n}": 0.30 for n in range(10)})
    assessment = SP.assess_semantic_evidence(
        scores, kinds_by_id={"a": "FONT"}, expected_kinds=("HISTORICAL_DESIGN",))
    assert assessment.verdict == SP.SEMANTIC_NO_EVIDENTIAL_BASIS
    assert assessment.facet_consistent is False


def test_gate_abstains_on_empty_scores():
    assert SP.assess_semantic_evidence({}).verdict == SP.SEMANTIC_NO_EVIDENTIAL_BASIS


def test_gate_is_not_activated_by_default_and_cannot_special_case_a_query():
    """Thresholds must not be switched on having been fitted to the 30 benchmark queries.

    The strongest guarantee is structural: the gate's signature accepts scores and kinds —
    it never receives the query text or id, so it *cannot* special-case a phrase even if
    someone tried.
    """
    assessment = SP.assess_semantic_evidence({"a": 0.9, "b": 0.2})
    assert assessment.activated is False
    import inspect
    parameters = set(inspect.signature(SP.assess_semantic_evidence).parameters)
    assert parameters == {"scores", "kinds_by_id", "expected_kinds", "thresholds",
                          "activate"}
    assert not {"query", "query_text", "query_id", "phrase"} & parameters
    # and no benchmark query id appears in the module's logic
    for query_id in ("Q01", "Q07", "Q09", "Q12", "Q29", "Q30"):
        assert query_id not in inspect.getsource(SP.assess_semantic_evidence)


def test_gate_versions_are_explicit():
    assert SP.EVIDENCE_GATE_VERSION == "semantic_evidence_gate/1.0"
    assert SP.SEARCH_PLANNER_VERSION == "intelligence_search_planner/1.0"


# === separation ==================================================================
def test_snapshot_writes_nothing_and_creates_no_authority():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    before = _authority()
    build_corpus_snapshot()
    assert _authority() == before
    assert SemanticIndexGeneration.objects.count() == 0


def test_ranker_1_1_is_untouched():
    from .hybrid_ranker import HYBRID_RANKER_VERSION, _LEXICAL_WEIGHT, _SEMANTIC_WEIGHT
    assert HYBRID_RANKER_VERSION == "intelligence_hybrid_ranker/1.1"
    assert (_LEXICAL_WEIGHT, _SEMANTIC_WEIGHT) == (1.0, 300.0)


# === performance: bounded queries, one build per request =========================
class CorpusSnapshotQueryBudgetTest(TestCase):
    """The pilot's 3.6 s came from rebuilding all 176 documents per request, each item
    issuing its own readiness/governance/assertion queries. The snapshot must be bulk."""

    def test_query_count_is_bounded_and_does_not_grow_per_item(self):
        from .test_review_campaign import asset as make_asset
        for _ in range(3):
            make_asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        with self.assertNumQueries(6):
            build_corpus_snapshot()
        for _ in range(9):
            make_asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        # 4x the items, same bounded query count — no N+1
        with self.assertNumQueries(6):
            build_corpus_snapshot()

    def test_manifest_hash_reuses_one_build(self):
        from .test_review_campaign import asset as make_asset
        make_asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        snapshot = build_corpus_snapshot()
        with self.assertNumQueries(0):          # hashing touches the database not at all
            snapshot.manifest_hash()
            snapshot.manifest_hash()


class StalenessContractTest(TestCase):
    """Staleness is corrected, not weakened: exact w.r.t. embedded content."""

    def test_membership_change_changes_the_manifest(self):
        from .test_review_campaign import asset as make_asset, brand as make_brand
        make_asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        before = build_corpus_snapshot().manifest_hash()
        make_brand()
        assert build_corpus_snapshot().manifest_hash() != before

    def test_embedded_content_change_changes_the_manifest(self):
        from .models import DesignAssetProfile
        from .test_review_campaign import asset as make_asset
        rc = make_asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        before = build_corpus_snapshot().manifest_hash()
        DesignAssetProfile.objects.filter(corpus_item=rc.corpus_item).update(
            candidate_asset_kind="PATTERN")          # changes an embedded phrase
        assert build_corpus_snapshot().manifest_hash() != before

    def test_non_embedded_workflow_change_does_not_change_the_manifest(self):
        """A workflow transition must NOT mark the index stale — none of it is embedded in
        1.2, so the vectors are unaffected. This is the corrected contract, not a
        relaxation: staleness is now exact with respect to what is actually embedded."""
        from .models import ReviewCandidate
        from .test_review_campaign import asset as make_asset
        rc = make_asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        before = build_corpus_snapshot().manifest_hash()
        ReviewCandidate.objects.filter(pk=rc.pk).update(
            workflow_status=ReviewCandidate.Status.NEEDS_INFORMATION, priority=99)
        assert build_corpus_snapshot().manifest_hash() == before
