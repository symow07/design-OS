# Phase 2B-2A — Native Motif Reconstruction & Multi-Surface Emission

Closes the two 2B-2 scope boundaries: the native reconstruction now renders
the selected concept's motif and emits artwork for every confirmed
decoration-bearing surface. Zero migrations (additive `spec_sheet` keys +
`container_design_graph/1.1`). No provider calls in reconstruction or tests.

## Policy (as directed)

1. Recognized unsupported motifs stay **FAIL-CLOSED** — a concept that visibly
   carries a motif never completes with the motif absent.
2. Font confirmation / licence gating is **deferred to 2B-3** (the emitted face
   is reported honestly; not gated here).
3. Native emission covers **all confirmed artwork-bearing surfaces** — front
   only is not a completion state.

## Motif contract (§1/§2) — `container_motif_spec/1.0`

Authored from the SELECTED variation (never the brief/direction prose alone)
and bound to the existing closed, deterministic, no-raster/no-trace engine
(`apps/ire/design_language.py`). The 12 mandate families collapse onto the
supported recipes and the collapse is **recorded**, not hidden:
`requested_family` (classified from the signature) vs `rendered_via` (the
actual `DesignLanguage`), with `rendered_via_is_approximate` where the nearest
generator is not a literal match (BOTANICAL_LINE_ART / FLORAL_ABSTRACT →
`petal_scatter`; RADIANCE_LINES → `contour_terrain`; MICRO_PATTERN →
`ruled_field`).

Capability: `SUPPORTED` (renders), `REVIEW_REQUIRED` (fails closed with
`VECTOR_RECONSTRUCTION_REVIEW_REQUIRED` — distinct from
`CONTAINER_NATIVE_RECONSTRUCTION_FAILED`), `NONE` (no motif in the concept).

Supported families → generators: POWDER_CONSTELLATION/PARTICLE_FLOW →
`powder_constellation`; CONTOUR_STREAMS/RADIANCE_LINES → `contour_terrain`;
RIBBON_FLOW → `liquid_veil`; SOFT_PETALS/FLORAL_ABSTRACT/BOTANICAL_LINE_ART →
`petal_scatter`; GEOMETRIC_ABSTRACT → `strata_field`;
EDITORIAL_RULE_SYSTEM/MICRO_PATTERN → `ruled_field`; TONAL_COLOR_FIELD →
`quiet_ground`. All emit only Bézier paths / circles / ellipses / stars /
strokes / fills / gradients / clipped groups — never raster, tracing, or
copied reference artwork.

### Floral / botanical safety (§3)

Botanical concepts render as abstract petal constructions (`petal_scatter`),
recorded as an approximation — never a traced or copied unique flower. A motif
that cannot be responsibly rebuilt fails closed rather than being simplified
into an unrelated generic motif.

## Multi-surface emission (§5-§8)

The confirmed front zone carries the hero motif + live name. Every other
confirmed surface gets a native panel by role:

- **back** → readable-info role (quiet ground, INFO/INCI/CODE placeholder, no
  motif); `container_front_back_relationship/1.0` records distinct hero vs
  readable roles and fails (`CONTAINER_FRONT_BACK_RELATIONSHIP_FAILED`) if they
  collapse.
- **cap** → independent mark, never stretched body artwork.
- **wrap / sides** → reduced motif continuation + a seam marker.
- **crimp / neck / shoulder / bottom** → a bounded CODE area only, never
  decoration.

## Motif fidelity (§4) — measures geometry, not the label

`container_motif_fidelity` measures the ACTUAL emitted motif nodes against the
spec: the expected node type for the chosen language must be present, so a
SUPPORTED motif that rendered nothing → `MOTIF_MISSING`, wrong family emitted →
`MOTIF_FAMILY_MISMATCH`, right geometry → `MEASURED_PASS`. Noisy INFERRED-local
targets (centroid / density / coverage / continuation) are `UNMEASURED`, never
gated against a pixel estimate. A `MEASURED_FAIL` blocks (non-global,
fail-closed at the reconstruction gate).

## Design Graph (§9) — `container_design_graph/1.1`

Additive over /1.0: per-surface artwork groups, surface inventory, motif groups
+ family, and the front/back relationship. 1.0 records are not reinterpreted.

## Outputs (§10) & Review Board (§14)

`container_native_output_manifest/1.0` lists the views (front hero + surface
panels, concept-sheet .ai, preview .png) and reports, splits
`surfaces_with_artwork` from `technical_only_surfaces`, and preserves the
legacy raster output. `review_sections` surfaces motif reconstruction status,
motif fidelity, and the surface classification.

## Golden fixtures (§13)

`container_native_golden.json` carries, per archetype, a first-pass census
(zero decorative rasters, multi-surface groups) **and** a recognized-motif
variant — bottle→powder_constellation, jar→strata_field (with BODY_WRAP
continuation), tube→liquid_veil — each verifying family preserved, motif
groups emitted, zero decorative rasters, containment clean, live text kept,
fidelity MEASURED_PASS, and deterministic reproducibility.

## Known bounds (honest — not over-claimed)

- **Font confirmation is not implemented** (deferred to 2B-3, per policy #2);
  the emitted default face is reported, not gated.
- **Front/back (§6):** the concept's front/back INTENT is vision-only and stays
  UNMEASURED. What IS gated is the EMITTED role collapse — `measure_front_back`
  fails (`CONTAINER_FRONT_BACK_RELATIONSHIP_FAILED`) if a hero motif lands on
  the back surface or the front carries no hero content (exercised by tests).
  Given the emitter never collapses roles by construction, this passes on
  normal output; it is a real guard against a future/edge emission, not a
  validation of concept intent.
- **Emitted-but-not-yet-gated codes:** cap orientation
  (`CONTAINER_CAP_ORIENTATION_FAILED`), cap/body coordination
  (`CONTAINER_CAP_BODY_COORDINATION_FAILED`), wrap alignment
  (`CONTAINER_WRAP_ALIGNMENT_FAILED`) and motif colour
  (`CONTAINER_MOTIF_COLOR_RELATIONSHIP_FAILED`) are defined and the artwork is
  emitted, but these axes are not yet measured (consistent with "measure
  geometry, leave vision/noisy signals UNMEASURED").
- Motif fidelity gates on presence + family (geometry-based); quantitative
  density/coverage/centroid vs INFERRED-local targets are UNMEASURED.
- Multi-surface artwork is emitted as labeled panels on one concept sheet
  (the proven one-sheet-regions layout), not yet a 3D-accurate wrap.
