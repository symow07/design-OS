"""The words a designer reads for a design's state (§BH55 Phase 3, 2026-09-19).

OWNER STANDING ORDER §BH55, PHASE 3: "Every capability the engine has is reachable and labelled in words a designer
understands." A design's status is the engine's name for where it stands ("awaiting_gate_1"); a designer reads what
happens next, or what already happened ("Choose a concept"). ONE map, read by the list, the design's own header and the
side panel — the server renders it and hands the same map to the page's script (`status-words`). The engine's names
stay the record's; these are only what the screen says.
"""
from __future__ import annotations

import re

STATUS_WORDS = {
    "queued": "Starting",
    "running": "Working on it",
    "awaiting_trend_review": "Trend pictures found — untick any you dislike",
    "awaiting_direction_selection": "Choose a direction",
    "awaiting_gate_1": "Choose a concept",
    "gate_1_approved": "Concept chosen",
    "awaiting_dimensions": "Confirm the size",
    "awaiting_container_profile": "Confirm the shape",
    "container_stage_visually_rejected": "Rejected at review",
    "awaiting_structure_confirmation": "Paused at a retired structure check",    # the step is gone (2026-10-04)
    "awaiting_design_intent_confirmation": "Confirm the design intent",
    "design_intent_confirmed": "Design intent confirmed",
    "generating_dieline": "Laying out the design",
    "awaiting_gate_2": "Review the design",
    "gate_2_approved": "Approved — preparing the files",
    "completed": "Finished",
    "failed": "Stopped",
    "rejected": "Rejected",
    "awaiting_gate1_generation_configuration": "Set up the concept renders",
}


def status_words(status: str | None) -> str:
    """What the screen says for ``status``; an unknown status is shown as the engine names it, never hidden."""
    return STATUS_WORDS.get(status or "", (status or "").replace("_", " "))


# --- §BH55 Phase 3, p3-history: the same discipline for the other names a record carries. Each map is what the SCREEN
# --- says; the records keep their own codes, and a code with no words here is shown as the record writes it.

def target_words(target: str | None) -> str:
    """What a design is being made — the start form's own card names, so the two can never drift apart."""
    from apps.pipeline.targets.ui import TARGET_CARDS
    for card in TARGET_CARDS:
        if card["value"] == target:
            return card["name"]
    return (target or "").replace("_", " ").strip() or "—"


#: a human decision at a gate, in words (the records' own GATE_CHOICES / DECISION_CHOICES)
GATE_WORDS = {"gate_1": "The concept", "dimension": "The size", "container_profile": "The container's shape",
              "structure": "The carton's structure", "design_intent": "The design intent", "gate_2": "The design"}
DECISION_WORDS = {"approve": "approved", "reject": "changes asked for"}

#: a reference offered to a design's concepts (ConceptReference), in words
REFERENCE_SOURCE_WORDS = {"HISTORICAL_DESIGN_REFERENCE": "a past BBROSE design",
                          "AI_DESIGN_LIBRARY": "one of the house's Illustrator files",
                          "MATERIAL_LIBRARY": "from the materials library", "WEB_REFERENCE": "found on the web"}
REFERENCE_OWNERSHIP_WORDS = {"HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED": "the house's own work — not yet confirmed",
                             "LIKELY_BBROSE_UNCONFIRMED": "probably BBROSE's own — not confirmed",
                             "UNCONFIRMED_THIRD_PARTY": "probably someone else's — not confirmed",
                             "OWNERSHIP_UNCONFIRMED": "whose it is: not confirmed",
                             "UNKNOWN": "whose it is: unknown"}
REFERENCE_RIGHTS_WORDS = {"RIGHTS_UNREVIEWED": "its rights not reviewed", "UNVERIFIED": "its rights not verified",
                          "PENDING_HUMAN_CONFIRMATION": "its rights waiting for a person to confirm"}
REFERENCE_PERMISSION_WORDS = {"CANDIDATE": "offered — not approved", "DECLINED": "declined",
                              "USER_APPROVED_FOR_CONCEPT_REFERENCE":
                                  "approved — a reference for this design's concepts only"}

#: the materials record's tiers, in words (the Image seam's own rule states the rest)
#: what a notification says happened to a design, after the design's name (the bell's short list); its kinds are
#: apps/pipeline/models.py NOTIFICATION_KINDS
NOTE_WORDS = {"awaiting_direction_selection": "its three directions are ready — choose one",
              "awaiting_gate1_generation_configuration": "its concepts wait to be set up",
              "awaiting_gate_1": "its concepts are ready — choose one",
              "awaiting_dimensions": "its size waits for you to confirm",
              "awaiting_container_profile": "its shape waits for you to confirm",
              "awaiting_design_intent_confirmation": "what it should be waits for you to confirm",
              "awaiting_gate_2": "it is drawn — review it", "failed": "it stopped", "completed": "it is finished"}


def note_words(kind: str | None) -> str:
    return NOTE_WORDS.get(kind or "", status_words(kind).lower())


#: the palette's material studies by what each shows (apps/pipeline/services/palette_material_engine.py, each
#: contract's own description)
MATERIAL_STUDY_WORDS = {"NEUTRAL_ABS_MATTE": "a matte grey case, the engineering default",
                        "DARK_GLOSSY_ABS": "a dark high-gloss case", "LIGHT_SATIN_ABS": "a light satin case",
                        "METALLIC_ACCENT": "a metallic lid, hinge and clasp",
                        "ES3083_SYMBOLIC_ZONES": "the ES3083's zones in their named colours",
                        "OWNER_SUBSTITUTED_COLOUR": "a colour you chose, on another base material"}

TIER_WORDS = {"PRODUCTION": "may be placed in a design", "REFERENCE": "a reference only — never placed"}

#: why a design's review cannot pass, and what its readiness record blocks on — the records' own codes, in words; a
#: code carries its own detail after a colon, which is kept as the record wrote it
READINESS_WORDS = {
    "HUMAN_VISUAL_ACCEPTANCE_REQUIRED": "a person must accept how it looks",
    "CONTAINER_FRONT_COPY_FIT_UNMEASURED": "the front copy has not been measured against its zone",
    "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_BAND": "a line of the front's copy sits above or below the safe area",
    "CONTAINER_BACK_COPY_FIT_UNMEASURED": "the back copy has not been measured against its panel",
    "CONTENT_VERIFICATION_REQUIRED": "the printed copy is still a placeholder — it must be verified",
    "COLOUR_USAGE_UNRECONCILED": "the colours drawn have not been reconciled with the brand's roles",
    "CONTAINER_PRINT_DATA_INCOMPLETE": "the printed information is incomplete",
    "MISSING_OUTPUT_INTENT": "no output intent is set for it",
    "CONTAINER_FIDELITY_REPORT_ABSENT": "a fidelity report it needs is not on record",
    "CONTAINER_MINIMUM_TEXT_SIZE_FAILED": "some printed text is below the size its print method allows",
    # §BH70(3): it held a design until a sample was made; a colleague test-fits one, and nothing waits on it
    "PHYSICAL_SAMPLE_VALIDATION_REQUIRED": "a colleague test-fits a printed sample — nothing waits on it",
    "VISUAL_QUALITY_GATE_FAILED": "its drawing has not passed the visual-quality gate — the gate's own axes must pass "
                                  "before anyone may approve it",
    "TECHNICAL_INTERVENTION_REQUIRED": "its records disagree with each other — a person with the code must look before "
                                       "it can move",
    "RECONSTRUCTION_NOT_COMPLETED": "its drawing did not finish — it must be drawn again",
    "ARTIFACT_NOT_AVAILABLE": "the editable file it would be approved on is not there",
}

#: THE OWNER'S ANSWER OF 2026-09-27: "The maker's printing specification is shown as a production note, never a
#: blocker." Each note in words for the printer — none says it holds anything (§BH50(f)(4): a label that blocks
#: nothing must not say it blocks). Keyed like container_production_readiness.MAKER_SPECIFICATION_NOTES.
PRODUCTION_NOTE_WORDS = {
    "CONTAINER_TECHNIQUE_UNVERIFIED": "the maker's printing specification confirms the print technique",
    "CONTAINER_TRAPPING_REVIEW_REQUIRED": "trapping is set to the maker's printing specification",
    "CONTAINER_OVERPRINT_REVIEW_REQUIRED": "overprinting is set to the maker's printing specification",
    "CONTAINER_REGISTRATION_REVIEW_REQUIRED": "registration is checked against the maker's printing specification",
    "CONTAINER_COLOR_COUNT_EXCEEDED": "more colours than this print method usually takes — the maker's "
                                      "specification says how many",
    "CONTAINER_MINIMUM_LINE_WEIGHT_FAILED": "a line finer than this print method usually holds — the maker's "
                                            "specification says how fine",
    "CONTAINER_MAXIMUM_COVERAGE_EXCEEDED": "more ink cover than this print method usually takes — the maker's "
                                           "specification says how much",
    "CONTAINER_REGISTRATION_TOLERANCE_FAILED": "tighter registration than this print method usually holds — the "
                                               "maker's specification says how tight",
    "CONTAINER_WHITE_UNDERBASE_REQUIRED": "the printer settles whether white goes under the colours",
    "MISSING_OUTPUT_INTENT": "the print shop's colour profile goes into the file before it prints",
}

#: §BH71 (0a), THE OWNER'S GOAL OF 2026-09-28: "Unmeasured checks (fidelity to the concept, copy fit) show as a warning
#: beside Approve, never a block." Each kind in words — what is not measured yet, never that it holds anything
#: (§BH50(f)(4)). READINESS_WORDS keeps its three entries for the same codes, for records read before (0a).
ACCEPTANCE_WARNING_WORDS = {
    "CONTAINER_FIDELITY_UNMEASURED": "how true the drawing is to its concept",
    "CONTAINER_QUANT_FIDELITY_UNMEASURED": "the drawing's measures against its concept",
    "CONTAINER_MOTIF_FIDELITY_UNMEASURED": "the drawing's motif against its concept",
    "CONTAINER_TYPOGRAPHY_FIDELITY_UNMEASURED": "the drawing's lettering against its concept",
    "CONTAINER_CONCEPT_FIDELITY_UNMEASURED": "the drawing's shape and material against its concept",
    "CONTAINER_FIDELITY_REPORT_ABSENT": "a check of the drawing against its concept that this kind of product does "
                                        "not have yet",
    "CONTAINER_FRONT_COPY_FIT_UNMEASURED": "whether the front copy fits its zone",
    "CONTAINER_BACK_COPY_FIT_UNMEASURED": "whether the back copy fits its panel",
    "CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED": "the size of copy drawn only as a picture of the product",
    # [his answer of 2026-09-29 to the §BH71 report, (4)] words nobody has confirmed, said "not confirmed yet"
    "CONTAINER_SHADE_ARABIC_UNCONFIRMED": "the shade name's Arabic, written by the executor",
    # [his review of 119, 2026-10-05, point 6] the label's words the system's translation wrote
    "CARTON_TRANSLATION_UNCONFIRMED": "the label's Spanish and Arabic, written by the system's translation from your "
                                      "English",
    "CARTON_FRONT_COPY_UNMEASURED": "whether the carton's front copy fits its panel",
    "ARTWORK_COPY_UNMEASURED": "whether a piece's copy fits its box",
}
#: the visual-quality check's axes, in the words the design page already gives them
VQ_AXIS_WARNING_WORDS = {
    "artifact_authority": "whether the editable file is there and whole",
    "artboard_fitness": "whether the artboard fits the product",
    "silhouette_fidelity": "whether the outline matches the concept",
    "closure_fidelity": "whether the closure matches the concept",
    "front_artwork_resolution": "whether the front artwork is drawn, not a stand-in",
    "logo_quality": "whether the mark is whole, unstretched and big enough",
    "typography_quality": "whether any text is cut off, overlapping or too small",
    "composition_quality": "whether everything is on the artboard, with no text over text",
}

#: what a paid call did, by the operation its ledger row carries
OPERATION_WORDS = {"creative_directions": "planned the directions", "image_prompts": "wrote the prompts",
                   "qa_vision_review": "checked a concept", "product_identification": "identified the product",
                   "dieline_estimation": "estimated the carton's size", "panel_translation": "translated the label copy",
                   "container_gate1_variations": "planned the container's concepts",
                   "gate1_regeneration_prompts": "wrote the prompts again, with references",
                   "vq1_close1_structural_inspection": "inspected a bottle's structure",
                   "inspiration_read": "read an inspiration picture",
                   # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)]
                   "label_copy_writing": "wrote the label's missing copy for the product type"}


# [the owner's answer to the UI directions of 2026-09-25: the palette's design-intent page is in the one shell and says
# its reading in words; each value the form posts is the record's code, as it was (PALT-M4C-4)]
#: how binding one field of a palette's reading is (palette_design_intent's levels)
INTENT_LEVEL_WORDS = {"HARD_VISIBLE_CONSTRAINT": "Must be seen", "SOFT_VISUAL_CONSTRAINT": "Should be seen",
                      "DECORATIVE_PREFERENCE": "A preference"}
#: where one field of the reading stands (palette_design_intent's states and the confirmation's provisional ones)
INTENT_STATE_WORDS = {"PROVISIONAL_PENDING_CONFIRMATION": "Read — not yet confirmed",
                      "PROVISIONAL_VISIBLE_CONSTRAINT": "Read as binding — not yet confirmed",
                      "AI_DESIGN_INTENT_DRAFT": "A first reading", "PENDING_OWNER_CONFIRMATION": "Waiting for you",
                      "HUMAN_CONFIRMED_DESIGN_INTENT": "Confirmed", "OWNER_CORRECTED": "Corrected by you",
                      "OWNER_REMOVED": "Removed by you", "UNRESOLVED": "Unresolved",
                      "SOURCE": "The picture it was read from"}
#: how a field was read off the picture
INTENT_METHOD_WORDS = {"OWNER_STATED": "as you stated it", "IMAGE_MEASURED": "measured on the picture",
                       "IMAGE_COUNTED": "counted on the picture", "IMAGE_INFERRED": "judged from the picture",
                       "NOT_EXTRACTED": "not read"}
#: what you can do to one field — each option's label; its value is the record's action
INTENT_ACTION_WORDS = {"CONFIRM": "Confirm it", "CORRECT": "Correct it — type the value", "DELETE": "Remove it",
                       "ADD": "Add it — type the value", "RECLASSIFY": "Change how binding it is — type the level",
                       "MARK_UNRESOLVED": "Mark it unresolved", "NOTE": "Add a note — type it"}


def _words(mapping: dict, code, fallback: str = "") -> str:
    """A code in words, or — when no words are written for it — the code as the record writes it."""
    code = str(code or "")
    return mapping.get(code) or fallback or code.replace("_", " ").lower()


def gate_words(gate) -> str:
    return _words(GATE_WORDS, gate)


def decision_words(decision) -> str:
    return _words(DECISION_WORDS, decision)


def reference_words(row) -> dict:
    """One offered reference in words — where it came from, whose it is, its rights and its permission."""
    return {"source": _words(REFERENCE_SOURCE_WORDS, getattr(row, "source_type", "")),
            "ownership": _words(REFERENCE_OWNERSHIP_WORDS, getattr(row, "ownership_status", "")),
            "rights": _words(REFERENCE_RIGHTS_WORDS, getattr(row, "rights_status", "")),
            "permission": _words(REFERENCE_PERMISSION_WORDS, getattr(row, "permission_status", ""))}


def tier_words(tier) -> str:
    return _words(TIER_WORDS, tier, fallback="no tier row" if not tier else "")


def readiness_words(code) -> str:
    """One blocking code in words, with the detail the record wrote after its colon kept as it is."""
    head, _, detail = str(code or "").partition(":")
    # [his goal of 2026-10-13, (1)] every check its words — never its code with the underscores taken out
    words = READINESS_WORDS.get(head.strip()) or check_words(head.strip()) or FAULT_REASON
    return f"{words} — {detail.strip()}" if detail.strip() else words


def acceptance_warning_words(code, count=1) -> str:
    """One kind of unmeasured check in words — "not measured yet", and how many where one kind has many; words nobody
    has confirmed (``UNCONFIRMED_WARNINGS``) — "not confirmed yet" [his answer of 2026-09-29 to the §BH71 report, (4)]."""
    from apps.ire.container_production_readiness import UNCONFIRMED_WARNINGS
    head = str(code or "").partition(":")[0].strip()
    words = ACCEPTANCE_WARNING_WORDS.get(head) or head.replace("_", " ").lower()
    if head in UNCONFIRMED_WARNINGS:
        return "%s — not confirmed yet" % words
    return "%s — not measured yet%s" % (words, " (%d measures)" % count if count > 1 else "")


def acceptance_warning_rows(codes) -> list:
    """The unmeasured checks in words, one row per kind in the order first met, with how many where one kind has
    many — the design page beside Approve and the record page both say them so."""
    kinds: dict = {}
    for c in codes or []:
        kinds.setdefault(str(c).partition(":")[0].strip(), []).append(c)
    return [{"code": head, "words": acceptance_warning_words(head, len(found))} for head, found in kinds.items()]


def vq_axis_warning_words(axis) -> str:
    """A visual-quality axis not measured yet, in words."""
    return "%s — not measured yet" % (VQ_AXIS_WARNING_WORDS.get(str(axis or "")) or str(axis or "").replace("_", " "))


#: §BH71 (0b): the code place's note, in words — kept apart from PRODUCTION_NOTE_WORDS, which is keyed exactly like
#: the maker's specification (the owner's answer of 2026-09-27)
CODE_PLACE_NOTE_WORDS = {
    "CONTAINER_BATCH_CODE_PLACE_NOT_CONFIRMED": "where the batch code prints is settled with the filler — a place is "
                                                "proposed",
    # [his answers after 122 was redrawn, 2026-10-08, (1)] said beside Approve, never a block
    "CONTAINER_SKU_NOT_GIVEN": "no SKU yet — add it beside Approve whenever you have it",
}


def production_note_words(code) -> str:
    """One production note in words, the detail the record wrote after its colon kept as it is."""
    head, _, detail = str(code or "").partition(":")
    words = (PRODUCTION_NOTE_WORDS.get(head.strip()) or CODE_PLACE_NOTE_WORDS.get(head.strip())
             or readiness_words(head))
    return f"{words} — {detail.strip()}" if detail.strip() else words


def operation_words(operation) -> str:
    """What one paid call did. A concept's drawing carries its direction's name; the flat artwork its own operation."""
    op = str(operation or "")
    if op.startswith("image:flat_artwork"):
        return "took the artwork out of the chosen concept"
    if op.startswith("image:"):
        return f"drew a concept — {op.split(':', 1)[1]}"
    return _words(OPERATION_WORDS, op)


# --- the owner's goal of 2026-09-25, "THE UI, DESIGNED THIS TIME", (d): "Plain words everywhere. No engine codes on
# --- screen." Why a design stopped, in words: its recorded error is read here and put into words where words are
# --- written for it. The record keeps its own text; only the screen changes. Measured on 2026-09-25 over every stopped
# --- design's error_message (tasks 11, 16, 18, 27, 49, 86–96, 99–102, 106, 109, 111).

#: the checks a set of three directions must pass before it is offered (direction planning's own validation codes)
DIRECTION_CHECK_WORDS = {
    "TYPOGRAPHY_NOT_DISTINCT": "their type was too alike",
    "HIERARCHY_NOT_DISTINCT": "their layouts were too alike",
    "PALETTE_SYSTEMS_NOT_DISTINCT": "their colours were too alike",
    "MOTIF_NOT_DISTINCT": "their motifs were too alike",
    "DIRECTIONS_SHARE_CORE_MOTIF": "they shared one motif",
    # [his correction of 2026-10-07] the motif his brief asks for in all three, and one composition too — [his test
    # blocker on design 123, (1)] and a carton continuing its container in one layout: said for both
    "COMPOSITION_NOT_DISTINCT": "they shared one layout",
    "DIRECTIONS_SUPERFICIALLY_VARIANT": "they differed only on the surface",
    "DIRECTION_SIGNATURE_INSUFFICIENT": "they lacked a character of their own",
    # [his test blocker on design 123, 2026-10-09: it read "emotional tone not distinct", the code with its underscores
    # taken out] the mood check's own words, and the plan's word-for-word duplicates', "not distinct" checks since (2)
    "EMOTIONAL_TONE_NOT_DISTINCT": "their mood was too alike",
    "DUPLICATE_DESIGN_AXIS": "two of them had the same idea, word for word",
    "DUPLICATE_LAYOUT_STRUCTURE": "two of them had the same layout, word for word",
    "DUPLICATE_COLOR_SYSTEM": "two of them had the same colours, word for word",
    "PRODUCTION_RASTER_DEPENDENCY": "a direction needed a photographic picture, which can't go into print-ready artwork",
    "UNCONFIRMED_STRUCTURE_ASSUMED": "a direction assumed a shape nobody had confirmed",
    # his test day finding 1, 2026-09-29: it read "required copy missing", the code with its underscores taken out
    "REQUIRED_COPY_MISSING": "they left out copy your brief requires, word for word",
    # [his goal of 2026-10-10, item 1: design 124 stopped twice on "house accents over one"] every check the planner's
    # three are read against, in words — shown beside the three now, never a stop
    "HOUSE_ACCENTS_OVER_ONE": "a direction used more than one of BBROSE's own colours beside your brief's colours",
    "DECORATIVE_COVERAGE_EXCEEDED": "a direction covered more of the pack in decoration than your brief allows",
    "ORIGINALITY_VIOLATION": "a direction asked for a reference's design to be copied",
    "DUPLICATE_DIRECTION_ID": "two of them had the same id, so the later is told apart by its letter",
    "DUPLICATE_DIRECTION_NAME": "two of them had the same name, so the later is told apart by its letter",
    # [his goal for the pitch, 2026-10-15, A (3)] the motifs no direction takes unasked, or again
    "DEFAULT_MOTIF_UNASKED": "a direction drew a rose or an arch your brief did not ask for",
    "RECENT_MOTIF_REPEATED": "a direction repeated the main motif of one of your recent designs",
    "OUTPUT_NOT_JSON": "the answer could not be read",
    "OUTPUT_NOT_AN_OBJECT": "the answer could not be read",
    "NOT_AN_OBJECT": "the answer could not be read",
    "DIRECTION_COUNT_INVALID": "the answer did not hold three directions",
    "FIELD_REQUIRED": "the answer left out a part every direction needs",
    "FIELD_NOT_TEXT": "the answer wrote a part in the wrong form",
    "FIELD_NOT_A_LIST": "the answer wrote a part in the wrong form",
    "FIELD_TOO_LONG": "the answer wrote a part longer than it may be",
    "FIELD_INVALID": "the answer wrote a part that could not be read",
    "TOO_MANY_ENTRIES": "the answer listed more than it may",
    "UNSUPPORTED_FIELD": "the answer added parts the plan has no place for",
    "UNSUPPORTED_TARGET": "the answer named a design type there is none of",
    "REFERENCE_LABEL_INVALID": "the answer named a reference the wrong way",
    "REFERENCE_SOURCE_INVALID": "the answer named a reference the wrong way",
    "HIERARCHY_FAMILY_NOT_DECLARED": "a direction did not say how its layout is ordered",
    "CONFIDENCE_INVALID": "the answer did not say how sure it was",
    "TARGET_GUIDANCE_MISSING": "the answer left out the guidance for this design type",
    "CONTRACT_INVALID": "the answer could not be read as three directions",
}
#: a stop the design's own error names, by the words its error starts with or contains
STOP_MESSAGE_WORDS = (
    ("Missing API key", "The writing service had no key, so nothing was written"),
    ("Could not resolve authentication method", "The writing service had no key, so nothing was written"),
    ("billing limit reached", "The picture service's spending limit was reached, so no concepts were drawn"),
    ("Request not allowed", "The writing service refused the request"),
    ("Error code: 403", "The writing service refused the request"),
    # the clean-up of 2026-10-04 (E8): a design started on the removed pre-2A path, refused by name
    ("PRE_2A_BRIEF_RETIRED", "It was started before directions were planned, and that old way of running it was "
                             "removed — start a new design from its brief"),
)
_PLANNING_PREFIX = "Direction planning failed validation:"


def direction_check_words(code) -> str:
    """One failed check of a direction set, in words; a check index ("…:direction[1]") is dropped — the words name
    what went wrong, not where in the record."""
    head = str(code or "").strip().split(":", 1)[0]
    # [his goal of 2026-10-13, (1)] every check its words — never its code with the underscores taken out
    return DIRECTION_CHECK_WORDS.get(head) or check_words(head) or FAULT_REASON


def _planning_attempts(task):
    """How many times the planner wrote its three directions on its last run — that run's own record ("generation
    metadata"), or None where it has none."""
    if task.pk is None:
        return None
    from apps.pipeline.models import AgentLog
    payload = (AgentLog.objects.filter(task_id=task.pk, action="Creative Director: generation metadata")
               .order_by("-timestamp", "-pk").values_list("payload", flat=True).first())
    return payload.get("attempts") if isinstance(payload, dict) else None


#: [His test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 3: "Errors are shown to me in words, never
#: engine codes (this one was raw codes again)."] the concept step's own checks, in words — each failed check of the
#: instructions written for the three concept pictures
CONCEPT_CHECK_WORDS = {
    "CONTAINER_VARIATION_IDENTITY_MISSING": "the three concepts were not each named for their direction",
    # [his goal of 2026-10-10, item 1] shown now, bound to the directions by their order
    "PROMPTS_NOT_BOUND_TO_DIRECTIONS": "the three concepts were not each matched to their direction, so they are "
                                       "matched in order",
    "CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT": "the three concepts were too alike",
    "VARIATION_PROMPTS_NOT_DISTINCT": "the three concepts were too alike",
    "CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED": "the answer came back incomplete",
    # [his goal of 2026-10-13, (1)] keyed by the codes the step records (gate1_prompts.GATE1_PROMPTS_*), never by the
    # names of the constants that hold them — keyed so, a concept stop was said with no reasons
    "PROMPT_ENGINEER_SCHEMA_MISMATCH": "the answer came back incomplete",
    "PROMPT_ENGINEER_EMPTY_RESPONSE": "the answer came back empty",
    "PROMPT_ENGINEER_OUTPUT_PARSE_FAILURE": "the answer could not be read",
}
_CONCEPT_PREFIX = "Gate-1 variation contract not satisfied"
#: an engine code — capitals joined by underscores — or the record's own markers: never shown to him
_ENGINE_TEXT = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b|§|Traceback|\bNone\b|[\[\]{}]|\.py\b|Error\b")
#: the record's own words for a stop that are words already, in a designer's words
PLAIN_STOP_WORDS = (
    ("Image Producer generated no images on rerun", "Drawing the concepts again made no picture"),
    ("Image Producer generated no images", "The picture service drew no concept picture"),
    ("Prompt Engineer produced", "The instructions for the concept pictures did not come back as three"),
    ("No current images to regenerate from", "There were no concept pictures to draw again from"),
    ("No dieline job linked to this output", "The carton's die was missing from its record"),
    ("persisted design intent failed validation", "The saved design plan failed its own check, so no picture was drawn"),
)


def concept_check_words(code) -> str:
    """One failed check of the concept step, in words."""
    head = str(code or "").strip().split(":", 1)[0].strip()
    return CONCEPT_CHECK_WORDS.get(head) or check_words(head)


#: [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (2): "Every "not
#: distinct" check: it never stops a design. On failure it retries once with the reason; if it still fails, it shows me
#: the three anyway with a note, and I choose."]
#: The record each note beside the three is read from — the planning's own line and the concept step's — what it names,
#: and its checks' words.
#: [his goal of 2026-10-10, item 1] the concept step's own "too alike" checks, said as "too alike" as the planner's are
CONCEPT_ALIKE_CODES = ("CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT", "VARIATION_PROMPTS_NOT_DISTINCT")
ALIKE_NOTE_SOURCES = (
    (("ARIA: structured directions validated",), "the three directions", direction_check_words),
    # [his goal of 2026-10-10, item 1] … and the prompts bound to the directions by their order
    (("Gate-1 variation contract result", "Gate-1 prompts: generation result", "Gate-1 prompts: bound by order"),
     "the instructions for the three concept pictures", concept_check_words),
)


def _alike_sentence(step, reasons, note) -> str:
    """One note, saying what happened: too alike on both attempts; too alike, then another check failed when made once
    more (the first three shown); another check failed, then too alike; or too alike on the one attempt made.
    [His goal of 2026-10-10, item 1: "it shows me the three directions with a plain note"] a set refused by any other
    check says so in the same plain words: they failed their checks, why, and that they are shown for him to choose."""
    from apps.pipeline.direction_signature import alike_code
    said = " — " + "; ".join(reasons) if reasons else ""
    alike_at = [int(n) for n in note.get("alike_attempts") or []]
    made = int(note.get("attempts") or len(alike_at))
    if not all(alike_code(code) or str(code).split(":", 1)[0].strip() in CONCEPT_ALIKE_CODES
               for code in note.get("codes") or []):
        if len(alike_at) >= 2:
            how = "failed their checks twice%s; made once more with that reason, they still did" % said
        elif made >= 2 and alike_at == [1]:
            how = ("failed their checks%s; made once more, the answer could not be read, so the first three are "
                   "shown" % said)
        elif made >= 2:
            how = "could not be read the first time, then failed their checks%s when made once more" % said
        else:
            how = "failed their checks%s" % said
        return "Shown anyway: %s %s. You choose." % (step, how)
    if len(alike_at) >= 2:
        how = "came back too alike twice%s; made once more with that reason, they did not change" % said
    elif made >= 2 and alike_at == [1]:
        how = ("came back too alike%s; made once more, they failed another of its checks, so the first three are "
               "shown" % said)
    elif made >= 2:
        how = "failed another of its checks, then came back too alike%s when made once more" % said
    else:
        how = "came back too alike%s" % said
    return "Shown anyway: %s %s. You choose." % (step, how)


def alike_words(task) -> list:
    """The note beside three concepts shown though a "not distinct" check still refused them after its one retry — one
    sentence for each step that did, read from that step's latest record; [] for every other design, and once he has
    chosen."""
    if task.pk is None or task.status != "awaiting_gate_1":
        return []
    from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
    from apps.pipeline.models import AgentLog
    from django.db.models import Q
    notes = []
    for actions, step, words_of in ALIKE_NOTE_SOURCES:
        which = Q()
        for action in actions:
            which |= Q(action__startswith=action)
        payload = (AgentLog.objects.filter(which, task_id=task.pk)
                   .order_by("-timestamp", "-pk").values_list("payload", flat=True).first())
        note = payload.get(SHOWN_ALIKE_KEY) if isinstance(payload, dict) else None
        if not isinstance(note, dict) or not note.get("codes"):
            continue
        reasons = []
        for code in note["codes"]:
            said = words_of(code)
            if said and said not in reasons:
                reasons.append(said)
        notes.append(_alike_sentence(step, reasons, note))
    return notes


def reason_words(text, task=None) -> str:
    """[His test findings on design 121, item 3] a stop's reason in a designer's words — never an engine code. The record
    keeps its own text; this is what he is shown: the words written for it, else, where the reason has none, the step it
    stopped on, in words (``step_times.last_step``), with its codes left in the record."""
    text = str(text or "").strip()
    if not text:
        return "It stopped with no reason recorded"
    if text.startswith(_PLANNING_PREFIX):
        seen = []
        for code in text[len(_PLANNING_PREFIX):].split(";"):
            words = direction_check_words(code)
            if words and words not in seen:
                seen.append(words)
        if task is not None and _planning_attempts(task) == 2:
            return "It wrote the three directions twice, and both failed its own checks: " + "; ".join(seen)
        return "The three directions it wrote failed its own checks: " + "; ".join(seen)
    if text.startswith(_CONCEPT_PREFIX):
        seen = []
        for code in re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", text):
            words = concept_check_words(code)
            if words and words not in seen:
                seen.append(words)
        return ("It stopped before drawing: the instructions for the three concept pictures failed their own checks "
                "twice" + (" — " + "; ".join(seen) if seen else "") + ". No concept picture was drawn")
    for needle, words in STOP_MESSAGE_WORDS + PLAIN_STOP_WORDS:
        if needle in text:
            return words
    if not _ENGINE_TEXT.search(text):
        return text
    # [his goal of 2026-10-13, (1): "Every check has its words written"] a check it names is said in its words; what
    # names none is not a check — a fault of the system itself, said as one, with the step it was on
    said = [w for w in dict.fromkeys(check_words(c) for c in _CODE.findall(text)) if w]
    from apps.pipeline.step_times import last_step_words
    step = last_step_words(task) if task is not None else ""
    if said:
        return ("It stopped while %s: %s" % (step[:1].lower() + step[1:], "; ".join(said)) if step
                else "It stopped: " + "; ".join(said))
    if step:
        return "It stopped while %s: %s" % (step[:1].lower() + step[1:], FAULT_WORDS)
    return "It stopped: " + FAULT_WORDS


#: [His test blocker on design 122 at reconstruction, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md), item 3: "The stop reason
#: must be shown in plain words on the page, never only codes in a fold."] why a drawing stopped, check by check, in
#: words — each says what the check wants and what it found missing; keyed by the record's codes, with or without their
#: CONTAINER_ head
DRAWING_STOP_WORDS = {
    "PRODUCT_NAME_TOO_SMALL": "the product name was not drawn on the front as the name, or it was drawn smaller than "
                              "the print floor allows",
    "PRODUCT_NAME_NOT_DOMINANT": "the product name does not span the front as the concept sets it",
    "TYPOGRAPHY_HIERARCHY_FAILED": "no line on the front carries the product name, or the name is not the largest type",
    "FRONT_BACK_RELATIONSHIP_FAILED": "the front does not carry the hero — neither the product name nor the concept's "
                                      "motif — or the back carries the hero motif",
    "PRODUCT_NAME_ZONE_MISMATCH": "the product name is not where the concept places it",
    "LOGO_ZONE_MISMATCH": "the logo is not where the concept places it",
    "LOGO_SCALE_MISMATCH": "the logo is not the size the concept shows",
    "MOTIF_FAMILY_MISMATCH": "the motif drawn is not the kind the concept shows",
    "MOTIF_MISSING": "the concept's motif was not drawn",
    "MOTIF_DENSITY_FAILED": "the motif is drawn sparser or denser than the concept shows",
    "MOTIF_POSITION_FAILED": "the motif is not where the concept places it",
    "MOTIF_COVERAGE_FAILED": "the motif covers more or less of the front than the concept shows",
    "MOTIF_CONTINUATION_FAILED": "the motif does not run on round the product as the concept shows",
    "MOTIF_COLOR_RELATIONSHIP_FAILED": "the motif's colours do not sit together as the concept's do",
    "MOTIF_SCALE_DISTRIBUTION_FAILED": "the motif's large and small pieces are not spread as the concept shows",
    "CAP_BODY_COORDINATION_FAILED": "the cap and the body do not go together as the concept shows",
    "WRAP_ALIGNMENT_FAILED": "the artwork does not meet itself where it wraps round",
    "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED": "the concept's motif cannot be drawn as clean lines yet — a person must "
                                             "look at it",
    "DECORATION_OUTSIDE_ZONE": "some artwork runs outside the print area you confirmed",
    "ZONE_SAFE_MARGIN_VIOLATION": "some artwork sits inside the safe margin of its print area",
    "ARTWORK_SURFACE_MISMATCH": "some artwork was placed on another surface than its print area's",
    "WRAP_SEAM_CONFLICT": "some artwork crosses the seam where the print wraps round",
    "CAP_BODY_ZONE_CONFLICT": "the cap's and the body's print areas overlap",
    "DECORATION_COVERAGE_EXCEEDED": "the artwork covers more of its print area than its print method allows",
    "SURFACE_PROJECTION_REVIEW_REQUIRED": "a print area lies on a curve the drawing cannot lay flat yet — a person must "
                                          "look at it",
    "ZONE_SAFE_MARGIN_AS_PICTURED": "some artwork sits inside its print area's safe margin, where the concept picture "
                                    "prints it",
    "ASPECT_RATIO_FIDELITY_FAILED": "the drawn shape's proportions are not the concept's",
    "SILHOUETTE_GEOMETRY_MISMATCH": "the drawn outline is not the concept's",
    "CAP_GEOMETRY_FIDELITY_FAILED": "the cap's shape is not the concept's",
    "MATERIAL_RELATIONSHIP_FAILED": "the materials do not sit together as the concept shows",
    "TRANSPARENCY_RELATIONSHIP_FAILED": "what shows through the material is not as the concept shows",
    "GENERIC_LABEL_FALLBACK_USED": "a plain label was drawn in place of the concept's front",
    "CYLINDRICAL_FORM_NOT_PRESERVED": "the round form was not kept",
    "COLLAR_SCALE_MISMATCH": "the collar is not the size the concept shows",
    "BULB_PROPORTION_FAILED": "the dropper's bulb is not in the concept's proportion",
    "NECK_CONNECTION_FAILED": "the neck does not join the body as the concept shows",
    "GLASS_CURVATURE_FAILED": "the glass does not curve as the concept's does",
    "PRODUCT_FILL_LEVEL_MISINTERPRETED": "the product's fill level was read wrongly",
    "SELECTED_TYPOGRAPHY_NOT_PRESERVED": "the concept's lettering was not kept",
    "SHOULDER_GEOMETRY_FAILED": "the shoulder's shape is not the concept's",
    "NECK_GEOMETRY_MISSING": "the neck is missing",
    "COLLAR_GEOMETRY_FIDELITY_FAILED": "the collar's shape is not the concept's",
    "COLLAR_MATERIAL_FIDELITY_FAILED": "the collar's material is not the concept's",
    "BULB_GEOMETRY_FIDELITY_FAILED": "the bulb's shape is not the concept's",
    "CLOSURE_PROPORTION_FAILED": "the closure is not in the concept's proportion",
    "FROSTED_GLASS_VISUALIZATION_FAILED": "the frosted glass is not shown as the concept shows it",
    "CONCEPT_SHEET_PRESENTATION_FAILED": "the sheet does not show the product as the concept does",
    "RECONSTRUCTION_DISPATCH_FAILED": "the drawing could not be sent to be drawn, so nothing was drawn — draw it again",
    # [his test finding on design 122's drawing, 2026-10-08, A and B]
    "FLAT_MOTIF_NOT_MADE": "the motif's flat artwork could not be made, so the motif was not drawn — it is never traced "
                           "from the concept photo",
    "MOTIF_STROKES_BROKEN": "the motif's traced strokes are broken or in fragments",
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "never printed broken"]
    "MOTIF_TRACE_BROKEN": "a motif traced from the concept photo came out broken and has no clean flat redraw to draw "
                          "it from, so it is left out — it is never printed broken",
    "COLOUR_DRIFTS_FROM_CONCEPT": "a colour drawn drifts from the concept's, past what an eye accepts (ΔE above 6)",
}
#: [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "Every check has its words written; a check without words
#: fails the wiring check."] the checks no table here had words for — measured over every check code the engine's
#: check modules declare (apps/ire/tests/test_compose.py holds that none is without words)
MORE_CHECK_WORDS = {
    # [his goal of 2026-10-13, (1) and (2)] the layout picture not made (its spending held at $0, a cap, the service)
    "CARTON_LAYOUT_PICTURE_NOT_MADE": "the carton's layout picture was not made, so its back, sides and flaps continue "
                                      "its front",
    "BRAND_STRING_ARTEFACT_WITHHELD": "the drawing carries brand words nobody has confirmed, so its files were held "
                                      "back",
    "BRAND_STRING_PROVISIONAL": "a brand word on the drawing is provisional — not yet confirmed as the brand's",
    "CARTON_FRONT_COPY_EXCEEDS_PANEL": "the front's copy runs past its panel",
    "CARTON_FRONT_INSIDE_SAFE_MARGIN": "the front's copy sits inside the safe margin",
    "CARTON_FRONT_COPY_NOT_READY": "the front's copy does not fit its panel at the smallest print size",
    "CARTON_LABEL_DOES_NOT_FIT": "the back label does not fit its panel at the smallest print size",
    "CARTON_LABEL_NOT_TRILINGUAL": "the back label is not in all three languages",
    "CONTAINER_LABEL_NOT_TRILINGUAL": "the label is not in all three languages",
    "CONTAINER_ARCHETYPE_OUT_OF_SCOPE": "the product's form is not one the drawing can make yet",
    "CONTAINER_ARCHETYPE_UNRESOLVED": "the product's form could not be told from the brief and the concept",
    "CONTAINER_BACK_COPY_DOES_NOT_FIT_THIS_BODY": "the back copy does not fit on this product's back",
    "CONTAINER_COLOUR_SOURCES_UNREAD": "where each colour drawn came from could not be read",
    "CONTAINER_DRAWING_SOURCE_UNKNOWN": "the record does not say what the product's shape was drawn from",
    "CONTAINER_LEARNED_SHAPE_MISSING": "the shape learned from the concept is not on record",
    "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA": "the front copy runs past the safe area",
    "CONTAINER_FRONT_COPY_EXCEEDS_ZONE": "the front copy runs past its print area",
    "CONTAINER_LID_ART_NOT_MADE": "the lid's illustration could not be redrawn flat",
    "CONTAINER_LID_ART_NOT_REGISTERED": "the lid's flat redraw does not stand where the concept draws it",
    "CONTAINER_LID_ART_NOT_TRACED": "the lid's flat redraw could not be traced",
    # [his goal for the pitch, 2026-10-15, B (5)] the designer's eye, the drawing beside its concept
    "DESIGNERS_EYE_DIFFERS": "the designer's eye sees the drawing differ from its concept",
    "CONTAINER_FACE_ART_NOT_DRAWN": "the product's printed face was drawn from its map alone, not from its flat redraw",
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "mark it "not confirmed — please check" beside Approve"]
    "LABEL_COPY_NOT_CONFIRMED": "a piece of the label was written for the product type — not confirmed, please check",
    "CONTAINER_NAME_WIDER_THAN_ITS_FRONT": "the product name is wider than the front at the smallest size it may print",
    "CONTAINER_NATIVE_RECONSTRUCTION_FAILED": "the drawing did not pass its own checks",
    "CONTAINER_RECONSTRUCTION_ABSENT": "the design has not been drawn yet",
    "CONTAINER_TYPE_DIFFERS": "the brief names another form than the one chosen",
    "CONTAINER_TYPE_QUESTION": "the brief names two forms, and which one it is was not said",
    "GLOSS_CONTAINER_QUESTION": "the brief's gloss could be a wand vial or a squeeze tube, and which was not said",
    "M3_FIT_OUTLINE_TOP_UNRESOLVED": "the top of the product's outline could not be found",
    "M3_FIT_BACKBONE_REQUIRED": "the product's measured outline is not on record",
    "VQR1_M3_GEOMETRY_DRIFT": "the product's drawn shape drifted from the confirmed one",
    "SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED": "the drawing is not true enough to the concept you chose",
    "SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED": "the chosen concept's own name is missing from its record",
    "DESIGN_MAP_NO_FACE": "the product's front could not be found in the concept picture",
    "DESIGN_MAP_NO_PRODUCT": "the product could not be found in the concept picture",
    "DESIGN_MAP_PARTS_UNREAD": "the concept picture's parts could not be read",
    "DESIGN_MAP_STOP": "a part of the concept cannot be drawn as it stands",
    "DESIGN_SHAPES_REFUSED": "the concept's shapes could not be traced",
    "DISPLAY_STAND_UNIT_UNSIZED": "the display's product has no size on record, so its tray is not sized to it",
    "DIRECTIONS_NOT_DISTINCT": "the directions were too alike",
    "DOCUMENT_NOT_CANONICAL": "the saved design plan was not written the way it is kept",
    "UNSUPPORTED_SCHEMA_VERSION": "the saved design plan is in a form this system no longer reads",
    "DUPLICATE_ACTIVE_GENERATION": "concept pictures were already being drawn for this design",
    "PRODUCTION_USE_NOT_PERMITTED": "a reference may not be used to make production artwork",
    "VARIATION_DIVERSITY_GATE_FAILED": "the concept pictures' instructions were too alike to draw",
    "VARIATION_REFERENCE_ASSIGNMENT_MISMATCH": "a concept's references are not the ones assigned to it",
    "VARIATION_REFERENCE_FILE_MISSING": "a reference picture's file is missing",
    "VARIATION_REFERENCE_NOT_APPROVED": "a reference was used that was not approved",
    "VARIATION_REFERENCE_PLAN_MISMATCH": "a concept's references do not follow their plan",
    "VARIATION_REFERENCE_SET_EXPANDED": "more references were used than were approved",
    "VARIATION_REFERENCE_SET_REDUCED": "fewer references were used than were approved",
    "GATE1_PROMPT_PLAN_CHECKPOINT_INVALIDATED": "the concepts' plan changed after it was saved, so it was made again",
    "OPENAI_IMAGE_BILLING_CONFIRMED_BY_OWNER_REQUIRED": "the picture service's billing must be confirmed by you first",
    "PROVIDER_CALL_BUDGET_EXCEEDED": "this design's spending cap was reached",
    "DIELINE_FOLD_CHECK_FAILED": "the die did not fold up cleanly in its check",
    "DIMENSION_COMBINATION_UNSUPPORTED": "the carton's sizes are not a combination its die can make",
    "ARTWORK_NOT_READY": "a piece of the artwork has not passed its own checks",
    "PRODUCTION_NOT_READY": "the design is not ready for production",
    "SPEC_STALE_REDERIVE_REQUIRED": "its checks were made before today's rules — it is drawn again to be approved",
    "GATE_2_NOT_READY": "the drawing is not finished, so it cannot be approved yet",
    "RECONSTRUCTION_ARTIFACT_INVALID": "the drawing's file is missing or damaged",
    "RECONSTRUCTION_FAILED": "the drawing did not finish",
    "RECONSTRUCTION_STATUS_INCONSISTENT": "the drawing's records disagree with each other",
    "RECONSTRUCTION_WORKER_FAILED": "the drawing step stopped before it finished",
    "UNDECLARED_READINESS_SECTION": "a readiness check reported in a place nobody declared",
    "FONT_USAGE_UNRECONCILED": "the faces drawn have not been reconciled with the granted ones",
    "AWAITING_OWNER_RULING": "the back copy waits for your ruling",
    "REVIEW_REQUIRED": "the concept's motif needs a person to look at it",
    "NOT_DRAWN": "a finish asked for was not drawn",
    "REFUSED_NO_VECTOR_MASTER": "a foil on the mark needs the mark's vector master, which is not on file",
    "EVOKED_NOT_SPECIFIED": "the brief's words suggest a finish without naming it, so none is made",
    "NOT_ASKED": "a finish nobody asked for, so no plate is made for it",
    "NATIVE_AI_DROPS_ELEMENTS": "the layered Illustrator file left out pieces the drawing has",
    "APPROVED_VISUAL_REFERENCES_REQUIRED": "drawing the concepts again with references needs references you approved",
    "APPROVED_REFERENCE_FILE_MISSING": "an approved reference picture's file is missing",
    "REFERENCE_APPROVAL_SET_CHANGED": "the approved references changed while the concepts were being drawn",
    "REFERENCE_INFLUENCE_PLAN_MISMATCH": "the references used do not follow the plan for how they shape the concepts",
    "UNAPPROVED_VISUAL_REFERENCE_USED": "a reference nobody approved was about to be used",
    "REFERENCE_CONTENT_UNAVAILABLE": "a reference's picture could not be read",
    # [his goal of 2026-10-13, (1)] what held Gate 2 by code until then, said beside Approve now
    "ARTWORK_COPY_EXCEEDS_BOX": "a piece's copy runs past its box",
    "ARTWORK_COPY_NOT_DRAWN": "a piece's copy was not drawn",
    "ARTWORK_HEADLINE_IS_THE_BRIEF_LINE": "a piece's headline is only the brief's first line, not a name",
    "ARTWORK_HEADLINE_MISSING": "a piece has no headline",
    "ARTWORK_KEY_VISUAL_MISSING": "a piece has no key visual",
    "ARTWORK_LOGO_BELOW_MINIMUM_SIZE": "the logo is smaller than its least size on a piece",
    "ARTWORK_LOGO_NOT_PLACED": "the logo could not be placed on a piece",
    "VQ_ARTIFACT_AUTHORITY_FAILED": "the editable file is missing or not whole",
    "VQ_ARTBOARD_NOT_PRODUCT_DERIVED": "the artboard was not sized from the product",
    "VQ_ARTBOARD_UNRELATED_TO_PRODUCT": "the artboard does not fit the product",
    "VQ_ARTBOARD_UNMEASURED": "the artboard's fit to the product was not measured",
    "VQ_SILHOUETTE_DIVERGENT": "the product's outline does not match the concept's",
    "VQ_SILHOUETTE_COMPARISON_UNAVAILABLE": "the product's outline could not be compared with the concept's",
    "VQ_CLOSURE_FAMILY_MISMATCH": "the closure is not the kind the concept shows",
    "VQ_CLOSURE_STRUCTURE_UNMEASURED": "the closure's build was not measured",
    "VQ_FRONT_ARTWORK_UNRESOLVED_PLACEHOLDER": "the front still carries a stand-in where its artwork belongs",
    "VQ_FRONT_ARTWORK_UNMEASURED": "the front artwork was not measured",
    "VQ_LOGO_METRICS_UNMEASURED": "the logo's size and place were not measured",
    "VQ_LOGO_DEFECTIVE": "the logo is drawn wrongly — its size, its place or its shape",
    "VQ_TYPOGRAPHY_METRICS_UNMEASURED": "the lettering was not measured",
    "VQ_TYPOGRAPHY_DEFECTIVE": "the lettering is drawn wrongly — its size, its order or its overlap",
    "VQ_COMPOSITION_COMPARISON_UNAVAILABLE": "the composition could not be compared with the concept's",
    "VQ_COMPOSITION_DEFECTIVE": "the composition does not hold together as the concept's does",
    "VISUAL_QUALITY_GATE_FAILED": "the drawing did not pass its visual-quality check",
    "BLOCKED_VISUAL_QUALITY": "the drawing did not pass its visual-quality check",
    "VISUAL_QUALITY_NOT_FULLY_MEASURED": "the drawing's visual quality was not measured in full",
}
#: the capitalised values those check modules declare that are NOT checks — states, roles, sources, surfaces and
#: retries a record carries; never shown as a reason (the same test holds every other one has its words)
NOT_A_CHECK = frozenset({
    "AI_SOURCE_OF_TRUTH", "PNG_PREVIEW_ONLY", "RESUME_EXISTING_CONFIRMED_PROFILE", "RETRYABLE_RECONSTRUCTION_INCONSISTENCY",
    "STALE_SPEC_REDERIVATION", "MEASURED_PASS", "MEASURED_FAIL", "NOT_APPLICABLE", "UNMEASURED_BLOCKING",
    "OWNER_CALIBRATED", "NOT_REVIEWED", "REVISION_REQUIRED", "BODY_FRONT", "TRAY_INSERT", "FRONT_DIRECT_PRINT",
    "CONFIRMED_CONTAINER_PROFILE", "CONFIRMED_FRONT_ZONE", "LOCAL_IMAGE_ANALYSIS", "SELECTED_VARIATION_PROMPT",
    "SELECTED_VARIATION_RECORD", "DESCRIPTIVE_REFERENCE_ONLY", "M3_FIT", "CAP_FRONT", "CAP_BACK", "CAP_WRAP",
    "BODY_BACK", "BODY_WRAP", "CRIMP_ZONE", "BODY_LEFT", "BODY_RIGHT", "BODY_BASE", "LID_EDGE",
    "INFERRED_NONAUTHORITATIVE", "VISUAL_QUALITY_PASSED",
    # [his last goal before the pitch, 2026-10-16, Step 1 (1)] the system's own notes, said once as one sentence
    # (gate2_problems.INTERNAL_WORDS) — the name of that row, never a check
    "SYSTEM_NOTES",
})
#: [his goal of 2026-10-13, (1) and (5)] a check's detail that names the fact it found missing, in words — beside Approve
#: "the printed information is incomplete — product name present" read as its opposite
DETAIL_WORDS = {
    "product_name_present": "the product's name is not given",
    "sku_present": "no SKU is given",
    "code_zone_confirmed": "no place for the batch code is confirmed",
    # a label's languages, as a check names them
    "en": "English", "es": "Spanish", "ar": "Arabic",
}


#: [his goal of 2026-10-13, (1)] what stops a design that is no check of it: a fault of the system itself
FAULT_WORDS = ("a fault in the system itself, not one of the design's checks — its details are kept in the design's "
               "record; resuming runs that step again")
FAULT_REASON = "a fault in the system itself, not one of the design's checks"


def check_words(code) -> str:
    """[His goal of 2026-10-13, (1).] One check in its words, wherever they are written — "" for a code with none (the
    test holds that every check code the engine declares has them). A detail after its colon is not the code."""
    head = str(code or "").strip().split(":", 1)[0].strip()
    if not head or head in NOT_A_CHECK:
        return ""
    bare = head[len("CONTAINER_"):] if head.startswith("CONTAINER_") else head
    axis = re.fullmatch(r"VQ_(.+)_(MISSING|FAILED|UNMEASURED)", head)
    if axis and head not in MORE_CHECK_WORDS and VQ_AXIS_WARNING_WORDS.get(axis.group(1).lower()):
        # the visual-quality check's own axis codes (VQ_<axis>_FAILED …), said by their axis
        return "%s — %s" % (VQ_AXIS_WARNING_WORDS[axis.group(1).lower()],
                            {"MISSING": "not measured", "FAILED": "it did not pass",
                             "UNMEASURED": "not measured yet"}[axis.group(2)])
    for table in (MORE_CHECK_WORDS, DIRECTION_CHECK_WORDS, CONCEPT_CHECK_WORDS, READINESS_WORDS,
                  PRODUCTION_NOTE_WORDS, ACCEPTANCE_WARNING_WORDS, CODE_PLACE_NOTE_WORDS):
        if head in table:
            return table[head]
    return DRAWING_STOP_WORDS.get(bare) or DRAWING_STOP_WORDS.get(head) or ""


#: a record's head code — what failed, never why — said once above the reasons, never as one of them
_DRAWING_STOP_HEADS = ("CONTAINER_NATIVE_RECONSTRUCTION_FAILED", "SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED",
                       "RECONSTRUCTION_FAILED")
_CODE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")


def drawing_stop_reasons(text, task=None) -> list:
    """[His test blocker on design 122 at reconstruction, 2026-10-08, item 3.] Each reason a drawing stopped, in words,
    in the record's order, once each: the words written for each check it names (``DRAWING_STOP_WORDS``); a check with
    none yet said as one, never by its code; a reason the record wrote in words already, in a designer's words
    (``reason_words``). Empty where nothing stopped it."""
    text = str(text or "").strip()
    if not text:
        return []
    # [his goal of 2026-10-13, (1)] a check's code is said in its words; a capitalised name that is no check (a print
    # area's, CAP_FRONT, in a containment's detail) is never read as one
    codes = [c for c in _CODE.findall(text) if c not in _DRAWING_STOP_HEADS and c not in NOT_A_CHECK]
    if not codes and "SELECTED_CONTAINER_CONCEPT_FIDELITY_FAILED" in text:
        return ["the drawing is not true enough to the concept you chose"]
    said = [check_words(c) for c in codes]
    if not any(said):
        return [reason_words(text, task)]
    out = []
    for words in said:
        if words and words not in out:
            out.append(words)
    return out


def stop_words(task) -> str:
    """Why a stopped design stopped, in a designer's words. With nothing recorded, it says so. [His test findings on
    design 121, 2026-10-07, item 3: "Errors are shown to me in words, never engine codes."] a reason with no words
    written for it is put into words (``reason_words``) — it was shown as the record writes it, codes and all; the record
    keeps its own text."""
    text = (getattr(task, "error_message", "") or "").strip()
    if not text and task.pk is not None:
        # no error recorded on the design: its own last failure line, as the log wrote it ("… failed — <why>")
        from apps.pipeline.models import AgentLog
        line = (AgentLog.objects.filter(task_id=task.pk, action__icontains="failed —").order_by("-timestamp")
                .values_list("action", flat=True).first())
        if line is not None and "failed —" in line:              # the query ignores case; the split does not
            text = line.split("failed —", 1)[1].strip().strip('"')
    # his test day finding 1, 2026-09-29: "It stops only if it fails again, and says why in plain words" — a planning
    # stop says how many times it tried, from its own record of the run (generation metadata), in ``reason_words``
    return reason_words(text, task)


def intent_row_words(row: dict) -> dict:
    """One field of a palette's reading in words: what it is, how binding, where it stands, how it was read, and how sure
    the reading is — the record's own codes kept beside, for what the form posts and for the folded record."""
    confidence = row.get("confidence")
    understood = row.get("understood")
    if isinstance(understood, str) and re.fullmatch(r"[A-Z]{3,}(?:_[A-Z]+)*", understood):
        understood = understood.replace("_", " ").lower()             # a value the reading names as a code: "top edge"
    elif isinstance(understood, str) and understood.startswith("ConceptReference:") and " — " in understood:
        understood = re.sub(r"\s*\([^)]*\)\s*$", "", understood.split(" — ", 1)[1])   # what it is, not its file
    return dict(row, field_words=str(row.get("field") or "").replace("_", " ").capitalize(), understood_words=understood,
                level_words=_words(INTENT_LEVEL_WORDS, row.get("level")) if row.get("level") else "",
                state_words=_words(INTENT_STATE_WORDS, row.get("state")),
                method_words=_words(INTENT_METHOD_WORDS, row.get("extraction_method"))
                if row.get("extraction_method") else "",
                sure=f"{round(float(confidence) * 100)}%" if confidence is not None else "")

