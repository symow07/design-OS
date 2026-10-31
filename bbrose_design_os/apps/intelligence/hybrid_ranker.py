"""Hybrid lexical + semantic ranking — DIP-1C-1 (`intelligence_hybrid_ranker/1.0`).

Combines the deterministic `intelligence_lexical_ranker/1.0` score with a semantic cosine
score from the published embedding index. The two scores are **always reported separately**
so a reader can see what each channel contributed; the blended figure is only for ordering.

What ranking may combine: lexical score, semantic similarity, an exact-identity bonus, and
explicit filter matches. What it must never use: legacy approval state, operational
permission as a relevance boost, randomness, wall-clock time, or any generative-model
judgement. Permission decides *eligibility* in operational modes — never *relevance*. Ties
break on the canonical CorpusItem UUID.
"""
from __future__ import annotations

HYBRID_RANKER_VERSION = "intelligence_hybrid_ranker/1.1"

# fixed blend weights (documented, not learned). Lexical exactness dominates; semantic
# similarity (0..1) is scaled to sit alongside lexical token/label scores.
# UNCHANGED from 1.0 — HYBRID ordering keeps exactly its frozen 1.0 meaning.
_LEXICAL_WEIGHT = 1.0
_SEMANTIC_WEIGHT = 300.0

R_SEMANTIC = "SEMANTIC_SIMILARITY"

# What changed in 1.1, and only this: SEMANTIC-only ordering no longer folds the lexical
# score in. In 1.0 every semantic-engaged result was blended, so a "semantic" ranking
# quietly carried lexical weight — which DIP-1C-2 forbids. HYBRID's formula is byte-for-byte
# the 1.0 blend, so previously frozen hybrid results keep their meaning; only SEMANTIC's
# ordering changes, which is why the version advances rather than mutating 1.0 silently.
RANK_MODE_LEXICAL = "LEXICAL"
RANK_MODE_SEMANTIC = "SEMANTIC"
RANK_MODE_HYBRID = "HYBRID"


def blended_score(lexical_score: int, semantic_score, *, use_semantic: bool,
                  rank_mode: str = RANK_MODE_HYBRID) -> float:
    """Deterministic score for ordering.

    * LEXICAL — the lexical score alone.
    * HYBRID  — lexical + weighted semantic (identical to 1.0).
    * SEMANTIC — the semantic score ALONE. The lexical score is still reported as a
      diagnostic, but it must not influence semantic-only ordering.

    When semantic is unavailable, HYBRID degrades to exactly the lexical score, so HYBRID
    with no index equals LEXICAL with no drift.
    """
    if rank_mode == RANK_MODE_SEMANTIC:
        if not use_semantic or semantic_score is None:
            return 0.0
        return _SEMANTIC_WEIGHT * float(semantic_score)
    total = _LEXICAL_WEIGHT * float(lexical_score)
    if use_semantic and semantic_score is not None:
        total += _SEMANTIC_WEIGHT * float(semantic_score)
    return total


def merge_reasons(lexical_reasons, semantic_score, *, use_semantic: bool):
    reasons = list(lexical_reasons)
    if use_semantic and semantic_score is not None:
        reasons.append(R_SEMANTIC)
    return reasons
