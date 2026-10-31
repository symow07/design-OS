"""M6 Phase 0 — R1/R2/R3/R6 assertions, each with the negative control
that proves it can fail. An assertion with no demonstrated failure mode
does not count (repair declaration 1e198aed8d86ed9c)."""
import glob

import numpy as np
from django.test import SimpleTestCase

from apps.pipeline.services import palette_powder_texture_axes as TX

M6 = "docs/roadmap/palt_m6"


def _synthetic_region_idx(h=100, w=100):
    """PLANAR = top block, GRAZING = next block, as flat indices."""
    idx = np.arange(h * w).reshape(h, w)
    return {"PLANAR": idx[5:45, 5:95].ravel().tolist(),
            "GRAZING": idx[55:95, 5:95].ravel().tolist()}


def _declared(arr, seed=0):
    """A558 — a synthetic frame with its identity DECLARED.

    source_kind says IN_MEMORY_SYNTHETIC in every record it reaches, so
    a synthetic frame can never be read as a rendered one. Tests that
    exercise the FORMULA must still name their input; that is the
    point.
    """
    return TX.provenanced_frame(arr, path="<synthetic>",
                                family="SYNTHETIC", seed=seed,
                                source_kind="IN_MEMORY_SYNTHETIC")


class R1FrameProvenanceTests(SimpleTestCase):
    def test_the_committed_8bit_artifact_is_refused(self):
        """The negative control is the exact artifact that caused
        F1/F2: a committed '_16bit' PNG that is uint8 RGBA."""
        frames = glob.glob(f"{M6}/texture_axes/*_16bit.png")
        self.assertTrue(frames, "the defect artifact must exist")
        with self.assertRaises(TX.FrameProvenanceError):
            TX.load_scene_linear(frames[0])

    def test_uint8_and_nonfloat_arrays_are_refused(self):
        with self.assertRaises(TX.FrameProvenanceError):
            TX.frame_provenance_assertion(
                np.zeros((8, 8, 4), dtype=np.uint8))
        with self.assertRaises(TX.FrameProvenanceError):
            TX.frame_provenance_assertion(
                np.zeros((8, 8, 3), dtype=np.uint16))
        with self.assertRaises(TX.FrameProvenanceError):
            TX.frame_provenance_assertion(None)
        with self.assertRaises(TX.FrameProvenanceError):
            TX.frame_provenance_assertion(
                np.zeros((8, 8), dtype=np.float32))

    def test_alpha_is_dropped_not_averaged(self):
        rgba = np.zeros((4, 4, 4), dtype=np.float32)
        rgba[..., :3] = 0.5
        rgba[..., 3] = 1.0
        out = TX.frame_provenance_assertion(rgba)
        self.assertEqual(out.shape, (4, 4))
        self.assertAlmostEqual(float(out[0, 0]), 0.5, places=6)

    def test_a_committed_exr_loads_as_float(self):
        exrs = glob.glob(f"{M6}/texture_axes/tx_*.exr") or \
            glob.glob(f"{M6}/texture_axes/*.exr")
        self.assertTrue(exrs, "an EXR must exist on disk")
        frame = TX.load_scene_linear(exrs[0])
        self.assertEqual(frame.ndim, 2)
        self.assertTrue(np.issubdtype(frame.dtype, np.floating))

    def test_region_alignment_rejects_a_misoriented_frame(self):
        """The negative control for the orientation defect: the same
        frame UNflipped must fail the alignment assertion against the
        Blender-side authority, exactly as the misaligned Phase 1 run
        would have."""
        import json
        from apps.pipeline.services import (
            palette_characterization_rig as CR)
        meas_path = (f"{M6}/texture_axes/"
                     f"swatch_tx_SURFACE_CONTINUITY_high.json")
        exr_path = meas_path.replace(".json", ".exr")
        measurement = json.load(open(meas_path))
        idx = CR.region_indices(f"{M6}/texture_axes")
        frame = TX.load_scene_linear(exr_path)
        TX.region_alignment_assertion(frame, idx, measurement)  # passes
        with self.assertRaises(TX.FrameProvenanceError):
            TX.region_alignment_assertion(frame[::-1], idx, measurement)


class R2StimulusRealizationTests(SimpleTestCase):
    def test_identical_frames_report_not_realized(self):
        """R2's negative control: bit-identical members must report
        STIMULUS_NOT_REALIZED, never 'no axis detects'."""
        rng = np.random.default_rng(0)
        frame = rng.uniform(0.2, 0.8, (100, 100))
        rec = TX.stimulus_realization(frame, frame.copy(),
                                      _synthetic_region_idx())
        self.assertFalse(rec["realized"])
        self.assertEqual(rec["rms"], 0.0)

    def test_a_real_difference_realizes(self):
        rng = np.random.default_rng(0)
        a = rng.uniform(0.2, 0.8, (100, 100))
        b = a + rng.normal(0.0, 0.05, a.shape)
        rec = TX.stimulus_realization(a, b, _synthetic_region_idx())
        self.assertTrue(rec["realized"])

    def test_the_floor_is_a_realization_floor_not_a_pass_bar(self):
        self.assertEqual(TX.REALIZATION_FLOOR, 0.002)
        self.assertNotEqual(TX.REALIZATION_FLOOR, TX.EFFECT_BAR)


class R3WithdrawnAxisTests(SimpleTestCase):
    def test_the_axis_is_withdrawn_from_the_registry(self):
        self.assertNotIn("SURFACE_AUTOCORRELATION_MM", TX.TEXTURE_AXES)

    def test_synthetic_field_control_records_the_failure(self):
        """SYNTHETIC_FIELD_CONTROL: a field with a KNOWN long
        correlation length. The withdrawn formula must fail to recover
        it — that failure is what makes the withdrawal evidence."""
        rng = np.random.default_rng(7)
        raw = rng.normal(0.0, 1.0, (160, 160))
        field = raw.copy()
        for _ in range(3):  # ~8px correlation length
            k = np.ones(9) / 9.0
            field = np.apply_along_axis(
                lambda r: np.convolve(r, k, mode="same"), 1, field)
            field = np.apply_along_axis(
                lambda c: np.convolve(c, k, mode="same"), 0, field)
        centred = field - field.mean()
        var = float((centred ** 2).mean())
        lag4 = float((centred[:, :-4] * centred[:, 4:]).mean()) / var
        self.assertGreater(lag4, 0.5,
                           "the synthetic field must really carry a "
                           "correlation length beyond 4px")
        recovered_mm = TX.withdrawn_autocorrelation_reference(field)
        true_mm = 8.0 / (1200.0 / 84.0)
        # it recovers at most half the true length here (4px for an
        # 8px field, kernel-bounded) and exactly 2px on every rendered
        # frame ever measured — failure to recover, recorded
        self.assertLessEqual(recovered_mm, true_mm / 2.0,
                             "the withdrawn formula is bounded by its "
                             "own high-pass kernel, not the field's "
                             "correlation length — the recorded "
                             "failure that justifies R3")
        self.assertLess(recovered_mm, true_mm)


class A3DerivedStatusTests(SimpleTestCase):
    """Gate A3 — REALIZED is derived from the exit record, never a
    literal of either polarity."""

    def test_status_derives_realized_from_the_real_record(self):
        from apps.pipeline.services import (
            palette_instrument_repair_protocol as RP)
        status = RP.repair_status()
        self.assertTrue(status["REALIZED"])
        self.assertTrue(status["realized_evidence"])
        self.assertEqual(status["repair_identity"], "1e198aed8d86ed9c")

    def test_a_missing_record_reports_unrealized_not_raises(self):
        from apps.pipeline.services import (
            palette_instrument_repair_protocol as RP)
        status = RP.repair_status("docs/roadmap/palt_m6/no_such.json")
        self.assertFalse(status["REALIZED"])

    def test_a_tampered_record_raises(self):
        import json
        import tempfile
        import os as _os
        from pathlib import Path
        from apps.pipeline.services import (
            palette_instrument_repair_protocol as RP)
        repo = Path(RP.__file__).resolve().parents[3]
        real = json.loads(
            (repo / RP.EXIT_RECORD).read_text())
        first = next(iter(real["exit_conditions"]))
        real["exit_conditions"][first]["satisfied"] = False
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", dir=repo, delete=False) as fh:
            json.dump(real, fh)
            name = fh.name
        try:
            with self.assertRaises(RP.RepairStatusError):
                RP.repair_status(_os.path.relpath(name, repo))
        finally:
            _os.unlink(name)


class R6NoSilentFallbackTests(SimpleTestCase):
    def test_black_planar_region_raises(self):
        frame = _declared(np.zeros((100, 100), dtype=np.float64))
        with self.assertRaises(TX.DegenerateRegionError):
            TX.measure_texture_axes(frame, _synthetic_region_idx())

    def test_black_grazing_region_raises(self):
        idx = _synthetic_region_idx()
        frame = np.zeros((100, 100), dtype=np.float64)
        flat = frame.ravel()
        flat[np.asarray(idx["PLANAR"])] = 0.5
        frame = _declared(flat.reshape(100, 100))
        with self.assertRaises(TX.DegenerateRegionError):
            TX.measure_texture_axes(frame, idx)

    def test_a_live_frame_measures_without_fallbacks(self):
        rng = np.random.default_rng(3)
        frame = _declared(rng.uniform(0.3, 0.7, (100, 100)))
        axes = TX.measure_texture_axes(frame, _synthetic_region_idx())
        self.assertEqual(sorted(axes), ["GRANULARITY_INDEX",
                                        "GRAZING_BAND_CONTRAST",
                                        "_provenance"])
        self.assertGreater(axes["GRANULARITY_INDEX"], 0.0)


class A559ProvenanceRefusalTests(SimpleTestCase):
    """3aa — the refusal DEMONSTRATED, not asserted.

    A guard reported present but never seen firing is a recurring shape
    in this arc: a shadowed __post_init__ made a route guard dead code
    twice, and both refusal probes printed NO REFUSAL — UNPROVEN. Each
    test below constructs a call in which provenance cannot be
    assembled and shows the raise.

    NOT VACUOUS, by construction rather than by claim:
      · the completeness loop is over PROVENANCE_REQUIRED_KEYS, a fixed
        6-tuple literal, so it cannot iterate zero times;
      · the per-frame loop is over FRAME_IDENTITY_FIELDS, a fixed
        4-tuple, and rejects absent AND present-but-None alike;
      · the mask loop is over PROVENANCE_REGIONS, a fixed 2-tuple, and
        a missing region RAISES rather than shortening the loop —
        test_a_missing_region_raises_rather_than_skipping proves the
        difference, which is the one a shorter loop would hide.
    """

    def test_the_fixed_tuples_are_non_empty(self):
        # if any of these were empty the loops above would pass
        # vacuously and every test in this class would be theatre
        self.assertEqual(len(TX.PROVENANCE_REQUIRED_KEYS), 6)
        self.assertEqual(len(TX.FRAME_IDENTITY_FIELDS), 4)
        self.assertEqual(TX.PROVENANCE_REGIONS, ("PLANAR", "GRAZING"))
        self.assertTrue(TX.TEXTURE_AXES)

    def test_a_bare_array_cannot_be_measured(self):
        """The defect the four marked cells took: a number computed
        from an array nobody recorded the origin of."""
        rng = np.random.default_rng(11)
        bare = rng.uniform(0.3, 0.7, (100, 100))
        with self.assertRaises(TX.ProvenanceIncompleteError):
            TX.measure_texture_axes(bare, _synthetic_region_idx())

    def test_a_frame_with_no_family_cannot_be_measured(self):
        """load_scene_linear's family/seed are keyword-optional; the
        MEASUREMENT is where that becomes a refusal."""
        rng = np.random.default_rng(12)
        frame = TX.provenanced_frame(
            rng.uniform(0.3, 0.7, (100, 100)), path="<synthetic>",
            family=None, seed=0, source_kind="IN_MEMORY_SYNTHETIC")
        with self.assertRaises(TX.ProvenanceIncompleteError):
            TX.measure_texture_axes(frame, _synthetic_region_idx())

    def test_a_frame_with_no_seed_cannot_be_measured(self):
        rng = np.random.default_rng(13)
        frame = TX.provenanced_frame(
            rng.uniform(0.3, 0.7, (100, 100)), path="<synthetic>",
            family="SYNTHETIC", seed=None,
            source_kind="IN_MEMORY_SYNTHETIC")
        with self.assertRaises(TX.ProvenanceIncompleteError):
            TX.measure_texture_axes(frame, _synthetic_region_idx())

    def test_a_missing_region_raises_rather_than_skipping(self):
        rng = np.random.default_rng(14)
        frame = _declared(rng.uniform(0.3, 0.7, (100, 100)))
        idx = _synthetic_region_idx()
        del idx["GRAZING"]
        with self.assertRaises(TX.ProvenanceIncompleteError):
            TX.measure_texture_axes(frame, idx)

    def test_an_empty_region_mask_raises(self):
        rng = np.random.default_rng(15)
        frame = _declared(rng.uniform(0.3, 0.7, (100, 100)))
        idx = _synthetic_region_idx()
        idx["GRAZING"] = []
        with self.assertRaises(TX.ProvenanceIncompleteError):
            TX.measure_texture_axes(frame, idx)

    def test_an_axis_without_a_named_denominator_raises(self):
        """(e) — an axis whose divisor is unstated cannot publish. The
        register's own class ten: DETERMINED_IN_FACT_NOT_IN_LAW."""
        rng = np.random.default_rng(16)
        frame = _declared(rng.uniform(0.3, 0.7, (100, 100)))
        original = dict(TX.AXIS_DENOMINATORS)
        try:
            del TX.AXIS_DENOMINATORS["GRANULARITY_INDEX"]
            with self.assertRaises(TX.ProvenanceIncompleteError):
                TX.measure_texture_axes(frame, _synthetic_region_idx())
        finally:
            TX.AXIS_DENOMINATORS.clear()
            TX.AXIS_DENOMINATORS.update(original)

    def test_a_measurement_that_succeeds_carries_a_b_c_d_e(self):
        rng = np.random.default_rng(17)
        frame = _declared(rng.uniform(0.3, 0.7, (100, 100)))
        block = TX.measure_texture_axes(
            frame, _synthetic_region_idx())["_provenance"]
        for key in TX.PROVENANCE_REQUIRED_KEYS:
            self.assertIn(key, block)
            self.assertTrue(block[key])
        ident = block["frame_identities"][0]
        for field in TX.FRAME_IDENTITY_FIELDS:
            self.assertIsNotNone(ident[field])
        self.assertEqual(ident["source_kind"], "IN_MEMORY_SYNTHETIC")
        self.assertEqual(ident["region_alignment"], "NOT_ASSERTED")
        self.assertEqual(len(block["derivation_code_digest"]), 16)
        self.assertEqual(block["alignment_tolerance"],
                         TX.ALIGNMENT_TOLERANCE)

    def test_the_code_digest_tracks_the_file_on_disk(self):
        """(c) is read from disk per call, not cached at import: a
        derivation edited mid-session cannot publish under its old
        digest."""
        import hashlib
        import pathlib
        src = pathlib.Path(TX.__file__).with_suffix(".py")
        self.assertEqual(
            TX._derivation_code_digest(),
            hashlib.sha256(src.read_bytes()).hexdigest()[:16])

    def test_the_pixel_digest_is_of_content_not_of_the_path(self):
        rng = np.random.default_rng(18)
        arr = rng.uniform(0.3, 0.7, (40, 40))
        same = TX.provenanced_frame(arr, path="<a>", family="F", seed=1,
                                    source_kind="IN_MEMORY_SYNTHETIC")
        other = TX.provenanced_frame(arr, path="<b>", family="F", seed=1,
                                     source_kind="IN_MEMORY_SYNTHETIC")
        self.assertEqual(same.frame_identity["pixel_digest"],
                         other.frame_identity["pixel_digest"])
        moved = TX.provenanced_frame(arr + 1e-9, path="<a>", family="F",
                                     seed=1,
                                     source_kind="IN_MEMORY_SYNTHETIC")
        self.assertNotEqual(same.frame_identity["pixel_digest"],
                            moved.frame_identity["pixel_digest"])
