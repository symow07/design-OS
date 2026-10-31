"""PALT-M2 — deterministic palette layout kernel.

Coordinate system (documented once, used everywhere):

* origin at the tray's inner front-left corner;
* +x to the right, +y toward the REAR (the hinge side), +z up;
* all values in millimetres;
* pan placements are the pan's bounding-box front-left corner.

The hinge therefore occupies the high-y band, the clasp the low-y band —
stated explicitly so collision checks are unambiguous.

Two modes (owner-mandated):

* ``MODULE_LATTICE`` — structured, reflowable layouts; occupancy on a
  lattice. Module equivalence is a CALCULATED_LAYOUT_HEURISTIC only, and
  every module resolves here to explicit millimetres.
* ``ABSOLUTE_DIMENSIONAL_LAYOUT`` — irregular/custom arrangements placed by
  explicit coordinates.

The kernel never shrinks a pan or silently adjusts a spec to make an
invalid layout pass. It resolves, then reports.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.pipeline.services.palette_contracts import (
    PaletteContractError, PaletteSpec, to_jsonable)
from apps.pipeline.services import palette_firing_trace as FT

KERNEL_VERSION = "palette_layout_kernel/1.0"


@dataclass(frozen=True)
class PlacedPan:
    pan_id: str
    x_mm: float          # front-left corner, tray-local
    y_mm: float
    width_mm: float      # bounding extent (nominal, without padding)
    height_mm: float
    depth_mm: float
    padded_width_mm: float   # incl. tolerance + removal clearance
    padded_height_mm: float
    shape: str
    zone: str
    refillable: bool

    @property
    def bounds(self):
        """(x0, y0, x1, y1) of the PADDED footprint — the extent that must
        not collide with anything."""
        px = (self.padded_width_mm - self.width_mm) / 2.0
        py = (self.padded_height_mm - self.height_mm) / 2.0
        return (self.x_mm - px, self.y_mm - py,
                self.x_mm + self.width_mm + px,
                self.y_mm + self.height_mm + py)


@dataclass(frozen=True)
class LayoutResult:
    kernel_version: str
    mode: str
    placed: tuple
    tray_inner_width_mm: float
    tray_inner_depth_mm: float
    usable_width_mm: float       # after hinge/clasp/applicator reservations
    usable_depth_mm: float
    reservations: dict
    derived_height_mm: float
    lattice: dict | None = None

    def as_dict(self):
        return {
            "kernel_version": self.kernel_version,
            "mode": self.mode,
            "tray_inner_width_mm": round(self.tray_inner_width_mm, 3),
            "tray_inner_depth_mm": round(self.tray_inner_depth_mm, 3),
            "usable_width_mm": round(self.usable_width_mm, 3),
            "usable_depth_mm": round(self.usable_depth_mm, 3),
            "reservations_mm": self.reservations,
            "derived_closed_height_mm": round(self.derived_height_mm, 3),
            "lattice": self.lattice,
            "pans": [
                {"pan_id": p.pan_id, "x_mm": round(p.x_mm, 3),
                 "y_mm": round(p.y_mm, 3),
                 "width_mm": round(p.width_mm, 3),
                 "height_mm": round(p.height_mm, 3),
                 "depth_mm": round(p.depth_mm, 3),
                 "padded_width_mm": round(p.padded_width_mm, 3),
                 "padded_height_mm": round(p.padded_height_mm, 3),
                 "shape": p.shape, "zone": p.zone,
                 "refillable": p.refillable}
                for p in self.placed],
        }


def _reservations(spec: PaletteSpec) -> dict:
    """Zones the pan field may never enter, in millimetres."""
    return {
        "hinge_rear_mm": spec.hinge.zone_depth.mm + spec.hinge.clearance.mm
        if spec.hinge.family != "NONE" else FT.traced_zero("palette_layout_kernel.py:_reservations", "guard"),
        "clasp_front_mm": spec.clasp.zone_depth.mm
        if spec.clasp.family != "NONE" else FT.traced_zero("palette_layout_kernel.py:_reservations", "guard"),
        "applicator_front_mm": spec.applicator.zone_depth.mm
        if spec.applicator.present else FT.traced_zero("palette_layout_kernel.py:_reservations", "guard"),
        "outer_margin_mm": spec.tray.outer_margin.mm,
    }


def derived_closed_height(spec: PaletteSpec) -> float:
    """Closed height is DERIVED, never authored — so a proposed height is
    arithmetically refutable."""
    deepest = max((p.depth.mm for p in spec.layout.pans), default=0.0)
    return (spec.case.base_thickness.mm
            + spec.tray.floor_thickness.mm
            + deepest
            + spec.lid.inner_clearance.mm
            + (spec.mirror.thickness.mm if spec.mirror.present else FT.traced_zero("palette_layout_kernel.py:derived_closed_height", "guard"))
            + spec.lid.thickness.mm)


def resolve_layout(spec: PaletteSpec) -> LayoutResult:
    """Deterministically resolve pan positions. Raises only on structurally
    impossible input; geometric violations are reported by the validators."""
    res = _reservations(spec)
    inner_w = spec.case.inner_width_mm
    inner_d = spec.case.inner_depth_mm
    margin = res["outer_margin_mm"]
    usable_w = inner_w - 2 * margin
    usable_d = (inner_d - res["hinge_rear_mm"] - res["clasp_front_mm"]
                - res["applicator_front_mm"] - 2 * margin)
    # the pan field's front-left origin inside the tray
    field_x0 = margin
    field_y0 = margin + res["clasp_front_mm"] + res["applicator_front_mm"]

    by_id = {p.pan_id: p for p in spec.layout.pans}
    placed = []
    lattice = None

    if spec.layout.mode == "MODULE_LATTICE":
        mw = spec.layout.module_width.mm
        mh = spec.layout.module_height.mm
        gap = spec.tray.inter_pan_gap.mm
        pitch_x = mw + gap
        pitch_y = mh + gap
        lattice = {"module_width_mm": mw, "module_height_mm": mh,
                   "gap_mm": gap, "pitch_x_mm": round(pitch_x, 3),
                   "pitch_y_mm": round(pitch_y, 3),
                   "rows": spec.layout.rows, "cols": spec.layout.cols,
                   "module_equivalence_authority":
                       "CALCULATED_LAYOUT_HEURISTIC",
                   "note": "every module resolves to explicit millimetres "
                           "here; occupancy is a layout convenience, not a "
                           "manufacturer or industry standard"}
        for pan_id, row, col, w_mod, h_mod in spec.layout.occupancy:
            if pan_id not in by_id:
                raise PaletteContractError(
                    f"occupancy references unknown pan {pan_id!r}")
            pan = by_id[pan_id]
            # module block extent in mm (multi-module spans absorb the gaps)
            block_w = w_mod * mw + (w_mod - 1) * gap
            block_h = h_mod * mh + (h_mod - 1) * gap
            bx = field_x0 + col * pitch_x
            by = field_y0 + row * pitch_y
            pw, ph = pan.footprint_mm
            # centre the pan inside its module block
            x = bx + (block_w - pan.width.mm) / 2.0
            y = by + (block_h - pan.height.mm) / 2.0
            placed.append(PlacedPan(
                pan_id, x, y, pan.width.mm, pan.height.mm, pan.depth.mm,
                pw, ph, pan.shape, pan.zone, pan.refillable))
    else:
        for pan_id, x, y in spec.layout.placements:
            if pan_id not in by_id:
                raise PaletteContractError(
                    f"placement references unknown pan {pan_id!r}")
            pan = by_id[pan_id]
            pw, ph = pan.footprint_mm
            placed.append(PlacedPan(
                pan_id, float(x), float(y), pan.width.mm, pan.height.mm,
                pan.depth.mm, pw, ph, pan.shape, pan.zone, pan.refillable))

    placed.sort(key=lambda p: (round(p.y_mm, 4), round(p.x_mm, 4), p.pan_id))
    return LayoutResult(
        KERNEL_VERSION, spec.layout.mode, tuple(placed), inner_w, inner_d,
        usable_w, usable_d, res, derived_closed_height(spec), lattice)


def minimum_feasible_case(spec: PaletteSpec) -> dict:
    """Smallest case that could contain this layout, given the spec's own
    gaps, margins, walls and reservations. Reported — never applied."""
    res = _reservations(spec)
    margin = res["outer_margin_mm"]
    wall = spec.case.wall_thickness.mm
    gap = spec.tray.inter_pan_gap.mm

    if spec.layout.mode == "MODULE_LATTICE":
        mw = spec.layout.module_width.mm
        mh = spec.layout.module_height.mm
        cols, rows = spec.layout.cols, spec.layout.rows
        field_w = cols * mw + (cols - 1) * gap
        field_h = rows * mh + (rows - 1) * gap
        # a pan padded beyond its module widens the field
        extra_w = extra_h = 0.0
        by_id = {p.pan_id: p for p in spec.layout.pans}
        for pan_id, _r, _c, w_mod, h_mod in spec.layout.occupancy:
            pan = by_id[pan_id]
            pw, ph = pan.footprint_mm
            block_w = w_mod * mw + (w_mod - 1) * gap
            block_h = h_mod * mh + (h_mod - 1) * gap
            extra_w = max(extra_w, pw - block_w)
            extra_h = max(extra_h, ph - block_h)
        field_w += max(extra_w, 0.0)
        field_h += max(extra_h, 0.0)
    else:
        xs0 = min(p.bounds[0] for p in resolve_layout(spec).placed)
        ys0 = min(p.bounds[1] for p in resolve_layout(spec).placed)
        xs1 = max(p.bounds[2] for p in resolve_layout(spec).placed)
        ys1 = max(p.bounds[3] for p in resolve_layout(spec).placed)
        field_w, field_h = xs1 - xs0, ys1 - ys0

    min_w = field_w + 2 * margin + 2 * wall
    min_d = (field_h + 2 * margin + res["hinge_rear_mm"]
             + res["clasp_front_mm"] + res["applicator_front_mm"] + 2 * wall)
    min_h = derived_closed_height(spec)
    return {
        "record_type": "palette_minimum_feasible_case/1.0",
        "minimum_outer_width_mm": round(min_w, 2),
        "minimum_outer_depth_mm": round(min_d, 2),
        "minimum_outer_height_mm": round(min_h, 2),
        "pan_field_mm": [round(field_w, 2), round(field_h, 2)],
        "reservations_mm": res,
        "wall_thickness_mm": wall,
        "method": "field extent + outer margins + mechanism reservations + "
                  "two case walls; closed height derived from the plate "
                  "stack (never authored)",
        "authority": "CALCULATED — provisional design figure, "
                     "NOT_MANUFACTURING_AUTHORITATIVE",
        "note": "reported, never applied: the kernel does not shrink pans "
                "or margins to make an invalid layout pass",
    }


def layout_report(spec: PaletteSpec) -> dict:
    result = resolve_layout(spec)
    return {
        "record_type": "palette_layout_result/1.0",
        "palette_id": spec.palette_id,
        "contract_identity": spec.identity(),
        "layout": result.as_dict(),
        "minimum_feasible_case": minimum_feasible_case(spec),
        "spec": to_jsonable(spec),
    }
