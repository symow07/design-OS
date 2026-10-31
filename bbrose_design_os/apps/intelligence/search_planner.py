"""Exact-identity search planning and semantic abstention — DIP-1C-4A.

Two separately versioned contracts, both answering failures the DIP-1C-3 pilot measured.

**`intelligence_search_planner/1.0` — exact identity is not similarity.**
The pilot's Q29 control failed under semantic ranking: an exact stable-key query did not
return its own item first, because cosine has no notion of "this IS the thing you named".
Identity lookup is an *identity operation*, so the planner resolves it deterministically and
pins the match ahead of ranking, in every mode. It is emphatically **not** implemented as a
huge hidden semantic weight — a weight is a nudge that a strong enough similarity can
outvote; a pin is an answer.

**`semantic_evidence_gate/1.0` — abstention.**
The pilot's sharpest finding: because every query has a vector and cosine ranks all 176
items, semantic search *always* returned ten confident results — including for `luxury
elegant style` and `modern geometric packaging`, concepts this corpus records nothing about.
It manufactured answers. Lexical's honest empties were more truthful. This gate lets semantic
say "I have no evidential basis" instead.

**The gate's thresholds are DEFINED and MEASURED here, not activated.** Tuning cut-offs
against the same 30 benchmark queries they would be judged on is overfitting; §9 forbids it.
`DEFAULT_THRESHOLDS` are candidates for the next authorized pilot to evaluate and approve.
"""
from __future__ import annotations

import dataclasses
import statistics

SEARCH_PLANNER_VERSION = "intelligence_search_planner/1.0"
EVIDENCE_GATE_VERSION = "semantic_evidence_gate/1.0"

# --- planner ---------------------------------------------------------------------
EXACT_IDENTITY_MATCH = "EXACT_IDENTITY_MATCH"
EXACT_STABLE_KEY = "EXACT_STABLE_KEY"
EXACT_DISPLAY_LABEL = "EXACT_DISPLAY_LABEL"


def _normalize(text):
    return " ".join((text or "").strip().lower().split())


def plan_exact_identity(query_text, *, keys_by_id, labels_by_id):
    """Resolve an exact identity match, or None.

    `keys_by_id` / `labels_by_id` are pre-loaded {corpus_item_id: value} maps. Returns
    (corpus_item_id, reason) where reason names which identity matched.
    """
    needle = _normalize(query_text)
    if not needle:
        return None
    for item_id, key in keys_by_id.items():
        if _normalize(key) == needle:
            return item_id, EXACT_STABLE_KEY
    for item_id, label in labels_by_id.items():
        if label and _normalize(label) == needle:
            return item_id, EXACT_DISPLAY_LABEL
    return None


def apply_identity_pin(rows, pinned_id, *, id_field="corpus_item_id"):
    """Move the exact-identity match to rank 1 and mark its reason.

    A deterministic pin, applied after ranking and before paging. Semantic scores stay
    visible for diagnostics; they simply cannot displace an identity answer.
    """
    if not pinned_id:
        return rows
    pinned = [r for r in rows if r.get(id_field) == pinned_id]
    if not pinned:
        return rows
    rest = [r for r in rows if r.get(id_field) != pinned_id]
    for row in pinned:
        reasons = list(row.get("match_reasons", []))
        if EXACT_IDENTITY_MATCH not in reasons:
            reasons.insert(0, EXACT_IDENTITY_MATCH)
        row["match_reasons"] = reasons
        row["exact_identity_match"] = True
    return pinned + rest


# --- abstention gate -------------------------------------------------------------
SEMANTIC_NO_EVIDENTIAL_BASIS = "SEMANTIC_NO_EVIDENTIAL_BASIS"
SEMANTIC_EVIDENCE_SUFFICIENT = "SEMANTIC_EVIDENCE_SUFFICIENT"

# Candidate thresholds — DEFINED, NOT ACTIVATED. Deliberately not fitted to the benchmark.
DEFAULT_THRESHOLDS = {
    "min_top_score": 0.50,          # a top hit below this resembles nothing in particular
    "min_top_to_median_margin": 0.08,   # the top must stand out from the corpus middle
    "min_top_to_second_margin": 0.0,    # not used by default; measured for the next pilot
    "require_facet_consistency": True,
}


@dataclasses.dataclass(frozen=True)
class EvidenceAssessment:
    version: str
    verdict: str
    top_score: float | None
    median_score: float | None
    score_spread: float | None
    top_to_median_margin: float | None
    top_to_second_margin: float | None
    item_kind_consistent: bool | None
    facet_consistent: bool | None
    thresholds_applied: dict
    activated: bool

    def as_dict(self):
        return dataclasses.asdict(self)


def assess_semantic_evidence(scores, *, kinds_by_id=None, expected_kinds=(),
                             thresholds=None, activate=False) -> EvidenceAssessment:
    """Measure whether a semantic result set has an evidential basis.

    `activate=False` (the default) MEASURES and reports without changing behaviour — that is
    how thresholds get evidence before they get power. No query id or benchmark phrase is
    special-cased; the gate sees only scores.
    """
    thresholds = dict(thresholds or DEFAULT_THRESHOLDS)
    if not scores:
        return EvidenceAssessment(
            version=EVIDENCE_GATE_VERSION, verdict=SEMANTIC_NO_EVIDENTIAL_BASIS,
            top_score=None, median_score=None, score_spread=None,
            top_to_median_margin=None, top_to_second_margin=None,
            item_kind_consistent=None, facet_consistent=None,
            thresholds_applied=thresholds, activated=activate)

    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    values = [v for _, v in ordered]
    top = values[0]
    second = values[1] if len(values) > 1 else None
    median = statistics.median(values)
    spread = max(values) - min(values)
    top_median_margin = top - median
    top_second_margin = (top - second) if second is not None else None

    kind_consistent = None
    if kinds_by_id and expected_kinds:
        top_kinds = [kinds_by_id.get(i) for i, _ in ordered[:5]]
        kind_consistent = any(k in expected_kinds for k in top_kinds if k)

    verdict = SEMANTIC_EVIDENCE_SUFFICIENT
    if top < thresholds["min_top_score"]:
        verdict = SEMANTIC_NO_EVIDENTIAL_BASIS
    elif top_median_margin < thresholds["min_top_to_median_margin"]:
        verdict = SEMANTIC_NO_EVIDENTIAL_BASIS
    elif (thresholds.get("require_facet_consistency") and kind_consistent is False):
        verdict = SEMANTIC_NO_EVIDENTIAL_BASIS

    return EvidenceAssessment(
        version=EVIDENCE_GATE_VERSION, verdict=verdict, top_score=round(top, 4),
        median_score=round(median, 4), score_spread=round(spread, 4),
        top_to_median_margin=round(top_median_margin, 4),
        top_to_second_margin=round(top_second_margin, 4) if top_second_margin is not None
        else None,
        item_kind_consistent=kind_consistent, facet_consistent=kind_consistent,
        thresholds_applied=thresholds, activated=activate)
