"""THE WIRING CHECK — the owner's clean-up goal of 2026-10-04 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 4414b0f),
Part 3, as his approval of the final list (transcribed at b5892f9) sets it: every design type run from its brief to its
finished file through the site's own doors, every paid service stubbed, failing on the seven things he named —

  1. a silent fallback            2. AI pixels where vector belongs (one key visual allowed on artwork designs only —
  3. the brief's copy missing        his third answer)
  4. another product's text       5. wrong product words       6. a step that never runs
  7. a broken link between steps

HOW IT RUNS. The stubs stand at the provider boundary only — the Anthropic client behind ``claude_service._get_client``,
the image client the Image Producer calls, and the trend search's connector — so every step between them runs as
production runs it, with the map read, the panel translation and the product inference switched ON (the suite has them
off). Each stub answers from the case's own picture: the picture is painted in flat colours, one per part, and the
"vision" answers find each part by its colour in the very picture they are sent (a colour-keyed oracle), so a read sent
the wrong picture answers wrongly. Every call is recorded; a call no answer exists for is refused AND recorded, so a
step that swallows the refusal still fails its case.

THE CASES are read from the code (``test_every_design_type_has_a_case``): the New design page's cards
(``targets.ui.TARGET_CARDS``), the twelve container forms (``targets.container.archetypes.ARCHETYPES``) and the dropper,
and the composite recipes (``targets.composite.COMPOSITE_RECIPES``). A card or form added without a case fails here.

THE DETECTORS (``Detect``) run after every case; each is proved by a fault planted through the real path
(``PlantedFaultTests``) — never by a fabricated record fed to the detector.

Nothing here moves a band, a threshold or a rule (§BH55, clause 3): a case that could only pass by moving one is a stop,
reported, never relaxed here — a NAMED STOP (the case asserts that refusal and no other) or a KNOWN FAULT (the case
asserts exactly that fault), each with the finding it comes from; either fails the day it is fixed, so it is written out.

Run it: ``venv/bin/python -m pytest -q apps/pipeline/tests/test_wiring_check.py`` (about a minute and a half). Two
optional diagnostics: WIRING_DUMP=<folder> saves each case's image prompts and the pictures its finished files hold;
WIRING_DEBUG=1 adds the motif, fidelity and artwork records to a failure's message.
"""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

import base64
import copy
import importlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.test import SimpleTestCase, TestCase, override_settings

# [his second goal of 2026-10-06, item 2] the fold check as this module first found it — a planted fault that silences
# the export's own check cannot silence this one
from apps.dielines.geometry.fold_check import check as _FOLD_AGAIN  # noqa: E402

FONT = os.path.join(settings.BASE_DIR, "static", "fonts", "NotoSans-Bold.ttf")
W, H = 1024, 1536
GROUND = (236, 231, 226)
#: [his test blocker on design 122, 2026-10-07] the deep charcoal a light product is redrawn on, and the words a redraw
#: opens with (``targets.container.readable.REDRAW_PROMPT``)
REDRAW_GROUND = (47, 45, 44)
REDRAW_WORDS = "Redraw this exact product design so it can be read"
#: 122's own brief, his one-colour brief ("one pink family with red line art"), word for word
BRIEF_122 = """Rose Blossom Hand Cream (test)

Product: BBROSE Rose Blossom Hand Cream (imaginary test product).
Arabic name: كريم اليدين روز بلوسوم
Type: hand cream in a squeeze tube with a flip-top cap, plus its tall
carton (reverse tuck end).
Size: 60 ml ℮ / 2 fl oz.
Audience: women 18–30, soft, romantic, girly, gift-able.

Mood: soft and romantic, one pink family with red line art. Combine the
uploaded pictures into OUR OWN design; never copy any of them:
- The red line-art blossoms: the illustration style. Fine hand-drawn
  red lines on soft pink. Our hero is our own line-art rose blossom with
  a long flowing stem (no characters, no people).
- The open dieline: how the design wraps the box. The stem flows from
  panel to panel, a bubbly pink band runs along the bottom, the top flap
  is designed, the text panels are neat and calm.
- The boxes: the overall mood. Soft, gentle, girly.
The logo is BBROSE.

Inside: bold berry petal flowers on pink, like the inside reference,
redrawn in our own shapes.

Front copy: BBROSE logo, "Rose Blossom", "Hand Cream / كريم اليدين",
60 ml ℮ 2 fl oz.
Back copy: Description: A soft, fast-absorbing hand cream with a gentle
rose scent. / Ingredients: Aqua, Glycerin, Butyrospermum Parkii Butter,
Cetearyl Alcohol, Parfum, Phenoxyethanol. / How to use: massage into
clean hands as often as needed. / Warnings: For external use only. Avoid
contact with eyes. / Made in UAE.

[Container type: tube; Product category: hand cream; Capacity: 60 ml; Closure: flip-top cap]"""
#: its tube as a one-colour picture paints it: pale pink on a pale pink ground, red lettering
ONE_PINK_GROUND = (240, 206, 210)
PINK_BODY, PINK_CAP, LINE_RED = (246, 216, 222), (234, 192, 202), (200, 52, 72)
#: [his answers after the fixes for design 122, (2)] the ink a picture's own size line is painted in — its own, so the
#: read finds it apart from the name: on the pink tube a deeper red, on the deep rose tube a pale gold
SIZE_RED, SIZE_GOLD = (168, 24, 44), (250, 236, 200)
# the house's own colours (the brand's canonical "Blush Core" ColorSystem): Deep Rose, Warm Gold, Warm Cream, Blush
# (the name prints in Pale Petal: Warm Cream beside the white mark is read as one ink, and the mark is then not traced —
# the path on which W11 found a jar's mark drawn off its sheet; fixed in compose_container._front_view_zone, its test in
# apps/ire/tests/test_compose_container.py)
BODY, LID, CREAM, WHITE, INK = (139, 58, 82), (203, 168, 125), (247, 221, 227), (255, 255, 255), (96, 24, 48)
PETAL = (242, 196, 206)
PALETTE = [{"hex": "#F2C4CE", "name": "Blush", "role": "Primary", "usage": "Main surfaces, hero cartons"},
           {"hex": "#F7DDE3", "name": "Pale Petal", "role": "Secondary", "usage": "Interior, secondary panels"},
           {"hex": "#8B3A52", "name": "Deep Rose", "role": "Accent", "usage": "Typography, fine detail lines"},
           {"hex": "Metallic 10122 C", "name": "Rose Gold", "role": "Metallic", "usage": "Caps, closures, foil detail"},
           {"hex": "#FAF3EC", "name": "Warm Cream", "role": "Ground", "usage": "Base packaging, backgrounds"},
           {"hex": "#CBA87D", "name": "Warm Gold", "role": "Ground", "usage": "Warm gold ground panels"}]
LOGO_RGB = (20, 20, 20)
DECOY = dict(product_id="WC-DECOY-01", name="Midnight Orchid", product_type="body lotion", category="SK", year=2026)
BACK = ("Back copy: How to use: Smooth a little over clean skin, morning and night. / Ingredients: Aqua, Glycerin, "
        "Rosa Damascena Flower Water. / Warnings: For external use only.")
BACK_SHORT = ("Back copy: How to use: Smooth over lips. / Ingredients: Aqua, Glycerin. / Warnings: External use "
              "only.")
BACK_TINY = "Back copy: How to use: Line the lips. / Ingredients: Wax, Glycerin. / Warnings: External use."
#: [his final goal, 2026-10-05, C5] a back copy no 22 mm back holds in three languages at the floors — [his correction of
#: 2026-10-07] even shrunk evenly to 3 pt (MEASURED: it stands at 3 pt from 26 mm)
BACK_LONG = ("Back copy: Description: A light rose serum that settles into the skin in seconds and leaves it soft, "
             "dewy and calm through the day. / How to use: Smooth a little over clean skin, morning and night, then "
             "follow with your moisturiser. / Ingredients: Aqua, Glycerin, Rosa Damascena Flower Water, Niacinamide, "
             "Sodium Hyaluronate, Panthenol, Allantoin, Phenoxyethanol, Ethylhexylglycerin. / Warnings: For external "
             "use only. Avoid contact with eyes. Discontinue use if irritation occurs. Keep out of reach of children.")
#: [his final goal, 2026-10-05, A] one piece of back copy: what the smallest backs hold in three languages, each language's
#: heading over its copy at the print method's 5 pt (lipstick, tin, ampoule; the long copy stops by name: tin_back_stop)
BACK_ONE = "Back copy: Ingredients: Glycerin. / Warnings: External use only."
BACK_WORDS = ("Glycerin",)                  # in both back copies: the brief's own words reach the finished file
REFERENCE_LABEL = "REFERENCE"


class StubRefused(Exception):
    """An unstubbed provider call: refused, never retried (``retry_transient`` retries only transient classes)."""


# ================================================================ the pictures

def _font(size, text=""):
    from PIL import ImageFont
    if any("\u0600" <= ch <= "\u06ff" for ch in text):
        # [his final goal, 2026-10-05, C8] Arabic painted in a face that holds it — the Latin face draws no ink for it
        return ImageFont.truetype(os.path.join(settings.BASE_DIR, "static", "fonts", "NotoNaskhArabic-Regular.ttf"), size)
    return ImageFont.truetype(FONT, size)


def paint(parts, ground=GROUND):
    """A plain-ground studio picture of the case's product, each part in its own flat colour."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), ground)
    d = ImageDraw.Draw(img)
    for p in parts:
        x0, y0, x1, y1 = p["box"]
        if p["kind"] in ("type", "mark"):
            font = _font(p["size"], p["text"])
            tw = d.textlength(p["text"], font=font)
            d.text(((x0 + x1 - tw) / 2, y0), p["text"], fill=p["colour"], font=font,
                   stroke_width=p.get("stroke", 0), stroke_fill=p["colour"])
        elif p.get("petals"):
            # a fan of petals, each a slim ellipse turned about the fan's foot
            from PIL import Image as _I
            cx, foot = (x0 + x1) / 2.0, y1
            for i in range(p["petals"]):
                leaf = _I.new("RGBA", (int(0.18 * (x1 - x0)) + 2, int(y1 - y0) + 2), (0, 0, 0, 0))
                ImageDraw.Draw(leaf).ellipse([0, 0, leaf.size[0] - 2, leaf.size[1] - 2], fill=p["colour"] + (255,))
                turned = leaf.rotate(-60 + i * 20, expand=True, center=(leaf.size[0] / 2, leaf.size[1]))
                img.paste(turned, (int(cx - turned.size[0] / 2), int(foot - turned.size[1])), turned)
        elif p.get("outline"):
            if p.get("ellipse"):
                d.ellipse([x0, y0, x1, y1], outline=p["colour"], width=p["outline"])
            else:
                d.rounded_rectangle([x0, y0, x1, y1], radius=p.get("round") or 0, outline=p["colour"],
                                    width=p["outline"])
        elif p.get("ellipse"):
            d.ellipse([x0, y0, x1, y1], fill=p["colour"])
        elif p.get("round"):
            d.rounded_rectangle([x0, y0, x1, y1], radius=p["round"], fill=p["colour"])
        else:
            d.rectangle([x0, y0, x1, y1], fill=p["colour"])
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _inside_the_rim(picture_bytes):
    """[His test blocker on design 124, 2026-10-11] a round lid stood square (``concept_outline.lid_picture``) is white
    outside its rim: read only inside it, as a reader reads a lid — a white mark is never the corners' white."""
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(picture_bytes)).convert("RGB")
    w, h = img.size
    if abs(w - h) > 2:
        return picture_bytes
    outside = Image.new("L", (w, h), 255)
    ImageDraw.Draw(outside).ellipse([1, 1, w - 2, h - 2], fill=0)
    img.paste((1, 2, 3), mask=outside)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def colour_box(picture_bytes, colour, tol=6):
    """The tight box, in the picture's own pixels, of the pixels within ``tol`` of ``colour``; None when none."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(io.BytesIO(picture_bytes)).convert("RGB")).astype(int)
    ys, xs = np.nonzero(abs(a - np.array(colour)).max(axis=2) <= tol)
    if xs.size == 0:
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def _text_size(text, width_px, height_px):
    """The largest font size whose line fits ``width_px`` within a ``height_px`` cap."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    size = int(height_px)
    while size > 10 and d.textlength(text, font=_font(size)) > width_px:
        size -= 2
    return size


def standing_parts(h_mm, w_mm, closure_share, *, name, closure_wider=False, name_share=0.6):
    """A product standing straight-on: its closure on top, its body below carrying the mark and its name."""
    s = min(900.0 / h_mm, 520.0 / w_mm)            # the whole product in frame, clear space round it
    pw, ph = w_mm * s, h_mm * s
    x0, y0 = (W - pw) / 2, (H - ph) / 2
    ch = ph * closure_share
    cw = pw * (1.04 if closure_wider else 0.72)
    bx0, by0, bx1, by1 = x0, y0 + ch, x0 + pw, y0 + ph
    bw, bh = bx1 - bx0, by1 - by0
    nsize = _text_size(name, name_share * bw, min(0.14 * bh, 96))
    msize = max(12, int(nsize * 0.55))
    r = int(min(bw, bh) * 0.08)
    return [
        dict(kind="field", name="deep rose body", colour=BODY, box=[int(bx0), int(by0), int(bx1), int(by1)], round=r),
        dict(kind="closure", name="gold closure", colour=LID,
             box=[int((W - cw) / 2), int(y0), int((W + cw) / 2), int(y0 + ch) + 1], round=max(2, int(r / 2))),
        dict(kind="mark", name="BBROSE wordmark", colour=WHITE, text="BBROSE", size=msize, layout="mark",
             box=[int(bx0), int(by0 + 0.30 * bh), int(bx1), int(by0 + 0.30 * bh + msize * 1.3)]),
        dict(kind="type", name="product name", colour=CREAM, text=name, size=nsize, layout="name",
             box=[int(bx0), int(by0 + 0.52 * bh), int(bx1), int(by0 + 0.52 * bh + nsize * 1.3)]),
    ]


def with_size_line(parts, ink, text="100 ml / 3.38 fl. oz."):
    """[His answers after the fixes for design 122, 2026-10-08, (2): "149 printed '100 ml': the drawing must always print
    my brief's size (60 ml), never the picture's text."] the product's picture printing a size of its own under its
    name, in its own ink, as 122's concept 149 printed "100 ml / 3.38 fl. oz." against its brief's 60 ml."""
    body = next(p for p in parts if p["kind"] == "field")
    name = next(p for p in parts if p["kind"] == "type")
    x0, y0, x1, y1 = body["box"]
    size = max(24, int(name["size"] * 0.75))
    top = int(y0 + 0.78 * (y1 - y0))
    return parts + [dict(kind="type", name="size line", colour=ink, text=text, size=size,
                         box=[x0, top, x1, top + int(size * 1.3)])]


def _quantities(text) -> set:
    """Each size ``text`` states, as (amount, unit): "60 ml ℮ 2 fl oz" -> {(60.0, "ml"), (2.0, "oz")}."""
    from apps.pipeline.services import concept_design_map as dm
    out = set()
    for m in re.finditer(dm.SIZE_QUANTITY, str(text), re.I):
        amount = re.match(r"\d+(?:[.,]\d+)?", m.group(0)).group(0).replace(",", ".")
        unit = re.sub(r"[^a-z]", "", m.group(0)[len(amount):].lower()).replace("floz", "oz")
        out.add((float(amount), unit))
    return out


def one_colour(parts):
    """[His test blocker on design 122] a product in one pink family with red lettering, as 122's brief asks: its body and
    its closure two pale pinks, its mark and its name red."""
    colours = {"field": PINK_BODY, "closure": PINK_CAP, "mark": LINE_RED, "type": LINE_RED}
    names = {"field": "pale pink body", "closure": "pink flip-top cap"}
    return [dict(p, colour=colours[p["kind"]], name=names.get(p["kind"], p["name"])) for p in parts]


def lid_parts(h_mm, w_mm, *, name, ellipse=False, type_only=False):
    """A face form seen from above: its lid carrying a petal window, the mark and its name — or, ``type_only``, its mark
    and its name alone ([his answer of 2026-10-05, W6: "type-only is a real design style; refuse only real placeholder
    text"]: such a lid was refused at Gate 2 as an unresolved placeholder, the wiring check's finding W6)."""
    s = min(700.0 / h_mm, 560.0 / w_mm)
    pw, ph = w_mm * s, h_mm * s
    x0, y0 = (W - pw) / 2, (H - ph) / 2
    lid = [int(x0), int(y0), int(x0 + pw), int(y0 + ph)]
    nsize = _text_size(name, 0.6 * pw, min(0.12 * ph, 110))
    msize = max(12, int(nsize * 0.55))
    lid_part = dict(kind="field", name="deep rose lid", colour=BODY, box=lid, layout="surface")
    if ellipse:
        lid_part["ellipse"] = True
    else:
        lid_part["round"] = int(min(pw, ph) * 0.12)
    if type_only:
        return [lid_part,
                dict(kind="mark", name="BBROSE wordmark", colour=WHITE, text="BBROSE", size=msize, layout="mark",
                     box=[lid[0], int(y0 + 0.30 * ph), lid[2], int(y0 + 0.30 * ph + msize * 1.3)]),
                dict(kind="type", name="product name", colour=CREAM, text=name, size=nsize, layout="name",
                     box=[lid[0], int(y0 + 0.48 * ph), lid[2], int(y0 + 0.48 * ph + nsize * 1.3)])]
    window = dict(kind="window", name="oval window", colour=LID, layout="window", outline=5, ellipse=True,
                  box=[int(x0 + 0.30 * pw), int(y0 + 0.08 * ph), int(x0 + 0.70 * pw), int(y0 + 0.30 * ph)])
    petals = dict(kind="motif", name="blush petal fan", colour=PETAL, layout="motif", petals=7,
                  box=[int(x0 + 0.38 * pw), int(y0 + 0.12 * ph), int(x0 + 0.62 * pw), int(y0 + 0.26 * ph)])
    return [lid_part, window, petals,
            dict(kind="mark", name="BBROSE wordmark", colour=WHITE, text="BBROSE", size=msize, layout="mark",
                 box=[lid[0], int(y0 + 0.32 * ph), lid[2], int(y0 + 0.32 * ph + msize * 1.3)]),
            dict(kind="type", name="product name", colour=CREAM, text=name, size=nsize, layout="name",
                 box=[lid[0], int(y0 + 0.50 * ph), lid[2], int(y0 + 0.50 * ph + nsize * 1.3)])]


#: [his final goal, 2026-10-05, C8] the foot row's two inks — each part of the picture is found by its own colour, and
#: the map's reading merges inks nearer than 10 ΔE: a teal and an olive no other part prints
FOOT_EN, FOOT_AR = (20, 100, 110), (110, 110, 20)


def foot_parts():
    """[His final goal, 2026-10-05, C8: "A LINE THAT BREAKS DROPS ITS SEPARATOR. When "LIP GLOSS · ملمّع الشفاه" breaks
    onto two lines, the "·" goes."] 119's foot row: "LIP GLOSS" and its Arabic side by side at the carton's foot."""
    return [dict(kind="type", name="LIP GLOSS descriptor", colour=FOOT_EN, text="LIP GLOSS", size=22,
                 box=[330, 1236, 500, 1262]),
            dict(kind="type", name="Arabic descriptor", colour=FOOT_AR, text="ملمّع الشفاه", size=22, stroke=1,
                 box=[520, 1236, 690, 1262])]


def carton_parts(name, stripe="field"):
    """A folding carton, its front panel square to the camera: a Deep Rose ground, a second field across it carrying
    the name (the path the wiring check's finding W3 opened), the mark above — or, ``stripe="band"``, the same stripe
    read as a band ([his answer of 2026-10-05, W2: "build it. Plain stripes are basic."]: a plain stripe read as a
    "band" stopped at Gate 1, the band tracer knowing only a band that ends in a gold edge — the finding W2)."""
    nsize = _text_size(name, 340, 70)
    return [dict(kind="field", name="deep rose ground", colour=BODY, box=[312, 300, 712, 1300]),
            dict(kind=stripe, name="cream stripe", colour=CREAM, box=[312, 760, 712, 900]),
            dict(kind="type", name="product name", colour=INK, text=name, size=nsize, box=[312, 795, 712, 880]),
            dict(kind="mark", name="BBROSE wordmark", colour=WHITE, text="BBROSE", size=40, box=[312, 400, 712, 455])]


# ================================================================ the cases

#: [His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), A1] a flat redraw as the image model gives it: line-art roses, their petals
#: hatched, stems and veined leaves, in one raspberry ink with its own thick-and-thin, on a flat blush ground
FLAT_122 = ("#C2185B", "#F6DCE3")


def flat_art(ink, ground, size=(1024, 1536), seed=122, broken=False, single=False):
    """Flat line art of roses — each rose a spiral of petals, its petals hatched, on a stem with veined leaves — drawn
    with strokes that thicken and thin; ``single``, one rose alone, centred and large (a small motif's flat redraw);
    ``broken``, the same with its strokes cut every few pixels (a motif in fragments)."""
    import random

    import cv2
    import numpy as np
    rng = random.Random(seed)

    def bgr(hx):
        return int(hx[5:7], 16), int(hx[3:5], 16), int(hx[1:3], 16)
    w, h = size
    img = np.full((h, w, 3), bgr(ground), np.uint8)
    col = bgr(ink)
    k = 3.0 if single else 1.0
    centres = [(w // 2, h // 2 - 150)] if single else [
        (cx + rng.randint(-20, 20), cy + rng.randint(-20, 20))
        for cy in range(140, h, 300) for cx in range(150 + (cy // 300 % 2) * 120, w, 260)]
    for cx, cy in centres:
        r = int(rng.randint(55, 75) * k)
        for ring in range(5):                                       # the petals: arcs that thicken and thin
            rr = int(r * (1 - ring * 0.17))
            for a0 in range(0, 360, 72):
                cv2.ellipse(img, (cx, cy), (rr, int(rr * 0.8)), (ring * 25) % 360, a0, a0 + 55, col,
                            int((2 + (ring % 3) * 2) * k), cv2.LINE_AA)
        for j in range(-3, 4):                                      # the hatching inside a petal
            x = cx + int(r * 0.55) + int(j * 7 * k)
            cv2.line(img, (x, cy - int(18 * k)), (x + int(6 * k), cy + int(18 * k)), col, int(2 * k), cv2.LINE_AA)
        pts = np.array([[cx, cy + r], [cx - int(10 * k), cy + r + int(60 * k)], [cx + int(8 * k), cy + r + int(120 * k)]],
                       np.int32)
        cv2.polylines(img, [pts], False, col, int(5 * k), cv2.LINE_AA)    # the stem
        leaf = (cx + int(34 * k), cy + r + int(70 * k))
        cv2.ellipse(img, leaf, (int(30 * k), int(13 * k)), 30, 0, 360, col, int(3 * k), cv2.LINE_AA)   # a leaf
        cv2.line(img, (leaf[0] - int(24 * k), leaf[1] - int(12 * k)), (leaf[0] + int(24 * k), leaf[1] + int(12 * k)),
                 col, int(2 * k), cv2.LINE_AA)                      # and its vein
    if broken:
        img[:, ::6] = bgr(ground)
        img[::6, :] = bgr(ground)
    return cv2.imencode(".png", img)[1].tobytes()


def _directions_for(noun):
    """The planner's one valid document (``direction_fixtures``), in the case's own product words."""
    from apps.pipeline.tests.direction_fixtures import valid_document
    text = json.dumps(valid_document())
    text = text.replace("tall slim serum carton", "the " + noun).replace("serum carton", noun)
    return json.loads(re.sub(r"\bcarton\b", noun, text))


_SIGS = {"typography_signature": "bold sans name, centred", "composition_signature": "centred column",
         "motif_signature": "no decorative motif", "cap_body_signature": "a Warm Gold closure on a Deep Rose body",
         "decoration_zone_signature": "centred front", "color_field_signature": "a Deep Rose body, Pale Petal type",
         "finish_signature": "gloss"}


def _product(sku, name, product_type, **dims):
    return dict(product_id=sku, name=name, product_type=product_type, category="SK", year=2026, **dims)


#: [His test blocker on design 122 at reconstruction, 2026-10-08, item 4] the shape he confirmed for 122 at 09:55:57Z, as
#: its record holds it ("container_confirmed_profile")
HIS_122_CONFIRMED = dict(archetype="tube", variant="standard", cap_style="flip", height_mm=120.0, width_mm=35.0,
                         depth_mm=20.0)
#: … and the name 122 is drawn with: started from his brief alone, it is named by its own reading of the brief, "Rose
#: Blossom Hand Cream" (``CreativeBrief.design_intent["brief"]["product_name"]``); a record named so draws it alike and
#: keeps the SKU Gate 2's print data asks for — the case's own record named it "Rose Blossom", the very line 149 sets,
#: and hid the stop
HIS_122_PRODUCT = _product("WC-CP-122", "Rose Blossom Hand Cream", "hand cream")


#: [His correction of 2026-10-07: "Floor: 3 pt."] the pencil was a NAMED STOP (the acceptance-time list's entries 14 and
#: 15, §BH70(1)): CONTAINER_MINIMUM_TEXT_SIZE_FAILED. MEASURED at the correction: its front's name stands at 13.5 pt;
#: what stopped it was its back label, set at 5 pt under the 6 pt of a hot stamp the machine proposed and nobody
#: confirmed (its back carries two methods, so the panel takes the 5 pt fallback). A label's floor is now his 3 pt unless
#: a CONFIRMED method records more (``back_panel.label_floor_pt``, the executor's reading, his to veto): it runs to the end




#: [his goal of 2026-10-06, item 1: "the Container type I choose ALWAYS wins ... Never a guess from picture readings or
#: word order"] every form's brief names, in a sentence of its own, ANOTHER form that ``FORM_WORDS`` lists before it — a
#: jar's pot before a tube, a sachet before a jar, a compact before a tin or a sachet — as design 120's field named a jar
#: before its brief's tube: the form chosen must hold all the way through (detector ``container_type``)
DECOY_SENTENCE = {"jar": "It replaces the pot it was sold in before.", "sachet": "Its sample sachet comes later.",
                  "compact": "It sits beside our pressed-powder compact."}
DECOY_OF = dict({f: "jar" for f in ("bottle", "tube", "lipstick", "mascara", "pencil", "oval_stick", "aerosol",
                                    "ampoule", "compact")}, jar="sachet", tin="compact", sachet="compact")
DECOY_WORDS = {"jar": ("jar", "pot"), "sachet": ("sachet",), "compact": ("compact", "palette")}


#: [his goal of 2026-10-06, item 8] the container whose back the old measuring ran into its safe margin (chosen by
#: measuring every form with that measuring planted back)
PLANTED_BACK_CASE = "bottle"


def _form(key, archetype, variant, cap, h, w, d, *, noun, product_type, name="Rose Velvet", closure_share=0.24,
          closure_wider=False, extra=None, face=False, ellipse=False, stop=None, name_share=0.6, back=BACK, type_only=False,
          known=None):
    from apps.pipeline.targets.container import archetypes as A
    parts = (lid_parts(h, w, name=name, ellipse=ellipse, type_only=type_only) if face
             else standing_parts(h, w, closure_share, name=name, closure_wider=closure_wider, name_share=name_share))
    profile = dict(archetype=archetype, variant=variant, cap_style=cap, height_mm=h, width_mm=w, depth_mm=d)
    profile.update(extra or {})
    brief = ("A %s for %s. %s\n\n%s\n\n[Container type: %s; Closure: %s]"
             % (noun, name, DECOY_SENTENCE[DECOY_OF[archetype]], back, archetype.replace("_", " ").title(),
                dict(A.closures_of(archetype))[cap]))
    return key, dict(kind="container", key=key, target="product_container", form=archetype, noun=noun, face=face,
                     type_only=type_only,
                     product=_product("WC-%s-01" % key.upper()[:10], name, product_type), brief=brief,
                     prompt_words="a %s with a gold closure and a deep rose body, straight-on on a plain ground" % noun,
                     signatures=_SIGS, profile=profile, parts=parts, **({"stop": stop} if stop else {}),
                     **({"known": known} if known else {}))


def build_cases():
    cases = dict([
        _form("bottle", "bottle", "cylindrical", "pump", 140, 45, 45, noun="pump bottle", product_type="body lotion",
              extra=dict(neck_ratio=0.42)),
        # [his goal of 2026-10-06, item 8] measured in the faces it is drawn in, the long back copy needs 62.75 mm of its
        # 60 mm at 5 pt in the dropper's 22 mm column — it stops by name now (tin_back_stop keeps that path); this case
        # runs to the end with the short copy its column holds
        _form("dropper", "bottle", "cylindrical", "dropper", 110, 40, 40, noun="dropper bottle",
              product_type="face serum", extra=dict(neck_ratio=0.42), back=BACK_SHORT),
        # [his answer of 2026-10-05, W10: "a jar's back copy goes on the back of its wrap label ... Never nowhere."] the
        # jar's brief's back copy prints on the back of its wrap label — the brief-copy detector reads it there
        _form("jar", "jar", "standard", "lid", 70, 60, 60, noun="jar", product_type="face cream", closure_share=0.26,
              closure_wider=False, name_share=0.45),
        # [his answer of 2026-10-05, W7: "build it. Squat jars (creams, balms) are core products."] a jar wider than tall
        # (60 mm tall, 70 mm across), read standing as the picture stands it and run to the end
        _form("jar_squat", "jar", "standard", "lid", 60, 70, 70, noun="jar", product_type="face cream",
              closure_share=0.26, closure_wider=False, name_share=0.45),
        # [his answer of 2026-10-05, W5: "fix the artboard check so tubes pass"] the tube runs to the end: its sheet is
        # read against the width it is drawn at (its flat end), and Gate 2 accepts it
        _form("tube", "tube", "standard", "screw", 150, 40, 22, noun="tube", product_type="hand cream",
              closure_share=0.14, name_share=0.8),
        _form("compact", "compact", "rounded_rect", "clasp", 95, 110, 18, noun="compact", product_type="pressed powder",
              face=True),
        # [his final goal, 2026-10-05, A: container backs trilingual] the small forms carry the short back copy their backs
        # hold in three languages (the long copy stops by name: tin_back_stop)
        _form("lipstick", "lipstick", "round", "cap", 85, 38, 38, noun="lipstick", product_type="lipstick",
              name="Rosa", closure_share=0.40, back=BACK_ONE),
        _form("mascara", "mascara", "round", "wand", 130, 28, 28, noun="mascara", product_type="mascara",
              name="Rosa", closure_share=0.45, back=BACK_SHORT),
        _form("pencil", "pencil", "sharpened", "cap", 150, 20, 20, noun="pencil", product_type="lip liner pencil",
              name="Rosa", closure_share=0.20, name_share=0.9, back=BACK_TINY),
        _form("tin", "tin", "round", "slip", 60, 60, 18, noun="tin", product_type="lip balm", face=True, ellipse=True,
              back=BACK_ONE),
        # [his answer of 2026-10-05, W6: "type-only is a real design style"] a tin whose lid prints its mark and its
        # name and nothing else, run to the end
        _form("tin_type_only", "tin", "round", "slip", 60, 60, 18, noun="tin", product_type="lip balm", face=True,
              ellipse=True, type_only=True, back=BACK_ONE),
        # [his final goal, A; his correction of 2026-10-07: "Only if it still doesn't fit at 3 pt, stop and tell me"] a
        # tin whose long back copy cannot stand in three languages on its 28 mm back even shrunk evenly to 3 pt (its
        # print method the machine's proposal, never confirmed): held at Gate 2 by name — never cut, never moved
        _form("tin_back_stop", "tin", "round", "slip", 60, 60, 18, noun="tin", product_type="lip balm", face=True,
              ellipse=True, back=BACK_LONG, stop=dict(codes=["CONTAINER_BACK_COPY_DOES_NOT_FIT_THIS_BODY"])),
        _form("sachet", "sachet", "three_side", "tear_notch", 150, 110, 3, noun="sachet", product_type="sheet mask",
              closure_share=0.06),
        _form("oval_stick", "oval_stick", "oval", "snap_cap", 120, 54, 32, noun="stick", product_type="deodorant stick",
              closure_share=0.30),
        _form("aerosol", "aerosol", "straight", "overcap", 190, 62, 62, noun="spray can", product_type="dry shampoo",
              closure_share=0.20),
        _form("ampoule", "ampoule", "vial", "stopper", 80, 24, 24, noun="vial", product_type="serum ampoule",
              name="Rosa", closure_share=0.22, back=BACK_ONE),
    ])
    cases["palette"] = dict(cases["compact"], key="palette", target="palette",
                            product=_product("WC-PALETTE-01", "Rose Velvet", "eyeshadow palette"),
                            brief="An eyeshadow palette for Rose Velvet.\n\n" + BACK)
    carton = dict(kind="carton", target="packaging", form="carton", noun="carton",
                  product=_product("WC-CARTON-01", "Rose Velvet", "face serum", width_mm=35, depth_mm=30,
                                   height_mm=100),
                  brief="A carton for Rose Velvet, a face serum.\n\n" + BACK,
                  prompt_words="a folding carton, front panel square to the camera, deep rose with a cream stripe",
                  face_colour=BODY, parts=carton_parts("Rose Velvet"))
    cases["packaging"] = dict(carton, key="packaging")
    # [his goal of 2026-10-10, item 1: "NO planner check ever stops a design (not only "not distinct")"] a carton whose
    # planner writes a printed photograph into a direction, twice: shown with its plain note, and run to the end
    noted = _directions_for("carton")
    noted["directions"][1]["imagery_approach"] = "a full-bleed photograph of real peonies printed across the front"
    cases["planner_note"] = dict(carton, key="planner_note", directions=noted,
                                 warnings_allowed=("still failed a check",))
    # [his answer of 2026-10-05, W2] the carton's stripe read as a band, run to the end
    cases["carton_stripe"] = dict(carton, key="carton_stripe", parts=carton_parts("Rose Velvet", stripe="band"))
    # [his final goal, 2026-10-05, C8] a 22 mm carton (119's) whose foot row cannot stand on one line inside its safe
    # margin at the print floor: it breaks onto two, and the "·" between "LIP GLOSS" and the Arabic goes with the break
    cases["carton_foot"] = dict(carton, key="carton_foot", parts=carton_parts("Rose Velvet") + foot_parts(),
                                product=_product("WC-CARTON-02", "Rose Velvet", "face serum", width_mm=22,
                                                 depth_mm=22, height_mm=105),
                                brief=('A carton for Rose Velvet, a face serum.\n\nCarton front: "LIP GLOSS · ملمّع '
                                       'الشفاه"\n\n' + BACK))
    # [his second goal of 2026-10-06 (transcribed at c34a518), item 1: "ALL LABEL INFORMATION GOES ON THE BACK STICKER";
    # his correction of 2026-10-07: "the text gets SMALLER ... Never widen the carton for text ... Shrink the whole label
    # evenly until everything fits ... Floor: 3 pt."] a 22 mm carton whose label does not stand on its back's sticker in
    # three languages at 5 pt: drawn at the 22 mm he confirmed, the whole label shrunk evenly (MEASURED: to 4 pt), every
    # word on the sticker. The long copy this case carried (BACK_LONG) does not stand on 22 mm even at 3 pt: it now
    # stops, and the planted fault test_l1_the_label_stopped_off_the_sticker_again keeps a stop's path
    cases["carton_label_shrunk"] = dict(carton, key="carton_label_shrunk",
                                         product=_product("WC-CARTON-03", "Rose Velvet", "face serum", width_mm=22,
                                                          depth_mm=22, height_mm=105),
                                         brief="A carton for Rose Velvet, a face serum.\n\n" + BACK,
                                         statuses=CARTON_STATUSES)
    # [his final goal, 2026-10-05, B1: "INSIDE AND TOP PRINTING"] a carton with an inside reference picture and its
    # brief's "Inside:" words: the inside drawn in vector on the second artboard, the picture never sent to a concept
    cases["carton_inside"] = dict(carton, key="carton_inside",
                                  brief=("A carton for Rose Velvet, a face serum.\n\nInside: thin diagonal stripes, "
                                         "close together.\n\n" + BACK),
                                  inside_pictures=[paint([{"kind": "ground", "colour": (90, 20, 40),
                                                           "box": (0, 0, 1024, 1024)}])],
                                  expect_inside={"pattern": "stripes", "direction": "diagonal", "density": "dense",
                                                 "source": "his inside reference and his brief's words"})
    # [his goal of 2026-10-06, items 10–12; his second goal of the day, item 1; his correction of 2026-10-07] 119's
    # carton: 22 mm, a four-word name, its inside printing the concept's own motif, its long label shrunk evenly on the
    # back's sticker (where it was printed inside, then widened for); its title on one or two lines; its sides designed;
    # its flaps carrying the motif
    cases["carton_title"] = dict(cases["carton_label_shrunk"], key="carton_title",
                                 product=_product("WC-CARTON-05", "Rose Glaze Lip Gloss", "lip gloss", width_mm=22,
                                                  depth_mm=22, height_mm=105),
                                 # [his correction of 2026-10-07] the copy a 22 mm back holds shrunk evenly (BACK_LONG
                                 # stops there even at 3 pt)
                                 brief=("A carton for Rose Glaze Lip Gloss, a lip gloss in a wand vial.\n\nInside: the "
                                        "concept's own motif.\n\n" + BACK),
                                 parts=carton_parts("Rose Glaze"))
    # [his final goal, 2026-10-05, B3] his custom sticker, as his brief's words say it, chosen at the size step
    cases["carton_sticker"] = dict(carton, key="carton_sticker",
                                   brief="A carton for Rose Velvet, a face serum.\n\nSticker: a dark arch with a thin "
                                         "border.\n\n" + BACK,
                                   size_choices={"back_info": "custom"},
                                   expect_back_info={"mode": "custom", "shape": "arch", "fill": "dark",
                                                     "border": "thin"})
    cases["gift_set"] = dict(carton, key="gift_set", target="gift_set", noun="gift set carton",
                             product=_product("WC-GIFT-01", "Rose Velvet", "face serum", width_mm=33, depth_mm=33,
                                              height_mm=96),
                             brief="A gift set of three 30 ml Rose Velvet face serums.\n\n" + BACK)
    for target in ("marketing_material", "social_media", "exhibition_booth", "display_stand"):
        cases[target] = dict(kind="artwork", key=target, target=target, form=target, noun="poster",
                             # [his answer of 2026-10-05, W9: "let the copy box grow to fit; no hold for under
                             # 2 mm"] a two-word name that wraps, and its category line: the square post's and the
                             # header card's copy boxes were 0.17 mm and 1.405 mm short of them, and held at Gate 2
                             product=_product("WC-%s" % target.upper()[:12], "Rose Velvet", "face serum",
                                              width_mm=35, depth_mm=30, height_mm=100),
                             brief="Artwork for Rose Velvet, a face serum.",
                             prompt_words="an editorial key visual of the Rose Velvet serum on a plain ground",
                             parts=standing_parts(110, 40, 0.24, name="Rose Velvet"))
    vial = cases["mascara"]
    cases["complete_product"] = dict(kind="composite", key="complete_product", target="complete_product",
                                     form="mascara", noun="wand vial",
                                     product=_product("WC-CP-01", "Rosa", "lip oil"),
                                     brief=("A wand vial for Rosa, a lip oil, and its carton. %s\n\n%s\n\n"
                                            "[Container type: Mascara; Closure: Doe-foot Applicator]"
                                            % (DECOY_SENTENCE["jar"], BACK_SHORT)),
                                     prompt_words=vial["prompt_words"].replace("mascara", "wand vial"),
                                     signatures=_SIGS, profile=dict(vial["profile"], cap_style="doe_foot"),
                                     parts=vial["parts"], carton=dict(carton, parts=carton_parts("Rosa")))
    # [his test blocker on design 122, 2026-10-07: "Add 2–4 to the wiring check with a real one-colour brief."] 122
    # itself: a Complete Product, its tube and its carton in one project, on its own brief word for word ("one pink family
    # with red line art"), its tube painted as its concepts came — a pale pink tube on a pale pink ground, red lettering.
    # The trace cannot cut it from that ground, so each concept is redrawn on a deep charcoal backdrop before it is shown,
    # read again, and run to the end
    tube = cases["tube"]
    cases["complete_product_one_colour"] = dict(
        kind="composite", key="complete_product_one_colour", target="complete_product", form="tube", noun="tube",
        product=_product("WC-CP-122", "Rose Blossom", "hand cream"), brief=BRIEF_122, ground=ONE_PINK_GROUND,
        prompt_words="a pale pink tube with red line-art lettering, straight-on on a plain pale pink ground",
        signatures=_SIGS, profile=dict(tube["profile"], cap_style="flip"),
        # [his answers after the fixes for design 122, (2)] its picture prints 149's own "100 ml / 3.38 fl. oz."
        parts=with_size_line(one_colour(standing_parts(150, 40, 0.14, name="Rose Blossom", name_share=0.8)), SIZE_RED),
        carton=dict(carton, parts=carton_parts("Rose Blossom")))
    return cases


# ================================================================ the provider boundary

def _response(payload):
    block = mock.MagicMock()
    block.type = "text"
    block.text = payload if isinstance(payload, str) else json.dumps(payload)
    resp = mock.MagicMock()
    resp.content = [block]
    resp.usage = mock.MagicMock(input_tokens=100, output_tokens=100, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0)
    resp.id, resp._request_id = "msg_wiring", "req_wiring"
    resp.stop_reason = "end_turn"
    return resp


def _said(kw):
    """Every text a model call was given — its system and its messages — as one string."""
    out = []

    def walk(v):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k in ("text", "content", "system") or not isinstance(x, str):
                    walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
    walk({"system": kw.get("system"), "messages": kw.get("messages")})
    return "\n".join(out)


def _operation_of_frames():
    """The ``operation`` its caller passed to ``claude_service.call_claude`` (read from that frame), or, for a caller
    that opens the client itself, ``direct:<module>``."""
    from apps.pipeline.services import claude_service as cs
    code = getattr(cs.call_claude, "__wrapped__", cs.call_claude).__code__
    f, first_app = sys._getframe(2), None
    while f is not None:
        if f.f_code is code:
            return f.f_locals.get("operation") or "?"
        mod = f.f_globals.get("__name__", "")
        if (first_app is None and mod.startswith("apps.") and "wiring" not in mod
                and mod != "apps.pipeline.services.spend_reservation"):
            first_app = mod
        f = f.f_back
    return "direct:%s" % first_app


def _writes_label(task, kind) -> bool:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (7).] Whether this design's brief and product record leave a
    piece of its back label empty — read as the engine reads them (a carton's panel copy, a container's back)."""
    from apps.pipeline.services import label_copy as lc
    if kind == "carton":
        from apps.pipeline.services.panel_info import build_panel_info
        info = build_panel_info(task)
        return any(not str(info.get(f) or "").strip() for f in lc.FIELDS)
    from apps.pipeline.targets.container import label_back
    return bool(label_back(task, {})["written"])


#: [his goal of 2026-10-10, item 3] the open web's two finds for a case that searches for pictures: its own product's
#: picture and another product's, each told apart by its colour when it is read
TREND_FINDS = {"trend-own": ((236, 170, 200), "own"), "trend-other": ((120, 200, 210), "lip gloss")}


def _trend_png(rgb, seed):
    """A trend picture of a design's size (noise round ``rgb`` does not compress)."""
    import random

    from PIL import Image
    rnd = random.Random(seed)
    img = Image.new("RGB", (160, 120))
    img.putdata([tuple(max(0, min(255, c + rnd.randint(-18, 18))) for c in rgb) for _ in range(160 * 120)])
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


class Harness:
    """One case's fake providers, the pictures they return and every call they answered."""

    def __init__(self, case, test):
        self.case, self.test = case, test
        self.calls: list = []
        self.refused: list = []
        self.prompts: list = []              # (the stage's own words, the prompt the image model was sent)
        self.sent: list = []                 # the files every image call was sent
        self.stage_case = case               # a composite's carton stage answers from its own picture
        self.next_stage = None               # [his final goal, B4] the stage armed to answer once its design runs
        self.asks: dict = {}                 # [his goal of 2026-10-06, item 1] each paid call's words, by operation
        self.queries: list = []              # …and each trend search's words
        case.setdefault("directions", _directions_for(case["noun"]))
        self.picture = paint(case["parts"], case.get("ground", GROUND))
        # [his test blocker on design 122, 2026-10-07, item 2] a concept redrawn so it can be read: the same parts on the
        # backdrop the redraw asks for — or on its own ground again, where a case's redraw fails too
        self.redrawn = paint(case["parts"], case.get("redraw_ground", REDRAW_GROUND))
        self.redraws = 0
        self.flat = flat_art(*FLAT_122)
        self.flats = 0
        self.layouts = 0
        self.sheet = None
        self.queue = list(case.get("pictures") or [])

    def to_stage(self, stage_case):
        self.stage_case = stage_case
        stage_case.setdefault("directions", _directions_for(stage_case["noun"]))
        self.picture = paint(stage_case["parts"], stage_case.get("ground", GROUND))
        self.redrawn = paint(stage_case["parts"], stage_case.get("redraw_ground", REDRAW_GROUND))

    def _follow(self):
        """[His final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away."] a composite's next
        stage begins inside the request that approves the one before it — its pictures are drawn there now — so the
        stubs answer as that stage from its design's first call (the ledger's design, by its target)."""
        if self.next_stage is None:
            return
        from apps.pipeline.services.cost_ledger import _current_task
        task = _current_task.get()
        if task is not None and getattr(task, "design_target", None) == self.next_stage["target"]:
            self.to_stage(self.next_stage)
            self.next_stage = None

    # -- Anthropic
    def create(self, **kw):
        self._follow()
        op = _operation_of_frames()
        self.calls.append(op)
        self.asks.setdefault(op, []).append(_said(kw))
        answer = getattr(self, "answer_" + re.sub(r"[^a-z0-9]", "_", op.lower()), None)
        if answer is None:
            self.refused.append(op)
            raise StubRefused("the wiring check has no answer for %r" % op)
        return _response(answer(kw))

    def answer_creative_directions(self, kw):
        return copy.deepcopy(self.stage_case["directions"])

    def answer_image_prompts(self, kw):
        # [his final goal, 2026-10-05, B4] the first concepts: one prompt for each planned direction, its id echoed;
        # three variations of one chosen direction where that is what is asked
        planned = self.stage_case["directions"]["directions"]
        asked = json.dumps(kw.get("messages") or "")
        one = "for the single selected direction" in asked
        return {"prompts": [{"direction_id": (planned[0] if one else d)["direction_id"],
                             "direction_name": (planned[0] if one else d)["name"],
                             "full_prompt": "%s — variation %d: %s" % ((planned[0] if one else d)["name"], i + 1,
                                                                      self.stage_case["prompt_words"]),
                             "aspect_ratio": "2:3", "notes": ""} for i, d in enumerate(planned[:3])]}

    def answer_container_gate1_variations(self, kw):
        from apps.pipeline.services import container_gate1 as cg1
        # [his final goal, 2026-10-05, B4] the first concepts are drawn inside Start itself, before its answer names the
        # design: the design being made is the newest
        from apps.pipeline.models import DesignTask
        task = self.test.current_task() if self.test._task_id else DesignTask.objects.order_by("-pk").first()
        plan = getattr(task, "concept_influence_plan", None)
        approved = list((plan.approved_reference_ids if plan is not None else None) or [])
        out = []
        for n, vid in enumerate(cg1.CONTAINER_VARIATION_IDENTITIES):
            v = {f: "%s — variant %d" % (self.stage_case["signatures"][f], n) for f in _SIGS}
            if self.stage_case.get("type_only"):
                # [W6] a type-only lid: its words name no motif and no window, in three wordings
                v["motif_signature"] = ("no decorative motif — the mark and the name alone",
                                        "no ornament: only the mark and the name",
                                        "type only, no motif or window")[n]
                v["decoration_zone_signature"] = "the name and the mark centred on the lid — variant %d" % n
                v["color_field_signature"] = "a Deep Rose lid, Pale Petal type — variant %d" % n
            elif self.stage_case.get("face"):
                # a lid's words name its ring, in three wordings
                v["motif_signature"] = ("seven blush petals fanned in an oval window above the name",
                                        "a fan of seven blush petals inside an oval window over the name",
                                        "seven slender blush petals in a fan within an oval window above the name")[n]
                v["decoration_zone_signature"] = "an oval window above the name — variant %d" % n
                v["color_field_signature"] = ("a Deep Rose lid, a Warm Gold oval frame, Blush petals, Pale Petal "
                                              "type — variant %d" % n)
            else:
                # the three must differ on every axis; each says "no motif" in its own words
                v["motif_signature"] = ("no decorative motif", "no decorative motif or pattern",
                                        "no decorative motif, no ornament")[n]
            if self.stage_case.get("type_only"):
                # [W6] its own concept names, slot letter first (the contract's form): none names a motif
                vid = ("A_TYPE_ONLY", "B_NAME_AND_MARK", "C_PLAIN_LETTERS")[n]
            # [his final goal, B4] the three planned directions, one variation each, in slot order
            v["direction_id"] = self.stage_case["directions"]["directions"][n]["direction_id"]
            v.update(variation_id=vid, title=vid, native_reconstruction_plan="live type and vector fields",
                     prompt=" ".join([self.stage_case["prompt_words"]] * 3), reference_ids=list(approved[:1]))
            out.append(v)
        return {"schema_version": cg1.CONTAINER_GATE1_SCHEMA, "approved_reference_ids": approved,
                "influence_plan_hash": getattr(plan, "plan_hash", "") or "", "variations": out}

    def answer_product_identification(self, kw):
        p = self.stage_case["product"]
        return {"name": p["name"], "category": p["category"], "product_type": p["product_type"],
                "physical_format": "", "required_copy": [], "preferred_colors": [], "prohibited_colors": [],
                "prohibited_motifs": [], "production_constraints": []}

    def answer_trend_brief(self, kw):
        # [his goal for the pitch, 2026-10-15, A (1)] the trend brief, written from the board's numbered sources
        return {"headline": "Soft-touch bodies with one lacquered accent", "whats_new": "Matte meets a single gloss.",
                "colours": ["butter yellow with cocoa [1]"], "type": ["wide grotesk capitals [1]"],
                "materials": ["soft-touch body [1]"], "illustration": ["fine line drawings [1]"],
                "layouts": ["name stacked low [1]"], "sources_used": [1]}

    def answer_designers_eye(self, kw):
        # [his goal for the pitch, 2026-10-15, B (5)] the designer's eye, the drawing beside its concept
        return {"matches": True, "summary": "the drawing matches its concept", "differences": []}

    def answer_qa_vision_review(self, kw):
        return critique(9)

    def answer_direct_apps_pipeline_services_inside_read(self, kw):
        # [his final goal, 2026-10-05, B1] an inside reference read for its pattern and style
        return {"pattern": "stripes", "direction": "diagonal", "density": "dense", "tone": "dark", "motif_words": "",
                "style": "thin diagonal pinstripes set close together", "take": "close diagonal pinstripes",
                "seen_not_taken": []}

    def answer_direct_apps_pipeline_services_inspiration(self, kw):
        # [his goal of 2026-10-10, item 3] the trend reader: what a picture shows, its product told by its colour
        from PIL import Image
        block = kw["messages"][0]["content"][0]
        img = Image.open(io.BytesIO(base64.b64decode(block["source"]["data"]))).convert("RGB")
        mean = [sum(px[i] for px in img.getdata()) / float(img.width * img.height) for i in range(3)]
        rgb, form = min(TREND_FINDS.values(), key=lambda f: sum((a - b) ** 2 for a, b in zip(f[0], mean)))
        return {"layout": "one product centred", "mood": "soft", "finish": "matte", "type_style": "no type",
                "colour_words": "soft pastels", "take": "a soft centred product", "seen_not_taken": [],
                "shows": "packaging design", "product_kind": "beauty or personal care",
                "product_form": self.stage_case["trend_product"] if form == "own" else form}

    def answer_label_copy_writing(self, kw):
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the label's pieces the brief
        # leaves empty, written for the product's type — each asked field, in the label's own register
        asked = json.loads(kw["messages"][0]["content"].rsplit("Write these fields: ", 1)[1])
        words = {"description": "A soft cream for every day.", "how_to_use": "Smooth over clean skin.",
                 "ingredients": "Aqua, Glycerin, Tocopherol, Phenoxyethanol.",
                 "warnings": "For external use only. Keep out of reach of children."}
        return {k: words[k] for k in asked}

    def answer_panel_translation(self, kw):
        src = json.loads(kw["messages"][0]["content"].split("\n", 1)[1])
        return {"es": {k: "ES " + v for k, v in src.items()}, "ar": {k: "عربي " + v for k, v in src.items()}}

    @staticmethod
    def _picture_sent(kw):
        content = kw["messages"][0]["content"]
        return base64.b64decode(next(b for b in content if b.get("type") == "image")["source"]["data"])

    def answer_container_design_map_parts(self, kw):
        pic, system = self._picture_sent(kw), kw["system"][0]["text"]
        carton = "CARTON" in system
        # [his test blocker on design 124, 2026-10-11, (2): "ONE ENGINE"] a compact's lid, read stood square: its window
        # and its motif the scene its art draws whole
        lid = "LID of a cosmetic PALETTE" in system
        if lid:
            pic = _inside_the_rim(pic)
        parts = []
        for p in self.stage_case["parts"]:
            box = colour_box(pic, p["colour"])
            if box is None or ((carton or lid) and p["kind"] == "closure"):
                continue
            kind = "illustration" if lid and p["kind"] in ("window", "motif") else p["kind"]
            part = {"kind": kind, "name": p["name"], "box": box, "finish": "none", "confidence": 0.9}
            if p["kind"] in ("type", "mark"):
                part["seen_text"] = p["text"]
            if p["kind"] == "type":
                part.update(lettering="sans", rotation=0)
            parts.append(part)
        out = {"parts": parts, "light": [], "notes": "wiring check oracle"}
        if carton:
            out["face"] = colour_box(pic, self.stage_case["face_colour"])
        return out

    def answer_container_concept_layout(self, kw):
        pic = self._picture_sent(kw)
        surface = next(p for p in self.stage_case["parts"] if p.get("layout") == "surface")
        elements = []
        for p in self.stage_case["parts"]:
            if p.get("layout") in ("mark", "name"):
                box = colour_box(pic, p["colour"])
                if box:
                    elements.append({"kind": p["layout"], "box": box, "align": "centre", "seen_text": p["text"],
                                     "finish": "none", "confidence": 0.9})
            elif p.get("layout") == "window":
                box = colour_box(pic, p["colour"])
                if box:
                    elements.append({"kind": "window", "box": box, "align": "centre", "shape": "oval",
                                     "finish": "gold foil", "confidence": 0.9})
            elif p.get("layout") == "motif":
                box = colour_box(pic, p["colour"])
                if box:
                    elements.append({"kind": "motif", "box": box, "align": "centre", "finish": "none",
                                     "confidence": 0.9})
        return {"surface": "lid", "surface_box": colour_box(pic, surface["colour"]),
                "surface_shape": "round" if surface.get("ellipse") else "rounded_rect",
                "elements": elements, "unread": [], "notes": "wiring check oracle"}

    # -- images
    def image(self, **kw):
        self._follow()
        self.calls.append("image")
        sent = kw.get("image")
        for f in sent if isinstance(sent, list) else ([sent] if sent is not None else []):
            # [his test blocker on design 122, 2026-10-07] the image service takes only what its library calls a file
            # (bytes, a stream, a path or a (name, bytes, type) tuple): the first redraw of 122's concepts sent a Django
            # file field, which this stub took and the live service refused
            from openai._files import is_file_content
            if not is_file_content(f):
                raise StubRefused("the image call was sent a %s, which the image service refuses" % type(f).__name__)
            self.sent.append(os.path.realpath(f[0] if isinstance(f, tuple) else getattr(f, "name", "") or ""))
        self.prompts.append((_own_words(self.stage_case), kw.get("prompt") or ""))
        data = mock.MagicMock()
        data.url = None
        redraw = str(kw.get("prompt") or "").startswith(REDRAW_WORDS)
        self.redraws += redraw
        # [His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), A1] a motif's flat redraw — answered by the case's own flat artwork,
        # or refused where the case refuses it
        from apps.pipeline.services.flat_motif import FLAT_WORDS
        flat = str(kw.get("prompt") or "").startswith(FLAT_WORDS)
        self.flats += flat
        if flat and self.stage_case.get("flat_refused"):
            raise RuntimeError(self.stage_case["flat_refused"])
        if flat and self.stage_case.get("flats"):
            # each motif's own flat redraw, by the picture and the part it was asked of (122's real one for 149)
            asked = next((f[1] for f in (sent if isinstance(sent, list) else [sent]) if isinstance(f, tuple)), b"")
            sha = hashlib.sha256(asked).hexdigest()
            self.flat = next((art for (pic_sha, part), art in self.stage_case["flats"].items()
                              if pic_sha == sha and part in str(kw.get("prompt"))), self.flat)
        # [his test findings on design 123, 2026-10-09, (1)] the carton's layout picture: a flat sheet of its panels
        from apps.pipeline.targets.carton_layout import LAYOUT_PROMPT
        layout = str(kw.get("prompt") or "").startswith(LAYOUT_PROMPT[:48])
        self.layouts += layout
        # [his test blocker on design 124, 2026-10-11, (3) and (5)] a lid's flat redraw — the lid it was sent, as the
        # image model keeps its scene — and an open palette's picture, its grid as asked
        from apps.pipeline.targets.container.lid_art import LID_ART_WORDS
        from apps.pipeline.targets.container.tray_picture import TRAY_WORDS
        lid_art = str(kw.get("prompt") or "").startswith(LID_ART_WORDS)
        tray = str(kw.get("prompt") or "").startswith(TRAY_WORDS)
        self.lid_arts = getattr(self, "lid_arts", 0) + lid_art
        self.trays = getattr(self, "trays", 0) + tray
        if lid_art and self.stage_case.get("lid_art_refused"):
            raise RuntimeError(self.stage_case["lid_art_refused"])
        if lid_art:
            sent_lid = next((f[1] for f in (sent if isinstance(sent, list) else [sent]) if isinstance(f, tuple)), b"")
            data.b64_json = base64.b64encode(self.stage_case.get("lid_art") or sent_lid).decode()
        elif tray:
            data.b64_json = base64.b64encode(self.stage_case.get("tray_picture") or tray_picture(kw.get("prompt"))).decode()
        if lid_art or tray:
            resp = mock.MagicMock()
            resp.data = [data]
            resp._request_id, resp.id = "req_img", "img_1"
            return resp
        # [his go of 2026-10-08, item 4] a case's own pictures, one a call, where it gives them (122's real concepts)
        queued = self.queue.pop(0) if self.queue and not redraw and not flat and not layout else None
        data.b64_json = base64.b64encode(queued if queued else (
            self.layout_sheet(kw.get("prompt")) if layout else (
                self.flat if flat else (self.redrawn if redraw else self.picture)))).decode()
        resp = mock.MagicMock()
        resp.data = [data]
        resp._request_id, resp.id = "req_img", "img_1"
        return resp

    # [his test findings on design 123, 2026-10-09, (1)] the layout picture the image service draws: four tall panels in
    # a row on white, each side as wide as the prompt asks, the design's pink, a berry band at each panel's foot
    def layout_sheet(self, prompt):
        import cv2
        import numpy as np
        m = re.search(r"each side (\d+)% as wide as the front", str(prompt))
        side = int(m.group(1)) / 100.0 if m else 0.6
        img = np.full((1024, 1536, 3), 255, np.uint8)
        fw, h, gap, x = 300, 660, 12, 60
        boxes = {}
        for name, share in (("back", 1.0), ("side_left", side), ("front", 1.0), ("side_right", side)):
            w = int(fw * share)
            boxes[name] = [x, 180, x + w, 180 + h]
            img[180:180 + h, x:x + w] = (214, 200, 247)
            img[180 + h - 60:180 + h, x:x + w] = (120, 40, 140)
            x += w + gap
        self.sheet = (cv2.imencode(".png", img)[1].tobytes(), boxes)
        return self.sheet[0]

    def answer_carton_layout_parts(self, kw):
        from apps.pipeline.services import concept_outline as co
        picture, boxes = self.sheet
        s = co._read(picture)[1]

        def up(b):
            return [int(round(v * s)) * 2 for v in b]
        return {"panels": [{"panel": name, "box": up(b), "parts": [
            {"kind": "field", "name": "pink ground", "box": up(b), "confidence": 0.9},
            {"kind": "band", "name": "berry foot band", "box": up([b[0], b[3] - 60, b[2], b[3]]), "confidence": 0.9}]}
            for name, b in boxes.items()], "notes": "wiring check oracle"}

    # -- trend search
    def search(self, query, **kw):
        self.calls.append("trend_search")
        self.queries.append(query)
        if self.case.get("trend_pictures") and not kw.get("include_domains"):
            # [his goal of 2026-10-10, item 3] the open web's finds: a picture of the case's own product and another's
            return {"results": [{"url": "https://%s.example/page" % host, "title": "trend: " + query[:60],
                                 "content": "", "score": 0.9,
                                 "images": [{"url": "https://%s.example/picture.png" % host, "description": ""}]}
                                for host in sorted(TREND_FINDS)], "images": [], "usage": {"credits": 1}}
        return {"results": [{"url": "https://www.pinterest.com/pin/%d/" % (sum(map(ord, query)) % 10 ** 6),
                             "title": "trend: " + query[:60], "images": []}],
                "images": [], "usage": {"credits": 1}}


def tray_picture(prompt) -> bytes:
    """[His test blocker on design 124, 2026-10-11, (5)] the open palette the image service draws: its pans in the grid
    the prompt asks for, each a shade of its own — matte, a sheen, or glitter, in turn — on a pink insert."""
    import cv2
    import numpy as np
    m = re.search(r"(\d+) \w+ pans in (\d+) rows of (\d+)", str(prompt))
    rows, cols = (int(m.group(2)), int(m.group(3))) if m else (3, 6)
    img = np.full((1024, 1536, 3), 238, np.uint8)
    cv2.rectangle(img, (100, 140), (1436, 920), (226, 210, 242), -1)
    side = int(min(1200 / (cols * 1.3), 700 / (rows * 1.6)))
    gap = int(side * 0.3)
    x0 = (1536 - (cols * side + (cols - 1) * gap)) // 2
    rnd = np.random.default_rng(124)
    for r in range(rows):
        for c in range(cols):
            x, y = x0 + c * (side + gap), 200 + r * int(side * 1.6)
            colour = np.array((60 + 25 * c, 50 + 40 * r, 150 + 10 * c), float)
            pan = np.zeros((side, side, 3), float)
            pan[:] = colour
            if (r + c) % 3 == 1:
                yy, xx = np.mgrid[0:side, 0:side]
                pan = pan + (255 - pan) * 0.5 * np.clip(1.0 - (xx + yy) / (1.2 * side), 0, 1)[..., None]
            if (r + c) % 3 == 2:
                for _ in range(int(0.05 * side * side / 4)):
                    px, py = rnd.integers(2, side - 3, 2)
                    pan[py - 1:py + 2, px - 1:px + 2] = pan[py, px] + (255 - pan[py, px]) * 0.8
            img[y:y + side, x:x + side] = pan.clip(0, 255).astype(np.uint8)
            cv2.rectangle(img, (x - 2, y - 2), (x + side + 1, y + side + 1), (150, 140, 160), 2)
    return cv2.imencode(".png", img)[1].tobytes()


# ================================================================ the detectors

def _size_of(input_json):
    """The carton's width, depth and height from a dieline job's input (top level, or under "dimensions")."""
    given = (input_json or {}).get("dimensions") if isinstance((input_json or {}).get("dimensions"), dict) else input_json
    return {k: float(given[k]) for k in ("width_mm", "depth_mm", "height_mm") if k in (given or {})}


def _black(colour) -> bool:
    if not colour:
        return False
    if len(colour) == 4:
        return colour[3] > 0.9 and max(colour[:3]) < 0.2
    return max(colour) < 0.2                # the label's rich black, never a pure 0


def ean_measured(page):
    """[His goal of 2026-10-10, item 7] a finished page's barcode, measured: ``(its bars' box mm, its module, its tallest
    bar, the white sticker round it)`` — its bars every thin black rectangle, the sticker the smallest white shape
    round them; None with no bars."""
    k = 25.4 / 72.0
    drawings = page.get_drawings()
    bars = [d["rect"] for d in drawings if _black(d.get("fill")) and d["rect"].width * k < 1.5
            and d["rect"].height * k > 1.0 and all(it[0] == "re" for it in d["items"])]
    if len(bars) < 20:
        return None
    x0, y0 = min(r.x0 for r in bars) * k, min(r.y0 for r in bars) * k
    x1, y1 = max(r.x1 for r in bars) * k, max(r.y1 for r in bars) * k
    whites = [d["rect"] for d in drawings if d.get("fill") and len(d["fill"]) == 3 and min(d["fill"]) > 0.97
              and d["rect"].x0 * k <= x0 and d["rect"].y0 * k <= y0 and d["rect"].x1 * k >= x1 and d["rect"].y1 * k >= y1]
    sticker = min(whites, key=lambda r: r.width * r.height) if whites else None
    return ((x0, y0, x1, y1), min(r.width for r in bars) * k, max(r.height for r in bars) * k,
            (sticker.x0 * k, sticker.y0 * k, sticker.x1 * k, sticker.y1 * k) if sticker else None)


#: [his goal of 2026-10-12, (5)] the widest gap two runs on one baseline are read across: a 3 mm sign's room and a space
SIGN_JOIN_PT = 13.5


def signs_drawn(page):
    """[His goal of 2026-10-10, item 8] each estimated sign a finished page draws as its own shape between a quantity and
    the next ("60 ml \u212e 2 fl oz"): ``[(the words round it, its box in mm)]`` — read where it is drawn, between the
    unit's last letter and the next number, never a glyph of a face. [His word of 2026-10-17 on 142] each with the size
    its words are set at, in pt: ``[(words, box, size_pt)]``."""
    import re
    k = 25.4 / 72.0
    fills = [d["rect"] for d in page.get_drawings() if d.get("fill") and any(it[0] == "c" for it in d["items"])]
    found = []
    # [his goal of 2026-10-12, (5)] a 3 mm sign needs a wider room than a face's "e", and a reader may split its run there
    # into two lines on one baseline: such lines are read as one row, the gap a space — never across a wider gap than a
    # sign's room and a space (JOIN_PT), so two columns side by side stay apart
    rows = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            chars = [dict(c, size=span["size"]) for span in line["spans"] for c in span["chars"]]
            if chars:
                rows.append((chars[0]["origin"][1], chars))
    rows.sort(key=lambda r: (round(r[0], 1), r[1][0]["bbox"][0]))
    joined = []
    for base, chars in rows:
        last = joined[-1] if joined else None
        if (last is not None and abs(last[0] - base) < 1.0
                and 0.0 <= chars[0]["bbox"][0] - last[1][-1]["bbox"][2] <= SIGN_JOIN_PT):
            gap = {"c": " ", "size": chars[0]["size"], "bbox": (last[1][-1]["bbox"][2], chars[0]["bbox"][1],
                                                                 chars[0]["bbox"][0], chars[0]["bbox"][3])}
            last[1].extend(([gap] if last[1][-1]["c"] != " " and chars[0]["c"] != " " else []) + chars)
        else:
            joined.append((base, list(chars)))
    for _base, chars in joined:
        text = "".join(c["c"] for c in chars)
        # after its unit, before the next number — or ending its line, where the row wraps after the sign
        for m in re.finditer(r"\d+(?:\.\d+)?\s*(?:ml|g)( +)(?=\d|$)", text):
            left = chars[m.start(1) - 1]["bbox"]
            last = m.end(1) >= len(chars)
            x_hi = left[2] + 2.0 * (left[3] - left[1]) if last else chars[m.end(1)]["bbox"][0] + 0.5
            found += [(" ".join(text[m.start():m.end(1) + 1].split()),
                       [round(v * k, 2) for v in (r.x0, r.y0, r.x1, r.y1)], chars[m.start(1) - 1]["size"])
                      for r in fills if left[2] - 0.5 <= r.x0 and r.x1 <= x_hi and r.y0 < left[3] and r.y1 > left[1]]
    return found


def _finished_files(output):
    out = []
    for field in ("dieline_file", "dieline_ai_file", "production_pdf", "design_preview_ai", "spec_pdf"):
        f = getattr(output, field)
        if f and f.name and os.path.exists(f.path):
            out.append((field, f.path))
    return out


def _image_kind(pix_bytes, concept_rgb):
    """'logo' | 'concept' | 'other' for one picture placed in a finished file — compared by its pixels."""
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(pix_bytes)).convert("RGB")
    a = np.asarray(im.resize((32, 32))).astype(float)
    if abs(a.mean(axis=(0, 1)) - np.array(LOGO_RGB)).max() < 30:
        return "logo"
    b = np.asarray(concept_rgb.resize((32, 32))).astype(float)
    return "concept" if abs(a - b).mean() < 25 else "other"


def _dump(where, h, output):
    """WIRING_DUMP only: the case's image prompts and every picture its finished files hold, to look at."""
    import fitz
    os.makedirs(where, exist_ok=True)
    with open(os.path.join(where, "prompts.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n\n----\n\n".join(p for _own, p in h.prompts))
    with open(os.path.join(where, "concept.png"), "wb") as fh:
        fh.write(h.picture)
    for field, path in _finished_files(output):
        shutil.copy(path, os.path.join(where, field + os.path.splitext(path)[1]))
        if path.endswith((".ai", ".pdf")):
            with fitz.open(path) as doc:
                for pno, page in enumerate(doc):
                    for k, img in enumerate(page.get_images(full=True)):
                        x = doc.extract_image(img[0])
                        with open(os.path.join(where, "%s_p%d_%d.%s" % (field, pno, k, x["ext"])), "wb") as fh:
                            fh.write(x["image"])


def _own_words(case):
    """The words a case's own product goes by (its noun, its form, its product type's words — [his test blocker on design
    124, 2026-10-11] a palette's lid is a palette's — and the generic product words)."""
    own = set(case["noun"].split()) | {case["form"], "product", "pack", "container"}
    own |= set(str((case.get("product") or {}).get("product_type") or "").lower().split())
    if case["kind"] in ("carton", "artwork"):
        own |= {"carton", "box", "case"}
    return own


#: [his goal of 2026-10-13, (8) and (9)] a step between neighbouring pixels (300 dpi, the largest channel) past which a
#: glow reads as bands; a seam: a row or a column where SEAM_SHARE of its lines step SEAM_STEP levels at once — measured
#: on 124: its 2026-10-12 bands stepped 8 and more and showed seams, its meshes step 4 and less and show none
GLOW_STEP, SEAM_STEP, SEAM_SHARE = 6.0, 2.0, 0.6


class Detect:
    """The seven failures, read from what a finished case left: its records, its files and its calls."""

    def __init__(self, case, h, task, output, statuses):
        self.case, self.h, self.task, self.output, self.statuses = case, h, task, output, statuses
        self.faults: list = []

    def fail(self, kind, words):
        self.faults.append("%s: %s" % (kind, words))

    def signs(self):
        """[His goal of 2026-10-10, item 8] every estimated sign the finished files draw as itself, after its quantity."""
        import fitz
        out = []
        for _field, path in _finished_files(self.output):
            if path.endswith((".ai", ".pdf")):
                with fitz.open(path) as doc:
                    for page in doc:
                        out += signs_drawn(page)
        return out

    def _text(self):
        import fitz
        out = []
        for _field, path in _finished_files(self.output):
            if path.endswith((".ai", ".pdf")):
                with fitz.open(path) as doc:
                    out.append(" ".join(page.get_text() for page in doc))
            elif path.endswith(".svg"):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    out.append(fh.read())
        return re.sub(r"\s+", " ", " ".join(out))

    # 1. a silent fallback
    def silent_fallback(self):
        from apps.pipeline.models import AgentLog, TrendBoard
        from apps.pipeline.services import concept_design_map as dm
        if self.h.refused:
            self.fail("SILENT_FALLBACK", "provider calls with no answer were swallowed: %s" % self.h.refused)
        allowed = tuple(self.case.get("warnings_allowed", ()))
        for level, words in AgentLog.objects.filter(task=self.task, level__in=("warning", "error")).values_list(
                "level", "action"):
            if not any(a in words for a in allowed):
                self.fail("SILENT_FALLBACK", "[%s] %s" % (level, words[:240]))
        board = TrendBoard.objects.filter(task=self.task).first()
        if board is not None and board.failure:
            self.fail("SILENT_FALLBACK", "the trend board failed: %s" % board.failure)
        spec = self.output.spec_sheet or {}
        # [his test blocker on design 124, 2026-10-11, (2) and (4): "ONE ENGINE ... no silent fallback"] every container's
        # map read — a face form's from its lid, never its own reading — and a face drawn from its art
        reads_a_map = self.case["kind"] in ("carton", "container")
        if reads_a_map and (spec.get(dm.SCHEMA) or {}).get("state") != dm.MAP_READ:
            self.fail("SILENT_FALLBACK", "the design map was not READ on the output (%r)"
                      % (spec.get(dm.SCHEMA) or {}).get("state"))
        if self.case["kind"] == "container" and self.case.get("face"):
            from apps.pipeline.targets.container import LID_ART_DRAWN_KEY
            if (spec.get(dm.SCHEMA) or {}).get("read") != dm.LID_READ:
                self.fail("SILENT_FALLBACK", "the lid was not read into its map (%r)" % (spec.get(dm.SCHEMA) or {}).get("read"))
            art = spec.get(LID_ART_DRAWN_KEY) or {}
            if art.get("state") != "TRACED":
                self.fail("SILENT_FALLBACK", "the lid was not drawn from its art — its form's own layout instead")
        if self.case.get("pans_named"):
            # [his test blocker on design 124, 2026-10-11, (5): "Every pan gets a real shade colour and finish ... No grey
            # pans."] every pan his brief names listed with its colour, its finish and where they came from
            from apps.ire.palette_tray import PAN_SHOWN
            from apps.pipeline.targets.container import TRAY_PANS_KEY
            from apps.pipeline.targets.container.tray_picture import FROM_NAME, FROM_PICTURE, GLITTER, MATTE, SHIMMER
            pans = [p for row in spec.get(TRAY_PANS_KEY) or [] for p in row]
            grey = [p.get("name") for p in pans if p.get("hex") in (None, PAN_SHOWN)
                    or p.get("source") not in (FROM_PICTURE, FROM_NAME) or p.get("finish") not in (MATTE, SHIMMER, GLITTER)]
            if len(pans) != self.case["pans_named"] or grey:
                self.fail("SILENT_FALLBACK", "the tray's pans were not each given a shade's colour and finish: %d of %d "
                          "listed, grey or unsourced %s" % (len(pans), self.case["pans_named"], grey))
        if self.output.approved_image is not None and dm.MAP_STOP_KEY in (
                self.output.approved_image.reference_provenance or {}):
            self.fail("SILENT_FALLBACK", "a map stop is still on the approved picture")

    # 2. AI pixels where vector belongs
    def ai_pixels(self):
        import fitz
        from PIL import Image
        concept = Image.open(io.BytesIO(self.h.picture)).convert("RGB")
        allowed = 1 if self.case["kind"] == "artwork" else 0
        text = self._text()
        if self.case["kind"] == "container" and REFERENCE_LABEL in text:
            allowed = 1      # the sheet's one labelled reference panel ("REFERENCE — not final artwork"), not artwork
        for field, path in _finished_files(self.output):
            if not path.endswith((".ai", ".pdf")):
                continue
            kinds = Counter()
            with fitz.open(path) as doc:
                pages = len(doc)
                for page in doc:
                    for img in page.get_images(full=True):
                        try:
                            kinds[_image_kind(doc.extract_image(img[0])["image"], concept)] += 1
                        except Exception:  # noqa: BLE001 — a picture that does not open is not vector either
                            kinds["unreadable"] += 1
            if kinds["other"] or kinds["unreadable"]:
                self.fail("AI_PIXELS", "%s holds %d picture(s) that are neither the logo nor the key visual"
                          % (field, kinds["other"] + kinds["unreadable"]))
            if kinds["concept"] > allowed * max(1, pages):
                self.fail("AI_PIXELS", "%s places the concept picture %d time(s) (a %s allows %d a page)"
                          % (field, kinds["concept"], self.case["kind"], allowed))

    # 3. the brief's copy missing
    def brief_copy(self):
        text = self._text()
        if self.case["product"]["name"] not in text and not self._name_set_as_lettering():
            self.fail("BRIEF_COPY_MISSING", "the product's name %r is in no finished file"
                      % self.case["product"]["name"])
        if self.case["kind"] in ("carton", "container") and not any(
                w in text for w in self.case.get("back_words") or BACK_WORDS):      # a real brief's own back copy
            self.fail("BRIEF_COPY_MISSING", "the brief's back copy is in no finished file")

    def _name_set_as_lettering(self) -> bool:
        """[His test blocker on design 124, 2026-10-11, (6)] a name the map sets as the picture letters it — its letters
        set in the closest granted face, in the record's own words, drawn as their outlines (outlines or live text is
        held for his word since his finding on 122's .ai) — counted where the drawing says it drew that part."""
        from apps.ire.container_fidelity import spells_the_name
        from apps.pipeline.services import concept_design_map as dm
        spec = self.output.spec_sheet or {}
        drawn = set(((spec.get("container_motif_fidelity_report") or {}).get("from_the_picture") or {}).get("drawn") or [])
        name = self.case["product"]["name"]
        for t in (spec.get(dm.SHAPES_SCHEMA) or {}).get("types") or []:
            sets = [t.get("lettering_set") or {}, (t.get("lettering_layers") or {}).get("set") or {}]
            if t.get("part") in drawn and any(s.get("state") == "SET" and spells_the_name(s.get("words"), name)
                                              for s in sets):
                return True
        return False

    # 4. another product's text
    def other_product(self):
        text = self._text()
        for words in (DECOY["name"], DECOY["product_id"]):
            if words in text:
                self.fail("OTHER_PRODUCT_TEXT", "another product's %r is printed" % words)

    # 5. wrong product words
    def product_words(self):
        from apps.pipeline.direction_content import _PRODUCT_NOUNS
        for own, prompt in self.h.prompts:
            wrong = sorted((set(_PRODUCT_NOUNS) - own) & set(re.findall(r"[a-z]+", prompt.lower())))
            if wrong:
                self.fail("WRONG_PRODUCT_WORDS", "the picture was asked for with %s" % wrong)

    # 6. a step that never runs
    def steps(self):
        expected = self.case["statuses"]
        missing = [s for s in expected if s not in self.statuses]
        if missing:
            self.fail("STEP_NEVER_RAN", "statuses never reached: %s (saw %s)" % (missing, self.statuses))
        from apps.pipeline.models import ApiCallRecord
        kind = "face" if self.case.get("face") else self.case["kind"]
        ledger = set(ApiCallRecord.objects.filter(task=self.task).values_list("operation", flat=True))
        wanted = list(self.case.get("calls", CALLS[kind]))
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] a design whose brief and record
        # leave a piece of its back label empty has it written — the paid step runs exactly there
        if self.case["kind"] != "composite" and kind in ("container", "face", "carton") and _writes_label(self.task, kind):
            wanted.append("label_copy_writing")
        for op in wanted:
            if op not in self.h.calls:
                self.fail("STEP_NEVER_RAN", "the paid step %r never ran" % op)
            elif op in LEDGERED and op not in ledger and self.case["kind"] != "composite":
                self.fail("BROKEN_LINK", "the paid step %r ran but is on no cost ledger row of this design" % op)
        files = _finished_files(self.output)
        if not files:
            self.fail("STEP_NEVER_RAN", "no finished file")
        for field, path in files:
            if os.path.getsize(path) == 0:
                self.fail("STEP_NEVER_RAN", "%s is empty" % field)

    # 7. a broken link between steps
    def links(self):
        from apps.pipeline.services import concept_design_map as dm
        spec = self.output.spec_sheet or {}
        img = self.output.approved_image
        with img.image_file.open("rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        if sha != hashlib.sha256(self.h.picture).hexdigest():
            self.fail("BROKEN_LINK", "the approved picture is not the picture the image step made")
        rec = spec.get(dm.SCHEMA) or {}
        read_from = sha
        if self.case.get("face"):
            # [his test blocker on design 124, 2026-10-11, (2)] a face form's map is read from its lid, stood square
            from apps.pipeline.targets.container import _map_bytes
            lid = _map_bytes(img, self.case["form"])
            read_from = hashlib.sha256(lid).hexdigest() if lid else None
        if rec.get("source_sha256") not in (None, read_from):
            self.fail("BROKEN_LINK", "the design map was read from another picture")
        if self.case["kind"] == "carton":
            confirmed = spec.get("confirmed_dimensions") or {}
            drawn = _size_of(self.output.dieline_job.input_json)
            # [his correction of 2026-10-07: "Never widen the carton for text; the 'widen' step is removed."] a carton
            # is made at the size he confirmed, its label whatever its length (``label_on_sticker``: CARTON_WIDENED)
            for k, v in self.case["dimensions"].items():
                if k not in confirmed or float(confirmed[k]) != float(v):
                    self.fail("BROKEN_LINK", "confirmed %s %r != posted %r" % (k, confirmed.get(k), v))
                if drawn.get(k) != float(v):
                    self.fail("BROKEN_LINK", "the die was drawn at %s %r, the size confirmed is %r" % (k, drawn.get(k), v))

    # 8. [his final goal, 2026-10-05, C8] a line that breaks keeps its separator
    def separators(self):
        import fitz

        from apps.ire.text_script import SEPARATORS
        for _field, path in _finished_files(self.output):
            if not path.endswith((".ai", ".pdf")):
                continue
            with fitz.open(path) as doc:
                for page in doc:
                    spans = []
                    for blk in page.get_text("dict")["blocks"]:
                        for ln in blk.get("lines", []):
                            across = abs(ln["dir"][0]) >= abs(ln["dir"][1])          # read across, or stood on end
                            for sp in ln["spans"]:
                                if sp["text"].strip():
                                    ox, oy = sp["origin"]
                                    spans.append((across, oy if across else ox, ox if across else -oy, sp["size"],
                                                  sp["text"]))
                    # one line: spans read the same way whose baselines lie within half their size — two runs set
                    # side by side (a Latin run and its Arabic, each centred in its own box) are one line; two lines
                    # set one under another are two, whatever their letters' boxes overlap
                    lines: list = []
                    for sp in sorted(spans, key=lambda s: (s[0], s[1])):
                        for line in lines:
                            a = line[0]
                            if a[0] == sp[0] and abs(a[1] - sp[1]) < 0.5 * min(a[3], sp[3]):
                                line.append(sp)
                                break
                        else:
                            lines.append([sp])
                    for line in lines:
                        words = " ".join(t for *_r, t in sorted(line, key=lambda s: s[2])).split()
                        if len(words) > 1 and words[-1] in SEPARATORS:
                            self.fail("SEPARATOR_AT_BREAK", "%s ends a line with its separator: %r"
                                      % (os.path.basename(path), " ".join(words)))

    # 9. [his final goal, 2026-10-05, C5: "THE INFO IS ONE DESIGNED BLOCK ... Side panels do ONE job ... never 'fl. / oz.'
    # ... never go below the floor"] a carton's label: a piece of it on a side, a span under its floor, or a quantity
    # broken from its unit across lines — read on the drawn file, each span placed on its panel by the die's own record
    LABEL_HEADS = ("INGREDIENTS", "WARNINGS", "HOW TO USE", "INGREDIENTES", "ADVERTENCIAS", "MODO DE USO", "DESCRIPCI",
                   "NET WT", "BATCH NO")
    UNITS = {"ml", "ml.", "g", "g.", "mg", "kg", "oz", "oz.", "fl", "fl.", "l", "%"}

    def label_block(self):
        import fitz

        from apps.dielines.exporters.label_layout import FINE_FLOOR_PT, FLOOR_PT, TITLE_EM
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire.compose import _PAGE_MARGIN_MM, BACK_COPY_KEY
        record = (self.output.spec_sheet or {}).get(BACK_COPY_KEY)
        job = getattr(self.output, "dieline_job", None)
        drawn = self.output.design_preview_ai
        if not record or job is None or not job.input_json or not (drawn and drawn.name and os.path.exists(drawn.path)):
            return
        levels = record.get("levels_pt") or {}
        if levels and (levels["body"] < FLOOR_PT or levels["fine"] < FINE_FLOOR_PT):
            self.fail("LABEL_UNDER_FLOOR", "the label's levels %s, under the floors %g / %g pt"
                      % (levels, FLOOR_PT, FINE_FLOOR_PT))
        # [his correction of 2026-10-07: "Shrink the whole label evenly until everything fits, keeping its layout,
        # spacing and order."] its ingredients and warnings at the body's size, its title never above its proportion
        # to it (smaller only where its own width asks: his goal of 2026-10-06, item 12)
        if levels and (abs(levels["fine"] - levels["body"]) > 1e-6
                       or levels["title"] > round(levels["body"] * TITLE_EM, 2) + 1e-6):
            self.fail("LABEL_UNEVEN", "the label's levels %s are not one size shrunk evenly" % (levels,))
        coords = calculate_dieline(DielineInputJSON(**job.input_json))
        vx = coords.bleed_polygon.bounds[0] - _PAGE_MARGIN_MM
        vy = coords.bleed_polygon.bounds[1] - _PAGE_MARGIN_MM
        k = 25.4 / 72.0

        def panel_at(x, y):
            return next((p.name for p in coords.panels if p.x <= x <= p.x + p.width and p.y <= y <= p.y + p.height),
                        None)
        back = []
        with fitz.open(drawn.path) as doc:
            for blk in doc[0].get_text("dict")["blocks"]:
                for ln in blk.get("lines", []):
                    for sp in ln["spans"]:
                        text = sp["text"].strip()
                        if not text:
                            continue
                        x0, y0, x1, y1 = sp["bbox"]
                        on = panel_at((x0 + x1) / 2 * k + vx, (y0 + y1) / 2 * k + vy)
                        if on in ("side_left", "side_right") and any(h in text for h in self.LABEL_HEADS):
                            self.fail("LABEL_SCATTERED", "%r stands on the %s" % (text, on))
                        if on == "back":
                            if sp["size"] < FINE_FLOOR_PT - 0.01 and not text.replace(" ", "").isdigit():
                                self.fail("LABEL_UNDER_FLOOR", "%r set at %.2f pt on the back" % (text, sp["size"]))
                            if abs(ln["dir"][0]) >= abs(ln["dir"][1]):
                                back.append((sp["origin"][1], sp["origin"][0], sp["size"], text))
        lines: list = []
        for sp in sorted(back):
            for line in lines:
                if abs(line[0][0] - sp[0]) < 0.5 * min(line[0][2], sp[2]):
                    line.append(sp)
                    break
            else:
                lines.append([sp])
        words = [" ".join(t for *_r, t in sorted(line, key=lambda s: s[1])).split() for line in lines]
        for a, b in zip(words, words[1:]):
            if a and b and (a[-1].lower() in ("fl", "fl.") or (re.match(r"^\d+([.,]\d+)?$", a[-1])
                                                               and b[0].lower() in self.UNITS)):
                self.fail("UNIT_BROKEN", "%r / %r" % (" ".join(a), " ".join(b)))

    # 10. [his final goal, 2026-10-05, B1: "Never leave the inside blank or white ... Two artboards, OUTSIDE and INSIDE
    # ... never pasted or copied 1:1"] a carton's inside: its own artboard, printed in vector over the sheet (unless he
    # chose plain), no picture placed on it, and no inside reference ever sent to an image service
    def inside_print(self):
        import fitz

        from apps.ire.compose import BACK_COPY_KEY, INSIDE_KEY
        spec = self.output.spec_sheet or {}
        drawn = self.output.design_preview_ai
        if BACK_COPY_KEY not in spec or not (drawn and drawn.name and os.path.exists(drawn.path)):
            return
        record = spec.get(INSIDE_KEY)
        if not record:
            self.fail("INSIDE_BLANK", "the carton keeps no record of its inside")
            return
        with fitz.open(drawn.path) as doc:
            if doc.page_count < 2:
                self.fail("INSIDE_BLANK", "the carton's file has one artboard")
                return
            page = doc[1]
            if page.get_images():
                self.fail("AI_PIXELS", "a picture is placed on the inside")
            if record.get("mode") != "plain":
                inked = [d for d in page.get_drawings() if d.get("fill") and min(d["fill"]) < 0.95
                         and (d["rect"].width / page.rect.width) * (d["rect"].height / page.rect.height) > 0.3]
                if not inked:
                    self.fail("INSIDE_BLANK", "the inside prints nothing across the sheet (%s)" % record.get("mode"))
        wanted = self.case.get("expect_inside") or {}
        if any(record.get(k) != v for k, v in wanted.items()):
            self.fail("INSIDE_NOT_FOLLOWED", "the inside %s, where his picture and words say %s"
                      % ({k: record.get(k) for k in wanted}, wanted))
        refs = [os.path.realpath(r.image.path) for r in self.task.references.filter(kind="inside_reference")]
        sent = [p for p in self.h.sent if p in refs]
        if sent:
            self.fail("INSIDE_REFERENCE_SENT", "an inside reference was sent to the image service: %s" % sent)

    # 11. [his final goal, 2026-10-05, B3: "THE BACK INFO IS A STICKER, his choice at the size step"] the back's
    # information as he chose it: on the record, and on the drawn back — a sticker drawn where he chose one, none where
    # he chose it printed, his custom sticker's fill where it is dark
    def back_info(self):
        import fitz

        from apps.ire.compose import BACK_COPY_KEY
        record = (self.output.spec_sheet or {}).get(BACK_COPY_KEY) or {}
        drawn = self.output.design_preview_ai
        if not record or not (drawn and drawn.name and os.path.exists(drawn.path)):
            return
        style = record.get("back_info") or {}
        wanted = self.case.get("expect_back_info") or {"mode": "sticker"}
        if any(style.get(k) != v for k, v in wanted.items()):
            self.fail("BACK_INFO_NOT_AS_CHOSEN", "the back's information stands %s where he chose %s"
                      % ({k: style.get(k) for k in wanted}, wanted))
        sticker = record.get("sticker_mm")
        if (style.get("mode") == "printed") != (sticker is None):
            self.fail("BACK_INFO_NOT_AS_CHOSEN", "a sticker %s where he chose %s" % ("drawn" if sticker else "missing",
                                                                                  style.get("mode")))

    # 12. [his final goal, 2026-10-05, A: "Go: container back labels are trilingual too (English, Spanish, Arabic),
    # translated per design."] a container's back panel, as drawn at print size: its Spanish and its Arabic beside its
    # English — never English alone
    def container_trilingual(self):
        from apps.ire import back_panel
        record = (self.output.spec_sheet or {}).get(back_panel.SCHEMA)
        if not record or self.case["kind"] != "container" or not record.get("lines"):
            return
        drawn = [e for e in record["lines"] if e.get("fits")]
        spanish = any(str(s.get("heading", "")).upper() in ("MODO DE USO", "INGREDIENTES", "ADVERTENCIAS",
                                                             "DESCRIPCIÓN") for s in record.get("sections") or [])
        arabic = any(e.get("lang") == "ar" for e in drawn)
        if not (spanish and (arabic or self.case.get("stop"))):
            self.fail("LABEL_NOT_TRILINGUAL", "the back panel carries %s" % (
                "no Spanish" if not spanish else "no Arabic drawn"))

    # 13. [his final goal, 2026-10-05, B2: "A PRINT-READY DIELINE ... Each on its own named layer: CUT, CREASE, GLUE,
    # BLEED, SAFE, ARTWORK. It must go to a printer without being edited."] a carton's die drawn at the print-ready
    # version — its lock slits and thumb notch cut — and its files on the named layers, the guides never printing, a
    # crease drawn on every fold
    def print_ready(self):
        import fitz

        from apps.dielines import registry
        from apps.dielines.exporters.counter_display_files import CARTON_LAYERS as LAYERS, CARTON_NON_PRINTING as NON_PRINTING, layers_of
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        job = self.output.dieline_job
        drawn = self.output.design_preview_ai
        if self.case["kind"] != "carton" or job is None or not (drawn and drawn.name and os.path.exists(drawn.path)):
            return
        coords = calculate_dieline(DielineInputJSON(**job.input_json))
        d = coords.derived
        want = registry.print_ready_version(job.template_type)
        if d.get("template_version") != want or len(coords.slit_lines) != 4 or not d.get("thumb_notch"):
            self.fail("DIE_NOT_PRINT_READY", "the die is drawn at %s, where %s is print-ready (%d lock slits, %s)" % (
                d.get("template_version"), want, len(coords.slit_lines),
                "a thumb notch" if d.get("thumb_notch") else "no thumb notch"))
        pdf = self.output.production_pdf
        for label, path, wanted in (("the design file", drawn.path, set(LAYERS)),
                                    ("the production PDF", pdf.path if pdf and pdf.name else None,
                                     {"CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS"})):
            if path is None or not os.path.exists(path):
                continue
            layers = layers_of(path)
            missing = sorted(wanted - set(layers))
            printing = sorted(n for n in NON_PRINTING if n in layers and layers[n]["prints"])
            if missing or printing:
                self.fail("DIE_NOT_PRINT_READY", "%s: %s" % (label, "; ".join(
                    (["no %s layer" % ", ".join(missing)] if missing else [])
                    + (["%s printing" % ", ".join(printing)] if printing else []))))
        with fitz.open(drawn.path) as doc:
            creases = sum(1 for dr in doc[0].get_drawings() if dr.get("layer") == "CREASE"
                          and dr.get("dashes") not in (None, "[] 0", "[] 0.0") for it in dr["items"] if it[0] == "l")
        if creases < len(coords.fold_lines):
            self.fail("DIE_NOT_PRINT_READY", "%d dashed creases drawn for %d folds" % (creases, len(coords.fold_lines)))

    # 23. [his goal of 2026-10-12, (1): "keep the files RGB like the drawing until I give you my printer's CMYK profile;
    # then convert with that profile only."] the layered file's colour space, as his printer's profile has it
    def layered_colour(self):
        from apps.dielines.exporters.output_intent import describe_profile
        record = (self.output.spec_sheet or {}).get("native_ai/1.0")
        if self.case["kind"] not in ("carton", "container", "face") or not record:
            return
        ident = describe_profile()
        want = ("CMYK", ident.path) if ident.valid else ("RGB", None)
        if (record.get("space"), record.get("profile")) != want:
            self.fail("LAYERED_FILE_COLOUR", "the layered file is %s (%s) where %s is wanted" % (
                record.get("space"), record.get("profile"), want[0]))

    # 24. [his goal of 2026-10-12, (4): "gold in the picture is foil (my rule)"] every region a lid's art draws in the
    # picture's gold on a foil plate
    def gold_foiled(self):
        spec = self.output.spec_sheet or {}
        want = int((spec.get("container_lid_art_drawn/1.0") or {}).get("gold_regions") or 0)
        if not want:
            return
        plates = ((spec.get("container_finish_plates/1.0") or {}).get("plates") or {}).get("plates") or []
        foiled = {i for p in plates if p.get("kind") in ("foil", "metallic_ink") for i in p.get("items") or []}
        got = sum(1 for i in foiled if str(i).startswith("lid-art-"))
        if got < want:
            self.fail("GOLD_NOT_FOIL", "%d of the lid art's %d gold regions on a foil plate" % (got, want))

    # 25. [his goal of 2026-10-12, (5): "℮: at least 3 mm tall wherever it's printed (the EU rule)"] — [his word of
    # 2026-10-17 on 142: "The ℮ is scaled with its line (at least 3 mm only where the line is large enough); never larger
    # than the text beside it."] 3 mm where its line's capitals stand that tall, and never taller than they are
    def estimated_size(self):
        from apps.ire.estimated_sign import CAP_SHARE, MIN_HEIGHT_MM, PT_PER_MM
        for words, box, size_pt in self.signs():
            tall, caps = box[3] - box[1], CAP_SHARE * size_pt / PT_PER_MM
            if caps >= MIN_HEIGHT_MM and tall < MIN_HEIGHT_MM - 0.05:
                self.fail("ESTIMATED_SIGN_SMALL", "%r: its sign %.2f mm tall" % (words, tall))
            if tall > caps + 0.05:
                self.fail("ESTIMATED_SIGN_LARGE", "%r: its sign %.2f mm tall over its %.2f mm capitals" % (
                    words, tall, caps))

    # 26. [his goal of 2026-10-12, (6): "FINISHES are never invented: a finish plate ... is made only when my brief or the
    # concept shows it."] every plate one his brief asks for, or the picture's gold
    def finish_asked(self):
        from apps.ire import container_finishes as F
        record = (self.output.spec_sheet or {}).get("container_finish_plates/1.0") or {}
        asked = F.asked(self.task.task_text)
        gold = {r.get("plate") for r in record.get("applied") or []
                if r.get("target") == "gold_as_drawn" and r.get("state") == F.APPLIED}
        for plate in (record.get("plates") or {}).get("plates") or []:
            if plate.get("kind") not in asked and plate.get("plate") not in gold:
                self.fail("FINISH_INVENTED", "plate %s (%s): his brief does not ask for it, nor is it the picture's "
                                             "gold" % (plate.get("plate"), plate.get("kind")))

    # 27. [his goal of 2026-10-12, (9) and (10): a shimmer pan "a soft, subtle sheen (light glow toward one corner), never
    # a hard left-to-right stripe"; a glitter pan "fine, dense sparkle, never a few big white dots"]
    def pan_finishes(self):
        drawn = ((self.output.spec_sheet or {}).get("palette_open_tray/1.0") or {}).get("pans_drawn") or {}
        for pan in drawn.get("shimmer") or []:
            if pan["kind"] != "radial" or pan["max_lift"] > 0.35 or pan["steepest"] > 0.6:
                self.fail("SHIMMER_STRIPE", "%s: a %s blend %.2f to white, falling %.2f per share" % (
                    pan["pan"], pan["kind"], pan["max_lift"], pan["steepest"]))
        for pan in drawn.get("glitter") or []:
            if pan["flakes"] < 100 or pan["largest_share"] > 0.025:
                self.fail("GLITTER_COARSE", "%s: %d flakes, the largest %.1f %% of the pan" % (
                    pan["pan"], pan["flakes"], 100.0 * pan["largest_share"]))

    # 14. [his final goal, 2026-10-05, C6: "EVERY ELEMENT IS ITS OWN PIECE ... Text stays editable where possible."] a
    # drawn carton's or container's native, layered .ai — built, or the record says why not; never silently absent
    def native_said(self):
        drawn = self.output.design_preview_ai
        if self.case["kind"] not in ("carton", "container", "face") or not (drawn and drawn.name):
            return
        record = (self.output.spec_sheet or {}).get("native_ai/1.0")
        if not record:
            self.fail("NATIVE_FILE_UNSAID", "the design keeps no record of its native, layered .ai")
        elif not record.get("built") and not record.get("reason"):
            self.fail("NATIVE_FILE_UNSAID", "the native .ai was not built and the record does not say why")

    # 17. [his final goal, 2026-10-05, C5: "Only if it still doesn't fit, STOP and offer ... fewer languages"; A:
    # "container back labels are trilingual too"] a container whose back cannot stand in its languages stops WITH its
    # offers measured — each smaller set its back holds, or the record that none does — never a stop without a way out
    def container_offers(self):
        from apps.pipeline.targets.container import CONTAINER_LABEL_OFFERS_KEY
        spec = self.output.spec_sheet or {}
        fit = spec.get("container_back_panel/1.0") or {}
        if self.case["kind"] not in ("container", "face") or fit.get("fits") is not False:
            return
        if CONTAINER_LABEL_OFFERS_KEY not in spec:
            self.fail("STOP_WITHOUT_OFFER", "the back stops in %s and no offer was measured"
                      % ", ".join(spec.get("container_label_languages") or ["en", "es", "ar"]))

    # 16. [his final goal, 2026-10-05, B4: "NO PROMPT STEP. Three directions planned privately and validated. Three
    # truly different concepts drawn straight away. Each picture shows a name and one sentence; the details folded."]
    # no direction asked of him; the first pictures one for each planned direction, by its id, each with its name and
    # its sentence; the picture he picked names the direction the design went on in
    def no_prompt_step(self):
        from apps.pipeline.models import CreativeBrief, GeneratedImage
        from apps.pipeline.serializers import GeneratedImageSerializer
        brief = CreativeBrief.objects.filter(task=self.task).first()
        if brief is None or not brief.design_intent:
            return
        if "awaiting_direction_selection" in self.statuses:
            self.fail("PROMPT_STEP", "the design waited for a direction to be chosen")
        planned = [d["direction_id"] for d in brief.directions]
        first = list(GeneratedImage.objects.filter(task=self.task).order_by("pk")[:len(planned)])
        if sorted(i.direction_id for i in first) != sorted(planned):
            self.fail("PROMPT_STEP", "the first pictures were drawn for %s, where the plan is %s"
                      % ([i.direction_id for i in first], planned))
        for row in GeneratedImageSerializer(first, many=True).data:
            if not (row.get("direction_name") and row.get("direction_sentence")):
                self.fail("PROMPT_STEP", "picture %s shows no name and sentence" % row["id"])
        picked = GeneratedImage.objects.filter(task=self.task, is_approved=True).first()
        if picked is not None and picked.direction_id and brief.selected_direction_id != picked.direction_id:
            self.fail("PROMPT_STEP", "he picked %s's picture; the design went on in %r"
                      % (picked.direction_id, brief.selected_direction_id))

    # 15. [his final goal, 2026-10-05, C7: "THE SYSTEM CHECKS ITS OWN WORK ... Never hand me a defect silently."] every
    # drawn design keeps the record of its own check, and what this detector's own read of the drawn file finds, the
    # record shows
    def self_checked(self):
        from apps.ire import self_check
        drawn = self.output.design_preview_ai
        if not (drawn and drawn.name and os.path.exists(drawn.path)):
            return
        record = (self.output.spec_sheet or {}).get(self_check.SCHEMA)
        if not record:
            self.fail("DEFECT_HANDED_SILENTLY", "the drawn design keeps no record of its own check")
            return
        if self.case["kind"] == "carton" and self.output.dieline_job is not None:
            from apps.dielines.geometry.engine import calculate_dieline
            from apps.dielines.validators.schema import DielineInputJSON
            job = self.output.dieline_job.input_json
            regions, folds, axis = self_check.carton_frame(calculate_dieline(DielineInputJSON(**job)))
            safe = float((job.get("print_settings") or {}).get("safe_margin_mm") or 0.0)
            pages = (0, 1)
        elif self.case["kind"] in ("container", "face"):
            import fitz
            from types import SimpleNamespace
            with fitz.open(drawn.path) as doc:
                w, h = doc[0].rect.width * 25.4 / 72.0, doc[0].rect.height * 25.4 / 72.0
            # [his final goal, C7b] its back panel at print size read with its own margin, as the check reads it
            regions = self_check.sheet_frame(SimpleNamespace(page_w=w, page_h=h, metadata={}),
                                             back_panel=(self.output.spec_sheet or {}).get("container_back_panel/1.0"))
            folds, safe, pages = None, 0.0, (0,)
            axis = None
        else:
            return
        shown = {f["what"] for f in record.get("shown") or []}
        for f in self_check.inspect(drawn.path, regions, folds=folds, safe_mm=safe, pages=pages, inside_axis=axis):
            if f["what"] not in shown:
                self.fail("DEFECT_HANDED_SILENTLY", "%s — %s, not in the record" % (f["kind"], f["what"]))

    # [his goal of 2026-10-06, item 1] "the Container type I choose ALWAYS wins ... The chosen type holds through the
    # title, the trend search, the directions, the concepts, the shape step and the carton."
    def container_type(self):
        from apps.dashboard.board import title_of
        from apps.pipeline.targets.container import brief_text, concept_directive, form_label, form_of_task, product_in_form
        form = self.case.get("chosen_form") or (self.case["form"] if self.case["kind"] in ("container", "composite")
                                                 else None)
        if form is None or self.case.get("target") == "palette":
            return
        decoy = DECOY_OF.get(form)
        words = DECOY_WORDS.get(decoy, ()) if decoy != form else ()
        tasks = list(self.task.project.tasks.order_by("pk")) if self.task.project_id else [self.task]
        vessel = next((t for t in tasks if t.design_target == "product_container"), None)
        if vessel is None:
            return
        text = brief_text(vessel)
        what = product_in_form(form, text) or form_label(form).lower().replace(" / ", " or ")

        def names_decoy(s):
            return [w for w in words if re.search(r"\b%s\b" % w, s.lower())]
        for t in tasks:
            if form_of_task(t) != form:
                self.fail("CONTAINER_TYPE", "design %s reads its form as %r, not the %r chosen" % (t.design_target,
                                                                                              form_of_task(t), form))
        title = title_of(vessel)
        if names_decoy(title):
            self.fail("CONTAINER_TYPE", "the title %r names %s" % (title, names_decoy(title)))
        for q in self.h.queries:
            if names_decoy(q):
                self.fail("CONTAINER_TYPE", "the trend search %r names %s" % (q, names_decoy(q)))
        for got in self.h.test.proposed:
            if got != form:
                self.fail("CONTAINER_TYPE", "the shape step proposed %r, not the %r chosen" % (got, form))
        if concept_directive(form, text) not in "\n".join(self.h.asks.get("creative_directions", [])):
            self.fail("CONTAINER_TYPE", "the directions were not asked for a %s" % what)
        line = "THE PRODUCT'S FORM: a %s — the owner's Container type" % what
        for ask in self.h.asks.get("container_gate1_variations", []):
            if line not in ask:
                self.fail("CONTAINER_TYPE", "a concept was asked without %r" % line)
        if self.case["kind"] == "carton":
            line = "THE PRODUCT INSIDE THIS CARTON: a %s — the owner's Container type" % what
            if not any(line in ask for ask in self.h.asks.get("image_prompts", [])):
                self.fail("CONTAINER_TYPE", "the carton's concepts were not told the %s inside" % what)

    def _carton_page(self):
        """``(the drawn outside page, coords, vx, vy)`` of a carton, or None."""
        if self.case["kind"] != "carton" or not self.output.design_preview_ai or not self.output.dieline_job:
            return None
        import fitz

        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire.compose import _PAGE_MARGIN_MM
        coords = calculate_dieline(DielineInputJSON(**self.output.dieline_job.input_json))
        vx = coords.bleed_polygon.bounds[0] - _PAGE_MARGIN_MM
        vy = coords.bleed_polygon.bounds[1] - _PAGE_MARGIN_MM
        return fitz.open(self.output.design_preview_ai.path)[0], coords, vx, vy

    @staticmethod
    def _circles(drawing) -> int:
        """How many of a drawing's closed runs of four curves are the dots of the invented pattern: circles of exactly
        its dots' size (``inside_print``: a dot's radius is a fifth of the sparse pitch) — a concept's own round motif,
        repeated at the motif's own size, is not one."""
        from apps.ire.inside_print import PITCH_MM
        dot = 2 * PITCH_MM["sparse"] * 0.2 * 72.0 / 25.4          # its diameter, in points
        items = drawing.get("items") or []
        n = 0
        for i in range(0, len(items) - 3, 4):
            run = items[i:i + 4]
            if any(it[0] != "c" for it in run):
                continue
            pts = [it[1] for it in run] + [run[-1][4]]
            xs, ys = [p.x for p in pts], [p.y for p in pts]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            if w > 0 and abs(w - h) <= 0.05 * w and abs(w - dot) <= 0.1 * dot:
                n += 1
        return n

    # [his second goal of 2026-10-06 (transcribed at c34a518), item 1: "ALL LABEL INFORMATION GOES ON THE BACK STICKER
    # (rule for every design). Never printed inside the box"; his correction of 2026-10-07: "Never move information
    # anywhere else ... and never drop it. Never widen the carton for text".] a carton's drawn outside carries every piece
    # of its label on the back — each language's headings and a word of each piece of his English — its inside none of
    # it and no line pointing there; and the carton is drawn at the width he confirmed
    def label_on_sticker(self):
        spec = self.output.spec_sheet or {}
        record = spec.get("back_copy/1.0")
        got = self._carton_page()
        if got is None or not record:
            return
        import fitz

        from apps.ire.compose import LABEL_DOES_NOT_FIT
        page, coords, vx, vy = got
        # [his correction of 2026-10-07: "Never widen the carton for text; the 'widen' step is removed."] the die is
        # drawn at the width he confirmed, whatever the label's length, stopped or not
        drawn_w = float(((self.output.dieline_job.input_json or {}).get("dimensions") or {}).get("width_mm") or 0)
        asked_w = float((self.case.get("dimensions") or {}).get("width_mm") or drawn_w)
        if abs(drawn_w - asked_w) > 1e-6 or record.get("widened"):
            self.fail("CARTON_WIDENED", "drawn %g mm wide where %g mm was confirmed (%r)" % (
                drawn_w, asked_w, record.get("widened")))
        if LABEL_DOES_NOT_FIT in (record.get("codes") or []):
            self.fail("LABEL_NOT_ON_STICKER", "the label stopped off the back's sticker: %s" % (record.get("said"),))
            return
        back = next(q for q in coords.panels if q.name == "back")
        k = 72.0 / 25.4
        box = fitz.Rect((back.x - vx) * k, (back.y - vy) * k, (back.x + back.width - vx) * k,
                        (back.y + back.height - vy) * k)
        on_back = " ".join(page.get_text("text", clip=box).split())
        drawn = fitz.open(self.output.design_preview_ai.path)
        inside = " ".join(drawn[1].get_text("text").split()) if drawn.page_count > 1 else ""
        info = spec.get("panel_info") or {}
        wanted = []
        for field, heads in (("description", ()), ("ingredients", ("INGREDIENTS", "INGREDIENTES")),
                             ("how_to_use", ()), ("warnings", ("WARNINGS", "ADVERTENCIAS"))):
            text = str(info.get(field) or "")
            if text.strip():
                words = [w.strip(".,;:()") for w in text.split()]
                wanted += [max(words, key=len)] + list(heads)
        for words in wanted:
            if words not in on_back:
                self.fail("LABEL_NOT_ON_STICKER", "the back's sticker does not carry %r: %r" % (words, on_back[:300]))
            if words in inside:
                self.fail("LABEL_PRINTED_INSIDE", "the inside carries %r of the label" % words)

    # [his goal of 2026-10-06, item 10: "Flaps use the concept's own motif or the logo, never an invented pattern"] no flap
    # of the drawn outside carries a dot pattern — a pattern the concept and the brief do not have
    def flap_design(self):
        got = self._carton_page()
        if got is None:
            return
        import fitz
        page, coords, vx, vy = got
        k = 72.0 / 25.4
        # [his second test blocker on design 123, 2026-10-09] each drawing with the clip it is drawn under: a drawing
        # clipped to another panel (a continued front's line art, clipped to the front, its connected stems running far
        # past it) never lies on a flap — a flap's own motif, clipped to its flap, is still measured whole
        drawings, scissors = [], {}
        for d in page.get_drawings(extended=True):
            if d.get("type") == "clip":
                scissors = {lv: r for lv, r in scissors.items() if lv < d["level"]}
                scissors[d["level"]] = fitz.Rect(d["scissor"])
            elif d.get("type") in ("f", "fs", "s"):
                held = [r for lv, r in scissors.items() if lv < d.get("level", 0)]
                drawings.append(dict(d, clip_rect=held[-1] if held else None))
        for name, poly in getattr(coords, "components", []) or []:
            if name in ("main-body", "glue-tab"):
                continue
            x0, y0, x1, y1 = poly.bounds
            box = fitz.Rect((x0 - vx) * k, (y0 - vy) * k, (x1 - vx) * k, (y1 - vy) * k)
            dots = sum(self._circles(d) for d in drawings if fitz.Rect(d["rect"]).intersects(box)
                       and d.get("fill") is not None and fitz.Rect(d["rect"]).get_area() < box.get_area() * 4)
            if dots >= 3:
                self.fail("INVENTED_PATTERN", "the %s flap carries %d dots, a pattern the design never had" % (name, dots))
            # [executor, the same goal, read on 119's drawn flaps: a repeat clipped to each flap cut its vials in half at
            # the die's edge and across the tuck's fold] every shape drawn on a flap stands whole on it: a filled drawing
            # smaller than the carton's body that reaches into the flap lies inside the flap — a tuck's on its own panel,
            # never across its fold onto its tongue
            from shapely.geometry import box as _box
            region = poly
            made = coords.dimensions.manufacture
            if "tuck" in name and name.startswith("top"):
                region = poly.intersection(_box(x0, coords.body_top_y - made[1], x1, coords.body_top_y))
            elif "tuck" in name and name.startswith("bottom"):
                region = poly.intersection(_box(x0, coords.body_bottom_y, x1, coords.body_bottom_y + made[1]))
            region = region.buffer(0.3)
            body = coords.body_polygon.bounds
            body_area = (body[2] - body[0]) * (body[3] - body[1]) * k * k
            # [His review of 127, 130, 131 and 132, 2026-10-15, C (1): "THE PATTERN WRAPS THE WHOLE PACK ... it covers
            # every panel of the carton (sides, back behind the sticker, flaps)"] on a flap the drawing's record says
            # carries the front's pattern, a drawing as large as the front's field (ROUND_FIELD_SHARE of the front) is
            # that pattern, cut at the flap's edge as it is at every fold — never a shape placed on the flap
            from apps.ire.compose import ROUND_FIELD_SHARE
            front = next(p for p in coords.panels if p.name == "front")
            wrapped = name in ((((self.output.spec_sheet or {}).get("front_type/1.0") or {}).get("round_the_pack") or {})
                               .get("flaps_named") or [])
            field_area = ROUND_FIELD_SHARE * front.width * front.height * k * k
            for d in drawings:
                r = fitz.Rect(d["rect"])
                reach = fitz.Rect(r)
                reach.intersect(box)
                if d.get("fill") is None or reach.is_empty or reach.get_area() <= 1.0 or r.get_area() >= body_area:
                    continue
                if wrapped and r.get_area() >= field_area:
                    continue
                if d["clip_rect"] is not None and not fitz.Rect(d["clip_rect"]).intersects(box):
                    continue                                  # clipped to another panel: it never lies on this flap
                if not region.contains(_box(r.x0 / k + vx, r.y0 / k + vy, r.x1 / k + vx, r.y1 / k + vy)):
                    self.fail("FLAP_SHAPE_CUT", "a shape on the %s flap is cut by its edge or its fold: drawn over "
                              "%.1f×%.1f mm, the flap's own face %s mm" % (
                                  name, r.width / k, r.height / k, [round(v, 1) for v in region.bounds]))
                    break

    # [his goal of 2026-10-06, item 11: "Side panels are designed: the product name at a real size plus a brand graphic
    # from the concept, not one tiny vertical line on plain ground."]
    def side_design(self):
        got = self._carton_page()
        if got is None or not (self.output.spec_sheet or {}).get("container_design_map/1.0"):
            return
        import fitz
        page, coords, vx, vy = got
        k = 72.0 / 25.4
        spans = [s for b in page.get_text("dict")["blocks"] for line in b.get("lines", []) for s in line["spans"]
                 if s["text"].strip()]
        drawings = page.get_drawings()
        for p in (q for q in coords.panels if q.name in ("side_left", "side_right")):
            box = fitz.Rect((p.x - vx) * k, (p.y - vy) * k, (p.x + p.width - vx) * k, (p.y + p.height - vy) * k)
            inside = [d for d in drawings if fitz.Rect(d["rect"]).intersects(box) and d.get("fill") is not None
                      and fitz.Rect(d["rect"]).get_area() < box.get_area() * 0.6 and fitz.Rect(d["rect"]) in box]
            biggest = max([s["size"] for s in spans if fitz.Rect(s["bbox"]).intersects(box)] + [0.0])
            name_drawn = biggest >= 12.0 or any(fitz.Rect(d["rect"]).height >= box.height * 0.3 for d in inside)
            if not name_drawn:
                self.fail("SIDE_UNDESIGNED", "the %s carries no name at a real size (its largest type %.1f pt)"
                          % (p.name, biggest))
            pictures = [fitz.Rect(i["bbox"]) for i in page.get_image_info() if fitz.Rect(i["bbox"]) in box]
            # [his test findings on design 123, 2026-10-09 (transcribed at cbdf721), (2): "Garden Wrap's rose field runs
            # across every panel unbroken"] or the front's field run round the carton across it: a drawing clipped to
            # the side that covers most of its top third
            top = fitz.Rect(box.x0 + k, box.y0 + k, box.x1 - k, box.y0 + box.height * 0.35)     # a millimetre in
            field = any(d.get("fill") is not None and d["clip_rect"] is not None
                        and fitz.Rect(d["clip_rect"]).contains(top) and fitz.Rect(d["clip_rect"]).width <= box.width + k
                        and fitz.Rect(d["rect"]).intersect(top).get_area() >= 0.7 * top.get_area()
                        for d in self._clipped(page))
            if not field and not any(r.y1 <= box.y0 + box.height * 0.35
                                     for r in [fitz.Rect(d["rect"]) for d in inside] + pictures):
                self.fail("SIDE_UNDESIGNED", "the %s carries no brand graphic" % p.name)

    # [his test findings on design 123, 2026-10-09 (transcribed at cbdf721), (1): "NO GUESSED PANELS ... Every panel is
    # drawn from it."] a carton drawn from its concept's map says where its back and each side came from: its layout
    # picture, or the front continued — and why
    def panels_said(self):
        from apps.ire.compose import FRONT_TYPE_KEY
        spec = self.output.spec_sheet or {}
        if self.case.get("kind") != "carton" or not (spec.get("container_design_map/1.0") or {}).get("face_box_px"):
            return
        said = {r.get("panel"): str(r.get("drawn_from") or "") for r in (spec.get(FRONT_TYPE_KEY) or {}).get("panels")
                or [] if str(r.get("drawn_from") or "") == "the layout picture"
                or str(r.get("drawn_from") or "").startswith("continues the front: ")}
        missing = [p for p in ("back", "side_left", "side_right") if p not in said]
        if missing:
            self.fail("PANELS_GUESSED", "the carton's %s drawn with no word of where it came from — no layout picture, "
                      "no front continued" % ", ".join(missing))

    @staticmethod
    def _clipped(page) -> list:
        """Each filled drawing on ``page`` with the clip rectangle it is drawn under (None where it has none)."""
        import fitz
        out, scissors = [], {}
        for d in page.get_drawings(extended=True):
            if d.get("type") == "clip":
                scissors = {lv: r for lv, r in scissors.items() if lv < d["level"]}
                scissors[d["level"]] = fitz.Rect(d["scissor"])
            elif d.get("type") in ("f", "fs", "s"):
                held = [r for lv, r in scissors.items() if lv < d.get("level", 0)]
                out.append(dict(d, clip_rect=held[-1] if held else None))
        return out

    # [his goal of 2026-10-06, item 12: "The sticker title is sized to fit on one or two lines, never one word per line"]
    def title_lines(self):
        got = self._carton_page()
        if got is None:
            return
        import fitz
        page, coords, vx, vy = got
        name = str(getattr(self.task.product, "name", "") or "").upper().split()
        back = next((q for q in coords.panels if q.name == "back"), None)
        if len(name) < 2 or back is None:
            return
        k = 72.0 / 25.4
        box = fitz.Rect((back.x - vx) * k, (back.y - vy) * k, (back.x + back.width - vx) * k,
                        (back.y + back.height - vy) * k)
        # the title is the name in capitals; the copy says it in its own case
        words = [w for w in page.get_text("words") if fitz.Rect(w[:4]).intersects(box) and w[4] in name]
        rows = sorted({round(w[3]) for w in words})
        if len(rows) > 2:
            self.fail("TITLE_LINES", "the sticker's title %r stands on %d lines" % (" ".join(name), len(rows)))
        # [his second goal of 2026-10-06] and its Arabic: the record counts the title's lines in both languages — at
        # most two each (label_layout.TITLE_LINES_MAX)
        from apps.dielines.exporters.label_layout import TITLE_LINES_MAX
        drawn = (((self.output.spec_sheet or {}).get("back_copy/1.0") or {}).get("panels") or {}).get("back") or {}
        if (drawn.get("title_lines") or 0) > 2 * TITLE_LINES_MAX:
            self.fail("TITLE_LINES", "the sticker's title stands on %d lines in its two languages"
                      % drawn["title_lines"])

    # [his goal of 2026-10-06, item 8: "Fix the container back-label 1 mm safe-margin overrun: measure with the real font
    # outlines so it never crosses. A warning is not a fix."] no line of a container's back stands in its safe margin —
    # read on the drawn file at print size, as the self-check reads it; shown beside Approve is not enough
    def back_margin(self):
        if self.case["kind"] not in ("container", "face"):
            return
        import fitz
        from types import SimpleNamespace

        from apps.ire import self_check
        drawn = self.output.design_preview_ai
        back = (self.output.spec_sheet or {}).get("container_back_panel/1.0")
        if not drawn or not back or not back.get("emitted", True):
            return
        with fitz.open(drawn.path) as doc:
            w, h = doc[0].rect.width * 25.4 / 72.0, doc[0].rect.height * 25.4 / 72.0
        regions = self_check.sheet_frame(SimpleNamespace(page_w=w, page_h=h, metadata={}), back_panel=back)
        for f in self_check.inspect(drawn.path, regions, pages=(0,)):
            if f["kind"] == "in the safe margin" and f.get("panel") == "back panel":
                self.fail("BACK_MARGIN", self_check.said(f))

    # [His second goal of 2026-10-06, item 2: "A FAST FOLD CHECK ... run on every dieline before I see it ... A failure is
    # fixed or shown to me, never hidden." — "Add the fold check and the rules to the wiring check."] a carton's die
    # folded again here from its job's own input, by the check as this module first imported it: the record the design
    # carries says what this says; a die that does not fold was held at Gate 2 by name, never approved; and the die is
    # the style it is named — a straight tuck end's tucks on one panel, a reverse tuck end's on opposite panels
    def fold_and_rules(self):
        job = self.output.dieline_job
        if self.case["kind"] != "carton" or job is None or not job.input_json:
            return
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        coords = calculate_dieline(DielineInputJSON(**job.input_json))
        again = _FOLD_AGAIN(coords)
        record = (self.output.spec_sheet or {}).get("fold_check/1.0")
        failed = sorted(x["id"] for x in again["failed"])
        if record is None:
            self.fail("FOLD_CHECK_UNSAID", "the design carries no fold check of its die")
        elif record.get("passed") != again["passed"] or sorted(x["id"] for x in record.get("failed") or []) != failed:
            self.fail("FOLD_CHECK_UNSEEN", "the design's record says %s; folded again, the die %s" % (
                "it folds" if record.get("passed") else "it fails %s" % [x["id"] for x in record.get("failed") or []],
                "folds" if again["passed"] else "fails %s" % failed))
        if not again["passed"]:
            held = self.task.status == "awaiting_gate_2" and "completed" not in (self.statuses or [])
            self.fail("FOLD_CHECK_FAILED" if held else "FOLD_CHECK_FAILED_UNHELD", "the die does not fold (%s)%s" % (
                ", ".join(failed), "; held at Gate 2 by name" if held else " — and the design went past Gate 2"))
        tucks = {n.split("-")[0]: n.split("-")[1] for n, _p in coords.components if n.endswith("-tuck")}
        style = job.input_json.get("template")
        if job.template_type != style:
            self.fail("STYLE_MISNAMED", "the job's row names a %s, its die is a %s" % (job.template_type, style))
        same = tucks.get("top") == tucks.get("bottom")
        if (style == "straight_tuck_end_carton" and not same) or (style == "reverse_tuck_end_carton" and same):
            self.fail("STYLE_MISNAMED", "a %s whose tucks hang from %s" % (style.replace("_", " "), tucks))

    # [his answers after the fixes for design 122, 2026-10-08, (2): "the drawing must always print my brief's size (60
    # ml), never the picture's text. Confirm that holds for every design."] every size a finished file prints is his
    # brief's, and his brief's — where it gives one — is printed
    def brief_size(self):
        from apps.pipeline.services import concept_design_map as dm
        size = dm.brief_size(self.task.task_text)
        wanted = _quantities(size[0]) if size else set()
        printed = _quantities(self._text())
        if printed - wanted:
            self.fail("SIZE_NOT_BRIEFS", "a size his brief does not give is printed: %s (his brief's: %s)"
                      % (sorted(printed - wanted), size[0] if size else "none"))
        if size and not wanted & printed:
            self.fail("SIZE_UNPRINTED", "his brief's size %r is in no finished file" % size[0])

    # [his goal of 2026-10-10, item 1: "NO planner check ever stops a design ... Apply this to every planner and
    # concept check."] a design a planner or concept check stopped, and a note beside three shown that names a check
    # in no words
    def planner_stopped(self):
        from apps.dashboard.words import CONCEPT_CHECK_WORDS, DIRECTION_CHECK_WORDS
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
        from apps.pipeline.models import AgentLog
        error = self.task.error_message or ""
        for words in ("Direction planning failed validation", "Gate-1 variation contract not satisfied",
                      "PROMPTS_NOT_BOUND_TO_DIRECTIONS", "Prompt Engineer produced"):
            if words in error:
                self.fail("PLANNER_STOPPED", "a planner or concept check stopped the design: %s" % error[:240])
        for payload in AgentLog.objects.filter(task=self.task).values_list("payload", flat=True):
            note = payload.get(SHOWN_ALIKE_KEY) if isinstance(payload, dict) else None
            for code in (note or {}).get("codes") or []:
                head = str(code).split(":", 1)[0].strip()
                if head not in DIRECTION_CHECK_WORDS and head not in CONCEPT_CHECK_WORDS:
                    self.fail("PLANNER_STOPPED", "the note beside the three names %s in no words" % head)

    # [his goal of 2026-10-10, items 3 and 4] a trend picture shown that is not the case's own product; a search
    # asked in generic words
    def trend_junk(self):
        from apps.pipeline.models import InspirationReading, TrendPick
        from apps.pipeline.services import trend_board
        for query in self.h.queries:
            if re.search(r"\b(packaging|cosmetic)\b", query.lower()):
                self.fail("TREND_QUERY_GENERIC", "the trend search asked for %r" % query)
        board = trend_board.payload(self.task)
        if board is None:
            return
        own = self.case.get("trend_product")
        shas = dict(TrendPick.objects.filter(board__task=self.task).values_list("pk", "sha256"))
        for picture in board["pictures"]:
            reading = InspirationReading.objects.filter(sha256=shas.get(picture["id"])).values_list(
                "reading", flat=True).first() or {}
            form = str(reading.get("product_form") or "")
            if not own or own not in form:
                self.fail("TREND_JUNK_SHOWN", "trend picture %s shows %r" % (picture["number"], form))

    # [his goal of 2026-10-10, item 5: "Draw ONE continuous scallop: every arc the same size, clean at panel edges,
    # aligned across every fold and round the whole carton."] a carton's scalloped band, measured on its finished file
    def scallop_even(self):
        import fitz
        from apps.pipeline.services import concept_design_map as dm
        if self.case["kind"] != "carton" or self.output is None or not self.output.design_preview_ai:
            return
        spec = self.output.spec_sheet or {}
        bands = [s for s in (spec.get(dm.SHAPES_SCHEMA) or {}).get("shapes") or [] if s.get("edges") and s.get("ink")]
        if not bands:
            return
        ink = tuple(int(bands[0]["ink"][i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        with self.output.design_preview_ai.open("rb") as fh:
            page = fitz.open(stream=fh.read(), filetype="pdf")[0]
        k = 25.4 / 72.0
        found = [d for d in page.get_drawings() if d.get("fill") and len(d["fill"]) == 3
                 and max(abs(a - b) for a, b in zip(d["fill"], ink)) < 0.06
                 and sum(1 for it in d["items"] if it[0] == "c") >= 6]
        dims = _size_of(self.output.dieline_job.input_json if self.output.dieline_job else {})
        round_mm = 2.0 * (dims["width_mm"] + dims["depth_mm"]) if len(dims) == 3 else 0.0
        widest = max(found, key=lambda d: d["rect"].width) if found else None
        if widest is None or widest["rect"].width * k < 0.95 * round_mm:
            self.fail("SCALLOP_NOT_ONE", "no one scallop runs round the carton's %.1f mm in its band's %s (widest %.1f mm)"
                      % (round_mm, bands[0]["ink"], widest["rect"].width * k if widest else 0.0))
            return
        curves = [it for it in widest["items"] if it[0] == "c"]
        feet = [float(it[4].x) * k for it in curves[1::2]]
        tops = [float(it[4].y) * k for it in curves[0::2]]
        widths = [b - a for a, b in zip(feet, feet[1:])]
        if widths and (max(widths) - min(widths) > 0.01 * sum(widths) / len(widths) or max(tops) - min(tops) > 0.05):
            self.fail("SCALLOP_RAGGED", "its arcs %.2f to %.2f mm wide, their tops %.2f mm apart"
                      % (min(widths), max(widths), max(tops) - min(tops)))

    # [his goal of 2026-10-10, item 7: "BARCODE: ... Always whole, inside the sticker, with quiet zones. No number
    # from me = no barcode."] his number's barcode on the finished file, measured
    def ean_whole(self):
        import fitz
        if self.case["kind"] != "carton" or self.output is None or not self.output.design_preview_ai:
            return
        with self.output.design_preview_ai.open("rb") as fh:
            measured = ean_measured(fitz.open(stream=fh.read(), filetype="pdf")[0])
        number = str(self.case["product"].get("barcode_ean") or "")
        if not number:
            if measured is not None:
                self.fail("EAN_WITHOUT_NUMBER", "a barcode is printed though he gave no number")
            return
        if measured is None:
            self.fail("EAN_CUT", "his number's barcode is in no finished file")
            return
        (x0, y0, x1, y1), module, tallest, sticker = measured
        if tallest < 60.0 * module:
            self.fail("EAN_CUT", "its bars %.1f mm tall at a %.3f mm module — cut short of its own height"
                      % (tallest, module))
        if sticker is None or x0 - sticker[0] < 11 * module or sticker[2] - x1 < 7 * module or y1 > sticker[3]:
            self.fail("EAN_CUT", "not whole inside the sticker with its quiet zones (bars %s, sticker %s)"
                      % ([round(v, 1) for v in (x0, y0, x1, y1)], sticker and [round(v, 1) for v in sticker]))

    # [his goal of 2026-10-10, item 8: "The ℮ prints as a plain "e": it must be the real estimated sign
    # everywhere."] the ℮ left to a face — which draws it as its "e" — or an "e" printed where the sign belongs
    def estimated_sign(self):
        import fitz
        for _field, path in _finished_files(self.output):
            if not path.endswith((".ai", ".pdf")):
                continue
            with fitz.open(path) as doc:
                text = " ".join(page.get_text() for page in doc)
            if "\u212e" in text:
                self.fail("ESTIMATED_SIGN_AS_LETTER", "%s sets the \u212e in a face, which draws it as an 'e'" % _field)
            m = re.search(r"\d\s*(?:ml|g|oz)\s+e\s+\d", text)
            if m:
                self.fail("ESTIMATED_SIGN_AS_LETTER", "%s prints an 'e' where the sign belongs: %r" % (_field, m.group(0)))

    # 28. [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design. ... Every check has
    # its words written; a check without words fails the wiring check."] a design never stopped on a check of its own,
    # and every check it went on past, every one its drawing shows and every one kept with his approval said in words
    def checks_go_on(self):
        from apps.dashboard.words import _CODE, NOT_A_CHECK, check_words
        from apps.ire.self_check import CHECKS_SHOWN_KEY
        from apps.pipeline.gate2_problems import KEPT_KEY
        if self.task.status == "failed":
            stopped = [c for c in _CODE.findall(self.task.error_message or "")
                       if c not in NOT_A_CHECK and check_words(c)]
            if stopped:
                self.fail("CHECK_STOPPED", "the design stopped on its own check: %s" % ", ".join(stopped))
        spec = (self.output.spec_sheet or {}) if self.output is not None else {}
        rows = list(spec.get(CHECKS_SHOWN_KEY) or []) + list(spec.get(KEPT_KEY) or [])
        rows += [f for f in ((spec.get("self_check/1.0") or {}).get("shown") or []) if f.get("code")]
        for row in rows:
            code = str(row.get("code") or "").split(":")[0].strip()
            if code and code not in NOT_A_CHECK and not check_words(code):
                self.fail("CHECK_WITHOUT_WORDS", "%s has no words written for it" % code)
            said = row.get("words") or row.get("what") or ""
            raw = [c for c in _CODE.findall(said) if c not in NOT_A_CHECK and check_words(c)]
            if raw:
                self.fail("CHECK_WITHOUT_WORDS", "%s is said with a check's code in it (%s): %r"
                          % (code, ", ".join(raw), said[:160]))

    # 29. [His goal of 2026-10-13, (3): ""Resume this design / Not moving?" appears ONLY when the design has truly
    # stopped ... Never while it's working, waiting for me, or done."] at every stop the run reached, the page was never
    # told the design had stopped
    def resume_only_stopped(self):
        for status, stalled, where in getattr(self.h.test, "stall_reads", []):
            if stalled is True:
                self.fail("RESUME_WHILE_MOVING", "%s (%s): the page is told the design has stopped" % (where, status))

    def _lid_drawn(self):
        """``(the drawing's path, the lid's box on its first page (mm, x y w h), the lid art's redraw)`` where a lid's art
        was drawn, else None."""
        drawn = ((self.output.spec_sheet or {}).get("container_lid_art_drawn/1.0") or {}).get("drawn") or {} \
            if self.output is not None else {}
        art = self.case.get("lid_art")
        if not drawn.get("on_page_mm") or not art or not (self.output.design_preview_ai and
                                                            self.output.design_preview_ai.name):
            return None
        return self.output.design_preview_ai.path, drawn["on_page_mm"], art

    def _gold_strokes(self, path, box):
        """The drawing's stroked paths in a gold ink inside ``box``: ``[(points in mm, stroke width mm)]``."""
        import fitz

        from apps.pipeline.services.concept_design_map import is_gold_hex
        k = 72.0 / 25.4
        x, y, w, h = box
        out = []
        with fitz.open(path) as pdf:
            for d in pdf[0].get_drawings():
                col = d.get("color")
                if not col or d.get("fill") is not None or d.get("type") not in ("s", "fs"):
                    continue
                if not is_gold_hex("#%02X%02X%02X" % tuple(int(round(c * 255)) for c in col[:3])):
                    continue
                pts = []
                for it in d["items"]:
                    # each segment's own ends — never a curve's handles, which stand off the line
                    for q in ((it[1], it[-1]) if it[0] in ("c", "l") else [q for q in it[1:] if hasattr(q, "x")]):
                        q = (float(q.x) / k, float(q.y) / k)
                        if not pts or pts[-1] != q:
                            pts.append(q)
                if pts and all(x - 1 <= px <= x + w + 1 and y - 1 <= py <= y + h + 1 for px, py in pts):
                    out.append((pts, float(d.get("width") or 0.0) / k))
        return out

    # 30. [His goal of 2026-10-13, (7): "Geometric shapes are DRAWN, not traced: 124's arch is jagged and broken into
    # dashes."] where the lid's redraw prints a long thin gold line, the drawing strokes it as a line as long — read
    # from the picture itself and from the drawing, never from the engine's record of it
    def geometry_drawn(self):
        import math

        import cv2
        import numpy as np

        from apps.pipeline.services.concept_design_map import _gold
        lid = self._lid_drawn()
        if lid is None:
            return
        path, box, art = lid
        img = cv2.imdecode(np.frombuffer(art, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        gold = _gold(img).astype(np.uint8)
        n, _lab, st, _c = cv2.connectedComponentsWithStats(
            cv2.morphologyEx(gold, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))), 8)
        thin = [int(max(st[c][2], st[c][3])) for c in range(1, n)
                if int(st[c][4]) < 0.08 * int(st[c][2]) * int(st[c][3]) and max(st[c][2], st[c][3]) > 0.25 * min(w, h)]
        if not thin:
            return                                   # the picture prints no long thin gold line
        want = max(thin) / float(w) * box[2]
        got = max((sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) for pts, _w in self._gold_strokes(path, box)),
                  default=0.0)
        if got < 0.5 * want:
            self.fail("TRACED_GEOMETRY", "the lid's picture prints a gold line %.0f mm across; the drawing strokes "
                                         "none longer than %.0f mm — it is traced in pieces" % (want, got))

    def _lid_pixels(self, path, box, dpi=300):
        import fitz
        import numpy as np
        k = 72.0 / 25.4
        x, y, w, h = box
        with fitz.open(path) as pdf:
            pix = pdf[0].get_pixmap(dpi=dpi, clip=fitz.Rect(x * k, y * k, (x + w) * k, (y + h) * k), alpha=False)
        return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).astype(float), dpi / 25.4

    # 31. [His goal of 2026-10-13, (8): "Glow is a real soft blur, never a stack of hard bands (124's arch glow reads as
    # lines)."] across the glow round the lid's gold line, read from the drawing along the line's own normals at its
    # upper part (clear of the flowers): no step between neighbouring pixels past GLOW_STEP
    def glow_smooth(self):
        import numpy as np
        lid = self._lid_drawn()
        if lid is None or not ((self.output.spec_sheet or {}).get("container_lid_art_drawn/1.0") or {}).get("glow"):
            return
        path, box, _art = lid
        strokes = self._gold_strokes(path, box)
        if not strokes:
            return                                   # no line drawn: the geometry detector names it
        pts, width = max(strokes, key=lambda s: len(s[0]))
        a, k = self._lid_pixels(path, box)
        p = np.array(pts)
        top = p[:, 1] <= np.percentile(p[:, 1], 30)
        worst = 0.0
        for i in [i for i in range(1, len(p) - 1) if top[i]][::max(1, int(top.sum()) // 12)]:
            d = p[i + 1] - p[i - 1]
            if not np.linalg.norm(d):
                continue
            n = np.array([-d[1], d[0]]) / np.linalg.norm(d)
            for side in (1.0, -1.0):
                prof = []
                for t in np.arange(width / 2.0 + 0.4, 5.0, 1.0 / k):
                    qx, qy = (p[i] + side * n * t - np.array(box[:2])) * k
                    if 0 <= int(qy) < a.shape[0] and 0 <= int(qx) < a.shape[1]:
                        prof.append(a[int(qy), int(qx)])
                if len(prof) > 2:
                    worst = max(worst, float(np.abs(np.diff(np.array(prof), axis=0)).max()))
        if worst > GLOW_STEP:
            self.fail("GLOW_BANDED", "across the lid's glow, one pixel steps %.0f levels from the next — bands" % worst)

    # 32. [His goal of 2026-10-13, (9): "Gradients are smooth, never flat bands (124's sky shows stripes)."] the lid's
    # sky, read from the drawing above its flowers: no seam — a row or a column where most of its lines step at once
    def sky_smooth(self):
        import numpy as np
        lid = self._lid_drawn()
        if lid is None:
            return
        path, box, _art = lid
        a, _k = self._lid_pixels(path, box)
        hgt, wid = a.shape[:2]
        band = a[int(0.05 * hgt):int(0.35 * hgt), int(0.05 * wid):int(0.95 * wid)]
        seams = 0
        for axis in (0, 1):
            d = np.abs(np.diff(band, axis=axis)).max(axis=2)
            seams += int(((d >= SEAM_STEP).mean(axis=1 - axis) >= SEAM_SHARE).sum())
        if seams:
            self.fail("GRADIENT_BANDED", "the lid's sky shows %d seam(s) — a row or a column of it stepping at once"
                      % seams)

    def all(self):
        for check in (self.silent_fallback, self.ai_pixels, self.brief_copy, self.other_product, self.product_words,
                      self.steps, self.links, self.separators, self.label_block, self.inside_print, self.back_info,
                      self.container_trilingual, self.print_ready, self.native_said, self.self_checked, self.no_prompt_step,
                      self.container_offers, self.container_type, self.flap_design,
                      self.side_design, self.title_lines, self.label_on_sticker,
                      self.back_margin, self.fold_and_rules, self.brief_size, self.panels_said,
                      self.planner_stopped, self.trend_junk, self.scallop_even, self.ean_whole,
                      self.estimated_sign, self.layered_colour, self.gold_foiled, self.estimated_size,
                      self.finish_asked, self.pan_finishes, self.checks_go_on, self.resume_only_stopped,
                      self.geometry_drawn, self.glow_smooth, self.sky_smooth):
            check()
        return self.faults


# ================================================================ the run

RUN_SETTINGS = dict(ANTHROPIC_API_KEY="wiring-check", OPENAI_API_KEY="wiring-check", WEB_SEARCH_API_KEY="wiring-check",
                    WEB_SEARCH_PROVIDER="tavily", DESIGN_MAP_READ=True, PANEL_TRANSLATE_ENABLED=True,
                    PRODUCT_INFERENCE=True, WEB_INSPIRATION_IN_GENERATION=True, OWNER_ACCOUNT="wiring_owner",
                    MAX_REVISION_PASSES=1, DESIGNERS_EYE=True,
                    LABEL_COPY_WRITING=True)   # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)]
#: the paid steps each kind must run (answered by the stubs; the Claude ones also on the design's cost ledger)
CALLS = {"container": ["trend_search", "creative_directions", "container_gate1_variations", "image", "qa_vision_review",
                       "container_design_map_parts",
                       # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the whole back
                       # translated — and, where his brief leaves a piece empty, that piece written (``_writes_label``)
                       "panel_translation"],
         # [his test blocker on design 124, 2026-10-11, (2): "ONE ENGINE"] a face form's map read from its lid, as every
         # form's is — its front never read again for its words' arrangement
         "face": ["trend_search", "creative_directions", "container_gate1_variations", "image", "qa_vision_review",
                  "container_design_map_parts", "panel_translation"],
         "carton": ["trend_search", "creative_directions", "image_prompts", "image", "qa_vision_review",
                    "container_design_map_parts", "panel_translation", "carton_layout_parts"],
         "artwork": ["trend_search", "creative_directions", "image_prompts", "image", "qa_vision_review"]}
LEDGERED = {"creative_directions", "container_gate1_variations", "image_prompts", "qa_vision_review", "trend_brief",
            "container_design_map_parts", "container_concept_layout", "panel_translation", "carton_layout_parts",
            "label_copy_writing"}
# [his final goal, 2026-10-05, B4] no direction is asked of him: the first stop is the pictures
CONTAINER_STATUSES = ["awaiting_gate_1", "awaiting_container_profile",
                      "awaiting_gate_2", "completed"]
CARTON_STATUSES = ["awaiting_gate_1", "awaiting_dimensions", "awaiting_gate_2",
                   "completed"]
STATUSES = {"container": CONTAINER_STATUSES, "carton": CARTON_STATUSES,
            "artwork": ["awaiting_gate_1", "awaiting_gate_2", "completed"]}


@override_settings(**RUN_SETTINGS)
class _Run(TestCase):
    """The site's own doors, driven as a person drives them, for one case."""

    def setUp(self):
        from PIL import Image

        from apps.core.models import Brand, Product
        from apps.pipeline.models import DesignTask
        self.dir = tempfile.mkdtemp(prefix="wiring_")
        self.addCleanup(shutil.rmtree, self.dir, True)
        logo = os.path.join(self.dir, "logo.png")
        Image.new("RGBA", (400, 120), LOGO_RGB + (255,)).save(logo)
        self.enterContext(override_settings(BRAND_LOGO_PATH=logo))
        self.brand = Brand.objects.create(name="BBROSE", master_brief="the house")
        from apps.core.models import ColorSystem
        ColorSystem.objects.create(brand=self.brand, name="Blush Core", system_id="CS-001", status="canonical",
                                   palette=PALETTE, image_generation_context="the house palette")
        Product.objects.create(brand=self.brand, **DECOY)          # another product of the same house (detector 4)
        self.user = get_user_model().objects.create_superuser("wiring_owner", "w@example.invalid", "x")
        self.client.force_login(self.user)
        self._task_id = None
        self.proposed: list = []
        self.stall_reads: list = []                  # [his goal of 2026-10-13, (3)] (status, stalled, where)

        self.saves: list = []

        def trace(sender, instance, **kw):
            self.saves.append((instance.pk, instance.status))
        post_save.connect(trace, sender=DesignTask, weak=False, dispatch_uid="wiring-trace")
        self.addCleanup(post_save.disconnect, sender=DesignTask, dispatch_uid="wiring-trace")

    def current_task(self):
        from apps.pipeline.models import DesignTask
        return DesignTask.objects.get(pk=self._task_id)

    def arm(self, h):
        from apps.pipeline.agents import image_producer
        from apps.pipeline.services import claude_service
        from apps.pipeline.services.round_designer import TavilySearchConnector
        fake = mock.MagicMock()
        fake.messages.create.side_effect = h.create
        self.enterContext(mock.patch.object(claude_service, "_get_client", return_value=fake))
        self.enterContext(mock.patch.object(image_producer.openai.images, "generate", side_effect=h.image))
        self.enterContext(mock.patch.object(image_producer.openai.images, "edit", side_effect=h.image))
        self.enterContext(mock.patch.object(TavilySearchConnector, "search", side_effect=h.search))

    def post(self, url, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, data=json.dumps(data or {}), content_type="application/json")

    def said(self, where):
        from apps.pipeline.models import AgentLog
        t = self.current_task()
        tail = list(AgentLog.objects.filter(task=t).order_by("-pk").values_list("level", "action")[:10])
        out = t.packaging_outputs.order_by("-pk").first()
        spec = (out.spec_sheet if out else None) or {}
        debug = ""
        if os.environ.get("WIRING_DEBUG"):
            keep = {k: v for k, v in spec.items() if any(w in k for w in ("motif", "fidelity", "concept_front",
                                                                         "concept_face", "layout"))}
            art = next((v for k, v in spec.items() if k.startswith("artwork_record")), None) or {}
            rows = [{k: r.get(k) for k in ("format", "key", "codes", "vertical", "layout", "copy_fit")} for r in
                    (art.get("formats") or []) if isinstance(r, dict) and r.get("codes")] + [art.get("fit")]
            debug = "\n  DEBUG " + json.dumps(keep, default=str)[:6000] + "\n  ARTWORK " + json.dumps(rows, default=str)[:3000]
        return "%s: status=%s error=%s\n  statuses=%s\n%s\n  generation_error=%s%s" % (
            where, t.status, (t.error_message or "")[:500], self.statuses_of(t.pk),
            "\n".join("  [%s] %s" % (lv, m[:280]) for lv, m in tail), str(spec.get("generation_error"))[:400], debug)

    def expect(self, status, where):
        self.assertEqual(self.current_task().status, status, self.said(where))
        # [his goal of 2026-10-13, (3)] what the page is told at every stop the run reaches (detector 29)
        r = self.client.get("/api/tasks/%d/status/" % self._task_id)
        if r.status_code == 200:
            self.stall_reads.append((status, r.json().get("stalled"), where))

    # -- the doors
    def create(self, case):
        from apps.core.models import Product
        product = Product.objects.create(brand=self.brand, **case["product"])
        payload = {"task_text": case["brief"], "design_target": case["target"], "product_id": product.pk,
                   "brand_id": self.brand.pk}
        if case.get("inside_pictures"):
            # [his final goal, 2026-10-05, B1] his inside references, sent with Start beside the brief
            from django.core.files.uploadedfile import SimpleUploadedFile
            files = [SimpleUploadedFile("inside_%d.png" % i, pic, "image/png")
                     for i, pic in enumerate(case["inside_pictures"])]
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post("/api/tasks/create/", dict(payload, inside_reference=files))
        else:
            r = self.post("/api/tasks/create/", payload)
        self.assertEqual(r.status_code, 201, r.content[:800])
        self._task_id = r.json()["task_id"]

    def front_half(self):
        # [his final goal, 2026-10-05, B4: "NO PROMPT STEP"] Start leads straight to the pictures
        self.expect("awaiting_gate_1", "create")
        image = self.current_task().images.order_by("pk").first()
        r = self.post("/api/tasks/%d/gate1_approve/" % self._task_id, {"image_id": image.pk})
        self.assertIn(r.status_code, (200, 202), r.content[:800])

    def output(self):
        return self.current_task().packaging_outputs.order_by("-pk").first()

    def gate2(self, stop=None):
        out = self.output()
        if stop is not None:
            # a named check at Gate 2: [his goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a
            # design ... the problem is shown beside Approve in plain words"] shown beside Approve, in words, with exactly
            # the frozen instrument's codes, the design left at its gate for his choice — Gate 2 refused with them until
            # then; an approval keeps them (the approval's own tests)
            body = self.client.get("/api/tasks/%d/status/" % self._task_id).json()
            kept = (body.get("gate2_problems") or {}).get("kept") or []
            codes = sorted({str(k["code"]).split(":")[0] for k in kept})
            self.assertEqual(codes, sorted(stop["codes"]), (kept, self.said("stop")))
            self.assertTrue(all(k["words"] and "_" not in k["words"] for k in kept), kept)
            return out
        r = self.post("/api/tasks/%d/gate2_approve/" % self._task_id, {"packaging_output_id": out.pk})
        if r.status_code != 200:
            if os.environ.get("WIRING_DUMP"):
                _dump(os.path.join(os.environ["WIRING_DUMP"], "refused_%d" % self._task_id), mock.MagicMock(prompts=[],
                      picture=b""), out)
            from apps.pipeline.services.visual_quality_gate import evaluate_container_visual_quality
            report = evaluate_container_visual_quality(self.current_task()) or {}
            failing = {k: v for k, v in (report.get("required_axes") or {}).items()
                       if isinstance(v, dict) and v.get("state") == "FAIL"}
            self.fail("gate 2 refused %s: %s\n  failing axes: %s\n%s" % (
                r.status_code, r.content[:3000], json.dumps(failing, default=str)[:3000], self.said("gate 2")))
        return out

    def container_back_half(self, case):
        self.expect("awaiting_container_profile", "gate 1 (%s)" % case["key"])
        # [his goal of 2026-10-06, item 1] the form the shape step proposes, as the page receives it, before it is set
        st = self.client.get("/api/tasks/%d/status/" % self._task_id).json()
        self.proposed.append((((st.get("container_profile_editor") or {}).get("proposed") or {}).get("archetype")))
        url = "/api/tasks/%d/confirm_container_profile/" % self._task_id
        r = self.post(url, {"profile": case["profile"]})
        if r.status_code == 409 and r.json().get("zones"):
            zones = r.json()["zones"]
            for z in zones:
                z["user_confirmation_state"] = "USER_CONFIRMED"
            r = self.post(url, {"profile": case["profile"], "zones": zones})
        self.assertEqual(r.status_code, 200, (r.content[:2000], self.said("profile (%s)" % case["key"])))
        self.expect("awaiting_gate_2", "profile (%s)" % case["key"])
        out = self.output()
        with out.design_preview.open("rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        r = self.client.post("/dashboard/history/tasks/%d/accept-design/" % self._task_id,
                             {"output_id": out.pk, "preview_sha256": sha, "decision": "ACCEPTED"})
        self.assertIn(r.status_code, (200, 302), r.content[:800])
        return self.gate2(case.get("stop"))

    def carton_back_half(self, case):
        self.expect("awaiting_dimensions", "gate 1 (%s)" % case["key"])
        job = self.output().dieline_job
        self.assertIsNotNone(job, self.said("no dieline job after Gate 1"))
        est = job.extraction_result or {}
        dims = {k: float(est[k]["value"]) for k in ("width_mm", "depth_mm", "height_mm")
                if isinstance(est.get(k), dict) and est[k].get("value") is not None}
        self.assertEqual(len(dims), 3, ("no proposed size on the dieline job", est))
        case["dimensions"] = dims
        r = self.post("/api/tasks/%d/confirm_dimensions/" % self._task_id,
                      dict({"dimensions": dims}, **(case.get("size_choices") or {})))
        self.assertIn(r.status_code, (200, 202), (r.content[:1500], self.said("dimensions (%s)" % case["key"])))
        self.expect("awaiting_gate_2", "dimensions (%s)" % case["key"])
        out = self.gate2(case.get("stop"))      # [his review of 119, 2026-10-05, point 1] a carton may stop by name too
        if case.get("take_offer"):
            # [his final goal, 2026-10-05, C5] his choice of the stopped label's offers, through the door his button opens
            r = self.post("/api/tasks/%d/label_offer/" % self._task_id, case["take_offer"])
            self.assertEqual(r.status_code, 200, (r.content[:800], self.said("label offer (%s)" % case["key"])))
            self.expect("awaiting_gate_2", "label offer (%s)" % case["key"])
            out = self.gate2(None)
        return out

    def run_case(self, case):
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        if case["kind"] == "composite":
            return self.run_composite(case, h)
        self.front_half()
        if case["kind"] == "container":
            out = self.container_back_half(case)
        elif case["kind"] == "carton":
            out = self.carton_back_half(case)
        else:
            self.expect("awaiting_gate_2", "gate 1 (%s)" % case["key"])
            out = self.gate2(case.get("stop"))
        self.expect("awaiting_gate_2" if case.get("stop") and not case.get("take_offer") else "completed",
                    "gate 2 (%s)" % case["key"])
        out.refresh_from_db()
        return case, h, out

    def run_composite(self, case, h):
        from apps.pipeline.models import DesignProject
        project = DesignProject.objects.order_by("-pk").first()
        self._task_id = project.tasks.order_by("pk").first().pk
        self.front_half()
        carton = dict(case["carton"], key="complete_product (the carton)", statuses=CARTON_STATUSES,
                      product=case["product"], chosen_form=case["form"])
        h.next_stage = carton        # [his final goal, B4] its pictures are drawn inside the vial's approval
        self.container_back_half(dict(case, kind="container", key="complete_product (the vial)"))
        project.refresh_from_db()
        self.assertEqual(project.status, "packaging", self.said("the vial's gate 2"))
        self._task_id = project.tasks.order_by("pk").last().pk
        h.to_stage(carton)
        self.front_half()
        out = self.carton_back_half(carton)
        project.refresh_from_db()
        self.assertEqual(project.status, "completed", self.said("the carton's gate 2"))
        out.refresh_from_db()
        return carton, h, out

    def statuses_of(self, task_id):
        out = []
        for pk, status in self.saves:
            if pk == task_id and (not out or out[-1] != status):
                out.append(status)
        return out

    def check(self, key):
        case = copy.deepcopy(CASES[key])
        case, h, out = self.run_case(case)
        case.setdefault("statuses", [s for s in STATUSES[case["kind"]] if not (case.get("stop") and s == "completed")])
        if os.environ.get("WIRING_DUMP"):
            _dump(os.path.join(os.environ["WIRING_DUMP"], key), h, out)
        faults = Detect(case, h, self.current_task(), out, self.statuses_of(self._task_id)).all()
        known = case.get("known") or {}
        kinds = {f.split(":", 1)[0] for f in faults}
        self.assertEqual(sorted(kinds - set(known)), [], "\n".join(faults))
        self.assertEqual(sorted(set(known) - kinds), [], "a KNOWN fault no longer shows — fixed? write it out of the "
                         "table: %s" % {k: known[k] for k in set(known) - kinds})
        return case, h, out


CASES = build_cases()


class WiringCheckTests(_Run):
    """Every design type, brief to finished file — one test per case, read from the code."""

    def test_display_stand(self):
        # Day5: a generic union of style inputs is not an exact assembly/product pack.
        # Historical selected-image composition remains separately covered.
        from apps.pipeline.models import AgentLog
        case=copy.deepcopy(CASES['display_stand']);h=Harness(case,self);self.arm(h);self.create(case)
        self.expect('failed','display exact-reference hold')
        self.assertIn('exact bottle reference and an exact assembly reference',self.current_task().error_message)
        self.assertNotIn('image',h.calls)
        self.assertFalse(self.current_task().images.exists())
        self.assertFalse(self.current_task().packaging_outputs.exists())
        self.assertTrue(AgentLog.objects.filter(task_id=self._task_id,action__contains='EXACT_DISPLAY_REFERENCE_PACK_REQUIRED').exists())

    def test_the_page_and_the_server_name_the_same_working_steps(self):
        # [his goal of 2026-10-06, item 2] the page's list of working steps (static/js/api.js) and the event stream's
        # (live_views.WORKING_STATUSES) are one list: the stream's lacked the trend review, so the page stopped at it
        from apps.pipeline.live_views import WORKING_STATUSES
        js = open(os.path.join(settings.BASE_DIR, "static", "js", "api.js"), encoding="utf-8").read()
        listed = re.search(r"var WORKING_STATUSES = \[([^\]]*)\]", js).group(1)
        self.assertEqual(sorted(re.findall(r"'([a-z_0-9]+)'", listed)), sorted(WORKING_STATUSES))

    # [his test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 1: "Make them agree, so a design can
    # never stop here again. Add it to the wiring check with a REAL planner output, not a stub."] the tube from Start to
    # Gate 1 — where 121 stopped — its concept step answered by the live model's own answer recorded on 121
    # (fixtures_agentlog2420): the first, named by its slots with no direction ids; the second, the ids folded into its
    # names. Each stands: one call, three concept pictures, each named by its slot and drawn for its own direction. (Past
    # Gate 1 the real answer's floral signatures meet the wiring check's motifless stand-in picture, so the run is
    # measured to where the answer is the thing under test.)
    def _on_121s_answer(self, n):
        from apps.pipeline.models import AgentLog
        from apps.pipeline.tests.fixtures_agentlog2420 import RAW_RESPONSES
        case = copy.deepcopy(CASES["tube"])
        h = Harness(case, self)
        self.arm(h)
        with mock.patch.object(Harness, "answer_container_gate1_variations", lambda harness, kw: RAW_RESPONSES[n]):
            self.create(case)
        self.expect("awaiting_gate_1", "121's answer %d" % (n + 1))
        self.assertEqual(h.calls.count("container_gate1_variations"), 1, "the concept step was asked again")
        images = list(self.current_task().images.order_by("pk"))
        self.assertEqual([i.reference_provenance.get("variation_identity") for i in images],
                         ["A_REBEL_BLOOM", "B_TYPE_IN_BLOOM", "C_PETAL_VEIL"])
        self.assertEqual([i.direction_id for i in images],
                         [d["direction_id"] for d in case["directions"]["directions"][:3]])
        self.assertTrue(AgentLog.objects.filter(task_id=self._task_id,
                                                action__contains="the ids read by their slots").exists())

    def test_his_test_findings_121_the_tube_on_the_live_models_first_answer(self):
        self._on_121s_answer(0)

    def test_his_test_findings_121_the_tube_on_the_live_models_second_answer(self):
        self._on_121s_answer(1)

    # [his test blocker on design 122, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), items 2 and 3: "Check each picture's
    # readability BEFORE showing it; if one fails, redraw it automatically (e.g. the same design straight-on on a clearly
    # contrasting plain background) and only show it when it passes"; "the picture the map reads must be clean and
    # contrasting."] 122's one-colour brief, brief to finished files: each tube concept the trace could not cut from its
    # pink ground redrawn on deep charcoal before it was shown — the same design — read once, its read kept for approval
    def test_complete_product_one_colour(self):
        """Rescue: a requested readability edit appends a child; original pixels remain immutable."""
        from apps.pipeline.models import ApiCallRecord, DesignProject
        from apps.pipeline.services.concept_quality import image_verdict
        from apps.pipeline.targets.container.readable import CHECK_KEY, DRAWABLE, NOT_DRAWABLE
        from pathlib import Path
        case = copy.deepcopy(CASES["complete_product_one_colour"])
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        project = DesignProject.objects.order_by("-pk").first()
        tube = project.tasks.order_by("pk").first()
        self._task_id = tube.pk
        originals = list(tube.images.order_by("pk"))
        snapshots = {i.pk: (i.image_file.name, Path(i.image_file.path).read_bytes()) for i in originals}
        self.assertEqual(h.redraws, 0)
        self.assertTrue(all(i.reference_provenance[CHECK_KEY]["state"] == NOT_DRAWABLE for i in originals))
        parent = originals[0]
        r = self.post("/api/tasks/%d/concept_redraw/" % tube.pk, {"image_id": parent.pk})
        self.assertEqual(r.status_code, 200, r.content[:800])
        self.expect("awaiting_gate_1", "immutable readability edit")
        child = tube.images.get(reference_provenance__repair_parent_image_id=parent.pk)
        self.assertEqual(child.reference_provenance[CHECK_KEY]["state"], DRAWABLE)
        self.assertEqual(image_verdict(child)["review_status"], "accepted")
        self.assertEqual(child.reference_provenance["repair_edit_parent_sha256"], hashlib.sha256(snapshots[parent.pk][1]).hexdigest())
        self.assertEqual(Path(child.image_file.path).read_bytes(), h.redrawn)
        self.assertEqual(h.redraws, 1)
        for original in originals:
            original.refresh_from_db()
            self.assertEqual((original.image_file.name, Path(original.image_file.path).read_bytes()), snapshots[original.pk])
        r = self.post("/api/tasks/%d/gate1_approve/" % tube.pk, {"image_id": child.pk})
        self.assertIn(r.status_code, (200, 202), r.content[:800])
        self.assertEqual(ApiCallRecord.objects.filter(task=tube, operation="container_design_map_parts").count(), 1)
        carton = dict(case["carton"], key="complete_product (the carton)", statuses=CARTON_STATUSES,
                      product=case["product"], chosen_form=case["form"])
        h.next_stage = carton
        self.container_back_half(dict(case, kind="container", key="complete_product (the tube)"))
        project.refresh_from_db()
        self.assertEqual(project.status, "packaging", self.said("the tube's gate 2"))
        self._task_id = project.tasks.order_by("pk").last().pk
        h.to_stage(carton)
        self.front_half()
        out = self.carton_back_half(carton)
        project.refresh_from_db()
        self.assertEqual(project.status, "completed", self.said("the carton's gate 2"))
        self.assertEqual(Detect(carton, h, self.current_task(), out, self.statuses_of(self._task_id)).all(), [])
        # [his answers after the fixes for design 122, (2)] the tube's picture printed "100 ml / 3.38 fl. oz.": its own
        # files print his brief's "60 ml ℮ 2 fl oz", never the picture's (the carton's are the detectors' above)
        tube_out = tube.packaging_outputs.order_by("-pk").first()
        sizes = Detect(dict(CASES["complete_product_one_colour"], kind="container"), h, tube, tube_out, [])
        sizes.brief_size()
        self.assertEqual(sizes.faults, [])
        # [re-pinned by his goal of 2026-10-10, item 8: "it must be the real estimated sign everywhere"] its words, and the sign drawn as itself between them
        self.assertIn("60 ml 2 fl oz", sizes._text())
        self.assertNotIn("℮", sizes._text())
        self.assertIn("60 ml 2", [w for w, _box, _pt in sizes.signs()])

    # [his test blocker on design 122, items 4 and 6: "If even the redraw fails, never a dead end: offer me in words what I
    # can do (redraw for $X, draw this concept from the template, or pick another), each with a button."] the same brief
    # where the redraw comes back on its pink ground too: each concept said in plain words with his three offers; his
    # redraw button redraws and checks again; his template button draws it from the tube's standard layout, to the end
    def test_his_test_blocker_122_where_the_redraw_fails_too_his_three_offers_each_a_button(self):
        from apps.pipeline.models import AgentLog, DesignProject
        from apps.pipeline.targets.container.readable import CHECK_KEY, NOT_DRAWABLE
        case = copy.deepcopy(CASES["complete_product_one_colour"])
        case["redraw_ground"] = ONE_PINK_GROUND
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        project = DesignProject.objects.order_by("-pk").first()
        self._task_id = project.tasks.order_by("pk").first().pk
        self.expect("awaiting_gate_1", "122's brief, its redraw failing too")
        images = list(self.current_task().images.filter(superseded=False).order_by("pk"))
        self.assertEqual(h.redraws, 0)
        for image in images:
            rec = image.reference_provenance[CHECK_KEY]
            self.assertEqual(rec["state"], NOT_DRAWABLE)
            self.assertEqual(rec["why"], "the product can't be told apart from its background, so its shape can't be "
                                         "cut out")
            self.assertIsNone(re.search(r"[A-Z_]{6,}", rec["why"]), rec["why"])
            self.assertEqual([o["key"] for o in rec["offers"]], ["redraw", "template", "another"])
            self.assertEqual(rec["offers"][0]["words"], "Redraw it on a plain contrasting backdrop")
            self.assertRegex(rec["offers"][0]["cost_usd"], r"^\d+\.\d\d$")
            self.assertEqual(rec["offers"][1]["words"], "Draw it from the tube's standard layout, with your brief's "
                                                        "words — not this picture's design")
        # the page is handed the reason and the offers with each concept
        shown = self.client.get("/api/tasks/%d/status/" % self._task_id).json()
        provs = [i.get("reference_provenance") or {} for i in shown.get("images") or []]
        self.assertEqual(len([p for p in provs if (p.get(CHECK_KEY) or {}).get("offers")]), 3, shown.get("images"))
        # his redraw button: redrawn once more, checked again, back at his concepts
        r = self.post("/api/tasks/%d/concept_redraw/" % self._task_id, {"image_id": images[0].pk})
        self.assertEqual(r.status_code, 200, r.content[:800])
        self.expect("awaiting_gate_1", "his redraw")
        self.assertEqual(h.redraws, 1)
        images[0].refresh_from_db()
        child = self.current_task().images.get(reference_provenance__repair_parent_image_id=images[0].pk)
        self.assertTrue(images[0].superseded)
        self.assertEqual(child.reference_provenance[CHECK_KEY]["state"], NOT_DRAWABLE)
        # his template button: the second concept drawn from the tube's standard layout with his brief's words, to the end
        carton = dict(case["carton"], key="complete_product_one_colour (the carton)", statuses=CARTON_STATUSES,
                      product=case["product"], chosen_form=case["form"])
        h.next_stage = carton
        r = self.post("/api/tasks/%d/gate1_approve/" % self._task_id, {"image_id": images[1].pk, "from_template": True})
        self.assertIn(r.status_code, (200, 202), r.content[:800])
        self.container_back_half(dict(case, kind="container", key="complete_product_one_colour (the tube)"))
        self.assertTrue(AgentLog.objects.filter(task_id=self._task_id, action__contains=(
            "drawn from the tube's standard layout with your brief's words — your choice")).exists())
        project.refresh_from_db()
        self.assertEqual(project.status, "packaging", self.said("the tube's gate 2"))
        self._task_id = project.tasks.order_by("pk").last().pk
        h.to_stage(carton)
        self.front_half()
        self.carton_back_half(carton)
        project.refresh_from_db()
        self.assertEqual(project.status, "completed", self.said("the carton's gate 2"))

    # [his answers after the fixes for design 122, 2026-10-08, (2): "never the picture's text. Confirm that holds for
    # every design."] the tube whose picture prints "100 ml / 3.38 fl. oz." and whose brief gives no size: the line is
    # left out by name, no size printed anywhere, the design runs to the end clean
    def test_his_answers_122_a_brief_with_no_size_never_prints_the_pictures(self):
        case = copy.deepcopy(CASES["tube"])
        case["parts"] = with_size_line(case["parts"], SIZE_GOLD)
        case, h, out = self.run_case(case)
        case.setdefault("statuses", STATUSES[case["kind"]])
        faults = Detect(case, h, self.current_task(), out, self.statuses_of(self._task_id)).all()
        self.assertEqual(faults, [])
        self.assertNotIn("100 ml", Detect(case, h, self.current_task(), out, [])._text())

    # [his go of 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at b0f09ca), item 4: "Add it to the wiring check with
    # 122's real concepts."] 122 itself, on its own brief: its three concepts as they stand on the design — the pictures
    # and the reads paid for them (fixtures_122), served as the image service's and the read's answers, nothing paid —
    # each checked drawable before it is shown, none redrawn; then each chosen in turn and drawn to Gate 2: its line art
    # each motif its own named group in its own ink at one width, its frame and its window, its small lines set from his
    # brief (149's size "60 ml ℮ 2 fl oz", never the picture's "100 ml"), the detectors clean.
    # [His test blocker on design 122 at reconstruction, 2026-10-08, item 4: "The wiring check must run each real concept
    # at MY confirmed sizes (122: 120 × 35), not test sizes, so this can't slip through again."] each run as he ran it: at
    # the shape he confirmed (HIS_122_CONFIRMED) and with the name it is drawn with (HIS_122_PRODUCT)
    @staticmethod
    def _his_flats_122(pictures, reads):
        """[His test finding on design 122's drawing, 2026-10-08, A1] each of 122's concepts' flat redraw, as the image
        model answers it: 149's its real one (fixtures_122/concept_149_flat.png); 147's and 148's flat line art in each
        concept's own colours — its body, and its lines' own ink as its photo shows them."""
        from apps.pipeline.services import flat_motif as fm
        here = os.path.join(os.path.dirname(__file__), "fixtures_122")
        out = {}
        for pk, pic in zip((147, 148, 149), pictures):
            sha = hashlib.sha256(pic).hexdigest()
            parts = reads[sha]["parts"]
            body = next(p["colour"] for p in parts if p["kind"] == "field")
            for motif in (p for p in parts if p["kind"] == "motif"):
                if pk == 149:
                    out[(sha, motif["name"])] = open(os.path.join(here, "concept_149_flat.png"), "rb").read()
                    continue
                # each motif in its own colours: its lines' ink, on the colour under its box (its cap's, on a cap)
                under = next((p["colour"] for p in parts if p["kind"] == "closure"
                              and p["box"][1] <= motif["box"][1] and motif["box"][3] <= p["box"][3] + 0.02), body)
                ink = fm.photo_line_ink(pic, motif["box"], under)
                small = (motif["box"][2] - motif["box"][0]) * (motif["box"][3] - motif["box"][1]) < fm.SINGLE_SHARE
                out[(sha, motif["name"])] = flat_art(ink, under, single=small)
        return out

    def _his_real_122(self, chosen, flat_refused=None, carton_directions=None, carton_pictures=None):
        from apps.pipeline.models import ApiCallRecord, DesignProject
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container.readable import CHECK_KEY, DRAWABLE
        here = os.path.join(os.path.dirname(__file__), "fixtures_122")
        pictures = [open(os.path.join(here, "concept_%d.png" % pk), "rb").read() for pk in (147, 148, 149)]
        self._pictures_122 = pictures
        reads = {json.load(open(os.path.join(here, "concept_%d_map.json" % pk)))["source_sha256"]:
                 json.load(open(os.path.join(here, "concept_%d_map.json" % pk))) for pk in (147, 148, 149)}

        def held(task, image_bytes, **kw):
            return copy.deepcopy(reads[hashlib.sha256(image_bytes).hexdigest()])
        self.enterContext(mock.patch.object(dm, "read_parts", side_effect=held))
        case = copy.deepcopy(CASES["complete_product_one_colour"])
        case.update(pictures=pictures, product=dict(HIS_122_PRODUCT), profile=dict(HIS_122_CONFIRMED),
                    flats=self._his_flats_122(pictures, reads))
        if flat_refused:
            case["flat_refused"] = flat_refused
        h = Harness(case, self)
        self._h122 = h
        self.arm(h)
        self.create(case)
        project = DesignProject.objects.order_by("-pk").first()
        self._task_id = project.tasks.order_by("pk").first().pk
        self.expect("awaiting_gate_1", "122's real concepts")
        images = list(self.current_task().images.filter(superseded=False).order_by("pk"))
        self.assertEqual([i.reference_provenance[CHECK_KEY]["state"] for i in images], [DRAWABLE] * 3,
                         [i.reference_provenance[CHECK_KEY] for i in images])
        self.assertEqual(h.redraws, 0)
        self.assertEqual(ApiCallRecord.objects.filter(task_id=self._task_id, operation="container_design_map_parts")
                         .count(), 0, "a read was paid for")
        carton = dict(case["carton"], key="122 (the carton)", statuses=CARTON_STATUSES, product=case["product"],
                      chosen_form=case["form"])
        if carton_directions is not None:
            carton["directions"] = carton_directions     # [his test blocker on design 123, (4)] its planner's answer
        self._carton_122 = carton
        h.next_stage = carton
        if carton_pictures is not None:
            h.queue = list(carton_pictures)              # [his second blocker on 123, (2)] its real concept pictures
        r = self.post("/api/tasks/%d/gate1_approve/" % self._task_id, {"image_id": images[chosen].pk})
        self.assertIn(r.status_code, (200, 202), r.content[:800])
        out = self.container_back_half(dict(case, kind="container", key="122, concept %d" % (147 + chosen)))
        project.refresh_from_db()
        self.assertEqual(project.status, "packaging", self.said("122's tube at gate 2"))
        out.refresh_from_db()
        spec = out.spec_sheet or {}
        shapes = spec.get(dm.SHAPES_SCHEMA) or {}
        sizes = Detect(dict(case, kind="container"), h, self.current_task(), out, [])
        sizes.brief_size()
        self.assertEqual(sizes.faults, [])
        # his confirmed shape, and his brief's name, drawn with its own line as the name
        from apps.pipeline.services import container_contract as cc
        fields = spec[cc.PROFILE_SCHEMA]["fields"]
        self.assertEqual({k: fields["body_%s" % k]["value"] for k in ("height_mm", "width_mm", "depth_mm")},
                         {k: HIS_122_CONFIRMED[k] for k in ("height_mm", "width_mm", "depth_mm")})
        self.assertEqual(spec.get("product_name"), "Rose Blossom Hand Cream")
        self._sizes = sizes
        return spec, shapes, sizes._text()

    # [his test blocker on design 122 at the shape step, 2026-10-08: "I set height 120 mm, diameter 35 mm, ticked the
    # front, back and batch-code print areas and pressed 'Confirm the shape and print areas'. The page came back at the
    # shape step ... no message saying why."] 122's concept 149 confirmed at his own sizes through the site's doors: the
    # confirm moves on — its front on the tube's 54.98 mm face (never 55.0), its back grown with it — and the design is
    # drawn to Gate 2
    def test_his_shape_step_122_at_his_sizes_the_confirm_moves_on(self):
        from apps.pipeline.services import container_contract as cc
        spec, _shapes, _text = self._his_real_122(2)
        zones = {z["zone_id"]: z for z in (spec.get(cc.ZONES_SCHEMA) or {}).get("zones") or []}
        self.assertEqual(spec[cc.PROFILE_SCHEMA]["fields"]["body_height_mm"]["value"], 120.0)
        self.assertLessEqual(zones["z_front"]["width"], 54.98)
        self.assertEqual((zones["z_back"]["width"], zones["z_back"]["height"]),
                         (zones["z_front"]["width"], zones["z_front"]["height"]))

    # [his answers after 122 was redrawn, 2026-10-08, (2): "Fix the front-copy fit check so it measures against MY
    # confirmed print area, not the drawing's own."] 149 at his shape: every line its front types measured against his
    # confirmed front — across and down — never said to be laid in the drawing's own label
    def test_his_answers_122_the_front_copy_is_measured_against_his_confirmed_front(self):
        from apps.ire.compose_dropper import FRONT_COPY_FIT_SCHEMA
        spec, _shapes, _text = self._his_real_122(2)
        fit = spec[FRONT_COPY_FIT_SCHEMA]
        self.assertIn("your confirmed front z_front, 54.9 x 99.9 mm", fit["measured_against"])
        measured = {row["name"] for row in fit["runs"] + fit["name_runs"]}
        self.assertTrue({"product-name-hero-0", "front-descriptor-1-0", "front-descriptor-2-0"} <= measured, measured)
        self.assertEqual({row["state"] for row in fit["vertical_runs"]}, {"HELD"}, fit["vertical_runs"])
        self.assertFalse([c for c in fit["codes"] if "drawing's own label area" in c or "no instrument" in c],
                         fit["codes"])

    # [His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), A: "Never trace motifs from the concept photo. First redraw the motif as a
    # FLAT, front-on, high-resolution artwork ... Trace it as OUTLINES (not centre-lines), keeping thick-and-thin strokes
    # ... Wrap the clean motif onto the form at the concept's layout."; B: "Measure colours from the flat, evenly lit
    # redraw ... check each drawn colour against the concept by eye-level difference (ΔE)"] 149 at his shape: its
    # engraving redrawn flat once — a paid picture — and drawn as that redraw's filled outlines in its own ink, never a
    # stroke traced from the photo; its body the redraw's evenly lit ground; every colour drawn checked by ΔE and held
    def test_his_finding_122_the_motif_is_its_flat_redraws_outlines_and_its_colours_its_own(self):
        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services import flat_motif as fm
        spec, _shapes, _text = self._his_real_122(2)
        self.assertEqual(ApiCallRecord.objects.filter(task_id=self._task_id, operation__startswith="image:flat motif:")
                         .count(), 1)
        out = self.output()
        with out.design_preview_ai.open("rb") as fh:
            self.assertTrue(fh.read(4))
        check = spec[fm.COLOUR_CHECK_SCHEMA]
        self.assertEqual(check["codes"], [], check)
        held = {role: row for role, row in check["roles"].items() if row["state"] == "HELD"}
        self.assertTrue({"body", "line art: red hairline rose and leaf engraving all-over"} <= set(held), check)
        # [his goal for the pitch, 2026-10-15, B (5)] the cap drawn in the photo's lit face is never checked against
        # that same colour (it would always hold): the designer's eye judges it against the concept
        if "cap" in check["roles"]:
            self.assertEqual(check["roles"]["cap"]["state"], "NOT_IN_THE_CONCEPT", check)
        line = held["line art: red hairline rose and leaf engraving all-over"]
        # its real flat redraw's ink — a raspberry red — against its photo's own lines, read alike; never the photo's
        # brownish #BA5C5D the photo's median read
        self.assertLess(line["delta_e"], 3.0, line)
        self.assertGreater(fm.delta_e(line["drawn"], "#BA5C5D"), fm.COLOUR_DE_MAX, line)
        # the cap drawn on its evenly lit face, the product where the concept's map finds it
        drawn_map = spec.get("container_design_map/1.0") or {}
        self.assertEqual(check["roles"]["cap"]["drawn"],
                         fm.lit_face(self._pictures_122[2], [0.1932, 0.8647, 0.8136, 1.015], drawn_map.get("product_box_px")))

    def test_his_finding_122_its_back_fills_its_panel_its_languages_balanced(self):
        """[His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), C:
        "Back label laid out like packaging, using the whole area: clear hierarchy, the three languages as balanced
        blocks; never cramped at the bottom with empty space below."] 149 at his shape: its back grown from its print
        size, its languages each a block with the height shared between them, its last line near its foot."""
        from apps.ire import back_panel as bp
        spec, _shapes, _text = self._his_real_122(2)
        back = spec[bp.SCHEMA]
        self.assertTrue(back["fits"] and back["size_pt"] > back["grown_from_pt"], back["size_pt"])
        self.assertGreater(back["block_gap_mm"], 0.0)
        last = max(e["baseline_mm"] for e in back["lines"])
        self.assertLess(back["height_available_mm"] - last, 0.1 * back["height_available_mm"], back)

    def test_goal_1013_never_stops_122_a_motif_whose_flat_redraw_cannot_be_made_goes_on_said_in_words(self):
        """[His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), A1;
        his goal of 2026-10-13, (1): "NO check ever stops a design"] the flat redraw refused: the motif is not drawn —
        never the photo traced in its place — and the design goes on, the motif said beside Approve in words; it
        stopped back at its shape step until then."""
        from apps.pipeline.services import flat_motif as fm
        spec, _shapes, _text = self._his_real_122(2, flat_refused="the picture service could not be reached")
        rows = spec["checks_shown/1.0"]
        self.assertTrue(any(r["code"] == fm.FLAT_REFUSED and r["what"].startswith(
            "the motif's flat artwork could not be made") for r in rows), rows)
        self.assertTrue(any("the motif's flat artwork could not be made" in s for s in spec["self_check/1.0"]["said"]))

    # [His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (4): "Add the
    # container-to-carton hand-over with a real approved container to the wiring check."] 122 — concept 149 at his
    # shape, drawn and approved: his real approved container — handed over to its carton, 123: the carton planned as
    # its continuation, drawn and approved through the site's doors
    def _his_real_123(self, directions, pictures=None):
        from apps.pipeline.models import DesignProject
        self._his_real_122(2, carton_directions=directions, carton_pictures=pictures)
        project = DesignProject.objects.order_by("-pk").first()
        self._task_id = project.tasks.order_by("pk").last().pk
        self.assertEqual(self.current_task().stage, "packaging")
        self.expect("awaiting_gate_1", "123, the carton of the approved 122")
        return project

    @staticmethod
    def _one_look(noun):
        """The carton's three directions as a planner continuing its container writes them: one mood, motif, type and
        colours — the container's — each its own layout."""
        from apps.pipeline.tests.test_design_direction_generator import _one_look
        return _one_look(_directions_for(noun))

    def test_his_blocker_123_the_carton_continues_its_real_approved_container(self):
        """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (1), (3)
        and (4).] 122's approved tube handed to its carton: the planner told it continues it — its rule, the tube's
        chosen direction, the colours its drawing prints, the faces it sets — and its three of one look and three
        layouts pass at once, no note; the carton drawn and approved: its flaps and sides the tube's own line art in
        the tube's ink, its inside our own petal flowers (his brief: "bold berry petal flowers ... redrawn in our own
        shapes"), every detector clean."""
        from apps.dashboard.words import alike_words
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
        from apps.pipeline.models import AgentLog
        from apps.pipeline.targets import composite as cx
        project = self._his_real_123(self._one_look(self._carton_122_noun()))
        carton = self.current_task()
        tube = project.tasks.order_by("pk").first()
        h = self._h122
        asked = h.asks["creative_directions"][-1]
        self.assertIn("## This design continues its approved container — READ FIRST", asked)
        self.assertIn("THREE LAYOUTS OF ONE APPROVED LOOK", asked)
        self.assertIn(cx.continuation_words(carton), asked)
        tube_spec = tube.packaging_outputs.order_by("-pk").first().spec_sheet
        line = tube_spec["container_colour_check/1.0"]["roles"]["line art: red hairline rose and leaf engraving all-over"]
        self.assertIn(line["drawn"], asked)                                  # the colour its drawing prints
        self.assertIn("Its type, as its drawing sets it:", asked)
        planned = AgentLog.objects.get(task=carton, action="ARIA: structured directions validated").payload
        self.assertIsNone(planned[SHOWN_ALIKE_KEY])
        self.assertEqual(alike_words(carton), [])
        self.assertEqual(len(h.asks["creative_directions"]), 2)              # the tube's plan, and the carton's, once
        art = cx.continued_line_art(carton)
        self.assertEqual((art["part"], art["source_task_id"]),
                         ("red hairline rose and leaf engraving all-over", tube.pk))
        self.front_half()
        case = dict(self._carton_122, key="123")
        out = self.carton_back_half(case)
        project.refresh_from_db()
        self.assertEqual(project.status, "completed", self.said("123's gate 2"))
        out.refresh_from_db()
        faults = Detect(dict(case, kind="carton"), h, carton, out, self.statuses_of(carton.pk)).all()
        self.assertEqual(faults, [], "\n".join(faults))
        # the drawing: each dust flap and the bottom tuck, and each side's graphic, the tube's line art in its ink;
        # the inside our own petal flowers
        from apps.ire.compose import INSIDE_KEY
        self.assertEqual((out.spec_sheet.get(INSIDE_KEY) or {}).get("motif"), "flower", out.spec_sheet.get(INSIDE_KEY))
        import fitz
        with out.design_preview_ai.open("rb") as fh:
            drawn = fitz.open(stream=fh.read(), filetype="pdf")
        ink = tuple(int(art["ink"][i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        tube_ink = [d for d in drawn[0].get_drawings() if d.get("fill") and max(
            abs(a - b) for a, b in zip(d["fill"], ink)) < 0.02]
        self.assertGreaterEqual(len(tube_ink), 5, "the tube's line art on the carton's flaps and sides")

    def test_his_second_blocker_123_a_concept_shown_drawable_draws(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "The
        check before I see the concepts and the check at drawing time must agree: a concept shown as drawable must
        draw. Make them one check, and add it to the wiring check with 123's real concepts."]
        122's approved tube handed to its carton, its three concepts 123's real pictures, each read as its real read
        was (Garden Wrap by the read that stopped it, its scalloped band named a "band"): each checked before it is
        shown — the one check: Garden Wrap drawable; Blossom Arch not yet, its oval read in its line art's pink and
        traced as the pale ground round its rose, said in words; Stem Journey drawable — [his test findings on design
        123, 2026-10-09 (transcribed at cbdf721), (4): "Text collisions are fixed by spacing or shrinking, never
        refused"] its "Hand Cream /" and its Arabic, set onto each other where its front is drawn, spaced apart there.
        Garden Wrap chosen, read nothing again, its size confirmed, drawn and approved; its front drawn as the picture
        prints it — its band at the foot and edge to edge, its name at one size, no line ending in a separator, its mark
        inside its oval. And its first read, which sets "Hand Cream" onto "Blossom" where it draws, settles: spaced,
        measured clear on the drawn file."""
        import json

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container.readable import CHECK_KEY, DRAWABLE, NOT_DRAWABLE
        here = os.path.join(os.path.dirname(__file__), "fixtures_123")
        pictures = [open(os.path.join(here, "concept_%d.png" % pk), "rb").read() for pk in (150, 151, 152)]
        reads = {}
        for pk in (150, 151, 152):
            rec = json.load(open(os.path.join(here, "concept_%d_map.json" % pk)))
            reads[rec["source_sha256"]] = rec
        asked = []

        def held(task, image_bytes, **kw):
            asked.append(hashlib.sha256(image_bytes).hexdigest())
            self._h122.calls.append("container_design_map_parts")          # the paid step, run — its real read
            return copy.deepcopy(reads[asked[-1]])
        self.enterContext(mock.patch.object(dm, "read_carton_parts", side_effect=held))
        project = self._his_real_123(self._one_look(self._carton_122_noun()), pictures=pictures)
        carton = self.current_task()
        images = list(carton.images.filter(superseded=False).order_by("pk"))
        checks = [i.reference_provenance[CHECK_KEY] for i in images]
        self.assertEqual([c["state"] for c in checks], [DRAWABLE, NOT_DRAWABLE, DRAWABLE], checks)
        self.assertEqual([(p["kind"], p["name"]) for p in checks[1]["parts"]],
                         [("shape", "oval cartouche frame with rose and vines illustration")])
        self.assertIn("pale ground", checks[1]["why"])
        self.assertNotRegex(checks[1]["why"], r"[A-Z]{2,}_[A-Z]")                 # in words, never a code
        self.assertEqual(len(asked), 3)                                     # each read once, before it is shown
        garden = next(i for i in images if hashlib.sha256(i.image_file.open("rb").read()).hexdigest()
                      == hashlib.sha256(pictures[0]).hexdigest())
        r = self.post("/api/tasks/%d/gate1_approve/" % carton.pk, {"image_id": garden.pk})
        self.assertIn(r.status_code, (200, 202), r.content[:800])
        self.assertEqual(len(asked), 3)                                     # chosen: read nothing again
        # its reads are 123's own, served in the read's place, so on no ledger row of this run; the picture the image
        # step made for it, Garden Wrap's own
        case = dict(self._carton_122, key="123, Garden Wrap",
                    calls=[op for op in CALLS["carton"] if op != "container_design_map_parts"])
        out = self.carton_back_half(case)
        project.refresh_from_db()
        self.assertEqual(project.status, "completed", self.said("123's gate 2"))
        out.refresh_from_db()
        self._h122.picture = pictures[0]
        faults = Detect(dict(case, kind="carton"), self._h122, carton, out, self.statuses_of(carton.pk)).all()
        self.assertEqual(faults, [], "\n".join(faults))
        # measured through the real path: the .ai's own composer, from the front on its record
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.pipeline.services.native_handoff import carton_map_front
        from django.conf import settings as django_settings

        from apps.ire import brand_mark
        from apps.ire.compose import compose_components_graph
        params = DielineInputJSON(**out.dieline_job.input_json)
        coords = calculate_dieline(params)
        # composed as production's own .ai (``native_handoff._carton_document``), handed the house's approved master —
        # the suite switches its lookup off ("a test that wants the vector mark hands a composer a master of its own")
        path = os.path.join(django_settings.BASE_DIR, *brand_mark.MARK_DIR, brand_mark.MASTER_FILE)
        master = brand_mark.read_master(open(path, "rb").read(), path=path)
        front_map = carton_map_front(out)
        doc = compose_components_graph(coords, logo_path=None, product_name=params.metadata.product_name,
                                       subtitle=params.metadata.product_type,
                                       panel_info=(out.spec_sheet or {}).get("panel_info"), map_front=front_map,
                                       safe_margin_mm=params.print_settings.safe_margin_mm,
                                       **({"tint": front_map["ground"]} if front_map.get("ground") else {}),
                                       **brand_mark.master_kwargs(master))
        fp = next(p for p in coords.panels if p.name == "front")
        bx0, by0, _bx1, _by1 = coords.bleed_polygon.bounds

        def frac(x, y):
            return (x - (fp.x - bx0 + 10.0)) / fp.width, (y - (fp.y - by0 + 10.0)) / fp.height
        nodes = []

        def walk(n):
            nodes.append(n)
            for c in getattr(n, "children", None) or []:
                walk(c)
        walk(doc.root)

        def extent(n):
            pts = [frac(getattr(g, a), getattr(g, b)) for g in n.segments for a, b in (("x", "y"), ("x1", "y1"))
                   if hasattr(g, a)]
            return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)
        # [his goal of 2026-10-10, item 5] the one scallop round the carton, in the picture's band's place
        band = next(n for n in nodes if str(getattr(n, "name", "")).startswith("scallop-band-"))
        bx_0, by_0, bx_1, by_1 = extent(band)
        self.assertLess(bx_0, 0.0)                                          # edge to edge, into the bleed
        self.assertGreater(bx_1, 1.0)
        self.assertAlmostEqual(by_1, 1.0, places=3)                         # to the fold at its foot, never onto the tuck
        self.assertGreater(by_0, 0.85)
        hero = [n for n in nodes if str(getattr(n, "name", "")).startswith("product-name-hero")]
        self.assertEqual(sorted(n.text for n in hero), ["Blossom", "Rose"])
        self.assertLess(abs(hero[0].size_pt - hero[1].size_pt), 0.03 * hero[0].size_pt)
        typed = [n for n in nodes if getattr(n, "type", "") == "text" and str(getattr(n, "name", "")).startswith("front-")]
        self.assertFalse([n.text for n in typed if n.text.rstrip()[-1:] in "•·|/"], [n.text for n in typed])
        oval = next(n for n in nodes if str(getattr(n, "name", "")).startswith("window-map-"))
        ox0, oy0, ox1, oy1 = extent(oval)
        mark = next(n for n in nodes if getattr(n, "name", "") == "logo-front")
        mx, my = frac(mark.x + mark.w / 2.0, mark.y + mark.h / 2.0) if hasattr(mark, "w") else extent(mark)[0:2]
        self.assertTrue(ox0 < mx < ox1 and oy0 < my < oy1, ((mx, my), (ox0, oy0, ox1, oy1)))
        # its first read, the one shown before the stop, drawn on his confirmed size: "Hand Cream" set onto "Blossom",
        # spaced, and measured clear on the drawn file; and Stem Journey's two lines, set onto each other, spaced apart
        from apps.pipeline.targets.container import product_name_for, type_sources_for
        from apps.pipeline.targets.packaging import (SETTLE_CLEAR_MM, PackagingTarget, drawing_size, drawn_copy_laps,
                                                     settle_front_copy)
        dims = drawing_size(out)
        for pk, read in ((150, "concept_150_map_first.json"), (152, "concept_152_map.json")):
            rec = json.load(open(os.path.join(here, read)))
            pic = pictures[(150, 151, 152).index(pk)]
            front = PackagingTarget().carton_front(carton, {dm.SCHEMA: rec, dm.SHAPES_SCHEMA: dm.trace_shapes(
                pic, rec, sources=type_sources_for(carton, product_name_for(carton, carton.product)[0], carton=True))},
                pic, [])
            self.assertTrue(drawn_copy_laps(carton, front, dims), read)          # set onto each other as read
            settled = settle_front_copy(carton, front, dims)
            self.assertEqual(drawn_copy_laps(carton, settled, dims, clear_mm=SETTLE_CLEAR_MM), [], read)   # clear space
            self.assertEqual({how["how"] for how in settled["copy_settled"]}, {"spaced"}, settled["copy_settled"])

    def test_goal_1010_wiring_item5_the_band_traced_ragged_again(self):
        # [his goal of 2026-10-10, item 5] the one scallop taken out: 123's real Garden Wrap drawn with the picture's
        # traced band on its front alone, and the detector names it
        self.enterContext(mock.patch("apps.ire.compose.scallop_round", lambda mc, *a, **k: ([], mc, None)))
        with self.assertRaises(AssertionError) as caught:
            self.test_his_second_blocker_123_a_concept_shown_drawable_draws()
        self.assertIn("SCALLOP_NOT_ONE", str(caught.exception))

    def test_his_second_blocker_123_a_standalone_cartons_line_art_is_redrawn_flat_before_it_is_traced(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
        "a standalone carton gets the same flat redraw before tracing (tell me the cost)".] A carton of no project, its
        concept 123's Garden Wrap: its rose field redrawn flat once — one paid picture, kept — and drawn as that
        redraw's outlines in their own ink, never a stroke traced from the photo; drawn and approved."""
        import json

        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services import concept_design_map as dm
        here = os.path.join(os.path.dirname(__file__), "fixtures_123")
        pic = open(os.path.join(here, "concept_150.png"), "rb").read()
        rec = json.load(open(os.path.join(here, "concept_150_map.json")))
        self.enterContext(mock.patch.object(dm, "read_carton_parts", side_effect=lambda task, image_bytes, **kw:
                                            copy.deepcopy(rec)))
        sha = hashlib.sha256(pic).hexdigest()
        line = "rose and foliage line illustration"
        case = copy.deepcopy(CASES["packaging"])
        alone = BRIEF_122.replace("hand cream in a squeeze tube with a flip-top cap, plus its tall\ncarton (reverse "
                                  "tuck end).", "hand cream, in its tall carton (reverse tuck end).")
        alone = alone.split("\n\n[Container type:")[0]                   # a carton of its own: no container's tag
        self.assertNotIn("tube", alone)                               # … and no tube in its brief
        case.update(key="123 as a carton of its own", brief=alone, pictures=[pic, pic, pic],
                    product=_product("WC-CARTON-123", "Rose Blossom Hand Cream", "hand cream", width_mm=42,
                                     depth_mm=27, height_mm=134),
                    flats={(sha, line): flat_art(*FLAT_122)},
                    calls=[op for op in CALLS["carton"] if op != "container_design_map_parts"])
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        self.front_half()
        out = self.carton_back_half(case)
        self.expect("completed", "123 as a carton of its own")
        self.assertEqual(h.flats, 1)
        self.assertEqual(ApiCallRecord.objects.filter(task_id=self._task_id, operation__startswith="image:flat motif:")
                         .count(), 1)
        from apps.pipeline.services.native_handoff import carton_map_front
        front = carton_map_front(out)
        lines, = front["shapes"]["lines"]
        self.assertEqual(lines["flat"]["state"], "TRACED")
        self.assertNotIn("continued", lines)
        h.picture = pic                                   # the picture the image step made: Garden Wrap's own
        faults = Detect(dict(case, kind="carton", statuses=STATUSES["carton"]), h, self.current_task(), out,
                        self.statuses_of(self._task_id)).all()
        self.assertEqual(faults, [], "\n".join(faults))

    def _carton_122_noun(self):
        return CASES["complete_product_one_colour"]["carton"]["noun"]

    def test_his_blocker_123_a_carton_still_too_alike_after_its_retry_is_shown_with_its_note(self):
        """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (2) and
        (4): "Every "not distinct" check: it never stops a design. On failure it retries once with the reason; if it
        still fails, it shows me the three anyway with a note, and I choose."] 122's carton planned twice in one
        layout: retried once with the reason, then drawn to Gate 1 — never stopped — the page saying why, in words."""
        from apps.dashboard.words import alike_words
        planted = self._one_look(self._carton_122_noun())
        for n, direction in enumerate(planted["directions"]):
            direction["layout_structure"] = ("a repeating pattern wraps all faces edge to edge", "a repeating "
                                             "pattern across every face with a quiet base", "a repeating pattern on "
                                             "all faces, the logo above")[n]
        self._his_real_123(planted)
        carton = self.current_task()
        self.assertEqual(len(self._h122.asks["creative_directions"]), 3)       # the tube's, and the carton's twice
        self.assertIn("COMPOSITION_NOT_DISTINCT", self._h122.asks["creative_directions"][-1])
        self.assertEqual(alike_words(carton), [
            "Shown anyway: the three directions came back too alike twice — they shared one layout; made once more "
            "with that reason, they did not change. You choose."])
        self.assertEqual(carton.images.filter(superseded=False).count(), 3)
        st = self.client.get("/api/tasks/%d/status/" % carton.pk).json()
        self.assertEqual(st["gate_1_alike_words"], alike_words(carton))

    def test_his_go_122_concept_147_its_red_rose_drawn_in_line_art(self):
        _spec, shapes, _text = self._his_real_122(0)
        lines = shapes.get("lines") or []
        self.assertEqual([ln["part"] for ln in lines], ["red line-art rose with stem and leaves"])
        self.assertFalse(lines[0]["gold"])

    def test_his_go_122_concept_148_its_frame_its_threads_and_its_set_lines(self):
        _spec, shapes, _text = self._his_real_122(1)
        self.assertEqual([f["shape"] for f in shapes.get("frames") or []], ["quad"])
        self.assertEqual(sorted(ln["part"] for ln in shapes.get("lines") or []),
                         ["red line-art stems tendrils and buds threading type", "small red line-art rosebud on cap face"])
        self.assertEqual(sorted(t["part"] for t in shapes.get("types") or [] if t.get("set")),
                         ["Arabic subcopy", "Hand Cream subcopy"])

    def test_his_go_122_concept_149_its_engraving_its_oval_window_and_his_size(self):
        _spec, shapes, text = self._his_real_122(2)
        self.assertEqual([f["shape"] for f in shapes.get("frames") or []], ["ellipse"])
        self.assertEqual([wd["shape"] for wd in shapes.get("windows") or []], ["ellipse"])
        self.assertEqual([ln["part"] for ln in shapes.get("lines") or []], ["red hairline rose and leaf engraving all-over"])
        # [re-pinned by his goal of 2026-10-10, item 8: "it must be the real estimated sign everywhere"] his words, the sign drawn as itself between them
        self.assertIn("60 ml 2 fl oz", text)
        self.assertNotIn("℮", text)
        self.assertIn("60 ml 2", [w for w, _box, _pt in self._sizes.signs()])
        self.assertNotIn("100 ml", text)

    def test_every_design_type_has_a_case(self):
        from apps.pipeline.targets.composite import COMPOSITE_RECIPES
        from apps.pipeline.targets.container.archetypes import ARCHETYPES
        from apps.pipeline.targets.ui import TARGET_CARDS
        cards = {c["value"] for c in TARGET_CARDS if c["active"]}
        covered = {c["target"] for c in CASES.values()} | {"product_container"}
        self.assertEqual(cards - covered, set(), "a New design card with no case")
        self.assertEqual((set(ARCHETYPES) | {"dropper"}) - set(CASES), set(), "a container form with no case")
        self.assertEqual(set(COMPOSITE_RECIPES) - set(CASES), set(), "a composite recipe with no case")


def _case_test(key):
    def test(self):
        self.check(key)
    test.__name__ = "test_%s" % key
    test.__doc__ = "%s: brief to finished file, the seven detectors clean" % key
    return test


for _key in CASES:
    if "test_%s" % _key not in vars(WiringCheckTests):      # a case whose test says more is written out above
        setattr(WiringCheckTests, "test_%s" % _key, _case_test(_key))


def _held_unfolding(case):
    """[His second goal of 2026-10-06, item 2] a planted run whose die does not fold: held at Gate 2 by name."""
    case["stop"] = {"codes": ["DIELINE_FOLD_CHECK_FAILED"]}
    case["statuses"] = [s for s in STATUSES[case["kind"]] if s != "completed"]


def _held_not_trilingual(case):
    """[His review of 119, 2026-10-05, point 1: "labels stay trilingual (English, Spanish, Arabic)."] A planted run whose
    label lacks a language stops at Gate 2 with exactly CARTON_LABEL_NOT_TRILINGUAL."""
    case["stop"] = {"codes": ["CARTON_LABEL_NOT_TRILINGUAL"]}


class PlantedFaultTests(_Run):
    """Each detector proved by a fault planted through the real path — the case runs as production runs it, one wire is
    broken where production could break it, and the detector of that kind names it. A detector that stays silent here
    proves nothing anywhere."""

    def planted(self, key, kind, *patches, settings=None, mutate=None):
        case = copy.deepcopy(CASES[key])
        if mutate:
            mutate(case)
        for target, wrapper in patches:
            self.enterContext(mock.patch(target, wrapper))
        if settings:
            self.enterContext(override_settings(**settings))
        case, h, out = self.run_case(case)
        case.setdefault("statuses", STATUSES[case["kind"]])
        faults = Detect(case, h, self.current_task(), out, self.statuses_of(self._task_id)).all()
        self.assertTrue(any(f.startswith(kind + ":") for f in faults),
                        "the planted %s fault went unseen; the detectors said: %s" % (kind, faults))
        return faults

    def test_s122_the_pictures_size_printed_again(self):
        # [his answers after the fixes for design 122, (2)] the size rule taken out: the tube's picture's "100 ml / 3.38
        # fl. oz." is drawn in the picture's own words again, and the detector names it
        def sized(case):
            case["parts"] = with_size_line(case["parts"], SIZE_GOLD)
        self.planted("tube", "SIZE_NOT_BRIEFS",
                     ("apps.pipeline.services.concept_design_map.size_stated", lambda text: None), mutate=sized)

    def _trend_run(self, *patches):
        """[His goal of 2026-10-10, item 3] the palette case searched with pictures: the open web's two finds fetched
        from a stand-in host and read, then the board as the page shows it, by the detectors of items 3 and 4."""
        from apps.pipeline.services import trend_board
        served = {"https://%s.example/picture.png" % host: _trend_png(rgb, n)
                  for n, (host, (rgb, _form)) in enumerate(sorted(TREND_FINDS.items()))}

        class _Served:
            def __init__(self, body):
                self.status_code, self.headers, self._body = 200, {"content-type": "image/png"}, body

            def iter_content(self, chunk_size=65536):
                for i in range(0, len(self._body), chunk_size):
                    yield self._body[i:i + chunk_size]

            def close(self):
                pass

        def get(url, *, headers, timeout):
            return _Served(served[url])
        real = trend_board.build
        self.enterContext(mock.patch.object(trend_board, "build", lambda task, **k: real(
            task, http_get=get, robots=lambda url, ua: "allowed", log=k.get("log"))))
        self.enterContext(mock.patch("apps.pipeline.services.web_research.check_url_policy"))
        self.enterContext(override_settings(WEB_QUARANTINE_ROOT=self.dir))
        for patch in patches:
            self.enterContext(patch)
        case = dict(copy.deepcopy(CASES["palette"]), key="trend_filter", trend_pictures=True, trend_product="palette")
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        found = Detect(case, h, self.current_task(), None, self.statuses_of(self._task_id))
        found.trend_junk()
        return found.faults, trend_board.payload(self.current_task())

    def test_goal_1010_wiring_item3_the_trend_board_shows_only_the_product(self):
        # [his goal of 2026-10-10, items 3 and 4] the palette's own picture shown, the gloss left out by what it shows,
        # every search in the product's own words
        faults, board = self._trend_run()
        self.assertEqual(faults, [], faults)
        self.assertEqual(len(board["pictures"]), 1)
        self.assertIn({"words": "a picture of another product (lip gloss), not an eyeshadow palette", "count": 1},
                      board["left_out"])

    def test_goal_1010_wiring_item3_a_picture_of_another_product_shown_again(self):
        # [his goal of 2026-10-10, item 3] the product check taken out: the gloss is shown again, and the detector
        # names it
        faults, _board = self._trend_run(mock.patch("apps.pipeline.services.trend_board.names_the_product",
                                                    lambda *a, **k: True))
        self.assertTrue(any(f.startswith("TREND_JUNK_SHOWN:") for f in faults), faults)

    def test_goal_1010_wiring_item1_a_planner_check_stops_a_design_again(self):
        # [his goal of 2026-10-10, item 1: "NO planner check ever stops a design"] the shown path taken out of the
        # planner: its refusal stops the design again, and the detector names it
        from apps.pipeline import design_direction_generator as gen
        real = gen._validate
        self.enterContext(mock.patch.object(gen, "_validate", lambda *a, **k: real(*a, **dict(k, keep_shown=False))))
        case = copy.deepcopy(CASES["planner_note"])
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        found = Detect(case, h, self.current_task(), None, self.statuses_of(self._task_id))
        found.planner_stopped()
        self.assertTrue(any(f.startswith("PLANNER_STOPPED:") for f in found.faults), found.faults)

    def test_goal_1010_wiring_item1_the_planner_note_reads_in_words(self):
        # [his goal of 2026-10-10, item 1: "it shows me the three directions with a plain note"] the planner_note case
        # at Gate 1: its three shown, the note in words
        from apps.dashboard.words import alike_words
        case = copy.deepcopy(CASES["planner_note"])
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        self.expect("awaiting_gate_1", "the planner's note")
        self.assertEqual(alike_words(self.current_task()), [
            "Shown anyway: the three directions failed their checks twice — a direction needed a photographic "
            "picture, which can't go into print-ready artwork; made once more with that reason, they still did. "
            "You choose."])

    def _with_number(self, case):
        case["product"] = dict(case["product"], barcode_ean="5061030633823")

    def test_goal_1010_wiring_item7_his_barcode_whole_inside_the_sticker(self):
        # [his goal of 2026-10-10, item 7] a carton with his number: drawn whole, inside its sticker, quiet zones clear
        case = copy.deepcopy(CASES["packaging"])
        self._with_number(case)
        case, h, out = self.run_case(case)
        case.setdefault("statuses", STATUSES[case["kind"]])
        faults = Detect(case, h, self.current_task(), out, self.statuses_of(self._task_id)).all()
        self.assertEqual(faults, [], "\n".join(faults))

    def test_goal_1010_wiring_item7_the_barcode_cut_short_again(self):
        # [his goal of 2026-10-10, item 7] its bars cut short of their own height again, as 123's were: named
        self.planted("packaging", "EAN_CUT", ("apps.dielines.exporters.label_layout.EAN_NOMINAL_BAR_MM", 4.0),
                     mutate=self._with_number)

    def _with_sign(self, case):
        # his brief gives the size with its sign, as 123's does ("60 ml \u212e 2 fl oz"), and the record carries it
        case["brief"] = case["brief"].replace("a face serum.\n", "a face serum.\nSize: 30 ml \u212e 1 fl oz\n", 1)
        case["product"] = dict(case["product"], net_weight="30 ml \u212e 1 fl oz")

    def test_goal_1010_wiring_item8_the_sign_drawn_as_itself(self):
        # [his goal of 2026-10-10, item 8] a carton whose net weight carries the sign: drawn as the sign, never a face's
        case = copy.deepcopy(CASES["packaging"])
        self._with_sign(case)
        case, h, out = self.run_case(case)
        case.setdefault("statuses", STATUSES[case["kind"]])
        faults = Detect(case, h, self.current_task(), out, self.statuses_of(self._task_id)).all()
        self.assertEqual(faults, [], "\n".join(faults))

    def test_goal_1010_wiring_item8_the_sign_left_to_a_face_again(self):
        # [his goal of 2026-10-10, item 8] the sign left to the face again — drawn as its "e" — and the detector names it
        def plain(c, x, y, text, face, size, align="left"):
            {"center": c.drawCentredString, "right": c.drawRightString}.get(align, c.drawString)(x, y, text)
        self.planted("packaging", "ESTIMATED_SIGN_AS_LETTER", ("apps.ire.estimated_sign.draw_text", plain),
                     mutate=self._with_sign)

    def test_l123_the_layout_picture_skipped_silently(self):
        # [his test findings on design 123, 2026-10-09, (1): "NO GUESSED PANELS"] the layout's panels dropped without a
        # word: the back and the sides drawn with no word of where they came from
        self.planted("packaging", "PANELS_GUESSED",
                     ("apps.pipeline.targets.carton_layout.panel_fronts", lambda *a, **k: {}))

    def test_l122_the_line_tracer_taken_out(self):
        # [his go of 2026-10-08, item 4] the line-art tracer taken out: 122's real concepts are refused again before they
        # are shown — each said in words, with his offers
        from apps.pipeline.models import DesignProject
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container.readable import CHECK_KEY, NOT_DRAWABLE
        here = os.path.join(os.path.dirname(__file__), "fixtures_122")
        pictures = [open(os.path.join(here, "concept_%d.png" % pk), "rb").read() for pk in (147, 148, 149)]
        reads = {json.load(open(os.path.join(here, "concept_%d_map.json" % pk)))["source_sha256"]:
                 json.load(open(os.path.join(here, "concept_%d_map.json" % pk))) for pk in (147, 148, 149)}
        self.enterContext(mock.patch.object(dm, "read_parts", side_effect=lambda task, b, **kw: copy.deepcopy(
            reads[hashlib.sha256(b).hexdigest()])))
        self.enterContext(mock.patch("apps.pipeline.services.line_art.trace_lines",
                                     lambda *a, **k: {"refused": "the line tracer taken out"}))
        case = copy.deepcopy(CASES["complete_product_one_colour"])
        case["pictures"] = pictures
        self.arm(Harness(case, self))
        self.create(case)
        self._task_id = DesignProject.objects.order_by("-pk").first().tasks.order_by("pk").first().pk
        self.expect("awaiting_gate_1", "122's real concepts, the line tracer taken out")
        checks = [i.reference_provenance[CHECK_KEY] for i in self.current_task().images.filter(superseded=False)
                  .order_by("pk")]
        self.assertEqual([c["state"] for c in checks], [NOT_DRAWABLE] * 3)
        self.assertIn("red line-art rose with stem and leaves", checks[0]["why"])

    def test_1_a_silent_fallback_the_map_read_switched_off_mid_run(self):
        self.planted("packaging", "SILENT_FALLBACK", settings=dict(DESIGN_MAP_READ=False))

    def test_2_ai_pixels_the_concept_placed_on_the_carton(self):
        from apps.ire import compose as real_compose
        from apps.ire.nodes import image_node
        real = real_compose.compose_components_graph
        concept = os.path.join(self.dir, "planted_concept.png")

        def placed(*a, **k):
            doc = real(*a, **k)
            with open(concept, "wb") as fh:
                fh.write(paint(CASES["packaging"]["parts"]))
            doc.root.children.append(image_node("planted-concept", concept, 0.0, 0.0, 40.0, 60.0))
            return doc
        self.planted("packaging", "AI_PIXELS", ("apps.ire.compose.compose_components_graph", placed))

    def test_3_the_briefs_copy_dropped_before_the_export(self):
        from apps.pipeline.agents.dieline_agent import DielineAgent
        real = DielineAgent.generate

        def dropped(agent, job, confirmed_dims, *a, **k):
            k["panel_info"] = None
            return real(agent, job, confirmed_dims, *a, **k)
        self.planted("packaging", "BRIEF_COPY_MISSING",
                     ("apps.pipeline.agents.dieline_agent.DielineAgent.generate", dropped))

    def test_4_another_products_words_reach_the_cartons_panels(self):
        from apps.pipeline.agents.dieline_agent import DielineAgent
        real = DielineAgent.generate

        def swapped(agent, job, confirmed_dims, *a, **k):
            k["panel_info"] = dict(k.get("panel_info") or {}, description="%s, %s" % (DECOY["name"],
                                                                                     DECOY["product_type"]))
            return real(agent, job, confirmed_dims, *a, **k)
        # [his review of 119, 2026-10-05, point 1] another product's words, untranslated on the label, now hold Gate 2
        # by name; the detector still names the words printed
        self.planted("packaging", "OTHER_PRODUCT_TEXT",
                     ("apps.pipeline.agents.dieline_agent.DielineAgent.generate", swapped), mutate=_held_not_trilingual)

    def test_5_the_planner_answers_for_another_product(self):
        def bottle_words(case):
            case["prompt_words"] = ("a tall pump bottle with a gold pump closure and a deep rose body, the name set in "
                                    "cream across its middle, pictured straight-on on a plain warm grey ground")
        self.planted("jar", "WRONG_PRODUCT_WORDS", mutate=bottle_words)

    def test_c8_a_broken_line_keeps_its_separator(self):
        # [his final goal, 2026-10-05, C8] the separator's rule switched off: the broken foot line ends with its "·"
        self.planted("carton_foot", "SEPARATOR_AT_BREAK",
                     ("apps.ire.text_script.drop_break_separators", lambda lines: list(lines)))

    def test_c5_a_label_set_under_its_floor(self):
        # [his final goal, 2026-10-05, C5: "never go below the floor"] the layout's first step set under the floors
        from apps.dielines.exporters import label_layout
        real = label_layout.steps

        def under(fonts):
            # [his correction of 2026-10-07] 3 pt is the floor now; under it is 2.5
            yield {"face": "regular", "body": 2.5, "fine": 2.5, "title": 3.25}
            yield from real(fonts)
        self.planted("packaging", "LABEL_UNDER_FLOOR", ("apps.dielines.exporters.label_layout.steps", under))

    def test_c5_a_label_block_drawn_on_a_side(self):
        # [his final goal, C5: "Never mix vertical side copy with label blocks"] the warnings set beside the side copy
        from apps.ire import compose as real_compose
        from apps.ire.graph import Color, TextRun
        real = real_compose.compose_components_graph

        def scattered(coords, *a, **k):
            doc = real(coords, *a, **k)
            side = next(p for p in coords.panels if p.name == "side_left")
            gx = coords.bleed_polygon.bounds[0] - real_compose._PAGE_MARGIN_MM
            gy = coords.bleed_polygon.bounds[1] - real_compose._PAGE_MARGIN_MM
            doc.root.children.append(TextRun(name="planted-warnings", text="WARNINGS: For external use only.",
                                             x=side.x - gx + 2.0, y=side.y - gy + 20.0, size_pt=5.0,
                                             color=Color.from_hex("#333333")))
            return doc
        self.planted("packaging", "LABEL_SCATTERED", ("apps.ire.compose.compose_components_graph", scattered))

    def test_b1_an_inside_drawn_blank(self):
        # [his final goal, 2026-10-05, B1: "Never leave the inside blank or white."] the inside's print switched off
        from apps.ire import inside_print
        real = inside_print.inside_group

        def blank(coords, gx, gy, spec, **k):
            return real(coords, gx, gy, dict(spec, mode="plain"), **k)
        self.planted("carton_inside", "INSIDE_BLANK", ("apps.ire.inside_print.inside_group", blank))

    def test_b3_his_sticker_choice_dropped(self):
        # [his final goal, 2026-10-05, B3] the size step's choice of a custom sticker lost on its way to the drawing
        from apps.ire import back_info
        real = back_info.plan
        self.planted("carton_sticker", "BACK_INFO_NOT_AS_CHOSEN",
                     ("apps.ire.back_info.plan", lambda mode, readings, words: real("sticker", readings, words)))

    def test_a2_a_containers_back_left_in_english(self):
        # [his final goal, 2026-10-05, A] the back's translation switched off: held at Gate 2 by name, and the detector
        # names a back panel in English alone
        def held(case):
            case["stop"] = {"codes": ["CONTAINER_LABEL_NOT_TRILINGUAL"]}
        self.planted("jar", "LABEL_NOT_TRILINGUAL",
                     ("apps.pipeline.targets.container.translate_back", lambda *a, **k: None), mutate=held)

    def test_b2_the_die_drawn_at_the_old_closure(self):
        # [his final goal, 2026-10-05, B2] the carton step's print-ready version switched back to 1.2: no lock slits, no
        # thumb notch — [his second goal of 2026-10-06, item 2] and a die that does not fold, held at Gate 2 by name
        self.planted("packaging", "DIE_NOT_PRINT_READY",
                     ("apps.pipeline.targets.packaging.PackagingTarget.carton_template_version", lambda _s, _t: "1.2"),
                     mutate=_held_unfolding)

    def test_dl_a_die_whose_dust_flaps_meet_is_held_by_name(self):
        # [his second goal of 2026-10-06, item 2] the 1.4 die's dust flaps drawn past the opening's middle: the fold
        # check fails it, Gate 2 holds it by name, and folded again here it fails the same way
        faults = self.planted("packaging", "FOLD_CHECK_FAILED",
                              ("apps.dielines.geometry.trade_tuck.DUST_COLLISION_MM", -4.0), mutate=_held_unfolding)
        self.assertTrue(any("top_dust_no_collision" in f for f in faults), faults)

    def test_dl_the_fold_check_silenced(self):
        # [his second goal of 2026-10-06, item 2: "never hidden"] the export's fold check made to pass every die, the
        # dust flaps drawn to meet: nothing holds the design — folded again here, it does not fold
        def silent(coords):
            return {"schema": "fold_check/1.0", "passed": True, "findings": [], "failed": [], "ms": 0.0}
        self.planted("packaging", "FOLD_CHECK_UNSEEN", ("apps.dielines.geometry.fold_check.check", silent),
                     ("apps.dielines.geometry.trade_tuck.DUST_COLLISION_MM", -4.0))

    def test_dl_a_straight_tuck_drawn_under_the_reverse_tucks_name(self):
        # [his second goal of 2026-10-06, item 2] the error 1.0–1.3 made the other way round: the reverse tuck end's
        # bottom tuck hung from the back — a straight tuck end — under the reverse tuck's name
        from apps.dielines.geometry import trade_tuck as TT
        styles = copy.deepcopy(TT.STYLES)
        styles["reverse_tuck_end_carton"]["bottom"] = "back"
        self.planted("packaging", "STYLE_MISNAMED", ("apps.dielines.geometry.trade_tuck.STYLES", styles))

    def test_b2_the_files_layers_dropped(self):
        # [his final goal, 2026-10-05, B2: "Each on its own named layer"] the files written without their layers
        self.planted("packaging", "DIE_NOT_PRINT_READY",
                     ("apps.dielines.exporters.counter_display_files.apply_layers", lambda *a, **k: None))

    def test_c6_the_native_file_left_unsaid(self):
        # [his final goal, 2026-10-05, C6] the export's native-file step dropped: no record — the detector names it
        self.planted("packaging", "NATIVE_FILE_UNSAID",
                     ("apps.dielines.services.export_service._native", lambda *a, **k: None))

    def test_c7_a_defect_handed_over_silently(self):
        # [his final goal, 2026-10-05, C7] the drawn file's read switched off, and two lines set onto each other on the
        # front: the record says nothing; the detector's own read names them. [His test findings on design 123, (4)]
        # the drawing's settling of the copy where it draws switched off with it — else it spaces what it can and says
        # what it cannot, and nothing is handed over silently
        from apps.ire import compose as real_compose
        from apps.ire.graph import Color, TextRun
        real = real_compose.compose_components_graph

        def crossed(coords, *a, **k):
            doc = real(coords, *a, **k)
            front = next(p for p in coords.panels if p.name == "front")
            gx = coords.bleed_polygon.bounds[0] - real_compose._PAGE_MARGIN_MM
            gy = coords.bleed_polygon.bounds[1] - real_compose._PAGE_MARGIN_MM
            for i, words in enumerate(("PLANTED ONE", "PLANTED TWO")):
                doc.root.children.append(TextRun(name="planted-%d" % i, text=words, x=front.x - gx + 6.0 + i,
                                                 y=front.y - gy + 40.0 + 0.6 * i, size_pt=7.0,
                                                 color=Color.from_hex("#333333")))
            return doc
        self.planted("packaging", "DEFECT_HANDED_SILENTLY", ("apps.ire.compose.compose_components_graph", crossed),
                     ("apps.ire.self_check.inspect_said", lambda *a, **k: []),
                     ("apps.pipeline.targets.packaging.settle_front_copy", lambda task, front, dims: front))

    def test_b4_the_first_concepts_drawn_from_one_direction(self):
        # [his final goal, 2026-10-05, B4] the old way planted back: the first direction taken for him and drawn three
        # ways — the detector names pictures not one for each direction
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import CreativeBrief

        def one_direction(agent, feedback=None):
            CreativeBrief.objects.filter(task=agent.task).update(selected_direction_id="d1")
            return agent._generate_from_selected_direction(feedback=feedback)
        self.planted("packaging", "PROMPT_STEP",
                     ("apps.pipeline.agents.aria.ARIAAgent._render_each_direction", one_direction))

    def test_i1_his_container_type_read_as_a_word_among_words(self):
        # [his goal of 2026-10-06, item 1] design 120's reading planted back: his Container type read with the brief as
        # one text, the first of the fixed order winning — the tube's brief names a pot before it, and the jar is drawn
        from apps.pipeline.targets import container as C

        def first_match(text):
            low = C.product_words(text).lower()
            form = next((f for f, w in C.FORM_WORDS if re.search(w, low)), None)
            return {"form": form, "source": "brief" if form else "", "said": "", "named": [form] if form else []}
        self.planted("tube", "CONTAINER_TYPE", ("apps.pipeline.targets.container.form_choice", first_match))

    def test_l1_the_label_stopped_off_the_sticker_again(self):
        # [his correction of 2026-10-07: "Floor: 3 pt."] the shrink stopped at the 5 pt it stopped at before: the label
        # does not stand on the 22 mm back and stops off the sticker, as it did when it waited on his offers
        from apps.dielines.exporters import label_layout
        real = label_layout.steps

        def to_five(fonts):
            yield from (step for step in real(fonts) if step["body"] >= 5.0)

        def stops(case):
            case["stop"] = {"codes": ["CARTON_LABEL_DOES_NOT_FIT"]}
            case["statuses"] = [s for s in CARTON_STATUSES if s != "completed"]
        faults = self.planted("carton_label_shrunk", "LABEL_NOT_ON_STICKER",
                              ("apps.dielines.exporters.label_layout.steps", to_five), mutate=stops)
        self.assertTrue(faults)

    def test_l1_the_carton_widened_for_its_label_again(self):
        # [his correction of 2026-10-07: "Never widen the carton for text"] the die drawn 11 mm wider than he confirmed,
        # as his second goal of 2026-10-06 once widened 119 (22 → 33 mm)
        from apps.pipeline.agents.dieline_agent import DielineAgent
        real = DielineAgent.generate

        def widened(agent, job, confirmed_dims, *a, **k):
            return real(agent, job, dict(confirmed_dims, width_mm=float(confirmed_dims["width_mm"]) + 11.0), *a, **k)
        self.planted("carton_label_shrunk", "CARTON_WIDENED",
                     ("apps.pipeline.agents.dieline_agent.DielineAgent.generate", widened))

    def test_l1_the_label_shrunk_unevenly_again(self):
        # [his correction of 2026-10-07: "Shrink the whole label evenly"] the fine print stepped down alone, as his final
        # goal's C5 had it: ingredients and warnings at 4 pt under a 5 pt body
        from apps.dielines.exporters import label_layout
        real = label_layout.steps

        def uneven(fonts):
            yield {"face": "regular", "body": 5.0, "fine": 4.0, "title": 6.5}
            yield from real(fonts)
        self.planted("packaging", "LABEL_UNEVEN", ("apps.dielines.exporters.label_layout.steps", uneven))

    def test_i10_the_flaps_dotted_again(self):
        # [his goal of 2026-10-06, item 10] 119's flaps planted back: every flap but the lid a dot pattern
        from apps.ire import inside_print as IP
        from apps.ire.graph import Color, Group, Path, SolidFill

        def dotted(coords, gx, gy, spec, **kw):
            out = []
            for name, poly in getattr(coords, "components", []) or []:
                if name in ("main-body", "glue-tab") or name.startswith("top-tuck"):
                    continue
                x0, y0, x1, y1 = poly.bounds
                segs = IP.pattern_segments(dict(spec, density="sparse", pattern="dots"), (gx(x0), gy(y0), gx(x1), gy(y1)))
                clip = IP._poly_segments([(gx(x), gy(y)) for x, y in list(poly.exterior.coords)[:-1]])
                out.append(Group(name="flap-%s" % name, role="decoration", clip=clip, children=[Path(
                    name="flap-%s-pattern" % name, segments=segs, fill=SolidFill(color=Color.from_hex("#51060A")),
                    fill_rule="nonzero")]))
            return out
        self.planted("carton_title", "INVENTED_PATTERN", ("apps.ire.inside_print.flap_nodes", dotted))

    def test_i10_the_flaps_motif_cut_by_the_die_again(self):
        # [executor, his goal of 2026-10-06, item 10, read on 119's drawn flaps] the flaps planted back as they were
        # drawn first: the concept's motif laid as a repeat over each flap and clipped to it — its shapes cut in half at
        # the die's edge and across the tuck's fold
        from apps.ire import inside_print as IP
        from apps.ire.graph import Color, Group, Path, SolidFill

        def repeated(coords, gx, gy, spec, *, motif_cubics=None, motif_aspect=1.0, **kw):
            motif = IP.unit_motif(motif_cubics, motif_aspect)
            out = []
            for name, poly in getattr(coords, "components", []) or []:
                if name in ("main-body", "glue-tab"):
                    continue
                x0, y0, x1, y1 = poly.bounds
                segs = IP.pattern_segments(dict(spec, density="sparse", pattern="motif"),
                                           (gx(x0), gy(y0), gx(x1), gy(y1)), motif)
                clip = IP._poly_segments([(gx(x), gy(y)) for x, y in list(poly.exterior.coords)[:-1]])
                out.append(Group(name="flap-%s" % name, role="decoration", clip=clip, children=[Path(
                    name="flap-%s-motif" % name, segments=segs, fill=SolidFill(color=Color.from_hex("#51060A")),
                    fill_rule="nonzero")]))
            return out
        self.planted("carton_title", "FLAP_SHAPE_CUT", ("apps.ire.inside_print.flap_nodes", repeated))

    def test_i11_the_sides_one_small_line_again(self):
        # [his goal of 2026-10-06, item 11] the sides as they were: the brief's side copy alone, nothing else
        from apps.ire import compose as C
        real = C._side_design_nodes

        def one_line(*a, **kw):
            nodes, record = real(*a, **kw)
            return [n for n in nodes if str(n.name).startswith("side-copy-")], record
        self.planted("carton_title", "SIDE_UNDESIGNED", ("apps.ire.compose._side_design_nodes", one_line))

    def test_i12_the_title_a_word_a_line_again(self):
        # [his goal of 2026-10-06, item 12] the title as it was: its level's size, wrapped greedily — a word a line
        from apps.dielines.exporters import label_layout as LL

        def greedy(name, ar, levels, width, fonts, keep_marks):
            en, over = LL._wrap_words([(w, True) for w in name.split()], levels["title"], width, fonts)
            ar_lines = LL._ar_lines(ar, "", levels["title"], width, fonts, keep_marks, all_bold=True) if ar else []
            return levels["title"], en, ar_lines, over
        # [his second goal of 2026-10-06, item 1] its long label now widens the carton, whose back then holds even a
        # greedy title on two lines: planted on the short label, the back at its 22 mm, where 119's stood a word a line
        def short(case):
            case["brief"] = case["brief"].replace(BACK_LONG, BACK_SHORT)
            # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] every label now carries
            # the full set — the description his BACK leaves empty is written — so the plant gives the four pieces
            # itself, short, and the back's title stands at the size where a greedy wrap sets a word a line
            case["brief"] = case["brief"].replace(BACK, BACK_TINY + " / Description: Rose gloss.")
        self.planted("carton_title", "TITLE_LINES", ("apps.dielines.exporters.label_layout._title_fit", greedy),
                     mutate=short)

    def test_i8_the_back_measured_in_a_face_it_is_not_drawn_in(self):
        # [his goal of 2026-10-06, item 8] the back label measured as before — no document, so the legacy faces (Noto
        # Sans) — and drawn in the theme's: a line runs into the back's safe margin and the detector names it
        from apps.ire import compose_container as CC
        real = CC.compose_information_panels

        def legacy(*a, **kw):
            kw.pop("doc_metadata", None)
            return real(*a, **kw)
        self.planted(PLANTED_BACK_CASE, "BACK_MARGIN", ("apps.ire.compose_container.compose_information_panels", legacy))

    def test_c5c_a_containers_stop_without_its_offers(self):
        # [his final goal, 2026-10-05, C5c] the stopped back's offers never measured: the detector names the stop
        self.planted("tin_back_stop", "STOP_WITHOUT_OFFER",
                     ("apps.pipeline.targets.container._save_label_offers", lambda *a, **k: None))

    def test_c5c_his_choice_of_a_containers_offer_makes_it_again_and_it_stands(self):
        # [his final goal, 2026-10-05, C5c] the tin whose back cannot stand in three languages: its offers drawn, his
        # choice taken through the site's own door, the container made again — nothing paid — and Gate 2 passes
        from apps.pipeline.targets.container import CONTAINER_LABEL_OFFERS_KEY
        case = copy.deepcopy(CASES["tin_back_stop"])
        case, h, out = self.run_case(case)
        out.refresh_from_db()
        offers = (out.spec_sheet or {}).get(CONTAINER_LABEL_OFFERS_KEY)
        self.assertTrue(offers, "the stopped back offers nothing: %s" % (out.spec_sheet or {}).get(
            "container_back_panel/1.0"))
        calls = len(h.calls)
        pick = offers[0]["languages"]
        r = self.post("/api/tasks/%d/label_offer/" % self._task_id, {"offer": "fewer_languages", "languages": pick})
        self.assertIn(r.status_code, (200, 202), r.content[:600])
        self.expect("awaiting_gate_2", "his choice of the offer")
        out = self.output()
        self.assertEqual((out.spec_sheet or {}).get("container_label_languages"), pick)
        # [his goal for the pitch, 2026-10-15, B (5)] the designer's eye looks at every drawing made, his choice's too —
        # the one paid call it makes; nothing else is paid for
        self.assertEqual([c for c in h.calls[calls:] if c not in ("trend_search", "designers_eye")], [],
                         "his choice paid for a call")
        with out.design_preview.open("rb") as fh:                      # the design made again: his look, again
            sha = hashlib.sha256(fh.read()).hexdigest()
        r = self.client.post("/dashboard/history/tasks/%d/accept-design/" % self._task_id,
                             {"output_id": out.pk, "preview_sha256": sha, "decision": "ACCEPTED"})
        self.assertIn(r.status_code, (200, 302), r.content[:800])
        self.gate2()

    def test_6_a_paid_step_that_never_runs(self):
        # [his review of 119, 2026-10-05, point 1: "labels stay trilingual"] the label whose translation never ran is now
        # held at Gate 2 by name — the planted fault caught at the door; the detector still names the step
        self.planted("packaging", "STEP_NEVER_RAN",
                     ("apps.pipeline.services.panel_translate.translate_panel_info", lambda *a, **k: {}),
                     mutate=_held_not_trilingual)

    def test_7_a_broken_link_the_die_drawn_at_another_size(self):
        from apps.pipeline.agents.dieline_agent import DielineAgent
        real = DielineAgent.generate

        def taller(agent, job, confirmed_dims, *a, **k):
            return real(agent, job, dict(confirmed_dims, height_mm=float(confirmed_dims["height_mm"]) + 10.0), *a, **k)
        self.planted("packaging", "BROKEN_LINK",
                     ("apps.pipeline.agents.dieline_agent.DielineAgent.generate", taller))


# ================================================================ the live half: the page, as he has it open

#: [his goal of 2026-10-06, item 2] one case of every design type, driven with its page open in a real browser
LIVE_CASES = ("packaging", "gift_set", "palette", "tube", "complete_product", "marketing_material", "social_media",
              "exhibition_booth", "display_stand")
#: what each screen of the design page is, as the page draws it
SCREENS = {"working": "#working-step", "trends": "#trend-view .trend-board", "concepts": "#image-gallery .image-card",
           "size": "#dimensions-state", "shape": "#profile-state", "review": "#gate2-state",
           "finished": "#complete-state"}


def _seed_trend_board(task, root):
    """[His goal of 2026-10-06, items 2 and 3] a trend board as the web leaves one — two pictures fetched and read, one
    picture its platform did not let us fetch, one link — built where the search builds it (the wiring check fetches
    nothing from the web)."""
    from PIL import Image

    from apps.pipeline.models import InspirationReading, TrendBoard, TrendPick
    board, _ = TrendBoard.objects.get_or_create(task=task)
    board.status, board.subject = TrendBoard.READY, "cosmetic packaging"
    board.searches = [{"platform": "pinterest", "query": "cosmetic packaging design", "scope": "", "credits": 1,
                       "results": 3}]
    board.save()
    for n in (1, 2):
        sha = ("%x" % (task.pk * 16 + n)).rjust(64, "0")
        thumb = os.path.join(root, "trend_%d_%d.png" % (task.pk, n))
        Image.new("RGB", (120, 160), (200, 120, 140)).save(thumb)
        TrendPick.objects.create(board=board, number=n, kind=TrendPick.PICTURE, platform="pinterest", used=True,
                                 page_url="https://www.pinterest.com/pin/%d%d/" % (task.pk, n), sha256=sha,
                                 thumb_path=thumb, thumb_width=120, thumb_height=160)
        InspirationReading.objects.get_or_create(sha256=sha, defaults={"reading": {
            "layout": "a tall panel with the name low", "colour_words": "deep rose on cream", "mood": "quiet",
            "finish": "matte", "type_style": "a light sans", "take": "the low name"}})
    # [his goal of 2026-10-10, item 3: "Only keep trend pictures that actually show THIS product type"] the picture not
    # fetched and the link, titled as the web titles them for this design's own product — shown as links where they
    # name it
    from apps.pipeline.services.trend_board import product_terms
    terms = product_terms(task)
    said = terms[0] if terms else "design"
    TrendPick.objects.create(board=board, number=3, kind=TrendPick.PICTURE, platform="dribbble",
                             page_url="https://dribbble.com/shots/%d3" % task.pk, title="a %s on Dribbble" % said,
                             unread_reason="not fetched — its page: HTTP 202")
    TrendPick.objects.create(board=board, number=4, kind=TrendPick.LINK, platform="behance",
                             page_url="https://www.behance.net/gallery/%d4" % task.pk, title="a %s on Behance" % said)
    return board


try:
    from apps.pipeline.tests.browser_live_server import DrainedStaticLiveServerTestCase as _LiveBase
except ImportError:              # pragma: no cover
    _LiveBase = TestCase


@override_settings(**RUN_SETTINGS, TREND_REVIEW_WINDOW_S=600)
class _LiveWalk(_LiveBase):
    """[His goal of 2026-10-06, item 2: "THE PAGE MUST MOVE ON BY ITSELF. When a step finishes in the background (trend
    pictures found, directions made, concept pictures drawn, a drawing done, the carton's pictures), the open design page
    switches to the next screen on its own, without me pressing refresh. While it works, it shows clearly what step it's
    on and roughly how long. ... Check every step of every design type."] Each design type, its page opened while it
    works; every step after it is moved where production moves it — the pipeline in this thread, his approvals through
    the site's doors from another client — and the page, never reloaded, must show the next screen by itself. A Complete
    Product's vial page opens its carton's page when the carton begins."""

    @classmethod
    def setUpClass(cls):
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        from playwright.sync_api import sync_playwright
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._pw.stop()
        super().tearDownClass()

    def setUp(self):
        from PIL import Image

        from django.core.cache import cache

        from apps.core.models import Brand, ColorSystem, Product
        from apps.pipeline.models import DesignTask
        cache.clear()                                   # the measured step times are this test's own
        self.dir = tempfile.mkdtemp(prefix="wiring_live_")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.enterContext(override_settings(MEDIA_ROOT=os.path.join(self.dir, "media"),
                                            WEB_QUARANTINE_ROOT=os.path.join(self.dir, "quarantine")))
        os.makedirs(os.path.join(self.dir, "quarantine"))
        logo = os.path.join(self.dir, "logo.png")
        Image.new("RGBA", (400, 120), LOGO_RGB + (255,)).save(logo)
        self.enterContext(override_settings(BRAND_LOGO_PATH=logo))
        self.brand = Brand.objects.create(name="BBROSE", master_brief="the house")
        ColorSystem.objects.create(brand=self.brand, name="Blush Core", system_id="CS-001", status="canonical",
                                   palette=PALETTE, image_generation_context="the house palette")
        Product.objects.create(brand=self.brand, **DECOY)
        self.user = get_user_model().objects.create_superuser("wiring_owner", "w@example.invalid", "x")
        self.client.force_login(self.user)
        self._task_id = None
        self.proposed: list = []
        self.saves: list = []

        def trace(sender, instance, **kw):
            self.saves.append((instance.pk, instance.status))
        post_save.connect(trace, sender=DesignTask, weak=False, dispatch_uid="wiring-live-trace")
        self.addCleanup(post_save.disconnect, sender=DesignTask, dispatch_uid="wiring-live-trace")

    current_task = _Run.current_task
    arm = _Run.arm
    output = _Run.output

    def post(self, url, data=None):
        return self.client.post(url, data=json.dumps(data or {}), content_type="application/json")

    def _page(self, task_id):
        from importlib import import_module

        store = import_module(settings.SESSION_ENGINE).SessionStore()
        store["_auth_user_id"] = str(self.user.pk)
        store["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
        store["_auth_user_hash"] = self.user.get_session_auth_hash()
        store.create()
        ctx = self._browser.new_context(viewport={"width": 1280, "height": 900})
        self.addCleanup(ctx.close)              # its streams end before the live server is drained, pass or fail
        host = self.live_server_url.split("//")[1].split(":")[0]
        ctx.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": store.session_key, "domain": host,
                          "path": "/"}])
        ctx.add_init_script("window.WATCH_MS = 300; window.POLL_MIN_MS = 300;")
        if getattr(self, "_browser_routes", None):
            ctx.route("**/static/js/poll.js*", self._browser_routes)
        if getattr(self, "_route_script", None):
            ctx.route(*self._route_script)
        page = ctx.new_page()
        self.navigations = []
        page.on("framenavigated", lambda f: f == page.main_frame and self.navigations.append(f.url))
        # [his goal of 2026-10-13, (4): "No browser pop-ups anywhere ("127.0.0.1 says…")"] each one the page raises, kept
        self.popups = []
        page.on("dialog", lambda d: (self.popups.append("%s: %s" % (d.type, d.message)), d.dismiss()))
        page.goto("%s/dashboard/designs/%d/" % (self.live_server_url, task_id), wait_until="domcontentloaded")
        page.wait_for_function("() => window._openedFor === '%d'" % task_id)    # its first status drawn
        page.evaluate("window.__sameDocument = 'opened'")
        return page

    def shows(self, page, screen, where, timeout=20000):
        """The screen appears on the open page by itself — the same document, never reloaded."""
        try:
            page.wait_for_selector(SCREENS[screen], state="visible", timeout=timeout)
        except Exception as e:      # noqa: BLE001 — named below, with what the page and the record show
            t = self.current_task()
            self.fail("%s: the page did not move on to %s by itself (the design is at %s; the page's badge says %r): %s"
                      % (where, screen, t.status, page.text_content("#task-status-badge"), str(e)[:200]))
        self.assertEqual(page.evaluate("window.__sameDocument"), "opened", "%s: the page was reloaded" % where)
        # [his goal of 2026-10-13, (4)] no browser pop-up on the way here; (3) no "Not moving?" on a screen that moves,
        # waits for him or is done — every screen this walk reaches is one of those
        page.wait_for_timeout(400)
        if self.popups:
            self.fail("BROWSER_POPUP: %s: the page raised the browser's own %s" % (where, self.popups))
        if page.locator("#resume-note").count():
            self.fail("RESUME_WHILE_MOVING: %s: the page offers to resume a design that has not stopped: %s"
                      % (where, page.text_content("#resume-note")))

    def _seed_measured_trends(self):
        """Three earlier designs' trend steps on this site — 100, 120 and 140 s — so the step's time is measured."""
        from datetime import timedelta

        from django.utils import timezone

        from apps.pipeline.models import AgentLog, DesignTask
        for n, seconds in enumerate((100, 120, 140)):
            t = DesignTask.objects.create(brand=self.brand, task_text="an earlier design %d" % n, status="completed")
            at = timezone.now() - timedelta(days=1, minutes=n)
            for action, when in (("ARIA: searching the web for current trends in cartons", at),
                                 ("ARIA: 2 trend picture(s) found and ticked — untick any", at + timedelta(seconds=seconds))):
                row = AgentLog.objects.create(task=t, agent_name="ARIA", action=action, level="info")
                AgentLog.objects.filter(pk=row.pk).update(timestamp=when)

    def walk(self, key):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import AgentLog, DesignProject
        from apps.pipeline.services import trend_board
        case = copy.deepcopy(CASES[key])
        h = Harness(case, self)
        self.arm(h)
        self.enterContext(mock.patch("apps.pipeline.services.trend_board.build",
                                     lambda task, **kw: _seed_trend_board(task, os.path.join(self.dir, "quarantine"))))
        self._seed_measured_trends()
        from apps.core.models import Product
        product = Product.objects.create(brand=self.brand, **case["product"])
        with mock.patch("apps.pipeline.tasks.run_aria_pipeline.delay"):      # Start, its run held: the page opens first
            r = self.post("/api/tasks/create/", {"task_text": case["brief"], "design_target": case["target"],
                                                  "product_id": product.pk, "brand_id": self.brand.pk})
        self.assertEqual(r.status_code, 201, r.content[:600])
        self._task_id = r.json()["task_id"]
        if case["kind"] == "composite":
            self._task_id = DesignProject.objects.order_by("-pk").first().tasks.order_by("pk").first().pk
        task = self.current_task()
        task.status = "running"
        task.save(update_fields=["status"])
        AgentLog.objects.create(task=task, agent_name="ARIA", action="ARIA: searching the web for current trends in "
                                "cosmetic packaging", level="info")
        page = self._page(task.pk)
        # while it works: its step in words, and roughly how long — measured on this site's designs
        self.shows(page, "working", "%s, working" % key)
        said = page.text_content("#working-step")
        self.assertIn("Finding current trend pictures", said)
        self.assertIn("Usually about 2 minutes — measured on this site's last 3 designs", said)
        self.assertIn("Running for", said)
        # the trends found, in the background: the board shows by itself
        ARIAAgent(task.pk).run()
        self.expect_status("awaiting_trend_review", key)
        self.shows(page, "trends", "%s, the trend pictures found" % key)
        self.trend_tiles(page, key)
        # the window closes, as the worker closes it: the directions are made, a picture drawn for each — shown by itself
        self.assertTrue(trend_board.proceed(task.pk, trend_board.BY_THE_WINDOW))
        if key=='display_stand':
            self.expect_status('failed',key)
            page.wait_for_selector('.failed-notice',state='visible',timeout=20000)
            self.assertIn('exact bottle reference and an exact assembly reference',self.current_task().error_message)
            self.assertNotIn('image',h.calls)
            self.assertFalse(self.current_task().images.exists())
            self.assertFalse(self.current_task().packaging_outputs.exists())
            self.assertEqual(page.locator('#working-step').count(),0)
            return
        self.expect_status("awaiting_gate_1", key)
        self.shows(page, "concepts", "%s, the concept pictures drawn" % key)
        self.back_half(case, h, page, key)

    def trend_tiles(self, page, where):
        """[His goal of 2026-10-06, item 3: "Show them as links only, never as blank tiles."] every tile on the board
        holds its picture, and the picture its platform did not let us fetch is a link to its page."""
        blank = page.eval_on_selector_all("#trend-view .trend-card", "cards => cards.filter(c => { const i = "
                                          "c.querySelector('img'); return !(i && i.getAttribute('src')) && "
                                          "!c.querySelector('.trend-words'); }).map(c => c.dataset.number)")
        self.assertEqual(blank, [], "%s: blank trend tiles %s" % (where, blank))
        self.assertEqual(page.locator("#trend-view .trend-card").count(), 2, "%s: the two fetched pictures" % where)
        links = page.eval_on_selector_all("#trend-view .trend-links a", "as => as.map(a => a.href)")
        self.assertTrue(any("dribbble.com/shots/" in href for href in links),
                        "%s: the unfetched picture is not a link: %s" % (where, links))

    def expect_status(self, status, where):
        self.assertEqual(self.current_task().status, status, "%s: %s" % (where, self.current_task().error_message))

    def back_half(self, case, h, page, key, stage=""):
        where = key + stage
        image = self.current_task().images.order_by("pk").first()
        r = self.post("/api/tasks/%d/gate1_approve/" % self._task_id, {"image_id": image.pk})
        self.assertIn(r.status_code, (200, 202), r.content[:600])
        kind = case["kind"] if case["kind"] != "composite" else "container"
        if kind == "carton":
            self.expect_status("awaiting_dimensions", where)
            self.shows(page, "size", "%s, the size proposed" % where)
            job = self.output().dieline_job
            est = job.extraction_result or {}
            dims = {k: float(est[k]["value"]) for k in ("width_mm", "depth_mm", "height_mm")}
            r = self.post("/api/tasks/%d/confirm_dimensions/" % self._task_id, dict({"dimensions": dims},
                                                                                     **(case.get("size_choices") or {})))
            self.assertIn(r.status_code, (200, 202), r.content[:600])
        elif kind == "container":
            self.expect_status("awaiting_container_profile", where)
            self.shows(page, "shape", "%s, the shape proposed" % where)
            url = "/api/tasks/%d/confirm_container_profile/" % self._task_id
            r = self.post(url, {"profile": case["profile"]})
            if r.status_code == 409 and r.json().get("zones"):
                zones = r.json()["zones"]
                for z in zones:
                    z["user_confirmation_state"] = "USER_CONFIRMED"
                r = self.post(url, {"profile": case["profile"], "zones": zones})
            self.assertEqual(r.status_code, 200, r.content[:600])
        self.expect_status("awaiting_gate_2", where)
        self.shows(page, "review", "%s, the drawing done" % where)
        out = self.output()
        if kind == "container":
            with out.design_preview.open("rb") as fh:
                sha = hashlib.sha256(fh.read()).hexdigest()
            r = self.client.post("/dashboard/history/tasks/%d/accept-design/" % self._task_id,
                                 {"output_id": out.pk, "preview_sha256": sha, "decision": "ACCEPTED"})
            self.assertIn(r.status_code, (200, 302), r.content[:600])
        if case["kind"] == "composite":
            carton = dict(case["carton"], key="complete_product (the carton)", product=case["product"])
            h.next_stage = carton                 # its pictures are drawn inside the vial's approval
        r = self.post("/api/tasks/%d/gate2_approve/" % self._task_id, {"packaging_output_id": out.pk})
        self.assertEqual(r.status_code, 200, r.content[:600])
        if case["kind"] == "composite":
            from apps.pipeline.models import DesignProject
            project = DesignProject.objects.order_by("-pk").first()
            self._task_id = project.tasks.order_by("pk").last().pk
            # the carton begins inside the vial's approval, its trends found: the vial's page opens the carton's page
            self.expect_status("awaiting_trend_review", "complete_product, the carton begun")
            try:
                page.wait_for_url("**/dashboard/designs/%d/" % self._task_id, timeout=20000)
            except Exception as e:  # noqa: BLE001
                self.fail("complete_product: the vial's page did not open the carton's page by itself: %s" % e)
            page.wait_for_function("() => window._openedFor === '%d'" % self._task_id)
            page.evaluate("window.__sameDocument = 'opened'")
            self.shows(page, "trends", "complete_product, the carton's trend pictures")
            from apps.pipeline.services import trend_board
            self.assertTrue(trend_board.proceed(self._task_id, trend_board.BY_THE_WINDOW))
            self.expect_status("awaiting_gate_1", "complete_product, the carton's pictures")
            self.shows(page, "concepts", "complete_product, the carton's pictures")
            return self.back_half(dict(carton, kind="carton"), h, page, key, stage=" (the carton)")
        self.expect_status("completed", where)
        self.shows(page, "finished", "%s, finished" % where)
        return page


class LiveMovesOnTests(_LiveWalk):
    """[His goal of 2026-10-06, item 2] every design type walked with its page open (``_LiveWalk``)."""

    def test_his_test_findings_121_a_design_that_stops_while_its_page_is_open(self):
        """[His test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), items 2 and 3: "The status box said
        'Working on it… running for 3 min' while the design had stopped. The status must always match the real state.";
        "Errors are shown to me in words, never engine codes (this one was raw codes again)."] A tube's page opened while
        it works, its step and its clock shown; the design then stops at its concept step, recorded by the pipeline's
        own stop with 121's own reason: the open page drops the working box and its clock by itself, and says why it
        stopped in words — no engine code on the page."""
        from apps.core.models import Product
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import AgentLog
        from apps.pipeline.tests.test_phase2a4 import _ENGINE_CODE, _REASON_121
        case = copy.deepcopy(CASES["tube"])
        self.arm(Harness(case, self))
        self._seed_measured_trends()
        product = Product.objects.create(brand=self.brand, **case["product"])
        with mock.patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            r = self.post("/api/tasks/create/", {"task_text": case["brief"], "design_target": case["target"],
                                                  "product_id": product.pk, "brand_id": self.brand.pk})
        self.assertEqual(r.status_code, 201, r.content[:600])
        self._task_id = r.json()["task_id"]
        task = self.current_task()
        task.status = "running"
        task.save(update_fields=["status"])
        AgentLog.objects.create(task=task, agent_name="ARIA", level="info",
                                action="ARIA: three design directions planned and validated — drawing one picture for "
                                       "each direction")
        page = self._page(task.pk)
        self.shows(page, "working", "121, working")
        self.assertIn("Running for", page.text_content("#working-step"))
        ARIAAgent(task.pk)._fail(_REASON_121)              # the pipeline's own stop, 121's own reason
        self.expect_status("failed", "121, stopped")
        try:
            page.wait_for_selector(".failed-notice", state="visible", timeout=20000)
        except Exception as e:      # noqa: BLE001 — named with what the page shows
            self.fail("the open page did not show the stop by itself: %s (%r)" % (e, page.text_content("body")[:400]))
        self.assertEqual(page.locator("#working-step").count(), 0, "the working box stayed beside the stop: %r"
                         % page.text_content("#working-step") if page.locator("#working-step").count() else "")
        said = page.text_content(".failed-notice")
        self.assertIn("concept pictures", said)
        self.assertNotRegex(said, _ENGINE_CODE)
        self.assertNotRegex(page.text_content("#activity-feed"), _ENGINE_CODE)
        self.assertEqual(page.evaluate("window.__sameDocument"), "opened", "the page was reloaded")

    def test_his_test_blocker_122_the_page_says_why_in_words_and_each_offer_is_a_button(self):
        """[His test blocker on design 122, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), items 4 and 6: "never a dead end:
        offer me in words what I can do (redraw for $X, draw this concept from the template, or pick another), each with
        a button"; "The refusal label 'ITS MAP CANNOT DRAW IT' is shouting engine words; say it plainly."] 122's own
        brief, its tube's redraw coming back on its pink ground too, walked with its page open: each concept says why in
        plain words, with its three offers each a button and the redraw's price — no engine word, no "Use this concept"
        on a concept that cannot be drawn. His redraw button redraws it and the page is back at his concepts; his
        template button takes the design on from the tube's standard layout."""
        import time
        import hashlib
        from pathlib import Path

        from apps.pipeline.targets.container.readable import CHECK_KEY, NOT_DRAWABLE

        from apps.core.models import Product
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import DesignProject
        from apps.pipeline.services import trend_board
        from apps.pipeline.tests.test_phase2a4 import _ENGINE_CODE
        case = copy.deepcopy(CASES["complete_product_one_colour"])
        case["redraw_ground"] = ONE_PINK_GROUND
        h = Harness(case, self)
        self.arm(h)
        self.enterContext(mock.patch("apps.pipeline.services.trend_board.build",
                                     lambda task, **kw: _seed_trend_board(task, os.path.join(self.dir, "quarantine"))))
        product = Product.objects.create(brand=self.brand, **case["product"])
        with mock.patch("apps.pipeline.tasks.run_aria_pipeline.delay"):
            r = self.post("/api/tasks/create/", {"task_text": case["brief"], "design_target": case["target"],
                                                  "product_id": product.pk, "brand_id": self.brand.pk})
        self.assertEqual(r.status_code, 201, r.content[:600])
        self._task_id = DesignProject.objects.order_by("-pk").first().tasks.order_by("pk").first().pk
        ARIAAgent(self._task_id).run()
        self.expect_status("awaiting_trend_review", "122")
        self.assertTrue(trend_board.proceed(self._task_id, trend_board.BY_THE_WINDOW))
        self.expect_status("awaiting_gate_1", "122, its concepts checked")
        page = self._page(self._task_id)
        self.shows(page, "concepts", "122, its concepts")
        gallery = page.text_content("#image-gallery")
        self.assertNotIn("Its map cannot draw it", gallery)
        self.assertNotRegex(gallery, _ENGINE_CODE)
        self.assertEqual(gallery.count("We can't draw this concept yet: the product can't be told apart from its "
                                       "background, so its shape can't be cut out."), 3, gallery[:1500])
        offers = page.eval_on_selector_all(".cannot-draw", "ds => ds.map(d => Array.from(d.querySelectorAll("
                                           "'.cannot-draw-offer')).map(b => [b.dataset.offer, b.textContent]))")
        self.assertEqual([[key for key, _w in each] for each in offers], [["redraw", "template", "another"]] * 3)
        self.assertRegex(offers[0][0][1], r"^Redraw it on a plain contrasting backdrop — about \$\d+\.\d\d$")
        self.assertEqual(page.locator("#image-gallery .btn-approve").count(), 0)

        def settles(status, where, redraws=None):
            for _ in range(200):
                if self.current_task().status == status and (redraws is None or h.redraws == redraws):
                    return
                time.sleep(0.1)
            self.fail("%s: the design is at %s, %d redraws" % (where, self.current_task().status, h.redraws))
        originals = list(self.current_task().images.order_by("variation_number", "pk"))
        snapshots = {im.pk: (im.image_file.name, Path(im.image_file.path).read_bytes(), im.prompt_used) for im in originals}
        parent, sibling = originals[:2]
        note = "Keep the exact Arabic and the original pink artwork; change only the backdrop."
        task = self.current_task()
        task.gate_1_notes = note
        task.save(update_fields=["gate_1_notes"])
        self.assertEqual(h.redraws, 0)
        parent_card = page.locator(".image-card").filter(has=page.locator(f"#prompt-edit-{parent.pk}"))
        parent_card.locator(".cannot-draw-offer[data-offer=redraw]").click()
        settles("awaiting_gate_1", "his redraw button", redraws=1)
        for _ in range(200):
            if self.current_task().images.filter(reference_provenance__repair_parent_image_id=parent.pk).exists():
                break
            time.sleep(0.1)
        child = self.current_task().images.get(reference_provenance__repair_parent_image_id=parent.pk)
        self.assertEqual(self.current_task().images.count(), 4)
        self.assertEqual(self.current_task().images.filter(superseded=False).count(), 3)
        self.assertEqual(child.reference_provenance[CHECK_KEY]["state"], NOT_DRAWABLE)
        self.assertEqual(child.reference_provenance["repair_edit_parent_sha256"], hashlib.sha256(snapshots[parent.pk][1]).hexdigest())
        self.assertIn(note, child.prompt_used)
        self.assertIn(note, h.prompts[-1][1])
        for original in originals:
            original.refresh_from_db()
            self.assertEqual((original.image_file.name, Path(original.image_file.path).read_bytes(), original.prompt_used), snapshots[original.pk])
            self.assertEqual(original.superseded, original.pk == parent.pk)
        self.assertEqual(self.current_task().options["rescue_repair_rounds"], 1)
        self.shows(page, "concepts", "122, back at its concepts after his redraw")
        page.wait_for_selector(f"#prompt-edit-{child.pk}", state="attached")
        sibling_card = page.locator(".image-card").filter(has=page.locator(f"#prompt-edit-{sibling.pk}"))
        sibling_card.locator(".cannot-draw-offer[data-offer=template]").click()
        settles("awaiting_container_profile", "his template button")
        self.assertEqual(page.evaluate("window.__sameDocument"), "opened", "the page was reloaded")

    def test_his_test_blocker_122_planted_the_page_as_it_was(self):
        # THE CONTROL: the page served its Gate 1 script as it was before (3a614c0) — it knew only the stop at approval,
        # so it said nothing of a concept checked before it was shown, and offered nothing: the walk must say so
        old = subprocess.run(["git", "show", "3a614c0:./static/js/gates.js"], cwd=settings.BASE_DIR,
                             capture_output=True, text=True, check=True).stdout
        self._route_script = ("**/static/js/gates.js*",
                              lambda r: r.fulfill(status=200, content_type="application/javascript", body=old))
        with self.assertRaises(AssertionError) as caught:
            self.test_his_test_blocker_122_the_page_says_why_in_words_and_each_offer_is_a_button()
        self.assertTrue(str(caught.exception).startswith("0 != 3"), str(caught.exception)[:300])

    def test_his_test_findings_121_planted_the_page_as_it_was(self):
        # THE CONTROL: the page served its render script as it was at 99de0c8 — the working box kept beside the stop,
        # the record's own text for the reason
        old = subprocess.run(["git", "show", "99de0c8:./static/js/render.js"], cwd=settings.BASE_DIR,
                             capture_output=True, text=True, check=True).stdout
        self._route_script = ("**/static/js/render.js*",
                              lambda r: r.fulfill(status=200, content_type="application/javascript", body=old))
        with self.assertRaises(AssertionError) as caught:
            self.test_his_test_findings_121_a_design_that_stops_while_its_page_is_open()
        self.assertIn("the working box stayed beside the stop", str(caught.exception))


class LiveMovesOnPlantedTests(_LiveWalk):
    """[His goal of 2026-10-06, item 2] the live walk proved by its fault planted back: the page's script served as it
    was — the settled screen thrown away (``refresh(); stopLiveUpdates();``) and nothing watching a step of his — and the
    walk must say the page did not move on by itself."""

    def test_i2_the_settled_screen_thrown_away_again(self):
        real_page = self._page

        def old_page(task_id):
            def route(r):
                body = open(os.path.join(settings.BASE_DIR, "static", "js", "poll.js"), encoding="utf-8").read()
                start = body.index("      es.addEventListener('settled', async () => {")
                end = body.index("      });", start) + len("      });")
                body = body[:start] + "      es.addEventListener('settled', () => { refresh(); stopLiveUpdates(); });" \
                    + body[end:]
                body = body.replace("function startWatching(taskId, data) {", "function startWatching(taskId, data) {"
                                    " return;")
                r.fulfill(status=200, content_type="application/javascript", body=body)
            self._browser_routes = route
            return real_page(task_id)
        self._page = old_page
        with self.assertRaises(AssertionError) as caught:
            self.walk("packaging")
        self.assertIn("did not move on", str(caught.exception))


class LiveApprovalReadMidWayTests(_LiveWalk):
    """[Found by Day 10's full suite, 2026-10-23: the palette's page stayed on "Approved — preparing the files" with the
    design completed] A container's design is approved; its page, watching at the review, reads it in the moment
    between the approval and the files (gate_2_approved — a working status, its drawing done: the reconstruction
    status terminal). The page must keep watching and move on to the finished screen by itself. The moment is held
    open (the gate-2 resume waits) and the page is first seen watching, so the page always reads it: as the Approve
    button reads it with a real worker, where the files are made after the click's own status read."""

    HOLD_S = 4.0                        # far over the walk's 300 ms watch: the page's watch reads the moment

    def held_walk(self, key):
        from apps.pipeline.agents.aria import ARIAAgent
        real = ARIAAgent.resume_after_gate_2

        def held(agent, *args, **kwargs):
            time.sleep(self.HOLD_S)
            return real(agent, *args, **kwargs)
        self.enterContext(mock.patch.object(ARIAAgent, "resume_after_gate_2", held))
        shows = self.shows

        def then_watching(page, screen, where, timeout=20000):
            shows(page, screen, where, timeout)
            if screen == "review":          # the event stream settled: the page watches its review, as it waits for him
                page.wait_for_function("() => !window._taskES && !!window.watchTimer")
        self.shows = then_watching
        return self.walk(key)

    def test_a_palettes_page_moves_on_from_its_approval_read_mid_way(self):
        self.held_walk("palette")

    def test_a_palettes_page_planted_as_it_was(self):
        # THE CONTROL: the page's loadTask as it was — a terminal snapshot at a working status returned with nothing
        # armed (no stream, no poll, no watch) — and the walk must say the page did not move on by itself
        def old(r):
            body = open(os.path.join(settings.BASE_DIR, "static", "js", "poll.js"), encoding="utf-8").read()
            start = body.index("    if (rs && rs.terminal) {")
            end = body.index("    }", start + 1) + len("    }")
            body = body[:start] + "    if (rs && rs.terminal) return;      // terminal snapshot: nothing to poll" + body[end:]
            r.fulfill(status=200, content_type="application/javascript", body=body)
        self._route_script = ("**/static/js/poll.js*", old)
        with self.assertRaises(AssertionError) as caught:
            self.held_walk("palette")
        self.assertIn("did not move on to finished", str(caught.exception))
        self.assertIn("Approved", str(caught.exception))


class LiveTrendTilesPlantedTests(_LiveWalk):
    """[His goal of 2026-10-06, item 3] the board's blank tile planted back — the unfetched picture sent as a picture and
    the page's tile without its picture — and the walk must name the blank tile."""

    def test_i3_a_blank_tile_for_a_picture_not_fetched(self):
        from apps.pipeline.services import trend_board
        real = trend_board.payload

        def as_before(task):
            out = real(task)
            if out:
                kept = [l for l in out["links"] if not l.get("why")]
                out["pictures"] += [{"id": 0, "number": l["number"], "platform": l["platform"], "page_url": l["page_url"],
                                     "title": l["title"], "feeds": False, "used": False, "why_not": l["why"],
                                     "thumb_url": "", "words": "", "taken": None}
                                    for l in out["links"] if l.get("why")]
                out["links"] = kept
            return out

        def old_tiles(r):
            body = open(os.path.join(settings.BASE_DIR, "static", "js", "trends.js"), encoding="utf-8").read()
            body = body.replace("const shown = board.pictures.filter(p => p.thumb_url || p.feeds);",
                                "const shown = board.pictures;")
            body = body.replace("board.links.concat(board.pictures.filter(p => !(p.thumb_url || p.feeds))",
                                "board.links.concat([]")
            r.fulfill(status=200, content_type="application/javascript", body=body)
        self.enterContext(mock.patch("apps.pipeline.services.trend_board.payload", as_before))
        self._browser_routes = None
        self._route_script = ("**/static/js/trends.js*", old_tiles)
        with self.assertRaises(AssertionError) as caught:
            self.walk("packaging")
        self.assertIn("blank trend tiles", str(caught.exception))


#: [his goal of 2026-10-06, item 14] the pages he moves through, and what a template prints when its own tag breaks
#: [the designer flow of 2026-10-27] New design is the mood-board intake; the classic start (new.html) is kept at its own address
SHELL_PAGES = ("/dashboard/new/", "/dashboard/new/classic/", "/dashboard/", "/dashboard/history/", "/dashboard/status/")
TEMPLATE_TEXT = ("{#", "#}", "{%", "%}", "{{", "}}")


def capture_from_top(page, path):
    """A full-page picture of ``page`` as he sees it from its top — taken after scrolling there: a capture of a scrolled
    page paints the sticky top bar where the window stood (his item 14 was the third picture of the flow, taken after a
    click had scrolled it)."""
    page.evaluate("window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
    page.wait_for_function("() => window.scrollY <= 4")          # the top: a page may settle a pixel or two down
    page.screenshot(path=path, full_page=True)


class LiveTopBarTests(_LiveWalk):
    """[His goal of 2026-10-06, item 14: "One screenshot of the new start showed the top bar drawn a second time across
    the middle of the page. Find and fix it."] Every page he moves through draws its top bar once, at the top of the
    window however far it is scrolled, and prints no template's own words; a full-page capture is taken from the top."""

    def top_bar(self, page, where):
        self.assertEqual(page.locator("header.bar").count(), 1, "%s: the top bar is drawn %d times"
                         % (where, page.locator("header.bar").count()))
        page.mouse.wheel(0, 2400)
        page.wait_for_timeout(250)
        top = page.evaluate("document.querySelector('header.bar').getBoundingClientRect().top")
        self.assertAlmostEqual(top, 0.0, delta=0.5, msg="%s: scrolled, the top bar stands %s px down" % (where, top))
        text = page.evaluate("document.body.innerText")
        shown = [t for t in TEMPLATE_TEXT if t in text]
        self.assertEqual(shown, [], "%s: the page prints its template's own text %s" % (where, shown))
        shot = os.path.join(self.dir, "capture.png")
        capture_from_top(page, shot)

    def pages(self):
        from apps.core.models import Product
        from apps.pipeline.models import DesignTask
        product = Product.objects.create(brand=self.brand, **CASES["packaging"]["product"])
        task = DesignTask.objects.create(brand=self.brand, product=product, task_text="A carton for Rose Velvet.",
                                         design_target="packaging", status="awaiting_gate_1", created_by=self.user)
        page = self._page(task.pk)
        self.top_bar(page, "the design page")
        for url in SHELL_PAGES:
            page.goto(self.live_server_url + url, wait_until="domcontentloaded")
            page.wait_for_selector("header.bar")
            self.top_bar(page, url)

    def test_i14_one_top_bar_and_no_template_text(self):
        self.pages()

    def test_i14_planted_a_template_comment_broken_over_two_lines(self):
        # the New design page's note as it was: a {# … #} over two lines, which Django prints
        broken = os.path.join(self.dir, "templates", "dashboard")
        os.makedirs(broken)
        src = open(os.path.join(settings.BASE_DIR, "templates", "dashboard", "new.html"), encoding="utf-8").read()
        start = src.index("    {% comment %}[the owner's answer of 2026-09-27")
        end = src.index("{% endcomment %}", start) + len("{% endcomment %}")
        src = src[:start] + "    {# a note\n       over two lines #}" + src[end:]
        with open(os.path.join(broken, "new.html"), "w", encoding="utf-8") as fh:
            fh.write(src)
        tpl = copy.deepcopy(settings.TEMPLATES)
        tpl[0]["DIRS"] = [os.path.join(self.dir, "templates")] + list(tpl[0].get("DIRS") or [])
        self.enterContext(override_settings(TEMPLATES=tpl))
        with self.assertRaises(AssertionError) as caught:
            self.pages()
        self.assertIn("prints its template's own text", str(caught.exception))


class LiveReferencesTests(_LiveWalk):
    """[His goal of 2026-10-06, item 13: "On the concept-pick page, the "draw again with references" grid is folded by
    default and shows only references that match the brief, not unrelated stock."] A library of five: a house design of
    the brief's own product, a house design sharing only the house's words ("bbrose", "carton", "and"), a stock pattern
    named with a word of the brief, a stock background named only with English's small words, and a face powder's .ai.
    The concepts page shows the grid folded, and offers the first and the third."""

    def library(self):
        import json as _json

        from PIL import Image

        from apps.core.models import DesignReference
        media, mats = os.path.join(self.dir, "media"), os.path.join(self.dir, "materials")
        for rel in ("refs/serum.png", "refs/noise.png"):
            os.makedirs(os.path.dirname(os.path.join(media, rel)), exist_ok=True)
            Image.new("RGB", (64, 64), (200, 160, 170)).save(os.path.join(media, rel))
        DesignReference.objects.create(name="YB-SERUM", image_path="refs/serum.png", category="SK",
                                       product_type="face serum", tags=["glass"], summary="a serum carton")
        DesignReference.objects.create(name="YB-NOISE", image_path="refs/noise.png", category="SK",
                                       product_type="eyeshadow palette", tags=["bbrose", "and", "carton", "bold"])
        rows = []
        for rel, cat, ext in (("stock/rose_dot_pattern.png", "PATTERN", ".png"),
                              ("stock/background_design_with_liquid_paint_for_flyers.png", "BACKGROUND", ".png"),
                              ("ai/FB-2060.ai", "HISTORICAL_DESIGN", ".ai")):
            os.makedirs(os.path.dirname(os.path.join(mats, rel)), exist_ok=True)
            Image.new("RGB", (64, 64), (180, 120, 140)).save(os.path.join(mats, rel).replace(".ai", ".png"))
            if ext == ".ai":
                shutil.copy(os.path.join(mats, rel).replace(".ai", ".png"), os.path.join(mats, rel))
            rows.append({"relative_path": rel, "category": cat, "extension": ext, "sha256": rel.replace("/", "_"),
                         "ownership_status": "UNKNOWN", "license_status": "UNVERIFIED"})
        inventory = os.path.join(self.dir, "inventory.jsonl")
        with open(inventory, "w") as fh:
            fh.write("\n".join(_json.dumps(r) for r in rows) + "\n")
        # [D-D7-1, Day 7 §3] the picker reads the library index — what each file SHOWS — never a file name: the stock
        # pattern is offered for the rose dots it shows, the liquid-paint background for nothing the brief says
        index = os.path.join(self.dir, "materials-index.json")
        with open(index, "w") as fh:
            _json.dump({"schema": "day7_materials_index/1", "items": [
                {"sha256": "stock_rose_dot_pattern.png", "name": "rose_dot_pattern.png", "paths": ["stock/rose_dot_pattern.png"], "extension": ".png",
                 "file_kind": "raster", "kind": "pattern", "subject": "rose dot pattern", "tags": ["rose", "dot", "pattern", "repeat"], "style": [],
                 "colours": [], "text_present": False, "text_seen": [], "language": "none", "surfaces": ["pattern-fill", "carton"], "preview": False,
                 "caption_source": "day7-haiku", "rights": {"tier": "house", "excluded": False, "basis": "D-D7-1"}},
                {"sha256": "stock_background_design_with_liquid_paint_for_flyers.png", "name": "background_design_with_liquid_paint_for_flyers.png",
                 "paths": ["stock/background_design_with_liquid_paint_for_flyers.png"], "extension": ".png", "file_kind": "raster", "kind": "background",
                 "subject": "liquid paint swirls for a flyer", "tags": ["liquid", "paint", "swirl", "flyer"], "style": [], "colours": [], "text_present": False,
                 "text_seen": [], "language": "none", "surfaces": ["backdrop"], "preview": False, "caption_source": "day7-haiku",
                 "rights": {"tier": "house", "excluded": False, "basis": "D-D7-1"}}]}, fh)
        self.enterContext(override_settings(DIP_INVENTORY_PATH=inventory, MATERIALS_ROOT=mats, MATERIALS_INDEX_PATH=index,
                                            HOUSE_INDEX_PATH=os.path.join(self.dir, "no-house-index.json")))

    def to_concepts(self, key="packaging"):
        from apps.core.models import Product
        from apps.pipeline.services import trend_board
        case = copy.deepcopy(CASES[key])
        self.arm(Harness(case, self))
        self.enterContext(mock.patch("apps.pipeline.services.trend_board.build",
                                     lambda task, **kw: _seed_trend_board(task, os.path.join(self.dir, "quarantine"))))
        product = Product.objects.create(brand=self.brand, **case["product"])
        r = self.post("/api/tasks/create/", {"task_text": case["brief"], "design_target": case["target"],
                                             "product_id": product.pk, "brand_id": self.brand.pk})
        self.assertEqual(r.status_code, 201, r.content[:600])
        self._task_id = r.json()["task_id"]
        self.assertTrue(trend_board.proceed(self._task_id, trend_board.BY_THE_WINDOW))
        self.expect_status("awaiting_gate_1", "references")
        return self._page(self._task_id)

    def offered(self):
        self.library()
        page = self.to_concepts()
        page.wait_for_selector("details.mat-ref-fold", state="attached")
        folded = page.evaluate("!document.querySelector('details.mat-ref-fold').open")
        page.click("details.mat-ref-fold > summary")
        titles = page.eval_on_selector_all("details.mat-ref-fold label.image-card strong:first-of-type",
                                           "els => els.map(e => e.textContent.trim())")
        return folded, titles

    def check_offered(self, folded, titles):
        self.assertTrue(folded, "the references grid opens unfolded")
        self.assertEqual(sorted(titles), ["YB-SERUM", "rose dot pattern"],
                         "offered beside the brief's own: %s" % titles)

    def test_i13_folded_and_only_what_matches_the_brief(self):
        self.check_offered(*self.offered())

    def test_i13_planted_the_old_matching(self):
        # the brief's words read with English's small words and the house's own — "and", "for", "bbrose", "carton" —
        # as before: the house design of another product and the stock background are offered again
        self.enterContext(mock.patch("apps.pipeline.services.concept_references.STOP_WORDS", frozenset()))
        with self.assertRaises(AssertionError) as caught:
            self.check_offered(*self.offered())
        self.assertIn("offered beside the brief's own", str(caught.exception))

    def test_i13_planted_the_grid_unfolded(self):
        def open_grid(r):
            body = open(os.path.join(settings.BASE_DIR, "static", "js", "gates.js"), encoding="utf-8").read()
            body = body.replace("<details class=\"mat-ref-fold\"${wasOpen ? ' open' : ''}>",
                                "<details class=\"mat-ref-fold\" open>")
            r.fulfill(status=200, content_type="application/javascript", body=body)
        self._route_script = ("**/static/js/gates.js*", open_grid)
        with self.assertRaises(AssertionError) as caught:
            self.check_offered(*self.offered())
        self.assertIn("opens unfolded", str(caught.exception))


def _live_test(key):
    def test(self):
        self.walk(key)
    test.__name__ = "test_live_%s" % key
    return test


for _key in LIVE_CASES:
    setattr(LiveMovesOnTests, "test_live_%s" % _key, _live_test(_key))


class Goal1013PlantedTests(_Run):
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md): "Add 1, 3, 4, 7, 8 and 9 to the wiring check."] Detectors 28
    and 29, each proved by its fault planted back where production could put it."""

    planted = PlantedFaultTests.planted

    def test_goal_1013_wiring_1_a_design_stopped_on_its_own_check_is_named(self):
        # (1) the stop that held 125, as its record wrote it: a design failed on one of its own checks
        case = copy.deepcopy(CASES["tube"])
        h = Harness(case, self)
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.create(brand=self.brand, task_text="a tube", status="failed",
                                         error_message="ARIA crashed: CONTAINER_PRODUCT_NAME_TOO_SMALL: the name drawn "
                                                       "under its floor")
        found = Detect(case, h, task, None, ["failed"])
        found.checks_go_on()
        self.assertTrue(any(f.startswith("CHECK_STOPPED:") for f in found.faults), found.faults)
        task.error_message = "a fault in the system itself, not one of the design's checks"
        found = Detect(case, h, task, None, ["failed"])
        found.checks_go_on()
        self.assertEqual(found.faults, [])                       # a fault of the system is said, never a check

    def test_goal_1013_wiring_1_a_check_with_no_words_is_named(self):
        # (1) a check the drawing went on past whose code has no words written for it
        self.planted("packaging", "CHECK_WITHOUT_WORDS",
                     ("apps.pipeline.targets.container.flat_motif_codes",
                      lambda map_front: ["CONTAINER_UNWORDED_PLANTED: the planted check"]))

    def test_goal_1013_wiring_3_the_page_told_a_moving_design_has_stopped_is_named(self):
        # (3) the old offer: Resume told on every state
        self.planted("tube", "RESUME_WHILE_MOVING", ("apps.pipeline.step_times.stalled", lambda task: True))


class Goal1013LivePlantedTests(_LiveWalk):
    """[His goal of 2026-10-13, (4): "No browser pop-ups anywhere ("127.0.0.1 says…")."] The live walk proved by its fault
    planted back: the page's own script raising the browser's dialog."""

    def test_goal_1013_wiring_4_a_browser_pop_up_is_named(self):
        def route(r):
            body = open(os.path.join(settings.BASE_DIR, "static", "js", "poll.js"), encoding="utf-8").read()
            body += "\nwindow.addEventListener('load', function () { alert('127.0.0.1 says: planted'); });\n"
            r.fulfill(status=200, content_type="application/javascript", body=body)
        self._browser_routes = route
        with self.assertRaises(AssertionError) as caught:
            self.walk("packaging")
        self.assertIn("BROWSER_POPUP", str(caught.exception))


class CompactFromTemplateTests(_Run):
    """[His test blocker on design 124, 2026-10-11, (2) and (4)] the one door past "never drawn from the form's own
    layout": his own "draw from template" (his test blocker on design 122, item 4) on a compact."""

    def test_goal_1011_one_engine_a_compact_he_sends_to_its_template_is_drawn_from_it_said(self):
        """His template button on a compact: drawn to Gate 2 from its form's own layout with his brief's words, said as
        his choice — no lid read for it, no lid art made — never stopped for the map it was told not to draw from."""
        from apps.pipeline.models import AgentLog
        case = copy.deepcopy(CASES["compact"])
        h = Harness(case, self)
        self.arm(h)
        self.create(case)
        self.expect("awaiting_gate_1", "create")
        image = self.current_task().images.order_by("pk").first()
        r = self.post("/api/tasks/%d/gate1_approve/" % self._task_id, {"image_id": image.pk, "from_template": True})
        self.assertIn(r.status_code, (200, 202), r.content[:800])
        self.container_back_half(dict(case, key="compact (from its template)"))
        self.assertEqual(getattr(h, "lid_arts", 0), 0)
        self.assertTrue(AgentLog.objects.filter(task_id=self._task_id, action__contains=(
            "drawn from the compact's standard layout with your brief's words — your choice")).exists())


#: [His test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6): "Add 2–5 to the
#: wiring check with 124's real concept."] 124 as he made it: his brief (fixtures_124/brief_124.txt), his chosen concept
#: (concept_153.png, "Arch & Bloom"), the size he confirmed at its shape step (190 x 120 x 12 mm, paperboard, magnetic)
HIS_124_CONFIRMED = dict(archetype="compact", variant="paperboard", cap_style="magnet", height_mm=120.0, width_mm=190.0,
                         depth_mm=12.0)
#: … and its tray's 18 pans' finishes as its real tray picture shows them (the executor's reading, his to correct)
HIS_124_FINISHES = [["shimmer", "shimmer", "glitter", "matte", "shimmer", "matte"],
                    ["matte", "shimmer", "shimmer", "matte", "shimmer", "matte"],
                    ["matte", "shimmer", "matte", "shimmer", "glitter", "matte"]]


class His124WiringTests(_Run):
    """[His test blocker on design 124, 2026-10-11, items 2 to 5, with 124's real concept] his palette driven through the
    site's own doors: its concept checked from its lid before it is shown, chosen, its open tray's picture made once,
    his size confirmed, its lid drawn from its map and its art — the pictures and the read paid for on 124 served as the
    image service's and the read's answers (fixtures_124), nothing paid — and every way it fell back before named."""

    HERE = os.path.join(os.path.dirname(__file__), "fixtures_124")

    def _fixture(self, name):
        with open(os.path.join(self.HERE, name), "rb") as fh:
            return fh.read()

    def _run_124(self, **case_changes):
        """124's case run to its shape step's confirmation: ``(case, harness, the design's status after it)``."""
        from apps.pipeline.services import concept_design_map as dm
        concept = self._fixture("concept_153.png")
        read = json.loads(self._fixture("lid_map_153.json").decode("utf-8"))
        asked = []

        def held(task, image_bytes, **kw):
            asked.append(hashlib.sha256(image_bytes).hexdigest())
            self._h124.calls.append("container_design_map_parts")      # the paid step, run — its real read
            self.assertEqual(asked[-1], read["source_sha256"], "the lid read is not 124's lid")
            return copy.deepcopy(read)
        self.enterContext(mock.patch.object(dm, "read_lid_parts", side_effect=held))
        case = copy.deepcopy(CASES["palette"])
        # the name on his record as the planner reads his brief, "Enchanted Rose Palette" — its lid sets its start
        case.update(key="124", product=_product("BBR-ER-124", "Enchanted Rose Palette", "eyeshadow palette"),
                    brief=self._fixture("brief_124.txt").decode("utf-8"), profile=dict(HIS_124_CONFIRMED),
                    pictures=[concept] * 3, lid_art=self._fixture("lid_art_153.png"),
                    tray_picture=self._fixture("tray_153.png"), pans_named=18,
                    back_words=("Talc, Mica", "Made in UAE"),
                    calls=[op for op in CALLS["face"] if op != "container_design_map_parts"])
        case.update(case_changes)
        h = Harness(case, self)
        h.picture = concept
        self._h124, self._asked124 = h, asked
        self.arm(h)
        self.create(case)
        self.front_half()
        self.expect("awaiting_container_profile", "gate 1 (124)")
        url = "/api/tasks/%d/confirm_container_profile/" % self._task_id
        r = self.post(url, {"profile": case["profile"]})
        if r.status_code == 409 and r.json().get("zones"):
            zones = r.json()["zones"]
            for z in zones:
                z["user_confirmation_state"] = "USER_CONFIRMED"
            r = self.post(url, {"profile": case["profile"], "zones": zones})
        self.assertEqual(r.status_code, 200, r.content[:2000])
        return case, h

    def _drawn_124(self, gate=True, **case_changes):
        """124 drawn to Gate 2 — and approved there, ``gate`` — read by the detectors. A planted fault's run stops at
        Gate 2 unapproved: what its detectors name is the finding, never Gate 2's own refusal."""
        case, h = self._run_124(**case_changes)
        self.expect("awaiting_gate_2", "profile (124)")
        out = self.output()
        if gate:
            with out.design_preview.open("rb") as fh:
                sha = hashlib.sha256(fh.read()).hexdigest()
            r = self.client.post("/dashboard/history/tasks/%d/accept-design/" % self._task_id,
                                 {"output_id": out.pk, "preview_sha256": sha, "decision": "ACCEPTED"})
            self.assertIn(r.status_code, (200, 302), r.content[:800])
            out = self.gate2(None)
        out.refresh_from_db()
        if os.environ.get("WIRING_DUMP"):
            _dump(os.path.join(os.environ["WIRING_DUMP"], "124"), h, out)
            with open(os.path.join(os.environ["WIRING_DUMP"], "124", "spec.json"), "w", encoding="utf-8") as fh:
                json.dump(out.spec_sheet, fh, ensure_ascii=False, indent=1, default=str)
        case.setdefault("statuses", STATUSES[case["kind"]])
        return case, h, out, Detect(case, h, self.current_task(), out, self.statuses_of(self._task_id)).all()

    def _stopped_124(self, **case_changes):
        from apps.pipeline.services import concept_design_map as dm
        self._run_124(**case_changes)
        self.expect("awaiting_gate_1", "the lid's art (124)")
        image = self.current_task().images.order_by("pk").first()
        image.refresh_from_db()
        return image.reference_provenance[dm.MAP_STOP_KEY]

    def test_goal_1011_wiring_124_drawn_from_its_lid_its_art_and_its_tray(self):
        """Items 2 to 5 on 124 itself: its three concepts each read from its lid before they are shown (one read each,
        nothing read again when chosen), its open tray's picture made once and read into his 3 rows of 6 — each pan its
        colour and finish from the picture, none grey — its lid's flat redraw made once, checked against its map and
        drawn: its sky, its illustration, its lines of type and its mark; the detectors clean."""
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import LID_ART_DRAWN_KEY, TRAY_PANS_KEY
        from apps.pipeline.targets.container.tray_picture import FROM_PICTURE
        case, h, out, faults = self._drawn_124()
        self.assertEqual(faults, [], "\n".join(faults))
        self.assertEqual(len(self._asked124), 3)                       # each concept read once, before it is shown
        self.assertEqual((h.lid_arts, h.trays), (1, 1))                # each picture made once
        spec = out.spec_sheet or {}
        self.assertEqual((spec[dm.SCHEMA]["read"], spec[dm.SCHEMA]["state"]), (dm.LID_READ, dm.MAP_READ))
        art = spec[LID_ART_DRAWN_KEY]
        self.assertEqual((art["state"], art["registration"]["state"]), ("TRACED", "REGISTERED"))
        self.assertGreater(art["measured"]["regions"], 500)
        pans = spec[TRAY_PANS_KEY]
        self.assertEqual([[p["finish"] for p in row] for row in pans], HIS_124_FINISHES)
        self.assertTrue(all(p["source"] == FROM_PICTURE for row in pans for p in row))
        self.assertEqual(pans[2][5]["name"], "Midnight Bloom")
        # [his (6)] its name set in Great Vibes, the granted face closest to its script, drawn as its letters
        title = next(t for t in spec[dm.SHAPES_SCHEMA]["types"] if t["part"] == "Enchanted Rose title")
        self.assertEqual((title["lettering_set"]["state"], title["lettering_set"]["face"]), ("SET", "GreatVibes-Regular"))
        self.assertTrue(Detect(case, h, self.current_task(), out, [])._name_set_as_lettering())
        self.assertIn("18 SHADES • 27 g", Detect(case, h, self.current_task(), out, [])._text())     # his brief's size

    def test_goal_1011_wiring_124_the_map_switched_off_falls_back_silently_again(self):
        """The planted fault: the map's read switched off — 124 drawn by its form's own layout, as it was at his
        blocker — and the detectors name it."""
        self.enterContext(override_settings(DESIGN_MAP_READ=False))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("SILENT_FALLBACK:") and "map was not READ" in f for f in faults), faults)

    # ---- [his goal of 2026-10-12 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ed4ca2c): "Add 1, 4, 5, 6, 9 and 10 to
    # ---- the wiring check."] each planted on 124 itself, and named

    def test_goal_1012_wiring_124_its_layered_file_turned_cmyk_without_his_profile(self):
        """(1) The planted fault: the layered file built CMYK where no printer's profile is set — and named."""
        from apps.ire.emitters import native_ai
        self.enterContext(mock.patch.object(native_ai, "press_profile", return_value="/not/his/printer.icc"))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("LAYERED_FILE_COLOUR:") for f in faults), faults)

    def test_goal_1012_wiring_124_its_gold_arch_left_off_the_foil_plate(self):
        """(4) The planted fault: the picture's gold left to print as ink — the arch off the foil plate — and named."""
        from apps.ire import container_finishes as F
        real = F.apply

        def no_gold(doc, record, **kw):
            return real(doc, record, **dict(kw, gold_as_drawn=tuple(n for n in kw.get("gold_as_drawn") or ()
                                                                  if not str(n).startswith("lid-art-"))))
        self.enterContext(mock.patch.object(F, "apply", side_effect=no_gold))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("GOLD_NOT_FOIL:") for f in faults), faults)

    def test_goal_1012_wiring_124_its_sign_drawn_small_again(self):
        """(5) The planted fault: the ℮ drawn at 3 mm beside its small run, as before his word of 2026-10-17 on 142 ("never
        larger than the text beside it") — and named."""
        from apps.ire import estimated_sign
        self.enterContext(mock.patch.object(estimated_sign, "floor_for",
                                            lambda size, per_mm=estimated_sign.PT_PER_MM: 3.0 * per_mm))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("ESTIMATED_SIGN_LARGE:") for f in faults), faults)

    def test_goal_1012_wiring_124_a_finish_only_the_planner_named_plated_again(self):
        """(6) The planted fault: the concept's finish line plated whole, as before — 124's soft-touch back, its clause as
        his concept wrote it — and named."""
        from apps.ire import container_finishes as F
        soft = {"clause": "soft-touch matte laminate on lid exterior and body", "evoked": [], "targets": ["ground"],
                "finishes": [{"kind": "soft_touch", "plate": "SOFT_TOUCH"}], "target_defaulted": False}

        def whole(record, brief):
            record = dict(record or {"schema_version": F.ASSIGNMENTS_VERSION, "read_from": "finish_signature",
                                     "state": "READ"})
            return dict(record, clauses=list(record.get("clauses") or []) + [soft]), []
        self.enterContext(mock.patch.object(F, "as_asked", side_effect=whole))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("FINISH_INVENTED:") and "SOFT_TOUCH" in f for f in faults), faults)

    def test_goal_1012_wiring_124_its_shimmer_drawn_as_a_stripe_again(self):
        """(9) The planted fault: a shimmer pan a straight blend across it, as at receipt — and named."""
        from apps.ire import palette_tray as T
        from apps.ire.graph import Color, GradientFill, GradientStop
        real = T._pan_shown

        def striped(pan, segs, x, y, side, name):
            nodes = real(pan, segs, x, y, side, name)
            if pan["finish"] == "shimmer":
                shade = nodes[0].fill.stops[-1].color
                lit = Color.from_hex(T._towards_white(pan["hex"], 0.45))
                nodes[0] = nodes[0].model_copy(update={"fill": GradientFill(kind="linear", x1=x, y1=y, x2=x + side,
                    y2=y + side, stops=[GradientStop(offset=0.0, color=lit), GradientStop(offset=0.55, color=shade),
                                        GradientStop(offset=1.0, color=shade)])})
            return nodes
        self.enterContext(mock.patch.object(T, "_pan_shown", side_effect=striped))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("SHIMMER_STRIPE:") for f in faults), faults)

    def test_goal_1012_wiring_124_its_glitter_drawn_as_big_dots_again(self):
        """(10) The planted fault: a glitter pan a couple of dozen big dots, as at receipt — and named."""
        from apps.ire import palette_tray as T
        self.enterContext(mock.patch.object(T, "SPARKLES", 22))
        self.enterContext(mock.patch.object(T, "SPARKLE_RADIUS", (0.03, 0.04)))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("GLITTER_COARSE:") for f in faults), faults)

    def test_goal_1011_wiring_124_its_pans_drawn_grey_again(self):
        """The planted fault: every pan given the grey the tray was drawn in at his blocker — and the detectors name
        it."""
        from apps.pipeline.targets.container import tray_picture as TP
        real = TP.pans_for

        def grey(*a, **kw):
            return [[dict(p, hex="#D8D2CF") for p in row] for row in real(*a, **kw)]
        self.enterContext(mock.patch.object(TP, "pans_for", side_effect=grey))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("SILENT_FALLBACK:") and "pans" in f for f in faults), faults)

    def test_goal_1011_wiring_124_its_lid_drawn_without_its_illustration_is_said(self):
        """The planted fault: the lid's art traced to no region — a lid of sky alone, its roses and arch gone. The
        drawing's motif check finds no illustration where the concept has one — and [his goal of 2026-10-13, (1): "NO
        check ever stops a design"] the design goes on to Gate 2, the missing motif said beside Approve in words."""
        from apps.pipeline.targets.container import lid_art as LA
        real = LA.trace_art

        def empty(*a, **kw):
            got = real(*a, **kw)
            return dict(got, regions=[], measured=dict(got["measured"], regions=0))
        self.enterContext(mock.patch.object(LA, "trace_art", side_effect=empty))
        self._run_124()
        spec = self.output().spec_sheet or {}
        self.assertIn("CONTAINER_MOTIF_MISSING", spec["container_reconstruction"]["blockers"])
        self.assertTrue(any(r["code"] == "CONTAINER_MOTIF_MISSING" and r["what"].startswith(
            "the concept's motif was not drawn") for r in spec["checks_shown/1.0"]), spec["checks_shown/1.0"])

    def test_goal_1013_never_stops_124_its_first_redraw_goes_on_naming_its_small_print(self):
        """Item 4 on 124's own first redraw (lid_art_153_first.png: its roses grown under the small print) — the redraw
        never drawn; [his goal of 2026-10-13, (1): "NO check ever stops a design"] the design goes on, its two lines of
        small print named with why beside Approve, with what he can do. It stopped back at Gate 1 until then."""
        from apps.pipeline.targets import container as C
        self._run_124(lid_art=self._fixture("lid_art_153_first.png"))
        # [his goal after the pitch page, B (11); the third brand-new brief, 137, sent back to its shape when its art was
        # refused] the redraw is drawn as it was redrawn — every element drawn, his A (4) — what its check saw said
        rows = [r for r in (self.output().spec_sheet or {})["checks_shown/1.0"]
                if r["what"].startswith("the lid's illustration is drawn as it was redrawn, but its flat redraw does "
                                        "not stand")]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("Arabic product line", rows[0]["what"])
        self.assertIn("shade count and weight", rows[0]["what"])
        self.assertEqual(rows[0]["options"], list(C.LID_ART_OPTIONS))

    def test_goal_1011_wiring_124_chosen_again_after_a_stop_is_drawn_on_its_new_output(self):
        """[His test blocker on design 124, 2026-10-11, (4): "stop and tell me which part and why, with options"] his
        options taken on 124: its redraw refused, the design stopped at Gate 1; the same concept chosen again — the
        service answering now — and his size confirmed again: drawn to Gate 2 on the output its new choice made, its map
        read from its lid and its art traced, never the stopped output's; the page's status naming that output. (Every
        door read the design's FIRST output: his size was confirmed on the stopped one, which holds no map, and the
        design stopped again — found redrawing 124 at 17:34Z.)"""
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import LID_ART_DRAWN_KEY
        self._stopped_124(lid_art_refused="upstream 500")
        stopped = self.output().pk
        self._h124.stage_case.pop("lid_art_refused")
        image = self.current_task().images.order_by("pk").first()
        r = self.post("/api/tasks/%d/gate1_approve/" % self._task_id, {"image_id": image.pk})
        self.assertIn(r.status_code, (200, 202), r.content[:800])
        self.expect("awaiting_container_profile", "chosen again (124)")
        url = "/api/tasks/%d/confirm_container_profile/" % self._task_id
        r = self.post(url, {"profile": dict(HIS_124_CONFIRMED)})
        if r.status_code == 409 and r.json().get("zones"):
            zones = r.json()["zones"]
            for z in zones:
                z["user_confirmation_state"] = "USER_CONFIRMED"
            r = self.post(url, {"profile": dict(HIS_124_CONFIRMED), "zones": zones})
        self.assertEqual(r.status_code, 200, r.content[:2000])
        self.expect("awaiting_gate_2", "drawn again (124)")
        out = self.output()
        self.assertNotEqual(out.pk, stopped)
        spec = out.spec_sheet or {}
        self.assertEqual((spec[dm.SCHEMA]["read"], spec[LID_ART_DRAWN_KEY]["state"]), (dm.LID_READ, "TRACED"))
        shown = self.client.get("/api/tasks/%d/status/" % self._task_id).json()
        self.assertEqual(shown["packaging_output"]["id"], out.pk)

    def test_goal_1011_wiring_124_its_redraw_refused_stops_with_his_options(self):
        """Item 4 where the image service refuses the lid's redraw: nothing drawn, the design back at Gate 1, the lid's
        illustrations named with why, his three options — never its form's own layout."""
        from apps.pipeline.services import concept_design_map as dm
        stop = self._stopped_124(lid_art_refused="upstream 500")
        self.assertTrue(stop["why"].startswith("its illustration could not be redrawn flat"), stop["why"])
        self.assertIn("upstream 500", stop["why"])
        self.assertEqual({p["kind"] for p in stop["parts"]}, {"illustration"})
        self.assertEqual(len(stop["parts"]), 4)
        self.assertEqual(stop["options"], list(dm.STOP_OPTIONS))


    # ---- [his goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (7)-(9): "Add 1, 3, 4, 7, 8 and 9 to the wiring check."]
    # ---- each planted on 124 itself, and named; its clean run above holds the three silent

    def test_goal_1013_wiring_124_its_arch_traced_in_pieces_again(self):
        """(7) The planted fault: no line found — 124's arch drawn as the trace broke it — and named."""
        self.enterContext(mock.patch("apps.pipeline.services.line_geometry.find",
                                     lambda trace, points, kinds=None: {"lines": [], "replaced": [], "params": {}}))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("TRACED_GEOMETRY:") for f in faults), faults)

    def test_goal_1013_wiring_124_its_glow_in_flat_rings_again(self):
        """(8) The planted fault: the glow's rings each one flat colour — the stack of bands — and named."""
        from apps.pipeline.services import line_geometry as LG
        real = LG.glow_parts

        def flat_rings(*a, **k):
            return [dict(part, patches=[p[:8] + [p[8], p[9], p[8], p[9]] for p in part["patches"]])
                    for part in real(*a, **k)]
        self.enterContext(mock.patch.object(LG, "glow_parts", flat_rings))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("GLOW_BANDED:") for f in faults), faults)

    def test_goal_1013_wiring_124_its_sky_in_flat_cells_again(self):
        """(9) The planted fault: the sky's mesh each cell one flat colour — stripes — and named."""
        from apps.pipeline.targets.container import lid_art as LA
        real = LA.sky_patches

        def flat_cells(*a, **k):
            return [p[:8] + [p[8]] * 4 for p in real(*a, **k)]
        self.enterContext(mock.patch.object(LA, "sky_patches", flat_cells))
        _case, _h, _out, faults = self._drawn_124(gate=False)
        self.assertTrue(any(f.startswith("GRADIENT_BANDED:") for f in faults), faults)


# ================================================================ every failure class on every type
# [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (10): "For every failure class we've hit (stopped checks, silent
# fallbacks, wrong orientation/size, traced geometry, banded gradients, missing elements in the layered file, wrong
# product words, generic trends, unreadable motifs, colour drift, text collisions, invented finishes/barcodes, ℮), check
# EVERY design type and form — tube, bottle, jar, compact/palette, lipstick, wand vial, pencil, carton, Complete Product,
# Gift Set, Display Stand, Marketing, Social Media, Exhibition Booth — and fix the engine."] Each cell: the detector the
# wiring check runs on that type's own case ("detector:<name>"), a test that proves it on that type ("test:<module>::
# <name>"), or why it cannot arise there ("n/a: <why>") — never a blank cell.

COVERAGE_TYPES = {"tube": "tube", "bottle": "bottle", "jar": "jar", "compact/palette": "palette", "lipstick": "lipstick",
                  "wand vial": "mascara", "pencil": "pencil", "carton": "packaging", "Complete Product": "complete_product",
                  "Gift Set": "gift_set", "Display Stand": "display_stand", "Marketing": "marketing_material",
                  "Social Media": "social_media", "Exhibition Booth": "exhibition_booth"}
_FORMS = ("tube", "bottle", "jar", "lipstick", "wand vial", "pencil")
_BOXES = ("carton", "Gift Set")
_ART = ("Display Stand", "Marketing", "Social Media", "Exhibition Booth")
_ART_WHY = ("n/a: an artwork places its approved concept picture as its key visual (the raster he allowed) and draws "
            "its grounds and type in vector — nothing of it is traced, banded or carried into a second file")


def _cells(**groups) -> dict:
    out = {}
    for names, cell in groups.values():
        for name in names:
            out[name] = cell
    return out


_ALL = tuple(COVERAGE_TYPES)
COVERAGE = {
    "stopped checks": _cells(a=(_ALL, "detector:checks_go_on")),
    "silent fallbacks": _cells(a=(_ALL, "detector:silent_fallback")),
    "wrong orientation/size": _cells(
        a=(_FORMS, "detector:container_type"),
        b=(("compact/palette", "Complete Product"),
           "test:apps.pipeline.tests.test_dimension_gate_structure::DimensionGateTests::"
           "test_goal_1013_orientation_a_box_proposed_lying_flat_is_confirmed_and_drawn_lying_flat"),
        c=(_BOXES, "test:apps.pipeline.tests.test_composite_orchestration::TheContainerSizesTheCartonTests::"
                   "test_bh70_a_compacts_carton_lies_flat_on_the_same_die_and_fits_the_tuck_end"),
        d=(_ART, "n/a: each piece is drawn at its format's own named size, set by its target, never proposed")),
    "traced geometry": _cells(
        a=(_FORMS + _BOXES + ("Complete Product",),
           "test:apps.ire.tests.test_compose::test_goal_1013_geometry_a_window_under_a_gold_arch_is_read_as_its_own_arch"),
        b=(("compact/palette",), "detector:geometry_drawn"),
        c=(_ART, _ART_WHY)),
    "banded gradients": _cells(
        a=(_FORMS + _BOXES + ("Complete Product",),
           "test:apps.ire.tests.test_compose::test_goal_1013_gradient_the_window_is_drawn_smooth_under_its_drawn_arch"),
        b=(("compact/palette",), "detector:sky_smooth"),
        c=(_ART, _ART_WHY)),
    "missing elements in the layered file": _cells(
        a=(_FORMS + _BOXES + ("compact/palette", "Complete Product"), "detector:native_said"),
        b=(_ART, "n/a: an artwork's .ai is its drawing itself, a page a piece — no second, layered file is built")),
    "wrong product words": _cells(a=(_ALL, "detector:product_words")),
    "generic trends": _cells(
        a=(_ALL, "test:apps.pipeline.tests.test_wiring_check::PlantedFaultTests::"
                 "test_goal_1010_wiring_item3_the_trend_board_shows_only_the_product")),
    "unreadable motifs": _cells(
        a=(_FORMS + _BOXES + ("compact/palette", "Complete Product"),
           "test:apps.pipeline.tests.test_targets::HisSecondBlocker123CartonFlatTests::"
           "test_a_carton_standing_alone_draws_every_motif_from_its_flat_redraw"),
        b=(_ART, "n/a: no motif is traced on an artwork — its key visual is the approved picture itself")),
    "colour drift": _cells(
        a=(_FORMS + _BOXES + ("compact/palette", "Complete Product"),
           "test:apps.ire.tests.test_compose::"
           "test_goal_1013_never_stops_a_colour_that_drifts_is_redrawn_in_the_concepts_and_checked_again"),
        b=(_ART, "n/a: an artwork's colours are its approved picture's own and the house's ruled grounds")),
    "text collisions": _cells(
        a=(_FORMS + ("compact/palette", "Complete Product"), "detector:back_margin"),
        b=(_BOXES, "detector:label_block"),
        c=(_ART, "test:apps.pipeline.tests.test_create_design_target::ARunThatDoesNotFitIsNamed::"
                 "test_a_name_too_long_for_its_floor_is_over_and_coded_never_shrunk_below_it")),
    "invented finishes/barcodes": _cells(
        a=(_FORMS + ("compact/palette", "Complete Product"), "detector:finish_asked"),
        b=(_BOXES, "detector:ean_whole"),
        c=(_ART, "n/a: no finish plate and no barcode is drawn on an artwork piece")),
    "℮": _cells(a=(_ALL, "detector:estimated_size")),
}


class Goal1013CoverageTests(SimpleTestCase):
    """[His goal of 2026-10-13, (10)] the table above holds: no blank cell; every type a case the wiring check runs; every
    detector named is one the check runs on every case (read by running ``Detect.all`` with each recorded, never from
    its source); every test named one that exists; every reason said."""

    def test_goal_1013_coverage_every_failure_class_on_every_type_has_a_check_or_a_reason(self):
        assert len(COVERAGE) == 13 and all(set(row) == set(COVERAGE_TYPES) for row in COVERAGE.values()), \
            {cls: sorted(set(COVERAGE_TYPES) - set(row)) for cls, row in COVERAGE.items()}
        assert set(COVERAGE_TYPES.values()) <= set(CASES), sorted(set(COVERAGE_TYPES.values()) - set(CASES))
        ran = []
        probe = Detect.__new__(Detect)
        for name in dir(Detect):
            if not name.startswith("_") and callable(getattr(Detect, name)) and name not in ("all", "fail", "signs"):
                setattr(probe, name, (lambda n: (lambda: ran.append(n)))(name))
        probe.faults = []
        Detect.all(probe)
        for cls, row in COVERAGE.items():
            for kind, cell in row.items():
                where, _, what = cell.partition(":")
                assert what.strip(), (cls, kind, cell)
                if where == "detector":
                    assert what in ran, (cls, kind, what, "is not run by Detect.all")
                elif where == "test":
                    module, *path = what.split("::")
                    target = importlib.import_module(module)
                    for part in path:
                        target = getattr(target, part)
                    assert callable(target), (cls, kind, what)
                else:
                    assert where == "n/a" and len(what.split()) >= 6, (cls, kind, cell)

    def test_goal_1013_coverage_a_blank_cell_is_refused(self):
        """The control: a table with one type's cell taken out is refused by the same reading."""
        row = dict(COVERAGE["℮"])
        row.pop("Exhibition Booth")
        assert set(row) != set(COVERAGE_TYPES)


class PitchRunTests(_Run):
    """[His goal after the pitch page, 2026-10-15, B (9): "Run each from brief to final files with no manual fixes: pick
    the trend-led concept automatically." (10): "total time from Start to final files ... any stop or error". (11):
    "the page moving on by itself, one clear button per step."] The pitch run (apps/pipeline/autopilot.py), driven
    through the site's own doors on the wiring check's stubs: started with its tick, every waiting step taken by the
    system itself as its button takes it, the trend-led concept chosen, and the design left at Gate 2 with no acceptance
    recorded — its files' time kept."""

    def start(self, case, **extra):
        from apps.core.models import Product
        product = Product.objects.create(brand=self.brand, **case["product"])
        r = self.post("/api/tasks/create/", dict({"task_text": case["brief"], "design_target": case["target"],
                                                  "product_id": product.pk, "brand_id": self.brand.pk,
                                                  "autopilot": "true"}, **extra))
        self.assertEqual(r.status_code, 201, r.content[:800])
        self._task_id = r.json()["task_id"]
        return r.json()

    def taken(self, task_id=None):
        from apps.pipeline import autopilot
        from apps.pipeline.models import DesignTask
        return [s["status"] for s in autopilot._steps(DesignTask.objects.get(pk=task_id or self._task_id))]

    def at_gate_2_untouched(self, where):
        from apps.ire.container_production_readiness import ACCEPTANCE_KEY
        from apps.pipeline.models import GateDecision
        self.expect("awaiting_gate_2", where)
        task = self.current_task()
        self.assertFalse(GateDecision.objects.filter(task=task, gate="gate_2").exists())
        self.assertNotIn(ACCEPTANCE_KEY, self.output().spec_sheet or {})
        body = self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]
        self.assertTrue(body["started_at"] and body["files_at"], body)
        self.assertRegex(body["start_to_files_words"], r"^Start → final files: (\d+ min )?\d+ s$")
        self.assertFalse(body["taking"])
        self.assertEqual(body["stops"], [])
        record = task.options["autopilot"]
        self.assertEqual([s["status"] for s in record["steps"]], self.taken())
        self.assertTrue(all(s["at"] for s in record["steps"]))
        self.assertEqual(record["files_at"], body["files_at"])
        return task

    def trend_led_concept_chosen(self):
        from apps.pipeline.creative_rules import role_at
        from apps.pipeline.models import GateDecision
        task = self.current_task()
        trend = next(d for i, d in enumerate(task.brief.directions) if role_at(i, d) == "TREND-LED")
        chosen = GateDecision.objects.get(task=task, gate="gate_1")
        self.assertIn("never the owner's approval", chosen.notes)
        image = task.images.get(is_approved=True) if task.images.filter(is_approved=True).exists() else None
        step = next(s for s in task.options["autopilot"]["steps"] if s["status"] == "awaiting_gate_1")
        picked = task.images.get(pk=step["choice"]["image_id"])
        self.assertEqual(picked.direction_id, trend["direction_id"])
        if image is not None:
            self.assertEqual(image.pk, picked.pk)
        from apps.pipeline.models import AgentLog
        self.assertTrue(AgentLog.objects.filter(task=task, action__contains=(
            'the system chose the trend-led concept, "%s", by itself — the pitch run\'s own pick, never the owner\'s '
            "approval" % picked.direction_name)).exists())

    def test_pitch_run_a_tube_from_start_to_its_final_files_by_itself(self):
        case = copy.deepcopy(CASES["tube"])
        self.arm(Harness(case, self))
        self.start(case)
        self.assertTrue(self.current_task().options["autopilot"]["on"])
        self.at_gate_2_untouched("the pitch run (tube)")
        self.assertEqual(self.taken(), ["awaiting_gate_1", "awaiting_container_profile"])
        self.trend_led_concept_chosen()

    def test_pitch_run_a_carton_from_start_to_its_final_files_by_itself(self):
        case = copy.deepcopy(CASES["packaging"])
        self.arm(Harness(case, self))
        self.start(case)
        self.at_gate_2_untouched("the pitch run (carton)")
        self.assertEqual(self.taken(), ["awaiting_gate_1", "awaiting_dimensions"])
        self.trend_led_concept_chosen()
        step = self.current_task().options["autopilot"]["steps"][1]
        self.assertTrue(step["choice"]["dimensions"]["thickness_compensation"])    # the page's box, ticked
        self.assertEqual((step["choice"]["inside_print"], step["choice"]["back_info"]), ("referenced", "sticker"))

    def test_pitch_run_a_complete_products_carton_is_a_pitch_run_too(self):
        from apps.pipeline.models import DesignProject
        case = copy.deepcopy(CASES["complete_product"])
        h = Harness(case, self)
        self.arm(h)
        h.next_stage = dict(case["carton"], key="complete_product (the carton)", product=case["product"],
                            chosen_form=case["form"])
        self.start(case)
        project = DesignProject.objects.order_by("-pk").first()
        self.assertTrue(project.metadata["autopilot"])
        vial = project.tasks.order_by("pk").first()
        self._task_id = vial.pk
        self.at_gate_2_untouched("the pitch run (the vial)")
        # Gate 2 is his: the owner accepts the vial and approves it, through his own doors
        out = self.output()
        with out.design_preview.open("rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        r = self.client.post("/dashboard/history/tasks/%d/accept-design/" % vial.pk,
                             {"output_id": out.pk, "preview_sha256": sha, "decision": "ACCEPTED"})
        self.assertIn(r.status_code, (200, 302), r.content[:800])
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/tasks/%d/gate2_approve/" % vial.pk,
                                 data=json.dumps({"packaging_output_id": out.pk}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content[:800])
        carton = project.tasks.order_by("pk").last()
        self.assertNotEqual(carton.pk, vial.pk)
        self._task_id = carton.pk
        self.assertNotEqual(carton.options["autopilot"]["started_at"], vial.options["autopilot"]["started_at"])
        self.at_gate_2_untouched("the pitch run (the carton)")
        self.assertEqual(self.taken(), ["awaiting_gate_1", "awaiting_dimensions"])
        whole = self.client.get("/api/tasks/%d/status/" % carton.pk).json()["autopilot"]["project"]
        self.assertEqual((whole["stages"], whole["started_at"]), (2, vial.options["autopilot"]["started_at"]))
        self.assertRegex(whole["start_to_files_words"], r"^Start → final files of every stage: .+ waited at Gate 2")

    def test_pitch_run_never_asked_takes_nothing(self):
        case = copy.deepcopy(CASES["tube"])
        self.arm(Harness(case, self))
        self.create(case)
        self.expect("awaiting_gate_1", "a design started without the pitch run")
        self.assertNotIn("autopilot", self.current_task().options)
        self.assertIsNone(self.client.get("/api/tasks/%d/status/" % self._task_id).json()["autopilot"])

    # -- each waiting step, its door stood in for: the right door, the right choice, once
    def waiting(self, status, directions=None):
        from apps.pipeline import autopilot
        from apps.pipeline.models import CreativeBrief, DesignTask
        task = DesignTask.objects.create(brand=self.brand, task_text="a tube of hand cream", status=status,
                                         created_by=self.user, options={"autopilot": autopilot.new_record()})
        CreativeBrief.objects.create(task=task, directions=directions or [
            {"direction_id": "d1", "name": "Bold Clash", "design_axis": "BOLD: a clash"},
            {"direction_id": "d2", "name": "Season Now", "design_axis": "TREND-LED: this season"},
            {"direction_id": "d3", "name": "Quiet Line", "design_axis": "MINIMAL: restraint"}],
            design_intent={"schema_version": "design_intent/1.1"})
        self._task_id = task.pk
        return task

    def test_pitch_run_the_direction_taken_is_the_trend_led_one_once(self):
        from apps.pipeline import autopilot
        task = self.waiting("awaiting_direction_selection")
        with mock.patch("apps.pipeline.views.select_design_direction",
                        return_value=({"status": "queued"}, 200)) as door:
            autopilot.drive(task.pk)
            autopilot.drive(task.pk)                      # a second trigger of the same visit takes nothing
        self.assertEqual(door.call_count, 1)
        self.assertEqual(door.call_args[0][2], "d2")      # the TREND-LED direction, wherever it stands
        self.assertEqual(door.call_args[0][1], self.user)
        self.assertEqual(self.taken(), ["awaiting_direction_selection"])

    def test_pitch_run_the_trends_pressed_on_named_as_the_pitch_run(self):
        from apps.pipeline import autopilot
        from apps.pipeline.models import TrendBoard
        task = self.waiting("awaiting_trend_review")
        _seed_trend_board(task, self.dir)
        with mock.patch("apps.pipeline.tasks.run_aria_pipeline.delay") as run, \
                self.captureOnCommitCallbacks(execute=True):
            autopilot.drive(task.pk)
        self.assertEqual(run.call_count, 1)
        board = TrendBoard.objects.get(task=task)
        self.assertEqual((board.status, board.confirmed_how), (TrendBoard.CONFIRMED, autopilot.BY_THE_PITCH_RUN))
        self.assertEqual(self.taken(), ["awaiting_trend_review"])

    def test_pitch_run_no_concept_to_choose_at_all_is_a_stop_in_words(self):
        # [his goal after the pitch page, B (11)] a missing trend-led concept is never a stop (the next direction's is
        # chosen); only a Gate 1 with no concept that can be chosen at all is
        from apps.pipeline import autopilot
        task = self.waiting("awaiting_gate_1")
        with mock.patch("apps.pipeline.views.Gate1ApproveView.post") as door:
            autopilot.drive(task.pk)
        door.assert_not_called()
        body = self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]
        self.assertEqual([s["status"] for s in body["stops"]], ["awaiting_gate_1"])
        self.assertIn('no concept of the trend-led direction, "Season Now"', body["stops"][0]["words"])
        self.assertFalse(body["taking"])                  # the page shows the concepts and their one button again

    def test_pitch_run_a_status_it_comes_back_to_is_left_to_him(self):
        from apps.pipeline import autopilot
        from apps.pipeline.models import GeneratedImage
        task = self.waiting("awaiting_gate_1")
        reviewed(GeneratedImage.objects.create(task=task, direction_name="Season Now", direction_id="d2", prompt_used="p"))
        from rest_framework.response import Response
        with mock.patch("apps.pipeline.views.Gate1ApproveView.post", return_value=Response({"status": "x"})) as door:
            self.assertTrue(self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]["taking"])
            autopilot.drive(task.pk)
            self.assertEqual(door.call_count, 1)
            # back at Gate 1 with a new concept (a stop sent it back): never taken twice
            reviewed(GeneratedImage.objects.create(task=task, direction_name="Season Now", direction_id="d2", prompt_used="q"))
            autopilot.drive(task.pk)
        self.assertEqual(door.call_count, 1)
        body = self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]
        self.assertIn("came back to", body["stops"][-1]["words"])
        self.assertFalse(body["taking"])

    def test_pitch_run_an_error_is_kept_as_a_stop_never_raised(self):
        from apps.pipeline import autopilot
        task = self.waiting("awaiting_direction_selection")
        with mock.patch("apps.pipeline.views.select_design_direction", side_effect=RuntimeError("planted")):
            autopilot.drive(task.pk)
        body = self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]
        self.assertIn("planted", body["stops"][-1]["words"])

    def test_pitch_run_the_start_page_has_its_one_tick_and_a_taken_step_its_one_line(self):
        # [B (11)] the Start page as it is served: its one tick beside Start, in plain words; a design whose step the run
        # is taking tells the page so (``taking``), and the page shows one line for it — never the step's form
        from apps.pipeline import autopilot
        page = self.client.get("/dashboard/new/classic/").content.decode("utf-8")
        self.assertEqual(page.count('id="autopilot-toggle"'), 1)
        self.assertIn("Let the system take every step by itself", page)
        task = self.waiting("awaiting_gate_1")
        state = self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]
        self.assertTrue(state["taking"])
        self.assertEqual(autopilot.TAKING_WORDS, "The system is taking this step by itself…")

    def test_pitch_run_a_step_never_claimed_gives_the_page_its_form_back(self):
        # a worker that never ran the step: past its patience the page shows the step's own form and one button again
        import datetime

        from django.utils import timezone

        from apps.pipeline import autopilot
        from apps.pipeline.models import DesignTask
        task = self.waiting("awaiting_direction_selection")
        self.assertTrue(self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]["taking"])
        DesignTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - datetime.timedelta(seconds=autopilot.PATIENCE + 1))
        self.assertFalse(self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]["taking"])

    def test_pitch_run_a_trend_led_concept_not_there_is_never_a_stop_the_next_direction_is_chosen(self):
        # [his goal after the pitch page, B (11)] the first Complete Product's carton: its trend-led concept lost to the
        # picture service, the run stopped at Gate 1 — now it takes the next direction's, in their order, and says so
        from apps.pipeline import autopilot
        from apps.pipeline.models import GeneratedImage
        task = self.waiting("awaiting_gate_1")
        GeneratedImage.objects.create(task=task, direction_name="Quiet Line", direction_id="d3", prompt_used="p")
        GeneratedImage.objects.create(task=task, direction_name="Bold Clash", direction_id="d1", prompt_used="p")
        with mock.patch("apps.pipeline.services.gate1_review.image_is_selectable", return_value=True):
            choice = autopilot.choose_concept(task)
        self.assertEqual(choice["direction_name"], "Bold Clash")      # d1 stands before d3
        self.assertIn("was not there to choose", choice["words"])

    def test_pitch_run_a_door_refused_after_the_design_moved_on_is_no_stop(self):
        # a person's click (or another trigger) moved the design on before the run's post: refused, never a stop
        from rest_framework.response import Response

        from apps.pipeline import autopilot
        from apps.pipeline.models import DesignTask, GeneratedImage
        task = self.waiting("awaiting_gate_1")
        reviewed(GeneratedImage.objects.create(task=task, direction_name="Season Now", direction_id="d2", prompt_used="p"))

        def moved_on(*a, **kw):
            DesignTask.objects.filter(pk=task.pk).update(status="gate_1_approved")
            return Response({"error": "Task is not awaiting this gate"}, status=409)
        with mock.patch("apps.pipeline.views.Gate1ApproveView.post", side_effect=moved_on):
            autopilot.drive(task.pk)
        self.assertEqual(self.client.get("/api/tasks/%d/status/" % task.pk).json()["autopilot"]["stops"], [])
