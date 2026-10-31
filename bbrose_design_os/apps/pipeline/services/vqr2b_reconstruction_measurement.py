"""R2b — reconstruction silhouette measurement
(``reconstruction_silhouette_measurement/1.0``).

Supplies the concept-side + reconstruction-side comparison that
``visual_quality_gate._silhouette_axis`` has been waiting for, so
``silhouette_fidelity`` can stop being UNMEASURED-by-construction.

DISTINCT FROM RBV-5. RBV-5 compares a subject to a REAL BOTTLE (or to the
M3 canonical proportion bound). R2b compares a RECONSTRUCTION — the
emitted, PDF-compatible ``.ai`` — to the SELECTED CONCEPT's own mask. Same
shared sampler, different question.

ONE SILHOUETTE TRUTH. The 64-sample width-at-height profile is IMPORTED
from ``concept_analysis`` (``product_container_concept_analysis/1.0``),
never re-implemented, exactly as RBV-5 does.

THE RASTERISER IS THE LIMITING INSTRUMENT, AND IT LIES ABOUT ITS
RESOLUTION. ``rasterize.pdf_to_png`` takes a ``dpi`` argument, but on this
machine only the ``sips`` branch is available and that branch NEVER PASSES
``dpi`` to sips — ``pdftoppm``, which would honour it, is absent. Measured:
a 65mm artboard returns 184x184px for every requested dpi of 72, 150, 300
and 600 alike, i.e. a fixed native ~71.9 DPI. A measurement that recorded
the REQUESTED dpi would be recording a number that never happened, so this
module records the EFFECTIVE resolution it actually got and refuses when
that resolution cannot support the profile it is about to compute.

Pure apart from the rasteriser subprocess: no Django ORM, no provider
calls, no network.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile

from PIL import Image

from apps.pipeline.services.concept_analysis import (
    PARAMS as CONCEPT_PARAMS,
    SCHEMA as CONCEPT_SCHEMA,
    extract_mask,
    measure_mask,
)

SCHEMA = "reconstruction_silhouette_measurement/1.0"

#: A 64-sample profile over a silhouette shorter than 64 pixels invents
#: resolution: samples land on the same row and the curve is an artefact
#: of interpolation, not of the artwork. The floor is the sample count
#: itself — one row per sample, minimum.
MIN_SILHOUETTE_PX = CONCEPT_PARAMS["profile_samples"]

#: Comfortable floor: below this the profile exists but each sample rests
#: on very few rows, so the measurement is quantisation-dominated. Recorded
#: as a warning rather than a refusal — the caller decides.
COMFORTABLE_SILHOUETTE_PX = 4 * CONCEPT_PARAMS["profile_samples"]

#: §U2. Owner-calibrated at 0.03 — the same VALUE as RBV-5's profile
#: threshold and a completely different STATEMENT. The reasoning must not
#: be copied across, and §U2a says so explicitly.
#:
#: WHAT THIS BINDS: the MEAN absolute deviation across the shared
#: 64-sample max-width-normalised profile, comparing a RECONSTRUCTION to
#: its SELECTED CONCEPT.
#:
#: WHY IT CLEARS NO NOISE. RBV-5's floor is 0.0100 because it compares a
#: vector fit against a raster — two representations, so some divergence
#: is instrumental and a threshold has to clear it. R2b rasterises, masks
#: and measures the SAME file, and the round trip reproduces EXACTLY:
#: THE MEASURED FLOOR IS 0.0. There is no noise here to be 3x clear of,
#: and writing "3x the measured floor" in this file would be false.
#:
#: WHAT 0.03 THEREFORE MEANS: a pure design tolerance — a reconstruction
#: may drift up to ~3% mean deviation from its selected concept across
#: the 64-sample profile before it stops being that concept. Every
#: nonzero deviation R2b reports is attributable to the artwork, not to
#: the instrument.
#:
#: WHAT IT HAS NOT SEEN: 0.03 is calibrated against a self-comparison,
#: which by construction has never met a real emitted .ai. The first real
#: reconstruction-vs-concept comparison is an owner-review item. If honest
#: work fails at 0.03 that is a FINDING ABOUT THE TOLERANCE and it returns
#: to the owner; it is never fixed by widening this number (§U2c).
PROFILE_DEVIATION_THRESHOLD = 0.03
PROFILE_DEVIATION_STATISTIC = "mean_abs_deviation"
THRESHOLD_STATUS = "OWNER_CALIBRATED"
MEASURED_FLOOR = 0.0
#: §V4. WHICH instrument that floor was measured on. §U2's premise is not
#: "the floor is 0.0" in the abstract — it is "the floor is 0.0 on THIS
#: rasteriser". Changing the instrument re-opens the calibration.
U2_CALIBRATED_RASTERISER = "sips"
RASTERISER_NONE = "NONE_AVAILABLE"
THRESHOLD_PROVENANCE = (
    "OWNER_BLOCKER_CLEARANCE.md §U2, 2026-08-17 — mean absolute deviation "
    "over the shared 64-sample profile, reconstruction vs selected "
    "concept. The measured floor is EXACTLY 0.0 (rasterise/mask/measure of "
    "the same file reproduces bit-identically), so this number clears NO "
    "noise and is a pure design tolerance: a reconstruction may drift up "
    "to ~3% mean deviation from its concept before it stops being that "
    "concept. It is NOT '3x a floor' — that reasoning belongs to §T1 and "
    "would be false here. Never seen a real emitted .ai; a failure on "
    "honest work is a finding about the tolerance, not a licence to widen "
    "it.")

VQR2B_SOURCE_MISSING = "VQR2B_SOURCE_MISSING"
VQR2B_RASTERISATION_FAILED = "VQR2B_RASTERISATION_FAILED"
VQR2B_RESOLUTION_TOO_LOW = "VQR2B_RESOLUTION_TOO_LOW"
VQR2B_MASK_UNRESOLVABLE = "VQR2B_MASK_UNRESOLVABLE"
VQR2B_CONCEPT_MEASUREMENT_INVALID = "VQR2B_CONCEPT_MEASUREMENT_INVALID"
VQR2B_PROFILE_LENGTH_MISMATCH = "VQR2B_PROFILE_LENGTH_MISMATCH"
VQR2B_PREMISE_GUARD_NOT_RE_RUN = "VQR2B_PREMISE_GUARD_NOT_RE_RUN"
VQR2B_U2_VOID_FLOOR_CHANGED = "VQR2B_U2_VOID_FLOOR_CHANGED"


class Vqr2bRefusal(ValueError):
    """Fail-closed measurement refusal; ``findings`` lists exact codes."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__("; ".join(self.findings))


def _sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def acting_rasteriser() -> str:
    """Name the default verified renderer; a changed backend needs its own measured premise."""
    from apps.ire.pdf_raster import probe_backends
    for backend in probe_backends():
        if backend.get("available") and backend.get("explicit_dpi_claimed"):
            return backend["backend"]
    return RASTERISER_NONE


def instrument_record(premise: dict | None = None) -> dict:
    """The instrument, named and floor-stated, for stamping on a verdict.

    §V4(c) asks for THAT rasteriser's measured floor, which is not the same
    thing as the calibrated floor. ``MEASURED_FLOOR`` was measured on sips;
    on any other instrument it is an open question, and the honest answer
    to an open question is UNMEASURED, never the sips number wearing the
    acting instrument's name. Pass the record from
    ``measure_round_trip_floor`` to close it.
    """
    acting = acting_rasteriser()
    matches = acting == U2_CALIBRATED_RASTERISER
    if premise is not None and premise.get("rasteriser") == acting:
        acting_floor = premise.get("measured_floor")
        floor_status = "MEASURED_THIS_RUN"
    elif matches:
        acting_floor = MEASURED_FLOOR
        floor_status = "MEASURED_AT_CALIBRATION"
    else:
        acting_floor = None
        floor_status = "UNMEASURED"
    return {
        "acting_rasteriser": acting,
        "calibrated_against": U2_CALIBRATED_RASTERISER,
        "calibrated_floor": MEASURED_FLOOR,
        "acting_rasteriser_floor": acting_floor,
        "acting_floor_status": floor_status,
        "instrument_matches_calibration": matches,
        "capability": rasteriser_capability(),
        "rule": ("§V4c — a result that cannot name its instrument is not a "
                 "measurement; §V4b — if this instrument's measured floor "
                 "is not the calibrated floor, §U2 is void by its own "
                 "terms and the threshold returns to the owner"),
    }


def _profile_deviation(a: list, b: list) -> tuple:
    """``(mean, max, per_sample)`` absolute deviation between two profiles.

    One arithmetic, two callers — the premise guard and the verdict. A
    second copy would let the floor and the comparison disagree about what
    deviation means, which is the one thing §U2 rests on.
    """
    diffs = [abs(x - y) for x, y in zip(a, b)]
    return (round(sum(diffs) / len(diffs), 4), round(max(diffs), 4),
            [round(d, 4) for d in diffs])


def measure_round_trip_floor(ai_path: str, *, requested_dpi: int,
                             artboard_mm: tuple | None = None) -> dict:
    """§V4(a). MEASURE this machine's round-trip floor rather than assume it.

    Rasterise, mask and measure the SAME file twice and report how far the
    two answers sit apart. §U2's tolerance rests on that distance being
    exactly 0.0 — "the tolerance clears no noise" is a claim about the
    instrument, and it was only ever measured on sips.

    This lives in the service and not in the test that first measured it
    because §V4(a) requires the guard re-run BEFORE a verdict, and a
    verdict cannot re-run a test. It reports; it does not adjudicate. If
    the floor has moved, §U2 is void by its own terms and the threshold
    returns to the owner (§V4b) — this function will not re-derive it.
    """
    a = measure_reconstruction(ai_path, requested_dpi=requested_dpi,
                               artboard_mm=artboard_mm)
    b = measure_reconstruction(ai_path, requested_dpi=requested_dpi,
                               artboard_mm=artboard_mm)
    mean_dev, max_dev, _ = _profile_deviation(
        _profile_of(a["measurement"], "round_trip_a"),
        _profile_of(b["measurement"], "round_trip_b"))
    holds = mean_dev == MEASURED_FLOOR and max_dev == MEASURED_FLOOR
    return {
        "schema": SCHEMA,
        "guard": "§U2 premise — the round trip reproduces exactly",
        "rasteriser": acting_rasteriser(),
        "capability": rasteriser_capability(),
        "measured_floor": mean_dev,
        "max_abs_deviation": max_dev,
        "calibrated_floor": MEASURED_FLOOR,
        "premise_holds": holds,
        "source": a["raster"]["source"],
        "requested_dpi": requested_dpi,
        "effective_dpi": a["raster"].get("effective_dpi"),
        "consequence_if_false": (
            "§V4b — §U2 is void by its own terms and PROFILE_DEVIATION_"
            "THRESHOLD returns to the owner for recalibration against the "
            "new floor; it is not quietly re-derived in this file"),
    }


def rasteriser_capability() -> dict:
    """Report available backends and the verified renderer's explicit DPI contract."""
    from apps.ire.pdf_raster import probe_backends
    backends = probe_backends()
    selected = acting_rasteriser()
    available = {b["backend"]: bool(b.get("available")) for b in backends}
    return {**available, "cairosvg": bool(shutil.which("cairosvg")),
            "selected_backend": selected,
            "dpi_argument_honoured": selected != RASTERISER_NONE,
            "note": "Successful pdf_to_png renders verify actual pixel dimensions against the PDF page box at the requested DPI. A chosen renderer failure is not replaced by an unverified sips render."}


def rasterise(ai_path: str, *, requested_dpi: int,
              artboard_mm: tuple | None = None) -> dict:
    """Rasterise a PDF-compatible ``.ai`` and MEASURE what came back.

    ``requested_dpi`` has NO DEFAULT deliberately. A default here would be
    every caller must state the requested sampling resolution. Successful
    rendering verifies pixel dimensions; this record still distinguishes
    the request from its measured effective resolution.
    """
    from apps.ire.rasterize import pdf_to_png

    if not os.path.isfile(ai_path):
        raise Vqr2bRefusal([f"{VQR2B_SOURCE_MISSING}:{ai_path}"])
    tmp = tempfile.mkdtemp(prefix="vqr2b_")
    out = os.path.join(tmp, "page.png")
    if not pdf_to_png(ai_path, out, dpi=requested_dpi) \
            or not os.path.isfile(out):
        shutil.rmtree(tmp, ignore_errors=True)
        raise Vqr2bRefusal([f"{VQR2B_RASTERISATION_FAILED}:{ai_path}"])
    with Image.open(out) as img:
        size = list(img.size)
    record = {
        "png_path": out,
        "pixel_size": size,
        "requested_dpi": requested_dpi,
        "capability": rasteriser_capability(),
        "source": {"path": ai_path, "sha256": _sha256(ai_path)},
    }
    if artboard_mm:
        w_mm, h_mm = artboard_mm
        if w_mm:
            px_per_mm = size[0] / float(w_mm)
            record["artboard_mm"] = [w_mm, h_mm]
            record["px_per_mm"] = round(px_per_mm, 4)
            record["effective_dpi"] = round(px_per_mm * 25.4, 1)
            record["requested_dpi_achieved"] = (
                abs(record["effective_dpi"] - requested_dpi) <= 1.0)
    return record


def measure_reconstruction(ai_path: str, *, requested_dpi: int,
                           artboard_mm: tuple | None = None) -> dict:
    """Rasterise, mask, and measure a reconstruction with the SHARED
    sampler — refusing when the raster cannot support the measurement."""
    raster = rasterise(ai_path, requested_dpi=requested_dpi,
                       artboard_mm=artboard_mm)
    try:
        with Image.open(raster["png_path"]) as img:
            mask, _, _, _ = extract_mask(img)
    finally:
        # the record keeps no png_path (below), so the page raster's folder goes now (the clean-up of 2026-10-04:
        # 7,072 vqr2b_* folders were left in the temp folder)
        shutil.rmtree(os.path.dirname(raster["png_path"]), ignore_errors=True)
    # extract_mask returns None when it cannot separate a subject from the
    # background — measured on real emissions, not hypothetical. Refusing
    # beats treating "no subject found" as "subject of size zero".
    if mask is None or not mask.any():
        raise Vqr2bRefusal([
            f"{VQR2B_MASK_UNRESOLVABLE}:{ai_path}:"
            f"{'extract_mask returned no mask' if mask is None else 'mask is empty'}"])

    ys = mask.any(axis=1).nonzero()[0]
    silhouette_px = int(ys.max() - ys.min() + 1)
    if silhouette_px < MIN_SILHOUETTE_PX:
        # refusing beats returning a 64-sample curve interpolated from
        # fewer than 64 rows — that curve would be an artefact of the
        # sampler, presented as a property of the artwork
        raise Vqr2bRefusal([
            f"{VQR2B_RESOLUTION_TOO_LOW}:silhouette {silhouette_px}px < "
            f"{MIN_SILHOUETTE_PX} samples; the profile would invent "
            f"resolution the raster does not carry"])

    measurement = measure_mask(mask)
    return {
        "schema": SCHEMA,
        "raster": {k: v for k, v in raster.items() if k != "png_path"},
        "silhouette_height_px": silhouette_px,
        "quantisation_warning": (
            None if silhouette_px >= COMFORTABLE_SILHOUETTE_PX else
            f"silhouette {silhouette_px}px gives "
            f"{silhouette_px / MIN_SILHOUETTE_PX:.1f} rows per sample; the "
            "profile is quantisation-dominated and small deviations are "
            "not meaningful"),
        "shared_measurement": {
            "schema": CONCEPT_SCHEMA,
            "function": "concept_analysis.measure_mask",
            "profile_samples": CONCEPT_PARAMS["profile_samples"],
            "note": ("imported, never re-implemented — a second profile "
                     "implementation would be a second silhouette truth"),
        },
        "measurement": measurement,
    }


def _profile_of(measurement: dict, label: str) -> list:
    contour = (measurement or {}).get("contour") or {}
    if contour.get("representation") != "width_at_height_profile/1.0":
        raise Vqr2bRefusal([
            f"{VQR2B_CONCEPT_MEASUREMENT_INVALID}:{label}:"
            f"representation={contour.get('representation')}"])
    return contour["width_profile"]


def _guard_the_premise(premise: dict | None) -> dict:
    """§V4(a) — no verdict before the guard has been re-run on the acting
    instrument. Returns the instrument record, or refuses.

    Two ways to fail, and neither is absorbed. The instrument changed and
    nobody measured its floor: there is no verdict to give, because §U2's
    tolerance is only meaningful over a floor of 0.0 and that number
    belongs to sips. Or the guard ran and the floor MOVED: §U2 is void by
    its own terms (§V4b) and the threshold goes back to the owner — this
    module will not widen it, re-derive it, or quietly carry on.
    """
    inst = instrument_record(premise)
    acting = inst["acting_rasteriser"]
    if premise is not None and premise.get("rasteriser") != acting:
        raise Vqr2bRefusal([
            f"{VQR2B_PREMISE_GUARD_NOT_RE_RUN}:guard_ran_on="
            f"{premise.get('rasteriser')}:acting={acting}; §V4a — the "
            f"premise was guarded on a different instrument than the one "
            f"about to produce this verdict"])
    if premise is None and not inst["instrument_matches_calibration"]:
        raise Vqr2bRefusal([
            f"{VQR2B_PREMISE_GUARD_NOT_RE_RUN}:acting={acting}:"
            f"calibrated_against={U2_CALIBRATED_RASTERISER}; §V4a — the "
            f"§U2 premise guard has not been re-run on this instrument, so "
            f"its round-trip floor is UNMEASURED and no comparison may "
            f"produce a verdict. Run measure_round_trip_floor() and pass "
            f"the result as premise="])
    if premise is not None and not premise.get("premise_holds"):
        raise Vqr2bRefusal([
            f"{VQR2B_U2_VOID_FLOOR_CHANGED}:acting={acting}:measured_floor="
            f"{premise.get('measured_floor')}:calibrated_floor="
            f"{MEASURED_FLOOR}; §V4b — §U2 is void by its own terms. The "
            f"threshold returns to the owner for recalibration against the "
            f"new floor; it is not re-derived here"])
    return inst


def compare_to_concept(reconstruction: dict, concept_measurement: dict, *,
                       threshold: float = PROFILE_DEVIATION_THRESHOLD,
                       premise: dict | None = None) -> dict:
    """Compare a reconstruction's silhouette to the SELECTED CONCEPT's.

    Both sides come from ``measure_mask``, so both profiles are 64-sample
    and max-width-normalised; that is asserted rather than assumed.

    ``premise`` is a ``measure_round_trip_floor`` record. It is OPTIONAL
    only while the acting instrument is the one §U2 was calibrated on —
    §V4(a) makes it mandatory the moment that changes.
    """
    instrument = _guard_the_premise(premise)
    recon_profile = _profile_of(reconstruction.get("measurement"),
                                "reconstruction")
    concept_profile = _profile_of(concept_measurement, "concept")
    n = CONCEPT_PARAMS["profile_samples"]
    if len(recon_profile) != n or len(concept_profile) != n:
        raise Vqr2bRefusal([
            f"{VQR2B_PROFILE_LENGTH_MISMATCH}:reconstruction="
            f"{len(recon_profile)}:concept={len(concept_profile)}:"
            f"expected={n}"])
    mean_dev, max_dev, diffs = _profile_deviation(recon_profile,
                                                  concept_profile)
    within = mean_dev <= threshold
    return {
        "schema": SCHEMA,
        "samples": n,
        "normalisation": "width at height / max width, both sides",
        "binding_statistic": PROFILE_DEVIATION_STATISTIC,
        "mean_abs_deviation": mean_dev,
        "max_abs_deviation": max_dev,
        "per_sample_abs_deviation": [round(d, 4) for d in diffs],
        "threshold": threshold,
        "threshold_status": THRESHOLD_STATUS,
        "threshold_provenance": THRESHOLD_PROVENANCE,
        "measured_floor": MEASURED_FLOOR,
        # §V4c: every verdict names its instrument and that instrument's
        # measured floor — which is the calibrated one only while the
        # calibrated instrument is the one acting
        "instrument": instrument,
        "premise_guard": premise,
        "within_threshold": within,
        "resolution": {
            "silhouette_height_px": reconstruction["silhouette_height_px"],
            "effective_dpi": reconstruction["raster"].get("effective_dpi"),
            "requested_dpi": reconstruction["raster"]["requested_dpi"],
            "requested_dpi_achieved":
                reconstruction["raster"].get("requested_dpi_achieved"),
            "quantisation_warning":
                reconstruction["quantisation_warning"],
        },
    }
