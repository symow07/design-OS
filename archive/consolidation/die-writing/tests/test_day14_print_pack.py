"""Day 14 pack builder regressions: structural read-back only, no rendered look."""
import importlib.util
import json
from pathlib import Path
import re
from unittest.mock import patch

import fitz
import pytest

from apps.pipeline.services import print_pack as pp

ROOT = Path(__file__).resolve().parents[4]
PACK = ROOT / 'docs/audit/day-14/print-pack'
OLD = ROOT / 'docs/audit/day-13/print-pack'
CHANGED = {'zilal-lid-and-sides', 'zilal-lid-foil-mask', 'zilal-lid-relief-mask',
           'lipstick-carton', 'balm-carton', 'display-die-tiles', 'display-plan-elevation'}


@pytest.fixture(scope='module')
def record():
    return json.loads((PACK / 'print-pack.json').read_text())


def test_exactly_seven_replacements_and_twenty_two_byte_identical_copies(record):
    prior = json.loads((OLD / 'print-pack.json').read_text())
    before = {r['key']: r for r in prior['pieces']}
    assert len(record['pieces']) == len(list(PACK.rglob('*.pdf'))) == 29
    actual_changed = set()
    for row in record['pieces']:
        assert pp.sha256(ROOT / row['file']) == row['sha256']
        assert pp.sha256(ROOT / before[row['key']]['file']) == before[row['key']]['sha256']
        if row['sha256'] != before[row['key']]['sha256']:
            actual_changed.add(row['key'])
    assert actual_changed == CHANGED
    assert len(record['delta']['unchanged']) == 22
    assert pp.sheet_totals(record['pieces']) == {'A4': 19, 'A3': 33}
    # Preserve compatibility with Part B's unchanged list-completeness reader:
    # provenance hash tables must not count as duplicate printable entries.
    listed = re.findall(r'^\| `([^`]+\.pdf)` \|', (PACK / 'PRINT-LIST.md').read_text(), re.M)
    assert len(listed) == len(set(listed)) == 29
    assert set(listed) == {str((ROOT / r['file']).relative_to(PACK)) for r in record['pieces']}


def test_all_pack_pages_read_back_at_full_size_with_bars_and_marks(record):
    exceptions, pages, segments = [], 0, 0
    with patch.object(fitz.Page, 'get_pixmap', side_effect=AssertionError('D-D14-9: no rendering')):
        for row in record['pieces']:
            readings = pp.read_back(ROOT / row['file'], row['page_records'])
            for page in readings:
                read = page['read']
                pages += 1
                assert read['at_100']
                assert read['bar']['segments'] == 5
                assert read['bar']['length_mm'] == pytest.approx(50., abs=.1)
                if page['crop_marks'] is None:
                    exceptions.append(row['key'])
                else:
                    assert read['crop_marks_found'] == read['crop_marks_of'] > 0
                    segments += read['crop_marks_found']
                if 'overlap_marks' in read:
                    marks = read['overlap_marks']
                    assert marks['band_lines'] == marks['band_lines_of']
                    assert marks['registration'] == marks['registration_of']
    assert pages == 52 and segments == 640
    assert set(exceptions) == {'display-plan-elevation', 'collection-board-page-1', 'collection-board-page-2'}
    assert len(exceptions) == 3


def test_live_wrap_and_vector_masks_have_matching_trim_and_fold_registration(record):
    rows = {r['key']: r for r in record['pieces']}
    keys = ('zilal-lid-and-sides', 'zilal-lid-foil-mask', 'zilal-lid-relief-mask')
    positions = []
    for key in keys:
        row = rows[key]
        assert row['sources'][0]['path'] == 'docs/audit/day-14/zilal/wrap/lid-and-sides.pdf'
        item = row['page_records'][0]['items'][0]
        positions.append({k: item[k] for k in ('rect_mm', 'trim_mm', 'fold_marks_mm')})
    assert positions[0] == positions[1] == positions[2]
    assert [rows[k]['sources'][0]['page'] for k in keys] == [1, 2, 3]
    with fitz.open(ROOT / rows[keys[0]]['file']) as doc:
        copy = [t for t in doc[0].get_texttrace() if t['font'].startswith('Tajawal')]
        assert len(copy) == 10
    for key in keys[1:]:
        assert rows[key]['black_on_white_structural']['no_images']
        assert rows[key]['black_on_white_structural']['all_vector_fills_black']


def test_replaced_fonts_embedded_and_balm_overflow_disclosed(record):
    assert record['fonts']['unembedded_used_resource_count'] == 0
    assert record['fonts']['unembedded_changed_resource_count'] == 0
    assert all(not f['used_on_page'] and not f['changed_piece'] for f in record['fonts']['unembedded_resources'])
    rows = {r['key']: r for r in record['pieces']}
    for key in CHANGED:
        with fitz.open(ROOT / rows[key]['file']) as doc:
            assert all(doc.extract_font(f[0])[3] for page in doc for f in page.get_fonts(full=True))
    balm = rows['balm-carton']['source_facts']
    assert balm['crossings'] == 0 and balm['overflow_lines'] == 1
    assert balm['overflow'][0]['size_pt'] == 5
    assert balm['overflow'][0]['overflow_mm'] == pytest.approx(.543)
    assert '0.543 mm' in (PACK / 'PRINT-LIST.md').read_text()


def test_plan_reuses_prior_position_and_answers_keep_ten_questions(record):
    rows = {r['key']: r for r in record['pieces']}
    plan = rows['display-plan-elevation']['page_records'][0]
    assert plan['ground_patch']['at_mm'] == [6., 287.5]
    assert 'no render' in plan['ground_patch']['method_day14']
    source = (OLD / 'BLIND-REVIEW.md').read_text()
    answers = (ROOT / 'docs/audit/day-14/blind-review/ANSWERS.md').read_text()
    assert re.findall(r'^### .+$', answers, re.M) == re.findall(r'^### .+$', source, re.M)
    assert len(re.findall(r'^Answer:', answers, re.M)) == 10
    assert 'Table order after the 2 m blind review:' in answers
    # The owner may fill these after release; the builder's record says it wrote blanks.
    assert record['answers']['answers_filled'] == 0 and not record['answers']['table_order_filled']
