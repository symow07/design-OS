"""M6 — BAKED_GEOMETRY_RIG: raking light across the pan profile.

Twice load-bearing: the PRESSED-vs-BAKED instrument, and the
pre-committed third channel for the diffuse pairs if GRANULARITY x
lobe crosses the ceiling. Commissioned to the harder job:

- the flat threshold comes from a seed-varied ENSEMBLE of flat pressed
  controls (max statistic — conservative), hashed STRICTLY before any
  BAKED frame exists; R4 applies to thresholds, not only axes;
- each raking axis is correlated against GRANULARITY_INDEX and the
  lobe cluster on the family census at commissioning; a raking axis
  >= 0.80 with GRANULARITY is texture-RMS in raking clothes and VOIDS
  the crossing pre-commitment — decided here, not under rescue;
- window conflicts (grazing incidence vs [0.35, 0.92]) are resolved by
  the INSTRUMENT (source energy), never the window or the elevation;
- axes are LOW-FREQUENCY by construction (Blender-side 32x32 region
  grids — no display frame anywhere), so high-frequency texture
  averages out before the statistic sees it.

AXES, declared before any frame:
- RAKING_DIRECTIONAL_SPAN (independent): the POWDER-region grid's
  column means along the light axis, (mean of brightest quartile -
  mean of darkest quartile) / region median. A dome produces a
  monotone bright-to-dark ramp; a flat pan does not.
- RAKING_SHADOW_FRACTION (independent): fraction of POWDER grid cells
  below 0.5 x region median — the self-shadow a dome casts on its far
  side. Different statistic, different physical mechanism (occlusion
  versus illumination angle).
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile

import numpy as np

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import palette_statistics as ST
from apps.pipeline.services import palette_baked_geometry as BG
from apps.pipeline.services import palette_characterization_rig as CR
from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP

SCHEMA = "baked_geometry_rig/1.0"

RIG = {
    "camera": {"azimuth": 0.0, "elevation": 55.0, "distance": 300.0,
               "ortho_scale": 40.0},
    "raking_source": {"azimuth": 90.0, "elevation": 10.0,
                      "distance": 300.0, "size": 120.0,
                      "energy": 2.0e5},
    "fill_source": {"azimuth": 210.0, "elevation": 40.0,
                    "distance": 400.0, "size": 200.0, "energy": 3.0e3},
    "raking_elevation_deg_max": 12.0,
    "window": [0.35, 0.92],
    "pan_inner_w": 22.6, "pan_inner_d": 16.6,
}

RAKING_AXES = {
    "RAKING_DIRECTIONAL_SPAN": {"independent": True},
    "RAKING_SHADOW_FRACTION": {"independent": True},
}
FLOOR_SEEDS = (300, 301, 302, 303, 304, 305)
SEPARATION_MARGIN = 2.0
PASS_BAR = 0.25


class RakingRigError(RuntimeError):
    pass


def _fixture_meshes(td, spec_params):
    vol = BG.build_powder_volume(
        spec_params, pan_inner_w=RIG["pan_inner_w"],
        pan_inner_d=RIG["pan_inner_d"], z_floor=0.0)
    path = os.path.join(td, "POWDER.obj")
    gvr.export_obj({"vertices": vol["vertices"],
                    "faces": vol["faces"]}, path)
    return {"POWDER": path}, vol


def _cfg(td, spec, spec_params, *, energy=None):
    meshes, vol = _fixture_meshes(td, spec_params)
    r = json.loads(json.dumps(RIG))
    if energy is not None:
        r["raking_source"]["energy"] = float(energy)
    if r["raking_source"]["elevation"] > r["raking_elevation_deg_max"]:
        raise RakingRigError("raking elevation exceeds the declared max")
    return {
        "meshes": meshes,
        "smooth_regions": ["POWDER"],
        "centre": [0.0, 0.0, vol["top_z_flat"]],
        "resolution": [900, 900], "samples": 48,
        "clamp_indirect": 4.0,
        "backdrop_colour": [0.05, 0.05, 0.055],
        "backdrop_strength": 0.2,
        "diffuse_source": {**r["fill_source"]},
        "specular_source": {**r["raking_source"]},
        "fill_source": {"azimuth": 0, "elevation": 60, "distance": 400,
                        "size": 100, "energy": 0.0},
        "camera": r["camera"],
        "region_colours": {"POWDER": [1.0, 0.2, 0.2]},
        "lighting_contract_identity": hashlib.sha256(
            json.dumps(r, sort_keys=True).encode()).hexdigest()[:16],
        "geometry_identity": vol["powder_geometry_identity"],
        "camera_identity": hashlib.sha256(
            json.dumps(r["camera"], sort_keys=True).encode()
        ).hexdigest()[:16],
    }, vol


_MASK = {}


def _region_indices(out_dir, spec_params, tag):
    if tag in _MASK:
        return _MASK[tag]
    meas = os.path.join(out_dir, f"_raking_mask_{tag}.json")
    if not os.path.exists(meas):
        with tempfile.TemporaryDirectory() as td:
            cfg, _ = _cfg(td, None, spec_params)
            cfg.update({"mask_mode": True,
                        "png": os.path.join(out_dir,
                                            f"raking_mask_{tag}.png"),
                        "exr": os.path.join(td, "m.exr"),
                        "measurements": meas, "samples": 8,
                        "material": {"display_rgb": [0.5, 0.5, 0.5]}})
            CR._run(cfg, td)
    data = json.load(open(meas))
    idx = [i for i, (r, g, b) in enumerate(data["rgb"])
           if r > 0.5 and g < 0.4 and (r + g + b) > 0.3]
    if len(idx) < 500:
        raise RakingRigError("POWDER region mask resolved too small")
    _MASK[tag] = {"POWDER": idx}
    return _MASK[tag]


def measure(spec, out_dir, label, *, energy=None, samples=48) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    params = spec.params
    tag = "domed" if params.get("dome") else "flat"
    idx = _region_indices(out_dir, params, tag)
    png = os.path.join(out_dir, f"{label}.png")
    exr = os.path.join(out_dir, f"{label}.exr")
    meas = os.path.join(out_dir, f"{label}.json")
    with tempfile.TemporaryDirectory() as td:
        cfg, vol = _cfg(td, spec, params, energy=energy)
        cfg.update({"material": spec.realize(), "png": png, "exr": exr,
                    "measurements": meas, "region_indices": idx,
                    "region_grids": True,
                    "material_identity": spec.material_identity(),
                    "render_identity": hashlib.sha256(
                        (label + cfg["lighting_contract_identity"])
                        .encode()).hexdigest()[:16]})
        if samples:
            cfg["samples"] = samples
        CR._run(cfg, td)
    data = json.load(open(meas))
    data["png"], data["exr"], data["label"] = png, exr, label
    data["powder_geometry_identity"] = vol["powder_geometry_identity"]
    return data


def raking_axes(measurement) -> dict:
    region = measurement["regions"]["POWDER"]
    grid = np.array(region["grid"], dtype=float)
    med = float(region["scene_linear_median"])
    if med <= 0:
        raise RakingRigError("POWDER median is zero — refusing")
    cols = np.nanmean(np.where(grid > 0, grid, np.nan), axis=0)
    cols = cols[~np.isnan(cols)]
    if cols.size < 8:
        raise RakingRigError("too few grid columns to measure a ramp")
    q = max(cols.size // 4, 1)
    srt = np.sort(cols)
    span = float(srt[-q:].mean() - srt[:q].mean()) / med
    cells = grid[grid > 0]
    shadow = float((cells < 0.5 * med).mean())
    return {"RAKING_DIRECTIONAL_SPAN": round(span, 6),
            "RAKING_SHADOW_FRACTION": round(shadow, 6)}


def _window_guard(measurement, label):
    r = measurement["regions"]["POWDER"]
    peak = float(r["scene_linear_peak"])
    if r["clipped_sample_count"] > 0:
        raise RakingRigError(f"{label} clipped — instrument must change")
    if not (RIG["window"][0] <= peak <= RIG["window"][1]):
        raise RakingRigError(
            f"{label} peak {peak:.3f} outside {RIG['window']} — the "
            f"response is the INSTRUMENT (energy), never the window or "
            f"the elevation")
    return peak


def commission_raking_rig(out_dir, *, samples=48,
                          flat_target=0.80, _attempts=None) -> dict:
    """The full commissioning, order non-negotiable: calibrate ->
    flat ensemble -> hash thresholds -> ONLY THEN baked -> census
    correlations -> pressed-vs-baked.

    WINDOW CONFLICT RESOLUTION (instrument-only, recorded): the dome's
    light-facing slope catches the raking source far steeper than any
    flat control, so an energy calibrated on flat can clip on the
    dome. When BAKED clips, the hashed thresholds are VOIDED on the
    record and the whole commissioning re-derives at a lower flat
    target — thresholds always come from flat data alone, at the same
    energy as the baked measurement, and no baked axis is ever
    computed before its threshold is fixed. The window and the
    elevation never move."""
    os.makedirs(out_dir, exist_ok=True)
    shade = PE.PowderShade("prov_rake", (0.62, 0.55, 0.48),
                           PE.PROVISIONAL_VISUALIZATION_SHADE)

    def flat_spec(seed):
        return PE.PowderMaterialSpec(PP.PRESSED_POWDER, shade, seed=seed)

    # (1) instrument-only window calibration on the first flat control
    probe = measure(flat_spec(FLOOR_SEEDS[0]), out_dir, "rk_probe",
                    samples=samples)
    peak = float(probe["regions"]["POWDER"]["scene_linear_peak"])
    energy = RIG["raking_source"]["energy"]
    calib = []
    for _ in range(4):
        energy = energy * flat_target / max(peak, 1e-6)
        d = measure(flat_spec(FLOOR_SEEDS[0]), out_dir, "rk_cal",
                    energy=energy, samples=samples)
        r = d["regions"]["POWDER"]
        peak = float(r["scene_linear_peak"])
        calib.append({"energy": energy, "peak": peak,
                      "clipped": r["clipped_sample_count"]})
        if r["clipped_sample_count"] == 0 and \
                RIG["window"][0] <= peak <= RIG["window"][1]:
            break
    else:
        raise RakingRigError(f"window calibration failed: {calib}")

    # (2) flat pressed ENSEMBLE at the calibrated energy
    ensemble = {}
    for seed in FLOOR_SEEDS:
        d = measure(flat_spec(seed), out_dir, f"rk_flat_{seed}",
                    energy=energy, samples=samples)
        _window_guard(d, f"flat_{seed}")
        ensemble[seed] = raking_axes(d)

    floors, thresholds = {}, {}
    for axis in RAKING_AXES:
        vals = [ensemble[s][axis] for s in FLOOR_SEEDS]
        effs = []
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                a, b = vals[i], vals[j]
                mean = (abs(a) + abs(b)) / 2.0
                effs.append(abs(a - b) / mean if mean > 1e-9 else 0.0)
        if len(set(vals)) == 1:
            # all ensemble members identical: the subject cannot vary
            # this axis, so a floor of 0.0 would be a refusal to
            # measure dressed as a measurement — the exact F7/R2
            # signature. The floor must come from a subject with
            # relief before this axis may gate a pair.
            floors[axis] = {"floor": "FLOOR_NOT_MEASURABLE_ON_THIS_"
                                     "SUBJECT",
                            "eligible": False,
                            "required": None,
                            "identical_ensemble_values": vals[0]}
            continue
        floors[axis] = {"floor": round(max(effs), 5),
                        "eligible": bool(max(effs) < PASS_BAR),
                        "required": round(max(PASS_BAR,
                                              max(effs)
                                              * SEPARATION_MARGIN), 5)}
        thresholds[axis] = {"flat_max_value": round(max(vals), 6),
                            "statistic": "MAX over the seed ensemble "
                                         "(conservative)"}
    threshold_hash = hashlib.sha256(json.dumps(
        thresholds, sort_keys=True).encode()).hexdigest()[:16]
    with open(os.path.join(out_dir, "flat_thresholds.json"), "w") as fh:
        json.dump({"thresholds": thresholds,
                   "threshold_hash": threshold_hash,
                   "hashed_strictly_before_any_baked_frame": True,
                   "floors": floors, "calibration": calib,
                   "energy": energy}, fh, indent=2)

    # (3) ONLY NOW: the baked member
    baked_spec = PE.PowderMaterialSpec(PP.BAKED, shade,
                                       seed=FLOOR_SEEDS[0])
    baked = measure(baked_spec, out_dir, "rk_BAKED", energy=energy,
                    samples=samples)
    try:
        _window_guard(baked, "BAKED")
    except RakingRigError:
        attempts = (_attempts or []) + [
            {"flat_target": flat_target, "energy": energy,
             "voided": "BAKED clipped — thresholds re-derived from "
                       "flat data alone at a lower target"}]
        if flat_target <= 0.40:
            raise
        return commission_raking_rig(out_dir, samples=samples,
                                     flat_target=round(
                                         flat_target - 0.20, 2),
                                     _attempts=attempts)
    baked_axes = raking_axes(baked)
    flat_ref = ensemble[FLOOR_SEEDS[0]]
    exceeds = {a: bool(baked_axes[a] > thresholds[a]["flat_max_value"])
               for a in RAKING_AXES}

    rows, counted = {}, []
    for axis in RAKING_AXES:
        a, b = flat_ref[axis], baked_axes[axis]
        mean = (abs(a) + abs(b)) / 2.0
        eff = abs(a - b) / mean if mean > 1e-9 else 0.0
        fl = floors[axis]
        reasons = []
        if fl["required"] is None:
            reasons.append("FLOOR_NOT_MEASURABLE_ON_FLAT")
        elif eff < fl["required"]:
            reasons.append("BELOW_REQUIRED")
        if fl["required"] is not None and not fl["eligible"]:
            reasons.append(f"INELIGIBLE_{fl['floor']}")
        if not exceeds[axis]:
            reasons.append("BELOW_HASHED_FLAT_THRESHOLD")
        if not reasons:
            counted.append(axis)
        rows[axis] = {"flat": a, "baked": b, "effect": round(eff, 5),
                      "exceeds_hashed_threshold": exceeds[axis],
                      "counts": not reasons, "reasons": reasons}

    # (4) census correlations — the third-channel question
    fams = {"POWDER_MATTE": 40, "POWDER_SATIN": 41,
            "PRESSED_POWDER": 47, "CREAM": 48, "SHIMMER": 42,
            "POWDER_METALLIC": 43}
    rak_census, lobe_sheen = {}, {}
    for fam, seed in fams.items():
        spec = PE.PowderMaterialSpec(fam, shade, seed=seed)
        d = measure(spec, out_dir, f"rk_census_{fam}", energy=energy,
                    samples=samples)
        rak_census[fam] = raking_axes(d)
        sw = json.load(open(f"docs/roadmap/palt_m6/swatches/"
                            f"swatch_powder_{fam}.json"))
        lobe_sheen[fam] = float(
            sw["regions"]["SHALLOW_CURVE"]["highlight_fwhm_fraction"])
    gran_vals = json.load(open(
        "docs/roadmap/palt_m6/axis_independence_matrix_n6.json"))["census"]

    def spearman(xs, ys):
        # 1g — the `if den else 0.0` this replaces was a live instance
        # of DEGENERATE_INPUT_PLAUSIBLE_OUTPUT: a constant vector read
        # as 0.0 correlation instead of a refusal. The guard raises.
        return ST.guarded_spearman(xs, ys)

    fam_list = sorted(fams)
    correlations = {}
    third_channel = {}
    for axis in RAKING_AXES:
        xs = np.array([rak_census[f][axis] for f in fam_list])
        g = np.array([gran_vals[f] for f in fam_list])
        s = np.array([lobe_sheen[f] for f in fam_list])
        rho_g = round(abs(spearman(xs, g)), 4)
        rho_s = round(abs(spearman(xs, s)), 4)
        correlations[axis] = {"vs_GRANULARITY": rho_g,
                              "vs_LOBE_SHEEN": rho_s}
        third_channel[axis] = ("VOID_TEXTURE_IN_RAKING_CLOTHES"
                               if rho_g > 0.80 else
                               ("VOID_LOBE_IN_RAKING_CLOTHES"
                                if rho_s > 0.80 else "INDEPENDENT"))

    pre_commit_ok = any(v == "INDEPENDENT"
                        for v in third_channel.values())
    verdict = ("PASS" if len(counted) >= 2 else "FAIL")
    record = {
        "record_type": SCHEMA,
        "rig": RIG, "axes": RAKING_AXES,
        "calibration_instrument_only": calib,
        "voided_attempts": _attempts or [],
        "flat_target_used": flat_target,
        "flat_ensemble": {str(k): v for k, v in ensemble.items()},
        "floors": floors,
        "thresholds_hashed_before_baked": {"hash": threshold_hash,
                                           **thresholds},
        "baked_axes": baked_axes,
        "pair_PRESSED_VS_BAKED": rows,
        "counted_axes": counted,
        "PRESSED_VS_BAKED": verdict,
        "census_correlations": correlations,
        "third_channel_ruling": third_channel,
        "crossing_pre_commitment": ("STANDS" if pre_commit_ok
                                    else "VOID"),
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
    with open(os.path.join(out_dir, "raking_commissioning.json"),
              "w") as fh:
        json.dump(record, fh, indent=2)
    return record
