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

    def test_cut_bbox_within_flat_bounds(self, name, w, d, h):
        """Milestone 9.1 invariant: the cut polygon must lie inside
        [0, flat_width] × [0, flat_height] to within 0.01 mm."""
        c = calculate_straight_tuck_end(make_params(w, d, h))
        minx, miny, maxx, maxy = c.cut_polygon.bounds
        eps = 0.01
        assert minx >= -eps
        assert miny >= -eps
        assert maxx <= c.flat_width_mm + eps
        assert maxy <= c.flat_height_mm + eps

    def test_no_clamp_and_no_slit_reduction_on_square_products(self, name, w, d, h):
        """Square products never trigger the 9.1 dust clamp or the
        DECISION-017 slit reduction — legacy geometry is untouched."""
        c = calculate_straight_tuck_end(make_params(w, d, h))
        assert c.derived["dust_flap_clamped"] is False
        assert c.derived["slit_reduced"] is False
        assert c.derived["slit_web_mm"] >= 2.0
        assert c.derived["notes"] == []

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
# Non-square products — Milestone 9.1 dust-flap clamp (audit C4)
# ---------------------------------------------------------------------------

class TestNonSquareProducts:
    def test_deep_narrow_carton_clamps_dust_flap(self):
        """15×35×90: nominal dust (22.085) would overshoot the tuck zone
        (18.405) — clamped to tuck − 2 mm and annotated."""
        c = calculate_straight_tuck_end(make_params(15, 35, 90))
        tuck = 15 * 1.227
        assert c.derived["dust_flap_clamped"] is True
        assert math.isclose(c.derived["dust_flap_height_nominal_mm"], 35 * 0.631, abs_tol=1e-6)
        assert math.isclose(c.derived["dust_flap_height_mm"], tuck - 2.0, abs_tol=1e-6)
        assert c.derived["dust_flap_height_mm"] < c.derived["tuck_flap_height_mm"]
        assert any("dust flap reduced" in n for n in c.derived["notes"])
        # clamped geometry must still satisfy the bbox invariant
        minx, miny, maxx, maxy = c.cut_polygon.bounds
        assert minx >= -0.01 and miny >= -0.01
        assert maxx <= c.flat_width_mm + 0.01
        assert maxy <= c.flat_height_mm + 0.01
        assert c.cut_polygon.is_valid

    def test_wide_shallow_carton_unclamped(self):
        """40×12×60: dust (7.572) far below the tuck zone — no clamp."""
        c = calculate_straight_tuck_end(make_params(40, 12, 60))
        assert c.derived["dust_flap_clamped"] is False
        assert math.isclose(c.derived["dust_flap_height_mm"], 12 * 0.631, abs_tol=1e-6)
        assert c.derived["notes"] == []
        assert c.cut_polygon.is_valid

    def test_clamp_boundary(self):
        """W=20 → tuck zone 24.54, clamp threshold D ≈ 35.72:
        D=35 stays nominal, D=36 clamps."""
        c35 = calculate_straight_tuck_end(make_params(20, 35, 80))
        assert c35.derived["dust_flap_clamped"] is False
        assert math.isclose(c35.derived["dust_flap_height_mm"], 35 * 0.631, abs_tol=1e-6)

        c36 = calculate_straight_tuck_end(make_params(20, 36, 80))
        assert c36.derived["dust_flap_clamped"] is True
        assert math.isclose(
            c36.derived["dust_flap_height_mm"], 20 * 1.227 - 2.0, abs_tol=1e-6,
        )

    def test_beyond_clamp_range_rejected_at_schema(self):
        """12×40×60: D > 2.5×W is the wrong carton style — hard reject."""
        with pytest.raises(ValidationError, match="2.5x width_mm"):
            make_params(12, 40, 60)


# ---------------------------------------------------------------------------
# DECISION-017 slit web guard — Milestone 9.3
# ---------------------------------------------------------------------------

class TestSlitWebGuard:
    def test_narrowest_width_keeps_min_web(self):
        """W=12 (schema minimum, the at-risk family): slit stays at the
        5 mm floor and the measured web beside each end is ≥ 2 mm."""
        c = calculate_straight_tuck_end(make_params(12, 12, 60))
        assert math.isclose(c.derived["slit_width_mm"], 5.0, abs_tol=1e-6)
        assert c.derived["slit_reduced"] is False
        assert c.derived["slit_web_mm"] >= 2.0

    def test_web_guard_reduces_slit_when_needed(self):
        """Unit-level: force a violating combination through the helper."""
        from apps.dielines.geometry.engine import _apply_slit_web_guard
        slit_w, web, reduced = _apply_slit_web_guard(9.0, 12.0, 0.5)
        assert reduced is True
        assert slit_w >= 3.0
        assert web >= 2.0 - 1e-9

    def test_web_guard_raises_below_functional_floor(self):
        from apps.dielines.geometry.engine import (
            GeometryError, _apply_slit_web_guard,
        )
        with pytest.raises(GeometryError):
            # panel so narrow that even a 3 mm slit cannot keep 2 mm webs
            _apply_slit_web_guard(5.0, 6.0, 0.0)


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

    def test_width_above_300_raises_at_schema(self):
        with pytest.raises(ValidationError):
            make_params(301, 20, 400)

    def test_depth_above_300_raises_at_schema(self):
        with pytest.raises(ValidationError):
            make_params(200, 301, 400)

    def test_height_above_600_raises_at_schema(self):
        with pytest.raises(ValidationError):
            make_params(20, 20, 601)

    def test_max_bounds_accepted_and_in_bbox(self):
        """The extreme corner of the allowed envelope still generates and
        satisfies the Milestone 9.1 bounding-box invariant."""
        c = calculate_straight_tuck_end(make_params(300, 300, 600))
        minx, miny, maxx, maxy = c.cut_polygon.bounds
        assert minx >= -0.01 and miny >= -0.01
        assert maxx <= c.flat_width_mm + 0.01
        assert maxy <= c.flat_height_mm + 0.01


# ---- [his final goal, 2026-10-05, B2: "A PRINT-READY DIELINE. Cut lines solid; crease lines dashed on EVERY fold,
# including flap hinges and the tuck fold. Proper dust-flap shapes, tuck-lock slits and a thumb notch."]

def _v(version, w=22.0, d=22.0, h=105.0, template="straight_tuck_end_carton"):
    from apps.dielines.geometry.engine import calculate_dieline
    from apps.dielines.validators.schema import DielineInputJSON
    return calculate_dieline(DielineInputJSON(
        template=template, template_version=version, unit="mm",
        dimensions={"width_mm": w, "depth_mm": d, "height_mm": h}, print_settings={},
        construction={"board_thickness_mm": 0.45, "thickness_compensation": True},
        metadata={"product_name": "x", "product_type": "y"}))


def test_his_final_goal_b2_v1_3_creases_the_tuck_folds_cuts_their_lock_slits_and_a_thumb_notch():
    """1.3 is 1.2's tuck across the depth with the tuck fold — between the lid (as deep as the carton) and its tongue —
    creased between two lock slits cut from the flap's side edges, top and bottom, and a half-round thumb notch in the
    top edge of the panel the lid closes onto (the front, on the straight tuck end); 1.2 and 1.1 draw as before."""
    from shapely.geometry import Point
    c12, c13 = _v("1.2"), _v("1.3")
    folds = c13.derived["tuck_folds"]
    assert [f["tuck"] for f in folds] == ["top", "bottom"] and all(f["tongue_mm"] >= 8.0 for f in folds)
    side = next(p for p in c13.panels if p.name == "side_left")
    assert abs(folds[0]["y"] - (c13.body_top_y - side.width)) < 1e-9
    for f in folds:
        assert (f["x_l"] + f["slit_mm"], f["y"], f["x_r"] - f["slit_mm"], f["y"]) in c13.fold_lines
        assert (f["x_l"], f["y"], f["x_l"] + f["slit_mm"], f["y"]) in c13.slit_lines
        assert (f["x_r"] - f["slit_mm"], f["y"], f["x_r"], f["y"]) in c13.slit_lines
    assert len(c13.fold_lines) == len(c12.fold_lines) + 2 and len(c13.slit_lines) == 4 and c12.slit_lines == []
    n = c13.derived["thumb_notch"]
    front = next(p for p in c13.panels if p.name == "front")
    assert n["panel"] == "front" and abs(n["cx"] - (front.x + front.width / 2)) < 1e-9 and 4.0 < n["r"] <= 9.0
    assert not c13.cut_polygon.contains(Point(n["cx"], n["y"] + n["r"] * 0.5))      # cut away
    assert c12.cut_polygon.contains(Point(n["cx"], n["y"] + n["r"] * 0.5))
    assert c12.derived["thumb_notch"] is None and c12.derived["tuck_folds"] == []
    reverse = _v("1.3", template="reverse_tuck_end_carton")
    assert reverse.derived["thumb_notch"]["panel"] == "back"                    # the lid closes onto the back


def test_his_final_goal_b2_a_new_carton_is_drawn_at_1_3_and_its_registry_entry_says_so():
    """[His second goal of 2026-10-06, item 2] a new carton is drawn at 1.4 now — the trade's written rules
    (test_trade_tuck.py); 1.3 stays registered, print-ready as he asked, for the jobs drawn at it."""
    from apps.dielines import registry
    from apps.pipeline.targets.gift_set import GiftSetTarget
    from apps.pipeline.targets.packaging import PackagingTarget
    assert PackagingTarget().carton_template_version(None) == "1.4" == GiftSetTarget().carton_template_version(None)
    defn = registry.resolve("straight_tuck_end_carton", "1.3")
    assert "PRINT-READY" in " ".join(defn.notes) and registry.resolve("straight_tuck_end_carton").version == "1.1"
    assert registry.QUALIFIED_AS["1.3"] == "1.2"
