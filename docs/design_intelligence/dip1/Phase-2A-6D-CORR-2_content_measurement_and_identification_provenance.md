# Phase 2A-6D-CORR-2 — Content Measurement and Identification Provenance Repair

**Date:** 2026-07-21 · **Task:** #50 (Baked Powder) — NOT retried, NOT mutated
· **Commits:** `251e81d` (provenance), `9e356ff` (validator semantics),
`552500f` (observability), this document.

## Why

The authorized retry of task #50 (run on `c8294ab`) produced a direction set
human review found substantially compliant — Editorial Soft Radiance /
Geometric Halo / Powder Drift — and validation rejected it with five codes.
Post-mortem attribution (payload preserved in AgentLog 806):

| Code | Verdict | Mechanism |
|---|---|---|
| `UNCONFIRMED_STRUCTURE_ASSUMED:design_intent` | genuine firing, upstream defect | `product_identification` **invented** "small upright rectangular tuck-end carton" ("tuck" appears nowhere in the brief) and the guess entered the generation context as fact |
| `DECORATIVE_COVERAGE_EXCEEDED:direction[1]` | validator defect | bounding extents ("30% of panel height and 45% of panel width" ≈ 13.5% area; declared ink coverage "under 18%") read as area claims |
| `PALETTE_SYSTEMS_NOT_DISTINCT` | validator defect | any-shared-hex rule fired on ivory `#FAF3EC`, which the brief REQUIRES in all three palettes |
| `EMOTIONAL_TONE_NOT_DISTINCT` | validator defect | "quietly" substring-matched the cue "quiet"; all three tones collapsed to SERENE |
| `DIRECTIONS_SUPERFICIALLY_VARIANT` | validator defect (cascade) | "materially **different from** … high-contrast serif" classified as serif ("different from" was not a contrast cue); "dot particles (**circles** …)" classified GEOMETRIC_ABSTRACT by table order |

## §1 Structural provenance (`251e81d`)

`resolve_product_profile` structure now carries provenance:
`EXPLICIT_USER_FACT` · `VERIFIED_PRODUCT_RECORD` · `INFERRED_NONAUTHORITATIVE`
· `UNKNOWN`. Only the first two populate `physical_format`; an inferred form
is quarantined in `inferred_non_authoritative_context` (diagnostic only) and
never rendered by `profile_text` — the block the Creative Director, Prompt
Engineer, QA reviewer and image producer all consume. An inferred form counts
as EXPLICIT_USER_FACT only when every structural assertion in it (closure
terms, dimensions) appears verbatim in the user's own task text.

For task #50 the context now resolves exactly as mandated:

```
Carton structure: width UNKNOWN, depth UNKNOWN, height UNKNOWN,
template UNKNOWN, panel sequence UNKNOWN, closure system UNKNOWN —
structural confirmation required. STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED: …
```

The deterministic parsing boundary (`normalize_identified_profile`) is
unit-tested with the exact task-#50 identification payload: the assembled
generation message carries the required copy (BBROSE / BAKED POWDER /
POLVO HORNEADO / LUMINOSIDAD SUAVE), pastel permissions, prohibited dominant
colors, the 20 % cap, prohibited motifs and finishes — and contains no
tuck-end, no auto-lock, no dimensions.

## §2–§6 Measurement semantics (`9e356ff`)

* **Coverage** — percentages classify as AREA claims, BOUNDING EXTENTS or
  UNKNOWN; paired height×width extents derive a rectangular upper bound
  (30 % × 45 % = 13.5 % passes a 20 % cap); a lone extent is never an area,
  except equal-extent shapes (a "circle at 70 % of panel width" stays a 49 %
  violation — Relief Strata remains rejected); a structured
  `decorative_coverage_pct` field takes precedence; malformed or contradicted
  declarations fail closed. `coverage_findings()` records value + source
  (`STRUCTURED_DECLARATION` / `EXPLICIT_AREA_LANGUAGE` /
  `DERIVED_BOUNDING_EXTENTS` / `UNKNOWN`) per direction.
* **Palette** — role-aware comparison over chromatic anchors with
  `SHARED_NEUTRAL_ALLOWED`; a brief-required shared neutral never collapses
  systems; a shared dominant chromatic primary, identical chromatic systems,
  or identical full hex palettes still fail; neutral-only palettes with one
  identical ground still fail.
* **Tone** — evidence-scored, whole-token classification ("quietly" ≠
  "quiet"); phrase cues outrank single words; ties break deterministically
  by table order; genuinely identical tones still collapse.
* **Contrast** — `different from`, `differs from`, `different than`,
  `contrasted with`, `in contrast to` join the negation-span cues; span
  truncation keeps affirmative content before the cue.
* **Motif** — scored specific-beats-generic classification;
  `GEOMETRIC_HALO` is its own family; generic shapes remain
  `GEOMETRIC_ABSTRACT`; precedence no longer depends on table order.

## §7 Observability (`552500f`)

A failed generation now captures the complete bounded result: design intent
AND directions of every attempt (initial vs repair distinguishable), the
validator's input brief, classification matrix, content codes, structured
coverage findings, schema versions, code revision and the structural-
provenance state. Bounded to intent + directions — no credentials, provider
transport or worker state (pinned by test). Supports deterministic offline
revalidation with zero provider calls.

## §8 Offline revalidation of AgentLog 806 (no model call)

Before (as rejected on `c8294ab`): 5 codes. After (corrected validators):

* signature failures: **none** (warning: `UNCLASSIFIED_HIERARCHY_FAMILY`);
  content codes: **none**; originality: **none**.
* Matrix: Editorial Soft Radiance `ASYMMETRIC_SPLIT / CONDENSED_EDITORIAL_SANS
  / NEUTRAL_METALLIC / PARTICLE_FLOW / REFINED`; Geometric Halo
  `CENTERED_FOCAL / MIXED_SERIF_SANS / NEUTRAL_METALLIC / GEOMETRIC_HALO /
  SERENE`; Powder Drift `ASYMMETRIC_SPLIT / GEOMETRIC_ROUNDED_SANS /
  NEUTRAL_METALLIC / PARTICLE_FLOW / FRESH`.
* Pairwise distances 5 / 3 / 5 — every pair ≥ the floor of 3.
* Coverage: d0 area 10 %, d1 area 18 % + derived 13.5 %, d2 area 20 % — all
  within the 20 % cap, sources recorded.

The 806 intent was never captured (the §7 gap) and its structural context
was contaminated by the tuck-end inference, so the old Design Intent is not
accepted or reconstructed; a clean future retry regenerates it from the
corrected, structure-safe context.

## State (unchanged by this correction)

Task #49 `failed`, preserved. Task #50 `failed`; one CreativeBrief; 0 active
directions; `selected_direction_id` empty; corrective specification intact in
`gate_1_notes` (5,749 chars); archives intact (AgentLog 780 originals, 792
first replacement, 806 latest); Prompt Engineer calls 0; GeneratedImages 0;
ApiCallRecord 181 before and after this correction (zero provider calls);
DecisionEvents 3 (Phase-1 quarantined chain, untouched); operational
permission projections 0.

## Verification

515 pipeline tests green (36 new: 12 provenance, 32 semantics/replay across
two files, 5 observability; 5 legacy pins updated to the corrected
contract); ruff clean; no migration drift; system check: only the expected
`dielines.pipeline.W001` ICC warning.
