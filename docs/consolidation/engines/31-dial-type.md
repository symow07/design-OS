# 31 · Dial type

`apps/pipeline/services/round_files_dial.py` · chain step: **Live type on the stand header**

## What it does today (read from its code)
`header_type` (:357) reads the drawn header: `band_masks` (:50) finds each shade band by colour (ΔE00 against the
brief's hexes, through lid_master's colour maths), `dial_centre` (:100), `label_windows` (:144) and `shade_labels`
(:165) set each shade's label on its own band, `free_ring`/`ring_type` (:212, :247) set BBROSE upright and ملمع شفاه along
the navy ring (round_files_ornament.layout_runs); metrics from round_balm_master.glyph_metrics.

## The run ($0)
Round 3's drawn header face (faces/header/face.png) read and its type placed through the face builder's `marks`; the
dial tests run.
Recorded in [runs/31.json](runs/31.json), made by `docs/consolidation/probe.py 31`. What came out:
- `face`: {"size_px": [1223, 928], "mode": "RGB", "bytes": 1223777, "sha256": "a16654bc8b2c08bd"}
- `px_per_mm`: 10.822276
- `header_marks`: {"type_rows": 9, "texts": [null, null, null, null, null, null, null, null], "logos": 0, "placement": "{'labels': {'shade_0': {'placed': True, 'band_px': 194637, 'thickness_px': 172.6, 'centre_px': [229.0, 275.0], 'size_pt': 12.6}…
- own tests (test_round_files_faces.py, -k "dial or ring or label or header"): **2 passed, 19 deselected, 5 warnings in 1.32s**
- seconds: 3.0; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `band_masks`, `dial_centre`, `label_windows`, `shade_labels`, `free_ring`, `ring_type`, `header_type`.
