"""Design Intent contract — Phase 2A-1 (`design_intent/1.0`).

A pure, versioned, deterministic contract between a cosmetics design brief and the three
design directions a user chooses from BEFORE any image is generated. Today the Creative
Director's directions exist only as loose JSON that flows straight into image generation;
the user first sees them next to already-rendered images. This contract makes the reasoning
step a first-class, inspectable artifact: brief in → intent + three directions out → the
user picks one → only then does the existing PromptEngineer/Gate-1 path run.

Design rules the contract enforces (not merely documents):

* **Bounded everywhere.** Every field is bounded text, a bounded list, or a closed
  vocabulary. Unknown fields are refused, never ignored — a misspelled field is a bug the
  caller should hear about, and "extra" fields are how hidden chain-of-thought would leak.
* **Exactly three directions, structurally distinct.** Distinct names, distinct design
  axes, distinct layout structures and distinct color systems. Three colorways of one
  layout fail validation; semantic distinctness beyond structure is the generator's job.
* **DIP references are descriptive only.** A direction may cite corpus items as context,
  but every reference carries the DESCRIPTIVE_REFERENCE_ONLY label plus its provenance
  (machine-derived vs human-verified) and a blocked flag. A blocked or rights-unreviewed
  reference is never a production input, and the contract has no field through which an
  asset could be "attached" — only described.
* **No authority.** Nothing here creates a permission, a DecisionEvent, an assertion or a
  governance state. It is a plain data contract.

Pure module: no Django models, no I/O, no LLM call. The generator (2A-2), the DIP context
adapter (2A-3) and the UI (2A-4) all build to this contract; none of them define it.
"""
from __future__ import annotations

# 1.0 is the exact Phase 2A-1 contract, FROZEN below; 1.1 is the richer Phase 2A-2 shape
# (audience interpretation on the intent; the expanded direction card with prompt_seed
# replacing image_prompt). Silently mutating 1.0's meaning was the mistake CORR-1 fixes.
DESIGN_INTENT_SCHEMA_V1_0 = "design_intent/1.0"
#: 1.1 is FROZEN as it was written: its documents validate exactly as they did (the resume path and direction selection
#: re-validate a persisted plan against its OWN declared version).
DESIGN_INTENT_SCHEMA_V1_1 = "design_intent/1.1"
#: §BH68(a): 1.2 = 1.1 plus each direction's DECLARED hierarchy family, from the known set. Nothing else changed.
DESIGN_INTENT_SCHEMA = "design_intent/1.2"

# --- bounds -----------------------------------------------------------------------
MAX_TEXT = 2000
MAX_SHORT = 200
MAX_LIST = 12
MAX_LIST_TEXT = 200
DIRECTION_COUNT = 3
MAX_DIP_REFERENCES = 8
MAX_UNRESOLVED_QUESTIONS = 8

#: Mirrors `apps.pipeline.targets.base.DesignTarget` values. Mirrored as literals so this
#: module stays importable without Django; a test asserts the two never drift.
DESIGN_TARGETS = (
    "product_container", "packaging", "palette", "complete_product",
    "gift_set", "display_stand", "marketing_material",
    "exhibition_booth", "social_media",
)

CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")

#: Provenance a DIP reference must declare. There is no "approved" value: approval is a
#: governance concept and unexpressible here.
REFERENCE_SOURCES = ("MACHINE_DERIVED", "HUMAN_VERIFIED")
REFERENCE_LABEL = "DESCRIPTIVE_REFERENCE_ONLY"

# --- brief (input) ----------------------------------------------------------------
BRIEF_REQUIRED_FIELDS = ("brand", "product_name", "product_category", "design_target")
BRIEF_OPTIONAL_FIELDS = (
    "audience", "market", "dimensions", "required_copy", "preferred_styles",
    "preferred_colors", "prohibited_colors", "prohibited_motifs", "references",
    "production_constraints",
)
BRIEF_FIELDS = BRIEF_REQUIRED_FIELDS + BRIEF_OPTIONAL_FIELDS
_BRIEF_LIST_FIELDS = frozenset({
    "required_copy", "preferred_styles", "preferred_colors", "prohibited_colors",
    "prohibited_motifs", "references", "production_constraints",
})

# --- intent (output) --------------------------------------------------------------
INTENT_TEXT_FIELDS = (
    "visual_objective", "audience_interpretation", "hierarchy", "focal_point",
    "composition", "typography_strategy", "color_strategy", "motif_strategy",
    "imagery_strategy", "material_finish_direction", "target_structural_guidance",
)
INTENT_LIST_FIELDS = ("originality_constraints", "forbidden_choices",
                      "unresolved_questions", "source_references")
INTENT_FIELDS = (("schema_version", "brief", "confidence")
                 + INTENT_TEXT_FIELDS + INTENT_LIST_FIELDS + ("directions",))

# --- frozen design_intent/1.0 field sets (Phase 2A-1, verbatim) ---------------------
V1_0_INTENT_TEXT_FIELDS = (
    "visual_objective", "hierarchy", "focal_point", "composition",
    "typography_strategy", "color_strategy", "motif_strategy", "imagery_strategy",
    "material_finish_direction", "target_structural_guidance",
)
V1_0_DIRECTION_TEXT_FIELDS = (
    "name", "concept_statement", "design_axis", "layout_structure", "color_system",
    "typography", "graphic_elements", "product_target_fit", "image_prompt",
    "risks", "originality_notes",
)
V1_0_DIRECTION_DISTINCT_FIELDS = ("name", "design_axis", "layout_structure",
                                  "color_system")

# --- direction (design_intent/1.1) --------------------------------------------------
# 1.1 is the full user-facing reasoning card; the final image prompt belongs to
# PromptEngineer, so a direction carries only a bounded `prompt_seed`.
DIRECTION_TEXT_FIELDS = (
    "direction_id", "name", "concept_statement", "subject_story", "design_axis",
    "layout_structure", "focal_hierarchy", "color_system", "typography",
    "graphic_elements", "imagery_approach", "material_finish_direction",
    "emotional_tone", "product_target_fit", "target_structural_guidance",
    "originality_notes", "risks", "prompt_seed",
    # 2B-3V correction: every direction must state how its PRINTED decoration
    # is rebuilt from native vector primitives (live type / paths / fills /
    # gradients / contours / particles / petals / ribbons / geometric motifs /
    # finish masks / bounded label art) and which elements are concept-render
    # only — so a photograph can never silently become the printed surface.
    "native_reconstruction_plan",
)
DIRECTION_LIST_FIELDS = ("prohibited_choices",)
#: design_intent/1.1's direction, frozen.
V1_1_DIRECTION_FIELDS = DIRECTION_TEXT_FIELDS + DIRECTION_LIST_FIELDS + ("dip_references",)
#: §BH68(a), OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "the planner DECLARES its hierarchy family from
#: the known set, nothing guesses it from prose". One of `direction_signature.HIERARCHY_FAMILY_NAMES`; a direction
#: that declares none, or one outside the set, is refused by name (HIERARCHY_FAMILY_NOT_DECLARED).
HIERARCHY_FAMILY_FIELD = "hierarchy_family"
HIERARCHY_FAMILY_NOT_DECLARED = "HIERARCHY_FAMILY_NOT_DECLARED"
DIRECTION_FIELDS = V1_1_DIRECTION_FIELDS + (HIERARCHY_FAMILY_FIELD,)
#: Structural distinctness: each field here must be pairwise distinct across the three
#: directions, and each failure carries its own stable reason code.
DIRECTION_DISTINCT_CODES = {
    "direction_id": "DUPLICATE_DIRECTION_ID",
    "name": "DUPLICATE_DIRECTION_NAME",
    "design_axis": "DUPLICATE_DESIGN_AXIS",
    "layout_structure": "DUPLICATE_LAYOUT_STRUCTURE",
    "color_system": "DUPLICATE_COLOR_SYSTEM",
}
#: [His test blocker on design 123, 2026-10-09, (2): "Every "not distinct" check: it never stops a design."] these three
#: are such checks — the same idea, layout or colours, word for word, in two directions. A plan shown to him anyway
#: carries them, and is built, kept and read back as written; a duplicate id or name stays a refusal.
ALIKE_STRUCTURE_FIELDS = ("design_axis", "layout_structure", "color_system")

DIP_REFERENCE_FIELDS = ("corpus_item_id", "label", "source", "blocked", "note")


class DesignIntentError(ValueError):
    """The brief, intent or directions violate the contract. Refused, never trimmed."""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


# --- primitives -------------------------------------------------------------------

def _text(value, field, *, maximum=MAX_TEXT, required=True):
    if value is None or value == "":
        if required:
            raise DesignIntentError(f"{field} is required", code="FIELD_REQUIRED")
        return ""
    if not isinstance(value, str):
        raise DesignIntentError(f"{field} must be text", code="FIELD_NOT_TEXT")
    text = " ".join(value.split())
    if not text and required:
        raise DesignIntentError(f"{field} is required", code="FIELD_REQUIRED")
    if len(text) > maximum:
        raise DesignIntentError(f"{field} exceeds {maximum} characters",
                                code="FIELD_TOO_LONG")
    if "\x00" in text:
        raise DesignIntentError(f"{field} contains a null byte", code="FIELD_INVALID")
    return text


def _text_list(value, field, *, maximum=MAX_LIST, item_maximum=MAX_LIST_TEXT):
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise DesignIntentError(f"{field} must be a list", code="FIELD_NOT_A_LIST")
    items = []
    for entry in value:
        text = _text(entry, f"{field} entry", maximum=item_maximum, required=False)
        if text:
            items.append(text)
    if len(items) > maximum:
        raise DesignIntentError(f"{field} exceeds {maximum} entries",
                                code="TOO_MANY_ENTRIES")
    return items


def _exact_fields(raw, allowed, required, kind):
    if not isinstance(raw, dict):
        raise DesignIntentError(f"{kind} must be an object", code="NOT_AN_OBJECT")
    unknown = set(raw) - set(allowed)
    if unknown:
        # unknown fields are refused: they are either bugs or smuggled content
        raise DesignIntentError(f"unsupported {kind} fields: {sorted(unknown)}",
                                code="UNSUPPORTED_FIELD")
    missing = [field for field in required if not raw.get(field)]
    if missing:
        raise DesignIntentError(f"missing {kind} fields: {missing}",
                                code="FIELD_REQUIRED")


def _normalized(text) -> str:
    return " ".join(str(text).lower().split())


# --- brief ------------------------------------------------------------------------

def build_design_brief(raw: dict) -> dict:
    """Validate an untrusted brief into the bounded `design_intent/1.0` input shape."""
    _exact_fields(raw, BRIEF_FIELDS, BRIEF_REQUIRED_FIELDS, "brief")
    brief = {}
    for field in ("brand", "product_name", "product_category"):
        brief[field] = _text(raw.get(field), field, maximum=MAX_SHORT)
    target = _text(raw.get("design_target"), "design_target", maximum=MAX_SHORT)
    if target not in DESIGN_TARGETS:
        raise DesignIntentError(
            f"design_target must be one of {list(DESIGN_TARGETS)}",
            code="UNSUPPORTED_TARGET")
    brief["design_target"] = target
    for field in ("audience", "market", "dimensions"):
        brief[field] = _text(raw.get(field), field, maximum=MAX_SHORT, required=False)
    for field in sorted(_BRIEF_LIST_FIELDS):
        brief[field] = _text_list(raw.get(field), field)
    return brief


# --- DIP references ---------------------------------------------------------------

def build_dip_reference(raw: dict) -> dict:
    """One labelled, descriptive-only DIP reference. There is no way to express approval,
    reuse or attachment — a reference describes context, it never supplies an input."""
    _exact_fields(raw, DIP_REFERENCE_FIELDS,
                  ("corpus_item_id", "label", "source"), "dip_reference")
    if raw.get("label") != REFERENCE_LABEL:
        raise DesignIntentError(
            f"dip_reference label must be {REFERENCE_LABEL!r}",
            code="REFERENCE_LABEL_INVALID")
    source = raw.get("source")
    if source not in REFERENCE_SOURCES:
        raise DesignIntentError(
            f"dip_reference source must be one of {list(REFERENCE_SOURCES)}",
            code="REFERENCE_SOURCE_INVALID")
    return {
        "corpus_item_id": _text(raw.get("corpus_item_id"), "corpus_item_id",
                                maximum=64),
        "label": REFERENCE_LABEL,
        "source": source,
        "blocked": bool(raw.get("blocked", False)),
        "note": _text(raw.get("note"), "note", maximum=MAX_SHORT, required=False),
    }


# --- directions -------------------------------------------------------------------

def build_direction(raw: dict, *, version: str = DESIGN_INTENT_SCHEMA) -> dict:
    fields = V1_1_DIRECTION_FIELDS if version == DESIGN_INTENT_SCHEMA_V1_1 else DIRECTION_FIELDS
    _exact_fields(raw, fields, DIRECTION_TEXT_FIELDS, "direction")
    direction = {field: _text(raw.get(field), field) for field in DIRECTION_TEXT_FIELDS}
    if version != DESIGN_INTENT_SCHEMA_V1_1:
        # §BH68(a): the hierarchy family is DECLARED from the known set; none, or one outside it, is refused by name
        from .direction_signature import HIERARCHY_FAMILY_NAMES, UNCLASSIFIED, declared_hierarchy_family
        declared = declared_hierarchy_family(raw.get(HIERARCHY_FAMILY_FIELD))
        if declared == UNCLASSIFIED:
            raise DesignIntentError(
                f"{HIERARCHY_FAMILY_FIELD} must be declared as one of {list(HIERARCHY_FAMILY_NAMES)}; "
                f"got {raw.get(HIERARCHY_FAMILY_FIELD)!r}", code=HIERARCHY_FAMILY_NOT_DECLARED)
        direction[HIERARCHY_FAMILY_FIELD] = declared
    prohibited = _text_list(raw.get("prohibited_choices"), "prohibited_choices")
    if not prohibited:
        # a direction must SAY what it refuses to do — that is the originality floor
        raise DesignIntentError("prohibited_choices must name at least one refusal",
                                code="FIELD_REQUIRED")
    direction["prohibited_choices"] = prohibited
    references = raw.get("dip_references") or []
    if not isinstance(references, (list, tuple)):
        raise DesignIntentError("dip_references must be a list", code="FIELD_NOT_A_LIST")
    if len(references) > MAX_DIP_REFERENCES:
        raise DesignIntentError(f"dip_references exceeds {MAX_DIP_REFERENCES}",
                                code="TOO_MANY_ENTRIES")
    direction["dip_references"] = [build_dip_reference(entry) for entry in references]
    return direction


def validate_directions_distinct(directions, *, alike_ok=False):
    """The structural floor under "three meaningfully different directions".

    Pairwise-distinct names, design axes, layout structures and color systems. This cannot
    prove semantic distinctness — that is the generator's responsibility — but it makes the
    cheapest failure mode (three colorways of one layout) unrepresentable.

    ``alike_ok`` ([his test blocker on design 123, 2026-10-09, (2)]): the idea, layout and colours
    (``ALIKE_STRUCTURE_FIELDS``) are not refused here — ``structure_duplicates`` names them.
    """
    if len(directions) != DIRECTION_COUNT:
        raise DesignIntentError(
            f"exactly {DIRECTION_COUNT} directions are required, got {len(directions)}",
            code="DIRECTION_COUNT_INVALID")
    for field, code in DIRECTION_DISTINCT_CODES.items():
        if alike_ok and field in ALIKE_STRUCTURE_FIELDS:
            continue
        values = [_normalized(direction[field]) for direction in directions]
        if len(set(values)) != DIRECTION_COUNT:
            raise DesignIntentError(
                f"directions must have pairwise-distinct {field} values", code=code)


def structure_duplicates(directions) -> list:
    """[His test blocker on design 123, 2026-10-09, (2)] each word-for-word duplicate of idea, layout or colours among
    the directions, as its refusal's code and words — [] where there is none."""
    found = []
    for field in ALIKE_STRUCTURE_FIELDS:
        values = [_normalized(direction[field]) for direction in directions]
        if len(set(values)) != len(values):
            found.append(f"{DIRECTION_DISTINCT_CODES[field]}: directions must have pairwise-distinct {field} values")
    return found


# --- intent -----------------------------------------------------------------------

def build_design_intent(*, brief: dict, intent: dict, directions: list,
                        version: str = DESIGN_INTENT_SCHEMA, alike_ok: bool = False) -> dict:
    """Assemble and validate one complete `design_intent/1.0` document.

    `brief` may be raw or already validated (validation is idempotent). The result is the
    exact document the UI displays and the selection step persists — nothing hidden, no
    free-form extras, no chain-of-thought field.
    """
    validated_brief = build_design_brief(brief)
    allowed = set(INTENT_TEXT_FIELDS) | set(INTENT_LIST_FIELDS) | {"confidence"}
    _exact_fields(intent, allowed, INTENT_TEXT_FIELDS, "intent")
    document = {
        "schema_version": version,
        "brief": validated_brief,
    }
    for field in INTENT_TEXT_FIELDS:
        document[field] = _text(intent.get(field), field)
    for field in INTENT_LIST_FIELDS:
        maximum = (MAX_UNRESOLVED_QUESTIONS if field == "unresolved_questions"
                   else MAX_LIST)
        document[field] = _text_list(intent.get(field), field, maximum=maximum)
    confidence = intent.get("confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise DesignIntentError(
            f"confidence must be one of {list(CONFIDENCE_LEVELS)}",
            code="CONFIDENCE_INVALID")
    document["confidence"] = confidence
    built = [build_direction(direction, version=version) for direction in directions]
    validate_directions_distinct(built, alike_ok=alike_ok)
    document["directions"] = built
    return document


def validate_design_intent_document(document) -> str:
    """Validate a complete document against ITS DECLARED schema version, or refuse.

    The declared version is authoritative: a 1.1-shaped payload declaring 1.0 fails on
    unknown fields, and a 1.0-shaped payload declaring 1.1 fails on missing ones —
    versions are never interchangeable. Returns the validated version string.
    """
    if not isinstance(document, dict):
        raise DesignIntentError("document must be an object", code="NOT_AN_OBJECT")
    declared = document.get("schema_version")
    if declared in (DESIGN_INTENT_SCHEMA, DESIGN_INTENT_SCHEMA_V1_1):
        # [his test blocker on design 123, (2)] a plan shown to him though alike is read back as it was written
        rebuilt = build_design_intent(
            brief=document.get("brief") or {},
            intent={key: value for key, value in document.items()
                    if key not in ("schema_version", "brief", "directions")},
            directions=document.get("directions") or [], version=declared, alike_ok=True)
        if rebuilt != document:
            raise DesignIntentError(
                f"document does not normalize to itself under {declared}",
                code="DOCUMENT_NOT_CANONICAL")
        return declared
    if declared == DESIGN_INTENT_SCHEMA_V1_0:
        _validate_v1_0(document)
        return DESIGN_INTENT_SCHEMA_V1_0
    raise DesignIntentError(f"unsupported schema_version {declared!r}",
                            code="UNSUPPORTED_SCHEMA_VERSION")


def _validate_v1_0(document):
    """The FROZEN Phase 2A-1 validator. Never extend this: 1.0 documents that were valid
    when written must stay valid, and nothing new may claim to be 1.0."""
    allowed = ({"schema_version", "brief", "confidence", "directions"}
               | set(V1_0_INTENT_TEXT_FIELDS) | set(INTENT_LIST_FIELDS))
    _exact_fields(document, allowed,
                  V1_0_INTENT_TEXT_FIELDS + ("brief", "directions"), "v1.0 document")
    build_design_brief(document["brief"])
    for field in V1_0_INTENT_TEXT_FIELDS:
        _text(document.get(field), field)
    for field in INTENT_LIST_FIELDS:
        _text_list(document.get(field), field,
                   maximum=(MAX_UNRESOLVED_QUESTIONS if field == "unresolved_questions"
                            else MAX_LIST))
    if document.get("confidence") not in CONFIDENCE_LEVELS:
        raise DesignIntentError("confidence invalid for v1.0", code="CONFIDENCE_INVALID")
    directions = document.get("directions") or []
    if len(directions) != DIRECTION_COUNT:
        raise DesignIntentError("v1.0 requires exactly 3 directions",
                                code="DIRECTION_COUNT_INVALID")
    for direction in directions:
        _exact_fields(direction, V1_0_DIRECTION_TEXT_FIELDS + ("dip_references",),
                      V1_0_DIRECTION_TEXT_FIELDS, "v1.0 direction")
        for field in V1_0_DIRECTION_TEXT_FIELDS:
            _text(direction.get(field), field)
        for entry in direction.get("dip_references") or []:
            build_dip_reference(entry)
    for field in V1_0_DIRECTION_DISTINCT_FIELDS:
        values = [_normalized(direction[field]) for direction in directions]
        if len(set(values)) != DIRECTION_COUNT:
            raise DesignIntentError(
                f"v1.0 directions must have pairwise-distinct {field} values",
                code="DIRECTIONS_NOT_DISTINCT")


def production_input_references(document) -> list:
    """Always empty, by contract — and callable, so a test can assert the invariant.

    A `design_intent/1.0` document can DESCRIBE corpus items but cannot supply one as a
    production input: references are labelled descriptive-only, and blocked or
    rights-unreviewed items stay behind their `blocked` flag. Any future field that made an
    asset an input would have to change the schema version.
    """
    return []
