# Phase 2A — Packaging Target — CLOSEOUT

Date: 2026-07-23. Classification:
**ROADMAP_IMPLEMENTATION_COMPLETE / PRODUCTION_AUTHORITY_PENDING_EXTERNAL_EVIDENCE.**
Packaging is architecturally complete end to end; it is NOT universally
production-approved — production authority waits on external evidence
(physical fit results, manufacturer dielines, printer ICC profile, font
licence evidence, verified regulatory/production data).

## What is complete

- **Brief → direction workflow.** design_intent/1.1; CreativeDirector emits
  exactly three axis-distinct directions; human selects one before any
  image generation (2A-1..2A-4).
- **Gate-1 generation.** Three concepts per selected direction; QA on the
  set; human approves one (task #50 = image #89 / direction d1).
- **Material-reference workflow.** ConceptReference (human-only,
  USER_APPROVED_FOR_CONCEPT_REFERENCE, production_use structurally false);
  candidate retrieval; material_influence_plan/1.0; influence realization
  mapped to emitted objects.
- **Selected-concept fidelity.** selected_concept loader verifies the
  variation prompt vs the approved image; concept_fidelity gate blocks a
  generic substitution before export (geometry + declarations).
- **Native-vector reconstruction.** compose_vector_art → pdf_ai emitter:
  editable paths, live text, editable gradients, vector barcode; the only
  flagged raster is the logo fallback; no decorative rasters.
- **Print-data integrity.** print-record snapshotting, forbidden-text
  checks, content validation, editability census.
- **Template registry.** One versioned source of truth (panel sequence,
  closure, seam, capabilities); fail-closed resolve(); geometry_hash
  identity; no fallback-by-similarity.
- **Structure confirmation.** Dimension gate → structural preview → human
  confirmation (geometry-hash-locked); artwork never composes on an
  unconfirmed/drifted die.
- **Qualified dieline archetypes.** reference_opposed_tuck_carton/0.1
  (task #50, opposing tucks); ecma_a20_20_01_01_ste_carton/0.1;
  straight_/reverse_tuck_end_carton 1.1 (legacy) and 1.2 (D-derived
  correction); skynte_foundation_tuck_carton/1.0 (task #47). Each has an
  independently derived supported domain, a seeded property sweep (0
  failures), a fixture matrix and a folded-closure diagnostic. Auto-bottom
  stays excluded (MEASURED_REFERENCE_REQUIRED).
- **Physical-validation authority.** Four independent states
  (TECHNICALLY_QUALIFIED_DOMAIN / PHYSICALLY_VALIDATED_INSTANCE /
  …DIMENSIONAL_FAMILY / PRODUCTION_AUTHORIZED_BY_MANUFACTURER); only the
  first is machine-grantable; Gate 2's physical blocker clears only on an
  exact-hash FIT_PASS. New-task selection recommends the corrected 1.2 and
  requires explicit version confirmation; 1.1 is legacy-reproduction only.
- **Named-layer Illustrator handoff.** illustrator_handoff_graph/1.0
  (15 root layers, panel sublayers, semantic groups, spot swatches, live
  typography); real-Illustrator execution adapter with a visual-parity
  gate; explicit-only (not the default output).

## Golden fixtures

- **task #47** — Skynte Foundation side-seam reconstruction, hash
  2be58c7bdb0afcc5728d700789c3e1e7 (frozen).
- **task #50** — reference_opposed_tuck_carton/0.1 at 90×32×92 / 0.5 mm,
  hash 0f5b8bf6bc2aa8ce0678fad3099da2d3; APPROVED_FOR_PHYSICAL_TEST, not
  yet PHYSICALLY_VALIDATED_INSTANCE. Next input: a FIT_PASS or a bounded
  failure code with measured corrections. Artwork not remapped; test PDF
  not regenerated; Gate 2 not approved.

## Remaining production blockers (external evidence)

- physical fit results (per geometry hash / dimensional family);
- manufacturer / customer supplied dielines (outrank all templates);
- printer CMYK ICC output profile (MISSING_OUTPUT_INTENT);
- font licence evidence (FONT_LICENSE_EVIDENCE_REQUIRED_FOR_PRODUCTION);
- verified regulatory and production data.

Gate 2 returns structured codes for each; there is no override.
