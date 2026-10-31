"""Day 11 §9 — Ẓilāl's lid master and object so far (D-D11-1 … D-D11-4, D-D11-7's sketch round), and the image guard
re-rooted for Day 11.

Every check here is written as a small function that returns what fails; each runs on the day's real record (nothing
fails) and on a planted copy with one thing changed (that thing fails) — a check that cannot fail proves nothing.
The measuring functions are run on small synthetic arrays and, where it is cheap, again on the committed pictures
(the record's numbers re-measured, never read as literals). Nothing here pays: no function that takes a client is
called, the eye gate's own rule is exercised with a stand-in call, and the shared denylist cache is never written
(a private copy is read). Nothing is written under docs/audit (every output goes to tmp_path)."""
import copy
import hashlib
import inspect
import json
import re
import shutil
import sqlite3
import textwrap
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from apps.pipeline.services import image_guard as ig
from apps.pipeline.services import jury
from apps.pipeline.services import lid_master as lm
from apps.pipeline.services import zilal_lipstick as zl
from apps.pipeline.services import zilal_master as zm
from apps.pipeline.services import zilal_object as zo

DAY11 = zm.DAY11
LID = zm.OUT
SIDES = zo.SIDES
INSIDE = zo.INSIDE / 'master'
TRAY = zo.TRAY / 'master'
LEDGER = ig.ROOT / 'var' / 'rescue_spend' / 'ledger.sqlite3'
#: the image calls of Ẓilāl and the lipstick (Golden Hour's D-D11-5 calls are its own and may land mid-run)
ZILAL_OPS = ('day11/images/zilal/', 'day11/images/lipstick/')

lid_records = pytest.mark.skipif(not (LID / 'master.json').exists(), reason='the Day 11 lid records are not here')
sides_records = pytest.mark.skipif(not (SIDES / 'continuity.json').exists(), reason='the sides records are not here')
inside_records = pytest.mark.skipif(not (INSIDE / 'inside-lid.json').exists(), reason='the inside lid is not here')
tray_records = pytest.mark.skipif(not (TRAY / 'tray.json').exists(), reason='the tray records are not here')
#: [Day 12] the guard moved on to Day 12's log under 'day12/': Day 11's log is closed and kept, read here by its own path
#: and audited under Day 11's own prefix (as test_day10_master reads Day 10's)
DAY11_CALL_LOG = ig.REPO / 'docs' / 'audit' / 'day-11' / 'image-calls.jsonl'
log_here = pytest.mark.skipif(not DAY11_CALL_LOG.exists(), reason='the Day 11 call log is not here')


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


def _changed_byte_copy(src, dest):
    """A copy of ``src`` with one byte changed (the last), so its sha256 is not the pinned one."""
    data = bytearray(Path(src).read_bytes())
    data[-1] ^= 0xFF
    Path(dest).write_bytes(bytes(data))
    return Path(dest)


# ======================================================================================================================
# The image guard's Day 11 settings, its refusals and the call log (D-D11-1, D-D11 §8; D-D8-2, D-D8-7, D-D8-10)
# ======================================================================================================================

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


def _decisions_pin(text):
    """D-D11-1's pinned pick as the owner typed it: (the path, the sha256), read from CURRENT_DECISIONS.md's Day 11
    section — never a literal in this file."""
    section = text.split('## Day 11 — owner decisions', 1)[1]
    found = re.search(r'\*\*D-D11-1 —.*?`([^`]+?lid\.png)`.*?sha256 `([0-9a-f]{64})`', section, re.S)
    return found.group(1), found.group(2)


def _pin_failures(text, pinned_path, pinned_sha):
    """Where the guard's pin of Ẓilāl differs from D-D11-1, or the file's bytes from the pin."""
    path, sha = _decisions_pin(text)
    out = []
    if Path(pinned_path).resolve() != (ig.REPO / path).resolve():
        out.append('path: the guard pins %s, D-D11-1 names %s' % (pinned_path, path))
    if pinned_sha != sha:
        out.append('sha256: the guard pins %s, D-D11-1 names %s' % (pinned_sha, sha))
    if Path(pinned_path).exists() and _sha(pinned_path) != pinned_sha:
        out.append('bytes: the file on disk is not the pinned sha256')
    return out


def test_the_guard_is_rooted_for_day11():
    """Day 11's own log under day-11 and the 'day11/' operations its paid pictures are filed under; the roots a call
    may draw on hold today's work and the house library, never Day 10's (Golden Hour, test one) nor Day 9's or Day 8's
    rejected designs; Ẓilāl's pick pinned by the path and sha256 D-D11-1 typed."""
    # [Day 12] the guard moved on: today's log under day-12 and 'day12/', Day 11's own log closed and kept (its rows are
    # read below by its path), day-11 no longer a root a call may draw on — as day-10 was not on Day 11
    assert DAY11_CALL_LOG.exists() and ig.CALL_LOG == ig.REPO / 'docs' / 'audit' / 'day-12' / 'image-calls.jsonl'
    assert ig.TODAY_OPERATION_PREFIX == 'day12/'
    assert ig.REPO / 'docs' / 'audit' / 'day-12' in ig.ALLOWED_ROOTS
    for day in ('day-8', 'day-9', 'day-10', 'day-11'):
        assert not any(_under(r, ig.REPO / 'docs' / 'audit' / day) for r in ig.ALLOWED_ROOTS), day
    assert ig.REPO / 'docs' / 'audit' / 'day-9' in ig.REJECTED_ROOTS
    assert ig.APPROVED_ZILAL in ig.APPROVED_PICKS and ig.APPROVED_PICK in ig.APPROVED_PICKS
    assert (zm.PICK, zm.PICK_SHA256) == ig.APPROVED_ZILAL
    decisions = (ig.REPO / 'CURRENT_DECISIONS.md').read_text(encoding='utf-8')
    assert _pin_failures(decisions, *ig.APPROVED_ZILAL) == []
    # control: a decisions text whose pin differs by one digit is caught
    _, sha = _decisions_pin(decisions)
    planted = decisions.replace(sha, sha[:-1] + ('0' if sha[-1] != '0' else '1'))
    assert any(f.startswith('sha256') for f in _pin_failures(planted, *ig.APPROVED_ZILAL))


def test_the_guard_takes_zilals_pick_only_as_itself(tmp_path, settings, deny):
    """The pick sits under Day 9's rejected root and is allowed by its path AND sha256 together: the same bytes
    elsewhere are a rejected design (D-D8-2), and with its pinned sha changed the real file is refused too."""
    settings.IMAGE_MODEL = 'gpt-image-2'
    path, sha = ig.APPROVED_ZILAL
    if not path.exists():
        pytest.skip('the pick is not on this machine')
    assert sha in deny['rejected']                         # it is a Day 9 picture: only the pin lets it through
    checked = ig.check([{'role': 'the owner\'s pick', 'path': path}], 'flat lid artwork', deny=deny)
    assert checked[0]['sha256'] == sha
    copy_ = tmp_path / 'lid.png'
    shutil.copyfile(path, copy_)
    with pytest.raises(ig.ImageCallRefused, match='D-D8-2'):
        ig.check([{'role': 'a copy of the pick', 'path': copy_}], 'flat lid artwork', deny=deny)
    with pytest.MonkeyPatch.context() as mp:                   # control: the pin decides
        mp.setattr(ig, 'APPROVED_PICKS', (ig.APPROVED_PICK, (path, '0' * 64)))
        with pytest.raises(ig.ImageCallRefused, match='D-D8-2'):
            ig.check([{'role': 'the owner\'s pick', 'path': path}], 'flat lid artwork', deny=deny)


def test_the_guard_refuses_a_rejected_design_a_web_picture_and_day10s_work(tmp_path, settings, deny):
    """Each refusal by its own reason (a bare raise would pass on a missing file): Day 9's B-1.3 BUILD is a rejected
    design (D-D11 §8: "Day 9's builds included"); a web picture is research only, by its root and, copied anywhere, by
    its sha256; Golden Hour's Day 10 master is outside the roots a Day 11 call draws on; a competitor in the prompt, a
    provider or a model other than the house's are refused before the inputs are read."""
    settings.IMAGE_MODEL = 'gpt-image-2'
    build = ig.REPO / 'docs' / 'audit' / 'day-9' / 'concepts' / 'B-1.3' / 'truthful.png'
    # a web picture whose bytes are only the web's (the Codex snapshot holds copies of some under a rejected root,
    # which D-D8-2 refuses first)
    web = [Path(p) for s, p in sorted(deny['web'].items()) if s not in deny['rejected'] and Path(p).exists()]
    day10 = ig.REPO / 'docs' / 'audit' / 'day-10' / 'lid' / 'lid-master-flat.png'
    if not (build.exists() and web and day10.exists()):
        pytest.skip('the Day 9 build, the web quarantine or Day 10\'s master is not on this machine')
    with pytest.raises(ig.ImageCallRefused, match='D-D8-2'):
        ig.check([{'role': 'Day 9\'s B-1.3 build', 'path': build}], 'flat lid artwork', deny=deny)
    with pytest.raises(ig.ImageCallRefused, match='D-D8-7.*web picture'):
        ig.check([{'role': 'a trend board thumb', 'path': web[0]}], 'flat lid artwork', deny=deny)
    with pytest.raises(ig.ImageCallRefused, match='outside the roots'):
        ig.check([{'role': 'Golden Hour\'s Day 10 master', 'path': day10}], 'flat lid artwork', deny=deny)
    with pytest.raises(ig.ImageCallRefused, match='competitor brand'):
        ig.check([], 'a lid in the manner of Huda Beauty', deny=deny)
    with pytest.raises(ig.ImageCallRefused, match='D-D8-10'):
        ig.check([], 'flat lid artwork', provider='google', deny=deny)
    # the web picture copied into a root a call may draw on is still refused, by its bytes
    allowed = tmp_path / 'allowed'
    allowed.mkdir()
    shutil.copyfile(web[0], allowed / 'renamed.png')
    plain = allowed / 'plain.png'
    Image.new('RGB', (8, 8), (12, 30, 70)).save(plain)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ig, 'ALLOWED_ROOTS', ig.ALLOWED_ROOTS + (allowed,))
        assert ig.check([{'role': 'a plain picture', 'path': plain}], 'flat lid artwork', deny=deny)  # control: passes
        with pytest.raises(ig.ImageCallRefused, match='D-D8-7.*web picture'):
            ig.check([{'role': 'a renamed web picture', 'path': allowed / 'renamed.png'}], 'flat lid artwork', deny=deny)


#: what ``guarded_call`` writes on every row, made, failed or refused
GUARD_KEYS = ('operation', 'provider', 'model', 'outcome', 'inputs', 'prompt_sha256', 'prompt', 'quality', 'size', 'at')


def _guard_shape_failures(rows, model):
    """The rows that do not read as written by ``guarded_call``: a field of its own missing, a prompt whose sha256 is
    not the recorded one, an outcome it never writes, an operation outside today's, a sent call without its reservation
    and output, an input without its role, path and sha256."""
    out = []
    for n, r in enumerate(rows):
        missing = [k for k in GUARD_KEYS if k not in r]
        if missing:
            out.append((n, 'missing %s' % missing))
            continue
        if hashlib.sha256(r['prompt'].encode()).hexdigest() != r['prompt_sha256']:
            out.append((n, 'the prompt is not the one its sha256 records'))
        if r['outcome'] not in ig.OUTCOMES:
            out.append((n, 'outcome %r' % r['outcome']))
        if not r['operation'].startswith(ig.TODAY_OPERATION_PREFIX):
            out.append((n, 'operation %s is not today\'s' % r['operation']))
        if (r['provider'], r['model']) != ('openai', model):
            out.append((n, 'provider/model %s/%s' % (r['provider'], r['model'])))
        try:
            datetime.fromisoformat(r['at'])
        except (TypeError, ValueError):
            out.append((n, 'at %r' % r['at']))
        if r['outcome'] == 'made':
            result = r['result'] if isinstance(r.get('result'), dict) else {}
            if not ('reservation_id' in result and 'output_sha256' in result):
                out.append((n, 'a made call without its reservation and output'))
            if any(not {'role', 'path', 'sha256'} <= set(i) for i in r['inputs']):
                out.append((n, 'an input without its role, path and sha256'))
    return out


def _root_failures(rows):
    """D-D11 §8 after the fact (``audit`` reads sha256s only, never the roots): every input of a sent call is the
    approved logo or one of the owner's picks by its path AND sha256, or a file of today's under docs/audit/day-11; a
    Ẓilāl or lipstick call never carries Golden Hour's pick, nor any of Golden Hour's own Day 11 files."""
    day11 = ig.REPO / 'docs' / 'audit' / 'day-11'
    golden = day11 / 'golden-hour'
    out = []
    for r in rows:
        if r['outcome'] == 'refused':
            continue
        zilal = r['operation'].startswith(ZILAL_OPS)
        for i in r['inputs']:
            pinned = ig._is_approved_logo(i)
            if not pinned and not _under(i['path'], day11):
                out.append((r['operation'], i['path'], 'outside the approved files and day-11'))
            if zilal and (Path(i['path']).resolve() == ig.APPROVED_PICK[0].resolve() or _under(i['path'], golden)):
                out.append((r['operation'], i['path'], 'a Golden Hour picture in a Ẓilāl call'))
    return out


@log_here
def test_every_line_of_the_day11_log_was_written_by_the_guard_and_draws_only_on_the_allowed_files(monkeypatch):
    """Every row has the guard's own fields, its prompt is the one its sha256 records, and every input is the logo or
    a pick by path and sha256, or a day-11 file; no Ẓilāl call carries Golden Hour. Controls: a prompt changed under
    its sha256, a row without its time, a Day 10 input and Golden Hour's pick in a Ẓilāl call are each caught."""
    from django.conf import settings as dj
    monkeypatch.setattr(ig, 'TODAY_OPERATION_PREFIX', 'day11/')       # [Day 12] Day 11's log under Day 11's prefix
    rows = _rows(DAY11_CALL_LOG)
    assert rows
    assert _guard_shape_failures(rows, dj.IMAGE_MODEL) == []
    assert _root_failures(rows) == []
    made = [r for r in rows if r['outcome'] == 'made']
    row = copy.deepcopy(made[0])
    row['prompt'] += ' and a little more'
    no_time = {k: v for k, v in made[0].items() if k != 'at'}
    assert [w for _, w in _guard_shape_failures([row, no_time], dj.IMAGE_MODEL)] == [
        'the prompt is not the one its sha256 records', 'missing [\'at\']']
    day10 = ig.REPO / 'docs' / 'audit' / 'day-10' / 'lid' / 'lid-master-flat.png'
    planted = copy.deepcopy([r for r in made if r['operation'].startswith(ZILAL_OPS)][0])
    planted['inputs'] = [{'role': 'Golden Hour\'s Day 10 master', 'path': str(day10), 'sha256': '0' * 64},
                         {'role': 'Golden Hour\'s pick', 'path': str(ig.APPROVED_PICK[0]), 'sha256': ig.APPROVED_PICK[1]}]
    whys = [w for _, _, w in _root_failures([planted])]
    assert whys == ['outside the approved files and day-11', 'a Golden Hour picture in a Ẓilāl call']


@log_here
def test_the_day11_log_audits_clean_and_each_planted_row_moves_its_own_count(tmp_path, monkeypatch, deny):
    """``image_guard.audit`` on Day 11's log (the denylist read from the private copy, never rewritten here): it holds,
    every count of a fault 0. Each planted row — a copy of a real one with one field changed — moves exactly its own
    count from 0 to 1: a rejected design's sha256 as an input, a competitor in the prompt, another provider."""
    monkeypatch.setattr(ig, 'denylist', lambda **kw: deny)
    monkeypatch.setattr(ig, 'TODAY_OPERATION_PREFIX', 'day11/')       # [Day 12] Day 11's log under Day 11's prefix
    rows = _rows(DAY11_CALL_LOG)
    audit = ig.audit(DAY11_CALL_LOG)
    faults = ('non_openai_or_named_tool', 'rejected_or_web_inputs', 'competitor_prompts', 'sent_without_input_sha256',
              'sent_without_prompt', 'unknown_outcome')
    assert audit['holds'] and audit['log_present'] and not audit['log_empty'], audit
    assert audit['calls'] == len(rows) and audit['sent'] == len([r for r in rows if r['outcome'] in ('made', 'failed')])
    assert all(audit[k] == 0 for k in faults), audit
    build = ig.REPO / 'docs' / 'audit' / 'day-9' / 'concepts' / 'B-1.3' / 'truthful.png'
    base = [r for r in rows if r['outcome'] == 'made'][0]
    rejected = copy.deepcopy(base)
    rejected['inputs'][0] = dict(rejected['inputs'][0], path=str(build), sha256=_sha(build))
    competitor = dict(copy.deepcopy(base), prompt=base['prompt'] + ' As Charlotte Tilbury would.')
    provider = dict(copy.deepcopy(base), provider='google')
    for planted, count in ((rejected, 'rejected_or_web_inputs'), (competitor, 'competitor_prompts'),
                           (provider, 'non_openai_or_named_tool')):
        log = tmp_path / ('%s.jsonl' % count)
        log.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows + [planted]) + '\n', encoding='utf-8')
        found = ig.audit(log)
        assert not found['holds'] and found[count] == 1, (count, found)
        assert all(found[k] == 0 for k in faults if k != count), (count, found)


def _ledger_ids(prefixes):
    """The spend ledger's OpenAI calls under ``prefixes`` (read only): {id: (operation, state)}."""
    with closing(sqlite3.connect('file:%s?mode=ro' % LEDGER, uri=True, timeout=30)) as db:
        rows = db.execute("select id, operation, state from calls where provider = 'openai'").fetchall()
    return {i: (op, state) for i, op, state in rows if op.startswith(prefixes)}


def _paid_pictures():
    """Every paid picture Ẓilāl's and the lipstick's code kept: each ``result.json`` under day-11 (its reservation, the
    picture and its sha256)."""
    out = {}
    for root in (DAY11 / 'zilal', DAY11 / 'lipstick'):
        for done in sorted(root.rglob('result.json')):
            rec = _json(done)
            picture = rec['picture'] if 'picture' in rec else rec['sketch']     # the refinements keep it as 'sketch'
            out[rec['reservation_id']] = (picture, rec['output_sha256'])
    return out


def _bijection_failures(ledger, rows, pictures):
    """A paid call outside the guard, or a logged one the ledger or the folders do not hold: the ledger's ids, the
    log's sent calls and the kept pictures are one set, each picture's bytes the sha256 the log records."""
    logged = {r['result']['reservation_id']: r for r in rows
              if r['outcome'] == 'made' and r['operation'].startswith(ZILAL_OPS)}
    out = ['ledger %s (%s) has no log row' % (i, op) for i, (op, _) in ledger.items() if i not in logged]
    out += ['log %s has no ledger row' % i for i in logged if i not in ledger]
    out += ['ledger %s is %s' % (i, state) for i, (_, state) in ledger.items() if state != 'usage_recorded']
    out += ['log %s has no kept picture' % i for i in logged if i not in pictures]
    out += ['kept picture %s has no log row' % p for i, (p, _) in pictures.items() if i not in logged]
    for i, (picture, sha) in pictures.items():
        if i in logged and not (logged[i]['result']['output_sha256'] == sha == _sha(ig.REPO / picture)):
            out.append('%s: the picture is not the bytes the log records' % picture)
    return out


@log_here
@pytest.mark.skipif(not LEDGER.exists(), reason='the spend ledger is not here')
def test_every_paid_zilal_and_lipstick_picture_went_through_the_guard():
    """The ledger's OpenAI calls under Ẓilāl's and the lipstick's operations, the log's sent rows and the kept
    pictures are the same calls, one for one (read from all three, never counted as a literal). Control: the log
    with one row dropped no longer matches."""
    ledger, rows, pictures = _ledger_ids(ZILAL_OPS), _rows(DAY11_CALL_LOG), _paid_pictures()
    assert ledger and _bijection_failures(ledger, rows, pictures) == []
    sent = [r for r in rows if r['outcome'] == 'made' and r['operation'].startswith(ZILAL_OPS)]
    dropped = [r for r in rows if r is not sent[-1]]
    assert _bijection_failures(ledger, dropped, pictures) == [
        'ledger %s (%s) has no log row' % (sent[-1]['result']['reservation_id'], sent[-1]['operation']),
        'kept picture %s has no log row' % pictures[sent[-1]['result']['reservation_id']][0]]


@log_here
@pytest.mark.skipif(not LEDGER.exists(), reason='the spend ledger is not here')
def test_todays_paid_pictures_are_the_day11_operations_only(monkeypatch):
    """The guard's exemption of today's own paid pictures reads the ledger under 'day11/': it holds every Day 11 image
    call's reservation and none of Day 10's (Golden Hour's pictures are not today's work). Control: under Day 10's
    prefix the Day 11 reservations are no longer today's."""
    responses = ig.ROOT / 'var' / 'rescue_spend' / 'responses'
    monkeypatch.setattr(ig, 'TODAY_OPERATION_PREFIX', 'day11/')       # [Day 12] Day 11's day read under its own prefix
    day11 = {r['result']['reservation_id'] for r in _rows(DAY11_CALL_LOG) if r['outcome'] == 'made'}
    day10 = set(_ledger_ids(('day10/',)))
    today = ig._todays_responses(responses)
    assert day11 <= today and not (day10 & today)
    monkeypatch.setattr(ig, 'TODAY_OPERATION_PREFIX', 'day10/')
    assert not (day11 & ig._todays_responses(responses))


# ======================================================================================================================
# zilal_master: the pick pinned, the safe area, the lid's records (D-D11-1 … D-D11-3)
# ======================================================================================================================

@lid_records
def test_the_pick_and_the_refined_pick_are_refused_on_a_changed_byte(tmp_path, monkeypatch):
    """``load_pick`` reads B-1.3 only as the owner's bytes (D-D11-1) and ``load_master_pick`` R3 only as the round
    recorded it (refine/pick.json); each refuses a copy with one byte changed. The round's pick is computed from its
    ranking (J1's first of the four, the original included), never read from pick.json alone."""
    assert zm.load_pick().shape == (zm.PICK_PX[1], zm.PICK_PX[0], 3)
    assert zm.load_master_pick().shape[2] == 3
    pick = _json(zm.REFINE / 'pick.json')
    ranking = _json(zm.REFINE / 'ranking.json')
    first = min(ranking['payload']['ranking'], key=lambda r: r['rank'])
    shown = ranking['sketches'][first['sketch'] - 1]
    assert (Path(shown['path']).resolve(), shown['sha256']) == ((ig.REPO / pick['lid']).resolve(), pick['lid_sha256'])
    assert (pick['refined_from']['path'], pick['refined_from']['sha256']) == (
        lm.rel(ig.APPROVED_ZILAL[0]), ig.APPROVED_ZILAL[1])
    monkeypatch.setattr(zm, 'PICK', _changed_byte_copy(zm.PICK, tmp_path / 'B-1.3.png'))
    with pytest.raises(ValueError, match='not the owner'):
        zm.load_pick()
    monkeypatch.setattr(zm, 'MASTER_PICK', _changed_byte_copy(zm.MASTER_PICK, tmp_path / 'R3.png'))
    with pytest.raises(ValueError, match='not the pick'):
        zm.load_master_pick()


def _inside_safe(box, w, h):
    return box[0] >= zm.SAFE_MM and box[1] >= zm.SAFE_MM and box[2] <= w - zm.SAFE_MM and box[3] <= h - zm.SAFE_MM


def test_safe_moves_moves_a_line_inside_4_mm_by_the_least_amount_and_a_row_together(monkeypatch):
    """D-D10-2.6 (D-D11-3.7): a line 1 mm inside the margin moves in by 1 mm and the 2 µm margin, no more; a line clear
    of it does not move; the bottom row's two lines take the row's one move (the larger), a line of the row that was
    clear moves with it (dx 0.0). Control: with the row rule taken away the two lines no longer share a baseline."""
    w, h = zm.LID_MM
    lines = {'eyeshadow': (3.0, 100.0, 50.0, 104.0), 'baliyt': (150.0, 20.0, 170.0, 26.0),
             'shades': (110.0, 110.0, 130.0, 115.0), 'net': (150.0, 111.0, 180.0, 118.0)}
    logo = (140.0, 4.5, 185.0, 12.0)
    moves = zm.safe_moves(lines, logo)
    assert set(moves) == {'eyeshadow', 'shades', 'net'}
    assert moves['eyeshadow'] == (1.002, 0.0)
    moved = zm.moved_box(lines['eyeshadow'], moves['eyeshadow'])
    assert _inside_safe(moved, w, h) and moved[0] - zm.SAFE_MM <= 0.003          # inside, by the least amount
    assert not _inside_safe(zm.moved_box(lines['eyeshadow'], (1.002 - 0.01, 0.0)), w, h)
    assert moves['net'] == (0.0, -2.002) and moves['shades'] == (0.0, -2.002)
    assert all(_inside_safe(zm.moved_box(lines[k], moves[k]), w, h) for k in ('shades', 'net'))
    monkeypatch.setattr(zm, 'ROWS', {})
    apart = zm.safe_moves(lines, logo)
    assert 'shades' not in apart and apart['net'] == (0.0, -2.002)


def test_safe_moves_carries_no_numeric_else():
    """The services ban (test_palette_statistics' enforcing detector) on ``safe_moves`` itself: its row step keeps
    dx 0.0 by an if, never ``moves[k][0] if k in moves else 0.0``. Control: that form planted in its source is caught."""
    from apps.pipeline.tests.test_palette_statistics import composed_gate
    src = textwrap.dedent(inspect.getsource(zm.safe_moves))
    assert composed_gate(src) == set()
    planted = src.replace('dx = 0.0\n                if k in moves:\n                    dx = moves[k][0]\n',
                          'dx = moves[k][0] if k in moves else 0.0\n')
    assert planted != src
    assert {kind for kind, _ in composed_gate(planted)} >= {'ifexp'}


def _moves_failures(rec):
    """The master's safe-area moves re-derived: each line's and the logo's box before its move (the recorded box less
    the recorded move) through ``safe_moves`` gives the recorded moves, and every box after them is inside 4 mm."""
    w, h = zm.LID_MM
    recorded = {k: (v['dx_mm'], v['dy_mm']) for k, v in rec['moves']['safe_area'].items()}
    before = {}
    for key, box in rec['line_boxes_mm'].items():
        dx, dy = recorded[key] if key in recorded else (0.0, 0.0)
        before[key] = (box[0] - dx, box[1] - dy, box[2] - dx, box[3] - dy)
    logo = before.pop('logo')
    again = zm.safe_moves(before, logo)
    out = ['%s: re-derived %s, recorded %s' % (k, again[k] if k in again else None, recorded[k] if k in recorded else None)
           for k in set(again) | set(recorded)
           if not (k in again and k in recorded and np.allclose(again[k], recorded[k], rtol=0.0, atol=1.5e-3))]
    out += ['%s is not inside the safe area' % k for k, box in rec['line_boxes_mm'].items() if not _inside_safe(box, w, h)]
    return out


@lid_records
def test_the_masters_safe_area_moves_are_what_safe_moves_gives():
    """master.json's moves (18 SHADES and the net line together, the logo) re-derived from its own boxes. Control: the
    bottom row recorded as moved 0.1 mm further than the least (its boxes and its moves changed together, so the record
    stays self-consistent) is caught: from where the row stood, the least move is still the original."""
    rec = _json(LID / 'master.json')
    assert _moves_failures(rec) == []
    planted = copy.deepcopy(rec)
    for key in zm.ROWS['bottom row']:
        planted['moves']['safe_area'][key]['dy_mm'] -= 0.1
        x0, y0, x1, y1 = planted['line_boxes_mm'][key]
        planted['line_boxes_mm'][key] = [x0, y0 - 0.1, x1, y1 - 0.1]
    assert sorted(f.split(':')[0] for f in _moves_failures(planted)) == ['net', 'shades']


def _lid_gate_failures(r0, r1, relook, verdict):
    """D-D11-3.7's verdict recomputed from the rounds, not read: round 0 did not hold (so the one repair was due); after
    repair 1 the gate look names no defect; every crop round 1 called a defect was looked at again on corrected
    evidence and allowed; the parts counted are the pick's; the repairs are one; the spend is the five looks'."""
    out = []
    if r0['answered'] and not r0['defects']:
        out.append('round 0 held: no repair was due')
    gate = [d['where'] for d in r1['gate']['payload']['differences'] if d['verdict'] == 'defect']
    if gate:
        out.append('round 1\'s gate names %s' % gate)
    crops = {zm.EYE_CROP_ORDER[c['image'] - 1] for c in r1['crops']['payload']['crops'] if c['verdict'] == 'defect'}
    relooked = {s['crop'] for s in relook['look_record']['sent']}
    out += ['round 1\'s defect %s was never looked at again' % c for c in sorted(crops - relooked)]
    if relook['look_record']['payload'] is None:
        out.append('the re-look did not answer')
    else:
        out += ['re-look image %d is a %s' % (c['image'], c['verdict'])
                for c in relook['look_record']['payload']['crops'] if c['verdict'] != 'allowed']
    out += ['%s: the pick draws %d parts, the master %d' % (k, v['pick'], v['master'])
            for k, v in relook['parts_counted'].items() if v['pick'] != v['master']]
    repairs = len([r for r in verdict['rounds'] if 'repair' in r])
    if repairs != verdict['verdict']['repairs_used'] or repairs > 1:
        out.append('repairs: %d in the rounds, %d recorded' % (repairs, verdict['verdict']['repairs_used']))
    costs = [r0['gate']['cost_usd'], r0['crops']['cost_usd'], r1['gate']['cost_usd'], r1['crops']['cost_usd'],
             relook['look_record']['cost_usd']]
    if (verdict['spend']['calls'], verdict['spend']['usd']) != (len(costs), round(sum(costs), 4)):
        out.append('spend: recorded %s, the looks %d / %.4f' % (verdict['spend'], len(costs), sum(costs)))
    if verdict['verdict']['holds'] != (not out):
        out.append('the verdict says holds=%s' % verdict['verdict']['holds'])
    return out


@lid_records
def test_the_lid_gate_holds_after_repair_1_and_the_relook():
    """fidelity.json's verdict (holds, one repair, 5 looks) recomputed from fidelity-r0/-r1/-relook. Controls: a defect
    planted in round 1's crops that the re-look never saw (the logo) fails, and so does a sixth look's cost."""
    r0, r1 = _json(LID / 'fidelity-r0.json'), _json(LID / 'fidelity-r1.json')
    relook, verdict = _json(LID / 'fidelity-relook.json'), _json(LID / 'fidelity.json')
    assert verdict['verdict']['holds'] and _lid_gate_failures(r0, r1, relook, verdict) == []
    planted = copy.deepcopy(r1)
    logo = [c for c in planted['crops']['payload']['crops'] if zm.EYE_CROP_ORDER[c['image'] - 1] == 'logo'][0]
    logo['verdict'] = 'defect'
    assert 'round 1\'s defect logo was never looked at again' in _lid_gate_failures(r0, planted, relook, verdict)
    more = copy.deepcopy(verdict)
    more['spend']['usd'] = round(more['spend']['usd'] + 0.1, 4)
    assert any(f.startswith('spend') for f in _lid_gate_failures(r0, r1, relook, more))


def _master_claim_failures(rec, verdict, relook):
    """What the report will say of the hero, read from master.json and held to its own numbers: each ``holds`` the
    rule applied to the numbers beside it (the trace within 0.3 mm and IoU 0.95; against the pick's own edges as
    measured — that one does not hold); the hatch's stroke what ``hatch_stroke`` gives for the recorded fit, inside the
    press limits; the registration's phase the best tried; repair 1's words (89 % / 58 %) the recorded shares; the
    re-look's per-letter shares the verdict's."""
    out = []
    trace = rec['hero']['trace']
    worst = max(trace['trace_to_sketch_max_mm'], trace['sketch_to_trace_max_mm'])
    if trace['holds'] != {'within_0_3_mm': worst <= zm.TRACE_MAX_MM, 'iou_0_95': trace['iou'] >= zm.TRACE_IOU_MIN}:
        out.append('trace holds %s for worst %.4f mm, IoU %.4f' % (trace['holds'], worst, trace['iou']))
    pick_edges = trace['against_the_pick_itself']
    if pick_edges['holds'] != (pick_edges['max_mm'] <= zm.TRACE_MAX_MM):
        out.append('against the pick: holds %s for max %.4f mm' % (pick_edges['holds'], pick_edges['max_mm']))
    hatch = rec['hero']['hatch']
    if zm.hatch_stroke(hatch['fit']) != hatch['stroke']:
        out.append('stroke: recorded %s, hatch_stroke gives %s' % (hatch['stroke'], zm.hatch_stroke(hatch['fit'])))
    if hatch['stroke']['stroke_mm'] < zm.HATCH_STROKE_MIN_MM or hatch['stroke']['gap_mm'] < 0.2:
        out.append('the hatch is outside the press limits: %s' % hatch['stroke'])
    reg = rec['hero']['registration']
    best = max(reg['tried'], key=lambda s: reg['tried'][s])
    if float(best) != reg['phase_sigma_mm']:
        out.append('phase sigma %s recorded, %s landed most' % (reg['phase_sigma_mm'], best))
    words = re.search(r'(\d+) % of the foil on the painted strokes, (\d+) % for straight lines',
                      verdict['rounds'][1]['repair'])
    shares = reg['on_painted_strokes_share']
    said = (int(words.group(1)), int(words.group(2)))
    if said != (round(100 * shares['registered']), round(100 * shares['straight'])):
        out.append('repair 1 says %s %%, master.json holds %s' % (said, shares))
    if verdict['rounds'][2]['per_letter_registration'] != relook['per_letter_registration']:
        out.append('the verdict\'s per-letter shares are not the re-look\'s')
    return out


@lid_records
def test_the_lids_records_hold_what_the_report_will_claim():
    """master.json's trace IoU (≥ 0.95, within 0.3 mm of the sketch's alpha edge), the hatch at the press limits and
    the registration's 89 % (58 % straight) agree with their own rules and with fidelity.json's words. The trace
    against the pick's own edges does NOT hold (max over 0.3 mm) and is recorded so; it is held to that, never
    claimed. Controls: an IoU under 0.95 left 'holding', a registered share moved to 0.80, and a fit whose pitch would
    need coarsening are each caught."""
    rec, verdict, relook = _json(LID / 'master.json'), _json(LID / 'fidelity.json'), _json(LID / 'fidelity-relook.json')
    assert rec['hero']['trace']['iou'] >= zm.TRACE_IOU_MIN
    assert rec['hero']['trace']['against_the_pick_itself']['holds'] is False
    assert _master_claim_failures(rec, verdict, relook) == []
    low = copy.deepcopy(rec)
    low['hero']['trace']['iou'] = 0.94
    assert any(f.startswith('trace holds') for f in _master_claim_failures(low, verdict, relook))
    moved = copy.deepcopy(rec)
    moved['hero']['registration']['on_painted_strokes_share']['registered'] = 0.80
    assert any(f.startswith('repair 1 says') for f in _master_claim_failures(moved, verdict, relook))
    fine = copy.deepcopy(rec)
    fine['hero']['hatch']['fit']['pitch_mm'] = 0.30                  # 0.30 − 0.22 < 0.15: coarsened to 0.37
    assert zm.hatch_stroke(fine['hero']['hatch']['fit'])['coarsened'] == {'from_mm': 0.30, 'to_mm': 0.37}
    assert any(f.startswith('stroke') for f in _master_claim_failures(fine, verdict, relook))


@lid_records
def test_the_lid_jury_record_is_the_stricter_jurors_7_0_on_the_master_of_record():
    """The jury once for the record: ``jury.combine`` on the two jurors' own records gives verdict.json's score (7.0)
    and its capped scores; the candidate and the finish proof it judged are the files on disk. Control: J2's beauty
    moved to 5 no longer gives the recorded score."""
    j1, j2, verdict = _json(LID / 'jury' / 'J1.json'), _json(LID / 'jury' / 'J2.json'), _json(LID / 'jury' / 'verdict.json')
    combined = jury.combine(j1, j2)
    assert combined['verdict']['score'] == verdict['verdict']['score'] == 7.0
    assert combined['capped'] == verdict['capped'] and combined['raw']['stricter_mean'] == 7.0
    assert _sha(verdict['candidate']) == verdict['candidate_sha256'] and _sha(verdict['proof']) == verdict['proof_sha256']
    planted = copy.deepcopy(j2)
    planted['payload']['dimensions']['beauty']['score'] = 5
    assert jury.combine(j1, planted)['verdict']['score'] != verdict['verdict']['score']


# ======================================================================================================================
# zilal_object, the sides (D-D11-4: continuity across each fold, mean ΔE00 ≤ 3, max ≤ 8, over a 1 mm strip)
# ======================================================================================================================

@sides_records
def test_fold_continuity_reads_0_on_the_mirror_canvas_and_fails_on_a_band_shifted_2_mm(tmp_path):
    """The measure on the master's own mirror (``mirror_canvas``: each band the lid's edge reflected) reads 0 on every
    side and holds; each band shifted 2 mm along its fold fails it (the marbling no longer meets itself)."""
    geom = _json(SIDES / 'continuity.json')['geometry']
    k = geom['px_per_mm']
    canvas = zo.mirror_canvas(geom, tmp_path / 'mirror')['array']
    lid = zo.lid_at_canvas(geom)
    bands = zo.bands_of(canvas, geom)
    rows = zo.fold_continuity(bands, lid, k)
    assert all(r['de00_mean'] == 0.0 and r['de00_max'] == 0.0 and r['holds'] for r in rows.values()), rows
    shift = int(round(2.0 * k))
    for side, axis in (('top', 1), ('bottom', 1), ('left', 0), ('right', 0)):
        planted = dict(bands, **{side: np.roll(bands[side], shift, axis=axis)})
        assert not zo.fold_continuity(planted, lid, k)[side]['holds'], side


def _offset_failures(planted_px, offset_px, tolerance_px):
    return [(p, o) for p, o in zip(planted_px, offset_px) if abs(p - o) > tolerance_px]


#: cv2.phaseCorrelate's sub-pixel reading is drawn toward whole pixels: measured on the mirror canvas, a planted
#: 0.4 px reads 0.14 and 0.5 px reads 0.82 (residual up to 0.32 px, 0.045 mm at the canvas's 7.11 px/mm)
REGISTRATION_TOLERANCE_PX = 0.35


@sides_records
def test_register_edit_refuses_noise_and_recovers_a_planted_shift_within_its_bias(tmp_path, monkeypatch):
    """A noise picture gives no lock (its peak under REGISTRATION_MIN_RESPONSE): the edit is returned unmoved and the
    record says so. The master's own canvas moved by a planted shift is locked and read back within 0.35 px a
    side — the estimator's measured bias toward whole pixels, not better (its ``after_px`` re-reads with the same
    estimator, so it is not evidence of a finer registration). Controls: a do-nothing reading of the 1.7 px shift
    is outside the tolerance, and with the lock threshold raised above the shift's own peak the edit is not moved."""
    geom = _json(SIDES / 'continuity.json')['geometry']
    base = zo.mirror_canvas(geom, tmp_path / 'mirror')['array']
    noise = np.random.default_rng(11).integers(0, 256, base.shape, dtype=np.uint8)
    edit, rec = zo.register_edit(noise, geom)
    assert edit is noise and rec['locked'] is False and rec['response'] < zo.REGISTRATION_MIN_RESPONSE
    for planted in ((1.7, 0.6), (0.4, -0.3), (2.5, -1.25)):
        moved = cv2.warpAffine(base, np.float32([[1, 0, planted[0]], [0, 1, planted[1]]]), (base.shape[1], base.shape[0]),
                               flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
        _, rec = zo.register_edit(moved, geom)
        assert rec['locked'] is True
        assert _offset_failures(planted, rec['offset_px'], REGISTRATION_TOLERANCE_PX) == [], (planted, rec)
    assert _offset_failures((1.7, 0.6), (0.0, 0.0), REGISTRATION_TOLERANCE_PX) != []
    monkeypatch.setattr(zo, 'REGISTRATION_MIN_RESPONSE', rec['response'] + 0.01)
    edit, refused = zo.register_edit(moved, geom)
    assert edit is moved and refused['locked'] is False


def _continuity_failures(rec):
    """Each side's ``holds`` is D-D11-4's rule on its own numbers (mean ≤ 3, max ≤ 8), and the record's on all four."""
    sides = rec['continuity']['sides']
    out = ['%s: holds %s for %.3f / %.3f' % (s, r['holds'], r['de00_mean'], r['de00_max']) for s, r in sides.items()
           if r['holds'] != (r['de00_mean'] <= zo.CONTINUITY_MEAN_MAX and r['de00_max'] <= zo.CONTINUITY_MAX)]
    if rec['continuity']['holds'] != all(r['holds'] for r in sides.values()):
        out.append('the record holds %s' % rec['continuity']['holds'])
    return out


def _eye_failures(rec):
    """An eye record's verdict recomputed from its own answer (``surface_look``'s rule: answered, no image a defect,
    no defect named)."""
    p = rec['look']['payload']
    answered = p is not None
    defects, images = (list(p['defects']), [i for i in p['images'] if i['verdict'] == 'defect']) if answered else ([], [])
    computed = bool(answered and not defects and not images)
    out = []
    if (rec['answered'], rec['holds']) != (answered, computed):
        out.append('answered/holds recorded %s, computed %s' % ((rec['answered'], rec['holds']), (answered, computed)))
    if rec['defects'] != defects or rec['image_defects'] != images:
        out.append('the defects are not the answer\'s')
    return out


def _sent_failures(sent):
    """The pictures an eye round was sent are still the bytes it judged (a crop the eye judges must be the thing on
    disk the record names)."""
    return [s['path'] for s in sent if not (ig.REPO / s['path']).exists() or _sha(ig.REPO / s['path']) != s['sha256']]


@sides_records
def test_the_sides_records_say_what_happened(tmp_path):
    """Round 0: the edit locked on the master and its continuity, re-measured here from the paid picture, is the
    record's and fails on every side; repair 1: no lock (its edit redrew the lid), re-measured, fails; both eye rounds
    answered and fail, their pictures the bytes judged; the edge-extension alternative's continuity is recorded as
    unmeasured (None, never True). Controls: a side recorded failing within the limits, a defect planted in an eye
    answer that held, a changed byte in a judged picture and an alternative recorded as holding are each caught."""
    for folder, locked in ((SIDES, True), (SIDES / 'repair1', False)):
        rec = _json(folder / 'continuity.json')
        geom = rec['geometry']
        raw = np.asarray(Image.open(ig.REPO / rec['edit']['picture']).convert('RGB'))
        assert _sha(ig.REPO / rec['edit']['picture']) == rec['edit']['output_sha256']
        edit, registration = zo.register_edit(raw, geom)
        assert registration == rec['registration'] and registration['locked'] is locked
        again = zo.fold_continuity(zo.bands_of(edit, geom), zo.lid_at_canvas(geom), geom['px_per_mm'])
        assert again == rec['continuity']['sides']
        assert _continuity_failures(rec) == [] and rec['continuity']['holds'] is False
        assert all(not r['holds'] for r in again.values())
        assert rec['lid_face_untouched']['holds'] is True
    for eye in (SIDES / 'eye-r0.json', SIDES / 'repair1' / 'eye-r1.json'):
        rec = _json(eye)
        assert _eye_failures(rec) == [] and rec['answered'] and rec['holds'] is False
        assert _sent_failures(rec['look']['sent']) == []
    alt = _json(SIDES / 'alternative-mirror' / 'alternative.json')
    assert alt['continuity']['holds'] is None
    # controls
    planted = copy.deepcopy(_json(SIDES / 'continuity.json'))
    planted['continuity']['sides']['top'].update(de00_mean=1.0, de00_max=2.0)
    assert any(f.startswith('top') for f in _continuity_failures(planted))
    held = copy.deepcopy(_json(INSIDE / 'eye-r0.json')) if (INSIDE / 'eye-r0.json').exists() else None
    if held is not None:
        held['look']['payload']['images'][0]['verdict'] = 'defect'
        assert _eye_failures(held) != []
    judged = _json(SIDES / 'eye-r0.json')['look']['sent'][0]
    changed = _changed_byte_copy(ig.REPO / judged['path'], tmp_path / 'judged.png')
    assert _sent_failures([dict(judged, path=str(changed))]) == [str(changed)]
    assert dict(alt['continuity'], holds=True)['holds'] is not None


def test_the_eye_gate_decides_in_code_and_pays_nothing_here(tmp_path, monkeypatch):
    """``surface_look``'s rule with a stand-in for the paid call: an answer naming no defect holds; one image called a
    defect fails; no answer (payload None) does not hold; a call that refuses before paying writes no record."""
    monkeypatch.setattr(lm, 'rel', lambda p: str(p))
    pics = []
    for n in range(2):
        path = tmp_path / ('pic-%d.png' % n)
        Image.new('RGB', (64, 40), (10 + n, 30, 70)).save(path)
        pics.append((path, 'picture %d' % n))

    def answer(images, defects):
        return lambda op, content, schema: {'payload': {'images': images, 'defects': defects,
                                                        'holds_the_lids_language': True, 'summary': ''}, 'cost_usd': 0.0}
    clean = [{'image': 1, 'verdict': 'holds', 'notes': ''}, {'image': 2, 'verdict': 'holds', 'notes': ''}]
    assert zo.surface_look(tmp_path, 'test', pics, 'rule', answer(clean, []), 0)['holds'] is True
    one = [clean[0], dict(clean[1], verdict='defect')]
    rec = zo.surface_look(tmp_path, 'test', pics, 'rule', answer(one, []), 1)
    assert rec['holds'] is False and rec['image_defects'] == [one[1]] and _eye_failures(rec) == []
    silent = zo.surface_look(tmp_path, 'test', pics, 'rule', lambda *a: {'payload': None, 'cost_usd': 0.0}, 2)
    assert silent['answered'] is False and silent['holds'] is False

    def refusing(*args):
        raise RuntimeError('stand-in: refused before paying')
    with pytest.raises(RuntimeError, match='refused before paying'):
        zo.surface_look(tmp_path, 'test', pics, 'rule', refusing, 3)
    assert not (tmp_path / 'eye-r3.json').exists()


# ======================================================================================================================
# zilal_object, the inside lid (the preservation path: the upscale proved, the bleed outside the trim)
# ======================================================================================================================

def _upscale_failures(rec, proof):
    keys = ('de00_mean', 'de00_max', 'ssim')
    out = ['%s: recorded %s, re-run %s' % (k, rec['upscale'][k], proof[k]) for k in keys if rec['upscale'][k] != proof[k]]
    out += ['%s does not hold' % k for k, v in proof['holds'].items() if not v]
    return out


@inside_records
def test_the_inside_lids_upscale_proof_holds_as_recorded():
    """The inside lid's pick is J1's first of its three (computed from ranking.json), its bytes the record's; the crop
    to the 184 × 114 face upscaled and proved again gives the record's numbers, every bar held (mean ΔE00 < 1, max < 4,
    SSIM > 0.97). Control: the same proof on the round's other sketch (S1, same crop) is not the record's (a crop one
    pixel off is no control: the proof's statistics are nearly translation-invariant, measured equal to 4 decimals)."""
    rec = _json(INSIDE / 'inside-lid.json')
    pick = zo.surface_pick('inside')
    ranking = _json(zo.INSIDE / 'sketches' / 'ranking.json')
    assert pick['sketch'] == min(ranking['payload']['ranking'], key=lambda r: r['rank'])['sketch'] == rec['pick']['sketch']
    assert pick['sha256'] == rec['pick']['sha256']
    src = np.asarray(Image.open(pick['path']).convert('RGB'))
    x0, y0, x1, y1 = rec['crop_px']
    crop = src[y0:y1, x0:x1]
    assert _upscale_failures(rec, lm.prove_upscale(crop, lm.upscale(crop), {})) == []
    other = sorted(r['sketch'] for r in ranking['payload']['ranking'] if r['sketch'] != pick['sketch'])[0]
    off = np.asarray(Image.open(zo.INSIDE / 'sketches' / ('S%d' % other) / 'lid.png').convert('RGB'))[y0:y1, x0:x1]
    assert _upscale_failures(rec, lm.prove_upscale(off, lm.upscale(off), {})) != []


@inside_records
def test_the_inside_lids_bleed_lies_outside_its_trim_and_a_mirror_line_inside_fails(tmp_path):
    """``bleed_outside_trim`` on the real files (the flat rendered from inside-lid.pdf against the plate inside its
    bleed — the upscale itself, its bleed taken off) holds with the record's edges; the same flat with a mirror line
    planted 1.5 mm inside the bottom and the left trim fails."""
    rec = _json(INSIDE / 'inside-lid.json')
    bled = np.asarray(Image.open(INSIDE / 'inside-plate-bleed.png').convert('RGB'))
    b = rec['bleed_px']
    plate = bled[b:-b, b:-b]
    check = zo.bleed_outside_trim(INSIDE / 'inside-lid-flat.png', plate)
    assert check['holds'] and check['edges'] == rec['bleed_outside_trim']['edges']
    flat = np.asarray(Image.open(INSIDE / 'inside-lid-flat.png').convert('RGB')).copy()
    m = int(round(1.5 * 300 / lm.MM_PER_INCH))
    planted = flat.copy()
    planted[-m:] = flat[-2 * m:-m][::-1]
    planted[:, :m] = flat[:, m:2 * m][:, ::-1]
    Image.fromarray(planted).save(tmp_path / 'planted.png')
    failed = zo.bleed_outside_trim(tmp_path / 'planted.png', plate)
    assert not failed['holds'] and failed['edges']['bottom'] > zo.BLEED_EDGE_DE_MAX
    assert failed['edges']['left'] > zo.BLEED_EDGE_DE_MAX


@inside_records
def test_the_inside_lids_eye_round_0_holds_and_its_relook_was_given_the_lid():
    """Round 0 answered with no defect (recomputed), its pictures the bytes judged. D-D11-4 gives the eye the lid as
    the language: round 0 was not sent it (its first picture is the pick), the re-look was (its first picture the
    lid master's flat) and holds too."""
    r0 = _json(INSIDE / 'eye-r0.json')
    assert _eye_failures(r0) == [] and r0['holds'] is True and _sent_failures(r0['look']['sent']) == []
    assert not r0['look']['sent'][0]['path'].endswith('lid-language.png')
    relook = INSIDE / 'eye-relook-with-the-lid.json'
    if relook.exists():
        rec = _json(relook)
        assert rec['look']['sent'][0]['path'].endswith('lid-language.png')
        assert _eye_failures(rec) == [] and rec['holds'] is True


# ======================================================================================================================
# zilal_object, the tray (pans.json, the lift, the names live, the cut page)
# ======================================================================================================================

def _de(hex_a, hex_b):
    return float(lm.delta_e00(zo.hex_lab(hex_a)[None], zo.hex_lab(hex_b)[None])[0])


def _is_teal(hex_):
    """D-D11-4's teal by palette_open's hue rule (CIELAB hue 150–250°, chroma ≥ 10), from the colour that prints."""
    _, a, b = zo.hex_lab(hex_)
    hue = float(np.degrees(np.arctan2(b, a)) % 360)
    return bool(zo.TEAL_HUE[0] <= hue <= zo.TEAL_HUE[1] and np.hypot(a, b) >= zo.TEAL_CHROMA_MIN)


def _pans_failures(rec, names):
    """pans.json held to D-D11-4, every number recomputed per pan from its hex (never the stored hue or ΔE): 18 pans,
    3 × 6, each the brief's name at its place; its printed hex the least lift of its mean (``lift``); ΔE00 ≥ 10 from its
    surround; its teal flag the hue rule's; row 3 at least three teal; the record's lists and flags its pans'."""
    pans = rec['pans']
    out = []
    if sorted((p['row'], p['col']) for p in pans) != [(r, c) for r in (1, 2, 3) for c in range(1, 7)]:
        out.append('the pans are not 3 × 6')
    for p in pans:
        where = '%s (%d, %d)' % (p['name'], p['row'], p['col'])
        if names[p['row'] - 1][p['col'] - 1] != p['name']:
            out.append('%s: the brief names %s here' % (where, names[p['row'] - 1][p['col'] - 1]))
        lifted, step = zo.lift(p['hex_mean'], p['surround'])
        if (lifted, step) != (p['hex'], p['lift_l']):
            out.append('%s: lift gives %s +%.1f, recorded %s +%.1f' % (where, lifted, step, p['hex'], p['lift_l']))
        if _de(p['hex'], p['surround']) < zo.PAN_SURROUND_DE_MIN:
            out.append('%s: ΔE00 %.2f from its surround' % (where, _de(p['hex'], p['surround'])))
        if _is_teal(p['hex']) != p['teal']:
            out.append('%s: teal recorded %s' % (where, p['teal']))
    teal = [p['name'] for p in pans if p['row'] == 3 and _is_teal(p['hex'])]
    if len(teal) < zo.TEAL_ROW_MIN:
        out.append('row 3 carries %d teal pans' % len(teal))
    if (rec['teal_row_3']['count'], rec['teal_row_3']['names']) != (len(teal), teal):
        out.append('teal_row_3 says %s' % rec['teal_row_3'])
    if [x['name'] for x in rec['lifted']] != [p['name'] for p in pans if p['lift_l'] > 0]:
        out.append('the lifted list is not the lifted pans')
    if rec['all_off_the_surround'] != all(_de(p['hex'], p['surround']) >= zo.PAN_SURROUND_DE_MIN for p in pans):
        out.append('all_off_the_surround says %s' % rec['all_off_the_surround'])
    return out


@tray_records
def test_pans_json_holds_18_pans_three_teal_in_row_3_and_every_pan_off_its_surround():
    """Controls: a pan set to a colour near its surround, and four of row 3's pans set to rose (two teal left), are
    each caught."""
    rec = _json(TRAY / 'pans.json')
    names = zo.tray_names()
    assert len(rec['pans']) == 18 and _pans_failures(rec, names) == []
    near = copy.deepcopy(rec)
    pan = near['pans'][0]
    pan['hex'] = pan['hex_mean'] = zo.lab_to_hex(zo.hex_lab(pan['surround']) + np.array([3.0, 0.0, 0.0]))
    assert any('from its surround' in f for f in _pans_failures(near, names))
    rose = copy.deepcopy(rec)
    for p in [q for q in rose['pans'] if q['row'] == 3][:4]:
        p['hex'] = p['hex_mean'] = '#C05C61'
    assert any(f.startswith('row 3 carries 2') for f in _pans_failures(rose, names))


def test_lift_takes_the_least_half_step_of_l_and_one_step_less_fails():
    """A dark pan on the indigo is lightened by L* steps of 0.5 (a* b* kept) until it stands ΔE00 10 off — read on the
    hex it prints as, the path ``lift`` itself takes; one step less is under 10. A pan already off is not moved; one
    that no lightening can bring off its ground is refused."""
    surround = '#051C43'
    for pan in ('#0A2550', '#152A55'):
        lifted, step = zo.lift(pan, surround)
        base = zo.hex_lab(pan)
        assert step > 0 and step % zo.LIFT_STEP_L == 0
        assert _de(lifted, surround) >= zo.PAN_SURROUND_DE_MIN
        less = zo.lab_to_hex((base[0] + step - zo.LIFT_STEP_L, base[1], base[2]))
        assert _de(less, surround) < zo.PAN_SURROUND_DE_MIN
    assert zo.lift('#DFABB1', surround) == ('#DFABB1', 0.0)
    with pytest.raises(ValueError, match='cannot be lifted'):
        zo.lift('#F8F8F8', '#FFFFFF')


@tray_records
def test_lab_to_hex_round_trips_every_pan_and_a_grid_of_srgb():
    """``lab_to_hex(hex_lab(h)) == h`` for every pan's colours and surround and a 6 × 6 × 6 grid of sRGB. Control: one
    L* more prints as another hex for every pan."""
    pans = _json(TRAY / 'pans.json')['pans']
    steps = (0, 37, 90, 128, 200, 255)
    grid = ['#%02X%02X%02X' % (r, g, b) for r in steps for g in steps for b in steps]
    hexes = sorted({h for p in pans for h in (p['hex'], p['hex_mean'], p['surround'])}) + grid
    assert [h for h in hexes if zo.lab_to_hex(zo.hex_lab(h)) != h] == []
    lighter = [p['hex'] for p in pans if zo.lab_to_hex(zo.hex_lab(p['hex']) + np.array([1.0, 0.0, 0.0])) == p['hex']]
    assert lighter == []


def test_main_cluster_drops_a_far_stray_column_and_keeps_a_word_space():
    """A name's columns: two words 14 px apart (a word space, 1.7 mm at the pick's scale) stay one name; a column 60 px
    off (a stone's light edge) is dropped. Control: the same two words 21 px apart split, the shorter lost."""
    velvet = np.arange(100, 160)
    bloom = np.arange(174, 220)
    stray = np.arange(280, 284)
    kept = zo.main_cluster(np.concatenate([velvet, bloom, stray]))
    assert kept.min() == 100 and kept.max() == 219
    apart = zo.main_cluster(np.concatenate([velvet, bloom + 7, stray + 7]))
    assert apart.min() == 100 and apart.max() == 159


def _set_width_mm(fit, face_path):
    """The width ``name_fit`` sets a name at: its advances at its size plus its tracking over its gaps (mm)."""
    from fontTools.ttLib import TTFont
    font = TTFont(face_path)
    cmap, hmtx, upm = font.getBestCmap(), font['hmtx'], font['head'].unitsPerEm
    advance = sum(hmtx[cmap[ord(ch)]][0] for ch in fit['name'].upper()) / upm
    return (advance + fit['tracking_fitted_em'] * (len(fit['name']) - 1)) * fit['size_mm']


@tray_records
def test_name_fit_and_refit_close_a_planted_width_error_and_reproduce_the_record():
    """``name_fit`` sets each name at the sketch's ink width, centred on it; ``refit`` with the first read-back gives
    tray.json's fits (tracking and centre). A planted 0.3 mm width error and 0.2 mm centre error read back are closed
    by ``refit``; left uncorrected they are outside the 0.25 mm the names are held to."""
    from fontTools.ttLib import TTFont
    rec = _json(TRAY / 'tray.json')
    face = _json(LID / 'master.json')['type']['faces']['latin']['path']
    font = TTFont(face)
    cap = font['OS/2'].sCapHeight / font['head'].unitsPerEm
    k = zm.PICK_PX[0] / zm.LID_MM[0]
    for fit, first in zip(rec['names']['fits'], rec['names']['overlay']['first']):
        x0, _, x1, _ = fit['ink_mm']
        fresh = zo.name_fit(fit['name'], [v * k for v in fit['ink_mm']], fit['size_mm'] * k * cap, k, face)
        assert abs(_set_width_mm(fresh, face) - (x1 - x0)) < 5e-3          # the record's 4-decimal rounding
        again = zo.refit(fresh, first)
        assert abs(again['tracking_fitted_em'] - fit['tracking_fitted_em']) <= 5e-4, fit['name']
        assert abs(again['x_centre_mm'] - fit['x_centre_mm']) <= 2e-3, fit['name']
    fit = rec['names']['fits'][5]
    read = {'d_width_mm': 0.3, 'd_centre_mm': -0.2}
    closed = zo.refit(fit, read)
    assert abs((_set_width_mm(fit, face) - _set_width_mm(closed, face)) - 0.3) < 5e-3
    assert abs(closed['x_centre_mm'] - (fit['x_centre_mm'] + 0.2)) < 1e-3
    assert max(abs(v) for v in read.values()) > zo.NAME_OVERLAY_MM


@tray_records
def test_the_names_read_back_from_the_print_within_a_quarter_millimetre():
    """``names_overlay`` re-run on the committed print flat gives tray.json's second read-back, every name within
    0.25 mm in width and centre of the sketch's ink. Control: the sketch's ink moved 0.5 mm reads the names 0.5 mm off."""
    rec = _json(TRAY / 'tray.json')
    inset = ((zm.LID_MM[0] - zo.TRAY_INSERT_MM[0]) / 2, (zm.LID_MM[1] - zo.TRAY_INSERT_MM[1]) / 2)
    second = zo.names_overlay(TRAY / 'tray-flat.png', rec['names']['fits'], inset)
    assert second == rec['names']['overlay']['second'] and rec['names']['overlay']['holds']
    assert all(abs(o['d_width_mm']) <= zo.NAME_OVERLAY_MM and abs(o['d_centre_mm']) <= zo.NAME_OVERLAY_MM for o in second)
    moved = [dict(f, ink_mm=[f['ink_mm'][0] + 0.5, f['ink_mm'][1], f['ink_mm'][2] + 0.5, f['ink_mm'][3]])
             for f in rec['names']['fits']]
    off = zo.names_overlay(TRAY / 'tray-flat.png', moved, inset)
    assert all(abs(o['d_centre_mm']) > zo.NAME_OVERLAY_MM for o in off)


def _cut_failures(pdf_path, pans):
    """tray-artwork.pdf's cut page held to pans.json pan by pan: page 1 (the print) draws no line; page 2 draws the
    insert's 184 × 114 outline 3 mm in and one well per pan at its box (0.05 mm), and nothing else."""
    import fitz
    to_mm = lm.MM_PER_INCH / 72.0
    with fitz.open(str(pdf_path)) as d:
        printed = d[0].get_drawings()
        cut = [[v * to_mm for v in (x['rect'].x0, x['rect'].y0, x['rect'].x1, x['rect'].y1)] for x in d[1].get_drawings()]
    out = ['the print page draws %d lines' % len(printed)] if printed else []
    inset = ((zm.LID_MM[0] - zo.TRAY_INSERT_MM[0]) / 2, (zm.LID_MM[1] - zo.TRAY_INSERT_MM[1]) / 2)
    outline = [inset[0], inset[1], inset[0] + zo.TRAY_INSERT_MM[0], inset[1] + zo.TRAY_INSERT_MM[1]]
    if not any(np.allclose(r, outline, atol=0.05) for r in cut):
        out.append('no insert outline')
    for p in pans:
        if not any(np.allclose(r, p['box_mm'], atol=0.05) for r in cut):
            out.append('no well for %s' % p['name'])
    if len(cut) != len(pans) + 1:
        out.append('the cut page draws %d paths' % len(cut))
    return out


@tray_records
def test_the_cut_page_holds_the_insert_outline_and_the_18_wells(tmp_path):
    """Control: a cut page drawn with the outline and 17 of the wells names the missing pan."""
    import fitz
    pans = _json(TRAY / 'pans.json')['pans']
    assert _cut_failures(TRAY / 'tray-artwork.pdf', pans) == []
    pt = 72.0 / lm.MM_PER_INCH
    pdf = fitz.open()
    pdf.new_page(width=zm.LID_MM[0] * pt, height=zm.LID_MM[1] * pt)
    page = pdf.new_page(width=zm.LID_MM[0] * pt, height=zm.LID_MM[1] * pt)
    page.draw_rect(fitz.Rect(3 * pt, 3 * pt, 187 * pt, 117 * pt), color=(0.78, 0.58, 0.35), width=0.7)
    for p in pans[:-1]:
        page.draw_rect(fitz.Rect(*[v * pt for v in p['box_mm']]), color=(0.78, 0.58, 0.35), width=0.7)
    pdf.save(str(tmp_path / 'cut.pdf'))
    pdf.close()
    assert _cut_failures(tmp_path / 'cut.pdf', pans) == ['no well for %s' % pans[-1]['name'], 'the cut page draws 18 paths']


@tray_records
def test_the_trays_eye_round_1_holds_and_says_what_it_lacked():
    """Round 0 failed and named its defects; repair 1's round answered with no defect (recomputed), its pictures the
    bytes judged. It was not given the lid (D-D11-4): its first picture is the pick. Every tray eye record's verdict is
    its own answer's, re-looks included."""
    r0, r1 = _json(TRAY / 'eye-r0.json'), _json(TRAY / 'eye-r1.json')
    assert _eye_failures(r0) == [] and r0['answered'] and r0['holds'] is False and r0['defects']
    assert _eye_failures(r1) == [] and r1['holds'] is True and _sent_failures(r1['look']['sent']) == []
    assert not r1['look']['sent'][0]['path'].endswith('lid-language.png')
    for eye in sorted(TRAY.glob('eye-*.json')):
        assert _eye_failures(_json(eye)) == [], eye.name


# ======================================================================================================================
# zilal_lipstick: the sheet's rectangles, the crop at the trim lines, the candidate (D-D11-7)
# ======================================================================================================================

def _aspect_failures(boxes, aspect, tolerance):
    return [(name, (b[2] - b[0]) / (b[3] - b[1])) for name, b in boxes.items()
            if abs((b[2] - b[0]) / (b[3] - b[1]) - aspect) / aspect > tolerance]


def test_the_sheets_rectangles_are_the_wraps_true_aspect():
    """Body above cap, each 900 px wide at 64.8 : 42 (1.543) within 0.2 %, inside the 1024 × 1536 sheet, apart.
    Control: a rectangle 0.3 % off the aspect fails the same check."""
    boxes = zl.rectangles()
    assert zl.ASPECT == zl.WRAP_MM[0] / zl.WRAP_MM[1] and abs(zl.ASPECT - 1.543) < 5e-4
    assert _aspect_failures(boxes, zl.ASPECT, 0.002) == []
    assert all(b[2] - b[0] == 900 and b[0] >= 0 and b[2] <= zl.SHEET_PX[0] and b[3] <= zl.SHEET_PX[1]
               for b in boxes.values())
    assert boxes['body'][3] < boxes['cap'][1]
    x0, y0 = boxes['body'][:2]
    off = {'body': (x0, y0, x0 + 900, y0 + 900 / (zl.ASPECT * 1.003))}
    assert _aspect_failures(off, zl.ASPECT, 0.002) != []


def _sheet_with(tmp_path, name, heights):
    """A sketch picture on a white sheet with each wrap drawn indigo at the sheet's place, 900 px wide and the given
    height (px), saved as ``picture.png`` in its own folder."""
    dest = tmp_path / name
    dest.mkdir()
    img = np.full((zl.SHEET_PX[1], zl.SHEET_PX[0], 3), 255, dtype=np.uint8)
    for wrap, (x0, y0, _, _) in zl.rectangles().items():
        img[y0:y0 + heights[wrap], x0:x0 + 900] = (16, 28, 72)
    Image.fromarray(img).save(dest / 'picture.png')
    return dest


def test_crop_wraps_disqualifies_a_3_percent_aspect_and_keeps_a_1_percent_one(tmp_path, monkeypatch):
    """The crop drops 2 px inside each trim line, so the heights are chosen for the cropped (w − 4) / (h − 4): the body
    at 3 % off the true aspect is disqualified (over D-D11-7's 2 %), the cap at 1 % qualifies, and the sketch with it
    does not; both at 1 % qualify."""
    monkeypatch.setattr(lm, 'rel', lambda p: str(p))
    three = int(round(896 / (zl.ASPECT * 1.03))) + 4
    one = int(round(896 / (zl.ASPECT * 1.01))) + 4
    rec = zl.crop_wraps(_sheet_with(tmp_path, 'mixed', {'body': three, 'cap': one}))
    assert abs(rec['wraps']['body']['aspect_error'] - 0.03) < 0.003 and not rec['wraps']['body']['qualifies']
    assert abs(rec['wraps']['cap']['aspect_error'] - 0.01) < 0.003 and rec['wraps']['cap']['qualifies']
    assert rec['qualifies'] is False
    both = zl.crop_wraps(_sheet_with(tmp_path, 'both', {'body': one, 'cap': one}))
    assert both['qualifies'] is True
    assert Image.open(tmp_path / 'both' / 'body.png').size == (896, one - 4)       # cropped, never stretched


def test_the_committed_sketches_crops_are_what_crop_wraps_reads(tmp_path, monkeypatch):
    """Every committed lipstick sketch (first round and retries) cropped again from its paid picture, in tmp_path: the
    aspect, its error and the verdict are its crop.json's."""
    monkeypatch.setattr(lm, 'rel', lambda p: str(p))
    folders = sorted(p.parent for p in zl.SKETCHES.glob('S*/crop.json'))
    if not folders:
        pytest.skip('the lipstick sketches are not here')
    for folder in folders:
        dest = tmp_path / folder.name
        dest.mkdir()
        shutil.copyfile(folder / 'picture.png', dest / 'picture.png')
        again, kept = zl.crop_wraps(dest), _json(folder / 'crop.json')
        assert again['qualifies'] == kept['qualifies'], folder.name
        for wrap in ('body', 'cap'):
            for key in ('aspect', 'aspect_error', 'qualifies', 'box_px'):
                assert again['wraps'][wrap][key] == kept['wraps'][wrap][key], (folder.name, wrap, key)


def _crop_json(folder, qualifies):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'crop.json').write_text(json.dumps({'wraps': {}, 'qualifies': qualifies}))


def test_candidate_takes_the_first_round_then_a_qualifying_retry_else_none(tmp_path, monkeypatch):
    """D-D11-7's rule as ``candidate`` keeps it: the first round when it qualifies (its retry never read), else the
    retry when made and qualifying, else None — a retry that also failed, or none made, leaves the sketch out."""
    monkeypatch.setattr(zl, 'SKETCHES', tmp_path)
    _crop_json(tmp_path / 'S1', True)
    _crop_json(tmp_path / 'S1-retry', False)
    _crop_json(tmp_path / 'S2', False)
    _crop_json(tmp_path / 'S2-retry', True)
    _crop_json(tmp_path / 'S3', False)
    _crop_json(tmp_path / 'S3-retry', False)
    _crop_json(tmp_path / 'S4', False)
    folder, rows = zl.candidate(1)
    assert folder == tmp_path / 'S1' and set(rows) == {'first'}
    folder, rows = zl.candidate(2)
    assert folder == tmp_path / 'S2-retry' and set(rows) == {'first', 'retry'}
    assert zl.candidate(3)[0] is None and set(zl.candidate(3)[1]) == {'first', 'retry'}
    assert zl.candidate(4) == (None, {'first': {'wraps': {}, 'qualifies': False}})


def test_the_ranked_lipstick_sketches_are_the_candidates():
    """The round after the retry ranked exactly the sketches ``candidate`` gives (computed for 1–6 from the crops on
    disk), each from its own folder, and recorded the rest as disqualified."""
    shown_map = zl.SKETCHES / 'ranking-after-retry-map.json'
    if not shown_map.exists():
        pytest.skip('the lipstick round after the retry is not here')
    shown = _json(shown_map)
    candidates = {n: zl.candidate(n)[0] for n in range(1, zl.COUNT + 1)}
    ranked = {v['sketch']: (ig.REPO / v['folder']).resolve() for v in shown['shown_as'].values()}
    assert ranked == {n: f.resolve() for n, f in candidates.items() if f is not None}
    assert sorted(d['sketch'] for d in shown['disqualified']) == sorted(n for n, f in candidates.items() if f is None)
