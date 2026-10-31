"""Day 14 pack builder regressions: structural read-back only, no rendered look."""
import importlib.util
import json
from pathlib import Path
import re
from unittest.mock import patch

import fitz
import pytest


ROOT = Path(__file__).resolve().parents[4]
PACK = ROOT / 'docs/audit/day-14/print-pack'
OLD = ROOT / 'docs/audit/day-13/print-pack'
CHANGED = {'zilal-lid-and-sides', 'zilal-lid-foil-mask', 'zilal-lid-relief-mask',
           'lipstick-carton', 'balm-carton', 'display-die-tiles', 'display-plan-elevation'}


@pytest.fixture(scope='module')
def record():
    return json.loads((PACK / 'print-pack.json').read_text())


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
