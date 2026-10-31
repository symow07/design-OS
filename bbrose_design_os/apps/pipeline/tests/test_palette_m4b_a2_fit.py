"""PALT-M4B-A2 — pan/pocket fit and dimension authority tests.

§1 of the owner's brief corrects my M4B-A framing: the requirement is not
inverted. Interference detection and pilot acceptance are SEPARATE tests:

* a deliberately invalid configuration must raise PAN_POCKET_INTERSECTION
* the actual PALT-P1 pilot must show zero intersections and positive
  clearance

Both are asserted below, against real built geometry.
"""
import math

from django.test import SimpleTestCase

from apps.pipeline.services import palette_clearance_policy as cp
from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palette_pan_profile as pp
from apps.pipeline.services import palette_pocket_datums as pdat
from apps.pipeline.services import palette_thickness_analysis as ta
from apps.pipeline.services import palt_m4b_a2 as A2
from apps.pipeline.services.palette_recessed_tray_geometry import (
    RecessedTrayError, build_recessed_palette_tray)


class _Base(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.matrix = A2.resolution_matrix()
        cls.selection = A2.select_strategy(cls.matrix)
        cls.assembly = A2.build_selected(cls.selection)
        cls.tray = cls.assembly["tray"]
        cls.datums = pdat.pocket_datums(cls.tray, A2.PAN)
        cls.chosen = next(r for r in cls.matrix["strategies"]
                          if r["strategy"] == cls.selection["selected"])


class NegativeInterferenceTests(_Base):
    """A. the validator must fire on a deliberately invalid configuration."""

    def test_negative_interference_detection(self):
        bad = A2.evaluate_strategy("DELIBERATELY_INVALID", {
            "description": "sharp pan in a pocket built at the layout "
                           "module — the M4B-A mistake",
            "sharp_wall_diameter_at_deck_mm": 26.0,
            "functional_diameter_mm": None,
            "floor_fillet_mm": 0.6, "base_corner_radius_mm": 0.0})
        self.assertLess(bad["governing_clearance_mm"], 0.0)
        self.assertFalse(bad["valid"])
        self.assertFalse(
            bad["clearance_tiers"][cp.GEOMETRIC]["established"])

    def test_validator_reports_the_code_on_an_invalid_pilot(self):
        spec = dict(A2.BASE)
        spec["pocket_sharp_wall_theoretical_diameter_at_deck_mm"] = 26.0
        tray = build_recessed_palette_tray(spec)
        contract = {"pan": dict(A2.PAN)}
        contract["pan"]["pan_outside_diameter_mm"] = 26.0
        rep = mv.validate_pan_seating(tray, contract)
        self.assertIn(mv.PAN_POCKET_INTERSECTION,
                      [f["code"] for f in rep["findings"]])

    def test_m4b_a_configuration_is_reproduced_exactly(self):
        """The rejected -0.0542 mm must be reproducible, or the control is
        not evidence."""
        repro = next(c for c in self.matrix["controls"]
                     if c["strategy"] == "CONTROL_M4B_A_REPRODUCTION")
        self.assertAlmostEqual(repro["min_radial_clearance_mm"], -0.0542,
                               places=4)
        self.assertFalse(repro["seating"]["stable"])


class PilotAcceptanceTests(_Base):
    """B. the real pilot must pass — not be excused."""

    def test_zero_intersection_pilot_acceptance(self):
        self.assertEqual(self._intersection_count(), 0)

    def _intersection_count(self):
        contract = {"pan": dict(A2.PAN)}
        rep = mv.validate_pan_seating(self.tray, contract)
        return len([f for f in rep["findings"]
                    if f["code"] == mv.PAN_POCKET_INTERSECTION])

    def test_positive_minimum_clearance(self):
        self.assertGreater(self.chosen["governing_clearance_mm"], 0.0)
        self.assertGreater(self.chosen["min_radial_clearance_mm"], 0.0)
        self.assertGreater(self.chosen["min_normal_clearance_mm"], 0.0)

    def test_engineering_clearance_is_established(self):
        tiers = self.chosen["clearance_tiers"]
        self.assertTrue(tiers[cp.GEOMETRIC]["established"])
        self.assertTrue(tiers[cp.ENGINEERING]["established"])
        self.assertGreaterEqual(self.chosen["governing_clearance_mm"],
                                cp.engineering_minimum_mm())

    def test_manufacturing_clearance_is_never_established(self):
        tiers = self.chosen["clearance_tiers"]
        self.assertFalse(tiers[cp.MANUFACTURING]["established"])
        self.assertEqual(tiers[cp.MANUFACTURING]["status"],
                         "NOT_ESTABLISHED")
        self.assertFalse(tiers["production_ready"])

    def test_pan_seating_stability(self):
        seat = self.chosen["seating"]
        self.assertTrue(seat["stable"])
        self.assertEqual(seat["contact_mode"], "FLAT_FACE_SEATING")
        self.assertGreaterEqual(seat["flat_seating_margin_mm"], 0.0)

    def test_pan_recess_preserved(self):
        self.assertAlmostEqual(self.chosen["pan_recess_mm"], 1.00, places=9)

    def test_powder_clearance_preserved(self):
        crown = A2.PAN["pan_top_z_mm"] + A2.PAN["powder_crown_mm"]
        head = A2.PAN["lid_inner_z_mm"] - crown
        self.assertGreaterEqual(head, A2.PAN["powder_to_lid_clearance_mm"])

    def test_tray_remains_manifold_and_watertight(self):
        rep = mv.validate_mesh("recessed_palette_tray", self.tray)
        d = rep["diagnostics"]
        self.assertEqual(d["boundary_edges"], 0)
        self.assertEqual(d["non_manifold_edges"], 0)
        self.assertEqual(d["inconsistent_half_edges"], 0)
        self.assertEqual(d["euler_characteristic"], 2)
        self.assertEqual(d["t_junctions"], 0)
        self.assertEqual(d["self_intersecting_pairs"], 0)
        self.assertTrue(rep["valid"], rep["findings"])

    def test_every_pan_mesh_is_manifold(self):
        for name, comp in self.assembly["components"].items():
            if not name.startswith("metal_pan_"):
                continue
            rep = mv.validate_mesh(name, comp,
                                   check_self_intersection=False)
            self.assertTrue(rep["valid"], (name, rep["findings"]))


class DatumSemanticsTests(_Base):
    def test_explicit_dimension_datum_semantics(self):
        d = self.datums["datums"]
        self.assertEqual(len(d), 7)
        for row in d.values():
            for key in ("value_mm", "z_datum_mm", "measurement_direction",
                        "provenance", "authority", "controls_fit",
                        "visual_only"):
                self.assertIn(key, row)
        self.assertTrue(pdat.validate_datums(self.datums, A2.PAN)["valid"])

    def test_visible_mouth_is_not_fit_controlling(self):
        d = self.datums["datums"]
        mouth = d["POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM"]
        func = d["POCKET_FUNCTIONAL_DIAMETER_AT_SEATING_DATUM"]
        self.assertFalse(mouth["controls_fit"])
        self.assertTrue(mouth["visual_only"])
        self.assertTrue(func["controls_fit"])
        self.assertGreater(mouth["value_mm"], func["value_mm"])

    def test_26_6_and_26_8_conflict_is_recorded(self):
        rec = pdat.conflict_record()
        values = [e["value_mm"] for e in rec["entries"]]
        self.assertIn(26.6, values)
        self.assertIn(26.8, values)
        by_value = {e["value_mm"]: e for e in rec["entries"]}
        # both survive; neither is deleted
        self.assertFalse(by_value[26.6]["controls_fit"])
        self.assertTrue(by_value[26.8]["controls_fit"])
        self.assertEqual(by_value[26.6]["re_datumed_as"].split(" (")[0],
                         "PAN_MAXIMUM_ENVELOPE_DIAMETER")
        self.assertTrue(rec["retired_field"]["values_preserved"])
        self.assertEqual(rec["retired_field"]["name"], "pocket_diameter_mm")

    def test_ambiguous_field_fails_closed(self):
        spec = A2.tray_spec()
        spec["pocket_diameter_mm"] = 26.6
        with self.assertRaises(RecessedTrayError) as ctx:
            build_recessed_palette_tray(spec)
        self.assertIn("retired", str(ctx.exception))
        with self.assertRaises(pdat.PocketDatumError):
            pdat.assert_no_ambiguous_field({"pocket_diameter_mm": 26.6})

    def test_functional_datum_solves_back_to_itself(self):
        """The solver is exact, not iterative — round-trip must be tight."""
        for target in (26.5, 26.8, 27.2):
            spec = A2.tray_spec(functional_diameter_mm=target)
            tray = build_recessed_palette_tray(spec)
            got = pdat.profile_radius(tray["pocket_profile_rings"],
                                      A2.PAN["pan_seating_z_mm"]) * 2.0
            self.assertAlmostEqual(got, target, places=7)

    def test_layout_module_is_not_the_fit_datum(self):
        self.assertEqual(A2.LAYOUT_MODULE_MM, 26.6)
        self.assertEqual(A2.FUNCTIONAL_DIAMETER_MM, 26.8)
        self.assertNotEqual(A2.LAYOUT_MODULE_MM, A2.FUNCTIONAL_DIAMETER_MM)


class PanProfileTests(_Base):
    def test_pan_base_radius_parameter(self):
        for br in pp.TESTED_BASE_RADII_MM:
            pan = pp.build_metal_pan("p", z0=2.65, base_corner_radius_mm=br)
            self.assertAlmostEqual(pan["flat_base_radius_mm"], 13.0 - br,
                                   places=9)
            self.assertAlmostEqual(pan["config"]["base_corner_radius_mm"],
                                   br, places=9)
        self.assertIn("base_corner_radius_mm", pp.PAN_CONTRACT)
        self.assertEqual(pp.PAN_EDGE_PROFILE_AUTHORITY,
                         "PROVISIONAL_DESIGN_DEFAULT")
        self.assertEqual(pp.PAN_MANUFACTURING_AUTHORITY, "NOT_ESTABLISHED")

    def test_pan_contract_carries_every_required_field(self):
        for field in ("pan_outside_diameter_mm", "side_wall_draft_deg",
                      "base_corner_radius_mm", "floor_radius_mm",
                      "metal_wall_thickness_mm", "metal_floor_thickness_mm",
                      "pan_depth_mm"):
            self.assertIn(field, pp.PAN_CONTRACT)
        for row in pp.contract_provenance().values():
            self.assertEqual(row["manufacturing_authority"],
                             "NOT_ESTABLISHED")

    def test_pan_profile_fails_closed(self):
        for bad in (-0.1, 20.0):
            with self.assertRaises(pp.PanProfileError):
                pp.outer_profile(outside_diameter=26.0, depth=3.5,
                                 base_corner_radius=bad)

    def test_larger_base_radius_removes_material(self):
        vols = []
        for br in (0.0, 0.30, 0.40, 0.50):
            pan = pp.build_metal_pan("p", z0=2.65,
                                     base_corner_radius_mm=br)
            v, f = pan["vertices"], pan["faces"]
            import numpy as np
            a = v[f[:, 0]]
            vols.append(float(np.einsum(
                "ij,ij->i", a,
                np.cross(v[f[:, 1]] - a, v[f[:, 2]] - a)).sum() / 6.0))
        self.assertEqual(vols, sorted(vols, reverse=True))


class StrategyMatrixTests(_Base):
    def test_strategy_A_calculations(self):
        row = self._row("A_FILLET_REDUCTION")
        self.assertLess(row["inputs"]["floor_fillet_mm"], 0.6)
        self.assertFalse(row["seating"]["stable"])
        self.assertFalse(row["valid"])

    def test_strategy_B_calculations(self):
        row = self._row("B_POCKET_ENLARGEMENT")
        self.assertAlmostEqual(row["inputs"]["floor_fillet_mm"], 0.6,
                               places=9)
        self.assertGreater(row["inputs"]["functional_diameter_mm"],
                           A2.LAYOUT_MODULE_MM)
        self.assertFalse(row["seating"]["stable"])
        self.assertFalse(row["valid"])

    def test_strategy_C_calculations(self):
        for br in pp.TESTED_BASE_RADII_MM:
            row = self._row(f"C_ROUNDED_PAN_BASE_0_{int(br * 100):02d}")
            self.assertAlmostEqual(row["inputs"]["base_corner_radius_mm"],
                                   br, places=9)
            self.assertAlmostEqual(row["inputs"]["floor_fillet_mm"], 0.6,
                                   places=9)
            self.assertTrue(row["valid"])
            self.assertTrue(row["seating"]["stable"])

    def test_every_strategy_reports_every_required_metric(self):
        required = ("valid", "min_radial_clearance_mm",
                    "min_normal_clearance_mm", "min_vertical_clearance_mm",
                    "pan_seating_elevation_mm", "pan_recess_mm",
                    "deck_ligament_mm", "pocket_wall_thickness_mm",
                    "layout_impact_3x3", "visual_implications",
                    "moulding_implications", "authority", "confidence")
        for row in self.matrix["strategies"]:
            for key in required:
                self.assertIn(key, row, row["strategy"])

    def test_no_strategy_moves_the_3x3_layout(self):
        for row in self.matrix["strategies"]:
            self.assertFalse(row["layout_impact_3x3"]["pitch_changed"])
            self.assertAlmostEqual(row["layout_impact_3x3"]["pitch_mm"],
                                   30.6, places=9)

    def test_datum_error_is_demonstrated_not_asserted(self):
        dem = self.matrix["datum_error_demonstrated"]
        self.assertTrue(dem["sharp_pan_clears_at_corrected_datum"])
        self.assertFalse(dem["sharp_pan_meets_engineering_minimum"])
        self.assertLess(dem["m4b_a_reproduction_governing_clearance_mm"], 0)

    def test_selected_strategy_provenance(self):
        sel = self.selection
        self.assertTrue(sel["selected"].startswith("C_"))
        self.assertEqual(sel["base_corner_radius_mm"],
                         min(pp.TESTED_BASE_RADII_MM))
        self.assertEqual(sel["PAN_EDGE_PROFILE_AUTHORITY"],
                         "PROVISIONAL_DESIGN_DEFAULT")
        self.assertEqual(sel["PAN_MANUFACTURING_AUTHORITY"],
                         "NOT_ESTABLISHED")
        self.assertIn("smallest", sel["rule"])
        for cond in sel["conditions"]:
            self.assertIn("checks", cond)

    def test_no_automatic_mutation(self):
        """Contracts are not rewritten by evaluating strategies."""
        before = (dict(A2.BASE), dict(A2.PAN), pp.contract_values())
        A2.resolution_matrix()
        self.assertEqual(before[0], dict(A2.BASE))
        self.assertEqual(before[1], dict(A2.PAN))
        self.assertEqual(before[2], pp.contract_values())
        self.assertEqual(A2.FUNCTIONAL_DIAMETER_MM, 26.8)

    def _row(self, name):
        return next(r for r in self.matrix["strategies"]
                    if r["strategy"] == name)


class DeckAndThicknessTests(_Base):
    def test_deck_ligament_validation(self):
        lig = pdat.deck_ligament_mm(self.tray)
        self.assertGreater(lig, 0.0)
        # both helpers round to 6 dp, so compare at the precision they
        # actually publish rather than at float precision
        self.assertAlmostEqual(pdat.pocket_wall_thickness_mm(self.tray),
                               lig / 2.0, places=6)
        self.assertAlmostEqual(self.chosen["deck_ligament_mm"], lig,
                               places=9)

    def test_thickness_map_determinism(self):
        a = ta.analyse(self.tray)
        b = ta.analyse(build_recessed_palette_tray(self.assembly["spec"]))
        self.assertEqual(a["regions"], b["regions"])
        self.assertEqual(a["thickness_ratio"], b["thickness_ratio"])

    def test_thickness_ratio_threshold(self):
        rep = ta.analyse(self.tray)
        self.assertGreater(rep["thickness_ratio"], 0.0)
        codes = [f["code"] for f in rep["findings"]]
        if rep["thickness_ratio"] > rep["ratio_limit"]:
            self.assertIn(ta.THICKNESS_RATIO_EXCEEDED, codes)
            self.assertFalse(rep["within_limit"])
        else:
            self.assertNotIn(ta.THICKNESS_RATIO_EXCEEDED, codes)

    def test_ratio_excludes_unmodelled_context_sections(self):
        rep = ta.analyse(self.tray)
        for name in rep["context_sections_excluded_from_ratio"]:
            self.assertIn(rep["regions"][name]["kind"],
                          ("TRANSITION", "INTERFACE"))

    def test_sink_risk_classification(self):
        rep = ta.analyse(self.tray)
        self.assertEqual(rep[ta.MOULDING_SINK_RISK],
                         "PROVISIONAL_ENGINEERING_RISK")
        self.assertEqual(rep["evidence_basis"],
                         "SECTION_THICKNESS_ONLY_NO_MOULD_FLOW_SIMULATION")
        self.assertIn("no mould-flow simulation was run",
                      rep["claim_limit"].lower())
        self.assertTrue(rep["mitigation_options_not_applied"])

    def test_tolerance_stack_is_declared(self):
        stack = cp.tolerance_stack()
        self.assertEqual(len(stack["contributors"]), 6)
        for row in stack["contributors"].values():
            self.assertIn("basis", row)
            self.assertEqual(row["authority"],
                             "DESIGN_DEFAULT_NOT_MANUFACTURER_CONFIRMED")
        self.assertLess(stack["root_sum_square_mm"], stack["worst_case_mm"])
        self.assertEqual(stack["engineering_minimum_radial_mm"],
                         stack["root_sum_square_mm"])


class DeterminismTests(_Base):
    def test_deterministic_mesh_and_section_identities(self):
        again = A2.build_selected(self.selection)
        self.assertEqual(again["tray"]["mesh_identity"],
                         self.tray["mesh_identity"])
        for name, comp in again["components"].items():
            if "mesh_identity" in comp:
                self.assertEqual(
                    comp["mesh_identity"],
                    self.assembly["components"][name]["mesh_identity"])
        s1 = A2.centre_section(self.assembly)
        s2 = A2.centre_section(again)
        self.assertEqual(s1["section_identity"], s2["section_identity"])
        self.assertEqual(s1["open_loop_count"], 0)

    def test_section_is_closed_and_boolean_free(self):
        sec = A2.centre_section(self.assembly)
        self.assertEqual(sec["open_loop_count"], 0)
        self.assertTrue(sec["boolean_free"])
        self.assertGreater(sec["loop_count"], 0)

    def test_authority_states_are_kept(self):
        contract = A2.contract(self.selection, self.matrix)
        auth = contract["authority"]
        self.assertEqual(auth["PALT_P1_FINAL_DIMENSIONS"], "NOT_APPROVED")
        self.assertEqual(auth["PALT_P1_MANUFACTURING_AUTHORITY"],
                         "NOT_ESTABLISHED")
        self.assertEqual(auth["PALT_P1_OWNER_APPROVAL"],
                         "REJECTED_PENDING_M4B")
        self.assertEqual(auth["PALT_M5"], "BLOCKED")

    def test_clearance_measurement_is_symmetric_in_metrics(self):
        """Governing clearance is the minimum of the two metrics."""
        for row in self.matrix["strategies"] + self.matrix["controls"]:
            self.assertAlmostEqual(
                row["governing_clearance_mm"],
                min(row["min_radial_clearance_mm"],
                    row["min_normal_clearance_mm"]), places=9)

    def test_engineering_minimum_is_finite_and_positive(self):
        m = cp.engineering_minimum_mm()
        self.assertTrue(math.isfinite(m))
        self.assertGreater(m, 0.0)
