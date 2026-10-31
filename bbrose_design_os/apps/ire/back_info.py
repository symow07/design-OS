"""[His final goal, 2026-10-05 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32e9aaf), B3: "THE BACK INFO IS A STICKER, his
choice at the size step. Sticker (default): the ground runs across the back; the info sits ON TOP as a rounded-rectangle
label with a margin. Printed directly on the panel. Custom sticker: follows a sticker reference picture or the brief's
words. With no reference or words, the default sticker is used."]

How the back's label stands on the carton:

- "sticker" (the default): a white rounded rectangle on the back's safe margin, over the carton's ground; the copy
  STICKER_PAD_MM inside it.
- "printed": no sticker — the copy printed on the back's own ground, inside its safe margin, in the front's ink that
  stands out most from that ground.
- "custom": the sticker his sticker reference picture shows (read once for its shape, corners, fill and border — never
  its pixels) or his brief's "Sticker:" words say — its shape (rounded, square-cornered, pill, oval, arch, scalloped,
  ticket), its fill in the design's own colours (paper white, a light tint of the ground, or the deep ink with the copy
  in the ground's colour), its border (none, thin, double); the copy in the largest rectangle the shape holds. With
  neither, the default sticker."""
from __future__ import annotations

import math
import re

MODES = ("sticker", "printed", "custom")
DEFAULT_MODE = "sticker"
KIND = "sticker_reference"
SHAPES = ("rounded", "square", "pill", "oval", "arch", "scalloped", "ticket")
FILLS = ("paper", "light", "dark")
BORDERS = ("none", "thin", "double")
PAD_MM = 1.5
RADIUS_MM = 2.0
BORDER_MM = 0.25
PAPER = "#FFFFFF"
#: what his words say of the sticker — the first each names leads
SHAPE_WORDS = (("oval", ("oval", "ellipse", "elliptical")), ("arch", ("arch", "arched", "arched-top")),
               ("pill", ("pill", "capsule", "lozenge")), ("scalloped", ("scallop", "scalloped", "wavy-edged")),
               ("ticket", ("ticket", "tag", "notched")), ("square", ("square", "square-cornered", "sharp", "rectangle",
                                                                     "rectangular")),
               ("rounded", ("rounded", "round-cornered", "soft")))
FILL_WORDS = (("dark", ("dark", "deep", "black", "berry", "navy", "inverted")),
              ("light", ("tint", "tinted", "light", "pale", "pastel", "blush")),
              ("paper", ("white", "paper", "clear", "cream")))
BORDER_WORDS = (("double", ("double",)), ("thin", ("border", "bordered", "outline", "outlined", "frame", "framed",
                                                   "line", "keyline")),
                ("none", ("borderless", "frameless", "no border")))
#: a sticker reference read into its shape and style: what the reader is asked
SYSTEM = """You read ONE picture of a STICKER LABEL a designer wants on the back of a cosmetics carton at BBROSE. Read its
SHAPE and STYLE so a NEW sticker can be drawn in vector in the design's own colours — never a copy of the picture.

Return ONE JSON object and nothing else:
{
  "shape": "one of: rounded, square, pill, oval, arch, scalloped, ticket",
  "fill": "one of: paper (white or near white), light (a pale tint), dark (a deep colour with light words)",
  "border": "one of: none, thin, double",
  "style": "the sticker's character, under 25 words — corners, edge, proportions, spacing",
  "take": "one sentence: what the new sticker should take from this picture, as qualities",
  "seen_not_taken": ["each brand name, logo, trademark or line of text you can see — NEVER reproduced"]
}
Rules: describe qualities, never an object to reproduce; no hex codes; no brand names outside seen_not_taken."""
FIELDS = ("shape", "fill", "border", "style", "take")


def brief_sticker_words(brief: str) -> str:
    """His brief's "Sticker: ..." words — the line and the lines under it until a blank line or another heading."""
    out, on = [], False
    for line in str(brief or "").splitlines():
        m = re.match(r"^\s*(?:back\s+)?sticker\s*:\s*(.*)$", line, re.IGNORECASE)
        if m:
            out, on = [m.group(1).strip()], True
            continue
        if on:
            if not line.strip() or re.match(r"^\s*[A-Z][\w ]{0,30}:", line):
                break
            out.append(line.strip())
    return " ".join(w for w in out if w).strip()


def _first(table, text):
    for value, names in table:
        if any(re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(n), text) for n in names):
            return value
    return None


def spec_from_words(words: str) -> dict | None:
    """His words read for the sticker ($0): its shape, fill and border; None where they name none of these."""
    text = " %s " % str(words or "").lower()
    spec = {k: v for k, v in (("shape", _first(SHAPE_WORDS, text)), ("fill", _first(FILL_WORDS, text)),
                              ("border", _first(BORDER_WORDS, text))) if v}
    return spec or None


def plan(mode: str, readings: list, words: str) -> dict:
    """How the back's label stands: ``{"mode", "shape", "fill", "border", "source"}`` — "custom" from his first sticker
    reference's reading under his words (his words win where they say a thing), else the default sticker, said."""
    mode = mode if mode in MODES else DEFAULT_MODE
    out = {"mode": mode, "shape": "rounded", "fill": "paper", "border": "none", "words": words or ""}
    if mode == "sticker":
        return dict(out, source="the default sticker")
    if mode == "printed":
        return dict(out, source="his choice: printed on the panel")
    sources = []
    for reading in readings[:1]:
        for k, allowed in (("shape", SHAPES), ("fill", FILLS), ("border", BORDERS)):
            v = str(reading.get(k) or "").strip().lower()
            if v in allowed:
                out[k] = v
        sources.append("his sticker reference")
    said = spec_from_words(words)
    if said:
        out.update(said)
        sources.append("his brief's words")
    if not sources:
        return dict(out, mode="sticker", source="the default sticker: no sticker reference and no words were given")
    return dict(out, source=" and ".join(sources))


def text_rect(style: dict, w: float, h: float) -> tuple:
    """The largest rectangle (x, y, w, h — from the sticker's top left, mm) the sticker's shape holds its copy in, its
    pad kept: an oval's inscribed rectangle, under an arch's spring, inside a pill's round ends."""
    shape = style.get("shape", "rounded")
    pad = PAD_MM + (2 * BORDER_MM if style.get("border") == "double" else 0.0)
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    if shape == "oval":
        ix, iy = w / 2.0 * (1 - 1 / math.sqrt(2)), h / 2.0 * (1 - 1 / math.sqrt(2))
        x0, y0, x1, y1 = ix + pad, iy + pad, w - ix - pad, h - iy - pad
    elif shape == "arch":
        y0 = _full_width_depth(w / 2.0, pad) + pad            # where the arch is as wide as the copy's column
    elif shape == "pill":
        r = min(w, h) / 2.0
        if h >= w:
            y0, y1 = _full_width_depth(r, pad) + pad, h - _full_width_depth(r, pad) - pad
        else:
            x0, x1 = _full_width_depth(r, pad) + pad, w - _full_width_depth(r, pad) - pad
    elif shape == "scalloped":
        x0, y0, x1, y1 = x0 + 1.0, y0 + 1.0, x1 - 1.0, y1 - 1.0
    elif shape == "ticket":
        x0, x1 = x0 + 1.0, x1 - 1.0
    return (x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0))


def _full_width_depth(r: float, pad: float) -> float:
    """How far into a half circle of radius ``r`` its chord is as wide as the circle less ``pad`` each side."""
    return r - math.sqrt(max(0.0, r * r - (r - pad) ** 2))


def _rounded(x, y, w, h, r):
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    r = max(0.0, min(r, w / 2.0, h / 2.0))
    k = 0.5523 * r
    return [MoveTo(x=x + r, y=y), LineTo(x=x + w - r, y=y),
            CubicTo(x1=x + w - r + k, y1=y, x2=x + w, y2=y + r - k, x=x + w, y=y + r), LineTo(x=x + w, y=y + h - r),
            CubicTo(x1=x + w, y1=y + h - r + k, x2=x + w - r + k, y2=y + h, x=x + w - r, y=y + h), LineTo(x=x + r, y=y + h),
            CubicTo(x1=x + r - k, y1=y + h, x2=x, y2=y + h - r + k, x=x, y=y + h - r), LineTo(x=x, y=y + r),
            CubicTo(x1=x, y1=y + r - k, x2=x + r - k, y2=y, x=x + r, y=y), ClosePath()]


def _oval(x, y, w, h):
    from apps.ire.graph import ClosePath, CubicTo, MoveTo
    cx, cy, rx, ry = x + w / 2.0, y + h / 2.0, w / 2.0, h / 2.0
    kx, ky = 0.5523 * rx, 0.5523 * ry
    return [MoveTo(x=cx + rx, y=cy), CubicTo(x1=cx + rx, y1=cy + ky, x2=cx + kx, y2=cy + ry, x=cx, y=cy + ry),
            CubicTo(x1=cx - kx, y1=cy + ry, x2=cx - rx, y2=cy + ky, x=cx - rx, y=cy),
            CubicTo(x1=cx - rx, y1=cy - ky, x2=cx - kx, y2=cy - ry, x=cx, y=cy - ry),
            CubicTo(x1=cx + kx, y1=cy - ry, x2=cx + rx, y2=cy - ky, x=cx + rx, y=cy), ClosePath()]


def _arch(x, y, w, h):
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    r = w / 2.0
    k = 0.5523 * r
    cx, top = x + r, y + r
    return [MoveTo(x=x, y=y + h), LineTo(x=x, y=top),
            CubicTo(x1=x, y1=top - k, x2=cx - k, y2=y, x=cx, y=y),
            CubicTo(x1=cx + k, y1=y, x2=x + w, y2=top - k, x=x + w, y=top), LineTo(x=x + w, y=y + h), ClosePath()]


def _scalloped(x, y, w, h):
    """A rectangle whose edges run in shallow half-circle scallops, about 4 mm each."""
    from apps.ire.graph import ClosePath, CubicTo, MoveTo
    segs = [MoveTo(x=x, y=y)]

    def edge(ax, ay, bx, by, outward):
        n = max(2, int(round(math.hypot(bx - ax, by - ay) / 4.0)))
        dx, dy = (bx - ax) / n, (by - ay) / n
        nx, ny = outward
        for i in range(n):
            sx, sy = ax + dx * i, ay + dy * i
            ex, ey = sx + dx, sy + dy
            bump = 0.9
            segs.append(CubicTo(x1=sx + dx * 0.2 + nx * bump, y1=sy + dy * 0.2 + ny * bump,
                                x2=ex - dx * 0.2 + nx * bump, y2=ey - dy * 0.2 + ny * bump, x=ex, y=ey))
    edge(x, y, x + w, y, (0, -1))
    edge(x + w, y, x + w, y + h, (1, 0))
    edge(x + w, y + h, x, y + h, (0, 1))
    edge(x, y + h, x, y, (-1, 0))
    segs.append(ClosePath())
    return segs


def _ticket(x, y, w, h):
    """A rectangle with a half-round notch in the middle of each long side."""
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    r = min(w, h) * 0.08
    k = 0.5523 * r
    my = y + h / 2.0
    return [MoveTo(x=x, y=y), LineTo(x=x + w, y=y), LineTo(x=x + w, y=my - r),
            CubicTo(x1=x + w - k, y1=my - r, x2=x + w - r, y2=my - k, x=x + w - r, y=my),
            CubicTo(x1=x + w - r, y1=my + k, x2=x + w - k, y2=my + r, x=x + w, y=my + r), LineTo(x=x + w, y=y + h),
            LineTo(x=x, y=y + h), LineTo(x=x, y=my + r),
            CubicTo(x1=x + k, y1=my + r, x2=x + r, y2=my + k, x=x + r, y=my),
            CubicTo(x1=x + r, y1=my - k, x2=x + k, y2=my - r, x=x, y=my - r), ClosePath()]


def outline(style: dict, x: float, y: float, w: float, h: float) -> list:
    """The sticker's outline as path segments, in the document's millimetres."""
    shape = style.get("shape", "rounded")
    if shape == "oval":
        return _oval(x, y, w, h)
    if shape == "arch":
        return _arch(x, y, w, h)
    if shape == "scalloped":
        return _scalloped(x, y, w, h)
    if shape == "ticket":
        return _ticket(x, y, w, h)
    radius = {"square": 0.0, "pill": min(w, h) / 2.0}.get(shape, RADIUS_MM)
    return _rounded(x, y, w, h, radius)


def colours(style: dict, ground_hex: str, ink_hex: str) -> tuple:
    """(the sticker's fill, the copy's ink) in the design's own colours: paper white and the front's ink; a light tint
    of the ground and the ink; or the deep ink with the copy in the ground's colour."""
    from apps.ire.graph import Color
    fill = style.get("fill", "paper")
    if fill == "dark":
        return ink_hex, ground_hex
    if fill == "light":
        g = Color.from_hex(ground_hex)
        tint = Color(r=g.r + (1 - g.r) * 0.55, g=g.g + (1 - g.g) * 0.55, b=g.b + (1 - g.b) * 0.55)
        return tint.to_hex(), ink_hex
    return PAPER, ink_hex
