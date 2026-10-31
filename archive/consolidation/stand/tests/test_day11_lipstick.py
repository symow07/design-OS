"""Day 11 §9 — the lipstick master (D-D11-7 as the owner's answer of 24 October changed it: D-D11-11): the seam, the
logotype placed from the lid's own vector, the cap's logo taken with its ®, the cleaning's grain, the bottom label Ø 18
with the ℮ at its legal 3 mm and its own width, the net line cleaned out of the body, and the gate's and the jury's
records.

Each check runs on a small planted picture or on the day's real records (nothing fails) and on a copy with one thing
changed (that thing fails). Nothing here pays; the label is built into pytest's temporary folder."""
import json

import fitz
import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_lipstick_master as zlm

lipstick_here = pytest.mark.skipif(not (zlm.OUT / 'lipstick.json').exists(), reason='the lipstick master is not built here')
pick_here = pytest.mark.skipif(not (zlm.LID / 'master.json').exists(), reason='the lid master is not built here')

INDIGO = (8, 32, 69)
ROSE_GOLD = (0xBE, 0x89, 0x6F)
CREAM = '#F3E6D8'


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _mm(pt):
    return pt * lm.MM_PER_INCH / 72.0


# --- the seam ---------------------------------------------------------------------------------------------------------

def _wrap(right, k):
    """A plain indigo wrap whose right end's last 2 mm is ``right`` (the colour the eye meets across the join)."""
    w, h = int(round(zlm.WRAP_MM[0] * k)), int(round(10 * k))
    rgb = np.empty((h, w, 3), np.uint8)
    rgb[:] = INDIGO
    rgb[:, -int(round(zlm.SEAM_BAND_MM * k)):] = right
    return rgb


def test_treat_seam_feathers_only_the_last_2_mm_and_says_when_the_join_stays_open():
    k = 8.0
    band = int(round(zlm.SEAM_BAND_MM * k))
    near = _wrap((22, 40, 84), k)
    out, rec = zlm.treat_seam(near, k)
    assert rec['before']['mean'] > zlm.SEAM_MEAN_MAX >= rec['after']['mean'] and rec['holds'] is True
    assert (out[:, :-band] == near[:, :-band]).all()                        # nothing outside the band is touched
    hard = _wrap((200, 60, 60), k)                                           # control: a join no feather closes
    assert zlm.treat_seam(hard, k)[1]['holds'] is False


# --- the logotype: the lid's own rings, one scale, on the sketch's ink box -------------------------------------------

@pick_here
def test_place_logotype_lands_on_the_sketchs_box_and_maps_back_onto_its_source():
    rings, src = zlm.logotype_source()
    k = 10.0
    gx0, gy0, gx1, gy1 = src['ink_box_lid_mm']
    s = 0.3
    box = [200.0, 300.0, 200.0 + s * (gx1 - gx0) * k, 300.0 + s * (gy1 - gy0) * k]
    _, rec = zlm.place_logotype(rings, src, box, k)
    assert rec['inverse_iou_with_the_source'] == 1.0 and abs(rec['scale'] - s) < 1e-9
    assert abs(rec['height_error_mm']) < 0.01
    assert max(abs(a - b / k) for a, b in zip(rec['placed_ink_mm'], box)) < 0.01
    tall = box[:3] + [box[1] + 2 * (box[3] - box[1])]                        # control: a box twice as tall as the mark
    assert zlm.place_logotype(rings, src, tall, k)[1]['height_error_mm'] < -1.0


# --- the cap's logo: the row of solid gold and its ® ------------------------------------------------------------------

ROW_END = 100 + 5 * 19 + 15


def _cap(mark_at):
    """An indigo cap at 10 px/mm with six rose-gold letters (1.5 × 3 mm, 0.4 mm apart, top at 80 px) and a thin mark
    for the ® — a 2 × 6 px stroke, opened away from the words as a vein is, kept by the logo's own 2 px opening — its
    top left at ``mark_at`` (px)."""
    k = 10.0
    rgb = np.empty((200, 400, 3), np.uint8)
    rgb[:] = INDIGO
    for i in range(6):
        x = 100 + i * 19
        rgb[80:110, x:x + 15] = ROSE_GOLD
    x, y = mark_at
    rgb[y:y + 6, x:x + 2] = ROSE_GOLD
    ground = lm.srgb_to_lab(np.array([[INDIGO]], np.uint8))[0, 0]
    return rgb, zlm.masks(rgb, ground), k


def test_cap_logo_box_takes_the_registered_mark_beside_the_last_letter_and_nothing_further():
    rec = zlm.cap_logo_box(*_cap((ROW_END + 4, 82)))
    # the logo's 2 px opening (an even ellipse, [[0, 1], [1, 1]]) moves a thin mark one px right
    assert ROW_END + 6 <= rec['box_px'][2] <= ROW_END + 7 and rec['mask'][84, ROW_END + 5]   # the ® in its box and mask
    far = zlm.cap_logo_box(*_cap((ROW_END + 40, 82)))                                 # control: 4 mm past the last letter
    assert far['box_px'][2] == ROW_END and not far['mask'][84, ROW_END + 40]
    low = zlm.cap_logo_box(*_cap((ROW_END + 4, 102)))                                 # control: at the row's foot
    assert low['box_px'][2] == ROW_END


# --- the cleaning's grain ---------------------------------------------------------------------------------------------

def _ground_and_stones(stone_cols):
    rng = np.random.default_rng(11)
    up = np.empty((200, 300, 3), np.int16)
    up[:] = INDIGO
    up += rng.integers(-3, 4, size=up.shape, dtype=np.int16)
    up[:, stone_cols] = (200, 70, 90)
    mask = np.zeros((200, 300), dtype=bool)
    mask[90:110, 40:60] = True
    ground = lm.srgb_to_lab(np.array([[INDIGO]], np.uint8))[0, 0]
    return np.clip(up, 0, 255).astype(np.uint8), mask, ground


def test_grain_fill_takes_its_grain_from_calm_ground_and_reports_a_stone_donor():
    # stones at the left, away from the donor the search finds first: the search takes the first wholly calm footprint
    # from its far corner, and its tone is read over its padded window — read beside stones it takes theirs in (measured
    # and listed in docs/audit/day-11/lipstick/master/grain-tone-check.json; the real wraps' fill kept)
    up, mask, ground = _ground_and_stones(slice(0, 20))
    out, shift, share = zlm.grain_fill(up, mask, ground, 10.0)
    assert share == 0.0 and shift != [0.0, 0.0]

    def spread(lab):
        return lm.delta_e00(lab, np.broadcast_to(ground, lab.shape))
    calm = np.zeros(mask.shape, dtype=bool)
    calm[:, 20:] = True
    own = spread(lm.srgb_to_lab(up)[calm & ~mask]).max()                     # the ground's own grain, untouched
    assert spread(lm.srgb_to_lab(out)[mask]).max() <= own + 1.0               # the fill no farther: no stone taken
    assert (out[~mask] == up[~mask]).all()                                    # only the footprint is filled
    stones, mask_, ground_ = _ground_and_stones(slice(0, 300))                # control: no calm ground to take from
    stones[mask_] = INDIGO
    assert zlm.grain_fill(stones, mask_, ground_, 10.0)[2] == 1.0


# --- the bottom label Ø 18 --------------------------------------------------------------------------------------------

def _label(tmp_path, monkeypatch):
    (tmp_path / 'engine').mkdir()
    monkeypatch.setattr(lm, 'rel', str)                                      # the record's paths: a temporary folder
    rec = zlm.label_master(tmp_path, '#082045', CREAM)
    return rec, fitz.open(str(tmp_path / 'label.pdf'))


def test_sign_segments_fill_a_box_of_the_signs_own_aspect_and_spill_from_a_narrower_one():
    a = zlm.sign_aspect()
    assert 1.0 < a < 1.2

    def xs(box):
        segs, _ = lm.sign_segments(box)
        v = [d[key] for s in segs for d in [s.model_dump()] for key in d if key.startswith('x')]
        return min(v), max(v)
    x0, x1 = xs((0.0, 0.0, 3.0 * a, 3.0))
    assert abs(x0) < 1e-9 and abs(x1 - 3.0 * a) < 1e-9
    assert xs((0.0, 0.0, 2.4, 3.0))[0] < -0.4                                 # control: the box the eye saw spill into the g


def test_the_label_stands_inside_its_safe_ring_with_the_sign_3_mm_at_its_own_width(tmp_path, monkeypatch):
    rec, pdf = _label(tmp_path, monkeypatch)
    rows = rec['rows']
    assert rec['holds']['inside_safe'] and rec['holds']['above_floor']
    assert min(r['die_clearance_mm'] for r in rows) >= zlm.LABEL_SAFE_MM
    assert min(r['size_pt'] for r in rows) >= zlm.FLOOR_PT
    page = pdf[0]
    sign = [d['rect'] for d in page.get_drawings() if 2.5 < _mm(d['rect'].height) < 3.5]
    assert len(sign) == 1
    assert abs(_mm(sign[0].height) - zlm.LABEL_SIGN_MM) < 0.01
    assert abs(sign[0].width / sign[0].height - zlm.sign_aspect()) < 0.01
    figures = [s['bbox'] for b in page.get_text('dict')['blocks'] for ln in b['lines'] for s in ln['spans']
               if s['text'] == '3.5 g']
    assert _mm(sign[0].x0 - figures[0][2]) > 0.5                              # a word space, never abutting the g
    die = [_mm(d['rect'].width) for d in pdf[1].get_drawings()]
    assert sorted(round(v, 2) for v in die) == [zlm.LABEL_D_MM - 2 * zlm.LABEL_SAFE_MM, zlm.LABEL_D_MM]


def test_a_shade_set_too_large_leaves_the_safe_ring(tmp_path, monkeypatch):
    monkeypatch.setattr(zlm, 'LABEL_SHADE_CAP_MM', 3.0)                       # control: the shade at twice its cap
    rec, _ = _label(tmp_path, monkeypatch)
    shade = [r for r in rec['rows'] if r['row'] == 'shade'][0]
    assert shade['inside_safe'] is False and rec['holds']['inside_safe'] is False


# --- the master as built: the net line cleaned, the seams, the logotype, the gate, the jury -------------------------

def _cream_share(path, box_mm, rows_down):
    im = np.asarray(Image.open(path).convert('RGB'))
    k = im.shape[1] / zlm.WRAP_MM[0]
    x0, y0, x1, y1 = (int(round(v * k)) for v in box_mm)
    m = zlm.masks(im, zlm.ground_lab(im))
    return float(m['cream'][y0 + rows_down:y1 + rows_down, x0:x1].mean())


@lipstick_here
def test_the_net_line_is_cleaned_out_of_the_body_and_was_there_in_the_pick():
    rec = _json(zlm.OUT / 'lipstick.json')
    body = rec['body']
    assert body['net_line']['cleaned_out'] is True
    k = body['trim']['px_per_mm']
    box_mm = [v / k for v in body['net_line']['sketch_box_px']]
    assert _cream_share(zlm.REPO / body['files']['flat'], box_mm, 0) < 0.005
    pick = zlm.REPO / body['sketch']['path']                                 # control: the pick's own painted line
    assert _cream_share(pick, box_mm, body['trim']['rows_cut_top']) > 0.05


@lipstick_here
def test_the_lipstick_record_holds_its_seams_logotype_and_label_and_its_gate_says_what_stays_open():
    rec = _json(zlm.OUT / 'lipstick.json')
    for part in ('body', 'cap'):
        assert rec[part]['seam']['holds'] is True and rec[part]['seam']['after']['mean'] <= zlm.SEAM_MEAN_MAX
    logo = rec['body']['logotype']
    assert logo['inverse_iou_with_the_source'] == 1.0 and abs(logo['height_error_mm']) <= 0.1
    assert all(rec['label']['holds'].values())
    gate = rec['gate']
    assert gate['repairs'] == 1 and gate['holds'] is False
    assert [r['round'] for r in gate['rounds']] == [0, 1] and all(r['answered'] for r in gate['rounds'])
    assert len(gate['after_the_gate']['fixed']) == 2 and 'the_sign' in gate['measured_vs_eye']


@lipstick_here
def test_the_lipstick_jury_is_recorded_once_with_the_leads_measured_notes_beside_it():
    jury = zlm.OUT / 'jury'
    verdict = _json(jury / 'verdict.json')
    assert verdict['rubric_version'] == 'v2' and verdict['raw']['stricter_mean'] == 6.1
    notes = _json(jury / 'lead-notes.json')
    assert notes['verdict']['stricter_mean'] == verdict['raw']['stricter_mean']
    assert any('label.pdf page 2' in n['measured'] for n in notes['measured_beside_the_named_issues'])
