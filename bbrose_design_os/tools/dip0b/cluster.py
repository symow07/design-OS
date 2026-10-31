"""Deterministic spatial clustering (DIP-0B2).

Grouping N bounding boxes by proximity is a union-find over "dilated rects that
touch". Done pairwise it is quadratic in dense glyph fields — the pilot's worst
page holds 67,156 paths, most of them glyph-scale.

Instead we paint each dilated bbox into a bounded raster and run connected
components. Two dilated boxes intersect **iff** their painted pixels overlap, so
the grouping is the same, at pixel resolution, in linear time. Pure numpy — no
scipy, no OpenCV.

Determinism: the raster grid, the paint order and the final ordering are all
functions of the inputs, so identical bytes + identical thresholds produce
identical clusters.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Grid:
    """pt → px mapping for a bounded raster."""

    origin_x: float
    origin_y: float
    zoom: float
    width: int
    height: int

    def to_px(self, x: float, y: float) -> tuple[int, int]:
        return (int((x - self.origin_x) * self.zoom),
                int((y - self.origin_y) * self.zoom))

    def to_pt(self, px: int, py: int) -> tuple[float, float]:
        return (px / self.zoom + self.origin_x, py / self.zoom + self.origin_y)


def build_grid(bbox_pt: tuple[float, float, float, float],
               max_long_edge: int, max_pixels: int) -> Grid:
    x0, y0, x1, y1 = bbox_pt
    w_pt = max(x1 - x0, 1e-6)
    h_pt = max(y1 - y0, 1e-6)
    zoom = min(1.0, max_long_edge / max(w_pt, h_pt))
    if zoom <= 0:
        zoom = 1.0
    px = (w_pt * zoom) * (h_pt * zoom)
    if px > max_pixels:
        zoom *= math.sqrt(max_pixels / px)
    w = max(1, int(math.ceil(w_pt * zoom)))
    h = max(1, int(math.ceil(h_pt * zoom)))
    return Grid(x0, y0, zoom, w, h)


def label_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected connected components over a boolean mask (run-length + union-find).

    Returns (labels, count) with labels in 1..count and 0 for background.
    """
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent: list[int] = [0]           # parent[0] unused

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)   # keep the smaller root: stable

    prev_runs: list[tuple[int, int, int]] = []
    for y in range(h):
        row = mask[y]
        if not row.any():
            prev_runs = []
            continue
        # runs of True in this row
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        runs: list[tuple[int, int, int]] = []
        for s, e in zip(starts, ends):
            lbl = 0
            for ps, pe, pl in prev_runs:
                if ps < e and s < pe:              # overlap on the row above
                    lbl = pl if lbl == 0 else lbl
                    if lbl != pl:
                        union(lbl, pl)
                    lbl = min(find(lbl), find(pl))
            if lbl == 0:
                parent.append(len(parent))
                lbl = len(parent) - 1
            labels[y, s:e] = lbl
            runs.append((s, e, lbl))
        prev_runs = runs

    if len(parent) == 1:
        return labels, 0

    # flatten unions, then compact to 1..n in first-appearance order
    roots = np.array([find(i) for i in range(len(parent))], dtype=np.int32)
    remap = np.zeros(len(parent), dtype=np.int32)
    nxt = 0
    for i in range(1, len(parent)):
        r = roots[i]
        if remap[r] == 0:
            nxt += 1
            remap[r] = nxt
        remap[i] = remap[r]
    labels = np.where(labels > 0, remap[labels], 0)
    return labels, int(nxt)


def cluster_rects(rects_pt, gap_pt: float, grid: Grid) -> list[list[int]]:
    """Group rect indices whose `gap_pt`-dilated boxes touch.

    Rects are `(x0, y0, x1, y1)` in points. Empty/degenerate rects still paint at
    least one pixel, so a hairline stroke is never dropped.
    """
    if not len(rects_pt):
        return []
    dil = max(1, int(round(gap_pt * grid.zoom / 2.0)))
    mask = np.zeros((grid.height, grid.width), dtype=bool)

    boxes = []
    for r in rects_pt:
        x0, y0 = grid.to_px(r[0], r[1])
        x1, y1 = grid.to_px(r[2], r[3])
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        x0 = max(0, x0 - dil)
        y0 = max(0, y0 - dil)
        x1 = min(grid.width, x1 + dil + 1)
        y1 = min(grid.height, y1 + dil + 1)
        if x1 <= x0:
            x1 = min(grid.width, x0 + 1)
        if y1 <= y0:
            y1 = min(grid.height, y0 + 1)
        boxes.append((x0, y0, x1, y1))
        mask[y0:y1, x0:x1] = True

    labels, n = label_components(mask)
    if n == 0:
        return []

    groups: dict[int, list[int]] = {}
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        # every painted box has a labelled interior; sample its centre
        cy = min(grid.height - 1, (y0 + y1) // 2)
        cx = min(grid.width - 1, (x0 + x1) // 2)
        lab = int(labels[cy, cx])
        if lab == 0:                       # defensive: take any painted pixel
            sub = labels[y0:y1, x0:x1]
            nz = sub[sub > 0]
            if nz.size == 0:
                continue
            lab = int(nz[0])
        groups.setdefault(lab, []).append(i)

    return [sorted(v) for _, v in sorted(groups.items())]


def union_bbox(rects, idxs) -> tuple[float, float, float, float]:
    xs0 = min(rects[i][0] for i in idxs)
    ys0 = min(rects[i][1] for i in idxs)
    xs1 = max(rects[i][2] for i in idxs)
    ys1 = max(rects[i][3] for i in idxs)
    return (xs0, ys0, xs1, ys1)


def iou(a, b) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    aa = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    bb = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    denom = aa + bb - inter
    return inter / denom if denom > 0 else 0.0


def containment(inner, outer) -> float:
    """Fraction of `inner`'s area lying inside `outer`."""
    ix0, iy0 = max(inner[0], outer[0]), max(inner[1], outer[1])
    ix1, iy1 = min(inner[2], outer[2]), min(inner[3], outer[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area = max(1e-9, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return inter / area


def clip_rect(r, box):
    """Intersection of `r` with `box`, or None if genuinely disjoint.

    Degenerate rects are real geometry: a hairline rule has zero height, and a
    vertical rule zero width. Demanding a strictly positive intersection area
    once pushed 95 in-ArtBox hairlines of `ES3083` out into the off-canvas
    workspace. Equality is therefore an intersection.
    """
    x0, y0 = max(r[0], box[0]), max(r[1], box[1])
    x1, y1 = min(r[2], box[2]), min(r[3], box[3])
    if x1 < x0 or y1 < y0:
        return None
    return (x0, y0, x1, y1)


def area(r) -> float:
    return max(0.0, (r[2] - r[0])) * max(0.0, (r[3] - r[1]))
