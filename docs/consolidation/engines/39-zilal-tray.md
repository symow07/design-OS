# 39 · zilal_tray

`apps/pipeline/services/zilal_tray.py` · chain step: **None (Day 12); four helpers the face builder uses**

## What it does today (read from its code)
`build` (:690) composes the Day 12 family display's faces from Ẓilāl's lid plate on the 0.1 die; `lid_banks`,
`bank_drift`, `drift_clear_of_creases`, `place_hero` and the words and marks writers do the Day 12 work. The face
builder uses only four names: `turn` (:637, a quarter-turn of a picture), `face_mm_size` (:641, a face's upright size),
`upright_polygon` (:593, its outline in the upright frame with the 3 mm bleed) and `K` (300 ppi in px/mm).

## The run ($0)
The four helpers on each printed face of round 3's die; the Day 12 display tests run.
Recorded in [runs/39.json](runs/39.json), made by `docs/consolidation/probe.py 39`. What came out:
- `faces`:
  - header: {"w_h_mm": [107.0, 78.25], "outline_area_mm2": 8372.7, "turned_4x6": [4, 6]}
  - header_back: {"w_h_mm": [107.0, 79.75], "outline_area_mm2": 8533.1, "turned_4x6": [4, 6]}
  - front: {"w_h_mm": [107.0, 18.2], "outline_area_mm2": 1947.6, "turned_4x6": [4, 6]}
  - side: {"w_h_mm": [82.0, 143.78], "outline_area_mm2": 6641.1, "turned_4x6": [6, 4]}
  - left: {"w_h_mm": [82.0, 143.78], "outline_area_mm2": 6641.1, "turned_4x6": [6, 4]}
  - back: {"w_h_mm": [107.0, 143.78], "outline_area_mm2": 15384.0, "turned_4x6": [4, 6]}
- `K_px_per_mm`: 11.811023622047244
- own tests (test_day12_display.py): **9 passed, 5 warnings in 4.27s**
- seconds: 5.2; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the four helpers. Old: the Day 12 tray composition.

## Parts worth keeping
- `turn`, `face_mm_size`, `upright_polygon`, `K`.
