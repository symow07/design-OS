# 51 · Tracers

`apps/pipeline/services/line_art.py (+2)` · chain step: **None (the die-first method paints; nothing is traced)**

## What it does today (read from its code)
`line_art.trace_lines`/`trace_frame`/`trace_window` (:276–:577) skeletonise line art into strokes;
`flat_motif.read_flat` (:236, the ink, ground and stroke of a flat picture), `trace_flat` (:296, potrace outlines),
`colour_art`, the paid `redraw_flat`, `colour_check`, `shape_whole`; `traced_text.inspect_bundle` (:157) checks a
bundle's live text and OCRs its raster layers. Imported by the old agent pipeline's targets.

## The run ($0)
`read_flat` on round 3's drawn header face; the traced-text test run.
Recorded in [runs/51.json](runs/51.json), made by `docs/consolidation/probe.py 51`. What came out:
- `read_flat`: {"img": "ndarray", "de": "ndarray", "mask": "ndarray", "ground": "#192A44", "ink": "#E0B56C", "stroke_px": 407.221, "crop": "list", "size": "list"}
- own tests (test_rescue_day5.py, -k "traced"): **1 passed, 26 deselected, 5 warnings in 0.20s**
- seconds: 1.1; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs.
