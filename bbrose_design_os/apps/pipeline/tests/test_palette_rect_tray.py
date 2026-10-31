"""PALT-M4C §8 — recessed rectangular pockets (ES3083 / PALT-P1B)."""
import math

from django.test import SimpleTestCase

from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palt_m4b_a as A
from apps.pipeline.services import palette_recessed_tray_geometry as round_tray
from apps.pipeline.services import palette_rect_pan as rect_pan
from apps.pipeline.services import palette_rect_tray_geometry as rt


class RectTrayGeometryTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = rt.build_rect_recessed_tray()

    def test_it_is_manifold_watertight_and_non_self_intersecting(self):
        rep = mv.validate_mesh("rect_tray", self.tray,
                               check_self_intersection=True)
        d = rep["diagnostics"]
        self.assertEqual(d["boundary_edges"], 0)
        self.assertEqual(d["non_manifold_edges"], 0)
        self.assertEqual(d["inconsistent_half_edges"], 0)
        self.assertEqual(d["t_junctions"], 0)
        self.assertEqual(d["self_intersecting_pairs"], 0)
        self.assertEqual(d["connected_components"], 1)
        self.assertTrue(rep["valid"], rep["findings"])

    def test_a_cored_recess_is_a_dent_not_a_hole(self):
        self.assertEqual(
            mv.validate_mesh("rect_tray", self.tray,
                             check_self_intersection=False)
            ["diagnostics"]["euler_characteristic"], 2)

    def test_no_tolerance_welding_was_used(self):
        self.assertEqual(self.tray["weld_count"], 0)
        self.assertIsNone(rt.TOPOLOGY["join_tolerance"])
        self.assertGreater(self.tray["shared_vertex_reuse_count"], 0)

    def test_the_pockets_are_rectangular_and_match_the_grid(self):
        self.assertEqual(self.tray["pocket_shape"], "RECTANGULAR")
        g = self.tray["grid"]
        self.assertEqual(self.tray["pocket_count"], g["rows"] * g["columns"])
        self.assertEqual((g["columns"], g["rows"]), (4, 3))

    def test_the_pocket_wall_is_a_true_normal_offset(self):
        """A scaled loop would deliver the offset on the straight walls and
        less in the corners — the PALT-M4B-A3R defect."""
        c = rt.RECT_TRAY_DEFAULTS
        pr = c["pocket_sharp_wall_corner_radius_at_deck_mm"]
        rim = rt.rect_pocket_loop(
            0.0, 0.0, c["pocket_sharp_wall_width_at_deck_mm"],
            c["pocket_sharp_wall_height_at_deck_mm"], pr, rt.POCKET_SEGMENTS)
        for inward in (0.10, 0.25, 0.80):
            deeper = rt.offset_pocket_loop(rim, inward, corner_radius=pr)
            dists = [math.hypot(a[0] - b[0], a[1] - b[1])
                     for a, b in zip(rim, deeper)]
            with self.subTest(inward=inward):
                self.assertAlmostEqual(min(dists), inward, places=9)
                self.assertAlmostEqual(max(dists), inward, places=9)

    def test_the_pocket_corners_stay_true_arcs_at_every_depth(self):
        c = rt.RECT_TRAY_DEFAULTS
        pw = c["pocket_sharp_wall_width_at_deck_mm"]
        ph = c["pocket_sharp_wall_height_at_deck_mm"]
        pr = c["pocket_sharp_wall_corner_radius_at_deck_mm"]
        for inward in (0.0, 0.5, 1.0):
            w, h, r = pw - 2 * inward, ph - 2 * inward, pr - inward
            hw, hd = w / 2 - r, h / 2 - r
            rim = rt.rect_pocket_loop(0.0, 0.0, pw, ph, pr,
                                      rt.POCKET_SEGMENTS)
            loop = rt.offset_pocket_loop(rim, inward, corner_radius=pr)
            errs = [abs(math.hypot(abs(x) - hw, abs(y) - hd) - r)
                    for x, y in loop
                    if abs(x) > hw + 1e-9 and abs(y) > hd + 1e-9]
            with self.subTest(inward=inward):
                self.assertTrue(errs)
                self.assertLess(max(errs), 1e-9)

    def test_the_draft_opens_upward_so_the_tool_releases(self):
        p = self.tray["pockets"][0]
        self.assertGreater(p["opening_width_mm"], p["floor_width_mm"])
        self.assertGreater(p["opening_height_mm"], p["floor_height_mm"])
        self.assertEqual(self.tray["draft"]["release_direction"], "UPWARD")

    def test_the_measured_wall_draft_matches_the_contract(self):
        rings = self.tray["pocket_profile_rings"]
        wall = [(r, z) for r, z in rings
                if self.tray["pockets"][0]["wall_bottom_z_mm"] - 1e-9
                <= z <= self.tray["pockets"][0]["wall_top_z_mm"] + 1e-9]
        (r0, z0), (r1, z1) = wall[0], wall[-1]
        self.assertAlmostEqual(
            math.degrees(math.atan2(r0 - r1, z0 - z1)),
            rt.RECT_TRAY_DEFAULTS["pocket_draft_deg"], places=6)

    def test_it_is_deterministic(self):
        self.assertEqual(rt.build_rect_recessed_tray()["mesh_identity"],
                         self.tray["mesh_identity"])

    def test_it_fails_closed_rather_than_approximating(self):
        for bad, frag in (
            ({"pocket_sharp_wall_corner_radius_at_deck_mm": 0.20},
             "pocket profile is not constructible"),
            ({"pocket_sharp_wall_width_at_deck_mm": 40.0}, "pitch"),
            ({"cells_x": 0}, "at least one cell"),
            ({"pitch_x_mm": 40.0}, "does not fit the tray"),
            ({"pocket_floor_z_mm": 5.0}, "elevations"),
            ({"tray_draft_deg": 60.0}, "collapses"),
        ):
            with self.subTest(**bad):
                with self.assertRaises(rt.RectTrayError) as ctx:
                    rt.build_rect_recessed_tray(bad)
                self.assertIn(frag, str(ctx.exception))

    def test_an_unknown_spec_key_is_refused(self):
        with self.assertRaises(rt.RectTrayError):
            rt.build_rect_recessed_tray({"pan_width_mm": 24.0})

    def test_a_bare_pocket_dimension_is_refused_as_ambiguous(self):
        """26.6 vs 26.8 was a datum conflict, not a value conflict. The
        rectangular family must not reopen it."""
        for key in ("pocket_width_mm", "pocket_height_mm",
                    "pocket_corner_radius_mm", "pocket_diameter_mm"):
            with self.subTest(key=key):
                with self.assertRaises(rt.RectTrayError) as ctx:
                    rt.build_rect_recessed_tray({key: 24.8})
                self.assertIn("does not name a datum", str(ctx.exception))

    def test_the_grid_is_parametric_not_a_hardened_soft_reading(self):
        a = self.tray["grid"]
        self.assertEqual(a["constraint_level"], "SOFT_VISUAL_CONSTRAINT")
        self.assertEqual(a["confidence"], 0.55)
        self.assertEqual(a["confirmation_state"],
                         "PENDING_OWNER_CONFIRMATION")
        other = rt.build_rect_recessed_tray(
            {"cells_x": 5, "cells_y": 2, "tray_width_mm": 142.0,
             "tray_depth_mm": 50.0})
        self.assertEqual(other["pocket_count"], 10)
        self.assertNotEqual(other["mesh_identity"],
                            self.tray["mesh_identity"])

    def test_no_dimension_here_claims_authority(self):
        # F1 2026-08-14 (f1_pan_redimension_ingestion.json): the owner
        # ADOPTED the calipered cavity/pitch, so the source claim moved
        # from provisional to MEASURED-adopted. The rest of the authority
        # posture is pinned unchanged: final dimensions remain
        # NOT_APPROVED and manufacturing remains NOT_ESTABLISHED.
        a = self.tray["dimensional_authority"]
        self.assertEqual(a["source"],
                         "MEASURED_CALIPER_OWNER_ADOPTED_F1_2026_08_14")
        self.assertEqual(a["final_dimensions"], "NOT_APPROVED")
        self.assertEqual(a["manufacturing_authority"], "NOT_ESTABLISHED")
        self.assertEqual(a["owner_approval"], "NOT_GRANTED")

    def test_no_boolean_and_blender_stays_a_renderer(self):
        self.assertTrue(self.tray["boolean_free"])
        self.assertEqual(self.tray["authority"],
                         "DETERMINISTIC_PYTHON_MESH_CONSTRUCTION")
        self.assertEqual(self.tray["blender_role"],
                         "VISUALIZATION_AND_RENDERING_ONLY")


class PanPocketDatumTests(SimpleTestCase):
    """The pan and the pocket must be linked by a solver, not by two
    hand-copied constants that can silently desynchronise."""

    def test_the_envelope_names_its_datum(self):
        env = rect_pan.pocket_envelope()
        self.assertEqual(env["datum"],
                         "FUNCTIONAL_CLEARANCE_AT_SEATING_DATUM")
        for key in ("functional_width_at_seating_datum_mm",
                    "functional_height_at_seating_datum_mm",
                    "functional_corner_radius_at_seating_datum_mm"):
            self.assertIn(key, env)

    def test_the_deck_input_is_wider_than_the_functional_section(self):
        """A drafted pocket narrows downward, so feeding the functional
        numbers straight in as deck-plane input would tighten the fit."""
        sol = rt.POCKET_DATUM_SOLUTION
        env = rect_pan.pocket_envelope()
        self.assertLess(sol["profile_offset_at_seating_datum_mm"], 0.0)
        self.assertGreater(sol["pocket_sharp_wall_width_at_deck_mm"],
                           env["functional_width_at_seating_datum_mm"])
        self.assertGreater(sol["pocket_sharp_wall_height_at_deck_mm"],
                           env["functional_height_at_seating_datum_mm"])

    def test_the_defaults_are_derived_from_the_pan_contract(self):
        for key in ("pocket_sharp_wall_width_at_deck_mm",
                    "pocket_sharp_wall_height_at_deck_mm",
                    "pocket_sharp_wall_corner_radius_at_deck_mm"):
            self.assertAlmostEqual(rt.RECT_TRAY_DEFAULTS[key],
                                   rt.POCKET_DATUM_SOLUTION[key], places=9)

    def test_the_BUILT_pocket_clears_the_pan_at_the_seating_datum(self):
        """Measured from the tray that exists, not from the numbers that
        were requested — comparing the envelope to itself proves nothing."""
        tray = rt.build_rect_recessed_tray()
        sec = rt.functional_section(
            tray, rt.POCKET_DATUM_SOLUTION["seating_datum_z_mm"])
        c = rect_pan.contract_values()
        tol = c["pocket_tolerance_mm"]
        self.assertAlmostEqual((sec["width_mm"] - c["pan_width_mm"]) / 2,
                               tol, places=6)
        self.assertAlmostEqual((sec["height_mm"] - c["pan_height_mm"]) / 2,
                               tol, places=6)
        self.assertAlmostEqual(sec["corner_radius_mm"],
                               c["corner_radius_mm"] + tol, places=6)

    def test_a_wider_pan_tolerance_widens_the_built_pocket(self):
        """The linkage is live, not a snapshot."""
        d = rt.RECT_TRAY_DEFAULTS
        sol = rt.solve_rect_sharp_wall_for_functional(
            rect_pan.pocket_envelope({"pocket_tolerance_mm": 0.60}),
            deck_z=d["deck_z_mm"], floor_z=d["pocket_floor_z_mm"],
            draft_deg=d["pocket_draft_deg"], rim_fillet=d["rim_fillet_mm"],
            floor_fillet=d["floor_fillet_mm"])
        self.assertGreater(sol["pocket_sharp_wall_width_at_deck_mm"],
                           rt.POCKET_DATUM_SOLUTION[
                               "pocket_sharp_wall_width_at_deck_mm"])

    def test_the_seating_datum_is_the_narrowest_wall_section(self):
        tray = rt.build_rect_recessed_tray()
        z_seat = rt.POCKET_DATUM_SOLUTION["seating_datum_z_mm"]
        higher = rt.functional_section(tray, z_seat + 0.5)
        self.assertGreater(higher["width_mm"],
                           rt.functional_section(tray, z_seat)["width_mm"])


class RoundTrayRegressionTests(SimpleTestCase):
    """PALT-P1A's frozen kernel must not move because P1B was added."""

    FROZEN = "ec65ea9402c16230"        # docs/roadmap/palt_m4b_a/

    def test_the_round_tray_identity_is_unchanged(self):
        tray = round_tray.build_recessed_palette_tray(
            dict(A._values(A.TRAY)))
        self.assertEqual(tray["mesh_identity"], self.FROZEN)
        self.assertEqual(len(tray["pockets"]), 9)

    def test_the_two_families_are_separate_schemas(self):
        self.assertNotEqual(rt.SCHEMA, round_tray.SCHEMA)
        self.assertEqual(rt.SCHEMA, "palette_recessed_tray_rectangular/1.0")
