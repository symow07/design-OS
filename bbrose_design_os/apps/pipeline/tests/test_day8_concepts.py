"""Day 8 §5 and §8 — the image guard, the sketch and truthful-build invariants, on fixtures; no provider is called."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from PIL import Image

from apps.pipeline.services import round_calls as ig


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


# --- the gate review of Day 8: a failed read, an empty region, a failing proof never pass ---------------------------

def _ivory_plate():
    """The plate of the proof test above: C's ivory ground with a faint grain (seed 0), 970 × 1536."""
    import numpy as np
    rng = np.random.default_rng(0)
    return np.clip(np.array([250, 243, 236]) + rng.normal(0, 1.5, (970, 1536, 3)), 0, 255).astype(np.uint8)


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
