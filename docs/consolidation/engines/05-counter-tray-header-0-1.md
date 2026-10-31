# 5 · counter_tray_header 0.1 (family display, provisional; still the registry's current)

`apps/dielines/geometry/counter_tray_header.py` · chain step: **Die solving (the stand)**

## What it does today (read from its code)
4,241 lines with two solvers under one template id. The family display (Day 12): `solve` (:481) from house values and
products, `_tray`/`_insert`/`_platform` parts, `fold_check` (:2005, ~600 lines of folding, sway, frame and gusset
checks), `scene`/`_sight`/`sightlines` (:2702–:3090, a ray-cast sightline model) and the reference-die measurer
(`measure_reference_die` :3618, `reference_mapping` :3977). The product-grid branch: `solve_product_tray` (:3091),
`_product_row_parts`, `build_product_tray_die`, `product_tray_fold_check`, `product_tray_platform_fronts`,
`product_tray_enclosure_elevations`, `product_tray_raise_rear`, `product_tray_sightlines` (:3187–:3617). Its
`build_die` and `fold_check` hand a 1.0 record on to counter_display (:1279, :2011). The 1.0 solver imports this module
for `solve_product_tray`, `Part`, `Die`, `_rect`, `_seg`, `_r`, `_product_row_parts` and the sheet constants, and the
stand adapter calls its sightlines, platform fronts, enclosure elevations and rear raise.

## The run ($0)
The family display solved from its own defaults, its die built and fold-checked; the product-grid branch solved for
round 3's 4 × 3 grid and fold-checked; this module's test file run (it also holds the stand adapter's tests).
Recorded in [runs/05.json](runs/05.json), made by `docs/consolidation/probe.py 5`. What came out:
- **The probe itself failed:** TypeError: solve_product_tray() missing 2 required keyword-only arguments: 'header_height_mm' and 'front_height_mm'

## Verdict: PARTLY
Good: the product-grid functions above, which 1.0 already depends on. Not needed: the Day 12 family display (solve,
_tray, _insert, sway and frame checks, scene, reference-die mapping); no chain step builds it.

## Parts worth keeping
- `solve_product_tray`, `_product_row_parts`, `Part`, `Die`, `_rect`, `_seg`, `_r` and the sheet constants — what 1.0 is
  built on.
- `product_tray_sightlines`, `_product_plate_hit`, `_product_first_hit` — the seats' sightline check 1.0 reports.
- `product_tray_platform_fronts`, `product_tray_enclosure_elevations`, `product_tray_raise_rear` — the elevations the
  stand adapter and the drawings use.
