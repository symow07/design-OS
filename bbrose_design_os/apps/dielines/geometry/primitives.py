"""Primitive path segments for cut-line geometry.

The geometry engine builds tuck-flap shoulders as true cubic Beziers,
but Shapely only consumes polygons of straight-line vertices. To
preserve the real curve through to SVG output (so Illustrator sees
real `C` commands rather than 20-segment polylines), each curved
component is built first as a list of these primitives and then
*also* sampled to a Shapely polygon for union/buffer math.

The SVG exporter prefers primitives when present and falls back to
polygon-to-polyline for straight-edged components.
"""
from __future__ import annotations

from dataclasses import dataclass


Point = tuple[float, float]


@dataclass(frozen=True)
class LineSeg:
    p0: Point
    p1: Point


@dataclass(frozen=True)
class CubicSeg:
    p0: Point
    c1: Point
    c2: Point
    p1: Point


Primitive = LineSeg | CubicSeg


def sample_path(path: list[Primitive], cubic_segments: int = 20) -> list[Point]:
    """Flatten a primitive path into a polyline.

    Used to feed the same geometry into Shapely for union/buffer/area
    operations. The number of cubic segments matches what the engine
    used previously, so polygon areas stay numerically equivalent.
    """
    pts: list[Point] = []
    if not path:
        return pts
    pts.append(path[0].p0)
    for seg in path:
        if isinstance(seg, LineSeg):
            pts.append(seg.p1)
        else:
            for i in range(1, cubic_segments + 1):
                t = i / cubic_segments
                u = 1.0 - t
                x = (u * u * u * seg.p0[0]
                     + 3 * u * u * t * seg.c1[0]
                     + 3 * u * t * t * seg.c2[0]
                     + t * t * t * seg.p1[0])
                y = (u * u * u * seg.p0[1]
                     + 3 * u * u * t * seg.c1[1]
                     + 3 * u * t * t * seg.c2[1]
                     + t * t * t * seg.p1[1])
                pts.append((x, y))
    return pts


def path_to_svg_d(
    path: list[Primitive], dx: float = 0.0, dy: float = 0.0,
) -> str:
    """Emit an SVG path `d` attribute using M / L / C / Z.

    Cubic primitives become real `C` commands so prepress software
    (Illustrator, Inkscape) receives true Bezier curves instead of
    polyline approximations.
    """
    if not path:
        return ""
    parts: list[str] = []
    x0, y0 = path[0].p0
    parts.append(f"M {x0 + dx:.4f} {y0 + dy:.4f}")
    for seg in path:
        if isinstance(seg, LineSeg):
            x, y = seg.p1
            parts.append(f"L {x + dx:.4f} {y + dy:.4f}")
        else:
            c1x, c1y = seg.c1
            c2x, c2y = seg.c2
            x, y = seg.p1
            parts.append(
                f"C {c1x + dx:.4f} {c1y + dy:.4f} "
                f"{c2x + dx:.4f} {c2y + dy:.4f} "
                f"{x + dx:.4f} {y + dy:.4f}"
            )
    parts.append("Z")
    return " ".join(parts)
