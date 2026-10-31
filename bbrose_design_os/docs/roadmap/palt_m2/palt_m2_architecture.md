# PALT-M2 — Palette Contract and Parametric Layout Kernel

**Status: IMPLEMENTED, PENDING OWNER REVIEW.** Deterministic and
non-rendering: no Blender, no powder materials, no image generation, no
Illustrator export, no client presentation.

## What was built

| Module | Role |
|---|---|
| `services/palette_contracts.py` | versioned specs; every dimension carries value, unit, provenance, confidence, authority, tolerance |
| `services/palette_layout_kernel.py` | two deterministic layout modes + derived closed height + minimum feasible case |
| `services/palette_layout_validators.py` | 12 fail-closed violation codes; never repairs |
| `services/palt_p1.py` | the first pilot contract + its feasibility answer |

## Coordinate system (fixed once)

Origin at the tray's inner front-left corner; **+x right, +y toward the
rear (hinge side), +z up**; millimetres throughout. Pan placements are
bounding-box front-left corners. The hinge therefore occupies the high-y
band and the clasp the low-y band, which makes every collision check
unambiguous.

## Contract schemas

`PaletteSpec` composes `PaletteCaseSpec`, `PaletteTraySpec`,
`PaletteLidSpec`, `PaletteLayoutSpec`, `PaletteMirrorSpec`,
`PaletteHingeSpec`, `PaletteClaspSpec`,
`PaletteApplicatorCompartmentSpec` and `PalettePanSpec`.

Case shapes: RECTANGLE · ROUNDED_RECTANGLE · SQUARE · CIRCLE · OVAL ·
POLYGON · CUSTOM_SILHOUETTE (≥8 outline points required — a custom shape
exists only when evidence exists).
Pan shapes: CIRCLE · SQUARE · ROUNDED_RECTANGLE · RECTANGLE · OVAL ·
CUSTOM_SILHOUETTE.

**`Dim` makes provenance structural**: a bare float cannot enter a spec.
Unknown provenance, confidence or authority raises `PaletteContractError`;
negative and non-numeric values are refused.

`PaletteSpec.identity()` is a deterministic sha256 of the whole
specification — a *contract* identity, distinct from a mesh identity.

## Layout kernel — two modes

**A. `MODULE_LATTICE`** — structured, reflowable. Occupancy `(pan_id, row,
col, w_modules, h_modules)` on a lattice of explicit millimetres. Per the
owner's PALT-M1 correction, module equivalence is a
`CALCULATED_LAYOUT_HEURISTIC`, never a standard, and **every module
resolves to explicit dimensions** — the module is the *pocket* module
(nominal pan + 2 × manufacturing tolerance), enforced by
`MODULE_SMALLER_THAN_PAN_FOOTPRINT`.

**B. `ABSOLUTE_DIMENSIONAL_LAYOUT`** — irregular/custom arrangements by
explicit coordinates, validated by exactly the same rules.

Occupancy accounts for pan width, height, area, depth, inter-pan gap, tray
wall thickness, removal clearance and manufacturing tolerance. The padded
footprint (nominal + 2 × tolerance + 2 × removal clearance when
refillable) is the extent all collision checks use.

## Derived closed height

```
closed = base + tray_floor + deepest_pan + lid_inner_clearance
       + mirror (if present) + lid
```

Height is **derived, never authored**, so a proposed case height is
arithmetically refutable (`INSUFFICIENT_CASE_THICKNESS`).

## Validation codes (all fail-closed, all test-covered)

`PAN_OVERLAP` · `CASE_BOUNDARY_VIOLATION` · `INSUFFICIENT_OUTER_MARGIN` ·
`INSUFFICIENT_INTER_PAN_GAP` · `HINGE_ZONE_COLLISION` ·
`CLASP_ZONE_COLLISION` · `MIRROR_COLLISION` ·
`APPLICATOR_ZONE_COLLISION` · `IMPOSSIBLE_PAN_DEPTH` ·
`INSUFFICIENT_CASE_THICKNESS` · `INVALID_REFILL_REMOVAL_CLEARANCE` ·
`WALL_BELOW_MINIMUM` · `MODULE_SMALLER_THAN_PAN_FOOTPRINT`

**The kernel never shrinks pans, gaps or margins to make an invalid layout
pass.** `minimum_feasible_case()` reports what *would* work; it never
mutates the spec.

## Authority

`PALETTE_GEOMETRY_AUTHORITY: PROVISIONAL_DESIGN_ONLY` ·
`MANUFACTURING_AUTHORITY: NOT_ESTABLISHED` ·
`MATERIAL_AUTHORITY: NOT_EXPRESSIBLE_IN_THIS_CONTRACT` (materials belong
to GME-M1) · `MODULE_EQUIVALENCE_AUTHORITY: CALCULATED_LAYOUT_HEURISTIC`.
