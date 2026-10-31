"""M6 — read-only forensics on the axis instrument's own frames.

This is NOT part of the instrument and must never be imported by it. It
re-measures frames ALREADY on disk, so it needs no Blender and changes
nothing. Its only job is to answer questions the instrument cannot ask
about itself:

  1. STIMULUS REALIZATION — did the low and high member of a fixture
     pair actually render differently? Without this, `detects: false`
     is ambiguous between "the axis is blind" and "the stimulus never
     landed". That ambiguity is exactly what produced two wrong M6
     verdicts (927ab8a, then 05d481c).
  2. FRAME PROVENANCE — is the file the instrument reads as `png16`
     actually 16-bit, and how many channels does it carry?
  3. READER SENSITIVITY — does the verdict change when the same frames
     are read as (a) the instrument reads them, (b) RGB only, (c) the
     scene-linear EXR? A measurement whose verdict depends on the
     reader is not a measurement.

Run:  python3 docs/roadmap/palt_m6/axis_instrument_forensics.py <dir>
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

PX_PER_MM = 1200.0 / 84.0
EFFECT_BAR = 0.25

#: fixture -> the axis it is the declared POSITIVE fixture for
FIXTURE_TARGET = {
    "SURFACE_CONTINUITY": "GRANULARITY_INDEX",
    "MICRO_NORMAL_CORRELATION": "SURFACE_AUTOCORRELATION_MM",
    "COMPACTION": "GRAZING_BAND_CONTRAST",
}
AXES = ("GRANULARITY_INDEX", "SURFACE_AUTOCORRELATION_MM",
        "GRAZING_BAND_CONTRAST")


# -- readers ---------------------------------------------------------------

def read_as_instrument(path):
    """Exactly what measure_texture_axes does today: mean over EVERY
    channel of the PNG — which for an RGBA frame includes ALPHA."""
    return np.asarray(Image.open(path)).astype(float).mean(axis=2)


def read_rgb(path):
    return np.asarray(Image.open(path)).astype(float)[..., :3].mean(axis=2)


def read_exr(path):
    import cv2
    a = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    return None if a is None else a[..., :3].astype(np.float64).mean(axis=2)


def frame_provenance(path):
    im = Image.open(path)
    a = np.asarray(im)
    return {"path": os.path.basename(path), "pil_mode": im.mode,
            "dtype": str(a.dtype), "channels": int(a.shape[2])
            if a.ndim == 3 else 1, "max_value": int(a.max()),
            "bit_depth_actual": 16 if a.dtype == np.uint16 else 8}


# -- regions ---------------------------------------------------------------

def region_masks(out_dir):
    meta = json.load(open(os.path.join(out_dir, "_region_mask.json")))
    rgb = np.asarray(Image.open(os.path.join(out_dir, "region_mask.png"))
                     .convert("RGB")).astype(float) / 255.0
    return {r: (np.abs(rgb - np.array(c)).sum(axis=2) < 0.15)
            for r, c in meta["region_colours"].items()}


# -- the three texture axes, reader-agnostic -------------------------------

def _high_pass(crop):
    pad = np.pad(crop, 1, mode="edge")
    local = np.zeros_like(crop)
    for dy in range(3):
        for dx in range(3):
            local += pad[dy:dy + crop.shape[0],
                         dx:dx + crop.shape[1]] / 9.0
    return crop - local


def _crop(img, mask):
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    return img[y0:y1 + 1, x0:x1 + 1], mask[y0:y1 + 1, x0:x1 + 1]


def texture_axes(img, masks):
    planar, pm = _crop(img, masks["PLANAR"])
    mean = float(planar[pm].mean())
    hp = _high_pass(planar)
    gran = float(np.sqrt((hp[pm] ** 2).mean())) / mean

    hpn = hp * pm
    var = float((hpn ** 2).sum()) / max(int(pm.sum()), 1)
    lag_mm = 0.0
    if var > 1e-12:
        for lag in range(1, 41):
            sel = pm[:, :-lag] & pm[:, lag:]
            a, b = hpn[:, :-lag][sel], hpn[:, lag:][sel]
            if (float((a * b).mean()) / var if a.size else 0.0) < 0.5:
                lag_mm = lag / PX_PER_MM
                break
        else:
            lag_mm = 40 / PX_PER_MM

    grazing, gm = _crop(img, masks["GRAZING"])
    g = grazing[gm]
    med = float(np.median(g))
    contrast = (float(np.percentile(g, 95) - np.percentile(g, 5)) / med
                if med > 0 else 0.0)
    return {"GRANULARITY_INDEX": gran,
            "SURFACE_AUTOCORRELATION_MM": lag_mm,
            "GRAZING_BAND_CONTRAST": contrast}


def effect(a, b):
    mean = (abs(a) + abs(b)) / 2.0
    return abs(a - b) / mean if mean > 1e-9 else 0.0


# -- the three forensic questions ------------------------------------------

def stimulus_realization(out_dir, masks):
    """Q1 — did the stimulus land? Frame-level, axis-independent."""
    rows = {}
    for fx in FIXTURE_TARGET:
        lo = os.path.join(out_dir, f"swatch_tx_{fx}_low_16bit.png")
        hi = os.path.join(out_dir, f"swatch_tx_{fx}_high_16bit.png")
        if not (os.path.exists(lo) and os.path.exists(hi)):
            continue
        a, b = read_rgb(lo), read_rgb(hi)
        entry = {}
        for reg in ("PLANAR", "GRAZING"):
            m = masks[reg]
            entry[reg] = {
                "bit_identical": bool(np.array_equal(a[m], b[m])),
                "rms_difference_codes": round(
                    float(np.sqrt(((a[m] - b[m]) ** 2).mean())), 4),
                "mean_low": round(float(a[m].mean()), 3),
                "mean_high": round(float(b[m].mean()), 3),
            }
        entry["stimulus_landed"] = bool(
            not entry["PLANAR"]["bit_identical"])
        rows[fx] = entry
    return rows


def reader_sensitivity(out_dir, masks):
    """Q3 — does the verdict depend on how the frame is read?"""
    readers = (("AS_INSTRUMENT_READS_IT", read_as_instrument,
                "_16bit.png"),
               ("RGB_ONLY_8BIT", read_rgb, "_16bit.png"),
               ("EXR_SCENE_LINEAR", read_exr, ".exr"))
    out = {}
    for name, fn, suffix in readers:
        block = {}
        for fx, target in FIXTURE_TARGET.items():
            lo = os.path.join(out_dir, f"swatch_tx_{fx}_low{suffix}")
            hi = os.path.join(out_dir, f"swatch_tx_{fx}_high{suffix}")
            if not (os.path.exists(lo) and os.path.exists(hi)):
                continue
            a, b = fn(lo), fn(hi)
            if a is None or b is None:
                block[fx] = {"error": "unreadable"}
                continue
            A, B = texture_axes(a, masks), texture_axes(b, masks)
            rows = {}
            for ax in AXES:
                e = effect(A[ax], B[ax])
                rows[ax] = {"low": round(A[ax], 6),
                            "high": round(B[ax], 6),
                            "relative_effect": round(e, 4),
                            "detects": bool(e >= EFFECT_BAR)}
            block[fx] = {"target_axis": target,
                         "target_detects": rows[target]["detects"],
                         "axes": rows}
        out[name] = block
    return out


def main(out_dir):
    masks = region_masks(out_dir)
    sample = os.path.join(out_dir, "swatch_tx_SURFACE_CONTINUITY_low"
                                   "_16bit.png")
    record = {
        "record_type": "axis_instrument_forensics/1.0",
        "read_only": True,
        "frames_dir": out_dir,
        "region_pixel_counts": {r: int(m.sum())
                                for r, m in masks.items()},
        "frame_provenance": (frame_provenance(sample)
                             if os.path.exists(sample) else None),
        "stimulus_realization": stimulus_realization(out_dir, masks),
        "reader_sensitivity": reader_sensitivity(out_dir, masks),
    }
    verdicts = {n: {fx: b.get("target_detects")
                    for fx, b in blk.items()}
                for n, blk in record["reader_sensitivity"].items()}
    distinct = {json.dumps(v, sort_keys=True) for v in verdicts.values()}
    record["verdict_depends_on_reader"] = bool(len(distinct) > 1)
    print(json.dumps(record, indent=2))
    return record


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else os.path.join(os.path.dirname(__file__), "texture_axes"))
