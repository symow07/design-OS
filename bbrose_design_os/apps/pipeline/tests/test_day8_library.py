"""Day 8 §1c — the house designs into materials/house-designs/ (apps/pipeline/services/materials_house_designs.py) and the
resolver that keeps every earlier path working (apps/ire/materials_paths.py). Every move test runs on a tmp tree laid out
like the repository: a Day 6 manifest, the house list, the Day 7 index, the DIP-0A inventory and the house index."""
import hashlib, json, os, stat, sys
from pathlib import Path

import pytest

from apps.ire import materials_paths as mpaths
from apps.pipeline.services import materials_house_designs as mhd

pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='the exclusive rename is validated only on Darwin')

#: (display name, bytes, in the house list, original folder, caption words)
FILES = [
    ('YB-1059(ES6009).END.ai', b'house one', True, 'historical AI production designs', ['EYE SHADOW']),
    ('ES3083吸塑 展盒刀线.ai', b'house two', True, 'historical AI production designs', ['OUTER GLOW']),
    ('BL3090.ai', b'house three', True, 'historical AI production designs', ['BLUSH']),
    ('ES3090 刀模.ai', b'an extra caught by name', False, 'a', []),
    ('ES3090 刀模.ai', b'a second file of that name', False, 'b', []),
    ('MA1 sticker.ai', b'a doubtful short code', False, 'a', []),
    ('CONCEALER 307 M.ai', b'a code-like name', False, 'a', []),
    ('brand book.pdf', b'a caption-only house file', False, 'a', ['BBROSE', 'LOGO']),
    ('AdobeStock_12345.ai', b'stock', False, 'a', ['GIRL']),
    ('Drink South.otf', b'a font', False, 'fonts', []),
]


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _tree(root):
    """A tmp repository: the files where Day 6 put them, and every record the move reads or repoints."""
    day6, listing, items, inventory = [], [], [], []
    for name, data, listed, folder, seen in FILES:
        sha = _sha(data); old = 'materials/%s/%s' % (folder, name); new = 'materials/unknown/unclassified/%s/%s' % (sha[:16], name)
        p = root / new; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        st = p.stat()
        row = {'sha256': sha, 'old_path': old, 'new_path': new, 'kind': 'unknown', 'subject': 'unclassified',
               'display_name': name, 'original_directory': 'materials/' + folder, 'duplicate_group': None,
               'duplicate_copy_index': 0, 'size_bytes': st.st_size, 'mtime_ns': st.st_mtime_ns}
        day6.append(row)
        if listed:
            listing.append({'sha256': sha, 'name': name, 'manifest': row, 'paths': [new]})
        items.append({'sha256': sha, 'name': name, 'paths': [new], 'extension': Path(name).suffix, 'kind': 'photo',
                      'subject': 'artwork', 'tags': ['carton'], 'style': [], 'colours': [], 'text_seen': seen,
                      'surfaces': ['carton'], 'preview': False, 'caption_source': 'day7-haiku',
                      'rights': {'tier': 'house', 'excluded': False, 'basis': 'D-D7-1'}})
        inventory.append({'relative_path': new, 'sha256': sha, 'filename': name, 'original_source_path': old,
                          'source_path': old, 'path_history': [old], 'root_folder': folder})
    (root / mhd.DAY6_MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (root / mhd.DAY6_MANIFEST).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in day6))
    (root / mhd.HOUSE_LIST).parent.mkdir(parents=True, exist_ok=True)
    (root / mhd.HOUSE_LIST).write_text(json.dumps(listing, ensure_ascii=False, indent=1))
    (root / mhd.DAY7_INDEX).parent.mkdir(parents=True, exist_ok=True)
    (root / mhd.DAY7_INDEX).write_text(json.dumps({'schema': 'day7_materials_index/1', 'items': items}, ensure_ascii=False, indent=0) + '\n')
    (root / mhd.INVENTORY).parent.mkdir(parents=True, exist_ok=True)
    (root / mhd.INVENTORY).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in inventory))
    house = root / mhd.HOUSE_FILES; house.mkdir(parents=True)
    (house / FILES[0][0]).write_bytes(FILES[0][1])
    (root / mhd.HOUSE_INDEX).write_text(json.dumps({'schema': 'house_reference_index/1.0', 'files': [
        {'id': 'house-001', 'filename': FILES[0][0], 'sha256': _sha(FILES[0][1]), 'status': 'rasterised',
         'pages': [{'png': 'previews-day5/001-page-1.png'}], 'description': 'peach eyeshadow carton'}]}, ensure_ascii=False))
    return {r['new_path']: r for r in day6}


def _snapshot(root):
    """Every file under materials/ with its bytes, spelled as readdir returns it."""
    out = {}
    for parent, _dirs, names in os.walk(root / 'materials'):
        for name in names:
            p = Path(parent) / name; out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def _records(root):
    return {rel: (root / rel).read_bytes() for rel in (mhd.INVENTORY, mhd.DAY7_INDEX, mhd.HOUSE_INDEX)}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path.resolve(); _tree(root)
    return root


def test_plan_rules_hold_list_and_name_collision(repo):
    """The list's rows move by the list; an extra moves by the name rule that caught it; a doubtful code, a code-like
    name and a caption-only file are held, never moved; a second file of one name gets -<sha16>."""
    out = mhd.plan(repo)
    rows = {r['to']: r for r in out['rows']}
    assert [r['rule'] for r in out['rows']].count(mhd.LIST_RULE) == 3
    extras = [r for r in out['rows'] if r['rule'] != mhd.LIST_RULE]
    assert len(extras) == 2 and all('product code ES: ES3090' in r['rule'] and 'packaging term: 刀模' in r['rule'] for r in extras)
    second = _sha(b'a second file of that name'); first = _sha(b'an extra caught by name')
    names = sorted(Path(r['to']).name for r in extras)
    assert 'materials/house-designs/ES3090 刀模.ai' in rows
    assert ('ES3090 刀模-%s.ai' % second[:16] in names) != ('ES3090 刀模-%s.ai' % first[:16] in names)
    held = {h['name']: h for h in out['held']}
    assert held['MA1 sticker.ai']['reason'].startswith('doubtful')
    assert held['CONCEALER 307 M.ai']['rule'] == 'code-like name'
    assert held['brand book.pdf']['rule'].startswith('caption only')
    assert 'AdobeStock_12345.ai' not in held and not any('AdobeStock' in r['to'] for r in out['rows'])
    assert out['list_caught_by_name_rules']['caught'] == 2 and out['list_caught_by_name_rules']['not_caught'] == ['BL3090.ai']


def test_manifest_first_then_the_move_journal_resolution_repoint_and_a_quiet_rerun(repo):
    before = _records(repo)
    mhd.prepare(repo)
    rows = mhd._jsonl(repo / mhd.MANIFEST)
    seen = []

    def manifest_exists_before_each_rename(row):
        assert (repo / mhd.MANIFEST).exists()
        assert mhd._jsonl(repo / mhd.JOURNAL)[-1] == {**mhd._jsonl(repo / mhd.JOURNAL)[-1], 'event': 'intent', 'from': row['from']}
        seen.append(row['to'])

    report = mhd.apply(repo, publication=mhd.publish, after_rename=manifest_exists_before_each_rename)
    assert report['state'] == 'VERIFIED' and report['moved'] == len(rows) == len(seen) == 5
    assert report['after']['passed'] and report['after']['path_set_matches'] and report['file_metadata_preserved']
    journal = mhd._jsonl(repo / mhd.JOURNAL)
    assert [e['event'] for e in journal] == ['intent', 'done'] * len(rows) and all('moved_at' in e for e in journal[1::2])
    for row in rows:
        target = (repo / row['to']).resolve()
        assert not (repo / row['from']).exists() and _sha(target.read_bytes()) == row['sha256']
        for src in (row['original_path'], row['from'], row['to']):
            assert mpaths.resolve_material_file(src, repo_root=repo, expected_sha=row['sha256']) == target
        assert mpaths.original_material_key(row['to'], row['sha256'], repo_root=repo) == (row['original_path'], row['sha256'])
        composed = mpaths.migration_row(row['from'], repo_root=repo)
        assert composed['new_path'] == row['to'] and composed['via'] == [row['from']] and composed['old_path'] == row['original_path']
    inventory = {r['sha256']: r for r in mhd._jsonl(repo / mhd.INVENTORY)}
    index = {i['sha256']: i for i in json.loads((repo / mhd.DAY7_INDEX).read_text())['items']}
    for row in rows:
        inv = inventory[row['sha256']]
        assert inv['relative_path'] == row['to'] and inv['path_history'] == [row['original_path'], row['from']]
        assert inv['original_source_path'] == row['original_path'] and index[row['sha256']]['paths'] == [row['to']]
    assert (repo / mhd.HOUSE_INDEX).read_bytes() == before[mhd.HOUSE_INDEX]
    held = _sha(b'a doubtful short code')
    assert inventory[held]['relative_path'].startswith('materials/unknown/') and (repo / inventory[held]['relative_path']).exists()
    # a re-run moves nothing, rewrites nothing, and keeps the move's own record
    records = _records(repo); snapshot = _snapshot(repo)
    again = mhd.apply(repo, publication=mhd.publish)
    assert again['state'] == 'VERIFIED_NOOP' and again['moved'] == 0 and again['previously_moved'] == len(rows)
    assert _records(repo) == records and _snapshot(repo) == snapshot
    assert json.loads((repo / mhd.MOVE).read_text())['state'] == 'VERIFIED'
    assert mhd.prepare(repo)['manifest_state'] == 'EXISTS_EQUAL'


def test_an_injected_failure_rolls_every_moved_pair_back(repo):
    snapshot, records = _snapshot(repo), _records(repo)
    mhd.prepare(repo)
    with pytest.raises(mhd.MoveError, match='Injected'):
        mhd.apply(repo, publication=mhd.publish, fail_after=2)
    assert _snapshot(repo) == snapshot and _records(repo) == records
    assert not (repo / mhd.DESTINATION).exists()
    report = json.loads((repo / mhd.MOVE).read_text())
    assert report['state'] == 'ROLLED_BACK' and report['rollback']['passed'] and report['rollback']['reversed'] == 2
    assert [e['event'] for e in mhd._jsonl(repo / mhd.JOURNAL)].count('rollback') == 2
    row = mhd._jsonl(repo / mhd.MANIFEST)[0]
    assert mpaths.resolve_material_file(row['original_path'], repo_root=repo) == (repo / row['from']).resolve()


def test_a_manifest_hash_that_disagrees_stops_before_that_rename_and_rolls_back_cleanly(repo):
    snapshot = _snapshot(repo)
    mhd.prepare(repo)
    rows = mhd._jsonl(repo / mhd.MANIFEST); rows[3]['sha256'] = '0' * 64
    (repo / mhd.MANIFEST).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    with pytest.raises(mhd.MoveError, match='Source bytes differ'):
        mhd.apply(repo)
    assert _snapshot(repo) == snapshot
    report = json.loads((repo / mhd.MOVE).read_text())
    assert report['state'] == 'ROLLED_BACK' and report['rollback']['reversed'] == 3 and report['rollback']['passed']


def test_a_destination_corrupted_after_its_rename_is_named_and_never_moved_back(repo):
    mhd.prepare(repo)
    rows = mhd._jsonl(repo / mhd.MANIFEST)

    def corrupt_the_second(row):
        if row['to'] == rows[1]['to']:
            (repo / row['to']).write_bytes(b'changed under the move')

    with pytest.raises(mhd.RollbackError):
        mhd.apply(repo, after_rename=corrupt_the_second)
    report = json.loads((repo / mhd.MOVE).read_text())
    assert report['state'] == 'ROLLBACK_INCOMPLETE' and report['error'].startswith('MoveError: Moved bytes differ')
    assert report['rollback']['conflicts'] == [rows[1]['to']] and report['rollback']['reversed'] == 1
    assert (repo / rows[0]['from']).exists() and not (repo / rows[0]['to']).exists()
    assert (repo / rows[1]['to']).read_bytes() == b'changed under the move'


def test_a_failed_repoint_restores_the_records_and_reverses_the_moves(repo):
    index = repo / mhd.DAY7_INDEX
    index.write_text(json.dumps(json.loads(index.read_text()), ensure_ascii=False, indent=2) + '\n')   # no longer round-trips
    snapshot, records = _snapshot(repo), _records(repo)
    mhd.prepare(repo)
    with pytest.raises(mhd.PublicationError, match='round-trip'):
        mhd.apply(repo, publication=mhd.publish)
    assert _snapshot(repo) == snapshot and _records(repo) == records     # the inventory, repointed first, is restored too
    assert json.loads((repo / mhd.MOVE).read_text())['rollback']['passed']


def test_a_run_stopped_between_a_rename_and_its_done_line_resumes(repo):
    mhd.prepare(repo)
    rows = mhd._jsonl(repo / mhd.MANIFEST); first = rows[0]
    (repo / mhd.DESTINATION).mkdir()
    mhd._journal(repo / mhd.JOURNAL, {'event': 'intent', 'from': first['from'], 'to': first['to']})
    mhd._rename_preserving_flags(repo / first['from'], repo / first['to'], 0)
    report = mhd.apply(repo, publication=mhd.publish)
    assert report['state'] == 'VERIFIED' and report['previously_moved'] == 1 and report['moved'] == len(rows) - 1
    assert report['after']['passed'] and report['metadata_read_at_destination'] == 1 and report['file_metadata_preserved']


def test_an_occupied_destination_or_another_spelling_of_it_refuses_before_anything_moves(repo):
    snapshot = _snapshot(repo)
    mhd.prepare(repo)
    row = mhd._jsonl(repo / mhd.MANIFEST)[0]
    (repo / mhd.DESTINATION).mkdir(); (repo / row['to']).write_bytes(b'unrelated')
    with pytest.raises(mhd.MoveError, match='Both locations'):
        mhd.apply(repo)
    assert (repo / row['to']).read_bytes() == b'unrelated' and (repo / row['from']).exists()
    (repo / row['to']).unlink(); (repo / mhd.DESTINATION).rmdir(); (repo / 'materials/House-Designs').mkdir()
    with pytest.raises(mhd.MoveError, match='identifies'):
        mhd.apply(repo)
    (repo / 'materials/House-Designs').rmdir()
    assert _snapshot(repo) == snapshot


def test_a_user_immutable_flag_survives_the_move_and_the_rollback(repo):
    mhd.prepare(repo)
    rows = mhd._jsonl(repo / mhd.MANIFEST); row = rows[0]; seen = {}
    os.chflags(repo / row['from'], stat.UF_IMMUTABLE)
    try:
        def flags_at_the_destination(r):
            if r['to'] == row['to']:
                seen['flags'] = (repo / r['to']).stat().st_flags
        with pytest.raises(mhd.MoveError, match='Injected'):
            mhd.apply(repo, fail_after=len(rows), after_rename=flags_at_the_destination)
        assert seen['flags'] == stat.UF_IMMUTABLE
        assert (repo / row['from']).stat().st_flags == stat.UF_IMMUTABLE
        assert json.loads((repo / mhd.MOVE).read_text())['rollback']['passed']
    finally:
        for name in ('from', 'to'):
            if (repo / row[name]).exists():
                os.chflags(repo / row[name], 0)


def test_without_a_later_manifest_the_resolver_is_the_day6_resolver(repo):
    day6 = {r['new_path']: r for r in mhd._jsonl(repo / mhd.DAY6_MANIFEST)}
    for new, row in day6.items():
        assert mpaths.migration_row(row['old_path'], repo_root=repo) == row and 'via' not in mpaths.migration_row(new, repo_root=repo)
        assert mpaths.resolve_material_file(row['old_path'], repo_root=repo, expected_sha=row['sha256']) == (repo / new).resolve()


@pytest.mark.parametrize('fault', ['sha', 'unplaced', 'onto_an_identity'])
def test_a_later_manifest_that_disagrees_with_the_migration_refuses(repo, fault):
    day6 = mhd._jsonl(repo / mhd.DAY6_MANIFEST); row = day6[0]
    move = {'sha256': row['sha256'], 'from': row['new_path'], 'to': 'materials/house-designs/' + row['display_name']}
    if fault == 'sha':
        move['sha256'] = '0' * 64
    elif fault == 'unplaced':
        move['from'] = 'materials/nowhere/' + row['display_name']
    else:
        move['to'] = day6[1]['new_path']
    (repo / mhd.MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (repo / mhd.MANIFEST).write_text(json.dumps(move, ensure_ascii=False) + '\n')
    with pytest.raises(mpaths.MaterialPathError):
        mpaths.resolve_material_file(row['old_path'], repo_root=repo)


def test_the_resolver_before_the_move_after_it_and_after_a_rollback(repo):
    mhd.prepare(repo)
    rows = mhd._jsonl(repo / mhd.MANIFEST); row = rows[0]
    before, after = (repo / row['from']).resolve(), (repo / row['to']).resolve()
    assert mpaths.resolve_material_file(row['original_path'], repo_root=repo, expected_sha=row['sha256']) == before
    mhd.apply(repo, publication=mhd.publish)
    assert mpaths.resolve_material_file(row['original_path'], repo_root=repo, expected_sha=row['sha256']) == after
    walk = set(json.loads((repo / mhd.RUNTIME / 'walk-before.json').read_text())['paths'])
    assert mhd.rollback(repo, rows, walk, True)['passed']
    assert mpaths.resolve_material_file(row['original_path'], repo_root=repo, expected_sha=row['sha256']) == before
    with pytest.raises(mpaths.MaterialPathError):
        mpaths.resolve_material_file(row['original_path'], repo_root=repo, expected_sha='0' * 64)


def test_every_consumer_reads_the_new_path(repo):
    """The retrieval cards and the Library page read the repointed index; the brain's caption join, the dip0 tools and
    the placement identity read the resolver."""
    from django.test import override_settings
    from apps.pipeline.services import materials_retrieval as mr
    from apps.dashboard import materials_library as ml
    import tools.dip0.config as dip0
    mhd.prepare(repo); mhd.apply(repo, publication=mhd.publish)
    rows = mhd._jsonl(repo / mhd.MANIFEST)
    with override_settings(MATERIALS_INDEX_PATH=str(repo / mhd.DAY7_INDEX), HOUSE_INDEX_PATH=str(repo / mhd.HOUSE_INDEX)):
        cards = {c['sha']: c for c in mr.cards() if not c['house']}
        house = [c for c in mr.cards() if c['house']]
        for row in rows:
            assert cards[row['sha256']]['path'] == row['to']
            assert ml.present_index(mr.index_row(row['sha256']))['folder'] == 'house-designs'
            assert ml.detail(row['sha256'])['file_names'] == [Path(row['to']).name]
        assert house[0]['path'] == mhd.HOUSE_FILES + '/' + FILES[0][0]          # the house index reads its own copy
    for row in rows:
        move = mpaths.migration_row(row['original_path'], repo_root=repo)        # the brain's caption join (rebuild.py)
        assert move['new_path'] == row['to'] and move['sha256'] == row['sha256']
        assert dip0.physical_path(row['original_path'], repo) == (repo / row['to']).resolve()


def test_on_this_machine_every_house_design_resolves_to_its_new_home():
    """The live tree, once the move has run here: every manifest row's original and Day 6 paths name the new path (no
    hashing), and three rows resolve through the resolver with their sha256 re-measured."""
    root = mhd.ROOT
    if not (root / mhd.MANIFEST).exists() or not (root / mhd.DESTINATION).is_dir():
        pytest.skip('the house-designs move has not run on this machine')
    rows = mhd._jsonl(root / mhd.MANIFEST)
    assert mhd.MANIFEST in mpaths.LATER_MANIFESTS
    for row in rows:
        for src in (row['original_path'], row['from'], row['to']):
            assert mpaths.migration_row(src)['new_path'] == row['to']
        assert mhd._spelled(root, row['to']) and not mhd._spelled(root, row['from'])
    for row in rows[:3]:
        assert mpaths.resolve_material_file(row['original_path'], expected_sha=row['sha256']) == (root / row['to']).resolve()
