# 10 · Die previews and mockups

`apps/dielines/exporters/mockup_3d.py (+3)` · chain step: **None (the chain draws its own folded drawing)**

## What it does today (read from its code)
`export_folded_mockup` (mockup_3d.py:26) writes an isometric folded PNG of a carton from a flat picture;
`export_design_preview_svg` (design_preview.py:83) embeds artwork clipped to panels, `export_design_components_ai`
(:239) and `export_design_preview_ai` (:427) write .ai files; `export_folded_diagnostic` (folded_diagnostic.py:75)
draws a four-stage fold (it needs the qualification's collision and closure records). `generate_provisional_preview`
(services/provisional_preview.py:72) writes a nine-item provisional package for a DielineJob.

## The run ($0)
Round 3's bottle carton previewed: the folded diagnostic, the folded mockup of a flat design picture, the design
preview SVG; the design-preview tests run.
Recorded in [runs/10.json](runs/10.json), made by `docs/consolidation/probe.py 10`. What came out:
- `folded_diagnostic`: {"error": "KeyError: 'main_a'"}
- `folded_mockup`: {"size_px": [272, 1015], "mode": "RGB", "bytes": 4051, "sha256": "ce2d518de3350355"}
- `design_preview_svg`: 26943
- own tests (test_design_preview.py): **8 passed, 5 warnings in 3.77s**
- seconds: 4.7; files written: 3 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- `export_folded_diagnostic` — a fold shown in stages (only with the qualification's records).
