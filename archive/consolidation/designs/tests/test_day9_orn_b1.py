"""TEMPORARY (Day 9, orn_b1): B-1's Arabic lockup — the face's own outlines, the copy re-extracted word for word, the
shared output form, the lettering switches, the foil limits through the engine, and the services gate. DB-free."""
from __future__ import annotations

import math
import unicodedata
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from apps.pipeline.services import orn_b1 as O
from apps.pipeline.services.lid_devices import zone_mm

ZONE = zone_mm((0.38, 0.13, 0.95, 0.6))       # B-1's arabic_hero zone
BUILD = dict(zone_mm=ZONE, alif_mm=22.0, small_alif_mm=8.0, hatch_angle_deg=0.0, hatch_line_mm=0.30,
             hatch_pitch_mm=0.62, contour_mm=0.4, keyline_mm=1.0, keyline_hex='#22205A', fill_hex='#22205A',
             emboss_inset_mm=0.3, level_uprights=True, lozenge_dot=True, join_mm=6.0)


@pytest.fixture(scope='module')
def built():
    return O.zilal(**BUILD)


def _union(rings):
    return unary_union([Polygon(r) for r in rings])


def test_the_shaped_text_reextracts_to_the_descriptor_in_reading_order(built):
    face = O.face()
    font, glyph_set = O._glyph_set(face['path'])
    words = [O.set_word(face['path'], glyph_set, w, tol_units=1.0) for w in (O.ABOVE, O.HERO, O.BELOW)]
    font.close()
    assert O.reextract(words) == 'باليت ظلال العيون' == O.DESCRIPTOR
    assert O.reextract(words[::-1]) != O.DESCRIPTOR          # the order is read, not assumed
    # every glyph is a presentation form or a letter named by its code point, and ظلال keeps its lam-alef ligature
    names = [g['name'] for g in words[1]]
    assert 'uniFEFC' in names and unicodedata.name(chr(0xFEFC)).startswith('ARABIC LIGATURE LAM WITH ALEF')
    # the build's own record says the same, from its own shaping
    assert built['measures']['text']['reextracted'] == O.DESCRIPTOR
    assert built['measures']['text']['reading_order'] == [O.ABOVE, O.HERO, O.BELOW]


def test_the_outlines_are_the_faces_own(built):
    face = O.face()
    assert face['postscript'] == 'ElMessiriPF-Bold' and 'Open Font License' in face['licence']
    assert built['measures']['face']['sha256'] == face['sha256']
    # the alif sets the scale: 22 mm over the isolated alif's own height in font units
    m = built['measures']['face']
    assert math.isclose(m['mm_per_unit_hero'] * m['alif_units'], 22.0, rel_tol=1e-9)


def test_the_output_form(built):
    assert set(built) == {'kind', 'marks', 'regions', 'params', 'measures'}
    for mk in built['marks']:
        assert set(mk) == {'points', 'closed', 'width', 'ink', 'fill', 'finishes'}
        assert mk['ink'] in ('rose_gold_foil', 'blind') or mk['ink'].startswith('ink:#')
        assert set(mk['finishes']) <= {'foil', 'emboss', 'deboss'}
        assert ('foil' in mk['finishes']) == (mk['ink'] == 'rose_gold_foil')
        assert mk['width'] >= 0.0 and len(mk['points']) >= 2
    for name in ('paint', 'relief', 'footprint', 'calm'):
        assert built['regions'][name], name
        for ring in built['regions'][name]:
            assert Polygon(ring).is_valid and not Polygon(ring).interiors
    assert {k: v for k, v in O.BUILD_PARAMS.items() if k != 'zone_mm'} == {k: v for k, v in BUILD.items()
                                                                          if k != 'zone_mm'}
    assert all(math.isclose(a, b) for a, b in zip(O.BUILD_PARAMS['zone_mm'], ZONE))
    assert built['measures']['densest_geometric']['lines_per_cm'] >= 16.0
    for key, value in BUILD.items():
        assert built['params'][key] == (list(value) if key == 'zone_mm' else value)


def test_the_regions_agree(built):
    r = built['regions']
    paint, foot, calm, relief = (_union(r[k]) for k in ('paint', 'footprint', 'calm', 'relief'))
    assert paint.intersection(foot.buffer(O.PAINT_GROW_MM - 0.01)).area < 1e-6
    assert box(*ZONE).buffer(1e-6).contains(paint)
    assert calm.buffer(1e-6).contains(foot.buffer(O.CALM_GROW_MM - 0.01))
    assert foot.buffer(1e-6).contains(relief)
    assert built['measures']['fits_zone']
    # the lockup is flush right in its zone
    assert math.isclose(foot.bounds[2], ZONE[2], abs_tol=1e-6)


def test_the_lettering_switches(built):
    ops = built['measures']['operations']
    assert built['measures']['uprights_height_mm'] == [22.0, 22.0, 22.0, 22.0]
    assert any(row['lift_units'] > 0 for row in ops['level'])           # the short alef of لا raised
    assert math.isclose(ops['lozenge']['dot_area_units2'], ops['lozenge']['lozenge_area_units2'], rel_tol=1e-6)
    assert ops['crowns']['count'] == 4 and ops['join']['mm'] == 6.0
    plain = O.zilal(**dict(BUILD, level_uprights=False, lozenge_dot=False, join_mm=0.0))
    assert plain['measures']['operations'] == {}
    assert sorted(plain['measures']['uprights_height_mm']) == [17.3, 22.0, 22.0, 22.0]
    assert plain['measures']['hero_mm']['width'] < built['measures']['hero_mm']['width']


def test_the_alternatives_keep_working():
    alt = O.zilal(**dict(BUILD, alif_mm=26.0, hatch_angle_deg=45.0, join_mm=0.0))
    m = alt['measures']
    assert m['hatch']['phase_rule'].startswith('the least disturbed')
    assert m['uprights_height_mm'] == [26.0, 26.0, 26.0, 26.0]
    # at 26 mm the lockup is about 2 mm taller than the zone at each end: measured and said, never hidden
    assert not m['fits_zone'] and m['lockup_bounds_mm'][3] - m['lockup_bounds_mm'][1] > ZONE[3] - ZONE[1]
    assert m['foil_limits_geometric']['thinner_than_line_mm2'] < 0.05
    with pytest.raises(ValueError):
        O.zilal(**dict(BUILD, hatch_pitch_mm=0.45))                      # a 0.15 mm gap is under the foil limit


def test_the_hatch_is_locked_and_within_the_limits_by_construction(built):
    h = built['measures']['hatch']
    assert h['lines_per_cm'] >= 16.0 and h['gap_mm'] >= 0.2 and h['line_mm'] >= 0.1
    assert h['locked']['edge_gap_mm'] >= O.FOIL_GAP_MIN_MM
    g = built['measures']['foil_limits_geometric']
    assert g['thinner_than_line_mm2'] < 0.05 and g['narrower_than_gap_mm2'] < 0.2   # curve-tip dust only


def test_through_the_engine_the_foil_limits_hold(built, tmp_path):
    record = O.prove(built, out_dir=tmp_path, key='b1', ground_hex='#22205A', rose_gold_hex='#C99A84')
    engine = record['engine']
    assert engine['foil_limits']['holds']
    plates = {p['plate']: p for p in engine['coverage']['plates']}
    assert set(plates) == {'FOIL_ROSE_GOLD', 'EMBOSS'}
    assert math.isclose(plates['FOIL_ROSE_GOLD']['area_pct'], built['measures']['foil_ink_pct'], abs_tol=0.1)
    assert math.isclose(plates['EMBOSS']['area_pct'], built['measures']['relief_pct'], abs_tol=0.1)
    assert engine['line_density_in_stem']['max_lines_per_cm'] >= 12.0
    # the shared reader's 10 mm window over the whole lid reads below the 12/cm floor: stems ~3.5 mm wide cannot fill
    # three quarters of a 10 mm window. Recorded as it reads, for the orchestrator to rule on.
    assert engine['line_density']['max_lines_per_cm'] < 12.0 and not engine['line_density']['meets_d9_3']
    for name in ('b1.png', 'b1-proof.png', 'b1.json', 'b1.ai'):
        assert (tmp_path / name).is_file()


def test_the_module_adds_no_gate_key():
    from apps.pipeline.tests.test_palette_statistics import composed_gate
    assert composed_gate(Path(O.__file__).read_text()) == set()
