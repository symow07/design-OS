# 30 · Face builder (+ the files eye)

`apps/pipeline/services/round_files_faces.py` · chain step: **Painting on the die; the stand's faces; type placement; the drawings**

## What it does today (read from its code)
Per face: `face_geometry` (:71), `template` (:203) and `prompt` (:276) for a product face's edit; the flat half —
`flat_setup` (:358), `flat_prompt` (:377), `paint_flat` (:499), `settle_flat` (:434: the die applied again, the proof,
the 1:1 PDF read back, ΔE00 across every fold by `seam_colour`), `painted_face` (:516), `flat_face` (:534),
`repaint_face` (:554); type: `marks` (:97, the header's from round_files_dial, the front strip's centred), `upright_marks`;
the composer `compose_stand` (:660, one raster on the die); `face_spec`, `product_spec`, `specs`, `face_views`;
`drawing` (:792) and `folded_drawing` (:851) through product_drawing; the eye's `advice_prompt` (:927). It takes
`face_mm_size`, `turn`, `upright_polygon` and `K` from zilal_tray, `glyph_metrics` from round_balm_master, and
`srgb_to_lab`/`delta_e00` from lid_master.

## The run ($0)
Round 3 at $0: a stand-in painting (the real two were lost to the network) settled on the die, every stand face cut
from it, and the stand composed on the die with its live type and logo; the face file's tests run.
Recorded in [runs/30.json](runs/30.json), made by `docs/consolidation/probe.py 30`. What came out:
- `proof_outside`: {"pixels": 1285946, "differing_from_template": 0, "zero_offset": true}
- `continuity`: {'schema': 'flat_fold_continuity/1', 'metric': 'CIEDE2000 (lid_master.delta_e00), 3 × 3 px means 1 mm either side', 'seams': [{'seam': 'back panel | header back', 'kind': 'same board, no fold', 'samples': 106, 'delta_e00_mean': 3…
- `faces_cut`: {"header": [266, 198], "header_back": [266, 202], "front": [266, 57], "side": [207, 352], "left": [207, 352], "back": [266, 352]}
- `compose_stand`: {"artwork_rasters": 1, "type_runs": 5, "logos": 1, "placements": ["tray / back panel", "tray / front panel", "tray / header back", "tray / header front", "tray / left side", "tray / right side"]}
- own tests (test_round_files_faces.py): **21 passed, 11 warnings in 38.18s**
- seconds: 40.2; files written: 24 (kept in the run folder, not committed)

## Verdict: GOOD
The stand-in paints each face its own colour on purpose, so the colour across the folds it reports (ΔE00 up to about
39) measures the stand-in, not a design. The composed stand is one raster with 5 live type runs and 1 logo.

## Parts worth keeping
- `flat_setup`, `paint_flat`, `settle_flat`, `painted_face`, `flat_face`, `repaint_face` — the die-first painting.
- `marks`, `upright_marks`, `compose_stand`, `face_spec`, `specs` — type and the composition on the die.
