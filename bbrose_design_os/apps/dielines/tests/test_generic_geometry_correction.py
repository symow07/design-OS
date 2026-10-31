"""Generic carton cut/fold correction (Phase 2A-6-CORR-1).

Asserted against the INDEPENDENT hand-derived fixtures in
``fixtures_generic_geometry`` — never against the engine's own output.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString

from apps.dielines import registry
from apps.dielines.exporters.structural_comparison import geometry_integrity
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON

from . import fixtures_generic_geometry as fx

TOL = 1e-6


def _params(template_id, version=None, **over):
    dims = {"width_mm": fx.W, "depth_mm": fx.D, "height_mm": fx.H}
    dims.update(over.pop("dimensions", {}))
    return DielineInputJSON(
        template=template_id, unit="mm", template_version=version,
        dimensions=dims,
        print_settings={"bleed_mm": fx.BLEED, "safe_margin_mm": fx.SAFE},
        construction={"glue_tab_mm": fx.G, "board_thickness_mm": fx.T,
                      "thickness_compensation": True},
        metadata={"product_name": "fixture", "product_type": "carton"},
    )


def _conflict_mm(coords) -> float:
    return sum(s["shared_mm"]
               for s in geometry_integrity(coords)["cut_fold_conflict_segments"])


def _horizontals(coords):
    return sorted((round(a, 4), round(b, 4), round(c, 4), round(d, 4))
                  for a, b, c, d in coords.fold_lines if abs(b - d) < TOL)


def _verticals(coords):
    return sorted((round(a, 4), round(b, 4), round(c, 4), round(d, 4))
                  for a, b, c, d in coords.fold_lines if abs(a - c) < TOL)


@pytest.fixture(params=fx.ALL_GENERIC, ids=lambda f: f["template_id"])
def spec(request):
    return request.param


# --- the defect, pinned independently -----------------------------------------


class TestDefectReproduces:
    def test_v1_0_reproduces_the_cut_fold_conflict(self, spec):
        coords = calculate_dieline(_params(spec["template_id"], "1.0"))
        assert geometry_integrity(coords)["cut_fold_conflict"] is True
        assert _conflict_mm(coords) == pytest.approx(
            spec["v1_0_conflict_mm"], abs=0.15)

    def test_v1_0_creases_match_the_recorded_defective_form(self, spec):
        coords = calculate_dieline(_params(spec["template_id"], "1.0"))
        expected = sorted(tuple(round(v, 4) for v in c)
                          for c in spec["v1_0_horizontal_creases"])
        assert _horizontals(coords) == expected

    def test_v1_0_is_marked_non_production(self, spec):
        defn = registry.resolve(spec["template_id"], "1.0")
        assert defn.production_ready is False
        assert defn.superseded_by == spec["corrected_version"]


# --- the correction ------------------------------------------------------------


class TestCorrectedGeometry:
    def test_zero_cut_fold_overlap(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        integrity = geometry_integrity(coords)
        assert integrity["cut_fold_conflict"] is False
        assert _conflict_mm(coords) == 0.0

    def test_creases_match_the_hand_derived_expectation(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        expected = sorted(tuple(round(v, 4) for v in c)
                          for c in spec["horizontal_creases"])
        assert _horizontals(coords) == expected

    def test_vertical_body_creases_unchanged(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        expected = sorted(tuple(round(v, 4) for v in c)
                          for c in fx.VERTICAL_CREASES)
        assert _verticals(coords) == expected

    def test_folds_remain_present_around_every_interruption(self, spec):
        """A conflict must be removed by SHORTENING, never by deleting the
        hinge: every flap-bearing column still has a crease."""
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        horizontals = _horizontals(coords)
        for end, columns in (("top", spec["top_flap_columns"]),
                             ("bottom", spec["bottom_flap_columns"])):
            y = fx.Y1 if end == "top" else fx.Y2
            for column in columns:
                x_l, x_r = {
                    "back": (fx.X1, fx.X2), "side_left": (fx.X2, fx.X3),
                    "front": (fx.X3, fx.X4), "side_right": (fx.X4, fx.X5),
                }[column]
                covering = [h for h in horizontals
                            if abs(h[1] - y) < 0.01
                            and h[0] >= x_l - 0.01 and h[2] <= x_r + 0.01]
                assert covering, f"{column} lost its {end} hinge"
                # and it spans most of the column (shortened, not stubbed)
                assert covering[0][2] - covering[0][0] >= (x_r - x_l) - 3 * fx.NOTCH

    def test_flapless_panel_has_no_crease(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        cases = [(spec["flapless_top_panel"], fx.Y1),
                 (spec["flapless_bottom_panel"], fx.Y2)]
        for panel, y in cases:
            if panel is None:
                continue
            x_l, x_r = {"back": (fx.X1, fx.X2), "front": (fx.X3, fx.X4)}[panel]
            for hx1, hy1, hx2, _hy2 in _horizontals(coords):
                if abs(hy1 - y) > 0.01:
                    continue
                overlap = min(hx2, x_r) - max(hx1, x_l)
                assert overlap <= 0.01, (
                    f"crease still crosses the flapless {panel} edge")

    def test_slits_remain_cut(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        assert [s[0] for s in coords.stadium_cutouts] == spec["slit_ids"]
        for _sid, cx, cy, sw, sh in coords.stadium_cutouts:
            assert sw > 0 and sh > 0
            # the slit is a hole in the flap, i.e. not solid material
            assert not coords.cut_polygon.contains(
                LineString([(cx - sw / 4, cy), (cx + sw / 4, cy)]))

    def test_lock_notches_remain_exact(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        assert coords.derived["lock_notch_mm"] == pytest.approx(fx.NOTCH)

    def test_no_duplicate_or_zero_length_segments(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        folds = [tuple(round(v, 6) for v in f) for f in coords.fold_lines]
        assert len(folds) == len(set(folds)), "duplicate crease segment"
        for x1, y1, x2, y2 in folds:
            assert (x1, y1) != (x2, y2), "zero-length crease segment"
        cuts = [tuple(round(v, 6) for v in s) for s in coords.slit_lines]
        assert len(cuts) == len(set(cuts)), "duplicate cut segment"

    def test_contour_and_areas_valid(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        integrity = geometry_integrity(coords)
        assert integrity["self_intersecting"] is False
        assert integrity["open_contour"] is False
        assert coords.cut_polygon.is_valid
        assert coords.bleed_polygon.is_valid and coords.safe_polygon.is_valid
        assert (coords.bleed_polygon.area > coords.cut_polygon.area
                > coords.safe_polygon.area)
        # bleed offsets outward on every side by the full bleed
        cb, bb = coords.cut_polygon.bounds, coords.bleed_polygon.bounds
        assert min(cb[0] - bb[0], cb[1] - bb[1],
                   bb[2] - cb[2], bb[3] - cb[3]) == pytest.approx(fx.BLEED, abs=0.01)
        # safe area sits inside the body
        assert coords.cut_polygon.contains(coords.safe_polygon)


class TestStructureMatchesFixtures:
    def test_panel_sequence_and_widths(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        assert [p.name for p in coords.panels] == spec["panel_sequence"]
        for panel in coords.panels:
            assert panel.width == pytest.approx(
                spec["panel_widths"][panel.name]), panel.name

    def test_flat_size_and_body_height(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        assert coords.flat_width_mm == pytest.approx(spec["flat_mm"][0], abs=0.01)
        assert coords.flat_height_mm == pytest.approx(spec["flat_mm"][1], abs=0.01)
        assert (coords.body_bottom_y - coords.body_top_y) == pytest.approx(
            spec["body_height_mm"])

    def test_contract_x_and_y(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        d = coords.derived
        for key, value in (("x0", fx.X0), ("x1", fx.X1), ("x2", fx.X2),
                           ("x3", fx.X3), ("x4", fx.X4), ("x5", fx.X5)):
            assert d[key] == pytest.approx(value, abs=0.01), key
        assert d["y1"] == pytest.approx(fx.Y1, abs=0.01)
        assert d["y2"] == pytest.approx(fx.Y2, abs=0.01)

    def test_components_and_flap_orientation(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        assert [cid for cid, _ in coords.components] == spec["component_ids"]

    def test_glue_seam_side(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        names = [p.name for p in coords.panels]
        assert names[0] == "glue_tab"
        assert names[1] == spec["glue_seam_side"]

    def test_registry_declaration_matches_the_drawn_die(self, spec):
        coords = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        defn = registry.resolve(spec["template_id"], spec["corrected_version"])
        assert defn.panel_order() == [p.name for p in coords.panels]
        # The corrected version fixes the CREASES. Production eligibility is a
        # separate judgement: the auto-bottom stays ineligible because its
        # closure mechanics await a measured die (Phase 2A-6A).
        if spec["template_id"] == "tuck_top_auto_bottom_carton":
            assert defn.production_ready is False
            assert defn.structure_status == registry.STRUCTURE_PROVISIONAL
        else:
            assert defn.production_ready is True


class TestDeterminismAndVersioning:
    def test_geometry_hash_is_deterministic(self, spec):
        params = _params(spec["template_id"], spec["corrected_version"])
        h1 = registry.geometry_hash(spec["template_id"],
                                    spec["corrected_version"],
                                    params.model_dump())
        h2 = registry.geometry_hash(spec["template_id"],
                                    spec["corrected_version"],
                                    params.model_dump())
        assert h1 == h2
        # and a different version is a different identity
        assert h1 != registry.geometry_hash(
            spec["template_id"], "1.0", params.model_dump())

    def test_repeated_generation_is_identical(self, spec):
        a = calculate_dieline(_params(spec["template_id"],
                                      spec["corrected_version"]))
        b = calculate_dieline(_params(spec["template_id"],
                                      spec["corrected_version"]))
        assert a.fold_lines == b.fold_lines
        assert a.cut_polygon.equals(b.cut_polygon)

    def test_unpinned_callers_get_the_corrected_version(self, spec):
        unpinned = calculate_dieline(_params(spec["template_id"]))
        corrected = calculate_dieline(
            _params(spec["template_id"], spec["corrected_version"]))
        assert unpinned.fold_lines == corrected.fold_lines

    def test_unknown_version_fails_closed(self, spec):
        with pytest.raises(ValueError, match="unknown version"):
            calculate_dieline(_params(spec["template_id"], "9.9"))
        with pytest.raises(registry.TemplateVersionMismatch):
            registry.resolve(spec["template_id"], "9.9")

    def test_current_version_is_the_corrected_one(self, spec):
        # The CURRENT (default) version stays the 1.1 correction. Phase
        # 2A-9D adds a NON-CURRENT 1.2 (D-derived) for STE/RTE, so the
        # version list may carry a later entry; 1.0 + the 1.1 correction
        # are always the first two, and 1.1 remains current.
        assert registry.current_version(spec["template_id"]) == \
            spec["corrected_version"]
        versions = registry.versions_of(spec["template_id"])
        assert versions[:2] == ["1.0", spec["corrected_version"]]
        assert all(v == "1.0" or v >= spec["corrected_version"]
                   for v in versions)

    def test_choosers_never_offer_a_defective_version(self):
        offered = registry.production_templates()
        assert all(d.production_ready for d in offered)
        assert all(d.superseded_by == "" for d in offered)
        assert all(d.structure_status == registry.STRUCTURE_MEASURED
                   for d in offered)
        # ...but every version remains reachable explicitly, for history and
        # for technical inspection of provisional structures.
        assert len(registry.all_templates(current_only=False)) > len(offered)


class TestSkynteRegression:
    """§8: the side-seam template must not move."""

    def _coords(self):
        return calculate_dieline(_params(fx.SKYNTE["template_id"]))

    def test_panel_sequence_and_widths(self):
        coords = self._coords()
        assert [p.name for p in coords.panels] == fx.SKYNTE["panel_sequence"]
        for panel in coords.panels:
            assert panel.width == pytest.approx(
                fx.SKYNTE["panel_widths"][panel.name]), panel.name

    def test_contract_coordinates(self):
        d = self._coords().derived
        for i, value in enumerate(fx.SKYNTE["x"]):
            assert d[f"x{i}"] == pytest.approx(value, abs=0.01)
        for i, value in enumerate(fx.SKYNTE["y"]):
            assert d[f"y{i}"] == pytest.approx(value, abs=0.01)

    def test_slits_notches_and_fold_shortening(self):
        coords = self._coords()
        d = coords.derived
        assert d["entry_slit_mm"] == pytest.approx(fx.SKYNTE["entry_slit_mm"])
        assert d["lock_notch_mm"] == pytest.approx(fx.SKYNTE["lock_notch_mm"])
        assert len(coords.slit_lines) == fx.SKYNTE["entry_cut_segments"]
        assert len(coords.fold_lines) == fx.SKYNTE["fold_line_count"]
        assert len(_horizontals(coords)) == fx.SKYNTE["horizontal_crease_count"]

    def test_still_conflict_free(self):
        assert _conflict_mm(self._coords()) == fx.SKYNTE["conflict_mm"]

    def test_version_and_production_state_unchanged(self):
        defn = registry.resolve(fx.SKYNTE["template_id"])
        assert defn.version == fx.SKYNTE["version"]
        assert defn.production_ready is True
        assert registry.versions_of(fx.SKYNTE["template_id"]) == ["1.0"]
