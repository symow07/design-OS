"""[His second goal of 2026-10-06 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c34a518), item 2: "TOP-TIER DIELINES ...
Every dieline must be professional, printable and foldable, and respect every rule of the trade ... A FAST FOLD CHECK
INSIDE THE SYSTEM: pure geometry, no Blender, no 3D renders, under a second, run on every dieline before I see it".]

Version 1.4 of the straight and the reverse tuck end, drawn to apps/dielines/docs/TRADE_RULES.md, and the fold check
(apps/dielines/geometry/fold_check.py): each rule read off the drawn die; the check passing every size the schema
admits, failing 119's 1.3 die where it does not fold, and naming each planted defect; the die set beside the professional
reference committed with the research (Box Blanks, its terms in docs/research/refs/TERMS.md)."""
import os
import re
import time

import pytest
from shapely.geometry import LineString, Point

from apps.dielines import registry
from apps.dielines.geometry import fold_check as FC
from apps.dielines.geometry import trade_tuck as TT
from apps.dielines.geometry.coordinates import DielineCoordinates
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON

REFS = os.path.join(os.path.dirname(__file__), "..", "docs", "research", "refs")
T = 0.45


def _params(template="reverse_tuck_end_carton", version="1.4", w=22.0, d=22.0, h=105.0, glue=12.0, t=T):
    return DielineInputJSON(
        template=template, template_version=version, unit="mm",
        dimensions={"width_mm": w, "depth_mm": d, "height_mm": h},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": glue, "board_thickness_mm": t, "thickness_compensation": True},
        metadata={"product_name": "Rose Glaze Lip Gloss", "product_type": "lip gloss"})


def _comp(coords, name):
    return dict(coords.components)[name]


# ---- the styles: ECMA's topology, named as the trade names it (S1, S2, S5) ------------------------------------------

@pytest.mark.parametrize("template,top,bottom,ecma", [
    ("straight_tuck_end_carton", "back", "back", "A20.20.01.01"),
    ("reverse_tuck_end_carton", "back", "front", "A20.20.03.01"),
])
def test_each_style_hangs_its_tucks_where_ecma_codes_it(template, top, bottom, ecma):
    coords = calculate_dieline(_params(template))
    names = [n for n, _p in coords.components]
    assert "top-%s-tuck" % top in names and "bottom-%s-tuck" % bottom in names
    assert coords.derived["ecma_code"] == ecma and coords.derived["template_version"] == "1.4"
    assert [p.name for p in coords.panels] == ["glue_tab", "back", "side_left", "front", "side_right"]
    assert sum(1 for n in names if n.endswith("-dust")) == 4


def test_every_design_draws_the_reverse_tuck_end_at_1_4():
    """The opposed layout of the house's approved reference, named as the trade names it; 1.0–1.3 kept for history."""
    from apps.pipeline.agents.dieline_agent import TEMPLATE_TYPE
    assert TEMPLATE_TYPE == "reverse_tuck_end_carton" and registry.print_ready_version(TEMPLATE_TYPE) == "1.4"
    defn = registry.resolve(TEMPLATE_TYPE, "1.4")
    assert defn.closure_type == registry.CLOSURE_REVERSE_TUCK and "inside" in defn.dimension_semantics["width_mm"]
    assert registry.resolve("straight_tuck_end_carton", "1.4").closure_type == registry.CLOSURE_STRAIGHT_TUCK
    for version in ("1.0", "1.1", "1.2", "1.3"):
        assert calculate_dieline(_params("straight_tuck_end_carton", version)).derived["template_version"] == version


# ---- the rules, read off the drawn die ---------------------------------------------------------------------------

def test_the_sizes_are_the_inside_and_every_crease_sits_one_caliper_out():
    """D1–D5, T7: inside W × D × H; crease-to-crease (W+t) × (D+t) × (H+t) on every panel; outside less inside 2t."""
    coords = calculate_dieline(_params(w=30.0, d=20.0, h=110.0))
    widths = {p.name: p.width for p in coords.panels}
    assert widths["back"] == widths["front"] == pytest.approx(30.45) and widths["side_left"] == widths[
        "side_right"] == pytest.approx(20.45)
    assert coords.body_bottom_y - coords.body_top_y == pytest.approx(110.45)
    assert coords.dimensions.inner == (30.0, 20.0, 110.0) and coords.dimensions.outer == (30.9, 20.9, 110.9)


def test_the_lid_spans_the_opening_and_hinges_one_caliper_outside_the_dust_flaps():
    """K1, K3, T3, T4: hinge to tuck fold = the side panel's crease width; the hinge t further out than the dust
    flaps'; the lid the panel less t, inset t/2 each side."""
    coords = calculate_dieline(_params())
    for tuck in coords.derived["tucks"]:
        assert abs(tuck["fold_y"] - tuck["hinge_y"]) == pytest.approx(22.45)
        dust_hinge = coords.body_top_y if tuck["end"] == "top" else coords.body_bottom_y
        assert abs(tuck["hinge_y"] - dust_hinge) == pytest.approx(T)
        assert tuck["x_r"] - tuck["x_l"] == pytest.approx(22.0)
        hinge = [f for f in coords.fold_lines if f[1] == f[3] == pytest.approx(tuck["hinge_y"])]
        assert hinge and hinge[0][2] - hinge[0][0] == pytest.approx(22.0)


@pytest.mark.parametrize("d,expected", [(22.0, 8.0), (40.0, 10.517), (80.0, 20.0)])
def test_the_tongue_is_a_quarter_of_the_lid_8_to_20_mm_set_back_and_rounded(d, expected):
    """K4, K5, T4: 0.26 × the lid's depth, never under 8 nor over 20 mm; set back t each side; corners rounded."""
    coords = calculate_dieline(_params(w=60.0, d=d, h=200.0))
    for tuck in coords.derived["tucks"]:
        assert tuck["tongue_mm"] == pytest.approx(expected, abs=1e-3)
        assert tuck["tongue_x_l"] - tuck["x_l"] == pytest.approx(T) and tuck["x_r"] - tuck["tongue_x_r"] == pytest.approx(T)
        assert tuck["tongue_radius_mm"] == pytest.approx(min(0.6 * expected, (tuck["tongue_x_r"] - tuck["tongue_x_l"]) / 4))
    assert not coords.stadium_cutouts                         # K7: no hole in the tongue


def test_the_lock_slits_and_the_dust_shoulders_are_one_lock():
    """K6, F3: a slit cut along each end of each tuck fold, the crease between them, each the shoulder + 1 mm; each
    dust flap shouldered toward the panel the tongue enters and straight toward the lid's panel."""
    coords = calculate_dieline(_params())
    sd = 0.075 * 22.45
    for tuck in coords.derived["tucks"]:
        slits = [s for s in coords.slit_lines if s[1] == s[3] == pytest.approx(tuck["fold_y"])]
        assert len(slits) == 2
        crease = [f for f in coords.fold_lines if f[1] == f[3] == pytest.approx(tuck["fold_y"])]
        assert crease[0][0] == pytest.approx(tuck["x_l"] + sd + 1.0) and crease[0][2] == pytest.approx(tuck["x_r"] - sd - 1.0)
    shoulders = {(r["end"], r["panel"]): r["shoulder_toward"] for r in coords.derived["dust_flaps"]}
    assert shoulders == {("top", "side_left"): "front", ("top", "side_right"): "front",
                         ("bottom", "side_left"): "back", ("bottom", "side_right"): "back"}


def test_the_dust_flaps_never_meet_and_stay_under_the_lid():
    """F2: depth = min(B − t, A/2 − 1) — at 119's size 10.225 mm on a 22.45 mm opening (1.3's were 13.9 mm each on 22,
    overlapping 5.8 mm when closed)."""
    coords = calculate_dieline(_params())
    for r in coords.derived["dust_flaps"]:
        assert r["depth_mm"] == pytest.approx(10.225)
    old = calculate_dieline(_params("straight_tuck_end_carton", "1.3", glue=10.0))
    assert old.derived["dust_flap_height_mm"] * 2 > 22.0


def test_the_glue_flap_tapers_and_stays_clear_and_the_thumb_notch_sits_where_the_tongue_enters():
    """G1–G3, N1."""
    coords = calculate_dieline(_params())
    glue = coords.derived["glue"]
    assert glue["width_mm"] == 12.0 and glue["taper_mm"] == pytest.approx(4.0)
    narrow = calculate_dieline(_params(d=12.0, w=20.0, h=80.0, glue=15.0))
    assert narrow.derived["glue"]["width_mm"] == pytest.approx(12.45 - 3.0) and narrow.derived["notes"]
    notch = coords.derived["thumb_notch"]
    front = next(p for p in coords.panels if p.name == "front")
    assert notch["panel"] == "front" and notch["cx"] == pytest.approx(front.x + front.width / 2) and notch["y"] == coords.body_top_y
    assert notch["r"] == pytest.approx(max(3.5, 0.18 * 22.45))


# ---- the fold check --------------------------------------------------------------------------------------------------

_SIZES = [(w, d, h) for w in (12.0, 15.0, 22.0, 42.0, 90.0, 150.0) for d in (12.0, 22.0, 32.0, 60.0)
          for h in (60.0, 105.0, 200.0) if h > w and h > d and d / w <= 2.5]


@pytest.mark.parametrize("template", ["straight_tuck_end_carton", "reverse_tuck_end_carton"])
def test_every_size_the_schema_admits_folds_and_the_check_takes_under_a_second(template):
    slowest = 0.0
    for w, d, h in _SIZES:
        coords = calculate_dieline(_params(template, w=w, d=d, h=h, glue=min(12.0, d + T - 3.0)))
        start = time.perf_counter()
        record = FC.check(coords)
        slowest = max(slowest, time.perf_counter() - start)
        assert record["passed"], ((w, d, h), record["failed"])
        assert len(record["findings"]) >= 30
    assert slowest < 1.0, slowest


def test_119s_1_3_die_does_not_fold_and_the_check_says_where():
    """The control: 119's die as drawn before (1.3, 22 × 22 × 105, 0.45 mm board): its dust flaps meet across the
    opening, its tube is not square, its lid is not set over the dust flaps, its dust flaps are not shouldered."""
    record = FC.check(calculate_dieline(_params("straight_tuck_end_carton", "1.3", glue=10.0)))
    failed = {x["id"] for x in record["failed"]}
    assert not record["passed"]
    assert {"top_dust_no_collision", "bottom_dust_no_collision", "tube_square", "top_lid_over_dust",
            "top_left_dust_shoulder"} <= failed, failed
    assert all(x["words"] for x in record["failed"]) and FC.said(record)[0].startswith("The die does not fold")


def _replaced(coords, **kw):
    fields = {k: getattr(coords, k) for k in DielineCoordinates.__dataclass_fields__}
    fields.update(kw)
    return DielineCoordinates(**fields)


def test_each_planted_defect_is_named():
    """A dust flap reaching past the middle; a lid 2 mm short; a panel 1 mm wide; a crease along a cut edge; a glue
    flap past its clearance; lock slits shorter than the shoulder they take — each named by the check that measures
    it."""
    from shapely.affinity import scale, translate
    coords = calculate_dieline(_params())
    comps = dict(coords.components)

    def named(c, fid):
        failed = {x["id"] for x in FC.check(c)["failed"]}
        assert fid in failed, (fid, failed)
    long_dust = scale(comps["top-left-dust"], xfact=1.0, yfact=1.4, origin=(0, coords.body_top_y))
    named(_replaced(coords, components=[(n, long_dust if n == "top-left-dust" else p) for n, p in coords.components]),
          "top_dust_no_collision")
    fold_y = coords.derived["tucks"][0]["fold_y"]
    named(_replaced(coords, fold_lines=[(x0, y0 + (2.0 if y0 == y1 == fold_y else 0.0), x1,
                                         y1 + (2.0 if y0 == y1 == fold_y else 0.0)) for x0, y0, x1, y1 in coords.fold_lines],
                    slit_lines=[(x0, y0 + 2.0, x1, y1 + 2.0) if y0 == fold_y else (x0, y0, x1, y1)
                                for x0, y0, x1, y1 in coords.slit_lines]), "top_tuck_reaches")
    panels = [type(p)(p.name, p.x, p.y, p.width + (1.0 if p.name == "front" else 0.0), p.height) for p in coords.panels]
    named(_replaced(coords, panels=panels), "tube_square")
    x5 = coords.derived["x5"]
    named(_replaced(coords, fold_lines=coords.fold_lines + [(x5, coords.body_top_y + 5, x5, coords.body_bottom_y - 5)]),
          "creases_on_board")
    wide = translate(scale(coords.glue_tab_polygon, xfact=2.0, yfact=1.0, origin=(coords.derived["x1"], 0)), 0, 0)
    named(_replaced(coords, glue_tab_polygon=wide), "glue_clear")
    short = [(x0, y0, x0 + (x1 - x0) * 0.2, y1) for x0, y0, x1, y1 in coords.slit_lines]     # slits a fifth as long
    named(_replaced(coords, slit_lines=short), "top_left_slit_catches")


def test_a_crash_lock_bottom_is_said_not_to_lock():
    """S3: the auto bottom (1.1) is four plain flaps — the check says so rather than pass it."""
    params = _params("tuck_top_auto_bottom_carton", "1.1", w=42.0, d=32.0, h=140.0, glue=10.0)
    failed = {x["id"] for x in FC.check(calculate_dieline(params))["failed"]}
    assert "bottom_closure" in failed


# ---- beside the professional reference ---------------------------------------------------------------------------

def _reference(style):
    """The Box Blanks die at inside 22 × 22 × 105, 0.45 board, measured from its SVG (mm): its creases and its cut."""
    svg = open(os.path.join(REFS, "boxblanks_%s_22x22x105_inside_t0.45.svg" % style), encoding="utf-8").read()
    crease_g = re.search(r'<g id="CREASE"[^>]*>(.*?)</g>', svg, re.S).group(1)
    cut_g = re.search(r'<g id="CUT"[^>]*>(.*?)</g>', svg, re.S).group(1)

    def lines(group):
        out = []
        for d in re.findall(r'd="([^"]+)"', group):
            pts = [tuple(map(float, p)) for p in re.findall(r"(-?[\d.]+) (-?[\d.]+)", d)]
            out += list(zip(pts, pts[1:]))
        return out
    creases, cut = lines(crease_g), [p for seg in lines(cut_g) for p in seg]
    verticals = sorted({round(a[0], 3) for a, b in creases if abs(a[0] - b[0]) < 1e-6})
    body_y = sorted({round(a[1], 3) for a, b in creases if abs(a[0] - b[0]) < 1e-6} |
                    {round(b[1], 3) for a, b in creases if abs(a[0] - b[0]) < 1e-6})
    horizontals = [(min(a[0], b[0]), a[1], max(a[0], b[0])) for a, b in creases if abs(a[1] - b[1]) < 1e-6]
    xs, ys = [p[0] for p in cut], [p[1] for p in cut]
    top_lid = [h for h in horizontals if h[0] > verticals[0] - 1e-6 and h[2] < verticals[1] + 1e-6
               and h[1] <= body_y[0] + 1e-6]
    return {"panels": [verticals[i + 1] - verticals[i] for i in range(3)] + [max(xs) - verticals[3]],
            "glue": verticals[0] - min(xs), "body": body_y[-1] - body_y[0],
            "lid_depth": max(h[1] for h in top_lid) - min(h[1] for h in top_lid),
            "tongue": min(h[1] for h in top_lid) - min(ys),
            "dust": body_y[0] - min(y for x, y in cut if verticals[1] + 1 < x < verticals[2] - 1)}


@pytest.mark.parametrize("style,template", [("RTE", "reverse_tuck_end_carton"), ("STE", "straight_tuck_end_carton")])
def test_the_die_agrees_with_the_professional_reference_where_the_rules_are_shared(style, template):
    """Box Blanks' die at the same style and size, read from its own file: every panel's crease width, the body's
    height, the glue flap, the lid's depth, the tongue and the dust flaps' depth are the same to 0.01 mm. Where 1.4
    differs by rule (TRADE_RULES.md §7) — the lid hinged one caliper out, the lock slits and the thumb notch — the
    reference has none of them."""
    ref = _reference(style)
    coords = calculate_dieline(_params(template))
    ours = {"panels": [p.width for p in coords.panels if p.name != "glue_tab"],
            "glue": coords.derived["glue"]["width_mm"], "body": coords.body_bottom_y - coords.body_top_y,
            "lid_depth": coords.derived["tucks"][0]["lid_depth_mm"], "tongue": coords.derived["tucks"][0]["tongue_mm"],
            "dust": coords.derived["dust_flaps"][0]["depth_mm"]}
    assert ref["panels"] == pytest.approx([22.45] * 4, abs=0.01) and ours["panels"] == pytest.approx(ref["panels"], abs=0.01)
    for key in ("glue", "body", "lid_depth", "tongue", "dust"):
        assert ours[key] == pytest.approx(ref[key], abs=0.01), (key, ours[key], ref[key])


# ---- the files printers expect (E1–E3, R1) ---------------------------------------------------------------------------

def test_every_file_draws_the_die_on_its_plates_colours_overprinting_with_its_grain(tmp_path):
    """The SVG working file draws the knife magenta and the creasing rules cyan — the CutContour and Crease plates' own
    colours, as the production PDF, the design .ai and the native .ai draw them (it drew blue and red, a second scheme);
    the production PDF's die overprints the artwork under it and says its style by its ECMA code, its grain and the side
    shown; the Illustrator handoff's die swatches carry the same colours."""
    import fitz

    from apps.dielines.exporters.counter_display_files import write_carton_pdf
    from apps.dielines.exporters.counter_display_files import write_carton_svg
    from apps.ire.handoff.graph_schema import SPOT_SWATCHES
    coords = calculate_dieline(_params())
    svg = write_carton_svg(coords, "trade", output_dir=str(tmp_path))
    assert re.search(r'id="cut-lines"[^>]*stroke="#EC008C"', svg) and re.search(r'id="fold-lines"[^>]*stroke="#00AEEF"', svg)
    assert "#0000FF" not in svg and "#FF0000" not in svg
    pdf = write_carton_pdf(coords, "trade", product_name="Rose Glaze", product_type="lip gloss",
                                board_thickness_mm=T, output_dir=str(tmp_path))
    raw = open(pdf, "rb").read()
    assert b"/OP true" in raw and b"/CutContour" in raw and b"/Crease" in raw
    words = " ".join(fitz.open(pdf)[0].get_text().split())
    assert "Reverse Tuck End (ECMA A20.20.03.01)" in words and "Grain parallel to the height (confirm)" in words
    assert "Side shown print side" in words and "Creases (W×D×H) 22.45 × 22.45 × 105.45" in words
    # every word on the sheet, inside its page — the title block's rows above its foot, the legend's words their own
    page = fitz.open(pdf)[0]
    spans = [s for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"] if s["text"].strip()]
    boxes = [fitz.Rect(s["bbox"]) for s in spans]
    assert all(page.rect.contains(r) for r in boxes)
    assert not any(a.intersects(b) and (a & b).get_area() > 1.0 for i, a in enumerate(boxes) for b in boxes[i + 1:]), \
        "two words overprint each other on the production sheet"
    # the title block's two columns: no word crosses the line between them (the legend's last word did) — the divide
    # the one upright line as tall as the block (44 mm) near the page's middle
    k = 72.0 / 25.4
    lines = [(it[1], it[2]) for d in page.get_drawings() for it in d["items"] if it[0] == "l"]
    divide = [(a, b) for a, b in lines if abs(a.x - b.x) < 0.01 and abs(abs(a.y - b.y) - 44.0 * k) < 1.0
              and page.rect.width * 0.4 < a.x < page.rect.width * 0.6]
    assert len(divide) == 1, divide
    (a, b), = divide
    y0, y1 = sorted((a.y, b.y))
    crossing = [s["text"] for s, r in zip(spans, boxes) if y0 <= r.y0 and r.y1 <= y1 and r.x0 < a.x < r.x1]
    assert not crossing, crossing
    swatches = {name: cmyk for name, _hex, cmyk in SPOT_SWATCHES}
    assert swatches["CUT"] == (0.0, 1.0, 0.0, 0.0) and swatches["CREASE"] == (1.0, 0.0, 0.0, 0.0)


def test_the_design_files_words_stay_on_its_artboard(tmp_path):
    """The die's words — its style and code, its inside and crease sizes, its board, flat size, bleed and safe, its
    grain — set in lines that stay on the artboard (on 119's 33 mm carton the one line ran off its right edge), and
    each panel's width to the hundredth (22.45 had read 22.4 beside a 33.45 that read 33.5)."""
    import fitz

    from apps.ire.compose import compose_components_graph
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    coords = calculate_dieline(_params(w=33.0))
    doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD")
    page = fitz.open(emit_pdf_ai(doc, str(tmp_path / "words.ai")))[0]
    spans = [s for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"]
             if s["text"].strip()]
    assert spans and all(page.rect.contains(fitz.Rect(s["bbox"])) for s in spans), \
        [s["text"] for s in spans if not page.rect.contains(fitz.Rect(s["bbox"]))]
    words = " ".join(" ".join(s["text"] for s in spans).split())
    assert "Reverse Tuck End (ECMA A20.20.03.01) · inside W 33 × D 22 × H 105 mm" in words
    assert "creases 33.45 × 22.45 × 105.45 mm" in words and "Grain parallel to the height" in words
    assert "33.45" in words.split() and "22.45" in words.split()
