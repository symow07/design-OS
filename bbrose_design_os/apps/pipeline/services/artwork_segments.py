"""Cut the approved artwork into separate motif elements (2026-07-07).

The components .ai placed the motif as ONE raster; designers need each
element — every flower, every cluster — as its own movable object. This
service segments the text-free motif image against its dominant background
color: alpha mask by color distance, connected-component labeling (numpy
two-pass union-find, 8-connectivity), one soft-edged RGBA crop per element.

The result preserves the EXACT approved artwork pixels — nothing is
regenerated. Segmentation is advisory: `[]` tells the caller to keep the
proven single-raster path, and that happens whenever cutting would be
meaningless (full-bleed gradients, near-empty masks) or anything fails.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

_LABEL_MAX_SIDE = 1024      # labeling resolution (boxes mapped back to full res)
_EDGE_SOFT_PX = 2           # alpha falloff at the cut edge, full-res pixels


@dataclass
class ArtworkSegment:
    image: object            # PIL RGBA crop, background pixels transparent
    x: int                   # bbox in FULL-RES artwork pixel space
    y: int
    w: int
    h: int


def _hex_rgb(color_hex: str) -> tuple[int, int, int]:
    h = (color_hex or "#EFE9E4").lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _label_components(mask):
    """8-connectivity two-pass labeling with numpy union-find.

    Returns (labels array, count). Row-wise runs are grouped first, then
    merged across rows — fast enough at <=1024px without scipy.
    """
    import numpy as np

    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent = [0]                                # parent[i] for union-find

    def find(i):
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:                # path compression
            parent[i], i = root, parent[i]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    next_label = 1
    for r in range(h):
        row = mask[r]
        c = 0
        while c < w:
            if not row[c]:
                c += 1
                continue
            run_start = c
            while c < w and row[c]:
                c += 1
            # neighbors in the previous row (8-connectivity → widen by 1)
            neigh = []
            if r > 0:
                lo = max(0, run_start - 1)
                hi = min(w, c + 1)
                prev = labels[r - 1, lo:hi]
                neigh = [int(v) for v in np.unique(prev) if v]
            if neigh:
                lab = min(find(n) for n in neigh)
                for n in neigh:
                    union(lab, n)
            else:
                lab = next_label
                parent.append(lab)
                next_label += 1
            labels[r, run_start:c] = lab

    if next_label == 1:
        return labels, 0
    # resolve unions + compact label ids
    roots = np.array([find(i) for i in range(next_label)], dtype=np.int32)
    remap = np.zeros(next_label, dtype=np.int32)
    uniq = np.unique(roots[1:])
    for new_id, root in enumerate(uniq, start=1):
        remap[roots == root] = new_id
    return remap[labels], len(uniq)


def segment_artwork(motif_path: str, background_hex: str, *,
                    max_elements: int | None = None,
                    min_area_frac: float | None = None,
                    log=None) -> list[ArtworkSegment]:
    """Segments of the motif image, or [] meaning 'keep the single raster'."""
    log = log or (lambda msg, data=None, level="info": None)
    max_elements = max_elements or settings.SEGMENT_MAX_ELEMENTS
    min_area_frac = (min_area_frac if min_area_frac is not None
                     else settings.SEGMENT_MIN_AREA_FRAC)
    try:
        import numpy as np
        from PIL import Image

        with Image.open(motif_path) as im:
            rgb_full = np.asarray(im.convert("RGB"), dtype=np.int16)
        fh, fw = rgb_full.shape[:2]

        bg = np.array(_hex_rgb(background_hex), dtype=np.int16)
        dist_full = np.sqrt(((rgb_full - bg) ** 2).sum(axis=2))
        fg_full = dist_full > settings.SEGMENT_BG_THRESHOLD

        coverage = fg_full.mean()
        if coverage < 0.02 or coverage > 0.98:
            log(f"segmentation: mask coverage {coverage:.0%} — keeping "
                f"single raster")
            return []

        # label at reduced resolution for speed
        scale = max(1, int(np.ceil(max(fh, fw) / _LABEL_MAX_SIDE)))
        small = fg_full[::scale, ::scale]
        # 1-iteration binary close to heal antialias pinholes
        padded = np.pad(small, 1)
        dil = (padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2]
               | padded[1:-1, 2:] | padded[1:-1, 1:-1])
        pad2 = np.pad(dil, 1, constant_values=True)
        closed = (pad2[:-2, 1:-1] & pad2[2:, 1:-1] & pad2[1:-1, :-2]
                  & pad2[1:-1, 2:] & pad2[1:-1, 1:-1])

        labels, count = _label_components(closed)
        if count == 0:
            return []

        areas = np.bincount(labels.ravel())[1:]          # per label id (1-based)
        canvas_area = closed.shape[0] * closed.shape[1]
        order = np.argsort(areas)[::-1] + 1              # label ids by size

        if areas[order[0] - 1] / canvas_area > 0.70:
            log("segmentation: one component covers >70% (full-bleed art) — "
                "keeping single raster")
            return []

        keep = [int(lab) for lab in order
                if areas[lab - 1] / canvas_area >= min_area_frac][:max_elements]
        if not keep:
            return []

        segments: list[ArtworkSegment] = []
        soft = float(_EDGE_SOFT_PX * settings.SEGMENT_BG_THRESHOLD)
        for lab in keep:
            ys, xs = np.nonzero(labels == lab)
            # map back to full res (+scale-1 pad to cover the sampling gap)
            x0 = int(xs.min()) * scale
            y0 = int(ys.min()) * scale
            x1 = min(fw, (int(xs.max()) + 1) * scale + scale - 1)
            y1 = min(fh, (int(ys.max()) + 1) * scale + scale - 1)
            if x1 - x0 < 4 or y1 - y0 < 4:
                continue
            crop = rgb_full[y0:y1, x0:x1]
            d = dist_full[y0:y1, x0:x1]
            # soft alpha: 0 at the background color, ramping to 255 just past
            # the threshold — keeps engraved edges smooth, kills the ground
            t = settings.SEGMENT_BG_THRESHOLD
            alpha = np.clip((d - t * 0.5) / max(soft, 1.0), 0.0, 1.0) * 255.0
            rgba = np.dstack([
                crop.astype(np.uint8), alpha.astype(np.uint8),
            ])
            segments.append(ArtworkSegment(
                image=Image.fromarray(rgba, mode="RGBA"),
                x=x0, y=y0, w=x1 - x0, h=y1 - y0,
            ))
        if len(segments) < 2:
            # a single cut element is the whole motif — not worth cutting
            return []
        log(f"segmentation: {len(segments)} separate motif element(s)")
        return segments
    except Exception as exc:  # noqa: BLE001 — advisory; single raster fallback
        logger.warning("artwork segmentation failed: %s", exc)
        return []
