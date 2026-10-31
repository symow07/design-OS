# The face builder — quality

**Job:** the stand's faces painted on the die, each printed face at print resolution; the bottle and cap on their
flat nets; live type placed; the stand composed at 1:1. File: `apps/pipeline/services/round_files_faces.py`.

**The bar, in numbers:** every printed face at 300 ppi native on its own die outline; nothing outside the die (the die
applied again: 0 pixels off it differing from the template); each face checked against what it was drawn from
(CIEDE2000 on a 16 × 16 grid of its printed pixels: median ≤ 10, p90 ≤ 20), plain faces plain (≤ 2% of pixels over
ΔE00 15 from their own colour); a painting that did not keep the die never drawn from (crop coverage ≥ 0.9, ≤ 50%
unpainted); the composed stand at 300 ppi.

**Before → after, same input** (round 3; before: its faces cut from one painting of the whole die, `engines/runs/
chain-before.json`; after: attempt 3 and its repairs, `engines/runs/chain-live-1029.json`, `runs/faces-1029.json`):

| Face | Before: px/mm (ppi) | After: px/mm (ppi), source | Against its reference (median / p90) |
|---|---|---|---|
| header (107 × 78.2 mm) | 2.35 (59.8) | 11.81 (300), panel | 4.19 / 8.29 |
| header back | 2.35 (59.8) | 11.81 (300), panel | 1.56 / 2.21 |
| front strip | 2.35 (59.8) | 11.81 (300), panel from D2's own view | 6.29 / 76.35 (the picture's perspective: looked at, right) |
| right side, left side | 2.35 (59.8) | 11.81 (300), panels on the board swatch | 1.02 / 1.25, 0.98 / 5.62 |
| back | 2.35 (59.8) | 11.81 (300), board ($0) | plain |
| bottle | front only, sides plain | 14.79 (376), its four sides on a net | — |
| cap | front only | 19.14 (486), four sides and top on a net | — |
| the composed stand | 59.8 ppi | 300 ppi (4901 × 4904 px) | read back 0.0003 mm |

Every part moved in is identical to its donor in behaviour (the four zilal helpers differ by a docstring and a renamed
constant; `runs/moved-parts.json`).

**Verdict: BETTER** — 5× the resolution on every stand face, the products die-first, and every face checked against
what it was drawn from.

**Weakest point** (what round 3's first real run showed): the image model does not keep the die's geometry when it
paints the whole die — it stretched it (registration IoU 0.53; side-wall coverage 0.26 and 0.31; the front strip
painted above its panel). The painting is now a gate, not a source, for the faces it did not keep, but the "idea"
painting itself is only as good as that one call; and a face drawn from the picked picture's perspective view cannot be
judged by the ΔE grid (the front strip stays flagged for the owner's eye).

Annotation, 2026-10-30 (the owner's part 1, CURRENT_DECISIONS.md): the layering this card measures (`layer_face`, its fitting and its vector share) is removed: "fitting vectors over a painting cracked it; the painting prints whole". The face builder now makes one wrap of the panels that meet at a fold, cuts it along the die, and measures every panel's ground and every fold on the raster that prints. Its weakest point is now the wrap's native resolution, about 250 PPI.
