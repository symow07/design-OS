"""Round paid boundary: saved replies, one reservation per delivery, bounded retries."""
from __future__ import annotations

import base64
import binascii
from contextlib import ExitStack
from datetime import datetime
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
import sys
import time
from zoneinfo import ZoneInfo

from django.conf import settings
from PIL import Image, UnidentifiedImageError
import numpy as np
import requests

from . import spend_reservation as spend
from .pipeline_errors import ImageDownloadError
from .round_flow import YieldRound, append_json, commit_artifacts, round_root, write_json

TEXT_MODEL = 'claude-opus-5-5'
IMAGE_MODEL = 'gpt-image-2'
# The owner's ruling of 2026-10-29 ("$2 per design"): one design round, brief to Make my files, at most $2.00 all in;
# the cuts, in the owner's order: no paid retry of a reply our own check refused; boards and design sketches at medium,
# only the final faces at high; the reading and the research on the cheaper model; the repeated picture cached.
ROUND_CAP_USD = 2.00
LIGHT_TEXT_MODEL = 'claude-sonnet-5-5'
LIGHT_KINDS = {'research', 'reading', 'readings', 'blind', 'locate'}
SKETCH_QUALITY = 'medium'
#: output tokens reserved for one 1536x1024 picture by quality: high 5,488 measured (8,192 reserved), medium 1,568
#: published for the size (2,048 reserved); the reply's own usage settles every call
IMAGE_OUTPUT_RESERVE = {'high': 8192, 'medium': 2048}
TEXT_TOKEN_FLOORS = {'low': 8192, 'medium': 16384}
READING_LENGTH_CORRECTION = (
    'The reading exceeded ten words. Re-read the same object and return the same JSON fields, '
    'with idea_in_ten_words in exactly ten words. Describe the visible idea, with its proof '
    'and preservation fragment. Return JSON only.')


class StreamIncomplete(Exception):
    """A streamed image edit that ended with no completed image: its outcome is unknown, as a dropped connection's."""


#: an image edit streams partial pictures so that bytes keep arriving through a tunnel that cuts a silent connection at
#: about 200 s (round 3, 2026-10-28: two edits cut at 205–206 s; every edit that finished took 70–114 s; BREAKS.md 19)
STREAM_PARTIAL_IMAGES = 2


def streamed_edit(client, log_path, **kwargs):
    """One streamed images.edit: every event logged with its seconds since the start (its type, partial index and
    size), and the reply rebuilt in the non-streamed shape (``data[0].b64_json`` and the completed event's ``usage``).
    A stream with no completed image raises StreamIncomplete; a partial picture is never the reply."""
    import time
    start, log, completed = time.monotonic(), [], None
    try:
        for event in client.images.edit(stream=True, partial_images=STREAM_PARTIAL_IMAGES, **kwargs):
            row = spend._plain(event)
            log.append({'type': row.get('type'), 'partial_image_index': row.get('partial_image_index'),
                        'b64_chars': len(row.get('b64_json') or ''), 'seconds': round(time.monotonic() - start, 1)})
            if row.get('type') == 'image_edit.completed':
                completed = row
    finally:
        write_json(log_path, {'events': log, 'seconds': round(time.monotonic() - start, 1),
                              'completed': completed is not None})
    if completed is None:
        raise StreamIncomplete('The stream ended with no completed image after %.0f s' % (time.monotonic() - start))
    return {'data': [{'b64_json': completed['b64_json']}], 'usage': completed.get('usage'),
            'stream': {'partial_images': STREAM_PARTIAL_IMAGES, 'events': len(log)}}


#: stamped on a round made under the owner's $2 ruling (round_flow.create_round: artifacts['cost_rules'])
COST_RULES = 'two-dollars/2026-10-29'


def under_cap_ruling(record):
    """A round made under the owner's $2 ruling (2026-10-29), as its record says: its reading and research run on the
    lighter model and its sketches at medium. A round made before keeps the settings its saved calls were made with, so
    a saved reply still matches its request."""
    return isinstance(record.artifacts, dict) and record.artifacts.get('cost_rules') == COST_RULES


def _text_settings(operation, max_tokens, light=False):
    """Opus 5.5 requires adaptive thinking; leave room beyond structured JSON.

    Effort guides thinking, not a hard thinking budget. The total-token floor
    and the single retry of an unreadable reply (cut at max_tokens, or ended
    with no parseable JSON) protect the structured response; a second
    unreadable reply is retained and never becomes a verdict.
    """
    kind = operation.split('/', 1)[0].split('-', 1)[0]
    effort = 'low' if kind in {'eye', 'check', 'checks', 'blind', 'reading', 'readings'} else 'medium'
    model = LIGHT_TEXT_MODEL if light and kind in LIGHT_KINDS else TEXT_MODEL
    return {'model': model, 'thinking': {'type': 'adaptive'},
            'output_config': {'effort': effort}, 'max_tokens': max(max_tokens, TEXT_TOKEN_FLOORS[effort])}


def _token_split(raw):
    """Keep provider totals authoritative; never count visible thinking text.

    output_tokens includes thinking. Anthropic calls subtraction of reported
    thinking tokens an estimate of non-reasoning output. Older replies may
    omit the breakdown; retain that absence explicitly, including on retries.
    """
    usage = raw.get('usage')
    total = usage.get('output_tokens') if isinstance(usage, dict) else None
    details = usage.get('output_tokens_details') if isinstance(usage, dict) else None
    thinking = details.get('thinking_tokens') if isinstance(details, dict) else None
    valid_total = isinstance(total, int) and not isinstance(total, bool) and total >= 0
    valid = valid_total and isinstance(thinking, int) and not isinstance(thinking, bool) and 0 <= thinking <= total
    return {'output_tokens': total if valid_total else None,
            'thinking_tokens': thinking if valid else None,
            'non_thinking_output_tokens_estimate': total - thinking if valid else None,
            'split_status': 'reported' if valid else 'unavailable'}


def _text_accounting(replies):
    splits = [_token_split(raw) for raw in replies]
    usage = _sum_usage(replies)
    reported = all(split['split_status'] == 'reported' for split in splits)
    aggregate = {'output_tokens': sum(split['output_tokens'] for split in splits) if all(split['output_tokens'] is not None for split in splits) else None,
                 'thinking_tokens': sum(split['thinking_tokens'] for split in splits) if reported else None,
                 'non_thinking_output_tokens_estimate': sum(split['non_thinking_output_tokens_estimate'] for split in splits) if reported else None,
                 'split_status': 'reported' if reported else 'unavailable'}
    return {'usage': usage, 'attempts': len(replies), 'token_split': aggregate, 'attempt_token_splits': splits}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_call_limit(record):
    """The image cap of a round context that names none of its own. (The owner's one r2-gloss repair added twenty to
    it; that repair retired with the whole-object kind on 2026-10-29, archive/consolidation/retire/merged/.)"""
    return 26


def scoped_spend(record):
    prefix = f'round/{record.slug}/'
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls WHERE substr(operation,1,?)=?', (len(prefix), prefix))]
    return {'accounted_usd': sum(r['accounted'] for r in rows) / 1e6,
            'actual_usd': sum(r['accounted'] for r in rows if r['state'] == 'usage_recorded') / 1e6,
            'reserved_usd': sum(r['accounted'] for r in rows if r['state'] in ('reserved', 'billing_unresolved')) / 1e6,
            'historical_reserved_usd': sum(r['reserved'] for r in rows) / 1e6,
            'calls': len(rows), 'image_calls': sum(r['provider'] == 'openai' for r in rows),
            'budget_usd': float(record.budget_usd), 'image_attempt_limit': image_call_limit(record)}


def _cost_step(head, rest, face_labels):
    """The step a round's paid call belongs to, in the owner's words, from its operation (head/<slug>/rest)."""
    part = rest.split('/')
    if part[0] in ('image', 'checks') and len(part) > 1:
        part = part[1:]
    if head == 'round':
        again = len(part) > 1 and part[1] != 'g1'
        named = {'research': 'Research', 'boards': 'Mood boards', 'designs': 'Designs'}
        if part[0] not in named:
            return 'Ideas: ' + part[0]
        return named[part[0]] + (' (again, after “None of these”)' if again and part[0] != 'research' else '')
    if head == 'files':
        if part[0] == 'locate-picture':
            return 'Reading your picture'
        if part[0] == 'flat':
            return 'The whole die painted'
        if part[0] in ('face', 'eye', 'repair') and len(part) > 1 and not part[1].isdigit():
            return face_labels[part[1]] if part[1] in face_labels else 'Face: ' + part[1].replace('_', ' ')
        if part[0] == 'eye':
            return 'The designer\'s eye on the whole picture'
        return 'Files: ' + part[0]
    return 'An earlier files attempt (%s)' % head


def round_costs(record, face_labels):
    """Every paid call of a round, brief to Make my files, by step, from the ledger (the owner's ruling of 2026-10-29:
    each step's real cost on its page): the step's dollars as settled (a call still out counts at its hold, a lost one
    at its hold, a refused one at $0), its calls, and the round's total against its one cap."""
    token = '/%s/' % record.slug
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute(
            'SELECT operation, state, accounted FROM calls WHERE instr(operation, ?) > 0 ORDER BY started_at', (token,))]
    steps = {}
    for row in rows:
        head, rest = row['operation'].split(token, 1)
        label = _cost_step(head, rest, face_labels)
        if label not in steps:
            steps[label] = {'step': label, 'usd': 0.0, 'calls': 0, 'held_usd': 0.0, 'lost': 0, 'refused': 0}
        step = steps[label]
        step['usd'] += row['accounted'] / 1e6
        step['calls'] += 1
        if row['state'] in ('reserved', 'billing_unresolved'):
            step['held_usd'] += row['accounted'] / 1e6
        step['lost'] += row['state'] == 'outcome_unknown'
        step['refused'] += row['state'] == 'rejected_unbilled'
    total = sum(step['usd'] for step in steps.values())
    return {'steps': list(steps.values()), 'total_usd': total, 'cap_usd': float(record.budget_usd),
            'left_usd': max(float(record.budget_usd) - total, 0.0)}


def _billing(identifier):
    with spend._connect() as db:
        row = db.execute('SELECT state,accounted,reserved FROM calls WHERE id=?', (identifier,)).fetchone()
    return {'billing_state': row['state'], 'accounted_usd': row['accounted'] / 1e6,
            'cost_usd': row['accounted'] / 1e6 if row['state'] == 'usage_recorded' else None,
            'reserved_usd': row['reserved'] / 1e6}


def _sum_usage(replies):
    usage = {}
    for raw in replies:
        used = raw.get('usage')
        if not isinstance(used, dict) or not all(k in used for k in ('input_tokens', 'output_tokens')):
            return None
        if any(not isinstance(used[key], int) or isinstance(used[key], bool) or used[key] < 0
               for key in ('input_tokens', 'output_tokens')):
            return None
        for key in ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'):
            usage[key] = usage.get(key, 0) + (used.get(key) or 0)
    return usage


def retained_verdict(destination):
    """(payload, reply file) of a call saved as incomplete whose last reply in fact ended its turn with readable JSON
    (an older parser could not read it); None for a reply cut at max_tokens, or one with no readable JSON."""
    destination = Path(destination)
    prior = json.loads(destination.read_text())
    if prior.get('status') != 'incomplete' or prior.get('stop_reason') != 'end_turn' or not prior.get('attempts'):
        return None
    raw_path = destination.with_suffix(f'.response-{prior["attempts"] - 1}.json')
    if not raw_path.exists():
        return None
    raw = json.loads(raw_path.read_text())
    text = ''.join(block.get('text', '') for block in raw['content'] if block.get('type') == 'text')
    try:
        payload = parse_response_text(text)
    except (ValueError, TypeError):
        return None
    return (payload, raw_path) if raw.get('stop_reason') == 'end_turn' and payload is not None else None


class RoundContext:
    def __init__(self, record, job=None, *, text_client=None, image_client=None):
        self.round = record
        self.job = job
        self.root = round_root(record)
        self.brief = record.product_brief
        self.prefix = f'round/{record.slug}/'
        self.round_cap = float(record.budget_usd)          # the whole round's one cap, every prefix (spend.reserve)
        self.ruled = under_cap_ruling(record)
        self.text_client = text_client
        self.image_client = image_client
        self.new_calls = 0
        self.active_calls = set()
        self.forks_per_mark = 2
        self.pair_batch_size = 9

    def prepare_budget_plan(self, step):
        """Persist ordered soft cuts before work; never change a partially built fork set."""
        path = self.root / 'budget-plan.json'
        plan = json.loads(path.read_text()) if path.exists() else {
            'forks_per_mark': 2, 'pair_batch_size': 9, 'batch_sizes': {}, 'cuts': [],
            'estimates_are_not_invoices': True}
        if step in ('pairwise', 'forks', 'final_pairwise'):
            spend_state = scoped_spend(self.round)
            image_limit = image_call_limit(self.round)
            plan['image_attempt_limit'] = image_limit
            plan['budget_usd'] = float(self.round.budget_usd)
            available = float(self.round.budget_usd) - spend_state['accounted_usd']
            forks_started = any((self.root / 'developments').glob('*/*/image-call.request.json'))
            if available < 6 and plan['forks_per_mark'] == 2 and not forks_started:
                plan['forks_per_mark'] = 1
                plan['cuts'].append({'cut': 'two forks per mark to one', 'available_usd': available,
                                     'reason': 'Preserve a $6 estimated development and final-jury allowance.'})
            if step == 'forks':
                marks = self.round.marks['marks']
                def unpaid_forks(count):
                    needed = 0
                    for mark in marks:
                        for fork in ('A', 'B')[:count]:
                            saved = self.root / 'developments' / mark['id'] / fork / 'image-call.json'
                            if not saved.exists() or json.loads(saved.read_text())['status'] != 'complete':
                                needed += 1
                    return needed
                if spend_state['image_calls'] + unpaid_forks(plan['forks_per_mark']) > image_limit and plan['forks_per_mark'] == 2:
                    plan['forks_per_mark'] = 1
                    plan['cuts'].append({'cut': 'two forks per mark to one', 'image_attempts': spend_state['image_calls'],
                                         'reason': f'Rejected and uncertain image attempts count toward {image_limit}; retain any already-paid B artifact in the audit.'})
                if spend_state['image_calls'] + unpaid_forks(plan['forks_per_mark']) > image_limit:
                    write_json(path, plan)
                    from .cost_ledger import BudgetExceededError
                    raise BudgetExceededError(f'The {image_limit}-image allowance cannot fit one fork per mark; no additional call made.')
            if available < 4 and plan['forks_per_mark'] == 1 and plan['pair_batch_size'] == 9 and step not in plan['batch_sizes']:
                plan['pair_batch_size'] = 10
                plan['cuts'].append({'cut': 'pairwise batches of ten', 'available_usd': available,
                                     'reason': 'Fork count was reduced first; preserve the final pick page.'})
            if step in ('pairwise', 'final_pairwise') and step not in plan['batch_sizes']:
                plan['batch_sizes'][step] = plan['pair_batch_size']
            write_json(path, plan)
        self.forks_per_mark = plan['forks_per_mark']
        self.pair_batch_size = plan['batch_sizes'][step] if step in plan['batch_sizes'] else plan['pair_batch_size']

    def _destination(self, destination):
        path = Path(destination).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('Call output must belong to this round.')
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _input(self, path, *, logo=False):
        path = Path(path).resolve()
        if not logo and not path.is_relative_to(self.root):
            raise ValueError('Only this round\'s artifacts may enter a call.')
        with Image.open(path) as im:
            size = list(im.size)
        return {'path': str(path), 'sha256': sha(path), 'px': size, 'sent_unchanged': True}

    def _one_call(self):
        if self.new_calls >= 1:
            raise YieldRound()
        self.new_calls += 1

    def _request(self, destination, identity, *, provider, operation, estimate):
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        request_path = destination.with_suffix('.request.json')
        if destination.exists():
            prior = json.loads(destination.read_text())
            if prior['request_sha256'] == digest and prior['status'] == 'complete':
                if self._journal(destination, prior, operation, provider == 'openai'):
                    commit_artifacts(self.round, f'{operation}: recovered paid-call journal')
                return prior, None, None
            if prior['request_sha256'] == digest and prior['status'] == 'incomplete' and provider == 'anthropic':
                recovered = self._reread(destination, prior, operation)
                if recovered is not None:
                    return recovered, None, None
        if request_path.exists():
            request = json.loads(request_path.read_text())
            app_attempt = self.job.attempts if self.job is not None else 0
            failed_complete = destination.exists() and json.loads(destination.read_text())['status'] in ('incomplete', 'validation_failed')
            rejected = any(json.loads(path.read_text()).get('http_status') in spend.UNBILLED_REJECTIONS
                           for path in destination.parent.glob(destination.stem + '.error*.json'))
            if app_attempt > request['app_attempt'] and (failed_complete or rejected):
                prior = json.loads(destination.read_text()) if destination.exists() else None
                if (prior is not None and prior['status'] == 'validation_failed' and provider == 'anthropic'
                        and prior['request_sha256'] == digest and prior['payload'] is not None
                        and 'rechecked' not in prior):
                    # a paid reply our own check refused: the owner's Retry first checks the same reply again at $0 (a
                    # check fixed since passes it); only a reply refused again is bought anew on a later Retry (the
                    # owner's ruling of 2026-10-29: no paid retry on errors our own code causes)
                    request['app_attempt'] = app_attempt
                    write_json(request_path, request)
                    result = dict(prior, status='complete', rechecked={
                        'refused_for': prior['validation_error'], 'app_attempt': app_attempt, 'new_calls': 0})
                    write_json(destination, result)
                    commit_artifacts(self.round, f'{operation}: the saved reply checked again, no new call')
                    return result, None, None
                archive = destination.parent / 'call-history' / (destination.stem + '-' + request['reservation_id'])
                archive.mkdir(parents=True, exist_ok=True)
                for path in list(destination.parent.glob(destination.stem + '.*json')):
                    path.rename(archive / path.name)
                if provider == 'openai' and (destination.parent / 'raw.png').exists():
                    (destination.parent / 'raw.png').rename(archive / 'raw.png')
                return self._request(destination, identity, provider=provider, operation=operation, estimate=estimate)
            if request['request_sha256'] != digest:
                raise ValueError('A paid request cannot silently change its inputs.')
            # An unfinished attempt may have been billed. A saved reply is recoverable;
            # an absent reply is not permission to send the request twice.
            return None, request, request_path
        self._one_call()
        attempt_cap = getattr(self, 'image_attempt_cap', image_call_limit(self.round)) if provider == 'openai' else None
        identifier = spend.reserve(provider, self.prefix + operation, identity['model'], estimate, digest,
            budget_prefix=self.prefix, prefix_cap=float(self.round.budget_usd),
            round_slug=self.round.slug, round_cap=self.round_cap,
            count_prefix=self.prefix + 'image/' if attempt_cap is not None else None,
            count_cap=attempt_cap)
        request = dict(identity, request_sha256=digest, reservation_id=identifier,
                       reserved_usd=estimate, started_attempts=[], app_attempt=self.job.attempts if self.job is not None else 0)
        write_json(request_path, request)
        self.active_calls.add(identifier)
        return None, request, request_path

    def _finish(self, destination, request, record, *, operation, image=False):
        result = dict(record, request_sha256=request['request_sha256'], reservation_id=request['reservation_id'],
                      **_billing(request['reservation_id']))
        write_json(destination, result)
        if image and result['status'] == 'validation_failed':
            self._validation_journal(destination, result, result['validation_error'])
        else:
            self._journal(destination, result, operation, image)
        commit_artifacts(self.round, f'{operation}: {result["status"]}')
        return result

    def _journal(self, destination, result, operation, image):
        path = self.root / ('image-calls.jsonl' if image else 'calls.jsonl')
        if path.exists():
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            if any(row['reservation_id'] == result['reservation_id'] for row in rows):
                return False
        append_json(path, dict(result, operation=operation, payload_file=str(destination.relative_to(self.root))))
        return True

    def _validation_journal(self, destination, result, reason):
        path = self.root / 'call-validation.jsonl'
        if path.exists():
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            if any(row['reservation_id'] == result['reservation_id'] for row in rows):
                return
        append_json(path, {'reservation_id': result['reservation_id'],
                    'payload_file': str(destination.relative_to(self.root)), 'error': str(reason)})

    def _reread(self, destination, prior, operation):
        """A retained reply that ended its turn but was saved as incomplete (an older parser could not read its JSON)
        is read again, at $0, and holds its verdict. A reply cut at max_tokens is never read as one."""
        retained = retained_verdict(destination)
        if retained is None:
            return None
        payload, raw_path = retained
        result = dict(prior, status='complete', payload=payload, reread={
            'reply': raw_path.name, 'reply_sha256': sha(raw_path), 'new_calls': 0,
            'rule': 'the retained reply read again by the fence parser; it was never truncated'})
        write_json(destination, result)
        commit_artifacts(self.round, f'{operation}: verdict read again from its retained reply, no new call')
        return result

    def _unknown_outcome(self, destination, request, provider):
        """A started attempt with no saved reply: its outcome is unknown, and it is never sent twice."""
        raise ValueError('Prior provider outcome is unknown; reservation held, no repeated payment.')

    def reject_result(self, destination, reason):
        """A call-specific semantic validator can reject JSON; only an app retry can replace it."""
        destination = self._destination(destination)
        result = json.loads(destination.read_text())
        if result['status'] != 'complete':
            raise ValueError('Only a completed provider reply can fail semantic validation.')
        result['status'] = 'validation_failed'
        result['validation_error'] = str(reason)
        write_json(destination, result)
        self._validation_journal(destination, result, reason)
        commit_artifacts(self.round, 'paid reply failed semantic validation')

    def text_call(self, operation, prompt, destination, *, images=(), max_tokens=3000, ceiling=1.0):
        destination = self._destination(destination)
        content, inputs = [], []
        for caption, path in images:
            item = self._input(path)
            item['caption'] = caption
            inputs.append(item)
            content.extend([{'type': 'text', 'text': caption}, {'type': 'image', 'source': {
                'type': 'base64', 'media_type': 'image/png', 'data': base64.b64encode(Path(path).read_bytes()).decode()}}])
        if len(images) > 1:
            # the leading picture repeats across a build's looks (the eye's picked picture): read from the cache
            content[1]['cache_control'] = {'type': 'ephemeral'}
        content.append({'type': 'text', 'text': prompt})
        call_settings = _text_settings(operation, max_tokens, light=self.ruled)
        request_args = {**call_settings,
                        'messages': [{'role': 'user', 'content': content}]}
        if len(json.dumps(request_args).encode()) > 31_000_000:
            raise ValueError('Full-size image request exceeds the 31 MB boundary before payment.')
        identity = {**call_settings, 'prompt': prompt, 'images': inputs}
        from .cost_ledger import claude_cost_usd
        is_reading = operation.split('/', 1)[0] in ('blind', 'reading', 'readings')
        attempt_limit = 2
        text_tokens = (len(prompt.encode()) + sum(len(caption.encode()) for caption, _ in images)) / 2 + 500
        if is_reading:
            # One length re-ask and one unreadable-reply retry share one reservation.
            attempt_limit = 3
            text_tokens += len(READING_LENGTH_CORRECTION.encode()) / 2
        image_tokens = sum(item['px'][0] * item['px'][1] / 600 + 500 for item in inputs)
        estimate = max(.001, float(claude_cost_usd(call_settings['model'], text_tokens + image_tokens, call_settings['max_tokens'])) * attempt_limit * 1.1)
        if estimate > ceiling:
            raise ValueError(f'{attempt_limit}-attempt upper estimate ${estimate:.4f} exceeds ${ceiling:.2f}.')
        cached, request, request_path = self._request(destination, identity, provider='anthropic', operation=operation, estimate=estimate)
        if cached is not None:
            return cached
        raw_replies = []
        unreadable_retried = length_reasked = False
        attempt_prompt = prompt
        for attempt in range(attempt_limit):
            raw_path = destination.with_suffix(f'.response-{attempt}.json')
            if is_reading:
                request_args['messages'][0]['content'] = content[:-1] + [{'type': 'text', 'text': attempt_prompt}]
                attempt_path = destination.with_suffix(f'.attempt-{attempt}.request.json')
                attempt_record = {**call_settings, 'prompt': attempt_prompt, 'images': inputs,
                    'request_sha256': request['request_sha256'],
                    'canonical_body_sha256': hashlib.sha256(json.dumps(request_args, sort_keys=True,
                        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()}
                if attempt_path.exists() and json.loads(attempt_path.read_text()) != attempt_record:
                    raise ValueError('A saved reading attempt cannot silently change its inputs.')
                write_json(attempt_path, attempt_record)
            if raw_path.exists():
                raw = json.loads(raw_path.read_text())
            else:
                if is_reading and request['reserved_usd'] < estimate:
                    raise ValueError('Saved reading reservation does not cover the bounded re-ask; no provider call made.')
                if attempt in request['started_attempts']:
                    self._unknown_outcome(destination, request, 'anthropic')
                if request['reservation_id'] not in self.active_calls:
                    self._one_call()
                    self.active_calls.add(request['reservation_id'])
                request['started_attempts'].append(attempt)
                write_json(request_path, request)
                if self.text_client is None:
                    if 'pytest' in sys.modules:
                        raise RuntimeError('Round fixtures require an explicit fake text client.')
                    import anthropic
                    self.text_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=0, timeout=300)
                try:
                    response = self.text_client.messages.create(**request_args)
                except Exception as exc:
                    status = spend.rejected_status(exc)
                    if status is not None and not raw_replies:
                        spend.release_rejected(request['reservation_id'], status, exc)
                    elif status is not None:
                        billing_path = destination.with_suffix('.billing.json')
                        known = {**_text_accounting(raw_replies), 'unbilled_retry_http_status': status}
                        write_json(billing_path, known)
                        spend.settle(request['reservation_id'], known, billing_path, provider='anthropic',
                                     model=call_settings['model'])
                    write_json(destination.with_suffix(f'.error-{attempt}.json'),
                               {'error_type': type(exc).__name__, 'http_status': status, 'reservation_id': request['reservation_id']})
                    commit_artifacts(self.round, f'{operation}: provider failure retained')
                    raise
                raw = spend._plain(response)
                write_json(raw_path, raw)
                commit_artifacts(self.round, f'{operation}: raw reply {attempt + 1} saved')
            raw_replies.append(raw)
            # Persist each attempt's split before another provider attempt can start.
            write_json(destination.with_suffix('.billing.json'), _text_accounting(raw_replies))
            text = ''.join(block.get('text', '') for block in raw['content'] if block.get('type') == 'text')
            try:
                payload = parse_response_text(text)
            except (ValueError, TypeError):
                payload = None
            word_count = 0
            if is_reading and isinstance(payload, dict) and isinstance(payload.get('idea_in_ten_words'), str):
                word_count = len(payload['idea_in_ten_words'].split())
            # A reply cut at max_tokens, or ended with no parseable JSON, holds no verdict: the same request is
            # asked once more within the same reservation. A readable reply is never re-asked.
            unreadable = raw.get('stop_reason') == 'max_tokens' or (raw.get('stop_reason') == 'end_turn' and payload is None)
            if unreadable and not unreadable_retried:
                unreadable_retried = True
                continue
            if raw.get('stop_reason') == 'end_turn' and word_count > 10 and not length_reasked:
                length_reasked = True
                attempt_prompt = prompt + '\n' + READING_LENGTH_CORRECTION
                continue
            break
        aggregate = _text_accounting(raw_replies)
        aggregate_path = destination.with_suffix('.billing.json')
        write_json(aggregate_path, aggregate)
        spend.settle(request['reservation_id'], aggregate, aggregate_path, provider='anthropic', model=call_settings['model'])
        final = raw_replies[-1]
        status = 'complete' if final.get('stop_reason') == 'end_turn' and payload is not None else 'incomplete'
        if is_reading:
            aggregate['reading_length'] = {'word_count': word_count, 'over_length': word_count > 10,
                                           'reasked': length_reasked}
        result = self._finish(destination, request, {'status': status, 'payload': payload,
            'images': inputs, **call_settings, **aggregate,
            'stop_reason': final.get('stop_reason')}, operation=operation)
        if status != 'complete':
            raise ValueError('Incomplete structured reply retained; it is not a verdict.')
        return result

    def image_call(self, operation, prompt, destination, *, target, mask, logo, sheet=None):
        destination = self._destination(Path(destination) / 'image-call.json')
        target, mask, logo = Path(target).resolve(), Path(mask).resolve(), Path(logo).resolve()
        approved, approved_sha = APPROVED_LOGO
        if logo != Path(approved).resolve() or sha(logo) != approved_sha:
            raise ValueError('Only the pinned approved logo is an image input.')
        if settings.IMAGE_MODEL != IMAGE_MODEL or competitor_in(prompt):
            raise ValueError('Round image model or prompt is outside the allowed boundary.')
        base_sheet = self.root / 'sheet.png'
        base_mask = self.root / 'sheet-mask.png'
        is_fork = target != base_sheet
        paths = [target, logo]
        if is_fork:
            if not target.is_relative_to(self.root / 'sketches') or target.name != 'picture.png' or sheet is None or Path(sheet).resolve() != base_sheet:
                raise ValueError('A fork uses its own round sketch, mask, logo and sheet only.')
            paths.append(base_sheet)
        elif sheet is not None or mask != base_mask:
            raise ValueError('A sketch uses only its sheet, sheet mask and logo.')
        inputs = [self._input(path, logo=path == logo) for path in paths]
        mask_input = self._input(mask)
        if any(item['px'] != [1536, 1024] for item in inputs if Path(item['path']) != logo) or mask_input['px'] != [1536, 1024]:
            raise ValueError('Round image input dimensions changed.')
        with Image.open(base_mask) as im:
            base = np.asarray(im.convert('RGBA'))[..., 3]
        with Image.open(mask) as im:
            effective = np.asarray(im.convert('RGBA'))[..., 3]
        if np.any((effective == 0) & (base != 0)) or (is_fork and not np.any((base == 0) & (effective != 0))):
            raise ValueError('The mask must protect construction and a fork\'s selected fragment.')
        identity = {'model': IMAGE_MODEL, 'quality': 'high', 'size': '1536x1024', 'prompt': prompt,
                    'inputs': inputs, 'mask': mask_input}
        op = operation if operation.startswith('image/') else 'image/' + operation
        cached, request, request_path = self._request(destination, identity, provider='openai', operation=op, estimate=1.0)
        if cached is not None:
            raw_image = destination.parent / 'raw.png'
            if not raw_image.exists() or sha(raw_image) != cached['output_sha256']:
                raise ValueError('Saved paid image changed; no repurchase.')
            return cached
        raw_path = destination.with_suffix('.response.json')
        if raw_path.exists():
            raw = json.loads(raw_path.read_text())
        else:
            if request['started_attempts']:
                raise ValueError('Prior image outcome is unknown; reservation held, no repeated payment.')
            if request['reservation_id'] not in self.active_calls:
                self._one_call()
                self.active_calls.add(request['reservation_id'])
            request['started_attempts'] = [0]
            write_json(request_path, request)
            if self.image_client is None:
                if 'pytest' in sys.modules:
                    raise RuntimeError('Round fixtures require an explicit fake image client.')
                from openai import OpenAI
                self.image_client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
            try:
                with ExitStack() as stack:
                    opened = [stack.enter_context(path.open('rb')) for path in paths]
                    opened_mask = stack.enter_context(mask.open('rb'))
                    response = self.image_client.images.edit(model=IMAGE_MODEL, quality='high', size='1536x1024',
                        prompt=prompt, n=1, image=opened, mask=opened_mask)
            except Exception as exc:
                status = spend.rejected_status(exc)
                if status is not None:
                    spend.release_rejected(request['reservation_id'], status, exc)
                write_json(destination.with_suffix('.error.json'), {'error_type': type(exc).__name__, 'http_status': status,
                           'reservation_id': request['reservation_id']})
                commit_artifacts(self.round, f'{op}: provider failure retained')
                raise
            raw = spend._plain(response)
            write_json(raw_path, raw)
            commit_artifacts(self.round, f'{op}: raw image reply saved')
        spend.settle(request['reservation_id'], raw, raw_path, provider='openai', model=IMAGE_MODEL)
        def reject_image(reason):
            self._finish(destination, request, dict(identity, status='validation_failed',
                         usage=raw.get('usage'), validation_error=reason), operation=op, image=True)
            raise ValueError(reason)

        data = raw.get('data')
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            reject_image('Exactly one paid image is required; reply retained.')
        item = data[0]
        if item.get('b64_json'):
            try:
                image_bytes = base64.b64decode(item['b64_json'], validate=True)
            except (binascii.Error, ValueError, TypeError):
                reject_image('Paid image bytes are not valid base64; reply retained.')
        elif item.get('url'):
            # A failed download can recover from this same saved response, without repurchase.
            image_bytes = download_image_bytes(item['url'])
        else:
            reject_image('Paid image bytes missing; reply retained.')
        try:
            with Image.open(BytesIO(image_bytes)) as im:
                im.load()
                dimensions = im.size
        except (UnidentifiedImageError, OSError, ValueError, TypeError):
            reject_image('Paid image bytes cannot be decoded; reply retained.')
        if dimensions != (1536, 1024):
            reject_image('Provider image has the wrong dimensions; paid reply retained.')
        # File errors are local recovery failures, not permission to buy a replacement image.
        raw_image = destination.parent / 'raw.png'
        raw_image.write_bytes(image_bytes)
        return self._finish(destination, request, dict(identity, status='complete', output_sha256=sha(raw_image),
                            usage=raw.get('usage')), operation=op, image=True)


# --- a reply read: one JSON fence or plain JSON (from round_balm_calls, 2026-10-28) -----------------------------------

def parse_response_text(text):
    """Accept one explicit JSON fence, with notes before or after it (kept in the raw reply); or the reply as JSON."""
    clean = text.strip()
    if '```json' in clean:
        parts = clean.split('```')
        if len(parts) != 3 or not parts[1].startswith('json\n'):
            raise ValueError('Ambiguous or incomplete JSON fence')
        return json.loads(parts[1][4:].strip())
    return json.loads(clean)


# --- a picture downloaded (from pipeline.agents.image_producer, 2026-10-28) -------------------------------------------

# Local-download policy (Milestone 8.6 / audit H1): provider URLs expire in
# ~1h, so the local copy is the ONLY durable artifact. Download with retry +
# backoff, verify it's a real image, and never fail silently.
DOWNLOAD_ATTEMPTS = 3


DOWNLOAD_TIMEOUT = 30   # seconds per attempt


DOWNLOAD_BACKOFF = 2    # seconds, multiplied by the attempt number


def download_image_bytes(url, attempts=DOWNLOAD_ATTEMPTS, timeout=DOWNLOAD_TIMEOUT):
    """Fetch image bytes with retry/backoff; verify content-type and non-zero
    size. Raises ImageDownloadError after the final failed attempt."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=timeout)
            content_type = response.headers.get('Content-Type', '') or ''
            if (response.status_code == 200
                    and content_type.startswith('image/')
                    and response.content):
                return response.content
            last_error = (
                f'status={response.status_code} content-type={content_type!r} '
                f'bytes={len(response.content or b"")}'
            )
        except requests.RequestException as e:
            last_error = str(e)
        if attempt < attempts:
            time.sleep(DOWNLOAD_BACKOFF * attempt)
    raise ImageDownloadError(last_error or 'unknown download error')


# --- the image guard: every image call's inputs and words (from image_guard, 2026-10-28) ------------------------------
# The guard every image call passes BEFORE payment (D-D8-2, D-D8-7, D-D8-10; re-rooted for Day 9, D-D9-1), and the call log §8 asserts from.
#
# Refused, by name, before a byte is sent:
# - an input whose bytes are a design the system made to date (D-D8-2: every concept, drawing, lid, surface, mockup and
#   paid picture) — by sha256 against a denylist hashed from where those live, however the file was renamed or copied;
# - an input that is a web or competitor picture (D-D8-7: research only) — anything under the web quarantine, by path
#   and by sha256;
# - an input from outside the roots a Day 8 call may draw on (our engine's renders, the approved mark, house-design
#   crops made for a named trait with the client's name masked, the house library's materials and previews);
# - a prompt that names a competitor brand (D-D8-7);
# - a provider other than OpenAI or a model other than ``settings.IMAGE_MODEL`` (D-D8-10).
# Every call — allowed or refused — is one line of ``docs/audit/day-9/image-calls.jsonl`` (Day 8's log is closed): the operation, the provider
# and model, each input's role, path and sha256, the prompt's sha256 and words, the quality and size, and the outcome.

ROOT = Path(settings.BASE_DIR)                      # bbrose_design_os/
REPO = ROOT.parent
# [Day 9] each day's calls are its own log; Day 8's log (docs/audit/day-8/image-calls.jsonl) is closed and kept
# [Day 10] and Day 9's (docs/audit/day-9/image-calls.jsonl) is closed and kept
# [Day 11] and Day 10's (docs/audit/day-10/image-calls.jsonl) is closed and kept
# [Day 12] and Day 11's (docs/audit/day-11/image-calls.jsonl) is closed and kept
CALL_LOG = REPO / 'docs' / 'audit' / 'day-12' / 'image-calls.jsonl'
DENYLIST_CACHE = ROOT / 'var' / 'day8' / 'image-guard-denylist.json'
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff', '.bmp'}

#: D-D8-2 — where the designs the system made to date live (each image file hashed into the denylist)
REJECTED_ROOTS = (
    ROOT / 'media' / 'generated', ROOT / 'media' / 'concepts', ROOT / 'media' / 'concept_thumbs',
    ROOT / 'media' / 'drawing_views', ROOT / 'media' / 'rejected', ROOT / 'media' / 'palette',
    ROOT / 'media' / 'containers', ROOT / 'media' / 'container_handoff', ROOT / 'media' / 'task_refs',
    ROOT / 'var' / 'rescue_spend' / 'responses', ROOT / 'docs' / 'roadmap' / 'palt_m7',
    ROOT / 'apps' / 'pipeline' / 'tests' / 'fixtures_124',
    REPO / 'docs' / 'audit' / 'day-4', REPO / 'docs' / 'audit' / 'day-5', REPO / 'docs' / 'audit' / 'day-6',
    REPO / 'docs' / 'audit' / 'day-7', REPO / 'docs' / 'audit' / 'codex-2026-10-18',
    # [Day 9, D-D9-1] Day 8's directions are closed and its builds are rejected designs (UNCHANGED: "no rejected design
    # (Day 8's builds included) ... ever goes to an image model"): every picture under Day 8's audit folder
    REPO / 'docs' / 'audit' / 'day-8',
    # [Day 10, D-D10-4] "never a web picture or a rejected design": every Day 9 picture but the owner's pick (APPROVED_PICK)
    REPO / 'docs' / 'audit' / 'day-9',
)
#: D-D8-7 — web and competitor pictures: research only, never an input
WEB_ROOTS = (ROOT / 'media' / 'web_quarantine',)
#: the roots a Day 11 image call may draw on (the owner's picks by their path and sha256: APPROVED_PICKS); Day 10's work
#: (Golden Hour, test one) is not among them — no Golden Hour picture reaches a Ẓilāl call (D-D11 §8)
#: [Day 12] the roots moved on to Day 12's own work: its style reference is the lid master re-traced by D-D12-9's reader
#: (docs/audit/day-12/zilal/lid), its sheets drawn there; Day 11's files are not today's (as Day 10's were not)
ALLOWED_ROOTS = (
    REPO / 'docs' / 'audit' / 'day-12',                      # [Day 12] today's own work
    REPO / 'materials',                                       # the house library (D-D7-1) — material, texture, layer
    ROOT / 'var' / 'design_intelligence' / 'previews' / 'materials',   # its Day 7 previews, by hash
    REPO / 'var' / 'design_intelligence' / 'previews' / 'materials',
)
#: [Day 9 §3] "Inputs: the approved logo only (no engine renders)": the approval's own source raster, one exact file, its
#: bytes pinned — allowed by path AND sha256 (docs/brand/mark/approval.json, source_png)
APPROVED_LOGO = (ROOT / 'media' / 'brand' / 'bbrose-logo.png', 'e107a0989d9cedf52980166cca0d368cdb4f1059ed8aff0c51badac7cee58c18')
#: [Day 10, D-D10-4] "every image call carries the pick as its style reference": the owner's pick, one exact file, its bytes
#: pinned — allowed by path AND sha256 (CURRENT_DECISIONS.md, Day 10), though it sits under Day 9's rejected root
APPROVED_PICK = (REPO / 'docs' / 'audit' / 'day-9' / 'sketches' / 'A-2.3' / 'lid.png',
                 '4293fe8b20a8c39e9776e433267fd6b36bfa89ca72f4381710f32a639f797de8')
#: [Day 11, D-D11-1] the pick changes to Ẓilāl: the sketch B-1.3, one exact file, its bytes pinned (CURRENT_DECISIONS.md,
#: Day 11); Golden Hour's pick stays approved for its own five fixes (D-D11-5: its new tray picture)
APPROVED_ZILAL = (REPO / 'docs' / 'audit' / 'day-9' / 'sketches' / 'B-1.3' / 'lid.png',
                  '090a543ce1b2ead1b4904fb555961ec8baa6848bc6e725438f3a77801584198d')
APPROVED_PICKS = (APPROVED_PICK, APPROVED_ZILAL)
#: D-D8-7 — the house's own production designs: an input only as a crop of a named trait, the client's name masked
HOUSE_DESIGN_ROOTS = (REPO / 'materials' / 'house-designs', REPO / 'docs' / 'brand' / 'house_references' / 'files')
#: D-D8-7 — no competitor brand name in an image prompt (the board's brand sites, the palette leaders, the prestige
#: houses the market board studied, and the Middle-East houses); matched as whole words, any case
COMPETITORS = (
    'Rare Beauty', 'Fenty', 'Glossier', 'Rhode', 'Huda Beauty', 'Huda', 'Charlotte Tilbury', 'Summer Fridays', 'Kayali',
    'Merit', 'Tower 28', 'ILIA', 'Byredo', 'Laneige', 'Saie', 'Haus Labs', 'Pat McGrath', 'Natasha Denona', 'Dior',
    'YSL', 'Yves Saint Laurent', 'Makeup by Mario', 'Chanel', 'Hermès', 'Hermes', 'Guerlain', 'Givenchy', 'Gucci',
    'Tom Ford', 'Victoria Beckham', 'Hourglass', 'Westman', 'Sisley', 'Rose Inc', 'Lancôme', 'Lancome', 'Estée Lauder',
    'Estee Lauder', 'MAC Cosmetics', 'NARS', 'Urban Decay', 'Anastasia Beverly Hills', 'Too Faced', 'Benefit',
    'Clinique', 'Bobbi Brown', 'Armani', 'Valentino', 'Prada', 'Burberry', 'Louboutin', 'Sephora', 'Asteri', 'Mikyajy',
    'Shiffa', 'Kylie', 'Morphe', 'ColourPop', 'Kiko', 'Bourjois', 'Maybelline', "L'Oréal", "L'Oreal", 'Revlon',
)


class ImageCallRefused(Exception):
    """An image call refused before payment — the reason in words."""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


#: a sha256 as ``_sha`` writes it — 64 lowercase hex digits, the only form the denylist is keyed by
_SHA256 = re.compile(r'[0-9a-f]{64}')


def _digest(value):
    """``value`` when it is a sha256 as ``_sha`` writes it, else None — a record that carries no digest has none (the
    gate review of Day 8: a missing or malformed sha256 is never read as a clean one)."""
    return value if isinstance(value, str) and _SHA256.fullmatch(value) else None


#: D-D8-2 rejects every design made BEFORE Day 8; a paid picture bought under a Day 8 operation (a sketch, a build's
#: plate) is today's own work, filed by the ledger under its reservation id — never a rejected design, or the chosen
#: sketch could not be its own build's style reference (§5 Stage 2)
TODAY_OPERATION_PREFIX = 'day12/'     # [Day 11] Day 10's paid pictures are no longer today's own work (D-D11 §8);
                                      # [Day 12] nor Day 11's


def _todays_responses(responses_root: Path) -> set:
    """The reservation ids (response folder names) the ledger files under a Day 8 operation."""
    import sqlite3
    ledger = responses_root.parent / 'ledger.sqlite3'
    if not ledger.exists():
        return set()
    with sqlite3.connect(str(ledger), timeout=30) as db:
        rows = db.execute("select id from calls where operation like ?", (TODAY_OPERATION_PREFIX + '%',)).fetchall()
    return {r[0] for r in rows}


def _images_under(roots) -> list:
    out = []
    for root in roots:
        if root.exists():
            found = [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
            if root.name == 'responses' and root.parent.name == 'rescue_spend':
                today = _todays_responses(root)
                found = [p for p in found if p.relative_to(root).parts[0] not in today]
            out += found
    return out


def _cached_sha(entry, st):
    """The sha256 the cache holds for a file hashed at its present size and mtime_ns — else None, and it is hashed
    again."""
    # Day 8 residual, documented and not closed: a path whose size and mtime_ns are both unchanged is trusted without
    # reading it. A rewrite of the same size whose mtime is put back (touch -r, or os.utime with ns=) keeps the stale
    # sha256 here, and a copy of its new bytes passes check() until denylist(refresh=True) hashes every file again or
    # the file's size or mtime moves. Measured on this APFS volume (2026-10-20): such a rewrite, and a file of the same
    # size and mtime renamed over the path, keep st_size and st_mtime_ns; st_ctime_ns moves (the kernel sets it on a
    # write and on the utime call itself, and touch and os.utime cannot set it back) and the rename changes st_ino.
    # Keying on those two would catch both cases measured here; that is left for a ruling, since a new key hashes every
    # file once. Hashing every file on every call is not done: check() builds the denylist on every guarded image call,
    # and audit() on every audit, over 326,193 paths and 11.7 GB under the rejected and web roots (counted from the
    # cache, 2026-10-20), so every byte would be read again on each call.
    if isinstance(entry, dict) and entry.get('size') == st.st_size and entry.get('mtime_ns') == st.st_mtime_ns:
        return _digest(entry.get('sha256'))
    return None


def denylist(*, refresh: bool = False) -> dict:
    """``{"rejected": {sha: path}, "web": {sha: path}}`` — every image under the rejected and the web roots, hashed and
    cached (``var/day8/image-guard-denylist.json``) with the size and mtime_ns each file was hashed at; a file the cache
    has not seen, or one whose size or mtime has changed since, is hashed again."""
    files = {'rejected': _images_under(REJECTED_ROOTS), 'web': _images_under(WEB_ROOTS)}
    cache = {}
    if DENYLIST_CACHE.exists() and not refresh:
        try:
            cache = json.loads(DENYLIST_CACHE.read_text())
        except ValueError:
            cache = {}
    # fix (gate review, Day 8): the cache held {sha: path} and was read back by path alone, so a file in a rejected root
    # rewritten in place kept its first sha256 and a copy of its new bytes passed check(). Each path is now cached with
    # the size and mtime_ns it was hashed at (its stat read before its bytes) and hashed again when either differs. A
    # cache in the old format has no 'by_path' table, so every file in it is hashed again, none of its shas trusted
    # (and a process still running the old code finds no 'rejected' or 'web' table here, so it hashes, never fails).
    hashed = cache['by_path'] if 'by_path' in cache else {}
    out, by_path = {}, {}
    for kind, paths in files.items():
        known = hashed[kind] if kind in hashed else {}                  # path -> {sha256, size, mtime_ns}
        table, entries = {}, {}
        for p in paths:
            st = p.stat()
            sha = _cached_sha(known.get(str(p)), st)
            if sha is None:
                sha = _sha(p)
            entries[str(p)] = {'sha256': sha, 'size': st.st_size, 'mtime_ns': st.st_mtime_ns}
            table[sha] = str(p)
        out[kind], by_path[kind] = table, entries
    DENYLIST_CACHE.parent.mkdir(parents=True, exist_ok=True)
    DENYLIST_CACHE.write_text(json.dumps({'by_path': by_path}))
    return out


def _under(path: Path, roots) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def competitor_in(prompt: str) -> str:
    """The first competitor brand the prompt names, or ''."""
    for name in COMPETITORS:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(name), prompt, re.I):
            return name
    return ''


def check(inputs, prompt: str, *, provider: str = 'openai', model: str | None = None, deny: dict | None = None) -> list:
    """The inputs as they would be sent, each ``{role, path, sha256}`` — or ``ImageCallRefused`` with the reason."""
    if provider != 'openai':
        raise ImageCallRefused('D-D8-10: generated images come from OpenAI only — provider %r refused' % provider)
    if (model or settings.IMAGE_MODEL) != settings.IMAGE_MODEL:
        raise ImageCallRefused('D-D8-10: the image model is %s — %r refused' % (settings.IMAGE_MODEL, model))
    name = competitor_in(prompt)
    if name:
        raise ImageCallRefused('D-D8-7: the prompt names a competitor brand (%s)' % name)
    deny = deny if deny is not None else denylist()
    checked = []
    for item in inputs:
        role, path = item['role'], Path(item['path'])
        if not path.exists():
            raise ImageCallRefused('input %s (%s) does not exist' % (path, role))
        sha = _sha(path)
        approved_logo = any(path.resolve() == pinned.resolve() and sha == pinned_sha
                            for pinned, pinned_sha in (APPROVED_LOGO,) + APPROVED_PICKS)
        # [Day 9] the approved logo is the house's own mark, never a design the system made: archived audit folders
        # (the Codex snapshot) hold byte-identical copies of it, so it is matched by its exact path AND sha before the
        # rejected-design hash check — its copies anywhere else stay refused
        if sha in deny['rejected'] and not approved_logo:
            raise ImageCallRefused('D-D8-2: input %s (%s) is a design the system made to date (%s)'
                                   % (path.name, role, deny['rejected'][sha]))
        if sha in deny['web'] or _under(path, WEB_ROOTS):
            raise ImageCallRefused('D-D8-7: input %s (%s) is a web picture — research only' % (path.name, role))
        if not approved_logo and not _under(path, ALLOWED_ROOTS):
            raise ImageCallRefused('input %s (%s) is outside the roots a Day 11 image call may draw on' % (path, role))
        if _under(path, HOUSE_DESIGN_ROOTS) and role != 'house trait crop':
            raise ImageCallRefused('D-D8-7: a house design reaches an image call only as a crop of a named trait')
        checked.append({'role': role, 'path': str(path), 'sha256': sha})
    return checked


def log_call(record: dict) -> None:
    """One line of the call log (append-only)."""
    CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = dict(record, at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
    with open(CALL_LOG, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + '\n')


def guarded_call(invoke, *, operation: str, inputs, prompt: str, quality: str, size: str, **extra):
    """``invoke(checked_inputs)`` after ``check`` passes; the call logged either way; a refusal raised before payment."""
    try:
        checked = check(inputs, prompt)
    except ImageCallRefused as exc:
        # Day 8 residual: the caller's extra fields come FIRST, so none of them (an 'outcome', a 'model', 'inputs')
        # can overwrite what the guard itself records about the call
        log_call({**extra, 'operation': operation, 'provider': 'openai', 'model': settings.IMAGE_MODEL, 'outcome': 'refused',
                  'why': str(exc), 'inputs': [{'role': i['role'], 'path': str(i['path'])} for i in inputs],
                  'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'prompt': prompt,
                  'quality': quality, 'size': size})
        raise
    try:
        result = invoke(checked)
    except Exception as exc:
        log_call({**extra, 'operation': operation, 'provider': 'openai', 'model': settings.IMAGE_MODEL, 'outcome': 'failed',
                  'why': '%s: %s' % (type(exc).__name__, str(exc)[:300]), 'inputs': checked,
                  'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'prompt': prompt,
                  'quality': quality, 'size': size})
        raise
    log_call({**extra, 'operation': operation, 'provider': 'openai', 'model': settings.IMAGE_MODEL, 'outcome': 'made',
              'inputs': checked, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(), 'prompt': prompt,
              'quality': quality, 'size': size,
              **({'result': result} if isinstance(result, dict) else {})})
    return result


#: the outcomes ``guarded_call`` writes, read exactly as written: sent ('made', 'failed') or refused before payment
def _is_approved_logo(item: dict) -> bool:
    """An input row naming the approval's own source raster (APPROVED_LOGO) or one of the owner's picks (APPROVED_PICKS: Day
    10's and Day 11's): its path is the file's and its sha256 the recorded one."""
    path = item['path'] if 'path' in item else None
    if not isinstance(path, str) or 'sha256' not in item:
        return False
    return any(Path(path).resolve() == pinned.resolve() and item['sha256'] == sha
               for pinned, sha in (APPROVED_LOGO,) + APPROVED_PICKS)


OUTCOMES = ('made', 'failed', 'refused')


def audit(log_path: Path = CALL_LOG) -> dict:
    """§8 — asserted from the call log: no Gemini, Pacdora or Blender call; no rejected design and no web picture in any
    image call; no competitor name in any image prompt. A sent call whose row does not record what it sent (no inputs,
    an input with no sha256, no prompt) cannot be asserted clean: it is counted, and the audit does not hold. Nor does
    it hold on a row whose outcome is none of ``OUTCOMES`` ('unknown_outcome'), on a log that does not exist
    ('log_present' False, every count None) or on a log with no rows ('log_empty')."""
    # Day 8 residual (the gate review's follow-up): a missing log was read as no rows and audited holds=True with
    # calls=0, though nothing was read and so nothing was asserted. It does not hold now, says log_present False, and
    # every count is None: unknown, never 0 (as a cost whose token counts are missing is unknown, never $0).
    present = log_path.exists()
    # Day 8 residual: rows are split on '\n' only — str.splitlines() also splits on U+2028 / U+0085, which a prompt
    # written with ensure_ascii=False may carry inside its JSON string
    rows = [json.loads(l) for l in log_path.read_text(encoding='utf-8').split('\n') if l.strip()] if present else []
    deny = denylist()
    made = [r for r in rows if r.get('outcome') in ('made', 'failed')]
    # Day 8 residual: only 'made' and 'failed' rows were read and 'refused' counted, so a row with no outcome, or with
    # one that is not exactly one of the three (another case, a typo), was checked by nothing and the audit still held.
    # It is counted by name and the audit does not hold. It stays out of 'sent' and out of the input and prompt counts,
    # which read only what is known to have been sent, so calls = sent + refused + unknown_outcome.
    unknown_outcome = [r for r in rows if r.get('outcome') not in OUTCOMES]
    bad_provider = [r for r in rows if r.get('provider') != 'openai'
                    or (r.get('outcome') != 'refused' and re.search(r'gemini|pacdora|blender', str(r.get('model')), re.I))]
    # fix (gate review, Day 8): the inputs and the prompt were read with [] and '' as their defaults, so a sent row with
    # no inputs or no prompt read as clean, while a missing provider counted as bad; such a row, or one with an input
    # carrying no sha256, is now counted by name (a row once) and the audit does not hold. A refused row sent nothing
    # and is not read here.
    sent_shas = [(r, [_digest(i.get('sha256')) if isinstance(i, dict) else None for i in r['inputs']])
                 for r in made if isinstance(r.get('inputs'), list)]
    no_input_sha = [r for r in made if not isinstance(r.get('inputs'), list)] + [r for r, shas in sent_shas if None in shas]
    # Day 9: the approved logo is exempt here exactly as check() exempts it — by its path and its sha256 together (a copy of
    # the same bytes under a rejected root is a rejected design; the approval's own source raster is not)
    bad_inputs = [r for r in made if isinstance(r.get('inputs'), list) for i in r['inputs']
                  if isinstance(i, dict) and (_digest(i.get('sha256')) in deny['rejected'] or _digest(i.get('sha256')) in deny['web'])
                  and not _is_approved_logo(i)]
    no_prompt = [r for r in made if not isinstance(r.get('prompt'), str)]
    bad_prompts = [r for r in made if isinstance(r.get('prompt'), str) and competitor_in(r['prompt'])]
    counts = {'calls': len(rows), 'sent': len(made), 'refused': len([r for r in rows if r.get('outcome') == 'refused']),
              'non_openai_or_named_tool': len(bad_provider), 'rejected_or_web_inputs': len(bad_inputs),
              'competitor_prompts': len(bad_prompts), 'sent_without_input_sha256': len(no_input_sha),
              'sent_without_prompt': len(no_prompt), 'unknown_outcome': len(unknown_outcome)}
    if not present:
        counts = {key: None for key in counts}                       # no log was read: no count was measured
    # Day 8 residual: a log with no rows does not hold either. guarded_call writes one row for every call it is given
    # (made, failed or refused), and every paid Day 8 picture went through it: the log's 22 rows (18 sketches, 4 build
    # plates) are, operation for operation, the spend ledger's 22 OpenAI image calls of Day 8 (checked 2026-10-20). So
    # a Day 8 log with no rows cannot tell "no image call was made" from "its rows were lost, cut or never written", and
    # zero rows assert nothing about the calls §8 asks about. It is reported (log_empty, its counts measured as 0). A
    # log of refusals alone still holds, because it records every call.
    return dict(counts, log_present=present, log_empty=(not rows) if present else None,
                holds=(present and len(rows) > 0 and not unknown_outcome and not bad_provider and not bad_inputs
                       and not bad_prompts and not no_input_sha and not no_prompt))


# --- the ideas half's image calls: the boards and the designs (from round_ideas_calls, 2026-10-28) --------------------
# Durable original-image calls for the ideas-only round pipeline.

def design_image_estimate(prompt, quality=SKETCH_QUALITY):
    """Reserve from the configured tariff; settlement uses provider usage.

    Historical high-quality 1536x1024 replies use 5,488 output tokens. Reserve
    8,192, plus a conservative byte-per-token prompt allowance and 1,024 input
    tokens of overhead, with another 25 percent margin. No reference images
    are sent by this endpoint. Missing tariffs fail before any provider call.
    """
    tariff = getattr(settings, 'OPENAI_IMAGE_PRICES', {}).get(IMAGE_MODEL, {})
    prices = [tariff.get(key) for key in ('text_input', 'image_output', 'image_input')]
    if any(isinstance(price, bool) or not isinstance(price, (int, float))
           or not math.isfinite(price) or price <= 0 for price in prices):
        raise ValueError('A current image tariff is required before reserving an ideas image.')
    text_price, output_price, _ = prices
    return math.ceil(1.25 * ((len(prompt.encode('utf-8')) + 1024) * text_price
                            + IMAGE_OUTPUT_RESERVE[quality] * output_price)) / 1_000_000


#: A gpt-image-2 input picture: a library preview, measured at 484 image tokens each on round 3's boards (1,452 for
#: three), reserved at twice that; the flat die's template and board at the full canvas, not yet measured, at 8,192.
REFERENCE_INPUT_TOKENS = 1024
FLAT_INPUT_TOKENS = 8192
MAX_REFERENCES = 3


def reference_image_estimate(prompt, count, quality=SKETCH_QUALITY, tokens=REFERENCE_INPUT_TOKENS):
    """A board drawn from house-library pictures: the original reservation plus each input picture's tokens."""
    image_price = getattr(settings, 'OPENAI_IMAGE_PRICES', {}).get(IMAGE_MODEL, {}).get('image_input')
    if isinstance(image_price, bool) or not isinstance(image_price, (int, float)) or not math.isfinite(image_price) or image_price <= 0:
        raise ValueError('A current image-input tariff is required before reserving a board drawn from references.')
    return design_image_estimate(prompt, quality) + math.ceil(1.25 * count * tokens * image_price) / 1_000_000


class IdeasContext(RoundContext):
    # Twenty accepted originals remain the stage target. Failed/rejected paid
    # attempts count too; the round's dollar cap remains the binding guard.
    image_attempt_cap = 40

    def _reference(self, item):
        """A house-library picture chosen at research time, sent only while its bytes match their record."""
        path = Path(item['path']).resolve()
        if _under(path, WEB_ROOTS) or not path.is_file() or sha(path) != item['sha256']:
            raise ValueError('A library reference changed or is not a house-library picture; no image call made.')
        with Image.open(path) as image:
            size = list(image.size)
        return {'id': item['id'], 'role': 'mood board reference', 'library_sha256': item['library_sha256'],
                'path': str(path), 'sha256': item['sha256'], 'px': size, 'sent_unchanged': True}

    def design_image_call(self, operation, prompt, output, *, references=(), template=None, style=None):
        """Generate one original PNG, preserving raw replies across deliveries.

        ``output`` is a candidate directory inside this round. The provider
        bytes are saved unchanged as raw.png beside the durable call records.
        Only an explicit owner retry can replace a known invalid response;
        an unknown provider outcome always retains its reservation. A mood
        board may carry up to three house-library pictures as references,
        recorded by hash; without them the request identity is unchanged.
        ``template`` and ``style``: a design painted on the stand's flat die
        (owner, 2026-10-28) — one edit, image 1 the die's template and its
        mask, image 2 the picked board, at the template's own canvas.
        """

        destination = self._destination(Path(output) / 'image-call.json')
        if settings.IMAGE_MODEL != IMAGE_MODEL or competitor_in(prompt):
            raise ValueError('Round image model or prompt is outside the allowed boundary.')
        if len(references) > MAX_REFERENCES:
            raise ValueError('A board takes at most three library references.')
        quality = SKETCH_QUALITY if self.ruled else 'high'
        args = {'model': IMAGE_MODEL, 'quality': quality, 'size': '1536x1024',
                'prompt': prompt, 'n': 1, 'output_format': 'png'}
        identity = {'protocol': 'ideas-original-v1', 'endpoint': 'images.generate', **args}
        estimate = design_image_estimate(prompt, quality)
        inputs = [self._reference(item) for item in references]
        flat = [self._input(template), self._input(style)] if template is not None else []
        if flat:
            if inputs or '%dx%d' % tuple(flat[0]['px']) not in ('1536x1024', '1024x1536'):
                raise ValueError('A flat design is the die\'s template and the picked board, on a full canvas.')
            args['size'] = '%dx%d' % tuple(flat[0]['px'])
            identity = {'protocol': 'designer-flat-die-v1', 'endpoint': 'images.edit', **args, 'inputs': flat,
                        'mask': flat[0], 'stream': {'partial_images': STREAM_PARTIAL_IMAGES}}
            estimate = reference_image_estimate(prompt, len(flat), quality, tokens=FLAT_INPUT_TOKENS)
        elif inputs:
            identity = {'protocol': 'designer-board-references-v1', 'endpoint': 'images.edit', **args,
                        'references': inputs}
            estimate = reference_image_estimate(prompt, len(inputs), quality)
        operation = operation if operation.startswith('image/') else 'image/' + operation
        cached, request, request_path = self._request(destination, identity, provider='openai',
            operation=operation, estimate=estimate)
        raw_image = destination.parent / 'raw.png'
        if cached is not None:
            if not raw_image.exists() or sha(raw_image) != cached['output_sha256']:
                raise ValueError('Saved paid image changed; no repurchase.')
            return cached

        raw_path = destination.with_suffix('.response.json')
        if raw_path.exists():
            raw = json.loads(raw_path.read_text())
        else:
            if request['started_attempts']:
                raise ValueError('Prior image outcome is unknown; reservation held, no repeated payment.')
            if request['reservation_id'] not in self.active_calls:
                self._one_call()
                self.active_calls.add(request['reservation_id'])
            request['started_attempts'] = [0]
            write_json(request_path, request)
            if self.image_client is None:
                if 'pytest' in sys.modules:
                    raise RuntimeError('Round fixtures require an explicit fake image client.')
                from openai import OpenAI
                self.image_client = OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=0, timeout=400)
            try:
                if flat:
                    with ExitStack() as stack:
                        opened = [stack.enter_context(Path(item['path']).open('rb')) for item in flat]
                        mask = stack.enter_context(Path(flat[0]['path']).open('rb'))
                        response = streamed_edit(self.image_client, destination.with_suffix('.stream.json'),
                                                 image=opened, mask=mask, **args)
                elif inputs:
                    with ExitStack() as stack:
                        opened = [stack.enter_context(Path(item['path']).open('rb')) for item in inputs]
                        response = self.image_client.images.edit(image=opened, **args)
                else:
                    response = self.image_client.images.generate(**args)
            except Exception as exc:
                status = spend.rejected_status(exc)
                if status is not None:
                    spend.release_rejected(request['reservation_id'], status, exc)
                write_json(destination.with_suffix('.error.json'), {
                    'error_type': type(exc).__name__, 'http_status': status,
                    'reservation_id': request['reservation_id']})
                commit_artifacts(self.round, f'{operation}: provider failure retained')
                raise
            raw = spend._plain(response)
            write_json(raw_path, raw)
            commit_artifacts(self.round, f'{operation}: raw image reply saved')

        # A malformed image is still a billed reply. Reconcile before decoding.
        spend.settle(request['reservation_id'], raw, raw_path, provider='openai', model=IMAGE_MODEL)
        usage = raw.get('usage') if isinstance(raw, dict) else None

        def reject_image(reason):
            self._finish(destination, request, dict(identity, status='validation_failed',
                         usage=usage, validation_error=reason), operation=operation, image=True)
            raise ValueError(reason)

        data = raw.get('data') if isinstance(raw, dict) else None
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
            reject_image('Exactly one paid image is required; reply retained.')
        item = data[0]
        if item.get('b64_json'):
            try:
                image_bytes = base64.b64decode(item['b64_json'], validate=True)
            except (binascii.Error, ValueError, TypeError):
                reject_image('Paid image bytes are not valid base64; reply retained.')
        elif item.get('url'):
            # Local download errors recover from the saved reply, never a new purchase.
            image_bytes = download_image_bytes(item['url'])
        else:
            reject_image('Paid image bytes missing; reply retained.')
        try:
            with Image.open(BytesIO(image_bytes)) as image:
                image.load()
                dimensions, image_format = image.size, image.format
        except (UnidentifiedImageError, OSError, ValueError, TypeError):
            reject_image('Paid image bytes cannot be decoded; reply retained.')
        if image_format != 'PNG':
            reject_image('Provider image is not PNG; paid reply retained.')
        if list(dimensions) != (flat[0]['px'] if flat else [1536, 1024]):
            reject_image('Provider image has the wrong dimensions; paid reply retained.')
        # Keep byte identity: do not re-encode even a valid PNG. Local write errors
        # leave the saved provider reply recoverable without buying another image.
        raw_image.write_bytes(image_bytes)
        return self._finish(destination, request, dict(identity, status='complete',
            output_sha256=sha(raw_image), output_px=list(dimensions), usage=usage),
            operation=operation, image=True)
