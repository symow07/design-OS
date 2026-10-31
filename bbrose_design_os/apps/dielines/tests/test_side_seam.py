"""Side-seam straight-tuck archetype (DECISION-018/019/020) — geometry tests.

The Skynte Foundation reference facts these tests pin:
  * panel sequence glue | side A | main B | side A | main B (32/42/32/42)
  * ECMA allowances re-expressed for the side-seam order (+4t flat total)
  * tuck height = D + lip per end (DECISION-019), NOT W × 1.227
  * tuck-base entry slits + per-hinge crease segments (DECISION-020)
  * the locked STE engine is not touched by the new dispatch path
"""
from __future__ import annotations

import pytest
from shapely.geometry import Point

from apps.dielines.exporters.counter_display_files import write_carton_svg
from apps.dielines.exporters.svg_validator import validate_svg
from apps.dielines.geometry.engine import GeometryError, calculate_dieline
from apps.dielines.geometry.side_seam import (
    SKYNTE_FOUNDATION_TUCK_CARTON_V1,
    SideSeamTuckSpec,
    calculate_side_seam_tuck,
    spec_for_template,
)
from apps.dielines.validators.schema import DielineInputJSON

W, D, H, G, T = 42.0, 32.0, 140.0, 10.0, 0.30


def _params(**over):
    dims = {"width_mm": W, "depth_mm": D, "height_mm": H}
    cons = {"glue_tab_mm": G, "board_thickness_mm": T,
            "thickness_compensation": True}
    dims.update(over.pop("dimensions", {}))
    cons.update(over.pop("construction", {}))
    return DielineInputJSON(
        template=over.pop("template", "skynte_foundation_tuck_carton"),
        unit="mm",
        dimensions=dims,
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction=cons,
        metadata={"product_name": "Skynte Foundation",
                  "product_type": "foundation"},
    )


@pytest.fixture(scope="module")
def coords():
    return calculate_dieline(_params())


class TestPanelSequence:
    def test_panel_order_matches_supplied_reference(self, coords):
        assert [p.name for p in coords.panels] == [
            "glue_tab", "side_left", "front", "side_right", "back",
        ]

    def test_panel_widths_carry_ecma_allowances(self, coords):
        widths = {p.name: p.width for p in coords.panels}
        assert widths["glue_tab"] == pytest.approx(G)
        assert widths["side_left"] == pytest.approx(D + T)
        assert widths["front"] == pytest.approx(W)          # reference panel
        assert widths["side_right"] == pytest.approx(D + T)
        assert widths["back"] == pytest.approx(W + 2 * T)   # glue joint panel

    def test_flat_width_grows_by_exactly_4t(self, coords):
        assert coords.flat_width_mm == pytest.approx(G + 2 * D + 2 * W + 4 * T)

    def test_coordinate_contract(self, coords):
        d = coords.derived
        assert d["x1"] == pytest.approx(G)
        assert d["x2"] == pytest.approx(G + D + T)
        assert d["x3"] == pytest.approx(G + D + T + W)
        assert d["x4"] == pytest.approx(G + 2 * (D + T) + W)
        assert d["x5"] == pytest.approx(coords.flat_width_mm)


class TestTuckHeightModel:
    def test_tuck_height_is_depth_plus_lip(self, coords):
        d = coords.derived
        lip = SKYNTE_FOUNDATION_TUCK_CARTON_V1.top_tuck_lip_mm
        assert d["y1"] == pytest.approx(D + lip)
        assert d["top_tuck_height_mm"] == pytest.approx(D + lip)
        # Explicitly NOT the square-reference W-based factor.
        assert d["top_tuck_height_mm"] != pytest.approx(W * 1.227, abs=0.5)

    def test_flat_height(self, coords):
        spec = SKYNTE_FOUNDATION_TUCK_CARTON_V1
        expected = (D + spec.top_tuck_lip_mm) + H + (D + spec.bottom_tuck_lip_mm)
        assert coords.flat_height_mm == pytest.approx(expected)

    def test_shoulder_curve_must_fit_inside_lip(self):
        spec = SideSeamTuckSpec(
            template="x", version="t", top_tuck_lip_mm=10.0,
            bottom_tuck_lip_mm=10.0, tuck_shoulder_curve_factor=0.30,
        )
        with pytest.raises(GeometryError, match="does not fit inside the tuck lip"):
            calculate_side_seam_tuck(_params(), spec)


class TestClosureGeometry:
    def test_two_rounded_tucks_and_four_dust_flaps(self, coords):
        ids = [cid for cid, _ in coords.components]
        assert "top-back-tuck" in ids and "bottom-front-tuck" in ids
        assert {"top-left-dust", "top-right-dust",
                "bottom-left-dust", "bottom-right-dust"} <= set(ids)
        # Both tucks carry primitive Bézier shoulders (rounded corners).
        assert set(coords.component_paths) == {"top-back-tuck", "bottom-front-tuck"}

    def test_two_friction_slits(self, coords):
        assert [s[0] for s in coords.stadium_cutouts] == [
            "top-back-slit", "bottom-front-slit",
        ]

    def test_lock_notches_present_at_tuck_bases(self, coords):
        # DECISION-015: a 2t × 2t notch at each tuck base corner — the point
        # just inside the flap column at base height must NOT be in the cut
        # polygon (it is notched away).
        d = coords.derived
        n = d["lock_notch_mm"]
        assert n == pytest.approx(2 * T)
        x4, y1 = d["x4"], d["y1"]
        probe = Point(x4 + n / 2.0, y1 - n / 2.0)
        assert not coords.cut_polygon.contains(probe)

    def test_entry_slits_shorten_the_tuck_base_creases(self, coords):
        d = coords.derived
        entry, n = d["entry_slit_mm"], d["lock_notch_mm"]
        x4, x5, y1 = d["x4"], d["x5"], d["y1"]
        assert (x4 + n + entry, y1, x5 - n - entry, y1) in coords.fold_lines
        assert (x4 + n, y1, x4 + n + entry, y1) in coords.slit_lines
        assert (x5 - n - entry, y1, x5 - n, y1) in coords.slit_lines
        assert len(coords.slit_lines) == 4          # two per tuck

    def test_no_crease_over_cut_edges(self, coords):
        # The front panel's top edge and back panel's bottom edge are plain
        # cut edges: no crease may span them (DECISION-020).
        d = coords.derived
        x2, x3, y1 = d["x2"], d["x3"], d["y1"]
        x4, x5, y2 = d["x4"], d["x5"], d["y2"]
        def overlaps(a1, a2, b1, b2):
            return min(a2, b2) - max(a1, b1) > 1e-6

        for (fx1, fy1, fx2, fy2) in coords.fold_lines:
            if fy1 == fy2 == y1:
                assert not overlaps(fx1, fx2, x2, x3), \
                    "crease crosses the front panel's top cut edge"
            if fy1 == fy2 == y2:
                assert not overlaps(fx1, fx2, x4, x5), \
                    "crease crosses the back panel's bottom cut edge"

    def test_glue_tab_tapered(self, coords):
        cc = coords.derived["glue_tab_corner_cut_mm"]
        assert cc == pytest.approx(min(G * 0.3, 4.0))
        ys = sorted(y for _, y in coords.glue_tab_polygon.exterior.coords)
        d = coords.derived
        assert ys[0] == pytest.approx(d["y1"])           # at the fold
        # free-edge corners are cut in by cc
        xs_at_top = [
            (x, y) for x, y in coords.glue_tab_polygon.exterior.coords
            if x == pytest.approx(0.0)
        ]
        assert all(
            y == pytest.approx(d["y1"] + cc) or y == pytest.approx(d["y2"] - cc)
            for _, y in xs_at_top
        )


class TestDimensionsAndValidation:
    def test_dimension_set_uses_supplied_board_thickness(self, coords):
        assert coords.dimensions.manufacture == (W, D, H)
        assert coords.dimensions.inner == (41.4, 31.4, 139.4)
        assert coords.dimensions.outer == (42.6, 32.6, 140.6)

    def test_assumptions_are_published(self, coords):
        d = coords.derived
        assert d["assumptions"], "template assumptions must be published"
        joined = " ".join(d["notes"])
        assert "ASSUMPTION (skynte_foundation_tuck_carton/1.0)" in joined

    def test_parameters_table_published(self, coords):
        p = coords.derived["parameters"]
        assert p["template"] == "skynte_foundation_tuck_carton"
        assert p["version"] == "1.0"
        assert p["top_tuck_lip_mm"] == 16.0

    def test_svg_round_trip_validates(self, coords, tmp_path):
        svg = write_carton_svg(coords, "t-side-seam", output_dir=str(tmp_path))
        assert validate_svg(svg, coords) == []
        # entry slits reach the cut layer
        assert 'id="entry-slit-0"' in svg

    def test_schema_rejects_bad_proportions(self):
        with pytest.raises(ValueError, match="height_mm"):
            _params(dimensions={"height_mm": 40.0})

    def test_uncompensated_geometry_has_no_notches_or_allowances(self):
        c = calculate_dieline(_params(
            construction={"thickness_compensation": False}))
        assert c.derived["lock_notch_mm"] == 0.0
        assert c.flat_width_mm == pytest.approx(G + 2 * D + 2 * W)


class TestRegistryAndDispatch:
    def test_spec_registry(self):
        assert spec_for_template("skynte_foundation_tuck_carton") is \
            SKYNTE_FOUNDATION_TUCK_CARTON_V1
        assert spec_for_template("nope") is None

    def test_unknown_template_still_refused(self):
        with pytest.raises(ValueError):
            _params(template="mystery_carton")

    def test_ste_reference_unaffected(self):
        # The locked STE path must keep its original panel order and count.
        c = calculate_dieline(_params(template="straight_tuck_end_carton"))
        assert [p.name for p in c.panels] == [
            "glue_tab", "back", "side_left", "front", "side_right",
        ]
        assert c.slit_lines == []
