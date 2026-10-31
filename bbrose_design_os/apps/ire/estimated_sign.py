"""[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 8: "The ℮ prints as a plain "e": it must be the real
estimated sign everywhere."]

The ℮ (U+212E) is drawn by every face the files set it in — and Noto Sans, the sticker's ruled face (§BH32(h)), draws it
as a light "e" with a lower bar, so on the pack it reads "60 ml e 2 fl oz"; the Arabic faces have none at all. Wherever
the files set text, the sign is now DRAWN — the estimated sign's own shape, a filled vector, in the run's colour, in the
room the run's face gives it — never left to the face:

- ITS SHAPE (``outline``) is the granted Montserrat Regular's ℮ (``container_font_owner_grant``, OFL): the sign as the
  EU directive draws it, a full-width bar across a closed bowl, read from the file once at its own units.
- IN A PDF (``draw_text``) a run holding the sign is drawn in pieces — its words in its own face, each sign as the shape
  at the run's size (as tall as its capitals), centred in the room the face gives it and the spaces beside it — so
  every measure the layout made of the run stands; its other text untouched.
- IN THE NATIVE .AI (``pieces``) the same run as its text pieces and each sign's outline, at the same places.
"""
from __future__ import annotations

import functools
import os

SIGN = "℮"
#: the granted face whose ℮ is the sign's shape (Montserrat, OFL — container_font_owner_grant)
SOURCE_FACE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "static",
                           "fonts", "brand2026", "Montserrat", "Montserrat-Regular.ttf")


@functools.lru_cache(maxsize=1)
def outline() -> dict:
    """The sign's shape at its face's own units: ``{"ops": [("M", x, y) | ("L", x, y) | ("C", x1, y1, x2, y2, x, y)
    | ("Z",)], "upm", "advance"}`` — y up from the baseline, as a face draws it."""
    from fontTools.pens.basePen import BasePen
    from fontTools.ttLib import TTFont

    font = TTFont(SOURCE_FACE)
    glyph_set = font.getGlyphSet()
    name = font.getBestCmap()[ord(SIGN)]

    class _Pen(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.ops = []

        def _moveTo(self, pt):
            self.ops.append(("M", float(pt[0]), float(pt[1])))

        def _lineTo(self, pt):
            self.ops.append(("L", float(pt[0]), float(pt[1])))

        def _curveToOne(self, p1, p2, p3):
            self.ops.append(("C", float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]), float(p3[0]),
                             float(p3[1])))

        def _closePath(self):
            self.ops.append(("Z",))

    pen = _Pen(glyph_set)
    glyph_set[name].draw(pen)
    return {"ops": pen.ops, "upm": float(font["head"].unitsPerEm), "advance": float(font["hmtx"][name][0])}


def room(face: str, size: float) -> float:
    """The room (points) a run's face gives the sign — its own advance for it, else its "e"'s."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.pdfmetrics import stringWidth
    try:
        have = pdfmetrics.getFont(face).face.charToGlyph
    except AttributeError:
        have = {}
    return stringWidth(SIGN if ord(SIGN) in have else "e", face, size)


#: the share of the room the sign's ink may take, so it never touches its neighbours
INK_SHARE = 0.94
#: [his goal of 2026-10-12, (5): "℮: at least 3 mm tall wherever it's printed (the EU rule), on every design."] the
#: sign's own drawn height is never under this — given the room that height needs, so it never squeezes its neighbours
MIN_HEIGHT_MM = 3.0
PT_PER_MM = 72.0 / 25.4
#: [his word of 2026-10-17 on 142: "The ℮ is scaled with its line (at least 3 mm only where the line is large enough);
#: never larger than the text beside it."] the height of a line's capitals, a share of its size: the sign is raised to
#: MIN_HEIGHT_MM only where they stand that tall themselves — never drawn taller than the words beside it
CAP_SHARE = 0.72


def floor_for(size: float, per_mm: float = PT_PER_MM) -> float:
    """The least height the sign is drawn at for a run of ``size`` (in the units ``size`` is in, ``per_mm`` a mm):
    MIN_HEIGHT_MM where the run's capitals (CAP_SHARE of its size) reach it, else none — the sign as its line draws it."""
    if CAP_SHARE * size >= MIN_HEIGHT_MM * per_mm:
        return MIN_HEIGHT_MM * per_mm
    return 0.0


@functools.lru_cache(maxsize=1)
def _ink() -> tuple:
    """The sign's ink at its face's units: ``(left, right, bottom, top)``."""
    ops = outline()["ops"]
    xs = [op[i] for op in ops for i in range(1, len(op), 2)]
    ys = [op[i] for op in ops for i in range(2, len(op), 2)]
    return min(xs), max(xs), min(ys), max(ys)


def sign_room(face: str, size: float, per_mm: float = PT_PER_MM) -> float:
    """The room the sign is drawn in, in the units ``size`` is in (``per_mm`` of them to a millimetre): the room its
    face gives it, or more where the sign at MIN_HEIGHT_MM needs more."""
    left, right, bottom, top = _ink()
    need = (right - left) * (floor_for(size, per_mm) / (top - bottom)) / INK_SHARE
    return max(room(face, size), need)


def width(text: str, face: str, size: float, per_mm: float = PT_PER_MM) -> float:
    """``text``'s width as the files lay it out: its words in ``face``, each ℮ in its ``sign_room``."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if SIGN not in text:
        return stringWidth(text, face, size)
    return stringWidth(text.replace(SIGN, ""), face, size) + text.count(SIGN) * sign_room(face, size, per_mm)
#: the share of a space beside the sign its ink may reach into — so it stands as tall as the run's capitals (its own
#: face's size), never squeezed into the narrow room of an "e"; never past the space, so no measure moves
SPACE_SHARE = 0.6


def _spares(parts: list, i: int, face: str, size: float) -> tuple:
    """How far (points) the i-th sign's ink may reach into the space before it and the space after it — SPACE_SHARE of
    the face's space where the run has one there, else nothing."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    space = SPACE_SHARE * stringWidth(" ", face, size)
    return (space if parts[i].endswith(" ") else 0.0), (space if parts[i + 1].startswith(" ") else 0.0)


def _placed(x: float, y: float, size: float, width: float, *, y_up: bool = True, min_h: float = 0.0) -> list:
    """The sign's ops at ``size``, its ink no wider than INK_SHARE of ``width`` (the room the run is laid out with, so
    every measure the layout made stands), centred in it from ``x`` on the baseline ``y`` — and never under ``min_h``
    tall (MIN_HEIGHT_MM, in the units ``size`` is in), its room made for that height (``sign_room``)."""
    shape = outline()
    xs = [op[i] for op in shape["ops"] for i in range(1, len(op), 2)]
    ink = max(xs) - min(xs)
    left, right, bottom, top = _ink()
    s = max(min(size / shape["upm"], INK_SHARE * width / ink), min_h / (top - bottom))
    dx = x + (width - ink * s) / 2.0 - min(xs) * s
    sign = 1.0 if y_up else -1.0
    out = []
    for op in shape["ops"]:
        pts = op[1:]
        out.append((op[0],) + tuple(dx + pts[i] * s if i % 2 == 0 else y + sign * pts[i] * s
                                    for i in range(len(pts))))
    return out


def draw_text(c, x: float, y: float, text: str, face: str, size: float, align: str = "left") -> None:
    """``text`` drawn on the canvas ``c`` at (x, y) points in ``face`` — as ``drawString`` / ``drawCentredString`` /
    ``drawRightString`` would by ``align`` — each ℮ in it DRAWN as the sign's own shape in the room the face gives it,
    in the canvas's fill colour; a run with no ℮ drawn as before. The canvas's font must be set."""
    if SIGN not in text:
        if align == "center":
            c.drawCentredString(x, y, text)
        elif align == "right":
            c.drawRightString(x, y, text)
        else:
            c.drawString(x, y, text)
        return
    from reportlab.pdfbase.pdfmetrics import stringWidth
    parts = text.split(SIGN)
    widths = [stringWidth(p, face, size) for p in parts]
    gap = sign_room(face, size)                     # [his goal of 2026-10-12, (5)] the room a 3 mm sign needs
    total = sum(widths) + gap * (len(parts) - 1)
    if align == "center":
        x -= total / 2.0
    elif align == "right":
        x -= total
    for i, part in enumerate(parts):
        if part:
            c.drawString(x, y, part)
        x += widths[i]
        if i < len(parts) - 1:
            before, after = _spares(parts, i, face, size)
            path = c.beginPath()
            for op in _placed(x - before, y, size, gap + before + after, min_h=floor_for(size)):
                if op[0] == "M":
                    path.moveTo(*op[1:])
                elif op[0] == "L":
                    path.lineTo(*op[1:])
                elif op[0] == "C":
                    path.curveTo(*op[1:])
                else:
                    path.close()
            c.drawPath(path, fill=1, stroke=0)
            x += gap


def pieces(text: str, x: float, y: float, size: float, face: str, align: str = "left") -> list:
    """For a file that sets text as items (the native .ai): ``[("text", piece, x) | ("sign", ops)]`` in millimetres —
    the run's words at their places and each sign's outline (y down, as the file's own page), the run laid out as
    ``draw_text`` lays it; ``[("text", text, x)]`` for a run with no ℮."""
    if SIGN not in text:
        return [("text", text, x)]
    from reportlab.pdfbase.pdfmetrics import stringWidth
    mm = 72.0 / 25.4
    parts = text.split(SIGN)
    widths = [stringWidth(p, face, size) / mm for p in parts]
    gap = sign_room(face, size) / mm                # [his goal of 2026-10-12, (5)] the room a 3 mm sign needs
    total = sum(widths) + gap * (len(parts) - 1)
    if align == "center":
        x -= total / 2.0
    elif align == "right":
        x -= total
    out = []
    for i, part in enumerate(parts):
        if part:
            out.append(("text", part, x))
        x += widths[i]
        if i < len(parts) - 1:
            before, after = (v / mm for v in _spares(parts, i, face, size))
            out.append(("sign", _placed(x - before, y, size / mm, gap + before + after, y_up=False,
                                        min_h=floor_for(size / mm, 1.0))))
            x += gap
    return out


def svg_text(x: float, y: float, text: str, size: float, attrs: str, face: str = "Helvetica-Bold") -> str:
    """For an SVG twin (its units millimetres): ``text`` as its own ``<text>`` pieces (``attrs`` on each: its family, size
    and fill) and each ℮ an SVG ``<path>`` of the sign's own shape, laid out left to right from ``x`` on the baseline
    ``y`` by ``face``'s widths (``size`` its size in the twin's units); a run with no ℮ as one ``<text>``."""
    from xml.sax.saxutils import escape
    if SIGN not in text:
        return '<text x="%.2f" y="%.2f" %s>%s</text>' % (x, y, attrs, escape(text))
    out = []
    for piece in pieces(text, x, y, size * 72.0 / 25.4, face):
        if piece[0] == "text":
            out.append('<text x="%.2f" y="%.2f" %s>%s</text>' % (piece[2], y, attrs, escape(piece[1])))
            continue
        d = []
        for op in piece[1]:
            if op[0] == "M":
                d.append("M%.3f %.3f" % op[1:])
            elif op[0] == "L":
                d.append("L%.3f %.3f" % op[1:])
            elif op[0] == "C":
                d.append("C%.3f %.3f %.3f %.3f %.3f %.3f" % op[1:])
            else:
                d.append("Z")
        out.append('<path d="%s" fill="#3F2620"/>' % " ".join(d))
    return "".join(out)
