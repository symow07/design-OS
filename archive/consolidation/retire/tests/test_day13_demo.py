"""Day 13, §4: the demo for Day 15 (docs/audit/day-13/demo/).

The owner: "DEMO-SCRIPT.md (≤ 90 lines): a ten-minute walk, in plain words, no engine codes ... Each step names the page
to open (its URL on the running site) and the physical piece to hand over"; "RUNNING-ORDER.md"; and "the site's demo tabs
checked on the running server: every page in the script answers 200 with its pictures (a capture record)". The live
check cannot run inside the suite (no server here); this reads its record, capture.json, against the two documents.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from apps.pipeline.services import lid_master as lm

DEMO = Path(lm.REPO) / 'docs' / 'audit' / 'day-13' / 'demo'
BASE = 'http://127.0.0.1:8000'
CODES = (r'D-D\d+-\d+', r'\bcounter_tray_header\b', r'\bJ[12]\b', r'§\d', r'\b[A-C]-\d\.\d\b', r'\bB3-r2\b',
         r'_(?:run|check)\.py\b', r'\bK\d\b')


def _urls(name):
    return [u[len(BASE):] for u in re.findall(r'`(%s/[^`\s]*)`' % re.escape(BASE), (DEMO / name).read_text(encoding='utf-8'))]


def test_the_script_is_a_ten_minute_walk_in_plain_words():
    text = (DEMO / 'DEMO-SCRIPT.md').read_text(encoding='utf-8')
    assert len(text.splitlines()) <= 90
    steps = re.findall(r'^\*\*(\d+)\. ', text, flags=re.M)
    assert steps == [str(n) for n in range(1, 11)]
    assert '9:00–10:00' in text and 'Hand over' in text and '## The numbers, on one sheet' in text
    for pattern in CODES:
        assert not re.search(pattern, text), pattern


def test_every_page_the_script_and_the_running_order_name_answered_200_with_its_pictures():
    rec = json.loads((DEMO / 'capture.json').read_text(encoding='utf-8'))
    named = set(_urls('DEMO-SCRIPT.md')) | set(_urls('RUNNING-ORDER.md'))
    assert named - {'/healthz'} <= set(rec['pages'])
    for path, page in rec['pages'].items():
        assert page['status'] == 200 and page['all_200'] and page['not_200'] == {}, path
        assert page['pictures'] > 0 and page['links_checked'] > 0, path
    assert rec['healthz']['status'] == 200 and rec['every_page_200_with_its_pictures']
    assert all(rec['pages'][p]['view_pictures_200'] for p in rec['pages'] if p.startswith('/dashboard/designs/'))


def test_the_running_order_has_the_night_before_the_table_the_tabs_and_a_fallback():
    text = (DEMO / 'RUNNING-ORDER.md').read_text(encoding='utf-8')
    for heading in ('## The night before', '## The table, left to right', '## The tabs, in order', '## If the site is down'):
        assert heading in text
    tabs = re.findall(r'^\d+\. `(%s/[^`]+)`' % re.escape(BASE), text, flags=re.M)
    assert len(tabs) == 8 and [t[len(BASE):] for t in tabs] == [u for u in _urls('RUNNING-ORDER.md') if u != '/healthz']
    for fallback in ('docs/audit/day-13/board/collection-board.png', 'docs/audit/day-13/creativity/sheet.png',
                     'docs/audit/day-13/print-pack/'):
        assert fallback in text and (Path(lm.REPO) / fallback).exists()
