"""Manifest-first, rename-only migration with conservation and automatic rollback.

Run prepare, inspect its evidence, then apply. Interrupted runs recover from both
paths in every manifest pair, including rename-before-journal crash windows.

Day 6, attempt 2 (Codex, rolled back): every byte was conserved, counts matched,
but 4,367 destination paths were not byte-exact. The Data volume is
case-insensitive APFS, so the planned ``materials/fonts/`` tree was created
inside the legacy ``materials/Fonts/`` directory and os.walk reported
``materials/Fonts/...``. The proof stays byte-exact. Any existing directory whose
spelling differs from a planned destination directory only by case or Unicode
normalization is re-spelled by a journaled exclusive rename before the file moves
and spelled back on rollback (``spelling_plan``). This volume preserves Unicode
form in both directions, so original names stay in the manifest paths as the tree
note requires; the ``diagnose`` stage measures both facts without writing.
"""
from pathlib import Path
from collections import Counter
import argparse, ctypes, datetime, errno, fcntl, hashlib, json, os, re, shutil, sys, unicodedata, stat
from tools.rescue_materials_census import ROOT, OUT, AUDIT, sha, save, physical_files

SPELLING_FILE = 'directory-spelling.json'


def slug(value, limit=48):
    s = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub('[^a-z0-9]+', '-', s).strip('-')[:limit] or 'unclassified'


def bounded(root, relative):
    if Path(relative).is_absolute() or '..' in Path(relative).parts or not relative.startswith('materials/'):
        raise ValueError('Unbounded manifest path')
    path = root / relative
    path.resolve().relative_to((root / 'materials').resolve())
    return path


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def rename_exclusive(old, new):
    """Darwin RENAME_EXCL from sys/stdio.h; never overwrite, copy or unlink."""
    if sys.platform != 'darwin':
        raise RuntimeError('Exclusive rename implementation is validated only on Darwin')
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renamex_np; fn.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    if fn(os.fsencode(old), os.fsencode(new), 4):
        e = ctypes.get_errno(); raise OSError(e, os.strerror(e), str(new))
    fsync_dir(old.parent)
    if old.parent != new.parent:
        fsync_dir(new.parent)


def rename_preserving_flags(old, new, expected_flags=None):
    flags=old.stat().st_flags if expected_flags is None else expected_flags
    # The owner's rename authorization includes temporarily clearing the user's
    # immutable bit on that exact file. Restore every flag immediately; never
    # alter system immutable flags, permissions, owners, xattrs or file bytes.
    original=old.stat().st_flags
    if original & stat.UF_IMMUTABLE:os.chflags(old,original & ~stat.UF_IMMUTABLE)
    try:
        rename_exclusive(old,new)
    finally:
        current=new if new.exists() and not old.exists() else old
        if current.exists() and current.stat().st_flags!=flags:os.chflags(current,flags)


def append_journal(path, row):
    with path.open('a') as stream:
        stream.write(json.dumps(row, ensure_ascii=False)+'\n'); stream.flush(); os.fsync(stream.fileno())


def prepare():
    if not (OUT / 'mockups-census.json').exists():
        raise RuntimeError('PSD census evidence must precede tree/manifest')
    rows = [json.loads(x) for x in (AUDIT / 'inventory-2026-10-19.jsonl').read_text().splitlines()]
    fonts = json.loads((OUT / 'fonts-census.json').read_text())
    families = {f['source_path']: (f['faces'][0].get('name_fields_raw', {}).get('1') or 'unclassified') for f in fonts['files'] if f['faces']}
    seen = Counter(); counts=Counter(r['sha256'] for r in rows); manifest = []; targets = set()
    for row in sorted(rows, key=lambda r:r['relative_path']):
        old = row['relative_path']; kind = row['kind_guess']; subject = slug(families.get(old, 'unclassified'))
        digest = row['sha256']; number = seen[digest]; seen[digest] += 1
        if kind == 'unknown':
            name = Path(old).name; destination = f'materials/unknown/{subject}/{digest[:16]}/{name}'
        else:
            name = f'{kind}_{subject}_{slug(Path(old).stem)}_{digest[:16]}{row["extension"]}'
            destination = f'materials/{kind}/{subject}/{name}'
        if number:
            destination = f'materials/_duplicates/{digest[:16]}/{number:04d}_{name}'
        key = unicodedata.normalize('NFC', destination).casefold()
        if key in targets:
            raise ValueError('Case/normalization destination collision: '+destination)
        targets.add(key)
        manifest.append({'sha256': digest, 'old_path': old, 'new_path': destination, 'kind': kind, 'subject': subject,
                         'display_name': Path(old).name, 'original_directory': str(Path(old).parent),
                         'duplicate_group': digest if counts[digest]>1 else None,
                         'duplicate_copy_index': number, 'size_bytes': row['size_bytes'], 'mtime_ns': row['mtime_ns']})
    tree = '''# Materials tree - Day 6, owner D-D6-4\n\nUsed unless the owner objects. Rights and licence scope remain attached to each original path and SHA.\n\n- Top level: mockups, patterns, backgrounds, ornaments, product-vectors, photos, fonts, dielines, licence-evidence, unknown. Empty kinds are reserved, not evidence of classified content.\n- Kind is an explicit extension/path heuristic in the census, never an assertion of visual content. PSD alone does not mean mockup; vector format alone does not mean product.\n- Subject is the parsed font family for fonts, otherwise unclassified until a visual census supplies evidence.\n- Known-kind names: kind_subject_source_shorthash.ext, ASCII lowercase, punctuation normalized to hyphens, no spaces. The original Unicode filename and directory remain in every manifest row.\n- Unknown files retain the exact original filename under unknown/unclassified/<hash-prefix>/; no guessed subject or translated filename.\n- Equal SHA bytes retain all copies: first original path in lexical order enters its kind; subsequent originals enter _duplicates/<hash-prefix>/<copy-number>_<name>. Rights are never merged by hash.\n- Three Finder files and the hidden JPEG are retained. Generated _tree.md and _migration metadata are excluded from conservation; _duplicates is included.\n- Rename only, exclusive destinations, same filesystem. Count, SHA multiset and every manifest path are verified from disk; failure automatically reverses moved pairs. No original directory is deleted.\n'''
    (OUT / 'tree.md').write_text(tree)
    target = OUT / 'manifest-2026-10-19.jsonl'
    if target.exists():
        raise ValueError('Manifest already exists; never regenerate over an active migration')
    target.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in manifest))
    meta = ROOT / 'materials/_migration'; meta.mkdir(exist_ok=True)
    (meta / target.name).write_bytes(target.read_bytes())
    (ROOT / 'materials/_tree.md').write_text(tree)
    for p in (target, meta / target.name, ROOT / 'materials/_tree.md'):
        with p.open('rb') as stream: os.fsync(stream.fileno())
        fsync_dir(p.parent)
    save(OUT / 'migration-prepared.json', {'state':'PREPARED','count':len(manifest),'manifest_sha256':sha(target),
                                        'tree_sha256':sha(OUT/'tree.md'),'moves_started':False})
    return manifest


# --- directory spelling: the volume's identity rule versus the manifest's byte-exact paths ---------------------

def spelling_key(name):
    """Two names this volume may treat as one entry: NFC form, case folded."""
    return unicodedata.normalize('NFC', name).casefold()


def volume_case_insensitive(root):
    """Measured without writing: the corpus directory looked up in another case resolves to itself."""
    a = Path(root) / 'materials'; b = Path(root) / 'MATERIALS'
    return a.is_dir() and b.exists() and os.path.samefile(a, b)


def planned_directories(rows):
    seen = {}
    for row in rows:
        parts = row['new_path'].split('/')
        for depth in range(2, len(parts)):
            seen.setdefault('/'.join(parts[:depth]), None)
    return sorted(seen, key=lambda rel: (rel.count('/'), rel))


class _Listing:
    """Cached directory listings grouped by the identity rule; read-only."""
    def __init__(self, root):
        self.root = Path(root); self.cache = {}

    def entries(self, relative):
        if relative not in self.cache:
            path = self.root / relative; table = {}
            if path.is_dir() and not path.is_symlink():
                for name in os.listdir(path):
                    table.setdefault(spelling_key(name), []).append(name)
            self.cache[relative] = table
        return self.cache[relative]


def spelled(root, relative):
    """True when the entry is present under exactly this spelling (byte-exact readdir)."""
    parent, name = relative.rsplit('/', 1); path = Path(root) / parent
    return path.is_dir() and name in os.listdir(path)


def spelling_plan(root, rows):
    """Existing directories that the volume identifies with a planned destination directory under another spelling.

    Shallow first. Each is re-spelled to the planned form by an exclusive rename of
    the same inode before any file moves, journaled, and spelled back on rollback.
    A symlink or a non-directory occupying the spelling refuses the migration
    before anything moves. On a volume that distinguishes the spellings the plan
    is empty because the planned path does not resolve to the existing entry."""
    root = Path(root); listing = _Listing(root); plan = []
    for relative in planned_directories(rows):
        parent, name = relative.rsplit('/', 1)
        for existing in listing.entries(parent).get(spelling_key(name), []):
            if existing == name:
                continue
            existing_path = root / parent / existing; planned_path = root / relative
            if not planned_path.exists() or not os.path.samefile(existing_path, planned_path):
                continue
            if existing_path.is_symlink() or not existing_path.is_dir():
                raise RuntimeError('Destination directory spelling occupied by a non-directory: ' + parent + '/' + existing)
            plan.append({'from': parent + '/' + existing, 'to': relative})
    return plan


def respell_directory(root, source_rel, target_rel, journal, key):
    """Rename one directory inode to another spelling of itself; never a distinct entry."""
    source = bounded(root, source_rel); target = bounded(root, target_rel)
    if source.is_symlink() or not source.is_dir():
        raise RuntimeError('Directory to re-spell is missing: ' + source_rel)
    if not (target.exists() and os.path.samefile(source, target)):
        raise RuntimeError('Re-spelling would replace a distinct entry: ' + target_rel)
    append_journal(journal, {key + '_intent': source_rel, 'to': target_rel})
    rename_exclusive(source, target)
    if not spelled(root, target_rel):
        raise RuntimeError('Re-spelling did not take effect: ' + target_rel)
    append_journal(journal, {key + '_done': target_rel})


def restore_spelling(root, journal):
    plan_path = journal.parent / SPELLING_FILE
    if not plan_path.exists():
        return []
    restored = []
    for item in reversed(json.loads(plan_path.read_text())):
        if spelled(root, item['to']) and not spelled(root, item['from']):
            respell_directory(root, item['to'], item['from'], journal, 'dir_rollback'); restored.append(item)
    return restored


def predicted_spelling(root, rows):
    """What os.walk would report for each planned destination on the live tree, without writing."""
    root = Path(root); listing = _Listing(root); out = {}
    for row in rows:
        parts = row['new_path'].split('/'); walked = [parts[0]]; current = parts[0]
        for component in parts[1:-1]:
            match = None
            for candidate in listing.entries(current).get(spelling_key(component), []):
                planned = root / current / component
                if candidate == component or (planned.exists() and os.path.samefile(root / current / candidate, planned)):
                    match = candidate; break
            walked.append(component if match is None else match); current = '/'.join(walked)
        walked.append(parts[-1]); out[row['new_path']] = '/'.join(walked)
    return out


def byte_difference(expected, observed):
    a, b = expected.encode(), observed.encode(); n = min(len(a), len(b))
    offset = next((i for i in range(n) if a[i] != b[i]), n)
    return {'expected': expected, 'observed': observed, 'first_differing_byte_offset': offset,
            'expected_byte': '0x%02x' % a[offset] if offset < len(a) else None,
            'observed_byte': '0x%02x' % b[offset] if offset < len(b) else None,
            'expected_utf8_length': len(a), 'observed_utf8_length': len(b)}


def diagnose(root, rows):
    """Manifest versus the live tree: predicted byte-exact mismatches and their cause, read-only."""
    predicted = predicted_spelling(root, rows)
    mismatches = [byte_difference(k, v) for k, v in predicted.items() if k != v]
    non_nfc = [r['new_path'] for r in rows if unicodedata.normalize('NFC', r['new_path']) != r['new_path']]
    mismatched = {m['expected'] for m in mismatches}
    def first_component(m):
        return next(i for i, (x, y) in enumerate(zip(m['expected'].split('/'), m['observed'].split('/'))) if x != y)
    plan = spelling_plan(root, rows)
    leftovers = []
    for item in plan:
        depth = item['to'].count('/') + 1
        children = [d for d in planned_directories(rows) if d.count('/') == depth and d.startswith(item['to'] + '/')]
        present = [d for d in children if spelled(root, d)]
        empty = [d for d in present if not any((Path(root) / d).iterdir())]
        leftovers.append({'directory': item['from'], 'planned_children': len(children), 'present_under_other_spelling': len(present), 'empty': len(empty)})
    return {'schema': 'day6_migration_diagnosis/1', 'rows': len(rows), 'volume_case_insensitive': volume_case_insensitive(root),
            'predicted_path_mismatches': len(mismatches), 'by_top_folder': dict(Counter(m['expected'].split('/')[1] for m in mismatches)),
            'first_differing_component_index': dict(Counter(first_component(m) for m in mismatches)),
            'first_20': mismatches[:20], 'non_ascii_new_paths': sum(any(ord(c) > 127 for c in r['new_path']) for r in rows),
            'non_nfc_new_paths': len(non_nfc), 'non_nfc_predicted_mismatching': sum(p in mismatched for p in non_nfc),
            'directory_spelling_plan': plan, 'leftover_scaffold_under_existing_spelling': leftovers,
            'method': 'Each planned destination directory is resolved component by component against the live tree with the volume\'s own identity (samefile); the manifest string is compared byte for byte with the spelling readdir returns. No file is written or moved.'}


def disk_proof(root, rows, side):
    expected = {r[side]: r['sha256'] for r in rows}
    observed = {}; links = []
    # Use local enumeration rather than manifest values as after-proof.
    for parent, dirs, names in os.walk(root / 'materials', followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(parent)/d).is_symlink() and Path(parent)/d != root/'materials/_migration']
        for name in names:
            p=Path(parent)/name
            if p==root/'materials/_tree.md': continue
            if p.is_symlink(): links.append(str(p)); continue
            if p.is_file():
                relative=str(p.relative_to(root)); observed[relative]=sha(p)
    result={'expected_count':len(rows),'actual_count':len(observed),'path_set_matches':set(expected)==set(observed),
            'sha_multiset_matches':Counter(expected.values())==Counter(observed.values()),
            'sha_set_matches':set(expected.values())==set(observed.values()),
            'every_manifest_row_exact':all(observed.get(k)==v for k,v in expected.items()),'symlinks':links,
            'hashes_remeasured':len(observed)}
    result['passed']=result['expected_count']==result['actual_count'] and all(result[k] for k in ('path_set_matches','sha_multiset_matches','sha_set_matches','every_manifest_row_exact')) and not links
    result['multiset_digest']=hashlib.sha256(json.dumps(sorted(Counter(observed.values()).items())).encode()).hexdigest()
    return result


def rollback(root, rows, journal):
    metadata_path=journal.parent/'file-metadata.json'
    metadata=json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    for row in reversed(rows):
        old,new=bounded(root,row['old_path']),bounded(root,row['new_path'])
        if old==new: continue
        if new.exists():
            if old.exists() or sha(new)!=row['sha256']:
                raise RuntimeError('Rollback conflict; preserve both locations for recovery')
            old.parent.mkdir(parents=True,exist_ok=True)
            rename_preserving_flags(new,old,metadata.get(row['old_path'],{}).get('flags'));append_journal(journal,{'rollback':row['old_path']})
    restored=restore_spelling(root,journal)
    proof=disk_proof(root,rows,'old_path')
    proof['directory_spelling_restored']=restored
    if not proof['passed']: raise RuntimeError('Rollback conservation failed')
    return proof


def apply(root, rows, evidence, *, fail_after=None, publication=None):
    root=Path(root).resolve();evidence=Path(evidence);evidence.mkdir(parents=True,exist_ok=True)
    journal=evidence/'move-journal.jsonl'
    with (evidence/'migration.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        started=False; moved=0;report={'state':'PRECHECK','rollback_triggered':False}
        # Safe completed rerun; never perform a second move.
        if all(bounded(root,r['new_path']).is_file() and not bounded(root,r['old_path']).exists() for r in rows):
            proof=disk_proof(root,rows,'new_path')
            if not proof['passed']: raise RuntimeError('Completed migration changed')
            if publication:publication()
            result={'state':'VERIFIED_NOOP','after':proof,'publication_checked':bool(publication)}
            save(evidence/'migration-proof.json',result)
            return result
        # Recover pending crash windows before attempting a fresh migration.
        previous=json.loads((evidence/SPELLING_FILE).read_text()) if (evidence/SPELLING_FILE).exists() else []
        if any(bounded(root,r['new_path']).exists() for r in rows) or any(spelled(root,item['to']) and not spelled(root,item['from']) for item in previous):
            if not journal.exists(): raise RuntimeError('Pre-existing destination; no owned journal')
            rollback(root,rows,journal)
        plan=spelling_plan(root,rows)
        targets=set();metadata={};device=(root/'materials').stat().st_dev
        for r in rows:
            old,new=bounded(root,r['old_path']),bounded(root,r['new_path'])
            if not old.is_file() or old.is_symlink():raise RuntimeError('Source unavailable or symlink')
            st=old.stat()
            metadata[r['old_path']]={'flags':st.st_flags,'mode':stat.S_IMODE(st.st_mode),'uid':st.st_uid,'gid':st.st_gid}
            if st.st_size!=r['size_bytes'] or st.st_mtime_ns!=r['mtime_ns']:raise RuntimeError('Source stat changed since census')
            if old==new:continue
            if new.exists() or new.is_symlink():raise RuntimeError('Occupied destination')
            key=unicodedata.normalize('NFC',str(new)).casefold()
            if key in targets:raise RuntimeError('Duplicate destination')
            targets.add(key)
            if st.st_dev!=device:raise RuntimeError('Cross-filesystem migration refused')
        save(evidence/'file-metadata.json',metadata)
        save(evidence/SPELLING_FILE,plan)
        report['directory_spelling']=plan;report['volume_case_insensitive']=volume_case_insensitive(root)
        try:
            started=True
            for item in plan:
                respell_directory(root,item['from'],item['to'],journal,'dir')
            for row in rows:
                bounded(root,row['new_path']).parent.mkdir(parents=True,exist_ok=True)
            for row in rows:
                old,new=bounded(root,row['old_path']),bounded(root,row['new_path'])
                if old==new:continue
                append_journal(journal,{'intent':row['old_path'],'to':row['new_path'],'sha256':row['sha256']})
                rename_preserving_flags(old,new,metadata[row['old_path']]['flags']);moved+=1
                append_journal(journal,{'done':row['old_path']})
                if moved%500==0: print(json.dumps({'stage':'rename','moved':moved}),flush=True)
                if fail_after and moved==fail_after:raise RuntimeError('Injected failure for rollback proof')
            after=disk_proof(root,rows,'new_path');report['after']=after
            report['file_metadata_preserved']=all({'flags':(root/r['new_path']).stat().st_flags,
                'mode':stat.S_IMODE((root/r['new_path']).stat().st_mode),'uid':(root/r['new_path']).stat().st_uid,
                'gid':(root/r['new_path']).stat().st_gid}==metadata[r['old_path']] for r in rows)
            if not report['file_metadata_preserved']:raise RuntimeError('File flags or metadata changed')
            if not after['passed']:raise RuntimeError('Conservation mismatch')
            if publication:publication()
            report.update(state='VERIFIED',moved=moved)
        except BaseException as exc:
            report.update(state='ROLLED_BACK',error=type(exc).__name__+': '+str(exc),rollback_triggered=True,moved=moved)
            report['rollback']=rollback(root,rows,journal)
            save(evidence/'migration-proof.json',report)
            raise
        save(evidence/'migration-proof.json',report)
        return report


def publish_indexes():
    """Atomic derived inventory publication; restore original bytes on any failure."""
    manifest=[json.loads(x) for x in (OUT/'manifest-2026-10-19.jsonl').read_text().splitlines()]
    mapping={r['old_path']:r for r in manifest}
    current=AUDIT/'inventory.jsonl';old_bytes=current.read_bytes()
    backup=ROOT/'materials/_migration/inventory-before.jsonl'
    if not backup.exists():backup.write_bytes(old_bytes)
    rows=[json.loads(x) for x in (AUDIT/'inventory-2026-10-19.jsonl').read_text().splitlines()]
    manifest_digest=sha(OUT/'manifest-2026-10-19.jsonl')
    for row in rows:
        move=mapping[row['relative_path']]
        row['path_history']=list(dict.fromkeys(row.get('path_history',[])+[row['relative_path']]))
        row['relative_path']=move['new_path'];row['filename']=Path(move['new_path']).name
        row['original_source_path']=move['old_path'];row['display_name']=move['display_name']
        row['duplicate_group']=move['duplicate_group']
        row['migration_manifest_sha256']=manifest_digest
    rows.extend(r for r in map(json.loads,old_bytes.decode().splitlines()) if not r['relative_path'].startswith('materials/'))
    payload=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows).encode()
    tracked=OUT/'inventory-migrated.jsonl';previous=tracked.read_bytes() if tracked.exists() else None
    try:
        temporary=current.with_suffix('.day6.tmp');temporary.write_bytes(payload);os.replace(temporary,current)
        tracked.write_bytes(payload)
        save(OUT/'index-publication.json',{'canonical_rows':len(rows),'material_rows':len(manifest),
                                         'previous_sha256':hashlib.sha256(old_bytes).hexdigest(),'current_sha256':sha(current),
                                         'path_history_preserved':True,'rights_changed':False})
    except BaseException:
        current.write_bytes(old_bytes)
        if previous is not None:tracked.write_bytes(previous)
        elif tracked.exists():tracked.unlink()
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','diagnose','apply'])
    parser.add_argument('--attempt',default=None,help='label for the saved proof copy, e.g. third')
    args=parser.parse_args();os.nice(10)
    if args.stage=='prepare':prepare()
    elif args.stage=='diagnose':
        rows=[json.loads(x) for x in (OUT/'manifest-2026-10-19.jsonl').read_text().splitlines()]
        report=diagnose(ROOT,rows);report['measured_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(OUT/'migration-diagnosis.json',report)
        print(json.dumps({k:v for k,v in report.items() if k!='first_20'},ensure_ascii=False),flush=True)
    else:
        rows=[json.loads(x) for x in (OUT/'manifest-2026-10-19.jsonl').read_text().splitlines()]
        evidence=ROOT/'materials/_migration'
        try:
            result=apply(ROOT,rows,evidence,publication=publish_indexes)
        except BaseException:
            if (evidence/'migration-proof.json').exists():
                shutil.copyfile(evidence/'migration-proof.json',OUT/('migration-%s-rollback-proof.json'%(args.attempt or 'latest')))
            raise
        save(OUT/'migration-proof.json',result)
        if args.attempt:save(OUT/('migration-%s-proof.json'%args.attempt),result)
        print(json.dumps(result),flush=True)
