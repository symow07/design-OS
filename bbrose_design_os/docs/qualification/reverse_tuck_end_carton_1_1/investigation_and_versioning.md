# Reverse tuck end 1.1 qualification — mirror audit & versioning

Phase 2A-9C slice 3. `reverse_tuck_end_carton/1.1` is the MIRROR of
STE 1.1: identical panel layout (glue | back | side_left | front |
side_right) and identical DECISION-016 ratio formulas, but the tuck
attachment is SWAPPED — top tuck on FRONT, bottom tuck on BACK (STE:
back/front). It is PROVISIONAL (no measured reference) and stays so;
qualification grants no production authority.

## Mirror audit (slice-3 focus) — CLEAN

The reverse tuck placement introduces no coordinate defects. Verified on
every supported fixture and across the property sweep:
- top tuck attaches to FRONT, bottom tuck to BACK (declared + measured)
- the top-tuck polygon sits over the FRONT column and the bottom-tuck
  polygon over the BACK column (a mirrored x-sign error would land them
  on the wrong panel — it does not)
- stadium friction slits name the mirrored panels (top-front, bottom-back)
- cut contour closed + non-self-intersecting; zero cut/fold overlap; no
  duplicate segments; RTE cut area and flat size are IDENTICAL to STE at
  the same dimensions (the mirror only swaps the tuck column)
- reconciliation + folded checks pass identically to STE

## Honest supported domain

Because RTE reuses STE's W-derived tuck and D-derived dust, its domain
is the SAME narrow band (derived here independently, not inherited):

    W >= 1.262 D        (dust pair clearance)
    1.227 W - D < H/2   (tuck lip vs body height — shared STE defect)
    0.631 D <= 1.227 W - 2   (dust clamp must not engage)
    slit web >= 2 mm at the NOMINAL slit width
    D + t >= G + 3;  H > W;  H > D;  D <= 2.5 W;  ranges as published

## Evidence

- 13 fixtures, 11 SUPPORTED; boundary pairs stable on both sides of the
  dust clearance and the tuck-lip rule; every supported row passes the
  mirror audit
- property sweep seed **20260725**: 150
  in-domain + 250 whole-space samples,
  173 supported, 227 rejected
  by named constraints, **0 failures/crashes**
- 1.1 GENERATOR unchanged; UNSUPPORTED enforced at the qualification
  layer / endpoint / UI (new-die paths), historical reproduction free

## Versioning decision

**Keep 1.1; publish the narrow domain honestly.** RTE 1.1 shares STE
1.1's W-derived tuck defect, so a future **reverse_tuck_end_carton/1.2**
would adopt the SAME D-derived correction proposed for STE 1.2 (and
validated by Skynte). Recorded, NOT implemented. RTE remains PROVISIONAL
regardless of qualification — authority is TECHNICALLY_QUALIFIED_DOMAIN
over the narrow band only; no promotion without physical/manufacturer
evidence.
