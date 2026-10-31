"""3e/A192 — a floor is a bound, and a bound may only tighten.

THE COMBINING RULE, executable rather than described:

    WORST_OBSERVED_EXCURSION_ACROSS_ENSEMBLES

A threshold derived from repeated measurement declares its KIND, and
the kind fixes the legal direction of movement as ensembles
accumulate:

  BOUND    combined by the worst observed value; may move only in the
           conservative direction. A floor answers "how large could
           this excursion be", so a kinder ensemble does not lower it.
  ESTIMATE combined by a rule declared BEFORE the second ensemble is
           run; may move in either direction.

A quantity with no declared kind may not be used in a gate — the same
shape as 2w: a threshold without a declared kind is not a threshold.

The dispersion-of-dispersion candidate is refused by construction and
not merely unused: under it a third ensemble that agreed closely would
SHRINK the dispersion and LOOSEN the floor, so accumulating evidence
would make the bar easier to clear. That is the forbidden direction
(A176's mirror), and a floor that moves beneath established verdicts
is not a floor.

RECIPE, co-located (2w): the combining rule's identity is
sha256(json.dumps(RULE, sort_keys=True)).hexdigest()[:16] over the
RULE dict below, which names the rule, the executable combiner's
source expression, and the legal movement directions.
"""
import hashlib
import json

BOUND = "BOUND"
ESTIMATE = "ESTIMATE"

RULE = {
    "name": "WORST_OBSERVED_EXCURSION_ACROSS_ENSEMBLES",
    "applies_to_kind": BOUND,
    "combiner_source": "max(abs(float(v)) for v in values)",
    "legal_movement": {
        BOUND: "conservative direction only (may tighten, never loosen)",
        ESTIMATE: "either direction, under a rule declared before the "
                  "second ensemble runs",
    },
    "refused_candidate": {
        "name": "dispersion_of_dispersion",
        "why": "accumulating agreement would loosen the floor — the "
               "forbidden direction",
    },
    "law": "3e",
}


class ThresholdKindError(RuntimeError):
    """A threshold used in a gate without a declared kind, or combined
    against its kind. Raised, never warned."""


def combining_rule_identity():
    """RECIPE: sha256(json.dumps(RULE, sort_keys=True))[:16]."""
    return hashlib.sha256(
        json.dumps(RULE, sort_keys=True).encode()).hexdigest()[:16]


def combine(values, kind):
    """Combine ensemble measurements of one threshold.

    A BOUND takes the worst observed excursion. An ESTIMATE is refused
    here on purpose: its combining rule must be declared before its
    second ensemble runs, so there is no default to fall back on.
    """
    vals = [abs(float(v)) for v in values]
    if not vals:
        raise ThresholdKindError(
            "no measurements to combine — a threshold cannot be "
            "derived from an empty ensemble set")
    if kind == BOUND:
        return max(vals)
    if kind == ESTIMATE:
        raise ThresholdKindError(
            "an ESTIMATE has no default combiner: its rule is declared "
            "before its second ensemble runs (3e); supply the declared "
            "rule rather than combining here")
    raise ThresholdKindError(
        f"threshold kind {kind!r} is not declared — a quantity with no "
        "declared kind may not be used in a gate (3e)")


def assert_gate_usable(declaration):
    """A quantity entering a gate states its kind, or it is refused."""
    if "kind" not in declaration:
        raise ThresholdKindError(
            "declaration carries no 'kind' — BOUND or ESTIMATE must be "
            "stated at declaration; a threshold without a declared "
            "kind is not a threshold (3e)")
    if declaration["kind"] not in (BOUND, ESTIMATE):
        raise ThresholdKindError(
            f"unknown kind {declaration['kind']!r}")
    return declaration["kind"]
