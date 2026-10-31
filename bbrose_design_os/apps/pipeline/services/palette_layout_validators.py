"""PALT-M2 — fail-closed palette layout validators.

Every violation produces a stable code. The validators never repair a
layout: they report. Shrinking pans or margins to make an invalid layout
pass is explicitly forbidden by the owner instruction.
"""
from __future__ import annotations

from apps.pipeline.services.palette_contracts import PaletteSpec
from apps.pipeline.services.palette_layout_kernel import (
    derived_closed_height, resolve_layout)

VALIDATOR_VERSION = "palette_layout_validators/1.0"

PAN_OVERLAP = "PAN_OVERLAP"
CASE_BOUNDARY_VIOLATION = "CASE_BOUNDARY_VIOLATION"
INSUFFICIENT_OUTER_MARGIN = "INSUFFICIENT_OUTER_MARGIN"
INSUFFICIENT_INTER_PAN_GAP = "INSUFFICIENT_INTER_PAN_GAP"
HINGE_ZONE_COLLISION = "HINGE_ZONE_COLLISION"
CLASP_ZONE_COLLISION = "CLASP_ZONE_COLLISION"
MIRROR_COLLISION = "MIRROR_COLLISION"
APPLICATOR_ZONE_COLLISION = "APPLICATOR_ZONE_COLLISION"
IMPOSSIBLE_PAN_DEPTH = "IMPOSSIBLE_PAN_DEPTH"
INSUFFICIENT_CASE_THICKNESS = "INSUFFICIENT_CASE_THICKNESS"
INVALID_REFILL_REMOVAL_CLEARANCE = "INVALID_REFILL_REMOVAL_CLEARANCE"
WALL_BELOW_MINIMUM = "WALL_BELOW_MINIMUM"
MODULE_SMALLER_THAN_PAN_FOOTPRINT = "MODULE_SMALLER_THAN_PAN_FOOTPRINT"

# moulding guidance (R14): ABS 1.5-3.0, PP 1.0-3.5
MIN_WALL_MM = {"ABS": 1.5, "PP": 1.0, "PC-ABS": 1.5, "SAN": 1.5, "PS": 1.5}


def _overlap(a, b) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def _gap_between(a, b) -> float:
    """Smallest axis gap between two padded footprints (negative = overlap)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    dx = max(bx0 - ax1, ax0 - bx1)
    dy = max(by0 - ay1, ay0 - by1)
    if dx >= 0 and dy >= 0:
        return min(dx, dy)
    return max(dx, dy)


def validate_layout(spec: PaletteSpec) -> dict:
    """Returns a findings record. ``valid`` is True only when empty."""
    result = resolve_layout(spec)
    findings: list[dict] = []

    def add(code, message, **extra):
        findings.append({"code": code, "message": message, **extra})

    # --- wall thickness vs moulding guidance
    min_wall = MIN_WALL_MM.get(spec.case.material.upper())
    if min_wall and spec.case.wall_thickness.mm < min_wall:
        add(WALL_BELOW_MINIMUM,
            f"case wall {spec.case.wall_thickness.mm} mm is below the "
            f"{spec.case.material} minimum {min_wall} mm",
            material=spec.case.material)
    if min_wall and spec.tray.wall_thickness.mm < min_wall:
        add(WALL_BELOW_MINIMUM,
            f"tray wall {spec.tray.wall_thickness.mm} mm is below the "
            f"{spec.case.material} minimum {min_wall} mm")

    # --- inter-pan gap declared below the recommended minimum
    if spec.tray.inter_pan_gap.mm < spec.tray.minimum_inter_pan_gap.mm:
        add(INSUFFICIENT_INTER_PAN_GAP,
            f"declared inter-pan gap {spec.tray.inter_pan_gap.mm} mm is "
            f"below the minimum {spec.tray.minimum_inter_pan_gap.mm} mm",
            declared=spec.tray.inter_pan_gap.mm,
            minimum=spec.tray.minimum_inter_pan_gap.mm)

    # --- a module must contain the pan INCLUDING tolerance and removal
    # clearance; otherwise the pocket overhangs its own lattice cell
    if spec.layout.mode == "MODULE_LATTICE":
        mw = spec.layout.module_width.mm
        mh = spec.layout.module_height.mm
        gap = spec.tray.inter_pan_gap.mm
        by_id = {p.pan_id: p for p in spec.layout.pans}
        for pan_id, _r, _c, w_mod, h_mod in spec.layout.occupancy:
            pan = by_id[pan_id]
            pw, ph = pan.footprint_mm
            block_w = w_mod * mw + (w_mod - 1) * gap
            block_h = h_mod * mh + (h_mod - 1) * gap
            if pw > block_w + 1e-6 or ph > block_h + 1e-6:
                add(MODULE_SMALLER_THAN_PAN_FOOTPRINT,
                    f"pan {pan_id} footprint {round(pw,2)}x{round(ph,2)} mm "
                    f"(incl. tolerance/removal clearance) exceeds its module "
                    f"block {round(block_w,2)}x{round(block_h,2)} mm",
                    pan_id=pan_id, footprint_mm=[round(pw, 2), round(ph, 2)],
                    block_mm=[round(block_w, 2), round(block_h, 2)])

    res = result.reservations
    margin = res["outer_margin_mm"]
    inner_w, inner_d = result.tray_inner_width_mm, result.tray_inner_depth_mm
    hinge_y0 = inner_d - res["hinge_rear_mm"]
    clasp_y1 = res["clasp_front_mm"]
    applicator_y1 = res["clasp_front_mm"] + res["applicator_front_mm"]

    for pan in result.placed:
        x0, y0, x1, y1 = pan.bounds
        if x0 < 0 or y0 < 0 or x1 > inner_w or y1 > inner_d:
            add(CASE_BOUNDARY_VIOLATION,
                f"pan {pan.pan_id} exceeds the tray inner bounds "
                f"({round(x0,2)},{round(y0,2)})-({round(x1,2)},{round(y1,2)}) "
                f"vs {round(inner_w,2)}x{round(inner_d,2)}",
                pan_id=pan.pan_id)
        if (x0 < margin - 1e-6 or y0 < margin - 1e-6
                or x1 > inner_w - margin + 1e-6
                or y1 > inner_d - margin + 1e-6):
            add(INSUFFICIENT_OUTER_MARGIN,
                f"pan {pan.pan_id} breaches the {margin} mm outer margin",
                pan_id=pan.pan_id)
        if res["hinge_rear_mm"] and y1 > hinge_y0 + 1e-6:
            add(HINGE_ZONE_COLLISION,
                f"pan {pan.pan_id} enters the hinge reservation "
                f"(rear {round(res['hinge_rear_mm'],2)} mm)",
                pan_id=pan.pan_id)
        if res["clasp_front_mm"] and y0 < clasp_y1 - 1e-6:
            add(CLASP_ZONE_COLLISION,
                f"pan {pan.pan_id} enters the clasp reservation "
                f"(front {round(res['clasp_front_mm'],2)} mm)",
                pan_id=pan.pan_id)
        if res["applicator_front_mm"] and y0 < applicator_y1 - 1e-6:
            add(APPLICATOR_ZONE_COLLISION,
                f"pan {pan.pan_id} enters the applicator compartment "
                f"reservation", pan_id=pan.pan_id)
        if pan.depth_mm <= 0:
            add(IMPOSSIBLE_PAN_DEPTH,
                f"pan {pan.pan_id} has non-positive depth",
                pan_id=pan.pan_id)
        if pan.refillable:
            src = next(p for p in spec.layout.pans if p.pan_id == pan.pan_id)
            if src.removal_clearance.mm <= 0:
                add(INVALID_REFILL_REMOVAL_CLEARANCE,
                    f"pan {pan.pan_id} is refillable but declares no removal "
                    f"clearance — it could not be lifted out",
                    pan_id=pan.pan_id)

    # --- pairwise overlap and realised gap
    placed = list(result.placed)
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = placed[i].bounds, placed[j].bounds
            if _overlap(a, b):
                add(PAN_OVERLAP,
                    f"pans {placed[i].pan_id} and {placed[j].pan_id} overlap",
                    pans=[placed[i].pan_id, placed[j].pan_id])
                continue
            g = _gap_between(a, b)
            if g + 1e-6 < spec.tray.minimum_inter_pan_gap.mm:
                add(INSUFFICIENT_INTER_PAN_GAP,
                    f"realised gap {round(g,3)} mm between "
                    f"{placed[i].pan_id} and {placed[j].pan_id} is below the "
                    f"minimum {spec.tray.minimum_inter_pan_gap.mm} mm",
                    pans=[placed[i].pan_id, placed[j].pan_id],
                    realised_gap_mm=round(g, 3))

    # --- mirror clearance in the CLOSED state
    if spec.mirror.present:
        deepest = max((p.depth_mm for p in result.placed), default=0.0)
        stack = (spec.case.base_thickness.mm + spec.tray.floor_thickness.mm
                 + deepest + spec.lid.inner_clearance.mm
                 + spec.mirror.thickness.mm + spec.lid.thickness.mm)
        if spec.lid.inner_clearance.mm <= 0:
            add(MIRROR_COLLISION,
                "mirror would contact the pan surfaces when closed "
                "(no lid inner clearance)")
        if stack > spec.case.outer_height.mm + 1e-6:
            add(INSUFFICIENT_CASE_THICKNESS,
                f"derived closed height {round(stack,2)} mm exceeds the "
                f"declared case height {spec.case.outer_height.mm} mm",
                derived_mm=round(stack, 2),
                declared_mm=spec.case.outer_height.mm)
    else:
        derived = derived_closed_height(spec)
        if derived > spec.case.outer_height.mm + 1e-6:
            add(INSUFFICIENT_CASE_THICKNESS,
                f"derived closed height {round(derived,2)} mm exceeds the "
                f"declared case height {spec.case.outer_height.mm} mm",
                derived_mm=round(derived, 2),
                declared_mm=spec.case.outer_height.mm)

    return {
        "record_type": "palette_layout_validation/1.0",
        "validator_version": VALIDATOR_VERSION,
        "palette_id": spec.palette_id,
        "contract_identity": spec.identity(),
        "valid": not findings,
        "finding_count": len(findings),
        "findings": findings,
        "fail_closed": True,
        "never_auto_repairs": "the validators never shrink pans, gaps or "
                              "margins to make an invalid layout pass",
    }
