"""PALT-M2 — palette contract and layout kernel tests.

Deterministic, non-rendering. Fail-closed behaviour is asserted with
negatives: every validator code must be reachable, and the kernel must
never repair an invalid layout.
"""
import json

from django.test import SimpleTestCase

from apps.pipeline.services import palette_layout_validators as V
from apps.pipeline.services.palette_contracts import (
    PaletteApplicatorCompartmentSpec, PaletteCaseSpec, PaletteClaspSpec,
    PaletteContractError, PaletteHingeSpec, PaletteLayoutSpec,
    PaletteLidSpec, PaletteMirrorSpec, PalettePanSpec, PaletteSpec,
    PaletteTraySpec, calculated, default, online, to_jsonable)
from apps.pipeline.services.palette_layout_kernel import (
    derived_closed_height, layout_report, minimum_feasible_case,
    resolve_layout)
from apps.pipeline.services.palt_p1 import build_palt_p1, feasibility_report


def _pan(pan_id, w=26.0, h=26.0, depth=3.5, tol=0.3, refillable=False,
         removal=0.0, shape="CIRCLE", zone="EYE"):
    return PalettePanSpec(
        pan_id=pan_id, shape=shape, width=online(w), height=online(h),
        depth=online(depth), manufacturing_tolerance=default(tol),
        removal_clearance=default(removal), refillable=refillable, zone=zone)


def _spec(pans, layout, *, w=140.0, d=140.0, h=15.0, gap=4.0, margin=5.0,
          hinge=6.0, clasp=5.0, mirror=True, material="ABS",
          case_wall=2.0, tray_wall=1.5, applicator=0.0):
    return PaletteSpec(
        palette_id="TEST",
        case=PaletteCaseSpec(
            shape="ROUNDED_RECTANGLE", outer_width=default(w),
            outer_depth=default(d), outer_height=default(h),
            wall_thickness=default(case_wall), base_thickness=default(1.5),
            material=material),
        tray=PaletteTraySpec(
            wall_thickness=default(tray_wall), floor_thickness=default(1.0),
            inter_pan_gap=default(gap), outer_margin=default(margin)),
        lid=PaletteLidSpec(thickness=default(1.5)),
        layout=layout,
        mirror=PaletteMirrorSpec(present=mirror),
        hinge=PaletteHingeSpec(
            family="PIN_HINGE" if hinge else "NONE",
            zone_depth=default(hinge)),
        clasp=PaletteClaspSpec(
            family="MECHANICAL_DETENT" if clasp else "NONE",
            zone_depth=default(clasp)),
        applicator=PaletteApplicatorCompartmentSpec(
            present=bool(applicator), kind="BRUSH_SLOT" if applicator
            else "NONE", zone_depth=default(applicator)),
    )


def _grid(rows, cols, module=26.6):
    pans = tuple(_pan(f"P{i+1}") for i in range(rows * cols))
    layout = PaletteLayoutSpec(
        mode="MODULE_LATTICE", pans=pans,
        module_width=calculated(module), module_height=calculated(module),
        rows=rows, cols=cols,
        occupancy=tuple((f"P{r*cols+c+1}", r, c, 1, 1)
                        for r in range(rows) for c in range(cols)))
    return pans, layout


class ContractTests(SimpleTestCase):
    def test_every_dimension_keeps_provenance(self):
        spec = build_palt_p1()
        data = to_jsonable(spec)
        pan = data["layout"]["pans"][0]["width"]
        for key in ("value", "unit", "provenance", "confidence", "authority"):
            assert key in pan, key
        assert data["case"]["outer_width"]["provenance"] == "DESIGN_DEFAULT"
        assert pan["provenance"] == "ONLINE_REPORTED"

    def test_unknown_vocabulary_is_refused(self):
        with self.assertRaises(PaletteContractError):
            default(1.0).__class__(1.0, provenance="MADE_UP")
        with self.assertRaises(PaletteContractError):
            PalettePanSpec("X", "TRIANGLE", online(1), online(1), online(1))
        with self.assertRaises(PaletteContractError):
            PaletteCaseSpec("BLOB", default(1), default(1), default(1),
                            default(1), default(1))

    def test_negative_and_nonnumeric_dimensions_refused(self):
        with self.assertRaises(PaletteContractError):
            default(-1.0)
        with self.assertRaises(PaletteContractError):
            default("wide")

    def test_custom_silhouette_requires_evidence(self):
        with self.assertRaises(PaletteContractError):
            PaletteCaseSpec("CUSTOM_SILHOUETTE", default(1), default(1),
                            default(1), default(1), default(1),
                            outline_points=((0, 0), (1, 1)))

    def test_duplicate_pan_ids_refused(self):
        pans = (_pan("A"), _pan("A"))
        with self.assertRaises(PaletteContractError):
            PaletteLayoutSpec(mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
                              placements=(("A", 0, 0),))

    def test_layout_mode_requires_its_own_fields(self):
        pans = (_pan("A"),)
        with self.assertRaises(PaletteContractError):
            PaletteLayoutSpec(mode="MODULE_LATTICE", pans=pans)
        with self.assertRaises(PaletteContractError):
            PaletteLayoutSpec(mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans)

    def test_contract_identity_is_deterministic_and_sensitive(self):
        a, b = build_palt_p1(), build_palt_p1()
        assert a.identity() == b.identity()
        assert a.identity() != build_palt_p1(outer_width=120.0).identity()


class ModuleLatticeTests(SimpleTestCase):
    def test_three_by_three_layout_resolves(self):
        pans, layout = _grid(3, 3)
        result = resolve_layout(_spec(pans, layout))
        assert len(result.placed) == 9
        assert result.lattice["module_equivalence_authority"] == \
            "CALCULATED_LAYOUT_HEURISTIC"
        xs = sorted({round(p.x_mm, 3) for p in result.placed})
        ys = sorted({round(p.y_mm, 3) for p in result.placed})
        assert len(xs) == 3 and len(ys) == 3
        assert abs((xs[1] - xs[0]) - (26.6 + 4.0)) < 1e-6   # pitch

    def test_mixed_size_layout_resolves(self):
        big = _pan("BIG", w=55.0, h=26.0, depth=5.0, shape="ROUNDED_RECTANGLE",
                   zone="BLUSH")
        small = tuple(_pan(f"S{i}") for i in range(2))
        pans = (big,) + small
        layout = PaletteLayoutSpec(
            mode="MODULE_LATTICE", pans=pans,
            module_width=calculated(26.6), module_height=calculated(26.6),
            rows=2, cols=2,
            occupancy=(("BIG", 0, 0, 2, 1), ("S0", 1, 0, 1, 1),
                       ("S1", 1, 1, 1, 1)))
        report = V.validate_layout(_spec(pans, layout))
        assert report["valid"], report["findings"]

    def test_module_must_contain_pan_including_tolerance(self):
        pans, layout = _grid(2, 2, module=26.0)   # pan+tol = 26.6 > 26.0
        report = V.validate_layout(_spec(pans, layout))
        codes = {f["code"] for f in report["findings"]}
        assert V.MODULE_SMALLER_THAN_PAN_FOOTPRINT in codes

    def test_layout_is_deterministic(self):
        pans, layout = _grid(3, 3)
        spec = _spec(pans, layout)
        a = json.dumps(layout_report(spec), sort_keys=True)
        b = json.dumps(layout_report(spec), sort_keys=True)
        assert a == b


class AbsoluteLayoutTests(SimpleTestCase):
    def test_direct_coordinate_layout_resolves_and_validates(self):
        pans = (_pan("A"), _pan("B"))
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 10.0, 10.0), ("B", 45.0, 10.0)))
        spec = _spec(pans, layout)
        result = resolve_layout(spec)
        assert result.mode == "ABSOLUTE_DIMENSIONAL_LAYOUT"
        assert V.validate_layout(spec)["valid"]

    def test_overlapping_direct_placement_is_rejected(self):
        pans = (_pan("A"), _pan("B"))
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 10.0, 10.0), ("B", 20.0, 10.0)))
        report = V.validate_layout(_spec(pans, layout))
        assert not report["valid"]
        assert V.PAN_OVERLAP in {f["code"] for f in report["findings"]}

    def test_unknown_pan_reference_refused(self):
        pans = (_pan("A"),)
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("GHOST", 0.0, 0.0),))
        with self.assertRaises(PaletteContractError):
            resolve_layout(_spec(pans, layout))


class ValidatorNegativeTests(SimpleTestCase):
    def test_case_boundary_violation(self):
        pans, layout = _grid(3, 3)
        report = V.validate_layout(_spec(pans, layout, w=70.0, d=70.0))
        assert V.CASE_BOUNDARY_VIOLATION in {f["code"]
                                             for f in report["findings"]}

    def test_hinge_zone_collision(self):
        pans = (_pan("A"),)
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 10.0, 60.0),))
        report = V.validate_layout(_spec(pans, layout, d=90.0, hinge=20.0))
        assert V.HINGE_ZONE_COLLISION in {f["code"]
                                          for f in report["findings"]}

    def test_clasp_zone_collision(self):
        pans = (_pan("A"),)
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 10.0, 1.0),))
        report = V.validate_layout(_spec(pans, layout, clasp=12.0))
        assert V.CLASP_ZONE_COLLISION in {f["code"]
                                          for f in report["findings"]}

    def test_applicator_zone_collision(self):
        pans = (_pan("A"),)
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 10.0, 6.0),))
        report = V.validate_layout(
            _spec(pans, layout, clasp=5.0, applicator=15.0))
        assert V.APPLICATOR_ZONE_COLLISION in {f["code"]
                                               for f in report["findings"]}

    def test_minimum_gap_enforced(self):
        pans = (_pan("A"), _pan("B"))
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 10.0, 10.0), ("B", 37.0, 10.0)))
        report = V.validate_layout(_spec(pans, layout))
        assert V.INSUFFICIENT_INTER_PAN_GAP in {f["code"]
                                                for f in report["findings"]}

    def test_outer_margin_enforced(self):
        pans = (_pan("A"),)
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 0.5, 20.0),))
        report = V.validate_layout(_spec(pans, layout))
        assert V.INSUFFICIENT_OUTER_MARGIN in {f["code"]
                                               for f in report["findings"]}

    def test_wall_thickness_enforced(self):
        pans, layout = _grid(2, 2)
        report = V.validate_layout(_spec(pans, layout, case_wall=0.8))
        assert V.WALL_BELOW_MINIMUM in {f["code"] for f in report["findings"]}

    def test_case_thickness_enforced(self):
        pans, layout = _grid(2, 2)
        report = V.validate_layout(_spec(pans, layout, h=5.0))
        assert V.INSUFFICIENT_CASE_THICKNESS in {f["code"]
                                                 for f in report["findings"]}

    def test_refill_without_removal_clearance_rejected(self):
        pans = (_pan("A", refillable=True, removal=0.0),)
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 20.0, 20.0),))
        report = V.validate_layout(_spec(pans, layout))
        assert V.INVALID_REFILL_REMOVAL_CLEARANCE in {
            f["code"] for f in report["findings"]}

    def test_refillable_pan_with_clearance_passes(self):
        pans = (_pan("A", refillable=True, removal=0.4),)
        layout = PaletteLayoutSpec(
            mode="ABSOLUTE_DIMENSIONAL_LAYOUT", pans=pans,
            placements=(("A", 20.0, 20.0),))
        assert V.validate_layout(_spec(pans, layout))["valid"]

    def test_mirror_reservation_is_in_the_derived_height(self):
        pans, layout = _grid(2, 2)
        with_mirror = derived_closed_height(_spec(pans, layout, mirror=True))
        without = derived_closed_height(_spec(pans, layout, mirror=False))
        assert with_mirror - without == 1.0


class MinimumFeasibleTests(SimpleTestCase):
    def test_kernel_reports_minimum_and_never_repairs(self):
        pans, layout = _grid(3, 3)
        spec = _spec(pans, layout, w=70.0, d=70.0)
        minimum = minimum_feasible_case(spec)
        assert minimum["minimum_outer_width_mm"] > 70.0
        # the invalid spec is untouched — no silent shrinking
        assert spec.case.outer_width.mm == 70.0
        assert not V.validate_layout(spec)["valid"]

    def test_palt_p1_proposed_case_is_infeasible_and_floor_is_reported(self):
        report = feasibility_report()
        assert report["proposed_is_feasible"] is False
        codes = {f["code"] for f in report["proposed_findings"]}
        assert V.HINGE_ZONE_COLLISION in codes
        assert V.CASE_BOUNDARY_VIOLATION in codes
        minimum = report["minimum_feasible_case"]
        assert minimum["minimum_outer_depth_mm"] > 92.0
        assert report["minimum_case_validates"] is True
        floor = report["absolute_floor_case"]
        assert floor["validates"] is True
        # even at minimum permitted spacing the 92 mm depth cannot work
        assert floor["outer_mm"][1] > 92.0

    def test_palt_p1_contract_matches_owner_decisions(self):
        spec = build_palt_p1()
        assert spec.case.material == "ABS"
        assert spec.mirror.present is True
        assert spec.refillable_default is False
        assert spec.applicator.present is False
        assert spec.hinge.family == "PIN_HINGE"
        assert spec.clasp.family == "MECHANICAL_DETENT"
        assert len(spec.layout.pans) == 9
        assert all(p.width.mm == 26.0 for p in spec.layout.pans)
