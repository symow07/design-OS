"""Legacy-regression guard: 28×28×120 at default construction must
reproduce the golden engine snapshot EXACTLY (Milestone 9.2).

The snapshot (docs/28x28x120_engine_reference.json) was generated from the
engine immediately before the Phase 9 changes, so any drift here means the
default (thickness_compensation=False) code path no longer produces legacy
geometry. The older docs/28x28x120_coordinate_dump.json is NOT used — it
predates DECISION-016 and describes a different tuck shape entirely.

If you intentionally change locked geometry (see geometry_decisions.md),
regenerate the snapshot and say so in the decision entry.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.validators.schema import DielineInputJSON

_REF_PATH = Path(__file__).resolve().parents[1] / "docs" / "28x28x120_engine_reference.json"


def _r6(v):
    return round(float(v), 6)


@pytest.fixture(scope="module")
def ref():
    with open(_REF_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def coords():
    params = DielineInputJSON(
        template="straight_tuck_end_carton",
        unit="mm",
        dimensions={"width_mm": 28, "depth_mm": 28, "height_mm": 120},
        print_settings={},
        construction={},
        metadata={"product_name": "Reference", "product_type": "reference"},
    )
    return calculate_straight_tuck_end(params)


class TestReferenceRegression:
    def test_flat_size(self, coords, ref):
        assert _r6(coords.flat_width_mm) == ref["flat_width_mm"]
        assert _r6(coords.flat_height_mm) == ref["flat_height_mm"]

    def test_body_band(self, coords, ref):
        assert _r6(coords.body_top_y) == ref["body_top_y"]
        assert _r6(coords.body_bottom_y) == ref["body_bottom_y"]

    def test_cut_exterior_exact(self, coords, ref):
        got = [[_r6(x), _r6(y)] for x, y in coords.cut_polygon.exterior.coords]
        assert got == ref["cut_exterior"]

    def test_cut_interiors_exact(self, coords, ref):
        got = [
            [[_r6(x), _r6(y)] for x, y in ring.coords]
            for ring in coords.cut_polygon.interiors
        ]
        assert got == ref["cut_interiors"]

    def test_panels_exact(self, coords, ref):
        got = [
            {"name": p.name, "x": _r6(p.x), "y": _r6(p.y),
             "width": _r6(p.width), "height": _r6(p.height)}
            for p in coords.panels
        ]
        assert got == ref["panels"]

    def test_fold_lines_exact(self, coords, ref):
        got = [[_r6(v) for v in line] for line in coords.fold_lines]
        assert got == ref["fold_lines"]

    def test_stadium_cutouts_exact(self, coords, ref):
        got = [
            [slot_id] + [_r6(v) for v in rest]
            for slot_id, *rest in coords.stadium_cutouts
        ]
        assert got == ref["stadium_cutouts"]

    def test_derived_snapshot_subset(self, coords, ref):
        """Every derived key recorded in the snapshot must still exist
        with the same value. New keys added since (clamp/slit/compensation
        annotations) are allowed on top."""
        for key, expected in ref["derived"].items():
            assert key in coords.derived, f"derived key {key} disappeared"
            got = coords.derived[key]
            if isinstance(expected, (int, float)) and not isinstance(expected, bool):
                assert _r6(got) == _r6(expected), f"derived[{key}]"
            else:
                assert got == expected, f"derived[{key}]"

    def test_bboxes_exact(self, coords, ref):
        assert [_r6(v) for v in coords.cut_polygon.bounds] == ref["cut_bbox"]
        assert [_r6(v) for v in coords.bleed_polygon.bounds] == ref["bleed_bbox"]
        assert [_r6(v) for v in coords.safe_polygon.bounds] == ref["safe_bbox"]

    def test_areas_exact(self, coords, ref):
        assert round(coords.cut_polygon.area, 4) == round(ref["areas"]["cut"], 4)
        assert round(coords.bleed_polygon.area, 4) == round(ref["areas"]["bleed"], 4)
        assert round(coords.safe_polygon.area, 4) == round(ref["areas"]["safe"], 4)
