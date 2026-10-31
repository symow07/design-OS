# 43 · Ẓilāl object, sticker, box, cartons

`apps/pipeline/services/zilal_object.py (+3)` · chain step: **None**

## What it does today (read from its code)
Day 11–12 surfaces composed from the lid's assets: the lid's sides, inside and tray (`sides_build` :314,
`inside_master` :711, `tray_master` :1043 — crop 3 mm, upscale 2×, mirror the bleed), the base sticker
(`zilal_sticker.build` :773 with `fit`, `widowless`, `glue_ci`), the outer box (`zilal_box.build` :174) and the stick
cartons (`zilal_cartons.build` :1141 through stick_carton), each reading Day 11/12 records.

## The run ($0)
Their tests (the Ẓilāl pack and the Day 13 lipstick carton files) run.
Recorded in [runs/43.json](runs/43.json), made by `docs/consolidation/probe.py 43`. What came out:
- own tests (test_day11_zilal_pack.py, test_day13_lipstick_carton.py): **18 passed, 5 warnings in 6.95s**
- seconds: 8.2; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs.
