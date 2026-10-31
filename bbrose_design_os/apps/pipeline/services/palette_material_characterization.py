"""M5 §4/§6/§7/§8/§10 — material characterization on the standard swatch.

Measures intrinsic material response, in SCENE-LINEAR data, on one shared
fixture. The palette's three-quarter view could not separate matte from
satin; this decides whether that was the view or the materials.

Everything here is engineering characterization. §9 still requires the
same two contracts to show a visible difference on real P1B geometry —
passing here does not excuse that.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile

import numpy as np

from apps.pipeline.services import geometry_validation_render as gvr
from apps.pipeline.services import palette_material_engine as ME
from apps.pipeline.services import palette_material_swatch as SW
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "palette_material_characterization/1.0"
VERSION = 1

SCRIPT = os.path.join(os.path.dirname(gvr.SCRIPT), "palette_csg_views.py")

#: §4 — lighting designed to expose BRDF differences WITHOUT clipping.
#: A broad soft key gives the diffuse base, a controlled grazing strip
#: gives the specular lobe its length, and the fill stays restrained so
#: nothing washes out. Energies are well below the M4B-B legibility rig,
#: which clipped at p99 253.7 of 255 and destroyed exactly the signal
#: these axes read.
CHARACTERIZATION_CONTRACT = {
    "schema": "material_characterization_render_contract/1.0",
    "version": VERSION,
    "purpose": "EXPOSE_BRDF_DIFFERENCES_WITHOUT_CLIPPING",
    "backdrop_colour": [0.18, 0.18, 0.19],
    "backdrop_strength": 0.30,
    "key_energy": 9.0e4,
    "fill_energy": 2.2e4,
    "rim_energy": 2.6e5,
    "second_rim_energy": 0.0,
    "grazing_strip": "the rim acts as the controlled grazing strip light",
    "beauty_lighting": False,
    "depth_of_field": False,
    "bloom": False,
    "exposure": 0.0,
    "view_transform": "Standard",
    "camera_mode": "ORTHOGRAPHIC",
    "camera": "three_quarter",
    "seed": 0,
    "samples": 64,
    "resolution": [1400, 1400],
    "scene_linear_diagnostic_artifact": "OPEN_EXR_32BIT",
    "scene_linear_statistics": "computed by Blender from its own float "
                               "render result and reported on stdout",
    "measured_from": "PNG_HIGHEST_AVAILABLE_BIT_DEPTH",
    "why_not_measured_from_exr": "no EXR reader is installed in this "
                                 "environment. The EXR is preserved and "
                                 "Blender reports the scene-linear peak "
                                 "and clipping counts, so a clipped "
                                 "highlight is detected; claiming a "
                                 "scene-linear measurement that cannot be "
                                 "performed would be worse than stating "
                                 "the limit.",
    "png_evidence_also_produced": True,
}


def contract_identity() -> str:
    return hashlib.sha256(
        json.dumps(CHARACTERIZATION_CONTRACT,
                   sort_keys=True).encode()).hexdigest()[:16]


class CharacterizationError(RuntimeError):
    """Raised when characterization cannot be performed honestly."""


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _blender_config():
    c = CHARACTERIZATION_CONTRACT
    return {
        "backdrop_colour": c["backdrop_colour"],
        "backdrop_strength": c["backdrop_strength"],
        "key_energy": c["key_energy"],
        "fill_energy": c["fill_energy"],
        "rim_energy": c["rim_energy"],
        "rim2": None,
        "render_contract_version": VERSION,
    }


def render_swatch(material_spec, out_png, out_exr, *, samples=None,
                  exposure_scale=1.0, out_png16=None) -> dict:
    """Render the shared swatch under one material.

    ``exposure_scale`` exists only for §7's negative fixture: it changes
    the light, never the material, so the discriminator must not mistake
    it for a material difference.
    """
    c = CHARACTERIZATION_CONTRACT
    swatch = SW.build_swatch()
    lo, hi = swatch["vertices"].min(axis=0), swatch["vertices"].max(axis=0)
    centre = ((lo + hi) / 2.0).tolist()
    scale = float(max(hi - lo)) * 1.12

    with tempfile.TemporaryDirectory() as td:
        obj = os.path.join(td, "swatch.obj")
        gvr.export_obj({"vertices": swatch["vertices"],
                        "faces": swatch["faces"]}, obj)
        cfg = {
            **_blender_config(),
            "meshes": {"material_swatch": obj},
            "csg": {}, "section": None,
            "resolution": list(c["resolution"]),
            "samples": samples or c["samples"],
            "centre": centre, "ortho_scale": scale,
            "camera_distance": max(400.0, scale * 4.0),
            "smooth_prefixes": ["material_swatch"],
            "technical_tones": False,
            "materials": {"material_swatch": material_spec},
            "detail_views": {},
            "views": {c["camera"]: out_png},
            "exr_views": {c["camera"]: out_exr},
            "png16_views": {c["camera"]:
                            out_png16 or out_png.replace(".png",
                                                         "_16.png")},
        }
        cfg["key_energy"] *= exposure_scale
        cfg["fill_energy"] *= exposure_scale
        cfg["rim_energy"] *= exposure_scale
        p = os.path.join(td, "cfg.json")
        json.dump(cfg, open(p, "w"))
        r = subprocess.run(
            [gvr.BLENDER, "-b", "--factory-startup", "-noaudio", "-P",
             SCRIPT, "--", p], capture_output=True, text=True, timeout=5400)
        if "PALETTE_CSG_VIEWS_OK" not in r.stdout:
            raise CharacterizationError(
                r.stdout[-1200:] + r.stderr[-400:])
        stats = {}
        for line in r.stdout.splitlines():
            if line.startswith("SCENE_LINEAR_STATS "):
                stats = json.loads(line.split(" ", 1)[1])
    png16 = out_png16 or out_png.replace(".png", "_16.png")
    for path in (out_png, out_exr, png16):
        if not os.path.exists(path):
            raise CharacterizationError(f"{path} was not written")
    return {"png": out_png, "exr": out_exr, "png16": png16,
            "scene_linear_stats": stats,
            "swatch_geometry_identity": swatch["swatch_geometry_identity"],
            "render_contract_identity": contract_identity(),
            "exposure_scale": exposure_scale}


# --------------------------------------------------------------------------
# §6/§10 — scene-linear measurement
# --------------------------------------------------------------------------

def _linear(path):
    """Luminance in 0-1 from the 16-bit PNG.

    Sixteen bits gives 65536 levels, so a specular lobe keeps its shape.
    The EXR beside it is the preserved scene-linear artifact and Blender's
    reported peak proves the highlight was not clipped.
    """
    from PIL import Image
    img = Image.open(path)
    raw = np.asarray(img)
    scale = 65535.0 if raw.dtype == np.uint16 else 255.0
    arr = raw.astype(np.float32)
    if arr.ndim == 2:
        return arr / scale
    return arr[:, :, :3].mean(axis=2) / scale


def optical_axes(exr_path) -> dict:
    """The six physical discriminators, measured in scene-linear data.

    A specular lobe carries its information in the shape and height of
    its highlight, not in the average brightness of the image, so these
    read the lobe.
    """
    lum = _linear(exr_path)
    finite = lum[np.isfinite(lum)]
    if finite.size == 0:
        raise CharacterizationError(f"{exr_path}: no finite data")
    bg = float(np.percentile(finite, 5))
    subject = lum > (bg + 0.02)
    if subject.sum() < 500:
        raise CharacterizationError(f"{exr_path}: no subject to measure")
    vals = lum[subject]
    peak = float(np.percentile(vals, 99.9))
    diffuse = float(np.percentile(vals, 50))

    # highlight full width at half maximum, measured as the fraction of
    # subject pixels above the half-height between diffuse and peak
    half = diffuse + 0.5 * (peak - diffuse)
    fwhm_fraction = float((vals > half).mean())

    # the grazing ramp is the lowest band of the image in the render, and
    # the bevel the narrow band just above it; both are read by row
    rows = np.where(subject.any(axis=1))[0]
    lo_r, hi_r = int(rows.min()), int(rows.max())
    span = max(1, hi_r - lo_r)
    grazing_band = lum[hi_r - int(span * 0.18):hi_r + 1]
    bevel_band = lum[lo_r + int(span * 0.55):lo_r + int(span * 0.72)]
    sheen_band = lum[lo_r + int(span * 0.20):lo_r + int(span * 0.42)]

    def band_response(band):
        m = band > (bg + 0.02)
        if m.sum() < 50:
            return 0.0
        b = band[m]
        return float(np.percentile(b, 95) / max(np.percentile(b, 50),
                                                1e-6))

    return {
        "HIGHLIGHT_FWHM": round(fwhm_fraction, 8),
        "HIGHLIGHT_PEAK": round(peak, 8),
        "SPECULAR_TO_DIFFUSE_RATIO": round(peak / max(diffuse, 1e-6), 8),
        "GRAZING_RESPONSE": round(band_response(grazing_band), 8),
        "SHEEN_REGION_RESPONSE": round(band_response(sheen_band), 8),
        "EDGE_HIGHLIGHT_RESPONSE": round(band_response(bevel_band), 8),
        "_diagnostics": {
            "peak_linear_intensity": round(float(finite.max()), 8),
            "diffuse_median": round(diffuse, 8),
            "clipping_count": int((lum >= 1.0).sum()),
            "saturated_pixel_count": int((lum >= 0.999).sum()),
            "subject_fraction": round(float(subject.mean()), 8),
            "percentile_response": {
                str(p): round(float(np.percentile(vals, p)), 8)
                for p in (5, 25, 50, 75, 95, 99)},
        },
    }


def normalized(axes) -> dict:
    """§7 — divide out overall brightness.

    A material must not be judged different merely because its render is
    brighter. Ratios are already exposure-invariant; the absolute peak is
    normalised by the diffuse level.
    """
    d = axes["_diagnostics"]["diffuse_median"] or 1e-6
    out = dict(axes)
    out["HIGHLIGHT_PEAK"] = round(axes["HIGHLIGHT_PEAK"] / d, 8)
    return out


def discriminate(axes_a, axes_b, label_a, label_b, *,
                 use_normalized=True) -> dict:
    """Apply the predeclared pass law."""
    a = normalized(axes_a) if use_normalized else axes_a
    b = normalized(axes_b) if use_normalized else axes_b
    rows, clearing = {}, []
    for axis in SW.DISCRIMINATOR_AXES:
        va, vb = float(a[axis]), float(b[axis])
        mean = (abs(va) + abs(vb)) / 2.0
        effect = abs(va - vb) / mean if mean > 1e-9 else FT.traced_zero("palette_material_characterization.py:discriminate", "guard")
        clears = effect >= SW.MINIMUM_RELATIVE_EFFECT
        rows[axis] = {"a": round(va, 6), "b": round(vb, 6),
                      "relative_effect": round(effect, 6),
                      "bar": SW.MINIMUM_RELATIVE_EFFECT,
                      "clears": bool(clears)}
        if clears:
            clearing.append(axis)
    ok = len(clearing) >= SW.REQUIRED_DISCRIMINATING_AXES
    return {
        "a": label_a, "b": label_b,
        "measured_in": "SCENE_LINEAR",
        "normalized": use_normalized,
        "axes": rows,
        "axes_clearing": clearing,
        "axes_required": SW.REQUIRED_DISCRIMINATING_AXES,
        "verdict": "PASS" if ok else "FAIL",
        "pass_law": SW.PASS_LAW["statement"],
    }


def spec_for(material, finish, rgb=(0.62, 0.62, 0.63)) -> dict:
    """The resolved material spec the renderer consumes."""
    return ME.MaterialAssignment("*", material, finish,
                                 ME.Colour(rgb=rgb)).resolved()
