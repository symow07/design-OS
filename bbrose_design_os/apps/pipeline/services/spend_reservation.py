"""Rescue budget: atomic reservations and durable paid replies before interpretation.

The journal covers task and taskless calls. USD values are accounting estimates,
not invoices; provider usage is retained verbatim. Unknown billing keeps its full
reservation. Caps apply to the Asia/Shanghai calendar day and the whole rescue.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings

DAY_CAP = 25_000_000
TOTAL_CAP = 250_000_000


def _root():
    root = Path(getattr(settings, 'RESCUE_SPEND_ROOT', Path(settings.BASE_DIR) / 'var' / 'rescue_spend'))
    import sys
    if 'pytest' in sys.modules and not hasattr(settings, 'RESCUE_SPEND_ROOT'):
        raise RuntimeError('Tests require an isolated RESCUE_SPEND_ROOT.')
    root.mkdir(parents=True, exist_ok=True)
    return root


def _connect():
    connection = sqlite3.connect(_root() / 'ledger.sqlite3', timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute('''CREATE TABLE IF NOT EXISTS calls (
        id TEXT PRIMARY KEY, day TEXT NOT NULL, provider TEXT NOT NULL,
        operation TEXT NOT NULL, model TEXT NOT NULL, task_id INTEGER,
        reserved INTEGER NOT NULL, accounted INTEGER NOT NULL,
        state TEXT NOT NULL, artifact TEXT, usage TEXT, request_hash TEXT,
        started_at TEXT NOT NULL, settled_at TEXT)''')
    return connection


def reserve(provider, operation, model, estimate, request_hash='', task=None, *, budget_prefix=None, prefix_cap=None, count_prefix=None, count_cap=None, attempt_limits=(), round_slug=None, round_cap=None):
    from .cost_ledger import BudgetExceededError, _resolve_task
    task = _resolve_task(task)
    amount = int(round(float(estimate) * 1_000_000))
    if amount <= 0:
        raise ValueError('A positive cost estimate is required before payment.')
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    day = now.date().isoformat()
    identifier = uuid.uuid4().hex
    with _connect() as db:
        db.execute('BEGIN IMMEDIATE')
        total = db.execute('SELECT COALESCE(SUM(accounted),0) FROM calls').fetchone()[0]
        daily = db.execute('SELECT COALESCE(SUM(accounted),0) FROM calls WHERE day=?', (day,)).fetchone()[0]
        if total + amount > TOTAL_CAP or daily + amount > DAY_CAP:
            raise BudgetExceededError('Spending paused before payment: the estimated call would exceed the $25 Shanghai calendar-day or $250 rescue budget. No design elements were removed.')
        if budget_prefix is not None:
            if not budget_prefix or not operation.startswith(budget_prefix) or prefix_cap is None or prefix_cap <= 0:
                raise ValueError('A scoped reservation needs its exact operation prefix and positive cap.')
            scoped = db.execute('SELECT COALESCE(SUM(accounted),0) FROM calls WHERE substr(operation,1,?)=?',
                                (len(budget_prefix),budget_prefix)).fetchone()[0]
            if scoped + amount > int(round(prefix_cap*1_000_000)):
                raise BudgetExceededError('Spending paused before payment: the owner-scoped allowance would be exceeded.')
        if round_slug is not None:
            # one cap for a whole round, brief to Make my files (the owner's ruling of 2026-10-29): every call whose
            # operation names the round's slug counts, whichever prefix it was made under
            if not round_slug or ('/%s/' % round_slug) not in operation or round_cap is None or round_cap <= 0:
                raise ValueError('A round-capped reservation needs its round in the operation and a positive cap.')
            spent = db.execute('SELECT COALESCE(SUM(accounted),0) FROM calls WHERE instr(operation,?)>0',
                               ('/%s/' % round_slug,)).fetchone()[0]
            if spent + amount > int(round(round_cap*1_000_000)):
                raise BudgetExceededError('The round stopped before this call: it has spent $%.2f of its $%.2f cap and '
                                          'the call needs up to $%.2f. Nothing more is spent.'
                                          % (spent / 1e6, round_cap, amount / 1e6))
        limits=list(attempt_limits)
        if count_prefix is not None:limits.append((count_prefix,count_cap))
        for count_prefix,count_cap in limits:
            if not count_prefix or not operation.startswith(count_prefix) or not isinstance(count_cap,int) or count_cap <= 0:
                raise ValueError('An attempt limit needs its exact operation prefix and positive integer cap.')
            attempts=db.execute('SELECT COUNT(*) FROM calls WHERE substr(operation,1,?)=?',(len(count_prefix),count_prefix)).fetchone()[0]
            if attempts >= count_cap:
                raise BudgetExceededError('Image-attempt limit reached before payment; failed and uncertain attempts also count.')
        db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (identifier, day, provider, operation, model, getattr(task, 'pk', None), amount, amount,
                    'reserved', None, None, request_hash, now.isoformat(), None))
    return identifier


def _plain(value):
    if hasattr(value, 'model_dump'):
        result = value.model_dump(mode='json')
        if isinstance(result, dict):
            return result
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, '__dict__'):
        return {k: _plain(v) for k, v in vars(value).items() if not k.startswith('_')}
    raise TypeError('Provider response could not be serialized.')


def cache_read_multiplier(model):
    """A cache read's price as a fraction of the model's input price (settings.CLAUDE_CACHE_READ_MULTIPLIER, cited there)."""
    table = getattr(settings, 'CLAUDE_CACHE_READ_MULTIPLIER', {})
    return float(table.get(str(model), table.get('default', 0.1)))


def openai_image_cost_micro(model, usage):
    """Micro-USD for a gpt-image reply from its own usage counts, or None when the tariff or the counts are missing."""
    tariff = getattr(settings, 'OPENAI_IMAGE_PRICES', {}).get(str(model))
    details = usage.get('input_tokens_details') if isinstance(usage, dict) else None
    if not tariff or not isinstance(details, dict) or not isinstance(usage.get('output_tokens'), (int, float)):
        return None
    if not all(isinstance(details.get(k), (int, float)) for k in ('image_tokens', 'text_tokens')):
        return None
    usd = (details['image_tokens'] * tariff['image_input'] + details['text_tokens'] * tariff['text_input']
           + usage['output_tokens'] * tariff['image_output']) / 1_000_000
    return int(round(usd * 1_000_000))


def settle(identifier, payload, artifact, *, provider, model):
    """Retain actual token/credit usage; use known tariffs, never invent billed USD."""
    usage = payload.get('usage') if isinstance(payload, dict) else None
    accounted = None
    if provider == 'anthropic' and isinstance(usage, dict) and all(k in usage for k in ('input_tokens', 'output_tokens')):
        from .cost_ledger import claude_cost_usd
        # Cache writes at 1.25x input (5-minute TTL); cache reads at the published read price (Day 8: the owner asked the
        # ledger to price cache reads from the returned counts), never at the full input rate.
        inputs = (usage['input_tokens'] + 1.25 * (usage.get('cache_creation_input_tokens') or 0)
                  + cache_read_multiplier(model) * (usage.get('cache_read_input_tokens') or 0))
        accounted = int(claude_cost_usd(model, inputs, usage['output_tokens']) * 1_000_000)
    elif provider == 'tavily' and isinstance(usage, dict) and isinstance(usage.get('credits'), (int, float)):
        accounted = int(usage['credits'] * settings.TAVILY_USD_PER_CREDIT * 1_000_000)
    elif provider == 'openai':
        # Day 8 (D-D8-10): an image call whose reply carries the provider's token counts is settled at the published
        # standard tariff (settings.OPENAI_IMAGE_PRICES, cited there); anything less keeps its reservation.
        accounted = openai_image_cost_micro(model, usage)
    # Image token tariffs vary with input type/model. Keep the reservation until
    # invoice reconciliation rather than mislabelling a flat per-image guess as actual.
    with _connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM calls WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise ValueError('Unknown reservation')
        if row['state'] != 'reserved':
            return
        value = row['reserved'] if accounted is None else max(0, accounted)
        db.execute('UPDATE calls SET accounted=?, state=?, artifact=?, usage=?, settled_at=? WHERE id=?',
                   (value, 'usage_recorded' if accounted is not None else 'billing_unresolved', str(artifact),
                    json.dumps(usage), datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), identifier))


def paid_operation(invoke, *args, provider, operation='', task=None, reservation_prefix=None, reservation_cap=None, estimate_override=None, count_prefix=None, count_cap=None, attempt_limits=(), **kwargs):
    """Exactly one provider attempt. Each application retry makes a new reservation."""
    model = str(kwargs.get('model', 'search'))
    if provider == 'anthropic':
        # Base64 image bytes aren't text tokens. Estimate image blocks separately.
        def text_size(value):
            if isinstance(value, dict):
                if value.get('type') == 'image':
                    return 16000
                return sum(text_size(v) for k, v in value.items() if k != 'data')
            if isinstance(value, (list, tuple)):
                return sum(text_size(v) for v in value)
            return len(value.encode('utf-8')) * 2 if isinstance(value, str) else 0
        from .cost_ledger import claude_cost_usd
        estimate = max(0.10, float(claude_cost_usd(model, text_size(kwargs) / 2, kwargs.get('max_tokens', 4096))) * 1.5)
    else:
        estimate = 1.0 * max(1, int(kwargs.get('n', 1))) if provider == 'openai' else 0.10
    # Hash only non-secret request identity. No headers or credentials enter the journal.
    identity = {k: kwargs[k] for k in ('model', 'prompt', 'messages', 'system', 'size', 'quality', 'n') if k in kwargs}
    request_hash = hashlib.sha256(json.dumps(identity, default=lambda _: '<binary>', sort_keys=True).encode()).hexdigest()
    if estimate_override is not None:
        estimate = max(estimate,float(estimate_override))
    identifier = reserve(provider, operation, model, estimate, request_hash, task=task,
                         budget_prefix=reservation_prefix,prefix_cap=reservation_cap,count_prefix=count_prefix,count_cap=count_cap,attempt_limits=attempt_limits)
    if provider == 'openai':
        import openai
        openai.max_retries = 0
    try:
        response = invoke(*args, **kwargs)  # failure retains reservation: billing may be unknown
    except Exception as exc:
        status = rejected_status(exc)
        if status is not None:
            release_rejected(identifier, status, exc)
        raise
    folder = _root() / 'responses' / identifier
    folder.mkdir(parents=True, exist_ok=False)
    if provider == 'tavily':
        (folder / 'response.body').write_bytes(response.content)
        try:
            payload = response.json()
        except ValueError:
            payload = {'parse_error': True}
    else:
        payload = _plain(response)
    artifact = folder / 'response.json'
    with artifact.open('x') as handle:
        request_id = getattr(response, '_request_id', None)
        json.dump({'provider_request_id': request_id if isinstance(request_id, str) else None, 'response': payload}, handle)
        handle.flush()
        import os
        os.fsync(handle.fileno())
    paid_images = []
    if provider == 'openai' and isinstance(payload, dict):
        for index, item in enumerate(payload.get('data') or []):
            if item.get('b64_json'):
                (folder / f'image-{index}.png').write_bytes(base64.b64decode(item['b64_json']))
            elif item.get('url'):
                from apps.pipeline.services.pipeline_errors import ImageDownloadError
                from apps.pipeline.services.round_calls import download_image_bytes
                try:
                    (folder / f'image-{index}.png').write_bytes(download_image_bytes(item['url']))
                except ImageDownloadError as exc:
                    # The provider succeeded. Preserve its URL and let the caller
                    # create the existing retry-download record without repurchasing.
                    (folder / f'image-{index}-download-error.txt').write_text(str(exc))
                    object.__setattr__(response, '_rescue_download_error', str(exc))
                    continue
            paid_images.append(str(folder / f'image-{index}.png'))
    if paid_images:
        object.__setattr__(response, '_rescue_paid_images', paid_images)
    settle(identifier, payload, artifact, provider=provider, model=model)
    try:
        object.__setattr__(response,'_rescue_reservation_id',identifier)
        object.__setattr__(response,'_rescue_response_artifact',str(artifact))
    except (AttributeError,TypeError):
        pass
    return response


#: [Day 8] statuses with which a provider rejects a request before running it — neither Anthropic nor OpenAI bills them
#: (a malformed request, auth, not found, too large, unprocessable, rate-limited); measured on Day 8: an unbilled 400
#: ("the compiled grammar is too large") held its $0.69 reservation for good and counted against the allowance
UNBILLED_REJECTIONS = (400, 401, 403, 404, 413, 422, 429)


def rejected_status(exc):
    """The HTTP status of a provider's rejection when it is one of ``UNBILLED_REJECTIONS``, else None (a timeout, a
    dropped connection or a 5xx keeps its reservation: billing unknown)."""
    status = getattr(exc, 'status_code', None)
    if status is None:
        response = getattr(exc, 'response', None)
        status = getattr(response, 'status_code', None)
    return status if status in UNBILLED_REJECTIONS else None


def release_rejected(identifier, status, exc) -> None:
    """A rejected, unbilled request: accounted at 0, its state and the provider's words kept."""
    with _connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE calls SET accounted=0, state='rejected_unbilled', usage=?, settled_at=? WHERE id=? AND state='reserved'",
                   (json.dumps({'http_status': status, 'error': str(exc)[:300]}),
                    datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), identifier))


def close_unknown(identifier, check) -> None:
    """A call whose outcome is unknown (the connection dropped, nothing came back), checked once against the provider:
    closed, never a permanent hold. Billed or unknown, its hold stays counted; only a provider check that shows nothing
    was billed releases it to 0. ``check``: that check's record."""
    released = check.get('billed') is False
    with _connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE calls SET accounted=CASE WHEN ? THEN 0 ELSE accounted END, state=?, usage=?, settled_at=? "
                   "WHERE id=? AND state='reserved'",
                   (released, 'released_unbilled' if released else 'outcome_unknown', json.dumps(check),
                    datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), identifier))


def release_unknown(identifier, check) -> bool:
    """A closed call of unknown outcome, checked again once the provider's usage for its window is final: released to
    0 only when that check shows nothing was billed; its check is recorded either way. Returns whether it was released."""
    released = check.get('billed') is False
    with _connect() as db:
        db.execute('BEGIN IMMEDIATE')
        cursor = db.execute("UPDATE calls SET accounted=CASE WHEN ? THEN 0 ELSE accounted END, state=?, usage=?, "
                            "settled_at=? WHERE id=? AND state='outcome_unknown'",
                            (released, 'released_unbilled' if released else 'outcome_unknown', json.dumps(check),
                             datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), identifier))
    return released and cursor.rowcount == 1


def totals():
    day = datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    with _connect() as db:
        total = db.execute('SELECT COALESCE(SUM(accounted),0) FROM calls').fetchone()[0]
        daily = db.execute('SELECT COALESCE(SUM(accounted),0) FROM calls WHERE day=?', (day,)).fetchone()[0]
        unresolved = db.execute("SELECT COUNT(*) FROM calls WHERE state IN ('reserved','billing_unresolved')").fetchone()[0]
    return {'today_usd_accounted': daily / 1_000_000, 'total_usd_accounted': total / 1_000_000,
            'unresolved_calls': unresolved, 'day_cap_usd': 25, 'total_cap_usd': 250}
