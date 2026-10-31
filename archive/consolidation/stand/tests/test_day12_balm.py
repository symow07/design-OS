"""Day 12 §3 — the lip balm's master (D-D12-3) by the lipstick's path: the hero بلسم inside the front third of the Ø 18
case on the master's own vectors; "Enchanted Rose" the lid's own logotype (inverse IoU 1.0), raised to the 2.5 mm cap
floor where it then still fits the front third and the stack, else kept and listed with its numbers; the bottom label
Ø 16's rows inside the safe ring and over 5 pt, its ℮ the lid's sign at exactly 3 mm on the figures' baseline; the
sheet's dashed front-third box found, cleaned (a pixel is dash only where it is lighter than EACH side) and proved gone
per line by the ridge per dash site — the uncleaned upscale failing on every one of the 8 lines — and the stones'
pixels proved untouched (a planted indigo bite inside a stone on a dash line fails); the seams' mean ΔE00 ≤ 2; the
product drawing deterministic and labelled (D-D12-1.4); a pick whose hero breaks the front third refused. Each check
runs on the day's real record or a planted case, with a control that fails. Nothing here pays.

[D-D12-8, the balm's one repair after the eye's round 0] The cleaning's ghost (the word boxes' darker panel and its
tile seams, the dash lines' trace) rebuilt on ground pixels only, and the ghost proof — no straight edge along any dash
line or cleaned box side, on ground pixels, against bars from the uncleaned sketch's own ground — holding on the final
plates, failing on the plates before the rebuild (the plates the eye saw), failing again when a straight tone step is
laid back; on a planted case the same, a stone and a vein untouched to the bit."""
import copy
import json

import cv2
import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import product_drawing as pdw
from apps.pipeline.services import zilal_balm as zb
from apps.pipeline.services import zilal_balm_master as zbm
from apps.pipeline.services import zilal_lipstick_master as zlm
from apps.pipeline.services import zilal_master as zm

MASTER = zbm.OUT
built = pytest.mark.skipif(not (MASTER / 'balm.json').exists(), reason='the balm master is not built here')
K_PX_PER_MM = 896 / 58.5                                # the sketch's scale (its 896 px across the 58.5 mm wrap)


def _rec():
    return json.loads((MASTER / 'balm.json').read_text(encoding='utf-8'))


# --- pure: the case, the trim, the dashes, the seam, the drawing, the floor ----------------------------------------------

def test_the_front_third_of_the_18_mm_case_and_the_balms_overlap():
    third = zlm.front_third(58.5, 18.0)
    assert third['width_mm'] == pytest.approx(18.8496, abs=1e-4)
    assert third['span_mm'][0] == pytest.approx(20.8009, abs=1e-4) and third['span_mm'][1] == pytest.approx(39.6504, abs=1e-4)
    assert zbm.OVERLAP_MM == pytest.approx(58.5 - np.pi * 18.0, abs=1e-9) and zbm.OVERLAP_MM == pytest.approx(1.951, abs=1e-3)
    assert zbm.BODY_MM == (58.5, 42.0) and zbm.CAP_MM == (58.5, 32.0) and zbm.LABEL_D_MM == 16.0


def test_the_trim_keeps_one_scale_for_each_wraps_own_height():
    body, rec = zbm.trim_rows(np.zeros((644, 896, 3), np.uint8), zbm.BODY_MM)
    assert body.shape[:2] == (643, 896) and rec['shift_rows_px'] == 0
    cap, rec = zbm.trim_rows(np.zeros((491, 896, 3), np.uint8), zbm.CAP_MM)
    assert cap.shape[:2] == (490, 896)
    # the lipstick's own trim (64.8 × 42) would have cut 63 rows from the balm's body: the reason for the balm's copy
    lip, _ = zlm.trim_rows(np.zeros((644, 896, 3), np.uint8))
    assert lip.shape[0] == 581


GROUND = (8, 24, 66)
CORAL = (214, 120, 112)
DASH_WHITE = np.array((245, 225, 225), np.float64)
PLANTED_BOX = (140, 70, 330, 250)                      # the box the "model" drew …
SHEET_BOX = [142, 68, 328, 253]                        # … a few px off the sheet's own position


def _planted():
    """An indigo ground with grain, a coral stone whose top edge runs along the box's top line (a step, not a dash) and
    which the right line crosses, and the sheet's dashed box drawn as the model draws it: 6 px dashes 6 px apart, each
    the dash's warm white laid over what lies beneath at 0.55 (the opacity read on S6), with a darker halo row beside
    it (× 0.8, as S6's halo on the red stone: L* 32 against 38)."""
    rng = np.random.default_rng(7)
    im = np.empty((320, 470, 3), np.float64)
    im[:] = GROUND
    im += rng.normal(0, 1.5, im.shape)
    yy, xx = np.mgrid[:320, :470]
    stone = ((xx - 345) / 70.0) ** 2 + ((yy - 110) / 55.0) ** 2 <= 1.0          # the right line crosses its body
    stone &= yy >= 70                                   # its top edge exactly on the top line's row
    im[stone] = np.array(CORAL) + rng.normal(0, 1.5, (int(stone.sum()), 3))
    clean = np.clip(np.round(im), 0, 255).astype(np.uint8)
    out = clean.astype(np.float64)
    x0, y0, x1, y1 = PLANTED_BOX

    def dash(ys, xs, halo):
        out[ys, xs] = 0.55 * DASH_WHITE + 0.45 * out[ys, xs]
        out[halo] *= 0.8
    for x in range(x0, x1, 12):
        xs = np.arange(x, min(x + 6, x1))
        dash(np.full_like(xs, y0), xs, (np.full_like(xs, y0 - 1), xs))
        dash(np.full_like(xs, y1), xs, (np.full_like(xs, y1 + 1), xs))
    for y in range(y0, y1, 12):
        ys = np.arange(y, min(y + 6, y1))
        dash(ys, np.full_like(ys, x0), (ys, np.full_like(ys, x0 - 1)))
        dash(ys, np.full_like(ys, x1), (ys, np.full_like(ys, x1 + 1)))
    return clean, np.clip(np.round(out), 0, 255).astype(np.uint8), stone


def test_a_planted_dashed_box_is_found_cleaned_and_proved_gone_on_every_line_with_controls():
    clean, planted, stone = _planted()
    lines = zbm.find_dashes(planted, SHEET_BOX)
    assert [ln['found_pos_px'] for ln in lines] == [140, 330, 70, 250]
    out, ridge_px, filled, sites, rec = zbm.clean_dashes(planted, lines)
    assert rec['ridge_px'] > 0 and rec['colour']['samples'] > 0
    proof = zbm.dash_proof(planted, lm.upscale(out), lines, sites, 470 / K_PX_PER_MM)
    assert proof['gone'] and all(r['gone'] and r['uncleaned_fails'] for r in proof['lines'])
    # control, on each line: the uncleaned picture read the same way is NOT gone
    uncleaned = zbm.dash_proof(planted, lm.upscale(planted), lines, sites, 470 / K_PX_PER_MM)
    assert [r['gone'] for r in uncleaned['lines']] == [False] * 4
    assert all(r['after_max_L'] > zbm.DASH_GONE_L for r in uncleaned['lines'])
    # nothing outside the dash's pixels moves; over the stone the fill is the stone's own colour, never indigo
    assert (out[~filled] == planted[~filled]).all()
    import cv2
    inside = cv2.erode(stone.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)   # 2 px inside its edge
    on_stone = filled & inside
    assert on_stone.sum() > 30
    lab = lm.srgb_to_lab(out).astype(np.float64)
    coral = lm.srgb_to_lab(np.array([[CORAL]], np.uint8))[0, 0]
    assert np.median(np.linalg.norm(lab[on_stone] - coral, axis=1)) < 8
    assert lab[on_stone][:, 0].min() > coral[0] - 15                                    # no indigo bite (L* ≈ 10)
    # control: Telea over the same pixels from all round (the method the review found biting) lays indigo there
    telea = cv2.inpaint(planted, cv2.dilate(filled.astype(np.uint8), np.ones((3, 3), np.uint8)), 2, cv2.INPAINT_TELEA)
    assert lm.srgb_to_lab(telea)[..., 0][filled & stone].min() < coral[0] - 15
    # the stone's top edge on the top line is a step (lighter than one side only): kept where no dash lies on it
    gaps = np.zeros_like(filled)
    gaps[70, 300:330] = True
    assert (out[gaps & ~filled] == planted[gaps & ~filled]).all() and (gaps & ~filled & stone).sum() > 5


def test_the_stones_proof_holds_on_a_clean_fill_and_fails_on_a_planted_bite():
    clean, planted, stone = _planted()
    lines = zbm.find_dashes(planted, SHEET_BOX)
    out, ridge_px, filled, sites, _ = zbm.clean_dashes(planted, lines)
    words = np.zeros(stone.shape, dtype=bool)
    plate = lm.upscale(out)
    proof = zbm.stones_proof(planted, out, ridge_px, words, plate, K_PX_PER_MM, 0, 470 / K_PX_PER_MM)
    assert proof['holds'] and proof['stone_px_read'] > 10000
    # control: an indigo bite 3 × 3 px inside the stone, 4 px beside the right line, laid on the plate, fails
    bitten = plate.copy()
    bitten[2 * 120:2 * 123, 2 * 335:2 * 338] = GROUND
    bad = zbm.stones_proof(planted, out, ridge_px, words, bitten, K_PX_PER_MM, 0, 470 / K_PX_PER_MM)
    assert not bad['holds'] and bad['over_2'] > 0
    # control: Telea over the band (the method the review found biting) fails the proof
    band = np.zeros(stone.shape, dtype=bool)
    band[66:75, 140:331] = True
    band[70:251, 326:335] = True
    import cv2
    telea = cv2.inpaint(planted, band.astype(np.uint8), 2, cv2.INPAINT_TELEA)
    assert not zbm.stones_proof(planted, telea, ridge_px, words, lm.upscale(telea), K_PX_PER_MM, 0,
                                470 / K_PX_PER_MM)['holds']


def test_the_logotype_floor_raises_where_it_fits_and_keeps_where_it_would_leave_the_front_third():
    rings, src = zlm.logotype_source()
    third = zlm.front_third(58.5, 18.0)
    k = K_PX_PER_MM
    cap_lid = json.loads((zbm.LID12 / 'master.json').read_text(encoding='utf-8'))['name']['measures']['cap_height_mm']
    # at the floor the logotype is as wide as the floor makes it whatever its sketched width (its cap goes with its
    # width): a 5 mm logotype centred on the front third's centre grows inside it
    c = third['centre_mm']
    small = [(c - 2.5) * k, 27.3 * k, (c + 2.5) * k, 30.6 * k]
    placed, transform = zlm.place_logotype(rings, src, small, k)
    out, move, rec = zbm.logotype_floor(rings, placed, transform, cap_lid, third, 25.69, [25.2, 31.86, 35.58, 33.1])
    assert rec['raised'], rec
    assert rec['scale_to_the_floor'] == pytest.approx(2.5 / (cap_lid * transform['scale']), rel=1e-4)
    assert rec['inverse_iou_with_the_source'] > 0.99 and move == pytest.approx(rec['lip_balm_move_down_mm'], abs=1e-3)
    # control: the sketch's own logotype box (22.46–38.65 mm) raised the same way crosses the front third: kept
    wide = [344, 417, 592, 470]
    placed, transform = zlm.place_logotype(rings, src, wide, k)
    out, move, rec = zbm.logotype_floor(rings, placed, transform, cap_lid, third, 25.69, [25.2, 31.86, 35.58, 33.1])
    assert not rec['raised'] and out is placed and move == 0.0
    assert rec['box_at_the_floor_mm'][2] > third['span_mm'][1] and 'front third' in rec['why']


def test_a_pick_whose_hero_breaks_the_front_third_is_refused_before_anything_is_read(tmp_path):
    crop = zbm.crop_record(zb.SKETCHES / 'S6')
    bad = copy.deepcopy(crop)
    bad['front_third']['passes'] = False
    with pytest.raises(ValueError, match='front third'):
        zbm.body_master(tmp_path / 'no such sketch', tmp_path, bad)


def test_the_seam_is_feathered_at_the_balms_overlap():
    k = 30.0
    im = np.zeros((300, int(58.5 * k), 3), np.uint8)
    im[:] = (10, 30, 70)
    im[:, -int(3 * k):] = (20, 40, 88)                  # the right end a little unlike the left start
    out, rec = zbm.treat_seam(im, k, zbm.OVERLAP_MM)
    assert rec['before']['mean'] > 2 and rec['after']['mean'] <= 2 and rec['holds']
    assert float(zbm.join_profile(im, k, zbm.OVERLAP_MM).mean()) > 2                 # control: untreated, it fails
    assert float(zbm.join_profile(out, k, zbm.OVERLAP_MM).mean()) <= 2


def _wrap(tmp_path, name, colour, h_px):
    im = np.zeros((h_px, 702, 3), np.uint8)
    im[:] = (8, 32, 69)
    im[h_px // 4:3 * h_px // 4, 300:420] = colour
    path = tmp_path / name
    Image.fromarray(im).save(path)
    return path


def test_the_balms_drawing_is_deterministic_and_says_it_is_a_drawing(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'rel', str)
    body = _wrap(tmp_path, 'body.png', (190, 137, 111), 504)
    cap = _wrap(tmp_path, 'cap.png', (120, 90, 160), 384)
    third = zlm.front_third(58.5, 18.0)
    bands = [('body', body, zbm.BODY_MM, 1.0, 40.0), ('cap', cap, zbm.CAP_MM, 1.0, 30.0)]
    a = pdw.draw('a balm', bands, 18.0, third['centre_mm'], zbm.OVERLAP_MM, '#051C41', tmp_path / 'a.png')
    b = pdw.draw('a balm', bands, 18.0, third['centre_mm'], zbm.OVERLAP_MM, '#051C41', tmp_path / 'b.png')
    assert a['sha256'] == b['sha256'] and a['label'] == pdw.LABEL == 'drawing, not a render'
    other = _wrap(tmp_path, 'other.png', (30, 160, 120), 504)
    c = pdw.draw('a balm', [('body', other, zbm.BODY_MM, 1.0, 40.0), bands[1]], 18.0, third['centre_mm'],
                 zbm.OVERLAP_MM, '#051C41', tmp_path / 'c.png')
    assert c['sha256'] != a['sha256']


def test_the_label_sign_proof_has_power():
    segs, _ = lm.sign_segments((0.0, 0.0, 2.5 * zlm.sign_aspect(), 2.5))
    p = zbm.sign_proof(segs, 2.5, 0.7)
    assert p['the_lids_sign'] and not p['exactly_3_mm'] and p['on_the_baseline']
    segs, _ = lm.sign_segments((0.0, 0.0, 3.0 * zlm.sign_aspect(), 3.0))
    p = zbm.sign_proof(segs, 3.2, 0.7)
    assert p['exactly_3_mm'] and not p['on_the_baseline']


# --- D-D12-8: the cleaning's ghost rebuilt on ground pixels, proved without a straight edge ---------------------------

GHOST_SKETCH_PX = (240, 360)                           # a planted wrap's sketch (rows, columns) at the balm's scale
GHOST_LINE_COL_PX = 100                                # its dash line's column …
GHOST_LINE_ROWS_PX = (20, 220)                         # … from row 20 to 220
GHOST_BOX_PX = (150, 120, 250, 150)                    # its cleaned word box (x0, y0, x1, y1)
GHOST_STONE = ((106, 60), 14)                          # a coral stone the line crosses (centre, radius px)
GHOST_VEIN_ROW_PX = 190                                # a thin copper vein crossing the line


def _ghost_sketch():
    """A planted sketch: an indigo ground with the sketch's kind of grain (fine, spatially correlated) and a soft
    mottle, a coral stone the dash line crosses and a thin copper vein crossing the line; and its dash band (the
    dash's filled pixels), its cleaned box and the line."""
    rng = np.random.default_rng(12)
    h, w = GHOST_SKETCH_PX
    f = np.empty((h, w, 3), np.float64)
    f[:] = GROUND
    f += cv2.GaussianBlur(rng.normal(0, 1.6, (h, w, 3)), (0, 0), 0.8)
    f += cv2.GaussianBlur(rng.normal(0, 6.0, (h, w)), (0, 0), 6.0)[..., None]
    yy, xx = np.mgrid[:h, :w]
    (sx, sy), r = GHOST_STONE
    stone = (xx - sx) ** 2 + (yy - sy) ** 2 <= r * r
    f[stone] = CORAL
    vein = (np.abs(yy - GHOST_VEIN_ROW_PX - 0.25 * (xx - GHOST_LINE_COL_PX)) <= 0.6) & (np.abs(xx - GHOST_LINE_COL_PX) < 40)
    f[vein] = (190, 137, 111)
    sketch = np.clip(np.round(f), 0, 255).astype(np.uint8)
    filled = np.zeros((h, w), dtype=bool)
    filled[GHOST_LINE_ROWS_PX[0]:GHOST_LINE_ROWS_PX[1], GHOST_LINE_COL_PX - 2:GHOST_LINE_COL_PX + 3] = True
    g = int(round(zlm.BOX_GROW_MM * K_PX_PER_MM))
    x0, y0, x1, y1 = GHOST_BOX_PX
    cleaned = np.zeros((h, w), dtype=bool)
    cleaned[y0 - g:y1 + g, x0 - g:x1 + g] = True
    line = {'side': 'left', 'orient': 'v', 'found_pos_px': GHOST_LINE_COL_PX, 'from_px': GHOST_LINE_ROWS_PX[0],
            'to_px': GHOST_LINE_ROWS_PX[1]}
    return sketch, stone, vein, filled, cleaned, line


def _ghost_plant(up, big, ground_up):
    """The ghost as the eye saw it, laid on the plate: the cleaned box a flat panel 2 levels darker (its grain smoothed
    away) and, along the line on ground pixels, the fill's dotted trace (a dark rim, then a light core, every 12 rows)."""
    out = up.astype(np.float64)
    smooth = cv2.GaussianBlur(out, (0, 0), 3.0)
    out[big] = smooth[big] - 2.0
    p = zbm.UP * GHOST_LINE_COL_PX + 1
    for y in range(zbm.UP * GHOST_LINE_ROWS_PX[0], zbm.UP * GHOST_LINE_ROWS_PX[1]):
        cols = np.arange(p - 2, p + 3)
        cols = cols[ground_up[y, cols]]
        out[y, cols] += -4.0 if (y // 12) % 2 == 0 else 3.0
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def _ghost_case():
    sketch, stone, vein, filled, cleaned, line = _ghost_sketch()
    ground = zlm.ground_lab(sketch)
    up = lm.upscale(sketch)
    big = cv2.resize(cleaned.astype(np.uint8), (up.shape[1], up.shape[0]), interpolation=cv2.INTER_NEAREST)
    big = cv2.dilate(big, zlm.disc(2 * zlm.CLEAN_GROW_PX + 1)).astype(bool)
    keep = np.zeros(cleaned.shape, dtype=bool)
    gm, _ = zbm.ground_mask(sketch, ground, cleaned, keep, filled, K_PX_PER_MM)
    ground_up = cv2.resize(gm.astype(np.uint8), (up.shape[1], up.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
    planted = _ghost_plant(up, big, ground_up)
    rebuilt, ground_up2, edges, rec = zbm.repair_ghost(sketch, planted, big, cleaned, keep, filled, [line], ground,
                                                       K_PX_PER_MM, [('box', GHOST_BOX_PX)], 0)
    assert (ground_up2 == ground_up).all()
    return {'sketch': sketch, 'stone': stone, 'vein': vein, 'up': up, 'big': big, 'ground_up': ground_up,
            'planted': planted, 'rebuilt': rebuilt, 'edges': edges, 'rec': rec, 'k_up': K_PX_PER_MM * zbm.UP}


def test_the_ground_mask_keeps_a_stone_and_a_vein_and_takes_the_dashs_own_rim_and_specks():
    sketch, stone, vein, filled, cleaned, line = _ghost_sketch()
    ground = zlm.ground_lab(sketch)
    keep = np.zeros(cleaned.shape, dtype=bool)
    gm, rec = zbm.ground_mask(sketch, ground, cleaned, keep, filled, K_PX_PER_MM)
    assert not gm[stone].any() and not gm[vein].any()                          # never a stone, never a vein
    near = cv2.dilate(vein.astype(np.uint8), zlm.disc(2 * zbm.GROUND_CLEAR_PX + 1)).astype(bool)
    assert not gm[near].any()                                                  # the vein kept 2 px clear
    assert gm[cleaned].all()                                                   # the cleaned box is ground whole
    # the dash's own residue in its filled pixels: a dark rim pixel and an isolated light speck are ground …
    marked = sketch.copy()
    marked[100, GHOST_LINE_COL_PX] = (2, 8, 30)                                # dark: the fill's rim left
    marked[140, GHOST_LINE_COL_PX + 1] = (40, 60, 110)                         # light: an isolated speck
    gm2, rec2 = zbm.ground_mask(marked, ground, cleaned, keep, filled, K_PX_PER_MM)
    assert gm2[100, GHOST_LINE_COL_PX] and gm2[140, GHOST_LINE_COL_PX + 1]
    assert rec2['dash_rim_px_taken_as_ground'] >= 1 and rec2['dash_specks_taken_as_ground'] >= 1
    # … control: the same marks off the dash's pixels are not ground (a dark mark, a light speck of the painting)
    marked2 = sketch.copy()
    marked2[100, 300] = (2, 8, 30)
    marked2[180, 301] = (40, 60, 110)
    gm3, _ = zbm.ground_mask(marked2, ground, cleaned, keep, filled, K_PX_PER_MM)
    assert not gm3[100, 300] and not gm3[180, 301]


def test_the_local_plane_follows_a_gradient_beside_a_band_where_a_mean_drifts():
    h, w = 120, 160
    ramp = np.repeat(np.linspace(20.0, 60.0, w)[None, :, None], h, axis=0).repeat(3, axis=2)
    weight = np.ones((h, w), dtype=bool)
    weight[:, 60:100] = False                                                  # a cleaned band: one-sided beside it
    sigma_px = 8.0
    plane, _ = zbm.local_plane(ramp, weight, sigma_px)
    assert np.abs(plane[20:100, 100:104] - ramp[20:100, 100:104]).max() < 0.05
    # control: the plain normalised mean beside the band drifts by the gradient times about σ
    wf = weight.astype(np.float64)
    mean = cv2.GaussianBlur(ramp[..., 0] * wf, (0, 0), sigma_px) / cv2.GaussianBlur(wf, (0, 0), sigma_px)
    assert np.abs(mean[20:100, 100] - ramp[20:100, 100, 0]).min() > 1.0


def test_a_planted_ghost_fails_the_proof_and_the_rebuild_clears_it_on_ground_pixels_only():
    c = _ghost_case()
    proof = zbm.ghost_proof(c['rebuilt'], c['planted'], c['up'], c['ground_up'], c['edges'], c['big'], c['k_up'], 0)
    names = [r['edge'] for r in proof['edges']]
    assert names[:5] == ['dash left', 'box left', 'box right', 'box top', 'box bottom']
    assert proof['holds'] and not proof['edges_failing_after'] and not proof['edges_not_read']
    # the control: the plate with the ghost fails on the line and on every side of the box
    assert {'dash left', 'box left', 'box right', 'box top', 'box bottom'} <= set(proof['edges_failing_on_the_control'])
    # the rule in the passing direction: the clean upscale (no ghost) holds, and its parallel copies hold
    clean = zbm.ghost_proof(c['up'], c['up'], c['up'], c['ground_up'], c['edges'], c['big'], c['k_up'], 0)
    assert clean['holds'] and clean['parallel_control']['share_holding'] >= 0.9
    # ground pixels only: the stone and the vein (and every pixel off the ground) bit for bit as they were
    changed = (c['rebuilt'] != c['planted']).any(axis=-1)
    assert changed.any() and not (changed & ~c['ground_up']).any() and c['rec']['pixels_changed_off_the_ground'] == 0
    for part in (c['stone'], c['vein']):
        big_part = cv2.resize(part.astype(np.uint8), (c['up'].shape[1], c['up'].shape[0]),
                              interpolation=cv2.INTER_NEAREST).astype(bool)
        assert (c['rebuilt'][big_part] == c['planted'][big_part]).all()
    # the grain kept: the rebuilt box's fine texture as strong as the ground's around it (not a smoothed panel)
    light = lm.srgb_to_lab(c['rebuilt'])[..., 0]
    fine = light - cv2.GaussianBlur(light, (0, 0), 2.0)
    inner = cv2.erode(c['big'].astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
    ring = cv2.dilate(c['big'].astype(np.uint8), np.ones((61, 61), np.uint8)).astype(bool) & ~cv2.dilate(
        c['big'].astype(np.uint8), np.ones((31, 31), np.uint8)).astype(bool) & c['ground_up']
    assert 0.7 < fine[inner].std() / fine[ring].std() < 1.3
    planted_fine = lm.srgb_to_lab(c['planted'])[..., 0]
    planted_fine = planted_fine - cv2.GaussianBlur(planted_fine, (0, 0), 2.0)
    assert planted_fine[inner].std() / fine[ring].std() < 0.5                    # control: the panel was smoothed
    # deterministic: the same inputs, the same bytes
    again = _ghost_case()
    assert (again['rebuilt'] == c['rebuilt']).all()


# --- the day's record -------------------------------------------------------------------------------------------------

def _read(rec, side):
    """A wrap as the master read it: the trimmed sketch, its dashes found and cleaned (with their ridge pixels and
    sites), the words its stones are read clear of, the final plate."""
    folder = zm.REPO / rec['pick']['folder']
    crop = zbm.crop_record(folder)
    raw, sha, _ = zlm.load_wrap(folder, side)
    assert sha == rec[side]['sketch']['sha256']
    wrap = zbm.BODY_MM if side == 'body' else zbm.CAP_MM
    rgb0, trim = zbm.trim_rows(raw, wrap)
    k = trim['px_per_mm']
    lines = zbm.find_dashes(rgb0, zbm.expected_dash_box(crop, side, trim))
    assert lines == rec[side]['dashes']['found']
    rgb, ridge_px, filled, sites, cleaning = zbm.clean_dashes(rgb0, lines)
    assert cleaning == rec[side]['dashes']['cleaning']
    m = zlm.masks(rgb, zlm.ground_lab(rgb))
    words = zbm.body_words(rgb, m, k)['words'] if side == 'body' else zlm.cap_logo_box(rgb, m, k)['mask']
    plate = np.asarray(Image.open(MASTER / 'engine' / ('%s-plate.png' % side)).convert('RGB'))
    return {'rgb0': rgb0, 'rgb': rgb, 'ridge': ridge_px, 'filled': filled, 'sites': sites, 'lines': lines, 'k': k,
            'words': words, 'plate': plate, 'wrap': wrap, 'seam_px': int(round(zlm.SEAM_BAND_MM * k * zlm.UP))}


@built
def test_the_hero_stands_inside_the_front_third_on_the_masters_vectors():
    rec = _rec()
    b = rec['body']
    r = _read(rec, 'body')
    m = zlm.masks(r['rgb'], zlm.ground_lab(r['rgb']))
    hero = zlm.hero_master(r['rgb'], m, r['k'])
    lo, hi = zlm.front_third(58.5, 18.0)['span_mm']
    x0, y0, x1, y1 = hero['letters'].bounds
    assert [round(v, 3) for v in (x0, y0, x1, y1)] == b['hero_in_the_front_third']['hero_vectors_mm']
    assert lo <= x0 and x1 <= hi and b['hero_in_the_front_third']['inside']
    assert rec['pick']['front_third_passes_as_sketched'] and not rec['pick']['hero_scaled']
    # every letter part and dot traced (بلسم: the word and the ب's dot); the trace within 0.3 mm at IoU ≥ 0.95
    assert len(b['hero']['letter_parts']) == b['hero']['trace']['parts'] >= 2
    assert b['hero']['trace']['holds'] == {'within_0_3_mm': True, 'iou_0_95': True}
    # control: the same vectors 0.1 mm past the span's left edge break the rule
    assert not (lo <= lo - 0.1 and x1 - (x0 - lo + 0.1) <= hi)


@built
def test_the_logotype_is_the_lids_own_and_its_floor_is_read_and_listed():
    rec = _rec()
    lt = rec['body']['logotype']
    assert lt['inverse_iou_with_the_source'] == 1.0
    _, src = zlm.logotype_source()
    assert lt['source']['pick_sha256'] == src['pick_sha256'] and lt['source']['rings'] == src['rings']
    lid = json.loads((zbm.LID12 / 'master.json').read_text(encoding='utf-8'))
    floor = lt['floor']
    cap = lid['name']['measures']['cap_height_mm'] * lt['scale']
    assert floor['cap_at_the_sketch_scale_mm'] == pytest.approx(cap, abs=1e-3)
    assert floor['scale_to_the_floor'] == pytest.approx(2.5 / cap, abs=1e-4)
    # the box at the floor is the sketch's box scaled about its own centre
    bx0, by0, bx1, by1 = floor['box_at_the_sketch_scale_mm']
    cx, s = (bx0 + bx1) / 2, floor['scale_to_the_floor']
    assert floor['box_at_the_floor_mm'][0] == pytest.approx(cx - s * (cx - bx0), abs=2e-3)
    assert floor['box_at_the_floor_mm'][2] == pytest.approx(cx + s * (bx1 - cx), abs=2e-3)
    span = zlm.front_third(58.5, 18.0)['span_mm']
    assert floor['inside_the_front_third'] == (span[0] <= floor['box_at_the_floor_mm'][0]
                                               and floor['box_at_the_floor_mm'][2] <= span[1])
    if floor['raised']:
        assert lt['cap_height_mm'] == pytest.approx(2.5, abs=1e-3) and lt['over_the_floor']
    else:
        assert lt['cap_height_mm'] == pytest.approx(cap, abs=1e-3) and not lt['over_the_floor']
        assert any(s_.startswith('"Enchanted Rose" keeps the sketch\'s scale') and '%.3f' % floor['box_at_the_floor_mm'][2]
                   in s_ for s_ in rec['listed'])


@built
def test_the_labels_rows_stand_inside_the_safe_ring_over_5_pt_with_the_lids_sign_at_3_mm():
    label = _rec()['label']
    assert label['diameter_mm'] == 16.0
    r_safe = 16.0 / 2 - 1.0
    c = (16.0 + 2.0) / 2
    texts = [r['text'] for r in label['rows']]
    assert texts == ['Rosewater', '4.5 g', '0.15 oz', 'BATCH']
    for r in label['rows']:
        x0, y0, x1, y1 = r['box_mm']
        worst = max(abs(y0 - c), abs(y1 - c))
        assert (x1 - x0) <= 2 * np.sqrt(r_safe ** 2 - worst ** 2) + 1e-6, r
        assert np.hypot(max(abs(x0 - c), abs(x1 - c)), worst) <= r_safe + 1e-6, r       # every corner inside the ring
        assert r['size_pt'] >= 5.0 and r['inside_safe'] and r['above_floor']
    assert [r['cap_mm'] for r in label['rows'] if r['row'] in ('net-1', 'net-2')] == [2.0, 2.0]
    sign = label['sign']
    assert sign['the_lids_sign'] and sign['exactly_3_mm'] and sign['on_the_baseline']
    assert sign['ink_height_mm'] == pytest.approx(3.0, abs=1e-3) and sign['word_space_mm'] > 0.5
    assert all(label['holds'].values())


@built
@pytest.mark.parametrize('side', ['body', 'cap'])
def test_the_dashes_proof_has_power_on_every_line_and_the_record_says_what_it_proves(side):
    rec = _rec()
    r = _read(rec, side)
    again = zbm.dash_proof(r['rgb0'], r['plate'], r['lines'], r['sites'], r['wrap'][0])
    assert again['lines'] == rec[side]['dashes']['lines'] and again['gone'] == rec[side]['dashes']['gone']
    for row in again['lines']:
        assert row['uncleaned_fails'] and row['competent']                     # the proof can see this line's dashes
        assert row['gone'] == (row['after_max_L'] <= zbm.DASH_GONE_L)
        if not row['gone']:
            assert any('the %s\'s %s dashed line is not proved gone' % (side, row['side']) in s_ for s_ in rec['listed'])
    # control, on each line: the uncleaned upscale's band laid back on the plate is not gone
    up0 = lm.upscale(r['rgb0'])
    for i, ln in enumerate(r['lines']):
        planted = r['plate'].copy()
        p, lo, hi = 2 * ln['found_pos_px'], 2 * ln['from_px'], 2 * ln['to_px']
        if ln['orient'] == 'v':
            planted[lo:hi, p - 4:p + 6] = up0[lo:hi, p - 4:p + 6]
        else:
            planted[p - 4:p + 6, lo:hi] = up0[p - 4:p + 6, lo:hi]
        back = zbm.dash_proof(r['rgb0'], planted, r['lines'], r['sites'], r['wrap'][0])['lines'][i]
        assert not back['gone'] and back['after_max_L'] > zbm.DASH_GONE_L, (side, ln['side'])


@built
@pytest.mark.parametrize('side', ['body', 'cap'])
def test_the_stones_are_untouched_over_the_whole_plate_and_a_planted_bite_fails(side):
    rec = _rec()
    r = _read(rec, side)
    again = zbm.stones_proof(r['rgb0'], r['rgb'], r['ridge'], r['words'], r['plate'], r['k'], r['seam_px'], r['wrap'][0])
    assert again == rec[side]['stones'] and again['holds'] and again['max'] <= 2.0
    # control: an indigo bite (the ground's colour) 3 × 3 sketch px inside a stone beside a dash line fails
    m0 = zlm.masks(r['rgb0'], zlm.ground_lab(r['rgb0']))
    stones = zlm.stones_clear_of_words(m0, r['words'], r['k']) & ~r['ridge']
    import cv2
    inner = cv2.erode(stones.astype(np.uint8), zlm.disc(9)).astype(bool)
    near = np.zeros_like(inner)
    for ln in r['lines']:
        p, lo, hi = ln['found_pos_px'], ln['from_px'], ln['to_px']
        if ln['orient'] == 'v':
            near[lo:hi, p - 8:p + 9] = True
        else:
            near[p - 8:p + 9, lo:hi] = True
    ys, xs = np.nonzero(inner & near)
    assert len(ys), 'no stone beside a dash line to bite'
    y, x = int(ys[0]), int(xs[0])
    bitten = r['plate'].copy()
    bitten[2 * y - 3:2 * y + 3, 2 * x - 3:2 * x + 3] = (8, 24, 66)
    bad = zbm.stones_proof(r['rgb0'], r['rgb'], r['ridge'], r['words'], bitten, r['k'], r['seam_px'], r['wrap'][0])
    assert not bad['holds'] and bad['max'] > 15


@built
def test_the_seams_hold_on_the_plates():
    rec = _rec()
    for side in ('body', 'cap'):
        assert rec[side]['seam']['holds'] and rec[side]['seam']['after']['mean'] <= 2.0
        plate = np.asarray(Image.open(MASTER / 'engine' / ('%s-plate.png' % side)).convert('RGB'))
        k_up = plate.shape[1] / 58.5
        assert float(zbm.join_profile(plate, k_up, zbm.OVERLAP_MM).mean()) == pytest.approx(
            rec[side]['seam']['after']['mean'], abs=2e-3)


@built
def test_the_drawing_is_recorded_and_labelled():
    drawing = json.loads((MASTER / 'balm-drawing.json').read_text(encoding='utf-8'))
    assert drawing['label'] == 'drawing, not a render' and drawing['sha256'] == pdw.sha256(MASTER / 'balm-drawing.png')
    assert drawing['case_d_mm'] == 18.0 and [b_['visible_mm'] for b_ in drawing['bands']] == [40.0, 30.0]
    assert drawing['overlap_mm'] == pytest.approx(zbm.OVERLAP_MM, abs=1e-4)


@built
def test_the_record_is_computed_and_lists_what_it_does_not_resolve():
    rec = _rec()
    assert rec['schema'] == 'day12_balm_master/1' and rec['cost_usd'] == 0.0
    assert rec['pick']['sketch'] == zb.the_pick()[0]
    assert rec['body']['files']['foil_limits']['holds'] is True
    cap_foil = rec['cap']['files']['foil_limits']
    assert cap_foil['holds'] is None and cap_foil['said'].startswith('not measured')    # the cap draws no foil
    assert rec['allowed_differences'] and isinstance(rec['listed'], list)
    if not rec['body']['lip_balm']['cap_over_the_floor']:
        assert any('LIP BALM' in s for s in rec['listed'])
    # the dash sentence carries the proofs' own results, never a typed "proved gone"
    lines = [r for side in ('body', 'cap') for r in rec[side]['dashes']['lines']]
    gone = sum(r['gone'] for r in lines)
    dash_line = [s for s in rec['allowed_differences'] if s.startswith('the sheet\'s dashed front-third box')]
    assert len(dash_line) == 1 and ('gone on %d of %d lines' % (gone, len(lines))) in dash_line[0]
    assert 'proved gone' not in ' '.join(rec['allowed_differences'])
    for side in ('body', 'cap'):
        assert rec[side]['stones']['holds'] or any('stones are not untouched' in s for s in rec['listed'])
        assert rec[side]['plate_ppi'] > 600 and rec[side]['files']['flat_ppi'] == pytest.approx(300.0, abs=1.0)
    sheet = json.loads((MASTER / 'finish-sheet.json').read_text(encoding='utf-8'))
    assert 'بلسم' in json.dumps(sheet, ensure_ascii=False) and 'balsam' not in json.dumps(sheet, ensure_ascii=False)


def _ghost_read(rec, side):
    """A wrap's repair as the master made it: what ``_read`` gives, with its cleaned boxes (and, on the body, the hero's
    carried raster kept), the cleaned mask on the plate's grid, the ground there, the edges and the control plate."""
    r = _read(rec, side)
    rgb, k = r['rgb'], r['k']
    ground = zlm.ground_lab(rgb)
    m = zlm.masks(rgb, ground)
    shape = rgb.shape[:2]
    if side == 'body':
        bw = zbm.body_words(rgb, m, k)
        hero = zlm.hero_master(rgb, m, k)
        hero_px = lm.raster_fill(hero['letters'], shape, (0.0, 0.0), k)
        keep = cv2.dilate(hero_px.astype(np.uint8), zlm.disc(zlm.odd_px(2 * zlm.HERO_CARRY_MM, k))).astype(bool)
        boxes = [('logotype box', bw['name']['box_px']), ('LIP BALM box', bw['line_box'])]
        cleaned = (zbm.word_box_mask(shape, boxes[0][1], k, m, bw['words'])
                   | zbm.word_box_mask(shape, boxes[1][1], k, m, bw['words'])) & ~keep
    else:
        logo = zlm.cap_logo_box(rgb, m, k)
        keep = np.zeros(shape, dtype=bool)
        boxes = [('logo box', logo['box_px'])]
        cleaned = zbm.word_box_mask(shape, logo['box_px'], k, m, logo['mask'])
    plate = r['plate']
    big = cv2.resize(cleaned.astype(np.uint8), (plate.shape[1], plate.shape[0]), interpolation=cv2.INTER_NEAREST)
    big = cv2.dilate(big, zlm.disc(2 * zlm.CLEAN_GROW_PX + 1)).astype(bool)
    gm, ground_rec = zbm.ground_mask(rgb, ground, cleaned, keep, r['filled'], k)
    ground_up = cv2.resize(gm.astype(np.uint8), (plate.shape[1], plate.shape[0]),
                           interpolation=cv2.INTER_NEAREST).astype(bool)
    control_png = MASTER / 'engine' / ('%s-plate-control.png' % side)
    control = np.asarray(Image.open(control_png).convert('RGB'))
    return dict(r, ground_up=ground_up, ground_rec=ground_rec, big=big, control=control, control_png=control_png,
                edges=zbm.ghost_edges(r['lines'], boxes, k, big), k_up=k * zlm.UP)


EYE_SAW = {'body': ('dash left', 'logotype box top'), 'cap': ('dash left', 'logo box top')}   # eye-r0: "down the left
#                                                     side and across below the hero"; the cap's box and line alike


@built
@pytest.mark.parametrize('side', ['body', 'cap'])
def test_the_ghost_proof_holds_on_the_plate_fails_on_its_control_and_on_a_step_laid_back(side):
    rec = _rec()
    g = _ghost_read(rec, side)
    ghost = rec[side]['ghost']
    assert ghost['ground'] == g['ground_rec']
    assert lm.sha256(g['control_png']) == ghost['control_sha256']
    up0 = lm.upscale(g['rgb0'])
    again = zbm.ghost_proof(g['plate'], g['control'], up0, g['ground_up'], g['edges'], g['big'], g['k_up'],
                            g['seam_px'])
    assert again == ghost['proof']                                    # the record is the proof's own output
    assert again['holds'] and not again['edges_failing_after'] and again['edges_read'] >= 8
    assert again['edges_not_read'] == ['dash top']                    # the top line runs through the stones
    assert any('reads no ground bin along dash top' in s_ for s_ in rec['listed'] if s_.startswith('the %s' % side))
    # the control: the plate before the rebuild (the plate the eye saw) fails where the eye saw the ghost
    for name in EYE_SAW[side]:
        assert name in again['edges_failing_on_the_control'], name
    # ground pixels only: nothing off the ground differs from the control
    changed = (g['plate'] != g['control']).any(axis=-1)
    assert changed.any() and not (changed & ~g['ground_up']).any() and ghost['pixels_changed_off_the_ground'] == 0
    # control, laid back: a straight-edged panel 2 sRGB levels darker on the cleaned box's ground fails its sides
    panel = g['plate'].astype(np.int16)
    panel[g['big'] & g['ground_up']] -= 2
    panel = np.clip(panel, 0, 255).astype(np.uint8)
    back = zbm.ghost_proof(panel, g['control'], up0, g['ground_up'], g['edges'], g['big'], g['k_up'], g['seam_px'])
    box_top = EYE_SAW[side][1]
    assert not back['holds'] and box_top in back['edges_failing_after']


@pytest.mark.skipif(not (MASTER / 'eye-r1.json').exists(), reason='the balm\'s gate has not run here')
def test_the_balms_gate_holds_at_round_1_after_its_one_repair(tmp_path, monkeypatch):
    """D-D12-3 / D-D12-8: round 0 failed, one repair, round 1 holds — read from the eye's own records; the gate in
    balm.json is the records' (the control: gate_record on a copy whose round 1 failed reads as not holding)."""
    rec = json.loads((MASTER / 'balm.json').read_text(encoding='utf-8'))
    gate = rec['gate']
    assert [r['round'] for r in gate['rounds']] == ['r0', 'r1'] and gate['repairs'] == 1
    assert not gate['rounds'][0]['holds'] and gate['rounds'][1]['holds'] and gate['holds']
    for r in gate['rounds']:
        eye = json.loads((zbm.REPO / r['record']).read_text(encoding='utf-8'))
        assert eye['holds'] == r['holds'] and eye['defects'] == r['defects']
    monkeypatch.setattr(zbm.lm, 'rel', str)
    for name in ('balm.json', 'eye-r0.json', 'eye-r1.json'):
        (tmp_path / name).write_bytes((MASTER / name).read_bytes())
    failed = json.loads((tmp_path / 'eye-r1.json').read_text(encoding='utf-8'))
    failed.update(holds=False, defects=[{'where': 'planted', 'what': 'planted', 'severity': 'major', 'repair': '-'}])
    (tmp_path / 'eye-r1.json').write_text(json.dumps(failed), encoding='utf-8')
    assert not zbm.gate_record(tmp_path)['gate']['holds']
