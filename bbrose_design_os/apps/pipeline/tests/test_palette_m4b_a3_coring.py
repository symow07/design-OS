"""PALT-M4B-A3 — cored tray, thickness field and preservation tests.

A3 did NOT meet its exit criteria: the sampled minimum wall is below
policy and its location is unidentified. These tests pin what IS
established — the coring geometry, the preserved A2 decisions, the
fail-closed rib constraint — and pin the FAILURE too, so it cannot be
quietly lost.
"""
import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_clearance_policy as cp
from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palette_pan_profile as pp
from apps.pipeline.services import palette_pocket_datums as pdat
from apps.pipeline.services import palette_thickness_field as tfield
from apps.pipeline.services import palt_m4b_a2 as A2
from apps.pipeline.services import palt_m4b_a3 as A3
from apps.pipeline.services.palette_cored_tray_geometry import (
    CORE_STRATEGIES, DEFAULT_CORE, EXPECTED_EULER, RIB_POLICY,
    CoredTrayError, build_cored_palette_tray)

SAMPLING = {"planes_per_family": 7}


def _tray(strategy="C_POCKET_FOLLOWING_CORE", **over):
    core = dict(DEFAULT_CORE)
    core.update(CORE_STRATEGIES[strategy])
    core.update(over)
    core["strategy"] = strategy
    return build_cored_palette_tray(A3.tray_spec(), core)


class CoredGeometryTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()
        cls.uniform = _tray("A_UNIFORM_UNDERSIDE_CORE")

    def test_every_coring_strategy_is_evaluated(self):
        self.assertEqual(set(CORE_STRATEGIES),
                         {"A_UNIFORM_UNDERSIDE_CORE",
                          "B_CELLULAR_UNDERSIDE_CORE",
                          "C_POCKET_FOLLOWING_CORE", "D_HYBRID_CORE"})

    def test_deterministic_core_identities(self):
        self.assertEqual(_tray()["mesh_identity"], self.tray["mesh_identity"])
        self.assertNotEqual(self.uniform["mesh_identity"],
                            self.tray["mesh_identity"])

    def test_core_config_changes_identity(self):
        self.assertNotEqual(_tray(deck_skin_mm=1.4)["mesh_identity"],
                            self.tray["mesh_identity"])

    def test_manifold_and_watertight(self):
        for tray in (self.tray, self.uniform):
            rep = mv.validate_mesh(tray["name"], tray)
            d = rep["diagnostics"]
            self.assertEqual(d["boundary_edges"], 0)
            self.assertEqual(d["non_manifold_edges"], 0)
            self.assertEqual(d["inconsistent_half_edges"], 0)
            self.assertEqual(d["euler_characteristic"], EXPECTED_EULER)
            self.assertEqual(d["t_junctions"], 0)
            self.assertEqual(d["self_intersecting_pairs"], 0)
            self.assertTrue(rep["valid"], rep["findings"])

    def test_euler_is_asserted_not_relaxed(self):
        """The cored recess is a dent, not a through-hole, so chi stays 2."""
        self.assertEqual(EXPECTED_EULER, 2)

    def test_base_skin_and_pocket_floor_support(self):
        self.assertAlmostEqual(self.tray["pocket_floor_thickness_mm"], 1.0,
                               places=9)
        self.assertAlmostEqual(self.tray["deck_skin_mm"], 1.0, places=9)
        self.assertEqual(len(self.tray["pockets"]), 9)

    def test_no_core_breakthrough(self):
        e = self.tray["elevations_mm"]
        self.assertLess(e["underside"], e["pocket_floor"])
        self.assertLess(e["pocket_floor"], e["core_ceiling"])
        self.assertLess(e["core_ceiling"], e["deck"])
        self.assertGreater(self.tray["pocket_floor_thickness_mm"], 0.0)

    def test_sealed_void_is_not_permitted(self):
        self.assertFalse(
            self.tray["core_topology"]["sealed_void_permitted"])

    def test_thick_floor_is_removed(self):
        v, f = self.tray["vertices"], self.tray["faces"]
        a = v[f[:, 0]]
        cored = float(np.einsum("ij,ij->i", a,
                                np.cross(v[f[:, 1]] - a,
                                         v[f[:, 2]] - a)).sum() / 6.0)
        from apps.pipeline.services.palette_recessed_tray_geometry import (
            build_recessed_palette_tray)
        solid = build_recessed_palette_tray(A3.tray_spec())
        v2, f2 = solid["vertices"], solid["faces"]
        a2 = v2[f2[:, 0]]
        full = float(np.einsum("ij,ij->i", a2,
                               np.cross(v2[f2[:, 1]] - a2,
                                        v2[f2[:, 2]] - a2)).sum() / 6.0)
        self.assertLess(cored, full * 0.55)

    # --- ribs -----------------------------------------------------------
    def test_cell_grid_ribs_fail_closed(self):
        for strategy in ("B_CELLULAR_UNDERSIDE_CORE", "D_HYBRID_CORE"):
            with self.subTest(strategy):
                with self.assertRaises(CoredTrayError) as ctx:
                    _tray(strategy)
                self.assertIn("rib", str(ctx.exception))

    def test_rib_policy_is_declared(self):
        for key in ("rib_thickness_mm", "rib_height_mm", "rib_draft_deg",
                    "rib_root_radius_mm", "rib_spacing_mm",
                    "rib_termination", "pocket_support_relationship",
                    "outer_wall_relationship",
                    "hinge_interface_placeholder",
                    "clasp_interface_placeholder"):
                self.assertIn(key, RIB_POLICY)
        self.assertEqual(RIB_POLICY["manufacturing_authority"],
                         "NOT_MANUFACTURER_CONFIRMED")
        self.assertIn("NOT_DEMONSTRATED",
                      RIB_POLICY["structural_sufficiency"])

    def test_rib_thickness_not_above_nominal_wall(self):
        self.assertLessEqual(RIB_POLICY["rib_thickness_mm"],
                             A3.THICKNESS_POLICY[
                                 "TARGET_NOMINAL_WALL_THICKNESS"]["mm"])


class PreservedA2DecisionsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()
        cls.assembly = A3.build_selected(
            {"selected": "C_POCKET_FOLLOWING_CORE"})
        cls.clearance = A3.clearance_recheck(cls.assembly)

    def test_fit_datum_is_unchanged(self):
        self.assertAlmostEqual(self.clearance["fit_datum_unchanged_mm"],
                               A2.FUNCTIONAL_DIAMETER_MM, places=6)

    def test_pan_base_radius_preserved(self):
        self.assertEqual(A3.SELECTED_PAN_BASE_RADIUS_MM, 0.30)
        self.assertEqual(pp.PAN_EDGE_PROFILE_AUTHORITY,
                         "PROVISIONAL_DESIGN_DEFAULT")
        self.assertEqual(pp.PAN_MANUFACTURING_AUTHORITY, "NOT_ESTABLISHED")

    def test_pan_clearance_is_bit_identical_to_a2(self):
        """Coring and the rim-fillet change must not touch the fit."""
        self.assertEqual(self.clearance["PAN_POCKET_INTERSECTION_COUNT"], 0)
        self.assertEqual(self.clearance["GEOMETRIC_CLEARANCE"], "PASS")
        self.assertEqual(self.clearance["ENGINEERING_CLEARANCE_RSS"], "PASS")
        self.assertAlmostEqual(
            self.clearance["measurement"]["governing_clearance_mm"],
            0.249767, places=6)

    def test_manufacturing_clearance_never_established(self):
        self.assertEqual(
            self.clearance["MANUFACTURING_CONFIRMED_CLEARANCE"],
            "NOT_ESTABLISHED")
        self.assertFalse(self.clearance["tiers"]["production_ready"])

    def test_pan_recess_and_powder_clearance_preserved(self):
        self.assertAlmostEqual(self.clearance["pan_recess_mm"], 1.0,
                               places=9)
        self.assertAlmostEqual(self.clearance["adhesive_gap_mm"], 0.15,
                               places=6)
        self.assertGreaterEqual(
            self.clearance["powder_to_lid_clearance_mm"],
            A2.PAN["powder_to_lid_clearance_mm"])

    def test_no_breakthrough(self):
        self.assertFalse(self.clearance["pocket_floor_breakthrough"])
        self.assertFalse(self.clearance["outer_wall_breakthrough"])

    def test_layout_and_envelope_untouched(self):
        spec = A3.tray_spec()
        self.assertEqual(spec["pitch_mm"], 30.6)
        self.assertEqual(spec["tray_width_mm"], 112.0)
        self.assertEqual(spec["tray_depth_mm"], 112.0)
        self.assertEqual(len(self.tray["pockets"]), 9)

    def test_pocket_datum_semantics_preserved(self):
        d = pdat.pocket_datums(self.tray, A2.PAN)
        self.assertTrue(pdat.validate_datums(d, A2.PAN)["valid"])
        self.assertFalse(
            d["datums"]["POCKET_VISIBLE_MOUTH_DIAMETER_AT_RIM"][
                "controls_fit"])

    def test_ambiguous_field_still_fails_closed(self):
        spec = A3.tray_spec()
        spec["pocket_diameter_mm"] = 26.6
        with self.assertRaises(CoredTrayError):
            build_cored_palette_tray(spec, dict(DEFAULT_CORE))


class LigamentAndWallTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()

    def test_minimum_deck_ligament_passes_policy(self):
        lig = cls_lig = self.tray["deck_ligament_mm"]
        self.assertGreaterEqual(
            lig, A3.THICKNESS_POLICY["MINIMUM_DECK_LIGAMENT"]["mm"])
        self.assertGreater(cls_lig, 1.933)     # the A2 value it replaces

    def test_pocket_wall_passes_on_the_A2_METRIC_unchanged(self):
        """A2 failed on ligament/2 = 0.966. A3 is measured the SAME way."""
        wall = self.tray["pocket_wall_at_mouth_mm"]
        self.assertAlmostEqual(wall, self.tray["deck_ligament_mm"] / 2.0,
                               places=6)
        self.assertGreaterEqual(
            wall,
            A3.THICKNESS_POLICY["MINIMUM_LOCAL_WALL_THICKNESS"]["mm"])
        self.assertGreater(wall, 0.966)

    def test_material_section_is_a_separate_declared_observation(self):
        self.assertAlmostEqual(
            self.tray["inter_pocket_material_section_mm"],
            self.tray["deck_ligament_mm"], places=9)
        self.assertNotEqual(self.tray["inter_pocket_material_section_mm"],
                            self.tray["pocket_wall_at_mouth_mm"])

    def test_rim_fillet_change_is_fit_neutral(self):
        a2_rings = _tray(rim_fillet_mm=0.6)["pocket_profile_rings"]
        a3_rings = self.tray["pocket_profile_rings"]
        for rings in (a2_rings, a3_rings):
            self.assertAlmostEqual(
                2 * pdat.profile_radius(rings, A2.PAN["pan_seating_z_mm"]),
                A2.FUNCTIONAL_DIAMETER_MM, places=6)


class ThicknessFieldTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()
        cls.field = tfield.sample({"tray": cls.tray}, width=112.0,
                                  depth=112.0, sampling=SAMPLING)

    def test_thickness_field_determinism(self):
        again = tfield.sample({"tray": self.tray}, width=112.0, depth=112.0,
                              sampling=SAMPLING)
        self.assertEqual(again["minimum_thickness_mm"],
                         self.field["minimum_thickness_mm"])
        self.assertEqual(again["histogram"], self.field["histogram"])
        self.assertEqual(again["percentiles_mm"],
                         self.field["percentiles_mm"])

    def test_sampling_method_is_versioned(self):
        s = self.field["sampling"]
        self.assertIn("version", s)
        self.assertIn("raster_pitch_mm", s)
        self.assertEqual(s["measure"],
                         "MEDIAL_RIDGE_OF_THE_RASTERISED_DISTANCE_FIELD")

    def test_gradient_and_histogram_present(self):
        self.assertGreater(self.field["gradient_count"], 0)
        self.assertEqual(len(self.field["histogram"]["counts"]), 24)
        for p in ("p1", "p5", "p50", "p95", "p99"):
            self.assertIn(p, self.field["percentiles_mm"])

    def test_field_reproduces_the_known_skin_thickness(self):
        """A 1.0 mm skin must read 1.0 after the half-pixel correction."""
        self.assertAlmostEqual(self.field["percentiles_mm"]["p50"], 1.0,
                               places=2)

    def test_sink_risk_is_a_classification_not_a_fact(self):
        risk = tfield.risk_classification(self.field, A3.THICKNESS_POLICY)
        self.assertEqual(risk["MOULDING_SINK_RISK"],
                         "PROVISIONAL_ENGINEERING_RISK")
        self.assertIn("no mould-flow simulation",
                      risk["claim_limit"].lower())


class HonestFailureTests(SimpleTestCase):
    """A3 did not pass. These pin the failure so it cannot be lost."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.matrix = A3.strategy_matrix(sampling=SAMPLING)
        cls.selection = A3.select_core(cls.matrix)

    def test_selection_is_not_marked_as_passing(self):
        self.assertFalse(self.selection["policy_satisfied"])
        self.assertEqual(
            self.selection["status"],
            "BEST_CONSTRUCTIBLE_CANDIDATE_NOT_A_PASSING_SELECTION")
        self.assertTrue(self.selection["unmet_policies"])

    def test_minimum_wall_failure_is_recorded(self):
        self.assertIn("min_wall_at_or_above_policy",
                      self.selection["unmet_policies"])

    def test_policy_was_not_weakened_to_pass(self):
        self.assertEqual(
            A3.THICKNESS_POLICY["MAXIMUM_THICKNESS_RATIO"]["mm"], 2.5)
        self.assertEqual(
            A3.THICKNESS_POLICY["MINIMUM_LOCAL_WALL_THICKNESS"]["mm"], 1.0)
        self.assertIn("DELIBERATELY UNCHANGED",
                      A3.THICKNESS_POLICY["MAXIMUM_THICKNESS_RATIO"][
                          "provenance"])

    def test_uncored_baseline_is_worse(self):
        base = self.matrix["uncored_baseline"]
        best = min(r["thickness_ratio"] for r in self.matrix["strategies"]
                   if r.get("constructible"))
        self.assertLess(best, base["thickness_ratio"])

    def test_every_policy_value_carries_provenance(self):
        for key, row in A3.THICKNESS_POLICY.items():
            if not isinstance(row, dict):
                continue
            for field in ("provenance", "authority", "confidence",
                          "supplier_confirmed"):
                self.assertIn(field, row, key)
            self.assertFalse(row["supplier_confirmed"], key)

    def test_authority_states_are_kept(self):
        auth = A3.contract(self.selection, self.matrix,
                           {"x": 1})["authority"]
        self.assertEqual(auth["PALT_P1_OWNER_APPROVAL"],
                         "REJECTED_PENDING_M4B")
        self.assertEqual(auth["PALT_M4B_B"], "BLOCKED")
        self.assertEqual(auth["PALT_M5"], "BLOCKED")

    def test_clearance_tiers_unchanged_from_a2(self):
        self.assertEqual(cp.CLEARANCE_TIER_STATUS[cp.MANUFACTURING],
                         "NOT_ESTABLISHED")
