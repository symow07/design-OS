"""Day 8 §5 and §8 — the image guard, the sketch and truthful-build invariants, on fixtures; no provider is called."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from PIL import Image

from apps.pipeline.services import image_guard as ig


@pytest.fixture
def roots(tmp_path, monkeypatch, settings):
    settings.IMAGE_MODEL = 'gpt-image-2'
    rejected, web, allowed, house = (tmp_path / 'rejected', tmp_path / 'web', tmp_path / 'allowed', tmp_path / 'house-designs')
    for d in (rejected, web, allowed, house):
        d.mkdir()
    monkeypatch.setattr(ig, 'REJECTED_ROOTS', (rejected,))
    monkeypatch.setattr(ig, 'WEB_ROOTS', (web,))
    monkeypatch.setattr(ig, 'ALLOWED_ROOTS', (allowed, house))
    monkeypatch.setattr(ig, 'HOUSE_DESIGN_ROOTS', (house,))
    monkeypatch.setattr(ig, 'REPO', tmp_path)
    monkeypatch.setattr(ig, 'DENYLIST_CACHE', tmp_path / 'deny.json')
    monkeypatch.setattr(ig, 'CALL_LOG', tmp_path / 'calls.jsonl')
    return {'rejected': rejected, 'web': web, 'allowed': allowed, 'house': house, 'tmp': tmp_path}


def _png(path: Path, colour) -> Path:
    Image.new('RGB', (8, 8), colour).save(path)
    return path


def test_a_copy_of_a_rejected_design_is_refused_wherever_it_is(roots):
    _png(roots['rejected'] / 'task_124_var_1.png', (200, 10, 10))
    copy = _png(roots['allowed'] / 'innocent-name.png', (200, 10, 10))
    with pytest.raises(ig.ImageCallRefused, match='D-D8-2'):
        ig.check([{'role': 'style reference', 'path': copy}], 'flat lid artwork')


def test_web_pictures_competitor_names_other_roots_and_providers_are_refused(roots):
    web = _png(roots['web'] / 'trend_01.png', (1, 2, 3))
    with pytest.raises(ig.ImageCallRefused, match='D-D8-7'):
        ig.check([{'role': 'reference', 'path': web}], 'flat lid artwork')
    ok = _png(roots['allowed'] / 'name.png', (9, 9, 9))
    with pytest.raises(ig.ImageCallRefused, match='competitor'):
        ig.check([{'role': 'name lettering', 'path': ok}], 'a lid like the Dior one')
    outside = _png(roots['tmp'] / 'loose.png', (4, 4, 4))
    with pytest.raises(ig.ImageCallRefused, match='outside the roots'):
        ig.check([{'role': 'texture', 'path': outside}], 'flat lid artwork')
    with pytest.raises(ig.ImageCallRefused, match='OpenAI only'):
        ig.check([], 'flat lid artwork', provider='gemini')
    house = _png(roots['house'] / 'ES6009.png', (7, 7, 7))
    with pytest.raises(ig.ImageCallRefused, match='named trait'):
        ig.check([{'role': 'style reference', 'path': house}], 'flat lid artwork')
    assert ig.check([{'role': 'house trait crop', 'path': house}], 'flat lid artwork')[0]['role'] == 'house trait crop'


def test_an_allowed_call_is_sent_and_logged_and_a_refusal_is_logged_before_payment(roots):
    name = _png(roots['allowed'] / 'name.png', (12, 34, 56))
    paid = []
    out = ig.guarded_call(lambda checked: paid.append(checked) or {'image': 'x.png'}, operation='day8/sketch/A-1',
                          inputs=[{'role': 'name lettering', 'path': name}], prompt='flat lid artwork', quality='medium',
                          size='1536x1024')
    assert out == {'image': 'x.png'} and len(paid) == 1
    with pytest.raises(ig.ImageCallRefused):
        ig.guarded_call(lambda checked: paid.append(checked), operation='day8/sketch/A-2', inputs=[], quality='medium',
                        prompt='like Pat McGrath', size='1536x1024')
    assert len(paid) == 1                                          # the refusal never reached the provider
    rows = [json.loads(l) for l in (roots['tmp'] / 'calls.jsonl').read_text().splitlines()]
    assert [r['outcome'] for r in rows] == ['made', 'refused']
    assert rows[0]['inputs'][0]['sha256'] and rows[0]['prompt_sha256']
    audit = ig.audit(roots['tmp'] / 'calls.jsonl')
    assert audit['holds'] and audit['sent'] == 1 and audit['refused'] == 1


def test_the_competitor_check_reads_whole_words():
    assert ig.competitor_in('a Dior-like lid') == 'Dior'
    assert ig.competitor_in('a narsissus field') == ''          # NARS is a word, not a substring
    assert ig.competitor_in('Huda Beauty palette') in ('Huda Beauty', 'Huda')


# --- §2a the finishes a production file specifies ------------------------------------------------------------------

def test_finishes_are_read_from_layers_and_words_never_from_encoded_data(tmp_path):
    import fitz
    from apps.pipeline.services import production_finishes as pf
    pdf = tmp_path / 'house.pdf'
    doc = fitz.open(); page = doc.new_page(width=200, height=200)
    xref = doc.add_ocg('UV')
    page.insert_text((20, 40), 'Lid: hot foil gold, spot UV on the name', oc=xref)
    doc.save(pdf); doc.close()
    rec = pf.finishes_of(pdf)
    assert rec['state'] == 'OPENED'
    assert {'hot foil gold', 'spot UV'} <= set(rec['finishes'])
    assert any(e['channel'] == 'layer' for e in rec['finishes']['spot UV'])
    assert pf._finishes_in('局部UV 烫金 击凸') == ['hot foil gold', 'spot UV', 'emboss']
    assert pf._finishes_in('ke4BH"m4-8!3EUP,2cth82-?1F1K^UV0j') == []            # encoded data, never a finish
    assert not pf.looks_like_a_name('"@<?F.+>5Dk./s5H>UV$D0/4Rtrr2t')
    assert pf.looks_like_a_name('图层 1') and pf.looks_like_a_name('Gold Foil')
    missing = pf.finishes_of(tmp_path / 'absent.ai')
    assert missing['state'] == 'UNREADABLE' and missing['finishes'] == {}


# --- an Arabic line names its own face (Day 8) ----------------------------------------------------------------------

def test_an_arabic_line_draws_in_the_arabic_face_it_names(tmp_path):
    import fitz
    from apps.ire import font_roles
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Color, Document, Group, TextRun
    stem = 'fonts_droid-arabic-kufi_droidkufi-regular_ae57aea1cb701121'
    if stem not in font_roles.catalogue():
        pytest.skip('the granted Kufi is not on this machine')
    key = font_roles.line_face_key(stem, 400)
    assert font_roles.line_face_scripts(key) == (False, True)
    doc = Document(page_w=60, page_h=20, metadata={'typography_surface': 'apps/pipeline/services/truthful_concept.py::build_lid'},
                   root=Group(name='root', children=[TextRun(name='ar', text='باليت ظلال العيون', x=55, y=12, font=key,
                                                             size_pt=10, color=Color(r=0, g=0, b=0), align='right')]))
    out = tmp_path / 'ar.pdf'
    emit_pdf_ai(doc, str(out))
    fonts = {f[3] for f in fitz.open(str(out))[0].get_fonts()}
    assert any('DroidArabicKufi' in f for f in fonts), fonts


def test_a_variable_weight_its_stat_table_does_not_name_is_still_drawn():
    """Day 8, measured: Cormorant Garamond at 500 raised "Cannot find Axis Values"; the instance is now derived and
    named by its weight."""
    from apps.ire import font_roles
    stem = 'CormorantGaramond[wght]'
    if stem not in font_roles.catalogue():
        pytest.skip('Cormorant Garamond is not on this machine')
    inst = font_roles.instance_at(stem, 500)
    assert inst is not None and Path(inst['path']).exists()
    from fontTools.ttLib import TTFont
    font = TTFont(inst['path'])
    assert 'fvar' not in font and font['name'].getDebugName(6)


# --- §5: the devices, the options and the truthful layout -----------------------------------------------------------

@pytest.fixture
def lid(settings):
    """The approved mark on file and the directions' faces in the catalogue, or skip (another machine)."""
    settings.BRAND_MARK_APPROVAL_LOOKUP = True
    from apps.ire import brand_mark, font_roles
    from apps.pipeline.services import truthful_concept as tc
    if brand_mark.approved_master()['master'] is None:
        pytest.skip('the approved mark is not on this machine')
    for stem in ('InstrumentSerif-Regular', 'Gloock-Regular', 'Italiana-Regular', 'Montserrat[wght]', 'NotoNaskhArabic-Regular'):
        if stem not in font_roles.catalogue():
            pytest.skip('%s is not on this machine' % stem)
    tc.resolved.cache_clear()
    return tc


def test_the_six_sketches_vary_along_the_specs_open_choices_never_at_random(lid):
    for d in 'ABC':
        opts = lid.options(d)
        axes = lid.spec(d)['open_choices']
        assert len(opts) == 6 and opts[0]['levels'] == [0, 0, 0]
        assert len({json.dumps(o['choices'], sort_keys=True) for o in opts}) == 6
        for k, axis in enumerate(axes[:2]):
            assert sorted(o['levels'][k] for o in opts) == [0, 0, 0, 1, 1, 1], axis['axis']
        for o in opts:
            assert all(o['choices'][a['axis']] in a['values'] for a in axes)


def test_every_option_meets_the_measured_checks_by_construction(lid):
    """The name ≥ 7 mm, the ℮ at 3 mm, nothing under 5 pt, the alif ≥ 90 %, one weight step, the copy word for word,
    the proportion exact, and no device mark nor line over another line — on all eighteen layouts."""
    from apps.pipeline.services import lid_devices as dev
    for d in 'ABC':
        for o in lid.options(d):
            lay = lid.layout(d, o)
            checks = lid.measured_checks(lay)
            assert checks['all_hold'], (o['id'], checks['cannot_meet'])
            assert dev.intrusions(lay['device'], list(lay['boxes'].values())) == [], o['id']
            assert not lay['notes'], (o['id'], lay['notes'])


def test_the_hero_line_swells_and_the_ring_field_clears_the_type(lid):
    from shapely.geometry import Point, box
    a = lid.layout('A', lid.options('A')[0])
    lo, hi = a['device']['hero_width_mm']
    assert abs(lo - 0.2) < 0.01 and 1.3 <= hi <= 1.4
    assert [m for m in a['device']['marks'] if m['ink'] == 'accent' and m['fill'] and 'foil' in m['finishes']]
    for o in lid.options('B'):
        b = lid.layout('B', o)
        centre, radius = Point(b['device']['field_centre_mm']), b['device']['field_radius_mm']
        assert all(centre.distance(box(*bb)) >= radius + 1.99 for bb in b['boxes'].values()), o['id']
        assert {m['ink'] for m in b['device']['marks']} == {'secondary' if o['choices']['colour weighting'] == 'rose-led' else 'accent', 'blind'}


def test_the_words_are_the_briefs_and_the_blind_never_prints(lid):
    from apps.ire.graph import TextRun
    lay = lid.layout('B', lid.options('B')[2])
    printed = lid.document(lay, view=False)
    runs = [n for n, _ in printed.walk() if isinstance(n, TextRun) and not n.name.endswith('-emboss')]
    words = {n.name.split('-')[0]: [] for n in runs}
    for n in runs:
        words[n.name.split('-')[0]].append(n.text)
    assert ' '.join(words['name']) == lid.COPY['name'] and words['descriptor_en'] == [lid.COPY['descriptor_en']]
    assert words['descriptor_ar'] == [lid.COPY['descriptor_ar']] and words['net'] == [lid.COPY['net']]
    device = [g for g in printed.root.children if g.name == 'DEVICE'][0]
    blind = lid._hex(lay['ink']['blind'])
    assert not [p for p in device.children if p.stroke is not None and p.stroke.color == blind]
    carriers = [g for g in printed.root.children if g.name == 'FINISH CARRIERS'][0]
    assert carriers.opacity == 0.0 and {f.kind for c in carriers.children for f in c.finishes} == {'deboss', 'emboss'}
    shown = lid.document(lay, view=True)
    device = [g for g in shown.root.children if g.name == 'DEVICE'][0]
    assert [p for p in device.children if p.stroke is not None and p.stroke.color == blind]


def test_the_plate_proof_catches_a_drawn_word_and_passes_a_clean_ground(lid, tmp_path):
    import numpy as np
    from PIL import ImageDraw, ImageFont
    lay = lid.layout('C', lid.options('C')[0])
    rng = np.random.default_rng(0)
    ground = np.clip(np.array([250, 243, 236]) + rng.normal(0, 1.5, (970, 1536, 3)), 0, 255).astype(np.uint8)
    clean = tmp_path / 'clean.png'
    Image.fromarray(ground).save(clean)
    assert lid.prove_plate('C', lay, clean, tmp_path)['holds']
    drawn = Image.fromarray(ground)
    font = ImageFont.truetype(str(Path(lid.settings.BASE_DIR) / 'static' / 'fonts' / 'NotoSans-Bold.ttf'), 90)
    ImageDraw.Draw(drawn).text((200, 300), 'Enchanted Rose', fill=(58, 33, 49), font=font)
    worded = tmp_path / 'worded.png'
    drawn.save(worded)
    proof = lid.prove_plate('C', lay, worded, tmp_path)
    assert not proof['holds'] and proof['latin_copy_found']
    lined = tmp_path / 'lined.png'
    lid.render(lid.document(lay, parts=('ground', 'device')), lined, frame=False)
    proof = lid.prove_plate('C', lay, lined, tmp_path)
    assert not proof['holds'] and (proof['device_line_energy_ratio'] > 1.6 or proof['device_pattern_ncc'] > 0.2)


# --- the gate review of Day 8: a failed read, an empty region, a failing proof never pass ---------------------------

def _ivory_plate():
    """The plate of the proof test above: C's ivory ground with a faint grain (seed 0), 970 × 1536."""
    import numpy as np
    rng = np.random.default_rng(0)
    return np.clip(np.array([250, 243, 236]) + rng.normal(0, 1.5, (970, 1536, 3)), 0, 255).astype(np.uint8)


def test_a_failed_ocr_read_raises_and_never_reads_as_no_words(tmp_path, monkeypatch):
    """Tesseract's exit code and TSV header are read, through the real tesseract: an unreadable picture exits 1 yet
    prints the header, a language that does not load exits 1 and prints nothing — each raises OCRFailed with the
    stderr's tail; a blank picture read cleanly is still no words."""
    import subprocess
    from types import SimpleNamespace
    from apps.pipeline.services import concept_sketches as cs
    blank = tmp_path / 'blank.png'
    Image.new('RGB', (200, 100), (250, 243, 236)).save(blank)
    assert cs.ocr_words(blank) == []                                        # read, and nothing on it
    garbage = tmp_path / 'not-a-picture.png'
    garbage.write_bytes(b'not a picture')
    with pytest.raises(cs.OCRFailed, match='did not read not-a-picture.png: exit 1, TSV header present; stderr') as failed:
        cs.ocr_words(garbage)
    assert 'Error during processing' in str(failed.value)
    monkeypatch.setattr(cs, 'TESSDATA', tmp_path / 'no-tessdata')
    with pytest.raises(cs.OCRFailed, match=r'tesseract \(ara, psm 11\) did not read blank.png: exit 1, no TSV header'):
        cs.ocr_words(blank, lang='ara')
    monkeypatch.setattr(cs, 'subprocess', SimpleNamespace(run=lambda args, **kw: subprocess.CompletedProcess(args, 0, '', '')))
    with pytest.raises(cs.OCRFailed, match='exit 0, no TSV header'):
        cs.ocr_words(blank)


def test_a_sketch_whose_ocr_failed_says_so_never_missing_every_word(tmp_path, monkeypatch):
    """copy_check records a failed read and does not raise (make() calls it after the paid edit, before result.json
    is written); the line J1 is given says the OCR failed, never "found 0" and "missing" every word. A clean read with
    nothing on it keeps its record."""
    from apps.pipeline.services import concept_sketches as cs
    lid_png = tmp_path / 'lid.png'
    Image.new('RGB', (1536, 970), (43, 23, 41)).save(lid_png)
    read = cs.copy_check(lid_png)
    assert 'ocr_failed' not in read and read['found'] == [] and read['missing'] == list(cs.COPY_WORDS)
    assert cs.checks_line({'copy': read}).startswith("OCR found 0 of the brief's 10 Latin words; missing: Enchanted")
    monkeypatch.setattr(cs, 'TESSDATA', tmp_path / 'no-tessdata')
    failed = cs.copy_check(lid_png)
    assert failed['found'] is None and failed['missing'] is None and failed['ocr_words'] is None
    assert failed['ocr_failed'].startswith('tesseract (eng, psm 11) did not read lid.png: exit 1')
    line = cs.checks_line({'copy': failed})
    assert line.startswith('OCR failed on this sketch, so its copy was not read') and '; missing:' not in line


def test_an_empty_region_has_no_line_energy():
    import numpy as np
    from apps.pipeline.services import truthful_concept as tc
    gray = np.random.default_rng(0).integers(0, 256, (970, 1536)).astype(np.uint8)
    assert tc._line_energy(gray, np.zeros(gray.shape, bool)) is None
    assert tc._line_energy(gray, np.ones(gray.shape, bool)) > 0


def test_the_plate_proof_does_not_hold_on_what_it_could_not_measure(lid, tmp_path, monkeypatch):
    """The clean ground holds; over an empty device footprint, or with the Arabic OCR failing, the proof does not —
    each named under not_measured, its value None. Line energy over the device and none elsewhere is measured: a line
    system detected, never filed under not_measured, and the proof does not hold."""
    import numpy as np
    from apps.pipeline.services import concept_sketches as cs
    lay = lid.layout('C', lid.options('C')[0])
    clean = tmp_path / 'clean.png'
    Image.fromarray(_ivory_plate()).save(clean)
    assert lid.prove_plate('C', lay, clean, tmp_path)['holds']
    bare = dict(lay, device=dict(lay['device'], marks=[]))                  # nothing drawn: an empty footprint
    proof = lid.prove_plate('C', bare, clean, tmp_path)
    assert not proof['holds'] and proof['device_line_energy_ratio'] is None and proof['device_pattern_ncc'] is None
    assert proof['not_measured'] == ['the device footprint is empty: no line energy or line pattern is measured over it']
    lines = lid.footprint(lay, tmp_path, keep_mark=lambda m: True, rule=False, grow_mm=0.0, parts=('device',))
    black = np.zeros((970, 1536, 3), np.uint8)
    black[lines] = 255                                                       # lines over the device, black elsewhere
    Image.fromarray(black).save(tmp_path / 'black.png')
    proof = lid.prove_plate('C', lay, tmp_path / 'black.png', tmp_path)
    assert not proof['holds'] and proof['device_line_energy_ratio'] is None          # it read 99.0
    assert proof['line_system_detected'] is True and 'not_measured' not in proof     # it was filed as not measured
    eng_only = tmp_path / 'tessdata-eng-only'
    eng_only.mkdir()
    (eng_only / 'eng.traineddata').symlink_to(cs.TESSDATA / 'eng.traineddata')
    monkeypatch.setattr(cs, 'TESSDATA', eng_only)                            # the Arabic data missing
    proof = lid.prove_plate('C', lay, clean, tmp_path)
    assert not proof['holds'] and proof['latin_copy_found'] == [] and proof['arabic_copy_found'] is None
    assert len(proof['not_measured']) == 1 and '(ara, psm 11)' in proof['not_measured'][0]


def test_reading_a_sketch_stops_on_a_failed_ocr_read(lid, tmp_path, monkeypatch):
    """read_sketch raises OCRFailed, so a build stops before any plate is paid for, rather than reading every anchor
    as "not read on the sketch"."""
    from apps.pipeline.services import concept_sketches as cs
    lid_png = tmp_path / 'lid.png'
    Image.fromarray(_ivory_plate()).save(lid_png)
    monkeypatch.setattr(cs, 'TESSDATA', tmp_path / 'no-tessdata')
    with pytest.raises(cs.OCRFailed):
        lid.read_sketch('C', lid.options('C')[0], lid_png, tmp_path)


def test_a_failing_plate_proof_fails_the_builds_checks(lid, tmp_path, monkeypatch):
    """The proof is one of the build's checks: a plate with a faint line system drawn over the device fails it while
    every measured row holds, and checks.json's all_hold and build.json's checks_hold say so (both were computed
    before the proof was added). Nothing is painted (plate_from) and nothing is written under docs/audit."""
    import numpy as np
    from apps.pipeline.services import concept_sketches as cs
    monkeypatch.setattr(cs, 'SKETCHES', tmp_path / 'sketches')
    monkeypatch.setattr(lid, 'CONCEPTS', tmp_path / 'concepts')
    option = lid.options('C')[0]
    ground = _ivory_plate()
    (tmp_path / 'sketches' / option['id']).mkdir(parents=True)
    Image.fromarray(ground).save(tmp_path / 'sketches' / option['id'] / 'lid.png')
    lines = lid.footprint(lid.layout('C', option), tmp_path, keep_mark=lambda m: True, rule=False, grow_mm=0.0, parts=('device',))
    faint = ground.astype(int)
    faint[lines] -= 8                                                        # our device's lines, 8 levels darker
    plate = tmp_path / 'plate.png'
    Image.fromarray(np.clip(faint, 0, 255).astype(np.uint8)).save(plate)
    record = lid.build('C', option, option['id'], plate_from={'plate': str(plate)})
    out = tmp_path / 'concepts' / option['id']
    checks = json.loads((out / 'checks.json').read_text())
    assert not checks['plate_proof']['holds'] and checks['plate_proof']['device_line_energy_ratio'] > 1.6
    assert all(r['holds'] for r in checks['checks'])             # every measured row holds: the proof alone fails
    assert checks['all_hold'] is False and record['checks_hold'] is False
    assert json.loads((out / 'build.json').read_text())['checks_hold'] is False
    assert [c for c in record['cannot_meet'] if c.startswith('the plate proof: ')]


def test_todays_own_paid_pictures_are_never_rejected_designs(tmp_path, monkeypatch):
    import sqlite3
    root = tmp_path / 'rescue_spend' / 'responses'
    for rid in ('old', 'today'):
        (root / rid).mkdir(parents=True)
        _png(root / rid / 'image-0.png', (1, 2, 3) if rid == 'old' else (4, 5, 6))
    with sqlite3.connect(str(tmp_path / 'rescue_spend' / 'ledger.sqlite3')) as db:
        db.execute('create table calls (id text, operation text)')
        db.executemany('insert into calls values (?, ?)', [('old', 'day7/stand/x'), ('today', ig.TODAY_OPERATION_PREFIX + 'sketches/A1')])
    found = {p.parent.name for p in ig._images_under((root,))}
    assert found == {'old'}


# --- §6: the pick page --------------------------------------------------------------------------------------------

def _pick_fixture(root):
    """A publication record with one concept below the bar, its files pinned by sha256."""
    import hashlib
    files = {}
    for rel, colour in (('concepts/X1/truthful.png', (43, 23, 41)), ('concepts/X1/name-1to1.png', (250, 243, 236)),
                        ('concepts/X1/arabic-1to1.png', (250, 243, 236)), ('concepts/X1/finish-sheet.png', (246, 246, 246)),
                        ('sketches/X1/lid.png', (43, 23, 41))):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (40, 25), colour).save(p)
        files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    pin = lambda rel, mime='image/png': {'path': rel, 'sha256': files[rel], 'mime': mime, 'words': rel}
    record = {'schema': 'day8_pick/1.0', 'gate': 'rubric v2 · mean ≥ 8', 'calibration': {'gate_rubric': 'v2'},
              'passing': [], 'below_the_bar': ['X1'],
              'concepts': [{'id': 'X1', 'direction': 'A', 'name': 'Gravure', 'role': 'trend-led', 'idea': 'One line of rose-gold light.',
                            'story': 'story', 'option': {}, 'sketch': 'X1', 'status': 'fail', 'passes': False,
                            'raw_means': {'J1': 7.1, 'J2': 7.4}, 'stricter_mean': 7.0, 'capped_mean': 6.8,
                            'scores': {'beauty': {'J1': 7, 'J2': 8, 'stands': 7}}, 'caps': [], 'hard_failures': [],
                            'top_issues': [{'observation': 'the hero line is thin at 2 m', 'location': 'centre', 'repair': 'widen it'}],
                            'reads': {'J1': ['name', 'line', 'mark'], 'J2': ['name', 'line', 'mark']}, 'idea_read': {'J1': 'a line', 'J2': 'a line'},
                            'checks': {'checks': [{'check': 'name cap height ≥ 7 mm', 'value': 11.0, 'holds': True}], 'issues': []},
                            'designer_eye': ['name: as sketched'], 'fonts': [{'role': 'Latin display', 'family': 'Instrument Serif', 'stem': 'InstrumentSerif-Regular', 'licence': 'SIL Open Font License, Version 1.1'}],
                            'takes': {'house_dna': 'gold rules'}, 'extends': {'lipstick': 'the hero line as its base ring'}, 'finishes': [{'finish': 'hot foil, rose gold', 'on': 'the hero line'}],
                            'proposals_flagged': [], 'repairs': {}, 'name_crop_width_mm': 84.0, 'arabic_crop_width_mm': 33.0,
                            'files': {'truthful': 'X1-truthful', 'name': 'X1-name', 'arabic': 'X1-arabic', 'finishes': 'X1-finishes'}}],
              'sketches': [{'id': 'X1', 'direction': 'A', 'choices': {}, 'rank': 1, 'score': 7.5, 'why': 'calm', 'went_on': True, 'copy': [], 'file': 'sketch-X1'}],
              'anchors': [{'brand': 'Hourglass', 'product': 'Curator', 'page': 'https://example.com/curator', 'role': 'fixed'}],
              'downloads': {'X1-truthful': pin('concepts/X1/truthful.png'), 'X1-name': pin('concepts/X1/name-1to1.png'),
                            'X1-arabic': pin('concepts/X1/arabic-1to1.png'), 'X1-finishes': pin('concepts/X1/finish-sheet.png'),
                            'sketch-X1': pin('sketches/X1/lid.png')}}
    (root / 'pick').mkdir(parents=True, exist_ok=True)
    (root / 'pick' / 'publication.json').write_text(json.dumps(record))
    return record


@pytest.mark.django_db
def test_the_pick_page_shows_the_below_the_bar_sheet_and_serves_only_pinned_bytes(client, tmp_path, monkeypatch):
    from django.contrib.auth.models import User
    from apps.pipeline.services import day8_pick
    _pick_fixture(tmp_path)
    monkeypatch.setattr(day8_pick, 'DAY8', tmp_path)
    monkeypatch.setattr(day8_pick, 'RECORD', tmp_path / 'pick' / 'publication.json')
    client.force_login(User.objects.create_superuser('owner8', 'o8@example.com', 'pw'))
    page = client.get('/dashboard/palette-pick/')
    assert page.status_code == 200
    body = page.content.decode()
    assert 'Below the bar.' in body and 'X1 · Gravure' in body and 'the hero line is thin at 2 m' in body
    assert 'width:84.0mm' in body and 'SIL Open Font License' in body
    for tab, words in (('history', 'went on to a build'), ('jury', 'Hourglass')):
        assert words in client.get('/dashboard/palette-pick/?tab=%s' % tab).content.decode()
    served = client.get('/dashboard/day8/files/X1-truthful/')
    assert served.status_code == 200 and served['Content-Type'] == 'image/png'
    Image.new('RGB', (40, 25), (0, 0, 0)).save(tmp_path / 'concepts/X1/truthful.png')      # the bytes change after publishing
    assert client.get('/dashboard/day8/files/X1-truthful/').status_code == 404
    assert client.get('/dashboard/palette-pick/').status_code == 404


@pytest.mark.django_db
def test_the_pick_page_needs_a_member(client, tmp_path, monkeypatch):
    from django.contrib.auth.models import User
    from apps.pipeline.services import day8_pick
    _pick_fixture(tmp_path)
    monkeypatch.setattr(day8_pick, 'DAY8', tmp_path)
    monkeypatch.setattr(day8_pick, 'RECORD', tmp_path / 'pick' / 'publication.json')
    client.force_login(User.objects.create_user('visitor8', 'v8@example.com', 'pw'))
    assert client.get('/dashboard/palette-pick/').status_code == 403


# --- the gate review of Day 8: the audit holds only on what a row records; a rewritten design is hashed again -------

def test_a_sent_call_that_does_not_record_what_it_sent_never_audits_clean(roots):
    """§8 asserts no rejected design, no web picture and no competitor name in what was SENT. A made or failed row with
    no 'inputs', an input with no sha256 or no 'prompt' cannot be checked (r.get('inputs', []) and r.get('prompt', '')
    read it as clean): it is counted by name and the audit does not hold — one row once, however many of its inputs
    carry no sha256. A refusal is logged before any hash and sent nothing: it stays clean, as does a call that sent no
    picture at all."""
    name = _png(roots['allowed'] / 'name.png', (12, 34, 56))
    ig.guarded_call(lambda checked: {'image': 'x.png'}, operation='day8/sketch/A-1',
                    inputs=[{'role': 'name lettering', 'path': name}], prompt='flat lid artwork', quality='medium',
                    size='1536x1024')
    made = json.loads((roots['tmp'] / 'calls.jsonl').read_text())
    refused = dict(made, outcome='refused', why='D-D8-7: the prompt names a competitor brand (Dior)',
                   inputs=[{'role': 'name lettering', 'path': str(name)}])
    rejected = _png(roots['rejected'] / 'task_124_var_1.png', (200, 10, 10))
    unhashed = {'role': 'texture', 'path': str(name)}
    log = roots['tmp'] / 'edited.jsonl'

    def audit_of(*rows):
        log.write_text(''.join(json.dumps(r) + '\n' for r in (made, refused) + rows))
        return ig.audit(log)

    def without(key, row=made):
        return {k: v for k, v in row.items() if k != key}

    for label, row, counts in (
            ('no inputs recorded', without('inputs'), (1, 0, 0)),
            ('inputs not a list', dict(made, inputs=None), (1, 0, 0)),
            ('an input with no sha256', dict(made, inputs=[unhashed]), (1, 0, 0)),
            ('two inputs with no sha256, one row', dict(made, inputs=[unhashed, dict(unhashed, role='mark')]), (1, 0, 0)),
            ('a sha256 that is not a digest', dict(made, inputs=[dict(made['inputs'][0], sha256='pending')]), (1, 0, 0)),
            ('a rejected input beside an unhashed one',
             dict(made, inputs=[dict(unhashed, sha256=ig._sha(rejected)), unhashed]), (1, 0, 1)),
            ('no prompt recorded', without('prompt'), (0, 1, 0)),
            ('a failed call with no prompt', dict(without('prompt'), outcome='failed'), (0, 1, 0)),
            ('a prompt that is not text', dict(made, prompt=None), (0, 1, 0))):
        found = audit_of(row)
        assert found['holds'] is False, label
        assert (found['sent_without_input_sha256'], found['sent_without_prompt'],
                found['rejected_or_web_inputs']) == counts, label
        assert found['sent'] == 2 and found['refused'] == 1 and found['competitor_prompts'] == 0, label
    for found in (audit_of(), audit_of(dict(made, inputs=[]))):
        assert found['holds'] is True
        assert (found['sent_without_input_sha256'], found['sent_without_prompt']) == (0, 0)


def test_a_rejected_design_rewritten_in_place_is_hashed_again(roots):
    """The denylist cache was keyed by path alone, so a design rewritten in place kept its first sha256 and a copy of
    its new bytes passed the guard; a file whose size or mtime has changed since it was hashed is hashed again."""
    design = roots['rejected'] / 'task_124_var_1.png'
    design.write_bytes(b'the design as it was first saved')
    ig.denylist()                                                            # hashed, and cached
    design.write_bytes(b'the design as it was saved again, over the same file')
    copy = roots['allowed'] / 'innocent-name.png'
    copy.write_bytes(design.read_bytes())
    with pytest.raises(ig.ImageCallRefused, match='D-D8-2'):
        ig.check([{'role': 'style reference', 'path': copy}], 'flat lid artwork')


def test_the_denylist_hashes_again_only_a_file_whose_size_or_mtime_changed(roots, monkeypatch):
    """Unchanged files are read from the cache, never hashed twice; a rewrite of the same size is caught by its mtime
    (set a second later here, so no file-system clock tick is relied on)."""
    import os
    kept, rewritten = roots['rejected'] / 'kept.png', roots['rejected'] / 'rewritten.png'
    kept.write_bytes(b'A' * 64)
    rewritten.write_bytes(b'B' * 64)
    sha, hashed = ig._sha, []
    monkeypatch.setattr(ig, '_sha', lambda path: hashed.append(Path(path).name) or sha(path))
    ig.denylist()
    assert sorted(hashed) == ['kept.png', 'rewritten.png']
    hashed.clear()
    ig.denylist()
    assert hashed == []                                                      # nothing changed: nothing hashed
    before, first = sha(rewritten), rewritten.stat()
    rewritten.write_bytes(b'C' * 64)                                         # the same size ...
    os.utime(rewritten, ns=(first.st_atime_ns, first.st_mtime_ns + 10 ** 9))      # ... saved a second later
    deny = ig.denylist()
    assert hashed == ['rewritten.png']
    assert deny['rejected'][sha(rewritten)] == str(rewritten) and before not in deny['rejected']


def test_a_denylist_cache_in_the_old_format_is_hashed_again_never_trusted(roots):
    """A cache written before the fix holds {sha: path} with no size or mtime: it does not crash the guard and none of
    its shas is trusted — each file is hashed again and the cache rewritten with each path's size and mtime_ns. An
    entry that carries no digest is hashed again too."""
    design = roots['rejected'] / 'task_124_var_1.png'
    design.write_bytes(b'the design as it is now')
    cache = roots['tmp'] / 'deny.json'
    cache.write_text(json.dumps({'rejected': {'0' * 64: str(design)}, 'web': {}}))      # a stale sha, old format
    sha, st = ig._sha(design), design.stat()
    assert ig.denylist() == {'rejected': {sha: str(design)}, 'web': {}}
    entry = {'sha256': sha, 'size': st.st_size, 'mtime_ns': st.st_mtime_ns}
    assert json.loads(cache.read_text()) == {'by_path': {'rejected': {str(design): entry}, 'web': {}}}
    cache.write_text(json.dumps({'by_path': {'rejected': {str(design): dict(entry, sha256=None)}, 'web': {}}}))
    assert ig.denylist() == {'rejected': {sha: str(design)}, 'web': {}}


# --- the gate review of Day 8: a production file's channel that could not be read is said, never "declares nothing" -

#: Illustrator's native data as its names read: a swatch "Gold Foil", a layer "图层 1", and a run that is not UTF-8 —
#: read as latin-1 it would be "ÿþ UV", a name saying spot UV; the UTF-8 filter drops it
_NATIVE = b'%%AI8_BeginLayer\n(Gold Foil) Lb\n(\xff\xfe UV) Ln\n(\xe5\x9b\xbe\xe5\xb1\x82 1) Ln\n'


def _gold_foil_ink_pdf(path):
    """A real one-page PDF whose page's resources name a Separation ink "Gold Foil", saved with object streams (the
    ink, the page and its resources are written inside one)."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    ink = doc.get_new_xref()
    doc.update_object(ink, '[/Separation /Gold#20Foil /DeviceCMYK << /FunctionType 2 /Domain [0 1] /C0 [0 0 0 0] '
                           '/C1 [0 0.2 0.8 0.1] /N 1 >>]')
    _kind, resources = doc.xref_get_key(page.xref, 'Resources')
    doc.xref_set_key(int(resources.split()[0]), 'ColorSpace', '<< /CS0 %d 0 R >>' % ink)
    doc.save(str(path), use_objstms=1)
    doc.close()
    return path


def _damage_the_object_stream(path):
    """The object stream's bytes scrambled in place (XOR 0x5A, its length kept), as a disk or a transfer damages a file:
    PyMuPDF still opens it, and every object inside raises "corrupt object stream" (measured on PyMuPDF 1.28)."""
    raw = path.read_bytes()
    start = raw.index(b'stream', raw.index(b'/ObjStm')) + len(b'stream')
    start += 2 if raw[start:start + 2] == b'\r\n' else 1
    end = raw.index(b'endstream', start)
    path.write_bytes(raw[:start] + bytes(b ^ 0x5A for b in raw[start:end]) + raw[end:])
    return path


def _native_data_pdf(path, parts, *, numblock=None, dangling=False):
    """A real one-page PDF carrying Illustrator's native data as an .ai saved PDF-compatible does: the page's
    /PieceInfo /Illustrator /Private dict names /AIPrivateData1..n and /NumBlock (the house files' layout). A part given
    as None is an object that is no stream; ``dangling`` names one part more, at an object the file does not have."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    refs = []
    for number, part in enumerate(parts, 1):
        xref = doc.get_new_xref()
        doc.update_object(xref, '<< >>')
        if part is not None:
            doc.update_stream(xref, part)
        refs.append('/AIPrivateData%d %d 0 R' % (number, xref))
    if dangling:
        refs.append('/AIPrivateData%d 9999 0 R' % (len(parts) + 1))
    priv = doc.get_new_xref()
    doc.update_object(priv, '<< %s /NumBlock %d >>' % (' '.join(refs), len(refs) if numblock is None else numblock))
    doc.xref_set_key(page.xref, 'PieceInfo', '<< /Illustrator << /Private %d 0 R >> >>' % priv)
    doc.save(str(path))
    doc.close()
    return path


def test_a_damaged_object_is_counted_and_never_read_as_naming_nothing(tmp_path):
    """The same file read whole names its "Gold Foil" ink (hot foil gold); with its object stream damaged, the objects
    in it (the ink among them) cannot be read: it still says OPENED and credits no finish, and the record now counts
    the objects not read where it said nothing at all (the old record: OPENED, no colourant, no finish, no failure)."""
    import fitz
    from apps.pipeline.services import production_finishes as pf
    whole = pf.finishes_of(_gold_foil_ink_pdf(tmp_path / 'whole.pdf'))
    assert whole['state'] == 'OPENED' and whole['colourants'] == ['Gold Foil']
    assert whole['finishes'] == {'hot foil gold': [{'channel': 'spot colourant', 'name': 'Gold Foil'}]}
    assert (whole['objects_unreadable'], whole['native_data'], whole['layers_error']) == (0, 'absent', None)
    damaged = _damage_the_object_stream(_gold_foil_ink_pdf(tmp_path / 'damaged.pdf'))
    doc, raised = fitz.open(str(damaged)), 0
    for xref in range(1, doc.xref_length()):
        try:
            doc.xref_object(xref, compressed=False)
        except Exception:  # noqa: BLE001 — as _object reads it (PyMuPDF 1.28 raises RuntimeError "corrupt object stream")
            raised += 1
    doc.close()
    rec = pf.finishes_of(damaged)
    assert rec['state'] == 'OPENED' and rec['colourants'] == [] and rec['finishes'] == {}      # no finish invented
    assert rec['objects_unreadable'] == raised >= 1
    assert (rec['native_data'], rec['layers_error']) == ('absent', None)


def test_native_data_says_absent_read_undecodable_or_incomplete(tmp_path):
    """The native-data channel's state is returned with its strings. Read whole (zlib, in two parts; ZStandard as the
    house files carry it) it is 'read' — the run that is not UTF-8 still dropped, so no spot UV is read into it. Data
    that will not decompress is 'undecodable' (it was [] with nothing said). A part that is no stream, a part that reads
    empty (what PyMuPDF returns for damaged Flate data), a part numbered past the file's objects (PyMuPDF raises "bad
    xref": the old reader crashed) or fewer parts than /NumBlock make it 'incomplete' — the strings what they were."""
    import shutil
    import subprocess
    import zlib
    import fitz
    from apps.pipeline.services import production_finishes as pf
    blob = b'%AI12_CompressedData' + zlib.compress(_NATIVE)
    names = ['Gold Foil', '图层 1']

    def native(name, parts, **kw):
        doc = fitz.open(str(_native_data_pdf(tmp_path / name, parts, **kw)))
        try:
            return pf.native_strings(doc)
        finally:
            doc.close()

    plain = tmp_path / 'plain.pdf'
    doc = fitz.open()
    doc.new_page()
    doc.save(str(plain))
    assert pf.native_strings(doc) == ([], 'absent')
    doc.close()
    assert native('read.pdf', [blob[:20], blob[20:]]) == (names, 'read')
    assert native('undecodable.pdf', [b'%AI12_CompressedData' + b'this is not zlib data']) == ([], 'undecodable')
    assert native('not-a-stream.pdf', [blob[:20], None]) == ([], 'incomplete')
    assert native('empty-part.pdf', [blob[:20], b'', blob[20:]]) == (names, 'incomplete')
    assert native('dangling.pdf', [blob[:20], blob[20:]], dangling=True) == (names, 'incomplete')
    assert native('short.pdf', [blob[:20], blob[20:]], numblock=3) == (names, 'incomplete')
    if shutil.which('zstd'):
        packed = subprocess.run(['zstd', '-c'], input=_NATIVE, capture_output=True, check=True).stdout
        assert native('zstd.pdf', [b'%AI24_ZStandard_Data' + packed]) == (names, 'read')
        assert native('zstd-bad.pdf', [b'%AI24_ZStandard_Data' + b'not a zstd frame']) == ([], 'undecodable')
    rec = pf.finishes_of(tmp_path / 'read.pdf')
    assert (rec['native_data'], rec['native_strings'], rec['objects_unreadable']) == ('read', 2, 0)
    assert set(rec['finishes']) == {'hot foil gold'} and 'spot UV' not in rec['finishes']
    rec = pf.finishes_of(tmp_path / 'undecodable.pdf')
    assert rec['state'] == 'OPENED' and (rec['native_data'], rec['native_strings'], rec['finishes']) == ('undecodable', 0, {})


def test_an_error_reading_the_layers_is_named_never_read_as_no_layers(tmp_path, monkeypatch):
    """A file's layers read as named with no error; when PyMuPDF raises reading them (no damaged /OCProperties tried on
    PyMuPDF 1.28 made it raise, so the test makes the call raise), layers_error names the exception and no finish is
    credited to the layers (the old record: no layers, nothing said)."""
    import fitz
    from apps.pipeline.services import production_finishes as pf
    pdf = tmp_path / 'layered.pdf'
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 40), 'artwork', oc=doc.add_ocg('UV'))
    doc.save(str(pdf))
    doc.close()
    rec = pf.finishes_of(pdf)
    assert (rec['layers'], rec['layers_error'], set(rec['finishes'])) == (['UV'], None, {'spot UV'})

    def corrupt(self):
        raise RuntimeError('code=7: corrupt object stream')
    monkeypatch.setattr(fitz.Document, 'get_ocgs', corrupt)
    rec = pf.finishes_of(pdf)
    assert rec['state'] == 'OPENED' and (rec['layers'], rec['layers_error'], rec['finishes']) == ([], 'RuntimeError', {})


def test_the_census_counts_the_files_with_an_unreadable_channel_and_invents_no_finish(tmp_path):
    """Over a whole file, a damaged one, one whose native data will not decompress and one that is absent: the absent
    file is 'unreadable' (its three channel states None), the two opened files with a channel not read are counted
    and named apart, and only the whole file's own ink is counted as a finish."""
    import zlib
    from apps.pipeline.services import production_finishes as pf
    whole = _gold_foil_ink_pdf(tmp_path / 'whole.pdf')
    damaged = _damage_the_object_stream(_gold_foil_ink_pdf(tmp_path / 'damaged.pdf'))
    undecodable = _native_data_pdf(tmp_path / 'undecodable.pdf', [b'%AI12_CompressedData' + zlib.compress(_NATIVE)[:-9]])
    absent = tmp_path / 'absent.ai'
    seen = pf.census([whole, damaged, undecodable, absent])
    assert (seen['files'], seen['unreadable'], seen['opened_with_an_unreadable_channel']) == (4, 1, 2)
    assert seen['paths_with_an_unreadable_channel'] == sorted([str(damaged), str(undecodable)])
    assert seen['files_by_finish'] == {'hot foil gold': 1}
    assert seen['per_file'][str(undecodable)]['native_data'] == 'undecodable'
    missing = seen['per_file'][str(absent)]
    assert missing['state'] == 'UNREADABLE' and (missing['objects_unreadable'], missing['native_data'],
                                                 missing['layers_error']) == (None, None, None)


# --- the gate review of Day 8, second pass: native data that names no known marker and no plain header is never text -

#: the header Illustrator's native data begins with when it is plain (measured on Day 8: the decompressed native data and
#: the AIMetaData stream of all 91 house files begin "%!PS-Adobe-3.0 \r\n")
_PS_HEADER = b'%!PS-Adobe-3.0 \r\n'


def _stored_unfiltered(path):
    """``path``'s native-data parts stored again unfiltered, as all 91 house files store theirs (/Filter null): the bytes
    on disk are the native data's own, its marker first, so damage on disk reaches the marker as written."""
    import re
    import fitz
    doc = fitz.open(str(path))
    priv = next(x for x in range(1, doc.xref_length()) if '/AIPrivateData1' in doc.xref_object(x))
    for xref in re.findall(r'/AIPrivateData\d+\s+(\d+)\s+0\s+R', doc.xref_object(priv)):
        doc.update_stream(int(xref), doc.xref_stream(int(xref)), compress=False)
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return path


def test_native_data_that_names_no_known_marker_or_header_is_undecodable_never_read_as_text(tmp_path):
    """Native data is read as text only when it says what it is: behind a compression marker the reader knows (decoded
    first), or plain under Illustrator's own PostScript header. Data that names neither — a ZStandard marker one byte off
    ("%AI25_…", "…_Dat\\x00"), a zlib part whose first bytes are damaged, a bare run with no header — is 'undecodable'
    with no strings, and 'incomplete' with a part missing. The first fix scanned such bytes as plain text and said 'read'
    (a copy of LP-2018.ai with one marker byte changed: 30 noise strings where 1014 were). Plain data under the header
    is 'read', its names what they were."""
    import shutil
    import subprocess
    import zlib
    import fitz
    from apps.pipeline.services import production_finishes as pf
    names = ['Gold Foil', '图层 1']

    def native(name, parts):
        doc = fitz.open(str(_native_data_pdf(tmp_path / name, parts)))
        try:
            return pf.native_strings(doc)
        finally:
            doc.close()

    plain = _PS_HEADER + _NATIVE
    assert native('plain.pdf', [plain[:24], plain[24:]]) == (names, 'read')
    assert native('bare.pdf', [_NATIVE]) == ([], 'undecodable')
    assert native('bare-short.pdf', [_NATIVE, None]) == ([], 'incomplete')
    packed = b'%AI12_CompressedData' + zlib.compress(plain)
    assert native('zlib.pdf', [packed]) == (names, 'read')
    assert native('zlib-damaged.pdf', [bytes(b ^ 0xFF for b in packed[:8]) + packed[8:]]) == ([], 'undecodable')
    if shutil.which('zstd'):
        frame = subprocess.run(['zstd', '-c'], input=plain, capture_output=True, check=True).stdout
        assert native('zstd.pdf', [b'%AI24_ZStandard_Data' + frame]) == (names, 'read')
        for n, marker in enumerate((b'%AI25_ZStandard_Data', b'%AI24_ZStandard_Dat\x00')):
            assert native('zstd-marker-%d.pdf' % n, [marker + frame]) == ([], 'undecodable')
            assert native('zstd-marker-short-%d.pdf' % n, [marker + frame, None]) == ([], 'incomplete')


def test_a_native_marker_damaged_on_disk_is_counted_by_the_census_never_read_clean(tmp_path):
    """The gate review's repro in the house files' own layout (the part stored unfiltered, its marker first): with the
    marker's version digit damaged on disk the file still opens, finishes_of says 'undecodable' with no native strings
    and credits no finish, and the census counts and names it (the first fix: 'read', and a clean census); the whole
    file's native "Gold Foil" stays its one finish."""
    import shutil
    import subprocess
    import zlib
    from apps.pipeline.services import production_finishes as pf
    plain = _PS_HEADER + _NATIVE
    packs = [(b'%AI12_CompressedData', zlib.compress(plain))]
    if shutil.which('zstd'):
        packs.append((b'%AI24_ZStandard_Data', subprocess.run(['zstd', '-c'], input=plain, capture_output=True,
                                                               check=True).stdout))
    for n, (marker, payload) in enumerate(packs):
        whole = _stored_unfiltered(_native_data_pdf(tmp_path / ('whole-%d.pdf' % n), [marker + payload]))
        raw = whole.read_bytes()
        assert raw.count(marker) == 1
        k = raw.index(marker) + 4                                       # "%AI12" → "%AI13", "%AI24" → "%AI25"
        damaged = tmp_path / ('damaged-%d.pdf' % n)
        damaged.write_bytes(raw[:k] + bytes([raw[k] + 1]) + raw[k + 1:])
        rec = pf.finishes_of(whole)
        assert (rec['native_data'], rec['native_strings'], set(rec['finishes'])) == ('read', 2, {'hot foil gold'})
        rec = pf.finishes_of(damaged)
        assert rec['state'] == 'OPENED' and (rec['native_data'], rec['native_strings'], rec['finishes']) == (
            'undecodable', 0, {})
        assert (rec['objects_unreadable'], rec['layers_error']) == (0, None)
        seen = pf.census([whole, damaged])
        assert (seen['opened_with_an_unreadable_channel'], seen['paths_with_an_unreadable_channel']) == (1, [str(damaged)])
        assert seen['files_by_finish'] == {'hot foil gold': 1}


# --- Day 8 residual: a file MuPDF repaired, a native part it warned about, the census arms no test pinned -----------

#: plain native data whose names say no finish (the layers "图层 1" and "Artwork"): the house-shaped file below then
#: declares its one finish by its ink alone
_NAMES_ONLY = _PS_HEADER + b'%%AI8_BeginLayer\n(\xe5\x9b\xbe\xe5\xb1\x82 1) Ln\n(Artwork) Ln\n'
#: plain native data long enough that damage late in its Flate stream leaves a long head that still decodes (402 names)
_LONG_PLAIN = _PS_HEADER + _NATIVE + b''.join(b'(Layer %d name) Ln\n' % n for n in range(400))


def _house_shaped_pdf(path):
    """A real one-page PDF in the house files' own layout: the page's /PieceInfo /Illustrator /Private dict names its
    native data (_NAMES_ONLY) in two parts stored unfiltered, as all 91 house files store theirs, and the page's
    resources name a Separation ink "Gold Foil", the last object in the file (PyMuPDF writes objects in number order).
    Returns the path, the private dict's object number and the ink's."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    refs = []
    for number, part in enumerate((_NAMES_ONLY[:24], _NAMES_ONLY[24:]), 1):
        xref = doc.get_new_xref()
        doc.update_object(xref, '<< >>')
        doc.update_stream(xref, part, compress=False)
        refs.append('/AIPrivateData%d %d 0 R' % (number, xref))
    priv = doc.get_new_xref()
    doc.update_object(priv, '<< %s /NumBlock %d >>' % (' '.join(refs), len(refs)))
    doc.xref_set_key(page.xref, 'PieceInfo', '<< /Illustrator << /Private %d 0 R >> >>' % priv)
    ink = doc.get_new_xref()
    doc.update_object(ink, '[/Separation /Gold#20Foil /DeviceCMYK << /FunctionType 2 /Domain [0 1] /C0 [0 0 0 0] '
                           '/C1 [0 0.2 0.8 0.1] /N 1 >>]')
    _kind, resources = doc.xref_get_key(page.xref, 'Resources')
    doc.xref_set_key(int(resources.split()[0]), 'ColorSpace', '<< /CS0 %d 0 R >>' % ink)
    doc.save(str(path))
    doc.close()
    return path, priv, ink


def _cut_before(path, xref, out):
    """``path``'s bytes up to object ``xref``, written to ``out``: the file cut short as a transfer or a full disk cuts
    it — that object, every one after it and the cross-reference table gone (MuPDF repairs it on open, measured)."""
    raw = path.read_bytes()
    out.write_bytes(raw[:raw.index(b'\n%d 0 obj' % xref) + 1])
    return out


def _offset_moved(path, xref, out):
    """``path`` with object ``xref``'s cross-reference entry pointing 3 bytes past the object: the file opens
    unrepaired, and MuPDF repairs it the first time that object is read (measured on PyMuPDF 1.28 / MuPDF 1.29)."""
    raw = path.read_bytes()
    at = re.search(rb'\nxref\r?\n0 \d+\r?\n', raw).end() + 20 * xref
    entry = raw[at:at + 20]
    out.write_bytes(raw[:at] + b'%010d' % (int(entry[:10]) + 3) + entry[10:] + raw[at + 20:])
    return out


def _damage_late(path, xref, out):
    """``path`` with one byte of object ``xref``'s Flate-filtered stream flipped at 90 % of its length, as a disk or a
    transfer damages it: PyMuPDF decodes it without raising, to garbled bytes of about its length (measured)."""
    raw = path.read_bytes()
    start = raw.index(b'stream', raw.index(b'\n%d 0 obj' % xref)) + len(b'stream')
    start += 2 if raw[start:start + 2] == b'\r\n' else 1
    end = raw.index(b'endstream', start)
    k = start + (end - start) * 9 // 10
    out.write_bytes(raw[:k] + bytes([raw[k] ^ 0xFF]) + raw[k + 1:])
    return out


def _part_xrefs(path):
    """The object numbers of ``path``'s native-data parts, as its private dict names them."""
    import fitz
    doc = fitz.open(str(path))
    try:
        priv = next(x for x in range(1, doc.xref_length()) if '/AIPrivateData1' in doc.xref_object(x))
        return [int(x) for x in re.findall(r'/AIPrivateData\d+\s+(\d+)\s+0\s+R', doc.xref_object(priv))]
    finally:
        doc.close()


def test_a_file_mupdf_repaired_is_said_and_counted_never_read_clean(tmp_path, monkeypatch):
    """A house-shaped file cut short: MuPDF repairs it on open and drops what it lost without raising. Cut before the
    ink, the file's one finish is gone and every channel read clean (the old record: OPENED, no colourant,
    objects_unreadable 0, native 'read', a clean census — finding 1); cut before the private dict, its native data
    read 'absent' (finding 2). The record now says 'repaired'; a repaired file's native data is never 'absent'
    (absence cannot be told from loss: 'incomplete'), in native_strings and in the record whatever native_strings
    said; the census counts and names both. The whole file reads as before, 'repaired' False."""
    import fitz
    from apps.pipeline.services import production_finishes as pf
    whole, priv, ink = _house_shaped_pdf(tmp_path / 'whole.pdf')
    no_ink = _cut_before(whole, ink, tmp_path / 'cut-before-the-ink.pdf')
    no_priv = _cut_before(whole, priv, tmp_path / 'cut-before-the-private-dict.pdf')
    rec = pf.finishes_of(whole)
    assert rec['state'] == 'OPENED' and rec['finishes'] == {'hot foil gold': [{'channel': 'spot colourant',
                                                                               'name': 'Gold Foil'}]}
    assert (rec['repaired'], rec['objects_unreadable'], rec['native_data'], rec['native_strings'],
            rec['layers_error']) == (False, 0, 'read', 2, None)
    rec = pf.finishes_of(no_ink)
    assert rec['state'] == 'OPENED' and (rec['colourants'], rec['finishes']) == ([], {})      # no finish invented
    assert (rec['repaired'], rec['objects_unreadable'], rec['native_data'], rec['native_strings'],
            rec['layers_error']) == (True, 0, 'read', 2, None)
    rec = pf.finishes_of(no_priv)
    assert rec['state'] == 'OPENED' and (rec['repaired'], rec['native_data'], rec['native_strings'],
                                         rec['finishes']) == (True, 'incomplete', 0, {})
    doc = fitz.open(str(no_priv))
    try:
        assert doc.is_repaired and pf.native_strings(doc) == ([], 'incomplete')
    finally:
        doc.close()
    absent = tmp_path / 'absent.ai'
    seen = pf.census([whole, no_ink, no_priv, absent])
    assert (seen['files'], seen['unreadable'], seen['opened_with_an_unreadable_channel']) == (4, 1, 2)
    assert seen['paths_with_an_unreadable_channel'] == sorted([str(no_ink), str(no_priv)])
    assert (seen['opened_repaired'], seen['paths_repaired']) == (2, sorted([str(no_ink), str(no_priv)]))
    assert seen['files_by_finish'] == {'hot foil gold': 1}
    assert seen['per_file'][str(absent)]['state'] == 'UNREADABLE' and seen['per_file'][str(absent)]['repaired'] is None
    # the record's own rule, whatever the native reader said: a file found repaired is never 'absent'
    monkeypatch.setattr(pf, 'native_strings', lambda doc: ([], 'absent'))
    assert (pf.finishes_of(no_ink)['native_data'], pf.finishes_of(whole)['native_data']) == ('incomplete', 'absent')


def test_a_repair_made_while_the_file_is_read_is_said_too(tmp_path):
    """MuPDF also repairs lazily: a file whose cross-reference table points beside an object opens unrepaired
    (is_repaired False) and is repaired the first time that object is read — so 'repaired' is read after every channel
    was read, never at open alone. The repair finds the ink again (its finish credited, as read) and the file is
    counted: its table was broken. Its native data, read after the repair's warnings, still reads 'read': what MuPDF
    said before a part's read is never laid on that part."""
    import fitz
    from apps.pipeline.services import production_finishes as pf
    whole, _priv, ink = _house_shaped_pdf(tmp_path / 'whole.pdf')
    moved = _offset_moved(whole, ink, tmp_path / 'moved.pdf')
    doc = fitz.open(str(moved))
    try:
        assert doc.is_repaired is False                         # at open MuPDF has repaired nothing yet
    finally:
        doc.close()
    rec = pf.finishes_of(moved)
    assert rec['state'] == 'OPENED' and (rec['colourants'], set(rec['finishes'])) == (['Gold Foil'],
                                                                                      {'hot foil gold'})
    assert (rec['repaired'], rec['objects_unreadable'], rec['native_data'], rec['native_strings'],
            rec['layers_error']) == (True, 0, 'read', 2, None)
    seen = pf.census([whole, moved])
    assert (seen['opened_with_an_unreadable_channel'], seen['paths_repaired']) == (1, [str(moved)])


def test_a_native_part_mupdf_warns_about_is_undecodable_never_read_as_text(tmp_path):
    """_stream said a part whose data will not inflate reads b''. Measured false: a Flate part damaged late decodes,
    without raising, to garbled bytes of about its length, MuPDF saying only "ignoring zlib error: incorrect data
    check" — and the native data read 'read', its garbled bytes scanned as names. MuPDF's warnings are now read around
    each part's read: a part it warned about that still returned bytes is never read as text — 'undecodable', or
    'incomplete' with a part missing — and the census counts the file (not repaired: its table is whole)."""
    import fitz
    from apps.pipeline.services import production_finishes as pf
    whole = _native_data_pdf(tmp_path / 'whole.pdf', [_LONG_PLAIN])
    short = _native_data_pdf(tmp_path / 'short.pdf', [_LONG_PLAIN], numblock=2)
    [part] = _part_xrefs(whole)
    damaged = _damage_late(whole, part, tmp_path / 'damaged.pdf')
    damaged_short = _damage_late(short, _part_xrefs(short)[0], tmp_path / 'damaged-short.pdf')
    doc = fitz.open(str(whole))
    try:
        names, state = pf.native_strings(doc)
        assert state == 'read' and len(names) == 402 and 'Gold Foil' in names
    finally:
        doc.close()
    doc = fitz.open(str(damaged))
    try:
        fitz.TOOLS.mupdf_warnings()
        garbled = doc.xref_stream(part)
        said = fitz.TOOLS.mupdf_warnings()
        assert garbled and garbled != _LONG_PLAIN and 'zlib' in said    # the premise: bytes, not b'', not the part
        assert pf.native_strings(doc) == ([], 'undecodable')
    finally:
        doc.close()
    doc = fitz.open(str(damaged_short))
    try:
        assert pf.native_strings(doc) == ([], 'incomplete')
    finally:
        doc.close()
    rec = pf.finishes_of(damaged)
    assert rec['state'] == 'OPENED' and (rec['native_data'], rec['native_strings'], rec['finishes']) == (
        'undecodable', 0, {})
    assert (rec['repaired'], rec['objects_unreadable'], rec['layers_error']) == (False, 0, None)
    seen = pf.census([whole, damaged])
    assert (seen['opened_with_an_unreadable_channel'], seen['paths_with_an_unreadable_channel']) == (1, [str(damaged)])
    assert seen['files_by_finish'] == {'hot foil gold': 1}


def test_a_warning_mupdf_owes_from_an_earlier_read_is_never_laid_on_a_part(tmp_path):
    """MuPDF folds a warning repeated back to back into a count it says only when its warnings are flushed ("...
    repeated 2 times..."). A count owed from an earlier read — another stream of the file, damaged late, read before
    the native data — is flushed and set aside before each part's read, so a part that reads clean reads 'read'."""
    import fitz
    from apps.pipeline.services import production_finishes as pf
    whole = _native_data_pdf(tmp_path / 'whole.pdf', [_LONG_PLAIN])
    doc = fitz.open(str(whole))
    other = doc.get_new_xref()
    doc.update_object(other, '<< >>')
    doc.update_stream(other, _LONG_PLAIN)
    doc.save(str(tmp_path / 'two-streams.pdf'))
    doc.close()
    damaged = _damage_late(tmp_path / 'two-streams.pdf', other, tmp_path / 'other-damaged.pdf')
    doc = fitz.open(str(damaged))
    try:
        assert doc.xref_stream(other) != _LONG_PLAIN            # another reader's read: MuPDF warned, and owes a count
        names, state = pf.native_strings(doc)
        assert state == 'read' and len(names) == 402
    finally:
        doc.close()


def test_the_census_counts_a_file_whose_native_data_alone_is_incomplete(tmp_path):
    """The census predicate's 'incomplete' arm, which no test pinned (a census that ignored it passed every finishes
    test): fewer parts than /NumBlock make the native data 'incomplete' while every other channel reads clean — not
    repaired, every object read, the layers read — and the census still counts and names the file."""
    from apps.pipeline.services import production_finishes as pf
    plain = _PS_HEADER + _NATIVE
    whole = _native_data_pdf(tmp_path / 'whole.pdf', [plain[:24], plain[24:]])
    short = _native_data_pdf(tmp_path / 'short.pdf', [plain[:24], plain[24:]], numblock=3)
    rec = pf.finishes_of(whole)
    assert (rec['native_data'], rec['repaired'], rec['objects_unreadable'], rec['layers_error']) == ('read', False, 0,
                                                                                                    None)
    rec = pf.finishes_of(short)
    assert rec['state'] == 'OPENED' and rec['native_data'] == 'incomplete'
    assert (rec['repaired'], rec['objects_unreadable'], rec['layers_error']) == (False, 0, None)    # its one arm
    seen = pf.census([whole, short])
    assert (seen['opened_with_an_unreadable_channel'], seen['paths_with_an_unreadable_channel']) == (1, [str(short)])


def test_the_census_counts_a_file_whose_layers_alone_could_not_be_read(tmp_path, monkeypatch):
    """The census predicate's layers_error arm, which no test pinned: of two files with the same layer "UV", the one
    whose layers PyMuPDF raised on (the test makes get_ocgs raise for that file alone) is counted and named, every other
    channel of it clean; only the other file's layer is credited a finish."""
    import fitz
    from apps.pipeline.services import production_finishes as pf
    paths = []
    for name in ('read.pdf', 'raised.pdf'):
        doc = fitz.open()
        page = doc.new_page(width=200, height=200)
        page.insert_text((20, 40), 'artwork', oc=doc.add_ocg('UV'))
        doc.save(str(tmp_path / name))
        doc.close()
        paths.append(tmp_path / name)
    read, raised = paths
    get_ocgs = fitz.Document.get_ocgs

    def raising_for_one(self):
        if self.name == str(raised):
            raise RuntimeError('code=7: corrupt object stream')
        return get_ocgs(self)
    monkeypatch.setattr(fitz.Document, 'get_ocgs', raising_for_one)
    rec = pf.finishes_of(read)
    assert (rec['layers'], rec['layers_error'], set(rec['finishes'])) == (['UV'], None, {'spot UV'})
    rec = pf.finishes_of(raised)
    assert rec['state'] == 'OPENED' and (rec['layers'], rec['layers_error'], rec['finishes']) == (
        [], 'RuntimeError', {})
    assert (rec['repaired'], rec['objects_unreadable'], rec['native_data']) == (False, 0, 'absent')    # its one arm
    seen = pf.census([read, raised])
    assert (seen['opened_with_an_unreadable_channel'], seen['paths_with_an_unreadable_channel']) == (1, [str(raised)])
    assert seen['files_by_finish'] == {'spot UV': 1}


# --- Day 8 residual: the plate proof — unmeasured never passes, measured never filed as missing ---------------------

#: the plate proof's record on the normal path — its keys as they were before the residual fixes
NORMAL_KEYS = {'latin_copy_found', 'arabic_copy_found', 'mark_best_score', 'device_line_energy_ratio',
               'device_pattern_ncc', 'thresholds', 'holds'}
#: find_mark's reason for a picture as small as 40 × 40 px (every scale of the template is larger) and for our mark
#: printed in the ground's own colour (its template is flat in grey at every scale)
TOO_LARGE_WHY = ('no scale could be tried: of the 17 from 0.6 to 1.4, the template is as large as the picture at 17 '
                 'and flat in grey at 0, a grey std under 1 (a mark that does not stand off its ground in grey)')
FLAT_WHY = ('no scale could be tried: of the 17 from 0.6 to 1.4, the template is as large as the picture at 0 '
            'and flat in grey at 17, a grey std under 1 (a mark that does not stand off its ground in grey)')


def _clean(tmp_path):
    clean = tmp_path / 'clean.png'
    Image.fromarray(_ivory_plate()).save(clean)
    return clean


def _flat_ink(lay):
    """The layout with our mark printed in the ground's own colour: its template is flat in grey at every scale."""
    return dict(lay, roles=dict(lay['roles'], logo=lay['ink']['dominant']))


def test_our_mark_matched_at_no_scale_has_no_score_and_says_why(lid, tmp_path):
    """A match is measured on the clean plate; printed in the ground's own colour, or on a picture smaller than the
    template at every scale, no scale is tried: no score and no box (they read -1.0 at a box at the origin), and why."""
    lay = lid.layout('C', lid.options('C')[0])
    clean = _clean(tmp_path)
    found = lid.find_mark(clean, lay, tmp_path)
    assert -1.0 <= found['score'] <= 1.0 and len(found['box_mm']) == 4 and 'not_measured' not in found
    flat = lid.find_mark(clean, _flat_ink(lay), tmp_path)
    assert flat == {'box_mm': None, 'score': None, 'not_measured': FLAT_WHY}
    tiny = tmp_path / 'tiny.png'
    Image.fromarray(_ivory_plate()[:40, :40]).save(tiny)
    assert lid.find_mark(tiny, lay, tmp_path) == {'box_mm': None, 'score': None, 'not_measured': TOO_LARGE_WHY}


def test_the_plate_proof_does_not_hold_when_our_mark_could_not_be_looked_for(lid, tmp_path):
    """The clean plate holds, its record's keys as they were; with our mark in the ground's own colour the proof does
    not hold (it held, on a score of -1.0 read as "our mark is not on the plate"): the score is None, and named."""
    lay = lid.layout('C', lid.options('C')[0])
    clean = _clean(tmp_path)
    proof = lid.prove_plate('C', lay, clean, tmp_path)
    assert proof['holds'] and set(proof) == NORMAL_KEYS
    proof = lid.prove_plate('C', _flat_ink(lay), clean, tmp_path)
    assert not proof['holds'] and proof['mark_best_score'] is None
    assert proof['not_measured'] == ['our mark could not be looked for on the plate — ' + FLAT_WHY]
    json.dumps(proof, allow_nan=False)


def test_reading_a_sketch_where_our_mark_matches_at_no_scale_keeps_the_specs_place(lid, tmp_path, monkeypatch):
    """read_sketch treats a mark matched at no scale as a low score is treated — no anchor, the spec's place stands —
    explicitly, and says why; designer_eye reports no sketch place for a match never made (it reported (0.0, 0.0))."""
    from apps.pipeline.services import concept_sketches as cs
    monkeypatch.setattr(cs, 'ocr_words', lambda png, **kw: [])                # a clean read, no word on it
    sketch = tmp_path / 'lid.png'
    Image.fromarray(_ivory_plate()[:40, :40]).save(sketch)                      # smaller than the mark at every scale
    option = lid.options('C')[0]
    read = lid.read_sketch('C', option, sketch, tmp_path)
    assert read['measured']['logo'] == {'box_mm': None, 'score': None, 'not_measured': TOO_LARGE_WHY}
    assert 'logo' not in read['anchors']
    assert 'logo: not measured on the sketch — %s — the spec\'s place stands' % TOO_LARGE_WHY in read['notes']
    eye = lid.designer_eye(read, lid.layout('C', option, anchors=read['anchors']))
    assert not [d for d in eye if d.startswith('logo: sketch at')]


@pytest.mark.parametrize('failing', [('eng', 11), ('eng', 6), ('ara', 11)])
def test_an_ocr_failure_without_a_message_is_named_and_never_holds(lid, tmp_path, monkeypatch, failing):
    """An OCRFailed whose message is empty is still a failed read: named under not_measured (it was dropped on the
    message's truthiness), its copy None, and the proof does not hold (it held: None read as "no copy found")."""
    from apps.pipeline.services import concept_sketches as cs
    real = cs.ocr_words

    def ocr_words(png, *, lang='eng', psm=11):
        if (lang, psm) == failing:
            raise cs.OCRFailed()                                               # str() of it is ''
        return real(png, lang=lang, psm=psm)

    monkeypatch.setattr(cs, 'ocr_words', ocr_words)
    lay = lid.layout('C', lid.options('C')[0])
    proof = lid.prove_plate('C', lay, _clean(tmp_path), tmp_path)
    assert not proof['holds']
    assert proof['not_measured'] == ['the OCR failed, so the plate\'s copy is not read: tesseract (%s, psm %d) raised '
                                     'OCRFailed without a message' % failing]
    copy = 'arabic_copy_found' if failing[0] == 'ara' else 'latin_copy_found'
    assert proof[copy] is None
    json.dumps(proof, allow_nan=False)


def test_line_energy_over_the_device_and_none_elsewhere_is_a_measured_detection(lid, tmp_path):
    """Our device's lines in white on black: line energy over the device, none elsewhere. Both energies are measured,
    so a line system is detected (line_system_detected, with the energy over the device), never filed under
    not_measured; there is no finite ratio (None), and the proof does not hold."""
    import numpy as np
    lay = lid.layout('C', lid.options('C')[0])
    lines = lid.footprint(lay, tmp_path, keep_mark=lambda m: True, rule=False, grow_mm=0.0, parts=('device',))
    black = np.zeros((970, 1536, 3), np.uint8)
    black[lines] = 255
    Image.fromarray(black).save(tmp_path / 'black.png')
    proof = lid.prove_plate('C', lay, tmp_path / 'black.png', tmp_path)
    assert not proof['holds'] and proof['device_line_energy_ratio'] is None
    assert proof['line_system_detected'] is True and proof['device_line_energy'] > 1.0
    assert 'not_measured' not in proof
    json.dumps(proof, allow_nan=False)


def test_an_even_band_over_the_device_has_no_pattern_correlation(lid, tmp_path, monkeypatch):
    """The band-pass made ±5 in a checkerboard (the blurs replaced on the plate's own arrays only): band varies, |band|
    does not, so the correlation of |band| with our lines is undefined — None and named, never NaN (np.corrcoef gave
    NaN and the record stored it; json.dumps wrote NaN)."""
    import cv2
    import numpy as np
    real_blur = cv2.GaussianBlur
    yy, xx = np.indices((970, 1536))
    checker = np.where((yy + xx) % 2 == 0, 5.0, -5.0).astype(np.float32)

    def blur(src, ksize, sigma, *args, **kw):
        if src.dtype == np.float32 and src.shape == checker.shape and tuple(ksize) == (0, 0) and sigma in (1.0, 4.0):
            return checker.copy() if sigma == 1.0 else np.zeros_like(checker)
        return real_blur(src, ksize, sigma, *args, **kw)

    monkeypatch.setattr(cv2, 'GaussianBlur', blur)
    lay = lid.layout('C', lid.options('C')[0])
    proof = lid.prove_plate('C', lay, _clean(tmp_path), tmp_path)
    assert not proof['holds'] and proof['device_pattern_ncc'] is None and proof['device_line_energy_ratio'] == 1.0
    assert proof['not_measured'] == ['the plate\'s line energy is even in strength over the device (|band| does not '
                                     'vary there): the line pattern\'s correlation is undefined, so it is not measured']
    json.dumps(proof, allow_nan=False)


def test_a_pattern_correlation_that_comes_out_nan_is_never_stored(lid, tmp_path, monkeypatch):
    """Whatever makes the correlation NaN, it is None and named, and the proof does not hold."""
    import numpy as np
    monkeypatch.setattr(np, 'corrcoef', lambda *args, **kw: np.full((2, 2), np.nan))
    lay = lid.layout('C', lid.options('C')[0])
    proof = lid.prove_plate('C', lay, _clean(tmp_path), tmp_path)
    assert not proof['holds'] and proof['device_pattern_ncc'] is None
    assert proof['not_measured'] == ['the line pattern\'s correlation over the device came out nan: it is not measured']
    json.dumps(proof, allow_nan=False)


# --- Day 8 residual: the call-log audit never holds on an outcome or a log it could not read ------------------------
# (every audit below is given its log path: audit's default CALL_LOG is bound when audit is defined, so a bare call
# would read the real Day 8 call log)

#: every key the audit returns: the counts as they were, the outcome nobody wrote, and the log's own state
_AUDIT_KEYS = {'calls', 'sent', 'refused', 'non_openai_or_named_tool', 'rejected_or_web_inputs', 'competitor_prompts',
         'sent_without_input_sha256', 'sent_without_prompt', 'unknown_outcome', 'log_present', 'log_empty', 'holds'}
_AUDIT_COUNTS = _AUDIT_KEYS - {'log_present', 'log_empty', 'holds'}


def _audit_made_and_refused(roots):
    """One made row and one refused row, written by ``guarded_call`` itself."""
    name = _png(roots['allowed'] / 'name.png', (12, 34, 56))
    ig.guarded_call(lambda checked: {'image': 'x.png'}, operation='day8/sketch/A-1',
                    inputs=[{'role': 'name lettering', 'path': name}], prompt='flat lid artwork', quality='medium',
                    size='1536x1024')
    with pytest.raises(ig.ImageCallRefused):
        ig.guarded_call(lambda checked: {'image': 'y.png'}, operation='day8/sketch/A-2', inputs=[], quality='medium',
                        prompt='like Pat McGrath', size='1536x1024')
    made, refused = [json.loads(l) for l in (roots['tmp'] / 'calls.jsonl').read_text().splitlines()]
    assert (made['outcome'], refused['outcome']) == ('made', 'refused')
    return made, refused


def test_residual_a_row_whose_outcome_is_not_made_failed_or_refused_never_audits_clean(roots):
    """Only 'made' and 'failed' rows were read and 'refused' counted: a row with no outcome, or with one that is not
    exactly one of the three guarded_call writes, was checked by nothing and the audit still held. It is counted under
    'unknown_outcome' and the audit does not hold; it is neither sent nor refused, and every other count stays as it
    was — calls = sent + refused + unknown_outcome."""
    made, refused = _audit_made_and_refused(roots)
    log = roots['tmp'] / 'edited.jsonl'

    def audit_of(*rows):
        log.write_text(''.join(json.dumps(r) + '\n' for r in (made, refused) + rows))
        return ig.audit(log)

    for label, row in (
            ('no outcome recorded', {k: v for k, v in made.items() if k != 'outcome'}),
            ('an outcome that is not text', dict(made, outcome=None)),
            ('another case', dict(made, outcome='Made')),
            ('a typo', dict(made, outcome='mdae')),
            ('a padded word', dict(made, outcome='made ')),
            ('a word guarded_call never writes', dict(made, outcome='sent')),
            ('a refusal in capitals', dict(refused, outcome='REFUSED'))):
        found = audit_of(row)
        assert found['holds'] is False, label
        assert found['unknown_outcome'] == 1, label
        assert (found['calls'], found['sent'], found['refused']) == (3, 1, 1), label
        assert found['calls'] == found['sent'] + found['refused'] + found['unknown_outcome'], label
        assert (found['non_openai_or_named_tool'], found['rejected_or_web_inputs'], found['competitor_prompts'],
                found['sent_without_input_sha256'], found['sent_without_prompt']) == (0, 0, 0, 0, 0), label
    two = audit_of(dict(made, outcome='Made'), dict(made, outcome=None))
    assert two['holds'] is False and two['unknown_outcome'] == 2 and two['calls'] == 4
    clean = audit_of()
    assert clean['holds'] is True and clean['unknown_outcome'] == 0 and (clean['sent'], clean['refused']) == (1, 1)
    failed = audit_of(dict(made, outcome='failed'))                 # a failed call is a known outcome: sent, and read
    assert failed['holds'] is True and failed['unknown_outcome'] == 0
    assert (failed['calls'], failed['sent'], failed['refused']) == (3, 2, 1)
    assert failed['calls'] == failed['sent'] + failed['refused'] + failed['unknown_outcome']


def test_residual_a_missing_call_log_never_audits_clean_and_counts_nothing(roots):
    """A missing log was read as no rows and audited holds=True with calls=0. Nothing was read, so nothing is asserted:
    the audit does not hold, says log_present False, and every count is None — unknown, never 0."""
    missing = roots['tmp'] / 'no-such-log.jsonl'
    found = ig.audit(missing)
    assert found['holds'] is False
    assert set(found) == _AUDIT_KEYS
    assert found['log_present'] is False and found['log_empty'] is None
    assert {k: found[k] for k in _AUDIT_COUNTS} == dict.fromkeys(_AUDIT_COUNTS)
    assert not missing.exists()                                      # the audit never creates the log it reads


def test_residual_a_call_log_with_no_rows_never_audits_clean(roots):
    """guarded_call writes one row for every call it is given, so a Day 8 log with no rows cannot tell "no call was
    made" from "its rows were lost": it is reported (log_empty True, its counts measured as 0) and does not hold."""
    log = roots['tmp'] / 'empty.jsonl'
    for text in ('', '\n', ' \n\n\t\n'):
        log.write_text(text)
        found = ig.audit(log)
        assert found['holds'] is False, repr(text)
        assert set(found) == _AUDIT_KEYS, repr(text)
        assert found['log_present'] is True and found['log_empty'] is True, repr(text)
        assert {k: found[k] for k in _AUDIT_COUNTS} == dict.fromkeys(_AUDIT_COUNTS, 0), repr(text)


def test_residual_a_log_that_records_its_calls_audits_as_before(roots):
    """The normal path is unchanged: a made and a refused call hold, and a log of refusals alone — every call it was
    given, none sent — still holds; both say the log was present and not empty."""
    made, refused = _audit_made_and_refused(roots)
    assert ig.audit(roots['tmp'] / 'calls.jsonl') == {
        'calls': 2, 'sent': 1, 'refused': 1, 'non_openai_or_named_tool': 0, 'rejected_or_web_inputs': 0,
        'competitor_prompts': 0, 'sent_without_input_sha256': 0, 'sent_without_prompt': 0, 'unknown_outcome': 0,
        'log_present': True, 'log_empty': False, 'holds': True}
    refusals = roots['tmp'] / 'refusals.jsonl'
    refusals.write_text(json.dumps(refused) + '\n')
    only = ig.audit(refusals)
    assert only['holds'] is True
    assert (only['calls'], only['sent'], only['refused'], only['unknown_outcome']) == (1, 0, 1, 0)
    assert only['log_present'] is True and only['log_empty'] is False


# --- Day 8 residual: the guard's own record is never overwritten, and a prompt's line separators stay inside its row ---

def test_an_extra_field_never_overwrites_what_the_guard_records(roots):
    """guarded_call spread its caller's **extra AFTER its own fields, so an extra 'outcome' could log a paid call as
    'refused' (never audited) or swap the model. The caller's fields now come first and the guard's own win."""
    name = _png(roots['allowed'] / 'name.png', (12, 34, 56))
    ig.guarded_call(lambda checked: {'image': 'x.png'}, operation='day8/sketch/A-1',
                    inputs=[{'role': 'name lettering', 'path': name}], prompt='flat lid artwork', quality='medium',
                    size='1536x1024', outcome='refused', model='another-model', option='A1')
    row = json.loads((roots['tmp'] / 'calls.jsonl').read_text())
    assert row['outcome'] == 'made' and row['model'] == 'gpt-image-2' and row['option'] == 'A1'
    assert ig.audit(roots['tmp'] / 'calls.jsonl')['sent'] == 1


def test_a_prompt_with_a_unicode_line_separator_audits_as_one_row(roots):
    """log_call writes with ensure_ascii=False; str.splitlines() also splits on U+2028 and U+0085 inside a JSON
    string, which broke the row in two. The audit now splits on newlines only."""
    name = _png(roots['allowed'] / 'name.png', (12, 34, 56))
    ig.guarded_call(lambda checked: {'image': 'x.png'}, operation='day8/sketch/A-1',
                    inputs=[{'role': 'name lettering', 'path': name}], prompt='flat lid artwork\u0085here',
                    quality='medium', size='1536x1024')
    result = ig.audit(roots['tmp'] / 'calls.jsonl')
    assert result['calls'] == 1 and result['sent'] == 1 and result['holds'] is True
