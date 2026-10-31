"""Milestone 12.1 — carton-style matrix.

Covers the StyleBase dispatch (``calculate_dieline``), the two provisional
styles (reverse tuck end, tuck-top auto bottom), per-style schema relaxation,
and the sheet-bounds invariant for every style incl. non-square products.
The locked STE reference geometry is guarded separately by
test_reference_regression.py.
"""
from __future__ import annotations

import pytest

from apps.dielines.geometry import engine
from apps.dielines.geometry.styles import available_styles, is_supported
from apps.dielines.validators.schema import DielineInputJSON

_EPS = 0.01


def _params(template, w, d, h, **construction):
    return DielineInputJSON(
        template=template,
        unit="mm",
        dimensions={"width_mm": w, "depth_mm": d, "height_mm": h},
        print_settings={},
        construction=construction or {},
        metadata={"product_name": "T", "product_type": "t"},
    )


def _assert_on_sheet(coords):
    minx, miny, maxx, maxy = coords.cut_polygon.bounds
    assert coords.cut_polygon.is_valid
    assert minx >= -_EPS and miny >= -_EPS
    assert maxx <= coords.flat_width_mm + _EPS
    assert maxy <= coords.flat_height_mm + _EPS
    # DielineCoordinates.validate enforces bleed > cut > safe.
    coords.validate()


# Tuck styles keep the STE constraints (H>W, H>D, D<=2.5W). Auto-bottom
# relaxes the H ordering so compacts/palettes fold.
_TUCK_MATRIX = [
    (28, 28, 120),   # square reference proportion
    (15, 35, 90),    # non-square, D within 2.5W
    (40, 20, 100),   # wide, shallow
    (20, 45, 90),    # D = 2.25W (near the ratio cap)
]
_AUTO_MATRIX = _TUCK_MATRIX + [
    (200, 150, 80),  # compact: H < W (impossible for a tuck carton)
    (120, 100, 60),  # shallow palette-style
]


class TestStyleMatrix:
    @pytest.mark.parametrize("w,d,h", _TUCK_MATRIX)
    @pytest.mark.parametrize("template", [
        "straight_tuck_end_carton", "reverse_tuck_end_carton",
    ])
    def test_tuck_styles_on_sheet(self, template, w, d, h):
        _assert_on_sheet(engine.calculate_dieline(_params(template, w, d, h)))

    @pytest.mark.parametrize("w,d,h", _AUTO_MATRIX)
    def test_auto_bottom_on_sheet(self, w, d, h):
        _assert_on_sheet(
            engine.calculate_dieline(
                _params("tuck_top_auto_bottom_carton", w, d, h)
            )
        )


class TestDispatch:
    def test_calculate_dieline_matches_named_functions(self):
        p = _params("straight_tuck_end_carton", 28, 28, 120)
        a = engine.calculate_dieline(p)
        b = engine.calculate_straight_tuck_end(p)
        assert list(a.cut_polygon.exterior.coords) == list(b.cut_polygon.exterior.coords)

    def test_unknown_template_raises(self):
        # Pydantic rejects unknown templates before the engine is reached, so
        # the engine dispatch guard is exercised with a hand-built stand-in.
        with pytest.raises(ValueError, match="unknown carton style"):
            engine.calculate_dieline(
                type("P", (), {"template": "does_not_exist"})()
            )


class TestReverseTuckLayout:
    def test_reverse_swaps_tuck_panels(self):
        rev = engine.calculate_dieline(
            _params("reverse_tuck_end_carton", 28, 28, 120)
        )
        ids = {c[0] for c in rev.components}
        assert "top-front-tuck" in ids       # reversed vs STE's top-back-tuck
        assert "bottom-back-tuck" in ids      # reversed vs STE's bottom-front-tuck
        assert rev.derived["provisional"] is True
        assert rev.derived["top_tuck_panel"] == "front"


class TestAutoBottomLayout:
    def test_auto_bottom_has_lock_flaps_not_bottom_tuck(self):
        auto = engine.calculate_dieline(
            _params("tuck_top_auto_bottom_carton", 60, 50, 100)
        )
        ids = {c[0] for c in auto.components}
        assert {"bottom-back-lock", "bottom-front-lock",
                "bottom-sl-lock", "bottom-sr-lock"} <= ids
        assert not any("tuck" in i and i.startswith("bottom") for i in ids)
        assert auto.derived["bottom_mode"] == "auto_lock"
        assert auto.derived["auto_bottom_height_mm"] is not None


class TestSchemaRelaxation:
    def test_tuck_style_rejects_h_le_w(self):
        with pytest.raises(ValueError):
            _params("straight_tuck_end_carton", 100, 50, 80)  # H < W
        with pytest.raises(ValueError):
            _params("reverse_tuck_end_carton", 100, 50, 80)

    def test_auto_bottom_allows_h_le_w(self):
        # H < W would be rejected for a tuck carton; auto-bottom permits it.
        p = _params("tuck_top_auto_bottom_carton", 200, 150, 80)
        assert p.dimensions.height_mm < p.dimensions.width_mm

    def test_depth_ratio_cap_applies_to_all(self):
        with pytest.raises(ValueError):
            _params("tuck_top_auto_bottom_carton", 12, 40, 80)  # D > 2.5W


class TestRegistry:
    def test_available_styles(self):
        styles = available_styles()
        assert len(styles) == 3
        # Production-ready (non-provisional) first.
        assert styles[0]["structure_type"] == "straight_tuck_end_carton"
        assert styles[0]["provisional"] is False
        assert all(is_supported(s["structure_type"]) for s in styles)
        assert not is_supported("bogus")
