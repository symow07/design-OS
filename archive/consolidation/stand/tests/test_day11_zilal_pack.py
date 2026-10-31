"""Day 11 §9 — Ẓilāl's base sticker and box (D-D11-4), and Golden Hour's relief end rule as the files of record carry it
(D-D11-5.1, D-D11-10).

Each check is a small function that returns what fails, run on the day's real records (nothing fails) and on a planted
copy with one thing changed (that thing fails). Nothing here pays and nothing is written under docs/audit."""
import json

import numpy as np
import pytest

from apps.pipeline.services import golden_hour_fixes as gf
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import palette_box as pb
from apps.pipeline.services import palette_sticker as ps
from apps.pipeline.services import zilal_box as zb
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_sticker as zs

sticker_here = pytest.mark.skipif(not (zs.OUT / 'sticker.json').exists(), reason='the sticker is not built here')
box_here = pytest.mark.skipif(not (zb.OUT / 'box.json').exists(), reason='the box is not built here')
golden_here = pytest.mark.skipif(not (gf.LID / 'master.json').exists(), reason='Golden Hour is not built here')


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


# --- the sticker ----------------------------------------------------------------------------------------------------

def test_glue_ci_keeps_every_colour_index_with_its_number_and_leaves_the_words():
    row = {'lang': 'ar', 'field': 'ingredients', 'text': 'May contain: CI 77491, CI 77891, CI 77007.'}
    words_before = row['text'].split()
    blocks = zs.glue_ci({'ar': [dict(row)]})
    units = blocks['ar'][0]['units']
    assert ['CI', '77007.'] in units and ['CI', '77491,'] in units
    assert [w for u in units for w in u] == words_before                     # the printed words unchanged
    control = ps.wrap_units(row['text'], 'ingredients')                      # control: unglued, CI stands alone
    assert ['CI'] in control and ['77007.'] in control


def _fc():
    return zs.faces()


def test_widowless_moves_one_word_down_and_a_short_paragraph_is_left_alone():
    fc = _fc()
    lines = [[('regular', 'one two three four five')], [('regular', 'six')]]
    moved = zs.widowless(lines, 60.0, 6.25, fc)
    assert [len(' '.join(t for _, t in ln).split()) for ln in moved] == [4, 2]
    assert ' '.join(t for ln in moved for _, t in ln) == 'one two three four five six'
    short = [[('regular', 'one two')], [('regular', 'three')]]                # control: a line of two keeps its word
    assert zs.widowless(short, 60.0, 6.25, fc) == short
    narrow = zs.widowless(lines, 2.0, 6.25, fc)                               # control: the new last line must fit
    assert narrow == lines


@sticker_here
def test_the_stickers_paragraphs_end_on_two_words_or_more_and_claims_wrap_by_claim():
    rec = _json(zs.OUT / 'sticker.json')
    assert rec['widows']['found'] == [] and rec['holds']['no_widow'] is True
    rows = [{'lang': 'ar', 'field': 'description', 'text': 'الحالمة.'}]      # control: a one-word last line is found
    assert zs.widows_in(rows)['found']


def test_letters_check_counts_only_letter_ink_left_as_the_plate_drew_it():
    window = np.full((20, 20, 3), (5, 20, 55), dtype=np.uint8)
    letters = np.zeros((20, 20), dtype=bool)
    letters[5:15, 5:15] = True
    alpha = np.zeros((20, 20))
    ground = window.copy()                                                    # plain ground returned as it was: no letter
    assert zs.letters_check(ground, window, letters, alpha)['holds'] is True
    inked = window.copy()
    inked[8:12, 8:12] = (200, 150, 110)                                       # control: rose-gold ink left in place
    rec = zs.letters_check(inked, inked, letters, alpha)
    assert rec['holds'] is False and rec['unchanged_letter_px'] == 16


@sticker_here
def test_the_stickers_record_holds_its_checks_and_its_gate_says_what_stays_open():
    rec = _json(zs.OUT / 'sticker.json')
    assert rec['all_hold'] is True
    assert all(v['worst_ratio'] >= zs.CONTRAST_MIN for v in rec['contrast']['per_ink'].values())
    refill = rec['ground']['bottom_refill']
    assert refill['filled_px'] > 0 and refill['source_not_calm_untouched_share'] < 0.05
    gate = rec['gate']
    assert gate['repairs'] == 1 and gate['holds'] is False and gate['open'] == []
    after = gate['after_the_gate']                                            # the owner's answer of 24 October, 4
    assert len(after['fixed']) == 1 and 0 < after['how']['narrowed_mm'] <= zs.AR_INCI_TRIM_MAX_MM


# --- the box --------------------------------------------------------------------------------------------------------

def _front_distances(master, scale, panel_w, panel_h):
    """Each lid element's nearest distance to the front panel's edges at ``scale`` (the lid centred, turned)."""
    lid_w, lid_h = lm.LID_MM
    out = {}
    for r in master['safe_area']:
        x0, y0, x1, y1 = r['ink_box_mm']
        along = min(panel_h / 2 - scale * (lid_w / 2 - x0), panel_h / 2 - scale * (x1 - lid_w / 2))
        across = min(panel_w / 2 - scale * (lid_h / 2 - y0), panel_w / 2 - scale * (y1 - lid_h / 2))
        out[r['element']] = min(along, across)
    return out


def test_front_scale_keeps_every_lid_element_4_mm_inside_the_panel():
    master = _json(zm.OUT / 'master.json')
    fc = pb.faces(pb.die()[0])
    fx0, fy0, fx1, fy1 = fc['front']['box']
    s = zb.front_scale(master, fx1 - fx0, fy1 - fy0)
    assert 1.0 < s <= (fx1 - fx0) / lm.LID_MM[1]
    assert min(_front_distances(master, s, fx1 - fx0, fy1 - fy0).values()) >= pb.SAFE_MM - 1e-6
    over = _front_distances(master, s + 0.01, fx1 - fx0, fy1 - fy0)          # control: 1 % more breaks the 4 mm
    assert min(over.values()) < pb.SAFE_MM


@box_here
def test_the_box_holds_its_fold_check_flaps_and_die_and_both_sides_draw_one_band():
    rec = _json(zb.OUT / 'box.json')
    fold = rec['fold_check']
    assert fold['all_inside_safe'] and fold['nothing_across_a_crease'] and fold['notch_clear']
    assert fold['die_untouched']['holds'] is True
    assert rec['clean']['holds'] is True and max(p['ink_mm2'] for p in rec['clean']['parts']) <= pb.CLEAN_INK_MAX_MM2
    assert rec['sides']['hero_measured_on_the_flat']['same'] is True
    assert rec['sides']['hero']['inverse_iou_with_the_source'] == 1.0
    hatch = rec['sides']['hero']['hatch']
    assert hatch['kept'] is False and hatch['scaled_pitch_mm'] < hatch['limits_mm']['stroke']
    assert rec['back']['holds'] is True
    gate = rec['gate']
    assert gate['repairs'] == 1 and [r['label'] for r in gate['rounds']] == ['r0', 'r1', 'r1-retry']
    assert gate['rounds'][1]['answered'] is False and 'image_4_vs_image_8' in gate['counter_evidence']


# --- Golden Hour's relief: the files of record are round 0's rule ----------------------------------------------------

@golden_here
def test_golden_hours_bars_end_by_contrast_and_the_repaired_build_is_kept_as_history():
    assert gf.RELIEF_ENDS_BY_ENGRAVING is False
    bars = _json(gf.LID / 'master.json')['finishes']['relief_mask']['bars']
    assert all(b['run_mm'] == b['ends_by']['contrast_run_mm'] for b in bars)
    repaired = _json(gf.LID / 'repair1' / 'master.json')['finishes']['relief_mask']['bars']
    assert any(b['run_mm'] != b['ends_by']['contrast_run_mm'] for b in repaired)     # control: the repair's rule moved them
    state = gf.relief_eye_state(gf.LID)
    assert state['state'] == 'looked' and state['holds'] is False
    assert gf.relief_eye_file(gf.LID).name == 'relief-eye.json'                # the look whose crops are on disk
