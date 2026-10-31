"""ES3083 BACK LABEL — DRAFT-TIER artifact, labelled as such on its face.

Honest ceiling per es3083_back_label_prerequisites.json 1.1 and the
clearance-sheet answers (owner_blocker_clearance_ingestion.json):
  - every owner-known field is REAL (brand words, item no ES3083);
  - every supplier-gated field renders as a marked [SUPPLIER-GATED]
    placeholder (INCI, fill weight, standard, market approval);
  - B1: the EAN is a marked PLACEHOLDER — the recovered vendor EAN is
    NOT printed; B2: responsible person / distributor is a marked
    placeholder.
  - fields adjudicated NO (ZHEZHUANG approval number, supplier
    identity) do NOT appear, even as placeholders for their values.

Geometry PARAMETRIC on es3083_artwork_geometry_substrate.json:
printed area 49.50 x 49.50 mm, die/bleed 55.00 x 55.00 mm (MEASURED);
the 2.0 pt keyline is the vendor label's own, recorded in
es3083_back_label_prerequisites.json geometry. Face: SET_FACE (Crimson
Text Regular, OFL). Text is LIVE in the SVG — never outlined.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
os.chdir(ROOT)
REPO = os.path.dirname(ROOT)

SUB = json.load(open("docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json"))
M = SUB["MEASURED_VECTOR_FROM_SOURCE"]
PW, PH = M["back_label_printed_mm"]
DW, DH = M["back_label_die_mm"]
COL = SUB["LABEL_SHEET_CONSTRUCTION_2026_08_14"]["treatment_colours_sRGB_from_measured_Lab"]
BLACK = tuple(COL["text_black"])
P627 = tuple(COL["pantone_627C"])
GREY = (120, 120, 120)
T = SUB["TYPEFACE_SPEC_2026_08_14"]
FONT = os.path.join(REPO, T["SET_FACE"]["file"])
FAMILY = T["SET_FACE"]["family"]

KEYLINE_PT = 2.0            # vendor label keyline, prerequisites 1.1 geometry
KEYLINE_MM = KEYLINE_PT * 25.4 / 72.0
OX, OY = (DW - PW) / 2.0, (DH - PH) / 2.0   # printed area centred in die

PAD = 2.6                    # inner pad, design choice
CX0, CX1 = OX + PAD, OX + PW - PAD
CW = CX1 - CX0

BODY = [
    # (text, em_mm, colour, gap_before_mm)
    ("INGREDIENTS (INCI): [SUPPLIER-GATED]", 1.75, BLACK, 0.0),
    ("pending supplier formulation confirmation", 1.55, GREY, 0.4),
    ("NET WT: [SUPPLIER-GATED] g", 1.75, BLACK, 1.15),
    ("MANUFACTURE STANDARD: [SUPPLIER-GATED]", 1.75, BLACK, 1.15),
    ("MARKET APPROVAL: [SUPPLIER-GATED]", 1.75, BLACK, 1.15),
    ("RESPONSIBLE PERSON / DISTRIBUTOR:", 1.75, BLACK, 1.15),
    ("[PLACEHOLDER — owner to supply]", 1.65, GREY, 0.4),
    ("ITEM NO. ES3083", 1.75, BLACK, 1.15),
]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def build_elements():
    """One shared element list; both backends consume it. mm throughout."""
    els = []
    els.append(("die", 0, 0, DW, DH))
    els.append(("keyline", OX, OY, PW, PH))
    # DRAFT banner — the draft tier declared on the artifact's face,
    # sitting fully INSIDE the keyline
    bh = 4.6
    els.append(("fillrect", OX + KEYLINE_MM, OY + KEYLINE_MM,
                PW - 2 * KEYLINE_MM, bh, GREY))
    base = OY + KEYLINE_MM + bh
    els.append(("ctext", "DRAFT — NOT FOR PRODUCTION", DW / 2,
                base - bh / 2 + 1.05, 2.4, 0.5, (255, 255, 255)))
    # brand block (established words only)
    els.append(("ctext", "BBROSE", DW / 2, base + 5.4, 3.6, 0.8, BLACK))
    els.append(("ctext", "EYE SHADOW — SOMBRA DE OJOS", DW / 2,
                base + 8.8, 1.9, 0.3, P627))
    els.append(("hline", CX0, base + 10.7, CX1, base + 10.7, P627, 0.2))
    # body stack, ranged left
    y = base + 12.9
    for s, em, col, gap in BODY:
        y += gap
        els.append(("ltext", s, CX0, y, em, col))
        y += em * 1.42
    # EAN placeholder — schematic bars, struck through, marked; the whole
    # block is held above the bottom keyline (caption included)
    bx, by, bw, bhh = CX1 - 17.0, OY + PH - 12.6, 15.0, 6.2
    els.append(("bars", bx, by, bw, bhh))
    els.append(("dline", bx - 0.8, by + bhh + 0.6, bx + bw + 0.8, by - 0.6,
                (150, 30, 30), 0.35))
    els.append(("ltext", "[PLACEHOLDER EAN]", bx - 0.2, by + bhh + 2.2,
                1.45, BLACK))
    els.append(("ltext", "ownership unconfirmed", bx - 0.2, by + bhh + 4.2,
                1.3, GREY))
    assert by + bhh + 4.2 + 1.3 < OY + PH - KEYLINE_MM, "EAN block overflows"
    return els


def bar_rects(bx, by, bw, bh):
    """Deterministic schematic bars — NOT an encoding of any number."""
    widths = [3, 1, 2, 1, 1, 3, 1, 2, 3, 1, 1, 2, 1, 3, 1, 2, 1, 1]
    unit = bw / (sum(widths) + len(widths) - 1)
    rects, x = [], bx
    for i, w in enumerate(widths):
        if i % 2 == 0:
            rects.append((x, by, w * unit, bh))
        x += (w + 1) * unit
    return rects


def measure_guard():
    f = {}
    for s, em, _c, _g in BODY:
        fnt = ImageFont.truetype(FONT, round(em * 40))
        w_mm = fnt.getlength(s) / 40.0
        assert w_mm <= CW, ("body line overflows printed width", s, w_mm, CW)
    return f


def render_png(els, out, dpi=800):
    k = dpi / 25.4
    img = Image.new("RGB", (round(DW * k), round(DH * k)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for e in els:
        kind = e[0]
        if kind == "die":
            _, x, y, w, h = e
            for i in range(0, round(w * k), round(1.6 * k / 2)):
                d.line([x * k + i, y * k, x * k + i + 0.8 * k / 2, y * k],
                       fill=(180, 180, 180), width=2)
                d.line([x * k + i, (y + h) * k - 1, x * k + i + 0.8 * k / 2,
                        (y + h) * k - 1], fill=(180, 180, 180), width=2)
            for i in range(0, round(h * k), round(1.6 * k / 2)):
                d.line([x * k, y * k + i, x * k, y * k + i + 0.8 * k / 2],
                       fill=(180, 180, 180), width=2)
                d.line([(x + w) * k - 1, y * k + i, (x + w) * k - 1,
                        y * k + i + 0.8 * k / 2], fill=(180, 180, 180), width=2)
        elif kind == "keyline":
            _, x, y, w, h = e
            d.rectangle([x * k, y * k, (x + w) * k, (y + h) * k],
                        outline=BLACK, width=max(1, round(KEYLINE_MM * k)))
        elif kind == "fillrect":
            _, x, y, w, h, col = e
            d.rectangle([x * k, y * k, (x + w) * k, (y + h) * k], fill=col)
        elif kind == "hline":
            _, x1, y1, x2, y2, col, wmm = e
            d.line([x1 * k, y1 * k, x2 * k, y2 * k], fill=col,
                   width=max(1, round(wmm * k)))
        elif kind == "dline":
            _, x1, y1, x2, y2, col, wmm = e
            d.line([x1 * k, y1 * k, x2 * k, y2 * k], fill=col,
                   width=max(1, round(wmm * k)))
        elif kind == "ctext":
            _, s, cx, yb, em, tr, col = e
            fnt = ImageFont.truetype(FONT, round(em * k))
            trk = tr * k
            tw = sum(fnt.getlength(ch) for ch in s) + trk * (len(s) - 1)
            x = cx * k - tw / 2
            for ch in s:
                d.text((x, yb * k), ch, font=fnt, fill=col, anchor="ls")
                x += fnt.getlength(ch) + trk
        elif kind == "ltext":
            _, s, x, yb, em, col = e
            fnt = ImageFont.truetype(FONT, round(em * k))
            d.text((x * k, yb * k), s, font=fnt, fill=col, anchor="ls")
        elif kind == "bars":
            _, bx, by, bw, bh = e
            for (x, y, w, h) in bar_rects(bx, by, bw, bh):
                d.rectangle([x * k, y * k, (x + w) * k, (y + h) * k],
                            fill=BLACK)
    img.save(out, dpi=(dpi, dpi))
    return img


def render_svg(els, out):
    L = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (DW, DH, DW, DH),
        '<!-- ES3083 back label, DRAFT TIER (declared on face). Parametric '
        'on es3083_artwork_geometry_substrate.json: printed %g x %g, die '
        '%g x %g MEASURED. Face %s (SET_FACE, OFL). LIVE text, never '
        'outlined. Placeholder EAN encodes NOTHING. -->'
        % (PW, PH, DW, DH, FAMILY),
        '<rect width="%g" height="%g" fill="white"/>' % (DW, DH),
    ]
    for e in els:
        kind = e[0]
        if kind == "die":
            _, x, y, w, h = e
            L.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" '
                     'stroke="rgb(180,180,180)" stroke-width="0.15" '
                     'stroke-dasharray="1.6 0.8"/>' % (x, y, w, h))
        elif kind == "keyline":
            _, x, y, w, h = e
            L.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" '
                     'stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                     % (x, y, w, h, *BLACK, KEYLINE_MM))
        elif kind == "fillrect":
            _, x, y, w, h, col = e
            L.append('<rect x="%g" y="%g" width="%g" height="%g" '
                     'fill="rgb(%d,%d,%d)"/>' % (x, y, w, h, *col))
        elif kind in ("hline", "dline"):
            _, x1, y1, x2, y2, col, wmm = e
            L.append('<line x1="%g" y1="%g" x2="%g" y2="%g" '
                     'stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                     % (x1, y1, x2, y2, *col, wmm))
        elif kind == "ctext":
            _, s, cx, yb, em, tr, col = e
            L.append('<text x="%g" y="%g" font-family="%s" font-size="%g" '
                     'letter-spacing="%g" text-anchor="middle" '
                     'fill="rgb(%d,%d,%d)">%s</text>'
                     % (cx - tr / 2, yb, FAMILY, em, tr, *col, esc(s)))
        elif kind == "ltext":
            _, s, x, yb, em, col = e
            L.append('<text x="%g" y="%g" font-family="%s" font-size="%g" '
                     'fill="rgb(%d,%d,%d)">%s</text>'
                     % (x, yb, FAMILY, em, *col, esc(s)))
        elif kind == "bars":
            _, bx, by, bw, bh = e
            for (x, y, w, h) in bar_rects(bx, by, bw, bh):
                L.append('<rect x="%g" y="%g" width="%g" height="%g" '
                         'fill="rgb(%d,%d,%d)"/>' % (x, y, w, h, *BLACK))
    L.append("</svg>")
    open(out, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    measure_guard()
    els = build_elements()
    img = render_png(els, f"{HERE}/es3083_back_label_DRAFT.png")
    render_svg(els, f"{HERE}/es3083_back_label_DRAFT.svg")
    print(f"back label DRAFT: PNG {img.width}x{img.height}px + SVG written")
