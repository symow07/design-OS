"""Unpaid queued-worker fixtures for the frozen-picture execution half.

Only queue delivery and the text provider are substituted. Extraction, the
stand engine, type shaping, PDF operators, readback and publication are real.
Native Illustrator is explicitly excluded from this fixture's claims.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import zipfile

import fitz
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.pipeline import tasks
from apps.pipeline.models import Round, RoundMaster
from apps.pipeline.services import round_calls, round_files_art, round_files_export
from apps.pipeline.services import round_files_flow as files_flow
from apps.pipeline.services import round_files_job as job
from apps.pipeline.services import round_flow as flow, round_ideas_brief, spend_reservation as spend
from apps.pipeline.services import round_files_attempt as attempt
from apps.pipeline.tests.test_round_files_art import fixture as picture_fixture


pytestmark = pytest.mark.django_db(transaction=True)
INSTRUCTION = 'INSTRUCTION SENTINEL: stretch the moon across the shelf'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reply(payload, stop_reason='end_turn'):
    return {'stop_reason': stop_reason,
            'content': [{'type': 'text', 'text': json.dumps(payload, ensure_ascii=False)}],
            'usage': {'input_tokens': 100, 'output_tokens': 100,
                      'output_tokens_details': {'thinking_tokens': 25}}}


@pytest.fixture
def execution(tmp_path, settings, monkeypatch):
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    settings.SECURE_SSL_REDIRECT = False
    source, _, inspection = picture_fixture(tmp_path)
    inspection['panels']['body_front']['text'][-1]['field'] = 'shade_2'
    inspection['panels']['cap_front']['text'] = [{
        'field': 'product_latin', 'box_px': [90, 25, 145, 45],
        'color': '#D5AF59', 'rotation': 0}]
    # Retain the same synthetic source, with realistic stand-face proportions.
    header = inspection['panels']['stand_header']
    header.update(crop_px=[160, 40, 240, 100],
        print_polygon_px=[[160, 55], [200, 40], [240, 55], [240, 100], [160, 100]],
        lineart_boxes_px=[[160, 40, 240, 100]])
    base = inspection['panels']['stand_base']
    base.update(crop_px=[240, 80, 320, 104],
        print_polygon_px=[[240, 80], [320, 80], [320, 104], [240, 104]],
        lineart_boxes_px=[[240, 80, 320, 104]])
    inspection['stand']['bottles'] = [
        {'row': row, 'column': column, 'box_px': [10 + column * 20, 5, 25 + column * 20, 100],
         'shade_field': ['shade_1', 'shade_0', None, 'shade_2'][column]}
        for row in range(3) for column in range(4)]
    inspection.update(unprinted_faces=[{'face': 'back', 'reason': 'Not visible in the picked picture.'}],
                      notes=['Twelve products in three aligned rows.', INSTRUCTION])
    brief = round_ideas_brief.gloss_brief()
    brief['truths'].append(INSTRUCTION)
    brief['bar'] = INSTRUCTION
    owner = get_user_model().objects.create_superuser(
        username='files-owner-' + uuid4().hex, email='files@example.invalid', password='fixture-password')
    record = Round.objects.create(slug='files-fixture-' + uuid4().hex,
        request_key=uuid4().hex, created_by=owner, product_brief=brief,
        state='complete', current_step='pick', budget_usd=10,
        pick={'id': 'C2', 'reason': 'Keep the picture and make the header top square.'})
    root = flow.round_root(record)
    relative = 'designs/C2/raw.png'
    picture = root / relative
    picture.parent.mkdir(parents=True)
    picture.write_bytes(source.read_bytes())
    card = {'id': 'C2', 'picture': relative, 'picture_sha256': sha(picture),
            'idea': 'Gold lines hold coloured glass above a matching counter stand.',
            'directory': 'designs/C2'}
    publication = {'schema': 'product_stand_publication/1', 'order': ['C2'],
                   'candidates': {'C2': card}, 'files': {relative: sha(picture)}}
    record.artifacts = {'pick_page': publication}
    record.save()
    flow.write_json(root / 'handoff.json', {
        'schema': 'product_stand_handoff/1', 'contract': round_ideas_brief.CONTRACT,
        'id': 'C2', 'picture': relative, 'picture_sha256': sha(picture),
        'size_px': inspection['image_size_px'], 'reason': record.pick['reason'],
        'source_round': record.pk, 'execution': 'Use this full-size picture as is; never redraw it.'})

    pending, dispatches, eye_replies = [], [], []
    prompts = []
    def text_create(**kwargs):
        assert kwargs['thinking'] == {'type': 'adaptive'}
        assert kwargs['max_tokens'] >= 16384
        prompt = kwargs['messages'][0]['content'][-1]['text']
        prompts.append(prompt)
        if 'Read this one picked picture for print-file extraction.' in prompt:
            assert kwargs['output_config'] == {'effort': 'medium'}
            return reply(deepcopy(inspection))
        assert prompt.startswith('You are the designer’s eye.')
        assert kwargs['output_config'] == {'effort': 'low'}
        if eye_replies:
            return deepcopy(eye_replies.pop(0))
        return reply({'verdict': 'pass', 'findings': [], 'repair': None})
    provider = Mock(name='explicit unpaid text provider')
    provider.messages.create.side_effect = text_create
    original_context = job.FilesContext
    contexts = []
    def context(build, step):
        value = original_context(build, step, text_client=provider, native=False)
        contexts.append(value)
        return value
    monkeypatch.setattr(job, 'FilesContext', context)
    delivery = Mock(name='queued task delivery', side_effect=pending.append)
    monkeypatch.setattr(tasks.run_round_files, 'delay', delivery)
    client = Client()
    client.force_login(owner)

    def drain(*, allow_failure=False):
        while pending:
            build_id = pending.pop(0)
            build = RoundMaster.objects.get(pk=build_id)
            before = provider.messages.create.call_count
            calls_before = job.scoped_spend(build)['calls']
            dispatches.append(build.current_step)
            result = tasks.run_round_files(build_id)
            assert provider.messages.create.call_count - before <= 2  # One bounded truncation retry.
            assert job.scoped_spend(build)['calls'] - calls_before <= 1
            assert len(dispatches) <= 20
            if result['status'] == 'failed':
                assert allow_failure, result
                assert not pending
                break
        build = RoundMaster.objects.get(round=record)
        return build

    return SimpleNamespace(owner=owner, record=record, root=root, picture=picture,
        source_bytes=picture.read_bytes(), inspection=inspection, brief=brief, pending=pending,
        dispatches=dispatches, provider=provider, delivery=delivery, eye_replies=eye_replies,
        prompts=prompts, contexts=contexts, drain=drain, client=client,
        round_artifacts=deepcopy(record.artifacts), pick=deepcopy(record.pick))


def assert_published_files(execution, build):
    assert build.state == 'complete'
    assert tuple(build.steps) == files_flow.STEPS or set(build.steps) == set(files_flow.STEPS)
    assert all(row['state'] == 'complete' for row in build.steps.values())
    assert set(execution.dispatches) == set(files_flow.STEPS)
    folder = files_flow.root(build)
    assert (folder / 'source.png').read_bytes() == execution.source_bytes
    assert execution.picture.read_bytes() == execution.source_bytes
    published = build.publication
    assert published['eye']['verdict'] == 'pass'
    assert published['download'] == 'files.zip'
    assert published['picture'] == 'source.png'
    for relative, pin in published['files'].items():
        path = (folder / relative).resolve()
        assert path.is_relative_to(folder)
        assert sha(path) == pin
    with zipfile.ZipFile(folder / published['download']) as archive:
        names = archive.namelist()
        ai = [name for name in names if name.endswith('.ai')]
        assert len(ai) == 3
        assert len([name for name in names if name.endswith('.png')]) >= 4
        assert any('drawing' in name and name.endswith('.png') for name in names)
        for name in ai:
            with fitz.open(stream=archive.read(name), filetype='pdf') as reopened:
                assert {layer['name'] for layer in reopened.get_ocgs().values()} == set(round_files_export.LAYERS)
    live_copy = []
    logos = []
    for path in folder.glob('revisions/*/**/*.export.json'):
        output = read(path)
        report = round_files_export.read_back_ai(output['ai'], output['type'], output['elements'])
        assert report['pdf_compatible_holds'], report['checks']
        assert report['checks']['die_guides_locked_nonprinting']
        assert not output['native']['requested'] and not output['native']['holds']
        assert not output['readback']['native_illustrator_validated']
        live_copy.extend(row['copy'] for row in output['type'])
        logos.extend(row for row in output['elements'] if row.get('approved_master'))
        assert all(row['font_sha256'] == round_files_export.FONT_PINS[row['face']] for row in output['type'])
        if output['id'] == 'cap':
            assert output['type'] and all(row['foil'] for row in output['type'])
    assert {'Lip Gloss', 'ملمع شفاه', 'Rose Glass'} <= set(live_copy)
    assert set(live_copy) <= set(round_files_art.copy_fields(execution.brief).values())
    assert INSTRUCTION not in '\n'.join(live_copy) and 'MODEL INVENTION' not in '\n'.join(live_copy)
    assert logos and all(row['sha256'] == round_files_export.LOGO_SHA256 for row in logos)
    revision = folder / 'revisions' / str(published['revision'])
    drawing = read(revision / 'product-drawing.json')
    assert drawing['hero']['shade_field'] == 'shade_2'
    assert drawing['hero']['liquid_colour'] == execution.brief['shades'][2]['hex']
    expected = {1: 'shade_1', 2: 'shade_0', 3: None, 4: 'shade_2'}
    assert all(row['shade_field'] == expected[row['column']] for row in drawing['stand_slots'])
    assert all(row['liquid_colour'] is None for row in drawing['stand_slots'] if row['shade_field'] is None)
    assert drawing['shade_loading']['unresolved_count'] == 3
    assert 'Only the picked hero bottle master is supplied' in drawing['bottle_master_scope']
    master = read(revision / 'bottle-front.export.json')
    original_shade = next(row for row in master['type'] if row['copy'] == 'Ember Glow')
    for field in ('shade_0', 'shade_1', 'unresolved'):
        proof = read(revision / 'proof-variants' / field / ('bottle-proof-' + field + '.export.json'))
        assert not proof['native']['requested']
        assert [row for row in proof['elements'] if row['kind'] != 'live_type'] == [
            row for row in master['elements'] if row['kind'] != 'live_type']
        if field == 'unresolved':
            assert 'Ember Glow' not in [row['copy'] for row in proof['type']]
        else:
            copied = round_files_art.copy_fields(execution.brief)[field]
            label = next(row for row in proof['type'] if row['copy'] == copied)
            for unchanged in ('box_mm', 'size_pt', 'face', 'font_sha256', 'foil', 'rotation', 'align'):
                assert label[unchanged] == original_shade[unchanged]
    assert 'other loaded shades are derived label proofs' in (folder / 'README.md').read_text()
    for name in files_flow.STEPS:
        assert (folder / 'steps' / (name + '.json')).is_file()
    execution.record.refresh_from_db()
    assert execution.record.state == 'complete' and execution.record.pick == execution.pick
    assert execution.record.artifacts == execution.round_artifacts


def test_owner_start_queued_worker_builds_real_files_and_is_idempotent(execution):
    first_half = 'round/' + execution.record.slug + '/'
    # A different half's held allowance is evidence of namespace separation.
    day_one_id = spend.reserve('anthropic', first_half + 'fixture-prior-half', round_calls.TEXT_MODEL,
                              9.8, budget_prefix=first_half, prefix_cap=10)
    response = execution.client.post(reverse('dashboard:product_round_files_start', args=[execution.record.pk]))
    assert response.status_code == 302
    assert response.url == reverse('dashboard:product_round_files', args=[execution.record.pk])
    build = RoundMaster.objects.get(round=execution.record)
    assert build.budget_usd == 10 and build.inputs['budget_usd'] == 10
    assert build.inputs['picture_sha256'] == sha(execution.picture)
    assert build.inputs['fonts'] == round_files_export.font_records()
    assert execution.pending == [build.pk] and execution.provider.messages.create.call_count == 0
    assert files_flow.start(execution.record.pk, execution.owner).pk == build.pk
    assert execution.pending == [build.pk] and RoundMaster.objects.count() == 1
    build = execution.drain()
    assert_published_files(execution, build)
    assert execution.provider.messages.create.call_count == 2
    assert job.scoped_spend(build)['budget_usd'] == 10
    assert 0 < job.scoped_spend(build)['accounted_usd'] < 10
    assert round_calls.scoped_spend(execution.record)['accounted_usd'] == 9.8
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls')]
    assert next(row for row in rows if row['id'] == day_one_id)['state'] == 'reserved'
    files_calls = [row for row in rows if row['operation'].startswith('files/')]
    assert len(files_calls) == 2 and all(row['state'] == 'usage_recorded' for row in files_calls)
    assert all(row['provider'] == 'anthropic' for row in files_calls)
    before = deepcopy(build.publication)
    assert tasks.run_round_files(build.pk)['status'] == 'complete'
    assert files_flow.start(execution.record.pk, execution.owner).pk == build.pk
    build.refresh_from_db()
    assert build.publication == before and execution.provider.messages.create.call_count == 2
    assert not execution.pending
    download = execution.client.get(reverse('dashboard:product_round_files_download',
                                            args=[execution.record.pk, 'files.zip']))
    assert download.status_code == 200
    assert download.content == (files_flow.root(build) / 'files.zip').read_bytes()


def test_owner_retry_preserves_frozen_input_after_queue_failure(execution):
    execution.delivery.side_effect = ConnectionError('Fixture queue is unavailable')
    build = files_flow.start(execution.record.pk, execution.owner)
    build.refresh_from_db()
    assert build.state == 'failed' and build.current_step == 'read'
    assert build.steps['read']['history'][0]['kind'] == 'queue delivery'
    assert execution.provider.messages.create.call_count == 0
    frozen = deepcopy(build.inputs)
    execution.delivery.side_effect = execution.pending.append
    files_flow.retry(execution.record.pk, execution.owner)
    build = execution.drain()
    assert_published_files(execution, build)
    assert build.inputs == frozen and build.steps['read']['attempts'] == 1
    assert len(build.steps['read']['history']) == 1
    failures = list((files_flow.root(build) / 'failures').glob('*.json'))
    assert len(failures) == 1 and read(failures[0])['kind'] == 'queue delivery'
    journal = (execution.root.parent / 'BREAKS.md').read_text()
    assert journal.count('Fixture queue is unavailable') == 1


def test_changed_frozen_picture_stops_before_provider_and_retry_cannot_repin_it(execution):
    build = files_flow.start(execution.record.pk, execution.owner)
    frozen = deepcopy(build.inputs)
    execution.picture.write_bytes(b'changed fixture bytes')
    build = execution.drain(allow_failure=True)
    assert build.state == 'failed' and not build.publication
    assert 'changed' in build.error
    assert execution.provider.messages.create.call_count == 0
    files_flow.retry(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=True)
    assert build.state == 'failed' and build.inputs == frozen
    assert execution.provider.messages.create.call_count == 0
    assert not (files_flow.root(build) / 'files.zip').exists()


def test_execution_cap_stops_before_provider_independently_of_first_half(execution):
    build = files_flow.start(execution.record.pk, execution.owner)
    prefix = 'files/' + execution.record.slug + '/'
    spend.reserve('anthropic', prefix + 'fixture-held', round_calls.TEXT_MODEL,
                  9.99, budget_prefix=prefix, prefix_cap=10)
    build = execution.drain(allow_failure=True)
    assert build.state == 'failed' and 'allowance' in build.error
    assert not build.publication and execution.provider.messages.create.call_count == 0
    assert job.scoped_spend(build)['held_usd'] == 9.99
    assert round_calls.scoped_spend(execution.record)['calls'] == 0


@pytest.mark.parametrize('mode', ['repair_pass', 'repair_again', 'invalid', 'truncated_twice'])
def test_eye_is_bounded_and_only_a_complete_pass_publishes(execution, mode):
    repair = {'verdict': 'needs_attention', 'findings': ['The product words need a small size adjustment.'],
              'repair': {'kind': 'type_size', 'object_id': 'bottle-front', 'run_index': 0, 'scale': 1.05}}
    if mode == 'repair_pass':
        execution.eye_replies[:] = [reply(repair), reply({'verdict': 'pass', 'findings': [], 'repair': None})]
    elif mode == 'repair_again':
        execution.eye_replies[:] = [reply(repair), reply(repair)]
    elif mode == 'invalid':
        execution.eye_replies[:] = [reply({'findings': []})]
    else:
        execution.eye_replies[:] = [reply({'verdict': 'pass'}, 'max_tokens'), reply({'verdict': 'pass'}, 'max_tokens')]
    files_flow.start(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=mode != 'repair_pass')
    folder = files_flow.root(build)
    assert execution.provider.messages.create.call_count == (2 if mode == 'invalid' else 3)
    assert not (folder / 'review' / 'eye-3.json').exists()
    assert (folder / 'review' / 'eye-1.json').exists()
    if mode.startswith('repair_'):
        assert (folder / 'review' / 'eye-2.json').exists()
        original = next((folder / 'revisions' / '0').rglob('bottle-front.export.json'))
        repaired = next((folder / 'revisions' / '1').rglob('bottle-front.export.json'))
        before, after = read(original), read(repaired)
        assert before['type'][0]['box_mm'] == after['type'][0]['box_mm']
        assert after['type'][0]['size_pt'] == pytest.approx(before['type'][0]['size_pt'] * 1.05)
        assert sha(before['ai']) == before['sha256']  # Revision zero remains immutable.
        assert not (folder / 'revisions' / '2').exists()
    if mode == 'repair_pass':
        assert_published_files(execution, build)
    else:
        assert build.state == 'failed' and build.current_step == 'eye' and not build.publication
        assert build.steps['publish']['state'] == 'waiting'
        assert not (folder / 'files.zip').exists()
        provider_calls = execution.provider.messages.create.call_count
        files_flow.retry(execution.record.pk, execution.owner)
        build = execution.drain(allow_failure=True)
        assert build.state == 'failed' and not build.publication
        assert execution.provider.messages.create.call_count == provider_calls
        if mode == 'truncated_twice':
            saved = read(folder / 'review' / 'eye-1.json')
            assert saved['status'] == 'incomplete' and saved['attempts'] == 2
            assert saved['stop_reason'] == 'max_tokens'


@pytest.mark.parametrize('mode', ['pass', 'needs_attention', 'truncated', 'interrupted_repair'])
def test_owner_retry_runs_one_mechanical_repair_and_only_the_second_eye(execution, monkeypatch, mode):
    first = {'verdict': 'needs_attention', 'findings': [
        'The source edges and provisional stand seating need mechanical correction.'], 'repair': None}
    execution.eye_replies[:] = [reply(first)]
    files_flow.start(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=True)
    folder = files_flow.root(build)
    assert build.state == 'failed' and build.current_step == 'eye'
    assert execution.provider.messages.create.call_count == 2
    assert not (folder/'review/repair.json').exists()
    assert not (folder/'revisions/1').exists()
    first_verdict = (folder/'review/verdict.json').read_bytes()
    preserved_paths = [folder/name for name in ('source.png', 'inspection.json', 'art.json', 'stand.json', 'reading-call.json')]
    preserved_paths += [path for directory in ('art', 'stand', 'revisions/0', 'review/views/0')
                        for path in (folder/directory).rglob('*') if path.is_file()]
    preserved_paths += list((folder/'review').glob('eye-1.*json'))
    pins = {path: sha(path) for path in preserved_paths}
    if mode == 'truncated':
        execution.eye_replies[:] = [reply({'verdict': 'pass'}, 'max_tokens')] * 2
    else:
        verdict = 'needs_attention' if mode == 'needs_attention' else 'pass'
        execution.eye_replies[:] = [reply({'verdict': verdict,
            'findings': ['An unresolved visual finding remains.'] if verdict == 'needs_attention' else [], 'repair': None})]
    original = job.build_outputs
    def interrupted(ctx, specs, revision, **kwargs):
        if revision == 1:
            raise RuntimeError('Fixture interrupted after the repair bundle was retained.')
        return original(ctx, specs, revision, **kwargs)
    if mode == 'interrupted_repair':
        monkeypatch.setattr(job, 'build_outputs', interrupted)
    files_flow.retry(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=mode != 'pass')
    if mode == 'interrupted_repair':
        assert build.state == 'failed' and execution.provider.messages.create.call_count == 2
        claim, bundle = (folder/'review/repair.json').read_bytes(), (folder/'repairs/mechanical/bundle.json').read_bytes()
        monkeypatch.setattr(job, 'build_outputs', original)
        files_flow.retry(execution.record.pk, execution.owner)
        build = execution.drain()
        assert (folder/'review/repair.json').read_bytes() == claim
        assert (folder/'repairs/mechanical/bundle.json').read_bytes() == bundle
    assert (folder/'review/verdict-before-repair.json').read_bytes() == first_verdict
    assert all(sha(path) == pin for path, pin in pins.items())
    claim = read(folder/'review/repair.json')
    assert claim['kind'] == 'mechanical' and claim['owner_retry_attempt'] == 1
    assert claim['additional_provider_cost_usd'] == 0
    assert not (folder/'review/eye-3.json').exists() and not (folder/'revisions/2').exists()
    assert execution.provider.messages.create.call_count == (4 if mode == 'truncated' else 3)
    assert sum('Read this one picked picture' in prompt for prompt in execution.prompts) == 1
    assert sum('second and FINAL look' in prompt for prompt in execution.prompts) == (2 if mode == 'truncated' else 1)
    if mode in ('pass', 'interrupted_repair'):
        assert build.state == 'complete' and build.publication['revision'] == 1
        assert len(build.publication['eye']['looks']) == 2
        assert len((folder/'README.md').read_text().splitlines()) <= 40
    else:
        assert build.state == 'failed' and not build.publication and not (folder/'files.zip').exists()
        calls = execution.provider.messages.create.call_count
        if mode == 'needs_attention':
            with pytest.raises(ValueError, match='authorized reviews are complete'):
                files_flow.retry(execution.record.pk, execution.owner)
        else:
            files_flow.retry(execution.record.pk, execution.owner)
            build = execution.drain(allow_failure=True)
        assert build.state == 'failed' and execution.provider.messages.create.call_count == calls
        assert all(sha(path) == pin for path, pin in pins.items())


def test_retry_recovers_paid_first_eye_before_opening_any_repair(execution, monkeypatch):
    first = {'verdict': 'needs_attention', 'findings': ['The first review needs a mechanical correction.'], 'repair': None}
    execution.eye_replies[:] = [reply(first)]
    original = flow.write_json
    def interrupted(path, value):
        if str(path).endswith('/review/verdict.json'):
            raise RuntimeError('Fixture stopped after the paid eye reply, before the verdict record.')
        return original(path, value)
    monkeypatch.setattr(flow, 'write_json', interrupted)
    files_flow.start(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=True)
    folder = files_flow.root(build)
    assert build.current_step == 'eye' and build.state == 'failed' and not build.steps['eye']['result']
    assert execution.provider.messages.create.call_count == 2
    assert read(folder/'review/eye-1.json')['payload'] == first
    assert not (folder/'review/verdict.json').exists()
    paid = {p: sha(p) for p in (folder/'review').glob('eye-1.*json')}
    monkeypatch.setattr(flow, 'write_json', original)
    files_flow.retry(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=True)
    assert build.state == 'failed' and build.steps['eye']['result']['looks'] == [first]
    assert execution.provider.messages.create.call_count == 2
    assert read(folder/'review/verdict.json')['looks'] == [first]
    assert not (folder/'review/repair.json').exists() and not (folder/'review/eye-2.request.json').exists()
    assert all(sha(path) == pin for path, pin in paid.items())
    files_flow.retry(execution.record.pk, execution.owner)
    build = execution.drain()
    assert build.state == 'complete' and build.publication['revision'] == 1
    assert execution.provider.messages.create.call_count == 3
    assert all(sha(path) == pin for path, pin in paid.items())


def fixture_second_rejection(execution):
    rejected = {'verdict': 'needs_attention', 'findings': ['Source material and line boundaries still differ.'], 'repair': None}
    execution.eye_replies[:] = [reply(rejected), reply(rejected)]
    files_flow.start(execution.record.pk, execution.owner)
    execution.drain(allow_failure=True)
    files_flow.retry(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=True)
    assert build.state == 'failed' and build.steps['eye']['result']['revision'] == 1
    assert execution.provider.messages.create.call_count == 3
    return build


def fixture_extension_policy(execution, build):
    folder = files_flow.root(build)
    return {'repair_extensions': {execution.record.slug: {
        'schema': 'owner_files_extension/1', 'source_revision': 1, 'result_revision': 2,
        'source_retry_attempt': build.steps['eye']['attempts'],
        'maximum_eye_looks': 3, 'maximum_repairs': 2, 'budget_usd': 10,
        'picture_sha256': sha(execution.picture), 'source_eye_sha256': sha(folder/'review/eye-2.json'),
        'owner_instruction': 'Allow one more repair and review'}}}


@pytest.mark.parametrize('mode', ['pass', 'needs_attention', 'truncated', 'interrupted_repair', 'interrupted_verdict'])
def test_owner_extension_is_one_new_pass_preserves_both_builds_and_never_buys_a_fourth(execution, monkeypatch, mode):
    from apps.pipeline.services import round_files_extension as extension
    build = fixture_second_rejection(execution)
    folder = files_flow.root(build)
    with pytest.raises(ValueError, match='authorized reviews are complete'):
        files_flow.retry(execution.record.pk, execution.owner)
    approved = fixture_extension_policy(execution, build)
    monkeypatch.setattr(extension, 'policy', lambda: approved)
    assert extension.extension_available(build)
    prior_verdict = (folder/'review/verdict.json').read_bytes()
    originals = [path for directory in ('art', 'stand', 'repairs/mechanical', 'revisions/0', 'revisions/1')
                 for path in (folder/directory).rglob('*') if path.is_file()]
    originals += [path for n in (1, 2) for path in (folder/'review').glob(f'eye-{n}.*json')]
    pins = {path: sha(path) for path in originals}
    if mode == 'truncated':
        execution.eye_replies[:] = [reply({'verdict': 'pass'}, 'max_tokens')]*2
    else:
        state = 'needs_attention' if mode == 'needs_attention' else 'pass'
        execution.eye_replies[:] = [reply({'verdict': state, 'findings': ['The final source match is still insufficient.'] if state != 'pass' else [], 'repair': None})]
    original_outputs, original_write = job.build_outputs, flow.write_json
    def interrupted_outputs(ctx, specs, revision, **kwargs):
        if revision == 2:
            raise RuntimeError('Fixture additional pass interrupted before export.')
        return original_outputs(ctx, specs, revision, **kwargs)
    def interrupted_verdict(path, value):
        if str(path).endswith('/review/verdict.json'):
            raise RuntimeError('Fixture third reply saved before final verdict.')
        return original_write(path, value)
    if mode == 'interrupted_repair':
        monkeypatch.setattr(job, 'build_outputs', interrupted_outputs)
    elif mode == 'interrupted_verdict':
        monkeypatch.setattr(flow, 'write_json', interrupted_verdict)
    files_flow.retry(execution.record.pk, execution.owner)
    build = execution.drain(allow_failure=mode != 'pass')
    if mode.startswith('interrupted_'):
        assert build.state == 'failed'
        count = execution.provider.messages.create.call_count
        claim = (folder/'review/extension-2.json').read_bytes()
        monkeypatch.setattr(job, 'build_outputs', original_outputs)
        monkeypatch.setattr(flow, 'write_json', original_write)
        files_flow.retry(execution.record.pk, execution.owner)
        build = execution.drain()
        assert (folder/'review/extension-2.json').read_bytes() == claim
        assert execution.provider.messages.create.call_count == count + (mode == 'interrupted_repair')
    assert (folder/'review/verdict-before-extension-2.json').read_bytes() == prior_verdict
    assert all(sha(path) == pin for path, pin in pins.items())
    assert not (folder/'review/eye-4.json').exists() and not (folder/'revisions/3').exists()
    assert execution.provider.messages.create.call_count == (5 if mode == 'truncated' else 4)
    if mode in ('pass', 'interrupted_repair', 'interrupted_verdict'):
        assert build.state == 'complete' and build.publication['revision'] == 2
        assert len(build.publication['eye']['looks']) == 3
        assert len((folder/'README.md').read_text().splitlines()) <= 40
        assert 'owner-extension-2/stand' in (folder/'README.md').read_text()
    else:
        assert build.state == 'failed' and not build.publication and not (folder/'files.zip').exists()
        count = execution.provider.messages.create.call_count
        if mode == 'needs_attention':
            with pytest.raises(ValueError, match='authorized reviews are complete'):
                files_flow.retry(execution.record.pk, execution.owner)
        else:
            files_flow.retry(execution.record.pk, execution.owner)
            execution.drain(allow_failure=True)
        assert execution.provider.messages.create.call_count == count


@pytest.mark.parametrize('damage', ['wrong_picture', 'wrong_verdict', 'extra_look', 'extra_repair', 'higher_cap'])
def test_extension_does_not_authorize_a_different_source_or_unbounded_work(execution, monkeypatch, damage):
    from apps.pipeline.services import round_files_extension as extension
    build = fixture_second_rejection(execution)
    approved = fixture_extension_policy(execution, build)
    row = approved['repair_extensions'][execution.record.slug]
    key, value = {'wrong_picture': ('picture_sha256', '0'*64), 'wrong_verdict': ('source_eye_sha256', '0'*64),
        'extra_look': ('maximum_eye_looks', 4), 'extra_repair': ('maximum_repairs', 3), 'higher_cap': ('budget_usd', 11)}[damage]
    row[key] = value
    monkeypatch.setattr(extension, 'policy', lambda: approved)
    with pytest.raises(ValueError):
        files_flow.retry(execution.record.pk, execution.owner)
    assert execution.provider.messages.create.call_count == 3 and not execution.pending


@pytest.mark.parametrize('damage', ['same_attempt', 'changed_ai', 'deleted_png', 'changed_review_view'])
def test_extension_requires_new_owner_retry_and_the_original_reviewed_files(execution, monkeypatch, damage):
    from apps.pipeline.services import round_files_extension as extension
    build = fixture_second_rejection(execution)
    approved = fixture_extension_policy(execution, build)
    monkeypatch.setattr(extension, 'policy', lambda: approved)
    folder = files_flow.root(build)
    if damage == 'same_attempt':
        context = job.FilesContext(build, SimpleNamespace(**build.steps['eye']))
        with pytest.raises(ValueError, match='new owner Retry'):
            extension.prepare(context)
    else:
        if damage == 'changed_ai':
            path = Path(build.steps['eye']['result']['outputs']['objects'][0]['ai'])
            path.write_bytes(path.read_bytes()+b'changed')
        elif damage == 'deleted_png':
            Path(build.steps['eye']['result']['outputs']['objects'][0]['png']).unlink()
        else:
            path = folder/'review/views/1/product-drawing.png'
            path.write_bytes(path.read_bytes()+b'changed')
        files_flow.retry(execution.record.pk, execution.owner)
        build = execution.drain(allow_failure=True)
        assert build.state == 'failed'
    assert not (folder/'review/extension-2.json').exists()
    assert not (folder/'revisions/2').exists()
    assert execution.provider.messages.create.call_count == 3


@pytest.mark.parametrize('outcome', ['pass', 'repair', 'rejected', 'interrupted', 'width_amended', 'width_retry'])
def test_attempt_two_runs_only_from_owner_retry_with_own_edits_and_four_dollar_scope(execution, monkeypatch, tmp_path, outcome):
    import base64
    from apps.pipeline.services import round_files_attempt_art as attempt_art
    from apps.pipeline.services import round_files_width_authority as widths
    from apps.pipeline.tests.test_round_files_art import _attempt_art_fixture
    from apps.pipeline.tests.test_round_calls import image_reply
    amended = outcome in ('width_amended', 'width_retry')
    source, inspection, physical, _, _ = _attempt_art_fixture(
        tmp_path, motif_width=6 if amended else 2)
    # The new attempt sees a real known straight network, not a stubbed fitter.
    execution.picture.write_bytes(source.read_bytes())
    execution.source_bytes = source.read_bytes()
    execution.inspection.clear(); execution.inspection.update(inspection)
    execution.inspection.update(unprinted_faces=[{'face':'back','reason':'not shown'}],notes=[])
    execution.inspection['stand'] = {'rows':2,'columns':7,'count':14,'bottles':[
        {'row':r,'column':c,'box_px':[c*20,10-r*5,c*20+15,150-r*5], 'shade_field':'shade_0'}
        for r in range(2) for c in range(7)]}
    physical['dimensions_mm'] = {'width':15,'depth':15,'height':100,'cap_height':30}
    base = execution.inspection['panels']['stand_base']
    base.update(crop_px=[600,165,800,195],print_polygon_px=[[600,165],[800,165],[800,195],[600,195]],lineart_boxes_px=[])
    execution.record.product_brief['dimensions_mm'] = physical['dimensions_mm']
    execution.brief['dimensions_mm'] = physical['dimensions_mm']
    # The brief's grid builds the stand (2026-10-27); this fixture's brief asks for the pictured 2 × 7.
    for brief in (execution.record.product_brief, execution.brief):
        brief['stand'].update(count=14, layout={'rows': 2, 'columns': 7})
    publication = execution.record.artifacts['pick_page']
    publication['files']['designs/C2/raw.png'] = sha(execution.picture)
    publication['candidates']['C2']['picture_sha256'] = sha(execution.picture)
    execution.record.save()
    handoff = read(execution.root/'handoff.json')
    handoff.update(picture_sha256=sha(execution.picture),size_px=inspection['image_size_px'])
    flow.write_json(execution.root/'handoff.json',handoff)
    rejection = {'verdict':'needs_attention','findings':['Prior pixel tracing has broken leading.'],'repair':None}
    execution.eye_replies[:] = [reply(rejection)]
    files_flow.start(execution.record.pk,execution.owner)
    build = execution.drain(allow_failure=True)
    folder = files_flow.root(build)
    assert build.steps['eye']['result']['revision'] == 0
    policy = {'execution_attempts':{execution.record.slug:{
        'schema':'owner_files_attempt/1','attempt':2,'source_revision':0,'first_revision':1,
        'source_look_count':1,'source_retry_attempt':build.steps['eye']['attempts'],
        'maximum_eye_looks':2,'maximum_repairs':1,'maximum_image_calls':2,'budget_usd':4,
        'picture_sha256':sha(execution.picture),'source_eye_sha256':sha(folder/'review/eye-1.json'),
        'owner_instruction':'Fixture owner authorizes second attempt and presses Retry.'}}}
    monkeypatch.setattr(attempt,'policy',lambda:policy)
    monkeypatch.setattr(widths,'policy',lambda:policy)
    assert attempt.available(build)
    assert not (folder/'attempts/2').exists()
    page = execution.client.get(reverse('dashboard:product_round_files',args=[execution.record.pk]))
    assert b'separate $4 allowance' in page.content and b'>Retry</button>' in page.content
    assert not (folder/'attempts/2').exists()
    original = {p:sha(p) for d in ('revisions/0','art','stand') for p in (folder/d).rglob('*') if p.is_file()}
    prior_review = (folder/'review/verdict.json').read_bytes()
    images = Mock(name='explicit unpaid image edit provider')
    def edit(**kwargs):
        assert kwargs['model']=='gpt-image-2' and kwargs['quality']=='high'
        assert len(kwargs['image'])==1 and kwargs['mask'].name.endswith('mask.png')
        if amended:
            from io import BytesIO
            from PIL import Image
            # Match the amendment's recovery case: paid edits were rejected,
            # and their recorded exact 2x fallbacks must survive the new Retry.
            payload = BytesIO()
            Image.new('RGB',tuple(map(int,kwargs['size'].split('x'))),'black').save(payload,format='PNG')
            return image_reply(item={'b64_json':base64.b64encode(payload.getvalue()).decode()})
        # Echo the exact own-crop prepared canvas: preserves the reference at full resolution.
        return image_reply(item={'b64_json':base64.b64encode(kwargs['image'][0].read()).decode()})
    images.images.edit.side_effect = edit
    original_context = attempt.AttemptContext
    def context(build,step,**kwargs):
        return original_context(build,step,text_client=execution.provider,image_client=images,native=False)
    monkeypatch.setattr(attempt,'AttemptContext',context)
    accepted = {'verdict':'pass','findings':[],'repair':None}
    if outcome=='repair':
        execution.eye_replies[:] = [reply(dict(rejection,repair={'kind':'type_size','object_id':'bottle-front','run_index':0,'scale':1.01})),reply(accepted)]
    elif outcome=='rejected':
        execution.eye_replies[:] = [reply(rejection)]
    else:
        execution.eye_replies[:] = [reply(accepted)]
    real_outputs = job.build_outputs
    def interrupted(ctx,specs,revision,**kwargs):
        if revision==1:
            raise RuntimeError('Fixture interruption after both saved detail edits.')
        return real_outputs(ctx,specs,revision,**kwargs)
    if outcome=='interrupted':
        monkeypatch.setattr(job,'build_outputs',interrupted)
    original_art = attempt_art.prepare_attempt_art
    if amended:
        def failed_fixed_width(*args, **kwargs):
            assert kwargs['width_mode'] == 'fixed'
            assert images.images.edit.call_count == 2
            failed = folder/'attempts/2/art/body_front/line-fit.json'
            flow.write_json(failed, {'schema':'straight_line_network/1','passed':False,
                'minimum_coverage':.9,'coverage':.75,'all_segments_supported':True,
                'source_line_pixels':100,'covered_source_line_pixels':75,'width_mm':.3,
                'fixture':'Explicit stop after two saved paid detail responses.'})
            raise ValueError('Fixture fixed-width coverage failed before output bundle.')
        monkeypatch.setattr(attempt_art,'prepare_attempt_art',failed_fixed_width)
    response = execution.client.post(reverse('dashboard:product_round_files_retry',args=[execution.record.pk]))
    assert response.status_code==302
    build = execution.drain(allow_failure=outcome in ('rejected','interrupted') or amended)
    if outcome=='interrupted':
        assert images.images.edit.call_count==2
        monkeypatch.setattr(job,'build_outputs',real_outputs)
        files_flow.retry(execution.record.pk,execution.owner)
        build = execution.drain()
    if amended:
        base = folder/'attempts/2'
        assert images.images.edit.call_count == 2 and not (base/'bundle.json').exists()
        assert not (base/'review').exists() and not (base/'width-rule.json').exists()
        claim_bytes = (base/'claim.json').read_bytes()
        paid_bytes = {p:p.read_bytes() for p in (base/'details').rglob('*') if p.is_file()}
        assert all(read(base/'details'/panel/'detail.json')['selected'] == 'upscale.png'
                   for panel in ('body_front','stand_header'))
        failed = base/'art/body_front/line-fit.json'
        failure_bytes = failed.read_bytes()
        original_authority = deepcopy(policy['execution_attempts'])
        policy['width_amendments'] = {execution.record.slug:{
            'schema':'owner_files_width_amendment/1','attempt':2,'mode':'pictured',
            'minimum_pixel_coverage':.9,
            'owner_answer':'Match the pictured widths; keep ≥90% pixel coverage',
            'source_retry_attempt':build.steps['eye']['attempts'],
            'picture_sha256':sha(folder/'source.png'),
            'attempt_claim_sha256':sha(base/'claim.json'),
            'failed_fit_path':str(failed.relative_to(folder)), 'failed_fit_sha256':sha(failed),
            'additional_budget_usd':0,'additional_image_calls':0,
            'additional_eye_looks':0,'additional_repairs':0}}
        monkeypatch.setattr(attempt_art,'prepare_attempt_art',original_art)
        if outcome == 'width_retry':
            def failed_pictured_width(source, inspection, brief, out, **kwargs):
                assert kwargs['width_mode'] == 'pictured'
                flow.write_json(out/'body_front/line-fit.json', {
                    'passed':False,'minimum_coverage':.9,'coverage':.86464,
                    'all_segments_supported':True,
                    'original_picture_measurement':{'passed':False,'coverage':.88294}})
                (out/'body_front/lineart.svg').write_text('<svg><!-- retained failed pictured fit --></svg>')
                raise ValueError('Fixture pictured widths remain below full-mask coverage.')
            monkeypatch.setattr(attempt_art,'prepare_attempt_art',failed_pictured_width)
        response = execution.client.post(reverse('dashboard:product_round_files_retry',args=[execution.record.pk]))
        assert response.status_code == 302
        build = execution.drain(allow_failure=outcome == 'width_retry')
        if outcome == 'width_retry':
            failed_retry = build.steps['eye']['attempts']
            previous_run = base/f'art-pictured-widths-retry-{failed_retry}'
            assert read(previous_run/'run.json')['status'] == 'failed'
            previous_bytes = {p:p.read_bytes() for p in previous_run.rglob('*') if p.is_file()}
            assert not (base/'bundle.json').exists() and not (base/'review').exists()
            assert images.images.edit.call_count == 2
            # A duplicate queue delivery cannot rewrite the failed execution.
            tasks.run_round_files(build.pk)
            assert all(p.read_bytes() == value for p,value in previous_bytes.items())
            assert all(p.read_bytes() == value for p,value in paid_bytes.items())
            monkeypatch.setattr(attempt_art,'prepare_attempt_art',original_art)
            response = execution.client.post(reverse('dashboard:product_round_files_retry',args=[execution.record.pk]))
            assert response.status_code == 302
            build = execution.drain()
            assert build.steps['eye']['attempts'] > failed_retry
            assert all(p.read_bytes() == value for p,value in previous_bytes.items())
        assert (base/'claim.json').read_bytes() == claim_bytes
        assert failed.read_bytes() == failure_bytes
        assert policy['execution_attempts'] == original_authority
        assert all(p.read_bytes() == value for p,value in paid_bytes.items())
        rule = read(base/'width-rule.json')
        assert rule['mode'] == 'pictured' and rule['minimum_pixel_coverage'] == .9
        bundle = build.steps['eye']['result']['outputs']['repair_bundle']
        assert bundle['width_rule'] == rule
        assert bundle['pins']['attempts/2/width-rule.json'] == sha(base/'width-rule.json')
        assert bundle['art']['foil_width_mode'] == 'pictured'
        run_folder = Path(bundle['art']['panels']['body_front']['raster']).parent.parent
        run = read(run_folder/'run.json')
        assert run['status'] == 'complete' and run['art_sha256'] == job.digest(bundle['art'])
        assert run_folder.name == f"art-pictured-widths-retry-{build.steps['eye']['attempts']}"
        if outcome == 'width_retry':
            assert all(bundle['pins'][str(p.relative_to(folder))] == sha(p) for p in previous_bytes)
            assert all(run['retained_pins'][str(p.relative_to(folder))] == sha(p) for p in previous_bytes)
        for panel in ('body_front','stand_header'):
            fitted = read(run_folder/panel/'line-fit.json')
            assert fitted['passed'] and fitted['coverage'] >= .9
            assert fitted['all_segments_supported']
            original_fit = fitted['original_picture_measurement']
            assert original_fit['passed'] and original_fit['coverage'] >= .9
            assert original_fit['all_segments_supported']
        assert 'foil widths measured per segment from the original picture' in execution.prompts[-1]
        assert 'pictured widths measured per segment; ≥90% full pixel coverage' in (folder/'README.md').read_text()
    assert images.images.edit.call_count==2
    assert (folder/'attempts/2/previous-verdict.json').read_bytes()==prior_review
    assert all(sha(p)==pin for p,pin in original.items())
    assert execution.picture.read_bytes()==execution.source_bytes
    assert job.scoped_spend(build)['budget_usd']==4
    assert job.scoped_spend(build)['calls']==(4 if outcome=='repair' else 3)
    result = build.steps['eye']['result']
    assert result['attempt']==2 and len(result['looks'])==(2 if outcome=='repair' else 1)
    assert result['outputs']['specs'][2]['die_visible']
    assert result['outputs']['repair_bundle']['geometry']['count']==14
    cap = result['outputs']['specs'][1]
    assert not cap['type_runs'] and not cap['foil_svg'] and len(cap['logos'])==1
    assert result['outputs']['drawing_record']['drawing_material']['status']=='engine'
    assert {p.name for p in (folder/'attempts/2/details').iterdir()} == {'body_front','stand_header'}
    assert all(row['selected'] in ('candidate.png','upscale.png') for row in result['outputs']['repair_bundle']['details']['panels'].values())
    if outcome=='rejected':
        assert not build.publication and not (folder/'files.zip').exists()
        assert not files_flow.review_exhausted(build)
        calls = execution.provider.messages.create.call_count
        files_flow.retry(execution.record.pk,execution.owner)
        build = execution.drain(allow_failure=True)
        assert execution.provider.messages.create.call_count == calls
        assert images.images.edit.call_count == 2
    else:
        assert build.state=='complete' and (folder/'files.zip').exists()
        assert len((folder/'README.md').read_text().splitlines())<=40
        assert 'cap $4' in (folder/'README.md').read_text()
    assert not (folder/'attempts/2/review/eye-3.json').exists()


@pytest.fixture
def width_authority_case(tmp_path, monkeypatch):
    from apps.pipeline.services import round_files_width_authority as widths
    root = tmp_path/'files'
    base = root/'attempts/2'
    base.mkdir(parents=True)
    (root/'source.png').write_bytes(b'unchanged picked picture fixture bytes')
    execution = {'schema':'owner_files_attempt/1','attempt':2,
        'picture_sha256':sha(root/'source.png'), 'budget_usd':4,
        'maximum_image_calls':2,'maximum_eye_looks':2,'maximum_repairs':1}
    flow.write_json(base/'claim.json', {'authority':execution,'owner_retry_attempt':3})
    failed = base/'art/body_front/line-fit.json'
    flow.write_json(failed, {'passed':False,'minimum_coverage':.9,'coverage':.75,'width_mm':.3})
    # Durable paid replies exist before the width choice and must not be reset.
    for panel in ('body_front', 'stand_header'):
        call = base/'details'/panel/'call'
        flow.write_json(call/'image-call.response.json', {'fixture':'already settled '+panel})
        flow.write_json(call/'image-call.json', {'status':'complete','cost_usd':.177348})
    amendment = {'schema':'owner_files_width_amendment/1','attempt':2,
        'mode':'pictured','minimum_pixel_coverage':.9,
        'owner_answer':'Match the pictured widths; keep ≥90% pixel coverage',
        'source_retry_attempt':3, 'picture_sha256':sha(root/'source.png'),
        'attempt_claim_sha256':sha(base/'claim.json'),
        'failed_fit_path':str(failed.relative_to(root)), 'failed_fit_sha256':sha(failed),
        'additional_budget_usd':0,'additional_image_calls':0,
        'additional_eye_looks':0,'additional_repairs':0}
    rules = {'execution_attempts':{'width-fixture':execution},
             'width_amendments':{'width-fixture':amendment}}
    monkeypatch.setattr(widths,'policy',lambda:rules)
    ctx = SimpleNamespace(root=root, build=SimpleNamespace(
        round=SimpleNamespace(slug='width-fixture'),
        inputs={'picture_sha256':sha(root/'source.png')}, steps={'eye':{'attempts':4}}),
        image_call=Mock(side_effect=AssertionError('No paid image call is allowed')),
        text_call=Mock(side_effect=AssertionError('No paid eye call is allowed')))
    original = {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
    return SimpleNamespace(module=widths,ctx=ctx,root=root,base=base,failed=failed,
        amendment=amendment,rules=rules,execution=execution,original=original)


def test_width_authority_unamended_round_remains_fixed_without_writes(width_authority_case):
    case = width_authority_case
    case.rules['width_amendments'].clear()
    assert case.module.claim_width_rule(case.ctx) == {'mode':'fixed'}
    assert not (case.base/'width-rule.json').exists()
    assert {p:p.read_bytes() for p in case.root.rglob('*') if p.is_file()} == case.original


def test_width_authority_claim_is_once_pinned_and_never_resets_paid_replies(width_authority_case, monkeypatch):
    case = width_authority_case
    write = Mock(wraps=flow.write_json)
    monkeypatch.setattr(flow,'write_json',write)
    rule = case.module.claim_width_rule(case.ctx)
    destination = case.base/'width-rule.json'
    saved = destination.read_bytes()
    assert rule['mode'] == 'pictured' and rule['minimum_pixel_coverage'] == .9
    assert rule['owner_retry_attempt'] == 4
    assert rule['authority'] == case.amendment
    assert rule['execution_limits'] == {'budget_usd':4,'maximum_image_calls':2,
                                      'maximum_eye_looks':2,'maximum_repairs':1}
    assert set(rule['pins']) == {'source.png','attempts/2/claim.json',str(case.failed.relative_to(case.root))}
    assert all(sha(case.root/name) == pin for name,pin in rule['pins'].items())
    assert rule['authority_sha256'] == job.digest(case.amendment)
    assert case.module.claim_width_rule(case.ctx) == rule
    # A later Retry and already-created outputs may replay an existing claim.
    case.ctx.build.steps['eye']['attempts'] = 5
    (case.base/'bundle.json').write_text('{}')
    (case.base/'review').mkdir()
    assert case.module.claim_width_rule(case.ctx) == rule
    assert destination.read_bytes() == saved
    assert write.call_count == 1
    assert all(p.read_bytes() == data for p,data in case.original.items())
    case.ctx.image_call.assert_not_called()
    case.ctx.text_call.assert_not_called()


@pytest.mark.parametrize('retry', [0, 3, True, 3.0])
def test_width_authority_requires_new_owner_retry_before_claim(width_authority_case, retry):
    case = width_authority_case
    case.ctx.build.steps['eye']['attempts'] = retry
    with pytest.raises(ValueError, match='new app Retry'):
        case.module.claim_width_rule(case.ctx)
    assert not (case.base/'width-rule.json').exists()
    assert all(p.read_bytes() == data for p,data in case.original.items())


@pytest.mark.parametrize('late', ['bundle.json','review','review/eye-1.request.json'])
def test_width_authority_cannot_change_completed_or_reviewed_attempt(width_authority_case, late):
    case = width_authority_case
    path = case.base/late
    if late == 'review':
        path.mkdir()
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('{}')
    with pytest.raises(ValueError, match='after attempt output or review'):
        case.module.claim_width_rule(case.ctx)
    assert not (case.base/'width-rule.json').exists()


@pytest.mark.parametrize('field,value', [
    ('mode','fixed'), ('minimum_pixel_coverage',.89),
    ('owner_answer','Match the pictured widths'), ('additional_budget_usd',1), ('additional_budget_usd',False),
    ('additional_image_calls',1), ('additional_eye_looks',1), ('additional_repairs',1),
    ('attempt',3), ('picture_sha256','0'*64), ('source_retry_attempt',2),
    ('failed_fit_path','../foreign/line-fit.json'), ('attempt_claim_sha256','0'*64),
    ('failed_fit_sha256','0'*64)])
def test_width_authority_refuses_unpinned_or_expanded_permission(width_authority_case, field, value):
    case = width_authority_case
    case.amendment[field] = value
    with pytest.raises(ValueError):
        case.module.claim_width_rule(case.ctx)
    assert not (case.base/'width-rule.json').exists()
    case.ctx.image_call.assert_not_called()
    case.ctx.text_call.assert_not_called()


@pytest.mark.parametrize('damage', ['source','claim','failed','policy','removed','rule','retry_regression','execution_limits'])
def test_width_authority_replay_refuses_changed_binding(width_authority_case, damage):
    case = width_authority_case
    case.module.claim_width_rule(case.ctx)
    destination = case.base/'width-rule.json'
    saved = destination.read_bytes()
    if damage in ('source','claim','failed'):
        target = {'source':case.root/'source.png','claim':case.base/'claim.json','failed':case.failed}[damage]
        target.write_bytes(target.read_bytes()+b' ')
    elif damage == 'policy':
        case.amendment['owner_answer'] += '.'
    elif damage == 'removed':
        case.rules['width_amendments'].clear()
    elif damage == 'rule':
        value = read(destination); value['minimum_pixel_coverage'] = .89
        flow.write_json(destination,value)
        saved = destination.read_bytes()
    elif damage == 'retry_regression':
        case.ctx.build.steps['eye']['attempts'] = 3
    else:
        case.execution['budget_usd'] = 5
    with pytest.raises(ValueError):
        case.module.claim_width_rule(case.ctx)
    assert destination.read_bytes() == saved
    case.ctx.image_call.assert_not_called()
    case.ctx.text_call.assert_not_called()


@pytest.mark.parametrize('passed,minimum', [(True,.9),(False,.8)])
def test_width_authority_requires_actual_failed_coverage_record(width_authority_case, passed, minimum):
    case = width_authority_case
    flow.write_json(case.failed, {'passed':passed,'minimum_coverage':minimum})
    case.amendment['failed_fit_sha256'] = sha(case.failed)
    with pytest.raises(ValueError,match='failed 90% pixel-coverage report'):
        case.module.claim_width_rule(case.ctx)
    assert not (case.base/'width-rule.json').exists()


def test_pictured_fit_failed_runs_and_legacy_evidence_survive_owner_retry(width_authority_case):
    case = width_authority_case
    case.ctx.brief = {}
    rule = case.module.claim_width_rule(case.ctx)
    legacy = case.base/'art-pictured-widths/body_front/line-fit.json'
    flow.write_json(legacy, {'passed':False,'coverage':.86464})
    legacy_bytes = legacy.read_bytes()
    inputs = {'inspection':{'source':'synthetic'},'details':{'saved_paid_details':True},
              'geometry':{'size_mm':[15,70]},'width_rule':rule}
    def fail(source, inspection, brief, out, **kwargs):
        flow.write_json(out/'body_front/line-fit.json',{'passed':False,'coverage':.86464})
        raise ValueError('Synthetic coverage failure')
    failed = Mock(side_effect=fail)
    with pytest.raises(ValueError, match='Synthetic coverage'):
        attempt._pictured_art(case.ctx,**inputs,prepare_art=failed)
    old_folder = case.base/'art-pictured-widths-retry-4'
    old = {p:p.read_bytes() for p in old_folder.rglob('*') if p.is_file()}
    assert read(old_folder/'run.json')['status'] == 'failed'
    with pytest.raises(ValueError, match='records stay unchanged'):
        attempt._pictured_art(case.ctx,**inputs,prepare_art=failed)
    assert failed.call_count == 1
    assert all(p.read_bytes() == data for p,data in old.items())
    case.ctx.build.steps['eye']['attempts'] = 5
    def success(source, inspection, brief, out, **kwargs):
        flow.write_json(out/'body_front/line-fit.json',{'passed':True,'coverage':.95})
        return {'fixture_art':True,'directory':str(out)}
    make = Mock(side_effect=success)
    result = attempt._pictured_art(case.ctx,**inputs,prepare_art=make)
    run_path = case.base/'art-pictured-widths-retry-5/run.json'
    completed_bytes = run_path.read_bytes()
    run = read(run_path)
    assert run['status'] == 'complete'
    assert set(run['implementation_sha256']) == {'round_files_attempt.py','round_files_attempt_art.py',
        'round_files_line_fit.py','round_files_art.py','round_files_refinement_v2.py'}
    assert run['retained_pins'][str(legacy.relative_to(case.root))] == sha(legacy)
    assert all(run['retained_pins'][str(p.relative_to(case.root))] == sha(p) for p in old)
    assert all(p.read_bytes() == data for p,data in old.items()) and legacy.read_bytes() == legacy_bytes
    assert attempt._pictured_art(case.ctx,**inputs,prepare_art=make) == result
    assert make.call_count == 1 and run_path.read_bytes() == completed_bytes
    assert all(p.read_bytes() == data for p,data in case.original.items())
    case.ctx.image_call.assert_not_called(); case.ctx.text_call.assert_not_called()


@pytest.mark.parametrize('damage', ['brief','inspection','details','geometry','code','code_classifier','code_art',
                                  'source','claim','width_rule','artifact','descriptor'])
def test_pictured_fit_completed_replay_refuses_changed_inputs_or_art(width_authority_case, monkeypatch, damage):
    case = width_authority_case
    case.ctx.brief = {}
    rule = case.module.claim_width_rule(case.ctx)
    inputs = {'inspection':{'pinned':True},'details':{'cached':True},'geometry':{'size_mm':[15,70]},'width_rule':rule}
    def success(source, inspection, brief, out, **kwargs):
        flow.write_json(out/'body_front/line-fit.json',{'passed':True,'coverage':.95})
        return {'fixture_art':True}
    stage = Mock(side_effect=success)
    attempt._pictured_art(case.ctx,**inputs,prepare_art=stage)
    run_path = case.base/'art-pictured-widths-retry-4/run.json'
    if damage == 'brief':
        case.ctx.brief['copy'] = {'product':'Changed source COPY'}
    elif damage in ('inspection','details','geometry'):
        inputs[damage]['changed'] = True
    elif damage in ('code','code_classifier','code_art'):
        real_sha = attempt.sha
        changed = {'code':'round_files_line_fit.py','code_classifier':'round_files_refinement_v2.py',
                   'code_art':'round_files_art.py'}[damage]
        monkeypatch.setattr(attempt,'sha',lambda path: '0'*64 if Path(path).name == changed else real_sha(path))
    elif damage in ('source','claim','width_rule'):
        path = {'source':case.root/'source.png','claim':case.base/'claim.json','width_rule':case.base/'width-rule.json'}[damage]
        path.write_bytes(path.read_bytes()+b' ')
    elif damage == 'artifact':
        path = run_path.parent/'body_front/line-fit.json'
        path.write_bytes(path.read_bytes()+b' ')
    else:
        value = read(run_path); value['art']['fixture_art'] = False
        flow.write_json(run_path,value)
    saved = run_path.read_bytes()
    with pytest.raises(ValueError):
        attempt._pictured_art(case.ctx,**inputs,prepare_art=stage)
    assert stage.call_count == 1 and run_path.read_bytes() == saved


def test_pictured_fit_new_retry_refuses_changed_failed_evidence(width_authority_case):
    case = width_authority_case
    case.ctx.brief = {}
    rule = case.module.claim_width_rule(case.ctx)
    def fail(source, inspection, brief, out, **kwargs):
        flow.write_json(out/'body_front/line-fit.json',{'passed':False,'coverage':.8})
        raise ValueError('Synthetic stop')
    with pytest.raises(ValueError,match='Synthetic stop'):
        attempt._pictured_art(case.ctx,{}, {}, {}, rule, fail)
    bad = case.base/'art-pictured-widths-retry-4/body_front/line-fit.json'
    bad.write_bytes(bad.read_bytes()+b' ')
    case.ctx.build.steps['eye']['attempts'] = 5
    stage = Mock(side_effect=AssertionError('Changed old evidence cannot start a new fit'))
    with pytest.raises(ValueError,match='retained repair input or artifact changed'):
        attempt._pictured_art(case.ctx,{}, {}, {}, rule, stage)
    stage.assert_not_called()
    assert not (case.base/'art-pictured-widths-retry-5').exists()


def test_pictured_fit_interrupted_completion_resumes_only_identical_unpaid_work(width_authority_case, monkeypatch):
    case = width_authority_case
    case.ctx.brief = {}
    rule = case.module.claim_width_rule(case.ctx)
    real_write = flow.write_json
    def checkpoint_failure(path, payload):
        if Path(path).name == 'run.json' and payload.get('status') == 'complete':
            raise OSError('Fixture interrupted completed-art checkpoint')
        real_write(path,payload)
    monkeypatch.setattr(flow,'write_json',checkpoint_failure)
    def success(source, inspection, brief, out, **kwargs):
        real_write(out/'line-fit.json',{'passed':True,'coverage':.95})
        return {'fixture_art':True}
    stage = Mock(side_effect=success)
    with pytest.raises(OSError,match='interrupted completed-art checkpoint'):
        attempt._pictured_art(case.ctx,{}, {}, {}, rule, stage)
    run_path = case.base/'art-pictured-widths-retry-4/run.json'
    assert read(run_path)['status'] == 'running'
    monkeypatch.setattr(flow,'write_json',real_write)
    assert attempt._pictured_art(case.ctx,{}, {}, {}, rule, stage) == {'fixture_art':True}
    assert read(run_path)['status'] == 'complete' and stage.call_count == 2
    case.ctx.image_call.assert_not_called(); case.ctx.text_call.assert_not_called()


@pytest.mark.parametrize('structured', [False, True])
def test_pictured_fit_geometry_failure_retains_exact_inputs_and_safe_traceback(width_authority_case, tmp_path, monkeypatch, structured):
    import numpy as np
    from PIL import Image
    from apps.pipeline.services import round_files_attempt_art as adapter, round_files_line_fit as fitter
    from apps.pipeline.tests.test_round_files_art import _attempt_art_fixture
    case = width_authority_case
    source, inspection, brief, details, geometry = _attempt_art_fixture(tmp_path,motif_width=6)
    before = source.read_bytes()
    (case.root/'source.png').write_bytes(before)
    case.ctx.brief = brief
    picture_pin = sha(case.root/'source.png')
    case.ctx.build.inputs['picture_sha256'] = picture_pin
    case.execution['picture_sha256'] = picture_pin
    case.amendment['picture_sha256'] = picture_pin
    flow.write_json(case.base/'claim.json',{'authority':case.execution,'owner_retry_attempt':3})
    case.amendment['attempt_claim_sha256'] = sha(case.base/'claim.json')
    rule = case.module.claim_width_rule(case.ctx)
    diagnostic = {'schema':'line_width_evidence_error/1','reason':'meeting nodes obscure original evidence',
                  'accepted_samples':2,'independent_original_station_cells':1,'minimum_independent_station_cells':3}
    def forced_width_failure(image, mask, size_mm, output_svg, width_mm, **kwargs):
        private_local = 'LOCAL_VALUE_MUST_NEVER_ENTER_A_FAILURE_RECORD'
        panel = Path(output_svg).parent
        inputs = read(panel/'fit-inputs.json')
        assert inputs['panel'] == 'body_front' and inputs['size_mm'] == list(size_mm)
        assert inputs['width_mode'] == 'pictured' and inputs['minimum_pixel_coverage'] == .9
        assert inputs['source_picture_sha256'] == picture_pin
        assert all(sha(panel/name) == pin for name,pin in inputs['files'].items())
        assert (panel/'selected.png').read_bytes() == Path(details['panels']['body_front']['selected_path']).read_bytes()
        assert np.array_equal(np.asarray(Image.open(panel/'selected.png').convert('RGB')),image)
        assert np.array_equal(np.asarray(Image.open(panel/'foil-source-mask.png')) > 0,mask)
        assert np.array_equal(np.asarray(Image.open(panel/'original-foil-source-mask.png')) > 0,kwargs['width_reference_mask'])
        assert inputs['original_motif_pixels'] == int(kwargs['width_reference_mask'].sum())
        assert inputs['selected_motif_pixels'] == int(mask.sum())
        with Image.open(source) as original:
            assert np.array_equal(np.asarray(Image.open(panel/'crop.png')),np.asarray(original.crop(inputs['source_crop_px'])))
        assert read(panel/'original-source-classification.json')['schema'] == 'source_material_metal/1'
        error = (fitter.WidthEvidenceError('Fixture width is obscured by meeting nodes',deepcopy(diagnostic))
                 if structured else ValueError('Fixture width is obscured by meeting nodes'))
        assert private_local  # Kept in the raising frame, never in its record.
        raise error
    call = Mock(side_effect=forced_width_failure)
    monkeypatch.setattr(fitter,'fit_line_network',call)
    with pytest.raises(ValueError,match='width is obscured'):
        attempt._pictured_art(case.ctx,inspection,details,geometry,rule,adapter.prepare_attempt_art)
    out = case.base/'art-pictured-widths-retry-4'
    run_path = out/'run.json'
    run_bytes = run_path.read_bytes()
    run = read(run_path)
    assert run['status'] == 'failed' and run['error_type'] == ('WidthEvidenceError' if structured else 'ValueError')
    assert not (out/'body_front/line-fit.json').exists()
    assert not (case.base/'bundle.json').exists()
    assert run['diagnostic']['panel'] == 'body_front'
    assert run['diagnostic']['fit_inputs_sha256'] == sha(out/'body_front/fit-inputs.json')
    if structured:
        assert all(run['diagnostic'][key] == value for key,value in diagnostic.items())
    else:
        assert run['diagnostic']['schema'] == 'panel_geometry_error/1'
    assert run['traceback_frames'] and all(set(row) == {'file','function','line'} for row in run['traceback_frames'])
    assert any(row['function'] == 'forced_width_failure' for row in run['traceback_frames'])
    assert all(type(row['line']) is int and row['line'] > 0 for row in run['traceback_frames'])
    assert b'LOCAL_VALUE_MUST_NEVER_ENTER_A_FAILURE_RECORD' not in run_bytes
    assert all(sha(case.root/name) == pin for name,pin in run['artifact_pins'].items())
    assert str((out/'body_front/fit-inputs.json').relative_to(case.root)) in run['artifact_pins']
    with pytest.raises(ValueError,match='records stay unchanged'):
        attempt._pictured_art(case.ctx,inspection,details,geometry,rule,adapter.prepare_attempt_art)
    assert call.call_count == 1 and run_path.read_bytes() == run_bytes
    assert source.read_bytes() == before and (case.root/'source.png').read_bytes() == before
    case.ctx.image_call.assert_not_called(); case.ctx.text_call.assert_not_called()


@pytest.mark.parametrize('bad_diagnostic', [float('nan'), object()])
def test_pictured_fit_invalid_diagnostic_cannot_erase_original_failure(width_authority_case, bad_diagnostic):
    case = width_authority_case
    case.ctx.brief = {}
    rule = case.module.claim_width_rule(case.ctx)
    def failure(*args, **kwargs):
        error = ValueError('Original geometry failure')
        error.diagnostic = {'invalid':bad_diagnostic}
        raise error
    with pytest.raises(ValueError,match='Original geometry failure'):
        attempt._pictured_art(case.ctx,{}, {}, {}, rule, failure)
    run = read(case.base/'art-pictured-widths-retry-4/run.json')
    assert run['status'] == 'failed' and run['error'] == 'Original geometry failure'
    assert run['diagnostic']['schema'] == 'invalid_exception_diagnostic/1'
    assert run['traceback_frames'][-1]['function'] == 'failure'


def test_a_reading_with_one_bad_and_one_arc_text_completes_and_builds_the_briefs_stand(execution):
    """The owner's message of 2026-10-27: one bad text never stops the read; an arc text stays as its box
    plus a note; invented lettering is set from COPY along its path; the brief's 12 are built, the picture's 18 listed."""
    inspection = execution.inspection
    inspection['panels']['body_front']['text'] = [
        {'field': 'product_latin', 'box_px': [20, 80, 40, 96], 'color': '#D5AF59', 'rotation': -90},
        {'field': 'shade_2', 'box_px': [10, 110, 60, 125], 'color': 'rgb(213, 175, 89)', 'rotation': 0, 'arc': True},
        {'field': 'product_arabic', 'box_px': [10, 40, 60, 55], 'color': 'gold', 'rotation': 0}]
    inspection['panels']['stand_header']['ornament_lettering'] = [
        {'path_px': [[165, 70], [200, 58], [235, 70]], 'height_px': 6, 'color': '#D5AF59'}]
    inspection['stand'] = {'rows': 3, 'columns': 6, 'count': 18, 'bottles': [
        {'row': row, 'column': column, 'box_px': [10 + column * 20, 5, 25 + column * 20, 100],
         'shade_field': ['shade_1', 'shade_0', None, 'shade_2', None, None][column] if row == 0 else None}
        for row in range(3) for column in range(6)]}
    flow.write_json(execution.root / 'files-copy.json', {
        'schema': 'round_files_copy/1', 'brief_sha256': job.digest(execution.record.product_brief),
        'arabic_shade_names': {'Ember Glow': 'إمبر جلو'}, 'source': 'fixture', 'confirmed': False})
    execution.client.post(reverse('dashboard:product_round_files_start', args=[execution.record.pk]))
    build = execution.drain()
    assert build.state == 'complete' and all(row['state'] == 'complete' for row in build.steps.values())
    prompt = execution.prompts[0]
    assert 'rotation is the turn of the lettering as seen: 0 upright, 90 reads bottom to top' in prompt
    assert 'ornament_lettering' in prompt and '"arabic_shade_2": "إمبر جلو"' in prompt
    reading = build.steps['read']['result']
    body = reading['panels']['body_front']['text']
    assert [(row['field'], row['rotation']) for row in body] == [('product_latin', 90), ('shade_2', 0)]
    assert body[1]['arc'] is True and body[1]['color'] == '#D5AF59'
    assert [(row['item'], row['why']) for row in reading['reading_findings'] if row['action'] == 'dropped'] == [
        ('text “product_arabic”', "its colour 'gold' is not a colour")]
    stand = build.steps['stand']['result']
    assert (stand['rows'], stand['columns'], stand['count']) == (3, 4, 12)
    assert stand['layout']['observed'] == {'rows': 3, 'columns': 6, 'count': 18}
    folder = files_flow.root(build)
    revision = folder / 'revisions' / str(build.publication['revision'])
    drawing = read(revision / 'product-drawing.json')
    assert drawing['count'] == drawing['drawn_product_instances'] == 12
    assert drawing['count_source'] == 'the brief’s rows × columns through the engine'
    header = read(revision / 'stand.export.json')
    words = [row['copy'] for row in header['type'] if row.get('ornament')]
    assert words == ['جلو', 'إمبر', 'شفاه', 'ملمع', 'BBROSE']
    assert all(row['present'] for row in header['readback']['copies'])
    live = ' '.join(row['copy'] for path in revision.glob('*.export.json') for row in read(path)['type'])
    assert 'مبر جلو' not in live.replace('إمبر جلو', '') and 'MODEL INVENTION' not in live
    readme = (folder / 'README.md').read_text()
    assert 'Reading: 1 item(s) dropped' in readme and 'the stand is built for the brief’s 12' in readme
    page = execution.client.get(reverse('dashboard:product_round_files', args=[execution.record.pk]))
    text = page.content.decode()
    assert 'Notes from reading your picture' in text and 'is not a colour' in text
    assert 'The picture shows 18 products (3 rows × 6 across)' in text
    assert 'not yet confirmed by you: Ember Glow إمبر جلو' in text
