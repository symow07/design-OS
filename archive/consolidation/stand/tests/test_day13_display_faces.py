"""Day 13, §1.2 (D-D13-8, the last repair): the display's faces on the Day 13 die.

The owner: "each crop re-anchored inside its visible wall area with its fade ending before any crease (a test in the
engine: no drift pixel across a crease line); the inner back wall carries a stone bank as the sides do; the drifts are
cut along the lid's flowing banks, their masks following the stones' edges, not rectangles." The engine refuses a drift
with a pixel within 3 mm of a fold line, hole, slot or slit (``zilal_tray.drift_clear_of_creases``); here it is read
again from the pictures as placed on the die (the stones told by their colour from each face's calm ground), and on a
planted drift. Read from docs/audit/day-13/display/tray/ and the die it was laid on.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from apps.dielines.geometry import counter_tray_header as cth
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_tray as zt

TRAY = Path(lm.REPO) / 'docs' / 'audit' / 'day-13' / 'display' / 'tray'
DIE_JSON = Path(lm.REPO) / 'docs' / 'audit' / 'day-13' / 'display' / 'die' / 'die.json'


@pytest.fixture(scope='module')
def record():
    if not (TRAY / 'tray.json').exists():
        pytest.skip('the Day 13 tray is not built')
    return json.loads((TRAY / 'tray.json').read_text(encoding='utf-8'))


@pytest.fixture(scope='module')
def die():
    return cth.build_die(json.loads(DIE_JSON.read_text(encoding='utf-8')))


def _drifted(record):
    return [r for r in record['faces'] if r['drift']]


def _face(die, row):
    part = next(p for p in die.parts if p.name == row['part'])
    poly = next(f for n, f, _printed in part.faces if n == row['face'])
    return part, poly


def test_the_faces_are_laid_on_the_day13_die(record):
    """Built on the die with the closed slot insert (D-D13-2): its record and hash; the same 22 printed faces as Day 12
    (the gussets are unprinted, so no face is new); 13 of them carry a drift."""
    assert record['die_json'] == lm.rel(DIE_JSON) and record['die_json_sha256'] == lm.sha256(DIE_JSON)
    assert {(r['part'], r['face']) for r in record['faces']} == set(zt.FACES)
    assert record['faces_new_on_this_die'] == [] and len(_drifted(record)) == 13


def test_no_drift_pixel_lies_within_3_mm_of_a_crease_on_the_placed_pictures(record, die):
    """Each drift face's picture as placed on the die (engine/<face>--on-die.png, turned and clipped as it prints): its
    stones told from its own calm ground (ΔE00 over the engine's stone rule) and every one measured against every fold
    line, die-cut hole, slot and slit of its part — none nearer than the 3 mm band (less one pixel)."""
    for row in _drifted(record):
        part, _poly = _face(die, row)
        stem = Path(row['picture']).stem
        rgba = np.asarray(Image.open(TRAY / 'engine' / ('%s--on-die.png' % stem)).convert('RGBA')).astype(np.float64)
        weight = np.asarray(Image.open(Path(lm.REPO) / row['drift']['alpha'])).astype(np.float64) / 255.0
        on_sheet = zt.turn(weight, row['turn_quarters_cw'])
        assert on_sheet.shape == rgba.shape[:2]
        printed = rgba[..., 3] > 0
        calm = np.median(rgba[..., :3][printed & (on_sheet == 0)], axis=0)
        de = lm.delta_e00(lm.srgb_to_lab(rgba[..., :3].reshape(-1, 3)), lm.srgb_to_lab(calm[None, :])[0][None, :])
        stones = (de.reshape(printed.shape) > zt.STONE_DE) & printed
        assert stones.any(), row['face']
        dist = zt.sheet_distance(part, row['frame_mm'], printed.shape)
        px_mm = row['frame_mm'][2] / printed.shape[1]
        assert float(dist[stones].min()) >= zt.CREASE_BAND_MM - px_mm, (row['part'], row['face'])
        assert row['drift']['min_distance_to_a_crease_mm'] >= zt.CREASE_BAND_MM


def test_the_engine_refuses_a_planted_drift_across_a_crease(record, die):
    """Planted: the side skin's drift weight filled to its whole face, so it reaches the gusset and floor creases — the
    engine refuses it; its own drift passes the same check at the distance the record names."""
    row = next(r for r in _drifted(record) if r['face'] == 'side skin R')
    part, poly = _face(die, row)
    weight = np.asarray(Image.open(Path(lm.REPO) / row['drift']['alpha'])).astype(np.float64) / 255.0
    least = zt.drift_clear_of_creases(weight, part, poly, row['turn_quarters_cw'])
    # the saved alpha is 8-bit: its faintest tail (under half a level) reads as nothing, so it reads no nearer
    assert least >= row['drift']['min_distance_to_a_crease_mm'] - 0.02 >= zt.CREASE_BAND_MM - 0.02
    with pytest.raises(ValueError, match='from a fold line'):
        zt.drift_clear_of_creases(np.ones_like(weight), part, poly, row['turn_quarters_cw'])


def test_the_inner_back_wall_carries_a_stone_bank_as_the_sides_do(record):
    """The eye's round 1: the inner back wall "largely plain", a postage-stamp crop. Now the return flap that lines it
    carries one of the lid's banks at the lid's scale or more, its stone share of the face beside the sides'."""
    row = next(r for r in record['faces'] if (r['part'], r['face']) == ('tray', 'return flap'))
    side = next(r for r in record['faces'] if (r['part'], r['face']) == ('tray', 'side skin R'))
    d = row['drift']
    assert d is not None and d['bank'] in (1, 2) and d['scale_of_the_lid'] >= 1.0
    assert d['stones_kept'] >= 20 and d['stone_share'] >= side['drift']['stone_share']


def test_every_drift_follows_the_stones_edges_not_a_rectangle(record):
    """A rectangular vignette covers about all of its own bounding box; each drift's support (closed 3 mm) covers under
    the engine's 80 % of its box. Planted: a rectangle's weight reads 1.0."""
    for row in _drifted(record):
        assert row['drift']['support_closed_over_box'] < zt.RECTANGLE_SHARE, (row['part'], row['face'])
    rect = np.zeros((300, 400))
    rect[50:250, 60:340] = 1.0
    assert zt.support_over_box(rect, zt.K) == pytest.approx(1.0)


def test_a_drift_reaches_another_face_only_where_no_fold_lies_between(record, die):
    """No drift pixel crosses a fold into the next face. Where a face runs on in the same plane into an unprinted part
    with no crease between (a platform's key tab, which passes down through its floor slot out of sight), the drift's
    edge pixels may lie on it: counted, and each such face named here unprinted and creaseless against its face."""
    for row in _drifted(record):
        part, poly = _face(die, row)
        weight = np.asarray(Image.open(Path(lm.REPO) / row['drift']['alpha'])).astype(np.float64) / 255.0
        on_sheet = zt.turn(weight, row['turn_quarters_cw'])
        frame = row['frame_mm']
        kxy = (on_sheet.shape[1] / frame[2], on_sheet.shape[0] / frame[3])
        for name, other, printed in part.faces:
            if other.equals(poly) or not ((on_sheet > 0) & zt.raster(other, on_sheet.shape, frame[:2], kxy)).any():
                continue
            between = [c for c, line in part.creases if line.distance(poly) < 0.01 and line.distance(other) < 0.01]
            assert not printed and between == [], (row['part'], row['face'], name)


def test_the_banks_are_the_lids(record):
    """Each drift is one of the lid's banks, cut from the lid's own plate (its outline recorded), never a rectangle."""
    banks = {b['bank'] for b in record['banks']['banks']}
    assert record['banks']['plate'] == 'docs/audit/day-12/zilal/lid/engine/plate.png'
    assert all(r['drift']['bank'] in banks for r in _drifted(record))
    assert all(len(b['outline_mm']) > 4 for b in record['banks']['banks'])
