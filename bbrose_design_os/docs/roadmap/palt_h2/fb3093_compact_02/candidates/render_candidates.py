"""H2 request fb3093_compact_02 — ROUND 2 under the §L COMPLEXITY MANDATE.

Owner verdict on round 1, verbatim: "all of them look too simple and can be
done easily, i need more complexity, and more creativity." Every candidate
here must clear the recorded COMPLEXITY BAR: >=2 interacting pattern
systems, path counts an order of magnitude above round 1, and depth
(foreground ornament over a patterned ground). Element counts are measured
and written into the register — claimed complexity is checked, not asserted.

Construction rules carried from round 1 unchanged: brief-parametric frame
(72x72 PRIOR), recorded brand colours/typeface, live text, two-ink
discipline (all 'tone' from hairline weight, overlap interference, and dot
density), established words only, deterministic geometry (pure math + fixed
seeds) so calipers re-flow every candidate by re-run. Techniques were
LEARNED from the round-2 ledger; every drawing is original.
"""
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, "..", "..", "fb3093_compact_01", "candidates")))
import render_candidates as r1  # noqa: E402 — round-1 machinery + same brief

FW, FH = r1.FW, r1.FH
P621, P627, BLACK = r1.P621, r1.P627, r1.BLACK
FONT, FAMILY = r1.FONT, r1.FAMILY
WORDS = r1.WORDS
TAU = 2 * math.pi

# local element additions: ("polyfill", pts, rgb) — filled polygon plate


def _ellipse_pts(cx, cy, a, b, n=120, rot=0.0):
    pts = []
    for i in range(n):
        th = TAU * i / n
        x, y = a * math.cos(th), b * math.sin(th)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot),
                    cy + x * math.sin(rot) + y * math.cos(rot)))
    return pts


def _ring(cx, cy, base, depth, lobes, phase, n=240):
    pts = []
    for i in range(n):
        th = TAU * i / n
        r = base * (1.0 + depth * math.cos(lobes * th + phase))
        pts.append((cx + r * math.cos(th), cy + r * math.sin(th)))
    return pts


def _rosette(els, cx, cy, r0, r1, nrings, lobes, wmm=0.07, depth=0.10):
    """Engine-turned rosette the way the accepted A2 reads: every ring the
    SAME lobe count, alternate rings phase-shifted a half-lobe so adjacent
    rings weave. The first build stacked three different lobe counts at
    once and the focal point collapsed into a spiky tangle — the §L
    self-check caught it; this is the fix, not the first idea."""
    for k in range(nrings):
        base = r0 + (r1 - r0) * k / max(1, nrings - 1)
        phase = (math.pi / lobes) * (k % 2)
        els.append(("poly", _ring(cx, cy, base, depth, lobes, phase, 280),
                    True, P627, wmm))
    els.append(("poly", _ellipse_pts(cx, cy, r1 * (1 + depth) * 1.02,
                                     r1 * (1 + depth) * 1.02, 160),
                True, P627, wmm * 1.6))


# ---------------------------------------------------------------- C1
def c1_engine_turned_cartouche():
    """Two orthogonal engine-turned wave lattices interfere across the full
    lid (barleycorn read); an oval cartouche plate floats above carrying a
    dense hypotrochoid rosette and the word stack; four corner bosses."""
    els = [("ground", P621)]
    lam, amp, step = 6.0, 0.34, 0.85
    y0 = 1.2
    while y0 < FH - 1.0:
        pts = [(x * 0.4, y0 + amp * math.sin(TAU * (x * 0.4) / lam + y0 * 0.95))
               for x in range(int(FW / 0.4) + 1)]
        els.append(("poly", pts, False, P627, 0.05))
        y0 += step
    x0 = 1.2
    while x0 < FW - 1.0:
        pts = [(x0 + amp * math.sin(TAU * (y * 0.4) / lam + x0 * 0.95), y * 0.4)
               for y in range(int(FH / 0.4) + 1)]
        els.append(("poly", pts, False, P627, 0.05))
        x0 += step
    # cartouche plate over the field
    ccx, ccy = FW / 2, 0.455 * FH
    els.append(("polyfill", _ellipse_pts(ccx, ccy, 0.335 * FW, 0.235 * FH), P621))
    els.append(("poly", _ellipse_pts(ccx, ccy, 0.335 * FW, 0.235 * FH), True, P627, 0.30))
    els.append(("poly", _ellipse_pts(ccx, ccy, 0.318 * FW, 0.218 * FH), True, P627, 0.10))
    # rosette inside the cartouche (A2-grammar interleave, legible weave)
    _rosette(els, ccx, ccy - 0.062 * FH, 0.026 * FW, 0.088 * FW, 9, 12)
    # corner bosses
    for bx, by in [(0.09 * FW, 0.09 * FH), (0.91 * FW, 0.09 * FH),
                   (0.09 * FW, 0.91 * FH), (0.91 * FW, 0.91 * FH)]:
        els.append(("polyfill", _ellipse_pts(bx, by, 0.052 * FW, 0.052 * FH), P621))
        _rosette(els, bx, by, 0.010 * FW, 0.036 * FW, 5, 8, depth=0.12)
    els += [
        ("text", WORDS["brand"], "centre", ccx, ccy + 0.075 * FH,
         0.050 * FH, 0.034 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "centre",
         ccx, ccy + 0.128 * FH, 0.019 * FH, 0.008 * FW, P627),
    ]
    return ("C1", "ENGINE-TURNED CARTOUCHE", "guilloche_cartouche", els,
            ["wave lattice x2 orthogonal (interference ground)",
             "hypotrochoid rosette (14 interleaved rings)",
             "cartouche + corner bosses (depth plates)"])


# ---------------------------------------------------------------- C2
def c2_phyllotaxis_b():
    """A Vogel phyllotaxis spiral of thousands of dots covers the lid; dot
    size is modulated by the ink mask of the brand's own B so the letter
    condenses out of the powder field. Second system: fine ring rules."""
    mdpi = 20
    k = mdpi / 25.4 * 10
    mask = Image.new("L", (int(FW * 4), int(FH * 4)), 0)
    md = ImageDraw.Draw(mask)
    f = ImageFont.truetype(FONT, int(0.62 * FH * 4))
    md.text((int(FW * 4 / 2), int(0.44 * FH * 4)), "B", font=f, fill=255,
            anchor="mm")
    mpx = mask.load()
    els = [("ground", P621)]
    cx, cy = FW / 2, 0.44 * FH
    n_dots = 0
    for n in range(1, 6200):
        r = 0.475 * math.sqrt(n)
        th = n * 2.399963229728653
        x = cx + r * math.cos(th)
        y = cy + r * math.sin(th)
        if not (1.8 <= x <= FW - 1.8 and 1.8 <= y <= 0.80 * FH):
            continue
        inside = mpx[int(x * 4), int(y * 4)] > 127
        d = math.hypot(x - cx, y - cy)
        base = 0.205 if inside else 0.088
        fade = max(0.45, 1.0 - (d / (0.62 * FW)) ** 2)
        els.append(("disc", x, y, base * fade + (0.02 if inside else 0.0), P627))
        n_dots += 1
    els.append(("rect", 0.025 * FW, 0.025 * FH, 0.95 * FW, 0.95 * FH, P627, 0.10))
    els.append(("rect", 0.045 * FW, 0.045 * FH, 0.91 * FW, 0.91 * FH, P627, 0.05))
    els.append(("line", 0.28 * FW, 0.845 * FH, 0.72 * FW, 0.845 * FH, P627, 0.10))
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.905 * FH,
         0.046 * FH, 0.030 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "centre",
         FW / 2, 0.955 * FH, 0.018 * FH, 0.008 * FW, P627),
    ]
    return ("C2", "PHYLLOTAXIS B", "phyllotaxis_glyph_carving", els,
            ["Vogel spiral field (%d placed dots)" % n_dots,
             "glyph-mask density carving (the B emerges from dot size)",
             "double rule frame + title rule"])


# ---------------------------------------------------------------- C3
def _braid_edge(els, p0, p1, amp, period, w_half, gap_half):
    """Two-strand braid along p0->p1 with true over-under: each strand is a
    sine ribbon drawn as its two edge hairlines; at each crossing the under
    strand breaks, alternating which strand goes under."""
    ux, uy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(ux, uy)
    ux, uy = ux / L, uy / L
    vx, vy = -uy, ux
    period = L / max(2, round(L / period))  # integer periods — no mid-phase end
    step = 0.3
    for strand, phase in ((0, 0.0), (1, math.pi)):
        crossings = [k * period / 2 for k in range(int(L / (period / 2)) + 2)]
        def under(s):
            for ki, sc in enumerate(crossings):
                if abs(s - sc) < gap_half and (ki % 2) == strand:
                    return True
            return False
        for side in (-1, 1):
            run = []
            s = 0.0
            while s <= L:
                if under(s):
                    if len(run) > 1:
                        els.append(("poly", run, False, P627, 0.10))
                    run = []
                else:
                    off = amp * math.sin(TAU * s / period + phase)
                    dyds = amp * TAU / period * math.cos(TAU * s / period + phase)
                    nl = math.hypot(1.0, dyds)
                    nx = (vx - dyds * ux) / nl
                    ny = (vy - dyds * uy) / nl
                    run.append((p0[0] + ux * s + vx * off + nx * side * w_half,
                                p0[1] + uy * s + vy * off + ny * side * w_half))
                s += step
            if len(run) > 1:
                els.append(("poly", run, False, P627, 0.10))


def c3_strapwork_moire():
    """A woven two-strand strapwork braid runs the perimeter between corner
    bosses (over-under crossings drawn honestly); the centre carries a moiré
    medallion — two offset fine ring systems interfering on a plate."""
    els = [("ground", P621)]
    m = 0.118 * FW
    boss_r = 0.055 * FW
    inset = boss_r + 0.02 * FW
    corners = [(m, m), (FW - m, m), (FW - m, FH - m), (m, FH - m)]
    edges = [((m + inset, m), (FW - m - inset, m)),
             ((FW - m, m + inset), (FW - m, FH - m - inset)),
             ((FW - m - inset, FH - m), (m + inset, FH - m)),
             ((m, FH - m - inset), (m, m + inset))]
    for p0, p1 in edges:
        _braid_edge(els, p0, p1, 0.026 * FW, 0.13 * FW, 0.012 * FW, 0.011 * FW)
    for bx, by in corners:
        els.append(("polyfill", _ellipse_pts(bx, by, boss_r, boss_r), P621))
        _rosette(els, bx, by, 0.011 * FW, 0.040 * FW, 5, 10, depth=0.11)
    # medallion: TRUE moiré — two identical ray fans, one rotated a hair
    # (the first build overlaid offset ring systems at too-fine pitch and
    # rendered as a solid ring disc; the self-check killed it)
    mcx, mcy = FW / 2, 0.435 * FH
    plate_r = 0.235 * FW
    els.append(("polyfill", _ellipse_pts(mcx, mcy, plate_r, plate_r), P621))
    els.append(("poly", _ellipse_pts(mcx, mcy, plate_r, plate_r), True, P627, 0.25))
    # true moiré: two fans with DIFFERENT ray counts — |96-102| = 6 beat
    # lobes (the equal-count 2.4°-offset fan just doubled the rays)
    r_in, r_out = 0.042 * FW, plate_r - 0.014 * FW
    for n_rays in (96, 102):
        for i in range(n_rays):
            th = TAU * i / n_rays
            els.append(("line", mcx + r_in * math.cos(th),
                        mcy + r_in * math.sin(th),
                        mcx + r_out * math.cos(th),
                        mcy + r_out * math.sin(th), P627, 0.07))
    _rosette(els, mcx, mcy, 0.012 * FW, 0.034 * FW, 4, 8, depth=0.13)
    els.append(("poly", _ellipse_pts(mcx, mcy, r_out, r_out, 160),
                True, P627, 0.12))
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.755 * FH,
         0.044 * FH, 0.028 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "centre",
         FW / 2, 0.805 * FH, 0.0175 * FH, 0.007 * FW, P627),
    ]
    return ("C3", "STRAPWORK MOIRE", "strapwork_interlace_moire", els,
            ["two-strand braid border, honest over-under breaks",
             "moiré medallion (two offset ring systems, 52 rings)",
             "corner bosses + plate depth"])


# ---------------------------------------------------------------- C4
def c4_security_lattice():
    """Banknote grammar: a checkerboard lattice of small hypotrochoid
    rosettes; a large interleaved multi-ring rosette on a central plate;
    micro-dashed double border. Three systems deep."""
    els = [("ground", P621)]
    pitch = 0.152 * FW
    for gy in range(6):
        for gx in range(6):
            x = 0.12 * FW + gx * pitch
            y = 0.12 * FH + gy * pitch
            if y > 0.80 * FH:
                continue
            if math.hypot(x - FW / 2, y - 0.42 * FH) < 0.24 * FW:
                continue
            a, b = ((8, 0.30), (6, 0.24)) if (gx + gy) % 2 == 0 else ((12, 0.22), (5, 0.30))
            els.append(("poly", _ring(x, y, 0.030 * FW, a[1], a[0], 0.0, 160),
                        True, P627, 0.08))
            els.append(("poly", _ring(x, y, 0.017 * FW, b[1], b[0], 0.6, 120),
                        True, P627, 0.08))
            els.append(("disc", x, y, 0.10, P627))
    ccx, ccy = FW / 2, 0.42 * FH
    els.append(("polyfill", _ellipse_pts(ccx, ccy, 0.225 * FW, 0.225 * FW), P621))
    els.append(("poly", _ellipse_pts(ccx, ccy, 0.225 * FW, 0.225 * FW), True, P627, 0.22))
    _rosette(els, ccx, ccy, 0.024 * FW, 0.180 * FW, 14, 14, wmm=0.065, depth=0.105)
    for inset, wmm in ((0.030, 0.16), (0.048, 0.06)):
        els.append(("rect", inset * FW, inset * FH,
                    FW * (1 - 2 * inset), FH * (1 - 2 * inset), P627, wmm))
    dash, gapd = 0.014 * FW, 0.010 * FW
    d_in = 0.060 * FH
    x = 0.07 * FW
    while x < 0.93 * FW - dash:
        els.append(("line", x, d_in, x + dash, d_in, P627, 0.10))
        els.append(("line", x, FH - d_in, x + dash, FH - d_in, P627, 0.10))
        els.append(("line", d_in, x, d_in, x + dash, P627, 0.10))
        els.append(("line", FW - d_in, x, FW - d_in, x + dash, P627, 0.10))
        x += dash + gapd
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.880 * FH,
         0.048 * FH, 0.032 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "centre",
         FW / 2, 0.932 * FH, 0.018 * FH, 0.008 * FW, P627),
    ]
    return ("C4", "SECURITY LATTICE", "security_rosette_lattice", els,
            ["checkerboard hypotrochoid lattice (two alternating param sets)",
             "central interleaved multi-ring rosette (up to 18 rings)",
             "double border + micro-dash rules"])


# ---------------------------------------------------------------- C5
def _square_pts(cx, cy, half, rot):
    pts = []
    for i in range(4):
        th = rot + math.pi / 2 * i
        pts.append((cx + half * math.sqrt(2) * math.cos(th + math.pi / 4),
                    cy + half * math.sqrt(2) * math.sin(th + math.pi / 4)))
    return pts


def _seg_int(p, q, a, b):
    dx1, dy1 = q[0] - p[0], q[1] - p[1]
    dx2, dy2 = b[0] - a[0], b[1] - a[1]
    den = dx1 * dy2 - dy1 * dx2
    if abs(den) < 1e-12:
        return None
    t = ((a[0] - p[0]) * dy2 - (a[1] - p[1]) * dx2) / den
    u = ((a[0] - p[0]) * dy1 - (a[1] - p[1]) * dx1) / den
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None


def _interlaced_squares(els, cx, cy, half, wmm, gap):
    """TRUE khatam interlace: both full squares drawn, breaks computed AT
    the 8 crossings with alternating parity per strand (Kaplan's
    consistency rule, ledger e19). The first build emitted only mid-side
    fragments of the rotated square — its corners vanished and the stars
    read as boxes with tick-marks; the §L self-check killed it."""
    sqA = _square_pts(cx, cy, half, 0.0)
    sqB = _square_pts(cx, cy, half, math.pi / 4)

    def crossings(sq, other):
        out = []
        for i in range(4):
            p, q = sq[i], sq[(i + 1) % 4]
            for j in range(4):
                t = _seg_int(p, q, other[j], other[(j + 1) % 4])
                if t is not None:
                    out.append((i, t))
        out.sort()
        return out

    for sq, other, parity in ((sqA, sqB, 0), (sqB, sqA, 1)):
        cr = crossings(sq, other)
        L = math.hypot(sq[1][0] - sq[0][0], sq[1][1] - sq[0][1])
        gt = gap / L
        for i in range(4):
            p, q = sq[i], sq[(i + 1) % 4]
            gaps = sorted((t - gt, t + gt)
                          for k, (si, t) in enumerate(cr)
                          if si == i and k % 2 == parity)
            runs, t0 = [], 0.0
            for g0, g1 in gaps:
                if g0 > t0:
                    runs.append((t0, g0))
                t0 = max(t0, g1)
            if t0 < 1.0:
                runs.append((t0, 1.0))
            for r0_, r1_ in runs:
                els.append(("poly", [(p[0] + (q[0] - p[0]) * t,
                                      p[1] + (q[1] - p[1]) * t)
                                     for t in (r0_, r1_)], False, P627, wmm))


def c5_girih_field():
    """A 4x3 girih star lattice (interlaced two-square khatam stars with
    inset 8-petal rosettes and connector diamonds) over the upper lid; rule
    + formal stack below. Interlace breaks are drawn, not implied."""
    els = [("ground", P621)]
    pitch = 0.222 * FW
    x0, y0 = 0.168 * FW, 0.148 * FH
    for gy in range(3):
        for gx in range(4):
            cx = x0 + gx * pitch
            cy = y0 + gy * pitch * 0.92
            # outer half must keep the rotated diagonal inside the cell:
            # 0.070·FW·√2 = 7.1mm < pitch/2 = 8.0mm (the 0.082 build
            # collided with neighbours and the field read as noise)
            _interlaced_squares(els, cx, cy, 0.070 * FW, 0.16, 0.012 * FW)
            _interlaced_squares(els, cx, cy, 0.058 * FW, 0.06, 0.010 * FW)
            _interlaced_squares(els, cx, cy, 0.040 * FW, 0.08, 0.008 * FW)
            els.append(("poly", _ring(cx, cy, 0.022 * FW, 0.38, 8, 0.0, 120),
                        True, P627, 0.08))
            els.append(("disc", cx, cy, 0.12, P627))
    for gy in range(2):
        for gx in range(3):
            dx = x0 + (gx + 0.5) * pitch
            dy = y0 + (gy + 0.5) * pitch * 0.92
            els.append(("poly", _square_pts(dx, dy, 0.030 * FW, math.pi / 4),
                        True, P627, 0.10))
            els.append(("poly", _square_pts(dx, dy, 0.019 * FW, math.pi / 4),
                        True, P627, 0.06))
    els.append(("line", 0.24 * FW, 0.795 * FH, 0.76 * FW, 0.795 * FH, P627, 0.12))
    els += [
        ("text", WORDS["brand"], "centre", FW / 2, 0.868 * FH,
         0.048 * FH, 0.032 * FW, P627),
        ("text", "%s · %s" % (WORDS["en"], WORDS["es"]), "centre",
         FW / 2, 0.920 * FH, 0.018 * FH, 0.008 * FW, P627),
    ]
    return ("C5", "GIRIH FIELD", "girih_interlace", els,
            ["interlaced two-square khatam stars (double-weight, broken under-passes)",
             "inset 8-petal rosettes + centre dots",
             "connector diamond lattice + rule"])


CANDIDATES = [c1_engine_turned_cartouche, c2_phyllotaxis_b,
              c3_strapwork_moire, c4_security_lattice, c5_girih_field]


# ---- rendering: reuse round-1 PNG machinery, extend for polyfill --------

def render_png(elements, out, dpi=600):
    k = dpi / 25.4
    img = Image.new("RGB", (round(FW * k), round(FH * k)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for e in elements:
        if e[0] == "polyfill":
            d.polygon([(x * k, y * k) for x, y in e[1]], fill=e[2])
        elif e[0] == "ground":
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
        elif e[0] == "disc":
            _, cx, cy, r, rgb = e
            d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k],
                      fill=rgb)
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            f = ImageFont.truetype(FONT, round(em * k))
            tw = r1.tracked_width(f, s, tr * k)
            x_px = (x * k - tw / 2) if mode == "centre" else x * k
            r1.draw_tracked(d, f, s, x_px, yb * k, tr * k, rgb)
    d.rectangle([0, 0, img.width - 1, img.height - 1],
                outline=(200, 200, 200), width=1)
    img.save(out, dpi=(dpi, dpi))
    return img


def render_svg(cid, cname, elements, out):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
        'viewBox="0 0 %g %g">' % (FW, FH, FW, FH),
        '<!-- FB3093 lid candidate %s (%s) — H2 request fb3093_compact_02, '
        'ROUND 2 under the §L complexity mandate. ORIGINAL parametric '
        'drawing; techniques learned from inspiration_ledger.json, nothing '
        'traced. PARAMETRIC ON THE ROUND-1 BRIEF: %g x %g mm PRIOR frame '
        '(calipers supersede, artwork re-flows by re-run). Face: %s '
        '(SET_FACE, OFL). Text LIVE, never outlined. -->'
        % (cid, cname, FW, FH, FAMILY),
    ]
    for e in elements:
        if e[0] == "polyfill":
            dstr = "M " + " L ".join("%.3f %.3f" % (x, y) for x, y in e[1]) + " Z"
            lines.append('<path d="%s" fill="rgb(%d,%d,%d)"/>' % (dstr, *e[2]))
        elif e[0] == "ground":
            lines.append('<rect width="%g" height="%g" fill="rgb(%d,%d,%d)"/>'
                         % (FW, FH, *e[1]))
        elif e[0] == "rect":
            _, x, y, w, h, rgb, wmm = e
            lines.append('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" '
                         'fill="none" stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                         % (x, y, w, h, *rgb, wmm))
        elif e[0] == "line":
            _, x1, y1, x2, y2, rgb, wmm = e
            lines.append('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" '
                         'stroke="rgb(%d,%d,%d)" stroke-width="%g"/>'
                         % (x1, y1, x2, y2, *rgb, wmm))
        elif e[0] == "poly":
            _, pts, closed, rgb, wmm = e
            dstr = "M " + " L ".join("%.3f %.3f" % (x, y) for x, y in pts)
            if closed:
                dstr += " Z"
            lines.append('<path d="%s" fill="none" stroke="rgb(%d,%d,%d)" '
                         'stroke-width="%g" stroke-linecap="round" '
                         'stroke-linejoin="round"/>' % (dstr, *rgb, wmm))
        elif e[0] == "disc":
            _, cx, cy, r_, rgb = e
            lines.append('<circle cx="%.3f" cy="%.3f" r="%.3f" '
                         'fill="rgb(%d,%d,%d)"/>' % (cx, cy, r_, *rgb))
        elif e[0] == "text":
            _, s, mode, x, yb, em, tr, rgb = e
            anchor, tx = ("middle", x - tr / 2) if mode == "centre" else ("start", x)
            lines.append(
                '<text x="%g" y="%g" font-family="%s" font-size="%g" '
                'letter-spacing="%g" text-anchor="%s" fill="rgb(%d,%d,%d)">'
                '%s</text>' % (round(tx, 3), yb, FAMILY, em, tr, anchor,
                               *rgb, r1.esc(s)))
    lines.append("</svg>")
    open(out, "w").write("\n".join(lines) + "\n")


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

    title = "FB3093 — ROUND 2 UNDER THE COMPLEXITY MANDATE (§L) — C1-C5"
    fh_ = fitted(round(head_h * 0.42), title, page_w - 2 * gap)
    d.text((page_w / 2 - fh_.getlength(title) / 2, head_h * 0.30),
           title, font=fh_, fill=BLACK)
    fc = ImageFont.truetype(FONT, round(cap_h * 0.44))
    for i, (cid, cname, tech, img) in enumerate(tiles):
        r_, c = divmod(i, cols)
        x = gap + c * (tile_w + gap)
        y = head_h + gap + r_ * (tile_h + cap_h + gap)
        tile = img.resize((tile_w, tile_h), Image.LANCZOS)
        page.paste(tile, (x, y))
        d.rectangle([x, y, x + tile_w, y + tile_h],
                    outline=(180, 180, 180), width=2)
        cap = "%s — %s  [%s]" % (cid, cname, tech)
        fc_i = fitted(round(cap_h * 0.44), cap, tile_w)
        d.text((x + tile_w / 2 - fc_i.getlength(cap) / 2,
                y + tile_h + cap_h * 0.22), cap, font=fc_i, fill=BLACK)
    foot_lines = [
        "ROUND 2 — round 1 rejected under §L ('too simple'); every candidate "
        "carries >=2 interacting pattern systems, measured element counts in "
        "the register, and depth plates",
        "Frame %.2f x %.2f mm PRIOR (owner calipers supersede; re-flows by "
        "re-run)  ·  Face: %s Regular (SET_FACE, OFL)  ·  PANTONE 621 C / "
        "627 C, all tone from hairline weight and density  ·  the owner's "
        "pick is design authority" % (FW, FH, FAMILY),
    ]
    fy = page_h - foot_h * 0.92
    for fl in foot_lines:
        f_fit = fitted(round(foot_h * 0.30), fl, page_w - 2 * gap)
        d.text((page_w / 2 - f_fit.getlength(fl) / 2, fy), fl,
               font=f_fit, fill=(90, 90, 90))
        fy += foot_h * 0.40
    page.save(out, dpi=(dpi, dpi))


def complexity_stats(els):
    counts = {}
    pts = 0
    for e in els:
        counts[e[0]] = counts.get(e[0], 0) + 1
        if e[0] in ("poly", "polyfill"):
            pts += len(e[1])
    return {"elements": sum(counts.values()), "by_kind": counts,
            "polyline_points": pts}


if __name__ == "__main__":
    tiles = []
    stats = {}
    for fn in CANDIDATES:
        cid, cname, direction, els, systems = fn()
        r1.assert_text_fits(cid, els)
        st = complexity_stats(els)
        st["systems"] = systems
        stats[cid] = st
        slug = "%s_%s" % (cid, cname.lower().replace(" ", "_").replace("-", "_"))
        img = render_png(els, f"{HERE}/fb3093_lid_{slug}.png")
        render_svg(cid, cname, els, f"{HERE}/fb3093_lid_{slug}.svg")
        tiles.append((cid, cname, direction, img))
        print(f"{cid} {cname}: {st['elements']} elements, "
              f"{st['polyline_points']} polyline points")
    contact_sheet(tiles, os.path.join(HERE, "..", "contact_sheet.png"))
    json.dump(stats, open(os.path.join(HERE, "complexity_stats.json"), "w"),
              indent=1)
    print("contact sheet + complexity stats written")
