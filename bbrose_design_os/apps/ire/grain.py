"""[His review of 127, 130, 131 and 132, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), C (5): "DETAIL AND TEXTURE: keep the
concept's detail: 131's sky grain and soft sun ... Nothing simplified to "hand-drawn flat"."]

A printed grain kept as vector. A flat redraw is traced clean (its texture would trace into thousands of shapes), so a
grain the concept's own print carries — where its design map reads one (``concept_design_map.TEXTURES``) — is drawn
over the traced art as a fine stipple: dots at the grain's own density, each in the concept's own colour where it stands,
a little lighter or darker by the grain's own measured strength. The dots are grouped by tone into a few compound paths,
opaque (no transparency the layered file would lose), every one vector.

- ``measure(png, boxes)`` — the grain where the read names it (``boxes``, the parts' shares of the picture): its
  strength (the picture's fine lightness noise over its smooth pixels, CIE L*) and its dots — ``{"amplitude", "density",
  "tones": {hex: [[x, y], ...]}}`` in shares of the picture, or None where there is none to keep.
- ``paths(record, x, y, w, h, prefix)`` — the dots drawn over a frame ``w`` x ``h`` mm at (x, y), one path a tone.

Every number below is the executor's, new with this module."""
from __future__ import annotations

#: the grain's measure: the picture's lightness less its blur at ``fine_px`` (the grain itself), read on the pixels
#: whose blur at ``smooth_px`` changes less than ``smooth_step`` L* a pixel (no edge, no line, no letter)
GRAIN = {"version": "grain/1.0", "fine_px": 1.2, "smooth_px": 5.0, "smooth_step": 0.5,
         # a grain under this strength (std of L*) is not kept; the strength the dots are drawn at is this share of it
         "min_amplitude": 1.2, "drawn_share": 1.6,
         # dots per square share of the frame at the grain's full density, and at most this many in all
         "dots_per_share": 9000, "max_dots": 6000,
         # a dot's side, in shares of the frame's width; the dots' order, fixed so a drawing is drawn alike again
         "dot_share": 0.0022, "seed": 11,
         # a line's or the mark's box, padded by this share of its height, holds no dot
         "words_pad": 0.5,
         # a dot's place lies within this (CIE76, the smooth picture) of its area's median colour — its ground's grain
         "ground_de": 18.0}


def _lab(img):
    import cv2
    import numpy as np
    return cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)


def measure(png: bytes, boxes: list, words: list | None = None) -> dict | None:
    """The grain the concept's print carries inside ``boxes`` (each [x0, y0, x1, y1], shares of the picture): its
    strength and its dots (module docstring); None where the boxes hold too little grain to keep."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None or not boxes:
        return None
    hgt, wid = img.shape[:2]
    lab = _lab(img)
    L = lab[..., 0] * (100.0 / 255.0)
    fine = L - cv2.GaussianBlur(L, (0, 0), GRAIN["fine_px"] * 2.0)
    soft = cv2.GaussianBlur(L, (0, 0), GRAIN["smooth_px"])
    gx = cv2.Sobel(soft, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(soft, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    smooth = np.sqrt(gx ** 2 + gy ** 2) < GRAIN["smooth_step"]
    inside = np.zeros((hgt, wid), bool)
    for b in boxes:
        x0, y0, x1, y1 = (float(v) for v in b)
        inside[max(0, int(y0 * hgt)):min(hgt, int(y1 * hgt) + 1), max(0, int(x0 * wid)):min(wid, int(x1 * wid) + 1)] = True
    # [his last goal before the pitch, Step 2, 139: "no duplicate or ghost text" — its grain's dots, each in the photo's
    # colour where it stands, drew its bold name again in brown dots] never a dot inside a line's or the mark's box
    # (``words``, padded by GRAIN["words_pad"] of its height): the grain is its ground's
    for b in words or []:
        x0, y0, x1, y1 = (float(v) for v in b)
        p = GRAIN["words_pad"] * (y1 - y0)
        inside[max(0, int((y0 - p) * hgt)):min(hgt, int((y1 + p) * hgt) + 1),
               max(0, int((x0 - p) * wid)):min(wid, int((x1 + p) * wid) + 1)] = False
    where = smooth & inside
    if where.sum() < 0.01 * hgt * wid:
        return None
    amplitude = float(fine[where].std())
    if amplitude < GRAIN["min_amplitude"]:
        return None
    # … nor on what is not its ground (a backdrop the picture shows beside the product, a motif's own colour): a dot
    # only where the smooth picture lies within GRAIN["ground_de"] of the textured area's own median
    soft_lab = cv2.GaussianBlur(lab, (0, 0), GRAIN["smooth_px"])
    median = np.median(soft_lab[where], axis=0)
    near = np.sqrt((((soft_lab - median) * np.array([100.0 / 255.0, 1.0, 1.0], np.float32)) ** 2).sum(-1))
    where = where & (near < GRAIN["ground_de"])
    if where.sum() < 0.01 * hgt * wid:
        return None
    rng = np.random.default_rng(GRAIN["seed"])
    area = float(inside.mean())
    density = min(1.0, amplitude / 6.0)
    n = int(min(GRAIN["max_dots"], GRAIN["dots_per_share"] * area * density))
    ys, xs = np.nonzero(where)
    if n <= 0 or not len(xs):
        return None
    pick = rng.integers(0, len(xs), n)
    base = cv2.GaussianBlur(lab, (0, 0), GRAIN["smooth_px"])
    tones: dict = {}
    for i, k in enumerate(pick):
        y, x = int(ys[k]), int(xs[k])
        l, a, b = (float(v) for v in base[y, x])
        step = GRAIN["drawn_share"] * amplitude * (255.0 / 100.0) * (1.0 if i % 2 else -1.0)
        px = np.array([[[min(255.0, max(0.0, l + step)), a, b]]], np.float32).astype(np.uint8)
        bgr = cv2.cvtColor(px, cv2.COLOR_LAB2BGR)[0, 0]
        # the dot's colour quantised a little, so dots of one tone share a path
        q = [int(round(c / 8.0) * 8) for c in bgr[::-1]]
        hx = "#%02X%02X%02X" % tuple(min(255, c) for c in q)
        tones.setdefault(hx, []).append([round(x / float(wid), 4), round(y / float(hgt), 4)])
    return {"version": GRAIN["version"], "amplitude": round(amplitude, 2), "density": round(density, 3),
            "dot_share": GRAIN["dot_share"], "tones": tones}


def paths(record: dict, x: float, y: float, w: float, h: float, prefix: str = "lid") -> list:
    """The grain's dots drawn over the frame at (x, y), ``w`` x ``h`` mm: one opaque compound path a tone, each dot a
    small square — named ``<prefix>-grain-<n>``."""
    from apps.ire.graph import ClosePath, Color, LineTo, MoveTo, Path, SolidFill
    side = float(record["dot_share"]) * w
    out = []
    for n, (hx, dots) in enumerate(sorted(record["tones"].items())):
        segs = []
        for fx, fy in dots:
            px, py = x + float(fx) * w, y + float(fy) * h
            segs += [MoveTo(x=px, y=py), LineTo(x=px + side, y=py), LineTo(x=px + side, y=py + side),
                     LineTo(x=px, y=py + side), ClosePath()]
        out.append(Path(name="%s-grain-%d" % (prefix, n), segments=segs, fill=SolidFill(color=Color.from_hex(hx))))
    return out
