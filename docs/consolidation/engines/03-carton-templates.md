# 3 · Carton templates: straight / reverse tuck end 1.0–1.4, tuck-top auto-bottom 1.0–1.1, ECMA STE 0.1, opposed tuck 0.1, Skynte side-seam 1.0

`apps/dielines/geometry/trade_tuck.py (+3)` · chain step: **Cartons**

## What it does today (read from its code)
Four archetype modules, each reached only through `calculate_dieline`, each returning `DielineCoordinates`:
`calculate_trade_tuck` (trade_tuck.py:89, straight and reverse tuck end 1.4: inside sizes W+t, D+t, H+t, clamped tongue,
shoulder, dust flap and glue flap, panel order glue, back, side, front, side); `calculate_ecma_ste` (ecma_ste.py:175,
ECMA A20.20.01.01, 0.1, with `collision_report` :491); `calculate_opposed_tuck` (opposed_tuck.py:201, a reference
reconstruction, 0.1, checked against its attachment map :169); `calculate_side_seam_tuck` (side_seam.py:173, Skynte 1.0).

## The run ($0)
Round 3's bottle drawn on every archetype, each folded by `fold_check.check`; then the other products of the goal (a
lipstick carton 25 × 25 × 85, a lip balm carton 22 × 22 × 78, the palette box 195 × 125 × 22 mm) on the three
non-trade archetypes and on reverse tuck 1.4; the archetypes' own tests run.
Recorded in [runs/03.json](runs/03.json), made by `docs/consolidation/probe.py 3`. What came out:
- `cartons`:
  - straight_tuck_end_carton@1.4: {"flat_mm": [71.4, 147.75], "panels": 5, "folds": 12, "cut_area_mm2": 8162.1, "fold_passed": true, "fold_failed": []}
  - reverse_tuck_end_carton@1.4: {"flat_mm": [71.4, 147.75], "panels": 5, "folds": 12, "cut_area_mm2": 8162.1, "fold_passed": true, "fold_failed": []}
  - ecma_a20_20_01_01_ste_carton@current: {"error": "EcmaSteGeometryError: back panel too narrow for the entry slits and lock ears"}
  - reference_opposed_tuck_carton@current: {"error": "OpposedTuckGeometryError: DIMENSION_COMBINATION_UNSUPPORTED: FOLD_HINGE_MIN: remaining fold span = 1.35 mm is below 10 mm | TUCK_TIP_MIN: tuck tip span = -0.05 mm is below 4 mm | DUST_PAIR…
  - skynte_foundation_tuck_carton@current: {"error": "GeometryError: entry slits (5.00 mm) plus lock notches consume more than 60% of the tuck base — the hinge would tear on first fold"}
- `goal_products`:
  - lipstick carton / ecma_a20_20_01_01_ste_carton: {"flat_mm": [112.1, 171.7], "panels": 5, "folds": 12, "cut_area_mm2": 12635.2, "fold_passed": false}
  - lipstick carton / reference_opposed_tuck_carton: {"error": "OpposedTuckGeometryError: DIMENSION_COMBINATION_UNSUPPORTED: DUST_PAIR_CLEARANCE: folded dust clearance = -18.35 mm is below 2 mm (needs W >= D + t + 20)"}
  - lipstick carton / skynte_foundation_tuck_carton: {"flat_mm": [110.0, 167.0], "panels": 5, "folds": 10, "cut_area_mm2": 12401.4, "fold_passed": false}
  - lipstick carton / reverse_tuck_end_carton: {"flat_mm": [111.4, 152.75], "panels": 5, "folds": 12, "cut_area_mm2": 12143.9, "fold_passed": true}
  - lip balm carton / ecma_a20_20_01_01_ste_carton: {"flat_mm": [100.1, 158.7], "panels": 5, "folds": 12, "cut_area_mm2": 10271.9, "fold_passed": false}
  - lip balm carton / reference_opposed_tuck_carton: {"error": "OpposedTuckGeometryError: DIMENSION_COMBINATION_UNSUPPORTED: FOLD_HINGE_MIN: remaining fold span = 8.35 mm is below 10 mm | DUST_PAIR_CLEARANCE: folded dust clearance = -18.35 mm is belo"}
  - lip balm carton / skynte_foundation_tuck_carton: {"flat_mm": [98.0, 154.0], "panels": 5, "folds": 10, "cut_area_mm2": 10038.7, "fold_passed": false}
  - lip balm carton / reverse_tuck_end_carton: {"flat_mm": [99.4, 139.75], "panels": 5, "folds": 12, "cut_area_mm2": 9853.2, "fold_passed": true}
  - palette box / ecma_a20_20_01_01_ste_carton: {"error": "ValidationError: 1 validation error for DielineInputJSON\ndimensions.height_mm\n Input should be greater than or equal to 60 [type=greater_than_equal, input_value=22.0, input_typ"}
  - palette box / reference_opposed_tuck_carton: {"error": "ValidationError: 1 validation error for DielineInputJSON\ndimensions.height_mm\n Input should be greater than or equal to 60 [type=greater_than_equal, input_value=22.0, input_typ"}
  - palette box / skynte_foundation_tuck_carton: {"error": "ValidationError: 1 validation error for DielineInputJSON\ndimensions.height_mm\n Input should be greater than or equal to 60 [type=greater_than_equal, input_value=22.0, input_typ"}
  - palette box / reverse_tuck_end_carton: {"error": "ValidationError: 1 validation error for DielineInputJSON\ndimensions.height_mm\n Input should be greater than or equal to 60 [type=greater_than_equal, input_value=22.0, input_typ"}
- own tests (test_opposed_tuck_archetype.py, test_ecma_ste_archetype.py, test_side_seam.py): **51 passed, 5 warnings in 4.22s**
- seconds: 5.2; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the trade tuck ends (1.4). The ECMA STE 0.1, opposed tuck 0.1 and Skynte side-seam 1.0 archetypes refuse the
goal's products (see the run); they serve no product the chain makes.

## Parts worth keeping
- `calculate_trade_tuck` — the qualified 1.4 trade tuck ends: they draw every product of the goal and fold clean.
