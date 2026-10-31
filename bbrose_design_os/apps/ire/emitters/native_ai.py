"""[His final goal, 2026-10-05 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32e9aaf), C6: "EVERY ELEMENT IS ITS OWN PIECE. In
the .ai, each part is a separate, named layer or group he can select, move or delete alone. Text stays editable where
possible." With B1 ("Two artboards, OUTSIDE and INSIDE") and B2 ("Each on its own named layer: CUT, CREASE, GLUE, BLEED,
SAFE, ARTWORK").]

The design's native Illustrator file, built in Illustrator itself from the Design Graph whenever Illustrator is on this
machine: the document as plain data (``tree``) and a bounded script (``script``) that builds it — two artboards, OUTSIDE
and INSIDE; the named layers ARTWORK, CUT, CREASE, GLUE, BLEED, SAFE, DIMENSIONS (the guides not printing); every group
of the graph a named group, every path a named path (a compound path where it has holes), every run of words live point
text in its own face (Arabic set right to left in Illustrator's own Middle Eastern composer), the label's every line its
own text (``label_layout.plan_to_nodes``), the house mark its outlines; the die's lines on their spot swatches
(CutContour, Crease), overprinting — then saved as an .ai beside the design's other files and closed; Illustrator's own
documents are never touched. Where Illustrator is not on this machine, or a face it needs is not installed, nothing is
built and the record says why (``build``): the PDF-compatible .ai stays the design's file.

[His bug on design 124, 2026-10-12 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c32250d): "the layered Illustrator
file must carry EVERY drawn element, each on its named layer."] Its gradients are gradients (``_fill``'s "grad",
Illustrator's own gradient on the item); a group that draws nothing is not carried, a mask Illustrator refuses leaves no
path behind (124's lid lay under one: its empty map group's clipping path, filled white), and a mask of many paths is
carried whole, its holes kept; a fill and a stroke at their own strength; a barcode, a pattern, a soft shadow and a
blend mode as the PDF draws them; a fade Illustrator's scripting cannot make is named (``effects_not_carried``).

[His bug, the same message: "Add a check that compares the layered file with the drawing (same elements, nothing
missing), and make it fail if anything is dropped."] The file is checked against the drawing (``check``): every element
the data sends built — its paths, words, groups, masks, gradients, blends and pictures counted on both sides,
Illustrator's errors none — every page of the drawing an artboard of the file, and, page by page, every place the
drawing inks inked in the file too, nothing inked where the drawing draws nothing (``CHECK``); a file that fails is not
offered, the reason said."""
from __future__ import annotations

import contextvars
import functools
import json
import os

LAYERS = ("ARTWORK", "CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS")
NOT_PRINTING = ("GLUE", "BLEED", "SAFE", "DIMENSIONS")
ARTBOARD_GAP_MM = 20.0
#: the faces reportlab registers, by the PostScript names Illustrator knows them by
POSTSCRIPT = {"NotoSans": "NotoSans-Regular", "NotoSans-Bold": "NotoSans-Bold",
              "NotoNaskhArabic": "NotoNaskhArabic-Regular", "NotoNaskhArabic-Bold": "NotoNaskhArabic-Bold",
              "Fredoka-Narrow": "Fredoka-Condensed",
              "Fredoka-NarrowBold": "Fredoka-SemiBoldCondensed"}
SCHEMA = "native_ai/1.0"
#: the check's numbers (the executor's, set on 124's layered file and a carton with an inside; his to change): both
#: files rendered at ``dpi``, every layer shown, and cut into cells of ``cell_mm``; a pixel darker than ``paper_l``
#: (CIE L*) is ink; a cell the drawing inks over ``ink_share`` of must, it or a neighbour, be inked over ``kept`` of
#: that in the file read faintly (darker than ``faint_l``: the CMYK file renders a pale ground half a step lighter),
#: and a cell the drawing, it and its neighbours read faintly, leaves under ``clear`` inked may not be inked over
#: ``extra`` in the file — colours are not compared (the file is CMYK), nor words by their ink (a face Illustrator does
#: not have sets them in a substitute): each line of words is counted built
CHECK = {"version": "native_check/1.1", "dpi": 30, "cell_mm": 5.0, "paper_l": 96.0, "faint_l": 98.0, "ink_share": 0.25,
         "kept": 0.4, "clear": 0.03, "extra": 0.3, "colour_dpi": 60, "smooth": 6.0, "colour_de": 10.0, "colour_places": 3}
#: [his goal of 2026-10-13, (10): "colour drift"] … and, where the file is RGB (its colours the drawing's own until his
#: printer's profile is set), its colours: both pages rendered at ``colour_dpi`` every layer shown, cut into the same
#: cells; a cell SMOOTH in both (nine in ten of its pixels within ``smooth`` ΔE76 of its own mean — a field, a glow, a
#: sky; never fine work, whose edges the two readers draw differently) whose two means differ by over ``colour_de`` is a
#: place drawn in another colour; ``colour_places`` of them fail. Set on 125's front (its glow and field washed out by
#: a leaked alpha: 33 such places; drawn whole: none over ΔE 2.8) and 124's (none over 9.2).
CHECK_FAILED = "NATIVE_AI_DROPS_ELEMENTS"
PASS, FAIL = "PASS", "FAIL"


# --- [his goal of 2026-10-12, (1): "keep the files RGB like the drawing until I give you my printer's CMYK profile;
# --- then convert with that profile only."] the layered file is an RGB document painting each colour as the drawing
# --- paints it; with his printer's profile set (PRODUCTION_ICC_PROFILE_PATH, an output profile ``output_intent``
# --- validates), a CMYK document, each colour through that profile and no other. The die's lines and the finishes'
# --- plates stay spot colours, as they print.

#: the conversion the layered file is built with: None, RGB; else a colour's CMYK through his printer's profile
_SPACE = contextvars.ContextVar("native_ai_space", default=None)
#: a plate's mask and a die line are defined in the press's own inks
PLATE_INK = [0.0, 0.0, 0.0, 1.0]


def press_profile() -> str | None:
    """His printer's CMYK profile where one is set and valid (``output_intent.describe_profile``), else None."""
    from apps.dielines.exporters.output_intent import describe_profile
    ident = describe_profile()
    return ident.path if ident.valid else None


@functools.lru_cache(maxsize=4)
def _through(profile_path: str):
    """A colour's CMYK through ``profile_path`` (from sRGB, relative colorimetric, as a press converts a proof)."""
    from PIL import Image, ImageCms
    transform = ImageCms.buildTransform(ImageCms.createProfile("sRGB"), ImageCms.getOpenProfile(profile_path), "RGB",
                                        "CMYK", renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)

    @functools.lru_cache(maxsize=65536)
    def convert(rgb: tuple) -> list:
        px = ImageCms.applyTransform(Image.new("RGB", (1, 1), rgb), transform).getpixel((0, 0))
        return [round(v / 255.0, 4) for v in px]
    return convert


def _ink(color) -> list:
    """A colour as the layered file writes it: its RGB as the drawing paints it — or, with his printer's profile set,
    its CMYK through that profile (a colour the graph already carries in print CMYK, that CMYK, as the drawing)."""
    convert = _SPACE.get()
    if convert is None:
        return [round(color.r, 4), round(color.g, 4), round(color.b, 4)]
    if getattr(color, "cmyk", None):
        return [round(v, 4) for v in color.cmyk]
    return convert((int(round(color.r * 255)), int(round(color.g * 255)), int(round(color.b * 255))))


def _cmyk(color) -> list:
    """A colour's CMYK by arithmetic — kept for what reads it outside the layered file; the file itself writes
    ``_ink``."""
    if getattr(color, "cmyk", None):
        return [round(v, 4) for v in color.cmyk]
    r, g, b = color.r, color.g, color.b
    k = 1.0 - max(r, g, b)
    if k >= 1.0:
        return [0.0, 0.0, 0.0, 1.0]
    return [round((1 - r - k) / (1 - k), 4), round((1 - g - k) / (1 - k), 4), round((1 - b - k) / (1 - k), 4),
            round(k, 4)]


def _segs(segments) -> list:
    out = []
    for s in segments:
        op = s.op
        if op == "M":
            out.append(["M", s.x, s.y])
        elif op == "L":
            out.append(["L", s.x, s.y])
        elif op == "C":
            out.append(["C", s.x1, s.y1, s.x2, s.y2, s.x, s.y])
        else:
            out.append(["Z"])
    return out


def _turn_item(item: dict, turn) -> dict:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2).] One item of the data sent to Illustrator turned onto the
    page by a group's quarter turn (``graph.Group.turn``): a path's and a clip's points, a rect's corners (it stays a
    rect, its sides swapped), a line of type's anchor and its rotation, a gradient's run, a picture's place and its
    rotation, a group's items — so the file draws the turned group exactly where the drawing does."""
    import math

    from apps.ire.graph import turned_point
    a, b = turn[0], turn[1]
    degrees = math.degrees(math.atan2(-b, a))          # the turn, counter-clockwise as a line of type turns
    out = dict(item)

    def segs(seq):
        moved = []
        for s in seq or []:
            if s[0] in ("M", "L"):
                x, y = turned_point(turn, s[1], s[2])
                moved.append([s[0], x, y])
            elif s[0] == "C":
                x1, y1 = turned_point(turn, s[1], s[2])
                x2, y2 = turned_point(turn, s[3], s[4])
                x, y = turned_point(turn, s[5], s[6])
                moved.append(["C", x1, y1, x2, y2, x, y])
            else:
                moved.append(list(s))
        return moved

    def paint(fill):
        if not fill or not fill.get("grad"):
            return fill
        grad = dict(fill["grad"])
        for key in ("from", "to", "centre"):
            grad[key] = list(turned_point(turn, *grad[key]))
        return dict(fill, grad=grad)

    kind = item.get("t")
    if kind == "g":
        out["kids"] = [_turn_item(k, turn) for k in item.get("kids") or []]
        if item.get("clip"):
            out["clip"] = segs(item["clip"])
    elif kind == "p":
        out["segs"] = segs(item["segs"])
        out["fill"] = paint(item.get("fill"))
    elif kind == "r":
        corners = [turned_point(turn, item["x"] + dx, item["y"] + dy) for dx in (0.0, item["w"]) for dy in (0.0, item["h"])]
        xs, ys = [c[0] for c in corners], [c[1] for c in corners]
        out.update(x=min(xs), y=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys), fill=paint(item.get("fill")))
    elif kind == "x":
        out["x"], out["y"] = turned_point(turn, item["x"], item["y"])
        out["rot"] = (item.get("rot") or 0.0) + degrees
    elif kind == "i":
        cx, cy = turned_point(turn, item["x"] + item["w"] / 2.0, item["y"] + item["h"] / 2.0)
        out.update(x=cx - item["w"] / 2.0, y=cy - item["h"] / 2.0, rot=(item.get("rot") or 0.0) + degrees)
    return out


#: [his goal of 2026-10-13, (8) and (9)] a mesh patch in the layered file: grown outward this far (mm) under its shape's
#: own clip, so neighbouring patches meet with no hairline between them; read at SAMPLES x SAMPLES points for its error
MESH_OVERLAP_MM, MESH_SAMPLES = 0.04, 5


def _lab(rgb) -> tuple:
    """sRGB (0..1) as CIE L*a*b* (D65)."""
    def lin(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(min(1.0, max(0.0, v))) for v in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0
    fx, fy, fz = f(x), f(y), f(z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


#: [his goal of 2026-10-13, (9)] a field's grid row carried as thin strips, each a gradient across: as many as keep each
#: strip's step down the row under MESH_STRIP_DE (ΔE76), at least MESH_STRIPS_LEAST and at most MESH_STRIPS_MOST
MESH_STRIP_DE, MESH_STRIPS_LEAST, MESH_STRIPS_MOST = 1.0, 2, 64


def _strip_items(grid: dict, name: str) -> tuple:
    """``(items, ΔE76 p95)`` — a field read on a grid (``graph.MeshFill.grid``) as the layered file carries it: each row
    of the grid in thin rects across its whole width (as many as its colour's change down the row asks), each one smooth linear gradient left to right through
    the colours at the grid's columns, blended down the row at the strip's middle; read at three heights and every
    column of each strip for its error against the mesh's own blend."""
    import math

    import numpy as np

    from apps.ire.graph import Color
    xs, ys = [float(v) for v in grid["xs"]], [float(v) for v in grid["ys"]]
    inks = np.array([[[int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)] for c in row] for row in grid["inks"]],
                    float) / 255.0
    x0, x1 = xs[0], xs[-1]
    width = max(x1 - x0, 1e-6)

    def colour(c):
        return Color(r=float(min(1.0, max(0.0, c[0]))), g=float(min(1.0, max(0.0, c[1]))),
                     b=float(min(1.0, max(0.0, c[2]))))
    items, errors = [], []
    for i in range(len(ys) - 1):
        down = max(math.dist(_lab(inks[i][j]), _lab(inks[i + 1][j])) for j in range(len(xs)))
        strips = int(min(MESH_STRIPS_MOST, max(MESH_STRIPS_LEAST, math.ceil(down / MESH_STRIP_DE))))
        for k in range(strips):
            t = (k + 0.5) / strips
            top = ys[i] + (ys[i + 1] - ys[i]) * k / strips
            tall = (ys[i + 1] - ys[i]) / strips
            row = inks[i] * (1 - t) + inks[i + 1] * t
            mid = top + tall / 2.0
            items.append({"t": "r", "name": "%s-strip-%d-%d" % (name, i, k), "x": x0, "y": top, "w": width,
                          "h": tall + (MESH_OVERLAP_MM if i < len(ys) - 2 or k < strips - 1 else 0.0), "r": 0.0,
                          "stroke": None, "o": 1.0,
                          "fill": {"c": _ink(colour(row[len(row) // 2])), "o": 1.0, "grad": {
                              "kind": "linear", "stops": [[(xs[j] - x0) / width, _ink(colour(row[j]))]
                                                          for j in range(len(xs))],
                              "from": [x0, mid], "to": [x1, mid], "centre": [x0, mid], "r": 0.0}}})
            for s in (0.1, 0.5, 0.9):
                truth = inks[i] * (1 - (k + s) / strips) + inks[i + 1] * ((k + s) / strips)
                for j in range(len(xs)):
                    errors.append(math.dist(_lab(truth[j]), _lab(row[j])))
    return items, (float(np.percentile(errors, 95)) if errors else 0.0)


def _blur_items(blur: dict, name: str) -> list:
    """A glow (``graph.MeshFill.blur``) as the layered file carries it: one stroke a ring, along the glow's line, as wide
    as the ring reaches, round at its ends, under Illustrator's own Gaussian blur as soft as the ring is wide — the
    widest first."""
    from apps.ire.graph import Color
    pts = blur["points"]
    segs = [["M", float(pts[0][0]), float(pts[0][1])]] + [["L", float(x), float(y)] for x, y in pts[1:]]
    if blur.get("closed"):
        segs.append(["Z"])
    return [{"t": "p", "name": "%s-blur-%d" % (name, n), "segs": segs, "fill": None, "evenodd": False, "o": 1.0,
             "stroke": {"c": _ink(Color.from_hex(ring["hex"])), "w": float(ring["width"]), "dash": None},
             "blur": float(ring["blur"])} for n, ring in enumerate(blur["rings"])]


def _mesh_items(fill, name: str) -> tuple:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (8) and (9): "Glow is a real soft blur, never a stack of hard
    bands", "Gradients are smooth, never flat bands".] A MeshFill as the layered file carries it — Illustrator's
    scripting cannot make a gradient mesh: each patch its own small path (grown ``MESH_OVERLAP_MM`` under the shape's
    clip, so no hairline shows between neighbours) painted with ONE smooth linear gradient, the colour field fitted to
    its four corners (least squares), run along the field's own steepest way. ``(items, ΔE76 p95 of the fit against
    the mesh's own blend)`` — each patch read at ``MESH_SAMPLES`` x ``MESH_SAMPLES`` points."""
    import math

    import numpy as np

    from apps.ire.graph import Color
    items, errors = [], []
    for k, p in enumerate(fill.patches):
        pts = np.array([[float(p[2 * i]), float(p[2 * i + 1])] for i in range(4)])
        cols = np.array([[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)] for h in p[8:12]], float) / 255.0
        centre = pts.mean(axis=0)
        A = np.column_stack([np.ones(4), pts[:, 0] - centre[0], pts[:, 1] - centre[1]])
        coef, *_ = np.linalg.lstsq(A, cols, rcond=None)             # c = c0 + gx·dx + gy·dy, per channel
        lum = np.array([0.299, 0.587, 0.114])
        gx, gy = float(coef[1] @ lum), float(coef[2] @ lum)
        steep = math.hypot(gx, gy)
        if steep < 1e-9:                                             # one colour: its mean, solid
            ux, uy = 1.0, 0.0
        else:
            ux, uy = gx / steep, gy / steep
        t = (pts - centre) @ np.array([ux, uy])
        t0, t1 = float(t.min()), float(t.max())

        def at(tt):
            c = coef[0] + coef[1] * ux * tt + coef[2] * uy * tt
            return Color(r=float(min(1.0, max(0.0, c[0]))), g=float(min(1.0, max(0.0, c[1]))),
                         b=float(min(1.0, max(0.0, c[2]))))
        start, end = at(t0), at(t1)
        grown = [centre + (q - centre) * (1.0 + MESH_OVERLAP_MM / max(np.linalg.norm(q - centre), 1e-6)) for q in pts]
        segs = [["M", float(grown[0][0]), float(grown[0][1])]] + [["L", float(q[0]), float(q[1])] for q in grown[1:]] \
            + [["Z"]]
        items.append({"t": "p", "name": "%s-patch-%d" % (name, k), "segs": segs, "stroke": None, "evenodd": False,
                      "o": 1.0, "fill": {"c": _ink(at(0.0)), "o": 1.0, "grad": {
                          "kind": "linear", "stops": [[0.0, _ink(start)], [1.0, _ink(end)]],
                          "from": [float(centre[0] + ux * t0), float(centre[1] + uy * t0)],
                          "to": [float(centre[0] + ux * t1), float(centre[1] + uy * t1)],
                          "centre": [float(centre[0]), float(centre[1])], "r": 0.0}}})
        # its error: the mesh's own blend (bilinear between the corners) against the fitted run, inside the patch
        for i in range(MESH_SAMPLES):
            for j in range(MESH_SAMPLES):
                s, u = (i + 0.5) / MESH_SAMPLES, (j + 0.5) / MESH_SAMPLES
                w = np.array([(1 - s) * (1 - u), s * (1 - u), s * u, (1 - s) * u])
                q = w @ pts
                want = w @ cols
                tt = float((q - centre) @ np.array([ux, uy]))
                got = np.clip(coef[0] + coef[1] * ux * tt + coef[2] * uy * tt, 0.0, 1.0)
                errors.append(math.dist(_lab(want), _lab(got)))
    p95 = float(np.percentile(errors, 95)) if errors else 0.0
    return items, p95


def _fill(fill):
    if fill is None:
        return None
    kind = getattr(fill, "type", "solid")
    if kind == "solid":
        return {"c": _ink(fill.color), "o": fill.opacity}
    if kind == "gradient":
        # its stops, its run (linear: from (x1, y1) to (x2, y2); radial: about (cx, cy) to r), mm in the document
        return {"c": _ink(fill.stops[0].color), "o": 1.0,
                "grad": {"kind": fill.kind, "stops": [[s.offset, _ink(s.color)] for s in fill.stops],
                         "from": [fill.x1, fill.y1], "to": [fill.x2, fill.y2], "centre": [fill.cx, fill.cy],
                         "r": fill.r}}
    return {"c": _ink(fill.color), "o": getattr(fill, "opacity", 1.0)}


def _stroke(stroke):
    if stroke is None:
        return None
    return {"c": _ink(stroke.color), "w": stroke.width_mm, "dash": list(stroke.dash) if stroke.dash else None}


def _font(name: str, fonts: dict) -> str:
    """The PostScript name Illustrator sets ``name`` in — a role resolved through the document's faces first."""
    face = fonts.get(name, name)
    return POSTSCRIPT.get(face, face)


def _label_nodes(node, fonts: dict, keep_marks: bool) -> list:
    """A sticker bridge as the label's pieces — planned exactly as the PDF draws it (``draw_info_panel``)."""
    from reportlab.lib.units import mm

    from apps.dielines.exporters import label_layout as LL
    from apps.dielines.exporters.info_panel import _resolve_arabic_font_for_label
    layout = node.layout or {}
    if not layout:
        return []
    f = {"regular": fonts.get("regular", "NotoSans"), "bold": fonts.get("bold", "NotoSans-Bold"),
         "arabic": _resolve_arabic_font_for_label()}         # [his goal of 2026-10-06, item 6] its Bold added by the plan
    dx, dy, rw, rh = (float(v) for v in layout["region_mm"])
    plan = LL.plan_label(node.info, rw * mm, rh * mm, f, panel_w=node.w * mm, tail=layout.get("tail", True),
                         languages=layout.get("languages", LL.LANGUAGES), title=bool(layout.get("title")),
                         band=bool(layout.get("band")), keep_marks=keep_marks, levels=layout.get("levels"))
    return LL.plan_to_nodes(plan, node.x + dx, node.y + dy, node.info, node.ink or "#3F2620", name=node.name,
                            paper=node.ground)


# --- [his bug on design 124, 2026-10-12: "the layered Illustrator file must carry EVERY drawn element"] what the PDF
# --- draws that Illustrator has no node for, carried as the PDF draws it: a barcode's bars and digits, a pattern's
# --- marks inside its shape, a soft shadow's copies; a blend mode set on the item; a fade Illustrator's scripting
# --- cannot make (an opacity mask) named, the element carried at its full strength

_K = 0.5522847498


def _circle(cx: float, cy: float, r: float) -> list:
    """A circle as four cubic arcs, mm in the document."""
    k = _K * r
    return [["M", cx + r, cy], ["C", cx + r, cy + k, cx + k, cy + r, cx, cy + r],
            ["C", cx - k, cy + r, cx - r, cy + k, cx - r, cy], ["C", cx - r, cy - k, cx - k, cy - r, cx, cy - r],
            ["C", cx + k, cy - r, cx + r, cy - k, cx + r, cy], ["Z"]]


def _pattern_marks(fill, box: tuple, name: str) -> list:
    """A pattern's marks as the PDF paints them (``pdf_ai._paint_pattern``), each a named path in the fill's one
    colour: lines and crosshatch, rings and grain stroked at its weight; dots filled at its diameter."""
    import math
    import random
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return []
    ink = _ink(fill.color)
    stroke = {"c": ink, "w": fill.weight_mm, "dash": None}
    step = fill.spacing_mm
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    reach = math.hypot(w, h) / 2.0
    segs = []
    if fill.kind in ("lines", "crosshatch"):
        for angle in ((fill.angle_deg,) if fill.kind == "lines" else (fill.angle_deg, fill.angle_deg + 90.0)):
            a = math.radians(angle)
            dx, dy = math.cos(a), math.sin(a)
            nx, ny = -dy, dx
            k = -reach
            while k <= reach:
                px, py = cx + nx * k, cy + ny * k
                segs += [["M", px - dx * reach, py - dy * reach], ["L", px + dx * reach, py + dy * reach]]
                k += step
    elif fill.kind == "rings":
        r = step
        while r <= reach:
            segs += _circle(cx, cy, r)
            r += step
    elif fill.kind == "dots":
        row, y = 0, y0
        while y <= y1 + step:
            x = x0 + (step / 2.0 if row % 2 else 0.0)
            while x <= x1 + step:
                segs += _circle(x, y, fill.weight_mm / 2.0)
                x += step
            y += step * 0.866
            row += 1
        return [{"t": "p", "name": name + "-dots", "segs": segs, "fill": {"c": ink, "o": fill.opacity},
                 "stroke": None, "evenodd": False, "o": fill.opacity}]
    else:
        rng = random.Random(fill.seed)
        for _ in range(max(1, int(w * h / (step * step)))):
            gx, gy = x0 + rng.random() * w, y0 + rng.random() * h
            a = rng.random() * math.pi
            half = step * 0.25
            segs += [["M", gx - math.cos(a) * half, gy - math.sin(a) * half],
                     ["L", gx + math.cos(a) * half, gy + math.sin(a) * half]]
    return [{"t": "p", "name": name + "-" + fill.kind, "segs": segs, "fill": None, "stroke": stroke,
             "evenodd": False, "o": fill.opacity}]


def _segments_box(segs: list) -> tuple:
    xs = [v for s in segs for v in s[1::2] if s[0] != "Z"]
    ys = [v for s in segs for v in s[2::2] if s[0] != "Z"]
    return min(xs), min(ys), max(xs), max(ys)


def _patterned(node, item: dict) -> dict:
    """A pattern-filled shape as the PDF draws it: its marks, masked to the shape; then the shape's own stroke."""
    shape = item["segs"] if item["t"] == "p" else _segs(_rect_shape(node))
    group = {"t": "g", "name": item["name"], "o": item["o"], "clip": shape,
             "kids": _pattern_marks(node.fill, _segments_box(shape), item["name"] + "-pattern")}
    if item.get("stroke"):
        outline = {"t": "p", "name": item["name"] + "-outline", "segs": shape, "fill": None, "stroke": item["stroke"],
                   "evenodd": item.get("evenodd", True), "o": item["o"] * node.stroke.opacity}
        return {"t": "g", "name": item["name"], "o": 1.0, "clip": None,
                "kids": [dict(group, name=item["name"] + "-fill"), outline]}
    return group


def _paint_alpha(fill) -> float:
    """A fill's own strength as the drawing paints it: a solid's opacity, a gradient's strongest stop's (``pdf_ai``
    paints the shading at its stops' highest opacity)."""
    if getattr(fill, "type", "solid") == "gradient":
        return max(s.opacity for s in fill.stops)
    return getattr(fill, "opacity", 1.0)


def _painted(node, item: dict) -> dict:
    """A shape at the strength the drawing paints it: its fill at the fill's opacity, its stroke at the stroke's — one
    item where the two agree, else its fill and its stroke apart, each at its own (Illustrator's scripting sets an
    item's opacity, not its fill's or its stroke's)."""
    fa = _paint_alpha(node.fill) if item.get("fill") else None
    sa = node.stroke.opacity if item.get("stroke") else None
    if fa is not None and sa is not None and abs(fa - sa) > 1e-6:
        return {"t": "g", "name": item["name"], "o": 1.0, "clip": None,
                "kids": [dict(item, name=item["name"] + "-fill", stroke=None, o=item["o"] * fa),
                         dict(item, name=item["name"] + "-stroke", fill=None, o=item["o"] * sa)]}
    return dict(item, o=item["o"] * (fa if fa is not None else sa if sa is not None else 1.0))


def _rect_shape(node):
    from apps.ire.emitters.pdf_ai import _rect_segments
    return _rect_segments(node)


def _shadow_items(node, name: str) -> list:
    """A soft shadow as the PDF draws it (``pdf_ai._draw_soft_shadow``): each silhouette offset, drawn in eight steps,
    each at an eighth of its opacity, filled and stroked at a weight narrowing from twice its blur."""
    from apps.ire.emitters.pdf_ai import _SHADOW_STEPS, _shadow_shapes
    shadow = node.shadow
    ink = _ink(shadow.color)
    step_alpha = shadow.opacity / _SHADOW_STEPS
    out = []
    for n, segments in enumerate(_shadow_shapes(node)):
        moved = []
        for s in _segs(segments):
            if s[0] == "C":
                moved.append(["C", s[1] + shadow.offset_x_mm, s[2] + shadow.offset_y_mm, s[3] + shadow.offset_x_mm,
                              s[4] + shadow.offset_y_mm, s[5] + shadow.offset_x_mm, s[6] + shadow.offset_y_mm])
            elif s[0] in ("M", "L"):
                moved.append([s[0], s[1] + shadow.offset_x_mm, s[2] + shadow.offset_y_mm])
            else:
                moved.append(s)
        for i in range(_SHADOW_STEPS):
            width = max(shadow.blur_mm * 2.0 * (1.0 - i / _SHADOW_STEPS), 0.01)
            out.append({"t": "p", "name": "%s-shadow-%d-%d" % (name, n, i), "segs": moved,
                        "fill": {"c": ink, "o": step_alpha}, "stroke": {"c": ink, "w": width, "dash": None},
                        "evenodd": False, "o": step_alpha})
    return out


def _barcode_items(node, name: str) -> list:
    """A barcode as the PDF draws it (``pdf_ai._draw_barcode``): its bars, its modules and its digits, in black ink."""
    from reportlab.graphics.shapes import Drawing, Group as RG, Polygon, Rect as RR, String as RS, mmult
    from reportlab.lib.units import mm
    ink = [0.0, 0.0, 0.0, 1.0]
    if node.symbology == "ean13":
        from reportlab.graphics.barcode import createBarcodeDrawing
        digits = "".join(ch for ch in node.value if ch.isdigit())
        if len(digits) not in (12, 13):
            return []
        d = createBarcodeDrawing("EAN13", value=digits, barHeight=node.h * mm, humanReadable=True)
        sc = (node.w * mm) / d.width if d.width else 1.0
        base = (sc, 0, 0, sc, 0, 0)
    else:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        q = QrCodeWidget(node.value)
        b = q.getBounds()
        side = min(node.w, node.h) * mm
        d = Drawing(side, side, transform=[side / (b[2] - b[0]), 0, 0, side / (b[3] - b[1]), 0, 0])
        d.add(q)
        base = (1, 0, 0, 1, 0, 0)
    out = []

    def at(t, px, py):
        return node.x + (t[0] * px + t[2] * py + t[4]) / mm, node.y + node.h - (t[1] * px + t[3] * py + t[5]) / mm

    def walk(g, t):
        for ch in g.contents:
            if isinstance(ch, RG):
                walk(ch, mmult(t, ch.transform))
            elif isinstance(ch, RR):
                pts = [at(t, ch.x, ch.y), at(t, ch.x + ch.width, ch.y), at(t, ch.x + ch.width, ch.y + ch.height),
                       at(t, ch.x, ch.y + ch.height)]
                out.append({"t": "p", "name": "%s-bar-%d" % (name, len(out)), "evenodd": False, "o": 1.0,
                            "segs": [["M", *pts[0]], ["L", *pts[1]], ["L", *pts[2]], ["L", *pts[3]], ["Z"]],
                            "fill": {"c": ink, "o": 1.0}, "stroke": None})
            elif isinstance(ch, Polygon):
                p = ch.points
                pts = [at(t, p[i], p[i + 1]) for i in range(0, len(p), 2)]
                out.append({"t": "p", "name": "%s-bar-%d" % (name, len(out)), "evenodd": False, "o": 1.0,
                            "segs": [["M", *pts[0]]] + [["L", *q] for q in pts[1:]] + [["Z"]],
                            "fill": {"c": ink, "o": 1.0}, "stroke": None})
            elif isinstance(ch, RS) and str(ch.text).strip():
                x, y = at(t, ch.x, ch.y)
                align = {"middle": "center", "end": "right"}.get(getattr(ch, "textAnchor", "start"), "left")
                out.append({"t": "x", "name": "%s-digits-%d" % (name, len(out)), "text": str(ch.text), "x": x, "y": y,
                            "size": float(ch.fontSize) * abs(t[3]), "font": "Helvetica", "c": ink, "align": align,
                            "rtl": False, "rot": 0.0, "bold": False, "track": 0.0, "o": 1.0})
    flat = d.expandUserNodes()
    walk(flat, mmult(base, getattr(flat, "transform", (1, 0, 0, 1, 0, 0))))
    return out


def _item(node, ox: float, fonts: dict, keep_marks: bool, skipped: list, effects: list | None = None):
    """One graph node as the script's data — its soft shadow under it and its blend mode on it, as the PDF draws them
    (``_carried``); None for what the native file does not carry (a raster, said in ``skipped``)."""
    effects = effects if effects is not None else []
    item = _bare_item(node, ox, fonts, keep_marks, skipped, effects)
    if item is None:
        return None
    return _carried(node, item, effects)


def _carried(node, item: dict, effects: list) -> dict:
    name = item["name"]
    if getattr(node, "opacity_mask", None) is not None:
        effects.append("%s: its fade (an opacity mask Illustrator's scripting cannot make) — carried at full strength"
                       % name)
    if getattr(node, "blend_mode", None):
        item = dict(item, blend=node.blend_mode)
    if getattr(node, "shadow", None) is not None:
        return {"t": "g", "name": name + "-with-shadow", "o": 1.0, "clip": None,
                "kids": [{"t": "g", "name": name + "-shadow", "o": 1.0, "clip": None,
                          "kids": _shadow_items(node, name)}, item]}
    return item


def _bare_item(node, ox: float, fonts: dict, keep_marks: bool, skipped: list, effects: list):
    from apps.ire.emitters.pdf_ai import _INK_FINISHES
    from apps.ire.graph import Barcode, Group, Image, MeshFill, Path, PatternFill, Rect, StickerBridge, TextRun
    name = getattr(node, "name", "") or ""
    ink = next((f for f in getattr(node, "finishes", None) or [] if f.kind in _INK_FINISHES), None)
    if isinstance(node, (Path, Rect)) and node.finishes:
        # page 1 as the drawing depicts its finishes: the element in its metal, its clear finishes over it
        twin = _ink_twin(node, ink) if ink is not None else node.model_copy(update={"finishes": []})
        item = _bare_item(twin, ox, fonts, keep_marks, skipped, effects) if twin is not None else None
        return _finished(node, item, node.finishes) if item is not None else None
    if isinstance(node, Group):
        kids = [i for i in (_item(c, ox, fonts, keep_marks, skipped, effects) for c in node.children) if i]
        if node.clip is not None:
            # a clear finish on a clipped group floods its region: depicted over what it holds, inside its mask
            kids += [d for f in node.finishes for d in _depiction(f, node.clip, name)]
        if not kids:
            return None            # a group that draws nothing: never a mask over nothing (his bug on 124's file)
        group = {"t": "g", "name": name, "kids": kids, "o": node.opacity,
                 "clip": _segs(node.clip) if node.clip else None}
        # [his goal of 2026-10-13, (2)] laid out in its own frame and turned onto the page: every point turned here, as
        # the drawing turns them, so Illustrator draws it where the drawing does
        return _turn_item(group, node.turn) if getattr(node, "turn", None) is not None else group
    if isinstance(node, StickerBridge):
        from apps.ire.graph import Group as G
        return _item(G(name=name, role="info", children=_label_nodes(node, fonts, keep_marks)), ox, fonts, keep_marks,
                     skipped, effects)
    if isinstance(node, Path) and isinstance(node.fill, MeshFill) and node.fill.grid:
        # [his goal of 2026-10-13, (9)] a field read on a grid: thin strips inside its own outline, each one smooth
        # gradient across — the form Illustrator draws as the drawing does (a gradient run across its own strip)
        strips, p95 = _strip_items(node.fill.grid, name)
        effects.append("%s: its smooth colour field carried as %d thin strips, each a smooth gradient across it, within "
                       "ΔE %.1f (p95) of the drawing — Illustrator's scripting cannot make a gradient mesh"
                       % (name, len(strips), p95))
        return {"t": "g", "name": name, "o": node.opacity, "clip": _segs(node.segments), "kids": strips}
    if isinstance(node, Path) and isinstance(node.fill, MeshFill) and node.fill.blur:
        # [his goal of 2026-10-13, (8): "Glow is a real soft blur"] a glow round a line: its bands as strokes along the
        # line under Illustrator's own Gaussian blur, the widest first — a real blur, live in the file
        return {"t": "g", "name": name, "o": node.opacity, "clip": None, "kids": _blur_items(node.fill.blur, name)}
    if isinstance(node, Path) and isinstance(node.fill, MeshFill):
        # [his goal of 2026-10-13, (8) and (9)] its smooth field as small smooth gradients inside its own outline
        patches, p95 = _mesh_items(node.fill, name)
        effects.append("%s: its smooth colour field carried as %d small smooth gradients, within ΔE %.1f (p95) of the "
                       "drawing — Illustrator's scripting cannot make a gradient mesh" % (name, len(patches), p95))
        return {"t": "g", "name": name, "o": node.opacity, "clip": _segs(node.segments), "kids": patches}
    if isinstance(node, Path):
        item = {"t": "p", "name": name, "segs": _segs(node.segments), "fill": _fill(node.fill),
                "stroke": _stroke(node.stroke), "evenodd": node.fill_rule != "nonzero", "o": node.opacity}
        return _patterned(node, item) if isinstance(node.fill, PatternFill) else _painted(node, item)
    if isinstance(node, Rect):
        item = {"t": "r", "name": name, "x": node.x, "y": node.y, "w": node.w, "h": node.h, "r": node.radius_mm,
                "fill": _fill(node.fill), "stroke": _stroke(node.stroke), "o": node.opacity}
        return _patterned(node, item) if isinstance(node.fill, PatternFill) else _painted(node, item)
    if isinstance(node, TextRun):
        text = node.text.upper() if node.text_case == "upper" else node.text
        colour = ink.appearance if (ink is not None and ink.appearance is not None) else node.color   # in its metal
        item = {"t": "x", "name": name, "text": text, "x": node.x, "y": node.y, "size": node.size_pt,
                "font": _font(node.font or "regular", fonts), "c": _ink(colour), "align": node.align,
                "rtl": bool(node.rtl), "rot": node.rotation_deg, "bold": name.endswith("-head-bold"),
                "track": node.tracking_em or 0.0, "o": node.opacity}
        from apps.ire.estimated_sign import SIGN, pieces
        face = fonts.get(node.font or "regular", fonts.get("regular"))
        if SIGN in text and not node.rotation_deg and face:
            # [his goal of 2026-10-10, item 8: "The ℮ prints as a plain "e": it must be the real estimated sign everywhere."] the run's words at their places and each ℮ as the sign's own
            # outline, laid out as the PDF draws them — never the face's "e"
            kids = []
            for k, piece in enumerate(pieces(text, node.x, node.y, node.size_pt, face, node.align)):
                if piece[0] == "text":
                    kids.append(dict(item, name="%s-%d" % (name, k), text=piece[1], x=piece[2], align="left"))
                    continue
                segs = []
                for op in piece[1]:
                    if op[0] == "M":
                        segs.append(["M", op[1], op[2]])
                    elif op[0] == "L":
                        segs.append(["L", op[1], op[2]])
                    elif op[0] == "C":
                        segs.append(["C", op[1], op[2], op[3], op[4], op[5], op[6]])
                    else:
                        segs.append(["Z"])
                kids.append({"t": "p", "name": "%s-estimated-sign-%d" % (name, k), "segs": segs,
                             "fill": {"c": _ink(node.color), "o": 1.0}, "stroke": None, "evenodd": False,
                             "o": node.opacity})
            return {"t": "g", "name": name, "kids": kids, "o": 1.0, "clip": None}
        return item
    if isinstance(node, Barcode):
        bars = _barcode_items(node, name)
        return {"t": "g", "name": name, "o": node.opacity, "clip": None, "kids": bars} if bars else None
    if isinstance(node, Image):
        # [his bug on design 124: "EVERY drawn element"] a picture placed and embedded where the drawing draws it, at
        # its size, masked where the drawing masks it
        item = {"t": "i", "name": name, "src": node.src, "x": node.x, "y": node.y, "w": node.w, "h": node.h,
                "o": node.opacity}
        return {"t": "g", "name": name + "-masked", "o": 1.0, "clip": _segs(node.clip), "kids": [item]} \
            if node.clip else item
    return None


# --- [his bug on design 124, 2026-10-12: "the layered Illustrator file must carry EVERY drawn element, each on its
# --- named layer"] the finishes as the drawing prints them (``pdf_ai``, §BH65(c)2): page 1 DEPICTS each — an ink
# --- finish paints its element in its metal, a gloss is a highlight across the element's upper quarter, a relief its
# --- outline lit and shadowed — and every finish's PLATE follows the artwork, each on its own artboard and its own
# --- named layer, a 100 % mask in a spot colour of its name, cut by the masks its elements were cut by, in register

def _resolved_finishes(node, inherited=()):
    """The node with every finish that reaches it on itself, as the drawing works them out (``_finishes_in_force``):
    a leaf's own and every enclosing group's, one per plate; a clipped group keeps its CLEAR finishes as a flood over
    its region and hands every other on to what it holds."""
    from apps.ire.emitters.pdf_ai import _INK_FINISHES
    from apps.ire.graph import Group
    if isinstance(node, Group):
        clipped = node.clip is not None
        floods = [f for f in node.finishes if clipped and f.kind not in _INK_FINISHES]
        reaches = [f for f in node.finishes if f not in floods]
        kids = [_resolved_finishes(c, list(inherited) + reaches) for c in node.children]
        return node.model_copy(update={"children": kids, "finishes": floods})
    if not hasattr(node, "finishes"):
        return node
    out, seen = [], set()
    for finish in list(node.finishes) + list(reversed(list(inherited))):
        if finish.plate not in seen:
            seen.add(finish.plate)
            out.append(finish)
    return node.model_copy(update={"finishes": out}) if out != list(node.finishes) else node


def _has_finishes(node) -> bool:
    return bool(getattr(node, "finishes", None)) or any(_has_finishes(c) for c in getattr(node, "children", None) or [])


def _ink_twin(node, ink):
    """An element an ink finish paints, as page 1 draws it (``pdf_ai._draw_ink_finished``): its fill and its stroke in
    the finish's metal, its geometry and its stroke's weight kept; None where nothing paints it."""
    from apps.ire.graph import GradientFill, SolidFill, Stroke
    paint = ink.appearance or (node.fill.color if isinstance(node.fill, SolidFill) else None)
    if paint is None and isinstance(node.fill, GradientFill):
        # [His goal after the pitch page, 2026-10-15, A (2)] a metal part's light, drawn as drawn (``pdf_ai``'s twin)
        return node.model_copy(update={"finishes": []})
    if paint is None and node.stroke is not None:
        paint = node.stroke.color
    if paint is None:
        return None
    fill = SolidFill(color=paint, opacity=getattr(node.fill, "opacity", 1.0)) if node.fill is not None else None
    stroke = (Stroke(color=paint, width_mm=node.stroke.width_mm, dash=node.stroke.dash, opacity=node.stroke.opacity)
              if node.stroke is not None else None)
    return node.model_copy(update={"fill": fill, "stroke": stroke, "finishes": []})


def _depiction(finish, segments, name: str) -> list:
    """Page 1's depiction of a clear finish over ``segments`` (``pdf_ai._depict_clear_finish``): a gloss a white
    highlight across the upper quarter of the element's box, inside the element; a relief its outline lit from the
    upper left and shadowed to the lower right (reversed for a deboss); a matte laminate none."""
    from apps.ire.emitters.pdf_ai import _RELIEF, _RELIEF_OFFSET_MM, _SHEEN
    from apps.ire.graph import Color
    kind = finish.kind
    if kind not in _SHEEN and kind not in _RELIEF:
        return []
    xs = [v for s in segments for v in (getattr(s, "x", None), getattr(s, "x1", None), getattr(s, "x2", None))
          if v is not None]
    ys = [v for s in segments for v in (getattr(s, "y", None), getattr(s, "y1", None), getattr(s, "y2", None))
          if v is not None]
    if not xs or not ys:
        return []
    if kind in _SHEEN:
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        band = (y1 - y0) * 0.25
        light = {"t": "p", "name": "%s-%s-highlight" % (name, kind), "segs": [["M", x0, y0], ["L", x1, y0],
                 ["L", x0, y0 + band * 2.0], ["Z"]], "fill": {"c": _ink(Color.from_hex("#FFFFFF")), "o": 0.14},
                 "stroke": None, "evenodd": False, "o": 0.14}
        return [{"t": "g", "name": "%s-%s" % (name, kind), "o": 1.0, "clip": _segs(segments), "kids": [light]}]
    sign, out = _RELIEF[kind], []
    for dx, hex_, alpha, side in ((-_RELIEF_OFFSET_MM * sign, "#FFFFFF", 0.55, "lit"),
                                  (_RELIEF_OFFSET_MM * sign, "#000000", 0.22, "shadowed")):
        segs = []
        for s in segments:
            if s.op == "M":
                segs.append(["M", s.x + dx, s.y + dx])
            elif s.op == "L":
                segs.append(["L", s.x + dx, s.y + dx])
            elif s.op == "C":
                segs.append(["C", s.x1 + dx, s.y1 + dx, s.x2 + dx, s.y2 + dx, s.x + dx, s.y + dx])
            elif s.op == "Z":
                segs.append(["Z"])
        out.append({"t": "p", "name": "%s-%s-%s" % (name, kind, side), "segs": segs, "fill": None,
                    "stroke": {"c": _ink(Color.from_hex(hex_)), "w": 0.3, "dash": None}, "evenodd": False,
                    "o": alpha})
    return out


def _finished(node, item: dict, finishes: list) -> dict:
    """An element with its clear finishes' depictions drawn over it, as page 1 draws them."""
    from apps.ire.emitters.pdf_ai import _INK_FINISHES, _rect_segments
    segments = node.segments if hasattr(node, "segments") else _rect_segments(node)
    shown = [d for f in finishes if f.kind not in _INK_FINISHES for d in _depiction(f, segments, item["name"])]
    if not shown:
        return item
    return {"t": "g", "name": item["name"] + "-finished", "o": 1.0, "clip": None, "kids": [item] + shown}


def _plates(roots) -> dict:
    """``{plate: {"kind", "items": [(node, clips, region)]}}`` in the order the drawing meets them
    (``pdf_ai._collect_plate``) — the roots' finishes resolved."""
    from apps.ire.graph import Group, Path, Rect, TextRun
    plates: dict = {}

    def collect(node, finish, clips, region=None):
        entry = plates.setdefault(finish.plate, {"kind": finish.kind, "items": []})
        entry["items"].append((node, list(clips), region))

    def walk(node, clips):
        if isinstance(node, Group):
            inner = clips + [node.clip] if node.clip is not None else clips
            for child in node.children:
                walk(child, inner)
            for finish in node.finishes:
                collect(node, finish, clips, region=node.clip)
        elif isinstance(node, (Rect, Path, TextRun)):
            for finish in node.finishes:
                collect(node, finish, clips)

    for root in roots:
        for child in root.children:
            walk(child, [])
    return plates


def _plate_boards(roots, first: int, page_w: float, fonts: dict, keep_marks: bool) -> list:
    """Every plate on its own artboard after the artwork (``pdf_ai._draw_finish_plates``): its own named layer; each
    element it covers a 100 % mask in the plate's spot colour, cut by the masks it was cut by — a flood its region, a
    line of words its words, a stroked line its line — and the plate's name in its corner."""
    from apps.ire.emitters.pdf_ai import _rect_segments
    from apps.ire.graph import Color, TextRun
    black = _ink(Color.from_hex("#000000"))
    boards = []
    for k, (plate, entry) in enumerate(_plates(roots).items()):
        mask = {"c": black, "o": 1.0, "spot": plate}
        items = []
        for node, clips, region in entry["items"]:
            name = "%s-%s" % (getattr(node, "name", "") or type(node).__name__, plate.lower())
            if region is not None:
                item = {"t": "p", "name": name, "segs": _segs(region), "fill": mask, "stroke": None, "evenodd": True,
                        "o": 1.0}
            elif isinstance(node, TextRun):
                twin = node.model_copy(update={"color": Color.from_hex("#000000"), "finishes": [], "opacity": 1.0,
                                               "blend_mode": None, "shadow": None})
                item = dict(_bare_item(twin, 0.0, fonts, keep_marks, [], []), name=name, spot=plate)
            else:
                segments = node.segments if hasattr(node, "segments") else _rect_segments(node)
                stroked = getattr(node, "fill", None) is None and getattr(node, "stroke", None) is not None
                item = {"t": "p", "name": name, "segs": _segs(segments), "o": 1.0,
                        "fill": None if stroked else mask, "evenodd": getattr(node, "fill_rule", None) != "nonzero",
                        "stroke": {"c": black, "w": node.stroke.width_mm, "dash": None, "spot": plate}
                        if stroked else None}
            for j, clip in enumerate(reversed(clips)):
                item = {"t": "g", "name": "%s-cut-%d" % (name, j), "o": 1.0, "clip": _segs(clip), "kids": [item]}
            items.append(item)
        label = "FINISH PLATE %s - %s - IN REGISTER WITH PAGE 1" % (plate, entry["kind"].upper())
        items.append({"t": "x", "name": "finish-plate-label-" + plate.lower(), "text": label, "x": 4.0, "y": 6.0,
                      "size": 6.0, "font": _font("regular", fonts), "c": black, "align": "left", "rtl": False,
                      "rot": 0.0, "bold": False, "track": 0.0, "o": 1.0})
        board = "FINISH PLATE " + plate
        boards.append({"name": board, "ox": (first + k) * (page_w + ARTBOARD_GAP_MM),
                       "layers": [{"name": board, "items": items}]})
    return boards


def _not_drawn(doc) -> set:
    """The rasters the drawing does not draw (``pdf_ai._draw_image``): one resolved REFERENCE for this output
    (``materials_placement.refuse_or_skip``'s skip), one whose file is not on this machine."""
    from apps.ire.graph import Image
    from apps.ire.materials_placement import RESOLVED_REFERENCE_NO_VISIBLE_CREDIT, resolve_placements
    skip = {r["node"] for r in resolve_placements(doc)["rows"]
            if r["resolution"] == RESOLVED_REFERENCE_NO_VISIBLE_CREDIT}

    def found(node):
        if isinstance(node, Image):
            return [node.name] if (node.name in skip or not os.path.exists(node.src)) else []
        return [n for child in getattr(node, "children", None) or [] for n in found(child)]
    return {n for root in (doc.root, doc.inside) if root is not None for n in found(root)}


def _without(node, names: set):
    """The node with the rasters ``names`` left out, as the drawing leaves them out."""
    from apps.ire.graph import Group, Image
    if isinstance(node, Group):
        kids = [_without(c, names) for c in node.children if not (isinstance(c, Image) and c.name in names)]
        return node.model_copy(update={"children": kids})
    return node


def document_fonts(doc) -> dict:
    """``{role: face}`` — the faces the PDF emitter draws ``doc`` with (``emit_pdf_ai``'s own resolution, role by role),
    so the native file sets each line in the face its PDF does."""
    from apps.ire.font_roles import is_exempt, legacy_emitter_fonts, legacy_role_map, resolve_document, theme_faces
    if is_exempt(doc):
        return dict(legacy_emitter_fonts(doc))
    fonts = {role: label for role, (label, _p) in theme_faces()["faces"].items()}
    fonts.update({role: label for role, (label, _p) in resolve_document(doc)["faces"].items()})
    if (doc.metadata or {}).get("confirmed_font"):
        legacy = legacy_role_map(doc.metadata)
        if "bold" in legacy:
            fonts["bold"] = fonts["display"] = legacy["bold"][0]
    return fonts


def tree(doc, *, fonts: dict | None = None) -> dict:
    """The document as the script's data: its artboards, each its layers (in LAYERS' order), each layer its items — in
    RGB as the drawing paints it, or in CMYK through his printer's profile where one is set (``space``, ``profile``)."""
    profile = press_profile()
    token = _SPACE.set(_through(profile) if profile else None)
    try:
        return dict(_tree(doc, fonts=fonts), space="CMYK" if profile else "RGB", profile=profile)
    finally:
        _SPACE.reset(token)


def _tree(doc, *, fonts: dict | None = None) -> dict:
    from apps.ire import brand_mark
    from apps.ire.emitters.pdf_ai import ARABIC_MARKS_KEY
    fonts = fonts or document_fonts(doc)
    doc = brand_mark.expand(doc)
    from apps.ire.materials_placement import refuse_or_skip
    from apps.ire.materials_paths import resolved_document_images
    material_skip, _ = refuse_or_skip(doc)
    doc = resolved_document_images(doc, skip=material_skip)
    keep = bool((doc.metadata or {}).get(ARABIC_MARKS_KEY))
    skipped: list = []
    effects: list = []
    boards = []
    roots = [r for r in (doc.root, doc.inside) if r is not None]
    absent = _not_drawn(doc)
    if absent:
        skipped += sorted(absent)            # the drawing does not draw them either
        roots = [_without(r, absent) for r in roots]
    if any(_has_finishes(r) for r in roots):
        roots = [_resolved_finishes(r) for r in roots]
    board_names = (doc.metadata or {}).get("surface_names", ("OUTSIDE", "INSIDE"))
    if not isinstance(board_names, (list, tuple)) or len(board_names) != 2 or not all(isinstance(name, str) and name.strip() for name in board_names):
        raise ValueError("Two named surface artboards are required.")
    for board, root, ox in zip(board_names, roots, (0.0, doc.page_w + ARTBOARD_GAP_MM)):
        layers = {name: [] for name in LAYERS}
        for child in root.children:
            layer = child.name if child.name in LAYERS else "ARTWORK"
            item = _item(child, ox, fonts, keep, skipped, effects)
            if item:
                layers[layer].append(item)
        boards.append({"name": board, "ox": ox, "layers": [{"name": n, "items": layers[n]} for n in LAYERS]})
    boards += _plate_boards(roots, len(boards), doc.page_w, fonts, keep)   # every finish's plate after the artwork
    used = sorted({i["font"] for b in boards for lay in b["layers"] for i in _walk(lay["items"]) if i["t"] == "x"})
    return {"w": doc.page_w, "h": doc.page_h, "boards": boards, "not_printing": list(NOT_PRINTING), "fonts": used,
            "skipped": skipped, "effects_not_carried": effects}


def _walk(items):
    for i in items:
        yield i
        if i["t"] == "g":
            yield from _walk(i["kids"])


_RUNTIME = r"""
var MM = 2.834645669291339;
var report = {status: "BUILT", artboards: 0, layers: [], groups: 0, paths: 0, texts: 0, clips: 0, gradients: 0,
              blends: 0, images: 0, blurs: 0, missingFonts: [], errors: [], saved: false};
var _ui = null;
try { _ui = app.userInteractionLevel; app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS; } catch (e) {}
try { app.coordinateSystem = CoordinateSystem.DOCUMENTCOORDINATESYSTEM; } catch (e) {}
// a colour as the data writes it: three channels RGB (the drawing's own), four CMYK (his printer's profile's)
function ink(v) { if (v.length === 3) { var r = new RGBColor(); r.red = v[0] * 255; r.green = v[1] * 255;
                                          r.blue = v[2] * 255; return r; } return cmyk(v); }
function cmyk(v) { var c = new CMYKColor(); c.cyan = v[0] * 100; c.magenta = v[1] * 100; c.yellow = v[2] * 100;
                   c.black = v[3] * 100; return c; }
var doc = app.documents.add(D.space === "CMYK" ? DocumentColorSpace.CMYK : DocumentColorSpace.RGB, D.w * MM,
                            D.h * MM);
var R0 = doc.artboards[0].artboardRect;
var X0 = R0[0], Y0 = R0[1];
doc.artboards[0].name = D.boards[0].name;
for (var b = 1; b < D.boards.length; b++) {
    var left = X0 + D.boards[b].ox * MM;
    doc.artboards.add([left, Y0, left + D.w * MM, Y0 - D.h * MM]);
    doc.artboards[b].name = D.boards[b].name;
}
report.artboards = doc.artboards.length;
function spot(name, v) {
    var s = null;
    try { s = doc.spots.getByName(name); } catch (e) { s = doc.spots.add(); s.name = name; s.colorType = ColorModel.SPOT;
                                                      s.color = cmyk(v); }
    var sc = new SpotColor(); sc.spot = s; sc.tint = 100; return sc;
}
var SPOTS = {CUT: spot("CutContour", [0, 1, 0, 0]), CREASE: spot("Crease", [1, 0, 0, 0])};
var PLATE_INK = [0, 0, 0, 1];
var layerOf = {};
doc.layers[0].name = "ARTWORK"; layerOf.ARTWORK = doc.layers[0];
var _names = ["CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS"];
for (var i = 0; i < _names.length; i++) { var L = doc.layers.add(); L.name = _names[i]; layerOf[_names[i]] = L; }
for (var n = 0; n < D.not_printing.length; n++) { layerOf[D.not_printing[n]].printable = false; }
var OX = 0;
function P(x, y) { return [X0 + (x + OX) * MM, Y0 - y * MM]; }
function gradientColor(gr, item) {
    // the drawing's gradient as Illustrator's own: its stops in order, its run along the drawing's own line. Illustrator
    // runs a new gradient across the item's own box, left to right, whatever origin, angle or length it is given
    // (measured: 2026-10-14); the gradient alone turned, it spans the box's extent along its new angle about the box's
    // middle. So the gradient is turned to the drawing's angle (``turn``, applied once it is the item's fill) and its
    // stops are set where the drawing's run lies on that span — a run that starts or ends past the box keeps the colour
    // it has at the box's edge; a radial one is set to its radius about the box's middle
    var gb = item.geometricBounds;
    var W = gb[2] - gb[0], H = gb[1] - gb[3], cx = (gb[0] + gb[2]) / 2, cy = (gb[1] + gb[3]) / 2;
    var turn = 0, t0 = 0, t1 = 1;
    if (gr.kind === "radial") {
        var reach = Math.sqrt(W * W + H * H) / (2 * Math.SQRT2);
        if (reach > 1e-9) { t1 = gr.r * MM / reach; }
    } else {
        var a = P(gr.from[0], gr.from[1]), b = P(gr.to[0], gr.to[1]);
        var dx = b[0] - a[0], dy = b[1] - a[1], L = Math.sqrt(dx * dx + dy * dy);
        if (L > 1e-9) {
            var ux = dx / L, uy = dy / L, S = W * Math.abs(ux) + H * Math.abs(uy);
            turn = Math.atan2(dy, dx) * 180 / Math.PI;
            if (S > 1e-9) {
                var sx = cx - ux * S / 2, sy = cy - uy * S / 2;
                t0 = ((a[0] - sx) * ux + (a[1] - sy) * uy) / S;
                t1 = ((b[0] - sx) * ux + (b[1] - sy) * uy) / S;
            }
        }
    }
    var stops = placedStops(gr.stops, t0, t1);
    var g = doc.gradients.add();
    g.type = gr.kind === "radial" ? GradientType.RADIAL : GradientType.LINEAR;
    while (g.gradientStops.length < stops.length) { g.gradientStops.add(); }
    for (var i = 0; i < stops.length; i++) {
        var st = g.gradientStops[i]; st.color = ink(stops[i][1]); st.midPoint = 50;
        st.rampPoint = Math.max(0, Math.min(100, stops[i][0] * 100));
    }
    var gc = new GradientColor(); gc.gradient = g;
    return {gc: gc, turn: Math.abs(turn) > 1e-6 ? turn : 0};
}
function placedStops(stops, t0, t1) {
    // the stops of a run laid from t0 to t1 of its span (0 to 1 is the span itself): each at its place, those past
    // either end replaced by the colour the run has there — as the drawing pads its run past its ends
    if (Math.abs(t0) < 1e-6 && Math.abs(t1 - 1) < 1e-6) { return stops; }
    function mix(p, q, f) {
        var out = [];
        for (var k = 0; k < p.length; k++) { out.push(p[k] + (q[k] - p[k]) * f); }
        return out;
    }
    function colourAt(o) {
        if (o <= stops[0][0]) { return stops[0][1]; }
        for (var k = 1; k < stops.length; k++) {
            if (o <= stops[k][0]) {
                var span = stops[k][0] - stops[k - 1][0];
                return span > 1e-9 ? mix(stops[k - 1][1], stops[k][1], (o - stops[k - 1][0]) / span) : stops[k][1];
            }
        }
        return stops[stops.length - 1][1];
    }
    var d = t1 - t0, out = [];
    if (Math.abs(d) < 1e-9) { return [[0, colourAt(t0 <= 0 ? 1 : 0)], [1, colourAt(t0 <= 0 ? 1 : 0)]]; }
    // the run's own offset at the span's two ends, and every stop between them, in the span's order
    var ends = [(0 - t0) / d, (1 - t0) / d];
    out.push([0, colourAt(ends[0])]);
    var inner = [];
    for (var k = 0; k < stops.length; k++) {
        var at = t0 + stops[k][0] * d;
        if (at > 1e-6 && at < 1 - 1e-6) { inner.push([at, stops[k][1]]); }
    }
    inner.sort(function (p, q) { return p[0] - q[0]; });
    for (var m = 0; m < inner.length; m++) { out.push(inner[m]); }
    out.push([1, colourAt(ends[1])]);
    return out;
}
function paint(item, it, layer) {
    if (it.fill) {
        item.filled = true;
        var painted = false;
        if (it.fill.grad) {
            // Illustrator now and then refuses one gradient of many ('MRAP', a different strip each run): asked once
            // more; refused twice, it is said
            for (var tries = 0; tries < 2 && !painted; tries++) {
                try { var made = gradientColor(it.fill.grad, item); item.fillColor = made.gc;
                      if (made.turn) { item.rotate(made.turn, false, false, true, false, Transformation.CENTER); }
                      painted = true; report.gradients++; }
                catch (ge) { if (tries > 0) { report.errors.push(String(it.name || "item") + " gradient: " + ge); } }
            }
        }
        if (!painted) { item.fillColor = it.fill.spot ? spot(it.fill.spot, PLATE_INK) : ink(it.fill.c); }
    } else { item.filled = false; }
    if (it.stroke) {
        item.stroked = true;
        item.strokeColor = SPOTS[layer] ? SPOTS[layer] : (it.stroke.spot ? spot(it.stroke.spot, PLATE_INK)
                                                                         : ink(it.stroke.c));
        item.strokeWidth = it.stroke.w * MM;
        if (it.stroke.dash) { item.strokeDashes = [it.stroke.dash[0] * MM, it.stroke.dash[1] * MM]; }
        if (SPOTS[layer]) { item.strokeOverprint = true; }
    } else { item.stroked = false; }
    if (it.evenodd !== undefined) { try { item.evenodd = it.evenodd; } catch (e) {} }
}
function subpaths(segs) {
    var subs = [], cur = null;
    for (var i = 0; i < segs.length; i++) {
        var s = segs[i];
        if (s[0] === "M") { cur = {pts: [], closed: false}; subs.push(cur);
                            var m = P(s[1], s[2]); cur.pts.push({a: m, l: m, r: m}); }
        else if (s[0] === "L") { var l = P(s[1], s[2]); cur.pts.push({a: l, l: l, r: l}); }
        else if (s[0] === "C") { cur.pts[cur.pts.length - 1].r = P(s[1], s[2]);
                                 cur.pts.push({a: P(s[5], s[6]), l: P(s[3], s[4]), r: P(s[5], s[6])}); }
        else { cur.closed = true;
               if (cur.pts.length > 1) { var f0 = cur.pts[0], z = cur.pts[cur.pts.length - 1];
                   if (Math.abs(f0.a[0] - z.a[0]) < 0.001 && Math.abs(f0.a[1] - z.a[1]) < 0.001) { f0.l = z.l;
                                                                                               cur.pts.pop(); } } }
    }
    return subs;
}
function fill(pi, sp) {
    for (var k = 0; k < sp.pts.length; k++) { var pp = pi.pathPoints.add(); pp.anchor = sp.pts[k].a;
        pp.leftDirection = sp.pts[k].l; pp.rightDirection = sp.pts[k].r; pp.pointType = PointType.CORNER; }
    pi.closed = sp.closed;
}
var BLENDS = {"multiply": "MULTIPLY", "screen": "SCREEN", "overlay": "OVERLAY", "soft-light": "SOFTLIGHT",
              "hard-light": "HARDLIGHT", "darken": "DARKEN", "lighten": "LIGHTEN", "color-dodge": "COLORDODGE",
              "color-burn": "COLORBURN", "difference": "DIFFERENCE", "exclusion": "EXCLUSION"};
// [his goal of 2026-10-13, (8): "Glow is a real soft blur"] a glow's ring: round at its ends and joins, under
// Illustrator's own Gaussian blur, live
function soften(item, it) {
    try { item.strokeCap = StrokeCap.ROUNDENDCAP; item.strokeJoin = StrokeJoin.ROUNDENDJOIN; } catch (ce) {}
    try {
        item.applyEffect('<LiveEffect name="Adobe PSL Gaussian Blur"><Dict data="R blur ' + (it.blur * MM).toFixed(2)
                         + ' "/></LiveEffect>');
        report.blurs++;
    } catch (be) { report.errors.push(String(it.name) + " blur: " + be); }
}
function blend(item, it) {
    if (!it.blend) { return; }
    try { item.blendingMode = BlendModes[BLENDS[it.blend]]; report.blends++; }
    catch (be) { report.errors.push(String(it.name) + " blend: " + be); }
}
function build(container, it, layer) {
    try {
        if (it.t === "g") {
            var g = container.groupItems.add(); g.name = it.name || "group"; report.groups++;
            for (var k = 0; k < it.kids.length; k++) { build(g, it.kids[k], layer); }
            if (it.clip && g.pageItems.length > 0) {
                // the mask's path never painted: a mask Illustrator refuses leaves nothing over the art (124's lid
                // lay under its empty map group's, filled white and stroked black); a mask of more than one
                // sub-path is a compound path, even-odd as the drawing clips — a sub-path inside another is a hole
                // (the carton inside's glue strip, kept clear of its print)
                var cs = subpaths(it.clip), cp;
                if (cs.length === 1) { cp = g.pathItems.add(); cp.filled = false; cp.stroked = false;
                                       fill(cp, cs[0]); cp.closed = true; }
                else { cp = g.compoundPathItems.add();
                       for (var q = 0; q < cs.length; q++) { var cq = cp.pathItems.add(); fill(cq, cs[q]);
                           cq.closed = true; cq.filled = false; cq.stroked = false; cq.evenodd = true; } }
                try { cp.move(g, ElementPlacement.PLACEATBEGINNING);
                      if (cs.length === 1) { cp.clipping = true; g.clipped = true; }
                      else {
                          // scripting will not make a compound path a mask; Illustrator's own Make Clipping Mask
                          // will — on this group alone, in this script's document, brought to the front first (a
                          // running script holds the UI, so none other comes before it)
                          doc.activate(); doc.selection = null; g.selected = true; app.executeMenuCommand("makeMask");
                          doc.selection = null;
                          if (!g.clipped) { throw "Make Clipping Mask left the group unmasked"; }
                      }
                      report.clips++; }
                catch (me) { try { cp.remove(); } catch (re) {} report.errors.push(String(it.name) + " mask: " + me); }
            }
            if (it.o < 1) { g.opacity = it.o * 100; }
            blend(g, it);
            return;
        }
        if (it.t === "p") {
            var subs = subpaths(it.segs);
            if (subs.length === 1) { var pi = container.pathItems.add(); pi.name = it.name; fill(pi, subs[0]);
                                     paint(pi, it, layer); if (it.o < 1) { pi.opacity = it.o * 100; } blend(pi, it);
                                     if (it.blur) { soften(pi, it); } }
            else { var cpi = container.compoundPathItems.add(); cpi.name = it.name;
                   for (var s = 0; s < subs.length; s++) { var p2 = cpi.pathItems.add(); fill(p2, subs[s]); }
                   for (var s2 = 0; s2 < cpi.pathItems.length; s2++) { paint(cpi.pathItems[s2], it, layer); }
                   if (it.o < 1) { cpi.opacity = it.o * 100; } blend(cpi, it); }
            report.paths++;
            return;
        }
        if (it.t === "i") {
            // a picture: placed from its file, at its place and its size, then embedded — the file carries it
            var pl = container.placedItems.add(); pl.file = new File(it.src);
            pl.width = it.w * MM; pl.height = it.h * MM; pl.position = P(it.x, it.y);
            pl.embed();
            var ri = container.pageItems[0]; ri.name = it.name;
            if (it.rot) { ri.rotate(it.rot); }          // [his goal of 2026-10-13, (2)] a picture in a turned group
            if (it.o < 1) { ri.opacity = it.o * 100; }
            report.images++;
            return;
        }
        if (it.t === "r") {
            var tl = P(it.x, it.y);
            var ri = it.r > 0 ? container.pathItems.roundedRectangle(tl[1], tl[0], it.w * MM, it.h * MM, it.r * MM,
                                                                     it.r * MM)
                              : container.pathItems.rectangle(tl[1], tl[0], it.w * MM, it.h * MM);
            ri.name = it.name; paint(ri, it, layer); if (it.o < 1) { ri.opacity = it.o * 100; } blend(ri, it);
            report.paths++;
            return;
        }
        if (it.t === "x") {
            var tf = container.textFrames.pointText(P(it.x, it.y)); tf.name = it.name; tf.contents = it.text;
            var ca = tf.textRange.characterAttributes; ca.size = it.size;
            try { ca.textFont = app.textFonts.getByName(it.font); } catch (fe) { report.missingFonts.push(it.font); }
            ca.fillColor = it.spot ? spot(it.spot, PLATE_INK) : ink(it.c);
            if (it.track) { ca.tracking = it.track * 1000; }
            var pa = tf.textRange.paragraphAttributes;
            if (it.rtl) {
                try { pa.composerEngine = ComposerEngineType.optycaComposer; } catch (ce) {}
                try { pa.paragraphDirection = ParagraphDirectionType.RIGHT_TO_LEFT_DIRECTION; } catch (pd) {}
            }
            if (it.align === "right") { pa.justification = Justification.RIGHT; }
            else if (it.align === "center") { pa.justification = Justification.CENTER; }
            // the line's own end on the graph's anchor, as the PDF sets it — whatever a right-to-left paragraph's
            // justification makes of the point (it ran the Arabic back over the Latin before it)
            var want = P(it.x, it.y)[0], gb0 = tf.geometricBounds;
            var have = it.align === "right" ? gb0[2] : (it.align === "center" ? (gb0[0] + gb0[2]) / 2 : gb0[0]);
            tf.translate(want - have, 0);
            if (it.rot) {
                var anchor = P(it.x, it.y); var gb = tf.geometricBounds;
                var cx = (gb[0] + gb[2]) / 2, cy = (gb[1] + gb[3]) / 2;
                tf.rotate(it.rot); var rad = it.rot * Math.PI / 180;
                var ax = anchor[0] - cx, ay = anchor[1] - cy;
                tf.translate(anchor[0] - (cx + ax * Math.cos(rad) - ay * Math.sin(rad)),
                             anchor[1] - (cy + ax * Math.sin(rad) + ay * Math.cos(rad)));
            }
            if (it.o < 1) { tf.opacity = it.o * 100; }
            blend(tf, it);
            report.texts++;
        }
    } catch (err) { report.errors.push(String(it.name || it.t) + ": " + err); }
}
for (var bi = 0; bi < D.boards.length; bi++) {
    OX = D.boards[bi].ox;
    for (var li = 0; li < D.boards[bi].layers.length; li++) {
        var lay = D.boards[bi].layers[li];
        // a finish's plate is its own layer, made where it is first met
        if (!layerOf[lay.name]) { var PL = doc.layers.add(); PL.name = lay.name; layerOf[lay.name] = PL; }
        for (var ii = 0; ii < lay.items.length; ii++) { build(layerOf[lay.name], lay.items[ii], lay.name); }
    }
}
for (var ln = 0; ln < doc.layers.length; ln++) { report.layers.push(doc.layers[ln].name); }
try {
    var opts = new IllustratorSaveOptions(); opts.pdfCompatible = true; opts.embedICCProfile = false;
    doc.saveAs(new File(D.save), opts); report.saved = true;
} catch (se) { report.errors.push("save: " + se); }
try { doc.close(SaveOptions.DONOTSAVECHANGES); } catch (ce2) { report.errors.push("close: " + ce2); }
try { if (_ui !== null) { app.userInteractionLevel = _ui; } } catch (e) {}
function q(s) { return '"' + String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"'; }
function arr(a) { var o = []; for (var j = 0; j < a.length; j++) { o.push(q(a[j])); } return "[" + o.join(",") + "]"; }
'{"status":' + q(report.status) + ',"artboards":' + report.artboards + ',"layers":' + arr(report.layers)
    + ',"groups":' + report.groups + ',"paths":' + report.paths + ',"texts":' + report.texts
    + ',"clips":' + report.clips + ',"gradients":' + report.gradients + ',"blends":' + report.blends
    + ',"images":' + report.images + ',"blurs":' + report.blurs
    + ',"missingFonts":' + arr(report.missingFonts) + ',"errors":' + arr(report.errors.slice(0, 20))
    + ',"saved":' + (report.saved ? "true" : "false") + '}';
"""


# --- [his bug on design 124, 2026-10-12: "Add a check that compares the layered file with the drawing (same
# --- elements, nothing missing), and make it fail if anything is dropped."]

def expected(data: dict) -> dict:
    """What the data sends Illustrator, counted as its run counts what it builds: each path and shape once (a compound
    path once), each line of words, each group, each mask, each gradient (a compound path's on every sub-path), each
    blend mode and each picture."""
    out = {"paths": 0, "texts": 0, "groups": 0, "clips": 0, "gradients": 0, "blends": 0, "images": 0, "blurs": 0}
    for board in data["boards"]:
        for layer in board["layers"]:
            for i in _walk(layer["items"]):
                out["blends"] += 1 if i.get("blend") else 0
                out["blurs"] += 1 if i.get("blur") else 0
                if i["t"] == "g":
                    out["groups"] += 1
                    out["clips"] += 1 if i.get("clip") else 0
                elif i["t"] in ("p", "r"):
                    out["paths"] += 1
                    if (i.get("fill") or {}).get("grad"):
                        out["gradients"] += sum(1 for s in i["segs"] if s[0] == "M") if i["t"] == "p" else 1
                elif i["t"] == "x":
                    out["texts"] += 1
                elif i["t"] == "i":
                    out["images"] += 1
    return out


def _inked(pdf_path: str, page: int, blank: list, paper_l: float | None = None):
    """The page's ink, cell by cell (CHECK): the share of each cell's pixels darker than the paper, every layer shown
    (the guides the file keeps on its non-printing layers are drawn, as the drawing draws them) — the places of
    ``blank`` (mm boxes: the words', compared as words) left out; None where the file has no such page."""
    import fitz
    import numpy as np
    with fitz.open(pdf_path) as pdf:
        if page >= len(pdf):
            return None
        for layer in pdf.layer_ui_configs():
            if not layer["on"]:
                pdf.set_layer_ui_config(layer["number"], 0)
        pix = pdf[page].get_pixmap(dpi=CHECK["dpi"], alpha=False)
        rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].astype(np.float64) / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    y = lin @ np.array([0.2126, 0.7152, 0.0722])
    lightness = np.where(y > 0.008856, 116.0 * np.cbrt(y) - 16.0, 903.3 * y)
    ink = lightness < (paper_l or CHECK["paper_l"])
    per_mm = CHECK["dpi"] / 25.4
    for x, y0, w, h in blank:
        ink[int(y0 * per_mm):int((y0 + h) * per_mm) + 1, int(x * per_mm):int((x + w) * per_mm) + 1] = False
    cell = max(1, int(round(CHECK["cell_mm"] * per_mm)))
    rows, cols = ink.shape[0] // cell, ink.shape[1] // cell
    return ink[:rows * cell, :cols * cell].reshape(rows, cell, cols, cell).mean(axis=(1, 3))


def _colours(pdf_path: str, page: int, blank: list):
    """``(means, smooth)``: each CHECK cell's mean colour (CIE Lab) and whether it is smooth (CHECK["smooth"]), every
    layer shown — a cell the words' boxes (``blank``) cover half of is never smooth; None where there is no such page."""
    import fitz
    import numpy as np
    with fitz.open(pdf_path) as pdf:
        if page >= len(pdf):
            return None
        for layer in pdf.layer_ui_configs():
            if not layer["on"]:
                pdf.set_layer_ui_config(layer["number"], 0)
        pix = pdf[page].get_pixmap(dpi=CHECK["colour_dpi"], alpha=False)
        rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].astype(np.float64) / 255.0
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    xyz = lin @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    lab = np.stack([116.0 * f[..., 1] - 16.0, 500.0 * (f[..., 0] - f[..., 1]), 200.0 * (f[..., 1] - f[..., 2])], -1)
    per_mm = CHECK["colour_dpi"] / 25.4
    words = np.zeros(lab.shape[:2], bool)
    for x, y0, w, h in blank:
        words[int(y0 * per_mm):int((y0 + h) * per_mm) + 1, int(x * per_mm):int((x + w) * per_mm) + 1] = True
    cell = max(1, int(round(CHECK["cell_mm"] * per_mm)))
    rows, cols = lab.shape[0] // cell, lab.shape[1] // cell
    blocks = lab[:rows * cell, :cols * cell].reshape(rows, cell, cols, cell, 3).transpose(0, 2, 1, 3, 4)
    blocks = blocks.reshape(rows, cols, cell * cell, 3)
    means = blocks.mean(axis=2)
    spread = np.percentile(np.sqrt(((blocks - means[:, :, None, :]) ** 2).sum(-1)), 90, axis=2)
    covered = words[:rows * cell, :cols * cell].reshape(rows, cell, cols, cell).mean(axis=(1, 3))
    return means, (spread <= CHECK["smooth"]) & (covered < 0.5)


def _word_boxes(pdf_path: str, page: int) -> list:
    """The mm boxes of the page's words, half a millimetre round."""
    import fitz
    with fitz.open(pdf_path) as pdf:
        if page >= len(pdf):
            return []
        to_mm = 25.4 / 72.0
        return [(x0 * to_mm - 0.5, y0 * to_mm - 0.5, (x1 - x0) * to_mm + 1.0, (y1 - y0) * to_mm + 1.0)
                for x0, y0, x1, y1, *_ in pdf[page].get_text("words")]


def _near(cells):
    """Each cell's largest ink among itself and its eight neighbours."""
    import numpy as np
    padded = np.pad(cells, 1)
    rows, cols = cells.shape
    return np.max([padded[1 + dr:1 + dr + rows, 1 + dc:1 + dc + cols] for dr in (-1, 0, 1) for dc in (-1, 0, 1)],
                  axis=0)


def check(data: dict, summary: dict, drawing_pdf: str, native_pdf: str) -> dict:
    """The layered file against the drawing (CHECK): every element the data sends built (``expected`` against the
    run's own counts) with no error of Illustrator's; every page of the drawing an artboard of the file (the artwork,
    its inside, each finish's plate), in its order; and, page by page, every place the drawing inks inked in the file,
    nothing inked where the drawing draws nothing — ``{"schema", "params", "state": PASS | FAIL, "expected", "built",
    "errors", "places", "why"}``, FAIL said in words: what was not built, and where the file differs."""
    import fitz
    sent = expected(data)
    built = {k: int(summary.get(k) or 0) for k in sent}
    short = ["%d of %d %s" % (built[k], sent[k], k) for k in sent if built[k] < sent[k]]
    errors = [str(e) for e in summary.get("errors") or []]
    places = []
    with fitz.open(drawing_pdf) as pdf:
        pages = len(pdf)
    for page in range(len(data["boards"]), pages):
        places.append({"board": "page %d" % (page + 1), "kind": "artboard",
                       "why": "the drawing's page %d is not an artboard of the file" % (page + 1)})
    for page, board in enumerate(data["boards"]):
        # words are compared as words — each line sent is a line built (above) — never by their ink: a face
        # Illustrator does not have sets them in a substitute (named in missing_fonts), wider or narrower; every
        # word's box, in either file, is left out of the ink
        here = _word_boxes(drawing_pdf, page) + _word_boxes(native_pdf, page)
        drawn, made = _inked(drawing_pdf, page, here), _inked(native_pdf, page, here)
        if drawn is None or made is None:
            places.append({"board": board["name"], "kind": "artboard", "why": "the artboard is not in the %s" % (
                "drawing" if drawn is None else "file")})
            continue
        rows, cols = min(drawn.shape[0], made.shape[0]), min(drawn.shape[1], made.shape[1])
        drawn, made = drawn[:rows, :cols], made[:rows, :cols]
        # a cell's neighbours count for it: a line of words set in a substitute face (a face Illustrator does not
        # have, named in missing_fonts) ends a few millimetres sooner, a hairline lands a pixel lower — the same
        # element, not a dropped one; and the other file's ink is read faintly (``faint_l``): a pale ground the
        # CMYK file renders half a step lighter than the drawing's RGB is the same ground — a dropped element leaves
        # the paper itself
        drawn_near = _near(_inked(drawing_pdf, page, here, CHECK["faint_l"])[:rows, :cols])
        made_near = _near(_inked(native_pdf, page, here, CHECK["faint_l"])[:rows, :cols])
        for r in range(rows):
            for c in range(cols):
                a, b = float(drawn[r, c]), float(made_near[r, c])
                at = [round(c * CHECK["cell_mm"], 1), round(r * CHECK["cell_mm"], 1)]
                if a >= CHECK["ink_share"] and b < CHECK["kept"] * a:
                    places.append({"board": board["name"], "kind": "missing", "at_mm": at, "drawing": round(a, 2),
                                   "file": round(b, 2)})
                elif float(drawn_near[r, c]) < CHECK["clear"] and float(made[r, c]) >= CHECK["extra"]:
                    places.append({"board": board["name"], "kind": "extra", "at_mm": at,
                                   "drawing": round(float(drawn_near[r, c]), 2), "file": round(float(made[r, c]), 2)})
        if data.get("space") == "RGB":
            # [his goal of 2026-10-13, (10)] then its colours where both files are smooth, the drawing's own (CHECK):
            # listed after its ink, which a dropped element fails first
            import numpy as np
            seen, kept = _colours(drawing_pdf, page, here), _colours(native_pdf, page, here)
            if seen is not None and kept is not None:
                cr, cc = min(seen[0].shape[0], kept[0].shape[0]), min(seen[0].shape[1], kept[0].shape[1])
                apart = np.sqrt(((seen[0][:cr, :cc] - kept[0][:cr, :cc]) ** 2).sum(-1))
                for r, c in zip(*np.where(seen[1][:cr, :cc] & kept[1][:cr, :cc] & (apart > CHECK["colour_de"]))):
                    places.append({"board": board["name"], "kind": "colour",
                                   "at_mm": [round(c * CHECK["cell_mm"], 1), round(r * CHECK["cell_mm"], 1)],
                                   "de": round(float(apart[r, c]), 1)})
    why = []
    if short:
        why.append("not built: " + ", ".join(short))
    if errors:
        why.append("Illustrator said: " + "; ".join(errors[:3]))
    for kind, words in (("missing", "blank in the file where the drawing draws"),
                        ("extra", "drawn in the file where the drawing draws nothing")):
        cells = [p for p in places if p["kind"] == kind]
        if cells:
            first = cells[0]
            why.append("%d places %s (the first at %s mm on %s)" % (len(cells), words, first["at_mm"], first["board"]))
    colour = [p for p in places if p["kind"] == "colour"]
    if len(colour) >= CHECK["colour_places"]:
        why.append("%d places drawn in another colour than the drawing's (the first at %s mm on %s, ΔE %.1f)" % (
            len(colour), colour[0]["at_mm"], colour[0]["board"], colour[0]["de"]))
    for p in places:
        if p["kind"] == "artboard":
            why.append("%s: %s" % (p["board"], p["why"]))
    return {"schema": "native_check/1.0", "params": dict(CHECK), "state": FAIL if why else PASS, "expected": sent,
            "built": built, "errors": errors[:10], "places": places[:40], "places_count": len(places),
            "why": "; ".join(why) if why else None}


def script(data: dict, save_path: str) -> str:
    """The bounded script: the data as a literal (JSON is valid ES3), then the fixed runtime above. It touches only the
    document it makes, saves it to ``save_path`` and closes it."""
    return "var D = %s;\n%s" % (json.dumps(dict(data, save=save_path), ensure_ascii=True), _RUNTIME)


def build(doc, save_path: str, *, fonts: dict | None = None, timeout_s: int = 300,
          drawing: str | None = None) -> dict:
    """[His final goal, C6.] The design's native .ai, built in Illustrator: ``{"schema", "built", "path", "summary",
    "missing_fonts", "reason"}`` — ``built`` False, with the reason, where Illustrator is not here or the script does
    not save; the PDF-compatible .ai stays the design's file then. A face Illustrator does not have is named in
    ``missing_fonts`` (its lines set in a substitute). The self-check says either."""
    from apps.ire.handoff.illustrator_exec import illustrator_available, run_jsx
    data = tree(doc, fonts=fonts)
    out = {"schema": SCHEMA, "built": False, "path": None, "fonts": data["fonts"], "not_carried": data["skipped"],
           "effects_not_carried": data["effects_not_carried"],
           "space": data["space"], "profile": data["profile"]}      # [his goal of 2026-10-12, (1)] said on the record
    if not illustrator_available():
        return dict(out, reason="Illustrator is not available on this machine — the PDF-compatible .ai is the file")
    jsx = os.path.splitext(save_path)[0] + ".jsx"
    with open(jsx, "w", encoding="utf-8") as fh:
        fh.write(script(data, os.path.abspath(save_path)))
    summary = run_jsx(jsx, timeout_s=timeout_s)
    if not summary.get("executed", True) or not summary.get("saved"):
        return dict(out, summary=summary, reason="Illustrator did not save the file: %s" % (
            summary.get("reason") or "; ".join(summary.get("errors") or []) or "no summary"))
    built = os.path.exists(save_path)
    # a face Illustrator does not have sets its lines in a substitute: built, and said (the self-check shows it)
    record = dict(out, built=built, path=save_path if built else None, summary=summary,
                  missing_fonts=sorted(set(summary.get("missingFonts") or [])),
                  reason=None if built else "the saved file is not where it was saved")
    if built and drawing:
        # [his bug on design 124, 2026-10-12: "make it fail if anything is dropped"] checked against the drawing
        # before it is offered: a file that does not carry the drawing whole is not the design's layered file, and
        # says why
        verdict = check(data, summary, drawing, save_path)
        record["check"] = verdict
        if verdict["state"] != PASS:
            record.update(built=False, path=None, code=CHECK_FAILED,
                          reason="the layered file does not carry the drawing whole — %s" % verdict["why"])
    return record
