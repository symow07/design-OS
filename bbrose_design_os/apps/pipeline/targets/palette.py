"""Palette design target (PALT-M4C §2).

Palette is a DEDICATED target, not an alias for Product Container. The
PALT-M4C §D audit found the palette geometry engine could not reach a
selected concept, and the root cause was that ``palette`` was not a
``DesignTarget`` at all — so no palette task, TaskReference or
ConceptReference could exist.

Approved HYBRID architecture: the target is dedicated, while rendering,
diagnostics, references, evidence, the Design Graph, owner gates and the
artifact infrastructure stay shared with the other targets.
"""
from __future__ import annotations

from apps.pipeline.targets.base import DesignTarget, TargetStrategy

# §3 — palette-specific reference categories. Every one stays
# REFERENCE_ONLY until an explicit authority process elevates it.
PALETTE_REFERENCE_KINDS = (
    ("palette_concept", "Palette concept"),
    ("palette_product", "Palette product reference"),
    ("outer_case", "Outer-case reference"),
    ("pan_layout", "Pan-layout reference"),
    ("hinge", "Hinge reference"),
    ("clasp", "Clasp reference"),
    ("mirror", "Mirror reference"),
    ("powder_finish", "Powder-finish reference"),
    ("artwork", "Artwork reference"),
    ("logo", "Logo"),
    ("typography", "Typography"),
    ("color", "Colour reference"),
    ("material", "Material reference"),
    ("inspiration", "Inspiration"),
)

SELECTED_CONCEPT_ROLE = "SELECTED_PALETTE_DESIGN_INTENT_REFERENCE"

CONCEPT_PROMPT_PROFILE = (
    "The object is a cosmetic PALETTE: a shallow hinged case containing "
    "recessed pans of pressed powder. Show the case, the pan layout and the "
    "lid relationship. It is not a bottle, jar, tube or carton."
)


#: §BH70(2) (§BH70 LIVE), his words: "Palette must be startable from New design. If it needs its case, lid, hinge and
#: clasp read from a concept, the system makes that concept as its first step. It does not refuse me at the door."
#: A palette is started as what the system designs end to end: a Product Container of the Compact / Palette form — the
#: route his own palette brief took (task 84, through Complete Product, §BH56) and the form §BH61 (LIVE) made its shape
#: step show — its concept made first (the container path's Gate 1), its case's size and closure confirmed at the shape
#: step, its lid drawn from the concept's own arrangement (§BH66, LIVE). The creation door reads these two; the dedicated
#: engine below keeps its `needs`, and the card no longer waits on them.
STARTS_AS = DesignTarget.PRODUCT_CONTAINER.value
STARTS_WITH_FORM_HINT = "\n\n[Container type: compact]"


class PaletteTarget(TargetStrategy):
    """Dedicated palette strategy."""

    name = DesignTarget.PALETTE.value
    #: §BH55 Phase 2, MEASURED: its intent comes only from `palette_es3083_intent.build_es3083_intent()` (no
    #: argument; one reference product), and five of its six components are NOT_BUILT
    #: (`palette_design_graph.COMPONENTS`: case, lid, base, hinge, clasp — only the tray is built). Before this it
    #: read Active, accepted a project, ran the paid planner and three paid renders, and failed after Gate 1.
    needs = ("a design intent read from its own concept (today's is fixed to one reference product, ES3083) "
             "and the geometry of its case, lid, base, hinge and clasp (only its tray is built)")

    def concept_structure_id(self, aria):
        """A palette has no carton structure — its structure is the case and
        pan layout, which the palette contract owns."""
        return None

    def concept_prompt_profile(self, aria) -> str:
        return CONCEPT_PROMPT_PROFILE

    def begin_output(self, aria, approved_image):
        """Back half. The palette deliverable pipeline is built across
        PALT-M4B/M4C; this entry point exists so the target is registered
        and dispatchable rather than silently absent.

        It fails closed rather than pretending to produce a deliverable:
        the owner's completion law forbids treating a registered strategy
        as a working feature.
        """
        raise NotImplementedError(
            "PALETTE_OUTPUT_PIPELINE_NOT_YET_CONNECTED — the palette "
            "geometry engine (PALT-M4B) and design-intent bridge "
            "(PALT-M4C) exist, but the Gate-1-to-deliverable entry is not "
            "wired. Registered and selectable; not yet productive.")

    def review_sections(self, task) -> list[dict]:
        from apps.pipeline.services import palette_design_intent as di
        return [
            {"label": "Design target", "value": "Palette (dedicated)"},
            {"label": "Concept authority", "value": di.REFERENCE_AUTHORITY},
            {"label": "Selected concept role", "value": SELECTED_CONCEPT_ROLE},
            {"label": "Manufacturing authority", "value": "NOT_ESTABLISHED"},
        ]
