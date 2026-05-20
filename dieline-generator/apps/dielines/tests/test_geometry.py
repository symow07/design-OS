"""Invariant-based tests for the parametric STE geometry engine.

These tests verify the print-accuracy invariants from the rebuild spec
across all four canonical products. We do NOT assert vertex coordinates
literally — instead we assert mathematical relationships that must hold
regardless of dimension input.
"""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError
from shapely.geometry import Polygon

from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.validators.schema import DielineInputJSON


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_params(w: float, d: float, h: float, **overrides) -> DielineInputJSON:
    payload = {
        "template": "straight_tuck_end_carton",
        "unit": "mm",
        "dimensions": {"width_mm": w, "depth_mm": d, "height_mm": h},
        "print_settings": {"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "construction": {"glue_tab_mm": 10.0, **overrides.get("construction", {})},
        "metadata": {"product_name": "Test", "product_type": "test"},
    }
    return DielineInputJSON(**payload)


PRODUCTS = [
    ("Eyeliner",  20, 20, 130),
    ("Reference", 28, 28, 120),
    ("Mascara",   30, 30, 140),
    ("LipGloss",  15, 15, 90),
]


# ---------------------------------------------------------------------------
# Spec invariants (per product)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,w,d,h", PRODUCTS)
class TestSpecInvariants:
    def test_flat_width(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert math.isclose(c.flat_width_mm, 10 + d + w + d + w, abs_tol=1e-6)

    def test_flat_height(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        tuck = w * 1.227
        assert math.isclose(c.flat_height_mm, tuck + h + tuck, abs_tol=1e-6)

    def test_tuck_flap_height(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert math.isclose(
            c.derived["tuck_flap_height_mm"], w * 1.227, abs_tol=1e-6,
        )

    def test_dust_flap_height(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        # DECISION-016: dust flap height is measured from the approved AI file.
        assert math.isclose(c.derived["dust_flap_height_mm"], d * 0.631, abs_tol=1e-6)

    def test_slit_width(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert math.isclose(
            c.derived["slit_width_mm"], max(5.0, w * 0.545 * 0.6), abs_tol=1e-6,
        )

    def test_dust_flap_top_width(self, name, w, d, h):
        """Per DECISION-016: chamfer = 6 mm fixed; top width = depth − 12."""
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert math.isclose(c.derived["dust_flap_top_chamfer_mm"], 6.0, abs_tol=1e-9)
        assert math.isclose(c.derived["dust_flap_top_width_mm"], d - 12.0, abs_tol=1e-9)
        assert d - 12.0 >= 2.0  # guard for current products

    def test_tuck_curve_height(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert math.isclose(c.derived["tuck_curve_h_mm"], w * 0.218, abs_tol=1e-6)

    def test_all_polygons_valid(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert c.cut_polygon.is_valid
        assert c.bleed_polygon.is_valid
        assert c.safe_polygon.is_valid

    def test_area_ordering(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert c.bleed_polygon.area > c.cut_polygon.area
        assert c.cut_polygon.area > c.safe_polygon.area

    def test_dimension_sets(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert c.dimensions.manufacture == (w, d, h)
        # Inner = manufacture - 2 * 0.35
        bt = 0.35
        assert c.dimensions.inner == (
            round(w - 2 * bt, 4), round(d - 2 * bt, 4), round(h - 2 * bt, 4),
        )
        assert c.dimensions.outer == (
            round(w + 2 * bt, 4), round(d + 2 * bt, 4), round(h + 2 * bt, 4),
        )

    def test_interior_holes_are_slits(self, name, w, d, h):
        """Cut polygon has two interior holes: top and bottom stadium slits."""
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert c.slit_lines == []
        assert len(c.cut_polygon.interiors) == 2

    def test_two_tuck_flap_polygons(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        # 1 top back tuck + 1 bottom front tuck.
        assert len(c.tuck_flap_polygons) == 2
        for p in c.tuck_flap_polygons:
            assert p.is_valid

    def test_four_dust_flap_polygons(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert len(c.dust_flap_polygons) == 4
        for p in c.dust_flap_polygons:
            assert p.is_valid

    def test_six_crease_lines(self, name, w, d, h):
        c = calculate_straight_tuck_end(make_params(w, d, h))
        # 4 verticals + 2 horizontals
        assert len(c.fold_lines) == 6

    def test_bleed_contains_cut(self, name, w, d, h):
        """The bleed polygon must fully contain the cut polygon, with
        every cut-exterior point at least bleed_mm from the bleed
        exterior. The distance may be greater than bleed_mm in concave
        regions (e.g. the small relief notches between flaps) — that is
        a natural consequence of a circular buffer and is print-correct.
        """
        c = calculate_straight_tuck_end(make_params(w, d, h))
        cut = c.cut_polygon
        bleed = c.bleed_polygon
        assert bleed.contains(cut)
        from shapely.geometry import Point
        n = 64
        for i in range(n):
            t = i / n
            p = cut.exterior.interpolate(t, normalized=True)
            dist = Point(p.x, p.y).distance(bleed.exterior)
            # Print invariant: never tighter than the requested bleed
            assert dist >= 2.95, f"point {i}: distance {dist:.3f} < 3mm (bleed too tight)"

    def test_safe_inside_body(self, name, w, d, h):
        """Safe area must lie strictly inside the body rectangle (x1..x5, y1..y2)."""
        c = calculate_straight_tuck_end(make_params(w, d, h))
        x1 = c.derived["x1"]
        x5 = c.derived["x5"]
        body_min_y = c.body_top_y
        body_max_y = c.body_bottom_y
        sx0, sy0, sx1, sy1 = c.safe_polygon.bounds
        assert sx0 >= x1 + 4.0 - 1e-6
        assert sx1 <= x5 - 4.0 + 1e-6
        assert sy0 >= body_min_y + 4.0 - 1e-6
        assert sy1 <= body_max_y - 4.0 + 1e-6


# ---------------------------------------------------------------------------
# Guard assertions
# ---------------------------------------------------------------------------

class TestGuards:
    def test_width_below_12_raises_at_schema(self):
        with pytest.raises(ValidationError):
            make_params(10, 20, 130)

    def test_height_below_60_raises_at_schema(self):
        with pytest.raises(ValidationError):
            make_params(20, 20, 50)

    def test_depth_below_12_raises_at_schema(self):
        with pytest.raises(ValidationError):
            make_params(20, 10, 130)
