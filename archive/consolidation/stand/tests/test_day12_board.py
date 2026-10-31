"""Day 12 §5 — the collection board, page 1 (D-D12-4): one caption line per item inside its cell, no score and no
engine word (a planted caption carrying one is refused before anything is drawn), the product drawings labelled, a
piece not built captioned "carton — Day 13", the round labels cut at their die. Nothing here pays."""
import json

import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import collection_board as cb
from apps.pipeline.services import product_drawing as pdw

BOARD = cb.OUT / 'board.json'
board_here = pytest.mark.skipif(not BOARD.exists(), reason='the board is not built here')


def test_a_caption_with_an_engine_word_is_refused_and_a_plain_one_is_not():
    assert cb.refused_words('The lid — 190 × 120 mm, rose-gold foil and emboss') == []
    assert cb.refused_words('The lid master after the eye\'s gate') == ['master', 'gate', 'eye']
    assert cb.refused_words('Scored 7.8 by J1') == ['j1']
    # "eyeshadow" is a word of its own, not the eye
    assert cb.refused_words('The eyeshadow palette — 18 shades') == []


def test_the_board_refuses_before_drawing_when_a_caption_carries_an_engine_word(tmp_path, monkeypatch):
    real = cb.rows

    def planted(work, day11=cb.DAY11, day12=cb.DAY12):
        made = real(work, day11, day12)
        heading, cells, side = made[0]
        cells = [(cells[0][0], 'The lid master — 190 × 120 mm')] + cells[1:]
        return [(heading, cells, side)] + made[1:]

    monkeypatch.setattr(cb, 'rows', planted)
    with pytest.raises(ValueError, match='master'):
        cb.build(tmp_path)
    assert not (tmp_path / 'collection-board.pdf').exists()


def test_a_round_label_is_cut_at_its_die(tmp_path):
    folder = tmp_path / 'stick'
    folder.mkdir()
    (folder / 'stick.json').write_text(json.dumps({'label': {'diameter_mm': 16.0}}), encoding='utf-8')
    k = 600 / 25.4
    side = int(round(18.0 * k))
    Image.fromarray(np.full((side, side, 3), (8, 32, 69), np.uint8)).save(folder / 'label-flat.png', dpi=(600, 600))
    out = np.asarray(Image.open(cb.label_round(folder, 'stick.json', tmp_path / 'round.png')).convert('RGB'))
    ground = tuple(int(round(v * 255)) for v in cb.GROUND)
    assert tuple(out[side // 2, side // 2]) == (8, 32, 69)                       # inside the die: the label
    assert tuple(out[2, 2]) == ground                                            # the bleed's corner: the board
    # the die's edge: 8 mm from the centre is the label's, 8.3 mm the board's
    assert tuple(out[side // 2, int(side / 2 + 7.9 * k)]) == (8, 32, 69)
    assert tuple(out[side // 2, int(side / 2 + 8.3 * k)]) == ground


@board_here
def test_the_built_board_holds_its_checks_and_names_what_is_absent():
    rec = json.loads(BOARD.read_text(encoding='utf-8'))
    assert all(rec['checks'].values())
    captions = [c['caption'] for c in rec['cells']]
    assert len(captions) == 18 and not any(cb.refused_words(c) for c in captions)
    drawings = [c for c in rec['cells'] if c['picture'] and c['picture'].endswith('-drawing.png')]
    assert len(drawings) == 2 and all(pdw.LABEL in c['caption'] for c in drawings)
    for c in rec['cells']:
        if c['picture'] is None:
            assert c['caption'].endswith(cb.ABSENT) and c['caption'] in rec['absent']
        else:
            assert c['sha256'] == cb.lm.sha256(cb.lm.REPO / c['picture'])
    # page 2: Golden Hour as test one — its five pieces, captioned as page 1's are
    second = rec['page_2']['cells']
    assert len(second) == 5 and not any(cb.refused_words(c['caption']) for c in second)
    assert all(c['sha256'] == cb.lm.sha256(cb.lm.REPO / c['picture']) for c in second)


def _drawing(tmp_path, d_mm, h_mm, name):
    """A planted product drawing: white, a front view (Ø × height at the drawing's px/mm) at the margin, a caption
    word below it, and its record."""
    k = pdw.PX_PER_MM
    m = int(pdw.MARGIN_MM * k)
    w, h = int(round(d_mm * k)), int(round(h_mm * k))
    sheet = np.full((m + h + 120, m + w + 400, 3), 255, np.uint8)
    sheet[m:m + h, m:m + w] = (8, 32, 69)
    sheet[m + h + 20:m + h + 40, m:m + 60] = (30, 30, 30)                     # the caption's ink, below a gap
    png = tmp_path / ('%s.png' % name)
    Image.fromarray(sheet).save(png)
    rec = tmp_path / ('%s.json' % name)
    rec.write_text(json.dumps({'px_per_mm': k, 'case_d_mm': d_mm}), encoding='utf-8')
    return png, rec


def test_a_sticks_front_is_cropped_at_its_records_size_and_a_wrong_size_is_refused(tmp_path):
    png, rec = _drawing(tmp_path, 18.0, 70.0, 'balm')
    out, size = cb.stick_front(png, rec, 70.0, tmp_path / 'front.png')
    assert size == pytest.approx((18.0, 70.0), abs=cb.FRONT_TOLERANCE_MM)
    with pytest.raises(ValueError, match='not Ø 18 × 80'):
        cb.stick_front(png, rec, 80.0, tmp_path / 'front.png')                # the lipstick's height asked of a balm


FAMILY = cb.FAMILY / 'family.json'


@pytest.mark.skipif(not FAMILY.exists(), reason='the family sheet is not built here')
def test_the_family_sheet_shows_the_three_fronts_at_one_scale():
    rec = json.loads(FAMILY.read_text(encoding='utf-8'))
    scales = []
    for piece in rec['fronts']['pieces']:
        x0, y0, x1, y1 = piece['placed_mm']
        w, h = piece['size_mm']
        scales += [(x1 - x0) / w, (y1 - y0) / h]
        assert piece['sha256'] == cb.lm.sha256(cb.lm.REPO / piece['picture'])
    assert max(scales) - min(scales) < 0.002 and abs(scales[0] - cb.FRONTS_SCALE) < 0.002
    bottoms = {round(p['placed_mm'][3], 2) for p in rec['fronts']['pieces']}
    assert len(bottoms) == 1                                                    # the three stand on one line



def test_a_carton_is_shown_only_when_it_holds_its_own_checks(tmp_path):
    """The board shows a carton's front only when its fold check passed, everything is inside its safe areas and nothing
    crosses a crease; a carton whose copy runs over a crease (the balm's, on Day 12) is "carton — Day 13"."""
    held = {'fold_check': {'passed': True}, 'all_inside_safe': True, 'nothing_across_a_crease': True}
    path = tmp_path / 'carton-fold-check.json'
    path.write_text(json.dumps(held), encoding='utf-8')
    assert cb.carton_holds(path)
    path.write_text(json.dumps(dict(held, nothing_across_a_crease=False)), encoding='utf-8')
    assert not cb.carton_holds(path)
    assert not cb.carton_holds(tmp_path / 'absent.json')
