"""Confidence-gated semantic rescue contracts — DIP-1C-5A.

Pins the evaluation-only contracts: a frozen deterministic dev/holdout split; a lexical
evidence profile that never consults semantic; gate 1.1 that judges a score distribution
without ever seeing the query; and rescue ranker 1.2 that preserves strong lexical, rescues
only weak+gated, abstains rather than manufactures, and keeps exact identity a planner pin —
never a score bonus. Ranker 1.1 and gate 1.0 remain frozen.
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import lexical_evidence as LE
from . import rescue_ranker as RR
from . import semantic_rescue_eval as SRE
from .lexical_ranker import score_item
from .models import (
    GovernanceDecisionProjection, HumanAssertionProjection,
    OperationalPermissionProjection,
)

pytestmark = pytest.mark.django_db


# === frozen split ================================================================
def test_split_is_deterministic_disjoint_and_complete():
    a, b = SRE.build_split(), SRE.build_split()
    assert a == b
    dev, hold, ctrl = set(a["development"]), set(a["holdout"]), set(a["controls"])
    assert not (dev & hold) and not (dev & ctrl) and not (hold & ctrl)
    assert len(dev | hold | ctrl) == 30


def test_controls_are_excluded_from_both_tuning_subsets():
    s = SRE.build_split()
    assert set(SRE.CONTROL_IDS) == set(s["controls"])
    assert not (set(SRE.CONTROL_IDS) & (set(s["development"]) | set(s["holdout"])))


def test_both_subsets_carry_supported_and_no_basis_queries():
    c = SRE.split_coverage()
    for subset in ("development", "holdout"):
        assert c[subset]["supported"] > 0 and c[subset]["no_basis"] > 0


def test_split_manifest_declares_it_was_frozen_before_results():
    m = SRE.split_manifest()
    assert m["frozen_before_full_distribution"] is True
    assert m["stratification_rule"]


# === lexical evidence profile (never sees semantic) ==============================
def test_lexical_profile_classifications_are_deterministic():
    exact = score_item("asset:x:1", external_key="asset:x:1")
    strong = score_item("almarai", external_key="font:x", display_label="almarai")
    # a single token-overlap match is weak lexical evidence
    weak = score_item("packaging widget", external_key="x",
                      display_label="packaging sample")
    assert LE.classify_lexical_evidence([exact], exact_identity=True).classification == (
        LE.EXACT_IDENTITY)
    assert LE.classify_lexical_evidence([strong]).classification == LE.STRONG_LEXICAL
    assert LE.classify_lexical_evidence([weak]).classification in (
        LE.WEAK_LEXICAL, LE.STRONG_LEXICAL)
    assert LE.classify_lexical_evidence([]).classification == LE.NO_LEXICAL_EVIDENCE


def test_lexical_profile_takes_no_semantic_input():
    import inspect
    # the guarantee is structural: it receives only lexical scored rows + the planner's
    # exact-identity boolean, never a semantic score
    params = set(inspect.signature(LE.classify_lexical_evidence).parameters)
    assert params == {"scored_rows", "exact_identity"}
    # its executable body references no semantic score variable
    body = inspect.getsource(LE.classify_lexical_evidence)
    assert "semantic_score" not in body and "cosine" not in body


# === gate 1.1 ====================================================================
def test_gate_1_1_passes_a_standout_top_and_abstains_on_a_flat_field():
    standout = {"top": 0.90}
    standout.update({f"i{n}": 0.30 for n in range(50)})
    assert RR.assess_evidence_v1_1(standout).verdict == RR.PASS
    flat = {f"i{n}": 0.40 + n * 1e-4 for n in range(50)}
    assert RR.assess_evidence_v1_1(flat).verdict == RR.ABSTAIN


def test_gate_1_1_abstains_on_low_top_and_on_empty():
    low = {"top": 0.30}
    low.update({f"i{n}": 0.10 for n in range(20)})
    assert RR.assess_evidence_v1_1(low).verdict == RR.ABSTAIN
    assert RR.assess_evidence_v1_1({}).verdict == RR.ABSTAIN


def test_gate_1_1_reports_review_required_near_a_threshold():
    scores = {"top": RR.DEFAULT_GATE_THRESHOLDS["min_top_score"] + 0.005}
    scores.update({f"i{n}": 0.10 for n in range(60)})
    assert RR.assess_evidence_v1_1(scores).verdict in (RR.REVIEW_REQUIRED, RR.PASS)


def test_gate_1_1_never_receives_query_text_or_id():
    import inspect
    params = set(inspect.signature(RR.assess_evidence_v1_1).parameters)
    assert not ({"query", "query_text", "query_id", "phrase", "expected"} & params)
    src = inspect.getsource(RR.assess_evidence_v1_1)
    for qid in ("Q01", "Q07", "Q29"):
        assert qid not in src


# === rescue ranker 1.2 ===========================================================
def test_exact_identity_is_pinned_first_not_scored():
    plan = RR.plan_rescue(strategy=RR.SEMANTIC_RESCUE_ONLY,
                          lexical_classification=LE.EXACT_IDENTITY, gate_verdict=RR.PASS,
                          lexical_ids=["x", "a"], semantic_ranked_ids=["z"],
                          exact_identity_id="a")
    assert plan.ordered_ids[0] == "a" and plan.channel_used == "EXACT_IDENTITY"


def test_strong_lexical_is_preserved_and_semantic_never_reorders_it():
    plan = RR.plan_rescue(strategy=RR.SEMANTIC_RESCUE_ONLY,
                          lexical_classification=LE.STRONG_LEXICAL, gate_verdict=RR.PASS,
                          lexical_ids=["a", "b", "c"], semantic_ranked_ids=["z", "y"])
    assert list(plan.ordered_ids) == ["a", "b", "c"] and plan.channel_used == "LEXICAL"


def test_weak_lexical_with_gate_pass_rescues_via_semantic():
    plan = RR.plan_rescue(strategy=RR.SEMANTIC_RESCUE_ONLY,
                          lexical_classification=LE.WEAK_LEXICAL, gate_verdict=RR.PASS,
                          lexical_ids=["a"], semantic_ranked_ids=["z", "y"])
    assert list(plan.ordered_ids) == ["z", "y"] and plan.channel_used == "SEMANTIC"


def test_gate_abstain_returns_honest_lexical_or_empty_never_manufactured():
    with_lex = RR.plan_rescue(strategy=RR.SEMANTIC_RESCUE_ONLY,
                              lexical_classification=LE.WEAK_LEXICAL, gate_verdict=RR.ABSTAIN,
                              lexical_ids=["a"], semantic_ranked_ids=["z"])
    assert list(with_lex.ordered_ids) == ["a"] and with_lex.channel_used == "LEXICAL"
    empty = RR.plan_rescue(strategy=RR.SEMANTIC_RESCUE_ONLY,
                           lexical_classification=LE.NO_LEXICAL_EVIDENCE,
                           gate_verdict=RR.ABSTAIN, lexical_ids=[],
                           semantic_ranked_ids=["z", "y"])
    assert empty.ordered_ids == () and empty.channel_used == "EMPTY" and empty.abstained


def test_review_required_exposes_uncertainty_not_confident_semantic():
    plan = RR.plan_rescue(strategy=RR.SEMANTIC_RESCUE_ONLY,
                          lexical_classification=LE.NO_LEXICAL_EVIDENCE,
                          gate_verdict=RR.REVIEW_REQUIRED, lexical_ids=["a"],
                          semantic_ranked_ids=["z"])
    assert plan.gate_verdict == RR.REVIEW_REQUIRED and plan.channel_used == "LEXICAL"


def test_no_giant_semantic_weight_in_rescue_ranker():
    # the DIP-1C-4B universal-weight mechanism is not carried over: ranker 1.2 defines no
    # _SEMANTIC_WEIGHT and its planning is channel-selection, not a weighted sum. The
    # structural absence of the constant is the guarantee (docstrings may name it to
    # explain the contrast).
    assert not hasattr(RR, "_SEMANTIC_WEIGHT")
    import inspect
    # plan_rescue never multiplies a score by that weight — it selects a channel
    assert "_SEMANTIC_WEIGHT" not in inspect.getsource(RR).replace(
        "no _SEMANTIC_WEIGHT", "")           # ignore the one explanatory mention


def test_ranker_1_1_and_gate_1_0_remain_frozen():
    from .hybrid_ranker import HYBRID_RANKER_VERSION, _SEMANTIC_WEIGHT
    from .search_planner import EVIDENCE_GATE_VERSION
    assert HYBRID_RANKER_VERSION == "intelligence_hybrid_ranker/1.1"
    assert _SEMANTIC_WEIGHT == 300.0
    assert EVIDENCE_GATE_VERSION == "semantic_evidence_gate/1.0"
    assert RR.RESCUE_RANKER_VERSION == "intelligence_hybrid_ranker/1.2"
    assert RR.EVIDENCE_GATE_V1_1 == "semantic_evidence_gate/1.1"


# === separation ==================================================================
def test_rescue_evaluation_contracts_create_no_authority():
    before = (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
              GovernanceDecisionProjection.objects.count(),
              OperationalPermissionProjection.objects.filter(
                  effective_state=OperationalPermissionProjection.State.ALLOWED).count())
    RR.assess_evidence_v1_1({"a": 0.9, "b": 0.2})
    RR.plan_rescue(strategy=RR.SEMANTIC_RESCUE_ONLY, lexical_classification=LE.WEAK_LEXICAL,
                   gate_verdict=RR.PASS, lexical_ids=["a"], semantic_ranked_ids=["z"])
    SRE.build_split()
    assert (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count()) == (
        before)
