# 7 · Stand die sheets (0.1)

`apps/dielines/exporters/counter_tray_header_sheets.py` · chain step: **Die writing**

## What it does today (read from its code)
Writes a counter_tray_header die (0.1 or 1.0's parts) as an SVG with Inkscape layers (`write_svg` :131), a layered die
PDF (`write_die_pdf` :284, layers ARTWORK, CUT, CREASE, SAFE, BLEED, WORDS), A3 tiles (`write_tiles_pdf` :342), a plan
and elevation sheet (`write_plan_elevation` :568) and a PNG of a PDF (`render_png` :767). `apply_layers` (:301) turns
marked content into optional-content groups with fitz; the 1.0 writer imports it.

## The run ($0)
Round 3's 1.0 die written as an SVG and a layered die PDF; the PDF read back for its layers.
Recorded in [runs/07.json](runs/07.json), made by `docs/consolidation/probe.py 7`. What came out:
- `svg_groups`: ["artwork", "bleed", "safe", "crease", "cut"]
- `pdf_layers_written`: ["ARTWORK", "CUT", "CREASE", "BLEED", "SAFE", "WORDS"]
- `pdf_pages`: 1
- `pdf_ocgs`: ["ARTWORK", "CUT", "CREASE", "BLEED", "SAFE", "WORDS"]
- `svg_bytes`: 95941
- seconds: 0.2; files written: 2 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: `apply_layers`, which 1.0 already calls. The rest writes the same die the 1.0 writer writes (die PDF, sheets),
in a second format nobody downloads; Make my files does not call it.

## Parts worth keeping
- `apply_layers` — the layer (OCG) writer the 1.0 die files use.
- `safe_areas` — each face's safe area for the sheets.
