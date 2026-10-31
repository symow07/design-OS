"""Fixture-only queue/state tests: the app starts, marks and picks; jobs do the rest."""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from apps.pipeline.models import Round, RoundStep
from apps.pipeline.services import round_flow as flow
from apps.pipeline.services.round_product import lip_gloss_brief


@pytest.fixture
def queued(tmp_path, settings, monkeypatch):
    from apps.pipeline.services import round_report
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    pending = []
    monkeypatch.setattr(flow, '_enqueue', pending.append)
    monkeypatch.setattr(round_report, 'finalize', lambda context, pick: None)
    return pending


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user(username='round-owner')


def fixture_step(name, context):
    ids = [f'A{i}' for i in range(1, 9)]
    if name == 'seeds':
        flow.write_json(context.root / 'critic-calibration.json', {'marks': {}, 'picks': []})
    if name == 'pairwise':
        return {'order': ids}
    if name == 'sketches':
        return {'candidates': {key: {'id': key} for key in ids}}
    if name == 'forks':
        return {'candidates': {}}
    if name == 'pick_page':
        return {'order': ids[:6], 'candidates': {key: {'id': key} for key in ids[:6]}}
    if name == 'marks_fallback':
        return {'marks': [{'id': key, 'preserve': 'A visible fragment'} for key in ids[:3]],
                'source': {'kind': 'jury timeout fallback'}}
    return {'fixture_step': name}


def drain(pending):
    while pending:
        flow.run_step_job(pending.pop(0))


@pytest.mark.django_db(transaction=True)
def test_start_runs_to_marks_then_pick_page_and_waits_for_owner(queued, owner, monkeypatch):
    from apps.pipeline.services import round_steps
    monkeypatch.setattr(round_steps, 'run_step', fixture_step)
    token = uuid.uuid4().hex
    record = flow.create_round(lip_gloss_brief(), owner, token)
    assert flow.create_round(lip_gloss_brief(), owner, token).pk == record.pk
    assert Round.objects.count() == 1 and set(queued) == {record.steps.get(name='seeds').pk}
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'awaiting_marks'
    assert len(record.artifacts['pairwise']['order']) == 8
    assert record.marks_due_at is not None
    flow.submit_marks(record.pk, [{'id': 'A1', 'preserve': 'Keep the visible fragment'}], owner)
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'awaiting_pick' and not record.pick
    assert not flow.marks_deadline(record.pk, record.marks_due_at + timedelta(days=1))
    flow.submit_pick(record.pk, 'A1', 'Its object idea.', owner)
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'complete' and record.pick['id'] == 'A1'
    assert (flow.round_root(record) / 'pick.json').is_file()
    assert record.steps.filter(state='complete').count() == len(flow.STEPS)


@pytest.mark.django_db(transaction=True)
def test_marks_fallback_only_at_sixty_minutes_and_only_marks(queued, owner, monkeypatch):
    from apps.pipeline.services import round_steps
    monkeypatch.setattr(round_steps, 'run_step', fixture_step)
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    drain(queued)
    record.refresh_from_db()
    assert not flow.marks_deadline(record.pk, record.marks_due_at - timedelta(seconds=1))
    assert flow.marks_deadline(record.pk, record.marks_due_at)
    assert not flow.marks_deadline(record.pk, record.marks_due_at)
    monkeypatch.setattr(flow.timezone, 'now', lambda: record.marks_due_at)
    drain(queued)
    record.refresh_from_db()
    assert record.marks['source']['kind'] == 'jury timeout fallback'
    assert len(record.marks['marks']) == 3 and record.state == 'awaiting_pick' and not record.pick


@pytest.mark.django_db(transaction=True)
def test_failed_step_retries_from_app_without_repeating_completed_steps(queued, owner, monkeypatch):
    from apps.pipeline.services import round_steps
    observed = []
    def broken(name, context):
        observed.append(name)
        if name == 'sheet':
            raise ValueError('fixture sheet failure')
        return fixture_step(name, context)
    monkeypatch.setattr(round_steps, 'run_step', broken)
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'failed' and record.current_step == 'sheet'
    monkeypatch.setattr(round_steps, 'run_step', fixture_step)
    flow.retry_round(record.pk, owner)
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'awaiting_marks'
    assert observed.count('seeds') == 1
    assert record.steps.get(name='sheet').attempts == 1
    assert record.steps.get(name='sheet').history[0]['error'] == 'ValueError: fixture sheet failure'
    seed_job = record.steps.get(name='seeds')
    assert flow.run_step_job(seed_job.pk)['status'] == 'complete'
    assert seed_job.dispatches == 1


@pytest.mark.django_db(transaction=True)
def test_claim_lock_duplicate_delivery_and_owner_permissions(queued, owner, monkeypatch):
    from apps.pipeline.services import round_steps
    monkeypatch.setattr(round_steps, 'run_step', fixture_step)
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    job = record.steps.get(name='seeds')
    with flow._job_lock(record) as owned:
        assert owned and flow.run_step_job(job.pk)['status'] == 'already_running'
    other = get_user_model().objects.create_user(username='other-round-owner')
    with pytest.raises(PermissionDenied):
        flow.create_round(lip_gloss_brief(), other, record.request_key)
    drain(queued)
    with pytest.raises(PermissionDenied):
        flow.submit_marks(record.pk, [{'id': 'A1', 'preserve': 'fragment'}], other)


@pytest.mark.django_db(transaction=True)
def test_completed_redelivery_recovers_next_step_after_publish_gap(queued, owner, monkeypatch):
    from apps.pipeline.services import round_steps
    monkeypatch.setattr(round_steps, 'run_step', fixture_step)
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    first = queued.pop()
    flow.run_step_job(first)
    queued.clear()  # The next queued DB row survives a lost broker publication.
    assert flow.run_step_job(first)['status'] == 'complete'
    assert len(queued) == 1
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'awaiting_marks'


@pytest.mark.django_db(transaction=True)
def test_failed_timer_retry_cannot_take_fallback_before_deadline(queued, owner, monkeypatch, settings):
    from apps.pipeline import tasks
    from apps.pipeline.services import round_steps
    monkeypatch.setattr(round_steps, 'run_step', fixture_step)
    settings.CELERY_TASK_ALWAYS_EAGER = False
    def broken_timer(**kwargs):
        raise RuntimeError('fixture broker down')
    monkeypatch.setattr(tasks.round_marks_deadline, 'apply_async', broken_timer)
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'failed' and record.current_step == 'marks'
    assert record.steps.get(name='pairwise').state == 'complete'
    marks_job = record.steps.get(name='marks')
    assert len(marks_job.history) == 1
    assert marks_job.history[0]['kind'] == 'marks_timer_delivery'
    flow._schedule_marks(record.pk, record.marks_due_at)
    marks_job.refresh_from_db()
    assert len(marks_job.history) == 1  # Duplicate failed publication is one break.
    monkeypatch.setattr(tasks.round_marks_deadline, 'apply_async', lambda **kwargs: None)
    flow.retry_round(record.pk, owner)
    drain(queued)
    record.refresh_from_db()
    assert record.state == 'awaiting_marks' and not record.marks
    assert record.steps.get(name='marks').state == 'waiting'


@pytest.mark.django_db(transaction=True)
def test_broker_failures_are_reportable_once_per_app_attempt(owner, monkeypatch, tmp_path, settings):
    from apps.pipeline import tasks
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    def unavailable(step_id):
        raise RuntimeError('fixture broker unavailable')
    monkeypatch.setattr(tasks.run_creative_round_step, 'delay', unavailable)
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    record.refresh_from_db()
    job = record.steps.get(name='seeds')
    assert record.state == job.state == 'failed'
    assert len(job.history) == 1 and job.history[0]['kind'] == 'queue_delivery'
    flow._enqueue(job.pk)
    job.refresh_from_db()
    assert len(job.history) == 1
    flow.retry_round(record.pk, owner)
    job.refresh_from_db()
    assert [event['attempt'] for event in job.history] == [0, 1]
    reportable = [{'step': item.name, **event} for item in record.steps.all() for event in item.history]
    assert len(reportable) == 2
    assert all(event['step'] == 'seeds' and 'fixture broker unavailable' in event['error'] for event in reportable)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('failure', ['context', 'root', 'brief'])
def test_setup_failure_records_original_error_and_remains_app_retryable(queued, owner, monkeypatch, failure):
    from apps.pipeline.services import round_calls, round_steps
    from unittest.mock import Mock
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    job_id = queued.pop(0)
    root = flow.round_root(record)
    run_step = Mock(side_effect=fixture_step)
    monkeypatch.setattr(round_steps, 'run_step', run_step)
    with monkeypatch.context() as broken:
        if failure == 'context':
            broken.setattr(round_calls, 'RoundContext', Mock(side_effect=OSError('fixture context unavailable')))
            expected = 'OSError: fixture context unavailable'
        elif failure == 'root':
            root.parent.mkdir(parents=True, exist_ok=True)
            root.write_text('fixture file blocks the artifact directory')
            expected = 'FileExistsError:'
        else:
            original_write = flow.write_json
            def write_unless_brief(path, payload):
                if path.name == 'brief.json':
                    raise PermissionError('fixture brief unavailable')
                original_write(path, payload)
            broken.setattr(flow, 'write_json', write_unless_brief)
            expected = 'PermissionError: fixture brief unavailable'
        outcome = flow.run_step_job(job_id)
    record.refresh_from_db()
    job = record.steps.get(pk=job_id)
    assert outcome['status'] == record.state == job.state == 'failed'
    assert outcome['error'] == record.error_message == job.error == job.history[0]['error']
    assert job.error.startswith(expected)
    assert len(job.history) == 1 and job.history[0]['attempt'] == 0
    run_step.assert_not_called()
    if failure == 'root':
        assert job.history[0]['evidence_error'].startswith('NotADirectoryError:')
        root.unlink()
    else:
        assert (root / 'failures' / 'seeds-0-1.json').exists()
    flow.retry_round(record.pk, owner)
    assert flow.run_step_job(queued.pop(0))['status'] == 'complete'
    job.refresh_from_db()
    assert job.state == 'complete' and job.attempts == 1 and len(job.history) == 1
    assert run_step.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_failure_evidence_commit_error_preserves_original_failure_and_app_retry(queued, owner, monkeypatch):
    from apps.pipeline.services import round_steps
    from unittest.mock import Mock
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    job_id = queued.pop(0)
    with monkeypatch.context() as broken:
        broken.setattr(round_steps, 'run_step', Mock(side_effect=ValueError('fixture original step failure')))
        broken.setattr(flow, 'commit_artifacts', Mock(side_effect=OSError('fixture evidence commit unavailable')))
        outcome = flow.run_step_job(job_id)
    record.refresh_from_db()
    job = record.steps.get(pk=job_id)
    assert outcome == {'status': 'failed', 'error': 'ValueError: fixture original step failure'}
    assert record.state == job.state == 'failed'
    assert record.error_message == job.error == job.history[0]['error'] == outcome['error']
    assert job.history[0]['evidence_error'] == 'OSError: fixture evidence commit unavailable'
    assert (flow.round_root(record) / 'failures' / 'seeds-0-1.json').exists()
    monkeypatch.setattr(round_steps, 'run_step', fixture_step)
    flow.retry_round(record.pk, owner)
    assert flow.run_step_job(queued.pop(0))['status'] == 'complete'
    job.refresh_from_db()
    assert job.state == 'complete' and job.attempts == 1 and len(job.history) == 1


@pytest.mark.django_db(transaction=True)
def test_continuation_commit_failure_is_app_retryable_without_repaying_cached_call(queued, owner, monkeypatch):
    import json
    from types import SimpleNamespace
    from unittest.mock import Mock
    from apps.pipeline.services import round_calls, round_steps
    create = Mock(return_value={'stop_reason': 'end_turn',
        'content': [{'type': 'text', 'text': '{"ok": true}'}],
        'usage': {'input_tokens': 100, 'output_tokens': 20}})
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    original_context = round_calls.RoundContext
    monkeypatch.setattr(round_calls, 'RoundContext', lambda record, job: original_context(record, job, text_client=client))
    def paid_step(name, context):
        context.text_call('first', 'Read first.', context.root / 'first.json', max_tokens=100, ceiling=1)
        context.text_call('second', 'Read second.', context.root / 'second.json', max_tokens=100, ceiling=1)
        return fixture_step(name, context)
    monkeypatch.setattr(round_steps, 'run_step', paid_step)
    record = flow.create_round(lip_gloss_brief(), owner, uuid.uuid4().hex)
    job_id = queued.pop(0)
    original_commit = flow.commit_artifacts
    def fail_continuation(record, detail):
        if detail.endswith('paid call saved; continuing'):
            raise OSError('fixture continuation commit unavailable')
        original_commit(record, detail)
    with monkeypatch.context() as broken:
        broken.setattr(flow, 'commit_artifacts', fail_continuation)
        outcome = flow.run_step_job(job_id)
    record.refresh_from_db()
    job = record.steps.get(pk=job_id)
    assert outcome == {'status': 'failed', 'error': 'OSError: fixture continuation commit unavailable'}
    assert record.state == job.state == 'failed'
    assert record.error_message == job.error == job.history[0]['error'] == outcome['error']
    assert len(job.history) == 1 and not queued and create.call_count == 1
    first = json.loads((flow.round_root(record) / 'first.json').read_text())
    assert first['status'] == 'complete'
    flow.retry_round(record.pk, owner)
    assert flow.run_step_job(queued.pop(0))['status'] == 'complete'
    job.refresh_from_db()
    assert job.state == 'complete' and job.attempts == 1 and len(job.history) == 1
    assert create.call_count == round_calls.scoped_spend(record)['calls'] == 2
    assert json.loads((flow.round_root(record) / 'first.json').read_text()) == first


@pytest.fixture
def obsolete_round(queued, owner):
    """A failed original generation, with the actual missing-right-face defect."""
    brief = lip_gloss_brief()
    brief['panels'] = [panel for panel in brief['panels'] if panel['id'] != 'body_right']
    seeds = {'seeds': [{'id': f'{family}{number}', 'seed': 'Keep this original seed',
                       'link': 'because a gloss preserves its own truth'}
                      for family in 'ABCD' for number in range(1, 6)]}
    sheet = {'schema': 'round_sheet/1', 'panels': {panel['id']: {} for panel in brief['panels']}}
    record = Round.objects.create(slug='r2-gloss', request_key=uuid.uuid4().hex,
        product_brief=brief, created_by=owner, state='failed', current_step='coarse',
        error_message='No eligible whole objects', artifacts={'seeds': seeds, 'sheet': sheet,
            'sketches': {'candidates': [row['id'] for row in seeds['seeds']]},
            'checks': {'eligible': []}, 'readings': {'readings': {}}})
    for position, name in enumerate(flow.STEPS[:6]):
        RoundStep.objects.create(round=record, name=name, position=position,
            state='failed' if name == 'coarse' else 'complete', result=record.artifacts.get(name, {}),
            history=[{'at': '2026-10-26T10:00:00+00:00', 'attempt': 0, 'error': 'No eligible whole objects'}]
            if name == 'coarse' else [])
    root = flow.round_root(record)
    for relative, payload in {'brief.json': brief, 'sheet.json': sheet, 'seeds.json': seeds,
            'seeds-call.json': {'fixture': 'original paid seed response'},
            'steps/seeds.json': seeds, 'steps/sheet.json': sheet,
            'sketches/A1/image-call.json': {'fixture': 'immutable old image'},
            'sketches/A1/whole-object-call.response-0.json': {'fixture': 'immutable old check'},
            'eligibility.json': {'eligible': []}, 'jury/coarse/old.json': {'fixture': 'old jury'},
            'critic-calibration.json': {'schema': 'round_critic_calibration/1', 'rule': 'Fixture rule',
                                      'format': 'Ordinal judgments', 'marks': [], 'picks': [], 'departures': []}}.items():
        flow.write_json(root / relative, payload)
    (root / 'sheet.png').write_bytes(b'old sheet bytes')
    (root / 'sheet-mask.png').write_bytes(b'old mask bytes')
    (root / 'image-calls.jsonl').write_text('{"original":"journal remains append-only"}\n')
    return record


@pytest.mark.django_db(transaction=True)
def test_owner_repair_queues_sketches_archives_once_and_preserves_seeds_and_spend(
        obsolete_round, queued, owner, monkeypatch):
    from django.template.loader import render_to_string
    from apps.pipeline.services import round_calls, round_sheet, round_steps, spend_reservation
    record = obsolete_round
    root = flow.round_root(record)
    before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    reservation = spend_reservation.reserve('openai', 'round/r2-gloss/image/A1', 'gpt-image-2', .01)
    with spend_reservation._connect() as db:
        ledger_before = [dict(row) for row in db.execute('SELECT * FROM calls')]
    preview = flow.summary(record)
    assert preview['repair_plan']['restart_step'] == 'sketches'
    assert preview['spend']['budget_usd'] == 22 and preview['spend']['image_attempt_limit'] == 26
    page = render_to_string('dashboard/product_round.html', {'round': record, 'summary': preview})
    assert 'Retry with corrected sheet and sketches' in page and 'including earlier spend' in page
    assert 'at most 46 attempts' in page and '$25' in page
    stranger = get_user_model().objects.create_user(username='repair-stranger')
    with pytest.raises(PermissionDenied):
        flow.retry_round(record.pk, stranger)
    assert not queued
    flow.retry_round(record.pk, owner)
    record.refresh_from_db()
    authorization = flow.repair_authorization(record)
    assert record.current_step == 'sketches' and record.state == 'queued' and record.budget_usd == 25
    assert authorization['user_id'] == owner.pk and authorization['additional_image_attempts'] == 20
    assert authorization['old_brief_sha256'] == hashlib.sha256(json.dumps(record.product_brief, sort_keys=True).encode()).hexdigest()
    assert round_calls.image_call_limit(record) == 46 and len(record.product_brief['panels']) == 11
    assert {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()} == before
    assert record.steps.get(name='seeds').state == 'complete' and record.steps.get(name='seeds').attempts == 0
    builds, sketches = [], []
    def build(brief, destination):
        builds.append(brief)
        sheet = {'schema': round_sheet.SCHEMA, 'panels': {panel['id']: {} for panel in brief['panels']}}
        flow.write_json(destination / 'sheet.json', sheet)
        (destination / 'sheet.png').write_bytes(b'corrected twelve-panel sheet')
        return sheet
    def sketch(name, context):
        assert name == 'sketches' and len(context.brief['panels']) == 12
        assert (root / 'seeds.json').read_bytes() == before['seeds.json']
        sketches.append(name)
        raise ValueError('Fixture pause after repaired prerequisite')
    monkeypatch.setattr(round_sheet, 'build', build)
    monkeypatch.setattr(round_steps, 'run_step', sketch)
    assert flow.run_step_job(queued.pop(0))['status'] == 'failed'
    record.refresh_from_db()
    assert len(record.product_brief['panels']) == 12 and record.artifacts['sheet']['schema'] == round_sheet.SCHEMA
    assert record.steps.get(name='sheet').state == 'complete'
    manifest_path = root / flow.REPAIR_ARCHIVE / 'manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest['authorization']['previous_artifacts']['checks'] == {'eligible': []}
    for entry in manifest['files']:
        assert (root / entry['archived']).read_bytes() == before[entry['original']]
    assert (root / 'image-calls.jsonl').read_bytes() == before['image-calls.jsonl']
    assert (root / 'seeds-call.json').read_bytes() == before['seeds-call.json']
    assert len(record.steps.get(name='coarse').history) == 2
    flow.retry_round(record.pk, owner)
    assert flow.run_step_job(queued.pop(0))['status'] == 'failed'
    record.refresh_from_db()
    assert len(builds) == 1 and len(sketches) == 2 and round_calls.image_call_limit(record) == 46
    assert manifest_path.read_bytes() == manifest_bytes and flow.repair_plan(record) is None
    with spend_reservation._connect() as db:
        assert [dict(row) for row in db.execute('SELECT * FROM calls')] == ledger_before
    assert round_calls.scoped_spend(record)['reserved_usd'] == .01 and reservation


@pytest.mark.django_db(transaction=True)
def test_repair_archive_write_failure_is_app_retryable_without_losing_originals(
        obsolete_round, queued, owner, monkeypatch):
    from apps.pipeline.services import round_sheet, round_steps
    record = obsolete_round
    root = flow.round_root(record)
    old = (root / 'sheet.json').read_bytes()
    flow.retry_round(record.pk, owner)
    original_write = flow.write_json
    def fail_manifest(path, payload):
        if path.name == 'manifest.json':
            raise OSError('fixture archive disk failure')
        return original_write(path, payload)
    with monkeypatch.context() as failure:
        failure.setattr(flow, 'write_json', fail_manifest)
        outcome = flow.run_step_job(queued.pop(0))
    record.refresh_from_db()
    assert outcome['status'] == record.state == 'failed'
    assert 'fixture archive disk failure' in record.error_message
    assert (root / 'sheet.json').read_bytes() == old
    assert len(record.product_brief['panels']) == 11
    monkeypatch.setattr(round_sheet, 'build', lambda brief, destination: {'schema': round_sheet.SCHEMA})
    monkeypatch.setattr(round_steps, 'run_step', lambda name, context: {'candidates': []})
    flow.retry_round(record.pk, owner)
    assert flow.run_step_job(queued.pop(0))['status'] == 'complete'
    assert (root / flow.REPAIR_ARCHIVE / 'sheet.json').read_bytes() == old


@pytest.mark.django_db(transaction=True)
def test_partial_repair_archive_resumes_without_rewriting_paid_evidence(obsolete_round, queued, owner, monkeypatch):
    from pathlib import Path
    from apps.pipeline.services import round_sheet, round_steps
    record = obsolete_round
    root = flow.round_root(record)
    before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    flow.retry_round(record.pk, owner)
    rename = Path.rename
    def interrupted(path, target):
        if path == root / 'sheet.json':
            raise OSError('fixture archive interrupted after earlier moves')
        return rename(path, target)
    with monkeypatch.context() as failure:
        failure.setattr(Path, 'rename', interrupted)
        assert flow.run_step_job(queued.pop(0))['status'] == 'failed'
    manifest_path = root / flow.REPAIR_ARCHIVE / 'manifest.json'
    original_manifest = manifest_path.read_bytes()
    assert not (root / 'brief.json').exists()
    assert (root / flow.REPAIR_ARCHIVE / 'brief.json').read_bytes() == before['brief.json']
    assert (root / 'sheet.json').read_bytes() == before['sheet.json']
    monkeypatch.setattr(round_sheet, 'build', lambda brief, destination: {'schema': round_sheet.SCHEMA})
    monkeypatch.setattr(round_steps, 'run_step', lambda name, context: {'candidates': []})
    flow.retry_round(record.pk, owner)
    assert flow.run_step_job(queued.pop(0))['status'] == 'complete'
    assert manifest_path.read_bytes() == original_manifest
    for entry in json.loads(original_manifest)['files']:
        assert (root / entry['archived']).read_bytes() == before[entry['original']]
    assert (root / 'seeds.json').read_bytes() == before['seeds.json']
    assert (root / 'image-calls.jsonl').read_bytes() == before['image-calls.jsonl']


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('tamper', ['source_escape', 'archive_escape', 'duplicate', 'symlink',
                                    'authorization', 'brief_snapshot', 'brief_hash'])
def test_tampered_repair_manifest_fails_before_any_move_or_outside_write(
        obsolete_round, queued, owner, tamper):
    from copy import deepcopy
    record = obsolete_round
    root = flow.round_root(record)
    flow.retry_round(record.pk, owner)
    record.refresh_from_db()
    authorization = flow.repair_authorization(record)
    outside = root.parent / 'outside-directory'
    outside.mkdir()
    sentinel = outside / 'sentinel.txt'
    sentinel.write_bytes(b'outside bytes must stay untouched')
    originals = ('brief.json', 'sheet.json', 'sheet.png', 'sketches/A1/image-call.json')
    manifest = {'schema': 'round_repair_archive/1', 'authorization': deepcopy(authorization),
        'files': [{'original': relative, 'archived': flow.REPAIR_ARCHIVE + '/' + relative,
                   'sha256': hashlib.sha256((root / relative).read_bytes()).hexdigest()} for relative in originals],
        'preserved_files': [{'original': 'seeds.json', 'sha256': hashlib.sha256((root / 'seeds.json').read_bytes()).hexdigest()}]}
    malicious = {'original': 'eligibility.json', 'archived': flow.REPAIR_ARCHIVE + '/eligibility.json',
                 'sha256': hashlib.sha256((root / 'eligibility.json').read_bytes()).hexdigest()}
    if tamper == 'source_escape':
        malicious.update(original='../outside-directory/sentinel.txt',
                         archived=flow.REPAIR_ARCHIVE + '/../outside-directory/sentinel.txt',
                         sha256=hashlib.sha256(sentinel.read_bytes()).hexdigest())
    elif tamper == 'archive_escape':
        malicious['archived'] = '../outside-directory/escaped.txt'
    elif tamper == 'duplicate':
        malicious = dict(manifest['files'][0])
    elif tamper == 'symlink':
        (root / 'linked').symlink_to(outside, target_is_directory=True)
        malicious.update(original='linked/sentinel.txt', archived=flow.REPAIR_ARCHIVE + '/linked/sentinel.txt',
                         sha256=hashlib.sha256(sentinel.read_bytes()).hexdigest())
    elif tamper == 'authorization':
        manifest['authorization']['user_id'] += 1
    elif tamper == 'brief_snapshot':
        wrong = dict(record.product_brief, name='Different original brief')
        flow.write_json(root / 'brief.json', wrong)
        manifest['files'][0]['sha256'] = hashlib.sha256((root / 'brief.json').read_bytes()).hexdigest()
    elif tamper == 'brief_hash':
        authorization['old_brief_sha256'] = '0' * 64
        record.save(update_fields=['artifacts'])
        manifest['authorization'] = deepcopy(authorization)
    manifest['files'].append(malicious)  # Invalid last entry must block even the first legitimate move.
    manifest_path = root / flow.REPAIR_ARCHIVE / 'manifest.json'
    flow.write_json(manifest_path, manifest)
    before = {relative: (root / relative).read_bytes() for relative in originals}
    outcome = flow.run_step_job(queued.pop(0))
    record.refresh_from_db()
    assert outcome['status'] == record.state == 'failed'
    assert {relative: (root / relative).read_bytes() for relative in originals} == before
    assert sentinel.read_bytes() == b'outside bytes must stay untouched'
    assert sorted(path.name for path in outside.iterdir()) == ['sentinel.txt']
    assert [path for path in (root / flow.REPAIR_ARCHIVE).rglob('*') if path.is_file()] == [manifest_path]
    assert not (root / 'repair-authorization.json').exists()


@pytest.mark.django_db(transaction=True)
def test_repair_does_not_change_other_rounds_or_current_sheet_contract(obsolete_round, queued, owner):
    from apps.pipeline.services import round_calls, round_sheet
    record = obsolete_round
    record.slug = 'another-gloss'
    record.save()
    assert flow.repair_plan(record) is None
    flow.retry_round(record.pk, owner)
    record.refresh_from_db()
    assert record.current_step == 'coarse' and record.budget_usd == 22
    assert round_calls.image_call_limit(record) == 26
    record.slug, record.state = 'r2-gloss', 'failed'
    record.artifacts['sheet']['schema'] = round_sheet.SCHEMA
    record.save()
    assert flow.repair_plan(record) is None


@pytest.fixture
def master_pick(queued,owner,tmp_path):
    """Synthetic published day-one pick, produced entirely under the isolated root."""
    from apps.pipeline.services import round_sheet
    from PIL import Image
    def make(brief=None):
        brief=lip_gloss_brief() if brief is None else brief
        record=Round.objects.create(slug='master-'+uuid.uuid4().hex[:10],request_key=uuid.uuid4().hex,
            product_brief=brief,created_by=owner,state='complete',current_step='pick',pick={'id':'A1','merge':None,'reason':'fixture'})
        root=flow.round_root(record);root.mkdir(parents=True)
        round_sheet.build(brief,root)
        dest=root/'sketches/A1';dest.mkdir(parents=True)
        Image.open(root/'sheet.png').convert('RGB').save(dest/'picture.png')
        round_sheet.crops_and_drawing(dest,root)
        paths=[dest/'picture.png',dest/'crop.json',root/'sheet.json']
        pins={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        record.artifacts={'pick_page':{'candidates':{'A1':{'id':'A1'}},'order':['A1'],'files':pins}}
        record.save()
        return record
    return make


@pytest.mark.django_db(transaction=True)
def test_master_start_retry_and_failure_are_separate_from_day_one(master_pick,owner,monkeypatch):
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_master_flow as mf,round_master_art as art
    record=master_pick();before=(record.product_brief,record.pick,record.state,record.budget_usd,record.artifacts)
    pending=[];monkeypatch.setattr(mf,'enqueue',pending.append)
    build=mf.start(record.pk,owner)
    assert mf.start(record.pk,owner).pk==build.pk and len(pending)==1
    def fail_once(name,ctx):raise ValueError('fixture failure')
    monkeypatch.setattr(art,'run_step',fail_once)
    assert mf.run(pending.pop())['status']=='failed'
    build.refresh_from_db();assert build.state=='failed'
    assert 'Master Break 9' in (flow.round_root(record)/'BREAKS.md').read_text()
    assert mf.run(build.pk)['status']=='failed'
    mf.retry(record.pk,owner);build.refresh_from_db()
    assert build.steps['panels']['attempts']==1 and build.state=='queued'
    record.refresh_from_db()
    assert (record.product_brief,record.pick,record.state,record.budget_usd,record.artifacts)==before
    assert RoundMaster.objects.count()==1


@pytest.mark.django_db(transaction=True)
def test_master_refuses_changed_owner_pick_before_queue_or_payment(master_pick,owner,monkeypatch):
    from apps.pipeline.services import round_master_flow as mf
    record=master_pick();pending=[];monkeypatch.setattr(mf,'enqueue',pending.append)
    path=flow.round_root(record)/'sketches/A1/picture.png';path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='pinned'):
        mf.start(record.pk,owner)
    assert not pending and not hasattr(record,'master_build')


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('kind',['gloss','palette'])
def test_master_real_panel_and_detail_stages_are_product_independent(master_pick,owner,monkeypatch,kind):
    from apps.pipeline.services import round_master_flow as mf,round_master_art as art
    from apps.pipeline.services.round_calls import MasterContext
    from types import SimpleNamespace
    from PIL import Image
    brief=lip_gloss_brief()
    if kind=='palette':
        brief.update(name='Palette',shape='palette',product_type='palette',material='Printed cardboard',
            panels=[{'id':'lid','label':'Lid','surface':'print','width_mm':190,'height_mm':120},
                    {'id':'base','label':'Base','surface':'print','width_mm':190,'height_mm':120}],
            copy={'product':'Eyeshadow','net':'18 g ℮'})
        brief.pop('carton')
    record=master_pick(brief);monkeypatch.setattr(mf,'enqueue',lambda pk:None)
    build=mf.start(record.pk,owner);ctx=MasterContext(build,SimpleNamespace(attempts=0));ctx.root.mkdir(parents=True)
    got=art.panels(ctx);assert len(got['panels'])==len(brief['panels'])
    calls=[]
    def edit(op,prompt,folder,*,target,mask):
        folder.mkdir(parents=True,exist_ok=True);Image.open(target).save(folder/'raw.png');calls.append(op)
    monkeypatch.setattr(ctx,'masked_edit',edit)
    result=art.detail(ctx);assert len(result['panels'])==len(brief['panels'])
    assert all(p['de00_mean']<=1.5 and p['ssim']>=.97 for p in result['panels'] if p['accepted'])
    assert len(calls)==len(brief['panels'])
    assert art.detail(ctx)==result and len(calls)==len(brief['panels'])
    assert record.product_brief==brief and ctx.prefix.startswith('master/')


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('kind',['gloss','palette'])
def test_master_complete_worker_fixture_builds_layers_zip_and_jury_once(master_pick,owner,monkeypatch,kind):
    from apps.pipeline.services import round_master_flow as mf,round_master_art as art,round_master_files as files
    from apps.pipeline.services import round_calls as calls
    from PIL import Image
    import zipfile,fitz
    brief=lip_gloss_brief()
    if kind=='palette':
        brief.update(name='Palette',shape='palette',product_type='palette',material='Printed cardboard',
            panels=[{'id':'lid','label':'Lid','surface':'print','width_mm':190,'height_mm':120},
                    {'id':'base','label':'Base','surface':'print','width_mm':190,'height_mm':120}],
            copy={'product':'Eyeshadow','net':'18 g ℮'})
        brief.pop('carton')
    record=master_pick(brief);pending=[];monkeypatch.setattr(mf,'enqueue',pending.append)
    purchased=[]
    def image_call(ctx,op,prompt,folder,*,target,mask):
        if (folder/'raw.png').exists():return {}
        ctx._one_call();folder.mkdir(parents=True,exist_ok=True)
        Image.open(target).save(folder/'raw.png');purchased.append(op)
        return {}
    def text_call(ctx,op,prompt,destination,**kwargs):
        if destination.exists():return json.loads(destination.read_text())
        ctx._one_call();purchased.append(op)
        if op.startswith('check/layout-'):
            group=op.split('check/layout-')[1];ids=art.objects(ctx)[group]
            plan={key:{'text':[],'erase':[],'marks':[],'geometry':[],'notes':'Fixture'} for key in ids}
            if kind=='gloss' and group=='body':
                plan[ids[0]]['text']=[{'field':'copy.product','text':'Lip','box':[.1,.2,.9,.23],'color':'#111111'}]
                plan[ids[0]]['geometry']=[{'points':[[.1,.5],[.9,.6]],'width_mm':.1,'color':'#C9977F','closed':False}]
            if group==('carton' if kind=='gloss' else 'body'):
                fields=[key for key in ('copy.product','copy.net','copy.back_en','copy.back_es','copy.back_ar','copy.batch') if key in ctx.build.inputs['copy']]
                for index,field in enumerate(fields):
                    key=ids[index%len(ids)]
                    for n,word in enumerate(ctx.build.inputs['copy'][field].split()):
                        plan[key]['text'].append({'field':field,'text':word,'box':[.15,.15+n*.09,.85,.18+n*.09],'color':'#111111'})
            payload={'panels':plan}
        elif op.startswith('eye/'):
            payload={'verdict':'pass','reason':'Fixture full verdict','allowed_differences':[],'issues':[],'repair':[]}
        elif op=='jury/master':payload={'record':'Fixture jury record','strengths':[],'concerns':[]}
        else:raise AssertionError(op)
        result={'payload':payload};flow.write_json(destination,result);return result
    monkeypatch.setattr(calls.MasterContext,'masked_edit',image_call)
    monkeypatch.setattr(calls.MasterContext,'text_call',text_call)
    # The real Illustrator bridge is exercised separately by native_fixture.py;
    # this queue test uses actual PDF files and an explicit application stub.
    monkeypatch.setattr(files,'native_roundtrip',lambda path:{'holds':True,'fixture_stub':True})
    monkeypatch.setattr(files,'native_reopen_checks',lambda paths:[{'holds':True,'fixture_stub':True,'final_sha256':files.sha(p)} for p in paths])
    build=mf.start(record.pk,owner)
    for delivery in range(100):
        if not pending:break
        outcome=mf.run(pending.pop(0))
        assert outcome['status']!='failed',outcome
    build.refresh_from_db();assert build.state=='complete',build.error
    assert all(row['state']=='complete' for row in build.steps.values())
    assert purchased.count('jury/master')==1
    assert len([op for op in purchased if op.startswith('detail/')])==len(brief['panels'])
    folder=mf.root(build)
    with zipfile.ZipFile(folder/'master-ai.zip') as archive:
        assert len(archive.namelist())==len(brief['panels'])+(11 if kind=='gloss' else 2)
        manifest=json.loads(archive.read('print-plates.json'))
        assert len(manifest['plates'])==(4 if kind=='gloss' else 0)
        for name in archive.namelist():
            if not name.endswith('.ai'):continue
            with fitz.open(stream=archive.read(name),filetype='pdf') as doc:
                assert set(v['name'] for v in doc.get_ocgs().values())==set(files.LAYERS)
                printed=doc[0].get_text()
                assert 'Full EN / ES / AR drafts' not in printed and 'An original collection name' not in printed
                assert all(len(doc.extract_font(font[0])[3])>0 for font in doc[0].get_fonts(full=True))
        if kind=='gloss':
            for panel,inks in manifest['plates'].items():
                assert set(inks)=={'white-frost','rose-gold'}
                for ink,row in inks.items():
                    assert files.sha(folder/'files'/row['file'])==row['sha256']
                    assert row['file'] in archive.namelist()
                    report=json.loads((folder/'files'/(panel+'-'+ink+'.json')).read_text())
                    assert report['ink_plate']['positive_monochrome']
            with fitz.open(folder/'files/body_front-rose-gold.ai') as doc:
                assert 'Lip' in doc[0].get_text() and not doc[0].get_image_info()
            original=json.loads((folder/'files/body_front.json').read_text())['rows']
            separated=json.loads((folder/'files/body_front-rose-gold.json').read_text())['rows']
            assert [(r['copy'],r['size_pt'],r['ink_box_mm']) for r in original]==[(r['copy'],r['size_pt'],r['ink_box_mm']) for r in separated]
    assert len((folder/'README.md').read_text().splitlines())<=80
    before=list(purchased);assert mf.run(build.pk)['status']=='complete';assert purchased==before
    assert record.state=='complete' and record.pick['id']=='A1'
    if kind=='gloss':
        from types import SimpleNamespace
        ctx=calls.MasterContext(build,SimpleNamespace(attempts=0))
        composite_before=files.sha(folder/'files/body_front.ai')
        for suffix in ('.ai','.png','.json'):
            path=folder/'files'/('body_front-white-frost'+suffix)
            path.rename(path.with_name('interrupted-fixture-'+path.name))
        art.build_files(ctx)
        assert files.sha(folder/'files/body_front.ai')==composite_before
        assert (folder/'files/body_front-white-frost.ai').exists()
        rose_before=files.sha(folder/'files/body_front-rose-gold.ai')
        art.apply_eye_repair(ctx,'body',art.objects(ctx)['body'],[
            {'kind':'type_box','panel':'body_front','index':0,'box':[.11,.2,.91,.23]}])
        assert files.sha(folder/'files/body_front-rose-gold.ai')!=rose_before
        assert files.sha(folder/'repairs/body/before/body_front-rose-gold.ai')==rose_before
        mapping=json.loads((folder/'print-plates.json').read_text())['plates']['body_front']
        assert mapping['rose-gold']['sha256']==files.sha(folder/'files/body_front-rose-gold.ai')
        with pytest.raises(ValueError,match='changed after'):art.eye(ctx)
        assert purchased==before


@pytest.fixture
def ideas_flow(queued, owner, monkeypatch):
    """Exercise the real queue dispatcher with deterministic, unpaid stage results."""
    from apps.pipeline.services import round_ideas, round_designer as round_ideas_brief, round_calls, round_steps, round_report
    observed, finalized, breaks = [], [], []
    ids = [f'A{index}' for index in range(1, 21)]

    def stage(context, name):
        observed.append(name)
        if name == 'seeds':
            return {'seeds': [{'id': key} for key in ids]}
        if name == 'designs':
            return {'candidates': ids}
        if name == 'pairwise':
            return {'order': ids, 'pair_count': 190}
        if name == 'pick_page':
            return {'order': ids[:3], 'candidates': {key: {'id': key} for key in ids[:3]}}
        raise AssertionError('Unexpected ideas stage: ' + name)

    def finish(context):
        finalized.append(context.round.pick.copy())
        return {'pick': context.round.pick, 'original_preserved': True}

    def legacy_forbidden(*args, **kwargs):
        raise AssertionError('An ideas-only round entered the historical workflow')

    monkeypatch.setattr(round_ideas, 'run_step', stage)
    monkeypatch.setattr(round_ideas, 'finalize_pick', finish)
    monkeypatch.setattr(flow, 'record_break', lambda record, job, error:
                        breaks.append({'round': record.pk, 'step': job.name,
                                       'attempt': job.attempts, 'error': error}))
    monkeypatch.setattr(round_calls.RoundContext, 'prepare_budget_plan', legacy_forbidden)
    monkeypatch.setattr(round_steps, 'run_step', legacy_forbidden)
    monkeypatch.setattr(round_steps, '_calibration', legacy_forbidden)
    monkeypatch.setattr(round_report, 'finalize', legacy_forbidden)
    monkeypatch.setattr(round_report, 'tag_if_requested', legacy_forbidden)
    monkeypatch.setattr(flow, '_prepare_repair', legacy_forbidden)
    monkeypatch.setattr(flow, 'repair_plan', legacy_forbidden)
    return {'brief': round_ideas_brief.gloss_brief(), 'pending': queued,
            'observed': observed, 'finalized': finalized, 'breaks': breaks, 'stage': stage}


@pytest.mark.django_db(transaction=True)
def test_ideas_round_uses_five_steps_ten_dollars_and_waits_for_owner(ideas_flow, owner):
    from apps.pipeline.services.round_ideas import IDEAS_STEPS
    data = ideas_flow
    token = uuid.uuid4().hex
    record = flow.create_round(data['brief'], owner, token)
    assert flow.create_round(data['brief'], owner, token).pk == record.pk
    assert Round.objects.count() == 1 and record.slug != 'r2-gloss'
    assert record.budget_usd == 10 and flow.steps_for(record) == IDEAS_STEPS
    progress = flow.summary(record)
    assert [row['name'] for row in progress['steps']] == list(IDEAS_STEPS)
    assert all(row['label'] and '_' not in row['label'] for row in progress['steps'])
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_pick' and not record.pick and not data['finalized']
    assert data['observed'] == ['seeds', 'designs', 'pairwise', 'pick_page']
    assert list(record.steps.values_list('name', flat=True)) == list(IDEAS_STEPS)
    assert not record.marks and record.marks_due_at is None
    assert not flow.marks_deadline(record.pk)
    with pytest.raises(ValueError, match='directly'):
        flow.submit_marks(record.pk, [{'id': 'A1', 'preserve': 'fixture'}], owner)
    with pytest.raises(ValueError, match='does not merge'):
        flow.submit_pick(record.pk, 'A1', 'fixture', owner, merge={'candidate': 'A2', 'element': 'stripe'})
    with pytest.raises(ValueError, match='final page'):
        flow.submit_pick(record.pk, 'A20', 'fixture', owner)
    flow.submit_pick(record.pk, 'A2', 'Its product idea.', owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'complete' and record.pick['id'] == 'A2'
    assert data['finalized'] == [record.pick]
    assert record.artifacts['pick']['original_preserved']
    assert record.steps.filter(state='complete').count() == 5
    assert flow.run_step_job(record.steps.get(name='pick').pk)['status'] == 'complete'
    assert data['finalized'] == [record.pick] and not data['breaks']


@pytest.mark.django_db(transaction=True)
def test_ideas_failed_stage_and_dispatch_recovery_preserve_completed_work(ideas_flow, owner, monkeypatch):
    from apps.pipeline.services import round_ideas
    data = ideas_flow
    record = flow.create_round(data['brief'], owner, uuid.uuid4().hex)
    first = data['pending'].pop(0)
    flow.run_step_job(first)
    data['pending'].clear()  # Simulate the committed designs outbox losing its broker publish.
    assert flow.run_step_job(first)['status'] == 'complete'
    assert len(data['pending']) == 1

    def broken(context, name):
        if name == 'designs':
            raise OSError('fixture image store unavailable')
        return data['stage'](context, name)

    monkeypatch.setattr(round_ideas, 'run_step', broken)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'failed' and record.current_step == 'designs'
    assert data['breaks'][-1]['step'] == 'designs'
    assert data['breaks'][-1]['error'] == 'OSError: fixture image store unavailable'
    failed = record.steps.get(name='designs')
    assert len(failed.history) == 1
    assert (flow.round_root(record) / 'failures' / 'designs-0-1.json').is_file()
    stranger = get_user_model().objects.create_user(username='ideas-stranger')
    with pytest.raises(PermissionDenied):
        flow.retry_round(record.pk, stranger)
    monkeypatch.setattr(round_ideas, 'run_step', data['stage'])
    flow.retry_round(record.pk, owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_pick' and data['observed'].count('seeds') == 1
    assert record.steps.get(name='designs').attempts == 1
    assert record.budget_usd == 10 and not record.marks


@pytest.mark.django_db(transaction=True)
def test_ideas_yield_resumes_same_step_without_a_failure_or_extra_attempt(ideas_flow, owner, monkeypatch):
    from apps.pipeline.services import round_ideas
    data = ideas_flow
    deliveries = []

    def resumable(context, name):
        if name == 'designs':
            deliveries.append(name)
            saved = context.root / 'fixture-paid-result.json'
            if not saved.exists():
                flow.write_json(saved, {'completed_call': 1})
                raise flow.YieldRound()
        return data['stage'](context, name)

    monkeypatch.setattr(round_ideas, 'run_step', resumable)
    record = flow.create_round(data['brief'], owner, uuid.uuid4().hex)
    drain(data['pending'])
    record.refresh_from_db()
    job = record.steps.get(name='designs')
    assert record.state == 'awaiting_pick' and deliveries == ['designs', 'designs']
    assert job.dispatches == 2 and job.attempts == 0 and not job.history
    assert not data['breaks']


@pytest.mark.django_db(transaction=True)
def test_ideas_broker_failures_enter_break_log_once_per_owner_attempt(owner, monkeypatch, tmp_path, settings):
    from apps.pipeline import tasks
    from apps.pipeline.services import round_ideas, round_designer as round_ideas_brief
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    breaks = []

    def unavailable(step_id):
        raise RuntimeError('fixture broker unavailable')

    monkeypatch.setattr(tasks.run_creative_round_step, 'delay', unavailable)
    monkeypatch.setattr(flow, 'record_break', lambda record, job, error:
                        breaks.append((job.name, job.attempts, error)))
    record = flow.create_round(round_ideas_brief.gloss_brief(), owner, uuid.uuid4().hex)
    record.refresh_from_db()
    job = record.steps.get(name='seeds')
    assert record.state == job.state == 'failed'
    assert breaks == [('seeds', 0, 'Queue delivery failed: RuntimeError: fixture broker unavailable')]
    flow._enqueue(job.pk)
    assert len(breaks) == 1
    flow.retry_round(record.pk, owner)
    job.refresh_from_db()
    assert [event['attempt'] for event in job.history] == [0, 1]
    assert [entry[1] for entry in breaks] == [0, 1]
    assert record.budget_usd == 10


@pytest.mark.django_db(transaction=True)
def test_ideas_secondary_break_failure_does_not_erase_concurrent_owner_retry(ideas_flow, owner, monkeypatch):
    from apps.pipeline.services import round_ideas
    data = ideas_flow
    record = flow.create_round(data['brief'], owner, uuid.uuid4().hex)

    def broken(context, name):
        raise OSError('fixture primary failure')

    def evidence_interrupted(current, job, error):
        flow.retry_round(current.pk, owner)
        raise OSError('fixture central break store unavailable')

    monkeypatch.setattr(round_ideas, 'run_step', broken)
    monkeypatch.setattr(flow, 'record_break', evidence_interrupted)
    outcome = flow.run_step_job(data['pending'].pop(0))
    record.refresh_from_db()
    job = record.steps.get(name='seeds')
    assert outcome['status'] == 'failed'
    assert record.state == job.state == 'queued' and job.attempts == 1
    assert len(job.history) == 1 and job.history[0]['error'] == 'OSError: fixture primary failure'
    assert 'central break store unavailable' in job.history[0]['evidence_error']


@pytest.mark.django_db(transaction=True)
def test_unknown_new_round_schema_is_rejected_before_queue(queued, owner):
    brief = lip_gloss_brief()
    brief['schema'] = 'product_stand_picture/999'
    with pytest.raises(ValueError, match='Unknown round brief schema'):
        flow.create_round(brief, owner, uuid.uuid4().hex)
    assert not queued and not Round.objects.exists()


SENTINEL = 'RESEARCH-SENTINEL-NEVER-TO-THE-IMAGE-MODEL'
WEB_SENTINEL = 'WEB-TAKEAWAY-SENTINEL'
LIBRARY_SENTINEL = 'LIBRARY-CAPTION-SENTINEL'
SEARCHED_URL = 'https://example.com/gloss-launches'


def _research_payload():
    line = 'Clear acrylic bodies read as colour first'
    return {'category': 'Lip gloss at a beauty counter', 'references': [SENTINEL, line],
            **{key: [line, 'Gold caps carry quiet marks'] for key in ('launches', 'materials', 'finishes', 'colour', 'type', 'avoid')},
            'sources': [{'url': SEARCHED_URL + '/', 'takeaway': WEB_SENTINEL + ' clear walls lead the shelf'},
                        {'url': 'https://never-returned.example/page', 'takeaway': 'A source the search never gave'}]}


TAVILY_KEY = 'tvly-fixture-key-never-written'


def _tavily_response(query):
    """A stubbed Tavily answer: one page (and a picture, which must never be kept), with its credit."""
    class Response:
        status_code = 200
        headers = {'x-request-id': 'tavily-fixture'}
        body = {'results': [{'url': SEARCHED_URL, 'title': 'Gloss launches', 'score': 0.9, 'published_date': '2026-09-01',
                             'content': WEB_SENTINEL + ' snippet for ' + query, 'images': ['https://example.com/pic.png']}],
                'images': ['https://example.com/pic.png'], 'usage': {'credits': 1}, 'request_id': 'tv-1'}
        content = json.dumps(body).encode()

        def json(self):
            return self.body
    return Response()


def _designer_reply(prompt):
    """Deterministic provider replies for the designer flow, chosen by the call's own prompt."""
    if prompt.startswith('You are a senior packaging'):
        payload = _research_payload()
        if 'Web search is unavailable for this round' in prompt:
            payload['sources'] = []
        return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(payload)}],
                'usage': {'input_tokens': 5000, 'output_tokens': 900}}
    elif prompt.startswith('Plan three mood boards'):
        second = 'THE OWNER REJECTED' in prompt
        payload = {'boards': [{'id': key, 'idea': f'{"Second" if second else "First"} {key} idea of light through clear walls',
                               'link': 'because the liquid shows its colour', 'type': 'A narrow high-contrast serif',
                               'motif': 'A ' + key + ' facet line', 'texture': 'Fine frosted grain',
                               'palette': [{'name': 'Rose glass', 'hex': '#c9707a', 'role': 'liquid'},
                                           {'name': 'Warm gold', 'hex': '#B8925A', 'role': 'cap'},
                                           {'name': 'Ink', 'hex': '#1F1A1C', 'role': 'type'},
                                           {'name': 'Paper', 'hex': '#F4EFEA', 'role': 'ground'}],
                               'materials': ['Clear acrylic', 'Rigid paperboard'], 'finishes': ['Hot foil', 'Soft-touch'],
                               'library': ['L1', 'L3', 'L99'],
                               # L3 is a house design and L99 does not exist: neither may become a picture.
                               'references': ['L1', 'L2', 'L3', 'L99'] if key == 'bold' else []}
                              for key in ('bold', 'refined', 'unexpected')]}
    elif prompt.startswith('Plan three designs'):
        ids = prompt.split('with exactly the ids ')[1].split('.')[0].split(', ')
        payload = {'designs': [{'id': key, 'idea': 'The facet line runs from cap to header ' + key,
                                'composition': f'Composition {key}: the hero stands at position {index}',
                                'header': 'The faceted dial fills the header front',
                                'faces': 'The facet line runs on across the walls and the back'}
                               for index, key in enumerate(ids)]}
    elif prompt.startswith('Quickly check'):
        ids = prompt.split('shown in order: ')[1].split('.')[0].split(', ')
        payload = {'designs': {key: {'banned': {'ok': True, 'note': 'No banned motif'},
                                     'words': {'ok': key != ids[0], 'note': 'No letters in the art'},
                                     'faces': {'ok': True, 'note': 'Every printed face is painted'}} for key in ids[1:]}}
    else:
        raise AssertionError('Unexpected designer prompt: ' + prompt[:80])
    return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(payload)}],
            'usage': {'input_tokens': 900, 'output_tokens': 700}}


def library_fixture(tmp_path, settings, monkeypatch):
    """A six-row Day 7 index with previews: two eligible house materials, a house design, a logo, a font, a quarantined row."""
    from PIL import Image
    from apps.pipeline.services import round_calls as image_guard
    from apps.pipeline.services.materials_retrieval import _hex_lab
    previews = tmp_path / 'previews'
    previews.mkdir()
    rows = []
    for char, kind, tags, colour, path, rights in (
            ('1', 'pattern', ['gold', 'acrylic', 'facet'], '#C9707A', 'materials/patterns/facets.png', {'tier': 'house'}),
            ('2', 'texture', ['clear', 'frost'], '#C8737C', 'materials/backgrounds/frost.png', {'tier': 'house'}),
            ('3', 'pattern', ['gold', 'wand'], '#B8925A', 'materials/house-designs/client-carton.png', {'tier': 'house'}),
            ('4', 'logo', ['gold', 'cap'], '#B8925A', 'materials/unknown/mark.png', {'tier': 'house'}),
            ('5', 'font', ['gold', 'gloss'], '#000000', 'materials/Fonts/a.otf', {'tier': 'GRANTED'}),
            ('6', 'pattern', ['gold', 'gloss'], '#C9707A', 'materials/unknown/b.png', {'tier': 'UNVERIFIED', 'excluded': True})):
        sha = char * 64
        Image.new('RGB', (40, 40), colour).save(previews / (sha + '.png'))
        rows.append({'sha256': sha, 'name': Path(path).name, 'paths': [path], 'kind': kind, 'tags': tags, 'style': [],
                     'subject': f'{LIBRARY_SENTINEL} {kind} {char}', 'colours': [{'hex': colour, 'lab': _hex_lab(colour), 'share': .6}],
                     'surfaces': [], 'rights': dict(rights, basis='fixture'), 'caption_source': 'day7-haiku',
                     'preview': True, 'preview_blank': False})
    index = tmp_path / 'materials-index.json'
    index.write_text(json.dumps({'schema': 'day7_materials_index/1', 'items': rows}))
    settings.MATERIALS_INDEX_PATH = str(index)
    settings.MATERIALS_PREVIEWS_ROOT = str(previews)
    settings.HOUSE_INDEX_PATH = str(tmp_path / 'no-house-index.json')
    monkeypatch.setattr(image_guard, 'denylist', lambda **kwargs: {'rejected': {}, 'web': {}})
    monkeypatch.setattr(image_guard, 'ALLOWED_ROOTS', image_guard.ALLOWED_ROOTS + (previews,))
    return previews


@pytest.fixture
def designer(queued, owner, monkeypatch, settings, tmp_path):
    """The real queue and paid boundary with deterministic fake providers and a fixture library; $0."""
    import base64
    from io import BytesIO
    from types import SimpleNamespace
    from PIL import Image
    from apps.pipeline.services import round_designer, round_designer as round_ideas_brief
    settings.IMAGE_MODEL = 'gpt-image-2'
    from apps.pipeline.services import web_research_tavily
    previews = library_fixture(tmp_path, settings, monkeypatch)
    sent = {'text': [], 'images': [], 'references': [], 'requests': [], 'tavily': []}
    settings.WEB_SEARCH_API_KEY = TAVILY_KEY
    settings.TAVILY_USD_PER_CREDIT = 0.008

    def tavily(url, *, json, headers, timeout):
        sent['tavily'].append(json)
        return sent['tavily_reply'](json['query'])

    sent['tavily_reply'] = _tavily_response
    monkeypatch.setattr(web_research_tavily.requests, 'post', tavily)

    def create(**kwargs):
        prompt = kwargs['messages'][0]['content'][-1]['text']
        sent['text'].append(prompt)
        sent['requests'].append(kwargs)
        return _designer_reply(prompt)

    def picture():
        output = BytesIO()
        Image.new('RGB', (1536, 1024), (len(sent['images']) * 9, 80, 60)).save(output, format='PNG')
        return {'data': [{'b64_json': base64.b64encode(output.getvalue()).decode()}],
                'usage': {'input_tokens': 700, 'output_tokens': 5488,
                          'input_tokens_details': {'image_tokens': 0, 'text_tokens': 700}}}

    def generate(**kwargs):
        sent['images'].append(kwargs['prompt'])
        sent['references'].append([])
        return picture()

    def edit(*, image, mask=None, stream=False, partial_images=0, **kwargs):
        sent['images'].append(kwargs['prompt'])
        sent['references'].append([Path(handle.name) for handle in image])
        if not stream:
            return picture()
        template = Image.open(image[0]).convert('RGBA')       # a flat design: the die's printed faces painted
        image[0].seek(0)
        painted = Image.new('RGB', template.size, (40, 60, 110 + len(sent['images'])))
        painted.paste(template.convert('RGB'), mask=template.getchannel('A'))
        output = BytesIO()
        painted.save(output, format='PNG')
        b64 = base64.b64encode(output.getvalue()).decode()
        return [{'type': 'image_edit.partial_image', 'partial_image_index': 0, 'b64_json': b64[:64]},
                {'type': 'image_edit.completed', 'b64_json': b64, 'usage': picture()['usage']}]

    original = round_designer.DesignerContext.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
        self.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate, edit=edit))

    monkeypatch.setattr(round_designer.DesignerContext, '__init__', init)
    brief = dict(round_ideas_brief.gloss_brief(), flow=round_ideas_brief.DESIGNER_FLOW)
    return {'brief': brief, 'pending': queued, 'sent': sent, 'previews': previews}


@pytest.mark.django_db(transaction=True)
def test_designer_flow_runs_from_start_to_the_frozen_handoff_with_one_redo_per_pick(designer, owner):
    from apps.pipeline.services import round_designer, round_files_gate as round_files_job, spend_reservation as spend
    from apps.pipeline.services.round_calls import scoped_spend
    from apps.pipeline.services.round_designer import gloss_brief, normalize_ideas_brief, printed_copy
    data, sent = designer, designer['sent']
    record = flow.create_round(data['brief'], owner, uuid.uuid4().hex)
    assert record.product_brief['flow'] == 'designer/1' and normalize_ideas_brief(gloss_brief()) == gloss_brief()
    assert record.current_step == 'research' and record.budget_usd == 10
    assert flow.steps_for(record) == round_designer.DESIGNER_STEPS
    assert [row['name'] for row in flow.summary(record)['steps']] == list(round_designer.DESIGNER_STEPS)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick' and record.current_step == 'board_pick'
    boards = record.artifacts['boards']
    assert boards['order'] == ['bold', 'refined', 'unexpected'] and len(boards['files']) == 3
    assert boards['taste_used'] == 0 and boards['candidates']['bold']['palette'][0]['hex'] == '#C9707A'
    root = flow.round_root(record)
    request = json.loads((root / 'research' / 'notes-call.request.json').read_text())
    assert 'tools' not in request and request['images'] == []
    assert not any('tools' in body for body in sent['requests'])  # No Anthropic web search tool anywhere.
    # The stubbed Tavily search: six queries of the product type and topic words, no picture asked for or kept.
    assert [body['query'] for body in sent['tavily']] == [row['query'] for row in round_designer.search_queries(record.product_brief, 2026)]
    assert all(body['include_images'] is False for body in sent['tavily'])
    assert not any(word in body['query'].lower() for body in sent['tavily'] for word in ('bbrose', 'rose glass', 'ملمع'))
    research = record.artifacts['research']
    assert research['search_provider'] == 'tavily' and research['web_search'] == 'used'
    assert [row['url'] for row in research['sources']] == [SEARCHED_URL] and research['unverified_sources'] == 1
    assert [row['status'] for row in research['searches']] == ['complete'] * 6
    assert SEARCHED_URL in sent['text'][0] and WEB_SENTINEL in sent['text'][0] and 'pic.png' not in sent['text'][0]
    with spend._connect() as db:
        searches = [dict(row) for row in db.execute('SELECT state,accounted FROM calls WHERE operation=?',
                                                     (f'round/{record.slug}/research/search',))]
    assert searches == [{'state': 'usage_recorded', 'accounted': 8000}] * 6  # $0.008 each, inside the round's cap.
    assert not any(TAVILY_KEY in path.read_text(errors='ignore') for path in root.rglob('*') if path.is_file())
    # The fixture library: house-tier matches with previews; only eligible materials may become pictures.
    matches = research['library']['matches']
    assert [row['sha256'][0] for row in matches] == ['1', '2', '3', '4'] and [row['id'] for row in matches] == ['L1', 'L2', 'L3', 'L4']
    assert [row['may_reference'] for row in matches] == [True, True, False, False]
    assert 'house design' in matches[2]['why_words_only'] and 'logo' in matches[3]['why_words_only']
    bold = boards['candidates']['bold']
    assert bold['library'] == ['L1', 'L3'] and bold['references'] == ['L1', 'L2']
    assert bold['references_not_taken'] == ['L3', 'L99'] and boards['candidates']['refined']['reference_inputs'] == []
    assert [row['sha256'] for row in bold['reference_inputs']] == [matches[0]['preview_sha256'], matches[1]['preview_sha256']]
    assert [path.name for path in sent['references'][0]] == ['1' * 64 + '.png', '2' * 64 + '.png']
    assert 'house-library samples' in sent['images'][0] and 'house-library samples' not in sent['images'][1]
    assert WEB_SENTINEL in sent['text'][1] and LIBRARY_SENTINEL in sent['text'][1] and SEARCHED_URL not in sent['text'][1]
    # None of these, once: three new boards answer the owner's line.
    flow.none_of_these(record.pk, 'boards', 'Too quiet; I want contrast', owner)
    with pytest.raises(ValueError, match='once per pick'):
        flow.none_of_these(record.pk, 'boards', 'Another line', owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick' and record.artifacts['boards']['generation'] == 2
    assert record.artifacts['rejected_boards']['boards']['generation'] == 1
    assert 'Too quiet; I want contrast' in sent['text'][2] and record.artifacts['boards']['redo']
    with pytest.raises(ValueError, match='once per pick'):
        flow.none_of_these(record.pk, 'boards', 'Too quiet again', owner)
    with pytest.raises(ValueError, match='three boards'):
        flow.submit_board_pick(record.pk, 'missing', '', owner)
    flow.submit_board_pick(record.pk, 'unexpected', '', owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_pick' and record.artifacts['board_pick']['id'] == 'unexpected'
    first = record.artifacts['pick_page']
    assert first['order'] == ['D1', 'D2', 'D3'] and first['flow'] == 'designer/1'
    findings = first['candidates']['D1']['findings']
    assert [row['ok'] for row in findings] == [None, None, None]  # Missing reading: a finding, never a removal.
    assert [row['ok'] for row in first['candidates']['D2']['findings']] == [True, True, True]
    check = json.loads((root / 'designs' / 'g1' / 'check-call.json').read_text())
    canvas = record.artifacts['designs']['candidates']['D1']['size_px']
    view = [1152, 768] if canvas[0] > canvas[1] else [768, 1152]
    assert [item['px'] for item in check['images']] == [view] * 3  # Reading copies of the flat dies; originals untouched.
    # The die first: solved from the brief before any design, its template the input of every design.
    die = record.artifacts['designs']['die']
    assert json.loads((root / die['stand']).read_text())['record']['schema'] == 'counter_tray_header/product-grid-2'
    d1 = record.artifacts['designs']['candidates']['D1']
    assert d1['proof']['outside']['differing_from_template'] == 0 and d1['folded'] and d1['loaded']
    assert first['contract'] == 'flat_die_design/1' and first['candidates']['D1']['die_line'].startswith('Die match: 0 of')
    flow.none_of_these(record.pk, 'designs', 'The three stands look alike', owner)
    drain(data['pending'])
    record.refresh_from_db()
    page = record.artifacts['pick_page']
    assert record.state == 'awaiting_pick' and page['order'] == ['D4', 'D5', 'D6'] and page['generation'] == 2
    with pytest.raises(ValueError, match='once per pick'):
        flow.none_of_these(record.pk, 'designs', 'Again', owner)
    with pytest.raises(ValueError, match='final page'):
        flow.submit_pick(record.pk, 'D1', 'An earlier design', owner)
    flow.submit_pick(record.pk, 'D5', 'The header carries the cap’s facet', owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'complete' and record.steps.filter(state='complete').count() == 6
    handoff = json.loads((root / 'handoff.json').read_text())
    assert handoff['schema'] == 'flat_die_handoff/1' and handoff['id'] == 'D5'
    assert handoff['picture'] == 'designs/g2/D5/flat.png' and handoff['reason'] == record.pick['reason']
    from apps.pipeline.services import round_files_gate as round_files_flow
    with pytest.raises(ValueError, match='flat die'):                  # said in words; nothing started or spent
        round_files_flow.start(record.pk, owner)
    # Twelve pictures; research words never reached the image model; designs keep the frozen format.
    assert len(sent['images']) == 12 and any(SENTINEL in prompt for prompt in sent['text'])
    for prompt in sent['images']:
        for marker in (SENTINEL, WEB_SENTINEL, LIBRARY_SENTINEL, SEARCHED_URL, 'RESEARCH', 'example.com'):
            assert marker not in prompt
    # Library pictures go only to the bold boards; a design is the die's template with the picked board as its style.
    assert [bool(paths) for paths in sent['references']] == [True, False, False, True, False, False] + [True] * 6
    assert all(path.parent == data['previews'] for paths in sent['references'][:6] for path in paths)
    for paths in sent['references'][6:]:
        assert [path.name for path in paths] == ['template.png', 'raw.png'] and paths[1].parent.parent.name == 'g2'
    for prompt in sent['images'][6:]:
        assert prompt.startswith('Image 1 is a flat die') and round_designer.COPY_START not in prompt
        assert 'BBROSE' not in prompt and 'Rose Glass' not in prompt and 'No letters, numbers or words' in prompt
    spend = scoped_spend(record)
    assert spend['image_calls'] == 12 and spend['reserved_usd'] == 0 and spend['accounted_usd'] < 10
    assert not (flow.round_root(record).parent / 'BREAKS.md').exists()
    # Taste memory: the next round's boards are guided by these picks and lines, and say so.
    following = flow.create_round(data['brief'], owner, uuid.uuid4().hex)
    drain(data['pending'])
    following.refresh_from_db()
    taste = json.loads((flow.round_root(following) / 'taste.json').read_text())['entries']
    assert [row['kind'] for row in taste] == ['board', 'none_of_these', 'none_of_these', 'design']
    assert taste[-1]['reason'] == record.pick['reason'] and following.artifacts['boards']['taste_used'] == 4
    assert 'THE OWNER’S PAST PICKS' in sent['text'][-1] and 'The three stands look alike' in sent['text'][-1]


@pytest.mark.django_db(transaction=True)
def test_designer_break_is_logged_and_owner_retry_continues(designer, owner, monkeypatch):
    replies, valid_reply = [], _designer_reply

    def broken_once(prompt):
        if prompt.startswith('You are a senior packaging') and not replies:
            replies.append('broken')
            return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{"category": ""}'}],
                    'usage': {'input_tokens': 900, 'output_tokens': 70}}
        return valid_reply(prompt)

    monkeypatch.setitem(globals(), '_designer_reply', broken_once)
    record = flow.create_round(designer['brief'], owner, uuid.uuid4().hex)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'failed' and record.current_step == 'research'
    breaks = (flow.round_root(record).parent / 'BREAKS.md').read_text()
    assert f'{record.slug} — research' in breaks and 'Research needs its category' in breaks
    flow.retry_round(record.pk, owner)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick', record.error_message
    assert breaks.count('<!-- stop:') == (flow.round_root(record).parent / 'BREAKS.md').read_text().count('<!-- stop:')


@pytest.mark.django_db
def test_designer_library_matches_house_previews_by_words_and_colours(settings, monkeypatch, tmp_path):
    from apps.pipeline.services import round_designer, round_designer as round_ideas_brief
    previews = library_fixture(tmp_path, settings, monkeypatch)
    brief = round_ideas_brief.gloss_brief()
    library = round_designer.library_matches(brief)
    assert 'gloss' in library['words'] and 'square' not in library['words']
    assert library['colours'] == ['#C9707A', '#8E4A5C', '#C2553A']
    matches = library['matches']
    assert [row['sha256'][0] for row in matches] == ['1', '2', '3', '4']  # No font, nothing quarantined.
    assert all(Path(row['preview_path']).parent == previews and len(row['preview_sha256']) == 64 for row in matches)
    assert [row['may_reference'] for row in matches] == [True, True, False, False]
    # The real guard decides at research time: a preview it refuses stays words only, with its reason.
    from apps.pipeline.services import round_calls as image_guard
    monkeypatch.setattr(image_guard, 'denylist', lambda **kwargs: {'rejected': {matches[1]['preview_sha256']: 'a made design'}, 'web': {}})
    refused = round_designer.library_matches(brief)['matches']
    assert refused[1]['may_reference'] is False and 'D-D8-2' in refused[1]['why_words_only']


class _Refused(Exception):
    """A provider 403 as the SDK raises it: unbilled, carrying its status code."""
    status_code = 403


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('failure', ['http', 'no_key'])
def test_designer_tavily_failure_carries_on_with_library_and_knowledge_and_says_so(designer, owner, settings, failure):
    from django.test import Client

    class Down:
        status_code, headers, content = 503, {}, b'{}'

        def json(self):
            return {}
    if failure == 'http':
        designer['sent']['tavily_reply'] = lambda query: Down()
    else:
        settings.WEB_SEARCH_API_KEY = ''
    record = flow.create_round(designer['brief'], owner, uuid.uuid4().hex)
    drain(designer['pending'])
    record.refresh_from_db()
    research = record.artifacts['research']
    assert record.state == 'awaiting_board_pick' and research['web_search'] == 'unavailable'
    assert research['sources'] == [] and research['library']['matches'] and [row['status'] for row in research['searches']] == ['failed'] * 6
    assert 'Web search is unavailable for this round' in designer['sent']['text'][0]
    assert not any('tools' in body for body in designer['sent']['requests'])
    owner.is_superuser = True
    owner.save()
    page = Client()
    page.force_login(owner)
    html = page.get(f'/dashboard/rounds/{record.pk}/research/', HTTP_HOST='127.0.0.1', secure=True).content.decode()
    assert 'Web search unavailable' in html and 'no web source for this round' in html


@pytest.mark.django_db(transaction=True)
def test_designer_research_refused_by_the_api_stops_in_words_and_retry_does_not_search_twice(designer, owner, monkeypatch):
    valid_reply = _designer_reply

    def refused(prompt):
        if prompt.startswith('You are a senior packaging'):
            raise _Refused('Error code: 403 - Request not allowed')
        return valid_reply(prompt)

    monkeypatch.setitem(globals(), '_designer_reply', refused)
    record = flow.create_round(designer['brief'], owner, uuid.uuid4().hex)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'failed' and 'VPN' in record.error_message and '403' in record.error_message
    assert 'Request not allowed' in (flow.round_root(record).parent / 'BREAKS.md').read_text()
    monkeypatch.setitem(globals(), '_designer_reply', valid_reply)  # The network is back.
    flow.retry_round(record.pk, owner)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick' and record.artifacts['research']['web_search'] == 'used'
    assert len(designer['sent']['tavily']) == 6  # The saved searches are read again, never bought twice.
