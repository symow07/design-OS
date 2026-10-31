"""Day 12 §2–§3 — the display's header (D-D12-2) and the balm's sketch round (D-D12-3): the header framed at the die's
250 : 110 by the least crop inside its drawn panel (a planted panel too short for its lettering is disqualified), the
name told from the logo by its likeness to the lid's own name, the header master's vectors the lid's own (inverse IoU
1, inside the safe area, the scaled hatch inside the press), the balm's sheet and its front-third check (a planted
hero outside it fails). Nothing here pays."""
import json

import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_balm as zb
from apps.pipeline.services import zilal_display as zd
from apps.pipeline.services import zilal_header as zh
from apps.pipeline.services import zilal_lipstick_master as zlm
from apps.pipeline.services import zilal_master as zm

HEADER = zd.HEADER / 'master' / 'header.json'
header_here = pytest.mark.skipif(not HEADER.exists(), reason='the header master is not built here')
INDIGO = (16, 26, 69)
GOLD = (196, 140, 104)


def _sheet_with(panel, letters, tmp_path, name='S9'):
    """A planted sketch: white, an indigo panel (x0, y0, x1, y1), rose-gold blocks (each a box) on it."""
    img = np.full((zd.SHEET_PX[1], zd.SHEET_PX[0], 3), 255, np.uint8)
    x0, y0, x1, y1 = panel
    img[y0:y1, x0:x1] = INDIGO
    for bx0, by0, bx1, by1 in letters:
        img[by0:by1, bx0:bx1] = GOLD
    dest = tmp_path / name
    dest.mkdir()
    Image.fromarray(img).save(dest / 'picture.png')
    return dest


def test_the_header_is_framed_at_the_dies_proportion_and_a_sketch_too_short_for_its_lettering_is_disqualified(
        tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'rel', str)
    true = 250.0 / 110.0
    # a panel wider than 250 : 110 whose lettering fits: framed by the least crop, the lettering inside the safe area
    dest = _sheet_with((30, 200, 1500, 800), [(200, 300, 700, 600), (900, 420, 1400, 480)], tmp_path)
    rec = zd.crop(dest)
    assert rec['qualifies'] and rec['lettering_inside_safe'] and rec['aspect_error'] < 0.005
    x0, y0, x1, y1 = rec['box_px']
    assert 30 <= x0 and x1 <= 1500 and 200 <= y0 and y1 <= 800
    assert (x1 - x0) / (y1 - y0) == pytest.approx(true, rel=0.005)
    # a panel taller than 250 : 110 whose lettering is taller than the frame allows: disqualified, on its height
    dest = _sheet_with((10, 90, 1526, 930), [(300, 120, 700, 880)], tmp_path, 'S8')
    rec = zd.crop(dest)
    assert not rec['qualifies'] and rec['fails_on'] == ['height']


def test_the_name_is_told_from_the_logo_by_its_likeness_to_the_lids_own_name():
    """The lid's traced name rasterised into a box reads as itself (high IoU); a solid block in the same box reads
    lower — the shape, not the box, decides."""
    rings, _, _ = zm.trace_name(zm.load_master_pick())
    geom = lm.rings_area(rings, 24)
    k = 6.0
    gx0, gy0, gx1, gy1 = geom.bounds
    s, dx, dy = zh.fit_to(geom.bounds, (10.0, 10.0, 110.0, 10.0 + 100.0 * (gy1 - gy0) / (gx1 - gx0)))
    from shapely import affinity
    placed = affinity.affine_transform(geom, [s, 0, 0, s, dx, dy])
    shape = (int(40 * k), int(130 * k))
    mask = lm.raster_fill(placed, shape, (0.0, 0.0), k)
    ys, xs = np.nonzero(mask)
    name = {'mask': mask, 'box_px': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]}
    block = np.zeros(shape, dtype=bool)
    block[name['box_px'][1]:name['box_px'][3], name['box_px'][0]:name['box_px'][2]] = True
    other = {'mask': block, 'box_px': name['box_px']}
    assert zh.name_likeness(name, geom, k) > 0.8 > zh.name_likeness(other, geom, k)


@header_here
def test_the_header_masters_letters_are_the_lids_own_scaled_inside_the_safe_area_and_the_press():
    rec = json.loads(HEADER.read_text(encoding='utf-8'))
    assert rec['hero']['inverse_iou_with_the_source'] == 1.0 and rec['logotype']['inverse_iou_with_the_source'] == 1.0
    assert rec['hero']['source']['pick_sha256'] == lm.sha256(zm.MASTER_PICK)
    assert all(rec['inside_safe'].values())
    h = rec['hero']['hatch_scaled']
    assert h['stroke_mm'] >= zm.HATCH_STROKE_MIN_MM and h['gap_mm'] >= zm.HATCH_GAP_MM - 0.02
    assert rec['finishes']['foil_limits']['holds']
    assert rec['resolution']['plate_ppi'] < rec['resolution']['lid_plate_ppi']        # reported, not a stop
    assert rec['pick']['crop']['qualifies'] and rec['pick']['crop']['lettering_inside_safe']


def test_the_balm_sheet_draws_both_wraps_at_their_proportion_and_the_front_third_inside_each():
    boxes = zb.rectangles()
    for key, (x0, y0, x1, y1) in boxes.items():
        w_mm, h_mm = zb.WRAPS_MM[key]
        assert (x1 - x0) / (y1 - y0) == pytest.approx(w_mm / h_mm, rel=0.003)
        third, rec = zb.front_third_px(key, (x0, y0, x1, y1))
        assert x0 < third[0] < third[2] < x1
        assert rec['width_mm'] == pytest.approx(np.pi * 18 / 3, abs=1e-3)


def test_the_balms_front_third_check_passes_a_hero_inside_and_fails_one_wider(tmp_path):
    k = 900 / zb.WRAPS_MM['body'][0]
    w, h = 900, int(round(900 * 42 / 58.5))
    third = zlm.front_third(58.5, 18.0)
    lo, hi = (v * k for v in third['span_mm'])
    for name, (x0, x1), passes in (('inside', (lo + 10, hi - 10), True), ('wider', (lo - 60, hi + 60), False)):
        img = np.zeros((h, w, 3), np.uint8)
        img[:] = INDIGO
        img[200:420, int(x0):int(x1)] = GOLD
        path = tmp_path / ('%s.png' % name)
        Image.fromarray(img).save(path)
        rec = zb.front_third_check(path)
        assert rec['hero_found'] and rec['passes'] is passes, (name, rec)


TRAY = zd.DISPLAY / 'tray' / 'tray.json'


def test_the_trays_drifts_and_calm_ground_never_take_the_lids_lettering_and_the_ground_is_deterministic():
    from apps.pipeline.services import zilal_tray as zt
    master = json.loads((zd.LID12 / 'master.json').read_text(encoding='utf-8'))
    assert zt.drift_boxes_clear(master)
    saved = zt.DRIFT_BOXES_MM
    try:
        zt.DRIFT_BOXES_MM = saved + ((10.0, 85.0, 60.0, 110.0),)       # a crop over "Enchanted": refused
        with pytest.raises(ValueError):
            zt.drift_boxes_clear(master)
    finally:
        zt.DRIFT_BOXES_MM = saved
    plate = zt.lid_plate()
    a, b = zt.calm(plate, 120, 80), zt.calm(plate, 120, 80)
    assert np.array_equal(a, b)


def test_the_turns_map_a_faces_corners_as_the_fold_does():
    from apps.pipeline.services import zilal_tray as zt
    # a right side (one quarter clockwise): the sheet's bottom-left corner is the upright face's bottom-right
    assert zt.sheet_corner_to_upright(0, 1, 1) == 'br'
    assert zt.sheet_corner_to_upright(0, 0, 0) == 'tl' and zt.sheet_corner_to_upright(0, 0, 2) == 'br'


@pytest.mark.skipif(not TRAY.exists(), reason='the tray is not built here')
def test_every_printed_face_of_the_die_has_its_design_and_the_gate_is_recorded():
    from apps.dielines.geometry import counter_tray_header as cth
    from apps.pipeline.services import zilal_tray as zt
    rec = json.loads(TRAY.read_text(encoding='utf-8'))
    die = cth.build_die(json.loads((zd.DISPLAY / 'die' / 'die.json').read_text(encoding='utf-8')))
    printed = {(p.name, n) for p in die.parts for n, _, pr in p.faces if pr}
    assert printed == {(f['part'], f['face']) for f in rec['faces']} == set(zt.FACES)
    assert {f['design'] for f in rec['faces'] if f['face'] in ('side skin R', 'side skin L')} == {'side'}
    assert rec['gate']['rounds'] and rec['gate']['repairs'] <= 1


@pytest.mark.skipif(not TRAY.exists(), reason='the tray is not built here')
def test_the_display_artwork_is_layered_with_its_die_locked_in_the_pdf_and_the_ai():
    """The page's one Download is the layered .ai: the artwork on its own layer, the cut and crease drawn from the die's
    geometry on theirs, locked (as the cartons'); the .ai the same layers as the PDF."""
    import fitz
    for name in ('display-artwork.pdf', 'display-artwork.ai'):
        with fitz.open(str(zd.DISPLAY / 'tray' / name)) as doc:
            ui = {c['text']: c for c in doc.layer_ui_configs()}
            assert set(ui) == {'artwork', 'cut', 'crease'}, name
            assert ui['cut']['locked'] and ui['crease']['locked'] and not ui['artwork']['locked']
