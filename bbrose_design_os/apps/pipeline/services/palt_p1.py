"""PALT-P1 — standard 9-pan eyeshadow palette (first owner-selected pilot).

Owner decisions 2026-08-05: mid-size premium, ABS, rectangular/rounded-
rectangular shell, 9 equal 26 mm round pans in 3x3, mirror YES,
conventional hinge and clasp, refillability OFF by default, no applicator
compartment initially, provisional outer size 116 x 92 x 15 mm
(PROVISIONAL_DESIGN_DEFAULT — explicitly not confirmed).

This module builds the contract only. Whether the proposed case can
actually contain the layout is answered by the kernel and validators, and
reported honestly — the proposal is never forced to fit.
"""
from __future__ import annotations

from apps.pipeline.services.palette_contracts import (
    PaletteApplicatorCompartmentSpec, PaletteCaseSpec, PaletteClaspSpec,
    PaletteHingeSpec, PaletteLayoutSpec, PaletteLidSpec, PaletteMirrorSpec,
    PalettePanSpec, PaletteSpec, PaletteTraySpec, calculated, default,
    online)

PROPOSED_OUTER = (116.0, 92.0, 15.0)   # PROVISIONAL_DESIGN_DEFAULT


def build_palt_p1(outer_width=None, outer_depth=None, outer_height=None,
                  inter_pan_gap=4.0, outer_margin=5.0,
                  design_intent=None) -> PaletteSpec:
    """PALT-P1 contract. Defaults to the owner's provisional outer size;
    callers may pass a different case to test feasibility.

    ``design_intent`` closes the gap the PALT-M4C section D audit found:
    before it, this signature was five floats and a selected concept had
    NO channel into the palette engine at all. When an intent is supplied,
    concept-derived values replace the generic defaults and every resolved
    value carries its provenance; when it is absent the behaviour is
    unchanged, so every existing caller and every prior identity is
    preserved.

    An intent is DESIGN_INTENT_REFERENCE only. It never becomes
    manufacturing, CAD, supplier or tolerance authority, and an
    unconfirmed intent never reports as owner-approved.
    """
    if design_intent is not None:
        from apps.pipeline.services import palette_intent_mapping as _im
        _defaults = {"layout.inter_pan_gap_mm": inter_pan_gap,
                     "layout.outer_margin_mm": outer_margin}
        _m = _im.map_intent(design_intent, _defaults)
        inter_pan_gap = _m["resolved"]["layout.inter_pan_gap_mm"]["value"]
        outer_margin = _m["resolved"]["layout.outer_margin_mm"]["value"]
    w = PROPOSED_OUTER[0] if outer_width is None else outer_width
    d = PROPOSED_OUTER[1] if outer_depth is None else outer_depth
    h = PROPOSED_OUTER[2] if outer_height is None else outer_height

    pans = tuple(
        PalettePanSpec(
            pan_id=f"P{i+1}",
            shape="CIRCLE",
            width=online(26.0, "26 mm is a cross-vendor interchange "
                               "standard (R1, R2, R6)"),
            height=online(26.0, "circular pan: width == height"),
            depth=online(3.5, "shallow eye-pan family (R2)"),
            manufacturing_tolerance=default(
                0.30, "pressed-powder pans have WIDE tolerance (R10)"),
            refillable=False,
            zone="EYE",
        ) for i in range(9))

    layout = PaletteLayoutSpec(
        mode="MODULE_LATTICE",
        pans=pans,
        # the module is the POCKET module: nominal pan + 2x tolerance.
        # "Every module must resolve to explicit dimensions" (owner).
        module_width=calculated(
            26.6, "26.0 nominal pan + 2 x 0.30 manufacturing tolerance"),
        module_height=calculated(
            26.6, "26.0 nominal pan + 2 x 0.30 manufacturing tolerance"),
        rows=3, cols=3,
        occupancy=tuple((f"P{r*3+c+1}", r, c, 1, 1)
                        for r in range(3) for c in range(3)),
    )

    return PaletteSpec(
        palette_id="PALT-P1",
        case=PaletteCaseSpec(
            shape="ROUNDED_RECTANGLE",
            outer_width=default(w, "PROVISIONAL_DESIGN_DEFAULT (owner)"),
            outer_depth=default(d, "PROVISIONAL_DESIGN_DEFAULT (owner)"),
            outer_height=default(h, "PROVISIONAL_DESIGN_DEFAULT (owner)"),
            wall_thickness=default(2.0, "mid-range ABS wall (R14: 1.5-3.0)"),
            base_thickness=default(1.5),
            corner_radius=default(4.0),
            material="ABS",
        ),
        tray=PaletteTraySpec(
            wall_thickness=default(1.5, "tray pocket wall, ABS minimum"),
            floor_thickness=default(1.0),
            inter_pan_gap=default(inter_pan_gap),
            outer_margin=default(outer_margin),
        ),
        lid=PaletteLidSpec(thickness=default(1.5)),
        layout=layout,
        mirror=PaletteMirrorSpec(
            present=True, coverage="LID_FULL",
            thickness=default(1.0, "mirror thickness is a research GAP"),
        ),
        hinge=PaletteHingeSpec(
            family="PIN_HINGE",
            zone_depth=default(6.0, "rear band reserved for the hinge "
                                    "barrel; unvalidated"),
        ),
        clasp=PaletteClaspSpec(
            family="MECHANICAL_DETENT",
            zone_depth=default(5.0, "front band reserved for the clasp; "
                                    "unvalidated"),
        ),
        applicator=PaletteApplicatorCompartmentSpec(present=False),
        refillable_default=False,
    )


def feasibility_report() -> dict:
    """Answer the owner's question: does 116 x 92 x 15 actually contain
    nine pans, gaps, tray walls, hinge, clasp, mirror and plates?"""
    from apps.pipeline.services.palette_layout_kernel import (
        layout_report, minimum_feasible_case)
    from apps.pipeline.services.palette_layout_validators import (
        validate_layout)

    spec = build_palt_p1()
    validation = validate_layout(spec)
    minimum = minimum_feasible_case(spec)
    report = layout_report(spec)

    feasible_spec = build_palt_p1(
        outer_width=minimum["minimum_outer_width_mm"],
        outer_depth=minimum["minimum_outer_depth_mm"],
        outer_height=max(minimum["minimum_outer_height_mm"],
                         PROPOSED_OUTER[2]))
    feasible_validation = validate_layout(feasible_spec)

    # absolute floor: the smallest case that could EVER hold this layout,
    # using the minimum permitted spacing rather than the proposed spacing
    floor_spec = build_palt_p1(inter_pan_gap=1.5, outer_margin=1.5)
    floor = minimum_feasible_case(floor_spec)
    floor_case = build_palt_p1(
        outer_width=floor["minimum_outer_width_mm"],
        outer_depth=floor["minimum_outer_depth_mm"],
        outer_height=max(floor["minimum_outer_height_mm"], 10.0),
        inter_pan_gap=1.5, outer_margin=1.5)
    floor_validation = validate_layout(floor_case)

    return {
        "record_type": "palt_p1_feasibility/1.0",
        "proposed_outer_mm": list(PROPOSED_OUTER),
        "proposed_authority": "PROVISIONAL_DESIGN_DEFAULT (owner) — not "
                              "confirmed, not manufacturing-authoritative",
        "proposed_is_feasible": validation["valid"],
        "proposed_findings": validation["findings"],
        "minimum_feasible_case": minimum,
        "minimum_case_validates": feasible_validation["valid"],
        "minimum_case_findings": feasible_validation["findings"],
        "absolute_floor_case": {
            "description": "smallest case that could EVER hold a 3x3 of "
                           "26 mm pans with a hinge and clasp, using the "
                           "MINIMUM permitted gap (1.5) and margin (1.5)",
            "outer_mm": [floor["minimum_outer_width_mm"],
                         floor["minimum_outer_depth_mm"],
                         floor["minimum_outer_height_mm"]],
            "validates": floor_validation["valid"],
            "findings": floor_validation["findings"],
        },
        "conclusion": (
            "the proposed 92 mm depth cannot hold three rows of 26 mm pans "
            "together with hinge and clasp reservations at ANY permitted "
            "spacing — the depth is the binding constraint, not the width"),
        "layout": report["layout"],
        "contract_identity": spec.identity(),
        "method_note": "the proposal was never adjusted to make it pass; "
                       "the minimum feasible case is reported separately",
    }
