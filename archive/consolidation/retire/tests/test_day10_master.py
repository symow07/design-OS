"""Day 10 §9 — the master of the owner's pick (§1), the back sticker (§3), the open palette (§2), the box (§4), the pick
page (§6) and the image guard re-rooted for Day 10.

The measuring functions are tested on synthetic inputs, each with a control that must fail; the day's records are read
where they are on this machine (skipped where they are not), and the cheap proofs are re-run on the real pick."""
import json
import shutil

import numpy as np
import pytest

from apps.pipeline.services import lid_master as lm

DAY10 = lm.REPO / 'docs' / 'audit' / 'day-10'
records = pytest.mark.skipif(not (DAY10 / 'lid' / 'master.json').exists(), reason='the Day 10 records are not here')
pick_here = pytest.mark.skipif(not lm.PICK.exists(), reason='the owner\'s pick is not on this machine')


def _record(rel):
    return json.loads((DAY10 / rel).read_text(encoding='utf-8'))


# --- colour and similarity -------------------------------------------------------------------------------------------

def test_ssim_is_one_on_itself_and_falls_under_noise():
    rng = np.random.default_rng(10)
    img = rng.integers(0, 256, (64, 80)).astype(np.float64)
    assert lm.ssim(img, img) == pytest.approx(1.0)
    noisy = np.clip(img + rng.normal(0, 40, img.shape), 0, 255)
    assert lm.ssim(img, noisy) < 0.9


def test_poisson_fill_keeps_the_boundary_and_takes_the_guides_texture():
    """Inside the mask the result carries the guide's Laplacian; outside it the image is untouched."""
    rng = np.random.default_rng(3)
    image = np.full((40, 40, 3), 100.0)
    guide = image + rng.normal(0, 5, image.shape)
    mask = np.zeros((40, 40), dtype=bool)
    mask[10:30, 12:28] = True
    out = lm.poisson_fill(image, guide, mask)
    assert np.array_equal(out[~mask], image[~mask])
    inner = out[12:28, 14:26] - out[12:28, 14:26].mean(axis=(0, 1))
    assert inner.std() > 2.0                                   # the guide's texture, not a flat fill
    assert abs(out[mask].mean() - 100.0) < 3.0                 # at the boundary's own level


# --- §1: the upscale ---------------------------------------------------------------------------------------------------

@pick_here
def test_the_upscale_proof_on_the_pick_as_recorded():
    """D-D10-2.1's global proof re-run on the pick: mean ΔE00 under 1 and SSIM over 0.97 hold; the max does not (it is
    reported, never moved), all of its pixels on the lettering, the bars and the name."""
    pick = lm.load_pick(lm.PICK)
    proof = lm.prove_upscale(pick, lm.upscale(pick), lm.REGIONS)
    assert proof['de00_mean'] < 1.0 and proof['ssim'] > 0.97
    assert proof['de00_max'] > 4.0 and proof['pixels_over_max_where']['elsewhere'] == 0
    if (DAY10 / 'lid' / 'master.json').exists():
        rec = _record('lid/master.json')['upscale']
        assert (rec['de00_mean'], rec['de00_max'], rec['ssim']) == (proof['de00_mean'], proof['de00_max'], proof['ssim'])


def test_the_pick_is_refused_unless_it_is_the_pick(tmp_path):
    other = tmp_path / 'lid.png'
    from PIL import Image
    Image.new('RGB', lm.PICK_PX, (10, 20, 30)).save(other)
    with pytest.raises(ValueError, match='not the owner'):
        lm.load_pick(other)


def test_bleed_mirrors_the_edges_and_moves_nothing_inside_the_trim():
    rng = np.random.default_rng(7)
    plate = rng.integers(0, 256, (120, 190, 3)).astype(np.uint8)
    out = lm.bleed(plate)
    b = lm.bleed_px()
    assert np.array_equal(out[b:-b, b:-b], plate)
    assert np.array_equal(out[b - 1, b:-b], plate[1])          # the band is the picture's own edge, mirrored
    assert np.array_equal(out[b:-b, b - 1], plate[:, 1])


@records
def test_the_eyes_one_to_one_verdict_on_the_upscale_is_recorded():
    """§9: the eye's 1 : 1 verdict on the upscale — after repair 2, no invented structure, allowed by item 1."""
    r2 = _record('lid/fidelity-r2.json')['upscale']['payload']
    assert r2['verdict'] == 'allowed' and r2['allowed_by'] == '1' and not r2['invented_structure']
    assert r2['in_the_picks_own_pixels']
    verdict = _record('lid/fidelity.json')['verdict']
    assert verdict['holds'] and verdict['repairs_used'] <= 2


@records
def test_the_eye_read_the_traced_name_itself_and_the_crops_it_was_shown_carry_the_trace():
    """The review of Day 10: rounds 0 and 1 showed the eye the plate's raster name. The re-look's pieces change the
    name from the pick (the trace drawn) and the eye reads each as the same letters, placed, nothing invented."""
    relook = _record('lid/fidelity-name-relook.json')
    assert relook['answered'] and relook['holds']
    sent = relook['name']['sent']
    assert len(sent) == 4 and all(i['changed_from_the_pick_inside_the_name'] > 0.05 for i in sent)
    for crop in relook['name']['payload']['crops']:
        assert crop['same_letters'] and crop['placed_as_the_pick'] and not crop['invented_structure']
        assert crop['verdict'] == 'allowed' and crop['allowed_by'] == '3'
    assert _record('lid/fidelity.json')['verdict']['name_relook_holds']


# --- §1: placement, the trace, the logo, the masks ---------------------------------------------------------------------

def _unit(x0, y0, x1, y1):
    return {'box_mm': (x0, y0, x1, y1)}


def test_overlay_proof_holds_within_a_millimetre_and_refuses_beyond():
    sketch = [_unit(10.0 + 3 * i, 50.0, 12.0 + 3 * i, 53.0) for i in range(6)]
    near = [_unit(u['box_mm'][0] + 0.3, 50.1, u['box_mm'][2] + 0.3, 53.1) for u in sketch]
    far = [_unit(u['box_mm'][0] + 1.2, 50.0, u['box_mm'][2] + 1.2, 53.0) for u in sketch]
    big = [_unit(u['box_mm'][0], 49.8, u['box_mm'][2], 53.2) for u in sketch]
    assert lm.overlay_proof(sketch, near)['holds']
    assert not lm.overlay_proof(sketch, far)['holds']
    assert not lm.overlay_proof(sketch, big)['holds']          # 3.4 / 3.0: over 3 %
    assert not lm.overlay_proof(sketch, near[:-1])['holds']


@records
def test_every_small_line_is_placed_within_a_millimetre_and_three_percent():
    overlay = _record('lid/master.json')['type']['overlay']
    assert set(overlay) == set(lm.LINES)
    for key, row in overlay.items():
        assert row['holds'], key
        assert row['worst_glyph_shift_mm'] <= 1.0 and abs(row['line_size_ratio'] - 1) <= 0.03


@pick_here
def test_the_name_trace_overlays_the_sketch_within_three_tenths_and_a_shifted_trace_does_not():
    pick = lm.load_pick(lm.PICK)
    rings, _, proof = lm.trace_name(pick, lm.NAME_BOX)
    assert proof['holds']['within_0_3_mm'] and proof['holds']['iou_0_95'] and proof['letters'] == 13
    own = lm.prove_outline_on_pick(pick, rings)
    assert own['holds'] and own['max_mm'] <= 0.3
    shifted = lm.map_rings(rings, lambda p: (p[0] + 0.45, p[1]))
    assert not lm.prove_outline_on_pick(pick, shifted)['holds']     # the control: the proof has power


@records
def test_the_logo_is_placed_by_position_and_size_and_its_letters_alone_are_foil():
    logo = _record('lid/master.json')['logo']
    assert logo['holds']['within_1_mm'] and logo['holds']['within_3_pct']
    # read on every edge and the centre, not the top-left corner alone (the right edge is the worst)
    assert logo['worst_shift_mm'] == max(logo['edge_shift_mm'].values()) <= 1.0
    assert logo['worst_shift_mm'] > logo['corner_shift_mm']
    foil = _record('lid/master.json')['finishes']
    assert foil['foil_limits']['holds'] and 'B B R S E' in foil['foil']


@records
def test_the_finishes_are_separated_not_redrawn():
    """Foil only on crisp gold (the name crisp); the bars' long edges and the lettering read by ONE operator, every
    bar read on three of its five profiles or more, the ends fading over 10 mm or more; the engraving's gaps at the
    foil limit; no relief, its reason said from the readings (not "soft"); the crisp specks left in the raster said
    from their own readings."""
    fin = _record('lid/master.json')['finishes']
    assert fin['crisp_gold']['by_region']['name']['crisp_shapes'] >= 10
    bars = fin['bars']
    assert bars['floor_mm'] <= min(bars['lettering_rise_mm'].values())
    assert all(b['long_edges_read'] >= 3 and min(b['end_fade_mm']) > 10 for b in bars['bars'])
    assert fin['engraving']['gap_mm_median'] < lm.FOIL_GAP_MIN_MM
    assert fin['coverage']['relief_pct'] == 0.0
    assert 'soft' not in fin['relief'].replace('not soft', '') and 'owner' in fin['relief']
    specks = fin['crisp_gold_left_as_raster']
    assert fin['crisp_gold_left_as_raster']['said'] == lm.said_specks(specks['specks'])
    assert all(r['widest_line_mm'] > lm.FOIL_LINE_MIN_MM for r in specks['specks'])


def test_one_edge_operator_tells_a_sharp_edge_from_a_soft_one():
    """The bars' operator has power: a step reads its floor, a 2 mm ramp reads far over it."""
    from scipy.ndimage import uniform_filter1d
    box = int(round(lm.ENGRAVING_PITCH_PX / 0.25))
    sharp = uniform_filter1d(np.r_[np.zeros(200), np.full(200, 40.0)], box, mode='nearest')
    ramp_px = int(2.0 * lm.PX_PER_MM_SRC / 0.25)
    soft = uniform_filter1d(np.r_[np.zeros(200), np.linspace(0, 40, ramp_px), np.full(200, 40.0)], box, mode='nearest')
    rise_sharp = lm._monotone_rise(sharp, int(np.argmax(np.abs(np.diff(sharp)))), 0.25)
    rise_soft = lm._monotone_rise(soft, int(np.argmax(np.abs(np.diff(soft)))), 0.25)
    assert rise_sharp / lm.PX_PER_MM_SRC < 0.35 and rise_soft / lm.PX_PER_MM_SRC > 1.0

def test_the_crisp_gold_search_tells_a_sharp_letter_from_a_soft_glow():
    img = np.full((80, 160, 3), (20, 30, 50), dtype=np.uint8)
    img[20:60, 20:40] = (200, 150, 80)                         # a sharp gold block
    yy, xx = np.mgrid[0:80, 0:160]
    glow = np.exp(-(((xx - 115) / 18.0) ** 2 + ((yy - 40) / 14.0) ** 2))[..., None]
    img = (img * (1 - glow * (xx[..., None] > 80)) + np.array([215, 170, 95]) * glow * (xx[..., None] > 80)).astype(np.uint8)
    rec, mask = lm.crisp_gold(img, {'sharp': (0, 0, 80, 80), 'soft': (80, 0, 160, 80)})
    assert rec['by_region']['sharp']['crisp_shapes'] == 1
    assert rec['by_region']['soft']['shapes'] >= 1 and rec['by_region']['soft']['crisp_shapes'] == 0


@records
def test_the_word_spaces_kept_and_every_check_but_the_upscale_max_holds():
    rec = _record('lid/master.json')
    for moved in rec['type']['word_spaces_kept']:
        assert abs(moved['by_mm']) < 1.0
    checks = _record('lid/checks.json')
    assert lm.failed_proofs(checks['proofs'], '') == ['upscale.de00_max']
    assert len(checks['issues']) == 1 and 'upscale' in checks['issues'][0]
    assert all(c['found'] for c in checks['copy'].values())
    sizes = checks['sizes']
    assert sizes['name_cap_holds'] and sizes['sign_holds'] and sizes['smallest_holds'] and sizes['alif_holds']
    assert sizes['page_mm'] == [196.0, 126.0] and sizes['trim_mm'] == [190.0, 120.0]


def test_every_proof_that_fails_is_an_issue():
    """The control: a proof deep in the record that reads False is found by its path (the review of Day 10: seven
    proofs were recorded and never read into the issues)."""
    proofs = {'upscale': {'de00_mean': True, 'de00_max': False}, 'name_trace': {'within_0_3_mm': True, 'iou_0_95': False},
              'logo_placed': {'within_1_mm': True}, 'safe_area': False, 'foil_limits': True}
    assert lm.failed_proofs(proofs, '') == ['upscale.de00_max', 'name_trace.iou_0_95', 'safe_area']
    assert lm.failed_proofs({'a': True, 'b': {'c': True}}, '') == []


@records
def test_every_element_is_inside_the_safe_area_so_the_bleed_holds_none():
    assert all(row['inside_safe'] for row in _record('lid/master.json')['safe_area'])


@records
def test_the_print_files_carry_their_fonts_and_the_layers_read_back():
    pre = _record('lid/preflight.json')
    assert pre['fonts_that_draw_embedded'] and pre['foil_masks_within_limits'] and pre['bleed_present']
    assert not pre['cmyk_conversion_applied']
    assert pre['colour_space']['holds'] and pre['colour_space']['picture'][0]['n'] == 3
    assert all(f['embedded'] for f in pre['fonts'].values() if f['draws'])
    back = _record('lid/master.json')['ai_read_back']
    assert [r['layer'] for r in back['layers']] == ['picture', 'type', 'name', 'logo', 'foil', 'relief', 'guides']
    assert back['empty_layers'] == ['relief'] and back['shown_artwork_vs_engine_page']['holds']
    assert back['holds'] and all(back['words_carried'].values())
    assert {r['element'] for r in back['by_element']} == set(lm.LINES) | {'name', 'logo'}
    assert all(r['holds'] for r in back['by_element'])


def _media_rows_each_line_in_its_own_face(media, faces):
    by_element = {e['element']: e['medium'] for e in media['elements']}
    return {key: key_copy in by_element and faces[key]['label'] in by_element[key_copy]
            for key, key_copy in ((k, lm.LINES[k]['copy']) for k in lm.LINES)}


@records
def test_the_media_map_names_each_small_line_in_its_own_face():
    """The review of Day 10: the media map pooled EYESHADOW PALETTE and 18 SHADES under one face, though 18 SHADES is
    set in Tajawal Medium. Each line has its own row naming the face it is set in (master.json); the control, the map
    as it was first written (a6c9322), is refused."""
    faces = _record('lid/master.json')['type']['faces']
    assert all(_media_rows_each_line_in_its_own_face(_record('lid/media-map.json'), faces).values())
    as_it_was = {'elements': [{'element': 'EYESHADOW PALETTE, 18 SHADES', 'medium': 'live text, DMSans-Medium, embedded'},
                              {'element': '27 g 0.95 oz', 'medium': 'live text, Nunito-Medium, embedded'},
                              {'element': 'the Arabic line', 'medium': 'live text, TajawalPF-Medium, embedded'}]}
    assert not any(_media_rows_each_line_in_its_own_face(as_it_was, faces).values())


@records
def test_the_print_file_carries_the_artwork_whole_on_its_first_page():
    """lid-master.pdf page 1 is the composite (the picture, the type and the logo; the review of Day 10: no page
    carried them together), then the foil plate, the relief plate and the guides."""
    import fitz
    with fitz.open(str(DAY10 / 'lid' / 'lid-master.pdf')) as pdf:
        assert pdf.page_count == 4
        first = pdf[0]
        assert first.get_images() and {f[3].split('+')[-1] for f in first.get_fonts()} >= {'DMSans-Medium', 'Nunito-Medium'}
    assert {'Eyeshadow', 'Palette', '18', 'shades', 'باليت ظلال العيون'} <= set(lm.actual_texts(DAY10 / 'lid' / 'lid-master.pdf', 0))


def test_the_read_back_sees_one_small_line_missing():
    """The control: a line present (drawn a pixel off, as a form anti-aliases it) reads back; the same line missing
    does not, though it is far under 1 % of a page."""
    picture = np.full((300, 600, 3), (30, 40, 60), dtype=np.uint8)
    master = picture.copy()
    master[100:112, 50:400] = (241, 217, 199)
    shifted = np.roll(master, 1, axis=1)
    box = {'line': tuple(v * lm.MM_PER_INCH / 300.0 for v in (50, 100, 400, 112))}
    assert lm.element_read_back(master, shifted, picture, box, 300.0)[0]['holds']
    assert not lm.element_read_back(master, picture, picture, box, 300.0)[0]['holds']


# --- §3: the sticker -----------------------------------------------------------------------------------------------------

@records
def test_the_sticker_shrinks_nothing_under_five_points_drops_nothing_and_keeps_the_copy():
    fit = _record('sticker/fit-report.json')
    assert fit['smallest_pt'] >= 5.0 and fit['dropped'] == [] and fit['moved'] == []
    assert all(line['fits'] for line in fit['lines'])
    copy = fit['copy']
    assert copy['all_found'] and copy['inci_in_every_language'] and copy['net_in_every_language']
    assert fit['dropped'] == copy['dropped'] and fit['moved'] == copy['moved']
    assert {r['lang'] for r in fit['for_review']} == {'es', 'ar'}
    assert {r['lang'] for r in fit['for_review'] if r['field'] == 'claims'} == {'es', 'ar'}


@records
def test_the_stickers_arabic_claims_are_the_houses_and_add_no_claim():
    """The review of Day 10: the machine draft added طبياً ("medically") to "Dermatologist tested". The Arabic claims
    printed are the house's on record (harakat out), and every translated claim is for review."""
    from apps.pipeline.services import palette_sticker as ps
    blocks = ps.copy(json.loads(ps.TRANSLATIONS.read_text(encoding='utf-8')))
    claims = {r['field']: r for r in blocks['ar']}['claims']
    assert claims['text'] == ' · '.join(ps.HARAKAT.sub('', c) for c in ps.HOUSE_CLAIMS_AR)
    assert 'طبيا' not in claims['text'] and claims['regulated'] and not claims['verbatim']
    drawn = ' '.join(r['text'] for r in _record('sticker/fit-report.json')['lines']
                     if r['lang'] == 'ar' and r['field'] == 'claims')
    assert 'طبيا' not in drawn and 'ثبات طويل' in drawn


@records
def test_the_stickers_copy_is_word_for_word_in_all_three_languages_from_the_file_itself():
    from apps.pipeline.services import palette_sticker as ps
    blocks = ps.copy(json.loads(ps.TRANSLATIONS.read_text(encoding='utf-8')))
    names = _record('sticker/fit-report.json')['copy']['span_names']
    check = ps.copy_check(DAY10 / 'sticker' / 'engine' / 'sticker-engine.ai', blocks, names)
    assert check['all_found'] and check['inci_in_every_language'] and check['net_in_every_language']
    assert check['dropped'] == [] and check['moved'] == []
    english = {r['field']: r['text'] for r in blocks['en']}
    assert english['ingredients'] == ps.INCI and english['description'] == ps.ENGLISH['description']
    for lang in ('es', 'ar'):
        assert {r['field']: r['text'] for r in blocks[lang]}['ingredients'] == ps.INCI
        assert all(not ps.HARAKAT.search(r['text']) for r in blocks[lang])


def test_the_sticker_copy_check_fails_on_a_dropped_word(tmp_path, monkeypatch):
    """The control: the word-for-word check has power (a section missing a word is not found, the whole one is)."""
    from apps.pipeline.services import palette_sticker as ps
    blocks = {'en': [{'field': 'warnings', 'head': 'Warnings', 'text': 'For external use only.', 'verbatim': True}]}
    names = ['en:warnings', 'en:warnings']
    monkeypatch.setattr(ps.lm, 'actual_texts', lambda pdf, page: ['Warnings:', 'For external use'])
    assert not ps.copy_check(tmp_path / 'x.ai', blocks, names)['all_found']
    monkeypatch.setattr(ps.lm, 'actual_texts', lambda pdf, page: ['Warnings:', 'For external use only.'])
    assert ps.copy_check(tmp_path / 'x.ai', blocks, names)['all_found']


@records
@pytest.mark.parametrize('lang, field, which', [
    ('es', 'ingredients', 'all'), ('ar', 'net', 'all'), ('es', 'shades', 'all'), ('es', 'ingredients', 'first'),
    ('ar', 'ingredients', 'first'), ('en', 'ingredients', 'first')])
def test_one_column_cannot_stand_for_another(monkeypatch, lang, field, which):
    """The controls (the review of Day 10): on the real file's spans, dropping one language's INCI, its ℮ line, the
    Spanish "18 tonos" or an ingredients head is seen — though the same words stand in the other columns."""
    from apps.pipeline.services import palette_sticker as ps
    blocks = ps.copy(json.loads(ps.TRANSLATIONS.read_text(encoding='utf-8')))
    names = _record('sticker/fit-report.json')['copy']['span_names']
    spans = lm.actual_texts(DAY10 / 'sticker' / 'engine' / 'sticker-engine.ai', 0)
    hit = [i for i, n in enumerate(names) if n.split(':')[:2] == [lang, field]]
    if which == 'first':
        hit = hit[:1]                       # the head opens the section's first span
    kept = [i for i in range(len(spans)) if i not in hit]
    monkeypatch.setattr(ps.lm, 'actual_texts', lambda pdf, page: [spans[i] for i in kept])
    check = ps.copy_check(DAY10 / 'sticker' / 'engine' / 'sticker-engine.ai', blocks, [names[i] for i in kept])
    assert not check['all_found']
    assert not [r for r in check['rows'] if (r['lang'], r['field']) == (lang, field)][0]['found']


# --- §2 and §4: the tray and the box -------------------------------------------------------------------------------------

@records
def test_every_pan_has_a_colour_and_a_finish_from_the_picture():
    pans = _record('tray/pans.json')
    assert len(pans['pans']) == 18 and {p['source'] for p in pans['pans']} == {'the tray picture'}
    assert all(p['finish'] in ('matte', 'shimmer', 'glitter') and len(p['hex']) == 7 for p in pans['pans'])
    assert pans['artwork']['names_word_for_word']
    assert pans['names']['pt'] == pans['artwork']['record']['name_pt']


@records
def test_the_tray_cut_carries_the_insert_and_the_case_is_measured_against_every_pan():
    """The review of Day 10: the cut held only the wells and the case colour's reason was a fixed sentence."""
    from apps.pipeline.services import palette_open as po
    pans = _record('tray/pans.json')
    art = pans['artwork']
    assert art['cut']['insert_outline'] and art['cut']['paths'] == 19
    assert art['print_trim_mm'] == [3.0, 3.0, 187.0, 117.0]
    against = pans['case']['pans_against_it']
    assert len(against) == 18
    low = [a['name'] for a in against if a['de00'] < po.CASE_DE_FLOOR]
    assert all(a['reads_into_the_case'] == (a['name'] in low) for a in against)
    assert all(name in pans['case']['why'] and name in pans['flagged'] for name in low)


@records
def test_the_box_fold_check():
    box = _record('box/box-fold-check.json')
    assert box['fold_check']['passed'] and box['die_untouched']['holds']
    assert box['all_inside_safe'] and box['nothing_across_a_crease'] and box['notch_clear']
    # the non-printing parts measured, not said (the review of Day 10: ~34 mm² of ground on three dust flaps)
    assert box['clean']['holds'] and len(box['clean']['parts']) >= 7


@records
def test_the_boxs_long_sides_carry_the_briefs_arabic_name():
    from apps.pipeline.services import palette_sticker as ps
    words = lm.actual_texts(DAY10 / 'box' / 'engine' / 'side-band.ai', 0)
    assert ps.NAME_AR in words and lm.LINES['descriptor_ar']['copy'] not in words


# --- the image guard and the call log ------------------------------------------------------------------------------------

def test_the_guard_allows_the_pick_only_as_itself(tmp_path, settings):
    from apps.pipeline.services import round_calls as ig
    settings.IMAGE_MODEL = 'gpt-image-2'
    path, sha = ig.APPROVED_PICK
    if not path.exists():
        pytest.skip('the owner\'s pick is not on this machine')
    deny = {'rejected': {sha: 'the pick under Day 9\'s rejected root'}, 'web': {}}
    checked = ig.check([{'role': 'the owner\'s pick', 'path': path}], 'the open tray', deny=deny)
    assert checked[0]['sha256'] == sha
    copy = tmp_path / 'lid.png'
    shutil.copyfile(path, copy)
    with pytest.raises(ig.ImageCallRefused):
        ig.check([{'role': 'the owner\'s pick', 'path': copy}], 'the open tray', deny=deny)
    assert ig._is_approved_logo({'path': str(path), 'sha256': sha})
    assert not ig._is_approved_logo({'path': str(copy), 'sha256': sha})


@records
def test_the_day10_image_call_log_audits_clean_with_only_the_pick_and_the_logo_sent(monkeypatch):
    """[Day 11] the guard moved on to Day 11's log under 'day11/': Day 10's closed log is audited under Day 10's own
    prefix, its one pick (A-2.3) and the logo the only inputs."""
    from apps.pipeline.services import round_calls as ig
    log = DAY10 / 'image-calls.jsonl'
    monkeypatch.setattr(ig, 'TODAY_OPERATION_PREFIX', 'day10/')
    audit = ig.audit(log)
    assert audit['log_present'] and not audit['log_empty'] and audit['holds'], audit
    rows = [json.loads(l) for l in log.read_text(encoding='utf-8').split('\n') if l.strip()]
    allowed = {ig.APPROVED_PICK[1], ig.APPROVED_LOGO[1]}
    assert all(r['operation'].startswith('day10/') for r in rows)
    assert all({i['sha256'] for i in r['inputs']} == allowed for r in rows if r['outcome'] == 'made')


# --- §6: the pick page ---------------------------------------------------------------------------------------------------


