# 19 · Jury (J1/J2)

`apps/pipeline/services/jury.py` · chain step: **None (the owner is the gate)**

## What it does today (read from its code)
`ask` (:355) makes one Anthropic call per juror and writes an immutable record; `combine` (:459) takes the stricter
score per dimension and unions the hard failures; `judge` (:518) runs J1 and J2 and writes verdict.json;
`rank_sketches`/`_v2` and `idea_check`/`_v2` rank and check Day 8–9 sketches. Its rubric is a 190 × 120 mm palette lid's
(`LID_WHAT` :288).

## The run ($0)
Its rubric read; its Day 8 tests run.
Recorded in [runs/19.json](runs/19.json), made by `docs/consolidation/probe.py 19`. What came out:
- `lid_what`: flat print artwork of the closed lid of an eyeshadow palette, 190 × 120 mm, front-on, edge to edge
- own tests (test_day8_jury.py): **28 passed in 0.18s**
- seconds: 1.0; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs (the owner's Accept/Redraw replaced juries).
