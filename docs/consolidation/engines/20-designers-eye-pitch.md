# 20 · Designer's eye (pitch)

`apps/pipeline/services/designers_eye.py` · chain step: **None (the files eye is round_files_faces.advice_prompt)**

## What it does today (read from its code)
`render` (:149) rasterises an .ai page; `look` (:194) asks a vision model to list differences between a concept and a
drawing; `agreed` (:290) keeps what two looks name; `check` (:537) runs up to three rounds, recolouring the document
(`recolour` :377) between them. Imported by the old agent pipeline (aria, targets.container, pipeline.views).

## The run ($0)
Round 3's 1.0 die PDF (row 8's file) rendered; two hand-made looks given to `agreed` (it needs a look's full record —
check, part and shape — and refused the short one, as the run shows); its test in the targets file run.
Recorded in [runs/20.json](runs/20.json), made by `docs/consolidation/probe.py 20`. What came out:
- `render`: 3019
- `agreed`: {"error": "KeyError: 'shape'"}
- own tests (test_targets.py, -k "designers_eye"): **1 passed, 98 deselected in 3.31s**
- seconds: 4.2; files written: 0 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- `agreed` — two looks reduced to what both name (an idea the files eye does not need: it looks once).
