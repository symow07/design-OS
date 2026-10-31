# 17 · Whole-object round (Round 1/2)

`apps/pipeline/services/round_steps.py (+3)` · chain step: **None (Round 1/2)**

## What it does today (read from its code)
`round_steps.run_step` (:743) runs Round 2's steps: twenty seeds, twenty sketches as edits, eligibility checks,
readings, a coarse jury, pairwise batches, forks, the final order, the pick page. `round_sheet.build` (:140) lays a
product's panels on one sheet; `needs_repair` (:30). `round_product.normalize_brief` (:121) and
`repair_missing_body_right` (:203, lip gloss wand only). `round_report.finalize` (:207) and `tag_if_requested` (:283,
hard-wired to the slug r2-gloss and the tag round-2-gloss-a).

## The run ($0)
Round 2's lip gloss brief normalised and its panel sheet drawn at $0; the media round file's non-ideas tests run.
Recorded in [runs/17.json](runs/17.json), made by `docs/consolidation/probe.py 17`. What came out:
- `panels`: 12
- `sheet`: {"schema": "round_sheet/2", "files": ["sheet-mask.png", "sheet-verification.json", "sheet-windows.png", "sheet.json", "sheet.png"]}
- own tests (test_product_round_media.py, -k "not ideas"): **65 passed, 7 deselected, 5 warnings in 58.88s**
- seconds: 59.9; files written: 5 (kept in the run folder, not committed)

## Verdict: UNUSED BY THE GOAL

## Parts worth keeping
- nothing the chain needs: the designer flow replaced the panel sheet and its jury.
