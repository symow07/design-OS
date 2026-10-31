"""PALT-M4C §8 — rectangular metal pans for the ES3083 pilot."""
import math

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_moulded_validators as mv
from apps.pipeline.services import palette_pan_profile as round_pan
from apps.pipeline.services import palette_rect_pan as rp


def _vol(mesh):
    v, f = mesh["vertices"], mesh["faces"]
    a = v[f[:, 0]]
    return float(np.einsum("ij,ij->i", a,
                           np.cross(v[f[:, 1]] - a,
                                    v[f[:, 2]] - a)).sum() / 6.0)


class RectPanGeometryTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pan = rp.build_rect_pan("pan", z0=2.65)

    def test_it_is_manifold_and_watertight(self):
        rep = mv.validate_mesh("rect", self.pan,
                               check_self_intersection=False)
        d = rep["diagnostics"]
        self.assertEqual(d["boundary_edges"], 0)
        self.assertEqual(d["non_manifold_edges"], 0)
        self.assertEqual(d["inconsistent_half_edges"], 0)
        self.assertEqual(d["euler_characteristic"], 2)
        self.assertTrue(rep["valid"], rep["findings"])

    def test_it_declares_itself_rectangular(self):
        self.assertEqual(self.pan["pan_shape"], "RECTANGULAR")

    def test_the_corner_is_a_true_radius_not_a_bounding_box(self):
        w, d, r = 24.0, 18.0, 2.0
        hw, hd = w / 2 - r, d / 2 - r
        loop = rp.rounded_rect_loop(w, d, r)
        errs = [abs(math.hypot(abs(x) - hw, abs(y) - hd) - r)
                for x, y, _, _ in loop
                if abs(x) > hw + 1e-9 and abs(y) > hd + 1e-9]
        self.assertTrue(errs)
        self.assertLess(max(errs), 1e-9)

    def test_the_wall_offset_is_a_true_parallel_offset(self):
        """The A3R defect was a centre-radial offset; every point must move
        exactly the wall distance along its OWN normal."""
        loop = rp.rounded_rect_loop(24.0, 18.0, 2.0)
        off = rp._offset_loop(loop, 0.25)
        d = [math.hypot(a[0] - b[0], a[1] - b[1])
             for a, b in zip(loop, off)]
        self.assertAlmostEqual(min(d), 0.25, places=9)
        self.assertAlmostEqual(max(d), 0.25, places=9)

    def test_volume_agrees_with_the_analytic_shell(self):
        c = rp.contract_values()
        def area(W, H, R):
            return W * H - (4 - math.pi) * R * R
        analytic = (area(c["pan_width_mm"], c["pan_height_mm"],
                         c["corner_radius_mm"]) * c["pan_depth_mm"]
                    - area(c["pan_width_mm"] - 2 * c["metal_wall_thickness_mm"],
                           c["pan_height_mm"] - 2 * c["metal_wall_thickness_mm"],
                           c["corner_radius_mm"] - c["metal_wall_thickness_mm"])
                    * (c["pan_depth_mm"] - c["metal_floor_thickness_mm"]))
        sharp = rp.build_rect_pan("p", z0=0.0, base_corner_radius_mm=0.0)
        # within the 8-segment corner-arc discretisation
        self.assertAlmostEqual(_vol(sharp), analytic, delta=analytic * 0.02)

    def test_a_larger_base_radius_removes_material(self):
        vols = [_vol(rp.build_rect_pan("p", base_corner_radius_mm=b))
                for b in (0.0, 0.30, 0.50)]
        self.assertEqual(vols, sorted(vols, reverse=True))

    def test_it_is_deterministic(self):
        self.assertEqual(rp.build_rect_pan("pan", z0=2.65)["mesh_identity"],
                         self.pan["mesh_identity"])

    def test_config_changes_the_identity(self):
        other = rp.build_rect_pan("pan", z0=2.65, pan_width_mm=26.0)
        self.assertNotEqual(other["mesh_identity"],
                            self.pan["mesh_identity"])

    def test_it_fails_closed_on_impossible_input(self):
        for bad in ({"corner_radius_mm": 20.0},
                    {"metal_wall_thickness_mm": 15.0},
                    {"metal_floor_thickness_mm": 9.0},
                    {"base_corner_radius_mm": 9.0}):
            with self.subTest(**bad):
                with self.assertRaises(rp.RectPanError):
                    rp.build_rect_pan("p", **bad)

    def test_every_contract_field_the_owner_listed_exists(self):
        for key in ("pan_width_mm", "pan_height_mm", "corner_radius_mm",
                    "side_wall_draft_deg", "base_corner_radius_mm",
                    "metal_wall_thickness_mm", "metal_floor_thickness_mm",
                    "pocket_tolerance_mm", "pocket_draft_deg",
                    "adhesive_allowance_mm", "powder_crown_mm"):
            self.assertIn(key, rp.RECT_PAN_CONTRACT, key)

    def test_authority_is_provisional(self):
        self.assertEqual(self.pan["pan_edge_profile_authority"],
                         "PROVISIONAL_DESIGN_DEFAULT")
        self.assertEqual(self.pan["pan_manufacturing_authority"],
                         "NOT_ESTABLISHED")


class RectPocketEnvelopeTests(SimpleTestCase):
    """The envelope reports a NAMED datum. Whether the built tray actually
    clears the pan is proved against built geometry in
    test_palette_rect_tray.PanPocketDatumTests, not here — comparing the
    envelope to its own inputs would prove nothing about the tray."""

    def test_it_names_the_datum_it_reports(self):
        self.assertEqual(rp.pocket_envelope()["datum"],
                         "FUNCTIONAL_CLEARANCE_AT_SEATING_DATUM")

    def test_the_clearance_is_applied_on_both_axes(self):
        c = rp.contract_values()
        p = rp.pocket_envelope()
        tol = c["pocket_tolerance_mm"]
        self.assertAlmostEqual(p["functional_width_at_seating_datum_mm"],
                               c["pan_width_mm"] + 2 * tol, places=6)
        self.assertAlmostEqual(p["functional_height_at_seating_datum_mm"],
                               c["pan_height_mm"] + 2 * tol, places=6)

    def test_the_corner_radius_grows_with_the_offset(self):
        """A fixed corner radius would make the clearance a scaled loop,
        not a true offset, and pinch the pan corners."""
        c = rp.contract_values()
        p = rp.pocket_envelope()
        self.assertAlmostEqual(
            p["functional_corner_radius_at_seating_datum_mm"],
            c["corner_radius_mm"] + c["pocket_tolerance_mm"], places=6)


class RoundPanRegressionTests(SimpleTestCase):
    """PALT-P1A must be untouched by the PALT-P1B rectangular work."""

    def test_the_round_pan_still_builds_and_is_unchanged(self):
        pan = round_pan.build_metal_pan("p", z0=2.65,
                                        base_corner_radius_mm=0.30)
        rep = mv.validate_mesh("round", pan,
                               check_self_intersection=False)
        self.assertTrue(rep["valid"])
        self.assertAlmostEqual(pan["flat_base_radius_mm"], 12.7, places=9)

    def test_the_two_families_are_distinct_implementations(self):
        self.assertNotEqual(rp.SCHEMA, round_pan.SCHEMA)
        self.assertEqual(rp.SCHEMA, "metal_pan_rectangular/1.0")
