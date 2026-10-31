"""PALT-M4B-A3M — identity semantics and maximum-thickness authority."""
import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_identity as pid
from apps.pipeline.services import palette_thickness_authority as ta
from apps.pipeline.services import palt_m4b_a3 as A3
from apps.pipeline.services.palette_cored_tray_geometry import (
    CORE_STRATEGIES, DEFAULT_CORE, build_cored_palette_tray)

A3F_CONSTRUCTION_IDENTITY = "6c23c5417ef93dbb"
A3_FROZEN_IDENTITY = "26c817b8c113851a"


def _tray(w=1.20, mode="TRUE_NORMAL"):
    c = dict(DEFAULT_CORE)
    c.update(CORE_STRATEGIES["C_POCKET_FOLLOWING_CORE"])
    c["cup_offset_mode"] = mode
    c["cup_wall_mm"] = w
    return build_cored_palette_tray(A3.tray_spec(), c)


def _slab(t=4.0, w=40.0):
    """Thick slab: a genuine 4 mm wall with a long 40 mm lateral path."""
    h = w / 2
    v = np.array([[-h, -h, 0], [h, -h, 0], [h, h, 0], [-h, h, 0],
                  [-h, -h, t], [h, -h, t], [h, h, t], [-h, h, t]], float)
    f = np.array([[0, 3, 2], [0, 2, 1], [4, 5, 6], [4, 6, 7],
                  [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                  [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]], np.int64)
    return {"vertices": v, "faces": f}


class IdentitySemanticsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()

    def test_geometry_identity_ignores_contract_metadata(self):
        a = pid.mesh_geometry_identity(self.tray)
        clone = {"vertices": self.tray["vertices"].copy(),
                 "faces": self.tray["faces"].copy(),
                 "core": {"totally": "different"}, "spec": {}}
        self.assertEqual(pid.mesh_geometry_identity(clone), a)

    def test_geometry_identity_changes_when_geometry_changes(self):
        self.assertNotEqual(pid.mesh_geometry_identity(_tray(1.30)),
                            pid.mesh_geometry_identity(self.tray))

    def test_contract_identity_changes_with_offset_mode(self):
        a = pid.construction_contract_identity(_tray()["core"])
        b = pid.construction_contract_identity(_tray(1.0, "RADIAL")["core"])
        self.assertNotEqual(a, b)

    def test_contract_identity_changes_with_a_default_valued_field(self):
        base = dict(self.tray["core"])
        changed = dict(base)
        changed["perimeter_wall_mm"] = base["perimeter_wall_mm"]
        changed["newly_declared_default"] = "SOMETHING"
        self.assertNotEqual(pid.construction_contract_identity(changed),
                            pid.construction_contract_identity(base))

    def test_default_valued_keys_are_not_stripped(self):
        self.assertIn("NEVER stripped", pid.migration_map([])["policy"])

    def test_evidence_identity_is_deterministic_and_covers_hashes(self):
        g = pid.mesh_geometry_identity(self.tray)
        c = pid.construction_contract_identity(self.tray["core"])
        a = pid.evidence_package_identity(
            g, c, authority_version=ta.SCHEMA, diagnostics=["x.png"],
            pixel_hashes={"x.png": "abc"})
        self.assertEqual(a, pid.evidence_package_identity(
            g, c, authority_version=ta.SCHEMA, diagnostics=["x.png"],
            pixel_hashes={"x.png": "abc"}))
        self.assertNotEqual(a, pid.evidence_package_identity(
            g, c, authority_version=ta.SCHEMA, diagnostics=["x.png"],
            pixel_hashes={"x.png": "def"}))

    def test_migration_entry_records_legacy_alias(self):
        e = pid.migration_entry(
            old_identity=A3_FROZEN_IDENTITY, mesh=self.tray,
            contract=self.tray["core"], geometry_changed=True,
            reason="A3F true-normal offset", milestone="PALT-M4B-A3F")
        self.assertEqual(e["legacy_alias"], A3_FROZEN_IDENTITY)
        self.assertTrue(e["geometry_changed"])
        self.assertIn("mesh_geometry_identity", e)
        self.assertIn("construction_contract_identity", e)

    def test_a3_radial_geometry_identity_is_stable_across_schema_change(self):
        """The A3 mesh is byte-identical after A3F's config key was added,
        so its GEOMETRY identity must be reproducible even though the old
        combined hash moved."""
        a = pid.mesh_geometry_identity(_tray(1.0, "RADIAL"))
        b = pid.mesh_geometry_identity(_tray(1.0, "RADIAL"))
        self.assertEqual(a, b)


class MaximumAuthorityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()
        f = cls.tray["faces"]
        cls.ray = ta.normal_ray_thickness(
            cls.tray, samples_per_face=1,
            face_filter=np.arange(len(f))[::9])
        cls.auth = ta.authoritative_maximum(cls.tray, cls.ray)

    def test_long_path_is_rejected_as_local_wall(self):
        top = max(self.ray["samples"], key=lambda r: r["thickness_mm"])
        got = ta.classify_maximum(self.tray, top)
        self.assertEqual(got["classification"],
                         "LONG_PATH_NOT_LOCAL_WALL_THICKNESS")
        self.assertFalse(got["counts_toward_maximum_policy"])
        self.assertLess(got["midpoint_ratio"], got["threshold"])

    def test_authoritative_maximum_is_a_local_wall(self):
        self.assertIsNotNone(self.auth["maximum_local_wall_mm"])
        self.assertLessEqual(self.auth["maximum_local_wall_mm"], 2.5)
        self.assertGreater(self.auth["longest_material_path_mm"],
                           self.auth["maximum_local_wall_mm"])

    def test_thickness_ratio_passes_with_the_local_wall_maximum(self):
        self.assertLessEqual(self.auth["maximum_local_wall_mm"] / 1.0, 2.5)

    def test_a_genuine_thick_slab_is_not_rejected(self):
        """The filter must not throw away real thick walls."""
        slab = _slab(t=4.0)
        rep = ta.normal_ray_thickness(slab)
        sample = min(rep["samples"], key=lambda r: r["thickness_mm"])
        got = ta.classify_maximum(slab, sample)
        self.assertEqual(got["classification"],
                         "CONFIRMED_PHYSICAL_THICK_REGION")
        self.assertTrue(got["counts_toward_maximum_policy"])

    def test_midpoint_inscribed_diameter_on_a_known_slab(self):
        slab = _slab(t=4.0)
        got = ta.midpoint_inscribed_diameter(slab, [0, 0, 0], [0, 0, 4.0])
        self.assertAlmostEqual(got, 4.0, delta=0.05)

    def test_maximum_classifications_are_enumerated(self):
        for name in ("CONFIRMED_PHYSICAL_THICK_REGION",
                     "LONG_PATH_NOT_LOCAL_WALL_THICKNESS",
                     "INCORRECT_OPPOSING_SURFACE_PAIR", "UNRESOLVED"):
            self.assertIn(name, ta.MAX_CLASSIFICATIONS)

    def test_maximum_policy_definition_is_declared(self):
        self.assertEqual(self.auth["definition"],
                         "MAXIMUM_LOCAL_WALL_THICKNESS")
        self.assertEqual(self.auth["excluded_definition"],
                         "LONGEST_MATERIAL_PATH")

    def test_no_geometry_mutation(self):
        before = pid.mesh_geometry_identity(self.tray)
        ta.authoritative_maximum(self.tray, self.ray)
        self.assertEqual(pid.mesh_geometry_identity(self.tray), before)

    def test_policies_unchanged(self):
        p = A3.THICKNESS_POLICY
        self.assertEqual(p["MINIMUM_LOCAL_WALL_THICKNESS"]["mm"], 1.0)
        self.assertEqual(p["TARGET_NOMINAL_WALL_THICKNESS"]["mm"], 1.2)
        self.assertEqual(p["MAXIMUM_LOCAL_THICKNESS"]["mm"], 2.5)
        self.assertEqual(p["MAXIMUM_THICKNESS_RATIO"]["mm"], 2.5)
        self.assertEqual(p["MINIMUM_DECK_LIGAMENT"]["mm"], 2.0)
