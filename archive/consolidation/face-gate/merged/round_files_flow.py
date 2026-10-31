"""Execution-half outbox: the owner starts; each face is drawn as its own job and the owner is the gate — Accept or
Redraw per face, then "Make my files" (owner, 2026-10-28; round_files_gate). Only queued jobs build files."""
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from apps.pipeline.models import Round, RoundMaster
from . import round_flow as flow

SCHEMA = 'picked_picture_files/1'
STEPS = ('read', 'stand', 'faces', 'files')
#: the face path's steps before the owner became the gate (2026-10-27/28): its builds move onto the gate
FACE_PATH_STEPS = ('read', 'stand', 'faces', 'files', 'eye', 'publish')
#: the retired picture-tracing path's steps (docs/rounds/reuse-plan.md): its builds are kept and shown, never run
V1_STEPS = ('read', 'crops', 'stand', 'files', 'eye', 'publish')
LABELS = {'read': 'Reading your picture', 'crops': 'Preparing the artwork', 'stand': 'Building the stand',
          'faces': 'Your faces: accept or redraw each', 'files': 'Making your files', 'eye': 'Designer’s review',
          'publish': 'Preparing your download'}
RETIRED = ('This build ran on the retired picture-tracing path (docs/rounds/reuse-plan.md); '
           'its saved files stay as they were.')
POLICY = flow.REPO / 'docs/rounds/files-build-policy.json'


COPY_RECORD = 'files-copy.json'


def root(build):
    return flow.round_root(build.round) / 'files'


def files_brief(build):
    """The frozen brief, plus the round's committed Arabic shade names where the brief has none.

    The record binds to the brief by digest. Names it supplies are marked by
    their source; executor-written names stay unconfirmed until the owner says.
    """
    import hashlib
    import json
    import re
    from copy import deepcopy
    brief = deepcopy(build.inputs['brief'])
    path = flow.round_root(build.round) / COPY_RECORD
    if not path.exists():
        return brief
    record = json.loads(path.read_text())
    if record.get('schema') != 'round_files_copy/1' or record.get('brief_sha256') != build.inputs['brief_sha256']:
        raise ValueError('The round’s added copy belongs to another brief.')
    names = record.get('arabic_shade_names') or {}
    if set(names) - {shade['name'] for shade in brief['shades']}:
        raise ValueError('The round’s added copy names a shade the brief does not have.')
    supplied = {}
    for shade in brief['shades']:
        value = names.get(shade['name'])
        if shade.get('name_arabic') or not value:
            continue
        if (not isinstance(value, str) or value != ' '.join(value.split()) or
                re.search(r'[A-Za-z]', value) or not re.search(r'[\u0600-\u06ff]', value)):
            raise ValueError('An added Arabic shade name must be one line of Arabic letters.')
        shade['name_arabic'] = supplied[shade['name']] = value
    if supplied:
        brief['copy_sources'] = {'arabic_shade_names': {
            'path': COPY_RECORD, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'names': supplied,
            'source': record.get('source', ''), 'confirmed': record.get('confirmed') is True}}
    return brief


def steps_of(build):
    if 'faces' not in build.steps:
        return V1_STEPS
    return STEPS if 'eye' not in build.steps else FACE_PATH_STEPS


def reading_notes(build):
    """Plain-words notes for the files page: what the reading repaired or dropped, the stand grid and added copy."""
    notes = []
    read = (build.steps.get('read') or {}).get('result') or {}
    for row in read.get('reading_findings', []) if isinstance(read, dict) else []:
        verb = {'dropped': 'left out', 'normalised': 'kept', 'replaced': 'replaced'}.get(row['action'], row['action'])
        notes.append(f"{row['label']}: {row['item']} {verb} — {row['why']}.")
    stand = (build.steps.get('stand') or {}).get('result') or {}
    layout = stand.get('layout') if isinstance(stand, dict) else None
    if layout and layout.get('note'):
        notes.append(layout['note'])
    drawn = (build.steps.get('faces') or {}).get('result') or {}
    if isinstance(drawn, dict) and drawn.get('header_leaves'):
        notes.append(drawn['header_leaves'])
    try:
        sources = files_brief(build).get('copy_sources', {})
    except (ValueError, KeyError, OSError):
        sources = {}
    added = sources.get('arabic_shade_names')
    if added and not added['confirmed']:
        notes.append('Arabic shade names written by Claude, not yet confirmed by you: ' +
                     ' · '.join(f'{name} {value}' for name, value in added['names'].items()) + '.')
    return notes


#: a flat pick (owner, 2026-10-28) prints as it was picked, but the files build does not yet take one
FLAT_PICK_WAITS = ('Your pick is a flat die: its stand prints as you picked it. Building its files from the flat die '
                   'is the next step to be built (the bottle and the cap need their own flat face templates first); '
                   'nothing was started and nothing was spent.')


def flat_pick(record):
    """Whether the round's sealed pick is a flat die (round_designer's flat_die_handoff/1)."""
    import json
    path = flow.round_root(record) / 'handoff.json'
    return path.exists() and json.loads(path.read_text()).get('schema') == 'flat_die_handoff/1'


def start(round_id, user):
    from .round_files_job import input_snapshot
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        flow._owner(record, user)
        if record.state != 'complete' or not flow.is_ideas_round(record):
            raise ValueError('Record your picture choice before building the files.')
        previous = RoundMaster.objects.filter(round=record).first()
        if previous is not None:
            if previous.inputs.get('schema') != SCHEMA:
                raise ValueError('This round already has a different build.')
            return previous
        if flat_pick(record):
            raise ValueError(FLAT_PICK_WAITS)
        snapshot = input_snapshot(record)
        snapshot['owner_start'] = {'user_id': user.pk, 'at': timezone.now().isoformat()}
        build = RoundMaster.objects.create(round=record, inputs=snapshot, budget_usd=10,
            current_step=STEPS[0], steps={name: {'state': 'queued' if i == 0 else 'waiting',
                'attempts': 0, 'dispatches': 0, 'history': [], 'result': {}} for i, name in enumerate(STEPS)})
        transaction.on_commit(lambda: enqueue(build.pk))
    return build


def enqueue(build_id):
    from apps.pipeline.tasks import run_round_files
    try:
        run_round_files.delay(build_id)
    except Exception as exc:
        fail(build_id, exc, kind='queue delivery', expected='queued')


def recover(build):
    """The page's nudge: a queued build is enqueued again; a face-path build waiting on a stop is queued so the worker
    moves it onto the gate ($0, no call)."""
    build.refresh_from_db()
    if 'eye' in build.steps and 'faces' in build.steps and build.state == 'failed':
        with transaction.atomic():
            locked = RoundMaster.objects.select_for_update().get(pk=build.pk)
            if locked.state == 'failed':
                locked.state, locked.error = 'queued', ''
                locked.save()
        build.refresh_from_db()
    if build.state == 'queued':
        enqueue(build.pk)


def retry(round_id, user):
    with transaction.atomic():
        build = RoundMaster.objects.select_for_update().select_related('round').get(round_id=round_id)
        flow._owner(build.round, user)
        if build.inputs.get('schema') != SCHEMA or build.state != 'failed':
            raise ValueError('There is no failed files step to retry.')
        if 'faces' not in build.steps:
            raise ValueError(RETIRED)
        step = build.steps[build.current_step]
        step.update(attempts=step['attempts'] + 1, state='queued')
        build.state, build.error = 'queued', ''
        build.save()
        transaction.on_commit(lambda: enqueue(build.pk))
    return build


def retain_failure(build, event):
    from .round_ideas import record_break
    flow.write_json(root(build) / 'failures' / (event['id'] + '.json'), event)
    job = SimpleNamespace(pk='files-' + str(build.pk), name=event['step'],
                          attempts=event['attempt'], history=[event])
    record_break(build.round, job, event['error'])
    flow.commit_artifacts(build.round, 'files stop recorded')


def fail(build_id, exc, *, kind='worker', expected=None):
    from .round_master_flow import digest
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
            current = RoundMaster.objects.select_for_update().get(pk=build.pk)
            current.steps[event['step']]['history'][-1]['evidence_error'] = str(evidence_error)
            current.save(update_fields=['steps', 'updated_at'])
    return {'status': 'failed', 'error': build.error}


def run(build_id):
    from . import round_files_gate as gate
    from .round_files_job import FilesContext, run_step, tag_completed
    build = RoundMaster.objects.select_related('round').get(pk=build_id)
    if build.inputs.get('schema') != SCHEMA:
        raise ValueError('This is not a picture-to-files build.')
    if build.state == 'complete':
        tag_completed(build)
        return {'status': 'complete'}
    queued = False
    with flow._job_lock(build.round) as claimed:
        if not claimed:
            return {'status': 'already_running'}
        with transaction.atomic():
            build = RoundMaster.objects.select_for_update().select_related('round').get(pk=build_id)
            if 'faces' not in build.steps:
                return {'status': 'retired'}
            if 'eye' in build.steps:
                gate.migrate(build)
            if gate.is_gate(build):
                gate.restand(build)
                gate.flatten(build)
            if build.state not in ('queued', 'running'):
                return {'status': build.state}
            step = build.steps[build.current_step]
            step.update(state='running', dispatches=step['dispatches'] + 1)
            build.state = 'running'
            build.save()
        try:
            context = FilesContext(build, SimpleNamespace(**step))
            context.root.mkdir(parents=True, exist_ok=True)
            for item in build.steps.values():
                for event in item['history']:
                    retain_failure(build, event)
            name = build.current_step
            if name == 'faces':
                # Each face's next job; the build then waits for the owner (Accept or Redraw per face).
                more = gate.work(context)
                flow.commit_artifacts(build.round, 'files faces worked')
                with transaction.atomic():
                    current = RoundMaster.objects.select_for_update().get(pk=build.pk)
                    more = more or any(gate.pending(row) for row in gate.board(current).values())
                    current.steps['faces']['state'] = 'running' if more else 'complete'
                    if current.current_step == 'faces':
                        current.state, queued = ('queued', True) if more else ('awaiting', False)
                    current.save()
            else:
                result = gate.make(context) if name == 'files' else run_step(name, context)
                flow.write_json(context.root / 'steps' / (name + '.json'), result)
                flow.commit_artifacts(build.round, 'files ' + name + ' complete')
                with transaction.atomic():
                    current = RoundMaster.objects.select_for_update().get(pk=build.pk)
                    current.steps[name].update(state='complete', result=result)
                    if name == 'files':
                        current.state, current.publication = 'complete', result
                    else:
                        current.current_step = STEPS[STEPS.index(name) + 1]
                        if current.current_step == 'faces':
                            from .round_files_faces import FACES
                            current.steps['faces']['board'] = {key: gate.empty_face(key) for key in FACES}
                            gate.open_flat(current)
                        current.steps[current.current_step]['state'] = 'queued'
                        current.state, queued = 'queued', True
                    current.error = ''
                    current.save()
                if current.state == 'complete':
                    tag_completed(current)
        except flow.YieldRound:
            try:
                flow.commit_artifacts(build.round, 'files paid reply retained; continuing')
                with transaction.atomic():
                    current = RoundMaster.objects.select_for_update().get(pk=build.pk)
                    current.steps[current.current_step]['state'] = 'queued'
                    current.state = 'queued'
                    current.save()
                queued = True
            except Exception as exc:
                return fail(build_id, exc)
        except Exception as exc:
            return fail(build_id, exc)
    if queued:
        enqueue(build_id)
    return {'status': 'queued' if queued else current.state}


def progress(build):
    return [{'label': LABELS[name], 'state': build.steps[name]['state']} for name in steps_of(build)]
