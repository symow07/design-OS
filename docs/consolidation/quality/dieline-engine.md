# The dieline engine — quality

**Job:** a carton's flat die at 1:1 mm (cut, crease, panels, glue, safe, bleed), qualified before it is offered.
Files: `apps/dielines/geometry/engine.py` (`calculate_dieline`), `registry.py`, `trade_tuck.py`, `fold_check.py`,
`qualification/`, `exporters/folded_diagnostic.py`.

**The bar, in numbers:** the fold check passes; the die read back from its 1:1 PDF lies within 0.01 mm of the
engine's own geometry, cut and crease, both ways; the page's TrimBox and BleedBox equal the die's cut and bleed
boxes within 0.01 mm; the CutContour and Crease separations are present.

**Before → after, same input** (three house cartons: reverse tuck end 1.4 and straight tuck end 1.4 at 22 × 22 ×
105 mm, straight tuck end at 28 × 28 × 120 mm; `runs/carton-before/`, `runs/carton-after/numbers.json`):

| | Before (row 9's writers) | After (the one die writer) |
|---|---|---|
| Flat size, reverse tuck 1.4 | 101.8 × 167.25 mm | 101.8 × 167.25 mm |
| Cut read-back, engine ↔ PDF | 0.0 / 0.0 mm (178 vertices, 346 points) | 0.0 / 0.0 mm (same) |
| Crease read-back | 0.0 / 0.0 mm (24 / 24) | 0.0 / 0.0 mm |
| TrimBox vs cut, BleedBox vs bleed | 0.0, 0.0 mm | 0.0, 0.0 mm |
| CutContour, Crease, All plates | present | present |

**Verdict: SAME.** Reason: no part was merged into the engine (rows 2, 3, 4 and 10's folded diagnostic were already its
own files under one entry); the die it draws is the same on every input measured. What changed is who writes its
files (the die writer: see die-writer.md).

**Weakest point:** only the trade tuck ends 1.4 (and Skynte 1.0) are production-qualified; ECMA STE 0.1 and opposed tuck
0.1 refuse or fail the fold on the goal's products (card 3), and they stay held by the old carton choosers.
