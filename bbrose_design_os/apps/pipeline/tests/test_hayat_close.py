"""Round1C evidence is checked against actual saved glyphs and immutable art."""
import hashlib
import importlib.util
import json
from pathlib import Path

import fitz
import pytest

REPO = Path(__file__).resolve().parents[4]
EVIDENCE = REPO / 'docs/rounds/r1-balm/master/evidence/close'
SPEC = importlib.util.spec_from_file_location('hayat_close_independent', EVIDENCE / 'verify_close.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def test_entry_measurement_keeps_the_part_b_findings_and_twelve_ai_baseline():
    snapshot = json.loads((EVIDENCE / 'entry-snapshot.json').read_text())
    objects = json.loads((EVIDENCE / 'entry-ai-objects.json').read_text())
    before = json.loads((EVIDENCE / 'entry-printed-lines.json').read_text())
    assert len(objects['files']) == 12
    for path, row in objects['files'].items():
        assert row['sha256'] == snapshot['files'][path]['sha256']
    assert len(before['lines']) == 27
    assert before['unsafe_count'] == 17
    assert len(before['script_font_errors']) == 31


def test_art_fragments_readings_and_nine_unchanged_ai_surfaces_stay_exact():
    result = audit.preservation_check()
    assert result['protected_file_count'] == 210
    assert result['changed_protected_files'] == []
    assert result['holds'] is True
    assert len(result['cartons']) == 3
    assert all(all(row['checks'].values()) for row in result['cartons'])


@pytest.mark.parametrize('variant', audit.VARIANTS)
@pytest.mark.parametrize('kind', ('carton', 'leaflet'))
def test_actual_final_printed_lines_copy_fonts_and_creases(variant, kind):
    result = audit.measure_surface(audit.MASTER / variant, kind)
    assert result['holds'], {key: val for key, val in result['checks'].items() if not val}
    assert result['unsafe_printed_line_count'] == 0
    assert result['hidden_characters'] == 0
    assert result['independent_hidden_nonspace_characters'] == 0
    assert result['crossed_line_count'] == 0
    assert result['script_font_errors'] == []
    if kind == 'leaflet':
        assert result['minimum_actual_type_pt'] >= 6 - .0001
        assert len(result['native_area_frames']) == 6


def test_final_independent_report_binds_all_fifteen_actual_ai_files():
    report = json.loads((EVIDENCE / 'final-verification.json').read_text())
    assert report['holds'] is True
    assert report['ai_file_count'] == len(report['ai_files']) == 15
    assert len(report['surfaces']) == 6
    for path, expected in report['ai_files'].items():
        assert hashlib.sha256((REPO / path).read_bytes()).hexdigest() == expected
    for key in ('native_hidden_characters', 'independent_hidden_nonspace_characters',
                'independent_extra_nonspace_characters', 'unsafe_printed_lines', 'crease_crossings', 'wrong_script_font_glyphs'):
        assert report[key] == 0
    assert report['listed_body_printed_alif_mm'] == 2.4157


def _temporary_printed_line(path, family='DMSans-Regular', x_mm=4, crease=False, text='HAYAT'):
    faces = json.loads((audit.MASTER / 'type.json').read_text())['faces']
    chosen = faces['latin' if family == 'DMSans-Regular' else 'arabic']
    program = (REPO / chosen['path']).read_bytes()
    assert hashlib.sha256(program).hexdigest() == chosen['sha256']
    with fitz.open() as doc:
        page = doc.new_page(width=72, height=72)
        type_layer = doc.add_ocg('type')
        page.insert_font(fontname='auditfont', fontbuffer=program)
        page.insert_text((x_mm * audit.PT_PER_MM, 7 * audit.PT_PER_MM), text,
                         fontname='auditfont', fontsize=6, color=(0, 0, 0), oc=type_layer)
        if crease:
            die = doc.add_ocg('die', on=False)
            page.draw_line((9 * audit.PT_PER_MM, 0), (9 * audit.PT_PER_MM, 72),
                           color=(0, .6, .9), dashes='[3 1.6] 0', oc=die)
        doc.save(path)


def test_wrong_latin_font_in_actual_saved_glyphs_is_detected(tmp_path):
    correct, wrong = tmp_path / 'correct.ai', tmp_path / 'wrong.ai'
    _temporary_printed_line(correct)
    _temporary_printed_line(wrong, family='Almarai-Regular')
    assert all(g['script_font_correct'] for g in audit.printed_glyphs(correct)[0])
    bad = audit.printed_glyphs(wrong)[0]
    assert len([g for g in bad if not g['script_font_correct']]) == 5


def test_spatial_parenthesis_observation_detects_reordering_with_identical_copy_inventory(tmp_path):
    correct, wrong = tmp_path / 'correct.ai', tmp_path / 'wrong.ai'
    _temporary_printed_line(correct, text='(owner to\nconfirm)')
    _temporary_printed_line(wrong, text='owner to)\n(confirm')
    good_glyphs, bad_glyphs = audit.printed_glyphs(correct)[0], audit.printed_glyphs(wrong)[0]
    assert audit.char_inventory(''.join(g['char'] for g in good_glyphs)) == audit.char_inventory(''.join(g['char'] for g in bad_glyphs))
    panel = [0, 0, 25.4, 25.4]
    assert audit.printed_latin_suffix(good_glyphs, panel) == '(ownertoconfirm)'
    assert audit.printed_latin_suffix(bad_glyphs, panel) == 'ownerto)(confirm'


def test_actual_margin_intrusion_and_hidden_crease_crossing_are_detected(tmp_path):
    unsafe, crossed = tmp_path / 'unsafe.ai', tmp_path / 'crossed.ai'
    _temporary_printed_line(unsafe, x_mm=1)
    _temporary_printed_line(crossed, x_mm=7, crease=True)
    panels = {'test': {'box_mm': [0, 0, 25.4, 25.4], 'safe_mm': [3, 3, 22.4, 22.4]}}
    margin_lines = audit.measure_lines(audit.printed_glyphs(unsafe)[0], panels, [])
    assert len(margin_lines) == 1 and not margin_lines[0]['inside_safe']
    creases = audit.actual_creases(crossed)
    assert len(creases) == 1
    fold_lines = audit.measure_lines(audit.printed_glyphs(crossed)[0], panels, creases)
    assert fold_lines[0]['crossed_crease_indexes'] == [0]
