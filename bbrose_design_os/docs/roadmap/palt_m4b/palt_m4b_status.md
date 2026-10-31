# PALT-M4B — STATUS: IN PROGRESS, NOT COMPLETE

**This milestone is NOT finished and is NOT submitted for owner review.**
It is committed so the work is not lost and the state is unambiguous.

## Owner review of PALT-M4 recorded

`PALT_M4_IMPLEMENTATION: PASS` · `PALT_M4_AUTOMATED_VALIDATION: PASS` ·
`PALT_M4_PRODUCT_GEOMETRY: FAIL` · `PALT_M4_MECHANISM_CREDIBILITY: FAIL` ·
`PALT_M4_MOULDED_CONSTRUCTION: FAIL` · `PALT_M4_VISUAL_QUALITY:
UNACCEPTABLE` · `PALT_P1_OWNER_APPROVAL: REJECTED` ·
`PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED` · `PALT_M5: BLOCKED`.

**The complete PALT-M4 package is preserved unchanged** (verified: no
modifications under `docs/roadmap/palt_m4/`).

## What is built and verified

`services/palette_moulded_geometry.py` — 57 components, all manifold,
deterministic identities:

- **Recessed pocket system defined as real CSG**: a continuous moulded
  tray deck minus nine *drafted* pocket cutters (2.0° pocket draft), with
  pocket floor at z 2.50, deck at z 7.15.
- **Pans seated ON the pocket floor** (z 2.65–6.15), recessed **1.0 mm**
  below the deck — not discs on a slab. Separate geometry per position for
  pocket cutter, metal pan (a real open-topped cup with wall and floor
  thickness) and powder volume (crowned, not a flat plate).
- **Parameterised** pan OD, metal-pan wall/floor, pocket diameter/depth,
  seating clearance, adhesive allowance, pan recess, powder crown,
  powder-to-lid clearance.
- **Moulded construction**: tray draft 1.5°, pocket draft 2.0°, internal
  fillets, wall-to-floor radii, pocket floor thickness, exterior wall,
  structural ribs, hinge-zone and clasp-zone reinforcement.
- **Hinge**: five alternating knuckles (3 base / 2 lid) on one axis, each
  bored for a real continuous pin, plus pin end caps, knuckle gaps,
  rotational clearance and root reinforcement.
- **Clasp**: lid hook + engagement undercut lip + base detent + lead-in
  chamfer + release clearance + local flex zone + finger-opening notch
  (cut from the base shell).
- **Mirror stack**: mirror + adhesive pad + retaining border + recess
  depth + perimeter clearance + lid backing.
- Eleven states including `HINGE_ONLY`, `CLASP_ONLY`, `MIRROR_STACK`.

All figures are `DESIGN_DEFAULT` / `NOT_MANUFACTURER_CONFIRMED`.

## The blocker

`blender_scripts/palette_csg_views.py` resolves the CSG and cuts true
sections with a half-space Boolean. **It produced correct recessed pockets
once, then regressed to producing no cut, and I have not found the cause.**
Three hypotheses were tested and disproved: modifier application context,
mesh-data refresh timing, and import-selection scrambling. I am not going
to claim a fix I have not verified.

**Recommended next step (deterministic, no Blender dependency):** build the
recessed tray in Python instead. Sample every cell boundary at a fixed
uniform count so adjacent cells share identical vertices, connect boundary
samples to pocket-circle samples as a quad strip, then weld. That yields a
watertight deck-with-recesses that is testable without a renderer, which
suits this repo's determinism rules better than a render-time Boolean.

## Not done

No M4B evidence renders · no true sections · no 3.5 vs 5.0 mm comparison
fixture · no M4B tests · no review board · no validation report · no
tracker update.

## Status kept

`PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED` ·
`PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED` ·
`PALT_P1_OWNER_APPROVAL: REJECTED_PENDING_M4B` · `PALT_M5: BLOCKED`.
