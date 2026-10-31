"""Confidence-gated semantic rescue — DIP-1C-5A.

Two new versioned, evaluation-only contracts. Neither is wired into the production search
path in this slice; `intelligence_hybrid_ranker/1.1` and `semantic_evidence_gate/1.0` remain
frozen and reproducible.

**`semantic_evidence_gate/1.1`** — the DIP-1C-4B finding was that gate 1.0, judged on a
top-10 view, could not tell "the corpus has something for this" from "cosine ranked ten
arbitrary neighbours". Gate 1.1 judges the **full corpus score distribution**: a query has an
evidential basis only when its top result stands out from the whole distribution, not merely
from the returned page. It never sees the query text, id, expected answer, human label,
lexical identity, permission, or legacy state.

**`intelligence_hybrid_ranker/1.2`** — a confidence-gated *rescue* strategy, not a universal
weighted sum. The DIP-1C-4B lesson: adding `300 × cosine` to every result diluted strong
lexical rankings below rank 1. Ranker 1.2 instead preserves lexical ordering when lexical
evidence is strong, and consults semantic only when lexical is weak/absent AND the gate
passes — otherwise it returns the honest lexical result or nothing, never a manufactured
nearest neighbour. Exact identity is always the planner's pin, never a score.
"""
from __future__ import annotations

import dataclasses
import statistics

from .lexical_evidence import (
    EXACT_IDENTITY, NO_LEXICAL_EVIDENCE, STRONG_LEXICAL, WEAK_LEXICAL,
)

EVIDENCE_GATE_V1_1 = "semantic_evidence_gate/1.1"
RESCUE_RANKER_VERSION = "intelligence_hybrid_ranker/1.2"

# gate outcomes
PASS = "PASS"
ABSTAIN = "ABSTAIN"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
SEMANTIC_NO_EVIDENTIAL_BASIS = "SEMANTIC_NO_EVIDENTIAL_BASIS"

# candidate rescue strategies (declared; one is selected on DEVELOPMENT, then frozen)
SEMANTIC_RESCUE_ONLY = "SEMANTIC_RESCUE_ONLY"
GATED_RECIPROCAL_RANK_FUSION = "GATED_RECIPROCAL_RANK_FUSION"
GATED_NORMALIZED_BLEND = "GATED_NORMALIZED_BLEND"
CANDIDATE_STRATEGIES = (SEMANTIC_RESCUE_ONLY, GATED_RECIPROCAL_RANK_FUSION,
                        GATED_NORMALIZED_BLEND)

# gate 1.1 candidate thresholds over full-distribution features (declared, evaluated on
# DEVELOPMENT, then frozen — never fitted to HOLDOUT)
DEFAULT_GATE_THRESHOLDS = {
    "min_top_score": 0.55,
    "min_top_to_median_margin": 0.12,
    "min_top_percentile": 0.90,        # top must sit in the corpus's high tail
    "review_band": 0.03,               # within this of a threshold → REVIEW_REQUIRED
}
_RRF_CONSTANT = 60                     # fixed, documented; not tuned per query


@dataclasses.dataclass(frozen=True)
class GateAssessment:
    version: str
    verdict: str
    top_score: float | None
    median_score: float | None
    top_to_median_margin: float | None
    top_to_second_margin: float | None
    top_percentile: float | None
    score_spread: float | None
    facet_consistent: bool | None
    top_tied_group_size: int | None
    thresholds: dict

    def as_dict(self):
        return dataclasses.asdict(self)


def assess_evidence_v1_1(full_scores, *, kinds_by_id=None, expected_kinds=(),
                         top_group_size=1, thresholds=None) -> GateAssessment:
    """Judge the FULL corpus score distribution. `full_scores`: {item_id: cosine} over the
    whole indexable corpus, not a page. Evaluation-only; sees no query text/id."""
    thresholds = dict(thresholds or DEFAULT_GATE_THRESHOLDS)
    if not full_scores:
        return GateAssessment(EVIDENCE_GATE_V1_1, ABSTAIN, None, None, None, None, None,
                              None, None, top_tied_group_size=None, thresholds=thresholds)
    ordered = sorted(full_scores.values(), reverse=True)
    top = ordered[0]
    second = ordered[1] if len(ordered) > 1 else top
    median = statistics.median(ordered)
    spread = top - min(ordered)
    margin = top - median
    # fraction of the corpus strictly below the top score
    percentile = sum(1 for s in ordered if s < top) / len(ordered)

    facet_consistent = None
    if kinds_by_id and expected_kinds:
        top_id = max(full_scores, key=lambda i: full_scores[i])
        facet_consistent = kinds_by_id.get(top_id) in expected_kinds

    def _below(value, key):
        return value < thresholds[key]

    def _near(value, key):
        return abs(value - thresholds[key]) <= thresholds["review_band"]

    verdict = PASS
    if (_below(top, "min_top_score") or _below(margin, "min_top_to_median_margin")
            or _below(percentile, "min_top_percentile")):
        verdict = ABSTAIN
    elif (_near(top, "min_top_score") or _near(margin, "min_top_to_median_margin")
          or facet_consistent is False):
        verdict = REVIEW_REQUIRED

    return GateAssessment(
        EVIDENCE_GATE_V1_1, verdict, round(top, 4), round(median, 4), round(margin, 4),
        round(top - second, 4), round(percentile, 4), round(spread, 4),
        facet_consistent, top_tied_group_size=top_group_size, thresholds=thresholds)


@dataclasses.dataclass(frozen=True)
class RescuePlan:
    version: str
    strategy: str
    lexical_classification: str
    gate_verdict: str
    channel_used: str          # LEXICAL | SEMANTIC | FUSION | EMPTY | EXACT_IDENTITY
    ordered_ids: tuple[str, ...]
    abstained: bool

    def as_dict(self):
        return dataclasses.asdict(self)


def plan_rescue(*, strategy, lexical_classification, gate_verdict, lexical_ids,
                semantic_ranked_ids, exact_identity_id=None, k=10) -> RescuePlan:
    """Deterministic confidence-gated plan. No score bonus, no _SEMANTIC_WEIGHT.

    `lexical_ids` / `semantic_ranked_ids`: ranked id lists (already tie-broken by UUID).
    """
    # 1. exact identity always wins, via the planner's pin
    if exact_identity_id is not None:
        rest = [i for i in lexical_ids if i != exact_identity_id]
        return RescuePlan(RESCUE_RANKER_VERSION, strategy, EXACT_IDENTITY, gate_verdict,
                          "EXACT_IDENTITY",
                          tuple([exact_identity_id] + rest)[:k], abstained=False)

    # 2. strong lexical → lexical ordering preserved; semantic never reorders it
    if lexical_classification == STRONG_LEXICAL:
        return RescuePlan(RESCUE_RANKER_VERSION, strategy, lexical_classification,
                          gate_verdict, "LEXICAL", tuple(lexical_ids[:k]), abstained=False)

    # 3. weak / absent lexical → consult the gate
    if lexical_classification in (WEAK_LEXICAL, NO_LEXICAL_EVIDENCE):
        if gate_verdict == PASS:
            if strategy == SEMANTIC_RESCUE_ONLY:
                order = semantic_ranked_ids
            elif strategy == GATED_RECIPROCAL_RANK_FUSION:
                order = _rrf(lexical_ids, semantic_ranked_ids)
            else:  # GATED_NORMALIZED_BLEND — deterministic, semantic-led when lexical weak
                order = _dedupe(list(semantic_ranked_ids) + list(lexical_ids))
            return RescuePlan(RESCUE_RANKER_VERSION, strategy, lexical_classification,
                              gate_verdict, "SEMANTIC" if strategy == SEMANTIC_RESCUE_ONLY
                              else "FUSION", tuple(order[:k]), abstained=False)
        if gate_verdict == REVIEW_REQUIRED:
            # expose uncertainty: return the honest lexical result, flagged, not confident
            return RescuePlan(RESCUE_RANKER_VERSION, strategy, lexical_classification,
                              gate_verdict, "LEXICAL", tuple(lexical_ids[:k]),
                              abstained=False)
        # ABSTAIN → honest lexical result, or empty if there is none. Never manufacture.
        return RescuePlan(RESCUE_RANKER_VERSION, strategy, lexical_classification,
                          gate_verdict, "LEXICAL" if lexical_ids else "EMPTY",
                          tuple(lexical_ids[:k]), abstained=not lexical_ids)

    return RescuePlan(RESCUE_RANKER_VERSION, strategy, lexical_classification, gate_verdict,
                      "LEXICAL", tuple(lexical_ids[:k]), abstained=False)


def _dedupe(ids):
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _rrf(lexical_ids, semantic_ids):
    """Reciprocal rank fusion with a fixed constant; both rank lists stay visible."""
    scores = {}
    for rank, i in enumerate(lexical_ids):
        scores[i] = scores.get(i, 0.0) + 1.0 / (_RRF_CONSTANT + rank + 1)
    for rank, i in enumerate(semantic_ids):
        scores[i] = scores.get(i, 0.0) + 1.0 / (_RRF_CONSTANT + rank + 1)
    # deterministic: score desc, then id asc
    return [i for i, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]
