"""Tests for svg_validator.validate_svg()."""
from __future__ import annotations

import os

import pytest

from apps.dielines.exporters.svg_exporter import export_svg
from apps.dielines.exporters.svg_validator import validate_svg
from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.validators.schema import DielineInputJSON


def _make_coords(w=28, d=28, h=120):
    p = DielineInputJSON(
        template="straight_tuck_end_carton",
        unit="mm",
        dimensions={"width_mm": w, "depth_mm": d, "height_mm": h},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0},
        metadata={"product_name": "Test", "product_type": "test"},
    )
    return calculate_straight_tuck_end(p)


def _make_svg(coords, tmp_path) -> str:
    original = os.getcwd()
    os.chdir(tmp_path)
    try:
        return export_svg(coords, "valtest")
    finally:
        os.chdir(original)


class TestValidatorHappyPath:
    def test_valid_svg_has_no_errors(self, tmp_path):
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        errors = validate_svg(svg, coords)
        assert errors == [], f"unexpected errors: {errors}"


class TestValidatorCatchesMissingLayers:
    def test_missing_cut_lines(self, tmp_path):
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        broken = svg.replace('id="cut-lines"', 'id="DELETED-cut-lines"')
        errors = validate_svg(broken, coords)
        assert any("cut-lines" in e for e in errors)

    def test_missing_bleed(self, tmp_path):
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        broken = svg.replace('id="bleed"', 'id="DELETED-bleed"')
        errors = validate_svg(broken, coords)
        assert any("bleed" in e for e in errors)

    def test_missing_fold_lines(self, tmp_path):
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        broken = svg.replace('id="fold-lines"', 'id="DELETED-fold-lines"')
        errors = validate_svg(broken, coords)
        assert any("fold-lines" in e for e in errors)

    def test_missing_safe_area(self, tmp_path):
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        broken = svg.replace('id="safe-area"', 'id="DELETED-safe-area"')
        errors = validate_svg(broken, coords)
        assert any("safe-area" in e for e in errors)

    def test_text_element_rejected(self, tmp_path):
        # The SVG must contain no <text>; validator rejects any.
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        broken = svg.replace(
            '</svg>',
            '<text x="0" y="0">should not be here</text></svg>',
        )
        errors = validate_svg(broken, coords)
        assert any("text" in e.lower() for e in errors)


class TestValidatorViewBox:
    def test_malformed_viewbox(self, tmp_path):
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        import re
        broken = re.sub(r'viewBox="[^"]+"', 'viewBox="not a viewbox"', svg)
        errors = validate_svg(broken, coords)
        assert any("viewBox" in e for e in errors)

    def test_cut_bounds_viewbox_rejected_when_bleed_is_clipped(self, tmp_path):
        coords = _make_coords()
        svg = _make_svg(coords, tmp_path)
        import re
        x0 = coords.derived["x0"]
        broken_viewbox = (
            f'viewBox="{x0:.4f} 0 {coords.flat_width_mm:.4f} '
            f'{coords.flat_height_mm:.4f}"'
        )
        broken = re.sub(r'viewBox="[^"]+"', broken_viewbox, svg)
        errors = validate_svg(broken, coords)
        assert any("contain bleed" in e for e in errors)


class TestValidatorParseFailure:
    def test_invalid_xml_returns_error(self):
        coords = _make_coords()
        errors = validate_svg("<svg><not closed", coords)
        assert any("not valid XML" in e for e in errors)
