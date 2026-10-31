"""M6 §§5-7 — texture axes under the mirror-placed source.

The sensitivity study proved the six lobe axes blind to every
structural property (927ab8a), while the glitter event maps prove the
same structure is VIVID under the commissioned mirror-placed source.
So the new axes measure per-pixel texture statistics exactly there —
same rig geometry the glitter census commissioned, 16-bit frames, and
every declaration below is fixed BEFORE any real family is measured.

THREE AXES, each a distinct physical quantity:

GRANULARITY_INDEX
  physical: presence/amplitude of granular micro-normal structure.
  formula: RMS of the 3x3-box-high-passed luminance over the PLANAR
  region, divided by the region mean (mean-normalised, so exposure
  cannot move it).
  positive fixture: SURFACE_CONTINUITY (amplitude 0.005 vs 0.34).

SURFACE_AUTOCORRELATION_MM
  physical: grain SCALE (correlation length), not amplitude — the
  high-pass field is variance-normalised before correlating, so a
  stronger grain of the same size cannot move it.
  formula: smallest pixel lag where the mean row/column autocorrelation
  of the normalised high-pass field falls below 0.5, converted to mm.
  positive fixture: MICRO_NORMAL_CORRELATION (0.06 vs 0.20 mm).

GRAZING_BAND_CONTRAST
  physical: compaction / planar continuity at grazing incidence.
  formula: (p95 - p5) / median of luminance over the GRAZING region.
  positive fixture: COMPACTION (level 0.0 vs 0.9).

Validity and law: the pass law is UNCHANGED (2 independent axes at
>= 25% relative effect). An axis is admitted only when it detects its
positive fixture at >= the law's own bar and every §7 control fails
correctly (identical re-render, exposure-only, seed-only, lighting
perturbation). Assignments: GRANULARITY + GRAZING_BAND serve
matte/satin, pressed/matte and satin/cream; AUTOCORRELATION serves
grain-scale questions. STRUCTURAL versus RENDERED: these are RENDERED
appearance metrics; the spec parameters remain the structural record
and are never measured as if they were evidence.
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np

# must be set before cv2 is first imported anywhere in the process
os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_powder_axis_diagnosis as AD
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP
from apps.pipeline.services import palette_powder_rigs as PR

SCHEMA = "powder_texture_axes/1.0"

EFFECT_BAR = 0.25  # the unchanged law bar, reused as admission bar

#: R3 — SURFACE_AUTOCORRELATION_MM is WITHDRAWN, not repaired in place:
#: it correlated a field a 3x3 box high-pass had just whitened, so it
#: reported its own kernel support (0.14mm = 2px) on every frame ever
#: measured, including both members of its own positive fixture. Grain
#: SCALE is an unmeasured quantity until a replacement axis passes the
#: SYNTHETIC_FIELD_CONTROL below. No pair depends on it.
TEXTURE_AXES = {
    "GRANULARITY_INDEX": {"independent": True,
                          "serves": ["MATTE_vs_SATIN",
                                     "PRESSED_vs_MATTE",
                                     "SATIN_vs_CREAM"]},
    "GRAZING_BAND_CONTRAST": {"independent": True,
                              "serves": ["PRESSED_vs_MATTE",
                                         "MATTE_vs_SATIN",
                                         "SATIN_vs_CREAM"]},
}

#: R2 — realization floor: rms difference over the measured region,
#: normalised by the low member's region mean. NOT a pass bar; never
#: compared against 0.25.
REALIZATION_FLOOR = 0.002


class TextureAxisError(RuntimeError):
    pass


class FrameProvenanceError(TextureAxisError):
    """R1 — the loaded frame is not the artifact the instrument
    declares it measures."""


class DegenerateRegionError(TextureAxisError):
    """R6 — a region the axis formula cannot honestly measure. A raise,
    never a returned zero."""


class StimulusNotRealizedError(TextureAxisError):
    """R2 — the two members of a fixture pair did not render
    differently; no axis result exists for such a pair."""


class ProvenanceIncompleteError(TextureAxisError):
    """3aa — A DERIVED QUANTITY CARRIES THE IDENTITY OF EVERY INPUT IT
    READ AND OF THE DERIVATION THAT PRODUCED IT, OR IT IS NOT EVIDENCE.

    A558. This module computed numbers without recording what it read,
    which is how four published cells became
    PUBLISHED_WITHOUT_RECOVERABLE_INPUTS (A526): nobody can determine
    which frames they measured. Forward search failed, backward search
    failed, and the per-seed values exist in exactly one file each —
    the result that publishes them.

    The repair is NOT a provenance field that gets filled in when it
    can be. There is deliberately no "if provenance available" branch
    anywhere below: THAT BRANCH IS THE DEFECT, and it is the branch the
    four marked cells took. A measurement that cannot assemble (a)-(e)
    raises this, and no number leaves the function.
    """


#: A558 (a)-(e), as a FIXED tuple. _seal_provenance iterates it, so the
#: completeness check cannot iterate zero times — the 2p shape (a count
#: standing in for an enumeration) and the vacuous-loop shape are both
#: closed by the tuple being a literal of known length.
PROVENANCE_REQUIRED_KEYS = (
    "frames_read_in_order",       # (a)
    "frame_identities",           # (b)
    "derivation_code_digest",     # (c)
    "region_masks",               # (d)
    "alignment_tolerance",        # (d)
    "axis_denominators",          # (e)
)

#: A558 (b), per frame. Same fixed-tuple reason. A field that is absent
#: and a field that is present-but-None are both refusals: an identity
#: reading {"family": null} names nothing.
FRAME_IDENTITY_FIELDS = ("path", "family", "seed", "pixel_digest")

#: A558 (d). The same fixed tuple region_alignment_assertion iterates,
#: for the same reason: a region missing from the index dict must raise
#: rather than shrink the loop.
PROVENANCE_REGIONS = ("PLANAR", "GRAZING")

#: A558 (e) — the denominator each axis divides by, NAMED, per axis,
#: from this module's own docstring. The PAIR-level denominator is a
#: different quantity and is carried separately as the corpus's
#: DENOMINATOR_CONVENTION, so the two can never be read as one.
AXIS_DENOMINATORS = {
    "GRANULARITY_INDEX": "PLANAR_REGION_MEAN",
    "GRAZING_BAND_CONTRAST": "GRAZING_REGION_MEDIAN",
}


def _derivation_code_digest() -> str:
    """A558 (c) — the digest of THIS module as it stands at computation
    time, read from disk on every call rather than cached at import, so
    an edited derivation cannot publish under the digest it had when
    the process started."""
    src = os.path.abspath(__file__)
    if src.endswith(".pyc"):
        src = src[:-1]
    try:
        with open(src, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError as exc:
        raise ProvenanceIncompleteError(
            f"the derivation's own source is unreadable ({exc}) — "
            "(c) cannot be assembled, so no number is returned") from exc


def _pixel_digest(arr) -> str:
    """A558 (b) — a digest of the LOADED PIXEL DATA, never of the path.

    A filename digest would have satisfied a reader and recovered
    nothing: the four marked cells have filenames nobody recorded and
    pixels nobody can match. Two differently-named frames with
    identical pixels collide here ON PURPOSE — the identity is the
    content.
    """
    buf = np.ascontiguousarray(np.asarray(arr), dtype=np.float64)
    return hashlib.sha256(buf.tobytes()).hexdigest()[:16]


class ProvenancedFrame(np.ndarray):
    """A loaded frame that carries the identity of what was read.

    An ndarray SUBCLASS rather than a side-channel argument, so the
    frame and its provenance cannot be separated in transit and every
    existing reader of load_scene_linear keeps working unchanged.
    measure_texture_axes refuses a bare ndarray, and that refusal is
    what makes omission structural rather than remembered.
    """

    frame_identity = None

    def __array_finalize__(self, obj):
        # An explicit type test, NOT an attribute lookup carrying a
        # default value. Lookup-with-default is the A32/1q shape the
        # standing source-scan control forbids in measurement code, and
        # it is the SAME silent-fallback shape 3aa exists to close —
        # writing the law and then implementing it with a silent
        # default would be the defect wearing the fix's clothes. (The
        # control scans source TEXT, so it fires on the shape written
        # in a comment too; it caught this instrument three times
        # before this wording, which is the control working.) The class
        # attribute above is the declared absence; a view taken of a
        # bare ndarray simply leaves it unset.
        if isinstance(obj, ProvenancedFrame):
            self.frame_identity = obj.frame_identity


def provenanced_frame(arr, *, path, family, seed, source_kind,
                      measurement=None):
    """Attach an input identity to an array.

    source_kind is RECORDED, never inferred, and is part of every
    result: a synthetic in-memory frame and a scene-linear EXR are both
    measurable and must never read alike in a record. The loader below
    is the only caller that may say SCENE_LINEAR_EXR.
    """
    base = np.asarray(arr)
    ident = {
        "path": path,
        "family": family,
        "seed": seed,
        "pixel_digest": _pixel_digest(base),
        "source_kind": source_kind,
        "shape": list(base.shape),
        "dtype": str(base.dtype),
        # set by region_alignment_assertion; NEVER defaulted to
        # asserted, so a result cannot be silent about whether the
        # frame was checked against the scene-linear authority
        "region_alignment": "NOT_ASSERTED",
    }
    if measurement is not None:
        # explicit membership, and ABSENT written out: a silent None
        # here would read in a record as "no render identity" when it
        # actually means "nobody looked"
        ident["measurement_record"] = {
            key: (measurement[key] if key in measurement else "ABSENT")
            for key in
            ("render_identity", "material_identity", "geometry_identity",
             "camera_identity", "lighting_contract_identity")}
    out = base.view(ProvenancedFrame)
    out.frame_identity = ident
    return out


def _seal_provenance(frame, region_idx) -> dict:
    """Assemble A558 (a)-(e) or RAISE. Called BEFORE any arithmetic.

    Sealing first is not cosmetic: it means there is no state of the
    program in which a number has been computed and the provenance is
    then found to be missing. The only two outcomes are "a number with
    its inputs" and "an exception".
    """
    if not isinstance(frame, ProvenancedFrame):
        raise ProvenanceIncompleteError(
            "the frame carries no identity — it was not loaded through "
            "load_scene_linear and was not declared through "
            "provenanced_frame, so (a) and (b) cannot be assembled and "
            "this measurement returns no number (3aa)")
    ident = frame.frame_identity
    if ident is None:
        raise ProvenanceIncompleteError(
            "the frame is a ProvenancedFrame whose identity was never "
            "set — an identity that names nothing is not provenance")

    for field in FRAME_IDENTITY_FIELDS:          # fixed 4-tuple
        if field not in ident:
            raise ProvenanceIncompleteError(
                f"frame identity is missing {field!r} — (b) incomplete")
        if ident[field] is None:
            raise ProvenanceIncompleteError(
                f"frame identity field {field!r} is None — a provenance "
                "block that names nothing is not provenance (3aa)")

    masks = {}
    for region in PROVENANCE_REGIONS:            # fixed 2-tuple
        try:
            flat = np.asarray(region_idx[region], dtype=np.int64)
        except KeyError as exc:
            # a missing region RAISES; it does not shorten the loop
            raise ProvenanceIncompleteError(
                f"region mask {region!r} absent from the index — (d) "
                "cannot be assembled") from exc
        if flat.size == 0:
            raise ProvenanceIncompleteError(
                f"region mask {region!r} is empty — an empty mask names "
                "no pixels and cannot identify what was measured")
        masks[region] = {
            "sample_count": int(flat.size),
            "index_digest": hashlib.sha256(
                np.ascontiguousarray(np.sort(flat)).tobytes()
            ).hexdigest()[:16]}

    denominators = {}
    for axis in sorted(TEXTURE_AXES):            # the admitted axes
        if axis not in AXIS_DENOMINATORS:
            raise ProvenanceIncompleteError(
                f"axis {axis!r} has no NAMED denominator — (e) cannot "
                "be assembled for an axis whose divisor is unstated")
        denominators[axis] = AXIS_DENOMINATORS[axis]

    block = {
        "law": "3aa",
        "schema": "texture_axis_measurement_provenance/1.0",
        "frames_read_in_order": [ident["path"]],
        "frame_identities": [ident],
        "derivation_code_digest": _derivation_code_digest(),
        "derivation": {
            "module": "apps/pipeline/services/palette_powder_texture_axes.py",
            "function": "measure_texture_axes"},
        "region_masks": masks,
        "alignment_tolerance": ALIGNMENT_TOLERANCE,
        "axis_denominators": denominators,
        "pair_relative_effect_denominator":
            PP.DENOMINATOR_CONVENTION["determination"],
    }

    for key in PROVENANCE_REQUIRED_KEYS:         # fixed 6-tuple
        if key not in block or block[key] in (None, [], {}):
            raise ProvenanceIncompleteError(
                f"provenance key {key!r} is absent or empty — A558 "
                "(a)-(e) is not satisfied and no number is returned")
    return block


def frame_provenance_assertion(arr):
    """R1 — accepts only a floating-point array with >= 3 channels,
    drops alpha explicitly, RAISES on uint8. The negative control is
    the committed 8-bit RGBA frame that caused F1/F2."""
    if arr is None:
        raise FrameProvenanceError("frame unreadable")
    if arr.dtype == np.uint8:
        raise FrameProvenanceError(
            "uint8 frame refused — the instrument measures scene-linear "
            "float frames only; 8-bit display-encoded PNGs are human "
            "review artifacts (F1/F2)")
    if not np.issubdtype(arr.dtype, np.floating):
        raise FrameProvenanceError(
            f"non-float frame refused: {arr.dtype}")
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise FrameProvenanceError(
            f"expected >= 3 channels, got shape {arr.shape}")
    # alpha (and any extra channel) dropped EXPLICITLY, never averaged
    return arr[..., :3].astype(np.float64).mean(axis=2)


def load_scene_linear(exr_path, *, family=None, seed=None,
                      measurement=None):
    """R1 — every measurement reads the float EXR the renderer already
    writes; the PNGs are demoted to human-review artifacts.

    A558: the loader RECORDS what it read — path, family, seed and a
    digest of the loaded pixels — onto the frame it returns. family and
    seed are keyword-optional HERE and mandatory at the measurement,
    which is the only place a number appears: readers that only load a
    frame (palette_flake_rig, palette_powder_rigs,
    palette_parameter_realization_audit) are unchanged, while anything
    that computes a number must name its inputs or raise.

    ORIENTATION: cv2 delivers the EXR vertically flipped relative to
    the region-index order — measured, not assumed: unflipped, the
    GRAZING indices land on backdrop (mean 0.0114 against the Blender
    authority's 0.0774) and its contrast reads an exact structureless
    0.0. The frame is flipped here, and REGION_ALIGNMENT_ASSERTION
    verifies the result against the Blender-side measurement on every
    single measurement, so an orientation regression cannot produce a
    number."""
    import cv2
    frame = frame_provenance_assertion(
        cv2.imread(exr_path, cv2.IMREAD_UNCHANGED))
    if measurement is None:
        sidecar = os.path.splitext(exr_path)[0] + ".json"
        if os.path.exists(sidecar):
            with open(sidecar) as fh:
                measurement = json.load(fh)
    # the digest is taken over the frame AS MEASURED — after the flip,
    # because the flip is part of the read path and a digest of the
    # pre-flip buffer would identify an array no axis ever sees
    return provenanced_frame(
        frame[::-1], path=exr_path, family=family, seed=seed,
        source_kind="SCENE_LINEAR_EXR", measurement=measurement)


#: declared tolerance for the alignment check: the loader's region mean
#: must sit within 5% relative of the Blender-side authority mean —
#: cross-implementation sampling differences measure ~1.6%, an
#: orientation error measures ~85%
ALIGNMENT_TOLERANCE = 0.05


def region_alignment_assertion(frame, region_idx, measurement):
    """The loaded frame's regions must BE the regions the Blender-side
    measurement (the scene-linear authority) describes."""
    for region in ("PLANAR", "GRAZING"):
        authority = float(
            measurement["regions"][region]["scene_linear_mean"])
        mask = np.zeros(frame.size, dtype=bool)
        mask[np.asarray(region_idx[region], dtype=int)] = True
        loaded = float(frame.reshape(-1)[mask].mean())
        if authority <= 0:
            raise DegenerateRegionError(
                f"{region} authority mean is zero")
        if abs(loaded - authority) / authority > ALIGNMENT_TOLERANCE:
            raise FrameProvenanceError(
                f"REGION_ALIGNMENT failed for {region}: loaded mean "
                f"{loaded:.4f} vs Blender authority {authority:.4f} — "
                f"the frame is not oriented as the indices assume")
    # A558 (d) — the fact that this ran is part of the frame's identity.
    # Only reached when BOTH regions passed, so it cannot record an
    # assertion that half-happened.
    if isinstance(frame, ProvenancedFrame) \
            and frame.frame_identity is not None:
        frame.frame_identity["region_alignment"] = "ASSERTED"
        frame.frame_identity["region_alignment_tolerance"] = \
            ALIGNMENT_TOLERANCE


def stimulus_realization(frame_a, frame_b, region_idx,
                         region="PLANAR") -> dict:
    """R2 — frame-level realization check, BEFORE any axis. Deterministic
    renders of identical input are bit-identical, so a pair below the
    floor proves the parameter never reached the frame — the exact
    false-blindness conclusion drawn at 927ab8a."""
    mask = np.zeros(frame_a.size, dtype=bool)
    mask[np.asarray(region_idx[region], dtype=int)] = True
    mask = mask.reshape(frame_a.shape)
    a, b = frame_a[mask], frame_b[mask]
    low_mean = float(min(a.mean(), b.mean()))
    if low_mean <= 0:
        raise DegenerateRegionError("realization region is black")
    rms = float(np.sqrt(((a - b) ** 2).mean()))
    ratio = rms / low_mean
    return {"rms": round(rms, 8), "low_member_mean": round(low_mean, 6),
            "rms_over_mean": round(ratio, 8),
            "floor": REALIZATION_FLOOR,
            "realized": bool(ratio >= REALIZATION_FLOOR)}


def withdrawn_autocorrelation_reference(field) -> float:
    """R3 forensic reference — the WITHDRAWN formula, kept only so the
    SYNTHETIC_FIELD_CONTROL can record its failure. Never an axis."""
    pad = np.pad(field, 1, mode="edge")
    local = np.zeros_like(field)
    for dy in range(3):
        for dx in range(3):
            local += pad[dy:dy + field.shape[0],
                         dx:dx + field.shape[1]] / 9.0
    hp = field - local
    var = float((hp ** 2).mean())
    for lag in range(1, 41):
        a, b = hp[:, :-lag], hp[:, lag:]
        if float((a * b).mean()) / var < 0.5:
            return lag / PR.PX_PER_MM
    return 40 / PR.PX_PER_MM


def _region_image(frame, region_idx, region):
    """Crop a loaded (already provenance-asserted) 2-D float frame to
    a region. This function no longer opens files — the loader does,
    through the assertion."""
    arr = frame
    mask = np.zeros(arr.size, dtype=bool)
    mask[np.asarray(region_idx[region], dtype=int)] = True
    mask = mask.reshape(arr.shape)
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = arr[y0:y1 + 1, x0:x1 + 1]
    inner = mask[y0:y1 + 1, x0:x1 + 1]
    return crop, inner


def _high_pass(crop):
    k = np.ones((3, 3)) / 9.0
    padded = np.pad(crop, 1, mode="edge")
    local = np.zeros_like(crop)
    for dy in range(3):
        for dx in range(3):
            local += k[dy, dx] * padded[dy:dy + crop.shape[0],
                                        dx:dx + crop.shape[1]]
    return crop - local


def measure_texture_axes(frame, region_idx) -> dict:
    """The two admitted texture axes, from a provenance-asserted
    scene-linear frame. R3: the autocorrelation axis is WITHDRAWN and
    not computed. R6: every degenerate branch raises — there is no
    return path a caller could mistake for a measurement of zero.

    A558/3aa: the provenance is SEALED FIRST. There is exactly one
    return statement and it carries _provenance unconditionally, so no
    state of this function exists in which a number has been computed
    and its inputs are then found to be missing.
    """
    provenance = _seal_provenance(frame, region_idx)
    # measured as a plain array from here: the identity is sealed, and
    # subclass arithmetic has no business inside the formula
    frame = np.asarray(frame)
    planar, pmask = _region_image(frame, region_idx, "PLANAR")
    mean = float(planar[pmask].mean())
    if mean <= 0:
        raise DegenerateRegionError(
            "PLANAR region mean is zero — refusing to measure")
    hp = _high_pass(planar)
    granularity = float(np.sqrt((hp[pmask] ** 2).mean())) / mean

    grazing, gmask = _region_image(frame, region_idx, "GRAZING")
    gvals = grazing[gmask]
    med = float(np.median(gvals))
    if med <= 0:
        raise DegenerateRegionError(
            "GRAZING region median is zero — refusing to measure")
    contrast = float(np.percentile(gvals, 95)
                     - np.percentile(gvals, 5)) / med
    # the axis values are UNCHANGED, rounding included — A563 forbids
    # re-specifying the derivation, and the committed per-seed values
    # this node is measured against were themselves computed from the
    # 6-dp form (0.041395 / 0.063692 reproduce 0.4243531550049007
    # exactly). Only _provenance is added.
    return {"GRANULARITY_INDEX": round(granularity, 6),
            "GRAZING_BAND_CONTRAST": round(contrast, 6),
            "_provenance": provenance}


#: subject validity window — the DECLARED dielectric window, reused:
#: below it a measurement is sampling noise on darkness (the first
#: validation run measured exactly that and a near-black frame proved
#: it), above it the frame clips
SUBJECT_WINDOW = (0.35, 0.92)

#: the calibration OPERATING TARGET sits inside the window — aiming at
#: the boundary made the fixed point converge to 0.92 + float epsilon
#: and miss acceptance by 3e-8; the window itself is unchanged
CAL_TARGET = 0.88


def _render_at(spec, out_dir, label, energy, *, samples,
               overrides_extra=None):
    over = PR.glitter_rig_overrides()
    over["specular_source"]["energy"] = float(energy)
    for key, val in (overrides_extra or {}).items():
        if isinstance(val, dict):
            over.setdefault(key, {}).update(val)
        else:
            over[key] = val
    return CR.characterize_powder(spec, out_dir, label=label,
                                  overrides=over, samples=samples)


#: M6-ENSEMBLE-CONVENTION-DECLARATION (2026-08-15, declared_spreads/
#: ensemble_convention_declaration.json): 6-member texture ensembles for
#: the non-MATTE diffuse families, pinned as commissioning constants the
#: way the flake rig pinned FLOOR_SEEDS. DERIVATION, written down before
#: any render consumes it: member 0 IS the family's canonical pair seed
#: (connecting each ensemble to every standing pair measurement, exactly
#: as MATTE's recorded ensemble contains its base 40); members 1-5 are
#: the contiguous block anchored at base*10 — the decimal shift makes
#: collision with every recorded seed in this instrument impossible
#: (bases 40/41/47/48, MATTE ensemble 81-99, replicates 400/401).
#: POWDER_MATTE is deliberately NOT restated here: its set remains the
#: RECORDED ensemble in axis_noise_floors.json, resolved fail-closed at
#: 93f0202 — this constant declares only what no record determined.
ENSEMBLE_SEEDS_BY_FAMILY = {
    "POWDER_SATIN": (41, 410, 411, 412, 413, 414),
    "CREAM": (48, 480, 481, 482, 483, 484),
    "PRESSED_POWDER": (47, 470, 471, 472, 473, 474),
}


def characterize_texture_pair(spec_a, spec_b, out_dir, *, label_a,
                              label_b, samples=64,
                              extra_b=None) -> dict:
    """Both members under ONE calibrated configuration.

    The rig calibrates per pair on its MEASURED brighter member using
    the same iterated law every other calibration in M5/M6 uses, to
    the same declared window — identical configuration for both
    members, so the comparison is never an exposure artifact. Both
    subjects must land inside SUBJECT_WINDOW or the pair refuses to
    measure.
    """
    # PER-MEMBER calibration to the same declared window under the
    # same iterated law. A single shared energy cannot hold a pair
    # whose property changes brightness by more than the window ratio
    # (continuity-class pairs measure 3.2x, BSDF-driven) — and it does
    # not have to: every texture axis is normalisation-invariant by
    # construction and the mandatory exposure-only control MEASURES
    # that invariance. Window, bars and controls unchanged.
    #
    # SUPERSEDED IN PLACE per 2u/2k (2026-08-11, law 44414377f5af69e0):
    # the sentence above is RETAINED as the claim under which every
    # prior pair was adjudicated, and it is REFUTED for
    # GRAZING_BAND_CONTRAST at member conditions — four-for-four
    # (SHIMMER, POWDER_METALLIC, BAKED, MARBLED energy negative
    # controls, shifts > 0.125 against both window-spanning offsets;
    # render_spend/queue_results.json energy_ctl.*.axes, stamps
    # NOT_ENERGY_INVARIANT_AT_CONDITION, validated ranges
    # [0.404,0.802]/[0.398,0.858]/[0.394,0.826]/[0.356,0.905]). The
    # commissioned exposure-only control validated invariance at
    # FIXTURE condition only; the generalisation to member conditions
    # was unvalidated (1p). GRANULARITY_INDEX cleared the same
    # controls in all four families and its invariance at those
    # conditions is ESTABLISHED, not assumed. Citations of GBC values
    # from those frames raise via read_stamped_axis.
    ref = PR.glitter_rig_overrides()["specular_source"]["energy"]
    calibrations = {}
    energies = {}
    for spec, label in ((spec_a, label_a), (spec_b, label_b)):
        d = _render_at(spec, out_dir, f"probe_{label}", ref,
                       samples=max(24, samples // 2))
        peak = float(d["regions"]["PLANAR"]["scene_linear_peak"])
        base = _render_at(spec, out_dir, f"base_{label}", 0.0,
                          samples=max(24, samples // 2))
        base_peak = float(base["regions"]["PLANAR"]["scene_linear_peak"])
        if base_peak >= SUBJECT_WINDOW[1]:
            raise TextureAxisError("base lighting alone exceeds the "
                                   "window")
        energy = ref
        iterations = []
        for _ in range(4):
            # linear transport: the specular contribution is
            # peak - base, so the solve works in BOTH directions —
            # the max() form could only calibrate downward and a dim
            # subject ratcheted without ever converging
            spec_contrib = max(peak - base_peak, 1e-6)
            energy = energy * (CAL_TARGET - base_peak) / spec_contrib
            d = _render_at(spec, out_dir, f"cal_{label}", energy,
                           samples=max(24, samples // 2))
            pl = d["regions"]["PLANAR"]
            peak = float(pl["scene_linear_peak"])
            iterations.append({"energy": energy, "peak": peak,
                               "clipped": pl["clipped_sample_count"]})
            if pl["clipped_sample_count"] == 0 \
                    and SUBJECT_WINDOW[0] <= peak <= SUBJECT_WINDOW[1]:
                break
        else:
            raise TextureAxisError(f"{label} calibration did not "
                                   f"converge: {iterations}")
        energies[label] = energy
        calibrations[label] = {"base_peak": base_peak,
                               "iterations": iterations,
                               "energy": energy}

    return _measure_pair_per_member(
        spec_a, spec_b, out_dir, label_a, label_b, energies, samples,
        extra_b, {"per_member": calibrations,
                  "why": "normalisation-invariant axes, exposure "
                         "control mandatory [SUPERSEDED per 2u "
                         "2026-08-11: refuted for GRAZING_BAND_"
                         "CONTRAST at member conditions four-for-"
                         "four; GRANULARITY_INDEX established; see "
                         "render_spend/queue_results.json]",
                  "window": list(SUBJECT_WINDOW)})


def _measure_pair_per_member(spec_a, spec_b, out_dir, label_a, label_b,
                             energies, samples, extra_b, calibration):
    """The single chokepoint every pair passes through.

    R1: frames load from the scene-linear EXR through the provenance
    assertion; the PNGs are human-review artifacts only. R2: the
    realization gate runs BEFORE any axis — a pair whose members did
    not render differently reports STIMULUS_NOT_REALIZED with NO axis
    values, so 'detects: false' is unreachable for an unrealized
    stimulus."""
    idx = CR.region_indices(out_dir)
    out = {"_calibration": calibration}
    frames = {}
    for spec, label, extra in ((spec_a, label_a, None),
                               (spec_b, label_b, extra_b)):
        d = _render_at(spec, out_dir, f"tx_{label}", energies[label],
                       samples=samples, overrides_extra=extra)
        pl = d["regions"]["PLANAR"]
        if pl["clipped_sample_count"]:
            raise TextureAxisError(f"{label} clipped — refused")
        if float(pl["scene_linear_peak"]) < SUBJECT_WINDOW[0]:
            raise TextureAxisError(
                f"{label} peak {pl['scene_linear_peak']:.3f} below the "
                f"declared window — a measurement of darkness is not a "
                f"measurement")
        # A558 (b) — family and seed come from the SPEC that was
        # rendered, not from the label or the filename. The spec is the
        # only authority for what the frame is of.
        frame = load_scene_linear(d["exr"], family=spec.family,
                                  seed=spec.seed, measurement=d)
        region_alignment_assertion(frame, idx, d)
        frames[label] = (frame, float(pl["scene_linear_peak"]))
    realization = stimulus_realization(frames[label_a][0],
                                       frames[label_b][0], idx)
    out["_stimulus"] = realization
    if not realization["realized"]:
        out["STIMULUS_NOT_REALIZED"] = True
        return out
    for label in (label_a, label_b):
        frame, peak = frames[label]
        out[label] = measure_texture_axes(frame, idx)
        out[label]["_planar_peak"] = peak
    return out


def measured_pair_at(spec_a, spec_b, out_dir, *, label_a, label_b,
                     energy, samples=64, extra_b=None) -> dict:
    """A pair at a KNOWN calibrated energy (control reuse) — same
    guards, no re-calibration."""
    return _measure_pair_per_member(
        spec_a, spec_b, out_dir, label_a, label_b,
        {label_a: energy, label_b: energy}, samples, extra_b,
        {"reused_energy": energy, "window": list(SUBJECT_WINDOW)})


def _effect(a, b):
    mean = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / mean if mean > 1e-9 else 0.0


def measure_frame_on_disk(exr_path, region_idx, *, family, seed) -> dict:
    """A553 — RUN the derivation over a frame already on disk.

    Renders nothing: render authority lives in the render_spend
    declaration under 2j and is not extended by reading. The sidecar
    measurement is the scene-linear authority region_alignment_assertion
    checks against, and it is REQUIRED — a frame with no authority
    beside it cannot be measured quietly, because that is precisely the
    condition under which the four marked cells were published.
    """
    sidecar = os.path.splitext(exr_path)[0] + ".json"
    if not os.path.exists(sidecar):
        raise ProvenanceIncompleteError(
            f"no scene-linear authority beside {exr_path} — the frame "
            "cannot be alignment-asserted, so it is not measured")
    with open(sidecar) as fh:
        measurement = json.load(fh)
    frame = load_scene_linear(exr_path, family=family, seed=seed,
                              measurement=measurement)
    region_alignment_assertion(frame, region_idx, measurement)
    return measure_texture_axes(frame, region_idx)


def recompute_pair_from_frames(frames_dir, region_idx, *, prefix,
                               family_a, family_b, seeds, axis) -> dict:
    """A561 — one published cell, recomputed from named frames.

    AGGREGATION IS DECLARED HERE, not chosen after looking: the family
    aggregate is the ARITHMETIC MEAN across the named seeds. Per-seed
    relative effects need no aggregation at all and are reported
    whole, so a reader can check the aggregate rather than take it.

    DENOMINATOR: MEAN_OF_THE_TWO_VALUES, the corpus's ratified
    DENOMINATOR_CONVENTION, applied per seed and to the aggregate —
    'their mean on that axis', one reading, no seed language.

    DISPERSION: A289 — MAXIMUM PAIRWISE ABSOLUTE DIFFERENCE of the
    per-seed clearings. A difference of relative effects, therefore in
    relative-effect units, therefore commensurable with the margin
    (A284: clearing_dispersion was not, and that was a units defect).
    """
    per_seed = {family_a: {}, family_b: {}}
    provenance = {"frames_read_in_order": [], "frame_identities": [],
                  "derivation_code_digest": None, "region_masks": None,
                  "alignment_tolerance": None, "axis_denominators": None}
    for family in (family_a, family_b):
        for seed in seeds:
            exr = os.path.join(frames_dir, f"{prefix}_{family}_{seed}.exr")
            axes = measure_frame_on_disk(exr, region_idx,
                                         family=family, seed=seed)
            per_seed[family][str(seed)] = axes[axis]
            block = axes["_provenance"]
            provenance["frames_read_in_order"] += block["frames_read_in_order"]
            provenance["frame_identities"] += block["frame_identities"]
            for key in ("derivation_code_digest", "region_masks",
                        "alignment_tolerance", "axis_denominators"):
                if provenance[key] is not None \
                        and provenance[key] != block[key]:
                    raise ProvenanceIncompleteError(
                        f"{key} changed mid-measurement — the cell would "
                        "be a mixture of derivations and could not name "
                        "the one that produced it (3aa)")
                provenance[key] = block[key]
    provenance["pair_relative_effect_denominator"] = \
        PP.DENOMINATOR_CONVENTION["determination"]
    provenance["aggregation_across_seeds"] = "ARITHMETIC_MEAN_DECLARED"
    provenance["law"] = "3aa"

    clearings = {str(s): _effect(per_seed[family_a][str(s)],
                                 per_seed[family_b][str(s)])
                 for s in seeds}
    vals = list(clearings.values())
    dispersion = max(abs(x - y) for i, x in enumerate(vals)
                     for y in vals[i + 1:])
    mean_a = sum(per_seed[family_a].values()) / len(seeds)
    mean_b = sum(per_seed[family_b].values()) / len(seeds)
    effect = _effect(mean_a, mean_b)
    bar = PP.PASS_LAW["relative_effect_bar"]
    return {
        "axis": axis, "prefix": prefix, "seeds": list(seeds),
        "per_seed_axis_values": per_seed,
        "family_means": {family_a: mean_a, family_b: mean_b},
        "per_seed_clearings": clearings,
        "cross_family_relative_effect": effect,
        "relative_effect_bar": bar,
        "margin": effect - bar,
        "A289_dispersion_max_pairwise_absolute_difference": dispersion,
        "_provenance": provenance,
    }


def validate_axes(out_dir, *, samples=64) -> dict:
    """§5 positive fixtures + §7 negative controls, before any family.

    Every comparison goes through the pair-calibrated path so both
    members sit inside the declared subject window — the first run of
    this validation measured sampling noise on darkness, and the
    window guard is what prevents that from ever reading as a result.
    """
    os.makedirs(out_dir, exist_ok=True)
    shade = PE.PowderShade("prov_diag_neutral", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)

    def spec_of(family, seed, overrides):
        return PE.PowderMaterialSpec(family, shade, seed=seed,
                                     overrides=overrides)

    positives = {}
    for axis, fixture in (
            ("GRANULARITY_INDEX", "SURFACE_CONTINUITY"),
            ("GRAZING_BAND_CONTRAST", "COMPACTION")):
        fx = AD.FIXTURES[fixture]
        pair = characterize_texture_pair(
            spec_of(fx["family"], fx["seed"], fx["low"]),
            spec_of(fx["family"], fx["seed"], fx["high"]),
            out_dir, label_a=f"{fixture}_low",
            label_b=f"{fixture}_high", samples=samples)
        if pair.get("STIMULUS_NOT_REALIZED"):
            # R2 — no relative effect exists for an unrealized pair;
            # 'detects: false' is unreachable from here by construction
            positives[axis] = {"fixture": fixture,
                               "STIMULUS_NOT_REALIZED": True,
                               "stimulus": pair["_stimulus"],
                               "detects": None}
            continue
        lo, hi = pair[f"{fixture}_low"], pair[f"{fixture}_high"]
        eff = _effect(lo[axis], hi[axis])
        positives[axis] = {"fixture": fixture,
                           "low": lo[axis], "high": hi[axis],
                           "relative_effect": round(eff, 4),
                           "stimulus": pair["_stimulus"],
                           "calibration": pair["_calibration"],
                           "detects": bool(eff >= EFFECT_BAR)}

    # §7 controls on the matte default. The identical pair is R2's own
    # negative control: a deterministic re-render of identical input
    # MUST report STIMULUS_NOT_REALIZED — 'no axis detects' is the
    # false conclusion the gate exists to make unreachable. The other
    # controls DO realize (their frames genuinely differ) and their
    # axis effects must stay under the bar, each pair compared within
    # itself.
    matte80 = spec_of(PP.POWDER_MATTE, 80, None)
    ident = characterize_texture_pair(
        matte80, matte80, out_dir, label_a="ctl_base",
        label_b="ctl_rerun", samples=samples)
    energy = ident["_calibration"]["per_member"]["ctl_base"]["energy"]
    controls = {"identical_rerun_realization_gate": {
        "expected": "STIMULUS_NOT_REALIZED",
        "stimulus": ident["_stimulus"],
        "behaved": bool(ident.get("STIMULUS_NOT_REALIZED"))}}
    for name, spec_b, extra in (
            ("seed_only", spec_of(PP.POWDER_MATTE, 81, None), None),
            ("exposure_only", matte80,
             {"diffuse_source": {"energy":
              CR.RIG["diffuse_source"]["energy"] * 1.35}}),
            ("lighting_perturbation", matte80,
             {"specular_source": {"elevation":
              CR.RIG["camera"]["elevation"] + 2.0}})):
        pair = measured_pair_at(
            matte80, spec_b, out_dir, label_a=f"ctl_a_{name}",
            label_b=f"ctl_b_{name}", energy=energy, samples=samples,
            extra_b=extra)
        if pair.get("STIMULUS_NOT_REALIZED"):
            controls[name] = {"STIMULUS_NOT_REALIZED": True,
                              "stimulus": pair["_stimulus"],
                              "behaved": False}
            continue
        a, b = pair[f"ctl_a_{name}"], pair[f"ctl_b_{name}"]
        effs = {ax: round(_effect(a[ax], b[ax]), 4)
                for ax in TEXTURE_AXES}
        controls[name] = {"effects": effs,
                          "stimulus": pair["_stimulus"],
                          "behaved": all(e < EFFECT_BAR
                                         for e in effs.values())}

    rejected = [a for a, p in positives.items()
                if p["detects"] is False]
    unrealized = [a for a, p in positives.items()
                  if p.get("STIMULUS_NOT_REALIZED")]
    misbehaved = [n for n, c in controls.items() if not c["behaved"]]
    return {
        "record_type": SCHEMA,
        "protocol_identity": PP.protocol_identity(),
        "repair_identity": "1e198aed8d86ed9c",
        "declared_before_family_measurement": True,
        "measured_from": "SCENE_LINEAR_EXR_RGB_ONLY",
        "effect_bar": EFFECT_BAR,
        "realization_floor": REALIZATION_FLOOR,
        "axes": TEXTURE_AXES,
        "withdrawn_axes": ["SURFACE_AUTOCORRELATION_MM"],
        "positive_fixtures": positives,
        "negative_controls": controls,
        "rejected_axes": rejected,
        "unrealized_fixtures": unrealized,
        "controls_misbehaved": misbehaved,
        # per-axis admission, as declared: a rejected CANDIDATE is out;
        # an UNREALIZED fixture admits nothing and rejects nothing;
        # the instrument passes when at least one axis is admitted and
        # every control behaved
        "verdict": ("PASS" if len(rejected) + len(unrealized)
                    < len(TEXTURE_AXES) and not misbehaved else "FAIL"),
    }


# --------------------------------------------------------------------------
# §§8-10 — the rulings: frozen families, admitted axes, unchanged law
# --------------------------------------------------------------------------

RULING_PAIRS = (
    ("MATTE_VS_SATIN", PP.POWDER_MATTE, PP.POWDER_SATIN),
    ("PRESSED_VS_MATTE", PP.PRESSED_POWDER, PP.POWDER_MATTE),
    ("SATIN_VS_CREAM", PP.POWDER_SATIN, PP.CREAM),
)


def rule_diffuse_pairs(validation, out_dir, swatch_dir, *,
                       samples=64) -> dict:
    """Re-run the three pairs WITHOUT touching the material definitions.

    Clearing axes are counted across the six lobe axes (diffuse-rig
    measurements) plus every ADMITTED texture axis (mirror-source rig)
    — different rig, different statistics, independent by construction
    and by the §7 controls. The law is the unchanged 2-at-25%.
    """
    if validation["verdict"] != "PASS":
        raise TextureAxisError("no texture axis is admitted — no "
                               "family ruling may use them")
    admitted = [a for a in TEXTURE_AXES
                if a not in validation["rejected_axes"]]
    shade = PE.PowderShade("prov_char_neutral", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)
    seeds = {PP.POWDER_MATTE: 40, PP.POWDER_SATIN: 41,
             PP.PRESSED_POWDER: 47, PP.CREAM: 48}

    rulings = {}
    for label, fam_a, fam_b in RULING_PAIRS:
        pair = characterize_texture_pair(
            PE.PowderMaterialSpec(fam_a, shade, seed=seeds[fam_a]),
            PE.PowderMaterialSpec(fam_b, shade, seed=seeds[fam_b]),
            out_dir, label_a=f"{label}_{fam_a}",
            label_b=f"{label}_{fam_b}", samples=samples)
        if pair.get("STIMULUS_NOT_REALIZED"):
            # two distinct families rendering identically is a refusal
            # to rule, never a FAIL_MATERIAL_MODEL
            rulings[label] = {"verdict": "REFUSED_STIMULUS_NOT_REALIZED",
                              "stimulus": pair["_stimulus"]}
            continue
        texture_a = pair[f"{label}_{fam_a}"]
        texture_b = pair[f"{label}_{fam_b}"]
        old = CR.discriminate(
            CR.axes_from(json.load(open(
                os.path.join(swatch_dir,
                             f"swatch_powder_{fam_a}.json")))),
            CR.axes_from(json.load(open(
                os.path.join(swatch_dir,
                             f"swatch_powder_{fam_b}.json")))),
            fam_a, fam_b)
        tex_rows = {}
        tex_clearing = []
        for axis in admitted:
            va = float(texture_a[axis])
            vb = float(texture_b[axis])
            eff = _effect(va, vb)
            tex_rows[axis] = {"a": va, "b": vb,
                              "relative_effect": round(eff, 4),
                              "clears": bool(eff >= EFFECT_BAR)}
            if eff >= EFFECT_BAR:
                tex_clearing.append(axis)
        clearing = old["axes_clearing"] + tex_clearing
        rulings[label] = {
            "lobe_axes": old["axes"],
            "texture_axes": tex_rows,
            "axes_clearing": clearing,
            "verdict": "PASS" if len(clearing) >= 2 else
                       "FAIL_MATERIAL_MODEL",
            "diagnosis": ("PREVIOUS_RIG_AXIS_INSUFFICIENCY"
                          if len(clearing) >= 2 and tex_clearing
                          else None),
        }
    failed = [k for k, v in rulings.items() if v["verdict"] != "PASS"]
    return {
        "record_type": "diffuse_pair_rulings/1.0",
        "material_definitions_changed": False,
        "admitted_texture_axes": admitted,
        "pass_law": "2 independent axes at >= 25% — unchanged",
        "rulings": rulings,
        "failed_pairs": failed,
        "verdict": "PASS" if not failed else "FAIL",
    }
