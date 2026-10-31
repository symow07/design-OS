"""Lexical confidence contract — DIP-1C-5A (`lexical_evidence_profile/1.0`).

Classifies how strong a query's LEXICAL evidence is, using only transparent lexical signals.
This is the switch that decides whether semantic is even consulted: strong lexical evidence
keeps lexical ordering; weak or absent lexical evidence is what a semantic *rescue* is for.

It never inspects semantic scores (that would defeat the point — the whole idea is to gate
semantic on lexical weakness, measured independently), never sees the query id or a
benchmark phrase, and never makes exact-identity decisions (those belong to
`intelligence_search_planner/1.0`).
"""
from __future__ import annotations

import dataclasses

from .lexical_ranker import (
    R_EXACT_KEY, R_EXACT_LABEL, R_FILTER_ONLY, R_PREFIX_KEY, R_PREFIX_LABEL,
)

PROFILE_VERSION = "lexical_evidence_profile/1.0"

EXACT_IDENTITY = "EXACT_IDENTITY"
STRONG_LEXICAL = "STRONG_LEXICAL"
WEAK_LEXICAL = "WEAK_LEXICAL"
NO_LEXICAL_EVIDENCE = "NO_LEXICAL_EVIDENCE"

# transparent, documented thresholds over lexical signals only
_STRONG_MIN_SCORE = 150           # a prefix-label match or better clears this
_STRONG_MIN_MATCHES = 3           # or several independent positive lexical matches


@dataclasses.dataclass(frozen=True)
class LexicalEvidence:
    version: str
    classification: str
    top_score: int
    second_score: int
    top_to_second_margin: int
    positive_match_count: int
    has_exact_identity: bool
    matched_reason_kinds: tuple[str, ...]

    def as_dict(self):
        return dataclasses.asdict(self)


def classify_lexical_evidence(scored_rows, *, exact_identity=False) -> LexicalEvidence:
    """`scored_rows`: iterable of MatchScore (from lexical_ranker.score_item), already the
    lexical result set for this query. Exact identity is decided by the planner and passed
    in; it is never inferred from a semantic score."""
    rows = [s for s in scored_rows if s.matched]
    scores = sorted((s.score for s in rows), reverse=True)
    top = scores[0] if scores else 0
    second = scores[1] if len(scores) > 1 else 0
    # a "positive" lexical match is one with a real lexical reason, not filter-only
    positive = sum(1 for s in rows
                   if any(r != R_FILTER_ONLY for r in s.reasons))
    reason_kinds = set()
    for s in rows:
        reason_kinds.update(s.reasons)

    if exact_identity:
        classification = EXACT_IDENTITY
    elif not positive:
        classification = NO_LEXICAL_EVIDENCE
    elif (any(r in reason_kinds for r in (R_EXACT_KEY, R_EXACT_LABEL, R_PREFIX_KEY,
                                          R_PREFIX_LABEL))
          or top >= _STRONG_MIN_SCORE or positive >= _STRONG_MIN_MATCHES):
        classification = STRONG_LEXICAL
    else:
        classification = WEAK_LEXICAL

    return LexicalEvidence(
        version=PROFILE_VERSION, classification=classification, top_score=top,
        second_score=second, top_to_second_margin=top - second,
        positive_match_count=positive,
        has_exact_identity=bool(exact_identity),
        matched_reason_kinds=tuple(sorted(reason_kinds)))
