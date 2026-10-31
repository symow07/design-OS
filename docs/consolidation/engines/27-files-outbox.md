# 27 · Files outbox

`apps/pipeline/services/round_files_flow.py` · chain step: **Make my files (starts and queues the execution half)**

## What it does today (read from its code)
`start` (:112) opens a files build for a picked design (a flat pick refuses in words until the product's flat face
templates exist: `flat_pick` :105), `enqueue` (:135), `run` (:208, one step under the build's lock, then the next),
`recover`, `retry` (:158), `retain_failure`/`fail` (:174–:183, using round_ideas.record_break and
round_master_flow.digest), `progress` (:293), `files_brief` (:32, the brief plus the round's committed Arabic shade
names).

## The run ($0)
Its tests (the files page file) run.
Recorded in [runs/27.json](runs/27.json), made by `docs/consolidation/probe.py 27`. What came out:
- own tests (test_round_files_page.py): **12 passed, 17 warnings in 4.95s**
- seconds: 5.9; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `start`, `enqueue`, `run`, `retry`, `fail`, `files_brief`, `progress`.
