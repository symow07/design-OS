"""vq2_polyline_equivalence_distance/1.0 — symmetric point-to-SEGMENT distance.

The previous metric compared sampled vertices only. Two polylines tracing the
same curve at different subdivision densities place vertices at different arc
positions, so vertex-to-vertex distance reports separation where none exists.
That produced a false negative on every glyph.

Here every sample point is measured against the opposing polyline's SEGMENTS
via a clamped projection, and the result is symmetric (both directions).
"""
from __future__ import annotations

import math

SCHEMA = "vq2_polyline_equivalence_distance/1.0"
NONAUTHORITATIVE_LEGACY = "VQ2_POINT_TO_VERTEX_DISTANCE_NONAUTHORITATIVE"
AMBIGUOUS = "VQ2_CONTOUR_CORRESPONDENCE_AMBIGUOUS"


def point_segment_distance(p, a, b):
    """Clamped projection of p onto segment ab. Zero-length safe."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    if den == 0.0:                       # degenerate segment
        return math.hypot(p[0] - ax, p[1] - ay), 0.0, (ax, ay)
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / den
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(p[0] - cx, p[1] - cy), t, (cx, cy)


def point_to_polyline(p, poly):
    """Minimum distance from p to any segment of a CLOSED polyline."""
    best, bt, bc, bi = float("inf"), 0.0, None, -1
    n = len(poly)
    for i in range(n):
        d, t, c = point_segment_distance(p, poly[i], poly[(i + 1) % n])
        if d < best:
            best, bt, bc, bi = d, t, c, i
    return best, bt, bc, bi


def directed(samples, targets):
    """Max/mean/percentiles from every sample to the nearest target segment."""
    dists, worst = [], None
    for poly in samples:
        for p in poly:
            best = float("inf")
            info = None
            for tp in targets:
                d, t, c, i = point_to_polyline(p, tp)
                if d < best:
                    best, info = d, (p, i, t, c)
            dists.append(best)
            if worst is None or best > worst[0]:
                worst = (best, info)
    if not dists:
        return {"count": 0}
    s = sorted(dists)

    def pct(q):
        k = max(0, min(len(s) - 1, int(round(q * (len(s) - 1)))))
        return s[k]
    return {"count": len(s), "max": s[-1], "p99": pct(0.99), "p95": pct(0.95),
            "mean": sum(s) / len(s),
            "worst_sample": None if worst is None else {
                "point": [round(v, 4) for v in worst[1][0]],
                "opposing_segment_index": worst[1][1],
                "projection_t": round(worst[1][2], 5),
                "closest_point": [round(v, 4) for v in worst[1][3]],
                "distance": round(worst[0], 5)}}


def symmetric(source, converted):
    """Both directed comparisons plus the symmetric summary."""
    a = directed(source, converted)
    b = directed(converted, source)
    return {
        "schema": SCHEMA,
        "source_to_converted": a,
        "converted_to_source": b,
        "symmetric_max": max(a["max"], b["max"]),
        "symmetric_p99": max(a["p99"], b["p99"]),
        "symmetric_p95": max(a["p95"], b["p95"]),
        "symmetric_mean": (a["mean"] * a["count"] + b["mean"] * b["count"])
        / max(1, a["count"] + b["count"]),
        "directed_max_source_to_converted": a["max"],
        "directed_max_converted_to_source": b["max"],
    }


# --- contour correspondence ---------------------------------------------------

def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1]
                   - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2.0


def _centroid(poly):
    n = len(poly)
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


def correspond(source, converted):
    """Pair contours by geometry (area + centroid), never by list index."""
    if len(source) != len(converted):
        return None, AMBIGUOUS
    used, pairs = set(), []
    for i, s in enumerate(source):
        sa, sc = _area(s), _centroid(s)
        best, bj = None, -1
        for j, c in enumerate(converted):
            if j in used:
                continue
            ca, cc = _area(c), _centroid(c)
            cost = (abs(sa - ca) / max(sa, 1e-9)
                    + math.hypot(sc[0] - cc[0], sc[1] - cc[1]) / 100.0)
            if best is None or cost < best:
                best, bj = cost, j
        if bj < 0:
            return None, AMBIGUOUS
        used.add(bj)
        pairs.append((i, bj, round(best, 6)))
    return pairs, None
