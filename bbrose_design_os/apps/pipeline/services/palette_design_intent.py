"""PALT-M4C §E/§F/§G — palette design-intent schema.

The §D audit established that no palette module can reach a selected
concept: ``build_palt_p1`` takes five floats and there is no channel for
design information. This module is that channel.

Authority law (§F). The selected AI concept is a
``DESIGN_INTENT_REFERENCE``. It is never a manufacturing drawing, CAD
authority, supplier authority, tolerance authority or hidden-geometry
authority. Every extracted field carries one of three constraint levels:

``HARD_VISIBLE_CONSTRAINT``
    countable or unambiguous in the image — nine pans, circular pans,
    mirror present, hinge visibly at the top.
``SOFT_VISUAL_CONSTRAINT``
    a proportion or impression — generous margins, softly rounded
    corners, a thin-looking lid.
``DECORATIVE_PREFERENCE``
    character only — gold accent, premium feel.

Soft and decorative fields must NOT be converted into rigid numbers.
They influence a value's target, never its tolerance.

Two-stage analysis (§G): an ``AI_DESIGN_INTENT_DRAFT`` may be produced
without the owner, but only ``HUMAN_CONFIRMED_DESIGN_INTENT`` is design
authority. Unconfirmed fields stay ``PENDING_OWNER_CONFIRMATION`` and are
carried as a clearly labelled ``PROVISIONAL_INTENT_VARIANT`` so the engine
can keep running without ever claiming approval.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

SCHEMA = "palette_design_intent/1.0"

# --- §F authority levels ---------------------------------------------------
HARD = "HARD_VISIBLE_CONSTRAINT"
SOFT = "SOFT_VISUAL_CONSTRAINT"
DECORATIVE = "DECORATIVE_PREFERENCE"
CONSTRAINT_LEVELS = (HARD, SOFT, DECORATIVE)

REFERENCE_AUTHORITY = "DESIGN_INTENT_REFERENCE"
NOT_AUTHORITY = ("MANUFACTURING_DRAWING", "CAD_AUTHORITY",
                 "SUPPLIER_AUTHORITY", "TOLERANCE_AUTHORITY",
                 "HIDDEN_GEOMETRY_AUTHORITY")

# --- §G confirmation states ------------------------------------------------
DRAFT = "AI_DESIGN_INTENT_DRAFT"
CONFIRMED = "HUMAN_CONFIRMED_DESIGN_INTENT"
PENDING = "PENDING_OWNER_CONFIRMATION"
CORRECTED = "OWNER_CORRECTED"
REMOVED = "OWNER_REMOVED"
CONFIRMATION_STATES = (DRAFT, CONFIRMED, PENDING, CORRECTED, REMOVED)

# --- §H decomposition layers ----------------------------------------------
DECOMPOSITION_LAYERS = (
    "PRODUCT_GEOMETRY", "PAN_LAYOUT", "MECHANICAL_COMPONENTS",
    "MATERIAL_ZONES", "COLOUR_ZONES", "ARTWORK", "TYPOGRAPHY", "LIGHTING",
    "BACKGROUND", "PRESENTATION_EFFECTS", "SHADOWS", "REFLECTIONS")

# layers that must never be read as product geometry
NON_PRODUCT_LAYERS = ("LIGHTING", "BACKGROUND", "PRESENTATION_EFFECTS",
                      "SHADOWS", "REFLECTIONS")

EXTRACTION_METHODS = ("OWNER_STATED", "IMAGE_MEASURED", "IMAGE_COUNTED",
                      "IMAGE_INFERRED", "NOT_EXTRACTED")

# --- §E field groups -------------------------------------------------------
OUTER_FORM_FIELDS = (
    "silhouette", "width_height_relationship", "perceived_thickness",
    "symmetry", "asymmetry", "corner_character", "corner_radius_impression",
    "lid_base_relationship", "edge_hierarchy", "parting_line_position",
    "exterior_relief", "cut_outs", "raised_or_recessed_details")

INTERNAL_LAYOUT_FIELDS = (
    "pan_count", "pan_shapes", "relative_pan_sizes", "rows", "columns",
    "irregular_positions", "grouped_zones", "margins", "spacing_rhythm",
    "alignment", "visual_balance", "applicator_zone",
    "decorative_empty_space")

MECHANICAL_FIELDS = (
    "opening_direction", "hinge_location", "clasp_location",
    "mirror_presence", "mirror_proportion", "open_angle_impression",
    "folding", "sliding", "rotating", "layered_or_modular_behaviour")

MATERIAL_FIELDS = (
    "apparent_material", "gloss", "matte", "satin", "metallic",
    "transparent", "translucent", "colour_zones", "reflective_accents",
    "inserts", "powder_finish_intent")

ARTWORK_FIELDS = (
    "logo_position", "typography_zones", "lid_artwork", "base_artwork",
    "interior_artwork", "shade_names", "shade_numbering",
    "regulatory_zones", "ornament", "pattern", "hierarchy")

STYLE_FIELDS = (
    "luxury", "minimal", "playful", "romantic", "scientific",
    "architectural", "organic", "futuristic", "collector", "travel",
    "premium", "youthful")

FIELD_GROUPS = {
    "outer_form": OUTER_FORM_FIELDS,
    "internal_layout": INTERNAL_LAYOUT_FIELDS,
    "mechanical": MECHANICAL_FIELDS,
    "material": MATERIAL_FIELDS,
    "artwork": ARTWORK_FIELDS,
    "style": STYLE_FIELDS,
}
ALL_FIELDS = {f for group in FIELD_GROUPS.values() for f in group}


class DesignIntentError(ValueError):
    """Raised when an intent field is malformed or misclassified."""


@dataclass(frozen=True)
class IntentField:
    """One extracted design fact, with everything needed to audit it."""

    name: str
    value: object
    source_reference: str            # which asset it came from
    source_region: str               # where in that asset
    confidence: float                # 0..1
    extraction_method: str
    confirmation_state: str
    constraint_level: str            # HARD / SOFT / DECORATIVE
    geometry_relevance: bool
    material_relevance: bool
    artwork_relevance: bool
    note: str = ""

    def __post_init__(self):
        if self.name not in ALL_FIELDS:
            raise DesignIntentError(f"unknown intent field {self.name!r}")
        if self.constraint_level not in CONSTRAINT_LEVELS:
            raise DesignIntentError(
                f"{self.name}: unknown constraint level "
                f"{self.constraint_level!r}")
        if self.confirmation_state not in CONFIRMATION_STATES:
            raise DesignIntentError(
                f"{self.name}: unknown confirmation state "
                f"{self.confirmation_state!r}")
        if self.extraction_method not in EXTRACTION_METHODS:
            raise DesignIntentError(
                f"{self.name}: unknown extraction method "
                f"{self.extraction_method!r}")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise DesignIntentError(
                f"{self.name}: confidence {self.confidence} outside 0..1")

    @property
    def is_design_authority(self) -> bool:
        """Only owner-confirmed fields may drive a contract as authority."""
        return self.confirmation_state in (CONFIRMED, CORRECTED)


@dataclass
class PaletteDesignIntent:
    """A versioned, auditable description of a selected palette concept."""

    concept_reference: str
    fields: list = field(default_factory=list)
    decomposition: dict = field(default_factory=dict)
    view: dict = field(default_factory=dict)
    unresolved_regions: list = field(default_factory=list)
    schema: str = SCHEMA
    authority: str = REFERENCE_AUTHORITY

    def add(self, **kwargs):
        self.fields.append(IntentField(**kwargs))
        return self

    def get(self, name):
        for f in self.fields:
            if f.name == name and f.confirmation_state != REMOVED:
                return f
        return None

    def by_level(self, level):
        return [f for f in self.fields if f.constraint_level == level
                and f.confirmation_state != REMOVED]

    def geometry_fields(self):
        return [f for f in self.fields
                if f.geometry_relevance and f.confirmation_state != REMOVED]

    @property
    def confirmed(self) -> bool:
        live = [f for f in self.fields if f.confirmation_state != REMOVED]
        return bool(live) and all(f.is_design_authority for f in live)

    @property
    def state(self) -> str:
        return CONFIRMED if self.confirmed else DRAFT

    def pending(self):
        return [f.name for f in self.fields
                if f.confirmation_state == PENDING]

    def identity(self) -> str:
        payload = repr([(f.name, repr(f.value), f.constraint_level,
                         f.confirmation_state, round(float(f.confidence), 4))
                        for f in sorted(self.fields, key=lambda x: x.name)])
        return hashlib.sha256(
            (payload + self.concept_reference + self.schema).encode()
        ).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "concept_reference": self.concept_reference,
            "authority": self.authority,
            "not_authority": list(NOT_AUTHORITY),
            "state": self.state,
            "identity": self.identity(),
            "pending_owner_confirmation": self.pending(),
            "fields": [asdict(f) for f in self.fields],
            "decomposition": dict(self.decomposition),
            "view": dict(self.view),
            "unresolved_regions": list(self.unresolved_regions),
            "counts": {level: len(self.by_level(level))
                       for level in CONSTRAINT_LEVELS},
        }


def provisional_variant(intent) -> dict:
    """§G — a clearly labelled variant the engine may run on while the
    owner has not confirmed anything. It is never design authority."""
    return {
        "record_type": "provisional_intent_variant/1.0",
        "label": "PROVISIONAL_INTENT_VARIANT",
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "state": intent.state,
        "pending_owner_confirmation": intent.pending(),
        "intent": intent.to_dict(),
        "usage_rule": "may drive geometry and rendering for review only; "
                      "may never be reported as owner-approved and may "
                      "never become manufacturing authority",
    }


def decompose(layers) -> dict:
    """§H — record what was read from each layer, and refuse to let the
    presentation layers become product geometry."""
    unknown = set(layers) - set(DECOMPOSITION_LAYERS)
    if unknown:
        raise DesignIntentError(f"unknown decomposition layers {unknown}")
    return {
        "record_type": "concept_decomposition/1.0",
        "layers": {k: layers[k] for k in layers},
        "non_product_layers": list(NON_PRODUCT_LAYERS),
        "interpretation_rules": [
            "shadows are not moulded geometry",
            "reflections are not cut-outs",
            "perspective distortion is not actual proportion",
            "background decoration is not product artwork",
            "hidden geometry is not confirmed fact",
        ],
    }


def validate(intent) -> dict:
    """Fail-closed checks on an intent record."""
    findings = []
    seen = {}
    for f in intent.fields:
        if f.name in seen and f.confirmation_state != REMOVED:
            findings.append({"code": "DUPLICATE_INTENT_FIELD",
                             "message": f"{f.name} declared twice"})
        seen[f.name] = f
        if f.constraint_level == HARD and f.confidence < 0.5:
            findings.append({
                "code": "HARD_CONSTRAINT_LOW_CONFIDENCE",
                "message": (f"{f.name} is HARD but confidence "
                            f"{f.confidence}; a hard constraint must be "
                            "unambiguous in the reference")})
        if f.constraint_level == DECORATIVE and f.geometry_relevance:
            findings.append({
                "code": "DECORATIVE_DRIVING_GEOMETRY",
                "message": (f"{f.name} is DECORATIVE but marked "
                            "geometry-relevant; decorative preferences must "
                            "not become rigid numerical rules")})
        if f.extraction_method == "NOT_EXTRACTED" and f.value is not None:
            findings.append({
                "code": "VALUE_WITHOUT_EXTRACTION",
                "message": f"{f.name} has a value but no extraction method"})
    return {"record_type": "design_intent_validation/1.0",
            "valid": not findings, "findings": findings,
            "finding_count": len(findings)}
