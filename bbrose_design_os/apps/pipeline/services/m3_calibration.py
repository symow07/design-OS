"""VQR-2B-A — M3 proportion-distortion calibration series.

Renders equal-height silhouette samples of the IMMUTABLE accepted M3 fit at
a fixed set of horizontal distortion ratios so the owner can calibrate the
provisional BOUNDED_M3_ADAPTATION threshold (1.05_PENDING_VQR_2B_
CALIBRATION) against actual visual evidence.

Boundaries:

* reads ONLY the frozen fit (hash-verified through
  ``m3_backbone.load_m3_fit``) — never reconstruction outputs, never
  production geometry, never task artifacts;
* changes NOTHING in production — the threshold stays selected-but-
  unenforced until a later approved slice implements the refusal;
* only the horizontal deformation varies between samples: same height, same
  visual scale, same colors, line treatment, closure, crop and background;
* samples are NOT pre-labeled PASS/FAIL — the contact sheet shows the
  proposed threshold line, objective geometry values, and a blank owner
  verdict field, with the recommendation clearly marked provisional.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from apps.ire.vq1_close1 import densify
from apps.pipeline.targets.container.m3_backbone import (
    M3_FIT_SHA256,
    load_m3_fit,
)

SCHEMA = "m3_proportion_calibration/1.0"

# §2 owner correction (2026-08-03): ONE canonical proportion definition —
# dense evaluation of the frozen GLASS cubics (sampling-converged at
# per_seg 120/240/480), assembly span INCLUDING the closure. Used for
# proportion calibration, VQR-2B-B comparison, golden expectations and
# future bounded-adaptation enforcement. The VQR-1 record's 3.0787 used
# the freeze record's NOMINAL body_width_px (343) and is superseded for
# policy use; production m3_backbone normalizes by the control-point max
# (172.7 — off-curve) for sizing, flagged for VQR-2B-B alignment.
CANONICAL_SCHEMA = "m3_canonical_proportion_bounds/1.0"
CANONICAL_PER_SEG = 240
CANONICAL_HEIGHT_PX = 1056.0            # assembly span 292..1348
CANONICAL_MAX_HALFWIDTH_PX = 172.5125   # dense GLASS curve max
CANONICAL_WIDTH_PX = 2 * CANONICAL_MAX_HALFWIDTH_PX
CANONICAL_ASPECT = round(CANONICAL_HEIGHT_PX / CANONICAL_WIDTH_PX, 4)


def canonical_bounds() -> dict:
    return {
        "schema": CANONICAL_SCHEMA,
        "source_asset": "docs/visual_quality/vq1_master/master_fit_m3.json "
                        f"(sha {M3_FIT_SHA256[:16]})",
        "contour": "frozen GLASS cubic component, dense-evaluated at "
                   f"per_seg={CANONICAL_PER_SEG} (converged 120/240/480)",
        "closure_included_in_height": True,
        "bounding_box": "assembly span 292..1348 px (height) x 2*max GLASS "
                        "half-width (width), centerline-symmetric",
        "crop_policy": "none — fit measurement space",
        "threshold_policy": "not applicable — vector fit, no pixels",
        "anti_alias_handling": "not applicable — vector fit, no raster",
        "height_px": CANONICAL_HEIGHT_PX,
        "width_px": CANONICAL_WIDTH_PX,
        "max_halfwidth_px": CANONICAL_MAX_HALFWIDTH_PX,
        "aspect_h_over_w": CANONICAL_ASPECT,
    }
RATIOS = (1.000, 1.025, 1.050, 1.075, 1.100, 1.1244, 1.150)
PROPOSED_THRESHOLD = 1.05
THRESHOLD_STATUS = "PROVISIONAL_PENDING_OWNER_CALIBRATION"
TASK_57_RATIO = 1.1244            # the rejected 35×95 policy evidence

SAMPLE_H = 700                    # rendered assembly height (px)
MARGIN = 30
COLORS = {"GLASS": (234, 215, 210), "COLLAR": (183, 110, 121),
          "DARK_CLOSURE": (58, 42, 44)}
OUTLINE = (63, 38, 32)
BG = (255, 255, 255)


def _half_profiles(fit: dict) -> dict:
    """Dense (y_px, halfwidth_px) polylines per component from the frozen
    fit — measurement-space, deterministic (canonical per_seg)."""
    return {name: densify(comp, per_seg=CANONICAL_PER_SEG)
            for name, comp in fit["fits"].items()}


def render_sample(ratio: float, *, fit: dict | None = None) -> Image.Image:
    """One equal-height sample: the M3 assembly with ONLY the horizontal
    dimension multiplied by ``ratio``."""
    fit = fit or load_m3_fit()
    span0, span1 = fit["assembly_span_px"]
    sy = SAMPLE_H / float(span1 - span0)
    profiles = _half_profiles(fit)
    max_hw = max(p[0] for p in profiles["GLASS"])
    base_sx = sy                          # ratio 1.0 == uniform scale
    sx = base_sx * ratio
    width = int(2 * max_hw * sx) + 2 * MARGIN
    img = Image.new("RGB", (width, SAMPLE_H + 2 * MARGIN), BG)
    draw = ImageDraw.Draw(img)
    cx = width / 2.0

    def poly(name):
        pts = [(cx + hw * sx, MARGIN + (y - span0) * sy)
               for hw, y in profiles[name]]
        pts += [(cx - hw * sx, MARGIN + (y - span0) * sy)
                for hw, y in reversed(profiles[name])]
        return pts

    for name in ("GLASS", "COLLAR", "DARK_CLOSURE"):
        draw.polygon(poly(name), fill=COLORS[name])
    draw.line(poly("GLASS") + poly("GLASS")[:1], fill=OUTLINE, width=2)
    return img


def sample_geometry(ratio: float, *, fit: dict | None = None) -> dict:
    """Objective per-sample geometry — no PASS/FAIL labels."""
    fit = fit or load_m3_fit()
    span0, span1 = fit["assembly_span_px"]
    profiles = _half_profiles(fit)
    glass = profiles["GLASS"]
    max_hw = max(p[0] for p in glass)
    native_aspect = (span1 - span0) / (2.0 * max_hw)
    aspect = native_aspect / ratio

    # width-at-normalized-height contour of the whole assembly
    all_pts = [p for comp in profiles.values() for p in comp]
    ys = np.array([p[1] for p in all_pts])
    hws = np.array([p[0] for p in all_pts])
    rows = np.linspace(span0, span1, 64)
    contour = []
    for r in rows:
        near = hws[np.abs(ys - r) <= (span1 - span0) / 128]
        contour.append(round(float(near.max()) * ratio / max_hw, 4)
                       if near.size else 0.0)

    # component facts (widths scale by ratio; heights are unchanged)
    glass_ys = np.array([p[1] for p in glass])
    glass_hw = np.array([p[0] for p in glass])
    shoulder_band = glass_hw[(glass_ys >= glass_ys.min())
                             & (glass_ys <= glass_ys.min()
                                + 0.15 * (glass_ys.max()
                                          - glass_ys.min()))]
    collar_hw = max(p[0] for p in profiles["COLLAR"])
    return {
        "distortion_ratio": ratio,
        "width_px_at_sample_height":
            round(2 * max_hw * (SAMPLE_H / (span1 - span0)) * ratio, 1),
        "height_px": SAMPLE_H,
        "aspect_h_over_w": round(aspect, 4),
        "normalized_contour_max": round(max(contour), 4),
        "shoulder_halfwidth_change_ratio":
            round(float(shoulder_band.max() / shoulder_band.min())
                  if shoulder_band.min() else 0.0, 4),
        "neck_width_norm": round(float(glass_hw[np.argmin(glass_ys)])
                                 * ratio / max_hw, 4),
        "collar_width_norm": round(collar_hw * ratio / max_hw, 4),
        "body_width_norm": round(1.0 * ratio, 4),
        "normalized_contour": contour,
    }


def build_calibration_record() -> dict:
    fit = load_m3_fit()
    span0, span1 = fit["assembly_span_px"]
    glass = _half_profiles(fit)["GLASS"]
    max_hw = max(p[0] for p in glass)
    return {
        "schema": SCHEMA,
        "created_at": "2026-08-03",
        "m3_fit_sha256": M3_FIT_SHA256,
        "canonical_bounds": canonical_bounds(),
        "native_m3_aspect_h_over_w":
            round((span1 - span0) / (2.0 * max_hw), 4),
        "proposed_threshold": PROPOSED_THRESHOLD,
        "threshold_status": THRESHOLD_STATUS,
        "task_57_evidence_ratio": TASK_57_RATIO,
        "production_enforcement": "NOT_ENFORCED — policy selected but "
                                  "unenforced until a later approved slice",
        "samples": [sample_geometry(r, fit=fit) for r in RATIOS],
        "owner_visual_review": {"verdict": None,
                                "note": "blank pending owner review"},
        "selected_final_policy": None,
        "recommendation": {"value": "BOUNDED_M3_ADAPTATION @ 1.05",
                           "status": "PROVISIONAL"},
    }


def build_contact_sheet(out_path: str) -> None:
    """All samples at IDENTICAL displayed height, labeled, with the
    proposed threshold line and a blank owner-verdict field."""
    fit = load_m3_fit()
    samples = [(r, render_sample(r, fit=fit)) for r in RATIOS]
    gap, header, footer = 24, 60, 120
    total_w = sum(im.width for _, im in samples) + gap * (len(samples) + 1)
    total_h = header + samples[0][1].height + 70 + footer
    sheet = Image.new("RGB", (total_w, total_h), (244, 237, 231))
    d = ImageDraw.Draw(sheet)
    d.text((16, 12), "M3 PROPORTION CALIBRATION — equal displayed height; "
                     "ONLY horizontal deformation varies",
           fill=(43, 27, 22))
    x = gap
    for ratio, im in samples:
        sheet.paste(im, (x, header))
        label = f"ratio {ratio:.4f}".rstrip("0").rstrip(".")
        d.text((x + 4, header + im.height + 8), label, fill=(43, 27, 22))
        d.text((x + 4, header + im.height + 26),
               f"aspect {sample_geometry(ratio, fit=fit)['aspect_h_over_w']}",
               fill=(90, 70, 64))
        if ratio == TASK_57_RATIO:
            d.text((x + 4, header + im.height + 44),
                   "= task-57 policy evidence", fill=(179, 69, 79))
        if abs(ratio - PROPOSED_THRESHOLD) < 1e-9:
            d.line([(x + im.width + gap // 2, header - 10),
                    (x + im.width + gap // 2,
                     header + im.height + 60)],
                   fill=(179, 69, 79), width=3)
            d.text((x + im.width - 150, header - 24),
                   "proposed 1.05 threshold (PROVISIONAL)",
                   fill=(179, 69, 79))
        x += im.width + gap
    d.text((16, total_h - footer + 10),
           "OWNER VERDICT: ____________________________   (samples are NOT "
           "pre-labeled PASS/FAIL; the 1.05 recommendation is provisional "
           "pending this calibration)", fill=(43, 27, 22))
    d.text((16, total_h - footer + 40),
           "objective values per sample are recorded in "
           "m3_proportion_calibration.json", fill=(90, 70, 64))
    sheet.save(out_path)
