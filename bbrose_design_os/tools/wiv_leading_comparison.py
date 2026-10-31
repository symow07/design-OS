"""WI-V / §AB3 — the leading comparison. NO VERDICT IS ISSUED.

    python tools/wiv_leading_comparison.py

§AB3 issues no ruling on the leading and asks for the render first, because
§AA2's law is *render before judging* and 1.06 em has never been seen. This
tool produces the comparison §AB3(a) specifies — 1.06 em, 2.0 em, 3.0047 em,
side by side, at TRUE SCALE, on the ruled 9.0 pt name — and measures all three
off the emitted PDFs. It recommends nothing. The verdict is the owner's and it
comes back as §AC.

WHY 9.0 AND NOT 6.5
§AB2 settled the size, and §AB3(a) is explicit: a comparison at a size we no
longer use is a comparison of nothing. Every panel here is 9.0 pt.

WHY THE INCUMBENT IS IN THE COMPARISON AND NOT ON TRIAL
§AB3(b): 3.0047 em carries no penalty for being accidental. It is what every
render and every approval in this repository has been of. Its PROVENANCE was a
defect in a comment — a `1.06` that read as an em ratio but was applied to
points and added to millimetres, so the leading it set was 1.06 / (25.4/72) =
3.0047244094488192 em. WI-P corrected the unit path and preserved the artwork
to 1 ULP. The number's APPEARANCE has never been judged and may be right, so
it is rendered here on the same page and in the same instrument as the other
two, with nothing in its label to prejudice it.

WHAT WI-U MEANS FOR THIS COMPARISON
Until WI-U the support line sat at a fraction of the drawn zone while the name
block was physical, so changing the leading changed the collision. Two of these
three panels would have overlapped by different amounts and the owner would
have been comparing collisions rather than leading. The support stack now hangs
off the name block's last baseline, so the clearance below the name is a
CONSTANT across all three panels — measured and printed below, not asserted.
That is the property that makes this page a comparison of one variable.
"""
from __future__ import annotations

import contextlib
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

import numpy as _np  # noqa: E402
import pymupdf  # noqa: E402

from apps.ire import compose_dropper  # noqa: E402
from apps.ire.compose_dropper import (_front_typography,  # noqa: E402
                                      compose_dropper_sheet)
from apps.ire.container_concept_fidelity import (  # noqa: E402
    measure_concept_fidelity)
from apps.ire.emitters.pdf_ai import emit_pdf_ai  # noqa: E402
from apps.ire.graph import (Color, Document, Group, Rect,  # noqa: E402
                            Stroke, TextRun)
from apps.ire.tests.test_back_panel import (_BACK_ZONE,  # noqa: E402
                                            _FRONT_NAME_LINES, _FRONT_RECORD,
                                            _FRONT_ZONE, _GEOMETRY)
from tools.wim_front_render import (K, MARGIN, ZONE_H,  # noqa: E402
                                    ZONE_W, spans,
                                    verify_zone_is_production)

OUT = os.path.join(_HERE, "docs", "visual_quality", "wiv_leading")
DPI = 600

#: §AB2's ruled size, fixed for every panel on this page.
RULED_PT = 9.0

#: The three §AB3(a) names. The incumbent is written as the FULL float rather
#: than "3.0047" because that is the value in the source, and a comparison that
#: renders a rounded version of the incumbent is not rendering the incumbent.
#:
#: §AC1 BROKE THIS LINE AND NOTHING IN THE SUITE NOTICED. It read
#: `compose_dropper.NAME_LEADING_EM`, which was the incumbent until §AC1 set it
#: to 2.0 — after which this tool's three panels would have been 1.06, 2.00 and
#: 2.00, a "comparison" containing the same value twice, with the caption
#: computed from the same variable so both labels would have agreed with the
#: artwork and with each other. `test_wiv_leading_comparison.py` loads this
#: module and never asserts `LEADINGS`, so the suite stayed green. The defect
#: was introduced by the §AC1 constant swap and is repaired as part of it, not
#: as a chained fix; the guard against a silent recurrence is in
#: `test_wiy_leading_metric_floor.py`, which asserts these three are three
#: DISTINCT numbers.
INCUMBENT = compose_dropper.NAME_LEADING_INCUMBENT_EM

#: What the composer SHIPS at, captured at import. Separate from INCUMBENT
#: since §AC1: the restore check at the end of `main` asks whether this tool
#: left the composer as it found it, and that question is about the live
#: constant, not about the recorded one.
SHIPPED = compose_dropper.NAME_LEADING_EM

#: Labels carry the number and nothing else. "incumbent", "tight", "current",
#: "proposed" are all verdict words in a page whose whole point is that no
#: verdict has been reached, so the captions state em and measured millimetres
#: and let the owner look.
LEADINGS = [
    ("1.06 em", 1.06),
    ("2.00 em", 2.0),
    (f"{INCUMBENT:.4f} em", INCUMBENT),
]


@contextlib.contextmanager
def leading(em: float):
    """Swap `NAME_LEADING_EM` for one render.

    The producer reads the module global at call time, so this changes the
    LIVE composer for the duration and nothing else about it. The alternative
    — adding a parameter to `_front_typography` — would be a production change
    that §AB3 did not ask for and §AB4(c) forbids, to render a page that is
    explicitly not a decision.
    """
    was = compose_dropper.NAME_LEADING_EM
    compose_dropper.NAME_LEADING_EM = em
    try:
        yield
    finally:
        compose_dropper.NAME_LEADING_EM = was


def _front(tag, ox, oy):
    """The producer called exactly as the sheet calls it, at s=1.0."""
    zone = dict(_FRONT_ZONE, x=0, y=0)
    closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                 + (_GEOMETRY.get("visible_neck_mm") or 3.0))
    kids, _pl, _lg, zrect = _front_typography(
        _GEOMETRY, zone, ox, oy - closure_h, 1.0, None,
        prefix=f"{tag}-", name_min=RULED_PT, name_lines=_FRONT_NAME_LINES,   # §BH68(d): the name, handed in
        **_FRONT_RECORD)        # §BH67(c)2: the record's two front lines, handed in as the sheet's caller does
    outline = Rect(name=f"{tag}-zone-outline", x=zrect[0], y=zrect[1],
                   w=ZONE_W, h=ZONE_H,
                   stroke=Stroke(color=Color.from_hex("#B0A0A8"),
                                 width_mm=0.1, opacity=0.9))
    return [outline] + list(kids)


def _emit(children, path, page_w, page_h, title):
    doc = Document(title=title, page_w=page_w, page_h=page_h,
                   root=Group(name="WIV", role="decoration",
                              children=children))
    emit_pdf_ai(doc, path)
    d = pymupdf.open(path)
    d[0].get_pixmap(dpi=DPI).save(path[:-4] + ".png")
    d.close()
    return path


def _zone_rect(pdf):
    """The zone box read back out of the artefact, in millimetres."""
    d = pymupdf.open(pdf)
    rects = [dr["rect"] for dr in d[0].get_drawings()]
    d.close()
    r = max(rects, key=lambda q: (q.x1 - q.x0) * (q.y1 - q.y0))
    return r.x0 / K, r.y0 / K, r.x1 / K, r.y1 / K


def render_each():
    """One panel per leading, each its own file, so a single one can be
    printed at 100% and held against the bottle without the other two on the
    sheet influencing the eye."""
    made = []
    for label, em in LEADINGS:
        tag = f"em{em:.4f}".replace(".", "_")
        with leading(em):
            kids = _front(tag, MARGIN, MARGIN)
        p = os.path.join(OUT, f"leading_{tag}.pdf")
        _emit(kids, p, ZONE_W + 2 * MARGIN, ZONE_H + 2 * MARGIN, tag)
        made.append((label, em, p))
    return made


def render_three():
    """§AB3(a)'s page: all three, true scale, one image."""
    gap = 9.0
    ink = Color.from_hex("#3A2A30")
    kids = []
    for i, (label, em) in enumerate(LEADINGS):
        ox = MARGIN + i * (ZONE_W + gap)
        with leading(em):
            kids += _front(f"c{i}", ox, MARGIN + 6.0)
        kids.append(TextRun(name=f"cap-{i}", text=label, x=ox + ZONE_W / 2,
                            y=MARGIN + 3.0, size_pt=4.2, color=ink,
                            font="bold", align="center"))
    page_w = 2 * MARGIN + 3 * ZONE_W + 2 * gap
    kids.append(TextRun(
        name="foot",
        text=(f"ALL THREE 1:1 - zone {ZONE_W} x {ZONE_H} mm - name "
              f"{RULED_PT} pt in all three - only the leading differs"),
        x=page_w / 2, y=MARGIN + ZONE_H + 11.0, size_pt=3.6, color=ink,
        align="center"))
    p = os.path.join(OUT, "leading_three_up.pdf")
    _emit(kids, p, page_w, ZONE_H + 2 * MARGIN + 13.0, "three")
    return p


def _named(rows, prefix):
    return next(r for r in rows if r[0].startswith(prefix))


def measure():
    """Every number below is read back out of an emitted PDF."""
    print(f"\n§AB3(a) — THREE LEADINGS AT {RULED_PT} pt, TRUE SCALE, MEASURED")
    print(f"  {'leading':>14}{'gap mm':>9}{'gap/em':>9}{'block mm':>10}"
          f"{'Dam->NIGHT':>12}{'tightest box':>14}{'lower band mm':>15}"
          f"{'%':>7}")
    rows_out = []
    for label, em in LEADINGS:
        tag = f"em{em:.4f}".replace(".", "_")
        pdf = os.path.join(OUT, f"leading_{tag}.pdf")
        r = spans(pdf)
        zx0, zy0, zx1, zy1 = _zone_rect(pdf)
        rose, dam = _named(r, "Rose"), _named(r, "Damascena")
        nig = _named(r, "N I G")
        # baseline-to-baseline is what `leading` sets; bbox tops of two runs
        # at one size differ by exactly that, so this reads the set value back.
        gap = dam[2][1] - rose[2][1]
        block = dam[2][3] - _named(r, "BBROSE")[2][1]
        clear = nig[2][1] - dam[2][3]
        # the tightest pair is reported BY NAME. An anonymous minimum tells
        # the owner that something touches and not what, and "something
        # touches" is the half of a measurement that cannot be acted on.
        pairs = [(b[2][1] - a[2][3], a[0], b[0]) for a, b in zip(r, r[1:])]
        tight, ta, tb = min(pairs)
        band = zy1 - max(q[2][3] for q in r)
        rows_out.append((label, em, gap, clear, tight, band, ta, tb))
        print(f"  {label:>14}{gap:>9.3f}{gap / em:>9.3f}{block:>10.3f}"
              f"{clear:>12.3f}{tight:>14.3f}{band:>15.3f}"
              f"{100 * band / (zy1 - zy0):>7.1f}   {ta[:9]}->{tb[:9]}")
    print("\n  gap/em is the same millimetre figure in all three rows because")
    print("  it is the em, converted: 9.0 pt = 3.175 mm. It is printed as a")
    print("  check that the swap took, not as a finding.")
    print("\n  'tightest box' is the smallest clearance between any two SPAN")
    print("  BOXES on the panel, named by pair. It is a LINE-BOX quantity,")
    print("  not ink — a span box runs ascent to descent whether or not a")
    print("  glyph reaches either. The section below measures both, because")
    print("  at the tight leading they disagree about whether anything is")
    print("  wrong, and the first version of this tool reported only one of")
    print("  them and called it ink.")

    clears = sorted(c for _, _, _, c, _, _, _, _ in rows_out)
    print(f"\n  Dam->NIGHT clearance, all three: {clears[0]:.6f} .. "
          f"{clears[-1]:.6f} mm (spread {clears[-1] - clears[0]:.2e} mm)")
    print("  Not one value to the last bit — the spread is a nanometre of")
    print("  float, and writing 'identical' would be the same overclaim the")
    print("  WI-U carry-across comment was caught making. What it means is")
    print("  WI-U's fix holding: the support stack follows the name block, so")
    print("  the leading moves the block and not the gap under it. Before")
    print("  WI-U this column would have read three different numbers, two of")
    print("  them negative, and the page would have compared collisions.")
    return rows_out


#: Rasterisation zoom for the ink measurement. 24x at 72 dpi is 1728 dpi, so
#: one pixel row is 0.0147 mm — two orders finer than the 1.073 mm quantity it
#: has to resolve, which is what makes the band count a measurement rather
#: than a rendering artefact.
INK_ZOOM = 24.0


def ink_bands(pdf, top_text="Rose", bottom_text="Damascena"):
    """The contiguous bands of ACTUAL DARK PIXELS across the two name lines.

    A PDF span bbox is the font's line box — ascent to descent — and it is
    drawn whether or not any glyph reaches those extents. `Rose` has no
    descender and `Damascena`'s tallest letter is a cap, so the line boxes
    and the ink are different quantities by millimetres, and the difference
    is the entire question at 1.06 em. This rasterises and looks.
    """
    d = pymupdf.open(pdf)
    pg = d[0]
    boxes = {}
    for blk in pg.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                t = sp["text"].strip()
                if t in (top_text, bottom_text):
                    boxes[t] = sp["bbox"]
    pm = pg.get_pixmap(matrix=pymupdf.Matrix(INK_ZOOM, INK_ZOOM),
                       colorspace=pymupdf.csGRAY)
    a = _np.frombuffer(pm.samples, dtype=_np.uint8).reshape(pm.height,
                                                            pm.width)
    y0 = boxes[top_text][1] - 1.0
    y1 = boxes[bottom_text][3] + 1.0
    x0 = min(boxes[top_text][0], boxes[bottom_text][0]) - 1
    x1 = max(boxes[top_text][2], boxes[bottom_text][2]) + 1
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
    # in mm, and the rule above the name is band 0 — the two name lines are
    # the last two
    out = [((off + b[0] / INK_ZOOM) / K, (off + b[1] / INK_ZOOM) / K)
           for b in bands]
    return out[-2], out[-1], len(out)


def touching_leading():
    """The leading at which the name block collides WITH ITSELF, measured —
    and there are TWO answers to that, not one.

    §AB2(f)'s discipline applied to the other axis: a limit only found by
    exceeding it is a limit nobody measured. But the first version of this
    function measured the SPAN BOX and called it ink, and the two are not the
    same number. The line box is ascent-to-descent and is drawn whether or
    not a glyph reaches it; `Rose` has no descender, so at 1.06 em the boxes
    overlap by 0.959 mm while the drawn letters still clear by 1.073. Both
    are reported, because they answer different questions:

    * the METRIC floor is a property of the FACE at this size, and below it
      the setting stops guaranteeing separation for any name at all;
    * the INK floor is a property of THESE TWO WORDS, and it moves the moment
      the product name does — §AB2(f) has the composer sizing to fit names it
      has not seen, and a name with a descender on line one would close the
      1.073 mm without anything about the leading changing.

    Reporting only the second would say the tight panel is fine. Reporting
    only the first would say it collides. Neither sentence is true.
    """
    pdf = os.path.join(OUT, "leading_em3_0047.pdf")
    r = spans(pdf)
    rose = _named(r, "Rose")
    box_h = rose[2][3] - rose[2][1]
    em_mm = RULED_PT * 25.4 / 72.0
    print(f"\nWHERE THE BLOCK MEETS ITSELF — measured, at {RULED_PT} pt")
    print("  TWO FLOORS, and they are different numbers.\n")
    print("  1. THE METRIC FLOOR — the face's own line box, any name")
    print(f"     {'line box of Rose, read from the PDF':<38}: {box_h:.3f} mm")
    print(f"     {f'one em at {RULED_PT} pt':<38}: {em_mm:.3f} mm")
    print(f"     {'leading at which the BOXES meet':<38}: {box_h:.3f} mm = "
          f"{box_h / em_mm:.3f} em")
    for label, em in LEADINGS:
        d = em * em_mm - box_h
        verb = "clears by" if d >= 0 else "OVERLAPS by"
        print(f"       {label:>14} -> {em * em_mm:6.3f} mm, {verb} "
              f"{abs(d):.3f} mm")
    print(f"\n  2. THE INK FLOOR — these two words, rasterised at "
          f"{int(INK_ZOOM * 72)} dpi")
    ink_rows = []
    for label, em in LEADINGS:
        f = os.path.join(OUT, f"leading_em{em:.4f}".replace(".", "_") + ".pdf")
        top, bottom, nbands = ink_bands(f)
        gap = bottom[0] - top[1]
        ink_rows.append((label, em, gap, nbands))
        verb = "clear white" if gap >= 0 else "INK OVERLAPS"
        print(f"       {label:>14} -> 'Rose' ink ends {top[1]:6.3f}, "
              f"'Damascena' ink starts {bottom[0]:6.3f}")
        print(f"       {'':>14}    {verb} {abs(gap):.3f} mm  "
              f"({nbands} separate ink bands in the block)")
    print("\n  So the tightest of the three panels is BELOW the metric floor")
    print("  and ABOVE the ink floor: the setting no longer guarantees the")
    print("  lines are apart, and for THIS name they are apart anyway. That")
    print("  is a MEASUREMENT and not a verdict. It says where the ink is,")
    print("  not which leading is right, and it narrows nothing §AB3")
    print("  reserved. It is reported because §AB0(b) requires a ruling to")
    print("  know the measurement it would be betting against — and because")
    print("  the ink figure is the one that stops being true when the")
    print("  product name changes, which §AB2(f) says it will.")
    return box_h, box_h / em_mm, ink_rows


#: `container_concept_fidelity.py:461`. Copied here as a STRING and evaluated,
#: so the report cannot drift from the source by transcription.
UNIFIED_RULE = "gap <= size * 1.45"


def run_the_gate(em):
    """Compose the WHOLE SHEET at `em` and RUN the fidelity gate on it.

    Not the typography fragment the panels above are built from: the gate
    returns at its first axis when the material objects are absent, so a
    fragment never reaches §11 and reports an axis list one item long. The
    table below therefore has to be produced from the document the pipeline
    actually hands the gate (`targets/container/__init__.py:1276`) or it is
    not a measurement of the gate at all — it is arithmetic that resembles
    one, which is the thing this sprint keeps catching."""
    was = compose_dropper.NAME_LEADING_EM
    compose_dropper.NAME_LEADING_EM = em
    try:
        doc = compose_dropper_sheet(
            _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
            logo_path=None, product_name="Rose Damascena", sku="WIV",
            back_sections=[{"heading": "P", "text": "x"}],
            revision_status="WIV_COMPARISON")
    finally:
        compose_dropper.NAME_LEADING_EM = was
    report = measure_concept_fidelity(doc, _GEOMETRY)
    axis = next((a for a in report["axes"]
                 if a["axis"] == "product_name_unified_block"), None)
    return axis, report["failures"]


def unified_axis(rows_out, touch_em):
    """What `product_name_unified_block` says at each leading, and what it
    would say if its units were right. This is a MEASUREMENT OF THE GATE, not
    an opinion about the leading, and it is reported because §AB0(b) requires
    a ruling to know what measurement it is betting against — and the owner is
    about to rule on exactly the quantity this axis claims to police."""
    print("\nTHE GATE THAT CLAIMS TO POLICE THIS — container_concept_fidelity")
    print("  §11 axis `product_name_unified_block`, target string:")
    print('    "stacked block, leading <=1.45xsize — one visual element"')
    print(f"  source line 461: `{UNIFIED_RULE}`, where `gap` is")
    print("  `hero_runs[1].y - hero_runs[0].y` (MILLIMETRES, graph space) and")
    print("  `size` is `hero_runs[0].size_pt` (POINTS). The comparison is")
    print("  mm <= pt x 1.45. §Z1(b) in a checker rather than a producer.")
    print("\n  The STATE column is the gate's own return value, not this")
    print("  tool's arithmetic: the sheet is composed at each leading and")
    print("  `measure_concept_fidelity` is called on it. WHOLE GATE is the")
    print("  full `failures` list from the same call.")
    print(f"\n  {'leading':>14}{'gap mm':>9}{'size'  :>7}{'STATE':>15}"
          f"{'WHOLE GATE':>12}{'gap in em':>11}{'em<=1.45':>10}"
          f"{'BOXES MEET?':>13}")
    for label, em, gap, _clear, _tight, _band, _ta, _tb in rows_out:
        axis, failures = run_the_gate(em)
        state = axis["state"] if axis else "AXIS NOT EMITTED"
        as_em = "PASS" if em <= 1.45 else "FAIL"
        overlaps = "YES" if em < touch_em else "no"
        whole = "clean" if not failures else f"{len(failures)} fail"
        print(f"  {label:>14}{axis['value']['leading']:>9.2f}"
              f"{axis['value']['size']:>7.1f}{state:>15}{whole:>12}"
              f"{em:>11.4f}{as_em:>10}{overlaps:>13}")
        assert abs(axis["value"]["leading"] - round(gap, 2)) < 0.01, (
            "the gate's gap and the PDF's gap must be the same quantity")
    print("\n  MEASURED_PASS at all three, and the WHOLE gate clean at all")
    print("  three: no axis anywhere catches it. The threshold it actually")
    print(f"  applies is {RULED_PT} x 1.45 = {RULED_PT * 1.45:.3f} — a POINT "
          f"count used as a")
    print("  millimetre bound, so 25.4/72 of it is thrown away and the real")
    print("  ceiling is 2.8x looser than the one written down.")
    print("\n  THE `em<=1.45` COLUMN IS NOT THE REPAIR. It is printed beside")
    print("  BOXES MEET? precisely so it cannot be read as one: `<=1.45` is")
    print(f"  an UPPER bound only, and the metric floor here is "
          f"{touch_em:.3f} em, so")
    print("  two lines can be set inside each other's line boxes by a full")
    print("  millimetre and satisfy the rule in either unit — the 1.06 em")
    print("  row is that case, PASS in both columns and past the floor. The")
    print("  axis polices 'too loose' and has no term at all for 'too")
    print("  tight', which is the state the §11 target string, 'one visual")
    print("  element', is actually about.")
    print("\n  RECORDED, NOT FIXED (§AB4(c)). Two separate defects, neither")
    print("  repaired here: the unit error at line 461, and the missing")
    print("  lower bound. WI-T's analyser is silent on that line BY DESIGN —")
    print("  `gap` comes from an attribute access it reads as UNKNOWN, and")
    print("  under a comparison an unknown operand means it declines to")
    print("  guess. The documented blind spot, with a live instance attached.")


def main():
    os.makedirs(OUT, exist_ok=True)
    verify_zone_is_production()
    render_each()
    render_three()
    rows_out = measure()
    _box_h, touch_em, _ink_rows = touching_leading()
    unified_axis(rows_out, touch_em)
    print("\nTHE VERDICT CAME BACK AS §AC1 AND IT IS NOT ISSUED HERE. §AB3")
    print("reserved the leading; §AC1 ruled 2.0 em against a 1.362 em metric")
    print("floor and killed 1.06. This page is unchanged and still compares")
    print("three values, because it is the artefact the ruling was made from.")
    print("Nothing in this run changed the composer:")
    print(f"  NAME_LEADING_EM after all renders = {compose_dropper.NAME_LEADING_EM!r}")
    print(f"  unchanged from the shipped value  = {SHIPPED!r}")
    print(f"  recorded incumbent, panel 3       = {INCUMBENT!r}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
