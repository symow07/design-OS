# STE 1.1 qualification — investigation report & versioning proposal

Phase 2A-9C slice 1. `straight_tuck_end_carton/1.1` is qualified for
a NARROW honest domain; two DECISION-016 ratio formulas carry real
geometry defects outside it. **1.1 is preserved byte-stable; the fixes
are proposed as version 1.2 — a review decision, not implemented.**

## Real geometry defects found (intended-domain investigation)

1. **W-derived tuck height (`tuck = W × 1.227`).** The factor was
   measured from a SQUARE 28×28×120 reference where W = D, which hides
   whether the tuck should scale with the panel width or the opening
   depth. Physically the tuck folds over the D-deep opening (as
   DECISION-019 established for the side-seam archetype). Consequence:
   on wide-short cartons the lip (1.227·W − D) exceeds the engine's own
   `tuck_lip_vs_height` rule — **the historical 90×25×92 STE die once
   offered to task #50 fails it (lip 85.4 mm ≥ H/2 = 46 mm)**, matching
   the user's physical rejection of that geometry class.
2. **D-derived dust flaps (`dust = D × 0.631`) folding across the W
   opening.** Opposing dust flaps collide whenever W < 1.262·D —
   **including the measured 28×28×120 reference itself** (folded
   overlap 7.34 mm, failing the engine's own
   `dust_flap_opposing_clearance ≥ 0` rule).
3. **Silent formula alterations became explicit domain edges** (per the
   mandate): the DECISION-004 dust clamp and the DECISION-017 slit-web
   reduction now mark the domain boundary — a clamped flap or a reduced
   slit is outside the qualified domain, never silently emitted as
   'supported'.

## Honest supported domain (compensated mode, t ∈ [0.3, 1.0])

    1.262·D ≤ W   (folded dust clearance — engine parity, limit 0)
    1.227·W − D < H/2   (tuck lip vs body height)
    0.631·D ≤ 1.227·W − 2   (dust clamp must not engage)
    slit web ≥ 2 mm at the NOMINAL slit width (numeric, DECISION-017)
    D + t ≥ G + 3;  H > W;  H > D;  D ≤ 2.5·W;  ranges as published

The band is real but narrow: roughly 1.262·D ≤ W < (D + H/2)/1.227.
Unsupported regions (explicit): all square-ish cartons (W < 1.262·D,
incl. the measured reference), all wide-short cartons
(W ≥ (D + H/2)/1.227, incl. 90×25×92-class dies).

## Qualification evidence

- fixtures: 10/15 SUPPORTED (8 structural + 2 inside-boundary); the
  measured reference and the historical task-50 STE die REJECTED with
  named constraints; boundary pairs stable on both sides
- property sweep seed **20260723**: 150
  in-domain + 250 whole-space samples,
  169 supported, 231 rejected
  by named constraints, **0 failures/crashes**
- semantic difference from opposed-tuck: the 1.1 GENERATOR does not
  fail closed (historical jobs must reproduce byte-identically);
  DIMENSION_COMBINATION_UNSUPPORTED is enforced by the qualification
  layer, the qualify_dimensions endpoint and the dimension-gate UI —
  every path that creates NEW dies

## Versioning proposal (REVIEW REQUIRED — not implemented)

**straight_tuck_end_carton/1.2**: D-derived closure (tuck = D + lip
with a parametric lip, DECISION-019-style), dust depth bounded by the
opening (min of D-derived and W/2-clearance), slit width bounded
non-silently. 1.1 stays registered and byte-stable for historical
reproduction; 1.2 would ship with its own contract, domain, sweep,
matrix and physical-test plan. Until then 1.1's authority is
TECHNICALLY_QUALIFIED_DOMAIN over the narrow band above ONLY.

Task-50 note: none of this touches task #50 (opposed-tuck archetype).
