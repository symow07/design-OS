"""House designs in one place — Day 8 §1c, the move half (the owner's Day 8 prompt, in the coordinator's narrowed scope).

The house's own production artwork — the 91 files the Day 6 manifest took from "materials/historical AI production
designs", listed in docs/audit/day-8/house-dna/house-designs-list.json — moves into materials/house-designs/ by the route
Day 6 ruled for any move under materials/ (docs/audit/day-6/README.md; the tree note docs/audit/day-6/library/tree.md):

* a manifest written BEFORE any rename (sha256, from, to, bytes, rule), never regenerated over a started move — a re-run
  recomputes the plan from records alone and refuses when it differs from the manifest on disk;
* rename only: exclusive (Darwin renamex_np RENAME_EXCL), same filesystem, never a copy, an overwrite or an unlink; a
  user-immutable flag is cleared for the one rename and restored at once (Day 6 attempt 1 stopped on one);
* the sha256 measured at the source before each rename and at the destination after it, an append-only journal written
  as it goes (``moved_at`` lives there: the manifest exists before anything moved), every name checked byte-exactly by
  readdir and never by exists() — the volume is case-insensitive APFS (Day 6 attempt 2);
* after the moves: the count and the whole path set under materials/ equal the walk taken before, less the sources, plus
  the destinations; every moved file is re-hashed; the destination holds exactly the plan. Any count, hash or path
  mismatch — or a repoint that fails — reverses every moved pair automatically and proves the tree as it was.

The original path stays the identity: apps.ire.materials_paths reads this manifest after the Day 6 one, so the original
path, the Day 6 path and the new path resolve to one file, and rights, tiers, grants, captions and placement (keyed on the
identity) are untouched. The consumers that keep a CURRENT path are repointed inside the same transaction: the DIP-0A
inventory (relative_path; path_history gains the Day 6 path) and the Day 7 index (the paths list per sha256). The house
index (docs/brand/house_references/index.json) names no materials/ path: it is measured, never rewritten.

Further production files are caught by NAME — a product code or a Chinese packaging term in the file's own name or its
original name — and listed in the manifest with the rule that caught them. A doubtful match, a code-like name no rule
catches, and a file whose only evidence is its caption are held and named in the plan record, never moved.

Run from bbrose_design_os/: ``venv/bin/python -m apps.pipeline.services.materials_house_designs prepare|apply|proof``.
"""
from pathlib import Path
from collections import Counter
import ctypes, datetime, fcntl, hashlib, json, os, re, stat, sys, unicodedata

ROOT = Path(__file__).resolve().parents[4]
DESTINATION = 'materials/house-designs'
LIBRARY = 'docs/audit/day-8/library'
MANIFEST = LIBRARY + '/house-designs-manifest.jsonl'
JOURNAL = LIBRARY + '/house-designs-journal.jsonl'
PLAN = LIBRARY + '/house-designs-plan.json'
MOVE = LIBRARY + '/house-designs-move.json'
PROOF = LIBRARY + '/house-designs-proof.json'
HOUSE_LIST = 'docs/audit/day-8/house-dna/house-designs-list.json'
DAY6_MANIFEST = 'docs/audit/day-6/library/manifest-2026-10-19.jsonl'
DAY7_INDEX = 'docs/audit/day-7/library/materials-index.json'
INVENTORY = 'var/design_intelligence/audits/dip0/inventory/inventory.jsonl'
HOUSE_INDEX = 'docs/brand/house_references/index.json'
HOUSE_FILES = 'docs/brand/house_references/files'
#: git-ignored working files: the lock, file metadata, the walk before the move, the repointed files' original bytes
RUNTIME = 'docs/audit/rescue_runtime/day8/house-designs'
#: Day 6's own evidence inside the corpus, outside conservation (the tree note)
EXCLUDED = ('materials/_migration', 'materials/_tree.md')
LIST_RULE = 'house-designs-list'
RENAME_EXCL = 4

#: The owner's name rules (Day 8 §1c): a product code or a Chinese packaging term in a file's name. Case as written;
#: a code never starts inside a word ("SERIES2024" is not ES2024).
CODE_RULES = (
    ('product code ES', re.compile(r'(?<![A-Za-z])ES\d{3,4}(?!\d)')),
    ('product code LP', re.compile(r'(?<![A-Za-z])LP\d+')),
    ('product code LG', re.compile(r'(?<![A-Za-z])LG\d+')),
    ('product code LH', re.compile(r'(?<![A-Za-z])LH\d+')),
    ('product code LM', re.compile(r'(?<![A-Za-z])LM\d+')),
    ('product code SF', re.compile(r'(?<![A-Za-z])SF\d+')),
    ('product code MA', re.compile(r'(?<![A-Za-z])MA\d+')),
    ('product code YB', re.compile(r'(?<![A-Za-z])YB-\d+')),
    ('product word STAND', re.compile(r'(?<![A-Za-z])STAND(?![A-Za-z])')),
)
PACKAGING_TERMS = ('刀线', '刀模', '展盒', '白卡', '包装盒', '彩盒', '吸塑')
#: doubtful: a one- or two-digit code (or the bare word STAND) is all that matched
SHORT_CODE = re.compile(r'^(LP|LG|LH|LM|SF|MA)\d{1,2}$')
#: held, never moved: a code outside the listed prefixes, or a product word beside a number; stock ids and licences excluded
CODE_LIKE = re.compile(r'(?<![A-Za-z0-9])[A-Z]{2,4}[- ]?\d{3,4}(?!\d)')
PRODUCT_WORDS = re.compile(r'(?i)(powder|concealer|lip ?gloss|lip ?stick|mascara|primer|serum|blush|highlighter|'
                           r'foundation|eye ?shadow|palette)')
NUMBER = re.compile(r'(?<!\d)\d{2,4}(?!\d)')
STOCK_ID = re.compile(r'(?i)^(adobestock_\d+|\d+-[A-Z0-9]{6}-\d+)|eula|licen[cs]e')
#: held, never moved: the caption alone reads as house production artwork
HOUSE_NAME = re.compile(r'(?i)b\s*b\s*r[oò]se')
PRODUCTION_KINDS = ('product-render', 'dieline', 'layout')
SCANNED = ('.ai', '.pdf')


class MoveError(RuntimeError):
    pass


class PlanError(MoveError):
    pass


class PublicationError(MoveError):
    pass


class RollbackError(MoveError):
    def __init__(self, proof):
        super().__init__('Rollback did not restore the tree: reversed %d, conflicts %s, path set %s'
                         % (proof['reversed'], proof['conflicts'], proof['path_set_matches']))
        self.proof = proof


# --- small primitives -------------------------------------------------------------------------------------------------

def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _key(name):
    """Two names this volume may treat as one entry: NFC form, case folded (Day 6's spelling key)."""
    return unicodedata.normalize('NFC', name).casefold()


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_bytes(path, payload):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.day8.tmp')
    with temporary.open('wb') as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path); _fsync_dir(path.parent)


def _save(path, value):
    _atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=1) + '\n').encode())


def _journal(path, row):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n'); stream.flush(); os.fsync(stream.fileno())


def _spelled(root, relative):
    """True when the entry is present under exactly this spelling — readdir, never exists() (case-insensitive volume)."""
    parent, name = relative.rsplit('/', 1); path = Path(root) / parent
    return path.is_dir() and name in os.listdir(path)


def _rename_exclusive(old, new):
    """Darwin renamex_np(RENAME_EXCL), Day 6's primitive: never overwrite, copy or unlink."""
    if sys.platform != 'darwin':
        raise MoveError('The exclusive rename is validated only on Darwin')
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renamex_np; fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    if fn(os.fsencode(old), os.fsencode(new), RENAME_EXCL):
        err = ctypes.get_errno(); raise OSError(err, os.strerror(err), str(new))
    _fsync_dir(old.parent)
    if old.parent != new.parent:
        _fsync_dir(new.parent)


def _rename_preserving_flags(old, new, flags):
    """Clear the user-immutable bit on this one file for the rename and restore every flag at once; system flags,
    permissions, owners, extended attributes and bytes are never altered (Day 6, attempt 1)."""
    original = old.stat().st_flags
    if original & stat.UF_IMMUTABLE:
        os.chflags(old, original & ~stat.UF_IMMUTABLE)
    try:
        _rename_exclusive(old, new)
    finally:
        current = new if new.exists() and not old.exists() else old
        if current.exists() and current.stat().st_flags != flags:
            os.chflags(current, flags)


def _walk(root):
    """Every regular file under materials/ (Day 6's evidence excluded), spelled as readdir returns it; symlinks named."""
    root = Path(root); files, links = set(), []
    skip = {root / p for p in EXCLUDED}
    for parent, dirs, names in os.walk(root / 'materials', followlinks=False):
        here = Path(parent)
        dirs[:] = [d for d in dirs if here / d not in skip]
        for name in names:
            path = here / name
            if path in skip:
                continue
            if path.is_symlink():
                links.append(path.relative_to(root).as_posix())
            elif path.is_file():
                files.add(path.relative_to(root).as_posix())
    return files, links


# --- the plan: from records alone, so a re-run recomputes the manifest exactly ---------------------------------------

def name_rules(name):
    """[(rule, matched text)] — the owner's name rules on one file name (NFC)."""
    text = unicodedata.normalize('NFC', name); found = []
    for rule, pattern in CODE_RULES:
        found.extend((rule, m.group(0)) for m in pattern.finditer(text))
    found.extend(('packaging term', t) for t in PACKAGING_TERMS if t in text)
    return found


def doubtful(found):
    """A name-rule match is doubtful when every hit is a one- or two-digit code or the bare word STAND."""
    return all(SHORT_CODE.match(text) or rule == 'product word STAND' for rule, text in found)


def code_like(name):
    """Held, never moved: a code outside the listed prefixes, or a product word beside a number — stock ids excluded."""
    text = unicodedata.normalize('NFC', name)
    if STOCK_ID.search(text):
        return False
    return bool(CODE_LIKE.search(text) or (PRODUCT_WORDS.search(text) and NUMBER.search(text)))


def _words(found):
    return ['%s: %s' % f for f in found]


def _move_row(m, rule, found):
    return {'sha256': m['sha256'], 'from': m['new_path'], 'to': None, 'bytes': m['size_bytes'], 'rule': rule,
            'name_rules': _words(found), 'original_path': m['old_path'], 'name': m['display_name']}


def _held_row(m, rule, reason):
    return {'sha256': m['sha256'], 'path': m['new_path'], 'original_path': m['old_path'], 'name': m['display_name'],
            'bytes': m['size_bytes'], 'rule': rule, 'reason': reason}


def plan(root=ROOT):
    """The move from records only — the house list, the Day 6 manifest and the Day 7 index — so it reads the same
    before, during and after the move. Returns {'rows', 'held', 'scan', 'list_caught_by_name_rules'}."""
    root = Path(root)
    day6 = {r['new_path']: r for r in _jsonl(root / DAY6_MANIFEST)}
    if any(p.startswith(DESTINATION + '/') or r['old_path'].startswith(DESTINATION + '/') for p, r in day6.items()):
        raise PlanError('A Day 6 identity already lies under ' + DESTINATION)
    rows, held, planned, not_caught = [], [], set(), []
    for item in json.loads((root / HOUSE_LIST).read_text(encoding='utf-8')):
        m = day6.get(item['manifest']['new_path'])
        if m is None or m != item['manifest'] or m['sha256'] != item['sha256']:
            raise PlanError('The house list disagrees with the Day 6 manifest: ' + item['name'])
        found = name_rules(m['display_name'])
        if not found:
            not_caught.append(m['display_name'])
        rows.append(_move_row(m, LIST_RULE, found)); planned.add(m['new_path'])
    scan = Counter()
    for path, m in sorted(day6.items()):
        if Path(path).suffix.lower() not in SCANNED:
            continue
        scan['ai_pdf_in_day6_manifest'] += 1
        if path in planned:
            continue
        scan['ai_pdf_outside_the_list'] += 1
        found = list(dict.fromkeys(name_rules(Path(path).name) + name_rules(m['display_name'])))
        if found and path.startswith('materials/_duplicates/'):
            scan['caught_by_name'] += 1
            held.append(_held_row(m, 'name: ' + '; '.join(_words(found)),
                                  'an exact-hash copy in Day 6 _duplicates/; the dedupe half decides'))
        elif found and doubtful(found):
            scan['caught_by_name'] += 1
            held.append(_held_row(m, 'name: ' + '; '.join(_words(found)),
                                  'doubtful: only a one- or two-digit code or the bare word STAND'))
        elif found:
            scan['caught_by_name'] += 1
            rows.append(_move_row(m, 'name: ' + '; '.join(_words(found)), found)); planned.add(path)
        elif code_like(m['display_name']):
            held.append(_held_row(m, 'code-like name',
                                  'a code outside the listed prefixes or a product word beside a number; no rule catches it'))
    held_paths = {h['path'] for h in held}; planned_shas = {r['sha256'] for r in rows}
    for item in json.loads((root / DAY7_INDEX).read_text(encoding='utf-8'))['items']:
        if str(item.get('extension')).lower() not in SCANNED or item['sha256'] in planned_shas:
            continue
        scan['ai_pdf_index_rows_outside_the_plan'] += 1
        seen = ' '.join(str(t) for t in item.get('text_seen') or []) + ' ' + str(item.get('subject'))
        codes = name_rules(seen) if item.get('kind') in PRODUCTION_KINDS else []
        house = HOUSE_NAME.search(seen)
        if not (codes or house):
            continue
        scan['caught_by_caption'] += 1
        path = sorted(item['paths'])[0]
        if path in held_paths or path in planned or path not in day6:
            continue
        rule = 'caption only: ' + ('; '.join(_words(codes)) if codes else 'the caption names the house (%s)' % house.group(0))
        held.append(_held_row(day6[path], rule, 'the caption alone reads as house production artwork; the name carries no rule'))
    taken = set()
    for row in sorted(rows, key=lambda r: (_key(r['name']), r['sha256'])):
        name = row['name']
        if '/' in name or name in ('', '.', '..'):
            raise PlanError('Not a file name: %r' % name)
        if _key(name) in taken:
            name = Path(name).stem + '-' + row['sha256'][:16] + Path(name).suffix
        if _key(name) in taken:
            raise PlanError('Destination collision after the hash suffix: ' + name)
        taken.add(_key(name)); row['to'] = DESTINATION + '/' + name
    rows.sort(key=lambda r: r['to'])
    held.sort(key=lambda h: h['path'])
    listed = sum(1 for r in rows if r['rule'] == LIST_RULE)
    return {'rows': rows, 'held': held, 'scan': dict(scan),
            'list_caught_by_name_rules': {'caught': listed - len(not_caught), 'of': listed, 'not_caught': sorted(not_caught),
                                          'note': 'the 91 are selected by the list, not by the name rules'}}


def _rules_record():
    return {'codes': {rule: pattern.pattern for rule, pattern in CODE_RULES}, 'packaging_terms': list(PACKAGING_TERMS),
            'doubtful': SHORT_CODE.pattern + ' (or the bare word STAND) is all that matched',
            'held_code_like': {'code': CODE_LIKE.pattern, 'product_words': PRODUCT_WORDS.pattern, 'number': NUMBER.pattern,
                               'excluded': STOCK_ID.pattern},
            'held_caption_only': {'kinds': list(PRODUCTION_KINDS), 'code_in_text_seen': 'the code rules above',
                                  'house_name': HOUSE_NAME.pattern},
            'scanned_extensions': list(SCANNED)}


def prepare(root=ROOT):
    """Write the manifest — before any rename — and the plan record (rules, scan counts, held list). Every source is
    re-hashed against the list first. A manifest already on disk is never rewritten: the recomputed plan must equal it."""
    root = Path(root); planned = plan(root); manifest = root / MANIFEST
    if manifest.exists():
        if _jsonl(manifest) != planned['rows']:
            raise PlanError('The manifest on disk differs from the plan; a started move is never re-planned')
        state = 'EXISTS_EQUAL'
    else:
        for row in planned['rows']:
            source = root / row['from']
            if not _spelled(root, row['from']) or source.is_symlink() or not source.is_file():
                raise PlanError('Source missing before the move: ' + row['from'])
            if source.stat().st_size != row['bytes'] or _sha(source) != row['sha256']:
                raise PlanError('Source bytes differ from the list: ' + row['from'])
        _atomic_bytes(manifest, ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in planned['rows']).encode())
        state = 'WRITTEN'
    record = {'schema': 'day8_house_designs_plan/1', 'manifest': MANIFEST, 'manifest_sha256': _sha(manifest),
              'manifest_state': state, 'destination': DESTINATION, 'rows': len(planned['rows']),
              'bytes': sum(r['bytes'] for r in planned['rows']),
              'moved_by_rule': dict(Counter(r['rule'] if r['rule'] == LIST_RULE else 'name rules' for r in planned['rows'])),
              'list_caught_by_name_rules': planned['list_caught_by_name_rules'], 'scan': planned['scan'],
              'held': planned['held'], 'held_by_rule': dict(Counter(h['rule'].split(':')[0] for h in planned['held'])),
              'rules': _rules_record(),
              'sources_rehashed_before_the_manifest': state == 'WRITTEN',
              'method': 'The 91 rows are the house list (Day 6 rows whose original_directory is "materials/historical AI '
                        'production designs"); further .ai/.pdf files are caught by name (their own name or their Day 6 '
                        'original name); a doubtful match, a code-like name and a caption-only candidate are held. '
                        'Destination: the original file name; a name this volume would identify with another gets '
                        '-<sha16> before the extension.'}
    if state == 'WRITTEN' or not (root / PLAN).exists():
        record['planned_at'] = _now(); _save(root / PLAN, record)
    return record


# --- the move ------------------------------------------------------------------------------------------------------------

def _classify(root, rows):
    pending, done = [], []
    for row in rows:
        at_from, at_to = _spelled(root, row['from']), _spelled(root, row['to'])
        if at_from and at_to:
            raise MoveError('Both locations hold a file (never overwritten): ' + row['to'])
        if not (at_from or at_to):
            raise MoveError('The file is at neither location: ' + row['from'])
        if at_to and _sha(root / row['to']) != row['sha256']:
            raise MoveError('A moved file does not carry the manifest bytes: ' + row['to'])
        (done if at_to else pending).append(row)
    return pending, done


def _walk_before(root, runtime, done):
    """The tree before the first rename. A fresh start measures it now (and keeps it only just before its first
    rename, so a refused run leaves nothing to reuse); a resumed run reads the walk its first run kept, or rebuilds it
    from the tree now with the moved rows put back where they were."""
    path = runtime / 'walk-before.json'
    if done and path.exists():
        return set(json.loads(path.read_text(encoding='utf-8'))['paths'])
    files, links = _walk(root)
    if links:
        raise MoveError('Symlinks under materials/: %s' % links[:5])
    return (files - {r['to'] for r in done}) | {r['from'] for r in done}


def _keep_walk(runtime, files, done):
    _save(runtime / 'walk-before.json', {'count': len(files), 'measured_at': _now(), 'rebuilt_for_moved_rows': len(done),
                                         'paths': sorted(files)})


def _check_destination(root):
    """Refused when materials/ holds another spelling of the destination, or the destination is not a folder."""
    parent, name = DESTINATION.rsplit('/', 1)
    for entry in os.listdir(root / parent):
        if _key(entry) == _key(name) and entry != name:
            raise MoveError('materials/ holds %r, which this volume identifies with %r' % (entry, name))
    path = root / DESTINATION
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise MoveError('The destination is not a folder: ' + DESTINATION)


def _make_destination(root, runtime):
    """Made when absent and recorded, so a rollback removes it again only if this move made it and it is empty."""
    path = root / DESTINATION; marker = runtime / 'destination-made.json'
    if not path.exists():
        _save(marker, {'path': DESTINATION, 'made_at': _now()})
        path.mkdir(); _fsync_dir(path.parent)
    return marker.exists()


def _metadata(root, runtime, pending, done):
    """Flags, mode and owners of every source, kept before the first rename. A row an earlier run moved without
    keeping its record (that run stopped first) is read at its destination and counted, never assumed changed."""
    path = runtime / 'file-metadata.json'
    metadata = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    device = (root / 'materials').stat().st_dev
    for row in done:
        if row['from'] not in metadata:
            st = (root / row['to']).stat()
            metadata[row['from']] = {'flags': st.st_flags, 'mode': stat.S_IMODE(st.st_mode), 'uid': st.st_uid,
                                     'gid': st.st_gid, 'read_at_destination': True}
    for row in pending:
        source = root / row['from']
        if source.is_symlink() or not source.is_file():
            raise MoveError('Source unavailable or a symlink: ' + row['from'])
        st = source.stat()
        if st.st_size != row['bytes']:
            raise MoveError('Source size differs from the manifest: ' + row['from'])
        if st.st_dev != device:
            raise MoveError('Cross-filesystem move refused: ' + row['from'])
        metadata[row['from']] = {'flags': st.st_flags, 'mode': stat.S_IMODE(st.st_mode), 'uid': st.st_uid, 'gid': st.st_gid}
    _save(path, metadata)
    return metadata


def _metadata_preserved(root, rows, metadata):
    for row in rows:
        st = (root / row['to']).stat()
        kept = {k: v for k, v in metadata[row['from']].items() if k != 'read_at_destination'} if row['from'] in metadata else None
        if kept != {'flags': st.st_flags, 'mode': stat.S_IMODE(st.st_mode), 'uid': st.st_uid, 'gid': st.st_gid}:
            return False
    return True


def _move(root, journal, row, flags, after_rename):
    source, target = root / row['from'], root / row['to']
    if _sha(source) != row['sha256']:
        raise MoveError('Source bytes differ from the manifest: ' + row['from'])
    _journal(journal, {'event': 'intent', 'from': row['from'], 'to': row['to'], 'sha256': row['sha256'], 'at': _now()})
    _rename_preserving_flags(source, target, flags)
    if after_rename is not None:
        after_rename(row)
    if not _spelled(root, row['to']) or _spelled(root, row['from']):
        raise MoveError('The rename did not take effect byte-exactly: ' + row['to'])
    measured = _sha(target)
    if measured != row['sha256']:
        raise MoveError('Moved bytes differ from the manifest: ' + row['to'])
    _journal(journal, {'event': 'done', 'from': row['from'], 'to': row['to'], 'sha256_after': measured,
                       'bytes': target.stat().st_size, 'moved_at': _now()})


def verify(root, rows, walk_before):
    """The tree after the move: the count and the path set exact (the walk before, less the sources, plus the
    destinations), every destination re-hashed, every source gone, the destination holding exactly the plan."""
    root = Path(root); files, links = _walk(root)
    finder = {p for p in files - walk_before if Path(p).name == '.DS_Store'}      # Finder's own, named, never conserved
    files -= finder
    expected = (walk_before - {r['from'] for r in rows}) | {r['to'] for r in rows}
    rehashed = [r for r in rows if (root / r['to']).is_file() and _sha(root / r['to']) == r['sha256']]
    listing = set(os.listdir(root / DESTINATION)) - {'.DS_Store'} if (root / DESTINATION).is_dir() else set()
    parents = sorted({str(Path(r['from']).parent) for r in rows})
    emptied = [p for p in parents if (root / p).is_dir() and not os.listdir(root / p)]
    result = {'expected_count': len(expected), 'actual_count': len(files), 'path_set_matches': files == expected,
              'missing': sorted(expected - files)[:20], 'unexpected': sorted(files - expected)[:20],
              'destinations_rehashed_exact': len(rehashed), 'every_destination_exact': len(rehashed) == len(rows),
              'every_source_gone': not any(_spelled(root, r['from']) for r in rows),
              'destination_holds_exactly_the_plan': listing == {Path(r['to']).name for r in rows},
              'symlinks': links, 'finder_files_ignored': sorted(finder),
              'source_folders_left_empty': len(emptied), 'source_folders': len(parents)}
    result['passed'] = (result['path_set_matches'] and result['expected_count'] == result['actual_count']
                        and result['every_destination_exact'] and result['every_source_gone']
                        and result['destination_holds_exactly_the_plan'] and not links)
    result['multiset_digest_of_moved'] = hashlib.sha256(json.dumps(sorted(r['sha256'] for r in rehashed)).encode()).hexdigest()
    return result


def rollback(root, rows, walk_before, made):
    """Reverse every moved pair, newest first. A destination whose bytes are not the manifest's is never moved on
    unverified bytes: it stays and is named. Then the tree as it was is proved (count and path set; every reversed
    file re-hashed)."""
    root = Path(root); journal = root / JOURNAL; conflicts, reversed_rows = [], []
    metadata_path = root / RUNTIME / 'file-metadata.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.exists() else {}
    for row in reversed(rows):
        if not _spelled(root, row['to']):
            continue
        if _spelled(root, row['from']) or _sha(root / row['to']) != row['sha256']:
            conflicts.append(row['to']); continue
        target = root / row['to']
        flags = metadata[row['from']]['flags'] if row['from'] in metadata else target.stat().st_flags
        _rename_preserving_flags(target, root / row['from'], flags)
        _journal(journal, {'event': 'rollback', 'from': row['from'], 'to': row['to'], 'at': _now()})
        reversed_rows.append(row)
    folder = root / DESTINATION
    if made and folder.is_dir() and not os.listdir(folder):
        os.rmdir(folder); _fsync_dir(folder.parent)
        (root / RUNTIME / 'destination-made.json').unlink()
        _journal(journal, {'event': 'rmdir', 'path': DESTINATION, 'at': _now()})
    files, links = _walk(root)
    files = {p for p in files if p in walk_before or Path(p).name != '.DS_Store'}
    proof = {'reversed': len(reversed_rows), 'conflicts': conflicts, 'expected_count': len(walk_before),
             'actual_count': len(files), 'path_set_matches': files == walk_before,
             'every_reversed_file_exact': all(_sha(root / r['from']) == r['sha256'] for r in reversed_rows),
             'destination_removed': not folder.exists(), 'symlinks': links}
    proof['passed'] = (not conflicts and proof['path_set_matches'] and proof['every_reversed_file_exact'] and not links)
    if not proof['passed']:
        raise RollbackError(proof)
    return proof


def apply(root=ROOT, *, publication=None, fail_after=None, after_rename=None):
    """Move every pending manifest row, verify the tree, repoint the consumers (``publication``), and roll every moved
    pair back on any mismatch. A completed re-run moves nothing: it verifies and republishes, and raises without
    reversing anything if either fails. ``fail_after`` and ``after_rename`` exist for the rollback proofs."""
    root = Path(root).resolve(); rows = _jsonl(root / MANIFEST)
    runtime = root / RUNTIME; runtime.mkdir(parents=True, exist_ok=True); journal = root / JOURNAL
    with (runtime / 'move.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        report = {'schema': 'day8_house_designs_move/1', 'state': 'PRECHECK', 'rows': len(rows), 'rollback_triggered': False,
                  'started_at': _now(), 'manifest_sha256': _sha(root / MANIFEST)}
        pending, done = _classify(root, rows)
        if pending:
            _check_destination(root)
        walk_before = _walk_before(root, runtime, done)
        report.update(walk_before_count=len(walk_before), previously_moved=len(done), pending=len(pending))
        if not pending:
            report['after'] = verify(root, rows, walk_before)
            if not report['after']['passed']:
                raise MoveError('The completed move no longer verifies: %s' % report['after'])
            if publication is not None:
                report['publication'] = publication(root, rows)
            report.update(state='VERIFIED_NOOP', moved=0, finished_at=_now())
            previous = json.loads((root / MOVE).read_text(encoding='utf-8')) if (root / MOVE).exists() else {}
            if previous.get('state') == 'VERIFIED':      # the move's own record stays; a re-check is added beside it
                previous['rechecks'] = list(previous.get('rechecks') or []) + [
                    {k: report[k] for k in ('state', 'finished_at', 'after', 'publication') if k in report}]
                _save(root / MOVE, previous)
            else:
                _save(root / MOVE, report)
            return report
        metadata = _metadata(root, runtime, pending, done)
        report['metadata_read_at_destination'] = sum(1 for v in metadata.values() if 'read_at_destination' in v)
        _keep_walk(runtime, walk_before, done)
        made = _make_destination(root, runtime)
        moved = 0
        try:
            report['state'] = 'MOVING'
            for row in pending:
                _move(root, journal, row, metadata[row['from']]['flags'], after_rename)
                moved += 1
                if fail_after is not None and moved == fail_after:
                    raise MoveError('Injected failure for the rollback proof')
            report['after'] = verify(root, rows, walk_before)
            if not report['after']['passed']:
                raise MoveError('Count, hash or path mismatch after the move')
            report['file_metadata_preserved'] = _metadata_preserved(root, rows, metadata)
            if not report['file_metadata_preserved']:
                raise MoveError('File flags or metadata changed')
            if publication is not None:
                report['publication'] = publication(root, rows)
            report.update(state='VERIFIED', moved=moved, finished_at=_now())
        except BaseException as exc:
            report.update(state='ROLLED_BACK', error=type(exc).__name__ + ': ' + str(exc), rollback_triggered=True,
                          moved=moved, finished_at=_now())
            try:
                report['rollback'] = rollback(root, rows, walk_before, made)
            except RollbackError as failure:
                report['state'] = 'ROLLBACK_INCOMPLETE'; report['rollback'] = failure.proof
                _save(root / MOVE, report)
                raise
            _save(root / MOVE, report)
            raise
        _save(root / MOVE, report)
        return report


# --- the repoint: consumers that keep a current path --------------------------------------------------------------------

def _repoint_inventory(root, moves, digest, backups, written):
    path = root / INVENTORY
    if not path.exists():
        return {'path': INVENTORY, 'state': 'ABSENT'}
    raw = path.read_bytes(); lines = raw.decode('utf-8').split('\n')
    if lines[-1] != '':
        raise PublicationError('The inventory does not end with a newline')
    rows = [json.loads(line) for line in lines[:-1]]
    if [json.dumps(r, ensure_ascii=False) for r in rows] != lines[:-1]:
        raise PublicationError('The inventory does not round-trip byte for byte')
    by_to = {m['to']: m for m in moves.values()}; found, changed = set(), 0
    for r in rows:
        rel = r['relative_path']
        if rel in moves:
            move = moves[rel]
        elif rel in by_to:
            move = by_to[rel]
        else:
            continue
        if r['sha256'] != move['sha256'] or move['to'] in found:
            raise PublicationError('The inventory row for %s is not the moved file' % rel)
        found.add(move['to'])
        if rel == move['from']:
            r['relative_path'] = move['to']; r['filename'] = Path(move['to']).name
            r['path_history'] = list(dict.fromkeys(list(r['path_history']) + [move['from']]))
            r['house_designs_manifest_sha256'] = digest
            changed += 1
    if len(found) != len(moves):
        raise PublicationError('%d moved files have no inventory row' % (len(moves) - len(found)))
    if changed:
        if not (backups / 'inventory-before.jsonl').exists():
            _atomic_bytes(backups / 'inventory-before.jsonl', raw)
        written.append((path, raw))
        _atomic_bytes(path, ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows).encode())
    return {'path': INVENTORY, 'rows': len(rows), 'repointed': changed, 'already_repointed': len(found) - changed,
            'sha256_before': hashlib.sha256(raw).hexdigest(), 'sha256_after': _sha(path),
            'kept': 'original_source_path, source_path, root_folder and the Day 6 manifest sha; path_history gains the Day 6 path'}


def _repoint_index(root, moves, backups, written):
    path = root / DAY7_INDEX
    if not path.exists():
        return {'path': DAY7_INDEX, 'state': 'ABSENT'}
    raw = path.read_bytes(); index = json.loads(raw)
    if (json.dumps(index, ensure_ascii=False, indent=0) + '\n').encode() != raw:
        raise PublicationError('The Day 7 index does not round-trip byte for byte')
    tos = {m['to']: m for m in moves.values()}; found, changed, single = set(), 0, 0
    for item in index['items']:
        hits = [p for p in item['paths'] if p in moves or p in tos]
        if not hits:
            continue
        for p in hits:
            move = moves[p] if p in moves else tos[p]
            if move['sha256'] != item['sha256'] or move['to'] in found:
                raise PublicationError('The Day 7 index row for %s is not the moved file' % p)
            found.add(move['to'])
        repointed = sorted(moves[p]['to'] if p in moves else p for p in item['paths'])
        if repointed != item['paths']:
            single += len(item['paths']) == 1
            item['paths'] = repointed; changed += 1
    if len(found) != len(moves):
        raise PublicationError('%d moved files have no Day 7 index row' % (len(moves) - len(found)))
    if changed:
        if not (backups / 'materials-index-before.json').exists():
            _atomic_bytes(backups / 'materials-index-before.json', raw)
        written.append((path, raw))
        _atomic_bytes(path, (json.dumps(index, ensure_ascii=False, indent=0) + '\n').encode())
    return {'path': DAY7_INDEX, 'rows': len(index['items']), 'repointed': changed, 'repointed_single_path_rows': single,
            'already_repointed': len(found) - changed, 'sha256_before': hashlib.sha256(raw).hexdigest(),
            'sha256_after': _sha(path), 'changed': 'the paths list of each moved file only'}


def _measure_house_index(root, moves):
    path = root / HOUSE_INDEX
    if not path.exists():
        return {'path': HOUSE_INDEX, 'state': 'ABSENT'}
    text = path.read_text(encoding='utf-8')
    named = [p for p in list(moves) + [m['to'] for m in moves.values()] if p in text]
    if named:
        raise PublicationError('The house index names a moved path and has no repoint here: ' + named[0])
    return {'path': HOUSE_INDEX, 'materials_paths_named': text.count('materials/'), 'rewritten': False,
            'sha256': _sha(path), 'files_read_from': HOUSE_FILES + '/<filename>'}


def publish(root, rows):
    """Repoint the consumers that keep a current path — the DIP-0A inventory, then the Day 7 index — and measure the
    house index. Each file is rewritten whole and atomically, only where a moved path appears, from bytes shown to
    round-trip exactly; any failure restores every file this call rewrote, then raises (and the move rolls back)."""
    root = Path(root); backups = root / RUNTIME / 'backups'
    moves = {r['from']: r for r in rows}; digest = _sha(root / MANIFEST); written = []
    try:
        return {'inventory': _repoint_inventory(root, moves, digest, backups, written),
                'day7_index': _repoint_index(root, moves, backups, written),
                'house_index': _measure_house_index(root, moves), 'at': _now()}
    except BaseException:
        for path, original in reversed(written):
            _atomic_bytes(path, original)
        raise


# --- the proof: every consumer, through its own call path (needs Django for retrieval and the Library page) -------------

def _resolution(mpaths, src, root, sha, target):
    try:
        return mpaths.resolve_material_file(src, repo_root=root, expected_sha=sha) == target
    except mpaths.MaterialPathError as exc:
        return 'refused: ' + str(exc)


def _brain_rows(brain_db, shas):
    """{sha: {'materials': [paths], 'captions': path}} from the brain's own tables; None when there is no brain here."""
    import sqlite3
    if brain_db is None or not Path(brain_db).exists():
        return None
    con = sqlite3.connect('file:%s?mode=ro' % brain_db, uri=True)
    try:
        out = {sha: {'materials': [], 'caption': None} for sha in shas}
        marks = ','.join('?' * len(shas))
        for path, sha in con.execute('SELECT relative_path, sha256 FROM materials WHERE sha256 IN (%s)' % marks, list(shas)):
            out[sha]['materials'].append(path)
        for sha, path in con.execute('SELECT sha256, relative_path FROM captions WHERE sha256 IN (%s)' % marks, list(shas)):
            out[sha]['caption'] = path
        return out
    finally:
        con.close()


def _db_rows_naming(paths):
    """How many database rows name any of these paths, in any text field whose name says path/src/source/file; a
    database that will not answer is recorded as unmeasured, never a crashed proof."""
    from django.apps import apps
    from django.db import DatabaseError
    from django.db.models import Q
    total, fields = 0, 0
    try:
        for model in apps.get_models():
            for field in model._meta.get_fields():
                kind = field.get_internal_type() if hasattr(field, 'get_internal_type') else None
                if kind in ('CharField', 'TextField') and any(k in field.name for k in ('path', 'src', 'source', 'file')):
                    query = Q()
                    for p in paths:
                        query |= Q(**{field.name + '__contains': p})
                    total += model.objects.filter(query).count(); fields += 1
    except DatabaseError as exc:
        return {'state': 'UNMEASURED', 'error': type(exc).__name__ + ': ' + str(exc)[:200]}
    return {'rows': total, 'text_fields_searched': fields}


def consumer_proof(root=ROOT, *, brain_db=None):
    """Every moved file through every consumer that resolves a materials/ path, and every house id."""
    from apps.ire import materials_paths as mpaths
    from apps.pipeline.services import materials_retrieval as mr
    from apps.dashboard import materials_library as ml
    root = Path(root).resolve(); rows = _jsonl(root / MANIFEST)
    plan_record = json.loads((root / PLAN).read_text(encoding='utf-8'))
    move = json.loads((root / MOVE).read_text(encoding='utf-8'))
    inventory = {}
    for r in _jsonl(root / INVENTORY):
        inventory.setdefault(r['sha256'], []).append(r)
    index = {item['sha256']: item for item in json.loads((root / DAY7_INDEX).read_text(encoding='utf-8'))['items']}
    cards = {c['sha']: c for c in mr.cards() if not c['house']}
    brain = _brain_rows(brain_db, [r['sha256'] for r in rows])
    per_file, failures = [], []
    for row in rows:
        target = (root / row['to']).resolve(); sha = row['sha256']
        mrow = mpaths.migration_row(row['from'], repo_root=root)
        inv = [r for r in inventory[sha] if r['relative_path'] == row['to']] if sha in inventory else []
        item = index[sha] if sha in index else {'paths': []}
        detail = ml.detail(sha)
        checks = {
            'resolves_from_the_original_path': _resolution(mpaths, row['original_path'], root, sha, target),
            'resolves_from_the_day6_path': _resolution(mpaths, row['from'], root, sha, target),
            'resolves_from_the_new_path': _resolution(mpaths, row['to'], root, sha, target),
            'identity_is_the_original_path': mpaths.original_material_key(row['to'], sha, repo_root=root) == (row['original_path'], sha),
            'migration_row_new_path': mrow is not None and mrow['new_path'] == row['to'],
            'inventory_relative_path': len(inv) == 1 and row['from'] in inv[0]['path_history']
                                       and inv[0]['original_source_path'] == row['original_path'],
            'day7_index_paths': row['to'] in item['paths'] and row['from'] not in item['paths'],
            'retrieval_card_path': sha in cards and cards[sha]['path'] == row['to'],
            'library_page_detail': detail is not None and detail['file_names'] == [Path(row['to']).name]
                                   and detail['card']['folder'] == 'house-designs',
        }
        if brain is not None:
            checks['brain_materials_row'] = brain[sha]['materials'] == [row['to']]
            checks['brain_caption_row'] = brain[sha]['caption'] in (None, row['to'])
        ok = all(v is True for v in checks.values())
        if not ok:
            failures.append(row['name'])
        per_file.append({'name': row['name'], 'sha256': sha, 'to': row['to'], 'resolves_everywhere': ok, 'checks': checks})
    house = json.loads((root / HOUSE_INDEX).read_text(encoding='utf-8'))
    moved_by_sha = {r['sha256']: r for r in rows}; house_rows = []
    for f in house['files']:
        copy = root / HOUSE_FILES / f['filename']; m = moved_by_sha.get(f['sha256'])
        entry = {'id': f['id'], 'filename': f['filename'], 'sha256': f['sha256'],
                 'house_file_exact': copy.is_file() and _sha(copy) == f['sha256'],
                 'materials_copy': m['to'] if m else None}
        if m:
            entry['materials_copy_resolves'] = _resolution(mpaths, m['original_path'], root, f['sha256'], (root / m['to']).resolve())
        house_rows.append(entry)
    house_shas = {f['sha256'] for f in house['files']}
    database = _db_rows_naming([r['from'] for r in rows])
    import tools.dip0.config as dip0
    dip0_sample = {r['original_path']: str(dip0.physical_path(r['original_path'], root)) == str(target)
                   for r in rows[:5] for target in [(root / r['to']).resolve()]}
    proof = {
        'schema': 'day8_house_designs_proof/1', 'measured_at': _now(), 'manifest': MANIFEST,
        'manifest_sha256': _sha(root / MANIFEST), 'destination': DESTINATION,
        'counts': {'planned': len(rows), 'moved_by_rule': plan_record['moved_by_rule'],
                   'moved_this_run_or_before': move['moved'] + move['previously_moved'],
                   'bytes_moved': sum(r['bytes'] for r in rows), 'held': len(plan_record['held']),
                   'held_by_rule': plan_record['held_by_rule'], 'scan': plan_record['scan'],
                   'list_caught_by_name_rules': plan_record['list_caught_by_name_rules']},
        'held': plan_record['held'],
        'move': {k: move[k] for k in ('state', 'moved', 'previously_moved', 'walk_before_count', 'started_at', 'finished_at')
                 if k in move},
        'tree_after': move['after'] if 'after' in move else None,
        'publication': move['publication'] if 'publication' in move else None,
        'resolution': {'files': len(per_file), 'resolving_everywhere': len(per_file) - len(failures), 'failures': failures,
                       'brain_checked': brain is not None, 'brain_db': str(brain_db) if brain_db else None},
        'house_ids': {'ids': len(house_rows), 'house_file_exact': sum(1 for h in house_rows if h['house_file_exact']),
                      'with_a_materials_copy': sum(1 for h in house_rows if h['materials_copy']),
                      'materials_copy_resolving': sum(1 for h in house_rows if h.get('materials_copy_resolves') is True),
                      'house_only': [h['id'] + ' ' + h['filename'] for h in house_rows if not h['materials_copy']],
                      'moved_but_not_in_the_house_index': sorted(r['name'] for r in rows if r['sha256'] not in house_shas),
                      'rows': house_rows},
        'database_rows_naming_a_day6_path_of_a_moved_file': database,
        'dip0_tools_physical_path_sample': dip0_sample,
        'per_file': per_file,
        'method': 'Every moved file is resolved through apps.ire.materials_paths from its original path, its Day 6 path '
                  'and its new path (sha256 re-measured by the resolver), its identity read back, and read through each '
                  'consumer that keeps a path: the DIP-0A inventory, the Day 7 index, the retrieval cards '
                  '(materials_retrieval.cards), the Library page (materials_library.detail), the brain\'s materials and '
                  'captions tables, and the dip0 tools\' physical_path. Every house id is checked against its own file.',
    }
    _save(root / PROOF, proof)
    return proof


if __name__ == '__main__':
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup()
    command = sys.argv[1]
    if command == 'plan':
        out = plan(ROOT); print(json.dumps({'rows': len(out['rows']), 'held': out['held'], 'scan': out['scan'],
                                            'list_caught_by_name_rules': out['list_caught_by_name_rules']}, ensure_ascii=False, indent=1))
    elif command == 'prepare':
        out = prepare(ROOT); print(json.dumps({k: v for k, v in out.items() if k not in ('held', 'rules')}, ensure_ascii=False, indent=1))
    elif command == 'apply':
        out = apply(ROOT, publication=publish); print(json.dumps(out, ensure_ascii=False, indent=1))
    elif command == 'proof':
        out = consumer_proof(ROOT, brain_db=ROOT / 'var/brain/brain.sqlite')
        print(json.dumps({k: out[k] for k in ('counts', 'move', 'resolution', 'database_rows_naming_a_day6_path_of_a_moved_file',
                                              'dip0_tools_physical_path_sample')}, ensure_ascii=False, indent=1))
        print(json.dumps({k: v for k, v in out['house_ids'].items() if k != 'rows'}, ensure_ascii=False, indent=1))
    else:
        raise SystemExit('usage: plan | prepare | apply | proof')
