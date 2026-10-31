# 57 · Palette engine (M-series)

`apps/pipeline/services/palette_*.py (+92)` · chain step: **None (palettes are in the goal; this engine is not on its path)**

## What it does today (read from its code)
Eighty-four palette_* modules (about 30,000 lines): the PALT-M2 layout kernel (`palette_layout_kernel.resolve_layout`),
mechanism and tray geometry, moulded and recessed pans, the ES3083 design intent and owner confirmation, the M5
material characterisation, the M6 powder and flake rigs and gates, governance and statistics guards, an M7 .ai emitter,
and Day 10's palette products. The dashboard's ES3083 confirmation view, the old palette target, the container
silhouettes and two evidence modules import parts of it.

## The run ($0)
Its file and line count; the layout kernel's tests run.
Recorded in [runs/57.json](runs/57.json), made by `docs/consolidation/probe.py 57`. What came out:
- `files`: 84
- `lines`: 30126
- own tests (test_palette_layout_kernel.py): **28 passed in 0.09s**
- seconds: 0.9; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain calls (a palette in New design is a lid face and its carton, drawn by the face method).
