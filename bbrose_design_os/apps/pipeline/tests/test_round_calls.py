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
    record = SimpleNamespace(pk=999, slug='fixture-round', product_brief={}, budget_usd=22, artifacts={})
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
    # the owner's ruling of 2026-10-29: the first Retry checks the same paid reply again, at $0 ...
    rechecked = retry.text_call('blind/A3', prompt, old_path, ceiling=1)
    assert rechecked['payload'] == reading_payload(11) and rechecked['rechecked']['new_calls'] == 0 and len(bodies) == 1
    retry.reject_result(old_path, 'Blind reading exceeds ten words; retained, not rewritten')
    # ... and only a reply our check refuses again is bought anew, on the next Retry
    retry = RoundContext(context.round, SimpleNamespace(attempts=2), text_client=context.text_client)
    replacement = retry.text_call('blind/A3', prompt, old_path, ceiling=1)
    archive = old_path.parent / 'call-history' / ('blind-call-' + old_id)
    for name, data in retained.items():
        if name not in ('blind-call.json', 'blind-call.request.json'):
            assert (archive / name).read_bytes() == data
    assert json.loads((archive / 'blind-call.json').read_text())['rechecked']['app_attempt'] == 1
    assert replacement['reservation_id'] != old_id and replacement['reading_length'] == {
        'word_count': 10, 'over_length': False, 'reasked': True}
    assert replacement['attempts'] == 2 and len(bodies) == 3
    with spend._connect() as db:
        assert dict(db.execute('SELECT * FROM calls WHERE id=?', (old_id,)).fetchone()) == old_ledger
    assert scoped_spend(context.round)['calls'] == 3
    replay = RoundContext(context.round, SimpleNamespace(attempts=2), text_client=context.text_client)
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


def _seed_designer_image_attempts(context):
    for index in range(18):
        reservation = spend.reserve('openai', context.prefix + f'image/prior/{index}', 'gpt-image-2', .01,
                                    budget_prefix=context.prefix, prefix_cap=float(context.round.budget_usd))
        spend.release_rejected(reservation, 400, ValueError('fixture rejection'))


@pytest.mark.parametrize('permission', [None, False, 1, 'true'])
def test_designer_image_attempt_limit_needs_explicit_round_exception(context, permission):
    from apps.pipeline.services.round_designer import DesignerContext
    context.round.budget_usd = 3
    if permission is not None:
        context.round.artifacts['image_attempts_limited_by_budget'] = permission
    designer = DesignerContext(context.round, context.job)
    _seed_designer_image_attempts(designer)

    with pytest.raises(BudgetExceededError, match='Image-attempt limit'):
        designer._request(designer.root / 'image-19.json', {'model': 'gpt-image-2'},
                          provider='openai', operation='image/19', estimate=.1)

    assert designer.image_attempt_cap == 18
    assert scoped_spend(designer.round)['image_calls'] == 18
    assert not (designer.root / 'image-19.request.json').exists()


def test_designer_round_exception_allows_more_images_but_keeps_dollar_cap(context):
    from apps.pipeline.services.round_designer import DesignerContext
    context.round.budget_usd = 3
    context.round.artifacts['image_attempts_limited_by_budget'] = True
    designer = DesignerContext(context.round, context.job)
    _seed_designer_image_attempts(designer)

    for index in (19, 20):
        resumed = DesignerContext(context.round, context.job)
        cached, request, path = resumed._request(
            resumed.root / f'image-{index}.json', {'model': 'gpt-image-2'},
            provider='openai', operation=f'image/{index}', estimate=.1)
        assert cached is None and request['reserved_usd'] == .1 and path.exists()

    resumed = DesignerContext(context.round, context.job)
    with pytest.raises(BudgetExceededError, match='owner-scoped allowance'):
        resumed._request(resumed.root / 'image-21.json', {'model': 'gpt-image-2'},
                         provider='openai', operation='image/21', estimate=2.9)
    assert scoped_spend(designer.round)['image_calls'] == 20
    assert scoped_spend(designer.round)['reserved_usd'] == pytest.approx(.2)
    assert context.round.budget_usd == resumed.round_cap == 3
    assert not (resumed.root / 'image-21.request.json').exists()

    other_record = SimpleNamespace(**{**vars(context.round), 'slug': 'other-round', 'budget_usd': 2, 'artifacts': {}})
    other = DesignerContext(other_record, context.job)
    _seed_designer_image_attempts(other)
    with pytest.raises(BudgetExceededError, match='Image-attempt limit'):
        other._request(other.root / 'image-19.json', {'model': 'gpt-image-2'},
                       provider='openai', operation='image/19', estimate=.1)
    assert other.image_attempt_cap == DesignerContext.image_attempt_cap == 18
    assert other.round_cap == 2
    assert scoped_spend(other_record)['image_calls'] == 18


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


def _ideas_seed_retry_sources(case):
    return {path.relative_to(case.ctx.root): path.read_bytes() for path in case.ctx.root.rglob('*')
            if path.is_file() and path.name not in ('seeds.json', 'seeds-call.revalidation.json')}


def _ideas_seed_retry_ledger():
    with spend._connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM calls ORDER BY id')]


def _jury_completion_payload(batch, shown):
    return {'pairs': [{'pair': list(pair), 'winner': pair[0],
                       'relationship': f'{pair[0]} connects the product decoration and stand header more clearly.'}
                      for pair in batch],
            'ideas': {key: f'A rising frost line connects the clear product and stand for {key}.' for key in shown}}


def _jury_completion_sources(row):
    paths = [row.destination, row.destination.with_suffix('.request.json'), row.destination.with_suffix('.billing.json')]
    paths.extend(row.destination.parent.glob(row.destination.stem + '.response-*.json'))
    return {path.name: path.read_bytes() for path in paths if path.is_file()}


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




# --- the owner's ruling of 2026-10-29: one design round, brief to Make my files, at most $2.00 all in -------------------

def test_one_cap_holds_a_whole_round_across_its_prefixes_and_stops_in_words(context):
    """Every call whose operation names the round counts toward its one cap — the ideas' round/<slug>/ and the files'
    files/<slug>/ alike — and a call that would pass it is refused before it is made, in plain words, at $0."""
    from apps.pipeline.services import round_calls
    context.round.budget_usd = round_calls.ROUND_CAP_USD
    context.round_cap = round_calls.ROUND_CAP_USD
    spent = spend.reserve('openai', 'files/%s/image/face/header/1' % context.round.slug, 'gpt-image-2', 1.9,
                          round_slug=context.round.slug, round_cap=2.0)
    spend.settle(spent, {'usage': None}, 'fixture', provider='openai', model='gpt-image-2')    # kept at its hold
    create = Mock(side_effect=[reply()])
    context.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    with pytest.raises(BudgetExceededError, match=r'spent \$1\.90 of its \$2\.00 cap.*Nothing more is spent'):
        context.text_call('eye', 'Look.', context.root / 'eye.json', max_tokens=100, ceiling=1)
    assert create.call_count == 0 and not (context.root / 'eye.request.json').exists()
    with pytest.raises(ValueError, match='round-capped reservation'):
        spend.reserve('anthropic', 'round/another-round/eye', 'claude-opus-5-5', .01, round_slug=context.round.slug,
                      round_cap=2.0)


def test_a_round_under_the_ruling_reads_on_sonnet_and_sketches_at_medium_and_an_older_one_keeps_its_settings(context):
    """The cuts apply to a round stamped with the ruling's cost rules (round_flow.create_round); a round made before
    keeps the model and quality its saved calls were made with, so a saved reply still matches its request."""
    from apps.pipeline.services import round_calls
    older = RoundContext(context.round, context.job)
    ruled = RoundContext(SimpleNamespace(pk=1000, slug='ruled-round', product_brief={}, budget_usd=2,
                                         artifacts={'cost_rules': round_calls.COST_RULES}), context.job)
    assert ruled.ruled and not older.ruled
    for operation in ('research', 'reading/A1', 'locate-picture'):
        assert round_calls._text_settings(operation, 100, light=True)['model'] == 'claude-sonnet-5-5'
        assert round_calls._text_settings(operation, 100)['model'] == round_calls.TEXT_MODEL
    for operation in ('boards/g1', 'designs/g1', 'eye/header/1', 'checks/designs/g1'):
        assert round_calls._text_settings(operation, 100, light=True)['model'] == round_calls.TEXT_MODEL
    assert round_calls.design_image_estimate('x', 'medium') < round_calls.design_image_estimate('x', 'high') / 3


def test_a_look_with_several_pictures_marks_its_leading_picture_for_the_cache(context, anthropic_transport):
    """The eye's looks lead with the same picked picture: it is marked for the prompt cache; a one-picture call is not
    (a write nobody reads back is a surcharge)."""
    bodies = []
    def transport(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=sdk_reply())
    context.text_client = anthropic_transport(transport)
    context.root.mkdir(parents=True)
    picture = context.root / 'picture.png'
    Image.new('RGB', (64, 64), 'white').save(picture)
    context.text_call('eye/header/1', 'Look.', context.root / 'eye.json',
                      images=[('The picked picture', picture), ('This face', picture)], ceiling=1)
    RoundContext(context.round, context.job, text_client=context.text_client).text_call(
        'eye/cap/1', 'Look.', context.root / 'eye-cap.json', images=[('The picked picture', picture)], ceiling=1)
    first, single = bodies[0]['messages'][0]['content'], bodies[1]['messages'][0]['content']
    assert first[1]['type'] == 'image' and first[1]['cache_control'] == {'type': 'ephemeral'}
    assert 'cache_control' not in first[3] and all('cache_control' not in block for block in single)
