"""Day 7 §4: the GRANTED font pool (Day 6 census) as the type classifier's enlarged candidate set, and the exclusion
list D-D7-1 orders — UNVERIFIED and BLOCKED faces excluded, not deleted, by a list the loader and the Library page read.
Nothing under materials/ is written; the census and this list are the only records.
"""
from pathlib import Path
import datetime, json, threading

ROOT = Path(__file__).resolve().parents[3]
CENSUS = ROOT / 'docs/audit/day-6/library'
EXCLUDED = ROOT / 'docs/audit/day-7/library/fonts-excluded.json'
_lock = threading.Lock(); _cache = {}


def pool(name) -> list[dict]:
    """The faces of one census pool: granted, unverified or blocked."""
    return json.loads((CENSUS / ('fonts-%s.json' % name)).read_text(encoding='utf-8')).get('faces') or []


def files_of(name) -> dict:
    """The pool's files by content hash: ``{sha: {path, family, faces, pool, reason, evidence}}``."""
    out = {}
    for face in pool(name):
        sha = face.get('source_sha256')
        if not sha:
            continue
        names = face.get('names') or {}; basis = face.get('pool_basis') or {}
        row = out.setdefault(sha, {'sha256': sha, 'path': face.get('source_path'), 'family': names.get('family_typographic') or names.get('family_legacy')
                                   or Path(face.get('source_path') or '').stem, 'faces': [], 'pool': face.get('pool'), 'reason': str(basis.get('reason') or '')[:200],
                                   'evidence': basis.get('evidence'), 'arabic': False, 'variable': False})
        row['faces'].append({'face_id': face.get('face_id'), 'full_name': names.get('full_name'), 'postscript_name': names.get('postscript_name'),
                             'weight_class': face.get('weight_class'), 'italic': bool(face.get('italic')), 'scripts': face.get('scripts') or [],
                             'is_variable': bool(face.get('is_variable')), 'variable_axes': face.get('variable_axes') or [], 'glyph_count': face.get('glyph_count'),
                             'collection_index': face.get('collection_index')})
        row['arabic'] = row['arabic'] or 'arabic' in (face.get('scripts') or []); row['variable'] = row['variable'] or bool(face.get('is_variable'))
    return out


def write_excluded() -> dict:
    """fonts-excluded.json: every UNVERIFIED and BLOCKED file, with its pool and the census's reason. D-D7-1."""
    files = []
    for name in ('unverified', 'blocked'):
        for row in files_of(name).values():
            files.append({'sha256': row['sha256'], 'path': row['path'], 'family': row['family'], 'faces': len(row['faces']), 'pool': row['pool'],
                          'arabic': row['arabic'], 'reason': row['reason'] or ('no licence evidence' if row['pool'] == 'UNVERIFIED' else 'blocked by the census')})
    files.sort(key=lambda f: (f['pool'], f['family'] or '', f['path'] or ''))
    record = {'schema': 'day7_fonts_excluded/1', 'rule': 'D-D7-1: UNVERIFIED and BLOCKED fonts are excluded, not deleted; a font leaves this list only when '
              'its licence evidence is added and the census moves it to GRANTED', 'written_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'counts': {'files': len(files), 'faces': sum(f['faces'] for f in files), 'UNVERIFIED': sum(1 for f in files if f['pool'] == 'UNVERIFIED'),
                         'BLOCKED': sum(1 for f in files if f['pool'] == 'BLOCKED'), 'arabic_files': sum(1 for f in files if f['arabic'])},
              'shown_as': 'Excluded fonts (no licence evidence)', 'files': files}
    EXCLUDED.parent.mkdir(parents=True, exist_ok=True); EXCLUDED.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return {k: v for k, v in record.items() if k != 'files'}


def excluded() -> dict:
    """The exclusion list by content hash, read once per change of the file."""
    try:
        stat = EXCLUDED.stat(); key = (stat.st_size, stat.st_mtime_ns)
    except OSError:
        return {}
    with _lock:
        if _cache.get('key') != key:
            data = json.loads(EXCLUDED.read_text(encoding='utf-8')); _cache['key'] = key
            _cache['files'] = {f['sha256']: f for f in data.get('files') or []}
        return _cache['files']


def is_excluded(sha: str) -> bool:
    return sha in excluded()


# --- the pool as catalogue entries, chains and grants (D-D7-1) ---------------------------------------------------------------

CATALOGUE_RECORD = ROOT / 'docs/audit/day-7/library/fonts-granted-catalogue.json'
GRANTED_CENSUS = CENSUS / 'fonts-granted.json'
EVIDENCE = ROOT / 'docs/audit/day-7/library/fonts-granted-evidence.json'
#: the evidence file's digest the Day 7 grants pin (each GRANTED file's licence wording and embedded licence text, drawn
#: from the census; small, because the channel re-hashes a grant's evidence on every application)
GRANTED_EVIDENCE_SHA256 = '4d5203679e37c8f49adb35eb989b706b16529f5ce1b3225a1093f0de86837e1f'
#: the census file's digest the evidence file was drawn from
GRANTED_CENSUS_SHA256 = 'd739397ffbd8f6a0d12732adf534624ef115e2d035da711070b71a3263bf19ba'
ORIGIN = 'MATERIALS_GRANTED_D-D7-1'
LICENCES = (('open font licen', 'SIL Open Font License, Version 1.1'), ('ofl', 'SIL Open Font License, Version 1.1'),
            ('apache', 'Apache License, Version 2.0'), ('ubuntu font licen', 'Ubuntu Font Licence 1.0'))
NO_WORDING = 'recorded free licence (census pool_basis), wording not embedded'
NAME_KEYS = ('family_typographic', 'family_legacy', 'subfamily_typographic', 'subfamily_legacy', 'full_name', 'postscript_name')


def licence_of(text) -> str:
    low = (text or '').lower()
    return next((name for key, name in LICENCES if key in low), NO_WORDING)


def classify(names: dict, width_class) -> str | None:
    """A lettering family of lettering_faces.FAMILIES from the face's NAMES and OS/2 width — a heuristic, recorded as
    such; None where the names say nothing (the face is listed, never chained)."""
    import re
    low = ' '.join(str(names.get(k) or '') for k in NAME_KEYS).lower()
    serif = 'serif' in low and 'sans' not in low
    if re.search(r'script|brush|hand|callig|signature|cursive', low):
        return 'script'
    if re.search(r'slab|mono|courier|typewriter', low):
        return 'slab'
    if width_class in ('CONDENSED', 'EXTRA_CONDENSED', 'ULTRA_CONDENSED', 'SEMI_CONDENSED') or re.search(r'condensed|narrow|compressed', low):
        return 'condensed-serif' if serif else 'condensed'
    if re.search(r'didone|bodoni|didot|playfair|fashion', low):
        return 'didone'
    if re.search(r'garamond|caslon|jenson|bembo|cormorant', low):
        return 'old-style'
    if re.search(r'cinzel|trajan|capitals', low):
        return 'roman-capitals'
    if serif or re.search(r'baskerville|times|georgia', low):
        return 'transitional'
    if width_class in ('EXPANDED', 'EXTRA_EXPANDED', 'ULTRA_EXPANDED', 'SEMI_EXPANDED') or re.search(r'wide|extended|expanded', low):
        return 'wide-sans'
    if re.search(r'sans|grotesk|gothic|geometric|neue|helvetica|montserrat|poppins|roboto|lato|raleway|futura|avenir|gill', low):
        return 'sans'
    return None


def build_catalogue_record() -> dict:
    """fonts-granted-catalogue.json: every GRANTED file resolved through the manifest, its digest checked against the census,
    inspected by the font seam's own reader (font_roles._inspect), with its licence wording and a family class."""
    import collections, hashlib, time
    from apps.ire import font_roles as FR
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    files = {}
    for face in pool('granted'):
        files.setdefault(face['source_sha256'], []).append(face)
    brand = FR.catalogue(); brand_shas = {e['sha256'] for e in brand.values()}
    started = time.time(); entries, problems, stems = [], [], collections.Counter()
    for sha, faces in files.items():
        face = faces[0]
        try:
            path = resolve_material_file(face['source_path'], repo_root=ROOT, expected_sha=sha)
        except MaterialPathError as exc:
            problems.append({'sha256': sha, 'path': face['source_path'], 'problem': 'resolve: ' + str(exc)[:100]}); continue
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            problems.append({'sha256': sha, 'path': face['source_path'], 'problem': 'missing or digest differs'}); continue
        try:
            inspected = FR._inspect(path)
        except Exception as exc:    # noqa: BLE001 — a face the reader cannot parse is listed as a problem, never silently dropped
            problems.append({'sha256': sha, 'path': face['source_path'], 'problem': 'inspect: ' + type(exc).__name__}); continue
        names = face.get('names') or {}; basis = face.get('pool_basis') or {}; evidence = basis.get('evidence') or {}
        stems[path.stem] += 1
        entries.append({'stem': path.stem, 'path': str(path.relative_to(ROOT)), 'sha256': sha, 'origin': ORIGIN, 'already_in_brand_catalogue': sha in brand_shas,
                        'licence': licence_of(evidence.get('text')), 'evidence_type': evidence.get('type'), 'evidence_text': str(evidence.get('text') or '')[:160],
                        'census_reason': str(basis.get('reason') or '')[:120], 'census_family': names.get('family_typographic') or names.get('family_legacy'),
                        'faces_in_file': len(faces), 'weight_class': face.get('weight_class'), 'width_class': face.get('width_class'), 'italic': bool(face.get('italic')),
                        'is_variable': bool(face.get('is_variable')), 'scripts': sorted({s for x in faces for s in (x.get('scripts') or [])}),
                        'complete_basic_arabic': any((x.get('actual_coverage') or {}).get('complete_basic_arabic') for x in faces),
                        'family_class': classify(names, face.get('width_class')), 'class_basis': 'face names and OS/2 width, a heuristic', **inspected})
    for e in entries:
        e['catalogue_stem'] = e['stem'] + '@' + e['sha256'][:8] if (e['stem'] in brand or stems[e['stem']] > 1) else e['stem']
    record = {'schema': 'day7_fonts_granted_catalogue/1', 'source': str(GRANTED_CENSUS.relative_to(ROOT)), 'source_sha256': GRANTED_CENSUS_SHA256, 'files': len(files),
              'entries': len(entries), 'problems': problems, 'already_in_brand_catalogue': sum(e['already_in_brand_catalogue'] for e in entries),
              'by_class': dict(collections.Counter(e['family_class'] or 'unclassified' for e in entries)), 'by_licence': dict(collections.Counter(e['licence'] for e in entries)),
              'arabic_complete_files': sum(1 for e in entries if e['complete_basic_arabic']), 'arabic_emitter_capable': sum(1 for e in entries if e['arabic']),
              'latin': sum(1 for e in entries if e['latin']), 'seconds': round(time.time() - started, 1), 'items': sorted(entries, key=lambda e: e['catalogue_stem'])}
    CATALOGUE_RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n')
    return {k: v for k, v in record.items() if k != 'items'}


def catalogue_entries() -> list[dict]:
    """The pool's catalogue entries (the record's items), read once per change of the record; [] without the record.
    [Day 8 §1a] a variable entry gains its static instances (``font_instances.instances_of``: path, wght, other axes),
    re-read when the instance directory changes — the Day 7 record itself is not rewritten."""
    from apps.ire import font_instances
    try:
        stat = CATALOGUE_RECORD.stat(); key = ('catalogue', stat.st_size, stat.st_mtime_ns)
    except OSError:
        return []
    with _lock:
        if _cache.get('catalogue_key') != key:
            _cache['catalogue_key'] = key; _cache['catalogue'] = json.loads(CATALOGUE_RECORD.read_text(encoding='utf-8')).get('items') or []
            _cache.pop('instances_key', None)
        ikey = font_instances.index_key()
        if _cache.get('instances_key') != ikey:
            for e in _cache['catalogue']:
                if e.get('variable'):
                    e['instances'] = font_instances.instances_of(e['catalogue_stem'], e['sha256'])
            _cache['instances_key'] = ikey
        return _cache['catalogue']


def chain(family: str) -> tuple:
    """The pool's faces of one lettering family, after the brand faces of lettering_faces.FAMILIES: (stem, weight or
    None for a variable face, italic), alphabetical; only faces the record did not find already in the brand catalogue."""
    out = []
    for e in catalogue_entries():
        if e.get('family_class') != family or e.get('already_in_brand_catalogue') or not e.get('latin'):
            continue
        weight = None if e.get('variable') and (e.get('axes') or {}).get('wght') else float(e.get('weight_class') or 400)
        out.append((e['catalogue_stem'], weight, bool(e.get('italic'))))
    return tuple(sorted(out))


def write_evidence() -> dict:
    """fonts-granted-evidence.json: per GRANTED file, its licence wording and the licence text embedded in the face (from the
    census), the census digest; the Day 7 grants' licence evidence."""
    rows = {}
    for face in pool('granted'):
        sha = face.get('source_sha256'); basis = face.get('pool_basis') or {}; ev = basis.get('evidence') or {}; names = face.get('names') or {}
        if sha and sha not in rows:
            rows[sha] = {'path': face.get('source_path'), 'family': names.get('family_typographic') or names.get('family_legacy'), 'licence': licence_of(ev.get('text')),
                         'evidence_type': ev.get('type'), 'evidence_text': str(ev.get('text') or '')[:400], 'census_reason': str(basis.get('reason') or '')[:160]}
    record = {'schema': 'day7_fonts_granted_evidence/1', 'source': str(GRANTED_CENSUS.relative_to(ROOT)), 'source_sha256': GRANTED_CENSUS_SHA256, 'files': len(rows),
              'rule': 'D-D7-1: the GRANTED pool is granted for concepts and final artwork; the wording here is each face\'s own embedded licence text', 'items': rows}
    EVIDENCE.write_text(json.dumps(record, ensure_ascii=False, indent=1, sort_keys=True) + '\n'); return {k: v for k, v in record.items() if k != 'items'}


def day7_grants() -> tuple:
    """The owner's D-D7-1 grant as the owner-grant channel reads it: one grant per licence wording, naming every GRANTED
    file's digest the earlier grants do not name; the licence evidence is the census file, re-hashed on every application."""
    from apps.ire.container_font_owner_grant import SCHEMA, OWNER_GRANTS_BEFORE_DAY7
    named = {s for g in OWNER_GRANTS_BEFORE_DAY7 for s in g['face_sha256s']}
    by_licence = {}
    for e in catalogue_entries():
        if e['sha256'] not in named:
            by_licence.setdefault(e['licence'], []).append(e['sha256'])
    return tuple({'schema_version': SCHEMA, 'granted_by': 'BBrose (D-D7-1, the Day 7 prompt)', 'granted_at': '2026-10-19', 'licence_id': licence,
                  'licence_evidence_path': str(EVIDENCE), 'licence_evidence_sha256': GRANTED_EVIDENCE_SHA256, 'face_sha256s': tuple(sorted(shas))}
                 for licence, shas in sorted(by_licence.items()))
