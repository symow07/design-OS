"""Trilingual sticker rendering (2026-07-07)."""
from __future__ import annotations

import hashlib

import pytest

from apps.dielines.exporters.info_panel import (
    _fit_sticker_blocks,
    build_sticker_blocks,
    has_info_content,
)
from apps.dielines.exporters.text_intl import has_ar_support, shape_ar, wrap_ar
from apps.dielines.tests.test_design_preview import (  # reuse fixtures/helpers
    _PNG,
    _inflated_pdf_streams,
)
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON

_AR_DESC = "باليت ظلال عيون من تسع درجات دافئة محايدة."
_AR_WARN = "للاستعمال الخارجي فقط. يحفظ بعيدا عن الأطفال."

_INFO = {
    "product_name": "Amber Hour Eyeshadow Palette",
    "description": "A 9-shade warm neutral eyeshadow palette with velvet mattes.",
    "ingredients": "MICA, TALC, CI 77491, TOCOPHERYL ACETATE.",
    "how_to_use": "Apply with a brush or fingertip.",
    "warnings": "For external use only. Keep away from children.",
    "net_weight": "9 x 1.5 g e 0.05 oz.",
    "item_no": "EP-3109-A",
    "barcode_ean": "5061030633823",
    "qr_url": "https://www.bbrose.com/amber-hour",
    "regulatory_text": "MADE IN CHINA BY SUPPLIER: YIWU YIBIN TRADING.",
    "translations": {
        "es": {
            "product_name": "Paleta de Sombras Amber Hour",
            "description": "Paleta de sombras de 9 tonos neutros cálidos.",
            "how_to_use": "Aplicar con brocha o con la yema del dedo.",
            "warnings": "Solo para uso externo. Mantener alejado de los niños.",
        },
        "ar": {
            "product_name": "باليت ظلال العيون آمبر آور",
            "description": _AR_DESC,
            "warnings": _AR_WARN,
        },
    },
}


@pytest.fixture
def coords():
    return calculate_dieline(DielineInputJSON(
        template="straight_tuck_end_carton", unit="mm",
        dimensions={"width_mm": 105, "depth_mm": 20, "height_mm": 150},
        print_settings={}, construction={},
        metadata={"product_name": "T", "product_type": "t"},
    ))


@pytest.fixture
def artwork(tmp_path):
    p = tmp_path / "art.png"
    p.write_bytes(_PNG)
    return str(p)


class TestTextIntl:
    def test_shape_ar_produces_presentation_forms(self):
        shaped = shape_ar("العربية")
        assert shaped != "العربية"          # reshaped + reordered
        assert shaped                        # never empty

    def test_wrap_ar_wraps_and_keeps_line_count_sane(self):
        lines = wrap_ar(_AR_DESC, "Helvetica", 8, 60.0)
        assert len(lines) >= 2
        assert all(lines)

    def test_has_ar_support(self):
        assert has_ar_support("NotoNaskhArabic") is True
        assert has_ar_support(None) is False

    def test_split_script_runs_keeps_latin_brands(self):
        from apps.dielines.exporters.text_intl import split_script_runs
        runs = split_script_runs("غلوس BBROSE ناعم")
        latin = [t for is_ar, t in runs if not is_ar]
        assert any("BBROSE" in t for t in latin)
        arabic = [t for is_ar, t in runs if is_ar]
        assert len(arabic) == 2


class TestHisArabicOnTheBack:
    """[His review of 119, 2026-10-05, point 6: "Back-panel Arabic: where my brief gives the Arabic, use my words
    exactly (with the shadda)."] 119's back printed its title in English alone: the translation's Arabic title was
    "Rose Glaze Lip Gloss", English letters the Arabic face cannot draw; his brief writes ملمّع الشفاه روز جليز."""

    def _drawn(self, tmp_path, info, keep):
        import unicodedata

        import fitz

        from apps.ire.emitters.pdf_ai import ARABIC_MARKS_KEY, emit_pdf_ai
        from apps.ire.graph import Document, Group, StickerBridge
        doc = Document(page_w=80, page_h=150, metadata={ARABIC_MARKS_KEY: True} if keep else {},
                       root=Group(name="r", children=[StickerBridge(name="sticker", x=5, y=5, w=70, h=140, info=info)]))
        out = emit_pdf_ai(doc, str(tmp_path / ("kept.ai" if keep else "as_before.ai")))
        return unicodedata.normalize("NFKC", fitz.open(out)[0].get_text())

    def test_his_arabic_name_titles_the_back_with_its_shadda(self, tmp_path):
        from apps.dielines.exporters.info_panel import title_ar
        his = "ملمّع الشفاه روز جليز"
        info = dict(_INFO, product_name="Rose Glaze Lip Gloss", product_name_ar=his)
        assert title_ar(info) == his                                    # his words, never the translation's
        assert "\u0651" in self._drawn(tmp_path, info, keep=True)       # its shadda drawn
        assert "\u0651" not in self._drawn(tmp_path, info, keep=False)  # a document that keeps no marks: as before

    def test_a_translation_in_english_letters_is_never_drawn_as_the_arabic_title(self):
        from apps.dielines.exporters.info_panel import title_ar
        info = dict(_INFO, translations=dict(_INFO["translations"], ar={"product_name": "Rose Glaze Lip Gloss"}))
        assert title_ar(info) == ""
        assert title_ar(_INFO) == _INFO["translations"]["ar"]["product_name"]   # an Arabic translation, where no words of his

    def test_his_brief_gives_the_arabic_name(self):
        from types import SimpleNamespace

        from apps.pipeline.targets.container import arabic_name_for
        task = SimpleNamespace(product=None, task_text="Rose Glaze Lip Gloss\nArabic name: ملمّع الشفاه روز جليز\nSize: 8 ml")
        assert arabic_name_for(task) == ("ملمّع الشفاه روز جليز", "the brief's Arabic name")
        record = SimpleNamespace(product=SimpleNamespace(name_ar="ملمع", product_type=""), task_text="Arabic name: x")
        assert arabic_name_for(record) == ("ملمع", "the product record's Arabic name")
        assert arabic_name_for(SimpleNamespace(product=None, task_text="no Arabic here")) == (None, None)

