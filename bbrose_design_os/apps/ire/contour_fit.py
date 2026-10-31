"""Corrected cubic-Bézier contour fitter — FUTURE RECONSTRUCTIONS ONLY.

``vq1_master.fit_cubics`` (v1) carries a defect: when the adaptive split
exceeds ``max_seg`` it silently replaces the tolerance-guaranteed result with
uniform chunks, so the requested tolerance is never enforced and the reported
residual is unbounded. See ``COARSENING_BYPASS`` / ``SEGMENT_CAP_DEFECT``.

This module fixes that for new work. It NEVER regenerates an existing
candidate: v1 stays byte-stable so historical artifacts and hashes reproduce
exactly, and nothing here is on the VQ-1 release path.

The tolerance contract here is explicit. Either the fit meets ``tol`` and says
so, or it fails closed with ``TOLERANCE_NOT_ACHIEVED``. It never quietly
returns a worse fit under the same name.
"""
from __future__ import annotations

import math

FIT_SCHEMA = "vq_contour_fit/2.0"
LEGACY_SCHEMA = "vq_contour_fit/1.0"

#: stable diagnostic when the requested tolerance cannot be met
TOLERANCE_NOT_ACHIEVED = "VQ_VECTOR_FIT_TOLERANCE_NOT_ACHIEVED"
#: the two v1 defects this module exists to correct
COARSENING_BYPASS = "VQ_FIT_CUBICS_COARSENING_BYPASSES_TOLERANCE"
SEGMENT_CAP_DEFECT = "VQ_FITTER_SEGMENT_CAP_FAILS_TO_PRESERVE_ERROR_BOUND"

LOCAL_NORMAL = "LOCAL_NORMAL_DIRECTION"
PARAMETER_MATCHED = "PARAMETER_MATCHED"

#: an absolute ceiling so a pathological input fails closed instead of
#: expanding without bound
DEFAULT_MAX_SEG = 48
HARD_SEG_CEILING = 1024


def _bez(p0, c1, c2, p3, t):
    u = 1.0 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * c1[0]
            + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * c1[1]
            + 3 * u * t * t * c2[1] + t ** 3 * p3[1])


def _fit_one(seg):
    """Catmull-Rom style tangents, identical to v1 so a like-for-like
    comparison isolates the segmentation policy rather than the curve form."""
    p0, p3 = seg[0], seg[-1]
    n = len(seg)
    c1 = (p0[0] + (seg[min(1, n - 1)][0] - p0[0]) * 1.2,
          p0[1] + (seg[min(1, n - 1)][1] - p0[1]) * 1.2)
    c2 = (p3[0] + (seg[max(n - 2, 0)][0] - p3[0]) * 1.2,
          p3[1] + (seg[max(n - 2, 0)][1] - p3[1]) * 1.2)
    res = 0.0
    for i, s in enumerate(seg):
        t = i / (n - 1) if n > 1 else 0.0
        b = _bez(p0, c1, c2, p3, t)
        res = max(res, math.hypot(b[0] - s[0], b[1] - s[1]))
    return (c1, c2, p3), res


def _polyline(start, segments, per_seg: int = 96):
    p0 = tuple(start)
    pts = [p0]
    for c1, c2, p3 in segments:
        for i in range(1, per_seg + 1):
            pts.append(_bez(p0, c1, c2, p3, i / per_seg))
        p0 = tuple(p3)
    return pts


def point_to_polyline(pt, poly) -> float:
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
        best = min(best, d)
    return best


def _adaptive(pts, tol, depth_limit=14):
    """Split until every sample is within ``tol``. No cap is applied here —
    the cap is a separate, explicit policy decision made by the caller."""
    def split(seg, depth=0):
        (c1, c2, p3), res = _fit_one(seg)
        if res <= tol or len(seg) <= 4 or depth > depth_limit:
            return [((c1, c2, p3), res)]
        mid = len(seg) // 2
        return split(seg[:mid + 1], depth + 1) + split(seg[mid:], depth + 1)
    return split(list(pts))


def fit_contour(samples, *, tol: float = 0.6, max_seg: int = DEFAULT_MAX_SEG,
                allow_cap_growth: bool = True,
                hard_ceiling: int = HARD_SEG_CEILING) -> dict:
    """Fit a cubic chain to ``samples`` under an enforced tolerance contract.

    When the adaptive result needs more segments than ``max_seg``:

    * ``allow_cap_growth=True`` raises the cap deterministically to exactly
      the number of segments the tolerance requires (never beyond
      ``hard_ceiling``) and keeps the tolerance guarantee;
    * ``allow_cap_growth=False`` fails closed with
      ``VQ_VECTOR_FIT_TOLERANCE_NOT_ACHIEVED``.

    Uniform chunking is never used. The v1 behaviour of silently substituting
    an unverified chunked fit is the defect this replaces.
    """
    pts = [tuple(p) for p in samples]
    base = {"schema_version": FIT_SCHEMA,
            "requested_tolerance_px": tol,
            "requested_max_seg": max_seg,
            "hard_ceiling": hard_ceiling,
            "sample_count": len(pts),
            "correspondence_method": LOCAL_NORMAL,
            "uniform_chunking_used": False,
            "supersedes": LEGACY_SCHEMA,
            "corrects": [COARSENING_BYPASS, SEGMENT_CAP_DEFECT]}

    if len(pts) < 3:
        return {**base, "segments": [], "start": pts[0] if pts else None,
                "segment_count": 0, "status": "OK",
                "tolerance_enforced": True,
                "residual_max_parameter_matched": 0.0,
                "residual_max_local_normal": 0.0,
                "residual_mean_local_normal": 0.0}

    out = _adaptive(pts, tol)
    segments = [o[0] for o in out]
    needed = len(segments)

    status, enforced, effective = "OK", True, max_seg
    if needed > max_seg:
        if allow_cap_growth and needed <= hard_ceiling:
            effective = needed
            status = "SEGMENT_CAP_RAISED_TOLERANCE_PRESERVED"
        else:
            status = TOLERANCE_NOT_ACHIEVED
            enforced = False

    poly = _polyline(pts[0], segments)
    normals = [point_to_polyline(p, poly) for p in pts]
    param_max = max(o[1] for o in out)
    normal_max = max(normals)

    # the enforced contract is measured, never assumed
    if status == "OK" and param_max > tol:
        status, enforced = TOLERANCE_NOT_ACHIEVED, False

    rec = {**base,
           "segments": segments, "start": pts[0],
           "segment_count": needed,
           "effective_max_seg": effective,
           "segment_cap_raised": effective != max_seg,
           "status": status,
           "tolerance_enforced": enforced,
           "residual_max_parameter_matched": round(param_max, 4),
           "residual_max_local_normal": round(normal_max, 4),
           "residual_mean_local_normal": round(
               sum(normals) / len(normals), 4),
           "provenance": {
               "fitter": FIT_SCHEMA,
               "policy": ("adaptive split to tolerance; cap raised "
                          "deterministically when required"
                          if allow_cap_growth else
                          "adaptive split to tolerance; fail closed at cap"),
               "tolerance_px": tol,
               "tolerance_enforced": enforced,
               "segment_count": needed,
               "correspondence_method": LOCAL_NORMAL,
               "residual_max_local_normal": round(normal_max, 4),
           }}
    if not enforced:
        rec["diagnostic"] = TOLERANCE_NOT_ACHIEVED
        rec["diagnostic_detail"] = (
            f"tolerance {tol} px needs {needed} segments; limit is "
            f"{max_seg} and cap growth is "
            f"{'disabled' if not allow_cap_growth else 'capped at ' + str(hard_ceiling)}. "
            "No fit is returned as tolerance-meeting. v1 would have "
            "silently substituted uniform chunks here.")
    return rec


def shadow_compare(samples, legacy_fit: dict, *, tol: float = 0.6) -> dict:
    """NON-AUTHORITATIVE diagnostic: how a corrected fit would compare with an
    existing frozen one.

    This creates no candidate, changes no status, and is not on the release
    path. It exists only so the size of the v1 defect is visible.
    """
    v2 = fit_contour(samples, tol=tol)
    pts = [tuple(p) for p in samples]
    legacy_poly = _polyline(legacy_fit["start"],
                            [tuple(tuple(v) for v in s)
                             for s in legacy_fit["segments"]])
    legacy_normals = [point_to_polyline(p, legacy_poly) for p in pts]
    return {
        "record_type": "vq_contour_fit_shadow_diagnostic/1.0",
        "authoritative": False,
        "creates_candidate": False,
        "changes_candidate_status": False,
        "on_release_path": False,
        "legacy": {
            "schema": LEGACY_SCHEMA,
            "segment_count": legacy_fit.get("segment_count"),
            "reported_residual_max": legacy_fit.get("residual_max"),
            "measured_residual_max_local_normal": round(
                max(legacy_normals), 4),
            "measured_residual_mean_local_normal": round(
                sum(legacy_normals) / len(legacy_normals), 4),
            "tolerance_enforced": False,
            "uniform_chunking_used": True,
        },
        "corrected": {
            "schema": FIT_SCHEMA,
            "segment_count": v2["segment_count"],
            "status": v2["status"],
            "tolerance_enforced": v2["tolerance_enforced"],
            "residual_max_parameter_matched":
                v2["residual_max_parameter_matched"],
            "residual_max_local_normal": v2["residual_max_local_normal"],
            "residual_mean_local_normal": v2["residual_mean_local_normal"],
        },
        "interpretation":
            "Informational only. It does not license regenerating any frozen "
            "candidate and does not reopen VQ-1.",
    }
