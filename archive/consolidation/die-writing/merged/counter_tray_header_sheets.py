"""The sheets of counter_tray_header 0.1 (D-D12-2): the die as SVG and PDF with named layers, the die at 100 % on one
page and tiled over A3, and the plan / front elevation / side section at 1 : 2 on A3.

[The owner's decision, CURRENT_DECISIONS.md "Day 12", D-D12-2: "Outputs: the die (SVG + PDF; named layers cut, crease,
artwork, safe), a fold check ..., the platforms and the slot as parts on the same sheet, the plan and elevation at
1 : 2, the A3 at 100 % (tiled with overlap marks)."]

Every coordinate handed in is a millimetre on the die's own sheet (X right, Y down) or in the display's model (x
across, y depth, z height over the counter); every PDF coordinate is a point, converted only through ``PT_PER_MM``.
The layers are ``apps.dielines.exporters.pdf_layers``'s: CUT and CREASE on their spot plates, ARTWORK an empty named
placeholder, SAFE and BLEED guides that never print — and, for this exporter only, WORDS: every die word (the part
labels, the title, the 50 mm bar and its words, the folder's marks), never printed (``apply_layers``; the shared
``pdf_layers.LAYERS`` and ``NON_PRINTING`` are left as their other users have them).
"""
from __future__ import annotations

import math
from functools import lru_cache
from xml.sax.saxutils import escape

from apps.dielines.exporters import pdf_layers as L
from apps.dielines.geometry import counter_tray_header as C

PT_PER_MM = C.PT_PER_MM
A3_LONG_MM, A3_SHORT_MM = 420.0, 297.0
BLEED_MM = C.DIE_BLEED_MM
SAFE_MM = 3.0
OVERLAP_MM = 10.0
SVG_GROUPS = ("artwork", "bleed", "safe", "crease", "cut")
#: every SVG group's inkscape:label (the house's svg_exporter labels each group so)
SVG_LABELS = {"artwork": "ARTWORK", "bleed": "BLEED", "safe": "SAFE", "crease": "CREASE", "cut": "CUT",
              "words": "WORDS"}
INKSCAPE_NS = "http://www.inkscape.org/namespaces/inkscape"
PDF_LAYERS = ("ARTWORK", "CUT", "CREASE", "SAFE", "BLEED", "WORDS")
#: the layers, in this order, and the ones that never print: pdf_layers' own, plus WORDS (this exporter only)
LAYER_ORDER = tuple(L.LAYERS) + ("WORDS",)
NON_PRINTING = tuple(L.NON_PRINTING) + ("WORDS",)
#: the house's SVG colours (apps/dielines/exporters/svg_exporter.py: cut-lines #EC008C, fold-lines #00AEEF dashed), the
#: same plates as the PDF's CutContour (magenta) and Crease (cyan)
SVG_CUT_HEX, SVG_CREASE_HEX = "#EC008C", "#00AEEF"
SVG_CREASE_DASH = "3 1.6"                      # mm, as the PDF's crease dash
#: the house's guide greys (svg_exporter.py: g#bleed #8C8C8C, g#safe-area #B3B3B3) — never the crease's cyan (the
#: reviewer's MINOR 3); used in the SVG and the PDF alike
BLEED_HEX, SAFE_HEX = "#8C8C8C", "#B3B3B3"


@lru_cache(maxsize=1)
def drawing_face():
    """D-D14-2: construction labels use the GRANTED, embedded Tajawal Medium.

    The same verified face measures and paints the labels. No base-14 fallback is permitted.
    """
    from apps.ire.font_roles import resolve_line_face
    face = resolve_line_face('Tajawal-Medium', 500.0)
    if face.get('refused'):
        raise ValueError('D-D14-2 construction face did not verify through font authority')
    return face


def drawing_font():
    return drawing_face()['label']


def _pt(value_mm):
    return value_mm * PT_PER_MM


def latin(text: str) -> str:
    """Keep the construction drawing's existing plain-word transcription unchanged."""
    for a, b in (("⟪", ""), ("⟫", ""), ("−", "-"), ("≥", ">="), ("≤", "<="), ("→", "->"), ("…", "...")):
        text = text.replace(a, b)
    return text.encode("cp1252", "replace").decode("cp1252")


# --- what each layer holds, in die millimetres -------------------------------------------------------------------------


def safe_areas(part) -> list:
    """Each printed face's safe area: the face inset ``SAFE_MM``, less every hole of the part grown by ``SAFE_MM`` (the
    reviewer's MINOR 9: nothing safe runs over a hole), less every slit of the part (a cut that bounds no face: the
    lock tabs' relief slits run 2 mm into the side skins) and every slot lying in the face, each grown by ``SAFE_MM``
    (the sheet verifier's minor: the safe line stood 1.00 from the slits' ends). A slot cut out of its face (the back
    wall's lock-slot notches) is already in the face's own outline, so the inset clears it. Polygons, interiors kept."""
    from shapely.geometry import Point
    from shapely.ops import unary_union
    if part.hole_shape == "square":
        holes = unary_union([polygon.buffer(SAFE_MM, join_style=2)
                             for _name, polygon in part.hole_polygons()]) if part.holes else None
    else:
        holes = unary_union([Point(c).buffer(r + SAFE_MM, 16) for _n, c, r in part.holes]) if part.holes else None
    slits = [s for _n, s in part.slits]
    out = []
    for _n, face, printed in part.faces:
        if not printed:
            continue
        safe = face.buffer(-SAFE_MM, join_style=2)
        if holes is not None:
            safe = safe.difference(holes)
        cuts = [s.buffer(SAFE_MM, 16) for s in slits if s.distance(face) < SAFE_MM]
        cuts += [sl["polygon"].buffer(SAFE_MM, 16) for sl in part.slots if sl["polygon"].intersection(face).area > 1e-6]
        if cuts:
            safe = safe.difference(unary_union(cuts))
        out += [g for g in getattr(safe, "geoms", [safe]) if not g.is_empty and g.area > 1.0]
    return out


def layer_geometry(die) -> dict:
    """``{"cut": [polyline], "holes": [(cx, cy, r)], "crease": [polyline], "safe": [ring], "bleed": [ring],
    "marks": [(text, (x, y), size)]}`` — every ring of a safe area, its interiors (around the holes) included."""
    out = {"cut": [], "holes": [], "crease": [], "safe": [], "bleed": [], "marks": []}
    # marks: (text, (x, y), size, side) — side "reverse": drawn flipped top to bottom (it lies on the unprinted face)
    for p in die.parts:
        out["cut"] += [list(ln.coords) for ln in p.cut_lines()]
        if p.hole_shape == "square":
            out["cut"] += [list(polygon.exterior.coords) for _name, polygon in p.hole_polygons()]
        else:
            out["holes"] += [(c[0], c[1], r) for _n, c, r in p.holes]
        out["crease"] += [list(cr.coords) for _n, cr in p.creases]
        bleed = p.outline().buffer(BLEED_MM, join_style=2)
        out["bleed"].append(list(bleed.exterior.coords))
        for g in safe_areas(p):
            out["safe"].append(list(g.exterior.coords))
            out["safe"] += [list(i.coords) for i in g.interiors]
        out["marks"] += [(m[0], m[1], m[2], m[4] if len(m) > 4 else "print") for m in p.marks]
    return out


# --- SVG ---------------------------------------------------------------------------------------------------------------


def write_svg(die, path) -> list:
    """The die as SVG in millimetres: groups ``artwork`` (empty, named), ``bleed``, ``safe``, ``crease``, ``cut``, then
    ``words`` (the words and the 50 mm bar), each with its ``inkscape:label`` (``SVG_LABELS``, as the house's
    svg_exporter labels every group; the sheet verifier's minor), the prefix declared once on the root. Returns the
    group ids written."""
    import base64
    from pathlib import Path
    embedded = base64.b64encode(Path(drawing_face()['path']).read_bytes()).decode('ascii')
    geo = layer_geometry(die)

    def pl(pts):
        return "M" + " L".join("%.3f %.3f" % (x, y) for x, y in pts)

    w, h = die.sheet_w, die.sheet_h
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="%s" width="%gmm" height="%gmm" '
             'viewBox="0 0 %g %g">' % (INKSCAPE_NS, w, h, w, h),
             '<title>%s</title>' % escape(die.title),
             '<defs><style>@font-face {font-family:Tajawal;src:url(data:font/ttf;base64,%s)}</style></defs>' % embedded,
             '<rect x="0" y="0" width="%g" height="%g" fill="#ffffff"/>' % (w, h),
             '<g id="artwork" inkscape:label="ARTWORK">'
             '<!-- placeholder: the artwork is placed on this layer later --></g>',
             '<g id="bleed" fill="none" stroke="%s" stroke-width="0.2" stroke-dasharray="2.2 1.6" '
             'inkscape:label="BLEED">' % BLEED_HEX]
    lines += ['<path d="%s Z"/>' % pl(r) for r in geo["bleed"]]
    lines += ['</g>', '<g id="safe" fill="none" stroke="%s" stroke-width="0.2" stroke-dasharray="1.4 1.4" '
                      'inkscape:label="SAFE">' % SAFE_HEX]
    lines += ['<path d="%s Z"/>' % pl(r) for r in geo["safe"]]
    lines += ['</g>', '<g id="crease" fill="none" stroke="%s" stroke-width="0.3" stroke-dasharray="%s" '
                      'inkscape:label="CREASE">' % (SVG_CREASE_HEX, SVG_CREASE_DASH)]
    lines += ['<path d="%s"/>' % pl(c) for c in geo["crease"]]
    lines += ['</g>', '<g id="cut" fill="none" stroke="%s" stroke-width="0.3" inkscape:label="CUT">' % SVG_CUT_HEX]
    lines += ['<path d="%s"/>' % pl(c) for c in geo["cut"]]
    lines += ['<circle cx="%.3f" cy="%.3f" r="%.3f"/>' % hc for hc in geo["holes"]]
    lines += ['</g>', '<g id="words" inkscape:label="WORDS" '
                      'font-family="Tajawal" fill="#222222">'
                      '<!-- the die\'s words: never printed (the PDF\'s WORDS layer) -->']
    for text, (x, y), size in die.labels:
        lines.append('<text x="%.2f" y="%.2f" font-size="%.2f">%s</text>' % (x, y, size, escape(text)))
    for text, (x, y), size, side in geo["marks"]:
        if side == "reverse":                  # on the unprinted face: flipped top to bottom as seen from the print side
            lines.append('<text transform="translate(%.2f %.2f) scale(1 -1)" x="0" y="0" font-size="%.2f">%s</text>' % (
                x, y, size, escape(text)))
        else:
            lines.append('<text x="%.2f" y="%.2f" font-size="%.2f">%s</text>' % (x, y, size, escape(text)))
    bx, by, bl = die.bar
    lines.append('<text x="%.2f" y="%.2f" font-size="%g">%s</text>' % (bx, by - 9, C.BAR_WORDS_MM, escape(die.title)))
    lines.append('<rect x="%.2f" y="%.2f" width="%.2f" height="3" fill="#000000"/>' % (bx, by, bl))
    lines.append('<text x="%.2f" y="%.2f" font-size="%g">%s</text>' % (bx + bl + 4, by + 3, C.BAR_WORDS_MM,
                                                                     escape(C.BAR_WORDS)))
    lines += ['</g>', '</svg>']
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return ["artwork", "bleed", "safe", "crease", "cut"]


# --- PDF: the die -------------------------------------------------------------------------------------------------------


def _path(c, pts, tx, ty, close=False):
    p = c.beginPath()
    p.moveTo(tx(pts[0][0]), ty(pts[0][1]))
    for x, y in pts[1:]:
        p.lineTo(tx(x), ty(y))
    if close:
        p.close()
    c.drawPath(p, stroke=1, fill=0)


def _draw_die(c, die, tx, ty, layered=True):
    from reportlab.lib.colors import HexColor
    geo = layer_geometry(die)
    begin = (lambda name: L.begin(c, name)) if layered else (lambda name: None)
    end = (lambda: L.end(c)) if layered else (lambda: None)
    begin("ARTWORK")                       # the named placeholder: the artwork is placed here later
    end()
    begin("BLEED")
    c.setStrokeColor(HexColor(BLEED_HEX))
    c.setLineWidth(0.5)
    c.setDash([_pt(2.2), _pt(1.6)])
    for ring in geo["bleed"]:
        _path(c, ring, tx, ty, close=True)
    end()
    begin("SAFE")
    c.setStrokeColor(HexColor(SAFE_HEX))
    c.setDash([_pt(1.4), _pt(1.4)])
    for ring in geo["safe"]:
        _path(c, ring, tx, ty, close=True)
    end()
    begin("CREASE")
    c.setStrokeColor(L.spot("CREASE"))
    c.setStrokeOverprint(True)
    c.setLineWidth(0.75)
    c.setDash([_pt(3.0), _pt(1.6)])
    for line in geo["crease"]:
        _path(c, line, tx, ty)
    end()
    begin("CUT")
    c.setStrokeColor(L.spot("CUT"))
    c.setLineWidth(0.75)
    c.setDash()
    for line in geo["cut"]:
        _path(c, line, tx, ty)
    for cx, cy, r in geo["holes"]:
        c.circle(tx(cx), ty(cy), _pt(r), stroke=1, fill=0)
    end()
    c.setStrokeOverprint(False)


def _words(c, die, tx, ty, layered=False):
    """Every die word — the part labels, the folder's marks (a reverse-face mark flipped top to bottom), the title, the
    50 mm bar and its words — inside the WORDS layer's marked content when ``layered`` (die.pdf: never printed)."""
    from reportlab.lib.colors import black
    if layered:
        L.begin(c, "WORDS")
    c.setFillColor(black)
    for text, (x, y), size in die.labels:
        c.setFont(drawing_font(), _pt(size))
        c.drawString(tx(x), ty(y), latin(text))
    for text, (x, y), size, side in layer_geometry(die)["marks"]:
        c.setFont(drawing_font(), _pt(size))
        if side == "reverse":                  # glyph tops toward +Y on the die (down the sheet): flipped
            c.saveState()
            c.translate(tx(x), ty(y))
            c.scale(1, -1)
            c.drawString(0, 0, latin(text))
            c.restoreState()
        else:
            c.drawString(tx(x), ty(y), latin(text))
    bx, by, bl = die.bar
    c.setFont(drawing_font(), _pt(C.BAR_WORDS_MM))
    c.drawString(tx(bx), ty(by - 9), latin(die.title))
    _bar(c, tx(bx), ty(by + 3), bl, C.BAR_WORDS, size_mm=C.BAR_WORDS_MM)
    if layered:
        L.end(c)


def _bar(c, x_pt, y_pt, length_mm, words, paper_mm=None, size_mm=3.2):
    """A calibration bar ``paper_mm`` long on paper (``length_mm`` when None), ticked every 10 mm of it."""
    from reportlab.lib.colors import black, white
    paper_mm = length_mm if paper_mm is None else paper_mm
    c.setDash()
    c.setLineWidth(0.5)
    c.setStrokeColor(black)
    n = 5
    for i in range(n):
        c.setFillColor(black if i % 2 == 0 else white)
        c.rect(x_pt + _pt(paper_mm * i / n), y_pt, _pt(paper_mm / n), _pt(3.0), stroke=1, fill=1)
    c.setFillColor(black)
    c.setFont(drawing_font(), _pt(size_mm))
    c.drawString(x_pt + _pt(paper_mm + 3.0), y_pt + _pt(0.6), latin(words))


def write_die_pdf(die, path, layered=True) -> list:
    """The die at 100 % on one page the size of its sheet (1 pt = 25.4 / 72 mm). With ``layered`` the file carries
    the optional content groups CUT, CREASE, ARTWORK, SAFE, BLEED, WORDS (SAFE, BLEED and WORDS never print).
    Returns the layers given."""
    from reportlab.pdfgen import canvas
    page_w_pt, page_h_pt = _pt(die.sheet_w), _pt(die.sheet_h)
    c = canvas.Canvas(str(path), pagesize=(page_w_pt, page_h_pt), invariant=1, initialFontName=drawing_font())
    c.setTitle(latin(die.title))
    tx = lambda x: _pt(x)                                   # noqa: E731
    ty = lambda y: _pt(die.sheet_h - y)                     # noqa: E731
    _draw_die(c, die, tx, ty, layered)
    _words(c, die, tx, ty, layered)
    c.showPage()
    c.save()
    return apply_layers(str(path), PDF_LAYERS) if layered else []


def apply_layers(path: str, layers, order=LAYER_ORDER, non_printing=NON_PRINTING, pages=None) -> list:
    """``pdf_layers.apply`` for this exporter: the same optional content groups, view on, the guides' print state off,
    with WORDS among them (in ``order``) and among the layers that never print (``non_printing``) — the shared
    module's LAYERS and NON_PRINTING are not touched. Returns the layers given."""
    import os

    import fitz
    names = [name for name in order if name in set(layers)]
    if not names:
        return []
    doc = fitz.open(path)
    xrefs = {name: doc.add_ocg(name, on=True) for name in names}
    for name in non_printing:
        if name in xrefs:
            doc.xref_set_key(xrefs[name], "Usage", "<</Print <</PrintState /OFF>> /View <</ViewState /ON>>>>")
    props = "<<%s>>" % " ".join("/%s %d 0 R" % (L.tag(n), x) for n, x in xrefs.items())
    for pno in range(doc.page_count) if pages is None else pages:
        doc.xref_set_key(doc[pno].xref, "Resources/Properties", props)
    guides = [xrefs[n] for n in non_printing if n in xrefs]
    if guides:
        doc.xref_set_key(doc.pdf_catalog(), "OCProperties/D/AS", "[<</Event /Print /OCGs [%s] /Category [/Print]>>]"
                         % " ".join("%d 0 R" % x for x in guides))
    tmp = path + ".layers"
    # no_new_id: keep the trailer /ID reportlab's invariant canvas wrote, so die.pdf regenerates byte for byte
    # (the sheet verifier's minor: a new /ID on every save)
    doc.save(tmp, garbage=0, deflate=True, no_new_id=True)
    doc.close()
    os.replace(tmp, path)
    return names


def tile_grid(die, page_w_mm=A3_LONG_MM, page_h_mm=A3_SHORT_MM):
    margin, foot = 12.0, 30.0
    win_w, win_h = page_w_mm - 2 * margin, page_h_mm - margin - foot
    step_w, step_h = win_w - OVERLAP_MM, win_h - OVERLAP_MM
    cols = max(1, math.ceil((die.sheet_w - OVERLAP_MM) / step_w))
    rows = max(1, math.ceil((die.sheet_h - OVERLAP_MM) / step_h))
    return {"margin": margin, "foot": foot, "win_w": win_w, "win_h": win_h, "step_w": step_w, "step_h": step_h,
            "cols": cols, "rows": rows}


def write_tiles_pdf(die, path) -> dict:
    """The die at 100 % over A3 landscape sheets: each tile a window of the die, 10 mm overlap with its neighbours,
    crop marks at the window's corners, registration marks centred in every shared overlap band, its row/column and
    "print at 100 %, no fit", and a 50 mm bar."""
    from reportlab.lib.colors import HexColor, black
    from reportlab.pdfgen import canvas
    tg = tile_grid(die)
    page_w_pt, page_h_pt = _pt(A3_LONG_MM), _pt(A3_SHORT_MM)
    c = canvas.Canvas(str(path), pagesize=(page_w_pt, page_h_pt), invariant=1, initialFontName=drawing_font())
    c.setTitle(latin("counter_tray_header %s - die at 100 %% tiled over A3" % C.VERSION))
    m, ww, wh = tg["margin"], tg["win_w"], tg["win_h"]
    top_mm = A3_SHORT_MM - m                                  # the window's top edge, from the page's foot
    for r in range(tg["rows"]):
        for col in range(tg["cols"]):
            wx, wy = col * tg["step_w"], r * tg["step_h"]
            tx = lambda x, wx=wx: _pt(m + x - wx)              # noqa: E731
            ty = lambda y, wy=wy: _pt(top_mm - (y - wy))       # noqa: E731
            c.saveState()
            p = c.beginPath()
            p.rect(_pt(m), _pt(top_mm - wh), _pt(ww), _pt(wh))
            c.clipPath(p, stroke=0, fill=0)
            _draw_die(c, die, tx, ty, layered=False)
            _words(c, die, tx, ty)
            c.restoreState()
            # the window, its overlap bands, crop and registration marks
            c.setStrokeColor(HexColor("#888888"))
            c.setLineWidth(0.3)
            c.setDash([_pt(1.0), _pt(1.0)])
            if col > 0:
                c.line(_pt(m + OVERLAP_MM), _pt(top_mm - wh), _pt(m + OVERLAP_MM), _pt(top_mm))
            if col < tg["cols"] - 1:
                c.line(_pt(m + ww - OVERLAP_MM), _pt(top_mm - wh), _pt(m + ww - OVERLAP_MM), _pt(top_mm))
            if r > 0:
                c.line(_pt(m), _pt(top_mm - OVERLAP_MM), _pt(m + ww), _pt(top_mm - OVERLAP_MM))
            if r < tg["rows"] - 1:
                c.line(_pt(m), _pt(top_mm - wh + OVERLAP_MM), _pt(m + ww), _pt(top_mm - wh + OVERLAP_MM))
            c.setDash()
            c.setStrokeColor(black)
            for cx_mm, cy_mm, sx, sy in ((m, top_mm, -1, 1), (m + ww, top_mm, 1, 1), (m, top_mm - wh, -1, -1),
                                         (m + ww, top_mm - wh, 1, -1)):
                c.line(_pt(cx_mm + sx * 2), _pt(cy_mm), _pt(cx_mm + sx * 8), _pt(cy_mm))
                c.line(_pt(cx_mm), _pt(cy_mm + sy * 2), _pt(cx_mm), _pt(cy_mm + sy * 8))
            marks = []
            if col > 0:
                marks.append((m + OVERLAP_MM / 2, top_mm - wh / 2))
            if col < tg["cols"] - 1:
                marks.append((m + ww - OVERLAP_MM / 2, top_mm - wh / 2))
            if r > 0:
                marks.append((m + ww / 2, top_mm - OVERLAP_MM / 2))
            if r < tg["rows"] - 1:
                marks.append((m + ww / 2, top_mm - wh + OVERLAP_MM / 2))
            for mx_mm, my_mm in marks:
                c.circle(_pt(mx_mm), _pt(my_mm), _pt(3.0), stroke=1, fill=0)
                c.line(_pt(mx_mm - 4.5), _pt(my_mm), _pt(mx_mm + 4.5), _pt(my_mm))
                c.line(_pt(mx_mm), _pt(my_mm - 4.5), _pt(mx_mm), _pt(my_mm + 4.5))
            c.setFillColor(black)
            c.setFont(drawing_font(), _pt(4.0))
            c.drawString(_pt(m), _pt(18.0), latin("tile row %d / col %d of %d x %d - print at 100 %%, no fit (A3 "
                                                  "landscape)" % (r + 1, col + 1, tg["rows"], tg["cols"])))
            c.setFont(drawing_font(), _pt(3.0))
            c.drawString(_pt(m), _pt(13.0), latin(
                "counter_tray_header %s PROVISIONAL - die x %.0f..%.0f, y %.0f..%.0f mm - overlap %g mm with each "
                "neighbour: lay the circled crosses on each other" % (C.VERSION, wx, wx + ww, wy, wy + wh,
                                                                      OVERLAP_MM)))
            _bar(c, _pt(m + 210.0), _pt(12.5), 50.0, "50 mm")
            c.showPage()
    c.save()
    return dict(tg, tiles=tg["rows"] * tg["cols"], page_mm=[A3_LONG_MM, A3_SHORT_MM], overlap_mm=OVERLAP_MM)


# --- PDF: plan, front elevation, side section at 1 : 2 ------------------------------------------------------------------

SCALE = 0.5


class _Drawn:
    """What a sheet draws, in paper mm (x right, y up from the page's foot): every line and circle, and every word's
    box — so a check can say whether a label sits on the drawing (the reviewer's MINOR 10)."""

    def __init__(self):
        self.lines = []        # (owner, LineString)
        self.words = []        # (kind, text, Polygon, owner)
        self.dims = []         # {"view", "words", "along", "model_mm": [a, b]}: every dimension drawn

    def dimension_owner(self, words) -> str:
        """A dimension's own id (each one unique: two dimensions may read the same, e.g. "160" on the section and
        the plan); its dimension line is owned by ``<id> line``, its extension lines and arrowheads by ``<id>``."""
        return "dimension %d: %s" % (len(self.dims) + 1, words)

    def clashes(self) -> list:
        """Every label against every line, circle and other word: a free label against all it does not own (its own
        leader), a dimension's words against all but its own dimension line (its extension lines and arrowheads
        included — the sheet verifier's minor: 'offset 16' was crossed by its own)."""
        out = []
        for kind, text, box, owner in self.words:
            if kind == "free":
                hits = [o or "drawing" for o, ln in self.lines if (owner is None or o != owner) and box.intersects(ln)]
            else:
                hits = [o or "drawing" for o, ln in self.lines if o != owner + " line" and box.intersects(ln)]
            hits += ["word: " + t for k, t, b, _o in self.words if b is not box and box.intersects(b)]
            out.append({"text": text, "kind": kind, "clear": not hits, "hits": len(hits), "first_hits": hits[:3]})
        return out


class _View:
    """A model view on the A3 page: model (u, v) mm -> paper (origin + u·½, origin + v·½) mm -> points."""

    def __init__(self, c, ox_mm, oy_mm, drawn: _Drawn | None = None, name: str = ""):
        self.c, self.ox_mm, self.oy_mm, self.name = c, ox_mm, oy_mm, name
        self.drawn = drawn if drawn is not None else _Drawn()

    def px(self, u):
        return _pt(self.ox_mm + u * SCALE)

    def py(self, v):
        return _pt(self.oy_mm + v * SCALE)

    def paper(self, u, v):
        return (self.ox_mm + u * SCALE, self.oy_mm + v * SCALE)

    def _keep(self, owner, pts_mm, close=False):
        from shapely.geometry import LineString
        pts = list(pts_mm) + ([pts_mm[0]] if close else [])
        self.drawn.lines.append((owner, LineString(pts)))

    def poly(self, pts, close=True, width=0.6, dash=None, fill=None, owner=None):
        c = self.c
        c.setLineWidth(width)
        c.setDash(dash or [])
        p = c.beginPath()
        p.moveTo(self.px(pts[0][0]), self.py(pts[0][1]))
        for u, v in pts[1:]:
            p.lineTo(self.px(u), self.py(v))
        if close:
            p.close()
        if fill is not None:
            c.setFillColor(fill)
        c.drawPath(p, stroke=1, fill=1 if fill is not None else 0)
        c.setDash([])
        self._keep(owner, [self.paper(u, v) for u, v in pts], close)

    def rect(self, u0, v0, u1, v1, **kw):
        self.poly([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], **kw)

    def circle(self, u, v, r, width=0.5, dash=None, owner=None):
        from shapely.geometry import Point
        self.c.setLineWidth(width)
        self.c.setDash(dash or [])
        self.c.circle(self.px(u), self.py(v), _pt(r * SCALE), stroke=1, fill=0)
        self.c.setDash([])
        self.drawn.lines.append((owner, Point(self.paper(u, v)).buffer(r * SCALE, 64).exterior))

    def _word_box(self, x_mm, y_mm, words, size_mm, centre, angle):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from shapely import affinity
        from shapely.geometry import Polygon
        w = stringWidth(latin(words), drawing_font(), size_mm)
        x0 = -w / 2 if centre else 0.0
        box = Polygon([(x0, -0.22 * size_mm), (x0 + w, -0.22 * size_mm), (x0 + w, 0.75 * size_mm),
                       (x0, 0.75 * size_mm)])
        return affinity.translate(affinity.rotate(box, angle, origin=(0, 0)), x_mm, y_mm)

    def text(self, u, v, words, size_mm=2.4, centre=False, angle=0, kind="free", owner=None):
        c = self.c
        c.saveState()
        c.translate(self.px(u), self.py(v))
        c.rotate(angle)
        c.setFont(drawing_font(), _pt(size_mm))
        (c.drawCentredString if centre else c.drawString)(0, 0, latin(words))
        c.restoreState()
        x_mm, y_mm = self.paper(u, v)
        self.drawn.words.append((kind, words, self._word_box(x_mm, y_mm, words, size_mm, centre, angle), owner))

    def _line_pt(self, owner, x0, y0, x1, y1):
        self.c.line(x0, y0, x1, y1)
        self._keep(owner, [(x0 / PT_PER_MM, y0 / PT_PER_MM), (x1 / PT_PER_MM, y1 / PT_PER_MM)])

    def dim_h(self, u0, u1, v, words, off=-8.0, words_at="centre"):
        """A horizontal dimension between u0 and u1 at model v, drawn ``off`` paper mm away; its words centred over
        it, or (``words_at="right"``) set outside it, past u1's arrow, when they are wider than the span."""
        c, own = self.c, self.drawn.dimension_owner(words)
        y_pt = self.py(v) + _pt(off)
        c.setLineWidth(0.35)
        self._line_pt(own, self.px(u0), self.py(v), self.px(u0), y_pt - _pt(1.5 if off < 0 else -1.5))
        self._line_pt(own, self.px(u1), self.py(v), self.px(u1), y_pt - _pt(1.5 if off < 0 else -1.5))
        self._line_pt(own + " line", self.px(u0), y_pt, self.px(u1), y_pt)
        for u, s in ((u0, 1), (u1, -1)):
            self._line_pt(own, self.px(u), y_pt, self.px(u) + s * _pt(1.6), y_pt + _pt(0.7))
            self._line_pt(own, self.px(u), y_pt, self.px(u) + s * _pt(1.6), y_pt - _pt(0.7))
        c.saveState()
        c.setFont(drawing_font(), _pt(2.4))
        if words_at == "right":
            xm, ym, centre = self.px(u1) + _pt(1.5), y_pt - _pt(0.8), False
            c.drawString(xm, ym, latin(words))
        else:
            xm, ym, centre = (self.px(u0) + self.px(u1)) / 2, y_pt + _pt(0.9), True
            c.drawCentredString(xm, ym, latin(words))
        c.restoreState()
        self.drawn.words.append(("dimension", words, self._word_box(xm / PT_PER_MM, ym / PT_PER_MM, words, 2.4,
                                                                    centre, 0), own))
        self.drawn.dims.append({"view": self.name, "words": words, "along": "u", "model_mm": [u0, u1],
                                "at_mm": v})

    def dim_v(self, v0, v1, u, words, off=-8.0):
        c, own = self.c, self.drawn.dimension_owner(words)
        x_pt = self.px(u) + _pt(off)
        c.setLineWidth(0.35)
        self._line_pt(own, self.px(u), self.py(v0), x_pt - _pt(1.5 if off < 0 else -1.5), self.py(v0))
        self._line_pt(own, self.px(u), self.py(v1), x_pt - _pt(1.5 if off < 0 else -1.5), self.py(v1))
        self._line_pt(own + " line", x_pt, self.py(v0), x_pt, self.py(v1))
        for v, s in ((v0, 1), (v1, -1)):
            self._line_pt(own, x_pt, self.py(v), x_pt + _pt(0.7), self.py(v) + s * _pt(1.6))
            self._line_pt(own, x_pt, self.py(v), x_pt - _pt(0.7), self.py(v) + s * _pt(1.6))
        c.saveState()
        xm, ym = x_pt - _pt(0.9), (self.py(v0) + self.py(v1)) / 2
        c.translate(xm, ym)
        c.rotate(90)
        c.setFont(drawing_font(), _pt(2.4))
        c.drawCentredString(0, 0, latin(words))
        c.restoreState()
        self.drawn.words.append(("dimension", words, self._word_box(xm / PT_PER_MM, ym / PT_PER_MM, words, 2.4,
                                                                    True, 90), own))
        self.drawn.dims.append({"view": self.name, "words": words, "along": "v", "model_mm": [v0, v1],
                                "at_mm": u})


def write_plan_elevation(record: dict, path) -> dict:
    """The front elevation, the side section on the centre line and the plan, each at 1 : 2 on one A3 landscape
    page; the products drawn as outlines from their records; dimensions in mm; a calibration bar."""
    from reportlab.lib.colors import HexColor, black
    from reportlab.pdfgen import canvas
    g = C._g_from_record(record)
    P = {name: {k: f["value"] for k, f in vals.items()} for name, vals in record["products"].items()}
    t, W, D = g["t"], g["W"], g["D"]
    pal, lip, balm = P["palette"], P["lipstick"], P["balm"]
    back_top = g["back_wall_h"] + t
    head_top = back_top + g["header_h"]
    stick_col, pal_col, tray_fill = HexColor("#8A1C4A"), HexColor("#2B2F7A"), HexColor("#EEEEEE")
    c = canvas.Canvas(str(path), pagesize=(_pt(A3_LONG_MM), _pt(A3_SHORT_MM)), invariant=1, initialFontName=drawing_font())
    c.setTitle(latin("counter_tray_header %s - plan, front elevation, side section at 1:2" % C.VERSION))
    c.setStrokeColor(black)

    drawn = _Drawn()

    # -- front elevation: x across, z up -------------------------------------------------------------------------------
    fe = _View(c, 40.0, 24.0, drawn, "front elevation")
    u0 = lambda x: x + W / 2                                   # noqa: E731
    fe.rect(u0(-W / 2), 0, u0(W / 2), head_top, width=0.7)
    c.setStrokeColor(HexColor("#666666"))
    fe.poly([(u0(-W / 2), back_top), (u0(W / 2), back_top)], close=False, width=0.4, dash=[2, 2])
    for x0, x1 in ((-W / 2, -W / 2 + g["spine"]), (W / 2 - g["spine"], W / 2)):
        fe.rect(u0(x0), 0, u0(x1), back_top, width=0.4)
    c.setStrokeColor(pal_col)
    lid_z0, lid_z1 = g["p0_h"] + t, g["p0_h"] + t + pal["height_mm"] * g["cos"]
    fe.rect(u0(-pal["width_mm"] / 2), lid_z0, u0(pal["width_mm"] / 2), lid_z1, width=0.7)
    fe.text(u0(0), (lid_z0 + lid_z1) / 2, "front palette lid 190 x 120 (leaning %g deg)" % g["theta_deg"],
            centre=True)
    c.setStrokeColor(black)
    fe.rect(u0(-W / 2), 0, u0(W / 2), g["front_skin_h"] + t, width=0.7, fill=tray_fill)
    c.setStrokeColor(stick_col)
    for x in g["lip_x"]:
        r = lip["diameter_mm"] / 2
        fe.rect(u0(x - r), max(t, g["front_skin_h"] + t), u0(x + r), t + lip["height_mm"], width=0.5)
        fe.poly([(u0(x - r), t + lip["body_mm"]), (u0(x + r), t + lip["body_mm"])], close=False, width=0.35)
    for x in g["balm_x"]:
        r = balm["diameter_mm"] / 2
        fe.rect(u0(x - r), g["front_skin_h"] + t, u0(x + r), t + balm["height_mm"], width=0.6,
                fill=HexColor("#FFFFFF"))
        fe.poly([(u0(x - r), t + balm["body_mm"]), (u0(x + r), t + balm["body_mm"])], close=False, width=0.35)
    c.setStrokeColor(black)
    c.setFillColor(black)
    fe.dim_h(u0(-W / 2), u0(W / 2), 0, "%g" % W, off=-7)
    fe.dim_v(0, head_top, u0(-W / 2), "%.2f" % head_top, off=-14)
    fe.dim_v(0, back_top, u0(-W / 2), "back wall %.2f" % back_top, off=-7)
    fe.dim_v(back_top, head_top, u0(W / 2), "header %g" % g["header_h"], off=7)
    fe.dim_v(0, g["front_skin_h"] + t, u0(W / 2), "%g" % (g["front_skin_h"] + t), off=14)
    # above the lipsticks' tops (the sheet verifier's minor: at off 4 the first lipstick's top ran through its words)
    fe.dim_h(u0(g["balm_x"][0]), u0(g["balm_x"][1]), t + balm["height_mm"], "pitch %g" % g["pitch"], off=10)
    fe.text(0, head_top + 6, "FRONT ELEVATION  1 : 2", size_mm=3.4)

    # -- side section on the centre line: y to the right (front at the left), z up -------------------------------------
    ss = _View(c, 222.0, 24.0, drawn, "side section")
    c.setStrokeColor(black)
    ss.rect(0, 0, D, t, width=0.5, fill=tray_fill)
    ss.rect(0, 0, g["spine"], g["front_skin_h"] + t, width=0.6, fill=tray_fill)
    ss.rect(g["back_inner_y"], 0, D, back_top, width=0.6, fill=tray_fill)
    ss.rect(D - t, back_top, D, head_top, width=0.6)
    ss.rect(D - 2 * t, back_top, D - t, head_top, width=0.6)
    c.setStrokeColor(HexColor("#666666"))
    ss.poly([(g["skin_y0"], g["front_skin_h"] + t), (g["skin_y1"], back_top)], close=False, width=0.4, dash=[2, 2])
    # the side wall's label above the drawing, on a leader down to the dashed top edge in front of the palettes
    from reportlab.pdfbase.pdfmetrics import stringWidth
    k = 0.62
    lead = (g["skin_y0"] + k * (g["skin_y1"] - g["skin_y0"]), g["front_skin_h"] + t + k * (back_top - g["front_skin_h"]
                                                                                            - t))
    side_words = "dashed: the side wall's top edge (beyond)"
    side_w = stringWidth(latin(side_words), drawing_font(), 2.2) / SCALE
    c.setFillColor(black)
    ss.text(4, 168, side_words, size_mm=2.2, owner="leader side wall")
    ss.poly([(4 + side_w + 1, 169), lead], close=False, width=0.3, owner="leader side wall")
    c.setStrokeColor(black)
    ins = g["insert"]
    tube = [(g["f_y"], 0), (g["f_y"], g["f_h"] + t), (g["b_y"], g["bed_low_h"] + t), (g["r_y"], g["r_h"] + t),
            (g["r_y"], 0)]
    ss.poly([(y, z) for y, z in tube], width=0.6)
    # D-D13-2: the gusset closing each of the tube's ends square, in its back-bottom corner on the floor's top — beyond
    # the centre line, so dashed as the side wall's edge is
    c.setStrokeColor(HexColor("#666666"))
    ss.poly([(g["r_y"], t), (g["r_y"], t + ins["gusset_up_mm"]), (g["r_y"] - ins["gusset_along_mm"], t)], width=0.4,
            dash=[2, 1], owner="gusset (beyond)")
    c.setStrokeColor(black)
    n, u = (g["cos"], -g["sin"]), (g["sin"], g["cos"])
    c.setStrokeColor(pal_col)
    for a0, a1 in ((0, pal["thickness_mm"]), (pal["thickness_mm"], 2 * pal["thickness_mm"])):
        corners = [(g["p0_y"] + a * n[0] + b * u[0], g["p0_h"] + t + a * n[1] + b * u[1])
                   for a, b in ((a0, 0), (a1, 0), (a1, pal["height_mm"]), (a0, pal["height_mm"]))]
        ss.poly(corners, width=0.7)
    c.setStrokeColor(black)
    for y0, d, hh in ((g["front_plate_y0"], g["front_plate_d"], g["front_plate_h"]),
                      (g["back_plate_y1"] - g["back_plate_d"], g["back_plate_d"], g["back_plate_h"])):
        ss.poly([(y0, t), (y0, t + hh), (y0 + d, t + hh), (y0 + d, t)], close=False, width=0.6)
    c.setStrokeColor(stick_col)
    for yc, rec in ((g["balm_y"], balm), (g["lip_y"], lip)):
        r = rec["diameter_mm"] / 2
        ss.rect(yc - r, t, yc + r, t + rec["height_mm"], width=0.6)
        ss.poly([(yc - r, t + rec["body_mm"]), (yc + r, t + rec["body_mm"])], close=False, width=0.35)
    c.setStrokeColor(HexColor("#C08000"))
    eye = (-float(record["owner_provisional"]["eye_front_mm"]["value"]),
           float(record["owner_provisional"]["eye_height_mm"]["value"]))
    for ty_, tz_ in ((g["balm_y"] - balm["diameter_mm"] / 2, t + balm["height_mm"] - 25.0),
                     (g["lip_y"] - lip["diameter_mm"] / 2, t + lip["height_mm"] - 25.0),
                     (g["p0_y"] + (t + lip["height_mm"] - g["p0_h"] - t) / g["cos"] * u[0], t + lip["height_mm"])):
        k = (0 - ty_) / (eye[0] - ty_)
        ss.poly([(ty_, tz_), (0, tz_ + k * (eye[1] - tz_))], close=False, width=0.35, dash=[1.5, 1])
    c.setStrokeColor(black)
    c.setFillColor(black)
    ss.text(-2, 150, "rays to the eye (500 in front, 350 up)", size_mm=2.2, angle=0)
    ss.dim_h(0, D, 0, "%g" % D, off=-7)
    # behind the back leg (D-D13-2: at off 6 its words crossed the gusset's long edge, dashed in front of the back leg)
    ss.dim_v(0, g["bed_low_h"] + t, g["b_y"], "slot floor %g (+%g board)" % (g["bed_low_h"], t), off=12)
    ss.dim_v(0, back_top, D, "%.2f" % back_top, off=8)
    ss.dim_v(back_top, head_top, D, "%g" % g["header_h"], off=8)
    ss.dim_h(g["balm_y"], g["lip_y"], t + lip["height_mm"], "rows %g" % (g["lip_y"] - g["balm_y"]), off=6)
    # the plates' heights from the floor's top, as the owner's numbers are (the sheet verifier's minor: they ran from
    # the counter, a board longer than their words)
    ss.dim_v(t, t + g["front_plate_h"], g["front_plate_y0"], "%g" % g["front_plate_h"], off=-4)
    ss.dim_v(t, t + g["back_plate_h"], g["back_plate_y1"], "%g" % g["back_plate_h"], off=4)
    pal_words = "two palettes, %g deg lean, top %.2f" % (g["theta_deg"], g["stack_top_h"] + t)
    pal_w = stringWidth(latin(pal_words), drawing_font(), 2.2) / SCALE      # model mm
    ss.text(D - 2 * t - 4 - pal_w, g["stack_top_h"] + t + 6, pal_words, size_mm=2.2)   # ends before the header
    ss.text(0, head_top + 6, "SIDE SECTION ON THE CENTRE LINE  1 : 2", size_mm=3.4)

    # -- plan: x across, y up the page from the front -------------------------------------------------------------------
    pv = _View(c, 40.0, 184.0, drawn, "plan")
    pu = lambda x: x + W / 2                                   # noqa: E731
    pv.rect(pu(-W / 2), 0, pu(W / 2), D, width=0.7)
    pv.rect(pu(-W / 2 + g["spine"]), g["spine"], pu(W / 2 - g["spine"]), g["back_inner_y"], width=0.35, dash=[2, 1])
    for y0, d in ((g["front_plate_y0"], g["front_plate_d"]), (g["back_plate_y1"] - g["back_plate_d"],
                                                              g["back_plate_d"])):
        pv.rect(pu(-g["plate_len"] / 2), y0, pu(g["plate_len"] / 2), y0 + d, width=0.45)
    pv.rect(pu(-ins["width_mm"] / 2), g["f_y"], pu(ins["width_mm"] / 2), g["r_y"], width=0.45)
    c.setStrokeColor(pal_col)
    pv.rect(pu(-pal["width_mm"] / 2), g["stack_front_y"], pu(pal["width_mm"] / 2), g["stack_rear_y"], width=0.6)
    c.setStrokeColor(black)
    for xs, yc, hole, rec in ((g["balm_x"], g["balm_y"], g["balm_hole"], balm),
                              (g["lip_x"], g["lip_y"], g["lip_hole"], lip)):
        for x in xs:
            if g.get("hole_shape", "circle") == "square":
                pv.rect(pu(x) - hole / 2, yc - hole / 2, pu(x) + hole / 2, yc + hole / 2, width=0.35)
            else:
                pv.circle(pu(x), yc, hole / 2, width=0.35)
            c.setStrokeColor(stick_col)
            pv.circle(pu(x), yc, rec["diameter_mm"] / 2, width=0.5)
            c.setStrokeColor(black)
    c.setFillColor(black)
    pv.dim_v(0, D, pu(-W / 2), "%g" % D, off=-7)
    pv.dim_h(pu(g["lip_x"][0]), pu(g["lip_x"][1]), D, "%g" % g["pitch"], off=5)
    # its words wider than its 8 mm span: set outside it, past its right arrow (the sheet verifier's minor)
    pv.dim_h(pu(g["balm_x"][0]), pu(g["lip_x"][0]), D, "offset %g" % g["offset"], off=11, words_at="right")
    pv.dim_v(g["balm_y"], g["lip_y"], pu(W / 2), "%g" % (g["lip_y"] - g["balm_y"]), off=6)
    pv.dim_v(0, g["balm_y"], pu(W / 2), "%g" % g["balm_y"], off=12)
    # each row's label on its own plate, in the free end the half-pitch offset leaves (clear of every hole)
    Lh = g["plate_len"] / 2
    for yc, xs, hole, words in ((g["balm_y"], g["balm_x"], g["balm_hole"], "%d balms, holes %g"),
                                (g["lip_y"], g["lip_x"], g["lip_hole"], "%d lipsticks, holes %g")):
        words = words % (len(xs), hole)
        w = stringWidth(latin(words), drawing_font(), 1.6) / SCALE
        free = (max(xs) + hole / 2, Lh) if Lh - max(xs) >= Lh + min(xs) else (-Lh, min(xs) - hole / 2)
        pv.text(pu((free[0] + free[1]) / 2 - w / 2), yc - 1.0, words, size_mm=1.6)
    pv.text(pu(0), (g["stack_front_y"] + g["stack_rear_y"]) / 2, "palettes (plan of the leaning stack)",
            centre=True, size_mm=2.0)
    pv.text(0, D + 30, "PLAN  1 : 2", size_mm=3.4)

    # -- title, notes, calibration bar -----------------------------------------------------------------------------------
    c.setFont(drawing_font(), _pt(4.2))
    c.drawString(_pt(20), _pt(A3_SHORT_MM - 12), latin("counter_tray_header %s PROVISIONAL - the family counter "
                                                       "display (D-D12-2) - plan, front elevation, side section at "
                                                       "1 : 2 on A3" % C.VERSION))
    c.setFont(drawing_font(), _pt(2.8))
    notes = [
        "Products drawn as outlines from their records: palette 190 x 120 x 12 (brief 124), lipstick 80 x dia 20 "
        "(cap 40, body 40, D-D11-7), balm 70 x dia 18 (cap 30, body 40, D-D11-8). Dimensions in mm, heights over "
        "the counter.",
        "Back wall %.2f over the counter = the leaning stack's top (solved from the slot), as the owner ruled it "
        "(D-D13-1: 183.62 over the counter; his 'about 245' corrected, not a departure). Board %g mm E-flute." % (
            back_top, t),
        "The slot insert's tube is closed square by a glued diagonal gusset at each end (D-D13-2), %g up the back "
        "leg and %g along the base: dashed in the section (beyond the centre line)." % (
            g["insert"]["gusset_up_mm"], g["insert"]["gusset_along_mm"]),
        "Print at 100 %, no fit. At 1 : 2 the bar below is 25 mm on paper and stands for 50 mm of the display.",
        "Third-angle: the plan above the front elevation (front at the foot of the plan); the section on the centre "
        "line, the front at its left.",
    ]
    import textwrap
    rows = [part for line in notes for part in textwrap.wrap(line, 118)]
    for i, line in enumerate(rows):
        c.drawString(_pt(222), _pt(262 - 4.2 * i), latin(line))
    _bar(c, _pt(222), _pt(262 - 4.2 * len(rows) - 8), 50.0, "50 mm at 1:2 (25 mm on paper)", paper_mm=25.0)
    c.showPage()
    c.save()
    return {"page_mm": [A3_LONG_MM, A3_SHORT_MM], "scale": "1:2",
            "views": ["front elevation", "side section on the centre line", "plan"],
            "labels": drawn.clashes(), "dimensions": drawn.dims}


def render_png(pdf_path, png_path, dpi=150) -> list:
    import fitz
    doc = fitz.open(str(pdf_path))
    pix = doc[0].get_pixmap(dpi=dpi)
    pix.save(str(png_path))
    size = [pix.irect[2], pix.irect[3]]
    doc.close()
    return size
