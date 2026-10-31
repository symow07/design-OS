"""Dimensional reconciliation + structural comparison (DIP-2A-5-DIE-2)."""
from __future__ import annotations

import json
import os

import pytest

from apps.dielines.analysis.reconciliation import (
    DISCREPANCY,
    MATCH,
    RECONCILED,
    infer_board_thickness,
    reconcile_dimensions,
)
from apps.dielines.exporters.structural_comparison import (
    build_checklist,
    export_structural_comparison,
)
from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON

# The supplied Skynte Foundation dimension triplets — structural truth.
MFG = (42.0, 32.0, 140.0)
INNER = (41.4, 31.4, 138.9)
OUTER = (42.4, 32.4, 140.9)


def _coords(t=0.30):
    return calculate_dieline(DielineInputJSON(
        template="skynte_foundation_tuck_carton", unit="mm",
        dimensions={"width_mm": MFG[0], "depth_mm": MFG[1], "height_mm": MFG[2]},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0, "board_thickness_mm": t,
                      "thickness_compensation": True},
        metadata={"product_name": "Skynte Foundation",
                  "product_type": "foundation"},
    ))


class TestBoardThicknessInference:
    def test_skynte_inner_implies_t_030(self):
        assert infer_board_thickness(MFG, INNER) == pytest.approx(0.30)

    def test_disagreeing_axes_refuse(self):
        assert infer_board_thickness((42, 32, 140), (41.4, 31.0, 138.9)) is None


class TestSkynteReconciliation:
    @pytest.fixture(scope="class")
    def result(self):
        return reconcile_dimensions(_coords(), INNER, OUTER)

    def test_fully_reconciled(self, result):
        assert result.reconciled is True
        assert result.discrepancies == []

    def test_inner_cross_section_matches_exactly(self, result):
        by = {(a.dimension_set, a.axis): a for a in result.axis_checks}
        assert by[("inner", "width")].status == MATCH
        assert by[("inner", "depth")].status == MATCH

    def test_every_non_match_carries_a_stated_assumption(self, result):
        for a in result.axis_checks:
            if a.status == RECONCILED:
                assert a.assumption, f"{a.dimension_set}/{a.axis} lacks assumption"
        # inner height: 0.5 mm closure headspace
        ih = next(a for a in result.axis_checks
                  if (a.dimension_set, a.axis) == ("inner", "height"))
        assert ih.delta_mm == pytest.approx(-0.5)
        assert "headspace" in ih.assumption

    def test_supplied_values_never_altered(self, result):
        by = {(a.dimension_set, a.axis): a.supplied_mm for a in result.axis_checks}
        assert (by[("inner", "width")], by[("inner", "depth")],
                by[("inner", "height")]) == INNER
        assert (by[("outer", "width")], by[("outer", "depth")],
                by[("outer", "height")]) == OUTER

    def test_all_collision_checks_pass(self, result):
        assert all(c.ok for c in result.collision_checks)
        names = {c.name for c in result.collision_checks}
        assert {"dust_flap_opposing_clearance", "dust_below_tuck_zone",
                "tuck_lip_entry_clearance", "slit_web",
                "bleed_contour_complete"} <= names


class TestFailureModes:
    def test_wrong_board_thickness_is_a_discrepancy(self):
        # Drawn with the old t = 0.35: the supplied inner implies 0.30 —
        # the mismatch must be reported, not absorbed.
        r = reconcile_dimensions(_coords(t=0.35), INNER, OUTER)
        assert r.reconciled is False
        assert any("board thickness mismatch" in x for x in r.discrepancies)

    def test_unexplainable_residual_is_a_discrepancy(self):
        r = reconcile_dimensions(_coords(), (39.0, 31.4, 138.9), OUTER)
        assert r.reconciled is False
        by = {(a.dimension_set, a.axis): a for a in r.axis_checks}
        assert by[("inner", "width")].status == DISCREPANCY


class TestStructuralComparison:
    @pytest.fixture(scope="class")
    def checklist(self):
        coords = _coords()
        rec = reconcile_dimensions(coords, INNER, OUTER)
        return build_checklist(coords, rec, previous_spec={
            "template": "straight_tuck_end_carton",
            "board_thickness_mm": 0.35,
        })

    def test_structure_gate_passes(self, checklist):
        assert checklist["structure_passed_before_graphics"] is True
        assert all(f["present"] for f in checklist["required_features"])

    def test_differences_vs_previous_recorded(self, checklist):
        aspects = {d["aspect"] for d in checklist["differences_vs_previous"]}
        assert {"template", "panel sequence", "board thickness",
                "tuck height model"} <= aspects

    def test_flap_inventory_complete(self, checklist):
        names = {f["component"] for f in checklist["flap_inventory"]}
        assert {"top-back-tuck", "bottom-front-tuck", "top-left-dust",
                "bottom-right-dust", "glue-tab", "top-back-slit",
                "entry-slit-0", "shoulder-lock-notches (x4)"} <= names

    def test_pdf_and_json_written(self, tmp_path):
        coords = _coords()
        rec = reconcile_dimensions(coords, INNER, OUTER)
        pdf, js = export_structural_comparison(
            coords, rec, "t-cmp", str(tmp_path),
            previous_spec={"template": "straight_tuck_end_carton",
                           "board_thickness_mm": 0.35},
        )
        assert os.path.getsize(pdf) > 2000
        data = json.loads(open(js, encoding="utf-8").read())
        assert data["structure_passed_before_graphics"] is True
        assert data["reconciliation"]["reconciled"] is True

    def test_failed_structure_blocks_graphics(self, tmp_path):
        coords = _coords(t=0.35)   # wrong board thickness
        rec = reconcile_dimensions(coords, INNER, OUTER)
        checklist = build_checklist(coords, rec)
        assert checklist["structure_passed_before_graphics"] is False
