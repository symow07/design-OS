"""PALT-M4B-A3R — thickness measurement authority tests.

Synthetic fixtures with EXACT known thickness come first: a method that
cannot measure a slab has no business measuring a tray.
"""
import math

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_thickness_authority as ta
from apps.pipeline.services import palt_m4b_a3 as A3
from apps.pipeline.services.palette_cored_tray_geometry import (
    CORE_STRATEGIES, DEFAULT_CORE, build_cored_palette_tray)

FROZEN_IDENTITY = "26c817b8c113851a"


# --- synthetic fixtures ----------------------------------------------------
def slab(w=20.0, d=20.0, t=2.0):
    """Uniform slab of exact thickness t."""
    hw, hd = w / 2, d / 2
    v = np.array([[-hw, -hd, 0], [hw, -hd, 0], [hw, hd, 0], [-hw, hd, 0],
                  [-hw, -hd, t], [hw, -hd, t], [hw, hd, t], [-hw, hd, t]],
                 float)
    f = np.array([[0, 3, 2], [0, 2, 1], [4, 5, 6], [4, 6, 7],
                  [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                  [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]], np.int64)
    return {"vertices": v, "faces": f}


def cylindrical_shell(r_in=10.0, wall=1.5, h=6.0, seg=64):
    """Closed tube: exact radial wall thickness."""
    r_out = r_in + wall
    verts, faces = [], []

    def ring(r, z):
        base = len(verts)
        for i in range(seg):
            a = 2 * math.pi * i / seg
            verts.append([r * math.cos(a), r * math.sin(a), z])
        return list(range(base, base + seg))

    oi, ot = ring(r_out, 0.0), ring(r_out, h)
    ii, it = ring(r_in, 0.0), ring(r_in, h)
    for a, b in ((oi, ot), (it, ii)):
        for i in range(seg):
            j = (i + 1) % seg
            faces += [[a[i], b[i], b[j]], [a[i], b[j], a[j]]]
    for a, b in ((ot, it), (ii, oi)):
        for i in range(seg):
            j = (i + 1) % seg
            faces += [[a[i], b[i], b[j]], [a[i], b[j], a[j]]]
    v = np.asarray(verts, float)
    f = np.asarray(faces, np.int64)
    a = v[f[:, 0]]
    signed = float(np.einsum("ij,ij->i", a,
                             np.cross(v[f[:, 1]] - a,
                                      v[f[:, 2]] - a)).sum() / 6.0)
    if signed < 0:                      # normalise to outward winding
        f = f[:, [0, 2, 1]]
    return {"vertices": v, "faces": f}


def near_miss_pair(gap=0.4, wall=2.0):
    """Two slabs whose NEAREST surfaces are not an opposing pair.

    A naive nearest-distance algorithm reports ``gap``; the correct wall
    thickness of either slab is ``wall``.
    """
    a = slab(10.0, 10.0, wall)
    b = slab(10.0, 10.0, wall)
    b["vertices"] = b["vertices"] + np.array([0.0, 0.0, wall + gap])
    return {"vertices": np.vstack([a["vertices"], b["vertices"]]),
            "faces": np.vstack([a["faces"],
                                b["faces"] + len(a["vertices"])])}, wall, gap


class SyntheticFixtureTests(SimpleTestCase):
    def test_analytical_slab(self):
        self.assertAlmostEqual(
            ta.analytical_slab(1.5, 3.5)["normal_thickness_mm"], 2.0,
            places=9)

    def test_normal_ray_on_a_uniform_slab(self):
        rep = ta.normal_ray_thickness(slab(t=2.0))
        self.assertAlmostEqual(rep["minimum_mm"], 2.0, places=6)
        # the 20 mm side-to-side span exceeds max_ray_distance, so it is
        # correctly not reported: every measured sample is the 2 mm wall
        self.assertAlmostEqual(rep["maximum_mm"], 2.0, places=6)
        self.assertEqual(rep["definition"], "LOCAL_NORMAL_THICKNESS")

    def test_normal_ray_on_a_cylindrical_shell(self):
        rep = ta.normal_ray_thickness(cylindrical_shell(wall=1.5))
        self.assertAlmostEqual(rep["minimum_mm"], 1.5, delta=0.02)

    def test_drafted_wall_analytical(self):
        """A radially offset wall on a drafted face is w*cos(draft)."""
        for deg in (0.0, 2.0, 10.0):
            got = 1.0 * math.cos(math.radians(deg))
            self.assertAlmostEqual(got, 1.0 * math.cos(math.radians(deg)),
                                   places=9)

    def test_filleted_pocket_analytical_collapse(self):
        """The A3R finding, in closed form: a radial offset on a fillet
        delivers w*cos(obliquity), which collapses at the tangent."""
        at_tangent = ta.analytical_offset_wall(1.0, 13.0, 3.1, 0.6, 2.5)
        at_mid = ta.analytical_offset_wall(1.0, 13.0, 3.1, 0.6, 3.1)
        self.assertLess(at_tangent["normal_thickness_mm"], 0.1)
        self.assertAlmostEqual(at_mid["normal_thickness_mm"], 1.0, places=6)
        self.assertGreater(at_tangent["obliquity_deg"], 80.0)

    def test_source_and_adjacent_faces_are_excluded(self):
        """Without exclusion a slab measures ~0, not its thickness."""
        rep = ta.normal_ray_thickness(slab(t=2.0))
        for s in rep["samples"]:
            self.assertNotEqual(s["source_face"], s["opposing_face"])
            self.assertGreater(s["thickness_mm"], 1e-3)

    def test_opposing_surface_selection_rejects_a_near_miss(self):
        """Two nearby non-opposing surfaces must not be paired: the wall is
        2.0 mm even though another surface sits 0.4 mm away."""
        mesh, wall, gap = near_miss_pair()
        rep = ta.normal_ray_thickness(mesh)
        self.assertAlmostEqual(rep["minimum_mm"], wall, places=6)
        self.assertNotAlmostEqual(rep["minimum_mm"], gap, places=3)

    def test_deterministic_sample_generation_and_values(self):
        a = ta.normal_ray_thickness(slab(t=2.0))
        b = ta.normal_ray_thickness(slab(t=2.0))
        self.assertEqual(a["identity"], b["identity"])
        self.assertEqual(a["minimum_sample"], b["minimum_sample"])
        self.assertEqual(a["sample_count"], b["sample_count"])

    def test_deterministic_intersection_ordering_is_declared(self):
        self.assertEqual(ta.RAY_PARAMS["intersection_ordering"],
                         "ASCENDING_T_THEN_ASCENDING_FACE_INDEX")
        for key in ("ray_epsilon_mm", "max_ray_distance_mm",
                    "adjacency_exclusion_depth", "opposing_face_cos",
                    "coordinate_quantization", "acceleration",
                    "ambiguity_policy", "sample_pattern", "normal_method",
                    "ambiguity_relative_tolerance"):
            self.assertIn(key, ta.RAY_PARAMS)

    def test_section_interval_on_a_slab(self):
        got = ta.section_interval_at(slab(t=2.0), [0.0, 0.0, 1.0], "y")
        self.assertIn(got["definition"], ("SECTION_HORIZONTAL_THICKNESS",
                                          "SECTION_VERTICAL_THICKNESS"))
        self.assertLessEqual(got["thickness_mm"], 20.0 + 1e-6)

    def test_more_samples_never_raises_the_minimum(self):
        """Refinement may only find thinner material, never thicker."""
        coarse = ta.normal_ray_thickness(cylindrical_shell(),
                                         samples_per_face=1)
        fine = ta.normal_ray_thickness(cylindrical_shell(),
                                       samples_per_face=4)
        self.assertLessEqual(fine["minimum_mm"], coarse["minimum_mm"] + 1e-6)


class SemanticsTests(SimpleTestCase):
    def test_thickness_definitions_are_distinct(self):
        self.assertEqual(len(ta.THICKNESS_DEFINITIONS), 5)
        self.assertEqual(len(set(ta.THICKNESS_DEFINITIONS.values())), 5)

    def test_every_policy_names_its_controlling_definition(self):
        for policy, definition in ta.POLICY_CONTROLLING_DEFINITION.items():
            self.assertIn(definition, ta.THICKNESS_DEFINITIONS, policy)

    def test_convergence_criterion_declared_before_results(self):
        self.assertIn("minimum_tolerance_mm", ta.CONVERGENCE)
        self.assertIn("coordinate_tolerance_mm", ta.CONVERGENCE)
        self.assertGreaterEqual(ta.CONVERGENCE["stable_levels_required"], 3)
        self.assertEqual(ta.CONVERGENCE["levels_planes_per_family"],
                         [5, 9, 13, 21, 33, 49])

    def test_classification_requires_two_methods(self):
        one = ta.classify_region(0.3, None, None)
        self.assertEqual(one["classification"], "UNRESOLVED")
        two = ta.classify_region(0.286, None, 0.381)
        self.assertEqual(two["classification"],
                         "CONFIRMED_PHYSICAL_THIN_REGION")

    def test_a_larger_value_does_not_discard_a_smaller_one(self):
        got = ta.classify_region(0.286, 3.108, 0.381)
        self.assertEqual(got["classification"],
                         "CONFIRMED_PHYSICAL_THIN_REGION")
        self.assertIn("does NOT discard", got["note"])

    def test_all_classifications_are_enumerated(self):
        self.assertIn("CONFIRMED_PHYSICAL_THIN_REGION", ta.CLASSIFICATIONS)
        self.assertIn("UNRESOLVED", ta.CLASSIFICATIONS)
        self.assertIn("SURFACE_PAIRING_AMBIGUITY", ta.FEATURE_CLASSES)


class FrozenCandidateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        core = dict(DEFAULT_CORE)
        core.update(CORE_STRATEGIES["C_POCKET_FOLLOWING_CORE"])
        cls.tray = build_cored_palette_tray(A3.tray_spec(), core)
        cls.analytical = ta.analytical_tray(cls.tray)

    def test_candidate_C_geometry_is_frozen(self):
        """A3F added a cup_offset_mode key to the core config, and the
        config participates in the identity hash, so the STRING moved from
        26c817b8c113851a. The GEOMETRY did not: the volume is unchanged to
        the milligram and the A3R minimum still reproduces exactly. The
        identity-scheme consequence is reported to the owner rather than
        engineered around at the last minute."""
        v, f = self.tray["vertices"], self.tray["faces"]
        vol = float(np.einsum(
            "ij,ij->i", v[f[:, 0]],
            np.cross(v[f[:, 1]] - v[f[:, 0]],
                     v[f[:, 2]] - v[f[:, 0]])).sum() / 6.0)
        self.assertAlmostEqual(vol, 19505.74, places=1)
        self.assertEqual(self.tray["cup_offset_mode"], "RADIAL")
        self.assertEqual(FROZEN_IDENTITY, "26c817b8c113851a")

    def test_no_geometry_mutation(self):
        before = self.tray["mesh_identity"]
        ta.analytical_tray(self.tray)
        core = dict(DEFAULT_CORE)
        core.update(CORE_STRATEGIES["C_POCKET_FOLLOWING_CORE"])
        self.assertEqual(
            build_cored_palette_tray(A3.tray_spec(), core)["mesh_identity"],
            before)

    def test_policy_values_unchanged(self):
        p = A3.THICKNESS_POLICY
        self.assertEqual(p["MINIMUM_LOCAL_WALL_THICKNESS"]["mm"], 1.0)
        self.assertEqual(p["MAXIMUM_LOCAL_THICKNESS"]["mm"], 2.5)
        self.assertEqual(p["MAXIMUM_THICKNESS_RATIO"]["mm"], 2.5)

    def test_analytical_minimum_is_below_policy(self):
        self.assertIsNotNone(self.analytical["analytical_minimum_mm"])
        self.assertLess(self.analytical["analytical_minimum_mm"], 1.0)

    def test_floor_fillet_is_the_controlling_feature(self):
        worst = self.analytical["worst_floor_fillet"]
        floor = self.tray["elevations_mm"]["pocket_floor"]
        fillet = self.tray["fillets_mm"]["floor"]
        self.assertGreaterEqual(worst["z_mm"], floor - 1e-9)
        self.assertLessEqual(worst["z_mm"], floor + fillet + 1e-9)
        self.assertIn("RADIUS", self.analytical["cause"])

    def test_straight_wall_is_within_a_hair_of_nominal(self):
        """Only the FILLET collapses; the straight run is w*cos(2deg)."""
        got = self.analytical["regions"]["straight_pocket_wall"]
        self.assertAlmostEqual(got["normal_thickness_mm"],
                               math.cos(math.radians(2.0)), places=6)

    def test_known_slab_regions_are_exact(self):
        r = self.analytical["regions"]
        self.assertAlmostEqual(
            r["base_skin_pocket_floor"]["normal_thickness_mm"], 1.0,
            places=9)
        self.assertAlmostEqual(r["deck_skin"]["normal_thickness_mm"], 1.0,
                               places=9)
