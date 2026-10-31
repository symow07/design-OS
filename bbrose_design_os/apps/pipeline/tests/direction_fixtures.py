"""One canonical VALID structured-director output for tests — Phase 2A-2.

Every test that stubs the model uses this document (or a deliberate mutation of it), so
"what a valid generation looks like" is defined once. The three directions are built to
classify into different signature families on every dimension; a test pins that property,
because if the fixture ever collapsed semantically, every consumer test would quietly stop
exercising the pass path.
"""
from __future__ import annotations

import copy


def valid_intent():
    return {
        "visual_objective": "Express hydration as suspended water, unmistakably BBROSE.",
        "audience_interpretation": "Premium skincare buyers who read texture as efficacy.",
        "hierarchy": "product name first, brand mark second, benefit line third",
        "focal_point": "a single suspended droplet at the optical center",
        "composition": "vertical thirds with generous negative space above the name",
        "typography_strategy": "expressive display type against quiet support copy",
        "color_strategy": "porcelain neutrals carrying one saturated accent",
        "motif_strategy": "one water motif, rendered differently per direction",
        "imagery_strategy": "no photography; drawn, engraved or embossed motifs only",
        "material_finish_direction": "soft-touch matte with selective gloss",
        "target_structural_guidance": "tall slim serum carton; the front face is the hero",
        "originality_constraints": ["no reuse of prior artwork", "logo never restyled"],
        "forbidden_choices": ["logo centered on a plain colored box", "stock imagery"],
        "unresolved_questions": ["final carton height unconfirmed"],
        "confidence": "MEDIUM",
        "source_references": ["brand context brief", "target directive: packaging"],
    }


def valid_directions():
    shared = {
        "subject_story": "Hyaluronic hydration told as water held in suspension.",
        "product_target_fit": "tall slim serum carton; form stated in the first line",
        "target_structural_guidance": "front face carries the story; sides stay quiet",
        "imagery_approach": "drawn and tooled surfaces, no photography",
        "originality_notes": "evolves house conventions; copies no prior artwork",
        "prohibited_choices": ["no centered-logo-on-a-box", "no stock art"],
        "risks": "foil and emboss budgets need production confirmation",
        "native_reconstruction_plan": "live serif/script/sans typography; vector "
            "water/botanical motifs; flat + gradient colour fields; front-face "
            "decoration surface; foil/emboss finish masks; any photography is "
            "concept-render only — printed decoration needs zero decorative rasters",
    }
    return [
        {**shared,
         "direction_id": "d1", "name": "Porcelain Verse",
         "concept_statement": "The product name set monumental becomes the design itself.",
         "design_axis": "typography-led",
         "layout_structure": "oversized name fills the upper two thirds of the front "
                             "face; logo small at the base",
         "focal_hierarchy": "name first, then the droplet glyph, then the logo",
         "hierarchy_family": "NAME_FIRST",
         "color_system": "porcelain white field with rose gold type",
         "typography": "oversized modern serif display for the product name",
         "graphic_elements": "a fine keyline frame and one droplet-shaped counter",
         "material_finish_direction": "soft-touch matte with rose gold foil type",
         "emotional_tone": "serene and still",
         "prompt_seed": "A tall slim porcelain-white carton where the oversized serif "
                        "product name IS the composition; rose gold foil; quiet light."},
        {**shared,
         "direction_id": "d2", "name": "Botanical Meridian",
         "concept_statement": "An engraved botanical field carries every face.",
         "design_axis": "pattern-led",
         "layout_structure": "engraved botanical pattern wraps all faces with a calm "
                             "central window for the name",
         "focal_hierarchy": "motif first — the pattern leads the eye to the window",
         "hierarchy_family": "MOTIF_FIRST",
         "color_system": "deep botanical green with blush accents",
         "typography": "hand-lettered script for the name inside the window",
         "graphic_elements": "botanical peony engraving flowing across panels",
         "material_finish_direction": "uncoated tactile stock, blind deboss on the window",
         "emotional_tone": "romantic and tender",
         "prompt_seed": "A tall slim deep-green carton wrapped in an engraved botanical "
                        "field; a calm window holds a hand-lettered name."},
        {**shared,
         "direction_id": "d3", "name": "Still Water Relief",
         "concept_statement": "The finish is the story: a sculpted droplet in relief.",
         "design_axis": "material-led",
         "layout_structure": "full-bleed blind emboss droplet relief; text confined to "
                             "a narrow foil strip at the base",
         "focal_hierarchy": "material first — the finish leads before any words",
         "hierarchy_family": "MATERIAL_FIRST",
         "color_system": "monochrome nude with a single gloss accent",
         "typography": "clean geometric sans in a single quiet line",
         "graphic_elements": "no motif; material only — the emboss is the graphic",
         "material_finish_direction": "heavy blind emboss with one gloss-UV droplet",
         "emotional_tone": "dramatic and intense",
         "prompt_seed": "A tall slim nude carton whose entire front is a blind-embossed "
                        "droplet relief catching raking light; one foil strip of text."},
    ]


def valid_document():
    return {"design_intent": valid_intent(), "directions": valid_directions()}


def mutated(document_mutator):
    """A deep copy of the valid document with one deliberate defect applied."""
    document = copy.deepcopy(valid_document())
    document_mutator(document)
    return document
