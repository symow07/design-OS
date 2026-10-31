"""counter_tray_header 1.0 — the counter display at production grade (owner, 2026-10-28): every case of the
qualification matrix passes the fold, strength, sightline and trade-rule checks and the comparison against the house's
measured display dies; each check catches its planted fault; the die-maker's files carry their layers. $0."""
import json
import math

import pytest
from shapely.affinity import translate

from apps.dielines.geometry import counter_display as cd

BOTTLE = dict(product_width_mm=15, product_depth_mm=15, product_height_mm=100, width_mm=113, header_height_mm=80,
              front_height_mm=20, clearance_mm=0.5)
MATRIX = {
    'bottle 1×4 flat, E-flute': dict(BOTTLE, product='bottle', board='e_flute', rows=1, columns=4, count=4,
                                      depth_mm=60, height_mm=170),
    'jar 1×3 flat, SBS 1.5': dict(product='jar', board='sbs_1_5', product_width_mm=40, product_depth_mm=40,
                                   product_height_mm=35, rows=1, columns=3, count=3, width_mm=160, depth_mm=70,
                                   height_mm=150, header_height_mm=70, front_height_mm=18, clearance_mm=0.5),
    'palette 1×2 flat, white card': dict(product='palette', board='white_card_0_5', product_width_mm=70,
                                          product_depth_mm=50, product_height_mm=12, rows=1, columns=2, count=2,
                                          width_mm=170, depth_mm=80, height_mm=120, header_height_mm=60,
                                          front_height_mm=8, clearance_mm=0.5),
    'stick 3×4 tiered, E-flute': dict(product='stick', board='e_flute', product_width_mm=20, product_depth_mm=20,
                                       product_height_mm=80, rows=3, columns=4, count=12, width_mm=130,
                                       depth_mm=110, height_mm=230, header_height_mm=80, front_height_mm=20,
                                       clearance_mm=0.5, row_seat_z_mm=[1.5, 40, 80]),
    'bottle 3×4 tiered, SBS 1.5': dict(BOTTLE, product='bottle', board='sbs_1_5', rows=3, columns=4, count=12,
                                        depth_mm=85, height_mm=240, header_height_mm=85.7, row_seat_z_mm=[1.5, 45, 90]),
}


@pytest.fixture(scope='module')
def flat():
    return cd.solve(**MATRIX['bottle 1×4 flat, E-flute'])


@pytest.mark.parametrize('case', sorted(MATRIX))
def test_every_case_of_the_matrix_passes_all_five_reports(case):
    result = cd.qualify(cd.solve(**MATRIX[case]))
    failed = {name: [row for row in report.get('checks', report.get('rows', [])) if not row.get('ok', True)]
              for name, report in result['reports'].items() if not report['passed']}
    assert result['passed'], failed
    assert set(result['reports']) == {'fold', 'strength', 'sightline', 'trade_rules', 'comparison'}


def test_the_header_is_the_back_panels_own_board_doubled_and_its_shopper_leaf_is_printed(flat):
    die = cd.build_die(flat)
    tray = next(part for part in die.parts if part.name == 'tray')
    faces = {name: (polygon, printed) for name, polygon, printed in tray.faces}
    assert faces['header front'][1] and faces['header back'][1]
    assert 'back / header' not in {name for name, _ in tray.creases}                 # no hinge: one board
    back, front = faces['header back'][0], faces['header front'][0]
    t = flat['inputs']['board_mm']
    assert math.isclose((back.bounds[3] - back.bounds[1]) - (front.bounds[3] - front.bounds[1]), t)   # closes flat
    assert faces['header front'][0].bounds[1] > faces['header back'][0].bounds[1]      # the folded-over leaf


def test_every_fold_carries_its_compensation_and_the_board_presets_are_measured_conventions(flat):
    folds = {row['fold']: row['allowance_mm'] for row in flat['production']['compensation']}
    assert folds['header fold (180°)'] == flat['inputs']['board_mm'] and folds['holder legs'] == 1.5
    assert {key: preset['fold_allowance_mm'] for key, preset in cd.BOARDS.items()} == {
        'e_flute': 1.5, 'sbs_1_5': 1.5, 'white_card_0_5': .5}                         # inset = one caliper (refs)


def test_glue_zones_stand_clear_of_their_creases_and_bleed_only_runs_past_printed_faces(flat):
    die = cd.build_die(flat)
    tray = next(part for part in die.parts if part.name == 'tray')
    creases = {name: line for name, line in tray.creases}
    for name, zone in die.glue:
        if name.endswith('glue flap') and not name.startswith(('holder', 'seat')):
            assert zone.distance(creases[name.replace('flap', 'fold')]) >= cd.RULES['glue_free_crease_mm'] - .01  # cap chords
    bleed = cd.bleed_area(tray)
    floor = next(f for n, f, _ in tray.faces if n == 'floor')
    assert not bleed.contains(floor.centroid) and bleed.contains(floor.buffer(1.0).boundary)   # ink stops 1 mm in
    assert len(cd.layer_geometry(die)['bleed']) > len(die.parts)                       # its inner rings drawn too


def test_the_locks_hold_every_lean_under_three_degrees_where_day_12s_keys_allowed_25(flat):
    report = cd.strength_check(flat)
    assert report['passed'] and max(row['lean_deg'] for row in report['lean']) < 3.0
    looser = dict(flat, geometry=dict(flat['geometry'], holder_height_mm=3.0))
    assert not cd.strength_check(looser)['passed']                                    # a short insert leans too far


def test_each_check_catches_its_planted_fault(flat):
    die = cd.build_die(flat)
    tray = next(part for part in die.parts if part.name == 'tray')
    slot = next(s for s in tray.slots if s['id'] == 'header lock slot')
    slot['polygon'] = translate(slot['polygon'], 0, 4)                                 # the slot off its landing
    assert not cd.fold_check(flat, die)['passed']
    die = cd.build_die(flat)
    tray = next(part for part in die.parts if part.name == 'tray')
    crease = next(line for name, line in tray.creases if name == 'floor / left')
    end = crease.coords[-1]
    ct = cd
    tray.slots.append({'id': 'planted', 'polygon': ct._rect(end[0] - 4, end[1] + 1.5, end[0] - 2, end[1] + 3)})
    assert not cd.trade_rules(flat, die)['passed']                                    # a cut 1.5 mm off a crease end
    hinged = cd.build_die(flat)
    tray = next(part for part in hinged.parts if part.name == 'tray')
    tray.creases.append(('back / header', ct._seg(0, 0, 1, 0)))
    assert not cd.strength_check(flat, hinged)['passed']                              # a hinge under the header


def test_the_die_makers_files_carry_their_layers_and_read_back(flat, tmp_path):
    from apps.dielines.exporters import counter_display_files as files
    out = files.write_all(flat, tmp_path)
    assert out['pdf_layers'] == list(files.LAYERS)
    declared = files.layers_of(str(tmp_path / 'die.pdf'))
    assert {name for name, row in declared.items() if not row['prints']} == {'GLUE', 'SAFE', 'BLEED', 'DIMENSIONS'}
    import fitz
    with fitz.open(tmp_path / 'die.pdf') as doc:
        page = doc[0]
        assert abs(page.rect.width * 25.4 / 72 - cd.build_die(flat).sheet_w) < .01        # true 1:1 mm
        assert b'CutContour' in doc.tobytes() and b'Crease' in doc.tobytes()
    assert (tmp_path / 'die.dxf').read_bytes().count(b'\r\n') > 100                     # CRLF, as DXF expects
    dxf = (tmp_path / 'die.dxf').read_text().splitlines()
    assert dxf[:8] == ['0', 'SECTION', '2', 'HEADER', '9', '$ACADVER', '1', 'AC1009'] and dxf[-1] == 'EOF'
    pairs = list(zip(dxf[::2], dxf[1::2]))
    layers = {value for code, value in pairs if code == '8'}
    assert {'CUT', 'CREASE', 'GLUE', 'BLEED', 'DIMENSIONS'} <= layers and out['dxf']['entities'] > 100
    cf2 = (tmp_path / 'die.cf2').read_text().splitlines()
    assert cf2[:2] == ['$BOF', 'V2'] and cf2[-1] == '$EOF' and 'UM' in cf2
    kinds = {line.split(',')[2] for line in cf2 if line.startswith('L,')}
    assert kinds == {'1', '2'} and out['cf2']['verified_by_a_die_shop'] is False
    best = out['nest']['best']
    assert best['sets'] >= 1 and 0 < best['yield'] < 1
    with fitz.open(tmp_path / 'assembly.pdf') as doc:
        text = doc[0].get_text()
    assert all(word in text for word in ('Flat die', 'Folded, front', 'Folded, side', 'Exploded', 'W 113.0'))


def test_the_registry_carries_1_0_production_ready_and_carton_choosers_never_offer_it():
    from apps.dielines import registry
    defn = cd.template_definition()
    assert defn.key == 'counter_tray_header/1.0' and defn.production_ready and not defn.provisional
    assert defn.geometry_module == 'apps.dielines.geometry.counter_display'
    assert registry.resolve('counter_tray_header', '1.0') is defn                       # the stand die by its number
    with pytest.raises(registry.UnknownTemplate):                                       # 0.1 archived: no current
        registry.resolve('counter_tray_header')
    assert 'counter_tray_header' not in {d.template_id for d in registry.production_templates()}


def test_the_comparison_names_every_difference_with_its_reason(flat):
    report = cd.compare(flat)
    assert report['passed'] and len(report['references']) == 8
    assert all(row['agrees'] or row['why'] for row in report['rows'])
    assert {row['convention'] for row in report['rows'] if row['agrees']} >= {'fold compensation', 'dust flaps'}


def test_the_die_comes_first_and_is_applied_again_to_a_painting_exactly(tmp_path):
    """The stand is designed flat (owner, 2026-10-28): the template's transparent area is exactly the printed faces and
    their bleed, with nothing drawn inside it; a painting that drifts 5, 3 px and paints past the die is caught by the
    proof, and after the die is applied again nothing off the paint differs from the template; the 1:1 PDF reads back
    on the engine's cut and crease; the folds where printed art meets printed art are all found."""
    import numpy as np
    from PIL import Image
    from apps.dielines.exporters import counter_display_files as files
    record = cd.solve(**MATRIX['bottle 3×4 tiered, SBS 1.5'])
    die = cd.build_die(record)
    frame = files.flat_frame(die)
    up = {'front panel': 0, 'right side': 1, 'left side': 3, 'back panel': 2, 'header back': 2, 'header front': 0}
    made = files.flat_template(die, frame, tmp_path, up=up)
    template = np.asarray(Image.open(tmp_path / made['template']))
    masks = files.flat_masks(die, frame)
    assert ((template[..., 3] == 0) == masks['paint']).all() and masks['paint'].any()
    assert (template[masks['paint']][:, :3] == 255).all()                   # nothing inside a painted area
    assert set(masks['names']) == {name for name, _face, printed in die.parts[0].faces if printed}
    assert Image.open(tmp_path / made['sheet']).size == (frame['canvas_px'][0], frame['canvas_px'][1] + 64)
    shifted = np.roll(np.roll(masks['paint'], 3, axis=0), 5, axis=1)
    raw = np.where(shifted[..., None], np.array([30, 40, 90], np.uint8), template[..., :3]).astype(np.uint8)
    raw[4:30, 4:200] = (200, 30, 30)                                         # paint past the die
    flat, art = files.apply_die(raw, template, masks['paint'])
    proof = files.die_proof(raw, template, flat, masks['paint'], masks['owner'], masks['names'])
    assert proof['registration']['best_shift_px'] == [5, 3] and proof['registration']['iou_at_best'] > .99
    assert proof['outside']['differing_from_template'] == 0 and proof['outside']['zero_offset']
    assert ((art[..., 3] == 255) == masks['paint']).all()
    Image.fromarray(art, 'RGBA').save(tmp_path / 'art.png')
    box = files.flat_box_mm(frame)
    files.write_pdf(die, record, tmp_path / 'die.pdf', {'path': tmp_path / 'art.png', 'box_mm': box})
    back = files.pdf_readback(tmp_path / 'die.pdf', die, record, box)
    assert back['CUT']['max_mm'] < .01 and back['CREASE']['max_mm'] < .01 and back['ARTWORK']['max_mm'] < .01
    seams = {(row['seam'], row['kind']) for row in files.fold_pairs(die, frame)}
    assert seams == {('back panel | header back', 'same board, no fold'), ('header back | header front', 'crease'),
                     ('front panel | left side', 'folded corner'), ('front panel | right side', 'folded corner'),
                     ('back panel | left side', 'folded corner'), ('back panel | right side', 'folded corner')}

# --- the stand from the brief: the stand adapter's two tests that hold on 1.0, moved with it from
# test_counter_tray_header.py (the consolidation of 2026-10-28) -----------------------------------------------------

def _observed_row_fixture():
    return {'image_size_px': [800, 800], 'stand': {'rows': 2, 'columns': 3, 'count': 6,
        'bottles': [{'row': row, 'column': column,
                     'box_px': [100 + 30*column, 200 if row == 0 else 184,
                                120 + 30*column, 600 if row == 0 else 204]}
                    for row in range(2) for column in range(3)]},
        'panels': {'stand_header': {'crop_px': [80, 100, 220, 184]},
                   'stand_base': {'crop_px': [80, 612, 220, 642]}}}


@pytest.mark.parametrize('missing', ['bottle', 'base', 'full_front', 'consistent_cap_tops'])
def test_round_files_stand_reports_insufficient_seat_evidence_without_inventing_rises(missing):
    from apps.dielines.geometry.counter_display import solve_stand
    from apps.pipeline.services.round_designer import gloss_brief
    inspection = _observed_row_fixture()
    if missing == 'bottle':
        inspection['stand']['bottles'].pop()
    elif missing == 'base':
        inspection['panels']['stand_base'].pop('crop_px')
    elif missing == 'full_front':
        inspection['stand']['bottles'][0]['box_px'][3] = 620
    else:
        inspection['stand']['bottles'][3]['box_px'][1] = 202
    result = solve_stand(gloss_brief(), inspection)
    assert not result['observed_row_placement']['applied']
    assert result['observed_row_placement']['reason']
    assert 'row_platforms' not in result['record']['geometry']
    assert result['front_elevation']['platform_fronts'] == []
    assert all(hole['seat_z_mm'] == 1.5 for hole in result['record']['holes'])


def test_round_files_stand_rounds_provisional_minimum_above_float_cancellation():
    from apps.dielines.geometry.counter_display import solve_stand
    from apps.pipeline.services.round_designer import gloss_brief
    brief = gloss_brief()
    inspection = {'stand': {'rows': 3, 'columns': 4, 'count': 12},
                  'panels': {'stand_header': {'crop_px': [100, 20, 180, 115]},
                             'stand_base': {'crop_px': [100, 120, 180, 144]}}}
    result = solve_stand(brief, inspection, include_enclosure=True)
    assert result['valid'], result['fold_check']['failed']
    geometry = result['record']['geometry']
    assert geometry['header_height_mm'] == 127.0625
    assert geometry['front_panel_height_mm'] == 32.1
    assert geometry['back_panel_height_mm'] >= geometry['front_panel_height_mm']
    assert 0 < result['dimensions_mm']['height'] - 160.6625 < 1e-10
    assert result['dimension_adjustments'][-1]['dimension'] == 'height'
    brief['stand']['provisional'] = False
    with pytest.raises(ValueError, match='no usable floor, walls or header'):
        solve_stand(brief, inspection, include_enclosure=True)


# --- the sightline fixed inside the ruled size (the owner's goal and ruling of 2026-10-29) ----------------------------

ROUND3 = __import__('pathlib').Path(__file__).resolve().parents[4] / 'docs/rounds/lip-gloss-product-and-counter-stand-9634b86f91/files'


def _round3_brief():
    from apps.pipeline.services.round_files_gate import execution_brief
    return execution_brief(json.loads((ROUND3 / 'inputs.json').read_text())['brief'])


def test_round_3s_stand_shows_every_top_band_and_the_headers_safe_area_inside_its_ruled_size():
    """Round 3's die read from D2 (225 mm, header leaf 107 × 78.2: the owner's ruling) failed its sightline on rows 2 and
    3 (0.538, 0.615). Solved again it keeps the size and moves only the seats: every product's top 25 mm band is seen
    from the engine's eye and the rear caps stay inside the header's 3 mm safe margin; the fold check holds."""
    inspection = json.loads((ROUND3 / 'inspection.json').read_text())
    result = cd.solve_stand(_round3_brief(), inspection)
    adjustment, sight = result['rear_visibility_adjustment'], result['sightlines']
    assert result['dimensions_mm']['height'] == pytest.approx(225.0247, abs=1e-3)
    assert result['header_mm'] == pytest.approx([107.0, 78.2491], abs=1e-3)
    assert adjustment['keep_size'] and adjustment['original_seats_mm'] == pytest.approx([19.7019, 28.2265, 39.0462])
    assert adjustment['final_seats_mm'][1] > 28.2265 and adjustment['final_seats_mm'][2] > 39.0462
    assert sight['passed'] and all(row['visible_fraction'] == 1.0 for row in sight['products'])
    assert sight['header_clear'] and 0 < sight['header']['covered_mm'] <= cd.SAFE_MM
    assert sight['seats_changed'] and result['valid']
    # the highest front seat that holds: 0.1 mm higher, the header's safe area would be covered
    higher = [adjustment['final_seats_mm'][0] + 0.1] + adjustment['original_seats_mm'][1:]
    grid = result['record']
    trial = cd.solve_product_tray(**dict(grid['inputs'], **grid['layout'], hole_shape=grid['hole_shape'],
                                         top_edge=grid['top_edge'], row_seat_z_mm=higher))
    raised = cd.product_tray_raise_rear(trial, keep_size=True)
    assert raised['final_seats_mm'][0] <= adjustment['final_seats_mm'][0] + 1e-9


def test_from_the_brief_alone_the_rows_rise_by_the_rule_and_the_change_is_listed():
    """The owner's part 2 (2026-10-31, §4) over the earlier "no rise nobody measured": from the brief alone (no picture), every row
    rises until each product and the header are seen, on the family's template, and the size it took is listed."""
    result = cd.solve_stand(_round3_brief(), None)
    assert result['record']['schema'] == cd.TEMPLATE_SCHEMA
    assert result['sightlines']['passed'] and result['sightlines']['header_clear']
    seats = sorted({hole['seat_z_mm'] for hole in result['record']['holes']})
    assert len(seats) == 3 and seats[0] == 1.5
    assert any(row['dimension'] == 'height' and row['from_mm'] == 160.0 for row in result['dimension_adjustments'])


def test_a_stand_read_from_a_picture_keeps_the_die_it_was_read_with():
    """Round 3's kind: a picture's reading stays on 1.0, and its rows on the floor still say so; nothing moves it but the owner."""
    assert cd.stand_type({'stand': {}}, {'panels': {}}) is None
    assert cd.stand_type({'stand': {}}, None) == 'counter_tray_header'
    assert cd.stand_type({'stand': {'type': 'tester_unit'}}, {'panels': {}}) == 'tester_unit'


def test_the_header_cover_is_measured_from_the_engines_eye():
    """Negative control: a product raised to the header's lower edge covers it by more than the safe margin."""
    result = cd.solve_stand(_round3_brief(), json.loads((ROUND3 / 'inspection.json').read_text()))
    record = json.loads(json.dumps(result['record']))
    eye = result['sightlines']['eye_mm']
    lower = record['inputs']['height_mm'] - record['inputs']['header_height_mm']
    for hole in record['holes']:
        hole['seat_z_mm'] = lower - record['inputs']['product_height_mm'] + 10
    cover = cd.product_tray_header_cover(record, eye)
    assert not cover['clear'] and cover['covered_mm'] > cd.SAFE_MM


def test_round_3s_d2_gives_a_rounded_header_and_a_blue_board():
    """Golden (the owner's goal of 2026-10-29, the shape check): round 3's D2 has a quarter-circle header on blue
    board; the die drew a square header on white board. Read from the picture, the header is cut to its curve
    (the doubled leaf mirrored about a fold kept straight) and the board's ground is the picture's blue."""
    inspection = json.loads((ROUND3 / 'inspection.json').read_text())
    result = cd.solve_stand(_round3_brief(), inspection, picture=ROUND3 / 'source.png')
    check = result['shape_check']
    assert check['header']['picture']['shape'] in ('quadrant', 'rounded', 'arched')
    assert check['header']['picture']['iou'] >= cd.HEADER_IOU_MIN and check['header']['result'].startswith('fixed')
    assert result['record']['geometry']['header_outline']['shape'] == check['header']['picture']['shape']
    r, g, b = (int(result['record']['production']['board_ground_hex'][i:i + 2], 16) for i in (1, 3, 5))
    assert b > r and b > g and check['ground']['result'].startswith('fixed')               # blue
    tray = next(part for part in cd.build_die(result['record']).parts if part.name == 'tray')
    header = next(f for n, f, _ in tray.faces if n == 'header front')
    box = (header.bounds[2] - header.bounds[0]) * (header.bounds[3] - header.bounds[1])
    assert header.area < 0.95 * box                                                       # cut to its curve
    fold = next(c for n, c in tray.creases if n == 'header fold')
    assert 10 <= fold.length < header.bounds[2] - header.bounds[0]                         # a fold kept straight
    assert result['valid'] and result['header_mm'] == pytest.approx([107.0, 78.2491], abs=1e-3)


def test_a_square_header_reads_square_and_the_die_stays_as_it_was():
    """Negative control: a square header in the reading is matched, not changed."""
    inspection = {'panels': {'stand_header': {'crop_px': [0, 0, 100, 80],
                                              'print_polygon_px': [[0, 0], [100, 0], [100, 80], [0, 80]]}}}
    assert cd.read_header_outline(inspection)['shape'] == 'square'
