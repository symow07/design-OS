"""Search contract + lexical ranker — DIP-1B-6.

The contract is a closed vocabulary: it accepts a bounded query or refuses it, and it never
approximates. The ranker is deterministic lexical matching with a stable UUID tie-break —
no embeddings, no row-order dependence, no machine label influencing rank.
"""
from __future__ import annotations

import pytest

from . import lexical_ranker as LR
from . import search_contract as SC


# === contract: accepts bounded, refuses everything else =========================
def test_defaults_are_reviewer_corpus_score():
    q = SC.build_search_query({})
    assert q.mode == SC.REVIEWER_CANDIDATE_SEARCH
    assert q.scope == SC.CORPUS_SCOPE
    assert q.order_by == SC.ORDER_BY_SCORE
    assert q.limit == SC.DEFAULT_LIMIT


def test_valid_bounded_query_is_accepted_and_normalized():
    q = SC.build_search_query({
        "query": "  Brand Logo  ", "mode": SC.OPERATIONAL_RETRIEVAL,
        "item_kinds": ["DESIGN_ASSET", "DESIGN_ASSET", "BRAND_ASSET"],
        "waves": ["WAVE_4_BRAND_AND_PALETTE_TRIAGE"], "limit": 10})
    assert q.query == "Brand Logo"
    # de-duplicated and sorted, so the same request always means the same query
    assert q.item_kinds == ("BRAND_ASSET", "DESIGN_ASSET")


@pytest.mark.parametrize("raw", [
    {"mode": "SEMANTIC_SEARCH"},                 # unsupported mode
    {"scope": "EVERYTHING"},
    {"order_by": "RANDOM"},
    {"item_kinds": ["NOT_A_KIND"]},
    {"waves": ["WAVE_9"]},
    {"readiness_states": ["APPROVED"]},
    {"blocker_codes": ["WHATEVER"]},
    {"limit": 101},                              # unbounded limit refused
    {"limit": 0},
    {"limit": "; DROP TABLE"},
    {"sql": "1=1"},                              # arbitrary field name refused
    {"filter": {"any": "json"}},
    {"order_by": "score; delete"},
])
def test_unhonourable_queries_are_refused(raw):
    with pytest.raises(SC.SearchContractError):
        SC.build_search_query(raw)


def test_free_labels_are_bounded_text_not_field_names():
    q = SC.build_search_query({"product_family_labels": ["lip-colour", "lip-colour"]})
    assert q.product_family_labels == ("lip-colour",)
    with pytest.raises(SC.SearchContractError):
        SC.build_search_query({"candidate_labels": ["x" * 101]})


def test_query_text_length_is_bounded():
    with pytest.raises(SC.SearchContractError):
        SC.build_search_query({"query": "a" * 201})


# === ranker: deterministic, lexical, stable-tie-broken ==========================
def test_exact_key_beats_prefix_beats_token():
    exact = LR.score_item("asset:brand:1", external_key="asset:brand:1")
    prefix = LR.score_item("asset:brand", external_key="asset:brand:1")
    token = LR.score_item("brand", external_key="asset:brand:1")
    assert exact.score > prefix.score > token.score
    assert exact.reasons[0] == LR.R_EXACT_KEY


def test_empty_query_matches_with_filter_only_reason_and_zero_score():
    s = LR.score_item("", external_key="anything", display_label="Any Label")
    assert s.matched and s.score == 0
    assert s.reasons == (LR.R_FILTER_ONLY,)


def test_machine_label_ranks_below_human_assertion():
    machine = LR.score_item("logo", external_key="x", display_label="",
                            machine_labels=["logo"])
    human = LR.score_item("logo", external_key="x", display_label="",
                          human_labels=["logo"])
    assert human.score > machine.score          # human truth outranks a machine guess


def test_reasons_are_emitted_in_normalized_order():
    s = LR.score_item("brand graphic", external_key="asset:brand:1",
                      display_label="brand graphic", fact_labels=["brand"])
    assert list(s.reasons) == [r for r in LR._REASON_ORDER if r in s.reasons]


def test_uuid_tiebreak_is_stable_and_independent_of_row_order():
    s = LR.score_item("brand", external_key="asset:brand:1")
    a = LR.sort_key(s, "00000000-0000-0000-0000-000000000002")
    b = LR.sort_key(s, "00000000-0000-0000-0000-000000000001")
    assert b < a                                # same score → UUID decides, deterministically
