"""[His go of 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md): "Trace line art and frames in ANY colour (not only gold): stems,
leaves, buds, outlines, thin frames, borders. Keep each motif in the picture's own colour." "Traced line art comes out
clean: smooth curves, even stroke widths, no wobble or specks (the clean-curves rule), each motif its own named layer."]

The design map's tracers for line art, frames and windows in any ink — beside its gold ones (``concept_design_map``:
``trace_scatter`` for small gold shapes, ``trace_rule`` for a gold rule), which knew no other colour. MEASURED on 122's
concepts: 147's "red line-art rose with stem and leaves", 148's "red line-art stems tendrils and buds" and "fine red
inner border frame", 149's "red hairline rose and leaf engraving all-over", "thin pink oval frame around window" and
"centred cleared elliptical window" — none could be drawn.

LINE ART (``trace_lines``): its ink the pixels of its box nearer the read's ink than their own ground — the ground a
median wider than any line, so a curved tube's shade is never ink — seeded where they stand LINE["strong_de"] apart and
grown through what stands LINE["weak_de"] apart, its one-pixel breaks closed and its specks dropped; the type, the mark,
a window and the closure kept out (a small line of type padded by its own height — a read's box can sit a line off its
letters); display lettering's own heavy strokes and their rims dropped, a thread through them kept. Thinned to its
centre lines, its spurs pruned, each stroke walked end to end (a ring kept closed), smoothed and simplified to the fewest
points that hold it — one width for the whole motif, measured at half its ink, and its colour the core of its ink.

FRAMES (``trace_frame``): an oval frame an ellipse fitted to the ink round its box's rim; any other a four-sided frame,
each side the outermost straight run of its ink near that side (its line is where the run lies; the corners where the
sides meet, leaning as the picture's perspective leans them). WINDOWS (``trace_window``): a cleared panel — the ellipse
inside the frame that rings it, or its box — filled with the surface it shows.

Pure: nothing written, nothing paid. The numbers in LINE are the executor's, new with this module, recorded on every
trace; no ruled number moves.
"""
from __future__ import annotations

LINE = {
    "version": "line_art_params/1.0",
    "strong_de": 12.0,         # a line's ink is seeded where it stands this far from its ground …
    "weak_de": 6.0,            # … and grown through what stands this far, connected to a seed
    "ground_share": 0.04,      # its ground: a median over this share of the product's width, wider than any line
    "speck_px": 8,             # an inked piece smaller than this many pixels, its breaks closed, is a speck
    "spur_widths": 2.0,        # a branch shorter than this many stroke widths off a junction is a spur
    "min_widths": 3.0,         # a stroke shorter than this many widths is dropped
    "smooth_widths": 1.5,      # each stroke smoothed along this many widths …
    "simplify_widths": 0.35,   # … and simplified to the points within this many widths of it
    "core_share": 0.3,         # its colour: the median of this share of its ink furthest from its ground
    "rim_share": 0.025,        # the product's own shaded rim, this share of its width, is never a motif's ink
    "avoid_pad": 0.012,        # a part kept out of a motif, padded by this share of the width
    "big_type": 0.05,          # a line of type this share of the product's height or taller is display lettering …
    "letter_half": 0.006,      # … its strokes at least twice this share of the width thick …
    "letter_de": 20.0,         # … its pixels within this of its own ink
    "frame_pad": 0.04,         # a frame's box read this share of its smaller side wider
    "frame_rim": 0.18,         # an oval frame's ink looked for within this share of its box's smaller side of its rim
    "frame_side": 0.35,        # a four-sided frame's side looked for within this share of its box from that side …
    "frame_run": 0.2,          # … its outermost straight run at least this share of the side …
    "frame_votes": 0.12,       # … found by this share of the side in votes …
    "frame_gap": 0.08,         # … across breaks of at most this share …
    "frame_lean_deg": 6.0,     # … leaning at most this far from square
}
#: a read's part named for a ring or an oval is drawn as an ellipse
OVAL_WORDS = ("oval", "ellip", "circle", "round", "ring")
#: the eight neighbours of a pixel, in order round it
_RING = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))


def oval_named(part: dict) -> bool:
    """The read names the part an oval, an ellipse, a circle, a ring."""
    return any(word in str(part.get("name")).lower() for word in OVAL_WORDS)


def _labs(bgr):
    import numpy as np

    from apps.pipeline.services.concept_design_map import _lab
    return np.stack(_lab(bgr), -1)


def _lab_of(hx):
    import numpy as np
    rgb = np.array([int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)], np.uint8).reshape(1, 1, 3)[..., ::-1]
    return _labs(np.ascontiguousarray(rgb))[0, 0]


def _width_px(far, ink_mask) -> float:
    """A line's one width in pixels, at half its ink: the centre line's distance to the edge of the pixels at least half
    as far from their ground as its core, twice over — anti-aliasing never thickens it."""
    import cv2
    import numpy as np
    core_far = float(np.percentile(far[ink_mask], 100.0 * (1.0 - LINE["core_share"])))
    half = ((far >= 0.5 * core_far) & ink_mask).astype(np.uint8)
    on_half = thin(ink_mask) & (half > 0)
    if not on_half.any():
        return 1.0
    return max(1.0, 2.0 * float(np.median(cv2.distanceTransform(half, cv2.DIST_L2, 3)[on_half])))


def _ink_of(lab, far, ink_mask):
    """``(hex, gold)``: the core of a line's ink — its pixels furthest from their ground — and whether it is gold."""
    import numpy as np

    from apps.pipeline.services.concept_design_map import SHAPE_PARAMS, _hex
    mine, dist = lab[ink_mask], far[ink_mask]
    core = np.median(mine[dist >= np.percentile(dist, 100.0 * (1.0 - LINE["core_share"]))], axis=0)
    gold = bool(core[2] > SHAPE_PARAMS["gold_b_min"] and core[2] > core[1] + SHAPE_PARAMS["gold_b_over_a"]
                and core[0] > SHAPE_PARAMS["gold_l_min"])
    return _hex(core), gold


def local_ground(bgr, w: float):
    """The picture's own ground at each pixel — a median over LINE["ground_share"] of the product's width."""
    import cv2
    k = max(9, int(LINE["ground_share"] * w)) | 1
    return _labs(cv2.medianBlur(bgr, k))


def grown_ink(strong, weak):
    """A line's ink: the faint pixels connected to a strong one, its one-pixel breaks closed, then its specks dropped."""
    import cv2
    import numpy as np
    _n, cc, _st, _c = cv2.connectedComponentsWithStats(weak.astype(np.uint8), 8)
    seeded = [i for i in np.unique(cc[strong]) if i > 0]
    ink = cv2.morphologyEx(np.isin(cc, seeded).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, cc, st, _c = cv2.connectedComponentsWithStats(ink, 8)
    return np.isin(cc, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= LINE["speck_px"]]).astype(np.uint8)


def thin(binary):
    """Zhang–Suen thinning: the ink's centre lines, one pixel wide."""
    import numpy as np
    img = np.pad(binary.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p2, p3, p4 = img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:]
            p5, p6, p7 = img[2:, 2:], img[2:, 1:-1], img[2:, :-2]
            p8, p9 = img[1:-1, :-2], img[:-2, :-2]
            centre = img[1:-1, 1:-1]
            around = [p2, p3, p4, p5, p6, p7, p8, p9]
            count = sum(n.astype(np.int32) for n in around)
            seq = around + [p2]
            turns = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.int32) for i in range(8))
            if step == 0:
                cond = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                cond = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            gone = (centre == 1) & (count >= 2) & (count <= 6) & (turns == 1) & cond
            if gone.any():
                centre[gone] = 0
                changed = True
        if not changed:
            return img[1:-1, 1:-1].astype(bool)


def strokes_of(skeleton, min_len: int, spur_len: int) -> list:
    """The centre lines' strokes, ``[(pixels in order, closed)]``: chains between its ends and its junctions (a pixel
    whose ring of neighbours crosses ink other than twice), a spur — an end's chain shorter than ``spur_len`` to a
    junction — dropped, a ring of ink with no end or junction kept closed; a chain shorter than ``min_len`` dropped."""
    import numpy as np
    on = {(int(y), int(x)) for y, x in zip(*np.nonzero(skeleton))}

    def nbrs(p):
        return [(p[0] + dy, p[1] + dx) for dy, dx in _RING if (p[0] + dy, p[1] + dx) in on]

    def crossings(p):
        ring = [(p[0] + dy, p[1] + dx) in on for dy, dx in _RING]
        return sum(1 for i in range(8) if not ring[i] and ring[(i + 1) % 8])
    nodes = {p for p in on if crossings(p) != 2 or len(nbrs(p)) == 1}
    used, walked = set(), []
    for start in nodes:
        for first in nbrs(start):
            if first in used and first not in nodes:
                continue
            chain, prev, cur = [start, first], start, first
            while cur not in nodes:
                used.add(cur)
                cand = [n for n in nbrs(cur) if n != prev and n not in used and n not in chain[-3:]]
                four = [n for n in cand if abs(n[0] - cur[0]) + abs(n[1] - cur[1]) == 1]
                nxt = four if four else cand
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                chain.append(cur)
            walked.append(chain)
    seen, out = set(), []
    for chain in walked:
        key = (min(chain[0], chain[-1]), max(chain[0], chain[-1]), len(chain))
        if key in seen:
            continue
        seen.add(key)
        spur = (len(nbrs(chain[0])) == 1) != (len(nbrs(chain[-1])) == 1) and len(chain) < spur_len
        if not spur and len(chain) >= min_len:
            out.append((chain, False))
    for p in sorted(on - used - nodes):
        if p in used:
            continue
        chain, prev, cur = [p], None, p
        used.add(p)
        while True:
            cand = [n for n in nbrs(cur) if n != prev and n not in used and n not in nodes]
            if not cand:
                break
            prev, cur = cur, cand[0]
            used.add(cur)
            chain.append(cur)
        closed = len(chain) > 2 and max(abs(chain[0][0] - chain[-1][0]), abs(chain[0][1] - chain[-1][1])) <= 1
        if len(chain) >= min_len:
            out.append((chain, closed))
    return out


def _smoothed(pts, win: float, closed: bool):
    """A stroke's points averaged along it over ``win`` points — its ends kept where it is open."""
    import numpy as np
    pts = np.asarray(pts, float)
    k = int(win) | 1
    if len(pts) < 3 or k < 3:
        return pts
    pad = k // 2
    if closed:
        ext = np.concatenate([pts[-pad:], pts, pts[:pad]])
    else:
        ext = np.concatenate([np.repeat(pts[:1], pad, 0), pts, np.repeat(pts[-1:], pad, 0)])
    out = np.stack([np.convolve(ext[:, i], np.ones(k) / k, mode="valid") for i in range(2)], -1)
    if not closed:
        out[0], out[-1] = pts[0], pts[-1]
    return out


def _simplified(pts, eps: float):
    """The fewest of a stroke's points within ``eps`` of it (Ramer–Douglas–Peucker)."""
    import numpy as np
    pts = np.asarray(pts, float)
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a
    n = float(np.hypot(*ab))
    if n > 0:
        d = np.abs(ab[0] * (pts[:, 1] - a[1]) - ab[1] * (pts[:, 0] - a[0])) / n
    else:
        d = np.hypot(pts[:, 0] - a[0], pts[:, 1] - a[1])
    i = int(np.argmax(d))
    if d[i] > eps:
        return np.concatenate([_simplified(pts[:i + 1], eps)[:-1], _simplified(pts[i:], eps)])
    return np.stack([a, b])


def _kept_out(shape, origin, pbox, avoid):
    """Where a motif's ink is never looked for: each part kept out (``{"box", "kind", "oval"}``) — a small line of type
    padded by its own height, a window by its ellipse where it is oval — and each traced frame's own line."""
    import cv2
    import numpy as np
    cx0, cy0 = origin
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    out = np.zeros(shape, np.uint8)
    pad = max(1, int(LINE["avoid_pad"] * w))
    for a in avoid:
        frame = a.get("frame")
        if frame:
            width = max(2, int(round(float(frame["width"]) * w * 3)))
            if frame["shape"] == "ellipse":
                cv2.ellipse(out, ((x0 + frame["centre"][0] * w - cx0, y0 + frame["centre"][1] * h - cy0),
                                  (frame["half"][0] * 2 * w, frame["half"][1] * 2 * h), frame["angle"]), 1, width)
            else:
                pts = np.array([[x0 + c[0] * w - cx0, y0 + c[1] * h - cy0] for c in frame["corners"]], np.int32)
                cv2.polylines(out, [pts], True, 1, width)
            continue
        bx0, by0, bx1, by1 = a["box"]
        px0, py0 = int(x0 + bx0 * w) - cx0, int(y0 + by0 * h) - cy0
        px1, py1 = int(x0 + bx1 * w) - cx0, int(y0 + by1 * h) - cy0
        if a.get("oval"):
            cv2.ellipse(out, (((px0 + px1) / 2.0, (py0 + py1) / 2.0), (px1 - px0 + 2 * pad, py1 - py0 + 2 * pad), 0.0),
                        1, -1)
            continue
        if a.get("kind") == "type" and (by1 - by0) >= LINE["big_type"]:
            continue                       # display lettering: its letters dropped by their weight, its threads kept
        vpad = max(pad, py1 - py0) if a.get("kind") == "type" else pad
        cv2.rectangle(out, (px0 - pad, py0 - vpad), (px1 + pad, py1 + vpad), 1, -1)
    return out > 0


def trace_lines(img, mask, pbox, part: dict, avoid: list) -> dict:
    """A motif of line art in any colour (module docstring), as strokes in the product's fractions: ``{"part", "ink",
    "gold", "width", "strokes": [{"points", "closed"}], "box"}``, or ``{"refused": why}``."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    bx0, by0, bx1, by1 = part["box"]
    cx0, cx1 = max(0, int(x0 + bx0 * w)), min(img.shape[1], int(x0 + bx1 * w) + 1)
    cy0, cy1 = max(0, int(y0 + by0 * h)), min(img.shape[0], int(y0 + by1 * h) + 1)
    if cx1 - cx0 < 3 or cy1 - cy0 < 3:
        return {"refused": "its box holds no picture"}
    crop = np.ascontiguousarray(img[cy0:cy1, cx0:cx1])
    lab = _labs(crop)
    rim = max(3, int(LINE["rim_share"] * w))
    inner = cv2.erode((mask > 0).astype(np.uint8), np.ones((2 * rim + 1, 2 * rim + 1), np.uint8))
    on = (inner[cy0:cy1, cx0:cx1] > 0) & ~_kept_out(lab.shape[:2], (cx0, cy0), pbox, avoid)
    if not on.any():
        return {"refused": "its box holds nothing of the product outside its other parts"}
    far = np.sqrt(((lab - local_ground(crop, w)) ** 2).sum(-1))
    nearer = on.copy()
    if part.get("colour"):
        nearer &= np.sqrt(((lab - _lab_of(part["colour"])) ** 2).sum(-1)) < far
    ink = grown_ink((far >= LINE["strong_de"]) & nearer, (far >= LINE["weak_de"]) & nearer) & on.astype(np.uint8)
    # display lettering in its box: its letters found by their own ink, opened to their heavy strokes, and dropped with
    # their rims (an embossed letter's edge reads as a line of its own) — a thread through them kept
    stroke = max(3, int(round(2 * LINE["letter_half"] * w)))
    letters = np.zeros(ink.shape, np.uint8)
    for a in avoid:
        if a.get("kind") != "type" or not a.get("colour") or (a["box"][3] - a["box"][1]) < LINE["big_type"]:
            continue
        r0, r1 = max(0, int(y0 + a["box"][1] * h) - cy0), max(0, int(y0 + a["box"][3] * h) - cy0 + 1)
        c0, c1 = max(0, int(x0 + a["box"][0] * w) - cx0), max(0, int(x0 + a["box"][2] * w) - cx0 + 1)
        # [His review of 127, 130, 131 and 132, 2026-10-15, C] a line of type wholly outside the motif's box is none of
        # its letters (132's lily above its CITRUS): its rows clipped to the box, never an empty slice
        r1, c1 = min(r1, ink.shape[0]), min(c1, ink.shape[1])
        if r1 <= r0 or c1 <= c0:
            continue
        own = (np.sqrt(((lab[r0:r1, c0:c1] - _lab_of(a["colour"])) ** 2).sum(-1)) < LINE["letter_de"]).astype(np.uint8)
        letters[r0:r1, c0:c1] |= cv2.morphologyEx(own, cv2.MORPH_OPEN, np.ones((stroke, stroke), np.uint8))
    if letters.any():
        ink[cv2.dilate(letters, np.ones((2 * stroke + 1,) * 2, np.uint8)) > 0] = 0
        ink = grown_ink(ink > 0, ink > 0)
    if not ink.any():
        return {"refused": "no line of its ink apart from its ground"}
    width_px = _width_px(far, ink > 0)
    chains = strokes_of(thin(ink > 0), max(3, int(LINE["min_widths"] * width_px)), int(LINE["spur_widths"] * width_px) + 1)
    if not chains:
        return {"refused": "no stroke of its ink long enough to draw"}
    strokes = []
    for chain, closed in chains:
        pts = _smoothed(np.array([(x, y) for y, x in chain], float), LINE["smooth_widths"] * width_px, closed)
        pts = _simplified(pts, max(0.5, LINE["simplify_widths"] * width_px))
        # a stroke shorter, as drawn, than min_widths of its width is a speck however many pixels it walked
        if float(np.hypot(*np.diff(pts, axis=0).T).sum()) < LINE["min_widths"] * width_px:
            continue
        strokes.append({"points": [[round(float((cx0 + px - x0) / w), 5), round(float((cy0 + py - y0) / h), 5)]
                                   for px, py in pts], "closed": bool(closed)})
    if not strokes:
        return {"refused": "no stroke of its ink long enough to draw"}
    ink_hex, gold = _ink_of(lab, far, ink > 0)
    pts = [p for s in strokes for p in s["points"]]
    return {"part": part.get("name"), "ink": ink_hex, "gold": gold, "width": round(width_px / w, 5),
            "strokes": strokes, "params": LINE["version"],
            "box": [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]}


def trace_frame(img, mask, pbox, part: dict, gold: bool = False) -> dict:
    """A thin frame or border round its box, in any colour (module docstring): an ellipse ``{"shape": "ellipse",
    "centre", "half", "angle"}`` or a four-sided frame ``{"shape": "quad", "corners"}``, with ``"ink"``, ``"gold"``,
    ``"width"``, ``"box"``; or ``{"refused": why}``. [His goal after the pitch page, 2026-10-15, A (4): "132's … gold
    double-rule frame was missing".] ``gold`` — the frame the read names gold, read in the picture's gold alone: 132's
    cartouche frame, its blue tiles' straight runs lying further out than it."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    bx0, by0, bx1, by1 = part["box"]
    bw, bh = (bx1 - bx0) * w, (by1 - by0) * h
    pad = LINE["frame_pad"] * min(bw, bh)
    cx0, cx1 = max(0, int(x0 + bx0 * w - pad)), min(img.shape[1], int(x0 + bx1 * w + pad) + 1)
    cy0, cy1 = max(0, int(y0 + by0 * h - pad)), min(img.shape[0], int(y0 + by1 * h + pad) + 1)
    if cx1 - cx0 < 8 or cy1 - cy0 < 8:
        return {"refused": "its box is too small to hold a frame"}
    crop = np.ascontiguousarray(img[cy0:cy1, cx0:cx1])
    lab = _labs(crop)
    on = mask[cy0:cy1, cx0:cx1] > 0
    far = np.sqrt(((lab - local_ground(crop, w)) ** 2).sum(-1))
    near = on & (far >= LINE["weak_de"])
    if part.get("colour"):
        near &= np.sqrt(((lab - _lab_of(part["colour"])) ** 2).sum(-1)) < far
    if gold:
        from apps.pipeline.services.concept_design_map import _gold
        near &= _gold(crop)
    # a frame's line can be fainter than a motif's (148's foot): its sides are searched in all its faint ink — a straight
    # run, or the ring of an oval, is what makes it a frame's, not its strength
    full = cv2.morphologyEx(near.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    H, W = full.shape
    if oval_named(part):
        yy, xx = np.mgrid[0:H, 0:W]
        rr = np.hypot((xx - (W - 1) / 2.0) / (bw / 2.0 + pad), (yy - (H - 1) / 2.0) / (bh / 2.0 + pad))
        ring = (full > 0) & (rr > 1.0 - 1.5 * LINE["frame_rim"]) & (rr < 1.08)
        ys, xs = np.nonzero(ring)
        if len(xs) < 20:
            return {"refused": "no ink of an oval frame round its box"}
        (ex, ey), (ea, eb), angle = cv2.fitEllipse(np.stack([xs, ys], -1).astype(np.float32))
        width_px = _width_px(far, ring)
        ink_hex, gold = _ink_of(lab, far, ring)
        return {"part": part.get("name"), "shape": "ellipse", "ink": ink_hex, "gold": gold,
                "width": round(width_px / w, 5), "params": LINE["version"],
                "centre": [round((cx0 + ex - x0) / w, 5), round((cy0 + ey - y0) / h, 5)],
                "half": [round(ea / 2.0 / w, 5), round(eb / 2.0 / h, 5)], "angle": round(float(angle), 2),
                "box": [round((cx0 + ex - ea / 2.0 - x0) / w, 5), round((cy0 + ey - eb / 2.0 - y0) / h, 5),
                        round((cx0 + ex + ea / 2.0 - x0) / w, 5), round((cy0 + ey + eb / 2.0 - y0) / h, 5)]}
    sides = {}
    for side, horizontal, keep in (("top", True, (slice(0, int(LINE["frame_side"] * H)), slice(None))),
                                   ("foot", True, (slice(H - int(LINE["frame_side"] * H), H), slice(None))),
                                   ("left", False, (slice(None), slice(0, int(LINE["frame_side"] * W)))),
                                   ("right", False, (slice(None), slice(W - int(LINE["frame_side"] * W), W)))):
        band = np.zeros_like(full)
        band[keep] = full[keep]
        span = W if horizontal else H
        segs = cv2.HoughLinesP(band * 255, 1, np.pi / 720, threshold=max(8, int(LINE["frame_votes"] * span)),
                               minLineLength=int(LINE["frame_run"] * span), maxLineGap=int(LINE["frame_gap"] * span))
        best = None
        for sx0, sy0, sx1, sy1 in (segs.reshape(-1, 4) if segs is not None else []):
            angle = abs(float(np.degrees(np.arctan2(sy1 - sy0, sx1 - sx0)))) % 180.0
            lean = min(angle, 180.0 - angle) if horizontal else abs(90.0 - angle)
            if lean > LINE["frame_lean_deg"]:
                continue
            # the outermost straight run along the side: a frame lies outside what it frames
            out_by = {"top": -min(sy0, sy1), "foot": max(sy0, sy1), "left": -min(sx0, sx1), "right": max(sx0, sx1)}[side]
            if best is None or out_by > best[0]:
                best = (out_by, (float(sx0), float(sy0)), (float(sx1), float(sy1)))
        if best is None:
            return {"refused": "no straight run of ink along its %s side" % side}
        sides[side] = best[1:]

    def meet(a, b):
        (p1, p2), (p3, p4) = a, b
        d = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
        t = ((p1[0] - p3[0]) * (p3[1] - p4[1]) - (p1[1] - p3[1]) * (p3[0] - p4[0])) / d
        return p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])
    corners = [meet(sides["top"], sides["left"]), meet(sides["top"], sides["right"]),
               meet(sides["foot"], sides["right"]), meet(sides["foot"], sides["left"])]
    # its width and its ink read along its four sides
    line = np.zeros_like(full)
    cv2.polylines(line, [np.array(corners, np.int32)], True, 1, 5)
    on_line = (line > 0) & (full > 0)
    if not on_line.any():
        return {"refused": "no ink along the frame its sides make"}
    width_px = _width_px(far, on_line)
    ink_hex, gold = _ink_of(lab, far, on_line)
    frac = [[round((cx0 + cx - x0) / w, 5), round((cy0 + cy - y0) / h, 5)] for cx, cy in corners]
    return {"part": part.get("name"), "shape": "quad", "ink": ink_hex, "gold": gold, "width": round(width_px / w, 5),
            "corners": frac, "params": LINE["version"],
            "box": [min(c[0] for c in frac), min(c[1] for c in frac), max(c[0] for c in frac), max(c[1] for c in frac)]}


#: [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (7): "Arches, frames, ovals, borders and rules are rebuilt as
#: clean geometric curves (symmetric where the concept is), with an even stroke, matched to the concept's shape"; (8): "Glow
#: is a real soft blur"; (9): "Gradients are smooth, never flat bands".] A window read further than its box: its arch from
#: its own rim — a thin, long gold line across ``arch_share`` of its width and more, folded on its own axis
#: (``line_geometry.arch_of``); its field on a ``field_grid`` (rows x columns) of its plain pixels (each within
#: ``plain_de`` of a ``plain_px`` median round it, its type and motifs left out), kept where its cells stand ``field_de``
#: apart or more; its rim's glow band by band out from the rim (shares of the product's width), each ``glow_de`` from the
#: ground beyond (``glow_far``) or more
WINDOW = {"version": "window_shape/1.0", "pad": 0.06, "arch_share": 0.6, "field_grid": (16, 12), "field_de": 4.0,
          "plain_de": 6.0, "plain_px": 31, "field_fits": 3, "field_off_de": 4.0, "field_off_mad": 2.5, "glow_bands": (0.003, 0.006, 0.009, 0.013, 0.018, 0.024),
          "glow_far": (0.03, 0.045), "glow_de": 5.0, "points": 64}


def _window_crop(img, pbox, box):
    """The window's box, padded by WINDOW["pad"], in the picture's pixels: ``(x0, y0, x1, y1)``."""
    x0, y0, x1, y1 = pbox
    w, h, pad = x1 - x0, y1 - y0, WINDOW["pad"]
    return (max(0, int(x0 + (box[0] - pad) * w)), max(0, int(y0 + (box[1] - pad) * h)),
            min(img.shape[1], int(x0 + (box[2] + pad) * w) + 1), min(img.shape[0], int(y0 + (box[3] + pad) * h) + 1))


def window_arch(img, mask, pbox, part: dict) -> dict | None:
    """``{"points": [[x, y]] (shares of the product, left foot to apex to right foot), "width", "ink", "gold", "axis",
    "mirror", "fit_px"}`` — the arch a window's gold rim draws; None where its rim is no arch."""
    import cv2
    import numpy as np

    from apps.pipeline.services import line_geometry as LG
    from apps.pipeline.services.concept_design_map import _gold, _hex
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    cx0, cy0, cx1, cy1 = _window_crop(img, pbox, part["box"])
    crop = np.ascontiguousarray(img[cy0:cy1, cx0:cx1])
    gold = (_gold(crop) & (mask[cy0:cy1, cx0:cx1] > 0)).astype(np.uint8)
    n, lab, stats, _c = cv2.connectedComponentsWithStats(
        cv2.morphologyEx(gold, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))), 8)
    if n < 2:
        return None
    c = max(range(1, n), key=lambda k: int(stats[k][2]) * int(stats[k][3]))
    sx, sy, sw, sh, area = (int(v) for v in stats[c])
    if sw < WINDOW["arch_share"] * (part["box"][2] - part["box"][0]) * w or area > LG.GEOMETRY["fill"] * sw * sh:
        return None                    # not across the window, or a mass of gold — never its rim
    band = (lab == c).astype(np.uint8)
    got = LG.arch_of(band, band.shape[1], band.shape[0], (sx, sy, sw, sh))
    if got is None or got[3] > LG.GEOMETRY["fit_px"]:
        return None
    line, axis, mirror, fit = got
    dist = cv2.distanceTransform(band, cv2.DIST_L2, 5)
    width = 2.0 * float(np.median(dist[dist > 0]))
    ink = _hex(np.median(_labs(crop)[(band > 0) & (gold > 0)], axis=0))
    step = max(1, len(line) // WINDOW["points"])
    pts = line[::step].tolist() + ([line[-1].tolist()] if (len(line) - 1) % step else [])
    return {"points": [[round((cx0 + px - x0) / w, 5), round((cy0 + py - y0) / h, 5)] for px, py in pts],
            "width": round(width / w, 5), "ink": ink, "gold": True, "axis": round((cx0 + axis - x0) / w, 5),
            "mirror": round(mirror, 3), "fit_px": round(fit, 2)}


def window_field(img, mask, pbox, region) -> dict | None:
    """``{"rows": [[hex] * columns] * rows, "box": [x0, y0, x1, y1] (shares of the product)}`` — the colour field inside
    ``region`` (a bool mask over the picture), read on WINDOW["field_grid"] from its plain pixels, each cell its
    median, a cell its type or motifs cover filled from its neighbours; None where it is one colour."""
    import cv2
    import numpy as np

    from apps.pipeline.services.concept_design_map import _hex
    ys, xs = np.nonzero(region)
    if len(xs) < 50:
        return None
    rx0, ry0, rx1, ry1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    crop = np.ascontiguousarray(img[ry0:ry1, rx0:rx1])
    inside = region[ry0:ry1, rx0:rx1] & (mask[ry0:ry1, rx0:rx1] > 0)
    lab = _labs(crop)
    plain = inside & (np.linalg.norm(lab - _labs(cv2.medianBlur(crop, WINDOW["plain_px"])), axis=2) < WINDOW["plain_de"])
    gh, gw = WINDOW["field_grid"]
    H, W = inside.shape
    cells = np.full((gh, gw, 3), np.nan, np.float32)
    for i in range(gh):
        for j in range(gw):
            m = plain[i * H // gh:(i + 1) * H // gh, j * W // gw:(j + 1) * W // gw]
            if m.sum() >= 4:
                cells[i, j] = np.median(lab[i * H // gh:(i + 1) * H // gh, j * W // gw:(j + 1) * W // gw][m], axis=0)
    held = ~np.isnan(cells[..., 0])
    if held.sum() < 6:
        return None
    # a window's field is a smooth gradient: a quadratic surface in its box, per channel, fitted to its cells — a cell a
    # leaf, a petal or a line of type crosses (far from the surface) dropped and the fit made again — read back at every
    # cell, so nothing drawn on the field is ever painted into it
    yy, xx = np.mgrid[0:gh, 0:gw]
    u, v = (xx + 0.5) / gw - 0.5, (yy + 0.5) / gh - 0.5
    terms = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], -1).reshape(-1, 6)
    seen = held.reshape(-1)
    values = np.nan_to_num(cells.reshape(-1, 3))
    keep = seen.copy()
    for _round in range(WINDOW["field_fits"]):
        coef = np.linalg.lstsq(terms[keep], values[keep], rcond=None)[0]
        off = np.linalg.norm(values - terms @ coef, axis=1)
        keep = seen & (off < max(WINDOW["field_off_de"], WINDOW["field_off_mad"] * float(np.median(off[keep]))))
    cells = (terms @ coef).reshape(gh, gw, 3)
    flat = cells.reshape(-1, 3)
    if float(np.linalg.norm(flat.max(axis=0) - flat.min(axis=0))) < WINDOW["field_de"]:
        return None
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    return {"rows": [[_hex(cells[i, j]) for j in range(gw)] for i in range(gh)],
            "box": [round((rx0 - x0) / w, 5), round((ry0 - y0) / h, 5), round((rx1 - x0) / w, 5),
                    round((ry1 - y0) / h, 5)]}


def rim_glow(img, mask, pbox, rim: dict, region) -> dict | None:
    """``{"bands": [{"to": a share of the product's width, "hex", "de"}]}`` — the glow outside a window's rim, band by
    band out from it, as the picture prints it; None where none stands from the ground beyond."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    line = np.zeros(region.shape, np.uint8)
    pts = np.int32([[x0 + px * w, y0 + py * h] for px, py in rim["points"]])
    cv2.polylines(line, [pts], False, 1, max(1, int(round(rim["width"] * w))))
    dist = cv2.distanceTransform((1 - line).astype(np.uint8), cv2.DIST_L2, 5)
    outside = ~region & (mask > 0)
    lab = _labs(img)
    far = outside & (dist > WINDOW["glow_far"][0] * w) & (dist < WINDOW["glow_far"][1] * w)
    if far.sum() < 20:
        return None
    ground = np.median(lab[far], axis=0)
    bands, inner = [], 0.5 * rim["width"] * w
    for outer in WINDOW["glow_bands"]:
        band = outside & (dist >= inner) & (dist < outer * w)
        inner = outer * w
        if band.sum() < 10:
            continue
        de = float(np.linalg.norm(np.median(lab[band], axis=0) - ground))
        if de < WINDOW["glow_de"]:
            break
        px = np.median(img[band], axis=0)
        bands.append({"to": outer, "hex": "#%02X%02X%02X" % (int(px[2]), int(px[1]), int(px[0])), "de": round(de, 1)})
    if not bands:
        return None
    from apps.pipeline.services.concept_design_map import _hex
    return {"bands": bands, "ground": _hex(ground)}


def trace_window(img, mask, pbox, part: dict, frames: list) -> dict:
    """A cleared window (module docstring): inside the oval frame that rings its box (its ring's inner edge), else an
    ellipse in its box where the read names it oval, else its box — ``{"part", "shape", ..., "fill", "box"}``, its fill
    the surface it shows (its pixels near their own median, the lines on it left out); or ``{"refused": why}``."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = pbox
    w, h = x1 - x0, y1 - y0
    bx0, by0, bx1, by1 = part["box"]
    ring = next((f for f in frames if f.get("shape") == "ellipse"
                 and bx0 <= f["centre"][0] <= bx1 and by0 <= f["centre"][1] <= by1), None)
    # [his goal after the pitch page, 2026-10-15, A (4)] a four-sided frame round it (132's gold cartouche frame, read
    # just outside the box the read gave the window): the window is what the frame holds, out to the frame's own line
    # (drawn over it) — never its box inside it with the pattern round it showing between the two
    quad = next((f for f in frames if f.get("shape") == "quad" and f.get("window") == part.get("name")), None)
    region = np.zeros(mask.shape, np.uint8)
    if quad is not None and ring is None:
        shape = {"shape": "quad", "corners": [[float(c[0]), float(c[1])] for c in quad["corners"]]}
        bx0, by0 = min(c[0] for c in shape["corners"]), min(c[1] for c in shape["corners"])
        bx1, by1 = max(c[0] for c in shape["corners"]), max(c[1] for c in shape["corners"])
    elif ring is not None:
        inset = float(ring["width"])
        shape = {"shape": "ellipse", "centre": list(ring["centre"]), "angle": ring["angle"],
                 "half": [round(max(0.0, ring["half"][0] - inset), 5),
                          round(max(0.0, ring["half"][1] - inset * w / h), 5)]}
    elif oval_named(part):
        shape = {"shape": "ellipse", "centre": [round((bx0 + bx1) / 2.0, 5), round((by0 + by1) / 2.0, 5)],
                 "half": [round((bx1 - bx0) / 2.0, 5), round((by1 - by0) / 2.0, 5)], "angle": 0.0}
    else:
        shape = {"shape": "quad", "corners": [[bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1]]}
    if shape["shape"] == "ellipse":
        cv2.ellipse(region, ((x0 + shape["centre"][0] * w, y0 + shape["centre"][1] * h),
                             (shape["half"][0] * 2 * w, shape["half"][1] * 2 * h), shape["angle"]), 1, -1)
    else:
        cv2.fillPoly(region, [np.array([[x0 + c[0] * w, y0 + c[1] * h] for c in shape["corners"]], np.int32)], 1)
    inside = (region > 0) & (mask > 0)
    if int(inside.sum()) < 20:
        return {"refused": "its window holds nothing of the product"}
    lab = _labs(np.ascontiguousarray(img))[inside]
    middle = np.median(lab, axis=0)
    plain = lab[np.sqrt(((lab - middle) ** 2).sum(-1)) < LINE["weak_de"]]
    from apps.pipeline.services.concept_design_map import _hex
    fill = _hex(np.median(plain, axis=0) if len(plain) else middle)
    if shape["shape"] == "ellipse":
        cx, cy = shape["centre"]
        hx, hy = shape["half"]
        box = [round(cx - hx, 5), round(cy - hy, 5), round(cx + hx, 5), round(cy + hy, 5)]
    else:
        box = [bx0, by0, bx1, by1]
    out = {"part": part.get("name"), **shape, "fill": fill, "box": box, "params": LINE["version"]}
    # [his goal of 2026-10-13, (7)] a window under an arch its gold rim draws: the arch's own shape, its rim one line
    rim = window_arch(img, mask, pbox, part) if ring is None and quad is None else None   # a frame is its rim
    if rim is not None:
        region = np.zeros(mask.shape, np.uint8)
        cv2.fillPoly(region, [np.int32([[x0 + px * w, y0 + py * h] for px, py in rim["points"]])], 1)
        out = dict(out, shape="arch", points=rim["points"], rim=rim,
                   box=[round(min(p[0] for p in rim["points"]), 5), round(min(p[1] for p in rim["points"]), 5),
                        round(max(p[0] for p in rim["points"]), 5), round(max(p[1] for p in rim["points"]), 5)])
        out.pop("corners", None)
        glow = rim_glow(img, mask, pbox, rim, region > 0)
        if glow is not None:
            out["glow"] = glow
    else:
        region = np.zeros(mask.shape, np.uint8)
        if out["shape"] == "ellipse":
            cv2.ellipse(region, ((x0 + out["centre"][0] * w, y0 + out["centre"][1] * h),
                                 (out["half"][0] * 2 * w, out["half"][1] * 2 * h), out["angle"]), 1, -1)
        else:
            cv2.fillPoly(region, [np.array([[x0 + c[0] * w, y0 + c[1] * h] for c in out["corners"]], np.int32)], 1)
    # [his goal of 2026-10-13, (9)] its field where it is not one colour — drawn as a smooth mesh
    field = window_field(img, mask, pbox, region > 0)
    if field is not None:
        out["field"] = field
    return out
