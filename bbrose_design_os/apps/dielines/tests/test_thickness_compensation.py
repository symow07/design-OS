"""Milestone 9.2 — opt-in board-thickness compensation (audit C5).

Default behaviour (thickness_compensation=False) must be byte-identical to
legacy geometry regardless of board_thickness_mm; opting in applies the
ECMA per-panel allowances (back +2t, sides +t each) and the DECISION-015
shoulder lock notches (2t) on the two active tuck flaps.
"""
from __future__ import annotations

import math

import pytest
from shapely.geometry import Point

from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.validators.schema import DielineInputJSON

T = 0.45  # test board thickness (mm)


def make_params(w=28, d=28, h=120, **construction):
    return DielineInputJSON(
        template="straight_tuck_end_carton",
        unit="mm",
        dimensions={"width_mm": w, "depth_mm": d, "height_mm": h},
        print_settings={},
        construction=construction,
        metadata={"product_name": "Comp", "product_type": "test"},
    )


@pytest.fixture(scope="module")
def legacy():
    return calculate_straight_tuck_end(make_params())


@pytest.fixture(scope="module")
def comp():
    return calculate_straight_tuck_end(
        make_params(board_thickness_mm=T, thickness_compensation=True)
    )


class TestOptInGate:
    def test_flag_defaults_off(self):
        assert make_params().construction.thickness_compensation is False

    def test_default_ignores_board_thickness_for_layout(self, legacy):
        """comp=False with a non-default t must still produce legacy layout
        (t feeds only the inner/outer spec table)."""
        c = calculate_straight_tuck_end(make_params(board_thickness_mm=T))
        assert list(c.cut_polygon.exterior.coords) == list(
            legacy.cut_polygon.exterior.coords
        )
        assert c.flat_width_mm == legacy.flat_width_mm
        assert c.derived["thickness_compensation"] is False
        assert c.derived["lock_notch_mm"] == 0.0
        # but the spec table does see t
        assert c.dimensions.inner != legacy.dimensions.inner

    def test_zero_thickness_compensation_is_legacy(self, legacy):
        """comp=True with t=0 degenerates exactly to legacy geometry."""
        c = calculate_straight_tuck_end(
            make_params(board_thickness_mm=0.0, thickness_compensation=True)
        )
        assert list(c.cut_polygon.exterior.coords) == list(
            legacy.cut_polygon.exterior.coords
        )
        assert [tuple(f) for f in c.fold_lines] == [tuple(f) for f in legacy.fold_lines]
        assert c.derived["lock_notch_mm"] == 0.0


class TestCompensatedLayout:
    def test_flat_width_grows_by_4t(self, comp, legacy):
        assert math.isclose(
            comp.flat_width_mm, legacy.flat_width_mm + 4 * T, abs_tol=1e-9,
        )

    def test_flat_height_unchanged(self, comp, legacy):
        assert comp.flat_height_mm == legacy.flat_height_mm

    def test_panel_allowances(self, comp):
        widths = {p.name: p.width for p in comp.panels}
        assert math.isclose(widths["glue_tab"], 10.0, abs_tol=1e-9)
        assert math.isclose(widths["back"], 28 + 2 * T, abs_tol=1e-9)
        assert math.isclose(widths["side_left"], 28 + T, abs_tol=1e-9)
        assert math.isclose(widths["front"], 28.0, abs_tol=1e-9)
        assert math.isclose(widths["side_right"], 28 + T, abs_tol=1e-9)

    def test_derived_annotations(self, comp):
        d = comp.derived
        assert d["thickness_compensation"] is True
        assert math.isclose(d["panel_allowance_back_mm"], 2 * T, abs_tol=1e-9)
        assert math.isclose(d["panel_allowance_side_mm"], T, abs_tol=1e-9)
        assert math.isclose(d["lock_notch_mm"], 2 * T, abs_tol=1e-9)
        assert any("board-thickness compensation" in n for n in d["notes"])

    def test_geometry_still_valid_and_in_bounds(self, comp):
        assert comp.cut_polygon.is_valid
        minx, miny, maxx, maxy = comp.cut_polygon.bounds
        assert minx >= -0.01 and miny >= -0.01
        assert maxx <= comp.flat_width_mm + 0.01
        assert maxy <= comp.flat_height_mm + 0.01


class TestLockNotches:
    """DECISION-015: 2t notches at both base corners of the two active
    tuck flaps. Probe the notch interiors with point containment."""

    def _probe(self, coords, x, y):
        return coords.cut_polygon.covers(Point(x, y))

    def test_top_back_tuck_notches_cut(self, comp, legacy):
        n = 2 * T  # 0.9
        x1 = comp.derived["x1"]           # back panel left edge (10.0)
        x2 = comp.derived["x2"]           # back panel right edge (38.9)
        y_base = comp.body_top_y          # tuck base (34.356)
        # centre of each notch square
        left_probe = (x1 + n / 2, y_base - n / 2)
        right_probe = (x2 - n / 2, y_base - n / 2)
        assert not self._probe(comp, *left_probe)
        assert not self._probe(comp, *right_probe)
        # legacy keeps that material (same local coordinates on its flap)
        lx1 = legacy.derived["x1"]
        lx2 = legacy.derived["x2"]
        assert self._probe(legacy, lx1 + n / 2, legacy.body_top_y - n / 2)
        assert self._probe(legacy, lx2 - n / 2, legacy.body_top_y - n / 2)

    def test_bottom_front_tuck_notches_cut(self, comp):
        n = 2 * T
        x3 = comp.derived["x3"]           # front panel left edge
        x4 = comp.derived["x4"]           # front panel right edge
        y_base = comp.body_bottom_y       # bottom tuck base
        assert not self._probe(comp, x3 + n / 2, y_base + n / 2)
        assert not self._probe(comp, x4 - n / 2, y_base + n / 2)

    def test_no_notches_on_dust_flaps(self, comp):
        """DECISION-015 applies only to the two active tuck flaps: the
        dust-flap corners keep their material."""
        n = 2 * T
        x2 = comp.derived["x2"]           # left dust flap starts at x2
        y_base = comp.body_top_y
        # just inside the dust flap base corner (past its 3 mm base notch
        # is a different feature — probe within the first 3 mm step zone
        # vertically above the body, at the flap's horizontal centre)
        x3 = comp.derived["x3"]
        cx = (x2 + x3) / 2
        assert self._probe(comp, cx, y_base - n / 2)
