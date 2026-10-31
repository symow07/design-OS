"""Round 1 paid boundary. Original image bytes, scoped reservations, durable replies.

The owner requests the repository's masked-edit/usage-ledger route. No rescue
judgment or design input is inherited. Imports and tests never buy a call.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from django.conf import settings
from PIL import Image

from . import spend_reservation as spend
from .round_calls import parse_response_text

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / 'docs/rounds/r1-balm'
MODEL = 'claude-opus-5-5'
PREFIX = 'r1-balm/'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def append(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')


def image_block(path):
    path = Path(path)
    with Image.open(path) as im:
        size = list(im.size)
    return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
            'data': base64.b64encode(path.read_bytes()).decode()}}, {
                'path': str(path.relative_to(REPO)), 'sha256': sha(path), 'px': size,
                'sent_unchanged': True}


def text_call(operation, prompt, destination, *, images=(), max_tokens=3000,
              ceiling=.17, client=None):
    """One call, never automatic retries; existing successful result is resumable."""
    destination = Path(destination)
    content, inputs = [], []
    for caption, path in images:
        block, rec = image_block(path)
        rec['caption'] = caption
        content += [{'type': 'text', 'text': caption}, block]
        inputs.append(rec)
    content.append({'type': 'text', 'text': prompt})
    request = {'model': MODEL, 'max_tokens': max_tokens,
               'messages': [{'role': 'user', 'content': content}]}
    if len(json.dumps(request).encode()) > 31_000_000:
        raise ValueError('Full-size request exceeds conservative 31 MB boundary; no payment made')
    identity = {'model': MODEL, 'max_tokens': max_tokens, 'prompt': prompt, 'images': inputs}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if destination.exists():
        record = json.loads(destination.read_text())
        if record['request_sha256'] != digest or record.get('status') != 'complete':
            raise ValueError('Existing paid result cannot be silently replaced: ' + str(destination))
        return record
    request_path = destination.with_suffix('.request.json')
    if request_path.exists():
        raise ValueError('Unresolved prior attempt; reconcile it before another paid call.')
    from .cost_ledger import claude_cost_usd
    text_tokens = (len(prompt.encode()) + sum(len(caption.encode()) for caption,_ in images)) / 2 + 500
    image_tokens = sum(r['px'][0] * r['px'][1] / 600 + 500 for r in inputs)
    estimate = float(claude_cost_usd(MODEL, text_tokens + image_tokens, max_tokens)) * 1.1
    if estimate > ceiling:
        raise ValueError(f'Request upper estimate ${estimate:.4f} exceeds ${ceiling:.2f}')
    identifier = spend.reserve('anthropic', PREFIX + operation, MODEL, estimate, digest,
                               budget_prefix=PREFIX, prefix_cap=20)
    write(request_path, dict(identity, request_sha256=digest, reservation_id=identifier,
                             reservation_usd=estimate, ceiling_usd=ceiling))
    if client is None:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=0, timeout=300)
    try:
        response = client.messages.create(**request)
    except Exception as exc:
        status = spend.rejected_status(exc)
        if status is not None:
            spend.release_rejected(identifier, status, exc)
        write(destination, {'status': 'provider_error', 'request_sha256': digest,
                            'reservation_id': identifier, 'error_type': type(exc).__name__,
                            'http_status': status})
        raise
    raw = response.model_dump(mode='json')
    raw_path = destination.with_suffix('.response.json')
    write(raw_path, raw)
    spend.settle(identifier, raw, raw_path, provider='anthropic', model=MODEL)
    text = ''.join(c.get('text', '') for c in raw['content'] if c.get('type') == 'text')
    parse_error = None
    try:
        payload = parse_response_text(text)
    except (ValueError,TypeError) as exc:
        payload = None
        parse_error = type(exc).__name__
    with spend._connect() as db:
        row = dict(db.execute('SELECT state,accounted,reserved FROM calls WHERE id=?', (identifier,)).fetchone())
    record = {'status': 'complete' if raw.get('stop_reason') == 'end_turn' and parse_error is None else 'incomplete',
              'request_sha256': digest, 'reservation_id': identifier, 'model': MODEL,
              'images': inputs, 'payload': payload, 'usage': raw.get('usage'),
              'cost_usd': row['accounted'] / 1e6 if row['state']=='usage_recorded' else None,
              'accounted_usd': row['accounted']/1e6, 'reserved_usd':row['reserved']/1e6, 'billing_state': row['state'],
              'parse_error':parse_error,'stop_reason':raw.get('stop_reason'),
              'raw_response_path':str(raw_path.relative_to(REPO))}
    write(destination, record)
    append(OUT / 'calls.jsonl', dict(record, operation=operation, payload_file=str(destination.relative_to(REPO))))
    if record['status'] != 'complete':
        raise ValueError('Incomplete paid response retained; never a verdict.')
    return record


def seed_prompt():
    source = (OUT / 'REQUEST.txt').read_text()
    brief = source.split('- **D-R1-9')[1].split('- **D-R1-10')[0]
    keep = (REPO / 'docs/audit/day-8/house-dna/house-dna.md').read_text()
    keep = '\n'.join(line for line in keep.splitlines() if '| **Keep** |' in line)
    return '''Return JSON only: {"seeds":[{"id":"A1","family":"action","seed":"..."}, ...]}.
Exactly twenty short seeds, <=15 whitespace-delimited words each; five each family:
action (A1-A5): turning, uncapping or unboxing; panels as moments of an action;
overlooked (B1-B5): invention begins bottom label, carton back or top, front follows;
craft (C1-C5): one named medium/technique governs every panel;
free (D1-D5): what one thing a stranger would repeat.
Each seed is only a mood, one constraint and where invention may live. No written-out
idea, layout, hex, font, copy list, collection name or explanatory field. Across all
twenty, never repeat a mood or material; leave the picture to discover the idea.
A $1B prestige house: crafted artwork, restrained branding, never one colour family
everywhere, never looks easy to make; each element its true medium.
Banned main motifs: rose flowers, petals, gardens, arches, glow frames, lips, cherries,
botanical line-art wallpaper; the August twelve-rosette, engine-turned cartouche and
strapwork moire; kisses, drips, honey, bees. Techniques remain open in new figures.
Taste, words only, no style inheritance: owner ranked Zilal master > its Day 9 build >
Golden Hour master > family sheet > header > lipstick > balm > A-2.3 > Day 8.
House Keep (vocabulary, not mandatory palette or layout):
''' + keep + '\nProduct brief: D-R1-9' + brief


def make_seeds():
    if (OUT/'seeds.json').exists():
        return json.loads((OUT/'seeds.json').read_text())['seeds']
    record = text_call('seeds', seed_prompt(), OUT / 'seeds-call.json', max_tokens=4000, ceiling=.40)
    rows = record['payload']['seeds']
    expected = {f'{f}{n}' for f in 'ABCD' for n in range(1, 6)}
    if len(rows) != 20 or {r['id'] for r in rows} != expected:
        raise ValueError('Seeds must be exactly the twenty named IDs.')
    families = dict(zip('ABCD', ('action', 'overlooked', 'craft', 'free')))
    for row in rows:
        if row['family'] != families[row['id'][0]] or not 1 <= len(row['seed'].split()) <= 15:
            raise ValueError('Seed family or word count invalid: ' + row['id'])
    write(OUT / 'seeds.json', {'schema': 'r1_seeds/1', 'source': 'seeds-call.json', 'seeds': rows})
    return rows
