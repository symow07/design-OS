"""VQ-2 direct Didone lettering construction — vq2_direct_didone_lettering/1.0.

Glyph outlines are AUTHORED HERE, in final document coordinates, from
construction primitives: stems, bowls, arches, hairline serifs and ball
terminals. No font outline is ever imported, nothing is traced, and no glyph
is scaled after construction — condensed proportions are a design parameter,
not a transform.

This is PROCEDURAL authorship. It is not a manual redraw and must never be
described as one.
"""
from __future__ import annotations

import math

SCHEMA = "vq2_direct_didone_lettering/1.0"
AUTHORING = "PROCEDURALLY_AUTHORED_CONDENSED_LETTERING"
NOT_MANUAL = "NOT_MANUALLY_REDRAWN_NOT_HUMAN_COMMISSIONED"

K = 0.5522847498307936          # circle→cubic constant


class Params:
    """The construction system. Every value is in FINAL document units."""

    def __init__(self, cap, *, xh_ratio=0.655, contrast=7.0, stem_ratio=0.185,
                 serif_len_ratio=0.115, serif_th_ratio=0.030,
                 overshoot_ratio=0.012):
        self.cap = cap
        self.xh = cap * xh_ratio
        self.stem = cap * stem_ratio          # thick vertical
        self.hair = self.stem / contrast      # hairline horizontal
        self.serif_len = cap * serif_len_ratio
        self.serif_th = max(cap * serif_th_ratio, self.hair * 0.9)
        self.over = cap * overshoot_ratio
        self.contrast = contrast

    def as_dict(self):
        return {"cap_height": round(self.cap, 4), "x_height": round(self.xh, 4),
                "stem_width": round(self.stem, 4),
                "hairline_width": round(self.hair, 4),
                "stroke_contrast_ratio": round(self.contrast, 3),
                "serif_length": round(self.serif_len, 4),
                "serif_thickness": round(self.serif_th, 4),
                "overshoot": round(self.over, 4)}


# --- primitives ----------------------------------------------------------------

def rect(x0, y0, x1, y1):
    return [("M", (x0, y0)), ("L", (x1, y0)), ("L", (x1, y1)),
            ("L", (x0, y1)), ("Z", None)]


def ellipse(cx, cy, rx, ry, ccw=False):
    """Closed cubic ellipse. ``ccw`` reverses winding so it punches a hole."""
    kx, ky = rx * K, ry * K
    p = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
    c = [((cx + kx, cy - ry), (cx + rx, cy - ky)),
         ((cx + rx, cy + ky), (cx + kx, cy + ry)),
         ((cx - kx, cy + ry), (cx - rx, cy + ky)),
         ((cx - rx, cy - ky), (cx - kx, cy - ry))]
    if ccw:
        p = [p[0], p[3], p[2], p[1]]
        c = [((cx - kx, cy - ry), (cx - rx, cy - ky)),
             ((cx - rx, cy + ky), (cx - kx, cy + ry)),
             ((cx + kx, cy + ry), (cx + rx, cy + ky)),
             ((cx + rx, cy - ky), (cx + kx, cy - ry))]
    out = [("M", p[0])]
    for i in range(4):
        out.append(("C", (c[i][0], c[i][1], p[(i + 1) % 4])))
    out.append(("Z", None))
    return out


def ring(cx, cy, rx, ry, tx, ty):
    """Didone bowl: thick at the sides (tx), hairline top and bottom (ty)."""
    return ellipse(cx, cy, rx, ry) + ellipse(cx, cy, max(rx - tx, rx * 0.06),
                                             max(ry - ty, ry * 0.06), ccw=True)


def serif(cx, y, half_len, th, up=True):
    """Unbracketed hairline slab serif of near-constant width."""
    return rect(cx - half_len, y, cx + half_len, y + (th if up else -th))


def ball(cx, cy, r):
    return ellipse(cx, cy, r, r)


def _arc_pts(cx, cy, rx, ry, a0, a1, n=8):
    return [(cx + rx * math.cos(a0 + (a1 - a0) * i / n),
             cy + ry * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def poly(points, close=True):
    out = [("M", points[0])] + [("L", p) for p in points[1:]]
    if close:
        out.append(("Z", None))
    return out


def open_bowl(cx, cy, rx, ry, tx, ty, a_start, a_end):
    """A c/e-style aperture: outer arc out, inner arc back, closed."""
    outer = _arc_pts(cx, cy, rx, ry, a_start, a_end, 12)
    inner = _arc_pts(cx, cy, max(rx - tx, rx * .06), max(ry - ty, ry * .06),
                     a_end, a_start, 12)
    return poly(outer + inner)


# --- glyphs (each authored at final size) --------------------------------------

def g_R(p, w):
    s, h = p.stem, p.hair
    bowl_h = p.cap * 0.52
    cy = p.cap - bowl_h / 2
    out = rect(0, 0, s, p.cap)
    out += serif(s / 2, 0, p.serif_len * 0.62, p.serif_th)
    out += serif(s / 2, p.cap, p.serif_len * 0.52, p.serif_th, up=False)
    rx = (w - s) * 0.92
    out += open_bowl(s, cy, rx, bowl_h / 2, rx * 0.42, h,
                     -math.pi / 2, math.pi / 2)
    out += poly([(s * 0.6, cy - bowl_h * 0.02), (s + rx * 0.55, cy - bowl_h * 0.30),
                 (w, 0), (w - s * 0.85, 0)])
    return out


def g_D(p, w):
    s, h = p.stem, p.hair
    out = rect(0, 0, s, p.cap)
    out += serif(s / 2, 0, p.serif_len * 0.60, p.serif_th)
    out += serif(s / 2, p.cap, p.serif_len * 0.60, p.serif_th, up=False)
    rx = (w - s)
    out += open_bowl(s, p.cap / 2, rx, p.cap / 2, rx * 0.40, h,
                     -math.pi / 2, math.pi / 2)
    return out


def g_o(p, w):
    return ring(w / 2, p.xh / 2, w / 2, p.xh / 2 + p.over, p.stem * 0.92,
                p.hair)


def g_e(p, w):
    cy = p.xh / 2
    rx, ry = w / 2, p.xh / 2 + p.over
    out = ring(w / 2, cy, rx, ry, p.stem * 0.88, p.hair)
    out += rect(rx * 0.16, cy + p.hair * 0.6, w - rx * 0.10,
                cy + p.hair * 0.6 + p.hair * 1.25)
    return out


def g_c(p, w):
    cy = p.xh / 2
    rx, ry = w / 2, p.xh / 2 + p.over
    out = open_bowl(w / 2, cy, rx, ry, p.stem * 0.88, p.hair,
                    math.radians(38), math.radians(322))
    out += ball(w / 2 + rx * 0.72, cy - ry * 0.62, p.hair * 1.5)
    out += ball(w / 2 + rx * 0.72, cy + ry * 0.62, p.hair * 1.5)
    return out


def g_s(p, w):
    rx = w / 2
    r = p.xh / 4
    out = open_bowl(w / 2, p.xh - r, rx, r + p.over, p.stem * 0.80, p.hair,
                    math.radians(-20), math.radians(200))
    out += open_bowl(w / 2, r, rx, r + p.over, p.stem * 0.80, p.hair,
                     math.radians(160), math.radians(380))
    out += ball(w / 2 + rx * 0.66, p.xh - r * 1.55, p.hair * 1.45)
    out += ball(w / 2 - rx * 0.66, r * 1.55, p.hair * 1.45)
    return out


def g_a(p, w):
    s, h = p.stem * 0.92, p.hair
    cy = p.xh * 0.30
    ry = p.xh * 0.30 + p.over
    rx = w / 2 * 0.96
    out = rect(w - s, 0, w, p.xh)
    out += ring(rx, cy, rx, ry, s * 0.9, h)
    arch = _arc_pts(w - s, p.xh - p.xh * 0.28, w * 0.62, p.xh * 0.28,
                    math.radians(200), math.radians(340), 10)
    inner = _arc_pts(w - s, p.xh - p.xh * 0.28, w * 0.62 - s * 0.85,
                     p.xh * 0.28 - h, math.radians(340), math.radians(200), 10)
    out += poly(arch + inner)
    out += ball(w * 0.08, p.xh * 0.70, h * 1.4)
    return out


def _arch(p, x0, w_arch, top, depth, s, h):
    o = _arc_pts(x0 + w_arch / 2, top - depth, w_arch / 2, depth,
                 math.pi, 2 * math.pi, 10)
    i = _arc_pts(x0 + w_arch / 2, top - depth, w_arch / 2 - s * 0.9,
                 depth - h, 2 * math.pi, math.pi, 10)
    return poly(o + i)


def g_n(p, w):
    s, h = p.stem, p.hair
    out = rect(0, 0, s, p.xh)
    out += serif(s / 2, 0, p.serif_len * 0.55, p.serif_th)
    out += rect(w - s, 0, w, p.xh * 0.80)
    out += serif(w - s / 2, 0, p.serif_len * 0.55, p.serif_th)
    out += _arch(p, 0, w, p.xh, p.xh * 0.30, s, h)
    return out


def g_m(p, w):
    s, h = p.stem, p.hair
    half = w / 2
    out = rect(0, 0, s, p.xh)
    out += serif(s / 2, 0, p.serif_len * 0.50, p.serif_th)
    out += rect(half - s / 2, 0, half + s / 2, p.xh * 0.80)
    out += serif(half, 0, p.serif_len * 0.50, p.serif_th)
    out += rect(w - s, 0, w, p.xh * 0.80)
    out += serif(w - s / 2, 0, p.serif_len * 0.50, p.serif_th)
    out += _arch(p, 0, half + s / 2, p.xh, p.xh * 0.28, s, h)
    out += _arch(p, half - s / 2, half + s / 2, p.xh, p.xh * 0.28, s, h)
    return out


BUILDERS = {"R": g_R, "D": g_D, "o": g_o, "e": g_e, "c": g_c, "s": g_s,
            "a": g_a, "n": g_n, "m": g_m}

#: condensed advance widths as a fraction of cap height — DESIGNED, not scaled
WIDTH_RATIO = {"R": 0.560, "D": 0.585, "o": 0.470, "e": 0.440, "c": 0.430,
               "s": 0.380, "a": 0.450, "n": 0.500, "m": 0.780}


def build_word(word: str, cap: float, *, target_width: float,
               contrast: float = 7.0):
    """Author every glyph at final size and solve the word width with optical
    side bearings only — never by scaling a glyph or the group."""
    p = Params(cap, contrast=contrast)
    widths = [WIDTH_RATIO[c] * cap for c in word]
    natural = sum(widths)
    n_gaps = max(1, len(word) - 1)
    gap = (target_width - natural) / n_gaps
    glyphs, x = [], 0.0
    for i, ch in enumerate(word):
        w = widths[i]
        contours = BUILDERS[ch](p, w)
        glyphs.append({"char": ch, "x": x, "width": w, "contours": contours})
        x += w + gap
    return {"params": p, "glyphs": glyphs, "gap": gap,
            "natural_width": natural, "target_width": target_width,
            "advance_width": x - gap}


def contour_bbox(contours):
    xs, ys = [], []
    for op, a in contours:
        if op in ("M", "L"):
            xs.append(a[0])
            ys.append(a[1])
        elif op == "C":
            for pt in a:
                xs.append(pt[0])
                ys.append(pt[1])
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)


def count_subpaths(contours):
    return sum(1 for op, _ in contours if op == "M")


def count_nodes(contours):
    return sum(1 for op, _ in contours if op in ("M", "L", "C"))
