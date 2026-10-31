# 15 · Ideas image calls

`apps/pipeline/services/round_ideas_calls.py` · chain step: **Boards and designs (their paid image calls)**

## What it does today (read from its code)
`IdeasContext(RoundContext)` (:52) is the paid context the boards and designs are bought through: `design_image_call`
(:68) generates, or edits with references or a flat template, saves the raw bytes, request, response and billing,
returns the saved record on replay and refuses changed bytes; `image_attempt_cap` 40. `design_image_estimate` (:21)
and `reference_image_estimate` (:44) are the reservations.

## The run ($0)
The reservation one design picture holds, the attempt cap; the ideas and flat tests of the paid-boundary file run.
Recorded in [runs/15.json](runs/15.json), made by `docs/consolidation/probe.py 15`. What came out:
- `design_image_usd`: 0.3386
- `reference_image_usd`: null
- `image_attempt_cap`: 40
- own tests (test_round_calls.py, -k "ideas or flat or design"): **35 passed, 98 deselected in 0.73s**
- seconds: 1.6; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `IdeasContext.design_image_call` — the flat-template edit and the boards' generate, saved, never bought twice.
- `design_image_estimate`, `reference_image_estimate`.
