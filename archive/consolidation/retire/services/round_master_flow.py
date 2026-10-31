"""Owner-started day-two outbox. No day-one state or historical artifact is rewritten."""
import fcntl
import hashlib
import json
import re
import subprocess
import sys
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.pipeline.models import Round, RoundMaster
from . import round_flow as flow

STEPS = ('panels', 'detail', 'layout', 'plates', 'files', 'eye', 'jury', 'publish')
LABELS = dict(zip(STEPS, ('Preparing panels', 'Bringing out detail', 'Placing the lettering',
    'Separating the print', 'Making printable files', 'Designer’s review', 'Jury record', 'Preparing your download')))


def root(build):
    return flow.round_root(build.round) / 'master'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def start(round_id, user):
    from .round_master_art import input_snapshot
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        flow._owner(record, user)
        if record.state != 'complete' or not record.pick:
            raise ValueError('Record your pick before building the master.')
        previous = RoundMaster.objects.filter(round=record).first()
        if previous is not None:
            return previous
        snapshot = input_snapshot(record)
        snapshot['owner_start'] = {'user_id': user.pk, 'at': timezone.now().isoformat()}
        build = RoundMaster.objects.create(round=record, inputs=snapshot,
            steps={name: {'state': 'queued' if i == 0 else 'waiting', 'attempts': 0,
                         'dispatches': 0, 'history': [], 'result': {}} for i, name in enumerate(STEPS)})
        transaction.on_commit(lambda: enqueue(build.pk))
    return build


def enqueue(build_id):
    from apps.pipeline.tasks import run_round_master
    try:
        run_round_master.delay(build_id)
    except Exception as exc:
        fail(build_id, exc, kind='queue delivery', expected='queued')


def recover(build):
    build.refresh_from_db()
    if build.state == 'queued':
        enqueue(build.pk)


def retry(round_id, user):
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=round_id)
        flow._owner(build.round, user)
        if build.state != 'failed':
            raise ValueError('There is no failed master step to retry.')
        step = build.steps[build.current_step]
        step['attempts'] += 1
        step['state'] = 'queued'
        build.state, build.error = 'queued', ''
        build.save()
        transaction.on_commit(lambda: enqueue(build.pk))
    return build


def retain_failure(build, event):
    folder = flow.round_root(build.round)
    folder.mkdir(parents=True, exist_ok=True)
    flow.write_json(root(build) / 'failures' / (event['id'] + '.json'), event)
    with (folder / '.master-breaks.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = folder / 'BREAKS.md'
        text = path.read_text() if path.exists() else '# Round breaks\n'
        marker = '<!-- master-stop:' + event['id'] + ' -->'
        if marker not in text:
            numbers = [int(x) for x in re.findall(r'## (?:Live |Master )?Break (\d+)', text)]
            number = max([8] + numbers) + 1
            text += (f'\n## Master Break {number} — {LABELS[event["step"]]}\n\n{marker}\n'
                     f'- Stop: {event["error"]}\n- Attempt: {event["attempt"]}; {event["at"]}.\n'
                     '- Recovery: code repair and owner Retry required; no manual step execution.\n'
                     '- Repair/commit: appended by the builder after diagnosis.\n')
            import os, uuid
            temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
            with temporary.open('x') as stream:
                stream.write(text);stream.flush();os.fsync(stream.fileno())
            temporary.replace(path)
    flow.commit_artifacts(build.round, 'master stop recorded')


def fail(build_id, exc, *, kind='worker', expected=None):
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(pk=build_id)
        if expected is not None and build.state != expected:
            return {'status': build.state}
        step = build.steps[build.current_step]
        event = {'step': build.current_step, 'error': f'{type(exc).__name__}: {exc}',
                 'attempt': step['attempts'], 'dispatch': step['dispatches'],
                 'kind': kind, 'at': timezone.now().isoformat()}
        event['id'] = digest(event)[:20]
        step['history'].append(event)
        step['state'] = 'failed'
        build.state, build.error = 'failed', event['error']
        build.save()
    try:
        retain_failure(build, event)
    except Exception as evidence_error:
        with transaction.atomic():
            current=RoundMaster.objects.select_for_update().get(pk=build.pk)
            for item in current.steps[event['step']]['history']:
                if item['id']==event['id']:item['evidence_error']=str(evidence_error)
            current.save(update_fields=['steps','updated_at'])
    return {'status': 'failed', 'error': build.error}


def tag(build):
    if build.round.slug != 'r2-gloss' or build.state != 'complete' or 'pytest' in sys.modules:
        return
    if not getattr(settings, 'ROUND_COMMIT_ARTIFACTS', True):
        return
    name = 'round-2-gloss-b'
    with (flow.REPO / '.git/round-artifacts.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = subprocess.run(['git', 'rev-parse', '--verify', 'refs/tags/' + name], cwd=flow.REPO, capture_output=True)
        if existing.returncode == 0:
            saved = subprocess.run(['git', 'show', name + ':docs/rounds/r2-gloss/master/publication.json'], cwd=flow.REPO, capture_output=True, check=True)
            if json.loads(saved.stdout) != build.publication:
                raise ValueError('The closing tag belongs to another master; it will not move.')
            return
        subprocess.run(['git', 'tag', '-a', name, '-m', 'C5 app-owned master; verdict and measured reports retained'], cwd=flow.REPO, check=True, capture_output=True)


def run(build_id):
    from .round_calls import MasterContext
    from .round_master_art import run_step
    build = RoundMaster.objects.select_related('round').get(pk=build_id)
    if build.state == 'complete':
        tag(build)
        return {'status': 'complete'}
    queued = False
    # Shared per-round claim also excludes a duplicate master delivery.
    with flow._job_lock(build.round) as claimed:
        if not claimed:
            return {'status': 'already_running'}
        with transaction.atomic():
            build = RoundMaster.objects.select_for_update().select_related('round').get(pk=build_id)
            if build.state not in ('queued', 'running'):
                return {'status': build.state}
            step = build.steps[build.current_step]
            step['state'] = 'running'
            step['dispatches'] += 1
            build.state = 'running'
            build.save()
        try:
            context = MasterContext(build, SimpleNamespace(**step))
            context.root.mkdir(parents=True, exist_ok=True)
            # Recover secondary failure-evidence writes without rewriting a paid input.
            for row in build.steps.values():
                for event in row['history']:
                    retain_failure(build, event)
            result = run_step(build.current_step, context)
            flow.write_json(context.root / 'steps' / (build.current_step + '.json'), result)
            flow.commit_artifacts(build.round, 'master ' + build.current_step + ' complete')
            with transaction.atomic():
                current = RoundMaster.objects.select_for_update().get(pk=build.pk)
                current.steps[build.current_step].update(state='complete', result=result)
                index = STEPS.index(build.current_step)
                if index == len(STEPS) - 1:
                    current.state, current.publication = 'complete', result
                else:
                    current.current_step = STEPS[index + 1]
                    current.steps[current.current_step]['state'] = 'queued'
                    current.state = 'queued'
                    queued = True
                current.error = ''
                current.save()
            if current.state == 'complete':
                tag(current)
        except flow.YieldRound:
            try:
                flow.commit_artifacts(build.round, 'master paid reply saved; continuing')
                build.steps[build.current_step]['state'] = 'queued'
                build.state = 'queued'
                build.save()
                queued = True
            except Exception as exc:
                return fail(build_id, exc)
        except Exception as exc:
            return fail(build_id, exc)
    if queued:
        enqueue(build_id)
    return {'status': 'queued' if queued else 'complete'}


def progress(build):
    return [{'label': LABELS[name], 'state': build.steps[name]['state']} for name in STEPS]
