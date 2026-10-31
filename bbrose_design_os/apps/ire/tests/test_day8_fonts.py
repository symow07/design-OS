"""Day 8 §1: the type book and the variable faces' static instances.

1a — a variable face draws its DEFAULT instance wherever a renderer opens the file as it is (Chivo Mono's, Montserrat's
default is Thin): static instances with every axis pinned (``font_instances``), the catalogue pointed at them, and the
stem each face draws measured against the weight it declares. 1b — the type book (``type_book``): every house and
GRANTED family once, grouped by class, the licence under each, the theme marked, the Arabic faces the emitter can draw
flagged; it builds offline from bundled fonts."""
import json
import types
from pathlib import Path

import pytest
from django.test import override_settings
from fontTools.ttLib import TTFont

from apps.ire import font_instances as FI
from apps.ire import font_pool, font_roles, type_book as TB

ROOT = Path(__file__).resolve().parents[4]
STATIC = Path(__file__).resolve().parents[3] / 'static' / 'fonts'
MONTSERRAT = STATIC / 'brand2026' / 'Montserrat' / 'Montserrat[wght].ttf'


def test_a_variable_face_at_its_heaviest_instance_draws_a_heavier_stem_and_the_catalogue_resolves_its_static_file(tmp_path, monkeypatch):
    """GOLDEN: Montserrat[wght] (100–900, default Thin) at its heaviest instance measures a stem at least 1.5× its
    lightest; font_roles.instance_at — what a line asking 900 draws — resolves the pre-made static file, re-hashed, with
    the instance's provenance beside it (source digest, every axis, never the default)."""
    granted = font_roles.catalogue()['Montserrat[wght]']
    monkeypatch.setattr(FI, 'INSTANCE_DIR', tmp_path)
    monkeypatch.setattr(font_roles, '_instance_cache', {})
    light = FI.make_instance(granted['path'], {'wght': 100}, family='Montserrat', licence='SIL OFL 1.1', source_stem='Montserrat[wght]')
    heavy = FI.make_instance(granted['path'], {'wght': 900}, family='Montserrat', licence='SIL OFL 1.1', source_stem='Montserrat[wght]')
    s_light = FI.stem_em(FI._abs(light['path']))['stem_em']
    s_heavy = FI.stem_em(FI._abs(heavy['path']))['stem_em']
    assert s_heavy >= 1.5 * s_light, (s_light, s_heavy)
    assert abs(FI.stem_em(granted['path'])['stem_em'] - s_light) < 0.005          # the file as it is draws its Thin default
    inst = font_roles.instance_at('Montserrat[wght]', 900.0)
    assert inst['premade'] is True and Path(inst['path']) == FI._abs(heavy['path']) and inst['sha256'] == heavy['sha256']
    assert inst['postscript'] == 'Montserrat-Black' and inst['axes'] == {'wght': 900.0}
    assert inst['derived_from_sha256'] == granted['sha256'] and inst['source_default_instance'] == 'Montserrat-Thin'
    with TTFont(inst['path']) as ft:
        assert 'fvar' not in ft and 'gvar' not in ft and ft['OS/2'].usWeightClass == 900
    meta = json.loads((tmp_path / 'Montserrat-Black.json').read_text())
    assert meta['source_sha256'] == granted['sha256'] and meta['axes'] == {'wght': 900.0} and meta['licence'] == 'SIL OFL 1.1'
    assert meta['sha256'] == heavy['sha256'] and 'never distributed' in meta['use']
    # a weight with no pre-made file is derived as before (the temp dir), never the default instance
    monkeypatch.setattr(font_roles, '_instance_cache', {})
    other = font_roles.instance_at('Montserrat[wght]', 600.0)
    assert not other.get('premade') and other['postscript'] == 'Montserrat-SemiBold'


def test_the_weight_band_reads_two_static_faces_within_their_declared_weights():
    reg, bold = FI.measure(STATIC / 'NotoSans-Regular.ttf'), FI.measure(STATIC / 'NotoSans-Bold.ttf')
    assert (reg['us_weight_class'], bold['us_weight_class']) == (400, 700)
    assert reg['glyph'] == bold['glyph'] == 'l'
    assert reg['verdict'] == bold['verdict'] == 'within' and reg['agrees'] and bold['agrees']
    assert bold['stem_em'] > 1.4 * reg['stem_em']
    # the band catches a face drawing another weight than it names: Montserrat's Thin default read as a Black
    assert FI.band_verdict(900, FI.stem_em(MONTSERRAT)['stem_em']) == 'lighter than declared'
    assert FI.band_verdict(100, bold['stem_em']) == 'heavier than declared'


def test_the_type_book_builds_offline_from_bundled_fonts(tmp_path):
    """Three bundled static faces and one variable face, no catalogue, no network: the JSON and the PDF, the families
    grouped by class, the licence under each, the theme marked, the Arabic face flagged emitter-capable."""
    ofl = STATIC / 'OFL.txt'
    faces = [TB.face_from_file(STATIC / 'NotoSans-Regular.ttf', licence_path=ofl),
             TB.face_from_file(STATIC / 'NotoSans-Bold.ttf', licence_path=ofl),
             TB.face_from_file(STATIC / 'NotoNaskhArabic-Regular.ttf', licence_path=ofl,
                               theme_roles=[{'role': 'arabic-body', 'weight': None, 'postscript': 'NotoNaskhArabic-Regular'}]),
             TB.face_from_file(MONTSERRAT, licence_path=MONTSERRAT.parent / 'OFL.txt')]
    rec = TB.build(faces, tmp_path, instance_dir=tmp_path / 'instanced', title='fixture type book')
    on_disk = json.loads((tmp_path / 'type-book.json').read_text())
    assert on_disk['complete'] is True and (tmp_path / 'type-book.pdf').stat().st_size > 10_000
    sans = {f['family']: f for f in rec['latin']['sans']}
    assert set(sans) == {'Montserrat', 'Noto Sans'} and not rec['latin']['unclassified']
    noto = sans['Noto Sans']
    assert noto['regular']['weight'] == 400 and noto['heaviest']['weight'] == 700
    assert noto['heaviest']['stem_em'] > noto['regular']['stem_em']
    mont = sans['Montserrat']
    assert mont['heaviest']['instance'] and mont['heaviest']['weight'] == 900.0 and mont['heaviest']['stem_em'] >= 0.18
    assert Path(mont['heaviest']['path_drawn']).parent == tmp_path / 'instanced'
    assert mont['regular']['instance']['axes'] == {'wght': 400.0}
    naskh = rec['arabic']['naskh']
    assert [f['family'] for f in naskh] == ['Noto Naskh Arabic'] and naskh[0]['emitter_capable'] is True and naskh[0]['theme']
    assert naskh[0]['files'][0]['emitter_capable'] is True and naskh[0]['specimen']['regular']['by'].startswith('reportlab')
    assert rec['arabic_path'].startswith("the engine's own emitter path: apps.dielines.exporters.text_intl.shape_ar")
    for script in ('latin', 'arabic'):
        for fams in rec[script].values():
            for f in fams:
                assert f['licence'] and f['licence'][0]['licence'] == 'SIL Open Font License, Version 1.1'
                assert f['licence'][0]['evidence_sha256'] in {TB._sha(ofl), TB._sha(MONTSERRAT.parent / 'OFL.txt')}
    import fitz
    with fitz.open(str(tmp_path / 'type-book.pdf')) as doc:
        text = ''.join(p.get_text() for p in doc)
    assert 'Noto Sans' in text and 'THEME' in text and 'emitter-capable' in text
    with pytest.raises(ValueError):
        TB.face_from_file(STATIC / 'NotoSans-Regular.ttf', licence_path=tmp_path / 'no-licence.txt')


def test_the_specimen_classes_go_through_the_reserved_paid_path_and_land_batch_by_batch(tmp_path):
    """The model's classes: one call per batch, reserved first under day8/fonts/ with its cap, each batch appended to the
    jsonl as it lands, folded into the book's classes (a fake client; no network)."""
    ofl = STATIC / 'OFL.txt'
    faces = [TB.face_from_file(STATIC / 'NotoSans-Regular.ttf', licence_path=ofl, stem='a'),
             TB.face_from_file(STATIC / 'NotoSans-Bold.ttf', licence_path=ofl, stem='b', family='Fixture Sans'),
             TB.face_from_file(STATIC / 'NotoNaskhArabic-Bold.ttf', licence_path=ofl, stem='c', family='Fixture Naskh')]
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        images = [b for b in kwargs['messages'][0]['content'] if b.get('type') == 'image']
        items = [{'n': n, 'latin_class': 'sans', 'arabic_class': 'naskh' if n == len(images) and len(images) == 1 else 'none',
                  'confidence': 0.9, 'why': 'fixture'} for n in range(1, len(images) + 1)]
        block = types.SimpleNamespace(type='tool_use', name='record_classes', input={'items': items})
        return types.SimpleNamespace(content=[block], stop_reason='tool_use',
                                     model_dump=lambda mode='json': {'usage': {'input_tokens': 2000, 'output_tokens': 100}})
    with override_settings(RESCUE_SPEND_ROOT=tmp_path / 'spend'):
        done = TB.classify_from_specimens(faces, tmp_path, batch=2, client=types.SimpleNamespace(messages=types.SimpleNamespace(create=create)),
                                          specimen_dir=tmp_path / 'specimens', instance_dir=tmp_path / 'instanced')
        again = TB.classify_from_specimens(faces, tmp_path, batch=2, client=types.SimpleNamespace(messages=types.SimpleNamespace(create=create)),
                                           specimen_dir=tmp_path / 'specimens', instance_dir=tmp_path / 'instanced')
        import sqlite3
        db = sqlite3.connect(str(tmp_path / 'spend' / 'ledger.sqlite3'))
        ops = [r[0] for r in db.execute('SELECT operation FROM calls ORDER BY started_at')]
    assert len(calls) == 2 and ops == ['day8/fonts/classify-01', 'day8/fonts/classify-02']     # the second pass asked nothing
    assert all(c['model'] == 'claude-haiku-4-5' and c['tool_choice'] == {'type': 'tool', 'name': 'record_classes'} for c in calls)
    assert len(done) == 3 and again.keys() == done.keys()
    rows = [json.loads(ln) for ln in (tmp_path / 'fonts-classified.jsonl').read_text().splitlines()]
    assert [r['batch'] for r in rows] == [1, 1, 2] and all(r['operation'].startswith('day8/fonts/classify-') for r in rows)
    folded = TB.classified_map(tmp_path)
    assert folded[faces[2]['sha256']]['arabic_class'] == 'naskh' and folded[faces[0]['sha256']]['latin_class'] == 'sans'


def test_the_pool_catalogue_gives_each_variable_entry_its_instances():
    variable = [e for e in font_pool.catalogue_entries() if e.get('variable')]
    assert len(variable) == 11 and all(isinstance(e.get('instances'), list) for e in variable)
    cat = font_roles.catalogue()
    assert sum(1 for e in cat.values() if e['origin'] == font_pool.ORIGIN) == 328      # no entry added: a field, not entries
    for e in variable:
        for i in e['instances']:                       # var/ is git-ignored: a fresh clone lists none and derives at use
            assert Path(i['path']).exists() and i['wght'] is not None and 'wght' in i['axes']


def test_the_day8_font_records_hold_their_rules():
    out = ROOT / 'docs' / 'audit' / 'day-8' / 'fonts'
    if not (out / 'type-book.json').exists():
        pytest.skip('the Day 8 type book has not been built here')
    book = json.loads((out / 'type-book.json').read_text())
    assert book['complete'] is True
    excluded = font_pool.excluded()
    families = [(s, f) for s in ('latin', 'arabic') for fams in book[s].values() for f in fams]
    assert not ({x['sha256'] for _s, f in families for x in f['files']} & set(excluded))
    assert all(f['licence'] and all(lic['evidence_sha256'] and lic['licence'] for lic in f['licence']) for _s, f in families)
    cat = font_roles.catalogue()
    capable = {x['stem'] for s, f in families if s == 'arabic' for x in f['files'] if x['emitter_capable']}
    assert all(isinstance(x.get('emitter_capable'), bool) for s, f in families if s == 'arabic' for x in f['files'])
    assert {'NotoNaskhArabic-Regular', 'NotoNaskhArabic-Bold'} <= capable and all(cat[s]['arabic'] for s in capable)
    assert {t for t in book['counts']['theme_families']} >= {'Poppins', 'Montserrat', 'Noto Naskh Arabic'}
    vi = json.loads((out / 'variable-instances.json').read_text())
    req = vi['request_chivo_mono_black']
    assert req['stem_em'] >= 1.5 * req['default_instance_stem_em'] and req['verdict'] == 'within'
