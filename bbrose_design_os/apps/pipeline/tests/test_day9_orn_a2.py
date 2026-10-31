"""TEMPORARY, DB-free: orn_a2.golden_hour — the louvred light of the BBROSE O (Day 9, A-2)."""
import inspect
import json
import math
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from apps.pipeline.services import orn_a2

SPEC = Path(__file__).resolve().parents[4] / 'docs' / 'audit' / 'day-9' / 'directions' / 'A-2.json'
ZONES = {k: v for k, v in json.loads(SPEC.read_text())['zones'].items() if k != 'light'}
BASE = dict(oval_centre_mm=(48.0, 24.0), oval_mm=(146.0, 84.0), turn_deg=-20.0, bars=5, rhythm=orn_a2.RHYTHM_FIVE,
            gap_ratio=1.0, line_mm=0.12, pitch_mm=0.40, fade_mm=1.6, emboss=True, type_zones=ZONES)


@pytest.fixture(scope='module')
def orn():
    return orn_a2.golden_hour(**BASE)


def test_keyword_only_without_defaults():
    sig = inspect.signature(orn_a2.golden_hour)
    for p in sig.parameters.values():
        assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty, p.name
    assert set(sig.parameters) == set(BASE)


@pytest.mark.parametrize('change', [{'line_mm': 0.09}, {'pitch_mm': 0.30}, {'oval_centre_mm': (62.7, 40.8)},
                                    {'bars': 5, 'rhythm': (1, 3, 1)}, {'bars': 3, 'rhythm': (1, 3, 1)},
                                    {'fade_mm': 4.0}])
def test_refusals(change):
    with pytest.raises(ValueError):
        orn_a2.golden_hour(**dict(BASE, **change))


def test_shared_form(orn):
    assert set(orn) == {'kind', 'marks', 'regions', 'params', 'measures'}
    for name in ('paint', 'relief', 'footprint', 'lit', 'shadow', 'deep_shadow', 'oval', 'slats'):
        assert orn['regions'][name], name
    assert orn['params']['rhythm'] == list(BASE['rhythm'])


def test_marks_are_closed_foil_rectangles_inside_the_face(orn):
    face = box(orn_a2.EDGE_MARGIN_MM - 1e-6, orn_a2.EDGE_MARGIN_MM - 1e-6, 190 - orn_a2.EDGE_MARGIN_MM + 1e-6,
               120 - orn_a2.EDGE_MARGIN_MM + 1e-6)
    assert len(orn['marks']) > 100
    for m in orn['marks']:
        assert m['closed'] and m['width'] == 0.0 and m['ink'] == m['fill'] == 'gold_foil' and m['finishes'] == ['foil']
        poly = Polygon(m['points'])
        assert poly.is_valid and face.contains(poly)
        (x0, y0), (x1, y1), (x2, y2) = m['points'][:3]
        assert math.hypot(x1 - x0, y1 - y0) >= orn_a2.MIN_LINE_MM - 1e-9
        assert math.hypot(x2 - x1, y2 - y1) == pytest.approx(BASE['line_mm'], abs=1e-3)


def test_foil_limits_by_geometry(orn):
    lines = [Polygon(m['points']) for m in orn['marks']]
    union = unary_union(lines)
    # no two lines touch, and every gap between neighbours holds the gap limit
    assert len(getattr(union, 'geoms', [union])) == len(lines)
    tree_min = min(a.distance(b) for i, a in enumerate(lines) for b in lines[i + 1:i + 3])
    assert tree_min >= orn_a2.FOIL_GAP_MIN_MM - 1e-6
    assert orn['measures']['foil_limits_geometric']['holds']


def test_regions_hole_free_and_valid(orn):
    for name, rings in orn['regions'].items():
        for ring in rings:
            poly = Polygon(ring)
            assert poly.is_valid and not poly.interiors and poly.area > 0, name


def test_paint_is_lid_minus_foil(orn):
    paint = unary_union([Polygon(r) for r in orn['regions']['paint']])
    foil = unary_union([Polygon(m['points']) for m in orn['marks']])
    want = box(0, 0, 190, 120).difference(foil)
    assert paint.symmetric_difference(want).area < 1e-2


def test_type_clear_and_light_reads(orn):
    m = orn['measures']
    assert min(m['type_zone_clearance_mm'].values()) >= orn_a2.CLEAR_MM
    assert m['descends_right'] and m['oval_cropped']
    assert m['visible_rhythm'] == [3.0, 1.0, 3.0, 1.0]
    assert m['relief_pct'] >= 15.0 and m['foil_pct'] > 4.0
    relief = unary_union([Polygon(r) for r in orn['regions']['relief']])
    foil = unary_union([Polygon(x['points']) for x in orn['marks']])
    assert relief.contains(foil.buffer(-1e-4))
    deep = unary_union([Polygon(r) for r in orn['regions']['deep_shadow']])
    assert deep.bounds[1] > 60.0 and not deep.intersects(foil)


def test_no_emboss_no_relief():
    assert orn_a2.golden_hour(**dict(BASE, emboss=False))['regions']['relief'] == []
