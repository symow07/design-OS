#!/usr/bin/env python3
"""Read-only proof of concept: ECMA A20.20.01.01 straight-tuck-end dieline
as a standalone SVG (no Rhino, no artwork, no BBROSE integration).

Geometry formulas adapted from DDR68/Rhino_Packaging_Toolkit
(packaging/ECMA_A20_20_01_01.py), MIT License, Copyright (c) 2026 DDR68.
https://github.com/DDR68/Rhino_Packaging_Toolkit

Adaptation: Rhino document objects replaced by SVG path emission; the
interactive prompt replaced by fixed research inputs; quadratic NURBS
tuck shoulders emitted as SVG quadratic Beziers (mathematically identical
for degree-2, 3-control-point curves); panel labels added.

Research inputs (Pacdora reference, task-50):
    inner 90 x 32 x 92 mm, board 0.5 mm
    -> external L/P/A = inner + 2*S  (91.0 x 33.0 x 93.0)
    -> body height between main creases = A - 2S = 92.0 (inner height)

NOT a parity claim: the reference-exact flap shapes, slits and bleed can
only be validated against the actual customer vector file (see
apps/dielines/services/customer_dieline.py registration gate).
"""
import io

# --- internal parameters (DDR68 defaults, mm) -------------------------
INC = 18.0        # glue-flap width
GANC = 18.0       # tuck hook length
CHAMF = 3.0       # corner chamfer on dust flaps / glue flap
TAPER = 2.0       # inner-edge taper on dust flaps
FESSURA_L = 7.0   # slit-lock width
FESSURA_P = 2.5   # slit-lock depth
NURBS_K = 0.635   # tuck shoulder control-point factor

# --- research inputs ---------------------------------------------------
INNER_W, INNER_D, INNER_H = 90.0, 32.0, 92.0
S = 0.5
L, P, A = INNER_W + 2 * S, INNER_D + 2 * S, INNER_H + 2 * S


def build(L=L, P=P, A=A, S=S):
    assert P >= INC + 3, "glue flap would overlap the side-panel fold"
    assert A > 2 * S

    cut, crease, labels = [], [], []

    def line(a, b, kind):
        (cut if kind == "T" else crease).append(
            f"M {a[0]:.3f} {a[1]:.3f} L {b[0]:.3f} {b[1]:.3f}")

    def qbez(p0, ctrl, p2):
        cut.append(f"M {p0[0]:.3f} {p0[1]:.3f} "
                   f"Q {ctrl[0]:.3f} {ctrl[1]:.3f} {p2[0]:.3f} {p2[1]:.3f}")

    body_h = A - 2 * S
    orecchio = 2 * S                     # slit-lock ear

    # panel boundaries: glue | P1(L-S) | P2(P-S) | [S relief] | P3(L) | P4(P-S)
    x0 = 0.0
    x1 = INC
    x2 = x1 + L - S
    x3 = x2 + P - S
    x3b = x3 + S
    x4 = x3b + L
    x5 = x4 + P - S

    y_bot, y_top = 0.0, body_h
    y_bot_t, y_top_t = y_bot - S, y_top + S          # P1 compensated creases
    y_inc_bot, y_inc_top = y_bot + S, y_top - S      # glue flap shortened

    dust_d = min((P + GANC - S) / 2.0, L / 2.0)
    tab_b_y, tab_t_y = y_bot - dust_d, y_top + dust_d

    tuck_b_ear = y_bot_t - P
    tuck_b_fold = tuck_b_ear + orecchio
    tuck_b_tip = tuck_b_fold - GANC
    tuck_t_ear = y_top_t + P
    tuck_t_fold = tuck_t_ear - orecchio
    tuck_t_tip = tuck_t_fold + GANC
    tuck_xl, tuck_xr = x1 - S, x2

    crd_off = S * 2 * S / (2 * S + TAPER)
    crd_x = x1 - crd_off

    # 1. vertical creases
    line((x1, y_inc_bot), (x1, y_inc_top), "C")
    line((x3, y_bot), (x2, y_bot), "C")
    line((x2, y_bot), (x2, y_top), "C")
    line((x2, y_top), (x3, y_top), "C")
    line((x3b, y_bot), (x3b, y_top), "C")
    line((x4, y_bot), (x4, y_top), "C")
    # 2/3. horizontal creases (bottom, top)
    line((x5, y_bot), (x4 + S, y_bot), "C")
    line((crd_x, y_bot_t), (x2, y_bot_t), "C")
    line((tuck_xl + FESSURA_L, tuck_b_fold), (tuck_xr - FESSURA_L, tuck_b_fold), "C")
    line((x5, y_top), (x4 + S, y_top), "C")
    line((crd_x, y_top_t), (x2, y_top_t), "C")
    line((tuck_xl + FESSURA_L, tuck_t_fold), (tuck_xr - FESSURA_L, tuck_t_fold), "C")
    # 4. body edge cuts
    line((x3b, y_bot), (x4, y_bot), "T")
    line((x3b, y_top), (x4, y_top), "T")
    line((x5, y_bot), (x5, y_top), "T")
    # 5/6. relief cuts
    line((x3, y_bot), (x3b, y_bot), "T")
    line((x4, y_bot), (x4 + S, y_bot), "T")
    line((x2, y_bot_t), (x2, y_bot), "T")
    line((x3, y_top), (x3b, y_top), "T")
    line((x4, y_top), (x4 + S, y_top), "T")
    line((x2, y_top), (x2, y_top_t), "T")
    # 7. glue-flap cuts
    line((x1, y_inc_bot), (x0, y_inc_bot + CHAMF), "T")
    line((x0, y_inc_bot + CHAMF), (x0, y_inc_top - CHAMF), "T")
    line((x0, y_inc_top - CHAMF), (x1, y_inc_top), "T")
    # 8. glue-flap to tuck diagonals
    line((x1, y_inc_bot), (tuck_xl, y_bot_t - TAPER), "T")
    line((x1, y_inc_top), (tuck_xl, y_top_t + TAPER), "T")
    # 9-12. dust flaps (P2/P4, bottom+top)
    for (xi, xo, ybase, ytab, sgn) in (
            (x3, x2, y_bot, tab_b_y, -1), (x4 + S, x5, y_bot, tab_b_y, -1),
            (x3, x2, y_top, tab_t_y, +1), (x4 + S, x5, y_top, tab_t_y, +1)):
        outer_first = xo < xi
        if outer_first:   # P2: outer edge at x2 (left), inner at x3 (right)
            line((xo, ybase), (xo + CHAMF, ybase + sgn * CHAMF), "T")
            line((xo + CHAMF, ybase + sgn * CHAMF), (xo + CHAMF, ytab), "T")
            line((xi, ybase), (xi, ybase + sgn * (CHAMF + TAPER)), "T")
            line((xi, ybase + sgn * (CHAMF + TAPER)),
                 (xi - CHAMF, ybase + sgn * (2 * CHAMF + TAPER)), "T")
            line((xi - CHAMF, ybase + sgn * (2 * CHAMF + TAPER)),
                 (xi - CHAMF - TAPER, ytab), "T")
            line((xo + CHAMF, ytab), (xi - CHAMF - TAPER, ytab), "T")
        else:             # P4: inner edge at x4+S (left), outer at x5 (right)
            line((xi, ybase), (xi, ybase + sgn * (CHAMF + TAPER)), "T")
            line((xi, ybase + sgn * (CHAMF + TAPER)),
                 (xi + CHAMF, ybase + sgn * (2 * CHAMF + TAPER)), "T")
            line((xi + CHAMF, ybase + sgn * (2 * CHAMF + TAPER)),
                 (xi + CHAMF + TAPER, ytab), "T")
            line((xo, ybase), (xo - CHAMF + S, ybase + sgn * CHAMF), "T")
            line((xo - CHAMF + S, ybase + sgn * CHAMF), (xo - CHAMF + S, ytab), "T")
            line((xi + CHAMF + TAPER, ytab), (xo - CHAMF + S, ytab), "T")
    # 13/14. tuck flaps (from P1, bottom+top)
    for (edge_off, ear, fold, tip, sgn) in (
            (y_bot_t, tuck_b_ear, tuck_b_fold, tuck_b_tip, -1),
            (y_top_t, tuck_t_ear, tuck_t_fold, tuck_t_tip, +1)):
        line((tuck_xl, edge_off + sgn * TAPER), (tuck_xl, ear), "T")
        line((tuck_xr, edge_off), (tuck_xr, ear), "T")
        line((tuck_xl, ear), (tuck_xl + FESSURA_L, ear), "T")
        line((tuck_xl + FESSURA_L, ear), (tuck_xl + FESSURA_L, ear - sgn * FESSURA_P), "T")
        line((tuck_xr, ear), (tuck_xr - FESSURA_L, ear), "T")
        line((tuck_xr - FESSURA_L, ear), (tuck_xr - FESSURA_L, ear - sgn * FESSURA_P), "T")
        tip_l = tuck_xl + FESSURA_L + orecchio
        tip_r = tuck_xr - FESSURA_L - orecchio
        line((tip_l, tip), (tip_r, tip), "T")
        ctrl_y = ear + (tip - ear) * NURBS_K
        qbez((tuck_xl, ear), (tuck_xl, ctrl_y), (tip_l, tip))
        qbez((tuck_xr, ear), (tuck_xr, ctrl_y), (tip_r, tip))

    for (cx, text) in ((x1 + (L - S) / 2, "MAIN P1"), (x2 + (P - S) / 2, "SIDE P2"),
                       (x3b + L / 2, "MAIN P3"), (x4 + (P - S) / 2, "SIDE P4"),
                       (INC / 2, "GLUE")):
        labels.append((cx, body_h / 2, text))
    labels.append((x1 + (L - S) / 2, tuck_t_fold + GANC / 2, "TUCK TOP"))
    labels.append((x1 + (L - S) / 2, tuck_b_fold - GANC / 2, "TUCK BOTTOM"))

    stats = dict(panels=[INC, L - S, P - S, S, L, P - S], body_h=body_h,
                 flat=(x5, tuck_t_tip - tuck_b_tip), dust_d=dust_d)
    return cut, crease, labels, stats


def to_svg(cut, crease, labels, stats, margin=12.0):
    w = stats["flat"][0]
    ys = [float(seg.split()[i]) for seg in cut + crease
          for i in (2, 5) if len(seg.split()) > i]
    y_lo, y_hi = min(ys) - margin, max(ys) + margin
    width, height = w + 2 * margin, y_hi - y_lo
    out = io.StringIO()
    out.write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" '
        f'height="{height}mm" viewBox="{-margin} {y_lo} {width} {height}">\n'
        '<g transform="scale(1,-1) translate(0,%.3f)">\n' % (-(y_lo + y_hi)))
    out.write('<g id="DIELINE_CUT" fill="none" stroke="#0000FF" stroke-width="0.3">\n')
    for d in cut:
        out.write(f'  <path d="{d}"/>\n')
    out.write('</g>\n<g id="DIELINE_CREASE" fill="none" stroke="#FF0000" '
              'stroke-width="0.3" stroke-dasharray="3,1.5">\n')
    for d in crease:
        out.write(f'  <path d="{d}"/>\n')
    out.write('</g>\n<g id="PANEL_LABELS" font-family="Helvetica" font-size="4" '
              'fill="#888888" text-anchor="middle">\n')
    for (x, y, text) in labels:
        out.write(f'  <text x="{x:.1f}" y="{-y:.1f}" transform="scale(1,-1)">{text}</text>\n')
    out.write('</g>\n</g>\n</svg>\n')
    return out.getvalue()


if __name__ == "__main__":
    import sys
    cut, crease, labels, stats = build()
    svg = to_svg(cut, crease, labels, stats)
    path = sys.argv[1] if len(sys.argv) > 1 else "ste_90x32x92_t05.svg"
    with open(path, "w") as fh:
        fh.write(svg)
    print(f"external L/P/A: {L} x {P} x {A}  (inner {INNER_W} x {INNER_D} x {INNER_H}, S={S})")
    print(f"body height between creases: {stats['body_h']} mm")
    print("panel widths (glue|P1|P2|relief|P3|P4):",
          " | ".join(f"{p:g}" for p in stats["panels"]))
    print(f"flat size: {stats['flat'][0]:.1f} x {stats['flat'][1]:.1f} mm")
    print(f"dust flap depth: {stats['dust_d']:.2f} mm")
    print(f"cut paths: {len(cut)}, crease paths: {len(crease)} -> {path}")
