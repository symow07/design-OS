"""Deterministic silhouette extraction for the ARIA Visual Inspector.

Pixels only — numpy + Pillow, no scipy/OpenCV. Everything downstream
(contour distance, symmetry, parallelism, landmarks) is computed from the
half-width profile this module produces, so the extractor is validated
against hand-read reference landmarks before any metric is trusted:
``validate_against_reference`` must reproduce the collar, body and
shoulder measurements read off the committed gridded crops.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

EXTRACT_SCHEMA = "visual_silhouette_profile/1.0"


def _load(path: str, max_side: int = 1400) -> np.ndarray:
    im = Image.open(path).convert("RGB")
    if max(im.size) > max_side:
        k = max_side / max(im.size)
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))),
                       Image.LANCZOS)
    return np.asarray(im).astype(np.float32)


def _background(rgb: np.ndarray, pad: int = 6) -> np.ndarray:
    """Median of the four corner patches — the backdrop, not the subject."""
    h, w = rgb.shape[:2]
    p = max(3, min(pad, h // 8, w // 8))
    corners = np.concatenate([
        rgb[:p, :p].reshape(-1, 3), rgb[:p, -p:].reshape(-1, 3),
        rgb[-p:, :p].reshape(-1, 3), rgb[-p:, -p:].reshape(-1, 3)])
    return np.median(corners, axis=0)


def _row_backdrop(rgb: np.ndarray, margin: int = 8, side: str = "right"):
    """Per-row backdrop from a clean image margin. Reference photographs
    are lit unevenly top-to-bottom, so one global background colour
    under-segments the lower rows."""
    strip = rgb[:, -margin:] if side == "right" else rgb[:, :margin]
    return np.median(strip, axis=1), strip.std(axis=(1, 2))


def edge_profile(path: str, centerline_px: float, *, side: str = "right",
                 min_run: int = 3, floor: float = 16.0) -> dict:
    """Measure the silhouette from ONE clean side about a known
    centerline. Used for reference photographs where the opposite edge is
    occluded by an adjacent object (the carton in reference #97), which
    no colour threshold can separate — the occlusion is reported rather
    than silently guessed."""
    rgb = _load(path, max_side=100000)          # no resample: px are data
    h, w = rgb.shape[:2]
    bg, noise = _row_backdrop(rgb, side=side)
    cx = float(centerline_px)
    half, edges = [], []
    for y in range(h):
        thr = max(floor, 3.5 * float(noise[y]))
        row = rgb[y]
        d = np.sqrt(((row - bg[y]) ** 2).sum(axis=1))
        hit = None
        run = 0
        rng = range(w - 1, -1, -1) if side == "right" else range(w)
        for x in rng:
            if d[x] > thr:
                run += 1
                if run >= min_run:
                    hit = x + (min_run - 1) if side == "right" \
                        else x - (min_run - 1)
                    break
            else:
                run = 0
        if hit is None:
            half.append(None)
            edges.append(None)
            continue
        hw = (hit - cx) if side == "right" else (cx - hit)
        half.append(float(hw) if hw > 0 else None)
        edges.append(int(hit))
    rows = [y for y, v in enumerate(half) if v is not None]
    return {"schema_version": EXTRACT_SCHEMA, "path": path, "method":
            f"single_side_{side}_about_calibrated_centerline",
            "height": h, "width": w, "centerline_px": cx,
            "top_px": rows[0] if rows else 0,
            "bottom_px": rows[-1] if rows else 0,
            "half_width": half, "edge": edges,
            "occlusion_note": "the opposite edge is occluded by an adjacent "
                              "object in this reference; symmetry is NOT "
                              "measurable here and is not claimed"}


def synthetic_profile(path: str, *, tol: float = 10.0) -> dict:
    """Extraction for SYNTHETIC renders. Their backdrop is a single flat
    colour, so a photographic threshold (tuned for frosted glass) badly
    under-segments pale fills. Here anything that differs from the flat
    backdrop at all is subject, and both edges are real — so symmetry IS
    measurable, unlike the occluded reference."""
    rgb = _load(path, max_side=100000)
    h, w = rgb.shape[:2]
    bg = np.median(np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]),
                   axis=0)
    d = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    mask = d > tol
    left, right = [], []
    for y in range(h):
        xs = np.flatnonzero(mask[y])
        if xs.size == 0:
            left.append(None)
            right.append(None)
        else:
            left.append(int(xs[0]))
            right.append(int(xs[-1]))
    rows = [y for y, v in enumerate(left) if v is not None]
    cols = mask.sum(axis=0)
    cx = (float((cols * np.arange(w)).sum() / cols.sum())
          if cols.sum() else w / 2.0)
    return {"schema_version": EXTRACT_SCHEMA, "path": path,
            "method": "synthetic_flat_backdrop_both_edges",
            "height": h, "width": w, "centerline_px": cx,
            "top_px": rows[0] if rows else 0,
            "bottom_px": rows[-1] if rows else 0,
            "left": left, "right": right,
            "half_width": [None if lo is None else (hi - lo) / 2.0
                           for lo, hi in zip(left, right)]}


def foreground_mask(path: str, *, sensitivity: float = 1.0
                    ) -> tuple[np.ndarray, dict]:
    """Distance-from-backdrop mask. Frosted glass on a light backdrop is a
    low-contrast subject, so the threshold is taken from the distance
    distribution itself rather than a fixed cut."""
    rgb = _load(path)
    bg = _background(rgb)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    # Otsu on the distance image
    hist, edges = np.histogram(dist, bins=128)
    tot = hist.sum()
    cum = np.cumsum(hist)
    mids = (edges[:-1] + edges[1:]) / 2
    csum = np.cumsum(hist * mids)
    best_t, best_var = mids[0], -1.0
    for i in range(1, len(hist)):
        w0, w1 = cum[i - 1], tot - cum[i - 1]
        if w0 == 0 or w1 == 0:
            continue
        m0 = csum[i - 1] / w0
        m1 = (csum[-1] - csum[i - 1]) / w1
        var = w0 * w1 * (m0 - m1) ** 2
        if var > best_var:
            best_var, best_t = var, mids[i]
    thr = best_t * sensitivity
    return dist > thr, {"threshold": float(thr),
                        "background_rgb": [float(x) for x in bg],
                        "shape": [int(rgb.shape[0]), int(rgb.shape[1])]}


def _centerline(mask: np.ndarray) -> float:
    cols = mask.sum(axis=0).astype(np.float64)
    if cols.sum() <= 0:
        return mask.shape[1] / 2.0
    idx = np.arange(mask.shape[1])
    return float((cols * idx).sum() / cols.sum())


def half_width_profile(path: str, *, sensitivity: float = 1.0) -> dict:
    """Per-row left/right extents of the subject run that spans the
    centerline. Rows with no subject are recorded as None so callers can
    see where the object actually starts and stops."""
    mask, meta = foreground_mask(path, sensitivity=sensitivity)
    h, w = mask.shape
    cx = _centerline(mask)
    ci = int(round(min(max(cx, 0), w - 1)))
    left, right = [], []
    for y in range(h):
        row = mask[y]
        if not row.any():
            left.append(None)
            right.append(None)
            continue
        # walk out from the centerline to the first background pixel,
        # tolerating short gaps (specular highlights on metal/glass)
        gap = max(2, w // 120)
        i = ci
        if not row[ci]:
            near = np.flatnonzero(row)
            i = int(near[np.argmin(np.abs(near - ci))])
            if abs(i - ci) > w * 0.25:
                left.append(None)
                right.append(None)
                continue
        li = i
        run = 0
        for x in range(i, -1, -1):
            if row[x]:
                li, run = x, 0
            else:
                run += 1
                if run > gap:
                    break
        ri = i
        run = 0
        for x in range(i, w):
            if row[x]:
                ri, run = x, 0
            else:
                run += 1
                if run > gap:
                    break
        left.append(int(li))
        right.append(int(ri))
    rows = [(y, lo, hi) for y, (lo, hi) in enumerate(zip(left, right))
            if lo is not None]
    top = rows[0][0] if rows else 0
    bottom = rows[-1][0] if rows else 0
    return {"schema_version": EXTRACT_SCHEMA, "path": path,
            "height": h, "width": w, "centerline_px": cx,
            "top_px": top, "bottom_px": bottom,
            "left": left, "right": right,
            "half_width": [None if lo is None else (hi - lo) / 2.0
                           for lo, hi in zip(left, right)],
            "mask_meta": meta}


def normalized_profile(prof: dict, n: int = 200) -> list[float]:
    """Half-width resampled to n points over the subject's own extent and
    scaled by the subject height — comparable across images and scales."""
    top, bottom = prof["top_px"], prof["bottom_px"]
    span = max(bottom - top, 1)
    hw = prof["half_width"]
    out = []
    for i in range(n):
        y = top + span * i / (n - 1)
        y0, y1 = int(np.floor(y)), min(int(np.ceil(y)), len(hw) - 1)
        a, b = hw[y0], hw[y1]
        if a is None and b is None:
            out.append(0.0)
        elif a is None or b is None:
            out.append(float(a if a is not None else b) / span)
        else:
            f = y - y0
            out.append(float(a * (1 - f) + b * f) / span)
    return out


def darkness_bands(path: str, prof: dict, *, quantile: float = 0.30) -> dict:
    """Rows whose subject pixels are markedly darker than the subject
    median — used to locate the dark closure component without assuming
    what that component IS."""
    rgb = _load(path)
    lum = rgb.mean(axis=2)
    vals, per_row = [], []
    for y, (lo, hi) in enumerate(zip(prof["left"], prof["right"])):
        if lo is None or hi <= lo:
            per_row.append(None)
            continue
        seg = lum[y, lo:hi + 1]
        per_row.append(float(seg.mean()))
        vals.append(float(seg.mean()))
    if not vals:
        return {"dark_rows": [], "threshold": None, "row_luminance": per_row}
    thr = float(np.quantile(np.array(vals), quantile))
    dark = [y for y, v in enumerate(per_row) if v is not None and v <= thr]
    return {"dark_rows": dark, "threshold": thr, "row_luminance": per_row,
            "dark_top": min(dark) if dark else None,
            "dark_bottom": max(dark) if dark else None}


def validate_against_reference(crop_profiles: dict, expected: dict,
                               tolerance_px: float = 12.0) -> dict:
    """The extractor's own acceptance test: reproduce the hand-read
    landmarks from the committed gridded crops. A metric from an
    unvalidated extractor self-certifies exactly like a formula does."""
    results, ok = {}, True
    for name, (measured, want) in expected.items():
        delta = abs(measured - want)
        passed = delta <= tolerance_px
        ok = ok and passed
        results[name] = {"measured_px": round(float(measured), 2),
                         "hand_read_px": float(want),
                         "delta_px": round(float(delta), 2),
                         "within_tolerance": passed}
    return {"schema_version": "visual_extractor_validation/1.0",
            "tolerance_px": tolerance_px, "checks": results,
            "extractor_validated": ok,
            "note": "half-width profiles are only trusted downstream when "
                    "this validation passes; it is re-run on every "
                    "inspection",
            "crops": sorted(crop_profiles)}
