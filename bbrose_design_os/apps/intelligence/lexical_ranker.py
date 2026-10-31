"""Deterministic lexical ranking — DIP-1B-6 (`intelligence_lexical_ranker/1.0`).

**This is lexical and metadata matching. It is not semantic search.** There are no
embeddings, no vector index, no learned weights and no model call anywhere in this module.
Calling it "semantic" would misdescribe the capability to every downstream reader, so the
name says exactly what it does. Semantic retrieval is a future milestone with its own
validation.

Ranking is a pure function of stable evidence:

1. exact stable-key match          2. exact display-label match
3. prefix match                    4. normalized token overlap
5. observed-fact label match       6. machine-classification label match
7. verified human-assertion label match

It deliberately does **not** consider database row order, mutable legacy approval fields,
wall-clock time, randomness, or a machine `candidate_kind` (a label that must never
influence lineage or rank). Ties break on canonical CorpusItem UUID, so the same corpus
state always produces the same order.
"""
from __future__ import annotations

import dataclasses
import re

RANKER_VERSION = "intelligence_lexical_ranker/1.0"

# match reasons, ordered by strength; the emitted order is normalised to this
R_EXACT_KEY = "EXACT_STABLE_KEY_MATCH"
R_EXACT_LABEL = "EXACT_DISPLAY_LABEL_MATCH"
R_PREFIX_KEY = "STABLE_KEY_PREFIX_MATCH"
R_PREFIX_LABEL = "DISPLAY_LABEL_PREFIX_MATCH"
R_TOKEN = "TOKEN_OVERLAP"
R_FACT = "OBSERVED_FACT_LABEL_MATCH"
R_MACHINE = "MACHINE_CLASSIFICATION_LABEL_MATCH"
R_HUMAN = "VERIFIED_HUMAN_ASSERTION_LABEL_MATCH"
R_FILTER_ONLY = "FILTER_MATCH_ONLY"

_REASON_ORDER = (
    R_EXACT_KEY, R_EXACT_LABEL, R_PREFIX_KEY, R_PREFIX_LABEL, R_TOKEN,
    R_FACT, R_MACHINE, R_HUMAN, R_FILTER_ONLY,
)

# fixed, documented weights — not learned, not tuned at runtime
_WEIGHTS = {
    R_EXACT_KEY: 1000,
    R_EXACT_LABEL: 500,
    R_PREFIX_KEY: 200,
    R_PREFIX_LABEL: 150,
    R_TOKEN: 40,          # multiplied by the number of overlapping tokens
    R_FACT: 25,
    R_MACHINE: 10,        # machine output ranks LOW: it is not human truth
    R_HUMAN: 60,          # a verified human assertion outranks any machine label
    R_FILTER_ONLY: 0,
}

_TOKEN = re.compile(r"[a-z0-9]+")


def normalize_tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall((text or "").lower()))


def _normalize(text: str) -> str:
    return " ".join(normalize_tokens(text))


@dataclasses.dataclass(frozen=True)
class MatchScore:
    score: int
    reasons: tuple[str, ...]

    @property
    def matched(self) -> bool:
        return bool(self.reasons)


def score_item(query: str, *, external_key: str = "", display_label: str = "",
               fact_labels=(), machine_labels=(), human_labels=()) -> MatchScore:
    """Deterministic score for one item against one query.

    An empty query matches everything with score 0 and reason FILTER_MATCH_ONLY: browsing
    with filters only is a legitimate search, and it must not fabricate relevance.
    """
    normalized_query = _normalize(query)
    if not normalized_query:
        return MatchScore(0, (R_FILTER_ONLY,))

    query_tokens = set(normalize_tokens(query))
    key_norm = _normalize(external_key)
    label_norm = _normalize(display_label)
    score, reasons = 0, []

    if normalized_query == key_norm:
        score += _WEIGHTS[R_EXACT_KEY]
        reasons.append(R_EXACT_KEY)
    elif key_norm.startswith(normalized_query) or normalized_query in key_norm:
        score += _WEIGHTS[R_PREFIX_KEY]
        reasons.append(R_PREFIX_KEY)

    if normalized_query == label_norm and label_norm:
        score += _WEIGHTS[R_EXACT_LABEL]
        reasons.append(R_EXACT_LABEL)
    elif label_norm and (label_norm.startswith(normalized_query)
                         or normalized_query in label_norm):
        score += _WEIGHTS[R_PREFIX_LABEL]
        reasons.append(R_PREFIX_LABEL)

    overlap = query_tokens & (set(normalize_tokens(external_key))
                              | set(normalize_tokens(display_label)))
    if overlap and R_EXACT_KEY not in reasons and R_EXACT_LABEL not in reasons:
        score += _WEIGHTS[R_TOKEN] * len(overlap)
        reasons.append(R_TOKEN)

    for labels, reason in ((fact_labels, R_FACT), (machine_labels, R_MACHINE),
                           (human_labels, R_HUMAN)):
        if any(query_tokens & set(normalize_tokens(label)) for label in labels):
            score += _WEIGHTS[reason]
            reasons.append(reason)

    ordered = tuple(r for r in _REASON_ORDER if r in reasons)
    return MatchScore(score, ordered)


def sort_key(score: MatchScore, corpus_item_id: str, *, by_identity: bool = False):
    """Stable ordering. The canonical UUID is the final tie-break, so ranking never
    depends on database row order."""
    if by_identity:
        return (str(corpus_item_id),)
    return (-score.score, str(corpus_item_id))
