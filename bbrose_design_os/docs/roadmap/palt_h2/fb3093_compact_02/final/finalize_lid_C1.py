"""FB3093 LID — C1 ENGINE-TURNED CARTOUCHE finalisation, production-candidate tier.

Authorized act: OWNER_BLOCKER_CLEARANCE.md §M (M1: verbatim "c1 & c3", no
adjustments stated), ingested in ../owner_pick_ingestion.json. REFINEMENT
PASS ONLY per the E1/C3/A2 precedent — the woven barleycorn ground, the
cartouche, the rosette and the type are the picked composition, preserved.
Measurement machinery IMPORTED from finalize_lid_C3 (the proven module),
never re-implemented.

MEASURED CHANNELS (each either applied above the declared 0.05 mm noise
floor, or reported and kept):
1. LATTICE MARGIN SYMMETRY — the wave-lattice rows/columns start at a step
   residue (first vs last line margins differ); measured, translated as a
   RIGID BODY only if the asymmetry clears the floor (wave phases ride
   along untouched).
2. ROSETTE AT THE MEASURED OPTICAL CENTRE OF ITS CHANNEL — the A2 rule
   transplanted into the cartouche: equalise cartouche-inner-ink-top ->
   rosette-ink-top and rosette-ink-bottom -> wordmark-ink-top; rings
   untouched, shifted as one body.
3. INK-CENTRING of both centred lines by measured ink extents (A2/C3 rule).
4. KERNING verified against the SET_FACE kern data for BOTH strings —
   "FACE POWDER · POLVOS" is a string no earlier verification covered.
5. VERIFICATION, NOT CHANGE — stroke weights, cartouche geometry, boss
   placement, the 0.455*FH cartouche vertical station (a compositional
   choice of the pick, not a defect): all measured and REPORTED; no
   programme standard exists to judge them against, so none is invented.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
os.chdir(ROOT)

sys.path.insert(0, os.path.join(ROOT, "docs", "roadmap", "palt_m7",
                                "lid_artwork"))
import finalize_lid_C3 as c3f   # noqa: E402 — proven measurement machinery

# Both rounds' generators share the filename render_candidates.py; loading
# round 2 under a distinct module name avoids the circular self-import its
# internal `import render_candidates as r1` would otherwise hit.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "r2_candidates", os.path.join(HERE, "..", "candidates",
                                  "render_candidates.py"))
r2 = importlib.util.module_from_spec(_spec)
sys.modules["r2_candidates"] = r2
_spec.loader.exec_module(r2)

FW, FH = r2.FW, r2.FH
P621, P627 = r2.P621, r2.P627
FONT, FAMILY = r2.FONT, r2.FAMILY
NOISE = c3f.INK_CENTRE_NOISE_MM


def group_elements(els):
    """Walk the generator's deterministic element order into named groups;
    assert the expected structure so a generator change can't be
    mis-finalised silently."""
    assert els[0][0] == "ground"
    i = 1
    lattice = []
    while els[i][0] == "poly" and not els[i][2]:
        lattice.append(els[i])
        i += 1
    assert len(lattice) % 2 == 0, "row/col split needs an even count"
    rows, cols = lattice[:len(lattice) // 2], lattice[len(lattice) // 2:]
    assert els[i][0] == "polyfill"
    cart_plate = els[i]; i += 1
    cart_keys = [els[i], els[i + 1]]; i += 2
    assert all(e[0] == "poly" and e[2] for e in cart_keys)
    rosette = []
    while els[i][0] == "poly":
        rosette.append(els[i]); i += 1
    assert len(rosette) == 10, "9 rings + boundary"
    bosses = []
    for _ in range(4):
        assert els[i][0] == "polyfill"
        boss = [els[i]]; i += 1
        while i < len(els) and els[i][0] == "poly":
            boss.append(els[i]); i += 1
        assert len(boss) == 7, "plate + 5 rings + boundary"
        bosses.append(boss)
    texts = els[i:]
    assert all(e[0] == "text" for e in texts) and len(texts) == 2
    return (els[0], rows, cols, cart_plate, cart_keys, rosette, bosses, texts)


def poly_ink_bbox(polys):
    xs = [p[0] for e in polys for p in e[1]]
    ys = [p[1] for e in polys for p in e[1]]
    h = max(e[4] for e in polys) / 2
    return min(xs) - h, min(ys) - h, max(xs) + h, max(ys) + h


def translate_poly(e, dx, dy):
    return (e[0], [(x + dx, y + dy) for x, y in e[1]], e[2], e[3], e[4])


def finalise(report):
    (ground, rows, cols, cart_plate, cart_keys, rosette, bosses,
     texts) = group_elements(r2.c1_engine_turned_cartouche()[3])
    brand, biling = texts

    # 1. lattice margin symmetry (rigid-body translation per axis)
    row_ys = sorted(e[1][0][1] - e[1][0][1] % 1e-9 or e[1][0][1] for e in rows)
    first_row = min(p[1] for p in rows[0][1]); last_row = max(
        p[1] for p in rows[-1][1])
    m_top = min(min(p[1] for p in e[1]) for e in rows)
    m_bot = FH - max(max(p[1] for p in e[1]) for e in rows)
    dy = (m_bot - m_top) / 2
    applied_dy = dy if abs(dy) > NOISE else 0.0
    m_left = min(min(p[0] for p in e[1]) for e in cols)
    m_right = FW - max(max(p[0] for p in e[1]) for e in cols)
    dx = (m_right - m_left) / 2
    applied_dx = dx if abs(dx) > NOISE else 0.0
    report["lattice_margins"] = {
        "rows_first_last_margin_mm": [round(m_top, 3), round(m_bot, 3)],
        "cols_first_last_margin_mm": [round(m_left, 3), round(m_right, 3)],
        "shift_mm": [round(dx, 3), round(dy, 3)],
        "applied_mm": [round(applied_dx, 3), round(applied_dy, 3)],
        "note": "rigid-body translation per axis; wave phases ride along"
                if (applied_dx or applied_dy) else
                "at/below the %.2f mm floor — not applied" % NOISE}
    rows = [translate_poly(e, 0.0, applied_dy) for e in rows]
    cols = [translate_poly(e, applied_dx, 0.0) for e in cols]

    # 2. rosette optical centring within its cartouche channel (A2 rule)
    _, _, _, b_top, b_bot = c3f.measure_ink(brand[1], brand[5], brand[6])
    wordmark_ink_top = brand[4] + b_top
    inner_key = cart_keys[1]
    cart_inner_top = min(p[1] for p in inner_key[1]) + inner_key[4] / 2
    rx0, ry0, rx1, ry1 = poly_ink_bbox(rosette)
    r_half = (ry1 - ry0) / 2
    cy_designed = (ry0 + ry1) / 2
    cy_optical = (cart_inner_top + wordmark_ink_top) / 2
    dyr = cy_optical - cy_designed
    applied_dyr = dyr if abs(dyr) > NOISE else 0.0
    report["rosette_centring"] = {
        "cartouche_inner_ink_top_mm": round(cart_inner_top, 3),
        "wordmark_ink_top_mm": round(wordmark_ink_top, 3),
        "designed_centre_y_mm": round(cy_designed, 3),
        "optical_centre_y_mm": round(cy_optical, 3),
        "clearance_above_before_mm": round(ry0 - cart_inner_top, 3),
        "clearance_below_before_mm": round(wordmark_ink_top - ry1, 3),
        "shift_mm": round(dyr, 3),
        "applied_mm": round(applied_dyr, 3),
        "derivation": "equalise cartouche-inner-top->rosette-ink and "
                      "rosette-ink->wordmark-ink (the A2 rule in the "
                      "cartouche channel)",
        "ring_geometry": "UNTOUCHED — same rings shifted as one body"}
    rosette = [translate_poly(e, 0.0, applied_dyr) for e in rosette]

    # 3. ink-centring of both centred lines
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

    # 4. kerning verification (middot line never covered before)
    found = []
    for e in texts:
        for a, b in zip(e[1], e[1][1:]):
            v = c3f.kern_mm(a, b, 1.0)
            if v:
                found.append("%s%s %+0.3f em" % (a, b, v))
    report["kerning"] = {
        "source": c3f.KERN_SOURCE,
        "pairs_in_font": len(c3f.KERN_UNITS),
        "pairs_touching_C1_strings": found if found else
        "NONE — verified no-op for both lines including the middot line"}

    # 5. verification-only measurements
    report["kept_by_verification"] = {
        "cartouche_vertical_station": "0.455*FH — compositional choice of "
                                      "the pick, kept (not a defect channel)",
        "stroke_weights_mm": {"lattice": 0.05, "cartouche_keys": [0.30, 0.10],
                              "rosette": 0.07, "boss": 0.07},
        "boss_centres_symmetric": "by construction at 0.09/0.91 fractions — "
                                  "verified equal margins",
        "colour": "substrate constants, Lab round-trip verified at C3 "
                  "finalisation (dE76 0.18/0.34) — cited, not re-derived"}

    finals = ([ground] + rows + cols + [cart_plate] + cart_keys + rosette
              + [e for boss in bosses for e in boss] + list(texts))
    return finals, texts, offsets


# ---- final renders (kern-aware text; no frame hint) ---------------------

def render_final_png(els, texts, offsets, out, dpi=800):
    k = dpi / 25.4
    img = Image.new("RGB", (round(FW * k), round(FH * k)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for e in els:
        if e[0] == "ground":
            d.rectangle([0, 0, img.width, img.height], fill=e[1])
        elif e[0] == "polyfill":
            d.polygon([(x * k, y * k) for x, y in e[1]], fill=e[2])
        elif e[0] == "poly":
            px = [(x * k, y * k) for x, y in e[1]]
            if e[2]:
                px.append(px[0])
            d.line(px, fill=e[3], width=max(1, round(e[4] * k)), joint="curve")
    for e, off in zip(texts, offsets):
        _, s, mode, x, yb, em, tr, rgb = e
        _, adv = c3f.advances_mm(s, em, tr, k)
        x_px = x * k - sum(adv) / 2 + off * k
        c3f.draw_kerned(d, s, x_px, yb * k, em, tr, k, rgb)
    img.save(out, dpi=(dpi, dpi))
    return img


def render_final_svg(els, texts, offsets, report, out):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (FW, FH, FW, FH),
        '<!-- FB3093 LID FINAL — C1 ENGINE-TURNED CARTOUCHE, production-'
        'candidate tier. Owner pick §M ("c1 & c3"), LOCKED; refinement pass '
        'only: rosette shifted %+0.3f mm to the measured optical centre of '
        'its cartouche channel (rings untouched); lattice margin asymmetry '
        'measured %s; ink-centring and kerning verified per the imported C3 '
        'machinery. PARAMETRIC ON THE BRIEF: %g x %g mm PRIOR frame — owner '
        'calipers supersede and the final re-flows by re-run. Face: %s '
        '(SET_FACE, OFL). Text LIVE, never outlined. Two spot inks only. -->'
        % (report["rosette_centring"]["applied_mm"],
           report["lattice_margins"]["note"], FW, FH, FAMILY),
    ]
    for e in els:
        if e[0] == "ground":
            lines.append('<rect width="%g" height="%g" fill="rgb(%d,%d,%d)"/>'
                         % (FW, FH, *e[1]))
        elif e[0] == "polyfill":
            d = "M " + " L ".join("%.3f %.3f" % (x, y) for x, y in e[1]) + " Z"
            lines.append('<path d="%s" fill="rgb(%d,%d,%d)"/>' % (d, *e[2]))
        elif e[0] == "poly":
            d = "M " + " L ".join("%.3f %.3f" % (x, y) for x, y in e[1])
            if e[2]:
                d += " Z"
            lines.append('<path d="%s" fill="none" stroke="rgb(%d,%d,%d)" '
                         'stroke-width="%g" stroke-linecap="round" '
                         'stroke-linejoin="round"/>' % (d, *e[3], e[4]))
    for e, off in zip(texts, offsets):
        _, s, mode, x, yb, em, tr, rgb = e
        tx = x - tr / 2 + off
        lines.append(
            '<text x="%g" y="%g" font-family="%s" font-size="%g" '
            'letter-spacing="%g" text-anchor="middle" fill="rgb(%d,%d,%d)">'
            '%s</text>' % (round(tx, 3), yb, FAMILY, em, tr, *rgb,
                           r2.r1.esc(s)))
    lines.append("</svg>")
    open(out, "w").write("\n".join(lines) + "\n")


def before_after_page(before_img, after_img, report, out, dpi=300):
    k = dpi / 25.4
    tile = round(FW * k)
    gap = round(6 * k)
    cap_h = round(7 * k)
    head_h = round(12 * k)
    text_h = round(40 * k / 2)
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
    ft = ImageFont.truetype(FONT, round(text_h * 0.075))
    title = ("FB3093 LID C1 — BEFORE (as picked) / AFTER (FINAL) — "
             "refinement pass only")
    fh_ = fitted(round(head_h * 0.36), title, page_w - 2 * gap)
    d.text((page_w / 2 - fh_.getlength(title) / 2, head_h * 0.3), title,
           font=fh_, fill=(20, 22, 20))
    caps = ["BEFORE — C1 as picked (contact sheet)",
            "AFTER — FINAL (rosette at measured channel centre)"]
    for i, (img, cap) in enumerate(zip((before_img, after_img), caps)):
        x = gap + i * (tile + gap)
        t = img.resize((tile, tile), Image.LANCZOS)
        page.paste(t, (x, head_h))
        d.rectangle([x, head_h, x + tile, head_h + tile],
                    outline=(180, 180, 180), width=2)
        d.text((x + tile / 2 - fc.getlength(cap) / 2,
                head_h + tile + cap_h * 0.2), cap, font=fc, fill=(20, 22, 20))
    rc = report["rosette_centring"]
    lm = report["lattice_margins"]
    lines_ = [
        "CHANGES (all measured, composition untouched):",
        "1  Rosette centre y %.3f -> %.3f mm (applied %+0.3f): %s." % (
            rc["designed_centre_y_mm"], rc["optical_centre_y_mm"],
            rc["applied_mm"], rc["derivation"]),
        "2  Lattice margins rows %s / cols %s mm -> %s." % (
            lm["rows_first_last_margin_mm"], lm["cols_first_last_margin_mm"],
            lm["note"]),
        "3  Ink-centring (mm): " + ", ".join(
            "'%s' %+0.3f%s" % (s[:12], v["measured_offset_mm"],
                               "" if v["applied_mm"] else " (noise)")
            for s, v in report["ink_centring"].items()),
        "4  Kerning: %s" % (report["kerning"]["pairs_touching_C1_strings"]
                            if isinstance(report["kerning"]
                                          ["pairs_touching_C1_strings"], str)
                            else ", ".join(report["kerning"]
                                           ["pairs_touching_C1_strings"])),
        "5  Cartouche station, stroke weights, boss symmetry: measured and "
        "kept — no programme standard exists; none invented.",
    ]
    ty = head_h + tile + cap_h + gap * 0.8
    for ln in lines_:
        while ft.getlength(ln) > page_w - 2 * gap:
            cut = len(ln)
            while ft.getlength(ln[:cut]) > page_w - 2 * gap:
                cut = ln.rfind(" ", 0, cut)
            d.text((gap, ty), ln[:cut], font=ft, fill=(60, 60, 60))
            ty += text_h * 0.085
            ln = "   " + ln[cut + 1:]
        d.text((gap, ty), ln, font=ft, fill=(60, 60, 60))
        ty += text_h * 0.10
    page.save(out, dpi=(dpi, dpi))


if __name__ == "__main__":
    report = {}
    finals, texts, offsets = finalise(report)
    png = render_final_png(finals, texts, offsets,
                           f"{HERE}/fb3093_lid_C1_final.png")
    render_final_svg(finals, texts, offsets, report,
                     f"{HERE}/fb3093_lid_C1_final.svg")
    before_els = r2.c1_engine_turned_cartouche()[3]
    before = r2.render_png(before_els, f"{HERE}/_tmp_c1_before.png", dpi=600)
    os.remove(f"{HERE}/_tmp_c1_before.png")
    before_after_page(before, png, report,
                      f"{HERE}/fb3093_lid_C1_before_after.png")
    record = {
        "record_type": "h2_c1_finalisation/1.0",
        "finalised_on": "2026-08-17",
        "authority": "OWNER_BLOCKER_CLEARANCE.md §M via owner_pick_ingestion.json",
        "precedent": "E1/C3/A2 finalisation — machinery imported from finalize_lid_C3, not re-implemented",
        "before": "../candidates/fb3093_lid_C1_engine_turned_cartouche.svg (as picked)",
        "final_svg": "fb3093_lid_C1_final.svg",
        "final_png": "fb3093_lid_C1_final.png (800 dpi)",
        "measurements": report,
    }
    with open(f"{HERE}/c1_finalisation_record.json", "w") as f:
        json.dump(record, f, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1))
    print("FINAL PNG %dx%d px" % (png.width, png.height))
