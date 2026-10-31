# 14 · Brief contract

`apps/pipeline/services/round_ideas_brief.py` · chain step: **Brief in**

## What it does today (read from its code)
`normalize_ideas_brief` (:57) whitelists a brief's printed copy (brand, product, shade names) and keeps geometry and
creative direction out of the copy; `printed_copy` (:123) is the only source lettering may come from;
`is_designer_brief` (:15) marks the designer flow; `gloss_brief` (:131) is the lip gloss default.

## The run ($0)
Round 3's brief normalised and its printed copy read; the brief tests of the round flow file run.
Recorded in [runs/14.json](runs/14.json), made by `docs/consolidation/probe.py 14`. What came out:
- `designer`: true
- `printed_copy`: {"brand": "BBROSE", "product": "Lip Gloss / ملمع شفاه", "shade_names": ["Rose Glass", "Fig Nectar", "Ember Glow"]}
- `keys`: ["audience", "banned", "bar", "contract", "copy", "dimensions_mm", "flow", "material", "measurements_provisional", "name", "product_type", "schema", "shades", "shape", "stand", "truths"]
- own tests (test_round_flow.py, -k "brief"): **3 passed, 38 deselected in 4.09s**
- seconds: 5.0; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `normalize_ideas_brief`, `printed_copy`, `is_designer_brief`.
