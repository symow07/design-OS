"""Day 13 §1.1 (D-D13-8, the last repair) — the lipstick carton's front: its stone drift cut from the closed wrap's own
print plate (the same bank at the wrap's scale, one window of the wrap as if unrolled onto the front), the hero
untouched. The window and the coverage measure are written before the front (drift-plan.json); every number the front's
record carries is read back here from the written files — the lower front's stone share against the wrap's within the
plan's tolerance, the drift's scale from the written picture, the lockup's rows byte for byte against Day 12's, nothing
within 1.5 mm of a fold or the bottom score — and Day 12's lid-drift path still draws Day 12's front. Each check carries
a control that fails (a planted fault). Nothing here pays or touches the database."""
import json

import cv2
import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_cartons as zc
from apps.pipeline.services import zilal_lipstick_master as zlm

D12 = zc.DAY12 / 'lipstick' / 'carton'
CARTON = zc.DAY13 / 'lipstick' / 'carton'
WRAP_REC = zc.DAY12 / 'lipstick' / 'closed' / 'lipstick.json'
built = pytest.mark.skipif(not (CARTON / 'carton-front.json').exists(), reason='the Day 13 lipstick carton is not built here')
FOLD_CLEAR_MM = 1.5                  # the eye's round 1: "at least 1.5 mm clear of the folds and the bottom score"


def _wrap():
    body = json.loads(WRAP_REC.read_text(encoding='utf-8'))['body']
    return {'pdf': lm.REPO / body['files']['pdf'], 'boxes_mm': body['boxes_mm'], 'ground': body['ground'],
            'plate': (lm.REPO / body['files']['ai']).parent / 'body-plate.png'}


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _rgb(path):
    return np.asarray(Image.open(path).convert('RGB')).astype(np.float64)


def _panel_mm(front, shape):
    """Each picture pixel's centre in panel mm (x, y)."""
    k = zc.FRONT_PX_PER_MM
    ox, oy = front['panel_on_the_picture_mm']
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return (xx + 0.5) / k - ox, (yy + 0.5) / k - oy


def _stone_pieces(mask, k, origin_mm, min_mm2):
    """The centres (mm) and areas (mm²) of a mask's 8-connected pieces of at least ``min_mm2``."""
    n, _, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    return [(origin_mm[0] + (cen[i][0] + 0.5) / k, origin_mm[1] + (cen[i][1] + 0.5) / k, st[i, 4] / (k * k))
            for i in range(1, n) if st[i, 4] / (k * k) >= min_mm2]


# --- planted cases (no build) ------------------------------------------------------------------------------------------

def test_a_window_reads_round_the_wraps_seam_and_only_the_tooth_is_filled():
    """A window across the wrap's seam (x past 64.8 mm) reads the plate's last columns then its first, in that order;
    a hole of the paper's tooth (≤ 0.01 mm²) inside a stone is filled, a gap between stones (0.5 mm²) stays ground."""
    k = 1792 / zlm.WRAP_MM[0]
    _, cols, origin = zc.window_pixels((63.8, 1.0, 66.8, 2.0), k, 1792)
    assert cols[0] > 1700 and cols[-1] < 60 and list(cols).index(0) == 1792 - cols[0]
    assert np.all(np.diff(cols[cols >= cols[0]]) == 1) and origin[0] == pytest.approx(63.8, abs=1 / k)
    mask = np.zeros((200, 200), bool)
    mask[20:180, 20:180] = True
    mask[50:52, 50:52] = False                                  # 4 px: 0.005 mm², the tooth
    mask[100:120, 100:120] = False                              # 400 px: 0.52 mm², a gap
    filled, holes = zc.tooth_filled(mask, k)
    assert filled[50:52, 50:52].all() and not filled[100:120, 100:120].any()
    assert holes['tooth_holes_filled']['count'] == 1 and holes['gaps_kept_as_ground']['count'] == 1


def test_the_area_paste_keeps_the_arts_area_draws_nothing_past_its_window_and_keeps_a_vein_whole():
    """A diagonal vein one plate pixel wide, laid on the front at 1 mm = 1 mm through ``area_paste``: its alpha summed
    is its area on the plate (± 1 %), nothing is drawn outside the clip, and it stays ONE piece; the control — the same
    vein sampled pixel by pixel at the front's grid (nearest, no area) — breaks into dashes."""
    kp = 1792 / zlm.WRAP_MM[0]
    alpha = np.zeros((300, 300))
    for i in range(20, 280):
        alpha[i, int(20 + i * 0.83)] = 1.0
    pre = alpha[..., None] * np.array([190.0, 130.0, 100.0])
    k = zc.FRONT_PX_PER_MM
    canvas, cover = np.zeros((400, 400, 3)), np.zeros((400, 400))
    clip = tuple(round(v * k) / k for v in (1.0, 1.0, 12.0, 12.0))
    full, scale = zc.area_paste(canvas, cover, pre, alpha, (kp, kp), (0.0, 0.0), (1.2, 1.2), clip)
    assert scale == pytest.approx((1.0, 1.0), abs=1e-12)
    assert full.sum() / k ** 2 == pytest.approx(alpha.sum() / kp ** 2, rel=0.01)
    box = [int(round(v * k)) for v in clip]
    outside = np.ones(full.shape, bool)
    outside[box[1]:box[3], box[0]:box[2]] = False
    assert not full[outside].any()
    assert cv2.connectedComponents((full > 0.2).astype(np.uint8), connectivity=8)[0] - 1 == 1
    near = cv2.resize(alpha, (int(round(300 * k / kp)), int(round(300 * k / kp))), interpolation=cv2.INTER_NEAREST)
    assert cv2.connectedComponents((near > 0.2).astype(np.uint8), connectivity=8)[0] - 1 > 1


def test_a_build_of_the_wraps_drift_is_refused_without_its_plan(tmp_path):
    """The coverage measure is written before the front: without drift-plan.json the wrap's drift is refused, and a
    file of another schema is refused."""
    with pytest.raises(FileNotFoundError, match='before the front is built'):
        zc.read_plan(tmp_path / zc.PLAN_NAME)
    (tmp_path / zc.PLAN_NAME).write_text(json.dumps({'schema': 'something else'}), encoding='utf-8')
    with pytest.raises(ValueError, match=zc.PLAN_SCHEMA):
        zc.read_plan(tmp_path / zc.PLAN_NAME)
    with pytest.raises(ValueError, match='drift\'s source'):
        zc.build('lipstick', _wrap(), claims=[], out_root=tmp_path, drift_source='lid drift')


def test_day12s_lid_drift_path_still_draws_day12s_front(tmp_path, monkeypatch):
    """``drift_source='lid'`` (the default) draws Day 12's front pixel for pixel and records Day 12's lockup and drift
    exactly (the written record, read back); the control — the same picture with one drift pixel moved — differs."""
    if not (D12 / 'carton-front.json').exists():
        pytest.skip('the Day 12 lipstick carton is not built here')
    real = lm.rel                                                # the picture is written outside the repository
    monkeypatch.setattr(zc.lm, 'rel', lambda p: real(p) if str(p).startswith(str(lm.REPO)) else str(p))
    colours, _ = zc.carton_colours(zc.BOX_RECORD)
    out = tmp_path / 'front-picture.png'
    rec = zc.front_picture(zc.products()['lipstick'], _wrap(), zc.LID_PLATE, zc.LID_MASTER, colours, out)
    lm.write_json(tmp_path / 'front.json', rec)
    rec = _json(tmp_path / 'front.json')
    day12 = _json(D12 / 'carton-front.json')
    assert rec['schema'] == zc.SCHEMA == day12['schema'] and 'drift_source' not in rec
    for key in ('lockup', 'drift', 'ground', 'front_safe_mm', 'notch_keep_out', 'px', 'said', 'nothing_crosses'):
        assert rec[key] == day12[key], key
    mine, theirs = np.asarray(Image.open(out)), np.asarray(Image.open(D12 / 'front-picture.png'))
    assert np.array_equal(mine, theirs)
    moved = mine.copy()
    moved[800, 300] = moved[800, 300] + 1
    assert not np.array_equal(moved, theirs)


# --- the built carton --------------------------------------------------------------------------------------------------

@built
def test_the_plan_was_written_before_the_front_and_the_record_carries_its_measure():
    """drift-plan.json is older than the front picture, the record names its bytes, and the record's coverage is the
    plan's definition (measure, areas, tolerance and its reason) with the measured shares added."""
    plan = _json(CARTON / zc.PLAN_NAME)
    front = _json(CARTON / 'carton-front.json')
    assert plan['schema'] == zc.PLAN_SCHEMA and front['schema'] == zc.SCHEMA_WRAP and front['drift_source'] == 'wrap'
    assert (CARTON / zc.PLAN_NAME).stat().st_mtime_ns < (CARTON / 'front-picture.png').stat().st_mtime_ns
    assert front['drift']['plan']['sha256'] == lm.sha256(CARTON / zc.PLAN_NAME)
    assert front['drift']['plan']['written_before_the_picture']
    cov = front['drift']['coverage']
    for key, value in plan['coverage'].items():
        assert cov[key] == value, key
    for key in ('lower_front_share', 'wrap_body_share', 'window_share', 'tolerance', 'tolerance_said',
                'difference_from_the_wrap_body'):
        assert key in cov
    assert 'whole stones' in cov['tolerance_said'] and plan['window']['reason']
    assert "Day 12 lid's own stones" not in front['said'] and 'wrap\'s own stone bank' in front['said']


@built
def test_the_lower_fronts_stone_share_is_within_its_tolerance_of_the_wraps():
    """The §6 check: the carton front's stone coverage against the wrap's, a measured share. Each share read here from
    the files by the plan's rule (pixels over STONE_DE ΔE76 from their own ground): the wrap body (the plate inside its
    trim, the words' zone out), the window, and the lower front (the written picture); the front within the plan's
    tolerance of the wrap — one largest stone over the lower front's area, recomputed here. The control: the same front
    with its drift painted out (all ground) reads no stone and fails."""
    plan = _json(CARTON / zc.PLAN_NAME)
    front = _json(CARTON / 'carton-front.json')
    cov = front['drift']['coverage']
    plate = _rgb(lm.REPO / plan['plate'])
    kp = zc.plate_scale(plate.shape)
    ground = np.median(plate.reshape(-1, 3), axis=0)
    stones = zc.plate_distance(plate, ground) > zc.STONE_DE
    xs, ys = zc.centres_mm(plate.shape[1], kp, 0.0), zc.centres_mm(plate.shape[0], kp, 0.0)
    zone = np.zeros(stones.shape, bool)
    for z in plan['words_zone_on_the_wrap_mm'].values():
        zone |= zc.in_rect(xs, ys, z)
    body = zc.in_rect(xs, ys, (0.0, 1.0, zlm.WRAP_MM[0], 41.0)) & ~zone
    assert float(stones[body].mean()) == pytest.approx(cov['wrap_body_share'], abs=1e-4)
    rows, cols, _ = zc.window_pixels(plan['window']['on_the_wrap_mm'], kp, plate.shape[1])
    win = stones[rows][:, cols]
    assert float(win.mean()) == pytest.approx(cov['window_share'], abs=1e-4)
    big, _ = zc.largest_stone(win, kp)
    lower = cov['lower_front_mm']
    area = (lower[2] - lower[0]) * (lower[3] - lower[1])
    assert big / area == pytest.approx(cov['tolerance'], abs=1e-4)
    picture = _rgb(CARTON / 'front-picture.png')
    x_mm, y_mm = _panel_mm(front, picture.shape)
    in_lower = (x_mm >= lower[0]) & (x_mm < lower[2]) & (y_mm >= lower[1]) & (y_mm < lower[3])
    lock = front['lockup']['box_on_the_front_mm']
    assert lower[1] == pytest.approx(lock[3] + zc.DRIFT_BELOW_LIPSTICK_MM, abs=1e-3)
    assert lower[0] == front['front_safe_mm'][0] and lower[2] == front['front_safe_mm'][2]
    assert lower[3] == front['front_safe_mm'][3]
    on = zc.plate_distance(picture, zc.hex_rgb(front['ground']['colour'])) > zc.STONE_DE
    share = float(on[in_lower].mean())
    assert share == pytest.approx(cov['lower_front_share'], abs=1e-4)
    assert abs(share - cov['wrap_body_share']) <= cov['tolerance'] and cov['holds']
    blank = picture.copy()
    blank[in_lower] = zc.hex_rgb(front['ground']['colour'])
    gone = float((zc.plate_distance(blank, zc.hex_rgb(front['ground']['colour'])) > zc.STONE_DE)[in_lower].mean())
    assert gone == 0.0 and abs(gone - cov['wrap_body_share']) > cov['tolerance']


@built
def test_the_drift_is_at_the_wraps_scale_read_back_from_the_written_picture():
    """1 mm on the wrap = 1 mm on the carton, read from the pixels: the window's stones on the plate and the stones of
    the written picture's lower front, each piece of at least 1 mm² matched to the piece nearest its place after the
    recorded shift — the pairwise distances' ratio within 0.5 % of 1, each match within 0.1 mm of its place, and the
    record's matrix scale exactly 1 and its summed alpha within 1 %. The control: the front's pieces read 10 % larger
    about the window's corner give a ratio of 1.1 and fail."""
    plan = _json(CARTON / zc.PLAN_NAME)
    front = _json(CARTON / 'carton-front.json')
    drift = front['drift']
    assert drift['scale'] == 1.0 and drift['scale_xy'] == [1.0, 1.0]
    assert abs(drift['scale_measured'] - 1.0) <= 0.005 and abs(drift['area_read_by_alpha_mm2']['ratio'] - 1.0) <= 0.01
    assert drift['unrolled'] == {'one_window': True, 'scale': 1.0, 'rotation_deg': 0.0, 'mirrored': False, 'tiled': False,
                                 'stones_moved': 0, 'said': drift['unrolled']['said']}
    plate = _rgb(lm.REPO / plan['plate'])
    kp = zc.plate_scale(plate.shape)
    w = plan['window']['on_the_wrap_mm']
    rows, cols, origin = zc.window_pixels(w, kp, plate.shape[1])
    src = zc.plate_distance(plate[rows][:, cols], np.median(plate.reshape(-1, 3), axis=0)) > zc.STONE_DE
    on_wrap = _stone_pieces(src, kp, origin, 1.0)
    picture = _rgb(CARTON / 'front-picture.png')
    k = zc.FRONT_PX_PER_MM
    ox, oy = front['panel_on_the_picture_mm']
    fw = plan['window']['on_the_front_mm']
    x0, y0, x1, y1 = (int(round((v + o) * k)) for v, o in zip(fw, (ox, oy, ox, oy)))
    on = zc.plate_distance(picture[y0:y1, x0:x1], zc.hex_rgb(front['ground']['colour'])) > zc.STONE_DE
    on_front = _stone_pieces(on, k, (x0 / k - ox, y0 / k - oy), 1.0)          # panel mm
    shift = drift['shift_wrap_to_panel_mm']
    assert len(on_wrap) >= 3

    matched = [min(on_front, key=lambda q: np.hypot(q[0] - p[0] - shift[0], q[1] - p[1] - shift[1])) for p in on_wrap]
    assert len(set(matched)) == len(matched)                     # each stone its own piece on the front

    def ratio(front_pieces):
        d_w = sum(np.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(on_wrap) for b in on_wrap[i + 1:])
        d_f = sum(np.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(front_pieces) for b in front_pieces[i + 1:])
        off = max(np.hypot(f[0] - p[0] - shift[0], f[1] - p[1] - shift[1]) for p, f in zip(on_wrap, front_pieces))
        return d_f / d_w, off

    got, off = ratio(matched)
    assert abs(got - 1.0) <= 0.005 and off <= 0.1
    corner = (fw[0], fw[1])
    larger = [(corner[0] + 1.1 * (x - corner[0]), corner[1] + 1.1 * (y - corner[1]), a) for x, y, a in matched]
    assert abs(ratio(larger)[0] - 1.0) > 0.05 and ratio(larger)[1] > 0.1


@built
def test_the_lockup_is_untouched_byte_for_byte_against_day12():
    """The hero untouched: the front picture's rows above both days' drifts are Day 12's bytes (the ground's grain and
    the whole lockup), and the lockup's record is Day 12's; the control — one lockup pixel changed — is caught."""
    front, day12 = _json(CARTON / 'carton-front.json'), _json(D12 / 'carton-front.json')
    assert front['lockup'] == day12['lockup']
    k = zc.FRONT_PX_PER_MM
    oy = front['panel_on_the_picture_mm'][1]
    top = min(front['drift']['box_on_the_front_mm'][1], day12['drift']['box_on_the_front_mm'][1])
    rows = int(np.floor((top + oy) * k))
    lock_bottom = int(np.ceil((front['lockup']['box_on_the_front_mm'][3] + oy) * k))
    assert rows > lock_bottom                                    # every lockup row is compared
    mine, theirs = np.asarray(Image.open(CARTON / 'front-picture.png')), np.asarray(Image.open(D12 / 'front-picture.png'))
    assert mine.shape == theirs.shape and np.array_equal(mine[:rows], theirs[:rows])
    changed = mine[:rows].copy()
    changed[lock_bottom - 20, mine.shape[1] // 2, 0] ^= 1
    assert not np.array_equal(changed, theirs[:rows])


@built
def test_nothing_of_the_drift_lies_within_1_5_mm_of_a_fold_or_the_bottom_score():
    """The eye's repair text: the drift at least 1.5 mm clear of the folds and the bottom score — read on the written
    picture (every pixel there within the ground's grain, under STONE_DE ΔE76 of the ground) and in the record (the
    drift's box inside the 3 mm safe area, nothing outside it, the fold read-back calm). The control: a stone pixel
    planted 1 mm from the left fold is caught."""
    front = _json(CARTON / 'carton-front.json')
    w_mm, h_mm = front['panel_mm']
    picture = _rgb(CARTON / 'front-picture.png')
    x_mm, y_mm = _panel_mm(front, picture.shape)
    near = ((x_mm < FOLD_CLEAR_MM) | (x_mm > w_mm - FOLD_CLEAR_MM) | (y_mm > h_mm - FOLD_CLEAR_MM))
    near &= (x_mm > -0.5) & (x_mm < w_mm + 0.5) & (y_mm < h_mm + 0.5) & (y_mm > front['drift']['box_on_the_front_mm'][1])
    ground = zc.hex_rgb(front['ground']['colour'])
    assert zc.plate_distance(picture[near], ground).max() < zc.STONE_DE
    box, safe = front['drift']['box_on_the_front_mm'], front['front_safe_mm']
    assert box[0] >= FOLD_CLEAR_MM and box[2] <= w_mm - FOLD_CLEAR_MM and box[3] <= h_mm - FOLD_CLEAR_MM
    assert front['drift']['check']['holds'] and box[0] >= safe[0] and box[2] <= safe[2] and box[3] <= safe[3]
    assert front['art_outside_the_safe_area_px'] == 0 and front['nothing_crosses'] and front['readback']['folds_hold']
    planted = picture.copy()
    k = zc.FRONT_PX_PER_MM
    ox, oy = front['panel_on_the_picture_mm']
    planted[int((50.0 + oy) * k), int((1.0 + ox) * k)] = (230.0, 140.0, 120.0)
    assert zc.plate_distance(planted[near], ground).max() >= zc.STONE_DE


@built
def test_the_window_carries_no_letter_and_cuts_only_where_the_wrap_cuts():
    """No letter carried: the window ends where the words' zone begins and holds none of it. Its edges: the top on the
    wrap's own trim and the right on the front's safe line may cut the bank (as the wrap's trim and seam cut it); the
    left and the bottom carry no alpha — on the record and on the written picture's pixels just inside them; no ground
    carried as a patch; the front holds."""
    plan, front = _json(CARTON / zc.PLAN_NAME), _json(CARTON / 'carton-front.json')
    w = plan['window']['on_the_wrap_mm']
    assert w[2] <= min(z[0] for z in plan['words_zone_on_the_wrap_mm'].values()) + 1e-6
    assert w[1] == zc.WRAP_TRIM_MM[0] and w[3] <= zc.WRAP_TRIM_MM[1] and not plan['window']['crosses_the_seam']
    drift = front['drift']
    assert set(drift['edges']['that_cut']) == {'top', 'right'} and drift['edges']['that_must_not_cut'] == ['left', 'bottom']
    assert drift['window_edge_alpha_on_the_front']['left'] == 0.0 and drift['window_edge_alpha_on_the_front']['bottom'] == 0.0
    assert drift['edges']['holds'] and drift['edges']['top_on_the_wraps_trim'] and drift['edges']['right_on_the_safe_line']
    assert drift['ground_carried_px'] == 0 and front['holds']
    picture = _rgb(CARTON / 'front-picture.png')
    k = zc.FRONT_PX_PER_MM
    ox, oy = front['panel_on_the_picture_mm']
    fw = plan['window']['on_the_front_mm']
    x0, y0, x1, y1 = (int(round((v + o) * k)) for v, o in zip(fw, (ox, oy, ox, oy)))
    ground = zc.hex_rgb(front['ground']['colour'])
    assert zc.plate_distance(picture[y0:y1, x0], ground).max() < zc.STONE_DE           # the left edge's column
    assert zc.plate_distance(picture[y1 - 1, x0:x1], ground).max() < zc.STONE_DE       # the bottom edge's row
    assert zc.plate_distance(picture[y0, x0:x1], ground).max() >= zc.STONE_DE          # the top: the bank runs off
