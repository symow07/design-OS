# 8 · Stand die files (1.0)

`apps/dielines/exporters/counter_display_files.py` · chain step: **Die writing; painting on the die**

## What it does today (read from its code)
`write_all(record, folder, artwork)` (counter_display_files.py:295) writes the die as a layered 1:1 PDF (`write_pdf` :57,
layers ARTWORK, CUT, CREASE, PERF, GLUE, BLEED, DIMENSIONS, spot cut and crease), DXF (`write_dxf` :102), CF2
(`write_cf2` :127), a nested sheet (`nest` :148) and an A3 assembly drawing (`assembly_drawing` :199). The flat half:
`flat_frame` (:321) fixes one mm→px transform, `flat_masks` (:355) and `flat_template` (:442) draw the painting's
template and the owner's sheet, `apply_die` (:528) re-applies the die to a painting, `die_proof` (:551) measures it,
`pdf_readback` (:587) reads the written PDF's cut, crease and artwork box back, `fold_pairs` (:626) samples each fold.

## The run ($0)
Round 3's committed die written (every file), the 1:1 PDF read back; its flat template made again and compared byte for
byte with the round's own; a $0 stand-in painting (each printed face's pixels coloured and textured, moved 3 px down and
2 px right) settled by the die and proved.
Recorded in [runs/08.json](runs/08.json), made by `docs/consolidation/probe.py 8`. What came out:
- `files`: ["die.pdf", "die.dxf", "die.cf2", "assembly.pdf"]
- `ocgs`: ["ARTWORK", "BLEED", "CREASE", "CUT", "DIMENSIONS", "GLUE", "PERF"]
- `nest`: {'board': 'E-flute corrugated, 1.5 mm', 'sheets': [{'sheet_mm': [1400, 1000], 'sets': 2, 'parts_placed': 14, 'yield': 0.155, 'turned': False, 'method': "shelf packing of the parts' bleed rectangles; whole sets only"}, {'sheet_mm'…
- `readback_cut_crease`:
  - CUT: {"vertices": 403, "read_back": 632, "max_mm": 0.0003}
  - CREASE: {"vertices": 104, "read_back": 104, "max_mm": 0.0002}
- `template_same_as_round3`: true
- `frame`: {"size": "1024x1536", "dpi_at_1to1": 59.8}
- `stand_in_proof`:
  - registration: {"best_shift_px": [2, 3], "iou_at_zero": 0.9409, "iou_at_best": 0.9641, "search_px": 12, "note": "the painting's own drift before the die was applied again"}
  - outside: {"pixels": 1285946, "differing_from_template": 0, "zero_offset": true}
  - pdf: {"CUT": {"vertices": 403, "read_back": 632, "max_mm": 0.0003}, "CREASE": {"vertices": 104, "read_back": 104, "max_mm": 0.0002}, "ARTWORK": {"box_mm": [4.721, -86.8438, 439.8304, 565.8201], "max_mm": …
- `continuity_folds`: 4
- seconds: 1.2; files written: 15 (kept in the run folder, not committed)

## Verdict: GOOD
The stand-in was moved 3 px down and 2 px right; the proof's best shift is [2, 3] (x, y): the drift found exactly.
After the die was applied again, 0 of the 1,285,946 pixels off the printed faces differ from the template; the 1:1 PDF
reads back within 0.0003 mm (cut), 0.0002 mm (crease) and 0.0002 mm (the artwork's box).

## Parts worth keeping
- `write_pdf`, `write_dxf`, `write_cf2`, `nest`, `assembly_drawing`, `write_all` — the die-maker's files.
- `flat_frame`, `flat_masks`, `flat_template`, `apply_die`, `die_proof`, `pdf_readback`, `fold_pairs` — the die-first
  method, measured.
