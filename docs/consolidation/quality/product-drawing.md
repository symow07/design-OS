# Product drawing — quality

**Job:** our own drawings ($0): the stand folded, empty and loaded with the products, and the product drawing in the
files. File: `apps/pipeline/services/product_drawing.py`.

**The bar, in numbers:** every printed face drawn where the die folds it (the faces' own pixels, never redrawn); the
loaded view at the brief's count; the same bytes on the same input.

**Before → after, same input.** Nothing moved into it; it no longer imports lid_master (its own `REPO`). Round 3's
product drawing in Make my files: the same bytes before and after the merges (`engines/runs/chain-before.json` →
`chain-after-native.json`, zip member `product-drawing.png`; `objects` SAME on every run since).

**Verdict: SAME.** Reason: no part was merged in; its one dependency on a retired engine was cut.

**Weakest point:** the drawings are schematic projections, not renders: no material, light or gloss.
