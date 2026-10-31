# MEASUREMENT NEEDED — SLIMMING_CREAM_R-108-A.ai

> **2026-07-07 — measurement is now AUTOMATED**: `manage.py
> measure_dielines <folder> --out report.json` (PyMuPDF, dev dependency)
> extracts cut/crease linework from PDF-compatible .ai files and reports
> the ratios below with an adoption gate (>=5 files, tight MAD).
> First run against `design_models/` (91 files): **10 measurable flats,
> none a consistent STE family** — they are display boxes and multi-piece
> layouts, so all constants stay as-is. Re-run the command when true
> tuck-end-carton production files (like SLIMMING_CREAM_R-108-A.ai) are
> added; the report at `exports/dieline_measure_report.json` shows
> per-file skip reasons. Constants move only via the deliberate Phase-B
> step (snapshot regen + DECISION entry).

Milestone 9.3 asked for the friction-slit width factor and the tuck
shoulder Bezier tangent factor to be re-derived from measured reference
data. The only measured dataset in the repo,
`28x28x120_coordinate_dump.json`, **predates DECISION-010/012/014/016**:
its tuck flaps are rounded rectangles (corner radius ≈ W × 0.107, tuck
height W × 0.9) and its slits are straight LINE elements — it contains
none of the curve or stadium-slit points these constants need. Both
constants therefore remain **provisional** (see DECISION-017 in
`geometry_decisions.md`):

- `_SLIT_WIDTH_FACTOR = 0.327` — provisional estimate
- `_TUCK_SHOULDER_K = 0.55228474983` — standard quarter-ellipse cubic
  constant, not the measured Pacdora tangent

## Exact coordinates to extract from SLIMMING_CREAM_R-108-A.ai

Open the file's PDF path data (same method used for DECISION-016) and
record, in mm, for **both** active tuck flaps (top back and bottom
front):

1. **Shoulder cubic control points — 8 coordinate pairs total.**
   For each of the four shoulder curves (left + right shoulder on each
   tuck flap), the `v`/`y` operator arguments give:
   - curve start point (on the flap side edge, vertical tangent)
   - control point 1
   - control point 2
   - curve end point (on the flat top, horizontal tangent)
   From these, compute the tangent lengths
   `k_v = |c1 − p0| / curve_h` and `k_h = |c2 − p1| / tuck_inset`; the
   replacement for `_TUCK_SHOULDER_K` is their measured value (report
   separately if `k_v ≠ k_h` — the engine currently assumes one k).

2. **Stadium slit extremes — 4 x-values total.**
   For each of the two friction slits (top back flap, bottom front
   flap): the leftmost and rightmost x of the slit outline (centre of
   each semicircular end cap ± cap radius is also acceptable; state
   which). The replacement `_SLIT_WIDTH_FACTOR` is
   `(x_right − x_left) / width_mm` for the carton's W as printed in the
   file's spec block.

3. **Context values needed to normalise:** the file's `width_mm` (panel
   width as drawn), each flap's `curve_h` (vertical span from curve
   start to flat top) and `tuck_inset` (horizontal span from flap side
   edge to flat-top corner) — used to cross-check against the locked
   DECISION-016 ratios (0.218 and 0.227).

## What to do with the measurements

1. Update `_SLIT_WIDTH_FACTOR` and `_TUCK_SHOULDER_K` in
   `apps/dielines/geometry/engine.py`.
2. Regenerate the golden snapshot
   `apps/dielines/docs/28x28x120_engine_reference.json` (the exact-match
   regression test in `tests/test_reference_regression.py` will fail
   until you do — that is intentional).
3. Update DECISION-017 in `geometry_decisions.md` from PROVISIONAL to
   LOCKED with the measured values and delete this file.
