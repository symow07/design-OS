"""ES3083 ALTERNATE LID — A2 TWELVE-ROSETTE finalisation, production-candidate tier.

Authorized act: OWNER_BLOCKER_CLEARANCE.md §J (J1: "A2 Twelve-Rosette", no
adjustments stated), ingested in ../owner_pick_ingestion.json. REFINEMENT
PASS ONLY per the E1/C3 precedent — the interleaved twelve-lobed rosette
composition is preserved, never re-explored.

WHAT THE REFINEMENT ACTUALLY IS (each measured, none hand-placed; the
measurement machinery is IMPORTED from the proven finalize_lid_C3, not
re-implemented):
1. ROSETTE AT THE MEASURED OPTICAL CENTRE — the rosette centre sat at the
   designed 0.435*FH; the final centre equalises the measured clearances
   frame-top -> rosette ink-top and rosette ink-bottom -> wordmark ink-top
   (the C3 rule-midpoint move, applied to the rosette block). Ring geometry
   itself is untouched — the same rings, shifted as one body.
2. INK-CENTRING BY MEASUREMENT — both centred lines recentred by measured
   ink extents, applied only above the C3-declared 0.05 mm noise floor.
3. KERNING — verified against the SET_FACE's kern data for BOTH strings
   including the new "EYE SHADOW · SOMBRA DE OJOS" combined line (a string
   the C3 verification never covered).
4. VERIFICATION, NOT CHANGE — stroke weight 0.18 mm and type sizes are the
   picked composition's treatment variables, kept; no die/stock or minimum-
   stroke standard exists in the programme, so clearances and weights are
   REPORTED as measurements, never judged against a fabricated standard.
   Colour sRGB values are the substrate constants whose Lab round-trip was
   verified at C3 finalisation (dE76 0.18 / 0.34) — cited, not re-derived.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
os.chdir(ROOT)
REPO = os.path.dirname(ROOT)

sys.path.insert(0, os.path.join(HERE, "..", "candidates"))
sys.path.insert(0, os.path.join(ROOT, "docs", "roadmap", "palt_m7",
                                "lid_artwork"))
import render_candidates as a2src  # noqa: E402 — the picked BEFORE model
import finalize_lid_C3 as c3f      # noqa: E402 — proven measurement machinery

FW, FH = a2src.FW, a2src.FH
P621, P627 = a2src.P621, a2src.P627
FONT, FAMILY = a2src.FONT, a2src.FAMILY
NOISE = c3f.INK_CENTRE_NOISE_MM
STROKE = 0.18  # the picked ring weight (treatment variable, kept)


def ring_ink_bbox(rings):
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    h = STROKE / 2
    return (min(xs) - h, min(ys) - h, max(xs) + h, max(ys) + h)


def a2_before():
    return a2src.a2_rosette()[3]


def finalise(report):
    els = a2_before()
    ground = els[0]
    rings_before = [e[1] for e in els if e[0] == "poly"]
    texts = [e for e in els if e[0] == "text"]
    brand, biling = texts[0], texts[1]

    # 1. rosette optical centring (measured channel, C3 midpoint move)
    _, _, _, b_top, b_bot = c3f.measure_ink(brand[1], brand[5], brand[6])
    wordmark_ink_top = brand[4] + b_top
    bx0, by0, bx1, by1 = ring_ink_bbox(rings_before)
    r_half = (by1 - by0) / 2
    cy_designed = (by0 + by1) / 2
    cy_optical = wordmark_ink_top / 2
    dy = cy_optical - cy_designed
    applied_dy = dy if abs(dy) > NOISE else 0.0
    report["rosette_centring"] = {
        "designed_centre_y_mm": round(cy_designed, 3),
        "wordmark_ink_top_mm": round(wordmark_ink_top, 3),
        "optical_centre_y_mm": round(cy_optical, 3),
        "shift_mm": round(dy, 3),
        "applied_mm": round(applied_dy, 3),
        "derivation": "equalise frame-top->rosette-ink and rosette-ink->"
                      "wordmark-ink clearances: cy = wordmark_ink_top/2 "
                      "= %.3f/2" % wordmark_ink_top,
        "ring_geometry": "UNTOUCHED — same rings shifted as one body"}
    rings_after = [[(x, y + applied_dy) for x, y in r] for r in rings_before]

    # 2. ink-centring of both lines (C3 machinery, C3 noise floor)
    report["ink_centring"] = {}
    offsets = []
    for e in texts:
        off = c3f.ink_centre_offset(e[1], e[5], e[6])
        applied = off if abs(off) > NOISE else 0.0
        offsets.append(applied)
        report["ink_centring"][e[1]] = {
            "measured_offset_mm": round(off, 3),
            "applied_mm": round(applied, 3),
            "note": "applied" if applied else
            "below %.2f mm noise floor — not applied" % NOISE}

    # 3. kerning verification INCLUDING the middot combined line
    found = []
    for e in texts:
        s = e[1]
        for a, b in zip(s, s[1:]):
            v = c3f.kern_mm(a, b, 1.0)
            if v:
                found.append("%s%s %+0.3f em" % (a, b, v))
    report["kerning"] = {
        "source": c3f.KERN_SOURCE,
        "pairs_in_font": len(c3f.KERN_UNITS),
        "pairs_touching_A2_strings": found if found else
        "NONE — verified no-op for both lines including the middot line"}

    # 4. type block gap + stroke weight: measured, reported, kept
    _, _, _, e_top, _ = c3f.measure_ink(biling[1], biling[5], biling[6])
    gap = (biling[4] + e_top) - (brand[4] + b_bot)
    report["type_block"] = {
        "wordmark_ink_bottom_mm": round(brand[4] + b_bot, 3),
        "bilingual_ink_top_mm": round(biling[4] + e_top, 3),
        "measured_gap_mm": round(gap, 3),
        "change": "NONE — the picked spacing kept; no spacing standard "
                  "exists in the programme"}
    report["stroke_weight"] = {
        "ring_mm": STROKE,
        "change": "NONE — treatment variable of the picked composition; "
                  "no die/stock or minimum-stroke standard exists in the "
                  "programme to judge it against"}
    report["colour"] = {
        "verdict": "CITED — 621C/627C sRGB are the substrate constants "
                   "verified at C3 finalisation (round-trip dE76 0.18 / "
                   "0.34, D50-Bradford path); same constants, not "
                   "re-derived (meta-work ban)"}
    return ground, rings_after, texts, offsets


# ---- renders (kern-aware raster via the C3 machinery) -------------------

def render_png(ground, rings, texts, offsets, out, dpi=800):
    k = dpi / 25.4
    img = Image.new("RGB", (round(FW * k), round(FH * k)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, img.height], fill=ground[1])
    for r in rings:
        px = [(x * k, y * k) for x, y in r]
        px.append(px[0])
        d.line(px, fill=P627, width=max(1, round(STROKE * k)), joint="curve")
    for e, off in zip(texts, offsets):
        _, s, mode, x, yb, em, tr, rgb = e
        _, adv = c3f.advances_mm(s, em, tr, k)
        x_px = x * k - sum(adv) / 2 + off * k
        c3f.draw_kerned(d, s, x_px, yb * k, em, tr, k, rgb)
    img.save(out, dpi=(dpi, dpi))
    return img


def render_svg(ground, rings, texts, offsets, report, out):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (FW, FH, FW, FH),
        '<!-- ES3083 ALTERNATE lid FINAL — A2 TWELVE-ROSETTE, production-'
        'candidate tier. Owner pick §J, LOCKED; refinement pass only '
        '(owner_pick_ingestion.json): rosette shifted %+0.3f mm to the '
        'measured optical centre (cy = wordmark ink top / 2), ring geometry '
        'untouched; ink-centring measured (below the 0.05 mm floor where '
        'not applied); kerning verified a no-op for BOTH lines including '
        'the middot line. PARAMETRIC on es3083_artwork_geometry_substrate.'
        'json: frame %g x %g mm MEASURED. Face: %s (SET_FACE, OFL). Text '
        'is LIVE, never outlined. Colours are the C3-verified substrate '
        'constants. -->'
        % (report["rosette_centring"]["applied_mm"], FW, FH, FAMILY),
        '<rect width="%g" height="%g" fill="rgb(%d,%d,%d)"/>'
        % (FW, FH, *ground[1]),
    ]
    for r in rings:
        d = "M " + " L ".join("%.3f %.3f" % (x, y) for x, y in r) + " Z"
        lines.append('<path d="%s" fill="none" stroke="rgb(%d,%d,%d)" '
                     'stroke-width="%g" stroke-linecap="round" '
                     'stroke-linejoin="round"/>' % (d, *P627, STROKE))
    for e, off in zip(texts, offsets):
        _, s, mode, x, yb, em, tr, rgb = e
        tx = x - tr / 2 + off  # the artwork's own trailing-track anchor
        lines.append(
            '<text x="%g" y="%g" font-family="%s" font-size="%g" '
            'letter-spacing="%g" text-anchor="middle" '
            'fill="rgb(%d,%d,%d)">%s</text>'
            % (round(tx, 3), yb, FAMILY, em, tr, *rgb, a2src.esc(s)))
    lines.append("</svg>")
    open(out, "w").write("\n".join(lines) + "\n")


def safe_margins(rings, texts, offsets, report):
    bx0, by0, bx1, by1 = ring_ink_bbox(rings)
    lo_x, lo_y, hi_x, hi_y = bx0, by0, bx1, by1
    for e, off in zip(texts, offsets):
        _, s, mode, x, yb, em, tr, _ = e
        w_adv, ink_l, ink_r, ink_t, ink_b = c3f.measure_ink(s, em, tr)
        x0 = x - w_adv / 2 + off
        lo_x = min(lo_x, x0 + ink_l)
        hi_x = max(hi_x, x0 + ink_r)
        lo_y = min(lo_y, yb + ink_t)
        hi_y = max(hi_y, yb + ink_b)
    report["safe_margins_mm"] = {
        "frame": [FW, FH],
        "ink_bbox": [round(v, 2) for v in (lo_x, lo_y, hi_x, hi_y)],
        "clearance_left": round(lo_x, 2),
        "clearance_right": round(FW - hi_x, 2),
        "clearance_top": round(lo_y, 2),
        "clearance_bottom": round(FH - hi_y, 2),
        "note": "no die-derived safe-margin standard exists in the "
                "programme; clearances are measurements, not a pass "
                "against a fabricated standard"}


def before_after_page(before_img, after_img, report, out, dpi=300):
    k = dpi / 25.4
    tile = round(FW * k)
    gap = round(6 * k)
    cap_h = round(7 * k)
    head_h = round(12 * k)
    text_h = round(46 * k / 2)
    page_w = 2 * tile + 3 * gap
    page_h = head_h + tile + cap_h + gap + text_h
    page = Image.new("RGB", (page_w, page_h), (244, 244, 242))
    d = ImageDraw.Draw(page)
    def fitted(size_px, s, max_w):
        f = ImageFont.truetype(FONT, size_px)
        while f.getlength(s) > max_w and size_px > 8:
            size_px -= 1
            f = ImageFont.truetype(FONT, size_px)
        return f

    fc = ImageFont.truetype(FONT, round(cap_h * 0.48))
    ft = ImageFont.truetype(FONT, round(text_h * 0.062))
    title = ("ES3083 ALTERNATE LID A2 — BEFORE (as picked) / AFTER (FINAL)"
             " — refinement pass only")
    fh_ = fitted(round(head_h * 0.36), title, page_w - 2 * gap)
    d.text((page_w / 2 - fh_.getlength(title) / 2, head_h * 0.3), title,
           font=fh_, fill=(20, 22, 20))
    caps = ["BEFORE — A2 as picked (contact sheet)",
            "AFTER — FINAL (rosette at measured optical centre)"]
    for i, (img, cap) in enumerate(zip((before_img, after_img), caps)):
        x = gap + i * (tile + gap)
        t = img.resize((tile, tile), Image.LANCZOS)
        page.paste(t, (x, head_h))
        d.rectangle([x, head_h, x + tile, head_h + tile],
                    outline=(180, 180, 180), width=2)
        d.text((x + tile / 2 - fc.getlength(cap) / 2,
                head_h + tile + cap_h * 0.2), cap, font=fc, fill=(20, 22, 20))
    r = report
    rc = r["rosette_centring"]
    lines = [
        "CHANGES (all measured, composition untouched):",
        "1  Rosette centre y %.3f -> %.3f mm (shift %+0.3f): %s. Rings themselves untouched." % (
            rc["designed_centre_y_mm"], rc["optical_centre_y_mm"],
            rc["applied_mm"], rc["derivation"]),
        "2  Ink-centring (mm, + = right): " + ", ".join(
            "'%s' %+0.3f%s" % (s[:12], v["measured_offset_mm"],
                               "" if v["applied_mm"] else " (noise)")
            for s, v in r["ink_centring"].items()),
        "3  Kerning: %s; pairs touching the A2 strings: %s" % (
            r["kerning"]["source"],
            r["kerning"]["pairs_touching_A2_strings"] if isinstance(
                r["kerning"]["pairs_touching_A2_strings"], str)
            else ", ".join(r["kerning"]["pairs_touching_A2_strings"])),
        "4  Type gap %.3f mm and ring stroke %.2f mm kept — treatment variables of the pick; no programme standard." % (
            r["type_block"]["measured_gap_mm"], r["stroke_weight"]["ring_mm"]),
        "5  Safe margins (ink -> frame, mm): L %.2f  R %.2f  T %.2f  B %.2f on the measured %.2f x %.2f — measurements, no fabricated standard." % (
            r["safe_margins_mm"]["clearance_left"],
            r["safe_margins_mm"]["clearance_right"],
            r["safe_margins_mm"]["clearance_top"],
            r["safe_margins_mm"]["clearance_bottom"], FW, FH),
        "Colours: C3-verified substrate constants (dE76 0.18/0.34), cited. "
        "Face: %s Regular (SET_FACE, OFL). Text LIVE, never outlined." % FAMILY,
    ]
    ty = head_h + tile + cap_h + gap * 0.8
    for ln in lines:
        while ft.getlength(ln) > page_w - 2 * gap:
            cut = len(ln)
            while ft.getlength(ln[:cut]) > page_w - 2 * gap:
                cut = ln.rfind(" ", 0, cut)
            d.text((gap, ty), ln[:cut], font=ft, fill=(60, 60, 60))
            ty += text_h * 0.068
            ln = "   " + ln[cut + 1:]
        d.text((gap, ty), ln, font=ft, fill=(60, 60, 60))
        ty += text_h * 0.082
    page.save(out, dpi=(dpi, dpi))


if __name__ == "__main__":
    report = {}
    ground, rings, texts, offsets = finalise(report)
    safe_margins(rings, texts, offsets, report)
    png = render_png(ground, rings, texts, offsets,
                     f"{HERE}/es3083_lid_A2_final.png")
    render_svg(ground, rings, texts, offsets, report,
               f"{HERE}/es3083_lid_A2_final.svg")
    before = a2src.render_png(a2_before(), f"{HERE}/_tmp_before.png",
                              dpi=600, frame_hint=False)
    os.remove(f"{HERE}/_tmp_before.png")
    before_after_page(before, png, report,
                      f"{HERE}/es3083_lid_A2_before_after.png")
    record = {
        "record_type": "h2_a2_finalisation/1.0",
        "finalised_on": "2026-08-15",
        "authority": "OWNER_BLOCKER_CLEARANCE.md §J via owner_pick_ingestion.json",
        "precedent": "E1/C3 finalisation (finalize_lid_C3.py) — machinery imported, not re-implemented",
        "before": "../candidates/es3083_alt_lid_A2_twelve_rosette.svg (as picked)",
        "final_svg": "es3083_lid_A2_final.svg",
        "final_png": "es3083_lid_A2_final.png (800 dpi)",
        "measurements": report,
    }
    with open(f"{HERE}/a2_finalisation_record.json", "w") as f:
        json.dump(record, f, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1))
    print("FINAL PNG %dx%d px" % (png.width, png.height))
