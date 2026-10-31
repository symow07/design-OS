"""PALT-M2 — versioned palette geometry contracts.

Deterministic, non-rendering foundation for palette geometry. Every
dimension carries value, unit, provenance, confidence, authority and (when
known) tolerance — no bare floats anywhere in a spec.

Authority law (inherited from container_geometry/1.0 and extended by the
owner's PALT-M1 decision):

* GEOMETRY_AUTHORITY            — shape/dimensions/identity
* MATERIAL_SPECIFICATION_AUTHORITY / COLOUR_AUTHORITY — never here
* MANUFACTURING_AUTHORITY       — NOT_ESTABLISHED, always

Owner correction 2026-08-05 (binding): module equivalence
(blush ~ 3 eye modules, cream ~ 2, brow = 1) is a
``CALCULATED_LAYOUT_HEURISTIC`` — never a MANUFACTURER_STANDARD,
INDUSTRY_STANDARD or PRODUCTION_RULE. Every module must resolve to
explicit dimensions, and the layout kernel supports direct
dimension-based placement as a first-class mode.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "palette_geometry/1.0"

# ---------------------------------------------------------------------------
# provenance / authority vocabularies (fail-closed)

PROVENANCE = ("ONLINE_REPORTED", "CALCULATED", "DESIGN_DEFAULT",
              "OWNER_CONFIRMED", "MANUFACTURER_CONFIRMED")
CONFIDENCE = ("HIGH", "MEDIUM", "LOW")
AUTHORITY = (
    "OWNER_MEASURED", "OWNER_CONFIRMED", "ONLINE_EXACT_MATCH",
    "ONLINE_ANALOGOUS_REFERENCE", "CALCULATED_FROM_OWNER_DATA",
    "CALCULATED_LAYOUT_HEURISTIC", "VISUAL_ESTIMATE_FROM_PHOTO",
    "GENERIC_RENDERING_DEFAULT", "VISUALIZATION_ONLY_GEOMETRY",
    "MANUFACTURER_TECHNICAL_DRAWING", "UNKNOWN")

CASE_SHAPES = ("RECTANGLE", "ROUNDED_RECTANGLE", "SQUARE", "CIRCLE",
               "OVAL", "POLYGON", "CUSTOM_SILHOUETTE")
PAN_SHAPES = ("CIRCLE", "SQUARE", "ROUNDED_RECTANGLE", "RECTANGLE",
              "OVAL", "CUSTOM_SILHOUETTE")
LAYOUT_MODES = ("MODULE_LATTICE", "ABSOLUTE_DIMENSIONAL_LAYOUT")
HINGE_FAMILIES = ("NONE", "PIN_HINGE", "SNAP_HINGE", "LIVING_HINGE",
                  "EXTERNAL_BARREL")
CLASP_FAMILIES = ("NONE", "MECHANICAL_DETENT", "MAGNETIC", "SLIDING_LOCK")
MIRROR_COVERAGE = ("NONE", "LID_FULL", "LID_PARTIAL", "SEPARATE_PANEL")


class PaletteContractError(ValueError):
    """Raised for any invalid or unknown contract value (fail-closed)."""


@dataclass(frozen=True)
class Dim:
    """A dimension that can never lose its provenance."""

    value: float
    unit: str = "mm"
    provenance: str = "DESIGN_DEFAULT"
    confidence: str = "LOW"
    authority: str = "GENERIC_RENDERING_DEFAULT"
    tolerance_mm: float | None = None
    note: str | None = None

    def __post_init__(self):
        if self.provenance not in PROVENANCE:
            raise PaletteContractError(
                f"unknown provenance {self.provenance!r}")
        if self.confidence not in CONFIDENCE:
            raise PaletteContractError(
                f"unknown confidence {self.confidence!r}")
        if self.authority not in AUTHORITY:
            raise PaletteContractError(
                f"unknown authority {self.authority!r}")
        if not isinstance(self.value, (int, float)) or self.value != self.value:
            raise PaletteContractError(f"non-numeric dimension {self.value!r}")
        if self.value < 0:
            raise PaletteContractError(
                f"negative dimension {self.value!r} — refused")

    @property
    def mm(self) -> float:
        return float(self.value)


def owner(value, note=None, tol=None):
    return Dim(value, provenance="OWNER_CONFIRMED", confidence="HIGH",
               authority="OWNER_CONFIRMED", note=note, tolerance_mm=tol)


def online(value, note=None, tol=None):
    return Dim(value, provenance="ONLINE_REPORTED", confidence="MEDIUM",
               authority="ONLINE_ANALOGOUS_REFERENCE", note=note,
               tolerance_mm=tol)


def calculated(value, note=None, tol=None):
    return Dim(value, provenance="CALCULATED", confidence="MEDIUM",
               authority="CALCULATED_FROM_OWNER_DATA", note=note,
               tolerance_mm=tol)


def default(value, note=None, tol=None):
    return Dim(value, provenance="DESIGN_DEFAULT", confidence="LOW",
               authority="GENERIC_RENDERING_DEFAULT", note=note,
               tolerance_mm=tol)


# ---------------------------------------------------------------------------
# component specifications


@dataclass(frozen=True)
class PalettePanSpec:
    """A pan. ``width``/``height`` are the bounding extents in the tray
    plane; a CIRCLE uses width == height == diameter."""

    pan_id: str
    shape: str
    width: Dim
    height: Dim
    depth: Dim
    removal_clearance: Dim = field(
        default_factory=lambda: default(
            0.0, "extra clearance needed to lift a refillable pan out"))
    manufacturing_tolerance: Dim = field(
        default_factory=lambda: default(
            0.30, "pressed-powder pans have WIDE tolerance (patent R10); "
                  "never an interference fit"))
    refillable: bool = False
    zone: str = "EYE"

    def __post_init__(self):
        if self.shape not in PAN_SHAPES:
            raise PaletteContractError(f"unknown pan shape {self.shape!r}")
        for d in (self.width, self.height, self.depth):
            if d.mm <= 0:
                raise PaletteContractError(
                    f"pan {self.pan_id}: non-positive dimension")

    @property
    def footprint_mm(self) -> tuple[float, float]:
        """Extent INCLUDING tolerance and removal clearance on each side."""
        pad = 2 * (self.manufacturing_tolerance.mm
                   + (self.removal_clearance.mm if self.refillable else FT.traced_zero("palette_contracts.py:footprint_mm", "guard")))
        return self.width.mm + pad, self.height.mm + pad

    @property
    def area_mm2(self) -> float:
        import math
        if self.shape == "CIRCLE":
            return math.pi * (self.width.mm / 2.0) ** 2
        if self.shape == "OVAL":
            return math.pi * (self.width.mm / 2.0) * (self.height.mm / 2.0)
        return self.width.mm * self.height.mm


@dataclass(frozen=True)
class PaletteTraySpec:
    wall_thickness: Dim
    floor_thickness: Dim
    inter_pan_gap: Dim
    outer_margin: Dim
    minimum_inter_pan_gap: Dim = field(
        default_factory=lambda: default(
            1.5, "below this, moulded pocket walls approach the ABS minimum "
                 "wall and cross-contamination risk rises"))


@dataclass(frozen=True)
class PaletteLidSpec:
    thickness: Dim
    inner_clearance: Dim = field(
        default_factory=lambda: default(
            0.5, "clearance between the closed lid face and pan top"))


@dataclass(frozen=True)
class PaletteMirrorSpec:
    present: bool
    coverage: str = "LID_FULL"
    thickness: Dim = field(
        default_factory=lambda: default(
            1.0, "mirror thickness is a documented research GAP"))
    inset: Dim = field(default_factory=lambda: default(3.0))

    def __post_init__(self):
        if self.coverage not in MIRROR_COVERAGE:
            raise PaletteContractError(
                f"unknown mirror coverage {self.coverage!r}")


@dataclass(frozen=True)
class PaletteHingeSpec:
    family: str
    zone_depth: Dim
    clearance: Dim = field(default_factory=lambda: default(0.5))
    open_angle_deg: Dim = field(
        default_factory=lambda: default(
            115.0, "obtuse is a FUNCTIONAL requirement (mirror must face the "
                   "user); the number itself is unvalidated"))

    def __post_init__(self):
        if self.family not in HINGE_FAMILIES:
            raise PaletteContractError(f"unknown hinge family {self.family!r}")


@dataclass(frozen=True)
class PaletteClaspSpec:
    family: str
    zone_depth: Dim

    def __post_init__(self):
        if self.family not in CLASP_FAMILIES:
            raise PaletteContractError(f"unknown clasp family {self.family!r}")


@dataclass(frozen=True)
class PaletteApplicatorCompartmentSpec:
    present: bool
    kind: str = "NONE"
    zone_depth: Dim = field(default_factory=lambda: default(0.0))


@dataclass(frozen=True)
class PaletteCaseSpec:
    shape: str
    outer_width: Dim
    outer_depth: Dim
    outer_height: Dim
    wall_thickness: Dim
    base_thickness: Dim
    corner_radius: Dim = field(default_factory=lambda: default(0.0))
    material: str = "ABS"
    outline_points: tuple | None = None

    def __post_init__(self):
        if self.shape not in CASE_SHAPES:
            raise PaletteContractError(f"unknown case shape {self.shape!r}")
        if self.shape == "CUSTOM_SILHOUETTE" and (
                not self.outline_points or len(self.outline_points) < 8):
            raise PaletteContractError(
                "CUSTOM_SILHOUETTE requires >=8 authoritative outline points "
                "— a custom shape exists only when evidence exists")

    @property
    def inner_width_mm(self) -> float:
        return self.outer_width.mm - 2 * self.wall_thickness.mm

    @property
    def inner_depth_mm(self) -> float:
        return self.outer_depth.mm - 2 * self.wall_thickness.mm


@dataclass(frozen=True)
class PaletteLayoutSpec:
    """Two placement modes. MODULE_LATTICE reflows structured layouts;
    ABSOLUTE_DIMENSIONAL_LAYOUT places pans by explicit coordinates."""

    mode: str
    pans: tuple
    # MODULE_LATTICE
    module_width: Dim | None = None
    module_height: Dim | None = None
    rows: int | None = None
    cols: int | None = None
    occupancy: tuple = ()          # ((pan_id, row, col, w_mod, h_mod), ...)
    # ABSOLUTE_DIMENSIONAL_LAYOUT — ((pan_id, x_mm, y_mm), ...) tray-local
    placements: tuple = ()

    def __post_init__(self):
        if self.mode not in LAYOUT_MODES:
            raise PaletteContractError(f"unknown layout mode {self.mode!r}")
        ids = [p.pan_id for p in self.pans]
        if len(ids) != len(set(ids)):
            raise PaletteContractError("duplicate pan_id in layout")
        if self.mode == "MODULE_LATTICE":
            if not (self.module_width and self.module_height
                    and self.rows and self.cols):
                raise PaletteContractError(
                    "MODULE_LATTICE requires module_width, module_height, "
                    "rows and cols")
            if not self.occupancy:
                raise PaletteContractError(
                    "MODULE_LATTICE requires occupancy")
        elif not self.placements:
            raise PaletteContractError(
                "ABSOLUTE_DIMENSIONAL_LAYOUT requires placements")


@dataclass(frozen=True)
class PaletteSpec:
    """The whole palette contract."""

    palette_id: str
    case: PaletteCaseSpec
    tray: PaletteTraySpec
    lid: PaletteLidSpec
    layout: PaletteLayoutSpec
    mirror: PaletteMirrorSpec
    hinge: PaletteHingeSpec
    clasp: PaletteClaspSpec
    applicator: PaletteApplicatorCompartmentSpec = field(
        default_factory=lambda: PaletteApplicatorCompartmentSpec(False))
    refillable_default: bool = False
    schema: str = SCHEMA

    def identity(self) -> str:
        """Deterministic contract identity (specification, not a mesh)."""
        payload = json.dumps(to_jsonable(self), sort_keys=True,
                             separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------


def to_jsonable(obj):
    """Serialize specs preserving every provenance field."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


AUTHORITY_STATEMENT = {
    "PALETTE_GEOMETRY_AUTHORITY": "PROVISIONAL_DESIGN_ONLY",
    "MANUFACTURING_AUTHORITY": "NOT_ESTABLISHED",
    "MATERIAL_AUTHORITY": "NOT_EXPRESSIBLE_IN_THIS_CONTRACT",
    "MODULE_EQUIVALENCE_AUTHORITY": "CALCULATED_LAYOUT_HEURISTIC",
    "usage_restriction": "design and validation only — never supplier or "
                         "tooling geometry",
}
