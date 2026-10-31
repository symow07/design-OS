# Phase 2B-2 — Native Container Reconstruction & Fidelity Gate

Replaces the raster-label reconstruction path with a native, editable
reconstruction driven by the selected Gate-1 variation, the confirmed
`container_profile/1.0`, the confirmed `container_decoration_zones/1.0`, the
selected-concept visual relationships, and explicit container-surface
projection. Zero database migrations (Option A). No provider calls in
reconstruction or in tests.

## The record chain (all additive `spec_sheet` keys)

| Key | Slice | What it is |
|---|---|---|
| `container_selected_variation/1.0` | 1 | verified identity of the EXACT approved image (fail closed) |
| `container_selected_concept_visual_graph/1.0` | 1 | deterministic, no-provider visual relationships (3-tier source) |
| `container_design_graph/1.0` | 2 | census over the emitted native Document (primitives + decorative-raster count) |
| `container_projection_report` | 3 | per-zone curvature projection (method + distortion) |
| `container_zone_containment_report` | 3 | every placement contained? + §6 problems |
| `container_fidelity_report` | 4 | three-state per-axis measurement of emitted vs concept |
| `container_reconstruction` | 4 | `RECONSTRUCTED` / `BLOCKED` + blocker codes |

## Selected-variation identity (§2)

`container_visual_graph.resolve_selected_variation_identity` reuses the
target-agnostic `selected_concept` service to load and **verify** the approved
image against the persisted image/prompt record. It fails closed with
`SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED` when the approved image is
missing/unpersisted or a regenerated image's structured record cannot be
matched — the broader direction or first concept is never substituted. A
first-pass concept (no regeneration) is a verified identity with
`structured_record_present=false`.

## Visual graph — three honest tiers (§3), no provider

Vision extraction is forbidden (§14 golden hashes require reproducibility), so
every field carries `value / confidence / source / verification` from:

* `SELECTED_VARIATION_RECORD` — prompt-verified structured variation → VERIFIED
* `SELECTED_VARIATION_PROMPT` — verbatim, deterministic prompt extraction
* `LOCAL_IMAGE_ANALYSIS` — PIL/numpy palette, whitespace, density → INFERRED

What genuinely needs vision (exact logo/name boxes, front/back relationship,
wrap continuation) stays `MISSING` — it becomes an `UNMEASURED` fidelity axis,
never invented.

## Native reconstruction (§4/§5) — supported primitives

Native, editable: live text, Bézier paths, rectangles, solid/tinted fills,
named groups, clipping masks, colour swatches. The confirmed zones drive a
native `Decoration` group (tinted field + keyline + live product name). The
raster label (`make_flat_artwork`, a provider call) is gone: **decorative
raster count is 0**. The selected render is `TEMPORARY_VISUAL_REFERENCE_ONLY`
(its own labelled group); the official logo is the one permitted controlled
raster fallback, counted separately.

## Projection classes (§7)

`FLAT` 1:1 · `CYLINDRICAL` flat-width→arc-length + wrap radius + reported
foreshortening · `TAPERED_CYLINDRICAL` trapezoid + distortion · `OVAL`
front/back only (full wrap → review) · `RECTANGULAR_WITH_ROUNDED_CORNERS` flat
centre + corner inset · `CUSTOM_PROFILE` / `UNKNOWN` fail closed with
`CONTAINER_SURFACE_PROJECTION_REVIEW_REQUIRED`. Distortion is reported, never
silently compensated.

## Zone containment (§6)

Every emitted placement must belong to a confirmed zone and sit within it:
bounds, safe margin, max coverage, surface assignment, decoration-excluded
surfaces (neck/shoulder/crimp), wrap seam, cap/body family. Codes:
`CONTAINER_DECORATION_OUTSIDE_ZONE`, `CONTAINER_ZONE_SAFE_MARGIN_VIOLATION`,
`CONTAINER_ARTWORK_SURFACE_MISMATCH`, `CONTAINER_WRAP_SEAM_CONFLICT`,
`CONTAINER_CAP_BODY_ZONE_CONFLICT`, `CONTAINER_DECORATION_COVERAGE_EXCEEDED`.
Nothing is resized to pass.

## Fidelity — three states (§10)

Per axis: `MEASURED_PASS` (target known + satisfied), `MEASURED_FAIL` (target
known + violated, incl. a motif family the native field cannot yet reproduce),
`UNMEASURED` (target MISSING — surfaced, never an auto-pass). "Element exists"
is not a pass. A `MEASURED_FAIL` → `SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED`.

## Failure semantics (§13)

On any blocker (projection review, out-of-zone placement, or a MEASURED_FAIL)
reconstruction persists all reports **then** fails closed with
`CONTAINER_NATIVE_RECONSTRUCTION_FAILED`: the task stays at the reconstruction
gate (`awaiting_container_profile`) with the report + identity + profile +
zones preserved. It is never globally failed and never reverts to the raster
fallback; an explicit retry re-runs after correction. On success the task is
reviewable at Gate 2 — no automatic approval.

## Review Board (§15)

`review_sections` surfaces the selected-variation identity, the identity
hashes (profile / zones / visual-graph / variation), the native census,
decorative-raster count, projection method, containment result, three-state
fidelity with failures, and reconstruction blockers — so the reviewer can tell
the original concept, the superseded legacy raster and the native
reconstruction apart.

## Golden fixtures (§14)

`tests/fixtures/container_native_golden.json` freezes bottle/jar/tube: zero
decorative rasters, live text present, all placements contained, deterministic
projection + hashes, three-state fidelity `MEASURED_PASS`. Reproducibility is
asserted (same inputs → identical census/projection/fidelity).

## Known bounds (honest scope — not overclaimed)

Front-view native reconstruction + the full contract/measurement chain are in
place. These are deliberately NOT yet delivered and are stated so approval is
informed:

1. **Motif families are not rendered (blocking, no in-phase recovery).** A
   concept that carries a recognised `motif_family` (incl. rose/floral/petal/
   botanical) → `CONTAINER_MOTIF_FAMILY_MISMATCH` → `MEASURED_FAIL` →
   `CONTAINER_NATIVE_RECONSTRUCTION_FAILED`, and re-confirming re-fails. So the
   native path completes end-to-end today only for concepts WITHOUT a
   recognised motif family (typically first-pass concepts). Failing closed is
   chosen over shipping a motif-less "generic" result (§5 forbids that) — but
   the FAIL-vs-UNMEASURED call is a policy lever the reviewer owns.
2. **§9 font confirmation is NOT implemented.** The native product name emits
   the default face; `CONTAINER_FONT_CONFIRMATION_REQUIRED` is not raised. Font
   licence/confirmation remains a Gate-2 concern (a pre-existing open item),
   not a reconstruction axis yet.
3. **§8 emission is front-view only.** Back / cap / side / wrap surfaces get no
   artwork and are not in `zones_consumed`; multi-view emission is future work.
