"""Milestone 9.5 — prepress correctness of the CMYK production PDF.

reportlab compresses page content streams but writes colorspace objects,
page-box entries and font dictionaries in plain object syntax, so byte
scans of our own output are reliable.
"""
from __future__ import annotations

import os
import re

import pytest

from apps.dielines.exporters.counter_display_files import carton_ai_from_pdf
from apps.dielines.exporters.counter_display_files import write_carton_pdf
from apps.dielines.exporters.svg_validator import (
    validate_ai,
    validate_production_pdf,
)
from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.validators.schema import DielineInputJSON


@pytest.fixture(scope="module")
def coords():
    params = DielineInputJSON(
        template="straight_tuck_end_carton",
        unit="mm",
        dimensions={"width_mm": 28, "depth_mm": 28, "height_mm": 120},
        print_settings={},
        construction={},
        metadata={"product_name": "PDF test", "product_type": "test"},
    )
    return calculate_straight_tuck_end(params)


@pytest.fixture()
def pdf_bytes_and_path(coords, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rel = write_carton_pdf(
        coords, "pdftest",
        product_name="PDF test", product_type="test",
        bleed_mm=3.0, safe_margin_mm=4.0, glue_tab_mm=10.0,
    )
    path = tmp_path / rel
    return path.read_bytes(), str(path)


class TestSpotPlates:
    def test_die_separations_present(self, pdf_bytes_and_path):
        data, _ = pdf_bytes_and_path
        assert b"/Separation" in data
        assert b"/CutContour" in data
        assert b"/Crease" in data

    def test_registration_marks_use_all_separation(self, pdf_bytes_and_path):
        """The /All registration colorant must exist as a Separation —
        a plain 100/100/100/100 process color would leave the marks off
        the CutContour and Crease plates."""
        data, _ = pdf_bytes_and_path
        assert re.search(rb"/Separation\s*/All[^A-Za-z]", data), (
            "registration marks are not in the /All separation colorant"
        )


def _font_graph(path):
    """(text-span font names, [(descriptor FontName, FontFile2 stream
    bytes)]) — walked over the whole xref table, never pinned to object
    numbers."""
    import pymupdf

    doc = pymupdf.open(path)
    spans: set = set()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    spans.add(span["font"])
    descriptors = []
    for x in range(1, doc.xref_length()):
        obj = doc.xref_object(x, compressed=True) or ""
        if "/FontDescriptor" in obj and "/FontName" in obj:
            name = re.search(r"/FontName\s*/(?:[A-Z]{6}\+)?([A-Za-z0-9-]+)",
                             obj)
            program = re.search(r"/FontFile2 (\d+) 0 R", obj)
            stream = (doc.xref_stream(int(program.group(1)))
                      if program else None)
            descriptors.append((name.group(1) if name else "?",
                                len(stream or b"")))
    return spans, descriptors


class TestFonts:
    """The production PDF must CARRY its own font program (print shops
    reject unembedded non-standard fonts). Deterministic on every platform:
    the fonts are the repo-bundled Noto files production itself prefers —
    no system font, no Linux path, no skip."""

    def test_bundled_noto_fonts_are_embedded(self, pdf_bytes_and_path):
        data, path = pdf_bytes_and_path
        assert b"/FontFile2" in data          # embedded TrueType program(s)
        spans, descriptors = _font_graph(path)
        # both faces the exporter resolves are actually USED by page text —
        # and the text is NOT silently falling back to unembedded Helvetica
        assert spans == {"NotoSans-Regular", "NotoSans-Bold"}
        by_name = {n: size for n, size in descriptors}
        for face in ("NotoSans-Regular", "NotoSans-Bold"):
            assert face in by_name, f"{face} has no FontDescriptor"
            assert by_name[face] > 1000, (
                f"{face} FontFile2 stream is missing or empty — the font "
                "program is not embedded")

    def test_helvetica_fallback_is_deterministic(self, coords, tmp_path,
                                                 monkeypatch):
        """The no-bundled-font branch, triggered by injection — never by
        the machine's font inventory. monkeypatch restores every patched
        attribute afterwards."""
        from apps.dielines.exporters import counter_display_files as pp

        monkeypatch.setattr(pp, "_register_ttf", lambda name, path: False)
        monkeypatch.setattr(pp, "_fonts_cache", None)
        monkeypatch.setattr(pp, "_ar_font_cache", False)
        # resolution reports the fallback pair, not a bundled font
        assert pp._resolve_fonts() == ("Helvetica", "Helvetica-Bold")
        monkeypatch.chdir(tmp_path)
        rel = write_carton_pdf(
            coords, "fallbacktest", product_name="PDF test",
            product_type="test", bleed_mm=3.0, safe_margin_mm=4.0,
            glue_tab_mm=10.0)
        path = tmp_path / rel
        data = path.read_bytes()
        assert b"/FontFile2" not in data      # nothing embedded — explicit
        spans, descriptors = _font_graph(str(path))
        assert spans and spans <= {"Helvetica", "Helvetica-Bold"}, (
            "fallback text must use the standard-14 Helvetica faces")
        assert all(size == 0 for _, size in descriptors), (
            "the explicit fallback mode must not carry font programs")


class TestPageBoxes:
    def test_trim_and_bleed_boxes_present(self, pdf_bytes_and_path):
        data, _ = pdf_bytes_and_path
        assert b"/TrimBox" in data
        assert b"/BleedBox" in data


class TestValidator:
    def test_validate_production_pdf_passes(self, pdf_bytes_and_path):
        _, path = pdf_bytes_and_path
        assert validate_production_pdf(path) == []

    def test_validate_production_pdf_rejects_plain_pdf(self, tmp_path):
        fake = tmp_path / "plain.pdf"
        fake.write_bytes(b"%PDF-1.4\n%%EOF\n")
        errors = validate_production_pdf(str(fake))
        assert any("CutContour" in e for e in errors)
        assert any("Crease" in e for e in errors)
        assert any("TrimBox" in e for e in errors)

    def test_validate_production_pdf_missing_file(self, tmp_path):
        errors = validate_production_pdf(str(tmp_path / "nope.pdf"))
        assert errors and "unreadable" in errors[0]

    def test_validator_rejects_unembedded_truetype(self, tmp_path):
        """A /TrueType reference without /FontFile2 must never be called
        production-ready (the font-embedding validator gap)."""
        fake = tmp_path / "unembedded.pdf"
        fake.write_bytes(
            b"%PDF-1.4 /Separation /CutContour /Crease /All /TrimBox "
            b"/BleedBox /TrueType\n%%EOF\n")
        errors = validate_production_pdf(str(fake))
        assert any("embedded" in e for e in errors)

    def test_validator_accepts_helvetica_fallback_output(self, coords,
                                                         tmp_path,
                                                         monkeypatch):
        """The explicit standard-14 fallback stays valid — the embedding
        check targets unembedded TrueType references, not policy."""
        from apps.dielines.exporters import counter_display_files as pp
        monkeypatch.setattr(pp, "_register_ttf", lambda name, path: False)
        monkeypatch.setattr(pp, "_fonts_cache", None)
        monkeypatch.setattr(pp, "_ar_font_cache", False)
        monkeypatch.chdir(tmp_path)
        rel = write_carton_pdf(
            coords, "fallbackvalid", product_name="PDF test",
            product_type="test", bleed_mm=3.0, safe_margin_mm=4.0,
            glue_tab_mm=10.0)
        assert validate_production_pdf(str(tmp_path / rel)) == []


class TestAiFromProductionPdf:
    def test_ai_copy_carries_spot_plates(self, pdf_bytes_and_path, tmp_path):
        _, path = pdf_bytes_and_path
        rel = carton_ai_from_pdf(path, "pdftest")
        ai_path = tmp_path / rel
        data = ai_path.read_bytes()
        assert data[:4] == b"%PDF"
        assert b"/CutContour" in data and b"/Crease" in data
        assert validate_ai(str(ai_path)) is True
        assert validate_ai(str(ai_path), require_spot_colors=True) is True

    def test_ai_from_missing_pdf_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            carton_ai_from_pdf(str(tmp_path / "missing.pdf"), "x")

    def test_preview_grade_ai_fails_strict_check(self, tmp_path):
        """An RGB preview .ai (no spot plates) passes the basic header
        check but fails the strict factory-grade check by design."""
        fake = tmp_path / "preview.ai"
        fake.write_bytes(b"%PDF-1.4\nno spot plates here\n%%EOF\n")
        assert validate_ai(str(fake)) is True
        assert validate_ai(str(fake), require_spot_colors=True) is False


class TestGeometryNotesRow:
    def test_export_succeeds_with_notes(self, tmp_path, monkeypatch):
        """A clamped carton (15×35×90) carries derived notes — the export
        must render its extra 'Geometry notes' spec row without error."""
        params = DielineInputJSON(
            template="straight_tuck_end_carton",
            unit="mm",
            dimensions={"width_mm": 15, "depth_mm": 35, "height_mm": 90},
            print_settings={},
            construction={},
            metadata={"product_name": "Clamped", "product_type": "test"},
        )
        coords = calculate_straight_tuck_end(params)
        assert coords.derived["notes"]
        monkeypatch.chdir(tmp_path)
        rel = write_carton_pdf(coords, "clamped")
        assert (tmp_path / rel).read_bytes()[:4] == b"%PDF"
