"""Execution-file fixtures: real PDF operators, fonts, layers and spot separations."""
import json
import os
from copy import deepcopy
from pathlib import Path
import time

import fitz
from PIL import Image, ImageDraw
import pytest

from apps.pipeline.services import round_files_export as export


def object_spec(directory, kind='bottle'):
    directory.mkdir(parents=True, exist_ok=True)
    sizes = {'bottle': [15, 70], 'cap': [15, 30], 'stand': [110, 160]}
    width, height = sizes[kind]
    plate = directory / (kind + '-art.png')
    image = Image.new('RGBA', (180, 600), (255, 255, 255, 0) if kind != 'stand' else (50, 40, 35, 255))
    if kind == 'stand':
        ImageDraw.Draw(image).rectangle([30, 30, 50, 60], fill=(0, 0, 0, 0))
    image.save(plate)
    foil = directory / 'foil.svg'
    foil.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                    '<path fill="#000000" fill-rule="evenodd" d="M0 0H10V10H0Z M3 3H7V7H3Z"/></svg>')
    if kind == 'cap':
        runs = [{'copy': 'GLASS', 'box_mm': [1, 3, 5, 27], 'size_pt': 7, 'face': 'latin', 'rotation': 90, 'foil': True}]
        logos = [{'box_mm': [6, 3, 13, 27], 'rotation': 270, 'foil': True}]
    else:
        runs = [{'copy': 'Lip Gloss', 'box_mm': [1, height - 18, width - 1, height - 13], 'size_pt': 6, 'face': 'latin'},
                {'copy': 'ملمع شفاه', 'box_mm': [1, height - 12, width - 1, height - 6], 'size_pt': 6, 'face': 'arabic'}]
        logos = [{'box_mm': [1, 1, width - 1, 6], 'foil': True}]
    return {'id': kind, 'title': kind + ' fixture', 'size_mm': [width, height],
            'trim_box_mm': [0, 0, width, height],
            'artwork': [{'path': str(plate), 'box_mm': [0, 0, width, height]}],
            'foil_svg': [{'path': str(foil), 'box_mm': [1, 8, 11, 18]}],
            'foil_paths': [{'points_mm': [[1, height - 3], [width - 1, height - 3]], 'stroke_mm': .2}],
            'type_runs': runs, 'logos': logos,
            'die': {'cut': [{'points_mm': [[0, 0], [width, 0], [width, height], [0, height]], 'closed': True}],
                    'fold': [[[0, height / 2], [width, height / 2]]]},
            'guides': [[[1, 1], [width - 1, 1]]]}


def fourteen_brief():
    """The brief's grid builds the stand (2026-10-27); these fixtures ask for the pictured 2 × 7."""
    from apps.pipeline.services.round_designer import gloss_brief
    brief = gloss_brief()
    brief['stand'].update(count=14, layout={'rows': 2, 'columns': 7})
    return brief


def full_stand_spec(directory):
    from apps.dielines.geometry.counter_display import solve_stand
    inspection = {'stand': {'rows': 2, 'columns': 7, 'count': 14,
        'bottles': [{'row': row, 'column': column, 'box_px': [100 + column * 30,
                    200 if row == 0 else 178, 120 + column * 30, 684 if row == 0 else 204]}
                    for row in range(2) for column in range(7)]},
        'panels': {'stand_header': {'crop_px': [80, 80, 300, 178]},
                   'stand_base': {'crop_px': [80, 697, 300, 725]}}}
    geometry = solve_stand(fourteen_brief(), inspection, include_enclosure=True, rear_visibility=True)
    directory.mkdir(parents=True, exist_ok=True)
    plate = directory/'synthetic-panel.png'
    image = Image.new('RGB', (180, 90), '#984E66')
    ImageDraw.Draw(image).line([(0, 0), (179, 89)], fill='#D5AF59', width=3)
    image.save(plate)
    spec = {'id': 'stand', 'title': 'Synthetic full stand die', 'size_mm': geometry['sheet_mm'],
            'die_visible': True, 'die': geometry['die'],
            'guides': geometry['guides']['safe'] + geometry['guides']['bleed'],
            'artwork': [{'path': str(plate), 'box_mm': face['box_mm']} for face in geometry['surfaces'].values()]}
    return spec, geometry


def assert_full_stand_die(result, geometry):
    assert result['readback']['die_geometry']['holds']
    # the die's own guides are its sub-layers now (the owner, 2026-10-30): SAFE and BLEED beside CUT and CREASE
    assert result['readback']['die_geometry']['expected_paths'] >= sum(len(geometry['die'][key]) for key in ('cut', 'fold'))
    layer = next(row for row in result['readback']['layers'] if row['name'] == 'DIE')
    assert layer['visible'] and layer['locked'] and not layer['printable']
    with fitz.open(result['ai']) as doc:
        shown = [row for row in doc[0].get_drawings() if row['layer'] == 'DIE']
        square_holes = [row for row in shown if abs(row['rect'].width/export.PT-15.5) < .005
                        and abs(row['rect'].height/export.PT-15.5) < .005]
    assert len(shown) == result['readback']['die_geometry']['expected_paths']
    assert len(square_holes) == 14


def test_files_export_full_engine_die_opens_visible_with_fourteen_square_holes(tmp_path):
    spec, geometry = full_stand_spec(tmp_path/'input')
    result = export.export_object(spec, tmp_path/'output', native=False)
    assert_full_stand_die(result, geometry)
    assert result['readback']['raster_count'] == 2
    expected = [item for item in result['elements'] if item['layer'] == 'DIE']
    actual = export._pdf_die_geometry(result['ai'])
    assert not export._die_geometry_check(expected, actual[1:])['holds']
    actual[0]['segments'][0][0][0] += 1
    assert not export._die_geometry_check(expected, actual)['holds']


@pytest.mark.parametrize('basis, palette, components', [
    ('DeviceCMYK', '0040800000FF00FF', 4),
    ('DeviceRGB', 'FF000000FF00', 3),
    ('DeviceGray', '00FF', 1),
])
def test_files_export_indexed_raster_checks_actual_colour_basis(basis, palette, components):
    with fitz.open() as doc:
        page = doc.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 1), False)
        xref = page.insert_image(fitz.Rect(0, 0, 20, 10), pixmap=pixmap)
        doc.xref_set_key(xref, 'ColorSpace', f'[/Indexed /{basis} 1 <{palette}>]')
        doc.update_stream(xref, bytes([0, 1]))
        with fitz.open(stream=doc.tobytes(), filetype='pdf') as fresh:
            colours = export._raster_colour_spaces(fresh)
    assert colours[0]['encoded_components'] == 1
    assert colours[0]['components'] == components
    assert (colours[0]['components'] == 4) == (basis == 'DeviceCMYK')


@pytest.mark.skipif(os.environ.get('ROUND_FILES_NATIVE_FIXTURE') != '1', reason='Explicit local Illustrator fixture only')
def test_files_export_full_stand_die_visible_after_actual_native_reopen(tmp_path):
    destination = Path(os.environ.get('ROUND_FILES_NATIVE_FIXTURE_DIR', str(tmp_path))) / 'visible-stand-die'
    spec, geometry = full_stand_spec(destination/'input')
    result = export.export_object(spec, destination/'output', native=True)
    assert result['native']['holds'] and result['readback']['native_illustrator_validated']
    assert_full_stand_die(result, geometry)
    census = result['native']['reopened_census']
    assert census['die_geometry']['holds']
    assert len(census['diePaths']) == result['readback']['die_geometry']['expected_paths']
    assert next(row for row in census['layers'] if row['name'] == 'DIE')['visible']
    (destination/'results.json').write_text(json.dumps({'result': result, 'geometry': geometry}, indent=2) + '\n')


@pytest.mark.parametrize('kind', ['bottle', 'cap', 'stand'])
def test_files_export_reopens_six_layers_live_granted_fonts_and_real_spot(tmp_path, kind):
    spec = object_spec(tmp_path / 'inputs', kind)
    original_plate = Path(spec['artwork'][0]['path']).read_bytes()
    result = export.export_object(spec, tmp_path / 'files', native=False)
    path = Path(result['ai'])
    assert path.read_bytes().startswith(b'%PDF-')
    assert Path(result['pdf']).read_bytes() == path.read_bytes()
    assert result['layers'] == ['GROUND', 'MOTIFS', 'RELIEF', 'FOIL', 'WORDS', 'DIE']   # the face in layers (2026-10-29)
    fresh = export.read_back_ai(path, result['type'], result['elements'])
    assert fresh['pdf_compatible_holds'] and all(fresh['checks'].values())
    assert fresh['size_mm'] == pytest.approx(spec['size_mm'], abs=.001)
    assert fresh['trim_box_mm'] == pytest.approx(spec['trim_box_mm'], abs=.001)
    assert fresh['spot_name'] == 'Gold_Foil' and fresh['spot_operator_count'] > 0
    assert all(item['components'] == 4 for item in fresh['raster_colour_spaces'])
    assert all('CMYK' in item['colour_space'] for item in fresh['live_type_colour_spaces'])
    assert all(row['present'] for row in fresh['copies']) and fresh['live_glyphs'] > 0
    assert all(font['embedded_bytes'] > 10000 for font in fresh['fonts'])
    assert all(row['pool'] == 'GRANTED' for row in result['fonts'].values())
    assert all(row['locked'] and not row['printable'] for row in fresh['layers'] if row['name'] in ('DIE', 'GUIDES'))
    assert fresh['native_illustrator_validated'] is False and result['native']['holds'] is False
    assert Path(spec['artwork'][0]['path']).read_bytes() == original_plate
    assert all(row['sha256'] == export.LOGO_SHA256 for row in result['elements'] if row.get('approved_master'))
    with Image.open(result['png']) as image:
        assert image.size == (round(spec['size_mm'][0] * 300 / 25.4 + .499), round(spec['size_mm'][1] * 300 / 25.4 + .499))
        assert image.info['dpi'] == pytest.approx((300, 300), abs=.01)
        assert image.mode == 'RGBA'
        if kind != 'stand':
            assert image.getextrema()[3][0] == 0  # Substrate and liquid are not flattened to white.


def test_files_export_foil_evenodd_hole_and_rotated_live_type_survive(tmp_path):
    spec = object_spec(tmp_path / 'inputs', 'cap')
    spec['type_runs'][0]['box_mm'] = [11, 2, 14, 27]
    spec['logos'] = []
    result = export.export_object(spec, tmp_path / 'files', native=False)
    with Image.open(result['png']) as image:
        pixels = image.convert('RGBA')
        at = lambda x, y: pixels.getpixel((round(x * 300 / 25.4), round(y * 300 / 25.4)))
        assert min(at(2, 9)[:3]) < 240 and at(2, 9)[3] == 255  # Actual foil ink.
        assert at(6, 13)[3] == 0  # The original evenodd knockout stays open.
    with fitz.open(result['ai']) as doc:
        trace = doc[0].get_texttrace()
        assert any(span['dir'] == pytest.approx((0, -1)) for span in trace)
        assert all('Almarai' not in span['font'] for span in trace)
    assert result['type'][0]['copy'] == 'GLASS' and result['type'][0]['rotation'] == 90
    assert result['type'][0]['foil'] is True


@pytest.mark.parametrize('copy,face', [('Latin words', 'arabic'), ('ملمع شفاه', 'latin')])
def test_files_export_refuses_script_font_mismatch(tmp_path, copy, face):
    spec = object_spec(tmp_path / 'inputs')
    spec['type_runs'] = [{'copy': copy, 'face': face, 'box_mm': [1, 20, 14, 30], 'size_pt': 6}]
    with pytest.raises(ValueError, match='face|engine'):
        export.export_object(spec, tmp_path / 'files', native=False)


@pytest.mark.parametrize('content', [
    '<text x="0" y="5">Hidden instruction</text>',
    '<image width="10" height="10" href="https://fixture.invalid/raster.png"/>',
])
def test_files_export_foil_svg_cannot_smuggle_text_or_raster(tmp_path, content):
    spec = object_spec(tmp_path / 'inputs')
    Path(spec['foil_svg'][0]['path']).write_text('<svg xmlns="http://www.w3.org/2000/svg">' + content + '</svg>')
    with pytest.raises(ValueError, match='vector geometry only'):
        export.export_object(spec, tmp_path / 'files', native=False)


def test_files_export_refuses_unapproved_logo_and_changed_granted_font(tmp_path, monkeypatch):
    spec = object_spec(tmp_path / 'inputs')
    spec['logos'][0]['path'] = spec['foil_svg'][0]['path']
    with pytest.raises(ValueError, match='approved vector logo'):
        export.export_object(spec, tmp_path / 'files', native=False)
    del spec['logos'][0]['path']
    wrong = tmp_path / 'changed.ttf'
    wrong.write_bytes(export.FONT_PATHS['latin'].read_bytes() + b'changed')
    monkeypatch.setattr(export, 'FONT_PATHS', dict(export.FONT_PATHS, latin=wrong))
    with pytest.raises(ValueError, match='pinned GRANTED'):
        export.export_object(spec, tmp_path / 'files', native=False)


@pytest.mark.parametrize('damage', ['unlocked', 'removed_live_text', 'metadata_only_copy', 'unused_spot', 'rgb_type'])
def test_files_export_actual_readback_detects_broken_layers_type_and_foil(tmp_path, damage):
    result = export.export_object(object_spec(tmp_path / 'inputs'), tmp_path / 'files', native=False)
    with fitz.open(result['ai']) as doc:
        if damage == 'unlocked':
            doc.xref_set_key(doc.pdf_catalog(), 'OCProperties/D/Locked', '[]')
        elif damage == 'removed_live_text':
            for xref in doc[0].get_contents():
                if b'/ActualText' in doc.xref_stream(xref):
                    doc.update_stream(xref, b'')
        elif damage == 'metadata_only_copy':
            import re
            for xref in doc[0].get_contents():
                content = doc.xref_stream(xref)
                if b'/ActualText' in content:
                    doc.update_stream(xref, re.sub(rb'BT\b.*?\bET', b'', content, flags=re.S))
                    break
        elif damage == 'rgb_type':
            import re
            for xref in doc[0].get_contents():
                content = doc.xref_stream(xref)
                if b'/ActualText' in content:
                    doc.update_stream(xref, re.sub(rb'(?:[.\d]+\s+){4}k', b'1 0 0 rg', content))
                    break
        else:
            for xref in range(1, doc.xref_length()):
                if doc.xref_is_stream(xref):
                    content = doc.xref_stream(xref)
                    if b'/Gold_Foil' in content:
                        doc.update_stream(xref, content.replace(b'/Gold_Foil cs 1 scn', b'0 0 0 rg').replace(b'/Gold_Foil CS 1 SCN', b'0 0 0 RG'))
        doc.saveIncr()
    fresh = export.read_back_ai(result['ai'], result['type'], result['elements'])
    assert fresh['pdf_compatible_holds'] is False
    key = {'unlocked': 'die_guides_locked_nonprinting', 'removed_live_text': 'live_text',
           'metadata_only_copy': 'all_expected_copy', 'unused_spot': 'gold_foil_spot',
           'rgb_type': 'live_type_colour_cmyk_or_spot'}[damage]
    assert fresh['checks'][key] is False


def test_files_export_default_requires_matching_native_final_bytes(tmp_path, monkeypatch):
    calls = []
    def fake_native(path, rows, elements, ops=None, size_mm=None):
        calls.append(str(path))
        return {'holds': True, 'final_sha256': 'not-the-file'}
    monkeypatch.setattr(export, 'native_roundtrip', fake_native)
    with pytest.raises(ValueError, match='native Illustrator'):
        export.export_object(object_spec(tmp_path / 'inputs'), tmp_path / 'files')
    assert len(calls) == 1


@pytest.mark.parametrize('components,expected', [(4, 'spot-CMYK'), (3, 'spot-non-CMYK')])
def test_files_export_reads_indirect_native_spot_alternate_without_accepting_rgb(tmp_path, components, expected):
    path = tmp_path / 'indirect-spot.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((30, 30), 'Fixture')
        profile, alternate, spot = [doc.get_new_xref() for _ in range(3)]
        doc.update_object(profile, f'<</N {components}>>')
        doc.update_object(alternate, f'[/ICCBased {profile} 0 R]')
        doc.update_object(spot, f'[/Separation /Gold_Foil {alternate} 0 R <</FunctionType 2>>]')
        resource = int(doc.xref_get_key(page.xref, 'Resources')[1].split()[0])
        doc.xref_set_key(resource, 'ColorSpace/CS0', f'{spot} 0 R')
        for xref in page.get_contents():
            doc.update_stream(xref, doc.xref_stream(xref).replace(b'BT', b'BT /CS0 cs 1 scn'))
        doc.save(path)
    assert export._text_colour_spaces(path) == [{'operator': 'TJ', 'colour_space': expected}]
    assert export.read_back_ai(path)['checks']['live_type_colour_cmyk_or_spot'] is (components == 4)


def native_text_frame(text='Fixture', size=13.0893507003784, font='DMSans-Regular', layer='type'):
    return {'text': text, 'layer': layer, 'kind': 'TextType.POINTTEXT',
            'characters': [{'text': char, 'font': None if char.isspace() else font,
                            'size': None if char.isspace() else size} for char in text]}


def test_files_export_native_size_comparison_handles_rounding_boundary_without_changing_identity():
    saved = {'frames': [native_text_frame('Fraction A')]}
    reopened = {'frames': [native_text_frame('Fraction A', size=13.0893497467041)]}
    assert round(saved['frames'][0]['characters'][0]['size'], 4) != round(reopened['frames'][0]['characters'][0]['size'], 4)
    result = export._compare_native_frames(saved, reopened)
    assert result['matches']
    assert result['size_tolerance_pt'] == .0001
    assert result['max_size_delta_pt'] == pytest.approx(.0000009536743)
    assert result['matched_frames'] == [{'saved_frame_index': 0, 'reopened_frame_index': 0,
                                        'max_size_delta_pt': result['max_size_delta_pt']}]


def test_files_export_native_frame_matching_is_order_independent_one_to_one_with_duplicates():
    saved = {'frames': [native_text_frame(size=10), native_text_frame(size=10.00015),
                        native_text_frame('Other', size=6)]}
    # A greedy matcher would consume target 0 for saved frame 0 and then fail.
    reopened = {'frames': [native_text_frame(size=10.000075), native_text_frame('Other', size=6),
                           native_text_frame(size=9.999925)]}
    result = export._compare_native_frames(saved, reopened)
    assert result['matches'] and len(result['matched_frames']) == 3
    assert len({row['saved_frame_index'] for row in result['matched_frames']}) == 3
    assert len({row['reopened_frame_index'] for row in result['matched_frames']}) == 3
    assert {row['saved_frame_index']: row['reopened_frame_index'] for row in result['matched_frames']} == {0: 2, 1: 0, 2: 1}
    reopened['frames'][2] = native_text_frame('Other', size=6)
    assert export._compare_native_frames(saved, reopened)['matches'] is False


@pytest.mark.parametrize('damage', ['size', 'font', 'copy', 'character', 'layer', 'missing_frame',
                                     'missing_character', 'missing_size', 'nan', 'infinity', 'boolean'])
def test_files_export_native_frame_match_refuses_real_or_invalid_changes(damage):
    saved = {'frames': [native_text_frame('Stable words')]}
    reopened = deepcopy(saved)
    frame = reopened['frames'][0]
    if damage == 'size':
        frame['characters'][0]['size'] += .001
    elif damage == 'font':
        frame['characters'][0]['font'] = 'Almarai-Regular'
    elif damage == 'copy':
        frame['text'] = 'Different words'
    elif damage == 'character':
        frame['characters'][0]['text'] = 'X'
    elif damage == 'layer':
        frame['layer'] = 'artwork'
    elif damage == 'missing_frame':
        reopened['frames'].clear()
    elif damage == 'missing_character':
        frame['characters'].pop()
    else:
        frame['characters'][0]['size'] = {'missing_size': None, 'nan': float('nan'),
                                         'infinity': float('inf'), 'boolean': True}[damage]
    result = export._compare_native_frames(saved, reopened)
    assert result['matches'] is False and result['max_size_delta_pt'] is None


@pytest.mark.parametrize('copy,face', [('Sample Word', 'latin'), ('ملمع شفاه', 'arabic')])
@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_files_export_minimum_type_envelope_preserves_actual_ink_and_origin(tmp_path, copy, face, rotation):
    original = {'copy': copy, 'face': face, 'size_pt': 5, 'align': 'center',
                'rotation': rotation, 'box_mm': [13, 20, 20, 23]}
    untouched = deepcopy(original)
    before = export.measure_type(original)
    assert before['overflow']
    repaired = export.fit_type_envelope(original, safe_box_mm=[.5, .5, 39.5, 49.5], occupied_boxes_mm=[])
    after = export.measure_type(repaired)
    assert original == untouched and repaired['source_box_mm'] == original['box_mm']
    assert repaired['size_pt'] == 5 and after['overflow'] is False
    assert after['position_pt'] == pytest.approx(before['position_pt'], abs=1e-9)
    assert after['ink_box_mm'] == pytest.approx(before['ink_box_mm'], abs=1e-9)
    assert repaired['type_fit']['source_position_preserved']
    for run, name in ((original, 'original'), (repaired, 'repaired')):
        result = export.export_object({'id': name, 'size_mm': [40, 50], 'type_runs': [run]}, tmp_path, native=False)
        if name == 'repaired':
            assert result['type'][0]['type_fit'] == repaired['type_fit']
            assert result['type'][0]['overflow'] is False
            assert result['readback']['copies'][0]['present']
    # Compare the actual emitted pixels, not only the shared layout calculation.
    with Image.open(tmp_path / 'original.png') as a, Image.open(tmp_path / 'repaired.png') as b:
        assert a.tobytes() == b.tobytes()
    with fitz.open(tmp_path / 'repaired.ai') as doc:
        pix = doc[0].get_pixmap(dpi=1200, alpha=True)
        bounds = Image.frombytes('RGBA', (pix.width, pix.height), pix.samples).getchannel('A').getbbox()
    assert bounds is not None
    actual_mm = [value * 25.4 / 1200 for value in bounds]
    assert actual_mm == pytest.approx(after['ink_box_mm'], abs=.045)


@pytest.mark.parametrize('problem', ['safe_area', 'other_copy', 'under_5pt', 'not_centered'])
def test_files_export_type_envelope_refuses_moving_shrinking_or_colliding(problem):
    run = {'copy': 'Sample Word', 'face': 'latin', 'size_pt': 5, 'align': 'center', 'box_mm': [13, 20, 20, 23]}
    safe, occupied = [.5, .5, 39.5, 49.5], []
    if problem == 'safe_area':
        safe = [13, .5, 20, 49.5]
    elif problem == 'other_copy':
        occupied = [[20.01, 20, 22, 23]]
    elif problem == 'under_5pt':
        run['size_pt'] = 4.9
    else:
        run['align'] = 'left'
    original = deepcopy(run)
    with pytest.raises(ValueError, match='safe area|overlaps|under 5|centered'):
        export.fit_type_envelope(run, safe_box_mm=safe, occupied_boxes_mm=occupied)
    assert run == original


def test_files_export_repeated_envelope_fit_keeps_original_source_box():
    run = {'copy': 'Sample Word', 'face': 'latin', 'size_pt': 5, 'box_mm': [13, 20, 20, 23]}
    first = export.fit_type_envelope(run, safe_box_mm=[.5, .5, 39.5, 49.5], occupied_boxes_mm=[])
    second = export.fit_type_envelope(first, safe_box_mm=[.5, .5, 39.5, 49.5], occupied_boxes_mm=[])
    assert second['source_box_mm'] == second['type_fit']['source_box_mm'] == run['box_mm']
    assert second['type_fit']['input_layout_box_mm'] == first['box_mm']
    assert second['box_mm'] == pytest.approx(first['box_mm'], abs=1e-9)
    assert export.measure_type(second)['position_pt'] == pytest.approx(export.measure_type(run)['position_pt'], abs=1e-9)


@pytest.mark.parametrize('origin', [(0, 0), (10, 20)])
def test_files_export_svg_canvas_keeps_empty_margins_instead_of_fitting_ink_bounds(tmp_path, origin):
    x, y = origin
    path = tmp_path / 'offset.svg'
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="134" height="500" viewBox="{x} {y} 134 500">'
                    f'<path fill="#D5AF59" d="M{x+28} {y+20} H{x+118} V{y+70} H{x+28} Z"/></svg>')
    original = path.read_bytes()
    result = export.export_object({'id': 'offset', 'size_mm': [15, 70],
        'foil_svg': [{'path': str(path), 'box_mm': [0, 0, 15, 70]}]}, tmp_path / 'files', native=False)
    with fitz.open(result['ai']) as doc:
        drawings = doc[0].get_drawings()
    assert len(drawings) == 1
    bounds_mm = [value / export.PT for value in drawings[0]['rect']]
    expected = [28/134*15, 20/500*70, 118/134*15, 70/500*70]
    assert bounds_mm == pytest.approx(expected, abs=.001)
    assert bounds_mm[0] > 3 and bounds_mm[3] < 10  # A content-bounds fit would fail this control.
    assert path.read_bytes() == original


@pytest.mark.parametrize('origin', [(0, 0), (214, 388)])
@pytest.mark.parametrize('canvas,physical', [((100, 200), (20, 40)), ((134, 500), (15, 70))])
def test_files_export_stroked_svg_keeps_source_canvas_round_ends_and_measured_width(tmp_path, origin, canvas, physical):
    """An inset foil line stays inset; round joins must not become filled wedges."""
    import numpy as np
    x, y = origin
    width, height = canvas
    sx, sy = physical[0]/width, physical[1]/height
    source = tmp_path / 'stroke.svg'
    source.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                      f'viewBox="{x} {y} {width} {height}"><path fill="none" stroke="#D5AF59" '
                      f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round" '
                      f'd="M{x+20} {y+30} H{x+60} V{y+80}"/></svg>')
    original = source.read_bytes()
    result = export.export_object({'id': 'stroke', 'size_mm': list(physical),
        'foil_svg': [{'path': str(source), 'box_mm': [0, 0, *physical]}]}, tmp_path / 'files', native=False)
    with fitz.open(result['ai']) as doc:
        drawings = doc[0].get_drawings()
        assert len(drawings) == 1
        stroke = drawings[0]
        assert stroke['type'] == 's' and stroke['fill'] is None
        if sx == sy:
            assert stroke['width'] / export.PT == pytest.approx(4*sx, abs=.001)
        assert stroke['lineCap'] == (1, 1, 1) and stroke['lineJoin'] == 1
        assert [value / export.PT for value in stroke['rect']] == pytest.approx([20*sx, 30*sy, 60*sx, 80*sy], abs=.001)
        pixmap = doc[0].get_pixmap(matrix=fitz.Matrix(1016/72, 1016/72), alpha=True)
        alpha = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)[..., -1]
    # Independent capsule-union geometry includes caps and the outer round join.
    # Fitting to the ink bounds, clipping caps or closing the L into a triangle
    # changes this expected footprint even if the SVG's own raster matches it.
    yy, xx = np.mgrid[:alpha.shape[0], :alpha.shape[1]]
    px, py = (xx+.5)/(40*sx), (yy+.5)/(40*sy)
    horizontal = np.hypot(px-np.clip(px, 20, 60), py-30)
    vertical = np.hypot(px-60, py-np.clip(py, 30, 80))
    expected = np.minimum(horizontal, vertical) <= 2
    actual = alpha >= 128
    assert (actual & expected).sum() / (actual | expected).sum() > .985
    assert not actual[:, :int(18*sx*40)-2].any() and not actual[:int(28*sy*40)-2, :].any()
    assert result['readback']['checks']['gold_foil_spot']
    assert source.read_bytes() == original


@pytest.mark.parametrize('damage', ['width', 'position', 'missing', 'reuse', 'nan', 'curve', 'uneditable'])
def test_files_export_fitted_readback_rejects_changed_or_missing_live_strokes(tmp_path, damage):
    source = tmp_path/'varied.svg'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="15mm" height="70mm" viewBox="0 0 15 70">'+''.join(
        f'<path d="M 2,{y} L 13,{y}" fill="none" stroke="#D5AF59" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
        for y, width in [(10, .3), (25, .5), (40, .7)])+'</svg>')
    result = export.export_object({'id': 'varied', 'size_mm': [25, 80],
        'foil_svg': [{'path': str(source), 'box_mm': [5, 5, 20, 75], 'fitted_strokes': True}]},
        tmp_path/'output', native=False)
    assert result['readback']['fitted_strokes']['holds']
    assert result['readback']['fitted_strokes']['expected_strokes'] == 3
    actual = export._pdf_fitted_strokes(result['ai'])
    for row in actual:
        row.update(editable=True, typename='PathItem', left_mm=deepcopy(row['points_mm']), right_mm=deepcopy(row['points_mm']))
    assert export._fitted_stroke_check(result['elements'], actual, native=True)['holds']
    if damage == 'width':
        actual[0]['width_mm'] += .1
    elif damage == 'position':
        actual[0]['points_mm'][0][0] += .1
    elif damage == 'missing':
        actual.pop()
    elif damage == 'reuse':
        result['elements'][0]['fitted_strokes'].append(deepcopy(result['elements'][0]['fitted_strokes'][0]))
    elif damage == 'nan':
        actual[0]['width_mm'] = float('nan')
    elif damage == 'curve':
        actual[0]['left_mm'][0][0] += .1
    else:
        actual[0]['editable'] = False
    assert not export._fitted_stroke_check(result['elements'], actual, native=True)['holds']


@pytest.mark.parametrize('damage', ['placement_size', 'pixels', 'transform', 'nonfinite_width'])
def test_files_export_fitted_svg_refuses_nonphysical_or_changed_scale(tmp_path, damage):
    source = tmp_path/'physical.svg'
    text = '<svg xmlns="http://www.w3.org/2000/svg" width="15mm" height="70mm" viewBox="0 0 15 70"><path d="M 2,5 L 13,55" fill="none" stroke="#D5AF59" stroke-width=".5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    box = [0, 0, 15, 70]
    if damage == 'placement_size':
        box[2] = 16
    elif damage == 'pixels':
        text = text.replace('width="15mm"', 'width="15px"')
    elif damage == 'transform':
        text = text.replace('<path ', '<path transform="translate(1 0)" ')
    else:
        text = text.replace('stroke-width=".5"', 'stroke-width="nan"')
    source.write_text(text)
    with pytest.raises(ValueError, match='Fitted|fitted'):
        export.export_object({'id': 'invalid', 'size_mm': [20, 80],
            'foil_svg': [{'path': str(source), 'box_mm': box, 'fitted_strokes': True}]},
            tmp_path/'output', native=False)


@pytest.mark.skipif(os.environ.get('ROUND_FILES_NATIVE_FIXTURE') != '1', reason='Explicit local Illustrator fixture only')
def test_files_export_stroked_trace_survives_actual_native_reopen(tmp_path):
    import numpy as np
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    destination = Path(os.environ.get('ROUND_FILES_NATIVE_FIXTURE_DIR', str(tmp_path))) / 'stroked-trace'
    destination.mkdir(parents=True, exist_ok=True)
    source = destination / 'synthetic-trace.svg'
    # Illustrator normalizes nonuniformly transformed SVG strokes to one width.
    # Expand strokes in source coordinates first, as the traced-art producer does;
    # the resulting filled round caps/joins must still pass the analytic oracle.
    lines = [[(242, 408), (332, 518), (302, 548)], [(242, 518), (332, 408)]]
    ink = unary_union([LineString(line).buffer(2.25, cap_style=1, join_style=1) for line in lines])
    contours = [ink.exterior, *ink.interiors]
    outline = ' '.join('M'+' L'.join(f'{x:.8f} {y:.8f}' for x, y in ring.coords)+' Z' for ring in contours)
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="134" height="500" viewBox="214 388 134 500">'
                      f'<path fill="#D5AF59" fill-rule="evenodd" d="{outline}"/></svg>')
    original = source.read_bytes()
    spec = {'id': 'native-stroked-trace', 'size_mm': [15, 70],
        'foil_svg': [{'path': str(source), 'box_mm': [0, 0, 15, 70]}],
        'type_runs': [{'copy': 'Lip Gloss', 'face': 'latin', 'size_pt': 5, 'box_mm': [1, 50, 14, 54]},
                      {'copy': 'ملمع شفاه', 'face': 'arabic', 'size_pt': 5, 'box_mm': [1, 57, 14, 61]}]}
    (destination / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n')
    started = time.monotonic()
    result = export.export_object(spec, destination / 'files', native=True)
    assert result['native']['holds'] and result['readback']['native_illustrator_validated']
    assert all(result['native']['reopen_checks'].values()) and all(result['readback']['checks'].values())
    assert result['layers'] == ['GROUND', 'MOTIFS', 'RELIEF', 'FOIL', 'WORDS', 'DIE']   # the face in layers (2026-10-29)
    assert all(row['present'] for row in result['readback']['copies'])
    assert all(row['size_pt'] == 5 and not row['overflow'] for row in result['type'])
    with fitz.open(result['ai']) as doc:
        pixmap = doc[0].get_pixmap(matrix=fitz.Matrix(1016/72, 1016/72), alpha=True,
                                  clip=fitz.Rect(0, 0, 15*export.PT, 35*export.PT))
        alpha = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)[..., -1]
    yy, xx = np.mgrid[:alpha.shape[0], :alpha.shape[1]]
    px, py = (xx+.5)/(40*15/134), (yy+.5)/(40*70/500)
    distance = np.full(alpha.shape, np.inf)
    for a, b in [((28, 20), (118, 130)), ((118, 130), (88, 160)), ((28, 130), (118, 20))]:
        dx, dy = b[0]-a[0], b[1]-a[1]
        along = np.clip(((px-a[0])*dx+(py-a[1])*dy)/(dx*dx+dy*dy), 0, 1)
        distance = np.minimum(distance, np.hypot(px-a[0]-along*dx, py-a[1]-along*dy))
    expected, actual = distance <= 2.25, alpha >= 128
    overlap = float((actual & expected).sum()/(actual | expected).sum())
    assert overlap > .985
    assert source.read_bytes() == original
    (destination / 'results.json').write_text(json.dumps({'seconds': time.monotonic()-started,
        'synthetic_source_sha256': export.sha(source), 'independent_analytic_footprint_iou': overlap,
        'source_canvas_px': [134, 500], 'source_viewbox_origin': [214, 388], 'target_mm': [15, 70],
        'stroke_width_source_px': 4.5, 'stroke_expansion': 'Closed filled contours in source coordinates; round caps/joins before nonuniform placement',
        'result': result}, ensure_ascii=False, indent=2) + '\n')


@pytest.mark.skipif(os.environ.get('ROUND_FILES_NATIVE_FIXTURE') != '1', reason='Explicit local Illustrator fixture only')
def test_files_export_type_envelope_and_svg_canvas_survive_actual_native_reopen(tmp_path):
    destination = Path(os.environ.get('ROUND_FILES_NATIVE_FIXTURE_DIR', str(tmp_path))) / 'placement'
    destination.mkdir(parents=True, exist_ok=True)
    svg = destination / 'offset.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="134" height="500" viewBox="0 0 134 500">'
                   '<path fill="#D5AF59" d="M28 20 H118 V70 H28 Z"/></svg>')
    runs = [{'copy': 'Sample Word', 'face': 'latin', 'size_pt': 5, 'box_mm': [13, 43, 20, 46]},
            {'copy': 'ملمع شفاه', 'face': 'arabic', 'size_pt': 5, 'box_mm': [13, 50, 20, 53]}]
    fitted = [export.fit_type_envelope(run, safe_box_mm=[.5, .5, 39.5, 69.5],
               occupied_boxes_mm=[other['box_mm'] for other in runs if other is not run]) for run in runs]
    result = export.export_object({'id': 'fixed-source-type', 'size_mm': [40, 70], 'type_runs': fitted,
        'foil_svg': [{'path': str(svg), 'box_mm': [0, 0, 40, 70]}]}, destination / 'files', native=True)
    assert result['native']['holds'] and result['readback']['native_illustrator_validated']
    assert all(row['size_pt'] == 5 and not row['overflow'] for row in result['type'])
    assert all(row['present'] for row in result['readback']['copies'])
    with fitz.open(result['ai']) as doc:
        rect = doc[0].get_drawings()[0]['rect']
    assert [value / export.PT for value in rect] == pytest.approx([28/134*40, 2.8, 118/134*40, 9.8], abs=.005)
    (destination / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')


@pytest.mark.skipif(os.environ.get('ROUND_FILES_NATIVE_FIXTURE') != '1', reason='Explicit local Illustrator fixture only')
def test_files_export_fractional_type_survives_actual_native_reopen(tmp_path):
    destination = Path(os.environ.get('ROUND_FILES_NATIVE_FIXTURE_DIR', str(tmp_path))) / 'fractional-type'
    spec = object_spec(destination / 'inputs', 'stand')
    spec['id'] = 'fractional-type'
    samples = [('Fraction A', 13.0893507003784, 'latin'), ('Fraction B', 13.0806112289429, 'latin'),
               ('Fraction C', 13.3352422714233, 'latin'), ('ملمع شفاه', 14.5980625152588, 'arabic'),
               ('Fraction D', 18.3326950073242, 'latin')]
    spec['type_runs'] = [{'copy': copy, 'face': face, 'size_pt': size,
                         'box_mm': [5, 35 + index * 20, 105, 45 + index * 20]}
                        for index, (copy, size, face) in enumerate(samples)]
    started = time.monotonic()
    result = export.export_object(spec, destination / 'files', native=True)
    comparison = result['native']['text_comparison']
    assert result['native']['holds'] and result['readback']['native_illustrator_validated']
    assert comparison['matches'] and comparison['saved_frame_count'] == comparison['reopened_frame_count'] == 5
    assert comparison['max_size_delta_pt'] <= comparison['size_tolerance_pt'] == .0001
    assert all(row['present'] for row in result['readback']['copies'])
    (destination / 'results.json').write_text(json.dumps({'seconds': time.monotonic() - started,
        'ai': result['ai'], 'sha256': result['sha256'], 'native': result['native'],
        'readback': result['readback']}, ensure_ascii=False, indent=2) + '\n')


@pytest.mark.skipif(os.environ.get('ROUND_FILES_NATIVE_FIXTURE') != '1', reason='Explicit local Illustrator fixture only')
def test_files_export_three_actual_illustrator_save_and_reopens_within_ten_minutes(tmp_path):
    destination = Path(os.environ.get('ROUND_FILES_NATIVE_FIXTURE_DIR', str(tmp_path)))
    started = time.monotonic()
    records = []
    for kind in ('bottle', 'cap', 'stand'):
        result = export.export_object(object_spec(destination / 'inputs', kind), destination / 'native-files', native=True)
        assert result['native']['holds'] and result['readback']['native_illustrator_validated']
        assert result['native']['reopen_checks']['same_live_text_and_fonts']
        records.append({'id': kind, 'ai': result['ai'], 'sha256': result['sha256'], 'readback': result['readback']})
    elapsed = time.monotonic() - started
    (destination / 'native-fixture-results.json').write_text(json.dumps({'seconds': elapsed, 'objects': records}, ensure_ascii=False, indent=2))
    assert elapsed < 600


@pytest.mark.skipif(os.environ.get('ROUND_FILES_NATIVE_FIXTURE') != '1', reason='Explicit local Illustrator fixture only')
def test_files_export_ornament_words_along_an_arc_survive_actual_native_reopen(tmp_path):
    from apps.pipeline.services.round_files_faces import layout_runs
    destination = Path(os.environ.get('ROUND_FILES_NATIVE_FIXTURE_DIR', str(tmp_path))) / 'ornament-arc'
    spec = object_spec(destination / 'inputs', 'stand')
    spec['id'] = 'ornament-arc'
    zone = {'path_norm': [[.05, .45], [.3, .2], [.6, .12], [.95, .3]], 'height_norm': .05, 'color': '#D5AF59',
            'copy': [{'field': 'brand', 'copy': 'BBROSE', 'face': 'latin'},
                     {'field': 'product_arabic', 'copy': 'ملمع شفاه', 'face': 'arabic'},
                     {'field': 'arabic_shade_2', 'copy': 'إمبر جلو', 'face': 'arabic'}]}
    runs, record = layout_runs('stand_header', 0, zone, [0, 0, 110, 160])
    spec['type_runs'] = runs
    result = export.export_object(spec, destination / 'files', native=True)
    comparison = result['native']['text_comparison']
    assert result['native']['holds'] and result['readback']['native_illustrator_validated']
    assert comparison['matches'] and comparison['saved_frame_count'] == comparison['reopened_frame_count'] == len(runs)
    assert all(row['present'] for row in result['readback']['copies'])
    (destination / 'results.json').write_text(json.dumps({'layout': record, 'ai': result['ai'], 'sha256': result['sha256'],
        'native': result['native'], 'readback': result['readback']}, ensure_ascii=False, indent=2) + '\n')


def test_illustrator_is_given_time_by_the_file_s_size(tmp_path):
    """Round 4 (2026-10-30): Make my files stopped when the 24.7 MB stand took 317 s to save in Illustrator, past a fixed
    180 s. The time is the file's size at 30 s a megabyte, never under 180 s nor over 1,200 s (the worker's task
    limit is 1,800 s)."""
    from apps.pipeline.services import round_files_export as ex
    for size, seconds in ((2_740_058, 180), (24_661_211, 740), (90_000_000, 1200)):
        path = tmp_path / ('%d.ai' % size)
        with open(path, 'wb') as handle:
            handle.truncate(size)
        assert ex.native_timeout(path) == seconds, size
    assert ex.native_timeout(tmp_path / '24661211.ai') > 317                  # the stand's measured save
