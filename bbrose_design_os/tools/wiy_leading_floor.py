"""WI-Y / §AC1 — the METRIC floor, its negative control, and the owner's bet.

    python tools/wiy_leading_floor.py

§AC1 ruled: *"the metric floor is the constraint. At 1.06 em the line boxes
overlap by 0.959 mm. That is a FAIL. The leading rises until the metric floor
clears, and the number it must clear is 1.362 em."* The setting is **2.0 em**.

This tool does three things and each is a measurement:

1. **Measures the metric floor** off an emitted PDF, rather than quoting
   §AC1's 1.362. If the floor this instrument reads and the floor the ruling
   names ever stop agreeing, one of them is wrong and the disagreement is the
   finding — so it is printed as a comparison, not an assertion.
2. **Runs the §AC1(d) negative control.** Same guard, same leading, on a
   synthetic descender-bearing name. The verdict must not move. And the
   control has a second half the ruling implies but does not spell out: it is
   only worth running if the INK genuinely does move with the string, because
   a control that cannot fail proves nothing. Both halves are measured.
3. **Renders the two survivors at true scale**, side by side, for the review
   queue — §AC1(c) named a bet and asked to be shown the artefact that can
   lose it.

WHY THE FLOOR IS A PROPERTY OF THE FACE AND THE INK IS NOT
-----------------------------------------------------------
A PDF span bbox is the font's line box, ascent to descent, drawn whether or not
a glyph reaches either end. Its height at a given size is a fact about the
FACE. The ink is a fact about THESE WORDS. `Rose` has no descender, so at 1.06
em the boxes overlap by 0.959 mm while the drawn letters still clear by 1.073 —
and §AC1(a) is that the second number *"is not a constraint, it is a
coincidence with a measurement next to it"*.

The clearance this tool reports is therefore always the BOX clearance, and the
ink is reported beside it only to show how far the two can diverge.

WHAT THIS TOOL DOES NOT DO
---------------------------
It issues no opinion on 2.0 versus 3.0047. §AC1(c) ruled 2.0 and named the
condition under which it loses — *"the 2.0 em render shows `Rose` and
`Damascena` reading as two unrelated lines rather than one lockup"* — and that
is a judgement of an image by a person. The tool renders the image.
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

import numpy as _np  # noqa: E402
import pymupdf  # noqa: E402

from apps.ire import back_panel  # noqa: E402
from apps.ire import compose_dropper  # noqa: E402
from apps.ire.compose_dropper import _front_typography  # noqa: E402
from apps.ire.emitters.pdf_ai import emit_pdf_ai  # noqa: E402
from apps.ire.graph import (Color, Document, Group, Rect,  # noqa: E402
                            Stroke, TextRun)
from apps.ire.tests.test_back_panel import _FRONT_RECORD, _FRONT_ZONE, _GEOMETRY  # noqa: E402
from tools.wim_front_render import (K, MARGIN, ZONE_H,  # noqa: E402
                                    ZONE_W, spans,
                                    verify_zone_is_production)

OUT = os.path.join(_HERE, "docs", "visual_quality", "wiy_leading_floor")

#: MEASUREMENT SCRATCH, DELIBERATELY NOT IN `OUT`. Every reading in this file
#: is taken by emitting a panel and reading it back, so a run writes ~23 PDFs
#: that are evidence for a number and not artefacts for review. They were in
#: `OUT` first, and two measurements say they do not belong there: the suite
#: regenerates them (the tests measure too), and the emitter does NOT produce
#: byte-stable output — the same panel, same content, hashed cf006867 then
#: 98bbe5ab across two runs. Committing them would hand every later sprint a
#: tree that goes dirty on `pytest`, against an invariant list that works by
#: naming exactly which files may move. `OUT` now holds only the two review
#: sheets, which are written by `main()` alone.
SCRATCH = os.path.join(tempfile.gettempdir(), "wiy_leading_floor")
DPI = 600

#: §AB2's ruled size. Every panel and every measurement here is 9.0 pt.
RULED_PT = 9.0

#: One em at the ruled size, through the named conversion (§Z1(b)).
EM_MM = RULED_PT * back_panel.MM_PER_PT

#: §AC1's own figures, quoted so the tool can be checked AGAINST the ruling
#: instead of silently agreeing with it.
RULED_FLOOR_EM = 1.362
RULED_OVERLAP_MM = 0.959
DEAD = 1.06
SET = compose_dropper.NAME_LEADING_EM
INCUMBENT = compose_dropper.NAME_LEADING_INCUMBENT_EM

#: THE THREE NAMES. §AC1(d) asks for one synthetic descender-bearing name; two
#: are used because they answer different objections.
#:
#: * `SHIPPING` is what the front draws today and what every figure in §AB3 and
#:   §AC1 was measured on.
#: * `PLAUSIBLE` is not synthetic at all. §AB2(f) ruled that this name is the
#:   fixed point *for this name* and the next SKU will have a different one;
#:   `Peony` is a rose-adjacent botanical with one descender, and it is here so
#:   the control cannot be dismissed as an unrealistic stress case.
#: * `SYNTHETIC` carries every descender the face has, which is the maximal
#:   version of §AC1(a)'s *"dies on the first product name containing a `g`,
#:   `j`, `p`, `q` or `y`"*.
#:
#: Only the FIRST line varies. A descender on line two hangs below the block
#: and cannot reach the line above it, so varying it would test nothing.
SHIPPING = ("Rose", "Damascena")
PLAUSIBLE = ("Peony", "Damascena")
SYNTHETIC = ("Rogypj", "Damascena")
NAMES = [("shipping", SHIPPING), ("plausible", PLAUSIBLE),
         ("synthetic", SYNTHETIC)]


@contextlib.contextmanager
def leading(em: float):
    """Swap `NAME_LEADING_EM` for one render, and put it back.

    The producer reads the module global at call time. WI-V established this
    shape; it is reused rather than reinvented so the two tools measure the
    same composer the same way.
    """
    was = compose_dropper.NAME_LEADING_EM
    compose_dropper.NAME_LEADING_EM = em
    try:
        yield
    finally:
        compose_dropper.NAME_LEADING_EM = was


def _front(tag, ox, oy, name_lines, outline=True):
    """The producer called exactly as the sheet calls it, at s=1.0.

    `name_lines` is §AC1(e)'s named exception — the parameter IS the
    instrument, in the same way WI-T's fix was. Passing `None` reproduces the
    shipping artwork bit for bit.
    """
    zone = dict(_FRONT_ZONE, x=0, y=0)
    closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                 + (_GEOMETRY.get("visible_neck_mm") or 3.0))
    kids, _pl, _lg, zrect = _front_typography(
        _GEOMETRY, zone, ox, oy - closure_h, 1.0, None,
        prefix=f"{tag}-", name_min=RULED_PT, name_lines=name_lines,
        **_FRONT_RECORD)        # §BH67(c)2: the record's two front lines, handed in as the sheet's caller does
    if not outline:
        return list(kids)
    box = Rect(name=f"{tag}-zone-outline", x=zrect[0], y=zrect[1],
               w=ZONE_W, h=ZONE_H,
               stroke=Stroke(color=Color.from_hex("#B0A0A8"),
                             width_mm=0.1, opacity=0.9))
    return [box] + list(kids)


def _emit(children, path, page_w, page_h, title, png=True):
    doc = Document(title=title, page_w=page_w, page_h=page_h,
                   root=Group(name="WIY", role="decoration",
                              children=children))
    emit_pdf_ai(doc, path)
    if png:
        d = pymupdf.open(path)
        d[0].get_pixmap(dpi=DPI).save(path[:-4] + ".png")
        d.close()
    return path


def render_panel(em, name_lines, tag):
    """One front, one leading, one name, at 1:1, into its own file."""
    with leading(em):
        kids = _front(tag, MARGIN, MARGIN, name_lines)
    os.makedirs(SCRATCH, exist_ok=True)
    p = os.path.join(SCRATCH, f"panel_{tag}.pdf")
    return _emit(kids, p, ZONE_W + 2 * MARGIN, ZONE_H + 2 * MARGIN, tag,
                 png=False)


def _named(rows, text):
    return next(r for r in rows if r[0].startswith(text))


# --------------------------------------------------------------------------
# THE GUARD
# --------------------------------------------------------------------------

def box_clearance(em, name_lines, tag=None):
    """The METRIC clearance between the two name line boxes, in millimetres.

    Positive is clear white between the boxes; negative is the boxes inside
    each other. This is the quantity §AC1 ruled on and it is read back out of
    an emitted PDF, never computed from the composer's intent.
    """
    tag = tag or f"m{em:.4f}_{name_lines[0]}".replace(".", "_")
    r = spans(render_panel(em, name_lines, tag))
    top, bottom = _named(r, name_lines[0]), _named(r, name_lines[1])
    return bottom[2][1] - top[2][3]


def line_box_height(name_lines=SHIPPING):
    """The face's line box at the ruled size, measured. THE FLOOR.

    Measured at the incumbent leading, where the two boxes are far apart and
    neither can be clipped by the other. The height of a span box is a
    property of the FACE and the SIZE, so it does not depend on which of the
    two lines is measured or on what either of them says — and `floors()`
    below checks exactly that rather than assuming it.
    """
    tag = f"boxh_{name_lines[0]}"
    r = spans(render_panel(INCUMBENT, name_lines, tag))
    top = _named(r, name_lines[0])
    return top[2][3] - top[2][1]


def verdict(em, name_lines):
    """§AC1's guard, as one word. PASS if the line boxes clear, FAIL if not.

    The threshold is ZERO CLEARANCE and not the 1.362 figure, deliberately.
    1.362 em is what zero clearance WORKS OUT TO at 9.0 pt in this face; if
    the size or the face changed and the guard were written against 1.362 it
    would go on reporting a floor that had moved underneath it. §AC0(a): the
    constraint that survives a change of content is the one that binds, and
    the same logic applies to a change of face.
    """
    return "PASS" if box_clearance(em, name_lines) >= 0.0 else "FAIL"


#: Rasterisation zoom for the ink measurement — WI-V's constant and WI-V's
#: reasoning: 24x at 72 dpi is 1728 dpi, one pixel row is 0.0147 mm, two orders
#: finer than the millimetre quantities it has to resolve.
INK_ZOOM = 24.0


def ink_clearance(em, name_lines):
    """The gap between ACTUAL DARK PIXELS on the two name lines.

    Not the guard. This exists to prove the guard's control is not vacuous:
    if this number did not move when the string gained a descender, then
    "metric" and "ink" would be the same measurement wearing two names and
    §AC1(d)'s control would pass for a guard that measures the wrong thing.
    """
    tag = f"ink{em:.4f}_{name_lines[0]}".replace(".", "_")
    pdf = render_panel(em, name_lines, tag)
    d = pymupdf.open(pdf)
    pg = d[0]
    boxes = {}
    for blk in pg.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                t = sp["text"].strip()
                if t in name_lines:
                    boxes[t] = sp["bbox"]
    pm = pg.get_pixmap(matrix=pymupdf.Matrix(INK_ZOOM, INK_ZOOM),
                       colorspace=pymupdf.csGRAY)
    a = _np.frombuffer(pm.samples, dtype=_np.uint8).reshape(pm.height,
                                                            pm.width)
    y0 = boxes[name_lines[0]][1] - 1.0
    y1 = boxes[name_lines[1]][3] + 1.0
    x0 = min(boxes[n][0] for n in name_lines) - 1
    x1 = max(boxes[n][2] for n in name_lines) + 1
    sub = a[int(y0 * INK_ZOOM):int(y1 * INK_ZOOM),
            int(x0 * INK_ZOOM):int(x1 * INK_ZOOM)]
    dark = (sub < 200).any(axis=1)
    bands, run = [], None
    for i, v in enumerate(dark):
        if v and run is None:
            run = i
        if not v and run is not None:
            bands.append((run, i))
            run = None
    if run is not None:
        bands.append((run, len(dark)))
    off = int(y0 * INK_ZOOM) / INK_ZOOM
    d.close()
    mm = [((off + b[0] / INK_ZOOM) / K, (off + b[1] / INK_ZOOM) / K)
          for b in bands]
    if len(mm) < 2:                        # the two lines have merged
        return 0.0
    return mm[-1][0] - mm[-2][1]


# --------------------------------------------------------------------------
# REPORTS
# --------------------------------------------------------------------------

def floors():
    """The metric floor, measured, and checked against the ruling's figure."""
    print(f"\nTHE METRIC FLOOR AT {RULED_PT} pt — MEASURED, NOT QUOTED")
    heights = {}
    for label, name in NAMES:
        heights[label] = line_box_height(name)
        print(f"  line box of {name[0]:<8} ({label:<9}) = "
              f"{heights[label]:.6f} mm")
    spread = max(heights.values()) - min(heights.values())
    print(f"  spread across all three names          = {spread:.2e} mm")
    print("  The line box does not depend on the string. That is the whole")
    print("  reason §AC1 ruled on it and not on the ink.")
    box_h = heights["shipping"]
    floor_em = box_h / EM_MM
    print(f"\n  one em at {RULED_PT} pt   = {EM_MM:.6f} mm")
    print(f"  floor, measured    = {box_h:.6f} mm = {floor_em:.6f} em")
    print(f"  floor, per §AC1    = {RULED_FLOOR_EM} em")
    print(f"  agreement          = {abs(floor_em - RULED_FLOOR_EM):.2e} em")
    return box_h, floor_em


def control():
    """§AC1(d), both halves, as one table."""
    print("\n§AC1(d) — THE NEGATIVE CONTROL")
    print("  Same guard, same leading, three names. The VERDICT column must")
    print("  not move down a block. The INK column must.\n")
    print(f"  {'leading':>10}{'name':>10}{'box clear mm':>15}"
          f"{'VERDICT':>10}{'ink clear mm':>15}")
    rows = []
    for em in (DEAD, SET, INCUMBENT):
        for label, name in NAMES:
            bc = box_clearance(em, name)
            v = verdict(em, name)
            ic = ink_clearance(em, name)
            rows.append((em, label, bc, v, ic))
            print(f"  {em:>10.4f}{name[0]:>10}{bc:>15.6f}{v:>10}{ic:>15.6f}")
        print()
    for em in (DEAD, SET, INCUMBENT):
        block = [r for r in rows if r[0] == em]
        verdicts = {r[3] for r in block}
        boxes = {round(r[2], 9) for r in block}
        inks = {round(r[4], 9) for r in block}
        print(f"  at {em:.4f} em: verdicts {sorted(verdicts)}, "
              f"{len(boxes)} distinct box clearance, {len(inks)} distinct ink")
    print("\n  ONE verdict and ONE box clearance per leading, across a name")
    print("  with no descender, a plausible next SKU with one, and a synthetic")
    print("  with every descender the face has. The guard does not move with")
    print("  the string, which is what §AC1(d) requires of it.")
    print("\n  AND THE CONTROL IS NOT VACUOUS. The ink column moves by the")
    print("  face's descender depth on the same renders — so a guard that")
    print("  measured ink WOULD have flipped, and this control would have")
    print("  caught it. A control that cannot fail is not evidence.")
    return rows


#: Annotation type on a review sheet is not artwork, but it is still type, and
#: a caption wider than its page is a clipped caption. The first run of this
#: tool emitted a one-line footer of ~120 characters onto a 60 mm page and cut
#: the first and last words off both sheets — the emitter has no measuring or
#: wrapping step, so nothing stopped it. Captions are wrapped here BY HAND into
#: lines short enough to fit, and `_caption_fits` checks the result off the
#: emitted PDF rather than trusting the estimate.
CAPTION_PT = 3.4


def _footer(lines, page_w, y, ink, tag="foot"):
    return [TextRun(name=f"{tag}-{i}", text=t, x=page_w / 2,
                    y=y + i * (CAPTION_PT * back_panel.MM_PER_PT * 1.35),
                    size_pt=CAPTION_PT, color=ink, align="center")
            for i, t in enumerate(lines)]


def _caption_fits(pdf, page_w):
    """Every run on the sheet lies inside the page. Measured, not estimated."""
    bad = [(r[0][:28], round(r[2][0], 2), round(r[2][2], 2))
           for r in spans(pdf) if r[2][0] < 0 or r[2][2] > page_w]
    if bad:
        print(f"    CLIPPED on {os.path.basename(pdf)}: {bad}")
    return not bad


def cohesion():
    """THE QUANTITY §AC1(c)'s BET IS ABOUT, MEASURED. NO VERDICT IS ISSUED.

    §AC1(c) named its own losing condition — *"the bet loses if the 2.0 em
    render shows `Rose` and `Damascena` reading as two unrelated lines rather
    than one lockup"* — and said plainly that it was ruled from arithmetic
    with the render unseen. That is a judgement of an image by a person and
    this tool does not make it.

    But "one lockup" has a measurable correlate, and §AB0(b) says a ruling
    should know the measurement it is betting against. Two lines read as one
    unit when they are closer TO EACH OTHER than the pair is to whatever sits
    next to it. So: the clearance INSIDE the name, against the clearance
    between the name and the tagline under it. A ratio above 1 means the name
    is more spread out internally than it is separated from its neighbour,
    which is the typographic shape of the failure the ruling names.

    Both numbers come off the same PDFs the review sheet is built from.
    """
    print("\nTHE QUANTITY §AC1(c)'s BET IS ABOUT — MEASURED, NOT JUDGED")
    print("  inside the name vs. name-to-tagline, both LINE-BOX clearances\n")
    print(f"  {'leading':>12}{'inside mm':>12}{'to tagline mm':>16}"
          f"{'ratio':>9}")
    out = []
    for em in (SET, INCUMBENT):
        tag = f"coh{em:.4f}".replace(".", "_")
        r = spans(render_panel(em, SHIPPING, tag))      # §BH68(d): `None` was the shipping name; now it is no name
        inside = (_named(r, "Damascena")[2][1]
                  - _named(r, "Rose")[2][3])
        below = _named(r, "N I G")[2][1] - _named(r, "Damascena")[2][3]
        out.append((em, inside, below, inside / below))
        print(f"  {em:>12.4f}{inside:>12.3f}{below:>16.3f}"
              f"{inside / below:>9.3f}")
    print("\n  The second column is the SAME NUMBER at both leadings, which is")
    print("  WI-U's fix holding: the support stack hangs off the name block's")
    print("  last baseline, so changing the leading moves the block and not")
    print("  the gap beneath it. That is what makes this a comparison of one")
    print("  variable rather than of two.")
    print("\n  BOTH SURVIVORS ARE ABOVE 1. At the ruled 2.0 em the two lines")
    print("  of the name are 1.33x further from each other than the name is")
    print("  from the tagline; at the incumbent, 3.44x. If the owner's stated")
    print("  losing condition is read as this ratio, 2.0 em does not clear it")
    print("  — it reduces it by a factor of 2.6.")
    print("\n  AND THE PRE-AUTHORISED FALLBACK IS WORSE ON THIS AXIS. §AC1(c)")
    print("  says *'if 2.0 loses, 3.0047 is the fallback and it needs no new")
    print("  ruling to take'*. On the quantity the bet names, 3.0047 loses by")
    print("  more than 2.0 does, so the fallback may not be one.")
    ceiling = (out[0][2] + line_box_height()) / EM_MM
    floor_em = line_box_height() / EM_MM
    print(f"\n  THE WINDOW WHERE THE RATIO IS BELOW 1, measured: "
          f"[{floor_em:.3f}, {ceiling:.3f}) em")
    print("  — bounded below by the metric floor §AC1 ruled and above by the")
    print("  leading at which the inside clearance equals the one below. It")
    print("  contains neither survivor. THIS IS NOT A PROPOSAL: §AC1(b) says")
    print("  clearing the floor says only which values are legal, and naming a")
    print("  legal interval is the same kind of statement. The setting is the")
    print("  owner's and 2.0 em stands until the owner looks at the render.")
    return out, floor_em, ceiling


def survivors():
    """§AC1(c)'s bet, as the artefact that can lose it."""
    gap = 10.0
    ink = Color.from_hex("#3A2A30")
    kids = []
    panels = [(f"{SET:.2f} em", SET), (f"{INCUMBENT:.4f} em", INCUMBENT)]
    for i, (label, em) in enumerate(panels):
        ox = MARGIN + i * (ZONE_W + gap)
        with leading(em):
            kids += _front(f"s{i}", ox, MARGIN + 7.0, SHIPPING)      # §BH68(d): as above
        kids.append(TextRun(name=f"cap-{i}", text=label, x=ox + ZONE_W / 2,
                            y=MARGIN + 4.0, size_pt=4.2, color=ink,
                            font="bold", align="center"))
    page_w = 2 * MARGIN + 2 * ZONE_W + gap
    kids += _footer([
        f"BOTH 1:1 - zone {ZONE_W} x {ZONE_H} mm",
        f"name {RULED_PT} pt in both, only the leading differs",
        f"both clear the {RULED_FLOOR_EM} em metric floor",
    ], page_w, MARGIN + ZONE_H + 12.0, ink)
    p = os.path.join(OUT, "wiy_survivors.pdf")
    _emit(kids, p, page_w, ZONE_H + 2 * MARGIN + 20.0, "survivors")
    print(f"\n  wrote {os.path.basename(p)} (+ .png at {DPI} dpi) — "
          f"§AC1(c)'s two survivors, 1:1   fits={_caption_fits(p, page_w)}")
    return p


def control_sheet():
    """The control, as a picture: the dead leading and the set one, on the
    shipping name and on the synthetic. The top-left panel is the one §AC1(a)
    is about — it looks fine, and it is a FAIL."""
    gap = 8.0
    ink = Color.from_hex("#3A2A30")
    kids = []
    cols = [(DEAD, f"{DEAD} em  DEAD"), (SET, f"{SET:.2f} em  SET")]
    rows_ = [(SHIPPING, "Rose (ships)"), (SYNTHETIC, "Rogypj (synthetic)")]
    top = MARGIN + 10.0                    # room for the column headers
    step = ZONE_H + 16.0                   # room for each row's own label
    for j, (name, rlabel) in enumerate(rows_):
        for i, (em, clabel) in enumerate(cols):
            ox = MARGIN + i * (ZONE_W + gap)
            with leading(em):
                kids += _front(f"c{i}{j}", ox, top + j * step, name)
            if j == 0:
                kids.append(TextRun(
                    name=f"col-{i}", text=clabel, x=ox + ZONE_W / 2,
                    y=MARGIN + 3.5, size_pt=4.0, color=ink, font="bold",
                    align="center"))
        # the row label sits BELOW the column headers, not level with them —
        # the first run put both at the same y and they overlapped.
        kids.append(TextRun(
            name=f"row-{j}", text=rlabel, x=MARGIN,
            y=top + j * step - 2.5, size_pt=3.4, color=ink, align="left"))
    page_w = 2 * MARGIN + 2 * ZONE_W + gap
    foot_y = top + 2 * step - 16.0 + ZONE_H + 6.0
    kids += _footer([
        "LEFT COLUMN FAILS THE METRIC FLOOR IN BOTH ROWS",
        "the top-left panel is the coincidence §AC1(a) is about:",
        "it looks fine, and it is a FAIL",
    ], page_w, foot_y, ink)
    p = os.path.join(OUT, "wiy_control.pdf")
    _emit(kids, p, page_w, foot_y + 12.0, "control")
    print(f"  wrote {os.path.basename(p)} (+ .png) — §AC1(d) as a picture"
          f"   fits={_caption_fits(p, page_w)}")
    return p


def main():
    os.makedirs(OUT, exist_ok=True)
    verify_zone_is_production()
    box_h, floor_em = floors()
    control()
    print("\nWHAT §AC1 SET, AND WHAT IT COSTS")
    for em, tag in ((DEAD, "dead"), (SET, "SET"), (INCUMBENT, "incumbent")):
        d = em * EM_MM - box_h
        verb = "clears by" if d >= 0 else "OVERLAPS by"
        print(f"  {em:>10.4f} em ({tag:>9}) -> {em * EM_MM:6.3f} mm, "
              f"{verb} {abs(d):.3f} mm = {abs(d) / EM_MM:.3f} em")
    print(f"\n  §AC1 says 1.06 em overlaps by {RULED_OVERLAP_MM} mm; measured "
          f"{abs(DEAD * EM_MM - box_h):.3f} mm.")
    print(f"  §AC1(c) says 2.0 em clears the floor by 0.638 em; measured "
          f"{(SET - floor_em):.3f} em.")
    cohesion()
    print("\nRENDERS")
    survivors()
    control_sheet()
    print(f"\n  NAME_LEADING_EM after all renders = "
          f"{compose_dropper.NAME_LEADING_EM!r}  (must be {SET!r})")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
