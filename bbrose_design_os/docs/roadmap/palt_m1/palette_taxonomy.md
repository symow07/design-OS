# Palette Taxonomy (PALT-M1 §A)

**Status: PROPOSAL.** A palette is classified by eleven independent axes.
Independence matters: any real product is a *combination*, so the engine
must never hard-code a bundle (e.g. "9-pan = square + mirror + hinge").

## The eleven axes

| # | Axis | Values |
|---|---|---|
| 1 | **Outer shape** | RECTANGLE · SQUARE · CIRCLE · OVAL · ROUNDED_RECTANGLE · POLYGON · CUSTOM_SILHOUETTE |
| 2 | **Case material** | ABS · AS/SAN · PP · PS · ACRYLIC · ALUMINIUM/TINPLATE · PAPERBOARD · PCR · BAMBOO · HYBRID |
| 3 | **Pan count** | 1 · 2–4 · 5–9 · 10–15 · 16+ · VARIABLE (refillable) |
| 4 | **Pan shape** | ROUND · SQUARE · RECTANGULAR · HEXAGONAL · TEARDROP · CUSTOM |
| 5 | **Pan size uniformity** | EQUAL · MIXED |
| 6 | **Layout** | GRID · CIRCULAR · RADIAL · IRREGULAR · ZONED (eye/face groups) · MODULAR |
| 7 | **Mirror** | NONE · LID_FULL · LID_PARTIAL · SEPARATE_PANEL |
| 8 | **Hinge** | NONE (lift-off lid) · PIN_HINGE · SNAP_HINGE · LIVING_HINGE · EXTERNAL_BARREL |
| 9 | **Clasp** | NONE (friction) · MECHANICAL_DETENT · MAGNETIC · SLIDING_LOCK |
| 10 | **Applicator space** | NONE · BRUSH_SLOT · PUFF_COMPARTMENT · UNDER_TRAY_DRAWER |
| 11 | **Pan retention** | FIXED (glued/moulded) · MAGNETIC_REFILL · REMOVABLE_TRAY · DRAWER |

Plus a structural axis: **SINGLE_LEVEL · MULTI_LEVEL (stacked/layered) ·
SLIDING · ROTATING · FOLDING**.

## Why this shape of taxonomy

The single most useful principle found in research (R15) is that mixed
palettes work by **module equivalence** — a blush pan consumes roughly
three eyeshadow modules, a cream two, a brow powder one. That means axes
3/4/5/6 collapse into one representable idea: *a module grid with
multi-module occupancy*. Layout is therefore never free coordinates; it is
occupancy on a declared module lattice, which is checkable (no overlap, no
out-of-bounds, spacing respected).

## Classification of the three pilots

| Pilot | 1 | 3 | 5 | 6 | 7 | 8 | 9 | 11 |
|---|---|---|---|---|---|---|---|---|
| PALT-P1 standard eyeshadow | ROUNDED_RECTANGLE | 9 | EQUAL | GRID | LID_FULL | PIN_HINGE | MECHANICAL_DETENT | FIXED |
| PALT-P2 mixed face | RECTANGLE | 12–15 | MIXED | ZONED | LID_FULL | PIN_HINGE | MAGNETIC | FIXED |
| PALT-P3 experimental BBROSE | CUSTOM_SILHOUETTE | VARIABLE | MIXED | MODULAR | TBD | TBD | MAGNETIC | MAGNETIC_REFILL |

## Rules

1. **No implied bundles.** Selecting SQUARE must not auto-select GRID.
2. **Fail-closed on unknown values**, exactly as `container_geometry/1.0`
   refuses unknown cross-section families.
3. **Open/closed is a state, not a type.** Every hinged palette has both;
   evidence packages must show both.
4. **Refillability is a retention axis**, not a product category — a
   refillable palette is not "a different product", it is axis 11.
