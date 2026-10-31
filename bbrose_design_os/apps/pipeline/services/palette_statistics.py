"""1g — the guarded rank correlation. The ONLY correlation path.

Owner ruling A1 (M6_DRIVER_COMPLETENESS_PROMPT.md): a Spearman computed
against a zero-variance vector is not 1.0 and not 0.0 — it is
undefined, and a computation that silently returns a plausible value
from a degenerate input is the third instance of its defect class in
this project (after the N=4 census degeneracy and the silent-zero
floor). Third instance gets a structural guard, not a fix: this module
raises, and a source-scan test asserts no other rank-correlation
implementation exists in the services tree.
"""
import numpy as np

#: the registered defect class — alongside DECLARED_BUT_UNREALIZED and
#: BUILDER_CONSTANT in the project's defect taxonomy
DEFECT_CLASS = "DEGENERATE_INPUT_PLAUSIBLE_OUTPUT"

DEFECT_INSTANCES = (
    "N=4 census degeneracy — a tiny attainable rank set read as "
    "precision",
    "silent zero — RAKING_SHADOW_FRACTION floor 0.0 recorded as a "
    "measurement of a subject that could not shadow",
    "constant-vector rank correlation — SHADOW|GRANULARITY 1.0 "
    "committed from a bit-constant vector (superseded in place, "
    "raking_rig/sweep/sweep_result.json)",
)


class DegenerateStatisticError(ValueError):
    """A statistic asked to summarize an input it cannot measure."""


def guarded_spearman(xs, ys):
    """Spearman rank correlation that REFUSES degenerate input.

    Raises DegenerateStatisticError when either vector has zero
    variance or the vectors are shorter than 3 — a rank correlation
    over such input is undefined, and returning any number would be
    the registered defect. Behavior on non-degenerate input is
    identical to the unguarded implementations it replaces.
    """
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if xs.shape != ys.shape or xs.ndim != 1:
        raise DegenerateStatisticError(
            f"rank correlation needs two equal-length vectors, got "
            f"{xs.shape} and {ys.shape}")
    if len(xs) < 3:
        raise DegenerateStatisticError(
            f"rank correlation over {len(xs)} points is not a "
            f"measurement")
    if np.all(xs == xs[0]) or np.all(ys == ys[0]):
        # THE mechanism of the committed artifact: stable-sort ranks
        # turn a bit-constant vector into 0..n-1, which correlates
        # perfectly with any monotone companion. The raw-value check
        # fires before ranking can manufacture an ordering.
        raise DegenerateStatisticError(
            "zero-variance input — a correlation against a constant "
            f"is undefined, not 1.0 and not 0.0 ({DEFECT_CLASS})")
    rx, ry = _average_ranks(xs), _average_ranks(ys)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = float(np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))
    if denom == 0.0:
        raise DegenerateStatisticError(
            "zero-variance rank vector after tie-averaging "
            f"({DEFECT_CLASS})")
    return float((rx * ry).sum() / denom)


def _average_ranks(v):
    """True Spearman ranks: ties share their average rank. The
    argsort(argsort(.)) form the guard replaces assigned ties
    ARBITRARY distinct ranks by stable sort order — mis-ranking every
    tied input, not only constants."""
    order = np.argsort(v, kind="stable")
    ranks = np.empty(len(v), dtype=float)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return ranks
