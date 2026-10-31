"""H2 request fb3093_compact_01 — five ORIGINAL square-compact lid candidates.

Authorized act: H2 second live request (§K session launcher, work item 2).
Candidates are drawn FROM SCRATCH, informed by inspiration_ledger.json
entries (ideas only — nothing traced or copied; per-entry originality notes
in the ledger). None of the five ES3083 directions is recycled; the vendor
sheet's Super Stay styling is expressly not carried.

BINDING CONSTRUCTION RULES (the M7/H2 lineage, adapted to the H2 model):
1. FRAME dimensions come from THE BRIEF (../brief.json) — the H2 contract's
   own rule that measurements are at-request-time inputs. The 72.00 x 72.00
   frame is a PRIOR-tier web measurement with URL provenance, superseded in
   place when the owner calipers the physical sample; nothing here hard-codes
   a millimetre.
2. Colour + typeface constants come from their recorded brand authority
   (es3083_artwork_geometry_substrate.json treatment colours, measured-Lab
   verified; TYPEFACE_SPEC SET_FACE Crimson Text, OFL).
3. NO TYPE IS OUTLINED — SVGs carry live <text>; PNGs are raster previews.
4. Words are the FB3093 established set BBROSE / FACE POWDER / POLVOS only
   (vendor sheet consulted for form + words; no claims, no shade names).
5. Two-ink discipline: every mark is 621 C or 627 C. 'Tint' readings are
   achieved by hairline weight and dot density, never by a third colour.
6. Frame drawn square at the brief's dimension; no corner radius asserted.
"""
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
os.chdir(ROOT)
REPO = os.path.dirname(ROOT)

BRIEF = json.load(open(os.path.join(HERE, "..", "brief.json")))
_dims = {m["name"]: m for m in BRIEF["physical_measurements"]}
FW, FH = _dims["lid_artwork_frame"]["value"]
FRAME_TIER = _dims["lid_artwork_frame"]["tier"]

SUB = json.load(open("docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json"))
COL = SUB["LABEL_SHEET_CONSTRUCTION_2026_08_14"]["treatment_colours_sRGB_from_measured_Lab"]
BLACK = tuple(COL["text_black"])
P627 = tuple(COL["pantone_627C"])
P621 = tuple(COL["pantone_621C"])
T = SUB["TYPEFACE_SPEC_2026_08_14"]
FONT = os.path.join(REPO, T["SET_FACE"]["file"])
FAMILY = T["SET_FACE"]["family"]

WORDS = {"brand": "BBROSE", "en": "FACE POWDER", "es": "POLVOS"}
TAU = 2 * math.pi


# ---- element model: ground/rect/line/text/poly as before, plus ----------
# ("disc", cx, cy, r_mm, rgb)          — filled dot (stipple vocabulary)
# ("circle", cx, cy, r_mm, rgb, w_mm)  — stroked ring


def leaf_loop(cx, cy, a, b, rot):
    pts = []
    for i in range(49):
        th = TAU * i / 48
        x, y = a * math.cos(th), b * math.sin(th)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)))
    return pts


def b1_powder_box_garland():
    """Perimeter garland frame (heritage powder-box genre, e01) built from
    an ORIGINAL repeating leaf unit along an inset rule ring (e08/e12 field
    discipline: ornament as quiet frame, centre calm)."""
    inset = 0.105 * FW
    els = [("ground", P621),
           ("rect", inset, inset, FW - 2 * inset, FH - 2 * inset, P627, 0.12)]
    n_per_edge = 7
    leaf_a, leaf_b = 0.020 * FW, 0.0075 * FH
    edges = [((inset, inset), (FW - inset, inset), 0.0),
             ((FW - inset, inset), (FW - inset, FH - inset), math.pi / 2),
             ((FW - inset, FH - inset), (inset, FH - inset), math.pi),
             ((inset, FH - inset), (inset, inset), -math.pi / 2)]
    for (x0, y0), (x1, y1), ang in edges:
        for i in range(1, n_per_edge + 1):
            t = i / (n_per_edge + 1)
            px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            side = -1 if i % 2 else 1
            nx, ny = -math.sin(ang) * side, math.cos(ang) * side
            lx = px + nx * 0.016 * FW
            ly = py + ny * 0.016 * FH
            els.append(("poly", leaf_loop(lx, ly, leaf_a, leaf_b,
                                          ang + side * 0.55), True, P627, 0.14))
    for cx, cy in [(inset, inset), (FW - inset, inset),
                   (inset, FH - inset), (FW - inset, FH - inset)]:
        els.append(("disc", cx, cy, 0.35, P627))
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.455 * FH,
         0.062 * FH, 0.042 * FW, P627),
        ("text", WORDS["en"], "centre", FW / 2, 0.535 * FH,
         0.024 * FH, 0.011 * FW, P627),
        ("text", WORDS["es"], "centre", FW / 2, 0.578 * FH,
         0.024 * FH, 0.011 * FW, P627),
    ]
    return "B1", "POWDER-BOX GARLAND", "heritage_border", els


def b2_veil_mesh():
    """All-over hairline diagonal mesh reading as fabric veil (e03/e16/e21);
    a ground-coloured clearing keeps the word stack calm. Two-ink rule: the
    'light tint' is hairline WEIGHT, not a third colour."""
    els = [("ground", P621)]
    pitch = 0.034 * FW
    # 45-degree mesh, both directions, correctly clipped to the frame:
    # direction (1,1) is the line family x - y = c; (1,-1) is x + y = c.
    c = -FH + pitch
    while c < FW:
        x0, y0 = max(0.0, c), max(0.0, -c)
        x1, y1 = min(FW, FH + c), min(FH, FW - c)
        if x1 > x0:
            els.append(("line", x0, y0, x1, y1, P627, 0.06))
        c += pitch
    c = pitch
    while c < FW + FH:
        x0, y0 = max(0.0, c - FH), min(FH, c)
        x1, y1 = min(FW, c), max(0.0, c - FW)
        if x1 > x0:
            els.append(("line", x0, y0, x1, y1, P627, 0.06))
        c += pitch
    cw, ch = 0.46 * FW, 0.20 * FH
    els.append(("rectfill", (FW - cw) / 2, 0.42 * FH, cw, ch, P621))
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.485 * FH,
         0.056 * FH, 0.040 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "centre",
         FW / 2, 0.555 * FH, 0.021 * FH, 0.009 * FW, P627),
    ]
    return "B2", "VEIL MESH", "veil_mesh", els


def b3_puff_bloom():
    """The ghost of a powder puff pressed once (e19): a deterministic
    blue-noise-flavoured stipple whose density falls off radially
    (e17/e24); tone from density alone — every dot is full 627 C."""
    els = [("ground", P621)]
    rng = random.Random(3093)  # deterministic; re-runs are byte-stable
    cx, cy, R = 0.615 * FW, 0.400 * FH, 0.315 * FW
    cell = 0.0135 * FW
    n_grid = int(FW / cell)
    for gy in range(n_grid + 1):
        for gx in range(n_grid + 1):
            x = (gx + rng.random() * 0.85) * cell
            y = (gy + rng.random() * 0.85) * cell
            d = math.hypot(x - cx, y - cy) / R
            keep = math.exp(-d * d * 1.9)
            if rng.random() < keep:
                r_dot = 0.085 + 0.05 * math.exp(-d * d)
                if y < 0.80 * FH or x < 0.30 * FW:
                    els.append(("disc", x, y, r_dot, P627))
    els += [
        ("text", WORDS["brand"], "left", 0.085 * FW, 0.860 * FH,
         0.058 * FH, 0.032 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "left",
         0.085 * FW, 0.918 * FH, 0.022 * FH, 0.009 * FW, P627),
    ]
    return "B3", "PUFF BLOOM", "powder_bloom", els


def b4_quiet_plate():
    """The centered micro-stack plate (e07): symmetric, equal margins,
    ground-as-hero (e04), hierarchy by tracking not size (e05/e27).
    quiet_minimal — deliberately DISTINCT from ES3083 A5 (asymmetric
    corner, keyline patch): here dead-centre, frameless, three lines."""
    return "B4", "QUIET PLATE", "quiet_minimal", [
        ("ground", P621),
        ("text", WORDS["brand"], "centre", FW / 2, 0.478 * FH,
         0.052 * FH, 0.055 * FW, P627),
        ("text", WORDS["en"], "centre", FW / 2, 0.545 * FH,
         0.020 * FH, 0.014 * FW, P627),
        ("text", WORDS["es"], "centre", FW / 2, 0.585 * FH,
         0.020 * FH, 0.014 * FW, P627),
    ]


def b5_pharmacy_seal():
    """Seal-scale device + formal stack (e15/e25): a small ORIGINAL dotted
    ring seal (NOT the A2 rosette class — plain circles at seal scale, a
    different genre), one hairline rule, three centred lines (e13/e22)."""
    scx, scy = FW / 2, 0.295 * FH
    els = [("ground", P621),
           ("circle", scx, scy, 0.088 * FW, P627, 0.14),
           ("circle", scx, scy, 0.070 * FW, P627, 0.10)]
    for i in range(24):
        th = TAU * i / 24
        els.append(("disc", scx + 0.079 * FW * math.cos(th),
                    scy + 0.079 * FW * math.sin(th), 0.10, P627))
    els.append(("text", "B", "centre", scx, scy + 0.026 * FH,
                0.072 * FH, 0.0, P627))
    els += [
        ("line", 0.38 * FW, 0.475 * FH, 0.62 * FW, 0.475 * FH, P627, 0.12),
        ("text", WORDS["brand"], "centre", FW / 2, 0.565 * FH,
         0.058 * FH, 0.038 * FW, P627),
        ("text", WORDS["en"], "centre", FW / 2, 0.630 * FH,
         0.023 * FH, 0.011 * FW, P627),
        ("text", WORDS["es"], "centre", FW / 2, 0.672 * FH,
         0.023 * FH, 0.011 * FW, P627),
    ]
    return "B5", "PHARMACY SEAL", "seal_typographic", els


CANDIDATES = [b1_powder_box_garland, b2_veil_mesh, b3_puff_bloom,
              b4_quiet_plate, b5_pharmacy_seal]


# ---- shared text measurement (M7 lineage) -------------------------------

def tracked_width(font, s, track_px):
    return sum(font.getlength(ch) for ch in s) + track_px * (len(s) - 1)


def draw_tracked(d, font, s, x_px, base_px, track_px, rgb):
    x = x_px
    for ch in s:
        d.text((x, base_px), ch, font=font, fill=rgb, anchor="ls")
        x += font.getlength(ch) + track_px


def text_extent_mm(s, em_mm, track_mm, probe_dpi=600):
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
        assert -0.02 * FW <= x0 and x0 + w <= 1.02 * FW, \
            "%s: '%s' escapes the frame (x0=%.2f w=%.2f)" % (cid, s, x0, w)


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
        elif e[0] == "rectfill":
            _, x, y, w, h, rgb = e
            d.rectangle([x * k, y * k, (x + w) * k, (y + h) * k], fill=rgb)
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
        elif e[0] == "disc":
            _, cx, cy, r, rgb = e
            d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k],
                      fill=rgb)
        elif e[0] == "circle":
            _, cx, cy, r, rgb, wmm = e
            d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k],
                      outline=rgb, width=max(1, round(wmm * k)))
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


def render_svg(cid, cname, elements, out):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (FW, FH, FW, FH),
        '<!-- FB3093 square-compact lid candidate %s (%s) — H2 request '
        'fb3093_compact_01, generation stage. ORIGINAL artwork drawn from '
        'scratch; inspiration ideas with provenance in '
        'inspiration_ledger.json. PARAMETRIC ON THE BRIEF: frame %g x %g mm '
        'is a %s-tier web measurement (supplier listing, URL in brief.json), '
        'superseded in place when the owner calipers the sample. Face: %s '
        '(SET_FACE, OFL). Text is LIVE, never outlined. -->'
        % (cid, cname, FW, FH, FRAME_TIER, FAMILY),
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
        elif e[0] == "rectfill":
            _, x, y, w, h, rgb = e
            lines.append('<rect x="%g" y="%g" width="%g" height="%g" '
                         'fill="rgb(%d,%d,%d)"/>' % (x, y, w, h, *rgb))
        elif e[0] == "line":
            _, x1, y1, x2, y2, rgb, wmm = e
            lines.append('<line x1="%g" y1="%g" x2="%g" y2="%g" '
                         'stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                         % (round(x1, 3), round(y1, 3), round(x2, 3),
                            round(y2, 3), *rgb, wmm))
        elif e[0] == "poly":
            _, pts, closed, rgb, wmm = e
            dstr = "M " + " L ".join("%.3f %.3f" % (x, y) for x, y in pts)
            if closed:
                dstr += " Z"
            lines.append('<path d="%s" fill="none" stroke="rgb(%d,%d,%d)" '
                         'stroke-width="%g" stroke-linecap="round" '
                         'stroke-linejoin="round"/>' % (dstr, *rgb, wmm))
        elif e[0] == "disc":
            _, cx, cy, r, rgb = e
            lines.append('<circle cx="%.3f" cy="%.3f" r="%.3f" '
                         'fill="rgb(%d,%d,%d)"/>' % (cx, cy, r, *rgb))
        elif e[0] == "circle":
            _, cx, cy, r, rgb, wmm = e
            lines.append('<circle cx="%.3f" cy="%.3f" r="%.3f" fill="none" '
                         'stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                         % (cx, cy, r, *rgb, wmm))
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            if mode == "centre":
                anchor, tx = "middle", x - tr / 2
            else:
                anchor, tx = "start", x
            lines.append(
                '<text x="%g" y="%g" font-family="%s" font-size="%g" '
                'letter-spacing="%g" text-anchor="%s" '
                'fill="rgb(%d,%d,%d)">%s</text>'
                % (round(tx, 3), yb, FAMILY, em, tr, anchor, *rgb, esc(s)))
    lines.append("</svg>")
    open(out, "w").write("\n".join(lines) + "\n")


# ---- contact sheet ------------------------------------------------------

def contact_sheet(tiles, out, dpi=300):
    k = dpi / 25.4
    tile_w, tile_h = round(FW * k), round(FH * k)
    gap = round(8 * k / 2)
    cap_h = round(9 * k / 2)
    head_h = round(16 * k / 2)
    foot_h = round(12 * k / 2)
    cols, rows = 3, 2
    page_w = cols * tile_w + (cols + 1) * gap
    page_h = head_h + rows * (tile_h + cap_h + gap) + gap + foot_h
    page = Image.new("RGB", (page_w, page_h), (244, 244, 242))
    d = ImageDraw.Draw(page)

    def fitted(size_px, s, max_w):
        f = ImageFont.truetype(FONT, size_px)
        while f.getlength(s) > max_w and size_px > 8:
            size_px -= 1
            f = ImageFont.truetype(FONT, size_px)
        return f

    title = "FB3093 FACE-POWDER COMPACT — H2 CANDIDATES B1-B5"
    fh_ = fitted(round(head_h * 0.42), title, page_w - 2 * gap)
    d.text((page_w / 2 - fh_.getlength(title) / 2, head_h * 0.30),
           title, font=fh_, fill=BLACK)
    fc = ImageFont.truetype(FONT, round(cap_h * 0.52))
    ff = ImageFont.truetype(FONT, round(foot_h * 0.30))
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
        "H2 request fb3093_compact_01 — ORIGINAL candidates from fresh web "
        "inspiration (27-entry ledger committed alongside)  ·  vendor Super "
        "Stay styling not carried",
        "Frame %.2f x %.2f mm PRIOR (supplier-listing web measurement — "
        "owner calipers supersede)  ·  Face: %s Regular (SET_FACE, OFL)  ·  "
        "PANTONE 621 C / 627 C  ·  the owner's pick is design authority"
        % (FW, FH, FAMILY),
    ]
    fy = page_h - foot_h * 0.92
    for fl in foot_lines:
        f_fit = fitted(round(foot_h * 0.30), fl, page_w - 2 * gap)
        d.text((page_w / 2 - f_fit.getlength(fl) / 2, fy), fl,
               font=f_fit, fill=(90, 90, 90))
        fy += foot_h * 0.40
    page.save(out, dpi=(dpi, dpi))


if __name__ == "__main__":
    tiles = []
    for fn in CANDIDATES:
        cid, cname, direction, els = fn()
        assert_text_fits(cid, els)
        slug = "%s_%s" % (cid, cname.lower().replace(" ", "_").replace("-", "_"))
        img = render_png(els, f"{HERE}/fb3093_lid_{slug}.png")
        render_svg(cid, cname, els, f"{HERE}/fb3093_lid_{slug}.svg")
        tiles.append((cid, cname, img))
        print(f"{cid} {cname} [{direction}]: PNG {img.width}x{img.height}px + SVG written")
    contact_sheet(tiles, os.path.join(HERE, "..", "contact_sheet.png"))
    print("contact sheet written")
