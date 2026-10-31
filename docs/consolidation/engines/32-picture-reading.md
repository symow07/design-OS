# 32 · Picture reading

`apps/pipeline/services/round_files_reading.py` · chain step: **Reading the picked picture (panels, COPY fields)**

## What it does today (read from its code)
`copy_fields` (:31) gives the only printable characters (from the brief's COPY); `normalise_reading` (:171) repairs a
reading item by item and drops only the bad one; `shade_loading` (:255) reads each seat's shade; `validate_inspection`
(:299); `text_rows` (:355) and `ornament_rows` (:362) turn the reading's text into rows the faces place.

## The run ($0)
Round 3's COPY fields and its saved reading's panels; the reading tests run.
Recorded in [runs/32.json](runs/32.json), made by `docs/consolidation/probe.py 32`. What came out:
- `copy_fields`: {"product_latin": "Lip Gloss", "product_arabic": "ملمع شفاه", "shade_0": "Rose Glass", "shade_1": "Fig Nectar", "shade_2": "Ember Glow"}
- `panels`: ["body_front", "cap_front", "stand_base", "stand_header"]
- own tests (test_round_files_faces.py, -k "reading or read"): **2 passed, 19 deselected, 5 warnings in 0.26s**
- seconds: 1.1; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `copy_fields`, `normalise_reading`, `validate_inspection`, `text_rows`, `ornament_rows`, `shade_loading`.
