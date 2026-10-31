# Phase 2A-9 — Customer-Grade STE Archetype (`ecma_a20_20_01_01_ste_carton/0.1`)

Status: **OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL** ·
Blocker: **PHYSICAL_SAMPLE_VALIDATION_REQUIRED** ·
Gate 2: blocked by construction (`production_ready=False`).

## What this is

An internal, versioned straight-tuck-end archetype whose closed-form
geometry is adapted — with attribution, see `THIRD_PARTY_NOTICES.md` and
`apps.dielines.geometry.ecma_ste.FORMULA_PROVENANCE` — from the
MIT-licensed `DDR68/Rhino_Packaging_Toolkit` ECMA A20.20.01.01 generator
(commit `e062327c0f309a0bb3a374fb9a210713d97a13ca`). It replaces nothing:
the historical generic STE 1.0/1.1 definitions are untouched, and any
registered customer- or manufacturer-supplied vector dieline outranks this
archetype automatically (template selection returns unresolved with
`CUSTOMER_DIELINE_IMPORT_REQUIRED`).

The Pacdora screenshot is a **visual closure reference only** — it is not a
production vector, it is not customer-supplied structural authority, and it
is never traced or embedded into any output.

## Structural authority for task #50 (known facts)

inner 90 × 32 × 92 mm · board 0.5 mm · panel sequence
glue | 90 main | 32 side | 90 main | 32 side.
The old 90 × 25 × 92 structure is permanently invalidated for the task
(banned geometry hash; confirmation refuses it).

## Dimension model (all assumptions reported per die)

| Set | Values at task-50 inputs | Meaning |
|---|---|---|
| inner | 90 × 32 × 92 | supplied; the archetype's input convention |
| external (drawn) | 91 × 33 × 93 | inner + 2t (adapted source convention) |
| manufacture (reported) | 91 × 33 × 93 | score-to-score reference set for reconciliation (inner = manufacture − 2t) |
| outer (reported) | 92 × 34 × 94 | manufacture + 2t (engine convention) |

Pacdora's published numbers (mfg ≈ 90.6 × 32.6 × 93.1, outer ≈ 91 × 33 × 94)
follow a different allowance convention; deltas are ≤ 0.6 mm. **Only the
physical sample or a supplied manufacturer die resolves the convention** —
that is exactly what PHYSICAL_SAMPLE_VALIDATION_REQUIRED gates.

## §4 Pacdora visual comparison (bounded classifications)

Classifications: MATCHES_VISIBLE_REFERENCE (feature visibly identical in
kind and placement) · CLOSE_PROVISIONAL_MATCH (same feature, provisional
proportions) · ESTIMATED_FROM_REFERENCE (parameter chosen to match the
look; value not measurable from a screenshot) ·
NOT_DETERMINABLE_FROM_SCREENSHOT. **No row claims exact customer parity —
screenshot pixels cannot establish coordinates.**

| Feature | Archetype | Classification |
|---|---|---|
| Panel sequence glue \| main \| side \| main \| side | identical | MATCHES_VISIBLE_REFERENCE (also a stated customer fact) |
| Top major-flap position (hinges from a main panel) | back panel carries the top tuck | MATCHES_VISIBLE_REFERENCE |
| Bottom major-flap position (same panel column as top — straight tuck) | back panel carries the bottom tuck | MATCHES_VISIBLE_REFERENCE |
| Rounded major-flap corners | quadratic-Bézier shoulders into a flat tip | CLOSE_PROVISIONAL_MATCH — curve family matches; radii not measurable |
| Curved shoulder proportions | control factor k = 0.635 (adapted source default) | ESTIMATED_FROM_REFERENCE |
| Dust-flap depth | (P + hook − t)/2 = 25.25 mm | ESTIMATED_FROM_REFERENCE |
| Dust-flap taper | 45° chamfer + 2 mm taper | CLOSE_PROVISIONAL_MATCH — shape family matches; angles not measurable |
| Slit and notch placement | 7 × 2.5 mm entry slits at both tuck-fold ends, 2t lock ears | CLOSE_PROVISIONAL_MATCH — placement matches; lengths not measurable |
| Glue-flap shape | chamfered, crease shortened by t, tapered transitions | NOT_DETERMINABLE_FROM_SCREENSHOT (glue flap largely hidden) |
| Closure orientation (both tucks open the same way) | straight-tuck orientation | MATCHES_VISIBLE_REFERENCE |
| Bleed contour | full cut-contour offset, 3 mm | NOT_DETERMINABLE_FROM_SCREENSHOT (Pacdora preview crops bleed) |

## Physical validation (§7)

`apps/dielines/services/physical_validation.py` — bounded outcomes
(FIT_PASS, FIT_TOO_TIGHT, FIT_TOO_LOOSE, DEPTH_INCORRECT, HEIGHT_INCORRECT,
DUST_FLAP_COLLISION, MAJOR_TUCK_ENTRY_FAILURE, LOCKING_SLIT_FAILURE,
GLUE_FLAP_INTERFERENCE, BOARD_COMPENSATION_FAILURE, PANEL_NOT_SQUARE,
OTHER_MEASURED_CORRECTION_REQUIRED), measured corrections in mm.
FIT_PASS requires `sample_printed_at_100pct=True` — a screenshot review can
never be recorded as a physical result. Only FIT_PASS (for the exact
geometry hash) clears `promotion_blockers()`; publishing a confirmed
version stays a separate human, code-reviewed step.

## Future supplier dieline (§9)

`register_customer_dieline(..., source_type=SOURCE_SUPPLIER)` registers a
manufacturer die as `CUSTOMER_OR_MANUFACTURER_SUPPLIED_DIELINE` with the
same top authority; `archetype_difference_report()` preserves the
comparison. Historical provisional outputs are never rewritten; artwork
remaps only after the supplied die is confirmed.

## Attribution (§10)

MIT notice preserved in `THIRD_PARTY_NOTICES.md`, in the geometry module
header, and in `FORMULA_PROVENANCE` (persisted into every preview parameter
table). No endorsement by DDR68/Rhino_Packaging_Toolkit is implied; no
unrelated source files were imported.
