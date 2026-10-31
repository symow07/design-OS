"""M5 §1-§8 — the specular-capable characterization rig and its driver.

The previous rig used one broad soft source and produced
SPECULAR_TO_DIFFUSE_RATIO ~1.1 — essentially pure diffuse, so five of the
six discriminators had nothing to read. This rig keeps a broad source for
the diffuse base and adds a COMPACT source to excite a measurable
reflection lobe, with a restrained fill so shadows do not collapse.

Numbers come from Blender's float Render Result via
``material_characterization.py``. Nothing here derives a scene-linear
claim from a PNG.

The rig is a reusable M5/M6 asset, so §3 requires it to work for every
finish rather than for matte-versus-satin alone, and §8 requires the
verdict to survive small perturbations of light, camera and exposure.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import palette_material_engine as ME
from apps.pipeline.services import palette_material_swatch as SW
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "material_characterization_rig/2.0"
VERSION = 2

SCRIPT = os.path.join(os.path.dirname(gvr.SCRIPT),
                      "material_characterization.py")

#: §2 — every parameter named, so the rig is a contract rather than a
#: setup someone once found looked good.
RIG = {
    "schema": SCHEMA, "version": VERSION,
    "purpose": "MATERIAL_CHARACTERIZATION_NOT_PRESENTATION",

    "diffuse_source": {
        "role": "BROAD_DIFFUSE_BASE",
        "size": 220.0, "distance": 420.0,
        "azimuth": -38.0, "elevation": 46.0, "energy": 4.2e4,
    },
    #: The correction. Small enough to keep a lobe, large enough to avoid
    #: point-source aliasing, bright enough to register, dim enough not to
    #: clip.
    "specular_source": {
        "role": "COMPACT_SPECULAR_EXCITATION",
        # 2.4e6 drove peak scene-linear to 1.38 with 128k clipped
        # samples, outside the window declared above. The window is the
        # contract, so the light came down rather than the window going up.
        "size": 14.0, "distance": 300.0,
        "azimuth": 26.0, "elevation": 34.0, "energy": 9.0e5,
    },
    "fill_source": {
        "role": "LOW_LEVEL_FILL_NO_SHADOW_COLLAPSE",
        "size": 300.0, "distance": 460.0,
        "azimuth": 150.0, "elevation": 22.0, "energy": 7.0e3,
    },
    "camera": {"azimuth": 30.0, "elevation": 28.0, "distance": 420.0,
               "ortho_scale": 84.0},

    "backdrop_colour": [0.05, 0.05, 0.055],
    "backdrop_strength": 0.22,
    "samples": 64,
    "clamp_indirect": 4.0,
    "resolution": [1200, 1200],
    "view_transform": "Standard", "exposure": 0.0, "seed": 0,
    "camera_mode": "ORTHOGRAPHIC",
    "beauty_lighting": False, "depth_of_field": False, "bloom": False,

    #: §2 — the operating window, declared before the final measurement.
    #: Brightness is not maximised; it is held inside a band where a lobe
    #: exists and nothing clips.
    "target_peak_scene_linear": [0.35, 0.92],
    "maximum_clipped_samples": 0,
}


def rig_identity() -> str:
    return hashlib.sha256(
        json.dumps(RIG, sort_keys=True).encode()).hexdigest()[:16]


class RigError(RuntimeError):
    """Raised when the rig cannot produce an honest measurement."""


def _swatch_centre():
    lo, hi = SW.swatch_bounds()
    return ((lo + hi) / 2.0).tolist()


def _export_regions(td):
    regions = SW.build_swatch_regions()
    meshes = {}
    for name, mesh in regions.items():
        path = os.path.join(td, f"{name}.obj")
        gvr.export_obj(mesh, path)
        meshes[name] = path
    return meshes


def _run(cfg, td):
    p = os.path.join(td, "cfg.json")
    json.dump(cfg, open(p, "w"))
    r = subprocess.run(
        [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
         SCRIPT, "--", p], capture_output=True, text=True, timeout=5400)
    if "MATERIAL_CHARACTERIZATION_OK" not in r.stdout:
        raise RigError(r.stdout[-1500:] + r.stderr[-500:])


def _base_cfg(td, overrides=None):
    o = overrides or {}
    rig = json.loads(json.dumps(RIG))
    for key in ("diffuse_source", "specular_source", "fill_source",
                "camera"):
        rig[key].update(o.get(key, {}))
    return {
        "meshes": _export_regions(td),
        "smooth_regions": ["SHALLOW_CURVE", "QUARTER_CYLINDER", "BEVEL"],
        "centre": _swatch_centre(),
        "resolution": list(rig["resolution"]),
        "samples": o.get("samples", rig["samples"]),
        "clamp_indirect": rig["clamp_indirect"],
        "backdrop_colour": rig["backdrop_colour"],
        "backdrop_strength": rig["backdrop_strength"],
        "diffuse_source": rig["diffuse_source"],
        "specular_source": rig["specular_source"],
        "fill_source": rig["fill_source"],
        "camera": rig["camera"],
        "region_colours": SW.REGION_COLOURS,
        "lighting_contract_identity": rig_identity(),
        "geometry_identity": SW.build_swatch()["swatch_geometry_identity"],
        "camera_identity": hashlib.sha256(
            json.dumps(rig["camera"], sort_keys=True).encode()
        ).hexdigest()[:16],
    }


_MASK_CACHE: dict = {}


def region_indices(out_dir) -> dict:
    """Pixel indices per region, from a mask rendered once.

    Same geometry, same camera, so one mask serves every material.
    """
    key = rig_identity()
    if key in _MASK_CACHE:
        return _MASK_CACHE[key]
    os.makedirs(out_dir, exist_ok=True)
    meas = os.path.join(out_dir, "_region_mask.json")
    png = os.path.join(out_dir, "region_mask.png")
    if not os.path.exists(meas):
        with tempfile.TemporaryDirectory() as td:
            cfg = _base_cfg(td)
            cfg.update({"mask_mode": True, "png": png,
                        "exr": os.path.join(td, "mask.exr"),
                        "measurements": meas, "samples": 8})
            _run(cfg, td)
    data = json.load(open(meas))
    idx: dict = {r: [] for r in SW.REGION_COLOURS}
    for i, (r, g, b) in enumerate(data["rgb"]):
        for name, colour in SW.REGION_COLOURS.items():
            if (abs(r - colour[0]) < 0.25 and abs(g - colour[1]) < 0.25
                    and abs(b - colour[2]) < 0.25
                    and (r + g + b) > 0.3):
                idx[name].append(i)
                break
    thin = {k: v for k, v in idx.items() if len(v) >= 200}
    if len(thin) < 4:
        raise RigError(
            f"the region mask resolved only {sorted(thin)}; a measurement "
            "cannot say which surface it came from")
    _MASK_CACHE[key] = thin
    return thin


def characterize_powder(powder_spec, out_dir, *, label=None,
                        overrides=None, samples=None) -> dict:
    """M6: render the swatch under a POWDER family and measure it.

    Same rig, same windows, same measurement path — the powder block
    goes through cfg["material"] and the script dispatches on
    powder_family, so there is no separate powder pipeline to drift.
    """
    os.makedirs(out_dir, exist_ok=True)
    spec = powder_spec.realize()
    name = label or f"powder_{spec['powder_family']}"
    png = os.path.join(out_dir, f"swatch_{name}.png")
    png16 = os.path.join(out_dir, f"swatch_{name}_16bit.png")
    exr = os.path.join(out_dir, f"swatch_{name}.exr")
    meas = os.path.join(out_dir, f"swatch_{name}.json")
    idx = region_indices(out_dir)
    with tempfile.TemporaryDirectory() as td:
        cfg = _base_cfg(td, overrides)
        cfg.update({
            "material": spec, "png": png, "exr": exr, "png16": png16,
            "measurements": meas, "region_indices": idx,
            "material_identity": spec["material_identity"],
            "render_identity": hashlib.sha256(
                (name + rig_identity()
                 + json.dumps(overrides or {}, sort_keys=True)).encode()
            ).hexdigest()[:16],
        })
        if samples:
            cfg["samples"] = samples
        _run(cfg, td)
    data = json.load(open(meas))
    data["png"] = png
    data["png16"] = png16
    data["exr"] = exr
    data["label"] = name
    return data


def characterize(material, finish, out_dir, *, label=None, overrides=None,
                 samples=None, rgb=(0.62, 0.62, 0.63)) -> dict:
    """Render the swatch under one material and measure it."""
    os.makedirs(out_dir, exist_ok=True)
    name = label or f"{material}_{finish}"
    png = os.path.join(out_dir, f"swatch_{name}.png")
    exr = os.path.join(out_dir, f"swatch_{name}.exr")
    meas = os.path.join(out_dir, f"swatch_{name}.json")
    spec = ME.MaterialAssignment("*", material, finish,
                                 ME.Colour(rgb=rgb)).resolved()
    idx = region_indices(out_dir)
    with tempfile.TemporaryDirectory() as td:
        cfg = _base_cfg(td, overrides)
        cfg.update({
            "material": spec, "png": png, "exr": exr,
            "measurements": meas, "region_indices": idx,
            "material_identity": hashlib.sha256(
                json.dumps(spec, sort_keys=True).encode()
            ).hexdigest()[:16],
            "render_identity": hashlib.sha256(
                (name + rig_identity()
                 + json.dumps(overrides or {}, sort_keys=True)).encode()
            ).hexdigest()[:16],
        })
        if samples:
            cfg["samples"] = samples
        _run(cfg, td)
    data = json.load(open(meas))
    data["png"] = png
    data["exr"] = exr
    data["label"] = name
    return data


# --------------------------------------------------------------------------
# §5/§6 — the six axes, from the scene-linear measurement
# --------------------------------------------------------------------------

def axes_from(measurement) -> dict:
    """Map the region measurements onto the six declared axes."""
    r = measurement["regions"]

    def get(region, key, default=0.0):
        return float(r.get(region, {}).get(key, default))

    planar = "PLANAR" if "PLANAR" in r else next(iter(r))
    curve = "QUARTER_CYLINDER" if "QUARTER_CYLINDER" in r else planar
    # §6 independence: five of the six axes previously read the SAME
    # scalar — peak divided by median — from five regions. Those are
    # transformations of one quantity, not five independent axes, and they
    # all describe how TALL a highlight is. What separates a matte from a
    # satin is how WIDE it is, so each region axis now reports its own
    # lobe width. Height is still represented, once, by HIGHLIGHT_PEAK.
    return {
        "HIGHLIGHT_FWHM": get(curve, "highlight_fwhm_fraction"),
        "HIGHLIGHT_PEAK": get(curve, "scene_linear_p999"),
        "SPECULAR_TO_DIFFUSE_RATIO": get(curve,
                                         "specular_to_diffuse_ratio"),
        "GRAZING_RESPONSE": get("GRAZING", "highlight_fwhm_fraction"),
        "SHEEN_REGION_RESPONSE": get("SHALLOW_CURVE",
                                     "highlight_fwhm_fraction"),
        "EDGE_HIGHLIGHT_RESPONSE": get("BEVEL",
                                       "highlight_fwhm_fraction"),
        "_frame": measurement.get("frame", {}),
        "_regions": {k: {"peak": v["scene_linear_peak"],
                         "median": v["scene_linear_median"],
                         "clipped": v["clipped_sample_count"]}
                     for k, v in r.items()},
    }


def normalized(axes) -> dict:
    """§7 — remove overall brightness.

    Ratios are already exposure-invariant; the absolute peak is divided by
    the frame median so a brighter render cannot masquerade as a different
    material.
    """
    frame = axes.get("_frame", {})
    ref = float(frame.get("percentiles", {}).get("50")
                or frame.get("scene_linear_mean") or 1e-6) or 1e-6
    out = dict(axes)
    out["HIGHLIGHT_PEAK"] = axes["HIGHLIGHT_PEAK"] / ref
    return out


def discriminate(a, b, label_a, label_b, *, use_normalized=True) -> dict:
    """The predeclared pass law, unchanged."""
    xa = normalized(a) if use_normalized else a
    xb = normalized(b) if use_normalized else b
    rows, clearing = {}, []
    for axis in SW.DISCRIMINATOR_AXES:
        va, vb = float(xa[axis]), float(xb[axis])
        mean = (abs(va) + abs(vb)) / 2.0
        effect = abs(va - vb) / mean if mean > 1e-9 else FT.traced_zero("palette_characterization_rig.py:discriminate", "guard")
        clears = effect >= SW.MINIMUM_RELATIVE_EFFECT
        rows[axis] = {"a": round(va, 6), "b": round(vb, 6),
                      "relative_effect": round(effect, 6),
                      "bar": SW.MINIMUM_RELATIVE_EFFECT,
                      "clears": bool(clears)}
        if clears:
            clearing.append(axis)
    ok = len(clearing) >= SW.REQUIRED_DISCRIMINATING_AXES
    return {"a": label_a, "b": label_b, "axes": rows,
            "axes_clearing": clearing,
            "axes_required": SW.REQUIRED_DISCRIMINATING_AXES,
            "measured_in": "SCENE_LINEAR",
            "normalized": use_normalized,
            "verdict": "PASS" if ok else "FAIL",
            "pass_law": SW.PASS_LAW["statement"]}


def rig_operating_window(measurement) -> dict:
    """§2 — did the render land inside the declared window?"""
    frame = measurement.get("frame", {})
    peak = float(frame.get("scene_linear_peak", 0.0))
    clipped = int(frame.get("clipped_sample_count", 0))
    lo, hi = RIG["target_peak_scene_linear"]
    return {
        "scene_linear_peak": round(peak, 6),
        "target_window": [lo, hi],
        "in_window": bool(lo <= peak <= hi),
        "clipped_sample_count": clipped,
        "maximum_clipped_samples": RIG["maximum_clipped_samples"],
        "no_clipping": clipped <= RIG["maximum_clipped_samples"],
        "verdict": "PASS" if (lo <= peak <= hi
                              and clipped <= RIG["maximum_clipped_samples"])
        else "FAIL",
    }
