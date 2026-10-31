# 33 · Ornament lettering

`apps/pipeline/services/round_files_ornament.py` · chain step: **Live type along a band**

## What it does today (read from its code)
`layout_runs` (:66) sets COPY as live words along an ornament zone's path, in visual order, each word turned to the path
(Arabic right to left); `zone_mask` (:35), `zone_record` (:44), `ornament_copy` (:27).

## The run ($0)
Its tests (live words on an arc, read back) run.
Recorded in [runs/33.json](runs/33.json), made by `docs/consolidation/probe.py 33`. What came out:
- own tests (test_round_files_faces.py, test_round_files_export.py, -k "ornament or lettering or arc"): **1 passed, 1 skipped, 89 deselected, 5 warnings in 0.38s**
- seconds: 1.2; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `layout_runs`, `zone_record`.
