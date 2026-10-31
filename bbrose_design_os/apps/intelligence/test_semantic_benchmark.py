"""Benchmark, evaluation and the human rating sheet — DIP-1C-3.

These are measurement tools, not authority. They must validate as a bounded contract, run
deterministically, never call a provider by themselves, and never create authority. The
rating sheet is explicitly search-quality feedback with no power over any CorpusItem.
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import semantic_benchmark as SB
from . import semantic_evaluation as SE
from . import semantic_evaluation_sheet as SS
from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection, SemanticIndexGeneration,
)
from .search_contract import SEARCH_SCOPES
from .semantic_query import SEMANTIC_FACETS
from .test_review_campaign import asset, brand

pytestmark = pytest.mark.django_db


def _authority():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count())


# === benchmark contract ==========================================================
def test_benchmark_validates_as_a_bounded_contract():
    assert SB.validate_benchmark() is True
    assert SB.BENCHMARK_SCHEMA == "intelligence_semantic_benchmark/1.0"


def test_query_ids_are_unique_and_facets_scopes_bounded():
    ids = [q.query_id for q in SB.BENCHMARK_QUERIES]
    assert len(ids) == len(set(ids))
    assert 20 <= len(ids) <= 40                      # a bounded, representative set
    for q in SB.BENCHMARK_QUERIES:
        assert q.facet in SEMANTIC_FACETS
        assert q.scope in SEARCH_SCOPES
        assert q.minimum_success_criteria.strip()
        assert q.prohibited_inference_notes


def test_relevance_labelling_is_category_level_not_fabricated_ground_truth():
    """No human has labelled this corpus, so no query may assert per-item ground truth."""
    assert SB.benchmark_document()["relevance_labelling"] == (
        "CATEGORY_LEVEL_ONLY_NO_HUMAN_GROUND_TRUTH")
    for q in SB.BENCHMARK_QUERIES:
        assert q.expected_external_key_prefixes == ()   # none invented


def test_queries_without_an_evidential_basis_are_marked():
    """Visual-content queries (floral/luxury/feminine) have nothing in the corpus to match;
    the benchmark says so rather than pretending."""
    flagged = {q.query_id for q in SB.BENCHMARK_QUERIES if q.expects_no_evidential_basis}
    assert {"Q07", "Q08", "Q09", "Q10", "Q11", "Q12"} <= flagged


def test_an_invalid_benchmark_is_rejected():
    bad = (SB.BENCHMARK_QUERIES[0], SB.BENCHMARK_QUERIES[0])     # duplicate ID
    with pytest.raises(ValueError):
        SB.validate_benchmark(bad)


# === evaluation ==================================================================
def test_category_hit_requires_the_label_when_one_is_expected():
    """Kind-only matching inflates precision to ~1.0 on every broad query, which would make
    a lexical-vs-semantic comparison meaningless."""
    kinds = {"a": "HISTORICAL_DESIGN", "b": "HISTORICAL_DESIGN"}
    labels = {"a": {"lip-colour"}, "b": {"concealer"}}
    query = next(q for q in SB.BENCHMARK_QUERIES if q.query_id == "Q03")   # lip-colour
    assert SE._category_hit("a", kinds, labels, query) is True
    assert SE._category_hit("b", kinds, labels, query) is False   # right kind, wrong label


def test_baseline_is_deterministic_and_writes_nothing():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    before = _authority()
    a = SE.evaluate(channels=("LEXICAL",))
    b = SE.evaluate(channels=("LEXICAL",))
    assert [q["channels"]["LEXICAL"]["top_ids"] for q in a["queries"]] == [
        q["channels"]["LEXICAL"]["top_ids"] for q in b["queries"]]
    assert _authority() == before
    assert SemanticIndexGeneration.objects.count() == 0


def test_evaluation_never_calls_a_provider_by_itself():
    """With no vector_provider supplied, evaluation must not embed anything."""
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    result = SE.evaluate(channels=("LEXICAL", "SEMANTIC"))
    for query in result["queries"]:
        # semantic cannot engage without a supplied vector, and must say so honestly
        assert query["channels"]["SEMANTIC"]["ranking_is_semantic"] is False


def test_evaluation_reports_no_statistical_significance_claim():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    result = SE.evaluate(channels=("LEXICAL",))
    assert "significance" in result["statistical_note"].lower()


def test_control_queries_bind_to_real_corpus_evidence():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    bound = {q.query_id: (text, expected)
             for q, text, expected in SE.bind_control_queries()}
    text, expected = bound["Q29"]
    assert text == rc.corpus_item.external_key      # bound to a real key, not invented
    assert expected == str(rc.corpus_item_id)


def test_operational_permission_stays_zero_across_every_channel():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    summary = SE.evaluate(channels=("LEXICAL",))["summary"]["LEXICAL"]
    assert summary["retrieval_allowed_total"] == 0
    assert summary["automatic_use_allowed_total"] == 0


# === document quality report =====================================================
def test_quality_report_excludes_identity_plumbing_from_meaningful_channels():
    for plumbing in ("external_key", "item_kind", "dataset_identifier", "schema_version"):
        assert plumbing not in SE.MEANINGFUL_CHANNELS


def test_quality_report_runs_and_writes_nothing():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    before = _authority()
    report = SE.document_quality_report()
    assert report["total_indexable_documents"] >= 1
    assert "meaningful_channel_definition" in report
    assert _authority() == before


# === human evaluation sheet: feedback only, never authority ======================
def test_sheet_is_search_feedback_and_creates_no_authority():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    evaluation = SE.evaluate(channels=("LEXICAL",))
    before = _authority()
    sheet = SS.build_evaluation_sheet(evaluation, channels=("LEXICAL",))
    assert sheet["schema_version"] == "intelligence_semantic_evaluation_sheet/1.0"
    assert sheet["creates_authority"] is False
    assert sheet["creates_decision_events"] is False
    assert sheet["creates_permissions"] is False
    assert sheet["persisted_in_authority_database"] is False
    assert "not approval" in sheet["disclaimer"].lower()
    assert _authority() == before


def test_sheet_ratings_are_bounded_and_never_pre_filled():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    sheet = SS.build_evaluation_sheet(SE.evaluate(channels=("LEXICAL",)),
                                      channels=("LEXICAL",))
    assert set(SS.RATINGS) == {"HIGHLY_RELEVANT", "RELEVANT", "PARTIALLY_RELEVANT",
                               "NOT_RELEVANT", "CANNOT_JUDGE"}
    for row in sheet["rows"]:
        assert row["rating"] == ""                     # the machine never guesses a rating
        assert row["allowed_ratings"] == list(SS.RATINGS)


def test_sheet_csv_is_bounded_and_carries_no_paths():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    sheet = SS.build_evaluation_sheet(SE.evaluate(channels=("LEXICAL",)),
                                      channels=("LEXICAL",))
    csv_text = SS.evaluation_sheet_csv(sheet)
    assert "query_id,query_text" in csv_text
    assert "/Users/" not in csv_text and "materials/" not in csv_text
