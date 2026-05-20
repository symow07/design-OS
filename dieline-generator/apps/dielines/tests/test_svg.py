"""SVG output tests for the parametric STE engine."""
from __future__ import annotations

import os
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from apps.dielines.api.payloads import build_generate_success_payload
from apps.dielines.exporters.ai_exporter import export_ai
from apps.dielines.exporters.svg_exporter import export_svg
from apps.dielines.exporters.svg_validator import validate_ai
from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.validators.schema import DielineInputJSON


_SVG_NS = {
    "svg": "http://www.w3.org/2000/svg",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
}


def _make_params(w: float, d: float, h: float) -> DielineInputJSON:
    return DielineInputJSON(
        template="straight_tuck_end_carton",
        unit="mm",
        dimensions={"width_mm": w, "depth_mm": d, "height_mm": h},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0},
        metadata={"product_name": "Test", "product_type": "test"},
    )


PRODUCTS = [
    ("Eyeliner",  20, 20, 130),
    ("Reference", 28, 28, 120),
    ("Mascara",   30, 30, 140),
    ("LipGloss",  15, 15, 90),
]


def _parse(svg_text: str) -> ET.Element:
    clean = re.sub(r"<![^>]*>", "", svg_text)
    return ET.fromstring(clean)


def _group(root: ET.Element, gid: str) -> ET.Element:
    return next(
        g for g in root.findall(".//svg:g", _SVG_NS) if g.get("id") == gid
    )


@pytest.fixture
def svg_artifact(tmp_path, request):
    name, w, d, h = request.param
    job_id = f"{name}-{uuid.uuid4().hex[:6]}"
    original = os.getcwd()
    os.chdir(tmp_path)
    try:
        coords = calculate_straight_tuck_end(_make_params(w, d, h))
        svg = export_svg(coords, job_id)
    finally:
        os.chdir(original)
    return svg, tmp_path / "exports" / f"{job_id}.svg", coords


@pytest.mark.parametrize("svg_artifact", PRODUCTS, indirect=True)
class TestSVGStructure:
    def test_xml_declaration_present(self, svg_artifact):
        svg, _, _ = svg_artifact
        assert svg.startswith('<?xml version="1.0"')

    def test_doctype_present(self, svg_artifact):
        svg, _, _ = svg_artifact
        assert "<!DOCTYPE svg" in svg

    def test_inkscape_namespace(self, svg_artifact):
        svg, _, _ = svg_artifact
        assert "xmlns:inkscape" in svg

    def test_sodipodi_namespace(self, svg_artifact):
        svg, _, _ = svg_artifact
        assert "xmlns:sodipodi" in svg

    def test_required_layers_present(self, svg_artifact):
        svg, _, _ = svg_artifact
        root = _parse(svg)
        ids = {g.get("id") for g in root.findall(".//svg:g", _SVG_NS)}
        for required in ("bleed", "cut-lines", "fold-lines", "safe-area"):
            assert required in ids, f"missing layer: {required}"

    def test_required_layers_have_illustrator_labels(self, svg_artifact):
        svg, _, _ = svg_artifact
        root = _parse(svg)
        labels = {
            g.get("id"): g.get("{http://www.inkscape.org/namespaces/inkscape}label")
            for g in root.findall(".//svg:g", _SVG_NS)
        }
        assert labels["bleed"] == "Bleed"
        assert labels["cut-lines"] == "Cut Lines"
        assert labels["fold-lines"] == "Fold Lines"
        assert labels["safe-area"] == "Safe Area"

    def test_no_panel_labels_group(self, svg_artifact):
        svg, _, _ = svg_artifact
        root = _parse(svg)
        ids = {g.get("id") for g in root.findall(".//svg:g", _SVG_NS)}
        assert "panel-labels" not in ids

    def test_no_text_elements(self, svg_artifact):
        svg, _, _ = svg_artifact
        root = _parse(svg)
        texts = root.findall(".//svg:text", _SVG_NS)
        assert len(texts) == 0, f"SVG must contain no <text> elements, found {len(texts)}"

    def test_cut_layer_has_component_and_stadium_paths(self, svg_artifact):
        """8 component paths + 2 stadium cutouts."""
        svg, _, _ = svg_artifact
        cut = _group(_parse(svg), "cut-lines")
        paths = cut.findall("svg:path", _SVG_NS)
        assert len(paths) == 10, f"expected 10 paths, got {len(paths)}"
        ids = {p.get("id") for p in paths}
        expected = {
            "main-body", "glue-tab",
            "top-back-tuck",
            "top-left-dust", "top-right-dust",
            "bottom-front-tuck",
            "bottom-left-dust", "bottom-right-dust",
            "top-back-slit", "bottom-front-slit",
        }
        assert ids == expected, f"missing: {expected - ids}, extra: {ids - expected}"

    def test_bleed_layer_has_path(self, svg_artifact):
        svg, _, _ = svg_artifact
        bleed = _group(_parse(svg), "bleed")
        assert len(bleed.findall("svg:path", _SVG_NS)) == 1

    def test_six_fold_lines(self, svg_artifact):
        svg, _, _ = svg_artifact
        fold = _group(_parse(svg), "fold-lines")
        assert len(fold.findall("svg:line", _SVG_NS)) == 6

    def test_slits_are_polygon_holes(self, svg_artifact):
        """Two friction slits = 2 interior rings."""
        _, _, coords = svg_artifact
        assert len(coords.cut_polygon.interiors) == 2

    def test_file_written(self, svg_artifact):
        _, path, _ = svg_artifact
        assert path.exists()


def test_well_formed_xml_for_all_products(tmp_path):
    original = os.getcwd()
    os.chdir(tmp_path)
    try:
        for name, w, d, h in PRODUCTS:
            coords = calculate_straight_tuck_end(_make_params(w, d, h))
            svg = export_svg(coords, name)
            _parse(svg)  # raises if malformed
    finally:
        os.chdir(original)


def test_ai_export_for_reference_product(tmp_path):
    original = os.getcwd()
    os.chdir(tmp_path)
    try:
        coords = calculate_straight_tuck_end(_make_params(28, 28, 120))
        svg = export_svg(coords, "ai-reference")
        ai_path = export_ai(svg, "ai-reference")
        assert Path(ai_path).exists()
        assert Path(ai_path).stat().st_size > 0
        assert validate_ai(ai_path)
    finally:
        os.chdir(original)


def test_generate_success_payload_contains_ai_file():
    coords = calculate_straight_tuck_end(_make_params(28, 28, 120))
    payload = build_generate_success_payload(
        job_id="job-123",
        svg_path="/exports/job-123.svg",
        ai_path="/exports/job-123.ai",
        coords=coords,
        warnings=[],
    )
    assert payload["ai_file"] == "/exports/job-123.ai"
