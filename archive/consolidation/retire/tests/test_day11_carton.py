"""Day 11, D-D11-7 / D-D11-8 — the stick carton (``stick_carton``) on our straight tuck end, at $0.

Each carton is built once into the test's own temporary folder with a FIXTURE translations file (test words standing in
for the lead's panel_translate output — never a translation, never in the module), and every claim the record makes is
read back from the written files: the die's segments, the text spans' boxes and sizes, the ActualText words, the EAN
frame's drawn extents, the ink on the flaps. Each check carries a control that must fail (a planted fault)."""
import copy as _copy
import json
import types

import fitz
import numpy as np
import pytest
from PIL import Image

from apps.core.models import AR_UNCONFIRMED
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import palette_box as pb
from apps.pipeline.services import palette_sticker as ps
from apps.pipeline.services import stick_carton as sc

MM = 25.4 / 72.0

# Brand.claims rows in the database's shape, each with its ar_source said (never the row with none: that case is the
# sticker's rule to settle) — the house's record as it stands (every row executor-unconfirmed) and one confirmed
UNCONFIRMED = [{'en': 'Cruelty-free', 'ar': 'خالٍ من القسوة', 'ar_source': AR_UNCONFIRMED},
               {'en': '100% vegan', 'ar': 'نباتي 100٪', 'ar_source': AR_UNCONFIRMED}]
CONFIRMED = [{'en': 'Cruelty-free', 'ar': 'خال من القسوة', 'ar_source': 'OWNER'},
             {'en': '100% vegan', 'ar': 'نباتي 100٪', 'ar_source': 'OWNER'}]

# FIXTURE — test words in the shape of the lead's file, not a translation (the module never holds ES or AR copy)
FIXTURE_WORDS = {
    'es': {'description': 'Barra de labios Enchanted Rose en el tono Wild Rose.',
           'how_to_use': 'Aplicar directamente sobre los labios desde el centro hacia fuera; superponer capas para más color.',
           'warnings': 'Solo para uso externo. Suspender el uso si se produce irritación.',
           'made_in': 'Hecho en EAU.', 'head:how_to_use': 'Modo de empleo', 'head:warnings': 'Advertencias'},
    'ar': {'description': 'أحمر شفاه إنشانتد روز بدرجة وايلد روز.',
           'how_to_use': 'يوضع مباشرة على الشفاه من المنتصف إلى الخارج، مع زيادة الطبقات للحصول على لون أكثر.',
           'warnings': 'للاستخدام الخارجي فقط. يوقف الاستخدام في حال حدوث تهيج.',
           'made_in': 'صنع في الإمارات العربية المتحدة.', 'head:how_to_use': 'طريقة الاستخدام', 'head:warnings': 'تحذيرات'},
}


def fixture_translations(product, path, english=None):
    """A FIXTURE translations file for ``product`` (marked so), in the lead's file's shape."""
    req = sc.translation_request(product)
    if english is not None:
        req = english
    back = {v: k for k, v in sc.LANDS.items()}
    calls = {}
    for call, fields in req.items():
        calls[call] = {'english': fields, 'translations': {
            lang: {key: FIXTURE_WORDS[lang][sc.LANDS[(call, key)]] for key in fields} for lang in ('es', 'ar')}}
    assert len(back) == len(sc.LANDS)
    path.write_text(json.dumps({'schema': sc.TRANSLATIONS_SCHEMA, 'product': product['key'],
                                'fixture': 'TEST ONLY — not a translation', 'model': 'fixture',
                                'spend': {'usd': 0.0, 'calls': 0}, 'calls': calls}, ensure_ascii=False),
                    encoding='utf-8')
    return path


def _build(tmp_path_factory, key, **kw):
    product = sc.PRODUCTS[key]
    out = tmp_path_factory.mktemp('carton-' + key)
    tr = fixture_translations(product, out / 'fixture-translations.json')
    if 'claims' not in kw:
        kw['claims'] = UNCONFIRMED
    record, report = sc.build(out / 'files', product=product, translations=tr, **kw)
    return {'product': product, 'out': out / 'files', 'record': record, 'report': report, 'translations': tr}


def _document(built):
    """The carton's own engine document, as ``build`` makes it (the placeholder front), with what made it."""
    product = built['product']
    translated, prov = sc.load_translations(product, built['translations'])
    blocks = sc.copy(product, translated, prov['model'], ps.arabic_claims(UNCONFIRMED))
    coords, _ = sc.die(product)
    fc_box = sc.faces(coords)
    fc = ps.faces()
    metrics = sc.face_metrics(fc)
    doc, layout = sc.document(product, coords, fc_box, blocks, dict(sc.PLACEHOLDER_COLOURS), None, None, fc, metrics)
    return {'doc': doc, 'layout': layout, 'blocks': blocks, 'coords': coords, 'faces': fc_box, 'fc': fc,
            'metrics': metrics}


def _named(doc, name):
    """The one node of ``doc`` named ``name``."""
    hit = [n for n, _ in doc.walk() if n.name == name]
    assert len(hit) == 1
    return hit[0]


@pytest.fixture(scope='module')
def lipstick(tmp_path_factory):
    return _build(tmp_path_factory, 'lipstick')


@pytest.fixture(scope='module')
def balm(tmp_path_factory):
    return _build(tmp_path_factory, 'lip_balm')


def _spans(pdf):
    """Page 1's text spans: (text, size pt, bbox in flat mm)."""
    out = []
    with fitz.open(str(pdf)) as d:
        for b in d[0].get_text('dict')['blocks']:
            if 'lines' not in b:
                continue
            for ln in b['lines']:
                for sp in ln['spans']:
                    x0, y0, x1, y1 = sp['bbox']
                    out.append((sp['text'], sp['size'], (x0 * MM - sc.BLEED_MM, y0 * MM - sc.BLEED_MM,
                                                         x1 * MM - sc.BLEED_MM, y1 * MM - sc.BLEED_MM)))
    return out


def _own_face(box, record):
    """The face a span stands on: the one whose box holds the span's centre (the faces do not overlap)."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    held = [k for k, f in record['faces'].items()
            if f['box_mm'][0] <= cx <= f['box_mm'][2] and f['box_mm'][1] <= cy <= f['box_mm'][3]]
    assert len(held) <= 1
    return held[0] if held else None


def _inside_its_own_safe_area(box, record, tol=0.02):
    face = _own_face(box, record)
    if face is None:
        return False
    s = record['faces'][face]['safe_mm']
    return box[0] >= s[0] - tol and box[1] >= s[1] - tol and box[2] <= s[2] + tol and box[3] <= s[3] + tol


# --- the die -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('key, flat', [('lipstick', (101.8, 145.25)), ('lip_balm', (93.8, 131.25))])
def test_the_die_is_our_straight_tuck_at_its_print_ready_version_both_tucks_on_the_back(key, flat):
    coords, fold = sc.die(sc.PRODUCTS[key])
    assert coords.derived['template_version'] == '1.4' and coords.derived['ecma_code'] == 'A20.20.01.01'
    assert {t['panel'] for t in coords.derived['tucks']} == {'back'}
    assert (coords.flat_width_mm, coords.flat_height_mm) == flat
    assert coords.derived['glue']['width_mm'] == sc.GLUE_TAB_MM and coords.board_thickness_mm == sc.BOARD_MM
    assert fold['passed'] and len(fold['findings']) == 38


def test_the_die_refuses_a_version_whose_closure_is_not_the_corrected_one(monkeypatch):
    """The control: a print-ready version other than 1.4 is refused before a face is read."""
    from apps.dielines import registry
    monkeypatch.setattr(registry, 'print_ready_version', lambda template: '1.3')
    with pytest.raises(ValueError):
        sc.die(sc.PRODUCTS['lipstick'])


def test_the_fold_check_passes_and_is_recorded(lipstick):
    fold = lipstick['record']['fold_check']
    assert fold['passed'] and fold['failed'] == [] and fold['checks'] == 38


def test_the_fold_check_has_power_on_the_old_closure():
    """The control: the same carton at 1.3 (the bottom tuck on the front under the straight-tuck name) fails it."""
    from apps.dielines.geometry import fold_check
    from apps.dielines.geometry.engine import calculate_dieline
    params = sc.die_input(sc.PRODUCTS['lipstick']).model_copy(update={'template_version': '1.3'})
    check = fold_check.check(calculate_dieline(params))
    assert not check['passed'] and len(check['failed']) > 0


def test_the_die_is_untouched_in_the_written_file_and_a_moved_crease_is_seen(lipstick):
    rec = lipstick['record']['die_untouched']
    assert rec['holds'] and rec['missing_or_moved'] == 0 and rec['segments'] == 185
    coords, _ = sc.die(lipstick['product'])
    again = sc.die_readback(lipstick['out'] / 'carton-artwork.pdf', coords, -sc.BLEED_MM, -sc.BLEED_MM)
    assert again['holds']
    # the control: the same file read against a die whose one crease sits 0.02 mm over
    moved = list(coords.fold_lines)
    x1, y1, x2, y2 = moved[0]
    moved[0] = (x1 + 0.02, y1, x2 + 0.02, y2)
    fake = types.SimpleNamespace(fold_lines=moved, slit_lines=coords.slit_lines, cut_polygon=coords.cut_polygon)
    planted = sc.die_readback(lipstick['out'] / 'carton-artwork.pdf', fake, -sc.BLEED_MM, -sc.BLEED_MM)
    assert not planted['holds'] and planted['missing_or_moved'] == 1


def test_the_die_layers_are_locked_and_the_pages_are_artwork_foil_relief(lipstick):
    with fitz.open(str(lipstick['out'] / 'carton-artwork.pdf')) as d:
        assert d.page_count == 3
        labels = [d[i].get_label() for i in range(3)]
        ocgs = {v['name']: v for v in d.get_ocgs().values()}
    assert labels[0].startswith('1 artwork') and labels[1].startswith('2 foil plate - none') \
        and labels[2].startswith('3 relief plate - none')
    assert {'artwork', 'cut', 'crease'} <= set(ocgs)
    with fitz.open(str(lipstick['out'] / 'carton-artwork.ai')) as d:
        assert {'artwork', 'foil', 'relief', 'cut', 'crease', 'guides'} <= {v['name'] for v in d.get_ocgs().values()}


# --- the copy, from the file -------------------------------------------------------------------------------------------

def test_every_copy_line_is_inside_its_panels_safe_area_read_from_the_file(lipstick):
    rec = lipstick['record']
    assert rec['all_inside_safe'] and lipstick['report']['every_line_inside_its_area']
    spans = _spans(lipstick['out'] / 'carton-artwork.pdf')
    assert len(spans) >= 20
    outside = [(t, b) for t, _, b in spans if not _inside_its_own_safe_area(b, rec)]
    assert outside == []
    # each language on the panel the plan gave it, read from the file
    chosen = lipstick['report']['panel_plan']['chosen']
    by_face = {}
    for t, _, b in spans:
        by_face.setdefault(_own_face(b, rec), []).append(t)
    assert 'Hecho en EAU.' in ' '.join(by_face[[p for p, lang in chosen.items() if lang == 'es'][0]])
    # the controls: a span moved 3.5 mm across its panel's safe edge, and a span moved onto the next panel, are seen
    t, _, b = spans[0]
    assert not _inside_its_own_safe_area((b[0] - 3.5, b[1], b[2] - 3.5, b[3]), rec)
    face = _own_face(b, rec)
    shift = rec['faces'][face]['box_mm'][2] - rec['faces'][face]['box_mm'][0]
    assert _own_face((b[0] + shift, b[1], b[2] + shift, b[3]), rec) != face


def test_nothing_crosses_a_crease_and_a_planted_box_across_one_is_seen(lipstick):
    rec = lipstick['record']
    assert rec['nothing_across_a_crease'] and all(not r['crosses_a_crease'] for r in rec['content'])
    coords, _ = sc.die(lipstick['product'])
    fc_box = sc.faces(coords)
    x = coords.derived['x2']                                # the back | left side crease
    layout = {'elements': [{'panel': 'back', 'element': 'planted', 'flat': (x - 1.0, 50.0, x + 1.0, 52.0)}]}
    row = sc.content_rows(layout, coords, fc_box)[0]
    assert row['crosses_a_crease'] and not row['inside_safe']


def test_the_type_is_never_under_the_floor_and_every_line_is_present(lipstick):
    rep = lipstick['report']
    sizes = [s for _, s, _ in _spans(lipstick['out'] / 'carton-artwork.pdf')]
    assert min(sizes) >= sc.BODY_FLOOR_PT - 1e-3 and rep['smallest_pt'] >= sc.BODY_FLOOR_PT
    assert all(r['size_pt'] >= sc.BODY_FLOOR_PT for r in rep['lines'])
    copy = rep['copy']
    assert copy['all_found'] and copy['dropped'] == [] and copy['moved'] == [] and copy['inci_in_every_language']
    assert copy['net']['found'] and copy['fields']['found']
    for lang in sc.LANGS:
        assert {r['field'] for r in copy['rows'] if r['lang'] == lang and r['found']} == set(sc.ORDER)
    assert sc.sizes()[-1] == sc.BODY_FLOOR_PT and min(sc.sizes()) == sc.BODY_FLOOR_PT


def test_a_copy_area_too_small_stays_at_the_floor_and_says_its_overflow_line_by_line(lipstick):
    """The control on the fit: given a band too small, the size stops at 5 pt, every line is still laid (none dropped)
    and each one past the area says by how much."""
    product = lipstick['product']
    translated, prov = sc.load_translations(product, lipstick['translations'])
    blocks = sc.copy(product, translated, prov['model'], ps.arabic_claims(UNCONFIRMED))
    fc = ps.faces()
    metrics = sc.face_metrics(fc)
    band = {'x': {'lang': 'es', 'area': (0.0, 0.0, 40.0, 8.0), 'rtl': False}}
    size_pt, laid, fits = sc.fit(blocks, band, fc, metrics)
    lines, height = laid['x']
    assert size_pt == sc.BODY_FLOOR_PT and not fits and height > 8.0
    words = ' '.join(t for line in lines for _, _, t in line['segments']).split()
    assert words == [w for r in blocks['es'] for w in ((r['head'] + ': ' if r['head'] else '') + r['text']).split()]
    assert any(line['overflow_mm'] > 0 for line in lines)


def test_a_dropped_line_is_refused(lipstick, tmp_path):
    """The control: the carton's own document with one line taken out, written, is refused — its section is found
    dropped (a single-line section) or not whole (a section of several lines)."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Group, TextRun
    product = lipstick['product']
    made = _document(lipstick)
    doc, blocks = made['doc'], made['blocks']
    whole = tmp_path / 'whole.ai'
    emit_pdf_ai(doc, str(whole))
    checked = sc.copy_checked(whole, blocks, sc.drawn_names(doc), product)
    sc.refuse_unless_whole(checked)                        # the document as built holds
    for name, want in (('es:ingredients', 'dropped'), ('en:warnings', 'not whole')):
        planted = doc.model_copy(deep=True)
        for group, _ in planted.walk():
            if isinstance(group, Group):
                hit = [n for n in group.children if isinstance(n, TextRun) and n.name == name]
                if hit:
                    group.children.remove(hit[-1])
                    break
        path = tmp_path / ('planted-%s.ai' % name.replace(':', '-'))
        emit_pdf_ai(planted, str(path))
        checked = sc.copy_checked(path, blocks, sc.drawn_names(planted), product)
        if want == 'dropped':
            assert checked['dropped'] == [name]
        assert not checked['all_found']
        with pytest.raises(sc.CopyRefused):
            sc.refuse_unless_whole(checked)


def test_a_refused_build_writes_no_deliverable(tmp_path, monkeypatch):
    """The build's own refusal: a band that loses its last run is refused from the engine file, before
    carton-artwork.pdf, the A4 sheet or the flat PNG exists."""
    product = sc.PRODUCTS['lipstick']
    tr = fixture_translations(product, tmp_path / 'fixture.json')
    real = sc.band_nodes

    def dropping(band, lines, size_pt, fc, colour):
        return real(band, lines, size_pt, fc, colour)[:-1]
    monkeypatch.setattr(sc, 'band_nodes', dropping)
    with pytest.raises(sc.CopyRefused):
        sc.build(tmp_path / 'files', product=product, translations=tr, claims=UNCONFIRMED)
    assert not any((tmp_path / 'files' / name).exists() for name in (
        'carton-artwork.pdf', 'carton-artwork.ai', 'carton-flat.png', 'carton-1to1-A4.pdf', 'carton-fold-check.json',
        'carton-fit-report.json'))


def test_a_build_refused_on_the_shipped_file_leaves_no_deliverable_beside_the_records(tmp_path, monkeypatch):
    """The second check (on the shipped carton-artwork.pdf) refuses with the four drawn files still in engine/staging:
    none of them, and no record, stands in the carton's folder. The planted fault: the shipped file's check reports a
    dropped line (the engine file's holds), so only the second refusal can stop the build."""
    product = sc.PRODUCTS['lipstick']
    tr = fixture_translations(product, tmp_path / 'fixture.json')
    real = sc.copy_checked
    seen = []

    def shipped_drops_a_line(pdf, blocks, names, product):
        checked = real(pdf, blocks, names, product)
        seen.append(pdf.name)
        if len(seen) == 2:
            checked['dropped'] = checked['dropped'] + ['en:warnings']
        return checked
    monkeypatch.setattr(sc, 'copy_checked', shipped_drops_a_line)
    with pytest.raises(sc.CopyRefused):
        sc.build(tmp_path / 'files', product=product, translations=tr, claims=UNCONFIRMED)
    assert seen == ['carton-engine.ai', 'carton-artwork.pdf']
    assert not any((tmp_path / 'files' / name).exists()
                   for name in sc.DELIVERABLES + ('carton-fold-check.json', 'carton-fit-report.json'))
    stage = (tmp_path / 'files').joinpath(*sc.STAGING)
    assert all((stage / name).exists() for name in sc.DELIVERABLES)


def test_no_line_opens_on_a_dot(lipstick):
    """D-D11-6: no line opens on "·" — a word with no letter or figure is bound to the one before it."""
    rep = lipstick['report']
    assert rep['no_line_opens_on_dot'] and all(not ln['text'].startswith('·') for ln in rep['lines'])
    row = {'field': 'claims', 'head': None, 'text': sc.CLAIMS['en'], 'script': 'latin'}
    assert all(not word.startswith('·') for _, _, word in sc.tokens(row))
    assert '·' in sc.CLAIMS['en'].split()                   # the control: split alone would let a line open on it


def test_the_net_line_carries_the_houses_sign_at_the_figures_cap_height(lipstick):
    net = lipstick['report']['net']
    assert net['sign_mm'] == pytest.approx(3.0) and net['cap_mm'] == pytest.approx(3.0, abs=1e-6)
    assert lipstick['report']['copy']['net']['spans'] == ['3.5 g', lm.SIGN, '0.12 oz']
    rows = [r for r in lipstick['record']['content'] if r['element'] == 'net']
    assert len(rows) == 1 and rows[0]['inside_safe']


def test_the_sign_is_read_from_the_file_and_a_planted_3_2_mm_sign_fails(lipstick, tmp_path):
    """D-D11-6 read back: the ℮ drawn on page 1 of carton-artwork.pdf, its height (across the turned band) against the
    figures' own ink (text_metrics.ink_extent_em, 3.051 mm for "3.5 g"). The control: the carton's own document with only
    its sign redrawn 3.2 mm tall, emitted and read the same way, fails 'never larger than its neighbours'."""
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import CubicTo, LineTo, MoveTo
    net = lipstick['report']['net']
    assert net['signs_found'] == 1 and net['read_from_the_file'][0]['height_mm'] == pytest.approx(3.0, abs=0.02)
    assert net['sign_never_larger'] and net['sign_at_least_3mm'] and net['sign_at_the_cap_height']
    assert min(net['neighbour_ink_mm'].values()) == pytest.approx(3.0514, abs=1e-3)
    made = _document(lipstick)
    foot = sc.net_measures(lipstick['product'], made['fc'], made['metrics'])
    back = made['faces']['back']['box']
    whole = tmp_path / 'whole.ai'
    emit_pdf_ai(made['doc'], str(whole))
    held = sc.signs_on_the_back(whole, sc.PLACEHOLDER_COLOURS['ink'], back, foot)
    assert len(held) == 1 and held[0]['never_larger_than_its_neighbours'] and held[0]['at_the_cap_height']
    planted = made['doc'].model_copy(deep=True)
    sign = _named(planted, lm.SIGN)
    pts = [(s.x, s.y) for s in sign.segments if isinstance(s, (MoveTo, LineTo, CubicTo))]
    x0, x1, base = min(p[0] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)
    w = (x1 - x0) * 3.2 / 3.0
    sign.segments, _ = lm.sign_segments(((x0 + x1 - w) / 2, base - 3.2, (x0 + x1 + w) / 2, base))
    path = tmp_path / 'planted-sign.ai'
    emit_pdf_ai(planted, str(path))
    read = sc.signs_on_the_back(path, sc.PLACEHOLDER_COLOURS['ink'], back, foot)
    assert len(read) == 1 and read[0]['height_mm'] == pytest.approx(3.2, abs=0.02)
    assert not read[0]['never_larger_than_its_neighbours'] and not read[0]['at_the_cap_height']


def test_the_net_line_stands_once_on_the_back_and_says_so(lipstick):
    """The ℮ line once, on the back — not per language — listed for the owner, never dropped from the check silently."""
    rep = lipstick['report']
    assert rep['copy']['net_in_every_language'] is False
    assert rep['copy']['net_placement'] == {'once_on_the_back': True, 'in_every_language': False, 'said': sc.NET_ONCE}
    review = {(r['lang'], r['field']): r['review'] for r in rep['for_review']}
    assert review[('all', 'net')] == sc.NET_ONCE and any(sc.NET_ONCE in p for p in rep['provisional'])


# --- the EAN-13 --------------------------------------------------------------------------------------------------------

def _white_frames(pdf):
    """Page 1's white-filled rectangles, as (width, height) in mm."""
    out = []
    with fitz.open(str(pdf)) as d:
        for dr in d[0].get_drawings():
            if dr['fill'] is not None and all(abs(c - 1.0) < 1e-3 for c in dr['fill']):
                r = dr['rect']
                out.append((round((r.x1 - r.x0) * MM, 2), round((r.y1 - r.y0) * MM, 2)))
    return out


def test_the_ean_frame_is_ladder_and_truncated_as_listed(lipstick):
    ean = lipstick['report']['ean']
    assert ean['status'] == 'truncated — owner to confirm' and ean['number'] is None
    assert ean['nominal_mm'] == [29.83, 20.74] and ean['drawn_mm'] == [29.83, 16.45]
    assert ean['bar_height_cut_mm'] == pytest.approx(4.29, abs=1e-3)
    assert ean['panel'] in ('side_left', 'side_right')
    frames = _white_frames(lipstick['out'] / 'carton-artwork.pdf')
    # drawn on the flat: 16.45 across the panel (x), 29.83 along its length (y) — ladder; a picket frame would be
    # 29.83 across, wider than the 22.45 mm panel
    assert (16.45, 29.83) in frames and (29.83, 16.45) not in frames
    row = [r for r in lipstick['record']['content'] if r['element'] == 'EAN-13 frame'][0]
    w, h = row['box_mm'][2] - row['box_mm'][0], row['box_mm'][3] - row['box_mm'][1]
    assert h == pytest.approx(29.83, abs=1e-3) and w == pytest.approx(16.45, abs=1e-3) and row['inside_safe']
    # the control: the frame laid unturned does not fit the panel's safe width
    assert sc.EAN_MM[0] > lipstick['record']['faces'][row['panel']]['safe_mm'][2] - \
        lipstick['record']['faces'][row['panel']]['safe_mm'][0]


# --- the flaps ---------------------------------------------------------------------------------------------------------

def test_the_flaps_are_clean_and_a_ground_planted_on_a_flap_fails(lipstick, tmp_path):
    clean = lipstick['record']['clean']
    assert clean['holds'] and len(clean['parts']) == 7     # four dust flaps, the glue flap, two tongues
    coords, _ = sc.die(lipstick['product'])
    bare = pb.non_printing(coords)
    fc_box = sc.faces(coords)
    engine = lipstick['out'] / 'engine' / 'carton-engine.ai'
    dust = coords.dust_flap_polygons[0]
    cx, cy = dust.representative_point().coords[0]
    planted = tmp_path / 'planted.ai'
    with fitz.open(str(engine)) as d:
        p = d[0]
        k = 72.0 / 25.4
        p.draw_rect(fitz.Rect((cx - 2 + sc.BLEED_MM) * k, (cy - 2 + sc.BLEED_MM) * k, (cx + 2 + sc.BLEED_MM) * k,
                              (cy + 2 + sc.BLEED_MM) * k), color=None, fill=(0.1, 0.13, 0.28))
        d.save(str(planted))
    check = pb.clean_parts(planted, bare, fc_box, -sc.BLEED_MM, -sc.BLEED_MM)
    assert not check['holds']
    assert max(r['ink_mm2'] for r in check['parts']) > 10.0


# --- the translations --------------------------------------------------------------------------------------------------

def test_the_copy_panels_are_refused_without_translations_and_nothing_is_written(tmp_path):
    product = sc.PRODUCTS['lipstick']
    with pytest.raises(sc.TranslationsMissing):
        sc.build(tmp_path / 'files', product=product, translations=tmp_path / 'absent.json')
    assert not (tmp_path / 'files').exists()
    # translated from other English: refused too (a stale file never stands for this copy)
    stale = sc.translation_request(product)
    stale = _copy.deepcopy(stale)
    stale['prose']['warnings'] = 'For external use only.'
    path = fixture_translations(product, tmp_path / 'stale.json', english=stale)
    with pytest.raises(sc.TranslationsMissing):
        sc.load_translations(product, path)
    # another product's file: refused
    other = fixture_translations(sc.PRODUCTS['lip_balm'], tmp_path / 'balm.json')
    with pytest.raises(sc.TranslationsMissing):
        sc.load_translations(product, other)
    # the control: this product's own file loads, the Arabic unvowelled
    good = fixture_translations(product, tmp_path / 'good.json')
    tr, prov = sc.load_translations(product, good)
    assert set(tr) == {'es', 'ar'} and tr['es']['made_in'] == 'Hecho en EAU.' and prov['model'] == 'fixture'


def test_the_default_translations_file_is_the_products_own_and_not_yet_made_here():
    """The module never writes it: the lead's runner does (panel_translate, ≈ $0.01)."""
    path = sc.translations_path(sc.PRODUCTS['lipstick'])
    assert path == lm.REPO / 'docs' / 'audit' / 'day-11' / 'lipstick' / 'carton' / 'carton-translations.json'


def test_a_call_without_its_english_or_its_translations_is_refused_by_name(tmp_path):
    """A malformed file is refused as TranslationsMissing, never a KeyError: a call missing its English or its
    translations, a language block that is not a block, a file that is not JSON. The control: the whole file loads."""
    product = sc.PRODUCTS['lipstick']
    good_path = fixture_translations(product, tmp_path / 'good.json')
    good = json.loads(good_path.read_text(encoding='utf-8'))
    planted = []
    for part in ('english', 'translations'):
        bad = _copy.deepcopy(good)
        del bad['calls']['prose'][part]
        planted.append((part, bad))
    bad = _copy.deepcopy(good)
    bad['calls']['short lines']['translations']['es'] = 'not a block'
    planted.append(('es', bad))
    for i, (said, bad) in enumerate(planted):
        path = tmp_path / ('bad-%d.json' % i)
        path.write_text(json.dumps(bad, ensure_ascii=False), encoding='utf-8')
        with pytest.raises(sc.TranslationsMissing, match=said):
            sc.load_translations(product, path)
    torn = tmp_path / 'torn.json'
    torn.write_text(good_path.read_text(encoding='utf-8')[:-40], encoding='utf-8')
    with pytest.raises(sc.TranslationsMissing):
        sc.load_translations(product, torn)
    tr, _ = sc.load_translations(product, good_path)
    assert tr['ar']['head:warnings'] == FIXTURE_WORDS['ar']['head:warnings']


def test_the_translations_file_is_written_whole_or_not_at_all(tmp_path):
    """The runner's write: a file one key short (panel_translate drops an empty or unknown value without a word) is
    refused before it takes the file's name — so a re-run is never blocked and nothing needs deleting — and its paid
    words stay in a stamped partial file; the whole file takes the name. Never overwritten."""
    product = sc.PRODUCTS['lipstick']
    good = json.loads(fixture_translations(product, tmp_path / 'src.json').read_text(encoding='utf-8'))
    path = tmp_path / 'carton' / sc.TRANSLATIONS_NAME
    short = sc.translation_request(product)['short lines']
    assert sc.call_gaps(short, good['calls']['short lines']['translations']) == []
    for lang, key, value in (('ar', 'warnings', None), ('es', 'how_to_use', '  ')):
        torn = _copy.deepcopy(good)
        block = torn['calls']['short lines']['translations'][lang]
        if value is None:
            del block[key]
        else:
            block[key] = value
        assert sc.call_gaps(short, torn['calls']['short lines']['translations']) == [(lang, key)]
        with pytest.raises(sc.TranslationsMissing):
            sc.write_translations(product, torn, path)
        assert not path.exists()
    assert len(list(path.parent.glob(sc.TRANSLATIONS_NAME + '.*.partial'))) == 2
    tr, prov = sc.write_translations(product, good, path)
    assert path.exists() and prov['file'] == str(path) and tr['es']['made_in'] == 'Hecho en EAU.'
    assert len(list(path.parent.glob(sc.TRANSLATIONS_NAME + '.*.partial'))) == 2      # the whole one moved, not copied
    with pytest.raises(FileExistsError):
        sc.write_translations(product, good, path)


# Day 10's three panel_translation calls as the ledger holds them (bbrose_design_os/var/rescue_spend/ledger.sqlite3,
# read 2026-10-23): settled before Day 11's entry, though their text sorts after "…T11:01"
DAY10_ROWS = [(5376, '2026-10-23T11:13:33.068905+08:00', 'usage_recorded'),
              (3774, '2026-10-23T11:13:40.265475+08:00', 'usage_recorded'),
              (2742, '2026-10-23T11:13:44.022359+08:00', 'usage_recorded')]


def test_the_translation_stop_counts_settled_spend_since_day_11s_entry_as_instants():
    assert sc.DAY11_ENTRY_UTC.isoformat() == '2026-10-23T11:01:00+00:00'
    assert sc.spent_since(DAY10_ROWS, sc.DAY11_ENTRY_UTC) == (0.0, 0)
    # the control on the instrument: compared as text, all three would count against the day's $0.20
    assert all(started >= sc.DAY11_ENTRY_UTC.isoformat()[:16] for _, started, _ in DAY10_ROWS)
    planted = DAY10_ROWS + [(4000, '2026-10-23T19:01:00+08:00', 'usage_recorded'),
                            (3000, '2026-10-23T22:30:00+08:00', 'usage_recorded'),
                            (100000, '2026-10-23T22:31:00+08:00', 'reserved')]
    spent, count = sc.spent_since(planted, sc.DAY11_ENTRY_UTC)
    assert spent == pytest.approx(0.007) and count == 2
    with pytest.raises(ValueError):
        sc.spent_since([(1, '2026-10-23T19:30:00', 'usage_recorded')], sc.DAY11_ENTRY_UTC)


def test_a_partial_write_keeps_what_was_paid_beside_the_name_and_never_takes_it(tmp_path):
    """``write_partial``, the runner's record of what was paid before the whole-or-nothing check: the data verbatim
    under a stamped name beside the file's own, in a folder it makes; never the file's own name, and two writes never
    share one."""
    path = tmp_path / 'carton' / sc.TRANSLATIONS_NAME
    data = {'calls': {}, 'words': 'ظلال'}
    first = sc.write_partial(path, data)
    second = sc.write_partial(path, data)
    assert not path.exists() and first != second and first.parent == second.parent == path.parent
    assert first.name.startswith(sc.TRANSLATIONS_NAME + '.') and first.name.endswith('.partial')
    assert json.loads(first.read_text(encoding='utf-8')) == data


# --- the copy's sources ------------------------------------------------------------------------------------------------

def test_the_claims_are_the_owners_lines_verbatim():
    decisions = (lm.REPO / 'CURRENT_DECISIONS.md').read_text(encoding='utf-8')
    assert '"%s"' % sc.CLAIMS['es'] in decisions and '"%s"' % ps.AR_CLAIMS_FALLBACK in decisions
    assert sc.CLAIMS['en'] == ps.ENGLISH['claims'] and sc.CLAIMS['es'] == ps.CORRECTED['es']['claims']
    assert 'ar' not in sc.CLAIMS                            # the Arabic is resolved at build time, never held here


def _ar_claims_drawn(built):
    names = built['report']['span_names']
    spans = lm.actual_texts(built['out'] / 'carton-artwork.pdf', 0)
    return ps._norm(' '.join(sp for n, sp in zip(names, spans) if n == 'ar:claims'))


def test_the_arabic_claims_follow_d_d11_6_at_build_time(lipstick, tmp_path_factory, monkeypatch):
    """The carton prints the Arabic claims by the sticker's own rule, decided when it is built from Brand.claims: the
    house's record unconfirmed (the module fixture) prints the owner's fallback line, marked "owner to confirm"; the
    same build with every row confirmed — read through the default path (``claims`` None reads the database: here
    ``house_claims`` planted) — prints the house's line exactly and asks for nothing."""
    assert _ar_claims_drawn(lipstick) == ps._norm(ps.AR_CLAIMS_FALLBACK)
    rep = lipstick['report']
    assert rep['arabic_claims']['owner_to_confirm'] and rep['arabic_claims']['text'] == ps.AR_CLAIMS_FALLBACK
    assert ('ar', 'claims') in {(r['lang'], r['field']) for r in rep['for_review']}
    monkeypatch.setattr(ps, 'house_claims', lambda: CONFIRMED)
    confirmed = _build(tmp_path_factory, 'lipstick', claims=None)
    house = ps.arabic_claims(CONFIRMED)[0]
    assert house == 'خال من القسوة · نباتي 100٪' and _ar_claims_drawn(confirmed) == ps._norm(house)
    assert not confirmed['report']['arabic_claims']['owner_to_confirm']
    assert ('ar', 'claims') not in {(r['lang'], r['field']) for r in confirmed['report']['for_review']}
    assert confirmed['report']['copy']['all_found']


def test_every_source_is_named_and_the_inci_is_a_placeholder_in_every_language(lipstick):
    rep = lipstick['report']
    for lang in sc.LANGS:
        assert set(rep['sources'][lang]) == set(sc.ORDER)
    # Day 13, D-D13-6: "the English my draft" — the owner's draft now, his to edit on the page before Day 15
    assert rep['sources']['en']['description'] == sc.OWNER_DRAFT and 'owner' in rep['sources']['en']['made_in']
    review = {(r['lang'], r['field']): r['review'] for r in rep['for_review']}
    assert review[('ar', 'claims')] == 'owner to confirm'
    assert all(review[(lang, 'ingredients')] == 'placeholder — owner to supply' for lang in sc.LANGS)
    assert all(review[(lang, f)] for lang in ('es', 'ar') for f in ('description', 'how_to_use', 'warnings', 'made_in'))
    words = lm.actual_texts(lipstick['out'] / 'carton-artwork.pdf', 0)
    assert words.count(sc.INCI_PLACEHOLDER) == 3 and not any('⟪PROVISIONAL⟫' in w for w in words)


# --- the front, the ends, the sheet ------------------------------------------------------------------------------------

def test_the_placeholder_front_is_named_and_carries_no_plate(lipstick):
    front = lipstick['record']['front']
    assert front['placeholder'] and front['ground'] == '#1B2148' and 'placeholder' in front['said']
    assert lipstick['record']['plates'] == {'foil': [], 'relief': []}
    assert 'ground' in lipstick['record']['colours_placeholder']


def test_the_ends_carry_the_logo_inside_their_safe_areas_read_from_the_file(lipstick, tmp_path):
    """The logos as laid out and as page 1 draws them (the top end's under a nested 180° turn the layout never sees),
    each inside its end's safe box. The control: a mark in the logo's ink planted on the top end, inside the lid but
    1 mm from its cut edge (outside its safe box), on a copy of the shipped PDF, is seen."""
    rec = lipstick['record']
    rows = [r for r in rec['content'] if r['element'] == 'the logo']
    assert {r['panel'] for r in rows} == {'top_end', 'bottom_end'} and all(r['inside_safe'] for r in rows)
    read = [r for r in rec['content'] if r['element'] == 'the logo, read from the file']
    assert {r['panel'] for r in read} == {'top_end', 'bottom_end'} and all(r['inside_safe'] for r in read)
    ends = rec['logos_read_from_the_file']
    assert ends['holds'] and all(e['parts'] == 3 for e in ends['ends'].values())
    laid = {r['panel']: r['box_mm'] for r in rows}
    for end, e in ends['ends'].items():
        assert e['box_mm'] == pytest.approx(laid[end], abs=0.02)
    x0, y0, x1, y1 = rec['faces']['top_end']['box_mm']
    planted = tmp_path / 'planted-end.pdf'
    k = 72.0 / 25.4
    with fitz.open(str(lipstick['out'] / 'carton-artwork.pdf')) as d:
        d[0].draw_rect(fitz.Rect((x0 + 1.0 + sc.BLEED_MM) * k, ((y0 + y1) / 2 + sc.BLEED_MM) * k,
                                 (x0 + 2.0 + sc.BLEED_MM) * k, ((y0 + y1) / 2 + 1.0 + sc.BLEED_MM) * k),
                       color=None, fill=sc._rgb(rec['colours']['logo']))
        d.save(str(planted))
    seen = sc.logos_on_the_ends(planted, rec['colours']['logo'], sc.faces(sc.die(lipstick['product'])[0]))
    assert not seen['top_end']['inside_safe'] and seen['top_end']['parts'] == 4 and seen['bottom_end']['inside_safe']


def test_the_a4_sheet_is_at_100_percent_with_its_ruler(lipstick, tmp_path):
    with fitz.open(str(lipstick['out'] / 'carton-1to1-A4.pdf')) as d:
        page = d[0]
        assert (round(page.rect.width * MM, 1), round(page.rect.height * MM, 1)) == (210.0, 297.0)
        lines = [it for dr in page.get_drawings() for it in dr['items'] if it[0] == 'l']
    lengths = [round(((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5 * MM, 2) for _, a, b in lines]
    assert 100.0 in lengths
    assert lipstick['record']['a4']['fold_marks'] == 24
    with Image.open(str(lipstick['out'] / 'carton-flat.png')) as im:
        assert im.info['dpi'][0] == pytest.approx(300, abs=1)


def test_the_a4_scale_is_measured_on_the_sheet_and_a_98_percent_sheet_fails(lipstick, tmp_path):
    """The scale is a crease's drawn length on the A4 page over the engine's own (83.45 mm along, 22 mm across). The
    control: the same artwork placed at 98 % reads 0.98 and fails."""
    scale = lipstick['record']['a4']['scale']
    assert scale['holds'] and scale['y']['engine_mm'] == pytest.approx(83.45) and scale['x']['engine_mm'] == 22.0
    assert scale['x']['scale'] == pytest.approx(1.0, abs=1e-4) and scale['y']['scale'] == pytest.approx(1.0, abs=1e-4)
    coords, _ = sc.die(lipstick['product'])
    planted = tmp_path / 'a4-at-98.pdf'
    with fitz.open() as doc, fitz.open(str(lipstick['out'] / 'carton-artwork.pdf')) as src:
        page = doc.new_page(width=lm.pt(sc.A4_MM[0]), height=lm.pt(sc.A4_MM[1]))
        w, h = src[0].rect.width * 0.98, src[0].rect.height * 0.98
        page.show_pdf_page(fitz.Rect(20, 20, 20 + w, 20 + h), src, 0)
        doc.save(str(planted))
    shrunk = sc.a4_scale(planted, coords)
    assert not shrunk['holds'] and shrunk['y']['scale'] == pytest.approx(0.98, abs=1e-3)


def test_a_front_picture_and_foiled_nodes_reach_the_flat_and_the_foil_page(tmp_path_factory):
    """The front's contract: a picture covering the front's ground and engine nodes in the front's own frame; a foiled
    node's plate lands on page 2. Each node is checked like the copy, its box read from its own emitted file: the hero
    stands inside the front's safe area; the control — a node inside the plain 3 mm safe box but within the thumb notch's
    keep-out (r 4.04 + 4 mm about the notch's centre on the top edge) — is refused there, and the record says so."""
    from apps.ire.graph import Color, Finish, Rect, SolidFill, TextRun
    pic_dir = tmp_path_factory.mktemp('front-pic')
    pic = pic_dir / 'front.png'
    grad = np.linspace(40, 200, 1200).astype(np.uint8)
    Image.fromarray(np.dstack([np.tile(grad[:, None], (1, 300))] * 3)).save(pic)
    foil = Rect(name='hero (test foil)', x=4.0, y=30.0, w=14.0, h=10.0, fill=SolidFill(color=Color.from_hex('#C9977F')),
                finishes=[Finish(kind='foil', plate='FOIL_ROSE_GOLD')])
    by_notch = Rect(name='planted by the notch', x=8.0, y=3.5, w=6.0, h=2.0,
                    fill=SolidFill(color=Color.from_hex('#F2E8D8')))
    words = TextRun(name='name (test words)', text='Enchanted', x=4.0, y=60.0, font=ps.faces()['medium']['role'],
                    size_pt=7.0, color=Color.from_hex('#F2E8D8'))
    built = _build(tmp_path_factory, 'lipstick', picture=pic, nodes=[foil, by_notch, words])
    rec = built['record']
    front = rec['front']
    assert not front['placeholder'] and front['picture']['pixels'] == [300, 1200] and front['nodes']['count'] == 3
    assert front['picture']['content_checked'] is False
    assert any('front picture' in p for p in built['report']['provisional'])
    assert rec['plates'] == {'foil': ['FOIL_ROSE_GOLD'], 'relief': []}
    with fitz.open(str(built['out'] / 'carton-artwork.pdf')) as d:
        assert d[1].get_label().startswith('2 foil plate - FOIL_ROSE_GOLD')
        assert d[1].get_drawings() and not d[2].get_drawings()
    fx0, fy0 = rec['faces']['front']['box_mm'][:2]
    rows = {r['element']: r for r in rec['content'] if r['panel'] == 'front'}
    hero = rows['front node 1 (hero (test foil))']
    assert hero['box_mm'] == pytest.approx([fx0 + 4.0, fy0 + 30.0, fx0 + 18.0, fy0 + 40.0], abs=0.02)
    assert hero['inside_safe'] and hero['notch_clear'] and not hero['crosses_a_crease']
    assert (built['out'] / 'engine' / 'front-node-1.ai').exists()
    planted = rows['front node 2 (planted by the notch)']
    assert planted['box_mm'] == pytest.approx([fx0 + 8.0, fy0 + 3.5, fx0 + 14.0, fy0 + 5.5], abs=0.02)
    assert planted['inside_safe_box'] and not planted['notch_clear'] and not planted['inside_safe']
    assert planted['notch_clear_mm'] == pytest.approx(3.5 - rec['die']['notch_keep_out_mm'], abs=0.02)
    text = rows['front node 3 (name (test words))']          # a text node: its span's box, read from its file
    assert text['box_mm'][0] == pytest.approx(fx0 + 4.0, abs=0.3) and text['box_mm'][1] < fy0 + 60.0 < text['box_mm'][3]
    assert text['box_mm'][2] - text['box_mm'][0] > 8.0 and text['inside_safe']     # at 10 pt it reads 18 mm: past the safe edge
    assert not rec['all_inside_safe'] and not rec['notch_clear']
    assert rec['faces']['front']['keep_out']['r_mm'] == pytest.approx(rec['die']['notch_keep_out_mm'])


def test_the_placeholder_build_checks_every_front_element_it_has(lipstick):
    """With no nodes the front carries only its ground: no front element to check, and every other row clears the
    notch (the plain safe box alone reaches 34.94 − 33.9 = 1.04 mm into the notch's cut on the lipstick)."""
    rec = lipstick['record']
    notch = rec['die']['thumb_notch']
    assert notch['y'] + notch['r'] > rec['faces']['front']['safe_mm'][1]
    assert rec['notch_clear'] and not [r for r in rec['content'] if r['panel'] == 'front']


# --- the lip balm (D-D11-8) --------------------------------------------------------------------------------------------

def test_the_lip_balm_takes_the_same_function(balm):
    rec, rep = balm['record'], balm['report']
    assert rec['die']['inside_mm'] == [20.0, 20.0, 73.0] and rec['fold_check']['passed']
    assert rec['die_untouched']['holds'] and rec['clean']['holds']
    assert rep['copy']['net']['spans'] == ['4.5 g', lm.SIGN, '0.15 oz'] and rep['copy']['all_found']
    assert rep['copy']['dropped'] == [] and rep['ean']['drawn_mm'] == [29.83, 14.45]
    # the balm's panels are 2 mm narrower (six lines at the floor, not seven): whatever does not fit at 5 pt is drawn
    # and said line by line — never dropped, never hidden — and only those lines leave the safe area
    assert rep['body']['size_pt'] == sc.BODY_FLOOR_PT or rep['body']['fits']
    over = {(ln['panel'], '%s line %d' % (ln['lang'], ln['line'])) for ln in rep['overflow']}
    outside = {(r['panel'], r['element']) for r in rec['content'] if not r['inside_safe'] or r['crosses_a_crease']}
    assert outside == over
    assert rep['every_line_inside_its_area'] == (rep['overflow'] == []) == rec['all_inside_safe']


def test_the_description_is_one_line_each_or_listed(lipstick, balm):
    """D-D11-7: the description one line each. The lipstick's holds; the control — the balm's English wraps to two
    lines on its 2 mm narrower panels — fails and is listed for review, language by language."""
    assert lipstick['report']['description_one_line_holds']
    assert 'description_lines' not in {r['field'] for r in lipstick['report']['for_review']}
    rep = balm['report']
    # Day 13, §1.3: the narrow-panel rule moves the languages (the Spanish no longer has the long side alone), so more
    # than the English may wrap; each that does is listed, language by language
    assert rep['description_one_line']['en'] == 2 and not rep['description_one_line_holds']
    listed = [(r['lang'], r['review']) for r in rep['for_review'] if r['field'] == 'description_lines']
    wraps = [lang for lang in ('en', 'es', 'ar') if rep['description_one_line'][lang] > 1]
    assert listed == [(lang, 'the description runs to %d lines: D-D11-7 asks one line each — to shorten or to rule'
                       % rep['description_one_line'][lang]) for lang in wraps]


def test_an_overflow_says_where_it_lies_and_the_plan_keeps_it_off_the_free_edge(balm):
    """Every overflow line says where it lies on the flat: past the trim (cut off), across a crease onto another panel
    (and on its elements or not), or in its own margin. The plan prefers an assignment whose overflow stays on the
    carton: the chosen one runs no line past a cut; the control — the house's order with the EAN on the right side,
    the plan's choice before the rule — runs Arabic lines off the right side's free edge."""
    rep = balm['report']
    assert rep['overflow'] and all('overflow_lies' in ln and ln['overflow_lies']['said'] for ln in rep['overflow'])
    assert rep['overflow_cut_off'] == []
    opts = rep['panel_plan']['options']
    plan = rep['panel_plan']
    # Day 13, §1.3: a way is also where the fields stand and how the paragraphs run (72 ways); the chosen one runs no
    # line past a cut and none across a crease or onto another face
    chosen = [o for o in opts if o['assign'] == plan['chosen'] and o['ean_panel'] == rep['ean']['panel']
              and o['fields_at'] == plan['fields_at'] and o['paragraphs'] == plan['paragraphs']]
    assert len(chosen) == 1 and chosen[0]['past_trim_lines'] == 0 and chosen[0]['crossing_lines'] == 0
    peers = [o for o in opts if (o['fits'], o['size_pt']) == (chosen[0]['fits'], chosen[0]['size_pt'])]
    assert chosen[0]['past_trim_lines'] == min(o['past_trim_lines'] for o in peers)
    house = [o for o in opts if o['assign'] == {'back': 'en', 'side_left': 'es', 'side_right': 'ar'}
             and o['ean_panel'] == 'side_right' and o['fields_at'] == plan['fields_at']
             and o['paragraphs'] == plan['paragraphs']][0]
    # Day 13, §1.3: the columns now leave the chosen way fewer lines over than the house's, not more
    assert house['past_trim_lines'] >= 1 and chosen[0]['overflow_lines'] <= house['overflow_lines']
    # the instrument on a planted line: 1 mm past the right side's free edge is cut off; the same line on the back
    # runs across its crease onto the left side instead
    coords, _ = sc.die(balm['product'])
    fc_box = sc.faces(coords)
    layout = {'faces': fc_box, 'elements': []}
    for panel, cut in (('side_right', True), ('back', False)):
        x0, y0, x1, y1 = fc_box[panel]['box']
        lies = sc.overflow_lies((10.0, x1 - x0 - 4.0, 30.0, x1 - x0 + 1.0), panel, layout)
        assert lies['cut_off'] == cut and lies['past_the_trim_mm'] == pytest.approx(1.0 if cut else 0.0, abs=1e-6)
        if not cut:
            assert lies['onto_faces'] == ['side_left'] and 'side_left' in lies['said']
