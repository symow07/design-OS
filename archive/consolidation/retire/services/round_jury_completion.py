"""Complete omitted jury comparisons without replacing any paid vote or picture."""
import hashlib
import json
from pathlib import Path

from PIL import Image

from . import rank_round, spend_reservation
from .round_calls import parse_response_text
from .round_calls import _text_settings, sha
from .round_flow import write_json

COMPLETION_ROUNDS = 3
PAIRS_PER_COMPLETION = 10


def _read(path):
    return json.loads(path.read_text())


def _identity(ctx, operation, prompt, images):
    inputs = []
    for caption, source in images:
        path = Path(source).resolve()
        if not path.is_relative_to(ctx.root.resolve()):
            raise ValueError('Jury pictures must belong to this round')
        with Image.open(path) as image:
            size = list(image.size)
        inputs.append({'path': str(path), 'sha256': sha(path), 'px': size,
                       'sent_unchanged': True, 'caption': caption})
    return {**_text_settings(operation, 16384), 'prompt': prompt, 'images': inputs}


def _partial(payload, batch, note_ids):
    """Missing entries may be completed; invalid or unrequested entries may not."""
    if not isinstance(payload, dict):
        raise ValueError('The jury reply must be an object')
    rows, notes = payload.get('pairs'), payload.get('ideas')
    expected = {frozenset(pair) for pair in batch}
    if not isinstance(rows, list):
        raise ValueError('The jury comparisons must be a list')
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Each jury comparison must be an object')
        pair = row.get('pair')
        if (not isinstance(pair, list) or len(pair) != 2 or
                any(not isinstance(key, str) for key in pair) or frozenset(pair) not in expected):
            raise ValueError('The jury returned an unrequested or malformed pair')
    rank_round.validate_pairs(rows, [row['pair'] for row in rows])
    if (not isinstance(notes, dict) or not set(notes).issubset(note_ids) or
            any(not isinstance(line, str) or not line.strip() or '\n' in line or '\r' in line
                for line in notes.values())):
        raise ValueError('The jury must describe each requested idea in one plain line')
    return rows, notes


def _sources(destination):
    paths = [destination, destination.with_suffix('.request.json'), destination.with_suffix('.billing.json')]
    paths.extend(sorted(destination.parent.glob(destination.stem + '.response-*.json')))
    return {path.name: sha(path) for path in paths if path.exists()}


def _pin(path, proof):
    if path.exists():
        if _read(path) != proof:
            raise ValueError('The retained jury comparison or its inputs changed; no repurchase')
    else:
        write_json(path, proof)


def _legacy_reply(ctx, operation, identity, destination, prior):
    """Intercept the old Missing pairs rejection before normal Retry archives it."""
    request = _read(destination.with_suffix('.request.json'))
    if ctx.job is None or ctx.job.attempts <= request['app_attempt']:
        raise ValueError('The saved jury reply needs the owner’s app Retry before completion')
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if (request['request_sha256'] != digest or prior['request_sha256'] != digest or
            any(request[key] != value for key, value in identity.items()) or
            prior['reservation_id'] != request['reservation_id'] or
            prior['billing_state'] != 'usage_recorded' or prior['stop_reason'] != 'end_turn'):
        raise ValueError('The saved jury request or paid result changed; no repurchase')
    with spend_reservation._connect() as db:
        reservation = db.execute('SELECT provider,model,operation,request_hash,state FROM calls WHERE id=?',
                                 (request['reservation_id'],)).fetchone()
    expected = ('anthropic', identity['model'], ctx.prefix + operation, digest, 'usage_recorded')
    if reservation is None or tuple(reservation) != expected:
        raise ValueError('The saved jury payment does not match this round; no repurchase')
    attempts = prior['attempts']
    if attempts not in (1, 2) or request['started_attempts'] != list(range(attempts)):
        raise ValueError('The saved jury response history is incomplete; no repurchase')
    raw = _read(destination.with_suffix(f'.response-{attempts - 1}.json'))
    text = ''.join(block['text'] for block in raw['content'] if block['type'] == 'text')
    if raw['stop_reason'] != 'end_turn' or parse_response_text(text) != prior['payload']:
        raise ValueError('The saved jury payload differs from its provider reply; no repurchase')
    return prior


def _fragment(ctx, operation, prompt, destination, images, batch, note_ids):
    identity = _identity(ctx, operation, prompt, images)
    receipt = destination.with_suffix('.retained.json')
    proof = {'schema': 'retained_jury_reply/1', 'operation': operation,
             'identity': identity, 'pairs': batch, 'note_ids': note_ids,
             'sources': _sources(destination)}
    # Check the pin before any cached-call journal reconciliation or validation.
    if receipt.exists() and _read(receipt) != proof:
        raise ValueError('The retained jury comparison or its inputs changed; no repurchase')
    prior = _read(destination) if destination.exists() else None
    legacy = (prior is not None and prior['status'] == 'validation_failed' and
              prior.get('validation_error') == 'Missing pairs')
    if legacy:
        call = _legacy_reply(ctx, operation, identity, destination, prior)
    else:
        call = ctx.text_call(operation, prompt, destination, images=images, max_tokens=16384, ceiling=2.0)
    try:
        rows, notes = _partial(call['payload'], batch, note_ids)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
        if not legacy:
            ctx.reject_result(destination, str(exc))
        raise
    proof['sources'] = _sources(destination)
    _pin(receipt, proof)
    return rows, notes


def _allow_round(ctx, destination, number):
    """A failed completion window can advance only on a newer owner app Retry."""
    path = destination.with_suffix('.completion-plan.json')
    job = getattr(ctx, 'job', None)
    attempt = job.attempts if job is not None else 0
    source = sha(destination.with_suffix('.retained.json'))
    if path.exists():
        plan = _read(path)
        if plan['source_receipt_sha256'] != source or not plan['windows']:
            raise ValueError('The jury completion plan changed')
        previous_attempt = -1
        for index, window in enumerate(plan['windows']):
            if (window['first_round'] != index * COMPLETION_ROUNDS + 1 or
                    window['last_round'] != (index + 1) * COMPLETION_ROUNDS or
                    window['app_attempt'] <= previous_attempt):
                raise ValueError('The jury completion retry history changed')
            previous_attempt = window['app_attempt']
        if attempt < previous_attempt:
            raise ValueError('An older worker cannot resume a newer jury Retry')
    else:
        plan = {'schema': 'jury_completion_plan/1', 'source_receipt_sha256': source,
                'windows': [{'app_attempt': attempt, 'first_round': 1, 'last_round': COMPLETION_ROUNDS}]}
        write_json(path, plan)
    last = plan['windows'][-1]
    if number > last['last_round']:
        exhausted_path = destination.with_suffix(f'.exhausted-{last["last_round"]}.json')
        if exhausted_path.exists():
            exhausted = _read(exhausted_path)
            if (exhausted['source_receipt_sha256'] != source or exhausted['window'] != last or
                    exhausted['app_attempt'] < last['app_attempt']):
                raise ValueError('The saved jury completion stop changed')
        else:
            exhausted = {'schema': 'jury_completion_exhaustion/1', 'source_receipt_sha256': source,
                         'window': last, 'app_attempt': attempt}
            write_json(exhausted_path, exhausted)
        if attempt <= exhausted['app_attempt'] or number != last['last_round'] + 1:
            raise ValueError('The jury still omits requested entries after three completion rounds; owner app Retry required')
        plan['windows'].append({'app_attempt': attempt, 'first_round': number,
                                'last_round': number + COMPLETION_ROUNDS - 1})
        write_json(path, plan)


def complete_batch(ctx, operation, prompt, destination, *, images, batch, shown):
    """At most three missing-only rounds per owner Retry, ten pairs per request.

    Each round freezes its chunks from prior accepted fragments. Replaying the
    stage reconstructs the same requests; text_call enforces one new request per
    worker delivery, budget reservations, and the existing truncation retry.
    """
    rows, notes = _fragment(ctx, operation, prompt, destination, images, batch, shown)
    rows, notes = list(rows), dict(notes)
    fragments = [destination]
    image_map = dict(images)
    context = prompt.split('\nSHOWN: ', 1)[0]
    round_number = 0
    while True:
        seen = {frozenset(row['pair']) for row in rows}
        missing = [pair for pair in batch if frozenset(pair) not in seen]
        missing_notes = [key for key in shown if key not in notes]
        if not missing and not missing_notes:
            break
        round_number += 1
        _allow_round(ctx, destination, round_number)
        chunks = [missing[start:start + PAIRS_PER_COMPLETION]
                  for start in range(0, len(missing), PAIRS_PER_COMPLETION)]
        if not chunks:
            chunks = [[]]
        for chunk_number, chunk in enumerate(chunks, 1):
            note_ids = missing_notes if chunk_number == 1 else []
            visible = [key for key in shown if key in note_ids or any(key in pair for pair in chunk)]
            supplement_prompt = (context + '\nComplete only the entries listed below. '
                'This is a continuation of the same jury batch. Earlier votes are retained. '
                'Return only PAIRS below and idea descriptions only for NOTE_IDS below '
                '(an empty NOTE_IDS means return an empty ideas object). Do not repeat other comparisons. '
                'Apply the same judging question independently to these pictures.\nSHOWN: ' + json.dumps(visible) +
                '\nNOTE_IDS: ' + json.dumps(note_ids) + '\nPAIRS: ' + json.dumps(chunk))
            suffix = f'completion-{round_number}-{chunk_number}'
            path = destination.with_name(destination.stem + '.' + suffix + '.json')
            additional, descriptions = _fragment(ctx, operation + '/' + suffix, supplement_prompt, path,
                [(key, image_map[key]) for key in visible], chunk, note_ids)
            rows.extend(additional)
            notes.update(descriptions)
            fragments.append(path)
    rank_round.validate_pairs(rows, batch)
    if set(notes) != set(shown):
        raise ValueError('The jury still omits idea descriptions after bounded completion')
    payload = {'pairs': rows, 'ideas': notes}
    _pin(destination.with_suffix('.completed.json'), {
        'schema': 'completed_jury_batch/1', 'operation': operation, 'payload': payload,
        'fragments': {path.name: sha(path.with_suffix('.retained.json')) for path in fragments}})
    return payload
