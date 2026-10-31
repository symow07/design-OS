# 18 · Round 1 jury

`apps/pipeline/services/rank_round.py (+1)` · chain step: **None**

## What it does today (read from its code)
`rank_round` is ordinal-jury maths: `coarse_cut` (:25), `pair_batches` (:40), `validate_pairs` (:54), `fine_order`
(:74, clean tie resolution); `coarse`, `fine` and `calibration` (:112–:156) are wired to docs/rounds/r1-balm.
`round_jury_completion.complete_batch` (:167) asks again only for missing pairs, at most three rounds per Retry.

## The run ($0)
Twenty ids in batches of nine; the balm round's pair and jury tests run.
Recorded in [runs/18.json](runs/18.json), made by `docs/consolidation/probe.py 18`. What came out:
- `batches`: 22
- `pairs`: 190
- own tests (test_round_balm.py, -k "pair or invalid or rank or jury"): **10 passed, 26 deselected in 0.65s**
- seconds: 1.5; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs: the designer flow has the owner pick, with no jury.
