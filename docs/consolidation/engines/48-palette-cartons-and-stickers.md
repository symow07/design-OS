# 48 · Palette cartons and stickers

`apps/pipeline/services/palette_box.py (+4)` · chain step: **Cartons (Day 10–13 cartons; none in the chain yet)**

## What it does today (read from its code)
`palette_box.build` (:199) the palette's outer box on reverse tuck 1.4 from Day 10's lid and sticker (`die` :45 reads a
saved spec), `fold_check_record` (:435), `clean_parts` (:508); `palette_sticker.build` (:605, EN/ES/AR back sticker,
`wrap`, `fit`, `document`); `stick_carton.build` (:1649, the lipstick and lip balm cartons on straight tuck 1.4 through
`registry.print_ready_version`, `die` :224, `lay` :601, `bands_for` :714, refusing without translations);
`palette_board.build` and `collection_board.build` (boards of pictures). Every default path is a Day 10–13 folder.

## The run ($0)
The lipstick carton's die and the palette box's die drawn by their own `die`; the Day 11 carton tests run.
Recorded in [runs/48.json](runs/48.json), made by `docs/consolidation/probe.py 48`. What came out:
- `stick_die`: {"flat_mm": [101.8, 145.25], "panels": 5, "folds": 12, "cut_area_mm2": 10555.0}
- `palette_box_die`: {"flat_mm": [285.25, 238.25], "panels": 5, "folds": 12, "cut_area_mm2": 60963.9}
- `products`: ["lip_balm", "lipstick"]
- own tests (test_day11_carton.py): **38 passed, 5 warnings in 7.19s**
- seconds: 8.4; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the dies and the fold record. Day-bound: every build reads a dated folder; the chain makes no carton yet.

## Parts worth keeping
- `stick_carton.die`, `palette_box.die` — the goal's cartons on the qualified 1.4 trade tuck.
- `palette_box.fold_check_record`, `clean_parts`, `stick_carton.lay` — ink against creases, copy laid in a panel.
