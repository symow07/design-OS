"""Canonical versioned packaging-template registry (Phase 2A-6, section 2).

One place declares every structural template the platform can build, what it
means dimensionally, and what it can physically do. Nothing else in the
codebase may name a template by bare string and assume geometry: callers
resolve through :func:`resolve` (fail-closed) and read the declaration.

Why a registry rather than the old `Literal[...]` in the input schema: the
task-#47 failure was a *silent* structural assumption — the pipeline hard-
coded `straight_tuck_end_carton`, whose panel sequence
(glue|main|side|main|side) simply cannot be the customer's die
(glue|side|main|side|main). A template is now a declared contract with an
explicit panel sequence, closure type and seam position, so a mismatch is a
comparison, not a guess.

**Structural compatibility is never inferred from W/D/H alone.** Dimensions
constrain a template (`fits_dimensions`); they never select one. Selection
is the separate, evidence-ordered concern in
``apps.pipeline.services.template_selection``.

Registering a new template: append a `TemplateDefinition` to `_REGISTRY`
with an explicit version, and add its geometry function to the engine
dispatch. An unregistered id raises `UnknownTemplate` — there is no
fallback-by-similarity path.
"""
from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field

# --- vocabulary --------------------------------------------------------------

#: Panel roles a template may lay out, in flat order. "main" panels carry the
#: display faces (front/back); "side" panels are the depth faces.
PANEL_GLUE = "glue_flap"
PANEL_SIDE = "side"
PANEL_MAIN = "main"

#: Which dimension a panel's width is taken from.
DIM_WIDTH = "width_mm"     # W — the main/display panel width
DIM_DEPTH = "depth_mm"     # D — the side panel width

CLOSURE_STRAIGHT_TUCK = "straight_tuck"          # both tucks hinge the same way
CLOSURE_REVERSE_TUCK = "reverse_tuck"            # tucks hinge opposite ways
CLOSURE_TUCK_TOP_AUTO_BOTTOM = "tuck_top_auto_bottom"

SEAM_ON_MAIN = "seam_leads_main_panel"           # glue flap precedes a main panel
SEAM_ON_SIDE = "seam_leads_side_panel"           # glue flap precedes a side panel

BOARD_MODEL_ECMA_MAIN_REFERENCE = "ecma_main_panel_reference"
BOARD_MODEL_NONE = "none"

# --- structural classification -----------------------------------------------
#: Geometry derived from (or verified against) a measured production die.
STRUCTURE_MEASURED = "MEASURED_STRUCTURE"
#: Closure mechanics are an approximation — inspection only, never production.
STRUCTURE_PROVISIONAL = "PROVISIONAL_STRUCTURE"
#: Geometry adapted from a licence-reviewed open-source formula source and
#: not yet validated against a physical sample (Phase 2A-9). Provisional by
#: definition; only a recorded physical FIT_PASS may promote it.
STRUCTURE_OPEN_SOURCE_ADAPTED = "OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL"
#: Geometry reconstructed to match a supplied visual reference's closure
#: topology (2A-9-CORR-2): the attachment map is the review contract, and a
#: physical sample is still required before any promotion.
STRUCTURE_REFERENCE_RECONSTRUCTED = "REFERENCE_RECONSTRUCTED_PROVISIONAL"

# --- ineligibility codes (returned by selection AND by Gate 2) ---------------
#: A version kept only so historical jobs reproduce; superseded by a fix.
NON_PRODUCTION_TEMPLATE_VERSION = "NON_PRODUCTION_TEMPLATE_VERSION"
#: The structure cannot go to production until a measured reference die is
#: supplied — clean cut/fold boundaries are necessary but not sufficient.
MEASURED_REFERENCE_REQUIRED = "MEASURED_REFERENCE_REQUIRED"
#: Marker used when a provisional template is explicitly selected.
PRODUCTION_INELIGIBLE = "PRODUCTION_INELIGIBLE"
#: An open-source-adapted archetype awaits a recorded physical FIT_PASS
#: (apps.dielines.services.physical_validation) before any promotion; the
#: structure cannot pass Gate 2 while this code stands.
#: [§BH70(3) (§BH70 LIVE), his words: "A physical sample is never required to finish a design (a colleague test-fits;
#: that is not the system's job)." From that commit the code is a FACT about the geometry — untested against a printed
#: sample — said as information, and no longer a hold at Gate 2; the sentence above is history.]
PHYSICAL_SAMPLE_VALIDATION_REQUIRED = "PHYSICAL_SAMPLE_VALIDATION_REQUIRED"
#: §BH70(3): the code in words, wherever it was a hold
PHYSICAL_SAMPLE_INFORMATION = ("its structure has not been tested against a printed sample — a colleague test-fits "
                               "one; nothing waits on it")


class UnknownTemplate(KeyError):
    """Raised when a template id is not registered. Never fall back."""


class TemplateVersionMismatch(ValueError):
    """Raised when a caller pins a version the registry does not publish."""


@dataclass(frozen=True)
class ParameterSpec:
    """One required input parameter and its permitted range."""
    name: str
    unit: str
    minimum: float
    maximum: float
    default: float | None = None
    note: str = ""


@dataclass(frozen=True)
class TemplateDefinition:
    # --- identity -----------------------------------------------------------
    template_id: str
    version: str
    label: str
    #: Flat panel sequence left→right as (role, dimension, engine panel name).
    #: The third element is the name the GEOMETRY ENGINE gives that column —
    #: it is not derivable from position, because which main panel is the
    #: front depends on the closure (the STE engine puts the tuck-carrying
    #: BACK panel first, the side-seam archetype puts the front first). A
    #: test pins every declaration against the drawn panels, so the registry
    #: can never describe a different die than the engine builds.
    panel_sequence: tuple[tuple[str, str | None, str], ...]
    #: What the user-supplied width/depth/height MEAN for this template.
    dimension_semantics: dict[str, str]
    closure_type: str
    glue_seam_position: str
    board_compensation_model: str
    required_parameters: tuple[ParameterSpec, ...]
    #: Capabilities the geometry actually emits — the structural checklist and
    #: the Gate-2 validator compare against these, so a template cannot claim
    #: a closure feature it does not draw.
    flap_capabilities: frozenset[str]
    notch_capabilities: frozenset[str]
    bleed_behavior: str
    safe_area_behavior: str
    #: Provisional = no measured reference die; a human must confirm the
    #: structure before production.
    provisional: bool = False
    #: False = this version has a known manufacturing defect and may be
    #: REPRODUCED (historical jobs) but never newly shipped. The production
    #: validator refuses it (NON_PRODUCTION_TEMPLATE_VERSION).
    production_ready: bool = True
    #: The version that corrects this one, when superseded.
    superseded_by: str = ""
    #: WHY this version is not production-eligible — the stable code the
    #: selector and Gate 2 both return. Empty when production_ready is True.
    ineligibility_code: str = ""
    #: Structural classification. PROVISIONAL_STRUCTURE means the closure
    #: mechanics are not modelled from a measured production die, so the
    #: template is for technical inspection only however clean its
    #: cut/fold boundaries are.
    structure_status: str = STRUCTURE_MEASURED
    #: 2A-9E: when True, the structure-confirmation gate itself refuses
    #: until an exact-hash physical FIT_PASS exists (the customer-grade
    #: archetypes: task #50's opposed die, the ecma_ste archetype — their
    #: flow is APPROVE-FOR-PHYSICAL-TEST then confirm). When False (STE/RTE
    #: 1.2 and everything else), confirmation and artwork mapping proceed
    #: and the physical blocker lives at Gate 2 only.
    confirmation_requires_physical_fit_pass: bool = False
    #: Specific limitations a reviewer must see before touching it.
    structural_limitations: tuple[str, ...] = ()
    #: Extra structural notes surfaced at the confirmation gate.
    notes: tuple[str, ...] = ()
    #: Optional per-template collision validator; defaults to the shared one.
    collision_validator: str = "apps.dielines.analysis.reconciliation:reconcile_dimensions"
    #: Which archetype module owns the geometry (documentation + audit).
    geometry_module: str = ""
    #: Frozen preset name in the archetype module, when the template is a
    #: parameter preset rather than a bare style.
    preset: str = ""
    aliases: tuple[str, ...] = field(default=())

    # --- derived views ------------------------------------------------------

    @property
    def key(self) -> str:
        return f"{self.template_id}/{self.version}"

    def panel_order(self) -> list[str]:
        """The engine's panel names, left→right across the flat."""
        return [name for _role, _dim, name in self.panel_sequence]

    def panel_sequence_label(self) -> str:
        """Reviewer-facing sequence, e.g. 'glue flap | D side_left | W front'."""
        parts = []
        for role, dim, name in self.panel_sequence:
            if role == PANEL_GLUE:
                parts.append("glue flap")
            else:
                axis = {DIM_WIDTH: "W", DIM_DEPTH: "D"}.get(dim, "?")
                parts.append(f"{axis} {name}")
        return " | ".join(parts)

    def fits_dimensions(self, dims: dict) -> list[str]:
        """Range/parameter violations for the supplied values — NOT a
        selection signal. An empty list means "this template *could* be
        built at these numbers", never "this template is correct"."""
        problems: list[str] = []
        for p in self.required_parameters:
            if p.name not in dims:
                if p.default is None:
                    problems.append(f"missing required parameter {p.name}")
                continue
            try:
                value = float(dims[p.name])
            except (TypeError, ValueError):
                problems.append(f"{p.name} is not a number")
                continue
            if not (p.minimum <= value <= p.maximum):
                problems.append(
                    f"{p.name} {value:g} {p.unit} is outside the permitted "
                    f"{p.minimum:g}–{p.maximum:g} {p.unit} for {self.key}"
                )
        return problems

    def to_dict(self) -> dict:
        d = asdict(self)
        d["flap_capabilities"] = sorted(self.flap_capabilities)
        d["notch_capabilities"] = sorted(self.notch_capabilities)
        d["panel_order"] = self.panel_order()
        d["panel_sequence_label"] = self.panel_sequence_label()
        d["key"] = self.key
        return d


# --- shared parameter sets -----------------------------------------------------

_TUCK_CARTON_PARAMETERS = (
    ParameterSpec("width_mm", "mm", 12.0, 300.0,
                  note="main/display panel width (W)"),
    ParameterSpec("depth_mm", "mm", 12.0, 300.0,
                  note="side panel width (D)"),
    ParameterSpec("height_mm", "mm", 60.0, 600.0),
    ParameterSpec("bleed_mm", "mm", 2.0, 5.0, default=3.0),
    ParameterSpec("safe_margin_mm", "mm", 3.0, 8.0, default=4.0),
    ParameterSpec("glue_tab_mm", "mm", 6.0, 15.0, default=10.0),
    ParameterSpec("board_thickness_mm", "mm", 0.0, 1.0, default=0.35),
)

_STE_FLAPS = frozenset({
    "top_tuck_flap", "bottom_tuck_flap", "top_dust_flaps", "bottom_dust_flaps",
    "tapered_glue_flap", "cubic_shoulder_curves", "friction_slits",
})
_SIDE_SEAM_FLAPS = _STE_FLAPS | {"tuck_base_entry_slits", "per_hinge_creases"}


# --- the registry ---------------------------------------------------------------

#: Keyed by (template_id, version) — a template may publish several
#: versions at once so historical geometry stays reproducible.
_REGISTRY: dict[tuple[str, str], TemplateDefinition] = {}
#: template_id -> the version an unpinned caller resolves to.
_CURRENT: dict[str, str] = {}


def _register(defn: TemplateDefinition, *, current: bool = True) -> TemplateDefinition:
    key = (defn.template_id, defn.version)
    if key in _REGISTRY:
        raise ValueError(f"template already registered: {defn.key}")
    _REGISTRY[key] = defn
    if current:
        _CURRENT[defn.template_id] = defn.version
    return defn


STRAIGHT_TUCK_END_CARTON_V1_0 = _register(TemplateDefinition(
    template_id="straight_tuck_end_carton",
    version="1.0",
    label="Straight Tuck-End Carton (generic)",
    # The STE engine lays the glue tab against the BACK panel (which carries
    # the top tuck); the front follows the first side panel.
    panel_sequence=(
        (PANEL_GLUE, None, "glue_tab"),
        (PANEL_MAIN, DIM_WIDTH, "back"),
        (PANEL_SIDE, DIM_DEPTH, "side_left"),
        (PANEL_MAIN, DIM_WIDTH, "front"),
        (PANEL_SIDE, DIM_DEPTH, "side_right"),
    ),
    dimension_semantics={
        "width_mm": "manufacturing main-panel width (score to score)",
        "depth_mm": "manufacturing side-panel width (score to score)",
        "height_mm": "manufacturing body height (score to score)",
    },
    closure_type=CLOSURE_STRAIGHT_TUCK,
    glue_seam_position=SEAM_ON_MAIN,
    board_compensation_model=BOARD_MODEL_ECMA_MAIN_REFERENCE,
    required_parameters=_TUCK_CARTON_PARAMETERS,
    flap_capabilities=_STE_FLAPS,
    notch_capabilities=frozenset({"shoulder_lock_notches_2t", "dust_base_notch"}),
    bleed_behavior="uniform outward offset of the complete cut contour, round joins",
    safe_area_behavior="body rectangle inset by the safe margin, glue tab excluded",
    geometry_module="apps.dielines.geometry.engine",
    notes=(
        "GENERIC template: its panel sequence is glue|main|side|main|side. "
        "Only correct when no customer die says otherwise.",
        "KNOWN DEFECT (found by the Phase 2A-6 cut/fold check, 2026-07-20): "
        "the engine draws full-width horizontal creases at y1/y2, so ~44 mm "
        "of crease runs along the panel edge that is actually CUT at that "
        "end (the panel carrying no flap there). The side-seam archetype "
        "fixed this via DECISION-020 per-hinge creases; the locked STE "
        "engine is unchanged pending a decision, so Gate-2 reports "
        "CUT_FOLD_CONFLICT for this template.",
    ),
    production_ready=False,
    superseded_by="1.1",
    ineligibility_code=NON_PRODUCTION_TEMPLATE_VERSION,
))

REVERSE_TUCK_END_CARTON_V1_0 = _register(TemplateDefinition(
    template_id="reverse_tuck_end_carton",
    version="1.0",
    label="Reverse Tuck-End Carton (generic, provisional)",
    panel_sequence=STRAIGHT_TUCK_END_CARTON_V1_0.panel_sequence,
    dimension_semantics=dict(STRAIGHT_TUCK_END_CARTON_V1_0.dimension_semantics),
    closure_type=CLOSURE_REVERSE_TUCK,
    glue_seam_position=SEAM_ON_MAIN,
    board_compensation_model=BOARD_MODEL_ECMA_MAIN_REFERENCE,
    required_parameters=_TUCK_CARTON_PARAMETERS,
    flap_capabilities=_STE_FLAPS,
    notch_capabilities=frozenset({"shoulder_lock_notches_2t", "dust_base_notch"}),
    bleed_behavior=STRAIGHT_TUCK_END_CARTON_V1_0.bleed_behavior,
    safe_area_behavior=STRAIGHT_TUCK_END_CARTON_V1_0.safe_area_behavior,
    provisional=True,
    geometry_module="apps.dielines.geometry.engine",
    notes=("No measured reference die — confirm the structure before production.",
        "KNOWN DEFECT: shares the straight_tuck_end_carton full-width "
        "crease issue — Gate-2 reports CUT_FOLD_CONFLICT.",
    ),
    production_ready=False,
    superseded_by="1.1",
    ineligibility_code=NON_PRODUCTION_TEMPLATE_VERSION,
))

TUCK_TOP_AUTO_BOTTOM_CARTON_V1_0 = _register(TemplateDefinition(
    template_id="tuck_top_auto_bottom_carton",
    version="1.0",
    label="Tuck-Top Auto-Bottom Carton (generic, provisional)",
    panel_sequence=STRAIGHT_TUCK_END_CARTON_V1_0.panel_sequence,
    dimension_semantics=dict(STRAIGHT_TUCK_END_CARTON_V1_0.dimension_semantics),
    closure_type=CLOSURE_TUCK_TOP_AUTO_BOTTOM,
    glue_seam_position=SEAM_ON_MAIN,
    board_compensation_model=BOARD_MODEL_ECMA_MAIN_REFERENCE,
    required_parameters=_TUCK_CARTON_PARAMETERS,
    flap_capabilities=frozenset({
        "top_tuck_flap", "top_dust_flaps", "crash_lock_base",
        "tapered_glue_flap", "cubic_shoulder_curves", "friction_slits",
    }),
    notch_capabilities=frozenset({"shoulder_lock_notches_2t", "dust_base_notch"}),
    bleed_behavior=STRAIGHT_TUCK_END_CARTON_V1_0.bleed_behavior,
    safe_area_behavior=STRAIGHT_TUCK_END_CARTON_V1_0.safe_area_behavior,
    provisional=True,
    geometry_module="apps.dielines.geometry.engine",
    notes=("Crash-lock base is an ECMA approximation — confirm before production.",
        "KNOWN DEFECT: shares the straight_tuck_end_carton full-width "
        "crease issue — Gate-2 reports CUT_FOLD_CONFLICT.",
    ),
    production_ready=False,
    superseded_by="1.1",
    ineligibility_code=NON_PRODUCTION_TEMPLATE_VERSION,
))

# --- corrected versions (Phase 2A-6-CORR-1, DECISION-021) -------------------
# Identical structure to their 1.0 predecessors EXCEPT the horizontal creases,
# which are now emitted per real hinge and shortened around the lock notches.
# 1.0 stays registered so a historical job reproduces byte-for-byte; only 1.1
# is production-eligible.

_CORRECTED_NOTE = (
    "Corrects the DECISION-021 crease defect: horizontal creases are emitted "
    "per real hinge and shortened around the DECISION-015 lock notches, so no "
    "crease is ever scored over a cut edge. Structure is otherwise identical "
    "to 1.0."
)


def _corrected(base: TemplateDefinition, *, production_ready: bool = True,
               ineligibility_code: str = "",
               structure_status: str = STRUCTURE_MEASURED,
               limitations: tuple[str, ...] = (),
               extra_notes: tuple[str, ...] = ()) -> TemplateDefinition:
    return _register(dataclasses.replace(
        base,
        version="1.1",
        label=base.label.replace(" (generic", " 1.1 (generic"),
        production_ready=production_ready,
        ineligibility_code=ineligibility_code,
        structure_status=structure_status,
        structural_limitations=limitations,
        superseded_by="",
        flap_capabilities=base.flap_capabilities | {"per_hinge_creases"},
        notes=tuple(n for n in base.notes if not n.startswith("KNOWN DEFECT"))
              + (_CORRECTED_NOTE,) + extra_notes,
    ))


STRAIGHT_TUCK_END_CARTON = _corrected(STRAIGHT_TUCK_END_CARTON_V1_0)
REVERSE_TUCK_END_CARTON = _corrected(REVERSE_TUCK_END_CARTON_V1_0)


_D_DERIVED_NOTE = (
    "2A-9D D-derived closure: the major tuck reaches across the DEPTH "
    "(D + explicit 16 mm lip) with a lip-derived shoulder span, correcting "
    "the 1.1 W-derived tuck. Structurally identical to 1.1 otherwise (same "
    "panel order, friction slits, 2t lock notches, dust flaps). Wider "
    "supported domain in the wide-short direction; the W >= 1.262 D dust "
    "clearance edge is unchanged from 1.1."
)


def _d_derived_version(base_11: TemplateDefinition) -> TemplateDefinition:
    """Register the 1.2 D-derived correction. NON-CURRENT (no default
    switch): 1.1 stays the resolved version until separately approved.
    TECHNICALLY_QUALIFIED_DOMAIN only — physical sample still required."""
    return _register(dataclasses.replace(
        base_11,
        version="1.2",
        label=base_11.label.replace(" 1.1 ", " 1.2 "),
        production_ready=False,
        ineligibility_code=PHYSICAL_SAMPLE_VALIDATION_REQUIRED,
        structure_status=STRUCTURE_PROVISIONAL,
        superseded_by="",
        structural_limitations=(
            "D-derived closure technically qualified over its published "
            "domain; no physical sample recorded (FIT_PASS required before "
            "any promotion)",
        ),
        notes=tuple(n for n in base_11.notes
                    if not n.startswith(_CORRECTED_NOTE[:24]))
              + (_D_DERIVED_NOTE,),
    ), current=False)


STRAIGHT_TUCK_END_CARTON_V1_2 = _d_derived_version(STRAIGHT_TUCK_END_CARTON)
REVERSE_TUCK_END_CARTON_V1_2 = _d_derived_version(REVERSE_TUCK_END_CARTON)

_PRINT_READY_NOTE = (
    "[His final goal, 2026-10-05, B2: \"A PRINT-READY DIELINE ... It must go to a printer without being edited.\"] 1.2's "
    "tuck across the depth, with the tuck fold creased between two lock slits cut from the flap's side edges, and a "
    "half-round thumb notch in the top edge of the panel the lid closes onto."
)


def _print_ready_version(base_12: TemplateDefinition) -> TemplateDefinition:
    """[His final goal, 2026-10-05, B2.] 1.3 — the version a new design is drawn at; not the unpinned current."""
    return _register(dataclasses.replace(
        base_12, version="1.3", label=base_12.label.replace(" 1.2 ", " 1.3 "),
        notes=tuple(base_12.notes) + (_PRINT_READY_NOTE,)), current=False)


STRAIGHT_TUCK_END_CARTON_V1_3 = _print_ready_version(STRAIGHT_TUCK_END_CARTON_V1_2)
REVERSE_TUCK_END_CARTON_V1_3 = _print_ready_version(REVERSE_TUCK_END_CARTON_V1_2)

#: [His second goal of 2026-10-06 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c34a518), item 2: "TOP-TIER DIELINES ...
#: Do NOT rely on what the system already believes about dielines."] 1.4 — drawn to the trade's written rules
#: (apps/dielines/docs/TRADE_RULES.md) by ``apps.dielines.geometry.trade_tuck``: the straight tuck end ECMA A20.20.01.01
#: (both tucks on the back), the reverse ECMA A20.20.03.01 (top on the back, bottom on the front); sizes read as the
#: inside, every crease at inside + t; the lid as deep as the side panel and hinged one caliper outside the dust flaps;
#: a tongue of 0.26 the lid's depth (8–20 mm) with rounded corners; lock slits at the tuck fold paired with shouldered,
#: asymmetric dust flaps that never meet across the opening; a tapered glue flap; a thumb notch. Folded and checked by
#: ``apps.dielines.geometry.fold_check`` on every die.
BOARD_MODEL_INSIDE_PLUS_CALIPER = "inside_plus_caliper"
_TRADE_FLAPS = frozenset({
    "top_tuck_flap", "bottom_tuck_flap", "top_dust_flaps", "bottom_dust_flaps", "tapered_glue_flap",
    "per_hinge_creases", "tuck_fold_creases", "lock_slits", "rounded_tongue_corners", "lid_hinge_offset",
    "thumb_notch", "flap_relief_slots",
})
_TRADE_SEMANTICS = {
    "width_mm": "inside width — the front and back panels' crease width is this plus the board's caliper",
    "depth_mm": "inside depth — the side panels' crease width is this plus the board's caliper",
    "height_mm": "inside height — the body's crease height is this plus the board's caliper",
}


def _trade_version(base: TemplateDefinition, *, label: str, closure: str, ecma: str) -> TemplateDefinition:
    return _register(dataclasses.replace(
        base, version="1.4", label=label, closure_type=closure, dimension_semantics=dict(_TRADE_SEMANTICS),
        board_compensation_model=BOARD_MODEL_INSIDE_PLUS_CALIPER, flap_capabilities=_TRADE_FLAPS,
        notch_capabilities=frozenset({"dust_flap_shoulders", "lock_slits", "thumb_notch"}),
        bleed_behavior="uniform outward offset of the complete cut contour, round joins (B1)",
        safe_area_behavior="the body inset by the safe margin; the glue flap free of ink (B2, G4)",
        geometry_module="apps.dielines.geometry.trade_tuck",
        notes=("ECMA %s, drawn to apps/dielines/docs/TRADE_RULES.md — every number a rule with its source." % ecma,
               "Folded by apps.dielines.geometry.fold_check on every die; a failure holds Gate 2 by name.")),
        current=False)


STRAIGHT_TUCK_END_CARTON_V1_4 = _trade_version(
    STRAIGHT_TUCK_END_CARTON_V1_3, label="Straight Tuck End 1.4 (ECMA A20.20.01.01)", closure=CLOSURE_STRAIGHT_TUCK,
    ecma="A20.20.01.01")
REVERSE_TUCK_END_CARTON_V1_4 = _trade_version(
    REVERSE_TUCK_END_CARTON_V1_3, label="Reverse Tuck End 1.4 (ECMA A20.20.03.01)", closure=CLOSURE_REVERSE_TUCK,
    ecma="A20.20.03.01")

# The auto-bottom's CUT/FOLD boundaries are corrected, but its closure
# MECHANICS are still an approximation: the crash-lock panels are not
# independently modelled, adhesive regions are incomplete, the diagonal folds
# come from no measured die, and the four lock flaps merge into one shape.
# Clean boundaries are necessary but nowhere near sufficient for a working
# auto bottom, so 1.1 is corrected AND production-ineligible.
TUCK_TOP_AUTO_BOTTOM_CARTON = _corrected(
    TUCK_TOP_AUTO_BOTTOM_CARTON_V1_0,
    production_ready=False,
    ineligibility_code=MEASURED_REFERENCE_REQUIRED,
    structure_status=STRUCTURE_PROVISIONAL,
    limitations=(
        "interlocking crash-lock panels are not independently modelled",
        "adhesive regions are incomplete",
        "diagonal folds are not based on a measured production reference",
        "the four lock flaps merge into one structural shape instead of "
        "being separated by cuts",
    ),
    extra_notes=(
        "PROVISIONAL_STRUCTURE / PRODUCTION_INELIGIBLE: cut and fold "
        "boundaries are correct, but the closure mechanics await a measured "
        "crash-lock reference die. Kept for technical inspection and future "
        "measured-reference work — this is NOT a finished auto-bottom "
        "production die. A corrected version may be published only after a "
        "measured reference is supplied.",
    ),
)


SKYNTE_FOUNDATION_TUCK_CARTON = _register(TemplateDefinition(
    template_id="skynte_foundation_tuck_carton",
    version="1.0",
    label="Skynte Foundation Tuck Carton (side-seam)",
    # Side-seam: the glue tab leads a SIDE panel, so the front comes second.
    panel_sequence=(
        (PANEL_GLUE, None, "glue_tab"),
        (PANEL_SIDE, DIM_DEPTH, "side_left"),
        (PANEL_MAIN, DIM_WIDTH, "front"),
        (PANEL_SIDE, DIM_DEPTH, "side_right"),
        (PANEL_MAIN, DIM_WIDTH, "back"),
    ),
    dimension_semantics={
        "width_mm": "manufacturing MAIN-panel width (42 mm on the Skynte die)",
        "depth_mm": "manufacturing SIDE-panel width (32 mm on the Skynte die)",
        "height_mm": "manufacturing body height (140 mm on the Skynte die)",
    },
    closure_type=CLOSURE_STRAIGHT_TUCK,
    glue_seam_position=SEAM_ON_SIDE,
    board_compensation_model=BOARD_MODEL_ECMA_MAIN_REFERENCE,
    required_parameters=_TUCK_CARTON_PARAMETERS,
    flap_capabilities=_SIDE_SEAM_FLAPS,
    notch_capabilities=frozenset({
        "shoulder_lock_notches_2t", "dust_base_notch", "tuck_base_entry_slits",
    }),
    bleed_behavior=STRAIGHT_TUCK_END_CARTON_V1_0.bleed_behavior,
    safe_area_behavior=STRAIGHT_TUCK_END_CARTON_V1_0.safe_area_behavior,
    geometry_module="apps.dielines.geometry.side_seam",
    preset="SKYNTE_FOUNDATION_TUCK_CARTON_V1",
    notes=(
        "Reconstructed parametrically from the supplied Skynte manufacturing "
        "reference (DECISION-018/019/020). Tuck height = D + lip; closure "
        "depths are published template assumptions, not customer dimensions.",
    ),
))


#: Phase 2A-9 — customer-grade STE archetype, adapted (MIT, attribution in
#: THIRD_PARTY_NOTICES.md) from DDR68/Rhino_Packaging_Toolkit's ECMA
#: A20.20.01.01 generator. PROVISIONAL 0.1: never production-eligible until
#: a physical sample records FIT_PASS, and automatically outranked by any
#: registered customer/manufacturer-supplied dieline.
ECMA_A20_20_01_01_STE_CARTON = _register(TemplateDefinition(
    template_id="ecma_a20_20_01_01_ste_carton",
    version="0.1",
    label="ECMA A20.20.01.01 Straight Tuck End (open-source-adapted, "
          "provisional)",
    # Both tuck flaps hinge from the back panel (the DDR68/Pacdora closure
    # orientation): glue | back | side | front | side.
    panel_sequence=(
        (PANEL_GLUE, None, "glue_tab"),
        (PANEL_MAIN, DIM_WIDTH, "back"),
        (PANEL_SIDE, DIM_DEPTH, "side_left"),
        (PANEL_MAIN, DIM_WIDTH, "front"),
        (PANEL_SIDE, DIM_DEPTH, "side_right"),
    ),
    dimension_semantics={
        "width_mm": "INNER main-panel width (external = inner + 2t)",
        "depth_mm": "INNER side-panel depth (external = inner + 2t)",
        "height_mm": "INNER body height (= body span between main creases)",
    },
    closure_type=CLOSURE_STRAIGHT_TUCK,
    glue_seam_position=SEAM_ON_MAIN,
    board_compensation_model=BOARD_MODEL_ECMA_MAIN_REFERENCE,
    required_parameters=(
        ParameterSpec("width_mm", "mm", 12.0, 300.0,
                      note="INNER main-panel width"),
        ParameterSpec("depth_mm", "mm", 12.0, 300.0,
                      note="INNER side-panel depth"),
        ParameterSpec("height_mm", "mm", 60.0, 600.0,
                      note="INNER body height"),
        ParameterSpec("bleed_mm", "mm", 2.0, 5.0, default=3.0),
        ParameterSpec("safe_margin_mm", "mm", 3.0, 8.0, default=4.0),
        ParameterSpec("glue_tab_mm", "mm", 6.0, 15.0, default=12.0),
        ParameterSpec("board_thickness_mm", "mm", 0.3, 1.0, default=0.5),
    ),
    flap_capabilities=frozenset({
        "top_tuck_flap", "bottom_tuck_flap", "top_dust_flaps",
        "bottom_dust_flaps", "cubic_shoulder_curves", "tapered_glue_flap",
        "tuck_base_entry_slits", "per_hinge_creases",
    }),
    notch_capabilities=frozenset(),
    bleed_behavior="full cut-contour offset (buffer of the union outline)",
    safe_area_behavior="body slab inset by safe_margin_mm",
    provisional=True,
    production_ready=False,
    ineligibility_code=PHYSICAL_SAMPLE_VALIDATION_REQUIRED,
    structure_status=STRUCTURE_OPEN_SOURCE_ADAPTED,
    confirmation_requires_physical_fit_pass=True,
    structural_limitations=(
        "no measured customer/manufacturer die: panel allowances follow the "
        "adapted source's external = inner + 2t convention (Pacdora's "
        "published numbers differ by <= 0.6 mm)",
        "flap shapes match the visible Pacdora reference only at screenshot "
        "level — exact contours are not claimable without the vector file",
        "closure verified geometrically, never physically — a printed "
        "100%-scale sample must record FIT_PASS before promotion",
    ),
    notes=(
        "PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED — NOT APPROVED "
        "FOR MASS PRODUCTION.",
        "Geometry adapted (MIT, attribution preserved) from "
        "DDR68/Rhino_Packaging_Toolkit ECMA_A20_20_01_01.py; provenance in "
        "apps.dielines.geometry.ecma_ste.FORMULA_PROVENANCE.",
        "A registered customer- or manufacturer-supplied dieline outranks "
        "this archetype automatically.",
    ),
    geometry_module="apps.dielines.geometry.ecma_ste",
    preset="ECMA_A20_20_01_01_STE_CARTON_V0_1",
))


#: 2A-9-CORR-2 — reference-matched OPPOSING-tuck carton. The first 2A-9
#: archetype hung both tucks from one main panel; the Pacdora reference
#: opposes them (top on main A, bottom on main B). Geometry adapted (MIT)
#: from DDR68/Rhino_Packaging_Toolkit's opposing-tuck generator; the
#: reference attachment map is persisted with every generated die.
REFERENCE_OPPOSED_TUCK_CARTON = _register(TemplateDefinition(
    template_id="reference_opposed_tuck_carton",
    version="0.1",
    label="Reference-Matched Opposing Tuck Carton (provisional)",
    panel_sequence=(
        (PANEL_GLUE, None, "glue_tab"),
        (PANEL_MAIN, DIM_WIDTH, "main_a"),
        (PANEL_SIDE, DIM_DEPTH, "side_a"),
        (PANEL_MAIN, DIM_WIDTH, "main_b"),
        (PANEL_SIDE, DIM_DEPTH, "side_b"),
    ),
    dimension_semantics={
        "width_mm": "INNER main-panel width (external = inner + 2t)",
        "depth_mm": "INNER side-panel depth (external = inner + 2t)",
        "height_mm": "INNER body height (= body span between main creases)",
    },
    closure_type=CLOSURE_REVERSE_TUCK,
    glue_seam_position=SEAM_ON_MAIN,
    board_compensation_model=BOARD_MODEL_ECMA_MAIN_REFERENCE,
    required_parameters=(
        ParameterSpec("width_mm", "mm", 12.0, 300.0,
                      note="INNER main-panel width"),
        ParameterSpec("depth_mm", "mm", 12.0, 300.0,
                      note="INNER side-panel depth"),
        ParameterSpec("height_mm", "mm", 60.0, 600.0,
                      note="INNER body height"),
        ParameterSpec("bleed_mm", "mm", 2.0, 5.0, default=3.0),
        ParameterSpec("safe_margin_mm", "mm", 3.0, 8.0, default=4.0),
        ParameterSpec("glue_tab_mm", "mm", 6.0, 15.0, default=12.0),
        ParameterSpec("board_thickness_mm", "mm", 0.3, 1.0, default=0.5),
    ),
    flap_capabilities=frozenset({
        "top_tuck_flap", "bottom_tuck_flap", "top_dust_flaps",
        "bottom_dust_flaps", "cubic_shoulder_curves", "tapered_glue_flap",
        "tuck_base_entry_slits", "per_hinge_creases",
    }),
    notch_capabilities=frozenset(),
    bleed_behavior="full cut-contour offset (buffer of the union outline)",
    safe_area_behavior="body slab inset by safe_margin_mm",
    provisional=True,
    production_ready=False,
    ineligibility_code=PHYSICAL_SAMPLE_VALIDATION_REQUIRED,
    structure_status=STRUCTURE_REFERENCE_RECONSTRUCTED,
    confirmation_requires_physical_fit_pass=True,
    structural_limitations=(
        "closure topology matches the reference attachment map (opposing "
        "tucks: top on main A, bottom on main B); exact contours are not "
        "claimable without the reference vector file",
        "panel allowances follow the adapted source's external = inner + 2t "
        "convention; only a physical sample or supplier die resolves it",
        "closure verified geometrically and in a folded diagnostic, never "
        "physically — FIT_PASS on a 100%-scale sample required",
    ),
    notes=(
        "PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED — NOT APPROVED "
        "FOR MASS PRODUCTION.",
        "OPPOSING TUCK / REFERENCE-MATCHED PROVISIONAL: top major tuck on "
        "MAIN PANEL A, bottom major tuck on MAIN PANEL B.",
        "Geometry adapted (MIT, attribution preserved) from "
        "DDR68/Rhino_Packaging_Toolkit ECMA_A20_20_03_01.py; upstream "
        "undefined dust_d fixed — see FORMULA_PROVENANCE.",
        "A registered customer- or manufacturer-supplied dieline outranks "
        "this archetype automatically.",
    ),
    geometry_module="apps.dielines.geometry.opposed_tuck",
    preset="REFERENCE_OPPOSED_TUCK_CARTON_V0_1",
))


#: [Owner, 2026-10-28, CURRENT_DECISIONS.md "the stand die to production grade": "The registry marks the template 1.0
#: only when all of these pass" — the fold, strength and sightline checks and the comparison against each measured
#: reference.] The single-product counter display, rebuilt from the conventions measured on the house's display dies
#: (apps/dielines/docs/research/counter_display_references.json) by apps.dielines.geometry.counter_display, qualified by
#: apps/dielines/tests/test_counter_display.py (every case of its matrix passes all four). §BH70(3) (LIVE): a physical
#: sample is never required to finish a design; what the sample still shows is named in structural_limitations.
#: Registered as a pinned version, not current: it takes no carton W/D/H, so no carton chooser offers it; the round's
#: stand adapter resolves it by its number. It is the stand die's one version: 0.1 (the Day 12 family display) went to
#: archive/ in the consolidation of 2026-10-28, so an unpinned resolve of counter_tray_header fails closed.
COUNTER_DISPLAY = _register(TemplateDefinition(
    template_id="counter_tray_header",
    version="1.0",
    label="Counter display with header — single product (production)",
    panel_sequence=(),
    dimension_semantics={
        "width_mm": "outer footprint width (floor + 2 × caliper)",
        "depth_mm": "outer footprint depth (floor + 2 × caliper)",
        "height_mm": "outer height: floor, back panel and header (the header the back panel's own board)",
    },
    closure_type="glued_corner_tray_locked_header",
    glue_seam_position="four tapered corner flaps glued inside the side walls; the insert's feet to the floor",
    board_compensation_model=BOARD_MODEL_INSIDE_PLUS_CALIPER,
    required_parameters=(),
    flap_capabilities=frozenset({"corner_glue_flaps", "glue_zones", "doubled_header", "header_lock_tab",
                                 "insert_lock_tabs", "retention_tongues", "row_seats"}),
    notch_capabilities=frozenset({"header_lock_slot", "insert_lock_slots"}),
    bleed_behavior="3 mm past printed faces only (mitre), 1 mm over a crease into an unprinted neighbour",
    safe_area_behavior="each printed panel inset 3 mm",
    provisional=False,
    production_ready=True,
    structure_status=STRUCTURE_MEASURED,
    structural_limitations=(
        "conventions measured on eight house display dies; the glued-corner construction and the header doubled from "
        "the back panel are this engine's own (the comparison report says where and why)",
        "not modelled, for the folded sample to show: the board's stiffness under the header, the glue's strength, "
        "the retention tongues' grip, a loaded stand's sway under a push",
        "CF2 is written to the format's published layout and has not been opened in a die shop's CAD",
    ),
    notes=("Owner, 2026-10-28: the stand die to production grade; the shopper-facing header leaf is the printed "
           "'header front'.",),
    geometry_module="apps.dielines.geometry.counter_display",
), current=False)


#: [Owner, 2026-10-31, part 2.] The stand family: each template pinned by its number, as 1.0 is, so no carton chooser offers one. Their
#: construction and proofs are stand_templates and stand_fold; their rules docs/research/stands/rules. Provisional until a folded sample.
STAND_FAMILY = tuple(_register(dataclasses.replace(
    COUNTER_DISPLAY, template_id=template_id, version=version, label=label + " (the family)", closure_type="locks_and_trapped_flaps",
    glue_seam_position=glue, flap_capabilities=frozenset({"trapped_corner_flaps", "double_walls", "slot_in_header", "stair_inserts"}),
    notch_capabilities=frozenset({"floor_slots", "rim_slots", "inner_leaf_slots"}), provisional=True, production_ready=False,
    structure_status=STRUCTURE_PROVISIONAL, structural_limitations=(
        "our own rules where the web gave none (docs/research/stands/rules/_common.json): a folded sample decides them",
        "CF2 read back by our own reader only: no die maker's CAD has opened it"),
    notes=("Owner, 2026-10-31: part 2, the stand family.",), geometry_module="apps.dielines.geometry.stand_templates"), current=False)
    for template_id, version, label, glue in (
        ("counter_tray_header", "2.0", "Counter tray with header", "none"), ("stepped_tiered", "1.0", "Stepped or tiered counter display", "none"),
        ("lid_header_tray", "1.0", "Lid-converts-to-header tray", "four small zones on the corner flaps"),
        ("slanted_front", "1.0", "Slanted or angled counter display", "none"), ("tester_unit", "1.0", "Tester unit", "none")))


# --- public API -----------------------------------------------------------------


def resolve(template_id: str, version: str | None = None) -> TemplateDefinition:
    """Return the definition for ``template_id``. Fails closed.

    ``version`` None resolves the CURRENT published version. A pinned
    version must exist exactly — a caller that recorded 1.0 keeps getting
    1.0 (historical reproduction), never a silently newer geometry.
    """
    tid = (template_id or "").strip()
    if tid not in _CURRENT and (version is None or not any(t == tid for t, _v in _REGISTRY)):
        # a template published only by its number (counter_tray_header 1.0, the stand die) resolves pinned, never
        # unpinned: no current version is ever guessed
        raise UnknownTemplate(
            f"unknown packaging template {template_id!r}; registered: "
            f"{sorted(_CURRENT)}"
        )
    if version is None:
        return _REGISTRY[(tid, _CURRENT[tid])]
    defn = _REGISTRY.get((tid, version))
    if defn is None:
        raise TemplateVersionMismatch(
            f"{tid} has no published version {version!r}; published: "
            f"{sorted(v for (t, v) in _REGISTRY if t == tid)}"
        )
    return defn


def is_registered(template_id: str) -> bool:
    return (template_id or "").strip() in _CURRENT


def current_version(template_id: str) -> str:
    return resolve(template_id).version


def all_templates(*, current_only: bool = True) -> list[TemplateDefinition]:
    """Published definitions. ``current_only`` (default) hides superseded
    versions. NOTE: this still includes production-INELIGIBLE current
    versions (a provisional structure is current but unusable) — the
    production chooser must use :func:`production_templates`."""
    if current_only:
        return [_REGISTRY[(t, v)] for t, v in sorted(_CURRENT.items())]
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def production_templates() -> list[TemplateDefinition]:
    """The ONLY templates a production chooser may offer: current versions
    that are production-eligible. Excludes superseded versions (defective
    creases) and provisional structures (unmeasured closure mechanics)."""
    return [d for d in all_templates() if d.production_ready]


# --- 2A-9E new-task selection policy ----------------------------------------
#: New-selection classifications (distinct from production_ready / structure
#: status — those govern Gate 2, these govern what a NEW-task chooser shows).
NEW_SELECTION_RECOMMENDED = "RECOMMENDED_CORRECTED_VERSION"
NEW_SELECTION_LEGACY = "LEGACY_REPRODUCTION_ONLY"
SUPERSEDED_FOR_NEW_SELECTION = "SUPERSEDED_FOR_NEW_SELECTION_BY_1_2"

#: EXPLICIT mapping (never inferred from a version count): a template_id whose
#: NEW-task recommendation is a corrected version. A future 1.3 must be added
#: here deliberately; it never changes control flow by accident.
_RECOMMENDED_CORRECTED_VERSION = {
    "straight_tuck_end_carton": "1.2",
    "reverse_tuck_end_carton": "1.2",
}
#: [his final goal, 2026-10-05, B2: "A PRINT-READY DIELINE ... It must go to a printer without being edited."] the
#: version a new design's carton is drawn at — 1.3: 1.2's tuck across the depth, its tuck folds creased between their
#: lock slits, a thumb notch where the lid closes (the retired structure chooser's recommendation above is untouched)
_PRINT_READY_VERSION = {
    # [his second goal of 2026-10-06, item 2] 1.4: drawn to the trade's written rules (it was 1.3)
    "straight_tuck_end_carton": "1.4",
    "reverse_tuck_end_carton": "1.4",
}
#: [his final goal, B2] the published domain a version is qualified over: 1.3 keeps 1.2's closure and its domain — its
#: tuck folds, lock slits and thumb notch change no constraint of it
QUALIFIED_AS = {"1.3": "1.2"}


def print_ready_version(template_id: str) -> str | None:
    """[His final goal, B2.] The version a new design's carton of ``template_id`` is drawn at."""
    return _PRINT_READY_VERSION.get((template_id or "").strip())


def recommended_corrected_version(template_id: str) -> str | None:
    """The version a NEW task should be steered toward for this template,
    or None if the current production version is already the recommendation."""
    return _RECOMMENDED_CORRECTED_VERSION.get((template_id or "").strip())


def _new_selection_entry(defn: TemplateDefinition, klass: str,
                         *, recommended_version: str = "",
                         superseded_note: str = "",
                         legacy_advanced: bool = False) -> dict:
    d = defn.to_dict()
    d["new_selection_class"] = klass
    d["recommended_version"] = recommended_version
    d["superseded_for_new_selection"] = superseded_note
    d["legacy_advanced"] = legacy_advanced
    d["physical_validation_required"] = (
        defn.ineligibility_code == PHYSICAL_SAMPLE_VALIDATION_REQUIRED)
    return d


def new_selection_templates() -> list[dict]:
    """Candidate templates for a NEW-task chooser (2A-9E §1/§3).

    Distinct from :func:`production_templates` (which stays guarded to
    production-ready measured structures). For a template_id with a declared
    recommended-corrected-version, this surfaces that version as
    RECOMMENDED_CORRECTED_VERSION AND the current version as
    LEGACY_REPRODUCTION_ONLY (a clearly-labelled advanced legacy option).
    Templates without the mapping are offered as their production current
    version, unchanged.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for defn in all_templates():
        tid = defn.template_id
        if tid in seen:
            continue
        seen.add(tid)
        rec_ver = recommended_corrected_version(tid)
        if rec_ver:
            rec = _REGISTRY.get((tid, rec_ver))
            if rec is not None:
                out.append(_new_selection_entry(
                    rec, NEW_SELECTION_RECOMMENDED,
                    recommended_version=rec_ver))
            # the current (legacy) version, advanced-only
            out.append(_new_selection_entry(
                defn, NEW_SELECTION_LEGACY,
                superseded_note=SUPERSEDED_FOR_NEW_SELECTION,
                legacy_advanced=True))
        elif defn.production_ready:
            out.append(_new_selection_entry(defn, "PRODUCTION_CURRENT"))
    return out


def is_production_eligible(template_id: str, version: str | None = None) -> bool:
    try:
        return resolve(template_id, version).production_ready
    except (UnknownTemplate, TemplateVersionMismatch):
        return False


def versions_of(template_id: str) -> list[str]:
    return sorted(v for (t, v) in _REGISTRY if t == (template_id or "").strip())


def generic_template_ids() -> frozenset[str]:
    """Templates that carry no customer-specific structural evidence. These
    may only be used when the user explicitly accepts a generic structure."""
    return frozenset({
        "straight_tuck_end_carton", "reverse_tuck_end_carton",
        "tuck_top_auto_bottom_carton",
    })


def is_generic(template_id: str) -> bool:
    return template_id in generic_template_ids()


def geometry_hash(template_id: str, version: str, parameters: dict) -> str:
    """Stable hash of (template, version, parameters) — the identity of a
    generated structure. A restart that produces a different hash has
    silently changed the die, which the confirmation gate must catch."""
    import hashlib
    import json
    payload = json.dumps(
        {"template": template_id, "version": version,
         "parameters": {k: parameters[k] for k in sorted(parameters)}},
        sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


__all__ = [
    "TemplateDefinition",
    "ParameterSpec",
    "UnknownTemplate",
    "TemplateVersionMismatch",
    "resolve",
    "is_registered",
    "all_templates",
    "production_templates",
    "new_selection_templates",
    "recommended_corrected_version",
    "NEW_SELECTION_RECOMMENDED",
    "NEW_SELECTION_LEGACY",
    "SUPERSEDED_FOR_NEW_SELECTION",
    "PHYSICAL_SAMPLE_VALIDATION_REQUIRED",
    "PHYSICAL_SAMPLE_INFORMATION",
    "generic_template_ids",
    "is_generic",
    "geometry_hash",
    "CLOSURE_STRAIGHT_TUCK",
    "CLOSURE_REVERSE_TUCK",
    "CLOSURE_TUCK_TOP_AUTO_BOTTOM",
    "SEAM_ON_MAIN",
    "SEAM_ON_SIDE",
]

# The engine's dispatch table and this registry must never drift: every
# registered template must be buildable, and every buildable style must be
# declared. Enforced by test_registry.py::test_registry_matches_engine_dispatch.
