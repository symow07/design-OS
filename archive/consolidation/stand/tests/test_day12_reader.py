"""Day 12 §0b — the silhouette reader (D-D12-9): the heroes' silhouette is the bevel's outer dark edge and their
counters stay closed. Golden on the tracer trial's three reference cases (docs/audit/tracer-trial/inputs: ظلال and
"Enchanted Rose" on the B-1.3 lid, شفاه on the lipstick's pick, each read at 2×), with the proof's power shown: the
trial's own alphas (Day 11's reader) and the fixed trace moved past the bar fail where the fixed trace holds. A planted
ring with a crack shows the seal rule (under 0.15 mm sealed and listed; wider kept open). Nothing here pays."""
import json

import cv2
import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_lipstick_master as zlm
from apps.pipeline.services import zilal_master as zm

TRIAL = zm.REPO / 'docs' / 'audit' / 'tracer-trial' / 'inputs'
trial_here = pytest.mark.skipif(not (TRIAL / 'zilal-2x.png').exists(), reason='the tracer trial\'s inputs are not here')

#: what each case must read: its parts (the trial's count: every part kept whole), its counters (ظ's bowl; the name's
#: five; ف and ه), and the points of the outer-edge proof over 0.3 mm, at most as measured on 24 October (each one
#: classified in docs/audit/day-12/reader/golden.json: at corners, short of the edge or past it)
GOLDEN = {'zilal': {'parts': 3, 'counters': 1, 'over_at_most': 50},
          'enchanted_rose': {'parts': 13, 'counters': 5, 'over_at_most': 3},
          'shifah': {'parts': 5, 'counters': 2, 'over_at_most': 5}}


def case_inputs(name):
    """The trial's own inputs for one case, as its runner read them (docs/audit/rescue_runtime/tracer-trial/trial.py):
    the sketch at its scale, the element's own mask on it, its window and px/mm, the hole limit."""
    if name in ('zilal', 'enchanted_rose'):
        pick = zm.load_pick()
        el = 'hero' if name == 'zilal' else 'name'
        x0, y0, x1, y1 = zm.WINDOWS[el]
        own = np.zeros(pick.shape[:2], dtype=bool)
        own[y0:y1, x0:x1] = zm.element_mask(pick, el, zm.masks(pick))
        return pick, own, list(zm.WINDOWS[el]), lm.PX_PER_MM_SRC, zm.HOLE_FILL_MM2 if el == 'hero' else zm.NAME_HOLE_MM2
    raw, _, _ = zlm.load_wrap(zlm.SKETCHES / 'S3-retry', 'body')
    rgb, _ = zlm.trim_rows(raw)
    k = rgb.shape[1] / zlm.WRAP_MM[0]
    hero = zlm.find_hero(rgb, zlm.masks(rgb, zlm.ground_lab(rgb)), k)
    return rgb, hero['mask'], hero['window_px'], k, zm.HOLE_FILL_MM2


def counters(rings, hole_mm2):
    from shapely.geometry import Polygon
    return sum(1 for g in lm.parts(lm.rings_area(rings, 24)) for r in g.interiors if Polygon(r).area >= hole_mm2)


@pytest.fixture(scope='module')
def reads():
    out = {}
    for name in GOLDEN:
        rgb, own, window, k, hole = case_inputs(name)
        rings, proof = zm.read_hero(rgb, own, window, k, hole)
        out[name] = {'rgb': rgb, 'window': window, 'k': k, 'hole': hole, 'rings': rings, 'proof': proof}
    return out


@trial_here
@pytest.mark.parametrize('name', sorted(GOLDEN))
def test_the_reader_reads_each_trial_hero_on_its_outer_dark_edge_with_its_counters_closed(reads, name):
    r, want = reads[name], GOLDEN[name]
    x0, y0, x1, y1 = [v * zm.READ_UP for v in r['window']]
    trial = np.asarray(Image.open(TRIAL / ('%s-2x.png' % name)).convert('RGB'))
    assert np.array_equal(zm.read_up(r['rgb'])[y0:y1, x0:x1], trial), 'the read is the trial\'s own 2× crop, byte for byte'
    proof = r['proof']
    assert proof['parts'] == want['parts']
    assert counters(r['rings'], r['hole']) == want['counters'] == proof['reader']['counters_closed']
    assert proof['iou'] >= zm.TRACE_IOU_MIN and proof['holds']['within_0_3_mm']
    edge = proof['outer_dark_edge']
    assert edge['p99_mm'] <= zm.TRACE_MAX_MM
    assert edge['unread_share'] <= lm.EDGE_UNREAD_MAX
    assert edge['over_0_3_mm'] == len(edge['over_points_mm']) <= want['over_at_most']


@trial_here
def test_the_trials_own_alphas_and_a_moved_trace_fail_the_outer_edge_proof(reads):
    """Power: Day 11's reader (the trial's saved alphas, traced by the same trace) sits on the bevel's highlight and
    reads many times more points over the bar; the fixed trace moved 0.35 or 0.45 mm reads most of its outline over."""
    for name, r in reads.items():
        k2 = r['k'] * zm.READ_UP
        window2 = [v * zm.READ_UP for v in r['window']]
        up = zm.read_up(r['rgb'])
        ground = r['proof']['reader']['ground']
        old_alpha = np.asarray(Image.open(TRIAL / ('%s-alpha.png' % name))).astype(np.float32) / 255.0
        old_rings, _ = zm.trace_alpha(old_alpha, window2, k2)
        old = zm.prove_outer_edge(up, old_rings, k2, ground)
        new = r['proof']['outer_dark_edge']
        assert old['over_0_3_mm'] >= 5 * max(new['over_0_3_mm'], 1), (name, old['over_0_3_mm'], new['over_0_3_mm'])
        for dx in (0.35, -0.35, 0.45):
            moved = zm.prove_outer_edge(up, lm.map_rings(r['rings'], lambda p, d=dx: (p[0] + d, p[1])), k2, ground)
            assert not moved['holds'] and moved['over_0_3_mm'] >= 0.25 * moved['points'], (name, dx, moved['over_0_3_mm'])


def _planted_ring(crack_mm, k):
    """A bevelled copper ring (outer radius 3 mm, counter radius 1.4 mm) on the indigo ground, drawn 8× and averaged
    down to ``k`` px/mm, with a ground-dark crack of ``crack_mm`` across from the outside into the counter (none at 0)."""
    s = 8
    size = int(10 * k) * s
    c = size / 2.0
    yy, xx = np.mgrid[0:size, 0:size]
    rr = np.hypot(xx - c, yy - c) / (k * s)
    img = np.zeros((size, size, 3), np.float32)
    img[:] = (0x10, 0x1A, 0x45)
    ring = (rr <= 3.0) & (rr >= 1.4)
    img[ring] = (0xC8, 0x8F, 0x70)
    img[(rr <= 3.0) & (rr >= 2.85)] = (0xF0, 0xD0, 0xB0)            # the rim's highlight
    if crack_mm > 0:
        half = crack_mm * k * s / 2.0
        img[(np.abs(yy - c) <= half) & (xx > c) & ring] = (0x10, 0x1A, 0x45)
    small = cv2.resize(img, (size // s, size // s), interpolation=cv2.INTER_AREA)
    rgb = np.clip(small, 0, 255).astype(np.uint8)
    own = np.zeros(rgb.shape[:2], dtype=bool)
    n = rgb.shape[0]
    yy1, xx1 = np.mgrid[0:n, 0:n]
    r1 = np.hypot(xx1 - n / 2.0, yy1 - n / 2.0) / k
    own[(r1 <= 2.9) & (r1 >= 1.5)] = True
    return rgb, own, [0, 0, n, n]


@pytest.mark.parametrize('crack_mm, sealed', [(0.0, None), (0.10, True), (0.20, False)])
def test_a_crack_under_0_15_mm_into_a_counter_is_sealed_and_listed_and_a_wider_one_kept_open(crack_mm, sealed):
    k = 2 * lm.PX_PER_MM_SRC
    rgb, own, window = _planted_ring(crack_mm, k)
    alpha, rec = zm.bevel_alpha(rgb, window, own, k, zm.HOLE_FILL_MM2)
    rings, _ = zm.trace_alpha(alpha, window, k)
    joins = [j for j in rec['joins'] if j['read_as'] == 'dark']
    if sealed is None:
        assert joins == [] and counters(rings, zm.HOLE_FILL_MM2) == 1
    elif sealed:
        assert [j['sealed'] for j in joins] == [True] and joins[0]['width_mm'] < zm.SEAL_MM
        assert counters(rings, zm.HOLE_FILL_MM2) == 1
    else:
        assert [j['sealed'] for j in joins] == [False] and joins[0]['width_mm'] >= zm.SEAL_MM
        assert counters(rings, zm.HOLE_FILL_MM2) == 0 and rec['openings_kept'] == 1


def test_the_reader_refuses_a_window_with_no_ground_to_read():
    k = 2 * lm.PX_PER_MM_SRC
    rgb = np.full((20, 20, 3), 200, np.uint8)
    own = np.ones((20, 20), dtype=bool)
    with pytest.raises(ValueError):
        zm.bevel_alpha(rgb, [0, 0, 20, 20], own, k, zm.HOLE_FILL_MM2)


@pytest.mark.skipif(not zm.MASTER_PICK.exists(), reason='the lid\'s pick of record is not here')
def test_the_lids_logotype_is_not_retraced_by_the_reader_fix():
    """D-D11-7 and D-D12-2: "Enchanted Rose" is the lid's own vector — the fix leaves its trace (name_alpha) unchanged:
    its 18 rings and the ink box the lipstick's master recorded on 24 October."""
    rings, _, _ = zm.trace_name(zm.load_master_pick())
    recorded = json.loads((zm.DAY11 / 'lipstick' / 'master' / 'PIECES.json').read_text(encoding='utf-8'))['logotype']
    assert len(rings) == recorded['rings']
    assert [round(v, 3) for v in lm.rings_area(rings, 24).bounds] == recorded['ink_box_lid_mm']
