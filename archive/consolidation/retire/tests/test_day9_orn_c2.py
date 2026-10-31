"""orn_c2 (C-2 Taʿshīq, the dovetail seam): geometry, the shared output form, and the engine's own measures. DB-free."""
import inspect
import math

import numpy as np
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from apps.pipeline.services import orn_c2

SPEC = dict(seam_x0_mm=0.45 * 190, seam_x1_mm=0.59 * 190, tails=6, slope=7.0, line_mm=0.12, pitch_mm=0.40,
            outline_mm=0.4, inset_mm=0.3, emboss=True)
COLOURS = dict(left_page_hex='#6E2840', right_page_hex='#EEE6E4', gold_hex='#C9A55C', rose_gold_hex='#C99A84')
LID = 190.0 * 120.0


@pytest.fixture(scope='module')
def res():
    return orn_c2.tashiq(**SPEC)


def _area(rings):
    return unary_union([Polygon(r) for r in rings]).area


def test_signature_is_keyword_only_without_defaults():
    sig = inspect.signature(orn_c2.tashiq)
    assert list(sig.parameters) == list(SPEC)
    for p in sig.parameters.values():
        assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty


def test_shared_output_form(res):
    assert set(res) == {'kind', 'marks', 'regions', 'params', 'measures'}
    assert res['params'] == SPEC
    for m in res['marks']:
        assert set(m) == {'points', 'closed', 'width', 'ink', 'fill', 'finishes'}
        assert m['ink'] in ('gold_foil', 'rose_gold_foil', 'blind') and set(m['finishes']) <= {'foil', 'emboss'}
        assert m['closed'] and m['width'] == 0.0 and m['fill'] == m['ink']
    for name in ('paint', 'relief', 'footprint', 'left_page', 'right_page'):
        assert res['regions'][name]
        for ring in res['regions'][name]:
            poly = Polygon(ring)
            assert poly.is_valid and not poly.interiors and poly.area > 0


def test_true_dovetails_alternating_metals(res):
    tails = [Polygon(r) for r in res['regions']['tails']]
    assert len(tails) == 6
    x0, x1 = SPEC['seam_x0_mm'] + SPEC['outline_mm'], SPEC['seam_x1_mm']
    for t in tails:
        (ax, ay), (bx, by), (cx, cy), (dx, dy) = list(t.exterior.coords)[:4]
        assert (ax, dx, bx, cx) == pytest.approx((x0, x0, x1, x1))
        neck, end = dy - ay, cy - by
        assert end > neck + 7.0                                   # flares toward its end: never a finger
        assert (bx - ax) / (ay - by) == pytest.approx(SPEC['slope'])   # 1:7 on both sides
        assert (cx - dx) / (cy - dy) == pytest.approx(SPEC['slope'])
    assert res['measures']['joint']['tail_inks'] == ['gold_foil', 'rose_gold_foil'] * 3
    pins = [Polygon(r) for r in res['regions']['pins']]
    assert len(pins) == 7                                         # five pins and two half-pins


def test_pages_partition_the_lid_along_the_dovetail_line(res):
    left = unary_union([Polygon(r) for r in res['regions']['left_page']])
    right = unary_union([Polygon(r) for r in res['regions']['right_page']])
    assert left.area + right.area == pytest.approx(LID, abs=1e-6)
    assert left.intersection(right).area == pytest.approx(0.0, abs=1e-9)
    tails = unary_union([Polygon(r) for r in res['regions']['tails']])
    assert tails.difference(left).area == pytest.approx(0.0, abs=1e-9)   # the tails are the left board's


def test_paint_is_the_lid_minus_the_foil_and_relief_is_the_band(res):
    foil = unary_union([Polygon(m['points']) for m in res['marks'] if 'foil' in m['finishes']])
    paint = _area(res['regions']['paint'])
    assert paint + foil.area == pytest.approx(LID, abs=0.01)
    assert unary_union([Polygon(r) for r in res['regions']['paint']]).intersection(foil).area < 1e-3          # coordinates are rounded to 1e-6 mm
    band = box(SPEC['seam_x0_mm'], 0, SPEC['seam_x1_mm'], 120)
    assert _area(res['regions']['relief']) == pytest.approx(band.area)
    assert _area(res['regions']['footprint']) == pytest.approx(band.area)
    assert foil.difference(band).area < 1e-9                      # nothing leaves the seam zone
    assert res['measures']['relief_pct'] == pytest.approx(14.0)


def test_foil_limits_by_construction(res):
    bars = [m for m in res['marks'] if 'foil' in m['finishes'] and len(m['points']) == 4
            and abs(m['points'][1][0] - m['points'][0][0] - SPEC['line_mm']) < 1e-5]
    assert len(bars) == 6 * res['measures']['engine_turning']['bars_per_tail']
    xs = sorted({round(b['points'][0][0], 6) for b in bars})
    assert np.diff(xs) == pytest.approx(SPEC['pitch_mm'])         # one phase, the stated pitch
    lim = res['measures']['foil_limits']
    assert lim['holds'] and lim['min_line_mm'] >= 0.1 and lim['min_gap_mm'] >= 0.28 - 1e-9
    assert lim['gap_bar_to_outline_min_mm'] >= SPEC['inset_mm'] - 1e-6
    assert res['measures']['lines_per_cm_densest']['value'] == pytest.approx(25.0)


def test_no_emboss_and_refusals():
    flat = orn_c2.tashiq(**dict(SPEC, emboss=False))
    assert flat['regions']['relief'] == [] and not any('emboss' in m['finishes'] for m in flat['marks'])
    for bad in (dict(slope=3.0), dict(line_mm=0.05), dict(pitch_mm=0.25), dict(inset_mm=0.1), dict(tails=1),
                dict(seam_x1_mm=80.0)):
        with pytest.raises(ValueError):
            orn_c2.tashiq(**dict(SPEC, **bad))


def test_engine_render_measures(res, tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.pipeline.services import finish_proof as fp
    ai = tmp_path / 'c2.ai'
    emit_pdf_ai(orn_c2.document(res, **COLOURS), str(ai))
    assert fp.foil_limits(ai)['holds']
    cov = fp.coverage(ai)
    assert cov['relief_pct'] == pytest.approx(14.0, abs=0.05)
    assert cov['foil_and_metallic_pct'] == pytest.approx(res['measures']['foil_ink_pct'], abs=0.1)
    masks = fp.plate_masks(ai, px_per_mm=40.0)
    foil = np.zeros_like(masks[0]['mask'])
    for m in masks:
        if m['kind'] == 'foil':
            foil |= m['mask']
    dens = fp.line_density(foil, px_per_mm=40.0)
    assert dens['max_lines_per_cm'] >= 12.0 and math.isclose(dens['max_lines_per_cm'], 25.0, abs_tol=0.5)
