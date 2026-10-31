"""Day 11 — Golden Hour closed as test one (D-D11-5): the bars embossed, the tray's teal (code), the sticker's corrected
lines (D-D11-6), one Latin face, and Day 10's files untouched.

The measuring functions are tested on synthetic inputs, each check beside a control that must fail (a planted fault);
the day's files are read where they are on this machine (skipped where they are not) and measured from the files
themselves — the relief from the file's EMBOSS plate, the sticker's words from its own ActualText."""
import json

import numpy as np
import pytest

from apps.pipeline.services import golden_hour_fixes as gf
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import palette_open as po
from apps.pipeline.services import palette_sticker as ps
from apps.pipeline.services import round_files_faces as faces

GH = gf.GH
DAY10 = lm.REPO / 'docs' / 'audit' / 'day-10'
lid_here = pytest.mark.skipif(not (GH / 'lid' / 'master.json').exists(), reason='Golden Hour\'s Day 11 lid is not here')
sticker_here = pytest.mark.skipif(not (GH / 'sticker' / 'fit-report.json').exists(),
                                  reason='Golden Hour\'s Day 11 sticker is not here')
pick_here = pytest.mark.skipif(not lm.PICK.exists(), reason='the owner\'s pick is not on this machine')
day10_here = pytest.mark.skipif(not (DAY10 / 'sticker' / 'fit-report.json').exists(), reason='Day 10 is not here')


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


# --- 1. the relief: 0.3 mm on the file's own plate -----------------------------------------------------------------------

def _ring(points):
    return [('L', points[i], points[(i + 1) % len(points)]) for i in range(len(points))]


def _plate_file(tmp_path, rings, name):
    """An engine page carrying ``rings`` on the EMBOSS plate (the lid master's own carrier), emitted as the master is."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group
    doc = Document(page_w=lm.LID_MM[0], page_h=lm.LID_MM[1], metadata={'typography_surface': lm.SURFACE},
                   root=Group(name='T', children=[lm.relief_carrier(rings, '#C69559')]))
    path = tmp_path / name
    emit_pdf_ai(doc, str(path))
    return path


BAR = [(10.0, 10.0), (40.0, 10.0), (40.0, 16.0), (10.0, 16.0)]
#: the control: the same bar with a sliver 0.2 mm wide and 3 mm long standing off its edge
BAR_WITH_SLIVER = [(10.0, 10.0), (40.0, 10.0), (40.0, 16.0), (25.1, 16.0), (25.1, 19.0), (24.9, 19.0), (24.9, 16.0),
                   (10.0, 16.0)]


def test_the_relief_plate_holds_at_0_3_mm_and_a_planted_0_2_mm_sliver_is_refused(tmp_path):
    clean = gf.relief_limits(_plate_file(tmp_path, [_ring(BAR)], 'clean.ai'))
    assert clean['holds'] is True and [p['plate'] for p in clean['plates']] == [lm.RELIEF_PLATE]
    sliver = gf.relief_limits(_plate_file(tmp_path, [_ring(BAR_WITH_SLIVER)], 'sliver.ai'))
    assert sliver['holds'] is False and sliver['plates'][0]['thin']['parts'] == 1
    # a gap of 0.2 mm between two bars is refused too
    gap = [_ring([(10.0, 10.0), (40.0, 10.0), (40.0, 16.0), (10.0, 16.0)]),
           _ring([(10.0, 16.2), (40.0, 16.2), (40.0, 22.0), (10.0, 22.0)])]
    assert gf.relief_limits(_plate_file(tmp_path, gap, 'gap.ai'))['holds'] is False


def test_no_relief_plate_is_never_a_pass(tmp_path):
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group
    path = tmp_path / 'none.ai'
    emit_pdf_ai(Document(page_w=lm.LID_MM[0], page_h=lm.LID_MM[1], metadata={'typography_surface': lm.SURFACE},
                         root=Group(name='T', children=[])), str(path))
    assert gf.relief_limits(path)['holds'] is None


def test_open_close_leaves_no_part_or_gap_under_the_limit():
    """The construction: a bar with a 0.2 mm sliver and two bars 0.2 mm apart, opened and closed at 0.33 mm — no part
    and no gap under 0.3 mm survives (the opening's and the closing's residue at 0.3 mm, read with the foil limits'
    exact disk); the control, the raw mask, has both."""
    from apps.pipeline.services import finish_proof as fp
    k = lm.PX_PER_MM_SRC * gf.RELIEF_SCALE
    mask = np.zeros((int(20 * k), int(30 * k)), dtype=bool)
    mask[int(2 * k):int(8 * k), int(2 * k):int(28 * k)] = True                       # a bar
    mask[int(8 * k):int(11 * k), int(15 * k):int(15.2 * k)] = True                   # its 0.2 mm sliver
    mask[int(8.2 * k):int(14 * k), int(2 * k):int(12 * k)] = True                    # a bar 0.2 mm below
    r = (gf.RELIEF_MIN_MM * k - fp.AA_TOLERANCE_PX) / 2

    def residue(m):
        thin = m & ~fp._opened(m, r)
        gaps = ~m & ~fp._opened(~m, r)
        return thin.sum() > 0.05 * k * k, gaps.sum() > 0.05 * k * k

    assert residue(mask) == (True, True)
    cleaned, _ = gf.open_close(mask, gf.RELIEF_CONSTRUCT_MM)
    assert residue(cleaned) == (False, False)


MEASURED = ('within_the_isoline', 'reaches_the_isoline', 'off_the_glow', 'the_control_fails', 'the_reach_control_fails',
            'plate_0_3_mm')
NOT_MEASURED = ('capped_outer_edges', 'bar_ends')     # by construction: never recorded as held


@lid_here
def test_the_masters_relief_plate_holds_0_3_mm_read_from_the_file():
    rec = _json(GH / 'lid' / 'master.json')['finishes']['relief_mask']
    measured = gf.relief_limits(GH / 'lid' / 'engine' / 'lid-engine.ai')
    assert measured['holds'] is True and measured['plates'][0]['plate'] == lm.RELIEF_PLATE
    assert rec['plate_limits']['holds'] is True
    assert all(rec['holds'][k] is True for k in MEASURED)
    # what holds only by construction is recorded None, and the eye's verdict None until it has looked at these crops
    assert all(rec['holds'][k] is None for k in NOT_MEASURED) and set(rec['by_construction']) == set(NOT_MEASURED)
    assert rec['holds']['eye'] == rec['eye']['holds']
    assert rec['eye']['state'] == gf.relief_eye_state(GH / 'lid')['state']
    assert set(rec['holds']) == set(MEASURED) | set(NOT_MEASURED) | {'eye'}
    assert measured['plates'][0]['foil_area_mm2'] == pytest.approx(rec['area_mm2'], rel=0.01)


def _file_mask():
    """The EMBOSS plate as the master's file carries it, on the relief's 8× grid over the oval."""
    from apps.pipeline.services import finish_proof as fp
    plates = fp.plate_masks(GH / 'lid' / 'engine' / 'lid-engine.ai', px_per_mm=lm.PX_PER_MM_SRC * gf.RELIEF_SCALE)
    mask = [p for p in plates if p['plate'] == lm.RELIEF_PLATE][0]['mask']
    x0, y0, x1, y1 = (v * gf.RELIEF_SCALE for v in lm.OVAL_BOX)
    assert not mask[:y0].any() and not mask[y1:].any() and not mask[:, :x0].any() and not mask[:, x1:].any()
    return mask[y0:y1, x0:x1]


@pytest.fixture(scope='module')
def frame():
    return gf.read_bars(lm.load_pick(lm.PICK))


@pick_here
@lid_here
def test_the_glow_is_outside_the_mask_and_a_plain_threshold_is_refused(frame):
    """The oval's glow is not embossed: the file's plate meets none of the glow probe (the gap between bars, the halo
    beyond the outer bars, the bars' fading ends — defined from the bars' edge lines, never from the mask). The control:
    the oval read by L* ≥ 70 alone takes in the halo and is refused."""
    glow = gf.glow_probe(frame)
    assert gf.glow_check(_file_mask(), glow)['holds']
    control = gf.glow_check(gf.control_mask(lm.load_pick(lm.PICK)), glow)
    assert not control['holds'] and control['mask_on_glow_mm2'] > 10


@pick_here
@lid_here
def test_the_mask_lies_within_the_bars_50_percent_isoline(frame):
    """Measured: the file's mask lies within the isoline region, or within 0.2 mm of it (the closing's gaps under the
    limit, the trace's smoothing). The control: the same mask grown by 0.5 mm is refused."""
    import cv2
    _, region = gf.isoline_raster(frame)
    mask = _file_mask()
    within = gf.within_isoline(mask, region)
    assert within['holds'] and within['outside_share'] < 0.01
    grow = int(round(0.5 * lm.PX_PER_MM_SRC * gf.RELIEF_SCALE))
    grown = cv2.dilate(mask.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
    assert not gf.within_isoline(grown.astype(bool), region)['holds']


def _ends_cut(mask, frame, mm):
    """The mask with every bar cut ``mm`` at each end (the review's planted fault)."""
    cut = mask.copy()
    k = lm.PX_PER_MM_SRC
    for bar in frame['bars']:
        win, u, v = gf._bar_window(bar, frame)
        start, stop = bar['run']
        band = np.abs(v - bar['mid_v']) <= bar['width_px']
        ends = (u < bar['us'][start] + mm * k) | (u > bar['us'][stop - 1] - mm * k)
        cut[win] &= ~(band & ends)
    return cut


@pick_here
@lid_here
def test_the_mask_reaches_the_walked_isoline_and_a_mask_short_of_the_bars_is_refused(frame):
    """The review of Day 11: the outward checks pass a mask that falls short of the bars. The reach check: the walked
    isoline, eroded by 0.2 mm and with the capped outer sides left out, lies inside the file's mask. The controls, the
    review's own faults, each pass the outward checks and are refused here: the mask eroded by 0.5 mm, and every bar
    cut 10 mm at each end."""
    _, region = gf.isoline_raster(frame)
    glow = gf.glow_probe(frame)
    reach, left_out = gf.reach_raster(frame)
    mask = _file_mask()
    held = gf.reach_check(mask, reach)
    assert held['holds'] and held['short_mm2'] == 0.0 and held['eroded_mm2'] > 1500
    for fault in (gf._erode(mask, gf.REACH_CONTROL_MM), _ends_cut(mask, frame, 10.0)):
        assert gf.within_isoline(fault, region)['holds'] and gf.glow_check(fault, glow)['holds']   # passed before
        refused = gf.reach_check(fault, reach)
        assert not refused['holds'] and refused['short_mm2'] > 100
    rec = _json(GH / 'lid' / 'master.json')['finishes']['relief_mask']
    assert rec['reach']['holds'] and not rec['reach_control']['holds']


@pick_here
def test_the_reach_leaves_out_only_the_capped_outer_sides(frame):
    """Bar 1's top and bar 5's foot are capped at the edge line (+ 0.25 mm), not walked to the isoline: the reach is
    not measured against them. Left out there (and where the walk's median spreads the cap), from the core line out;
    everywhere else the walked isoline itself. The control: the walked isoline with the capped sides kept is larger by
    the capped halves, and every bar's inner side is in both."""
    walked, _ = gf.isoline_raster(frame)
    reach, left_out = gf.reach_raster(frame)
    assert not (reach & ~walked).any()                                  # never more than the walk
    assert [(r['bar'], r['side']) for r in left_out] == [(1, 'upper'), (5, 'lower')]
    for r in left_out:
        bar = frame['bars'][r['bar'] - 1]
        side = {'upper': -1, 'lower': 1}[r['side']]
        assert r['stations_capped'] == int(bar['capped'][side].sum()) > 0
        assert r['stations_capped'] <= r['stations_left_out'] <= r['stations']
    px_mm2 = (lm.PX_PER_MM_SRC * gf.RELIEF_SCALE) ** 2
    assert (walked & ~reach).sum() / px_mm2 > 100                      # the capped halves: left out
    for k in (1, 2, 3):                                                # bars 2–4 have no capped side: kept whole
        assert not frame['bars'][k]['capped']


@lid_here
def test_the_relief_is_on_every_page_that_should_carry_it():
    """The finish proof reads the EMBOSS plate (relief over 0 %), the layered file's relief layer is no longer empty, the
    print file's relief page says so, and the eye's crops are each under its pixel limits."""
    import fitz
    master = _json(GH / 'lid' / 'master.json')
    assert master['finishes']['coverage']['relief_pct'] > 5.0
    back = master['ai_read_back']
    assert back['holds'] and back['empty_layers'] == []
    with fitz.open(str(GH / 'lid' / 'lid-master.pdf')) as pdf:
        assert 'blind emboss' in pdf[2].get_label() and pdf[2].get_drawings()
    crops = _json(GH / 'lid' / 'relief-edge-crops.json')
    assert len(crops['pieces']) == 5 and all(p['under_the_eyes_limits'] for p in crops['pieces'])
    sheet = {p['plate'] for p in master['finish_sheet']['plates']}
    assert lm.RELIEF_PLATE in sheet and lm.FOIL_PLATE in sheet


@lid_here
def test_the_box_front_carries_the_relief_and_the_corrected_sticker():
    import fitz
    box = _json(GH / 'box' / 'box-fold-check.json')
    assert box['fold_check']['passed'] and box['die_untouched']['holds'] and box['clean']['holds']
    assert box['sources']['lid'].endswith('golden-hour/lid') and box['sources']['sticker'].endswith('golden-hour/sticker')
    with fitz.open(str(GH / 'box' / 'box-artwork.pdf')) as pdf:
        assert 'blind emboss' in pdf[2].get_label() and pdf[2].get_drawings()
    words = ' '.join(lm.actual_texts(GH / 'box' / 'box-artwork.pdf', 0))
    assert ps.CORRECTED['es']['claims'].split(' · ')[0] in words and ps.PALETTE_AR_NEVER not in words


# --- 3. the sticker's lines (D-D11-6) ------------------------------------------------------------------------------------

UNCONFIRMED = [{'en': 'Cruelty-free', 'ar': 'خالٍ من القسوة', 'ar_source': ps.AR_UNCONFIRMED},
               {'en': '100% vegan', 'ar': 'نباتي 100٪', 'ar_source': ps.AR_UNCONFIRMED}]
CONFIRMED = [{'en': 'Cruelty-free', 'ar': 'خال من القسوة', 'ar_source': 'OWNER'},
             {'en': '100% vegan', 'ar': 'نباتي 100٪', 'ar_source': 'OWNER'}]


def test_the_arabic_claims_print_the_house_record_only_when_confirmed():
    from apps.core import models as core
    assert ps.AR_UNCONFIRMED is core.AR_UNCONFIRMED                    # the house's mark, imported, never repeated
    text, _, confirm, _ = ps.arabic_claims(CONFIRMED)
    assert text == 'خال من القسوة · نباتي 100٪' and not confirm
    # the review of Day 11: a row with no ar_source (or an empty one) is unconfirmed — it never fails open
    no_source = [{k: v for k, v in r.items() if k != 'ar_source'} for r in CONFIRMED]
    empty_source = [dict(r, ar_source='') for r in CONFIRMED]
    for claims in (UNCONFIRMED, [], CONFIRMED[:1] + UNCONFIRMED[1:], no_source, empty_source, CONFIRMED[:1] + no_source[1:]):
        text, _, confirm, _ = ps.arabic_claims(claims)
        assert text == ps.AR_CLAIMS_FALLBACK and confirm


def test_a_claims_row_without_ar_source_failed_open_under_the_old_rule():
    """The control of the claims fix: the rule as it stood (unconfirmed only when ar_source says EXECUTOR_UNCONFIRMED)
    printed a row with no ar_source as confirmed; ``confirmed_arabic`` does not."""
    def old_unconfirmed(r):
        return 'ar' not in r or not r['ar'] or ('ar_source' in r and r['ar_source'] == ps.AR_UNCONFIRMED)
    row = {'en': 'Cruelty-free', 'ar': 'خال من القسوة'}
    assert not old_unconfirmed(row) and not ps.confirmed_arabic(row)
    assert ps.confirmed_arabic(CONFIRMED[0]) and not ps.confirmed_arabic(UNCONFIRMED[0])


def test_a_claims_line_never_opens_on_a_separator_and_day_10s_wrap_did():
    """The claims wrap claim by claim, the separator kept at its line's end; the control: Day 10's word-by-word wrap of
    the same line at the same column opens a line on "·"."""
    fc = ps.faces()
    text = ps.CORRECTED['es']['claims']
    row = {'field': 'claims', 'head': None, 'text': text, 'script': 'latin', 'lang': 'es',
           'units': ps.wrap_units(text, 'claims')}
    plain = dict(row)
    plain.pop('units')
    opened = []
    for column in np.arange(18.0, 60.0, 0.5):
        lines = [' '.join(t for _, t in line) for line in ps.wrap(row, column, 7.0, fc)]
        assert not any(line.startswith(ps.SEPARATOR) for line in lines)
        assert ' '.join(lines) == text
        opened += [column for line in ps.wrap(plain, column, 7.0, fc) if ' '.join(t for _, t in line).startswith(ps.SEPARATOR)]
    assert opened                                   # the control has power: word by word, some width opens on "·"
    assert ps.wrap_units(text, 'claims') == [['No', 'testado', 'en', 'animales', '·'], ['100', '%', 'vegano', '·'],
                                             ['Probado', 'dermatológicamente', '·'], ['Larga', 'duración']]


def test_the_corrected_copy_refuses_lawha():
    """باليت everywhere: an Arabic line that still says لوحة is refused (the control: Day 10's machine description)."""
    translations = {'calls': {name: {'translations': {lang: dict(fields) for lang in ('es', 'ar')}} for name, fields in (
        ('prose', {'description': 'x', 'how_to_use': 'x', 'warnings': 'x'}),
        ('short lines', {'description': 'x', 'how_to_use': 'x', 'warnings': 'x'}),
        ('headings', {'product_name': 'x', 'description': 'x', 'how_to_use': 'x', 'warnings': 'x'}))}, 'model': 'm'}
    blocks = ps.corrected_copy(translations, UNCONFIRMED)
    assert {r['field']: r['text'] for r in blocks['ar']}['description'] == ps.CORRECTED['ar']['description']
    translations['calls']['prose']['translations']['ar']['warnings'] = 'لوحة ظلال'
    with pytest.raises(ValueError, match='لوحة'):
        ps.corrected_copy(translations, UNCONFIRMED)


@sticker_here
def test_the_stickers_corrected_lines_are_verbatim_in_both_languages_from_the_files_own_actual_text():
    fit = _json(GH / 'sticker' / 'fit-report.json')
    art = GH / 'sticker' / 'engine' / 'sticker-engine.ai'
    spans = lm.actual_texts(art, 0)
    names = fit['copy']['span_names']
    by_section = {}
    for n, sp in zip(names, spans):
        by_section.setdefault(tuple(n.split(':')[:2]), []).append(sp)
    blocks = ps.corrected_copy(_json(ps.TRANSLATIONS), [])          # no confirmed claims: the fallback, as printed
    heads = {(lang, r['field']): r['head'] for lang, rows in blocks.items() for r in rows}
    for lang, table in ps.CORRECTED.items():
        for field, text in table.items():
            words = text
            if heads[(lang, field)] is not None:
                words = heads[(lang, field)] + ': ' + text
            assert ps._norm(' '.join(by_section[(lang, field)])) == ps._norm(words), (lang, field)
    check = ps.copy_check(art, blocks, names)
    assert check['all_found'] and check['inci_in_every_language'] and check['net_in_every_language']
    # the AR claims: the owner's fallback, every Brand.claims row being unconfirmed — marked for him
    ar_claims = ps._norm(' '.join(by_section[('ar', 'claims')]))
    assert ar_claims == ps._norm(ps.AR_CLAIMS_FALLBACK) and fit['arabic_claims']['owner_to_confirm']
    assert {r['review'] for r in fit['owner_to_confirm']} == {ps.OWNER_TO_CONFIRM}
    assert fit['copy']['all_found'] and fit['dropped'] == [] and fit['moved'] == [] and fit['smallest_pt'] >= 5.0


@sticker_here
@day10_here
def test_no_lawha_and_no_line_opening_on_a_separator_in_the_file_and_day_10s_had_both():
    def faults(fit_path, art):
        spans = lm.actual_texts(art, 0)
        lines = [r['text'] for r in _json(fit_path)['lines']]
        return (any(ps.PALETTE_AR_NEVER in sp for sp in spans),
                any(t.startswith(ps.SEPARATOR) for t in lines) or any(sp.lstrip().startswith(ps.SEPARATOR) for sp in spans))
    assert faults(GH / 'sticker' / 'fit-report.json', GH / 'sticker' / 'engine' / 'sticker-engine.ai') == (False, False)
    assert faults(DAY10 / 'sticker' / 'fit-report.json', DAY10 / 'sticker' / 'engine' / 'sticker-engine.ai') == (True, True)


@sticker_here
@day10_here
def test_the_e_mark_stands_at_the_lines_cap_height_and_no_taller_than_its_neighbours():
    """Read from the file: three ℮ signs, each at the medium face's cap height at the ℮ line's size (≥ 3 mm), no
    taller than the figures beside it. The control: Day 10's signs (3 mm beside 9 pt figures of 2.2 mm) fail both."""
    fit = _json(GH / 'sticker' / 'fit-report.json')
    net = fit['net']
    signs = ps.signs_in_file(GH / 'sticker' / 'engine' / 'sticker-engine.ai', fit['ink'], net)
    assert len(signs) == 3 and all(s['at_the_cap_height'] and s['at_least_3_mm'] and s['never_larger_than_its_neighbours']
                                   for s in signs)
    assert net['cap_mm'] >= 3.0 and all(r['size_pt'] == net['pt'] for r in fit['lines'] if r['field'] == 'net')
    day10 = _json(DAY10 / 'sticker' / 'fit-report.json')
    day10_net = dict(net, cap_mm=ps.NET_PT * ps.MM_PER_PT * net['cap_em'],
                     neighbour_ink_mm={k: v * ps.NET_PT / net['pt'] for k, v in net['neighbour_ink_mm'].items()})
    old = ps.signs_in_file(DAY10 / 'sticker' / 'engine' / 'sticker-engine.ai', day10['ink'], day10_net)
    assert len(old) == 3 and not any(s['at_the_cap_height'] or s['never_larger_than_its_neighbours'] for s in old)


# --- 4. one Latin face ---------------------------------------------------------------------------------------------------

def _one_face(faces):
    return len({faces[k]['label'] for k in gf.ONE_FACE_LINES}) == 1


@lid_here
@day10_here
def test_one_latin_face_is_recorded_and_sets_all_three_small_lines():
    """The pooled choice recorded with its near-tie read both ways; the three Latin lines set in it (the type record
    and the media map); the control: Day 10's master set them in three faces."""
    master = _json(GH / 'lid' / 'master.json')
    one = master['faces'][lm.ONE_FACE_KEY]
    assert one['lines'] == list(gf.ONE_FACE_LINES) and one['near_tie']['agree'] and one['measured'] > 100
    assert _one_face(master['type']['faces'])
    assert {master['type']['faces'][k]['stem'] for k in gf.ONE_FACE_LINES} == {one['chosen']['stem']}
    media = {e['element']: e for e in _json(GH / 'lid' / 'media-map.json')['elements']}
    for key in gf.ONE_FACE_LINES:
        row = media[lm.LINES[key]['copy']]
        assert master['type']['faces'][key]['label'] in row['medium'] and 'pooled over all three' in row['why']
    assert not _one_face(_json(DAY10 / 'lid' / 'master.json')['type']['faces'])


@pick_here
@lid_here
def test_every_small_line_refitted_in_the_one_face_overlays_the_sketch_within_1_mm_and_3_percent():
    """Re-measured on the engine's own page: each line's glyphs against the sketch's (D-D10-1: 1 mm, 3 %). The control:
    the same reading with the drawn line moved 1.2 mm is refused."""
    pick = lm.load_pick(lm.PICK)
    render = lm.render_page(GH / 'lid' / 'engine' / 'lid-engine.ai', 0, lm.RENDER_PX_PER_MM)
    for key in lm.LINES:
        sketch, _ = lm.line_units(pick, key)
        drawn = lm.drawn_units(render, key)
        assert lm.overlay_proof(sketch, drawn)['holds'], key
    moved = [dict(u, box_mm=(u['box_mm'][0] + 1.2, u['box_mm'][1], u['box_mm'][2] + 1.2, u['box_mm'][3])) for u in drawn]
    assert not lm.overlay_proof(sketch, moved)['holds']
    checks = _json(GH / 'lid' / 'checks.json')
    assert all(checks['proofs']['type_placed'].values()) and checks['sizes']['smallest_holds']


# --- 2. the tray's teal: the code -----------------------------------------------------------------------------------------

def test_the_tray_prompt_states_the_colour_story_row_by_row_with_three_teal_pans_in_row_3():
    tray = po.tray_names()
    prompt = po.tray_story_prompt(tray)
    rows = [prompt.index('ROW %d' % i) for i in (1, 2, 3)]
    assert rows == sorted(rows)
    row3 = prompt[rows[2]:prompt.index('Row 3 must')]
    assert all(name in row3 for name in tray['names'][2]) and row3.count(' teal,') >= 3
    for r, names in enumerate(tray['names']):
        seg = prompt[rows[r]:]
        assert all(name in seg for name in names)
    from apps.pipeline.services import image_guard as ig
    assert not ig.competitor_in(prompt)


def _read(hexes):
    from apps.pipeline.targets.container import tray_picture as tp
    return {'state': tp.READ, 'pans': [[{'hex': h} for h in row] for row in hexes]}


def test_row_3s_teal_is_counted_from_the_picture_and_browns_are_not_teal():
    teals = ['#4F9A94', '#5FB3AE', '#2E6B6B', '#745555', '#65526A', '#43312E']
    assert po.teal_pans(_read([['#000000'] * 6, ['#000000'] * 6, teals]))['count'] == 3
    day10_row3 = ['#745555', '#65526A', '#43312E', '#402A36', '#252E3C', '#15222F']   # Day 10's tray, as read
    assert not po.teal_pans(_read([['#000000'] * 6, ['#000000'] * 6, day10_row3]))['holds']


def test_a_pan_too_close_to_the_case_is_lightened_by_the_least_step_that_reaches_delta_e_10():
    case = '#102638'
    rows = [{'name': 'Eternal', 'hex': '#252E3C', 'flags': []}, {'name': 'Petal Frost', 'hex': '#DAB4AC', 'flags': []}]
    moved = po.lift_from_case(rows, case)
    assert [m['name'] for m in moved] == ['Eternal'] and rows[1]['hex'] == '#DAB4AC'
    m = moved[0]
    de = float(faces.delta_e00(po._lab(m['to']), po._lab(case))[0])
    assert de >= po.CASE_DE_FLOOR and rows[0]['picture_hex'] == '#252E3C'
    # the control: one step less does not reach it
    lab = po._lab('#252E3C')[0]
    less = po._hex(po.lab_to_srgb(np.array([lab[0] + m['l_step'] - po.LIFT_STEP_L, lab[1], lab[2]])))
    assert float(faces.delta_e00(po._lab(less), po._lab(case))[0]) < po.CASE_DE_FLOOR


def test_lab_to_srgb_inverts_srgb_to_lab():
    rng = np.random.default_rng(11)
    rgb = rng.integers(0, 256, (200, 3)).astype(np.float64)
    assert np.abs(po.lab_to_srgb(faces.srgb_to_lab(rgb)) - rgb).max() < 0.01        # far under half a level


@lid_here
def test_the_tray_round_stops_at_the_limit_and_builds_from_what_it_has(tmp_path, monkeypatch):
    """The control of the paid round, at $0: the picture is stubbed with Day 10's (its row 3 holds no teal, so a retry
    is due), and the guard refuses the second picture — the round stops, says so, and still builds the pans and the
    artwork from the first; no picture is bought past the refusal."""
    import shutil
    source = DAY10 / 'tray' / 'picture.png'
    if not source.exists():
        pytest.skip('Day 10\'s tray picture is not here')
    bought = []

    def stub(name, prompt, *, client, out, prefix, cap_usd):
        assert prefix.startswith('day11/') and cap_usd == gf.TRAY_CAP_USD
        bought.append(name)
        (out / name).mkdir(parents=True)
        shutil.copyfile(source, out / name / 'picture.png')
        made = {'picture': str(out / name / 'picture.png'), 'output_sha256': lm.sha256(source), 'reservation_id': 'stub'}
        (out / name / 'picture.json').write_text(json.dumps(made))
        return made

    monkeypatch.setattr(gf, 'TRAY', tmp_path)
    monkeypatch.setattr(po, 'make_picture', stub)
    record = gf.make_tray(None, lambda name: name == 'picture-1')
    attempts = _json(tmp_path / 'attempts.json')
    assert bought == ['picture-1'] and attempts['chosen'] == 'picture-1' and 'picture-2 not bought' in attempts['stopped']
    assert not attempts['teal_holds'] and record['teal_row_3']['count'] == 0
    assert (tmp_path / 'pans.json').exists() and (tmp_path / 'tray-artwork.pdf').exists()
    assert all(a['de00'] >= po.CASE_DE_FLOOR for a in record['case']['pans_against_it'])


def test_the_tray_picture_goes_under_day_11_and_today():
    assert gf.TRAY == lm.REPO / 'docs' / 'audit' / 'day-11' / 'golden-hour' / 'tray'
    assert gf.TRAY_PREFIX.startswith('day11/') and gf.TRAY_CAP_USD >= 0.60 + 1.00 and gf.TRAY_ATTEMPTS == 3


# --- Day 10 untouched ----------------------------------------------------------------------------------------------------

@lid_here
def test_day_10s_files_were_left_untouched_by_the_regeneration():
    record = _json(GH / 'golden-hour.json')
    assert record['day10_untouched']['holds'] and record['day10_untouched']['files'] > 50
    assert record['cost_usd'] == 0.0 and 'skipped' in record['fixes']['5 super-resolution']
    # and still untouched now: Day 10's folder as a whole reads as it did right after the regeneration
    assert gf.digest_of(gf.tree_digest(DAY10)) == record['day10_untouched']['tree_sha256']


def test_one_changed_file_changes_the_folders_digest(tmp_path):
    (tmp_path / 'a.png').write_bytes(b'one')
    before = gf.digest_of(gf.tree_digest(tmp_path))
    (tmp_path / 'a.png').write_bytes(b'two')
    assert gf.digest_of(gf.tree_digest(tmp_path)) != before


# --- the review of Day 11: the relief's proof, the eye's texts, the margin, Day 10's defaults --------------------------

def _lid_copy(tmp_path, monkeypatch):
    """The lid's records copied to a scratch lid folder beside a copy of golden-hour.json (the crops they name are read
    where they are, never written): the merge is exercised there, never on the real records. (``lm.rel`` names repo
    paths only: a scratch path is named as it is.)"""
    import shutil
    from pathlib import Path
    rel = lm.rel
    monkeypatch.setattr(lm, 'rel', lambda p: rel(p) if Path(p).resolve().is_relative_to(lm.REPO) else str(p))
    lid = tmp_path / 'lid'
    (lid / 'engine').mkdir(parents=True)
    for name in ('master.json', 'checks.json', 'relief-edge-crops.json', 'finish-proof.png'):
        shutil.copyfile(GH / 'lid' / name, lid / name)
    shutil.copyfile(GH / 'lid' / 'engine' / 'flat-1536.png', lid / 'engine' / 'flat-1536.png')
    shutil.copyfile(GH / 'golden-hour.json', tmp_path / 'golden-hour.json')
    return lid


def _eye_stub(verdict, calls):
    def call(operation, content, schema):
        calls.append(operation)
        assert operation == 'relief-edge' and schema is gf.RELIEF_LOOK_SCHEMA
        assert sum(1 for c in content if c['type'] == 'image') == 6          # five pieces and the overview
        return {'payload': {'pieces': [], 'follows_the_bars': True, 'glow_inside': False, 'cuts_into_a_bar': False,
                            'verdict': verdict, 'notes': 'stub'}, 'stop_reason': 'end_turn', 'cost_usd': 0.0}
    return call


@lid_here
def test_the_eyes_verdict_is_pending_until_it_looks_and_is_merged_into_every_record(tmp_path, monkeypatch):
    """D-D11-5.1: the proof is the eye's verdict. Until it looks, the relief reads pending (None) in master.json,
    checks.json and golden-hour.json — never passed — and the relief's look is listed pending. A look (a stub at $0, on
    copies) is merged into all three: a defect reads False and is listed failed (the control), a verdict that holds
    reads True; a look on other crops than the mask's edge now reads stale (None); a look is never paid twice."""
    lid = _lid_copy(tmp_path, monkeypatch)
    record_path = tmp_path / 'golden-hour.json'
    assert gf.merge_relief_eye(lid, record_path)['state'] == 'pending'

    def read():
        master, checks, record = (_json(p) for p in (lid / 'master.json', lid / 'checks.json', record_path))
        assert checks == master['checks'] and checks['proofs']['relief_mask'] == master['finishes']['relief_mask']['holds']
        assert record['files']['lid'] == gf.tree_digest(lid)
        return master, checks, record
    master, checks, record = read()
    assert master['finishes']['relief_mask']['holds']['eye'] is None and not checks['checks_hold']
    assert 'relief_mask.eye' in checks['proofs_not_measured'] and 'relief_mask.eye' in record['checks']['proofs_not_measured']
    assert 'relief_mask.eye' not in record['checks']['proofs_failed']
    assert 'relief_mask.eye is not measured (pending, or holding only by construction)' in checks['issues']
    assert any('gh_relief_eye_run.py' in p['runner'] for p in record['pending'])

    calls = []
    gf.relief_look(lid, _eye_stub('defect', calls))                  # the control: a defect is never read as held
    master, checks, record = read()
    assert master['finishes']['relief_mask']['holds']['eye'] is False and record['fixes']['1 emboss the bars']['eye']['state'] == 'looked'
    assert 'relief_mask.eye' in record['checks']['proofs_failed'] and 'relief_mask.eye does not hold' in checks['issues']
    assert not any('gh_relief_eye_run.py' in p['runner'] for p in record['pending'])
    gf.relief_look(lid, _eye_stub('holds', calls))                   # read back: never paid twice
    assert calls == ['relief-edge'] and _json(lid / 'master.json')['finishes']['relief_mask']['holds']['eye'] is False

    (lid / 'relief-eye.json').unlink()
    gf.relief_look(lid, _eye_stub('holds', calls))
    master, checks, record = read()
    assert master['finishes']['relief_mask']['holds']['eye'] is True and 'relief_mask.eye' not in record['checks']['proofs_failed']
    assert 'relief_mask.eye' not in checks['proofs_not_measured']
    assert set(checks['proofs_not_measured']) == {'relief_mask.capped_outer_edges', 'relief_mask.bar_ends'}

    look = _json(lid / 'relief-eye.json')                           # a look on other crops: stale, its verdict not this mask's
    look['sent'][0]['sha256'] = '0' * 64
    (lid / 'relief-eye.json').write_text(json.dumps(look))
    assert gf.merge_relief_eye(lid, record_path)['state'] == 'stale'
    assert _json(lid / 'master.json')['finishes']['relief_mask']['holds']['eye'] is None


@lid_here
@day10_here
def test_the_eyes_prompt_and_the_masters_facts_state_where_the_outline_is_not_the_isoline():
    """The review of Day 11: on bar 1's top and bar 5's foot the outline is the edge line plus 0.25 mm on most stations,
    and the eye was told "the 50 % isoline" everywhere. Both texts now say which edges, on how many stations, and what
    the outline is there, from the record. The control: a record with no capped station says no cap (the words come
    from the record), and Day 10's facts say no relief."""
    master = _json(GH / 'lid' / 'master.json')
    relief = master['finishes']['relief_mask']
    capped = {(b['bar'], side): (n, b['stations']) for b in relief['bars'] for side, n in b['stations_stopped_by_side'].items() if n}
    assert set(capped) == {(1, 'upper'), (5, 'lower')}
    for text in (gf.relief_look_text(relief['outline_said']), lm.master_facts(master)):
        assert 'bar 1\'s top edge' in text and 'bar 5\'s bottom edge' in text and 'NOT the isoline' in text
        assert 'plus 0.25 mm' in text and '50 % isoline' in text
        for n, of in capped.values():
            assert '%d of its %d stations' % (n, of) in text
    # the whole-lid look reads D-D10-2's list, whose item 5 allows relief only where A-2's spec declared it: the facts
    # say the emboss is the owner's override (D-D11-5.1), so the eye judges its outline, not its presence
    facts = lm.master_facts(master)
    assert 'override of item 5' in facts and 'D-D11-5.1' in facts and 'Relief only where' in lm.allowed_differences()
    uncapped = [dict(b, stations_stopped_by_side={k: 0 for k in b['stations_stopped_by_side']}) for b in relief['bars']]
    assert 'NOT the isoline' not in gf.outline_said(uncapped) and '50 % isoline' in gf.outline_said(uncapped)
    day10 = lm.master_facts(_json(DAY10 / 'lid' / 'master.json'))
    assert 'No relief.' in day10 and 'isoline' not in day10


@lid_here
def test_the_embosss_margin_is_measured_from_the_file_and_reported_beside_the_safe_area():
    """The review of Day 11: the emboss enters the 4 mm safe margin and nothing said so. D-D10-2.6 names the copy lines
    and the logo (the emboss is the picture's bars, not moved): the relief's nearest trim is measured, recorded in
    master.json and checks.json, and said. Read from the file's EMBOSS plate. The control: a relief 5 mm inside every
    trim reads inside."""
    from apps.pipeline.services import finish_proof as fp
    master = _json(GH / 'lid' / 'master.json')
    margin = master['finishes']['relief_mask']['safe_margin']
    assert _json(GH / 'lid' / 'checks.json')['relief_safe_margin'] == margin
    k = lm.PX_PER_MM_SRC * gf.RELIEF_SCALE
    plate = [p for p in fp.plate_masks(GH / 'lid' / 'engine' / 'lid-engine.ai', px_per_mm=k)
             if p['plate'] == lm.RELIEF_PLATE][0]['mask']
    rows, cols = np.nonzero(plate)
    h, w = plate.shape
    from_file = min(rows.min() / k, cols.min() / k, (w - 1 - cols.max()) / k, (h - 1 - rows.max()) / k)
    assert margin['nearest_trim_mm'] == pytest.approx(from_file, abs=0.05) and margin['side'] == 'top'
    assert margin['inside_safe'] is False and 'enters the 4 mm safe margin' in margin['said']
    assert 'relief' not in {r['element'] for r in master['safe_area']}            # the copy lines' check unchanged
    assert lm.relief_safe_margin([5.0, 5.0, 100.0, 100.0])['inside_safe'] is True


def test_the_box_names_its_sources_only_when_given():
    """The review of Day 11: Day 10's default box record gained a 'sources' key. Now None on the default path; the
    control: given sources are recorded."""
    from apps.pipeline.services import palette_box as pb
    assert pb.sources_record(False, lm.OUT, DAY10 / 'sticker', False) is None
    given = pb.sources_record(True, GH / 'lid', GH / 'sticker', True)
    assert given['lid'].endswith('golden-hour/lid') and 'page 3' in given['relief']


AREA_SERVICES = ('golden_hour_fixes', 'lid_master', 'palette_sticker', 'palette_open', 'palette_box', 'palette_board')


def numeric_defaults(source):
    """Every default argument that is a number — a literal, or a module-level name bound to one (the services' ban;
    the lint gate reads literals only)."""
    import ast
    tree = ast.parse(source)
    numeric = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
                value = value.operand
            if isinstance(value, ast.Constant) and type(value.value) in (int, float):
                numeric |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for d in list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]:
                if (isinstance(d, ast.Name) and d.id in numeric) or (isinstance(d, ast.Constant) and type(d.value) in (int, float)):
                    found.append(ast.unparse(d))
    return found


def test_no_numeric_default_argument_in_the_golden_hour_services():
    """The review of Day 11: ``make_picture(..., cap_usd=CAP_USD)`` was a numeric default the lint gate missed (a name,
    not a literal). None in the area's services; the control: that very signature is found."""
    from pathlib import Path
    services = Path(gf.__file__).parent
    for name in AREA_SERVICES:
        assert numeric_defaults((services / (name + '.py')).read_text()) == [], name
    planted = 'CAP_USD = 2.20\n\ndef make_picture(name, prompt, *, client, cap_usd=CAP_USD):\n    return cap_usd\n'
    assert numeric_defaults(planted) == ['CAP_USD']
    import inspect
    assert inspect.signature(po.make_picture).parameters['cap_usd'].default is None


@pick_here
@lid_here
def test_the_whole_lid_look_is_made_once_on_the_pinned_master(tmp_path, monkeypatch):
    """D-D11-5's "the eye once on its lid": ``lid_look`` runs ``lid_master.fidelity_look`` once (stubbed, $0, on
    copies) on the lid's own record, round 0, the master pinned first; a second call reads back (the control: the stub
    counts one look); a rebuilt master reads stale."""
    lid = _lid_copy(tmp_path, monkeypatch)
    seen = []

    def stub(out, rec, sketch, call, round_no):
        seen.append((out, round_no, rec['schema'], sorted(sketch)))
        assert (out / 'lid-eye.json').exists()                    # pinned before anything is paid
        return {'holds': True, 'answered': True, 'defects': []}
    monkeypatch.setattr(lm, 'fidelity_look', stub)
    assert gf.lid_look_state(lid)['state'] == 'pending'
    first = gf.lid_look(lid, call=None)
    second = gf.lid_look(lid, call=None)
    assert len(seen) == 1 and seen[0][:3] == (lid, 0, gf.SCHEMA) and seen[0][3] == sorted(lm.LINES)
    assert first == second and gf.lid_look_state(lid)['state'] == 'looked'
    (lid / 'finish-proof.png').write_bytes(b'another build')
    assert gf.lid_look_state(lid)['state'] == 'stale'


@lid_here
def test_golden_hour_json_lists_the_looks_still_to_be_paid():
    """The eye once on the lid and the eye on the relief's edge are listed pending in golden-hour.json while not made,
    each with its runner on disk; the record's proofs split into failed and not measured."""
    record = _json(GH / 'golden-hour.json')
    runners = {p['runner'] for p in record['pending']}
    for runner, state in (('gh_relief_eye_run.py', gf.relief_eye_state(GH / 'lid')),
                          ('gh_lid_eye_run.py', gf.lid_look_state(GH / 'lid'))):
        path = 'docs/audit/rescue_runtime/day11/' + runner
        assert (path in runners) == (state['state'] != 'looked')
        if (lm.REPO / 'docs' / 'audit' / 'rescue_runtime' / 'day11').exists():
            assert (lm.REPO / path).exists()
    assert record['checks'] == gf.checks_summary(_json(GH / 'lid' / 'checks.json'))
    assert record['fixes']['1 emboss the bars']['eye'] == _json(GH / 'lid' / 'master.json')['finishes']['relief_mask']['eye']
