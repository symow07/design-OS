"""Closure capability model (2A-9C slice 0).

Every archetype declares its closure mechanics explicitly — the invariants,
the folded simulator and the collision checks read THESE declarations
instead of assuming entry-slit ears everywhere. Nothing here weakens an
invariant: a declared capability turns its checks ON; an undeclared one
switches to that closure family's own checks, never to "no checks".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

# closure orientations
ORIENT_OPPOSING = "OPPOSING_TUCK"           # top on main A, bottom on main B
ORIENT_STRAIGHT = "STRAIGHT_TUCK"           # both openings face the same way
ORIENT_REVERSE = "REVERSE_TUCK"             # openings face opposite ways

# locking mechanisms
LOCK_ENTRY_SLIT_EARS = "ENTRY_SLIT_EARS"    # 2t ears snap into L-slits
LOCK_FRICTION_NOTCHES = "FRICTION_SLIT_LOCK_NOTCHES"  # stadium slit + 2t notches

# slit types
SLIT_ENTRY_L_CUT = "ENTRY_SLIT_L_CUT"
SLIT_STADIUM_FRICTION = "STADIUM_FRICTION_SLIT"
SLIT_TUCK_BASE_ENTRY = "TUCK_BASE_ENTRY_SLIT"          # DECISION-020

# notch types
NOTCH_NONE = "NONE"
NOTCH_SHOULDER_LOCK_2T = "SHOULDER_LOCK_NOTCH_2T"      # DECISION-015
NOTCH_DUST_BASE = "DUST_BASE_NOTCH"


@dataclass(frozen=True)
class ClosureModel:
    """What this archetype's closure actually is — the review contract the
    qualification machinery checks against."""
    orientation: str
    major_tuck_count: int
    top_tuck_panel: str
    bottom_tuck_panel: str
    dust_panels: tuple[str, ...]                 # one per dust flap, in order
    locking_mechanism: str
    slit_type: str
    notch_types: tuple[str, ...] = (NOTCH_NONE,)
    #: per closure end, innermost first
    fold_sequence: tuple[str, ...] = ("dust_flap", "dust_flap", "major_tuck")
    board_compensation_model: str = "external_equals_inner_plus_2t"
    collision_model: str = "opposing_tuck_folded"
    physical_validation_requirement: str = \
        "PHYSICAL_SAMPLE_VALIDATION_REQUIRED"
    #: entry-slit closures: cut segments expected in coords.slit_lines
    expected_slit_line_count: int = 0
    #: friction closures: stadium cutouts expected per active tuck
    expected_stadium_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FoldedSimulationSpec:
    """How the folded simulator should articulate this closure.

    ``closure_fold_depth_formula`` names the depth (from the tuck hinge)
    where the flap functionally folds over the opening; the callable
    receives the coords and returns mm.
    """
    top_label: str
    bottom_label: str
    lock_marker: str            # "slit_ear" | "friction_slit" | "lock_notch"
    fold_depth: object = None   # callable(coords) -> mm
    insertion_note: str = ""


OPPOSED_TUCK_CLOSURE = ClosureModel(
    orientation=ORIENT_OPPOSING,
    major_tuck_count=2,
    top_tuck_panel="main_a",
    bottom_tuck_panel="main_b",
    dust_panels=("side_a", "side_b", "side_a", "side_b"),
    locking_mechanism=LOCK_ENTRY_SLIT_EARS,
    slit_type=SLIT_ENTRY_L_CUT,
    notch_types=(NOTCH_NONE,),
    collision_model="opposing_tuck_folded",
    expected_slit_line_count=8,
)

STE_LEGACY_CLOSURE = ClosureModel(
    orientation=ORIENT_STRAIGHT,
    major_tuck_count=2,
    top_tuck_panel="back",
    bottom_tuck_panel="front",
    dust_panels=("side_left", "side_right", "side_left", "side_right"),
    locking_mechanism=LOCK_FRICTION_NOTCHES,
    slit_type=SLIT_STADIUM_FRICTION,
    notch_types=(NOTCH_SHOULDER_LOCK_2T, NOTCH_DUST_BASE),
    collision_model="ratio_tuck_folded",
    expected_stadium_count=2,      # one friction slit per active tuck
)

RTE_LEGACY_CLOSURE = ClosureModel(
    orientation=ORIENT_REVERSE,
    major_tuck_count=2,
    top_tuck_panel="front",
    bottom_tuck_panel="back",
    dust_panels=("side_left", "side_right", "side_left", "side_right"),
    locking_mechanism=LOCK_FRICTION_NOTCHES,
    slit_type=SLIT_STADIUM_FRICTION,
    notch_types=(NOTCH_SHOULDER_LOCK_2T, NOTCH_DUST_BASE),
    collision_model="ratio_tuck_folded",
    expected_stadium_count=2,
)

SKYNTE_CLOSURE = ClosureModel(
    orientation=ORIENT_STRAIGHT,
    major_tuck_count=2,
    top_tuck_panel="back",
    bottom_tuck_panel="front",
    dust_panels=("side_left", "side_right", "side_left", "side_right"),
    locking_mechanism=LOCK_FRICTION_NOTCHES,
    slit_type=SLIT_TUCK_BASE_ENTRY,
    notch_types=(NOTCH_SHOULDER_LOCK_2T, NOTCH_DUST_BASE),
    fold_sequence=("dust_flap", "dust_flap", "major_tuck"),
    collision_model="side_seam_folded",
    expected_stadium_count=2,
)

__all__ = [
    "ClosureModel", "FoldedSimulationSpec",
    "OPPOSED_TUCK_CLOSURE", "STE_LEGACY_CLOSURE", "RTE_LEGACY_CLOSURE",
    "SKYNTE_CLOSURE",
    "ORIENT_OPPOSING", "ORIENT_STRAIGHT", "ORIENT_REVERSE",
    "LOCK_ENTRY_SLIT_EARS", "LOCK_FRICTION_NOTCHES",
    "SLIT_ENTRY_L_CUT", "SLIT_STADIUM_FRICTION", "SLIT_TUCK_BASE_ENTRY",
    "NOTCH_NONE", "NOTCH_SHOULDER_LOCK_2T", "NOTCH_DUST_BASE",
]
