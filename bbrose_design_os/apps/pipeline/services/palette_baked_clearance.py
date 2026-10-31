"""M6 — BAKED dome CLOSED-state clearance, in millimetres.

Order fixed by declaration: the tolerance ASSUMPTIONS are declared and
hashed BEFORE any clearance number is computed. They are assumptions,
not data — ES3083_DIMENSIONS_UNREADABLE stands, every P1B dimension is
a PROVISIONAL_DESIGN_DEFAULT, and no supplier tolerance exists. The
result therefore inherits BOTH provisionalities (provisional nominals
AND assumed tolerances): it can support a design decision and can
never be quoted as measured, and the record says so in those terms.
"""
from __future__ import annotations

import hashlib
import json

from apps.pipeline.services import palette_baked_geometry as BG
from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_rect_pan as RP

SCHEMA = "baked_closed_clearance/1.0"

#: DECLARED TOLERANCE ASSUMPTIONS — hashed before computation. Values
#: are engineering assumptions typical for moulded ABS + pressed
#: powder, NOT data from any drawing or supplier.
TOLERANCE_ASSUMPTIONS = {
    "moulding_per_feature_mm": 0.15,
    "pan_seating_mm": 0.10,
    "powder_fill_height_mm": 0.20,
    "dome_crown_mm": 0.15,
    "lid_closure_seating_mm": 0.10,
    "basis": "ASSUMPTION_NOT_DATA — no declared tolerances exist for "
             "any P1B dimension",
}


def assumptions_hash() -> str:
    return hashlib.sha256(json.dumps(
        TOLERANCE_ASSUMPTIONS, sort_keys=True).encode()).hexdigest()[:16]


def closed_clearance() -> dict:
    """Worst-case minimum distance between the dome peak and the
    closed lid interior, from the P1B dimension chain."""
    comps, dims = MR.build_rect_components(OC.confirmed_intent())
    pan_c = RP.contract_values()

    # dimension chain, every term named
    closed = MR.compose_rect_state(comps, dims, "CLOSED")
    lid_roof_underside_z = float(
        closed["lid_outer_shell"]["vertices"][:, 2].max()
        # M6-LID-ROOF-REPAIR (A74): default REMOVED, not aligned
        # — a missing key is a loud failure, never a quiet 1.6
        - dims["lid_roof_mm"])
    tray_pocket_floor_z = float(
        closed["metal_pan_1"]["vertices"][:, 2].min())

    shade = PE.PowderShade("prov_clearance", (0.5, 0.4, 0.3),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)
    baked = PE.PowderMaterialSpec(PP.BAKED, shade, seed=1)
    vol = BG.build_powder_volume(
        baked.params,
        pan_inner_w=pan_c["pan_width_mm"]
        - 2 * pan_c["metal_wall_thickness_mm"],
        pan_inner_d=pan_c["pan_height_mm"]
        - 2 * pan_c["metal_wall_thickness_mm"],
        z_floor=tray_pocket_floor_z
        + pan_c["metal_floor_thickness_mm"])
    dome_peak_z = vol["top_z_peak"]

    nominal = lid_roof_underside_z - dome_peak_z
    t = TOLERANCE_ASSUMPTIONS
    worst_stack = (t["moulding_per_feature_mm"] + t["pan_seating_mm"]
                   + t["powder_fill_height_mm"] + t["dome_crown_mm"]
                   + t["lid_closure_seating_mm"])
    worst_case = nominal - worst_stack
    required = baked.params["dome"]["lid_clearance_required_mm"]

    return {
        "record_type": SCHEMA,
        "tolerance_assumptions": TOLERANCE_ASSUMPTIONS,
        "assumptions_hash": assumptions_hash(),
        "assumptions_hashed_before_computation": True,
        "dimension_chain_mm": {
            "lid_roof_underside_z": round(lid_roof_underside_z, 3),
            "pan_floor_z": round(tray_pocket_floor_z, 3),
            "dome_peak_z": round(dome_peak_z, 3),
        },
        "nominal_clearance_mm": round(nominal, 3),
        "worst_case_stack_mm": round(worst_stack, 3),
        "worst_case_clearance_mm": round(worst_case, 3),
        "required_mm": required,
        "verdict": ("CLEARS_AT_WORST_CASE"
                    if worst_case >= required else
                    "FAILS_AT_WORST_CASE"),
        "provisionality": (
            "this number inherits TWO provisionalities: the nominals are "
            "PROVISIONAL_DESIGN_DEFAULTS (ES3083_DIMENSIONS_UNREADABLE) "
            "and the tolerances are ASSUMPTIONS (no drawing, no "
            "supplier). It supports a design decision. It is not a "
            "manufacturing claim and may never be quoted as measured. "
            "manufacturing_authority: NOT_ESTABLISHED."),
        "owner_approved": False,
    }
