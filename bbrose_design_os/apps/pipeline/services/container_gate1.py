"""Container Gate-1 variation contract (Phase 2B-3V correction §4/§5/§6).

Task #51's initial Gate-1 render emitted generic variation_1/2/3 that converged
on typography, colour-field and cap/body, and forced the same references into
every prompt. This module defines the CONTAINER variation contract that the
reference-grounded prompt builder must satisfy before any image spend:

  container_gate1_variations/1.0

* exactly three NAMED identities (A_PETAL_WINDOW / B_LIQUID_VEIL /
  C_DEWDROP_CONSTELLATION) — generic variation_N fails;
  [§BH67(c)4, 2026-09-24: no identity is forced now. The three are SLOTS —
  A_<NAME>, B_<NAME>, C_<NAME> — each named by its own concept; the three
  July identities are house motifs a variation MAY take, never defaults.]
* every variation persists a typography / composition / motif / cap-body /
  decoration-zone / colour-field / finish signature, a native-reconstruction
  plan, and its OWN subset of approved reference ids;
* the diversity gate measures all seven axes pairwise BEFORE any image call.

It reuses the proven builder/validator in ``gate1_prompts`` — only the contract
knobs differ (extend, never rebuild).
"""
from __future__ import annotations

CONTAINER_GATE1_SCHEMA = "container_gate1_variations/1.0"

#: The three container variation identities §4/§5 MANDATED, 2026-07-24 (de61794) — until §BH67(c)4.
#: §BH67(c)4, OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "The July petal-window directive stops being
#: forced onto variation 1. A house instruction is not a design decision. All three variations come from the
#: directions; the directive may be offered as one option, never a default." These names are now the HOUSE MOTIFS a
#: variation may take where its direction calls for one; the records of tasks 51-91 carry them, and they still name
#: their slots (A_, B_, C_) validly. Nothing defaults to them.
CONTAINER_VARIATION_IDENTITIES = [
    "A_PETAL_WINDOW", "B_LIQUID_VEIL", "C_DEWDROP_CONSTELLATION"]

#: §BH67(c)4 — what the contract requires instead: three SLOTS, in order, each id the slot's letter and the variation's
#: OWN concept name in capitals and underscores (A_ORCHARD_HOUR). Never `variation_N`: `load_selected_variation` reads
#: that legacy form as "no structured record". A person's own identities for a project (2C-2C
#: `gate1_variation_spec.variation_identities`) are a person's decision, and are still enforced exactly.
CONTAINER_VARIATION_SLOTS = ("A", "B", "C")

#: Stable container Gate-1 codes (§5).
CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT = "CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT"
CONTAINER_VARIATION_IDENTITY_MISSING = "CONTAINER_VARIATION_IDENTITY_MISSING"
CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED = "CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED"

#: §4 — every variation persists these. ``reference_ids`` is per-variation (§6).
CONTAINER_REQUIRED_FIELDS = (
    "variation_id", "title", "prompt",
    "typography_signature", "composition_signature", "motif_signature",
    "cap_body_signature", "decoration_zone_signature", "color_field_signature",
    "finish_signature", "native_reconstruction_plan", "reference_ids",
)

#: CORR-2 §7 — the same contract WITHOUT per-variation reference_ids, used when
#: the task has no approved concept references (structured, ungrounded — never
#: a revert to generic unnamed variations).
CONTAINER_REQUIRED_FIELDS_NO_REFS = tuple(
    f for f in CONTAINER_REQUIRED_FIELDS if f != "reference_ids")

#: §5 — the seven diversity axes every pair must differ on.
CONTAINER_DIVERSITY_FIELDS = (
    "typography_signature", "composition_signature", "motif_signature",
    "cap_body_signature", "decoration_zone_signature", "color_field_signature",
    "finish_signature",
)

#: Every pair must differ on a strong majority of the seven axes.
CONTAINER_MIN_PAIRWISE_DIFFERENCES = 5

#: §5 — the three container variation briefs (native-vector reconstructable
#: decoration only; the physical product may be photorealistic, the applied
#: decoration must be reconstructable from live type / Bézier / gradients).
#: §BH67(c)4: the three variations are the SELECTED DIRECTION's, read three ways — the brief below no longer assigns
#: a motif, a palette or a hierarchy to a slot. The July directive's three house motifs are listed as OPTIONS a
#: variation may take where its direction calls for one, and never because they are listed.
CONTAINER_GATE1_DIRECTIVES = """
Reinterpret the selected direction across three MATERIALLY different container
concepts. All three come from the direction: each variation's motif,
composition, colour field and finish are the direction's own, read three
different ways. The physical container must retain the brief's measured shape,
closure and material. The production master uses live vector type, logo, layout
and finish masks; illustration and texture may remain high-resolution raster.
Do not infer production geometry from the beauty shot or require tracing.

NAME each variation from its own concept, in slot order: A_<NAME>, B_<NAME>,
C_<NAME> — capitals and underscores, for example A_ORCHARD_HOUR. Give the three
distinctly different logo and product-name placements, typographic
hierarchies, closure/body relationships, decoration-zone strategies, colour-field
structures and finish strategies.

HOUSE MOTIFS — OPTIONS, NEVER DEFAULTS. The house has drawn motif families
before — petal windows, nectar veils, dewdrop constellations, roses, arches.
None is taken unless the brief asks for it (his goal for the pitch,
2026-10-15): every design finds its own subject, and no variation draws a
rose, rose petals or an arch, or enlarges the logo's rose into a motif, unless
the brief asks for one.

COMPOSITION. Give each direction a clear focal point, intentional type scale,
palette roles and quiet zones. Pattern supports the name and may be absent.
Restraint, clear glass and cool chrome are valid. The brief's colours override
house defaults; monochrome still needs contrast. Do not add texture, multiple
colour planes or all-over pattern merely to make a design look busy.

Each variation's seven signature fields must honestly describe THAT prompt, and
its reference_ids must name only the approved references whose influence it
actually uses: a reference may serve more than one variation, but no variation
should carry the whole set.
"""

CONTAINER_SYSTEM = f"""
You are the Prompt Engineer for BBROSE, a luxury beauty brand, building the
REFERENCE-GROUNDED Gate-1 variation set for a PRODUCT CONTAINER (the product
itself, in the form its brief and product block name — a bottle, jar, tube,
compact or palette, lipstick, mascara, pencil or another — never a flat carton).

Produce EXACTLY THREE image-generation prompts, one per slot (A, B, C), each
a photorealistic CONCEPT render of the product with the design applied, and
each named by its own concept. The
image model receives the official BBROSE logo and the user-approved concept
references as attachments; your prompts describe the DESIGN. Write flowing
visual language. BANNED: pt/mm measurements, "dieline", aspect-ratio flags,
macro photography that obscures the whole product. High-resolution illustration or
texture is allowed when briefed; required type and the logo remain live vector artwork.

THE PICTURE IS READ, NOT ONLY SEEN. Each prompt shows the product ALONE —
standing upright, straight-on, whole and uncropped — on a plain seamless
backdrop that contrasts clearly with the product in LIGHTNESS: a light product
(pastel, pink, cream or white) on a deep charcoal-grey backdrop, a dark product
on a clean white one. Never a backdrop in the product's own colour family, never
a scene, props or a second product beside it. Write the backdrop into every
prompt in those words.

The three variations must be MATERIALLY different across all seven axes —
typography, composition, motif arrangement, closure/body relationship, front
decoration-zone strategy, colour-field structure and finish strategy — never
one design in three colourways.

Respond ONLY with valid JSON in exactly this shape (no markdown, no prose):
{{
  "schema_version": "{CONTAINER_GATE1_SCHEMA}",
  "approved_reference_ids": [<echo the approved reference ids you were given>],
  "influence_plan_hash": "<echo the influence-plan hash you were given>",
  "variations": [
    {{
      "variation_id": "<the slot letter, then this variation's own concept name: A_<NAME> | B_<NAME> | C_<NAME>>",
      "direction_id": "<the direction_id of the direction this variation realises, copied exactly — never inside variation_id>",
      "title": "<short display title>",
      "prompt": "<the complete image prompt>",
      "typography_signature": "<one line: the type system + hierarchy>",
      "composition_signature": "<one line: the composition system>",
      "motif_signature": "<one line: the decorative motif + arrangement>",
      "cap_body_signature": "<one line: the closure/body colour + finish relationship — its cap, lid, clasp or none>",
      "decoration_zone_signature": "<one line: the front decoration-zone strategy>",
      "color_field_signature": "<one line: the colour-field structure>",
      "finish_signature": "<one line: foil/spot-UV/emboss finish strategy>",
      "native_reconstruction_plan": "<one line: how the decoration is authored from live type, vector layout and retained high-resolution raster assets>",
      "reference_ids": [<the subset of approved ids this variation actually uses>]
    }},
    ... exactly three entries, one per slot, A then B then C ...
  ]
}}
Keep every prompt complete — do not truncate.
"""

__all__ = [
    "CONTAINER_GATE1_SCHEMA", "CONTAINER_VARIATION_IDENTITIES", "CONTAINER_VARIATION_SLOTS",
    "CONTAINER_REQUIRED_FIELDS", "CONTAINER_REQUIRED_FIELDS_NO_REFS",
    "CONTAINER_DIVERSITY_FIELDS",
    "CONTAINER_MIN_PAIRWISE_DIFFERENCES", "CONTAINER_GATE1_DIRECTIVES",
    "CONTAINER_SYSTEM",
    "CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT",
    "CONTAINER_VARIATION_IDENTITY_MISSING",
    "CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED",
]


#: [his final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away."] the same contract when the
#: three variations are the three planned directions — one each, in slot order, never three readings of one
CONTAINER_DIRECTIONS_DIRECTIVES = CONTAINER_GATE1_DIRECTIVES.replace(
    """Reinterpret the selected direction across three MATERIALLY different container
concepts. All three come from the direction: each variation's motif,
composition, colour field and finish are the direction's own, read three
different ways.""",
    """Draw the three planned directions, ONE container concept for each, in slot
order: A is the first direction, B the second, C the third. Each variation's
motif, composition, colour field and finish are its OWN direction's — three
truly different concepts, never three readings of one direction.""")
# [his goal for the pitch, 2026-10-15, A (3)] the house motifs are taken only where the brief asks — no direction's
# wording about them is left to replace
assert "Draw the three planned directions" in CONTAINER_DIRECTIONS_DIRECTIVES
