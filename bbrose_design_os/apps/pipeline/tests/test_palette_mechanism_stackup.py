"""PALT-M3 — mechanism strategy and stack-up tests.

Deterministic, non-rendering. Asserts the owner's corrections structurally:
the three height values stay separated, nothing auto-shrinks, module
resolution includes the retention envelope, and no market listing is
treated as a technical drawing.
"""
import json
import pathlib

from django.test import SimpleTestCase

from apps.pipeline.services.palette_contracts import PaletteContractError
from apps.pipeline.services.palette_mechanism_contracts import (
    CLASP_ENVELOPES, CLASP_STRATEGIES, HINGE_ENVELOPES, HINGE_STRATEGIES,
    PALT_P1_BASELINE, RETENTION_ENVELOPES, RETENTION_STRATEGIES,
    MechanismStrategySpec)
from apps.pipeline.services.palette_mechanism_validators import (
    MECHANISM_ENVELOPE_UNDEFINED, MECHANISM_MATERIAL_CONFLICT,
    palt_p1_strategy_matrix, validate_strategy)
from apps.pipeline.services.palette_stackup_engine import (
    ALLOWANCES, footprint_stackup, height_stackup, pocket_module_mm)
from apps.pipeline.services.palt_p1 import build_palt_p1

DOCS = pathlib.Path("docs/roadmap/palt_m3")


def _strategy(**kw):
    base = dict(hinge_strategy="INTERNAL_RESERVED_BAND_PIN_HINGE",
                clasp_strategy="INTERNAL_RESERVED_BAND_SNAP_CLASP",
                retention_strategy="ADHESIVE_FIXED")
    base.update(kw)
    return MechanismStrategySpec(**base)


class StrategyContractTests(SimpleTestCase):
    def test_every_hinge_strategy_has_an_envelope(self):
        for name in HINGE_STRATEGIES:
            assert name in HINGE_ENVELOPES, name
            env = HINGE_ENVELOPES[name]
            assert env.internal_band.mm >= 0 and env.wall_add.mm >= 0

    def test_every_clasp_strategy_has_an_envelope(self):
        for name in CLASP_STRATEGIES:
            assert name in CLASP_ENVELOPES, name

    def test_every_retention_strategy_has_an_envelope(self):
        for name in RETENTION_STRATEGIES:
            assert name in RETENTION_ENVELOPES, name

    def test_unknown_strategies_are_refused(self):
        for kw in ({"hinge_strategy": "MAGIC"}, {"clasp_strategy": "MAGIC"},
                   {"retention_strategy": "MAGIC"},
                   {"hinge_edge": "DIAGONAL"},
                   {"case_orientation": "SIDEWAYS"}):
            with self.assertRaises(PaletteContractError):
                _strategy(**kw)

    def test_hinge_and_clasp_cannot_share_an_edge(self):
        with self.assertRaises(PaletteContractError):
            _strategy(hinge_edge="TOP_EDGE", clasp_edge="TOP_EDGE")

    def test_custom_placeholders_fail_closed(self):
        spec = build_palt_p1()
        for kw in ({"hinge_strategy": "CUSTOM_MECHANISM_PLACEHOLDER"},
                   {"clasp_strategy": "CUSTOM_MECHANISM_PLACEHOLDER"},
                   {"retention_strategy": "CUSTOM_RETENTION_PLACEHOLDER"}):
            report = validate_strategy(spec, _strategy(**kw))
            assert not report["valid"]
            assert MECHANISM_ENVELOPE_UNDEFINED in {
                f["code"] for f in report["findings"]}

    def test_living_hinge_conflicts_with_an_abs_case(self):
        spec = build_palt_p1()          # ABS
        report = validate_strategy(spec, _strategy(
            hinge_strategy="LIVING_HINGE"))
        assert MECHANISM_MATERIAL_CONFLICT in {f["code"]
                                               for f in report["findings"]}

    def test_undefined_retention_pocket_raises_rather_than_assuming_zero(self):
        spec = build_palt_p1()
        with self.assertRaises(ValueError):
            pocket_module_mm(spec, _strategy(
                retention_strategy="CUSTOM_RETENTION_PLACEHOLDER"))


class EdgeMappingTests(SimpleTestCase):
    def test_top_bottom_edges_consume_depth(self):
        s = _strategy(hinge_edge="TOP_EDGE", clasp_edge="BOTTOM_EDGE")
        assert s.hinge_axis == "depth" and s.clasp_axis == "depth"

    def test_left_right_edges_consume_width(self):
        s = _strategy(hinge_edge="LEFT_EDGE", clasp_edge="RIGHT_EDGE")
        assert s.hinge_axis == "width" and s.clasp_axis == "width"

    def test_edge_mapping_changes_feasibility(self):
        spec = build_palt_p1()
        long_edge = footprint_stackup(
            spec, _strategy(hinge_edge="TOP_EDGE", clasp_edge="BOTTOM_EDGE"),
            3, 3)
        short_edge = footprint_stackup(
            spec, _strategy(hinge_edge="LEFT_EDGE", clasp_edge="RIGHT_EDGE"),
            3, 3)
        # the reserved bands move from the depth axis onto the width axis
        assert short_edge.minimum_width_mm > long_edge.minimum_width_mm
        assert short_edge.minimum_depth_mm < long_edge.minimum_depth_mm

    def test_portrait_and_landscape_are_both_recorded(self):
        for orientation in ("PORTRAIT", "LANDSCAPE"):
            s = _strategy(case_orientation=orientation)
            assert s.case_orientation == orientation


class HeightStackupTests(SimpleTestCase):
    def setUp(self):
        self.spec = build_palt_p1()
        self.stack = height_stackup(self.spec, PALT_P1_BASELINE)

    def test_three_values_stay_strictly_separated(self):
        assert (self.stack.geometric_lower_bound_mm
                < self.stack.engineering_minimum_mm
                < self.stack.premium_design_target_mm)

    def test_lower_bound_carries_a_non_production_warning(self):
        assert "never" in self.stack.as_dict()["warning"].lower()
        assert "production recommendation" in self.stack.as_dict()["warning"]

    def test_full_height_arithmetic_is_explicit(self):
        c = self.stack.components
        for key in ("outer_base_skin", "tray_floor", "pan_depth",
                    "pan_seating_adhesive", "pan_proud_recess",
                    "powder_crown", "interior_clearance_above_powder",
                    "lid_inner_skin", "lid_outer_skin", "mirror_thickness",
                    "mirror_adhesive", "mirror_safety_clearance",
                    "hinge_height_envelope", "clasp_closure_clearance",
                    "cosmetic_parting_gap", "manufacturing_tolerance",
                    "warpage_allowance", "decoration_insert_allowance"):
            assert key in c, key

    def test_mirror_and_adhesive_stack_is_included_only_when_present(self):
        from apps.pipeline.services.palette_contracts import (
            PaletteMirrorSpec)
        import dataclasses
        no_mirror = dataclasses.replace(
            self.spec, mirror=PaletteMirrorSpec(present=False))
        other = height_stackup(no_mirror, PALT_P1_BASELINE)
        delta = (self.stack.engineering_minimum_mm
                 - other.engineering_minimum_mm)
        expected = (self.spec.mirror.thickness.mm
                    + ALLOWANCES["mirror_adhesive_mm"]
                    + ALLOWANCES["mirror_safety_clearance_mm"])
        assert abs(delta - expected) < 1e-6

    def test_powder_clearance_and_warpage_are_enforced_in_engineering(self):
        gap = (self.stack.engineering_minimum_mm
               - self.stack.geometric_lower_bound_mm)
        assert gap >= (ALLOWANCES["powder_crown_mm"]
                       + ALLOWANCES["warpage_allowance_mm"]
                       + ALLOWANCES["manufacturing_tolerance_mm"])

    def test_magnetic_retention_adds_height(self):
        magnetic = height_stackup(self.spec, _strategy(
            retention_strategy="MAGNETIC_REFILL"))
        assert (magnetic.engineering_minimum_mm
                > self.stack.engineering_minimum_mm)


class FootprintStackupTests(SimpleTestCase):
    def test_module_resolves_to_the_full_pocket_and_retention_envelope(self):
        spec = build_palt_p1()
        adhesive = pocket_module_mm(spec, _strategy(
            retention_strategy="ADHESIVE_FIXED"))
        lip = pocket_module_mm(spec, _strategy(
            retention_strategy="RETENTION_LIP"))
        # owner correction: the module is NOT merely nominal pan + tolerance
        assert lip[0] > adhesive[0]
        assert adhesive[0] == 26.0 + 2 * 0.3

    def test_wall_integrated_needs_less_internal_space_than_reserved_band(self):
        spec = build_palt_p1()
        band = footprint_stackup(spec, _strategy(), 3, 3)
        wall = footprint_stackup(spec, _strategy(
            hinge_strategy="WALL_INTEGRATED_PIN_HINGE",
            clasp_strategy="WALL_INTEGRATED_SNAP_CLASP"), 3, 3)
        assert wall.minimum_depth_mm < band.minimum_depth_mm

    def test_external_hinge_reports_external_addition_separately(self):
        spec = build_palt_p1()
        ext = footprint_stackup(spec, _strategy(
            hinge_strategy="EXTERNAL_BARREL_HINGE"), 3, 3)
        assert ext.external_depth_add_mm > 0
        d = ext.as_dict()
        assert d["total_external_depth_mm"] > d["minimum_depth_mm"]

    def test_footprint_components_are_explicit(self):
        spec = build_palt_p1()
        c = footprint_stackup(spec, _strategy(), 3, 3).components
        for key in ("pocket_module_w", "pan_field_w", "inter_pan_gap",
                    "outer_margin_x2", "internal_tray_walls_x2",
                    "outer_case_walls_x2", "hinge_internal_band",
                    "clasp_internal_band", "lid_structural_border_x2",
                    "assembly_clearance", "moulding_tolerance",
                    "corner_radius_effect"):
            assert key in c, key


class StrategyMatrixTests(SimpleTestCase):
    def setUp(self):
        self.matrix = palt_p1_strategy_matrix()

    def test_matrix_is_deterministic(self):
        assert json.dumps(self.matrix, sort_keys=True) == \
            json.dumps(palt_p1_strategy_matrix(), sort_keys=True)

    def test_pan_layout_is_retained_not_reduced(self):
        assert "3 x 3" in self.matrix["pan_layout"]
        assert "not reduced to 3x2" in self.matrix["pan_layout"].lower()

    def test_multiple_strategies_and_both_hinge_edges_are_tested(self):
        hinges = {c["mechanism"]["hinge_strategy"]
                  for c in self.matrix["configurations"]}
        edges = {c["mechanism"]["hinge_edge"]
                 for c in self.matrix["configurations"]}
        assert len(hinges) >= 2 and len(edges) >= 2

    def test_target_result_is_scoped_to_tested_strategies_only(self):
        result = self.matrix["target_envelope_result"]
        assert "ALL_TESTED" in result["classification"]
        assert "NOT proven infeasible under ALL POSSIBLE" in \
            result["explicitly_not"]

    def test_every_configuration_states_the_envelope_it_was_judged_against(
            self):
        for c in self.matrix["configurations"]:
            assert c["judged_against_envelope_mm"]

    def test_matrix_does_not_auto_select_the_smallest(self):
        assert "NEVER chosen" in self.matrix["selection_rule"]

    def test_each_configuration_reports_provenance_and_unknowns(self):
        for c in self.matrix["configurations"]:
            assert c["dimension_provenance"]
            assert c["confidence"]
            assert isinstance(c["manufacturing_unknowns"], list)

    def test_no_configuration_claims_manufacturing_readiness(self):
        assert self.matrix["manufacturing_readiness"] == "NOT_ESTABLISHED"


class OwnerCorrectionTests(SimpleTestCase):
    def test_supplier_outreach_reports_the_channel_limitation_honestly(self):
        log = json.loads((DOCS / "supplier_outreach_log.json").read_text())
        assert log["requests_sent"] == 0
        assert log["responses_received"] == 0
        assert log["CHANNEL_STATUS"] == \
            "NO_APPROVED_OUTBOUND_COMMUNICATION_CHANNEL_AVAILABLE"
        for r in log["prepared_recipients"]:
            assert r["request_status"] == "PREPARED_NOT_SENT"
            assert r["request_date"] is None

    def test_no_market_listing_is_treated_as_a_technical_drawing(self):
        log = json.loads((DOCS / "supplier_outreach_log.json").read_text())
        for r in log["prepared_recipients"]:
            assert r["received_files"] == []
            # provenance is conditional ("if received"), never asserted now
            assert "provenance_if_received" in r

    def test_strategy_matrix_records_the_corrected_classification(self):
        matrix = json.loads((DOCS / "palt_p1_strategy_matrix.json")
                            .read_text())
        assert "TARGET_DESIGN_ENVELOPE" in \
            matrix["target_envelope_classification"][0]

    def test_height_artifact_keeps_the_three_values_separate(self):
        stack = json.loads((DOCS / "palt_p1_height_stackup.json").read_text())
        assert stack["GEOMETRIC_LOWER_BOUND_mm"] < \
            stack["ENGINEERING_MINIMUM_mm"] < \
            stack["PREMIUM_DESIGN_TARGET_mm"]
        assert "production recommendation" in stack["warning"]
