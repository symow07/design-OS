"""A100 — the census-energy reading instrument, named per 2f.

The N=8 texture census calibrated four late-joining families
(SHIMMER, POWDER_METALLIC, BAKED, MARBLED) per member and committed
the full calibrating frame quartet (probe/base/cal/tx swatches under
docs/roadmap/palt_m6/texture_axes/) but never wrote the solved energy
to any record. The solve itself is committed law
(characterize_texture_pair's iterated linear-transport step in
palette_powder_texture_axes) and both of its inputs are committed
measurements, so the first-iteration energy is re-derivable exactly:

    E1 = ref * (CAL_TARGET - base_peak) / (probe_peak - base_peak)

CONDITIONAL, stated on the record it returns: the cal frame was
overwritten in place on every iteration, so committed records support
but cannot prove single-iteration convergence. E1 equals the
census-era energy IFF the loop broke on iteration one; the returned
record carries the pixel-identity verification that would convert the
derivation into proof (re-render the cal frame at E1, compare
scene-linear pixels to the committed cal EXR). Nothing here renders.

The four diffuse families' energies were committed directly
(independence_sweeps/family_energies.json); ``read_cached_energy``
reads that record. GLITTER raises: it was never in the texture census
(a2_firing_result.json census_n8 has no GLITTER row) — there is no
energy to recover and no row to replicate.
"""
import json
import os

from apps.pipeline.services import palette_powder_rigs as PR
from apps.pipeline.services import palette_powder_texture_axes as TX

TEXTURE_AXES_DIR = "docs/roadmap/palt_m6/texture_axes"
CACHED_ENERGIES = ("docs/roadmap/palt_m6/independence_sweeps/"
                   "family_energies.json")
DERIVABLE = ("SHIMMER", "POWDER_METALLIC", "BAKED", "MARBLED")
NEVER_IN_TEXTURE_CENSUS = ("GLITTER",)


class EnergyRecoveryError(RuntimeError):
    """No committed record supports the requested energy."""


#: A114 — per-axis stamps carried by the energy-control record. A
#: value's invariance verdict travels WITH the value so a future
#: citation is stopped by the stamp, not by someone remembering (the
#: A95 move applied to control coverage).
STAMP_INVARIANT = "ENERGY_INVARIANT_AT_CONDITION"
STAMP_NOT_INVARIANT = "NOT_ENERGY_INVARIANT_AT_CONDITION"


class StampedAxisError(RuntimeError):
    """The cited axis value is not stamped energy-invariant. Raised,
    never warned — the citing path enforces what 1p would otherwise
    leave to future vigilance."""


def read_stamped_axis(control_record, family, axis):
    """A114 — the only sanctioned way to cite a texture-axis value
    from the energy-control frames. Returns the stamped entry when the
    axis is ENERGY_INVARIANT_AT_CONDITION with its cleared range (2m);
    raises on a NOT_ENERGY_INVARIANT stamp or an absent one."""
    if "families" not in control_record:
        raise StampedAxisError(
            "record carries no families block — not an energy-control "
            "record; refusing to read")
    fams = control_record["families"]
    if family not in fams:
        raise StampedAxisError(
            f"{family} has no energy-control entry — the axis value "
            "is unvalidated at condition; refusing to read")
    axes = fams[family]["axes"]
    if axis not in axes:
        raise StampedAxisError(
            f"{family}.{axis} was not measured on the control frames "
            "— refusing to read")
    entry = axes[axis]
    if "stamp" not in entry:
        raise StampedAxisError(
            f"{family}.{axis} carries no stamp — its invariance was "
            "never adjudicated; refusing to read")
    if entry["stamp"] != STAMP_INVARIANT:
        raise StampedAxisError(
            f"{family}.{axis} is stamped {entry['stamp']} on these "
            "frames — a value that is not energy-invariant at the "
            "condition may not be cited from them")
    return entry


def _planar(kind, family):
    path = os.path.join(TEXTURE_AXES_DIR,
                        f"swatch_{kind}_census_{family}.json")
    if not os.path.exists(path):
        raise EnergyRecoveryError(
            f"no committed {kind} record for {family} at {path}")
    with open(path) as f:
        return json.load(f)["regions"]["PLANAR"], path


def read_cached_energy(family):
    """The committed-value branch: families whose census-era energy
    was written to family_energies.json (63bb0a9)."""
    with open(CACHED_ENERGIES) as f:
        cached = json.load(f)
    if family not in cached:
        raise EnergyRecoveryError(
            f"{family} is not in the committed energy cache "
            f"{CACHED_ENERGIES}")
    return {"family": family, "energy": cached[family],
            "status": "COMMITTED_VALUE",
            "read_from": CACHED_ENERGIES}


def derive_census_energy(family):
    """The derivation branch: exact re-computation of the committed
    solve from committed inputs, conditional on single-iteration
    convergence, which the returned record states rather than hides."""
    if family in NEVER_IN_TEXTURE_CENSUS:
        raise EnergyRecoveryError(
            f"{family} was never in the texture census — no "
            "calibration exists; nothing to recover or replicate")
    if family not in DERIVABLE:
        raise EnergyRecoveryError(
            f"{family} has no committed calibrating quartet; use "
            "read_cached_energy for committed-value families")
    probe, probe_path = _planar("probe", family)
    base, base_path = _planar("base", family)
    cal, cal_path = _planar("cal", family)
    ref = PR.glitter_rig_overrides()["specular_source"]["energy"]
    base_peak = float(base["scene_linear_peak"])
    probe_peak = float(probe["scene_linear_peak"])
    spec_contrib = max(probe_peak - base_peak, 1e-6)
    energy = ref * (TX.CAL_TARGET - base_peak) / spec_contrib
    lo, hi = TX.SUBJECT_WINDOW
    cal_peak = float(cal["scene_linear_peak"])
    if cal["clipped_sample_count"] != 0 or not lo <= cal_peak <= hi:
        raise EnergyRecoveryError(
            f"{family}: committed cal frame does not satisfy the "
            "convergence conditions the law required — the committed "
            "quartet is not a converged calibration; derivation "
            "refused")
    return {
        "family": family, "energy": energy,
        "status": "EXACT_IFF_SINGLE_ITERATION_CONVERGENCE",
        "law": ("E1 = ref * (CAL_TARGET - base_peak) / "
                "(probe_peak - base_peak); "
                "palette_powder_texture_axes.characterize_texture_pair"),
        "inputs": {"ref": ref, "cal_target": TX.CAL_TARGET,
                   "probe_peak": probe_peak, "base_peak": base_peak,
                   "probe_path": probe_path, "base_path": base_path},
        "consistent_committed_evidence": {
            "cal_path": cal_path, "cal_peak": cal_peak,
            "cal_clipped": cal["clipped_sample_count"],
            "window": [lo, hi]},
        "verification_that_would_prove_it": (
            "re-render the cal frame at this energy (same spec, seed "
            "and half samples) and compare scene-linear pixels to the "
            "committed cal EXR; pixel identity proves the committed "
            "cal frame IS the iteration-one render, i.e. the census "
            "energy is exactly this value"),
    }
