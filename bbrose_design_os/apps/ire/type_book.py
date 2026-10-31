"""The type book (Day 8 §1b): every house and GRANTED family once, its regular and its heaviest face, grouped by class.

Latin classes didone, serif, slab, sans, condensed, display, script, mono; Arabic classes naskh, kufi, display — Latin and
Arabic apart (a family carrying both scripts is listed in each script's part). Under each family the licence wording and
its evidence; the house's theme faces (``font_roles.theme_faces()``) marked. A face without licence evidence is never in
the book, and nothing on the D-D7-1 exclusion list is (``docs/audit/day-7/library/fonts-excluded.json``).

Specimens are drawn by reportlab, the engine's own emitter: the Latin lines as given; the Arabic line shaped through the
engine's own Arabic path — ``text_intl.shape_ar(text, keep_harakat=True)``: arabic_reshaper's presentation forms, then
python-bidi's visual order, drawn with no OpenType shaping — so a face lacking a presentation form the reshaper emits
shows the gap the emitter would print. A variable face is drawn at a static instance (``font_instances``), never its
default. A file reportlab cannot read (CFF outlines, some collections) is drawn as a raster of the same string by PIL's
basic layout and marked: the emitter cannot draw it.

Classes: the house's families by the executor's table below (``HOUSE_CLASS``, stated); the GRANTED pool's by
``font_pool.classify`` (face names and OS/2 width, a heuristic) with mono split out by the face's own fixed pitch; the
faces the names leave unclassified by a vision model reading their specimens (``classify_from_specimens``), folded in
under "classified from specimens (model)".

``build(faces, out_dir)`` is pure (any face list, any folder — the offline fixture test builds from tracked files);
``gather()`` reads the catalogue, the pool record, the licence files and the theme. Outputs: ``type-book.json`` (written
after every class, atomically) and then ``type-book.pdf``.
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import json
import os
import re
from pathlib import Path

from apps.ire import font_instances

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs' / 'audit' / 'day-8' / 'fonts'
SCHEMA = 'day8_type_book/1'
LATIN_LINES = ('Enchanted Rose', 'EYESHADOW PALETTE · 18 shades · 27 g ℮', 'Aa Bb Qq Rr 0123')
ARABIC_LINE = 'باليت ظلال العيون'
LATIN_CLASSES = ('didone', 'serif', 'slab', 'sans', 'condensed', 'display', 'script', 'mono')
ARABIC_CLASSES = ('naskh', 'kufi', 'display')
UNCLASSIFIED = 'unclassified'
ARABIC_PATH = ('the engine\'s own emitter path: apps.dielines.exporters.text_intl.shape_ar(text, keep_harakat=True) — '
               'arabic_reshaper presentation forms, then python-bidi visual order — drawn by reportlab drawString with no '
               'OpenType shaping (no HarfBuzz)')
EMITTER_CAPABLE_MEANS = ('the face carries the 36 basic letters, every presentation form arabic_reshaper emits for them in '
                         'every joining position and every harakat mark the path keeps (font_roles._inspect, read from the '
                         'cmap), AND reportlab reads the file — the only Arabic faces the directions may pick')
#: lettering family (``font_pool.classify`` / ``lettering_faces.FAMILIES``) → the book's class
FROM_LETTERING = {'didone': 'didone', 'old-style': 'serif', 'transitional': 'serif', 'roman-capitals': 'serif',
                  'flared': 'serif', 'condensed-serif': 'condensed', 'slab': 'slab', 'sans': 'sans', 'wide-sans': 'sans',
                  'condensed': 'condensed', 'script': 'script'}
#: the house's families classed by the executor — (Latin class, Arabic class); None where the family carries no such
#: script for the book. Where ``lettering_faces.FAMILIES`` names the family its class follows (didone, old-style →
#: serif, condensed-serif → condensed, …); the four display faces of his rule 3 (``DISPLAY_FACES_FIRST``) are display;
#: the rest by the face's design as published (Cairo "extends the Kufi style"; Tajawal and Reem Kufi geometric kufi;
#: Aref Ruqaa and Lalezar Arabic display).
HOUSE_CLASS = {
    'abrilfatface': ('didone', None), 'amaticsc': ('display', None), 'arefruqaa': ('serif', 'display'),
    'bagelfatone': ('display', None), 'barlowcondensed': ('condensed', None), 'bebasneue': ('condensed', None),
    'cairo': ('sans', 'kufi'), 'chango': ('display', None), 'cinzel': ('serif', None), 'cookie': ('script', None),
    'cormorantgaramond': ('serif', None), 'courierprime': ('mono', None), 'dmserifdisplay': ('didone', None),
    'damion': ('script', None), 'dancingscript': ('script', None), 'fredoka': ('display', None),
    'gloock': ('condensed', None), 'grandhotel': ('script', None), 'greatvibes': ('script', None),
    'instrumentserif': ('condensed', None), 'italiana': ('didone', None), 'jost': ('sans', None),
    'kaushanscript': ('script', None), 'lalezar': ('display', 'display'), 'lato': ('sans', None),
    'librebaskerville': ('serif', None), 'lobster': ('script', None), 'marcellus': ('serif', None),
    'montserrat': ('sans', None), 'notosans': ('sans', None), 'notonaskharabic': (None, 'naskh'),
    'opensans': ('sans', None), 'oswald': ('condensed', None), 'pacifico': ('script', None),
    'playfairdisplay': ('didone', None), 'poppins': ('sans', None), 'quicksand': ('sans', None),
    'raleway': ('sans', None), 'reemkufi': ('sans', 'kufi'), 'rubik': ('sans', None), 'satisfy': ('script', None),
    'shadowsintolighttwo': ('script', None), 'shrikhand': ('display', None), 'tajawal': ('sans', 'kufi'),
    'yellowtail': ('script', None),
}
#: an Arabic family's class from its names: the kind of hand it is named for
ARABIC_NAME_CLASS = ((r'naskh|nasakh|lateef|markazi|amiri|scheherazade', 'naskh'),
                     (r'kufi|kufic|kufam', 'kufi'),
                     (r'ruqaa|ruqa|thuluth|diwani|nastaliq|khati|calligraph', 'display'))
_WEIGHT_TAIL = re.compile(r'(extrabold|ultrabold|semibold|demibold|bold|extralight|ultralight|light|thin|hairline|black|'
                          r'heavy|medium|regular|italic|book|oblique)$')


def family_key(name: str) -> str:
    """One key per family: lower-case letters and digits, weight and style words stripped from the end (a legacy name
    such as "Abhaya Libre ExtraBold" joins "Abhaya Libre")."""
    key = re.sub(r'[^a-z0-9]', '', str(name or '').lower())
    while True:
        stripped = _WEIGHT_TAIL.sub('', key)
        if stripped == key or not stripped:
            return key
        key = stripped


def _rel(path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, path)


# --- the faces -------------------------------------------------------------------------------------------------------

def read_face(path, index: int = 0) -> dict:
    """What the book reads from a file itself: cmap, fixed pitch, italic, weight class, style name, outline format, and
    whether reportlab reads it."""
    from fontTools.ttLib import TTFont
    with TTFont(str(path), lazy=True, fontNumber=index) as ft:
        cmap = set((ft.getBestCmap() or {}).keys())
        post = ft['post'] if 'post' in ft else None
        os2 = ft['OS/2'] if 'OS/2' in ft else None
        head = ft['head'] if 'head' in ft else None
        italic = bool((os2 is not None and os2.fsSelection & 1) or (head is not None and head.macStyle & 2)
                      or (post is not None and abs(float(post.italicAngle or 0)) > 0.5))
        # a mono face draws every letter on one advance; some (Chivo Mono) leave post.isFixedPitch unset
        adv = {ft['hmtx'][ft.getBestCmap()[ord(ch)]][0] for ch in 'abcdefghijklmnopqrstuvwxyz'
               if ord(ch) in cmap and 'hmtx' in ft}
        out = {'cmap': cmap, 'fixed_pitch': bool((post is not None and post.isFixedPitch) or (len(adv) == 1 and len(cmap) > 26)),
               'italic': italic, 'us_weight_class': os2.usWeightClass if os2 is not None else None,
               'style': ft['name'].getDebugName(17) or ft['name'].getDebugName(2) or '',
               'cff': 'CFF ' in ft or 'CFF2' in ft}
    out['reportlab'] = _reportlab_reads(path, index)
    try:
        from PIL import ImageFont
        ImageFont.truetype(str(path), 20, index=index)
        out['pil_reads'] = True
    except Exception:          # noqa: BLE001 — recorded: no raster of this file either
        out['pil_reads'] = False
    return out


_RL_CACHE: dict = {}


def _reportlab_reads(path, index: int = 0) -> dict:
    """``{'ok': bool, 'name': registered name, 'why'}`` — the face registered with reportlab under a name of its own bytes
    (never its PostScript name: pool and house copies share names, and a reused name silently draws another face)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont as RLFont
    key = (str(path), index)
    if key in _RL_CACHE:
        return _RL_CACHE[key]
    name = 'TB-' + hashlib.sha256(('%s|%d' % (_sha(path), index)).encode()).hexdigest()[:14]
    try:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(RLFont(name, str(path), subfontIndex=index))
        out = {'ok': True, 'name': name, 'why': ''}
    except Exception as exc:        # noqa: BLE001 — the row says the emitter cannot draw this file
        out = {'ok': False, 'name': None, 'why': '%s: %s' % (type(exc).__name__, str(exc)[:120])}
    _RL_CACHE[key] = out
    return out


def _licence_file_evidence(licence_path: Path, recorded_sha: str | None) -> dict | None:
    """A house licence file as evidence: present, its bytes the recorded digest (when one is recorded), its wording."""
    from apps.ire.font_pool import licence_of
    if not licence_path.exists():
        return None
    sha = _sha(licence_path)
    if recorded_sha and sha != recorded_sha:
        return None
    text = licence_path.read_text(encoding='utf-8', errors='replace')
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), '')
    return {'licence': licence_of(text), 'evidence': 'licence file', 'evidence_path': _rel(licence_path), 'evidence_sha256': sha,
            'wording': first[:200]}


def gather() -> tuple[list[dict], list[dict]]:
    """``(faces, excluded)``: every face of ``font_roles.catalogue()`` — the house (brand2026 re-hashed against
    PROVENANCE.json, the Noto files) and the GRANTED pool — with its licence evidence, theme roles and the seam's
    verdict; a face without licence evidence or on the D-D7-1 exclusion list goes to ``excluded``."""
    from apps.ire import font_pool, font_roles
    from apps.ire.container_font_authority import VERIFIED_FOR_PRODUCTION
    cat = font_roles.catalogue()
    pool = {e['catalogue_stem']: e for e in font_pool.catalogue_entries()}
    excluded_shas = font_pool.excluded()
    static = Path(font_roles.__file__).resolve().parents[2] / 'static' / 'fonts'
    prov = json.loads((static / 'brand2026' / 'PROVENANCE.json').read_text())
    licence_by_file = {}
    for folder, fam in (prov.get('families') or {}).items():
        for f in fam.get('files') or []:
            if f.get('licence_file'):
                licence_by_file[str((static / 'brand2026' / folder / f['file']).resolve())] = (
                    static / 'brand2026' / folder / f['licence_file'], f.get('licence_sha256'), fam.get('family') or folder)
    noto_licence = {'NotoNaskhArabic-Bold': static / 'NotoNaskhArabic-Bold.OFL.txt'}
    theme = font_roles.theme_faces()
    roles_of = collections.defaultdict(list)
    for role, res in sorted(theme['resolutions'].items()):
        if res.get('stem'):
            inst = res.get('instance') or {}
            roles_of[res['stem']].append({'role': role, 'weight': (inst.get('axes') or {}).get('wght'),
                                          'postscript': res.get('postscript')})
    faces, excluded = [], []
    for stem, e in sorted(cat.items()):
        is_pool = e.get('origin') == font_pool.ORIGIN
        path = Path(e['path'])
        if e['sha256'] in excluded_shas:
            excluded.append({'stem': stem, 'path': _rel(path), 'sha256': e['sha256'], 'why': 'on the D-D7-1 exclusion list'})
            continue
        if is_pool:
            pe = pool.get(stem) or {}
            if e.get('licence') in (None, '', font_pool.NO_WORDING):
                excluded.append({'stem': stem, 'path': _rel(path), 'sha256': e['sha256'], 'why': 'no licence wording recorded'})
                continue
            licence = {'licence': e['licence'], 'evidence': 'licence text embedded in the face (name table), drawn from the '
                                                           'Day 6 census; the Day 7 grant\'s evidence file',
                       'evidence_path': _rel(font_pool.EVIDENCE), 'evidence_sha256': font_pool.GRANTED_EVIDENCE_SHA256,
                       'wording': str(pe.get('evidence_text') or '')[:200]}
            family_class = pe.get('family_class')
            complete_arabic = bool(pe.get('complete_basic_arabic'))
        else:
            held = licence_by_file.get(str(path.resolve()))
            if held:
                licence = _licence_file_evidence(held[0], held[1])
            else:
                licence = _licence_file_evidence(noto_licence.get(stem, static / 'OFL.txt'), None)
            if licence is None:
                excluded.append({'stem': stem, 'path': _rel(path), 'sha256': e['sha256'], 'why': 'licence file missing or its digest differs'})
                continue
            family_class, complete_arabic = None, bool(e.get('arabic_letters'))
        role = 'display' if e.get('latin') else ('arabic-body' if e.get('arabic') else None)
        rec = font_roles.verify_candidate(role, stem) if role else None
        faces.append({'stem': stem, 'path': str(path), 'sha256': e['sha256'], 'origin': e.get('origin'),
                      'source': 'pool' if is_pool else 'house', 'family': e.get('family') or stem,
                      'postscript': e.get('postscript'), 'variable': bool(e.get('variable')),
                      'axes': {k: list(v) for k, v in (e.get('axes') or {}).items()},
                      'latin': bool(e.get('latin')), 'arabic_letters': bool(e.get('arabic_letters')),
                      'complete_basic_arabic': complete_arabic, 'arabic_flag': bool(e.get('arabic')),
                      'arabic_forms_missing': e.get('arabic_forms_missing'), 'arabic_marks_missing': e.get('arabic_marks_missing'),
                      'family_class': family_class, 'licence': licence, 'theme_roles': roles_of.get(stem, []),
                      'seam': (rec or {}).get('verification') if rec else 'not a candidate for its script',
                      'verified_for_production': bool(rec and rec.get('verification') == VERIFIED_FOR_PRODUCTION)})
    return faces, excluded


def face_from_file(path, *, licence_path, family: str | None = None, source: str = 'house', theme_roles=(), stem: str | None = None) -> dict:
    """A face of ``gather()``'s shape read from a file and its licence file — a fixture, or a face outside the
    catalogue; the seam is not consulted (``seam`` says so). Raises where the licence file gives no evidence."""
    from apps.ire import font_roles
    path = Path(path)
    info = font_roles._inspect(path)
    lic = _licence_file_evidence(Path(licence_path), None)
    if lic is None:
        raise ValueError('no licence evidence: %s' % licence_path)
    return {'stem': stem or path.stem, 'path': str(path), 'sha256': _sha(path), 'origin': 'FILE', 'source': source,
            'family': family or info['family'], 'postscript': info['postscript'], 'variable': info['variable'],
            'axes': {k: list(v) for k, v in info['axes'].items()}, 'latin': info['latin'],
            'arabic_letters': info['arabic_letters'], 'complete_basic_arabic': info['arabic_letters'], 'arabic_flag': info['arabic'],
            'arabic_forms_missing': info['arabic_forms_missing'], 'arabic_marks_missing': info['arabic_marks_missing'],
            'family_class': None, 'licence': lic, 'theme_roles': [dict(r) for r in theme_roles],
            'seam': 'not consulted (a face read from a file)', 'verified_for_production': False}


# --- classes, families and the faces each draws ----------------------------------------------------------------------

def _arabic_class_by_name(row) -> str | None:
    names = ' '.join([row['family']] + [f['family'] + ' ' + f['stem'] for f in row['faces']]).lower()
    return next((cls for pattern, cls in ARABIC_NAME_CLASS if re.search(pattern, names)), None)


def group(faces: list[dict], classified: dict | None = None) -> list[dict]:
    """One row per family (``family_key``), house faces leading; its Latin and Arabic class with the basis."""
    rows = {}
    for f in faces:
        key = family_key(f['family'])
        row = rows.setdefault(key, {'key': key, 'faces': []})
        row['faces'].append(f)
    out = []
    classified = classified or {}
    for key, row in sorted(rows.items()):
        faces_ = sorted(row['faces'], key=lambda f: (f['source'] != 'house', f['stem']))
        house = [f for f in faces_ if f['source'] == 'house']
        names = [f['family'] for f in (house or faces_)]
        row = {'key': key, 'family': min(names, key=lambda n: (len(n), n)), 'faces': faces_,
               'sources': sorted({f['source'] for f in faces_}), 'theme_roles': [dict(r, stem=f['stem']) for f in faces_ for r in f['theme_roles']]}
        # the Latin class
        latin_basis = None
        if key in HOUSE_CLASS and house:
            latin_cls, arabic_cls = HOUSE_CLASS[key]
            latin_basis = arabic_basis = 'the executor\'s house table (type_book.HOUSE_CLASS)'
        else:
            latin_cls, arabic_cls, arabic_basis = None, None, None
            named = collections.Counter(FROM_LETTERING.get(f['family_class']) for f in faces_ if f.get('family_class'))
            if named:
                latin_cls, latin_basis = named.most_common(1)[0][0], 'face names and OS/2 width (font_pool.classify), a heuristic'
        if latin_cls in ('slab', 'sans') and any(f.get('fixed_pitch') for f in faces_ if f['latin']):
            latin_cls, latin_basis = 'mono', (latin_basis or '') + '; mono by the face\'s own fixed pitch (one advance for a-z)'
        model = [classified[f['sha256']] for f in faces_ if f['sha256'] in classified]
        if latin_cls is None:
            if any(f.get('fixed_pitch') for f in faces_ if f['latin']):
                latin_cls, latin_basis = 'mono', 'the face\'s own fixed pitch (one advance for a-z)'
            else:
                votes = collections.Counter()
                for m in model:
                    if m.get('latin_class') in LATIN_CLASSES:
                        votes[m['latin_class']] += float(m.get('confidence') or 0.5)
                if votes:
                    latin_cls, latin_basis = votes.most_common(1)[0][0], 'classified from specimens (model)'
        if arabic_cls is None:
            arabic_cls = _arabic_class_by_name(dict(row, faces=faces_))
            if arabic_cls:
                arabic_basis = 'the family\'s names (type_book.ARABIC_NAME_CLASS)'
            else:
                votes = collections.Counter()
                for m in model:
                    if m.get('arabic_class') in ARABIC_CLASSES:
                        votes[m['arabic_class']] += float(m.get('confidence') or 0.5)
                if votes:
                    arabic_cls, arabic_basis = votes.most_common(1)[0][0], 'classified from specimens (model)'
        row['model'] = [{'stem': f['stem'], **{k: classified[f['sha256']].get(k) for k in ('latin_class', 'arabic_class', 'confidence',
                                                                                           'runs_agree', 'latin_class_runs', 'why')}}
                        for f in faces_ if f['sha256'] in classified]
        has_latin = any(f['latin'] for f in faces_) and not (key in HOUSE_CLASS and house and HOUSE_CLASS[key][0] is None)
        has_arabic = any(f['complete_basic_arabic'] or f['arabic_letters'] for f in faces_)
        row['latin'] = {'class': latin_cls or UNCLASSIFIED, 'basis': latin_basis or 'pending: the names say nothing'} if has_latin else None
        row['arabic'] = {'class': arabic_cls or UNCLASSIFIED, 'basis': arabic_basis or 'pending: the names say nothing'} if has_arabic else None
        out.append(row)
    return out


def _candidates(row: dict, script: str) -> list[dict]:
    """The faces a row may show for ``script``: upright first (italic only where the family has no upright face)."""
    ok = [f for f in row['faces'] if (f['latin'] if script == 'latin' else (f['arabic_letters'] or f['complete_basic_arabic']))]
    upright = [f for f in ok if not f.get('italic')]
    return upright or ok


def _drawn(face: dict, weight: float | None, instance_dir) -> dict:
    """The file a face draws at ``weight``: a static face its own file; a variable face the static instance at that
    wght, every other axis at its default (``font_instances``), made when absent."""
    if not face['variable']:
        return {'path': face['path'], 'weight': face.get('us_weight_class'), 'instance': None}
    axes = face['axes']
    wght = axes.get('wght')
    coords = {'wght': min(max(float(weight), wght[0]), wght[2])} if wght and weight is not None else {}
    made = None
    if wght:
        made = font_instances.static_at(face['stem'], face['sha256'], coords['wght'], out_dir=instance_dir)
    if made is None:
        rec = font_instances.make_instance(face['path'], coords, family=face['family'], licence=face['licence']['licence'],
                                           source_stem=face['stem'], out_dir=instance_dir)
        made = {'path': font_instances._abs(rec['path']) if not Path(rec['path']).is_absolute() else rec['path'],
                'postscript': rec['postscript'], 'sha256': rec['sha256'], 'axes': rec['axes']}
    return {'path': str(made['path']), 'weight': coords.get('wght'), 'instance': {'postscript': made['postscript'], 'sha256': made['sha256'],
                                                                                   'axes': made.get('axes'), 'path': _rel(made['path'])}}


def choose(row: dict, script: str, instance_dir=None) -> dict:
    """``{'regular': …, 'heaviest': …}`` for ``script``: the regular the face nearest 400 (a variable face at 400 inside
    its axis); the heaviest the face whose MEASURED stem is greatest (a variable face at the top of its axis) — the
    declared weight breaks a tie within 2 %, then a file the emitter (reportlab) reads, then a house face, then a static
    file; a family of one face shows it once."""
    cands = _candidates(row, script)
    if not cands:
        return {}
    regular_opts, heavy_opts = [], []
    for f in cands:
        if f['variable'] and f['axes'].get('wght'):
            lo, _d, hi = f['axes']['wght']
            regular_opts.append((f, min(max(400.0, lo), hi)))
            heavy_opts.append((f, hi))
        else:
            w = f.get('us_weight_class') or 400
            regular_opts.append((f, float(w)))
            heavy_opts.append((f, float(w)))
    # the emitter's own reader first: a file reportlab cannot read (CFF outlines) shows only where nothing else can
    reg_face, reg_w = min(regular_opts, key=lambda o: (abs(o[1] - 400.0), not o[0]['reportlab']['ok'], o[0]['source'] != 'house',
                                                       o[0]['variable'], o[0]['stem']))
    regular = dict(_drawn(reg_face, reg_w, instance_dir), stem=reg_face['stem'], asked=reg_w)
    regular['measure'] = font_instances.measure(regular['path'])
    measured = []
    for f, w in heavy_opts:
        d = regular if (f is reg_face and w == reg_w) else dict(_drawn(f, w, instance_dir), stem=f['stem'], asked=w)
        if 'measure' not in d:
            d['measure'] = font_instances.measure(d['path'])
        measured.append((d['measure'].get('stem_em') or 0.0, w, f, d))
    top = max(m[0] for m in measured)
    near = [m for m in measured if m[0] >= top * 0.98]
    _stem, _w, hf, heaviest = max(near, key=lambda m: (m[1], m[2]['reportlab']['ok'], m[2]['source'] == 'house', not m[2]['variable'],
                                                       m[2]['stem']))
    out = {'regular': _face_row(reg_face, regular), 'heaviest': _face_row(hf, heaviest)}
    out['single'] = out['regular']['path_drawn'] == out['heaviest']['path_drawn']
    return out


def _face_row(face: dict, drawn: dict) -> dict:
    m = drawn['measure']
    return {'stem': face['stem'], 'source': face['source'], 'path': _rel(face['path']), 'sha256': face['sha256'],
            'path_drawn': _rel(drawn['path']), 'weight': drawn.get('weight') if drawn.get('weight') is not None else m.get('us_weight_class'),
            'instance': drawn.get('instance'), 'variable': face['variable'], 'italic': bool(face.get('italic')),
            'stem_em': m.get('stem_em'), 'stem_glyph': m.get('glyph'), 'band': m.get('verdict'), 'band_by_name': m.get('verdict_by_name')}


# --- the book --------------------------------------------------------------------------------------------------------

def _annotate(faces: list[dict]) -> None:
    for f in faces:
        if 'cmap' not in f:
            f.update(read_face(f['path']))
        f['emitter_capable'] = bool(f['arabic_flag'] and f['reportlab']['ok'])


def _missing(face_path: str, text: str) -> list[str]:
    from fontTools.ttLib import TTFont
    with TTFont(str(face_path), lazy=True) as ft:
        cmap = set((ft.getBestCmap() or {}).keys())
    return sorted({c for c in text if not c.isspace() and ord(c) not in cmap})


def _family_record(row: dict, script: str, instance_dir) -> dict:
    from apps.dielines.exporters.text_intl import shape_ar
    chosen = choose(row, script, instance_dir)
    faces_ = row['faces']
    shown = [f for f in faces_ if (f['latin'] if script == 'latin' else (f['arabic_letters'] or f['complete_basic_arabic']))]
    licences, seen = [], set()
    for f in shown:
        lic = f['licence']
        k = (lic['licence'], lic['evidence_path'], lic['wording'][:60])
        if k not in seen:
            seen.add(k)
            licences.append(lic)
    specimen = {}
    for which in ('regular', 'heaviest'):
        c = chosen.get(which)
        if not c:
            continue
        drawn = ROOT / c['path_drawn'] if not Path(c['path_drawn']).is_absolute() else Path(c['path_drawn'])
        lines = list(LATIN_LINES) if script == 'latin' else [shape_ar(ARABIC_LINE, keep_harakat=True)]
        rl = _reportlab_reads(drawn)
        face = next(f for f in faces_ if f['stem'] == c['stem'])
        specimen[which] = {'lines': lines if script == 'latin' else [ARABIC_LINE], 'drawn_as': lines,
                           'missing': {ln: _missing(drawn, ln) for ln in lines},
                           'by': 'reportlab (the emitter)' if rl['ok'] else 'raster (PIL basic layout of the same string): reportlab cannot read this file — %s' % rl['why'],
                           'emitter_draws_file': rl['ok'], 'rendered': bool(rl['ok'] or face.get('pil_reads'))}
    rec = {'family': row['family'], 'key': row['key'], 'script': script,
           'class': (row[script] or {}).get('class'), 'class_basis': (row[script] or {}).get('basis'),
           'model': row.get('model') or [], 'sources': row['sources'],
           'theme_roles': row['theme_roles'], 'theme': bool(row['theme_roles']),
           'files': [{'stem': f['stem'], 'path': _rel(f['path']), 'sha256': f['sha256'], 'source': f['source'],
                      'postscript': f['postscript'], 'style': f.get('style'), 'weight': f.get('us_weight_class'),
                      'italic': bool(f.get('italic')), 'variable': f['variable'], 'axes': f['axes'],
                      'instances': font_instances.instances_of(f['stem'], f['sha256'], out_dir=instance_dir) if f['variable'] else [],
                      'scripts': [s for s, ok in (('latin', f['latin']), ('arabic', f['arabic_letters'] or f['complete_basic_arabic'])) if ok],
                      'reportlab_reads': f['reportlab']['ok'], 'outlines': 'CFF' if f.get('cff') else 'TrueType',
                      'seam': f['seam'], 'verified_for_production': f['verified_for_production'],
                      'licence': f['licence']['licence'],
                      **({'emitter_capable': f['emitter_capable'], 'arabic_forms_missing': f['arabic_forms_missing'],
                          'arabic_marks_missing': f['arabic_marks_missing']} if script == 'arabic' else {})}
                     for f in shown],
           'regular': chosen.get('regular'), 'heaviest': chosen.get('heaviest'), 'single_face_shown': chosen.get('single', False),
           'licence': licences, 'specimen': specimen,
           'specimen_rendered': {k: v['rendered'] for k, v in specimen.items()}}
    # the emitter draws only what reportlab reads: a family whose every file has CFF outlines is refused at registration
    rec['emitter_draws'] = any(f['reportlab']['ok'] for f in shown)
    model_rows = [m for m in rec['model'] if m.get('runs_agree') is not None]
    rec['model_runs_agree'] = all(m['runs_agree'] for m in model_rows) if model_rows else None
    if script == 'arabic':
        rec['emitter_capable_faces'] = [f['stem'] for f in shown if f['emitter_capable']]
        rec['emitter_capable'] = bool(rec['emitter_capable_faces'])
        for which in ('regular', 'heaviest'):
            if rec.get(which):
                face = next(f for f in shown if f['stem'] == rec[which]['stem'])
                rec[which]['emitter_capable'] = face['emitter_capable']
                rec[which]['arabic_forms_missing'] = face['arabic_forms_missing']
    return rec


def build(faces: list[dict], out_dir, *, classified: dict | None = None, excluded: list | None = None, instance_dir=None,
          pdf: bool = True, title: str = 'BBROSE type book') -> dict:
    """The book from ``faces`` (``gather()``'s, or any list of the same shape): ``type-book.json`` written after every
    class, then ``type-book.pdf``. Returns the record."""
    out_dir = Path(out_dir)
    _annotate(faces)
    rows = group(faces, classified)
    record = {'schema': SCHEMA, 'title': title, 'built_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'complete': False,
              'rule': {'licence': 'a face without licence evidence is never in the book; nothing on the D-D7-1 exclusion list is',
                       'once': 'every family once per script part: house and GRANTED files of one family (type_book.family_key) '
                               'share its row, house files leading; a family carrying both scripts is listed in each part',
                       'regular_and_heaviest': choose.__doc__.split(':', 1)[1].strip(),
                       'variable': 'a variable face is drawn at a static instance (font_instances, every axis pinned), never its default',
                       'classes': 'house: type_book.HOUSE_CLASS (the executor\'s table); pool: font_pool.classify (names and OS/2 '
                                  'width, a heuristic), mono by fixed pitch; the rest: classified from specimens (model)'},
              'specimen_lines': {'latin': list(LATIN_LINES), 'arabic': ARABIC_LINE},
              'arabic_path': ARABIC_PATH, 'emitter_capable_means': EMITTER_CAPABLE_MEANS,
              'classes': {'latin': list(LATIN_CLASSES), 'arabic': list(ARABIC_CLASSES)},
              'latin': {}, 'arabic': {}, 'excluded': excluded or [], 'counts': {}}
    json_path = out_dir / 'type-book.json'
    for script, classes in (('latin', LATIN_CLASSES), ('arabic', ARABIC_CLASSES)):
        for cls in classes + (UNCLASSIFIED,):
            members = [r for r in rows if r.get(script) and r[script]['class'] == cls]
            members.sort(key=lambda r: (not r['theme_roles'], 'house' not in r['sources'],
                                        (r[script]['basis'] or '').startswith('classified from specimens'), r['family'].lower()))
            record[script][cls] = [_family_record(r, script, instance_dir) for r in members]
            _count(record)
            _write_json(json_path, record)
    shown = {x['sha256'] for s in ('latin', 'arabic') for cls in record[s].values() for f in cls for x in f['files']}
    record['not_shown'] = [{'stem': f['stem'], 'path': _rel(f['path']), 'sha256': f['sha256'],
                            'why': 'carries neither the 52 basic Latin letters nor the 36 basic Arabic letters'}
                           for f in faces if f['sha256'] not in shown]
    record['complete'] = True
    _count(record)
    _write_json(json_path, record)
    if pdf:
        render_pdf(record, out_dir / 'type-book.pdf')
        record['pdf'] = _rel(out_dir / 'type-book.pdf')
        _write_json(json_path, record)
    return record


def _count(record: dict) -> None:
    fams = {s: [f for cls in record[s].values() for f in cls] for s in ('latin', 'arabic')}
    record['counts'] = {
        'families_latin': len(fams['latin']), 'families_arabic': len(fams['arabic']),
        'families': len({f['key'] for s in fams.values() for f in s}),
        'faces': len({x['sha256'] for s in fams.values() for f in s for x in f['files']}),
        'by_class': {s: {cls: len(v) for cls, v in record[s].items()} for s in ('latin', 'arabic')},
        'classified_from_specimens': sum(1 for s in fams.values() for f in s if (f['class_basis'] or '').startswith('classified from specimens')),
        'theme_families': sorted({f['family'] for s in fams.values() for f in s if f['theme']}),
        'arabic_emitter_capable_families': sorted(f['family'] for f in fams['arabic'] if f.get('emitter_capable')),
        'arabic_emitter_capable_faces': sorted({x['stem'] for f in fams['arabic'] for x in f['files'] if x.get('emitter_capable')}),
        'latin_families_the_emitter_cannot_draw': sorted(f['family'] for f in fams['latin'] if f.get('emitter_draws') is False),
        'model_classes_runs_disagree': sorted(f['family'] for s in fams.values() for f in s
                                              if (f['class_basis'] or '').startswith('classified from specimens') and f.get('model_runs_agree') is False),
        'excluded': len(record['excluded'])}


# --- the PDF ---------------------------------------------------------------------------------------------------------

def render_pdf(record: dict, path) -> None:
    """A4, one family per row under its class heading: the regular face left, the heaviest right, the licence line
    under each family."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fallback = _fallback_font()
    c = rl_canvas.Canvas(str(path) + '.tmp', pagesize=A4, pageCompression=1)
    c.setTitle(record['title'])
    W, H = A4
    M = 36.0
    state = {'y': H - M, 'page': 1}

    def new_page():
        c.setFont('Helvetica', 6.5)
        c.setFillColorRGB(0.45, 0.42, 0.40)
        c.drawRightString(W - M, 20, '%s · page %d' % (record['title'], state['page']))
        c.showPage()
        state['page'] += 1
        state['y'] = H - M

    def need(h):
        if state['y'] - h < M:
            new_page()

    # the cover
    c.setFillColorRGB(0.12, 0.10, 0.09)
    c.setFont('Helvetica-Bold', 18)
    c.drawString(M, state['y'] - 18, record['title'])
    state['y'] -= 34
    cnt = record['counts']
    intro = ['%d families (%d in the Latin part, %d in the Arabic part), %d faces; %d families classed from specimens by a model.'
             % (cnt.get('families', 0), cnt.get('families_latin', 0), cnt.get('families_arabic', 0), cnt.get('faces', 0),
                cnt.get('classified_from_specimens', 0)),
             'Licence: ' + record['rule']['licence'] + '. Rights: D-D7-1 (the GRANTED pool) and the house set with its licence files.',
             'Each row: the regular face (left) and the heaviest (right). ' + record['rule']['variable'] + '.',
             'Arabic: ' + record['arabic_path'] + '.',
             'Emitter-capable Arabic: ' + record['emitter_capable_means'] + '.',
             'THEME marks the house\'s theme faces (font_roles.theme_faces()). Grey glyphs in a Latin line are set in Noto Sans: '
             'the face lacks them.',
             'Classes: ' + record['rule']['classes'] + '.']
    c.setFont('Helvetica', 7.5)
    c.setFillColorRGB(0.25, 0.22, 0.20)
    for para in intro:
        for ln in _wrap(para, 'Helvetica', 7.5, W - 2 * M):
            c.drawString(M, state['y'] - 8, ln)
            state['y'] -= 10
        state['y'] -= 3
    for script, title in (('latin', 'LATIN'), ('arabic', 'ARABIC')):
        new_page()
        c.setFont('Helvetica-Bold', 15)
        c.setFillColorRGB(0.12, 0.10, 0.09)
        c.drawString(M, state['y'] - 15, '%s FAMILIES' % title)
        state['y'] -= 28
        for cls, fams in record[script].items():
            if not fams:
                continue
            need(70)
            c.setFillColorRGB(0.55, 0.20, 0.30)
            c.setFont('Helvetica-Bold', 11)
            c.drawString(M, state['y'] - 11, '%s — %s (%d)' % (title.title(), cls, len(fams)))
            state['y'] -= 18
            model_heading = False
            for fam in fams:
                if (fam['class_basis'] or '').startswith('classified from specimens') and not model_heading:
                    need(60)
                    c.setFillColorRGB(0.40, 0.36, 0.33)
                    c.setFont('Helvetica-Oblique', 8)
                    c.drawString(M, state['y'] - 8, 'classified from specimens (model)')
                    state['y'] -= 13
                    model_heading = True
                _draw_family(c, fam, script, M, W, state, need, fallback)
    new_page()
    c.save()
    os.replace(str(path) + '.tmp', path)


def _fallback_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont as RLFont
    p = Path(__file__).resolve().parents[2] / 'static' / 'fonts' / 'NotoSans-Regular.ttf'
    if 'TB-fallback' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(RLFont('TB-fallback', str(p)))
    return 'TB-fallback'


def _fit(text: str, font: str, size: float, width: float) -> str:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + '…', font, size) > width:
        text = text[:-1]
    return text + '…'


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words, lines, cur = text.split(), [], ''
    for w in words:
        trial = (cur + ' ' + w).strip()
        if stringWidth(trial, font, size) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_family(c, fam, script, M, W, state, need, fallback) -> None:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    lic_lines = []
    for lic in fam['licence']:
        lic_lines += _wrap('Licence: %s — %s %s (sha256 %s…): “%s”' % (lic['licence'], lic['evidence'], lic['evidence_path'],
                                                                     lic['evidence_sha256'][:12], lic['wording'][:150]),
                           'Helvetica', 5.6, W - 2 * M)
    lic_lines = lic_lines[:4]
    body = 84.0 if script == 'latin' else 58.0
    h = 14 + body + 7.0 * len(lic_lines) + 10
    need(h)
    y = state['y']
    c.setStrokeColorRGB(0.85, 0.82, 0.79)
    c.setLineWidth(0.4)
    c.line(M, y, W - M, y)
    c.setFillColorRGB(0.12, 0.10, 0.09)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(M, y - 11, fam['family'])
    x = M + stringWidth(fam['family'], 'Helvetica-Bold', 9) + 8
    tags = ['%s' % ' + '.join(fam['sources']), '%d file%s' % (len(fam['files']), '' if len(fam['files']) == 1 else 's')]
    var = [f for f in fam['files'] if f['variable']]
    if var:
        tags.append('variable ' + ', '.join('%s %g–%g' % (k, v[0], v[2]) for k, v in var[0]['axes'].items()))
    if fam['class_basis']:
        tags.append('class: %s%s' % (fam['class_basis'], ' — runs disagree' if fam.get('model_runs_agree') is False
                                     and fam['class_basis'].startswith('classified from specimens') else ''))
    if fam.get('emitter_draws') is False:
        tags.append('THE EMITTER CANNOT DRAW IT (CFF outlines)')
    if script == 'arabic':
        tags.append('EMITTER-CAPABLE: ' + ', '.join(s[:28] for s in fam['emitter_capable_faces']) if fam['emitter_capable']
                    else 'NOT emitter-capable')
    theme_tag = ''
    if fam['theme']:
        roles = ', '.join(sorted({'%s%s' % (r['role'], (' @%g' % r['weight']) if r.get('weight') else '') for r in fam['theme_roles']}))
        theme_tag = 'THEME · ' + roles
        c.setFillColorRGB(0.70, 0.18, 0.35)
        c.setFont('Helvetica-Bold', 6.5)
        c.drawRightString(W - M, y - 11, theme_tag)
    room = W - M - x - (stringWidth(theme_tag, 'Helvetica-Bold', 6.5) + 10 if theme_tag else 0)
    c.setFont('Helvetica', 6.2)
    c.setFillColorRGB(0.42, 0.39, 0.36)
    c.drawString(x, y - 11, _fit(' · '.join(tags), 'Helvetica', 6.2, room))
    col_w = (W - 2 * M - 12) / 2.0
    for i, which in enumerate(('regular', 'heaviest')):
        face = fam.get(which)
        if not face:
            continue
        x0 = M + i * (col_w + 12)
        y0 = y - 22
        c.setFont('Helvetica', 5.8)
        c.setFillColorRGB(0.45, 0.42, 0.40)
        label = '%s · %s · %s%s · stem %s/em (%s)' % (
            which.upper(), ('%g' % face['weight']) if face.get('weight') is not None else '—',
            (face['instance'] or {}).get('postscript') or face['stem'][:44],
            ' (static instance)' if face.get('instance') else '', face.get('stem_em'), face.get('band'))
        if fam['single_face_shown'] and which == 'heaviest':
            label = 'HEAVIEST · the family has one face to show — as left'
        c.drawString(x0, y0, label[:120])
        if fam['single_face_shown'] and which == 'heaviest':
            continue
        spec = fam['specimen'][which]
        drawn = ROOT / face['path_drawn'] if not Path(face['path_drawn']).is_absolute() else Path(face['path_drawn'])
        rl = _reportlab_reads(drawn)
        if script == 'latin':
            sizes = (20.0, 8.6, 12.0)
            yy = y0 - 22
            for ln, size in zip(spec['drawn_as'], sizes):
                _draw_line(c, ln, drawn, rl, size, x0, yy, col_w, spec['missing'].get(ln) or [], fallback, rtl=False)
                yy -= size + 7
        else:
            ln = spec['drawn_as'][0]
            _draw_line(c, ln, drawn, rl, 20.0, x0, y0 - 28, col_w, spec['missing'].get(ln) or [], None, rtl=True)
            miss = face.get('arabic_forms_missing')
            c.setFont('Helvetica', 5.6)
            c.setFillColorRGB(0.20, 0.45, 0.25) if face.get('emitter_capable') else c.setFillColorRGB(0.70, 0.20, 0.20)
            c.drawString(x0, y0 - 42, ('emitter-capable' if face.get('emitter_capable') else
                                       'not emitter-capable: %s presentation form(s) the reshaper emits are missing%s'
                                       % (miss, '' if rl['ok'] else '; reportlab cannot read the file')))
    yy = y - 14 - body - 2
    c.setFont('Helvetica', 5.6)
    c.setFillColorRGB(0.40, 0.37, 0.35)
    for ln in lic_lines:
        c.drawString(M, yy, ln)
        yy -= 7.0
    state['y'] = yy - 6


def _draw_line(c, text, path, rl, size, x0, y, width, missing, fallback, *, rtl) -> None:
    """One specimen line in the face, shrunk to the column; missing Latin glyphs set in Noto Sans, grey."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    if rl['ok']:
        name = rl['name']
        runs, cur = [], ''
        for ch in text:
            miss = ch in missing and fallback is not None
            if runs and runs[-1][1] == miss:
                runs[-1][0] += ch
            else:
                runs.append([ch, miss])
        def width_at(s):
            return sum(stringWidth(t, fallback if m else name, s) for t, m in runs)
        while size > 5 and width_at(size) > width:
            size -= 0.5
        x = x0 + width - width_at(size) if rtl else x0
        for t, m in runs:
            c.setFont(fallback if m else name, size)
            c.setFillColorRGB(0.62, 0.60, 0.58) if m else c.setFillColorRGB(0.10, 0.08, 0.07)
            c.drawString(x, y, t)
            x += stringWidth(t, fallback if m else name, size)
        return
    # reportlab cannot read the file: a raster of the same string, PIL's basic layout (no shaping), marked
    import io
    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader
    px_per_pt = 8
    try:
        font = ImageFont.truetype(str(path), int(size * px_per_pt), layout_engine=ImageFont.Layout.BASIC)
        bbox = font.getbbox(text)
        im = Image.new('L', (max(1, bbox[2] - min(0, bbox[0]) + 4), int(size * px_per_pt * 1.5)), 255)
        ImageDraw.Draw(im).text((2 - min(0, bbox[0]), int(size * px_per_pt * 0.2)), text, font=font, fill=20)
        # [Day 8 §8] the raster's size is in PIXELS, named so: unit_analysis reads `.width` / `.height` as millimetres,
        # and `im.width / scale` was reported as mm reaching a pt name (a false PT_FROM_MM, repaired at the source)
        width_px, height_px = im.size
        w_pt = width_px / px_per_pt
        h_pt = height_px / px_per_pt
        if w_pt > width:
            h_pt *= width / w_pt
            w_pt = width
        buf = io.BytesIO()
        im.save(buf, format='PNG')
        buf.seek(0)
        x = x0 + width - w_pt if rtl else x0
        c.drawImage(ImageReader(buf), x, y - h_pt * 0.25, width=w_pt, height=h_pt, mask=None)
        c.setFont('Helvetica', 4.8)
        c.setFillColorRGB(0.70, 0.20, 0.20)
        c.drawString(x0, y - 6.5 if not rtl else y - 4.5, 'raster — the emitter (reportlab) cannot read this file')
    except Exception as exc:     # noqa: BLE001 — the row says the line was not drawn
        c.setFont('Helvetica', 6)
        c.setFillColorRGB(0.70, 0.20, 0.20)
        c.drawString(x0, y, 'not drawn: %s' % str(exc)[:80])


# --- specimens for the model, and its classes -------------------------------------------------------------------------

def specimen_png(face: dict, path, instance_dir=None) -> Path:
    """One face's specimen for a vision reading: "Enchanted Rose", "Aa Bb Qq Rr 0123" and, where it carries the Arabic
    letters, the Arabic line (PIL with raqm shaping — the face's own design, for classing only); a variable face at 400."""
    from PIL import Image, ImageDraw, ImageFont
    drawn = _drawn(face, 400.0, instance_dir) if face['variable'] else {'path': face['path']}
    p = drawn['path']
    lines = [(LATIN_LINES[0], 64, 'ltr', None), (LATIN_LINES[2], 44, 'ltr', None)] if face['latin'] else []
    if face['arabic_letters'] or face['complete_basic_arabic']:
        lines.append((ARABIC_LINE, 60, 'rtl', 'ar'))
    W, H = 900, 40 + sum(int(s * 1.7) for _t, s, _d, _l in lines)
    im = Image.new('RGB', (W, max(H, 120)), (255, 255, 255))
    d = ImageDraw.Draw(im)
    y = 20
    for text, size, direction, lang in lines:
        try:
            font = ImageFont.truetype(str(p), size)
            if direction == 'rtl':
                w = d.textlength(text, font=font, direction='rtl', language=lang)
                d.text((W - 30 - w, y), text, font=font, fill=(20, 18, 16), direction='rtl', language=lang)
            else:
                d.text((30, y), text, font=font, fill=(20, 18, 16))
        except Exception:         # noqa: BLE001 — the specimen shows what it can
            pass
        y += int(size * 1.7)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


CLASSIFY_SYSTEM = (
    'You are a senior type director classifying typefaces from specimen images for a cosmetics brand\'s type book. '
    'Each specimen shows one font: "Enchanted Rose" and "Aa Bb Qq Rr 0123", and sometimes an Arabic line. Classify what '
    'you SEE in the letterforms, never a name (none is shown). Latin classes: didone (high-contrast vertical stress, '
    'hairline serifs, fashion), serif (any other serif: old-style, transitional, glyphic, wedge), slab (heavy rectangular '
    'serifs, proportional), sans, condensed (narrow proportions, sans or serif), display (decorative, novelty, outline, '
    'shadow, stencil, very heavy rounded or quirky forms meant for headlines), script (joined or brush or handwriting), '
    'mono (every letter the same width). Arabic classes (only where an Arabic line is shown): naskh (classic cursive, '
    'round bowls, contrast), kufi (geometric, angular or low-contrast modern sans-like), display (calligraphic ruqaa/'
    'diwani/thuluth/nastaliq or decorative). Answer every specimen with its number, the class, the Arabic class or '
    '"none", your confidence 0–1, and a reason in under 15 words.')
CLASSIFY_TOOL = {'name': 'record_classes', 'description': 'Record the class of each numbered specimen.',
                 'input_schema': {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {
                     'type': 'object', 'properties': {
                         'n': {'type': 'integer'},
                         'latin_class': {'type': 'string', 'enum': list(LATIN_CLASSES) + ['none']},
                         'arabic_class': {'type': 'string', 'enum': list(ARABIC_CLASSES) + ['none']},
                         'confidence': {'type': 'number'}, 'why': {'type': 'string'}},
                     'required': ['n', 'latin_class', 'arabic_class', 'confidence', 'why']}}}, 'required': ['items']}}
CLASSIFY_MODEL = 'claude-haiku-4-5'
CLASSIFY_PREFIX = 'day8/fonts/'
CLASSIFY_CAP = 1.5


def unclassified_faces(faces: list[dict]) -> list[dict]:
    """The GRANTED pool's faces the names leave unclassified (``family_class`` None in the Day 7 record), by stem;
    a brand duplicate (classed by the house table) included so the count is the record's."""
    from apps.ire import font_pool
    by_sha = {f['sha256']: f for f in faces}
    out = []
    for e in font_pool.catalogue_entries():
        if e.get('family_class'):
            continue
        f = by_sha.get(e['sha256'])       # a brand duplicate is found under the house entry carrying the same bytes
        if f is None:
            continue
        out.append(f)
    return sorted(out, key=lambda f: f['stem'])


def _stamped_block(png, n: int) -> dict:
    """The specimen as an image block with its number stamped in its top-right corner, so the model ties each answer to
    the picture it read (the first run, unstamped, tied some answers to a neighbour: Merriweather Bold read 'sans')."""
    import base64
    import io
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(png).convert('RGB')
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(str(Path(__file__).resolve().parents[2] / 'static' / 'fonts' / 'NotoSans-Bold.ttf'), 40)
    except OSError:
        font = ImageFont.load_default()
    label = '#%d' % n
    w = d.textlength(label, font=font)
    d.rectangle((im.width - w - 36, 8, im.width - 8, 62), fill=(200, 30, 60))
    d.text((im.width - w - 22, 10), label, font=font, fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                        'data': base64.standard_b64encode(buf.getvalue()).decode('ascii')}}


def classify_from_specimens(faces: list[dict], out_dir=OUT, *, batch: int = 12, instance_dir=None, specimen_dir=None,
                            client=None, model: str = CLASSIFY_MODEL, run: int = 1) -> dict:
    """One vision call per batch of ~12 specimens (``model``), every call reserved first through ``paid_operation``
    (operation 'day8/fonts/classify-NN', the prefix's cap ``CLASSIFY_CAP``). Each batch's answers are appended to
    ``fonts-classified.jsonl`` at once; a face already answered there is not asked again. Returns ``{sha256: answer}``."""
    from apps.pipeline.services.spend_reservation import paid_operation
    from apps.pipeline.services.claude_service import image_block_from_file
    out_dir = Path(out_dir)
    jsonl = out_dir / 'fonts-classified.jsonl'
    done = {}
    if jsonl.exists():
        for ln in jsonl.read_text(encoding='utf-8').splitlines():
            if ln.strip():
                row = json.loads(ln)
                if (row.get('latin_class') or row.get('arabic_class')) and int(row.get('run') or 1) == run:
                    done[row['sha256']] = row
    batches_before = [int(json.loads(ln).get('batch') or 0) for ln in jsonl.read_text(encoding='utf-8').splitlines()
                      if ln.strip()] if jsonl.exists() else []
    todo = [f for f in faces if f['sha256'] not in done]
    specimen_dir = Path(specimen_dir) if specimen_dir else out_dir / 'specimens'
    if client is None:
        import anthropic
        from django.conf import settings
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY or None, max_retries=0, timeout=120)
    first = 1 + max(batches_before or [0])            # operation numbers never repeat across runs
    for b, start in enumerate(range(0, len(todo), batch), first):
        chunk = todo[start:start + batch]
        content = [{'type': 'text', 'text': 'Classify each of these %d numbered type specimens. Each picture carries its '
                                            'number in a red box at its top right; answer each number from its own '
                                            'picture only.' % len(chunk)}]
        for n, f in enumerate(chunk, 1):
            png = specimen_png(f, specimen_dir / ('%s.png' % f['sha256'][:16]), instance_dir)
            block = _stamped_block(png, n) if run > 1 else image_block_from_file(str(png))
            content += [{'type': 'text', 'text': 'Specimen #%d:' % n}, block]
        operation = 'day8/fonts/classify-%02d' % b
        response = paid_operation(client.messages.create, provider='anthropic', operation=operation,
                                  reservation_prefix=CLASSIFY_PREFIX, reservation_cap=CLASSIFY_CAP, model=model,
                                  max_tokens=2000, system=CLASSIFY_SYSTEM, messages=[{'role': 'user', 'content': content}],
                                  tools=[CLASSIFY_TOOL], tool_choice={'type': 'tool', 'name': 'record_classes'})
        items = next((blk.input.get('items') for blk in response.content
                      if getattr(blk, 'type', '') == 'tool_use' and isinstance(getattr(blk, 'input', None), dict)), None) or []
        usage = response.model_dump(mode='json').get('usage') or {}
        by_n = {int(i.get('n', 0)): i for i in items if isinstance(i, dict)}
        with jsonl.open('a', encoding='utf-8') as fh:
            for n, f in enumerate(chunk, 1):
                ans = by_n.get(n) or {}
                latin = ans.get('latin_class') if ans.get('latin_class') in LATIN_CLASSES else None
                arabic = ans.get('arabic_class') if ans.get('arabic_class') in ARABIC_CLASSES else None
                row = {'sha256': f['sha256'], 'stem': f['stem'], 'family': f['family'], 'run': run, 'batch': b, 'n': n, 'model': model,
                       'operation': operation, 'latin_class': latin, 'arabic_class': arabic,
                       'confidence': ans.get('confidence'), 'why': ans.get('why'), 'raw': ans or None,
                       'reservation_id': getattr(response, '_rescue_reservation_id', None),
                       'specimen': _rel(specimen_dir / ('%s.png' % f['sha256'][:16])),
                       'batch_usage': usage if n == 1 else None}
                fh.write(json.dumps(row, ensure_ascii=False) + '\n')
                if latin or arabic:
                    done[f['sha256']] = row
            fh.flush()
            os.fsync(fh.fileno())
    return done


def summarise_classified(out_dir=OUT, ledger=None) -> dict:
    """fonts-classified.json: the model's classes for the faces the names left unclassified, from the jsonl."""
    out_dir = Path(out_dir)
    runs = _runs(out_dir)
    chosen = classified_map(out_dir)
    items = sorted(chosen.values(), key=lambda r: r['stem'])
    agreement = None
    if len(runs) > 1:
        first, last = runs[min(runs)], runs[max(runs)]
        both = [s for s in last if s in first and first[s].get('latin_class') and last[s].get('latin_class')]
        agreement = {'runs': sorted(runs), 'faces_in_both': len(both),
                     'latin_class_same': sum(1 for s in both if first[s]['latin_class'] == last[s]['latin_class']),
                     'changed': [{'stem': last[s]['stem'], 'family': last[s]['family'], 'run_%d' % min(runs): first[s]['latin_class'],
                                  'run_%d' % max(runs): last[s]['latin_class']} for s in both
                                 if first[s]['latin_class'] != last[s]['latin_class']],
                     'used': 'every run folded: per face the class with the greatest summed confidence (classified_map); '
                             'run %d had each picture\'s number stamped on it' % max(runs)}
    record = {'schema': 'day8_fonts_classified/1', 'model': CLASSIFY_MODEL, 'operation_prefix': CLASSIFY_PREFIX,
              'rule': 'one vision call per batch of ~12 specimens; the model reads the letterforms (no names shown); '
                      'classes are recorded with the model\'s confidence and folded into the type book under '
                      '"classified from specimens (model)"; an answer outside the vocabulary is kept raw and the face stays '
                      'unclassified',
              'faces': len(items), 'classified_latin': sum(1 for r in items if r.get('latin_class')),
              'classified_arabic': sum(1 for r in items if r.get('arabic_class')),
              'by_latin_class': dict(collections.Counter(r.get('latin_class') or 'none' for r in items)),
              'by_arabic_class': dict(collections.Counter(r.get('arabic_class') for r in items if r.get('arabic_class'))),
              'mean_confidence': round(sum(float(r.get('confidence') or 0) for r in items) / max(1, len(items)), 3),
              'runs_agree': sum(1 for r in items if r.get('runs_agree')), 'runs_disagree': [
                  {'family': r['family'], 'stem': r['stem'], 'latin': r.get('latin_class_runs'), 'arabic': r.get('arabic_class_runs'),
                   'folded': r.get('latin_class') or r.get('arabic_class')} for r in items if not r.get('runs_agree')],
              'batches': len({r['batch'] for r in items}), 'runs_agreement': agreement, 'ledger': ledger, 'items': items}
    _write_json(out_dir / 'fonts-classified.json', record)
    return record


def _runs(out_dir=OUT) -> dict:
    """``{run: {sha256: row}}`` from the jsonl (a row without a run is the first run's)."""
    p = Path(out_dir) / 'fonts-classified.jsonl'
    runs: dict = {}
    if p.exists():
        for ln in p.read_text(encoding='utf-8').splitlines():
            if ln.strip():
                r = json.loads(ln)
                runs.setdefault(int(r.get('run') or 1), {})[r['sha256']] = r
    return runs


def classified_map(out_dir=OUT) -> dict:
    """``{sha256: answer}`` — every run folded: for each face the class with the greatest summed confidence across the
    runs (Latin and Arabic apart), the confidence their mean over the runs (a class one run gave and another did not
    counts 0 for the other), ``runs_agree`` whether every run said the same."""
    runs = _runs(out_dir)
    shas = {sha for rows in runs.values() for sha in rows}
    out = {}
    for sha in shas:
        answers = [rows[sha] for _run, rows in sorted(runs.items()) if sha in rows]
        folded = dict(answers[-1])
        for field in ('latin_class', 'arabic_class'):
            votes = collections.Counter()
            for a in answers:
                if a.get(field):
                    votes[a[field]] += float(a.get('confidence') or 0.5)
            if votes:
                cls, total = votes.most_common(1)[0]
                folded[field] = cls
                folded[field + '_confidence'] = round(total / len(answers), 3)
                folded[field + '_runs'] = [a.get(field) for a in answers]
            else:
                folded[field] = None
        folded['runs'] = len(answers)
        folded['runs_agree'] = all(a.get('latin_class') == answers[0].get('latin_class') and a.get('arabic_class') == answers[0].get('arabic_class')
                                   for a in answers)
        folded['confidence'] = folded.get('latin_class_confidence') or folded.get('arabic_class_confidence')
        if folded['latin_class'] or folded['arabic_class']:
            out[sha] = folded
    return out


def face_for(book: dict, family: str, weight: float, script: str = 'latin') -> dict | None:
    """A direction's request — a family of the book at a weight — as the file to draw: a static face of that weight, or
    a variable face's static instance at it (made when absent). ``{stem, path, weight, instance}`` or None."""
    key = family_key(family)
    fam = next((f for cls in book.get(script, {}).values() for f in cls if f['key'] == key), None)
    if fam is None:
        return None
    best = None
    for f in fam['files']:
        if f['italic']:
            continue
        if f['variable'] and f['axes'].get('wght'):
            lo, _d, hi = f['axes']['wght']
            at = min(max(float(weight), lo), hi)
        else:
            at = float(f['weight'] or 400)
        cost = (abs(at - float(weight)), f['source'] != 'house', f['variable'])
        if best is None or cost < best[0]:
            best = (cost, f, at)
    if best is None:
        return None
    _cost, f, at = best
    if not f['variable']:
        return {'stem': f['stem'], 'path': str(ROOT / f['path']), 'weight': at, 'instance': None}
    face = {'stem': f['stem'], 'path': str(ROOT / f['path']), 'sha256': f['sha256'], 'variable': True, 'axes': f['axes'],
            'family': fam['family'], 'licence': {'licence': f['licence']}}
    drawn = _drawn(face, at, None)
    return {'stem': f['stem'], 'path': drawn['path'], 'weight': at, 'instance': drawn['instance']}


def build_book(*, pdf: bool = True) -> dict:
    """The Day 8 book from the catalogue: ``gather()``, the model's classes folded (``classified_map``), JSON per class,
    then the PDF, into ``OUT``."""
    faces, excluded = gather()
    return build(faces, OUT, classified=classified_map(), excluded=excluded, pdf=pdf)


def ledger_spend(prefix: str = CLASSIFY_PREFIX) -> dict:
    """The rescue ledger's calls and accounted USD under ``prefix``."""
    import sqlite3
    from django.conf import settings
    path = Path(getattr(settings, 'RESCUE_SPEND_ROOT', Path(settings.BASE_DIR) / 'var' / 'rescue_spend')) / 'ledger.sqlite3'
    with sqlite3.connect(str(path)) as db:
        n, total, settled = db.execute("SELECT COUNT(*), COALESCE(SUM(accounted),0), SUM(state='usage_recorded') FROM calls "
                                       "WHERE substr(operation,1,?)=?", (len(prefix), prefix)).fetchone()
    return {'prefix': prefix, 'calls': n, 'usd_accounted': total / 1e6, 'usage_recorded': settled}


if __name__ == '__main__':          # python -m apps.ire.type_book [book|classify RUN|instances|stems]
    import logging
    import sys
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    logging.getLogger('fontTools').setLevel(logging.WARNING)
    what = sys.argv[1] if len(sys.argv) > 1 else 'book'
    if what == 'classify':
        faces_, _x = gather()
        _annotate(faces_)
        classify_from_specimens(unclassified_faces(faces_), OUT, batch=12, run=int(sys.argv[2]) if len(sys.argv) > 2 else 1)
        summarise_classified(OUT, ledger=ledger_spend())
        what = 'book'
    if what == 'instances':
        print(json.dumps(font_instances.write_variable_instances()['counts']))
    elif what == 'stems':
        print(json.dumps(font_instances.write_stem_weights()['by_verdict']))
    elif what == 'book':
        summarise_classified(OUT, ledger=ledger_spend()) if (OUT / 'fonts-classified.jsonl').exists() else None
        print(json.dumps(build_book()['counts'], ensure_ascii=False))
