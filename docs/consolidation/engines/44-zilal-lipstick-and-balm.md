# 44 · Ẓilāl lipstick and balm

`apps/pipeline/services/zilal_lipstick.py (+3)` · chain step: **None**

## What it does today (read from its code)
Paid sketch rounds for the lipstick and the balm (`sketch`, `rank`, `crop_wraps`, reading Day 9's direction B-1) and
their masters: `zilal_lipstick_master.build`/`build_closed` (:1308, :1376: body, cap, label, A4 page, a product drawing)
and `zilal_balm_master.build` (:1666: the sketch's dashed guides cleaned by `find_dashes`/`clean_dashes`, ghost edges
rebuilt by `harmonic_fill`/`repair_ghost`).

## The run ($0)
The balm's trim rows on an empty wrap; their tests run.
Recorded in [runs/44.json](runs/44.json), made by `docs/consolidation/probe.py 44`. What came out:
- `trim_rows`: (array([[[0, 0, 0], [0, 0, 0], [0, 0, 0], ..., [0, 0, 0], [0, 0, 0], [0, 0, 0]], [[0, 0, 0], [0, 0, 0], [0, 0, 0], ...,
- own tests (test_day12_balm.py, test_day11_lipstick.py, test_day12_lipstick.py): **43 passed, 5 warnings in 37.27s**
- seconds: 38.2; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs.
