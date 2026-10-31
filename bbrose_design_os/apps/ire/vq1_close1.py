"""VQ-1-MASTER-CLOSE-1 — dense geometry confirmation and analytical evidence.

This module NEVER emits a candidate. It measures the already-frozen M3 fit
against the validated reference at full row density, and it renders
*analytical evidence* that makes the existing contour measurable without
touching the candidate artwork (§6).

Two residual measures are reported for every row, matching the established
correspondence contract:

``local_normal``  canonical — true point-to-curve distance;
``same_row``      diagnostic only — invalid at steep transitions.

Everything here is read-only with respect to ``master_it3.*``.
"""
from __future__ import annotations

import math
import os

from apps.ire.vq1_master import (ASSEMBLY_SPAN_PX, BANDS, BODY_WIDTH_PX,
                                 CENTERLINE_PX)

DENSE_SCHEMA = "vq1_neck_shoulder_dense_confirmation/1.0"
EVIDENCE_SCHEMA = "vq1_analytical_structural_evidence/1.0"
INSPECTION_RULE_SCHEMA = "vq1_evidence_assisted_structural_inspection/1.0"
CONSISTENCY_SCHEMA = "vq1_final_structural_scorecard_consistency/1.0"
WITHDRAWAL_SCHEMA = "vq1_measurement_method_withdrawal/1.0"

GEOMETRY_STATE = "VQ1_GEOMETRY_COMPLETE_PENDING_FINAL_STRUCTURAL_INSPECTION"
RELEASE_STATE = "VQ1_MASTER_STRUCTURAL_CANDIDATE_PENDING_HUMAN_REVIEW"
HARD_STOP = "VQ1_MASTER_HARD_STOP_REVIEW_REQUIRED"

#: §4 — the withdrawn correction candidate may never be built
M3S1_WITHDRAWN = "M3S1_AUTHORIZATION_WITHDRAWN_REFERENCE_MEASUREMENT_CONTRADICTION"
PROHIBITED_CANDIDATES = ("M3S1", "M3S2")

#: the sample-vs-source comparison that produced the superseded numbers
VACUOUS_METHOD = "VQ1_SAMPLE_IDENTITY_COMPARISON_VACUOUS"
#: adaptive tolerance was not enforced on the GLASS chain
COARSENED_FIT = "VQ1_GLASS_FIT_COARSENED_TOLERANCE_NOT_ENFORCED"

#: per-row confidence is genuinely absent upstream — never synthesized
NO_CONFIDENCE = "NOT_AVAILABLE_IN_SOURCE_EXTRACTION"
#: the reference is occluded on one flank; the far edge is a mirror
MIRROR = "DERIVED_BY_MIRROR_NOT_INDEPENDENTLY_MEASURED"

#: §10 CLOSE-1 legibility floors. The v1 ``LEGIBILITY_FLOORS`` are immutable;
#: these are additional and higher, and apply only to this evidence set.
CLOSE1_FLOORS = {
    "full_reference": {"min_h": 900},
    "full_candidate": {"min_h": 900},
    "neck_crop": {"min_h": 600},
    "shoulder_crop": {"min_w": 600},
    "collar_neck_crop": {"min_h": 600},
    "complete_closure_crop": {"min_h": 900},
}

DENSE_GATES = {
    "neck_mean": 0.006, "neck_p95": 0.018, "neck_max": 0.035,
    "shoulder_mean": 0.006, "shoulder_p95": 0.018, "shoulder_max": 0.035,
    "one_row_spike_ratio": 2.5,
    "inset_present_px": 4.0,
}


# --- curve evaluation ---------------------------------------------------------

def _bez(p0, c1, c2, p3, t):
    u = 1.0 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * c1[0]
            + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * c1[1]
            + 3 * u * t * t * c2[1] + t ** 3 * p3[1])


def densify(component_fit: dict, per_seg: int = 240) -> list:
    """The fitted chain as a dense polyline of (half_width_px, row_px)."""
    p0 = tuple(component_fit["start"])
    pts = [p0]
    for seg in component_fit["segments"]:
        c1, c2, p3 = (tuple(v) for v in seg)
        for i in range(1, per_seg + 1):
            pts.append(_bez(p0, c1, c2, p3, i / per_seg))
        p0 = p3
    return pts


def half_at_row(poly: list, y: float):
    """SAME_ROW half-width — diagnostic only (§ correspondence contract)."""
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]
        if a[1] == b[1]:
            continue
        if (a[1] - y) * (b[1] - y) <= 0:
            t = (y - a[1]) / (b[1] - a[1])
            return a[0] + t * (b[0] - a[0])
    return None


def point_to_curve(pt, poly: list) -> float:
    """Canonical LOCAL_NORMAL residual: true distance from a reference edge
    point to the fitted contour, measured perpendicular to the local segment
    rather than along a scan row."""
    px, py = pt
    best = float("inf")
    for i in range(len(poly) - 1):
        ax, ay = poly[i]
        bx, by = poly[i + 1]
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        if den == 0:
            d = math.hypot(px - ax, py - ay)
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / den))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if d < best:
            best = d
    return best


def tangent_curvature(hw: dict, y: int):
    """Reference tangent (degrees from vertical) and curvature (px/row^2)."""
    ys = [y - 2, y - 1, y, y + 1, y + 2]
    if not all(v in hw for v in ys):
        return None, None
    d1 = (hw[y + 1] - hw[y - 1]) / 2.0
    d2 = hw[y + 1] - 2 * hw[y] + hw[y - 1]
    return round(math.degrees(math.atan(d1)), 3), round(d2, 4)


# --- §5 dense confirmation ----------------------------------------------------

def semantic_region(y: int, neck: tuple, shoulder: tuple) -> str:
    if neck[0] <= y <= neck[1]:
        return "GLASS_NECK_UNDERCUT"
    if shoulder[0] <= y <= shoulder[1]:
        return "GLASS_SHOULDER_TRANSITION"
    return "OUT_OF_BOUNDED_REGION"


def dense_rows(hw: dict, poly: list, neck: tuple, shoulder: tuple) -> list:
    """Every usable row in the bounded neck/shoulder region, with the full
    §5 field set. No row is skipped and none is interpolated."""
    out = []
    for y in range(neck[0], shoulder[1] + 1):
        if y not in hw:
            continue
        ref_half = float(hw[y])
        cand_half = half_at_row(poly, float(y))
        if cand_half is None:
            continue
        tan, curv = tangent_curvature(hw, y)
        normal = point_to_curve((ref_half, float(y)), poly)
        out.append({
            "row_px": y,
            "semantic_region": semantic_region(y, neck, shoulder),
            "reference_half_width_px": ref_half,
            "m3_half_width_px": round(cand_half, 4),
            "reference_left_edge_px": round(CENTERLINE_PX - ref_half, 3),
            "reference_right_edge_px": round(CENTERLINE_PX + ref_half, 3),
            "reference_right_edge_provenance": MIRROR,
            "m3_left_edge_px": round(CENTERLINE_PX - cand_half, 3),
            "m3_right_edge_px": round(CENTERLINE_PX + cand_half, 3),
            "residual_local_normal_px": round(normal, 4),
            "residual_local_normal_norm": round(normal / BODY_WIDTH_PX, 6),
            "residual_same_row_px": round(abs(cand_half - ref_half), 4),
            "residual_same_row_norm": round(
                abs(cand_half - ref_half) / BODY_WIDTH_PX, 6),
            "same_row_is_diagnostic_only": True,
            "contour_confidence": NO_CONFIDENCE,
            "reference_tangent_deg_from_vertical": tan,
            "reference_curvature_px_per_row2": curv,
        })
    return out


def _stats(vals: list) -> dict:
    if not vals:
        return {"count": 0}
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round(0.95 * (len(s) - 1)))))
    return {"count": len(s), "mean": round(sum(s) / len(s), 6),
            "p95": round(s[k], 6), "max": round(s[-1], 6)}


def spike_check(rows: list, key: str) -> dict:
    """A one-row spike is a row whose residual towers over both neighbours.
    A smooth local maximum shared with its neighbours is not a spike."""
    spikes = []
    for i in range(1, len(rows) - 1):
        a, b, c = (rows[i - 1][key], rows[i][key], rows[i + 1][key])
        nb = max(a, c)
        if nb > 0 and b / nb >= DENSE_GATES["one_row_spike_ratio"]:
            spikes.append({"row_px": rows[i]["row_px"], "value": b,
                           "neighbour_max": nb})
    return {"one_row_spikes": spikes, "count": len(spikes),
            "ratio_threshold": DENSE_GATES["one_row_spike_ratio"]}


def build_dense_confirmation(hw: dict, fit: dict, neck_rec: dict,
                             shoulder_rec: dict) -> dict:
    neck = (int(neck_rec["neck_start_row"]), int(neck_rec["neck_end_row"]))
    shoulder = (int(shoulder_rec["shoulder_start_row"]),
                int(shoulder_rec["shoulder_end_row"]))
    poly = densify(fit["fits"]["GLASS"])
    rows = dense_rows(hw, poly, neck, shoulder)

    nrows = [r for r in rows if r["semantic_region"] == "GLASS_NECK_UNDERCUT"]
    srows = [r for r in rows
             if r["semantic_region"] == "GLASS_SHOULDER_TRANSITION"]

    def block(rs):
        return {
            "local_normal": _stats([r["residual_local_normal_norm"]
                                    for r in rs]),
            "same_row_diagnostic": _stats([r["residual_same_row_norm"]
                                           for r in rs]),
            "spikes": spike_check(rs, "residual_local_normal_norm"),
        }

    nb, sb = block(nrows), block(srows)

    # is the reference undercut still expressed by the fitted contour?
    ref_min = min(r["reference_half_width_px"] for r in nrows)
    cand_min = min(r["m3_half_width_px"] for r in nrows)
    collar_half = float(neck_rec["collar_half_px"])
    ref_inset = collar_half - ref_min
    cand_inset = collar_half - cand_min

    # is the shoulder still convex outward in the fitted contour?
    cand_curv = []
    for i in range(1, len(srows) - 1):
        cand_curv.append(srows[i + 1]["m3_half_width_px"]
                         - 2 * srows[i]["m3_half_width_px"]
                         + srows[i - 1]["m3_half_width_px"])
    ref_curv = [r["reference_curvature_px_per_row2"] for r in srows
                if r["reference_curvature_px_per_row2"] is not None]

    gates = {
        "neck_mean": nb["local_normal"]["mean"] <= DENSE_GATES["neck_mean"],
        "neck_p95": nb["local_normal"]["p95"] <= DENSE_GATES["neck_p95"],
        "neck_max": nb["local_normal"]["max"] <= DENSE_GATES["neck_max"],
        "shoulder_mean": (sb["local_normal"]["mean"]
                          <= DENSE_GATES["shoulder_mean"]),
        "shoulder_p95": (sb["local_normal"]["p95"]
                         <= DENSE_GATES["shoulder_p95"]),
        "shoulder_max": (sb["local_normal"]["max"]
                         <= DENSE_GATES["shoulder_max"]),
        "no_neck_spike": nb["spikes"]["count"] == 0,
        "no_shoulder_spike": sb["spikes"]["count"] == 0,
        "neck_inset_present": cand_inset >= DENSE_GATES["inset_present_px"],
        "shoulder_convex_outward": (sum(cand_curv) < 0
                                    and sum(ref_curv) < 0),
    }
    return {
        "record_type": DENSE_SCHEMA,
        "candidate": "M3",
        "geometry_modified": False,
        "measurement_space": "SOURCE_IMAGE_PIXELS",
        "normalization": "BODY_WIDTH_PX",
        "body_width_px": BODY_WIDTH_PX,
        "canonical_correspondence": "LOCAL_NORMAL_DIRECTION",
        "same_row_retained_as": "DIAGNOSTIC_ONLY",
        "row_density": "EVERY_AVAILABLE_ROW_STEP_1",
        "fit_sampling_density": "STEP_3",
        "density_ratio": 3,
        "neck_band_rows": list(neck),
        "shoulder_band_rows": list(shoulder),
        "rows": rows,
        "neck": nb, "shoulder": sb,
        "gates": DENSE_GATES,
        "gate_results": gates,
        "all_gates_pass": all(gates.values()),
        "neck_inset": {
            "collar_half_px": collar_half,
            "reference_min_half_px": ref_min,
            "m3_min_half_px": round(cand_min, 3),
            "reference_inset_px_per_side": round(ref_inset, 3),
            "m3_inset_px_per_side": round(cand_inset, 3),
            "inset_expression_ratio": round(cand_inset / ref_inset, 4)
            if ref_inset else None,
            "feature_relative_shortfall_px": round(ref_inset - cand_inset, 3),
        },
        "shoulder_convexity": {
            "reference_curvature_sum": round(sum(ref_curv), 4),
            "m3_curvature_sum": round(sum(cand_curv), 4),
            "both_outward_convex": gates["shoulder_convex_outward"],
        },
        "contour_confidence_available": False,
        "contour_confidence_state": NO_CONFIDENCE,
        "reference_far_edge": MIRROR,
        "asymmetry_scope_limit":
            "Reference symmetry cannot be audited: the far flank is mirrored "
            "from the measured flank, so any reference-vs-candidate asymmetry "
            "finding is unsupportable. Candidate symmetry alone is auditable.",
        "authority": "CONCEPT_VISUAL_PIXEL_EVIDENCE",
        "is_physical_dimension": False,
    }


# --- §7 analytical evidence rendering -----------------------------------------

BG = (250, 249, 248)
REF_INK = (20, 20, 24)
CAND_INK = (200, 30, 40)
GRID = (208, 204, 200)
LABEL = (40, 40, 46)
MASK_FILLS = {"DARK_CLOSURE": (90, 90, 98), "COLLAR": (170, 168, 164),
              "GLASS": (222, 220, 216)}


def _font(size: int):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def assembly_half(hw: dict, fit: dict | None, y: int):
    """Outer silhouette half-width at a row: the widest visible band."""
    if fit is None:
        return float(hw[y]) if y in hw else None
    best = None
    for name, band in BANDS.items():
        if band[0] <= y <= band[1]:
            v = half_at_row(densify_cache(fit, name), float(y))
            if v is not None and (best is None or v > best):
                best = v
    return best


_POLY_CACHE: dict = {}


def densify_cache(fit: dict, name: str) -> list:
    key = (id(fit), name)
    if key not in _POLY_CACHE:
        _POLY_CACHE[key] = densify(fit["fits"][name])
    return _POLY_CACHE[key]


def draw_silhouette(out_png: str, hw: dict, fit: dict | None, *,
                    scale: float = 1.0, title: str = "") -> dict:
    """A flat binary silhouette on the shared canvas. No shading, no
    gradient, no annotation inside the form."""
    from PIL import Image, ImageDraw
    y0, y1 = ASSEMBLY_SPAN_PX
    w = int(round(BODY_WIDTH_PX * 1.55 * scale))
    h = int(round((y1 - y0) * scale)) + 60
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    cx = w / 2.0
    for y in range(y0, y1 + 1):
        hv = assembly_half(hw, fit, y)
        if hv is None:
            continue
        py = (y - y0) * scale + 30
        d.line([(cx - hv * scale, py), (cx + hv * scale, py)],
               fill=REF_INK, width=1)
    if title:
        d.text((8, 6), title, fill=LABEL, font=_font(16))
    img.save(out_png)
    return {"path": out_png, "size": list(img.size), "scale": scale}


def draw_contour_overlay(out_png: str, hw: dict, fit: dict, *,
                         scale: float = 1.0) -> dict:
    """Reference contour and M3 contour on one canvas, identical transform."""
    from PIL import Image, ImageDraw
    y0, y1 = ASSEMBLY_SPAN_PX
    w = int(round(BODY_WIDTH_PX * 1.55 * scale))
    h = int(round((y1 - y0) * scale)) + 60
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    cx = w / 2.0

    def trace(getter, colour):
        prev = None
        for y in range(y0, y1 + 1):
            hv = getter(y)
            if hv is None:
                prev = None
                continue
            py = (y - y0) * scale + 30
            pt = (cx - hv * scale, py)
            if prev:
                d.line([prev, pt], fill=colour, width=1)
                d.line([(2 * cx - prev[0], prev[1]),
                        (2 * cx - pt[0], pt[1])], fill=colour, width=1)
            prev = pt

    trace(lambda y: float(hw[y]) if y in hw else None, REF_INK)
    trace(lambda y: assembly_half(hw, fit, y), CAND_INK)
    d.line([(cx, 30), (cx, h - 30)], fill=GRID, width=1)
    f = _font(15)
    d.text((8, 6), "BLACK = reference contour   RED = M3 contour",
           fill=LABEL, font=f)
    img.save(out_png)
    return {"path": out_png, "size": list(img.size), "scale": scale}


def draw_region_overlay(out_png: str, hw: dict, fit: dict, band: tuple, *,
                        scale: float, pad: int = 6, title: str = "",
                        markers: list | None = None) -> dict:
    """Enlarged contour overlay for one bounded region, with an external
    scale bar. Annotation never enters the candidate artwork (§6)."""
    from PIL import Image, ImageDraw
    y0, y1 = band[0] - pad, band[1] + pad
    hs = [float(hw[y]) for y in range(y0, y1 + 1) if y in hw]
    hmax = max(hs) + 12
    w = int(round(hmax * 2 * scale)) + 210
    h = int(round((y1 - y0) * scale)) + 90
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    cx = (w - 210) / 2.0 + 200

    for gy in range(y0, y1 + 1, 5):
        py = (gy - y0) * scale + 50
        d.line([(200, py), (w - 6, py)], fill=GRID, width=1)
        d.text((150, py - 7), str(gy), fill=GRID, font=_font(13))

    def trace(getter, colour, width=2):
        prev = None
        for y in range(y0, y1 + 1):
            hv = getter(y)
            if hv is None:
                prev = None
                continue
            py = (y - y0) * scale + 50
            pt = (cx - hv * scale, py)
            if prev:
                d.line([prev, pt], fill=colour, width=width)
                d.line([(2 * cx - prev[0], prev[1]),
                        (2 * cx - pt[0], pt[1])], fill=colour, width=width)
            prev = pt

    trace(lambda y: float(hw[y]) if y in hw else None, REF_INK)
    trace(lambda y: assembly_half(hw, fit, y), CAND_INK)
    d.line([(cx, 50), (cx, h - 30)], fill=GRID, width=1)

    f = _font(16)
    d.text((8, 8), title or f"rows {band[0]}-{band[1]}  x{scale:g}",
           fill=LABEL, font=f)
    d.text((8, 28), "BLACK = reference   RED = M3   grid = 5 source rows",
           fill=LABEL, font=_font(14))
    for m in (markers or []):
        py = (m["row"] - y0) * scale + 50
        d.line([(200, py), (w - 6, py)], fill=(30, 90, 180), width=1)
        d.text((6, py - 8), m["label"], fill=(30, 90, 180), font=_font(14))
    img.save(out_png)
    return {"path": out_png, "size": list(img.size), "scale": scale,
            "band": list(band)}


def draw_flank_overlay(out_png: str, hw: dict, fit: dict, band: tuple, *,
                       scale: float, x_window: tuple, pad: int = 6,
                       title: str = "", markers: list | None = None) -> dict:
    """Enlarged overlay of the MEASURED flank only.

    The far flank of the reference is a mirror, so rendering it would double
    the width without adding evidence — and a very wide image is downscaled
    below the §10 legibility floors on delivery. Single-flank keeps the
    delivered crop legible and matches the honest provenance.
    """
    from PIL import Image, ImageDraw
    y0, y1 = band[0] - pad, band[1] + pad
    xlo, xhi = x_window
    gut = 150
    w = int(round((xhi - xlo) * scale)) + gut + 20
    h = int(round((y1 - y0) * scale)) + 96
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    def X(hv):
        return gut + (hv - xlo) * scale

    def Y(y):
        return (y - y0) * scale + 62

    for gy in range(y0, y1 + 1):
        if gy % 5:
            continue
        d.line([(gut, Y(gy)), (w - 8, Y(gy))], fill=GRID, width=1)
        d.text((gut - 46, Y(gy) - 7), str(gy), fill=GRID, font=_font(13))
    for v in range(int(xlo), int(xhi) + 1):
        if v % 5 == 0:
            d.line([(X(v), 62), (X(v), h - 30)], fill=GRID, width=1)
            d.text((X(v) - 10, h - 26), str(v), fill=GRID, font=_font(13))

    def trace(getter, colour):
        prev = None
        for y in range(y0, y1 + 1):
            hv = getter(y)
            if hv is None or not (xlo <= hv <= xhi):
                prev = None
                continue
            pt = (X(hv), Y(y))
            if prev:
                d.line([prev, pt], fill=colour, width=3)
            prev = pt

    trace(lambda y: float(hw[y]) if y in hw else None, REF_INK)
    trace(lambda y: assembly_half(hw, fit, y), CAND_INK)
    d.text((8, 8), title or f"rows {band[0]}-{band[1]}  x{scale:g}",
           fill=LABEL, font=_font(17))
    d.text((8, 32), "BLACK reference   RED M3   measured flank only "
                    "(far flank is mirrored)", fill=LABEL, font=_font(14))
    for m in (markers or []):
        d.line([(gut, Y(m["row"])), (w - 8, Y(m["row"]))],
               fill=(30, 90, 180), width=2)
        d.text((gut + 6, Y(m["row"]) - 18), m["label"],
               fill=(30, 90, 180), font=_font(14))
    img.save(out_png)
    return {"path": out_png, "size": list(img.size), "scale": scale,
            "band": list(band), "x_window": list(x_window),
            "single_flank": True, "far_flank": MIRROR}


def draw_neck_width_diagram(out_png: str, dense: dict) -> dict:
    """§7D — collar / neck / body widths with the 8 px reference inset shown
    as an external dimension, plus the exact residual."""
    from PIL import Image, ImageDraw
    rows = [r for r in dense["rows"]
            if r["semantic_region"] == "GLASS_NECK_UNDERCUT"]
    ins = dense["neck_inset"]
    w, h = 1180, 760
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    f, fs = _font(17), _font(14)
    d.text((16, 12), "NECK WIDTH PROGRESSION — reference vs M3",
           fill=LABEL, font=_font(20))

    x0, y0, pw, ph = 90, 90, 760, 560
    hmin = min(min(r["reference_half_width_px"] for r in rows),
               min(r["m3_half_width_px"] for r in rows)) - 2
    hmax = max(ins["collar_half_px"],
               max(r["reference_half_width_px"] for r in rows)) + 3

    def px(v):
        return x0 + (v - hmin) / (hmax - hmin) * pw

    def py(i):
        return y0 + i / max(1, len(rows) - 1) * ph

    d.rectangle([x0, y0, x0 + pw, y0 + ph], outline=GRID)
    for i, r in enumerate(rows):
        if i % 3 == 0:
            d.text((30, py(i) - 7), str(r["row_px"]), fill=GRID, font=fs)
    for v in range(int(hmin) + 1, int(hmax) + 1):
        if v % 2 == 0:
            d.line([(px(v), y0), (px(v), y0 + ph)], fill=GRID, width=1)
            d.text((px(v) - 10, y0 + ph + 6), str(v), fill=GRID, font=fs)

    for key, colour in (("reference_half_width_px", REF_INK),
                        ("m3_half_width_px", CAND_INK)):
        prev = None
        for i, r in enumerate(rows):
            pt = (px(r[key]), py(i))
            if prev:
                d.line([prev, pt], fill=colour, width=2)
            prev = pt

    cx = px(ins["collar_half_px"])
    d.line([(cx, y0), (cx, y0 + ph)], fill=(30, 90, 180), width=2)
    d.text((cx + 6, y0 + 4), f"collar half {ins['collar_half_px']} px",
           fill=(30, 90, 180), font=fs)
    mn = px(ins["reference_min_half_px"])
    d.line([(mn, y0), (mn, y0 + ph)], fill=(20, 130, 90), width=2)
    d.text((mn - 190, y0 + 4),
           f"ref neck min {ins['reference_min_half_px']} px",
           fill=(20, 130, 90), font=fs)
    ay = y0 + ph - 40
    d.line([(mn, ay), (cx, ay)], fill=(20, 130, 90), width=2)
    d.line([(mn, ay - 6), (mn, ay + 6)], fill=(20, 130, 90), width=2)
    d.line([(cx, ay - 6), (cx, ay + 6)], fill=(20, 130, 90), width=2)
    d.text(((mn + cx) / 2 - 96, ay - 26),
           f"reference inset {ins['reference_inset_px_per_side']} px/side",
           fill=(20, 130, 90), font=fs)

    tx = x0 + pw + 24
    lines = [
        "BLACK reference    RED M3",
        "",
        f"collar half        {ins['collar_half_px']} px",
        f"ref neck minimum   {ins['reference_min_half_px']} px",
        f"M3  neck minimum   {ins['m3_min_half_px']} px",
        f"ref inset/side     {ins['reference_inset_px_per_side']} px",
        f"M3  inset/side     {ins['m3_inset_px_per_side']} px",
        f"inset expressed    {ins['inset_expression_ratio']}",
        f"shortfall          {ins['feature_relative_shortfall_px']} px",
        "",
        f"body width         {BODY_WIDTH_PX} px",
        f"inset as % body    "
        f"{100 * ins['reference_inset_px_per_side'] / BODY_WIDTH_PX:.2f} %",
        "",
        "residual (local normal, normalized)",
        f"  mean {dense['neck']['local_normal']['mean']}",
        f"  p95  {dense['neck']['local_normal']['p95']}",
        f"  max  {dense['neck']['local_normal']['max']}",
    ]
    for i, ln in enumerate(lines):
        d.text((tx, y0 + i * 22), ln, fill=LABEL, font=f)
    d.text((16, h - 26), "half-width, source pixels  (x axis)  /  "
                         "source row (y axis)", fill=LABEL, font=fs)
    img.save(out_png)
    return {"path": out_png, "size": list(img.size)}


def draw_shoulder_curvature_diagram(out_png: str, dense: dict) -> dict:
    """§7E — half-width progression, curvature, tangents, deviation map."""
    from PIL import Image, ImageDraw
    rows = [r for r in dense["rows"]
            if r["semantic_region"] == "GLASS_SHOULDER_TRANSITION"]
    w, h = 1240, 820
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    f, fs = _font(17), _font(14)
    d.text((16, 12), "SHOULDER TRANSITION — progression, curvature, deviation",
           fill=LABEL, font=_font(20))

    x0, y0, pw, ph = 80, 76, 620, 330
    hmin = min(r["reference_half_width_px"] for r in rows) - 3
    hmax = max(r["reference_half_width_px"] for r in rows) + 3

    def sx(i):
        return x0 + i / max(1, len(rows) - 1) * pw

    def sy(v):
        return y0 + ph - (v - hmin) / (hmax - hmin) * ph

    d.rectangle([x0, y0, x0 + pw, y0 + ph], outline=GRID)
    d.text((x0, y0 - 22), "half-width progression", fill=LABEL, font=f)
    for key, colour in (("reference_half_width_px", REF_INK),
                        ("m3_half_width_px", CAND_INK)):
        prev = None
        for i, r in enumerate(rows):
            pt = (sx(i), sy(r[key]))
            if prev:
                d.line([prev, pt], fill=colour, width=2)
            prev = pt
    for i, r in enumerate(rows):
        if i % 6 == 0:
            d.text((sx(i) - 12, y0 + ph + 6), str(r["row_px"]),
                   fill=GRID, font=fs)

    cy0, cph = y0 + ph + 70, 200
    cur = [r["reference_curvature_px_per_row2"] or 0.0 for r in rows]
    cmax = max(1e-6, max(abs(v) for v in cur))
    d.rectangle([x0, cy0, x0 + pw, cy0 + cph], outline=GRID)
    d.text((x0, cy0 - 22), "reference curvature (px / row^2)  "
                           "negative = convex outward", fill=LABEL, font=f)
    mid = cy0 + cph / 2
    d.line([(x0, mid), (x0 + pw, mid)], fill=GRID, width=1)
    prev = None
    for i, v in enumerate(cur):
        pt = (sx(i), mid - v / cmax * (cph / 2 - 8))
        if prev:
            d.line([prev, pt], fill=(20, 130, 90), width=2)
        prev = pt
    ki = max(range(len(cur)), key=lambda i: abs(cur[i]))
    d.line([(sx(ki), cy0), (sx(ki), cy0 + cph)], fill=(30, 90, 180), width=2)
    d.text((sx(ki) + 5, cy0 + 6),
           f"max curvature row {rows[ki]['row_px']}",
           fill=(30, 90, 180), font=fs)

    dy0, dph = cy0, 200
    dx0, dpw = x0 + pw + 130, 300
    dev = [r["residual_local_normal_px"] for r in rows]
    dmax = max(1e-6, max(dev))
    d.rectangle([dx0, dy0, dx0 + dpw, dy0 + dph], outline=GRID)
    d.text((dx0, dy0 - 22), "deviation map (local normal, px)",
           fill=LABEL, font=f)
    for i, v in enumerate(dev):
        bx = dx0 + i / max(1, len(dev) - 1) * dpw
        d.line([(bx, dy0 + dph), (bx, dy0 + dph - v / dmax * (dph - 10))],
               fill=CAND_INK, width=2)
    d.text((dx0, dy0 + dph + 6), f"peak {round(dmax, 3)} px at row "
                                 f"{rows[dev.index(dmax)]['row_px']}",
           fill=LABEL, font=fs)

    tx = x0 + pw + 130
    st = dense["shoulder"]["local_normal"]
    lines = [
        "BLACK reference   RED M3",
        "",
        f"neck contact  {rows[0]['reference_half_width_px']} px",
        f"body contact  {rows[-1]['reference_half_width_px']} px",
        f"rows          {len(rows)}",
        f"max curvature row {rows[ki]['row_px']}",
        f"ref tangent start {rows[0]['reference_tangent_deg_from_vertical']}"
        " deg",
        f"ref tangent end   "
        f"{rows[-1]['reference_tangent_deg_from_vertical']} deg",
        "",
        "residual (local normal, normalized)",
        f"  mean {st['mean']}",
        f"  p95  {st['p95']}",
        f"  max  {st['max']}",
    ]
    for i, ln in enumerate(lines):
        d.text((tx, y0 + i * 22), ln, fill=LABEL, font=f)
    img.save(out_png)
    return {"path": out_png, "size": list(img.size)}


def draw_component_mask(out_png: str, fit: dict, *, scale: float = 1.0):
    """§7F — flat diagnostic fills only, one value per visible band."""
    from PIL import Image, ImageDraw
    y0, y1 = ASSEMBLY_SPAN_PX
    w = int(round(BODY_WIDTH_PX * 1.55 * scale))
    h = int(round((y1 - y0) * scale)) + 60
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    cx = w / 2.0
    for name in ("GLASS", "COLLAR", "DARK_CLOSURE"):
        band = BANDS[name]
        poly = densify_cache(fit, name)
        for y in range(band[0], band[1] + 1):
            hv = half_at_row(poly, float(y))
            if hv is None:
                continue
            py = (y - y0) * scale + 30
            d.line([(cx - hv * scale, py), (cx + hv * scale, py)],
                   fill=MASK_FILLS[name], width=1)
    f = _font(15)
    for i, (n, c) in enumerate(MASK_FILLS.items()):
        d.rectangle([8, 6 + i * 20, 24, 20 + i * 20], fill=c)
        d.text((30, 5 + i * 20), n, fill=LABEL, font=f)
    img.save(out_png)
    return {"path": out_png, "size": list(img.size), "flat_fills": True}


def enlarge(src_png: str, out_png: str, factor: int) -> dict:
    """Deterministic nearest-neighbour enlargement. The record always keeps
    the native size so an enlarged crop can never pose as native detail."""
    from PIL import Image
    im = Image.open(src_png)
    native = list(im.size)
    big = im.resize((im.width * factor, im.height * factor), Image.NEAREST)
    big.save(out_png)
    return {"path": out_png, "native_size": native, "size": list(big.size),
            "enlargement_factor": factor, "resample": "NEAREST",
            "is_native_resolution": False}
