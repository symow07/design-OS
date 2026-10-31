# 46 · Product drawing

`apps/pipeline/services/product_drawing.py` · chain step: **The pick's folded and loaded drawings; the built drawing**

## What it does today (read from its code)
`draw` (:162) lays a closed product's front view and three-quarter view side by side from its flat wraps, labelled
"drawing, not a render" (`view` :54, `square_view` :101, `outline` :153, `band_texture` :44) and `write_record` (:217)
records the inputs by hash. The face builder's `drawing` and `folded_drawing` and the designer's `flat_drawings` draw
through it. It takes `REPO` and `rel` from lid_master.

## The run ($0)
Round 3's stand folded and loaded, drawn from a $0 stand-in painting by the designer's own `flat_drawings`; the drawing
tests of the face file run.
Recorded in [runs/46.json](runs/46.json), made by `docs/consolidation/probe.py 46`. What came out:
- `folded`: {"size_px": [1954, 1433], "mode": "RGB", "bytes": 645286, "sha256": "ee43cfbdfaa87c0e"}
- `loaded`: {"size_px": [2234, 2703], "mode": "RGB", "bytes": 450038, "sha256": "8580d51bf4966e0b"}
- own tests (test_round_files_faces.py, -k "drawing or folded or loaded"): **3 passed, 18 deselected, 6 warnings in 9.30s**
- seconds: 11.2; files written: 25 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `draw`, `view`, `square_view`, `outline`, `band_texture`, `write_record`.
