"""Normalized cosine similarity — DIP-1C-1.

Exact in-memory numpy scan. At the bounded Phase-1 corpus size (~176 items) a brute-force
cosine over every published embedding is instantaneous and fully deterministic; there is no
ANN approximation and no randomization. Ranking ties break on the canonical CorpusItem
UUID, so identical scores always order identically.

**Scale note:** this is the bounded Phase-1 MVP, not the final large-scale vector
architecture. Reconsider an indexed vector store (pgvector or equivalent) when the published
embedding count approaches ~50,000 — beyond that an exact per-query scan stops being
negligible. Below it, exactness and determinism are worth more than an index.
"""
from __future__ import annotations

import math

RECONSIDER_INDEXED_STORE_ABOVE = 50_000


class SimilarityError(ValueError):
    pass


def _validate(vector, name):
    if not isinstance(vector, (list, tuple)) or not vector:
        raise SimilarityError(f"{name} must be a non-empty numeric vector")
    for component in vector:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise SimilarityError(f"{name} components must be numbers")
        if not math.isfinite(component):
            raise SimilarityError(f"{name} components must be finite")


def cosine_similarity(a, b) -> float:
    """Deterministic normalized cosine. Rejects empty, mismatched, or non-finite input."""
    _validate(a, "query vector")
    _validate(b, "document vector")
    if len(a) != len(b):
        raise SimilarityError(f"dimension mismatch: {len(a)} != {len(b)}")
    import numpy as np
    va, vb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        raise SimilarityError("zero-length vector has no direction")
    score = float(np.dot(va, vb) / (na * nb))
    # clamp tiny floating-point overshoot so the score stays in [-1, 1]
    return max(-1.0, min(1.0, score))


def rank_by_similarity(query_vector, candidates):
    """candidates: iterable of (corpus_item_id, vector). Returns (id, score) sorted by
    score desc then UUID asc — a stable, deterministic order."""
    scored = [
        (str(item_id), cosine_similarity(query_vector, vector))
        for item_id, vector in candidates
    ]
    scored.sort(key=lambda row: (-row[1], row[0]))
    return scored
