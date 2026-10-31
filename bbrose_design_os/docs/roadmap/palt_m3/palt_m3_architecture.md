# PALT-M3 — Case Stack-Up and Mechanism Strategy Engine

**Status: IMPLEMENTED, PENDING OWNER REVIEW.** Deterministic engineering
contracts. No powder rendering, no client presentation rendering, no
Blender, no image generation, no Illustrator export.

## Modules

| Module | Role |
|---|---|
| `services/palette_mechanism_contracts.py` | 5 hinge, 5 clasp and 5 retention strategies; envelope model; edge/orientation mapping |
| `services/palette_stackup_engine.py` | full height stack-up (3 separated values) + footprint stack-up + configuration evaluation |
| `services/palette_mechanism_validators.py` | strategy validation + the PALT-P1 matrix |

## The envelope model — the core idea

A mechanism strategy declares **where** its space is spent:

* `internal_band_mm` — reserved band inside the tray (steals pan field)
* `wall_add_mm` — extra thickness on the affected wall
* `external_add_mm` — material outside the footprint
* `height_add_mm` — contribution to closed height

PALT-M2 modelled only the first sink, which is why its "infeasible"
conclusion was too strong. Owner correction applied: 116 × 92 is
`INFEASIBLE_UNDER_CURRENT_RESERVED_BAND_STRATEGY`, and after this
milestone `INFEASIBLE_UNDER_ALL_TESTED_MECHANISM_STRATEGIES` — never
"infeasible under all possible strategies".

## Orientation is not bound to physics

The solver keeps a normalized local frame (hinge at +Y). The contract maps
it to `TOP_EDGE` / `BOTTOM_EDGE` / `LEFT_EDGE` / `RIGHT_EDGE`, and records
hinge edge, clasp edge, opening direction, case presentation orientation
and portrait/landscape usage. **Top/bottom edges consume depth;
left/right consume width** — so feasibility genuinely changes with edge
mapping, and the matrix tests both.

## Height stack-up (explicit, 18 components)

outer base skin · tray floor · pan depth · pan seating/adhesive · pan
proud/recess · powder crown · interior clearance above powder · lid inner
skin · lid outer skin · mirror thickness · mirror adhesive · mirror safety
clearance · hinge envelope · clasp closure clearance · retention height ·
cosmetic parting gap · manufacturing tolerance · warpage allowance ·
decoration/insert allowance (premium only).

Three values are produced and **never merged**:
`GEOMETRIC_LOWER_BOUND` < `ENGINEERING_MINIMUM` < `PREMIUM_DESIGN_TARGET`.
The lower bound carries a machine-readable warning that it is not a
production recommendation.

## Footprint stack-up

pocket module (full pocket **and retention** envelope — owner correction,
not merely nominal pan + tolerance) · pan tolerance · retention allowance ·
inter-pan gaps · internal tray walls · outer case walls · hinge envelope ·
clasp envelope · lid structural borders · assembly clearance · moulding
tolerance · corner-radius note.

## Fail-closed behaviour

`MECHANISM_MATERIAL_CONFLICT` (a PP living hinge on an ABS case) ·
`MECHANISM_ENVELOPE_UNDEFINED` (custom placeholders refuse to assume zero) ·
`TARGET_WIDTH_EXCEEDED` · `TARGET_DEPTH_EXCEEDED` ·
`TARGET_HEIGHT_BELOW_ENGINEERING_MINIMUM`.

Nothing auto-shrinks; the matrix never selects the smallest configuration.

## Authority

`MECHANISM_ENVELOPE_AUTHORITY: DESIGN_DEFAULT` — every envelope figure is
an engineering estimate because no manufacturer drawing was obtainable.
`MANUFACTURING_AUTHORITY: NOT_ESTABLISHED`. A strategy comparison narrows
the design space; it does not prove any strategy is manufacturable.
