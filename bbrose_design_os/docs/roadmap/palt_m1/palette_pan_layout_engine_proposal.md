# Pan-Layout Engine Proposal — `pan_layout/1.0` (PALT-M1 §C)

**Status: PROPOSAL. No implementation in this milestone.**

## OWNER CORRECTION 2026-08-05 (binding)

The blush ≈ 3 modules / cream ≈ 2 / brow = 1 relationships are recorded as
`MODULE_EQUIVALENCE_AUTHORITY: CALCULATED_LAYOUT_HEURISTIC` — **never** a
`MANUFACTURER_STANDARD`, `INDUSTRY_STANDARD` or `PRODUCTION_RULE`.
Every module must resolve to explicit dimensions, and the engine must
support **two** placement modes: `MODULE_LATTICE` *and*
`ABSOLUTE_DIMENSIONAL_LAYOUT`. Occupancy is a convenience for reflowable
layouts, not a physical law.

Layout occupancy must additionally account for pan width, pan height, pan
area, pan depth, inter-pan gap, tray wall thickness, removal clearance and
manufacturing tolerance.

## The organising idea: module occupancy as ONE mode

Research finding R15 (refill-system vendors) is the design key: mixed
palettes work because a large pan consumes an integer number of small-pan
**modules** — a blush ≈ 3 eyeshadow modules, a cream ≈ 2, a brow powder
= 1; a zone holds "4 small OR 1 large OR 1 medium + 2 small".

So the engine specifies a **module lattice** and each pan's **occupancy**
on it. Module occupancy makes structured layouts reflowable and checkable. It is
**not** the only mode: irregular and custom arrangements use
`ABSOLUTE_DIMENSIONAL_LAYOUT`, where each pan carries explicit coordinates
and dimensions and is validated by exactly the same rules.

```
pan_layout/1.0
├── lattice        { module_mm, gap_mm, origin, rows, cols }   (GRID)
│                  or { radius_mm, count, phase }              (CIRCULAR/RADIAL)
├── slots[]        { id, occupancy [w,h] in modules, pan_ref, zone }
├── zones[]        EYE | BLUSH | CONTOUR | HIGHLIGHT | BROW | MIXED
└── margins        { outer_mm, inter_pan_mm }
```

## Supported arrangements

- **rows and columns** — the base GRID lattice
- **circular / radial** — lattice defined by radius + count + phase angle
- **asymmetrical / irregular** — GRID lattice with sparse occupancy and
  deliberate empty modules (still validated, still re-flowable)
- **mixed pan sizes** — multi-module occupancy (a 36 mm pan on a 26 mm
  lattice occupies a 2×1 or 2×2 block depending on `module_mm`)
- **mixed pan shapes** — shape is a pan property, occupancy is a lattice
  property; they are independent
- **grouped face and eye zones** — `zone` tags drive grouping, artwork
  labels and shade-family logic
- **removable / magnetic pans** — a retention property per slot, so a
  single palette may mix fixed and refillable slots

## Derived, checkable quantities

```
lattice_pitch = module_mm + gap_mm
required_inner_width  = cols * pitch - gap + 2 * outer_margin
required_inner_length = rows * pitch - gap + 2 * outer_margin
```

Working ranges (all provenance-tagged in `palette_measurement_ranges.json`):
pitch from the worked 83 mm / 9-pan example ≈ 27.0–27.3 mm for 26 mm pans;
inter-pan gap 1.0–4.0 mm observed, **1.5 mm recommended minimum**
(DESIGN_DEFAULT — below that, moulded pocket walls approach the ABS
minimum wall and powder cross-contamination risk rises); outer margin
1.5–8.0 mm observed.

## Validation (fail-closed)

- `LAYOUT_OVERLAP` — two slots claim the same module
- `LAYOUT_OUT_OF_BOUNDS` — occupancy exceeds the lattice
- `LAYOUT_GAP_BELOW_MINIMUM` — computed gap < minimum
- `LAYOUT_EXCEEDS_CASE` — required inner size > case inner size
- `LAYOUT_PAN_DEPTH_EXCEEDS_TRAY`
- `LAYOUT_REFILL_INCOMPATIBLE` — a slot declared MAGNETIC_REFILL whose
  module size does not match a standard pan family (15/26/30/36/58.5)

The last one matters commercially: refill compatibility is a real customer
promise, and the engine should refuse to silently break it.

## Interfaces

Consumes: pan family dimensions, case inner dimensions.
Produces: pocket definitions for `palette_geometry/1.0`, label anchors for
the artwork system, and a per-slot shade mapping for the shade system.
