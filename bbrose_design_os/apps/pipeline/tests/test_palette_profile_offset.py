"""PALT-M4B-A3F — signed normal profile-offset kernel tests."""
import math

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_profile_offset as po
from apps.pipeline.services import palette_thickness_authority as ta
from apps.pipeline.services import palt_m4b_a3 as A3
from apps.pipeline.services.palette_cored_tray_geometry import (
    CORE_STRATEGIES, DEFAULT_CORE, CoredTrayError, build_cored_palette_tray)

A3R_AUTHORITATIVE_MINIMUM = 0.600738
FROZEN_A3_IDENTITY = "26c817b8c113851a"


def _tray(w, mode):
    core = dict(DEFAULT_CORE)
    core.update(CORE_STRATEGIES["C_POCKET_FOLLOWING_CORE"])
    core["cup_offset_mode"] = mode
    core["cup_wall_mm"] = w
    return build_cored_palette_tray(A3.tray_spec(), core)


def _min_wall(tray, lo=2.5, hi=3.2, stride=3):
    v, f = tray["vertices"], tray["faces"]
    cz = v[f].mean(axis=1)[:, 2]
    sel = np.nonzero((cz > lo) & (cz < hi))[0][::stride]
    return ta.normal_ray_thickness(tray, samples_per_face=1,
                                   face_filter=sel)["minimum_mm"]


class PrimitiveOffsetTests(SimpleTestCase):
    def test_vertical_line_offsets_by_exactly_the_distance(self):
        got = po.offset_primitive(po.line(10.0, 5.0, 10.0, 0.0), 1.2)
        self.assertAlmostEqual(got["start"][0], 11.2, places=9)
        self.assertAlmostEqual(got["end"][0], 11.2, places=9)
        self.assertAlmostEqual(got["start"][1], 5.0, places=9)

    def test_drafted_line_offsets_perpendicular_not_radially(self):
        th = math.radians(2.0)
        top, bot = 10.0, 10.0 - 5.0 * math.tan(th)
        got = po.offset_primitive(po.line(top, 5.0, bot, 0.0), 1.0)
        moved = math.hypot(got["start"][0] - top, got["start"][1] - 5.0)
        self.assertAlmostEqual(moved, 1.0, places=9)
        # the point travels 1.0 along the NORMAL, so its radial component
        # is w*cos(draft) < 1.0. A radial offset would have moved exactly
        # 1.0 in r and delivered less than 1.0 of wall — the A3 defect.
        self.assertAlmostEqual(got["start"][0] - top,
                               math.cos(th), places=9)
        self.assertLess(got["start"][0] - top, 1.0)

    def test_convex_arc_offset_adds_to_the_radius(self):
        got = po.offset_primitive(
            po.arc(13.0, 3.1, 0.6, 0, -90, material_toward_centre=False), 1.2)
        self.assertAlmostEqual(got["radius"], 1.8, places=9)
        self.assertEqual(got["centre"], (13.0, 3.1))

    def test_concave_arc_offset_subtracts_and_fails_at_the_radius(self):
        ok = po.offset_primitive(
            po.arc(10.0, 0.0, 1.0, 0, 90, material_toward_centre=True), 0.4)
        self.assertAlmostEqual(ok["radius"], 0.6, places=9)
        for bad in (1.0, 1.5):
            with self.assertRaises(po.ProfileOffsetError) as ctx:
                po.offset_primitive(
                    po.arc(10.0, 0.0, 1.0, 0, 90,
                           material_toward_centre=True), bad)
            self.assertIn(po.OFFSET_SINGULARITY, str(ctx.exception))

    def test_negative_and_zero_distance_rejected(self):
        with self.assertRaises(po.ProfileOffsetError):
            po.offset_primitive(po.line(1, 1, 1, 0), -0.5)
        with self.assertRaises(po.ProfileOffsetError):
            po.offset_meridional_profile_normal([po.line(1, 1, 1, 0)], 0.0)

    def test_unknown_side_rejected(self):
        with self.assertRaises(po.ProfileOffsetError):
            po.offset_primitive(po.line(1, 1, 1, 0), 1.0, side="CAVITY")

    def test_zero_length_segment_rejected(self):
        with self.assertRaises(po.ProfileOffsetError):
            po.offset_primitive(po.line(1, 1, 1, 1), 1.0)

    def test_arc_with_non_positive_radius_rejected(self):
        with self.assertRaises(po.ProfileOffsetError):
            po.arc(1, 1, 0.0, 0, 90, material_toward_centre=False)


class ProfileOffsetTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        spec = A3.tray_spec()
        cls.prims, cls.meta = po.pocket_profile_primitives(
            sharp_r=spec[
                "pocket_sharp_wall_theoretical_diameter_at_deck_mm"] / 2.0,
            deck_z=7.15, floor_z=2.5, draft_deg=2.0, rim_fillet=0.35,
            floor_fillet=0.6, core_top_z=6.15)

    def test_tangency_is_preserved_line_to_arc(self):
        got = po.offset_meridional_profile_normal(self.prims, 1.2)
        self.assertEqual(len(got["primitives"]), 2)
        self.assertGreater(len(got["points"]), 3)

    def test_offset_delivers_constant_true_normal_thickness(self):
        """The A3F fix, measured: every offset point sits exactly the
        target distance from the cavity profile."""
        dense = []
        for p in self.prims:
            dense.extend(po.sample_primitive(p, 400))
        orig = np.asarray(dense)
        for w in (1.0, 1.2, 1.3):
            got = po.offset_meridional_profile_normal(self.prims, w)
            pts = np.asarray(got["points"])
            d = [float(np.hypot(orig[:, 0] - r, orig[:, 1] - z).min())
                 for r, z in pts]
            self.assertAlmostEqual(min(d), w, places=5)
            self.assertAlmostEqual(max(d), w, places=5)

    def test_deterministic_profile_identity(self):
        a = po.offset_meridional_profile_normal(self.prims, 1.2)
        b = po.offset_meridional_profile_normal(self.prims, 1.2)
        self.assertEqual(a["profile_identity"], b["profile_identity"])
        self.assertNotEqual(
            po.offset_meridional_profile_normal(self.prims,
                                                1.1)["profile_identity"],
            a["profile_identity"])

    def test_topology_version_changes_identity(self):
        base = po.offset_meridional_profile_normal(self.prims, 1.2)
        original = po.OFFSET_TOPOLOGY["join_policy"]
        try:
            po.OFFSET_TOPOLOGY["join_policy"] = "SOMETHING_ELSE"
            changed = po.offset_meridional_profile_normal(self.prims, 1.2)
        finally:
            po.OFFSET_TOPOLOGY["join_policy"] = original
        self.assertNotEqual(changed["profile_identity"],
                            base["profile_identity"])

    def test_conventions_are_recorded(self):
        for key in ("profile_orientation", "material_side_convention",
                    "signed_offset_convention", "join_policy",
                    "curvature_policy", "cusp_policy",
                    "self_intersection_policy",
                    "adaptive_chord_tolerance_mm",
                    "coordinate_quantization"):
            self.assertIn(key, po.OFFSET_TOPOLOGY)

    def test_self_intersecting_offset_rejected(self):
        """A concave arc offset past its centre folds the curve."""
        prof = [po.line(10.0, 2.0, 10.0, 1.0),
                po.arc(9.5, 1.0, 0.5, 0.0, -90.0,
                       material_toward_centre=True)]
        with self.assertRaises(po.ProfileOffsetError):
            po.offset_meridional_profile_normal(prof, 0.5)


class CorrectedTrayTests(SimpleTestCase):
    def test_a3_radial_failure_is_reproduced(self):
        """The legacy path must still produce the A3R value exactly."""
        tray = _tray(1.0, "RADIAL")
        self.assertAlmostEqual(_min_wall(tray), A3R_AUTHORITATIVE_MINIMUM,
                               places=6)
        # The GEOMETRY is unchanged — volume matches A3 candidate C to the
        # milligram. The identity STRING moved because the core config
        # gained a cup_offset_mode key and the config is part of the hash;
        # that is a schema change, not a geometry change, and it is
        # recorded rather than hidden.
        v, f = tray["vertices"], tray["faces"]
        vol = float(np.einsum(
            "ij,ij->i", v[f[:, 0]],
            np.cross(v[f[:, 1]] - v[f[:, 0]],
                     v[f[:, 2]] - v[f[:, 0]])).sum() / 6.0)
        self.assertAlmostEqual(vol, 19505.74, places=1)
        self.assertEqual(tray["cup_offset_mode"], "RADIAL")

    def test_true_normal_wall_passes_policy(self):
        for w in (1.10, 1.20, 1.30):
            with self.subTest(w=w):
                self.assertGreaterEqual(_min_wall(_tray(w, "TRUE_NORMAL")),
                                        1.0 - 1e-9)

    def test_corrected_tray_has_a_new_identity(self):
        corrected = _tray(1.20, "TRUE_NORMAL")
        self.assertNotEqual(corrected["mesh_identity"], FROZEN_A3_IDENTITY)
        self.assertEqual(corrected["cup_offset_mode"], "TRUE_NORMAL")
        self.assertIsNotNone(corrected["cup_profile_identity"])

    def test_deterministic_corrected_identity(self):
        self.assertEqual(_tray(1.20, "TRUE_NORMAL")["mesh_identity"],
                         _tray(1.20, "TRUE_NORMAL")["mesh_identity"])

    def test_unknown_offset_mode_fails_closed(self):
        core = dict(DEFAULT_CORE)
        core.update(CORE_STRATEGIES["C_POCKET_FOLLOWING_CORE"])
        core["cup_offset_mode"] = "NONSENSE"
        with self.assertRaises(CoredTrayError):
            build_cored_palette_tray(A3.tray_spec(), core)

    def test_fit_and_recess_are_unchanged(self):
        tray = _tray(1.20, "TRUE_NORMAL")
        cl = A3.clearance_recheck({"tray": tray})
        self.assertEqual(cl["PAN_POCKET_INTERSECTION_COUNT"], 0)
        self.assertEqual(cl["GEOMETRIC_CLEARANCE"], "PASS")
        self.assertEqual(cl["ENGINEERING_CLEARANCE_RSS"], "PASS")
        self.assertEqual(cl["MANUFACTURING_CONFIRMED_CLEARANCE"],
                         "NOT_ESTABLISHED")
        self.assertAlmostEqual(
            cl["measurement"]["governing_clearance_mm"], 0.249767, places=6)
        self.assertAlmostEqual(cl["fit_datum_unchanged_mm"], 26.8, places=6)
        self.assertAlmostEqual(cl["pan_recess_mm"], 1.0, places=9)
        self.assertGreaterEqual(cl["deck_ligament_mm"], 2.0)

    def test_corrected_tray_is_manifold_and_watertight(self):
        from apps.pipeline.services import palette_moulded_validators as mv
        rep = mv.validate_mesh("corrected", _tray(1.20, "TRUE_NORMAL"))
        d = rep["diagnostics"]
        self.assertEqual(d["boundary_edges"], 0)
        self.assertEqual(d["non_manifold_edges"], 0)
        self.assertEqual(d["inconsistent_half_edges"], 0)
        self.assertEqual(d["euler_characteristic"], 2)
        self.assertEqual(d["t_junctions"], 0)
        self.assertEqual(d["self_intersecting_pairs"], 0)

    def test_policies_unchanged(self):
        p = A3.THICKNESS_POLICY
        self.assertEqual(p["MINIMUM_LOCAL_WALL_THICKNESS"]["mm"], 1.0)
        self.assertEqual(p["MAXIMUM_LOCAL_THICKNESS"]["mm"], 2.5)
        self.assertEqual(p["MAXIMUM_THICKNESS_RATIO"]["mm"], 2.5)
        self.assertEqual(p["MINIMUM_DECK_LIGAMENT"]["mm"], 2.0)

    def test_no_blender_boolean_dependency(self):
        src = open(po.__file__).read()
        for banned in ("import bpy", "bpy.", "modifiers.new"):
            self.assertNotIn(banned, src)
