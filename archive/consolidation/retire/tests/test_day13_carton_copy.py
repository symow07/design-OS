"""Day 13, §1.3 and the copy half of §1.1: the cartons' regulated copy on panels under 25 mm.

The owner: "the layout engine, for panels under 25 mm, sets the regulated copy in columns inside the safe area or runs it
vertically along the long sides; the fold check must report zero crossings; the EAN-13 ladder-wise and truncated as the
lipstick's; type down to the 5 pt floor, any overflow listed"; and, for the lipstick, "the Arabic panel's copy cleared
from the net line by one line's space". Read from the Day 13 records (docs/audit/day-13/{balm,lipstick}/carton/), and the
crossing count on a planted box. D-D13-6: the copy prints as it stands, marked.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import stick_carton as sc

D13 = Path(lm.REPO) / 'docs' / 'audit' / 'day-13'
BALM = D13 / 'balm' / 'carton'
LIPSTICK = D13 / 'lipstick' / 'carton'


def _records(folder):
    if not (folder / 'carton-fold-check.json').exists():
        pytest.skip('%s not built' % folder)
    return (json.loads((folder / 'carton-fold-check.json').read_text()),
            json.loads((folder / 'carton-fit-report.json').read_text()))


def test_the_balm_carton_reports_zero_crossings():
    """No line across a crease and none on another face (Day 12: three); the die's fold check passes; what stands past
    its safe area inside its own panel is named, and it is exactly the overflow the fit report lists."""
    rec, rep = _records(BALM)
    z = rec['zero_crossings']
    assert rec['schema'] == sc.SCHEMA and rec['fold_check']['passed'] and rec['die_untouched']['holds']
    assert z['crossings'] == 0 and z['across_a_crease'] == [] and z['on_another_face'] == []
    assert z['nothing_across_a_crease'] and z['no_box_on_another_face'] and rec['nothing_across_a_crease']
    over = {'%s line %d' % (ln['lang'], ln['line']) for ln in rep['overflow']}
    assert set(z['outside_the_safe_area']) == over
    assert rep['narrow_panels']['applies'] and rep['narrow_panels']['chosen']['crossing_lines'] == 0
    assert all(w < sc.NARROW_PANEL_MM for w in rep['narrow_panels']['panel_width_mm'].values())


def test_the_balm_copy_is_whole_at_the_floor_and_its_overflow_lies_in_its_own_panel():
    """Shrink never drop: every regulated line drawn and found in the file, nothing under 5 pt; each line still over at
    the floor said where it lies — in its own panel's margin, on no other face, cut off nowhere."""
    _rec, rep = _records(BALM)
    assert rep['copy']['all_found'] and rep['copy']['dropped'] == []
    assert rep['smallest_pt'] >= sc.BODY_FLOOR_PT and rep['body']['size_pt'] >= sc.BODY_FLOOR_PT
    assert rep['overflow_cut_off'] == []
    for ln in rep['overflow']:
        lies = ln['overflow_lies']
        assert lies['onto_faces'] == [] and not lies['cut_off'] and lies['past_the_trim_mm'] == 0.0
        assert ln['size_pt'] == sc.BODY_FLOOR_PT and ln['shrunk']


def test_the_carton_copy_is_marked_as_the_owner_ruled():
    """D-D13-6: the English the owner's draft, the Spanish and Arabic machine drafts for review, the INCI a placeholder
    'owner to supply', the Arabic claims 'owner to confirm' — nothing invented to fill a gap."""
    _rec, rep = _records(BALM)
    review = {(r['lang'], r['field']): r['review'] for r in rep['for_review']}
    assert review[('en', 'description')] == sc.OWNER_DRAFT == rep['sources']['en']['description']
    assert review[('es', 'description')] == review[('ar', 'description')] == sc.MACHINE_DRAFT
    assert all(review[(lang, 'ingredients')] == 'placeholder — owner to supply' for lang in sc.LANGS)
    assert review[('ar', 'claims')] == 'owner to confirm'


def test_the_balm_ean_is_ladder_wise_and_truncated_as_the_lipsticks():
    rec, rep = _records(BALM)
    ean = rep['ean']
    assert ean['orientation'].startswith('ladder') and ean['number'] is None
    assert ean['status'] == 'truncated — owner to confirm' and ean['bar_height_cut_mm'] > 0
    assert ean['drawn_mm'][1] == pytest.approx(rec['faces'][ean['panel']]['safe_mm'][2]
                                               - rec['faces'][ean['panel']]['safe_mm'][0], abs=0.01)


def test_the_balm_a4_is_at_100_percent():
    rec, _rep = _records(BALM)
    a4 = rec['a4']
    assert a4['page_mm'] == [210.0, 297.0] and a4['scale']['holds']
    assert a4['scale']['x']['scale'] == a4['scale']['y']['scale'] == 1.0
    assert (BALM / 'carton-1to1-A4.pdf').exists()


def test_a_box_wholly_on_another_face_counts_as_a_crossing():
    """Planted: Day 12's balm Arabic line 9 lay wholly past its crease, on the front, and no crease line ran through it;
    the count missed it. A box on another face now counts, and one inside its own panel's margin does not."""
    coords, _ = sc.die(sc.PRODUCTS['lip_balm'])
    fc_box = sc.faces(coords)
    x0, y0, x1, y1 = fc_box['side_left']['box']
    elements = [{'panel': 'side_left', 'element': 'planted on the front', 'flat': (x1 + 0.2, y0 + 10, x1 + 2.6, y0 + 20)},
                {'panel': 'side_left', 'element': 'planted in its margin', 'flat': (x1 - 2.5, y0 + 10, x1 - 0.6, y0 + 20)}]
    rows = {r['element']: r for r in sc.content_rows({'elements': elements}, coords, fc_box)}
    assert rows['planted on the front']['on_another_face'] and rows['planted on the front']['crosses_a_crease']
    assert not rows['planted in its margin']['crosses_a_crease'] and not rows['planted in its margin']['inside_safe']
    z = sc.zero_crossings({'passed': True}, list(rows.values()), True)
    assert z['crossings'] == 1 and z['on_another_face'] == ['planted on the front'] and not z['holds']
    assert z['outside_the_safe_area'] == ['planted on the front', 'planted in its margin']


def test_the_lipstick_arabic_copy_stands_one_line_clear_of_the_net_line():
    """The eye's round 1: the Arabic began about 2 mm after "3.5 g ℮ 0.12 oz". Now ZONE_GAP_MM plus one line's pitch
    at the size set, read back from the file; the three languages still whole, inside the safe area, at >= 5 pt."""
    rec, rep = _records(LIPSTICK)
    pitch = rep['body']['size_pt'] * sc.MM_PER_PT * sc.LEAD
    clear = rep['foot_clearance']
    assert clear['holds'] and clear['want_along_mm'] == pytest.approx(sc.ZONE_GAP_MM + pitch, abs=0.01)
    net = next(p for p in clear['parts'] if p['part'] == 'net')
    assert net['panel'] == 'back' and net['least_gap_along_mm'] >= sc.ZONE_GAP_MM + pitch - 0.01 >= 5.0
    assert rep['panel_plan']['chosen']['back'] == 'ar'
    assert rep['body']['fits'] and rep['overflow'] == [] and rep['smallest_pt'] >= sc.BODY_FLOOR_PT
    assert rec['zero_crossings']['holds'] and rec['zero_crossings']['crossings'] == 0
