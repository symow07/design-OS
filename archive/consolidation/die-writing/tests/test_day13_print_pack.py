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
from apps.pipeline.services import print_pack as pp

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


def test_every_piece_the_owner_names_is_in_the_pack_with_its_sheet_paper_and_count(record):
    keys = [p['key'] for p in record['pieces']]
    assert sorted(keys) == sorted(OWNER_PIECES) and len(set(keys)) == len(keys)
    for p in record['pieces']:
        path = Path(lm.REPO) / p['file']
        assert path.exists() and lm.sha256(path) == p['sha256'], p['key']
        assert p['paper'] and p['count'] and sum(p['sheets'].values()) == p['pages'], p['key']
        assert set(p['sheets']) == {'A4', 'A3'}
    assert pp.sheet_totals(record['pieces']) == {'A4': 19, 'A3': 33}


def test_every_page_is_at_100_percent_with_a_50_mm_bar_and_its_crop_marks(record):
    """Each page read again from its file: every placed form a pure translation at scale 1, the bar's five segments
    50 mm long to 0.1 mm (measured from the page's drawings), all eight crop-mark segments of each trim found — but on
    the three pages that are the A3 sheet itself, which say why they carry none."""
    for p in record['pieces']:
        reads = pp.read_back(Path(lm.REPO) / p['file'], [dict(r, read=None) for r in p['page_records']])
        for r in reads:
            got = r['read']
            assert got['at_100'], (p['key'], got['page'])
            assert got['bar'] is not None and got['bar']['segments'] == pp.BAR_SEGMENTS, (p['key'], got['page'])
            assert abs(got['bar']['length_mm'] - pp.BAR_MM) <= pp.BAR_TOLERANCE_MM, (p['key'], got['page'])
            if r['crop_marks'] is None:          # a whole A3 sheet (the plan, the board): its trim is the paper's edge
                assert p['key'] in WHOLE_SHEETS and 'no room outside it for marks' in r['crop_marks_why']
                assert got['sheet_mm_read'] == [420.0, 297.0]
                continue
            assert got['crop_marks_found'] == got['crop_marks_of'] > 0, (p['key'], got['page'])


def test_a_piece_larger_than_a3_is_tiled_on_a3_with_its_overlap_marks(record):
    """The display's die and its artwork on the same A3 grid: every tile's dashed band lines and circled crosses found."""
    tiles = [p for p in record['pieces'] if p['kind'] == 'tiles']
    assert {p['key'] for p in tiles} == {'display-die-tiles', 'display-artwork-tiles'}
    assert len({p['pages'] for p in tiles}) == 1 and tiles[0]['sheets']['A3'] == tiles[0]['pages']
    for p in tiles:
        for r in pp.read_back(Path(lm.REPO) / p['file'], [dict(r, read=None) for r in p['page_records']]):
            o = r['read']['overlap_marks']
            assert o['band_lines'] == o['band_lines_of'] and o['registration'] == o['registration_of'] > 0
    assert record['facts']['artwork_matches_die']['same_size'] and record['facts']['tile_pages_match_die_builders']


def test_the_finish_masks_are_black_on_white(record):
    masks = [p for p in record['pieces'] if p['key'].endswith('-mask')]
    assert len(masks) == 4
    for p in masks:
        with fitz.open(str(Path(lm.REPO) / p['file'])) as doc:
            assert all(pp.chroma_max(doc, n, 72) <= pp.MASK_CHROMA_MAX for n in range(doc.page_count)), p['key']


def test_each_source_is_named_by_its_sha256_and_the_repaired_pieces_are_day13s(record):
    for p in record['pieces']:
        for s in p['sources']:
            assert lm.sha256(Path(lm.REPO) / s['path']) == s['sha256'], (p['key'], s['path'])
    assert all(c['day'] == 13 for c in record['choices'].values())
    stands = {p['key'] for p in record['pieces'] if str(p['prints_as_it_stands']).startswith('yes')}
    assert stands == {'lipstick-carton', 'balm-carton', 'display-artwork-tiles', 'display-parts'}


def test_a_planted_page_placed_at_99_percent_is_not_at_100(tmp_path):
    src = fitz.open()
    src.new_page(width=lm.pt(50), height=lm.pt(30)).draw_rect(fitz.Rect(0, 0, lm.pt(50), lm.pt(30)), fill=(0, 0, 0))
    doc = fitz.open()
    page = doc.new_page(width=lm.pt(210), height=lm.pt(297))
    page.show_pdf_page(fitz.Rect(lm.pt(20), lm.pt(20), lm.pt(20 + 49.5), lm.pt(20 + 29.7)), src, 0)
    path = tmp_path / 'planted.pdf'
    doc.save(str(path))
    with fitz.open(str(path)) as again:
        assert not pp.at_100(pp.placements(again, 0))


def test_the_print_list_and_the_blind_review_are_written():
    listing = (PACK / 'PRINT-LIST.md').read_text(encoding='utf-8')
    assert 'cut → crease → fold → glue' in listing and '| A4 | A3 |' in listing
    review = (PACK / 'BLIND-REVIEW.md').read_text(encoding='utf-8')
    assert review.count('\n### ') == 10 and '500 mm' in review
