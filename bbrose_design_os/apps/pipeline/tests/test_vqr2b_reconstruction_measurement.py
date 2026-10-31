"""Verified reconstruction resolution, real mask refusals and changed-renderer calibration guards."""
import json
from pathlib import Path

import pytest

from apps.pipeline.services import concept_analysis as ca
from apps.pipeline.services import visual_quality_gate as vqg
from apps.pipeline.services import vqr2b_reconstruction_measurement as v


def _rasterise_clean(*args, **kwargs):
    """v.rasterise, with its page raster's folder removed once the record is read — the record keeps the numbers
    (the clean-up of 2026-10-04: each run left two vqr2b_* folders in the temp folder)."""
    import os
    import shutil
    record = v.rasterise(*args, **kwargs)
    shutil.rmtree(os.path.dirname(record["png_path"]), ignore_errors=True)
    return record

REPO = Path(__file__).resolve().parents[3]
#: real committed emissions, chosen because they exercise both outcomes
BIG_AI = REPO / "docs/visual_quality/vq1_corr5/vq1_corr5_p1_bulb.ai"
SMALL_AI = REPO / "docs/roadmap/palt_m7/ai_emission/es3083_lid_C3.ai"
BIG_ARTBOARD_MM = (420, 236)  # measured PDF MediaBox, not an assumed A4 page


@pytest.fixture(scope="module")
def measured():
    return v.measure_reconstruction(str(BIG_AI), requested_dpi=150,
                                    artboard_mm=BIG_ARTBOARD_MM)


@pytest.fixture(scope="module")
def measured_premise():
    return v.measure_round_trip_floor(str(BIG_AI), requested_dpi=150, artboard_mm=BIG_ARTBOARD_MM)


def _controlled_raster(monkeypatch, tmp_path, image):
    folder = tmp_path / "controlled_raster"
    folder.mkdir()
    path = folder / "page.png"
    image.save(path)
    monkeypatch.setattr(v, "rasterise", lambda *a, **kw: {
        "png_path": str(path), "pixel_size": list(image.size), "requested_dpi": kw["requested_dpi"],
        "source": {"path": "controlled fixture", "sha256": "synthetic"}})


class TestTheRasteriserIsMeasuredNotTrusted:
    def test_capability_is_probed_not_assumed(self):
        cap = v.rasteriser_capability()
        assert set(cap) >= {"pymupdf", "sips", "pdftoppm", "dpi_argument_honoured"}
        assert cap["selected_backend"] == v.acting_rasteriser()
        assert cap["dpi_argument_honoured"] == (v.acting_rasteriser() != v.RASTERISER_NONE)

    def test_requested_dpi_is_recorded_as_requested_not_as_achieved(self, measured):
        raster = measured["raster"]
        assert raster["requested_dpi"] == 150
        assert raster["effective_dpi"] == pytest.approx(150, abs=1)
        assert raster["requested_dpi_achieved"] is True

    def test_requested_dpi_scales_the_verified_raster(self):
        sizes = {dpi: tuple(_rasterise_clean(str(SMALL_AI), requested_dpi=dpi,
                                           artboard_mm=(65, 65))["pixel_size"]) for dpi in (72, 300)}
        assert sizes[72] != sizes[300]
        for dimension in range(2):
            assert sizes[300][dimension] == pytest.approx(65 / 25.4 * 300, abs=1)
            assert sizes[72][dimension] == pytest.approx(65 / 25.4 * 72, abs=1)


class TestResolutionIsAPreconditionNotAFootnote:
    def test_an_under_resolved_source_refuses_rather_than_interpolating(self, monkeypatch, tmp_path):
        from PIL import Image, ImageDraw
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((48, 20, 79, 82), fill=(20, 40, 70, 255))
        _controlled_raster(monkeypatch, tmp_path, image)
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.measure_reconstruction("controlled", requested_dpi=150)
        assert e.value.findings[0].startswith(v.VQR2B_RESOLUTION_TOO_LOW)
        assert "63px < 64 samples" in e.value.findings[0]
        assert "invent resolution" in e.value.findings[0]

    def test_the_floor_is_the_sample_count(self):
        assert v.MIN_SILHOUETTE_PX == ca.PARAMS["profile_samples"] == 64

    def test_a_resolvable_source_measures_and_records_its_resolution(
            self, measured):
        assert measured["silhouette_height_px"] >= v.MIN_SILHOUETTE_PX
        assert measured["measurement"]["contour"]["samples"] == 64
        assert measured["raster"]["pixel_size"][0] > 0

    def test_missing_source_refuses(self, tmp_path):
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.measure_reconstruction(str(tmp_path / "nope.ai"), requested_dpi=150)
        assert e.value.findings[0].startswith(v.VQR2B_SOURCE_MISSING)

    def test_an_unresolvable_mask_refuses_rather_than_measuring_zero(self, monkeypatch, tmp_path):
        from PIL import Image, ImageDraw
        image = Image.new("RGB", (128, 128), "white")
        ImageDraw.Draw(image).rectangle((0, 0, 63, 127), fill="black")
        _controlled_raster(monkeypatch, tmp_path, image)
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.measure_reconstruction("controlled", requested_dpi=150)
        assert e.value.findings[0].startswith(v.VQR2B_MASK_UNRESOLVABLE)


class TestTheSilhouetteTruthIsShared:
    def test_the_sampler_is_imported_not_reimplemented(self):
        assert v.measure_mask is ca.measure_mask
        assert v.CONCEPT_PARAMS is ca.PARAMS

    def test_the_module_defines_no_second_profile(self):
        src = (REPO / "apps/pipeline/services/"
               "vqr2b_reconstruction_measurement.py").read_text()
        assert "def measure_mask" not in src

    def test_a_non_shared_measurement_refuses(self, measured, measured_premise):
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.compare_to_concept(
                measured, {"contour": {"representation": "hand_rolled/9.9"}}, premise=measured_premise)
        assert e.value.findings[0].startswith(
            v.VQR2B_CONCEPT_MEASUREMENT_INVALID)


class TestTheComparisonAndItsNoiseFloor:
    def test_the_pipeline_is_deterministic(self, measured_premise):
        """The instrument's own noise floor for R2b. Unlike RBV-5 — where
        vector fit and raster are different representations and the floor
        is 0.0100 — rasterise/mask/measure of the SAME file reproduces
        exactly, so a deviation in a real comparison is attributable to
        the artwork. Determinism is not accuracy: this says the
        measurement repeats, not that it is correct."""
        a = v.measure_reconstruction(str(BIG_AI), requested_dpi=150, artboard_mm=BIG_ARTBOARD_MM)
        b = v.measure_reconstruction(str(BIG_AI), requested_dpi=150, artboard_mm=BIG_ARTBOARD_MM)
        cmp = v.compare_to_concept(a, b["measurement"], premise=measured_premise)
        assert cmp["mean_abs_deviation"] == 0.0
        assert cmp["max_abs_deviation"] == 0.0

    def test_threshold_is_owner_calibrated_by_its_own_reasoning(self,
                                                                measured, measured_premise):
        """§U2. Same VALUE as RBV-5's profile threshold, different
        STATEMENT — and the file must not borrow §T1's reasoning."""
        cmp = v.compare_to_concept(measured, measured["measurement"], premise=measured_premise)
        assert cmp["threshold_status"] == "OWNER_CALIBRATED"
        assert cmp["binding_statistic"] == "mean_abs_deviation"
        prov = cmp["threshold_provenance"]
        assert "§U2" in prov
        # §U2a: the floor is 0.0, so this clears NO noise. The "3x the
        # measured floor" sentence belongs to §T1 and would be false here.
        assert "clears NO" in prov
        assert "NOT '3x a floor'" in prov
        assert "3x the measured floor" not in prov

    def test_the_premise_is_guarded_the_floor_is_still_exactly_zero(self, measured_premise):
        """§U2b. The §T1 inverted guard cannot apply — there is no noise
        to sit above. What must be guarded is the PREMISE: if the
        self-comparison ever stops reproducing exactly, the instrument has
        changed and this ruling is void."""
        a = v.measure_reconstruction(str(BIG_AI), requested_dpi=150,
                                     artboard_mm=BIG_ARTBOARD_MM)
        b = v.measure_reconstruction(str(BIG_AI), requested_dpi=150,
                                     artboard_mm=BIG_ARTBOARD_MM)
        cmp = v.compare_to_concept(a, b["measurement"], premise=measured_premise)
        assert cmp["mean_abs_deviation"] == 0.0, (
            "the R2b instrument no longer reproduces exactly — §U2's "
            "premise (floor 0.0, so the tolerance clears no noise) is "
            "void and the calibration needs a fresh ruling")
        assert cmp["max_abs_deviation"] == 0.0
        assert v.MEASURED_FLOOR == 0.0
        assert cmp["measured_floor"] == 0.0

    def test_every_verdict_names_its_instrument(self, measured, measured_premise):
        """§V4c. A result that cannot name its instrument is not a
        measurement."""
        cmp = v.compare_to_concept(measured, measured["measurement"], premise=measured_premise)
        inst = cmp["instrument"]
        assert inst["acting_rasteriser"] in ("pymupdf", "pdftoppm")
        assert inst["acting_floor_status"] == "MEASURED_THIS_RUN"
        assert inst["calibrated_against"] == v.U2_CALIBRATED_RASTERISER
        assert inst["calibrated_floor"] == v.MEASURED_FLOOR

    def test_the_acting_rasteriser_is_which_one_runs_not_which_exist(self, monkeypatch):
        from apps.ire import pdf_raster
        for pymupdf, poppler, expected in ((True, True, "pymupdf"), (False, True, "pdftoppm"), (False, False, v.RASTERISER_NONE)):
            monkeypatch.setattr(pdf_raster, "probe_backends", lambda: [
                {"backend": "pymupdf", "available": pymupdf, "explicit_dpi_claimed": True},
                {"backend": "pdftoppm", "available": poppler, "explicit_dpi_claimed": True},
                {"backend": "sips", "available": True, "explicit_dpi_claimed": False}])
            assert v.acting_rasteriser() == expected
            assert v.rasteriser_capability()["dpi_argument_honoured"] is (expected != v.RASTERISER_NONE)

    def test_a_changed_instrument_is_flagged_not_absorbed(self,
                                                          monkeypatch):
        """§V4b NEGATIVE CONTROL. If the acting instrument is not the one
        §U2 was calibrated against, the record must SAY the calibration no
        longer matches — it is not quietly re-derived in the file."""
        monkeypatch.setattr(v, "acting_rasteriser", lambda: "pdftoppm")
        inst = v.instrument_record()
        assert inst["instrument_matches_calibration"] is False
        assert "void by its own terms" in inst["rule"]

    def test_verified_backend_does_not_inherit_sips_calibration(self, measured):
        inst = v.instrument_record()
        assert inst["acting_rasteriser"] in ("pymupdf", "pdftoppm")
        assert inst["instrument_matches_calibration"] is False
        assert inst["acting_rasteriser_floor"] is None
        assert inst["acting_floor_status"] == "UNMEASURED"
        with pytest.raises(v.Vqr2bRefusal) as caught:
            v.compare_to_concept(measured, measured["measurement"])
        assert caught.value.findings[0].startswith(v.VQR2B_PREMISE_GUARD_NOT_RE_RUN)

    def test_the_comparison_carries_its_resolution_evidence(self, measured, measured_premise):
        cmp = v.compare_to_concept(measured, measured["measurement"], premise=measured_premise)
        res = cmp["resolution"]
        assert res["silhouette_height_px"] >= 64
        assert "requested_dpi_achieved" in res
        assert "quantisation_warning" in res

    def test_mismatched_sample_counts_refuse(self, measured, measured_premise):
        bad = json.loads(json.dumps(measured["measurement"]))
        bad["contour"]["width_profile"] = [0.5] * 32
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.compare_to_concept(measured, bad, premise=measured_premise)
        assert e.value.findings[0].startswith(
            v.VQR2B_PROFILE_LENGTH_MISMATCH)


class TestThePremiseGuardRunsBeforeTheVerdict:
    """§V4(a) — "the instrument is measured before it measures anything."

    The guard used to exist only as the test above, which is a guard on
    the machine the suite happens to run on and not on the instrument that
    produces a verdict. Worse, the poppler test SKIPS once poppler is
    installed, so the guard went quiet at exactly the moment §V4 was
    written for. These exercise the changed-instrument path by monkeypatch
    so they run on THIS machine, today, with sips.
    """

    def test_the_guard_measures_the_floor_rather_than_asserting_it(self):
        """It rasterises twice and reports the distance. A guard that
        returned MEASURED_FLOOR would be restating the premise it exists
        to check."""
        rec = v.measure_round_trip_floor(str(BIG_AI), requested_dpi=150,
                                         artboard_mm=BIG_ARTBOARD_MM)
        assert rec["rasteriser"] == v.acting_rasteriser()
        assert rec["measured_floor"] == 0.0
        assert rec["max_abs_deviation"] == 0.0
        assert rec["premise_holds"] is True
        # it really rasterised the file it says it did
        assert rec["source"]["sha256"] == v._sha256(str(BIG_AI))

    def test_the_guard_reports_what_it_measured_not_what_it_expected(
            self, monkeypatch):
        """The decisive one, because 0.0 is also the constant. A guard
        that returned ``MEASURED_FLOOR`` would agree with the premise on
        every machine forever — including the machine where the premise
        has just stopped being true. Injecting a deviation proves the
        answer flows from the measurement."""
        monkeypatch.setattr(v, "_profile_deviation",
                            lambda a, b: (0.0071, 0.0212, []))
        rec = v.measure_round_trip_floor(str(BIG_AI), requested_dpi=150,
                                         artboard_mm=BIG_ARTBOARD_MM)
        assert rec["measured_floor"] == 0.0071
        assert rec["max_abs_deviation"] == 0.0212
        assert rec["premise_holds"] is False

    def test_an_unguarded_changed_instrument_produces_no_verdict(
            self, measured, monkeypatch):
        """§V4a. Not a warning field on a verdict — no verdict at all.
        §U2's 0.03 is only meaningful over a floor of 0.0, and that 0.0
        belongs to sips."""
        monkeypatch.setattr(v, "acting_rasteriser", lambda: "pdftoppm")
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.compare_to_concept(measured, measured["measurement"])
        assert e.value.findings[0].startswith(v.VQR2B_PREMISE_GUARD_NOT_RE_RUN)
        assert "UNMEASURED" in e.value.findings[0]

    def test_a_re_run_guard_that_holds_lets_the_verdict_through(
            self, measured, monkeypatch):
        """The refusal above must be about the MISSING guard and not a
        blanket refusal of any instrument that is not sips — otherwise
        §V4's whole premise (poppler MAY be installed) is denied."""
        monkeypatch.setattr(v, "acting_rasteriser", lambda: "pdftoppm")
        premise = {"rasteriser": "pdftoppm", "measured_floor": 0.0,
                   "premise_holds": True}
        cmp = v.compare_to_concept(measured, measured["measurement"],
                                   premise=premise)
        assert cmp["within_threshold"] is True
        assert cmp["instrument"]["acting_floor_status"] == "MEASURED_THIS_RUN"
        assert cmp["premise_guard"] is premise

    def test_a_moved_floor_voids_u2_and_does_not_re_derive_the_threshold(
            self, measured, monkeypatch):
        """§V4b. The owner's number does not move to accommodate a worse
        instrument — the ruling goes back to the owner instead."""
        monkeypatch.setattr(v, "acting_rasteriser", lambda: "pdftoppm")
        premise = {"rasteriser": "pdftoppm", "measured_floor": 0.004,
                   "premise_holds": False}
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.compare_to_concept(measured, measured["measurement"],
                                 premise=premise)
        assert e.value.findings[0].startswith(v.VQR2B_U2_VOID_FLOOR_CHANGED)
        assert "returns to the owner" in e.value.findings[0]
        assert v.PROFILE_DEVIATION_THRESHOLD == 0.03
        assert v.MEASURED_FLOOR == 0.0

    def test_a_guard_run_on_a_different_instrument_is_not_accepted(
            self, measured, monkeypatch):
        """A sips guard does not vouch for pdftoppm. Accepting it would
        make the guard a formality satisfiable by any record at all."""
        monkeypatch.setattr(v, "acting_rasteriser", lambda: "pdftoppm")
        premise = {"rasteriser": "sips", "measured_floor": 0.0,
                   "premise_holds": True}
        with pytest.raises(v.Vqr2bRefusal) as e:
            v.compare_to_concept(measured, measured["measurement"],
                                 premise=premise)
        assert e.value.findings[0].startswith(v.VQR2B_PREMISE_GUARD_NOT_RE_RUN)
        assert "different instrument" in e.value.findings[0]

    def test_the_record_never_presents_the_sips_floor_as_the_acting_one(
            self, monkeypatch):
        """§V4c asks for THAT rasteriser's measured floor. The record used
        to answer with the sips constant unconditionally while its
        docstring said the floor was 'the one MEASURED for the acting
        instrument' — a claim the code did not carry."""
        monkeypatch.setattr(v, "acting_rasteriser", lambda: "pdftoppm")
        inst = v.instrument_record()
        assert inst["acting_rasteriser_floor"] is None
        assert inst["acting_floor_status"] == "UNMEASURED"
        # the calibrated floor is still reported, under its own name
        assert inst["calibrated_floor"] == v.MEASURED_FLOOR

    def test_on_the_calibrated_instrument_the_floor_is_the_measured_one(self, monkeypatch):
        monkeypatch.setattr(v, "acting_rasteriser", lambda: v.U2_CALIBRATED_RASTERISER)
        inst = v.instrument_record()
        assert inst["acting_floor_status"] == "MEASURED_AT_CALIBRATION"
        assert inst["acting_rasteriser_floor"] == v.MEASURED_FLOOR

    def test_the_floor_and_the_verdict_share_one_arithmetic(self):
        """A second deviation implementation would let the floor and the
        comparison disagree about what deviation means, which is the one
        thing §U2 rests on."""
        src = (REPO / "apps/pipeline/services/"
               "vqr2b_reconstruction_measurement.py").read_text()
        assert src.count("sum(diffs) / len(diffs)") == 1


class TestSilhouetteFidelityFlips:
    """The axis was UNMEASURED by construction. With a comparison
    persisted it becomes a real verdict — and an under-resolved
    comparison is still not a pass."""

    PROFILE = {"width_mm": 37.4, "height_mm": 114.3}

    def _axis(self, comparison):
        return vqg._silhouette_axis(
            {"reconstruction_silhouette": comparison}, self.PROFILE)

    def _cmp(self, **over):
        base = {
            "schema": "reconstruction_silhouette_measurement/1.0",
            "binding_statistic": "mean_abs_deviation",
            "mean_abs_deviation": 0.01, "max_abs_deviation": 0.09,
            "threshold": 0.03,
            "threshold_status": "PROVISIONAL_PENDING_OWNER_CALIBRATION",
            "within_threshold": True,
            "resolution": {"silhouette_height_px": 614,
                           "effective_dpi": 101.9, "requested_dpi": 150,
                           "requested_dpi_achieved": False,
                           "quantisation_warning": None},
        }
        base.update(over)
        return base

    def test_within_tolerance_is_a_real_pass(self):
        axis = self._axis(self._cmp())
        assert axis["state"] == vqg.PASS
        assert axis["measured"]["mean_abs_deviation"] == 0.01

    def test_beyond_tolerance_fails(self):
        axis = self._axis(self._cmp(within_threshold=False,
                                    mean_abs_deviation=0.2))
        assert axis["state"] == vqg.FAIL
        assert axis["code"] == vqg.VQ_SILHOUETTE_DIVERGENT

    def test_a_quantisation_dominated_comparison_is_not_a_pass(self):
        """The decisive one: a comparison can be 'within tolerance' and
        still mean nothing if the raster had too few rows per sample."""
        axis = self._axis(self._cmp(resolution={
            "silhouette_height_px": 70, "effective_dpi": 72.0,
            "requested_dpi": 150, "requested_dpi_achieved": False,
            "quantisation_warning": "quantisation-dominated"}))
        assert axis["state"] == vqg.UNMEASURED
        assert axis["state"] != vqg.PASS

    def test_without_a_comparison_the_axis_is_unchanged(self):
        """No regression: the pre-R2b behaviour still holds when nothing
        is persisted."""
        axis = vqg._silhouette_axis({}, self.PROFILE)
        assert axis["state"] == vqg.UNMEASURED
        assert axis["code"] == vqg.VQ_SILHOUETTE_COMPARISON_UNAVAILABLE

    def test_unmeasured_remains_blocking_in_the_combiner(self):
        axes = {n: {"state": vqg.PASS, "required": True, "reason": "ok"}
                for n in vqg.REQUIRED_AXES}
        axes["silhouette_fidelity"] = self._axis(self._cmp(resolution={
            "silhouette_height_px": 70, "effective_dpi": 72.0,
            "requested_dpi": 150, "requested_dpi_achieved": False,
            "quantisation_warning": "quantisation-dominated"}))
        combined = vqg.combine_axes(axes)
        # [§BH71 (0a), the owner's goal of 2026-09-28: it read overall FAIL — an unmeasured axis is a warning beside
        # Approve, never a block, and it still never reads PASS]
        assert combined["overall"] == vqg.UNMEASURED
        assert [w["axis"] for w in combined["acceptance_warnings"]] == ["silhouette_fidelity"]


def test_exactly_sixty_four_silhouette_rows_can_be_measured(monkeypatch, tmp_path):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((48, 20, 79, 83), fill=(20, 40, 70, 255))
    _controlled_raster(monkeypatch, tmp_path, image)
    measured = v.measure_reconstruction("controlled", requested_dpi=150)
    assert measured["silhouette_height_px"] == 64
    assert measured["measurement"]["contour"]["samples"] == 64
