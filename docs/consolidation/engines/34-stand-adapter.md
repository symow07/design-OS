# 34 · Stand adapter

`apps/pipeline/services/round_files_stand.py` · chain step: **Die solving (the stand from the brief and the picture's reading)**

## What it does today (read from its code)
`solve_stand` (:130) turns the brief (and, if any, the picked picture's reading) into 1.0's product grid: the opening
with clearance, three-board webs, a provisional width/depth/height grown to fit, the header and front heights from the
reading's panel ratios (`_panel_ratio` :56), seats raised to the pictured rows (`observed_row_placement` :73); it then
calls counter_display.solve and 0.1's build_die, fold_check, sightlines, platform fronts and (optionally) the enclosure
elevations and rear raise, and writes the round's stand.json (`build_stand` :265).

## The run ($0)
Round 3's stand solved (row 6's run); the adapter's tests in the 0.1 file and the face file run.
Recorded in [runs/34.json](runs/34.json), made by `docs/consolidation/probe.py 34`. What came out:
- own tests (test_counter_tray_header.py, test_round_files_faces.py, -k "round_files_stand or stand_is_built"): **9 failed, 6 passed, 86 deselected, 5 warnings in 1.14s**
  - failed: `test_round_files_stand_adapter_uses_vision_count_and_engine_surfaces`
  - failed: `test_round_files_stand_grows_provisional_brief_for_fourteen_observed_bottles`
  - failed: `test_round_files_stand_measures_row_rises_front_clearance_and_header_gap[80]`
  - failed: `test_round_files_stand_measures_row_rises_front_clearance_and_header_gap[100]`
  - failed: `test_round_files_stand_measures_row_rises_front_clearance_and_header_gap[120]`
  - failed: `test_round_files_stand_enclosure_preserves_observed_cap_band_at_actual_scale[3]`
  - failed: `test_round_files_stand_enclosure_preserves_observed_cap_band_at_actual_scale[7]`
  - failed: `test_round_files_stand_opt_in_raises_real_rear_supports_until_top_band_passes[3]`
  - failed: `test_round_files_stand_opt_in_raises_real_rear_supports_until_top_band_passes[7]`
- seconds: 2.0; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the translation from brief to grid. Failing: nine of its tests in test_counter_tray_header.py (they expect the
older vision-count behaviour; the brief's grid now wins, 2026-10-28). It still calls 0.1's module for six functions.

## Parts worth keeping
- `solve_stand`, `stand_layout`, `observed_row_placement`, `build_stand` — the brief to the 1.0 grid.
