"""WI-M / §AA2 — render the container front before anyone judges it.

§AA2(a) requires the changed front rendered at TRUE SCALE and at both panel
scales, with the images in the owner queue. §AA2(d) is equally binding: "the
render, and only the render". This tool therefore calls the SHIPPING
``_front_typography`` with the arguments the sheet already passes it. It
re-proportions nothing, and WI-M edits no production module.

    python tools/wim_front_render.py                 # render + measure
    python tools/wim_front_render.py --attribution   # + the pre-WI-J control

WHY A TRUE-SCALE RENDER IS A DIFFERENT PICTURE, NOT A SECOND OPINION
--------------------------------------------------------------------
After WI-J every ``size_pt`` is an absolute point value that does not move with
the panel scale ``s`` — that is the whole of the fix. The ZONE, however, is
drawn ``s`` times its physical size. So panel 5 shows physical type against a
1.22x zone and panel 8 shows the same physical type against a 1.545x zone.
**Neither panel on the sheet shows the printed proportion, and the sheet has no
panel that does.** Only s=1.0 does, and nothing in the pipeline draws it.

That is §AA's own precedent one level out: a constraint the pipeline never
reaches is a constraint nobody has tested — here, a SCALE the sheet never draws
is a layout nobody has checked. §W1(a) gave the BACK panel a true-scale panel
for exactly this reason. The front never got one.

THE TWO PANELS ALSO DISAGREE ABOUT TYPE, WHICH IS THE §AA2(c) FINDING
  panel 5 calls with the default ``name_min=9.0``; panel 8 calls with 6.5;
  ``BRAND_PT`` is 6.0 for both. So they do not agree about what dominates.

INPUT PROVENANCE — §AA requires a fixture to be named as a fixture every time
its numbers are quoted:
  ``_GEOMETRY`` and ``_FRONT_ZONE`` are FIXTURES, from
  ``apps/ire/tests/test_back_panel.py``. ``_FRONT_ZONE`` is a transcription of
  what ``propose_zones`` derives, and ``verify_zone_is_production`` below CHECKS
  that transcription rather than trusting it (BODY_FRONT is body_width_mm x
  body_height_mm = 31.5 x 70.5; ``centred`` takes 70%/60% rounded to 1dp = 22.0
  x 42.3). The check is printed on every run.
  ``logo_path=None`` is the LIVE branch: ``BRAND_LOGO_PATH`` is still owner-owed
  (§D), so the composer draws the BBROSE wordmark. Supplying a logo deletes the
  ``front-brand`` run entirely, and every number below with it.

Measurements are read back out of the EMITTED PDF with PyMuPDF — the inked glyph
boxes and the zone outline — never recomputed from the composer's intent. §Z1's
lesson was that a claim contradicting an artefact is a finding about your
instrument.
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

import pymupdf  # noqa: E402

from apps.ire.compose_dropper import _front_typography  # noqa: E402
from apps.ire.emitters.pdf_ai import emit_pdf_ai  # noqa: E402
from apps.ire.graph import (Color, Document, Group, Rect,  # noqa: E402
                            Stroke, TextRun)
from apps.ire.tests.test_back_panel import (_BACK_ZONE,  # noqa: E402
                                            _FRONT_NAME_LINES, _FRONT_RECORD,
                                            _FRONT_ZONE, _GEOMETRY, _LIVE,
                                            _METHODS)

OUT = os.path.join(_HERE, "docs", "visual_quality", "wim_front_true_scale")
K = 72.0 / 25.4          # mm -> pt
MARGIN = 3.0
DPI = 600

HERO_S = 1.22                                   # compose_dropper.py:579
FLAT_S = 34.0 / float(_FRONT_ZONE["width"])     # compose_dropper.py:610
ZONE_W = float(_FRONT_ZONE["width"])
ZONE_H = float(_FRONT_ZONE["height"])

#: (tag, scale, name_min, caption). The two TRUE-SCALE rows are the same
#: physical zone under the two type programmes the sheet currently disagrees
#: about; the two panel rows are those programmes as the sheet draws them.
RENDERS = [
    ("true-9.0", 1.0, 9.0, "TRUE SCALE 1:1 — panel 5's type programme"),
    ("true-6.5", 1.0, 6.5, "TRUE SCALE 1:1 — panel 8's type programme"),
    ("hero", HERO_S, 9.0, "panel 5 as the sheet draws it (s=1.22)"),
    ("flat", FLAT_S, 6.5, f"panel 8 as the sheet draws it (s={FLAT_S:.4f})"),
]


def verify_zone_is_production():
    """The fixture CLAIMS to transcribe ``propose_zones``. Check, do not trust."""
    bw, bh = _GEOMETRY["body_diameter_mm"], _GEOMETRY["body_height_mm"]
    w, h = round(bw * 0.7, 1), round(bh * 0.6, 1)
    derived = {"x": round((bw - w) / 2, 1), "y": round((bh - h) / 2, 1),
               "width": w, "height": h}
    actual = {k: _FRONT_ZONE[k] for k in derived}
    return derived, actual, derived == actual


def _front(tag, s, name_min, ox, oy):
    """The shipping producer, called exactly as the sheet calls it."""
    zone = dict(_FRONT_ZONE, x=0, y=0)
    closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                 + (_GEOMETRY.get("visible_neck_mm") or 3.0))
    kids, _pl, _lg, zrect = _front_typography(
        _GEOMETRY, zone, ox, oy - closure_h * s, s, None,
        prefix=f"{tag}-", name_min=name_min, name_lines=_FRONT_NAME_LINES,   # §BH68(d): the name, handed in
        **_FRONT_RECORD)        # §BH67(c)2: the record's two front lines, handed in as the sheet's caller does
    outline = Rect(name=f"{tag}-zone-outline", x=zrect[0], y=zrect[1],
                   w=ZONE_W * s, h=ZONE_H * s,
                   stroke=Stroke(color=Color.from_hex("#B0A0A8"),
                                 width_mm=0.1, opacity=0.9))
    return [outline] + list(kids)


def render_one(tag, s, name_min, caption):
    zw, zh = ZONE_W * s, ZONE_H * s
    doc = Document(title=f"wim-{tag}", page_w=zw + 2 * MARGIN,
                   page_h=zh + 2 * MARGIN,
                   root=Group(name=f"WIM-{tag}", role="decoration",
                              children=_front(tag, s, name_min, MARGIN,
                                              MARGIN)))
    pdf = os.path.join(OUT, f"front_{tag}.pdf")
    emit_pdf_ai(doc, pdf)
    d = pymupdf.open(pdf)
    d[0].get_pixmap(dpi=DPI).save(os.path.join(OUT, f"front_{tag}.png"))
    d.close()
    return pdf


def render_side_by_side():
    """The single image the §AA2(c) decision is actually made from: both type
    programmes, same physical zone, same page, 1:1."""
    gap = 8.0
    kids = (_front("sbs-a", 1.0, 9.0, MARGIN, MARGIN + 5.0)
            + _front("sbs-b", 1.0, 6.5, MARGIN + ZONE_W + gap, MARGIN + 5.0))
    ink = Color.from_hex("#3A2A30")
    # These labels are ANNOTATION on a review sheet, not artwork. They are sized
    # to fit the page they sit on: at 5.0 pt the first one ran off the left edge
    # and collided with the second, which is the same class of defect this
    # render exists to show. Measured, not guessed: ~21 characters at 4.0 pt is
    # ~15 mm, and the label centres are 30 mm apart.
    for name, cx, txt in (("lbl-a", MARGIN + ZONE_W / 2, "PANEL 5 — name 9.0 pt"),
                          ("lbl-b", MARGIN + ZONE_W * 1.5 + gap,
                           "PANEL 8 — name 6.5 pt")):
        kids.append(TextRun(name=name, text=txt, x=cx, y=MARGIN + 2.5,
                            size_pt=4.0, color=ink, font="bold",
                            align="center"))
    kids.append(TextRun(
        name="lbl-foot",
        text=f"BOTH 1:1 — zone {ZONE_W} x {ZONE_H} mm — wordmark 6.0 pt in both",
        x=MARGIN + ZONE_W + gap / 2, y=MARGIN + ZONE_H + 9.5, size_pt=4.0,
        color=ink, align="center"))
    doc = Document(title="wim-side-by-side",
                   page_w=2 * ZONE_W + gap + 2 * MARGIN,
                   page_h=ZONE_H + 2 * MARGIN + 12.0,
                   root=Group(name="WIM-SBS", role="decoration",
                              children=kids))
    pdf = os.path.join(OUT, "front_true_scale_side_by_side.pdf")
    emit_pdf_ai(doc, pdf)
    d = pymupdf.open(pdf)
    d[0].get_pixmap(dpi=DPI).save(
        os.path.join(OUT, "front_true_scale_side_by_side.png"))
    d.close()


def render_sheet_crops():
    """The ARTEFACT: the composed sheet, then panels 5 and 8 cropped from it.
    The tight renders show the front alone; panel 5 draws it ON the bottle,
    which is the thing the hierarchy decision is actually looking at."""
    from apps.ire.compose_dropper import compose_dropper_sheet
    doc = compose_dropper_sheet(
        _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
        logo_path=None, product_name="Rose Damascena", sku="X",
        back_sections=_LIVE, revision_status="WI-M RENDER",
        methods_record=_METHODS)
    pdf = os.path.join(OUT, "sheet.pdf")
    emit_pdf_ai(doc, pdf)
    d = pymupdf.open(pdf)
    page = d[0]
    page.get_pixmap(dpi=200).save(os.path.join(OUT, "sheet.png"))
    for tag, box in (("panel5", (148.0, 22.0, 205.0, 162.0)),
                     ("panel8", (10.0, 183.0, 54.0, 268.0))):
        clip = pymupdf.Rect(*[v * K for v in box])
        page.get_pixmap(dpi=DPI, clip=clip).save(
            os.path.join(OUT, f"sheet_{tag}.png"))
    d.close()


def spans(pdf):
    d = pymupdf.open(pdf)
    rows = []
    for blk in d[0].get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for sp in line.get("spans", []):
                if sp["text"].strip():
                    rows.append((sp["text"].strip(), sp["size"],
                                 [v / K for v in sp["bbox"]]))
    d.close()
    return sorted(rows, key=lambda r: r[2][1])


def measure(pdf, s):
    """Zone outline read FROM the artefact, then every run judged against it."""
    d = pymupdf.open(pdf)
    rects = [dr["rect"] for dr in d[0].get_drawings()]
    d.close()
    zone = max(rects, key=lambda r: (r.x1 - r.x0) * (r.y1 - r.y0))
    zx0, zx1 = zone.x0 / K, zone.x1 / K
    rows = spans(pdf)
    crossings, gaps = [], []
    for text, size, (x0, y0, x1, y1) in rows:
        if x0 < zx0 - 1e-6 or x1 > zx1 + 1e-6:
            crossings.append((text, max(zx0 - x0, 0.0), max(x1 - zx1, 0.0)))
    for a, b in zip(rows, rows[1:]):
        gaps.append((a[0], b[0], b[2][1] - a[2][3]))
    return rows, (zx0, zx1), crossings, gaps


def attribution():
    """Is the true-scale collision WI-J's doing, or older? Attribution by
    arithmetic is the move §Z1 punished, so this loads the PRE-WI-J producer out
    of git (dd0d60b^, the WI-J commit's parent) and runs the same four
    configurations through it."""
    import importlib.util
    import subprocess
    src = "bbrose_design_os/apps/ire/compose_dropper.py"
    try:
        blob = subprocess.check_output(
            ["git", "-C", os.path.dirname(_HERE), "show", f"dd0d60b^:{src}"],
            text=True, stderr=subprocess.DEVNULL)
    except Exception as exc:                      # pragma: no cover
        print(f"  attribution unavailable: {exc}")
        return
    tmp = "/tmp/_wim_compose_dropper_prewij.py"
    with open(tmp, "w") as fh:
        fh.write(blob)
    spec = importlib.util.spec_from_file_location("_wim_prewij", tmp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pre = mod._front_typography

    print("\nATTRIBUTION — pre-WI-J (dd0d60b^) vs shipping, same 4 configs")
    print(f"  {'config':<32}{'name PRE':>10}{'name POST':>11}"
          f"{'tightest gap PRE':>19}{'POST':>9}")
    for tag, s, nm, _cap in RENDERS:
        out = {}
        for who, fn in (("PRE", pre), ("POST", _front_typography)):
            zone = dict(_FRONT_ZONE, x=0, y=0)
            ch = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                  + (_GEOMETRY.get("visible_neck_mm") or 3.0))
            kids, *_ = fn(_GEOMETRY, zone, MARGIN, MARGIN - ch * s, s, None,
                          prefix=f"{who}-", name_min=nm)
            doc = Document(title="p", page_w=ZONE_W * s + 6,
                           page_h=ZONE_H * s + 6,
                           root=Group(name="P", role="decoration",
                                      children=list(kids)))
            p = os.path.join("/tmp", f"_wim_attr_{who}.pdf")
            emit_pdf_ai(doc, p)
            r = spans(p)
            name = next(x[1] for x in r if x[0].startswith("Damascena"))
            tight = min(b[2][1] - a[2][3] for a, b in zip(r, r[1:]))
            out[who] = (name, tight)
        flag = ("  <- OVERLAP in BOTH: not WI-J's doing"
                if out["PRE"][1] < 0 and out["POST"][1] < 0 else "")
        print(f"  {tag + ' s=' + format(s, '.4f') + ' nm=' + str(nm):<32}"
              f"{out['PRE'][0]:>10.3f}{out['POST'][0]:>11.3f}"
              f"{out['PRE'][1]:>19.3f}{out['POST'][1]:>9.3f}{flag}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attribution", action="store_true",
                    help="also run the pre-WI-J negative control")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    derived, actual, ok = verify_zone_is_production()
    print("ZONE PROVENANCE — fixture _FRONT_ZONE vs propose_zones arithmetic")
    print(f"  propose_zones derives : {derived}")
    print(f"  fixture carries       : {actual}")
    print(f"  transcription faithful: {ok}")
    if not ok:
        raise SystemExit("fixture no longer transcribes propose_zones — stop")
    print(f"  HERO_S {HERO_S}   FLAT_S 34.0/{ZONE_W} = {FLAT_S:.6f}\n")

    pdfs = {}
    for tag, s, nm, cap in RENDERS:
        pdfs[tag] = render_one(tag, s, nm, cap)
    render_side_by_side()
    render_sheet_crops()

    for tag, s, nm, cap in RENDERS:
        rows, (zx0, zx1), crossings, gaps = measure(pdfs[tag], s)
        print("=" * 72)
        print(f"{tag}   s={s:.4f}  name_min={nm}   {cap}")
        print(f"  zone outline (read from the PDF): "
              f"{zx0:.3f} .. {zx1:.3f} mm wide")
        for text, size, (x0, y0, x1, y1) in rows:
            print(f"    {text[:24]:<26}{size:>7.2f} pt   "
                  f"x {x0:7.3f}..{x1:7.3f}   y {y0:7.3f}..{y1:7.3f}")
        print(f"  runs crossing the zone: "
              f"{crossings if crossings else 'NONE'}")
        for a, b, g in gaps:
            state = "OVERLAP" if g < 0 else ("touching" if g < 0.15 else "clear")
            print(f"    {a[:18]:<20} -> {b[:18]:<20} gap {g:+7.3f} mm  {state}")
        print()

    if args.attribution:
        attribution()
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
