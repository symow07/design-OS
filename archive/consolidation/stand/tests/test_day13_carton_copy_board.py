"""The Day 13 board's carton test, moved out of apps/pipeline/tests/test_day13_carton_copy.py with collection_board (the
consolidation of 2026-10-28, the stand commit)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.pipeline.services import lid_master as lm

D13 = Path(lm.REPO) / 'docs' / 'audit' / 'day-13'


def test_the_board_shows_a_carton_that_reports_zero_crossings(tmp_path):
    """[Day 13] The board's rule read in the owner's §1.3 terms: a carton whose record counts its crossings shows when
    its fold check passed and it has none, a line over at the floor in its own margin listed, not a crossing; a box on
    another face hides it. The Day 13 board lays both cartons and the rebuilt display from Day 13's folders."""
    from apps.pipeline.services import collection_board as cb
    z = {'fold_check_passed': True, 'crossings': 0, 'nothing_across_a_crease': True, 'no_box_on_another_face': True,
         'all_inside_safe': False, 'outside_the_safe_area': ['en line 7']}
    path = tmp_path / 'carton-fold-check.json'
    path.write_text(json.dumps({'fold_check': {'passed': True}, 'all_inside_safe': False,
                                'nothing_across_a_crease': True, 'zero_crossings': z}), encoding='utf-8')
    assert cb.carton_holds(path)
    path.write_text(json.dumps({'fold_check': {'passed': True}, 'all_inside_safe': False, 'nothing_across_a_crease': False,
                                'zero_crossings': dict(z, crossings=1, no_box_on_another_face=False)}), encoding='utf-8')
    assert not cb.carton_holds(path)
    board = D13 / 'board' / 'board.json'
    if not board.exists():
        pytest.skip('the Day 13 board is not built')
    rec = json.loads(board.read_text(encoding='utf-8'))
    assert rec['absent'] == [] and rec['rebuilt_on_day13'] == sorted(
        'docs/audit/day-13/' + r for r in cb.REBUILT)
