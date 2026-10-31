"""Shared canonical-contour helpers for the VQ-1 correction fixtures.

One place for the two rules every corrected fixture depends on: a right
side is produced by mathematically mirroring the left half (never authored
twice), and curvature is sampled from the cubic itself rather than
asserted."""
from __future__ import annotations

from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo


def segment_starts(segs):
    cur, out = None, []
    for s in segs:
        out.append(cur)
        if not isinstance(s, ClosePath):
            cur = (s.x, s.y)
    return out


def mirrored_return(segs, cx: float):
    """Left half traced start->end (first segment a MoveTo) -> the mirrored
    right half traced end->start, control points reflected and reversed."""
    starts = segment_starts(segs)
    out = []
    for seg, start in zip(segs[::-1], starts[::-1]):
        if isinstance(seg, MoveTo):
            continue
        if isinstance(seg, LineTo):
            out.append(LineTo(x=2 * cx - start[0], y=start[1]))
        elif isinstance(seg, CubicTo):
            out.append(CubicTo(x1=2 * cx - seg.x2, y1=seg.y2,
                               x2=2 * cx - seg.x1, y2=seg.y1,
                               x=2 * cx - start[0], y=start[1]))
    return out


def closed_from_left(left_half, cx: float):
    return left_half + mirrored_return(left_half, cx) + [ClosePath()]


def cubic_point(seg, p0, t):
    x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * seg.x1
         + 3 * (1 - t) * t ** 2 * seg.x2 + t ** 3 * seg.x)
    y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * seg.y1
         + 3 * (1 - t) * t ** 2 * seg.y2 + t ** 3 * seg.y)
    return x, y


def cubic_curvature_samples(p0_seg, seg, n: int = 17):
    """Curvature along one cubic. Interior samples only — a clamped
    one-sided difference at an exact endpoint reads as 0 and is not real
    curvature."""
    p0 = (p0_seg.x, p0_seg.y) if hasattr(p0_seg, "x") else p0_seg
    out = []
    for i in range(n):
        t = 0.02 + 0.96 * i / (n - 1)
        dt = 1e-4
        a = cubic_point(seg, p0, t - dt)
        b = cubic_point(seg, p0, t + dt)
        m = cubic_point(seg, p0, t)
        dx, dy = (b[0] - a[0]) / (2 * dt), (b[1] - a[1]) / (2 * dt)
        ddx = (b[0] - 2 * m[0] + a[0]) / dt ** 2
        ddy = (b[1] - 2 * m[1] + a[1]) / dt ** 2
        den = (dx * dx + dy * dy) ** 1.5 or 1e-9
        out.append({"t": round(t, 3), "x": round(m[0], 3),
                    "y": round(m[1], 3),
                    "curvature": round(abs(dx * ddy - dy * ddx) / den, 6)})
    return out
