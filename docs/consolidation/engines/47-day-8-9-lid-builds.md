# 47 · Day 8/9 lid builds

`apps/pipeline/services/truthful_concept.py (+6)` · chain step: **None**

## What it does today (read from its code)
The Day 8–9 rebuilds of a lid from a sketch's spec: `truthful_concept.layout`/`document`/`render`/`paint_plate` (paid)/
`prove_plate` (tesseract), `rich_concept.layout`/`make_plate`/`checks`, `rich_plate.prove_rich_plate` and
`clean_small`, `lid_devices.gravure`/`interference`/`astrolabe` (pure ornament geometry), `day9_recipes.recipe` and the
paid `day9_sketches.make`/`concept_sketches.make`. Their constants point at Day 8 and Day 9 folders.

## The run ($0)
The gravure and astrolabe devices drawn; the Day 8 concept and Day 9 ornament tests run.
Recorded in [runs/47.json](runs/47.json), made by `docs/consolidation/probe.py 47`. What came out:
- `gravure`: {"kind": 7, "marks": 148, "lines": 130, "hero_index": 66, "hero_width_mm": 2, "params": 10}
- `astrolabe`: {"kind": 9, "marks": 329, "params": 2, "centre_mm": 2, "radius_mm": 62.0}
- own tests (test_day8_concepts.py, test_day9_orn_b1.py): **61 passed, 7 warnings in 161.26s (0:02:41)**
- seconds: 162.4; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs (rebuilding a design from its spec is the redrawing the owner ruled out).
