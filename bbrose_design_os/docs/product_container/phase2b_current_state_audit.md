# Phase 2B — Product Container — Current-State Audit (repository-grounded)

Date: 2026-07-23. Read-only audit of the live code; no provider calls.
Sources: apps/pipeline/targets/container/{__init__,silhouettes}.py,
apps/ire/compose_container.py, apps/pipeline/services/flat_artwork.py,
apps/pipeline/models.py, apps/pipeline/review_board.py.

## The flow as it exists today

brief → Design Intent → 3 directions → direction selection → 3 Gate-1
concepts → selected concept → **awaiting_container_profile** gate →
`reconstruct_container` → Review Board (review_sections only) → Gate 2.

`ProductContainerTarget.begin_output` infers a `ContainerProfile` and pauses
at `awaiting_container_profile` (mirrors packaging's dimension gate).
`reconstruct_container` builds an editable container sheet
(compose_container_graph → pdf_ai) onto the shared PackagingOutput file
fields (design_preview_ai / design_preview). Container state lives entirely
in `PackagingOutput.spec_sheet` (JSON); containers do NOT use a DielineJob.

## Stage-by-stage gaps (against the §1 checklist)

| Concern | State | Evidence |
|---|---|---|
| legacy / task-specific routing | OK-ish | `begin_output` uses the generic target flow; profile gate exists |
| loses selected variation identity | **GAP** | reconstruct reads `approved_image` for COLOUR only (`dominant_color_hex`); no variation-prompt-vs-image verification (packaging's selected_concept has it) |
| raster artwork as final decoration | **GAP** | label is `make_flat_artwork(...)` — a RASTER extraction from the concept; the reference photo is also placed raster |
| substitutes generic container graphics | **GAP** | without an API key the label extraction is skipped → best-effort/blank; no explicit stop |
| does not persist confirmed profile data | **PARTIAL** | `container_profile` persisted as `asdict(profile)`, but the schema is minimal and unversioned (no hash, no confirmation source/timestamp, no UNKNOWN policy) |
| lacks fidelity validation | **GAP** | no SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED; no emitted-geometry fidelity gate |
| lacks material-reference influence | **GAP** | no material_influence_realization for containers |
| lacks production-readiness validation | **GAP** | no container Gate-2 (no decoration-zone / technique / profile blockers) |
| lacks native named-layer Illustrator handoff | **GAP** | packaging has illustrator_handoff_graph/1.0; container has none |

## Current ContainerProfile (silhouettes.py) vs the §2 contract

Present: archetype, variant, aspect_ratio, neck_ratio, cap_style,
label_zone (Rect), decoration_zone (Rect).

Missing (to add in 2B-1, all as JSON): explicit body dimensions, shoulder
geometry, cap dimensions, body/cap material, body/cap colour,
transparency/opacity, decoration method, a structured decoration-ZONE model
(§3, not a single Rect), label zones, front/back orientation, manufacturer
constraints (persisted UNKNOWN, never inferred as verified),
confirmation source, confirmation timestamp, profile hash + schema version.

## Decoration zones (§3) — not yet modelled

Today there is a single optional `decoration_zone: Rect`. The §3 model
(FRONT_PRINT_ZONE, WRAP_LABEL_ZONE, CAP_PRINT_ZONE, …) with per-zone
dimensions/position/curvature/safe-margin/technique/max-coverage/source/
verification does not exist. No production print area is known ⇒ the flow
must return CONTAINER_DECORATION_ZONE_CONFIRMATION_REQUIRED; print areas
must never be guessed from a photograph.

## Reuse (do NOT rebuild — mandate preserves these)

Bottle/jar/tube archetypes + silhouette backbone (silhouettes.py); the
awaiting_container_profile gate; variant/cap selection + proportion factors;
reference uploads (`_uploaded_paths`); Review Board `review_sections`;
editable container sheet (compose_container_graph); PNG + AI downloads
(PackagingOutput file fields); TargetStrategy integration
(ProductContainerTarget).

## Proposed migrations for 2B-1

**Schema/profile + decoration-zone model are JSON in
`PackagingOutput.spec_sheet` — no new DB columns.** The versioned
`container_profile/1.0` record (with hash, confirmation source/timestamp,
UNKNOWN manufacturer constraints) and the `container_decoration_zones/1.0`
model are JSON keys, exactly as packaging's `structure_selection` /
`provisional_preview` are.

Migration required: **one** `DesignTask.status` choices `AlterField`, only
if 2B-1 adds a distinct decoration-zone/structure confirmation gate status.

- OPTION A (minimal, recommended for 2B-1): reuse the existing
  `awaiting_container_profile` gate to carry both profile and
  decoration-zone confirmation (the refusal code
  CONTAINER_DECORATION_ZONE_CONFIRMATION_REQUIRED is returned there).
  **Zero migrations.**
- OPTION B (explicit two-step, mirrors packaging dimensions→structure):
  add `awaiting_container_decoration_zones` to `TASK_STATUS`, producing
  one AlterField migration, e.g.:

      # apps/pipeline/migrations/00XX_container_zone_gate.py
      migrations.AlterField(
          model_name="designtask",
          name="status",
          field=models.CharField(max_length=50, default="queued",
              choices=[... existing ...,
                       ("awaiting_container_decoration_zones",
                        "Awaiting Container Decoration Zones")]),
      )

  (Choices-only change; no column/DDL change. `status` is already
  max_length=50 — no width change needed.)

Recommendation: **Option A for 2B-1** (zero migrations); revisit a separate
zone-gate status in 2B-2 if the fidelity flow needs it. Either way, 2B-1
adds no new model, no new column, and touches no packaging table.

## Non-regression guardrails for 2B

Preserve task #47 and task #50 golden fixtures and all packaging behavior;
no rewrite of completed container tasks; no silent conversion of old
outputs; no provider calls in implementation or regression tests
(synthetic / already-persisted concept data only).
