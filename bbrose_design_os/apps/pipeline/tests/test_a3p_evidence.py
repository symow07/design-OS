"""PALT-M4B-A3P §5 — the required-evidence manifest and its validation.

The 41 diagnostics were produced by a one-off run. Without these, a kernel
change would silently stale the committed package while
``A3P_41_DIAGNOSTICS: COMPLETE`` kept reading as true — and that record is
the precondition the owner named for M5.
"""
import copy
import os
import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from apps.pipeline.services import a3p_evidence_manifest as MAN
from apps.pipeline.services import a3p_evidence_render as R

#: absolute, so a working-directory change cannot turn this guard into a
#: silent skip. The package is committed, so absence is a failure.
REPO = Path(__file__).resolve().parents[3]
EVIDENCE = str(REPO / "docs" / "roadmap" / "palt_m4b_a3p" / "evidence")


class RequiredManifestTests(SimpleTestCase):
    def test_it_holds_exactly_the_41_the_directives_named(self):
        self.assertEqual(MAN.TOTAL, 41)
        self.assertEqual(len(MAN.REQUIRED), 41)
        self.assertEqual(MAN.COUNTS, {"A3R": 13, "A3F": 16, "A3M": 12})
        for milestone, count in MAN.COUNTS.items():
            self.assertEqual(
                sum(1 for r in MAN.REQUIRED if r[1] == milestone), count)

    def test_filenames_are_unique(self):
        names = [r[0] for r in MAN.REQUIRED]
        self.assertEqual(len(set(names)), len(names))

    def test_every_entry_declares_a_feature_the_probe_understands(self):
        for _name, _m, _p, feature in MAN.REQUIRED:
            self.assertIn(feature, R.FEATURE_PROBE)

    def test_the_a3r_set_is_bound_to_the_failed_candidate(self):
        b = MAN.GEOMETRY_BINDING["A3R"]
        self.assertEqual(b["mesh_geometry_identity"], "743ead2beceb7fe5")
        self.assertEqual(b["legacy_alias"], "26c817b8c113851a")
        self.assertEqual(b["status"], "HISTORICAL")

    def test_the_a3f_and_a3m_sets_share_the_corrected_geometry(self):
        self.assertEqual(MAN.GEOMETRY_BINDING["A3F"]
                         ["mesh_geometry_identity"], "7c0558062fde67a7")
        self.assertEqual(MAN.GEOMETRY_BINDING["A3M"]
                         ["mesh_geometry_identity"], "7c0558062fde67a7")

    def test_all_eight_failure_conditions_are_declared(self):
        self.assertEqual(len(MAN.FAILURE_CONDITIONS), 8)


class StampTests(SimpleTestCase):
    """``stamp`` chooses labels from the MEASURED geometry, so its choice
    must still be right when two milestones share one geometry."""

    def _stamp(self, milestone, identity):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "x.png")
        Image.new("RGB", (64, 48), (200, 100, 60)).save(path)
        R.stamp(path, milestone, "T", "S", geometry_identity=identity)
        return Image.open(path).text

    def test_a3m_keeps_its_own_labels_despite_sharing_a3f_geometry(self):
        shared = MAN.GEOMETRY_BINDING["A3M"]["mesh_geometry_identity"]
        self.assertEqual(
            MAN.GEOMETRY_BINDING["A3F"]["mesh_geometry_identity"], shared,
            "this test only means something while the two share geometry")
        meta = self._stamp("A3M", shared)
        self.assertEqual(meta["a3p_labels"].split("|"),
                         list(MAN.REQUIRED_LABELS["A3M"]))

    def test_a3f_keeps_its_own_labels_too(self):
        meta = self._stamp(
            "A3F", MAN.GEOMETRY_BINDING["A3F"]["mesh_geometry_identity"])
        self.assertEqual(meta["a3p_labels"].split("|"),
                         list(MAN.REQUIRED_LABELS["A3F"]))

    def test_the_wrong_geometry_still_gets_the_wrong_labels(self):
        """prefer must not paper over a real mismatch."""
        meta = self._stamp(
            "A3F", MAN.GEOMETRY_BINDING["A3R"]["mesh_geometry_identity"])
        self.assertEqual(meta["a3p_labels"].split("|"),
                         list(MAN.REQUIRED_LABELS["A3R"]))
        self.assertEqual(meta["a3p_status"], "HISTORICAL")

    def test_an_unrecognised_geometry_is_labelled_as_such(self):
        meta = self._stamp("A3F", "0000000000000000")
        self.assertIn("UNRECOGNISED GEOMETRY", meta["a3p_labels"])
        self.assertEqual(meta["a3p_status"], "UNRECOGNISED_GEOMETRY")


class FrozenGeometryTests(SimpleTestCase):
    def test_both_frozen_trays_still_rebuild_to_their_identities(self):
        for milestone in ("A3R", "A3F", "A3M"):
            tray = R.frozen_tray(milestone)
            self.assertEqual(
                tray["_geometry_identity"],
                MAN.GEOMETRY_BINDING[milestone]["mesh_geometry_identity"])

    def test_it_refuses_to_render_a_drifted_kernel(self):
        """Rendering anyway would attach a truthful label to the wrong
        mesh."""
        bind = copy.deepcopy(MAN.GEOMETRY_BINDING)
        bind["A3F"]["mesh_geometry_identity"] = "deadbeefdeadbeef"
        with self.settings():
            original = MAN.GEOMETRY_BINDING
            MAN.GEOMETRY_BINDING = bind
            try:
                with self.assertRaises(R.EvidenceRenderError) as ctx:
                    R.frozen_tray("A3F")
                self.assertIn("deadbeefdeadbeef", str(ctx.exception))
            finally:
                MAN.GEOMETRY_BINDING = original

    def test_an_unrecognised_identity_is_named_as_such(self):
        name, bind = R.binding_for_identity("0000000000000000")
        self.assertIsNone(name)
        self.assertEqual(bind["status"], "UNRECOGNISED_GEOMETRY")


class CommittedPackageTests(SimpleTestCase):
    """The package that is in the repository must stay valid."""

    def test_the_committed_package_is_present(self):
        self.assertTrue(os.path.isdir(EVIDENCE),
                        f"the committed evidence package is missing from "
                        f"{EVIDENCE}")

    def test_the_committed_package_validates_clean(self):
        report = R.validate_package(EVIDENCE)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["present_count"], MAN.TOTAL)
        self.assertEqual(report["A3P_41_DIAGNOSTICS"], "COMPLETE")
        self.assertEqual(report["A3P_EVIDENCE_MANIFEST"], "PASS")

    def test_every_image_carries_its_measured_geometry_identity(self):
        for name, milestone, _p, _f in MAN.REQUIRED:
            meta = Image.open(os.path.join(EVIDENCE, name)).text
            with self.subTest(name=name):
                self.assertEqual(
                    meta["a3p_geometry_identity"],
                    MAN.GEOMETRY_BINDING[milestone]
                    ["mesh_geometry_identity"])

    def _tampered_dir(self, mutate):
        tmp = tempfile.mkdtemp()
        for name, *_ in MAN.REQUIRED:
            shutil.copy(os.path.join(EVIDENCE, name),
                        os.path.join(tmp, name))
        mutate(tmp)
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        return tmp

    def _restamp(self, path, **overrides):
        img = Image.open(path)
        meta = PngInfo()
        text = dict(img.text)
        text.update(overrides)
        for k, v in text.items():
            meta.add_text(k, v)
        img.convert("RGB").save(path, pnginfo=meta)

    def test_a_wrong_source_geometry_is_detected(self):
        """The negative control. If the stamp restated the requirement
        instead of recording a measurement, this could not fire."""
        target = "corrected_tray_top.png"
        tmp = self._tampered_dir(
            lambda d: self._restamp(
                os.path.join(d, target),
                a3p_geometry_identity="743ead2beceb7fe5"))
        report = R.validate_package(tmp)
        codes = {f["code"] for f in report["findings"]
                 if f.get("file") == target}
        self.assertIn("WRONG_SOURCE_GEOMETRY", codes)
        self.assertEqual(report["A3P_EVIDENCE_MANIFEST"], "FAIL")

    def test_historical_evidence_presented_as_current_is_detected(self):
        target = "minimum_location_top.png"
        tmp = self._tampered_dir(
            lambda d: self._restamp(os.path.join(d, target),
                                    a3p_status="CURRENT"))
        codes = {f["code"] for f in R.validate_package(tmp)["findings"]
                 if f.get("file") == target}
        self.assertIn("HISTORICAL_PRESENTED_AS_CURRENT", codes)

    def test_a_missing_required_label_is_detected(self):
        target = "convergence_plot.png"
        tmp = self._tampered_dir(
            lambda d: self._restamp(os.path.join(d, target),
                                    a3p_labels="SOMETHING ELSE"))
        codes = {f["code"] for f in R.validate_package(tmp)["findings"]
                 if f.get("file") == target}
        self.assertIn("REQUIRED_LABEL_MISSING", codes)

    def test_an_absent_image_is_detected(self):
        target = "false_pairing_diagnostic.png"
        tmp = self._tampered_dir(
            lambda d: os.remove(os.path.join(d, target)))
        report = R.validate_package(tmp)
        self.assertIn("IMAGE_ABSENT",
                      {f["code"] for f in report["findings"]})
        self.assertEqual(report["A3P_41_DIAGNOSTICS"], "INCOMPLETE")

    def test_an_unlisted_filename_is_detected(self):
        tmp = self._tampered_dir(
            lambda d: Image.new("RGB", (8, 8)).save(
                os.path.join(d, "not_in_the_manifest.png")))
        self.assertIn("FILENAME_NOT_IN_MANIFEST",
                      {f["code"] for f in R.validate_package(tmp)
                       ["findings"]})

    def test_blank_evidence_is_detected(self):
        target = "corrected_thickness_map.png"
        def blank(d):
            img = Image.open(os.path.join(d, target))
            flat = Image.new("RGB", img.size, (250, 249, 246))
            meta = PngInfo()
            for k, v in img.text.items():
                meta.add_text(k, v)
            flat.save(os.path.join(d, target), pnginfo=meta)
        tmp = self._tampered_dir(blank)
        codes = {f["code"] for f in R.validate_package(tmp)["findings"]
                 if f.get("file") == target}
        self.assertIn("EVIDENCE_VISUALLY_BLANK", codes)
