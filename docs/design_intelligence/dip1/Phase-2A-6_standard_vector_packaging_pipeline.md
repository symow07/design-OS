# Phase 2A-6 — Standard Parametric Dieline and Native-Vector Production Pipeline

Makes the corrected task-#47 path the **standard, target-aware packaging
workflow** instead of a one-off correction. Everything below ships behind
`STANDARD_VECTOR_PACKAGING_PIPELINE` (**default False**) — no legacy cutover,
no historical task rewritten.

Commits: `5a6aacd` registry / selection / structure gate · `8d379d2` its
panel-order fix · `f0f62ba` native-vector standard mode · `e675a4e` print
data + generalized validators · `dd9c795` pipeline integration · this
document.

## 1. What the standard path did wrong (the review)

The pre-2A-6 flow defaulted rather than decided. Findings, all now closed:

| Where | Defect |
|---|---|
| `dieline_agent.TEMPLATE_TYPE`, `aria._build_dieline_spec`, `views.ConfirmDimensionsView` | `straight_tuck_end_carton` hard-coded in three places; no template ever selected |
| the same | glue\|main\|side\|main\|side assumed; a supplied die could not change it |
| `Product.packaging_structure` | an existing carton association was never consulted |
| `aria.resume_after_dimensions` → `flat_artwork.make_flat_artwork` | the Gate-1 render was re-rendered by an image model and **printed** as panel background |
| `artwork_layers.artwork_targets` | that raster was cover-cropped onto every panel and flap |
| `aria.resume_after_dimensions` metadata | `product_name` fell back to `task_text[:60]` — the brief printed as the product name |
| `panel_info` | any string passed through, including "To be confirmed" |
| everywhere | no vector reconstruction existed for packaging artwork |

## 2. Template registry (`apps/dielines/registry.py`)

One canonical, versioned declaration per template: id, version, panel
sequence **with the engine's own panel names**, dimension semantics, closure
type, glue-seam position, required parameters + permitted ranges, board
compensation model, flap/notch capabilities, collision validator, bleed and
safe-area behavior.

Registered: `straight_tuck_end_carton/1.0`, `reverse_tuck_end_carton/1.0`,
`tuck_top_auto_bottom_carton/1.0` (generic) and
`skynte_foundation_tuck_carton/1.0` (side-seam archetype).

Unknown ids raise `UnknownTemplate`; a pinned version must match exactly.
Two tests keep the registry honest: it must equal the engine dispatch set,
and **every** declared panel order must equal the panels the engine actually
draws. That second test caught a real bug during the build — front/back were
swapped for all three generic templates.

**Structural compatibility is never inferred from W/D/H.** Dimensions only
constrain a chosen template (`fits_dimensions`).

### Generic-template cut/fold defect — CORRECTED (see CORR-1 below)

The cut/fold check found that the three legacy generic templates scored
creases along edges that are actually **cut**. Repaired in Phase 2A-6-CORR-1
(`DECISION-021`): corrected geometry ships as **v1.1**; the defective **v1.0**
stays registered for historical reproduction and is refused for production.

## 3. Selection priority (`services/template_selection.py`)

1. `EXPLICIT_USER_CONFIRMATION` · 2. `PRODUCT_TEMPLATE_ASSOCIATION` ·
3. `SUPPLIED_STRUCTURAL_PROFILE` · 4. `TARGET_STRATEGY_RECOMMENDATION`
(≥ 0.7 only) · 5. human confirmation · 6. `GENERIC_FALLBACK_ACCEPTED`.

A generic template is unreachable without explicit acceptance, and **any**
structural evidence outranks acceptance. An unregistered or unbuildable
choice returns `STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED` — never a
substituted structure.

## 4. Persistence

`DielineJob.structure_selection` (one additive JSONField; `sqlmigrate` = one
`ADD COLUMN`, plus a no-op choices alter for the new task status) holds
template id/version, parameters, source, confidence, reasons, assumptions,
geometry hash, confirmation stamp and the reconciliation. A restart reloads
it **verbatim** and never re-selects; a changed template/version/parameter
breaks the geometry hash and hard-stops.

## 5. Structure-confirmation gate

`awaiting_structure_confirmation` + `POST /api/tasks/<id>/confirm_structure/`
(Reviewer-only, idempotent per die, refuses a stale hash). The dashboard
panel shows the panel map and sequence, dimensions, closure, flap and
notch inventory, compensation assumptions, the per-axis reconciliation and
collision results. **No GateDecision, no permission** — it confirms the die,
not a design. Artwork composition asserts confirmation first.

## 6–8. Native-vector artwork

`NATIVE_VECTOR_RECONSTRUCTION` is the only production mode; the Gate-1
render is `TEMPORARY_VISUAL_REFERENCE_ONLY` and informs colour, flow,
density, hierarchy, motif and finish intent through the selected direction's
vocabulary — it never reaches the page.

**Design languages** (`apps/ire/design_language.py`), all built from the
bounded primitive set (base fills, gradients, ribbons, flowing lines,
contour streams, geometric fields, line patterns, abstract motifs, panel and
finish masks, live typography): `liquid_veil`, `contour_terrain`,
`strata_field`, `ruled_field`, `petal_scatter`, `quiet_ground`. Editable
parameters: swatches (CMYK-bearing), stroke widths, density, scale, opacity,
control jitter, per-panel emphasis, finish, continuation, seed.

Below the keyword floor, `VECTOR_RECONSTRUCTION_REVIEW_REQUIRED` stops the
task. There is no tracing path and no raster fallback.

**Panel roles**: front 1.0 · back 0.0 (quiet, for regulatory readability) ·
sides 0.55 · top/bottom flaps 0.35 · dust 0.25 · glue 0.15. Each surface
generates from its own seed, so no panel is another panel's artwork tiled.

## 9–10. Printed-data contract

A **whitelist** of product-facing fields (brand, product line, type,
description, INCI, directions, warnings, net content, shade, SKU, barcode,
QR, batch, manufacturer, marketer, importer, country of origin). Unknown and
internal keys are dropped, so task titles, briefs, prompts and agent
rationale have no path into artwork.

States: `VERIFIED` · `UNVERIFIED` · `MISSING` · `PLACEHOLDER` ·
`NOT_APPLICABLE`, with **distinct** codes: `REQUIRED_PRINT_FIELD_MISSING`,
`PLACEHOLDER_PRINT_CONTENT`, `UNVERIFIED_REQUIRED_PRINT_FIELD`,
`INTERNAL_TEXT_IN_PRINT_DATA`, `EXAMPLE_IDENTIFIER_IN_PRINT_DATA`,
`REQUIRED_LEGAL_ROLE_MISSING`. Preview artwork may show marked placeholders;
production never does.

## 11. Production validator (`validators/production.py`)

Four families, every failure categorized and coded, **no override**:

- **structural** — `STRUCTURE_NOT_CONFIRMED` (incl. post-confirmation drift),
  `TEMPLATE_MISMATCH`, `PANEL_SEQUENCE_MISMATCH`, `MISSING_CLOSURE_GEOMETRY`,
  `DIMENSIONS_UNRECONCILED`, `CLOSURE_COLLISION`, `INVALID_SLIT_OR_NOTCH`,
  `INCOMPLETE_BLEED`, `CUT_FOLD_CONFLICT`,
  `OPEN_OR_SELF_INTERSECTING_CONTOUR`, `STRUCTURE_CHECKLIST_MISSING`
- **artwork** — `PANEL_SIZED_RASTER`, `PRINTABLE_CONCEPT_RENDER`,
  `FLATTENED_PANEL_GRAPHICS`, `INSUFFICIENT_EDITABLE_VECTOR_COVERAGE`,
  `DUPLICATED_PANEL_TEXTURE`, `REFERENCE_ONLY_IMAGE_PRINTABLE`,
  `ARTWORK_INVENTORY_MISSING`
- **content** — the print-data codes, `FORBIDDEN_PANEL_TEXT`,
  `TEXT_BELOW_MINIMUM_SIZE`
- **colour/output** — `RGB_PRODUCTION_ARTWORK`, `INVALID_SPOT_DEFINITION`,
  `MISSING_OUTPUT_INTENT`, `INVALID_FONT_EMBEDDING`,
  `PRODUCTION_PDF_MISSING`

`PRODUCTION_NOT_READY` is only the transport-level error carrying the list.

**OutputIntent**: the documented reportlab gap is now closable —
`exporters/output_intent.py` embeds the print shop's CMYK ICC profile as a
PDF/X OutputIntent when `PRODUCTION_ICC_PROFILE_PATH` is set, refuses a
non-CMYK profile, and never guesses one. **Open action: supply the shop's
CMYK profile, or Gate 2 correctly reports `MISSING_OUTPUT_INTENT`.**

## 12. Editability report

Shipped with every evaluation: vector/raster counts, raster area + fraction,
decorative-vector coverage, live vs outlined text, clipping masks,
gradients, swatches, spot colours, technical vs printing vs reference-only
layers, editable vs fixed elements.

## 13–14. Integration and legacy

Standard flow: Gate-1 concept → dimensions → template selection → clean
structure → **human structure confirmation** → native-vector artwork →
production validation → Gate 2. Task #47 is reproducible through it with no
task-specific script (14 integration tests).

With the flag off, the legacy path runs verbatim and writes no structural
record. Historical outputs stay as they are; an explicit regeneration runs
under current policy. Defective historical jobs are preserved.

## Brand logo fallback

`BRAND_LOGO_RASTER_FALLBACK` — `media/brand/logo.png`, 1439×300 px, RGBA,
~300 dpi tag / ~1450 effective dpi at its 25.2 × 5.25 mm front-panel
placement. Raster, non-editable, exempt from the decorative-raster rules as
the sole controlled fallback. **No approved canonical vector master exists.**
It is never auto-traced or redrawn.

## Exclusions

No DecisionEvent, permission or authority of any kind. No semantic search.
No image tracing. No legacy cutover, no historical rewrite. No invented INCI
(task #47 remains blocked on customer data). No changes to Phase 2A
direction selection, Gate 1, the container/complete-product targets, or the
locked STE reference geometry.
