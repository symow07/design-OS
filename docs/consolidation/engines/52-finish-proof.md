# 52 · Finish proof

`apps/pipeline/services/finish_proof.py` · chain step: **None**

## What it does today (read from its code)
`prove_build` (:1184) shades a flat under a softbox with the engine .ai's foil and emboss plates (`render_proof` :1087)
and measures them (`coverage` :553, `foil_limits` :767, `line_density` :878); it reads only plates written by
`pdf_ai._draw_finish_plates`.

## The run ($0)
Its foil and relief tests run.
Recorded in [runs/52.json](runs/52.json), made by `docs/consolidation/probe.py 52`. What came out:
- own tests (test_day9_orn_b2.py, test_day11_golden_hour.py, -k "foil or relief"): **7 passed, 45 deselected, 5 warnings in 5.12s**
- seconds: 6.0; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs (the round's .ai carries no finish plates).
