"""Composer — dieline → Design Graph → editable .ai (Phase 1).

Proves the graph-first pipe end-to-end: the structural content is native
vector, the logo rides as a flagged Image node when drawn from its raster, and
the trilingual sticker survives via the bridge with its text extractable (i.e.
still editable, zero visual regression). [The clean-up of 2026-10-04 (E2): the
motif the composer placed on every panel and flap is removed, with its tests.]
"""
from __future__ import annotations

import pytest

from apps.ire import inside_print as IP
from apps.ire.compose import INSIDE_KEY, compose_components_graph
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import Group, StickerBridge, TextRun
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON

fitz = pytest.importorskip("fitz")

_INFO = {
    "product_name": "Rose Nectar Lip Gloss",
    "description": "A high-shine plumping lip gloss.",
    "ingredients": "POLYBUTENE, TOCOPHERYL ACETATE.",
    "warnings": "For external use only.",
    "net_weight": "6 ml e 0.20 fl. oz.",
    "item_no": "LG-6410-E",
    "barcode_ean": "5061030634110",
    "qr_url": "https://www.bbrose.com/rose-nectar",
    "translations": {
        "es": {"description": "Un brillo de labios voluminizador.",
               "warnings": "Solo para uso externo."},
        "ar": {"description": "غلوس شفاه لامع.", "warnings": "للاستعمال الخارجي فقط."},
    },
}


@pytest.fixture
def coords():
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": 35, "depth_mm": 25, "height_mm": 95},
        print_settings={}, construction={},
        metadata={"product_name": "Rose Nectar", "product_type": "lip gloss"}))


def test_graph_has_the_expected_named_hierarchy(coords):
    doc = compose_components_graph(
        coords, product_name="ROSE NECTAR",
        subtitle="LIP GLOSS", panel_info=_INFO)
    roles = {g.role for g in doc.root.children if isinstance(g, Group)}
    assert {"background", "product", "typography", "info", "structure"} <= roles
    # the info face is bridged (temporary), not yet native nodes
    info = doc.find_role("info")[0]
    assert any(isinstance(c, StickerBridge) for c in info.children)
    # the product group stands, empty: no picture is placed on a carton (the clean-up of 2026-10-04, E2)
    assert doc.find_role("product")[0].children == []
    # product name is native live text
    typ = doc.find_role("typography")[0]
    assert any(isinstance(c, TextRun) and c.text == "ROSE NECTAR"
               for c in typ.children)


def test_emitted_ai_is_editable_and_keeps_the_sticker(coords, tmp_path):
    doc = compose_components_graph(
        coords, product_name="ROSE NECTAR",
        subtitle="LIP GLOSS", panel_info=_INFO)
    out = emit_pdf_ai(doc, str(tmp_path / "d.ai"))
    page = fitz.open(out)[0]
    text = page.get_text()
    # native live text: product name + trilingual sticker copy extractable
    assert "ROSE NECTAR" in text
    assert "INGREDIENTS:" in text                     # EN sticker label
    # [his review of 119, 2026-10-05, point 2] the copy laid out at one size: a phrase may wrap, read across its lines
    assert "Solo para uso externo" in " ".join(text.split())   # Spanish (sticker bridge)
    # Arabic renders as shaped presentation-form glyphs (don't reverse-map to
    # base codepoints), so prove it by the embedded Arabic face.
    assert b"NotoNaskhArabic" in open(out, "rb").read()
    # vector structure (cut/fold) present; no picture at all (no logo is passed, no motif placed)
    assert len(page.get_drawings()) > 5
    assert page.get_images() == []


# §BH55 Phase 2 (2026-09-19): the carton front's name and its line, SET AS TYPE (the §Z1(b) guard) and MEASURED against
# the panel they print on (§BH50(f)(3), LIVE: "a copy overrun BLOCKS Gate 2").

def _carton(w, d, h):
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm", dimensions={"width_mm": w, "depth_mm": d, "height_mm": h},
        print_settings={}, construction={}, metadata={"product_name": "x", "product_type": "carton"}))


def _runs(doc, prefix):
    return [n for n in doc.find_role("typography")[0].children if n.name.startswith(prefix)]


def test_the_front_type_is_set_as_type_and_does_not_move_with_the_carton(coords):
    from apps.ire.compose import FRONT_LINE_PT, FRONT_NAME_PT, FRONT_TYPE_KEY
    for doc in (compose_components_graph(coords, product_name="ROSE NECTAR", subtitle="LIP GLOSS", panel_info=_INFO),
                compose_components_graph(_carton(111, 39, 112), product_name="ROSE NECTAR", subtitle="LIP GLOSS",
                                         panel_info=_INFO)):
        assert {n.size_pt for n in _runs(doc, "product-name")} == {FRONT_NAME_PT}
        assert {n.size_pt for n in _runs(doc, "subtitle")} == {FRONT_LINE_PT}
        assert doc.metadata[FRONT_TYPE_KEY]["codes"] == []


def test_a_long_name_is_set_in_lines_inside_its_panel_and_never_cut(tmp_path):
    from apps.ire.compose import FRONT_TYPE_KEY
    name = "Rose Damascena Night Repair Oil Concentrate"       # 43 characters: the old composer cut it at 40
    doc = compose_components_graph(_carton(40, 40, 110), product_name=name, subtitle="carton", panel_info=_INFO)
    record = doc.metadata[FRONT_TYPE_KEY]
    front = next(p for p in record["panels"] if p["panel"] == "front")
    assert " ".join(front["name"]["lines"]) == name and len(front["name"]["lines"]) > 1
    assert all(w <= front["avail_mm"] for w in front["name"]["widths_mm"]) and record["codes"] == []
    text = " ".join(fitz.open(emit_pdf_ai(doc, str(tmp_path / "d.ai")))[0].get_text().split())
    assert all(line in text for line in front["name"]["lines"])       # every word printed, nothing cut


def test_a_name_that_cannot_fit_its_panel_is_recorded_over_and_never_shrunk():
    from apps.ire.compose import FRONT_COPY_EXCEEDS_PANEL, FRONT_NAME_PT, FRONT_TYPE_KEY
    doc = compose_components_graph(_carton(30, 30, 90), product_name="Supercalifragilisticexpialidocious",
                                   panel_info=_INFO)
    assert {n.size_pt for n in _runs(doc, "product-name")} == {FRONT_NAME_PT}      # the size held, not shrunk
    assert f"{FRONT_COPY_EXCEEDS_PANEL}:front:name" in doc.metadata[FRONT_TYPE_KEY]["codes"]


def test_no_motif_means_no_raster_at_all(coords, tmp_path):
    doc = compose_components_graph(coords, product_name="ROSE NECTAR",
                                   panel_info=_INFO)
    out = emit_pdf_ai(doc, str(tmp_path / "d.ai"))
    page = fitz.open(out)[0]
    assert page.get_images() == []                    # fully vector, no raster
    assert "ROSE NECTAR" in page.get_text()           # native text survives


def test_his_go_a_cartons_front_is_drawn_from_its_own_concepts_map(coords):
    """His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design, for a wand vial and a carton". A carton whose concept's map traced a hot-pink band at the top
    of its front, a gold rule under it and two type lines: the front panel is drawn as the picture draws it — its ground
    the picture's cream, the band and the rule, the two lines set where the picture sets them, the house mark clear of
    them since the picture prints none — in place of its ruled mark and ruled type; its type is measured inside the
    panel; the back is drawn as before; and with no map the carton is exactly what it was."""
    from django.conf import settings

    from apps.ire.compose import CARTON_MAP_FRONT, FRONT_TYPE_KEY
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "bands": [{"part": "hot pink band", "fill": "#E82878", "edge_ink": None, "edge_width": 0.0,
                         "edge": [], "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.2], [0.0, 0.2]], "drips": 0}],
              "rules": [{"part": "gold rule", "box": [0.0, 0.2, 1.0, 0.208], "ink": "#D0A85C"}],
              "types": [{"part": "product name", "box": [0.1, 0.4, 0.9, 0.56], "ink": "#AA1E50",
                         "words": "Rosé Nectar", "source": "the product's name"},
                        {"part": "LIP GLOSS", "box": [0.22, 0.62, 0.78, 0.65], "ink": "#AA1E50",
                         "words": "LIP GLOSS", "source": "the brief's front copy"}]}
    plain = compose_components_graph(coords, product_name="Rosé Nectar", subtitle="lip gloss",
                                     logo_path=settings.BRAND_LOGO_PATH)
    doc = compose_components_graph(coords, product_name="Rosé Nectar", subtitle="lip gloss",
                                   logo_path=settings.BRAND_LOGO_PATH,
                                   map_front={"shapes": shapes, "edge_part": None, "ground": "#FAF0E2"})
    names = {getattr(n, "name", ""): n for n, _ in doc.walk()}
    plain_names = {getattr(n, "name", ""): n for n, _ in plain.walk()}
    assert "Map front" not in plain_names and "logo-front" in plain_names
    assert "Map front" in names and {"band-map-0", "rule-map-0"} <= set(names)
    assert names["panel-front"].fill.color.to_hex().upper() == "#FAF0E2"
    front = next(p for p in coords.panels if p.name == "front")
    mf = doc.metadata["map_front"]
    assert mf["drawn"] == ["hot pink band", "gold rule", "product name", "LIP GLOSS"], mf["drawn"]
    assert mf["mark"]["why"].startswith("the picture prints no mark"), mf.get("mark")
    ft = doc.metadata[FRONT_TYPE_KEY]
    assert ft["panels"][0]["panel"] == "front" and ft["panels"][0]["drawn_from"] == CARTON_MAP_FRONT and ft["codes"] == []
    assert {t["part"] for t in ft["panels"][0]["typed"]} == {"product name", "LIP GLOSS"}
    logo, ground = names["logo-front"], names["panel-front"]
    for x0, y0, x1, y1 in mf["boxes"].values():
        px0, px1 = ground.x + x0 * front.width, ground.x + x1 * front.width
        py0, py1 = ground.y + y0 * front.height, ground.y + y1 * front.height
        assert (logo.y + logo.h <= py0 + 1e-6 or logo.y >= py1 - 1e-6 or logo.x + logo.w <= px0 + 1e-6
                or logo.x >= px1 - 1e-6), ((logo.x, logo.y, logo.w, logo.h), (px0, py0, px1, py1))
    # [his goal of 2026-10-06, item 11: "Side panels are designed"] a carton drawn from its concept's map designs its
    # sides too; the ruled carton's panels as before
    assert [p["panel"] for p in ft["panels"][1:]] == [p["panel"] for p in plain.metadata[FRONT_TYPE_KEY]["panels"]
                                                       if p["panel"] != "front"] + ["side_left", "side_right"]


def test_his_finding_on_119_every_panel_is_vector_and_continues_the_concepts_ground_and_graphics(coords, tmp_path):
    """The owner's finding on design 119 (2026-10-03, transcribed at 32898c7): "KILL THE RASTER PATH ... Every panel is
    vector, drawn from the concept's map: front as the concept shows it; sides, back and flaps continue the concept's own
    ground, colours and graphics." A carton whose front's picture runs a hot-pink band and a gold rule edge to edge: the
    carton's every panel, flap and the glue tab stand on the picture's own cream; the band and the rule continue flat,
    in their own colours, at their own rows, across the side beside each edge and round the back to the glue tab; and
    the file holds no picture at all."""
    from apps.ire.compose import CONTINUED_FROM
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "concept_design_shapes_params/1.0"},
              "bands": [{"part": "hot pink band", "fill": "#E82878", "edge_ink": None, "edge_width": 0.0, "edge": [],
                         "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.2], [0.0, 0.2]], "drips": 0,
                         "edges": {"left": [0.0, 0.2], "right": [0.0, 0.2]}, "bleed_reach": 0.0}],
              "rules": [{"part": "gold rule", "box": [0.0, 0.2, 1.0, 0.208], "ink": "#D0A85C", "edges": ["left", "right"],
                         "drawn_box": [0.0, 0.2, 1.0, 0.208]}]}
    doc = compose_components_graph(coords, product_name="Rosé Nectar", tint="#FAF0E2",
                                   map_front={"shapes": shapes, "edge_part": None, "ground": "#FAF0E2"})
    names = {getattr(n, "name", ""): n for n, _ in doc.walk()}
    assert names["silhouette"].fill.color.to_hex() == "#FAF0E2"              # every flap and the glue tab
    assert all(names["panel-%s" % p].fill.color.to_hex() == "#FAF0E2" for p in ("front", "back"))
    panels = {p.name: p for p in coords.panels}
    for side, across in CONTINUED_FROM.items():
        for name in across:
            band, rule = names["continued-band-0-%s" % name], names["continued-rule-0-%s" % name]
            p = panels[name]
            assert band.fill.color.to_hex() == "#E82878" and rule.fill.color.to_hex() == "#D0A85C"
            assert abs(band.w - p.width) < 1e-6 and abs(band.h - 0.2 * p.height) < 1e-6
            assert abs(rule.h - 0.008 * p.height) < 1e-6
    assert not any(n.type == "image" for n, _ in doc.walk())
    out = emit_pdf_ai(doc, str(tmp_path / "d.ai"))
    assert fitz.open(out)[0].get_images() == []                               # no picture in the file at all


def test_his_finding_on_119_his_briefs_side_copy_is_set_on_both_sides_in_the_fronts_own_ink(coords):
    """The owner's finding on design 119 (2026-10-03, transcribed at 32898c7): "sides, back and flaps continue the
    concept's own ground, colours and graphics"; his brief: "Carton side: "LIP GLOSS · ملمّع الشفاه", 8 ml ℮ / 0.27 fl oz."
    Each side panel carries his side copy — each phrase one line stood on end, reading up, each script its own run — in
    the front's ink that stands out most from its ground, measured inside the side."""
    from apps.ire.compose import FRONT_TYPE_KEY, SIDE_PANELS
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
              "shapes": [{"part": "berry silhouette", "ink": "#56111B", "box": [0.2, 0.2, 0.8, 0.8],
                          "cubics": [[[[0.2, 0.2], [0.8, 0.2, 0.8, 0.2, 0.8, 0.2], [0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
                                       [0.2, 0.8, 0.2, 0.8, 0.2, 0.8], [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]]]]}],
              "types": [{"part": "LIP GLOSS", "box": [0.1, 0.9, 0.5, 0.93], "ink": "#F2B6AF", "words": "LIP GLOSS",
                         "source": "the picture's own English words"}]}
    side = ["LIP GLOSS · ملمّع الشفاه", "8 ml ℮ / 0.27 fl oz"]
    doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D2C0",
                                   map_front={"shapes": shapes, "edge_part": None, "ground": "#F1D2C0",
                                              "side_copy": side})
    runs = [n for n, _ in doc.walk() if isinstance(n, TextRun) and n.name.startswith("side-copy-")]
    for panel in SIDE_PANELS:
        mine = [r for r in runs if r.name.startswith("side-copy-%s-" % panel)]
        assert [r.text for r in mine] == ["LIP GLOSS ·", "ملمّع الشفاه", "8 ml ℮ / 0.27 fl oz"], [r.text for r in mine]
        assert all(r.rotation_deg == 90.0 and r.color.to_hex() == "#56111B" for r in mine)
        assert mine[1].rtl is True and mine[0].rtl is False
    sides = [p for p in doc.metadata[FRONT_TYPE_KEY]["panels"] if p["panel"] in SIDE_PANELS]
    # [his goal of 2026-10-06, item 11: "Side panels are designed: the product name at a real size plus a brand graphic
    # from the concept"] each side holds the name, stood on end, and the concept's own motif, beside his side copy
    assert len(sides) == 2 and all(p["drawn_from"] == "the product name, a brand graphic from the concept and the "
                                   "brief's side copy" and p["graphic"] == "the concept's own motif" and
                                   p["name"] == "Rose Glaze Lip Gloss" and p["name_size_pt"] >= 12 for p in sides), sides
    names = {n.name: n for n, _ in doc.walk()}
    for panel in SIDE_PANELS:
        assert names["side-name-%s" % panel].rotation_deg == 90.0 and "side-graphic-%s" % panel in names
    assert not [c for c in doc.metadata[FRONT_TYPE_KEY]["codes"] if "side-copy" in c or "side-name" in c]


def test_his_rule_one_the_cartons_arabic_is_drawn_with_its_marks_as_his_brief_writes_it(coords, tmp_path):
    """His rule 1 for design 119 and every design (2026-10-05, transcribed at 3bcdb26): "My brief's words win over the
    picture's text: ... the Arabic ملمّع as my brief writes it." The carton is drawn on the exempt drawer, which shaped
    the shadda of ملمّع away (119 printed ملمع); the carton declares it keeps its Arabic marks, so the drawn file holds
    ملمّع with its shadda. A document that does not declare it — every other exempt surface — draws exactly as before."""
    import unicodedata

    from apps.ire.emitters.pdf_ai import ARABIC_MARKS_KEY
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
              "types": [{"part": "LIP GLOSS", "box": [0.1, 0.9, 0.5, 0.93], "ink": "#56111B", "words": "LIP GLOSS",
                         "source": "the picture's own English words"}]}
    doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D2C0",
                                   map_front={"shapes": shapes, "edge_part": None, "ground": "#F1D2C0",
                                              "side_copy": ["LIP GLOSS · ملمّع الشفاه"]})
    assert doc.metadata[ARABIC_MARKS_KEY] is True

    def drawn(name):
        page = fitz.open(emit_pdf_ai(doc, str(tmp_path / name)))[0]
        return unicodedata.normalize("NFKC", page.get_text())

    assert drawn("kept.ai").count("\u0651") == 2                  # the shadda on both sides, as his brief writes it
    del doc.metadata[ARABIC_MARKS_KEY]
    assert "\u0651" not in drawn("as_before.ai")                  # undeclared: the exempt drawer as at 41604ac


def test_his_review_point_three_the_back_stands_on_the_cartons_one_ground(coords, tmp_path):
    """His review of 119 (2026-10-05, transcribed at bf7cb7f), point 3: "One ground all round the carton, taken from the
    concept's own colour ... The back panel must match the other panels." 119's back was laid on a paper of its own
    (#FCF8F5) and the sticker framed on another (#FCF9F6): every panel, flap and the glue tab now stand on the concept's
    ground, the back too, and the sticker lays no paper of its own."""
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
              "types": [{"part": "LIP GLOSS", "box": [0.1, 0.9, 0.5, 0.93], "ink": "#56111B", "words": "LIP GLOSS",
                         "source": "the picture's own English words"}]}
    doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#EFE9E4", panel_info=_INFO,
                                   map_front={"shapes": shapes, "edge_part": None, "ground": "#F2D7CE"})
    names = {getattr(n, "name", ""): n for n, _ in doc.walk()}
    assert "info-ground" not in names
    assert names["silhouette"].fill.color.to_hex() == "#F2D7CE"            # the map's ground, never the tint passed
    assert all(names["panel-%s" % p].fill.color.to_hex() == "#F2D7CE" for p in ("front", "back"))
    # [his final goal, 2026-10-05, B3: "Sticker (default): the ground runs across the back; the info sits ON TOP as a
    # rounded-rectangle label with a margin."] the back stands on the ground; the label on a sticker of its own over it
    sticker = next(n for n, _ in doc.walk() if isinstance(n, StickerBridge))
    assert sticker.ground == "#FFFFFF"
    out = emit_pdf_ai(doc, str(tmp_path / "back.ai"))
    page = fitz.open(out)[0]
    back = next(p for p in coords.panels if p.name == "back")
    fills = {tuple(round(v, 3) for v in d["fill"]) for d in page.get_drawings() if d.get("fill") is not None
             and d["rect"].width * 25.4 / 72 > back.width * 0.8 and d["rect"].height * 25.4 / 72 > back.height * 0.8}
    assert (0.988, 0.976, 0.965) not in fills and (0.989, 0.97, 0.953) not in fills, fills   # neither paper drawn


# ---- his review of 119, 2026-10-05, point 2: "THE BACK PANEL IS LAID OUT, NOT CRAMMED" — measured on the drawn file

_INFO_119 = {
    "product_name": "Rose Glaze Lip Gloss", "product_name_ar": "ملمّع الشفاه روز جليز",
    "description": "A glossy, lightweight lip gloss with a soft rose shine.",
    "ingredients": "Polybutene, Hydrogenated Polyisobutene, Silica Dimethyl Silylate, Parfum, Tocopheryl Acetate, CI 15850.",
    "how_to_use": "Apply to lips alone or over lipstick.",
    "warnings": "For external use only. Avoid contact with eyes. Discontinue use if irritation occurs.",
    "net_weight": "8 ml ℮ 0.27 fl. oz.", "item_no": "RG-001", "barcode_ean": "", "qr_url": "https://www.bbrose.com",
    "regulatory_text": "Made in UAE.",
    "translations": {
        "es": {"description": "Un gloss labial brillante y ligero con un suave brillo rosado.",
               "ingredients": "Polybutene, Hydrogenated Polyisobutene, Silica Dimethyl Silylate, Parfum, Tocopheryl "
                              "Acetate, CI 15850.",
               "how_to_use": "Aplicar en los labios solos o sobre el labial.",
               "warnings": "Solo para uso externo. Evitar el contacto con los ojos. Suspender el uso si se produce "
                           "irritación."},
        "ar": {"description": "غلوس شفاه لامع وخفيف الوزن مع لمعة وردية ناعمة.",
               "how_to_use": "يُطبَّق على الشفتين منفرداً أو فوق أحمر الشفاه.",
               "warnings": "للاستخدام الخارجي فقط. تجنب ملامسة العيون. أوقف الاستخدام في حال حدوث تهيج."}},
}


def _carton_119(width, depth, height):
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": width, "depth_mm": depth, "height_mm": height},
        print_settings={}, construction={}, metadata={"product_name": "Rose Glaze", "product_type": "lip gloss"}))


def signs_drawn(page):
    """[His goal of 2026-10-10, item 8] each estimated sign a finished page draws as its own shape between a quantity and
    the next ("60 ml \u212e 2 fl oz"): ``[(the words round it, its box in mm)]`` — read where it is drawn, between the
    unit's last letter and the next number, never a glyph of a face."""
    import re
    k = 25.4 / 72.0
    fills = [d["rect"] for d in page.get_drawings() if d.get("fill") and any(it[0] == "c" for it in d["items"])]
    found = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            chars = [c for span in line["spans"] for c in span["chars"]]
            text = "".join(c["c"] for c in chars)
            # after its unit, before the next number — or ending its line, where the row wraps after the sign
            for m in re.finditer(r"\d+(?:\.\d+)?\s*(?:ml|g)( +)(?=\d|$)", text):
                left = chars[m.start(1) - 1]["bbox"]
                last = m.end(1) >= len(chars)
                x_hi = left[2] + 2.0 * (left[3] - left[1]) if last else chars[m.end(1)]["bbox"][0] + 0.5
                found += [(" ".join(text[m.start():m.end(1) + 1].split()),
                           [round(v * k, 2) for v in (r.x0, r.y0, r.x1, r.y1)])
                          for r in fills if left[2] - 0.5 <= r.x0 and r.x1 <= x_hi and r.y0 < left[3] and r.y1 > left[1]]
    return found


def _drawn_label(coords, info, tmp_path, map_front=None):
    """The carton composed and drawn: its document, and every text span on each panel, in panel millimetres."""
    doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD", panel_info=info,
                                   map_front=map_front)
    out = emit_pdf_ai(doc, str(tmp_path / "label.ai"))
    page = fitz.open(out)[0]
    from apps.ire.compose import _PAGE_MARGIN_MM
    vx, vy = coords.bleed_polygon.bounds[0] - _PAGE_MARGIN_MM, coords.bleed_polygon.bounds[1] - _PAGE_MARGIN_MM
    k = 25.4 / 72.0
    spans = []
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln.get("spans", []):
                if sp["text"].strip():
                    x0, y0, x1, y1 = sp["bbox"]
                    spans.append((sp["text"], round(sp["size"], 2), (x0 * k + vx, y0 * k + vy, x1 * k + vx, y1 * k + vy)))
    black = [(r.x0 * k + vx, r.y0 * k + vy, r.x1 * k + vx, r.y1 * k + vy) for r in
             (d["rect"] for d in page.get_drawings() if d.get("fill") is not None and max(d["fill"]) < 0.2)]
    # (the codes' CMYK black reads (0.137, 0.122, 0.125) in RGB)
    return doc, spans, black, page.get_text()


def _on(panel, box, inset=0.0):
    x0, y0, x1, y1 = box
    return (panel.x + inset - 0.05 <= x0 and x1 <= panel.x + panel.width - inset + 0.05
            and panel.y + inset - 0.05 <= y0 and y1 <= panel.y + panel.height - inset + 0.05)


def _centre_on(panel, box):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return panel.x <= cx <= panel.x + panel.width and panel.y <= cy <= panel.y + panel.height


_ORDER = ["ROSE", "INGREDIENTS", "HOW TO USE:", "WARNINGS:", "DESCRIPCIÓN:", "MODO DE USO:", "ADVERTENCIAS:", "UAE.",
          "NET WT:", "ITEM NO:", "BATCH NO:", "EXP:"]


def _first(spans, needle):
    ys = [box[3] for t, _s, box in spans if needle in t]
    assert ys, needle
    return min(ys)


def _sticker_of(doc):
    from apps.ire.graph import Rect
    return next(n for n, _ in doc.walk() if isinstance(n, Rect) and n.name == "sticker")


def test_his_final_goal_c5_a_carton_sets_its_label_as_one_designed_block_on_its_sticker(tmp_path):
    """His final goal (2026-10-05, transcribed at 32e9aaf), C5: "THE INFO IS ONE DESIGNED BLOCK. All label info (title,
    description, ingredients, how to use, warnings, made in, NET WT/ITEM/BATCH/EXP, QR) lives together on the back
    sticker. A clear title; sections in a fixed order; one language block after another; one size and line spacing per
    level; bold headings." A 105 × 20 × 150 mm carton: every span of its label stands on the back's rounded sticker, which
    stands on the back's 4 mm safe margin over the carton's ground; English, then Spanish, then Arabic, then "Made in
    UAE.", then the NET WT block — in that order down the sticker; three sizes at most (the title, the body, the fine
    print) and the EAN's digits; the Spanish ingredients, the English's own words, printed once."""
    from apps.ire.compose import BACK_COPY_KEY, STICKER_RADIUS_MM
    coords = _carton_119(105, 20, 150)
    info = dict(_INFO_119, barcode_ean="5061030634110")
    doc, spans, _black, text = _drawn_label(coords, info, tmp_path)
    record = doc.metadata[BACK_COPY_KEY]
    assert record["codes"] == [] and record["offers"] == {} and record["languages"] == ["en", "es", "ar"], record
    back = next(p for p in coords.panels if p.name == "back")
    sticker = _sticker_of(doc)
    assert sticker.radius_mm == STICKER_RADIUS_MM and sticker.fill.color.to_hex() == "#FFFFFF"
    label = [(t, s, box) for t, s, box in spans if _centre_on(back, box)]
    assert all(_on(back, box, inset=4.0) for _t, _s, box in label), [t for t, _s, b in label if not _on(back, b, 4.0)]
    ys = [_first(label, n) for n in _ORDER]
    assert ys == sorted(ys), list(zip(_ORDER, ys))
    arabic = [box[3] for t, _s, box in label if any("؀" <= ch <= "ۿ" or "ﭐ" <= ch <= "﻿" for ch in t)]
    assert any(_first(label, "ADVERTENCIAS:") < y < _first(label, "UAE.") for y in arabic)   # the Arabic block, third
    assert "INGREDIENTS / INGREDIENTES:" in " ".join(text.split()) and text.count("Polybutene") == 1
    lv = record["levels_pt"]
    sizes = {s for _t, s, _b in label}
    digits = {s for t, s, _b in label if t.strip().isdigit()}
    assert sizes - digits <= {lv["title"], lv["body"], lv["fine"]} and lv["body"] >= 5.0 and lv["fine"] >= 4.0, sizes
    sides = [t for t, _s, box in spans for p in coords.panels if p.name.startswith("side_") and _centre_on(p, box)]
    assert sides == [], sides                                                   # nothing of the label on a side


def test_his_final_goal_c5_a_narrow_carton_shrinks_the_whole_label_evenly_in_its_own_face(tmp_path):
    """C5: "If it doesn't fit, shrink step by step keeping per-level consistency." [His correction of 2026-10-07:
    "Shrink the whole label evenly until everything fits, keeping its layout, spacing and order. Floor: 3 pt."] A 35 mm
    carton: where his final goal set the body at 5 pt, the ingredients and warnings at 4 pt and the whole in Fredoka at
    width 75, the label now stands in its own face with the body and the ingredients and warnings at one size, 4 pt,
    the title in its proportion; no span of it under that size but the title's own; the ℮ drawn as the estimated sign."""
    from apps.ire.compose import BACK_COPY_KEY
    coords = _carton_119(35, 30, 100)
    doc, spans, _black, text = _drawn_label(coords, _INFO_119, tmp_path)
    record = doc.metadata[BACK_COPY_KEY]
    lv = record["levels_pt"]
    assert (record["face"], lv["body"], lv["fine"], lv["title"]) == ("regular", 4.0, 4.0, 5.2), record
    back = next(p for p in coords.panels if p.name == "back")
    label = [(t, s) for t, s, box in spans if _centre_on(back, box)]
    sizes = {round(s, 2) for t, s in label if not t.strip().isdigit()}
    assert sizes <= {lv["title"], lv["body"]} and min(sizes) == 4.0, sizes
    # [re-pinned by his goal of 2026-10-10, item 8: "it must be the real estimated sign everywhere"] the sign drawn as itself after its quantity
    assert "℮" not in text and [w for w, _box in signs_drawn(fitz.open(str(tmp_path / "label.ai"))[0])], text
    fonts = {f[3] for f in fitz.open(str(tmp_path / "label.ai"))[0].get_fonts()}
    assert not any("Condensed" in f for f in fonts), fonts                      # the narrower face is no longer a step


def test_his_final_goal_c5_a_quantity_and_its_unit_are_never_broken_across_lines():
    """C5: "No awkward breaks (never 'fl. / oz.')" — a quantity and its unit stand as one token wherever the label
    wraps: the NET WT row and the copy alike."""
    from apps.dielines.exporters import label_layout as LL
    from apps.ire.compose import _label_fonts
    words = LL.unit_groups([(w, False) for w in "8 ml ℮ 0.27 fl. oz. with CI 15850. and 8 ml".split()])
    assert [w for w, _b in words] == ["8 ml ℮", "0.27 fl. oz.", "with", "CI 15850.", "and", "8 ml"]
    fonts = _label_fonts()
    lines, _over = LL._wrap_words([(w, False) for w in "NET 8 ml ℮ 0.27 fl. oz.".split()], 5.0, 24.0, fonts)
    assert [" ".join(w for w, _b in ln) for ln in lines] == ["NET", "8 ml ℮", "0.27 fl. oz."]


def test_his_final_goal_c5_a_label_that_does_not_stand_at_3_pt_is_held_with_its_one_offer_measured(tmp_path):
    """C5: "Only if it still doesn't fit, STOP and offer ... Never scatter it; never go below the floor." [His correction
    of 2026-10-07: "Only if it still doesn't fit at 3 pt, stop and tell me; don't widen or move anything on your own";
    "fewer languages only by my choice".] 119's 22 mm back now holds its own label at 3 pt; twice its copy does not stand
    there in three languages even at 3 pt: the design is held at Gate 2 by name, with the one offer measured through
    the same layout — English and Arabic, or English alone — each holding, shrunk evenly, when it is taken; never a wider
    carton nor the info inside; the held back carries the title, "Made in UAE." and the foot, and no language scattered
    anywhere."""
    from types import SimpleNamespace

    from apps.ire.compose import BACK_COPY_KEY, LABEL_DOES_NOT_FIT
    from apps.pipeline.targets.packaging import PackagingTarget
    coords = _carton_119(22, 22, 105)
    own = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD",
                                   panel_info=_INFO_119).metadata[BACK_COPY_KEY]
    assert own["codes"] == [] and own["levels_pt"]["body"] == own["levels_pt"]["fine"] == 3.0, own["levels_pt"]
    twice = dict(_INFO_119, **{k: (_INFO_119[k] + " ") * 2 for k in ("description", "ingredients", "how_to_use",
                                                                     "warnings")})
    doc, spans, _black, text = _drawn_label(coords, twice, tmp_path)
    record = doc.metadata[BACK_COPY_KEY]
    assert record["codes"] == [LABEL_DOES_NOT_FIT], record
    assert record["offers"] == {"fewer_languages": [["en", "ar"], ["en"]]}, record["offers"]
    held = PackagingTarget().gate2_hold(None, SimpleNamespace(spec_sheet={BACK_COPY_KEY: record}))
    assert held["error"] == LABEL_DOES_NOT_FIT and held["offers"] == record["offers"]
    flat = " ".join(text.split())
    assert "ROSE" in flat and "UAE." in flat and "NET WT:" in flat
    assert not any(w in flat for w in ("INGREDIENTS", "WARNINGS", "ADVERTENCIAS", "Polybutene")), flat
    for langs in record["offers"]["fewer_languages"]:
        taken = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD",
                                         panel_info=dict(twice, label_languages=langs)).metadata[BACK_COPY_KEY]
        lv = taken["levels_pt"]
        assert taken["codes"] == [] and taken["languages"] == langs and taken["languages_chosen"] is True, taken
        assert 3.0 <= lv["body"] == lv["fine"], lv


def test_his_final_goal_c5_the_sides_do_one_job(tmp_path):
    """C5: "Side panels do ONE job: name, size and brand graphics. Never mix vertical side copy with label blocks." His
    side copy stands whole on each side, centred in its height — nothing of the label beside it; the label set in the
    front's ink that stands out most from its sticker's paper (berry on 119)."""
    from apps.ire.compose import BACK_COPY_KEY
    from apps.ire.compose_container import name_width_estimate_mm
    coords = _carton_119(35, 22, 105)
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
              "shapes": [{"part": "berry silhouette", "ink": "#56111B", "box": [0.2, 0.2, 0.8, 0.8],
                          "cubics": [[[[0.2, 0.2], [0.8, 0.2, 0.8, 0.2, 0.8, 0.2], [0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
                                       [0.2, 0.8, 0.2, 0.8, 0.2, 0.8], [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]]]]}],
              "types": [{"part": "LIP GLOSS", "box": [0.1, 0.9, 0.5, 0.93], "ink": "#F2B6AF", "words": "LIP GLOSS",
                         "source": "the picture's own English words"}]}
    front = {"shapes": shapes, "edge_part": None, "ground": "#F1D5CD",
             "side_copy": ["LIP GLOSS · ملمّع الشفاه", "8 ml ℮ / 0.27 fl oz"]}
    doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD", panel_info=_INFO_119,
                                   map_front=front)
    assert doc.metadata[BACK_COPY_KEY]["codes"] == []
    label = next(n for n, _ in doc.walk() if isinstance(n, StickerBridge))
    assert label.ink == "#56111B" and label.name == "label"
    vy = coords.bleed_polygon.bounds[1] - 10.0
    from apps.ire.compose import SIDE_GAP_MM, SIDE_GRAPHIC_SHARE
    for p in (q for q in coords.panels if q.name.startswith("side_")):
        runs = [n for n, _ in doc.walk() if isinstance(n, TextRun) and n.name.startswith("side-copy-%s-0-" % p.name)]
        foot = max(r.y for r in runs) + vy
        top = min(r.y + vy - name_width_estimate_mm(r.text, r.size_pt) for r in runs)
        # [his goal of 2026-10-06, item 11] centred in the name's column, under the side's brand graphic
        safe_h = p.height - 2 * 4.0
        column_mid = p.y + 4.0 + safe_h - (safe_h * (1 - SIDE_GRAPHIC_SHARE) - SIDE_GAP_MM) / 2.0
        assert abs((foot + top) / 2 - column_mid) < 2.5, (foot, top, column_mid)
    out = emit_pdf_ai(doc, str(tmp_path / "sides.ai"))
    page = fitz.open(out)[0]
    vx = coords.bleed_polygon.bounds[0] - 10.0
    k = 25.4 / 72.0
    for p in (q for q in coords.panels if q.name.startswith("side_")):
        on = [sp["text"] for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for sp in ln["spans"]
              if _centre_on(p, (sp["bbox"][0] * k + vx, sp["bbox"][1] * k + vy, sp["bbox"][2] * k + vx,
                                sp["bbox"][3] * k + vy))]
        assert not any(w in " ".join(on) for w in ("INGREDIENTS", "WARNINGS", "ADVERTENCIAS", "NET WT")), on


def test_his_review_point_four_nothing_of_the_front_inside_the_safe_margin(tmp_path):
    """His review of 119 (2026-10-05, transcribed at bf7cb7f), point 4: "Nothing inside the safe margin: 119's foot line
    touches the fold. Set it in the concept's weight (bold, berry)." 119's front as its picture places it: the
    silhouette 2.9 mm from the side folds, the foot line "LIP GLOSS · ملمّع الشفاه" 1.3 mm from the foot's — 17.2 mm long
    at the 5 pt floor where the front's safe width is 14 mm. Its two parts are set one under the other, the front's parts
    scaled as one into the 4 mm margin, "LIP GLOSS ·" set bold as the picture prints it; a band the picture runs edge to
    edge still runs into the bleed."""
    from apps.ire.compose import FRONT_INSIDE_SAFE_MARGIN, FRONT_TYPE_KEY
    from apps.ire.compose_container import name_width_estimate_mm
    coords = _carton_119(22, 22, 105)
    ring = [[[[0.13, 0.04], [0.86, 0.04, 0.86, 0.04, 0.86, 0.04], [0.86, 0.956, 0.86, 0.956, 0.86, 0.956],
              [0.13, 0.956, 0.13, 0.956, 0.13, 0.956], [0.13, 0.04, 0.13, 0.04, 0.13, 0.04]]]]
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
              "bands": [{"part": "pink band", "fill": "#E82878", "edge_ink": None, "edge_width": 0.0, "edge": [],
                         "outline": [[0.0, 0.0], [1.0, 0.0], [1.0, 0.02], [0.0, 0.02]], "drips": 0,
                         "edges": {"left": [0.0, 0.02], "right": [0.0, 0.02]}, "bleed_reach": 0.0}],
              "shapes": [{"part": "berry silhouette", "ink": "#56111B", "box": [0.13, 0.04, 0.86, 0.956],
                          "cubics": ring}],
              "types": [{"part": "LIP GLOSS descriptor", "box": [0.093, 0.9727, 0.4147, 0.9833], "ink": "#51060A",
                         "words": "LIP GLOSS ·", "source": "the brief's carton front", "weight": "bold"},
                        {"part": "Arabic descriptor", "box": [0.4108, 0.9742, 0.8798, 0.9894], "ink": "#53120F",
                         "words": "ملمّع الشفاه", "source": "the brief's carton front"}]}
    doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD",
                                   map_front={"shapes": shapes, "edge_part": None, "ground": "#F1D5CD"})
    record = doc.metadata["map_front"]["safe_margin"]
    assert record["stacked"] == [["LIP GLOSS descriptor", "Arabic descriptor"]] and record["scale"] < 1.0, record
    assert not [c for c in doc.metadata[FRONT_TYPE_KEY]["codes"] if FRONT_INSIDE_SAFE_MARGIN in c]
    front = next(p for p in coords.panels if p.name == "front")
    vx, vy = coords.bleed_polygon.bounds[0] - 10.0, coords.bleed_polygon.bounds[1] - 10.0
    x_lo, x_hi = front.x + 4.0 - 0.01, front.x + front.width - 4.0 + 0.01
    y_lo, y_hi = front.y + 4.0 - 0.01, front.y + front.height - 4.0 + 0.01
    runs = [n for n, _ in doc.walk() if isinstance(n, TextRun) and n.name.startswith("front-descriptor-")]
    assert len(runs) == 2
    for r in runs:
        wide = name_width_estimate_mm(r.text, r.size_pt) * (1.06 if r.font == "bold" else 1.0)
        x0 = {"left": r.x, "center": r.x - wide / 2, "right": r.x - wide}[r.align] + vx
        assert x_lo <= x0 and x0 + wide <= x_hi and y_lo <= r.y + vy - r.size_pt * 0.3528 and r.y + vy <= y_hi, (
            r.text, round(x0, 2), round(x0 + wide, 2), round(r.y + vy, 2))
        assert r.size_pt >= 5.0
    latin = next(r for r in runs if "LIP" in r.text)
    assert latin.font == "bold" and latin.color.to_hex() == "#51060A"
    names = {getattr(n, "name", ""): n for n, _ in doc.walk()}
    sil = [n for n, _ in doc.walk() if n.type == "path" and n.fill is not None
           and getattr(n.fill, "color", None) is not None and n.fill.color.to_hex() == "#56111B"]
    xs = [s.x for p in sil for s in p.segments if hasattr(s, "x")]
    ys = [s.y for p in sil for s in p.segments if hasattr(s, "y")]
    assert sil and x_lo <= min(xs) + vx and max(xs) + vx <= x_hi and y_lo <= min(ys) + vy and max(ys) + vy <= y_hi
    band = [n for n, _ in doc.walk() if n.type == "path" and getattr(getattr(n, "fill", None), "color", None) is not None
            and n.fill.color.to_hex() == "#E82878"]
    bx = [s.x for p in band for s in p.segments if hasattr(s, "x")]
    assert band and min(bx) + vx <= front.x + 0.01 and max(bx) + vx >= front.x + front.width - 0.01   # still edge to edge



def test_his_review_point_five_the_silhouettes_rim_is_drawn_under_it(coords):
    """His review of 119, point 5: "The silhouette keeps the concept's details" — the rim the map read round the
    silhouette is drawn in its own ink, under the silhouette."""
    ring = [[[[0.2, 0.2], [0.8, 0.2, 0.8, 0.2, 0.8, 0.2], [0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
              [0.2, 0.8, 0.2, 0.8, 0.2, 0.8], [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]]]]
    rim = [[[[0.19, 0.19], [0.81, 0.19, 0.81, 0.19, 0.81, 0.19], [0.81, 0.81, 0.81, 0.81, 0.81, 0.81],
             [0.19, 0.81, 0.19, 0.81, 0.19, 0.81], [0.19, 0.19, 0.19, 0.19, 0.19, 0.19]]]]
    shapes = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
              "shapes": [{"part": "berry silhouette", "ink": "#56111B", "box": [0.19, 0.19, 0.81, 0.81], "cubics": ring,
                          "rim": {"ink": "#F6CDC7", "width": 0.01, "width_px": 3.0, "share": 0.7, "cubics": rim,
                                  "outer": {"ink": "#E0AEA0", "width": 0.02, "width_px": 5.0, "cubics": rim}}}]}
    doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD",
                                   map_front={"shapes": shapes, "edge_part": None, "ground": "#F1D5CD"})
    order = [getattr(n, "name", "") for n, _ in doc.walk()]
    assert "shape-rim-0" in order and order.index("shape-rim-outer-0") < order.index("shape-rim-0") < order.index(
        "shape-map-0")                                                      # the shadow, then the rim, then the shape
    names = {getattr(n, "name", ""): n for n, _ in doc.walk()}
    assert names["shape-rim-0"].fill.color.to_hex() == "#F6CDC7"


def test_his_review_point_one_a_label_missing_a_language_is_held_by_name(tmp_path):
    """His review of 119 (2026-10-05), point 1: "LANGUAGES: labels stay trilingual (English, Spanish, Arabic). That is
    how my company works: I enter English, the system translates." The sticker drew a label whose translation was
    missing in fewer languages without a word; now each piece of his English without its Spanish or its Arabic holds
    Gate 2 by name — and 119's own label, translated, holds nothing."""
    from types import SimpleNamespace

    from apps.ire.compose import BACK_COPY_KEY, LABEL_NOT_TRILINGUAL
    from apps.pipeline.targets.packaging import PackagingTarget
    coords = _carton_119(105, 20, 150)
    whole = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD", panel_info=_INFO_119)
    assert not [c for c in whole.metadata[BACK_COPY_KEY]["codes"] if c.startswith(LABEL_NOT_TRILINGUAL)]
    info = dict(_INFO_119, translations={"es": _INFO_119["translations"]["es"]})        # no Arabic came back
    doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD", panel_info=info)
    codes = doc.metadata[BACK_COPY_KEY]["codes"]
    assert sorted(codes) == sorted("%s:ar:%s" % (LABEL_NOT_TRILINGUAL, f) for f in ("description", "how_to_use",
                                                                                     "warnings")), codes
    held = PackagingTarget().gate2_hold(None, SimpleNamespace(spec_sheet={BACK_COPY_KEY: doc.metadata[BACK_COPY_KEY]}))
    assert held["error"] == LABEL_NOT_TRILINGUAL and held["codes"] == codes



def test_his_final_goal_c8_a_line_that_breaks_drops_its_separator(tmp_path):
    """His final goal (2026-10-05, transcribed at 32e9aaf), C8: "A LINE THAT BREAKS DROPS ITS SEPARATOR. When "LIP GLOSS
    · ملمّع الشفاه" breaks onto two lines, the "·" goes." On 119's 22 mm front the row cannot stand on one line inside
    the safe margin: it is set on two, one under the other and never on each other, and the "·" goes; on a front wide
    enough for one line it stays."""
    from apps.ire.text_script import drop_break_separators
    assert drop_break_separators(["LIP GLOSS ·", "ملمّع الشفاه"]) == ["LIP GLOSS", "ملمّع الشفاه"]
    assert drop_break_separators(["8 ml ℮", "/ 0.27 fl oz"]) == ["8 ml ℮", "0.27 fl oz"]
    assert drop_break_separators(["LIP GLOSS · ملمّع الشفاه"]) == ["LIP GLOSS · ملمّع الشفاه"]   # unbroken: kept
    types = [{"part": "LIP GLOSS descriptor", "box": [0.093, 0.9727, 0.4147, 0.9833], "ink": "#51060A",
              "words": "LIP GLOSS ·", "source": "the brief's carton front", "weight": "bold"},
             {"part": "Arabic descriptor", "box": [0.4108, 0.9742, 0.8798, 0.9894], "ink": "#53120F",
              "words": "ملمّع الشفاه", "source": "the brief's carton front"}]
    for width, broken in ((22, True), (80, False)):
        coords = _carton_119(width, 22, 105)
        doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD",
                                       map_front={"shapes": {"types": [dict(t) for t in types]}, "edge_part": None,
                                                  "ground": "#F1D5CD"})
        runs = [n for n, _ in doc.walk() if isinstance(n, TextRun) and n.name.startswith("front-descriptor-")]
        texts = [r.text for r in runs]
        if broken:
            assert texts == ["LIP GLOSS", "ملمّع الشفاه"], texts
            from apps.ire.back_panel import MM_PER_PT
            assert abs(runs[0].y - runs[1].y) >= runs[0].size_pt * MM_PER_PT, [r.y for r in runs]   # two lines, apart
        else:
            assert "LIP GLOSS ·" in texts and abs(runs[0].y - runs[1].y) < 1.0, (texts, [r.y for r in runs])


# ---- [his final goal, 2026-10-05, B1: "INSIDE AND TOP PRINTING"] — measured on the drawn file

_INSIDE_SHAPES = {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
           "shapes": [{"part": "berry vial silhouette", "ink": "#56111B", "box": [0.3, 0.1, 0.7, 0.9],
                       "cubics": [[[[0.3, 0.1], [0.7, 0.1, 0.7, 0.1, 0.7, 0.1], [0.7, 0.9, 0.7, 0.9, 0.7, 0.9],
                                    [0.3, 0.9, 0.3, 0.9, 0.3, 0.9], [0.3, 0.1, 0.3, 0.1, 0.3, 0.1]]]]}],
           "types": []}
_INSIDE_FRONT = {"shapes": _INSIDE_SHAPES, "edge_part": None, "ground": "#F1D5CD"}


def _inside_carton(w=35, d=25, h=95):
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm", dimensions={"width_mm": w, "depth_mm": d, "height_mm": h},
        print_settings={}, construction={}, metadata={"product_name": "Rose Glaze", "product_type": "lip gloss"}))


def test_his_final_goal_b1_the_briefs_inside_words_are_read_for_the_pattern():
    """The brief may describe it in words ("Inside: ..."): the line and its continuation, read for the kind, direction,
    density and tone of the pattern — at no cost; words that name none of these give nothing."""
    brief = "Mood: playful.\nInside: thin diagonal stripes,\n close together, on a deep ground.\n\nCarton side: LIP GLOSS"
    words = IP.brief_inside_words(brief)
    assert words == "thin diagonal stripes, close together, on a deep ground."
    assert IP.spec_from_words(words) == {"pattern": "stripes", "direction": "diagonal", "density": "dense",
                                         "tone": "dark"}
    assert IP.spec_from_words("our pink liquid swirl, large and airy")["pattern"] == "waves"
    assert IP.spec_from_words("the BBROSE monogram repeated")["motif"] == "logo"
    assert IP.brief_inside_words("Mood: calm.") == "" and IP.spec_from_words("make it lovely") is None


def test_his_final_goal_b1_the_inside_follows_his_picture_then_his_words_else_the_concepts_motif():
    """His picture's reading leads, his words win where they say a thing; with neither, the concept's own traced shape;
    the colours are the design's own — the ground its map reads, and the front's ink that stands out most from it."""
    picture = {"pattern": "dots", "direction": "none", "density": "sparse", "tone": "light"}
    both = IP.plan("referenced", [picture], "dense stripes", _INSIDE_FRONT)
    assert (both["pattern"], both["density"], both["tone"]) == ("stripes", "dense", "light")
    assert both["source"] == "his inside reference and his brief's words"
    assert (both["dark"], both["light"]) == ("#56111B", "#F1D5CD")
    alone = IP.plan("referenced", [], "", _INSIDE_FRONT)
    assert (alone["pattern"], alone["motif"], alone["source"]) == ("motif", "concept", "the concept's own motif")
    assert IP.plan("solid", [picture], "stripes", _INSIDE_FRONT)["mode"] == "solid"
    assert IP.plan("plain", [], "", _INSIDE_FRONT)["source"] == "his choice: plain"


def _inside_drawn(tmp_path, spec, name="inside.ai", w=35):
    coords = _inside_carton(w)
    doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD", map_front=_INSIDE_FRONT, inside=spec)
    out = emit_pdf_ai(doc, str(tmp_path / name))
    return coords, doc, fitz.open(out)


def test_his_final_goal_b1_the_inside_is_its_own_artboard_printed_in_vector_in_the_designs_colours(tmp_path):
    """Two artboards: the outside, then the inside — the sheet seen from its inside, mirrored; its ground the design's
    dark tone across the whole bleed, its pattern (the concept's vial, repeated) one compound path in the light tone; no
    picture placed; the strip the glue tab is glued onto left unprinted, at the LEFT of the inside where the tab stands
    at the left of the outside."""
    spec = IP.plan("referenced", [], "", _INSIDE_FRONT)
    coords, doc, drawn = _inside_drawn(tmp_path, spec)
    assert drawn.page_count == 2 and doc.metadata[INSIDE_KEY]["pattern"] == "motif"
    page = drawn[1]
    assert page.get_images() == []
    fills = [(d["fill"], d["rect"]) for d in page.get_drawings() if d.get("fill")]
    dark = tuple(int("56111B"[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    light = tuple(int("F1D5CD"[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    def share(r):                                                # of the page, its width's and its height's
        return (r.width / page.rect.width) * (r.height / page.rect.height)
    assert any(max(abs(a - b) for a, b in zip(f, dark)) < 0.03 and share(r) > 0.5 for f, r in fills)
    assert any(max(abs(a - b) for a, b in zip(f, light)) < 0.03 for f, _r in fills)
    names = {n.name for n, _ in [(c, None) for c in doc.inside.children]}
    assert names == {"Inside print", "CUT", "CREASE"}                 # [his final goal, B2] the die on its layers
    # the glue strip, unprinted: the inside's print is clipped round it — at the left, mirrored from the outside's right
    strip = IP.glue_strip(coords)
    tab = coords.glue_tab_polygon.bounds
    assert tab[2] <= strip[0]                                    # the tab on the left, its strip on the body's right
    clip = doc.inside.children[0].clip
    xs = [s.x for s in clip if hasattr(s, "x")]
    bx0, _by0, bx1, _by1 = coords.bleed_polygon.bounds
    mirrored_left = (bx0 + bx1) - strip[2] - (bx0 - 10.0)        # in the page's millimetres
    assert any(abs(x - mirrored_left) < 0.01 for x in xs)


def test_his_final_goal_b1_solid_and_plain_as_he_chooses(tmp_path):
    """At the size step: one solid colour — the dark tone alone, no pattern; plain — nothing printed inside, the die's
    lines only."""
    _c, doc, drawn = _inside_drawn(tmp_path, IP.plan("solid", [], "", _INSIDE_FRONT), "solid.ai")
    printed = doc.inside.children[0].children
    assert [n.name for n in printed] == ["inside-ground"]
    _c, doc, drawn = _inside_drawn(tmp_path, IP.plan("plain", [], "", _INSIDE_FRONT), "plain.ai")
    assert [g.name for g in doc.inside.children] == ["CUT", "CREASE"] and drawn.page_count == 2


def test_his_final_goal_b1_the_flaps_carry_design(tmp_path):
    """The flaps carry design: the dust flaps and the bottom tuck the concept's motif (each group clipped to its flap
    as a guard); the lid the house mark, turned to read from the front when the carton is closed (where an approved
    master is on file)."""
    coords, doc, _drawn_ = _inside_drawn(tmp_path, IP.plan("referenced", [], "dense dots", _INSIDE_FRONT), "flaps.ai")
    flaps = next(g for g in doc.root.children if g.name == "Flaps")
    names = {n.name for n in flaps.children}
    dusts = {name for name, _p in coords.components if "dust" in name}
    assert {"flap-%s" % d for d in dusts} <= names and all(n.clip for n in flaps.children if n.name.startswith("flap-"))


def test_his_goal_of_2026_10_06_item_10_each_flaps_motif_stands_once_and_whole_inside_its_safe_area():
    """[Executor, his goal of 2026-10-06, item 10, read on 119's drawn flaps: the motif laid as a repeat and clipped to
    each flap cut its vials in half at the die's edge and across the tuck's fold.] Each flap carries the concept's motif
    ONCE, whole: every point of it inside the flap less the carton's 4 mm safe margin — a tuck's on its own panel
    (the lid's, where no mark is on file; the bottom's), clear of its fold onto the tongue — at the inside's own repeat size where the flap holds it, smaller where it
    does not; on 119's 22 mm carton too."""
    from shapely.geometry import Point
    from shapely.geometry import box as _box

    from apps.ire.compose import _concept_motif
    for coords in (_inside_carton(), _carton_119(22, 22, 105)):
        nodes = IP.flap_nodes(coords, (lambda v: v), (lambda v: v), IP.plan("referenced", [], "", _INSIDE_FRONT),
                              ground_hex="#F1D5CD", motif_cubics=_concept_motif(_INSIDE_FRONT), motif_aspect=1.5,
                              safe_mm=4.0)
        comps = dict(coords.components)
        depth = coords.dimensions.manufacture[1]
        drawn = {n.name[len("flap-"):]: n.children[0] for n in nodes if n.name.startswith("flap-")}
        assert set(drawn) == {n for n in comps if n not in ("main-body", "glue-tab")}, set(drawn)   # no mark on file
        for name, path in drawn.items():
            poly = comps[name]
            x0, _y0, x1, _y1 = poly.bounds
            if name == "bottom-front-tuck":
                poly = poly.intersection(_box(x0, coords.body_bottom_y, x1, coords.body_bottom_y + depth))
            if name == "top-back-tuck":
                poly = poly.intersection(_box(x0, coords.body_top_y - depth, x1, coords.body_top_y))
            safe = poly.buffer(-4.0 + 1e-6, join_style=2)
            pts = [(s.x, s.y) for s in path.segments if hasattr(s, "x")]
            pts += [(s.x1, s.y1) for s in path.segments if hasattr(s, "x1")]
            assert all(safe.contains(Point(p)) for p in pts), (name, [round(v, 1) for v in safe.bounds])
            starts = [s for s in path.segments if type(s).__name__ == "MoveTo"]
            assert len(starts) == sum(len(poly_) for poly_ in _concept_motif(_INSIDE_FRONT)), (name, len(starts))
            ys = [p[1] for p in pts]
            assert max(ys) - min(ys) >= IP.FLAP_MOTIF_MIN_MM, name


def test_his_final_goal_b1_the_lid_mark_reads_from_the_front(tmp_path):
    """The lid's mark is the house master's outline turned 180° about the lid's centre: its first point lands where the
    upright mark's first point lands, reflected through that centre."""
    import os

    from django.conf import settings

    from apps.ire import brand_mark
    path = os.path.join(settings.BASE_DIR, *brand_mark.MARK_DIR, brand_mark.MASTER_FILE)
    master = brand_mark.read_master(open(path, "rb").read(), path=path)       # the house master, read from its file
    coords = _inside_carton()
    gx = gy = (lambda v: v)
    nodes = IP.flap_nodes(coords, gx, gy, IP.plan("referenced", [], "", _INSIDE_FRONT), ground_hex="#F1D5CD",
                          logo_master=master)
    lid = next(n for n in nodes if n.name == "lid-mark")
    xs = [s.x for s in lid.segments if hasattr(s, "x")]
    ys = [s.y for s in lid.segments if hasattr(s, "y")]
    top = dict(coords.components)["top-back-tuck"].bounds
    depth = coords.dimensions.manufacture[1]
    cx, cy = (top[0] + top[2]) / 2.0, coords.body_top_y - depth / 2.0
    assert abs((min(xs) + max(xs)) / 2 - cx) < 0.5 and abs((min(ys) + max(ys)) / 2 - cy) < 0.5
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    upright = brand_mark.placed_segments(master, cx - w / 2, cy - h / 2, w, h)
    first = next(s for s in upright if hasattr(s, "x"))
    turned = next(s for s in lid.segments if hasattr(s, "x"))
    assert abs(turned.x - (2 * cx - first.x)) < 0.05 and abs(turned.y - (2 * cy - first.y)) < 0.05


def test_his_final_goal_b1_a_document_without_an_inside_draws_its_one_artboard(tmp_path):
    """Every call before B1 (no ``inside``) draws the one artboard it always did, and dumps no "inside"."""
    coords = _inside_carton()
    doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD", map_front=_INSIDE_FRONT)
    assert doc.inside is None and "inside" not in doc.model_dump() and INSIDE_KEY not in doc.metadata
    assert fitz.open(emit_pdf_ai(doc, str(tmp_path / "one.ai"))).page_count == 1


def test_his_correction_of_2026_10_07_the_label_shrinks_evenly_to_3_pt_on_the_carton_he_confirmed(tmp_path):
    """[His correction of 2026-10-07 (transcribed at a6b2092): "when the label doesn't fit, the text gets SMALLER. Never
    move information anywhere else (not inside, not behind the QR, not to another panel) and never drop it. Never widen
    the carton for text ... Shrink the whole label evenly until everything fits, keeping its layout, spacing and order.
    Floor: 3 pt."] 119's label on its 22 mm carton (the reverse tuck end at 1.4): every language on the back's sticker,
    the body and the ingredients and warnings at one size — not under 3 pt — and the title in its proportion, in the
    label's own face; the carton drawn at the width confirmed; nothing printed inside (an old size that chose it, too)."""
    from apps.dielines.exporters import label_layout as LL
    from apps.dielines.validators.schema import DielineInputJSON
    from apps.ire.compose import BACK_COPY_KEY
    coords = calculate_dieline(DielineInputJSON(
        template="reverse_tuck_end_carton", template_version="1.4", unit="mm",
        dimensions={"width_mm": 22, "depth_mm": 22, "height_mm": 105},
        print_settings={"bleed_mm": 3, "safe_margin_mm": 4},
        construction={"glue_tab_mm": 12, "board_thickness_mm": 0.45, "thickness_compensation": True},
        metadata={"product_name": "Rose Glaze Lip Gloss", "product_type": "lip gloss"}))
    assert LL.FLOOR_PT == LL.FINE_FLOOR_PT == 3.0
    assert all(lv["face"] == "regular" and lv["body"] == lv["fine"] for lv in LL.steps({"narrow_regular": "x"}))
    for info in (_INFO_119, dict(_INFO_119, label_inside=True)):          # an old size that chose the inside
        doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD", panel_info=info,
                                       inside={"mode": "solid", "dark": "#51060A", "light": "#F1D5CD"})
        record = doc.metadata[BACK_COPY_KEY]
        lv = record["levels_pt"]
        assert record["codes"] == [] and record["languages"] == ["en", "es", "ar"] and "widened" not in record
        assert 3.0 <= lv["body"] < 5.0 and lv["fine"] == lv["body"] and record["face"] == "regular", lv
        assert lv["title"] <= round(lv["body"] * LL.TITLE_EM, 2) + 1e-9 and "shrunk evenly" in record["said"][0]
        assert coords.dimensions.inner[0] == 22.0
        drawn = fitz.open(emit_pdf_ai(doc, str(tmp_path / "shrunk.ai")))
        outside, inside = " ".join(drawn[0].get_text().split()), " ".join(drawn[1].get_text().split())
        for words in ("INGREDIENTS", "INGREDIENTES", "ADVERTENCIAS", "NET WT", "UAE."):
            assert words in outside, words
        assert "INGREDIENTS" not in inside and inside == ""


def test_his_correction_of_2026_10_07_a_label_that_does_not_fit_at_3_pt_stops_and_says_so():
    """"Only if it still doesn't fit at 3 pt, stop and tell me; don't widen or move anything on your own." A label four
    times 119's long on its 22 mm back: held by name, laid at 3 pt when it was tried, its words saying it waits on him;
    its one offer fewer languages, never a wider carton nor the info inside."""
    from apps.dielines.exporters import label_layout as LL
    from apps.ire.compose import BACK_COPY_KEY, LABEL_DOES_NOT_FIT
    long_info = dict(_INFO_119, **{k: (_INFO_119[k] + " ") * 4 for k in ("description", "ingredients", "how_to_use",
                                                                         "warnings")})
    doc = compose_components_graph(_carton_119(22, 22, 105), product_name="Rose Glaze Lip Gloss", tint="#F1D5CD",
                                   panel_info=long_info)
    record = doc.metadata[BACK_COPY_KEY]
    assert record["codes"][:1] == [LABEL_DOES_NOT_FIT] and set(record["offers"]) <= {"fewer_languages"}
    assert "%g pt" % LL.FLOOR_PT in record["said"][0] and "nothing was moved, dropped or widened" in record["said"][0]


# ---- [his final goal, 2026-10-05, B3: "THE BACK INFO IS A STICKER, his choice at the size step."]

def test_his_final_goal_b3_his_words_are_read_for_the_sticker():
    """The brief may describe the sticker ("Sticker: ..."): read for its shape, fill and border, at no cost; with no
    reference and no words, the default sticker, said."""
    from apps.ire import back_info as BI
    words = BI.brief_sticker_words("Mood: calm.\nSticker: a dark oval with a thin border.\n\nInside: dots")
    assert words == "a dark oval with a thin border."
    assert BI.spec_from_words(words) == {"shape": "oval", "fill": "dark", "border": "thin"}
    assert BI.plan("custom", [], "")["mode"] == "sticker"                       # nothing given: the default sticker
    assert BI.plan("custom", [{"shape": "arch", "fill": "light", "border": "double"}], "square")["shape"] == "square"
    assert BI.plan("printed", [], words)["source"] == "his choice: printed on the panel"


def _back_spans(doc, coords, tmp_path, name):
    out = emit_pdf_ai(doc, str(tmp_path / name))
    page = fitz.open(out)[0]
    k = 25.4 / 72.0
    vx, vy = coords.bleed_polygon.bounds[0] - 10.0, coords.bleed_polygon.bounds[1] - 10.0
    back = next(p for p in coords.panels if p.name == "back")
    spans = [(sp["text"], (sp["bbox"][0] * k + vx, sp["bbox"][1] * k + vy, sp["bbox"][2] * k + vx,
                           sp["bbox"][3] * k + vy)) for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])
             for sp in ln["spans"] if sp["text"].strip()]
    return back, [(t, b) for t, b in spans if _centre_on(back, b)], page


def test_his_final_goal_b3_the_back_info_as_a_sticker_printed_or_his_custom_sticker(tmp_path):
    """Sticker (default): the white rounded label with its margin, the ground across the back under it. Printed: no
    sticker — the copy on the back's own ground inside its safe margin. Custom: his sticker as his words say it — a dark
    oval with a thin border, its copy in the ground's colour inside the oval's inscribed rectangle."""
    from apps.ire import back_info as BI
    from apps.ire.compose import BACK_COPY_KEY
    from apps.ire.graph import Path, Rect
    coords = _carton_119(60, 30, 120)
    front = {"shapes": {"state": "TRACED", "source_sha256": "ab" * 32, "params": {"version": "x"},
                        "shapes": [{"part": "berry", "ink": "#56111B", "box": [0.2, 0.2, 0.8, 0.8],
                                    "cubics": [[[[0.2, 0.2], [0.8, 0.2, 0.8, 0.2, 0.8, 0.2],
                                                 [0.8, 0.8, 0.8, 0.8, 0.8, 0.8], [0.2, 0.8, 0.2, 0.8, 0.2, 0.8],
                                                 [0.2, 0.2, 0.2, 0.2, 0.2, 0.2]]]]}], "types": []},
             "edge_part": None, "ground": "#F1D5CD"}

    def drawn(style, name):
        doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD", map_front=front,
                                       panel_info=dict(_INFO_119, back_info=style))
        return doc, *_back_spans(doc, coords, tmp_path, name)
    doc, back, spans, _page = drawn(BI.plan("sticker", [], ""), "sticker.ai")
    sticker = next(n for n, _ in doc.walk() if getattr(n, "name", "") == "sticker")
    assert isinstance(sticker, Rect) and sticker.radius_mm == BI.RADIUS_MM and doc.metadata[BACK_COPY_KEY]["codes"] == []
    doc, back, spans, page = drawn(BI.plan("printed", [], ""), "printed.ai")
    assert not any(getattr(n, "name", "") == "sticker" for n, _ in doc.walk())
    assert spans and all(_on(back, b, inset=4.0) for _t, b in spans)
    label = next(n for n, _ in doc.walk() if isinstance(n, StickerBridge))
    assert label.ground == "#F1D5CD" and label.ink == "#56111B"                 # on the ground, in the front's ink
    style = BI.plan("custom", [], "a dark oval with a thin border")
    doc, back, spans, page = drawn(style, "custom.ai")
    sticker = next(n for n, _ in doc.walk() if getattr(n, "name", "") == "sticker")
    assert isinstance(sticker, Path) and sticker.fill.color.to_hex() == "#56111B" and sticker.stroke is not None
    label = next(n for n, _ in doc.walk() if isinstance(n, StickerBridge))
    assert label.ink == "#F1D5CD"                                               # the copy in the ground's colour
    sx, sy, sw, sh = doc.metadata[BACK_COPY_KEY]["sticker_mm"]
    tx, ty, tw, th = BI.text_rect(style, sw, sh)
    inner = (back.x + sx + tx - 0.05, back.y + sy + ty - 0.05, back.x + sx + tx + tw + 0.05, back.y + sy + ty + th + 0.05)
    assert spans and all(inner[0] <= b[0] and b[2] <= inner[2] and inner[1] <= b[1] and b[3] <= inner[3]
                         for _t, b in spans), [t for t, b in spans if not (inner[0] <= b[0] and b[2] <= inner[2])]
    for shape in BI.SHAPES:                                                     # every shape draws, its copy inside it
        d = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD", map_front=front,
                                     panel_info=dict(_INFO_119, back_info=dict(style, shape=shape, fill="light")))
        assert d.metadata[BACK_COPY_KEY]["back_info"]["shape"] == shape


def _inside_carton_13(w=35, d=25, h=95):
    """[His final goal, B2] a carton at the print-ready 1.3."""
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", template_version="1.3", unit="mm",
        dimensions={"width_mm": w, "depth_mm": d, "height_mm": h}, print_settings={}, construction={},
        metadata={"product_name": "Rose Glaze", "product_type": "lip gloss"}))


def test_his_final_goal_b2_the_drawn_file_is_on_named_layers_its_guides_never_printing(tmp_path):
    """Each on its own named layer: CUT, CREASE, GLUE, BLEED, SAFE, ARTWORK (and DIMENSIONS) — the guides seen and never
    printed; the die's lines on their spot plates, overprinting; the cut the die's one outline with its slits; every
    fold creased and dashed; the glue tab marked and left without ink; the dimensions labelled."""
    from apps.dielines.exporters.counter_display_files import CARTON_NON_PRINTING as NON_PRINTING, layers_of
    coords = _inside_carton_13()
    doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD", map_front=_INSIDE_FRONT,
                                   inside=IP.plan("referenced", [], "", _INSIDE_FRONT))
    out = emit_pdf_ai(doc, str(tmp_path / "layers.ai"))
    layers = layers_of(out)
    assert set(layers) == {"ARTWORK", "CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS"}
    assert [n for n, v in layers.items() if not v["prints"]] == sorted(NON_PRINTING, key=list(layers).index)
    drawn = fitz.open(out)
    page = drawn[0]
    by_layer = {}
    for d in page.get_drawings():
        by_layer.setdefault(d.get("layer"), []).append(d)
    assert len(by_layer["CREASE"]) == len(coords.fold_lines) and all(d["dashes"] not in ("[] 0", None)
                                                                     for d in by_layer["CREASE"])
    assert len(by_layer["CUT"]) == 1 + len(coords.slit_lines)
    raw = drawn.xref_stream(page.get_contents()[0]).decode("latin-1")
    assert "/OP true" in raw or " gs" in raw                                    # the die's lines overprint
    assert "W 35 × D 25 × H 95 mm" in " ".join(page.get_text().split())
    names = {g.name for g in doc.inside.children}
    assert {"CUT", "CREASE"} <= names and set(layers_of(out)) >= {"CUT", "CREASE"}
    # the glue tab: no ground on it — [his second goal of 2026-10-06, item 2: B1, G4] past the 3 mm bleed over its crease
    from apps.ire.compose import GLUE_BLEED_MM
    sil = next(n for n in doc.root.children[0].children if n.name == "silhouette")
    gx0, gy0, gx1, gy1 = coords.glue_tab_polygon.bounds
    vx = coords.bleed_polygon.bounds[0] - 10.0
    assert min(s.x for s in sil.segments if hasattr(s, "x")) == pytest.approx(gx1 - GLUE_BLEED_MM - vx, abs=0.05)
    assert "Grain parallel to the height" in " ".join(page.get_text().split())


def test_his_final_goal_b2_the_production_pdfs_cut_is_the_dies_one_outline(tmp_path):
    """The production PDF drew each component's own outline — the body's top and bottom edges ran a cut along every
    flap hinge. Its cut is now the die's one outline and its open slits, on the CutContour plate; its bleed, safe, glue
    and dimensions on layers that never print."""
    from apps.dielines.exporters.counter_display_files import layers_of
    from apps.dielines.exporters.counter_display_files import write_carton_pdf
    coords = _inside_carton_13()
    out = write_carton_pdf(coords, "t-b2", output_dir=str(tmp_path))
    layers = layers_of(out)
    assert all(not layers[n]["prints"] for n in ("BLEED", "SAFE", "GLUE", "DIMENSIONS"))
    cut = [d for d in fitz.open(out)[0].get_drawings() if d.get("layer") == "CUT"]
    slits = [d for d in cut if len(d["items"]) == 1]
    assert len(cut) == 1 + len(coords.slit_lines) and len(slits) == len(coords.slit_lines)   # one outline, its slits


# --- [his final goal, 2026-10-05, C6: "EVERY ELEMENT IS ITS OWN PIECE. In the .ai, each part is a separate, named layer
# or group he can select, move or delete alone. Text stays editable where possible."] ----------------------------------

def _c6_doc(w=35, d=25, h=95):
    coords = _inside_carton_13(w, d, h)
    return compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD", map_front=_INSIDE_FRONT,
                                    panel_info=_INFO_119, inside=IP.plan("referenced", [], "", _INSIDE_FRONT))


def test_his_final_goal_c6_the_native_file_names_every_piece_on_its_layer_and_artboard():
    """The native .ai's data: two artboards, OUTSIDE and INSIDE, each with the named layers in order; every path, shape
    and line of words its own named item; the words live text in their own faces; nothing of the design a picture."""
    from apps.ire.emitters import native_ai
    data = native_ai.tree(_c6_doc())
    assert [b["name"] for b in data["boards"]] == ["OUTSIDE", "INSIDE"]
    assert all([lay["name"] for lay in b["layers"]] == list(native_ai.LAYERS) for b in data["boards"])
    outside = {lay["name"]: lay["items"] for lay in data["boards"][0]["layers"]}
    assert outside["ARTWORK"] and outside["CUT"] and outside["CREASE"] and outside["DIMENSIONS"]
    items = list(native_ai._walk([i for lay in data["boards"][0]["layers"] for i in lay["items"]]))
    unnamed = [i["t"] for i in items if not i["name"]]
    assert unnamed == [], unnamed
    texts = [i for i in items if i["t"] == "x"]
    assert texts and all(i["text"] and i["font"] and i["size"] > 0 for i in texts)
    assert data["skipped"] == [] and set(data["not_printing"]) == {"GLUE", "BLEED", "SAFE", "DIMENSIONS"}


def test_his_final_goal_c6_the_label_is_its_own_pieces_its_words_live():
    """The back's label in the native file: not one drawing but its pieces — the title, each language's sections, the
    made-in line, the NET WT block, the QR — each a named group of live lines, the Arabic in its logical order for
    Illustrator to shape, right to left."""
    from apps.ire.emitters import native_ai
    data = native_ai.tree(_c6_doc(105, 20, 150))                  # a back wide enough to hold the label (C5)
    items = list(native_ai._walk([i for lay in data["boards"][0]["layers"] for i in lay["items"]]))
    names = {i["name"] for i in items}
    for piece in ("label-title", "label-en", "label-es", "label-ar", "label-made-in", "label-net-wt", "label-qr"):
        assert piece in names, (piece, sorted(n for n in names if n.startswith("label")))
    arabic = [i for i in items if i["t"] == "x" and i["rtl"]]
    assert arabic and all(not any("ﭐ" <= ch <= "﻿" for ch in i["text"]) for i in arabic)
    assert any(i["t"] == "x" and i["text"].startswith("INGREDIENTS") for i in items)


def test_his_final_goal_c6_the_script_touches_only_its_own_document(tmp_path):
    from apps.ire.emitters import native_ai
    js = native_ai.script(native_ai.tree(_c6_doc()), str(tmp_path / "n.ai"))
    assert js.startswith("var D = {") and "doc.close(SaveOptions.DONOTSAVECHANGES)" in js
    assert "activeDocument" not in js and "app.documents[" not in js and ".close(" not in js.replace(
        "doc.close(SaveOptions.DONOTSAVECHANGES)", "")


def test_his_final_goal_c6_where_illustrator_cannot_build_it_the_record_says_why(tmp_path, monkeypatch):
    """No test drives Illustrator: where it is not here the record says so; where its run saves, the file is built."""
    from apps.ire.emitters import native_ai
    from apps.ire.handoff import illustrator_exec
    monkeypatch.setattr(illustrator_exec, "illustrator_available", lambda: False)
    out = native_ai.build(_c6_doc(), str(tmp_path / "n.ai"))
    assert out["built"] is False and "Illustrator is not available" in out["reason"] and out["schema"] == native_ai.SCHEMA

    def saved(jsx, timeout_s=0):
        open(str(tmp_path / "n.ai"), "wb").write(b"%PDF-1.4 stub")
        return {"executed": True, "saved": True, "texts": 40, "errors": []}
    monkeypatch.setattr(illustrator_exec, "illustrator_available", lambda: True)
    monkeypatch.setattr(illustrator_exec, "run_jsx", saved)
    out = native_ai.build(_c6_doc(), str(tmp_path / "n.ai"))
    assert out["built"] is True and out["path"].endswith("n.ai") and out["reason"] is None

    monkeypatch.setattr(illustrator_exec, "run_jsx", lambda jsx, timeout_s=0: {"executed": True, "saved": False,
                                                                                 "errors": ["save: denied"]})
    out = native_ai.build(_c6_doc(), str(tmp_path / "m.ai"))
    assert out["built"] is False and "save: denied" in out["reason"]


# --- [his final goal, 2026-10-05, C7: "THE SYSTEM CHECKS ITS OWN WORK ... Never hand me a defect silently."] -------

def _c7_bottle(wobble=False, threads=True, spike=False, speck=False):
    """A bottle's traced outline as the map draws it — symmetric about x = 20, its neck's threads on both sides — with,
    where asked, a stretch of wobble down its right edge (119's, bottom right), a thin spike, or a speck beside it."""
    from apps.ire.graph import ClosePath, Color, Document, Group, LineTo, MoveTo, Path, SolidFill
    def edge(wobble, spike):
        pts = [(23.0, 0.0), (23.0, 8.0)]
        if threads:
            for y in (9.0, 11.0, 13.0):
                pts += [(23.6, y), (23.0, y + 1.0)]
        pts += [(23.0, 16.0), (28.0, 20.0)]
        for i in range(1, 120):
            y, x = 20.0 + i * 0.5, 28.0
            if wobble and 70.0 <= y <= 76.0:
                x += 0.25 if i % 2 else -0.2
            pts.append((x, y))
            if spike and abs(y - 50.0) < 1e-6:
                pts += [(31.0, 50.1), (28.0, 50.2)]
        return pts + [(28.0, 80.0), (27.0, 81.0)]
    right = edge(wobble, spike)
    left = [(40.0 - x, y) for x, y in reversed(edge(False, False))]
    pts = right + left
    segs = [MoveTo(x=pts[0][0], y=pts[0][1])] + [LineTo(x=x, y=y) for x, y in pts[1:]] + [ClosePath()]
    if speck:
        segs += [MoveTo(x=34.0, y=40.0), LineTo(x=34.3, y=40.0), LineTo(x=34.3, y=40.3), LineTo(x=34.0, y=40.3),
                 ClosePath()]
    shape = Path(name="shape-map-0", segments=segs, fill=SolidFill(color=Color.from_hex("#5A1018")),
                 fill_rule="evenodd")
    return Document(page_w=60.0, page_h=100.0, root=Group(name="root", children=[Group(name="front", children=[shape])]))


def test_his_final_goal_c7_a_wobble_down_one_edge_is_redrawn_smooth_and_the_threads_are_kept():
    """119's silhouette, bottom right: one edge of a symmetric outline wobbles where its mirror is clean. The repair
    finds that stretch, and only it — the neck's threads repeat on both sides and are the shape — and redraws it as one
    smooth curve, said with its panel and millimetres."""
    from apps.ire import self_check as SC
    from apps.ire.graph import Path
    clean = _c7_bottle()
    assert SC.repair(clean, [{"name": "front", "x": 0.0, "y": 0.0, "w": 60.0, "h": 100.0}]) == []
    doc = _c7_bottle(wobble=True)
    before = SC._polygon(doc.root.children[0].children[0].segments)
    assert SC.outline_defects(before), "the wobble is found"
    found = SC.repair(doc, [{"name": "front", "x": 0.0, "y": 0.0, "w": 60.0, "h": 100.0}])
    assert [f["kind"] for f in found] == ["outline"] and found[0]["fixed"] and found[0]["panel"] == "front"
    assert "right edge" in found[0]["what"] and 69.0 <= found[0]["y_mm"] <= 77.0, found
    after = doc.root.children[0].children[0]
    assert isinstance(after, Path) and SC.outline_defects(SC._polygon(after.segments)) == []
    from shapely.geometry import box
    neck = box(15.0, 8.0, 25.0, 15.0)
    assert abs(SC._polygon(after.segments).intersection(neck).area - before.intersection(neck).area) < 1e-6
    assert SC.record(found, [])["said"][0].startswith("Fixed: the right edge")


def test_his_final_goal_c7_a_speck_is_removed_and_a_spur_cut_away():
    from apps.ire import self_check as SC
    doc = _c7_bottle(spike=True, speck=True)
    found = SC.repair(doc, [])
    kinds = sorted(f["kind"] for f in found)
    assert kinds == ["outline", "speck"], found
    shape = SC._polygon(doc.root.children[0].children[0].segments)
    assert SC.outline_defects(shape) == [] and len(SC._pieces(shape)) == 1 and shape.bounds[2] < 30.5


def test_his_final_goal_c7_an_e_after_a_quantity_is_set_as_the_estimated_sign():
    """"the ℮ must be the real estimated sign, not 'e'"."""
    from apps.ire import self_check as SC
    from apps.ire.graph import Color, TextRun
    assert SC.normalise_estimated("8 ml e / 0.27 fl oz") == "8 ml ℮ / 0.27 fl oz"
    assert SC.normalise_estimated("30 g e") == "30 g ℮"
    assert SC.normalise_estimated("8 ml ℮ 0.27 fl. oz.") == "8 ml ℮ 0.27 fl. oz."
    assert SC.normalise_estimated("Made in UAE, e-commerce") == "Made in UAE, e-commerce"
    doc = _c7_bottle()
    doc.root.children[0].children.append(TextRun(name="side", text="8 ml e / 0.27 fl oz", x=5.0, y=90.0, size_pt=6.0,
                                                 color=Color.from_hex("#333333")))
    found = SC.repair(doc, [{"name": "side_left", "x": 0.0, "y": 80.0, "w": 60.0, "h": 20.0}])
    assert doc.root.children[0].children[1].text == "8 ml ℮ / 0.27 fl oz"
    assert [(f["kind"], f["fixed"], f["panel"]) for f in found] == [("wrong glyph", True, "side_left")]


def test_his_final_goal_c7_the_drawn_file_is_read_for_what_the_eye_would_catch(tmp_path):
    """Text crossing text, a line across a traced shape's edge, a line that does not read on the shape it is set on, a
    line in the safe margin, a character its face has no glyph for — each shown with its panel and millimetres; a
    guide's words and the glue tab's mark are not his design. [re-pinned by his goal of 2026-10-10, item 8: "it must be the real estimated sign everywhere"] the ℮ never reaches a face now (it is
    drawn as itself), so the empty box is read on a character the face truly lacks."""
    from apps.ire import self_check as SC
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, TextRun
    doc = _c7_bottle()
    kids = doc.root.children[0].children
    ink = Color.from_hex("#5A1018")
    kids += [TextRun(name="a", text="ROSE GLAZE", x=30.0, y=95.0, size_pt=8.0, color=ink),
             TextRun(name="b", text="LIP GLOSS", x=31.0, y=95.6, size_pt=8.0, color=ink),
             TextRun(name="across", text="ACROSS THE EDGE", x=22.0, y=60.0, size_pt=6.0, color=Color.from_hex("#FFFFFF")),
             TextRun(name="dark", text="DARK", x=15.0, y=40.0, size_pt=6.0, color=ink),
             TextRun(name="margin", text="MARGIN", x=0.5, y=30.0, size_pt=6.0, color=ink),
             TextRun(name="sign", text="8 \u2602", x=50.0, y=20.0, size_pt=6.0, color=ink, rtl=True),
             TextRun(name="guide", text="GLUE — NO INK", x=45.0, y=95.0, size_pt=5.0, color=Color.from_hex("#00A0E3"))]
    regions = [{"name": "front", "x": 0.0, "y": 0.0, "w": 60.0, "h": 100.0}]
    path, rec = SC.run(doc, lambda d: emit_pdf_ai(d, str(tmp_path / "c7.ai")), regions, safe_mm=3.0)
    said = " | ".join(rec["said"])
    kinds = {(f["kind"], f["what"].split("'")[1] if "'" in f["what"] else f["what"]) for f in rec["shown"]}
    assert ("text crossing", "ROSE GLAZE") in kinds, said
    assert ("text crossing", "ACROSS THE EDGE") in kinds, said
    assert ("overlap", "DARK") in kinds, said
    assert ("in the safe margin", "MARGIN") in kinds, said
    assert any(f["kind"] == "wrong glyph" and "empty box" in f["what"] for f in rec["shown"]), said
    assert "GLUE" not in said and not rec["clean"]
    assert all(f["panel"] == "front" and "x_mm" in f for f in rec["shown"]), rec["shown"]


def test_his_final_goal_c7_a_check_that_could_not_run_is_shown_never_read_as_clean(tmp_path):
    from apps.ire import self_check as SC
    _path, rec = SC.run(_c7_bottle(), lambda d: str(tmp_path / "never_written.ai"), [])
    assert not rec["clean"] and rec["shown"][0]["kind"] == "check"


def test_his_final_goal_c7_a_line_is_never_nudged_onto_another_part():
    """119's "LIP GLOSS" stood under its bottle and poked past the margin at its print size; the nudge moved it up onto
    the bottle's foot, dark on dark. A nudge that would land a line on another part is not made: the front is fitted
    as one, its composition kept."""
    from apps.ire.compose import _typed_extent, inside_safe
    W, H = 22.0, 105.0
    front = {"shapes": {"shapes": [{"part": "bottle", "box": [0.2, 0.1, 0.8, 0.86], "cubics": [], "ink": "#5A1018"}],
                        "types": [{"part": "descriptor", "words": "LIP GLOSS", "box": [0.3, 0.87, 0.7, 0.985],
                                   "size_pt": 5.0}]}}
    fitted, record = inside_safe(front, W, H, 4.0, "Rose Glaze")
    shapes = fitted["shapes"]
    bottle = [float(v) for v in shapes["shapes"][0]["box"]]
    line = _typed_extent(shapes["types"][0], W, H, "Rose Glaze")
    assert line[1] >= bottle[3] * H - 1e-6, (line, bottle[3] * H)
    assert record["not_nudged"] and record["not_nudged"][0]["parts"] == ["descriptor"]
    assert line[3] <= H - 4.0 + 0.01


def test_his_final_goal_c7_the_labels_e_is_set_as_the_estimated_sign_before_it_is_drawn(coords, tmp_path):
    """The label is drawn from its own words: "6 ml e 0.20 fl. oz." printed an "e" where ℮ belongs. The repair sets the
    sign before the label is drawn, and says so; the drawn file carries ℮ in a face that has it. [re-pinned by his goal of 2026-10-10, item 8: "it must be the real estimated sign everywhere"]
    the drawn file carries the sign drawn as itself after "6 ml" (its row wraps there, the sign with its quantity), and
    no "e" left there."""
    from apps.ire import self_check as SC
    doc = compose_components_graph(coords, product_name="ROSE NECTAR", subtitle="LIP GLOSS", panel_info=_INFO)
    regions, folds, axis = SC.carton_frame(coords)
    path, rec = SC.run(doc, lambda d: emit_pdf_ai(d, str(tmp_path / "sign.ai")), regions, folds=folds, inside_axis=axis)
    text = " ".join(fitz.open(path)[0].get_text().split())
    assert "℮" not in text and "6 ml e " not in text and "6 ml 0.20 fl. oz." in text, text[:400]
    assert [w for w, _box in signs_drawn(fitz.open(path)[0])] == ["6 ml"], signs_drawn(fitz.open(path)[0])
    assert any(f["kind"] == "wrong glyph" and f["fixed"] and "net weight" in f["what"] for f in rec["fixed"]), rec
    assert not any(f["kind"] == "wrong glyph" for f in rec["shown"]), rec["shown"]


def test_his_final_goal_c7b_a_containers_back_panel_is_read_with_its_own_safe_margin(tmp_path):
    """[His final goal, 2026-10-05, A: "The safe margin rule applies to containers too"; C7: "elements in the safe
    margin ... show what and where"] A container's back panel at print size is read with its own margin, where its
    record says it is drawn: a line running past the column into the margin is shown by its panel and millimetres; the
    sheet's annotations around it are not his design's margin."""
    from types import SimpleNamespace

    from apps.ire import self_check as SC
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, TextRun
    ink = Color.from_hex("#333333")
    record = {"origin_mm": [15.7, 40.0], "panel_mm": [55.0, 99.0], "margin_mm": 3.0}
    doc = Document(page_w=120.0, page_h=160.0, root=Group(name="root", children=[
        TextRun(name="ok", text="How to use", x=18.7, y=50.0, size_pt=5.0, color=ink),
        TextRun(name="long", text="Aqua, Glycerin, Cocos Nucifera Oil, Cetearyl Alcohol, Rosa Damascena",
                x=18.7, y=55.0, size_pt=5.0, color=ink),
        TextRun(name="annotation", text="BACK PANEL AT PRINT SIZE", x=1.0, y=36.0, size_pt=6.0, color=ink)]))
    regions = SC.sheet_frame(SimpleNamespace(page_w=doc.page_w, page_h=doc.page_h, metadata={}), back_panel=record)
    assert regions[0]["name"] == "back panel" and regions[0]["safe_mm"] == 3.0 and regions[-1]["name"] == "sheet"
    path = emit_pdf_ai(doc, str(tmp_path / "back.ai"))
    shown = SC.inspect(path, regions)
    margin = [f for f in shown if f["kind"] == "in the safe margin"]
    assert len(margin) == 1 and margin[0]["panel"] == "back panel" and "Aqua" in margin[0]["what"], shown
    assert "mm inside the 3 mm safe margin" in margin[0]["what"]


def test_his_goal_of_2026_10_06_item_6_the_labels_arabic_headings_are_set_in_the_granted_bold_never_stroked(tmp_path):
    """His goal of 2026-10-06, item 6: "Approve Noto Naskh Arabic Bold ... for Arabic headings; no outline bolding." 119's
    label, drawn: its Arabic headings and its Arabic title are set in Noto Naskh Arabic Bold, and no Arabic is drawn with
    a stroke round its letters (every Naskh span filled, none stroked) — it was the Regular, stroked 0.035 em."""
    coords = _carton_119(35, 22, 105)
    doc = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD", panel_info=_INFO_119)
    out = emit_pdf_ai(doc, str(tmp_path / "bold.ai"))
    pdf = fitz.open(out)
    used = {f[3] for page in pdf for f in page.get_fonts()}
    assert any("NotoNaskhArabic-Bold" in f for f in used), used
    spans = [s for page in pdf for s in page.get_texttrace() if "Naskh" in s["font"]]
    assert spans and all(s["type"] == 0 for s in spans), [(s["font"], s["type"]) for s in spans if s["type"]]
    assert any("Bold" in s["font"] for s in spans) and any("Regular" in s["font"] for s in spans)



# ---- [his test blocker on design 123, 2026-10-09, (3)] — the carton continuing its container

def _field_art(ink="#AF2B2F"):
    """A container's line art as ``targets.composite.continued_line_art`` hands it: a field of small filled squares —
    potrace's grammar, a 100-unit drawing — over the box [0.1, 0.05, 0.9, 0.95] of a 35 x 120 mm tube."""
    squares = " ".join("M%d %d l4 0 0 4 -4 0 z" % (x, y) for x in range(0, 100, 10) for y in range(0, 100, 10))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg"><g transform="translate(0,0) scale(1,1)"><path d="%s"/></g></svg>'
           % squares)
    return {"part": "red hairline rose field", "outlines": {"svg": svg, "frame": [0.1, 0.05, 0.8 / 100, 0.9 / 100]},
            "box": [0.1, 0.05, 0.9, 0.95], "product_mm": [35.0, 120.0], "ink": ink, "ink_share": 0.16,
            "source_task_id": 122}


def test_his_blocker_123_the_containers_line_art_is_laid_at_its_own_scale_never_shrunk():
    """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3): "The
    carton's inside follows the inside reference (the berry petal flowers), and its flaps/sides repeat 122's line
    art."]
    The tube's line art laid over a box keeps the tube's own scale — its field 28 x 108 mm — enlarged only as far as it
    must be to cover the box, centred on it: over a 20 x 20 mm box it stands at its own size; over a 70 x 50 mm box,
    2.5 times, its width the box's."""
    from apps.ire.compose_container import continued_outlines
    art = _field_art()
    small = continued_outlines(art, [0.0, 0.0, 1.0, 1.0], 20.0, 20.0)
    ox, oy, kx, ky = small["frame"]
    assert abs(kx * 100 * 20.0 - 28.0) < 1e-6 and abs(ky * 100 * 20.0 - 108.0) < 1e-6      # the tube's own size
    assert abs((ox + 50 * kx) - 0.5) < 1e-9 and abs((oy + 50 * ky) - 0.5) < 1e-9             # centred
    wide = continued_outlines(art, [0.0, 0.0, 1.0, 1.0], 70.0, 50.0)
    _ox, _oy, kx, ky = wide["frame"]
    assert abs(kx * 100 - 1.0) < 1e-9 and abs(ky * 100 * 50.0 - 108.0 * 2.5) < 1e-6           # 2.5x: its width the box's


def test_his_blocker_123_the_flaps_and_sides_carry_the_containers_rose_whole(tmp_path):
    """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3): "The
    carton's inside follows the inside reference (the berry petal flowers), and its flaps/sides repeat 122's line
    art."]
    A carton continuing its container: each flap but the lid, and each side's graphic, carry the container's own rose —
    the largest whole, compact piece of its line art — once and whole inside the flap's safe area, in the container's
    ink; never the carton concept's traced shape, never a dot."""
    from shapely.geometry import Point

    from apps.ire.compose import _concept_motif, _motif_aspect, _motif_ink
    from apps.pipeline.targets.composite import _rose_of
    art = _field_art()
    art["rose"] = _rose_of(art["outlines"], art["product_mm"])
    # the field's squares stand apart, each 4 units: 1.12 x 4.32 mm — none a whole, compact piece of 8 mm or more
    assert art["rose"] is None
    ring = [[0.0, 0.0], [10.0, 0.0, 10.0, 0.0, 10.0, 0.0], [10.0, 12.0, 10.0, 12.0, 10.0, 12.0],
            [0.0, 12.0, 0.0, 12.0, 0.0, 12.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
    hole = [[3.0, 3.0], [3.0, 9.0, 3.0, 9.0, 3.0, 9.0], [7.0, 9.0, 7.0, 9.0, 7.0, 9.0], [7.0, 3.0, 7.0, 3.0, 7.0, 3.0],
            [3.0, 3.0, 3.0, 3.0, 3.0, 3.0]]
    art["rose"] = {"cubics": [[ring, hole]], "mm": [10.0, 12.0]}
    front = dict(_INSIDE_FRONT, continued=art)
    assert _concept_motif(front) == art["rose"]["cubics"] and _motif_aspect(front, None) == 1.0
    assert _motif_ink(front) == "#AF2B2F" and _motif_ink(_INSIDE_FRONT) is None
    coords = _inside_carton()
    nodes = IP.flap_nodes(coords, (lambda v: v), (lambda v: v), IP.plan("referenced", [], "", front),
                          ground_hex="#F1D5CD", motif_cubics=_concept_motif(front), motif_aspect=1.0, safe_mm=4.0,
                          motif_ink=_motif_ink(front))
    comps = dict(coords.components)
    drawn = {n.name[len("flap-"):]: n.children[0] for n in nodes if n.name.startswith("flap-")}
    assert set(drawn) == {n for n in comps if n not in ("main-body", "glue-tab")}, set(drawn)
    for name, path in drawn.items():
        assert path.fill.color.to_hex().upper() == "#AF2B2F", name
        assert len([g for g in path.segments if type(g).__name__ == "MoveTo"]) == 2, name    # the rose and its hole
        safe = IP.flap_area(name, comps[name], coords, 4.0).buffer(1e-6)
        pts = [(g.x, g.y) for g in path.segments if hasattr(g, "x")]
        assert all(safe.contains(Point(p)) for p in pts), name                                # whole, never cut
    doc = compose_components_graph(coords, product_name="Rose Glaze", tint="#F1D5CD", map_front=front,
                                   inside=IP.plan("referenced", [], "", front))
    found = []

    def walk(n):
        found.append(n)
        for c in getattr(n, "children", None) or []:
            walk(c)
    walk(doc.root)
    sides = [n for n in found if str(getattr(n, "name", "")).startswith("side-graphic-")]
    assert sides and all(n.fill.color.to_hex().upper() == "#AF2B2F" for n in sides), sides
    out = emit_pdf_ai(doc, str(tmp_path / "continued.ai"))
    assert fitz.open(out).page_count == 2


def test_his_blocker_123_the_inside_follows_its_references_flowers_drawn_in_our_own_shape(tmp_path):
    """[His test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ea2b98b), (3): "The
    carton's inside follows the inside reference (the berry petal flowers), and its flaps/sides repeat 122's line
    art."]
    His brief for 123: "Inside: bold berry petal flowers on pink, like the inside reference, redrawn in our own
    shapes." The reference read as a repeat of flowers is drawn as our own petal flower — five round petals about a
    round heart, never the concept's traced shape in their place, never the reference's own — at the reference's
    density and tone; his words alone say so too, and count its petals; a pattern of no flowers is as it was."""
    reading = {"pattern": "motif", "direction": "none", "density": "sparse", "tone": "light",
               "motif_words": "bold rounded petal flowers"}
    words = "bold berry petal flowers on pink, like the inside reference, redrawn in our own shapes."
    spec = IP.plan("referenced", [reading], words, _INSIDE_FRONT)
    assert (spec["pattern"], spec["motif"], spec["petals"], spec["density"], spec["tone"]) == (
        "motif", "flower", 5, "sparse", "light"), spec
    assert spec["source"].endswith("drawn as our own 5-petal flower"), spec["source"]
    assert IP.plan("referenced", [], "six-petal daisies, scattered", _INSIDE_FRONT)["petals"] == 6
    assert "petals" not in IP.plan("referenced", [], "dense dots", _INSIDE_FRONT)
    flower = IP.petal_flower(5)
    assert len(flower) == 6 and all(len(ring) == 3 for ring in flower[:5]) and len(flower[5]) == 5
    _coords, doc, drawn = _inside_drawn(tmp_path, spec, "flowers.ai")
    pattern = next(n for n in doc.inside.children[0].children if n.name == "inside-pattern")
    starts = len([s for s in pattern.segments if type(s).__name__ == "MoveTo"])
    # [re-pinned by his goal of 2026-10-10, item 10: "five long, pointed petals per flower"] whole flowers: five
    # petals each, no round heart drawn (the heart is pooled darker, in a layer of its own)
    assert starts and starts % 5 == 0, starts
    assert drawn.page_count == 2 and drawn[1].get_images() == []



def test_his_second_blocker_123_a_concepts_big_bloom_is_the_containers_rose_whole_and_scaled():
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4):
    "the big rose in Blossom Arch / Stem Journey is 122's rose, whole and scaled ($0)".]
    Where the concept's line art draws one big bloom (``targets.packaging.big_bloom``), the container's own rose is
    drawn there whole — its ring and its hole, its own proportions — as large as its place holds BLOOM_GROW times over,
    centred on it, in the line art's ink; the field round it drawn faint and kept clear behind it. A field with no bloom
    is drawn as before: whole strength, no rose laid on it."""
    from apps.ire.compose_container import BLOOM_FIELD_OPACITY, BLOOM_GROW
    art = _field_art()
    ring = [[0.0, 0.0], [10.0, 0.0, 10.0, 0.0, 10.0, 0.0], [10.0, 12.0, 10.0, 12.0, 10.0, 12.0],
            [0.0, 12.0, 0.0, 12.0, 0.0, 12.0], [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
    hole = [[3.0, 3.0], [3.0, 9.0, 3.0, 9.0, 3.0, 9.0], [7.0, 9.0, 7.0, 9.0, 7.0, 9.0], [7.0, 3.0, 7.0, 3.0, 7.0, 3.0],
            [3.0, 3.0, 3.0, 3.0, 3.0, 3.0]]
    art["rose"] = {"cubics": [[ring, hole]], "mm": [10.0, 12.0]}
    drawn = {}
    for bloom in ([0.4, 0.15, 0.85, 0.4], None):
        line = {"part": "line-drawn rose with stem and leaves", "ink": "#E3A9A7", "strokes": [],
                "continued": dict(art, part_box=[0.0, 0.0, 1.0, 1.0], bloom=bloom)}
        front = dict(_INSIDE_FRONT, shapes=dict(_INSIDE_SHAPES, shapes=[], lines=[line]), continued=art)
        doc = compose_components_graph(_inside_carton(), product_name="Rose Glaze", tint="#F1D5CD", map_front=front)
        found = []

        def walk(n):
            found.append(n)
            for c in getattr(n, "children", None) or []:
                walk(c)
        walk(doc.root)
        drawn[bool(bloom)] = found
    roses = [n for n in drawn[True] if str(getattr(n, "name", "")).endswith("-bloom")]
    assert len(roses) == 1, [getattr(n, "name", "") for n in drawn[True]]
    rose, = roses
    assert rose.fill.color.to_hex().upper() == "#AF2B2F"                         # the line art's ink
    assert len([g for g in rose.segments if type(g).__name__ == "MoveTo"]) == 2   # whole: its ring and its hole
    xs = [g.x for g in rose.segments if hasattr(g, "x")]
    ys = [g.y for g in rose.segments if hasattr(g, "y")]
    assert abs((max(xs) - min(xs)) / (max(ys) - min(ys)) - 10.0 / 12.0) < 0.01     # its own proportions
    field, = [n for n in drawn[True] if str(getattr(n, "name", "")).endswith("-continued")]
    assert field.fill.opacity == BLOOM_FIELD_OPACITY
    # as large as its place holds BLOOM_GROW times over: the bloom's place on the front, measured on the field's clip
    group = next(n for n in drawn[True] if field in (getattr(n, "children", None) or []))
    cx = [g.x for g in group.clip if hasattr(g, "x")]
    cy = [g.y for g in group.clip if hasattr(g, "y")]
    fw, fh = max(cx) - min(cx), max(cy) - min(cy)                                  # the part's box: the whole product
    assert abs((max(ys) - min(ys)) - min(0.45 * fw, 0.25 * fh) * BLOOM_GROW) < 0.01 * fh
    plain = [n for n in drawn[False] if str(getattr(n, "name", "")).endswith("-bloom")]
    assert plain == []
    field, = [n for n in drawn[False] if str(getattr(n, "name", "")).endswith("-continued")]
    assert field.fill.opacity == 1.0


def test_his_second_blocker_123_a_window_moves_with_its_mark_and_a_shape_run_edge_to_edge_stays():
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010).] Where a
    front's key elements are fitted inside the safe margin, the oval a mark is set in moves with it — Garden Wrap's
    BBROSE stood below its oval — and a solid shape the picture runs edge to edge stays where the picture prints it, into
    the bleed (his rule 3)."""
    from apps.ire.compose import inside_safe
    band = {"part": "scalloped band", "ink": "#E9A8A7", "box": [-0.1, 0.91, 1.1, 1.03], "edges": {"left": [0.92, 1.0]},
            "cubics": [[[[-0.1, 0.91], [1.1, 0.91, 1.1, 0.91, 1.1, 0.91], [1.1, 1.03, 1.1, 1.03, 1.1, 1.03],
                         [-0.1, 0.91, -0.1, 0.91, -0.1, 0.91]]]]}
    mark = {"part": "BBROSE wordmark", "box": [0.2, 0.0, 0.8, 0.04]}                  # inside the top margin
    window = {"part": "oval", "shape": "ellipse", "centre": [0.5, 0.02], "half": [0.35, 0.03], "angle": 0.0,
              "fill": "#F6E6E4", "box": [0.15, -0.01, 0.85, 0.05]}
    front = {"shapes": {"shapes": [band], "marks": [mark], "windows": [window], "types": []}}
    fitted, record = inside_safe(front, 42.0, 134.0, 4.0, "Rose Blossom")
    assert record["moved_mm"][1] > 0.0                                             # brought down inside the margin
    moved_mark, = fitted["shapes"]["marks"]
    moved_window, = fitted["shapes"]["windows"]
    assert fitted["shapes"]["shapes"][0] == band                                   # left where the picture prints it
    # the mark's box and the oval round it moved by the one fit: its centre still the mark's centre
    mx = (moved_mark["box"][0] + moved_mark["box"][2]) / 2.0
    my = (moved_mark["box"][1] + moved_mark["box"][3]) / 2.0
    assert abs(moved_window["centre"][0] - mx) < 1e-6 and abs(moved_window["centre"][1] - my) < 1e-6
    assert moved_window["centre"][1] > window["centre"][1]


def test_his_findings_123_the_front_is_laid_out_at_the_concepts_own_proportions():
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Scale
    the layout as a whole when the real size differs from the concept's (57 x 37 x 123 mm)."] Garden Wrap's face is 0.30
    as wide as it is tall, his front 57 x 123 mm (0.46): its type, its mark and the oval round it laid out as one block
    at the concept's own proportions, centred — no element stood wider than the concept draws it — while its scalloped
    band, run edge to edge, still spans the panel; a panel shaped as the face is drawn as the picture lays it."""
    from apps.ire.compose import uniform_layout
    band = {"part": "scalloped band", "ink": "#E9A8A7", "box": [-0.1, 0.92, 1.1, 1.03], "edges": {"left": [0.92, 1.0]},
            "cubics": [[[[-0.1, 0.92], [1.1, 0.92, 1.1, 0.92, 1.1, 0.92], [1.1, 1.03, 1.1, 1.03, 1.1, 1.03],
                         [-0.1, 0.92, -0.1, 0.92, -0.1, 0.92]]]]}
    name = {"part": "product name line 2", "words": "Blossom", "ink": "#D85457", "box": [0.22, 0.70, 0.88, 0.75]}
    mark = {"part": "BBROSE wordmark", "box": [0.25, 0.24, 0.76, 0.28]}
    oval = {"part": "oval", "shape": "ellipse", "centre": [0.5, 0.26], "half": [0.38, 0.05], "angle": 0.0,
            "fill": "#F6E6E4", "box": [0.12, 0.21, 0.88, 0.31]}
    front = {"face_aspect": 0.2992, "shapes": {"shapes": [band], "types": [name], "marks": [mark], "windows": [oval]}}
    laid, record = uniform_layout(front, 57.0, 123.0)
    k = 0.2992 / (57.0 / 123.0)
    assert record["scale"] == [round(k, 4), 1.0] and abs(record["block_mm"][0] - 0.2992 * 123.0) < 0.05
    got = laid["shapes"]["types"][0]["box"]
    assert abs((got[2] - got[0]) - 0.66 * k) < 1e-9 and abs((got[0] + got[2]) / 2.0 - (0.5 + (0.55 - 0.5) * k)) < 1e-9
    assert got[1] == 0.70 and got[3] == 0.75                                    # its height as the concept sets it
    assert abs(laid["shapes"]["windows"][0]["half"][0] - 0.38 * k) < 1e-9
    assert laid["shapes"]["shapes"][0] == band                                # edge to edge: spans the panel
    same, none = uniform_layout(dict(front, face_aspect=57.0 / 123.0), 57.0, 123.0)
    assert none is None and same["shapes"]["types"][0]["box"] == name["box"]


def test_his_findings_123_a_panel_with_nothing_from_a_picture_continues_the_front():
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (2): "Where a
    panel still has nothing from a picture, it CONTINUES the front: Garden Wrap's rose field runs across every panel
    unbroken; the scallop band runs all the way round; sides use the front's type style, smaller and lighter (never a
    giant bold name); the back keeps the same ground and pattern (faint), with the info sticker on top."]
    The front's field and its band, run edge to edge, continued on the back and both sides — [re-pinned by his goal of
    2026-10-10, items 5 and 9: "Draw ONE continuous scallop ... round the whole carton"; "keep the concept's organic
    garden, never mirrored"] the field moved onto each, never mirrored, the band the one scallop round the whole row —
    the field faint on the back; each side's name in the front's own face a weight lighter, at most half its size, and no
    rose graphic where the field runs round."""
    from apps.ire.compose import BACK_FIELD_OPACITY, SIDE_NAME_MIN_PT, SIDE_NAME_SHARE_OF_FRONT
    coords = _inside_carton(57, 37, 123)
    art = _field_art()
    field = {"part": "rose and foliage line illustration", "ink": "#E3A9A7", "strokes": [],
             "continued": dict(art, part_box=[0.0, 0.0, 1.0, 0.93], bloom=None)}
    band = {"part": "scalloped band", "ink": "#E9A8A7", "box": [-0.1, 0.92, 1.1, 1.0], "edges": {"left": [0.92, 1.0]},
            "cubics": [[[[-0.1, 0.92], [0.5, 0.88, 0.5, 0.88, 1.1, 0.92], [1.1, 1.0, 1.1, 1.0, 1.1, 1.0],
                         [-0.1, 1.0, -0.1, 1.0, -0.1, 1.0], [-0.1, 0.92, -0.1, 0.92, -0.1, 0.92]]]]}
    from apps.pipeline.services.concept_design_map import PICTURE_ENGLISH
    name = [{"part": "product name line %d" % (i + 1), "words": w, "ink": "#D85457", "source": PICTURE_ENGLISH,
             "box": [0.25, 0.66 + 0.05 * i, 0.75, 0.70 + 0.05 * i]} for i, w in enumerate(("Rose", "Blossom"))]
    front = {"shapes": {"state": "TRACED", "types": name, "shapes": [band], "lines": [field]}, "ground": "#F1E6E3",
             "continued": art, "side_copy": []}
    doc = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3", map_front=front)
    found = []

    def walk(n):
        found.append(n)
        for c in getattr(n, "children", None) or []:
            walk(c)
    walk(doc.root)
    by = {str(getattr(n, "name", "")): n for n in found}
    for panel in ("back", "side_left", "side_right"):
        assert "round-%s" % panel in by, panel
    left = by["round-side_left"]
    copies = [c for c in left.children if c.fill is not None and c.fill.color.to_hex().upper() == "#AF2B2F"]
    assert copies                                                             # the field, on the side
    front_panel = next(p for p in coords.panels if p.name == "front")
    fold = min(float(g.x) for g in left.clip if hasattr(g, "x"))               # the side's own left edge
    side_xs = [float(g.x) for c in copies for g in c.segments if hasattr(g, "x")]
    assert min(side_xs) < fold + 1.0                                           # it runs to the fold and beyond, clipped
    back = by["round-back"]
    faint = [c for c in back.children if c.fill is not None and c.fill.color.to_hex().upper() == "#AF2B2F"]
    assert faint and all(abs(c.fill.opacity - BACK_FIELD_OPACITY) < 1e-6 for c in faint)
    band = by["scallop-band-0"]                                                # the one scallop, round the side too
    band_xs = [float(g.x) for g in band.segments if hasattr(g, "x")]
    assert band.fill.color.to_hex().upper() == "#E9A8A7" and min(band_xs) <= fold < max(band_xs)
    hero = [n for n in found if str(getattr(n, "name", "")).startswith("product-name-hero-")]
    sides = [n for n in found if str(getattr(n, "name", "")).startswith("side-name-")]
    assert hero and sides
    assert all(n.font == "regular" for n in sides), [n.font for n in sides]
    assert all(n.size_pt <= max(SIDE_NAME_MIN_PT, SIDE_NAME_SHARE_OF_FRONT * max(h.size_pt for h in hero)) + 1e-6
               for n in sides), [(n.size_pt, [h.size_pt for h in hero]) for n in sides]
    assert not [n for n in found if str(getattr(n, "name", "")).startswith("side-graphic-")]
    assert front_panel.name == "front"


def test_his_findings_123_the_inside_follows_its_references_character_never_a_grid_of_stamps():
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (5): "Inside:
    follow the inside reference's character: loose, overlapping, painterly petals in deep berry on pink, varied sizes and
    rotations; never a rigid grid of identical stamps."] Our own flowers strewn loose over the inside: of many sizes,
    turned every way, overlapping each other, in three strengths of the one berry on the pink ground — and the
    same strew wherever the same inside is drawn again. [Re-pinned by his goal of 2026-10-10, item 10: "five long,
    pointed petals per flower, soft painted feel"] five petals and no round heart, the hearts pooled in a layer of
    their own."""
    from apps.ire.inside_print import CORE_STRENGTH, SCATTER_LAYERS, strewn_flowers
    spec = {"pattern": "motif", "motif": "flower", "petals": 5, "density": "sparse", "tone": "light",
            "motif_words": "bold rounded petal flowers"}
    box = (0.0, 0.0, 200.0, 150.0)
    layers = strewn_flowers(box, spec, 5)
    assert [strength for strength, _segs in layers] == list(SCATTER_LAYERS) + [CORE_STRENGTH]
    flowers = []
    for _strength, segs in layers[:-1]:
        starts = [i for i, g in enumerate(segs) if type(g).__name__ == "MoveTo"]
        assert len(starts) % 5 == 0                                         # whole flowers: five petals, no heart
        for f in range(0, len(starts), 5):
            chunk = segs[starts[f]:starts[f + 5] if f + 5 < len(starts) else len(segs)]
            xs = [g.x for g in chunk if hasattr(g, "x")]
            ys = [g.y for g in chunk if hasattr(g, "y")]
            flowers.append((min(xs), min(ys), max(xs), max(ys)))
    from collections import Counter
    sizes = [round(b[2] - b[0], 1) for b in flowers]
    assert max(sizes) >= 1.8 * min(sizes)                                   # varied sizes: never stamped alike
    assert max(Counter(sizes).values()) <= 0.05 * len(sizes)
    lefts = sorted({round(b[0] % 10.0, 1) for b in flowers})
    assert len(lefts) > 10                                                  # never on a grid's columns
    overlapping = sum(1 for i, a in enumerate(flowers) for b in flowers[i + 1:]
                      if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]))
    assert overlapping >= len(flowers) // 4                                 # loose, overlapping
    assert strewn_flowers(box, spec, 5) == layers                           # the same strew drawn again


def test_his_findings_123_every_panel_its_layout_picture_gives_is_drawn_from_it():
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (1): "NO
    GUESSED PANELS ... Every panel is drawn from it."] Each panel the carton's layout picture gives is drawn from its own
    map, clipped to it between the body's folds: the back's own shape, and the front's field only where its picture
    prints line art; a panel the picture does not give continues the front (his (2)), said why — each in the drawing's
    record, where it came from."""
    from apps.ire.compose import FRONT_TYPE_KEY
    coords = _inside_carton(57, 37, 123)
    art = _field_art()
    field = {"part": "rose field", "ink": "#E3A9A7", "strokes": [],
             "continued": dict(art, part_box=[0.0, 0.0, 1.0, 0.93], bloom=None)}
    square = [[[[0.1, 0.45], [0.9, 0.45, 0.9, 0.45, 0.9, 0.45], [0.9, 0.8, 0.9, 0.8, 0.9, 0.8],
                [0.1, 0.8, 0.1, 0.8, 0.1, 0.8], [0.1, 0.45, 0.1, 0.45, 0.1, 0.45]]]]
    label = {"part": "label area", "ink": "#FBF3F1", "box": [0.1, 0.45, 0.9, 0.8], "cubics": square}
    back = {"shapes": {"state": "TRACED", "shapes": [label], "bands": [], "types": [], "marks": []},
            "line_art": False, "bands_from_front": False, "face_aspect": 0.47, "edge_part": None,
            "drawn_from": "the layout picture"}
    right = {"shapes": {"state": "TRACED", "shapes": [], "bands": [], "types": [], "marks": []},
             "line_art": True, "bands_from_front": False, "face_aspect": 0.3, "edge_part": None,
             "drawn_from": "the layout picture"}
    front = {"shapes": {"state": "TRACED", "types": [], "shapes": [], "lines": [field]}, "ground": "#F1E6E3",
             "continued": art, "side_copy": [],
             "panels": {"back": back, "side_right": right, "side_left": {"continues": "the read did not find it"}}}
    doc = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3", map_front=front)
    found = []

    def walk(n):
        found.append(n)
        for c in getattr(n, "children", None) or []:
            walk(c)
    walk(doc.root)
    by = {str(getattr(n, "name", "")): n for n in found}
    drawn_back = by["Map back"]
    inside = []

    def under(n):
        inside.append(n)
        for c in getattr(n, "children", None) or []:
            under(c)
    under(drawn_back)
    assert drawn_back.clip and [n for n in inside if getattr(n, "fill", None) is not None
                                and n.fill.color.to_hex().upper() == "#FBF3F1"], [getattr(n, "name", "") for n in inside]
    assert by["round-back"].children == []                                      # no line art pictured: no field
    assert by["round-side_right"].children                                      # line art pictured: the field
    assert len(by["round-side_left"].children) >= 1                             # continues the front
    said = {r["panel"]: r["drawn_from"] for r in doc.metadata[FRONT_TYPE_KEY]["panels"]
            if str(r.get("drawn_from")) == "the layout picture"
            or str(r.get("drawn_from")).startswith("continues the front")}
    assert said == {"back": "the layout picture", "side_right": "the layout picture",
                    "side_left": "continues the front: the read did not find it"}


def test_his_findings_123_small_copy_on_a_field_stands_clear_its_clear_places_merged():
    """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "never over
    the pattern so the small copy gets lost".] The places a field is kept clear of are merged where they meet: two laid
    over each other cut nothing where they overlap (a clip fills by its winding) — Garden Wrap's "Hand Cream", spaced
    down into its Arabic's place, stood on the field. Two overlapping lines of small copy: one clear place."""
    from shapely.geometry import Polygon

    from apps.ire.compose_container import clear_rings
    rings = clear_rings([(0.3, 0.70, 0.8, 0.75), (0.3, 0.74, 0.8, 0.80), (0.3, 0.88, 0.7, 0.91)])
    assert len(rings) == 2                                                      # the two that meet, merged
    merged = Polygon(rings[0])
    assert abs(merged.area - 0.5 * 0.10) < 1e-9 and merged.exterior.is_ccw is False
    art = _field_art()
    field = {"part": "rose field", "ink": "#E3A9A7", "strokes": [],
             "continued": dict(art, part_box=[0.0, 0.0, 1.0, 1.0], bloom=None)}
    copy = [{"part": "descriptor %d" % i, "words": w, "ink": "#D85457", "source": "x", "box": b}
            for i, (w, b) in enumerate((("Hand Cream", [0.3, 0.70, 0.8, 0.725]), ("Rose cream", [0.3, 0.72, 0.8, 0.745])))]
    front = {"shapes": {"state": "TRACED", "types": copy, "shapes": [], "lines": [field]}, "ground": "#F1E6E3",
             "continued": art, "side_copy": []}
    doc = compose_components_graph(_inside_carton(57, 37, 123), product_name="Rose Blossom", tint="#F1E6E3",
                                   map_front=front)
    group = next(n for n, _p in doc.walk() if str(getattr(n, "name", "")).startswith("lineart-map-0"))
    assert len([g for g in group.clip if type(g).__name__ == "MoveTo"]) == 2      # the part's box and one clear place


# ---- [his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), items 5 and 9: "SCALLOP BAND: messy and inconsistent. Draw
# ---- ONE continuous scallop: every arc the same size, clean at panel edges, aligned across every fold and round the
# ---- whole carton." — "FRONT PATTERN is mirrored left-right (a damask): keep the concept's organic garden, never
# ---- mirrored."]

def _ragged_band(arcs=7):
    """A scalloped band as a picture traces it: arcs of uneven widths and heights along the front's foot, run past both
    its edges into the bleed — its outline as cubics in the front's fractions."""
    xs = [-0.1]
    widths = [0.13, 0.19, 0.15, 0.21, 0.12, 0.17, 0.16][:arcs]
    for wd in widths:
        xs.append(xs[-1] + wd)
    xs[-1] = 1.1
    ring = [[-0.1, 1.0], [-0.1, 0.93, -0.1, 0.93, -0.1, 0.93]]
    for i, (a, b) in enumerate(zip(xs, xs[1:])):
        rise = 0.03 + 0.012 * (i % 3)
        ring.append([a, 0.93 - rise, b, 0.93 - rise, b, 0.93])
    ring += [[1.1, 1.0, 1.1, 1.0, 1.1, 1.0], [-0.1, 1.0, -0.1, 1.0, -0.1, 1.0]]
    return {"part": "scalloped pink base band", "ink": "#EAA6A6", "box": [-0.1, 0.88, 1.1, 1.0],
            "edges": {"left": [0.93, 1.0], "right": [0.93, 1.0]}, "cubics": [[ring]]}


def _round_doc(band=None, field=True):
    coords = _inside_carton(57, 37, 123)
    art = _field_art()
    lines = [{"part": "rose and foliage line illustration", "ink": "#E3A9A7", "strokes": [],
              "continued": dict(art, part_box=[0.0, 0.0, 1.0, 0.93], bloom=None)}] if field else []
    front = {"shapes": {"state": "TRACED", "types": [], "shapes": [band] if band else [], "lines": lines},
             "ground": "#F1E6E3", "continued": art, "side_copy": []}
    doc = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3", map_front=front)
    found = []

    def walk(n):
        found.append(n)
        for c in getattr(n, "children", None) or []:
            walk(c)
    walk(doc.root)
    return coords, doc, {str(getattr(n, "name", "")): n for n in found}


def test_goal_1010_item5_one_scallop_of_equal_arcs_runs_round_the_whole_carton():
    """A band the picture traces ragged — arcs of five widths and three heights — drawn as ONE scallop round the body's
    whole row, back to right side: every arc the same width and height, a whole number of them round the carton so it
    meets itself where it is glued, its two free edges each at an arc's foot, one path between the body's folds, the
    picture's traced band gone from the front."""
    from apps.ire.compose import SCALLOP_SCHEMA, _PAGE_MARGIN_MM
    coords, doc, by = _round_doc(_ragged_band())
    path = by["scallop-band-0"]
    record, = doc.metadata[SCALLOP_SCHEMA]["bands"]
    gx0 = coords.bleed_polygon.bounds[0] - _PAGE_MARGIN_MM
    row = [p for p in coords.panels if p.name in ("back", "side_left", "front", "side_right")]
    rx0, rx1 = min(p.x for p in row) - gx0, max(p.x + p.width for p in row) - gx0
    assert abs(record["row_mm"] - (rx1 - rx0)) < 1e-6 and abs(record["row_mm"] - 2 * (57 + 37)) < 0.5
    feet = [g for g in path.segments if type(g).__name__ == "CubicTo"][1::2]          # each arc's foot
    peaks = [g for g in path.segments if type(g).__name__ == "CubicTo"][0::2]         # each arc's top
    assert len(feet) == record["arcs"] and abs(record["arcs"] * record["pitch_mm"] - record["row_mm"]) < 0.01
    assert abs(record["pitch_mm"] - 57.0 * 1.2 / 7) < 2.0                         # the picture's own arcs, about
    widths = [b.x - a.x for a, b in zip([path.segments[1]] + feet, feet)]
    assert max(widths) - min(widths) < 1e-6                                         # every arc the same width
    assert max(p.y for p in peaks) - min(p.y for p in peaks) < 1e-6                  # … and the same height
    assert abs(path.segments[1].x - rx0) < 1e-6 and abs(feet[-1].x - rx1) < 1e-6     # clean free edges, at an arc's foot
    assert not [n for n in by if n.startswith("shape-map-")]                       # the picture's band taken off the front
    panels = [n for n in by["scallop-round-0"].children]
    assert [n.name for n in panels] == ["scallop-0-%s" % p for p in ("back", "side_left", "front", "side_right")]
    assert all(n.children[0].segments == path.segments for n in panels)            # one path on every panel
    gy0 = coords.bleed_polygon.bounds[1] - _PAGE_MARGIN_MM
    for n, p in zip(panels, sorted(row, key=lambda q: q.x)):
        ys = [g.y for g in n.clip if hasattr(g, "y")]
        assert min(ys) >= p.y - gy0 and max(ys) <= p.y + p.height - gy0 + 1e-6      # inside its panel alone
    assert record["read_from_the_picture"] and record["arcs_the_picture_shows"] >= 3


def test_goal_1010_item9_the_garden_continues_round_moved_never_mirrored():
    """The front's field on each side and the back moved there — every point of it at the same shift from the front's,
    never turned over at a fold: the left side ends where the garden ends, the right side and the back begin where it
    begins."""
    coords, _doc, by = _round_doc()
    front_field = next(n for name, n in by.items() if name.endswith("-continued"))
    xs = [float(g.x) for g in front_field.segments if hasattr(g, "x")]
    for panel in ("side_left", "side_right", "back"):
        copy = by["round-%s" % panel].children[0]
        cx = [float(g.x) for g in copy.segments if hasattr(g, "x")]
        shifts = {round(c - x, 6) for c, x in zip(cx, xs)}
        assert len(shifts) == 1, (panel, sorted(shifts)[:3])                        # moved, every point alike
        assert len({round(c + x, 6) for c, x in zip(cx, xs)}) > 1                    # never a mirror
    left = next(p for p in coords.panels if p.name == "side_left")
    front = next(p for p in coords.panels if p.name == "front")
    copy = by["round-side_left"].children[0]
    shift = max(float(g.x) for g in copy.segments if hasattr(g, "x")) - max(xs)
    assert abs(shift - ((left.x + left.width) - (front.x + front.width))) < 1e-6   # it ends where the garden ends


# ---- [his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face
# ---- closest to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy
# ---- house bold; "Hand Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh. No
# ---- hard rectangle cut out of the roses behind it; soft breathing room as the concept shows, and the soft oval
# ---- cartouche behind the BBROSE logo."]

def _garden_wrap_front(faces):
    from apps.pipeline.services.concept_design_map import PICTURE_ENGLISH
    art = _field_art()
    field = {"part": "rose and foliage line illustration", "ink": "#E3A9A7", "strokes": [],
             "continued": dict(art, part_box=[0.0, 0.0, 1.0, 0.93], bloom=None)}
    types = [{"part": "product name line 1", "words": "Rose", "ink": "#DD6367", "ink_read": "#DD6367",
              "lettering": "sans", "source": PICTURE_ENGLISH, "box": [0.30, 0.62, 0.79, 0.68]},
             {"part": "product name line 2", "words": "Blossom", "ink": "#C8444D", "ink_read": "#DD6367",
              "lettering": "sans", "source": PICTURE_ENGLISH, "box": [0.23, 0.69, 0.87, 0.75]},
             {"part": "product descriptor English", "words": "Hand Cream", "ink": "#D13D46", "lettering": "serif",
              "source": PICTURE_ENGLISH, "box": [0.33, 0.76, 0.80, 0.78]},
             {"part": "product descriptor Arabic", "words": "كريم اليدين", "ink": "#DF8889", "lettering": "arabic",
              "source": "his brief's front copy", "box": [0.28, 0.79, 0.79, 0.82]}]
    mark = {"part": "BBROSE wordmark", "box": [0.23, 0.23, 0.78, 0.27], "ink": "#C39563"}
    window = {"part": "oval cartouche behind wordmark", "shape": "ellipse", "centre": [0.5, 0.25], "half": [0.39, 0.05],
              "angle": 0.0, "fill": "#F6E6E4", "box": [0.11, 0.20, 0.89, 0.30]}
    return {"shapes": {"state": "TRACED", "types": types, "lines": [field], "windows": [window], "marks": [mark]},
            "ground": "#F1E6E3", "continued": art, "side_copy": [], "soft_room": True,
            **({"front_faces": faces} if faces else {})}


def test_goal_1010_item6_a_soft_designs_sans_is_the_rounded_one():
    """The two granted sans he names: the rounded Quicksand where the design's words make it soft (123's brief: "soft,
    romantic, girly"), the crisp Montserrat where nothing does; the name at its weight, the copy a step lighter, the
    Arabic in Tajawal — each a static instance of the granted file."""
    import os

    from apps.ire import front_faces
    soft = front_faces.choose("Audience: women 18-30, soft, romantic, girly, gift-able.")
    crisp = front_faces.choose("Mood: clinical, precise, modern.")
    assert (soft["family"], crisp["family"]) == ("Quicksand", "Montserrat")
    assert soft["soft_words"] == ["soft", "girly"]
    assert soft["copy_weight"] < soft["name_weight"]
    for role in front_faces.ROLES:
        assert os.path.exists(soft["roles"][role]["path"]), role
    assert soft["roles"][front_faces.ARABIC_ROLE]["name"].startswith("Tajawal")


def test_goal_1010_item6_the_front_in_its_own_sans_one_colour_on_soft_breathing_room(tmp_path):
    """Garden Wrap's front: its name in the rounded sans and ONE colour (the ink its picture reads both lines in, never
    its two pinks), its copy in the same family, lighter, its Arabic in Tajawal — never the house's bold nor Naskh; the
    roses never cut by a rectangle round its type: soft rooms of its ground laid over them, rounded; and the oval its
    mark stands in drawn soft — then emitted in those very faces."""
    from apps.ire import front_faces
    faces = front_faces.choose("soft, romantic, girly")
    coords = _inside_carton(57, 37, 123)
    doc = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3",
                                   map_front=_garden_wrap_front(faces))
    found = []

    def walk(n):
        found.append(n)
        for c in getattr(n, "children", None) or []:
            walk(c)
    walk(doc.root)
    hero = [n for n in found if str(getattr(n, "name", "")).startswith("product-name-hero-")]
    assert hero and {n.font for n in hero} == {front_faces.NAME_ROLE}
    assert {n.color.to_hex().upper() for n in hero} == {"#DD6367"}                 # one colour
    copy = [n for n in found if str(getattr(n, "name", "")).startswith("front-descriptor-")]
    assert {n.font for n in copy if not n.rtl} == {front_faces.COPY_ROLE}
    assert {n.font for n in copy if n.rtl} == {front_faces.ARABIC_ROLE}
    rooms = [n for n in found if str(getattr(n, "name", "")).startswith("soft-room-")]
    assert len(rooms) == 7 and all(n.fill.opacity < 0.5 for n in rooms)
    field = next(n for n in found if isinstance(n, Group) and str(n.name).startswith("lineart-map-0"))
    assert sum(1 for g in field.clip if type(g).__name__ == "MoveTo") == 1          # no hole cut in the roses
    # [his goal of 2026-10-13, (8): "Glow is a real soft blur, never a stack of hard bands"] the oval's soft edge one
    # smooth mesh ring out to the ground — it was four rings stacked
    soft = [n for n in found if str(getattr(n, "name", "")).startswith("window-map-0-soft")]
    assert len(soft) == 1 and soft[0].fill.type == "mesh"
    assert doc.metadata["front_faces"]["family"] == "Quicksand"
    out = emit_pdf_ai(doc, str(tmp_path / "front.ai"))
    with fitz.open(out) as pdf:
        used = " ".join(f[3] for f in pdf[0].get_fonts())
        text = pdf[0].get_text()
    assert "Quicksand" in used and "Tajawal" in used, used
    assert "Rose" in text and "Blossom" in text and "Hand Cream" in text
    plain = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3",
                                     map_front=_garden_wrap_front(None))
    plain_hero = [n for n, _p in plain.walk() if str(getattr(n, "name", "")).startswith("product-name-hero-")]
    assert {n.font for n in plain_hero} == {"bold"}                                # a front with no faces: as before


# ---- [his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 7: "BARCODE: my number prints correctly but is cut at
# ---- the sticker's edge. Always whole, inside the sticker, with quiet zones. No number from me = no barcode."]

def _black(colour) -> bool:
    if not colour:
        return False
    if len(colour) == 4:
        return colour[3] > 0.9 and max(colour[:3]) < 0.2
    return max(colour) < 0.2                # the label's rich black, never a pure 0


def ean_bars_mm(path):
    """The finished file's barcode, measured: ``(its bars' box, mm, its module, its tallest bar, the white sticker round
    it)`` — the bars every thin black rectangle standing in a row, the sticker the smallest white shape round them; None
    with no bars."""
    k = 25.4 / 72.0
    with fitz.open(path) as pdf:
        drawings = pdf[0].get_drawings()
    bars = [d["rect"] for d in drawings if _black(d.get("fill")) and d["rect"].width * k < 1.5
            and d["rect"].height * k > 3.0 and all(it[0] == "re" for it in d["items"])]
    if len(bars) < 20:
        return None
    x0, y0 = min(r.x0 for r in bars) * k, min(r.y0 for r in bars) * k
    x1, y1 = max(r.x1 for r in bars) * k, max(r.y1 for r in bars) * k
    module = min(r.width for r in bars) * k
    tallest = max(r.height for r in bars) * k
    whites = [d["rect"] for d in drawings if d.get("fill") and min(d["fill"][:3]) > 0.97 and len(d["fill"]) == 3
              and d["rect"].x0 * k <= x0 and d["rect"].y0 * k <= y0 and d["rect"].x1 * k >= x1
              and d["rect"].y1 * k >= y1]
    sticker = min(whites, key=lambda r: r.width * r.height) if whites else None
    return (x0, y0, x1, y1), module, tallest, (sticker.x0 * k, sticker.y0 * k, sticker.x1 * k, sticker.y1 * k) \
        if sticker else None


def test_goal_1010_item7_the_barcode_is_whole_inside_the_sticker_with_its_quiet_zones(tmp_path):
    """His number drawn as a whole EAN-13 at its own proportions — its bars as tall as its size gives them (80 % where
    the sticker holds it), never cut short — inside the sticker, its quiet zones clear (eleven modules before it, seven
    after); with no number, no barcode at all; and the native file draws the same bars."""
    from apps.dielines.exporters.label_layout import EAN_MAGNIFICATION
    coords = _inside_carton(57, 37, 123)
    doc = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3",
                                   panel_info=dict(_INFO, barcode_ean="5061030633823"))
    measured = ean_bars_mm(emit_pdf_ai(doc, str(tmp_path / "ean.ai")))
    assert measured is not None
    (x0, y0, x1, y1), module, tallest, sticker = measured
    assert abs(module - 0.33 * EAN_MAGNIFICATION) < 0.01                       # 80 %, as its sticker holds it
    assert tallest >= 0.9 * 22.85 * EAN_MAGNIFICATION                          # whole: never cut short
    assert sticker is not None
    assert x0 - sticker[0] >= 11 * module and sticker[2] - x1 >= 7 * module     # its quiet zones inside the sticker
    assert y0 > sticker[1] and y1 < sticker[3]


def test_goal_1010_item7_no_number_from_him_no_barcode(tmp_path):
    """With no number from him, no barcode at all — never a placeholder."""
    coords = _inside_carton(57, 37, 123)
    none = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3",
                                    panel_info=dict(_INFO, barcode_ean=""))
    assert ean_bars_mm(emit_pdf_ai(none, str(tmp_path / "none.ai"))) is None


def test_goal_1010_item7_the_native_file_draws_the_same_bars():
    """The native .ai's label carries his barcode too — it had none — each bar and its digits as the PDF draws them."""
    from apps.dielines.exporters import label_layout as LL
    shapes = LL.ean_shapes("5061030633823", 22.85 * 72.0 / 25.4)
    bars = [s for s in shapes if s[0] == "bar"]
    assert len(bars) >= 30 and [s for s in shapes if s[0] == "digits"]
    module = min(s[3] for s in bars) * 25.4 / 72.0
    assert abs(module - 0.33) < 0.01                                                # its own 100 % module


# ---- [his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 8: "The ℮ prints as a plain "e": it must be the real
# ---- estimated sign everywhere."]

def test_goal_1010_item8_the_estimated_sign_is_drawn_never_left_to_a_face(tmp_path):
    """The ℮ wherever it is set — the sticker's NET WT row, a front's size line — drawn as the sign itself, a filled
    shape in the room its face gives it: never a glyph of the face (Noto Sans draws a light "e"); the words round it
    untouched."""
    coords = _inside_carton(57, 37, 123)
    doc = compose_components_graph(coords, product_name="Rose Blossom", tint="#F1E6E3",
                                   panel_info=dict(_INFO, net_weight="60 ml ℮ 2 fl oz"))
    out = emit_pdf_ai(doc, str(tmp_path / "sign.ai"))
    with fitz.open(out) as pdf:
        text = pdf[0].get_text()
    assert "℮" not in text and "60 ml" in text and "2 fl oz" in text


def test_goal_1010_item8_the_native_file_and_the_svg_twin_draw_the_sign_too():
    """The native .ai sets the run's words as items and each ℮ as the sign's own path between them; the SVG twin the
    same — never the face's "e"."""
    from apps.ire import estimated_sign
    from apps.ire.emitters import native_ai
    from apps.dielines.exporters.counter_display_files import _resolve_fonts
    regular = _resolve_fonts()[0]
    pieces = estimated_sign.pieces("60 ml ℮ 2 fl oz", 10.0, 20.0, 8.0, regular)
    kinds = [p[0] for p in pieces]
    assert kinds == ["text", "sign", "text"]
    sign = pieces[1][1]
    xs = [op[i] for op in sign for i in range(1, len(op), 2)]
    from reportlab.pdfbase.pdfmetrics import stringWidth
    space = stringWidth(" ", regular, 8.0) * 25.4 / 72.0
    ink = [op[i] for op in sign for i in range(2, len(op), 2)]
    # in its own room and the spaces beside it, never past them — and as tall as the run's capitals, never an "e"'s
    room = estimated_sign.sign_room(regular, 8.0) * 25.4 / 72.0    # [his goal of 2026-10-12, (5)] a 3 mm sign's room
    assert pieces[2][2] - room - space < min(xs) and max(xs) < pieces[2][2] + space and pieces[0][1].endswith(" ")
    assert max(ink) - min(ink) >= 0.68 * 8.0 * 25.4 / 72.0
    item = native_ai._item(TextRun(name="size", text="60 ml ℮ 2 fl oz", x=10.0, y=20.0, size_pt=8.0,
                                   color=__import__("apps.ire.graph", fromlist=["Color"]).Color.from_hex("#C7404A")),
                           0.0, {"regular": regular}, True, [])
    assert item["t"] == "g" and [k["t"] for k in item["kids"]] == ["x", "p", "x"]
    assert estimated_sign.SIGN not in "".join(k.get("text", "") for k in item["kids"])
    svg = estimated_sign.svg_text(5.0, 9.0, "NET WT: 60 ml \u212e 2 fl oz", 2.5, 'font-size="2.5"')
    assert "\u212e" not in svg and svg.count("<path") == 1 and svg.count("<text") == 2


# ---- [his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 10: "INSIDE: still round blobs on off-white. Follow the
# ---- inside reference: five long, pointed petals per flower, soft painted feel, deep berry on a bright pink ground,
# ---- varied sizes and turns."]

def _two_colour_picture(ground=(246, 160, 199), ink=(160, 18, 64)):
    """A picture like his inside reference: a bright pink ground with deep berry petals over two fifths of it."""
    import io as _io

    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 300), ground)
    draw = ImageDraw.Draw(img)
    for cx, cy in ((80, 80), (220, 90), (150, 220)):
        draw.ellipse((cx - 60, cy - 50, cx + 60, cy + 50), fill=ink)
    out = _io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def test_goal_1010_item10_the_inside_is_painted_in_its_references_own_berry_on_pink():
    """His reference's own two colours, measured from its pixels at $0 — its bright pink the ground, its deep berry the
    ink — drawn so: never the front's off-white and its red."""
    colours = IP.reference_colours(_two_colour_picture())
    def rgb(h):
        return [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    ground, ink = rgb(colours["ground"]), rgb(colours["ink"])
    assert abs(ground[0] - 246) < 12 and abs(ground[2] - 199) < 12                # the bright pink ground
    assert abs(ink[0] - 160) < 12 and ink[1] < 40                                   # the deep berry
    reading = {"pattern": "motif", "tone": "light", "density": "sparse", "motif_words": "petal flowers",
               "colours": colours}
    spec = IP.plan("referenced", [reading], "bold berry petal flowers on pink", _INSIDE_FRONT)
    assert (spec["light"], spec["dark"]) == (colours["ground"], colours["ink"])
    assert spec["colours_from"].startswith("his inside reference")
    assert IP.reference_colours(b"not a picture") is None


def test_goal_1010_item10_five_long_pointed_petals_a_flower_its_heart_pooled_darker():
    """Each flower five petals, each long and pointed — far longer than it is wide, narrow at the heart and at its tip —
    no round heart drawn; its heart pooled darker as paint pools; bold flowers of many sizes, turned every way."""
    import random
    from apps.ire.inside_print import CORE_STRENGTH, SCATTER_LAYERS, loose_flower, strewn_flowers
    rnd = random.Random(7)
    rings = loose_flower(5, rnd)
    assert len(rings) == 5                                                        # five petals, no heart ring
    for ring in rings:
        base, tip = ring[0], ring[1][-2:]
        reach = ((tip[0] - base[0]) ** 2 + (tip[1] - base[1]) ** 2) ** 0.5
        ax, ay = (tip[0] - base[0]) / reach, (tip[1] - base[1]) / reach
        widest = max(abs((pt[i] - base[0]) * -ay + (pt[i + 1] - base[1]) * ax)
                     for pt in ring[1:] for i in range(0, len(pt), 2))
        # long: its reach over twice its handles' widest (the curve itself narrower than its handles)
        assert reach >= 2.4 * widest, (reach, widest)
    spec = {"pattern": "motif", "motif": "flower", "petals": 5, "density": "sparse", "tone": "light",
            "motif_words": "petal flowers"}
    layers = strewn_flowers((0.0, 0.0, 200.0, 150.0), spec, 5)
    strengths = [s for s, _segs in layers]
    assert strengths[:-1] == [s for s in SCATTER_LAYERS if s in strengths[:-1]] and strengths[-1] == CORE_STRENGTH
    petals = sum(1 for s, segs in layers[:-1] for g in segs if type(g).__name__ == "MoveTo")
    hearts = sum(1 for g in layers[-1][1] if type(g).__name__ == "MoveTo")
    assert petals % 5 == 0 and hearts == petals                                    # every flower's heart pooled
    flowers = petals // 5
    assert 10 <= flowers <= 120                                                    # bold: never a fine all-over print


def _curled_band(pitch=0.19):
    """A scalloped band as a photograph of a box traces it: even arcs ``pitch`` of the front wide along its foot, its
    two ends curled up where the box turns away from the camera — its outline as cubics in the front's fractions."""
    ring = [[-0.1, 1.0], [-0.1, 0.86, -0.1, 0.86, -0.1, 0.86], [0.0, 0.93, 0.0, 0.93, 0.0, 0.93]]
    x = 0.0
    while x + pitch <= 1.0 + 1e-9:
        ring.append([x, 0.93 - 0.02, x + pitch, 0.93 - 0.02, x + pitch, 0.93])
        x += pitch
    ring += [[1.1, 0.86, 1.1, 0.86, 1.1, 0.86], [1.1, 1.0, 1.1, 1.0, 1.1, 1.0], [-0.1, 1.0, -0.1, 1.0, -0.1, 1.0]]
    return {"part": "scalloped pink base band", "ink": "#EAA6A6", "box": [-0.1, 0.86, 1.1, 1.0],
            "edges": {"left": [0.86, 1.0], "right": [0.86, 1.0]}, "cubics": [[ring]]}


def test_goal_1010_item5_a_band_curled_at_its_ends_still_reads_its_own_arcs():
    """[His goal of 2026-10-10, item 5: "every arc the same size"] Garden Wrap's band as its photograph traced it — even
    arcs about 11 mm wide, its ends curled up where the box turns — read across the front's middle, its depth between
    its edge's lower and upper tenths: its arcs' width the picture's own, never the curl's; and bubbles, never flatter
    than SCALLOP_MIN_RISE of their width (the traced outline reads them flatter than the concept draws them)."""
    from apps.ire.compose import SCALLOP_MIN_RISE, SCALLOP_SCHEMA
    _coords, doc, _by = _round_doc(_curled_band())
    record, = doc.metadata[SCALLOP_SCHEMA]["bands"]
    assert record["read_from_the_picture"] and record["arcs_the_picture_shows"] >= 3
    assert abs(record["pitch_mm"] - 0.19 * 57.0) < 1.5, record                     # the picture's arcs, not the curl's
    assert record["rise_mm"] >= SCALLOP_MIN_RISE * record["pitch_mm"] - 1e-6       # a bubble, never flatter


# --- [his bug on design 124, 2026-10-12: "the layered Illustrator file must carry EVERY drawn element, each on its
# --- named layer"] ---------------------------------------------------------------------------------------------------

def _b124_doc(*nodes):
    from apps.ire.graph import Document, Group
    return Document(page_w=200.0, page_h=150.0, title="b124", root=Group(name="Artwork", children=list(nodes)))


def _b124_box(name, x, y, w, h, fill):
    from apps.ire.graph import ClosePath, LineTo, MoveTo, Path
    return Path(name=name, fill=fill, segments=[MoveTo(x=x, y=y), LineTo(x=x + w, y=y), LineTo(x=x + w, y=y + h),
                                                LineTo(x=x, y=y + h), ClosePath()])


def test_his_bug_124_a_group_that_draws_nothing_is_never_masked_and_a_refused_mask_leaves_no_path():
    """124's lid lay under its empty map group's clipping path: Illustrator refused a mask over nothing and left the
    path as it makes a new one, filled white and stroked black. A group that draws nothing is not carried; every mask's
    path is made unpainted, closed, and removed where Illustrator refuses it — counted where it masks."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import Color, Group, SolidFill
    art = _b124_box("rose", 10, 10, 50, 40, SolidFill(color=Color.from_hex("#E8A0B0")))
    outline = [s for s in art.segments]
    doc = _b124_doc(Group(name="LID ART", children=[art], clip=outline),
                    Group(name="map-front-within-the-outline", children=[], clip=outline))
    data = native_ai.tree(doc)
    names = [i["name"] for i in native_ai._walk(data["boards"][0]["layers"][0]["items"])]
    assert "LID ART" in names and "rose" in names and "map-front-within-the-outline" not in names
    js = native_ai.script(data, "/tmp/b124.ai")
    assert "cp.filled = false; cp.stroked = false;" in js and "cp.closed = true;" in js
    assert "cp.remove();" in js and "g.pageItems.length > 0" in js and "report.clips++" in js
    assert sum(1 for i in native_ai._walk(data["boards"][0]["layers"][0]["items"]) if i.get("clip")) == 1


def test_his_bug_124_a_gradient_is_carried_as_a_gradient_its_stops_and_its_run():
    """The sky's 96 bands came through flat — each painted its first stop. A gradient is sent with its stops and its run
    (a line's ends; a circle's centre and radius) and built as Illustrator's own gradient, counted."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import Color, GradientFill, GradientStop, Rect
    band = Rect(name="lid-sky-0", x=10, y=10, w=100, h=5, fill=GradientFill(kind="linear", x1=10, y1=10, x2=110, y2=10,
                stops=[GradientStop(offset=0.0, color=Color.from_hex("#D8B4E2")),
                       GradientStop(offset=0.5, color=Color.from_hex("#F4C2C2")),
                       GradientStop(offset=1.0, color=Color.from_hex("#A8DADC"))]))
    data = native_ai.tree(_b124_doc(band))
    item = next(i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"]) if i["name"] == "lid-sky-0")
    grad = item["fill"]["grad"]
    assert [s[0] for s in grad["stops"]] == [0.0, 0.5, 1.0] and grad["from"] == [10, 10] and grad["to"] == [110, 10]
    js = native_ai.script(data, "/tmp/b124.ai")
    # [his goal of 2026-10-13, (10)] built, then turned to the drawing's run (Illustrator runs it across the box)
    assert "doc.gradients.add()" in js and "var made = gradientColor(it.fill.grad, item); item.fillColor = made.gc;" in js


def test_his_bug_124_a_barcode_is_carried_as_its_bars_and_its_digits():
    """A barcode was left out of the layered file — every carton's EAN. It is carried as the PDF draws it: its bars,
    each a black path inside its own box, and its digits, live text."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import Barcode
    data = native_ai.tree(_b124_doc(Barcode(name="ean", symbology="ean13", value="629100000001", x=20, y=30, w=37.29,
                                            h=25.93)))
    items = list(native_ai._walk(data["boards"][0]["layers"][0]["items"]))
    bars = [i for i in items if i["t"] == "p" and i["name"].startswith("ean-bar-")]
    digits = "".join(i["text"] for i in items if i["t"] == "x")
    assert data["skipped"] == [] and len(bars) >= 30 and digits.replace(" ", "").startswith("62910000000")
    xs = [v for b in bars for s in b["segs"] if s[0] != "Z" for v in s[1::2]]
    ys = [v for b in bars for s in b["segs"] if s[0] != "Z" for v in s[2::2]]
    assert 19.9 <= min(xs) and max(xs) <= 57.4 and 29.9 <= min(ys) and max(ys) <= 56.0


def test_his_bug_124_a_pattern_is_carried_as_its_marks_inside_its_shape():
    """A pattern fill came through as one flat colour. It is carried as the PDF paints it: its marks — lines stroked,
    dots filled — masked to the shape."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import Color, PatternFill, Rect
    lines = Rect(name="engraved-field", x=10, y=10, w=40, h=30, fill=PatternFill(kind="lines", color=Color.from_hex(
        "#B97745"), spacing_mm=2.0, weight_mm=0.2, angle_deg=30.0))
    dots = Rect(name="pattern-repeat", x=60, y=10, w=40, h=30, fill=PatternFill(kind="dots", color=Color.from_hex(
        "#B97745"), spacing_mm=3.0, weight_mm=0.8))
    data = native_ai.tree(_b124_doc(lines, dots))
    items = {i["name"]: i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"])}
    assert items["engraved-field"]["t"] == "g" and items["engraved-field"]["clip"]
    marks = items["engraved-field-pattern-lines"]
    assert marks["stroke"]["w"] == 0.2 and marks["fill"] is None and sum(1 for s in marks["segs"] if s[0] == "M") > 10
    dotted = items["pattern-repeat-pattern-dots"]
    assert dotted["fill"] and dotted["stroke"] is None and sum(1 for s in dotted["segs"] if s[0] == "M") > 50


def test_his_bug_124_a_shadow_and_a_blend_are_carried_and_a_fade_is_named():
    """A soft shadow and a blend mode were left out. The shadow is carried as the PDF draws it — eight offset copies,
    each an eighth of its opacity — under its element; the blend mode is set on the element; a fade (an opacity mask
    Illustrator's scripting cannot make) is named in the record, its element carried at full strength."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import Color, Group, OpacityMask, Shadow, SolidFill
    motif = _b124_box("motif", 10, 10, 30, 30, SolidFill(color=Color.from_hex("#8C6D95")))
    motif.shadow = Shadow(color=Color.from_hex("#8C6D95"), opacity=0.3)
    motif.blend_mode = "multiply"
    faded = Group(name="faded", children=[_b124_box("petal", 60, 10, 20, 20, SolidFill(color=Color.from_hex(
        "#E8A0B0")))], opacity_mask=OpacityMask(kind="linear", x1=60, y1=10, x2=60, y2=30))
    data = native_ai.tree(_b124_doc(motif, faded))
    items = {i["name"]: i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"])}
    shadow = [i for n, i in items.items() if n.startswith("motif-shadow-")]
    assert len(shadow) == 8 and all(abs(i["o"] - 0.3 / 8) < 1e-9 for i in shadow)
    assert items["motif"]["blend"] == "multiply"
    assert data["effects_not_carried"] and data["effects_not_carried"][0].startswith("faded: its fade")
    assert "item.blendingMode = BlendModes[BLENDS[it.blend]]" in native_ai.script(data, "/tmp/b124.ai")


def test_his_bug_124_a_mask_of_many_paths_is_carried_whole_its_holes_kept():
    """A carton's inside print is masked by its outline AND its glue strip, wound the other way — a hole the drawing
    clips even-odd, so the glue stays clear. The native mask had kept the first path only and printed over the glue.
    Every path of a mask is sent; the script makes a mask of many paths with Illustrator's own Make Clipping Mask, on
    its own document brought to the front, and names a group it leaves unmasked."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import ClosePath, Color, Group, LineTo, MoveTo, SolidFill
    art = _b124_box("inside-ground", 10, 10, 100, 80, SolidFill(color=Color.from_hex("#5A1A20")))
    hole = [MoveTo(x=15, y=20), LineTo(x=15, y=70), LineTo(x=25, y=70), LineTo(x=25, y=20), ClosePath()]
    doc = _b124_doc(Group(name="Inside print", children=[art], clip=list(art.segments) + hole))
    data = native_ai.tree(doc)
    group = next(i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"]) if i["name"] == "Inside print")
    assert sum(1 for s in group["clip"] if s[0] == "M") == 2
    js = native_ai.script(data, "/tmp/b124.ai")
    assert 'doc.activate(); doc.selection = null; g.selected = true; app.executeMenuCommand("makeMask");' in js
    assert "cq.evenodd = true" in js and "if (!g.clipped)" in js


def test_his_bug_124_a_fill_and_a_stroke_are_carried_at_their_own_strength():
    """124's label rules are hairlines at a third of their colour's strength; the layered file drew them at full. A
    fill's and a stroke's own opacity are carried as the drawing paints them (a gradient at its strongest stop's) —
    one item where the two agree, else its fill and its stroke apart, each at its own."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import (ClosePath, Color, GradientFill, GradientStop, LineTo, MoveTo, Path, Rect, SolidFill,
                                Stroke)
    rose = Color.from_hex("#C77D9A")
    rule = Path(name="back-panel-1-rule", segments=[MoveTo(x=10, y=50), LineTo(x=150, y=50)],
                stroke=Stroke(color=rose, width_mm=0.15, opacity=0.35))
    panel = Rect(name="panel", x=10, y=60, w=80, h=40, fill=SolidFill(color=rose, opacity=0.5),
                 stroke=Stroke(color=rose, width_mm=0.3))
    wash = Rect(name="wash", x=100, y=60, w=80, h=40, fill=GradientFill(kind="linear", x1=100, y1=60, x2=180, y2=60,
                stops=[GradientStop(offset=0.0, color=rose, opacity=0.2), GradientStop(offset=1.0, color=rose,
                                                                                        opacity=0.6)]))
    tick = Path(name="tick", segments=[MoveTo(x=5, y=5), LineTo(x=8, y=5), LineTo(x=8, y=8), ClosePath()],
                fill=SolidFill(color=rose), opacity=0.85)
    data = native_ai.tree(_b124_doc(rule, panel, wash, tick))
    items = {i["name"]: i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"])}
    assert abs(items["back-panel-1-rule"]["o"] - 0.35) < 1e-9
    assert items["panel"]["t"] == "g" and abs(items["panel-fill"]["o"] - 0.5) < 1e-9
    assert items["panel-fill"]["stroke"] is None and items["panel-stroke"]["fill"] is None
    assert abs(items["panel-stroke"]["o"] - 1.0) < 1e-9
    assert abs(items["wash"]["o"] - 0.6) < 1e-9 and abs(items["tick"]["o"] - 0.85) < 1e-9


def test_his_bug_124_a_finish_is_drawn_on_page_one_as_the_drawing_depicts_it():
    """124's mark prints in rose-gold foil: the drawing paints it in the metal; the layered file had painted it in its
    own colour. An ink finish paints its element — and every element of a group it reaches — in its metal; a gloss is
    a highlight inside the element; a relief its outline lit and shadowed; a matte laminate has none."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import Color, Finish, Group, SolidFill
    gold = Color.from_hex("#B76E79")
    mark = _b124_box("logo", 10, 10, 30, 10, SolidFill(color=Color.from_hex("#8C6D95")))
    mark.finishes = [Finish(kind="foil", plate="FOIL_ROSE_GOLD", appearance=gold)]
    panel = _b124_box("panel", 50, 10, 40, 40, SolidFill(color=Color.from_hex("#F4C2C2")))
    panel.finishes = [Finish(kind="spot_uv", plate="SPOT_UV")]
    seal = _b124_box("seal", 100, 10, 20, 20, SolidFill(color=Color.from_hex("#F4C2C2")))
    seal.finishes = [Finish(kind="emboss", plate="EMBOSS")]
    leaf = _b124_box("leaf", 130, 10, 10, 10, SolidFill(color=Color.from_hex("#8AB6C8")))
    gilded = Group(name="gilded", children=[leaf], finishes=[Finish(kind="foil", plate="FOIL_ROSE_GOLD",
                                                                    appearance=gold)])
    data = native_ai.tree(_b124_doc(mark, panel, seal, gilded))
    items = {i["name"]: i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"])}
    assert items["logo"]["fill"]["c"] == native_ai._ink(gold) and items["leaf"]["fill"]["c"] == native_ai._ink(gold)
    assert items["panel-finished"]["kids"][0]["name"] == "panel"
    assert items["panel-spot_uv"]["clip"] and abs(items["panel-spot_uv-highlight"]["o"] - 0.14) < 1e-9
    assert {"seal-emboss-lit", "seal-emboss-shadowed"} <= set(items)
    assert items["seal-emboss-lit"]["stroke"]["w"] == 0.3 and abs(items["seal-emboss-lit"]["o"] - 0.55) < 1e-9


def test_his_bug_124_every_plate_is_its_own_artboard_and_layer_in_its_spot_colour_as_the_drawing_pages_them(tmp_path):
    """124's soft-touch and foil plates are the drawing's pages 2 and 3; the layered file had none. Every finish's
    plate follows the artwork on its own artboard — the drawing's pages, in their order — on its own named layer, each
    element it covers a full mask in a spot colour of the plate's name, cut by the masks it was cut by, a clear finish
    on a masked group its region; the plate's name in its corner."""
    from apps.ire.container_finishes import SCHEMA as FP
    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Finish, Group, SolidFill
    gold = Color.from_hex("#B76E79")
    lid = _b124_box("lid", 10, 10, 120, 80, SolidFill(color=Color.from_hex("#F4C2C2")))
    mark = _b124_box("logo", 20, 20, 30, 10, SolidFill(color=Color.from_hex("#8C6D95")))
    mark.finishes = [Finish(kind="foil", plate="FOIL_ROSE_GOLD", appearance=gold)]
    front = Group(name="FRONT_DIRECT_PRINT", children=[lid, mark], clip=list(lid.segments),
                  finishes=[Finish(kind="soft_touch", plate="SOFT_TOUCH")])
    doc = _b124_doc(front)
    data = native_ai.tree(doc)
    usage = {}
    emit_pdf_ai(doc, str(tmp_path / "drawing.ai"), usage_out=usage)
    pages = ["FINISH PLATE " + p["plate"] for p in usage[FP]["plates"]]
    assert [b["name"] for b in data["boards"]] == ["OUTSIDE"] + pages == ["OUTSIDE", "FINISH PLATE FOIL_ROSE_GOLD",
                                                                           "FINISH PLATE SOFT_TOUCH"]
    foil, soft = data["boards"][1], data["boards"][2]
    assert [lay["name"] for lay in foil["layers"]] == ["FINISH PLATE FOIL_ROSE_GOLD"]
    assert foil["ox"] == 200.0 + native_ai.ARTBOARD_GAP_MM and soft["ox"] == 2 * (200.0 + native_ai.ARTBOARD_GAP_MM)
    cut = foil["layers"][0]["items"][0]
    assert cut["clip"] and cut["kids"][0]["name"] == "logo-foil_rose_gold"
    assert cut["kids"][0]["fill"] == {"c": [0.0, 0.0, 0.0], "o": 1.0, "spot": "FOIL_ROSE_GOLD"}
    region = soft["layers"][0]["items"][0]
    assert region["name"] == "FRONT_DIRECT_PRINT-soft_touch" and region["fill"]["spot"] == "SOFT_TOUCH"
    assert soft["layers"][0]["items"][-1]["text"] == "FINISH PLATE SOFT_TOUCH - SOFT_TOUCH - IN REGISTER WITH PAGE 1"
    js = native_ai.script(data, "/tmp/b124.ai")
    assert "it.fill.spot ? spot(it.fill.spot, PLATE_INK)" in js and "if (!layerOf[lay.name])" in js


def test_his_bug_124_a_picture_the_drawing_places_is_placed_and_one_it_does_not_is_left_out_alike(tmp_path):
    """124's reference photo was left out of the layered file. A picture the drawing places is placed — at its place
    and its size, masked where the drawing masks it, embedded so the file carries it; one the drawing does not draw
    (its file not on this machine) is left out alike, and said."""
    import numpy as np
    from PIL import Image as PILImage

    from apps.ire.emitters import native_ai
    from apps.ire.graph import Image
    photo = tmp_path / "photo.png"
    PILImage.fromarray(np.full((60, 80, 3), 90, np.uint8)).save(photo)
    placed = Image(name="reference-photo", src=str(photo), x=140, y=10, w=50, h=40)
    masked = Image(name="swatch", src=str(photo), x=10, y=60, w=30, h=30,
                   clip=list(_b124_box("round", 10, 60, 30, 30, None).segments))
    gone = Image(name="gone", src=str(tmp_path / "not-there.png"), x=60, y=60, w=30, h=30)
    data = native_ai.tree(_b124_doc(placed, masked, gone))
    items = {i["name"]: i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"])}
    assert items["reference-photo"] == {"t": "i", "name": "reference-photo", "src": str(photo), "x": 140, "y": 10,
                                        "w": 50, "h": 40, "o": 1.0}
    assert items["swatch-masked"]["clip"] and items["swatch-masked"]["kids"][0]["name"] == "swatch"
    assert "gone" not in items and data["skipped"] == ["gone"]
    js = native_ai.script(data, "/tmp/b124.ai")
    assert "pl.file = new File(it.src);" in js and "pl.embed();" in js and "report.images++" in js


# --- [his bug on design 124, 2026-10-12: "Add a check that compares the layered file with the drawing (same elements,
# --- nothing missing), and make it fail if anything is dropped."] -------------------------------------------------------

def _b124_art():
    from apps.ire.graph import Color, Group, SolidFill
    lid = _b124_box("lid", 10, 10, 120, 80, SolidFill(color=Color.from_hex("#F4C2C2")))
    rose = _b124_box("rose", 30, 30, 40, 40, SolidFill(color=Color.from_hex("#D86A8A")))
    return _b124_doc(Group(name="LID ART", children=[lid, rose], clip=list(lid.segments)))


def test_his_bug_124_the_check_passes_a_file_that_carries_the_drawing_whole(tmp_path):
    """The drawing compared with itself: every element sent built, every place it inks inked — PASS."""
    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    doc = _b124_art()
    data = native_ai.tree(doc)
    drawing = emit_pdf_ai(doc, str(tmp_path / "drawing.ai"))
    verdict = native_ai.check(data, dict(native_ai.expected(data), errors=[]), drawing, drawing)
    assert verdict["state"] == native_ai.PASS and verdict["why"] is None and verdict["places_count"] == 0


def test_his_bug_124_the_check_fails_by_name_where_the_art_is_hidden_or_not_built(tmp_path):
    """124's file: every element built, the lid's art under a white path — FAIL, naming the places blank in the file.
    And a file one shape short, Illustrator's error said — FAIL, naming what was not built."""
    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, SolidFill, Stroke
    doc = _b124_art()
    data = native_ai.tree(doc)
    drawing = emit_pdf_ai(doc, str(tmp_path / "drawing.ai"))
    covered = _b124_art()
    white = _b124_box("mask-left-as-a-path", 10, 10, 120, 80, SolidFill(color=Color.from_hex("#FFFFFF")))
    white.stroke = Stroke(color=Color.from_hex("#231F20"), width_mm=0.35)
    covered.root.children.append(white)
    native = emit_pdf_ai(covered, str(tmp_path / "native.ai"))
    hidden = native_ai.check(data, dict(native_ai.expected(data), errors=[]), drawing, native)
    assert hidden["state"] == native_ai.FAIL and "blank in the file where the drawing draws" in hidden["why"]
    assert hidden["places_count"] >= 100 and {p["kind"] for p in hidden["places"]} == {"missing"}
    short = dict(native_ai.expected(data), errors=["map-front: There must be at least two page items"])
    short["paths"] -= 1
    said = native_ai.check(data, short, drawing, drawing)
    assert said["state"] == native_ai.FAIL and "not built: 1 of 2 paths" in said["why"]
    assert "Illustrator said: map-front" in said["why"]


def test_his_bug_124_a_picture_or_a_plate_the_file_lacks_fails_by_name(tmp_path):
    """124's reference photo and its finishes' plates are drawn: a file without the picture fails — the picture not
    built, its place blank — and a file without a plate's page fails, the plate's artboard named."""
    import numpy as np
    from PIL import Image as PILImage

    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Finish, Image
    photo = tmp_path / "photo.png"
    PILImage.fromarray(np.full((60, 80, 3), 90, np.uint8)).save(photo)
    with_photo = _b124_art()
    with_photo.root.children.append(Image(name="reference-photo", src=str(photo), x=140, y=10, w=50, h=40))
    data = native_ai.tree(with_photo)
    assert data["skipped"] == [] and native_ai.expected(data)["images"] == 1
    drawing = emit_pdf_ai(with_photo, str(tmp_path / "drawing.ai"))
    without = emit_pdf_ai(_b124_art(), str(tmp_path / "without.ai"))
    built = dict(native_ai.expected(data), images=0, errors=[])
    lacks = native_ai.check(data, built, drawing, without)
    assert lacks["state"] == native_ai.FAIL and "not built: 0 of 1 images" in lacks["why"]
    assert "blank in the file where the drawing draws" in lacks["why"]
    foiled = _b124_art()
    foiled.root.children[0].children[1].finishes = [Finish(kind="foil", plate="FOIL_ROSE_GOLD",
                                                           appearance=Color.from_hex("#B76E79"))]
    data = native_ai.tree(foiled)
    assert [b["name"] for b in data["boards"]] == ["OUTSIDE", "FINISH PLATE FOIL_ROSE_GOLD"]
    drawing = emit_pdf_ai(foiled, str(tmp_path / "foiled.ai"))
    one_page = emit_pdf_ai(_b124_art(), str(tmp_path / "one_page.ai"))
    plate = native_ai.check(data, dict(native_ai.expected(data), errors=[]), drawing, one_page)
    assert plate["state"] == native_ai.FAIL and "FINISH PLATE FOIL_ROSE_GOLD: the artboard is not in the file" in \
        plate["why"]
    assert native_ai.check(data, dict(native_ai.expected(data), errors=[]), drawing, drawing)["state"] == native_ai.PASS



def test_goal_1013_agree_the_check_fails_a_file_whose_smooth_colours_are_not_the_drawings(tmp_path):
    """[His goal of 2026-10-13, (10): "colour drift".] 125's drawing and its layered file disagreed on its window's glow
    and field — the drawing washed out by a leaked alpha — and the check, reading ink only, passed them. An RGB file is
    read for its colours too, where both files are smooth: a lid paler than the drawing's fails, its places named; the
    same pair passes a CMYK file's check (its colours not the drawing's own until his profile is set), and the drawing
    passes itself."""
    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, SolidFill
    doc = _b124_art()
    data = native_ai.tree(doc)
    assert data["space"] == "RGB"
    drawing = emit_pdf_ai(doc, str(tmp_path / "drawing.ai"))
    washed = _b124_art()
    washed.root.children[0].children[0].fill = SolidFill(color=Color.from_hex("#FBE9E9"))
    native = emit_pdf_ai(washed, str(tmp_path / "native.ai"))
    built = dict(native_ai.expected(data), errors=[])
    drift = native_ai.check(data, built, drawing, native)
    assert drift["state"] == native_ai.FAIL and "drawn in another colour than the drawing's" in drift["why"]
    assert {p["kind"] for p in drift["places"]} == {"colour"} and drift["places_count"] >= 100
    assert native_ai.check(dict(data, space="CMYK"), built, drawing, native)["state"] == native_ai.PASS
    assert native_ai.check(data, built, drawing, drawing)["state"] == native_ai.PASS

def test_his_bug_124_a_layered_file_that_fails_the_check_is_not_offered_the_reason_said(tmp_path, monkeypatch):
    """Built and checked against the design's own .ai: a file that carries it whole is offered; one that hides its art
    is not — the record says why, by name."""
    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, SolidFill
    from apps.ire.handoff import illustrator_exec
    doc = _b124_art()
    data = native_ai.tree(doc)
    drawing = emit_pdf_ai(doc, str(tmp_path / "drawing.ai"))
    covered = _b124_art()
    covered.root.children.append(_b124_box("white", 10, 10, 120, 80, SolidFill(color=Color.from_hex("#FFFFFF"))))
    made = {"file": doc}

    def run(jsx, timeout_s=0):
        emit_pdf_ai(made["file"], str(tmp_path / "n.ai"))
        return dict(native_ai.expected(data), executed=True, saved=True, errors=[])
    monkeypatch.setattr(illustrator_exec, "illustrator_available", lambda: True)
    monkeypatch.setattr(illustrator_exec, "run_jsx", run)
    good = native_ai.build(doc, str(tmp_path / "n.ai"), drawing=drawing)
    assert good["built"] is True and good["check"]["state"] == native_ai.PASS
    made["file"] = covered
    bad = native_ai.build(doc, str(tmp_path / "n.ai"), drawing=drawing)
    assert bad["built"] is False and bad["path"] is None and bad["code"] == native_ai.CHECK_FAILED
    assert bad["reason"].startswith("the layered file does not carry the drawing whole —")


# --- [his goal of 2026-10-12 (OWNER_BLOCKER_CLEARANCE.md, transcribed at ed4ca2c)] --------------------------------------

def test_goal_1012_rgb_the_layered_file_is_rgb_and_paints_the_drawings_own_colours():
    """(1) "keep the files RGB like the drawing until I give you my printer's CMYK profile": the layered file is an RGB
    document and writes each colour as the drawing paints it — 124's pinks no longer turned to CMYK by arithmetic (a pink
    read as peach); its die lines and plates spot colours, as they print."""
    from apps.ire.emitters import native_ai
    from apps.ire.graph import Color, SolidFill, Stroke
    pink = Color.from_hex("#F4B6C8")
    teal = Color.from_hex("#8FD3CF")
    petal = _b124_box("petal", 10, 10, 40, 30, SolidFill(color=pink))
    leaf = _b124_box("leaf", 60, 10, 40, 30, SolidFill(color=teal))
    leaf.stroke = Stroke(color=pink, width_mm=0.3)
    data = native_ai.tree(_b124_doc(petal, leaf))
    assert data["space"] == "RGB" and data["profile"] is None
    items = {i["name"]: i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"])}
    assert items["petal"]["fill"]["c"] == [round(pink.r, 4), round(pink.g, 4), round(pink.b, 4)]
    assert items["leaf"]["fill"]["c"] == [round(teal.r, 4), round(teal.g, 4), round(teal.b, 4)]
    js = native_ai.script(data, "/tmp/b124.ai")
    assert 'D.space === "CMYK" ? DocumentColorSpace.CMYK : DocumentColorSpace.RGB' in js
    assert 'spot("CutContour", [0, 1, 0, 0])' in js and "var PLATE_INK = [0, 0, 0, 1];" in js


def test_goal_1012_rgb_with_his_printers_profile_set_every_colour_goes_through_it_and_no_other(monkeypatch):
    """"then convert with that profile only": with his printer's CMYK profile set and valid, the layered file is CMYK,
    each colour through that profile — never the arithmetic that read 124's pink as peach."""
    import os

    import pytest

    from apps.ire.emitters import native_ai
    from apps.ire.graph import Color, SolidFill
    profile = "/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc"
    if not os.path.exists(profile):
        pytest.skip("no CMYK output profile on this machine to stand in for his printer's")
    monkeypatch.setattr(native_ai, "press_profile", lambda: profile)
    pink = Color.from_hex("#F4B6C8")
    data = native_ai.tree(_b124_doc(_b124_box("petal", 10, 10, 40, 30, SolidFill(color=pink))))
    assert data["space"] == "CMYK" and data["profile"] == profile
    item = next(i for i in native_ai._walk(data["boards"][0]["layers"][0]["items"]) if i["name"] == "petal")
    through = native_ai._through(profile)((244, 182, 200))
    assert item["fill"]["c"] == through and len(through) == 4 and through != native_ai._cmyk(pink)


def test_goal_1012_fade_the_drawing_keeps_a_shapes_own_fade_as_the_layered_file_does(tmp_path):
    """(3) "a shape's own fade (e.g. 85%) is right; the drawing must keep it too": a carton's flap motif set at 85 %
    printed at 100 % in the drawing. A shape's own opacity, its group's and its paint's, multiplied — on a composed
    design the drawing paints them as the layered file does; a code and a line of words never take a faded neighbour's."""
    import fitz

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.font_roles import SURFACE_KEY
    from apps.ire.graph import Color, Group, SolidFill
    black = SolidFill(color=Color.from_hex("#000000"))
    motif = _b124_box("flap-top-tuck-motif", 10, 10, 30, 30, black)
    motif.opacity = 0.85
    held = _b124_box("held", 60, 10, 30, 30, black)
    faded = Group(name="faded", opacity=0.5, children=[held])
    after = _b124_box("after-the-fade", 110, 10, 30, 30, black)
    doc = _b124_doc(motif, faded, after)
    doc.metadata = {SURFACE_KEY: "apps/ire/compose_container.py::compose_container_graph"}
    path = emit_pdf_ai(doc, str(tmp_path / "d.ai"))
    with fitz.open(path) as pdf:
        pix = pdf[0].get_pixmap(dpi=72, alpha=False)

    def grey(x_mm, y_mm):
        return pix.pixel(int(x_mm * 72 / 25.4), int(y_mm * 72 / 25.4))[0]
    assert abs(grey(25, 25) - 255 * 0.15) <= 6          # 85 % of black
    assert abs(grey(75, 25) - 255 * 0.5) <= 6           # half, from its group
    assert grey(125, 25) <= 6                           # full again after the fade


def test_goal_1012_estimated_sign_is_at_least_3_mm_tall_wherever_it_prints(tmp_path):
    """(5) "℮: at least 3 mm tall wherever it's printed (the EU rule), on every design": 124's sign printed 2.10 mm on
    its lid and 1.99 mm on its back. In the layered file's pieces and in the drawing alike the sign is never under 3 mm,
    given the room that height needs — and a layout measures the run with that room, so nothing it measured moves.
    [His word of 2026-10-17 on 142: "The ℮ is scaled with its line (at least 3 mm only where the line is large enough);
    never larger than the text beside it."] So the 3 mm holds where the line's capitals stand that tall themselves (12 pt
    and up), and a smaller line's sign is drawn at the line's own scale, never taller than its capitals."""
    import fitz

    from apps.ire import estimated_sign as E
    from apps.ire import text_metrics
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.font_roles import SURFACE_KEY
    from apps.ire.graph import Color, TextRun
    run = "18 SHADES • 27 g ℮ 0.95 oz"
    for size in (5.0, 6.0, 8.0, 12.0, 14.0, 20.0):
        parts = E.pieces(run, 0.0, 10.0, size, "Helvetica")
        sign = next(p[1] for p in parts if p[0] == "sign")
        ys = [v for op in sign for v in op[2::2]]
        caps_mm = E.CAP_SHARE * size / E.PT_PER_MM
        assert max(ys) - min(ys) <= caps_mm + 1e-6, size
        if caps_mm >= E.MIN_HEIGHT_MM:
            assert max(ys) - min(ys) >= E.MIN_HEIGHT_MM - 1e-6, size
        else:
            assert max(ys) - min(ys) < E.MIN_HEIGHT_MM, size
        last = parts[-1]
        laid = last[2] + E.width(last[1], "Helvetica", size) / E.PT_PER_MM
        assert abs(laid - E.width(run, "Helvetica", size) / E.PT_PER_MM) < 1e-6
    mm6 = 6.0 / E.PT_PER_MM
    assert abs(text_metrics.text_width_mm_measured(run, mm6, "Helvetica")
               - E.width(run, "Helvetica", mm6, per_mm=1.0)) < 1e-9
    doc = _b124_doc(TextRun(name="front-descriptor", text=run, x=20.0, y=40.0, size_pt=6.0,
                            color=Color.from_hex("#8E6D94")))
    doc.metadata = {SURFACE_KEY: "apps/ire/compose_container.py::compose_container_graph"}
    with fitz.open(emit_pdf_ai(doc, str(tmp_path / "d.ai"))) as pdf:
        signs = [d["rect"] for d in pdf[0].get_drawings() if d.get("fill") is not None]
    # a 6 pt line: its sign at the line's own scale, no taller than its capitals
    assert signs and max(r.height for r in signs) * 25.4 / 72.0 <= E.CAP_SHARE * 6.0 / E.PT_PER_MM + 0.05


def test_goal_1012_finish_a_plate_only_from_his_brief_never_the_planners_words_alone():
    """(6) "FINISHES are never invented": 124's all-over soft-touch came from the planner's words — its concept's finish
    line — and his brief asks for none. A clause's finish is kept only where his brief asks for it, read from his own
    words and never from what prints on the pack (his shade "Gilded Petal" is a name, not a foil); each other is said,
    NOT_ASKED, and never plated."""
    from apps.ire import container_finishes as F
    record = F.assignments("soft-touch matte laminate on lid exterior and body; rose-gold hot foil on bbrose lockup")
    brief = ("Mood: a dreamy fairytale, soft gradients.\nShade names (row by row, left to right):\nRow 1: Gilded Petal, "
             "Foil Star.\nBack copy: Description: shimmers with a hot foil look.\n")
    assert F.asked(brief) == set()
    kept, aside = F.as_asked(record, brief)
    assert all(not c["finishes"] for c in kept["clauses"])
    assert sorted((r["finish"], r["state"]) for r in aside) == [("foil", F.NOT_ASKED), ("soft_touch", F.NOT_ASKED)]
    assert all(r["how"].startswith("named only in the concept's finish line") for r in aside)
    asks = brief + "Finish: a soft-touch laminate on the lid.\n"
    assert F.asked(asks) == {"soft_touch"}
    kept, aside = F.as_asked(record, asks)
    assert [f["kind"] for c in kept["clauses"] for f in c["finishes"]] == ["soft_touch"]
    assert [r["finish"] for r in aside] == ["foil"]


def test_goal_1012_finish_gold_in_the_picture_is_foil_on_the_plate_with_the_logo():
    """(4) "gold in the picture is foil (my rule): 124's gold arch and gold "Enchanted Rose" go on the foil plate with the
    logo": a part drawn in the picture's gold — judged as the map's tracers judge gold — joins the gold plate the
    concept named, whatever its finish line's clauses were set aside for."""
    from apps.ire import container_finishes as F
    from apps.ire.graph import Color, Group, SolidFill
    from apps.pipeline.services.concept_design_map import is_gold_hex
    assert is_gold_hex("#D2A475") and is_gold_hex("#C89020") and is_gold_hex("#E2B878")
    assert not is_gold_hex("#F4B6C8") and not is_gold_hex("#8FD3CF") and not is_gold_hex("#9B7499")
    arch = _b124_box("lid-art-7", 10, 10, 30, 5, SolidFill(color=Color.from_hex("#C89020")))
    name = _b124_box("product-name-traced", 10, 20, 60, 10, SolidFill(color=Color.from_hex("#D2A475")))
    logo = _b124_box("logo", 10, 35, 20, 5, SolidFill(color=Color.from_hex("#E2B878")))
    sky = _b124_box("lid-art-0", 0, 0, 120, 80, SolidFill(color=Color.from_hex("#F4B6C8")))
    doc = _b124_doc(Group(name="Container", children=[sky, arch, name, logo]))
    record = F.assignments("soft-touch matte laminate on lid exterior; rose-gold hot foil on bbrose lockup")
    kept, aside = F.as_asked(record, "Mood: a dreamy fairytale.")
    out = F.apply(doc, kept, brand_metallic_hex="#B76E79", depict_as_drawn=True, set_aside=tuple(aside),
                  gold_as_drawn=("lid-art-7", "product-name-traced", "logo"), gold_plate=("foil", "FOIL_ROSE_GOLD"))
    gold = next(r for r in out["applied"] if r["target"] == "gold_as_drawn")
    assert gold["state"] == F.APPLIED and gold["plate"] == "FOIL_ROSE_GOLD"
    assert sorted(gold["nodes"]) == ["lid-art-7", "logo", "product-name-traced"]
    assert not sky.finishes and {r["state"] for r in out["applied"] if r["target"] != "gold_as_drawn"} == {F.NOT_ASKED}


def test_goal_1012_subtitle_set_in_small_spaced_capitals_as_the_concept_shows():
    """(7) "EYESHADOW PALETTE as small spaced capitals, as the concept shows (not grey title case)": 124's lid set it
    in title case at 17.6 pt, the size its picture's width gave the words untracked. A line the picture prints in
    capitals — the brief's words, the letters it shows — is set in capitals at their own height, spaced out to the
    picture's width; a line it prints in lower case stays as it was."""
    from types import SimpleNamespace

    from apps.ire import compose_container as CC
    types = [{"part": "eyeshadow palette subtitle", "words": "Eyeshadow Palette", "seen": "EYESHADOW PALETTE",
              "box": [0.35, 0.40, 0.65, 0.42], "ink": "#9B7499", "source": "the brief's front copy"},
             {"part": "tagline", "words": "a dreamy fairytale", "seen": "a dreamy fairytale",
              "box": [0.35, 0.50, 0.65, 0.53], "ink": "#9B7499", "source": "the brief's front copy"}]
    zone = {"x": 0.0, "y": 0.0, "width": 190.0, "height": 120.0}
    group, _places, rec = CC._map_type_group({"shapes": {"types": types}}, zone, SimpleNamespace(
        width_mm=190.0, height_mm=120.0), 1.0, 0.0, 0.0, name_font="regular", product_name="Enchanted Rose")
    runs = {n.name: n for n in group.children}
    caps, plain = runs["front-descriptor-0-0"], runs["front-descriptor-1-0"]
    assert caps.text_case == "upper" and caps.tracking_em > 0.1
    cap_mm = caps.size_pt * CC._INK_MM_PER_PT * CC.MAP_TYPE_CAP_EM
    assert abs(cap_mm - 0.02 * 120.0) < 0.05                                   # its capitals the picture's height
    spread = CC.name_width_estimate_mm(caps.text, caps.size_pt, upper=True, tracking_em=caps.tracking_em)
    assert abs(spread - 0.30 * 190.0 * CC.MAP_TYPE_SAFE_FILL) < 0.6 or abs(spread - 0.30 * 190.0) < 0.6
    assert plain.text_case is None and not plain.tracking_em
    assert CC._caps_as_seen(types[0]) and not CC._caps_as_seen(types[1])


def test_goal_1012_subtitle_a_line_of_capitals_is_traced_as_its_letters_own_band():
    """The map traced 124's subtitle 49 rows tall — its ink's tolerance took in the pink sky round its mauve capitals
    — for capitals 12 rows tall. A line the picture prints in capitals is traced as the band its letters fill."""
    import json
    import os

    from apps.pipeline.services import concept_design_map as M
    from apps.pipeline.services import concept_outline as co
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline",
                        "tests", "fixtures_124")
    with open(os.path.join(here, "concept_153.png"), "rb") as fh:
        lid = co.lid_picture(fh.read())
    with open(os.path.join(here, "lid_map_153.json"), encoding="utf-8") as fh:
        read = json.load(fh)
    img, mask, pbox = M._full_size(lid["png"], read)
    part = next(p for p in read["parts"] if "subtitle" in p["name"])
    box = M.trace_type(img, mask, pbox, part)["box"]
    rows = (box[3] - box[1]) * (pbox[3] - pbox[1])
    assert 8 <= rows <= 18, rows


def _goal_1012_fixture(name):
    import os
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline",
                        "tests", "fixtures_124", name)
    with open(here, "rb") as fh:
        return fh.read()


def test_goal_1012_glow_the_arch_glows_as_the_concept_shows_it():
    """(8) "The arch's soft glow as the concept shows it": 124's flat redraw draws a white core and a teal light round
    its gold arch, and the trace left it out with the sky. The glow is read from the redraw band by band out from the
    gold and drawn under the illustration — the gold grown to each band's reach, outermost first, never spiked."""
    from apps.ire.graph import Path
    from apps.pipeline.services.concept_design_map import is_gold_hex
    from apps.pipeline.targets.container import lid_art as LA
    trace = LA.trace_art(_goal_1012_fixture("lid_art_153.png"), False)
    bands = trace["glow"]["bands"]
    assert len(bands) >= 3 and all(b["de"] >= LA.GLOW["min_de"] for b in bands)
    teal = [b for b in bands if int(b["hex"][5:7], 16) > int(b["hex"][1:3], 16)]      # bluer than red: the teal light
    assert teal, bands
    group = LA.art_group(trace, 0.0, 0.0, 190.0, 120.0)
    names = [g.name for g in group.children]
    # [his goal of 2026-10-13, (7) and (8)] the gold arch found and drawn as a line, its glow round it a smooth mesh
    # through the same colours — the redraw's teal light among them
    assert names == ["lid-sky", "lid-glow", "lid-lines", "lid-illustration"]
    glows = group.children[1].children
    assert glows and all(isinstance(p, Path) and p.fill.type == "mesh" for p in glows)
    inks = {c for p in glows for patch in p.fill.patches for c in patch[8:12]}
    assert {b["hex"] for b in bands} <= inks
    assert any(is_gold_hex(line["hex"]) for line in trace["lines"])


def test_goal_1012_pan_shimmer_is_a_soft_sheen_toward_one_corner_never_a_stripe():
    """(9) "SHIMMER pans: a soft, subtle sheen (light glow toward one corner), never a hard left-to-right stripe": 124's
    shimmer pans were a straight blend from 45 % white across to the full shade from 55 %. A shimmer pan is a glow
    centred toward its upper left, its lightest only a third of the way to white, easing into the shade."""
    from apps.ire import palette_tray as T
    from apps.ire.graph import Color, GradientFill
    side = 16.0
    pan = {"name": "Petal Frost", "hex": "#E8C4C4", "finish": "shimmer", "source": "the tray picture"}
    node = T._pan_shown(pan, T._pan_segments("square", 10.0, 20.0, side), 10.0, 20.0, side, "pan-1-1")[0]
    fill = node.fill
    assert isinstance(fill, GradientFill) and fill.kind == "radial"
    assert 10.0 < fill.cx < 10.0 + side / 2.0 and 20.0 < fill.cy < 20.0 + side / 2.0 and fill.r >= side * 0.8
    shade = Color.from_hex(pan["hex"])

    def lift(c):
        return max((c.r - shade.r) / max(1.0 - shade.r, 1e-6), (c.g - shade.g) / max(1.0 - shade.g, 1e-6),
                   (c.b - shade.b) / max(1.0 - shade.b, 1e-6))
    lifts = [lift(s.color) for s in fill.stops]
    assert max(lifts) <= 0.35 and fill.stops[-1].color.to_hex() == pan["hex"]
    steps = [(b.offset - a.offset, lift(a.color) - lift(b.color)) for a, b in zip(fill.stops, fill.stops[1:])]
    assert all(drop / max(run, 1e-6) <= 0.6 for run, drop in steps)       # a soft fall, never a hard edge


def test_goal_1012_pan_glitter_is_fine_dense_sparkle_never_a_few_big_dots():
    """(10) "GLITTER pans: fine, dense sparkle, never a few big white dots": 124's glitter pans carried 22 specks each
    about 3.5 % of the pan. A glitter pan carries a hundred and more fine flakes, none wider than about 2 % of its side,
    spread over the whole pan — no quarter of it bare."""
    from apps.ire import palette_tray as T
    from apps.ire.emitters.pdf_ai import _segments_box
    side = 16.0
    pan = {"name": "Fairy Dust", "hex": "#D9C7D6", "finish": "glitter", "source": "the tray picture"}
    nodes = T._pan_shown(pan, T._pan_segments("square", 10.0, 20.0, side), 10.0, 20.0, side, "pan-1-3")
    flakes = [n for n in nodes if n.name.startswith("pan-1-3-speck-")]
    assert len(flakes) >= 100
    boxes = [_segments_box(n.segments) for n in flakes]
    assert max(b[2] - b[0] for b in boxes) <= side * 0.025
    quarters = {(int((b[0] + b[2]) / 2 >= 10.0 + side / 2), int((b[1] + b[3]) / 2 >= 20.0 + side / 2)) for b in boxes}
    assert quarters == {(0, 0), (0, 1), (1, 0), (1, 1)}


def _goal_1012_tray_read():
    import os

    from apps.pipeline.targets.container import tray_picture as TP
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline",
                        "tests", "fixtures_124", "tray_153.png")
    with open(here, "rb") as fh:
        return TP.read_tray_picture(fh.read(), 3, 6)


def _goal_1012_lab(hx):
    import cv2
    import numpy as np
    lab = cv2.cvtColor(np.uint8([[[int(hx[5:7], 16), int(hx[3:5], 16), int(hx[1:3], 16)]]]), cv2.COLOR_BGR2LAB)[0, 0]
    return float(lab[0]) * 100 / 255, float(lab[1]) - 128, float(lab[2]) - 128


def test_goal_1012_rims_soft_gold_from_the_tray_picture_never_grey():
    """(11) "Pan rims follow the tray picture (soft gold), not grey": 124's rims were grey keylines (#8A8480). Each
    pan is framed in the rim's ink its tray picture prints — a warm soft gold — its cut line in it too."""
    from apps.ire import palette_tray as T
    from apps.ire.palette_tray import read_tray
    read = _goal_1012_tray_read()
    L, a, b = _goal_1012_lab(read["rim"])
    assert 55 < L < 85 and b > 8 and b > a, read["rim"]                     # warm, soft: a muted gold
    tray = read_tray("18 square pans in 3 rows of 6\nShade names:\nRow 1: A, B, C, D, E, F\nRow 2: G, H, I, J, K, L\n"
                     "Row 3: M, N, O, P, Q, R")
    group, rec = T.compose_open_tray(tray, 190.0, 120.0, 0.0, 0.0, ground_hex="#F6DCE6", ink_hex="#6B3A5A",
                                     edge_hexes=["#F4B8CF"], face="Helvetica", rim_hex=read["rim"],
                                     glow_hex=read["glow"], name_hex=read["names_ink"])
    found = {n.name: n for n in _goal_1012_walk(group)}
    rims = [n for name, n in found.items() if name.startswith("pan-rim-")]
    assert len(rims) == 18 and all(n.fill.color.to_hex() == read["rim"] for n in rims)
    wells = [n for name, n in found.items() if name.startswith("pan-well-")]
    assert all(n.stroke.color.to_hex() == read["rim"] for n in wells) and rec["rim_hex"] == read["rim"]


def test_goal_1012_edge_the_holographic_glow_round_each_pan_as_the_picture_shows():
    """(12) "the holographic edge around the pans, as the tray picture shows": the picture lights each pan with a pale
    teal glow; the frame drawn round the whole field in the design's colours is not in it. Each pan its glow, fading
    outward, in the picture's own light."""
    from apps.ire import palette_tray as T
    from apps.ire.palette_tray import read_tray
    read = _goal_1012_tray_read()
    L, a, b = _goal_1012_lab(read["glow"])
    assert L > 80 and a < 2, read["glow"]                                    # light and cool
    tray = read_tray("18 square pans in 3 rows of 6")
    group, _rec = T.compose_open_tray(tray, 190.0, 120.0, 0.0, 0.0, ground_hex="#F6DCE6", ink_hex="#6B3A5A",
                                      edge_hexes=["#F4B8CF"], face="Helvetica", rim_hex=read["rim"],
                                      glow_hex=read["glow"])
    names = [n.name for n in _goal_1012_walk(group)]
    glows = [n for n in _goal_1012_walk(group) if n.name.startswith("pan-glow-1-1-")]
    assert "tray-pan-field-edge" not in names and len(glows) == T.GLOW_STEPS
    alphas = [n.fill.opacity for n in sorted(glows, key=lambda n: int(n.name.rsplit("-", 1)[1]))]
    assert alphas == sorted(alphas, reverse=True) and alphas[0] <= T.GLOW_ALPHA


def test_goal_1012_names_readable_in_the_pictures_ink_never_under_the_floor():
    """(13) "Pan names readable (check the size against the print floor)": the names in the dark ink the picture
    prints them in, where it stands well off the tray's ground, at a size never under the print floor — both said on
    the record."""
    from apps.ire import palette_tray as T
    from apps.ire.palette_tray import read_tray
    read = _goal_1012_tray_read()
    assert _goal_1012_lab(read["names_ink"])[0] < 45, read["names_ink"]
    tray = read_tray("18 square pans in 3 rows of 6\nShade names:\nRow 1: Petal Frost, Moonlit Rose, Fairy Dust, "
                     "Rosewater, Wild Rose, Velvet Bloom\nRow 2: Lilac Mist, Gilded Petal, Spellbound, Enchanted, "
                     "Twilight, Briar\nRow 3: Dusk Garden, Mystic, Thorn, Nightshade, Eternal, Midnight Bloom")
    group, rec = T.compose_open_tray(tray, 190.0, 120.0, 0.0, 0.0, ground_hex="#F6DCE6", ink_hex="#F2C9D6",
                                     edge_hexes=["#F4B8CF"], face="Helvetica", name_hex=read["names_ink"])
    words = [n for n in _goal_1012_walk(group) if n.name.startswith("shade-name-")]
    assert words and all(n.color.to_hex() == read["names_ink"] for n in words)
    assert rec["name_pt"] >= rec["name_floor_pt"] == T.NAME_MIN_PT and rec["name_contrast_de"] >= T.NAME_CONTRAST_DE
    _g, pale = T.compose_open_tray(tray, 190.0, 120.0, 0.0, 0.0, ground_hex="#F6DCE6", ink_hex="#6B3A5A",
                                   edge_hexes=["#F4B8CF"], face="Helvetica", name_hex="#F0D0DC")
    assert pale["name_hex"] == "#6B3A5A"                                   # a name ink that would not read: never used


def _goal_1012_walk(node):
    yield node
    for child in getattr(node, "children", None) or []:
        yield from _goal_1012_walk(child)


def test_goal_1012_inside_the_lids_inside_is_read_from_the_tray_picture():
    """(12) "Draw the inside of the lid (roses + arch above the pans) ... as the tray picture shows": the open lid the
    tray picture shows above its pans — found at its hinge, between its sides — is straightened and traced as the lid's
    art is, its sky a gradient, its roses and arch regions."""
    import os

    from apps.pipeline.targets.container import lid_art as LA
    from apps.pipeline.targets.container import tray_picture as TP
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline",
                        "tests", "fixtures_124", "tray_153.png")
    with open(here, "rb") as fh:
        png = fh.read()
    read = TP.read_tray_picture(png, 3, 6)
    grid_top = min(p["box_px"][1] for p in read["pans"][0])
    strip, rec = TP.lid_inside_strip(png, grid_top)
    assert rec["state"] == TP.READ and 200 < rec["hinge_px"] < grid_top
    assert rec["strip_px"][0] == TP.LID_INSIDE["strip_px"] and rec["strip_px"][1] < rec["strip_px"][0]
    trace = LA.trace_art(strip, False)
    assert trace["state"] == LA.TRACED and len(trace["regions"]) >= 40
    assert TP.lid_inside_strip(b"", grid_top)[0] is None


def test_goal_1012_inside_drawn_above_the_pans_at_print_size_its_names_its_own():
    """The inside of the lid drawn at the insert's own size above it, a hinge apart — the picture's strip at its foot,
    its sky carried up — the insert under it; its nodes named as the lid's inside, never as the lid's art the finishes
    and the motif check read."""
    import os

    from apps.ire import palette_tray as T
    from apps.ire.palette_tray import read_tray
    from apps.pipeline.targets.container import lid_art as LA
    from apps.pipeline.targets.container import tray_picture as TP
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline",
                        "tests", "fixtures_124", "tray_153.png")
    with open(here, "rb") as fh:
        png = fh.read()
    read = TP.read_tray_picture(png, 3, 6)
    strip, _rec = TP.lid_inside_strip(png, min(p["box_px"][1] for p in read["pans"][0]))
    trace = LA.trace_art(strip, False)
    tray = read_tray("18 square pans in 3 rows of 6")
    group, rec = T.compose_open_tray(tray, 190.0, 120.0, 10.0, 20.0, ground_hex="#F6DCE6", ink_hex="#6B3A5A",
                                     edge_hexes=["#F4B8CF"], face="Helvetica", lid_inside=trace)
    w, h = rec["insert_mm"]
    assert group.children[0].name == "LID INSIDE" and rec["lid_inside"]["panel_mm"] == [round(w, 2), round(h, 2)]
    assert abs(rec["drawn_h_mm"] - (2 * h + T.HINGE_GAP_MM)) < 0.05
    ground = next(n for n in group.children if n.name == "tray-insert-ground")
    assert abs(ground.y - (20.0 + h + T.HINGE_GAP_MM)) < 1e-6
    names = {n.name for n in _goal_1012_walk(group.children[0])}
    assert any(n.startswith("lid-inside-art-") for n in names) and not any(n.startswith("lid-art-") for n in names)


def _goal_1012_back_sections():
    return [{"heading": "Description", "text": "An 18-shade eyeshadow palette of shimmers and mattes in dreamy rose, "
                                               "lilac and teal.", "lang": "en"},
            {"heading": "Ingredients", "text": "Talc, Mica, Magnesium Stearate, Dimethicone, Phenoxyethanol. May "
                                               "contain: CI 77491, CI 77891, CI 77007.", "lang": "en", "fine": True},
            {"heading": "How to use", "text": "Apply with a brush or fingertip, build up for intensity.", "lang": "en"},
            {"heading": "Warnings", "text": "For external use only. Avoid contact with eyes' inner rim.", "lang": "en",
             "fine": True},
            {"heading": "Descripción", "text": "Paleta de 18 sombras de ojos con acabados brillantes y mates en tonos "
                                               "rosa, lila y verde azulado.", "lang": "es"},
            {"heading": "Ingredientes", "text": "Talc, Mica, Magnesium Stearate, Dimethicone, Phenoxyethanol.",
             "lang": "es", "fine": True},
            {"heading": "Modo de uso", "text": "Aplicar con un pincel o la yema del dedo.", "lang": "es"},
            {"heading": "الوصف", "text": "باليت ظلال عيون من 18 درجة لونية بتشطيبات لامعة ومطفأة.", "lang": "ar"},
            {"heading": "طريقة الاستعمال", "text": "يطبق بفرشاة أو بطرف الإصبع.", "lang": "ar"}]


def test_goal_1012_back_a_palettes_back_is_packaging_its_languages_side_by_side_to_the_foot():
    """(14) "Laid out like packaging, using the whole panel: clear hierarchy, the three languages as balanced blocks,
    never a squeezed list with empty space below": 124's back held 26 lines at one size, one under another. A
    palette's or a compact's back sets its languages side by side, each heading in bold capitals over its copy, at the
    largest size every column holds, each column reaching the panel's foot."""
    from apps.ire import back_panel as BP
    zone = {"zone_id": "back", "width": 171.0, "height": 108.0, "safe_margin_mm": 3.0}
    meta = {"typography_surface": "apps/ire/compose_container.py::compose_container_graph"}
    group, rec = BP.compose_back_panel(_goal_1012_back_sections(), zone, 0.0, 0.0, doc_metadata=meta,
                                       heading_role="heading", copy_role="body", fill_area=True, packaging=True)
    assert rec["layout"] == BP.PACKAGING and rec["columns"] == 3 and rec["languages"] == ["en", "es", "ar"]
    assert rec["fits"] is True and rec["lines_emitted"] == rec["lines_required"]
    assert rec["size_pt"] > 5.0 and rec["size_pt"] <= BP.PACK_MAX_PT
    columns = {}
    for e in rec["lines"]:
        columns.setdefault(e["column"], []).append(e)
    room = rec["height_available_mm"]
    for k, lines in columns.items():
        assert max(e["baseline_mm"] for e in lines) >= 0.8 * room, k          # each block to the panel's foot
        assert all(abs(e["x_mm"] - (3.0 + k * (rec["column_mm"] + BP.PACK_GUTTER_MM))) < 0.01 for e in lines)
    heads = [e["text"] for e in rec["lines"] if e["role"] == "heading" and e.get("lang") != "ar"]
    assert heads and all(h == h.upper() for h in heads)
    names = {n.name for n in group.children}
    assert "back-panel-0-heading-0" in names and "back-panel-7-heading-0" in names


def test_goal_1012_back_a_narrow_back_keeps_its_blocks_stacked():
    """Where three columns would each be narrower than a readable measure, the back keeps its languages stacked, as
    before — never squeezed into slivers."""
    from apps.ire import back_panel as BP
    zone = {"zone_id": "back", "width": 80.0, "height": 140.0, "safe_margin_mm": 3.0}
    meta = {"typography_surface": "apps/ire/compose_container.py::compose_container_graph"}
    _group, rec = BP.compose_back_panel(_goal_1012_back_sections(), zone, 0.0, 0.0, doc_metadata=meta,
                                        heading_role="heading", copy_role="body", fill_area=True, packaging=True)
    assert rec.get("layout") != BP.PACKAGING and all("x_mm" not in e for e in rec["lines"])


# --------------------------------------------------------------------------------------------------------------------
# [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "It stopped while drawing: "on one of its own checks — that
# check has no words written for it yet". Find it and fix it. Then, everywhere: NO check ever stops a design."]
# --------------------------------------------------------------------------------------------------------------------

def test_goal_1013_tracking_one_bound_for_letter_spacing():
    """125 stopped: 55dbcf8 spaced a line of capitals up to ``MAP_TYPE_MAX_TRACK_EM`` = 0.6 while the drawing's text
    model took at most 0.5 — one bound written twice, disagreeing; 125's front asked 0.6 and the model refused it. The
    composer's bound is the model's own."""
    from annotated_types import Le

    from apps.ire import compose_container as CC
    from apps.ire.graph import TRACKING_EM_MAX, TextRun
    model = next(float(m.le) for m in TextRun.model_fields["tracking_em"].metadata if isinstance(m, Le))
    assert CC.MAP_TYPE_MAX_TRACK_EM == TRACKING_EM_MAX == model


def test_goal_1013_tracking_a_capitals_line_wider_than_its_letters_is_drawn():
    """125's carton front: "EYESHADOW PALETTE" in capitals in a box far wider than its letters — the spacing the width
    asks for is past the bound; the line is drawn spaced at the bound, never refused."""
    from types import SimpleNamespace

    from apps.ire import compose_container as CC
    types = [{"part": "eyeshadow palette subtitle", "words": "Eyeshadow Palette", "seen": "EYESHADOW PALETTE",
              "box": [0.04, 0.60, 0.96, 0.63], "ink": "#9B7499", "source": "the brief's front copy"}]
    zone = {"x": 0.0, "y": 0.0, "width": 192.0, "height": 122.0}
    group, _places, _rec = CC._map_type_group({"shapes": {"types": types}}, zone, SimpleNamespace(
        width_mm=192.0, height_mm=122.0), 1.0, 0.0, 0.0, name_font="regular", product_name="Enchanted Rose")
    def leaves(node):
        for kid in getattr(node, "children", None) or []:
            yield kid
            yield from leaves(kid)
    runs = [n for n in leaves(group) if getattr(n, "type", "") == "text"]
    run = next(r for r in runs if r.text.upper().replace(" ", "") == "EYESHADOWPALETTE")
    assert run.text_case == "upper" and run.tracking_em == CC.MAP_TYPE_MAX_TRACK_EM


def test_goal_1013_never_stops_a_value_past_a_bound_is_brought_to_it_and_said():
    """While a drawing is made, a value past one of the drawing's own closed bounds is brought to the bound and said in
    words; outside a drawing the schema refuses as before — a repair is made only where it is said."""
    from pydantic import ValidationError

    from apps.ire import graph as G
    with G.bounds_kept() as brought:
        run = G.TextRun(text="EYESHADOW PALETTE", x=0, y=0, size_pt=8, font="x", tracking_em=0.6,
                        color=G.Color(r=1.2, g=0.2, b=0.3))
    assert run.tracking_em == 0.5 and run.color.r == 1.0
    said = [G.bound_words(r) for r in brought]
    assert "a line's letter-spacing (EYESHADOW PALETTE) asked 0.6 em, past the 0.5 em the drawing takes — drawn at " \
           "0.5 em" in said
    assert "a colour's red asked 1.2, past the 1 the drawing takes — drawn at 1" in said
    with pytest.raises(ValidationError):
        G.TextRun(text="A", x=0, y=0, size_pt=8, font="x", tracking_em=0.6, color=G.Color(r=0, g=0, b=0))
    with G.bounds_kept(), pytest.raises(ValidationError):    # an open bound — a size of nothing — is never "brought"
        G.TextRun(text="A", x=0, y=0, size_pt=0, font="x", color=G.Color(r=0, g=0, b=0))


def test_goal_1013_never_stops_every_bound_of_the_drawing_has_its_words():
    """Every closed bound the drawing's models declare has its words (``graph.BOUND_WORDS``) — never a field's name."""
    import inspect

    from pydantic import BaseModel

    from apps.ire import graph as G
    models = [c for _n, c in inspect.getmembers(G, inspect.isclass)
              if issubclass(c, BaseModel) and c.__module__ == G.__name__]
    bounded = {(c.__name__, f) for c in models for f, _lo, _hi in G.closed_bounds(c)}
    assert ("TextRun", "tracking_em") in bounded and len(bounded) > 10
    assert {f for _c, f in bounded} <= set(G.BOUND_WORDS)


def test_goal_1013_never_stops_a_stage_says_what_its_drawing_kept_beside_approve():
    """Every pipeline stage keeps the drawing's bounds (``crash_safe``): a stage whose drawing asked past a bound goes
    on, and each value brought to its bound is listed beside Approve as a fix of the drawing's own."""
    from types import SimpleNamespace

    from apps.ire import graph as G
    from apps.ire import self_check as SC
    from apps.pipeline.agents.aria import ARIAAgent, crash_safe

    saved = {}
    output = SimpleNamespace(spec_sheet={SC.SCHEMA: SC.record([], [{"kind": "x", "what": "a line in the margin"}])},
                             save=lambda **kw: saved.setdefault("fields", kw.get("update_fields")))
    logs = []

    class Stage:
        task = SimpleNamespace(current_output=lambda: output)
        _say_bounds_kept = ARIAAgent._say_bounds_kept

        def log(self, words, **kw):
            logs.append(words)

        def _fail(self, reason, tb=None):
            raise AssertionError("the stage stopped: %s" % reason)

        @crash_safe
        def draw(self):
            G.TextRun(text="EYESHADOW PALETTE", x=0, y=0, size_pt=8, font="x", tracking_em=0.6,
                      color=G.Color(r=0, g=0, b=0))
            return "drawn"

    assert Stage().draw() == "drawn"
    check = output.spec_sheet[SC.SCHEMA]
    assert [f["what"] for f in check["fixed"]] == [
        "a line's letter-spacing (EYESHADOW PALETTE) asked 0.6 em, past the 0.5 em the drawing takes — drawn at 0.5 em"]
    assert [f["what"] for f in check["shown"]] == ["a line in the margin"] and saved["fields"] == ["spec_sheet"]
    assert logs and logs[0].startswith("ARIA: the drawing kept its own bounds — a line's letter-spacing")


#: the engine's check modules — every check code any of them declares has its words, or is named a state that is no
#: check (apps/dashboard/words.py ``check_words``, ``NOT_A_CHECK``)
CHECK_MODULES = (
    "apps.ire.container_concept_fidelity", "apps.ire.container_motif", "apps.pipeline.services.container_projection",
    "apps.ire.container_fidelity", "apps.ire.container_motif_fidelity", "apps.pipeline.services.flat_motif",
    "apps.ire.brand_string_runtime", "apps.pipeline.targets.container.m3_backbone", "apps.ire.compose_dropper",
    "apps.pipeline.targets.container.archetypes", "apps.ire.compose_container",
    "apps.pipeline.services.container_visual_graph", "apps.pipeline.design_intent",
    "apps.pipeline.design_direction_generator", "apps.pipeline.direction_signature",
    "apps.pipeline.services.gate1_prompts", "apps.pipeline.services.container_gate1",
    "apps.pipeline.services.provider_prespend", "apps.pipeline.targets.packaging", "apps.pipeline.targets.gift_set",
    "apps.pipeline.targets.artwork", "apps.ire.container_production_readiness",
    "apps.pipeline.services.reconstruction_status", "apps.ire.compose", "apps.pipeline.targets.container",
    "apps.pipeline.services.concept_design_map", "apps.pipeline.targets.container.lid_art",
    "apps.pipeline.targets.carton_layout", "apps.ire.container_finishes",
    # [his goal of 2026-10-13, (1)] what held Gate 2 by code until then
    "apps.pipeline.services.visual_quality_gate", "apps.ire.compose_artwork", "apps.pipeline.gate2_problems",
)


def test_goal_1013_words_every_check_the_engine_declares_has_its_words():
    """[His goal of 2026-10-13, (1): "Every check has its words written; a check without words fails the wiring
    check."] Every check code a check module declares (its own constant in capitals and underscores) is said in its
    words, or is named as a state no check is — 79 had none when it was measured."""
    import importlib
    import re

    from apps.dashboard import words as W
    code = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
    declared = {}
    for name in CHECK_MODULES:
        module = importlib.import_module(name)
        for key, value in vars(module).items():
            if key.isupper() and isinstance(value, str) and code.match(value):
                declared.setdefault(value, "%s.%s" % (name, key))
    assert len(declared) > 120
    wordless = {c: at for c, at in declared.items() if not W.check_words(c) and c not in W.NOT_A_CHECK}
    assert wordless == {}
    for c in W.MORE_CHECK_WORDS.values():
        assert "_" not in c and c == c.strip() and c[:1].islower()


def test_goal_1013_words_a_stop_is_said_in_words_never_as_a_check_with_none():
    """125's page said "on one of its own checks — that check has no words written for it yet". A check it names is
    said in its words; what names none is a fault of the system itself, said as one — never "no words written"."""
    from apps.dashboard import words as W
    fault = W.reason_words("1 validation error for TextRun\ntracking_em\n  Input should be less than or equal to 0.5 "
                           "[type=less_than_equal, input_value=0.6, input_type=float]")
    assert fault.startswith("It stopped: a fault in the system itself") and "no words" not in fault
    said = W.reason_words("CONTAINER_NATIVE_RECONSTRUCTION_FAILED: CONTAINER_MOTIF_MISSING")
    assert "the concept's motif was not drawn" in said and "no words" not in said
    # the concept step's own codes, keyed by their values — the constants' names left them without words
    assert W.concept_check_words("PROMPT_ENGINEER_OUTPUT_PARSE_FAILURE") == "the answer could not be read"
    assert "the answer could not be read" in W.reason_words(
        "Gate-1 variation contract not satisfied after the bounded repair (PROMPT_ENGINEER_OUTPUT_PARSE_FAILURE)")
    # a print area's name in a containment's detail is no check, never "a check with no words"
    assert W.drawing_stop_reasons("CONTAINER_NATIVE_RECONSTRUCTION_FAILED: CONTAINER_ARTWORK_SURFACE_MISMATCH: the "
                                  "motif on CAP_FRONT") == [W.DRAWING_STOP_WORDS["ARTWORK_SURFACE_MISMATCH"]]
    assert W.readiness_words("BRAND_STRING_PROVISIONAL: brand tier") == (
        "a brand word on the drawing is provisional — not yet confirmed as the brand's — brand tier")


def test_goal_1013_words_a_carton_whose_drawing_fails_says_so_beside_approve(tmp_path, settings, db, monkeypatch):
    """The carton's drawing was best-effort: a failure was logged and the carton reached Gate 2 with nothing said
    beside Approve. It is said there now, as a fault of the system's — the die and its files made."""
    settings.MEDIA_ROOT = str(tmp_path)
    from apps.dielines.models import DielineJob
    from apps.dielines.services.export_service import generate_exports
    from apps.dielines.validators.schema import DielineInputJSON
    from apps.ire import compose as C

    def fails(*a, **k):
        raise ValueError("a fault planted in the composer")
    monkeypatch.setattr(C, "compose_components_graph", fails)
    job = DielineJob.objects.create(template_type="straight_tuck_end_carton", scenario="A", input_json={})
    params = DielineInputJSON(template="straight_tuck_end_carton", unit="mm",
                              dimensions={"width_mm": 28, "depth_mm": 28, "height_mm": 120}, print_settings={},
                              construction={}, metadata={"product_name": "T", "product_type": "t"})
    result = generate_exports(job, params)
    assert result["design_preview_ai_path"] is None
    check = result["self_check"]
    assert check and not check["clean"] and len(check["shown"]) == 1
    assert check["said"][0].startswith("Look at: the design could not be drawn on its die — a fault in the system "
                                       "itself (ValueError)")


def test_goal_1013_never_stops_a_colour_that_drifts_is_redrawn_in_the_concepts_and_checked_again():
    """[His goal of 2026-10-13, (1): "A failing check fixes the drawing itself and re-checks."] A colour the colour check
    finds drifting from the concept's is redrawn in the concept's own — every fill, stroke, stop and line of it — and
    the check run again passes; said as a fix."""
    from apps.ire.graph import (Color, Document, GradientFill, GradientStop, Group, Rect, SolidFill, Stroke,
                                TextRun)
    from apps.pipeline.services import flat_motif as fm
    from apps.pipeline.targets.container import colour_check_of, repair_drifting_colours
    drift, concept = "#C06070", "#E8A0B0"
    body = Rect(name="body", x=0, y=0, w=10, h=10, fill=SolidFill(color=Color.from_hex(drift)),
                stroke=Stroke(color=Color.from_hex(drift), width_mm=0.2))
    band = Rect(name="band", x=0, y=0, w=10, h=2, fill=GradientFill(stops=[
        GradientStop(offset=0.0, color=Color.from_hex(drift)), GradientStop(offset=1.0, color=Color.from_hex("#FFFFFF"))]))
    word = TextRun(name="w", text="x", x=1, y=1, size_pt=8, font="x", color=Color.from_hex(drift))
    doc = Document(page_w=20, page_h=20, root=Group(name="r", role="artwork", children=[body, band, word]))
    colors = {"body": drift}
    front = {"concept_colours": {"body": (concept, "the concept's own")}, "shapes": {"lines": []}}
    first = colour_check_of(colors, {}, front)
    assert first["codes"] and first["codes"][0].startswith(fm.COLOUR_DRIFTS)
    said = repair_drifting_colours(doc, colors, front, first)
    assert said == ["the body colour drifted from the concept's (ΔE %.1f) — redrawn in the concept's own, %s"
                    % (first["roles"]["body"]["delta_e"], concept)]
    assert {body.fill.color.to_hex(), body.stroke.color.to_hex(), band.fill.stops[0].color.to_hex(),
            word.color.to_hex()} == {concept} and colors["body"] == concept
    assert colour_check_of(colors, {}, front)["codes"] == []


def test_goal_1013_never_stops_each_check_gone_past_is_listed_beside_approve_once_with_what_he_can_do():
    """The checks a design went on past, kept as each is met, listed beside Approve with the drawing's own check — each
    once, in its words, with what he can do."""
    from apps.ire import self_check as SC
    spec = {}
    SC.keep_shown(spec, "CONTAINER_MOTIF_MISSING: rose", "the concept's motif was not drawn", ("ask for changes",))
    SC.keep_shown(spec, "CONTAINER_MOTIF_MISSING: rose", "the concept's motif was not drawn", ("ask for changes",))
    assert spec[SC.CHECKS_SHOWN_KEY] == [{"code": "CONTAINER_MOTIF_MISSING", "what": "the concept's motif was not drawn",
                                          "options": ["ask for changes"]}]
    check = SC.with_shown(SC.record([{"what": "a speck taken off"}], [{"what": "a line in the margin"}]), spec)
    assert check["said"] == ["Fixed: a speck taken off", "Look at: a line in the margin",
                             "Look at: the concept's motif was not drawn — you can ask for changes"]
    assert not check["clean"]


def test_goal_1013_never_stops_a_provisional_line_is_left_out_never_drawn():
    """[His goal of 2026-10-13, (1); §AE2(c) unloosened] a line whose words the owner did not supply is taken out of the
    drawing — the design drawn on without it — and named, never drawn and never the design stopped."""
    from apps.ire.brand_string_runtime import MARKER, brand_string_report, leave_out_provisional
    from apps.ire.graph import Color, Document, Group, TextRun
    name = TextRun(name="product-name-hero", text="%s Rose Serum" % MARKER, x=1, y=1, size_pt=12, font="x",
                   color=Color.from_hex("#000000"))
    keep = TextRun(name="front-net-content", text="30 ml", x=1, y=5, size_pt=6, font="x", color=Color.from_hex("#000000"))
    doc = Document(page_w=20, page_h=20, root=Group(name="r", role="artwork", children=[
        Group(name="type", role="typography", children=[name, keep])]))
    gone = leave_out_provisional(doc)
    assert [r["node"] for r in gone] == ["product-name-hero"]
    assert brand_string_report(doc)["clean"] and [n.name for n, _p in doc.walk() if n.type == "text"] == [
        "front-net-content"]


def test_goal_1013_never_stops_gate_2_says_every_hold_in_words_and_refuses_only_his_act_or_no_drawing():
    """[His goal of 2026-10-13, (1).] What stood at Gate 2 by code is said in words beside Approve — the visual-quality
    check's axes, an artwork piece's codes, a die outside its domain, a stale verdict — and only his own acceptance not
    given, or no drawing at all, refuses an approval."""
    from apps.dashboard.words import check_words
    from apps.pipeline.gate2_problems import REFUSING, _row
    for code in ("VQ_SILHOUETTE_FIDELITY_FAILED", "VQ_LOGO_DEFECTIVE", "VISUAL_QUALITY_GATE_FAILED",
                 "ARTWORK_KEY_VISUAL_MISSING", "DIMENSION_COMBINATION_UNSUPPORTED", "SPEC_STALE_REDERIVE_REQUIRED",
                 "CARTON_FRONT_COPY_EXCEEDS_PANEL:front:name", "DIELINE_FOLD_CHECK_FAILED"):
        row = _row(code)
        assert check_words(code) and "_" not in row["words"], (code, row)
    assert set(REFUSING) == {"HUMAN_VISUAL_ACCEPTANCE_REQUIRED", "CONTAINER_RECONSTRUCTION_ABSENT",
                             "RECONSTRUCTION_NOT_COMPLETED", "ARTIFACT_NOT_AVAILABLE", "TECHNICAL_INTERVENTION_REQUIRED"}



# --------------------------------------------------------------------------------------------------------------------
# [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (11): "a test mode that draws ONE concept instead of three", and
# (2): "let me continue 125 ... at $0"] the executor's per-design options
# --------------------------------------------------------------------------------------------------------------------

def test_goal_1013_options_a_design_held_at_0_is_refused_every_paid_call_before_it_is_made():
    """A design whose spending is held (``options["spend_held"]``) reaches no paid service: the writing service, a
    picture or a web search each refused before the call, as a spending cap is — said; a design without it as ever."""
    from types import SimpleNamespace

    from apps.pipeline.services import claude_service
    from apps.pipeline.services.cost_ledger import (SPEND_HELD_WORDS, BudgetExceededError, before_paid_call,
                                                    task_cost_context)
    held, free = SimpleNamespace(options={"spend_held": True}), SimpleNamespace(options={})
    with task_cost_context(held):
        with pytest.raises(BudgetExceededError) as said:
            before_paid_call("a picture")
        assert str(said.value) == SPEND_HELD_WORDS + " (a picture)"
        with pytest.raises(BudgetExceededError):
            claude_service._get_client()
    with task_cost_context(free):
        before_paid_call("a picture")
    before_paid_call("a picture")                                    # no design being made: nothing to hold


def test_goal_1013_options_a_test_run_draws_one_concept_of_the_three_planned():
    """[His (11)] the executor's test run (``options["one_concept"]``) — never his designs' default: the three planned
    and checked, one drawn; a design without it draws its three."""
    from types import SimpleNamespace

    from apps.pipeline.agents.aria import concepts_to_draw
    prompts = [{"variation_id": v} for v in ("A", "B", "C")]
    one, expected = concepts_to_draw(SimpleNamespace(options={"one_concept": True}), prompts, ["A", "B", "C"])
    assert (one, expected) == (prompts[:1], ["A"])
    assert concepts_to_draw(SimpleNamespace(options={}), prompts, ["A", "B", "C"]) == (prompts, ["A", "B", "C"])
    from apps.pipeline.models import DesignTask
    assert DesignTask._meta.get_field("options").default() == {}



# --------------------------------------------------------------------------------------------------------------------
# [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is the lid's
# face (landscape). Use each container's real orientation for every form."]
# --------------------------------------------------------------------------------------------------------------------

def test_goal_1013_orientation_a_quarter_turn_stands_a_landscape_frame_on_a_standing_panel():
    """The turn that lays a 192 x 122 frame, upright, onto a 122 x 192 panel at the same place: its top edge along the
    panel's left, its right edge along the panel's top; only quarter turns are taken."""
    from pydantic import ValidationError

    from apps.ire.graph import Group, quarter_turn, turned_point
    t = quarter_turn(192.0, 122.0, 10.0, 20.0)
    corners = {(round(x, 6), round(y, 6)) for x, y in (turned_point(t, u, v) for u in (10.0, 202.0) for v in (20.0, 142.0))}
    assert corners == {(10.0, 20.0), (132.0, 20.0), (10.0, 212.0), (132.0, 212.0)}
    assert turned_point(t, 10.0, 20.0) == (10.0, 212.0)          # the frame's top-left at the panel's foot-left
    assert turned_point(t, 202.0, 20.0) == (10.0, 20.0)          # its top-right at the panel's top-left
    Group(name="g", turn=t)
    with pytest.raises(ValidationError):
        Group(name="g", turn=(0.5, 0.0, 0.0, 1.0, 0.0, 0.0))


def test_goal_1013_orientation_the_drawing_and_the_layered_file_turn_a_group_alike():
    """A turned group drawn: its rect lands on the panel where the turn puts it, its line of type turned with it; the
    data the layered file is built from carries the same points and the type's rotation."""
    import tempfile

    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, Rect, SolidFill, TextRun, quarter_turn
    t = quarter_turn(80.0, 40.0, 10.0, 10.0)
    box = Rect(name="box", x=10.0, y=10.0, w=20.0, h=10.0, fill=SolidFill(color=Color.from_hex("#B03050")))
    word = TextRun(name="word", text="FRONT", x=15.0, y=30.0, size_pt=10, font="regular", color=Color.from_hex("#000000"))
    doc = Document(page_w=100, page_h=100, root=Group(name="root", role="artwork", children=[
        Group(name="turned", role="decoration", children=[box, word], turn=t)]))
    with tempfile.TemporaryDirectory() as tmp:
        path = tmp + "/t.pdf"
        emit_pdf_ai(doc, path)
        with fitz.open(path) as pdf:
            page = pdf[0]
            fills = [d["rect"] for d in page.get_drawings() if d.get("fill")]
            lines = [l for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])]
    k = 72.0 / 25.4
    want = fitz.Rect(10.0 * k, 70.0 * k, 20.0 * k, 90.0 * k)      # the rect turned: 10 wide, 20 tall, at (10, 70)
    assert any(abs(r.x0 - want.x0) < 0.5 and abs(r.y0 - want.y0) < 0.5 and abs(r.x1 - want.x1) < 0.5
               and abs(r.y1 - want.y1) < 0.5 for r in fills), fills
    assert lines and abs(lines[0]["dir"][0]) < 1e-6 and lines[0]["dir"][1] == -1.0     # reading up the page
    data = native_ai.tree(doc)
    flat = [i for board in data["boards"] for layer in board["layers"] for i in native_ai._walk(layer["items"])]
    rects = [i for i in flat if i.get("t") == "r" and i.get("name") == "box"]
    texts = [i for i in flat if i.get("t") == "x" and i.get("name") == "word"]
    assert rects and texts, flat
    assert (round(rects[0]["x"], 6), round(rects[0]["y"], 6), round(rects[0]["w"], 6), round(rects[0]["h"], 6)) == (
        10.0, 70.0, 10.0, 20.0)
    assert texts[0]["rot"] == 90.0


def test_goal_1013_orientation_native_turns_every_point_it_sends():
    """The layered file's data, turned item by item: a path's points, a clip, a rect's corners, a type's anchor and
    rotation, a gradient's run, a picture's place and rotation."""
    from apps.ire.emitters.native_ai import _turn_item
    from apps.ire.graph import quarter_turn
    t = quarter_turn(80.0, 40.0, 0.0, 0.0)
    g = {"t": "g", "kids": [
        {"t": "p", "segs": [["M", 0.0, 0.0], ["L", 80.0, 0.0], ["C", 80.0, 10.0, 70.0, 40.0, 0.0, 40.0], ["Z"]],
         "fill": {"c": [1, 0, 0], "o": 1.0, "grad": {"kind": "linear", "from": [0.0, 0.0], "to": [80.0, 0.0],
                                                    "centre": [0.0, 0.0], "r": 0.0, "stops": []}}},
        {"t": "r", "x": 0.0, "y": 0.0, "w": 80.0, "h": 40.0, "r": 0.0},
        {"t": "x", "x": 5.0, "y": 10.0, "rot": 0.0},
        {"t": "i", "x": 0.0, "y": 0.0, "w": 20.0, "h": 10.0}], "clip": [["M", 0.0, 0.0], ["L", 80.0, 0.0]]}
    out = _turn_item(g, t)
    p, r, x, i = out["kids"]
    assert p["segs"][:2] == [["M", 0.0, 80.0], ["L", 0.0, 0.0]] and p["segs"][-1] == ["Z"]
    assert p["fill"]["grad"]["from"] == [0.0, 80.0] and p["fill"]["grad"]["to"] == [0.0, 0.0]
    assert (r["x"], r["y"], r["w"], r["h"]) == (0.0, 0.0, 40.0, 80.0)
    assert (x["x"], x["y"], x["rot"]) == (10.0, 75.0, 90.0)
    assert (i["rot"], round(i["x"] + i["w"] / 2, 6), round(i["y"] + i["h"] / 2, 6)) == (90.0, 5.0, 70.0)
    assert out["clip"] == [["M", 0.0, 80.0], ["L", 0.0, 0.0]]


def test_goal_1013_orientation_a_flat_box_is_composed_upright_and_turned_onto_its_standing_die():
    """A palette's carton, 122 x 14 x 192 on its die and lying flat: its front laid out 192 wide and 122 tall, upright,
    turned onto the die's front; its label laid out on the back as it is seen, turned with it; nothing of the front
    continued round a box that lies flat, said."""
    from apps.ire.compose import compose_components_graph
    params = DielineInputJSON(template="reverse_tuck_end_carton", unit="mm",
                              dimensions={"width_mm": 122.0, "depth_mm": 14.0, "height_mm": 192.0}, print_settings={},
                              construction={}, metadata={"product_name": "Enchanted Rose", "product_type": "palette"})
    coords = calculate_dieline(params)
    info = {"product_name": "Enchanted Rose", "description": "An eyeshadow palette.", "ingredients": "Talc, Mica.",
            "how_to_use": "Apply.", "warnings": "External use.", "net_weight": "27 g e 0.95 oz"}
    doc = compose_components_graph(coords, product_name="Enchanted Rose", subtitle="palette", panel_info=info,
                                   turn_faces=True)
    turned = [n for n, _p in doc.walk() if getattr(n, "type", "") == "group" and getattr(n, "turn", None) is not None]
    assert turned and all(g.turn[:4] == (0.0, -1.0, 1.0, 0.0) for g in turned)
    label = [g for g in turned if any(getattr(c, "type", "") == "sticker_bridge" for c in g.children)]
    assert label and label[0].children[-1].w > label[0].children[-1].h           # the label laid out wide, as seen



# --------------------------------------------------------------------------------------------------------------------
# [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (7): "Geometric shapes are DRAWN, not traced: 124's arch is
# jagged and broken into dashes. Arches, frames, ovals, borders and rules are rebuilt as clean geometric curves
# (symmetric where the concept is), with an even stroke, matched to the concept's shape." (8): "Glow is a real soft blur,
# never a stack of hard bands (124's arch glow reads as lines)." (9): "Gradients are smooth, never flat bands (124's sky
# shows stripes)."] Measured on 124's own redraw (fixtures_124/lid_art_153.png), drawn and read back.
# --------------------------------------------------------------------------------------------------------------------

def _goal_1013_lid():
    from apps.pipeline.targets.container import lid_art as LA
    return LA, LA.trace_art(_goal_1012_fixture("lid_art_153.png"), False)


def _goal_1013_drawn(group, w=190.0, h=120.0, dpi=300):
    """The art drawn at (5, 5) on its own page and read back as pixels (RGB, 0..255, float)."""
    import tempfile

    import numpy as np

    from apps.ire.graph import Document, Group
    doc = Document(page_w=w + 10.0, page_h=h + 10.0, root=Group(name="Artwork", role="artwork", children=[group]))
    with tempfile.TemporaryDirectory() as tmp:
        path = emit_pdf_ai(doc, tmp + "/lid.ai")
        with fitz.open(path) as pdf:
            pix = pdf[0].get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).astype(float), dpi / 25.4


def _goal_1013_seams(a, step=2.0, share=0.6):
    """Seams in a field of pixels: boundaries, along rows or columns, where most lines step by ``step`` levels at once —
    a band's edge; a smooth field's quantisation steps never line up so."""
    import numpy as np
    out = 0
    for axis in (0, 1):
        d = np.abs(np.diff(a, axis=axis)).max(axis=2)
        out += int(((d >= step).mean(axis=1 - axis) >= share).sum())
    return out


def test_goal_1013_geometry_124s_arch_is_found_and_drawn_as_one_even_symmetric_line():
    """124's gold arch, traced as 115 broken regions, is found as ONE line: folded on its own axis (symmetric, as the
    concept draws it), fitted within a pixel and a half of the line it replaces, one even width; the regions it replaces
    are left out of the trace; it is drawn as one stroked curve in its gold."""
    from apps.ire.graph import Path
    from apps.pipeline.services.concept_design_map import is_gold_hex
    LA, trace = _goal_1013_lid()
    gold = [line for line in trace["lines"] if is_gold_hex(line["hex"])]
    assert len(gold) == 1, trace["lines"]
    arch = gold[0]
    assert arch["kind"] == "arch" and arch["symmetric"] and arch["mirror"] >= 0.6 and arch["fit_px"] <= 1.5
    assert 0.8 <= arch["width"] * 190.0 <= 1.8                         # 124's arch about 1.2 mm on its 190 mm lid
    assert trace["measured"]["line_regions_replaced"] >= 50
    group = LA.art_group(trace, 0.0, 0.0, 190.0, 120.0)
    lines = next(g for g in group.children if g.name == "lid-lines").children
    drawn = [p for p in lines if is_gold_hex(p.stroke.color.to_hex())]
    assert len(drawn) == 1 and isinstance(drawn[0], Path) and drawn[0].fill is None
    # [his goal for the pitch, 2026-10-15, B (10): "a thin, bright gold line"] drawn thinner than its measured run,
    # in one bright gold — its gold and its bright core mixed
    assert abs(drawn[0].stroke.width_mm - arch["drawn_width"] * 190.0) < 1e-6
    assert abs(arch["drawn_width"] - 0.7 * arch["width"]) < 1e-4
    xs = [s.x for s in drawn[0].segments]
    axis = arch["axis"] * 190.0
    assert abs((xs[0] + xs[-1]) / 2.0 - axis) < 2.0                    # its feet either side of its own axis


def test_goal_1013_geometry_art_without_line_work_keeps_its_regions():
    """The control: a picture of soft blooms on a sky, no thin long line in it, finds none and its trace is left as it
    is; and 124's open tray photograph, read for its lid's inside (arches and ovals only), finds none — its hinge edge
    in broken shading and its dark straight edges are the photograph's, never drawn lines."""
    import io

    import numpy as np
    from PIL import Image, ImageDraw

    from apps.pipeline.services import line_geometry as LG
    from apps.pipeline.targets.container import lid_art as LA
    pic = Image.new("RGB", (768, 512))
    pic.paste(Image.fromarray(np.uint8([[[240 - y // 8, 196, 210 + y // 12]] * 768 for y in range(512)])))
    draw = ImageDraw.Draw(pic)
    for cx, cy, r in ((200, 300, 70), (560, 320, 80), (380, 400, 50)):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(214, 120, 150))
        draw.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=(236, 170, 190))
    buf = io.BytesIO()
    pic.save(buf, "PNG")
    trace = LA.trace_art(buf.getvalue(), False)
    assert trace["regions"] and not trace.get("lines")
    assert LG.find({"size_px": trace["size_px"], "regions": trace["regions"]}, LA._ring_points)["lines"] == []
    # the lid's inside is read from the tray's photograph — its arches and ovals only, never the photograph's edges
    tray = LA.trace_art(_goal_1012_fixture("tray_153.png"), False, kinds=("arch", "oval"))
    assert not tray.get("lines")


def test_goal_1013_geometry_the_drawn_arch_is_one_unbroken_line_where_the_trace_broke_it():
    """Read back from the drawing: the gold along the arch is one connected line, its legs followed down under the
    roses — the trace drew it as dozens of pieces."""
    import cv2
    import numpy as np

    from apps.pipeline.services.concept_design_map import is_gold_hex
    LA, trace = _goal_1013_lid()

    arch = next(line for line in trace["lines"] if is_gold_hex(line["hex"]))

    def gold_pieces(tr, drawn):
        # the arch as drawn: its line by itself (it runs on under the roses, which cover it where the picture does);
        # the trace before it: the gold it traced, in the illustration
        group = LA.art_group(tr, 5.0, 5.0, 190.0, 120.0)
        group.children = [g for g in group.children if g.name == drawn]
        a, k = _goal_1013_drawn(group)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        gold = ((r > 170) & (g > 120) & (b < 120) & (r - b > 90)).astype(np.uint8)
        # only the gold along the arch — 3 mm either side of its line — never the gold of the roses or the type
        along = np.zeros(gold.shape, np.uint8)
        cv2.polylines(along, [np.int32([[(5.0 + x * 190.0) * k, (5.0 + y * 120.0) * k] for x, y in arch["points"]])],
                      False, 1, int(round(6.0 * k)))
        n, _lab, stats, _c = cv2.connectedComponentsWithStats(gold & along, 8)
        return sum(1 for i in range(1, n) if stats[i][4] >= 0.5 * k * k)      # pieces of half a square mm or more
    old = dict(trace, lines=[], regions=LA.trace_art(_goal_1012_fixture("lid_art_153.png"), False,
                                                     lines=False)["regions"])
    assert gold_pieces(trace, "lid-lines") == 1 and gold_pieces(old, "lid-illustration") >= 5


def test_goal_1013_glow_the_arch_glows_as_a_smooth_mesh_never_stepped_bands():
    """Across the glow, read back from the drawing along the arch's own normals: no step — every pixel within a few
    levels of its neighbour — where the bands of 2026-10-12 stepped from one colour to the next."""
    import numpy as np
    LA, trace = _goal_1013_lid()

    def worst_step(tr, glows):
        group = LA.art_group(tr, 5.0, 5.0, 190.0, 120.0)
        group.children = [g for g in group.children if g.name in ("lid-sky", "lid-glow")]
        if not glows:
            group.children[1].children = LA._glow_paths(tr, 5.0, 5.0, 190.0, 120.0)
        a, k = _goal_1013_drawn(group)
        line = next(l for l in trace["lines"])       # the arch's own line: the same places on both drawings
        pts = np.array([(5.0 + x * 190.0, 5.0 + y * 120.0) for x, y in line["points"]])
        worst = 0.0
        for i in range(len(pts) // 4, len(pts) // 2):                    # the arch's upper left, clear of the roses
            d = pts[i + 1] - pts[i - 1]
            n = np.array([-d[1], d[0]]) / np.linalg.norm(d)
            prof = []
            for s in np.arange(0.5 * line["width"] * 190.0 + 0.4, 8.0, 1.0 / k):
                x, y = (pts[i] + n * s) * k
                prof.append(a[int(round(y)), int(round(x))])
            prof = np.array(prof)
            worst = max(worst, float(np.abs(np.diff(prof, axis=0)).max()))
        return worst
    assert worst_step(trace, True) <= 4.0
    # the control: the bands of 2026-10-12 grown round the traced gold (the arch not yet found), on the same places
    old = LA.trace_art(_goal_1012_fixture("lid_art_153.png"), False, lines=False)
    assert worst_step(old, False) >= 8.0



def test_goal_1013_glow_the_traces_own_glow_pieces_are_left_out_so_the_whole_lid_reads_smooth():
    """(8) "124's arch glow reads as lines": the trace cut the redraw's glow into flat rings of its colours and the lid
    drew them over its smooth glow — read on the whole lid, a flat colour, then a step. The pieces of the glow's own
    colours lying within its reach are left out: across the glow, on both sides of the arch's upper part, no step; the
    roses and leaves kept. The control: the same lid with those pieces drawn steps."""
    from unittest import mock

    import numpy as np

    from apps.pipeline.services import line_geometry as LG
    LA, trace = _goal_1013_lid()
    assert trace["measured"]["glow_regions_replaced"] >= 20

    def worst(tr):
        group = LA.art_group(tr, 5.0, 5.0, 190.0, 120.0)
        a, k = _goal_1013_drawn(group)
        line = next(l for l in tr["lines"])
        pts = np.array([(5.0 + x * 190.0, 5.0 + y * 120.0) for x, y in line["points"]])
        upper = [i for i in range(1, len(pts) - 1) if pts[i][1] <= np.percentile(pts[:, 1], 30)]
        out = 0.0
        for i in upper:
            d = pts[i + 1] - pts[i - 1]
            n = np.array([-d[1], d[0]]) / np.linalg.norm(d)
            for side in (1.0, -1.0):
                prof = [a[int(round(q[1])), int(round(q[0]))] for q in
                        ((pts[i] + side * n * t) * k for t in np.arange(0.5 * line["width"] * 190.0 + 0.4, 5.0, 1.0 / k))]
                out = max(out, float(np.abs(np.diff(np.array(prof), axis=0)).max()))
        return out
    assert worst(trace) <= 6.0
    with mock.patch.object(LG, "glow_pieces", lambda *a, **k: []):
        kept = LA.trace_art(_goal_1012_fixture("lid_art_153.png"), False)
    assert len(kept["regions"]) - len(trace["regions"]) == trace["measured"]["glow_regions_replaced"]
    assert worst(kept) >= 10.0

def test_goal_1013_glow_the_layered_file_carries_the_mesh_smoothly_and_says_how():
    """The layered file carries each smooth field in the form Illustrator draws as the drawing does — the sky as thin
    strips, each one smooth gradient across (Illustrator runs a gradient across its own shape), within a small ΔE of
    the drawing's own blend, said in what it does not carry; the glow as strokes along its line under Illustrator's own
    Gaussian blur, live — counted with what is built."""
    import re

    from apps.ire.emitters import native_ai
    from apps.ire.graph import Document, Group
    LA, trace = _goal_1013_lid()
    doc = Document(page_w=200.0, page_h=130.0, root=Group(name="Artwork", role="artwork", children=[
        LA.art_group(trace, 5.0, 5.0, 190.0, 120.0)]))
    data = native_ai.tree(doc)
    flat = [i for b in data["boards"] for lay in b["layers"] for i in native_ai._walk(lay["items"])]
    strips = [i for i in flat if i.get("t") == "r" and "-strip-" in i.get("name", "")]
    assert strips and all(i["fill"]["grad"]["kind"] == "linear" and i["fill"]["grad"]["from"][1] ==
                          i["fill"]["grad"]["to"][1] for i in strips)            # each a gradient straight across
    blurred = [i for i in flat if i.get("blur")]
    assert blurred and all(i["t"] == "p" and i["stroke"] and i["fill"] is None for i in blurred)
    assert native_ai.expected(data)["blurs"] == len(blurred)
    said = [e for e in data["effects_not_carried"] if "thin strips" in e]
    assert any(e.startswith("lid-sky:") for e in said)
    assert all(float(re.search(r"ΔE ([0-9.]+)", e).group(1)) <= 2.0 for e in said), said
    assert not [e for e in data["effects_not_carried"] if e.startswith("lid-glow")]   # the glow is carried, live

def test_goal_1013_gradient_the_sky_is_one_smooth_mesh_with_no_seams():
    """124's sky — 96 stacked bands that showed stripes — is one smooth mesh over the lid, its corners the field's own
    colours: read back, not one seam in it, where the bands showed seams; and its colour where it is drawn is the
    field's."""
    import numpy as np
    LA, trace = _goal_1013_lid()
    group = LA.art_group(trace, 5.0, 5.0, 190.0, 120.0)
    sky = group.children[0]
    assert sky.children[0].fill.type == "mesh" and len(sky.children) == 1
    group.children = [sky]
    a, k = _goal_1013_drawn(group)
    patch = a[int(20 * k):int(45 * k), int(15 * k):int(60 * k)]       # the sky's upper left, clear of the art
    assert _goal_1013_seams(patch) == 0
    at = LA.sky_at(trace)
    for fx, fy in ((0.1, 0.1), (0.5, 0.05), (0.9, 0.2)):
        want = at(fx, fy)
        got = a[int((5.0 + fy * 120.0) * k), int((5.0 + fx * 190.0) * k)]
        assert max(abs(got[c] - int(want[1 + 2 * c:3 + 2 * c], 16)) for c in range(3)) <= 4, (fx, fy, want, got)


def test_goal_1013_gradient_the_bands_of_2026_10_12_show_seams_the_control():
    """The control for the test above: the sky as 2026-10-12 drew it — one band per row of the field — shows seams."""
    from apps.ire.graph import Color, GradientFill, GradientStop, Group, Rect
    LA, trace = _goal_1013_lid()
    rows = trace["sky"]["rows"]
    n = len(rows)
    bands = []
    for i, row in enumerate(rows):
        stops = [GradientStop(offset=j / float(len(row) - 1), color=Color.from_hex(c)) for j, c in enumerate(row)]
        top = 5.0 + 120.0 * i / n
        bands.append(Rect(name="sky-%d" % i, x=5.0, y=top, w=190.0, h=120.0 / n * 1.25,
                          fill=GradientFill(kind="linear", stops=stops, x1=5.0, y1=top, x2=195.0, y2=top)))
    a, k = _goal_1013_drawn(Group(name="old sky", children=bands))
    assert _goal_1013_seams(a[int(20 * k):int(45 * k), int(15 * k):int(60 * k)]) > 0



def _goal_1013_window():
    """125's concept traced as the map's shapes trace it (``trace_shapes``) — its window."""
    import json
    import os

    from apps.pipeline.services import concept_design_map as dm
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "pipeline",
                        "tests", "fixtures_125")
    with open(os.path.join(here, "concept_125.png"), "rb") as fh:
        png = fh.read()
    with open(os.path.join(here, "map_125.json"), encoding="utf-8") as fh:
        record = json.load(fh)
    shapes = dm.trace_shapes(png, record)
    return shapes, next(w for w in shapes.get("windows") or [] if "arch" in w["part"])


def test_goal_1013_geometry_a_window_under_a_gold_arch_is_read_as_its_own_arch():
    """125's lavender window under a gold ogee arch, traced as a box until now: read as its arch from its own rim —
    one line, symmetric about its own axis, within a pixel and a half of the rim — its field lavender over pink, its
    rim's glow mint fading to the ground; read from the concept, nothing paid."""
    from apps.pipeline.services.concept_design_map import is_gold_hex
    _shapes, win = _goal_1013_window()
    rim = win["rim"]
    assert win["shape"] == "arch" and rim["gold"] and is_gold_hex(rim["ink"])
    assert rim["mirror"] >= 0.6 and rim["fit_px"] <= 1.5
    xs = [p[0] for p in rim["points"]]
    assert abs((min(xs) + max(xs)) / 2.0 - rim["axis"]) < 0.01                  # its feet either side of its axis
    apex = min(rim["points"], key=lambda p: p[1])
    assert abs(apex[0] - rim["axis"]) < 0.01                                    # its apex on it
    top, foot = win["field"]["rows"][0], win["field"]["rows"][-1]

    def rgb(hx):
        return int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
    assert rgb(top[6])[2] > rgb(top[6])[1] + 15                                 # lavender: blue over green
    assert rgb(foot[6])[0] > rgb(top[6])[0] + 15                                # pinker at its foot
    bands = win["glow"]["bands"]
    assert len(bands) >= 2 and rgb(bands[0]["hex"])[1] > rgb(bands[0]["hex"])[0]   # mint: green over red


def test_goal_1013_gradient_the_window_is_drawn_smooth_under_its_drawn_arch():
    """Drawn as the front draws its map: the field one smooth mesh inside the arch (no seam in it), the glow a smooth mesh
    outside, the rim ONE stroked line in its gold on the foil plate's list — read back from the drawing."""
    from types import SimpleNamespace

    import cv2
    import numpy as np

    from apps.ire.compose_container import _map_front_group
    from apps.ire.graph import Document, Group
    shapes, win = _goal_1013_window()
    map_front = {"shapes": dict(shapes, types=[], marks=[], lines=[], bands=[], frames=[], rules=[], scatters=[],
                                shapes=[], windows=[win]), "ground": "#F2C7CA"}
    zone = {"x": 0.0, "y": 0.0, "width": 192.0, "height": 122.0, "zone_id": "front"}
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    outline = [MoveTo(x=0.0, y=0.0), LineTo(x=192.0, y=0.0), LineTo(x=192.0, y=122.0), LineTo(x=0.0, y=122.0),
               ClosePath()]
    group, _places, record = _map_front_group(map_front, zone, SimpleNamespace(width_mm=192.0, height_mm=122.0,
                                                                               silhouette=outline), 1.0, 4.0, 4.0)
    nodes = {n.name: n for n, _p in Document(page_w=200, page_h=130, root=group).walk() if getattr(n, "name", None)}
    assert nodes["window-map-0"].fill.type == "mesh" and nodes["window-glow-map-0-0"].fill.type == "mesh"
    assert nodes["window-glow-map-0-1"].fill.type == "mesh"                 # its two halves, each on its own side
    rim = nodes["window-rim-gold-map-0"]
    assert rim.fill is None and rim.stroke is not None and "window-rim-gold-map-0" in record["gold_nodes"]
    a, k = _goal_1013_drawn(Group(name="front", role="artwork", children=[group]), w=192.0, h=122.0)
    fb = win["field"]["box"]
    inner = a[int((4 + (fb[1] + 0.3 * (fb[3] - fb[1])) * 122) * k):int((4 + (fb[1] + 0.6 * (fb[3] - fb[1])) * 122) * k),
              int((4 + (fb[0] + 0.3 * (fb[2] - fb[0])) * 192) * k):int((4 + (fb[0] + 0.7 * (fb[2] - fb[0])) * 192) * k)]
    assert _goal_1013_seams(inner) == 0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    gold = ((r > 150) & (g > 110) & (b < 140) & (r - b > 50)).astype(np.uint8)
    n, _lab, stats, _c = cv2.connectedComponentsWithStats(gold, 8)
    assert sum(1 for i in range(1, n) if stats[i][4] >= 0.5 * k * k) == 1      # the rim, one unbroken line


def test_goal_1013_geometry_each_kind_of_line_is_drawn_as_its_own_geometry():
    """(7) "Arches, frames, ovals, borders and rules are rebuilt as clean geometric curves": a trace's regions as it
    breaks three lines into dashes — a gold rule, a berry oval ring and a gold arch — the rule is found as its two ends,
    the ring as an oval (closed, round, where it stands), the arch folded on its own axis; their dashes left out of the
    trace; each drawn as one stroke of an even width."""
    import math

    import numpy as np

    from apps.pipeline.services import line_geometry as LG
    from apps.pipeline.targets.container import lid_art as LA
    W, H, wide = 1536, 1024, 14.0                                    # a redraw's own size, its lines about 14 px

    def dash(p, q, fill, gap=6.0):
        (x0, y0), (x1, y1) = p, q
        d = math.hypot(x1 - x0, y1 - y0)
        nx, ny = -(y1 - y0) / d * wide / 2, (x1 - x0) / d * wide / 2
        x1, y1 = x1 - (x1 - x0) * gap / d, y1 - (y1 - y0) * gap / d      # broken as a trace breaks a line
        ring = [[(x0 + nx) / W, (y0 + ny) / H], [(x1 + nx) / W, (y1 + ny) / H], [(x1 - nx) / W, (y1 - ny) / H],
                [(x0 - nx) / W, (y0 - ny) / H]]
        return {"fill": fill, "rings": [ring]}
    gold, berry = "#CDA046", "#963C64"
    regions = [dash((x, 930), (x + 46, 930), gold) for x in range(140, 1400, 46)]
    oval = [(1190 + 190 * math.cos(math.radians(a)), 420 + 120 * math.sin(math.radians(a))) for a in range(0, 361, 6)]
    regions += [dash(oval[k], oval[k + 1], berry) for k in range(len(oval) - 1)]
    arch = [(500 + 260 * math.cos(math.radians(a)), 720 - 440 * math.sin(math.radians(a))) for a in range(0, 181, 3)]
    regions += [dash(arch[k], arch[k + 1], gold) for k in range(len(arch) - 1)]
    found = LG.find({"size_px": [W, H], "regions": regions}, LA._ring_points)
    by = {line["kind"]: line for line in found["lines"]}
    assert sorted(by) == ["arch", "oval", "rule"], [(l["kind"], l["hex"]) for l in found["lines"]]
    assert len(found["replaced"]) >= 0.9 * len(regions)               # their dashes left out of the trace
    rule = np.array(by["rule"]["points"]) * [W, H]
    assert len(rule) == 2 and abs(rule[0][1] - 930) < 2 and abs(rule[1][1] - 930) < 2 and rule[:, 0].min() < 150
    ring = np.array(by["oval"]["points"]) * [W, H]
    assert abs(ring[:, 0].mean() - 1190) < 6 and abs(ring[:, 1].mean() - 420) < 6
    assert abs((ring[:, 0].max() - ring[:, 0].min()) / 2 - 190) < 8 and abs((ring[:, 1].max() - ring[:, 1].min()) / 2 - 120) < 8
    assert by["arch"]["mirror"] >= 0.6 and abs(by["arch"]["axis"] * W - 500) < 6
    assert all(abs(line["width"] * W - wide) < 4 for line in found["lines"]), [l["width"] * W for l in found["lines"]]
    trace = {"size_px": [W, H], "round": False, "sky": {"rows": [["#F2D6DE"] * 4] * 4},
             "regions": [r for j, r in enumerate(regions) if j not in set(found["replaced"])], "lines": found["lines"],
             "measured": {}}
    group = LA.art_group(trace, 0.0, 0.0, 180.0, 120.0)
    strokes = next(g for g in group.children if g.name == "lid-lines").children
    assert len(strokes) == 3 and all(p.fill is None and p.stroke.width_mm > 0 for p in strokes)


# --------------------------------------------------------------------------------------------------------------------
# [His goal of 2026-10-13, (7)-(10)] the drawing and the layered file draw alike — measured on 125's front, drawn again:
# its window's glow and field washed out in the drawing (a mesh painted at the alpha a faded shape before it left), its
# field a box inside its arch, its words in the drawing out of their case and spacing, and in the layered file each
# strip of its turned field a gradient run across its 1 mm width (a sawtooth) — each fixed in the engine.
# --------------------------------------------------------------------------------------------------------------------

def test_goal_1013_agree_a_mesh_paints_at_its_own_strength_after_a_faded_shape():
    """125's front: its soft rooms (its ground at 30%) drawn before its window left the page's fill alpha at 30%, and the
    window's glow and field — smooth meshes — painted washed out in the drawing while the layered file drew them whole.
    A mesh paints at its own strength on every document, the exempt box among them: read back, its own colour."""
    from apps.ire.graph import ClosePath, Color, LineTo, MeshFill, MoveTo, Path, SolidFill
    lav = "#B19EC6"
    room = Path(name="soft-room-0", segments=[MoveTo(x=0.0, y=0.0), LineTo(x=60.0, y=0.0), LineTo(x=60.0, y=40.0),
                                              LineTo(x=0.0, y=40.0), ClosePath()],
                fill=SolidFill(color=Color.from_hex("#F4CAD1"), opacity=0.3))
    field = Path(name="window-map-0", segments=[MoveTo(x=10.0, y=10.0), LineTo(x=50.0, y=10.0), LineTo(x=50.0, y=30.0),
                                                LineTo(x=10.0, y=30.0), ClosePath()],
                 fill=MeshFill(patches=[[10.0, 10.0, 50.0, 10.0, 50.0, 30.0, 10.0, 30.0, lav, lav, lav, lav]]))
    a, k = _goal_1013_drawn(Group(name="front", children=[room, field]), w=60.0, h=40.0)
    got = a[int(20.0 * k), int(30.0 * k)]
    assert max(abs(got[c] - int(lav[1 + 2 * c:3 + 2 * c], 16)) for c in range(3)) <= 3, got


def _goal_1013_glow_over(ground: str, parts, old: bool = False):
    """The glow parts drawn over a ground — or, ``old``, as 2026-10-13 drew them: faded to a colour read beside the
    concept's arch (#DCD4D4), never to nothing — read back at 600 dpi."""
    from apps.ire.graph import ClosePath, Color, LineTo, MeshFill, MoveTo, Path, Rect, SolidFill
    kids = [Rect(name="ground", x=0.0, y=0.0, w=100.0, h=80.0, fill=SolidFill(color=Color.from_hex(ground)))]
    for n, part in enumerate(parts):
        x0, y0, x1, y1 = part["box"]
        patches = [p[:10] + (["#DCD4D4", "#DCD4D4"] if a[2] == 0.0 else p[10:12]) for p, a in
                   zip(part["patches"], part["alphas"])] if old else part["patches"]
        kids.append(Path(name="glow-%d" % n, fill=MeshFill(patches=patches, alphas=None if old else part["alphas"]),
                         segments=[MoveTo(x=x0, y=y0), LineTo(x=x1, y=y0), LineTo(x=x1, y=y1), LineTo(x=x0, y=y1),
                                   ClosePath()]))
    return _goal_1013_drawn(Group(name="glow", children=kids), w=100.0, h=80.0, dpi=600)


def test_goal_1013_glow_fades_to_nothing_over_whatever_is_drawn_beneath():
    """(8) "a real soft blur": a glow fades from its colours to nothing at its reach — over a pale ground and over a dark
    one alike its reach is the ground's own colour, no step where it ends; never faded to a colour read from elsewhere
    (125's glow faded to the concept's #DCD4D4 over a box whose ground is #F4CAD1) — the control, faded so, steps."""
    import numpy as np

    from apps.pipeline.services import line_geometry as LG
    line = {"kind": "arch", "width": 0.004,
            "points": [(0.2, 0.9), (0.2, 0.5), (0.35, 0.25), (0.5, 0.15), (0.65, 0.25), (0.8, 0.5), (0.8, 0.9)]}
    bands = [{"to": 0.01, "hex": "#DCF6F0"}, {"to": 0.03, "hex": "#CFE4E1"}]
    parts = LG.glow_parts(line, 0.0, 0.0, 100.0, 80.0, bands)
    assert parts and all(p["alphas"] and len(p["alphas"]) == len(p["patches"]) for p in parts)
    assert any(a[2] == 0.0 for p in parts for a in p["alphas"])                     # each fades to nothing …
    assert all(p[10] == bands[-1]["hex"] for part in parts for p, a in zip(part["patches"], part["alphas"])
               if a[2] == 0.0)                                                         # … in its own last colour

    def profile(ground, old=False):
        a, k = _goal_1013_glow_over(ground, parts, old)
        row = int(0.7 * 80.0 * k)                                   # the left leg, upright there: across it, outward
        xs = [int(round((20.0 - 0.35 - 0.05 * j) * k)) for j in range(0, 160)]   # from the rim's outer edge
        return np.array([a[row, x] for x in xs])
    for ground in ("#F4CAD1", "#2B2D5C"):
        prof = profile(ground)
        want = np.array([int(ground[1 + 2 * c:3 + 2 * c], 16) for c in range(3)], float)
        assert np.abs(prof[-1] - want).max() <= 3, (ground, prof[-1])          # its reach is the ground's own colour
        assert np.abs(np.diff(prof, axis=0)).max() <= 6, ground               # and no step on the way
    assert np.abs(np.diff(profile("#2B2D5C", old=True), axis=0)).max() >= 40   # the control: a step where it ends


def test_goal_1013_gradient_a_relaid_windows_arch_field_and_glow_move_together():
    """(7) "matched to the concept's shape": 125's front is laid out again on its box (as one block, then fitted to its
    safe area) — its window's box and field moved and its arch stood where the concept drew it, the field a lavender box
    inside it. Its arch, its rim's axis and width and its glow's reach move with its box; drawn, the gold rim stands
    round the moved box and the lavender fills it to the rim's legs."""
    from types import SimpleNamespace

    import numpy as np

    from apps.ire.compose import _frac_walk
    from apps.ire.compose_container import _map_front_group
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    from apps.pipeline.services import line_geometry as LG
    shapes, win = _goal_1013_window()
    k, bx, by, ky = 0.8, 0.1, 0.05, 0.9
    laid = _frac_walk(win, k, bx, by, ky)
    xs, ys = [p[0] for p in laid["points"]], [p[1] for p in laid["points"]]
    assert abs(min(xs) - laid["box"][0]) < 1e-4 and abs(max(xs) - laid["box"][2]) < 1e-4
    assert abs(min(ys) - laid["box"][1]) < 1e-4 and abs(max(ys) - laid["box"][3]) < 1e-4    # the arch with its box
    assert abs(laid["rim"]["axis"] - (k * win["rim"]["axis"] + bx)) < 1e-9
    assert abs(laid["rim"]["width"] - k * win["rim"]["width"]) < 1e-9
    assert all(abs(a["to"] - k * b["to"]) < 1e-9 for a, b in zip(laid["glow"]["bands"], win["glow"]["bands"]))
    map_front = {"shapes": dict(shapes, types=[], marks=[], lines=[], bands=[], frames=[], rules=[], scatters=[],
                                shapes=[], windows=[laid]), "ground": "#F2C7CA"}
    zone = {"x": 0.0, "y": 0.0, "width": 192.0, "height": 122.0, "zone_id": "front"}
    outline = [MoveTo(x=0.0, y=0.0), LineTo(x=192.0, y=0.0), LineTo(x=192.0, y=122.0), LineTo(x=0.0, y=122.0),
               ClosePath()]
    group, _places, _record = _map_front_group(map_front, zone, SimpleNamespace(width_mm=192.0, height_mm=122.0,
                                                                                silhouette=outline), 1.0, 4.0, 4.0)
    a, px = _goal_1013_drawn(Group(name="front", role="artwork", children=[group]), w=192.0, h=122.0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    gold = (r > 150) & (g > 110) & (b < 140) & (r - b > 50)
    cols = np.where(gold.any(axis=0))[0]
    lb = laid["box"]
    assert abs(cols.min() / px - 4.0 - lb[0] * 192.0) <= 1.0 and abs(cols.max() / px - 4.0 - lb[2] * 192.0) <= 1.0
    fy = lb[1] + 0.75 * (lb[3] - lb[1])
    leg = min((p for p in laid["points"] if p[0] < laid["rim"]["axis"]), key=lambda p: abs(p[1] - fy))[0]
    rr, gg, bb = a[int((4.0 + fy * 122.0) * px), int((4.0 + leg * 192.0 + 2.0) * px)]   # 2 mm inside its leg
    assert bb > gg + 15, (rr, gg, bb)                                # lavender: blue over green, never the pink ground
    grid = LG.field_grid(win["field"]["rows"], 10.0, 10.0, 50.0, 40.0, reach=[0.0, 5.0, 70.0, 50.0])
    assert grid["xs"][0] == 0.0 and grid["xs"][-1] == 70.0 and grid["ys"][0] == 5.0 and grid["ys"][-1] == 50.0
    assert LG.field_grid(win["field"]["rows"], 10.0, 10.0, 50.0, 40.0)["xs"][0] == 10.0   # no shape given: its box


def test_goal_1013_agree_an_exempt_drawing_prints_a_runs_own_case_and_letter_spacing():
    """125's box is drawn by the exempt drawer, which printed its front's "EYESHADOW PALETTE" as "Eyeshadow Palette", its
    letters unspaced, while the layered file set it as the concept does. A run that declares its case and its spacing
    prints in them on that drawer too; a run that declares neither prints as it always did."""
    import tempfile

    from apps.ire.graph import Color, Document
    ink = Color.from_hex("#6B3A6E")
    doc = Document(page_w=140.0, page_h=50.0, root=Group(name="Artwork", role="artwork", children=[
        TextRun(name="spaced", text="Eyeshadow Palette", x=70.0, y=15.0, size_pt=9.0, color=ink, align="center",
                text_case="upper", tracking_em=0.3),
        TextRun(name="upper", text="Eyeshadow Palette", x=70.0, y=28.0, size_pt=9.0, color=ink, align="center",
                text_case="upper"),
        TextRun(name="plain", text="18 shades", x=70.0, y=41.0, size_pt=9.0, color=ink, align="center")]))
    with tempfile.TemporaryDirectory() as tmp:
        path = emit_pdf_ai(doc, tmp + "/words.ai")
        with fitz.open(path) as pdf:
            lines = []
            for block in pdf[0].get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    chars = [ch for span in line["spans"] for ch in span["chars"]]
                    lines.append(("".join(ch["c"] for ch in chars), line["bbox"]))
    lines.sort(key=lambda t: t[1][1])
    (spaced, sb), (upper, ub), (plain, _pb) = lines
    # the reader puts its own spaces between letters set wide apart: the letters, read without them
    assert spaced.replace(" ", "") == "EYESHADOWPALETTE" and upper == "EYESHADOW PALETTE" and plain == "18 shades"
    gap = 0.3 * 9.0 * (len("EYESHADOW PALETTE") - 1)                   # its spacing, after every letter but the last
    assert abs((sb[2] - sb[0]) - (ub[2] - ub[0]) - gap) <= 1.5
    assert abs((sb[0] + sb[2]) / 2.0 - 70.0 * 72.0 / 25.4) <= 1.0          # centred where it is set, spacing and all


def test_goal_1013_agree_the_layered_file_runs_each_gradient_the_way_the_drawing_does():
    """Illustrator runs a new gradient left to right across its item's own box whatever run it is given, and a gradient
    turned by itself spans the box's extent along its new angle about the box's middle (measured in Illustrator,
    2026-10-14) — so a turned face's strips (125's window, its box lying flat) ran across their 1 mm width: a sawtooth.
    The runtime's own gradientColor, run against that measured behaviour: a strip turned to stand, one standing the
    other way, an angled run inside its box, one longer than its box, three stops, a radial — each paints the drawing's
    own colour at every point of its item; the control, the run Illustrator drew before, does not."""
    import json
    import math
    import shutil
    import subprocess

    from apps.ire.emitters import native_ai
    rt = native_ai._RUNTIME
    fns = rt[rt.index("function gradientColor(gr, item) {"):rt.index("function paint(item, it, layer) {")]
    two = [[0.0, [1.0, 0.0, 0.0]], [1.0, [0.0, 0.0, 1.0]]]
    cases = [
        {"x": 10, "y": 10, "w": 4, "h": 100, "grad": {"kind": "linear", "from": [12, 10], "to": [12, 110], "stops": two}},
        {"x": 20, "y": 10, "w": 4, "h": 100, "grad": {"kind": "linear", "from": [22, 110], "to": [22, 10], "stops": two}},
        {"x": 30, "y": 10, "w": 80, "h": 40, "grad": {"kind": "linear", "from": [50, 20], "to": [90, 40], "stops": two}},
        {"x": 30, "y": 60, "w": 80, "h": 20, "grad": {"kind": "linear", "from": [10, 70], "to": [130, 70], "stops": two}},
        {"x": 120, "y": 10, "w": 20, "h": 80, "grad": {"kind": "linear", "from": [130, 10], "to": [130, 90], "stops": [
            [0.0, [1.0, 0.0, 0.0]], [0.3, [0.0, 1.0, 0.0]], [1.0, [0.0, 0.0, 1.0]]]}},
        {"x": 120, "y": 100, "w": 60, "h": 30, "grad": {"kind": "radial", "centre": [150, 115], "r": 10, "stops": two}},
    ]
    mm, top = 72.0 / 25.4, 1000.0
    js = """var MM = %r, X0 = 0, Y0 = %r;
function P(x, y) { return [X0 + x * MM, Y0 - y * MM]; }
function ink(v) { return v; }
var GradientType = {RADIAL: "radial", LINEAR: "linear"};
function GradientColor() {}
var doc = {gradients: {add: function () { var s = [{}, {}]; s.add = function () { this.push({}); };
                                          return {gradientStops: s}; }}};
%s
var CASES = %s, out = [];
for (var i = 0; i < CASES.length; i++) {
    var c = CASES[i], tl = P(c.x, c.y), br = P(c.x + c.w, c.y + c.h);
    var made = gradientColor(c.grad, {geometricBounds: [tl[0], tl[1], br[0], br[1]]});
    var st = made.gc.gradient.gradientStops, stops = [];
    for (var k = 0; k < st.length; k++) { stops.push([st[k].rampPoint / 100, st[k].color]); }
    out.push({turn: made.turn, stops: stops});
}
console.log(JSON.stringify(out));
""" % (mm, top, fns, json.dumps(cases))
    node = shutil.which("node") or "/opt/homebrew/bin/node"
    made = json.loads(subprocess.run([node, "-e", js], capture_output=True, text=True, check=True, timeout=60).stdout)

    def at(stops, t):
        t = min(max(t, stops[0][0]), stops[-1][0])
        for i in range(1, len(stops)):
            if t <= stops[i][0] + 1e-12:
                f = (t - stops[i - 1][0]) / max(stops[i][0] - stops[i - 1][0], 1e-12)
                return [p + (q - p) * f for p, q in zip(stops[i - 1][1], stops[i][1])]
        return stops[-1][1]

    def worst(case, turn, stops):
        g = case["grad"]
        left, right = case["x"] * mm, (case["x"] + case["w"]) * mm
        upper, lower = top - case["y"] * mm, top - (case["y"] + case["h"]) * mm
        W, H, cx, cy = right - left, upper - lower, (left + right) / 2.0, (upper + lower) / 2.0
        out = 0.0
        for fx in (0.1, 0.3, 0.5, 0.7, 0.9):
            for fy in (0.1, 0.3, 0.5, 0.7, 0.9):
                px, py = case["x"] + fx * case["w"], case["y"] + fy * case["h"]
                qx, qy = px * mm, top - py * mm
                if g["kind"] == "radial":                    # Illustrator's: about the box's middle, its own reach
                    t = math.hypot(qx - cx, qy - cy) / (math.hypot(W, H) / (2.0 * math.sqrt(2.0)))
                    want = math.hypot(px - g["centre"][0], py - g["centre"][1]) / g["r"]
                else:                                         # Illustrator's: the box's extent along the turned run
                    ux, uy = math.cos(math.radians(turn)), math.sin(math.radians(turn))
                    S = W * abs(ux) + H * abs(uy)
                    t = ((qx - (cx - ux * S / 2.0)) * ux + (qy - (cy - uy * S / 2.0)) * uy) / S
                    (ax, ay), (bx, by) = g["from"], g["to"]
                    want = ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)
                out = max(out, max(abs(p - q) for p, q in zip(at(stops, t), at(g["stops"], want))))
        return out
    for case, got in zip(cases, made):
        assert worst(case, got["turn"], got["stops"]) <= 0.01, (case, got)
    assert worst(cases[0], 0.0, cases[0]["grad"]["stops"]) >= 0.4               # the control: run across its width


def test_goal_1013_agree_illustrator_is_waited_for_as_long_as_the_run_may_take():
    """125's layered file took 145 s to build and was said "not saved": the Apple event gave up at its own two minutes
    while Illustrator went on and saved. The event now waits as long as the run may take."""
    from types import SimpleNamespace
    from unittest import mock

    from apps.ire.handoff import illustrator_exec as IE
    sent = []

    def run(args, **_kw):
        sent.append(args)
        return SimpleNamespace(returncode=0, stdout='{"saved": true}', stderr="")
    with mock.patch.object(IE, "illustrator_available", return_value=True), mock.patch.object(IE.subprocess, "run", run):
        assert IE.run_jsx("/tmp/a.jsx", timeout_s=300)["saved"] is True
    script = sent[-1][2]
    assert "with timeout of 300 seconds" in script and script.index("with timeout") < script.index("do javascript")


# --- [His goal after the pitch page, 2026-10-15, A (4) COMPLETENESS and A (5) CONTRAST] ----------------------------

def _pitch_a4_picture():
    """A flat carton front, 400 x 500 px, BGR: a cream ground; blue tile rules running straight down both sides outside
    the panel; a thin gold frame round a cream panel; in the panel a gold disc with a blue cross over it (a flower and
    its outline, in two inks)."""
    import numpy as np
    img = np.zeros((500, 400, 3), np.uint8)
    img[:] = (229, 237, 240)                                  # cream #F0EDE5, BGR
    blue, gold = (115, 62, 34), (60, 144, 198)                # #223E73, #C6903C
    for x in (20, 40, 360, 380):
        img[10:490, x:x + 3] = blue                           # the tiles' own straight runs, further out
    img[80:83, 70:331] = gold                                 # the frame: top, foot, left, right
    img[417:420, 70:331] = gold
    img[80:420, 70:73] = gold
    img[80:420, 328:331] = gold
    yy, xx = np.mgrid[0:500, 0:400]
    img[(xx - 200) ** 2 + (yy - 200) ** 2 <= 35 ** 2] = gold  # the flower's gold disc …
    img[160:240, 196:204] = blue                              # … and its blue over it
    img[196:204, 160:240] = blue
    return img, np.ones((500, 400), np.uint8), (0.0, 0.0, 400.0, 500.0)


def test_pitch_a4_a_frame_named_in_its_window_is_traced_in_its_gold_and_the_window_fills_to_it():
    """132's "gold double-rule frame was missing": the read named it only in its window's words ("ivory cartouche with
    gold frame", finished "gold foil"), so no tracer ever looked for it. It is traced round the window in the picture's
    gold — never the blue tiles' straight runs further out — and the window fills out to it."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import line_art as la
    img, mask, pbox = _pitch_a4_picture()
    window = {"kind": "window", "name": "ivory cartouche with gold frame", "finish": "gold foil",
              "box": [0.2, 0.18, 0.8, 0.82], "colour": "#F0EDE5"}
    frame = dm.window_frame(img, mask, pbox, window, [])
    assert frame is not None and "refused" not in frame, frame
    assert frame["shape"] == "quad" and frame["gold"] and frame["window"] == window["name"], frame
    for got, want in zip(frame["box"], (71.5 / 400, 81.5 / 500, 329.5 / 400, 418.5 / 500)):
        assert abs(got - want) <= 0.01, frame["box"]
    # a window whose words name no frame, nor any gold, looks for none
    assert dm.window_frame(img, mask, pbox, dict(window, name="cream panel", finish="matte"), []) is None
    # … nor one a traced frame already rings
    assert dm.window_frame(img, mask, pbox, window, [frame]) is None
    filled = la.trace_window(img, mask, pbox, window, [frame])
    assert filled["shape"] == "quad" and filled["box"] == [min(c[0] for c in frame["corners"]),
                                                           min(c[1] for c in frame["corners"]),
                                                           max(c[0] for c in frame["corners"]),
                                                           max(c[1] for c in frame["corners"])], filled


def test_pitch_a4_a_shape_read_in_two_inks_is_traced_in_both_and_shade_is_never_a_second_ink():
    """132's centre flower was traced in its gold alone. Its second ink (its blue outline and leaves) is traced too, as
    a layer over its first, kept to the shape's own box; a second ink that is the first under another light is never
    traced ("colours never from shadow")."""
    from apps.pipeline.services import concept_design_map as dm
    img, mask, pbox = _pitch_a4_picture()
    flower = {"kind": "shape", "name": "stylised flower emblem", "box": [0.4, 0.32, 0.6, 0.48], "colour": "#C6903C",
              "second_colour": "#223E73"}
    title = {"kind": "type", "name": "CITRUS", "box": [0.3, 0.485, 0.7, 0.52], "colour": "#223E73"}
    layers, said = dm.shape_layers(img, mask, pbox, flower, "#F0EDE5", [title])
    assert said == [] and len(layers) == 1 and layers[0]["ink"] == "#223E73", (layers, said)
    lx0, ly0, lx1, ly1 = layers[0]["box"]
    assert 0.39 <= lx0 and lx1 <= 0.61 and 0.31 <= ly0 and ly1 <= 0.49, layers[0]["box"]
    shade = dict(flower, second_colour="#9A713A")             # the gold in shade: one printed colour
    assert dm.shape_layers(img, mask, pbox, shade, "#F0EDE5", [title]) == ([], [])


def test_pitch_a4_a_solid_inside_a_window_is_drawn_over_the_window_and_its_frame():
    """132's flower was traced and drawn — then painted out by its cartouche's fill, drawn after it. A solid lying in a
    window is drawn over the window and its frame, its further ink over it; a solid outside every window stays under."""
    from types import SimpleNamespace

    from apps.ire.compose_container import _map_front_group
    from apps.ire.graph import ClosePath, Group, LineTo, MoveTo

    def square(x0, y0, x1, y1):
        return [[[[x0, y0], [x0, y0, x1, y0, x1, y0], [x1, y0, x1, y1, x1, y1], [x1, y1, x0, y1, x0, y1],
                  [x0, y1, x0, y0, x0, y0]]]]
    shapes = {"shapes": [{"part": "flower", "ink": "#C6903C", "box": [0.4, 0.3, 0.6, 0.5],
                          "cubics": square(0.4, 0.3, 0.6, 0.5),
                          "layers": [{"ink": "#223E73", "box": [0.45, 0.35, 0.55, 0.45],
                                      "cubics": square(0.45, 0.35, 0.55, 0.45)}]},
                         {"part": "corner leaf", "ink": "#223E73", "box": [0.0, 0.0, 0.1, 0.1],
                          "cubics": square(0.0, 0.0, 0.1, 0.1)}],
              "windows": [{"part": "cartouche", "shape": "quad", "fill": "#F0EDE5", "box": [0.2, 0.2, 0.8, 0.8],
                           "corners": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]}],
              "frames": [{"part": "cartouche — its frame", "shape": "quad", "ink": "#926323", "gold": True,
                          "width": 0.005, "box": [0.2, 0.2, 0.8, 0.8],
                          "corners": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]}]}
    sil = [MoveTo(x=0.0, y=0.0), LineTo(x=100.0, y=0.0), LineTo(x=100.0, y=100.0), LineTo(x=0.0, y=100.0), ClosePath()]
    group, _places, record = _map_front_group({"shapes": shapes}, {"zone_id": "z", "x": 0.0, "y": 0.0, "width": 100.0,
                                                                  "height": 100.0},
                                              SimpleNamespace(width_mm=100.0, height_mm=100.0, silhouette=sil),
                                              1.0, 0.0, 0.0)
    names = []

    def walk(n):
        for c in getattr(n, "children", None) or []:
            if not isinstance(c, Group):
                names.append(c.name)
            walk(c)
    walk(group)
    assert names.index("shape-map-1") < names.index("window-map-0") < names.index("frame-gold-map-0") \
        < names.index("shape-map-0") < names.index("shape-ink-0-0"), names
    assert "flower" in record["drawn"]


def _pitch_a5_doc(text_hex: str, mark_hex: str, *, window: bool = True, size_pt: float = 6.0):
    """A product: a dark brown body, a cream window over it (or none), a line of type and a recoloured mark on it."""
    from apps.ire.graph import AssetRef, Color, Document, Group, Rect, SolidFill, TextRun
    kids = [Rect(name="body", x=0.0, y=0.0, w=60.0, h=100.0, fill=SolidFill(color=Color.from_hex("#4B3022")))]
    if window:
        kids.append(Rect(name="window-map-0", x=5.0, y=20.0, w=50.0, h=60.0,
                         fill=SolidFill(color=Color.from_hex("#F0EDE5"))))
    kids += [TextRun(name="front-descriptor-0-0", text="Vitamin C Day Cream", x=30.0, y=50.0, size_pt=size_pt,
                     color=Color.from_hex(text_hex), align="center"),
             AssetRef(name="logo-front", x=15.0, y=30.0, w=30.0, h=6.0, recolor=Color.from_hex(mark_hex))]
    return Document(page_w=60.0, page_h=100.0, root=Group(name="Artwork", role="artwork", children=[
        Group(name="Container", role="product", children=kids),
        Group(name="Spec", role="info", children=[TextRun(name="swatch-label", text="BODY #F2CF70", x=1.0, y=99.0,
                                                          size_pt=4.0, color=Color.from_hex("#F2E0D0"))])]))


def test_pitch_a5_the_least_lightness_move_keeps_the_hue_and_a_gold_stays_gold():
    """"logos and small text are always readable": an ink that does not read is moved in lightness only, the least
    either way that reads, its hue kept — a gold mark stays gold where a gold of its hue reads."""
    import math

    from apps.ire import legibility as LG
    got = LG.least_move("#C9A24B", ["#F2CF70"], LG.MARK_RATIO)       # a gold mark on a butter-yellow body
    # [his review of 127-132, C (5)-(6)] it reads by its contrast or by its colour's distance (``READ_DE``)
    assert got["reads"] and LG.reads(got["hex"], ["#F2CF70"], LG.MARK_RATIO) and got["kept_gold"] \
        and LG.is_gold(got["hex"]), got
    L0, a0, b0 = LG.to_lab("#C9A24B")
    L1, a1, b1 = LG.to_lab(got["hex"])
    assert L1 < L0 and abs(math.degrees(math.atan2(b1, a1) - math.atan2(b0, a0))) < 3.0, (got, (L0, a0, b0))
    assert LG.least_move("#223E73", ["#F0EDE5"], LG.SMALL_TYPE_RATIO)["moved_l"] == 0.0   # reads: untouched
    light = LG.least_move("#5A3A28", ["#4B3022"], LG.MARK_RATIO)      # brown on brown: lighter, the nearer way
    assert light["reads"] and light["moved_l"] > 0, light


def test_pitch_a5_what_lies_under_a_line_is_the_topmost_fill_painted_before_it():
    """The ground a line or a mark is read against is what the drawing paints beneath it — the window over the body,
    never the body under the window — and a line on the window that reads is left as it is; the sheet's own words are
    never his print."""
    from apps.ire import legibility as LG
    doc = _pitch_a5_doc("#223E73", "#9A7237")
    wanted = LG.targets(doc)
    assert [t["node"].name for t in wanted] == ["front-descriptor-0-0", "logo-front"], wanted
    assert LG.ground_under(doc, wanted) == [["#F0EDE5"], ["#F0EDE5"]]
    assert LG.repair(doc) == [] and LG.remaining(doc) == []
    bare = _pitch_a5_doc("#223E73", "#9A7237", window=False)
    assert LG.ground_under(bare, LG.targets(bare)) == [["#4B3022"], ["#4B3022"]]


def test_pitch_a5_a_mark_and_small_type_that_do_not_read_are_moved_and_said_beside_approve():
    """127's and 132's marks were inked from the photo's gold, never set against their ground; small type was read
    only over traced solids. Each is moved the least it must — the mark to 3:1, a line under 9 pt to 4.5:1 — each move
    said ("Fixed: ..."), never a stop; what still reads under its ratio is shown by the drawing's own check."""
    from apps.ire import legibility as LG
    from apps.ire import self_check as SC
    doc = _pitch_a5_doc("#C8CCD3", "#E2D8C8")              # pale grey type, pale mark, on the cream window
    assert [f["what"].split(" reads ")[0] for f in LG.remaining(doc)] == ["'Vitamin C Day Cream' (6 pt)",
                                                                           "the mark logo-front"], LG.remaining(doc)
    fixed, shown = SC.repair_said(doc, [])
    contrast = [f for f in fixed if f["kind"] == "contrast"]
    assert len(contrast) == 2 and shown == [], (fixed, shown)
    text, mark = doc.root.children[0].children[2], doc.root.children[0].children[3]
    assert LG.reads(text.color.to_hex(), ["#F0EDE5"], LG.SMALL_TYPE_RATIO)
    assert LG.reads(mark.recolor.to_hex(), ["#F0EDE5"], LG.MARK_RATIO)
    assert LG.to_lab(text.color.to_hex())[0] < LG.to_lab("#C8CCD3")[0]     # dark on light: darker, as the concept sets it
    assert LG.remaining(doc) == []
    assert doc.root.children[1].children[0].color.to_hex() == "#F2E0D0"     # the sheet's own words: untouched
    assert any(line.startswith("Fixed: 'Vitamin C Day Cream' (6 pt) read 1.") for line in SC.record(fixed, [])["said"])
    # a line that no lightness of its hue reads against both grounds it straddles is shown, never stopped
    straddle = _pitch_a5_doc("#9A8A7A", "#9A7237")             # a mid tone, between the cream and the brown
    straddle.root.children[0].children[1].w = 25.0             # the window ends under the line's middle
    SC.repair_said(straddle, [])
    left = LG.remaining(straddle)
    assert len(left) == 1 and "under the 4.5:1 it needs" in left[0]["what"], left


def test_pitch_a5_a_gold_line_that_cannot_stay_gold_to_read_comes_off_its_foil_plate():
    """132's 5 pt Arabic, gold on cream (3.1:1): no gold of its hue reads at 4.5:1, so it is set darker in its own hue —
    and its foil plate is taken off, so the press never foils a line the drawing shows in brown; said beside Approve."""
    from apps.ire import legibility as LG
    from apps.ire.graph import Color, Finish
    doc = _pitch_a5_doc("#E0C080", "#9A7237")
    doc.root.children[0].children[1].fill.color = Color.from_hex("#D9C9A0")      # a pale gold line on a sand cartouche
    line = doc.root.children[0].children[2]
    line.finishes = [Finish(kind="foil", plate="FOIL_GOLD")]
    fixed = LG.repair(doc)
    assert len(fixed) == 1 and "no longer gold" in fixed[0]["what"] and "its foil plate taken off" in fixed[0]["what"]
    assert line.finishes == [] and not LG.is_gold(line.color.to_hex())
    assert LG.reads(line.color.to_hex(), ["#D9C9A0"], LG.SMALL_TYPE_RATIO)
    mark = doc.root.children[0].children[3]
    assert LG.is_gold(mark.recolor.to_hex()) and LG.reads(mark.recolor.to_hex(), ["#D9C9A0"], LG.MARK_RATIO)


def _tile_art(fill="#1A3E7E"):
    """A pattern traced in its colours (``flat_motif.colour_art``'s record): a field of small squares over its whole
    redraw, as 132's majolica was traced, its regions in its blue."""
    regions = [{"fill": fill, "rings": [[[x, y], [x + 0.04, y], [x + 0.04, y + 0.04], [x, y + 0.04], [x, y]]]}
               for x in [i / 10.0 for i in range(10)] for y in [j / 10.0 for j in range(10)]]
    return {"state": "TRACED", "size_px": [100, 100], "round": False, "sky": {"rows": []}, "regions": regions}


def _majolica_front(box=(0.0, 0.0, 1.0, 1.0)):
    from apps.pipeline.services.concept_design_map import PICTURE_ENGLISH
    pattern = {"part": "blue tile pattern", "ink": "#1A3E7E", "strokes": [],
               "flat": {"state": "TRACED", "art": _tile_art(), "box": list(box), "ink": "#1A3E7E", "ink_share": 0.16,
                        "ground": "#F6EEE1"}}
    name = [{"part": "name", "words": "Citrus", "ink": "#1A3E7E", "source": PICTURE_ENGLISH,
             "box": [0.3, 0.45, 0.7, 0.52]}]
    flower = [[[[0.45, 0.3], [0.55, 0.3, 0.55, 0.3, 0.55, 0.3], [0.55, 0.4, 0.55, 0.4, 0.55, 0.4],
                [0.45, 0.4, 0.45, 0.4, 0.45, 0.4], [0.45, 0.3, 0.45, 0.3, 0.45, 0.3]]]]
    emblem = {"part": "flower emblem", "ink": "#C6903C", "box": [0.45, 0.3, 0.55, 0.4], "cubics": flower}
    return {"shapes": {"state": "TRACED", "types": name, "shapes": [emblem], "lines": [pattern]},
            "ground": "#F6EEE1", "side_copy": []}


def test_his_review_132_c1_the_pattern_wraps_the_whole_pack():
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (1): "THE PATTERN WRAPS THE WHOLE PACK: when the concept
    shows a pattern running all round (132's majolica), it covers every panel of the carton (sides, back behind the
    sticker, flaps), never only the front. No grey panels."] A front whose pattern — traced in its colours from its flat
    redraw, as 132's — covers it edge to edge prints it all round: on both sides and the back (faint, under the sticker)
    as the front's own drawing moved, never copied point by point; on every flap and tuck, clipped to each; never the
    glue tab; no motif stamped on the flaps, no graphic on the sides; the lid keeps its mark; said on the record. A
    motif standing in one corner of the front is no pattern: the flaps keep their own design."""
    import os

    from django.conf import settings

    from apps.ire import brand_mark
    from apps.ire.compose import BACK_FIELD_OPACITY, wrapping_pattern
    path = os.path.join(settings.BASE_DIR, *brand_mark.MARK_DIR, brand_mark.MASTER_FILE)
    master = brand_mark.read_master(open(path, "rb").read(), path=path)
    coords = _inside_carton_13(67, 67, 84)
    front = _majolica_front()
    assert [line["part"] for line in wrapping_pattern(front)] == ["blue tile pattern"]
    doc = compose_components_graph(coords, product_name="Citrus Atelier", tint="#F6EEE1", map_front=front,
                                   inside=IP.plan("referenced", [], "", front), logo_master=master)
    found = []

    def walk(n):
        found.append(n)
        for c in getattr(n, "children", None) or []:
            walk(c)
    walk(doc.root)
    by = {str(getattr(n, "name", "")): n for n in found}
    for panel in ("back", "side_left", "side_right"):
        moved = [c for c in by["round-%s" % panel].children if isinstance(c, Group) and c.turn is not None]
        assert moved, panel                                                   # the front's own drawing, moved
        assert all(c.turn[:4] == (1.0, 0.0, 0.0, 1.0) for c in moved)
    faint = _paths(by["round-back"])                                          # under the sticker, faint
    assert faint and all(abs(p.fill.opacity - BACK_FIELD_OPACITY) < 1e-6 for p in faint)
    flaps = [name for name, _poly in coords.components if name not in ("main-body", "glue-tab")]
    assert sorted(n[len("flap-"):-len("-pattern")] for n in by if n.startswith("flap-") and n.endswith("-pattern")) \
        == sorted(flaps)
    assert not [n for n in by if n.endswith("-motif") or "glue" in n and n.endswith("-pattern")]
    assert "lid-mark" in by and not [n for n in by if n.startswith("side-graphic-")]
    assert doc.metadata["map_front"]["round_the_pack"]["parts"] == ["blue tile pattern"]
    # a motif in one corner is not a pattern: the flaps keep their own design
    corner = _majolica_front(box=(0.0, 0.0, 0.3, 0.3))
    assert wrapping_pattern(corner) == []
    small = compose_components_graph(coords, product_name="Citrus Atelier", tint="#F6EEE1", map_front=corner,
                                     inside=IP.plan("referenced", [], "", corner), logo_master=master)
    names = [str(getattr(n, "name", "")) for n, _p in small.walk()]
    assert not [n for n in names if n.endswith("-pattern") and n.startswith("flap-")]
    assert [n for n in names if n.startswith("flap-") and n.endswith("-motif")]


def _paths(node):
    from apps.ire.graph import Path
    if isinstance(node, Path):
        return [node]
    return [p for c in getattr(node, "children", None) or [] for p in _paths(c)]


def test_his_review_132_c2_a_broken_motif_is_never_stamped_on_the_flaps_sides_or_inside():
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (2): "NO BROKEN MOTIFS: a motif that can't be traced cleanly
    (132's side and flap flower, which looks like a fidget spinner) is redrawn flat and traced again; never printed
    broken."] The concept's motif the flaps, the sides and the inside repeat (``_concept_motif``) is never a shape left
    out as broken, nor ONE ink of a shape printed in several (132's gold alone, its petals cut out of it, was the
    spinner) — its inks together; one redrawn flat is its redraw's clean outlines; and the front draws a redrawn shape
    from its redraw, a broken one not at all."""
    from apps.ire.compose import _concept_motif, outline_cubics
    from apps.ire.compose_container import _map_front_group
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    front = _majolica_front()
    emblem = front["shapes"]["shapes"][0]
    layer = {"ink": "#223E73", "cubics": [[[[0.4, 0.35], [0.6, 0.35, 0.6, 0.35, 0.6, 0.35],
                                             [0.5, 0.45, 0.5, 0.45, 0.5, 0.45], [0.4, 0.35, 0.4, 0.35, 0.4, 0.35]]]]}
    layered = dict(front, shapes=dict(front["shapes"], shapes=[dict(emblem, layers=[layer])]))
    assert _concept_motif(layered) == emblem["cubics"] + layer["cubics"]          # its inks together
    left_out = dict(front, shapes=dict(front["shapes"], shapes=[dict(emblem, undrawn="broken")]))
    assert _concept_motif(left_out) is None                                       # never the broken one
    svg = ('<svg xmlns="http://www.w3.org/2000/svg"><g transform="translate(0,100) scale(1,-1)">'
           '<path d="M10 10 L90 10 L90 90 L10 90 z"/></g></svg>')
    mono = {"state": "TRACED", "outlines": {"svg": svg, "frame": [0.45, 0.3, 0.1 / 100, 0.1 / 100]}}
    redrawn = dict(emblem, flat={"state": "TRACED", "art": _tile_art("#C6903C"), "box": [0.45, 0.3, 0.55, 0.4]},
                   flat_mono=mono)
    motif = _concept_motif(dict(front, shapes=dict(front["shapes"], shapes=[redrawn])))
    assert motif == outline_cubics(mono["outlines"]) and len(motif) == 1
    xs = [v for ring in motif[0] for pt in ring for v in pt[0::2]]
    assert abs(min(xs) - 0.46) < 1e-6 and abs(max(xs) - 0.54) < 1e-6            # through its frame
    outline = [MoveTo(x=0.0, y=0.0), LineTo(x=67.0, y=0.0), LineTo(x=67.0, y=84.0), LineTo(x=0.0, y=84.0), ClosePath()]
    import types
    backbone = types.SimpleNamespace(width_mm=67.0, height_mm=84.0, silhouette=outline, cap_region=[])
    zone = {"zone_id": "z", "x": 0.0, "y": 0.0, "width": 67.0, "height": 84.0}

    def drawn(shape):
        only = {"shapes": {"state": "TRACED", "shapes": [shape], "types": [], "lines": []}}
        group, _places, record = _map_front_group(only, zone, backbone, 1.0, 0.0, 0.0)
        return [n.name for n in _walk_nodes(group)], record["drawn"]
    names, parts = drawn(redrawn)
    assert "flower emblem" in parts and any(n.startswith("shape-map-0-art-") for n in names), names
    names, parts = drawn(dict(emblem, undrawn="broken"))
    assert "flower emblem" not in parts and not [n for n in names if n.startswith("shape-map-")]


def _walk_nodes(node):
    out = [node]
    for c in getattr(node, "children", None) or []:
        out += _walk_nodes(c)
    return out


def test_his_review_132_c_the_lines_a_frame_holds_stay_inside_it_top_to_foot():
    """[His review of 127, 130, 131 and 132, 2026-10-15, C — the designer's eye on 132: "the Arabic line sits on the
    label's bottom edge over the tile pattern".] The type lines a cartouche's frame holds are kept inside it, top to foot,
    by FRAME_HOLD_PAD of its height: 132's read set its Arabic at 0.726-0.760, its frame's foot at 0.764 — its rows
    drawn closer as one block, their top kept where the picture sets them (the lily above never run into), never moved
    sideways; a block already inside, and a line no frame holds, are left as the picture sets them."""
    from apps.ire.compose import FRAME_HOLD_PAD, hold_in_frames
    frame = {"part": "gold cartouche frame", "shape": "quad", "box": [0.194, 0.214, 0.851, 0.764]}
    lines = [{"part": "CITRUS line", "words": "CITRUS", "box": [0.29, 0.466, 0.73, 0.534]},
             {"part": "50 ml", "words": "50 ml", "box": [0.45, 0.677, 0.58, 0.711]},
             {"part": "Arabic subtitle", "words": "كريم النهار", "box": [0.317, 0.726, 0.702, 0.760]},
             {"part": "foot line", "words": "MADE IN UAE", "box": [0.3, 0.90, 0.7, 0.93]}]
    front = {"shapes": {"frames": [frame], "windows": [], "types": lines}}
    held, said = hold_in_frames(front)
    types = {t["part"]: t["box"] for t in held["shapes"]["types"]}
    limit = 0.764 - FRAME_HOLD_PAD * (0.764 - 0.214)
    assert abs(types["Arabic subtitle"][3] - limit) < 1e-9                    # inside its frame, by its pad
    assert types["CITRUS line"][1] == 0.466                                    # the block's top where the picture sets it
    assert all(types[p][0] == b["box"][0] and types[p][2] == b["box"][2] for p, b in
               ((t["part"], t) for t in lines))                                # never moved sideways
    assert types["50 ml"][3] <= types["Arabic subtitle"][1] + 1e-9             # its rows in their order, closer
    assert types["foot line"] == [0.3, 0.90, 0.7, 0.93]                        # no frame holds it
    assert said[0]["lines"] == ["CITRUS line", "50 ml", "Arabic subtitle"]
    inside = {"shapes": {"frames": [frame], "windows": [], "types": lines[:2]}}
    assert hold_in_frames(inside) == (inside, [])


# --- [His review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL: ... 132's sticker only the name
# and net weight. Every back label carries the full set (description, ingredients, how to use, warnings, made in, net
# content, batch/exp, QR). When the brief gives no back copy, write sensible standard copy for that product type and mark
# it "not confirmed — please check" beside Approve. Never leave it nearly empty."] ---

def test_his_review_c7_a_carton_sticker_with_no_copy_is_given_the_full_set_and_his_words_win(settings):
    """A carton whose brief and record give no label copy: every piece written for its type (its standard copy where no
    model is called), named as written, and "Made in UAE" its placeholder origin; a piece he typed stands, and words the
    last run WROTE handed back as the size step's override are still written — never his."""
    from apps.pipeline.services import label_copy as lc
    settings.ANTHROPIC_API_KEY = ""
    info = {"product_name": "Citrus Atelier Vitamin C Day Cream", "net_weight": "50 ml", "description": "",
            "ingredients": "", "how_to_use": "", "warnings": "", "regulatory_text": "", "qr_url": "https://www.bbrose.com"}
    spec = {}
    about = "Citrus Atelier Vitamin C Day Cream, 50 ml jar (jar)"
    lc.fill_panel(spec, info, {}, about)
    assert info[lc.PANEL_WRITTEN_KEY] == list(lc.FIELDS)
    assert all(info[f] == lc.STANDARD["cream"][f] for f in lc.FIELDS)
    assert info["regulatory_text"] == "Made in UAE" and info[lc.PANEL_MADE_IN_KEY] is True
    assert spec[lc.SCHEMA]["by"] == lc.FROM_STANDARD
    from apps.dielines.exporters import label_layout as LL
    said = LL.label_sections(info, languages=("en",))
    assert [s["field"] for s in said["blocks"][0]["sections"]] == ["description", "ingredients", "how_to_use",
                                                                   "warnings"]
    assert said["tail"] == "Made in UAE" and "check" not in " ".join(s["text"] for s in said["blocks"][0]["sections"])
    # his own words for a piece: they stand, and only the rest is written
    mine = dict(info, how_to_use="Smooth over the face each morning.", regulatory_text="Made in Italy")
    again = dict(mine)
    lc.fill_panel(spec, again, info, about)
    assert again["how_to_use"] == "Smooth over the face each morning." and "how_to_use" not in again[lc.PANEL_WRITTEN_KEY]
    assert again["regulatory_text"] == "Made in Italy" and lc.PANEL_MADE_IN_KEY not in again
    # the last run's written words handed back unchanged (the stored label as the override): still written, not his
    back = {k: info[k] for k in ("description", "ingredients", "how_to_use", "warnings", "regulatory_text")}
    handed = dict(info, **back)
    handed.pop(lc.PANEL_WRITTEN_KEY)
    lc.fill_panel(spec, handed, info, about)
    assert handed[lc.PANEL_WRITTEN_KEY] == list(lc.FIELDS) and handed[lc.PANEL_MADE_IN_KEY] is True


def test_his_review_c7_written_pieces_are_set_shorter_never_his_label_stopped(tmp_path):
    """The narrow 22 mm carton whose twice-long label cannot stand in three languages at 3 pt: where the long pieces are
    the system's WRITTEN copy, the form they are set in is measured first (``label_form``) — shortened, or in English
    only — and the whole label stands on the back's sticker with no stop and no offer; his own pieces are never cut."""
    from apps.ire.compose import BACK_COPY_KEY, label_form
    from apps.pipeline.services import label_copy as lc
    coords = _carton_119(22, 22, 105)
    twice = dict(_INFO_119, **{k: (_INFO_119[k] + " ") * 2 for k in ("description", "ingredients", "how_to_use",
                                                                     "warnings")})
    written = dict(twice, **{lc.PANEL_WRITTEN_KEY: list(lc.FIELDS)})
    chosen = label_form(written, (22.0, 105.0), 4.0)
    assert chosen["form"] in lc.FORMS and chosen["form"] != lc.FULL, chosen
    record = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD",
                                      panel_info=dict(written, **{lc.PANEL_FORM_KEY: chosen["form"],
                                                                  lc.PANEL_DROPPED_KEY: chosen["dropped"]})
                                      ).metadata[BACK_COPY_KEY]
    assert record["codes"] == [] and record["offers"] == {}, record
    # the same words as HIS copy are never shortened: they stop by name, as before
    held = compose_components_graph(coords, product_name="Rose Glaze Lip Gloss", tint="#F1D5CD",
                                    panel_info=twice).metadata[BACK_COPY_KEY]
    assert held["codes"] != []


def test_his_review_c7_the_types_whole_standard_copy_on_a_22_mm_carton_never_stops_the_label(settings):
    """The 22 × 22 × 105 mm carton with no copy of his but its name and size: the type's whole standard copy written
    (``fill_panel``), its form measured (``label_form``) — shortened, English only, at the last left off — and the label
    stands on the back's sticker: no LABEL_DOES_NOT_FIT, no offer, no hold."""
    from types import SimpleNamespace

    from apps.ire.compose import BACK_COPY_KEY, label_form
    from apps.pipeline.services import label_copy as lc
    from apps.pipeline.targets.packaging import PackagingTarget
    settings.ANTHROPIC_API_KEY = ""
    info = {"product_name": "Rose Glaze Lip Gloss", "net_weight": "8 ml", "description": "", "ingredients": "",
            "how_to_use": "", "warnings": "", "regulatory_text": "", "qr_url": "https://www.bbrose.com"}
    lc.fill_panel({}, info, {}, "Rose Glaze Lip Gloss, a lip gloss in a wand vial")
    chosen = label_form(info, (22.0, 105.0), 4.0)
    info.update({lc.PANEL_FORM_KEY: chosen["form"], lc.PANEL_DROPPED_KEY: chosen["dropped"]})
    record = compose_components_graph(_carton_119(22, 22, 105), product_name="Rose Glaze Lip Gloss", tint="#F1D5CD",
                                      panel_info=info).metadata[BACK_COPY_KEY]
    assert record["codes"] == [] and record["offers"] == {}, record
    assert PackagingTarget().gate2_hold(None, SimpleNamespace(spec_sheet={BACK_COPY_KEY: record})) is None


def test_b10_a_motif_standing_on_the_front_is_drawn_over_its_field_and_its_soft_rooms():
    """[His goal after the pitch page, B (10): the designer's eye on 140, "concept a full-colour smiling honey dipper;
    drawing a faint ghosted outline"] A motif redrawn flat that stands in one place on the front is drawn over the
    pattern run all round it and over the soft rooms laid round the type — never under them; the field itself, and a
    solid as large as it, stay under the rooms."""
    from types import SimpleNamespace

    from apps.ire.compose_container import _map_front_group
    from apps.ire.graph import ClosePath, Group, LineTo, MoveTo
    front = _majolica_front()
    dipper = {"part": "honey dipper", "ink": "#E18B07", "box": [0.0, 0.2, 0.3, 0.45], "cubics": [],
              "flat": {"state": "TRACED", "art": _tile_art("#F2A103"), "box": [0.02, 0.2, 0.29, 0.42],
                       "ink": "#F2A103", "ground": "#F6EEE1"}}
    front["shapes"]["shapes"] = [dipper]
    front["soft_room"] = True
    sil = [MoveTo(x=0.0, y=0.0), LineTo(x=60.0, y=0.0), LineTo(x=60.0, y=120.0), LineTo(x=0.0, y=120.0), ClosePath()]
    group, _places, record = _map_front_group(front, {"zone_id": "z", "x": 0.0, "y": 0.0, "width": 60.0,
                                                      "height": 120.0},
                                              SimpleNamespace(width_mm=60.0, height_mm=120.0, silhouette=sil),
                                              1.0, 0.0, 0.0)
    names = []

    def walk(n):
        for c in getattr(n, "children", None) or []:
            if not isinstance(c, Group):
                names.append(c.name)
            walk(c)
    walk(group)
    field = [i for i, n in enumerate(names) if n.startswith("lineart-map-0")]
    rooms = [i for i, n in enumerate(names) if n.startswith("soft-room-")]
    dipper_at = [i for i, n in enumerate(names) if n.startswith("shape-map-0")]
    assert field and rooms and dipper_at, names
    assert max(field) < min(rooms) and max(rooms) < min(dipper_at), names
    assert "honey dipper" in record["drawn"]


def test_b10_a_motif_repeated_is_drawn_for_the_size_it_prints_at():
    """[His goal after the pitch page, B (10): 140's carton .ai was 116 MB] The motif the inside, the flaps and the sides
    repeat is drawn for the size it prints at: its specks (under the self-check's own speck there) left out, each ring
    run within MOTIF_TOLERANCE_MM of its curve in far fewer steps; a ring drawn in few cubics kept exactly; and the
    inside's pattern carries the fewer cubics."""
    import math

    from apps.ire.inside_print import MOTIF_TOLERANCE_MM, drawn_at, pattern_segments
    n = 600
    pts = [(0.5 + 0.4 * math.cos(2 * math.pi * k / n), 0.5 + 0.4 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    circle = [[pts[0][0], pts[0][1]]] + [[a[0], a[1], b[0], b[1], b[0], b[1]] for a, b in zip(pts, pts[1:] + pts[:1])]
    specks = [[[0.1 + 0.01 * j, 0.1], [0.1 + 0.01 * j + 0.002, 0.1, 0.1 + 0.01 * j + 0.002, 0.102,
                                       0.1 + 0.01 * j + 0.002, 0.102],
               [0.1 + 0.01 * j, 0.102, 0.1 + 0.01 * j, 0.1, 0.1 + 0.01 * j, 0.1]] for j in range(40)]
    square = [[0.0, 0.0], [0.3, 0.0, 0.7, 0.0, 1.0, 0.0], [1.0, 0.3, 1.0, 0.7, 1.0, 1.0],
              [0.7, 1.0, 0.3, 1.0, 0.0, 1.0], [0.0, 0.7, 0.0, 0.3, 0.0, 0.0]]
    motif = [circle] + specks + [square]
    size = 8.4
    got = drawn_at(motif, size)
    assert len(got) == 2                                         # the circle and the square; the 40 specks left out
    assert got[1] == square                                      # few cubics: kept as drawn
    assert len(got[0]) < len(circle) / 4
    for c in got[0][1:]:
        r = math.hypot(c[4] - 0.5, c[5] - 0.5)
        assert abs(r - 0.4) * size <= MOTIF_TOLERANCE_MM + 1e-6
    full = pattern_segments({"pattern": "motif", "density": "medium"}, (0.0, 0.0, 60.0, 60.0), [circle] + specks)
    one = pattern_segments({"pattern": "motif", "density": "medium"}, (0.0, 0.0, 60.0, 60.0), [square])
    assert len(full) < len(one) * 10                             # far under the 640 cubics a repeat carried


def test_b10_a_name_set_over_several_lines_is_carried_whole_on_each_side_inside_its_frame():
    """[His goal after the pitch page, B (10): 140's side printed "Oat &" alone, the first of its name's three lines,
    run out of its panel] A name the front sets over several traced lines is carried whole on each side — every line, as
    the front stacks them — fitted inside the side's safe frame."""
    from apps.ire.compose import _seg_bounds, _side_design_nodes
    from apps.ire.graph import ClosePath, Color, LineTo, MoveTo, Path, SolidFill
    coords = _inside_carton(42, 30, 100)
    gx, gy = (lambda x: x), (lambda y: y)

    def line(y0, w):
        return Path(name="product-name-traced", fill=SolidFill(color=Color.from_hex("#98292B")), segments=[
            MoveTo(x=10.0, y=y0), LineTo(x=10.0 + w, y=y0), LineTo(x=10.0 + w, y=y0 + 6.0), LineTo(x=10.0, y=y0 + 6.0),
            ClosePath()])
    kids = [line(30.0, 20.0), line(37.0, 22.0), line(44.0, 30.0)]
    safe = 3.0
    nodes, record = _side_design_nodes({"ground": "#F9BB21", "shapes": {}, "side_copy": []}, {}, kids, coords.panels,
                                       gx, gy, safe, faces={}, logo_master=None,
                                       product_name="Oat & Honey Comfort", logo_path=None, layout={},
                                       motif_aspect=1.5)
    sides = [n for n in nodes if str(n.name).startswith("side-name-")]
    assert len(sides) == 2
    for n in sides:
        assert len(n.segments) == sum(len(k.segments) for k in kids)          # all three lines, never one
        p = next(q for q in coords.panels if "side-name-%s" % q.name == n.name)
        bx0, by0, bx1, by1 = _seg_bounds(n.segments)
        assert p.x + safe - 1e-6 <= bx0 and bx1 <= p.x + p.width - safe + 1e-6, (p.name, bx0, bx1)
        assert p.y + safe - 1e-6 <= by0 and by1 <= p.y + p.height - safe + 1e-6, (p.name, by0, by1)
    assert {r["name"] for r in record["panels"] if r.get("name_traced")} == {"Oat & Honey Comfort"}
