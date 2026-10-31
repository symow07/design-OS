# Real Bottle Reference Standard — `real_bottle_reference_pack/1.0`

**Status: PROPOSED — 2026-08-04.** Governs what counts as an authoritative
real-bottle reference after the owner rejected abstract fixtures as
non-representative visual evidence.

## 1. Reference authority order (owner decision, recorded)

| # | Source | Authority |
|---|---|---|
| 1 | CAD_OR_TECHNICAL_DRAWING | HIGH_GEOMETRIC_AUTHORITY |
| 2 | CALIBRATED_REAL_PRODUCT_PHOTOGRAPHY | MEDIUM_TO_HIGH_VISUAL_AUTHORITY |
| 3 | GOVERNANCE_CLEARED_SUPPLIER_REFERENCE | LIMITED_TO_DOCUMENTED_SOURCE_AND_VIEW |
| 4 | AI_GENERATED_CONCEPT | DESIGN_INTENT_REFERENCE_ONLY |

Hard rules: AI-generated concepts are **never** real-bottle geometric
truth. No claim of exact physical accuracy exists without authoritative
CAD, technical drawings, or complete dimensional evidence. Hidden or
unavailable geometry is never fabricated — it is recorded as
`REAL_BOTTLE_REFERENCE_INCOMPLETE`.

## 2. The pack

A `real_bottle_reference_pack/1.0` record contains, with per-item presence
flags (missing ⇒ INCOMPLETE, never fabricated):

**Geometry authority** — manufacturer CAD or technical drawing; exact
overall height; body width; body depth; neck diameter; collar dimensions;
closure dimensions.

**Photographic evidence** — front orthographic; side orthographic; top;
three-quarter; closure close-up; neck/collar close-up. All on a neutral
background with a known scale or calibration object in at least one frame.

**Appearance authority** — material and finish reference; colour reference
(physical swatch, Pantone, or calibrated capture).

**Provenance** — source, ownership/licensing evidence (DIP rules binding —
possession is not permission), declared authority level per item, and a
**known-uncertainty** statement.

## 3. Calibration requirements for photography

- camera distance ≥ 8× product height for near-orthographic front/side
  views (perspective error < ~1%) or a documented telecentric/ortho note;
- scale object (ruler/calibration card) in-plane with the product;
- lens distortion noted or corrected; no beauty retouching of geometry;
- file provenance recorded (device, original resolution, no AI upscaling).

## 4. Governance

References enter the repository through the existing secure reference
core (B4b validation), are hash-recorded, and become
`REAL_BOTTLE_GOLDEN_REFERENCES` only after explicit owner acceptance.
Repository materials with `ownership UNKNOWN / licence UNVERIFIED` are
unusable until the owner confirms ownership — filenames and folders prove
nothing.
