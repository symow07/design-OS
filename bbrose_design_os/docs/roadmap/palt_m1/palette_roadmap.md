# PALT-M1 — PALETTE SYSTEM FOUNDATION

**Status: FOUNDATION MILESTONE DELIVERED FOR OWNER REVIEW.**
Architecture, research and contracts only. No production modelling, no
Blender implementation, no image generation.

## Objective

Design the architecture for BBROSE palette products — eyeshadow, pressed-
powder compacts, blush, contour, highlighter, mixed face, baked, refillable
and custom BBROSE structures — as a first-class Design OS program, not a
minor bottle archetype.

## Scope

In: taxonomy, architecture decision, outer-case geometry contract, pan-
layout engine, mechanical system, powder material engine (as a consumer of
GME-M1), artwork/shade system outline, three pilot specifications, an
online reference library with provenance, measurement ranges, risks, and
the roadmap/tracker updates.

Out (deliberately): any modelling, rendering, image generation, or claim of
manufacturing authority.

## Dependencies

- **GME-M1** (generalized material & colour engine) — palettes consume it;
  powder finishes are material specifications.
- Shared engine layers proven by P1: geometry authority record, mesh
  diagnostics, pinned Blender runtime, unlit-alpha mask authority, neutral
  clay vs material modes, versioned evidence packaging, strict owner review.
- **P1 remains frozen** as an engine-validation reference and regression
  fixture.

## Implementation phases

| Phase | Content | Gate |
|---|---|---|
| **PALT-M1** | foundation: taxonomy, architecture, contracts, research, pilots (this milestone) | owner review of the architecture decision |
| **PALT-M2** | implement `palette_geometry/1.0` + `pan_layout/1.0`, fail-closed validation, deterministic identities | tests green; no renders yet |
| **PALT-M3** | mechanism contract + articulated OPEN state + collision checks | both states render in clay |
| **PALT-M4** | powder material engine via GME-M1 + finish-differentiation board | owner accepts finishes side by side |
| **PALT-M5** | PALT-P1 pilot evidence package | strict owner visual review |
| **PALT-M6** | artwork + shade system + .AI export + PNG preview | artwork authority review |
| **PALT-M7** | PALT-P2 and PALT-P3 pilots | strict owner visual review |

## Deliverables (this milestone)

`generalized_material_engine_roadmap.md` ·
`generalized_material_contract_proposal.json` ·
`palette_online_reference_library.json` · `palette_measurement_ranges.json` ·
`palette_taxonomy.md` · `palette_architecture_decision.md` ·
`palette_geometry_contract_proposal.md` ·
`palette_pan_layout_engine_proposal.md` ·
`palette_mechanical_system_proposal.md` ·
`palette_powder_material_engine_proposal.md` ·
`palette_first_three_pilots.md` · `palette_risks_and_unknowns.md` ·
`palette_roadmap.md` · `palette_roadmap_tracker.json`

## Tests (defined here, implemented in PALT-M2+)

layout overlap / out-of-bounds / minimum-gap / case-fit · derived-height
consistency · wall-below-minimum · pocket generated from layout (single
source) · OPEN state is a transform, not a second mesh · mechanism
collision · refill-compatibility · material change preserves mesh identity ·
finish differentiation is measurable · existing P1 fixtures unchanged.

## Owner gates

G1 architecture decision · G2 pilot dimension confirmation · G3 finish
acceptance · G4 pilot visual acceptance · G5 artwork acceptance.
**No self-approval at any gate.**

## Failure conditions

Any palette shipped without both states; any layout authored as free
coordinates; any palette-local shader bypassing GME-M1; any DESIGN_DEFAULT
presented as manufacturable; any mechanism resembling a claimed patent
without legal review; any regression in the P1 fixtures.

## Authority limitations

`PALETTE_GEOMETRY_AUTHORITY: PROVISIONAL_DESIGN_ONLY` ·
`MANUFACTURING_AUTHORITY: NOT_ESTABLISHED` ·
`MATERIAL_AUTHORITY: VISUALIZATION_PARAMETERS_ONLY` ·
`REFERENCE_AUTHORITY: SUPPLIER/RETAILER/PATENT ANALOGUES ONLY — no
manufacturer technical drawing was obtainable`.

## Estimated complexity

Higher than the Product Container target: two articulated states, a module
lattice, mechanisms, nine powder finishes and four artwork surfaces.
PALT-M2–M4 are the substantial build; PALT-M5–M7 are pilots and artwork.

## Critical path

architecture decision → `pan_layout/1.0` → `palette_geometry/1.0` →
mechanism/OPEN state → powder finishes (GME-M1) → PALT-P1 evidence →
artwork/.AI → P2/P3.

## Exit criteria for PALT-M1

Architecture documented ✓ · reference library usable ✓ · ranges provenance-
tagged ✓ · taxonomy complete ✓ · pan-layout contract defined ✓ ·
mechanical contract defined ✓ · powder system defined ✓ · three pilots
specified ✓ · roadmap and tracker updated ✓ · **owner review requested** ✓
