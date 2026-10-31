"""Versioned parameter contracts (2A-9B §1).

Every parameter of an archetype is declared with its KIND, so nothing can
hide a task-specific measurement inside the generator:

    USER        supplied per die (dimensions, board, glue, bleed, safe)
    CONSTANT    frozen with the template VERSION (changing one = new version)
    DERIVED     computed from user parameters + constants by a stated formula
    ALLOWANCE   manufacturing compensation built from board thickness

The contract is data, published with the qualification report; the domain
constraints (domain.py) and the generator consume the same values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

KIND_USER = "USER"
KIND_CONSTANT = "TEMPLATE_CONSTANT"
KIND_DERIVED = "DERIVED"
KIND_ALLOWANCE = "MANUFACTURING_ALLOWANCE"


@dataclass(frozen=True)
class ParameterEntry:
    name: str
    kind: str
    unit: str
    description: str
    minimum: float | None = None
    maximum: float | None = None
    default: float | None = None
    value: float | None = None          # constants only
    formula: str = ""                   # derived/allowance only


@dataclass(frozen=True)
class ParameterContract:
    schema_version: str
    template_key: str
    entries: tuple[ParameterEntry, ...] = field(default=())

    def by_kind(self, kind: str) -> list[ParameterEntry]:
        return [e for e in self.entries if e.kind == kind]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "template_key": self.template_key,
            "parameters": [asdict(e) for e in self.entries],
        }


#: reference_opposed_tuck_carton/0.1 — the full §1 parameter set. The
#: constants are the DDR68-adapted template values frozen with version 0.1;
#: changing any of them requires publishing 0.2 (§9).
OPPOSED_TUCK_CONTRACT = ParameterContract(
    schema_version="dieline_parameter_contract/1.0",
    template_key="reference_opposed_tuck_carton/0.1",
    entries=(
        # --- user-controlled -------------------------------------------------
        ParameterEntry("width_mm", KIND_USER, "mm",
                       "INNER main-panel width", 12.0, 300.0),
        ParameterEntry("depth_mm", KIND_USER, "mm",
                       "INNER side-panel depth", 12.0, 300.0),
        ParameterEntry("height_mm", KIND_USER, "mm",
                       "INNER body height", 60.0, 600.0),
        ParameterEntry("board_thickness_mm", KIND_USER, "mm",
                       "board caliper t", 0.3, 1.0, default=0.5),
        ParameterEntry("glue_tab_mm", KIND_USER, "mm",
                       "glue-flap width G", 6.0, 15.0, default=12.0),
        ParameterEntry("bleed_mm", KIND_USER, "mm",
                       "bleed offset", 2.0, 5.0, default=3.0),
        ParameterEntry("safe_margin_mm", KIND_USER, "mm",
                       "safe-area inset", 3.0, 8.0, default=4.0),
        # --- template constants (version 0.1) --------------------------------
        ParameterEntry("hook_mm", KIND_CONSTANT, "mm",
                       "major-tuck depth past the fold (tuck lip)",
                       value=18.0),
        ParameterEntry("shoulder_control_k", KIND_CONSTANT, "ratio",
                       "quadratic-Bezier shoulder control position "
                       "(shoulder radius analogue)", value=0.635),
        ParameterEntry("chamfer_mm", KIND_CONSTANT, "mm",
                       "corner chamfer on dust and glue flaps "
                       "(corner radius analogue)", value=3.0),
        ParameterEntry("taper_mm", KIND_CONSTANT, "mm",
                       "dust-flap free-edge taper", value=2.0),
        ParameterEntry("entry_slit_len_mm", KIND_CONSTANT, "mm",
                       "entry-slit width along the ear line", value=7.0),
        ParameterEntry("entry_slit_depth_mm", KIND_CONSTANT, "mm",
                       "entry-slit depth across the fold", value=2.5),
        ParameterEntry("flap_clearance_mm", KIND_CONSTANT, "mm",
                       "minimum folded clearance between opposing dust "
                       "flaps", value=2.0),
        ParameterEntry("min_fold_hinge_mm", KIND_CONSTANT, "mm",
                       "minimum functional tuck-fold crease span between "
                       "the entry slits", value=10.0),
        ParameterEntry("min_dust_base_mm", KIND_CONSTANT, "mm",
                       "minimum dust-flap base after chamfer + taper",
                       value=2.0),
        ParameterEntry("min_tuck_tip_mm", KIND_CONSTANT, "mm",
                       "minimum flat tuck-tip span between the shoulders",
                       value=4.0),
        ParameterEntry("min_ear_engagement_mm", KIND_CONSTANT, "mm",
                       "minimum slit depth beyond the locking ear",
                       value=0.5),
        # --- derived ---------------------------------------------------------
        ParameterEntry("external_L_mm", KIND_DERIVED, "mm",
                       "external main span", formula="width_mm + 2t"),
        ParameterEntry("external_P_mm", KIND_DERIVED, "mm",
                       "external side span", formula="depth_mm + 2t"),
        ParameterEntry("external_A_mm", KIND_DERIVED, "mm",
                       "external height", formula="height_mm + 2t"),
        ParameterEntry("closure_face_mm", KIND_DERIVED, "mm",
                       "tuck closure-face depth (both ends)",
                       formula="P - 2t = depth_mm"),
        ParameterEntry("major_tuck_reach_mm", KIND_DERIVED, "mm",
                       "tuck zone from hinge to tip",
                       formula="P - 2t + hook_mm"),
        ParameterEntry("dust_flap_depth_mm", KIND_DERIVED, "mm",
                       "dust-flap depth",
                       formula="(P + hook_mm - t) / 2, capped at L/2"),
        ParameterEntry("panel_main_a_mm", KIND_DERIVED, "mm",
                       "main A score-to-score", formula="L - t"),
        ParameterEntry("panel_side_a_mm", KIND_DERIVED, "mm",
                       "side A score-to-score", formula="P"),
        ParameterEntry("panel_main_b_mm", KIND_DERIVED, "mm",
                       "main B score-to-score", formula="L"),
        ParameterEntry("panel_side_b_mm", KIND_DERIVED, "mm",
                       "side B free-edge span", formula="P - t"),
        # --- manufacturing allowances ----------------------------------------
        ParameterEntry("locking_ear_mm", KIND_ALLOWANCE, "mm",
                       "locking-ear projection past the tuck fold",
                       formula="2t"),
        ParameterEntry("ear_slit_crossing_mm", KIND_ALLOWANCE, "mm",
                       "slit depth beyond the ear (lock engagement)",
                       formula="entry_slit_depth_mm - 2t"),
        ParameterEntry("closure_stack_mm", KIND_ALLOWANCE, "mm",
                       "board stack absorbed per closure end",
                       formula="2t (ear) + t (main compensation)"),
        ParameterEntry("compensated_crease_offset_mm", KIND_ALLOWANCE, "mm",
                       "main A top / main B bottom crease offset",
                       formula="+t / -t"),
        ParameterEntry("score_compression_mm", KIND_ALLOWANCE, "mm",
                       "score compression — NOT modelled in 0.1; recorded "
                       "as an assumption for the physical sample",
                       value=0.0),
        ParameterEntry("headspace_mm", KIND_ALLOWANCE, "mm",
                       "headspace — none added; inner height is the "
                       "customer fact", value=0.0),
    ),
)

_CONTRACTS = {OPPOSED_TUCK_CONTRACT.template_key: OPPOSED_TUCK_CONTRACT}


def register_contract(contract: ParameterContract) -> ParameterContract:
    _CONTRACTS[contract.template_key] = contract
    return contract


def contract_for(template_key: str) -> ParameterContract | None:
    return _CONTRACTS.get(template_key)


__all__ = ["ParameterEntry", "ParameterContract", "OPPOSED_TUCK_CONTRACT",
           "contract_for", "register_contract", "KIND_USER", "KIND_CONSTANT", "KIND_DERIVED",
           "KIND_ALLOWANCE"]
