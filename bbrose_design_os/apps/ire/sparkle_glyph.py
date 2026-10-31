"""[His look at 117 drawn from its map, 2026-10-02 (transcribed at 99ede0a): "when it comes to these small designs, like
those sparkles, oh, they are always inconsistent. And not looking good. I want to fix that."] THE ONE SPARKLE every
drawing draws — four arms, top, right, foot and left, each ending in a blunt tip ``tip`` of the sparkle's span across
it wide each side, joined tip to tip by a cubic arc whose handles are pulled toward the centre by the sparkle's PINCH:
pinch 0 and tip 0 is a straight-sided diamond; a high pinch makes thin arms and a small heart; a tip keeps an arm's
width to its end, as a printed sparkle's does. One clean shape, sized per sparkle and placed per sparkle, never traced from the handful of
pixels a small sparkle prints in and never a straight-sided polygon.

Everything here is millimetres or fractions, in the caller's own frame (y down)."""
from __future__ import annotations

from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo

#: the sparkle design 117's concept picture measures (2026-10-02: the pinch whose arms are as wide as its gold's, a
#: quarter and half way out, on the eight sparkles a fit could read — 0.6 to 0.75, their median 0.7) — the house
#: sparkle where no picture measures one; its tip is a fine one, finer than the picture's pixels can measure
HOUSE_PINCH = 0.7
HOUSE_TIP = 0.03


def _corners(cx: float, cy: float, half_w: float, half_h: float, tip: float) -> list:
    """Each arm's tip as its two corners, clockwise from the top tip's left."""
    tw, th = tip * half_w, tip * half_h            # an arm's half width at its end: a share of the span across it
    return [((cx - tw, cy - half_h), (cx + tw, cy - half_h)), ((cx + half_w, cy - th), (cx + half_w, cy + th)),
            ((cx + tw, cy + half_h), (cx - tw, cy + half_h)), ((cx - half_w, cy + th), (cx - half_w, cy - th))]


def _arcs(cx: float, cy: float, half_w: float, half_h: float, pinch: float, tip: float) -> list:
    """``[(tip corner a, handle 1, handle 2, next tip corner b)]`` — the four arcs, clockwise from the top tip."""
    tips = _corners(cx, cy, half_w, half_h, tip)
    out = []
    for i in range(4):
        a, b = tips[i][1], tips[(i + 1) % 4][0]
        out.append((a, (a[0] + (cx - a[0]) * pinch, a[1] + (cy - a[1]) * pinch),
                    (b[0] + (cx - b[0]) * pinch, b[1] + (cy - b[1]) * pinch), b))
    return out


def segments(cx: float, cy: float, half_w: float, half_h: float, pinch: float, tip: float) -> list:
    """The sparkle as a closed path: the top tip first, clockwise — each tip straight across, each side one arc."""
    tips = _corners(cx, cy, half_w, half_h, tip)
    out = [MoveTo(x=tips[0][0][0], y=tips[0][0][1])]
    for i, (a, h1, h2, b) in enumerate(_arcs(cx, cy, half_w, half_h, pinch, tip)):
        if tip:
            out.append(LineTo(x=a[0], y=a[1]))
        out.append(CubicTo(x1=h1[0], y1=h1[1], x2=h2[0], y2=h2[1], x=b[0], y=b[1]))
    return out + [ClosePath()]


def outline(cx: float, cy: float, half_w: float, half_h: float, pinch: float, tip: float, steps: int) -> list:
    """The sparkle's outline sampled as points — ``steps`` along each arc, and each tip's corners — for a box, a
    raster or a score."""
    pts = []
    for a, h1, h2, b in _arcs(cx, cy, half_w, half_h, pinch, tip):
        for k in range(steps):
            t = k / float(steps)
            u = 1.0 - t
            pts.append((u ** 3 * a[0] + 3 * u * u * t * h1[0] + 3 * u * t * t * h2[0] + t ** 3 * b[0],
                        u ** 3 * a[1] + 3 * u * u * t * h1[1] + 3 * u * t * t * h2[1] + t ** 3 * b[1]))
        pts.append(b)
    return pts


def arm_width(half_w: float, half_h: float, pinch: float, tip: float, along: float) -> float:
    """How wide the top arm is ``along`` of its reach out from the centre (0 the centre, 1 its tip)."""
    pts = outline(0.0, 0.0, half_w, half_h, pinch, tip, 120)
    y = -along * half_h
    xs = [ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1])
          if (ay - y) * (by - y) <= 0 and ay != by]
    return max(xs) - min(xs) if xs else 0.0


__all__ = ["HOUSE_PINCH", "HOUSE_TIP", "segments", "outline", "arm_width"]
