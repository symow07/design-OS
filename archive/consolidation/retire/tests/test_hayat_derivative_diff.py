"""The derivative proof must detect actual file changes, including hidden dies."""
import json
import hashlib

import fitz
import pytest

from apps.pipeline.services import round_balm_finish as finish


def test_final_positive_proof_binds_all_fifteen_current_native_ai_files():
    report = json.loads((finish.OUT / 'derivatives.json').read_text())
    assert report['schema'] == 'hayat_tints/3'
    assert report['negative_controls']['holds'] is True
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['negative_controls']['master_sha256'] == sha(finish.OUT / 'body-wrap.ai')
    files = set()
    assert len(report['derivatives']) == 2
    for row in report['derivatives']:
        folder = finish.m.REPO / row['path']
        assert row['same_master_holds'] is True
        assert row['area_frames']['carton']['exact_same_named_frames'] is True
        assert row['area_frames']['carton']['expected_count'] == 3
        assert row['area_frames']['leaflet']['exact_same_named_frames'] is True
        assert row['area_frames']['leaflet']['expected_count'] == 6
        assert len(row['surfaces']) == 5
        assert json.loads((folder / 'diff.json').read_text()) == row
        for surface in row['surfaces']:
            master, derivative = finish.OUT / surface['file'], folder / surface['file']
            files.update((master, derivative))
            assert surface['master_sha256'] == sha(master)
            assert surface['derivative_sha256'] == sha(derivative)
            assert surface['holds'] is True
            assert all(surface['checks'].values())
            assert surface['native_master']['holds'] and surface['native_derivative']['holds']
    assert len(files) == 15


@pytest.mark.parametrize('layer', ['die', 'mark'])
def test_saved_file_diff_rejects_changed_hidden_die_or_visible_mark(tmp_path, layer):
    original = finish.OUT / 'body-wrap.ai'
    control = finish.compare_saved_surfaces(original, original)
    assert control['holds'] is True
    changed = tmp_path / 'mutated.ai'
    with fitz.open(original) as doc:
        ocg = next(x for x, row in doc.get_ocgs().items() if row['name'] == layer)
        # A production path inserted on the actual target layer, including the
        # hidden die, must be caught without depending on metadata or preview.
        doc[0].draw_line(fitz.Point(2, 2), fitz.Point(11, 9), color=(1, 0, 0), width=.37, oc=ocg)
        doc.save(changed)
    result = finish.compare_saved_surfaces(original, changed)
    assert result['holds'] is False
    assert result['checks']['all_vector_paths_strokes_clips_identical'] is False
    assert result['vector_layer_checks'][layer] is False
    assert result['checks']['decoded_painting_pixels_and_placement_identical'] is True
    assert result['checks']['fixed_live_glyphs_font_colour_size_position_identical'] is True


def test_type_spec_rejects_font_size_or_colour_changes_even_in_tint():
    original = {'name': 'cap tint', 'copy': 'ROSEWATER', 'face': 'latin', 'font_path': 'font.ttf',
                'size_pt': 8, 'requested_size_pt': 8, 'color': '#f4e9e5', 'zone_mm': [2, 2, 18, 6]}
    changed = dict(original, copy='FIG MILK')
    assert finish._type_specs([original], [changed], 'FIG MILK')[0]['holds'] is True
    # A different pre-fit request is harmless only if the actual final size
    # remains identical; actual saved glyph styles are checked independently.
    assert finish._type_specs([original], [dict(changed, requested_size_pt=9)], 'FIG MILK')[0]['holds'] is True
    for field, value in [('size_pt', 8.1), ('color', '#ff0000'), ('face', 'arabic'), ('zone_mm', [3, 2, 18, 6])]:
        altered = dict(changed, **{field: value})
        assert finish._type_specs([original], [altered], 'FIG MILK')[0]['holds'] is False
    assert finish._type_specs([original], [], 'FIG MILK')[0]['holds'] is False


@pytest.mark.parametrize('surface,count', [('carton', 3), ('leaflet', 6)])
def test_missing_native_copy_frame_cannot_pass_zip_comparison(tmp_path, monkeypatch, surface, count):
    base = tmp_path / 'master'; other = tmp_path / 'variant'; base.mkdir(); other.mkdir()
    frames = [{'name': surface + str(i), 'copy': 'Rosewater', 'face': 'latin',
               'size_pt': 6, 'leading_pt': 7, 'box_mm': [1, i * 12, 19, i * 12 + 10], 'language': ('en', 'es', 'ar')[i % 3]}
              for i in range(count)]
    (base / f'{surface}-native-frames.json').write_text(json.dumps({'frames': frames}))
    (other / f'{surface}-native-frames.json').write_text(json.dumps({'frames': [dict(f, copy='Ember') for f in frames[:-1]]}))
    monkeypatch.setattr(finish, 'OUT', base)
    proof, _, _ = finish._area_specs(other, 'EMBER', surface)
    assert proof['exact_same_named_frames'] is False
    assert proof['holds'] is False


def test_mixed_area_font_change_is_detected_even_when_both_style_names_remain_present():
    def region(text):
        return {'glyph_styles': [{'character': ord(char), 'font': 'Almarai-Regular' if char in 'اﺍ' else 'DMSans-Regular',
                                  'size': 6, 'color': [0, 0, 0], 'layer': 'type'} for char in text]}
    source = 'A ا B Rosewater'
    master = finish._fixed_area_styles(region(source), source)
    derivative = region('B ﺍ A Fig Milk')  # Contextual form and reflow order may change.
    assert finish._fixed_area_styles(derivative, source, 'FIG MILK') == master
    before_styles = {row['font'] for row in derivative['glyph_styles']}
    next(row for row in derivative['glyph_styles'] if row['character'] == ord('B'))['font'] = 'Almarai-Regular'
    assert {row['font'] for row in derivative['glyph_styles']} == before_styles
    assert finish._fixed_area_styles(derivative, source, 'FIG MILK')['sha256'] != master['sha256']


def test_consolidating_leaflet_checks_preserves_original_allowed_difference_bytes(tmp_path, monkeypatch):
    result = {'ai_check': {'holds': True}, 'contrast': [], 'type': []}
    (tmp_path / 'surface-builds.json').write_text(json.dumps({'body': result, 'cap': result, 'label': result}))
    for name in ('carton', 'leaflet'):
        (tmp_path / (name + '.json')).write_text(json.dumps({'files': result}))
    historical = b'{ "allowed": ["Original spacing remains exact"] }\n'
    path = tmp_path / 'allowed-differences.json'
    path.write_bytes(historical)
    monkeypatch.setattr(finish, 'OUT', tmp_path)
    combined = finish.consolidate()
    assert set(combined) == {'body', 'cap', 'label', 'carton', 'leaflet'}
    assert path.read_bytes() == historical
    assert 'leaflet' in json.loads((tmp_path / 'ai-check.json').read_text())


@pytest.mark.parametrize('origin_x,left,right,inside', ((9.9,9.9,10.5,True), (-.5,-.5,0,True), (-.6,-.6,-.1,False)))
def test_area_trailing_space_uses_origin_or_touching_edge_without_exempting_visible_glyphs(origin_x,left,right,inside):
    pt = finish.m.PT
    class Page:
        def get_texttrace(self):
            return [{'font': 'ABCDEF+DMSans-Regular', 'size': 5, 'color': (1, 1, 1), 'opacity': 1,
                     'type': 0, 'dir': (1, 0), 'wmode': 0, 'layer': 'type',
                     'chars': [(32, 1, (origin_x * pt, 5 * pt), (left * pt, 3 * pt, right * pt, 5 * pt)),
                               (65, 2, (origin_x * pt, 5 * pt), (left * pt, 3 * pt, right * pt, 5 * pt))]}]
    result = finish._text_evidence([Page()], [{'name': 'native', 'kind': 'area-reflow', 'box_mm': [0, 0, 10, 10]}])
    assert result['allowed_regions']['native']['text'] == (' ' if inside else '')
    assert sorted(row['character'] for row in result['fixed_glyphs']) == ([65] if inside else [32, 65])
    assert result['fixed_glyphs'][0]['font'] == 'DMSans-Regular'
