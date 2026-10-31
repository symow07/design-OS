"""Day 6 all-file census. Read materials; write evidence outside the corpus.

No database, worker, provider or engine grant changes. Historical inventory
metadata is retained; excluded/junk files are counted, never silently omitted.
"""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, copy, datetime, hashlib, json, os, sys, unicodedata

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'bbrose_design_os'
sys.path.insert(0, str(APP))
AUDIT = ROOT / 'var/design_intelligence/audits/dip0/inventory'
OUT = ROOT / 'docs/audit/day-6/library'
FONTS = {'.ttf', '.otf', '.ttc', '.otc', '.woff', '.woff2', '.fon', '.pfb', '.pfm', '.dfont', '.eot'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)


def classify(relative):
    p = Path(relative); ext = p.suffix.lower(); words = str(p).lower()
    if ext in FONTS:
        return 'fonts', 'unclassified'
    if ext in {'.psd', '.psb'} and 'mockup' in words:
        return 'mockups', 'unclassified'
    if any(x in p.name.lower() for x in ('licence', 'license', 'ofl.', 'copyright', 'readme')) and ext in {'.txt', '.md', '.pdf', '.html'}:
        return 'licence-evidence', 'unclassified'
    rules = [('dielines', ('dieline', 'cutline', '刀模')), ('patterns', ('pattern', 'seamless', '花纹', '底纹')),
             ('backgrounds', ('background', 'texture', '背景')), ('ornaments', ('ornament', 'border', '装饰'))]
    if ext in {'.ai', '.eps', '.svg', '.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff'}:
        for kind, terms in rules:
            if any(t in words for t in terms):
                return kind, 'unclassified'
        if ext in {'.ai', '.eps', '.svg'} and any(t in words for t in ('bottle', 'cosmetic', 'packaging', 'lipstick', 'serum', 'tube-', 'عبوات')):
            return 'product-vectors', 'unclassified'
        if ext in {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}:
            # Bitmap format alone does not prove it is a photograph.
            return 'unknown', 'unclassified'
    return 'unknown', 'unclassified'


def physical_files(root):
    files, links = [], []
    for parent, dirs, names in os.walk(root, followlinks=False):
        dirs.sort(); names.sort()
        for name in list(dirs):
            path = Path(parent) / name
            if path.is_symlink():
                links.append({'path': str(path.relative_to(ROOT)), 'target': os.readlink(path), 'kind': 'directory'})
                dirs.remove(name)
            elif path == root / '_migration':
                dirs.remove(name)
        for name in names:
            path = Path(parent) / name
            if path == root / '_tree.md':
                continue
            if path.is_symlink():
                links.append({'path': str(path.relative_to(ROOT)), 'target': os.readlink(path), 'kind': 'file'})
            elif path.is_file():
                files.append(path)
    return files, links


def inventory():
    from tools.dip0 import config
    old_path = AUDIT / 'inventory.jsonl'
    old = {x['relative_path']: x for x in map(json.loads, old_path.read_text().splitlines())}
    cache_path = AUDIT / 'hash_cache.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    dated = AUDIT / 'inventory-2026-10-19.jsonl'
    if dated.exists():
        for row in map(json.loads, dated.read_text().splitlines()):
            cache[f"{row['relative_path']}|{row['size_bytes']}|{row['mtime_ns']}"] = row['sha256']
    files, links = physical_files(ROOT / 'materials')
    rows = []; reused = hashed = 0
    for index, path in enumerate(files):
        relative = str(path.relative_to(ROOT)); stat = path.stat(); prior = old.get(relative, {})
        key = f'{relative}|{stat.st_size}|{stat.st_mtime_ns}'
        if prior.get('size_bytes') == stat.st_size and prior.get('mtime_ns') == stat.st_mtime_ns and prior.get('sha256'):
            digest = prior['sha256']; reused += 1
        elif key in cache:
            digest = cache[key]; reused += 1
        else:
            digest = sha(path); hashed += 1
        now = path.stat()
        if (now.st_size, now.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise RuntimeError('File changed during census: ' + relative)
        kind, subject = classify(relative)
        row = copy.deepcopy(prior)
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        def envelope(value):
            return {'value': value, 'source': 'day6_unverified', 'evidence': [], 'confidence': 0.,
                    'extracted_at': stamp, 'parser': 'rescue_materials_census/1'}
        defaults = {'signature_kind': envelope('unknown'), 'mime_detected': envelope('application/octet-stream'),
                    'category': envelope('UNKNOWN'), 'ownership_status': envelope('UNKNOWN'),
                    'license_evidence': [], 'license_status': envelope('UNVERIFIED'), 'license_evidence_strength': 'none',
                    'posture': {'knowledge_class': False, 'excluded_from_retrieval_by_rule': config.is_excluded_path(relative),
                                'retrieval_allowed': False, 'automatic_use_allowed': False, 'reason': 'New census row; no rights or retrieval grant inferred'},
                    'review_required': True, 'review_reasons': ['day6_unverified_new_asset'],
                    'human_confirmed': {'category': None, 'license_status': None, 'ownership_status': None, 'reviewed_by': None, 'reviewed_at': None, 'notes': ''},
                    'duplicate_group': None}
        for name, value in defaults.items():
            row.setdefault(name, value)
        row.update(relative_path=relative, filename=path.name, extension=path.suffix.lower(), size_bytes=stat.st_size,
                   mtime_ns=stat.st_mtime_ns, mtime_iso=datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat(),
                   sha256=digest, root_folder=path.relative_to(ROOT / 'materials').parts[0], kind_guess=kind,
                   subject_guess=subject, kind_authority='extension/path heuristic; not visual content or rights',
                   preview_candidate=path.suffix.lower() in {'.ai', '.eps', '.pdf', '.psd', '.psb', '.jpg', '.jpeg', '.png', '.tif', '.tiff'},
                   source_path=relative, parser_support=prior.get('parser_support', {'status': config.parser_support(path.suffix.lower()), 'parser': None}),
                   warnings=prior.get('warnings', []), hash_source='old stat-bound hash' if key in cache or digest == prior.get('sha256') else 'newly measured',
                   legacy_excluded=config.is_excluded_path(relative), hidden_metadata=any(p.startswith('.') for p in path.relative_to(ROOT / 'materials').parts))
        rows.append(row)
        if index % 500 == 0:
            print(json.dumps({'stage': 'inventory', 'done': index, 'total': len(files), 'reused': reused, 'hashed': hashed}), flush=True)
    target = AUDIT / 'inventory-2026-10-19.jsonl'
    target.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
    groups = defaultdict(list)
    for row in rows:
        groups[row['sha256']].append(row['relative_path'])
    duplicates = {h: paths for h, paths in groups.items() if len(paths) > 1}
    save(OUT / 'duplicate-groups.json', duplicates)
    summary = {'schema': 'day6_inventory/1', 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'file_count': len(rows), 'source_bytes': sum(x['size_bytes'] for x in rows), 'expected_owner_count': 14310,
               'difference_from_owner_estimate': len(rows) - 14310, 'count_basis': 'All regular files including hidden metadata and legacy exclusions; symlinks listed separately. Generated _tree.md and _migration excluded.',
               'symlinks': links, 'hashes_reused': reused, 'hashes_new': hashed,
               'by_root': dict(Counter(x['root_folder'] for x in rows)), 'by_extension': dict(Counter(x['extension'] for x in rows)),
               'by_kind': dict(Counter(x['kind_guess'] for x in rows)), 'duplicate_groups': len(duplicates),
               'extra_duplicate_copies': sum(len(v) - 1 for v in duplicates.values()),
               'legacy_inventory_rows': len(old), 'legacy_materials_rows': sum(k.startswith('materials/') for k in old),
               'inventory_sha256': sha(target), 'inventory_path': str(target.relative_to(ROOT)), 'materials_modified': False}
    save(OUT / 'inventory-summary.json', summary)
    print(json.dumps({'stage': 'inventory_complete', 'files': len(rows), 'hashed': hashed, 'reused': reused}), flush=True)
    return rows


def font_pool(face, known):
    raw = face['fstype']['raw']; names = face['names']
    text = '\n'.join(str(names.get(k) or '') for k in ['license_description', 'license_info_url', 'description'])
    # Full licence-identifying declarations, not copyright or fsType alone.
    lower = text.lower()
    licence = ('OFL-1.1' if 'sil open font license' in lower and ('1.1' in lower or 'openfontlicense.org' in lower) else
               'Apache-2.0' if 'apache' in lower and ('version 2.0' in lower or 'licenses/license-2.0' in lower) else
               'UFL-1.0' if 'ubuntu font licence' in lower and '1.0' in lower else None)
    evidence = {'type': 'embedded name table', 'text': text} if licence else None
    if face['source_sha256'] in known:
        evidence = known[face['source_sha256']]; licence = evidence['licence_id']
    restricted = raw is not None and bool(raw & (0x0002 | 0x0200))
    commercial = any(s in lower for s in ('license must be purchased', 'licence must be purchased', 'personal use only', 'not for commercial use'))
    if restricted or commercial:
        return 'BLOCKED', {'reason': 'Restricted/bitmap-only embedding or explicit noncommercial/purchase condition', 'evidence': evidence, 'licence': licence}
    valid_embedding = raw is not None and (raw & ~0x030e) == 0 and (raw & 0x000e) in (0, 4, 8)
    if licence and valid_embedding:
        return 'GRANTED', {'reason': 'Recorded free licence plus embeddable fsType; census projection only, engine grants unchanged', 'evidence': evidence, 'licence': licence}
    return 'UNVERIFIED', {'reason': 'No sufficient licence evidence or embedding metadata; no production grant', 'evidence': evidence, 'licence': licence}


def fonts(rows):
    from fontTools.ttLib import TTFont, TTCollection
    from tools.dip0c.fontinfo import audit_file
    from apps.ire.container_font_owner_grant import OWNER_GRANTS
    known = {}
    for grant in OWNER_GRANTS:
        p = Path(grant['licence_evidence_path'])
        if p.exists() and sha(p) == grant['licence_evidence_sha256']:
            for digest in grant['face_sha256s']:
                known[digest] = {k: grant[k] for k in ['licence_id', 'licence_evidence_path', 'licence_evidence_sha256']}
    save(OUT / 'known-font-licence-hashes.json', known)
    files = [r for r in rows if r['extension'] in FONTS]; results = []; cache = {}
    for index, row in enumerate(files):
        path = ROOT / row['relative_path']; digest = row['sha256']
        if digest in cache:
            result = copy.deepcopy(cache[digest]); result['source_path'] = row['relative_path']
            for face in result['faces']:
                face['source_path'] = row['relative_path']
        else:
            result = audit_file(path, sha256=digest)
            if result['faces']:
                collection = TTCollection(str(path), lazy=True) if row['extension'] in {'.ttc', '.otc'} else None
                opened = collection.fonts if collection else [TTFont(str(path), lazy=True)]
                try:
                    for face, font in zip(result['faces'], opened):
                        try:
                            chars = sorted((font.getBestCmap() or {}).keys())
                            coverage_error = None
                        except Exception as error:
                            chars = []
                            coverage_error = type(error).__name__ + ': ' + str(error)
                        face['coverage_error'] = coverage_error
                        latin = [c for c in chars if unicodedata.category(chr(c)).startswith('L') and 'LATIN' in unicodedata.name(chr(c), '')]
                        arabic = [c for c in chars if unicodedata.category(chr(c)).startswith('L') and 'ARABIC' in unicodedata.name(chr(c), '')]
                        basic = set(range(0x621, 0x63b)) | set(range(0x641, 0x64b))
                        base = sorted(set(chars) & basic)
                        face['actual_coverage'] = {'latin': latin, 'arabic': arabic, 'latin_count': len(latin), 'arabic_count': len(arabic),
                                                  'arabic_base_letters': base, 'arabic_base_letters_count': len(base), 'complete_basic_arabic': basic <= set(chars),
                                                  'definition': 'Unicode letter category and LATIN/ARABIC character name; FEFF excluded. Cmap coverage does not prove shaping.'}
                        face['names']['description'] = font['name'].getDebugName(10) if 'name' in font else None
                        face['name_fields_raw'] = {str(n): font['name'].getDebugName(n) if 'name' in font else None for n in [0,1,2,4,6,10,13,14]}
                        # Existing parser field names are preserved; canonical raw fields drive this new projection.
                        face['names']['license_description'] = face['name_fields_raw']['13']
                        face['names']['license_info_url'] = face['name_fields_raw']['14']
                        face['pool'], face['pool_basis'] = font_pool(face, known)
                        face['embedding_limitations'] = {'preview_print_only': face['fstype']['raw'] is not None and bool(face['fstype']['raw'] & 4),
                                                        'no_subsetting': face['fstype']['raw'] is not None and bool(face['fstype']['raw'] & 0x100)}
                        if coverage_error and face['pool'] != 'BLOCKED':
                            face['pool'] = 'UNVERIFIED'
                            face['pool_basis']['reason'] = 'Corrupt cmap; retained for repair, not granted'
                        face['family_name_sha256'] = hashlib.sha256(str(face['name_fields_raw']['1']).casefold().encode()).hexdigest()
                finally:
                    for font in opened:
                        font.close()
                    if collection:
                        collection.close()
            if not result['faces']:
                result['pool'] = 'UNVERIFIED'
            cache[digest] = copy.deepcopy(result)
        results.append(result)
        if index % 250 == 0:
            print(json.dumps({'stage': 'font_census', 'done': index, 'total': len(files)}), flush=True)
    faces = [face for file in results for face in file['faces']]
    report = {'schema': 'day6_fonts/1', 'file_count': len(files), 'unique_contents': len(cache), 'face_instances': len(faces),
              'unique_faces': len({x['face_id'] for x in faces}), 'files_without_parsed_faces': sum(not x['faces'] for x in results),
              'pool_face_counts': dict(Counter(x['pool'] for x in faces)), 'arabic_face_counts_by_pool': dict(Counter(x['pool'] for x in faces if x['actual_coverage']['arabic_base_letters_count'])),
              'complete_basic_arabic_by_pool': dict(Counter(x['pool'] for x in faces if x['actual_coverage']['complete_basic_arabic'])),
              'engine_grants_changed': False, 'files': results}
    save(OUT / 'fonts-census.json', report)
    for pool in ['GRANTED', 'UNVERIFIED', 'BLOCKED']:
        save(OUT / ('fonts-' + pool.lower() + '.json'), {'pool': pool, 'engine_grants_changed': False, 'faces': [x for x in faces if x['pool'] == pool],
                                                     'unparsed_files': [x for x in results if not x['faces']] if pool == 'UNVERIFIED' else []})
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--stage', choices=['inventory', 'fonts', 'inventory-fonts'], default='inventory-fonts')
    args = parser.parse_args(); os.nice(10)
    if args.stage in {'inventory', 'inventory-fonts'}:
        rows = inventory()
    else:
        rows = [json.loads(line) for line in (AUDIT / 'inventory-2026-10-19.jsonl').read_text().splitlines()]
    if args.stage in {'fonts', 'inventory-fonts'}:
        fonts(rows)
