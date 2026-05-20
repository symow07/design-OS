from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .panels import Panel
from .primitives import Primitive

if TYPE_CHECKING:
    from shapely.geometry import Polygon


@dataclass
class DimensionSet:
    """The three dimension sets every printed carton needs.

    All three are reported on the dieline so the prepress operator can
    verify the geometry before sending plates.
    """
    manufacture: tuple[float, float, float]   # (w, d, h) as supplied by user
    inner: tuple[float, float, float]         # manufacture - 2*board_thickness
    outer: tuple[float, float, float]         # manufacture + 2*board_thickness


@dataclass
class DielineCoordinates:
    flat_width_mm: float
    flat_height_mm: float
    panels: list[Panel]
    fold_lines: list[tuple[float, float, float, float]]

    # Shapely polygons. cut_polygon is the full union of body + all flaps +
    # glue tab. bleed_polygon and safe_polygon are buffer/inverse-buffer.
    cut_polygon: "Polygon"
    bleed_polygon: "Polygon"
    safe_polygon: "Polygon"

    # Per-flap geometry kept separately for inspection/labelling/testing.
    tuck_flap_polygons: list["Polygon"]    # 2 polygons: top back + bottom front
    dust_flap_polygons: list["Polygon"]    # 4 polygons: 2 top, 2 bottom
    glue_tab_polygon: "Polygon"
    body_polygon: "Polygon"
    slit_lines: list[tuple[float, float, float, float]]  # friction-lock slits (top tucks only)

    dimensions: DimensionSet
    board_thickness_mm: float
    body_top_y: float
    body_bottom_y: float

    # Ordered list of (id, polygon) for rendering each component as a
    # separate <path> element in the cut-lines layer of the SVG.
    components: list[tuple[str, "Polygon"]] = field(default_factory=list)
    # Optional primitive representation of components whose outline
    # includes curves (the two tuck flaps). When a component id is
    # present here, the SVG exporter emits real M/L/C/Z commands from
    # the primitive path; otherwise it falls back to the polygon-to-
    # polyline form used for straight-edged components.
    component_paths: dict[str, list[Primitive]] = field(default_factory=dict)
    # Stadium-shaped interior cutouts. Each entry:
    # (id, cx, cy, width, height). Emitted by the SVG exporter as paths
    # with true elliptical-arc (A) commands instead of polyline samples,
    # so prepress software (Illustrator) sees real arcs.
    stadium_cutouts: list[tuple[str, float, float, float, float]] = field(default_factory=list)
    derived: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.flat_width_mm <= 0:
            raise ValueError(f"flat_width_mm must be > 0, got {self.flat_width_mm}")
        if self.flat_height_mm <= 0:
            raise ValueError(f"flat_height_mm must be > 0, got {self.flat_height_mm}")
        if not self.cut_polygon.is_valid:
            raise ValueError("cut_polygon is invalid (self-intersecting or malformed)")
        if not self.bleed_polygon.is_valid:
            raise ValueError("bleed_polygon is invalid")
        if not self.safe_polygon.is_valid:
            raise ValueError("safe_polygon is invalid")
        if not (self.bleed_polygon.area > self.cut_polygon.area > self.safe_polygon.area):
            raise ValueError(
                "expected bleed_area > cut_area > safe_area, got "
                f"bleed={self.bleed_polygon.area}, cut={self.cut_polygon.area}, "
                f"safe={self.safe_polygon.area}"
            )
