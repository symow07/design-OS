"""ES3083 LID ARTWORK — four composition candidates, PARAMETRIC renderer.

Authorized act: OWNER_BLOCKER_CLEARANCE.md A3 (YES — AUTHORIZED, four
candidates + contact sheet), ingested in owner_blocker_clearance_ingestion.json.

BINDING CONSTRUCTION RULES (es3083_artwork_geometry_substrate.json):
1. Every mm dimension is read from the substrate or derived from it as a
   fraction of the MEASURED 65.00 x 65.00 lid frame — no hard-coded mm.
   A caliper session edits the record and re-runs this script.
2. The typeface is a parameter (TYPEFACE_SPEC SET_FACE). C1 ruling:
   ACCEPT_SET_FACE (Crimson Text Regular, OFL). The TARGET face (Adobe
   Caslon Pro) is NOT used anywhere here.
3. NO TYPE IS OUTLINED — the SVGs carry live <text>; PNGs are raster
   renders, which is not an outline conversion.
4. Words are exactly the established typography set BBROSE / EYE SHADOW /
   SOMBRA DE OJOS (ES3083_DIMENSION_FINDINGS.md:47 — the lid's
   typography_zones content). No copy is invented.
5. Colours are the measured-Lab-derived sRGB values recorded in the
   substrate (PANTONE 621 C, PANTONE 627 C, text black). White is a
   design ground, not a stock claim.
6. The frame edge is drawn square at exactly the measured 65.00 x 65.00.
   No corner radius is asserted — die/case corner geometry is not
   established and is NOT fabricated here.

The four candidates are deliberately distinct directions (executor's
design judgment, authorized by A3): C1 wordmark-dominant, C2
typographic-grid, C3 minimal-central, C4 border-led.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
os.chdir(ROOT)
REPO = os.path.dirname(ROOT)

SUB = json.load(open("docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json"))
FW, FH = SUB["MEASURED_VECTOR_FROM_SOURCE"]["lid_artwork_mm"]
COL = SUB["LABEL_SHEET_CONSTRUCTION_2026_08_14"]["treatment_colours_sRGB_from_measured_Lab"]
BLACK = tuple(COL["text_black"])
P627 = tuple(COL["pantone_627C"])
P621 = tuple(COL["pantone_621C"])
WHITE = (255, 255, 255)  # design ground; the stock question lives with the labels
T = SUB["TYPEFACE_SPEC_2026_08_14"]
FONT = os.path.join(REPO, T["SET_FACE"]["file"])
FAMILY = T["SET_FACE"]["family"]

WORDS = {"brand": "BBROSE", "en": "EYE SHADOW", "es": "SOMBRA DE OJOS"}


# ---- element model: everything in mm within the FW x FH frame ----------
# ("ground", rgb)
# ("rect", x, y, w, h, rgb_stroke, w_mm)          — stroked, no fill
# ("line", x1, y1, x2, y2, rgb, w_mm)
# ("text", s, mode, x, y_baseline, em_mm, track_mm, rgb)  mode: centre|left

def c1_wordmark_dominant():
    """Large letterspaced wordmark at the optical centre, paired rules."""
    return "C1", "WORDMARK-DOMINANT", [
        ("ground", WHITE),
        ("line", 0.15 * FW, 0.315 * FH, 0.85 * FW, 0.315 * FH, P627, 0.30),
        ("text", WORDS["brand"], "centre", FW / 2, 0.475 * FH,
         0.160 * FH, 0.022 * FW, BLACK),
        ("line", 0.15 * FW, 0.545 * FH, 0.85 * FW, 0.545 * FH, P627, 0.30),
        ("text", WORDS["en"], "centre", FW / 2, 0.640 * FH,
         0.046 * FH, 0.014 * FW, P627),
        ("text", WORDS["es"], "centre", FW / 2, 0.700 * FH,
         0.038 * FH, 0.011 * FW, P627),
    ]


def c2_typographic_grid():
    """Full 627 C ground, ranged-left 621 C type on a ruled grid."""
    m = 0.09 * FW
    return "C2", "TYPOGRAPHIC-GRID", [
        ("ground", P627),
        ("text", WORDS["brand"], "left", m, 0.225 * FH,
         0.130 * FH, 0.016 * FW, P621),
        ("line", m, 0.285 * FH, FW - m, 0.285 * FH, P621, 0.25),
        ("text", WORDS["en"], "left", m, 0.560 * FH,
         0.072 * FH, 0.018 * FW, P621),
        ("line", m, 0.615 * FH, FW - m, 0.615 * FH, P621, 0.25),
        ("text", WORDS["es"], "left", m, 0.870 * FH,
         0.050 * FH, 0.013 * FW, P621),
        ("line", m, 0.920 * FH, FW - m, 0.920 * FH, P621, 0.25),
    ]


def c3_minimal_central():
    """Whisper-scale centred stack on the pale 621 C ground."""
    return "C3", "MINIMAL-CENTRAL", [
        ("ground", P621),
        ("text", WORDS["brand"], "centre", FW / 2, 0.475 * FH,
         0.085 * FH, 0.050 * FW, P627),
        ("line", 0.44 * FW, 0.525 * FH, 0.56 * FW, 0.525 * FH, P627, 0.25),
        ("text", WORDS["en"], "centre", FW / 2, 0.585 * FH,
         0.032 * FH, 0.010 * FW, P627),
        ("text", WORDS["es"], "centre", FW / 2, 0.635 * FH,
         0.032 * FH, 0.010 * FW, P627),
    ]


def c4_border_led():
    """Double 627 C border frame; bilingual lines held inside it."""
    b1 = 0.045 * FW
    b2 = b1 + 0.025 * FW
    return "C4", "BORDER-LED", [
        ("ground", WHITE),
        ("rect", b1, b1, FW - 2 * b1, FH - 2 * b1, P627, 0.60),
        ("rect", b2, b2, FW - 2 * b2, FH - 2 * b2, P627, 0.25),
        ("text", WORDS["en"], "centre", FW / 2, 0.235 * FH,
         0.046 * FH, 0.016 * FW, P627),
        ("text", WORDS["brand"], "centre", FW / 2, 0.540 * FH,
         0.135 * FH, 0.020 * FW, BLACK),
        ("text", WORDS["es"], "centre", FW / 2, 0.820 * FH,
         0.046 * FH, 0.016 * FW, P627),
    ]


CANDIDATES = [c1_wordmark_dominant, c2_typographic_grid,
              c3_minimal_central, c4_border_led]


# ---- shared text measurement (PIL metrics; SVG uses the same tracking) --

def tracked_width(font, s, track_px):
    return sum(font.getlength(ch) for ch in s) + track_px * (len(s) - 1)


def draw_tracked(d, font, s, x_px, base_px, track_px, rgb):
    x = x_px
    for ch in s:
        d.text((x, base_px), ch, font=font, fill=rgb, anchor="ls")
        x += font.getlength(ch) + track_px


# ---- PNG (raster preview, >=1500 px) ------------------------------------

def render_png(elements, out, dpi=600, frame_hint=True):
    k = dpi / 25.4
    img = Image.new("RGB", (round(FW * k), round(FH * k)), WHITE)
    d = ImageDraw.Draw(img)
    for e in elements:
        if e[0] == "ground":
            d.rectangle([0, 0, img.width, img.height], fill=e[1])
        elif e[0] == "rect":
            _, x, y, w, h, rgb, wmm = e
            d.rectangle([x * k, y * k, (x + w) * k, (y + h) * k],
                        outline=rgb, width=max(1, round(wmm * k)))
        elif e[0] == "line":
            _, x1, y1, x2, y2, rgb, wmm = e
            d.line([x1 * k, y1 * k, x2 * k, y2 * k], fill=rgb,
                   width=max(1, round(wmm * k)))
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            f = ImageFont.truetype(FONT, round(em * k))
            tw = tracked_width(f, s, tr * k)
            x_px = (x * k - tw / 2) if mode == "centre" else x * k
            draw_tracked(d, f, s, x_px, yb * k, tr * k, rgb)
    if frame_hint:  # raster-only frame hint so white grounds read on white
        d.rectangle([0, 0, img.width - 1, img.height - 1],
                    outline=(200, 200, 200), width=1)
    img.save(out, dpi=(dpi, dpi))
    return img


# ---- SVG (true scale, LIVE text — rule 3) -------------------------------

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def render_svg(cid, cname, elements, out):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (FW, FH, FW, FH),
        '<!-- ES3083 lid artwork candidate %s (%s). PARAMETRIC on '
        'es3083_artwork_geometry_substrate.json: frame %g x %g mm MEASURED. '
        'Face: %s (SET_FACE, OFL). Text is LIVE, never outlined. -->'
        % (cid, cname, FW, FH, FAMILY),
    ]
    for e in elements:
        if e[0] == "ground":
            lines.append('<rect width="%g" height="%g" fill="rgb(%d,%d,%d)"/>'
                         % (FW, FH, *e[1]))
        elif e[0] == "rect":
            _, x, y, w, h, rgb, wmm = e
            lines.append('<rect x="%g" y="%g" width="%g" height="%g" '
                         'fill="none" stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                         % (x, y, w, h, *rgb, wmm))
        elif e[0] == "line":
            _, x1, y1, x2, y2, rgb, wmm = e
            lines.append('<line x1="%g" y1="%g" x2="%g" y2="%g" '
                         'stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                         % (x1, y1, x2, y2, *rgb, wmm))
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            if mode == "centre":
                # letter-spacing trails the last glyph; recentre by tr/2
                anchor, tx = "middle", x - tr / 2
            else:
                anchor, tx = "start", x
            lines.append(
                '<text x="%g" y="%g" font-family="%s" font-size="%g" '
                'letter-spacing="%g" text-anchor="%s" '
                'fill="rgb(%d,%d,%d)">%s</text>'
                % (tx, yb, FAMILY, em, tr, anchor, *rgb, esc(s)))
    lines.append("</svg>")
    open(out, "w").write("\n".join(lines) + "\n")


# ---- contact sheet: single PNG, all four at equal scale -----------------

def contact_sheet(tiles, out, dpi=300):
    k = dpi / 25.4
    tile_w, tile_h = round(FW * k), round(FH * k)
    gap = round(8 * k / 2)
    cap_h = round(9 * k / 2)
    head_h = round(16 * k / 2)
    foot_h = round(12 * k / 2)
    page_w = 2 * tile_w + 3 * gap
    page_h = head_h + 2 * (tile_h + cap_h) + 3 * gap + foot_h
    page = Image.new("RGB", (page_w, page_h), (244, 244, 242))
    d = ImageDraw.Draw(page)
    fh = ImageFont.truetype(FONT, round(head_h * 0.42))
    fc = ImageFont.truetype(FONT, round(cap_h * 0.52))
    ff = ImageFont.truetype(FONT, round(foot_h * 0.30))
    title = "ES3083 LID ARTWORK — COMPOSITION CANDIDATES"
    d.text((page_w / 2 - fh.getlength(title) / 2, head_h * 0.30),
           title, font=fh, fill=BLACK)
    for i, (cid, cname, img) in enumerate(tiles):
        r, c = divmod(i, 2)
        x = gap + c * (tile_w + gap)
        y = head_h + gap + r * (tile_h + cap_h + gap)
        tile = img.resize((tile_w, tile_h), Image.LANCZOS)
        page.paste(tile, (x, y))
        d.rectangle([x, y, x + tile_w, y + tile_h],
                    outline=(180, 180, 180), width=2)
        cap = "%s — %s" % (cid, cname)
        d.text((x + tile_w / 2 - fc.getlength(cap) / 2, y + tile_h + cap_h * 0.22),
               cap, font=fc, fill=BLACK)
    foot_lines = [
        "Frame %.2f x %.2f mm MEASURED (equal scale, all four)  ·  "
        "Face: %s Regular (SET_FACE, OFL) — TARGET Caslon not used" % (FW, FH, FAMILY),
        "Colours: PANTONE 621 C / 627 C from measured Lab  ·  "
        "2026-08-14, act authorized by OWNER_BLOCKER_CLEARANCE.md A3",
    ]
    fy = page_h - foot_h * 0.92
    for fl in foot_lines:
        fw_px = ff.getlength(fl)
        assert fw_px < page_w * 0.96, "footer line overflows the page"
        d.text((page_w / 2 - fw_px / 2, fy), fl, font=ff, fill=(90, 90, 90))
        fy += foot_h * 0.40
    page.save(out, dpi=(dpi, dpi))


if __name__ == "__main__":
    tiles = []
    for fn in CANDIDATES:
        cid, cname, els = fn()
        slug = "%s_%s" % (cid, cname.lower().replace("-", "_"))
        img = render_png(els, f"{HERE}/es3083_lid_{slug}.png")
        render_svg(cid, cname, els, f"{HERE}/es3083_lid_{slug}.svg")
        tiles.append((cid, cname, img))
        print(f"{cid} {cname}: PNG {img.width}x{img.height}px + SVG written")
    contact_sheet(tiles, f"{HERE}/es3083_lid_contact_sheet_C1_C4.png")
    print("contact sheet written")
