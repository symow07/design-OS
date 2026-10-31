"""VQR-2B-A — concept-side analysis, golden fixtures, M3 calibration.

Deterministic local evidence only: these tests pin the §16 mask rules, the
§17 measurement invariants, the §18 golden-fixture expectations, the §19
calibration series, and the §20 provider/reconstruction isolation. Nothing
here reads reconstruction output or calls any provider.
"""
from __future__ import annotations

import builtins
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from django.test import SimpleTestCase
from PIL import Image, ImageDraw

from apps.pipeline.services import concept_analysis as ca
from apps.pipeline.services import m3_calibration as mc

FIXTURES = (Path(__file__).resolve().parents[3] / "docs" / "visual_quality"
            / "vqr2b" / "golden_fixtures")
MANIFEST = json.loads((FIXTURES / "golden_fixture_manifest.json").read_text())


def _bottle_image(bg=(255, 255, 255, 255), alpha_bg=False, cx=320, top=90,
                  bw=210, bh=720):
    img = Image.new("RGBA", (640, 900),
                    (0, 0, 0, 0) if alpha_bg else bg)
    d = ImageDraw.Draw(img)
    ch = bh * 0.22
    d.rounded_rectangle([cx - bw * 0.14, top, cx + bw * 0.14,
                         top + ch * 0.55], radius=bw * 0.14,
                        fill=(58, 42, 44, 255))
    d.rectangle([cx - bw * 0.28, top + ch * 0.45, cx + bw * 0.28, top + ch],
                fill=(183, 110, 121, 255))
    d.rounded_rectangle([cx - bw / 2, top + ch, cx + bw / 2, top + bh],
                        radius=bw * 0.16, fill=(216, 190, 184, 255))
    return img


def _lid_png(axes=(250, 210), angle=25.0, size=(640, 960)) -> bytes:
    """A compact's lid as a concept draws it: a cream disc seen tilted — an ellipse of these semi-axes turned by
    ``angle`` — its rim a darker line, on a warm ground."""
    import io
    im = Image.new("RGB", size, (226, 214, 200))
    big = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    a, b = axes
    ImageDraw.Draw(big).ellipse((400 - a, 400 - b, 400 + a, 400 + b), fill=(246, 238, 228, 255),
                                outline=(170, 120, 100, 255), width=6)
    big = big.rotate(angle, resample=Image.BICUBIC)
    im.paste(big, (size[0] // 2 - 400, size[1] // 2 - 400), big)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _bottle_png(size=(600, 900), *, tilt=0.0, ground=(236, 228, 220), body=(214, 170, 160), cap=(120, 60, 70),
                neck=True, second=None) -> bytes:
    """A standing bottle as a concept draws it: a body with rounded shoulders, a neck and a cap of its own colour, on
    a plain ground, turned ``tilt`` degrees; ``second`` stands a carton "apart" from it or "behind" it; without
    ``neck`` it is one block of one colour, capless."""
    import io
    w, h = size
    im = Image.new("RGB", size, ground)
    d = ImageDraw.Draw(im)
    cx, bw = w // 2, int(w * 0.30)
    d.rounded_rectangle([cx - bw // 2, int(h * 0.36), cx + bw // 2, int(h * 0.86)], radius=int(bw * 0.18), fill=body)
    if neck:
        nw = int(bw * 0.40)
        d.rectangle([cx - nw // 2, int(h * 0.26), cx + nw // 2, int(h * 0.36) + 5], fill=body)
        d.rounded_rectangle([cx - int(nw * 0.6), int(h * 0.14), cx + int(nw * 0.6), int(h * 0.27)], radius=6, fill=cap)
    else:
        d.rounded_rectangle([cx - bw // 2, int(h * 0.14), cx + bw // 2, int(h * 0.40)], radius=int(bw * 0.18),
                            fill=body)
    if second == "apart":
        d.rectangle([int(w * 0.04), int(h * 0.30), int(w * 0.30), int(h * 0.86)], fill=(190, 200, 214))
    elif second == "behind":
        box = Image.new("RGB", size, (190, 200, 214))
        cut = Image.new("L", size, 0)
        ImageDraw.Draw(cut).rectangle([int(w * 0.14), int(h * 0.20), int(w * 0.46), int(h * 0.86)], fill=255)
        ImageDraw.Draw(cut).rounded_rectangle([cx - bw // 2, int(h * 0.36), cx + bw // 2, int(h * 0.86)],
                                              radius=int(bw * 0.18), fill=0)       # the bottle stands in front
        im.paste(box, (0, 0), cut)
    if tilt:
        im = im.rotate(tilt, resample=Image.BICUBIC, fillcolor=ground)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _emblem_png(size=(900, 900), *, petals=5, metal=(1, 3), window=True) -> bytes:
    """A compact's lid seen square-on, as a concept draws it: a cream disc with a darker rim; inside it an oval window
    with a thin frame holding a fan of teardrop petals (``design_language._petal_path``'s own teardrop) — flat rose
    ones, and ``metal`` ones lit like foil, their lightness running from dark at the point to bright at the round end;
    ``window`` False leaves the lid plain."""
    import io
    import math
    from apps.ire.design_language import _petal_path
    w, h = size
    im = Image.new("RGB", size, (226, 214, 200))
    d = ImageDraw.Draw(im)
    cx, cy, r = w // 2, h // 2, int(0.42 * min(w, h))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(244, 234, 222), outline=(160, 110, 90), width=6)
    if window:
        a, b = int(0.40 * r), int(0.52 * r)
        wy = cy + int(0.10 * r)
        d.ellipse((cx - a, wy - b, cx + a, wy + b), fill=(222, 200, 182), outline=(150, 105, 85), width=4)
        for i in range(petals):
            share = i / max(1, petals - 1)
            theta = math.radians(-140.0 + 100.0 * share)                  # a fan opening upward
            foot = (cx + (share - 0.5) * 0.5 * a, wy + 0.50 * b)            # each petal on its own foot
            path = _petal_path("p", foot[0], foot[1], theta, 0.55 * b, 0.22 * b, lambda v: v, lambda v: v)
            poly, last = [], None
            for sg in path.segments:
                if type(sg).__name__ == "MoveTo":
                    last = (sg.x, sg.y)
                    poly.append(last)
                elif type(sg).__name__ == "CubicTo":
                    for k in range(1, 13):
                        t = k / 12.0
                        mt = 1 - t
                        poly.append((mt ** 3 * last[0] + 3 * mt * mt * t * sg.x1 + 3 * mt * t * t * sg.x2 + t ** 3 * sg.x,
                                     mt ** 3 * last[1] + 3 * mt * mt * t * sg.y1 + 3 * mt * t * t * sg.y2 + t ** 3 * sg.y))
                    last = (sg.x, sg.y)
            if i in metal:
                mask = Image.new("L", size, 0)
                ImageDraw.Draw(mask).polygon(poly, fill=255)
                lit = Image.new("RGB", size, (0, 0, 0))
                ld = ImageDraw.Draw(lit)
                c, s, length = math.cos(theta), math.sin(theta), 0.55 * b
                for k in range(80):                                        # dark at the point, bright at the round end
                    t = k / 79.0
                    col = (int(105 + 140 * t), int(65 + 120 * t), int(45 + 100 * t))
                    px, py = foot[0] + t * length * c, foot[1] + t * length * s
                    ld.line([(px + 0.3 * b * s, py - 0.3 * b * c), (px - 0.3 * b * s, py + 0.3 * b * c)], fill=col,
                            width=max(3, int(length / 60)))
                im.paste(lit, (0, 0), mask)
            else:
                d.polygon(poly, fill=(196, 140, 132))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _tube_on_its_cap_png(size=(512, 768)) -> bytes:
    """His test day finding 3 (2026-09-30, design 117), as his concept draws it: a squeeze tube standing on its flip-top
    — a hot-pink upper body, a soft-pink lower body near the ground's own colour, a hot-pink cap at its foot — on a
    ground that shades from peach at the top of the frame to pink at its foot, as a studio sweep does."""
    w, h = size
    im = Image.new("RGB", size)
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=(int(252 - 10 * t), int(214 - 30 * t), int(200 - 20 * t)))
    cx, top, foot, cap_h = w // 2, 90, 700, 90
    crimp_w, round_w = 280, 190
    body_foot = foot - cap_h

    def half(y):
        return (crimp_w + (round_w - crimp_w) * (y - top) / (body_foot - top)) / 2
    split = top + int(0.40 * (body_foot - top))
    d.polygon([(cx - half(top), top), (cx + half(top), top), (cx + half(split), split), (cx - half(split), split)],
              fill=(233, 30, 120))
    d.polygon([(cx - half(split), split), (cx + half(split), split), (cx + half(body_foot), body_foot),
               (cx - half(body_foot), body_foot)], fill=(247, 190, 200))
    cw = int(0.9 * round_w)
    d.rectangle((cx - cw // 2, body_foot, cx + cw // 2, foot), fill=(215, 25, 105))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _carton_on_a_cream_ground() -> tuple:
    """[The owner's finding on design 119, 2026-10-03.] A cream carton on a cream ground beside a rose — 119's concept,
    drawn here: a berry vial silhouette on its front panel, a gold mark and a pale pink name turned on it, a berry foot
    line under it — and its map, from a stand-in read's answer in the read's own picture pixels (nothing paid).
    ``(png, record)``."""
    from PIL import Image, ImageDraw

    from apps.pipeline.services import concept_design_map as dm
    im = Image.new("RGB", (512, 768), (240, 226, 212))
    d = ImageDraw.Draw(im)
    d.rectangle((190, 60, 320, 710), fill=(241, 210, 192))
    d.rectangle((240, 70, 270, 120), fill=(86, 17, 27))
    d.rectangle((205, 120, 305, 680), fill=(86, 17, 27))
    d.rectangle((225, 270, 285, 285), fill=(221, 185, 134))
    for y in range(300, 650, 40):
        d.rectangle((230, y, 280, y + 28), fill=(242, 182, 175))
    for x in range(200, 260, 12):
        d.rectangle((x, 692, x + 8, 700), fill=(86, 17, 27))
    d.ellipse((40, 590, 140, 690), fill=(200, 60, 90))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    png = buf.getvalue()
    answer = {"face": [380, 120, 640, 1420], "parts": [
        {"kind": "field", "name": "cream panel", "box": [380, 120, 640, 1420]},
        {"kind": "shape", "name": "deep berry vial silhouette", "box": [410, 140, 610, 1360]},
        {"kind": "mark", "name": "BBROSE wordmark", "box": [450, 540, 570, 570], "seen_text": "BBROSE"},
        {"kind": "type", "name": "turned product name", "box": [460, 600, 560, 1300], "seen_text": "RoseGlaze",
         "lettering": "display", "rotation": 90},
        {"kind": "type", "name": "foot line", "box": [400, 1384, 520, 1400], "seen_text": "LIP GLOSS",
         "lettering": "sans", "rotation": 0}],
        "light": [{"kind": "background", "box": [0, 0, 1024, 1536]}], "notes": "stand-in"}
    return png, dm.carton_record(png, answer, model="stand-in", cost={"usd": "0.000000", "calls": 0})


class TheWiringChecksW3Tests(SimpleTestCase):
    """The clean-up's wiring check, 2026-10-04 (its finding W3): a field printed on a carton's ground is coloured and
    traced — the ground's box, which holds the whole panel, no longer hides it."""

    def test_a_second_field_on_a_cartons_panel_is_coloured_and_traced(self):
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.new("RGB", (512, 768), (236, 231, 226))
        d = ImageDraw.Draw(im)
        d.rectangle((156, 150, 356, 650), fill=(142, 44, 72))          # the deep rose panel
        d.rectangle((156, 380, 356, 450), fill=(243, 230, 207))        # a cream field across it
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        answer = {"face": [312, 300, 712, 1300], "parts": [
            {"kind": "field", "name": "deep rose ground", "box": [312, 300, 712, 1300]},
            {"kind": "field", "name": "cream field", "box": [312, 760, 712, 900]}], "light": [], "notes": "stand-in"}
        rec = dm.carton_record(png, answer, model="stand-in", cost={"usd": "0.000000", "calls": 0})
        assert rec["state"] == dm.MAP_READ, rec
        colours = {p["name"]: p.get("colour") for p in rec["parts"]}
        assert colours["cream field"] is not None and colours["deep rose ground"] is not None, colours
        assert colours["cream field"] != colours["deep rose ground"], colours
        shapes = dm.trace_shapes(png, rec)
        assert "cream field" in {s["part"] for s in shapes.get("shapes") or []}, shapes.get("problems")
        assert not dm.undrawn_parts(rec, shapes, []), dm.undrawn_parts(rec, shapes, [])


class ConceptOutlineTraceTests(SimpleTestCase):
    """§BH71 PART 1, the owner's goal of 2026-09-28: \"Take the drawn outline and proportions from the chosen concept
    picture itself (read and traced to a clean vector). Templates are only a fallback, and the design says when the
    fallback was used.\" The PLAN trace, on pictures made here."""

    def test_a_standing_bottle_is_read_about_its_own_axis(self):
        """§BH71 PART 1 for a form drawn in ELEVATION: a bottle standing a little turned is stood upright and read
        about its own axis — its proportion, and its closure where its outline narrows above the body."""
        from apps.pipeline.services import concept_outline as co
        png = _bottle_png(tilt=6.0)
        t = co.trace_elevation(png)
        assert (t["state"], t["kind"]) == (co.TRACED_FROM_CONCEPT, co.PROFILE), t.get("detail")
        assert abs(abs(t["turned_deg"]) - 6.0) < 1.5, t["turned_deg"]
        assert abs(t["height_to_width"] - 3.6) < 0.2, t["height_to_width"]      # 648 px tall, 180 px at its widest
        assert abs(t["closure_share"] - 0.31) < 0.04 and t["closure_by"].startswith("the outline narrows"), t
        assert max(s for _t, s in t["profile"]) == 1.0 and t["source_sha256"] == hashlib.sha256(png).hexdigest()
        assert co.trace_elevation(png) == t                                   # the same bytes, the same record

    def test_a_product_only_one_cut_finds_is_not_read(self):
        """TWO CUTS MUST AGREE: a product near its ground's colour (task 51's pink bottle on a pink wall) is found by
        one cut and missed by the others, and one cut can be wrong and look right — the template draws, and the one
        reading is said with its numbers."""
        from apps.pipeline.services import concept_outline as co
        t = co.trace_elevation(_bottle_png(body=(228, 212, 204), cap=(200, 150, 150)))
        assert (t["state"], t["reason"]) == (co.TEMPLATE_FALLBACK, co.TRACE_MASK_UNRESOLVED), t
        assert "no second cut agrees" in t["detail"] and "read 3.6" in t["detail"], t["detail"]
        clear = co.trace_elevation(_bottle_png())                 # on a clear ground every cut agrees
        assert clear["state"] == co.TRACED_FROM_CONCEPT and clear["confirmed_by"], clear.get("detail")

    def test_two_products_and_a_capless_block_fall_back_by_name(self):
        """A picture of two products is not read as one — every seed tried and why it was not taken said — and a
        product whose outline neither narrows nor changes colour where a closure would meet it draws no closure: the
        template draws, by name."""
        from apps.pipeline.services import concept_outline as co
        apart = co.trace_elevation(_bottle_png(second="apart"))         # a prop apart from it is left out
        assert apart["state"] == co.TRACED_FROM_CONCEPT and abs(apart["height_to_width"] - 3.6) < 0.2, apart
        two = co.trace_elevation(_bottle_png(second="behind"))
        assert (two["state"], two["reason"]) == (co.TEMPLATE_FALLBACK, co.TRACE_MASK_UNRESOLVED), two
        assert "not read as one standing product" in two["detail"], two["detail"]
        block = co.trace_elevation(_bottle_png(neck=False))
        assert block["state"] == co.TRACED_FROM_CONCEPT and block["closure_share"] is None, block
        _o, source = co.outline_for(block, archetype="bottle", variant="cylindrical",
                                    image_sha256=block["source_sha256"])
        assert (source["source"], source["reason"]) == (co.TEMPLATE_FALLBACK, co.TRACE_NO_CLOSURE), source
        tiny = co.trace_elevation(__import__("base64").b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC"))
        assert (tiny["state"], tiny["reason"]) == (co.TEMPLATE_FALLBACK, co.TRACE_IMAGE_UNREADABLE), tiny

    def test_finding3_a_tube_on_its_cap_on_a_shaded_ground_is_read_and_read_again_when_drawn(self):
        """His test day finding 3 (2026-09-30, design 117): "It didn't respect the shape that we gave it". His tube stood
        on its cap on a ground shading down the frame; the border colour's cut kept only its upper body and the detail's
        lost its lower half, so the middle's reading had no second cut and the template drew. The row's own ground
        confirms the middle's reading, and the tube is read standing on its cap. A trace on record from older trace
        parameters is traced again when drawn, and written beside the drawing; one from these parameters is read."""
        import types

        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY, _profile_with_outline
        from apps.pipeline.targets.container.silhouettes import ContainerProfile
        png = _tube_on_its_cap_png()
        t = co.trace_elevation(png)
        assert (t["state"], t["kind"]) == (co.TRACED_FROM_CONCEPT, co.PROFILE), t.get("detail")
        assert any("its own row's ground" in how for how in t["confirmed_by"]), t["confirmed_by"]
        assert t["stood_narrow_end_up"] is True                                  # on its cap, as the picture stands it
        assert abs(t["height_to_width"] - 2.18) < 0.1, t["height_to_width"]      # 610 px tall, 280 px at its crimp
        assert abs(t["closure_share"] - 0.15) < 0.03, t["closure_share"]         # its 90 px cap
        pic = types.SimpleNamespace(name="concept.png", open=lambda mode: io.BytesIO(png))
        output = types.SimpleNamespace(approved_image=types.SimpleNamespace(image_file=pic))
        tube = ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0, width_mm=50.0)
        old = {"schema_version": co.SCHEMA, "view": "ELEVATION", "state": co.TEMPLATE_FALLBACK,
               "reason": co.TRACE_MASK_UNRESOLVED, "source_sha256": hashlib.sha256(png).hexdigest(),
               "params": {"version": "concept_outline_params/1.0"}}
        records = []
        drawn = _profile_with_outline(tube, {co.SCHEMA: old}, output, records)
        written = dict((key, value) for _op, key, value in records)
        assert drawn.outline["kind"] == co.PROFILE and written[OUTLINE_SOURCE_KEY]["source"] == co.TRACED_FROM_CONCEPT
        assert written[co.SCHEMA]["params"]["version"] == co.TRACE_PARAMS["version"]    # the new trace, on record
        records = []
        kept = _profile_with_outline(tube, {co.SCHEMA: dict(old, params=dict(co.TRACE_PARAMS))}, output, records)
        assert kept.outline is None and co.SCHEMA not in dict((k, v) for _op, k, v in records)   # this one is read

    def test_his_answer_the_design_map_reads_the_pictures_colours_and_leaves_the_light_out(self):
        """His answer after test day finding 3 (2026-09-30, transcribed at 23d4375): the chosen design is read from its
        picture — each part's colour measured — and "it shouldn't care about shadowing, background, the lighting on the
        bottle … the system should be smart enough to detect those things and ignore them". On the tube standing on its
        cap, with a shine streak across its hot pink and a gold letter on it: the product is stood as the picture
        stands it; the hot pink and the soft pink are measured colours with their own regions; the streak is shine,
        left out and never a colour; the gold letter is a colour, never shine; the ground is never read."""
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)
        d.line([(300, 110), (360, 230)], fill=(255, 250, 250), width=5)          # a shine streak on the hot pink
        d.rectangle((226, 170, 290, 200), fill=(214, 170, 90))                    # a gold letter on the hot pink
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        picture, mask, read = co.standing_pixels(png)
        rows = [int((mask[y] > 0).sum()) for y in range(mask.shape[0]) if (mask[y] > 0).any()]
        assert rows[-5] < rows[5] and read["stood_narrow_end_up"] is True        # its cap at its foot, as pictured
        m = dm.read_map(png)
        assert m["state"] == dm.MAP_READ and m["params"]["version"] == dm.MAP_PARAMS["version"]
        near = {name: min(m["colours"], key=lambda c, rgb=rgb: sum(
            (int(c["hex"][i:i + 2], 16) - v) ** 2 for i, v in zip((1, 3, 5), rgb))) for name, rgb in (
            ("hot", (233, 30, 120)), ("soft", (247, 190, 200)), ("gold", (214, 170, 90)))}
        for name, rgb in (("hot", (233, 30, 120)), ("soft", (247, 190, 200)), ("gold", (214, 170, 90))):
            c = near[name]
            assert max(abs(int(c["hex"][i:i + 2], 16) - v) for i, v in zip((1, 3, 5), rgb)) <= 6, (name, c)
        assert near["hot"]["share"] > 0.2 and near["soft"]["share"] > 0.2 and near["gold"]["regions"]
        assert not any(min(int(c["hex"][i:i + 2], 16) for i in (1, 3, 5)) > 240 for c in m["colours"])   # no shine
        assert 0.0 < m["light"]["shine_share"] < 0.02 and m["light"]["edge_share"] > 0.05
        assert dm.read_map(png) == m                                               # the same bytes, the same map
        assert dm.overlay_png(png)[:8] == b"\x89PNG\r\n\x1a\n"
        assert dm.read_map(b"")["reason"] == dm.MAP_NO_PRODUCT

    def test_his_answer_the_read_names_each_part_and_its_colour_comes_from_the_picture(self):
        """His answer after test day finding 3 (2026-09-30, transcribed at 23d4375): each part of the design named,
        measured and coloured from the picture, never from the written codes. The read (a stand-in answer here) names
        the hot-pink field, the soft-pink field, the cap, a gold mark and a shine; each part's box comes back as
        fractions of the product; the fields and the cap take the colour their middle holds, the mark its gold ink —
        not the pink it sits on — and the shine is light, never a part; the read's cost is stated from its usage."""
        import types

        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle((226, 170, 290, 200), fill=(214, 170, 90))                    # a gold mark on the hot pink
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        seen = {}

        def call(system, content, **kw):
            import base64
            pic = Image.open(io.BytesIO(base64.b64decode(content[0]["source"]["data"])))
            seen.update(size=pic.size, operation=kw.get("operation"), system=system)
            w, h = pic.size
            # the stand-in reads on the copy it is shown: the product runs its full height; its parts by share of it
            def box(x0, y0, x1, y1):
                return [round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)]
            answer = {"parts": [
                {"kind": "field", "name": "hot pink upper field", "box": box(0.10, 0.05, 0.90, 0.33)},
                {"kind": "field", "name": "soft pink lower field", "box": box(0.20, 0.40, 0.80, 0.80)},
                {"kind": "closure", "name": "flip-top cap", "box": box(0.25, 0.88, 0.75, 0.98)},
                {"kind": "mark", "name": "BBROSE logo", "box": box(0.30, 0.13, 0.62, 0.21), "seen_text": "BBROSE"},
                {"kind": "shine", "name": "a streak", "box": box(0.6, 0.1, 0.8, 0.2)}],
                "light": [{"kind": "shine", "box": box(0.6, 0.1, 0.8, 0.2)}], "notes": "stand-in"}
            import json as _json
            return types.SimpleNamespace(usage=types.SimpleNamespace(input_tokens=1000, output_tokens=200),
                                         content=[types.SimpleNamespace(type="text", text=_json.dumps(answer))])
        rec = dm.read_parts(None, png, call=call)
        assert seen["operation"] == dm.PARTS_OPERATION and "THE LIGHT IS NOT DESIGN" in seen["system"]
        parts = {p["name"]: p for p in rec["parts"]}
        assert set(parts) == {"hot pink upper field", "soft pink lower field", "flip-top cap", "BBROSE logo"}
        assert any("no declared kind" in p for p in rec["problems"]) and rec["light_named"][0]["kind"] == "shine"

        def near(hx, rgb, tol=8):
            return max(abs(int(hx[i:i + 2], 16) - v) for i, v in zip((1, 3, 5), rgb)) <= tol
        assert near(parts["hot pink upper field"]["colour"], (233, 30, 120))
        assert near(parts["soft pink lower field"]["colour"], (247, 190, 200))
        assert near(parts["BBROSE logo"]["colour"], (214, 170, 90)), parts["BBROSE logo"]     # its ink, not the pink
        assert parts["BBROSE logo"]["seen_text"] == "BBROSE"
        x0, y0, x1, y1 = parts["BBROSE logo"]["box"]
        assert 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0
        assert float(rec["cost"]["usd"]) > 0 and rec["cost"]["calls"] == 1
        assert dm.overlay_png(png, rec)[:8] == b"\x89PNG\r\n\x1a\n"

        def broken(*a, **k):
            raise RuntimeError("no provider")
        failed = dm.read_parts(None, png, call=broken)
        assert failed["state"] == dm.MAP_READ and failed["parts"] == [] and "raised" in failed["problems"][0]

    def test_his_answers_122_his_brief_states_its_size_where_he_writes_it(self):
        """His answers after the fixes for design 122 (2026-10-08, transcribed at fc88e8d), (2): "the drawing must always
        print my brief's size (60 ml), never the picture's text." His brief's size, in his words, wherever his briefs
        have written it: the front copy (120–122), the words a piece prints (119's "Carton side:"), the Size line, the
        capacity his New design form writes; none where it gives none."""
        from apps.pipeline.services import concept_design_map as dm
        assert dm.brief_size('Front copy: BBROSE logo, "Rose Blossom", 60 ml ℮ 2 fl oz.\n\nSize: 60 ml ℮ / 2 fl oz.') == (
            "60 ml ℮ 2 fl oz", dm.BRIEF_SIZE_FRONT)
        assert dm.brief_size('Carton side: "LIP GLOSS · ملمّع الشفاه", 8 ml ℮ / 0.27 fl oz.\n') == (
            "8 ml ℮ / 0.27 fl oz", dm.BRIEF_SIZE_FIELD)
        assert dm.brief_size("Size: 200 ml ℮ / 6.7 fl oz. Tube about 50 mm across, 180 mm tall.") == (
            "200 ml ℮ / 6.7 fl oz", dm.BRIEF_SIZE_LINE)
        assert dm.brief_size("[Container type: tube; Capacity: 60 ml; Closure: flip-top cap]") == (
            "60 ml", dm.BRIEF_SIZE_CAPACITY)
        assert dm.brief_size("A tube for Rose Velvet, 50 mm across.") is None
        for not_a_size in ("8 good things", "350 gsm", "Rose Blossom", "150 mm", "3 pt"):
            assert dm.size_stated(not_a_size) is None, not_a_size

    def test_his_answers_122_a_line_the_picture_prints_a_size_on_prints_his(self):
        """(2) on the map's own lines: 149's "100 ml / 3.38 fl. oz." prints his "60 ml ℮ 2 fl oz" — never the picture's
        figures, though it shares only 3 of 8 words with his (under the 0.6 bar, where it had taken the picture's own
        words); a line carrying more than its size keeps its other words; with no size on record it is left out by name,
        and never blocks the concept; any other line is matched as before."""
        from apps.pipeline.services import concept_design_map as dm
        his = [("Rose Blossom", "the brief's front copy"), ("60 ml ℮ 2 fl oz", "the brief's front copy")]

        def said(seen, sources):
            return dm.type_sources([{"part": "line", "seen": seen, "lettering": "sans"}], sources)[0]
        line = said("100 ml / 3.38 fl. oz.", his)
        assert (line["words"], line["source"], line["size"]) == ("60 ml ℮ 2 fl oz", "the brief's front copy", True)
        assert said("Hand Cream · 100 ml", his)["words"] == "Hand Cream · 60 ml ℮ 2 fl oz"
        unsized = said("100 ml / 3.38 fl. oz.", his[:1])
        assert unsized["words"] is None and unsized["left_out"] == "no size on record: the picture's own size is never printed"
        assert said("Rose Blossom", his)["words"] == "Rose Blossom"
        record = {"parts": [{"kind": "type", "name": "line", "box": [0.1, 0.8, 0.9, 0.9]}]}
        assert dm.undrawn_parts(record, {"types": [{"part": "line", "seen": "100 ml / 3.38 fl. oz."}]}, his[:1]) == []

    @staticmethod
    def _his_real_122(pk):
        """122's concept ``pk`` as it stands on the design — its picture and the read paid for it (fixtures_122) — traced
        by the real tracers with his brief's words; nothing paid."""
        import json
        import os

        from apps.pipeline.services import concept_design_map as dm
        here = os.path.join(os.path.dirname(__file__), "fixtures_122")
        pic = open(os.path.join(here, "concept_%d.png" % pk), "rb").read()
        rec = json.load(open(os.path.join(here, "concept_%d_map.json" % pk)))
        sources = [("Rose Blossom", "x"), ("Hand Cream / كريم اليدين", "the brief's front copy"),
                   ("Hand Cream /", "the brief's front copy"), ("كريم اليدين", "the brief's front copy"),
                   ("60 ml ℮ 2 fl oz", dm.BRIEF_SIZE_FRONT)]
        return rec, dm.trace_shapes(pic, rec, sources=sources), sources

    def test_his_go_122_line_art_frames_and_windows_in_any_colour_on_his_real_concepts(self):
        """His go of 2026-10-08 (transcribed at b0f09ca), item 1: "Trace line art and frames in ANY colour (not only
        gold): stems, leaves, buds, outlines, thin frames, borders. Keep each motif in the picture's own colour." On
        122's three real concepts every part is traced and none is left undrawn: 147's red rose; 148's frame — four
        sides leaning as the tube's perspective leans them — its threads and its cap's rosebud; 149's red engraving
        (never again one gold sparkle), its oval frame and the cleared window inside it, filled with the surface it
        shows. Each in the picture's own red, none gold."""
        from apps.pipeline.services import concept_design_map as dm

        def near(hx, rgb, tol):
            return max(abs(int(hx[i:i + 2], 16) - v) for i, v in zip((1, 3, 5), rgb)) <= tol
        for pk, lines, frames, windows in ((147, ["red line-art rose with stem and leaves"], [], []),
                                           (148, ["red line-art stems tendrils and buds threading type",
                                                  "small red line-art rosebud on cap face"], ["quad"], []),
                                           (149, ["red hairline rose and leaf engraving all-over"], ["ellipse"],
                                            ["ellipse"])):
            rec, shapes, sources = self._his_real_122(pk)
            assert dm.undrawn_parts(rec, shapes, sources) == [], (pk, dm.undrawn_parts(rec, shapes, sources))
            assert sorted(ln["part"] for ln in shapes.get("lines") or []) == sorted(lines), pk
            assert [f["shape"] for f in shapes.get("frames") or []] == frames, pk
            assert [wd["shape"] for wd in shapes.get("windows") or []] == windows, pk
            assert not shapes.get("scatters"), (pk, shapes.get("scatters"))
            for item in (shapes.get("lines") or []) + (shapes.get("frames") or []):
                hx = item["ink"]
                assert not item["gold"] and int(hx[1:3], 16) > int(hx[3:5], 16) + 40, (pk, item["part"], hx)
        _rec, shapes, _s = self._his_real_122(148)
        corners = shapes["frames"][0]["corners"]
        for got, want in zip(corners, ([0.083, 0.075], [0.910, 0.074], [0.849, 0.809], [0.152, 0.811])):
            assert abs(got[0] - want[0]) <= 0.02 and abs(got[1] - want[1]) <= 0.02, corners
        _rec, shapes, _s = self._his_real_122(149)
        ring, window = shapes["frames"][0], shapes["windows"][0]
        assert abs(ring["centre"][0] - 0.505) <= 0.01 and abs(ring["centre"][1] - 0.466) <= 0.01, ring
        assert window["centre"] == ring["centre"] and window["half"][0] < ring["half"][0], (window, ring)
        assert near(window["fill"], (0xF6, 0xE8, 0xE3), 6), window["fill"]

    def test_his_go_122_traced_line_art_is_clean_and_each_motif_its_own_named_layer(self):
        """His go of 2026-10-08, item 2: "Traced line art comes out clean: smooth curves, even stroke widths, no wobble
        or specks (the clean-curves rule), each motif its own named layer." Each motif one width; every stroke at least
        min_widths of it long and simplified to few points for its length; drawn as one smooth curve each (cubics,
        never a chain of straight steps) at that width in its own ink, under a group named for its motif; a window filled
        over the strokes and its frame stroked over the window — and none of it on the foil plate, its ink red."""
        import math

        from apps.ire import compose_container as cc
        from apps.ire.graph import ClosePath, CubicTo, Group, LineTo, MoveTo, Path
        from apps.pipeline.services import line_art as la
        for pk in (147, 148, 149):
            rec, shapes, _s = self._his_real_122(pk)
            px0, py0, px1, py1 = rec["product_box_px"]
            tall = float(py1 - py0) / float(px1 - px0)          # a stroke's length in widths of the product
            for ln in shapes.get("lines") or []:
                assert isinstance(ln["width"], float) and 0.001 <= ln["width"] <= 0.008, (pk, ln["width"])
                for st in ln["strokes"]:
                    pts = st["points"]
                    length = sum(math.hypot(b[0] - a[0], (b[1] - a[1]) * tall) for a, b in zip(pts, pts[1:]))
                    assert len(pts) >= 2 and length >= la.LINE["min_widths"] * ln["width"] * (1 - 1e-3), (pk, st)
                    assert all(type(v) is float for p in pts for v in p), pts
                    # few points for its length: at most one a half stroke along it, past its two ends
                    assert (len(pts) - 2) * 0.5 * ln["width"] <= length, (pk, len(pts), length)
        _rec, shapes, _s = self._his_real_122(149)
        zone = {"zone_id": "front", "x": 0.0, "y": 0.0, "width": 40.0, "height": 150.0}
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=40.0, y=0.0), LineTo(x=40.0, y=150.0), LineTo(x=0.0, y=150.0),
                   ClosePath()]
        backbone = type("Backbone", (), {"width_mm": 40.0, "height_mm": 150.0, "silhouette": outline})()
        group, _places, record = cc._map_front_group({"shapes": shapes}, zone, backbone, 1.0, 0.0, 0.0)
        within = group.children[0]
        assert within.name == cc.MAP_WITHIN_OUTLINE
        names = [c.name for c in within.children]
        motif = next(c for c in within.children if c.name.startswith("lineart-map-0 "))
        assert motif.name == "lineart-map-0 red hairline rose and leaf engraving all-over" and isinstance(motif, Group)
        assert all(isinstance(p, Path) and p.stroke is not None and p.fill is None for p in motif.children)
        assert len({p.stroke.width_mm for p in motif.children}) == 1
        assert all(any(isinstance(sg, CubicTo) for sg in p.segments) for p in motif.children if len(p.segments) > 2)
        assert names.index(motif.name) < names.index("window-map-0") < names.index("frame-map-0"), names
        assert record["gold_nodes"] == [] and "lineart-map-" in record["motif_prefixes"], record

    def test_his_122_a_line_setting_the_start_of_the_name_is_the_name_at_the_size_the_concept_shows(self):
        """[His test blocker on design 122 at reconstruction, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md): "the concept sets
        "Rose Blossom" small inside its oval window. The picture's layout wins (my rule): draw the name at the size the
        concept shows".] 122 is drawn with its brief's name, "Rose Blossom Hand Cream"; 149 sets "Rose Blossom" alone,
        "Hand Cream" on the line below. That line is the name — drawn as the name, centred where the picture centres it,
        at the size the picture's line holds, above the print floor — where until now a line was the name only when it
        was the whole name, so it was drawn as plain copy and the drawing stopped with no name. A line setting a later
        part of the name (119's "LIP GLOSS"), one word of a longer name, or a line beside one that carries the whole name
        is never taken for it."""
        from apps.ire import compose_container as cc
        from apps.ire.graph import ClosePath, LineTo, MoveTo
        from apps.pipeline.services import concept_design_map as dm
        _rec, shapes, sources = self._his_real_122(149)
        shapes = dict(shapes, types=dm.type_sources(shapes["types"], sources))     # each line's words, as the drawing
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=54.98, y=0.0), LineTo(x=54.98, y=120.0), LineTo(x=0.0, y=120.0),
                   ClosePath()]
        backbone = type("Backbone", (), {"width_mm": 54.98, "height_mm": 120.0, "silhouette": outline})()
        zone = {"zone_id": "z_front", "x": 0.0, "y": 0.0, "width": 54.9, "height": 99.9, "safe_margin_mm": 3.0}
        group, places, record = cc._map_type_group({"shapes": shapes}, zone, backbone, 1.0, 0.0, 0.0,
                                                   name_font="regular", product_name="Rose Blossom Hand Cream")
        runs = {c.name: c for c in group.children if getattr(c, "text", None) is not None}
        name = runs["product-name-hero-0"]
        assert name.text == "Rose Blossom" and cc.MAP_TYPE_FLOOR_PT < name.size_pt, runs
        assert not any(r.text == "Rose Blossom" for k, r in runs.items() if k.startswith("front-descriptor")), runs
        assert [p["kind"] for p in places].count("product_name") == 1
        typed = [{"part": "a", "words": "Rose Blossom", "box": [0.2, 0.44, 0.8, 0.48]},
                 {"part": "b", "words": "Hand Cream /", "box": [0.25, 0.52, 0.76, 0.55]}]
        assert cc._name_start(typed, "Rose Blossom Hand Cream") == {"a"}
        assert cc._name_start(typed, "Rose Blossom") == set()                    # the whole name: set by its words
        assert cc._name_start([dict(typed[0], words="Rose")], "Rose Blossom Hand Cream") == set()
        assert cc._name_start([dict(typed[0], words="LIP GLOSS")], "Velvet Lip Gloss") == set()
        assert cc._name_start(typed + [{"part": "c", "words": "Rose Blossom Hand Cream", "box": [0, 0.1, 1, 0.2]}],
                              "Rose Blossom Hand Cream") == set()

    def test_his_go_122_small_text_and_the_logo_are_set_where_the_picture_shows_them(self):
        """His go of 2026-10-08 (transcribed at b0f09ca), item 3: "Small text lines never need reading off the picture:
        product name, type line, Arabic, size and the logo are SET from my brief and the approved logo, placed where the
        picture shows them." A line whose ink the map did not measure (148's subcopy), a line read in another part's
        colour (149's size line, read in the cap's), and a mark whose ink is not in its box (147's cap logo) are each
        set in the box the read gave them — never refused — their ink the pixels that stand apart in that box, or the
        traced line's beside them; their words their source's (the size his brief's)."""
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")             # 117's tube, on its cap
        d = ImageDraw.Draw(im)
        for x in range(212, 300, 9):
            d.rectangle((x, 430, x + 3, 436), fill=(200, 40, 60))                        # a small line: unmeasured
            d.rectangle((x, 500, x + 3, 505), fill=(193, 32, 43))                        # its size line
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        img, mask, pbox = dm._full_size(png, dm.read_map(png))
        x0, y0, x1, y1 = pbox
        w, h = x1 - x0, y1 - y0

        def frac(a, b, c, e):
            return [round((a - x0) / w, 4), round((b - y0) / h, 4), round((c - x0) / w, 4), round((e - y0) / h, 4)]
        small = {"kind": "type", "name": "subcopy", "box": frac(207, 426, 305, 440), "colour": None,
                 "seen_text": "Hand Cream /", "lettering": "sans"}
        size = {"kind": "type", "name": "volume line", "box": frac(207, 496, 305, 509), "colour": "#F7BEC8",
                "seen_text": "100 ml / 3.38 fl. oz.", "lettering": "sans"}
        logo = {"kind": "mark", "name": "logo on cap", "box": frac(230, 560, 282, 575), "colour": None}
        got = [dm.trace_type(img, mask, pbox, small), dm.trace_type(img, mask, pbox, size),
               dm.trace_mark(img, mask, pbox, logo)]
        assert all("refused" not in g and g["set"] == dm.SET_FROM_BOX for g in got), got
        assert got[0]["box"] == small["box"] and got[2]["box"] == logo["box"]
        assert got[0]["ink"] is not None and got[1]["ink"] is not None and got[2]["ink"] is None
        hx = got[1]["ink"]
        assert int(hx[1:3], 16) > int(hx[3:5], 16) + 80, hx                           # its red, never the read's pink
        sources = [("Rose Blossom", "x"), ("Hand Cream /", "the brief's front copy"),
                   ("60 ml ℮ 2 fl oz", dm.BRIEF_SIZE_FRONT)]
        assert [t["words"] for t in dm.type_sources([dict(g, seen=g["seen"]) for g in got[:2]], sources)] == [
            "Hand Cream /", "60 ml ℮ 2 fl oz"]
        # the logo whose box holds none of its own takes the ink of the traced line beside it
        assert dm._ink_beside(got[2], [dict(got[1], box=got[1]["box"]), got[2]]) == got[1]["ink"]

    def test_his_test_blocker_122_a_background_the_read_names_never_hides_the_product(self):
        """His test blocker on design 122 (2026-10-07, transcribed at 29c2288), item 5: the read of 122's concept 149
        named the background by a box over the whole picture; taken as the product's own light, that box hid every
        pixel of the tube, and all nine of its parts were read with no colour ("no measured pixel in its box"). The
        background is said beside the map and never applied: on the same tube a read naming a whole-picture background
        colours each part exactly as a read naming no light."""
        import json as _json
        import types

        from PIL import Image

        from apps.pipeline.services import concept_design_map as dm
        png = _tube_on_its_cap_png()

        def reading(light):
            def call(system, content, **kw):
                pic = Image.open(io.BytesIO(__import__("base64").b64decode(content[0]["source"]["data"])))
                w, h = pic.size

                def box(x0, y0, x1, y1):
                    return [round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)]
                answer = {"parts": [
                    {"kind": "field", "name": "hot pink upper field", "box": box(0.10, 0.05, 0.90, 0.33)},
                    {"kind": "field", "name": "soft pink lower field", "box": box(0.20, 0.40, 0.80, 0.80)},
                    {"kind": "closure", "name": "flip-top cap", "box": box(0.25, 0.88, 0.75, 0.98)}],
                    "light": [dict(item, box=box(*item["box"])) for item in light], "notes": "stand-in"}
                return types.SimpleNamespace(usage=types.SimpleNamespace(input_tokens=1000, output_tokens=200),
                                             content=[types.SimpleNamespace(type="text", text=_json.dumps(answer))])
            return dm.read_parts(None, png, call=call)
        named = reading([{"kind": "background", "box": (0.0, 0.0, 1.0, 1.0)}])
        plain = reading([])
        colours = {p["name"]: p.get("colour") for p in named["parts"]}
        assert all(colours.values()), named["parts"]
        assert colours == {p["name"]: p.get("colour") for p in plain["parts"]}, (colours, plain["parts"])
        assert named["light_named"] == [] and [b["kind"] for b in named["light_beside"]] == ["background"]
        assert named["light_beside"][0]["why"] == "the ground around the product: not applied to its colours"

    def test_his_finding_on_119_a_cartons_map_reads_its_front_panel_never_the_silhouette_printed_on_it(self):
        """The owner's finding on design 119 (2026-10-03, transcribed at 32898c7): "nothing of my concept (silhouette,
        "Rose Glaze"); no vectors". The map cut ONE standing product from its ground, and on 119 the cream carton stood
        on a cream ground, so the cut took the berry vial silhouette printed on it for the product and no part held a
        colour. A carton's read names its FRONT PANEL itself: on a cream carton on a cream ground, beside a rose prop,
        the panel is cream, the silhouette berry, the turned name pale pink and turned, the mark gold, the foot line
        berry; the rose outside the panel is left out by name; the background and a cast shadow over the foot line are
        said, never applied; the read is held for this picture alone and the shapes are traced on the panel."""
        import types

        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services.cost_ledger import BudgetExceededError
        im = Image.new("RGB", (512, 768), (240, 226, 212))                       # a cream ground
        d = ImageDraw.Draw(im)
        d.rectangle((190, 60, 320, 710), fill=(241, 210, 192))                    # the cream carton's front panel
        d.rectangle((240, 70, 270, 120), fill=(86, 17, 27))                       # the silhouette's wand …
        d.rectangle((205, 120, 305, 680), fill=(86, 17, 27))                      # … and its vial, in berry
        d.rectangle((225, 270, 285, 285), fill=(221, 185, 134))                   # the gold mark
        for y in range(300, 650, 40):
            d.rectangle((230, y, 280, y + 28), fill=(242, 182, 175))              # the turned name's letters, pale pink
        for x in range(200, 260, 12):
            d.rectangle((x, 692, x + 8, 700), fill=(86, 17, 27))                  # the foot line, berry
        d.ellipse((40, 590, 140, 690), fill=(200, 60, 90))                        # a rose beside the carton
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        seen = {}

        def answer(face=True):
            return {**({"face": [380, 120, 640, 1420]} if face else {}), "parts": [
                {"kind": "field", "name": "cream panel", "box": [380, 120, 640, 1420]},
                {"kind": "shape", "name": "deep berry vial silhouette", "box": [410, 140, 610, 1360]},
                {"kind": "mark", "name": "BBROSE wordmark", "box": [450, 540, 570, 570], "seen_text": "BBROSE"},
                {"kind": "type", "name": "turned product name", "box": [460, 600, 560, 1300], "seen_text": "RoseGlaze",
                 "lettering": "display", "rotation": 90},
                {"kind": "type", "name": "foot line", "box": [400, 1384, 520, 1400], "seen_text": "LIP GLOSS",
                 "lettering": "sans", "rotation": 0},
                {"kind": "motif", "name": "rose prop", "box": [80, 1180, 280, 1380], "count": 1}],
                "light": [{"kind": "background", "box": [0, 0, 1024, 1536]},
                          {"kind": "shadow", "box": [300, 1370, 700, 1500]}], "notes": "stand-in"}

        def call(system, content, **kw):
            import base64
            import json as _json
            pic = Image.open(io.BytesIO(base64.b64decode(content[0]["source"]["data"])))
            seen.update(size=pic.size, operation=kw.get("operation"), system=system, text=content[1]["text"])
            return types.SimpleNamespace(usage=types.SimpleNamespace(input_tokens=3171, output_tokens=585),
                                         content=[types.SimpleNamespace(type="text", text=_json.dumps(answer()))])
        rec = dm.read_carton_parts(None, png, call=call)
        assert seen["system"] == dm.CARTON_PARTS_SYSTEM and seen["operation"] == dm.PARTS_OPERATION
        assert seen["size"] == (1024, 1536) and seen["text"].startswith("THE PICTURE is 1024 x 1536 pixels.")
        assert rec["state"] == dm.MAP_READ and rec["read"] == dm.CARTON_READ and rec["face_box_px"] == [190, 60, 320, 710]
        assert rec["turned_deg"] == 0.0 and rec["product_box_px"] == [190, 60, 320, 710]
        parts = {p["name"]: p for p in rec["parts"]}
        assert set(parts) == {"cream panel", "deep berry vial silhouette", "BBROSE wordmark", "turned product name",
                              "foot line"}
        assert any("rose prop" in p and "outside the front panel" in p for p in rec["problems"]), rec["problems"]

        def near(hx, rgb, tol=10):
            return hx is not None and max(abs(int(hx[i:i + 2], 16) - v) for i, v in zip((1, 3, 5), rgb)) <= tol
        assert near(parts["cream panel"]["colour"], (241, 210, 192)), parts["cream panel"]
        assert near(parts["deep berry vial silhouette"]["colour"], (86, 17, 27)), parts["deep berry vial silhouette"]
        assert near(parts["turned product name"]["colour"], (242, 182, 175)), parts["turned product name"]
        assert near(parts["BBROSE wordmark"]["colour"], (221, 185, 134)), parts["BBROSE wordmark"]
        assert near(parts["foot line"]["colour"], (86, 17, 27)), parts["foot line"]
        assert parts["turned product name"]["rotation"] == 90 and parts["turned product name"]["lettering"] == "display"
        assert rec["light_named"] == [] and [item["kind"] for item in rec["light_beside"]] == ["background", "shadow"]
        assert float(rec["cost"]["usd"]) > 0 and rec["cost"]["calls"] == 1
        # held for this picture alone, as a carton's read; a container's read of it is never taken for it
        assert dm.held_carton_parts(rec, png) is rec and dm.held_parts(rec, png) is None
        assert dm.held_carton_parts(rec, png + b"x") is None
        assert dm.held_carton_parts(dict(rec, read=None, parts_prompt_version=dm.PARTS_PROMPT_VERSION), png) is None
        # the shapes traced on the panel at full size: its mask is the panel, never the silhouette a cut finds
        img, mask, pbox = dm._full_size(png, rec)
        assert pbox == (190.0, 60.0, 320.0, 710.0) and int(mask.sum()) == 130 * 650
        shapes = dm.trace_shapes(png, rec)
        assert shapes["state"] == dm.SHAPES_TRACED and len(shapes["marks"]) == 1 and len(shapes["types"]) == 2
        assert dm.recolour(png, rec)["parts"] == rec["parts"]
        # a read that names no panel, fails, or meets a spending cap, by name
        none = dm.carton_record(png, answer(face=False), model="m", cost=rec["cost"])
        assert (none["state"], none["reason"]) == (dm.MAP_UNREAD, dm.CARTON_NO_FACE) and none["cost"] == rec["cost"]

        def broken(*a, **k):
            raise RuntimeError("no provider")
        failed = dm.read_carton_parts(None, png, call=broken)
        assert (failed["state"], failed["reason"]) == (dm.MAP_UNREAD, dm.PARTS_UNREAD) and "raised" in failed["detail"]

        def capped(*a, **k):
            raise BudgetExceededError("cap")
        with self.assertRaises(BudgetExceededError):
            dm.read_carton_parts(None, png, call=capped)

    def test_his_finding_on_119_a_solid_shape_the_concept_prints_is_traced_and_drawn_as_vector(self):
        """The owner's finding on design 119 (2026-10-03, transcribed at 32898c7): "Every panel is vector, drawn from the
        concept's map: front as the concept shows it". The berry vial silhouette printed on a carton's panel is traced
        as one solid shape — its wand and its vial, the name and the mark printed on it filled under them, never holes —
        refit as cubics, and drawn under every other part in its own ink; a hole the ground shows through, under no
        part, is kept."""
        import types

        from PIL import Image, ImageDraw
        from shapely.geometry import Polygon

        from apps.ire.compose_container import _map_front_group
        from apps.ire.graph import ClosePath, Document, LineTo, MoveTo
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        shapes = dm.trace_shapes(png, rec)
        assert shapes["state"] == dm.SHAPES_TRACED and len(shapes["shapes"]) == 1, shapes["problems"]
        solid = shapes["shapes"][0]
        assert solid["part"] == "deep berry vial silhouette" and solid["holes_kept"] == 0 and solid["holes_filled"] >= 9
        x0, y0, x1, y1 = solid["box"]                         # the panel's fractions: 130 x 650 px from (190, 60)
        assert abs(x0 - 15 / 130) < 0.02 and abs(x1 - 116 / 130) < 0.02 and abs(y0 - 10 / 650) < 0.01, solid["box"]
        assert abs(y1 - 621 / 650) < 0.01, solid["box"]
        assert all(len(seg) == 6 for poly in solid["cubics"] for ring in poly for seg in ring[1:])
        area = sum(Polygon([ring[0]] + [seg[4:6] for seg in ring[1:]]).area for poly in solid["cubics"]
                   for ring in poly[:1]) * 130 * 650
        assert abs(area - (101 * 561 + 31 * 50)) / (101 * 561 + 31 * 50) < 0.03, area    # wand and vial, solid
        # drawn as vector, first — under the mark and the type — in its own ink
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=40.0, y=0.0), LineTo(x=40.0, y=200.0), LineTo(x=0.0, y=200.0),
                   ClosePath()]
        backbone = types.SimpleNamespace(width_mm=40.0, height_mm=200.0, silhouette=outline, cap_region=[])
        group, _places, record = _map_front_group({"shapes": shapes}, {"zone_id": "z", "x": 0.0, "y": 0.0,
                                                                      "width": 40.0, "height": 200.0},
                                                  backbone, 1.0, 0.0, 0.0)
        paths = [n for n, _p in Document(page_w=40.0, page_h=200.0, root=group).walk() if n.type == "path"]
        assert paths[0].name == "shape-map-0" and paths[0].fill.color.to_hex() == solid["ink"].upper()
        assert "deep berry vial silhouette" in record["drawn"]
        # a hole the ground shows through, under no part, is kept
        im = Image.open(io.BytesIO(png)).convert("RGB")
        ImageDraw.Draw(im).rectangle((245, 160, 265, 200), fill=(241, 210, 192))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        holed = buf.getvalue()
        again = dm.trace_shapes(holed, dict(rec, source_sha256=hashlib.sha256(holed).hexdigest()))["shapes"][0]
        assert again["holes_kept"] == 1 and len(again["cubics"][0]) == 2

    def test_the_wiring_checks_w1_a_front_whose_map_names_no_motif_expects_none(self):
        """The clean-up's wiring check, 2026-10-04 (its finding W1): a map front records the motif it draws only where
        the map names one. The 119 carton's front — a solid shape, a name and a mark, no drip and no sparkle — records
        no motif node names, so the motif check finds no motif expected from the map; a front with a scattered motif
        still records them (the rule stands: a motif the map names must be drawn)."""
        import types

        from apps.ire.compose_container import MAP_MOTIF_PREFIXES, _map_front_group
        from apps.ire.container_motif_fidelity import MOTIF_MISSING, validate_motif_fidelity
        from apps.ire.graph import ClosePath, Document, LineTo, MoveTo
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        shapes = dm.trace_shapes(png, rec)
        assert shapes["state"] == dm.SHAPES_TRACED and not shapes.get("scatters") and not shapes.get("bands")
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=40.0, y=0.0), LineTo(x=40.0, y=200.0), LineTo(x=0.0, y=200.0),
                   ClosePath()]
        backbone = types.SimpleNamespace(width_mm=40.0, height_mm=200.0, silhouette=outline, cap_region=[])
        zone = {"zone_id": "z", "x": 0.0, "y": 0.0, "width": 40.0, "height": 200.0}
        group, _places, record = _map_front_group({"shapes": shapes}, zone, backbone, 1.0, 0.0, 0.0)
        assert record["motif_prefixes"] == []
        doc = Document(page_w=40.0, page_h=200.0, root=group, metadata={"map_front": record})
        none = {"reconstruction_capability": "NONE", "requested_family": None}
        assert validate_motif_fidelity(doc, none)["axes"]["motif_family"].get("code") != MOTIF_MISSING
        # a front with a scattered motif still says it, and still must draw it
        star = {"part": "gold sparkles", "count": 1, "stars": [{"outline": [(0.4, 0.4), (0.5, 0.3), (0.6, 0.4)],
                                                                 "ink": "#C9A24B"}]}
        _g, _p, with_motif = _map_front_group({"shapes": dict(shapes, scatters=[star])}, zone, backbone, 1.0, 0.0, 0.0)
        assert with_motif["motif_prefixes"] == list(MAP_MOTIF_PREFIXES)

    def test_his_second_blocker_123_garden_wraps_scalloped_band_draws_however_the_read_names_it(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): "Tell me
        in words which part it was and why ... Make that part drawable (it's 122's own look: line-art rose field, oval,
        scallop band, type)".] 123's Garden Wrap, its two real reads: the first named its scalloped pink base band a
        "shape", the second a "band" — refused as no plain stripe, its colour running on 12 pixels past its straight rows,
        and the concept stopped at drawing. Either read draws it now: the band traced as the shape it is, its scallops
        kept, at its foot; and every part of Blossom Arch and Stem Journey, read once each, is traced (whether each
        draws as pictured is the one check's: ``test_his_second_blocker_123_a_concept_shown_drawable_draws``)."""
        import json
        import os

        from apps.pipeline.services import concept_design_map as dm
        here = os.path.join(os.path.dirname(__file__), "fixtures_123")
        sources = [("Rose Blossom Hand Cream", "product name"), ("Hand Cream / كريم اليدين", "front copy"),
                   ("60 ml ℮ 2 fl oz", "front copy")]
        for pk, read in ((150, "concept_150_map_first.json"), (150, "concept_150_map.json"),
                         (151, "concept_151_map.json"), (152, "concept_152_map.json")):
            png = open(os.path.join(here, "concept_%d.png" % pk), "rb").read()
            record = json.load(open(os.path.join(here, read)))
            shapes = dm.trace_shapes(png, record, sources=sources)
            self.assertEqual(shapes["state"], dm.SHAPES_TRACED, (read, shapes.get("reason")))
            undrawn = [u for u in dm.undrawn_parts(record, shapes, sources) if u["kind"] != "type"]
            self.assertEqual(undrawn, [], read)
            if read == "concept_150_map.json":
                band, = [sh for sh in shapes["shapes"] if sh.get("part") == "scalloped pink base band"]
                self.assertTrue(band["shaped_band"])
                self.assertGreater(band["box"][1], 0.85)                                  # at the carton's foot
                self.assertFalse(any("scalloped pink base band" in p for p in shapes["problems"]), shapes["problems"])

    def test_his_second_blocker_123_a_solid_that_paints_over_its_ground_is_said(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2):
        "a concept shown as drawable must draw".] Blossom Arch's oval, read in its line art's own pink (#EAB7B3, within
        the tracer's reach of its pale ground), traced as the pale ground round its rose — most of it the picture's
        ground: the one check says so in words. Garden Wrap's band (either read) and Stem Journey's paint their own ink."""
        import json
        import os

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import _ground_painted
        here = os.path.join(os.path.dirname(__file__), "fixtures_123")
        share = {}
        for pk, read in ((150, "concept_150_map_first.json"), (150, "concept_150_map.json"),
                         (151, "concept_151_map.json"), (152, "concept_152_map.json")):
            png = open(os.path.join(here, "concept_%d.png" % pk), "rb").read()
            shapes = dm.trace_shapes(png, json.load(open(os.path.join(here, read))), sources=[])
            share[read] = [(sh["part"], sh["ground_share"]) for sh in shapes["shapes"]]
            said = _ground_painted(shapes)
            if pk == 151:
                self.assertEqual([(u["kind"], u["name"]) for u in said],
                                 [("shape", "oval cartouche frame with rose and vines illustration")], share)
                self.assertIn("pale ground", said[0]["why"])
            else:
                self.assertEqual(said, [], share)
        limit = dm.SHAPE_PARAMS["shape_ground_share"]
        self.assertGreater(share["concept_151_map.json"][0][1], limit + 0.2, share)
        for read in ("concept_150_map_first.json", "concept_150_map.json", "concept_152_map.json"):
            self.assertLess(share[read][0][1], limit, share)

    def test_his_second_blocker_123_the_big_bloom_is_found_where_the_concept_draws_one(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
        "the big rose in Blossom Arch / Stem Journey is 122's rose, whole and scaled ($0)".] The one big bloom a
        concept's line art draws — Blossom Arch's rose in its oval, Stem Journey's hero rose — found by its strokes'
        density; Garden Wrap's all-over field, by either read, has none (it stays the field it is)."""
        import json
        import os

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.packaging import big_bloom
        here = os.path.join(os.path.dirname(__file__), "fixtures_123")
        blooms = {}
        for pk, read in ((150, "concept_150_map_first.json"), (150, "concept_150_map.json"),
                         (151, "concept_151_map.json"), (152, "concept_152_map.json")):
            png = open(os.path.join(here, "concept_%d.png" % pk), "rb").read()
            shapes = dm.trace_shapes(png, json.load(open(os.path.join(here, read))), sources=[])
            blooms[read] = {line["part"]: big_bloom(line) for line in shapes.get("lines") or []}
        self.assertEqual(set(blooms["concept_150_map_first.json"].values()), {None}, blooms)
        self.assertEqual(set(blooms["concept_150_map.json"].values()), {None}, blooms)
        arch = blooms["concept_151_map.json"]["rose vines around oval"]
        stem, = blooms["concept_152_map.json"].values()
        for box in (arch, stem):
            self.assertIsNotNone(box, blooms)
            self.assertLess(box[3] - box[1], 0.3, blooms)                 # one bloom, never the whole field
        self.assertLess(stem[1], arch[1])                                  # Stem Journey's rose stands higher

    def _garden_wrap(self, read):
        import json
        import os

        from apps.pipeline.services import concept_design_map as dm
        here = os.path.join(os.path.dirname(__file__), "fixtures_123")
        png = open(os.path.join(here, "concept_150.png"), "rb").read()
        record = json.load(open(os.path.join(here, read)))
        sources = [("Rose Blossom Hand Cream", "the product's name on the record"),
                   ("Hand Cream / كريم اليدين", "the brief's front copy"), ("Hand Cream /", "the brief's front copy"),
                   ("كريم اليدين", "the brief's front copy"), ("60 ml ℮ 2 fl oz", "the brief's front copy")]
        shapes = dm.trace_shapes(png, record, sources=sources)
        return record, dict(shapes, types=dm.type_sources(shapes.get("types") or [], sources))

    def test_his_second_blocker_123_garden_wraps_band_runs_edge_to_edge_into_the_bleed_from_either_read(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): "Make
        that part drawable (it's 122's own look: line-art rose field, oval, scallop band, type)".]
        Its scalloped band, read a "shape" once and a "band" once, traced as the shape it is either way and run edge to
        edge: past both sides and its foot into the bleed (his rule 3, "EDGE TO EDGE MEANS BLEED"), the rows it meets
        each side at kept for the sides to continue it — so the front's fit leaves it where the picture prints it."""
        from apps.ire.compose import _bleeds
        for read in ("concept_150_map_first.json", "concept_150_map.json"):
            _record, shapes = self._garden_wrap(read)
            band, = [sh for sh in shapes["shapes"] if sh["part"] == "scalloped pink base band"]
            self.assertTrue(_bleeds(band), read)
            self.assertEqual(sorted(band["edges"]), ["left", "right"], read)
            self.assertLess(band["box"][0], -0.05, read)
            self.assertGreater(band["box"][2], 1.05, read)
            self.assertGreater(band["box"][3], 1.0, read)                  # past its foot
            self.assertGreater(band["picture_box"][1], 0.89, read)          # its top where the picture prints it

    def test_his_second_blocker_123_garden_wraps_type_as_the_picture_sets_it(self):
        """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010): "Make
        that part drawable (it's 122's own look: line-art rose field, oval, scallop band, type)".]
        Its name, "Rose" over "Blossom", set at one size, as the picture sets them alike (they stood at 21.9 and 10.5 pt,
        each sized from its own trace); "Hand Cream", the half of his front copy the picture prints on its own line,
        without the "/" left at its end — while a half the picture sets beside its Arabic on one line keeps its
        separator (his rule 2 for 119)."""
        import types

        from apps.ire.compose_container import _map_type_group
        from apps.ire.graph import ClosePath, LineTo, MoveTo
        from apps.pipeline.services import concept_design_map as dm
        _record, shapes = self._garden_wrap("concept_150_map.json")
        words = {t["part"]: t.get("words") for t in shapes["types"]}
        self.assertEqual(words["descriptor English"], "Hand Cream")
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=42.45, y=0.0), LineTo(x=42.45, y=134.59), LineTo(x=0.0, y=134.59),
                   ClosePath()]
        panel = types.SimpleNamespace(width_mm=42.45, height_mm=134.59, silhouette=outline, cap_region=[])
        zone = {"zone_id": "carton-front", "x": 0.0, "y": 0.0, "width": 42.45, "height": 134.59}
        _group, _places, record = _map_type_group({"shapes": shapes}, zone, panel, 1.0, 0.0, 0.0, name_font="bold",
                                                  product_name="Rose Blossom Hand Cream")
        sizes = {line["part"]: line["size_pt"] for line in record["typed"]}
        self.assertEqual(sizes["product name line 1"], sizes["product name line 2"], sizes)
        self.assertGreater(sizes["product name line 1"], 18.0, sizes)
        one_line = dm.type_sources([{"part": "side", "seen": "LIP GLOSS · ملمّع", "box": [0, 0, 1, 0.1]}],
                                   [("LIP GLOSS · ملمّع", "the brief's side copy")])
        self.assertEqual(one_line[0]["words"], "LIP GLOSS · ملمّع")

    def test_his_blocker_123_a_continued_cartons_line_art_is_the_containers_never_its_photos_strokes(self):
        """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3): "The
        carton's inside follows the inside reference (the berry petal flowers), and its flaps/sides repeat 122's line
        art."]
        A carton continuing its approved container: each line-art part of its front draws the container's own line art
        — its flat redraw's outlines, cropped to the part's box, in its ink — never the strokes traced from the carton's
        own photo; the part still recorded as its motif, drawn."""
        import types

        from apps.ire.compose_container import _map_front_group
        from apps.ire.graph import ClosePath, LineTo, MoveTo
        from apps.ire.tests.test_compose import _field_art
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        shapes = dm.trace_shapes(png, rec)
        line = {"part": "red rose lines", "ink": "#123456", "width": 0.01, "gold": False,
                "strokes": [{"points": [[0.2, 0.2], [0.8, 0.5]], "closed": False}],
                "continued": dict(_field_art(), part_box=[0.1, 0.1, 0.9, 0.6])}
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=40.0, y=0.0), LineTo(x=40.0, y=200.0), LineTo(x=0.0, y=200.0),
                   ClosePath()]
        backbone = types.SimpleNamespace(width_mm=40.0, height_mm=200.0, silhouette=outline, cap_region=[])
        zone = {"zone_id": "z", "x": 0.0, "y": 0.0, "width": 40.0, "height": 200.0}
        group, _places, record = _map_front_group({"shapes": dict(shapes, lines=[line])}, zone, backbone, 1.0, 0.0, 0.0)
        found = []

        def walk(n):
            found.append(n)
            for c in getattr(n, "children", None) or []:
                walk(c)
        walk(group)
        art = next(n for n in found if getattr(n, "name", "") == "lineart-map-0 red rose lines")
        path, = art.children
        assert art.clip and path.name == "lineart-map-0-continued" and path.fill.color.to_hex().upper() == "#AF2B2F"
        assert not any(getattr(n, "stroke", None) is not None and str(getattr(n, "name", "")).startswith("lineart-map-0-")
                       for n in found)                               # no stroke traced from the photo
        xs = [s.x for s in art.clip if hasattr(s, "x")]
        assert abs(min(xs) - 4.0) < 1e-6 and abs(max(xs) - 36.0) < 1e-6       # cropped to the part's box
        assert "red rose lines" in record["drawn"], record["drawn"]

    def test_his_finding_on_119_a_turned_display_name_is_drawn_as_the_concept_letters_it(self):
        """The owner's finding on design 119 (2026-10-03, transcribed at 32898c7): "nothing of my concept (silhouette,
        "Rose Glaze")". 119 stands its name on end, in a chunky display face, up its silhouette. A display or turned line
        is traced and set in the closest face — read turned to run left to right, every point turned back — and drawn as
        the picture letters it: where no face comes close, its traced outlines, with why; where one does (the name set
        here in Poppins Black, stood on end), the face's letters, in place. It is never typed across the panel; the foot
        line, upright in a sans, is typed as before."""
        import types

        from PIL import Image, ImageDraw, ImageFont

        from apps.ire import font_roles
        from apps.ire.compose_container import _map_type_group
        from apps.ire.graph import ClosePath, Document, LineTo, MoveTo, TextRun
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        shapes = dm.trace_shapes(png, rec)
        turned = next(t for t in shapes["types"] if t["part"] == "turned product name")
        assert turned["rotation"] == 90 and turned["outlines"]["svg"].lstrip().startswith("<?xml")
        setting = turned["lettering_set"]
        # [his rule 3, 2026-10-05: "Try setting the name in the granted display faces ... before tracing it."] no face
        # is the picture's own (its letters are bars): set in the closest of his four display faces, never traced
        assert setting["read_turned"] is True and setting["state"] == dm.LETTERING_SET, setting.get("why")
        assert setting["face"] in dm.DISPLAY_FACES_FIRST and setting["set_by"].startswith("his rule 3"), setting
        assert {row[0] for row in setting["display_faces_measured"]} == set(dm.DISPLAY_FACES_FIRST)
        foot = next(t for t in shapes["types"] if t["part"] == "foot line")
        assert "lettering_set" not in foot and "outlines" not in foot
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=40.0, y=0.0), LineTo(x=40.0, y=200.0), LineTo(x=0.0, y=200.0),
                   ClosePath()]
        backbone = types.SimpleNamespace(width_mm=40.0, height_mm=200.0, silhouette=outline, cap_region=[])
        front = {"shapes": dict(shapes, types=dm.type_sources(shapes["types"], []))}
        group, _places, record = _map_type_group(front, {"zone_id": "z", "x": 0.0, "y": 0.0, "width": 40.0,
                                                         "height": 200.0}, backbone, 1.0, 0.0, 0.0,
                                                 name_font="bold", product_name="Rose Glaze Lip Gloss")
        nodes = [n for n, _p in Document(page_w=40.0, page_h=200.0, root=group).walk()]
        lettered = [n for n in nodes if n.type == "path" and n.name.startswith("front-lettering-")]
        assert len(lettered) == 1 and lettered[0].fill.color.to_hex() == turned["ink"].upper()
        x0, y0, x1, y1 = record["boxes"]["turned product name"]
        assert (y1 - y0) * 200.0 > 3 * (x1 - x0) * 40.0                        # stood on end, as pictured
        assert not any(isinstance(n, TextRun) and n.text == "RoseGlaze" for n in nodes)
        assert any(isinstance(n, TextRun) and n.text == "LIP GLOSS" for n in nodes)    # the foot line, typed
        line = next(row for row in record["typed"] if row["part"] == "turned product name")
        assert line["rotation"] == 90 and line["lettering"]["state"] == "SET" and "drawn" not in line["lettering"]
        assert line["lettering"]["set_by"].startswith("his rule 3"), line["lettering"]
        # a name the picture letters in a face the house holds, stood on end: set in that face, every point turned back
        im = Image.new("RGB", (512, 768), (86, 17, 27))
        font = ImageFont.truetype(font_roles.catalogue()["Poppins-Black"]["path"], 96)
        text = Image.new("L", (620, 140), 0)
        ImageDraw.Draw(text).text((10, 0), "RoseGlaze", font=font, fill=255)
        text = text.rotate(90, expand=True)                                   # reads from the foot up
        im.paste(Image.new("RGB", text.size, (242, 182, 175)), (190, 80), text)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        face_png = buf.getvalue()
        ys, xs = np.nonzero(np.asarray(text) > 127)
        answer = {"face": [200, 100, 824, 1500], "parts": [
            {"kind": "field", "name": "berry panel", "box": [200, 100, 824, 1500]},
            {"kind": "type", "name": "name on end", "seen_text": "RoseGlaze", "lettering": "display", "rotation": 90,
             "box": [2 * (190 + int(xs.min())) - 4, 2 * (80 + int(ys.min())) - 4, 2 * (190 + int(xs.max())) + 4,
                     2 * (80 + int(ys.max())) + 4]}], "light": []}
        face_rec = dm.carton_record(face_png, answer, model="stand-in", cost={"usd": "0.000000", "calls": 0})
        set_line = next(t for t in dm.trace_shapes(face_png, face_rec)["types"] if t["part"] == "name on end")
        got = set_line["lettering_set"]
        assert got["state"] == dm.LETTERING_SET and got["face"].startswith("Poppins-"), got.get("why")
        pts = [p for poly in got["layers"][0]["cubics"] for ring in poly for p in [ring[0]] + [s[4:6] for s in ring[1:]]]
        bx0, by0 = min(p[0] for p in pts), min(p[1] for p in pts)
        bx1, by1 = max(p[0] for p in pts), max(p[1] for p in pts)
        tx0, ty0, tx1, ty1 = set_line["box"]
        assert max(abs(bx0 - tx0), abs(bx1 - tx1)) < 0.03 and max(abs(by0 - ty0), abs(by1 - ty1)) < 0.03, (
            [bx0, by0, bx1, by1], set_line["box"])

    def test_his_answer_a_thin_or_small_part_takes_its_own_ink_never_the_ground_or_its_shade(self):
        """His answer after test day finding 3 (2026-09-30): measured on 117, its gold rule read cream, its gold
        sparkles soft pink and its type lines a shaded soft pink — the ground's shade or a surface under them won. On
        the tube on its cap: a gold rule where the hot pink meets the soft pink, gold stars on the soft pink, a brown
        type line on it and a patch of the soft pink in shade: the rule and the stars are gold, the type brown, never the
        pink or its shade; and the map on record is coloured again from its picture with no new read."""
        import json as _json
        import types

        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)
        split = 90 + int(0.40 * 520)
        d.rectangle((150, split - 2, 362, split + 2), fill=(214, 170, 90))                  # a gold rule at the split
        for x in (190, 240, 290):
            d.polygon([(x, 380), (x + 5, 392), (x, 404), (x - 5, 392)], fill=(214, 170, 90))   # gold stars
        d.rectangle((168, 440, 238, 470), fill=(222, 160, 172))                             # the soft pink in shade,
        d.rectangle((240, 452, 312, 460), fill=(140, 80, 60))                               # beside a brown type line
        #                                                  — more of the shade than of the ink inside the line's box
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()

        def call(system, content, **kw):
            import base64
            w, h = Image.open(io.BytesIO(base64.b64decode(content[0]["source"]["data"]))).size
            top, foot = 10 * dm.PARTS_UPSCALE, h - 10 * dm.PARTS_UPSCALE      # the product inside the crop's pad
            def y(v):                                                          # a picture row to the copy's pixels
                return round(top + (v - 90) / 610.0 * (foot - top))
            answer = {"parts": [
                {"kind": "field", "name": "hot pink field", "box": [round(0.15 * w), y(95), round(0.85 * w), y(290)]},
                {"kind": "field", "name": "soft pink field", "box": [round(0.2 * w), y(305), round(0.8 * w), y(600)]},
                {"kind": "rule", "name": "gold rule", "box": [round(0.12 * w), y(split - 3), round(0.88 * w),
                                                              y(split + 3)]},
                {"kind": "motif", "name": "gold stars", "box": [round(0.25 * w), y(376), round(0.6 * w), y(408)],
                 "count": 3},
                {"kind": "type", "name": "a type line", "box": [round(0.3 * w), y(448), round(0.7 * w), y(464)],
                 "seen_text": "Body Lotion", "lettering": "sans"}], "light": [], "notes": "stand-in"}
            return types.SimpleNamespace(usage=types.SimpleNamespace(input_tokens=900, output_tokens=150),
                                         content=[types.SimpleNamespace(type="text", text=_json.dumps(answer))])
        rec = dm.read_parts(None, png, call=call)
        parts = {p["name"]: p for p in rec["parts"]}

        def near(hx, rgb, tol=10):
            return hx is not None and max(abs(int(hx[i:i + 2], 16) - v) for i, v in zip((1, 3, 5), rgb)) <= tol
        assert near(parts["gold rule"]["colour"], (214, 170, 90)), parts["gold rule"]
        assert near(parts["gold stars"]["colour"], (214, 170, 90)), parts["gold stars"]
        assert near(parts["a type line"]["colour"], (140, 80, 60)), parts["a type line"]
        assert near(parts["soft pink field"]["colour"], (247, 190, 200))
        again = dm.recolour(png, rec)
        assert [(p["name"], p["colour"]) for p in again["parts"]] == [(p["name"], p["colour"]) for p in rec["parts"]]
        assert again["cost"] == rec["cost"] and again["params"]["version"] == dm.MAP_PARAMS["version"]

    def test_his_answer_the_drip_band_and_the_rule_are_traced_from_the_picture(self):
        """His answer after test day finding 3 (2026-09-30, transcribed at 23d4375): each part's "color, the shape and
        everything". On the tube standing on its cap, a gold rule where the hot pink meets the soft pink and under it a
        cream band ending in four drips, edged in a 3 px gold line, with gold stars below: the band is traced as the
        cream joined to its top without crossing its edge — four drips, its edge about 3 px wide and gold, never the
        stars — and the rule by its own rows; a map of another picture, or of a product the read turned, is refused."""
        import math

        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        d.rectangle((cx - half(split), split - 2, cx + half(split), split + 1), fill=(214, 170, 90))   # the rule
        edge = []
        for x in range(int(cx - half(330)) + 6, int(cx + half(330)) - 5):
            u = (x - (cx - half(330))) / (2 * half(330))
            low = 335 + 30 * (1 - math.cos(2 * math.pi * 4 * u))                     # four drips, 335 down to 395
            d.line([(x, split + 2), (x, low)], fill=(250, 240, 228))
            edge.append((x, low))
        d.line(edge, fill=(214, 170, 90), width=3)                                  # the band's gold edge
        for x in (200, 256, 312):
            d.polygon([(x, 430), (x + 4, 438), (x, 446), (x - 4, 438)], fill=(214, 170, 90))     # gold stars below
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[
            {"kind": "rule", "name": "gold rule", "colour": "#D6AA5A",
             "box": [fx(cx - half(split)), fy(split - 2), fx(cx + half(split)), fy(split + 2)]},
            {"kind": "band", "name": "cream drip band", "colour": "#FAF0E4",
             "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]},
            {"kind": "motif", "name": "cream drips with a gold edge", "colour": "#D6AA5A", "count": 4,
             "box": [fx(cx - half(330)), fy(330), fx(cx + half(330)), fy(398)]}])
        s = dm.trace_shapes(png, rec)
        assert s["state"] == dm.SHAPES_TRACED and s["problems"] == [], s
        (band,), (rule,) = s["bands"], s["rules"]
        assert (band["drips"], band["drips_read"]) == (4, 4), band["drips"]
        assert abs(band["edge_width"] * (x1 - x0) - 3.0) <= 1.0, band["edge_width"]
        assert max(abs(int(band["edge_ink"][i:i + 2], 16) - v) for i, v in zip((1, 3, 5), (214, 170, 90))) <= 12
        lows = [y * (y1 - y0) + y0 for _x, y in band["outline"]]
        assert abs(min(lows) - (split + 2)) <= 4 and abs(max(lows) - 396.5) <= 3, (min(lows), max(lows))
        assert max(y * (y1 - y0) + y0 for line in band["edge"] for _x, y in line) < 420      # never the stars
        assert abs(rule["box"][1] * (y1 - y0) + y0 - (split - 2)) <= 1, rule["box"]
        assert abs(rule["box"][3] * (y1 - y0) + y0 - (split + 2)) <= 1, rule["box"]
        assert dm.trace_shapes(png, dict(rec, source_sha256="ab" * 32))["state"] == dm.SHAPES_REFUSED
        assert "turned" in dm.trace_shapes(png, dict(rec, turned_deg=30.0))["reason"]

    def test_his_look_the_drip_band_is_traced_and_drawn_smooth_never_in_zigzags(self):
        """His look at 117 drawn from its map (2026-10-02, transcribed at 99ede0a): "in the drips, the edges ... it's
        looking like uh, zigzags on them everything should be smooth". A cream band whose gold edge wobbles a pixel or
        a pixel along its four drips, as a shaded foil line does: its outline and its edge are traced as the smooth line
        through the pixels — the direction turning back on itself at most twice per 100 px of edge, where the pixel
        steps turned it back every few pixels — still four drips, its foot within 3 px of the pixels; and the front
        draws the edge as one curve through it, never straight steps."""
        import math
        import random

        from PIL import Image, ImageDraw

        from apps.ire.graph import CubicTo, LineTo
        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        d.rectangle((cx - half(split), split - 2, cx + half(split), split + 1), fill=(214, 170, 90))   # the rule
        wobble = random.Random(117)
        edge = []
        for x in range(int(cx - half(330)) + 6, int(cx + half(330)) - 5):
            u = (x - (cx - half(330))) / (2 * half(330))
            low = 335 + 30 * (1 - math.cos(2 * math.pi * 4 * u)) + wobble.choice((-1.0, 0.0, 1.0))
            d.line([(x, split + 2), (x, low)], fill=(250, 240, 228))
            edge.append((x, low))
        d.line(edge, fill=(214, 170, 90), width=3)                                  # the band's gold edge, wobbling
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[
            {"kind": "rule", "name": "gold rule", "colour": "#D6AA5A",
             "box": [fx(cx - half(split)), fy(split - 2), fx(cx + half(split)), fy(split + 2)]},
            {"kind": "band", "name": "cream drip band", "colour": "#FAF0E4",
             "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]},
            {"kind": "motif", "name": "cream drips with a gold edge", "colour": "#D6AA5A", "count": 4,
             "box": [fx(cx - half(330)), fy(330), fx(cx + half(330)), fy(398)]}])
        s = dm.trace_shapes(png, rec)
        (band,) = s["bands"]
        assert band["drips"] == 4, band["drips"]

        def px(line):
            return [((x * (x1 - x0)) + x0, (y * (y1 - y0)) + y0) for x, y in line]

        def backs_per_100px(pts):
            turns, length = [], 0.0
            for (ax, ay), (bx, by), (qx, qy) in zip(pts, pts[1:], pts[2:]):
                t = math.atan2(qy - by, qx - bx) - math.atan2(by - ay, bx - ax)
                t = (t + math.pi) % (2 * math.pi) - math.pi
                if abs(t) > math.radians(2):
                    turns.append(t > 0)
                length += math.hypot(bx - ax, by - ay)
            return 100.0 * sum(a != b for a, b in zip(turns, turns[1:])) / length
        for line in band["edge"]:
            assert backs_per_100px(px(line)) <= 2.0, backs_per_100px(px(line))
        assert backs_per_100px(px(band["outline"])) <= 2.0
        # never more than 2.5 px from the band's own pixels: its foot at the drips' lowest
        lows = [y for _x, y in px(band["outline"])]
        assert abs(max(lows) - 396.5) <= 3.0, max(lows)
        # the front draws the edge as one curve through the line
        from django.conf import settings

        from apps.ire.compose_container import compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        doc = compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
            map_front={"shapes": s, "edge_part": None})
        nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
        drawn = [name for name in nodes if str(name).startswith(("band-map-0", "drip-map-0"))
                 and not str(name).endswith("-arches")]
        assert "band-map-0" in drawn and any(str(name).startswith("drip-map-0") for name in drawn), drawn
        for name in drawn:                         # the band and its edge, every layer of them, as curves
            kinds = {type(sg) for sg in nodes[name].segments}
            assert CubicTo in kinds and LineTo not in kinds, (name, kinds)

    def test_his_answer_the_sparkle_stars_are_traced_each_by_its_gold_core(self):
        """His answer after test day finding 3 (2026-09-30, transcribed at 23d4375): each motif's "color, the shape and
        everything". On the tube standing on its cap, three four-point gold stars on the soft pink — one of them faint,
        its rays fading into the pink round a gold core — a pale cream highlight with no gold in it, and a star under
        a type line's box: the three stars are traced, each its own outline in its core's gold, the faint one with its
        rays; the highlight is never a star, and the one among the type is the type's."""
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)

        def star(x, y, r, fill):
            d.polygon([(x, y - r), (x + r // 4, y - r // 4), (x + r, y), (x + r // 4, y + r // 4), (x, y + r),
                       (x - r // 4, y + r // 4), (x - r, y), (x - r // 4, y - r // 4)], fill=fill)
        star(200, 420, 6, (214, 170, 90))
        star(256, 440, 6, (214, 170, 90))
        star(312, 420, 6, (240, 205, 170))                                      # faint: pale rays …
        d.ellipse((310, 418, 314, 422), fill=(214, 170, 90))                    # … round a gold core
        d.ellipse((240, 386, 252, 398), fill=(250, 236, 222))                   # a pale highlight, no gold
        star(256, 465, 6, (214, 170, 90))                                       # among the type's box
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[
            {"kind": "motif", "name": "gold sparkle stars", "colour": "#D6AA5A", "count": 3,
             "box": [fx(190), fy(410), fx(320), fy(450)]},
            {"kind": "type", "name": "a type line", "colour": "#8C503C", "box": [fx(200), fy(456), fx(312), fy(476)]}])
        s = dm.trace_shapes(png, rec)
        assert s.get("scatters"), (s["state"], s.get("reason"), s["problems"])
        (scatter,) = s["scatters"]
        assert (scatter["count"], scatter["count_read"]) == (3, 3), scatter
        centres = sorted((round(sum(p[0] for p in st["outline"]) / len(st["outline"]) * (x1 - x0) + x0),
                          round(sum(p[1] for p in st["outline"]) / len(st["outline"]) * (y1 - y0) + y0))
                         for st in scatter["stars"])
        assert [(abs(cx - ex) <= 2 and abs(cy - ey) <= 2) for (cx, cy), (ex, ey) in zip(
            centres, [(200, 420), (256, 440), (312, 420)])] == [True, True, True], centres
        for st in scatter["stars"]:
            assert max(abs(int(st["ink"][i:i + 2], 16) - v) for i, v in zip((1, 3, 5), (214, 170, 90))) <= 14, st
        # [his narrowing: the light ignored] one motif, one gold — every star prints the one ink over all their cores
        assert {st["ink"] for st in scatter["stars"]} == {scatter["ink"]}
        faint = max(scatter["stars"], key=lambda st: sum(p[0] for p in st["outline"]))
        assert (max(p[1] for p in faint["outline"]) - min(p[1] for p in faint["outline"])) * (y1 - y0) >= 10   # rays

    def test_his_look_each_sparkle_is_the_one_sparkle_at_its_own_place_and_size(self):
        """His look at 117 drawn from its map (2026-10-02, transcribed at 99ede0a): "About the sparkles ... I want them
        to match the reference exactly ... these small designs, like those sparkles ... are always inconsistent. And not
        looking good." Three sparkles printed as one shape — four curved arms, pinched 0.7 with fine tips, taller than
        wide, at three sizes — as a picture's pixels print them: each is measured as that one shape, its centre within
        0.75 px and each arm's reach within 1.25 px, the pinch they share within 0.15; and the front draws every one as
        that same clean shape — curved arms, straight only across its four tips, the same outline once its place and
        size are taken out."""
        from PIL import Image, ImageFilter

        from apps.ire import sparkle_glyph
        from apps.ire.graph import CubicTo, LineTo
        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        truth = [(200.0, 420.0, 5.0, 7.0), (256.0, 440.0, 6.0, 8.0), (312.0, 424.0, 4.5, 6.5)]   # 117's in proportion
        fine = 8
        for cx, cy, hw, hh in truth:
            size = 40
            mask = Image.new("L", (size * fine, size * fine), 0)
            from PIL import ImageDraw
            ImageDraw.Draw(mask).polygon([(x * fine, y * fine) for x, y in sparkle_glyph.outline(
                size / 2.0, size / 2.0, hw, hh, 0.7, 0.03, 24)], fill=255)
            mask = mask.resize((size, size), Image.BOX).filter(ImageFilter.GaussianBlur(0.3))
            im.paste(Image.new("RGB", (size, size), (214, 170, 90)), (int(cx - size / 2), int(cy - size / 2)), mask)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "motif", "name": "gold sparkle stars", "colour": "#D6AA5A", "count": 3,
                              "box": [fx(185), fy(405), fx(325), fy(455)]}])
        s = dm.trace_shapes(png, rec)
        (scatter,) = s["scatters"]
        assert scatter["count"] == 3 and abs(scatter["glyph"]["pinch"] - 0.7) <= 0.15, scatter.get("glyph")
        got = sorted((st["centre"][0] * (x1 - x0) + x0, st["centre"][1] * (y1 - y0) + y0,
                      st["half"][0] * (x1 - x0), st["half"][1] * (y1 - y0)) for st in scatter["stars"])
        for (gx, gy, ghw, ghh), (cx, cy, hw, hh) in zip(got, sorted(truth)):
            cx, cy = cx - 0.5, cy - 0.5                          # the tracer counts by pixel centres, the truth by edges
            assert abs(gx - cx) <= 0.75 and abs(gy - cy) <= 0.75, (gx, gy, cx, cy)
            assert abs(ghw - hw) <= 1.25 and abs(ghh - hh) <= 1.25, (ghw, ghh, hw, hh)
        # the front draws each as the same clean shape
        from django.conf import settings

        from apps.ire.compose_container import compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        doc = compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
            map_front={"shapes": s, "edge_part": None})
        import re
        stars = [n for n, _ in doc.walk() if re.fullmatch(r"sparkle-map-\d+-\d+", str(getattr(n, "name", "")))]
        assert len(stars) == 3                     # each sparkle's body (its rim and its lit heart are the same shape)
        shapes = []
        for n in stars:
            assert sum(isinstance(sg, CubicTo) for sg in n.segments) == 4                   # four curved sides …
            assert sum(isinstance(sg, LineTo) for sg in n.segments) <= 4                    # … straight only at tips
            xs = [v for sg in n.segments for v in (getattr(sg, "x", None), getattr(sg, "x1", None),
                                                   getattr(sg, "x2", None)) if v is not None]
            ys = [v for sg in n.segments for v in (getattr(sg, "y", None), getattr(sg, "y1", None),
                                                   getattr(sg, "y2", None)) if v is not None]
            cx, cy, hw, hh = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(xs) - min(xs)) / 2,
                              (max(ys) - min(ys)) / 2)
            shapes.append([round((x - cx) / hw, 6) for x in xs] + [round((y - cy) / hh, 6) for y in ys])
        assert shapes[0] == shapes[1] == shapes[2]                               # one shape, never inconsistent

    def test_his_look_the_script_is_layered_as_the_picture_each_layer_even(self):
        """His look at 117 drawn from its map (2026-10-02, transcribed at 99ede0a): "the edges of the text, it's looking
        not um, constant ... The highlighting is not looking good." A script line lettered in layers — a pink letter, a
        pale inline 1.5 px, a gold ring 3 px (bronze its inner half, lit its outer), a pale outer line 1 px: its
        lettering is rebuilt as those five layers, back to front, each measured within 0.75 px and coloured from its own
        band; and the front draws them, the gold ring under the name's own name so the name checks and the foil read
        it, the pink letter and the pale lines under their own."""
        from PIL import Image, ImageDraw, ImageFilter

        from apps.ire import container_finishes as F
        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        fine = 4
        letters = Image.new("L", (130 * fine, 40 * fine), 0)
        ld = ImageDraw.Draw(letters)
        for x0_, x1_ in ((10, 30), (38, 60), (68, 84), (92, 120)):                     # four letters, joined pairs
            ld.rounded_rectangle((x0_ * fine, 8 * fine, x1_ * fine, 32 * fine), radius=6 * fine, fill=255)
        ld.rectangle((30 * fine, 18 * fine, 38 * fine, 22 * fine), fill=255)
        import numpy as np
        import cv2
        body = (np.asarray(letters) > 0).astype(np.uint8)
        out = cv2.distanceTransform(1 - body, cv2.DIST_L2, 5) / fine
        inn = cv2.distanceTransform(body, cv2.DIST_L2, 5) / fine
        rgb = np.zeros(body.shape + (3,), np.uint8)
        rgb[:] = (247, 190, 200)                                                        # the soft pink ground
        rgb[out <= 4.0] = (252, 236, 222)                                               # the pale outer line
        rgb[out <= 3.0] = (226, 168, 98)                                                # the ring, lit
        rgb[out <= 1.5] = (150, 82, 44)                                                 # the ring, in its bronze
        rgb[body > 0] = (252, 228, 226)                                                 # the pale inline
        rgb[inn > 1.5] = (238, 170, 178)                                                # the letter
        patch = Image.fromarray(rgb).resize((130, 40), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.3))
        im.paste(patch, (190, 430))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]
        line = {"part": "product name script", "box": [(192 - x0) / (x1 - x0), (434 - y0) / (y1 - y0),
                                                       (318 - x0) / (x1 - x0), (466 - y0) / (y1 - y0)],
                "ink": "#965230", "lettering": "script"}
        img, mask, pbox = dm._full_size(png, m)
        got = dm.trace_lettering(img, mask, pbox, line)
        assert [layer["name"] for layer in got["layers"]] == list(dm.LETTERING_LAYERS), got.get("refused")
        widths = got["widths_px"]
        assert abs(widths["ring"] - 3.0) <= 0.75 and abs(widths["ring_split"] - 1.5) <= 0.75, widths
        assert abs(widths["outer"] - 1.0) <= 0.75 and abs(widths["inline"] - 1.5) <= 0.75, widths
        inks = {layer["name"]: layer["ink"] for layer in got["layers"]}

        def near(hx, want, tol=24):
            return max(abs(int(hx[i:i + 2], 16) - v) for i, v in zip((1, 3, 5), want)) <= tol
        assert near(inks["ring"], (226, 168, 98)) and near(inks["ring-shade"], (150, 82, 44)), inks
        assert near(inks["body"], (238, 170, 178)) and near(inks["outer"], (252, 236, 222)), inks
        # the front draws them, back to front, the ring as the name's contour
        from django.conf import settings

        from apps.ire.compose_container import LETTERING_NAMES, compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        name = "Coconut Rose Body Lotion"
        drawn = dict(line, words=name, source="the product's name on the record", match=1.0,
                     outlines={"svg": got["layers"][1]["svg"], "frame": got["frame"]}, lettering_layers=got)
        shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
                  "types": [drawn]}
        doc = compose_container_graph(
            bb, product_name=name, sku="X", zones=zones, native=True, name_lines=[name],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy(name, descriptor="Body Lotion"),
            map_front={"shapes": shapes, "edge_part": None})
        order = [n.name for n, _ in doc.walk() if str(getattr(n, "name", "")) in set(LETTERING_NAMES.values())]
        assert order == [LETTERING_NAMES[k] for k in dm.LETTERING_LAYERS], order
        assert doc.metadata["map_front"]["name_traced"]["words"] == name
        rows = F.apply(doc, F.assignments("gold metallic ink on the script name contour"),
                       brand_metallic_hex="#C9A24B", depict_as_drawn=True)["applied"]
        plated = {nm for r in rows if r.get("plate") for nm in r["nodes"]}
        assert plated == {"product-name-traced", "product-name-traced-shade"}, plated

    def test_his_look_the_gold_edge_is_raised_as_the_picture_lights_it(self):
        """His look at 117 drawn from its map (2026-10-02, transcribed at 99ede0a): "The edges are not um, looking 3D as
        we hoped for." A cream band whose 4 px gold edge is bronze at its sides and lit in its middle, with a pale line
        1 px inside it along the cream: the edge is traced in its relief — bronze, gold body, bright crest, body and
        bronze on its inner side, the pale line, the band's fill, back to front — its crest where the picture lights it
        and each colour from its band; the front draws them under the drip's and the band's names, the gold under the drip's so the foil the
        concept names on the drips reads them; a sparkle and a rule carrying their light are drawn with it."""
        import math

        import cv2
        import numpy as np
        from PIL import Image

        from apps.ire import container_finishes as F
        from apps.pipeline.services import concept_design_map as dm
        im = np.asarray(Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")).copy()
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        fine = 4
        H, W = im.shape[:2]
        band = np.zeros((H * fine, W * fine), np.uint8)
        x_lo, x_hi = int(cx - half(330)) + 6, int(cx + half(330)) - 5
        for x in range(x_lo * fine, x_hi * fine):
            u = (x / fine - (cx - half(330))) / (2 * half(330))
            low = 335 + 30 * (1 - math.cos(2 * math.pi * 3 * u))
            band[(split + 2) * fine:int(low * fine), x] = 1
        out = cv2.distanceTransform(1 - band, cv2.DIST_L2, 5) / fine
        inn = cv2.distanceTransform(band, cv2.DIST_L2, 5) / fine
        rgb = cv2.resize(im, (W * fine, H * fine), interpolation=cv2.INTER_NEAREST)
        rows = np.zeros(band.shape, bool)
        rows[(split + 2) * fine:400 * fine, x_lo * fine - 6 * fine:x_hi * fine + 6 * fine] = True
        rgb[rows & (out <= 4.0)] = (176, 112, 52)                                         # the edge's bronze …
        rgb[rows & (out > 1.0) & (out <= 3.0)] = (246, 206, 128)                          # … its lit middle
        rgb[(band > 0)] = (252, 246, 240)                                                 # the pale line …
        rgb[(inn > 1.0)] = (244, 230, 214)                                                # … and the cream
        im = cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(im).save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "band", "name": "cream drip band", "colour": "#F4E6D6",
                              "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(405)]}])
        s = dm.trace_shapes(png, rec)
        (traced,) = s["bands"]
        relief = traced["relief"]
        assert [layer["name"] for layer in relief["layers"]] == ["edge-shade", "edge-body", "edge-lit", "edge-body-inner",
                                                                  "edge-inner", "inline", "fill"]
        lit_from, lit_to = relief["widths_px"]["lit"]
        assert abs(lit_from - 1.0) <= 0.75 and abs(lit_to - 3.0) <= 0.75, relief["widths_px"]
        assert abs(relief["widths_px"]["inline"] - 1.0) <= 0.75, relief["widths_px"]
        inks = {layer["name"]: layer["ink"] for layer in relief["layers"]}

        def near(hx, want, tol=28):
            return max(abs(int(hx[i:i + 2], 16) - v) for i, v in zip((1, 3, 5), want)) <= tol
        assert near(inks["edge-shade"], (176, 112, 52)) and near(inks["edge-lit"], (246, 206, 128)), inks
        assert inks["edge-inner"] == inks["edge-shade"] and inks["fill"] == "#F4E6D6", inks
        # the front draws the relief, and a sparkle and a rule carrying their light
        from django.conf import settings

        from apps.ire.compose_container import compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        shapes = dict(s, scatters=[{"part": "gold sparkle stars", "ink": "#E3AE6C", "ink_lit": "#F6D392",
                                    "ink_shade": "#B07440", "count": 1,
                                    "glyph": {"kind": "four-point sparkle", "pinch": 0.7, "tip": 0.03},
                                    "stars": [{"centre": [0.5, 0.6], "half": [0.02, 0.012], "ink": "#E3AE6C",
                                               "outline": [[0.48, 0.6], [0.5, 0.588], [0.52, 0.6], [0.5, 0.612]]}]}],
                      rules=[{"part": "gold rule", "box": [0.12, 0.40, 0.88, 0.405], "ink": "#E5B977",
                              "ink_lit": "#F4D79E", "ink_shade": "#C08A4A"}])
        doc = compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
            map_front={"shapes": shapes, "edge_part": None})
        names = [str(getattr(n, "name", "")) for n, _ in doc.walk()]
        assert [n for n in names if n.startswith(("drip-map-", "band-map-")) and not n.endswith("-arches")] == [
            "drip-map-0-shade", "drip-map-0-body", "drip-map-0-lit", "drip-map-0-body-inner", "drip-map-0-inner",
            "band-map-0-inline", "band-map-0"]
        assert [n for n in names if n.startswith("sparkle-map-")] == [
            "sparkle-map-0-0-rim", "sparkle-map-0-0", "sparkle-map-0-0-lit"]
        assert [n for n in names if n.startswith("rule-map-")] == ["rule-map-0", "rule-map-0-lit"]
        rows_ = F.apply(doc, F.assignments("gold metallic ink on the drip outlines and sparkle stars"),
                        brand_metallic_hex="#C9A24B", depict_as_drawn=True)["applied"]
        plated = {nm for r in rows_ if r.get("plate") for nm in r["nodes"]}
        assert plated == {"drip-map-0-shade", "drip-map-0-body", "drip-map-0-lit", "drip-map-0-body-inner",
                          "drip-map-0-inner", "sparkle-map-0-0-rim", "sparkle-map-0-0", "sparkle-map-0-0-lit"}, plated

    def test_his_look_the_arches_between_the_drips_take_the_pictures_own_gradient(self):
        """His look at 117 drawn from its map (2026-10-02), the executor's analysis transcribed with it: the arches
        between the drips print flat pink where the picture shows them peach at their top fading to pink. A band whose
        arches run from peach at the band's top to the soft pink at its drips' foot: their colour is measured down them,
        its first stop the peach and its last the pink, each within 12 of the picture's; the front draws them behind
        the band as that gradient, top to foot, its stops named as the picture's for the printed-colour audit."""
        import math

        import numpy as np
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import map_front_colour_sources
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        d.rectangle((cx - half(split), split - 2, cx + half(split), split + 1), fill=(214, 170, 90))   # the rule
        peach, pink = np.array((246, 214, 186)), np.array((247, 190, 200))
        x_lo, x_hi = int(cx - half(330)) + 6, int(cx + half(330)) - 5
        for y in range(split + 2, 396):                                       # the arches' colour, peach down to pink
            t = (y - (split + 2)) / float(396 - (split + 2))
            c = tuple(int(v) for v in np.round(peach + (pink - peach) * t))
            d.line([(x_lo, y), (x_hi - 1, y)], fill=c)
        edge = []
        for x in range(int(cx - half(330)) + 6, int(cx + half(330)) - 5):
            u = (x - (cx - half(330))) / (2 * half(330))
            low = 335 + 30 * (1 - math.cos(2 * math.pi * 4 * u))
            d.line([(x, split + 2), (x, low)], fill=(250, 240, 228))
            edge.append((x, low))
        d.line(edge, fill=(214, 170, 90), width=3)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "band", "name": "cream drip band", "colour": "#FAF0E4",
                              "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]}])
        s = dm.trace_shapes(png, rec)
        assert s.get("bands"), (s["state"], s.get("reason"), s["problems"])
        (band,) = s["bands"]
        stops = band["arches"]["stops"]

        def near(hx, want, tol=12):
            return max(abs(int(hx[i:i + 2], 16) - int(v)) for i, v in zip((1, 3, 5), want)) <= tol
        top_row = band["arches"]["rows"][0] * (y1 - y0) + y0
        expect_top = peach + (pink - peach) * ((top_row - (split + 2)) / float(396 - (split + 2)))
        assert near(stops[0][1], expect_top) and near(stops[-1][1], pink, 14), (stops, top_row)
        assert [o for o, _hx in stops] == sorted(o for o, _hx in stops) and stops[0][0] == 0.0 and stops[-1][0] == 1.0
        # where the map knows the field the drips hang into, the arches end in its colour, meeting it without a seam
        with_field = dict(rec, parts=rec["parts"] + [{"kind": "field", "name": "soft pink lower field",
                                                      "colour": "#F7BEC8", "box": [0.1, fy(380), 0.9, fy(430)]}])
        assert dm.trace_shapes(png, with_field)["bands"][0]["arches"]["stops"][-1] == [1.0, "#F7BEC8"]
        from django.conf import settings

        from apps.ire.compose_container import compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.ire.graph import GradientFill
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        doc = compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
            map_front={"shapes": s, "edge_part": None})
        names = [str(getattr(n, "name", "")) for n, _ in doc.walk()]
        assert names.index("band-map-0-arches") < min(i for i, n in enumerate(names) if n.startswith(("band-map-0",
                                                                                                   "drip-map-0")) and n != "band-map-0-arches")
        arches = next(n for n, _ in doc.walk() if getattr(n, "name", "") == "band-map-0-arches")
        assert isinstance(arches.fill, GradientFill) and len(arches.fill.stops) == len(stops)
        named = map_front_colour_sources({"shapes": s})
        assert all(hx.upper() in named for _o, hx in stops)

    def test_his_second_look_the_script_letter_has_no_holes_and_keeps_its_eyes(self):
        """His second look at 117 (2026-10-02, transcribed at 96f9c24): "there are some some holes in the in the text ...
        it's not as smooth as the reference". Four lettered letters, one crossed inside by a short broken bronze line
        (a slit, as a broken inner stroke line leaves) and one with an eye (a bronze counter 3 px across each side):
        the letter shape is rebuilt with the slit filled and the eye kept — no hole but the eye — its edge snapped to
        where the picture's lightness passes from the ring to the letter."""
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        fine = 4
        letters = Image.new("L", (130 * fine, 40 * fine), 0)
        ld = ImageDraw.Draw(letters)
        for x0_, x1_ in ((10, 30), (38, 60), (68, 84), (92, 120)):
            ld.rounded_rectangle((x0_ * fine, 8 * fine, x1_ * fine, 32 * fine), radius=6 * fine, fill=255)
        ld.rectangle((30 * fine, 18 * fine, 38 * fine, 22 * fine), fill=255)
        body = (np.asarray(letters) > 0).astype(np.uint8)
        out = cv2.distanceTransform(1 - body, cv2.DIST_L2, 5) / fine
        inn = cv2.distanceTransform(body, cv2.DIST_L2, 5) / fine
        rgb = np.zeros(body.shape + (3,), np.uint8)
        rgb[:] = (247, 190, 200)
        rgb[out <= 4.0] = (252, 236, 222)
        rgb[out <= 3.0] = (226, 168, 98)
        rgb[out <= 1.5] = (150, 82, 44)
        rgb[body > 0] = (252, 228, 226)
        rgb[inn > 1.5] = (238, 170, 178)
        rgb[18 * fine:19 * fine, 42 * fine:52 * fine] = (150, 82, 44)                    # a slit in the second letter
        yy, xx = np.mgrid[0:body.shape[0], 0:body.shape[1]]
        rgb[(yy - 20 * fine) ** 2 + (xx - 106 * fine) ** 2 <= (3 * fine) ** 2] = (150, 82, 44)   # an eye in the fourth
        patch = Image.fromarray(rgb).resize((130, 40), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.3))
        im.paste(patch, (190, 430))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]
        line = {"part": "product name script", "box": [(192 - x0) / (x1 - x0), (434 - y0) / (y1 - y0),
                                                       (318 - x0) / (x1 - x0), (466 - y0) / (y1 - y0)],
                "ink": "#965230", "lettering": "script"}
        img, mask, pbox = dm._full_size(png, m)
        got = dm.trace_lettering(img, mask, pbox, line)
        assert "refused" not in got and got["slits_filled"] >= 1, {k: v for k, v in got.items() if k != "layers"}
        assert got["eyes"] == 1, {k: v for k, v in got.items() if k != "layers"}
        assert [layer["name"] for layer in got["layers"]] == list(dm.LETTERING_LAYERS)
        assert 60.0 < got["edge_l"] < 90.0, got["edge_l"]

    def test_his_second_look_the_drips_edge_is_the_pictures_own_never_a_spur(self):
        """His second look at 117 (2026-10-02, transcribed at 96f9c24): the drips "still zigzaggy a bit it can be way
        better". A cream band whose raised gold edge breaks for 2 px where its shine is — the cream reaching into the gap
        — and wobbles a pixel along its drips: every layer of its relief keeps to the band's own edge, never more than
        1.5 px out of it, with no spur into the gap; and no layer turns back on itself more than 1.5 times per 100 px."""
        import math
        import random

        import cv2
        import numpy as np
        from PIL import Image

        from apps.pipeline.services import concept_design_map as dm
        im = np.asarray(Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")).copy()
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        fine = 4
        H, W = im.shape[:2]
        band = np.zeros((H * fine, W * fine), np.uint8)
        x_lo, x_hi = int(cx - half(330)) + 6, int(cx + half(330)) - 5
        wobble = random.Random(2)
        for x in range(x_lo * fine, x_hi * fine):
            u = (x / fine - (cx - half(330))) / (2 * half(330))
            low = 335 + 30 * (1 - math.cos(2 * math.pi * 4 * u)) + (wobble.choice((-1.0, 0.0, 1.0)) if x % fine == 0
                                                                     else 0.0)
            band[(split + 2) * fine:int(low * fine), x] = 1
        out = cv2.distanceTransform(1 - band, cv2.DIST_L2, 5) / fine
        rgb = cv2.resize(im, (W * fine, H * fine), interpolation=cv2.INTER_NEAREST)
        rows = np.zeros(band.shape, bool)
        rows[(split + 2) * fine:400 * fine, x_lo * fine - 6 * fine:x_hi * fine + 6 * fine] = True
        rgb[rows & (out <= 4.0)] = (176, 112, 52)
        rgb[rows & (out > 1.0) & (out <= 3.0)] = (246, 206, 128)
        rgb[band > 0] = (244, 230, 214)
        # [his rules of 2026-10-02, rule 3, at K5] the gold rule its record declares, drawn: without it the band read up
        # to the picture's own two-tone line, where the tube's colour spans it wall to wall — an edge-to-edge band, which
        # rule 3 now runs into the bleed — and this test is of a band that hangs from a rule, inside the tube's edges
        rgb[(split - 2) * fine:(split + 2) * fine, int(cx - half(split)) * fine:int(cx + half(split)) * fine] = (214, 170, 90)
        gx = int((cx - half(360) + 30) * fine)                                     # a 2 px gap in the gold, its shine
        rgb[355 * fine:357 * fine, gx - 6 * fine:gx + 6 * fine] = (244, 230, 214)
        im = cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(im).save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "rule", "name": "gold rule", "colour": "#D6AA5A",
                              "box": [fx(cx - half(split)), fy(split - 2), fx(cx + half(split)), fy(split + 2)]},
                             {"kind": "band", "name": "cream drip band", "colour": "#F4E6D6",
                              "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]}])
        s_ = dm.trace_shapes(png, rec)
        assert s_.get("bands"), s_["problems"]
        relief = s_["bands"][0]["relief"]
        beyond = cv2.distanceTransform((1 - band).astype(np.uint8), cv2.DIST_L2, 5) / fine     # px out of the band

        def backs(pts):
            turns, length = [], 0.0
            for (ax, ay), (bx, by), (qx, qy) in zip(pts, pts[1:], pts[2:]):
                t = math.atan2(qy - by, qx - bx) - math.atan2(by - ay, bx - ax)
                t = (t + math.pi) % (2 * math.pi) - math.pi
                if abs(t) > math.radians(2):
                    turns.append(t > 0)
                length += math.hypot(bx - ax, by - ay)
            return 100.0 * sum(a != b for a, b in zip(turns, turns[1:])) / length
        for layer in relief["layers"]:
            pts = [(x * (x1 - x0) + x0, y * (y1 - y0) + y0) for x, y in layer["outline"]]
            inside_rows = [(px, py) for px, py in pts if split + 6 < py < 398]
            if layer["name"] in ("fill", "inline"):
                worst = max(beyond[min(int(py * fine), beyond.shape[0] - 1), min(int(px * fine), beyond.shape[1] - 1)]
                            for px, py in inside_rows)
                assert worst <= 1.5, (layer["name"], worst)                   # never a spur into the gold
            assert backs(pts) <= 1.5, (layer["name"], backs(pts))

    def test_his_rules_the_drips_are_redrawn_as_clean_curves_their_gold_even_and_open_at_the_rule(self):
        """His rules for cloning a design from a picture (2026-10-02, transcribed at 6badb27), rule 2: "SHAPES ARE
        REDRAWN AS CLEAN CURVES: refit drips, waves, arches and ribbons with the fewest points; even widths, round ends,
        no wobble." A cream band hanging from a gold rule, four drips, its raised gold edge wobbling a pixel: every layer
        of its relief is drawn as cubics — far fewer than the 4 px steps along it — none bending where the band does
        not (at most two bends a drip, and the band's two corners); the gold ring as wide all round as it was measured;
        none of its gold above the band's top, where the rule lies; the front draws each layer as those cubics."""
        import math
        import random

        import cv2
        import numpy as np
        from PIL import Image
        from shapely.geometry import Polygon

        from apps.pipeline.services import concept_design_map as dm
        im = np.asarray(Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")).copy()
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        fine = 4
        H, W = im.shape[:2]
        band = np.zeros((H * fine, W * fine), np.uint8)
        x_lo, x_hi = int(cx - half(330)) + 6, int(cx + half(330)) - 5
        wobble = random.Random(2)
        for x in range(x_lo * fine, x_hi * fine):
            u = (x / fine - (cx - half(330))) / (2 * half(330))
            low = 335 + 30 * (1 - math.cos(2 * math.pi * 4 * u)) + (wobble.choice((-1.0, 0.0, 1.0)) if x % fine == 0
                                                                     else 0.0)
            band[(split + 2) * fine:int(low * fine), x] = 1
        out = cv2.distanceTransform(1 - band, cv2.DIST_L2, 5) / fine
        rgb = cv2.resize(im, (W * fine, H * fine), interpolation=cv2.INTER_NEAREST)
        rows = np.zeros(band.shape, bool)
        rows[(split + 2) * fine:400 * fine, x_lo * fine - 6 * fine:x_hi * fine + 6 * fine] = True
        rgb[rows & (out <= 4.0)] = (176, 112, 52)
        rgb[rows & (out > 1.0) & (out <= 3.0)] = (246, 206, 128)
        rgb[band > 0] = (244, 230, 214)
        # the gold rule its record declares, drawn (at K5: the band hangs from it, inside the tube's edges)
        rgb[(split - 2) * fine:(split + 2) * fine, int(cx - half(split)) * fine:int(cx + half(split)) * fine] = (214, 170, 90)
        im = cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(im).save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "rule", "name": "gold rule", "colour": "#D6AA5A",
                              "box": [fx(cx - half(split)), fy(split - 2), fx(cx + half(split)), fy(split + 2)]},
                             {"kind": "band", "name": "cream drip band", "colour": "#F4E6D6",
                              "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]}])
        s_ = dm.trace_shapes(png, rec)
        relief = s_["bands"][0]["relief"]
        layers = {layer["name"]: layer for layer in relief["layers"]}
        assert {"edge-shade", "edge-body", "edge-lit", "fill"} <= set(layers), list(layers)

        def px(p):
            return p[0] * (x1 - x0) + x0, p[1] * (y1 - y0) + y0

        def curves(layer):
            for poly in layer["cubics"]:
                for ring in poly:
                    a = px(ring[0])
                    for c in ring[1:]:
                        yield np.array([a, px(c[0:2]), px(c[2:4]), px(c[4:6])])
                        a = px(c[4:6])

        def points(layer, n=12):
            u = np.linspace(0.0, 1.0, n)[:, None]
            return np.vstack([(1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u * u * c[2]
                              + u ** 3 * c[3] for c in curves(layer)])

        def bends(layer, below):
            # where the curve's bending changes side, read along every cubic in turn (a radius under 100 px each way):
            # a drip bends one way at its tip and the other at the arch beside it — two such turns a drip
            u = np.linspace(0.02, 0.98, 49)[:, None]
            signs = []
            for c in curves(layer):
                q = (1 - u) ** 3 * c[0] + 3 * (1 - u) ** 2 * u * c[1] + 3 * (1 - u) * u * u * c[2] + u ** 3 * c[3]
                d1 = 3 * (1 - u) ** 2 * (c[1] - c[0]) + 6 * (1 - u) * u * (c[2] - c[1]) + 3 * u * u * (c[3] - c[2])
                d2 = 6 * (1 - u) * (c[2] - 2 * c[1] + c[0]) + 6 * u * (c[3] - 2 * c[2] + c[1])
                cr = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / (np.hypot(*d1.T) ** 3 + 1e-9)
                signs.extend(np.sign(cr[(np.abs(cr) > 0.01) & (q[:, 1] > below)]))
            return int((np.array(signs[1:]) != np.array(signs[:-1])).sum())
        fill = layers["fill"]
        steps = len(fill["outline"])                                     # the 4 px steps along it
        assert len(list(curves(fill))) <= steps / 2, (len(list(curves(fill))), steps)        # the fewest points
        # no wobble along the drips and the arches (below the band's top, whose corners meet the product's sides)
        assert bends(fill, split + 12) <= 2 * 4 + 2, bends(fill, split + 12)
        # even widths: the gold ring as wide all round as it was measured
        widths = relief["widths_px"]
        from shapely.geometry import Point
        fill_poly = Polygon(points(layers["fill"], 24))
        far = [fill_poly.exterior.distance(Point(p)) for p in points(layers["edge-shade"], 24)
               if p[1] > split + 12 and not fill_poly.contains(Point(p))]
        far = [d for d in far if d > 1.0]                                 # the ring's outer edge, not its inner one
        want = widths["edge"] + (widths.get("inline") or 0.0)
        assert far and abs(float(np.median(far)) - want) <= 0.6 and float(np.percentile(far, 90)) - float(
            np.percentile(far, 10)) <= 1.0, (np.percentile(far, [10, 50, 90]), want)
        # none of the gold above the band's top, where the rule lies — and none along it: no gold within a gold width
        # under the band's top line except down its two sides
        band_top = float(np.median([p[1] for p in points(layers["fill"]) if p[1] < split + 6]))
        gold = points(layers["edge-shade"])
        assert min(p[1] for p in gold) >= band_top - 0.75, (min(p[1] for p in gold), band_top)
        sides = (min(p[0] for p in points(layers["fill"])) + 8, max(p[0] for p in points(layers["fill"])) - 8)
        assert not [p for p in gold if p[1] < band_top + widths["edge"] and sides[0] < p[0] < sides[1]]
        # the front draws each layer as its cubics
        from django.conf import settings

        from apps.ire.compose_container import compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.ire.graph import CubicTo
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        doc = compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
            map_front={"shapes": s_, "edge_part": None})
        nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
        shade = nodes["drip-map-0-shade"]
        assert shade.fill_rule == "evenodd"
        assert sum(isinstance(sg, CubicTo) for sg in shade.segments) == len(list(curves(layers["edge-shade"])))

    def test_his_rules_a_band_the_picture_runs_edge_to_edge_runs_into_the_bleed_never_a_gap(self):
        """His rules for cloning a design from a picture (2026-10-02, transcribed at 6badb27), rule 3: "EDGE TO EDGE MEANS
        BLEED. Anything touching the edge in the picture runs past the outline into the bleed; never a gap (117's left
        gap)." A cream band that hangs from a gold rule wall to wall across the tube: both are traced as reaching both
        sides; the front draws them cut by the tube's drawn outline only — not by his front, which lies inside it — each
        run past the outline by more than the house's 3 mm bleed, as the record says; inside the outline, at the band's
        rows, the band reaches the outline itself; and nothing of either is recorded cut from his front."""
        import math

        import cv2
        import numpy as np
        from PIL import Image
        from shapely.geometry import Point, Polygon

        from apps.pipeline.services import concept_design_map as dm
        im = np.asarray(Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")).copy()
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        fine = 4
        H, W = im.shape[:2]
        mask = np.zeros((H * fine, W * fine), np.uint8)
        for yy in range((split + 2) * fine, 400 * fine):
            y = yy / fine
            a, b = cx - half(y), cx + half(y)
            for xx in range(int(a * fine), int(b * fine)):
                u = (xx / fine - a) / (b - a)
                if y < 335 + 30 * (1 - math.cos(2 * math.pi * 4 * u)):
                    mask[yy, xx] = 1
        out = cv2.distanceTransform(1 - mask, cv2.DIST_L2, 5) / fine
        rgb = cv2.resize(im, (W * fine, H * fine), interpolation=cv2.INTER_NEAREST)
        inside_tube = np.zeros(mask.shape, bool)
        for yy in range((split + 2) * fine, 400 * fine):
            y = yy / fine
            inside_tube[yy, int((cx - half(y)) * fine):int((cx + half(y)) * fine)] = True
        rgb[inside_tube & (out <= 4.0)] = (176, 112, 52)
        rgb[inside_tube & (out > 1.0) & (out <= 3.0)] = (246, 206, 128)
        rgb[mask > 0] = (244, 230, 214)
        rgb[(split - 2) * fine:(split + 2) * fine, int((cx - half(split)) * fine):int((cx + half(split)) * fine)] = (
            214, 170, 90)
        im = cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(im).save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "rule", "name": "gold rule", "colour": "#D6AA5A",
                              "box": [fx(cx - half(split)), fy(split - 2), fx(cx + half(split)), fy(split + 2)]},
                             {"kind": "band", "name": "cream drip band", "colour": "#F4E6D6",
                              "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]}])
        s_ = dm.trace_shapes(png, rec)
        band, rule = s_["bands"][0], s_["rules"][0]
        assert set(band["edges"]) == {"left", "right"} and rule["edges"] == ["left", "right"], (band.get("edges"), rule)
        assert rule["drawn_box"][0] < rule["box"][0] - 0.05 and rule["drawn_box"][2] > rule["box"][2] + 0.05
        # the front: his front inside the tube's outline, as 117's lies 1.2 mm inside it
        from django.conf import settings

        from apps.ire.compose_container import MAP_EDGE_TO_EDGE, MAP_WITHIN_HIS_FRONT, compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 12.0,
                  "y": 39.1, "width": 58.0, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        doc = compose_container_graph(
            bb, product_name="Coconut Rose Body Lotion", sku="X", zones=zones, native=True,
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Coconut Rose Body Lotion", descriptor="Body Lotion"),
            map_front={"shapes": s_, "edge_part": None})
        groups = {getattr(n, "name", None): n for n, _ in doc.walk() if getattr(n, "type", "") == "group"}
        edge, zoned = groups[MAP_EDGE_TO_EDGE], groups[MAP_WITHIN_HIS_FRONT]
        assert {"band-map-0", "rule-map-0"} <= {c.name for c in edge.children}
        rec_ = doc.metadata["map_front"]
        by = {p["part"]: p for p in rec_["edge_to_edge"]}
        assert by["cream drip band"]["into_the_bleed"] and by["gold rule"]["into_the_bleed"], by
        assert all(p["past_the_outline_mm"] >= 3.0 for p in by.values()), by
        assert not {"cream drip band", "gold rule"} & set(rec_["clipped_to_his_front_mm"]), rec_["clipped_to_his_front_mm"]

        def shape(segs):
            pts, last = [], None
            for sg in segs:
                if sg.op in ("M", "L"):
                    last = (sg.x, sg.y)
                    pts.append(last)
                elif sg.op == "C":
                    for k in range(1, 9):
                        u, v = k / 8.0, 1.0 - k / 8.0
                        pts.append((v ** 3 * last[0] + 3 * v * v * u * sg.x1 + 3 * v * u * u * sg.x2 + u ** 3 * sg.x,
                                    v ** 3 * last[1] + 3 * v * v * u * sg.y1 + 3 * v * u * u * sg.y2 + u ** 3 * sg.y))
                    last = (sg.x, sg.y)
            return Polygon(pts).buffer(0)
        fill = shape(next(c for c in edge.children if c.name == "band-map-0").segments)
        tube = shape(edge.clip)
        row = fill.bounds[1] + 3.0                                     # a row of the band's top, inside the tube
        from shapely.geometry import LineString
        across = tube.intersection(LineString([(tube.bounds[0] - 10, row), (tube.bounds[2] + 10, row)])).bounds
        for x in (across[0] + 0.3, across[2] - 0.3):                    # just inside the outline, both sides
            assert fill.contains(Point(x, row)), (x, row, fill.bounds)       # never a gap
        assert zoned.clip is not None                                  # his front still bounds the rest

    def test_his_word_a_drip_the_edge_cuts_is_kept_whole_in_the_bleed_never_cut_flat(self):
        """His word of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "where the picture shows a shape
        whole (117's edge drips with round tips), keep it whole inside the bleed; don't cut it flat." A cream band hangs
        wall to wall across the tube with its drips spaced so the tube's two sides cut a drip down its middle: past each
        side the band as drawn runs on as that drip — at its middle depth as far past the side as the picture shows of
        it inside, never the whole bleed's ledge — and down to its tip, not cut off where the band's solid top ends."""
        import math

        import cv2
        import numpy as np
        from PIL import Image

        from apps.pipeline.services import concept_design_map as dm
        im = np.asarray(Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")).copy()
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        fine = 4
        H, W = im.shape[:2]
        mask = np.zeros((H * fine, W * fine), np.uint8)
        for yy in range((split + 2) * fine, 400 * fine):
            y = yy / fine
            a, b = cx - half(y), cx + half(y)
            for xx in range(int(a * fine), int(b * fine)):
                u = (xx / fine - a) / (b - a)
                # four drips across, the tube's sides cutting the first and the last down their middles
                if y < 335 + 30 * (1 - math.cos(2 * math.pi * 4 * u + math.pi)):
                    mask[yy, xx] = 1
        out = cv2.distanceTransform(1 - mask, cv2.DIST_L2, 5) / fine
        rgb = cv2.resize(im, (W * fine, H * fine), interpolation=cv2.INTER_NEAREST)
        inside_tube = np.zeros(mask.shape, bool)
        for yy in range((split + 2) * fine, 400 * fine):
            y = yy / fine
            inside_tube[yy, int((cx - half(y)) * fine):int((cx + half(y)) * fine)] = True
        rgb[inside_tube & (out <= 4.0)] = (176, 112, 52)
        rgb[inside_tube & (out > 1.0) & (out <= 3.0)] = (246, 206, 128)
        rgb[mask > 0] = (244, 230, 214)
        rgb[(split - 2) * fine:(split + 2) * fine, int((cx - half(split)) * fine):int((cx + half(split)) * fine)] = (
            214, 170, 90)
        im = cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(im).save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "rule", "name": "gold rule", "colour": "#D6AA5A",
                              "box": [fx(cx - half(split)), fy(split - 2), fx(cx + half(split)), fy(split + 2)]},
                             {"kind": "band", "name": "cream drip band", "colour": "#F4E6D6",
                              "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]}])
        band = dm.trace_shapes(png, rec)["bands"][0]
        assert set(band["edges"]) == {"left", "right"}, band.get("edges")
        whole = {d["side"]: d for d in band.get("edge_drips_whole") or []}
        assert set(whole) == {"left", "right"}, band.get("edge_drips_whole")
        # past each side the band as drawn (its relief's fill): at the drip's middle depth about its own half-width out,
        # far short of the bleed's whole reach; and down to its tip
        fill = next(layer for layer in band["relief"]["layers"] if layer["name"] == "fill")
        pts = [(float(x), float(y)) for x, y in fill["outline"]]

        def side(y_frac, sign):
            return fx(cx + sign * half(y0 + y_frac * (y1 - y0)))
        mid = [x for x, y in pts if abs(y - fy(365)) < 0.004]
        past_left, past_right = side(fy(365), -1) - min(mid), max(mid) - side(fy(365), 1)
        assert 0.02 < past_left < 0.06 and 0.02 < past_right < 0.06, (past_left, past_right)
        assert band["bleed_reach"] > 0.09                                   # the ledge it was: the whole reach out
        deepest = [max(y for x, y in pts if sign * (x - side(y, sign)) > 0.002 and y > fy(340)) for sign in (-1, 1)]
        assert min(deepest) > fy(380), (deepest, fy(380))

    def test_his_answer_the_score_measures_the_drawing_against_the_concepts_full_size_trace(self):
        """His answer 3 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "The score's yardstick is a
        full-size trace of the concept, so it can say 'matches' without my eye." A tube whose picture hangs a cream band
        under a gold rule, drawn from its map: scored against the picture's full-size trace, the band and the rule each
        MATCH — drawn in their traced inks, where the trace puts them — and the drawing matches its concept; a part
        recorded 3 mm from where the trace puts it does not, nor does one drawn in another colour, and the board says
        which in words."""

        import numpy as np
        from django.conf import settings
        from PIL import Image

        from apps.ire.compose_container import compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container import _score_rows
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        import math

        import cv2
        im = np.asarray(Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")).copy()
        cx, top, body_foot = 256, 90, 610

        def half(y):
            return (280 + (190 - 280) * (y - top) / (body_foot - top)) / 2
        split = top + int(0.40 * (body_foot - top))
        fine = 4
        H, W = im.shape[:2]
        mask = np.zeros((H * fine, W * fine), np.uint8)
        for yy in range((split + 2) * fine, 400 * fine):
            y = yy / fine
            a_, b_ = cx - half(y), cx + half(y)
            for xx in range(int(a_ * fine), int(b_ * fine)):
                if y < 335 + 30 * (1 - math.cos(2 * math.pi * 4 * (xx / fine - a_) / (b_ - a_))):
                    mask[yy, xx] = 1
        out = cv2.distanceTransform(1 - mask, cv2.DIST_L2, 5) / fine
        rgb = cv2.resize(im, (W * fine, H * fine), interpolation=cv2.INTER_NEAREST)
        inside_tube = np.zeros(mask.shape, bool)
        for yy in range((split + 2) * fine, 400 * fine):
            y = yy / fine
            inside_tube[yy, int((cx - half(y)) * fine):int((cx + half(y)) * fine)] = True
        rgb[inside_tube & (out <= 4.0)] = (176, 112, 52)
        rgb[inside_tube & (out > 1.0) & (out <= 3.0)] = (246, 206, 128)
        rgb[mask > 0] = (244, 230, 214)
        rgb[(split - 2) * fine:(split + 2) * fine, int((cx - half(split)) * fine):int((cx + half(split)) * fine)] = (
            214, 170, 90)
        im = cv2.resize(rgb, (W, H), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(im).save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]

        def fx(x):
            return (x - x0) / (x1 - x0)

        def fy(y):
            return (y - y0) / (y1 - y0)
        rec = dict(m, parts=[{"kind": "rule", "name": "gold rule", "colour": "#D6AA5A",
                              "box": [fx(cx - half(split)), fy(split - 2), fx(cx + half(split)), fy(split + 2)]},
                             {"kind": "band", "name": "cream band", "colour": "#F4E6D6",
                              "box": [fx(cx - half(split)), fy(split + 2), fx(cx + half(split)), fy(398)]}])
        shapes = dm.trace_shapes(png, rec)
        assert {b["part"] for b in shapes.get("bands") or []} == {"cream band"}, shapes.get("problems")
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 0.0,
                  "y": 0.0, "width": 78.5, "height": 180.0, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        doc = compose_container_graph(
            bb, product_name="Rose Glow", sku="X", zones=zones, native=True, name_lines=["Rose Glow"],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#E91E78", "cap": "#D71969", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Rose Glow", descriptor="Body Lotion"),
            map_front={"shapes": shapes, "edge_part": None})
        drawn = dm.product_png(doc)
        boxes = doc.metadata["map_front"]["boxes"]
        score = dm.score_traced(shapes, png, rec, drawn, drawn_boxes=boxes, size_mm=(bb.width_mm, bb.height_mm))
        assert score["schema_version"] == dm.SCORE_TRACED_SCHEMA and score["yardstick"] == dm.SCORE_YARDSTICK
        by = {r["part"]: r for r in score["parts"]}
        assert by["cream band"]["matches"] and by["gold rule"]["matches"], score["parts"]
        assert score["matches"] and score["passed"] == score["of"] == 2
        assert _score_rows({dm.SCORE_TRACED_SCHEMA: score})[0]["value"].startswith("MATCHES — all 2 parts")
        moved = dict(boxes, **{"gold rule": [v + (3.0 / 180.0 if i % 2 else 0.0) for i, v in enumerate(boxes["gold rule"])]})
        off = dm.score_traced(shapes, png, rec, drawn, drawn_boxes=moved, size_mm=(bb.width_mm, bb.height_mm))
        row = {r["part"]: r for r in off["parts"]}["gold rule"]
        assert not row["matches"] and row["offset_mm"] >= 3.0 and not off["matches"], row
        assert "gold rule (3.0 mm off)" in _score_rows({dm.SCORE_TRACED_SCHEMA: off})[0]["value"]
        recoloured = dict(shapes, bands=[dict(shapes["bands"][0], fill="#B3E5FC")])
        blue = dm.score_traced(recoloured, png, rec, drawn, drawn_boxes=boxes, size_mm=(bb.width_mm, bb.height_mm))
        assert {r["part"]: r for r in blue["parts"]}["cream band"]["delta_e"] > 3.0

    def test_his_rules_lettering_is_set_in_the_closest_face_not_traced_and_traced_only_saying_why(self):
        """His rules for cloning a design from a picture (2026-10-02, transcribed at 6badb27), rule 1: "LETTERING IS SET,
        NOT TRACED: closest real script font (granted, or a licensed one proposed), exact words, then the picture's
        outline, fill, colours, size and placement; trace only when no font comes close, and say so." A script line
        lettered "Rose Glow" in a face the house holds (Grand Hotel), layered as the picture layers its script: it is SET
        in that face — the closest of every face measured, sharing at least the bar with the picture's letters — each
        layer an even offset of the set letters, in the picture's colours; the front draws those layers as cubics where
        the record's words are the ones set. Letters no face the house holds comes close to (four rounded blocks) are
        traced, and the record says which face came closest, how close, and the bar."""
        import cv2
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter, ImageFont

        from apps.pipeline.services import concept_design_map as dm

        def lettered(mask_img):
            im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
            body = (np.asarray(mask_img) > 127).astype(np.uint8)
            out = cv2.distanceTransform(1 - body, cv2.DIST_L2, 5) / fine
            inn = cv2.distanceTransform(body, cv2.DIST_L2, 5) / fine
            rgb = np.zeros(body.shape + (3,), np.uint8)
            rgb[:] = (247, 190, 200)
            rgb[out <= 4.0] = (252, 236, 222)
            rgb[out <= 3.0] = (226, 168, 98)
            rgb[out <= 1.5] = (150, 82, 44)
            rgb[body > 0] = (252, 228, 226)
            rgb[inn > 1.5] = (238, 170, 178)
            patch = Image.fromarray(rgb).resize((200, 70), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.3))
            im.paste(patch, (156, 420))
            buf = io.BytesIO()
            im.save(buf, "PNG")
            png = buf.getvalue()
            m = dm.read_map(png)
            x0, y0, x1, y1 = m["product_box_px"]
            line = {"part": "product name script", "box": [(158 - x0) / (x1 - x0), (423 - y0) / (y1 - y0),
                                                           (354 - x0) / (x1 - x0), (487 - y0) / (y1 - y0)],
                    "ink": "#965230", "lettering": "script", "seen": "Rose Glow"}
            img, mask, pbox = dm._full_size(png, m)
            return line, dm.trace_lettering(img, mask, pbox, line)
        fine = 4
        face = ImageFont.truetype("static/fonts/brand2026/Grand_Hotel/GrandHotel-Regular.ttf", 44 * fine)
        letters = Image.new("L", (200 * fine, 70 * fine), 0)
        ImageDraw.Draw(letters).text((100 * fine, 35 * fine), "Rose Glow", font=face, fill=255, anchor="mm")
        letters = letters.filter(ImageFilter.MaxFilter(13))             # a bolder retro script: the face grown 1.5 px
        line, got = lettered(letters)
        setting = got["set"]
        assert setting["state"] == dm.LETTERING_SET, setting.get("why")
        assert setting["face"] == "GrandHotel-Regular" and setting["outline"] >= setting["bar"] == 0.40, setting
        # [his answer 1 of 2026-10-02: "set 117's name in the closest one"] the face itself, far closer than any other
        assert all(row[2] < setting["outline"] - 0.3 for row in setting["faces_measured"][1:]), setting["faces_measured"]
        assert setting["faces_measured"][0][0] == "GrandHotel-Regular" and len(setting["faces_measured"]) >= 3
        traced = {layer["name"]: layer["ink"] for layer in got["layers"]}
        # the layers the picture letters in, in their order — each an even offset of the set letters
        assert [layer["name"] for layer in setting["layers"]] == [n for n in dm.LETTERING_LAYERS if n in traced]
        assert {"outer", "ring", "inline", "body"} <= set(traced), traced
        assert {layer["name"]: layer["ink"] for layer in setting["layers"]} == traced      # the picture's own colours
        # the front draws the set letters where the record's words are the ones set
        from django.conf import settings

        from apps.ire.compose_container import LETTERING_NAMES, compose_container_graph
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.ire.graph import CubicTo
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))
        drawn = dict(line, words="Rose Glow", source="the product's name on the record", match=1.0,
                     outlines={"svg": got["layers"][1]["svg"], "frame": got["frame"]}, lettering_layers=got)
        doc = compose_container_graph(
            bb, product_name="Rose Glow", sku="X", zones=zones, native=True, name_lines=["Rose Glow"],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy("Rose Glow", descriptor="Body Lotion"),
            map_front={"shapes": {"state": "TRACED", "source_sha256": "ab" * 32,
                                  "params": {"version": "concept_design_shapes_params/1.12"}, "types": [drawn]},
                       "edge_part": None})
        nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}
        ring = nodes[LETTERING_NAMES["ring"]]
        assert ring.fill_rule == "evenodd" and any(isinstance(sg, CubicTo) for sg in ring.segments)
        typed = doc.metadata["map_front"]["typed"]
        assert typed[0]["lettering"]["state"] == dm.LETTERING_SET and typed[0]["lettering"]["face"] == "GrandHotel-Regular"
        # letters no face the house holds comes close to — [his rule 3, 2026-10-05: "Try setting the name in the granted
        # display faces ... before tracing it."] — are set in the closest of his four display faces, and the record says
        # so: no face is the picture's own, the closest and how close, the bar, the face it was set in (they were traced)
        blocks = Image.new("L", (200 * fine, 70 * fine), 0)
        bd = ImageDraw.Draw(blocks)
        for x0_, x1_ in ((20, 52), (62, 94), (106, 138), (150, 182)):
            bd.rounded_rectangle((x0_ * fine, 14 * fine, x1_ * fine, 56 * fine), radius=8 * fine, fill=255)
        _line, got = lettered(blocks)
        setting = got["set"]
        assert setting["state"] == dm.LETTERING_SET and setting["face"] in dm.DISPLAY_FACES_FIRST, setting
        assert setting["faces_measured"][0][2] < setting["bar"], setting["faces_measured"][:2]
        assert "his rule 3" in setting["set_by"] and "%.2f" % setting["bar"] in setting["set_by"], setting["set_by"]

    def test_his_rules_the_foil_plate_is_the_gold_outline_never_the_band_or_the_letters_solid(self):
        """His rules for cloning a design from a picture (2026-10-02, transcribed at 6badb27), rule 4: "THE FOIL PLATE
        FOLLOWS THE DRAWING. 117's foil plate (page 2 of the .ai) fills the whole drip band and every letter solid; only
        the gold OUTLINES are foil." A band whose relief rings it in gold over a pale line and its fill, and a script
        letter whose gold ring, lit and in its shade, lies between a pale outer line and a pale inline over its body:
        on the plate the gold rings are black and the band's fill and the letter's body are not; page 1 still shows
        the fill and the body in their own colours."""
        import math
        import tempfile

        import fitz
        from django.conf import settings

        from apps.ire import container_finishes as F
        from apps.ire.compose_container import compose_container_graph
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        from apps.ire.front_hierarchy import ruled_front_hierarchy
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE", "parent_surface": "BODY_FRONT", "x": 9.1,
                  "y": 39.1, "width": 64.7, "height": 110.7, "safe_margin_mm": 3.0, "curvature_type": "CYLINDRICAL"}]
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0))

        def ellipse(grow):
            return [[round(0.5 + (0.2 + grow) * math.cos(2 * math.pi * k / 48), 5),
                     round(0.42 + (0.04 + grow) * math.sin(2 * math.pi * k / 48), 5)] for k in range(48)]
        relief = [{"name": name, "outline": ellipse(grow), "ink": ink} for name, grow, ink in (
            ("edge-shade", 0.012, "#B07034"), ("edge-body", 0.010, "#E2B060"), ("edge-lit", 0.008, "#F6CE80"),
            ("edge-body-inner", 0.006, "#E2B060"), ("edge-inner", 0.004, "#B07034"), ("inline", 0.002, "#FBF1E4"),
            ("fill", 0.0, "#F4E6D6"))]
        band = {"part": "cream drip band", "fill": "#F4E6D6", "edge_ink": "#E2B060", "edge_width": 0.008,
                "edge": [ellipse(0.006)[:25]], "outline": ellipse(0.012), "drips": 0,
                "relief": {"layers": relief, "widths_px": {"edge": 4.0}}}

        def square(inset):
            a, b = 100 + inset, 900 - inset
            return ('<svg xmlns="http://www.w3.org/2000/svg" version="1.0" width="100pt" height="40pt" viewBox="0 0 '
                    '100 40"><g transform="translate(0.000000,40.000000) scale(0.100000,-0.100000)" fill="#000000" '
                    'stroke="none"><path d="M%d %d L%d %d L%d %d L%d %d z"/></g></svg>'
                    % (a, inset * 0.3 + 50, b, inset * 0.3 + 50, b, 350 - inset * 0.3, a, 350 - inset * 0.3))
        letters = {"layers": [{"name": name, "svg": square(inset), "ink": ink} for name, inset, ink in (
            ("outer", 0, "#FCECDE"), ("ring", 30, "#E2A862"), ("ring-shade", 60, "#96522C"), ("inline", 90, "#FFF4EA"),
            ("body", 120, "#EEAAB2"))], "frame": [0.19, 0.553, 0.615 / 100.0, 0.126 / 40.0]}
        name = "Coconut Rose Body Lotion"
        shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
                  "bands": [band],
                  "types": [{"part": "product name script", "box": [0.19, 0.553, 0.805, 0.679], "ink": "#B97447",
                             "words": name, "source": "the product's name on the record", "match": 1.0,
                             "lettering": "script", "outlines": {"svg": square(30), "frame": letters["frame"]},
                             "lettering_layers": letters}]}
        doc = compose_container_graph(
            bb, product_name=name, sku="X", zones=zones, native=True, name_lines=[name],
            logo_path=settings.BRAND_LOGO_PATH, colors={"body": "#EF316F", "cap": "#CC1E4E", "ink": "#9D5045"},
            hierarchy_lines=ruled_front_hierarchy(name, descriptor="Body Lotion"),
            map_front={"shapes": shapes, "edge_part": None})
        rows = F.apply(doc, F.assignments("gold metallic ink on the drip outlines and the script name contour"),
                       brand_metallic_hex="#C9A24B", depict_as_drawn=True)["applied"]
        plated = {nm for r in rows if r.get("plate") for nm in r["nodes"]}
        assert {"drip-map-0-shade", "product-name-traced"} <= plated, plated
        nodes = {getattr(n, "name", None): n for n, _ in doc.walk()}

        def box(node):
            xs = [sg.x for sg in node.segments if getattr(sg, "x", None) is not None]
            ys = [sg.y for sg in node.segments if getattr(sg, "y", None) is not None]
            return min(xs), min(ys), max(xs), max(ys)
        fill, shade = box(nodes["band-map-0"]), box(nodes["band-map-0-inline"])
        outer = box(nodes["drip-map-0-shade"])
        body, ring_in = box(nodes["script-lettering-body"]), box(nodes["script-lettering-inline"])
        ring_out = box(nodes["product-name-traced"])
        # the points to read, in mm: inside the fill and the body; on the gold, between its outer edge and the pale line's
        points = {"band's fill": ((fill[0] + fill[2]) / 2, (fill[1] + fill[3]) / 2),
                  "band's gold": ((outer[0] + shade[0]) / 2, (fill[1] + fill[3]) / 2),
                  "letter's body": ((body[0] + body[2]) / 2, (body[1] + body[3]) / 2),
                  "letter's gold": ((ring_out[0] + ring_in[0]) / 2, (body[1] + body[3]) / 2)}
        with tempfile.TemporaryDirectory() as d:
            pdf = fitz.open(emit_pdf_ai(doc, d + "/plate.ai"))
            assert pdf.page_count >= 2
            page1, plate = pdf[0].get_pixmap(dpi=300), pdf[1].get_pixmap(dpi=300)

            def at(pix, where):
                x, y = points[where]
                return pix.pixel(int(x / 25.4 * 300), int(y / 25.4 * 300))
            got = {where: at(plate, where) for where in points}
            assert max(got["band's gold"]) < 60 and max(got["letter's gold"]) < 60, got     # the gold: foil
            assert min(got["band's fill"]) > 200 and min(got["letter's body"]) > 200, got   # never the band or the letter
            seen = {where: at(page1, where) for where in ("band's fill", "letter's body")}
            assert max(abs(a - b) for a, b in zip(seen["band's fill"], (0xF4, 0xE6, 0xD6))) <= 6, seen
            assert max(abs(a - b) for a, b in zip(seen["letter's body"], (0xEE, 0xAA, 0xB2))) <= 6, seen

    def test_his_answer_the_mark_is_measured_by_its_own_gold_ink(self):
        """His answer after test day finding 3 (2026-09-30): the house mark at "the place the picture gives it" — on the
        tube standing on its cap, a gold mark on the hot pink inside a looser box from the map's read: its place and size
        are its gold ink's, to the pixel, never the read's box."""
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        ImageDraw.Draw(im).rectangle((200, 160, 311, 185), fill=(214, 170, 90))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]
        rec = dict(m, parts=[{"kind": "mark", "name": "BBROSE gold wordmark", "colour": "#D6AA5A",
                              "box": [(190 - x0) / (x1 - x0), (150 - y0) / (y1 - y0), (330 - x0) / (x1 - x0),
                                      (195 - y0) / (y1 - y0)]}])
        (mark,) = dm.trace_shapes(png, rec)["marks"]
        got = [mark["box"][0] * (x1 - x0) + x0, mark["box"][1] * (y1 - y0) + y0,
               mark["box"][2] * (x1 - x0) + x0, mark["box"][3] * (y1 - y0) + y0]
        assert max(abs(a - b) for a, b in zip(got, [200, 160, 312, 186])) <= 1, got

    def test_his_answer_a_type_line_is_placed_by_its_ink_and_typed_only_from_a_source(self):
        """His answer after test day finding 3 (2026-09-30) and the executor's proposal recorded with it: the small copy
        "placed at the picture's place and size but typed from the brief". A brown type line on the tube's soft pink is
        placed by its own ink, to the pixel; a brief's front copy is read as its phrases; each line takes the words of
        the source phrase that matches what the picture shows — the name from the record, the descriptor and the
        capacity from the brief — and a line no source carries (a scent line, an Arabic name the record does not hold)
        is left out, never typed from the picture."""
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        ImageDraw.Draw(im).rectangle((210, 452, 301, 459), fill=(140, 80, 60))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]
        rec = dict(m, parts=[{"kind": "type", "name": "descriptor", "colour": "#8C503C", "lettering": "sans",
                              "seen_text": "Body Lotion • لوشن للجسم",
                              "box": [(200 - x0) / (x1 - x0), (448 - y0) / (y1 - y0), (312 - x0) / (x1 - x0),
                                      (464 - y0) / (y1 - y0)]}])
        (line,) = dm.trace_shapes(png, rec)["types"]
        got = [line["box"][0] * (x1 - x0) + x0, line["box"][1] * (y1 - y0) + y0,
               line["box"][2] * (x1 - x0) + x0, line["box"][3] * (y1 - y0) + y0]
        assert max(abs(a - b) for a, b in zip(got, [210, 452, 302, 460])) <= 1, got
        brief = ('Give me three clearly different directions.\n'
                 'Front copy: BBROSE logo, product name (EN + AR), "Body Lotion / لوشن للجسم",\n'
                 'scent line, 200 ml ℮ 6.7 fl oz.\n'
                 'Back copy: How to use: massage onto clean skin, daily.')
        phrases = dm.brief_front_copy(brief)
        assert phrases == ["BBROSE logo", "product name (EN + AR)", "Body Lotion / لوشن للجسم", "scent line",
                           "200 ml ℮ 6.7 fl oz"], phrases
        sources = [("Coconut Rose Body Lotion", "the product's name on the record")] + [
            (p, "the brief's front copy") for p in phrases]
        lines = [{"part": n, "seen": seen} for n, seen in (
            ("product name script", "Coconut Rose Body Lotion"), ("Arabic product name", "لوشن للجسم بجوز الهند والورد"),
            ("descriptor 1", "Body Lotion • لوشن للجسم"), ("descriptor 2", "Coconut Cream • Rose Petals"),
            ("capacity", "200 ml e 6.7 fl oz"))]
        got = {t["part"]: (t["words"], t["source"]) for t in dm.type_sources(lines, sources)}
        # [his look at 117 drawn from its map, 2026-10-02: "And about the English words, they need to be added."] the
        # English line no record carries is typed in the picture's own words, and a line from the brief prints the
        # picture's own separator; [his second look, "add the Arabic lines"] and so the Arabic line no record carries
        assert got == {"product name script": ("Coconut Rose Body Lotion", "the product's name on the record"),
                       "Arabic product name": ("لوشن للجسم بجوز الهند والورد", dm.PICTURE_ARABIC),
                       "descriptor 1": ("Body Lotion • لوشن للجسم", "the brief's front copy"),
                       "descriptor 2": ("Coconut Cream • Rose Petals", dm.PICTURE_ENGLISH),
                       "capacity": ("200 ml ℮ 6.7 fl oz", "the brief's front copy")}, got

    def test_his_answer_the_script_lettering_is_traced_from_the_picture(self):
        """His answer after test day finding 3 (2026-09-30), (3): "the script lettering also traced from the picture". A
        brown word lettered on the tube's soft pink, its line read as script: it is traced by potrace at full size, and
        the traced outlines, taken through their frame, lie on the line's own ink to within two pixels."""
        import os
        import shutil

        import pytest
        from django.conf import settings
        from PIL import Image, ImageDraw, ImageFont

        from apps.ire import brand_mark as B
        from apps.pipeline.services import concept_design_map as dm
        if shutil.which("potrace") is None:
            pytest.skip("potrace is not on this machine")
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        font = ImageFont.truetype(os.path.join(settings.BASE_DIR, "static/fonts/brand2026/Poppins/Poppins-Bold.ttf"), 34)
        d = ImageDraw.Draw(im)
        d.text((196, 430), "Rose", font=font, fill=(140, 80, 60))
        ink = d.textbbox((196, 430), "Rose", font=font)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]
        rec = dict(m, parts=[{"kind": "type", "name": "product name script", "colour": "#8C503C", "lettering": "script",
                              "seen_text": "Rose", "box": [(ink[0] - 6 - x0) / (x1 - x0), (ink[1] - 6 - y0) / (y1 - y0),
                                                           (ink[2] + 6 - x0) / (x1 - x0), (ink[3] + 6 - y0) / (y1 - y0)]}])
        (line,) = dm.trace_shapes(png, rec)["types"]
        fx0, fy0, kx, ky = line["outlines"]["frame"]
        import xml.etree.ElementTree as ET
        root = ET.fromstring(line["outlines"]["svg"].encode())
        pts = []
        for g in (el for el in root if el.tag.endswith("}g")):
            for path in g:
                for sub in B._parse_d(path.get("d"), B._transform(g.get("transform")))[0]:
                    pts += [(op[-2], op[-1]) for op in sub if op[0] != "Z"]
        xs = [(fx0 + u * kx) * (x1 - x0) + x0 for u, _v in pts]
        ys = [(fy0 + v * ky) * (y1 - y0) + y0 for _u, v in pts]
        got = [min(xs), min(ys), max(xs), max(ys)]
        assert max(abs(a - b) for a, b in zip(got, [line["box"][0] * (x1 - x0) + x0, line["box"][1] * (y1 - y0) + y0,
                                                     line["box"][2] * (x1 - x0) + x0,
                                                     line["box"][3] * (y1 - y0) + y0])) <= 2, got

    def test_his_answer_the_cap_meets_the_body_where_the_pictures_cap_colour_begins(self):
        """His answer after test day finding 3 (2026-09-30): the layout "exactly the picture"; his check of the map: the
        cap as the picture shows it. On the tube standing on its cap, with a brown type line just above the cap: the cap
        meets the body where its own colour begins, to the pixel, never at the type; and the drawing's outline takes
        that edge, turned into its own frame, saying it replaced the outline's narrowing."""
        import types

        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY, _profile_with_outline
        from apps.pipeline.targets.container.silhouettes import ContainerProfile
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        ImageDraw.Draw(im).rectangle((226, 596, 286, 603), fill=(140, 80, 60))     # a type line just above the cap
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]
        rec = dict(m, parts=[{"kind": "closure", "name": "flip-top cap", "colour": "#D71969",
                              "box": [(171 - x0) / (x1 - x0), (606 - y0) / (y1 - y0), (341 - x0) / (x1 - x0), 1.0]},
                             {"kind": "field", "name": "soft pink lower field", "colour": "#F7BEC8",
                              "box": [0.2, (298 - y0) / (y1 - y0), 0.8, (610 - y0) / (y1 - y0)]}])
        edge = dm.closure_edge(png, rec)
        assert edge["side"] == "foot" and abs(edge["edge"] * (y1 - y0) + y0 - 610) <= 1, edge
        assert "refused" in dm.closure_edge(png, dict(rec, source_sha256="ab" * 32))
        pic = types.SimpleNamespace(name="concept.png", open=lambda mode: io.BytesIO(png))
        output = types.SimpleNamespace(approved_image=types.SimpleNamespace(image_file=pic))
        tube = ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0, width_mm=50.0)
        records = []
        drawn = _profile_with_outline(tube, {co.SCHEMA: co.trace_elevation(png), dm.SCHEMA: rec}, output, records)
        assert drawn.outline["closure_share"] == round(1.0 - edge["edge"], 4), drawn.outline["closure_share"]
        source = dict((k, v) for _op, k, v in records)[OUTLINE_SOURCE_KEY]
        assert source["closure_share"] == drawn.outline["closure_share"] and "map" in source["closure_by"]

    def test_his_answer_a_traced_script_outline_broken_by_a_highlight_is_traced_whole(self):
        """Measured on 117 at 300 dpi (2026-10-02): its script's outline ring carries a pale highlight line, and traced as
        read it broke into fragments. A brown ring on the tube's pink with a 2 px pale gap through it is traced as ONE
        closed ring — its two outlines, outer and inner — never as broken pieces."""
        import shutil
        import xml.etree.ElementTree as ET

        import pytest
        from PIL import Image, ImageDraw

        from apps.ire import brand_mark as B
        from apps.pipeline.services import concept_design_map as dm
        if shutil.which("potrace") is None:
            pytest.skip("potrace is not on this machine")
        im = Image.open(io.BytesIO(_tube_on_its_cap_png())).convert("RGB")
        d = ImageDraw.Draw(im)
        d.ellipse((216, 420, 296, 470), outline=(140, 80, 60), width=6)
        d.rectangle((212, 444, 224, 445), fill=(247, 190, 200))                  # a pale highlight across the ring
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        m = dm.read_map(png)
        x0, y0, x1, y1 = m["product_box_px"]
        rec = dict(m, parts=[{"kind": "type", "name": "a script letter", "colour": "#8C503C", "lettering": "script",
                              "seen_text": "O", "box": [(208 - x0) / (x1 - x0), (412 - y0) / (y1 - y0),
                                                        (304 - x0) / (x1 - x0), (478 - y0) / (y1 - y0)]}])
        (line,) = dm.trace_shapes(png, rec)["types"]
        root = ET.fromstring(line["outlines"]["svg"].encode())
        subs = [sub for g in root if g.tag.endswith("}g") for path in g
                for sub in B._parse_d(path.get("d"), B._transform(g.get("transform")))[0]]
        assert len(subs) == 2, len(subs)                                     # the ring whole: outer and inner

    def test_his_answer_the_score_sets_the_drawing_beside_the_concept_part_by_part(self):
        """His answer after test day finding 3 (2026-09-30): "that design should be drawn one hundred percent", read
        against the bars told him — each part within ΔE 3 and 1 mm. A tube drawn in two fields, hot pink over soft pink,
        scored against a map whose upper field is the drawn hot pink and whose lower field is a pink ΔE 13 away: the
        upper field passes where its place is recorded at the map's own box; the lower fails on its colour; a part whose
        place is not recorded fails and says so; the product alone is drawn for the score, never the sheet."""
        from apps.ire.compose_container import compose_container_graph
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        trace = co.trace_elevation(_tube_on_its_cap_png())
        outline, _src = co.outline_for(trace, archetype="tube", variant="standard", image_sha256=trace["source_sha256"])
        bb = build_backbone(ContainerProfile(archetype="tube", variant="standard", cap_style="flip", height_mm=180.0,
                                             width_mm=50.0, outline=outline))
        doc = compose_container_graph(bb, product_name="Rose", sku="X", body_split=0.342,
                                      colors={"body": "#E91E8C", "cap": "#CC1E4E", "body_lower": "#F7B8D4"})
        png = dm.product_png(doc)
        from PIL import Image
        im = Image.open(io.BytesIO(png))
        assert im.mode == "RGBA" and abs(im.size[1] / im.size[0] - 180.0 / bb.width_mm) < 0.1, im.size   # alone
        record = {"state": dm.MAP_READ, "parts": [
            {"kind": "field", "name": "hot pink upper field", "box": [0.1, -0.01, 0.9, 0.3], "colour": "#E91E8C"},
            {"kind": "field", "name": "soft pink lower field", "box": [0.2, 0.4, 0.8, 0.8], "colour": "#F0A9B1"},
            {"kind": "closure", "name": "cap", "box": [0.25, 0.86, 0.75, 0.99], "colour": "#CC1E4E"}]}
        s = dm.score(record, png, drawn_boxes={"hot pink upper field": [0.1, -0.01, 0.9, 0.3],   # read above its top
                                               "soft pink lower field": [0.2, 0.4, 0.8, 0.8]}, size_mm=(50.0, 180.0))
        rows = {r["name"]: r for r in s["parts"]}
        assert s["schema_version"] == dm.SCORE_SCHEMA and s["bars"] == {"delta_e": 3.0, "mm": 1.0}
        assert rows["hot pink upper field"]["delta_e"] <= 3.0 and rows["hot pink upper field"]["passes"], rows
        assert rows["soft pink lower field"]["delta_e"] > 10.0 and not rows["soft pink lower field"]["passes"]
        assert rows["cap"]["delta_e"] <= 3.0 and not rows["cap"]["passes"] and "not recorded" in rows["cap"]["place"]
        assert (s["passed"], s["of"]) == (1, 3)

    def test_the_hero_is_measured_in_its_window_and_its_metal_told_from_its_flat(self):
        """§BH71 PART 1, the owner's goal of 2026-09-28: \"The concept's hero element (e.g. 91's rose-gold flower
        emblem), its finish and its material carry into the drawing.\" ROUTE A: the lid rectified by its own rim, its
        window's ellipse found, each petal's pose measured — its point, its axis, its length and width as shares of the
        window — and the ones lit like foil told from the flat ones; a lid with no window says so."""
        from apps.pipeline.services import concept_outline as co
        png = _emblem_png()
        hero = co.trace_hero(png, co.trace_plan(png))
        assert (hero["state"], hero["count"]) == (co.HERO_FROM_CONCEPT, 5), hero.get("reason")
        assert hero["metal_units"] == ["petal-1", "petal-2"], hero["metal_units"]
        thetas = sorted(u["theta_deg"] for u in hero["units"])
        assert all(abs(t - want) < 3.0 for t, want in zip(thetas, (-140.0, -115.0, -90.0, -65.0, -40.0))), thetas
        assert all(abs(u["length"] - 0.357) < 0.02 and abs(u["width"] - 0.143) < 0.02 for u in hero["units"])
        assert co.trace_hero(png, co.trace_plan(png)) == hero                   # the same bytes, the same record
        box = co.hero_window_box(hero)
        assert abs((box[2] - box[0]) - 0.40) < 0.02 and abs((box[1] + box[3]) / 2 - 0.55) < 0.02, box   # its place
        plain = _emblem_png(window=False)
        bare = co.trace_hero(plain, co.trace_plan(plain))
        assert bare["state"] == co.HERO_NOT_READ and "no window" in bare["reason"], bare
        assert co.trace_hero(png, None)["state"] == co.HERO_NOT_READ

    def test_the_target_reads_the_hero_of_the_approved_picture(self):
        """The container target reads the hero once per picture, locally — on the trace its record carries for these
        bytes, else traced there — and a picture it cannot open is said, never read."""
        import tempfile
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import _read_hero
        with tempfile.NamedTemporaryFile(suffix=".png") as fh:
            fh.write(_emblem_png())
            fh.flush()
            hero = _read_hero({}, fh.name, "compact")
        assert (hero["state"], hero["count"]) == (co.HERO_FROM_CONCEPT, 5), hero.get("reason")
        gone = _read_hero({}, "/nonexistent/concept.png", "compact")
        assert (gone["state"], gone["reason"]) == (co.HERO_NOT_READ, co.TRACE_NO_CONCEPT_IMAGE)

    def test_a_tilted_round_lid_is_traced_round_with_its_tilt(self):
        from apps.pipeline.services import concept_outline as co
        png = _lid_png((250, 210), 25.0)
        t = co.trace_plan(png)
        assert t["state"] == co.TRACED_FROM_CONCEPT and t["kind"] == co.ROUND, t
        assert abs(t["tilt_deg"] - 32.9) < 2.0, t["tilt_deg"]          # acos(210 / 250)
        assert t["rim"]["support"] >= co.TRACE_PARAMS["rim_support_min"]
        assert t["rim"]["residual"] <= co.TRACE_PARAMS["rim_residual_max"]
        assert t["source_sha256"] == hashlib.sha256(png).hexdigest() and co.trace_plan(png) == t
        assert co.trace_plan(_lid_png((250, 250), 0.0))["tilt_deg"] < 3.0   # a lid seen square-on is a circle

    def test_an_oval_the_reading_names_is_a_shape_no_variant_draws(self):
        from apps.pipeline.services import concept_outline as co
        t = co.trace_plan(_lid_png((250, 170), 0.0), reading_shape="oval")
        assert t["kind"] == co.OVAL and co.proposal(t, "compact", width_mm=110.0) == {}
        assert co.unknown_shape(t) == {"kind": co.OVAL, "words": "an oval lid"}
        _o, src = co.outline_for(t, archetype="compact", variant="round", image_sha256=t["source_sha256"])
        assert (src["source"], src["reason"]) == (co.TEMPLATE_FALLBACK, "TRACE_SHAPE_UNKNOWN")

    def test_bh71_a_lid_no_variant_draws_is_said_on_the_record_and_never_squeezed(self):
        """§BH71 PART 3: when the shape step is proposed no reading names the lid (the concept's read comes later, and
        is paid), so the tracer read an ellipse as a round lid seen tilted even when the brief said \"an oval compact\";
        and a lid no variant draws kept the form's first variant on the record. The brief's own name for the lid
        names the ellipse, saying whose name it was; a lid no variant draws is said on the record — from the approved
        concept when its picture shows it, from the brief otherwise, with no picture too — and no variant proposed;
        a round lid no word names is proposed round exactly as before."""
        from types import SimpleNamespace
        from django.core.files.base import ContentFile
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.targets.container import _seed_outline_proposal, lid_shape_named_in

        def picture(png):
            return SimpleNamespace(image_file=ContentFile(png, name="concept.png"))
        record = cc.build_inferred_profile("compact", "rounded_rect", {"body_width_mm": 110.0, "body_height_mm": 95.0})
        oval = lid_shape_named_in("compact", "an oval compact of pressed powder")
        out, trace = _seed_outline_proposal(record, picture(_lid_png((250, 170), 0.0)), named_shape=oval)
        assert (trace["kind"], trace["named_by"], trace["proposal"]) == (co.OVAL, "the brief's words", {}), trace
        assert out["variant"] == "" and out["fields"]["variant"]["value"] is None
        assert out["unknown_shape"]["source"] == "the approved concept" and out["unknown_shape"]["kind"] == "oval"
        assert out["unknown_shape"]["sentence"].startswith("The approved concept shows an oval lid")
        assert out["profile_hash"] == cc.profile_hash(out) and record["variant"] == "rounded_rect"
        heart = lid_shape_named_in("compact", "a heart-shaped compact")
        out2, trace2 = _seed_outline_proposal(record, picture(_lid_png((250, 250), 0.0)), named_shape=heart)
        assert trace2["kind"] == co.ROUND and trace2["proposal"] == {}      # its rim reads round; it is not proposed
        assert out2["variant"] == "" and out2["unknown_shape"]["source"] == "the brief"
        out3, _t3 = _seed_outline_proposal(record, SimpleNamespace(image_file=None), named_shape=oval)
        assert out3["variant"] == "" and out3["unknown_shape"]["sentence"].startswith("The brief names an oval lid")
        out4, trace4 = _seed_outline_proposal(record, picture(_lid_png((250, 250), 0.0)))
        assert out4["variant"] == "round" and "unknown_shape" not in out4 and "named_by" not in trace4

    def test_a_picture_with_no_lid_falls_back_to_the_template_by_name(self):
        import io
        from apps.pipeline.services import concept_outline as co
        buf = io.BytesIO()
        Image.new("RGB", (640, 960), (238, 232, 224)).save(buf, "PNG")
        assert (co.trace_plan(buf.getvalue())["state"], co.trace_plan(buf.getvalue())["reason"]) == (
            co.TEMPLATE_FALLBACK, co.TRACE_NO_RIM)
        assert co.trace_plan(b"")["reason"] == co.TRACE_NO_CONCEPT_IMAGE
        assert co.trace_plan(b"not a picture")["reason"] == co.TRACE_IMAGE_UNREADABLE

    def test_the_proposal_and_the_drawings_record_of_which_drew(self):
        from apps.pipeline.services import concept_outline as co
        t = co.trace_plan(_lid_png((250, 210), 25.0))
        assert co.proposal(t, "compact", width_mm=110.0) == {"variant": "round", "height_mm": 110.0}
        outline, src = co.outline_for(t, archetype="compact", variant="round", image_sha256=t["source_sha256"])
        assert src["source"] == co.TRACED_FROM_CONCEPT and outline["kind"] == co.ROUND
        assert co.words(src).startswith("traced from the concept — a round lid, the rim ")
        _o, moved = co.outline_for(t, archetype="compact", variant="round", image_sha256="0" * 64)
        assert moved["reason"] == co.TRACE_IMAGE_CHANGED
        _o, other = co.outline_for(t, archetype="compact", variant="rounded_rect", image_sha256=t["source_sha256"])
        assert other["reason"] == "TRACE_NOT_ACCEPTED_AT_CONFIRMATION"
        assert co.words(other).startswith("the compact template, rounded rectangle — the fallback: ")
        assert co.words(co.outline_for(None, archetype="compact", variant="round", image_sha256=None)[1]) == (
            "the compact template, round — the fallback: there is no approved concept picture to trace")


class MaskExtractionTests(SimpleTestCase):
    def test_alpha_extraction_is_deterministic(self):
        img = _bottle_image(alpha_bg=True)
        m1, method, conf, _ = ca.extract_mask(img)
        m2, _, _, _ = ca.extract_mask(img)
        assert method == ca.ALPHA and conf == "HIGH"
        assert np.array_equal(m1, m2)

    def test_background_extraction_is_deterministic(self):
        img = _bottle_image()
        m1, method, _, _ = ca.extract_mask(img)
        m2, _, _, _ = ca.extract_mask(img)
        assert method == ca.BACKGROUND_SEGMENTATION
        assert np.array_equal(m1, m2)

    def test_owner_golden_mask_is_used_and_hash_verified(self):
        img = _bottle_image()
        golden = Image.new("L", img.size, 0)
        ImageDraw.Draw(golden).rectangle([200, 100, 440, 800], fill=255)
        digest = hashlib.sha256(golden.tobytes()).hexdigest()
        mask, method, conf, _ = ca.extract_mask(img, golden_mask=golden)
        assert method == ca.OWNER_GOLDEN_MASK and conf == "HIGH"
        assert int(mask.sum()) == 241 * 701
        assert hashlib.sha256(golden.tobytes()).hexdigest() == digest

    def test_valid_mask_never_unmeasurable(self):
        rec = ca.analyze_concept_image(_bottle_image(), safe_filename="x",
                                       sha256="x")
        assert rec["classification"] == ca.READY
        assert rec["analysis_state"] == ca.MEASURED

    def test_empty_and_frame_filling_masks_rejected(self):
        blank = Image.new("RGBA", (640, 900), (255, 255, 255, 255))
        rec = ca.analyze_concept_image(blank, safe_filename="x", sha256="x")
        assert rec["classification"] == ca.UNMEASURABLE_CLASS
        full = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        ImageDraw.Draw(full).rectangle([1, 1, 198, 198],
                                       fill=(200, 60, 60, 255))
        rec = ca.analyze_concept_image(full, safe_filename="x", sha256="x")
        assert rec["classification"] == ca.UNMEASURABLE_CLASS
        assert ca.CONCEPT_MASK_FRAME_FILLING in rec["blocking_findings"]

    def test_fragmented_and_multiple_components_reported(self):
        img = Image.open(FIXTURES / "bad_fragmented_mask.png")
        rec = ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        assert ca.CONCEPT_MASK_FRAGMENTED in rec["blocking_findings"]
        img = Image.open(FIXTURES / "bad_multiple_products.png")
        rec = ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        assert ca.CONCEPT_MULTIPLE_PRODUCTS in rec["blocking_findings"]

    def test_frame_touch_reported(self):
        img = Image.open(FIXTURES / "bad_touches_frame.png")
        rec = ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        assert ca.CONCEPT_FRAME_CONTACT in rec["blocking_findings"]
        assert rec["classification"] == ca.PARTIAL_CLASS

    def test_hole_filling_reports_outline_sources(self):
        img = Image.new("RGBA", (640, 900), (255, 255, 255, 255))
        ImageDraw.Draw(img).rounded_rectangle(
            [220, 100, 420, 800], radius=30, outline=(90, 44, 58, 255),
            width=6)
        rec = ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        assert rec["classification"] == ca.READY
        assert rec["mask_quality"]["holes_filled_ratio"] > 0.5
        assert any("OUTLINE_SOURCE" in w for w in rec["warnings"])
        # coverage describes the FILLED product, not the stroke ring
        assert rec["measurements"]["coverage_ratio"] > 0.15

    def test_source_image_is_never_modified(self):
        img = _bottle_image()
        before = np.asarray(img).copy()
        ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        assert np.array_equal(np.asarray(img), before)


class MeasurementTests(SimpleTestCase):
    def _rect_mask(self, x0=100, y0=200, w=100, h=300, size=(640, 900)):
        m = np.zeros((size[1], size[0]), dtype=bool)
        m[y0:y0 + h, x0:x0 + w] = True
        return m

    def test_bounds_aspect_coverage_centroid_margins(self):
        m = ca.measure_mask(self._rect_mask())
        assert m["bounding_box_px"] == {"x": 100, "y": 200, "width": 100,
                                        "height": 300}
        assert m["aspect_h_over_w"] == 3.0
        assert abs(m["coverage_ratio"] - (100 * 300) / (640 * 900)) < 1e-4
        assert abs(m["centroid_normalized"]["x"] - 149.5 / 640) < 1e-3
        assert m["clearances_normalized"]["left"] == round(100 / 640, 4)
        assert not any(m["frame_contacts"].values())

    def test_translation_invariance(self):
        a = ca.measure_mask(self._rect_mask(x0=100, y0=200))
        b = ca.measure_mask(self._rect_mask(x0=300, y0=400))
        assert a["aspect_h_over_w"] == b["aspect_h_over_w"]
        assert a["contour"]["width_profile"] == b["contour"]["width_profile"]

    def test_uniform_scale_invariance(self):
        a = ca.measure_mask(self._rect_mask(w=100, h=300))
        b = ca.measure_mask(self._rect_mask(w=200, h=600))
        assert a["aspect_h_over_w"] == b["aspect_h_over_w"]
        assert a["contour"]["width_profile"] == b["contour"]["width_profile"]

    def test_horizontal_distortion_changes_expected_ratio(self):
        a = ca.measure_mask(self._rect_mask(w=100, h=300))
        b = ca.measure_mask(self._rect_mask(w=125, h=300))
        assert abs(a["aspect_h_over_w"] / b["aspect_h_over_w"] - 1.25) < 0.01

    def test_profile_and_contour_deterministic(self):
        img = _bottle_image()
        r1 = ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        r2 = ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        assert r1["measurements"]["contour"] == r2["measurements"]["contour"]

    def test_measurement_failures_stay_explicit(self):
        tiny = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
        ImageDraw.Draw(tiny).rectangle([30, 30, 33, 33],
                                       fill=(90, 44, 58, 255))
        rec = ca.analyze_concept_image(tiny, safe_filename="x", sha256="x")
        assert rec["classification"] == ca.UNMEASURABLE_CLASS
        assert rec["measurements"] is None
        assert ca.CONCEPT_PRODUCT_TOO_SMALL in rec["blocking_findings"]


class GoldenFixtureTests(SimpleTestCase):
    def test_manifest_versioned_ids_unique_hashes_match(self):
        assert MANIFEST["schema"] == "golden_visual_fixtures/1.0"
        ids = [f["fixture_id"] for f in MANIFEST["fixtures"]]
        assert len(ids) == len(set(ids))
        for f in MANIFEST["fixtures"]:
            if not f.get("sha256"):
                continue
            path = FIXTURES / f["file"]
            assert path.exists(), f["file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == \
                f["sha256"], f"immutable fixture changed: {f['fixture_id']}"
            assert f["immutable"] is True

    def test_m3_fixture_copy_preserves_identity(self):
        entry = next(f for f in MANIFEST["fixtures"]
                     if f["fixture_id"] == "good_m3_fixture_silhouette")
        assert entry["sha256"].startswith("4ecc8e9df1d1")

    def test_every_analyzed_fixture_matches_expectations(self):
        for f in MANIFEST["fixtures"]:
            if not f.get("analyzed_by_vqr2b_a"):
                continue
            rec = ca.analyze_concept_image(
                Image.open(FIXTURES / f["file"]),
                safe_filename=f["file"], sha256=f["sha256"] or "")
            assert rec["classification"] == f["expected_analyzability"], \
                f["fixture_id"]
            assert rec["mask_method"] == f["expected_mask_method"], \
                f["fixture_id"]
            for code in f["expected_reason_codes"]:
                assert code in rec["blocking_findings"], \
                    (f["fixture_id"], code)
            exp = f.get("expected_measurements") or {}
            m = rec["measurements"]
            if "aspect_h_over_w" in exp and m:
                lo, hi = exp["aspect_h_over_w"]
                assert lo <= m["aspect_h_over_w"] <= hi, f["fixture_id"]
            if "aspect_max" in exp and m:
                assert m["aspect_h_over_w"] <= exp["aspect_max"], \
                    f["fixture_id"]
            if "coverage" in exp and m:
                lo, hi = exp["coverage"]
                assert lo <= m["coverage_ratio"] <= hi, f["fixture_id"]
            if "closure_separable" in exp and m:
                assert (m["closure_zone"] is not None) == \
                    exp["closure_separable"], f["fixture_id"]
            if "symmetry_min" in exp and m:
                assert m["vertical_symmetry_deviation"] >= \
                    exp["symmetry_min"], f["fixture_id"]


class ProportionCalibrationTests(SimpleTestCase):
    def test_ratio_series_deterministic_and_ordered(self):
        rec1 = mc.build_calibration_record()
        rec2 = mc.build_calibration_record()
        assert json.dumps(rec1["samples"], sort_keys=True) == \
            json.dumps(rec2["samples"], sort_keys=True)
        ratios = [s["distortion_ratio"] for s in rec1["samples"]]
        assert ratios == sorted(ratios) == list(mc.RATIOS)
        aspects = [s["aspect_h_over_w"] for s in rec1["samples"]]
        assert aspects == sorted(aspects, reverse=True)

    def test_equal_heights_only_horizontal_deforms(self):
        fit = mc.load_m3_fit()
        base = mc.render_sample(1.0, fit=fit)
        widened = mc.render_sample(1.15, fit=fit)
        assert base.height == widened.height
        assert widened.width > base.width
        g1 = mc.sample_geometry(1.0, fit=fit)
        g2 = mc.sample_geometry(1.15, fit=fit)
        assert g1["height_px"] == g2["height_px"]
        assert abs(g2["width_px_at_sample_height"]
                   / g1["width_px_at_sample_height"] - 1.15) < 0.01

    def test_task57_evidence_ratio_present_and_threshold_provisional(self):
        rec = mc.build_calibration_record()
        assert any(abs(s["distortion_ratio"] - 1.1244) < 1e-9
                   for s in rec["samples"])
        assert rec["task_57_evidence_ratio"] == 1.1244
        assert rec["proposed_threshold"] == 1.05
        assert rec["threshold_status"] == \
            "PROVISIONAL_PENDING_OWNER_CALIBRATION"
        assert rec["owner_visual_review"]["verdict"] is None
        assert rec["selected_final_policy"] is None

    def test_no_production_policy_activated(self):
        # the production gate carries NO proportion-enforcement threshold;
        # calibration lives beside it, never inside it
        from apps.pipeline.services.visual_quality_gate import THRESHOLDS
        assert "m3_max_distortion_ratio" not in THRESHOLDS
        import apps.pipeline.services.m3_calibration as module
        src = Path(module.__file__).read_text()
        assert "reconstruct_container" not in src
        assert "build_container_backbone" not in src


class IsolationTests(SimpleTestCase):
    """§13/§20 — reconstruction-independent and provider-free."""

    def test_no_reconstruction_files_opened(self):
        opened: list[str] = []
        real_open = builtins.open

        def spy(file, *a, **kw):
            opened.append(str(file))
            return real_open(file, *a, **kw)

        img = _bottle_image()
        try:
            builtins.open = spy
            ca.analyze_concept_image(img, safe_filename="x", sha256="x")
            mc.build_calibration_record()
        finally:
            builtins.open = real_open
        for path in opened:
            assert "dielines" not in path, path
            assert "design_preview" not in path, path

    def test_no_reconstruction_imports(self):
        for module in (ca, mc):
            src = Path(module.__file__).read_text()
            assert "reconstruction_status" not in src
            assert "compose_container" not in src
            assert "emit_pdf_ai" not in src

    def test_no_provider_no_dispatch_no_gate_writes(self):
        from unittest.mock import patch
        from .test_confirm_profile_ui2b1 import _DELAY
        with patch("apps.pipeline.services.claude_service.call_claude") \
                as claude, patch(_DELAY) as delay:
            ca.analyze_concept_image(_bottle_image(), safe_filename="x",
                                     sha256="x")
            mc.build_calibration_record()
        claude.assert_not_called()
        delay.assert_not_called()
        # pure-module guarantee: neither module touches Django models
        for module in (ca, mc):
            src = Path(module.__file__).read_text()
            assert "GateDecision" not in src
            assert "DesignTask" not in src


class ReadinessSemanticsTests(SimpleTestCase):
    """§1 owner correction — split readiness, mask authority, MEDIUM cap."""

    def test_outline_fill_reports_derived_authority_and_medium_cap(self):
        # ALPHA extraction (normally HIGH) of an outline drawing must cap
        # at MEDIUM with OUTLINE_FILL_DERIVED authority
        img = Image.new("RGBA", (640, 900), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(
            [220, 100, 420, 800], radius=30, outline=(90, 44, 58, 255),
            width=6)
        rec = ca.analyze_concept_image(img, safe_filename="x", sha256="x")
        assert rec["mask_method"] == ca.ALPHA
        assert rec["mask_authority"] == ca.MASK_AUTHORITY_OUTLINE_FILL
        assert rec["mask_confidence"] == "MEDIUM"

    def test_solid_source_keeps_direct_authority(self):
        rec = ca.analyze_concept_image(_bottle_image(alpha_bg=True),
                                       safe_filename="x", sha256="x")
        assert rec["mask_authority"] == ca.MASK_AUTHORITY_DIRECT
        assert rec["mask_confidence"] == "HIGH"

    def test_readiness_reports_split_facts_with_authority(self):
        rec = ca.analyze_concept_image(_bottle_image(), safe_filename="x",
                                       sha256="x")
        r = rec["measurement_readiness"]
        for key in ("SILHOUETTE_ANALYSIS_READY", "CLOSURE_ANALYSIS_READY",
                    "COMPOSITION_ANALYSIS_READY", "MASK_AUTHORITY",
                    "MASK_CONFIDENCE"):
            assert key in r, key
        assert r["MASK_AUTHORITY"] == rec["mask_authority"]
        assert r["MASK_CONFIDENCE"] == rec["mask_confidence"]

    def test_canonical_bounds_single_definition(self):
        # §2: one canonical proportion definition, converged and versioned
        cb = mc.canonical_bounds()
        assert cb["schema"] == "m3_canonical_proportion_bounds/1.0"
        assert cb["aspect_h_over_w"] == mc.CANONICAL_ASPECT == 3.0606
        assert cb["closure_included_in_height"] is True
        # the calibration record carries the canonical definition
        rec = mc.build_calibration_record()
        assert rec["canonical_bounds"]["aspect_h_over_w"] == 3.0606
        assert rec["native_m3_aspect_h_over_w"] == 3.0606


class TheWiringChecksW2Tests(SimpleTestCase):
    """[His answer of 2026-10-05, W2: "build it. Plain stripes are basic."] A plain stripe the read names a "band" is
    traced and drawn; a band whose gold edge the picture breaks is still refused, never drawn flat."""

    @staticmethod
    def _carton(foot):
        from PIL import Image, ImageDraw

        from apps.pipeline.services import concept_design_map as dm
        im = Image.new("RGB", (512, 768), (236, 231, 226))
        d = ImageDraw.Draw(im)
        d.rectangle((156, 150, 356, 650), fill=(142, 44, 72))          # the deep rose panel
        d.polygon(foot, fill=(243, 230, 207))                           # the cream stripe across it
        buf = io.BytesIO()
        im.save(buf, "PNG")
        png = buf.getvalue()
        answer = {"face": [312, 300, 712, 1300], "parts": [
            {"kind": "field", "name": "deep rose ground", "box": [312, 300, 712, 1300]},
            {"kind": "band", "name": "cream stripe", "box": [312, 760, 712, 900]}], "light": [], "notes": "stand-in"}
        return png, dm.carton_record(png, answer, model="stand-in", cost={"usd": "0.000000", "calls": 0})

    def test_a_plain_stripe_read_as_a_band_is_traced_and_drawn(self):
        from apps.ire.compose_container import _map_front_group
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        png, rec = self._carton([(156, 380), (356, 380), (356, 450), (156, 450)])
        assert rec["state"] == dm.MAP_READ, rec
        shapes = dm.trace_shapes(png, rec)
        bands = shapes.get("bands") or []
        assert [b["part"] for b in bands] == ["cream stripe"] and shapes["problems"] == [], shapes["problems"]
        band = bands[0]
        assert band["plain"] and band["edge"] == [] and band["drips"] == 0 and "edge_ink" not in band, band
        assert set(band.get("edges") or {}) == {"left", "right"}, band.get("edges")   # edge to edge: into the bleed
        ys = [p[1] for p in band["outline"]]
        assert abs(min(ys) - 0.46) < 0.01 and abs(max(ys) - 0.60) < 0.01, (min(ys), max(ys))   # rows 380 to 450 of 150-650
        assert min(p[0] for p in band["outline"]) < 0.0 < 1.0 < max(p[0] for p in band["outline"])   # into the bleed
        assert all(type(v) is float for p in band["outline"] for v in p)          # plain numbers: the record is JSON
        assert not dm.undrawn_parts(rec, shapes, []), dm.undrawn_parts(rec, shapes, [])
        bb = build_backbone(ContainerProfile(archetype="bottle", height_mm=100, width_mm=40))
        zone = {"x": 0.0, "y": 0.0, "width": 40.0, "height": 100.0}
        _group, _places, record = _map_front_group({"shapes": shapes}, zone, bb, 1.0, 0.0, 0.0)
        assert "cream stripe" in record["drawn"] and record["motif_prefixes"] == [], record

    def test_a_band_whose_foot_wanders_is_never_drawn_flat(self):
        """[Re-pinned by his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at
        2f42010): "Make that part drawable (it's 122's own look: line-art rose field, oval, scallop band, type)".] A band
        whose foot wanders is never drawn flat as a stripe: refused before, it is traced now as the shape it is, its
        foot as the picture prints it — and drawn."""
        from apps.pipeline.services import concept_design_map as dm
        png, rec = self._carton([(156, 380), (356, 380), (356, 420), (300, 470), (250, 420), (200, 470), (156, 430)])
        shapes = dm.trace_shapes(png, rec)
        assert not shapes.get("bands"), shapes.get("bands")
        shaped = [sh for sh in shapes.get("shapes") or [] if sh["part"] == "cream stripe"]
        assert shaped and shaped[0]["shaped_band"], shapes["problems"]
        assert shaped[0]["box"][3] - shaped[0]["box"][1] > 0.05                    # its wandering foot kept, never flat
        assert "cream stripe" not in {u["name"] for u in dm.undrawn_parts(rec, shapes, [])}


class TheWiringChecksW7Tests(SimpleTestCase):
    """[His answer of 2026-10-05, W7: "build it. Squat jars (creams, balms) are core products."] A jar pictured wider
    than tall is read standing, as the picture stands it — never laid on its side and refused as "two colours"."""

    @staticmethod
    def _squat_jar_png(size=(900, 900), ground=(236, 228, 220), body=(214, 170, 160), lid=(203, 168, 125)):
        w, h = size
        im = Image.new("RGB", size, ground)
        d = ImageDraw.Draw(im)
        cx, bw = w // 2, int(w * 0.56)
        d.rounded_rectangle([cx - bw // 2, int(h * 0.44), cx + bw // 2, int(h * 0.76)], radius=int(bw * 0.06), fill=body)
        lw = int(bw * 0.92)
        d.rounded_rectangle([cx - lw // 2, int(h * 0.32), cx + lw // 2, int(h * 0.45)], radius=10, fill=lid)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()

    def test_a_squat_jar_is_read_standing_as_the_picture_stands_it(self):
        from apps.pipeline.services import concept_design_map as dm
        from apps.pipeline.services import concept_outline as co
        png = self._squat_jar_png()
        t = co.trace_elevation(png)
        assert t["state"] == co.TRACED_FROM_CONCEPT, t.get("detail")
        assert abs(t["turned_deg"]) < 1.0, t["turned_deg"]                     # never laid on its side
        assert t["height_to_width"] < 1.0, t["height_to_width"]                  # wider than tall, as pictured
        assert t["stood_as_pictured"] is True                                    # and the record says how it was read
        picture, mask, read = co.standing_pixels(png)
        assert "refused" not in read and abs(read["turned_deg"]) < 1.0, read
        m = dm.read_map(png)
        assert m["state"] == dm.MAP_READ, m.get("detail")

    def test_a_tall_bottle_a_little_turned_is_still_stood_upright(self):
        from apps.pipeline.services import concept_outline as co
        t = co.trace_elevation(_bottle_png(tilt=6.0))
        assert abs(abs(t["turned_deg"]) - 6.0) < 1.5 and t["height_to_width"] > 3.0, t
        assert "stood_as_pictured" not in t                                      # read the way it always was


#: [his rules 1 and 2, 2026-10-05] the lines of 119's own brief that give its carton and its vial their words
BRIEF_119_LINES = (
    "Rose Glaze Lip Gloss (test)\n\n"
    "Arabic name: ملمّع الشفاه روز جليز\n\n"
    "Vial copy: BBROSE logo, \"Rose Glaze\", \"Lip Gloss / ملمّع الشفاه\",\n"
    "8 ml ℮ 0.27 fl oz. Keep the vial's words horizontal.\n"
    "Carton front: BBROSE logo, \"Rose Glaze\", the hero graphic.\n"
    "Carton side: \"LIP GLOSS · ملمّع الشفاه\", 8 ml ℮ / 0.27 fl oz.\n"
    "Carton back: How to use: apply to lips alone or over lipstick. /\nMade in UAE.\n")


class HisRulesOneAndTwoTests(SimpleTestCase):
    """[His rules 1 and 2 for 119 and every design, 2026-10-05: "My brief's words win over the picture's text: 'Rose
    Glaze' with a space, and the Arabic ملمّع as my brief writes it." / "Keep the '·' between 'LIP GLOSS' and the
    Arabic."]"""

    TYPES = [{"part": "name", "seen": "RoseGlaze", "lettering": "display"},
             {"part": "descriptor", "seen": "LIP GLOSS", "lettering": "sans"},
             {"part": "arabic", "seen": "ملمع الشفاه", "lettering": "arabic"}]

    def _sources(self, carton):
        from types import SimpleNamespace
        from unittest.mock import patch

        from apps.pipeline.targets import container as ct
        with patch.object(ct, "brief_text", return_value=BRIEF_119_LINES):
            return ct.type_sources_for(SimpleNamespace(product=None), "Rose Glaze Lip Gloss", carton=carton)

    def test_the_cartons_lines_print_his_brief_words_and_keep_the_dot(self):
        from apps.pipeline.services import concept_design_map as dm
        got = {t["part"]: (t["words"], t["match"]) for t in dm.type_sources(self.TYPES, self._sources(True))}
        assert got == {"name": ("Rose Glaze", 1.0), "descriptor": ("LIP GLOSS ·", 1.0),
                       "arabic": ("ملمّع الشفاه", 1.0)}, got

    def test_the_vial_takes_its_own_lines_and_the_carton_never_the_vials(self):
        from apps.pipeline.services import concept_design_map as dm
        vial = {t["part"]: t["words"] for t in dm.type_sources(self.TYPES, self._sources(False))}
        assert vial["descriptor"] == "Lip Gloss /" and vial["name"] == "Rose Glaze", vial
        carton = [text for text, _o in self._sources(True)]
        assert "Lip Gloss / ملمّع الشفاه" not in carton and "LIP GLOSS · ملمّع الشفاه" in carton, carton
        assert "LIP GLOSS · ملمّع الشفاه" not in [text for text, _o in self._sources(False)]

    def test_the_halves_and_the_folding(self):
        from apps.pipeline.services import concept_design_map as dm
        assert dm.script_halves("LIP GLOSS · ملمّع الشفاه") == ["LIP GLOSS ·", "ملمّع الشفاه"]
        assert dm.script_halves("Rose Glaze") == [] and dm.script_halves("ملمّع الشفاه") == []
        assert dm._words("ملمّع") == dm._words("ملمع") and dm._squashed("RoseGlaze") == dm._squashed("Rose Glaze")
        assert dm._squashed("Rose Glaze") != dm._squashed("Rose Glaze Lip Gloss")

    def test_his_goal_of_2026_10_06_item_11_the_sides_carry_the_fronts_own_lettering_of_the_name(self):
        """His goal of 2026-10-06, item 11: "Side panels are designed: the product name at a real size plus a brand
        graphic from the concept". 119's front letters its name ("Rose Glaze") as a line of its own words, where the
        record's name is longer ("Rose Glaze Lip Gloss"): the sides carry the front's own lettering of it — its letters,
        stood on end — never the record's name typed in a stand-in face."""
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire.compose import FRONT_TYPE_KEY, SIDE_PANELS, compose_components_graph
        from apps.ire.graph import TextRun
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        shapes = dm.trace_shapes(png, rec, sources=[("Rose Glaze", "the brief's carton front")])
        front = {"shapes": dict(shapes, types=dm.type_sources(shapes["types"], [("Rose Glaze", "the brief's carton front")])),
                 "edge_part": None, "ground": "#F1D5CD"}
        coords = calculate_dieline(DielineInputJSON(template="straight_tuck_end_carton", unit="mm",
                                                    dimensions={"width_mm": 22, "depth_mm": 22, "height_mm": 105},
                                                    print_settings={}, construction={},
                                                    metadata={"product_name": "Rose Glaze", "product_type": "lip gloss"}))
        doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD", map_front=front)
        names = {n.name: n for n, _ in doc.walk()}
        sides = [p for p in doc.metadata[FRONT_TYPE_KEY]["panels"] if p["panel"] in SIDE_PANELS]
        assert [p.get("name") for p in sides] == ["Rose Glaze", "Rose Glaze"] and all(p["name_traced"] for p in sides)
        from apps.ire.compose import SIDE_GAP_MM, SIDE_GRAPHIC_SHARE, _seg_bounds
        for panel in SIDE_PANELS:
            lettering = names["side-name-%s" % panel]
            assert lettering.type == "path", lettering
            # at a real size, standing on end as the front stands it: as tall as the side's column holds, not across it
            x0, y0, x1, y1 = _seg_bounds(lettering.segments)
            side = next(q for q in coords.panels if q.name == panel)
            column = (side.height - 8.0) * (1 - SIDE_GRAPHIC_SHARE) - SIDE_GAP_MM
            assert y1 - y0 > x1 - x0 and y1 - y0 >= 0.6 * column, (x1 - x0, y1 - y0, column)
        assert not any(isinstance(n, TextRun) and n.name.startswith("side-name-") for n in names.values())

    def test_a_display_name_is_set_in_his_brief_words(self):
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        shapes = dm.trace_shapes(png, rec, sources=[("Rose Glaze", "the brief's carton front")])
        name = next(t for t in shapes["types"] if t["part"] == "turned product name")
        assert name["words"] == "Rose Glaze" and name["lettering_set"]["words"] == "Rose Glaze", name.get("lettering_set")
        assert shapes["sources_sha256"] == dm.sources_sha256([("Rose Glaze", "the brief's carton front")])
        bare = dm.trace_shapes(png, rec)
        assert "words" not in next(t for t in bare["types"] if t["part"] == "turned product name")


class HisRuleThreeTests(SimpleTestCase):
    """[His rule 3 for 119 and every design, 2026-10-05: "Try setting the name in the granted display faces (Bagel Fat
    One, Shrikhand, Chango, Fredoka) before tracing it."]"""

    def test_a_name_no_face_matches_is_set_in_the_closest_of_the_four(self):
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        name = next(t for t in dm.trace_shapes(png, rec)["types"] if t["part"] == "turned product name")
        got = name["lettering_set"]
        assert got["state"] == dm.LETTERING_SET and got["face"] in dm.DISPLAY_FACES_FIRST, got.get("why")
        best = max(got["display_faces_measured"], key=lambda row: row[2])
        assert got["face"] == best[0] and got["outline"] == best[2], got["display_faces_measured"]   # the closest
        assert "his rule 3" in got["set_by"] and got["layers"], got["set_by"]

    def test_a_name_none_of_them_can_set_is_traced_with_why(self):
        import copy

        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        rec = copy.deepcopy(rec)
        for part in rec["parts"]:
            if part["name"] == "turned product name":
                part["seen_text"] = "ملمع"                              # letters none of the four faces holds
        name = next(t for t in dm.trace_shapes(png, rec)["types"] if t["part"] == "turned product name")
        got = name["lettering_set"]
        assert got["state"] == dm.LETTERING_TRACED and got["why"], got
        assert not got.get("display_faces_measured"), got.get("display_faces_measured")

    def test_the_granted_face_is_set_as_it_is_drawn_never_grown(self):
        """119 redrawn at 8eda68d set "Rose Glaze" in Bagel Fat One grown 32 px to the picture's weight: the letters ran
        into one another and their counters shut. A granted face is set as the face draws it — never grown, its own
        counters every one kept."""
        from fontTools.ttLib import TTFont

        from apps.ire import font_roles
        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        name = next(t for t in dm.trace_shapes(png, rec)["types"] if t["part"] == "turned product name")
        got = name["lettering_set"]
        assert got["state"] == dm.LETTERING_SET and "never grown" in got["set_by"], got.get("set_by")
        assert got["grown_px"] == [0] * len(got["lines"]), got["grown_px"]
        entry = font_roles.catalogue()[got["face"]]
        inst = font_roles.instance_for(got["face"], "display") if entry.get("variable") else None
        font = TTFont(inst["path"] if inst else entry["path"])
        kern = dm._pair_kerning(font)
        own = 0
        for line in got["lines"]:
            shape = dm._set_line(font, kern, line)
            own += sum(len(p.interiors) for p in (shape.geoms if hasattr(shape, "geoms") else [shape]))
        layer = got["layers"][-1]
        drawn = sum(len(poly) - 1 for poly in layer["cubics"])
        assert own and drawn >= own, (drawn, own)                       # the face's own counters, none shut


class HisRuleFourTests(SimpleTestCase):
    """[His rule 4 for 119 and every design, 2026-10-05: "Smooth the silhouette's edge into clean curves."] A traced
    shape's edge loses the pixels' steps and the picture's jitter and keeps its true corners."""

    @staticmethod
    def _edge(draw):
        import cv2
        im = Image.new("L", (400, 400), 0)
        draw(ImageDraw.Draw(im))
        mask = (np.asarray(im) > 127).astype(np.uint8)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        return max(cnts, key=cv2.contourArea)[:, 0, :] + 0.5

    def test_a_pixel_stepped_circle_comes_out_as_one_clean_curve(self):
        from apps.pipeline.services import concept_design_map as dm
        raw = self._edge(lambda d: d.ellipse((80, 80, 320, 320), fill=255))
        ring = dm._clean_ring(raw)
        r = np.hypot(ring[:, 0] - 200.5, ring[:, 1] - 200.5)
        assert abs(r.mean() - 120.5) < 1.0 and r.max() - r.min() < 1.0, (r.min(), r.max())    # round, not stepped
        d1 = np.diff(np.vstack([ring, ring[:1]]), axis=0)
        turn = np.sign(d1[:, 0] * np.roll(d1[:, 1], -1) - d1[:, 1] * np.roll(d1[:, 0], -1))
        assert len(set(turn[turn != 0].tolist())) == 1, "a wiggle: the edge turns both ways"   # one way all round
        assert len(ring) < len(raw)

    def test_a_rectangle_keeps_its_four_corners(self):
        from apps.pipeline.services import concept_design_map as dm
        raw = self._edge(lambda d: d.rectangle((100, 60, 300, 340), fill=255))
        ring = dm._clean_ring(raw)
        for cx, cy in ((100.5, 60.5), (300.5, 60.5), (300.5, 340.5), (100.5, 340.5)):
            assert np.hypot(ring[:, 0] - cx, ring[:, 1] - cy).min() < 1.5, (cx, cy)

    def test_the_traced_silhouette_is_refit_as_fewer_cubics(self):
        from unittest.mock import patch

        from apps.pipeline.services import concept_design_map as dm
        png, rec = _carton_on_a_cream_ground()
        clean = dm.trace_shapes(png, rec)
        with patch.dict(dm.SHAPE_PARAMS, {"shape_curve_tol_px": dm.SHAPE_PARAMS["curve_tol_px"]}), \
                patch.object(dm, "_clean_ring", lambda pts: dm._smooth(pts, True, dm.SHAPE_PARAMS["shape_smooth_px"])):
            before = dm.trace_shapes(png, rec)
        count = lambda s: sum(len(ring) for shp in s["shapes"] for poly in shp["cubics"] for ring in poly)  # noqa: E731
        assert count(clean) < count(before), (count(clean), count(before))


class HisReviewPointThreeTests(SimpleTestCase):
    """[His review of 119, 2026-10-05, point 3: "One ground all round the carton, taken from the concept's own colour
    (119's concept is a light cream/blush, not peach)."] The ground is the field's colour with the photograph's light
    taken out by half, where the picture's brightest pixels are bright and near neutral."""

    @staticmethod
    def _picture(light, card):
        import cv2
        im = np.zeros((200, 200, 3), np.uint8)
        im[:] = card
        im[:20, :20] = light                                   # the brightest 1 % of the picture: its light
        im[50:150, 50:150] = (86, 17, 27)
        return cv2.imencode(".png", np.ascontiguousarray(im[..., ::-1]))[1].tobytes()

    def test_a_warm_light_is_taken_out_of_the_ground_by_half(self):
        from apps.pipeline.services import concept_design_map as dm
        got = dm.light_corrected(self._picture((254, 247, 223), (242, 212, 193)), "#F2D4C1")
        assert got["photographed"] == "#F2D4C1" and got["light"] == "#FEF7DF", got
        assert got["hex"] == "#F2D7CE", got                     # 119's card: the cream/blush, not the peach
        assert "von Kries" in got["method"] and "why" not in got

    def test_a_neutral_light_leaves_the_ground_as_photographed(self):
        from apps.pipeline.services import concept_design_map as dm
        assert dm.light_corrected(self._picture((255, 255, 255), (242, 212, 193)), "#F2D4C1")["hex"] == "#F2D4C1"

    def test_a_coloured_highlight_is_never_taken_for_the_light(self):
        from apps.pipeline.services import concept_design_map as dm
        got = dm.light_corrected(self._picture((255, 214, 110), (242, 212, 193)), "#F2D4C1")   # a gold foil's shine
        assert got["hex"] == "#F2D4C1" and "too dark or too coloured" in got["why"], got


class HisReviewPointFourTypeTests(SimpleTestCase):
    """[His review of 119, 2026-10-05, point 4: "Set it in the concept's weight (bold, berry)."] A type line's weight is
    read from its strokes, and a thin line's ink from its letters' cores."""

    @staticmethod
    def _line(face):
        import cv2
        from PIL import ImageFont

        from apps.dielines.exporters.counter_display_files import _repo_font
        im = Image.new("RGB", (400, 60), (242, 212, 193))
        ImageDraw.Draw(im).text((10, 18), "LIP GLOSS", font=ImageFont.truetype(_repo_font(face), 20), fill=(86, 17, 27))
        bgr = cv2.GaussianBlur(np.asarray(im)[..., ::-1].copy(), (0, 0), 0.6)    # the picture's own blur
        part = {"name": "LIP GLOSS descriptor", "box": [0.0, 0.0, 1.0, 1.0], "colour": "#7A3A40",
                "seen_text": "LIP GLOSS"}
        return bgr, part

    def test_a_bold_line_reads_bold_and_a_regular_one_regular(self):
        from apps.pipeline.services import concept_design_map as dm
        for face, weight in (("NotoSans-Bold.ttf", "bold"), ("NotoSans-Regular.ttf", "regular")):
            img, part = self._line(face)
            got = dm.trace_type(img, np.full(img.shape[:2], 255, np.uint8), (0, 0, img.shape[1], img.shape[0]), part)
            assert got["weight"] == weight, (face, got.get("stroke_em"))

    def test_a_thin_lines_ink_is_read_from_its_letters_cores(self):
        from apps.pipeline.services import concept_design_map as dm
        img, part = self._line("NotoSans-Regular.ttf")
        got = dm.trace_type(img, np.full(img.shape[:2], 255, np.uint8), (0, 0, img.shape[1], img.shape[0]), part)

        def de(a, b):
            la = np.stack(dm._lab(np.uint8([[[int(a[5:7], 16), int(a[3:5], 16), int(a[1:3], 16)]]])), -1)[0, 0]
            lb = np.stack(dm._lab(np.uint8([[[int(b[5:7], 16), int(b[3:5], 16), int(b[1:3], 16)]]])), -1)[0, 0]
            return float(np.sqrt(((la - lb) ** 2).sum()))
        assert got["ink_read"] == "#7A3A40"
        assert de(got["ink"], "#56111B") < de("#7A3A40", "#56111B"), got["ink"]   # nearer the berry it prints in


class HisReviewPointFiveRimTests(SimpleTestCase):
    """[His review of 119, 2026-10-05, point 5: "The silhouette keeps the concept's details: 119's neck threads under
    the wand are missing."] The pale rim a picture draws round a solid shape is read — its colour, its width — and drawn
    under it; a shape with no rim is drawn as before."""

    @staticmethod
    def _shape(rim, shadow=False):
        import cv2
        im = np.zeros((300, 200, 3), np.uint8)
        im[:] = (193, 210, 241)                                    # the cream ground (BGR)
        if shadow:
            cv2.rectangle(im, (45, 45), (154, 254), (160, 174, 224), -1)   # the edge's shadow outside it (#E0AEA0)
        if rim:
            cv2.rectangle(im, (47, 47), (152, 252), (196, 200, 244), -1)   # a 3 px pale pink rim (#F4C8C4)
        cv2.rectangle(im, (50, 50), (149, 249), (27, 17, 86), -1)          # the berry shape (#56111B)
        part = {"name": "berry silhouette", "box": [0.2, 0.15, 0.8, 0.85], "colour": "#56111B"}
        return im, part

    def test_a_shapes_pale_rim_is_read_and_drawn_under_it(self):
        from apps.pipeline.services import concept_design_map as dm
        img, part = self._shape(rim=True)
        got = dm.trace_shape(img, np.full(img.shape[:2], 255, np.uint8), (0, 0, 200, 300), part, "#F1D2C0", [])
        rim = got["rim"]
        assert 2.0 <= rim["width_px"] <= 3.5 and rim["share"] >= 0.6, rim
        lab = np.stack(dm._lab(np.uint8([[[196, 200, 244]]])), -1)[0, 0]
        ink = np.stack(dm._lab(np.uint8([[[int(rim["ink"][5:7], 16), int(rim["ink"][3:5], 16),
                                            int(rim["ink"][1:3], 16)]]])), -1)[0, 0]
        assert float(np.sqrt(((lab - ink) ** 2).sum())) < 6.0, rim["ink"]
        assert rim["cubics"] and got["box"][0] < 50 / 200 - 1e-3          # the rim is drawn: the box takes it

    def test_the_edges_shadow_outside_the_rim_is_read_as_its_second_band(self):
        from apps.pipeline.services import concept_design_map as dm
        img, part = self._shape(rim=True, shadow=True)
        got = dm.trace_shape(img, np.full(img.shape[:2], 255, np.uint8), (0, 0, 200, 300), part, "#F1D2C0", [])
        outer = got["rim"]["outer"]
        assert outer["width_px"] > got["rim"]["width_px"] and outer["cubics"], got["rim"]
        lab = np.stack(dm._lab(np.uint8([[[160, 174, 224]]])), -1)[0, 0]
        ink = np.stack(dm._lab(np.uint8([[[int(outer["ink"][5:7], 16), int(outer["ink"][3:5], 16),
                                            int(outer["ink"][1:3], 16)]]])), -1)[0, 0]
        assert float(np.sqrt(((lab - ink) ** 2).sum())) < 6.0, outer["ink"]

    def test_a_shape_with_no_rim_is_drawn_as_before(self):
        from apps.pipeline.services import concept_design_map as dm
        img, part = self._shape(rim=False)
        got = dm.trace_shape(img, np.full(img.shape[:2], 255, np.uint8), (0, 0, 200, 300), part, "#F1D2C0", [])
        assert "rim" not in got, got.get("rim")


class HisReviewPointFourShapeBoxTests(SimpleTestCase):
    """[His review of 119, 2026-10-05, point 4: "Nothing inside the safe margin".] A shape's box is the whole extent it
    draws — its rim's outer band and every point of its cubics, control points too — so a front fitted inside the safe
    margin by its parts' boxes leaves nothing of it outside (119's shadow band ran 0.12 mm past the margin when the box
    was the traced outline's own)."""

    def test_a_shapes_box_holds_every_point_it_draws(self):
        from apps.pipeline.services import concept_design_map as dm
        img, part = HisReviewPointFiveRimTests._shape(rim=True, shadow=True)
        got = dm.trace_shape(img, np.full(img.shape[:2], 255, np.uint8), (0, 0, 200, 300), part, "#F1D2C0", [])
        x0, y0, x1, y1 = got["box"]
        for cubics in (got["cubics"], got["rim"]["cubics"], got["rim"]["outer"]["cubics"]):
            pts = [seg[i:i + 2] for poly in cubics for ring in poly for seg in ring for i in range(0, len(seg), 2)]
            assert all(x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6 for x, y in pts)



class HisFinding122FlatMotifTests(SimpleTestCase):
    """[His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), A and B.] The motif traced from a flat redraw as OUTLINES — the stroke's own
    thick-and-thin kept — never from the photo; checked whole; the colours read from the redraw, the photo's lighting
    taken off, and checked by ΔE."""

    @staticmethod
    def _flat(**kw):
        from apps.pipeline.tests.test_wiring_check import FLAT_122, flat_art
        return flat_art(*FLAT_122, **kw)

    def test_a_flat_redraw_is_traced_as_filled_outlines_in_its_own_ink_on_its_own_ground(self):
        import re

        from apps.pipeline.services import flat_motif as fm
        from apps.pipeline.tests.test_wiring_check import FLAT_122
        traced = fm.trace_flat(self._flat(), [0.0, 0.0, 1.0, 0.87], (54.98, 120.0))
        assert traced["state"] == fm.TRACED and traced["whole"]["ok"], traced.get("why")
        assert fm.delta_e(traced["ink"], FLAT_122[0]) < 3.0 and fm.delta_e(traced["ground"], FLAT_122[1]) < 3.0
        paths = re.findall(r"<path ", traced["outlines"]["svg"])
        assert len(paths) >= 1 and "fill" in traced["outlines"]["svg"]          # filled outlines, never centre-lines
        assert traced["box"] == [0.0, 0.0, 1.0, 0.87] and 0.0 < traced["ink_share"] < 0.5
        assert 0.05 < traced["stroke_mm"] < 1.0, traced["stroke_mm"]

    def test_the_composer_draws_it_as_its_filled_outlines_never_strokes_from_the_photo(self):
        from apps.ire import compose_container as cc
        from apps.ire.graph import ClosePath, Group, LineTo, MoveTo, Path
        from apps.pipeline.services import flat_motif as fm
        traced = fm.trace_flat(self._flat(), [0.0, 0.0, 1.0, 0.87], (54.98, 120.0))
        line = {"part": "red hairline rose and leaf engraving all-over", "ink": "#BA5C5D", "width": 0.003, "gold": False,
                "strokes": [{"points": [[0.1, 0.1], [0.5, 0.5]], "closed": False}], "flat": traced}
        outline = [MoveTo(x=0.0, y=0.0), LineTo(x=54.98, y=0.0), LineTo(x=54.98, y=120.0), LineTo(x=0.0, y=120.0),
                   ClosePath()]
        backbone = type("Backbone", (), {"width_mm": 54.98, "height_mm": 120.0, "silhouette": outline})()
        zone = {"zone_id": "z_front", "x": 0.0, "y": 0.0, "width": 54.9, "height": 99.9}
        group, _places, record = cc._map_front_group({"shapes": {"lines": [line]}}, zone, backbone, 1.0, 0.0, 0.0)
        motif = next(c for c in group.children[0].children if c.name.startswith("lineart-map-0 "))
        assert isinstance(motif, Group) and [p.name for p in motif.children] == ["lineart-map-0-outlines"]
        drawn = motif.children[0]
        assert isinstance(drawn, Path) and drawn.fill is not None and drawn.stroke is None
        assert drawn.fill.color.to_hex().upper() == traced["ink"].upper() and len(drawn.segments) > 50
        undrawn = dict(line, flat=None, undrawn="no flat redraw of it is kept — the concept photo is never traced")
        group, _p, _r = cc._map_front_group({"shapes": {"lines": [undrawn]}}, zone, backbone, 1.0, 0.0, 0.0)
        assert not [c for c in group.children[0].children if c.name.startswith("lineart-map-")]

    def test_a_motif_in_fragments_is_refused_by_name(self):
        from apps.pipeline.services import flat_motif as fm
        traced = fm.trace_flat(self._flat(broken=True), [0.0, 0.0, 1.0, 0.87], (54.98, 120.0))
        assert traced["state"] == fm.REFUSED and not traced["whole"]["ok"], traced["whole"]
        assert "broken" in traced["why"] or "specks" in traced["why"], traced["why"]

    def test_the_photos_lighting_is_taken_off_and_each_colour_checked_by_delta_e(self):
        from apps.pipeline.services import flat_motif as fm
        gain = fm.lit_gain("#F7E9E4", "#F6DCE3")                 # 122's photo body, a flat redraw's blush ground
        assert fm.delta_e(fm.corrected("#F7E9E4", gain), "#F6DCE3") < 1.0
        assert fm.delta_e("#D55B64", "#D55B64") == 0.0
        assert abs(fm.delta_e("#D55B64", "#BA5C5D") - fm.delta_e("#BA5C5D", "#D55B64")) < 1e-9
        assert fm.delta_e("#C2185B", "#BA5C5D") > fm.COLOUR_DE_MAX         # raspberry against the photo's brown-red
        check = fm.colour_check({"body": "#F7E9E4", "cap": "#EDC3BF", "type": "#D55B64"},
                                {"body": ("#F6DCE3", "flat"), "cap": ("#EDC3BF", "photo")})
        assert check["roles"]["cap"]["state"] == "HELD" and check["roles"]["type"]["state"] == "NOT_IN_THE_CONCEPT"
        assert check["roles"]["body"]["delta_e"] > 0 and check["limit_delta_e"] == fm.COLOUR_DE_MAX
        drift = fm.colour_check({"line art": "#BA5C5D"}, {"line art": ("#C2185B", "flat")})
        assert drift["codes"] and drift["codes"][0].startswith(fm.COLOUR_DRIFTS)


def test_goal_1010_a_four_cornered_lid_traced_is_kept_on_the_record_it_is_written_to():
    """[124, 2026-10-10: he chose its concept at Gate 1 and the design stopped — "Object of type float32 is not JSON
    serializable".] A palette's lid traced four-cornered — square or a rounded rectangle — is written to the design's
    record after Gate 1: every measure of its trace a plain number the record holds, never numpy's float32."""
    import io
    import json

    from PIL import Image, ImageDraw

    from apps.pipeline.services import concept_outline as co

    def lid(w, h, r, size=(640, 960)):
        img = Image.new("RGB", size, (236, 230, 226))
        cx, cy = size[0] // 2, size[1] // 2
        ImageDraw.Draw(img).rounded_rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], radius=r,
                                              fill=(214, 120, 150))
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    for w, h, r, kind in ((420, 300, 26, co.ROUNDED_RECT), (400, 400, 30, co.SQUARE)):
        t = co.trace_plan(lid(w, h, r))
        assert (t["state"], t["kind"]) == (co.TRACED_FROM_CONCEPT, kind), t
        assert type(t["corner_share"]) is float and type(t["quad"]["corner_share"]) is float, t
        assert json.loads(json.dumps(t))["quad"] == t["quad"]                   # the record holds it whole


# ---- [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "ONE
# ---- ENGINE: palettes and compacts run the same map-first path as the tube and carton"] the lid stood square

def _palette_png(size=(640, 960), lid=(400, 260), ground=(70, 70, 74)):
    """A palette's lid as a concept draws it from above, a little off square: a pink lid with a teal arch and a dark
    rose on it, its four corners taken through a mild perspective, on a dark ground."""
    import cv2
    import numpy as np
    w, h = lid
    flat = np.zeros((h, w, 3), np.uint8)
    flat[:] = (196, 182, 236)                                         # pink (BGR)
    cv2.ellipse(flat, (w // 2, h), (w // 4, int(h * 0.7)), 0, 180, 360, (190, 200, 120), 6)   # the teal arch
    cv2.circle(flat, (w // 5, int(h * 0.7)), 24, (120, 60, 170), -1)                       # a rose
    cx, cy = size[0] // 2, size[1] // 2
    dst = np.float32([[cx - w / 2 + 6, cy - h / 2], [cx + w / 2 - 4, cy - h / 2 + 3], [cx + w / 2, cy + h / 2],
                      [cx - w / 2, cy + h / 2 - 2]])
    warp = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), dst)
    canvas = np.zeros((size[1], size[0], 3), np.uint8)
    canvas[:] = ground
    lidded = cv2.warpPerspective(flat, warp, size, flags=cv2.INTER_CUBIC)
    inside = cv2.warpPerspective(np.full((h, w), 255, np.uint8), warp, size) > 127
    canvas[inside] = lidded[inside]
    ok, png = cv2.imencode(".png", canvas)
    return png.tobytes()


def test_goal_1011_lid_picture_a_four_cornered_lid_seen_off_square_is_stood_square():
    """[His test blocker on design 124, (2)] A palette's lid pictured a little off square is cut from its ground and
    stood square at the picture's own resolution: its sides' own lengths (the lid's aspect kept), nothing of the ground
    left at its corners, its arch and rose where the lid prints them — the picture the map reads and the redraw is made
    from."""
    import cv2
    import numpy as np

    from apps.pipeline.services import concept_outline as co
    png = _palette_png()
    rec = co.lid_picture(png)
    assert (rec["state"], rec["shape"]) == (co.LID_STRAIGHTENED, "rect"), rec.get("reason")
    w, h = rec["size_px"]
    assert abs(w / h - 400 / 260) < 0.04 and abs(w - 400) < 16, rec["size_px"]
    lid = cv2.imdecode(np.frombuffer(rec["png"], np.uint8), cv2.IMREAD_COLOR)
    assert lid.shape[:2] == (h, w)
    for x, y in ((8, 8), (w - 9, 8), (w - 9, h - 9), (8, h - 9)):      # every corner the lid's pink, never the ground
        assert np.abs(lid[y, x].astype(int) - (196, 182, 236)).max() < 30, (x, y, lid[y, x])
    rose = lid[int(h * 0.7) - 4:int(h * 0.7) + 4, w // 5 - 4:w // 5 + 4].reshape(-1, 3).mean(axis=0)
    assert np.abs(rose - (120, 60, 170)).max() < 30, rose                # the rose where the lid prints it
    assert rec["source_sha256"] and rec["lid_sha256"] and co.lid_picture(png)["lid_sha256"] == rec["lid_sha256"]


def test_goal_1011_lid_picture_a_round_lid_seen_tilted_is_stood_round_and_nothing_else_is_read():
    """A round compact seen tilted — its rim an ellipse — stood round: the ellipse taken to the circle of its long axis,
    the cream disc as round as it is wide, everything outside its rim said by one colour of its own, never the lid."""
    import cv2
    import numpy as np

    from apps.pipeline.services import concept_outline as co
    rec = co.lid_picture(_lid_png((250, 210), 25.0))
    assert (rec["state"], rec["shape"]) == (co.LID_STRAIGHTENED, "round"), rec.get("reason")
    w, h = rec["size_px"]
    assert w == h and abs(w - 500) < 20, rec["size_px"]
    lid = cv2.imdecode(np.frombuffer(rec["png"], np.uint8), cv2.IMREAD_COLOR)
    assert tuple(int(v) for v in lid[2, 2]) == co.LID_OUTSIDE                # outside the rim: never the lid
    cream = np.all(np.abs(lid.astype(int) - (228, 238, 246)) < 18, axis=2)
    ys, xs = np.nonzero(cream)
    assert abs((xs.max() - xs.min()) / (ys.max() - ys.min()) - 1.0) < 0.04   # round, not the tilted ellipse
    assert rec["from_px"]["axes"][0] > rec["from_px"]["axes"][1]


def test_goal_1011_lid_picture_no_lid_traced_is_said_never_guessed():
    """A picture with no lid its trace can find is NOT straightened, said by the trace's own reason — never a picture
    guessed for the map to read."""
    import io

    from apps.pipeline.services import concept_outline as co
    buf = io.BytesIO()
    Image.new("RGB", (640, 960), (226, 214, 200)).save(buf, "PNG")
    rec = co.lid_picture(buf.getvalue())
    assert rec["state"] == co.LID_NOT_STRAIGHTENED and "png" not in rec and rec["reason"].startswith("its lid was not")


# ---- [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (6): "The script
# ---- name: set in the granted face closest to the concept's script, never wide-spaced capitals."]

def test_goal_1011_script_a_fine_script_is_measured_in_every_face_as_it_draws_and_set_in_the_closest():
    """124's own "Enchanted Rose", its letters cut from its concept's lid (fixtures_124/name_mask_153.png): FINE — their
    stroke 1.4% of their height — so every granted face is measured finely, each as it draws, and the name set in the
    closest, Great Vibes; the shortlist of six the coarse measure picks, grown to the picture's weight (as before), set
    it in another face — the control that this is what changed."""
    import os
    from unittest import mock

    import cv2

    from apps.pipeline.services import concept_design_map as dm
    here = os.path.join(os.path.dirname(__file__), "fixtures_124", "name_mask_153.png")
    body = cv2.imread(here, cv2.IMREAD_GRAYSCALE) > 0
    got = dm._set_lettering(body, 1, "Enchanted Rose", dict(dm.DISPLAY_REACH), {}, lambda p: p)
    assert (got["state"], got["face"]) == (dm.LETTERING_SET, "GreatVibes-Regular"), got["faces_measured"][:4]
    assert got["measured_finely"].startswith("every face") and len(got["faces_measured"]) >= 40
    with mock.patch.dict(dm.SHAPE_PARAMS, {"lettering_fine_stroke": 0.0}):
        before = dm._set_lettering(body, 1, "Enchanted Rose", dict(dm.DISPLAY_REACH), {}, lambda p: p)
    assert before["face"] != "GreatVibes-Regular" and before["measured_finely"].startswith("the six closest")


def test_goal_1011_script_bold_letters_keep_the_quick_shortlist():
    """Bold letters — a brush script's — are measured as before: the six closest at the coarse measure, grown to the
    picture's weight; set in their own face."""
    import numpy as _np
    from PIL import ImageFont

    from apps.ire import font_roles
    from apps.pipeline.services import concept_design_map as dm
    path = font_roles.catalogue()["Lobster-Regular"]["path"]
    im = Image.new("L", (900, 220), 0)
    ImageDraw.Draw(im).text((20, 20), "Rose Velvet", font=ImageFont.truetype(path, 140), fill=255)
    body = _np.array(im) > 127
    got = dm._set_lettering(body, 1, "Rose Velvet", dict(dm.DISPLAY_REACH), {}, lambda p: p)
    assert got["measured_finely"].startswith("the six closest") and got["face"] == "Lobster-Regular", got["faces_measured"][:3]


def test_goal_1011_one_engine_a_compact_lid_is_read_into_its_map_as_a_cartons_front_is():
    """[His test blocker on design 124, 2026-10-11, (2): "ONE ENGINE: palettes and compacts run the same map-first path as
    the tube and carton"] A palette's lid, stood square, read into its design map in one call — the whole picture its
    face — naming its ground, its illustration and its lines of type, each with its box as fractions of the lid and its
    colour from the lid's own pixels; a kind outside a lid's own left out by name; kept for THIS lid picture only."""
    import io as _io
    import json as _json
    import types as _types

    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import concept_outline as co
    lid = co.lid_picture(_palette_png())
    assert lid["state"] == co.LID_STRAIGHTENED
    w, h = lid["size_px"]
    seen = {}
    answer = {"parts": [
        {"kind": "field", "name": "pink lid ground", "box": [0, 0, 2 * w, 2 * h]},
        {"kind": "illustration", "name": "teal arch", "box": [int(0.45 * w), int(0.55 * h), int(1.55 * w), 2 * h]},
        {"kind": "illustration", "name": "dark rose", "box": [int(0.25 * w), int(1.2 * h), int(0.55 * w), int(1.6 * h)]},
        {"kind": "type", "name": "the name", "box": [int(0.6 * w), int(0.2 * h), int(1.4 * w), int(0.45 * h)],
         "seen_text": "Enchanted Rose", "lettering": "script", "spacing": "normal", "rotation": 0},
        {"kind": "closure", "name": "a clasp", "box": [0, 0, 10, 10]}], "light": [], "notes": "stand-in"}

    def call(system, content, **kw):
        import base64
        pic = Image.open(_io.BytesIO(base64.b64decode(content[0]["source"]["data"])))
        seen.update(size=pic.size, system=system, operation=kw.get("operation"))
        return _types.SimpleNamespace(usage=_types.SimpleNamespace(input_tokens=2400, output_tokens=400),
                                      content=[_types.SimpleNamespace(type="text", text=_json.dumps(answer))])
    rec = dm.read_lid_parts(None, lid["png"], call=call)
    assert seen["system"] == dm.LID_PARTS_SYSTEM and seen["operation"] == dm.PARTS_OPERATION and seen["size"] == (2 * w, 2 * h)
    assert (rec["state"], rec["read"], rec["parts_prompt_version"]) == (dm.MAP_READ, dm.LID_READ, dm.LID_PARTS_PROMPT_VERSION)
    assert rec["face_box_px"] == [0, 0, w, h] and float(rec["cost"]["usd"]) > 0
    parts = {p["name"]: p for p in rec["parts"]}
    assert set(parts) == {"pink lid ground", "teal arch", "dark rose", "the name"}
    assert parts["the name"]["spacing"] == "normal" and parts["the name"]["lettering"] == "script"
    assert any("a clasp" in p and "no declared kind" in p for p in rec["problems"]) or any(
        "closure" in p for p in rec["problems"]), rec["problems"]
    pink = parts["pink lid ground"]["colour"]
    assert max(abs(int(pink[i:i + 2], 16) - v) for i, v in zip((1, 3, 5), (236, 182, 196))) <= 12, pink
    assert dm.held_lid_parts(rec, lid["png"]) == rec
    assert dm.held_lid_parts(rec, co.lid_picture(_palette_png(lid=(380, 260)))["png"]) is None
    assert dm.held_carton_parts(rec, lid["png"]) is None                      # a lid's map is never a carton's


def test_goal_1011_one_engine_a_lids_illustration_is_drawn_only_where_its_art_traced():
    """The lid's illustration is drawn whole by its art: a part of that kind counts as drawn only where the art traced it
    (``shapes["illustrations"]``), and is said undrawn otherwise — never passed by default."""
    from apps.pipeline.services import concept_design_map as dm
    record = {"face_box_px": [0, 0, 400, 260], "parts": [
        {"kind": "field", "name": "pink lid ground", "box": [0, 0, 1, 1]},
        {"kind": "illustration", "name": "teal arch", "box": [0.2, 0.3, 0.8, 1.0]}]}
    undrawn = dm.undrawn_parts(record, {"state": dm.SHAPES_TRACED}, [])
    assert [(u["kind"], u["name"]) for u in undrawn] == [("illustration", "teal arch")]
    drawn = dm.undrawn_parts(record, {"state": dm.SHAPES_TRACED, "illustrations": [{"part": "teal arch"}]}, [])
    assert drawn == []


def test_goal_1011_lid_picture_a_lid_with_rounded_corners_is_cut_where_its_straight_sides_meet():
    """[His test blocker on design 124, 2026-10-11, (2): "Fix for every palette and compact"] a lid whose corners are
    rounded a fifth of its short side — too round for four corners to close at the finest tolerances, and so stopped as
    "no rim the edges support" — seen a little off square: cut where its straight sides meet, each corner within 2 % of
    its short side of the true one, stood square at its sides' own lengths; its outline marked rounded."""
    import cv2
    import numpy as _np

    from apps.pipeline.services import concept_outline as co
    w, h, r = 440, 300, 60
    flat = _np.full((h, w, 3), (120, 60, 200), _np.uint8)
    canvas = _np.full((900, 700, 3), (236, 231, 226), _np.uint8)
    rim = _np.zeros((h, w), _np.uint8)
    cv2.rectangle(rim, (r, 0), (w - r, h), 1, -1)
    cv2.rectangle(rim, (0, r), (w, h - r), 1, -1)
    for cx, cy in ((r, r), (w - r, r), (r, h - r), (w - r, h - r)):
        cv2.circle(rim, (cx, cy), r, 1, -1)
    true = _np.float32([[130, 300], [574, 306], [570, 604], [128, 598]])         # a little off square
    warp = cv2.getPerspectiveTransform(_np.float32([[0, 0], [w, 0], [w, h], [0, h]]), true)
    inside = cv2.warpPerspective(rim * 255, warp, (700, 900)) > 127
    canvas[inside] = cv2.warpPerspective(flat, warp, (700, 900))[inside]
    png = cv2.imencode(".png", canvas)[1].tobytes()
    plan = co.trace_plan(png)
    assert plan["state"] == co.TRACED_FROM_CONCEPT and plan["quad"]["rounded"] is True, plan.get("detail")
    got = _np.float32(plan["quad"]["corners_px"]) / co._read(png)[1]         # read small, as lid_picture reads them
    assert _np.abs(got - true).max() < 0.02 * h, got
    lid = co.lid_picture(png, plan)
    assert lid["state"] == co.LID_STRAIGHTENED and lid["shape"] == "rect"
    assert abs(lid["size_px"][0] - 444) < 8 and abs(lid["size_px"][1] - 298) < 8, lid["size_px"]


def test_goal_1011_one_engine_a_briefs_front_copy_ends_where_its_next_label_begins():
    """[His test blocker on design 124, 2026-10-11] 124's brief wraps its lid's front copy over two lines and opens the
    next with its own label ("Shade names (row by row, left to right):"): its front copy ends at the full stop before it
    — its size, "27 g ℮ 0.95 oz", read as his size — never run on into the shade names."""
    from apps.pipeline.services import concept_design_map as dm
    brief = ('Lid front copy: BBROSE logo, "Enchanted Rose", "Eyeshadow Palette /\nباليت ظلال العيون", "18 shades", '
             '27 g ℮ 0.95 oz.\nShade names (row by row, left to right):\nRow 1: Petal Frost, Moonlit Rose.\n')
    assert dm.brief_front_copy(brief) == ["BBROSE logo", "Enchanted Rose", "Eyeshadow Palette / باليت ظلال العيون",
                                          "18 shades", "27 g ℮ 0.95 oz"]
    assert dm.brief_size(brief) == ("27 g ℮ 0.95 oz", dm.BRIEF_SIZE_FRONT)
    # as his New design form wrote it, its lines ending "\r\n" — read alike (the live brief lost its size so)
    assert dm.brief_front_copy(brief.replace("\n", "\r\n"))[-1] == "27 g ℮ 0.95 oz"
    assert dm.brief_size(brief.replace("\n", "\r\n")) == ("27 g ℮ 0.95 oz", dm.BRIEF_SIZE_FRONT)
    # its other ends stand: a blank line, the next "... copy:"
    assert dm.brief_front_copy('Front copy: "Rose Glow", "Lip oil"\n\nBack copy: x') == ["Rose Glow", "Lip oil"]
    assert dm.brief_front_copy('Front copy: "Rose Glow",\n"10 ml"\nBack copy: x') == ["Rose Glow", "10 ml"]


def test_goal_1011_script_124s_title_read_on_the_real_path_is_set_in_great_vibes():
    """[His test blocker on design 124, 2026-10-11, (6): "set in the granted face closest to the concept's script"] 124's
    own lid (fixtures_124: its concept stood square, its lid's map as read on record), traced by the map's own tracer:
    its fine gold script read as its ink — the ring's reading found only the four loops its gold ring encloses and set
    Chango (0.10) — and set in Great Vibes, every granted face measured as it draws. Measured through the real path, as
    026f702's test was not (its mask cut by hand)."""
    import json
    import os

    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import concept_outline as co
    here = os.path.join(os.path.dirname(__file__), "fixtures_124")
    with open(os.path.join(here, "concept_153.png"), "rb") as fh:
        lid = co.lid_picture(fh.read())
    with open(os.path.join(here, "lid_map_153.json"), encoding="utf-8") as fh:
        read = json.load(fh)
    shapes = dm.trace_shapes(lid["png"], read, [("Enchanted Rose", "the product's name on the record")])
    title = next(t for t in shapes["types"] if t["part"] == "Enchanted Rose title")
    assert title["lettering_set"]["state"] == "SET" and title["lettering_set"]["face"] == "GreatVibes-Regular"
    assert "every face" in title["lettering_set"]["measured_finely"]
    ringed = title["lettering_layers"]["set"]
    assert title["lettering_set"]["iou"] > ringed["iou"] and title["lettering_set"]["outline"] > ringed["outline"]


def _cartouche_carton(broken_flower: bool = False) -> tuple:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C.] 132's front, drawn here: a cream panel, a gold frame round
    its cartouche — the read naming the frame a "rule" the size of the cartouche, in the blue of the tiles beside it, as
    132's second read did — a two-ink flower in the cartouche read as a motif, and a blue emblem read as a shape; its map
    from a stand-in read in the read's own pixels (nothing paid). ``(png, record)``."""
    from PIL import Image, ImageDraw

    from apps.pipeline.services import concept_design_map as dm
    im = Image.new("RGB", (512, 768), (80, 80, 80))
    d = ImageDraw.Draw(im)
    d.rectangle((100, 100, 420, 700), fill=(240, 236, 228))                      # the panel
    d.rectangle((150, 200, 370, 560), outline=(200, 160, 60), width=3)           # the gold frame
    d.ellipse((230, 250, 290, 310), outline=(30, 60, 120), width=3)               # the flower, drawn in line: its ring
    d.line([(240, 300), (260, 258), (280, 300), (240, 300)], fill=(30, 60, 120), width=3)   # … and its petal
    if broken_flower:
        for x in range(160, 360, 26):
            d.rectangle((x, 620, x + 10, 630), fill=(30, 60, 120))
    else:
        d.rectangle((180, 600, 340, 650), fill=(30, 60, 120))                    # the emblem under the cartouche
    buf = io.BytesIO()
    im.save(buf, "PNG")
    png = buf.getvalue()
    answer = {"face": [200, 200, 840, 1400], "parts": [
        {"kind": "field", "name": "cream ground", "box": [200, 200, 840, 1400]},
        {"kind": "window", "name": "central cartouche", "box": [310, 410, 730, 1110]},
        {"kind": "rule", "name": "gold cartouche frame", "box": [310, 410, 730, 1110], "finish": "gold foil"},
        {"kind": "motif", "name": "lily flower emblem", "box": [456, 496, 584, 624], "finish": "gold foil"},
        {"kind": "shape", "name": "blue emblem", "box": [350, 1190, 690, 1310]}],
        "light": [{"kind": "background", "box": [0, 0, 1024, 1536]}], "notes": "stand-in"}
    rec = dm.carton_record(png, answer, model="stand-in", cost={"usd": "0.000000", "calls": 0})
    # the read's misreading of the frame's ink, as 132's: the tiles' blue
    rec["parts"] = [dict(p, colour="#213C74") if p["name"] == "gold cartouche frame" else p for p in rec["parts"]]
    return png, rec


def test_his_review_132_c_a_rule_the_size_of_its_cartouche_is_traced_as_its_frame_and_the_window_is_what_it_holds():
    """[His review of 127, 130, 131 and 132, 2026-10-15, C — the designer's eye on 132: "no gold inner frame round the
    label"; "the label panel drawn LANDSCAPE where the concept's is portrait".] A rule the read boxes round a box both
    ways is the frame it is: traced as a four-sided frame in the picture's gold — never one straight gold line along
    the cartouche's top — and the cartouche it rings is what the frame holds, out to the frame's own line, never the
    read's own box sticking out past it. And a motif printed ON the cartouche is traced on it, never refused as lying
    in "nothing of the product outside its other parts"."""
    from apps.pipeline.services import concept_design_map as dm
    png, rec = _cartouche_carton()
    shapes = dm.trace_shapes(png, rec)
    assert shapes["state"] == dm.SHAPES_TRACED, shapes
    assert not shapes.get("rules"), shapes.get("rules")                       # never a straight line along its top
    frame, = shapes["frames"]
    assert frame["shape"] == "quad" and frame["gold"] and frame["window"] == "central cartouche", frame
    fx0, fy0, fx1, fy1 = frame["box"]                                         # 150..370 x 200..560 of the 320 x 600 panel
    assert abs(fx0 - 50 / 320) < 0.03 and abs(fx1 - 270 / 320) < 0.03 and abs(fy0 - 100 / 600) < 0.03, frame["box"]
    assert abs(fy1 - 460 / 600) < 0.03, frame["box"]
    window, = shapes["windows"]
    assert window["box"] == frame["box"]                                      # what the frame holds, portrait as drawn
    assert (window["box"][2] - window["box"][0]) * 320 < (window["box"][3] - window["box"][1]) * 600
    assert any(line["part"] == "lily flower emblem" for line in shapes.get("lines") or []), shapes["problems"]


def test_his_review_132_c2_a_shape_traced_whole_agrees_with_its_picture_and_one_broken_is_measured_broken():
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (2): "a motif that can't be traced cleanly (132's side and
    flap flower, which looks like a fidget spinner) is redrawn flat and traced again".] A solid motif traced from the
    photo is measured against the picture it was traced from (``flat_motif.shape_whole``): the emblem traced whole agrees
    with it; the same emblem printed in pieces is broken into more pieces than SHAPE_WHOLE allows; and a trace that
    loses half of what the picture prints agrees on too little of its ink — each said in words."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    png, rec = _cartouche_carton()
    emblem = next(sh for sh in dm.trace_shapes(png, rec)["shapes"] if sh["part"] == "blue emblem")
    whole = fm.shape_whole(png, rec, emblem)
    assert whole["ok"] and whole["agreement"] >= 0.95 and whole["pieces"] == [1], whole
    bits_png, bits_rec = _cartouche_carton(broken_flower=True)
    bits = next(sh for sh in dm.trace_shapes(bits_png, bits_rec)["shapes"] if sh["part"] == "blue emblem")
    broken = fm.shape_whole(bits_png, bits_rec, bits)
    assert not broken["ok"] and max(broken["pieces"]) > fm.SHAPE_WHOLE["pieces_max"], broken
    assert "pieces" in broken["why"]
    x0, y0, x1, y1 = emblem["box"]
    half = dict(emblem, cubics=[[[[x0, y0], [x0, y1, x0, y1, x0, y1], [(x0 + x1) / 2, y1, (x0 + x1) / 2, y1,
                                                                        (x0 + x1) / 2, y1],
                                  [(x0 + x1) / 2, y0, (x0 + x1) / 2, y0, (x0 + x1) / 2, y0],
                                  [x0, y0, x0, y0, x0, y0]]]])
    lost = fm.shape_whole(png, rec, half)
    assert not lost["ok"] and lost["agreement"] < fm.SHAPE_WHOLE["agree_min"] and "agrees" in lost["why"], lost
    assert fm.shape_whole(b"", rec, emblem)["measured"] is False                # nothing to measure: kept as drawn
