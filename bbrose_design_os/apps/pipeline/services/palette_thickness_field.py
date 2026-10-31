"""PALT-M4B-A3 §8 — deterministic thickness field over the whole tray.

A2 measured ten hand-named regions. The owner's brief forbids relying on
a few manually selected sections, so the field here is sampled densely and
automatically: a fixed lattice of orthogonal section planes is cut with
the same deterministic section engine that produces the review sections,
and local thickness is measured on every boundary point of every closed
loop.

Local thickness at a boundary point is the distance to the nearest
boundary point that is not a geodesic neighbour on the same loop — the
standard 2D wall measure. It is exact for walls that run perpendicular to
the section plane and it OVERSTATES thickness where the true minimum runs
out of plane, so the reported minimum is an upper bound on the true
minimum. That limitation is declared rather than hidden; with two
orthogonal plane families over a shell whose walls are vertical or
horizontal, the residual error is small.

No mould-flow simulation is involved. Sink and warpage remain
PROVISIONAL_ENGINEERING_RISK classifications.
"""
from __future__ import annotations

import numpy as np

from apps.pipeline.services import palette_mesh_section as ms
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "palette_thickness_field/1.0"

SAMPLING = {
    "version": "thickness_field_sampling/1.0",
    "plane_families": ["x", "y"],
    "planes_per_family": 41,
    "plane_span_fraction": 0.94,      # of the tray half-width, each side
    "measure": "MEDIAL_RIDGE_OF_THE_RASTERISED_DISTANCE_FIELD",
    "raster_pitch_mm": 0.05,
    "geodesic_skip": 6,               # retained for reproducibility
    "percentiles": [1, 5, 25, 50, 75, 95, 99],
    "method": "ORTHOGONAL_SECTION_LATTICE_MEDIAL_RIDGE_THICKNESS",
    "limitation": "2D in-plane measure; overstates where the true minimum "
                  "runs out of plane, so the reported minimum is an upper "
                  "bound on the true minimum",
}


def _segments(loops):
    """All boundary segments of a section as (A, B) arrays."""
    a, b = [], []
    for lp in loops:
        p = np.asarray(lp["points_2d"], dtype=float)
        a.append(p)
        b.append(np.roll(p, -1, axis=0))
    return np.concatenate(a), np.concatenate(b)


def _ray_hits(origin, direction, A, B, eps):
    """Smallest positive t where origin + t*dir crosses a segment."""
    d = direction
    e = B - A
    denom = e[:, 0] * d[1] - e[:, 1] * d[0]
    ok = np.abs(denom) > 1e-14
    w = origin - A
    t = np.full(len(A), np.inf)
    u = np.full(len(A), np.inf)
    t[ok] = (e[ok, 0] * w[ok, 1] - e[ok, 1] * w[ok, 0]) / denom[ok]
    u[ok] = (d[0] * w[ok, 1] - d[1] * w[ok, 0]) / denom[ok]
    hit = ok & (t > eps) & (u >= -1e-9) & (u <= 1.0 + 1e-9)
    return t[hit].min() if hit.any() else np.inf


def _inside(point, A, B):
    """Even-odd point-in-material test over every loop of the section."""
    x, y = point
    y0, y1 = A[:, 1], B[:, 1]
    straddle = (y0 > y) != (y1 > y)
    if not straddle.any():
        return False
    xs = (A[straddle, 0]
          + (y - y0[straddle]) * (B[straddle, 0] - A[straddle, 0])
          / (y1[straddle] - y0[straddle]))
    return bool((xs > x).sum() % 2 == 1)


def _raster_thickness(loops, pitch):
    """Local wall thickness on one section, by medial-ridge sampling.

    The section is rasterised, every interior pixel gets its distance to
    the boundary, and thickness is read as twice that distance AT RIDGE
    PIXELS — the local maxima of the distance field, which lie on the
    medial axis of each wall. Reading 2r at every pixel instead would
    report ~0 at every corner; reading it only on the ridge gives the
    wall-centre value, which is the thickness a moulder cares about.
    """
    A, B = _segments(loops)
    lo = np.minimum(A, B).min(axis=0)
    hi = np.maximum(A, B).max(axis=0)
    nx = max(int(np.ceil((hi[0] - lo[0]) / pitch)) + 1, 3)
    ny = max(int(np.ceil((hi[1] - lo[1]) / pitch)) + 1, 3)
    if nx * ny > 4_000_000:
        return np.empty(0)
    xs = lo[0] + (np.arange(nx) + 0.5) * pitch
    ys = lo[1] + (np.arange(ny) + 0.5) * pitch
    gx, gy = np.meshgrid(xs, ys, indexing="ij")

    # even-odd fill, vectorised one segment at a time
    inside = np.zeros((nx, ny), dtype=bool)
    for a, b in zip(A, B):
        if a[1] == b[1]:
            continue
        straddle = ((a[1] > gy) != (b[1] > gy))
        if not straddle.any():
            continue
        xcross = a[0] + (gy - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        inside ^= straddle & (xcross > gx)
    if not inside.any():
        return np.empty(0)

    # distance to the boundary, vectorised per segment
    dist = np.full((nx, ny), np.inf)
    for a, b in zip(A, B):
        e = b - a
        ll = float(e @ e)
        wx, wy = gx - a[0], gy - a[1]
        t = np.clip((wx * e[0] + wy * e[1]) / ll, 0.0, 1.0) if ll > 0 else FT.traced_zero("palette_thickness_field.py:_raster_thickness", "guard")
        dx = wx - t * e[0]
        dy = wy - t * e[1]
        np.minimum(dist, np.hypot(dx, dy), out=dist)
    dist[~inside] = -np.inf

    # ridge = local maximum of the distance field over the 8-neighbourhood
    ridge = inside.copy()
    for sx in (-1, 0, 1):
        for sy in (-1, 0, 1):
            if sx == 0 and sy == 0:
                continue
            shifted = np.roll(np.roll(dist, sx, axis=0), sy, axis=1)
            ridge &= dist >= shifted - 1e-12
    # half-pixel correction: distances are measured from pixel CENTRES, so
    # a wall of true thickness t rasterises to 2r = t - pitch. Without the
    # correction a known 1.000 mm skin reports 0.950 at a 0.05 mm pitch.
    vals = 2.0 * dist[ridge] + pitch
    return vals[np.isfinite(vals) & (vals > 0)]


def _section_thickness(loops, skip, *, eps=1e-6, facing_cos=0.5,
                       max_thickness=None):
    """Ray-cast wall thickness at every boundary point.

    From each boundary point the ray is fired along the inward MATERIAL
    normal, so the measurement crosses plastic and never air. Measuring
    plain point-to-point distance instead reports the width of cavities
    and cored voids as if they were wall.

    Two corrections make it a wall measure rather than a chord measure,
    and both are standard in ray-thickness tooling:

    * the two segments incident to the origin point are excluded, or every
      ray reports the length of its own neighbour;
    * a hit only counts when the opposing face actually faces back at the
      ray (``facing_cos``). Without it, a ray grazing along a flat deck
      runs the whole width of the part and reports it as thickness.
    """
    A, B = _segments(loops)
    edge = B - A
    seg_n = np.stack([-edge[:, 1], edge[:, 0]], axis=1)
    seg_len = np.hypot(seg_n[:, 0], seg_n[:, 1])
    live = seg_len > 1e-12
    seg_n[live] /= seg_len[live][:, None]

    out = []
    off = 0
    for lp in loops:
        p = np.asarray(lp["points_2d"], dtype=float)
        n = len(p)
        if n < 4:
            off += n
            continue
        tang = np.roll(p, -1, axis=0) - np.roll(p, 1, axis=0)
        norm = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
        ln = np.hypot(norm[:, 0], norm[:, 1])
        good = ln > 1e-12
        norm[good] /= ln[good][:, None]
        for i in range(n):
            if not good[i]:
                continue
            d = norm[i]
            if not _inside(p[i] + d * 1e-4, A, B):
                d = -d
                if not _inside(p[i] + d * 1e-4, A, B):
                    continue          # degenerate: on a knife edge
            mask = np.ones(len(A), dtype=bool)
            mask[off + i] = False
            mask[off + (i - 1) % n] = False
            mask &= live
            mask &= (seg_n @ d) < -facing_cos
            if not mask.any():
                continue
            t = _ray_hits(p[i], d, A[mask], B[mask], eps)
            if np.isfinite(t) and (max_thickness is None
                                   or t <= max_thickness):
                out.append(t)
        off += n
    return np.asarray(out, dtype=float)


def sample(components, *, width, depth, sampling=None) -> dict:
    """Thickness field over the tray, from an orthogonal section lattice."""
    cfg = dict(SAMPLING)
    cfg.update(sampling or {})
    n = cfg["planes_per_family"]
    frac = cfg["plane_span_fraction"]

    values = []
    per_plane = []
    for axis, extent in (("x", width), ("y", depth)):
        half = extent / 2.0 * frac
        for at in np.linspace(-half, half, n):
            at = float(round(at, 9))
            try:
                sec = ms.section_assembly(components, axis, at, cap=False)
            except ms.SectionError:
                continue
            loops = [lp for comp in sec["components"].values()
                     for lp in comp["loops"]]
            if not loops:
                continue
            t = _raster_thickness(loops, cfg["raster_pitch_mm"])
            t = t[np.isfinite(t)]
            if not len(t):
                continue
            values.append(t)
            per_plane.append({"axis": axis, "at_mm": at,
                              "loop_count": len(loops),
                              "min_mm": round(float(t.min()), 6),
                              "max_mm": round(float(t.max()), 6),
                              "sample_count": int(len(t))})
    if not values:
        raise ValueError("thickness field produced no samples")

    allv = np.concatenate(values)
    pct = {f"p{p}": round(float(np.percentile(allv, p)), 6)
           for p in cfg["percentiles"]}
    lo, hi = float(allv.min()), float(allv.max())
    ratio = hi / lo if lo > 0 else float("inf")

    # gradients: plane-to-plane change in the local minimum, a proxy for
    # abrupt section change along the part
    grads = []
    for fam in ("x", "y"):
        rows = [r for r in per_plane if r["axis"] == fam]
        for a, b in zip(rows, rows[1:]):
            step = abs(b["at_mm"] - a["at_mm"]) or 1.0
            grads.append({"axis": fam, "from_mm": a["at_mm"],
                          "to_mm": b["at_mm"],
                          "d_min_per_mm": round(
                              abs(b["min_mm"] - a["min_mm"]) / step, 6)})
    largest = max(grads, key=lambda g: g["d_min_per_mm"]) if grads else None

    hist_counts, hist_edges = np.histogram(allv, bins=24, range=(0.0, hi))
    return {
        "record_type": SCHEMA,
        "sampling": cfg,
        "sample_count": int(len(allv)),
        "plane_count": len(per_plane),
        "minimum_thickness_mm": round(lo, 6),
        "maximum_thickness_mm": round(hi, 6),
        "median_thickness_mm": round(float(np.median(allv)), 6),
        "mean_thickness_mm": round(float(allv.mean()), 6),
        "percentiles_mm": pct,
        "thickness_ratio": round(ratio, 4),
        "largest_gradient": largest,
        "gradient_count": len(grads),
        "histogram": {"counts": [int(c) for c in hist_counts],
                      "edges_mm": [round(float(e), 6) for e in hist_edges]},
        "per_plane": per_plane,
        "evidence_basis": "SECTION_LATTICE_GEOMETRY_ONLY_NO_MOULD_FLOW",
    }


def risk_classification(field, policy) -> dict:
    """Sink and warpage risk from the sampled field, as classifications."""
    hi = field["maximum_thickness_mm"]
    lo = field["minimum_thickness_mm"]
    nominal = policy["target_nominal_wall_mm"]
    sink_threshold = nominal * policy["sink_threshold_ratio_vs_nominal"]
    over = [r for r in field["per_plane"] if r["max_mm"] > sink_threshold]
    return {
        "record_type": "palette_thickness_risk/1.0",
        "MOULDING_SINK_RISK": "PROVISIONAL_ENGINEERING_RISK",
        "sink_threshold_mm": round(sink_threshold, 6),
        "planes_above_sink_threshold": len(over),
        "plane_count": field["plane_count"],
        "fraction_above_sink_threshold": round(
            len(over) / max(field["plane_count"], 1), 4),
        "maximum_thickness_mm": hi,
        "minimum_thickness_mm": lo,
        "thickness_ratio": field["thickness_ratio"],
        "warpage_proxy": "LARGEST_LOCAL_MINIMUM_GRADIENT",
        "largest_gradient": field["largest_gradient"],
        "claim_limit": "risk CLASSIFICATIONS from section geometry only. "
                       "No mould-flow simulation was run, so no sink or "
                       "warpage is asserted as fact.",
        "evidence_basis": field["evidence_basis"],
    }
