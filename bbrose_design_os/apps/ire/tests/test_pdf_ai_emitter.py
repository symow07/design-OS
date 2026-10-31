"""pdf_ai emitter — Design Graph → editable PDF-compatible .ai (Phase 1).

Asserts the output is a real PDF whose content is NATIVE vector (path ops,
live text, a PDF shading for the gradient, vector barcode) — not an embedded
raster. This is the editability guarantee the whole redesign rests on.
"""
from __future__ import annotations

import pytest

from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import (
    Barcode,
    Color,
    Document,
    GradientFill,
    GradientStop,
    Group,
    Image,
    Rect,
    SolidFill,
    Stroke,
    TextRun,
)

_ROSE = Color.from_hex("#8B2E3C")
_CREAM = Color.from_hex("#EFE9E4")


fitz = pytest.importorskip("fitz")   # PyMuPDF (dev dep) — robust PDF inspection


def _page(path):
    return fitz.open(path)[0]


def _raw(path):
    return open(path, "rb").read()


def _doc(with_image=False):
    children = [
        Group(name="Background", role="background", children=[
            Rect(name="ground", x=0, y=0, w=105, h=150,
                 fill=GradientFill(kind="radial", cx=52, cy=75, r=90, stops=[
                     GradientStop(offset=0.0, color=_CREAM),
                     GradientStop(offset=1.0, color=_ROSE),
                 ])),
        ]),
        Group(name="Label", role="label", children=[
            Rect(name="sticker", x=8, y=8, w=89, h=60, radius_mm=4,
                 fill=SolidFill(color=_CREAM), stroke=Stroke(color=_ROSE, width_mm=0.5)),
            TextRun(name="title", text="ROSE NECTAR", x=52, y=40,
                    size_pt=20, color=_ROSE, align="center", font="bold"),
            Barcode(name="ean", symbology="ean13", value="5061030634110",
                    x=12, y=120, w=40, h=18),
        ]),
    ]
    if with_image:
        children.append(Group(name="Decoration", role="decoration", children=[
            Image(name="motif", src="/nonexistent/motif.png",
                  x=0, y=0, w=105, h=150),
        ]))
    return Document(page_w=105, page_h=150, title="t",
                    root=Group(name="Artwork", role="artwork", children=children))


def test_emits_a_valid_pdf(tmp_path):
    out = emit_pdf_ai(_doc(), str(tmp_path / "d.ai"))
    assert _raw(out).startswith(b"%PDF-")
    assert fitz.open(out).page_count == 1


def test_gradient_becomes_a_pdf_shading_not_a_raster(tmp_path):
    out = emit_pdf_ai(_doc(), str(tmp_path / "d.ai"))
    raw = _raw(out)
    # reportlab writes axial/radial gradients as PDF shading dictionaries;
    # Illustrator reads these as editable gradients.
    assert b"/Shading" in raw or b"/ShadingType" in raw
    # no raster image placed when no Image node is present
    assert _page(out).get_images() == []


def test_text_is_live_and_paths_are_vector(tmp_path):
    out = emit_pdf_ai(_doc(), str(tmp_path / "d.ai"))
    page = _page(out)
    # Live, selectable text (not outlines, not raster) — extractable as text.
    assert "ROSE NECTAR" in page.get_text()
    assert b"/FontFile" in _raw(out)          # font program embedded
    # native vector drawing ops present (rect / sticker / path)
    assert len(page.get_drawings()) > 0
    # nothing rasterized
    assert page.get_images() == []


def test_missing_image_src_is_skipped_not_fatal(tmp_path):
    # Image with a nonexistent src must not crash the emit (best-effort raster)
    out = emit_pdf_ai(_doc(with_image=True), str(tmp_path / "d.ai"))
    assert _raw(out).startswith(b"%PDF-")
    assert _page(out).get_images() == []   # nothing embedded (src was missing)


# ---- §BH32(e): the role-based selection layer at the emitter (W1/W2).

def _themed(doc):
    """§BH32(h)(7): a NON-exempt surface — the goal's exercise documents."""
    from apps.ire.font_roles import NON_EXEMPT_EXERCISE, SURFACE_KEY
    doc.metadata = dict(doc.metadata or {}, **{SURFACE_KEY: NON_EXEMPT_EXERCISE})
    return doc


def _bilingual_doc():
    from apps.ire.graph import Color, Document, Group, TextRun
    rose = Color(r=0.5, g=0.2, b=0.3)
    kids = [
        TextRun(name="name-ar", text="رحيق الورد", x=40, y=20, font="bold", size_pt=12, color=rose, align="center"),
        TextRun(name="name-en", text="ROSE NECTAR", x=40, y=30, font="bold", size_pt=10, color=rose, align="center"),
        TextRun(name="body", text="Facial serum 30 ml", x=40, y=40, font="regular", size_pt=6, color=rose),
        TextRun(name="mixed", text="حجم 30 ml", x=40, y=48, font="regular", size_pt=6, color=rose, align="right"),
    ]
    return _themed(Document(title="bilingual", page_w=80, page_h=60,
                            root=Group(name="root", children=kids)))


def _embedded_faces(path):
    return {f[3].split("+", 1)[-1] for f in fitz.open(path)[0].get_fonts(full=True)}


def test_the_layer_catalogue_is_exactly_the_35_plus_the_noto_trio():
    from apps.ire import font_roles as FR
    cat = FR.catalogue()
    # [the owner's answers after 117 was redrawn on his rules, 2026-10-02, answer 1: the font set he granted — 24 faces in
    # 17 families, placed under static/fonts/brand2026 with their provenance] the 35 + the Noto trio + the 24: 62, and
    # 59 brand faces
    # [his goal of 2026-10-06, item 6] and Naskh's granted Bold: 63
    # [his goal after the pitch page, 2026-10-15, A (1)] and the 19 serif, condensed and geometric faces: 82, 78 brand
    # [his review of 127, 130, 131 and 132, 2026-10-15, C (6)] and the condensed serifs, Instrument Serif (2) and Gloock: 85
    # [his goal after the pitch page, B (10), 2026-10-16] and the typewriter slab, Courier Prime (2): 87
    # [D-D7-1, the owner's Day 7 prompt, 2026-10-19] and the GRANTED pool of the materials library: 337 files, nine of
    # them the brand's own bytes already here, 328 entries — read from the pool's catalogue record, verified at use
    from apps.ire import font_pool
    pool = {k: e for k, e in cat.items() if e["origin"] == font_pool.ORIGIN}
    cat = {k: e for k, e in cat.items() if e["origin"] != font_pool.ORIGIN}
    assert len(pool) == 328 and all(e.get("licence") for e in pool.values())
    assert len(cat) == 87
    assert {"NotoSans-Regular", "NotoSans-Bold", "NotoNaskhArabic-Regular", "NotoNaskhArabic-Bold"} <= set(cat)
    assert sum(1 for e in cat.values() if e["origin"] != "STATIC_FONTS") == 83
    assert all(e["latin"] for k, e in cat.items() if not k.startswith("NotoNaskhArabic-"))
    # base letters: Cairo-Bold and Naskh; CAPABILITY on this emitter (every
    # presentation form the shaping path emits): Naskh alone — Cairo-Bold lacks
    # forms and dropped the non-joining letters of رحيق الورد on the goal page
    # [2026-10-02] the set's Arabic display faces carry the base letters, and every one lacks presentation forms the
    # shaping path emits (Lalezar 38, Cairo variable and Tajawal 36, Reem Kufi and Aref Ruqaa 119): granted, and never
    # handed an Arabic run on this emitter — measured, not assumed
    assert {k for k, e in cat.items() if e["arabic_letters"]} == {
        "Cairo-Bold", "NotoNaskhArabic-Regular", "NotoNaskhArabic-Bold", "ArefRuqaa-Bold", "ArefRuqaa-Regular",
        "Cairo[slnt,wght]", "Lalezar-Regular", "ReemKufi[wght]", "Tajawal-Black", "Tajawal-Bold", "Tajawal-ExtraBold",
        "Tajawal-ExtraLight", "Tajawal-Light", "Tajawal-Medium", "Tajawal-Regular"}
    # [his goal of 2026-10-06, item 6] Naskh's granted Bold beside the Regular: the two faces this emitter hands Arabic
    assert {k for k, e in cat.items() if e["arabic"]} == {"NotoNaskhArabic-Regular", "NotoNaskhArabic-Bold"}
    assert cat["Cairo-Bold"]["arabic_forms_missing"] > 0 and cat["NotoNaskhArabic-Regular"]["arabic_forms_missing"] == 0


def test_every_ruled_default_verifies_through_the_seam():
    from apps.ire import font_roles as FR
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    for role, chain in FR.CHAINS.items():
        r = FR.resolve_role(role)
        assert not r.get("refused"), (role, r)
        assert r["stem"] == chain[0]                      # the ruled default, first try
        assert [t["stem"] for t in r["tried"]] == [chain[0]]   # nothing skipped before it
        assert r["record"]["verification"] == VERIFIED_FOR_PRODUCTION
        assert r["record"]["is_fallback"] is False
    # §BH33(1): Naskh is the default for the three Arabic roles, each chain
    # Naskh → REFUSAL; Cairo-Bold left every Arabic chain (it cannot render the
    # forms this emitter emits) and keeps only its Latin display role
    # [his goal of 2026-10-06, item 6: "Approve Noto Naskh Arabic Bold ... for Arabic headings"] the heading's chain
    # leads with the granted Bold, the Regular behind it
    for role in ("arabic-display", "arabic-body"):
        assert FR.CHAINS[role] == ("NotoNaskhArabic-Regular",)
    assert FR.CHAINS["arabic-heading"] == ("NotoNaskhArabic-Bold", "NotoNaskhArabic-Regular")
    assert not any("Cairo-Bold" in chain for chain in FR.CHAINS.values())
    assert FR.catalogue()["Cairo-Bold"]["latin"] is True


def test_a_latin_document_renders_in_theme_faces_and_a_bilingual_one_in_naskh(tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    out = emit_pdf_ai(_themed(_doc()), str(tmp_path / "latin.ai"))
    faces = _embedded_faces(out)
    assert "Poppins-Light" in faces or "Poppins-Regular" in faces
    assert not faces & {"NotoSans-Regular", "NotoSans-Bold"}
    # MEASURED, not repaired, at §BH32(e): the EAN-13 widget draws its
    # human-readable digits in built-in Helvetica (reportlab's barcode, a
    # choice point outside the eight the §BH31 census listed) and the canvas
    # declares Times-Roman as its default resource without drawing a glyph.
    # Both are on the record for the owner; neither is a text run of the graph.
    assert faces - {"Helvetica", "Times-Roman"} <= {"Poppins-Light", "Poppins-Regular"}
    out = emit_pdf_ai(_bilingual_doc(), str(tmp_path / "bilingual.ai"))
    faces = _embedded_faces(out)
    assert "NotoNaskhArabic-Regular" in faces           # every Arabic role — Naskh renders
    assert "Cairo-Bold" not in faces                    # §BH33(1): out of every Arabic chain
    assert "Poppins-Light" in faces and "Poppins-Regular" in faces
    text = fitz.open(out)[0].get_text()
    assert "ROSE NECTAR" in text and "30 ml" in text


def test_a_mark_the_arabic_face_lacks_is_drawn_in_the_latin_face_never_dropped(tmp_path):
    """His second look at 117 (2026-10-02): "add the Arabic lines" — the picture's Arabic scent line sets its phrases
    apart by a "•", which Noto Naskh Arabic has no glyph for. Drawn inside the Arabic run it printed nothing, unseen;
    it is drawn in the run's Latin face, between the two phrases."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, TextRun
    rose = Color(r=0.5, g=0.2, b=0.3)
    doc = _themed(Document(title="arabic separator", page_w=80, page_h=40, root=Group(name="root", children=[
        TextRun(name="scent-ar", text="كريمة جوز الهند • بتلات الورد", x=40, y=20, font="regular", size_pt=8,
                color=rose, align="center", rtl=True)])))
    out = emit_pdf_ai(doc, str(tmp_path / "sep.ai"))
    page = fitz.open(out)[0]
    assert "•" in page.get_text()
    spans = [sp for b in page.get_text("dict")["blocks"] for ln in b.get("lines", []) for sp in ln["spans"]]
    assert any("•" in sp["text"] and "Naskh" not in sp["font"] for sp in spans), [(sp["text"], sp["font"]) for sp in spans]


def test_a_refused_role_draws_nothing_and_never_a_latin_face(tmp_path, monkeypatch):
    from apps.ire import font_roles as FR
    from apps.ire.emitters import pdf_ai as E
    monkeypatch.setitem(FR.CHAINS, "arabic-display", ())
    monkeypatch.setitem(FR.CHAINS, "arabic-body", ())
    FR.reset_cache()
    try:
        skipped = []
        real = E._Ctx.__init__
        def spy(self, *a, **k):
            real(self, *a, **k); skipped.append(self)
        monkeypatch.setattr(E._Ctx, "__init__", spy)
        out = E.emit_pdf_ai(_bilingual_doc(), str(tmp_path / "refused.ai"))
        faces = _embedded_faces(out)
        assert not faces & {"NotoNaskhArabic-Regular", "Cairo-Bold"}
        ctx = skipped[0]
        assert ctx.refusals["arabic-display"]["code"] == FR.REFUSAL_CODE
        assert {s["script"] for s in ctx.skipped} == {"arabic"}   # only the Arabic chunks were withheld
        assert "ROSE NECTAR" in fitz.open(out)[0].get_text()      # the Latin runs still drew
        assert "رحيق" not in fitz.open(out)[0].get_text()         # nothing Arabic rendered in a Latin face
    finally:
        FR.reset_cache()


def test_nothing_outside_the_catalogue_is_reachable_from_the_layer(tmp_path):
    from apps.ire import font_roles as FR
    stems = {stem for chain in FR.CHAINS.values() for stem in chain}
    assert stems <= set(FR.catalogue())
    # a confirmed concept face outside the catalogue is not used for the bold
    # role of a NON-exempt document (the 2A-7 golden path is exempt and keeps it)
    doc = _themed(_doc())
    doc.metadata = dict(doc.metadata, confirmed_font={"name": "BarlowCondensed-Bold",
                        "path": str(tmp_path / "nope.ttf")})
    faces = FR.legacy_role_map(doc.metadata)
    assert faces["bold"][0] == "Poppins-Light"


# ---- §BH32(h): the exemption list — each exempt surface bypassed, a non-exempt sibling not.

def _legacy_pair_used(out_path):
    faces = _embedded_faces(out_path)
    return bool(faces & {"NotoSans-Regular", "NotoSans-Bold"}) and not faces & {"Poppins-Light", "Poppins-Regular"}


def test_the_exemption_list_is_path_literal_and_names_entry_points_not_test_files():
    import os
    from apps.ire import font_roles as FR
    # 7 -> 6 (the owner's message of 2026-10-29, the four checks re-pinned): the dieline previews' entry left with its file
    assert len(FR.EXEMPT_SURFACES) == 6      # §BH48(a): the three container composers lifted
    for entry in FR.EXEMPT_SURFACES:
        path, _, func = entry.partition("::")
        assert path.startswith("apps/") and path.endswith(".py") and "tests" not in path and func
        assert os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(FR.__file__)))), path))


def test_an_untagged_or_anonymous_document_resolves_as_at_41604ac(tmp_path):
    """The reading (h)(2) forces: the ruled surfaces' measurers ask with no
    document, so anonymous == exempt. The tagged sibling takes the theme."""
    from apps.ire import font_roles as FR
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.text_metrics import resolve_metric_faces
    assert FR.is_exempt({}) and FR.is_exempt(None) and FR.is_exempt(_doc())
    assert resolve_metric_faces({})["bold"][0] == "NotoSans-Bold"
    assert set(resolve_metric_faces({})) == {"regular", "bold", "arabic"}
    assert _legacy_pair_used(emit_pdf_ai(_doc(), str(tmp_path / "untagged.ai")))
    sibling = _themed(_doc())
    assert not FR.is_exempt(sibling)
    assert resolve_metric_faces(sibling.metadata)["bold"][0] == "Poppins-Light"
    assert not _legacy_pair_used(emit_pdf_ai(sibling, str(tmp_path / "tagged.ai")))


def _untagged(doc):
    """§BH48(a): the untagged sibling — no surface tag, so it resolves as at 41604ac by (h)(2)."""
    from apps.ire.font_roles import SURFACE_KEY
    doc.metadata = {k: v for k, v in (doc.metadata or {}).items() if k != SURFACE_KEY}
    return doc


def test_the_container_composition_takes_the_theme_and_its_untagged_sibling_stays_on_41604ac(tmp_path):
    """§BH48(a) re-pin of §BH32(h)'s proof. The composition was exempt and drew the legacy pair;
    the owner lifted it, so the tagged document draws the theme and only an UNTAGGED document
    still resolves as at 41604ac."""
    import apps.pipeline.tests.test_container_font_authority as T
    from apps.ire import font_roles as FR
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    doc = T._doc()
    assert doc.metadata[FR.SURFACE_KEY] == "apps/ire/compose_container.py::compose_container_graph"
    assert not FR.is_exempt(doc)
    out = emit_pdf_ai(doc, str(tmp_path / "container.ai"))
    assert not _legacy_pair_used(out)
    assert {"Poppins-Light", "Poppins-Regular"} & _embedded_faces(out)
    sibling = _untagged(T._doc())
    assert FR.is_exempt(sibling)
    assert _legacy_pair_used(emit_pdf_ai(sibling, str(tmp_path / "container_sibling.ai")))


def test_the_dropper_sheet_takes_the_theme_and_its_untagged_sibling_stays_on_41604ac(tmp_path):
    """§BH48(a) re-pin of §BH32(h)'s proof, for the dropper sheet: lifted, it draws the theme —
    every run, the `serif-bold` product name included — and only its untagged copy resolves as
    at 41604ac."""
    from apps.ire import font_roles as FR
    from apps.ire.compose_dropper import compose_dropper_sheet
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE, _GEOMETRY
    def sheet():
        return compose_dropper_sheet(_GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
                                     logo_path=None, product_name="Rose Damascena", sku="X",
                                     back_sections=[{"heading": "P", "text": "x"}], revision_status="TEST")
    doc = sheet()
    assert doc.metadata[FR.SURFACE_KEY] == "apps/ire/compose_dropper.py::compose_dropper_sheet"
    assert not FR.is_exempt(doc)
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "dropper.ai"), usage_out=usage)
    assert not _legacy_pair_used(out)
    assert {"Poppins-Light", "Poppins-Regular"} & _embedded_faces(out)
    assert usage["refused"]["chunks"] == [] and usage["refused"]["roles"] == {}   # the name block drew
    sibling = _untagged(sheet())
    assert FR.is_exempt(sibling)
    assert _legacy_pair_used(emit_pdf_ai(sibling, str(tmp_path / "dropper_sibling.ai")))


def test_the_sticker_family_and_the_2a_handoff_stay_on_41604ac():
    from apps.dielines.exporters.counter_display_files import _resolve_arabic_font, _resolve_fonts
    from apps.ire import font_roles as FR
    assert _resolve_fonts() == ("NotoSans", "NotoSans-Bold")
    assert _resolve_arabic_font() == "NotoNaskhArabic"
    for entry in ("apps/dielines/exporters/counter_display_files.py::_resolve_fonts",
                  "apps/dielines/exporters/info_panel.py::draw_info_panel",
                  "apps/ire/handoff/graph_schema.py::serialize_handoff_graph",
                  "apps/ire/compose_vector_art.py::compose_vector_art_graph"):
        assert entry in FR.EXEMPT_SURFACES


# ---- §BH32(f): usage measured, not assumed — the counter reconciled against the artefact.

def test_the_usage_record_counts_every_face_that_drew_and_reconciles_with_the_artefact(tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai, USAGE_SCHEMA
    usage = {}
    out = emit_pdf_ai(_bilingual_doc(), str(tmp_path / "usage.ai"), usage_out=usage)
    assert usage["schema_version"] == USAGE_SCHEMA and usage["artefact"] == "usage.ai"
    by_face = {f["postscript"]: f for f in usage["faces"]}
    assert set(by_face) == {"Poppins-Light", "Poppins-Regular", "NotoNaskhArabic-Regular"}
    assert by_face["NotoNaskhArabic-Regular"]["scripts"] == ["arabic"]
    assert {"display", "body"} <= set(by_face["NotoNaskhArabic-Regular"]["roles"])
    assert all(f["runs"] >= 1 and f["chars"] >= 1 and f["sha256"] for f in usage["faces"])
    recon = usage["reconciliation"]
    assert recon["status"] == "RECONCILED" and recon["agree"] is True and recon["codes"] == []
    assert set(recon["embedded"]) == set(recon["counted"]) == set(by_face)
    from apps.ire.emitters.pdf_ai import _embedded_faces as _drew
    assert set(recon["embedded"]) == _drew(out)                # the span reader, independently
    assert "Helvetica" in recon["declared_without_glyphs"]       # declared by the canvas, no glyph drawn
    assert usage["refused"] == {"roles": {}, "chunks": []}


def test_a_refused_chunk_is_in_the_record_and_not_in_the_count(tmp_path, monkeypatch):
    from apps.ire import font_roles as FR
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    for role in ("arabic-body", "arabic-display", "arabic-heading"):
        monkeypatch.setitem(FR.CHAINS, role, ())
    FR.reset_cache()
    try:
        usage = {}
        emit_pdf_ai(_bilingual_doc(), str(tmp_path / "refused.ai"), usage_out=usage)
        assert usage["refused"]["roles"]["arabic-body"]["code"] == FR.REFUSAL_CODE
        assert usage["refused"]["chunks"] and all(c["script"] == "arabic" for c in usage["refused"]["chunks"])
        assert "NotoNaskhArabic-Regular" not in {f["postscript"] for f in usage["faces"]}
        assert usage["reconciliation"]["agree"] is True     # what drew is what the file carries
    finally:
        FR.reset_cache()


def test_a_disagreement_between_counter_and_artefact_is_a_named_defect(tmp_path, monkeypatch):
    from apps.ire.emitters import pdf_ai as E
    real = E._embedded_faces
    monkeypatch.setattr(E, "_embedded_faces", lambda path: real(path) | {"GhostFace-Regular"})
    usage = {}
    E.emit_pdf_ai(_doc(), str(tmp_path / "ghost.ai"), usage_out=usage)
    recon = usage["reconciliation"]
    assert recon["agree"] is False
    assert recon["unaccounted_in_artefact"] == ["GhostFace-Regular"]
    assert recon["codes"] == [E.USAGE_DISAGREEMENT_CODE]
    monkeypatch.setattr(E, "_embedded_faces", lambda path: None)
    usage = {}
    E.emit_pdf_ai(_doc(), str(tmp_path / "blind.ai"), usage_out=usage)
    assert usage["reconciliation"]["status"] == "UNRECONCILED"
    assert usage["reconciliation"]["codes"] == [E.USAGE_UNRECONCILED_CODE]


# ---- §BH33(2): a variable face never renders its default instance.

_VARIABLE = {"Montserrat[wght]", "Montserrat-Italic[wght]", "Quicksand[wght]",
             "PlayfairDisplay[wght]", "PlayfairDisplay-Italic[wght]"}
#: [2026-10-02: the font set he granted] its four variable faces, measured from their fvar tables — read beside the five,
#: whose §BH33 and §BH68 checks stay theirs
_VARIABLE_2026_10_02 = {"DancingScript[wght]", "Fredoka[wdth,wght]", "ReemKufi[wght]", "Cairo[slnt,wght]"}
#: [his goal after the pitch page, 2026-10-15, A (1)] the eight variable faces of the serif, condensed and geometric set,
#: each a weight axis alone — drawn only at the weight a line asks (``instance_at``), never their default instance
_VARIABLE_2026_10_15 = {"CormorantGaramond[wght]", "CormorantGaramond-Italic[wght]", "LibreBaskerville[wght]",
                        "LibreBaskerville-Italic[wght]", "Cinzel[wght]", "Oswald[wght]", "Jost[wght]",
                        "Jost-Italic[wght]"}


def test_the_catalogue_measures_exactly_five_variable_faces():
    from apps.ire import font_roles as FR
    from apps.ire import font_pool
    cat = FR.catalogue()
    # [D-D7-1, 2026-10-19] the GRANTED pool's variable faces are measured by the same reader and listed beside the brand's
    assert sum(1 for e in cat.values() if e["origin"] == font_pool.ORIGIN and e["variable"]) == 11
    cat = {k: e for k, e in cat.items() if e["origin"] != font_pool.ORIGIN}
    assert {k for k, e in cat.items() if e["variable"]} == _VARIABLE | _VARIABLE_2026_10_02 | _VARIABLE_2026_10_15   # measured from fvar
    assert all(set(e["axes"]) == {"wght"} for k, e in cat.items() if k in _VARIABLE)
    assert cat["Montserrat[wght]"]["axes"]["wght"] == (100.0, 100.0, 900.0)
    assert cat["Montserrat[wght]"]["postscript"] == "Montserrat-Thin"     # the default instance — never rendered
    assert cat["Montserrat-Regular"]["variable"] is False                  # the static face is its own granted file
    # §BH68(c), OWNER RULED 2026-09-24: "THE DISPLAY ROLE TAKES THE HEADING PIN — weight 700 for a variable face"
    assert FR.INSTANCE_WEIGHT_BY_ROLE == {"heading": 700.0, "body": 400.0, "display": 700.0}


def test_a_variable_face_resolves_at_its_pinned_instance_never_the_default():
    from apps.ire import font_roles as FR
    granted = FR.catalogue()["Montserrat[wght]"]
    r = FR.resolve_role("heading")
    assert r["stem"] == "Montserrat[wght]" and r["label"] == "Montserrat-Bold"
    assert r["instance"]["axes"] == {"wght": 700.0} and r["instance"]["style"] == "Bold"
    assert r["sha256"] == granted["sha256"]                          # the granted bytes are what verified
    assert r["instance"]["derived_from_sha256"] == granted["sha256"]
    assert r["granted_path"] == granted["path"] and r["path"] != granted["path"]
    assert r["instance"]["source_default_instance"] == "Montserrat-Thin"
    # deterministic derivation: the same bytes, the same file, every time
    again = FR.instance_for("Montserrat[wght]", "heading")
    assert again["sha256"] == r["instance"]["sha256"] and again["path"] == r["path"]
    # body = wght 400 (Regular) by the same table; bold/regular alias to display/body
    body = FR.instance_for("Montserrat[wght]", "body")
    assert body["postscript"] == "Montserrat-Regular" and body["axes"] == {"wght": 400.0}
    assert FR.instance_for("Montserrat[wght]", "regular")["postscript"] == "Montserrat-Regular"
    # no pinned weight for display / caption / script-accent: never the default instance
    # [§BH68(c), 2026-09-24: display now takes the heading pin — 700 — for a variable face; caption and script-accent
    # still pin none, and still never receive the default instance]
    assert FR.instance_for("Montserrat[wght]", "display")["axes"] == {"wght": 700.0}
    assert FR.instance_for("Montserrat[wght]", "caption") is None
    assert FR.instance_for("Poppins-Regular", "heading") is None          # a static face has no instance
    # the other variable faces get the same rule, named by their own STAT
    assert FR.instance_for("Quicksand[wght]", "heading")["postscript"] == "Quicksand-Bold"


def test_the_artefact_embeds_the_instance_by_name_and_the_counter_reconciles_on_it(tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    doc = _themed(_doc())
    doc.root.children.append(TextRun(name="h", text="HYDRATING FACIAL SERUM", x=10, y=80,
                                     font="heading", size_pt=9, color=_ROSE))
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "heading.ai"), usage_out=usage)
    faces = _embedded_faces(out)
    assert "Montserrat-Bold" in faces and "Montserrat-Thin" not in faces
    row = next(f for f in usage["faces"] if f["postscript"] == "Montserrat-Bold")
    assert row["roles"] == ["heading"] and row["outside_layer"] is False
    assert row["instance_of"]["stem"] == "Montserrat[wght]" and row["instance_of"]["axes"] == {"wght": 700.0}
    assert row["sha256"] and row["sha256"] != row["instance_of"]["sha256"]   # the derived bytes, not the granted
    assert usage["reconciliation"]["agree"] is True and usage["reconciliation"]["codes"] == []


def test_montserrat_at_the_body_role_embeds_montserrat_regular(tmp_path, monkeypatch):
    """§BH33(2): body = wght 400 (Regular) — proved with the body chain led by
    Montserrat[wght]. The ruled body chain itself (Poppins-Regular first) is
    not re-ruled by (2), as the T33 executor's reading records."""
    from apps.ire import font_roles as FR
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    monkeypatch.setitem(FR.CHAINS, "body", ("Montserrat[wght]", "Poppins-Regular", "NotoSans-Regular"))
    FR.reset_cache()
    try:
        doc = _themed(_doc())
        doc.root.children.append(TextRun(name="b", text="Apply two drops morning and night.", x=10, y=80,
                                         font="body", size_pt=5, color=_ROSE))
        usage = {}
        out = emit_pdf_ai(doc, str(tmp_path / "body.ai"), usage_out=usage)
        faces = _embedded_faces(out)
        assert "Montserrat-Regular" in faces and "Montserrat-Thin" not in faces
        assert usage["reconciliation"]["agree"] is True
        row = next(f for f in usage["faces"] if f["postscript"] == "Montserrat-Regular")
        assert row["instance_of"]["axes"] == {"wght": 400.0}
    finally:
        FR.reset_cache()


def test_bh68c_the_usage_reconciliation_reads_a_long_font_name_whole(tmp_path):
    """§BH68(c): MuPDF reports a span's font name cut at 24 characters after the subset tag; the page's own font
    resources carry it whole. A face whose PostScript name is longer — built here from a granted file, renamed — is
    read whole, a name of 24 or fewer is read as it is, and a cut name two declared fonts could begin stays cut."""
    from fontTools.ttLib import TTFont as FontFile
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    from apps.ire.emitters.pdf_ai import _MUPDF_NAME_CHARS, _declared_faces, _embedded_faces, _whole_names
    from apps.ire.font_roles import catalogue
    long_name = "BbroseSixtyEightTestFaceLongName"                        # 32 characters, past the 24 MuPDF keeps
    face = FontFile(catalogue()["Poppins-Light"]["path"])
    for platform, encoding, language in ((3, 1, 0x409), (1, 0, 0)):
        face["name"].setName(long_name, 6, platform, encoding, language)
    renamed = str(tmp_path / "long.ttf")
    face.save(renamed)
    pdfmetrics.registerFont(TTFont("bh68c-long", renamed))
    path = str(tmp_path / "long.pdf")
    c = canvas.Canvas(path)
    c.setFont("bh68c-long", 12)
    c.drawString(72, 700, "Focus")
    c.setFont("Helvetica", 12)
    c.drawString(72, 650, "Powder")
    c.save()
    assert long_name in _declared_faces(path)
    assert _embedded_faces(path) == {long_name, "Helvetica"}
    cut = long_name[:_MUPDF_NAME_CHARS]
    assert _whole_names({cut}, {long_name + "A", long_name + "B"}) == {cut}      # two could be it: none is chosen
    assert _whole_names({"Poppins-Light"}, {"Poppins-Light"}) == {"Poppins-Light"}


def test_a_variable_face_at_an_unpinned_role_is_skipped_and_the_chain_continues(monkeypatch):
    from apps.ire import font_roles as FR
    monkeypatch.setitem(FR.CHAINS, "caption", ("Quicksand[wght]", "Poppins-Light", "Poppins-Regular", "NotoSans-Regular"))
    FR.reset_cache()
    try:
        r = FR.resolve_role("caption")
        assert r["stem"] == "Poppins-Light"                               # never Quicksand-Light, the default
        assert r["tried"][0] == {"stem": "Quicksand[wght]", "verification": FR.UNPINNED_VERDICT}
    finally:
        FR.reset_cache()


# ---- §BH33(3): harakat and tanween KEPT on non-exempt surfaces; exempt surfaces untouched.

_TANWEEN_TEXT = "يوضع قطرتان صباحاً ومساءً"      # two fathatan (U+064B) in the logical text


def _arabic_run_doc(text, font="regular"):
    return Document(title="h", page_w=80, page_h=40,
                    root=Group(name="root", children=[
                        TextRun(name="ar", text=text, x=75, y=20, font=font, size_pt=8,
                                color=_ROSE, align="right")]))


def _spans(path):
    return [(sp["font"].split("+", 1)[-1], sp["text"])
            for blk in fitz.open(path)[0].get_text("dict")["blocks"]
            for ln in blk.get("lines", []) for sp in ln.get("spans", [])]


def test_harakat_are_kept_on_a_non_exempt_surface_and_untouched_on_an_exempt_one(tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    out = emit_pdf_ai(_themed(_arabic_run_doc(_TANWEEN_TEXT)), str(tmp_path / "kept.ai"))
    text = fitz.open(out)[0].get_text()
    assert text.count("\u064b") == 2                       # both tanween drawn, as written
    assert all(font == "NotoNaskhArabic-Regular" for font, t in _spans(out) if "\u064b" in t)
    # an untagged document is EXEMPT and draws exactly as at 41604ac: harakat deleted
    out = emit_pdf_ai(_arabic_run_doc(_TANWEEN_TEXT), str(tmp_path / "exempt.ai"))
    assert "\u064b" not in fitz.open(out)[0].get_text()


def test_a_mark_at_a_script_boundary_stays_with_its_arabic_base(tmp_path):
    """In visual order a mark precedes its base; after a Latin run it would
    otherwise be split into the Latin chunk and drawn with a Latin face."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    usage = {}
    out = emit_pdf_ai(_themed(_arabic_run_doc("30 ml صباحاً")), str(tmp_path / "mixed.ai"), usage_out=usage)
    spans = _spans(out)
    assert any("\u064b" in t for _, t in spans)
    assert all(font == "NotoNaskhArabic-Regular" for font, t in spans if "\u064b" in t)
    assert all("\u064b" not in t for font, t in spans if font.startswith("Poppins"))
    assert usage["reconciliation"]["agree"] is True
    by_face = {f["postscript"]: f for f in usage["faces"]}
    assert by_face["NotoNaskhArabic-Regular"]["scripts"] == ["arabic"]


def test_arabic_capability_counts_the_marks_the_path_now_keeps():
    from apps.ire import font_roles as FR
    cat = FR.catalogue()
    assert cat["NotoNaskhArabic-Regular"]["arabic_marks_missing"] == 0
    # [his goal of 2026-10-06, item 6] the granted Bold carries every form and mark the path draws, as the Regular does
    assert cat["NotoNaskhArabic-Bold"]["arabic_marks_missing"] == 0
    # [D-D7-1, 2026-10-19] the GRANTED pool carries four faces the same reader finds emitter-capable (every form and mark the
    # path draws): measured, listed beside the brand's two; the Arabic role chains name the brand's faces as before
    from apps.ire import font_pool
    assert sum(1 for e in cat.values() if e["origin"] == font_pool.ORIGIN and e["arabic"]) == 4
    assert {k for k, e in cat.items() if e["arabic"] and e["origin"] != font_pool.ORIGIN} == {"NotoNaskhArabic-Regular", "NotoNaskhArabic-Bold"}
    from apps.dielines.exporters.text_intl import shape_ar
    assert "\u064b" in shape_ar("صباحاً", keep_harakat=True)
    assert "\u064b" not in shape_ar("صباحاً")                 # the default: exempt callers unchanged


# ---- §BH39(d): the placement record on the Image seam, the credit node, the refusals; the retrieval contract as an interface.

def _mat_doc(tmp_path, *, src, record=None, credit=None, name="asset-1"):
    from apps.ire.graph import Document, Group, Image, TextRun
    from apps.ire import materials_placement as MP
    from apps.ire.font_roles import NON_EXEMPT_EXERCISE, SURFACE_KEY
    kids = [Image(name=name, src=str(src), x=5, y=5, w=40, h=30)]
    if credit is not None:
        kids.append(credit)
    doc = Document(title="materials placement exercise", page_w=80, page_h=60, root=Group(name="root", children=kids))
    md = {SURFACE_KEY: NON_EXEMPT_EXERCISE}
    if record is not None:
        md[MP.SCHEMA] = {"schema_version": MP.SCHEMA, "placements": [record]}
    doc.metadata = md
    return doc


def _png(path):
    from PIL import Image as PILImage
    PILImage.new("RGB", (8, 8), (200, 150, 120)).save(path)
    return path


def _production_row(rel, sha="a" * 64, condition=""):
    return {"relative_path": rel, "sha256": sha, "tier": "PRODUCTION", "tier_source": "OWNER_GRANT",
            "evidence": "materials/x/License free.txt sha256:" + "b" * 64, "terms_class": "ATTRIBUTION-REQUIRED" if condition else "PERMISSIVE",
            "condition": condition}


def test_an_ungoverned_media_image_places_as_today(tmp_path):
    from apps.ire import materials_placement as MP
    src = _png(tmp_path / "motif.png")
    doc = _mat_doc(tmp_path, src=src)
    usage = MP.resolve_placements(doc)
    assert usage["rows"][0]["resolution"] == MP.PLACED and usage["rows"][0]["governed"] is False
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "m.ai"), usage_out=usage)
    assert len(_page(out).get_images()) == 1
    assert MP.reconcile_images(out, usage[MP.USAGE_SCHEMA])["agree"] is True and usage[MP.USAGE_SCHEMA]["placed"] == 1


def test_a_materials_source_without_a_placement_record_is_refused_ahead_of_every_byte(tmp_path):
    from apps.ire import materials_placement as MP
    src = MP.REPO_ROOT / "materials" / "17-10-2024" / "pile-online-shopping-package-mockups" / "65757.jpg"
    if not src.exists():
        pytest.skip("materials/ not on this machine")
    doc = _mat_doc(tmp_path, src=src)
    with pytest.raises(MP.PlacementRefused) as e:
        emit_pdf_ai(doc, str(tmp_path / "r.ai"))
    assert e.value.code == MP.REFUSED_NO_PLACEMENT_RECORD
    assert not (tmp_path / "r.ai").exists()


def test_a_reference_asset_can_never_be_placed(tmp_path):
    from apps.ire import materials_placement as MP
    from apps.ire.graph import Image
    src = MP.REPO_ROOT / "materials" / "ADOBE STOCK"
    src = next((p for p in src.rglob("*.jpg")), None) if src.exists() else None
    if src is None:
        pytest.skip("materials/ not on this machine")
    node = Image(name="asset-1", src=str(src), x=5, y=5, w=40, h=30)
    row = {"relative_path": "materials/ADOBE STOCK/x.jpg", "sha256": "c" * 64, "tier": "REFERENCE", "tier_source": "MACHINE", "evidence": "", "condition": ""}
    doc = _mat_doc(tmp_path, src=src, record=MP.placement_record(node, row))
    with pytest.raises(MP.PlacementRefused) as e:
        emit_pdf_ai(doc, str(tmp_path / "ref.ai"))
    assert e.value.code == MP.REFUSED_REFERENCE_ASSET


def test_a_conditioned_asset_without_its_visible_credit_resolves_reference_for_that_output(tmp_path):
    from apps.ire import materials_placement as MP
    from apps.ire.graph import Image
    src = MP.REPO_ROOT / "materials" / "17-10-2024" / "pile-online-shopping-package-mockups" / "65757.jpg"
    if not src.exists():
        pytest.skip("materials/ not on this machine")
    cond = '<a href="http://www.freepik.com">Designed by rawpixel.com / Freepik</a> | "Designed by rawpixel.com / Freepik"'
    node = Image(name="asset-1", src=str(src), x=5, y=5, w=40, h=30)
    rec = MP.placement_record(node, _production_row("materials/17-10-2024/pile-online-shopping-package-mockups/65757.jpg", condition=cond))
    doc = _mat_doc(tmp_path, src=src, record=rec)
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "nocredit.ai"), usage_out=usage)
    pu = usage[MP.USAGE_SCHEMA]
    assert pu["rows"][0]["resolution"] == MP.RESOLVED_REFERENCE_NO_VISIBLE_CREDIT
    assert _page(out).get_images() == []                                       # the asset did not reach the output
    assert MP.reconcile_images(out, pu)["agree"] is True and pu["placed"] == 0


def test_a_conditioned_asset_with_its_credit_node_is_placed_and_the_credit_is_in_the_record_and_visible(tmp_path):
    from apps.ire import materials_placement as MP
    from apps.ire.graph import Image
    src = MP.REPO_ROOT / "materials" / "17-10-2024" / "pile-online-shopping-package-mockups" / "65757.jpg"
    if not src.exists():
        pytest.skip("materials/ not on this machine")
    cond = '<a href="http://www.freepik.com">Designed by rawpixel.com / Freepik</a> | "Designed by rawpixel.com / Freepik"'
    node = Image(name="asset-1", src=str(src), x=5, y=5, w=40, h=30)
    rec = MP.placement_record(node, _production_row("materials/17-10-2024/pile-online-shopping-package-mockups/65757.jpg", condition=cond), credit_node_name="credit-asset-1")
    credit = MP.credit_node(rec, x=5, y=52, size_pt=6)
    assert credit.text == "Designed by rawpixel.com / Freepik" and credit.name == "credit-asset-1"
    doc = _mat_doc(tmp_path, src=src, record=rec, credit=credit)
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "credit.ai"), usage_out=usage)
    pu = usage[MP.USAGE_SCHEMA]
    assert pu["rows"][0]["resolution"] == MP.PLACED and pu["rows"][0]["condition"] == cond
    assert len(_page(out).get_images()) == 1                                   # placed
    assert "Designed by rawpixel.com / Freepik" in _page(out).get_text()       # visible on the artefact
    assert MP.reconcile_images(out, pu)["agree"] is True and pu["placed"] == 1


def test_the_retrieval_contract_carries_no_bytes_and_no_locator_and_is_not_a_server():
    from apps.ire import materials_retrieval as MR
    row = {"sha256": "d" * 64, "tier": "REFERENCE", "category": "PATTERN", "pack": "ALL..MOCKUP/27-4-2024/x", "caption": "a floral pattern",
           "palette": ["#F2E8E2", "#CBA87D"], "layout_metadata": {"canvas_px": [4000, 3000], "mode": "RGB"}, "evidence": {"class": "NO EVIDENCE"},
           "condition": "", "prohibited": MR.PROHIBITED_FROM_COPYING}
    assert MR.validate_row(row) is row
    with pytest.raises(MR.RetrievalContractError):
        MR.validate_row(dict(row, path="materials/x.jpg"))
    with pytest.raises(MR.RetrievalContractError):
        MR.validate_row(dict(row, tier="PLACEABLE"))
    with pytest.raises(MR.RetrievalContractError):
        MR.validate_query({"wanted": ["bytes"], "k": 3})
    with pytest.raises(NotImplementedError):
        MR.MaterialsRetrieval().query({"task_tokens": ["blush"], "wanted": ["palette"], "k": 3})


# ---- §BH39(e): the colour layer — brand_gov FIRST through colour_roles; exempt surfaces byte-identical; the seam consulted.

def test_the_layer_resolves_every_role_with_a_brand_colour_to_brand_gov_and_the_rest_to_the_surface_literal():
    from apps.ire import colour_roles as CR
    from apps.ire.graph import Color
    md = {CR.SURFACE_KEY: CR.NON_EXEMPT_EXERCISE}
    fallback = Color.from_hex("#123456")
    gold = CR.resolve_role(md, "ground_gold", fallback)
    assert gold["hex"] == "#CBA87D" and gold["source"] == CR.SOURCE_BRAND_GOV and "Warm Gold" in gold["evidence"]
    cream = CR.resolve_role(md, "ground_cream", fallback)
    assert cream["hex"] == "#FAF3EC" and cream["source"] == CR.SOURCE_BRAND_GOV
    dark = CR.resolve_role(md, "accent_dark", fallback)
    assert dark["hex"] == "#123456" and dark["source"] == CR.SOURCE_SURFACE_FALLBACK   # no brand colour, no candidate: the literal
    with pytest.raises(ValueError):
        CR.resolve_role(md, "not-a-role", fallback)


def test_an_exempt_or_untagged_document_receives_its_own_literal_untouched():
    """§BH48(a) re-pin: the container composition was the exempt example here and is lifted,
    so the exempt example is a surface that STAYED (the 2A-7 carton golden path). On the lifted
    container surface the colour layer is ACTIVE — a ROLE resolves to brand_gov's swatch — while a
    FILL with no role map declared is still the surface's own literal (the palette step's)."""
    from apps.ire import colour_roles as CR
    from apps.ire.graph import Color
    fallback = Color.from_hex("#E8C9B3", cmyk=(0.06, 0.22, 0.30, 0.02))
    for md in ({}, {CR.SURFACE_KEY: "apps/ire/compose_vector_art.py::compose_vector_art_graph"}):
        row = CR.resolve_role(md, "ground_gold", fallback)
        assert row["color"] is fallback and row["source"] == CR.SOURCE_SURFACE_FALLBACK
        assert CR.resolve_fill(md, fallback)["color"] is fallback
    lifted = {CR.SURFACE_KEY: "apps/ire/compose_container.py::compose_container_graph"}
    row = CR.resolve_role(lifted, "ground_gold", fallback)
    assert row["source"] == CR.SOURCE_BRAND_GOV and row["color"] is not fallback
    fill = CR.resolve_fill(lifted, fallback)
    assert fill["color"] is fallback and fill["source"] == CR.SOURCE_SURFACE_FALLBACK


def test_a_library_colour_is_admitted_only_from_a_production_row_and_only_where_the_role_has_no_brand_colour():
    from apps.ire import colour_roles as CR
    from apps.ire.graph import Color
    md = {CR.SURFACE_KEY: CR.NON_EXEMPT_EXERCISE}
    prod = {"tier": "PRODUCTION", "sha256": "a" * 64, "relative_path": "materials/x/a.ai", "evidence": "materials/x/License free.txt sha256:" + "b" * 64}
    ref = dict(prod, tier="REFERENCE", evidence="")
    # accent_dark has no brand colour: a PRODUCTION candidate is admitted, a REFERENCE one is inspiration only
    row = CR.resolve_role(md, "accent_dark", Color.from_hex("#000000"), candidates=[("#231916", ref), ("#2A2426", prod)])
    verdicts = {v["hex"]: v["verdict"] for v in row["verdicts"]}
    assert verdicts == {"#231916": CR.CANDIDATE_INSPIRATION_ONLY, "#2A2426": CR.CANDIDATE_ADMITTED}
    assert row["hex"] == "#2A2426" and row["source"] == CR.SOURCE_PRODUCTION_PALETTE and row["tier"] == "PRODUCTION"
    # ground_gold has a brand colour: every library candidate is refused, brand_gov resolves
    row = CR.resolve_role(md, "ground_gold", Color.from_hex("#000000"), candidates=[("#C9A24B", prod), ("#CBA87D", ref)])
    assert {v["verdict"] for v in row["verdicts"]} == {CR.CANDIDATE_REFUSED_ROLE_HAS_BRAND_COLOUR, CR.CANDIDATE_INSPIRATION_ONLY}
    assert row["hex"] == "#CBA87D" and row["source"] == CR.SOURCE_BRAND_GOV
    # a REFERENCE palette can never be written: no resolution ever carries a REFERENCE tier
    for role in CR.ROLES:
        r = CR.resolve_role(md, role, Color.from_hex("#000000"), candidates=[("#FF00FF", ref)])
        assert r["tier"] != "REFERENCE" and r["hex"] != "#FF00FF"


def test_the_emitter_resolves_a_non_exempt_documents_declared_roles_and_counts_them(tmp_path):
    from apps.ire import colour_roles as CR
    doc = CR.compose_goal_exercise()
    assert CR.role_map(doc) and CR.role_map(doc)["#CBA87D"] == "ground_gold"
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "roles.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    assert cu["exempt"] is False
    by_role = {r["role"]: r for r in cu["rows"] if r.get("role")}
    assert by_role["ground_gold"]["hex"] == "#CBA87D" and by_role["ground_gold"]["source"] == CR.SOURCE_BRAND_GOV
    assert by_role["ground_cream"]["hex"] == "#FAF3EC" and by_role["ground_blush"]["hex"] == "#F2C4CE"
    assert by_role["accent_dark"]["source"] == CR.SOURCE_SURFACE_FALLBACK          # no brand colour today; the literal, recorded
    assert sum(cu["counter"].values()) >= len(CR.ROLES)                              # every field counted


def test_the_post_hoc_palette_check_measures_against_the_layers_roles_warm_gold_included(db):
    from django.core.management import call_command
    from apps.ire import colour_roles as CR
    call_command("seed_bbrose", verbosity=0)
    hexes = CR.brand_hexes_for_check()
    assert "#CBA87D" in hexes and "#FAF3EC" in hexes and "#F2C4CE" in hexes
    assert "#8B3A52" not in hexes and "#7A4A42" not in hexes                       # the dark accents hold no role
    import inspect
    from apps.pipeline.agents import qa_reviewer
    assert "brand_hexes_for_check" in inspect.getsource(qa_reviewer)


# ---- §BH50(d)-0: a gradient draws its stops' declared opacity on a non-exempt document — never the alpha the
# ---- previous solid fill left in the graphics state; an exempt document paints exactly as before.

def _shading_after_a_solid(md, opacities):
    """A black solid at 0.9 painted first, then a black-to-black gradient whose stops declare ``opacities``."""
    black = Color.from_hex("#000000")
    kids = [Rect(name="solid", x=0, y=0, w=20, h=20, fill=SolidFill(color=black, opacity=0.9)),
            Rect(name="shaded", x=30, y=0, w=20, h=20,
                 fill=GradientFill(kind="linear", x1=30, y1=0, x2=50, y2=0,
                                   stops=[GradientStop(offset=0.0, color=black, opacity=opacities[0]),
                                          GradientStop(offset=1.0, color=black, opacity=opacities[1])]))]
    return Document(page_w=60, page_h=30, title="t", root=Group(name="root", children=kids), metadata=md)


def _grey_at(path, x_mm, y_mm):
    """The rendered grey at a point, 0 (black) .. 255 (white), at 1 px per point."""
    pix = _page(path).get_pixmap(dpi=72)
    return pix.pixel(int(x_mm / 25.4 * 72), int(y_mm / 25.4 * 72))[0]


def test_a_gradient_draws_its_stops_declared_opacity_on_a_non_exempt_document_and_an_exempt_one_is_unchanged(tmp_path):
    from apps.ire import colour_roles as CR
    tagged = {CR.SURFACE_KEY: CR.NON_EXEMPT_EXERCISE}
    out = emit_pdf_ai(_shading_after_a_solid(tagged, (0.25, 0.25)), str(tmp_path / "declared.ai"))
    assert abs(_grey_at(out, 40, 10) - 255 * 0.75) <= 2                    # black at the stops' 0.25 over white
    assert abs(_grey_at(out, 10, 10) - 255 * 0.1) <= 2                     # the solid keeps its own 0.9
    # stops that differ: one alpha per shading, their maximum — the fidelity reader's value for the node
    out = emit_pdf_ai(_shading_after_a_solid(tagged, (0.2, 0.6)), str(tmp_path / "differ.ai"))
    assert abs(_grey_at(out, 31, 10) - 255 * 0.4) <= 2 and abs(_grey_at(out, 49, 10) - 255 * 0.4) <= 2
    # an exempt (untagged) document paints as before: the shading inherits the 0.9 the solid left behind
    out = emit_pdf_ai(_shading_after_a_solid({}, (0.25, 0.25)), str(tmp_path / "exempt.ai"))
    assert abs(_grey_at(out, 40, 10) - 255 * 0.1) <= 2


# ---- §BH50(d): the product's colour roles — declared by the composer, resolved through the layer to brand_gov.

def test_the_dropper_declares_exactly_the_roles_its_materials_fall_in_at_the_records_own_cluster_tolerance():
    """The declaration is the rule, measured: a material takes the §BH39 role whose measured cluster its colour falls
    in, at ΔE76 ≤ 8 (the record's own clustering), the nearest when two hold it — with the instrument the record was
    measured with. Every other material takes none."""
    from apps.ire import colour_roles as CR
    from apps.ire import compose_dropper as D
    from apps.pipeline.services.image_checks import _delta_e, _hex_to_rgb, _rgb_to_lab
    rec = CR.record()
    assert "ΔE76 ≤ 8" in rec["measured_by"] and D.PALETTE_CLUSTER_TOLERANCE_DE76 == 8.0
    clusters = [(r["role"], r["measured_hex"]) for r in rec["roles"]]
    clusters += [(r["role"], r["also"]["measured_hex"]) for r in rec["roles"] if r.get("also")]

    def de(a, b):
        return _delta_e(_rgb_to_lab(_hex_to_rgb(a)), _rgb_to_lab(_hex_to_rgb(b)))
    literals = {name: entry[0] for name, entry in D.MATERIALS.items()} | {"INK": D._INK.to_hex()}
    measured = {}
    for name, hexv in literals.items():
        distance, role = min((de(hexv, m), role) for role, m in clusters)
        if distance <= D.PALETTE_CLUSTER_TOLERANCE_DE76:
            measured[name] = role
    assert D.PRODUCT_COLOUR_ROLES == measured


def test_the_dropper_draws_its_roled_materials_from_brand_gov_and_every_other_colour_as_its_literal(tmp_path):
    from apps.ire import colour_roles as CR
    from apps.ire import compose_dropper as D
    from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE, _GEOMETRY
    doc = D.compose_dropper_sheet(_GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None, logo_path=None,
                                  product_name="Rose Damascena", sku="X",
                                  back_sections=[{"heading": "P", "text": "x"}], revision_status="TEST")
    rows = {r["name"]: r for r in doc.metadata[D.PALETTE_SCHEMA]["rows"]}
    assert {n: (r["role"], r["hex"], r["source"]) for n, r in rows.items() if r["role"]} == {
        "BODY_BASE": ("accent_nude", "#E8C9B3", CR.SOURCE_BRAND_GOV),
        "GLASS_BASE": ("ground_cream", "#FAF3EC", CR.SOURCE_BRAND_GOV),
        "ROSE_GOLD_LIGHT": ("accent_nude", "#E8C9B3", CR.SOURCE_BRAND_GOV),
        "ROSE_GOLD_SPECULAR": ("ground_cream", "#FAF3EC", CR.SOURCE_BRAND_GOV),
        "INK": ("accent_dark", "#2A2426", CR.SOURCE_SURFACE_FALLBACK)}          # no brand swatch: its own literal
    assert all(r["hex"] == r["literal"] and r["source"] == CR.SOURCE_SURFACE_FALLBACK
               for r in rows.values() if r["role"] is None)
    drawn_by = {}
    for n, _ in doc.walk():
        f = getattr(n, "fill", None)
        if isinstance(f, SolidFill):
            drawn_by.setdefault(n.name, set()).add(f.color.to_hex())
        elif isinstance(f, GradientFill):
            drawn_by.setdefault(n.name, set()).update(s.color.to_hex() for s in f.stops)
    assert drawn_by["GLASS_OUTER_WALL"] == {"#E8C9B3"} and drawn_by["GLASS_BASE_THICKNESS"] == {"#FAF3EC"}
    assert drawn_by["COLLAR_ROSE_GOLD_BASE"] == {"#6E3A46", "#BC7480", "#E8C9B3", "#FAF3EC"}
    labels = {n.name: n.text for n, _ in doc.walk() if getattr(n, "type", "") == "text"}
    assert labels["swatch-label-body_base"] == "BODY_BASE #E8C9B3"               # the sheet prints what it draws
    assert labels["swatch-label-type_wine"] == "TYPE_WINE #5A2C3A"
    # the emitter's map holds the brand-resolved hexes only: the ink the sheet's furniture shares is never declared
    assert CR.role_map(doc) == {"#E8C9B3": "accent_nude", "#FAF3EC": "ground_cream"}
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "palette.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    assert {(r["hex"], r["role"]) for r in cu["rows"] if r["source"] == CR.SOURCE_BRAND_GOV} == {
        ("#E8C9B3", "accent_nude"), ("#FAF3EC", "ground_cream")}
    fills = _fills_of(out)
    assert {"#E8C9B3", "#FAF3EC"} <= fills and not {"#D8BEB8", "#EFE8E3", "#EBD0BC", "#FDEFE4"} & fills
    rec = cu["reconciliation"]
    # §BH50(f)(7): "THE COUNTER READS EVERY PLACE COLOUR IS APPLIED — fills, strokes and text." Under the fills-only
    # reader this line pinned counted_but_absent == ["#2A2426", "#8E4F5C"] and agree False: the ink the sheet
    # applies as strokes and text, and the status colour it applies as text alone, were "absent" from a page that
    # carried both. The operator reader finds them where they are, by kind, and the two sets agree both ways.
    assert rec["schema_version"] == CR.RECONCILIATION_SCHEMA and rec["status"] == CR.RECONCILED
    assert set(rec["applied"]["fill"]) == fills
    assert "#2A2426" in rec["applied"]["stroke"] and "#2A2426" in rec["applied"]["text"]
    assert "#8E4F5C" in rec["applied"]["text"]
    assert "#8E4F5C" not in rec["applied"]["fill"] and "#8E4F5C" not in rec["applied"]["stroke"]
    assert rec["applied"]["text_stroke"] == {}                     # no run draws in a stroking render mode
    # the collar's rose-gold base and shadow reach the product only as gradient stops: counted now, as stops
    assert {"#BC7480", "#6E3A46"} <= set(rec["applied"]["stop"])
    assert {"#BC7480", "#6E3A46"} <= set(cu["gradient_stops"])
    assert rec["applied_not_counted"] == [] and rec["counted_not_applied"] == []
    assert rec["agree"] is True and rec["codes"] == []
    assert rec["images"]["count"] == 0


# ---- §BH50(f)(7): THE COUNTER READS EVERY PLACE COLOUR IS APPLIED — the reconciler's five states on small documents.

def _non_exempt(doc):
    """§BH32(h): an untagged document is exempt; the goal-exercise tag lifts it into the layer without a database
    (no role map is declared, so every colour is its own literal, resolved and counted as SURFACE_FALLBACK)."""
    from apps.ire.font_roles import NON_EXEMPT_EXERCISE, SURFACE_KEY
    doc.metadata = dict(doc.metadata or {}, **{SURFACE_KEY: NON_EXEMPT_EXERCISE})
    return doc


def test_an_exempt_document_reads_exempt_not_counted_and_never_a_pass(tmp_path):
    from apps.ire import colour_roles as CR
    usage = {}
    emit_pdf_ai(_doc(), str(tmp_path / "x.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    rec = cu["reconciliation"]
    assert cu["exempt"] is True and cu["counter"] == {} and cu["gradient_stops"] == {}
    assert rec["schema_version"] == CR.RECONCILIATION_SCHEMA
    assert rec["status"] == CR.EXEMPT_NOT_COUNTED and rec["agree"] is None and rec["codes"] == []


def test_the_reader_reads_every_place_colour_is_applied_on_a_non_exempt_document(tmp_path):
    """Fills, strokes, text and the stops of the shading, by kind; the barcode's CMYK ink is process, decided on
    its components; the two sets agree both ways; nothing is read through an ICC conversion."""
    from apps.ire import colour_roles as CR
    usage = {}
    emit_pdf_ai(_non_exempt(_doc()), str(tmp_path / "x.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    rec = cu["reconciliation"]
    assert rec["status"] == CR.RECONCILED
    cream, rose = _CREAM.to_hex(), _ROSE.to_hex()
    assert cream in rec["applied"]["fill"]                      # the sticker
    assert rose in rec["applied"]["stroke"]                     # its border
    assert rose in rec["applied"]["text"]                       # the title
    assert {cream, rose} <= set(rec["applied"]["stop"])         # the ground's radial shading
    assert cu["gradient_stops"] == {cream: 1, rose: 1}          # counted as stops, at the literal drawn
    assert "#000000" in rec["process"]                          # the barcode's CMYK ink, decided on components
    assert any(e["components"] == [0.0, 0.0, 0.0, 1.0] and e["matched_hex"] == "#000000"
               for e in rec["applied_cmyk"])
    assert rec["applied_not_counted"] == [] and rec["counted_not_applied"] == []
    assert rec["agree"] is True and rec["codes"] == []
    assert rec["units"] == CR.UNITS and rec["reader"] == CR.READER


def test_a_cmyk_colour_is_matched_in_the_space_it_is_drawn_in(tmp_path):
    """A solid drawn from a CMYK override reaches the page as `k` components; the counted row carries the same
    components, so it reconciles by them — never by a hex an ICC conversion would invent."""
    from apps.ire import colour_roles as CR
    ink = Color.from_hex("#8B2E3C", cmyk=(0.15, 0.95, 0.60, 0.20))
    doc = _non_exempt(Document(page_w=50, page_h=50, title="cmyk", root=Group(
        name="Artwork", role="artwork", children=[
            Rect(name="swatch", x=5, y=5, w=20, h=20, fill=SolidFill(color=ink))])))
    usage = {}
    emit_pdf_ai(doc, str(tmp_path / "k.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    rec = cu["reconciliation"]
    assert [r["cmyk"] for r in cu["rows"] if r["hex"] == "#8B2E3C"] == [[0.15, 0.95, 0.6, 0.2]]
    assert rec["applied"]["fill"] == {"#8B2E3C": 1}
    assert rec["applied_cmyk"] == [{"kind": "fill", "components": [0.15, 0.95, 0.6, 0.2],
                                    "matched_hex": "#8B2E3C", "count": 1}]
    assert rec["agree"] is True and rec["codes"] == []


def test_a_cmyk_shadings_stops_are_counted_once_and_reconcile_by_components(tmp_path):
    """The stops of a CMYK shading pass through `_rl_color` and are counted there, as colour-set calls, at their
    resolved hex; the stops counter holds RGB shadings only, so no stop sits in both counters. The page draws the
    shading in DeviceCMYK, and each stop endpoint is matched by its components."""
    from apps.ire import colour_roles as CR
    a = Color.from_hex("#8B2E3C", cmyk=(0.15, 0.95, 0.60, 0.20))
    b = Color.from_hex("#EFE9E4", cmyk=(0.05, 0.08, 0.10, 0.0))
    doc = _non_exempt(Document(page_w=50, page_h=50, title="cmyk-grad", root=Group(
        name="Artwork", role="artwork", children=[
            Rect(name="band", x=5, y=5, w=30, h=20, fill=GradientFill(kind="linear", x1=5, y1=5, x2=35, y2=5, stops=[
                GradientStop(offset=0.0, color=a), GradientStop(offset=1.0, color=b)]))])))
    usage = {}
    emit_pdf_ai(doc, str(tmp_path / "g.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    rec = cu["reconciliation"]
    assert cu["gradient_stops"] == {}
    assert cu["counter"] == {"#8B2E3C": 1, "#EFE9E4": 1}
    assert set(rec["applied"]["stop"]) == {"#8B2E3C", "#EFE9E4"}
    assert {e["matched_hex"] for e in rec["applied_cmyk"] if e["kind"] == "stop"} == {"#8B2E3C", "#EFE9E4"}
    assert rec["agree"] is True and rec["codes"] == []


def _rl_canvas(path):
    from reportlab.pdfgen import canvas as _canvas
    return _canvas.Canvas(str(path))


def test_a_form_xobject_inherits_the_colour_in_effect_where_it_is_painted(tmp_path):
    """A Form XObject with no colour of its own paints in the state in effect at `Do`; the reader reads it there,
    never from a fresh black state that would drop the colour into process (review finding R1)."""
    from reportlab.lib.colors import Color as RLColor
    from apps.ire import colour_applications as CA
    path = tmp_path / "form.pdf"
    c = _rl_canvas(path)
    c.beginForm("F1")
    c.rect(10, 10, 20, 20, fill=1, stroke=1)
    c.endForm()
    c.setFillColor(RLColor(1, 0, 0))
    c.setStrokeColor(RLColor(0, 1, 0))
    c.doForm("F1")
    c.showPage()
    c.save()
    read = CA.read_applications(str(path))
    assert read["status"] == "READ"
    assert {e["hex"] for e in read["events"] if e["kind"] == "fill"} == {"#FF0000"}
    assert {e["hex"] for e in read["events"] if e["kind"] == "stroke"} == {"#00FF00"}


def test_an_inline_image_never_hides_what_is_drawn_after_it(tmp_path):
    """The payload between ID and EI is skipped by the tokenizer, so a byte in it can never swallow the operators
    after the image and leave a READ census short (review finding R2). Twenty random payloads."""
    import random
    from PIL import Image as PILImage
    from reportlab.lib.colors import Color as RLColor
    from apps.ire import colour_applications as CA
    for seed in range(20):
        rnd = random.Random(seed)
        im = PILImage.new("RGB", (9, 7))
        im.putdata([tuple(rnd.randrange(256) for _ in range(3)) for _ in range(63)])
        path = tmp_path / f"inline{seed}.pdf"
        c = _rl_canvas(path)
        c.setFillColor(RLColor(1, 0, 0))
        c.rect(5, 5, 10, 10, fill=1, stroke=0)
        c.drawInlineImage(im, 30, 30, 20, 20)
        c.setFillColor(RLColor(0, 0, 1))
        c.rect(60, 60, 10, 10, fill=1, stroke=0)
        c.showPage()
        c.save()
        read = CA.read_applications(str(path))
        assert read["status"] == "READ", (seed, read.get("reason"))
        assert {e["hex"] for e in read["events"] if e["kind"] == "fill"} == {"#FF0000", "#0000FF"}, seed
        assert [e["xobject"] for e in read["events"] if e["kind"] == "image"] == ["inline"], seed


def test_an_object_the_reader_cannot_resolve_reads_unread_never_clean(tmp_path):
    """An XObject name the page's resources do not hold, like a shading function the reader cannot read, makes the
    reconciliation UNREAD with the unreconciled code — never a clean census (review finding R3); and a content
    stream cut inside a literal string raises inside the reader, so it is UNREAD too, never READ short (R4)."""
    from reportlab.lib.colors import Color as RLColor
    from apps.ire import colour_applications as CA
    from apps.ire import colour_roles as CR
    path = tmp_path / "missing.pdf"
    c = _rl_canvas(path)
    c.setFillColor(RLColor(1, 0, 0))
    c.rect(1, 1, 5, 5, fill=1, stroke=0)
    c._code.append("/NotInResources Do")
    c.showPage()
    c.save()
    rec = CR.reconcile_colours(str(path), {"counter": {"#FF0000": 1}, "gradient_stops": {}, "rows": [], "exempt": False})
    assert rec["status"] == CR.UNREAD and rec["agree"] is None
    assert rec["codes"] == [CR.COLOUR_USAGE_UNRECONCILED_CODE]
    assert "NotInResources" in rec["reason"]
    with pytest.raises(ValueError):
        list(CA._tokenize(b"BT (never closed Tj ET 1 0 0 rg 0 0 5 5 re f"))


def test_an_unreadable_artefact_reads_unread_with_the_code_and_the_emit_never_raises(tmp_path, monkeypatch):
    from apps.ire import colour_applications as CA
    from apps.ire import colour_roles as CR

    def torn(self, raw):
        raise RuntimeError("torn artefact")
    monkeypatch.setattr(CA._PDF, "__init__", torn)
    usage = {}
    out = emit_pdf_ai(_non_exempt(_doc()), str(tmp_path / "u.ai"), usage_out=usage)
    assert _raw(out).startswith(b"%PDF-")                      # the artefact was written; only the reader failed
    rec = usage[CR.USAGE_SCHEMA]["reconciliation"]
    assert rec["status"] == CR.UNREAD and rec["agree"] is None
    assert rec["codes"] == [CR.COLOUR_USAGE_UNRECONCILED_CODE]
    assert "RuntimeError: torn artefact" in rec["reason"]


def test_a_run_with_no_glyph_applies_no_colour_and_is_not_counted(tmp_path):
    """reportlab writes no show operator for an empty string, so an empty run applies no colour; its colour-set call
    is taken back out of the counter, and a colour drawn only by such a run is neither counted nor applied."""
    from apps.ire import colour_roles as CR
    ghost = Color.from_hex("#123456")
    doc = _non_exempt(_doc())
    doc.root.children.append(Group(name="Empty", role="label", children=[
        TextRun(name="empty", text="", x=10, y=10, size_pt=9, color=ghost, font="bold")]))
    usage = {}
    emit_pdf_ai(doc, str(tmp_path / "e.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    rec = cu["reconciliation"]
    assert "#123456" not in cu["counter"]
    assert all("#123456" not in v for v in rec["applied"].values())
    assert rec["agree"] is True and rec["codes"] == []


def test_a_colour_on_the_page_that_no_counter_holds_is_a_named_disagreement_both_ways(tmp_path):
    from apps.ire import colour_roles as CR
    usage = {}
    out = emit_pdf_ai(_non_exempt(_doc()), str(tmp_path / "d.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    forgotten = dict(cu, counter={}, gradient_stops={})
    rec = CR.reconcile_colours(out, forgotten)
    assert rec["applied_not_counted"] == sorted({_CREAM.to_hex(), _ROSE.to_hex()})   # process black is not a defect
    assert rec["counted_not_applied"] == []
    assert rec["agree"] is False and rec["codes"] == [CR.COLOUR_USAGE_DISAGREEMENT_CODE]
    ghost = dict(cu, counter=dict(cu["counter"], **{"#123456": 1}))
    rec2 = CR.reconcile_colours(out, ghost)
    assert rec2["counted_not_applied"] == ["#123456"] and rec2["agree"] is False


# ---- §BH39(f) + GOAL STATE: usage measured on real emitted documents — counter == every application (§BH50(f)(7)),
# ---- placement == embedded images;
# ---- a REAL non-exempt document with every colour role resolving through the layer to brand_gov, Warm Gold included;
# ---- one document placing a PRODUCTION asset with its credit in the record and visible; the two negative controls.

def _tier_rows_on_disk():
    """The materials tier record (var/ audit output, the outer root) — the goal documents draw on its rows."""
    import json as _json
    from pathlib import Path as _Path
    rec = _Path(__file__).resolve().parents[4] / "var" / "design_intelligence" / "audits" / "dip0" / "tiers" / "materials_tiers.jsonl"
    if not rec.exists():
        pytest.skip("materials tier record not present (var/ audit output)")
    return [_json.loads(l) for l in rec.read_text(encoding="utf-8").splitlines() if l.strip()]


def _fills_of(path):
    return {"#%02X%02X%02X" % tuple(max(0, min(255, int(round(v * 255)))) for v in d["fill"][:3])
            for d in _page(path).get_drawings() if d.get("fill") is not None}


def test_goal_a_real_non_exempt_document_draws_every_colour_role_from_brand_gov_and_the_counter_equals_its_fills(tmp_path, db):
    from django.core.management import call_command
    from apps.ire import colour_roles as CR
    call_command("seed_bbrose", verbosity=0)
    doc = CR.compose_goal_exercise()
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "goal.ai"), usage_out=usage)
    cu = usage[CR.USAGE_SCHEMA]
    brand = set(CR.brand_hexes_for_check())
    fills = _fills_of(out)
    assert "#CBA87D" in fills                                                     # Warm Gold, drawn from brand_gov
    resolved = {r["hex"] for r in cu["rows"] if r.get("source") == CR.SOURCE_BRAND_GOV}
    assert resolved <= brand and "#CBA87D" in resolved
    assert cu["reconciliation"]["agree"] is True             # counter == every application (§BH50(f)(7))
    assert not cu["reconciliation"]["applied_not_counted"] and not cu["reconciliation"]["counted_not_applied"]
    # every fill on the artefact is a resolved role's colour or process black/white; nothing outside brand_gov drew
    literal_fallbacks = {r["hex"] for r in cu["rows"] if r.get("source") == CR.SOURCE_SURFACE_FALLBACK}
    assert fills <= brand | literal_fallbacks | {"#FFFFFF", "#000000"}
    assert literal_fallbacks <= {"#231916", "#000000"}                              # accent_dark and ink: no brand colour today


def test_goal_a_document_placing_a_production_asset_carries_its_credit_in_the_record_and_visibly_and_the_counter_agrees(tmp_path):
    from apps.ire import materials_placement as MP
    from apps.ire import materials_owner_grant as MG
    from apps.ire.graph import Image
    rows = _tier_rows_on_disk()
    prod = [r for r in rows if r["tier"] == "PRODUCTION" and r.get("condition") and r["relative_path"].lower().endswith(".jpg")]
    assert prod
    row = prod[0]
    src = MP.REPO_ROOT / row["relative_path"]
    if not src.exists():
        pytest.skip("materials/ not on this machine")
    node = Image(name="asset-goal", src=str(src), x=5, y=5, w=40, h=30)
    rec = MP.placement_record(node, row, credit_node_name="credit-asset-goal")
    credit = MP.credit_node(rec, x=5, y=52, size_pt=6)
    doc = _mat_doc(tmp_path, src=src, record=rec, credit=credit, name="asset-goal")
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "goal_asset.ai"), usage_out=usage)
    pu = usage[MP.USAGE_SCHEMA]
    assert pu["rows"][0]["resolution"] == MP.PLACED and pu["rows"][0]["evidence"] == row["evidence"]
    assert pu["rows"][0]["condition"] == row["condition"]                          # the credit in the record
    assert MP.credit_text(row["condition"]) in _page(out).get_text()               # and visible on the artefact
    assert pu["reconciliation"]["agree"] is True and pu["reconciliation"]["embedded_images"] == 1


def test_goal_negative_controls_a_reference_asset_is_never_placed_and_a_reference_palette_is_never_written(tmp_path):
    from apps.ire import colour_roles as CR
    from apps.ire import materials_placement as MP
    from apps.ire.graph import Color, Image
    rows = _tier_rows_on_disk()
    ref = next(r for r in rows if r["tier"] == "REFERENCE" and r["relative_path"].lower().endswith(".jpg"))
    src = MP.REPO_ROOT / ref["relative_path"]
    if not src.exists():
        pytest.skip("materials/ not on this machine")
    node = Image(name="asset-ref", src=str(src), x=5, y=5, w=40, h=30)
    doc = _mat_doc(tmp_path, src=src, record=MP.placement_record(node, ref), name="asset-ref")
    with pytest.raises(MP.PlacementRefused) as e:
        emit_pdf_ai(doc, str(tmp_path / "ref_goal.ai"), usage_out={})
    assert e.value.code == MP.REFUSED_REFERENCE_ASSET and not (tmp_path / "ref_goal.ai").exists()
    md = {CR.SURFACE_KEY: CR.NON_EXEMPT_EXERCISE}
    for role in CR.ROLES:
        r = CR.resolve_role(md, role, Color.from_hex("#000000"), candidates=[("#FF00FF", dict(ref, evidence=""))])
        assert r["hex"] != "#FF00FF" and r["tier"] != "REFERENCE"
        assert all(v["verdict"] == CR.CANDIDATE_INSPIRATION_ONLY for v in r["verdicts"])


# ---- §BH48(a): the container composers adopt the theme — the exemption lifted for the product path.
def test_the_three_container_composers_are_lifted_and_the_seven_others_stay():
    from apps.ire import font_roles as FR
    lifted = {"apps/ire/compose_dropper.py::compose_dropper_sheet",
              "apps/ire/back_panel.py::compose_back_panel",
              "apps/ire/compose_container.py::compose_container_graph"}
    assert not lifted & set(FR.EXEMPT_SURFACES)
    for entry in lifted:
        assert not FR.is_exempt({FR.SURFACE_KEY: entry})
    # six stay since the owner's message of 2026-10-29 (the four checks re-pinned): the dieline previews' entry left with
    # its file to archive/, and the production PDF's two resolvers carry the one die writer's path
    stayed = {"apps/ire/compose_vector_art.py::compose_vector_art_graph",
              "apps/dielines/exporters/counter_display_files.py::_resolve_fonts",
              "apps/dielines/exporters/counter_display_files.py::_resolve_arabic_font",
              "apps/dielines/exporters/info_panel.py::draw_info_panel",
              "apps/dielines/exporters/info_panel.py::svg_info_panel",
              "apps/ire/handoff/graph_schema.py::serialize_handoff_graph"}
    assert stayed == set(FR.EXEMPT_SURFACES)


def test_the_layer_knows_the_dropper_fronts_role_key_so_no_run_is_skipped(tmp_path):
    """The dropper front names its product-name runs `serif-bold`. Before §BH48(a) the emitter's
    theme path found no face for that key and skipped the chunk (July drew it in the legacy Regular);
    the layer now reads it as `display`, and a lifted surface draws every run it composes."""
    from apps.ire import font_roles as FR
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, TextRun
    assert FR.base_role("serif-bold") == "display"
    assert FR.roles_for_text("serif-bold", "Rose") == {"display"}
    doc = Document(page_w=60, page_h=40, root=Group(name="root", children=[
        TextRun(name="name", text="Rose Damascena", x=6, y=20, font="serif-bold", size_pt=9.0, color=Color.from_hex("#222222"))]),
        metadata={FR.SURFACE_KEY: "apps/ire/compose_dropper.py::compose_dropper_sheet"})
    assert not FR.is_exempt(doc)
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "front.ai"), usage_out=usage)
    assert "Poppins-Light" in _embedded_faces(out)
    refused = usage["refused"] if "refused" in usage else next(v for k, v in usage.items() if isinstance(v, dict) and "refused" in v)["refused"]
    assert refused["chunks"] == [] and refused["roles"] == {}


def test_the_products_text_is_set_by_role_and_the_theme_faces_reach_it_through_the_layer(tmp_path):
    """§BH49(c): the dropper front's name lines are the HEADING (Montserrat[wght] at its pinned 700
    instance), the support line the BODY, the net content the CAPTION; the back panel's headings and
    copy the same two roles. The aliases stay for the sheet's own furniture. Emitted, the usage record
    counts exactly those faces, none outside the layer, nothing refused."""
    from apps.ire.compose_dropper import compose_dropper_sheet
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.tests.test_back_panel import _FRONT_RECORD
    from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE, _GEOMETRY
    # §BH67(c)2: the support line and the net content are the product record's — handed in, as production does
    doc = compose_dropper_sheet(_GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None,
                                logo_path=None, product_name="Rose Damascena", sku="X",
                                back_sections=[{"heading": "Directions", "text": "Apply nightly."}],
                                revision_status="TEST", drawing_source="PARAMETRIC", **_FRONT_RECORD)
    roles = {n.name: n.font for n, _ in doc.walk() if getattr(n, "type", "") == "text"}
    assert {k: v for k, v in roles.items() if k.startswith("product-name-hero-")} == {
        "product-name-hero-0": "heading", "product-name-hero-1": "heading"}
    assert roles["front-support"] == "body" and roles["front-net-content"] == "caption"
    back = {k: v for k, v in roles.items() if k.startswith("back-panel-")}
    assert back and all(v == ("heading" if "-heading-" in k else "body") for k, v in back.items()), back
    assert roles["sheet-title"] == "bold" and roles["sku"] == "bold"          # the sheet's furniture keeps its aliases
    usage = {}
    emit_pdf_ai(doc, str(tmp_path / "dropper_roles.ai"), usage_out=usage)
    by_face = {f["postscript"]: set(f["roles"]) for f in usage["faces"]}
    assert by_face["Montserrat-Bold"] == {"heading"}
    assert by_face["Poppins-Regular"] == {"body"}
    assert by_face["Poppins-Light"] == {"caption", "display"}
    assert usage["outside_layer"] == [] and usage["refused"] == {"roles": {}, "chunks": []}


# ---------------------------------------------------------------------------------------------------------------
# §BH65(c) — THE ONE CONTRACT, emitter side: every capability the contract calls DRAWN that the EMITTER writes as
# its own PDF construct is proved on the bytes of a file actually written — never on the composer's say-so. A new
# DRAWN emitter capability without a proof here fails the coverage assertion.
# ---------------------------------------------------------------------------------------------------------------

def _one(node):
    return Document(page_w=60, page_h=60, title="t",
                    root=Group(name="Artwork", role="artwork", children=[node]))


def _bezier():
    from apps.ire.graph import ClosePath, CubicTo, MoveTo, Path
    return Path(name="petal", segments=[MoveTo(x=10, y=30), CubicTo(x1=20, y1=10, x2=40, y2=10, x=50, y=30),
                                        ClosePath()], fill=SolidFill(color=_ROSE))


def _patterned(kind):
    from apps.ire.graph import PatternFill
    return _one(Rect(name="p", x=5, y=5, w=30, h=20, fill=PatternFill(kind=kind, color=_ROSE, spacing_mm=1.5)))


def _faded(kind="linear"):
    from apps.ire.graph import OpacityMask
    mask = (OpacityMask(kind="linear", x1=5, y1=30, x2=55, y2=30, start_opacity=1.0, end_opacity=0.0)
            if kind == "linear" else
            OpacityMask(kind="radial", cx=30, cy=30, r=25, start_opacity=1.0, end_opacity=0.0))
    return Document(page_w=60, page_h=60, title="t", root=Group(name="Artwork", role="artwork", children=[
        Rect(name="ground", x=0, y=0, w=60, h=60, fill=SolidFill(color=_CREAM)),     # an opaque page to read
        Group(name="faded", role="decoration", opacity_mask=mask, children=[
            Rect(name="band", x=5, y=20, w=50, h=20, fill=SolidFill(color=_ROSE))])]))


def _shadowed():
    from apps.ire.graph import Shadow
    return _one(Rect(name="lifted", x=10, y=10, w=30, h=20, fill=SolidFill(color=_CREAM),
                     shadow=Shadow(color=_ROSE, blur_mm=1.5, opacity=0.4)))


def _square_clip():
    from apps.ire.graph import ClosePath, LineTo, MoveTo
    return [MoveTo(x=0, y=0), LineTo(x=30, y=0), LineTo(x=30, y=30), ClosePath()]


#: capability -> (a document drawing it, the operator bytes its file must carry)
_EMITTER_PROOFS = {
    "path": (lambda: _one(_bezier()), (b" c\n", b" c ")),
    "solid_fill": (lambda: _one(Rect(name="r", x=5, y=5, w=20, h=20, fill=SolidFill(color=_ROSE))), (b" f\n", b"f*")),
    "gradient_fill": (lambda: _doc(), (b" sh\n", b" sh ")),
    "opacity": (lambda: _one(Rect(name="r", x=5, y=5, w=20, h=20, fill=SolidFill(color=_ROSE, opacity=0.4))),
                (b" gs\n", b" gs ")),
    "clip": (lambda: _one(Group(name="g", role="decoration", clip=_square_clip(),
        children=[Rect(name="r", x=5, y=5, w=40, h=40, fill=SolidFill(color=_ROSE))])), (b"W* n", b"W n")),
    "stroke": (lambda: _one(Rect(name="r", x=5, y=5, w=20, h=20, stroke=Stroke(color=_ROSE, width_mm=0.3))),
               (b" S\n", b" S ")),
    "live_text": (lambda: _one(TextRun(name="t", text="FOCUS", x=30, y=30, size_pt=12, color=_ROSE,
                                       align="center")), (b"Tj", b"TJ")),
    # §BH65(c)8: letter-spacing is the PDF character-spacing operator on the run
    "tracking": (lambda: _themed(_one(TextRun(name="t", text="Focus", x=30, y=30, size_pt=12, color=_ROSE,
                                              align="center", tracking_em=0.15))), (b" Tc",)),
    "small_caps": (lambda: _themed(_one(TextRun(name="t", text="Focus", x=30, y=30, size_pt=12, color=_ROSE,
                                                align="center", text_case="upper"))), (b"FOCUS", b"(FOCUS)")),
    # §BH65(c)4: a pattern is native vector marks inside the shape's clip — dots filled, lines and grain stroked
    "pattern_fill": (lambda: _patterned("dots"), (b"\nf\n", b" f\n", b"f*")),
    "texture_fill": (lambda: _patterned("grain"), (b"\nS\n", b" S\n")),
    "line_field": (lambda: _patterned("lines"), (b"\nS\n", b" S\n")),
    # §BH65(c)5: the blend mode's graphics state is set in the content; its /BM name is proved on the file below
    "blend_mode": (lambda: _one(Rect(name="b", x=5, y=5, w=20, h=20, fill=SolidFill(color=_ROSE),
                                     blend_mode="multiply")), (b" gs\n", b" gs ")),
    # §BH65(c)6: the soft mask's graphics state is set in the content; the mask itself is proved on the render below
    "soft_mask": (lambda: _faded(), (b" gs\n", b" gs ")),
    # a glow is a disc under a RADIAL soft mask — the same construct, proved the same way
    "glow": (lambda: _faded("radial"), (b" gs\n", b" gs ")),
    # §BH65(c)7: an APPROXIMATED shadow is still an emitter construct — the offset silhouette, filled and stroked
    "soft_shadow": (lambda: _shadowed(), (b"\nB\n", b" B\n", b"B*")),
}


def test_every_drawn_capability_the_emitter_writes_is_proved_on_its_bytes(tmp_path):
    from apps.ire import composer_vocabulary as V
    emitted = {t.capability for t in V.TERMS if t.status in (V.DRAWN, V.APPROXIMATED)
               and (t.axis == "primitive" or t.capability in ("live_text", "tracking", "small_caps"))}
    assert emitted == set(_EMITTER_PROOFS), "a DRAWN emitter capability has no proof on the bytes"
    for capability, (make, needles) in _EMITTER_PROOFS.items():
        out = emit_pdf_ai(make(), str(tmp_path / f"{capability}.ai"))
        content = fitz.open(out)[0].read_contents()
        assert any(n in content for n in needles), (capability, needles)



# §BH65(c)2 — every finish the contract calls DRAWN is proved on the file: page 1 DEPICTS it, and its PLATE is its own
# page after the artwork, a black mask labelled with the plate's name. A document with no finish writes one page.

def _finished(kind, plate, *, appearance="#C9A24B", stroke_only=False):
    from apps.ire.graph import Finish
    node = _bezier()
    if stroke_only:
        node = node.model_copy(update={"fill": None, "stroke": Stroke(color=_ROSE, width_mm=0.3)})
    fin = Finish(kind=kind, plate=plate, appearance=Color.from_hex(appearance) if kind in ("foil", "metallic_ink")
                 else None)
    return _one(node.model_copy(update={"finishes": [fin]}))


_FINISH_PROOFS = {
    "finish:foil": ("foil", "FOIL_ROSE_GOLD"), "finish:metallic_ink": ("metallic_ink", "METALLIC_PEARL"),
    "finish:spot_uv": ("spot_uv", "SPOT_UV"), "finish:gloss_varnish": ("gloss_varnish", "VARNISH_GLOSS"),
    "finish:soft_touch": ("soft_touch", "SOFT_TOUCH"), "finish:emboss": ("emboss", "EMBOSS"),
    "finish:deboss": ("deboss", "DEBOSS"), "finish:plate": ("spot_uv", "SPOT_UV"),
}


def test_every_finish_is_depicted_on_page_one_and_plated_on_its_own_page(tmp_path):
    from apps.ire import composer_vocabulary as V
    from apps.ire.container_finishes import SCHEMA
    drawn = {t.capability for t in V.TERMS if t.axis == "finish" and t.status == V.DRAWN}
    assert drawn == set(_FINISH_PROOFS), "a DRAWN finish has no proof on the bytes"
    bare = fitz.open(emit_pdf_ai(_one(_bezier()), str(tmp_path / "bare.ai")))[0].read_contents()
    for capability, (kind, plate) in _FINISH_PROOFS.items():
        usage = {}
        out = emit_pdf_ai(_finished(kind, plate), str(tmp_path / f"{kind}.ai"), usage_out=usage)
        pdf = fitz.open(out)
        assert pdf.page_count == 2, capability
        assert f"FINISH PLATE {plate}" in pdf[1].get_text(), capability
        assert usage[SCHEMA]["plates"] == [{"plate": plate, "kind": kind, "page": 2, "items": ["petal"]}]
        page1 = pdf[0].read_contents()
        if kind in ("foil", "metallic_ink"):
            assert b".788235 .635294 .294118 rg" in page1, capability        # #C9A24B, the depiction
        elif kind == "soft_touch":
            assert page1 == bare, capability                                  # matte depicts as nothing
        else:
            # a sheen or a relief is drawn over the element, at its own alpha
            assert page1 != bare and page1.startswith(bare.rstrip(b" \n")) and b" gs" in page1, capability


def test_a_document_with_no_finish_writes_one_page_and_records_no_plate(tmp_path):
    from apps.ire.container_finishes import SCHEMA
    usage = {}
    out = emit_pdf_ai(_doc(), str(tmp_path / "d.ai"), usage_out=usage)
    assert fitz.open(out).page_count == 1
    assert usage[SCHEMA]["plates"] == [] and usage[SCHEMA]["pages"] == 1


def test_a_clear_finish_on_a_clipped_group_floods_the_region_and_its_leaves_keep_their_paint(tmp_path):
    from apps.ire.container_finishes import SCHEMA
    from apps.ire.graph import Finish
    group = Group(name="FRONT_DIRECT_PRINT", role="decoration", clip=_square_clip(),
                  finishes=[Finish(kind="soft_touch", plate="SOFT_TOUCH")],
                  children=[TextRun(name="product-name-hero", text="FOCUS", x=15, y=15, size_pt=9, color=_ROSE,
                                    align="center")])
    usage = {}
    out = emit_pdf_ai(_one(group), str(tmp_path / "g.ai"), usage_out=usage)
    assert usage[SCHEMA]["plates"] == [{"plate": "SOFT_TOUCH", "kind": "soft_touch", "page": 2,
                                        "items": ["FRONT_DIRECT_PRINT"]}]
    assert "FOCUS" not in fitz.open(out)[1].get_text()       # the region is the plate, not the type on it


def test_the_colour_counter_agrees_with_a_finish_bearing_artefact_on_every_page(tmp_path):
    """A THEMED document — an exempt one counts nothing and reconciles nothing (§BH32(h)), so it would prove nothing.
    The counter reads every page, the plates' black included, and still agrees with the artefact."""
    from apps.ire.colour_roles import RECONCILED, USAGE_SCHEMA
    from apps.ire.graph import Finish
    doc = _themed(_doc())
    doc.root.children[1].children[1].finishes = [Finish(kind="foil", plate="FOIL_GOLD",
                                                        appearance=Color.from_hex("#C9A24B"))]
    doc.root.children[1].children[0].finishes = [Finish(kind="spot_uv", plate="SPOT_UV")]
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "f.ai"), usage_out=usage)
    assert fitz.open(out).page_count == 3
    recon = usage[USAGE_SCHEMA]["reconciliation"]
    assert recon["status"] == RECONCILED and recon["agree"] is True and recon["codes"] == []



def test_every_pattern_kind_is_vector_marks_inside_the_shape_and_the_counter_agrees(tmp_path):
    """§BH65(c)4: lines, cross-hatch, dots, grain and rings — each emitted as native path marks, cut to the element's
    shape, no image and no /Pattern resource the colour reader could not read; the counter agrees on a themed page."""
    from apps.ire.colour_roles import USAGE_SCHEMA
    from apps.ire.graph import PatternFill
    for kind in ("lines", "crosshatch", "dots", "grain", "rings"):
        doc = _themed(_one(Rect(name="p", x=5, y=5, w=30, h=20, fill=PatternFill(
            kind=kind, color=_ROSE, spacing_mm=1.5, angle_deg=30.0))))
        usage = {}
        out = emit_pdf_ai(doc, str(tmp_path / f"{kind}.ai"), usage_out=usage)
        raw, page = _raw(out), fitz.open(out)[0]
        assert page.get_images() == [] and b"/Pattern" not in raw, kind
        assert b"W* n" in page.read_contents() or b"W n" in page.read_contents(), kind    # cut to the shape
        assert usage[USAGE_SCHEMA]["reconciliation"]["agree"] is True, kind



def test_a_blend_mode_is_written_as_its_pdf_name_and_reaches_nothing_after_it(tmp_path):
    """§BH65(c)5: every mode the graph accepts is a mode reportlab writes, by its PDF name; it is set inside its own
    graphics state (q ... Q), so the next element prints Normal; and a finish plate never prints in its element's
    blend mode — a mask is black, whatever the artwork's blend."""
    import typing
    from apps.ire.graph import BlendMode, Finish
    for mode in typing.get_args(BlendMode):
        doc = _one(Rect(name="b", x=5, y=5, w=20, h=20, fill=SolidFill(color=_ROSE), blend_mode=mode))
        raw = _raw(emit_pdf_ai(doc, str(tmp_path / f"{mode}.ai")))
        from apps.ire.emitters.pdf_ai import _PDF_BLEND
        assert b"/BM /" + _PDF_BLEND[mode].encode() in raw, mode
    doc = _one(Group(name="g", role="decoration", children=[
        Rect(name="under", x=5, y=5, w=20, h=20, fill=SolidFill(color=_ROSE), blend_mode="multiply",
             finishes=[Finish(kind="spot_uv", plate="SPOT_UV")]),
        Rect(name="after", x=30, y=5, w=20, h=20, fill=SolidFill(color=_CREAM))]))
    out = emit_pdf_ai(doc, str(tmp_path / "scoped.ai"))
    page1 = fitz.open(out)[0].read_contents()
    after_blend = page1.split(b" gs", 1)[1]                                   # set, restored, then the next element
    assert b"Q" in after_blend and b"re f" in after_blend.split(b"Q", 1)[1]
    assert b" gs" not in fitz.open(out)[1].read_contents().split(b"BT")[0]    # the plate page sets no blend



def test_a_soft_mask_is_a_true_pdf_soft_mask_and_the_preview_renderer_fades_it(tmp_path):
    """§BH65(c)6: a luminosity /SMask whose form is declared a DeviceGray transparency GROUP — measured before this
    was written: without the /Group declaration macOS's renderer (sips, which makes every preview) ignores the mask
    and paints the band at full alpha, while MuPDF honours it. The render here is the preview's own path."""
    from apps.ire.rasterize import pdf_to_png
    from PIL import Image as PILImage
    for kind in ("linear", "radial"):
        out = emit_pdf_ai(_faded(kind), str(tmp_path / f"{kind}.ai"))
        raw = _raw(out)
        assert b"/SMask" in raw and b"/Luminosity" in raw and b"/Transparency" in raw, kind
        png = str(tmp_path / f"{kind}.png")
        assert pdf_to_png(out, png)
        im = PILImage.open(png).convert("RGB")
        w, h = im.size
        # where the mask keeps the band it prints rose; where the mask drops it the cream ground shows through
        kept, dropped = ((0.12, 0.85) if kind == "linear" else (0.5, 0.12))
        near, far = im.getpixel((int(w * kept), h // 2)), im.getpixel((int(w * dropped), h // 2))
        assert near != far and far[0] > near[0] and far[2] > near[2], (kind, near, far)   # toward #EFE9E4 from #8B2E3C



def test_a_soft_shadow_is_stepped_vector_under_its_element_and_never_a_raster(tmp_path):
    """§BH65(c)7, APPROXIMATED and said so: PDF has no blur. The silhouette, offset, drawn eight times at 1/8 of the
    shadow's alpha with a widening stroke — drawn BEFORE its element, so it lies under it; no image anywhere; and
    the render is darker where the steps overlap than at the blur's outer edge."""
    from apps.ire.rasterize import pdf_to_png
    from PIL import Image as PILImage
    out = emit_pdf_ai(_shadowed(), str(tmp_path / "shadow.ai"))
    page = fitz.open(out)[0]
    assert page.get_images() == []
    content = page.read_contents()
    shadow_part, element_part = content.split(b"Q", 1)                 # the shadow's own q..Q, then the element
    assert (b"B*" in shadow_part or b"\nB\n" in shadow_part) and b"re f" in element_part   # fill+stroke, then the element
    png = str(tmp_path / "shadow.png")
    assert pdf_to_png(out, png)
    im = PILImage.open(png).convert("RGB")
    w, h = im.size
    # the shadow shows past the element's lower-right edge, and fades toward the blur's outer edge
    inner = im.getpixel((int(w * 0.50), int(h * 0.535)))
    outer = im.getpixel((int(w * 0.50), int(h * 0.555)))
    assert inner != outer and inner != (255, 255, 255)



def test_a_tracked_capitalised_run_prints_centred_and_its_box_is_the_box_it_prints(tmp_path):
    """§BH65(c)8: tracking is added after every glyph but the last, so a centred run's ink stays centred on its anchor;
    the record keeps the run's own words while the page prints capitals; and the text box every instrument reads
    (geometry_report._text_bbox_mm) is the box the run prints — wider by exactly its tracking, in its case."""
    from apps.ire.geometry_report import _text_bbox_mm
    plain = TextRun(name="t", text="Focus Pressed", x=30, y=30, size_pt=9, color=_ROSE, align="center")
    styled = plain.model_copy(update={"tracking_em": 0.15, "text_case": "upper"})
    out = emit_pdf_ai(_themed(_one(styled)), str(tmp_path / "t.ai"))
    page = fitz.open(out)[0]
    # the extractor itself spaces the tracked letters apart ("F OC U S ...") — the tracking, read back
    assert "FOCUSPRESSED" in "".join(page.get_text().split()) and styled.text == "Focus Pressed"
    words = page.get_text("words")
    left, right = min(w[0] for w in words), max(w[2] for w in words)
    centre_mm = (left + right) / 2 * 25.4 / 72
    assert round(centre_mm, 1) == 30.0                                    # centred on its anchor
    bp, bs = _text_bbox_mm(plain), _text_bbox_mm(styled)
    assert bs[2] != bp[2] and round(bs[0] + bs[2] / 2, 6) == round(bp[0] + bp[2] / 2, 6)


# ---------------------------------------------------------------------------------------------------------------
# §BH67(c)5 — "where the concept names a face that sits inside my granted set — the 35 plus the Noto trio — the
# concept's face leads. Outside that set, the role layer decides. No face outside the set is ever drawn."
# ---------------------------------------------------------------------------------------------------------------

def _typeface(sig):
    from apps.ire import concept_typeface as CT
    from apps.ire.font_roles import INSTANCE_WEIGHT_BY_ROLE, catalogue
    return CT.read({"typography_signature": sig}, catalogue(),
                   name_role_pin=INSTANCE_WEIGHT_BY_ROLE.get("display"))


def test_bh67c5_a_granted_face_the_concept_names_leads_its_name_and_a_style_names_none():
    from apps.ire import concept_typeface as CT
    r = _typeface("Product name 'Focus' in Poppins SemiBold, wide-tracked; claims in Lato Light on the side band; "
                  "BBROSE lockup in Montserrat")
    assert (r["name"]["verdict"], r["name"]["stem"]) == (CT.LEADS, "Poppins-SemiBold")
    rows = {row["family"]: row for row in r["named"]}
    assert (rows["lato"]["element"], rows["lato"]["code"]) == ("other", CT.WEIGHT_NOT_GRANTED)   # Lato Black only
    assert rows["montserrat"]["element"] == "mark"                # the lockup is fixed artwork, never re-set
    # task 91's own words name a STYLE and no face: nothing leads, and the role layer decides as it always has
    t91 = _typeface("High-contrast old-style Latin serif ('Focus') over matching Naskh ('فوكس'), identical cap-height, "
                    "tracked evenly, set above the petal window in Deep Rose; BBROSE wordmark in rose-gold hot-foil "
                    "at the crown arc")
    assert t91["state"] == "READ" and t91["name"] is None and t91["named"] == []


def test_bh67c5_what_cannot_lead_is_refused_by_name_and_the_role_layer_decides():
    from apps.ire import concept_typeface as CT
    assert _typeface("Name in Didot italic")["name"]["code"] == CT.OUTSIDE_THE_SET
    # §BH33(2): "A role with no pinned weight never receives a variable face" — the name prints at DISPLAY, which pins
    # none, so the set's only serif cannot lead a container's name until the owner pins a display instance
    # [§BH68(c), 2026-09-24: HE PINNED IT — display takes the heading pin, 700. The set's only serif now LEADS, at the
    # weight the layer draws; the refusal stands, by name, for a role that pins none.]
    playfair = _typeface("Playfair Display Bold for 'Focus'")["name"]
    assert (playfair["verdict"], playfair["stem"], playfair["weight"]) == (CT.LEADS, "PlayfairDisplay[wght]", 700.0)
    from apps.ire.font_roles import catalogue
    unpinned = CT.read({"typography_signature": "Playfair Display Bold for 'Focus'"}, catalogue(),
                       name_role_pin=None)["name"]
    assert (unpinned["verdict"], unpinned["code"], unpinned["stem"]) == (
        CT.REFUSED, CT.VARIABLE_UNPINNED, "PlayfairDisplay[wght]")
    assert _typeface("Montserrat caps for the product name")["name"]["stem"] == "Montserrat-Regular"   # its static file
    assert _typeface("Raleway for the name")["name"]["stem"] == "Raleway-Light"          # the family's one granted file


def _led_doc(lead):
    from apps.ire.font_roles import CONCEPT_NAME, CONCEPT_TYPEFACE_KEY
    meta = {"typography_surface": "apps/ire/compose_container.py::compose_container_graph"}
    if lead:
        meta[CONCEPT_TYPEFACE_KEY] = {"stem": lead}
    return Document(title="t", page_w=80.0, page_h=40.0, metadata=meta, root=Group(name="R", role="decoration", children=[
        TextRun(name="product-name-hero", text="Focus", x=40.0, y=15.0, size_pt=12.0,
                color=Color.from_hex("#8B3A52"), font=CONCEPT_NAME, align="center"),
        TextRun(name="sheet-title", text="Sheet", x=40.0, y=30.0, size_pt=8.0,
                color=Color.from_hex("#3F2620"), font="bold", align="center")]))


def _span_faces(path):
    import pymupdf
    d = pymupdf.open(path)
    out = {}
    for b in d[0].get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for sp in line.get("spans", []):
                if sp["text"].strip():
                    out[sp["text"].strip()] = sp["font"]
    d.close()
    return out


def test_bh67c5_the_lead_prints_the_name_only_and_every_reader_sees_the_face_it_prints(tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.font_roles import CONCEPT_NAME, legacy_role_map, record_faces, resolve_document
    doc = _led_doc("Poppins-SemiBold")
    usage = {}
    emit_pdf_ai(doc, str(tmp_path / "led.ai"), usage_out=usage)
    faces = _span_faces(str(tmp_path / "led.ai"))
    display = resolve_document(_led_doc(None))["faces"]["display"][0]
    assert faces["Focus"].endswith("Poppins-SemiBold")                    # the concept's own granted face
    assert faces["Sheet"].endswith(display) and display != "Poppins-SemiBold"    # the furniture keeps the chain's
    # the measurers and the record read the face the emitter draws, never the chain's
    assert legacy_role_map(doc.metadata)[CONCEPT_NAME][0] == resolve_document(doc)["faces"][CONCEPT_NAME][0]
    row = next(r for r in record_faces(doc)[0] if r[0] == CONCEPT_NAME)
    assert row[2].endswith("Poppins-SemiBold.ttf")
    assert usage["outside_layer"] == [] and usage["reconciliation"]["agree"] is True
    # no lead: the same run prints in the display chain's face, exactly as a name always has
    emit_pdf_ai(_led_doc(None), str(tmp_path / "plain.ai"))
    assert _span_faces(str(tmp_path / "plain.ai"))["Focus"].endswith(display)


def test_bh68c_playfair_display_and_quicksand_draw_when_a_concept_names_them(tmp_path):
    """§BH68(c): "THE DISPLAY ROLE TAKES THE HEADING PIN — weight 700 for a variable face — unless the face declares its
    own display instance. Playfair Display and Quicksand draw when a concept names them." Read from the five granted
    variable faces' own fvar tables: none declares a display instance, so each draws at 700 — the name's lead records
    it, the emitter embeds that instance, and the record agrees with the ink. A weight the concept names beside a
    variable face is kept on the record; the layer draws the pin."""
    from apps.ire import concept_typeface as CT
    from apps.ire import font_roles as FR
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    cat = FR.catalogue()
    from apps.ire import font_pool
    cat = {k: e for k, e in cat.items() if e["origin"] != font_pool.ORIGIN}   # [D-D7-1] the pool beside the brand set
    assert {k for k, e in cat.items() if e["variable"]} == _VARIABLE | _VARIABLE_2026_10_02 | _VARIABLE_2026_10_15
    assert [k for k in _VARIABLE if cat[k]["display_instance"] is not None] == []
    for sig, stem, face in (("Playfair Display for 'Focus'", "PlayfairDisplay[wght]", "PlayfairDisplayRoman-Bold"),
                            ("Quicksand for the product name", "Quicksand[wght]", "Quicksand-Bold")):
        lead = _typeface(sig)["name"]
        assert (lead["verdict"], lead["stem"], lead["weight"]) == (CT.LEADS, stem, 700.0)
        assert FR.pinned_weight(stem, FR.CONCEPT_NAME) == 700.0
        usage = {}
        path = str(tmp_path / f"{face}.ai")
        emit_pdf_ai(_led_doc(stem), path, usage_out=usage)
        assert face in _embedded_faces(path)                       # the PDF span reports the name cut at 24 characters
        assert _span_faces(path)["Focus"].endswith(face[:24])
        assert usage["outside_layer"] == [] and usage["reconciliation"]["agree"] is True
    light = _typeface("Quicksand Light for the product name")["name"]
    assert (light["weight"], light["named_weight"]) == (700.0, 300)


def test_bh68c_a_face_that_declares_its_own_display_instance_draws_at_it(monkeypatch):
    """"... unless the face declares its own display instance." Where a variable face's fvar names a Display instance,
    the display role draws at that instance's weight, the lead records it, and every other role keeps its pin."""
    from apps.ire import concept_typeface as CT
    from apps.ire import font_roles as FR
    held = FR.catalogue()
    declared = dict(held, **{"PlayfairDisplay[wght]": dict(held["PlayfairDisplay[wght]"],
                                                          display_instance={"name": "Display Black", "wght": 900.0})})
    monkeypatch.setattr(FR, "catalogue", lambda: declared)
    assert FR.pinned_weight("PlayfairDisplay[wght]", FR.CONCEPT_NAME) == 900.0
    assert FR.pinned_weight("PlayfairDisplay[wght]", "heading") == 700.0
    assert FR.pinned_weight("Quicksand[wght]", FR.CONCEPT_NAME) == 700.0
    lead = CT.read({"typography_signature": "Playfair Display for 'Focus'"}, declared, name_role_pin=700.0)["name"]
    assert (lead["verdict"], lead["weight"]) == (CT.LEADS, 900.0) and "Display Black" in lead["why"]


def test_bh67c5_a_lead_outside_the_catalogue_is_never_drawn(tmp_path):
    """"No face outside the set is ever drawn": a lead naming a file the catalogue does not hold is no lead at all."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.font_roles import concept_lead, resolve_document
    doc = _led_doc("Didot-Regular")
    assert concept_lead(doc.metadata) is None
    emit_pdf_ai(doc, str(tmp_path / "outside.ai"))
    assert _span_faces(str(tmp_path / "outside.ai"))["Focus"].endswith(resolve_document(doc)["faces"]["display"][0])


# ---------------------------------------------------------------------------------------------------------------------
# THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
# testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." The mark drawn from an
# approved vector master, through this emitter — page 1 and the foil plate. Every master here is a SYNTHETIC fixture
# (apps/ire/tests/brand_mark_fixtures.py) handed straight to the node: the owner's trace is never placed by a test.
# ---------------------------------------------------------------------------------------------------------------------

def _mark_doc(svg, *, foil=False, x=20.0, y=20.0, w=70.0, page=(110.0, 70.0)):
    """A document holding the mark drawn from ``svg`` in the box a composer would give it — its height from the
    master's ink aspect — optionally carrying the lockup's foil, exactly as `container_finishes.apply` sets it."""
    from apps.ire import brand_mark as B
    from apps.ire.graph import Finish
    master = B.read_master(svg)
    box = (x, y, w, w * master.aspect)
    mark = B.mark_node("logo", master, *box)
    if foil:
        mark.finishes = [Finish(kind="foil", plate="FOIL_ROSE_GOLD", appearance=Color.from_hex("#C9A24B"))]
    doc = Document(page_w=page[0], page_h=page[1], title="mark",
                   root=Group(name="Artwork", role="artwork",
                              children=[Group(name="Container", role="product", children=[mark])]))
    return doc, master, box


_MARK_DPI = 600


def _coverage(path, page_index):
    """The page's ink as coverage 0..1 (alpha over a transparent ground), and pixels per mm."""
    import numpy as np
    with fitz.open(path) as pdf:
        pix = pdf[page_index].get_pixmap(dpi=_MARK_DPI, alpha=True)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        return arr[..., pix.n - 1].astype(float) / 255.0, _MARK_DPI / 25.4


def _user_to_mm(master, box, u, v):
    """A point of the master's user space -> document mm, through the ink box -> placed box map."""
    x0, y0, x1, y1 = master.bounds
    bx, by, bw, bh = box
    return bx + (u - x0) / (x1 - x0) * bw, by + (v - y0) / (y1 - y0) * bh


def _ink_at(cov, k, x_mm, y_mm):
    return float(cov[int(round(y_mm * k)), int(round(x_mm * k))])


def _box_ink(cov, k, box):
    bx, by, bw, bh = box
    region = cov[int(by * k):int((by + bh) * k), int(bx * k):int((bx + bw) * k)]
    return float(region.sum()), region.size


def test_bh69_a_document_with_no_mark_is_expanded_to_itself_and_a_marked_one_is_never_mutated():
    """Byte-identity starts here: the emitter's expansion hands back THE SAME OBJECT for a document that draws no mark
    from a master, so nothing it writes can move; for one that does, it expands a COPY, and the document every
    instrument reads keeps its box."""
    from apps.ire import brand_mark as B
    from apps.ire.tests import brand_mark_fixtures as FX
    plain = _doc()
    assert B.expand(plain) is plain
    marked, _master, _box = _mark_doc(FX.POTRACE_STYLE)
    expanded = B.expand(marked)
    assert expanded is not marked
    assert [n.type for n, _ in marked.walk() if n.name == "logo"] == ["asset_ref"]
    assert [(n.type, n.fill_rule) for n, _ in expanded.walk() if n.name == "logo"] == [("path", "nonzero")]


def test_bh69_a_mark_no_master_resolves_is_refused_by_name_and_nothing_is_written(tmp_path):
    """Never drawn as nothing: an AssetRef naming a master neither read in this process nor approved on file is
    refused by name, ahead of every byte (a fresh sha256, so no registry entry can answer it)."""
    import hashlib
    import os

    from apps.ire import brand_mark as B
    from apps.ire.graph import AssetRef
    ghost = AssetRef(name="logo", asset_id=B.ASSET_PREFIX + hashlib.sha256(b"a master no test ever read").hexdigest(),
                     x=10, y=10, w=40, h=10)
    doc = Document(page_w=60, page_h=30, title="ghost", root=Group(name="Artwork", children=[ghost]))
    out = str(tmp_path / "ghost.ai")
    with pytest.raises(B.MarkRefused) as refused:
        emit_pdf_ai(doc, out)
    assert refused.value.reason == B.CODE_UNRESOLVED
    assert not os.path.exists(out)


def test_bh69_the_foil_plate_is_cut_from_the_marks_own_outlines_never_its_box(tmp_path):
    """TRAP: `_draw_finish_plates` cuts a node with no segments as its BOX. The mark is expanded into its outlines
    BEFORE any plate is collected, so the FOIL plate's ink is the mark's page-1 ink — and far below its box."""
    from apps.ire import container_finishes as F
    from apps.ire.tests import brand_mark_fixtures as FX
    doc, _master, box = _mark_doc(FX.POTRACE_STYLE, foil=True)
    usage = {}
    out = emit_pdf_ai(doc, str(tmp_path / "foil.ai"), usage_out=usage)
    plates = usage[F.SCHEMA]
    assert plates["pages"] == 2
    assert [(p["plate"], p["kind"], p["items"]) for p in plates["plates"]] == [("FOIL_ROSE_GOLD", "foil", ["logo"])]
    page1, k = _coverage(out, 0)
    plate, _k = _coverage(out, 1)
    ink1, area = _box_ink(page1, k, box)
    inkp, _area = _box_ink(plate, k, box)
    assert ink1 > 0 and abs(inkp - ink1) / ink1 < 0.01
    assert inkp / area < 0.5                        # the fixture inks 44.8 % of its box; the box would be 100 %


def test_bh69_the_marks_counters_stay_holes_on_page_1_and_on_the_plate(tmp_path):
    """The counters of the fixture's block and the hole of its ring (potrace's own convention: every hole runs against
    its outline) stay holes, on the page and on the plate; the ink around them is ink."""
    from apps.ire.tests import brand_mark_fixtures as FX
    doc, master, box = _mark_doc(FX.POTRACE_STYLE, foil=True)
    out = emit_pdf_ai(doc, str(tmp_path / "holes.ai"))
    for page in (0, 1):
        cov, k = _coverage(out, page)
        for u, v in FX.POTRACE_HOLES:
            assert _ink_at(cov, k, *_user_to_mm(master, box, u, v)) == 0.0, (page, u, v)
        for u, v in FX.POTRACE_INKED:
            assert _ink_at(cov, k, *_user_to_mm(master, box, u, v)) == 1.0, (page, u, v)


def test_bh69_the_mark_fills_by_the_nonzero_rule_its_master_declares_and_an_undeclared_path_does_not(tmp_path):
    """TRAP: reportlab fills EVEN-ODD by default (canvas.py:407). An outline nested in another that runs the SAME way
    is filled by the nonzero rule an SVG master declares and cut out by even-odd. The mark is drawn — and plated — by
    its master's rule; the control, the same outlines on a Path that declares none, draws the hole every path before
    the field drew."""
    from apps.ire import brand_mark as B
    from apps.ire.graph import Path
    from apps.ire.tests import brand_mark_fixtures as FX
    doc, master, box = _mark_doc(FX.SAME_DIRECTION, foil=True, x=20.0, y=10.0, w=40.0)
    out = emit_pdf_ai(doc, str(tmp_path / "nonzero.ai"))
    centre = _user_to_mm(master, box, 30.0, 30.0)                    # the inner square's centre
    for page in (0, 1):
        cov, k = _coverage(out, page)
        assert _ink_at(cov, k, *centre) == 1.0, page
    control = Document(page_w=110, page_h=70, title="control", root=Group(name="Artwork", children=[
        Path(name="control", segments=B.placed_segments(master, *box), fill=SolidFill(color=Color.from_hex("#000000")))]))
    cov, k = _coverage(emit_pdf_ai(control, str(tmp_path / "evenodd.ai")), 0)
    assert _ink_at(cov, k, *centre) == 0.0


def test_bh69_the_dropper_draws_the_mark_in_the_masters_own_black_and_the_role_map_does_not_recolour_it(tmp_path):
    """The mark prints in its master's one flat fill — #000000, which is also every opaque pixel of the live PNG it
    replaces — through the colour layer on a sheet that DECLARES a role map: #000000 is no role, so no brand colour
    is substituted for it."""
    import numpy as np

    from apps.ire import brand_mark as B
    from apps.ire.compose_dropper import compose_dropper_sheet
    from apps.ire.tests import brand_mark_fixtures as FX
    from apps.ire.tests.test_wiv_leading_comparison import _BACK_ZONE, _FRONT_ZONE, _GEOMETRY
    from apps.ire import colour_roles as CR
    master = B.read_master(FX.POTRACE_STYLE)
    doc = compose_dropper_sheet(_GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE], reference_path=None, logo_path=None,
                                product_name="Rose Damascena", sku="X", back_sections=[{"heading": "P", "text": "x"}],
                                revision_status="TEST", logo_master=master)
    assert "#000000" not in CR.role_map(doc)
    mark = next(n for n, _ in doc.walk() if n.name == "logo")
    box = (mark.x, mark.y, mark.w, mark.h)
    out = emit_pdf_ai(doc, str(tmp_path / "dropper.ai"))
    with fitz.open(out) as pdf:
        pix = pdf[0].get_pixmap(dpi=_MARK_DPI, alpha=False)
        rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    k = _MARK_DPI / 25.4
    for u, v in FX.POTRACE_INKED:
        x_mm, y_mm = _user_to_mm(master, box, u, v)
        assert tuple(int(c) for c in rgb[int(round(y_mm * k)), int(round(x_mm * k))][:3]) == (0, 0, 0), (u, v)


def test_a1_each_line_prints_in_the_granted_face_its_concept_letters_it_in_and_both_files_agree(tmp_path):
    """[His goal after the pitch page, 2026-10-15, A (1): "set each line in the closest granted face with the same
    weight, spacing, size and colour."] A line naming its own face (``line-face:<stem>@<wght>``) prints in that face —
    a variable face at exactly that weight — on a themed and on an exempt document alike; the layered file sets it in
    the same face; a face that does not verify prints the line in the display chain's face, never drops it."""
    from apps.ire import font_roles as FR
    from apps.ire.emitters import native_ai
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    serif, condensed = FR.line_face_key("PlayfairDisplay[wght]", 700), FR.line_face_key("BarlowCondensed-Medium", 500)
    missing = FR.line_face_key("NoSuchFace-Regular", 400)

    def doc(meta):
        return Document(title="t", page_w=80.0, page_h=40.0, metadata=meta, root=Group(name="R", role="decoration",
                        children=[TextRun(name="a", text="Velvet", x=40.0, y=10.0, size_pt=12.0,
                                          color=Color.from_hex("#8B3A52"), font=serif, align="center"),
                                  TextRun(name="b", text="SERUM", x=40.0, y=20.0, size_pt=9.0,
                                          color=Color.from_hex("#3F2620"), font=condensed, align="center"),
                                  TextRun(name="c", text="Kept", x=40.0, y=30.0, size_pt=9.0,
                                          color=Color.from_hex("#3F2620"), font=missing, align="center")]))
    themed = doc({"typography_surface": "apps/ire/compose_container.py::compose_container_graph"})
    emit_pdf_ai(themed, str(tmp_path / "themed.ai"))
    faces = _span_faces(str(tmp_path / "themed.ai"))
    assert faces["Velvet"].split("+")[-1].startswith("PlayfairDisplayRoman-Bol")    # the PDF cuts the name short
    assert faces["SERUM"].endswith("BarlowCondensed-Medium")
    assert "Kept" in faces                                       # never dropped: the display chain's face
    emit_pdf_ai(doc({}), str(tmp_path / "exempt.ai"))
    assert "Playfair" in _span_faces(str(tmp_path / "exempt.ai"))["Velvet"]
    fonts = native_ai.document_fonts(themed)
    assert "Playfair" in native_ai._font(serif, fonts) and native_ai._font(condensed, fonts) == "BarlowCondensed-Medium"
    assert FR.parse_line_face(serif) == ("PlayfairDisplay[wght]", 700.0) and FR.base_role(serif) == "display"
