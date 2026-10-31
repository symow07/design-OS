"""Day 12 §9 — "the pages serve pinned bytes" and "the image-call log audits clean (every generation and masked edit
listed per box; inputs only the picked sketches, the lid master and the logo)".

Every check runs on the day's real records — the call log (docs/audit/day-12/image-calls.jsonl), the spend ledger
(read only), the kept pictures and their requests, the page manifests (docs/audit/day-12/pages/*.json) — and skips
where they are not on this machine. Each carries a control that must fail, a planted fault: a row in a copy of the log,
an id in a copy of the ledger, an input in a copy of a real row, one byte of one published copy. A check that cannot
fail proves nothing.

Nothing here pays and nothing is written under docs/audit or var: the shared denylist cache is read from a private copy,
the ledger is opened read-only (its planted copy is made in tmp_path), and every page is published into a MEDIA_ROOT
under tmp_path with the test database — never the owner's media, never his tasks."""
import copy
import hashlib
import json
import re
import shutil
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import pytest

from apps.pipeline.services import round_calls as ig
from apps.pipeline.services import master_tasks as mt

DAY12 = ig.REPO / 'docs' / 'audit' / 'day-12'
DAY12_CALL_LOG = DAY12 / 'image-calls.jsonl'
LEDGER = ig.ROOT / 'var' / 'rescue_spend' / 'ledger.sqlite3'
#: where every Day 12 picture call is filed, in the ledger and the log (zilal_master.IMAGE_PREFIX); the box is the
#: operation's path between it and the call's own name ('day12/images/balm/S6': the box 'balm', the call 'S6')
IMAGE_OPS = 'day12/images/'
#: the lid master re-traced by D-D12-9's reader: the style reference of every Day 12 call, its bytes pinned by its own
#: Day 12 record (master.json's files)
LID12 = DAY12 / 'zilal' / 'lid'
LID_FLAT = LID12 / 'lid-master-flat.png'
PAGES = DAY12 / 'pages'
#: the pages §9 names: Ẓilāl's and the lipstick's, and — when their manifests exist — the balm's and the display's;
#: any other manifest in the folder is read too, so a new page is never missed

def _is_a_manifest(path):
    """[Day 12, the full suite's one failure] a page manifest says so by its schema: the folder also keeps the pages'
    live check (published.json), which is a record of the pages, not a page."""
    data = json.loads(path.read_text(encoding='utf-8'))
    return 'schema' in data and data['schema'] == mt.MANIFEST_SCHEMA


PAGE_NAMES = sorted({'zilal', 'lipstick', 'balm', 'display'} | {p.stem for p in PAGES.glob('*.json') if _is_a_manifest(p)})
#: the counts of a fault ``image_guard.audit`` keeps
FAULTS = ('non_openai_or_named_tool', 'rejected_or_web_inputs', 'competitor_prompts', 'sent_without_input_sha256',
          'sent_without_prompt', 'unknown_outcome')

log_here = pytest.mark.skipif(not DAY12_CALL_LOG.exists(), reason='the Day 12 call log is not here')
ledger_here = pytest.mark.skipif(not LEDGER.exists(), reason='the spend ledger is not here')


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _rows(log_path):
    """The call log's rows, split on '\\n' only (as ``image_guard.audit`` reads it)."""
    return [json.loads(l) for l in Path(log_path).read_text(encoding='utf-8').split('\n') if l.strip()]


def _under(path, root) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _box(operation: str) -> str:
    """The box a picture call is filed under: 'day12/images/display/header/S1' -> 'display/header'."""
    return operation[len(IMAGE_OPS):].rsplit('/', 1)[0]


def _stable_copy(src, dest):
    """A copy of the shared denylist cache that parses: another process may be rewriting it (``denylist`` writes it
    back in place), so a torn copy is taken again, never read as an empty cache (that would hash 11.7 GB again)."""
    for _ in range(4):
        shutil.copyfile(src, dest)
        try:
            json.loads(Path(dest).read_text())
            return True
        except ValueError:
            time.sleep(2.0)
    return False


@pytest.fixture(scope='module')
def deny(tmp_path_factory):
    """The real denylist (every picture under the rejected and the web roots, by sha256), computed once from a private
    copy of the cache: this test never writes var/day8/image-guard-denylist.json, which other agents read while making
    guarded calls."""
    if not ig.DENYLIST_CACHE.exists():
        pytest.skip('the denylist cache is not here (hashing every rejected picture takes too long for this file)')
    cache = tmp_path_factory.mktemp('guard') / 'denylist.json'
    if not _stable_copy(ig.DENYLIST_CACHE, cache):
        pytest.skip('the shared denylist cache did not parse in four reads (being rewritten)')
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ig, 'DENYLIST_CACHE', cache)
        return ig.denylist()


# ======================================================================================================================
# 1. The call log audits clean (D-D8-2, D-D8-7, D-D8-10 asserted from the log)
# ======================================================================================================================

@log_here
def test_the_day12_log_audits_clean_and_each_planted_row_moves_its_own_count(tmp_path, monkeypatch, deny):
    """``image_guard.audit`` on Day 12's own log — the log the guard writes today, under today's prefix — with the
    denylist read from the private copy: it holds, its calls are the log's rows and its sent calls the rows that went
    out, every count of a fault 0. The controls: three planted rows, each a copy of a real one with one field changed —
    a rejected design's bytes as its one bad input (Day 9's B-1.3 build, first shown to be on the denylist so the
    control is not vacuous), a competitor named in the prompt, another provider — each moves exactly its own count
    from 0 to 1 and no other."""
    assert ig.CALL_LOG == DAY12_CALL_LOG and ig.TODAY_OPERATION_PREFIX == 'day12/'
    monkeypatch.setattr(ig, 'denylist', lambda **kw: deny)
    rows = _rows(DAY12_CALL_LOG)
    audit = ig.audit(DAY12_CALL_LOG)
    assert audit['holds'] and audit['log_present'] and not audit['log_empty'], audit
    assert audit['calls'] == len(rows), audit
    assert audit['sent'] == len([r for r in rows if r.get('outcome') in ('made', 'failed')]), audit
    assert audit['refused'] == len([r for r in rows if r.get('outcome') == 'refused']), audit
    assert all(audit[k] == 0 for k in FAULTS), audit

    build = ig.REPO / 'docs' / 'audit' / 'day-9' / 'concepts' / 'B-1.3' / 'truthful.png'
    if not build.exists():
        pytest.skip('Day 9\'s B-1.3 build (the planted rejected design) is not on this machine')
    assert _sha(build) in deny['rejected']                 # the planted input IS a rejected design
    base = [r for r in rows if r['outcome'] == 'made'][0]
    rejected = copy.deepcopy(base)
    # the call's sheet replaced (never the logo, which the audit exempts by its pin): exactly one bad input
    sheet = next(n for n, i in enumerate(rejected['inputs']) if not ig._is_approved_logo(i))
    rejected['inputs'][sheet] = dict(rejected['inputs'][sheet], path=str(build), sha256=_sha(build))
    competitor = dict(copy.deepcopy(base), prompt=base['prompt'] + ' As Charlotte Tilbury would.')
    provider = dict(copy.deepcopy(base), provider='google')
    for planted, count in ((rejected, 'rejected_or_web_inputs'), (competitor, 'competitor_prompts'),
                           (provider, 'non_openai_or_named_tool')):
        log = tmp_path / ('%s.jsonl' % count)
        log.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows + [planted]) + '\n', encoding='utf-8')
        found = ig.audit(log)
        assert not found['holds'] and found[count] == 1, (count, found)
        assert all(found[k] == 0 for k in FAULTS if k != count), (count, found)


# ======================================================================================================================
# 2. The log, the ledger and the kept pictures are one set, box by box
# ======================================================================================================================

def _ledger(path):
    """The spend ledger's OpenAI calls of Day 12 (every operation under 'day12/', so a picture call filed elsewhere
    cannot escape), read only: {id: (operation, state)}."""
    with closing(sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=30)) as db:
        rows = db.execute("select id, operation, state from calls where provider = 'openai'").fetchall()
    return {i: (op, state) for i, op, state in rows if op.startswith(ig.TODAY_OPERATION_PREFIX)}


def _kept_pictures():
    """Every paid picture Day 12's code kept: each ``result.json`` under day-12 — {reservation id: (the picture, the
    sha256 the record keeps, its folder)} — and, in words, every one that does not say its reservation, its picture or
    its sha256 (it cannot be joined to the log, so it is a failure, never skipped)."""
    kept, unread = {}, []
    for done in sorted(DAY12.rglob('result.json')):
        rec = _json(done)
        picture = rec['picture'] if 'picture' in rec else rec.get('sketch')
        if not ('reservation_id' in rec and 'output_sha256' in rec and isinstance(picture, str)):
            unread.append('%s does not say its reservation, its picture and its sha256' % done.relative_to(ig.REPO))
            continue
        kept[rec['reservation_id']] = (picture, rec['output_sha256'], done.parent)
    return kept, unread


def _requests(kept):
    """The request each kept picture was made from (``request.json`` beside it: its inputs and its mask), by
    reservation id; None where there is none."""
    return {i: (_json(folder / 'request.json') if (folder / 'request.json').exists() else None)
            for i, (_picture, _sha256, folder) in kept.items()}


def _set_failures(ledger, rows, kept, requests):
    """A paid call outside the guard, or a logged one the ledger or the folders do not hold, in words. The ledger's
    Day 12 OpenAI ids (each a picture call, settled, filed as its log row is), the log's sent calls and the kept
    pictures are one set; each picture's bytes are the sha256 the log records and lie in its own box's folder; each
    request's inputs are the inputs logged, and a masked edit's mask is one of them, the bytes logged — the log has no
    field of its own for a mask, so this is where it is seen to be listed."""
    out, logged = [], {}
    for r in rows:
        if r.get('outcome') != 'made':
            continue
        if not r['operation'].startswith(IMAGE_OPS):
            out.append('log row %s is not filed under %s' % (r['operation'], IMAGE_OPS))
        result = r['result'] if isinstance(r.get('result'), dict) else {}
        if 'reservation_id' not in result:
            out.append('log row %s carries no reservation' % r['operation'])
            continue
        logged[result['reservation_id']] = r
    for i, (op, state) in sorted(ledger.items()):
        if not op.startswith(IMAGE_OPS):
            out.append('ledger %s (%s) is an OpenAI call outside %s' % (i, op, IMAGE_OPS))
        if i not in logged:
            out.append('ledger %s (%s) has no log row' % (i, op))
        elif logged[i]['operation'] != op:
            out.append('ledger %s is filed as %s, its log row as %s' % (i, op, logged[i]['operation']))
        if state != 'usage_recorded':
            out.append('ledger %s is %s' % (i, state))
    for i, r in logged.items():
        if i not in ledger:
            out.append('log %s (%s) has no ledger row' % (i, r['operation']))
        if i not in kept:
            out.append('log %s (%s) has no kept picture' % (i, r['operation']))
    for i, (picture, sha, _folder) in sorted(kept.items()):
        if i not in logged:
            out.append('kept picture %s has no log row' % picture)
            continue
        r = logged[i]
        if not (r['result']['output_sha256'] == sha == _sha(ig.REPO / picture)):
            out.append('%s: the picture is not the bytes the log records' % picture)
        box = DAY12 / _box(r['operation'])
        if not _under(ig.REPO / picture, box):
            out.append('kept picture %s is not in its box\'s folder %s' % (picture, box.relative_to(ig.REPO)))
        request = requests.get(i)
        if request is None:
            out.append('%s has no request beside it' % picture)
            continue
        sent = [(Path(x['path']).resolve(), x.get('sha256')) for x in r['inputs']]
        if [p for p, _ in sent] != [Path(x['path']).resolve() for x in request['inputs']]:
            out.append('%s: its request\'s inputs are not the inputs logged' % r['operation'])
        if request.get('mask') is not None:
            mask = Path(request['mask']).resolve()
            shas = [s for p, s in sent if p == mask]
            if not shas:
                out.append('the mask of %s (%s) is not among its logged inputs' % (r['operation'], request['mask']))
            elif _sha(mask) != shas[0]:
                out.append('the mask of %s is not the bytes logged' % r['operation'])
    return out


@log_here
@ledger_here
def test_the_log_the_ledger_and_the_kept_pictures_are_one_set_box_by_box(tmp_path):
    """The ledger's Day 12 OpenAI calls, the log's sent rows and the kept pictures are the same calls, one for one —
    read from all three, never counted as a literal: every reservation the log names is a ledger row under
    'day12/images/' (provider openai, its usage recorded), every such row is a logged call, every kept picture's bytes
    hash to the sha256 the log records, each lies in the folder of the box its call is filed under, and every masked
    edit's mask is one of its logged inputs. The listing per box, from the log, is the listing from the folders. The
    controls: a copy of the ledger with one extra id under a real operation, and a request whose mask is not among
    its inputs, each fail by name and alone."""
    ledger, rows = _ledger(LEDGER), _rows(DAY12_CALL_LOG)
    kept, unread = _kept_pictures()
    requests = _requests(kept)
    assert ledger and kept and unread == []
    assert _set_failures(ledger, rows, kept, requests) == []
    # every generation and masked edit listed per box: the log's calls by box are the kept pictures' by box
    made = [r for r in rows if r['outcome'] == 'made']
    by_log = {}
    for r in made:
        by_log.setdefault(_box(r['operation']), set()).add(r['result']['reservation_id'])
    by_folder = {}
    for i, (picture, _sha256, _folder) in kept.items():
        # the deepest box whose folder holds it (a box inside another is its own)
        box = max((b for b in by_log if _under(ig.REPO / picture, DAY12 / b)), key=len, default=None)
        by_folder.setdefault(box, set()).add(i)
    assert by_log == by_folder and set(by_log) == {_box(op) for op, _state in ledger.values()}

    # the control: one id more in a copy of the ledger (made with sqlite's backup, so no page of it is missed)
    planted = tmp_path / 'ledger.sqlite3'
    some, (op, _state) = sorted(ledger.items())[0]
    with closing(sqlite3.connect('file:%s?mode=ro' % LEDGER, uri=True, timeout=30)) as src, \
            closing(sqlite3.connect(str(planted))) as dst:
        src.backup(dst)
        dst.execute("insert into calls select ?, day, provider, operation, model, task_id, reserved, accounted, state, "
                    "artifact, usage, request_hash, started_at, settled_at from calls where id = ?",
                    ('planted-' + some, some))
        dst.commit()
    assert _set_failures(_ledger(planted), rows, kept, requests) == [
        'ledger planted-%s (%s) has no log row' % (some, op)]
    # the control: a masked edit whose mask is a file it did not log
    masked = next(i for i, request in requests.items() if request and request.get('mask'))
    moved = dict(requests, **{masked: dict(requests[masked], mask=str(tmp_path / 'another-mask.png'))})
    op = next(r['operation'] for r in made if r['result']['reservation_id'] == masked)
    assert _set_failures(ledger, rows, kept, moved) == [
        'the mask of %s (%s) is not among its logged inputs' % (op, tmp_path / 'another-mask.png')]


# ======================================================================================================================
# 3. Every input is Day 12's own work: the lid master re-traced, a picked sketch, the call's own sheet, the logo
# ======================================================================================================================

def _picks():
    """Every box's picked sketch: {its folder: (its picture, the sha256 its result records)}, read from each box's
    ``pick.json`` under day-12 (the header's and the balm's) — never a literal."""
    out = {}
    for record in sorted(DAY12.rglob('pick.json')):
        pick = _json(record).get('pick')
        folder = record.parent / pick if isinstance(pick, str) else None
        if folder is not None and (folder / 'result.json').exists():
            result = _json(folder / 'result.json')
            out[folder.resolve()] = ((ig.REPO / result['picture']).resolve(), result['output_sha256'])
    return out


def _input_why(path, sha, mask, box, lid_pin, picks, deny):
    """Why an input of a sent call is not Day 12's own work, in words; None where it is one of the four kinds a Day 12
    call may carry: the approved logo (its path and pinned sha256 together — never ``_is_approved_logo``, which passes
    the Day 9 picks too); the lid master re-traced, by the sha256 its Day 12 record pins; a picked sketch (its picture
    by the sha256 its result records, or a crop of it in its own folder); the call's own sheet — the canvas its box's
    rectangles are drawn on, which is also the masked edit's mask (its request names it), drawn today and no design."""
    path = Path(path).resolve()
    logo, logo_sha = ig.APPROVED_LOGO
    if path == logo.resolve():
        return None if sha == logo_sha else 'the logo\'s path, but not its approved bytes'
    if not _under(path, DAY12):
        return 'not Day 12\'s own work'
    if sha in deny['rejected'] or sha in deny['web']:
        return 'a rejected design or a web picture'
    if path == LID_FLAT.resolve():
        return None if sha == lid_pin else 'the lid master\'s path, but not the bytes its Day 12 record pins'
    for folder, (picture, picture_sha) in picks.items():
        if _under(path, folder):
            if path == picture:
                return None if sha == picture_sha else 'the picked sketch\'s path, but not its bytes'
            return None if path.parent == folder and path.suffix == '.png' else 'inside a picked sketch, not a crop of it'
    # a sketch not picked is refused BEFORE the sheet is read: the mask is named by the request the calling code
    # writes itself, so naming a file as the mask never makes it a sheet
    if 'sketches' in path.relative_to(DAY12.resolve()).parts[:-2]:
        return 'a sketch not picked (a rejected design of today)'
    if mask is not None and path == mask and _under(path, box):
        return None
    return 'a Day 12 file that is none of the logo, the lid master, a picked sketch or the call\'s own sheet'


def _input_failures(rows, requests, lid_pin, picks, deny):
    """(operation, input path, why) for every input of a sent call that is not Day 12's own work (``_input_why``). A
    refused row sent nothing and is not read (``audit`` counts what it named)."""
    out = []
    for r in rows:
        if r.get('outcome') == 'refused':
            continue
        result = r['result'] if isinstance(r.get('result'), dict) else {}
        request = requests.get(result.get('reservation_id')) or {}
        mask = Path(request['mask']).resolve() if request.get('mask') else None
        box = DAY12 / _box(r['operation'])
        for i in r['inputs']:
            why = _input_why(i['path'], i.get('sha256'), mask, box, lid_pin, picks, deny)
            if why is not None:
                out.append((r['operation'], i['path'], why))
    return out


@log_here
def test_every_input_of_every_day12_call_is_day12s_own_work(deny):
    """The guard is rooted for Day 12 (today's log and prefix; day-12 a root a call may draw on, never day-8 to
    day-11), and every input of every sent call is one of four kinds, each by its place AND its bytes: the lid master
    re-traced (the sha256 its Day 12 record pins), a picked sketch (the pick its box's pick.json names), the approved
    logo (its pin alone) — the three the owner named — and a fourth he did not: the call's own sheet, the white canvas
    with its box's rectangles that every sketch was drawn on, which is also the masked edit's mask (named here, never
    folded in silently). Never a file of Day 11's or earlier, never a rejected design. The controls, each a copy of a
    real row carrying one planted input, each failing for its own reason: Day 10's master; Day 11's lid flat, whose
    bytes are the Day 12 flat's own, so it is refused by its place (the check is not bytes alone); Day 9's B-1.3 pick
    by its pinned path and sha256, which ``_is_approved_logo`` passes; a sketch its box did not pick; the lid master's
    path with other bytes. A picked sketch's own picture passes (no Day 12 call has carried one yet, so this is where
    that kind is exercised)."""
    assert ig.CALL_LOG == DAY12_CALL_LOG and ig.TODAY_OPERATION_PREFIX == 'day12/'
    assert DAY12 in ig.ALLOWED_ROOTS
    for day in ('day-8', 'day-9', 'day-10', 'day-11'):
        assert not any(_under(root, ig.REPO / 'docs' / 'audit' / day) for root in ig.ALLOWED_ROOTS), day
    rows = _rows(DAY12_CALL_LOG)
    kept, _unread = _kept_pictures()
    requests = _requests(kept)
    lid_pin = _json(LID12 / 'master.json')['files'][LID_FLAT.name]['sha256']
    picks = _picks()
    sent = [r for r in rows if r.get('outcome') in ('made', 'failed')]
    assert sent and picks
    assert _input_failures(rows, requests, lid_pin, picks, deny) == []

    day10 = ig.REPO / 'docs' / 'audit' / 'day-10' / 'lid' / 'lid-master-flat.png'
    day11 = ig.REPO / 'docs' / 'audit' / 'day-11' / 'zilal' / 'lid' / 'lid-master-flat.png'
    if not (day10.exists() and day11.exists() and ig.APPROVED_ZILAL[0].exists()):
        pytest.skip('Day 10\'s master, Day 11\'s lid flat or Day 9\'s pick (the planted inputs) is not on this machine')
    assert ig._is_approved_logo({'path': str(ig.APPROVED_ZILAL[0]), 'sha256': ig.APPROVED_ZILAL[1]})
    base = [r for r in rows if r['outcome'] == 'made'][0]

    def planted(path, sha):
        row = copy.deepcopy(base)
        row['inputs'] = [{'role': 'planted', 'path': str(path), 'sha256': sha}]
        return row

    folder, (picture, picture_sha) = sorted(picks.items())[0]
    unpicked = next(f / 'picture.png' for f in sorted(folder.parent.iterdir())
                    if f.is_dir() and f.resolve() != folder and (f / 'picture.png').exists())
    for path, sha, why in (
            (day10, _sha(day10), 'not Day 12\'s own work'),
            (day11, _sha(day11), 'not Day 12\'s own work'),
            (ig.APPROVED_ZILAL[0], ig.APPROVED_ZILAL[1], 'not Day 12\'s own work'),
            (unpicked, _sha(unpicked), 'a sketch not picked (a rejected design of today)'),
            (LID_FLAT, '0' * 64, 'the lid master\'s path, but not the bytes its Day 12 record pins')):
        assert [w for _op, _path, w in _input_failures([planted(path, sha)], requests, lid_pin, picks, deny)] == [
            why], path
    assert _input_failures([planted(picture, picture_sha)], requests, lid_pin, picks, deny) == []
    # the control for the sheet's own kind: a call of the unpicked sketch's own box whose request names that sketch
    # as its mask, and sends it — still a sketch not picked (a request naming a mask never makes it a sheet)
    same_box = next(r for r in rows if r['outcome'] == 'made' and _under(unpicked, DAY12 / _box(r['operation'])))
    rid = same_box['result']['reservation_id']
    masked = dict(requests, **{rid: dict(requests[rid], mask=str(unpicked))})
    row = dict(copy.deepcopy(same_box), inputs=[{'role': 'planted', 'path': str(unpicked), 'sha256': _sha(unpicked)}])
    assert [w for _op, _path, w in _input_failures([row], masked, lid_pin, picks, deny)] == [
        'a sketch not picked (a rejected design of today)']


# ======================================================================================================================
# 4. The pages serve pinned bytes (master_tasks.publish into the test media, the files door)
# ======================================================================================================================

@pytest.fixture
def local_media(settings, tmp_path, monkeypatch):
    """Every copy, drawing and view under tmp_path, never the owner's media; the new test tasks never the owner's
    folded task numbers."""
    settings.MEDIA_ROOT = str(tmp_path / 'media')
    monkeypatch.setattr('apps.dashboard.board.OWNER_FOLD', {})
    return Path(settings.MEDIA_ROOT)


@pytest.fixture
def owner(db, client):
    from django.contrib.auth.models import Group, User

    from apps.core.models import Brand
    user = User.objects.create_superuser('day12-owner', password='test-only')
    Brand.objects.create(name='BBROSE', master_brief='the house brief')
    reviewer = User.objects.create_user('day12-reviewer', email='reviewer@example.invalid')
    reviewer.groups.add(Group.objects.get_or_create(name='Reviewer')[0])
    client.force_login(user)
    return user


def _no_paid_call():
    """Not one row in the test database's cost ledger, whichever task it would name: no image, model or search call
    was made."""
    from apps.pipeline.models import ApiCallRecord
    assert not ApiCallRecord.objects.exists(), list(ApiCallRecord.objects.values_list('provider', 'operation'))


@pytest.mark.parametrize('name', PAGE_NAMES)
def test_each_day12_page_serves_its_pinned_bytes(name, local_media, owner, client):
    """Each Day 12 page manifest published as the app publishes it (``master_tasks.publish``) into the test media with
    the test database: ``checked`` holds (every copy re-hashed equal to its pin), every pinned copy is served at the
    files door (outside ``dielines/hybrid``, which ``serve_media`` refuses first, and ``door_refusal`` None), the task
    stands at Gate 2 with the manifest's design target, its one Download — the status API's — is the primary
    surface's own layered .ai (by the source its pin names, as a file named twice is copied where it was first named),
    and no ledger row appears. The controls: a planted ledger row fails the no-paid-call check, and one byte of the
    smallest copy flipped in place (its size kept, so the check is seen to read bytes) makes ``checked`` raise
    ``Changed`` naming that copy."""
    from apps.core.views import door_refusal
    from apps.pipeline.models import ApiCallRecord, DesignTask, PackagingOutput

    path = PAGES / ('%s.json' % name)
    if not path.exists():
        pytest.skip('docs/audit/day-12/pages/%s.json is not here (its page is not made yet)' % name)
    manifest = _json(path)
    slug = manifest['slug']
    made = mt.publish(manifest)
    record = mt.checked(slug)
    assert record['task_id'] == made['task_id'] and record['output_id'] == made['output_id']

    media = local_media.resolve()
    hybrid = media / 'dielines' / 'hybrid'
    refused = {}
    for rel in record['files']:
        target = (media / rel).resolve()
        assert target.is_file() and target.is_relative_to(media) and not target.is_relative_to(hybrid), rel
        why = door_refusal(target, media)
        if why is not None:
            refused[rel] = why
    assert refused == {}

    task = DesignTask.objects.get(pk=made['task_id'])
    assert (task.status, task.design_target) == (mt.AWAITING, manifest['target'])
    native = PackagingOutput.objects.get(pk=made['output_id']).spec_sheet['native_ai/1.0']['path']
    primary = next(s for s in manifest['surfaces'] if s['key'] == manifest['primary'])
    assert native.endswith('.ai') and record['files'][native]['source'] == primary['layered']
    status = client.get('/api/tasks/%d/status/' % task.pk)
    assert status.status_code == 200
    assert status.json()['packaging_output']['native_ai_url'] == '/files/' + native

    _no_paid_call()
    ApiCallRecord.objects.create(provider='openai', model='planted-control', operation='control')
    with pytest.raises(AssertionError):
        _no_paid_call()

    rel = min(record['files'], key=lambda r: ((media / r).stat().st_size, r))
    copied = media / rel
    data = bytearray(copied.read_bytes())
    data[-1] ^= 0xFF
    copied.write_bytes(bytes(data))
    with pytest.raises(mt.Changed, match=re.escape('%s changed since it was published' % rel)):
        mt.checked(slug)
