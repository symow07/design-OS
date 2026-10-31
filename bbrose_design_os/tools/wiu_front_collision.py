"""WI-U / §AB2 — the front collision, repaired by moving the support line.

    python tools/wiu_front_collision.py

§AB2 ruled that **9.0 pt is correct** and that the −1.389 mm overlap between
``Damascena`` and ``N I G H T   R E P A I R   O I L`` is a PLACEMENT bug. This
tool renders the repair at true scale, negative-controls it against the
producer as it stood at the PINNED pre-WI-U commit, and measures the
horizontal headroom §AB2(f) asked for.

IT REUSES WI-M'S INSTRUMENT ON PURPOSE
--------------------------------------
``spans``, ``measure`` and ``verify_zone_is_production`` are imported from
``tools/wim_front_render.py`` rather than reimplemented. WI-M established that
the numbers come out of the EMITTED PDF — inked span boxes and the zone outline
read back from the artefact, never recomputed from the composer's intent. A
second copy of that instrument could drift from the first and then the two
sprints would not be comparable, which is the whole value of a control.

WHAT THE DEFECT ACTUALLY WAS, IN ONE SENTENCE
---------------------------------------------
``leading`` is physical (9.54 mm at 9.0 pt, at every panel scale) and the
support line sat at ``zh * 0.545`` which is a fraction of the DRAWN zone, so
the name block and the line beneath it were independent quantities — and at
s=1.0, the only scale that prints, they overlapped. The sheet concealed it
because the smallest front it draws is 1.22×, where the fraction has grown 22%
and the block has not. That is WI-M's FINDING 1 and FINDING 2 meeting.

THE FIX IS A PLACEMENT, AND THE CONTROL PROVES IT IS ONLY A PLACEMENT
---------------------------------------------------------------------
Both support baselines now hang off the name block's last baseline. The
control below runs the pre-WI-U producer and the shipping producer through the
same configurations and prints both, so the claim "the name did not move" is
a measurement rather than an assurance. If the name size or the name's
baselines had moved, this table would say so.

§AB2(c) is RECORDED, NOT RULED, and this tool does not touch it: the type
block still occupies the upper part of the zone and the lower part is still
empty. Moving the support line down consumes a little of that space as a side
effect of clearing the collision; it is not an answer to the question, and no
attempt is made here to fill or to justify the remainder.
"""
from __future__ import annotations

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
from apps.ire.tests.test_back_panel import (_FRONT_ZONE,  # noqa: E402
                                            _GEOMETRY)
from tools.wim_front_render import (FLAT_S, HERO_S, K,  # noqa: E402
                                    MARGIN, ZONE_H, ZONE_W, spans,
                                    verify_zone_is_production)

OUT = os.path.join(_HERE, "docs", "visual_quality", "wiu_front_collision")
DPI = 600

#: The ruled size. §AB2 makes this the fixed point of the whole work item, so
#: it is a module constant and not a parameter — a knob here would invite
#: exactly the "try a smaller name" move the ruling forbids.
RULED_PT = 9.0

#: (tag, scale, name_min PRE, name_min POST). The PRE and POST sizes are
#: carried SEPARATELY because they genuinely differ on one row: the pre-WI-U
#: commit's panel 8 passed 6.5 and §AB2(d) retires it. An earlier version of this table fed 9.0
#: to both columns of that row, which made the control read as though panel 8
#: had always been 9.0 — a control that quietly restates the new state as the
#: old one is worse than no control, so the shape of the table had to change
#: rather than the number in it.
CONFIGS = [
    ("true 1:1", 1.0, RULED_PT, RULED_PT),
    ("panel 5", HERO_S, RULED_PT, RULED_PT),
    ("panel 8", FLAT_S, 6.5, RULED_PT),
    ("1:1 @6.5 (retired)", 1.0, 6.5, 6.5),
]

ZONE_MM = ZONE_W


def _front(producer, tag, s, name_min, ox, oy, logo=None):
    """The producer called exactly as the sheet calls it."""
    zone = dict(_FRONT_ZONE, x=0, y=0)
    closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                 + (_GEOMETRY.get("visible_neck_mm") or 3.0))
    kids, _pl, _lg, zrect = producer(
        _GEOMETRY, zone, ox, oy - closure_h * s, s, logo,
        prefix=f"{tag}-", name_min=name_min)
    outline = Rect(name=f"{tag}-zone-outline", x=zrect[0], y=zrect[1],
                   w=ZONE_W * s, h=ZONE_H * s,
                   stroke=Stroke(color=Color.from_hex("#B0A0A8"),
                                 width_mm=0.1, opacity=0.9))
    return [outline] + list(kids)


#: The commit WI-U starts from — WI-T, the sprint's previous work item. PINNED
#: and not ``HEAD``: the first version of this tool read ``HEAD``, which is the
#: pre-fix producer only until the fix is committed and is the fix itself
#: immediately afterwards. A control that silently becomes a comparison of the
#: new code with itself does not fail, it just stops meaning anything, and it
#: would have printed a table of zero differences that looked like success.
#: WI-M pinned ``dd0d60b^`` for the same reason.
PRE_WIU = "e3d3d6a"


def pre_wiu_producer():
    """``_front_typography`` as it stood before WI-U — the negative control.

    NAMED FOR THE COMMIT, not for ``HEAD``. It was ``head_producer`` until the
    artefact it writes was renamed for the same reason; leaving the function
    called "head" while it loads a pinned SHA is the identical stale label one
    level up, and the next reader would have believed the name over the code.

    Attribution by arithmetic is the move §Z1 punished, so the control is the
    real prior code executed, not a recomputation of what it would have done.
    """
    import importlib.util
    import subprocess
    src = "bbrose_design_os/apps/ire/compose_dropper.py"
    blob = subprocess.check_output(
        ["git", "-C", os.path.dirname(_HERE), "show", f"{PRE_WIU}:{src}"],
        text=True, stderr=subprocess.DEVNULL)
    tmp = "/tmp/_wiu_compose_dropper_pre.py"
    with open(tmp, "w") as fh:
        fh.write(blob)
    spec = importlib.util.spec_from_file_location("_wiu_pre", tmp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._front_typography


def render(producer, tag, s, name_min):
    zw, zh = ZONE_W * s, ZONE_H * s
    doc = Document(title=f"wiu-{tag}", page_w=zw + 2 * MARGIN,
                   page_h=zh + 2 * MARGIN,
                   root=Group(name=f"WIU-{tag}", role="decoration",
                              children=_front(producer, tag, s, name_min,
                                              MARGIN, MARGIN)))
    pdf = os.path.join(OUT, f"front_{tag}.pdf")
    emit_pdf_ai(doc, pdf)
    d = pymupdf.open(pdf)
    d[0].get_pixmap(dpi=DPI).save(os.path.join(OUT, f"front_{tag}.png"))
    d.close()
    return pdf


def render_before_after():
    """The one image the repair is read from: pre-WI-U and shipping, both 1:1,
    both at the ruled 9.0 pt, same page. Same physical zone, same type size —
    the ONLY difference on this page is where the support line sits."""
    gap = 8.0
    pre = pre_wiu_producer()
    kids = (_front(pre, "before", 1.0, RULED_PT, MARGIN, MARGIN + 5.0)
            + _front(_front_typography, "after", 1.0, RULED_PT,
                     MARGIN + ZONE_W + gap, MARGIN + 5.0))
    ink = Color.from_hex("#3A2A30")
    for name, cx, txt in (
            ("lbl-a", MARGIN + ZONE_W / 2, "BEFORE — overlap -1.389 mm"),
            ("lbl-b", MARGIN + ZONE_W * 1.5 + gap,
             "AFTER — clear +1.518 mm")):
        kids.append(TextRun(name=name, text=txt, x=cx, y=MARGIN + 2.5,
                            size_pt=4.0, color=ink, font="bold",
                            align="center"))
    kids.append(TextRun(
        name="lbl-foot",
        text=(f"BOTH 1:1 - zone {ZONE_W} x {ZONE_H} mm - name {RULED_PT} pt "
              f"in both - only the support line moved"),
        x=MARGIN + ZONE_W + gap / 2, y=MARGIN + ZONE_H + 9.5, size_pt=4.0,
        color=ink, align="center"))
    doc = Document(title="wiu-before-after",
                   page_w=2 * ZONE_W + gap + 2 * MARGIN,
                   page_h=ZONE_H + 2 * MARGIN + 12.0,
                   root=Group(name="WIU-BA", role="decoration",
                              children=kids))
    pdf = os.path.join(OUT, "front_collision_before_after.pdf")
    emit_pdf_ai(doc, pdf)
    d = pymupdf.open(pdf)
    d[0].get_pixmap(dpi=DPI).save(
        os.path.join(OUT, "front_collision_before_after.png"))
    d.close()


def _rows(producer, s, nm):
    doc = Document(title="m", page_w=ZONE_W * s + 6, page_h=ZONE_H * s + 6,
                   root=Group(name="M", role="decoration",
                              children=_front(producer, "m", s, nm, 3.0, 3.0)))
    p = "/tmp/_wiu_measure.pdf"
    emit_pdf_ai(doc, p)
    return spans(p)


def _named(rows, prefix):
    return next(r for r in rows if r[0].startswith(prefix))


def control():
    """PRE (the pinned commit) vs POST (shipping), same configs, both measured.

    The SHA is deliberately not interpolated here: a docstring is not an
    f-string, so ``{PRE_WIU}`` would have printed literally and read as a
    formatting bug. The constant is thirty lines up and is the single place
    the commit is written down.
    """
    pre = pre_wiu_producer()
    print("\nNEGATIVE CONTROL — pre-WI-U vs shipping, each at ITS OWN prior size")
    print(f"  {'config':<22}{'name pt PRE':>12}{'POST':>7}"
          f"{'Dam->NIGHT PRE':>16}{'POST':>9}{'tightest POST':>15}")
    for tag, s, pre_nm, post_nm in CONFIGS:
        out = {}
        for who, fn, nm in (("PRE", pre, pre_nm),
                            ("POST", _front_typography, post_nm)):
            r = _rows(fn, s, nm)
            dam = _named(r, "Damascena")
            nig = _named(r, "N I G")
            out[who] = (dam[1], nig[2][1] - dam[2][3],
                        min(b[2][1] - a[2][3] for a, b in zip(r, r[1:])))
        flag = ("  <- WHAT PRINTS" if tag == "true 1:1"
                else "  <- AB2(d)" if tag == "panel 8" else "")
        print(f"  {tag:<22}{out['PRE'][0]:>12.3f}{out['POST'][0]:>7.3f}"
              f"{out['PRE'][1]:>16.3f}{out['POST'][1]:>9.3f}"
              f"{out['POST'][2]:>15.3f}{flag}")

    print("\nWHAT DID NOT MOVE — the same two runs, read from both artefacts")
    r_pre = _rows(pre, 1.0, RULED_PT)
    r_post = _rows(_front_typography, 1.0, RULED_PT)
    print(f"  {'run':<26}{'pt PRE':>8}{'POST':>7}"
          f"{'x0 PRE':>9}{'POST':>8}{'x1 PRE':>9}{'POST':>8}{'y PRE':>9}"
          f"{'POST':>8}")
    for pfx in ("BBROSE", "Rose", "Damascena", "N I G", "30 ml"):
        a, b = _named(r_pre, pfx), _named(r_post, pfx)
        moved = "" if abs(a[2][1] - b[2][1]) < 1e-6 else "   <- MOVED"
        print(f"  {pfx:<26}{a[1]:>8.3f}{b[1]:>7.3f}"
              f"{a[2][0]:>9.3f}{b[2][0]:>8.3f}{a[2][2]:>9.3f}{b[2][2]:>8.3f}"
              f"{a[2][1]:>9.3f}{b[2][1]:>8.3f}{moved}")


def width_mm(text, pt=RULED_PT, font="serif-bold"):
    """One run, measured off its own PDF — the same read-back as everything
    else here, so the headroom number and the collision number come from one
    instrument."""
    doc = Document(title="w", page_w=400.0, page_h=20.0,
                   root=Group(name="W", role="decoration", children=[
                       TextRun(name="t", text=text, x=5.0, y=12.0,
                               size_pt=pt, color=Color.from_hex("#3A2A30"),
                               font=font, align="left")]))
    p = "/tmp/_wiu_width.pdf"
    emit_pdf_ai(doc, p)
    d = pymupdf.open(p)
    w = 0.0
    for blk in d[0].get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for sp in line.get("spans", []):
                if sp["text"].strip():
                    w = (sp["bbox"][2] - sp["bbox"][0]) / K
    d.close()
    return w


#: Real botanical / fragrance names, because the question §AB2(f) asks is
#: about the next SKU and not about a synthetic alphabet.
CANDIDATES = ["Rose", "Myrrh", "Neroli", "Vetiver", "Jasmine", "Bergamot",
              "Magnolia", "Tuberose", "Cardamom", "Geranium", "Damascena",
              "Chamomile", "Patchouli", "Osmanthus", "Immortelle",
              "Sandalwood", "Helichrysum", "Ylang Ylang", "Frankincense",
              "Rosa Centifolia"]


def headroom():
    print(f"\n§AB2(f) — HORIZONTAL HEADROOM at {RULED_PT} pt, zone "
          f"{ZONE_MM} mm wide")
    shipped = width_mm("Damascena")
    print(f"  the shipping line 'Damascena' : {shipped:.3f} mm")
    print(f"  headroom                      : {ZONE_MM - shipped:.3f} mm "
          f"({(ZONE_MM - shipped) / 2:.3f} mm each side)")
    print(f"\n  {'candidate':<18}{'chars':>6}{'width mm':>10}"
          f"{'headroom':>10}   verdict")
    for n in sorted(CANDIDATES, key=len):
        w = width_mm(n)
        print(f"  {n:<18}{len(n):>6}{w:>10.3f}{ZONE_MM - w:>10.3f}   "
              + ("fits" if w <= ZONE_MM
                 else f"OVERFLOWS by {w - ZONE_MM:.3f} mm"))
    print("\n  THE LIMIT IS MILLIMETRES, NOT CHARACTERS — measured both ways:")
    for ch, label in (("i", "narrowest"), ("m", "widest")):
        n = 1
        while width_mm(ch * n) <= ZONE_MM:
            n += 1
        print(f"    {label:<10} all-'{ch}' : {n - 1} characters "
              f"= {width_mm(ch * (n - 1)):.3f} mm")
    for stem in ("Damascena", "Immortelle"):
        s = stem
        while width_mm(s) <= ZONE_MM:
            s = s + s[-1]
        print(f"    {stem}-like mix : longest fitting = {len(s) - 1} "
              f"characters = {width_mm(s[:-1]):.3f} mm")


def main():
    os.makedirs(OUT, exist_ok=True)
    derived, actual, ok = verify_zone_is_production()
    print("ZONE PROVENANCE — fixture _FRONT_ZONE vs propose_zones arithmetic")
    print(f"  propose_zones derives : {derived}")
    print(f"  fixture carries       : {actual}")
    print(f"  transcription faithful: {ok}")
    if not ok:
        raise SystemExit("fixture no longer transcribes propose_zones — stop")

    for tag, s, _pre_nm, post_nm in CONFIGS:
        render(_front_typography,
               tag.replace(" ", "_").replace(":", "").replace("(", "")
               .replace(")", ""), s, post_nm)
    # The control render is named for the COMMIT it came from, not for "HEAD".
    # A file called HEAD stops being true the moment WI-U lands, and a stale
    # label on an artefact is how a comparison quietly becomes a comparison of
    # the new code with itself — the same trap PRE_WIU exists to close.
    render(pre_wiu_producer(), f"{PRE_WIU}_true_1_1", 1.0, RULED_PT)
    render_before_after()
    control()
    headroom()
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
