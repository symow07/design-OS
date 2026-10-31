# 6 · counter_tray_header 1.0 (single product, production, pinned)

`apps/dielines/geometry/counter_display.py` · chain step: **Die solving (the stand), the die first**

## What it does today (read from its code)
`solve(product=, board=, product_grid=)` (counter_display.py:68) takes the brief's grid, starts from 0.1's
`solve_product_tray`, compensates for the board (`BOARDS`), locks the header from the back panel, sizes the holder,
insert tabs and retention tongues (`_tongues` :145) and returns the 1.0 record. `build_die` (:197) draws the tray,
holder rows and seats as parts with faces, creases, glue zones and slots and lays them on a sheet. `trade_rules`,
`fold_check`, `strength_check`, `sightline_check` (0.1's code) and `compare` (against the house's measured display
dies) are run together by `qualify` (:553).

## The run ($0)
Round 3's stand solved again exactly as the files build solves it (the brief plus the picked picture's saved reading)
and compared leaf by leaf with the committed record; solved from the brief alone; qualified; its tests run.
Recorded in [runs/06.json](runs/06.json), made by `docs/consolidation/probe.py 6`. What came out:
- `committed_vs_again`: {"differing_leaves": 0, "first": []}
- `with_reading`: {"height_mm": 225.02474195235837, "header_mm": [107.0, 78.2491], "holes": 12, "sheet_mm": [445, 901], "parts": ["tray", "seat row 1", "holder row 1", "seat row 2", "holder row 2", "seat row 3", "holder row 3"]}
- `brief_alone`: {"height_mm": 160.0, "header_mm": [107.0, 58.5]}
- `qualification`: {"passed": false, "reports": {"fold": true, "strength": true, "sightline": false, "trade_rules": true, "comparison": true}}
- own tests (test_counter_display.py): **14 passed, 5 warnings in 0.78s**
- seconds: 1.7; files written: 2 (kept in the run folder, not committed)

## Verdict: GOOD
Round 3's own die fails its sightline check (0.1's `product_tray_sightlines`), while fold, strength, trade rules and
the comparison pass. Recorded as found; the stand-die merge keeps the same result and does not change it.

## Parts worth keeping
- `solve` / `build_die` — the production die the flow uses.
- `trade_rules`, `fold_check`, `strength_check`, `compare`, `qualify` — every check in one call.
- `cut_polygons`, `bleed_area`, `layer_geometry` — the die's layers for the writer.
