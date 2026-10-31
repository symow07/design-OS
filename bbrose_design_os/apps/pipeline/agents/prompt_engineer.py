from django.conf import settings

from apps.pipeline.services.claude_service import call_claude, extract_json
from apps.pipeline.services.brand_context import get_packaging_structure
import json

PROMPT_ENGINEER_SYSTEM = """
You are the Prompt Engineer for BBROSE, a luxury beauty brand.

Your job: turn each creative direction into ONE image-generation prompt that
produces a stunning CONCEPT PACKSHOT — a photorealistic hero shot of the
finished carton with the design applied, the kind of image that wins a
packaging award feature. A human will pick a direction from these renders;
print artwork is produced later from the dieline, so the render's job is to
sell the DESIGN, not to be printable.

Write prompts as VISUAL language, never production-spec language.
BANNED: percentage zone layouts, pt/mm measurements, "flat surface artwork",
"dieline", "wrap laid out in sequence", --ar flags, aspect-ratio text.
The image is portrait 2:3 (set by the system) — compose for a tall frame.

Every prompt must contain, in flowing natural sentences:
1. The object: ONE hero carton whose PHYSICAL FORM matches the Product
   Profile provided (an eyeshadow palette ships in a wide low-profile
   landscape box; a lip gloss in a tall slim carton; a compact in a small
   squat box). State the form explicitly in the first sentence. NEVER
   default to a tall upright carton, and NO other packaging in the scene —
   no bottles, tubes, droppers or jars unless the profile says the product
   itself is one.
2. The design ON the box, led by the direction's design_axis — describe the
   composition concretely: what dominates the front face, the focal element,
   how typography is treated for the PRODUCT NAME and secondary text (e.g.
   set in a modern serif, oversized, foil-stamped...), any motif or pattern
   and how it flows across the face. THE LOGO: the image model receives the
   official BBROSE logo artwork as an attached image — write "the official
   BBROSE logo placed <where, size, finish>" and NEVER describe drawing,
   restyling, or re-lettering the wordmark itself.
3. Materials and finishes AS THEY BEHAVE IN LIGHT: soft-touch matte drinking
   the light, rose-gold foil catching a highlight, blind emboss casting
   micro-shadow, gloss UV reflecting a softbox streak.
4. Exact palette anchored with the direction's hex codes.
5. The scene: styled editorial packshot — surface, backdrop, one or two
   styling props max, soft directional studio light, shallow depth of field,
   high-end beauty campaign quality. Props and surface must echo the
   direction's subject_story (hydration → a water drop or wet stone; citrus →
   a curl of zest; botanical → a single leaf) — never generic decoration.
   EXCEPT where the Design target says the product is pictured ALONE: then
   NO props at all, nothing beside it, a plain seamless ground — that
   picture is drawn from, and a prop in it is drawn as part of the design.
6. Craft bar: "award-winning packaging design, Dieline-feature quality,
   ultra-detailed, photorealistic".

The three prompts must read as three DIFFERENT designs (different dominant
elements and compositions), not one design in three colorways.

Respond ONLY with valid JSON:
{
  "prompts": [
    {
      "direction_id": "The direction_id of the direction this prompt is for, copied exactly",
      "direction_name": "Name from creative direction",
      "full_prompt": "Complete image generation prompt",
      "notes": "Any special instructions for this prompt"
    }
  ]
}
"""


VARIATION_CLAUSE = """
You are given exactly ONE approved creative direction. Produce EXACTLY THREE
prompts that are controlled VARIATIONS WITHIN that direction — one design
executed three ways, never three new directions. Vary only bounded execution
dimensions: composition emphasis, typography placement, graphic density,
imagery crop, finish/material emphasis, secondary color distribution. Every
variation must preserve the direction's design axis, core concept, subject
story, target-specific structure, originality constraints and prohibited
choices.
"""

_DIFFERENT_DESIGNS_CLAUSE = """The three prompts must read as three DIFFERENT designs (different dominant
elements and compositions), not one design in three colorways."""
#: Phase 2A-4: same system prompt, mode-switched on the one clause that differs.
PROMPT_ENGINEER_VARIATION_SYSTEM = PROMPT_ENGINEER_SYSTEM.replace(
    _DIFFERENT_DESIGNS_CLAUSE, VARIATION_CLAUSE.strip())
assert PROMPT_ENGINEER_VARIATION_SYSTEM != PROMPT_ENGINEER_SYSTEM, \
    "variation clause failed to replace the different-designs clause"
#: [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (1): "the carton
#: CONTINUES the approved container ... Its three options differ only by layout and composition on the carton ...
#: never by mood or personality."] the same prompt, the one clause switched, for a design continuing its container
CONTINUATION_CLAUSE = """The three prompts are three LAYOUTS of one approved look: each keeps the approved
container's mood, motif, colours, type and logo treatment, and differs from the others only in its
layout and composition on the carton — never in mood or personality."""
PROMPT_ENGINEER_CONTINUATION_SYSTEM = PROMPT_ENGINEER_SYSTEM.replace(_DIFFERENT_DESIGNS_CLAUSE, CONTINUATION_CLAUSE)
assert PROMPT_ENGINEER_CONTINUATION_SYSTEM != PROMPT_ENGINEER_SYSTEM, \
    "continuation clause failed to replace the different-designs clause"


class PromptEngineerAgent:

    def __init__(self, directions, packaging_structure_id, log_fn=None,
                 feedback=None, product_profile=None, reference_anatomy=None,
                 target_directive="", variation_mode=False,
                 influence_plan=None):
        self.directions = directions
        self.structure = get_packaging_structure(packaging_structure_id) if packaging_structure_id else None
        self.feedback = feedback
        self.product_profile = product_profile or {}
        self.reference_anatomy = reference_anatomy or {}
        # Target directive (Phase B3): steers the object type (carton vs
        # container vs ...). Empty for packaging → prompt byte-identical.
        self.target_directive = target_directive or ""
        # Phase 2A-4: True → the input is ONE selected direction and the output is
        # three controlled variations within it (Gate 1 keeps its three concepts).
        self.variation_mode = variation_mode
        # 2A-6E §5: material_influence_plan/1.0 built from USER-approved
        # concept references — design principles the prompts must express,
        # never assets, never a layout to reproduce. None → byte-identical.
        self.influence_plan = influence_plan or None
        # B4b-3B §13: owner-uploaded reference summary text (categories +
        # REFERENCE ONLY constraints), built by the manifest module and set
        # by ARIA. None → prompt byte-identical.
        self.uploaded_reference_context = None
        # §BH71 PART 2: the trend board's words (trend_board.words_block) — found on the web, not his upload
        self.trend_context = None
        # [his test blocker on design 123, (1)] the approved container this design continues, in its record's words
        # (targets.composite.continuation_words) — None for every other design, whose prompt is unchanged
        self.continuation = None
        self.log = log_fn or (lambda *a, **k: None)

    def run(self):
        self.log("Prompt Engineer: building dieline-aware prompts")

        structure_text = json.dumps(self.structure, indent=2) if self.structure else "No structure specified — use standard beauty product proportions"
        directions_text = json.dumps(self.directions, indent=2)

        from apps.pipeline.services.product_profile import profile_text, with_brief_colours
        product_block = profile_text(self.product_profile) or (
            "Not identified — derive the product and its carton form from "
            "the creative directions; still never default to a tall carton."
        )

        revision_block = ""
        if self.feedback:
            self.log("Prompt Engineer: applying revision feedback")
            revision_block = f"""
## Revision notes — address these
The previous renders missed the mark. Tighten each prompt to resolve this
feedback (palette fidelity, finish cues, composition, brand mood):
{self.feedback}
"""

        anatomy_block = ""
        if self.reference_anatomy:
            anatomy_block = (
                "\n## House composition vocabulary (measured from the closest"
                " real BBROSE production file — borrow its conventions for"
                " scale, placement and finishes, never copy the layout)\n"
                + json.dumps(self.reference_anatomy, ensure_ascii=False)[:2000]
                + "\n"
            )

        influence_block = ""
        if self.influence_plan:
            self.log("Prompt Engineer: applying approved material-influence "
                     "plan")
            influence_block = (
                "\n## Approved material references (concept influence ONLY)\n"
                "The user approved specific library references for THIS task. "
                "Express their design PRINCIPLES in every prompt — palette "
                "balance, composition discipline, motif treatment, texture "
                "layering, finishing language. NEVER instruct copying a "
                "layout, reproducing a pattern, tracing artwork or imitating "
                "a recognizable design. No production use is granted.\n"
                + json.dumps(self.influence_plan, ensure_ascii=False)[:4000]
                + "\n")

        uploaded_block = ""
        if self.uploaded_reference_context:
            self.log("Prompt Engineer: including owner-uploaded reference "
                     "guidance")
            uploaded_block = ("\n## Owner-uploaded references "
                              "(REFERENCE ONLY)\n"
                              + self.uploaded_reference_context + "\n")

        # [his answer 1 of 2026-10-02 (6badb27)] the brief's own colours, said to the step that makes the concept picture
        product_block = with_brief_colours(product_block, self.product_profile)
        trend_block = ""
        if self.trend_context:
            self.log("Prompt Engineer: including the trend board's words")
            trend_block = "\n## Current trends found on the web (words only)\n" + self.trend_context + "\n"

        # Target directive (B3): when set (non-packaging), it leads the message
        # and overrides any carton framing. Empty → block absent → byte-identical.
        directive_block = (f"## Design target — READ FIRST\n{self.target_directive}\n\n"
                           if self.target_directive else "")

        # [his test blocker on design 123, (1)] the container it continues, said beside its directions
        continuation_block = ("\n## This design continues its approved container — keep its look\n"
                              + self.continuation + "\n") if self.continuation else ""
        user_message = f"""
{directive_block}## Product Profile (the carton form MUST match this product)
{product_block}

## Creative Directions
{directions_text}
{continuation_block}
## Packaging Structure
{structure_text}
{anatomy_block}{influence_block}{uploaded_block}{trend_block}{revision_block}
{"Build EXACTLY THREE variation prompts for the single selected direction above." if self.variation_mode else "Build one dieline-aware image generation prompt per direction."}
"""

        # Sonnet: prompt construction is text-only — reserve Opus for vision QA.
        system = (PROMPT_ENGINEER_VARIATION_SYSTEM if self.variation_mode
                  else PROMPT_ENGINEER_CONTINUATION_SYSTEM if self.continuation
                  else PROMPT_ENGINEER_SYSTEM)
        response = call_claude(
            system, user_message, max_tokens=3000,
            model=settings.CLAUDE_MODEL_FAST, operation="image_prompts",
        )

        try:
            result = extract_json(response)
            prompts = result.get('prompts', [])
            self.log(f"Prompt Engineer: built {len(prompts)} prompts")
            return prompts
        except ValueError as e:
            self.log(f"Prompt Engineer: could not parse response — {e}", level='error')
            return []
