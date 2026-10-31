# Skynte side-seam 1.0 qualification — investigation & versioning

Phase 2A-9C slice 2. `skynte_foundation_tuck_carton/1.0` reconstructs
the task-#47 Skynte Foundation reference (glue | side | main | side |
main; tucks on the two MAIN panels). It uses the CORRECT D-derived
closure (tuck = D + fixed 16 mm lip, DECISION-019), so — unlike STE 1.1
— it has **no lip-vs-height defect**. Task #47 is the golden fixture;
1.0 is untouched.

## Honest supported domain

The domain is defect-free but BOUNDED by two real limits derived from
the generator's own rules:

1. **Width cap W < 73.4 mm** — the shoulder curve is W-derived
   (`0.218·W`) while the tuck lip is a FIXED 16 mm constant, so the
   curve stops fitting inside the lip at W ≥ 16/0.218 ≈ 73.4 mm. The
   **generator already fails closed here** (GeometryError) — a hard
   LIMITATION, never silent distortion. (Candidate future 1.1: a
   parametric lip or D-derived shoulder curve would lift the cap; not
   a required fix.)
2. **W ≥ 1.262·D** — D-derived dust flaps (`0.631·D`) fold across the W
   opening and collide below this (same family as STE; the generator
   does NOT fail closed, so the qualification layer enforces it). The
   42×32 reference sits just inside it (clearance 1.6 mm).

Plus the schema rules (H > W, H > D, D ≤ 2.5·W), the entry-slit hinge
guard (slits + notches ≤ 60% of the tuck base) and the published
ranges. Combined, the usable envelope is narrow-to-medium tall cartons
up to ~73 mm wide — which covers the cosmetics cartons this archetype
was reconstructed for.

## Evidence

- 13 fixtures, 10 SUPPORTED; the task-47 reference SUPPORTED with its
  pinned hash `2be58c7bdb0afcc5728d700789c3e1e7`;
  boundary pairs stable on both sides of the width cap, the dust
  clearance and the height rule
- property sweep seed **20260724**: 150
  in-domain + 250 whole-space samples,
  147 supported, 250 rejected
  by named constraints, **0 failures/crashes**
- the 1.0 GENERATOR is unchanged; the task-47 reference regenerates
  byte-identically (pinned by test)

## Versioning decision

**No version bump.** 1.0 is defect-free within its bounded domain; the
width cap is an honest fail-closed limitation, not a geometry defect.
A future **1.1** could widen the cap (parametric lip / D-derived
shoulder curve) — recorded as a candidate improvement only.

Contrast with STE 1.1 (slice 1), which DID need a proposed 1.2 because
its W-derived tuck produced physically wrong lips inside its intended
domain. Skynte's D-derived closure is the model STE 1.2 would adopt.
