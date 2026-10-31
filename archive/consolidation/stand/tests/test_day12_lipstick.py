"""Day 12 §1 — the lipstick closed (D-D12-1): the hero pair × 0.63 within the front third of the Ø 20 case, the
logotype × 0.80 over the 2.5 mm floor, the stack in the sketch's own gaps, the stones' pixels untouched; the label's ℮
the lid's own sign at exactly 3 mm on the figures' baseline; the product drawing deterministic and labelled
(D-D12-1.4); the gate's and the jury's records. Each check runs on the day's real records or a planted case, with a
control that fails. Nothing here pays."""
import json

import cv2
import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import product_drawing as pdw
from apps.pipeline.services import zilal_lipstick_master as zlm
from apps.pipeline.services import zilal_master as zm

CLOSED = zm.REPO / 'docs' / 'audit' / 'day-12' / 'lipstick' / 'closed'
closed_here = pytest.mark.skipif(not (CLOSED / 'lipstick.json').exists(), reason='the closed lipstick is not built here')


def _rec():
    return json.loads((CLOSED / 'lipstick.json').read_text(encoding='utf-8'))


def test_the_front_third_of_a_20_mm_case_is_opposite_its_seam():
    third = zlm.front_third(64.8, 20.0)
    assert third['width_mm'] == pytest.approx(20.944, abs=1e-3)
    assert third['centre_mm'] == pytest.approx((64.8 - np.pi * 20) + np.pi * 10, abs=1e-3)
    assert third['span_mm'][0] == pytest.approx(22.912, abs=1e-3) and third['span_mm'][1] == pytest.approx(43.856, abs=1e-3)


@closed_here
def test_the_closed_body_holds_the_hero_in_the_front_third_and_its_floors():
    b = _rec()['body']
    lo, hi = b['front_third']['span_mm']
    x0, _, x1, _ = b['closed']['pair_box_mm']
    assert lo <= x0 and x1 <= hi and b['closed']['pair_inside_the_front_third']
    assert b['closed']['hero_scale'] == zlm.HERO_SCALE == 0.63 and b['closed']['logotype_times'] == 0.80
    assert b['logotype']['cap_height_mm'] >= zlm.CAP_FLOOR_SMALL_WRAP_MM and b['logotype']['over_the_floor']
    assert b['logotype']['scale'] == pytest.approx(b['logotype']['sketch_scale'] * 0.80, abs=1e-6)
    assert b['logotype']['inverse_iou_with_the_source'] == 1.0
    # "LIPSTICK" keeps its sketched size, under the floor: listed, not resolved
    assert b['lipstick']['cap_mm'] < zlm.CAP_FLOOR_SMALL_WRAP_MM
    assert b['closed']['lipstick_cap_under_the_floor']['cap_mm'] == b['lipstick']['cap_mm']
    # the stack in the sketch's own gaps: the logotype's top one gap under the pair, LIPSTICK one gap under the logotype
    g1, g2 = b['closed']['sketch_gaps_mm']
    assert b['logotype']['placed_ink_mm'][1] - b['closed']['pair_box_mm'][3] == pytest.approx(g1, abs=0.02)
    assert b['lipstick']['ink_mm'][1] - b['logotype']['placed_ink_mm'][3] == pytest.approx(g2, abs=0.05)
    assert b['hero']['closed']['hatch']['fit']['pitch_mm'] == zlm.PRESS_PITCH_MM == 0.37
    assert b['files']['foil_limits']['holds']


@closed_here
def test_the_stones_pixels_are_the_sketchs_own_after_the_closing():
    """Every stone pixel (read 1.5 mm clear of the words) of the upscaled sketch is in the closed body's plate unchanged,
    the seam's feathered band apart (Day 11's own seam treatment) — a planted stroke over one stone fails."""
    rec = _rec()['body']
    raw, sha, _ = zlm.load_wrap(zm.REPO / rec['sketch']['path'].rsplit('/', 1)[0], 'body')
    assert sha == rec['sketch']['sha256']
    rgb, _ = zlm.trim_rows(raw)
    k = rgb.shape[1] / zlm.WRAP_MM[0]
    m = zlm.masks(rgb, zlm.ground_lab(rgb))
    found = zlm.find_hero(rgb, m, k)
    solid = zlm.find_solid(m, {'mask': found['mask'], 'window_px': found['window_px']}, k)
    words = found['mask'] | solid['name']['mask'] | solid['ahmar']['mask']
    lines = zlm.find_lines(rgb, m, k, solid['name']['box_px'][3], words)
    for key in ('lipstick', 'net'):
        words |= zlm.box_mask(m['cream'].shape, lines[key], k, m, rgb)
    stones = zlm.stones_clear_of_words(m, words, k)
    up = lm.upscale(rgb)
    big = cv2.resize(stones.astype(np.uint8), (up.shape[1], up.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
    big = cv2.erode(big.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)      # their own edges' resampling apart
    seam = int(np.ceil((zlm.SEAM_BAND_MM + 0.5) * k * zlm.UP))
    big[:, :seam] = False
    big[:, -seam:] = False
    plate = np.asarray(Image.open(CLOSED / 'engine' / 'body-plate.png').convert('RGB'))
    assert big.sum() > 10000
    assert (plate[big] == up[big]).all()
    planted = plate.copy()
    ys, xs = np.nonzero(big)
    planted[ys[0], xs[0]] = 255 - planted[ys[0], xs[0]]
    assert not (planted[big] == up[big]).all()


@closed_here
def test_the_labels_sign_is_the_lids_own_at_exactly_3_mm_on_the_figures_baseline():
    sign = _rec()['label']['sign']
    assert sign['the_lids_sign'] and sign['exactly_3_mm'] and sign['on_the_baseline']
    assert sign['ink_height_mm'] == pytest.approx(3.0, abs=1e-3) and sign['figures_cap_mm'] == 2.0
    assert sign['word_space_mm'] > 0.5
    # the proof has power: a sign set in a 2.5 mm box reads 2.5, not 3
    segs, _ = lm.sign_segments((0.0, 0.0, 2.5 * zlm.sign_aspect(), 2.5))
    ink = zlm.sign_ink(segs)
    assert ink[3] - ink[1] == pytest.approx(2.5, abs=1e-3)


def _wrap(tmp_path, name, colour):
    im = np.zeros((497, 766, 3), np.uint8)
    im[:] = (8, 32, 69)
    im[150:350, 300:460] = colour
    path = tmp_path / name
    Image.fromarray(im).save(path)
    return path


def test_the_product_drawing_is_deterministic_and_says_it_is_a_drawing(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, 'rel', str)
    body = _wrap(tmp_path, 'body.png', (190, 137, 111))
    cap = _wrap(tmp_path, 'cap.png', (120, 90, 160))
    bands = [('body', body, (64.8, 42.0), 1.0, 40.0), ('cap', cap, (64.8, 42.0), 1.0, 40.0)]
    a = pdw.draw('a stick', bands, 20.0, 33.384, 64.8 - np.pi * 20, '#051C41', tmp_path / 'a.png')
    b = pdw.draw('a stick', bands, 20.0, 33.384, 64.8 - np.pi * 20, '#051C41', tmp_path / 'b.png')
    assert a['sha256'] == b['sha256'] and a['label'] == 'drawing, not a render' == pdw.LABEL
    assert (tmp_path / 'a.png').read_bytes() == (tmp_path / 'b.png').read_bytes()
    # a changed wrap changes the drawing (the drawing reads the wraps, not a picture of its own)
    other = _wrap(tmp_path, 'other.png', (30, 160, 120))
    c = pdw.draw('a stick', [('body', other, (64.8, 42.0), 1.0, 40.0), bands[1]], 20.0, 33.384, 64.8 - np.pi * 20,
                 '#051C41', tmp_path / 'c.png')
    assert c['sha256'] != a['sha256']
    # the front view shows the front centre: the planted patch (x 25.4–38.9 mm) sits mid-case
    view = pdw.view([pdw.band_texture(body, (64.8, 42.0), 1.0) + (40.0,)], 20.0, 33.384, 64.8 - np.pi * 20, 0.0, 0.0,
                    (5, 28, 65))
    mid = view[view.shape[0] // 2, view.shape[1] // 2, :3]
    assert tuple(int(v) for v in mid) == (190, 137, 111)


@closed_here
def test_the_closed_lipsticks_gate_holds_and_the_jury_is_recorded_beside_day_11s():
    rec = _rec()
    assert rec['gate']['holds'] and rec['gate']['rounds'][0]['round'] == 'r0'
    assert rec['jury']['day11']['stricter_mean'] == 6.1
    assert rec['jury']['stricter_mean'] == json.loads((CLOSED / 'jury' / 'verdict.json').read_text())['raw']['stricter_mean']
    drawing = json.loads((CLOSED / 'lipstick-drawing.json').read_text())
    assert drawing['label'] == 'drawing, not a render' and drawing['sha256'] == pdw.sha256(CLOSED / 'lipstick-drawing.png')


CARTON = zm.REPO / 'docs' / 'audit' / 'day-12' / 'lipstick' / 'carton'


def test_the_lipstick_carton_carries_the_net_content_on_its_back_and_its_hero_inside_the_fronts_safe_area():
    """D-D12-5 / D-D11-11's second destination, and the one repair of the eye's round 0 (D-D12-8). The Arabic claims:
    a number is bound to its word ("نباتي 100%"), so at a planted width where the old breaker parted them (its line held
    through نباتي and "100% ·" opened the next) the claim stays whole — and the built back says so. The carton built by
    stick_carton (fold check, die untouched, flaps clean, nothing past the floor) in Ẓilāl's colours from the Day 12
    box's record, the ℮ read from the file on the back at 3 mm; the front's WHOLE lockup inside the safe area and below
    the thumb notch's keep-out (one moved 5 mm up into the notch fails; one wider than the safe area fails), the lid's
    drift at lid scale (exactly 1.0) and clear of the lid's words (a region over "Enchanted" is refused), and the
    ground continuous across both folds as the written file draws it (a front ground 10 ΔE off fails)."""
    import re

    from apps.pipeline.services import palette_sticker as ps
    from apps.pipeline.services import stick_carton as sc
    from apps.pipeline.services import zilal_cartons as zc
    # -- the Arabic claims: a number with its word, at a planted narrow width (no build needed)
    fc = ps.faces()
    claims = 'غير مختبر على الحيوانات · نباتي 100% · مختبر من قبل أطباء الجلد · ثبات طويل الأمد'
    words = claims.split()
    old = []                                                      # the old breaker's tokens: "·" bound, nothing else
    for w in words[:words.index('نباتي') + 1]:
        if old and not re.search(r'\w', w):
            old[-1] += ' ' + w
        else:
            old.append(w)
    held_mm = sc.line_width([('claims', 'arabic', ' '.join(old))], 5.0, fc)
    width_mm = held_mm + 0.01
    # the control: at this width the old breaker held its line through نباتي, and "100% ·" did not fit after it
    assert sc.line_width([('claims', 'arabic', ' '.join(old + ['100% ·']))], 5.0, fc) > width_mm
    row = {'field': 'claims', 'head': None, 'text': claims, 'script': 'arabic'}
    assert ('claims', 'arabic', 'نباتي 100% ·') in sc.tokens(row)
    lines = [' '.join(t for _, _, t in segs) for segs in sc.wrap([row], width_mm, 5.0, fc)]
    assert lines[0] == ' '.join(old[:-1]) and lines[1].startswith('نباتي 100%')
    assert not any(sc.is_number(ln.split()[0]) for ln in lines)
    # a Latin line binds a number to the word AFTER it ("100 % vegano" stayed parted on the ES side at round 1): one
    # token with its closing "·"; the control, the old breaker, kept "100%" alone
    latin = sc.tokens({'field': 'claims', 'head': None, 'text': '· 100% vegan ·', 'script': 'latin'})
    assert ('claims', 'regular', '100% vegan ·') in latin and ('claims', 'regular', '100%') not in latin
    assert sc.splits_a_number('No testado en animales · 100 %', 'vegano · Probado', False)
    assert not sc.splits_a_number('No testado en animales ·', '100 % vegano · Probado', False)
    if not (CARTON / 'carton-fold-check.json').exists():
        pytest.skip('the lipstick carton is not built here')
    rec = json.loads((CARTON / 'carton-fold-check.json').read_text(encoding='utf-8'))
    front = json.loads((CARTON / 'carton-front.json').read_text(encoding='utf-8'))
    report = json.loads((CARTON / 'carton-fit-report.json').read_text(encoding='utf-8'))
    ar = [ln['text'] for ln in report['lines'] if ln['lang'] == 'ar']
    assert report['no_arabic_line_opens_on_a_number'] and any('نباتي 100%' in t for t in ar)
    # -- the carton: its die, flaps, floor and the ℮ read from the file on the back at 3 mm
    assert rec['fold_check']['passed'] and rec['die_untouched']['holds'] and rec['clean']['holds']
    assert rec['all_inside_safe'] and rec['notch_clear'] and report['copy']['all_found'] and not report['overflow']
    assert report['smallest_pt'] >= sc.BODY_FLOOR_PT
    signs = report['net']['read_from_the_file']
    assert signs and all(s['height_mm'] >= 3.0 - 1e-3 for s in signs)
    # -- Ẓilāl's colours, not the placeholder: the Day 12 box's record, by key; the barcode's white by rule
    box = json.loads((zm.REPO / 'docs' / 'audit' / 'day-12' / 'zilal' / 'box' / 'box.json').read_text(encoding='utf-8'))
    assert {k: rec['colours'][k] for k in ('ground', 'ink', 'logo')} == {'ground': box['ground'], 'ink': box['ink'],
                                                                         'logo': box['logo_ink']}
    assert all(rec['colours'][k] != sc.PLACEHOLDER_COLOURS[k] for k in ('ground', 'ink', 'logo'))
    assert rec['colours']['ean_ground'] == '#FFFFFF' and rec['colours_placeholder'] == []     # every key passed
    assert all(report['no_line_opens_on_a_number_word_split'].values())                     # EN, ES and AR
    assert front['colours']['source']['record'] == 'docs/audit/day-12/zilal/box/box.json'
    # -- the whole lockup: inside the safe area, below the notch; cut by its ink (no window edge carries alpha)
    lock, safe, notch = front['lockup'], front['front_safe_mm'], front['notch_keep_out']
    x0, y0, x1, y1 = lock['box_on_the_front_mm']
    assert zc.lockup_clearance([x0, y0, x1, y1], safe, notch)['holds'] and lock['check']['holds']
    assert set(lock['words_boxes_on_the_wrap_mm']) == {'hero', 'logotype', 'lipstick'}
    assert lock['window_edge_alpha'] == [0.0, 0.0] and front['nothing_crosses']
    assert 0.97 <= lock['fills_of_the_safe_width'] <= zc.SAFE_FILL
    assert lock['ink_width_on_the_wrap_mm'] >= lock['widest_box_mm']           # the logotype whole, never cropped
    moved = zc.lockup_clearance([x0, y0 - 5.0, x1, y1 - 5.0], safe, notch)
    assert not moved['holds'] and moved['clearance_mm']['notch'] < 0
    wide = zc.lockup_clearance([safe[0] - 0.5, y0, safe[2] + 0.5, y1], safe, notch)
    assert not wide['holds'] and wide['clearance_mm']['left'] < 0 and wide['clearance_mm']['right'] < 0
    assert front['readback']['lockup_inside_its_box']
    # -- the drift: the lid's own stones at lid scale, beneath LIPSTICK, clear of the lid's words
    drift = front['drift']
    assert drift['scale'] == 1.0 and drift['scale_xy'] == [1.0, 1.0]
    read = drift['scale_read_from_the_pixels']                                # and read back from the pixels
    assert read['stones_matched'] == len(drift['stones']) == read['pieces_on_the_front']
    assert abs(drift['scale_measured'] - 1.0) <= 0.005 and all(abs(r - 1.0) <= 0.03 for r in read['area_ratios'])
    assert all(abs(r - 1.0) <= 0.02 for r in drift['box_size_ratio_front_over_lid'])
    assert drift['check']['holds'] and drift['box_on_the_front_mm'][1] > y1 and drift['region_edge_alpha'] == 0.0
    assert len(drift['stones']) >= 3 and all(s['size_mm'] <= zc.STONE_MAX_MM for s in drift['stones'])
    master = json.loads(zc.LID_MASTER.read_text(encoding='utf-8'))
    words = zc.lid_word_boxes(master)
    assert min(zc.refuse_near_words(drift['region_on_the_lid_mm'], words, zc.LID_WORDS_CLEAR_MM).values()) >= 2.0
    with pytest.raises(ValueError, match='element name'):
        zc.refuse_near_words((14.0, 88.0, 30.0, 100.0), words, zc.LID_WORDS_CLEAR_MM)      # over "Enchanted"
    # -- the ground across both folds, read from the written file; a front ground 10 ΔE off fails
    folds = front['readback']['folds']
    assert set(folds) == {'left', 'right'}
    assert all(f['holds'] and f['binned_mean_de00'] <= 2.0 and f['pairs_mean_de00'] <= 2.0 for f in folds.values())
    ground = zc.hex_rgb(front['ground']['colour'])
    lab = lm.srgb_to_lab(ground[None, :])
    t = next(t for t in np.arange(0.5, 120.0, 0.5) if lm.delta_e00(lab, lm.srgb_to_lab((ground + t)[None, :]))[0] >= 10.0)
    k = zc.FOLD_PPI / lm.MM_PER_INCH
    planted = np.empty((int(30 * k), int(8 * k), 3))
    planted[:] = ground
    planted[:, planted.shape[1] // 2:] = ground + t
    off = zc.across_fold(planted, planted.shape[1] // 2, k, 'right')
    assert not off['holds'] and off['binned_mean_de00'] >= 9.5
    planted[:, planted.shape[1] // 2:] = ground
    assert zc.across_fold(planted, planted.shape[1] // 2, k, 'right')['holds']


def test_the_finish_sheet_sets_zilal_and_the_arabic_and_refuses_a_list_too_long(tmp_path):
    """[Day 12] Set in Helvetica, the shared finish sheet printed "Ẓilāl" as "·il·l" and every Arabic word in a plate's
    row as dots; laid out as HTML, the title and the row read back whole (the Arabic as its shaped forms), and a list
    longer than the page refuses rather than running off it."""
    import unicodedata

    import fitz

    from apps.pipeline.services import zilal_object as zo
    flat = tmp_path / 'flat.png'
    Image.fromarray(np.full((120, 190, 3), (8, 32, 69), np.uint8)).save(flat)
    zo.finish_sheet('the lipstick', flat, [{'plate': 'foil (rose gold)', 'what': 'شفاه: its rim and its hatch'}], tmp_path)
    with fitz.open(str(tmp_path / 'finish-sheet.pdf')) as doc:
        text = unicodedata.normalize('NFKC', doc[0].get_text())
    assert 'Ẓilāl — the lipstick' in text and 'شفاه' in text and '·' not in text
    rows = [{'plate': 'plate %d' % i, 'what': 'a row of words long enough to wrap twice in its column ' * 3} for i in range(40)]
    with pytest.raises(ValueError, match='do not fit'):
        zo.finish_sheet('the lipstick', flat, rows, tmp_path)
