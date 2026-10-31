"""PALT-M3 — complete palette stack-up engine.

Produces THREE separated height values, never one:

* ``GEOMETRIC_LOWER_BOUND`` — solids and unavoidable clearances only.
  A mathematical artefact. **Never a production recommendation.**
* ``ENGINEERING_MINIMUM``   — adds adhesives, tolerance, warpage, parting
  gap, powder crown and mechanism height.
* ``PREMIUM_DESIGN_TARGET`` — adds premium skin thickness, comfortable
  clearances and a decoration/insert allowance.

The footprint stack-up is equally explicit, and the module resolves to the
full pocket-and-retention envelope (owner correction), not merely nominal
pan + tolerance.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.pipeline.services.palette_contracts import PaletteSpec
from apps.pipeline.services.palette_mechanism_contracts import (
    MechanismStrategySpec)
from apps.pipeline.services import palette_firing_trace as FT

ENGINE_VERSION = "palette_stackup_engine/1.0"

# --- allowances (all DESIGN_DEFAULT; none is manufacturer-confirmed) -------
ALLOWANCES = {
    "pan_seating_adhesive_mm": 0.15,
    "pan_proud_recess_mm": 0.20,        # pan rim standing proud of the tray
    "powder_crown_mm": 0.30,            # pressed powder is not perfectly flat
    "interior_clearance_above_powder_mm": 0.50,
    "mirror_adhesive_mm": 0.15,
    "mirror_safety_clearance_mm": 0.30,
    "cosmetic_parting_gap_mm": 0.20,
    "manufacturing_tolerance_mm": 0.30,
    "warpage_allowance_mm": 0.40,
    "decoration_insert_allowance_mm": 0.60,   # premium only
    "assembly_clearance_mm": 0.30,
    "moulding_tolerance_mm": 0.20,
    "lid_structural_border_mm": 2.0,
    "premium_skin_uplift_mm": 0.80,           # premium only, per skin
    "premium_clearance_uplift_mm": 0.50,      # premium only
}


@dataclass(frozen=True)
class HeightStackup:
    geometric_lower_bound_mm: float
    engineering_minimum_mm: float
    premium_design_target_mm: float
    components: dict

    def as_dict(self):
        return {
            "GEOMETRIC_LOWER_BOUND_mm": round(self.geometric_lower_bound_mm, 3),
            "ENGINEERING_MINIMUM_mm": round(self.engineering_minimum_mm, 3),
            "PREMIUM_DESIGN_TARGET_mm": round(self.premium_design_target_mm, 3),
            "components_mm": {k: round(v, 3) for k, v in
                              self.components.items()},
            "authority": "DESIGN_DEFAULT allowances; "
                         "MANUFACTURING_AUTHORITY NOT_ESTABLISHED",
            "warning": "the geometric lower bound is a mathematical "
                       "artefact and must never be presented as a "
                       "production recommendation or a premium thickness",
        }


def height_stackup(spec: PaletteSpec,
                   strategy: MechanismStrategySpec) -> HeightStackup:
    a = ALLOWANCES
    deepest = max((p.depth.mm for p in spec.layout.pans), default=0.0)
    mirror = spec.mirror.present

    # --- solids and unavoidable clearances
    base_skin = spec.case.base_thickness.mm
    tray_floor = spec.tray.floor_thickness.mm
    lid_inner_skin = spec.lid.thickness.mm / 2.0
    lid_outer_skin = spec.lid.thickness.mm / 2.0
    mirror_t = spec.mirror.thickness.mm if mirror else FT.traced_zero("palette_stackup_engine.py:height_stackup", "guard")

    lower = (base_skin + tray_floor + deepest + lid_inner_skin
             + lid_outer_skin + mirror_t
             + a["interior_clearance_above_powder_mm"])

    # --- engineering additions
    mech_height = (strategy.hinge_envelope.height_add.mm
                   + strategy.clasp_envelope.height_add.mm
                   + strategy.retention_envelope.height_add.mm)
    engineering = (lower
                   + a["pan_seating_adhesive_mm"]
                   + a["pan_proud_recess_mm"]
                   + a["powder_crown_mm"]
                   + (a["mirror_adhesive_mm"] + a["mirror_safety_clearance_mm"]
                      if mirror else FT.traced_zero("palette_stackup_engine.py:height_stackup", "guard"))
                   + mech_height
                   + a["cosmetic_parting_gap_mm"]
                   + a["manufacturing_tolerance_mm"]
                   + a["warpage_allowance_mm"])

    premium = (engineering
               + 2 * a["premium_skin_uplift_mm"]
               + a["premium_clearance_uplift_mm"]
               + a["decoration_insert_allowance_mm"])

    components = {
        "outer_base_skin": base_skin,
        "tray_floor": tray_floor,
        "pan_depth": deepest,
        "pan_seating_adhesive": a["pan_seating_adhesive_mm"],
        "pan_proud_recess": a["pan_proud_recess_mm"],
        "powder_crown": a["powder_crown_mm"],
        "interior_clearance_above_powder":
            a["interior_clearance_above_powder_mm"],
        "lid_inner_skin": lid_inner_skin,
        "lid_outer_skin": lid_outer_skin,
        "mirror_thickness": mirror_t,
        "mirror_adhesive": a["mirror_adhesive_mm"] if mirror else FT.traced_zero("palette_stackup_engine.py:height_stackup", "guard"),
        "mirror_safety_clearance":
            a["mirror_safety_clearance_mm"] if mirror else FT.traced_zero("palette_stackup_engine.py:height_stackup", "guard"),
        "hinge_height_envelope": strategy.hinge_envelope.height_add.mm,
        "clasp_closure_clearance": strategy.clasp_envelope.height_add.mm,
        "retention_height": strategy.retention_envelope.height_add.mm,
        "cosmetic_parting_gap": a["cosmetic_parting_gap_mm"],
        "manufacturing_tolerance": a["manufacturing_tolerance_mm"],
        "warpage_allowance": a["warpage_allowance_mm"],
        "premium_skin_uplift_x2": 2 * a["premium_skin_uplift_mm"],
        "premium_clearance_uplift": a["premium_clearance_uplift_mm"],
        "decoration_insert_allowance": a["decoration_insert_allowance_mm"],
    }
    return HeightStackup(lower, engineering, premium, components)


@dataclass(frozen=True)
class FootprintStackup:
    minimum_width_mm: float
    minimum_depth_mm: float
    external_width_add_mm: float
    external_depth_add_mm: float
    components: dict

    def as_dict(self):
        return {
            "minimum_width_mm": round(self.minimum_width_mm, 3),
            "minimum_depth_mm": round(self.minimum_depth_mm, 3),
            "external_width_add_mm": round(self.external_width_add_mm, 3),
            "external_depth_add_mm": round(self.external_depth_add_mm, 3),
            "total_external_width_mm": round(
                self.minimum_width_mm + self.external_width_add_mm, 3),
            "total_external_depth_mm": round(
                self.minimum_depth_mm + self.external_depth_add_mm, 3),
            "components_mm": {k: round(v, 3) if isinstance(v, (int, float))
                              else v for k, v in self.components.items()},
            "authority": "DESIGN_DEFAULT allowances; "
                         "MANUFACTURING_AUTHORITY NOT_ESTABLISHED",
        }


def pocket_module_mm(spec: PaletteSpec,
                     strategy: MechanismStrategySpec) -> tuple:
    """The FULL pocket + retention envelope (owner correction: a module is
    not merely nominal pan + tolerance). Returns (w, h) or raises when the
    retention strategy is an undefined placeholder."""
    add = strategy.retention_pocket_add_mm
    if add is None:
        raise ValueError(
            f"{strategy.retention_strategy} has an undefined pocket "
            "envelope — fails closed rather than assuming zero")
    w = max(p.width.mm + 2 * p.manufacturing_tolerance.mm + 2 * add
            for p in spec.layout.pans)
    h = max(p.height.mm + 2 * p.manufacturing_tolerance.mm + 2 * add
            for p in spec.layout.pans)
    # refillable pans also need removal clearance around them
    if any(p.refillable for p in spec.layout.pans):
        extra = 2 * max(p.removal_clearance.mm for p in spec.layout.pans)
        w += extra
        h += extra
    return w, h


def footprint_stackup(spec: PaletteSpec, strategy: MechanismStrategySpec,
                      rows: int, cols: int) -> FootprintStackup:
    a = ALLOWANCES
    mod_w, mod_h = pocket_module_mm(spec, strategy)
    gap = spec.tray.inter_pan_gap.mm
    margin = spec.tray.outer_margin.mm
    tray_wall = spec.tray.wall_thickness.mm
    case_wall = spec.case.wall_thickness.mm

    field_w = cols * mod_w + (cols - 1) * gap
    field_h = rows * mod_h + (rows - 1) * gap

    hinge = strategy.hinge_envelope
    clasp = strategy.clasp_envelope
    # internal bands steal field on the axis their edge belongs to
    internal_w = ((hinge.internal_band.mm if strategy.hinge_axis == "width"
                   else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard"))
                  + (clasp.internal_band.mm if strategy.clasp_axis == "width"
                     else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard")))
    internal_d = ((hinge.internal_band.mm if strategy.hinge_axis == "depth"
                   else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard"))
                  + (clasp.internal_band.mm if strategy.clasp_axis == "depth"
                     else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard")))
    # wall additions thicken the wall on the mechanism's axis (one side each)
    wall_w = ((hinge.wall_add.mm if strategy.hinge_axis == "width" else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard"))
              + (clasp.wall_add.mm if strategy.clasp_axis == "width" else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard")))
    wall_d = ((hinge.wall_add.mm if strategy.hinge_axis == "depth" else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard"))
              + (clasp.wall_add.mm if strategy.clasp_axis == "depth" else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard")))

    common = (2 * margin + 2 * tray_wall + 2 * case_wall
              + a["assembly_clearance_mm"] + a["moulding_tolerance_mm"]
              + 2 * a["lid_structural_border_mm"])

    min_w = field_w + internal_w + wall_w + common
    min_d = field_h + internal_d + wall_d + common

    ext_w = ((hinge.external_add.mm if strategy.hinge_axis == "width" else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard"))
             + (clasp.external_add.mm if strategy.clasp_axis == "width"
                else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard")))
    ext_d = ((hinge.external_add.mm if strategy.hinge_axis == "depth" else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard"))
             + (clasp.external_add.mm if strategy.clasp_axis == "depth"
                else FT.traced_zero("palette_stackup_engine.py:footprint_stackup", "guard")))

    components = {
        "pocket_module_w": mod_w,
        "pocket_module_h": mod_h,
        "retention_pocket_add_per_side": strategy.retention_pocket_add_mm,
        "pan_field_w": field_w,
        "pan_field_h": field_h,
        "inter_pan_gap": gap,
        "outer_margin_x2": 2 * margin,
        "internal_tray_walls_x2": 2 * tray_wall,
        "outer_case_walls_x2": 2 * case_wall,
        "hinge_internal_band": hinge.internal_band.mm,
        "clasp_internal_band": clasp.internal_band.mm,
        "hinge_wall_add": hinge.wall_add.mm,
        "clasp_wall_add": clasp.wall_add.mm,
        "hinge_external_add": hinge.external_add.mm,
        "clasp_external_add": clasp.external_add.mm,
        "lid_structural_border_x2": 2 * a["lid_structural_border_mm"],
        "assembly_clearance": a["assembly_clearance_mm"],
        "moulding_tolerance": a["moulding_tolerance_mm"],
        "corner_radius_effect": (
            "corner radius reduces usable corner area; with round pans on a "
            f"{round(margin,2)} mm margin and R{spec.case.corner_radius.mm} "
            "the corner pans stay clear — re-check for square pans"),
    }
    return FootprintStackup(min_w, min_d, ext_w, ext_d, components)


def evaluate_configuration(spec: PaletteSpec, strategy: MechanismStrategySpec,
                           rows: int, cols: int, *, label: str,
                           target_width_mm=None, target_depth_mm=None,
                           target_height_mm=None) -> dict:
    """One row of the strategy matrix. Reports; never adjusts."""
    conflict = strategy.material_conflict(spec.case.material)
    try:
        foot = footprint_stackup(spec, strategy, rows, cols)
        foot_dict = foot.as_dict()
        foot_error = None
    except ValueError as exc:
        foot, foot_dict, foot_error = None, None, str(exc)
    height = height_stackup(spec, strategy)

    codes = []
    if conflict:
        codes.append("MECHANISM_MATERIAL_CONFLICT")
    if foot_error:
        codes.append("MECHANISM_ENVELOPE_UNDEFINED")
    fits_w = fits_d = fits_h = None
    if foot is not None and target_width_mm and target_depth_mm:
        fits_w = target_width_mm + 1e-6 >= foot.minimum_width_mm
        fits_d = target_depth_mm + 1e-6 >= foot.minimum_depth_mm
        if not fits_w:
            codes.append("TARGET_WIDTH_EXCEEDED")
        if not fits_d:
            codes.append("TARGET_DEPTH_EXCEEDED")
    if target_height_mm:
        fits_h = target_height_mm + 1e-6 >= height.engineering_minimum_mm
        if not fits_h:
            codes.append("TARGET_HEIGHT_BELOW_ENGINEERING_MINIMUM")

    return {
        "label": label,
        "valid": not codes,
        "failure_codes": codes,
        "mechanism": {
            "hinge_strategy": strategy.hinge_strategy,
            "clasp_strategy": strategy.clasp_strategy,
            "retention_strategy": strategy.retention_strategy,
            "hinge_edge": strategy.hinge_edge,
            "clasp_edge": strategy.clasp_edge,
            "hinge_axis": strategy.hinge_axis,
            "clasp_axis": strategy.clasp_axis,
            "case_orientation": strategy.case_orientation,
            "opening_direction": strategy.opening_direction,
            "material_conflict": conflict,
        },
        "minimum_width_mm": (round(foot.minimum_width_mm, 2)
                             if foot else None),
        "minimum_depth_mm": (round(foot.minimum_depth_mm, 2)
                             if foot else None),
        "external_add_mm": ([round(foot.external_width_add_mm, 2),
                             round(foot.external_depth_add_mm, 2)]
                            if foot else None),
        "GEOMETRIC_LOWER_BOUND_height_mm":
            round(height.geometric_lower_bound_mm, 2),
        "ENGINEERING_MINIMUM_height_mm":
            round(height.engineering_minimum_mm, 2),
        "PREMIUM_DESIGN_TARGET_height_mm":
            round(height.premium_design_target_mm, 2),
        "fits_target": {"width": fits_w, "depth": fits_d, "height": fits_h},
        "footprint_stackup": foot_dict,
        "footprint_error": foot_error,
        "dimension_provenance": "DESIGN_DEFAULT allowances + ONLINE_REPORTED "
                                "pan family; nothing MANUFACTURER_CONFIRMED",
        "confidence": "LOW — mechanism envelopes are engineering estimates",
        "manufacturing_unknowns": strategy.unknowns,
    }
