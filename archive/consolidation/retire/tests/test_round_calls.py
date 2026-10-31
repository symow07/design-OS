"""Fixture and real-SDK transport contracts for the round's durable payment boundary."""
from concurrent.futures import ThreadPoolExecutor
import base64
from io import BytesIO
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import anthropic
import httpx
import pytest
from PIL import Image

from apps.pipeline.services import spend_reservation as spend
from apps.pipeline.services.cost_ledger import BudgetExceededError
from apps.pipeline.services.round_calls import RoundContext, scoped_spend
from apps.pipeline.services.round_flow import YieldRound


@pytest.fixture
def context(tmp_path, settings):
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    record = SimpleNamespace(pk=999, slug='fixture-round', product_brief={}, budget_usd=22)
    return RoundContext(record, SimpleNamespace(attempts=0))


def reply(stop='end_turn', text='{"ok":true}'):
    return {'stop_reason': stop, 'content': [{'type': 'text', 'text': text}],
            'usage': {'input_tokens': 100, 'output_tokens': 20}}


def test_truncation_retries_once_with_same_reservation_and_aggregated_usage(context):
    create = Mock(side_effect=[reply('max_tokens', '{'), reply()])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    output = context.root / 'eye.json'
    result = context.text_call('eye', 'Read the whole object.', output, max_tokens=100, ceiling=1)
    assert result['payload'] == {'ok': True}
    assert result['attempts'] == 2
    assert result['usage']['input_tokens'] == 200
    assert create.call_count == 2
    assert all(call.kwargs['thinking'] == {'type': 'adaptive'} for call in create.call_args_list)
    assert all(call.kwargs['output_config'] == {'effort': 'low'} for call in create.call_args_list)
    assert scoped_spend(context.round)['calls'] == 1
    assert scoped_spend(context.round)['reserved_usd'] == 0
    assert scoped_spend(context.round)['actual_usd'] == scoped_spend(context.round)['accounted_usd']
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    assert restarted.text_call('eye', 'Read the whole object.', output, max_tokens=100, ceiling=1) == result
    assert create.call_count == 2


def test_second_truncation_is_failure_and_only_explicit_app_retry_can_repurchase(context):
    create = Mock(side_effect=[reply('max_tokens', '{'), reply('max_tokens', '{'), reply()])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(ValueError, match='not a verdict'):
        context.text_call('eye', 'Read', context.root / 'eye.json', max_tokens=100, ceiling=1)
    assert create.call_count == 2
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    with pytest.raises(ValueError, match='not a verdict'):
        restarted.text_call('eye', 'Read', context.root / 'eye.json', max_tokens=100, ceiling=1)
    assert create.call_count == 2
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    assert retry.text_call('eye', 'Read', context.root / 'eye.json', max_tokens=100, ceiling=1)['status'] == 'complete'
    assert scoped_spend(context.round)['calls'] == 2
    assert len(list(context.root.glob('call-history/*/eye.response-*.json'))) == 2


# Round 3's eye/front/2 (2026-10-28): end_turn, 379 of 8,192 tokens, one sentence before its JSON fence.
FENCED_AFTER_NOTES = ('Image 3 shows clear doubling.\n\n```json\n'
                      '{"verdict":"needs_attention","findings":["The wordmark is doubled."]}\n```')


def test_a_verdict_fenced_after_notes_is_read_with_one_call(context):
    create = Mock(side_effect=[reply(text=FENCED_AFTER_NOTES)])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    result = context.text_call('eye/front/2', 'Look', context.root / 'eye.json', max_tokens=100, ceiling=1)
    assert result['status'] == 'complete' and result['attempts'] == 1 and create.call_count == 1
    assert result['payload'] == {'verdict': 'needs_attention', 'findings': ['The wordmark is doubled.']}


def test_an_unreadable_reply_is_asked_once_more_in_the_same_reservation(context):
    create = Mock(side_effect=[reply(text='The face reads well.'), reply(text=FENCED_AFTER_NOTES)])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    output = context.root / 'eye.json'
    result = context.text_call('eye/front/2', 'Look', output, max_tokens=100, ceiling=1)
    assert result['status'] == 'complete' and result['attempts'] == 2 and create.call_count == 2
    assert result['payload']['verdict'] == 'needs_attention'
    assert create.call_args_list[0].kwargs == create.call_args_list[1].kwargs
    assert len(result['attempt_token_splits']) == 2 and result['token_split']['output_tokens'] == 40
    assert scoped_spend(context.round)['calls'] == 1
    assert scoped_spend(context.round)['reserved_usd'] == 0
    assert scoped_spend(context.round)['actual_usd'] == scoped_spend(context.round)['accounted_usd']


def test_a_second_unreadable_reply_is_retained_and_never_a_verdict(context):
    create = Mock(side_effect=[reply(text='Looks fine.'), reply('max_tokens', '{"verdict":')])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(ValueError, match='not a verdict'):
        context.text_call('eye/front/2', 'Look', context.root / 'eye.json', max_tokens=100, ceiling=1)
    saved = json.loads((context.root / 'eye.json').read_text())
    assert saved['status'] == 'incomplete' and saved['payload'] is None and saved['attempts'] == 2
    assert create.call_count == 2 and scoped_spend(context.round)['calls'] == 1


def test_a_retained_reply_an_older_parser_could_not_read_is_read_again_without_a_call(context):
    create = Mock(side_effect=[reply(text=FENCED_AFTER_NOTES)])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    output = context.root / 'eye.json'
    first = context.text_call('eye/front/2', 'Look', output, max_tokens=100, ceiling=1)
    output.write_text(json.dumps(dict(first, status='incomplete', payload=None)))     # as saved at round 3's stop 16
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    again = retry.text_call('eye/front/2', 'Look', output, max_tokens=100, ceiling=1)
    assert again['status'] == 'complete' and again['payload'] == first['payload'] and create.call_count == 1
    assert again['reread'] == {'reply': 'eye.response-0.json', 'reply_sha256': hashlib.sha256(
        (context.root / 'eye.response-0.json').read_bytes()).hexdigest(), 'new_calls': 0,
        'rule': 'the retained reply read again by the fence parser; it was never truncated'}
    assert scoped_spend(context.round)['calls'] == 1 and not list(context.root.glob('call-history/*'))


def test_a_reply_cut_at_max_tokens_is_never_read_again_as_a_verdict(context):
    from apps.pipeline.services.round_calls import retained_verdict
    create = Mock(side_effect=[reply('max_tokens', FENCED_AFTER_NOTES), reply('max_tokens', FENCED_AFTER_NOTES)])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(ValueError, match='not a verdict'):
        context.text_call('eye/front/2', 'Look', context.root / 'eye.json', max_tokens=100, ceiling=1)
    assert retained_verdict(context.root / 'eye.json') is None


def test_a_readable_needs_attention_is_never_asked_again(context):
    create = Mock(side_effect=[reply(text='{"verdict":"needs_attention","findings":["x"]}'), reply()])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    result = context.text_call('eye/front/2', 'Look', context.root / 'eye.json', max_tokens=100, ceiling=1)
    assert result['payload']['verdict'] == 'needs_attention' and create.call_count == 1


def test_unknown_timeout_holds_reservation_and_cannot_be_repeated(context):
    create = Mock(side_effect=TimeoutError('fixture timeout'))
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(TimeoutError):
        context.text_call('eye', 'Read', context.root / 'eye.json', max_tokens=100, ceiling=1)
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    with pytest.raises(ValueError, match='outcome is unknown'):
        retry.text_call('eye', 'Read', context.root / 'eye.json', max_tokens=100, ceiling=1)
    assert create.call_count == 1
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    assert row['state'] == 'reserved' and row['reserved'] == row['accounted']
    assert scoped_spend(context.round)['actual_usd'] == 0
    assert scoped_spend(context.round)['reserved_usd'] == scoped_spend(context.round)['accounted_usd']


def test_delivery_yields_before_a_second_new_call_but_can_read_completed_calls(context):
    create = Mock(return_value=reply())
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    first = context.text_call('first', 'Read', context.root / 'first.json', max_tokens=100, ceiling=1)
    assert context.text_call('first', 'Read', context.root / 'first.json', max_tokens=100, ceiling=1) == first
    with pytest.raises(YieldRound):
        context.text_call('second', 'Read', context.root / 'second.json', max_tokens=100, ceiling=1)
    assert create.call_count == 1
    assert not (context.root / 'second.request.json').exists()


def test_owner_cap_is_atomic_and_refuses_before_any_provider_call(context):
    def reserve_one(_):
        try:
            return spend.reserve('anthropic', context.prefix + 'test', 'test', 12,
                                 budget_prefix=context.prefix, prefix_cap=22)
        except BudgetExceededError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(value is not None for value in pool.map(reserve_one, range(2))) == 1
    spend.reserve('anthropic', context.prefix + 'hold', 'test', 10, budget_prefix=context.prefix, prefix_cap=22)
    create = Mock(return_value=reply())
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(BudgetExceededError):
        context.text_call('eye', 'Read', context.root / 'eye.json', max_tokens=100, ceiling=1)
    create.assert_not_called()


def test_saved_raw_reply_recovers_without_repurchase(context):
    create = Mock(return_value=reply())
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    output = context.root / 'eye.json'
    result = context.text_call('eye', 'Read', output, max_tokens=100, ceiling=1)
    output.unlink()  # Simulate loss after durable provider reply but before the interpreted artifact.
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    recovered = restarted.text_call('eye', 'Read', output, max_tokens=100, ceiling=1)
    assert recovered['reservation_id'] == result['reservation_id']
    assert create.call_count == 1


def test_cached_result_reconciles_missing_audit_journal_without_repayment(context):
    create = Mock(return_value=reply())
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    output = context.root / 'eye.json'
    result = context.text_call('eye', 'Read', output, max_tokens=100, ceiling=1)
    (context.root / 'calls.jsonl').unlink()  # Kill between the complete record and journal append.
    assert context.text_call('eye', 'Read', output, max_tokens=100, ceiling=1) == result
    assert result['reservation_id'] in (context.root / 'calls.jsonl').read_text()
    assert create.call_count == 1


def test_truncated_then_unbilled_rejection_settles_known_first_usage(context):
    class Rejected(Exception):
        status_code = 429
    create = Mock(side_effect=[reply('max_tokens', '{'), Rejected('fixture limited')])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(Rejected):
        context.text_call('eye', 'Read', context.root / 'eye.json', max_tokens=100, ceiling=1)
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    assert row['state'] == 'usage_recorded' and row['accounted'] < row['reserved']
    assert create.call_count == 2


def test_image_attempt_capacity_cuts_forks_first_and_refuses_if_one_cannot_fit(context):
    context.round.marks = {'marks': [{'id': key, 'preserve': 'fragment'} for key in ('A1', 'A2', 'A3')]}
    for index in range(21):
        identifier = spend.reserve('openai', context.prefix + f'image/fixture-{index}', 'gpt-image-2', .001,
                                   budget_prefix=context.prefix, prefix_cap=22)
    spend.release_rejected(identifier, 400, ValueError('fixture rejected before billing'))
    context.prepare_budget_plan('forks')
    assert context.forks_per_mark == 1 and context.pair_batch_size == 9
    assert scoped_spend(context.round)['image_calls'] == 21
    for index in range(21, 26):
        spend.reserve('openai', context.prefix + f'image/fixture-{index}', 'gpt-image-2', .001,
                      budget_prefix=context.prefix, prefix_cap=22)
    with pytest.raises(BudgetExceededError, match='one fork per mark'):
        context.prepare_budget_plan('forks')


def authorize_fixture_repair(context):
    from apps.pipeline.services.round_flow import REPAIR_ID
    context.round.slug = 'r2-gloss'
    context.round.budget_usd = 25
    context.round.artifacts = {'repair_authorization': {
        'id': REPAIR_ID, 'source': 'owner app retry', 'user_id': 1,
        'authorized_at': '2026-10-26T12:00:00+00:00', 'additional_image_attempts': 20,
        'image_attempt_limit': 46, 'budget_usd': 25}}
    return RoundContext(context.round, context.job)


def test_repair_attempt_increment_is_named_round_only_and_cannot_be_arbitrarily_enlarged(context):
    from apps.pipeline.services.round_calls import image_call_limit
    repaired = authorize_fixture_repair(context)
    assert image_call_limit(repaired.round) == 46
    repaired.round.slug = 'another-round'
    assert image_call_limit(repaired.round) == 26
    repaired.round.slug = 'r2-gloss'
    repaired.round.artifacts['repair_authorization']['additional_image_attempts'] = 100
    assert image_call_limit(repaired.round) == 26
    repaired.round.artifacts['repair_authorization']['additional_image_attempts'] = 20
    repaired.round.artifacts['repair_authorization']['id'] = 'another-repair'
    assert image_call_limit(repaired.round) == 26


def test_repair_counts_prior_attempts_and_cuts_forks_against_forty_six(context):
    repaired = authorize_fixture_repair(context)
    repaired.round.marks = {'marks': [{'id': key, 'preserve': 'fragment'} for key in ('A1', 'A2', 'A3')]}
    for index in range(41):
        identifier = spend.reserve('openai', repaired.prefix + f'image/fixture-{index}', 'gpt-image-2', .001)
        if index == 0:
            spend.release_rejected(identifier, 400, ValueError('original rejected attempt'))
    repaired.prepare_budget_plan('forks')
    plan = json.loads((repaired.root / 'budget-plan.json').read_text())
    assert repaired.forks_per_mark == 1 and plan['image_attempt_limit'] == 46 and plan['budget_usd'] == 25
    assert scoped_spend(repaired.round)['image_calls'] == 41
    for index in range(41, 46):
        spend.reserve('openai', repaired.prefix + f'image/fixture-{index}', 'gpt-image-2', .001)
    with pytest.raises(BudgetExceededError, match='46-image allowance'):
        repaired.prepare_budget_plan('forks')
    output = repaired._destination(repaired.root / 'sketches' / 'A1' / 'image-call.json')
    with pytest.raises(BudgetExceededError, match='Image-attempt limit'):
        repaired._request(output, {'model': 'gpt-image-2'}, provider='openai', operation='image/A1', estimate=.001)
    assert not output.with_suffix('.request.json').exists()
    assert scoped_spend(repaired.round)['image_calls'] == 46


def test_repair_budget_still_counts_historical_spend_before_new_reservation(context):
    repaired = authorize_fixture_repair(context)
    spend.reserve('anthropic', repaired.prefix + 'historical-hold', 'fixture', 24.5)
    output = repaired._destination(repaired.root / 'sketches' / 'A1' / 'image-call.json')
    with pytest.raises(BudgetExceededError):
        repaired._request(output, {'model': 'gpt-image-2'}, provider='openai', operation='image/A1', estimate=1)
    assert not output.with_suffix('.request.json').exists()
    assert scoped_spend(repaired.round)['calls'] == 1


@pytest.fixture
def image_inputs(context, settings, monkeypatch):
    from apps.pipeline.services import round_calls as image_guard
    from apps.pipeline.services.round_calls import sha
    settings.IMAGE_MODEL = 'gpt-image-2'
    context.root.mkdir(parents=True)
    target, mask, logo = [context.root / name for name in ('sheet.png', 'sheet-mask.png', 'fixture-logo.png')]
    Image.new('RGBA', (1536, 1024), 'white').save(target)
    Image.new('RGBA', (1536, 1024), (0, 0, 0, 0)).save(mask)
    Image.new('RGBA', (8, 8), 'black').save(logo)
    monkeypatch.setattr(image_guard, 'APPROVED_LOGO', (str(logo), sha(logo)))
    return {'target': target, 'mask': mask, 'logo': logo}


def image_reply(size=(1536, 1024), *, item=None):
    if item is None:
        output = BytesIO()
        Image.new('RGBA', size, 'white').save(output, format='PNG')
        item = {'b64_json': base64.b64encode(output.getvalue()).decode()}
    return {'data': [item], 'usage': {'input_tokens': 100, 'output_tokens': 100,
            'input_tokens_details': {'image_tokens': 20, 'text_tokens': 80}}}


@pytest.mark.parametrize('invalid,reason', [
    ({'data': []}, 'Exactly one paid image'),
    ({'item': {}}, 'bytes missing'),
    ({'item': {'b64_json': '!!!'}}, 'not valid base64'),
    ({'item': {'b64_json': base64.b64encode(b'not an image').decode()}}, 'cannot be decoded'),
    ({'size': (100, 100)}, 'wrong dimensions'),
])
def test_known_invalid_image_requires_app_retry_and_retains_paid_failed_attempt(context, image_inputs, invalid, reason):
    bad = image_reply(**invalid) if 'data' not in invalid else dict(image_reply(), **invalid)
    edit = Mock(side_effect=[bad, image_reply()])
    context.image_client = SimpleNamespace(images=SimpleNamespace(edit=edit))
    destination = context.root / 'sketches' / 'A1'
    def call(ctx):
        return ctx.image_call('sketch/A1', 'Draw the fixture object.', destination, **image_inputs)
    with pytest.raises(ValueError, match=reason):
        call(context)
    failed = json.loads((destination / 'image-call.json').read_text())
    assert failed['status'] == 'validation_failed' and failed['billing_state'] == 'usage_recorded'
    assert failed['usage'] == bad['usage'] and reason in failed['validation_error']
    assert not (destination / 'raw.png').exists()
    assert not (context.root / 'image-calls.jsonl').exists()
    assert scoped_spend(context.round)['image_calls'] == 1 and scoped_spend(context.round)['reserved_usd'] == 0
    replay = RoundContext(context.round, context.job, image_client=context.image_client)
    with pytest.raises(ValueError, match=reason):
        call(replay)
    assert edit.call_count == 1
    assert len((context.root / 'call-validation.jsonl').read_text().splitlines()) == 1
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), image_client=context.image_client)
    success = call(retry)
    assert success['status'] == 'complete' and success['reservation_id'] != failed['reservation_id']
    assert edit.call_count == scoped_spend(context.round)['image_calls'] == 2
    archive = destination / 'call-history' / ('image-call-' + failed['reservation_id'])
    assert json.loads((archive / 'image-call.json').read_text()) == failed
    assert json.loads((archive / 'image-call.response.json').read_text()) == bad
    journal = [json.loads(line) for line in (context.root / 'image-calls.jsonl').read_text().splitlines()]
    assert [row['reservation_id'] for row in journal] == [success['reservation_id']]


@pytest.mark.parametrize('failure', ['write', 'download'])
def test_local_image_recovery_reuses_saved_provider_response(context, image_inputs, monkeypatch, failure):
    from apps.pipeline.services import round_calls as image_producer        # the boundary downloads (2026-10-28)
    valid = image_reply()
    response = valid if failure == 'write' else image_reply(item={'url': 'https://fixture.invalid/image.png'})
    image_bytes = base64.b64decode(valid['data'][0]['b64_json'])
    edit = Mock(return_value=response)
    context.image_client = SimpleNamespace(images=SimpleNamespace(edit=edit))
    destination = context.root / 'sketches' / 'A1'
    def call(ctx):
        return ctx.image_call('sketch/A1', 'Draw the fixture object.', destination, **image_inputs)
    with monkeypatch.context() as broken:
        if failure == 'write':
            write_bytes = Path.write_bytes
            def write_unless_raw(path, data):
                if path.name == 'raw.png':
                    raise PermissionError('fixture disk unavailable')
                return write_bytes(path, data)
            broken.setattr(Path, 'write_bytes', write_unless_raw)
        else:
            broken.setattr(image_producer, 'download_image_bytes', Mock(side_effect=TimeoutError('fixture download unavailable')))
        with pytest.raises((PermissionError, TimeoutError), match='fixture'):
            call(context)
    assert not (destination / 'image-call.json').exists()
    assert not (context.root / 'call-validation.jsonl').exists()
    monkeypatch.setattr(image_producer, 'download_image_bytes', Mock(return_value=image_bytes))
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), image_client=context.image_client)
    assert call(retry)['status'] == 'complete'
    assert edit.call_count == scoped_spend(context.round)['image_calls'] == 1


def test_invalid_image_replacement_still_obeys_image_attempt_cap(context, image_inputs):
    edit = Mock(return_value=image_reply(item={}))
    context.image_client = SimpleNamespace(images=SimpleNamespace(edit=edit))
    destination = context.root / 'sketches' / 'A1'
    with pytest.raises(ValueError, match='bytes missing'):
        context.image_call('sketch/A1', 'Draw the fixture object.', destination, **image_inputs)
    for index in range(25):
        identifier = spend.reserve('openai', context.prefix + f'image/rejected-{index}', 'gpt-image-2', .001,
                                   budget_prefix=context.prefix, prefix_cap=22)
        spend.release_rejected(identifier, 400, ValueError('fixture rejection'))
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), image_client=context.image_client)
    with pytest.raises(BudgetExceededError):
        retry.image_call('sketch/A1', 'Draw the fixture object.', destination, **image_inputs)
    assert edit.call_count == 1 and scoped_spend(context.round)['image_calls'] == 26


def test_unknown_image_outcome_remains_held_and_cannot_repurchase(context, image_inputs):
    edit = Mock(side_effect=TimeoutError('fixture provider timeout'))
    context.image_client = SimpleNamespace(images=SimpleNamespace(edit=edit))
    destination = context.root / 'sketches' / 'A1'
    with pytest.raises(TimeoutError):
        context.image_call('sketch/A1', 'Draw the fixture object.', destination, **image_inputs)
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), image_client=context.image_client)
    with pytest.raises(ValueError, match='outcome is unknown'):
        retry.image_call('sketch/A1', 'Draw the fixture object.', destination, **image_inputs)
    assert edit.call_count == 1 and scoped_spend(context.round)['reserved_usd'] == 1
    assert not (destination / 'image-call.json').exists()


@pytest.fixture
def anthropic_transport():
    clients = []
    def build(handler):
        client = anthropic.Anthropic(api_key='fixture-not-a-real-key', max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        clients.append(client)
        return client
    yield build
    for client in clients:
        client.close()


def sdk_reply(stop='end_turn', text='{"ok":true}', *, usage=None):
    return {'id': 'msg_fixture', 'type': 'message', 'role': 'assistant',
            'model': 'claude-opus-5-5', 'stop_reason': stop, 'stop_sequence': None,
            'content': [{'type': 'thinking', 'thinking': 'Fixture reasoning, never a verdict.',
                         'signature': 'fixture-signature'}, {'type': 'text', 'text': text}],
            'usage': usage if usage is not None else {'input_tokens': 100, 'output_tokens': 40}}


@pytest.mark.parametrize('operation,effort', [
    ('seeds', 'medium'), ('check/A1', 'low'), ('eye/A1', 'low'),
    ('blind/A1', 'low'), ('reading/A1', 'low'), ('eye-r2', 'low'), ('coarse/J1', 'medium'),
    ('pairwise/shortlist/J1/0', 'medium'), ('fragment/A1', 'medium'),
])
def test_anthropic_sdk_serializes_adaptive_thinking_for_every_round_profile(context, anthropic_transport, operation, effort):
    requests = []
    def transport(request):
        assert request.method == 'POST' and request.url.path == '/v1/messages'
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=sdk_reply())
    context.text_client = anthropic_transport(transport)
    output = context.root / 'profile.json'
    result = context.text_call(operation, 'Read this fixture.', output, max_tokens=2048, ceiling=1)
    assert len(requests) == 1
    body = requests[0]
    assert body['model'] == 'claude-opus-5-5'
    assert body['max_tokens'] == (8192 if effort == 'low' else 16384)
    assert body['thinking'] == {'type': 'adaptive'}
    assert body['output_config'] == {'effort': effort}
    assert body['messages'] == [{'role': 'user', 'content': [{'type': 'text', 'text': 'Read this fixture.'}]}]
    saved = json.loads(output.with_suffix('.request.json').read_text())
    assert saved['thinking'] == result['thinking'] == body['thinking']
    assert saved['output_config'] == result['output_config'] == body['output_config']
    assert result['payload'] == {'ok': True}
    assert scoped_spend(context.round)['calls'] == 1 and scoped_spend(context.round)['reserved_usd'] == 0


@pytest.mark.parametrize('second_stop', ['end_turn', 'max_tokens'])
def test_sdk_truncation_is_one_reserved_retry_and_prices_all_returned_tokens(context, anthropic_transport, second_stop):
    from apps.pipeline.services.cost_ledger import claude_cost_usd
    first_usage = {'input_tokens': 100, 'output_tokens': 80,
                   'cache_creation_input_tokens': 10, 'cache_read_input_tokens': 30,
                   'output_tokens_details': {'thinking_tokens': 60}}
    second_usage = {'input_tokens': 140, 'output_tokens': 40,
                    'cache_creation_input_tokens': 20, 'cache_read_input_tokens': 50,
                    'output_tokens_details': {'thinking_tokens': 10}}
    replies = [sdk_reply('max_tokens', '{', usage=first_usage),
               sdk_reply(second_stop, '{"ok":true}' if second_stop == 'end_turn' else '{', usage=second_usage)]
    requests, reservation_ids = [], []
    def transport(request):
        requests.append(json.loads(request.content))
        with spend._connect() as db:
            rows = [dict(row) for row in db.execute('SELECT * FROM calls')]
        assert len(rows) == 1 and rows[0]['state'] == 'reserved'
        reservation_ids.append(rows[0]['id'])
        assert len(requests) <= 2
        if len(requests) == 2:
            first_billing = json.loads(output.with_suffix('.billing.json').read_text())
            assert first_billing['attempts'] == 1
            assert first_billing['token_split'] == {'output_tokens': 80, 'thinking_tokens': 60,
                'non_thinking_output_tokens_estimate': 20, 'split_status': 'reported'}
            assert first_billing['attempt_token_splits'] == [first_billing['token_split']]
        return httpx.Response(200, json=replies[len(requests)-1])
    context.text_client = anthropic_transport(transport)
    output = context.root / 'eye.json'
    if second_stop == 'end_turn':
        result = context.text_call('eye/A1', 'Read this fixture.', output, max_tokens=2048, ceiling=1)
        assert result['payload'] == {'ok': True}
    else:
        with pytest.raises(ValueError, match='not a verdict'):
            context.text_call('eye/A1', 'Read this fixture.', output, max_tokens=2048, ceiling=1)
        result = json.loads(output.read_text())
        assert result['status'] == 'incomplete'
    assert len(requests) == 2 and len(set(reservation_ids)) == 1
    assert all(body['thinking'] == {'type': 'adaptive'} and body['output_config'] == {'effort': 'low'}
               for body in requests)
    assert result['attempts'] == 2
    assert result['token_split'] == {'output_tokens': 120, 'thinking_tokens': 70,
        'non_thinking_output_tokens_estimate': 50, 'split_status': 'reported'}
    assert result['attempt_token_splits'] == [
        {'output_tokens': 80, 'thinking_tokens': 60, 'non_thinking_output_tokens_estimate': 20, 'split_status': 'reported'},
        {'output_tokens': 40, 'thinking_tokens': 10, 'non_thinking_output_tokens_estimate': 30, 'split_status': 'reported'},
    ]
    billing = json.loads(output.with_suffix('.billing.json').read_text())
    assert billing['token_split'] == result['token_split']
    assert billing['attempt_token_splits'] == result['attempt_token_splits']
    assert result['usage'] == {'input_tokens': 240, 'output_tokens': 120,
                             'cache_creation_input_tokens': 30, 'cache_read_input_tokens': 80}
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    billable_inputs = 240 + 1.25 * 30 + spend.cache_read_multiplier('claude-opus-5-5') * 80
    assert row['state'] == 'usage_recorded'
    assert row['accounted'] == int(claude_cost_usd('claude-opus-5-5', billable_inputs, 120) * 1_000_000)
    assert scoped_spend(context.round)['calls'] == 1 and scoped_spend(context.round)['reserved_usd'] == 0
    assert json.loads(output.with_suffix('.response-0.json').read_text())['content'][0]['type'] == 'thinking'
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    if second_stop == 'end_turn':
        assert restarted.text_call('eye/A1', 'Read this fixture.', output, max_tokens=2048, ceiling=1) == result
    else:
        with pytest.raises(ValueError, match='not a verdict'):
            restarted.text_call('eye/A1', 'Read this fixture.', output, max_tokens=2048, ceiling=1)
    assert len(requests) == 2


@pytest.mark.parametrize('details', [None, {}, {'thinking_tokens': -1}, {'thinking_tokens': 41},
                                   {'thinking_tokens': True}, {'thinking_tokens': '4'}])
def test_sdk_missing_or_invalid_thinking_counts_remain_unknown(context, anthropic_transport, details):
    usage = {'input_tokens': 100, 'output_tokens': 40}
    if details is not None:
        usage['output_tokens_details'] = details
    context.text_client = anthropic_transport(lambda request: httpx.Response(200, json=sdk_reply(usage=usage)))
    output = context.root / 'reading.json'
    result = context.text_call('blind/A1', 'Read this fixture.', output, max_tokens=2048, ceiling=1)
    assert result['token_split'] == {'output_tokens': 40, 'thinking_tokens': None,
        'non_thinking_output_tokens_estimate': None, 'split_status': 'unavailable'}
    assert result['attempt_token_splits'] == [result['token_split']]
    assert result['usage']['output_tokens'] == 40 and result['billing_state'] == 'usage_recorded'
    assert result['payload'] == {'ok': True}


def test_sdk_retry_with_one_unknown_thinking_split_does_not_invent_an_aggregate(context, anthropic_transport):
    replies = [sdk_reply('max_tokens', '{', usage={'input_tokens': 100, 'output_tokens': 80,
                    'output_tokens_details': {'thinking_tokens': 60}}), sdk_reply()]
    count = 0
    def transport(request):
        nonlocal count
        response = replies[count]
        count += 1
        return httpx.Response(200, json=response)
    context.text_client = anthropic_transport(transport)
    result = context.text_call('eye/A1', 'Read this fixture.', context.root / 'eye.json', max_tokens=2048, ceiling=1)
    assert count == 2 and result['usage']['output_tokens'] == 120
    assert result['token_split'] == {'output_tokens': 120, 'thinking_tokens': None,
        'non_thinking_output_tokens_estimate': None, 'split_status': 'unavailable'}
    assert result['attempt_token_splits'][0]['thinking_tokens'] == 60
    assert result['attempt_token_splits'][1]['thinking_tokens'] is None
    assert scoped_spend(context.round)['calls'] == 1


def test_sdk_400_legacy_disabled_request_is_archived_only_after_explicit_app_retry(context, anthropic_transport):
    requests = []
    def transport(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(400, json={'type': 'error', 'error': {'type': 'invalid_request_error',
                'message': 'Fixture unsupported thinking mode rejection.'}}, headers={'request-id': 'req_fixture_400'})
        assert len(requests) == 2
        return httpx.Response(200, json=sdk_reply())
    context.text_client = anthropic_transport(transport)
    output = context.root / 'seeds-call.json'
    with pytest.raises(anthropic.BadRequestError):
        context.text_call('seeds', 'Return fixture seeds.', output, max_tokens=3500, ceiling=1)
    request_path, error_path = output.with_suffix('.request.json'), output.with_suffix('.error-0.json')
    retained = json.loads(request_path.read_text())
    error_bytes = error_path.read_bytes()
    assert json.loads(error_bytes)['http_status'] == 400
    with spend._connect() as db:
        original = dict(db.execute('SELECT * FROM calls').fetchone())
    assert original['state'] == 'rejected_unbilled' and original['accounted'] == 0
    assert len(requests) == 1 and not output.exists()

    # Isolated historical fixture: the actual rejected request used the pre-fix identity.
    # No legacy request is sent; rewrite only this test's retained request and matching ledger hash.
    legacy_identity = {key: retained[key] for key in ('model', 'prompt', 'images')}
    legacy_identity.update(max_tokens=3500, thinking={'type': 'disabled'})
    legacy_digest = hashlib.sha256(json.dumps(legacy_identity, sort_keys=True).encode()).hexdigest()
    retained.pop('output_config')
    retained.update(legacy_identity, request_sha256=legacy_digest)
    request_path.write_text(json.dumps(retained))
    legacy_request_bytes = request_path.read_bytes()
    with spend._connect() as db:
        db.execute('UPDATE calls SET request_hash=? WHERE id=?', (legacy_digest, original['id']))
    same_app_attempt = RoundContext(context.round, context.job, text_client=context.text_client)
    with pytest.raises(ValueError, match='silently change'):
        same_app_attempt.text_call('seeds', 'Return fixture seeds.', output, max_tokens=3500, ceiling=1)
    assert len(requests) == 1 and not (context.root / 'call-history').exists()
    assert request_path.read_bytes() == legacy_request_bytes

    # The persisted app-attempt number changes only in the owner Retry service.
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    result = retry.text_call('seeds', 'Return fixture seeds.', output, max_tokens=3500, ceiling=1)
    archive = context.root / 'call-history' / ('seeds-call-' + original['id'])
    assert (archive / request_path.name).read_bytes() == legacy_request_bytes
    assert (archive / error_path.name).read_bytes() == error_bytes
    assert result['reservation_id'] != original['id'] and result['payload'] == {'ok': True}
    assert requests[-1]['thinking'] == {'type': 'adaptive'}
    assert requests[-1]['output_config'] == {'effort': 'medium'}
    assert requests[-1]['max_tokens'] == 16384
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls ORDER BY started_at')]
    assert len(rows) == 2 and rows[0]['state'] == 'rejected_unbilled' and rows[0]['accounted'] == 0
    assert rows[1]['state'] == 'usage_recorded'
    assert scoped_spend(context.round)['reserved_usd'] == 0
    replay = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    assert replay.text_call('seeds', 'Return fixture seeds.', output, max_tokens=3500, ceiling=1) == result
    assert len(requests) == 2



def test_sdk_reported_output_split_survives_missing_billing_input_tokens(context, anthropic_transport):
    requests = []
    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=sdk_reply(usage={
            'output_tokens': 40, 'output_tokens_details': {'thinking_tokens': 10}}))
    context.text_client = anthropic_transport(transport)
    output = context.root / 'reading.json'
    result = context.text_call('reading/A1', 'Read this fixture.', output, max_tokens=2048, ceiling=1)
    assert result['token_split'] == {'output_tokens': 40, 'thinking_tokens': 10,
        'non_thinking_output_tokens_estimate': 30, 'split_status': 'reported'}
    assert result['attempt_token_splits'] == [result['token_split']]
    assert result['usage'] is None and result['billing_state'] == 'billing_unresolved'
    assert result['cost_usd'] is None and result['payload'] == {'ok': True}
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    assert row['state'] == 'billing_unresolved' and row['accounted'] == row['reserved'] > 0
    assert scoped_spend(context.round)['actual_usd'] == 0
    assert scoped_spend(context.round)['reserved_usd'] == row['reserved'] / 1_000_000
    replay = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    assert replay.text_call('reading/A1', 'Read this fixture.', output, max_tokens=2048, ceiling=1) == result
    assert len(requests) == scoped_spend(context.round)['calls'] == 1


def reading_payload(count=10):
    words = 'one two three four five six seven eight nine ten eleven twelve'.split()
    return {'idea_in_ten_words': ' '.join(words[:count]), 'proof_panel': 'body_left',
            'proof': 'The side repeats the visible interval.', 'preserve': 'The interval on body_left.'}


def reading_usage(attempt):
    multiplier = attempt + 1
    return {'input_tokens': 100 * multiplier, 'output_tokens': 40 * multiplier,
            'cache_creation_input_tokens': 10 * multiplier, 'cache_read_input_tokens': 20 * multiplier,
            'output_tokens_details': {'thinking_tokens': 10 * multiplier}}


def assert_reading_attempt_wire_record(output, attempt, body):
    """Inspect the durable request from inside the real SDK's transport callback."""
    saved = json.loads(output.with_suffix(f'.attempt-{attempt}.request.json').read_text())
    base = json.loads(output.with_suffix('.request.json').read_text())
    assert saved['prompt'] == body['messages'][0]['content'][-1]['text']
    assert saved['images'] == base['images']
    assert saved['request_sha256'] == base['request_sha256']
    assert saved['canonical_body_sha256'] == hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    for key in ('model', 'thinking', 'output_config', 'max_tokens'):
        assert saved[key] == body[key]
    # The first request identity remains compatible with paid readings from before this fix.
    identity = {key: base[key] for key in ('model', 'thinking', 'output_config', 'max_tokens', 'prompt', 'images')}
    assert base['request_sha256'] == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def assert_reading_settlement(result, attempts):
    from apps.pipeline.services.cost_ledger import claude_cost_usd
    multiple = sum(range(1, attempts + 1))
    assert result['usage'] == {'input_tokens': 100 * multiple, 'output_tokens': 40 * multiple,
                             'cache_creation_input_tokens': 10 * multiple, 'cache_read_input_tokens': 20 * multiple}
    assert result['token_split'] == {'output_tokens': 40 * multiple, 'thinking_tokens': 10 * multiple,
        'non_thinking_output_tokens_estimate': 30 * multiple, 'split_status': 'reported'}
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls')]
    assert len(rows) == 1 and rows[0]['id'] == result['reservation_id'] and rows[0]['state'] == 'usage_recorded'
    billed_inputs = (100 + 1.25 * 10 + spend.cache_read_multiplier('claude-opus-5-5') * 20) * multiple
    assert rows[0]['accounted'] == int(claude_cost_usd('claude-opus-5-5', billed_inputs, 40 * multiple) * 1_000_000)


@pytest.mark.parametrize('operation', ['blind/A1', 'reading/A1', 'readings/A1'])
@pytest.mark.parametrize('final_words', [10, 11])
def test_sdk_reading_reasks_once_on_same_reservation_and_retains_final_text(
        context, anthropic_transport, operation, final_words):
    output = context.root / 'blind-call.json'
    context.root.mkdir(parents=True)
    picture = context.root / 'picture.png'
    Image.new('RGB', (16, 12), 'gold').save(picture)
    prompt = 'Read the visible invention in at most TEN words. Café.'
    responses = [reading_payload(11), reading_payload(final_words)]
    bodies, reservation_ids = [], []
    def transport(request):
        attempt = len(bodies)
        assert attempt < 2  # Even a second overlong answer must not buy a third request.
        body = json.loads(request.content)
        assert_reading_attempt_wire_record(output, attempt, body)
        with spend._connect() as db:
            rows = [dict(row) for row in db.execute('SELECT * FROM calls')]
        assert len(rows) == 1 and rows[0]['state'] == 'reserved'
        reservation_ids.append(rows[0]['id'])
        if attempt:
            first = json.loads(output.with_suffix('.billing.json').read_text())
            assert first['attempts'] == 1 and first['token_split']['thinking_tokens'] == 10
        bodies.append(body)
        return httpx.Response(200, json=sdk_reply(text=json.dumps(responses[attempt]), usage=reading_usage(attempt)))
    context.text_client = anthropic_transport(transport)
    result = context.text_call(operation, prompt, output, images=[('Whole object', picture)], max_tokens=2048, ceiling=1)
    assert result['status'] == 'complete' and result['payload'] == responses[-1]
    assert result['reading_length'] == {'word_count': final_words, 'over_length': final_words > 10, 'reasked': True}
    assert result['attempts'] == len(bodies) == 2 and len(set(reservation_ids)) == 1
    assert bodies[0]['messages'][0]['content'][-1]['text'] == prompt
    assert bodies[1]['messages'][0]['content'][:-1] == bodies[0]['messages'][0]['content'][:-1]
    correction = bodies[1]['messages'][0]['content'][-1]['text']
    assert correction.startswith(prompt + '\n') and 'exactly ten words' in correction.lower()
    assert_reading_settlement(result, 2)
    raw = json.loads(output.with_suffix('.response-0.json').read_text())
    assert json.loads(raw['content'][-1]['text']) == responses[0]
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    assert restarted.text_call(operation, prompt, output, images=[('Whole object', picture)], max_tokens=2048, ceiling=1) == result
    assert len(bodies) == 2 and scoped_spend(context.round)['reserved_usd'] == 0


@pytest.mark.parametrize('count', [1, 10])
def test_sdk_reading_within_limit_is_not_reasked(context, anthropic_transport, count):
    bodies = []
    def transport(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=sdk_reply(text=json.dumps(reading_payload(count)), usage=reading_usage(0)))
    context.text_client = anthropic_transport(transport)
    result = context.text_call('blind/A1', 'Read this picture.', context.root / 'blind.json', ceiling=1)
    assert result['reading_length'] == {'word_count': count, 'over_length': False, 'reasked': False}
    assert result['payload'] == reading_payload(count) and len(bodies) == 1
    assert_reading_settlement(result, 1)


@pytest.mark.parametrize('sequence,correction_flags', [
    (['truncated', 'overlong', 'good'], [False, False, True]),
    (['overlong', 'truncated', 'good'], [False, True, True]),
    (['truncated', 'overlong', 'overlong'], [False, False, True]),
    (['overlong', 'truncated', 'truncated'], [False, True, True]),
    (['truncated', 'truncated'], [False, False]),
])
def test_sdk_reading_truncation_and_length_retries_have_independent_global_limits(
        context, anthropic_transport, sequence, correction_flags):
    output = context.root / 'blind-call.json'
    bodies = []
    def transport(request):
        attempt = len(bodies)
        assert attempt < len(sequence)
        body = json.loads(request.content)
        assert_reading_attempt_wire_record(output, attempt, body)
        with spend._connect() as db:
            rows = list(db.execute('SELECT state FROM calls'))
        assert len(rows) == 1 and rows[0]['state'] == 'reserved'
        bodies.append(body)
        kind = sequence[attempt]
        if kind == 'truncated':
            response = sdk_reply('max_tokens', '{', usage=reading_usage(attempt))
        else:
            response = sdk_reply(text=json.dumps(reading_payload(11 if kind == 'overlong' else 10)), usage=reading_usage(attempt))
        return httpx.Response(200, json=response)
    context.text_client = anthropic_transport(transport)
    if sequence[-1] == 'truncated':
        with pytest.raises(ValueError, match='not a verdict'):
            context.text_call('blind/A1', 'Read the whole object.', output, ceiling=1)
        result = json.loads(output.read_text())
        assert result['status'] == 'incomplete'
    else:
        result = context.text_call('blind/A1', 'Read the whole object.', output, ceiling=1)
        assert result['status'] == 'complete'
        assert result['reading_length'] == {'word_count': 11 if sequence[-1] == 'overlong' else 10,
            'over_length': sequence[-1] == 'overlong', 'reasked': True}
    assert len(bodies) == result['attempts'] == len(sequence) <= 3
    assert [('exactly ten words' in body['messages'][0]['content'][-1]['text'].lower()) for body in bodies] == correction_flags
    assert_reading_settlement(result, len(sequence))


@pytest.mark.parametrize('crash_after', [0, 1])
def test_reading_reask_resumes_saved_raw_responses_without_repayment(
        context, anthropic_transport, monkeypatch, crash_after):
    from apps.pipeline.services import round_calls
    output = context.root / 'blind-call.json'
    bodies = []
    def transport(request):
        attempt = len(bodies)
        assert attempt < 2
        body = json.loads(request.content)
        assert_reading_attempt_wire_record(output, attempt, body)
        bodies.append(body)
        return httpx.Response(200, json=sdk_reply(text=json.dumps(reading_payload(11 if attempt == 0 else 10)),
                                                usage=reading_usage(attempt)))
    context.text_client = anthropic_transport(transport)
    original_commit = round_calls.commit_artifacts
    def stop_after_raw(record, detail):
        if detail.endswith(f'raw reply {crash_after + 1} saved'):
            raise OSError('fixture worker interrupted after durable raw reply')
        return original_commit(record, detail)
    with monkeypatch.context() as crash:
        crash.setattr(round_calls, 'commit_artifacts', stop_after_raw)
        with pytest.raises(OSError, match='worker interrupted'):
            context.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    assert len(bodies) == crash_after + 1 and not output.exists()
    first_bytes = output.with_suffix('.response-0.json').read_bytes()
    with spend._connect() as db:
        before = dict(db.execute('SELECT * FROM calls').fetchone())
    assert before['state'] == 'reserved'
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    result = restarted.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    assert result['reservation_id'] == before['id'] and result['reading_length']['reasked']
    assert output.with_suffix('.response-0.json').read_bytes() == first_bytes
    assert len(bodies) == 2
    assert_reading_settlement(result, 2)


@pytest.mark.parametrize('failure', ['rejected', 'unknown'])
def test_reading_reask_failure_settles_only_known_usage_or_retains_unknown_hold(
        context, anthropic_transport, failure):
    output = context.root / 'blind-call.json'
    bodies = []
    def transport(request):
        attempt = len(bodies)
        assert attempt < 2
        body = json.loads(request.content)
        assert_reading_attempt_wire_record(output, attempt, body)
        bodies.append(body)
        if attempt == 0:
            return httpx.Response(200, json=sdk_reply(text=json.dumps(reading_payload(11)), usage=reading_usage(0)))
        assert json.loads(output.with_suffix('.billing.json').read_text())['attempts'] == 1
        if failure == 'unknown':
            raise httpx.ReadTimeout('fixture unknown correction outcome', request=request)
        return httpx.Response(400, json={'type': 'error', 'error': {
            'type': 'invalid_request_error', 'message': 'Fixture correction rejected before billing.'}})
    context.text_client = anthropic_transport(transport)
    error = anthropic.BadRequestError if failure == 'rejected' else anthropic.APITimeoutError
    with pytest.raises(error):
        context.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    if failure == 'unknown':
        assert row['state'] == 'reserved' and row['accounted'] == row['reserved']
    else:
        assert row['state'] == 'usage_recorded' and row['accounted'] < row['reserved']
        assert json.loads(row['usage'])['output_tokens'] == 40
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    with pytest.raises(ValueError):
        restarted.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    assert len(bodies) == 2 and scoped_spend(context.round)['calls'] == 1


def test_historical_overlong_reading_archives_only_on_owner_retry_and_keeps_prior_completion(
        context, anthropic_transport):
    from apps.pipeline.services import round_calls, round_flow
    prompt = 'Read this object in at most TEN words.'
    bodies = []
    def transport(request):
        attempt = len(bodies)
        assert attempt < 3
        bodies.append(json.loads(request.content))
        # A1 is already complete; only the replacement A3 needs one correction.
        count = 11 if attempt == 1 else 10
        return httpx.Response(200, json=sdk_reply(text=json.dumps(reading_payload(count)), usage=reading_usage(0)))
    context.text_client = anthropic_transport(transport)
    first_path = context.root / 'A1' / 'blind-call.json'
    first = context.text_call('blind/A1', prompt, first_path, ceiling=1)
    first_bytes = first_path.read_bytes()

    # Build the pre-fix, already-settled failure entirely inside this fixture ledger.
    old_path = context.root / 'A3' / 'blind-call.json'
    identity = {**round_calls._text_settings('blind/A3', 3000), 'prompt': prompt, 'images': []}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    old_id = spend.reserve('anthropic', context.prefix + 'blind/A3', 'claude-opus-5-5', .4, digest,
                           budget_prefix=context.prefix, prefix_cap=22)
    raw = sdk_reply(text=json.dumps(reading_payload(11)), usage=reading_usage(0))
    billing = round_calls._text_accounting([raw])
    round_flow.write_json(old_path.with_suffix('.request.json'), dict(identity, request_sha256=digest,
        reservation_id=old_id, reserved_usd=.4, started_attempts=[0], app_attempt=0))
    round_flow.write_json(old_path.with_suffix('.response-0.json'), raw)
    round_flow.write_json(old_path.with_suffix('.billing.json'), billing)
    spend.settle(old_id, billing, old_path.with_suffix('.billing.json'), provider='anthropic', model='claude-opus-5-5')
    round_flow.write_json(old_path, dict(identity, status='validation_failed', payload=reading_payload(11),
        validation_error='Blind reading exceeds ten words; retained, not rewritten',
        request_sha256=digest, reservation_id=old_id, stop_reason='end_turn', **billing, **round_calls._billing(old_id)))
    retained = {path.name: path.read_bytes() for path in old_path.parent.iterdir()}
    with spend._connect() as db:
        old_ledger = dict(db.execute('SELECT * FROM calls WHERE id=?', (old_id,)).fetchone())
    same_attempt = RoundContext(context.round, context.job, text_client=context.text_client)
    with pytest.raises(ValueError):
        same_attempt.text_call('blind/A3', prompt, old_path, ceiling=1)
    assert len(bodies) == 1 and not (old_path.parent / 'call-history').exists()
    retry = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    assert retry.text_call('blind/A1', prompt, first_path, ceiling=1) == first
    assert first_path.read_bytes() == first_bytes and len(bodies) == 1
    replacement = retry.text_call('blind/A3', prompt, old_path, ceiling=1)
    archive = old_path.parent / 'call-history' / ('blind-call-' + old_id)
    for name, data in retained.items():
        assert (archive / name).read_bytes() == data
    assert replacement['reservation_id'] != old_id and replacement['reading_length'] == {
        'word_count': 10, 'over_length': False, 'reasked': True}
    assert replacement['attempts'] == 2 and len(bodies) == 3
    with spend._connect() as db:
        assert dict(db.execute('SELECT * FROM calls WHERE id=?', (old_id,)).fetchone()) == old_ledger
    assert scoped_spend(context.round)['calls'] == 3
    replay = RoundContext(context.round, SimpleNamespace(attempts=1), text_client=context.text_client)
    assert replay.text_call('blind/A3', prompt, old_path, ceiling=1) == replacement
    assert len(bodies) == 3


def test_reading_reserves_three_attempts_before_payment_and_respects_remaining_cap(context, anthropic_transport):
    output = context.root / 'blind-call.json'
    context.root.mkdir(parents=True)
    picture = context.root / 'picture.png'
    Image.new('RGB', (1536, 1024), 'white').save(picture)
    requests = []
    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=sdk_reply())
    context.text_client = anthropic_transport(transport)
    context.round.budget_usd = .5
    # The old two-attempt estimate fits, but the independent length reask must be reserved too.
    context.text_call('eye/A1', 'Read this picture.', context.root / 'eye.json', images=[('Whole object', picture)], ceiling=1)
    reading = RoundContext(context.round, context.job, text_client=context.text_client)
    with pytest.raises(BudgetExceededError):
        reading.text_call('blind/A1', 'Read this picture.', output, images=[('Whole object', picture)], ceiling=1)
    assert len(requests) == 1 and scoped_spend(context.round)['calls'] == 1
    assert not output.with_suffix('.request.json').exists()


def test_saved_legacy_reading_hold_cannot_expand_to_three_attempts_on_resume(context, anthropic_transport, monkeypatch):
    from apps.pipeline.services import round_calls
    output = context.root / 'blind-call.json'
    requests = []
    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=sdk_reply('max_tokens', '{', usage=reading_usage(0)))
    context.text_client = anthropic_transport(transport)
    def stop_after_raw(record, detail):
        if detail.endswith('raw reply 1 saved'):
            raise OSError('fixture pre-fix interruption')
    with monkeypatch.context() as crash:
        crash.setattr(round_calls, 'commit_artifacts', stop_after_raw)
        with pytest.raises(OSError, match='pre-fix interruption'):
            context.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    request_path = output.with_suffix('.request.json')
    saved = json.loads(request_path.read_text())
    saved['reserved_usd'] *= 2 / 3  # Only this isolated persisted request models the older two-attempt hold.
    request_path.write_text(json.dumps(saved))
    raw_bytes = output.with_suffix('.response-0.json').read_bytes()
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    with pytest.raises(ValueError, match='does not cover'):
        restarted.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    assert len(requests) == scoped_spend(context.round)['calls'] == 1
    assert output.with_suffix('.response-0.json').read_bytes() == raw_bytes
    assert json.loads(request_path.read_text())['started_attempts'] == [0]
    assert not output.with_suffix('.response-1.json').exists()


def test_saved_valid_legacy_reading_recovers_with_old_hold_without_new_provider_call(
        context, anthropic_transport, monkeypatch):
    from apps.pipeline.services import round_calls
    output = context.root / 'blind-call.json'
    requests = []
    def transport(request):
        requests.append(json.loads(request.content))
        assert len(requests) == 1
        return httpx.Response(200, json=sdk_reply(text=json.dumps(reading_payload(6)), usage=reading_usage(0)))
    context.text_client = anthropic_transport(transport)
    def stop_after_raw(record, detail):
        if detail.endswith('raw reply 1 saved'):
            raise OSError('fixture legacy raw saved before interpretation')
    with monkeypatch.context() as crash:
        crash.setattr(round_calls, 'commit_artifacts', stop_after_raw)
        with pytest.raises(OSError, match='before interpretation'):
            context.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    request_path = output.with_suffix('.request.json')
    saved = json.loads(request_path.read_text())
    saved['reserved_usd'] *= 2 / 3
    request_path.write_text(json.dumps(saved))
    output.with_suffix('.attempt-0.request.json').unlink()  # Historical calls predate per-attempt request records.
    # Both persisted request and this isolated ledger now carry the old two-attempt hold.
    with spend._connect() as db:
        held = int(round(saved['reserved_usd'] * 1_000_000))
        db.execute('UPDATE calls SET reserved=?,accounted=? WHERE id=?', (held, held, saved['reservation_id']))
    raw_bytes = output.with_suffix('.response-0.json').read_bytes()
    assert not output.exists()
    restarted = RoundContext(context.round, context.job, text_client=context.text_client)
    result = restarted.text_call('blind/A1', 'Read this object.', output, ceiling=1)
    assert result['status'] == 'complete' and result['payload'] == reading_payload(6)
    assert result['reading_length'] == {'word_count': 6, 'over_length': False, 'reasked': False}
    assert result['reservation_id'] == saved['reservation_id'] and result['attempts'] == 1
    assert len(requests) == scoped_spend(context.round)['calls'] == 1
    assert output.with_suffix('.response-0.json').read_bytes() == raw_bytes
    assert not output.with_suffix('.attempt-1.request.json').exists()
    assert_reading_settlement(result, 1)


def test_master_eye_uses_disjoint_budget_and_never_accepts_truncation(context):
    from apps.pipeline.services.round_calls import MasterContext,master_scoped_spend as master_spend
    build=SimpleNamespace(round=context.round,budget_usd=15,inputs={'brief':{}},pk=123)
    create=Mock(side_effect=[reply('max_tokens','{'),reply('max_tokens','{')])
    ctx=MasterContext(build,SimpleNamespace(attempts=0),text_client=SimpleNamespace(messages=SimpleNamespace(create=create)))
    with pytest.raises(ValueError,match='not a verdict'):
        ctx.text_call('eye/body/r0','Compare.',ctx.root/'eye-call.json',max_tokens=12288,ceiling=1.5)
    assert create.call_count==2
    assert all(c.kwargs['thinking']=={'type':'adaptive'} and c.kwargs['max_tokens']>=12288 for c in create.call_args_list)
    assert master_spend(build)['calls']==1 and master_spend(build)['held_usd']==0
    assert scoped_spend(context.round)['calls']==0
    saved=json.loads((ctx.root/'eye-call.json').read_text())
    assert saved['status']=='incomplete'
    # Same delivery replay cannot buy a third reply.
    again=MasterContext(build,SimpleNamespace(attempts=0),text_client=ctx.text_client)
    with pytest.raises(ValueError,match='not a verdict'):
        again.text_call('eye/body/r0','Compare.',again.root/'eye-call.json',max_tokens=12288,ceiling=1.5)
    assert create.call_count==2


def test_master_masked_edit_retains_bad_shape_for_explicit_owner_retry(context):
    from apps.pipeline.services.round_calls import MasterContext
    build=SimpleNamespace(round=context.round,budget_usd=15,inputs={'brief':{}},pk=123)
    ctx=MasterContext(build,SimpleNamespace(attempts=0))
    ctx.root.mkdir(parents=True)
    target=ctx.root/'input.png';mask=ctx.root/'mask.png'
    Image.new('RGB',(1536,1024),'white').save(target)
    m=Image.new('RGBA',(1536,1024),(255,255,255,255));m.paste((255,255,255,0),(10,10,100,100));m.save(mask)
    edit=Mock(return_value={'data':[None],'usage':{'input_tokens':10,'output_tokens':10,
        'input_tokens_details':{'text_tokens':10,'image_tokens':0},'output_tokens_details':{'image_tokens':10}}})
    ctx.image_client=SimpleNamespace(images=SimpleNamespace(edit=edit))
    with pytest.raises(ValueError,match='Invalid master image'):
        ctx.masked_edit('detail/test','Preserve.',ctx.root/'call',target=target,mask=mask)
    assert json.loads((ctx.root/'call/image-call.json').read_text())['status']=='validation_failed'
    assert edit.call_count==1


@pytest.fixture
def ideas_context(context):
    from apps.pipeline.services.round_calls import IdeasContext
    context.round.budget_usd = 10
    return IdeasContext(context.round, context.job)


def test_ideas_generate_real_sdk_contract_preserves_exact_png_and_replays(ideas_context):
    from openai import OpenAI
    from apps.pipeline.services.round_calls import IdeasContext
    requests = []
    response = image_reply()
    provider_bytes = base64.b64decode(response['data'][0]['b64_json'])

    def transport(request):
        requests.append(request)
        return httpx.Response(200, json=response)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        client = OpenAI(api_key='fixture-only', max_retries=0, http_client=http_client)
        ideas_context.image_client = client
        output = ideas_context.root / 'ideas' / 'I01'
        result = ideas_context.design_image_call('ideas/I01', 'An original product and twelve-unit counterstand.', output)
        assert requests[0].url.path == '/v1/images/generations'
        body = json.loads(requests[0].content)
        assert body == {'model': 'gpt-image-2', 'quality': 'high', 'size': '1536x1024',
                        'n': 1, 'output_format': 'png',
                        'prompt': 'An original product and twelve-unit counterstand.'}
        assert (output / 'raw.png').read_bytes() == provider_bytes
        assert result['output_sha256'] == hashlib.sha256(provider_bytes).hexdigest()
        assert result['output_px'] == [1536, 1024]
        assert result['billing_state'] == 'usage_recorded'
        assert result['cost_usd'] == spend.openai_image_cost_micro('gpt-image-2', response['usage']) / 1e6
        assert .25 < result['reserved_usd'] < .4
        saved_raw = json.loads((output / 'image-call.response.json').read_text())
        assert saved_raw['data'][0]['b64_json'] == response['data'][0]['b64_json']
        restarted = IdeasContext(ideas_context.round, ideas_context.job, image_client=client)
        assert restarted.design_image_call('ideas/I01', body['prompt'], output) == result
        assert len(requests) == scoped_spend(ideas_context.round)['calls'] == 1
        assert len((ideas_context.root / 'image-calls.jsonl').read_text().splitlines()) == 1
        with pytest.raises(YieldRound):
            ideas_context.design_image_call('ideas/I02', 'Another original.', ideas_context.root / 'ideas' / 'I02')
        assert len(requests) == 1


@pytest.mark.parametrize('invalid,reason', [
    ({'data': []}, 'Exactly one paid image'),
    ({'data': [None]}, 'Exactly one paid image'),
    ({'item': {}}, 'bytes missing'),
    ({'item': {'b64_json': '!!!'}}, 'not valid base64'),
    ({'item': {'b64_json': base64.b64encode(b'not an image').decode()}}, 'cannot be decoded'),
    ({'size': (100, 100)}, 'wrong dimensions'),
])
def test_ideas_invalid_reply_settles_and_only_owner_retry_can_replace(ideas_context, invalid, reason):
    from apps.pipeline.services.round_calls import IdeasContext
    bad = dict(image_reply(), **invalid) if 'data' in invalid else image_reply(**invalid)
    generate = Mock(side_effect=[bad, image_reply()])
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    output = ideas_context.root / 'ideas' / 'I01'
    with pytest.raises(ValueError, match=reason):
        ideas_context.design_image_call('ideas/I01', 'Original.', output)
    failed = json.loads((output / 'image-call.json').read_text())
    assert failed['status'] == 'validation_failed'
    assert failed['billing_state'] == 'usage_recorded' and failed['cost_usd'] > 0
    assert not (output / 'raw.png').exists()
    assert not (ideas_context.root / 'image-calls.jsonl').exists()
    again = IdeasContext(ideas_context.round, ideas_context.job, image_client=ideas_context.image_client)
    with pytest.raises(ValueError, match=reason):
        again.design_image_call('ideas/I01', 'Original.', output)
    assert generate.call_count == 1
    assert len((ideas_context.root / 'call-validation.jsonl').read_text().splitlines()) == 1
    retry = IdeasContext(ideas_context.round, SimpleNamespace(attempts=1), image_client=ideas_context.image_client)
    replacement = retry.design_image_call('ideas/I01', 'Original.', output)
    assert replacement['status'] == 'complete'
    assert replacement['reservation_id'] != failed['reservation_id']
    assert generate.call_count == scoped_spend(ideas_context.round)['calls'] == 2
    archived = output / 'call-history' / ('image-call-' + failed['reservation_id'])
    assert json.loads((archived / 'image-call.json').read_text()) == failed
    assert json.loads((archived / 'image-call.response.json').read_text()) == bad


def test_ideas_non_png_is_a_paid_validation_failure(ideas_context):
    output = BytesIO()
    Image.new('RGB', (1536, 1024), 'white').save(output, format='JPEG')
    generate = Mock(return_value=image_reply(item={'b64_json': base64.b64encode(output.getvalue()).decode()}))
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    path = ideas_context.root / 'ideas' / 'I01'
    with pytest.raises(ValueError, match='not PNG'):
        ideas_context.design_image_call('ideas/I01', 'Original.', path)
    result = json.loads((path / 'image-call.json').read_text())
    assert result['status'] == 'validation_failed' and result['billing_state'] == 'usage_recorded'
    assert not (path / 'raw.png').exists()


@pytest.mark.parametrize('failure', ['after_raw', 'write_png', 'download'])
def test_ideas_local_failure_recovers_saved_reply_without_repurchase(ideas_context, monkeypatch, failure):
    from apps.pipeline.services import round_calls as image_producer        # the boundary downloads (2026-10-28)
    from apps.pipeline.services import round_calls as round_ideas_calls
    from apps.pipeline.services.round_calls import IdeasContext
    response = image_reply()
    exact = base64.b64decode(response['data'][0]['b64_json'])
    if failure == 'download':
        response['data'] = [{'url': 'https://fixture.invalid/paid.png'}]
        download = Mock(side_effect=[OSError('fixture local failure'), exact])
        monkeypatch.setattr(image_producer, 'download_image_bytes', download)
    generate = Mock(return_value=response)
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    path = ideas_context.root / 'ideas' / 'I01'
    original_write = Path.write_bytes

    def fail_write(self, data):
        if self == path / 'raw.png':
            raise OSError('fixture local failure')
        return original_write(self, data)

    def fail_commit(record, detail):
        if detail.endswith('raw image reply saved'):
            raise OSError('fixture local failure')

    with monkeypatch.context() as crash:
        if failure == 'write_png':
            crash.setattr(Path, 'write_bytes', fail_write)
        elif failure == 'after_raw':
            crash.setattr(round_ideas_calls, 'commit_artifacts', fail_commit)
        with pytest.raises(OSError, match='fixture local failure'):
            ideas_context.design_image_call('ideas/I01', 'Original.', path)
    assert (path / 'image-call.response.json').exists() and not (path / 'image-call.json').exists()
    raw_reply = (path / 'image-call.response.json').read_bytes()
    restarted = IdeasContext(ideas_context.round, SimpleNamespace(attempts=1), image_client=ideas_context.image_client)
    result = restarted.design_image_call('ideas/I01', 'Original.', path)
    assert result['status'] == 'complete' and (path / 'raw.png').read_bytes() == exact
    assert (path / 'image-call.response.json').read_bytes() == raw_reply
    assert generate.call_count == scoped_spend(ideas_context.round)['calls'] == 1
    assert not (path / 'call-history').exists()


def test_ideas_unknown_outcome_holds_reservation_even_after_owner_retry(ideas_context):
    from apps.pipeline.services.round_calls import IdeasContext
    generate = Mock(side_effect=TimeoutError('fixture timeout'))
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    output = ideas_context.root / 'ideas' / 'I01'
    with pytest.raises(TimeoutError):
        ideas_context.design_image_call('ideas/I01', 'Original.', output)
    retry = IdeasContext(ideas_context.round, SimpleNamespace(attempts=1), image_client=ideas_context.image_client)
    with pytest.raises(ValueError, match='outcome is unknown'):
        retry.design_image_call('ideas/I01', 'Original.', output)
    assert generate.call_count == scoped_spend(ideas_context.round)['calls'] == 1
    state = scoped_spend(ideas_context.round)
    assert state['actual_usd'] == 0 and state['reserved_usd'] > .25
    assert json.loads((output / 'image-call.error.json').read_text())['http_status'] is None


def test_ideas_owner_cap_blocks_before_generation(ideas_context):
    generate = Mock()
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    spend.reserve('anthropic', ideas_context.prefix + 'prior', 'test', 9.9,
                  budget_prefix=ideas_context.prefix, prefix_cap=10)
    with pytest.raises(BudgetExceededError):
        ideas_context.design_image_call('ideas/I01', 'Original.', ideas_context.root / 'ideas' / 'I01')
    generate.assert_not_called()
    assert scoped_spend(ideas_context.round)['calls'] == 1


def test_ideas_attempt_cap_counts_rejected_calls_and_blocks_before_generation(ideas_context):
    for index in range(ideas_context.image_attempt_cap):
        reservation = spend.reserve('openai', ideas_context.prefix + f'image/prior/{index}', 'gpt-image-2', .01,
                                    budget_prefix=ideas_context.prefix, prefix_cap=10)
        spend.release_rejected(reservation, 400, ValueError('fixture rejection'))
    generate = Mock()
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    with pytest.raises(BudgetExceededError):
        ideas_context.design_image_call('ideas/I01', 'Original.', ideas_context.root / 'ideas' / 'I01')
    generate.assert_not_called()
    assert scoped_spend(ideas_context.round)['calls'] == 40


def test_ideas_estimate_tracks_tariff_and_refuses_missing_tariff_before_payment(ideas_context, settings):
    from apps.pipeline.services.round_calls import design_image_estimate
    prompt = 'An original gloss product with a twelve-unit counterstand.'
    first = design_image_estimate(prompt)
    settings.OPENAI_IMAGE_PRICES = {'gpt-image-2': {'text_input': 10.0, 'image_output': 60.0, 'image_input': 16.0}}
    assert design_image_estimate(prompt) == pytest.approx(2 * first, abs=.000002)
    assert design_image_estimate(prompt * 100) > design_image_estimate(prompt)
    settings.OPENAI_IMAGE_PRICES = {}
    generate = Mock()
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    with pytest.raises(ValueError, match='tariff'):
        ideas_context.design_image_call('ideas/I01', prompt, ideas_context.root / 'ideas' / 'I01')
    generate.assert_not_called()
    assert scoped_spend(ideas_context.round)['calls'] == 0


def test_ideas_changed_request_or_paid_bytes_never_repurchase(ideas_context):
    from apps.pipeline.services.round_calls import IdeasContext
    generate = Mock(return_value=image_reply())
    ideas_context.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate))
    output = ideas_context.root / 'ideas' / 'I01'
    ideas_context.design_image_call('ideas/I01', 'Original.', output)
    restarted = IdeasContext(ideas_context.round, SimpleNamespace(attempts=1), image_client=ideas_context.image_client)
    with pytest.raises(ValueError, match='silently change'):
        restarted.design_image_call('ideas/I01', 'Changed.', output)
    (output / 'raw.png').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='no repurchase'):
        restarted.design_image_call('ideas/I01', 'Original.', output)
    assert generate.call_count == scoped_spend(ideas_context.round)['calls'] == 1


def test_ideas_unbilled_sdk_rejection_needs_owner_retry_and_keeps_attempt_history(ideas_context):
    from openai import BadRequestError, OpenAI
    from apps.pipeline.services.round_calls import IdeasContext
    requests = []

    def transport(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(400, json={'error': {'message': 'fixture rejection', 'type': 'invalid_request_error'}})
        return httpx.Response(200, json=image_reply())

    with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
        client = OpenAI(api_key='fixture-only', max_retries=0, http_client=http_client)
        ideas_context.image_client = client
        output = ideas_context.root / 'ideas' / 'I01'
        with pytest.raises(BadRequestError):
            ideas_context.design_image_call('ideas/I01', 'Original.', output)
        old_request = json.loads((output / 'image-call.request.json').read_text())
        with spend._connect() as db:
            row = dict(db.execute('SELECT * FROM calls WHERE id=?', (old_request['reservation_id'],)).fetchone())
        assert row['state'] == 'rejected_unbilled' and row['accounted'] == 0
        again = IdeasContext(ideas_context.round, ideas_context.job, image_client=client)
        with pytest.raises(ValueError, match='outcome is unknown'):
            again.design_image_call('ideas/I01', 'Original.', output)
        assert len(requests) == 1
        retry = IdeasContext(ideas_context.round, SimpleNamespace(attempts=1), image_client=client)
        result = retry.design_image_call('ideas/I01', 'Original.', output)
        assert result['status'] == 'complete' and result['reservation_id'] != old_request['reservation_id']
        archive = output / 'call-history' / ('image-call-' + old_request['reservation_id'])
        assert json.loads((archive / 'image-call.error.json').read_text())['http_status'] == 400
        assert len(requests) == scoped_spend(ideas_context.round)['calls'] == 2


@pytest.fixture
def ideas_seed_retry_case(ideas_context):
    """Create the historical rejection through the real durable text-call path."""
    from apps.pipeline.services import round_ideas as ideas
    from apps.pipeline.services.round_designer import gloss_brief
    ideas_context.round.product_brief = ideas_context.brief = gloss_brief()
    rows = [{'id': key, 'family': ideas.FAMILIES[key[0]],
             'seed': f'Clear acrylic and a rising frost line connect the product and loaded stand for direction {key}.',
             'link': 'Visible liquid provides shade colour beneath printed frost and engraved gold.'}
            for key in ideas.IDS]
    by_id = {row['id']: row for row in rows}
    by_id['D2']['seed'] = ('A pale woven ribbon of frost crosses clear acrylic and rises across the stand header '
                           'while visible liquid supplies every shade below.')
    by_id['D3']['seed'] = ('Gold cap engravings align with slender header arches, turning the bottles into a gallery '
                           'where transparent colour remains the central feature.')
    assert len(by_id['D2']['seed'].split()) == 22
    assert len(by_id['D3']['seed'].split()) == 21
    payload = {'seeds': rows}
    create = Mock(return_value=reply(text=json.dumps(payload)))
    ideas_context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    result = ideas.seeds(ideas_context)
    destination = ideas_context.root / 'seeds-call.json'
    old_reason = 'Each starting point needs its family and a short product-truth link'
    ideas_context.reject_result(destination, old_reason)
    (ideas_context.root / 'seeds.json').unlink()
    assert create.call_count == 1 and scoped_spend(ideas_context.round)['calls'] == 1
    return SimpleNamespace(ctx=ideas_context, create=create, result=result, destination=destination,
                           payload=payload, old_reason=old_reason)


def _ideas_seed_retry_sources(case):
    return {path.relative_to(case.ctx.root): path.read_bytes() for path in case.ctx.root.rglob('*')
            if path.is_file() and path.name not in ('seeds.json', 'seeds-call.revalidation.json')}


def _ideas_seed_retry_ledger():
    with spend._connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM calls ORDER BY id')]


def test_ideas_seed_retry_revalidates_paid_long_reply_without_changing_source_or_charging(ideas_seed_retry_case):
    from apps.pipeline.services import round_ideas as ideas
    from apps.pipeline.services.round_calls import IdeasContext
    case = ideas_seed_retry_case
    sources = _ideas_seed_retry_sources(case)
    ledger = _ideas_seed_retry_ledger()
    retry = IdeasContext(case.ctx.round, SimpleNamespace(attempts=1), text_client=case.ctx.text_client)
    result = ideas.seeds(retry)
    assert result == case.result
    assert result['length_observations']['advisory_only'] is True
    assert result['length_observations']['words']['D2']['seed'] == 22
    assert result['length_observations']['words']['D3']['seed'] == 21
    assert case.create.call_count == 1 and retry.new_calls == 0
    assert _ideas_seed_retry_ledger() == ledger
    assert _ideas_seed_retry_sources(case) == sources
    prior = json.loads(case.destination.read_text())
    request_path = case.destination.with_suffix('.request.json')
    raw_path = case.destination.with_suffix('.response-0.json')
    receipt_path = case.destination.with_suffix('.revalidation.json')
    receipt = json.loads(receipt_path.read_text())
    assert receipt == {
        'schema': 'seed_reply_revalidation/1', 'validation': 'structure required; word targets advisory',
        'status': 'accepted', 'request_sha256': prior['request_sha256'],
        'reservation_id': prior['reservation_id'],
        'paid_record_sha256': hashlib.sha256(case.destination.read_bytes()).hexdigest(),
        'request_file_sha256': hashlib.sha256(request_path.read_bytes()).hexdigest(),
        'provider_reply_sha256': hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        'app_attempt': 1, 'previous_error': case.old_reason, 'additional_provider_calls': 0}
    assert prior['status'] == 'validation_failed' and prior['validation_error'] == case.old_reason
    assert not (case.ctx.root / 'call-history').exists()
    receipt_bytes = receipt_path.read_bytes()
    replay = IdeasContext(case.ctx.round, SimpleNamespace(attempts=1), text_client=case.ctx.text_client)
    assert ideas.seeds(replay) == result
    assert case.create.call_count == 1 and replay.new_calls == 0
    assert receipt_path.read_bytes() == receipt_bytes
    assert _ideas_seed_retry_sources(case) == sources and _ideas_seed_retry_ledger() == ledger


@pytest.mark.parametrize('job', [None, SimpleNamespace(attempts=0)])
def test_ideas_seed_retry_requires_owner_retry_before_reusing_reply(ideas_seed_retry_case, job):
    from apps.pipeline.services import round_ideas as ideas
    from apps.pipeline.services.round_calls import IdeasContext
    case = ideas_seed_retry_case
    sources, ledger = _ideas_seed_retry_sources(case), _ideas_seed_retry_ledger()
    replay = IdeasContext(case.ctx.round, job, text_client=case.ctx.text_client)
    with pytest.raises(ValueError, match='owner.*app Retry'):
        ideas.seeds(replay)
    assert case.create.call_count == 1 and replay.new_calls == 0
    assert _ideas_seed_retry_sources(case) == sources and _ideas_seed_retry_ledger() == ledger
    assert not (case.ctx.root / 'seeds.json').exists()
    assert not case.destination.with_suffix('.revalidation.json').exists()


@pytest.mark.parametrize('mismatch', [
    'request_identity', 'request_digest', 'paid_record_digest', 'reservation', 'billing',
    'paid_record_truncation', 'raw_truncation', 'raw_payload', 'started_attempts',
    'missing_ids', 'duplicate_ids', 'wrong_family', 'competitor', 'empty_link', 'multiline_link',
])
def test_ideas_seed_retry_refuses_changed_or_invalid_paid_reply_without_repurchase(ideas_seed_retry_case, mismatch):
    from apps.pipeline.services import round_ideas as ideas
    from apps.pipeline.services.round_calls import IdeasContext
    case = ideas_seed_retry_case
    request_path = case.destination.with_suffix('.request.json')
    raw_path = case.destination.with_suffix('.response-0.json')
    prior = json.loads(case.destination.read_text())
    request = json.loads(request_path.read_text())
    raw = json.loads(raw_path.read_text())
    if mismatch == 'request_identity':
        request['prompt'] += ' Changed after payment.'
    elif mismatch == 'request_digest':
        request['request_sha256'] = '0' * 64
    elif mismatch == 'paid_record_digest':
        prior['request_sha256'] = '0' * 64
    elif mismatch == 'reservation':
        prior['reservation_id'] = 'different-paid-call'
    elif mismatch == 'billing':
        prior['billing_state'] = 'billing_unresolved'
    elif mismatch == 'paid_record_truncation':
        prior['stop_reason'] = 'max_tokens'
    elif mismatch == 'raw_truncation':
        raw['stop_reason'] = 'max_tokens'
    elif mismatch == 'raw_payload':
        changed = json.loads(raw['content'][0]['text'])
        changed['seeds'][0]['seed'] += ' Changed after payment.'
        raw['content'][0]['text'] = json.dumps(changed)
    elif mismatch == 'started_attempts':
        request['started_attempts'] = []
    else:
        rows = prior['payload']['seeds']
        if mismatch == 'missing_ids':
            rows.pop()
        elif mismatch == 'duplicate_ids':
            rows[-1]['id'] = rows[0]['id']
        elif mismatch == 'wrong_family':
            rows[0]['family'] = 'material'
        elif mismatch == 'competitor':
            rows[0]['seed'] = 'Use the Chanel reference design.'
        elif mismatch == 'empty_link':
            rows[0]['link'] = ' '
        elif mismatch == 'multiline_link':
            rows[0]['link'] = 'Visible coloured liquid.\nA second line.'
        raw['content'][0]['text'] = json.dumps(prior['payload'])
    # Corrupt only this temporary historical fixture; capture it before Retry.
    for path, value in ((case.destination, prior), (request_path, request), (raw_path, raw)):
        path.write_text(json.dumps(value))
    sources, ledger = _ideas_seed_retry_sources(case), _ideas_seed_retry_ledger()
    retry = IdeasContext(case.ctx.round, SimpleNamespace(attempts=1), text_client=case.ctx.text_client)
    with pytest.raises(ValueError):
        ideas.seeds(retry)
    assert case.create.call_count == 1 and retry.new_calls == 0
    assert _ideas_seed_retry_sources(case) == sources and _ideas_seed_retry_ledger() == ledger
    assert not (case.ctx.root / 'seeds.json').exists()
    assert not case.destination.with_suffix('.revalidation.json').exists()
    assert not (case.ctx.root / 'call-history').exists()


def _jury_completion_payload(batch, shown):
    return {'pairs': [{'pair': list(pair), 'winner': pair[0],
                       'relationship': f'{pair[0]} connects the product decoration and stand header more clearly.'}
                      for pair in batch],
            'ideas': {key: f'A rising frost line connects the clear product and stand for {key}.' for key in shown}}


def _jury_completion_sources(row):
    paths = [row.destination, row.destination.with_suffix('.request.json'), row.destination.with_suffix('.billing.json')]
    paths.extend(row.destination.parent.glob(row.destination.stem + '.response-*.json'))
    return {path.name: path.read_bytes() for path in paths if path.is_file()}


def _jury_completion_call(ctx, row):
    from apps.pipeline.services.round_jury_completion import complete_batch
    return complete_batch(ctx, row.operation, row.prompt, row.destination,
                          images=row.images, batch=row.batch, shown=row.shown)


@pytest.fixture
def jury_completion_case(ideas_context):
    from itertools import combinations
    from apps.pipeline.services.round_calls import IdeasContext
    create = Mock()
    image_generate, image_edit = Mock(), Mock()
    text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    image_client = SimpleNamespace(images=SimpleNamespace(generate=image_generate, edit=image_edit))
    ideas_context.root.mkdir(parents=True)
    batches = [[['A1', 'A2']], [['B1', 'B2']],
               [list(pair) for pair in combinations([f'{family}{number}' for family in 'CD' for number in range(1, 6)], 2)]]
    saved = []
    for index, batch in enumerate(batches, 1):
        shown = sorted({key for pair in batch for key in pair})
        images = []
        for key in shown:
            picture = ideas_context.root / 'jury' / 'views' / (key + '.png')
            picture.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (768, 512), 'white').save(picture)
            images.append((key, picture))
        payload = _jury_completion_payload(batch, shown)
        if index == 3:
            payload['pairs'] = [row for row in payload['pairs'] if row['pair'] != ['C5', 'D5']]
        create.return_value = reply(text=json.dumps(payload))
        row = SimpleNamespace(operation=f'pairwise/ideas/J1/{index}',
            prompt='Compare every listed pair.\nSHOWN: ' + json.dumps(shown) + '\nPAIRS: ' + json.dumps(batch),
            destination=ideas_context.root / 'jury' / f'J1-{index}.json', images=images, batch=batch,
            shown=shown, payload=payload)
        delivery = IdeasContext(ideas_context.round, SimpleNamespace(attempts=0),
                                text_client=text_client, image_client=image_client)
        row.record = delivery.text_call(row.operation, row.prompt, row.destination,
                                        images=images, max_tokens=16384, ceiling=2.0)
        if index == 3:
            delivery.reject_result(row.destination, 'Missing pairs')
        saved.append(row)
    assert create.call_count == 3 and len(saved[-1].payload['pairs']) == 44
    return SimpleNamespace(ctx=ideas_context, create=create, image_generate=image_generate, image_edit=image_edit,
                           text_client=text_client, image_client=image_client, rows=saved, partial=saved[-1])


def _jury_completion_context(case, attempt=1):
    from apps.pipeline.services.round_calls import IdeasContext
    return IdeasContext(case.ctx.round, SimpleNamespace(attempts=attempt),
                        text_client=case.text_client, image_client=case.image_client)


def test_jury_completion_legacy_failure_requires_owner_retry(jury_completion_case):
    case = jury_completion_case
    source, ledger = _jury_completion_sources(case.partial), _ideas_seed_retry_ledger()
    with pytest.raises(ValueError):
        _jury_completion_call(_jury_completion_context(case, attempt=0), case.partial)
    assert case.create.call_count == 3
    assert _jury_completion_sources(case.partial) == source and _ideas_seed_retry_ledger() == ledger
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


@pytest.mark.parametrize('mismatch', ['raw', 'image', 'prompt', 'ledger_hash', 'ledger_billing', 'ledger_operation'])
def test_jury_completion_changed_legacy_identity_refuses_without_payment(jury_completion_case, mismatch):
    case, row = jury_completion_case, jury_completion_case.partial
    if mismatch == 'raw':
        raw_path = row.destination.with_suffix('.response-0.json')
        raw = json.loads(raw_path.read_text())
        payload = json.loads(raw['content'][0]['text'])
        payload['pairs'][0]['winner'] = payload['pairs'][0]['pair'][1]
        raw['content'][0]['text'] = json.dumps(payload)
        raw_path.write_text(json.dumps(raw))
    elif mismatch == 'image':
        Image.new('RGB', (768, 512), 'black').save(row.images[0][1])
    elif mismatch == 'prompt':
        row.prompt += '\nChanged after the paid comparison.'
    else:
        column, value = {'ledger_hash': ('request_hash', 'changed-hash'),
                         'ledger_billing': ('state', 'billing_unresolved'),
                         'ledger_operation': ('operation', 'another-round/another-call')}[mismatch]
        with spend._connect() as db:
            db.execute(f'UPDATE calls SET {column}=? WHERE id=?', (value, row.record['reservation_id']))
    source, ledger = _jury_completion_sources(row), _ideas_seed_retry_ledger()
    with pytest.raises(ValueError):
        _jury_completion_call(_jury_completion_context(case), row)
    assert case.create.call_count == 3
    assert _jury_completion_sources(row) == source and _ideas_seed_retry_ledger() == ledger
    assert not (row.destination.parent / 'call-history').exists()
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


@pytest.mark.parametrize('malformation', [
    'non_object', 'duplicate', 'unexpected', 'invalid_winner', 'empty_relationship',
    'unexpected_note', 'nontext_note', 'multiline_note',
])
def test_jury_completion_invalid_original_votes_cannot_be_salvaged(jury_completion_case, malformation):
    case, row = jury_completion_case, jury_completion_case.partial
    prior = json.loads(row.destination.read_text())
    payload = prior['payload']
    if malformation == 'non_object':
        payload['pairs'][0] = None
    elif malformation == 'duplicate':
        payload['pairs'].append(dict(payload['pairs'][0]))
    elif malformation == 'unexpected':
        payload['pairs'][0]['pair'] = ['A1', 'A2']
        payload['pairs'][0]['winner'] = 'A1'
    elif malformation == 'invalid_winner':
        payload['pairs'][0]['winner'] = 'A1'
    elif malformation == 'empty_relationship':
        payload['pairs'][0]['relationship'] = ' '
    elif malformation == 'unexpected_note':
        payload['ideas']['A1'] = 'An unrequested idea.'
    elif malformation == 'nontext_note':
        payload['ideas']['C1'] = {'text': 'A wrapped note.'}
    elif malformation == 'multiline_note':
        payload['ideas']['C1'] = 'First line.\nSecond line.'
    raw_path = row.destination.with_suffix('.response-0.json')
    raw = json.loads(raw_path.read_text())
    raw['content'][0]['text'] = json.dumps(payload)
    row.destination.write_text(json.dumps(prior))
    raw_path.write_text(json.dumps(raw))
    source, ledger = _jury_completion_sources(row), _ideas_seed_retry_ledger()
    with pytest.raises(ValueError):
        _jury_completion_call(_jury_completion_context(case), row)
    assert case.create.call_count == 3
    assert _jury_completion_sources(row) == source and _ideas_seed_retry_ledger() == ledger
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


def test_jury_completion_budget_refusal_retains_all_original_votes(jury_completion_case):
    case, row = jury_completion_case, jury_completion_case.partial
    spend.reserve('anthropic', case.ctx.prefix + 'fixture-budget-hold', 'test', 9.99,
                  budget_prefix=case.ctx.prefix, prefix_cap=10)
    source, ledger = _jury_completion_sources(row), _ideas_seed_retry_ledger()
    with pytest.raises(BudgetExceededError):
        _jury_completion_call(_jury_completion_context(case), row)
    assert case.create.call_count == 3
    assert _jury_completion_sources(row) == source and _ideas_seed_retry_ledger() == ledger
    assert len(json.loads(row.destination.read_text())['payload']['pairs']) == 44
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


def test_jury_completion_no_progress_is_bounded_and_never_success(jury_completion_case):
    case, row = jury_completion_case, jury_completion_case.partial
    source = _jury_completion_sources(row)
    case.create.return_value = reply(text=json.dumps({'pairs': [], 'ideas': {}}))
    failed = False
    for _ in range(5):
        before = case.create.call_count
        try:
            _jury_completion_call(_jury_completion_context(case), row)
        except YieldRound:
            assert case.create.call_count - before <= 1
            continue
        except ValueError:
            failed = True
            break
        pytest.fail('An incomplete jury batch was accepted without its missing vote')
    assert failed and 3 < case.create.call_count <= 6
    assert _jury_completion_sources(row) == source
    assert scoped_spend(case.ctx.round)['image_calls'] == 0
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


def test_jury_completion_owner_retry_preserves_44_votes_and_reuses_unrelated_batches(jury_completion_case):
    case, row = jury_completion_case, jury_completion_case.partial
    sources = [_jury_completion_sources(saved) for saved in case.rows]
    original_ledger = _ideas_seed_retry_ledger()
    initial_paths = {path for path in case.ctx.root.rglob('*.json')}
    missing = _jury_completion_payload([['C5', 'D5']], [])
    case.create.return_value = reply(text=json.dumps(missing))
    retry = _jury_completion_context(case)
    for previous in case.rows[:2]:
        assert _jury_completion_call(retry, previous) == previous.payload
    assert case.create.call_count == 3 and retry.new_calls == 0
    result = _jury_completion_call(retry, row)
    assert result['ideas'] == row.payload['ideas']
    expected = {frozenset(vote['pair']): vote for vote in row.payload['pairs'] + missing['pairs']}
    assert {frozenset(vote['pair']): vote for vote in result['pairs']} == expected
    assert len(result['pairs']) == 45
    assert case.create.call_count == 4 and retry.new_calls == 1
    assert [_jury_completion_sources(saved) for saved in case.rows] == sources
    ledger = _ideas_seed_retry_ledger()
    assert len(ledger) == 4
    assert [saved for saved in ledger if saved['id'] in {old['id'] for old in original_ledger}] == original_ledger
    assert scoped_spend(case.ctx.round)['image_calls'] == 0
    # One receipt must pin the untouched paid result, request, and provider reply.
    source_paths = [row.destination, row.destination.with_suffix('.request.json'),
                    row.destination.with_suffix('.response-0.json')]
    pinned_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths]
    receipts = [json.loads(path.read_text()) for path in case.ctx.root.rglob('*.json') if path not in initial_paths]
    assert any(all(digest in json.dumps(receipt) for digest in pinned_hashes) for receipt in receipts)
    replay = _jury_completion_context(case)
    assert _jury_completion_call(replay, row) == result
    assert case.create.call_count == 4 and replay.new_calls == 0
    assert _ideas_seed_retry_ledger() == ledger
    assert [_jury_completion_sources(saved) for saved in case.rows] == sources
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


def test_jury_completion_fresh_partial_yields_after_one_paid_call_then_resumes(jury_completion_case):
    case, original = jury_completion_case, jury_completion_case.partial
    row = SimpleNamespace(**vars(original))
    row.destination = original.destination.with_name('J1-fresh.json')
    row.operation = 'pairwise/ideas/J1/fresh'
    case.create.return_value = reply(text=json.dumps(row.payload))
    delivery = _jury_completion_context(case, attempt=0)
    with pytest.raises(YieldRound):
        _jury_completion_call(delivery, row)
    assert case.create.call_count == 4 and delivery.new_calls == 1
    saved = json.loads(row.destination.read_text())
    assert len(saved['payload']['pairs']) == 44
    source = _jury_completion_sources(row)
    case.create.return_value = reply(text=json.dumps(_jury_completion_payload([['C5', 'D5']], [])))
    resumed = _jury_completion_context(case, attempt=0)
    result = _jury_completion_call(resumed, row)
    assert len(result['pairs']) == 45 and result['ideas'] == row.payload['ideas']
    assert case.create.call_count == 5 and resumed.new_calls == 1
    assert _jury_completion_sources(row) == source
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


@pytest.mark.parametrize('malformation', ['duplicate', 'unexpected', 'invalid_winner', 'non_object', 'unexpected_note'])
def test_jury_completion_invalid_followup_cannot_overwrite_retained_votes(jury_completion_case, malformation):
    case, row = jury_completion_case, jury_completion_case.partial
    source = _jury_completion_sources(row)
    payload = _jury_completion_payload([['C5', 'D5']], [])
    if malformation == 'duplicate':
        payload['pairs'].append(dict(payload['pairs'][0]))
    elif malformation == 'unexpected':
        payload['pairs'] = [row.payload['pairs'][0]]
    elif malformation == 'invalid_winner':
        payload['pairs'][0]['winner'] = 'A1'
    elif malformation == 'non_object':
        payload['pairs'][0] = None
    elif malformation == 'unexpected_note':
        payload['ideas']['C1'] = 'A replacement note for an already recorded idea.'
    case.create.return_value = reply(text=json.dumps(payload))
    with pytest.raises(ValueError):
        _jury_completion_call(_jury_completion_context(case), row)
    assert case.create.call_count == 4 and _jury_completion_sources(row) == source
    ledger = _ideas_seed_retry_ledger()
    with pytest.raises(ValueError):
        _jury_completion_call(_jury_completion_context(case), row)
    assert case.create.call_count == 4 and _ideas_seed_retry_ledger() == ledger
    assert _jury_completion_sources(row) == source
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


@pytest.mark.parametrize('missing_pair_count', [0, 23])
def test_jury_completion_requests_only_missing_pairs_and_notes_in_small_restartable_chunks(
        jury_completion_case, missing_pair_count):
    case, row = jury_completion_case, jury_completion_case.partial
    missing_pairs = row.batch[-missing_pair_count:] if missing_pair_count else []
    missing_keys = {frozenset(pair) for pair in missing_pairs}
    retained = _jury_completion_payload([pair for pair in row.batch if frozenset(pair) not in missing_keys], row.shown)
    for key in ('C5', 'D5'):
        del retained['ideas'][key]
    prior = json.loads(row.destination.read_text())
    prior['payload'] = retained
    raw_path = row.destination.with_suffix('.response-0.json')
    raw = json.loads(raw_path.read_text())
    raw['content'][0]['text'] = json.dumps(retained)
    row.destination.write_text(json.dumps(prior))
    raw_path.write_text(json.dumps(raw))
    source = _jury_completion_sources(row)
    requests = []

    def complete_requested(**kwargs):
        content = kwargs['messages'][0]['content']
        prompt = content[-1]['text']
        pairs = json.loads(prompt.rsplit('\nPAIRS: ', 1)[1])
        notes = json.loads(prompt.rsplit('\nNOTE_IDS: ', 1)[1].split('\nPAIRS: ', 1)[0])
        shown = json.loads(prompt.rsplit('\nSHOWN: ', 1)[1].split('\nNOTE_IDS: ', 1)[0])
        assert len(pairs) <= 10 and (pairs or notes)
        assert all(frozenset(pair) in missing_keys for pair in pairs)
        assert set(notes) <= {'C5', 'D5'}
        assert set(shown) == {key for pair in pairs for key in pair} | set(notes)
        assert sum(block['type'] == 'image' for block in content) == len(shown)
        requests.append({'pairs': pairs, 'notes': notes})
        return reply(text=json.dumps(_jury_completion_payload(pairs, notes)))

    case.create.side_effect = complete_requested
    result = None
    for _ in range(6):
        before = case.create.call_count
        try:
            result = _jury_completion_call(_jury_completion_context(case), row)
        except YieldRound:
            assert case.create.call_count - before <= 1
            continue
        assert case.create.call_count - before <= 1
        break
    assert result is not None and len(result['pairs']) == 45 and set(result['ideas']) == set(row.shown)
    requested_pairs = [frozenset(pair) for request in requests for pair in request['pairs']]
    assert len(requested_pairs) == len(set(requested_pairs)) == missing_pair_count
    assert set(requested_pairs) == missing_keys
    assert sorted(key for request in requests for key in request['notes']) == ['C5', 'D5']
    assert len(requests) == (3 if missing_pair_count else 1)
    by_pair = {frozenset(vote['pair']): vote for vote in result['pairs']}
    assert all(by_pair[frozenset(vote['pair'])] == vote for vote in retained['pairs'])
    assert all(result['ideas'][key] == value for key, value in retained['ideas'].items())
    assert _jury_completion_sources(row) == source
    ledger = _ideas_seed_retry_ledger()
    assert _jury_completion_call(_jury_completion_context(case), row) == result
    assert _ideas_seed_retry_ledger() == ledger and case.create.call_count == 3 + len(requests)
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


def test_jury_completion_exhausted_window_only_new_owner_retry_can_continue(jury_completion_case):
    case, row = jury_completion_case, jury_completion_case.partial
    case.create.return_value = reply(text=json.dumps({'pairs': [], 'ideas': {}}))
    # Three separately delivered, empty replies exhaust this owner's attempt.
    for number in range(1, 4):
        delivery = _jury_completion_context(case, attempt=1)
        with pytest.raises(YieldRound if number < 3 else ValueError):
            _jury_completion_call(delivery, row)
        assert case.create.call_count == 3 + number and delivery.new_calls == 1
    plan_path = row.destination.with_suffix('.completion-plan.json')
    assert plan_path.exists()
    plan_before = plan_path.read_bytes()
    original_plan = json.loads(plan_before)
    assert original_plan['windows'] == [{'app_attempt': 1, 'first_round': 1, 'last_round': 3}]
    fragments = {path: path.read_bytes() for path in row.destination.parent.glob(row.destination.stem + '.*')
                 if path.is_file() and path != plan_path}
    assert all(row.destination.with_name(row.destination.stem + f'.completion-{number}-1.json') in fragments
               for number in range(1, 4))
    ledger_before = _ideas_seed_retry_ledger()
    replay = _jury_completion_context(case, attempt=1)
    with pytest.raises(ValueError):
        _jury_completion_call(replay, row)
    assert replay.new_calls == 0 and case.create.call_count == 6
    assert _ideas_seed_retry_ledger() == ledger_before and plan_path.read_bytes() == plan_before
    assert all(path.read_bytes() == data for path, data in fragments.items())

    def provide_missing_vote(**kwargs):
        prompt = kwargs['messages'][0]['content'][-1]['text']
        assert json.loads(prompt.rsplit('\nPAIRS: ', 1)[1]) == [['C5', 'D5']]
        assert json.loads(prompt.rsplit('\nNOTE_IDS: ', 1)[1].split('\nPAIRS: ', 1)[0]) == []
        assert json.loads(prompt.rsplit('\nSHOWN: ', 1)[1].split('\nNOTE_IDS: ', 1)[0]) == ['C5', 'D5']
        return reply(text=json.dumps(_jury_completion_payload([['C5', 'D5']], [])))

    case.create.side_effect = provide_missing_vote
    owner_retry = _jury_completion_context(case, attempt=2)
    result = _jury_completion_call(owner_retry, row)
    assert len(result['pairs']) == 45 and result['ideas'] == row.payload['ideas']
    by_pair = {frozenset(vote['pair']): vote for vote in result['pairs']}
    assert all(by_pair[frozenset(vote['pair'])] == vote for vote in row.payload['pairs'])
    assert case.create.call_count == 7 and owner_retry.new_calls == 1
    assert row.destination.with_name(row.destination.stem + '.completion-4-1.json').exists()
    assert all(path.read_bytes() == data for path, data in fragments.items())
    updated_plan = json.loads(plan_path.read_text())
    assert updated_plan == dict(original_plan, windows=original_plan['windows'] + [
        {'app_attempt': 2, 'first_round': 4, 'last_round': 6}])
    ledger_after = _ideas_seed_retry_ledger()
    original_ids = {record['id'] for record in ledger_before}
    assert [record for record in ledger_after if record['id'] in original_ids] == ledger_before
    completed_replay = _jury_completion_context(case, attempt=2)
    assert _jury_completion_call(completed_replay, row) == result
    assert completed_replay.new_calls == 0 and case.create.call_count == 7
    assert _ideas_seed_retry_ledger() == ledger_after
    assert json.loads(plan_path.read_text()) == updated_plan
    with pytest.raises(ValueError, match='older worker'):
        _jury_completion_call(_jury_completion_context(case, attempt=1), row)
    assert case.create.call_count == 7 and _ideas_seed_retry_ledger() == ledger_after
    assert scoped_spend(case.ctx.round)['image_calls'] == 0
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()


def test_jury_completion_early_retry_must_stop_at_actual_exhaustion_before_new_window(jury_completion_case):
    case, row = jury_completion_case, jury_completion_case.partial
    case.create.return_value = reply(text=json.dumps({'pairs': [], 'ideas': {}}))
    first = _jury_completion_context(case, attempt=1)
    with pytest.raises(YieldRound):
        _jury_completion_call(first, row)
    assert case.create.call_count == 4 and first.new_calls == 1
    # A Retry before exhaustion can finish the existing window, but cannot also
    # open another window after spending its remaining two rounds.
    for expected_calls, outcome in ((5, YieldRound), (6, ValueError)):
        early_retry = _jury_completion_context(case, attempt=2)
        with pytest.raises(outcome):
            _jury_completion_call(early_retry, row)
        assert case.create.call_count == expected_calls and early_retry.new_calls == 1
    plan_path = row.destination.with_suffix('.completion-plan.json')
    original_plan = json.loads(plan_path.read_text())
    assert original_plan['windows'] == [{'app_attempt': 1, 'first_round': 1, 'last_round': 3}]
    exhausted_path = row.destination.with_suffix('.exhausted-3.json')
    exhausted = json.loads(exhausted_path.read_text())
    assert exhausted['app_attempt'] == 2 and exhausted['window'] == original_plan['windows'][0]
    assert exhausted['source_receipt_sha256'] == original_plan['source_receipt_sha256']
    assert not row.destination.with_name(row.destination.stem + '.completion-4-1.json').exists()
    retained = {path: path.read_bytes() for path in row.destination.parent.glob(row.destination.stem + '.*')
                if path.is_file() and path != plan_path}
    ledger_before = _ideas_seed_retry_ledger()
    repeated = _jury_completion_context(case, attempt=2)
    with pytest.raises(ValueError):
        _jury_completion_call(repeated, row)
    assert repeated.new_calls == 0 and case.create.call_count == 6
    assert json.loads(plan_path.read_text()) == original_plan and _ideas_seed_retry_ledger() == ledger_before
    assert all(path.read_bytes() == data for path, data in retained.items())

    def complete_after_exhaustion(**kwargs):
        prompt = kwargs['messages'][0]['content'][-1]['text']
        assert json.loads(prompt.rsplit('\nPAIRS: ', 1)[1]) == [['C5', 'D5']]
        assert json.loads(prompt.rsplit('\nNOTE_IDS: ', 1)[1].split('\nPAIRS: ', 1)[0]) == []
        return reply(text=json.dumps(_jury_completion_payload([['C5', 'D5']], [])))

    case.create.side_effect = complete_after_exhaustion
    later_retry = _jury_completion_context(case, attempt=3)
    result = _jury_completion_call(later_retry, row)
    assert len(result['pairs']) == 45 and result['ideas'] == row.payload['ideas']
    assert case.create.call_count == 7 and later_retry.new_calls == 1
    assert json.loads(plan_path.read_text()) == dict(original_plan, windows=original_plan['windows'] + [
        {'app_attempt': 3, 'first_round': 4, 'last_round': 6}])
    assert row.destination.with_name(row.destination.stem + '.completion-4-1.json').exists()
    assert all(path.read_bytes() == data for path, data in retained.items())
    assert scoped_spend(case.ctx.round)['image_calls'] == 0
    case.image_generate.assert_not_called()
    case.image_edit.assert_not_called()
