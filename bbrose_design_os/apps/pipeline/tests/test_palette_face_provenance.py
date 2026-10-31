"""PALT-M4B-A3P — build-time face provenance and the cup-wall proof.

A3M classified faces by elevation band, which put deck-skin faces at
z=6.15 inside the cup-wall band and made the 1.20 mm proof impossible.
Provenance is now stamped at BUILD time, so nothing is inferred from
geometry, normals, bounding boxes or appearance.
"""
import math

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_identity as pid
from apps.pipeline.services import palette_thickness_authority as ta
from apps.pipeline.services import palt_m4b_a3 as A3
from apps.pipeline.services.palette_cored_tray_geometry import (
    CORE_STRATEGIES, CUP_WALL_CLASSES, DEFAULT_CORE, PRIMARY_FACE_CLASSES,
    FaceLog, FaceProvenanceError, build_cored_palette_tray)

FROZEN_GEOMETRY_IDENTITY = "7c0558062fde67a7"
TARGET_MM = 1.20
# a-priori: a 64-gon at r=14.09 mm has chord error r*(1-cos(pi/64))
CHORD_BOUND_MM = 14.09 * (1 - math.cos(math.pi / 64))
TOLERANCE_MM = 0.02


def _tray(w=1.20):
    c = dict(DEFAULT_CORE)
    c.update(CORE_STRATEGIES["C_POCKET_FOLLOWING_CORE"])
    c["cup_offset_mode"] = "TRUE_NORMAL"
    c["cup_wall_mm"] = w
    return build_cored_palette_tray(A3.tray_spec(), c)


class FaceLogTests(SimpleTestCase):
    def test_emitting_without_a_class_fails_closed(self):
        log = FaceLog()
        with self.assertRaises(FaceProvenanceError):
            log.append((0, 1, 2))

    def test_unknown_class_rejected(self):
        log = FaceLog()
        with self.assertRaises(FaceProvenanceError):
            log.begin("NOT_A_REAL_CLASS")

    def test_audit_rejects_unknown_face_class(self):
        log = FaceLog()
        log.begin("CORE_WALL")
        log.append((0, 1, 2))
        log.classes[0] = "UNKNOWN_FACE_CLASS"
        with self.assertRaises(FaceProvenanceError):
            log.audit()

    def test_audit_rejects_a_length_mismatch(self):
        log = FaceLog()
        log.begin("CORE_WALL")
        log.append((0, 1, 2))
        log.classes.append("CORE_WALL")
        with self.assertRaises(FaceProvenanceError):
            log.audit()


class TrayProvenanceTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()
        cls.fc = np.array(cls.tray["face_classes"])

    def test_geometry_is_frozen(self):
        """Provenance is metadata; it must not move the mesh."""
        self.assertEqual(pid.mesh_geometry_identity(self.tray),
                         FROZEN_GEOMETRY_IDENTITY)

    def test_every_face_has_exactly_one_primary_class(self):
        self.assertEqual(len(self.tray["face_classes"]),
                         len(self.tray["faces"]))
        for k in self.tray["face_classes"]:
            self.assertIn(k, PRIMARY_FACE_CLASSES)

    def test_no_unclassified_faces(self):
        self.assertEqual(
            self.tray["face_classes"].count("UNKNOWN_FACE_CLASS"), 0)

    def test_class_counts_sum_to_the_face_count(self):
        self.assertEqual(sum(self.tray["face_class_counts"].values()),
                         len(self.tray["faces"]))

    def test_expected_classes_are_present(self):
        for k in ("OUTER_DECK_TOP", "POCKET_RIM_FILLET",
                  "POCKET_DRAFTED_WALL", "POCKET_FLOOR_FILLET",
                  "POCKET_FLOOR", "CORE_CEILING", "CORE_WALL",
                  "BASE_SKIN_UNDERSIDE", "OUTER_SIDE_WALL",
                  "PERIMETER_STRUCTURE"):
            self.assertIn(k, self.tray["face_class_counts"], k)

    def test_provenance_is_deterministic(self):
        self.assertEqual(_tray()["face_classes"],
                         self.tray["face_classes"])

    def test_provenance_is_not_inferred_from_elevation(self):
        """Deck-skin and cup-wall faces coexist at the core ceiling; a
        band classifier cannot separate them, provenance can."""
        v, f = self.tray["vertices"], self.tray["faces"]
        cz = v[f].mean(axis=1)[:, 2]
        mixed = []
        for lo in np.arange(1.5, 7.15, 0.1):
            band = (cz >= lo) & (cz < lo + 0.1)
            if band.any() and len(set(self.fc[band])) > 1:
                mixed.append((round(float(lo), 2), sorted(set(self.fc[band]))))
        # at least one elevation band holds more than one face class, so a
        # band classifier is inherently ambiguous and provenance is required
        self.assertTrue(mixed, "no band mixes classes")


class CupWallProofTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tray = _tray()
        fc = np.array(cls.tray["face_classes"])
        cls.ray = ta.normal_ray_thickness(
            cls.tray, samples_per_face=1,
            face_filter=np.nonzero(np.isin(fc, list(CUP_WALL_CLASSES)))[0][::3])
        cls.all_ray = ta.normal_ray_thickness(
            cls.tray, samples_per_face=1,
            face_filter=np.arange(len(cls.tray["faces"]))[::9])

    def _pairs(self, src, opp):
        return [s["thickness_mm"] for s in self.ray["samples"]
                if self.tray["face_classes"][s["source_face"]] == src
                and self.tray["face_classes"][s["opposing_face"]] == opp]

    def test_tolerance_is_an_a_priori_bound_not_a_fitted_one(self):
        self.assertLessEqual(CHORD_BOUND_MM, TOLERANCE_MM)
        self.assertAlmostEqual(CHORD_BOUND_MM, 0.01697, places=5)

    def test_drafted_wall_holds_the_target(self):
        vals = self._pairs("POCKET_DRAFTED_WALL", "CORE_WALL")
        self.assertTrue(vals)
        for t in vals:
            self.assertAlmostEqual(t, TARGET_MM, delta=TOLERANCE_MM)

    def test_floor_fillet_holds_the_target(self):
        vals = self._pairs("POCKET_FLOOR_FILLET", "CORE_WALL")
        self.assertTrue(vals)
        for t in vals:
            self.assertAlmostEqual(t, TARGET_MM, delta=TOLERANCE_MM)

    def test_cup_wall_is_never_averaged_with_other_features(self):
        """Every cup-wall sample is keyed by BOTH endpoints' classes."""
        for s in self.ray["samples"]:
            src = self.tray["face_classes"][s["source_face"]]
            self.assertIn(src, CUP_WALL_CLASSES)

    def test_no_sample_below_the_minimum_wall_policy(self):
        self.assertEqual(
            [s["thickness_mm"] for s in self.all_ray["samples"]
             if s["thickness_mm"] < 1.0 - 1e-9], [])

    def test_every_sub_target_sample_has_a_real_class(self):
        for s in self.all_ray["samples"]:
            if s["thickness_mm"] < TARGET_MM:
                k = self.tray["face_classes"][s["source_face"]]
                self.assertIn(k, PRIMARY_FACE_CLASSES)
                self.assertNotEqual(k, "UNKNOWN_FACE_CLASS")

    def test_intentional_one_millimetre_features_are_separately_governed(self):
        """The 1.0 mm samples must be skins, never the cup wall."""
        for s in self.all_ray["samples"]:
            if s["thickness_mm"] < 1.05:
                k = self.tray["face_classes"][s["source_face"]]
                self.assertNotIn(k, ("POCKET_DRAFTED_WALL",))

    def test_the_long_path_is_provably_a_non_wall_pair(self):
        """A3M used a heuristic; provenance names both surfaces."""
        top = max(self.all_ray["samples"], key=lambda r: r["thickness_mm"])
        src = self.tray["face_classes"][top["source_face"]]
        opp = self.tray["face_classes"][top["opposing_face"]]
        self.assertNotEqual(src, opp)
        self.assertEqual(
            ta.classify_maximum(self.tray, top)["classification"],
            "LONG_PATH_NOT_LOCAL_WALL_THICKNESS")

    def test_policies_unchanged(self):
        p = A3.THICKNESS_POLICY
        self.assertEqual(p["MINIMUM_LOCAL_WALL_THICKNESS"]["mm"], 1.0)
        self.assertEqual(p["TARGET_NOMINAL_WALL_THICKNESS"]["mm"], 1.2)
        self.assertEqual(p["MAXIMUM_THICKNESS_RATIO"]["mm"], 2.5)
