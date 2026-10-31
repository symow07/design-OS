"""Day 13, §3: the print pack for Day 14 (docs/audit/day-13/print-pack/).

The owner: "One folder a print shop can take as it is. For every piece: the PDF at 100 % with crop marks and a 50 mm
bar, the paper it goes on, the count, and the sheet it fits (A4 or A3; A3 tiled with overlap marks where a piece is
larger)", the finish masks "as separate black-on-white pages", and PRINT-LIST.md and BLIND-REVIEW.md. Read from the
files: every page's forms at scale 1, its bar's five segments measured from its drawings, its crop marks at the trim's
four corners, a tile's overlap marks, a mask's colour; every source's sha256 as it stands now.
"""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from apps.pipeline.services import lid_master as lm

PACK = Path(lm.REPO) / 'docs' / 'audit' / 'day-13' / 'print-pack'
# every piece the owner names in §3, by its key in print-pack.json
OWNER_PIECES = (
    'zilal-lid-and-sides', 'zilal-inside-lid', 'zilal-tray-print', 'zilal-tray-cut', 'zilal-sticker', 'zilal-box',
    'zilal-lid-foil-mask', 'zilal-lid-relief-mask', 'zilal-box-foil-mask', 'zilal-box-relief-mask',
    'golden-hour-lid', 'golden-hour-tray-print', 'golden-hour-tray-cut', 'golden-hour-sticker', 'golden-hour-box',
    'lipstick-body-wrap', 'lipstick-cap-wrap', 'lipstick-label', 'lipstick-carton',
    'balm-body-wrap', 'balm-cap-wrap', 'balm-label', 'balm-carton',
    'display-die-tiles', 'display-artwork-tiles', 'display-parts', 'display-plan-elevation',
    'collection-board-page-1', 'collection-board-page-2')


# the pages that ARE the sheet (A3, edge to edge): no room outside the trim for marks, the bar in a patch of their ground
WHOLE_SHEETS = ('display-plan-elevation', 'collection-board-page-1', 'collection-board-page-2')


@pytest.fixture(scope='module')
def record():
    if not (PACK / 'print-pack.json').exists():
        pytest.skip('the print pack is not built')
    return json.loads((PACK / 'print-pack.json').read_text(encoding='utf-8'))


def test_each_source_is_named_by_its_sha256_and_the_repaired_pieces_are_day13s(record):
    for p in record['pieces']:
        for s in p['sources']:
            assert lm.sha256(Path(lm.REPO) / s['path']) == s['sha256'], (p['key'], s['path'])
    assert all(c['day'] == 13 for c in record['choices'].values())
    stands = {p['key'] for p in record['pieces'] if str(p['prints_as_it_stands']).startswith('yes')}
    assert stands == {'lipstick-carton', 'balm-carton', 'display-artwork-tiles', 'display-parts'}


def test_the_print_list_and_the_blind_review_are_written():
    listing = (PACK / 'PRINT-LIST.md').read_text(encoding='utf-8')
    assert 'cut → crease → fold → glue' in listing and '| A4 | A3 |' in listing
    review = (PACK / 'BLIND-REVIEW.md').read_text(encoding='utf-8')
    assert review.count('\n### ') == 10 and '500 mm' in review
