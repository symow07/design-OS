# Phase 2B-2 §1 — Current Raster Reconstruction Path Audit

Audited before any change. Existing outputs are preserved for audit; nothing
in the legacy path is deleted.

## Path traced

`ARIA.resume_after_container_profile` → `reconstruct_container`
([apps/pipeline/targets/container/__init__.py](../../apps/pipeline/targets/container/__init__.py))
→ `build_backbone` ([silhouettes.py](../../apps/pipeline/targets/container/silhouettes.py))
+ `compose_container_graph` ([apps/ire/compose_container.py](../../apps/ire/compose_container.py))
→ `emit_pdf_ai` → `pdf_to_png`. Colour via `dominant_color_hex`; interim label
via `make_flat_artwork` ([flat_artwork.py](../../apps/pipeline/services/flat_artwork.py)).

## Where the selected concept is lost — classified defects

| Code | Where | Finding |
|---|---|---|
| `SELECTED_CONTAINER_VARIATION_NOT_LOADED` | `reconstruct_container` | The approved `GeneratedImage` FK is loaded **only** for `image_file.path`; its variation identity (direction/variation/prompt) is never verified or persisted, and its structured variation record (`gate1_reference_regeneration_prompts/1.0` — composition/color/motif signatures, logo/name zones, coverage) is never consulted. `load_selected_variation` exists and is used by the **packaging** target only. |
| `CONTAINER_RASTER_LABEL_FALLBACK_USED` | `reconstruct_container` → `make_flat_artwork(variant="background")` → `compose_container_graph(label_path=…)` | A provider (`openai.images.edit`) re-renders a raster "background" and it is placed as a raster `Image` node clipped to `backbone.label_zone`. The decoration IS a raster. This is also a **provider call inside reconstruction**. |
| `CONTAINER_DESIGN_GRAPH_NOT_CREATED` | `compose_container_graph` | A shared Design-Graph `Document` **is** produced, but it is a concept **sheet** (reference \| container \| spec regions) with raster label/logo escape hatches — not a native container graph whose artwork objects belong to confirmed decoration zones. No `container_design_graph/1.0`. |
| `CONTAINER_DECORATION_ZONES_NOT_CONSUMED` | `compose_container_graph` | Artwork is clipped to the heuristic `backbone.label_zone` (derived in `silhouettes.py`), **not** the confirmed `container_decoration_zones/1.0` from 2B-1. Zones, techniques, margins and coverage are ignored. |
| `CONTAINER_SURFACE_PROJECTION_NOT_APPLIED` | `compose_container_graph` | The label is a flat rectangle clip. No curvature projection (cylindrical arc, tapered trapezoid, seam) — a wrap prints as if flat. |
| `CONTAINER_SELECTED_CONCEPT_FIDELITY_UNMEASURED` | whole path | Only the **border colour** of the concept survives (`dominant_color_hex`); cap colour is a constant. Logo/name position/scale, motif family/density, colour-area proportions, front/back relationship, wrap continuation, whitespace — none are derived from the concept or measured against the emitted artwork. |

Additional observations (not defects, but constraints for the rebuild):
- Front/back orientation is not modelled — one label region only.
- The official logo is a raster `Image` node at the `logo` anchor (a legitimate
  controlled fallback when no vector master exists — reported, not decoration).
- `product_name` **is** already native live text at its anchor (the one part
  that survives natively today).

## §18 — Migration decision: **ZERO MIGRATIONS**

Consistent with 2B-1 (Option A). No new DB columns or models.

- **Selected-variation identity** uses the existing `PackagingOutput.approved_image`
  FK + `GeneratedImage.reference_provenance` (`variation_identity`) +
  `Gate1RegenerationJob.prompts_payload`. A resolved, verified identity block is
  persisted as an additive `spec_sheet` key.
- **`container_selected_concept_visual_graph/1.0`**, **`container_design_graph/1.0`**,
  the reconstruction report, fidelity report, zone-containment report and
  native-output manifest are all additive `spec_sheet` JSON keys.
- **Native views** (front / back / cap / wrap) are regions in **one**
  Design-Graph `Document` emitted to the existing `design_preview_ai`
  (`.ai`) + `design_preview` (`.png`) file fields — the proven
  `compose_container` one-sheet-regions pattern. No new file fields.
- **§16 legacy regeneration**: before overwriting a legacy task's native
  output, snapshot the prior native-output manifest into a `spec_sheet` key —
  no field added.

Zero migrations; the 2B-1 schema semantics are unchanged (§19 stop condition
not triggered).

## Reuse (frozen-architecture discipline — extend, never replace)

- `apps/pipeline/services/selected_concept.py` — `load_selected_variation`
  (verified, fail-closed) + `reconstruction_spec`; target-agnostic, reused.
- `apps/ire/graph.py` — all §4 primitives (live text, Bézier, fills, gradients,
  clips, named groups/swatches) already exist; `container_design_graph/1.0` is a
  metadata tag + persisted JSON over the shared `Document`.
- `apps/ire/compose_container.py` — **extended** to consume zones + visual graph
  + projection; not replaced.
- `apps/ire/concept_fidelity.py` / `geometry_report.py` — the packaging
  fidelity/measurement pattern is mirrored for container surfaces (three-state:
  `MEASURED_PASS` / `MEASURED_FAIL` / `UNMEASURED`).

## Fidelity is three-state (no-provider consequence)

Deterministic derivation (§14 golden hashes) rules out vision extraction, so
semantic-element positions (logo, product-name, motif centroid) come from
**structured variation data** or are `INFERRED`/low-confidence; colour-area
proportions, whitespace and density come from **local PIL/numpy**. Fidelity is
therefore `MEASURED_PASS` / `MEASURED_FAIL` / `UNMEASURED`
(`CONTAINER_SELECTED_CONCEPT_FIDELITY_UNMEASURED`) — "element exists" is never a
pass, and "target unknown" is never an auto-pass.
