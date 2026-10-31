"""Day 9, B-2 "Damascene": the engine's inlay (apps/pipeline/services/orn_b2.py). DB-free; $0."""
import math
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from apps.pipeline.services import orn_b2 as B

LID = (190.0, 120.0)
SPEC = dict(p0_mm=(0.18 * 190, 0.74 * 120), p1_mm=(0.82 * 190, 0.26 * 120), band_mm=22.0,
            medallion_centre_mm=(95.0, 60.0), medallion_mm=54.0, folds=10, wire_mm=0.45, channel_mm=1.0,
            edge_wire_mm=0.4, glaze='by_strap', finial='pointed')


@pytest.fixture(scope='module')
def device():
    return B.damascene(**SPEC)


def _geom(mark):
    return B._mark_geom(mark)


def _parts(device):
    return list(zip(device['measures']['parts'], device['marks']))


@pytest.mark.parametrize('folds', [6, 3, 9, 12, 7, 4])
def test_six_fold_and_star_capable_folds_are_refused(folds):
    with pytest.raises(ValueError, match='six-pointed star'):
        B.damascene(**dict(SPEC, folds=folds))


def test_inputs_are_refused_when_out_of_range():
    with pytest.raises(ValueError):
        B.damascene(**dict(SPEC, glaze='metallic'))
    with pytest.raises(ValueError):
        B.damascene(**dict(SPEC, finial='round'))
    with pytest.raises(ValueError):
        B.damascene(**dict(SPEC, wire_mm=0.05))
    with pytest.raises(TypeError):
        B.damascene(p0_mm=(0, 0))                                      # keyword-only, no defaults


def test_the_output_format(device):
    assert set(device) == {'kind', 'marks', 'regions', 'params', 'measures'}
    assert device['params'] == {k: (tuple(v) if isinstance(v, tuple) else v) for k, v in SPEC.items()}
    inks = {'gold_foil', 'rose_gold_foil', 'blind'}
    for m in device['marks']:
        assert set(m) == {'points', 'closed', 'width', 'ink', 'fill', 'finishes'}
        assert m['ink'] in inks or (m['ink'].startswith('ink:#') and len(m['ink']) == 11)
        assert set(m['finishes']) <= {'foil', 'emboss', 'deboss'}
        assert ('foil' in m['finishes']) == m['ink'].endswith('_foil')            # every gold element is foil
        assert m['width'] == 0.0 or m['width'] >= 0.1
        assert 'metallic' not in m['ink']
        for x, y in m['points']:
            assert 0.0 <= x <= LID[0] and 0.0 <= y <= LID[1]
    assert len(device['measures']['parts']) == len(device['marks'])
    assert {'paint', 'relief', 'footprint'} <= set(device['regions'])


def test_regions_relief_footprint_paint(device):
    def shape(rows):
        return unary_union([Polygon(r['exterior'], r['holes']) for r in rows])
    relief, foot, paint = (shape(device['regions'][k]) for k in ('relief', 'footprint', 'paint'))
    assert len(device['regions']['relief']) == 1                                 # one raised object
    lid = box(0, 0, *LID)
    assert abs(paint.area + foot.area - lid.area) < 0.5
    assert paint.intersection(foot).area < 0.05
    inked = unary_union([_geom(m) for m in device['marks'] if m['ink'] != 'blind'])
    assert inked.difference(relief).area < 0.05                                  # everything sits in the relief
    emboss = [m for m in device['marks'] if 'emboss' in m['finishes']]
    assert len(emboss) == 1 and emboss[0]['ink'] == 'blind'
    assert abs(_geom(emboss[0]).area - relief.area) < 0.5


def test_metals_and_glaze_by_strap(device):
    by_part = {}
    for part, m in _parts(device):
        by_part.setdefault(part, set()).add(m['ink'])
    assert by_part['strap-gold'] == {'gold_foil', 'ink:' + B.GLAZE_ROSE_HEX}
    assert by_part['strap-rose-gold'] == {'rose_gold_foil', 'ink:' + B.GLAZE_TEAL_HEX}


def test_glaze_turns_uses_the_three_palette_colours():
    d = B.damascene(**dict(SPEC, glaze='turns'))
    glazes = {m['ink'] for m in d['marks'] if m['ink'].startswith('ink:')}
    assert glazes == {'ink:' + h for h in B.GLAZE_TURNS}


def test_the_knot_alternates_over_and_under_at_every_crossing(device):
    rows = device['measures']['crossings']['rows']
    assert device['measures']['crossings']['alternate_on_every_strand']
    for name, seq in device['measures']['crossings']['by_strand'].items():
        assert seq, name                                                         # every strand is woven
        assert all(a != b for a, b in zip(seq, seq[1:])), (name, seq)
        if name.startswith('petal'):
            assert len(seq) % 2 == 0 and seq[0] != seq[-1], (name, seq)          # closed: alternates round the loop
    for r in rows:
        assert r['over'] != r['under']
    # few strap-on-strap crossings along the band (no plait): one on each arm
    assert device['measures']['straps']['crossings_with_each_other'] == 2


def test_the_drawn_ink_breaks_where_a_strand_goes_under(device):
    """At every crossing the over strand's ink covers the crossing point and the under strand's foil keeps at least
    0.6 mm (the owner's floor) clear of everything the over strand inks there."""
    parts = _parts(device)
    for r in device['measures']['crossings']['rows']:
        here = Point(r['at_mm'])
        near = here.buffer(4.0)
        over = unary_union([_geom(m) for p, m in parts if p == r['over']]).intersection(near)
        under_foil = unary_union([_geom(m) for p, m in parts if p == r['under'] and m['ink'].endswith('_foil')])
        assert over.buffer(1e-6).contains(here), r
        local_under = under_foil.intersection(here.buffer(2.0))
        assert local_under.is_empty or local_under.distance(over) >= 0.6 - 1e-3, r


def test_crossings_are_clean(device):
    m = device['measures']
    assert m['crossings']['min_angle_deg'] >= 35.0
    assert m['clearance']['least_mm'] >= B.BREAK_MM - 0.05
    assert B.BREAK_MM >= 0.6


def test_the_medallion_turns_one_way(device):
    """Every petal curls the same way: its inner end is turned clockwise on the lid (y down) from its outer end."""
    c = np.array(SPEC['medallion_centre_mm'])
    parts = _parts(device)
    for k in range(SPEC['folds']):
        pts = np.vstack([m['points'] for p, m in parts if p == 'petal-%d' % k])
        rel = pts - c
        r = np.hypot(rel[:, 0], rel[:, 1])
        inner, outer = rel[np.argmin(r)], rel[np.argmax(r)]
        turn = math.degrees(math.atan2(inner[1], inner[0]) - math.atan2(outer[1], outer[0]))
        turn = (turn + 180.0) % 360.0 - 180.0
        assert 10.0 < turn < 90.0, (k, turn)


def test_the_46_mm_medallion_and_the_lobed_finial_build():
    d = B.damascene(**dict(SPEC, medallion_mm=46.0, finial='lobed', glaze='turns'))
    assert d['measures']['crossings']['alternate_on_every_strand']
    assert d['measures']['clearance']['least_mm'] >= B.BREAK_MM - 0.05


def test_module_adds_no_gate_key():
    from apps.pipeline.tests.test_palette_statistics import composed_gate
    assert composed_gate(Path(B.__file__).read_text()) == set()


def test_through_the_engine_foil_limits_hold_and_the_floor_is_met(device, tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.pipeline.services import finish_proof as fp
    ai = tmp_path / 'b2.ai'
    emit_pdf_ai(B.document(device, ground_hex='#0B0A0E'), str(ai))
    limits = fp.foil_limits(ai)
    assert limits['holds'], limits['foil_plates']
    assert {p['plate'] for p in limits['foil_plates']} == {'FOIL_GOLD', 'FOIL_ROSE_GOLD'}
    assert limits['metallic_ink_plates'] == []
    masks = [row['mask'] for row in fp.plate_masks(ai, px_per_mm=40.0) if row['kind'] == 'foil']
    density = fp.line_density(np.logical_or.reduce(masks), px_per_mm=40.0)
    assert density['max_lines_per_cm'] >= 12.0, density['max_lines_per_cm']
    cover = fp.coverage(ai)
    assert cover['relief_pct'] >= 15.0
