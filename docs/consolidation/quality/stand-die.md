# The stand die (counter_tray_header 1.0) — quality

**Job:** the counter stand's die from the brief and the picked picture, before any design.
File: `apps/dielines/geometry/counter_display.py` (`solve_stand`, the product grid, sightlines, the rear raise).

**The bar, in numbers:** the fold check valid; every product's top 25 mm band seen whole (26 of 26 samples) from the
engine's eye (500 mm out, 350 mm up); the rear products cover at most the header's 3 mm safe margin from that eye; the
owner's ruled size kept (round 3: 225 mm high, header leaf 107 × 78.2 mm); one solver.

**Before → after, same input** (round 3's brief and reading; donor: counter_tray_header 0.1's grid with the stand
adapter round_files_stand, as committed on round 3 at 26db887; after: `c169b09`):

| | Before | After |
|---|---|---|
| Height, header leaf | 225.02 mm, 107 × 78.25 mm | 225.02 mm, 107 × 78.25 mm |
| Row seats | 19.70, 28.23, 39.05 mm | 10.3, 30.2, 50.7 mm |
| Top band seen, rows 1 / 2 / 3 | 1.0 / 0.538 / 0.615 | 1.0 / 1.0 / 1.0 |
| Products passing | 4 of 12 | 12 of 12 |
| Header covered from the eye | not measured | 2.946 mm (≤ 3.0 safe) |
| Fold check | valid | valid |
| Solvers of a stand die | two (0.1, 1.0) | one |

Every part moved in is identical to its donor but `solve_stand`, whose change is this fix (`runs/moved-parts.json`).
Tests: dielines/tests/test_counter_display.py (the matrix, the planted faults, round 3 inside its size and the 0.1 mm
higher seat that would not hold, the floor rows, the header-cover negative control).

**Verdict: BETTER** — 12 of 12 products seen, inside the owner's size.

**Weakest point:** the front row sits 9.4 mm lower behind the front lip than in D2's picture (its band still shows in
full), and a stand solved from the brief alone (no picture) keeps its rows on the floor and fails its sightline,
reported for the designer's eye: no rise is invented where nothing was measured. A physical sample is still owed.
