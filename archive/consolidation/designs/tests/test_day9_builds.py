"""Day 9 §4–§8 — the builds: the shared build core (rich_concept), the recipes of the six chosen sketches (day9_recipes),
the foil trap, and the image-call log's audit. DB-free; $0 (every image-model and vision call is a fake)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from apps.pipeline.services import day9_pick, day9_recipes as recipes, image_guard as ig, rich_concept as rc

CHOSEN = ('A-2.3', 'A-2.2', 'B-1.3', 'B-2.2', 'C-2.2', 'C-1.1')


@pytest.fixture
def mark_on(settings):
    """The approved mark looked up on file (the suite turns the lookup off by default), or skip on another machine."""
    settings.BRAND_MARK_APPROVAL_LOOKUP = True
    from apps.ire import brand_mark
    if brand_mark.approved_master()['master'] is None:
        pytest.skip('the approved mark is not on this machine')
    return True


def _toy_ornament(*, x0, y0, x1, y1, pitch_mm, line_mm):
    marks, y = [], y0
    while y <= y1:
        marks.append({'points': [(x0, y), (x1, y)], 'closed': False, 'width': line_mm, 'ink': 'gold_foil', 'fill': None, 'finishes': ['foil']})
        y += pitch_mm
    block = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    lid = [(0, 0), (190, 0), (190, 120), (0, 120)]
    return {'kind': 'toy', 'marks': marks, 'regions': {'paint': [lid], 'relief': [block], 'footprint': [block]}, 'params': {}, 'measures': {}}


def _toy_recipe(**name_over):
    name = {'face': 'Gloock-Regular', 'cap_mm': 8.0, 'ops': {'Enchanted Rose': []}, 'lines': ['Enchanted Rose'], 'ink': 'rose_gold_foil',
            'emboss': True, 'zone': 'name', 'align': 'left', 'upper': False, 'leading': 1.2, 'descent_mm': 0.6, 'draw': True}
    name.update(name_over)
    return {'idea': 'B-2', 'ornament': _toy_ornament,
            'ornament_params': {'x0': 40.0, 'y0': 45.0, 'x1': 110.0, 'y1': 70.0, 'pitch_mm': 0.4, 'line_mm': 0.12},
            'plate_path': 'b', 'plate_prompt': 'black lacquer', 'ground_hex': '#0B0A0E',
            'guide': lambda lay: np.full((rc.LID_PX[1], rc.LID_PX[0], 3), 11, np.uint8),
            'name': name,
            'arabic': {'in_ornament': False, 'outlined': False, 'stem': 'ElMessiriPF-Bold', 'alif_mm': 6.6, 'ink': 'gold_foil',
                       'zone': 'descriptor_ar', 'align': 'left', 'emboss': False},
            'support': {'stem': 'Jost[wght]@400', 'cap_mm': 3.0, 'tracking_em': 0.14, 'align': {'descriptor_en': 'left', 'shades': 'left', 'net': 'right'},
                        'colour': {'descriptor_en': '#EDE6EC', 'shades': '#EDE6EC', 'net': '#EDE6EC'}},
            'logo': {'zone': 'logo', 'ink': 'ink:#EDE6EC'}, 'ink_hex': recipes.INK_HEX, 'foil_plates': recipes.FOIL_PLATES}


DAY9_CALL_LOG = ig.REPO / 'docs' / 'audit' / 'day-9' / 'image-calls.jsonl'


def test_the_day9_image_call_log_audits_clean(monkeypatch):
    """§8: every Day 9 image call is gpt-image-2 through the guard, sent its inputs with their sha256, carried no rejected
    design and no web picture (the approved logo exempt only as itself), and named no competitor. [Day 10] the guard now
    roots Day 10 (Day 9's pictures rejected, the pick apart): Day 9's closed log is audited under Day 9's own roots."""
    monkeypatch.setattr(ig, 'REJECTED_ROOTS', tuple(r for r in ig.REJECTED_ROOTS if r != ig.REPO / 'docs' / 'audit' / 'day-9'))
    monkeypatch.setattr(ig, 'TODAY_OPERATION_PREFIX', 'day9/')
    a = ig.audit(DAY9_CALL_LOG)
    assert a['log_present'] and not a['log_empty'] and a['holds'], a
    assert a['rejected_or_web_inputs'] == 0 and a['competitor_prompts'] == 0 and a['non_openai_or_named_tool'] == 0
    rows = [json.loads(l) for l in DAY9_CALL_LOG.read_text(encoding='utf-8').split('\n') if l.strip()]
    assert all(r['operation'].startswith('day9/') for r in rows)


def test_the_audit_exempts_the_approved_logo_by_path_and_sha_only(tmp_path, monkeypatch):
    """A copy of the logo's bytes anywhere else is still a rejected design to the audit; the approval's own raster is not."""
    logo_path, logo_sha = ig.APPROVED_LOGO
    copy = tmp_path / 'logo-copy.png'
    shutil.copyfile(logo_path, copy)
    monkeypatch.setattr(ig, 'denylist', lambda refresh=False: {'rejected': {logo_sha: 'a rejected copy'}, 'web': {}})

    def row(path):
        return {'operation': 'day9/sketches/x', 'provider': 'openai', 'model': 'gpt-image-2', 'outcome': 'made', 'prompt': 'a lid',
                'inputs': [{'role': 'logo', 'path': str(path), 'sha256': logo_sha}]}
    for path, holds in ((logo_path, True), (copy, False)):
        log = tmp_path / ('log-%s.jsonl' % holds)
        log.write_text(json.dumps(row(path)) + '\n', encoding='utf-8')
        assert ig.audit(log)['holds'] is holds


def test_a_toy_build_writes_every_file_the_pick_page_reads(tmp_path, mark_on):
    """The core end to end at $0: a fake edit (the guide back) and a fake eye; every BUILD_FILE but the verdict is written,
    build.json carries every key the pick page reads, the finish numbers come from the files, nothing reaches day-8."""
    recipe = _toy_recipe()

    def fake_edit(image_png, mask_png, prompt, style_ref):
        from PIL import Image
        with Image.open(image_png) as im:
            return np.asarray(im.convert('RGB')).copy()

    def fake_eye(sketch, proof, flat, spec_text):
        return {'payload': {'kept': '-', 'lost': '-', 'gained': '-', 'top_three_fixes': ['-'], 'reads_as_the_sketch': False}, 'cost_usd': 0.0}

    holder = {}
    holder['lay'] = rc.layout(rc.spec('B-2'), recipe, rc.sketch_record('B-2.2')['option']['choices'])
    rec = rc.build('TOY', idea='B-2', sketch_id='B-2.2', recipe=recipe, edit_fn=fake_edit, eye_fn=fake_eye,
                   ocr=__import__('apps.pipeline.services.concept_sketches', fromlist=['ocr_words']).ocr_words,
                   mark_matcher=lambda png: rc.find_mark(png, holder['lay'], tmp_path), repair_of=None, folder_root=tmp_path)
    folder = tmp_path / 'TOY'
    for name in day9_pick.BUILD_FILES:
        if name != 'jury/verdict.json':
            assert (folder / name).is_file(), name
    build = json.loads((folder / 'build.json').read_text())
    for key in ('schema', 'concept', 'idea', 'direction', 'idea_name', 'idea_line', 'sketch', 'plate_path', 'lettering', 'arabic',
                'checks_hold', 'cannot_meet', 'finish', 'repair_of'):
        assert key in build, key
    assert build['schema'] == day9_pick.BUILD_SCHEMA and rec['finish']['lines_per_cm_densest'] >= 12.0
    proof = json.loads((folder / 'proof-record' / 'record.json').read_text())
    assert rec['finish']['relief_pct'] == proof['coverage']['relief_pct']
    with pytest.raises(PermissionError):
        rc.build('X', idea='B-2', sketch_id='B-2.2', recipe=recipe, edit_fn=fake_edit, eye_fn=fake_eye, ocr=None, mark_matcher=None,
                 repair_of=None, folder_root=rc.DAY8 / 'concepts')


def test_a_line_that_does_not_fit_its_zone_is_refused_never_shrunk(mark_on):
    with pytest.raises(rc.LineDoesNotFit):
        rc.layout(rc.spec('B-2'), _toy_recipe(cap_mm=14.0), rc.sketch_record('B-2.2')['option']['choices'])


def test_a_recipe_that_does_not_say_what_a_build_needs_is_refused():
    recipe = _toy_recipe()
    recipe.pop('guide')
    with pytest.raises(rc.RecipeRefused):
        rc.check_recipe(recipe)


def test_the_foil_trap_closes_the_gaps_a_serif_leaves_under_the_foil_limit(tmp_path):
    """Cormorant Garamond Italic's ascender notches close under 0.2 mm (measured: five parts, 0.27 mm²); trapped to the
    foil's gap they hold, and the trap adds only what the press would have filled."""
    from apps.ire import lettering
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Finish, Group, Rect, SolidFill
    from apps.pipeline.services import finish_proof
    foil = [Finish(kind='foil', plate='FOIL_ROSE_GOLD', appearance=Color.from_hex('#C99A84'))]
    group, _rec = lettering.logotype('Enchanted Rose', 'CormorantGaramond-Italic[wght]@600', [], cap_mm=9.0, x_mm=10, top_mm=20,
                                     colour='#C99A84', finishes=foil)
    trapped, trap = rc.foil_trapped(group, gap_mm=0.2)
    held = {}
    for tag, g in (('raw', group), ('trapped', trapped)):
        doc = Document(page_w=190, page_h=120, title='t', root=Group(name='root', role='artwork', children=[
            Group(name='G', role='background', children=[Rect(name='g', x=0, y=0, w=190, h=120, fill=SolidFill(color=Color.from_hex('#22205A')))]), g]))
        ai = tmp_path / f'{tag}.ai'
        emit_pdf_ai(doc, str(ai))
        held[tag] = finish_proof.foil_limits(ai)['holds']
    assert held == {'raw': False, 'trapped': True}
    assert 0.0 < trap['area_added_mm2'] < 1.0


@pytest.mark.parametrize('sid', CHOSEN)
def test_every_chosen_build_lays_out_from_its_recipe_at_no_cost(sid, mark_on):
    idea = sid.rsplit('.', 1)[0]
    choices = rc.sketch_record(sid)['option']['choices']
    recipe = recipes.recipe(idea, choices, sid)
    lay = rc.layout(rc.spec(idea), recipe, choices)
    assert lay['ornament']['marks'] and lay['name'] and set(lay['lines']) >= {'descriptor_en', 'shades', 'net'}
    assert recipe['logo']['ink'].startswith('ink:'), 'the logo is printed in ink: the approved mark cannot hold the foil gap'
    roles = {m['ink'] for m in lay['ornament']['marks']}
    assert not any('metallic' in r for r in roles), 'no metallic ink: 9244 C is a pastel in the house files'


# --- the plate's seams and residue, as they print (Day 9's close: the second-agent verifier's findings) ----------------

K = rc.PX_PER_MM


def _picture(rows=320, cols=480, seed=7):
    """A textured picture: smoothed noise round mid-grey, fine detail everywhere (a ring always has energy)."""
    import cv2
    rng = np.random.default_rng(seed)
    base = rng.normal(128, 18, (rows, cols, 3)).astype(np.float32)
    return np.clip(cv2.GaussianBlur(base, (0, 0), 1.2), 0, 255).astype(np.uint8)


def test_a_seam_is_judged_on_its_rise_over_the_picture_before_the_paste():
    """A picture's own edge along a pasted region's line is not a seam (B-1.3's marbling read as 62 seam arcs); a
    paste that shifts the colour is one, read against the same arcs before the paste."""
    from apps.pipeline.services import rich_plate as rp
    pic = _picture()
    pic[:, 240:] = np.clip(pic[:, 240:].astype(int) + 60, 0, 255).astype(np.uint8)       # the picture's own edge
    region = np.zeros(pic.shape[:2], bool)
    region[40:280, 240:440] = True                                                       # its left side on that edge
    plain = rp.seam_delta_e(pic, region, px_per_mm=K)
    paired = rp.seam_delta_e(pic, region, px_per_mm=K, before_rgb=pic)
    assert plain['over_count'] > 0 and paired['over_count'] == 0 and paired['max_judged'] < 0.01
    plain_pic = _picture(seed=11)                                                         # no edge of its own
    pasted = plain_pic.copy()
    pasted[region] = np.clip(pasted[region].astype(int) + 25, 0, 255).astype(np.uint8)   # a real paste seam
    seam = rp.seam_delta_e(pasted, region, px_per_mm=K, before_rgb=plain_pic)
    assert seam['over_count'] == seam['measured'] > 0 and seam['max_judged'] >= rp.SEAM_DELTA_E_MAX
    assert all('rise' in a and 'at_mm' in a for a in seam['over'])


def test_a_seam_the_print_covers_does_not_print_and_one_it_shows_does():
    from apps.pipeline.services import rich_plate as rp
    import cv2
    pic = _picture()
    region = np.zeros(pic.shape[:2], bool)
    region[60:260, 120:360] = True
    pic[region] = np.clip(pic[region].astype(int) + 14, 0, 255).astype(np.uint8)
    line = cv2.dilate(cv2.Canny(region.astype(np.uint8) * 255, 1, 1), np.ones((25, 25), np.uint8)) > 0   # every band covered
    hidden = rp.seam_delta_e(pic, region, px_per_mm=K, cover=line)
    assert hidden['over_count'] == 0 and hidden['covered'] == hidden['arcs'] and hidden['unmeasured'] == 0
    half = line.copy()
    half[:, 240:] = False                                                                # the right half prints
    shown = rp.seam_delta_e(pic, region, px_per_mm=K, cover=half)
    assert 0 < shown['over_count'] and shown['covered'] > 0 and all(a['at_mm'][0] * K >= 230 for a in shown['over'])


def test_a_residue_in_a_corner_of_a_large_cleaned_piece_is_read_by_its_tile():
    """One mean over a large piece averaged away a word left in it (the sketch's own Arabic on B-1.3); the piece's most
    energetic tile against its ring's catches it, and two separate pieces of one mask are read one by one."""
    from apps.pipeline.services import rich_plate as rp
    pic = _picture(rows=600, cols=900)
    mask = np.zeros(pic.shape[:2], bool)
    mask[80:400, 80:560] = True                                   # about 40 x 60 mm
    mask[450:520, 650:800] = True                                 # a second piece of the same mask

    def energy(rgb):
        lab = rp.srgb_to_lab(rgb)
        b = [rp._band(lab[..., c], K) for c in range(3)]
        return b[0] ** 2 + b[1] ** 2 + b[2] ** 2
    clean = rp._residue_check(energy(pic), [mask], mask.shape, K)
    assert clean['holds'] and [r['piece'] for r in clean['regions']] == [1, 2]
    left = pic.copy()
    patch = left[100:132, 100:132]                                # a 4 x 4 mm patch of strokes left behind:
    patch[:] = 245                                                # 2 px dark lines every 6 px (0.74 mm), a letter's
    for row in range(0, 32, 6):                                   # stroke rhythm at the lid's small copy
        patch[row:row + 2] = 15
    read = rp._residue_check(energy(left), [mask], mask.shape, K)
    big = read['regions'][0]
    assert big['ratio'] <= rp.RESIDUE_RATIO_MAX < big['local_ratio']          # the mean passes it; the tile does not
    assert not read['holds'] and 9.0 <= big['local_at_mm'][0] <= 18.0 and 9.0 <= big['local_at_mm'][1] <= 18.0


def test_plate_findings_judge_the_seams_as_they_print_never_by_the_path():
    proof = {part: {'holds': True} for part in ('words', 'mark', 'structure', 'residue')}
    proof.update(seams={'holds': False}, not_measured=['seams: pasted region 0: 3 of its 40 seam arcs have a band too small'])
    plate = {'path': 'b', 'proof': proof}
    printed = {'regions': [{'index': 0, 'arcs': 40, 'measured': 30, 'covered': 10, 'unmeasured': 0, 'over_count': 2,
                            'over': [{'at_mm': [36.06, 8.54], 'delta_e': 5.32}, {'at_mm': [0.4, 60.0], 'delta_e': 4.1}]}]}
    issues, cannot = rc.plate_findings(plate, {}, printed)
    assert any(i.startswith('plate seam prints: 1 arc(s)') and '[36.06, 8.54]' in i for i in issues)
    assert any("on the lid's edge" in c and '[0.4, 60.0]' in c for c in cannot)
    assert not any('opaque' in x for x in issues + cannot)                       # no excuse by the path alone
    quiet = {'regions': [dict(printed['regions'][0], over=[], over_count=0)]}
    assert rc.plate_findings(plate, {}, quiet) == ([], [])
    unread = {'regions': [dict(printed['regions'][0], over=[], over_count=0, unmeasured=3)]}
    assert rc.plate_findings(plate, {}, unread)[0] == ['plate seam of region 0: 3 of its 40 arcs could not be read where they print']
    whole = {'regions': [{'index': 0, 'not_measured': 'the region covers the whole plate: it has no seam to read'}]}
    assert 'whole plate' in rc.plate_findings(plate, {}, whole)[0][0]


def test_the_b1_repair_paints_again_around_the_calm_field_not_over_it(mark_on):
    choices = rc.sketch_record('B-1.3')['option']['choices']
    recipe = recipes.REPAIRS['B-1'](choices, 'B-1.3')
    lay = rc.layout(rc.spec('B-1'), recipe, choices)
    region = rc._raster(recipe['clean_large'](lay), grow_mm=0.0)
    from shapely.ops import unary_union
    calm = unary_union(rc.region_polygons(lay['ornament']['regions']['calm']))
    x, y = calm.representative_point().coords[0]
    assert not region[int(y * K), int(x * K)] and region.mean() < 0.9


def test_the_day9_plates_seams_read_as_they_print(mark_on):
    """B-1.3's 62 'seam' arcs are its marbling's own edges (no arc rises 3 over the sketch it was cleaned from); C-1.1's
    inpainted rectangles print round its small type and logo (its checks once held on 'no seam of it prints')."""
    out = {}
    for cid, idea, sid in (('B-1.3', 'B-1', 'B-1.3'), ('C-1.1', 'C-1', 'C-1.1')):
        choices = rc.sketch_record(sid)['option']['choices']
        lay = rc.layout(rc.spec(idea), recipes.recipe(idea, choices, sid), choices)
        plate = json.loads((rc.DAY9 / 'concepts' / cid / 'plate.json').read_text())
        out[cid] = rc.printed_seams(lay, plate, sid, rc.DAY9 / 'concepts' / cid / 'truthful.png')['regions'][0]
    assert out['B-1.3']['over_count'] == 0 and out['B-1.3']['max_judged'] < 3.0 < out['B-1.3']['max_delta_e']
    assert out['C-1.1']['over_count'] > 0 and out['C-1.1']['covered'] > 0
