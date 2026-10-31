"""A222 — 1k's NAMED quantity, executable.

1k (723acb4, 2026-08-08) says of a cross-family clearing:

    "the named quantity is the clearing itself recomputed at each seed
    of the declared ensemble, and its dispersion; max_seed_only_effect
    is the same functional at the null point — a legitimate
    conservative proxy, not the test."

Every 1i adequacy result in this programme has been evaluated against
that proxy. This module implements the test.

THE DISPERSION MEASURE IS DECLARED HERE, BEFORE ANY CLEARING IS
COMPUTED, and it is the MAXIMUM PAIRWISE RELATIVE EFFECT across the
per-seed clearings — chosen for one reason, which is 1k's own
sentence: max_seed_only_effect is "the same functional at the null
point". The proxy is that functional evaluated where the two families
coincide; the named test is therefore that same functional evaluated
where they do not. Holding the functional fixed and moving only the
point is what makes the two comparable, and it is the only choice that
does not introduce a second change alongside the one under test.

DIRECTION, STATED BEFORE THE NUMBERS: a maximum over a set is not
below a dispersion measure over that set, so the proxy sits at or
above the test. An UNMET under the proxy therefore establishes
UNMET-or-possibly-MET, never UNMET. This computation can only move
adequacy verdicts toward MET, which is the direction that favours the
executor, which is why the recipe is committed before it runs.

    ^^^ BOTH PARAGRAPHS ABOVE ARE SUPERSEDED IN PLACE (2u/2k, A291),
    retained as the claims under which recipe 6d6e4ab90686503f
    computed, and REFUTED:

    (1) the measure was MAX PAIRWISE RELATIVE EFFECT applied to
        quantities that are themselves relative effects — the
        functional applied a second time to its own output, giving a
        FRACTION_OF_A_RELATIVE_EFFECT, which is NOT commensurable
        with margin (relative-effect units) or with
        max_seed_only_effect (relative-effect units). Established
        from the code at A284. "Holding the functional fixed" does
        not hold the UNITS fixed when the input type changes from raw
        values to effects.

    (2) the direction claim was false in its premise: a maximum over
        a set is not below a dispersion over THE SAME set under THE
        SAME functional, and proxy and test are neither. Refuted at
        A232 before any number, and the recomputation under matched
        units gives ratios 0.96 / 1.02 / 1.08 / 1.26 — the premise
        PROXY_BOUNDS_TEST is UNRESOLVED_AT_PARITY, not refuted by
        large factors and not established either (3f).

    (3) "its dispersion" was underdetermined by 1k's text and was
        pinned here by analogy rather than escalated — the 3i breach.
        The measure is now set by RULING (A289) and is stated in
        RECIPE above.

RECIPE, co-located (2w): the identity is
sha256(json.dumps(RECIPE, sort_keys=True)).hexdigest()[:16] over the
RECIPE dict below.
"""
import hashlib
import itertools
import json

RECIPE = {
    "name": "CLEARING_DISPERSION_1k_NAMED_QUANTITY",
    "per_seed_quantity": ("the clearing between the two families' axis "
                          "values at one seed, as the relative effect "
                          "abs(a-b)/mean(abs(a),abs(b))"),
    "dispersion_measure": "MAX_PAIRWISE_ABSOLUTE_DIFFERENCE",
    "dispersion_source": ("A289 ruling under 3i: '\u2018its dispersion\u2019 "
                          "is underdetermined by 1k's text, so the choice "
                          "among dimensionally sound candidates is a "
                          "ruling. Grounds, in order: (1) DIMENSIONAL \u2014 "
                          "a difference between two relative effects is "
                          "in relative-effect units, commensurable with "
                          "margin, which excludes every relative form; "
                          "(2) 3e \u2014 the comparator is a BOUND, not an "
                          "estimate, and a bound takes the worst "
                          "observed excursion, which excludes stdev, MAD "
                          "and IQR; (3) consistency \u2014 worst observed "
                          "excursion is the arc's standing discipline "
                          "and it makes the band calibration and the "
                          "comparator one quantity"),
    "supersedes": ("recipe 6d6e4ab90686503f, which applied the effect "
                   "functional a SECOND time to its own output and was "
                   "therefore UNITS_INCOMMENSURABLE_WITH_MARGIN"),
    "ensemble": "the declared seed ensemble, all seeds, no subsetting",
    "degenerate_policy": "raise; never substitute a plausible zero",
    "law": "1k @ 723acb4 (2026-08-08), under 1i @ 8f6cb81",
}


class ClearingDispersionError(RuntimeError):
    """Refuses rather than returning a plausible number."""


def recipe_identity():
    """RECIPE: sha256(json.dumps(RECIPE, sort_keys=True))[:16]."""
    return hashlib.sha256(
        json.dumps(RECIPE, sort_keys=True).encode()).hexdigest()[:16]


def relative_effect(a, b):
    """The programme's unchanged effect functional."""
    mean = (abs(float(a)) + abs(float(b))) / 2.0
    if mean <= 1e-9:
        raise ClearingDispersionError(
            "degenerate pair: both values ~zero — refusing to return a "
            "plausible effect")
    return abs(float(a) - float(b)) / mean


def clearings_per_seed(family_a_by_seed, family_b_by_seed):
    """The clearing recomputed at each seed of the declared ensemble."""
    seeds_a = set(family_a_by_seed)
    seeds_b = set(family_b_by_seed)
    if seeds_a != seeds_b:
        raise ClearingDispersionError(
            f"the two families are not measured on the same declared "
            f"ensemble: {sorted(seeds_a ^ seeds_b)} unmatched — the "
            "named quantity is undefined without a common seed set")
    if len(seeds_a) < 2:
        raise ClearingDispersionError(
            "fewer than two seeds — a dispersion is not defined")
    return {s: relative_effect(family_a_by_seed[s], family_b_by_seed[s])
            for s in sorted(seeds_a)}


def clearing_dispersion(family_a_by_seed, family_b_by_seed):
    """1k's named quantity: the per-seed clearings and their
    dispersion, under the measure declared in RECIPE."""
    per_seed = clearings_per_seed(family_a_by_seed, family_b_by_seed)
    # A289: the maximum pairwise ABSOLUTE difference — a difference of
    # relative effects, hence in relative-effect units and commensurable
    # with margin. Over a set this is its range; the implementation is
    # shorter than the one it replaces.
    pairs = {f"{a}|{b}": abs(per_seed[a] - per_seed[b])
             for a, b in itertools.combinations(sorted(per_seed), 2)}
    return {
        "per_seed_clearings": per_seed,
        "pairwise": pairs,
        "dispersion": max(pairs.values()),
        "dispersion_measure": RECIPE["dispersion_measure"],
        "recipe_identity": recipe_identity(),
    }
