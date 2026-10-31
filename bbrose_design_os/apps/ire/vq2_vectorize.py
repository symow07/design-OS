"""Deterministic raster → vector reconstruction for VQ-2-CORR-1.

HONEST LABELLING, read this first
---------------------------------
This module performs **automated contour extraction and Bézier fitting**. It
is NOT a designer manually redrawing a mark in Illustrator, and nothing it
produces may be described as a *manual* reconstruction.

It is also not Adobe Image Trace, and differs from it in ways that are
measured rather than asserted: contours are extracted per visible component
so every glyph is a separate editable object, corners are detected and
preserved, and node counts are controlled and reported. Image Trace's
characteristic failure — one flattened blob carrying thousands of
uncontrolled nodes — is therefore checkable here, not merely disclaimed.

Whether that is good enough to stand as the approved brand mark is a human
decision. This module only produces the geometry and the evidence.
"""
from __future__ import annotations

import math

METHOD = "DETERMINISTIC_CONTOUR_EXTRACTION_AND_BEZIER_FIT"
NOT_MANUAL = ("AUTOMATED_VECTORIZATION_NOT_A_MANUAL_REDRAW")
NOT_IMAGE_TRACE_EVIDENCE = (
    "per-component decomposition, corner-preserving fit and a reported node "
    "budget — all three are measured, not claimed")

#: a reconstruction carrying more nodes than this per glyph has degenerated
#: into a trace and must not be presented as clean vector artwork
MAX_NODES_PER_COMPONENT = 160


# --- mask handling --------------------------------------------------------------

def alpha_mask(path: str, *, threshold: int = 128, upsample: int = 4):
    """Binary ink mask from a raster, upsampled first so the extracted
    contour is smoother than the source pixel grid."""
    import numpy as np
    from PIL import Image
    im = Image.open(path)
    if im.mode == "RGBA":
        chan = im.split()[3]
    else:
        chan = im.convert("L").point(lambda v: 255 - v)
    if upsample > 1:
        chan = chan.resize((chan.width * upsample, chan.height * upsample),
                           Image.LANCZOS)
    return (np.asarray(chan) > threshold), upsample


def luminance_mask(arr, box, *, threshold: float, upsample: int = 4):
    """Ink mask for a crop of an existing RGB array (the concept render)."""
    import numpy as np
    from PIL import Image
    x0, y0, x1, y1 = box
    sub = arr[y0:y1, x0:x1].mean(axis=2)
    img = Image.fromarray(np.clip(255 - sub, 0, 255).astype("uint8"))
    if upsample > 1:
        img = img.resize((img.width * upsample, img.height * upsample),
                         Image.LANCZOS)
    return (np.asarray(img) > (255 - threshold)), upsample


def components(mask, *, min_pixels: int = 40) -> list:
    """Connected ink components (4-connectivity), largest first.

    Each component becomes one independently editable object, which is what
    keeps a wordmark from collapsing into a single flattened path.
    """
    import numpy as np
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for sy in range(h):
        xs = np.where(mask[sy] & ~seen[sy])[0]
        for sx in xs:
            if seen[sy, sx]:
                continue
            stack, pix = [(sy, sx)], []
            seen[sy, sx] = True
            while stack:
                y, x = stack.pop()
                pix.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] \
                            and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if len(pix) >= min_pixels:
                ys = [p[0] for p in pix]
                xs2 = [p[1] for p in pix]
                out.append({"pixels": len(pix),
                            "bbox": (min(xs2), min(ys), max(xs2), max(ys)),
                            "mask_indices": pix})
    out.sort(key=lambda c: c["bbox"][0])
    return out


# --- contour tracing -------------------------------------------------------------

def trace_contours(mask) -> list:
    """Closed boundary polylines via Moore-neighbour tracing.

    Returns outer and inner (counter) contours, so bowls and counters survive
    rather than being filled in.
    """
    import numpy as np
    h, w = mask.shape
    P = 2                                    # pad so neighbour tests stay safe
    padded = np.zeros((h + 2 * P, w + 2 * P), dtype=bool)
    padded[P:-P, P:-P] = mask
    visited = set()
    contours = []
    nbrs = [(-1, 0), (-1, 1), (0, 1), (1, 1),
            (1, 0), (1, -1), (0, -1), (-1, -1)]

    def is_boundary(y, x):
        if not padded[y, x]:
            return False
        return not (padded[y + 1, x] and padded[y - 1, x]
                    and padded[y, x + 1] and padded[y, x - 1])

    # Tracing only INK boundaries is sufficient: a counter is enclosed by ink
    # pixels that are themselves adjacent to background, so bowls and counters
    # come out as their own loops without a separate background sweep.
    for y in range(P, h + P):
        row = np.where(padded[y])[0]
        for x in row:
            if (y, x) in visited or not is_boundary(y, x):
                continue
            start, cur, prev_dir = (y, x), (y, x), 0
            path = []
            for _ in range(400000):
                path.append(cur)
                visited.add(cur)
                found = False
                for k in range(8):
                    d = (prev_dir + 6 + k) % 8
                    dy, dx = nbrs[d]
                    ny, nx = cur[0] + dy, cur[1] + dx
                    if not is_boundary(ny, nx):
                        continue
                    # returning to the start CLOSES the loop; every other
                    # candidate must be unvisited
                    if (ny, nx) == start and len(path) > 2:
                        cur, found = start, True
                        break
                    if (ny, nx) not in visited:
                        cur, prev_dir, found = (ny, nx), d, True
                        break
                if not found or cur == start:
                    break
            if len(path) >= 12:
                contours.append([(p[1] - P, p[0] - P) for p in path])
    return [c for c in contours if len(c) >= 12]


def rdp(points: list, eps: float) -> list:
    """Ramer-Douglas-Peucker simplification — the node-budget control."""
    if len(points) < 3:
        return list(points)
    a, b = points[0], points[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    den = math.hypot(dx, dy)
    worst, idx = -1.0, 0
    for i in range(1, len(points) - 1):
        p = points[i]
        d = (abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / den
             if den > 1e-9 else math.hypot(p[0] - a[0], p[1] - a[1]))
        if d > worst:
            worst, idx = d, i
    if worst <= eps:
        return [a, b]
    return rdp(points[:idx + 1], eps)[:-1] + rdp(points[idx:], eps)


def corners(points: list, *, angle_deg: float = 48.0) -> set:
    """Indices where the contour turns sharply — serif tips and stem
    junctions that must stay crisp rather than be rounded into curves."""
    out = set()
    n = len(points)
    for i in range(n):
        a, b, c = points[(i - 1) % n], points[i], points[(i + 1) % n]
        v1 = (b[0] - a[0], b[1] - a[1])
        v2 = (c[0] - b[0], c[1] - b[1])
        m1, m2 = math.hypot(*v1), math.hypot(*v2)
        if m1 < 1e-9 or m2 < 1e-9:
            continue
        cosang = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (m1 * m2)))
        if math.degrees(math.acos(cosang)) >= angle_deg:
            out.add(i)
    return out


def fit_closed(points: list, *, corner_idx: set, tol: float) -> list:
    """Cubic Béziers between corners; straight runs stay straight."""
    n = len(points)
    if n < 4:
        return [("L", p) for p in points]
    # A smooth closed contour (a bowl or a counter) has NO sharp corners, so
    # corner breaks alone would collapse it to a single degenerate run.
    # Always subdivide as well, so every run stays short enough to fit.
    breaks = set(corner_idx)
    step = max(2, min(6, n // 4))
    breaks.update(range(0, n, step))
    breaks = sorted(breaks)
    segs, out = [], []
    for i, b in enumerate(breaks):
        nb = breaks[(i + 1) % len(breaks)]
        run = []
        j = b
        while True:
            run.append(points[j % n])
            if j % n == nb % n and len(run) > 1:
                break
            j += 1
            if len(run) > n:
                break
        segs.append(run)
    for run in segs:
        if len(run) <= 2:
            out.append(("L", run[-1]))
            continue
        p0, p3 = run[0], run[-1]
        t1 = run[min(1, len(run) - 1)]
        t2 = run[max(len(run) - 2, 0)]
        c1 = (p0[0] + (t1[0] - p0[0]) * 1.35, p0[1] + (t1[1] - p0[1]) * 1.35)
        c2 = (p3[0] + (t2[0] - p3[0]) * 1.35, p3[1] + (t2[1] - p3[1]) * 1.35)
        # straight run? keep it a line
        dev = 0.0
        ax, ay = p3[0] - p0[0], p3[1] - p0[1]
        den = math.hypot(ax, ay)
        if den > 1e-9:
            for p in run[1:-1]:
                dev = max(dev, abs(ay * p[0] - ax * p[1]
                                   + p3[0] * p0[1] - p3[1] * p0[0]) / den)
        if dev <= tol:
            out.append(("L", p3))
        else:
            out.append(("C", (c1, c2, p3)))
    return out


def vectorize_component(mask, *, rdp_eps: float, fit_tol: float,
                        angle_deg: float = 48.0) -> dict:
    """One component → closed contours as controlled Bézier runs."""
    raw = trace_contours(mask)
    paths, nodes = [], 0
    for c in raw:
        simple = rdp(c, rdp_eps)
        if len(simple) < 4:
            continue
        cs = corners(simple, angle_deg=angle_deg)
        segs = fit_closed(simple, corner_idx=cs, tol=fit_tol)
        nodes += len(segs)
        paths.append({"start": simple[0], "segments": segs,
                      "raw_points": len(c), "simplified_points": len(simple),
                      "corners": len(cs)})
    return {"contours": paths, "node_count": nodes,
            "contour_count": len(paths), "method": METHOD}


# --- fidelity measurement --------------------------------------------------------

def rasterize_paths(paths: list, size: tuple, *, scale: float = 1.0,
                    offset: tuple = (0.0, 0.0)):
    """Fill the reconstructed contours so they can be compared with the
    source mask. Even-odd fill so counters stay open."""
    from PIL import Image, ImageDraw
    w, h = size
    img = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(img)
    polys = []
    for p in paths:
        pts, cur = [], p["start"]
        pts.append(cur)
        for op, payload in p["segments"]:
            if op == "L":
                cur = payload
                pts.append(cur)
            else:
                c1, c2, p3 = payload
                for i in range(1, 13):
                    t = i / 12.0
                    u = 1 - t
                    pts.append((
                        u ** 3 * cur[0] + 3 * u * u * t * c1[0]
                        + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
                        u ** 3 * cur[1] + 3 * u * u * t * c1[1]
                        + 3 * u * t * t * c2[1] + t ** 3 * p3[1]))
                cur = p3
        polys.append([((x + offset[0]) * scale, (y + offset[1]) * scale)
                      for x, y in pts])
    for poly in polys:
        if len(poly) >= 3:
            d.polygon(poly, fill=1)
    # counters: re-punch smaller contours
    order = sorted(range(len(polys)),
                   key=lambda i: -_area(polys[i]))
    for i in order[1:]:
        if len(polys[i]) >= 3 and _area(polys[i]) < _area(polys[order[0]]) * 0.9:
            d.polygon(polys[i], fill=0)
    return img


def _area(poly) -> float:
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def iou(mask_a, mask_b) -> float:
    import numpy as np
    a = np.asarray(mask_a, dtype=bool)
    b = np.asarray(mask_b, dtype=bool)
    if a.shape != b.shape:
        return 0.0
    inter = (a & b).sum()
    union = (a | b).sum()
    return float(inter) / float(union) if union else 0.0


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("vectorization source raster is display-encoded; the contour source is the artifact")
