# 1 · Dieline engine core

`apps/dielines/geometry/engine.py (+4)` · chain step: **Cartons (anything that folds: the die first)**

## What it does today (read from its code)
`calculate_dieline` (engine.py:437) takes a validated `DielineInputJSON` and dispatches it: the 1.4 trade tuck ends
first (`trade_tuck.is_trade`), then the versioned style table (unpinned: 1.1), then the side-seam, ECMA and opposed-tuck
archetypes; anything else raises `unknown carton style`. It returns a `DielineCoordinates` (panels, fold lines, the
cut, bleed and safe polygons, flaps, slits, a `derived` record). It writes no file. `_calculate_carton` (engine.py:561,
about 590 lines) is the one carton recipe: board-thickness compensation, a slit-web guard (`_apply_slit_web_guard`
:203) and lock notches. The pinned 1.0 wrappers (`calculate_straight_tuck_end` :493 and two more) are kept to
reproduce old jobs.

## The run ($0)
Round 3's bottle (15 × 15 × 100 mm, the brief's sizes) drawn as a carton through `calculate_dieline`, unpinned and at
1.4, for three styles, each validated; the 1.4 straight tuck end written as an SVG; the engine's geometry and trade-tuck
tests run.
Recorded in [runs/01.json](runs/01.json), made by `docs/consolidation/probe.py 1`. What came out:
- `cartons`:
  - straight_tuck_end_carton@unpinned: {"flat_mm": [70.0, 136.81], "panels": 5, "folds": 10, "cut_area_mm2": 7797.7, "validate": null}
  - straight_tuck_end_carton@1.4: {"flat_mm": [71.4, 147.75], "panels": 5, "folds": 12, "cut_area_mm2": 8162.1, "validate": null}
  - reverse_tuck_end_carton@1.4: {"flat_mm": [71.4, 147.75], "panels": 5, "folds": 12, "cut_area_mm2": 8162.1, "validate": null}
  - tuck_top_auto_bottom_carton@unpinned: {"flat_mm": [70.0, 129.655], "panels": 5, "folds": 11, "cut_area_mm2": 7788.9, "validate": null}
- own tests (test_geometry.py, test_trade_tuck.py): **108 passed, 5 warnings in 0.73s**
- seconds: 1.6; files written: 1 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `calculate_dieline` — one entry for every carton, versions pinned or current, never a silent fallback.
- `_calculate_carton` — the thickness-compensated recipe with its guards.
- `primitives.sample_path` / `path_to_svg_d` — real M/L/C/Z paths from the primitives.
- `DielineCoordinates.validate` — bleed ⊃ cut ⊃ safe, polygons valid.
