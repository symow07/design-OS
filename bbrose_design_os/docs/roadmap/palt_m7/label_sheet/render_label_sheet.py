"""ES3083 shade-label sheet — PARAMETRIC renderer.

BINDING CONSTRUCTION RULES (recorded in the geometry substrate,
TYPEFACE_SPEC / LABEL_SHEET_CONSTRUCTION blocks, and restated here so
the artifact itself carries them):

1. EVERY millimetre value is read from
   docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json.
   No numeric literal for any mm dimension appears below — a caliper
   session edits the record and re-runs this script.
2. THE TYPEFACE IS A PARAMETER — the spec dict from the substrate's
   TYPEFACE_SPEC block. Changing the family is one field there.
3. THE FIT RULE IS A CONSTRAINT — solved against the set face's own
   metrics every run. No solved size is a constant anywhere.
4. NO TYPE IS OUTLINED. The SVG and PDF carry live text; the PNG is a
   raster render, which is not an outline conversion.
5. Frames come from pitch x count; margins are derived and asserted
   equal on both axes' ends before anything is drawn.

The twelve names are READ from es3083_shade_authority.json (1.3).
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
os.chdir(ROOT)
REPO = os.path.dirname(ROOT)

SUB = json.load(open("docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json"))
REC = json.load(open("docs/roadmap/palt_m6/es3083_shade_authority.json"))
assert REC["record_type"] == "es3083_shade_authority/1.3"
NAMES = [s["name"] for s in REC["shades"]]

M = SUB["MEASURED_VECTOR_FROM_SOURCE"]
C = SUB["LABEL_SHEET_CONSTRUCTION_2026_08_14"]
T = SUB["TYPEFACE_SPEC_2026_08_14"]
LP = C["layout_parameters"]

LW, LH = M["shade_name_label_mm"]
PX, PY = M["shade_label_pitch_mm"]
SW, SH = M["shade_label_sheet_mm"]
COLS, ROWS = C["columns"], C["rows"]

# rule 5 — margins derived from pitch x count, asserted symmetric
grid_w = (COLS - 1) * PX + LW
grid_h = (ROWS - 1) * PY + LH
mx, my = (SW - grid_w) / 2.0, (SH - grid_h) / 2.0
assert abs(mx - my) < 0.005, (mx, my)  # the vendor sheet is 10/10

names_seq = list(NAMES)
if C["allocation_24_labels_12_shades"]["duplicate_names_fill_second_half"]:
    names_seq = NAMES + NAMES
assert len(names_seq) == COLS * ROWS


def solve_size(font_path, dpi):
    """Rule 3 — the fit rule as a constraint against real metrics."""
    mmpx = dpi / 25.4
    max_w = (LW - 2 * LP["pad_x_mm"]) * mmpx
    max_h = (LH - 2 * LP["pad_y_mm"]) * mmpx
    lo, hi, best = 4, int(LH * mmpx), 4
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(font_path, mid)
        asc, desc = f.getmetrics()
        if max(f.getlength(n) for n in NAMES) <= max_w and (asc + desc) <= max_h:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


#: DE-CONFOUNDED SET, design stated (2026-08-14). Variables: alignment
#: {centre,left}, keyline {no,yes}, ink {black,627C}, ground {white,621C}.
#: Isolating pairs — each variable judged ALONE:
#:   ALIGNMENT: T1 vs T4   (black, no keyline, ground white on both)
#:   KEYLINE:   T4 vs T2   (ranged left, black on both)
#:   INK:       T1 vs T3   (centred, no keyline on both)
#:   GROUND:    T1 vs T5   (identical layout; 621 C tinted ground — the
#:              stock is UNDETERMINED and this cell shows a question)
#: Cells NOT rendered, and why: centred+keyline, left+627C, left+keyline+
#: 627C, centred+keyline+627C — every variable already has one clean
#: isolating pair, and second-order interactions (ink x keyline, ink x
#: alignment) decide nothing at this stage; rendering them would imply a
#: choice space nobody has opened.
TREATMENTS = {
    "T1_centred_black": {"align": "centre", "keyline": False,
                         "colour": C["treatment_colours_sRGB_from_measured_Lab"]["text_black"],
                         "cost": "one ink, no frame: cheapest; no added registration constraint"},
    "T2_left_keyline": {"align": "left", "keyline": True,
                        "colour": C["treatment_colours_sRGB_from_measured_Lab"]["text_black"],
                        "cost": "one ink + printed keyline: die-cut misregistration becomes visible, tightening the print tolerance the vendor must hold"},
    "T3_centred_627C": {"align": "centre", "keyline": False,
                        "colour": C["treatment_colours_sRGB_from_measured_Lab"]["pantone_627C"],
                        "cost": "one SPOT ink (PANTONE 627 C): a spot plate instead of process black; can share the case's existing 627 C plate if printed in the same works"},
    "T4_left_black": {"align": "left", "keyline": False,
                      "colour": C["treatment_colours_sRGB_from_measured_Lab"]["text_black"],
                      "cost": "identical to T1 — alignment is FREE: no ink change, no tolerance change"},
    "T5_stock_question_621C_ground": {
        "align": "centre", "keyline": False,
        "colour": C["treatment_colours_sRGB_from_measured_Lab"]["text_black"],
        "ground": C["treatment_colours_sRGB_from_measured_Lab"]["pantone_621C"],
        "cost": "STOCK UNDETERMINED — this cell shows the white-stock assumption by breaking it; a tinted ground costs either a flood plate (per-ink) or tinted stock (a purchasing fact), and neither is chosen here"},
}


def render_png(font_path, dpi, treatment, out):
    mmpx = dpi / 25.4
    t = TREATMENTS[treatment]
    sz = solve_size(font_path, dpi)
    f = ImageFont.truetype(font_path, sz)
    asc, desc = f.getmetrics()
    ground = tuple(t.get("ground",
                         SUB["STOCK_PARAMETER_2026_08_14"]["assumed_stock_srgb"]))
    img = Image.new("RGB", (int(SW * mmpx), int(SH * mmpx)), ground)
    d = ImageDraw.Draw(img)
    for i, name in enumerate(names_seq):
        r, c = divmod(i, COLS)
        x0 = (mx + c * PX) * mmpx
        y0 = (my + r * PY) * mmpx
        x1, y1 = x0 + LW * mmpx, y0 + LH * mmpx
        if t["keyline"]:
            klw = max(1, round(LP["keyline_weight_pt"] / 72.0 * dpi))
            d.rectangle([x0, y0, x1, y1], outline=(120, 120, 120), width=klw)
        else:
            d.rectangle([x0, y0, x1, y1], outline=(225, 225, 225), width=1)
        ty = y0 + (LH * mmpx - (asc + desc)) / 2
        if t["align"] == "centre":
            tx = x0 + (LW * mmpx - f.getlength(name)) / 2
        else:
            tx = x0 + LP["pad_x_mm"] * mmpx
        d.text((tx, ty), name, font=f, fill=tuple(t["colour"]))
    img.save(out, dpi=(dpi, dpi))
    return sz


def write_svg(font_path, family, treatment, out):
    """Live-text vector — rule 4. Sizes in mm; text is <text>."""
    dpi = 72.0
    sz_px = solve_size(font_path, 720) / 10.0  # solve at 720dpi, sz in pt
    f = ImageFont.truetype(font_path, int(sz_px * 10))
    asc, desc = f.getmetrics()
    box_h_pt = (asc + desc) / 10.0
    t = TREATMENTS[treatment]
    col = "rgb(%d,%d,%d)" % tuple(t["colour"])
    pt2mm = 25.4 / 72.0
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (SW, SH, SW, SH),
        '<!-- parametric: all mm from es3083_artwork_geometry_substrate.json; '
        'text is LIVE, never outlined -->',
    ]
    for i, name in enumerate(names_seq):
        r, c = divmod(i, COLS)
        x0, y0 = mx + c * PX, my + r * PY
        stroke = ('stroke="#787878" stroke-width="%g"' % (LP["keyline_weight_pt"] * pt2mm)
                  ) if t["keyline"] else 'stroke="#e1e1e1" stroke-width="0.05"'
        lines.append('<rect x="%g" y="%g" width="%g" height="%g" fill="none" %s/>'
                     % (x0, y0, LW, LH, stroke))
        asc_mm = asc / 10.0 * pt2mm
        box_mm = box_h_pt * pt2mm
        ty = y0 + (LH - box_mm) / 2 + asc_mm
        if t["align"] == "centre":
            anchor, tx = "middle", x0 + LW / 2
        else:
            anchor, tx = "start", x0 + LP["pad_x_mm"]
        lines.append('<text x="%g" y="%g" font-family="%s" font-size="%gmm" '
                     'text-anchor="%s" fill="%s">%s</text>'
                     % (tx, ty, family, sz_px * pt2mm, anchor, col, name))
    lines.append("</svg>")
    open(out, "w").write("\n".join(lines) + "\n")
    return sz_px


def write_pdf(font_path, treatment, out):
    """Live embedded text via reportlab — a real PDF, named .pdf."""
    from reportlab.lib.units import mm as RMM
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont as RLTTF
    from reportlab.pdfgen import canvas
    pdfmetrics.registerFont(RLTTF("SetFace", font_path))
    sz_pt = solve_size(font_path, 720) / 10.0
    f = ImageFont.truetype(font_path, int(sz_pt * 10))
    asc, desc = f.getmetrics()
    cv = canvas.Canvas(out, pagesize=(SW * RMM, SH * RMM))
    t = TREATMENTS[treatment]
    cv.setFillColorRGB(*[v / 255 for v in t["colour"]])
    cv.setStrokeColorRGB(0.47, 0.47, 0.47)
    for i, name in enumerate(names_seq):
        r, c = divmod(i, COLS)
        x0 = (mx + c * PX) * RMM
        # PDF origin bottom-left
        y0 = (SH - my - r * PY - LH) * RMM
        if t["keyline"]:
            cv.setLineWidth(LP["keyline_weight_pt"])
            cv.rect(x0, y0, LW * RMM, LH * RMM)
        box_pt = (asc + desc) / 10.0
        base = y0 + (LH * RMM - box_pt) / 2 + (desc / 10.0)
        cv.setFont("SetFace", sz_pt)
        w = cv.stringWidth(name, "SetFace", sz_pt)
        tx = x0 + (LW * RMM - w) / 2 if t["align"] == "centre" \
            else x0 + LP["pad_x_mm"] * RMM
        cv.drawString(tx, base, name)
    cv.save()
    return sz_pt


if __name__ == "__main__":
    OUT = os.path.join(HERE)
    set_face = os.path.join(REPO, T["SET_FACE"]["file"])
    test_face = os.path.join(REPO, T["TEST_FACE"]["file"])
    fam = T["SET_FACE"]["family"]
    report = {}
    for tr in TREATMENTS:
        p = f"{OUT}/es3083_label_sheet_{tr}.png"
        sz = render_png(set_face, 600, tr, p)
        report[tr] = {"png": p, "solved_px_600dpi": sz,
                      "solved_pt": round(sz * 72 / 600, 2)}
        write_svg(set_face, fam, tr, f"{OUT}/es3083_label_sheet_{tr}.svg")
    write_pdf(set_face, "T1_centred_black",
              f"{OUT}/es3083_label_sheet_T1_centred_black.pdf")
    # substitution PROOF — TEST FACE, marked, out of the deliverable set
    os.makedirs(f"{OUT}/substitution_test", exist_ok=True)
    tsz = render_png(test_face, 600, "T1_centred_black",
                     f"{OUT}/substitution_test/"
                     f"TEST_NOT_DELIVERABLE_merriweather_T1.png")
    report["TEST_merriweather"] = {"solved_px_600dpi": tsz,
                                   "solved_pt": round(tsz * 72 / 600, 2)}
    print(json.dumps(report, indent=1))
