"""Day 9, C-1 "Signed Baguette": the engine ornament generator apps/pipeline/services/orn_c1.py (DB-free, $0)."""
import inspect
import math

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from apps.pipeline.services import orn_c1

CENTRE = (95.0, 0.565 * 120.0)
FACETS = {'count': 3, 'tip_deg': 120.0, 'apex_deg': 60.0}


@pytest.fixture(scope='module')
def cut():
    return orn_c1.name_cutouts(text='ENCHANTED ROSE', face='Marcellus-Regular', cap_mm=7.5, centre_mm=CENTRE)


@pytest.fixture(scope='module')
def built(cut):
    return orn_c1.baguette(centre_mm=CENTRE, length_mm=142.5, height_mm=30.0, end_facets=FACETS, line_mm=0.12,
                           pitch_mm=0.40, rim_mm=0.3, cutouts_mm=cut['rings'], emboss=True)


def _union(rings):
    return unary_union([Polygon(r).buffer(0) for r in rings])


def test_signatures_are_keyword_only_without_defaults():
    for fn in (orn_c1.baguette, orn_c1.name_cutouts, orn_c1.stone, orn_c1.document):
        for p in inspect.signature(fn).parameters.values():
            assert p.kind is inspect.Parameter.KEYWORD_ONLY, (fn.__name__, p.name)
            assert p.default is inspect.Parameter.empty, (fn.__name__, p.name)


def test_the_stone_lies_on_the_rose_cut_lattice():
    geo = orn_c1.stone(centre_mm=CENTRE, length_mm=142.5, height_mm=30.0, end_facets=FACETS)
    assert geo['bevel_mm'] == pytest.approx(30.0 / 6.0, abs=1e-9)
    edges = [geo['tip'], geo['outer_tl'], geo['table_tl']]
    angles = set()
    for a, b in ((edges[0], edges[1]), (edges[0], edges[2]), (edges[1], edges[2])):
        ang = abs(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 180.0
        angles.add(round(ang, 6))
    assert angles == {60.0, 30.0}
    middle = geo['planes']['left_end_middle']
    sides = [math.dist(p, q) for p, q in zip(middle.exterior.coords[:-1], middle.exterior.coords[1:])]
    assert max(sides) - min(sides) < 1e-9                  # the rose cut's facet: equilateral
    assert geo['outline'].bounds == pytest.approx((23.75, CENTRE[1] - 15.0, 166.25, CENTRE[1] + 15.0))
    assert len(geo['planes']) == 9


def test_refusals(cut):
    with pytest.raises(ValueError):
        orn_c1.stone(centre_mm=CENTRE, length_mm=142.5, height_mm=30.0,
                     end_facets={'count': 2, 'tip_deg': 120.0, 'apex_deg': 60.0})
    with pytest.raises(ValueError):
        orn_c1.baguette(centre_mm=CENTRE, length_mm=142.5, height_mm=30.0, end_facets=FACETS, line_mm=0.08,
                        pitch_mm=0.40, rim_mm=0.3, cutouts_mm=cut['rings'], emboss=True)
    with pytest.raises(ValueError):
        orn_c1.baguette(centre_mm=CENTRE, length_mm=142.5, height_mm=30.0, end_facets=FACETS, line_mm=0.12,
                        pitch_mm=0.30, rim_mm=0.3, cutouts_mm=cut['rings'], emboss=True)


def test_the_name_is_the_faces_own_outline(cut):
    letters = orn_c1.letters_of(cut['rings'])
    assert letters.area == pytest.approx(cut['record']['ink_area_mm2'], rel=0.01)
    counters = [h for p in getattr(letters, 'geoms', [letters]) for h in p.interiors]
    assert len(counters) == 4                                 # A, D, R, O
    assert cut['record']['face']['stem'].startswith('Marcellus')
    x0, y0, x1, y1 = letters.bounds
    assert (x0 + x1) / 2.0 == pytest.approx(CENTRE[0], abs=0.01)


def test_shape_of_the_output(built):
    assert set(built) == {'kind', 'marks', 'regions', 'params', 'measures'}
    assert {'paint', 'relief', 'footprint'} <= set(built['regions'])
    inks = {m['ink'] for m in built['marks']}
    assert inks == {'gold_foil', 'blind', orn_c1.BODY_INK}
    for m in built['marks']:
        assert set(m) == {'points', 'closed', 'width', 'ink', 'fill', 'finishes'}
        assert m['closed'] and m['width'] == 0.0 and len(m['points']) >= 3
        assert set(m['finishes']) <= {'foil', 'emboss', 'deboss'}
        if m['ink'] == 'gold_foil':
            assert m['finishes'] == ['foil']
        if m['ink'] == 'blind':
            assert m['finishes'] in (['emboss'], ['deboss'])
    assert built['params']['rim_mm'] == 0.3 and built['params']['emboss'] is True


def test_foil_never_in_the_paint_and_nothing_outside_the_bar(built):
    foil = _union([m['points'] for m in built['marks'] if m['ink'] == 'gold_foil'])
    paint = _union(built['regions']['paint'])
    bar = _union(built['regions']['footprint'])
    lid = box(0.0, 0.0, 190.0, 120.0)
    assert foil.intersection(paint).area < 0.01
    assert built['measures']['foil_lines_inside_letters_mm2'] < 1e-6
    for m in built['marks']:
        assert bar.buffer(0.02).contains(Polygon(m['points']))
    assert lid.contains(bar)
    # the paint is the lid outside the bar plus the letters' openings
    openings = _union(built['regions']['openings'])
    assert paint.area == pytest.approx(lid.area - bar.area + openings.area, rel=1e-3)


def test_the_relief_is_nine_pillows_and_the_letters_sunk(built):
    m = built['measures']
    assert m['relief_pillows'] == 9
    assert m['relief_pct'] >= 15.0                          # D-D9-3's relief floor (foil alone is under 10 %)
    assert m['deboss_area_mm2'] == pytest.approx(m['openings_area_mm2'] - m['opening_tip_fillets_mm2'], abs=0.5)


def test_print_limits_and_density(built):
    m = built['measures']
    assert m['foil_limits_geometry']['holds']
    assert m['lines_per_cm_densest']['value'] == pytest.approx(25.0)
    assert m['counters_hold'] and len(m['counters']) == 4
    assert all(c['width_mm'] >= orn_c1.COUNTER_MIN_MM for c in m['counters'])
    assert m['narrowest_opening_mm'] >= orn_c1.FOIL_GAP_MIN_MM
    assert 5.0 < m['foil_pct'] < 8.0


def test_through_the_engine(built, tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.pipeline.services import finish_proof
    doc = orn_c1.document(result=built, ground_hex='#6B3F6E', title='c1 test')
    ai = tmp_path / 'c1.ai'
    emit_pdf_ai(doc, str(ai))
    cov = finish_proof.coverage(ai)
    plates = {p['plate']: p['kind'] for p in cov['plates']}
    assert plates == {'FOIL_GOLD': 'foil', 'EMBOSS': 'emboss', 'DEBOSS': 'deboss'}
    assert cov['meets_d9_3'] and cov['relief_pct'] >= 15.0
    assert cov['foil_and_metallic_pct'] == pytest.approx(built['measures']['foil_pct'], abs=0.15)
    foil = [p for p in finish_proof.plate_masks(ai, px_per_mm=40.0) if p['kind'] == 'foil'][0]
    density = finish_proof.line_density(foil['mask'], px_per_mm=40.0)
    assert density['max_lines_per_cm'] >= 24.5 and density['meets_d9_3']
