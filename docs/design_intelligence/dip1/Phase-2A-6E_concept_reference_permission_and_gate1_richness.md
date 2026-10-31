# Phase 2A-6E — Concept-Reference Permission and Gate-1 Visual Richness

**Date:** 2026-07-21 · **Task:** #50 at `awaiting_gate_1` (selected direction
d1 "Editorial Soft Radiance") · **Commits:** `12207fb` (permission +
candidates), `c3d9f99` (plumbing + diversity gate + provenance), this
document + UI. **No provider call occurred during this correction.**

## §1 Gate-1 audit (from persisted data)

Path: selection (04:56:44) → identification (call 184, quarantine WORKED:
"inferred form, non-authoritative — excluded from generation context") →
Prompt Engineer ×1 (call 185, `image_prompts`, variation mode) → gpt-image-2
×3 (calls 186–188, $0.25 each, images 84–86) → QA ×3 (calls 189–191, scores
9/8/9). Total $0.86, ~4.5 min.

Findings, from calls and logs — not assumption:

1. **Did the provider see material-library images?** NO. It received 4
   rasterized past-production DesignReference files + the official logo
   (log 825) via `images.edit`. The DIP/materials library reaches no part of
   the render path, and **which** four files shipped was never persisted.
2. **Text only?** DIP context exists only at PLANNING: log 812 shows
   channels HISTORICAL_DESIGN=0, DESIGN_ASSET_METADATA=0,
   BRAND_OR_PALETTE_CANDIDATE=22 → 2 text-only entries to the Creative
   Director. The Prompt Engineer received no material context of any kind.
3. **Excluded for missing permission?** Structurally yes: DIP references are
   `DESCRIPTIVE_REFERENCE_ONLY` by mandate and no concept-reference
   permission existed, so no mechanism could pass a material visually.
4. **Did the PE convert material context into visual instructions?** There
   was no material context input to convert. It faithfully rendered the
   selected direction — whose own spec caps decoration at <10% with exactly
   one hairline + micro dots — three times.
5. **Why three near-identical variations?** The variation clause instructs
   "one design executed three ways… vary ONLY bounded execution dimensions",
   the direction is intentionally ultra-minimal, no visual vocabulary was
   available to differentiate, and QA scores each render alone (9/8/9) —
   nothing measured the SET.

## §2 Root causes (with evidence)

| Cause | Verdict | Evidence |
|---|---|---|
| `MATERIAL_CONTEXT_NOT_RETRIEVED` | CONFIRMED | render path has no material retrieval; planning channels returned 0 historical designs, 0 asset metadata (log 812) |
| `MATERIAL_CONTEXT_TEXT_ONLY` | CONFIRMED | the only DIP influence anywhere is 2 text entries at planning |
| `NO_VISUAL_REFERENCES_PASSED` | CONFIRMED for the material library (house production rasters did pass, unrecorded) |
| `MATERIAL_PERMISSION_NOT_AVAILABLE` | CONFIRMED | no concept-reference permission concept existed |
| `PROMPT_ENGINEER_DROPPED_MATERIAL_CONTEXT` | NOT CONFIRMED | nothing reached it to drop |
| `VARIATION_PROMPTS_NOT_DISTINCT` | CONFIRMED | prompts 84–86 share one system (ivory field, stacked name, one rule + dots, same logo/copy zones) |
| `SELECTED_DIRECTION_OVER_CONSTRAINED` | CONFIRMED | d1 spec: one hairline + 8–12 micro dots, coverage <10%, prohibition list |
| `IMAGE_PROVIDER_IGNORED_REFERENCE_CONTEXT` | NOT SUPPORTED | renders match their prompts; QA notes confirm house craft |

## What shipped

* **§3 Permission** — `ConceptReference` with
  `USER_APPROVED_FOR_CONCEPT_REFERENCE`: task-scoped, human-only (machine
  code never approves), `production_use_allowed` structurally False;
  ownership/rights states carried verbatim (`UNKNOWN`/`UNVERIFIED` for
  library items, lineage-unconfirmed for house references).
* **§4 Selection screen** — bounded deterministic retrieval (≤6 house
  references + ≤4 DIP-inventory decorative rasters, keyword-scored, never
  padded with irrelevant items), thumbnails streamed read-only and bounded
  to the declared root, 2–4 explicit user approvals, nothing auto-selected,
  nothing sent to a provider before approval.
* **§5 Influence plan** — `material_influence_plan/1.0`: per-reference
  permitted analysis + palette/typography/composition/motif/texture/
  finishing principles + copy prohibitions + similarity-risk note;
  locator-free by assertion; hashed.
* **§6–§7 Richness + variations** — `GATE1_RICHNESS_DIRECTIVES` reinterprets
  Editorial Soft Radiance with 15–20% controlled decorative coverage and
  mandates variations A (editorial panel) / B (layered type field) /
  C (powder constellation); a deterministic diversity gate (logo zone, name
  zone, scored motif, color-field devices; every pair ≥2 differences) runs
  BEFORE any image spend, with one bounded repair then fail-closed.
* **§8 Provenance** — every generated image persists
  `reference_provenance`: approved concept IDs whose file actually shipped,
  every visual file passed, influence-plan hash, variation identity,
  provider model. Built strictly from the opened path list — a missing file
  is neither passed nor claimed. The Review Board renders MATERIAL
  REFERENCES USED per image (or states that none reached the provider).
* **§9 Preservation** — images 84–86 labeled
  `REJECTED_BY_USER — INSUFFICIENT_VISUAL_RICHNESS`, rows and files kept.
* **Regeneration** — `regenerate_gate1_with_references` (Reviewer-gated API
  + Celery): same selected direction, Creative Director never rerun,
  refusals `REGEN_NOT_AT_GATE1` / `REGEN_NO_APPROVED_REFERENCES` /
  `REGEN_NO_INFLUENCE_PLAN`. **Not executed** — it waits for the user's
  reference selection.

## Stop state

Task #50 remains at `awaiting_gate_1` with d1 selected; 10 candidates are
persisted and visible on the Gate-1 screen; nothing is approved; no image
was regenerated; ApiCallRecord unchanged (191) throughout the correction.
