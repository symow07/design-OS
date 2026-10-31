# 9 · Carton exporters (dielines app jobs)

`apps/dielines/exporters/ai_exporter.py (+6)` · chain step: **Cartons (writing a carton die and its artwork)**

## What it does today (read from its code)
`export_svg` (svg_exporter.py:99) writes a carton's print SVG; `export_production_pdf` (production_pdf.py:191) the CMYK
production PDF with CutContour and Crease spots, registration marks, dimensions and a title block;
`export_ai_from_production_pdf` (ai_exporter.py:43) copies that PDF to .ai; `pdf_layers` (`begin` :22, `end` :27,
`apply` :40, `layers_of` :66) is the optional-content writer both stand die writers use; `label_layout.plan_label`
(:483) fits a label's copy down to a 3 pt floor; `export_service.generate_exports` (:82) runs geometry and every
exporter for a DielineJob row (the dielines app's API). `production_pdf.py:86` names a Linux font folder that does not
exist here; the bundled Noto fonts are found first.

## The run ($0)
Round 3's bottle carton (straight tuck 1.4) written as SVG, CMYK production PDF and .ai; the PDF's layers read back;
the SVG and production PDF tests run.
Recorded in [runs/09.json](runs/09.json), made by `docs/consolidation/probe.py 9`. What came out:
- `svg`: 11921
- `production_pdf`: {"path": "carton_production.pdf", "pages": 1, "ocgs": ["BLEED", "CREASE", "CUT", "DIMENSIONS", "GLUE", "SAFE"], "bytes": 37301}
- `ai_from_pdf`: carton.ai
- `pdf_layers_of`:
  - CUT: {"prints": true}
  - CREASE: {"prints": true}
  - GLUE: {"prints": false}
  - BLEED: {"prints": false}
  - SAFE: {"prints": false}
  - DIMENSIONS: {"prints": false}
- own tests (test_svg.py, test_production_pdf.py): **68 passed, 5 warnings in 0.35s**
- seconds: 1.2; files written: 3 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the layer writer and the production PDF. Old: `generate_exports` and the job API serve the dielines app's jobs,
which the chain never starts; the round's .ai is written by round_files_export.

## Parts worth keeping
- `pdf_layers.begin/end/apply/layers_of` — the PDF layer writer (used by the 1.0 die files).
- `export_production_pdf` — spot cut and crease, registration and title block for a carton.
- `label_layout.plan_label` — copy fitted to a panel with a floor.
