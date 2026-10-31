# PALT-P1 Mechanism Decision — analysis and recommendation

**Status: RECOMMENDATION — owner decision required. Nothing here is
approved or manufacturing-confirmed.**

## What changed since PALT-M2

PALT-M2 computed a 101.8 × 113.3 minimum. That figure was **understated**:
it omitted lid structural borders (2 × 2.0), assembly clearance (0.3),
moulding tolerance (0.2) and internal tray walls. The PALT-M3 stack-up
includes them, so every minimum grew. This is the intended direction — a
more complete model produces larger, more honest numbers.

## Strategy matrix result

| Config | Mechanism | Hinge edge | Min W × D | Fits 116 × 92? |
|---|---|---|---|---|
| A1 | reserved band ×2 | long | 109.3 × 120.3 | no — depth |
| A2 | wall-integrated ×2 | long | 109.3 × 111.5 | no — depth |
| A3 | external barrel + wall clasp | long | 109.3 × 110.3 (+3.5 external) | no — depth |
| A4 | reserved band ×2 | short | 120.3 × 109.3 | no — width + depth |
| A5 | wall-integrated + magnetic | short | 111.3 × 109.3 | no — depth |
| A6 | living hinge + friction | long | 109.3 × 109.9 | no — **material conflict** (PP hinge on an ABS case) + depth |
| C1 | wall-integrated ×2, tight spacing | short | 103.5 × 101.3 | no — depth |
| C2 | reserved band ×2, tight spacing | short | 112.3 × 101.3 | no — depth |

**Result: `INFEASIBLE_UNDER_ALL_TESTED_MECHANISM_STRATEGIES`.** The depth
axis falls short by **9.3 mm** even in the most compact wall-integrated
configuration. This is *not* a claim of universal infeasibility — six
hinge/clasp combinations and both hinge edges were tested, not every
conceivable mechanism.

Two findings worth the owner's attention:

1. **Width was never the problem.** 116 mm accommodates every strategy
   except A4 (reserved bands on the short edges). The constraint is
   entirely on depth, because three 26.6 mm pocket modules plus gaps,
   margins, tray walls, case walls and lid borders already consume ~101 mm
   before any mechanism is added.
2. **Mechanism choice buys ~9–19 mm of depth**, orientation buys a
   further ~11 mm, and spacing buys ~10 mm — but the three together still
   land 9.3 mm above the 92 mm target.

## Height: three separated values (baseline strategy)

| Value | mm | Meaning |
|---|---|---|
| `GEOMETRIC_LOWER_BOUND` | **9.00** | solids + unavoidable clearance only — a mathematical artefact |
| `ENGINEERING_MINIMUM` | **11.15** | + adhesives, powder crown, parting gap, tolerance, warpage, mechanism height |
| `PREMIUM_DESIGN_TARGET` | **13.85** | + premium skins, comfortable clearance, decoration allowance |

The 15 mm target height is comfortable — it exceeds even the premium
target. **The 9 mm figure must never be described as a viable premium
production thickness**, and PALT-M2's two 9 mm results are hereby
reclassified accordingly.

## Recommendation (not the smallest option)

**Adopt a ~116 × 116 × 15 mm near-square premium envelope with
wall-integrated pin hinge + wall-integrated snap clasp on the long edge,
adhesive-fixed pans, mirror retained** (config A2 geometry at the
standard 4.0 mm gap / 5.0 mm margin, rounded up for premium comfort).

Reasoning:
- it keeps the **9 × 26 mm 3 × 3 layout** the owner retained;
- it keeps generous 4 mm gaps and 5 mm margins — the compact C1 option
  achieves 103.5 × 101.3 only by squeezing spacing to 2.0/3.0, which reads
  cheap rather than `MID_SIZE_PREMIUM`;
- 116 mm width is already the owner's stated target, so only depth moves;
- a near-square palette is a legitimate premium format, and the 116 mm
  width is preserved as a brand-consistent dimension;
- height 15 mm sits above the 13.85 premium target, leaving decoration
  headroom.

**Explicitly not recommended:** C1 (smallest) — the selection rule forbids
choosing the smallest automatically, and its tight spacing conflicts with
premium positioning.

## What would change this recommendation

A supplier technical drawing showing that hinge and clasp can be absorbed
into a thinner wall than our 1.2/1.0 mm estimates, or that lid structural
borders can be under 2 mm, would shrink the depth requirement. Those
figures are `DESIGN_DEFAULT` engineering estimates — the largest single
source of uncertainty in this analysis.
