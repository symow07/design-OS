"""The stand family (owner's part 2, 2026-10-31): every template's proofs, read from the die folded, and the owner's golden bad cases."""
from __future__ import annotations

import copy

import pytest
from shapely.affinity import translate

from apps.dielines.geometry import counter_display as cd
from apps.dielines.geometry import stand_fold as sf
from apps.dielines.geometry import stand_templates as templates
from apps.dielines.geometry import stand_types as types

GLOSS = {'width_mm': 15.0, 'depth_mm': 15.0, 'height_mm': 100.0, 'cap_mm': 30.0}
ROUND_4 = {'width_mm': 110.0, 'depth_mm': 85.0, 'height_mm': 160.0}
CASES = [('counter_tray_header', 3, 4, ROUND_4), ('counter_tray_header', 1, 5, {}), ('counter_tray_header', 4, 6, {}),
         ('stepped_tiered', 3, 4, {}), ('stepped_tiered', 2, 5, {}), ('lid_header_tray', 3, 4, ROUND_4), ('lid_header_tray', 2, 3, {}),
         ('slanted_front', 2, 4, {}), ('slanted_front', 1, 6, {}), ('tester_unit', 1, 4, {}), ('tester_unit', 1, 6, {}),
         ('flat_tray_testers', 3, 4, ROUND_4), ('flat_tray_testers', 2, 6, {}), ('flat_tray_testers', 1, 5, {})]
TEMPLATES = ['counter_tray_header', 'stepped_tiered', 'lid_header_tray', 'slanted_front', 'tester_unit', 'flat_tray_testers']


def solved(name='counter_tray_header', rows=3, columns=4, envelope=None, **options):
    return templates.solve(name, product=GLOSS, rows=rows, columns=columns, envelope=envelope or {}, **options)


@pytest.fixture(scope='module')
def round_4():
    record = solved(envelope=ROUND_4)
    return record, templates.build_die(record), templates.qualify(record)


@pytest.mark.parametrize('case', CASES, ids=lambda case: '%s-%dx%d' % case[:3])
def test_every_template_passes_every_proof_measured_on_its_die_folded(case):
    name, rows, columns, envelope = case
    record = solved(name, rows, columns, envelope)
    report = templates.qualify(record)
    fold = report['fold']
    assert fold['dimensions']['passed'], fold['dimensions']
    assert fold['joints']['passed'], [row for row in fold['joints']['joints'] if not row['ok']]
    assert not fold['collisions'], fold['collisions']
    assert fold['locks']['passed'] and fold['locks']['header_locked'], [row for row in fold['locks']['locks'] if not row['ok']]
    assert fold['fit']['passed'], [row for row in fold['fit']['products'] if not row['ok']]
    assert fold['art']['passed'], fold['art']['faults']
    assert report['sightlines']['passed'] and len(report['sightlines']['eyes']) == 2
    assert all(eye['header']['samples'] > 100 and eye['header']['seen_share'] == 1.0 for eye in report['sightlines']['eyes']), 'the header is measured on every type'
    assert report['grain']['passed'] and report['allowances']['passed'] and report['trade_rules']['passed'], report['trade_rules']
    assert report['rules_file']['passed'], report['rules_file']
    assert report['passed']


def test_every_joint_is_within_the_owners_half_millimetre(round_4):
    rows = round_4[2]['fold']['joints']['joints']
    assert len(rows) >= 15 and all(0.0 <= row['gap_mm'] <= 0.5 for row in rows)


def test_the_closed_size_comes_from_the_die_and_the_envelope_changes_are_listed(round_4):
    record, _die, report = round_4
    assert report['fold']['dimensions']['closed_mm'] == {'width_mm': 110.0, 'depth_mm': record['inputs']['depth_mm'], 'height_mm': record['inputs']['height_mm']}
    changed = {row['measure']: row for row in record['changes']}
    assert changed['height_mm']['from_mm'] == 160.0 and changed['height_mm']['to_mm'] == record['inputs']['height_mm'] > 160.0
    assert changed['depth_mm']['to_mm'] - changed['depth_mm']['from_mm'] <= 2.0, 'the least change that seats three rows'


def test_every_lock_has_a_rule_sized_slot_and_the_header_slots_in_with_barbs(round_4):
    _record, die, report = round_4
    rows = report['fold']['locks']['locks']
    assert {row['kind'] for row in rows} == {'flush', 'through', 'barbed'}
    header = [row for row in rows if 'header' in row['id']]
    assert len(header) == 4 and all(row['head_mm'] > row['slot_mm'][0] for row in header)
    assert all(row['through_mm'] >= 10.0 for row in header)
    tray = next(part for part in die.parts if part.name == 'tray')
    assert [slot['plies'] for slot in tray.slots if slot['id'].startswith('rim slot')] == [2, 2]
    assert all(abs(slot['width_mm'] - 3.3) < 1e-9 for slot in tray.slots if slot['id'].startswith('rim slot'))


def test_every_opening_is_the_product_plus_one_millimetre_and_every_product_sits_on_its_seat(round_4):
    rows = round_4[2]['fold']['fit']['products']
    assert len(rows) == 12
    assert all(row['clearance_mm'] == [1.0, 1.0] and row['above_seat_mm'] == 0.0 and not row['hits'] for row in rows)


def test_the_grain_runs_across_the_main_folds_and_says_which_do_not(round_4):
    report = round_4[2]['grain']
    assert not report['main_folds_along_grain'] and set(report['along_grain']) == {'floor / left', 'floor / right'}


def test_a_tall_header_takes_a_back_brace_that_covers_no_art():
    record = solved(rows=2, columns=3, envelope={'width_mm': 90.0, 'depth_mm': 70.0}, header_height=120.0)
    report = templates.qualify(record)
    die = templates.build_die(record)
    assert record['geometry'].get('brace') and any(part.name == 'brace' for part in die.parts)
    assert report['passed'] and {'brace into the header', 'brace into the back wall'} <= {row['id'] for row in report['fold']['locks']['locks']}


def test_a_lid_tray_closes_as_a_box_with_the_products_under_it_and_tears_to_a_stand():
    record = solved('lid_header_tray', envelope=ROUND_4)
    die = templates.build_die(record)
    report = templates.qualify(record, die)
    ship = report['ship']
    assert ship['passed'] and ship['head_room_mm'] >= 0.0 and ship['closed_mm']['depth_mm'] == 85.0
    folded = sf.fold(die, die.plan)
    assert ('tray', 'front tear') not in folded and ('tray', 'header back') in folded
    tray = next(part for part in die.parts if part.name == 'tray')
    assert {name for name, _line in tray.perfs} == {'front tear line', 'left tear line', 'right tear line'}
    assert die.glue and all(name.endswith('flap') for name, _polygon in die.glue)


def test_leaning_rows_lean_back_toward_the_eye():
    die = templates.build_die(solved('slanted_front', 2, 4))
    for product in die.plan.products:
        axis, front = product['frame'][:3, 2], -product['frame'][:3, 1]
        assert axis[1] > 0.1 and front[2] > 0.1, 'the top goes to the back; the front face looks up'


def test_a_tester_opening_is_wider_and_each_has_a_place_for_its_cap():
    record = solved('tester_unit', 1, 4)
    assert record['inputs']['clearance_mm'] == 2.0
    die = templates.build_die(record)
    collar = next(part for part in die.parts if part.name == 'collar')
    assert sum(slot.get('kind') == 'opening' for slot in collar.slots) == 8 and len(die.plan.products) == 4


def test_no_load_claim_without_its_mark(round_4):
    strength = round_4[2]['strength']
    assert strength['provisional'] and '⟪PROVISIONAL⟫' in strength['words'] and strength['tip']['provisional']


# --- the owner's golden bad cases ------------------------------------------------------------------------------------------

def test_golden_zero_clearance_fails_the_fit():
    record = copy.deepcopy(solved())
    for hole in record['geometry']['holes']:
        hole['w_mm'] = hole['d_mm'] = 15.0
    report = templates.qualify(record)
    assert not report['fold']['fit']['passed'] and not report['passed']


def test_golden_a_header_with_no_lock_fails():
    record = solved()
    die = templates.build_die(record)
    die.plan.locks = [lock for lock in die.plan.locks if 'header' not in lock.id]
    report = templates.qualify(record, die)
    assert not report['fold']['locks']['header_locked'] and not report['passed']


def test_golden_a_product_hidden_by_the_row_in_front_fails_the_sightlines():
    record = copy.deepcopy(solved())
    geometry = record['geometry']
    geometry['seats_z_mm'] = [0.0, 6.0, 12.0]
    geometry['collars_z_mm'] = [20.0, 26.0, 32.0]
    report = templates.qualify(record)
    assert not report['sightlines']['passed']
    blocked = [row for row in report['sightlines']['eyes'][0]['products'] if not row['ok']]
    assert blocked and any(any(name.startswith('product') for name in row['blocked_by']) for row in blocked)


def test_golden_a_stand_whose_header_is_missing_or_hidden_fails_the_sightlines():
    record = solved()
    die = templates.build_die(record)
    folded = sf.fold(die, die.plan)
    report = sf.sightlines_report(die.plan, {key: row for key, row in folded.items() if key[1] != 'header front'}, width=110.0, face_bar_mm=38.0)
    assert not report['passed'] and report['eyes'][0]['header']['why'] == 'the stand has no header'
    low = copy.deepcopy(record)
    low['geometry']['header_top_z_mm'] = low['geometry']['header_top_z_mm'] - 60.0   # the header dropped behind the rear row
    assert not templates.qualify(low)['sightlines']['passed']


def test_golden_a_lock_that_does_not_meet_its_slot_fails():
    record = solved()
    die = templates.build_die(record)
    tray = next(part for part in die.parts if part.name == 'tray')
    slot = next(row for row in tray.slots if row['id'] == 'floor slot front 1')
    slot['polygon'] = translate(slot['polygon'], 0.0, 3.0)
    report = templates.qualify(record, die)
    row = next(row for row in report['fold']['locks']['locks'] if row['id'] == 'front wall into the floor 1')
    assert not row['ok'] and not report['passed']


def test_golden_two_panels_through_each_other_are_found():
    record = copy.deepcopy(solved())
    record['geometry']['back_cap_mm'] = 2.0     # the inner leaf comes back through the stair's own tabs and the header's tongues
    report = templates.qualify(record)
    assert not report['passed']


# --- the rules files ---------------------------------------------------------------------------------------------------------

def test_every_type_has_a_record_and_the_working_ones_are_the_owners_five_in_his_order():
    every = types.all_types()
    assert [row['id'] for row in every if row['status'] == 'working'] == TEMPLATES
    assert {'rotating_carousel', 'floor_stand', 'clip_strip', 'shelf_ready', 'gondola_end', 'power_wing', 'dump_bin', 'pallet_display'} <= {row['id'] for row in every if row['status'] == 'recorded'}
    for row in every:
        for key in ('label', 'one_line', 'for', 'suits', 'panels', 'folds', 'locks', 'allowances', 'limits', 'reinforcement', 'glue', 'faces_to_shopper', 'failures', 'codes', 'sources', 'provisional'):
            assert key in row, (row['id'], key)
        assert row['sources'] and row['provisional'], row['id']


def test_the_rules_file_catches_a_panel_the_die_lost(round_4):
    record, die, _report = round_4
    damaged = copy.deepcopy(die)
    tray = next(part for part in damaged.parts if part.name == 'tray')
    tray.faces = [row for row in tray.faces if row[0] != 'front cap']
    assert 'front cap' in templates.rules_report(record, damaged)['missing']['panels']


def test_the_engine_suggests_by_its_rules_and_the_owner_chooses():
    assert types.suggest(count=12, rows=3, product_height_mm=100)['type'] == 'flat_tray_testers'      # the house's most-used, the owner's part 3
    assert types.suggest(count=20, rows=4, product_height_mm=100)['type'] == 'stepped_tiered'
    assert types.suggest(count=6, rows=1, product_height_mm=100)['type'] == 'slanted_front'
    assert types.suggest(count=4, testers=True)['type'] == 'tester_unit'
    assert types.suggest(count=12, ships_filled=True)['type'] == 'lid_header_tray'


def test_a_brief_with_no_grid_gets_the_squarest_and_the_chain_reads_the_same_shape():
    brief = {'dimensions_mm': {'width': 15.0, 'depth': 15.0, 'height': 100.0, 'cap_height': 30.0}, 'stand': {'count': 12, 'dimensions_mm': {'width': 110.0, 'depth': 85.0, 'height': 160.0}}}
    result = cd.solve_stand(brief, None)
    assert (result['rows'], result['columns']) == (3, 4) and result['record']['schema'] == cd.TEMPLATE_SCHEMA
    assert result['valid'] and result['sightlines']['passed'] and result['sightlines']['header_clear']
    assert result['dimension_adjustments'] and result['front_elevation']['product_slots']
    for row in result['front_elevation']['product_slots']:
        assert row['seat_z_mm'] >= 1.5


# --- the die's files -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('name', TEMPLATES)
def test_every_templates_files_open_in_a_real_reader_and_its_sheets_are_drawn(name, tmp_path):
    from apps.dielines.exporters import counter_display_files as files
    rows, columns = {'slanted_front': (2, 4), 'tester_unit': (1, 4)}.get(name, (3, 4))
    made = files.write_all(solved(name, rows, columns, {'width_mm': 110.0}), tmp_path)
    assert made['qualification']['passed']
    assert made['open_check']['all_open'], made['open_check']
    assert made['open_check']['files']['die.dxf']['reader'].startswith('ezdxf') and 'die maker' in made['open_check']['files']['die.cf2']['reader']
    for name_ in made['files']:
        assert (tmp_path / name_).stat().st_size > 100
    assert made['nest']['best']['sets'] >= 1 and 0.2 < made['nest']['best']['yield'] < 1
    assert not any(row.get('half_turn') is None for row in made['nest']['best']['placements'])
    import fitz
    with fitz.open(tmp_path / 'fold-up.pdf') as doc:
        text = doc[0].get_text()
    assert 'drawing, not a render' in text and all(word in text for word in ('Front', 'Side', 'Top', 'Three-quarter', 'PROVISIONAL'))
    with fitz.open(tmp_path / 'assembly.pdf') as doc:
        text = doc[0].get_text()
    assert '1' in text and 'Lay the tray flat' in text or 'lay the tray flat' in text
    with fitz.open(tmp_path / 'cut-and-fold-1to1.pdf') as doc:
        page = doc[0]
        assert abs(page.rect.width * 25.4 / 72 - 420) < .5 and abs(page.rect.height * 25.4 / 72 - 297) < .5
        assert doc.page_count == made['cut_and_fold']['tiles'] and '50 mm' in page.get_text() and '100 %' in page.get_text()


def test_the_die_has_every_sub_layer_of_the_law_on_every_writer(round_4, tmp_path):
    from apps.dielines.exporters import counter_display_files as files
    from apps.pipeline.services import round_files_export as export
    record, die, _report = round_4
    assert set(export.DIE_SUBLAYERS.values()) == {'CUT', 'CREASE', 'PERF', 'HALF-CUT', 'GLUE', 'SAFE', 'BLEED'}
    law = templates.layer_law(die)
    assert law['passed'] and law['counts']['half_cut'] == 1 and law['counts']['crease'] > 0 and law['counts']['glue'] == 0
    assert files.write_pdf(die, record, tmp_path / 'die.pdf') == list(files.LAYERS)
    assert {'CUT', 'CREASE', 'PERF', 'HALF-CUT', 'GLUE', 'SAFE', 'BLEED'} <= set(files.layers_of(str(tmp_path / 'die.pdf')))
    files.write_dxf(die, record, tmp_path / 'die.dxf')
    import ezdxf
    assert {'CUT', 'CREASE', 'PERF', 'HALF-CUT', 'GLUE', 'SAFE', 'BLEED'} <= {layer.dxf.name for layer in ezdxf.readfile(tmp_path / 'die.dxf').layers}
    files.write_cf2(die, record, tmp_path / 'die.cf2')
    assert files.read_cf2(tmp_path / 'die.cf2')['lines_by_type'].keys() >= {'1', '2', '4'}


def test_a_lid_trays_perforation_and_glue_reach_their_layers(tmp_path):
    from apps.dielines.exporters import counter_display_files as files
    record = solved('lid_header_tray', envelope=ROUND_4)
    die = templates.build_die(record)
    law = templates.layer_law(die)
    assert law['counts']['perf'] == 3 and law['counts']['glue'] == 4 and law['counts']['half_cut'] == 1
    files.write_cf2(die, record, tmp_path / 'die.cf2')
    assert '3' in files.read_cf2(tmp_path / 'die.cf2')['lines_by_type']


def test_the_nest_keeps_the_grain_and_uses_the_trays_waste(round_4):
    from apps.dielines.exporters import counter_display_files as files
    record, die, _report = round_4
    nesting = files.nest(die, record)
    best = nesting['best']
    assert best['yield'] > 0.3
    assert all(row['w_mm'] == pytest.approx(next(part for part in die.parts if part.name == row['part']).outline().buffer(cd.DIE_BLEED_MM, join_style=2).bounds[2]
                                            - next(part for part in die.parts if part.name == row['part']).outline().buffer(cd.DIE_BLEED_MM, join_style=2).bounds[0], abs=.01) for row in best['placements'])


def test_the_house_comparison_says_where_the_die_does_not_beat_the_house(round_4):
    from apps.dielines.exporters import counter_display_files as files
    record, die, report = round_4
    rows = templates.better_than_house(record, report, files.nest(die, record))['rows']
    assert {row['point'] for row in rows} >= {'strength', 'assembly', 'product show', 'material use', 'where it does not beat them'}
    assert any(row['better'] is False for row in rows)


def test_the_type_drawings_exist_for_every_working_type():
    from pathlib import Path
    from django.conf import settings
    for row in types.buildable():
        assert (Path(settings.BASE_DIR) / 'static/img/stands' / (row['id'] + '.svg')).read_text().startswith('<svg')


def test_golden_a_slot_beside_a_fold_fails():
    record = solved()
    die = templates.build_die(record)
    tray = next(part for part in die.parts if part.name == 'tray')
    slot = next(row for row in tray.slots if row['id'] == 'floor slot front 1')
    slot['polygon'] = translate(slot['polygon'], 0.0, -2.0)
    report = sf.slots_report(die, 3.0)
    assert not report['passed'] and report['too_close'][0]['crease'] == 'floor / front'


# --- part 3: the house flat tray with testers, and the rules it brought for every template --------------------------------------------

@pytest.fixture(scope='module')
def flat():
    record = solved('flat_tray_testers', envelope=ROUND_4)
    return record, templates.build_die(record), templates.qualify(record)


def _without(die, plan, folded, *names):
    return {key: row for key, row in folded.items() if key[0] not in names}


def test_the_flat_tray_holds_twelve_at_one_height_and_a_tester_at_each_column(flat):
    record, die, report = flat
    assert report['passed'], report
    assert record['layout'] == {'rows': 3, 'columns': 4, 'count': 12}
    products = die.plan.products
    sealed, testers = [p for p in products if not p['tester']], [p for p in products if p['tester']]
    assert len(sealed) == 12 and len(testers) == 4
    assert sorted(p['column'] for p in testers) == [1, 2, 3, 4]
    assert {round(float(p['frame'][2, 3]), 3) for p in products} == {record['inputs']['board_mm']}       # one height, no steps
    for tester in testers:                                                                                # its tester stands in its column, in front
        column = [p for p in sealed if p['column'] == tester['column']]
        assert len(column) == 3
        assert all(abs(p['frame'][0, 3] - tester['frame'][0, 3]) < 1e-9 for p in column)
        assert all(p['frame'][1, 3] > tester['frame'][1, 3] for p in column)
    assert record['geometry']['web_between_openings_mm'] >= 8.5 and record['geometry']['web_tester_to_row_mm'] == 9.0       # the house's own webs


def test_the_flat_tray_folds_locks_and_fits_a_tester_with_its_wider_clearance(flat):
    record, _die, report = flat
    fold = report['fold']
    assert fold['dimensions']['passed'] and fold['joints']['passed'] and fold['locks']['passed'] and fold['locks']['header_locked'] and not fold['collisions']
    assert fold['fit']['count'] == 16 and fold['fit']['passed']
    clearances = {tuple(row['clearance_mm']) for row in fold['fit']['products']}
    assert clearances == {(1.0, 1.0), (2.0, 2.0)}
    assert len([row for row in fold['locks']['locks'] if 'liner' in row['id']]) == 4
    assert record['inputs']['height_mm'] == 160.0 and not [row for row in record['changes'] if row['measure'] == 'height_mm']      # the brief's height holds


def test_every_shade_shows_its_colour_and_the_report_is_per_shade(flat):
    record, die, report = flat
    shades = report['shades']
    assert shades['passed'] and len(shades['columns']) == 4
    assert all(row['carried_by'] == 'tester' and row['worst_share'] >= .5 for row in shades['columns'])
    names = [{'column': c, 'name': 'Shade %d' % c, 'hex': '#123456'} for c in (1, 2, 3, 4)]
    folded = sf.fold(die, die.plan)
    assert sf.shade_report(die.plan, folded, width=110.0, names=names)['columns'][2]['shade'] == 'Shade 3'


def test_golden_a_tester_missing_from_a_column_fails_that_shade_in_words(flat):
    _record, die, _report = flat
    folded = sf.fold(die, die.plan)
    plan = copy.copy(die.plan)
    plan.products = [p for p in die.plan.products if not (p['tester'] and p['column'] == 2)]
    report = sf.shade_report(plan, folded, width=110.0)
    assert not report['passed']
    row = report['columns'][1]
    assert not row['ok'] and row['carried_by'] == 'nothing' and 'no tester or product' in row['why']
    assert all(other['ok'] for other in report['columns'] if other['column'] != 2)


def test_golden_a_hidden_shade_fails_it():
    record = solved('flat_tray_testers', envelope=ROUND_4, front_height=85.0)          # a front wall so tall it hides each tester's colour
    report = templates.qualify(record)
    assert not report['passed'] and not report['shades']['passed']
    assert all(not row['ok'] and 'colour window' in row['why'] for row in report['shades']['columns'])


def test_a_check_with_no_products_fails_rather_than_passing(flat):
    _record, die, _report = flat
    plan = copy.copy(die.plan)
    plan.products = []
    assert not sf.shade_report(plan, sf.fold(die, die.plan), width=110.0)['passed']


def test_golden_a_bare_inside_wall_fails_the_view(flat):
    record, die, report = flat
    assert report['view']['passed'] and report['view']['points_read'] > 1000
    assert {'left liner / left liner', 'right liner / right liner', 'deck / deck tread 1', 'tray / back inner'} <= set(report['view']['faces_seen'])
    folded = sf.fold(die, die.plan)
    bare = sf.view_report(die.plan, _without(die, die.plan, folded, 'left liner'), die)
    assert not bare['passed']
    assert any(row['face'] == 'tray / left side' and 'unprinted side' in row['kind'] for row in bare['faults'])
    # a face in view with no art on its print side fails too
    plain = copy.copy(die)
    plain.ground_faces = [row for row in die.ground_faces if row != ('deck', 'deck tread 1')]
    faults = sf.view_report(die.plan, folded, plain)['faults']
    assert any(row['face'] == 'deck / deck tread 1' and 'no art' in row['kind'] for row in faults)


def test_inside_faces_the_shopper_sees_are_print_faces_on_the_die(flat):
    _record, die, report = flat
    for wanted in (('left liner', 'left liner'), ('right liner', 'right liner'), ('deck', 'deck tread 1'), ('tray', 'front inner'), ('tray', 'back inner'), ('tray', 'back cap')):
        assert wanted in die.ground_faces
    assert not [row for row in die.ground_faces if ' tab ' in row[1]]
    assert report['slots']['passed'] and report['grain']['passed'] and report['allowances']['passed'] and report['trade_rules']['passed']


def test_testers_off_the_front_product_carries_each_shade():
    record = solved('flat_tray_testers', envelope=ROUND_4, testers=False)
    report = templates.qualify(record)
    die = templates.build_die(record)
    assert len(die.plan.products) == 12 and not record['geometry']['tester_holes']
    assert report['passed'], report['shades']
    assert all(row['carried_by'] == 'product' for row in report['shades']['columns'])


def test_the_flat_tray_is_parametric_in_product_and_grid():
    record = templates.solve('flat_tray_testers', product={'width_mm': 22.0, 'depth_mm': 22.0, 'height_mm': 80.0, 'cap_mm': 20.0}, rows=2, columns=6)
    assert templates.qualify(record)['passed']
    assert len(templates.build_die(record).plan.products) == 18


@pytest.mark.parametrize('name, rows, columns', [('counter_tray_header', 3, 4), ('stepped_tiered', 3, 4), ('lid_header_tray', 3, 4), ('slanted_front', 2, 4), ('tester_unit', 1, 4)])
def test_the_shade_rule_holds_on_every_template_half_of_each_products_window(name, rows, columns):
    record = solved(name, rows, columns)
    report = templates.qualify(record)
    assert record['inputs']['face_bar_mm'] == 66.0                                                   # the 30 mm cap, half of its 70 mm window, one read step
    assert report['shades']['passed'] and report['shades']['worst_share'] >= .5, report['shades']['columns']


def test_a_bar_no_wall_can_meet_fails_and_never_hangs_the_solve(monkeypatch):
    monkeypatch.setattr(templates, 'face_bar', lambda common, height, cap: 100.0)
    record = solved('tester_unit', 1, 4)
    assert not templates.qualify(record)['passed']


def test_the_house_flat_tray_is_the_suggestion_where_nothing_else_is_asked():
    assert types.suggest(count=12, rows=3, product_height_mm=100.0, testers=True)['type'] == 'flat_tray_testers'
    assert types.suggest(count=4, rows=1, product_height_mm=100.0, testers=True)['type'] == 'tester_unit'
    assert types.suggest(count=12, rows=3, product_height_mm=100.0)['type'] == 'flat_tray_testers'
