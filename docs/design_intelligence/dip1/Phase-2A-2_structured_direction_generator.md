# Phase 2A-2 — Structured Three-Direction Generator

`design_direction_generator/1.0` · prompt lineage `structured_director/2.0`

## The seam it fills

ARIA's `_generate_candidates` runs `CreativeDirectorAgent.run()` and pipes the three
directions straight into `PromptEngineerAgent` and image generation — the user first sees
the reasoning next to finished renders. 2A-2 makes the reasoning step a validated,
inspectable artifact; 2A-4 will insert the user's choice between the two.

## One canonical source of direction semantics

The Creative Director **is** the generator. Its system prompt was replaced — not
duplicated — by `DIRECTOR_SYSTEM` in `design_direction_generator.py`, which emits the full
`design_intent/1.0` document (intent + three rich directions) in **one model call**. The
legacy directions-only prompt no longer exists; `CREATIVE_DIRECTOR_SYSTEM` survives as an
alias for importers. The house rules carried over intact: subject-first, axis distinctness,
the fixed-logo rule, "logo centered on a colored box is banned", concise strings.

* `CreativeDirectorAgent.run_structured()` — the canonical path: assembles the existing
  brand context, product context, similar products, reference images and anatomy digests,
  then delegates the call/validate/repair loop to the generator. Returns a
  `GeneratorResult` (document + metadata).
* `CreativeDirectorAgent.run()` — the compatibility projection: `to_legacy_direction()`
  maps each rich direction onto the historical dict shape (name/rationale/palette/…/
  prompt_seed), so ARIA and PromptEngineer are untouched until 2A-4. Validation failure
  returns `[]`, exactly as before.

## Call and repair behavior

One generation call on the happy path. On validation failure, **exactly one** repair call:
it carries the reason codes, the invalid output, and "fix only the listed problems" — never
a new brief, never restated requirements. A second invalid output fails closed with the
codes; nothing proceeds to prompt engineering or image generation. Proven by tests counting
`FakeModel` calls: 1 on success, 2 maximum, never 3.

## Contract extension (pre-consumer)

`design_intent/1.0` was extended one slice after 2A-1, before any consumer existed:
intent gained `audience_interpretation`; the direction card grew to the full user-facing
set (`direction_id`, `subject_story`, `focal_hierarchy`, `imagery_approach`,
`material_finish_direction`, `emotional_tone`, `target_structural_guidance`, required
`prohibited_choices`), and the full `image_prompt` became a bounded `prompt_seed` —
PromptEngineer owns the canonical final prompt. Structural distinctness now emits
field-specific codes.

## Distinctness — two deterministic layers

**Structural (contract):** pairwise-distinct `direction_id`, `name`, `design_axis`,
`layout_structure`, `color_system` → `DUPLICATE_*` codes; `DIRECTION_COUNT_INVALID`.

**Semantic (`direction_signature.py`):** each direction reduces to a bounded signature —
axis · composition family · hierarchy family · typography family · color relationship ·
motif family · emotional tone — classified by deterministic keyword tables (no embeddings,
no second model). Reason codes:

`TYPOGRAPHY_NOT_DISTINCT` · `MOTIF_NOT_DISTINCT` · `HIERARCHY_NOT_DISTINCT` ·
`EMOTIONAL_TONE_NOT_DISTINCT` (a dimension where all three classified values collapse) ·
`DIRECTIONS_SUPERFICIALLY_VARIANT` (a pair differing in fewer than 3 classified dimensions
— the paraphrase floor — or three CENTERED_EMBLEM compositions, whatever the colors say).

Honesty rule: wording the tables don't recognize classifies `UNCLASSIFIED`, which produces
a bounded **warning**, never a pass and never a failure — a keyword table cannot fail
creative work for vocabulary it lacks, and cannot silently approve it either.

## TargetStrategy

`TARGET_GUIDANCE` names explicit structural guidance for **all eight** real `DesignTarget`
values; `assert_every_target_has_guidance()` plus the 2A-1 mirror test fail the moment a
target is added without a deliberate entry. The strategy's `concept_prompt_profile`
directive is passed through unchanged. **Deliberate behavior change:** the old B3 parity
("packaging → empty directive → byte-identical prompt") ended here — packaging now carries
its explicit guidance line like every other target, per the no-hard-coded-default rule; the
parity test was updated to pin the new rule.

## Originality boundary

Each direction must state `originality_notes` and at least one `prohibited_choices` entry
(contract-required). `originality_violations()` refuses copy instructions —
verb + target pairs ("replicate … historical", "copy … reference") and phrases
("identical to the", "pixel-for-pixel") — naming the offending direction:
`ORIGINALITY_VIOLATION:direction[i]`. Ordinary design language ("copy legibility",
"reproduction-grade print") does not trip it, by test. Reference context informs patterns;
it is never a template.

## User-input safety

Brief text is design content, not instructions: unknown brief fields are refused before any
model call, and a hostile brief demanding five directions still fails `DIRECTION_COUNT_INVALID`
because the requirement lives in the validator, not the prompt.

## Exclusions honored

No DIP query (2A-3 injects already-labelled summaries; a test captures zero DB queries
during generation), no image generation, no IRE/Design Graph, no DecisionEvent, no
permission, **no migration**. Output has no hidden-reasoning field — unknown fields are a
contract violation.

## Transition to 2A-3

The generator accepts `dip_context` as an injected list of labelled summaries and renders
them under "descriptive only … never an asset to reuse". 2A-3 builds the read-only lexical
adapter that produces that list; nothing in the generator changes.
