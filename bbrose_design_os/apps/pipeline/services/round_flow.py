"""App-owned round state machine. Only its queued worker writes round artifacts."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.pipeline.models import Round, RoundStep

REPO = Path(__file__).resolve().parents[4]


def is_designer_round(record):
    """The mood-board flow: an ideas round whose stored brief carries the designer marker."""
    from .round_designer import is_designer_brief
    return is_designer_brief(record.product_brief)


def is_retired_round(record):
    """The owner's goal of 2026-10-29 retired the twenty-design (Round 2) and the whole-object (Round 1/2) kinds:
    only the designer flow runs. A retired round stays in the database and its records in docs/rounds/<slug>/."""
    return not is_designer_round(record)


def retired_words(record):
    return ('This round ran on the retired pipeline; its records stay in docs/rounds/%s/.' % record.slug)


def rejected(record):
    """The owner's rejection of a round as recorded (the ruling of 2026-10-29 on round 3), or None. A rejected round
    is history: its records stay on disk, it takes no more work and no new round reads it."""
    if not isinstance(record.artifacts, dict):
        return None
    return record.artifacts.get('rejected')


def rejected_words(record):
    return ('You rejected this round on %s. Its records stay in docs/rounds/%s/ as history; it takes no more work and '
            'no new round uses it.' % (record.artifacts['rejected']['at'][:10], record.slug))


def reject(round_id, ruling):
    """Marks a round rejected, in its record and in its folder (rejected.json). Nothing is deleted."""
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        entry = {'schema': 'round_rejected/1', 'ruling': ruling, 'at': timezone.now().isoformat(),
                 'recorded_in': 'CURRENT_DECISIONS.md'}
        record.artifacts = dict(record.artifacts, rejected=entry)
        record.save(update_fields=['artifacts', 'updated_at'])
    write_json(round_root(record) / 'rejected.json', entry)
    return record


def steps_for(record):
    """The designer flow's steps; a retired round (the twenty-design or the whole-object kind) runs none."""
    if is_designer_round(record):
        from .round_designer import DESIGNER_STEPS
        return DESIGNER_STEPS
    return ()


class YieldRound(Exception):
    """One new paid logical call finished; continue in another bounded queue job."""


def round_root(round_record):
    if 'pytest' in sys.modules and not hasattr(settings, 'ROUND_ARTIFACT_ROOT'):
        raise RuntimeError('Round tests require an isolated ROUND_ARTIFACT_ROOT.')
    base = Path(getattr(settings, 'ROUND_ARTIFACT_ROOT', REPO / 'docs/rounds')).resolve()
    root = (base / round_record.slug).resolve()
    if root.parent != base or round_record.slug == 'r1-balm':
        raise ValueError('Invalid round artifact directory.')
    return root


def write_json(path, payload):
    """Atomic durable artifact replacement; provider raw replies use distinct paths."""
    import os
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_json(path, payload):
    import os
    with Path(path).open('a') as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def commit_artifacts(round_record, detail):
    if 'pytest' in sys.modules:
        return
    if not getattr(settings, 'ROUND_COMMIT_ARTIFACTS', True):
        return
    root = round_root(round_record)
    relative = str(root.relative_to(REPO))
    with (REPO / '.git/round-artifacts.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        subprocess.run(['git', 'add', '--', relative], cwd=REPO, check=True, capture_output=True)
        changed = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', relative], cwd=REPO)
        if changed.returncode == 1:
            subprocess.run(['git', 'commit', '--only', '-m', f'Round {round_record.slug}: {detail}', '--', relative],
                           cwd=REPO, check=True, capture_output=True)
        elif changed.returncode != 0:
            raise RuntimeError('Round artifact commit inspection failed.')


def _owner(round_record, user):
    if not user.is_authenticated or (round_record.created_by_id != user.pk and not user.is_staff):
        raise PermissionDenied('This round belongs to another owner.')
    if rejected(round_record):                          # every owner action on a round passes here
        raise ValueError(rejected_words(round_record))


def _dispatch_failure(step_id, reason, kind, expected_state):
    """Keep broker failures in the same reportable history as worker failures."""
    identity = RoundStep.objects.only('round_id').get(pk=step_id)
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=identity.round_id)
        job = RoundStep.objects.select_for_update().get(pk=step_id)
        if job.state != expected_state or record.current_step != job.name:
            return False
        event = {'at': timezone.now().isoformat(), 'error': reason, 'attempt': job.attempts, 'kind': kind}
        if not any(item.get('kind') == kind and item['attempt'] == job.attempts for item in job.history):
            job.history = list(job.history) + [event]
        job.state = 'failed'
        job.error = reason
        job.save(update_fields=['state', 'error', 'history', 'updated_at'])
        record.state = 'failed'
        record.error_message = reason
        record.save(update_fields=['state', 'error_message', 'updated_at'])
    _retain_failure_evidence(record, job, job.history)
    return True


def _enqueue(step_id):
    from apps.pipeline.round_tasks import run_creative_round_step
    try:
        run_creative_round_step.delay(step_id)
    except Exception as exc:
        reason = f'Queue delivery failed: {type(exc).__name__}: {exc}'
        _dispatch_failure(step_id, reason, 'queue_delivery', 'queued')


def recover_dispatch(record):
    """App GET/redelivery repairs a committed outbox item whose broker publish was lost. A retired round is left
    exactly as it is."""
    record.refresh_from_db()
    if is_retired_round(record) or rejected(record):
        return
    if record.state == 'queued':
        job = record.steps.filter(name=record.current_step, state='queued').first()
        if job is not None:
            _enqueue(job.pk)


def create_round(brief, user, request_key):
    from .round_designer import is_designer_brief, is_ideas_brief, normalize_ideas_brief
    if not user.is_authenticated:
        raise PermissionDenied('Sign in to start a round.')
    if not isinstance(request_key, str) or not 8 <= len(request_key) <= 64:
        raise ValueError('Start needs its form identity.')
    normalized = normalize_ideas_brief(brief) if is_ideas_brief(brief) else None
    if normalized is None or not is_designer_brief(normalized):
        raise ValueError('A round starts only from the designer brief (research, three boards, three designs); '
                         'the twenty-design and whole-object rounds are retired.')
    with transaction.atomic():
        # Serialize duplicate form submissions before choosing the unique round slug.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        previous = Round.objects.filter(request_key=request_key).first()
        if previous is not None:
            _owner(previous, user)
            if previous.product_brief != normalized:
                raise ValueError('This Start identity already belongs to a different brief.')
            transaction.on_commit(lambda: recover_dispatch(previous))
            return previous
        stem = slugify(normalized['name'])[:65]
        if not stem:
            stem = 'product'
        slug = f'{stem}-{uuid.uuid4().hex[:10]}'
        first = 'research'
        from .round_calls import COST_RULES, ROUND_CAP_USD      # the owner's $2.00 per design round (2026-10-29)
        from .round_files_faces import FACE_RULES               # measured holds, medium faces (2026-10-29)
        record = Round.objects.create(slug=slug, request_key=request_key, product_brief=normalized,
                                      created_by=user, budget_usd=ROUND_CAP_USD, current_step=first,
                                      artifacts={'cost_rules': COST_RULES, 'face_rules': FACE_RULES})
        job = RoundStep.objects.create(round=record, name=first, position=0)
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


def _next_locked(record, completed):
    sequence = steps_for(record)
    index = sequence.index(completed)
    if completed == 'pick':
        record.state = 'complete'
        record.current_step = 'pick'
        record.save()
        return
    next_name = sequence[index + 1]
    waiting = next_name in ('board_pick', 'pick')
    job, _ = RoundStep.objects.get_or_create(round=record, name=next_name,
        defaults={'position': index + 1, 'state': 'waiting' if waiting else 'queued'})
    record.current_step = next_name
    record.state = f'awaiting_{next_name}' if waiting else 'queued'
    record.error_message = ''
    record.save()
    return None if waiting else job.pk


@contextmanager
def _job_lock(record):
    from django.conf import settings
    base = Path(getattr(settings, 'ROUND_LOCK_ROOT', Path(settings.BASE_DIR) / 'var/round-locks'))
    if 'pytest' in sys.modules:
        base = round_root(record).parent / '.locks'
    base.mkdir(parents=True, exist_ok=True)
    with (base / f'{record.pk}.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _retain_failure_evidence(record, job, history):
    """Keep secondary evidence errors separate from the already-recorded step failure."""
    return _retain_ideas_failure(record, job, history)


def _retain_ideas_failure(record, job, history):
    """The central break record and local evidence recover independently."""
    errors = []
    job.history = history
    try:
        record_break(record, job, history[-1]['error'])
    except Exception as exc:
        errors.append(f'Central break record: {type(exc).__name__}: {exc}')
    try:
        write_json(round_root(record) / 'failures' / f'{job.name}-{job.attempts}-{job.dispatches}.json', history[-1])
        commit_artifacts(record, f'{job.name} failed; evidence retained')
    except Exception as exc:
        errors.append(f'Local failure evidence: {type(exc).__name__}: {exc}')
    if errors:
        # A concurrent owner Retry must retain its newer attempt and state.
        with transaction.atomic():
            current = RoundStep.objects.select_for_update().get(pk=job.pk)
            for event in current.history:
                if event['at'] == history[-1]['at'] and event['attempt'] == history[-1]['attempt']:
                    event['evidence_error'] = '; '.join(errors)
            current.save(update_fields=['history', 'updated_at'])


def _record_step_failure(record, job, exc):
    reason = f'{type(exc).__name__}: {exc}'
    history = list(job.history) + [{'at': timezone.now().isoformat(), 'error': reason, 'attempt': job.attempts}]
    with transaction.atomic():
        RoundStep.objects.filter(pk=job.pk).update(state='failed', error=reason, history=history)
        Round.objects.filter(pk=record.pk).update(state='failed', error_message=reason)
    _retain_failure_evidence(record, job, history)
    return {'status': 'failed', 'error': reason}


def _continue_step(record, job):
    try:
        commit_artifacts(record, f'{job.name} paid call saved; continuing')
        with transaction.atomic():
            RoundStep.objects.filter(pk=job.pk).update(state='queued')
            Round.objects.filter(pk=record.pk).update(state='queued')
    except Exception as exc:
        return _record_step_failure(record, job, exc)
    return {'status': 'queued'}


def run_step_job(step_id):
    """One bounded worker delivery, resumable after process loss or duplicate delivery. A retired round's job is
    refused in words: nothing is spent and nothing of the round changes."""
    job = RoundStep.objects.select_related('round').get(pk=step_id)
    if is_retired_round(job.round):
        return {'status': 'retired', 'error': retired_words(job.round)}
    if rejected(job.round):
        return {'status': 'rejected', 'error': rejected_words(job.round)}
    if job.state == 'complete':
        recover_dispatch(job.round)
        return {'status': 'complete'}
    next_step_id = None
    outcome = {'status': 'queued'}
    with _job_lock(job.round) as owned:
        if not owned:
            return {'status': 'already_running'}
        with transaction.atomic():
            job = RoundStep.objects.select_for_update().select_related('round').get(pk=step_id)
            record = Round.objects.select_for_update().get(pk=job.round_id)
            if job.state not in ('queued', 'running') or record.current_step != job.name:
                return {'status': job.state}
            job.state = 'running'
            job.dispatches += 1
            if job.started_at is None:
                job.started_at = timezone.now()
            job.save()
            record.state = 'running'
            record.save()
        try:
            from .round_designer import DesignerContext, run_step, finalize_pick
            if job.name not in steps_for(record):
                raise ValueError('This step is outside the designer flow.')
            for prior in record.steps.all():
                if prior.history:
                    record_break(record, prior, prior.history[-1]['error'])
            context = DesignerContext(record, job)
            context.root.mkdir(parents=True, exist_ok=True)
            write_json(context.root / 'brief.json', record.product_brief)
            if job.name == 'pick':
                if not record.pick:
                    raise ValueError('An owner decision is required.')
                write_json(context.root / 'pick.json', record.pick)
                result = finalize_pick(context)
            else:
                result = run_step(context, job.name)
            write_json(context.root / 'steps' / f'{job.name}.json', result)
            commit_artifacts(record, f'{job.name} complete')
            with transaction.atomic():
                current = Round.objects.select_for_update().get(pk=record.pk)
                current.artifacts = dict(current.artifacts, **{job.name: result})
                job.state = 'complete'
                job.result = result
                job.error = ''
                job.finished_at = timezone.now()
                job.save()
                # Enqueue only after releasing the filesystem claim, including eager fixtures.
                current.save()
                next_step_id = _next_locked(current, job.name)
            outcome = {'status': 'complete', 'step': job.name}
        except YieldRound:
            outcome = _continue_step(record, job)
            if outcome['status'] == 'failed':
                return outcome
            next_step_id = step_id
        except Exception as exc:
            return _record_step_failure(record, job, exc)
    if next_step_id is not None:
        _enqueue(next_step_id)
    return outcome


def submit_pick(round_id, candidate, reason, user, merge=None):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Your pick needs a reason.')
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        _owner(record, user)
        if is_retired_round(record):
            raise ValueError(retired_words(record))
        if merge is not None:
            raise ValueError('Choose one original design; this round does not merge candidates.')
        if record.state != 'awaiting_pick':
            if record.pick and record.pick['id'] == candidate and record.pick['reason'] == reason.strip() and record.pick['merge'] == merge:
                transaction.on_commit(lambda: recover_dispatch(record))
                return record
            raise ValueError('The round is not waiting for a pick.')
        page = record.artifacts['pick_page']
        if candidate not in page['order']:
            raise ValueError('Pick one candidate from the final page.')
        record.pick = {'id': candidate, 'reason': reason.strip(), 'merge': merge, 'source': {'kind': 'owner app', 'user_id': user.pk}, 'recorded_at': timezone.now().isoformat()}
        record.state = 'queued'
        record.save()
        job = record.steps.get(name='pick')
        job.state = 'queued'
        job.save()
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


def submit_board_pick(round_id, board, reason, user):
    """The owner's one mood board; the reason is optional."""
    reason = reason.strip() if isinstance(reason, str) else ''
    if len(reason) > 1000:
        raise ValueError('Keep the reason under a thousand characters.')
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        _owner(record, user)
        if not is_designer_round(record):
            raise ValueError('This round has no mood boards.')
        saved = record.artifacts.get('board_choice') or {}
        if record.state != 'awaiting_board_pick':
            if saved.get('id') == board and saved.get('reason') == reason:
                transaction.on_commit(lambda: recover_dispatch(record))
                return record
            raise ValueError('The round is not waiting for a board pick.')
        boards = record.artifacts.get('boards') or {}
        if board not in boards.get('order', []):
            raise ValueError('Pick one of the three boards.')
        record.artifacts = dict(record.artifacts, board_choice={'id': board, 'reason': reason,
            'generation': boards['generation'], 'source': {'kind': 'owner app', 'user_id': user.pk},
            'recorded_at': timezone.now().isoformat()})
        record.state = 'queued'
        record.save()
        job = record.steps.get(name='board_pick')
        job.state = 'queued'
        job.save()
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


NONE_OF_THESE = {'boards': ('awaiting_board_pick', ('boards',), ('board_pick',)),
                 'designs': ('awaiting_pick', ('designs', 'pick_page'), ('pick',))}


def none_of_these(round_id, stage, line, user):
    """Once per pick: the owner's one line makes three new boards or three new designs."""
    line = line.strip() if isinstance(line, str) else ''
    if not line or '\n' in line or '\r' in line or len(line) > 500:
        raise ValueError('Write one line on what is wrong.')
    if stage not in NONE_OF_THESE:
        raise ValueError('Unknown pick.')
    waiting, rerun, later = NONE_OF_THESE[stage]
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        _owner(record, user)
        if not is_designer_round(record):
            raise ValueError('This round has no "None of these".')
        redo = dict(record.artifacts.get('redo') or {})
        if stage in redo:
            if redo[stage]['line'] == line and record.state != waiting:
                transaction.on_commit(lambda: recover_dispatch(record))
                return record
            raise ValueError('"None of these" is used once per pick.')
        if record.state != waiting:
            raise ValueError('The round is not waiting for this pick.')
        artifacts = dict(record.artifacts)
        redo[stage] = {'line': line, 'rejected': list(artifacts[rerun[-1]]['order']),
                       'source': {'kind': 'owner app', 'user_id': user.pk}, 'recorded_at': timezone.now().isoformat()}
        artifacts['redo'] = redo
        artifacts['rejected_' + stage] = {name: artifacts.pop(name) for name in rerun if name in artifacts}
        record.artifacts = artifacts
        record.current_step = rerun[0]
        record.state = 'queued'
        record.error_message = ''
        record.save()
        # Completed rows would otherwise be skipped as already done; the second pass writes new paths.
        for name in rerun:
            RoundStep.objects.filter(round=record, name=name).update(
                state='queued', result={}, error='', started_at=None, finished_at=None)
        RoundStep.objects.filter(round=record, name__in=later).update(state='waiting')
        job = record.steps.get(name=rerun[0])
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


def retry_round(round_id, user):
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        _owner(record, user)
        if is_retired_round(record):
            raise ValueError(retired_words(record))
        if record.state != 'failed':
            raise ValueError('Only a failed step can be retried.')
        job = record.steps.select_for_update().get(name=record.current_step)
        job.state = 'queued'
        job.attempts += 1
        job.error = ''
        job.save()
        record.state = 'queued'
        record.error_message = ''
        record.save()
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


#: each designer step in the owner's words — the round's page, Home, Designs and the top bar read the same ones
DESIGNER_STEP_LABELS = {'research': 'Researching the category', 'boards': 'Making three mood boards',
                        'board_pick': 'Your board', 'designs': 'Drawing three designs',
                        'pick_page': 'Checking the designs', 'pick': 'Your pick'}


def summary(record):
    from .round_calls import scoped_spend
    if is_retired_round(record):
        return {'state': record.state, 'current_step': record.current_step, 'current_step_label': record.current_step,
                'error': record.error_message, 'retired': retired_words(record),
                'steps': list(record.steps.values('name', 'state', 'attempts', 'error')), 'spend': scoped_spend(record),
                'repair_plan': None, 'repair_authorization': None}
    from .round_designer import DesignerContext
    labels = DESIGNER_STEP_LABELS
    saved = {row['name']: row for row in record.steps.values('name', 'state', 'attempts', 'error')}
    progress = []
    for name in steps_for(record):
        row = saved[name] if name in saved else {'name': name, 'state': 'waiting', 'attempts': 0, 'error': ''}
        progress.append(dict(row, label=labels[name]))
    spend = scoped_spend(record)
    spend['image_attempt_limit'] = DesignerContext.image_attempt_cap
    return {'state': record.state, 'current_step': record.current_step,
            'current_step_label': labels[record.current_step], 'error': record.error_message, 'retired': '',
            'steps': progress, 'spend': spend,
            'repair_plan': None, 'repair_authorization': None}


def record_break(record, job, error):
    """Append each persisted worker/dispatch stop once, including replay after a crash."""
    base = Path(settings.ROUND_ARTIFACT_ROOT) if hasattr(settings, 'ROUND_ARTIFACT_ROOT') else REPO / 'docs' / 'rounds'
    path = base / 'BREAKS.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    events = job.history or [{'error': str(error), 'attempt': job.attempts, 'kind': 'worker'}]
    with (base / '.breaks.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = path.read_text() if path.exists() else '# Round stops\n'
        for event in events:
            if not event.get('error'):
                continue
            stable_event = {key: event[key] for key in ('at', 'error', 'attempt', 'kind') if key in event}
            identity = hashlib.sha256(json.dumps({'round': record.pk, 'job': job.pk, 'event': stable_event},
                                               sort_keys=True).encode()).hexdigest()
            marker = '<!-- stop:' + identity + ' -->'
            if marker in existing:
                continue
            numbers = [int(number) for number in re.findall(r'^## (\d+)\.', existing, re.MULTILINE)]
            number = max(numbers, default=0) + 1
            message = str(event['error']).replace('\n', ' ').replace('\r', ' ')
            existing += (f'\n## {number}. {record.slug} — {job.name}\n\n{marker}\n'
                         f'Stopped: {message}\n\nThe job is paused. Fix the code, then the owner presses Retry in the app. '
                         'No manual stage was run.\n')
        temporary = path.with_suffix('.md.tmp')
        temporary.write_text(existing)
        temporary.replace(path)
