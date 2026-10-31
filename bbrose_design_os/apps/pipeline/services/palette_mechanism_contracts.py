"""PALT-M3 — versioned mechanism strategy contracts.

A mechanism strategy declares WHERE its envelope is spent, which is the
question PALT-M2 answered for only one case. Three sinks exist:

* ``internal_band_mm`` — a reserved band inside the tray (steals pan field)
* ``wall_add_mm``      — extra thickness on the affected case wall
* ``external_add_mm``  — material outside the case footprint

The PALT-M2 conclusion ("116 x 92 is infeasible") tested only the internal
reserved band. Owner correction: that is
``INFEASIBLE_UNDER_CURRENT_RESERVED_BAND_STRATEGY`` and **not proven
infeasible under all mechanism strategies**.

Orientation is likewise not bound to physics: the solver keeps a
normalized local frame (hinge at +Y) and the contract maps it onto a
physical edge.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.pipeline.services.palette_contracts import (
    Dim, PaletteContractError, default)

SCHEMA = "palette_mechanism_strategy/1.0"

HINGE_STRATEGIES = (
    "INTERNAL_RESERVED_BAND_PIN_HINGE",
    "WALL_INTEGRATED_PIN_HINGE",
    "EXTERNAL_BARREL_HINGE",
    "LIVING_HINGE",
    "CUSTOM_MECHANISM_PLACEHOLDER",
)
CLASP_STRATEGIES = (
    "INTERNAL_RESERVED_BAND_SNAP_CLASP",
    "WALL_INTEGRATED_SNAP_CLASP",
    "MAGNETIC_CLOSURE",
    "FRICTION_CLOSURE",
    "CUSTOM_MECHANISM_PLACEHOLDER",
)
RETENTION_STRATEGIES = (
    "ADHESIVE_FIXED",
    "PRESS_FIT",
    "MAGNETIC_REFILL",
    "RETENTION_LIP",
    "CUSTOM_RETENTION_PLACEHOLDER",
)

EDGES = ("TOP_EDGE", "BOTTOM_EDGE", "LEFT_EDGE", "RIGHT_EDGE")
ORIENTATIONS = ("PORTRAIT", "LANDSCAPE")


@dataclass(frozen=True)
class MechanismEnvelope:
    """Where a strategy spends its space. Every figure is a
    DESIGN_DEFAULT until a manufacturer drawing replaces it."""

    internal_band: Dim
    wall_add: Dim
    external_add: Dim
    height_add: Dim
    requires_material: str | None = None
    unknowns: tuple = ()

    @property
    def is_unknown(self) -> bool:
        return bool(self.unknowns) and self.internal_band.mm == 0 \
            and self.wall_add.mm == 0 and self.external_add.mm == 0


def _env(internal=0.0, wall=0.0, external=0.0, height=0.0,
         material=None, unknowns=(), note=""):
    return MechanismEnvelope(
        internal_band=default(internal, note or None),
        wall_add=default(wall), external_add=default(external),
        height_add=default(height), requires_material=material,
        unknowns=tuple(unknowns))


# --- hinge strategies ------------------------------------------------------
# every numeric figure below is a DESIGN_DEFAULT: no manufacturer drawing
# was obtainable (PALT-M1 research), so these are engineering estimates.

HINGE_ENVELOPES = {
    "INTERNAL_RESERVED_BAND_PIN_HINGE": _env(
        internal=6.0, height=0.0,
        note="pin barrel sits inside the tray, stealing pan field",
        unknowns=("hinge pin diameter", "gudgeon dimensions")),
    "WALL_INTEGRATED_PIN_HINGE": _env(
        wall=1.2, height=0.0,
        note="barrel absorbed into a locally thickened rear wall",
        unknowns=("achievable wall thickening without sink marks",
                  "minimum pin engagement")),
    "EXTERNAL_BARREL_HINGE": _env(
        external=3.5, height=0.0,
        note="barrel outside the footprint; costs external size, not "
             "internal field",
        unknowns=("external barrel diameter", "visual acceptability")),
    "LIVING_HINGE": _env(
        wall=0.6, height=0.0, material="PP",
        note="requires PP (owner: PP allowed for intentional living "
             "hinges); ABS will fatigue and crack",
        unknowns=("fatigue life", "hinge web thickness")),
    "CUSTOM_MECHANISM_PLACEHOLDER": _env(
        unknowns=("entire envelope undefined",),
        note="placeholder — fails closed until defined"),
}

CLASP_ENVELOPES = {
    "INTERNAL_RESERVED_BAND_SNAP_CLASP": _env(
        internal=5.0,
        note="snap detent inside the tray front band",
        unknowns=("detent geometry", "retention force")),
    "WALL_INTEGRATED_SNAP_CLASP": _env(
        wall=1.0,
        note="detent formed in a locally thickened front wall",
        unknowns=("retention force", "wear over cycles")),
    "MAGNETIC_CLOSURE": _env(
        wall=0.8, height=0.4,
        note="magnet pockets in lid and base; adds a little height",
        unknowns=("magnet grade", "pull force", "magnet thickness")),
    "FRICTION_CLOSURE": _env(
        note="no dedicated feature; relies on tight tolerance",
        unknowns=("achievable tolerance", "closure feel", "loosening over "
                  "cycles")),
    "CUSTOM_MECHANISM_PLACEHOLDER": _env(
        unknowns=("entire envelope undefined",),
        note="placeholder — fails closed until defined"),
}

RETENTION_ENVELOPES = {
    "ADHESIVE_FIXED": _env(
        height=0.15,
        note="adhesive film under the pan; no pocket growth",
        unknowns=("adhesive thickness in production",)),
    "PRESS_FIT": _env(
        wall=0.0, height=0.0,
        note="interference ribs in the pocket wall",
        unknowns=("interference fit vs the WIDE pan tolerance — the patent "
                  "source warns against interference fits",)),
    "MAGNETIC_REFILL": _env(
        height=0.8,
        note="magnet or steel disc under each pan; requires removal "
             "clearance",
        unknowns=("magnet thickness", "pull force", "removal ergonomics")),
    "RETENTION_LIP": _env(
        note="moulded lip overhangs the pan rim",
        unknowns=("lip overhang", "visible pan reduction")),
    "CUSTOM_RETENTION_PLACEHOLDER": _env(
        unknowns=("entire envelope undefined",),
        note="placeholder — fails closed until defined"),
}

# pocket growth per side caused by the retention strategy (mm)
RETENTION_POCKET_ADD = {
    "ADHESIVE_FIXED": 0.0,
    "PRESS_FIT": 0.20,
    "MAGNETIC_REFILL": 0.40,
    "RETENTION_LIP": 0.60,
    "CUSTOM_RETENTION_PLACEHOLDER": None,     # unknown → fails closed
}


@dataclass(frozen=True)
class MechanismStrategySpec:
    """A complete mechanism choice plus its physical orientation."""

    hinge_strategy: str
    clasp_strategy: str
    retention_strategy: str
    hinge_edge: str = "TOP_EDGE"
    clasp_edge: str = "BOTTOM_EDGE"
    case_orientation: str = "LANDSCAPE"
    opening_direction: str = "AWAY_FROM_USER"
    schema: str = SCHEMA
    notes: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if self.hinge_strategy not in HINGE_STRATEGIES:
            raise PaletteContractError(
                f"unknown hinge strategy {self.hinge_strategy!r}")
        if self.clasp_strategy not in CLASP_STRATEGIES:
            raise PaletteContractError(
                f"unknown clasp strategy {self.clasp_strategy!r}")
        if self.retention_strategy not in RETENTION_STRATEGIES:
            raise PaletteContractError(
                f"unknown retention strategy {self.retention_strategy!r}")
        for edge in (self.hinge_edge, self.clasp_edge):
            if edge not in EDGES:
                raise PaletteContractError(f"unknown edge {edge!r}")
        if self.case_orientation not in ORIENTATIONS:
            raise PaletteContractError(
                f"unknown orientation {self.case_orientation!r}")
        if self.hinge_edge == self.clasp_edge:
            raise PaletteContractError(
                "hinge and clasp cannot occupy the same edge")

    # --- axis mapping: which physical axis each mechanism consumes -------
    @staticmethod
    def _axis(edge: str) -> str:
        """TOP/BOTTOM edges consume DEPTH; LEFT/RIGHT consume WIDTH."""
        return "depth" if edge in ("TOP_EDGE", "BOTTOM_EDGE") else "width"

    @property
    def hinge_axis(self) -> str:
        return self._axis(self.hinge_edge)

    @property
    def clasp_axis(self) -> str:
        return self._axis(self.clasp_edge)

    @property
    def hinge_envelope(self) -> MechanismEnvelope:
        return HINGE_ENVELOPES[self.hinge_strategy]

    @property
    def clasp_envelope(self) -> MechanismEnvelope:
        return CLASP_ENVELOPES[self.clasp_strategy]

    @property
    def retention_envelope(self) -> MechanismEnvelope:
        return RETENTION_ENVELOPES[self.retention_strategy]

    @property
    def retention_pocket_add_mm(self):
        return RETENTION_POCKET_ADD[self.retention_strategy]

    @property
    def unknowns(self) -> list:
        out = []
        for name, env in (("hinge", self.hinge_envelope),
                          ("clasp", self.clasp_envelope),
                          ("retention", self.retention_envelope)):
            out.extend(f"{name}: {u}" for u in env.unknowns)
        return out

    def material_conflict(self, case_material: str) -> str | None:
        need = self.hinge_envelope.requires_material
        if need and case_material.upper() != need:
            return (f"{self.hinge_strategy} requires {need}; case material "
                    f"is {case_material}")
        return None


PALT_P1_BASELINE = MechanismStrategySpec(
    hinge_strategy="INTERNAL_RESERVED_BAND_PIN_HINGE",
    clasp_strategy="INTERNAL_RESERVED_BAND_SNAP_CLASP",
    retention_strategy="ADHESIVE_FIXED",
    hinge_edge="TOP_EDGE", clasp_edge="BOTTOM_EDGE",
    case_orientation="LANDSCAPE",
    notes=("owner baseline: conventional pin hinge, conventional snap "
           "clasp, fixed non-refillable pans, mirror included",),
)

AUTHORITY_STATEMENT = {
    "MECHANISM_ENVELOPE_AUTHORITY": "DESIGN_DEFAULT — engineering estimates; "
                                    "no manufacturer drawing was obtainable",
    "MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
    "note": "a strategy comparison narrows the design space; it does not "
            "confirm that any strategy is manufacturable as drawn",
}
