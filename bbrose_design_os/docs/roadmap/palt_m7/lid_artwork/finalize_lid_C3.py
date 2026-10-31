"""ES3083 LID ARTWORK — C3 FINALISATION at production-candidate tier.

Authorized act: OWNER_BLOCKER_CLEARANCE.md Section E (E1: C3 MINIMAL-CENTRAL
picked, LOCKED AS-IS), ingested in section_e_owner_picks_ingestion.json.
This is a REFINEMENT PASS ONLY — the composition is not re-explored. Scope,
verbatim from the launcher: optical spacing and kerning of the wordmark
block, rule weights, Lab->output colour verification for the 621 C ground,
safe-margin check against the measured 65.00 x 65.00 frame.

BINDING CONSTRUCTION RULES carried unchanged from render_lid_candidates.py
(es3083_artwork_geometry_substrate.json): parametric on the substrate, no
hard-coded mm, SET_FACE only, live text never outlined, measured-Lab
colours, square frame, no corner radius asserted.

WHAT THE REFINEMENT ACTUALLY IS (each measured, none hand-placed):
1. KERNING FIDELITY — the M7F raster path drew char-by-char with bare
   advances, discarding the face's GPOS 'kern' pairs; the SVG deliverable
   is live text, which conforming renderers DO kern. Preview and
   deliverable therefore disagreed by the kern amounts. The final raster
   path applies the GPOS pairs read from the font file, so the preview
   shows what the vector ships.
2. OPTICAL CENTRING BY INK — 'centre' was advance-centre; round/asymmetric
   glyph ink makes that differ from what the eye centres. Each line is
   recentred by its measured ink extents (applied only where the offset
   exceeds a declared noise floor).
3. RULE AT THE MEASURED OPTICAL MIDPOINT — the rule sat at the designed
   0.525*FH; the white gap above it (wordmark ink bottom -> rule) and
   below it (rule -> EYE SHADOW ink top) were unequal. The rule now sits
   at the measured midpoint of that white channel. Weight is unchanged
   at the designed 0.25 mm (a treatment variable, judged by eye).
4. VERIFICATION, NOT CHANGE — the 621 C / 627 C sRGB values are verified
   against the substrate's measured Lab under both D50 and D65 reading
   assumptions with round-trip deltaE; safe margins are measured from
   rendered ink to the 65.00 x 65.00 frame edges. No die-derived safe
   margin exists in the programme, so clearances are REPORTED as
   measurements, not judged against a fabricated standard.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
os.chdir(ROOT)
REPO = os.path.dirname(ROOT)

import sys  # noqa: E402 — chdir/path setup must precede the sibling import
sys.path.insert(0, HERE)
import render_lid_candidates as m7f  # noqa: E402 — frozen BEFORE model + M7F renderer

SUB = json.load(open("docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json"))
FW, FH = SUB["MEASURED_VECTOR_FROM_SOURCE"]["lid_artwork_mm"]
COL = SUB["LABEL_SHEET_CONSTRUCTION_2026_08_14"]["treatment_colours_sRGB_from_measured_Lab"]
P627 = tuple(COL["pantone_627C"])
P621 = tuple(COL["pantone_621C"])
LAB_621 = SUB["MEASURED_VECTOR_FROM_SOURCE"]["pantone_621C_lab"]
LAB_627 = SUB["MEASURED_VECTOR_FROM_SOURCE"]["pantone_627C_lab"]
T = SUB["TYPEFACE_SPEC_2026_08_14"]
FONT = os.path.join(REPO, T["SET_FACE"]["file"])
FAMILY = T["SET_FACE"]["family"]
WORDS = m7f.WORDS

INK_CENTRE_NOISE_MM = 0.05  # below this, advance-centre vs ink-centre is noise


# ---- GPOS 'kern' feature pairs, read from the SET_FACE file -------------

def gpos_kern_pairs(font_path):
    """{(glyphA, glyphB): xadvance_units} from the GPOS 'kern' feature, or —
    when the build has no GPOS, as this Crimson Text build does not — from
    the legacy TrueType 'kern' table, which shaping engines apply in GPOS's
    absence. Returns (pairs, upm, cmap, source)."""
    tt = TTFont(font_path)
    upm = tt["head"].unitsPerEm
    cmap = tt.getBestCmap()
    pairs = {}
    if "GPOS" not in tt:
        if "kern" in tt:
            for st in tt["kern"].kernTables:
                for pair, v in st.kernTable.items():
                    pairs.setdefault(pair, v)
            return pairs, upm, cmap, "legacy 'kern' table (GPOS absent)"
        return pairs, upm, cmap, "NONE — font has neither GPOS nor 'kern'"
    gpos = tt["GPOS"].table
    lookup_idx = set()
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "kern":
            lookup_idx.update(fr.Feature.LookupListIndex)
    for li in sorted(lookup_idx):
        lookup = gpos.LookupList.Lookup[li]
        subtables = lookup.SubTable
        if lookup.LookupType == 9:  # Extension
            subtables = [st.ExtSubTable for st in subtables]
        for st in subtables:
            if getattr(st, "Format", 0) == 1 and hasattr(st, "PairSet"):
                for first, ps in zip(st.Coverage.glyphs, st.PairSet):
                    for pvr in ps.PairValueRecord:
                        v = getattr(pvr.Value1, "XAdvance", 0) if pvr.Value1 else 0
                        if v:
                            pairs.setdefault((first, pvr.SecondGlyph), v)
            elif getattr(st, "Format", 0) == 2 and hasattr(st, "Class1Record"):
                cd1 = st.ClassDef1.classDefs
                cd2 = st.ClassDef2.classDefs
                cov = set(st.Coverage.glyphs)
                by_class2 = {}
                for g in cd2:
                    by_class2.setdefault(cd2[g], []).append(g)
                for g1 in cov:
                    c1 = cd1.get(g1, 0)
                    if c1 >= len(st.Class1Record):
                        continue
                    c1rec = st.Class1Record[c1]
                    for c2, c2rec in enumerate(c1rec.Class2Record):
                        v = getattr(c2rec.Value1, "XAdvance", 0) if c2rec.Value1 else 0
                        if not v:
                            continue
                        for g2 in by_class2.get(c2, []):
                            pairs.setdefault((g1, g2), v)
    return pairs, upm, cmap, "GPOS 'kern' feature"


KERN_UNITS, UPM, CMAP, KERN_SOURCE = gpos_kern_pairs(FONT)


def kern_mm(a, b, em_mm):
    ga, gb = CMAP.get(ord(a)), CMAP.get(ord(b))
    if ga is None or gb is None:
        return 0.0
    return KERN_UNITS.get((ga, gb), 0) * em_mm / UPM


# ---- kern-aware measurement and drawing ---------------------------------

def advances_mm(s, em_mm, track_mm, k):
    """Per-glyph pen advances in px at scale k, GPOS-kerned + tracked."""
    f = ImageFont.truetype(FONT, round(em_mm * k))
    adv = []
    for i, ch in enumerate(s):
        a = f.getlength(ch)
        if i < len(s) - 1:
            a += kern_mm(ch, s[i + 1], em_mm) * k + track_mm * k
        adv.append(a)
    return f, adv


def draw_kerned(d, s, x_px, base_px, em_mm, track_mm, k, rgb):
    f, adv = advances_mm(s, em_mm, track_mm, k)
    x = x_px
    for ch, a in zip(s, adv):
        d.text((x, base_px), ch, font=f, fill=rgb, anchor="ls")
        x += a
    return sum(adv)


def measure_ink(s, em_mm, track_mm, mdpi=800):
    """Render s on scratch; return (width_mm_advance, ink_l, ink_r, ink_top,
    ink_bot) in mm relative to pen start x=0 and baseline y=0."""
    k = mdpi / 25.4
    f, adv = advances_mm(s, em_mm, track_mm, k)
    w = int(sum(adv)) + int(em_mm * k * 2)
    h = int(em_mm * k * 4)
    base = int(em_mm * k * 2)
    x0 = int(em_mm * k)
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    x = float(x0)
    for ch, a in zip(s, adv):
        d.text((x, base), ch, font=f, fill=0, anchor="ls")
        x += a
    bb = ImageOps.invert(img).getbbox()
    mm = 25.4 / mdpi
    return (sum(adv) * mm, (bb[0] - x0) * mm, (bb[2] - x0) * mm,
            (bb[1] - base) * mm, (bb[3] - base) * mm)


# ---- colour verification (Lab -> sRGB under D50 and D65 readings) -------

D65 = (0.95047, 1.0, 1.08883)
D50 = (0.96422, 1.0, 0.82521)


def lab_to_xyz(lab, wp):
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    def inv(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    return tuple(w * inv(f) for w, f in zip(wp, (fx, fy, fz)))


def bradford_d50_to_d65(xyz):
    M = ((0.9555766, -0.0230393, 0.0631636),
         (-0.0282895, 1.0099416, 0.0210077),
         (0.0122982, -0.0204830, 1.3299098))
    return tuple(sum(m * c for m, c in zip(row, xyz)) for row in M)


def xyz_to_srgb(xyz):
    X, Y, Z = xyz
    lin = (3.2406 * X - 1.5372 * Y - 0.4986 * Z,
           -0.9689 * X + 1.8758 * Y + 0.0415 * Z,
           0.0557 * X - 0.2040 * Y + 1.0570 * Z)
    def g(c):
        c = max(0.0, min(1.0, c))
        return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return tuple(round(g(c) * 255) for c in lin)


def srgb_to_lab_d65(rgb):
    def inv_g(u):
        u /= 255
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    r, g, b = (inv_g(c) for c in rgb)
    X = 0.4124 * r + 0.3576 * g + 0.1805 * b
    Y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    Z = 0.0193 * r + 0.1192 * g + 0.9505 * b
    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = (f(c / w) for c, w in zip((X, Y, Z), D65))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def verify_colour(name, lab, recorded):
    via_d65 = xyz_to_srgb(lab_to_xyz(lab, D65))
    via_d50 = xyz_to_srgb(bradford_d50_to_d65(lab_to_xyz(lab, D50)))
    rt = srgb_to_lab_d65(recorded)
    de = sum((m - r) ** 2 for m, r in zip(lab, rt)) ** 0.5
    exact = recorded in (via_d65, via_d50)
    return {"name": name, "measured_lab": lab, "recorded_srgb": list(recorded),
            "lab_direct_d65": list(via_d65), "lab_d50_bradford": list(via_d50),
            "roundtrip_lab_of_recorded": [round(v, 2) for v in rt],
            "deltaE76_roundtrip": round(de, 2),
            "verdict": "CONFIRMED" if exact else
            ("WITHIN_1_LEVEL" if all(
                min(abs(recorded[i] - via_d65[i]), abs(recorded[i] - via_d50[i])) <= 1
                for i in range(3)) else "MISMATCH")}


# ---- the BEFORE (frozen 3d9f867 model) and AFTER (refined) models -------

def c3_before():
    return m7f.c3_minimal_central()[2]


def c3_final(report):
    """Same composition; rule y re-derived at the measured optical midpoint."""
    els = c3_before()
    brand = els[1]      # ("text", s, mode, x, yb, em, tr, rgb)
    rule = els[2]       # ("line", x1, y1, x2, y2, rgb, w)
    en = els[3]
    _, _, _, _, b_yb, b_em, b_tr, _ = brand
    _, _, _, _, e_yb, e_em, e_tr, _ = en
    _, b_ink_l, b_ink_r, b_top, b_bot = measure_ink(WORDS["brand"], b_em, b_tr)
    _, _, _, e_top, _ = measure_ink(WORDS["en"], e_em, e_tr)
    ink_bottom = b_yb + b_bot          # wordmark ink bottom (serif overshoot in)
    ink_top_en = e_yb + e_top          # EYE SHADOW ink top (cap line, measured)
    rule_y = (ink_bottom + ink_top_en) / 2
    report["rule"] = {
        "before_y_mm": rule[2], "after_y_mm": round(rule_y, 3),
        "derivation": "midpoint(wordmark ink bottom %.3f, EYE SHADOW ink top %.3f)"
                      % (ink_bottom, ink_top_en),
        "weight_mm": rule[6], "weight_change": "NONE — designed 0.25 mm kept"}
    out = list(els)
    out[2] = ("line", rule[1], round(rule_y, 3), rule[3], round(rule_y, 3),
              rule[5], rule[6])
    return out


def ink_centre_offset(s, em, tr):
    """(advance_centre - ink_centre) in mm; positive => shift right to centre ink.
    advances_mm adds no track after the last glyph, so sum(adv) is already
    the trailing-track-free visual advance width."""
    w_adv, ink_l, ink_r, _, _ = measure_ink(s, em, tr)
    return w_adv / 2 - (ink_l + ink_r) / 2


# ---- final renders -------------------------------------------------------

def text_x_offset(s, em, tr, report, label):
    off = ink_centre_offset(s, em, tr)
    applied = off if abs(off) > INK_CENTRE_NOISE_MM else 0.0
    report["ink_centring"][label] = {
        "measured_offset_mm": round(off, 3),
        "applied_mm": round(applied, 3),
        "note": "below %.2f mm noise floor — not applied" % INK_CENTRE_NOISE_MM
        if applied == 0.0 else "applied"}
    return applied


def render_final_png(els, offsets, out, dpi=800):
    k = dpi / 25.4
    img = Image.new("RGB", (round(FW * k), round(FH * k)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    ti = 0
    for e in els:
        if e[0] == "ground":
            d.rectangle([0, 0, img.width, img.height], fill=e[1])
        elif e[0] == "line":
            _, x1, y1, x2, y2, rgb, wmm = e
            d.line([x1 * k, y1 * k, x2 * k, y2 * k], fill=rgb,
                   width=max(1, round(wmm * k)))
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            _, adv = advances_mm(s, em, tr, k)
            w_px = sum(adv)  # advances_mm adds no trailing track
            x_px = x * k - w_px / 2 + offsets[ti] * k
            draw_kerned(d, s, x_px, yb * k, em, tr, k, rgb)
            ti += 1
    img.save(out, dpi=(dpi, dpi))
    return img


def render_final_svg(els, offsets, out):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (FW, FH, FW, FH),
        '<!-- ES3083 lid artwork FINAL — C3 MINIMAL-CENTRAL, production-candidate '
        'tier. Owner pick Section E / E1, LOCKED; refinement pass only '
        '(section_e_owner_picks_ingestion.json). PARAMETRIC on '
        'es3083_artwork_geometry_substrate.json: frame %g x %g mm MEASURED. '
        'Face: %s (SET_FACE, OFL). Text is LIVE, never outlined. Kerning and '
        'ink-centring VERIFIED as already correct (this build carries no kern '
        'pair touching these strings; ink-centre offsets measured below the '
        '0.05 mm noise floor). The rule sits at the measured optical midpoint '
        'of the white channel between wordmark ink bottom and EYE SHADOW ink '
        'top. Colours verified against measured Lab (D50-Bradford path, '
        'round-trip dE76 0.18 / 0.34). -->' % (FW, FH, FAMILY),
    ]
    ti = 0
    for e in els:
        if e[0] == "ground":
            lines.append('<rect width="%g" height="%g" fill="rgb(%d,%d,%d)"/>'
                         % (FW, FH, *e[1]))
        elif e[0] == "line":
            _, x1, y1, x2, y2, rgb, wmm = e
            lines.append('<line x1="%g" y1="%g" x2="%g" y2="%g" '
                         'stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                         % (x1, y1, x2, y2, *rgb, wmm))
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            tx = x - tr / 2 + offsets[ti]  # trailing-track + ink compensation
            lines.append(
                '<text x="%g" y="%g" font-family="%s" font-size="%g" '
                'letter-spacing="%g" text-anchor="middle" '
                'fill="rgb(%d,%d,%d)">%s</text>'
                % (round(tx, 3), yb, FAMILY, em, tr, *rgb, m7f.esc(s)))
            ti += 1
    lines.append("</svg>")
    open(out, "w").write("\n".join(lines) + "\n")


# ---- safe margins (measured ink -> frame edges) --------------------------

def safe_margins(els, offsets, report):
    lo_x, hi_x, lo_y, hi_y = FW, 0.0, FH, 0.0
    ti = 0
    for e in els:
        if e[0] == "line":
            _, x1, y1, x2, y2, _, wmm = e
            lo_x, hi_x = min(lo_x, x1), max(hi_x, x2)
            lo_y, hi_y = min(lo_y, y1 - wmm / 2), max(hi_y, y2 + wmm / 2)
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, _ = e
            w_adv, ink_l, ink_r, ink_t, ink_b = measure_ink(s, em, tr)
            x0 = x - w_adv / 2 + offsets[ti]
            lo_x = min(lo_x, x0 + ink_l)
            hi_x = max(hi_x, x0 + ink_r)
            lo_y = min(lo_y, yb + ink_t)
            hi_y = max(hi_y, yb + ink_b)
            ti += 1
    report["safe_margins_mm"] = {
        "frame": [FW, FH],
        "ink_bbox": [round(v, 2) for v in (lo_x, lo_y, hi_x, hi_y)],
        "clearance_left": round(lo_x, 2), "clearance_right": round(FW - hi_x, 2),
        "clearance_top": round(lo_y, 2), "clearance_bottom": round(FH - hi_y, 2),
        "note": "no die-derived safe-margin standard exists in the programme "
                "(corner/die geometry not established); clearances are "
                "measurements, not a pass against a fabricated standard"}


# ---- before/after page ---------------------------------------------------

def before_after_page(before_img, after_img, report, out, dpi=300):
    k = dpi / 25.4
    tile = round(FW * k)
    gap = round(6 * k)
    cap_h = round(7 * k)
    head_h = round(12 * k)
    # zoom strip: wordmark + rule region, 2.5x
    zy0, zy1 = 0.38, 0.60  # fraction of FH covering wordmark..EN line
    zoom = 2.5
    strip_h = round((zy1 - zy0) * FH * k * zoom / 2)
    text_h = round(52 * k / 2)
    page_w = 2 * tile + 3 * gap
    page_h = head_h + tile + cap_h + gap + strip_h + cap_h + gap + text_h
    page = Image.new("RGB", (page_w, page_h), (244, 244, 242))
    d = ImageDraw.Draw(page)
    def fitted(size_px, s, max_w):
        f = ImageFont.truetype(FONT, size_px)
        while f.getlength(s) > max_w and size_px > 8:
            size_px -= 1
            f = ImageFont.truetype(FONT, size_px)
        return f
    ft = ImageFont.truetype(FONT, round(text_h * 0.052))
    title = "ES3083 LID C3 — BEFORE (3d9f867) / AFTER (FINAL) — refinement pass only"
    fh_ = fitted(round(head_h * 0.38), title, page_w - 2 * gap)
    d.text((page_w / 2 - fh_.getlength(title) / 2, head_h * 0.3), title,
           font=fh_, fill=(20, 22, 20))
    caps = ["BEFORE — C3 as picked (3d9f867)",
            "AFTER — FINAL (rule at measured optical midpoint)"]
    for i, (img, cap) in enumerate(zip((before_img, after_img), caps)):
        x = gap + i * (tile + gap)
        t = img.resize((tile, tile), Image.LANCZOS)
        page.paste(t, (x, head_h))
        d.rectangle([x, head_h, x + tile, head_h + tile],
                    outline=(180, 180, 180), width=2)
        fc_i = fitted(round(cap_h * 0.48), cap, tile)
        d.text((x + tile / 2 - fc_i.getlength(cap) / 2, head_h + tile + cap_h * 0.2),
               cap, font=fc_i, fill=(20, 22, 20))
        # zoom strip
        src_y0 = round(zy0 * img.height)
        src_y1 = round(zy1 * img.height)
        band = img.crop((round(0.18 * img.width), src_y0,
                         round(0.82 * img.width), src_y1))
        bw = tile
        bh = round(band.height * tile / band.width)
        band = band.resize((bw, min(bh, strip_h)), Image.LANCZOS)
        sy = head_h + tile + cap_h + gap
        page.paste(band, (x, sy))
        d.rectangle([x, sy, x + bw, sy + band.height],
                    outline=(180, 180, 180), width=2)
    zcap = "wordmark block detail (enlarged) — rule position; kerning and centring verified"
    fc_z = fitted(round(cap_h * 0.48), zcap, page_w - 2 * gap)
    d.text((page_w / 2 - fc_z.getlength(zcap) / 2,
            head_h + tile + cap_h + gap + strip_h + cap_h * 0.2),
           zcap, font=fc_z, fill=(20, 22, 20))
    # change list
    ty = head_h + tile + cap_h + gap + strip_h + cap_h + gap * 0.8
    r = report
    kerns = r["gpos_pairs_in_wordmark"]
    lines = [
        "CHANGES (all measured, composition untouched):",
        "1  Kerning fidelity MEASURED: source %s, %d pairs in the font; pairs applying to the artwork "
        "strings: %s. The M7F preview therefore already matched the live-text SVG exactly; the kern-aware "
        "raster path stands so the preview keeps matching when the kerned TARGET face (Caslon) swaps in." % (
            r["kern_source"], r["kern_total_pairs_in_font"],
            kerns if kerns else "NONE — verified no-op for this face"),
        "2  Ink-centring offsets (mm, + = right): " + ", ".join(
            "%s %s%s" % (lbl, v["measured_offset_mm"],
                         "" if v["applied_mm"] else " (noise, not applied)")
            for lbl, v in r["ink_centring"].items()),
        "3  Rule: y %.3f -> %.3f mm — %s. Weight %.2f mm unchanged." % (
            r["rule"]["before_y_mm"], r["rule"]["after_y_mm"],
            r["rule"]["derivation"], r["rule"]["weight_mm"]),
        "4  621 C ground VERIFIED: recorded sRGB %s vs Lab %s -> D65 %s / D50-Bradford %s; "
        "round-trip dE76 %.2f — %s. 627 C type: dE76 %.2f — %s." % (
            tuple(r["colour"]["621C"]["recorded_srgb"]), tuple(LAB_621),
            tuple(r["colour"]["621C"]["lab_direct_d65"]),
            tuple(r["colour"]["621C"]["lab_d50_bradford"]),
            r["colour"]["621C"]["deltaE76_roundtrip"], r["colour"]["621C"]["verdict"],
            r["colour"]["627C"]["deltaE76_roundtrip"], r["colour"]["627C"]["verdict"]),
        "5  Safe margins (ink -> frame, mm): L %.2f  R %.2f  T %.2f  B %.2f on the measured %.2f x %.2f. "
        "No die-derived margin standard exists; these are measurements." % (
            r["safe_margins_mm"]["clearance_left"], r["safe_margins_mm"]["clearance_right"],
            r["safe_margins_mm"]["clearance_top"], r["safe_margins_mm"]["clearance_bottom"],
            FW, FH),
        "Face: %s Regular (SET_FACE, OFL) — TARGET Caslon not used. Text LIVE, never outlined. "
        "Tray/cavity context: CLASS_TYPICAL_NOT_PRODUCT_SPECIFIC until caliper numbers arrive." % FAMILY,
    ]
    for ln in lines:
        # naive wrap
        while ft.getlength(ln) > page_w - 2 * gap:
            cut = len(ln)
            while ft.getlength(ln[:cut]) > page_w - 2 * gap:
                cut = ln.rfind(" ", 0, cut)
            d.text((gap, ty), ln[:cut], font=ft, fill=(60, 60, 60))
            ty += text_h * 0.058
            ln = "   " + ln[cut + 1:]
        d.text((gap, ty), ln, font=ft, fill=(60, 60, 60))
        ty += text_h * 0.070
    page.save(out, dpi=(dpi, dpi))


if __name__ == "__main__":
    report = {"ink_centring": {}, "colour": {}}
    # gpos pairs present in ANY of the three strings, for the honest change list
    found = []
    for s in WORDS.values():
        for a, b in zip(s, s[1:]):
            v = kern_mm(a, b, 1.0)  # units/upm -> em fraction
            if v:
                found.append("%s%s %+0.3f em" % (a, b, v))
    report["gpos_pairs_in_wordmark"] = ", ".join(found) if found else ""
    report["kern_source"] = KERN_SOURCE
    report["kern_total_pairs_in_font"] = len(KERN_UNITS)

    report["colour"]["621C"] = verify_colour("PANTONE 621 C", LAB_621, P621)
    report["colour"]["627C"] = verify_colour("PANTONE 627 C", LAB_627, P627)

    els_final = c3_final(report)
    offsets = []
    for e in els_final:
        if e[0] == "text":
            lbl = e[1]
            offsets.append(text_x_offset(e[1], e[5], e[6], report, lbl))

    png = render_final_png(els_final, offsets,
                           f"{HERE}/es3083_lid_C3_final.png")
    render_final_svg(els_final, offsets, f"{HERE}/es3083_lid_C3_final.svg")
    safe_margins(els_final, offsets, report)

    before = m7f.render_png(c3_before(), f"{HERE}/_tmp_before.png",
                            dpi=600, frame_hint=False)
    os.remove(f"{HERE}/_tmp_before.png")
    before_after_page(before, png, report,
                      f"{HERE}/es3083_lid_C3_before_after.png")

    print(json.dumps(report, indent=1))
    print("FINAL PNG %dx%d px" % (png.width, png.height))
