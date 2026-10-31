"""H2 request es3083_lid_alt_01 — five ORIGINAL alternate-lid candidates.

Authorized act: H2 launcher work item 4 under §H2 + §I (both signed
2026-08-15). Generation stage of the design-request pipeline: candidates are
drawn FROM SCRATCH, informed by inspiration_ledger.json entries (ideas only —
no web artwork is traced, copied, or closely derived; per-entry originality
notes in the ledger). The accepted C3 lid stays shipped and untouched; the
C3 minimal-central layout is NOT re-served here.

BINDING CONSTRUCTION RULES (carried from the M7 renderer, unchanged):
1. Every mm dimension is read from es3083_artwork_geometry_substrate.json or
   derived as a fraction of the MEASURED 65.00 x 65.00 frame. Curve geometry
   is computed parametrically from those fractions — no hard-coded mm.
2. Typeface = SET_FACE (Crimson Text Regular, OFL). No other face.
3. NO TYPE IS OUTLINED — SVGs carry live <text>; PNGs are raster previews.
4. Words are the established lid typography set BBROSE / EYE SHADOW /
   SOMBRA DE OJOS only. Shade names and new copy are NOT invented onto the
   lid — copy decisions beyond the established set are the owner's.
5. Colours are the substrate's measured-Lab-derived sRGB (621 C, 627 C).
6. Frame drawn square at the measured 65.00 x 65.00; no corner radius
   asserted. Curves cropped by the frame are cropped by the viewBox/canvas,
   never redrawn to fake a bleed allowance (die geometry is owner spec).
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
os.chdir(ROOT)
REPO = os.path.dirname(ROOT)

SUB = json.load(open("docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json"))
FW, FH = SUB["MEASURED_VECTOR_FROM_SOURCE"]["lid_artwork_mm"]
COL = SUB["LABEL_SHEET_CONSTRUCTION_2026_08_14"]["treatment_colours_sRGB_from_measured_Lab"]
BLACK = tuple(COL["text_black"])
P627 = tuple(COL["pantone_627C"])
P621 = tuple(COL["pantone_621C"])
T = SUB["TYPEFACE_SPEC_2026_08_14"]
FONT = os.path.join(REPO, T["SET_FACE"]["file"])
FAMILY = T["SET_FACE"]["family"]

WORDS = {"brand": "BBROSE", "en": "EYE SHADOW", "es": "SOMBRA DE OJOS"}

TAU = 2 * math.pi


# ---- element model (M7's, plus "poly": stroked polyline/polygon) --------
# ("ground", rgb)
# ("rect", x, y, w, h, rgb_stroke, w_mm)
# ("line", x1, y1, x2, y2, rgb, w_mm)
# ("text", s, mode, x, y_baseline, em_mm, track_mm, rgb)
# ("poly", [(x,y)...], closed, rgb, w_mm)   — computed curve, round joins


def rose_gesture_points():
    """A1 — ORIGINAL continuous-line rose: one unbroken epitrochoid-on-spiral
    stroke whose growing epicycle self-intersects into petal loops, exiting
    toward the frame edge. Constructed parametrically here; no reference
    artwork traced (ledger e03/e08/e10/e30 contribute the IDEA of a
    single-gesture monoline rose only)."""
    cx, cy = 0.630 * FW, 0.355 * FH
    rmax = 0.300 * FW
    turns, alpha = 2.6, 4.2
    pts = []
    n = 900
    for i in range(n + 1):
        t = i / n
        th = TAU * turns * t - 0.6
        r = rmax * (t ** 0.9)
        q = 0.42 * r
        pts.append((cx + r * math.cos(th) + q * math.cos(alpha * th),
                    cy + r * math.sin(th) + q * math.sin(alpha * th)))
    # tail: swing the final heading outward so the stroke crops at the edge
    x1, y1 = pts[-2]
    x2, y2 = pts[-1]
    hx, hy = x2 - x1, y2 - y1
    h = math.hypot(hx, hy)
    for j in range(1, 30):
        pts.append((x2 + hx / h * j * 0.02 * FW, y2 + hy / h * j * 0.012 * FH))
    return pts


def rosette_rings():
    """A2 — twelve-lobed concentric rosette: closed curves r = R(0.86 +
    0.14 cos 12θ). Twelve lobes deliberately echo the palette's 12-pan
    interior (ledger e04's module-echo idea; e22's read-as-rose-without-
    depicting-one; e14's centred radial burst)."""
    cx, cy = FW / 2, 0.435 * FH
    rings = []
    for k in range(6):
        base = (0.100 + 0.046 * k) * FW
        phase = (math.pi / 12) * (k % 2)  # alternate rings interleave
        pts = []
        for i in range(361):
            th = TAU * i / 360
            r = base * (0.91 + 0.09 * math.cos(12 * th + 12 * phase))
            pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
        rings.append(pts)
    return rings


def sprig_points():
    """A4 — small ORIGINAL leaf-sprig monoline: a gently arched stem;
    slim leaves sit ALONG it (leaf_loop calls in a4), angled near the
    stem tangent — the first render clustered them into a knot."""
    bx, by = 0.500 * FW, 0.235 * FH
    pts = []
    for i in range(41):
        t = i / 40
        pts.append((bx + (t - 0.5) * 0.30 * FW,
                    by - math.sin(t * math.pi) * 0.028 * FH))
    return pts


def stem_point(t):
    bx, by = 0.500 * FW, 0.235 * FH
    return (bx + (t - 0.5) * 0.30 * FW, by - math.sin(t * math.pi) * 0.028 * FH)


def leaf_loop(cx, cy, a, b, rot):
    pts = []
    for i in range(61):
        th = TAU * i / 60
        x, y = a * math.cos(th), b * math.sin(th)
        xr = x * math.cos(rot) - y * math.sin(rot)
        yr = x * math.sin(rot) + y * math.cos(rot)
        pts.append((cx + xr, cy + yr))
    return pts


def a1_rose_gesture():
    return "A1", "ROSE-GESTURE", "botanical_gesture", [
        ("ground", P621),
        ("poly", rose_gesture_points(), False, P627, 0.35),
        ("text", WORDS["brand"], "left", 0.090 * FW, 0.830 * FH,
         0.072 * FH, 0.030 * FW, P627),
        ("text", WORDS["en"], "left", 0.090 * FW, 0.895 * FH,
         0.028 * FH, 0.010 * FW, P627),
        ("text", WORDS["es"], "left", 0.090 * FW, 0.940 * FH,
         0.028 * FH, 0.010 * FW, P627),
    ]


def a2_rosette():
    els = [("ground", P621)]
    for pts in rosette_rings():
        els.append(("poly", pts, True, P627, 0.18))
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.870 * FH,
         0.058 * FH, 0.036 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "centre",
         FW / 2, 0.930 * FH, 0.024 * FH, 0.008 * FW, P627),
    ]
    return "A2", "TWELVE-ROSETTE", "geometric_rosette", els


def a3_letter_field():
    """Monumental 'B' as letter-as-image. The small text column MUST clear
    the B's measured advance — the first render swallowed the 'S' of the
    Spanish line inside the dark glyph (dark-on-dark); guarded now by a
    MEASURED assert in main, not by eye."""
    b_em, b_cx = 0.950 * FH, 0.330 * FW
    col_x = 0.660 * FW
    return "A3", "LETTER-FIELD", "typographic_play", [
        ("ground", P621),
        ("text", "B", "centre", b_cx, 0.830 * FH, b_em, 0.0, P627),
        ("text", WORDS["brand"], "left", col_x, 0.160 * FH,
         0.050 * FH, 0.018 * FW, P627),
        ("text", WORDS["en"], "left", col_x, 0.225 * FH,
         0.023 * FH, 0.007 * FW, P627),
        ("text", WORDS["es"], "left", col_x, 0.270 * FH,
         0.023 * FH, 0.007 * FW, P627),
    ]


def a4_nocturne():
    els = [
        ("ground", P627),
        ("rect", 0.060 * FW, 0.060 * FH, 0.880 * FW, 0.880 * FH, P621, 0.20),
        ("poly", sprig_points(), False, P621, 0.30),
    ]
    # slim leaves spaced ALONG the stem, angled off its tangent
    for (t, side, size) in [(0.20, -1, 0.85), (0.45, -1, 1.0),
                            (0.62, 1, 0.8), (0.85, -1, 0.9)]:
        sx, sy = stem_point(t)
        tangent = math.atan2(stem_point(t + 0.01)[1] - sy,
                             stem_point(t + 0.01)[0] - sx)
        rot = tangent + side * 0.85
        a = 0.042 * FW * size
        lx = sx + math.cos(rot) * a * 0.9
        ly = sy + math.sin(rot) * a * 0.9 - 0.004 * FH
        els.append(("poly", leaf_loop(lx, ly, a, 0.013 * FH * size, rot),
                    True, P621, 0.30))
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.560 * FH,
         0.085 * FH, 0.050 * FW, P621),
        ("text", WORDS["en"], "centre", FW / 2, 0.660 * FH,
         0.030 * FH, 0.010 * FW, P621),
        ("text", WORDS["es"], "centre", FW / 2, 0.710 * FH,
         0.030 * FH, 0.010 * FW, P621),
    ]
    return "A4", "NOCTURNE", "tonal_inversion", els


def a5_quiet_corner():
    """Quiet-minimal owner taste — composed DIFFERENTLY from shipped C3
    (C3 = centred whisper stack + rule; A5 = lower-left ranged corner
    placement inside a hairline patch, bilingual line single, no rule)."""
    return "A5", "QUIET-CORNER", "quiet_minimal", [
        ("ground", P621),
        ("rect", 0.075 * FW, 0.075 * FH, 0.850 * FW, 0.850 * FH, P627, 0.15),
        ("text", WORDS["brand"], "left", 0.145 * FW, 0.760 * FH,
         0.062 * FH, 0.040 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "left",
         0.145 * FW, 0.822 * FH, 0.024 * FH, 0.008 * FW, P627),
    ]


CANDIDATES = [a1_rose_gesture, a2_rosette, a3_letter_field,
              a4_nocturne, a5_quiet_corner]


# ---- shared text measurement (identical to the M7 renderer) -------------

def tracked_width(font, s, track_px):
    return sum(font.getlength(ch) for ch in s) + track_px * (len(s) - 1)


def draw_tracked(d, font, s, x_px, base_px, track_px, rgb):
    x = x_px
    for ch in s:
        d.text((x, base_px), ch, font=font, fill=rgb, anchor="ls")
        x += font.getlength(ch) + track_px


# ---- PNG ----------------------------------------------------------------

def render_png(elements, out, dpi=600, frame_hint=True):
    k = dpi / 25.4
    img = Image.new("RGB", (round(FW * k), round(FH * k)), (255, 255, 255))
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
        elif e[0] == "poly":
            _, pts, closed, rgb, wmm = e
            px = [(x * k, y * k) for x, y in pts]
            if closed:
                px.append(px[0])
            d.line(px, fill=rgb, width=max(1, round(wmm * k)), joint="curve")
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            f = ImageFont.truetype(FONT, round(em * k))
            tw = tracked_width(f, s, tr * k)
            x_px = (x * k - tw / 2) if mode == "centre" else x * k
            draw_tracked(d, f, s, x_px, yb * k, tr * k, rgb)
    if frame_hint:
        d.rectangle([0, 0, img.width - 1, img.height - 1],
                    outline=(200, 200, 200), width=1)
    img.save(out, dpi=(dpi, dpi))
    return img


# ---- SVG (true scale, LIVE text) ----------------------------------------

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def fmt_pts(pts, closed):
    d = "M " + " L ".join("%.3f %.3f" % (x, y) for x, y in pts)
    return d + (" Z" if closed else "")


def render_svg(cid, cname, elements, out):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (FW, FH, FW, FH),
        '<!-- ES3083 ALTERNATE lid candidate %s (%s) — H2 request '
        'es3083_lid_alt_01, generation stage. ORIGINAL artwork drawn from '
        'scratch; inspiration ideas with provenance in '
        'inspiration_ledger.json (nothing traced or copied). PARAMETRIC on '
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
        elif e[0] == "poly":
            _, pts, closed, rgb, wmm = e
            lines.append('<path d="%s" fill="none" stroke="rgb(%d,%d,%d)" '
                         'stroke-width="%g" stroke-linecap="round" '
                         'stroke-linejoin="round"/>'
                         % (fmt_pts(pts, closed), *rgb, wmm))
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


# ---- contact sheet: A1-A5 at equal scale (M7F pattern) ------------------

def contact_sheet(tiles, out, dpi=300):
    k = dpi / 25.4
    tile_w, tile_h = round(FW * k), round(FH * k)
    gap = round(8 * k / 2)
    cap_h = round(9 * k / 2)
    head_h = round(16 * k / 2)
    foot_h = round(12 * k / 2)
    cols = 3
    rows = 2
    page_w = cols * tile_w + (cols + 1) * gap
    page_h = head_h + rows * (tile_h + cap_h + gap) + gap + foot_h
    page = Image.new("RGB", (page_w, page_h), (244, 244, 242))
    d = ImageDraw.Draw(page)
    fh = ImageFont.truetype(FONT, round(head_h * 0.42))
    fc = ImageFont.truetype(FONT, round(cap_h * 0.52))
    ff = ImageFont.truetype(FONT, round(foot_h * 0.30))
    title = "ES3083 ALTERNATE LID — H2 CANDIDATES A1-A5"
    d.text((page_w / 2 - fh.getlength(title) / 2, head_h * 0.30),
           title, font=fh, fill=BLACK)
    for i, (cid, cname, img) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = gap + c * (tile_w + gap)
        y = head_h + gap + r * (tile_h + cap_h + gap)
        tile = img.resize((tile_w, tile_h), Image.LANCZOS)
        page.paste(tile, (x, y))
        d.rectangle([x, y, x + tile_w, y + tile_h],
                    outline=(180, 180, 180), width=2)
        cap = "%s — %s" % (cid, cname)
        d.text((x + tile_w / 2 - fc.getlength(cap) / 2,
                y + tile_h + cap_h * 0.22), cap, font=fc, fill=BLACK)
    foot_lines = [
        "H2 request es3083_lid_alt_01 — ORIGINAL candidates from fresh web "
        "inspiration (ledger committed alongside)  ·  the accepted C3 lid "
        "stays shipped and untouched",
        "Frame %.2f x %.2f mm MEASURED (equal scale)  ·  Face: %s Regular "
        "(SET_FACE, OFL)  ·  PANTONE 621 C / 627 C from measured Lab  ·  "
        "the owner's pick is design authority" % (FW, FH, FAMILY),
    ]
    fy = page_h - foot_h * 0.92
    for fl in foot_lines:
        fw_px = ff.getlength(fl)
        assert fw_px < page_w * 0.96, "footer line overflows the page"
        d.text((page_w / 2 - fw_px / 2, fy), fl, font=ff, fill=(90, 90, 90))
        fy += foot_h * 0.40
    page.save(out, dpi=(dpi, dpi))


def text_extent_mm(s, em_mm, track_mm, probe_dpi=600):
    """Measured (not estimated) tracked ink width in mm via the SET_FACE
    metrics — the guard that catches overflow/overlap structurally."""
    k = probe_dpi / 25.4
    f = ImageFont.truetype(FONT, round(em_mm * k))
    return tracked_width(f, s, track_mm * k) / k


def assert_text_fits(cid, els):
    for e in els:
        if e[0] != "text":
            continue
        _, s, mode, x, yb, em, tr, rgb = e
        w = text_extent_mm(s, em, tr)
        x0 = (x - w / 2) if mode == "centre" else x
        assert x0 >= -0.02 * FW and x0 + w <= 1.02 * FW or s == "B", \
            "%s: '%s' escapes the frame (x0=%.2f w=%.2f)" % (cid, s, x0, w)


def assert_a3_column_clear(els):
    """The small-type column must start right of the measured B advance —
    the defect the first render proved possible (invisible dark-on-dark S)."""
    b = [e for e in els if e[0] == "text" and e[1] == "B"][0]
    b_right = b[3] + text_extent_mm("B", b[5], 0.0) / 2
    for e in els:
        if e[0] == "text" and e[1] != "B":
            assert e[3] > b_right + 0.015 * FW, \
                "A3 column at %.2f overlaps B right edge %.2f" % (e[3], b_right)


if __name__ == "__main__":
    tiles = []
    for fn in CANDIDATES:
        cid, cname, direction, els = fn()
        assert_text_fits(cid, els)
        if cid == "A3":
            assert_a3_column_clear(els)
        slug = "%s_%s" % (cid, cname.lower().replace("-", "_"))
        img = render_png(els, f"{HERE}/es3083_alt_lid_{slug}.png")
        render_svg(cid, cname, els, f"{HERE}/es3083_alt_lid_{slug}.svg")
        tiles.append((cid, cname, img))
        print(f"{cid} {cname} [{direction}]: PNG {img.width}x{img.height}px + SVG written")
    contact_sheet(tiles, os.path.join(HERE, "..", "contact_sheet.png"))
    print("contact sheet written")
