"""HAYAT preservation: one fidelity look, one bounded repair, two blind readings.

Only text/vision messages are possible here. No image generation and no jury.
Every request is reserved before payment and its raw reply precedes interpretation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from . import round_balm_calls as calls
from . import spend_reservation as spend

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / 'docs/rounds/r1-balm/master'
SOURCE = REPO / 'docs/rounds/r1-balm/developments/D1/A'
PREFIX = 'r1-balm-b/'
OPERATIONS = ('eye-r0', 'eye-r1', 'reading-K1', 'reading-K2')
CLOSE_PREFIX = 'r1-balm-c/'
PANELS = ('body', 'cap', 'label', 'back', 'side_left', 'front', 'side_right', 'top_end', 'bottom_end')


def paid_text(operation, prompt, images, *, ceiling, max_tokens=2200, client=None):
    """One resumable attempt under the owner's $3 scope, including failures."""
    if operation not in OPERATIONS:
        raise ValueError('Only the eye and two blind readings are authorized.')
    return _paid_text(operation, prompt, images, ceiling=ceiling, max_tokens=max_tokens,
                      client=client, prefix=PREFIX, scope_cap=3)


def _paid_text(operation, prompt, images, *, ceiling, max_tokens, client, prefix, scope_cap):
    """Shared durable boundary; public entry points define their owner scope."""
    destination = OUT / 'calls' / (operation + '.json')
    content, inputs = [], []
    for caption, path in images:
        block, record = calls.image_block(path)
        inputs.append(dict(record, caption=caption))
        content.extend(({'type': 'text', 'text': caption}, block))
    content.append({'type': 'text', 'text': prompt})
    request = {'model': calls.MODEL, 'max_tokens': max_tokens,
               'messages': [{'role': 'user', 'content': content}]}
    identity = {'model': calls.MODEL, 'max_tokens': max_tokens, 'prompt': prompt, 'images': inputs}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if destination.exists():
        prior = json.loads(destination.read_text())
        if prior['request_sha256'] != digest or prior['status'] != 'complete':
            raise ValueError('Prior paid attempt needs reconciliation; no automatic retry.')
        return prior
    request_path = destination.with_suffix('.request.json')
    if request_path.exists():
        raise ValueError('Prior reservation exists; no repeated payment.')
    from .cost_ledger import claude_cost_usd
    text_tokens = (len(prompt.encode()) + sum(len(c.encode()) for c, _ in images)) / 2 + 500
    image_tokens = sum(r['px'][0] * r['px'][1] / 600 + 500 for r in inputs)
    estimate = float(claude_cost_usd(calls.MODEL, text_tokens + image_tokens, max_tokens)) * 1.1
    if estimate > ceiling:
        raise ValueError(f'Conservative estimate ${estimate:.6f} exceeds ${ceiling:.2f}.')
    identifier = spend.reserve('anthropic', prefix + operation, calls.MODEL, estimate, digest,
                               budget_prefix=prefix, prefix_cap=scope_cap,
                               count_prefix=prefix + operation, count_cap=1)
    calls.write(request_path, dict(identity, request_sha256=digest, reservation_id=identifier,
                                  reserved_usd=estimate, ceiling_usd=ceiling))
    if client is None:
        import anthropic
        from django.conf import settings
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, max_retries=0, timeout=300)
    try:
        response = client.messages.create(**request)
    except Exception as exc:
        status = spend.rejected_status(exc)
        if status is not None:
            spend.release_rejected(identifier, status, exc)
        calls.write(destination, {'status': 'provider_error', 'request_sha256': digest,
                                 'reservation_id': identifier, 'http_status': status,
                                 'error_type': type(exc).__name__})
        raise
    raw = response.model_dump(mode='json')
    raw_path = destination.with_suffix('.response.json')
    calls.write(raw_path, raw)
    spend.settle(identifier, raw, raw_path, provider='anthropic', model=calls.MODEL)
    text = ''.join(b.get('text', '') for b in raw['content'] if b.get('type') == 'text')
    try:
        payload = calls.parse_response_text(text)
    except (ValueError, TypeError):
        payload = None
    with spend._connect() as db:
        billing = dict(db.execute('SELECT state, accounted, reserved FROM calls WHERE id=?', (identifier,)).fetchone())
    record = dict(identity, request_sha256=digest, reservation_id=identifier,
                  status='complete' if payload is not None and raw.get('stop_reason') == 'end_turn' else 'incomplete',
                  payload=payload, stop_reason=raw.get('stop_reason'), usage=raw.get('usage'),
                  billing_state=billing['state'], cost_usd=billing['accounted'] / 1e6,
                  reserved_usd=billing['reserved'] / 1e6, response_file=str(raw_path.relative_to(REPO)))
    calls.write(destination, record)
    calls.append(OUT / 'calls.jsonl', dict(record, operation=operation))
    if record['status'] != 'complete':
        raise ValueError('Incomplete response retained; no verdict claimed.')
    return record


def comparisons():
    """Page-only pair crops, each pair at exactly one common physical scale."""
    crop = json.loads((SOURCE / 'crop.json').read_text())['panels']
    folder = OUT / 'comparison'
    folder.mkdir(exist_ok=True)
    rows = []
    for panel in PANELS:
        mm = crop[panel]['mm']
        px = tuple(round(v * 5) for v in mm)
        pair = Image.new('RGB', (px[0] * 2 + 30, px[1] + 25), 'white')
        for n, path in enumerate((SOURCE / f'{panel}.png', OUT / 'panels' / f'{panel}-flat.png')):
            with Image.open(path) as im:
                pair.paste(im.convert('RGB').resize(px, Image.Resampling.LANCZOS), (n * (px[0] + 30), 25))
        d = ImageDraw.Draw(pair)
        d.text((0, 0), panel + ' / source', fill='black')
        d.text((px[0] + 30, 0), 'master', fill='black')
        path = folder / (panel + '.png')
        pair.save(path)
        rows.append((panel + ': source left; master right; same physical scale.', path))
    calls.write(folder / 'scale.json', {'px_per_mm': 5, 'panels': crop,
                                      'purpose': 'page and eye comparison only; never a print sheet'})
    return rows


def eye(round_no=0):
    if round_no not in (0, 1):
        raise ValueError('At most two looks.')
    differences = json.loads((OUT / 'allowed-differences.json').read_text())
    images = comparisons() + [('Closed product: front and three-quarter; deterministic drawing, not a render.', OUT / 'drawing.png')]
    archive = OUT / 'eye-inputs' / f'r{round_no}'
    archive.mkdir(parents=True, exist_ok=True)
    retained_images = []
    for caption, source in images:
        destination = archive / source.name
        data = source.read_bytes()
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError('A retained eye input cannot be replaced; use the authorized next look.')
        destination.write_bytes(data)
        retained_images.append((caption, destination))
    images = retained_images
    prompt = '''You are the designer's eye. This is one whole lip balm object: nine master panels beside their pinned sketch crops and its product drawing. The owner's pick is the design. Process colour only. Judge fidelity, not taste; no scores and no jury. The cap word is a traced vector with a spurious 1 removed; small text is live; the regulated draft is live on the back; edge extension bleed and 2 mm seam feathering are allowed; black fork rectangles and guide/mask edges may be cleaned. The owner subsequently identified two side-fragment rectangular interruptions as mistakes and explicitly directed their repair before finalization (D-R1B-7). Those two local areas now recover continuous existing paint from the retained raw image, with no invented strokes; treat this as authorized cleaning. All other fragmented/repeated/interrupted Arabic strokes remain painting and MUST survive. Report every visible difference as allowed or defect. Classify defects as type, cleaning, bleed, seam, or design. Be concise: group authorized changes by panel and give each real defect its own finding. Only the first four classes permit ONE zero-cost repair; design findings are listed and the master stands. Acknowledge physical copy overflow if visible. Answer JSON only: {"verdict":"pass|fail", "idea_survives":true, "findings":[{"panel":"...","class":"type|cleaning|bleed|seam|design","status":"allowed|defect","finding":"...","repair":"... or none"}],"whole_object":"..."}. Allowed difference record follows:\n''' + json.dumps(differences, ensure_ascii=False)
    if round_no == 1:
        assessment = json.loads((OUT / 'eye-assessment.json').read_text())
        prompt += '\nThis is the single second look after the bounded repair. The original owner explicitly requires the cap mark and tint and the label tint, even though the sketch omits them. Removing those would violate the owner instructions. The two actual type repairs restore the Arabic batch label and the front separator rule. Read the owner-scope assessment below, assess the final object independently, and retain any remaining real defects rather than assuming a pass:\n' + json.dumps(assessment, ensure_ascii=False)
    record = paid_text(f'eye-r{round_no}', prompt, images, ceiling=.17, max_tokens=4000)
    calls.write(OUT / f'eye-r{round_no}.json', record)
    return record


def readings():
    """The creativity_check.py ten-word question, blind independent calls."""
    mapping = json.loads((OUT / 'reading-map.json').read_text())
    records = {}
    for label in ('K1', 'K2'):
        path = REPO / mapping['labels'][label]['path']
        if calls.sha(path) != mapping['labels'][label]['sha256']:
            raise ValueError('Blind input changed after the mapping was committed.')
        record = paid_text('reading-' + label,
            'Describe the packaging idea a stranger sees in exactly ten whitespace-delimited words. '
            'Count the ten words before answering; use plain spaces and no hyphenated compounds. '
            'No scores, approval or ranking. Return JSON only: {"idea_in_ten_words":"..."}.',
            [(label + ': nine panels of one lip balm object.', path)], ceiling=.06, max_tokens=600)
        reading = record['payload']['idea_in_ten_words']
        records[label] = {'reading': reading, 'words': len(reading.split()),
                          'exactly_ten': len(reading.split()) == 10,
                          'call': str((OUT / 'calls' / ('reading-' + label + '.json')).relative_to(REPO))}
    result = {'schema': 'hayat_blind_readings/1', 'method': 'creativity_check.py idea_in_ten_words, independent blind messages',
              'labels': records, 'map': mapping, 'gates_nothing': True}
    calls.write(OUT / 'readings.json', result)
    return result


def completion_inputs():
    """D-R1C-3: retain the same difference list and archive the corrected object."""
    differences = (OUT / 'allowed-differences.json').read_text()
    images = comparisons() + [
        ('Closed product: front and three-quarter; deterministic drawing.', OUT / 'drawing.png'),
        ('Leaflet: no sketch — regulated copy; full unfolded print flat.', OUT / 'leaflet-flat.png'),
    ]
    archive = OUT / 'eye-inputs/r2'
    archive.mkdir(parents=True, exist_ok=True)
    retained = []
    for caption, source in images:
        target = archive / source.name
        data = source.read_bytes()
        if target.exists() and target.read_bytes() != data:
            raise ValueError('A retained completion input cannot be replaced.')
        target.write_bytes(data)
        retained.append((caption, target))
    prompt = '''Complete the designer-eye review of this whole lip balm object. Judge fidelity to the owner's picked sketch, not taste; no scores or jury. The prior second reply was truncated and has no final verdict. This is its sole authorized completion (D-R1C-3); no design repair follows. Evaluate the current nine source/master pairs, drawing, and leaflet independently.
Keep every real defect; concise findings, one per defect, and group authorized changes by panel. Required cap mark/tint and label tint must remain even where absent from the sketch. The Arabic batch label and front separator were restored before this look.
The SAME allowed-difference record follows unchanged; the newer owner instructions below explicitly supersede its back-copy provision:
''' + differences + '''
D-R1C-1/2 authorize file corrections only: the carton back now carries short EN/ES/AR product, net, see-leaflet, batch, EAN frame and INCI-placeholder copy. Full drafts, warnings and claims marked "owner to confirm" move to a new folded leaflet (no sketch), live at least 6pt. Correct safe margins and Latin words in Arabic using DM Sans; Arabic remains Almarai. No plate, fragment or other design changes are authorized. D-R1C-4 lists the existing body tint/alif height, cap/label contrast and source resolution; do not assume they passed.
Return one complete JSON object, no markdown: {"verdict":"pass|fail","idea_survives":true,"findings":[{"panel":"...","class":"type|cleaning|bleed|seam|design","status":"allowed|defect","finding":"...","repair":"none — closeout record"}],"whole_object":"..."}. Keep prose under 1800 words so the complete object fits. A fail is an acceptable recorded result; do not conceal findings to pass.'''
    return prompt, retained


def complete_eye(*, client=None, max_tokens=6400):
    """One newly authorized completion, at most $0.20 within the $1 close scope."""
    if not 4000 < max_tokens <= 8000:
        raise ValueError('Completion reply budget must exceed 4000 and be at most 8000 tokens.')
    prompt, images = completion_inputs()
    record = _paid_text('eye-r2', prompt, images, ceiling=.20, max_tokens=max_tokens,
                        client=client, prefix=CLOSE_PREFIX, scope_cap=1)
    payload = record['payload']
    if (not isinstance(payload, dict) or payload.get('verdict') not in ('pass', 'fail')
            or not isinstance(payload.get('idea_survives'), bool)
            or not isinstance(payload.get('findings'), list)
            or not isinstance(payload.get('whole_object'), str)):
        raise ValueError('Completion response lacks the required final verdict schema; raw reply retained.')
    for finding in payload['findings']:
        if (not isinstance(finding, dict)
                or set(('panel', 'class', 'status', 'finding', 'repair')) - set(finding)
                or finding['class'] not in ('type', 'cleaning', 'bleed', 'seam', 'design')
                or finding['status'] not in ('allowed', 'defect')):
            raise ValueError('Completion response has an invalid finding; raw reply retained.')
    record.update(authority='D-R1C-3', completes='eye-r1.json', final_verdict_available=True,
                  final_action='Record the verdict and findings; no design repair follows.')
    calls.write(OUT / 'eye-r2.json', record)
    return record


def audit_close():
    """Retain Round 1B's audit and write this closeout's separate ledger evidence."""
    from datetime import datetime
    import subprocess
    from zoneinfo import ZoneInfo
    from apps.pipeline.models import ApiCallRecord

    zone = ZoneInfo('Asia/Shanghai')
    start = datetime.fromisoformat(subprocess.check_output(
        ['git', 'show', '-s', '--format=%cI', '32518e4'], cwd=REPO, text=True).strip()).astimezone(zone)
    end = datetime.now(zone)
    with spend._connect() as db:
        journal = [dict(row) for row in db.execute('SELECT * FROM calls ORDER BY started_at')]
    scoped = [row for row in journal if row['operation'].startswith(CLOSE_PREFIX)]
    window = [row for row in journal if start <= datetime.fromisoformat(row['started_at']) <= end]
    app_rows = list(ApiCallRecord.objects.filter(created_at__gte=start, created_at__lte=end)
                    .values('id', 'provider', 'model', 'operation', 'image_count', 'created_at'))

    def counts(rows):
        images = [row for row in rows if (
            row.get('image_count', 0) > 0
            or any(term in row['model'].lower() for term in ('gpt-image', 'dall-e', 'imagen', 'flux', 'stable-diffusion'))
            or any(term in row['operation'].lower() for term in ('/image/', 'image_generation', 'image_edit'))
            or row['provider'] in ('replicate', 'higgsfield', 'stability', 'fal'))]
        other = [row for row in rows if not (
            row['provider'] == 'anthropic' and row['operation'] == CLOSE_PREFIX + 'eye-r2')]
        return {'calls': len(rows), 'image_attempts': len(images), 'other_than_completion': len(other)}

    result = {'schema': 'hayat_close_spend/1', 'authority': 'D-R1C-3', 'scope': CLOSE_PREFIX,
              'cap_usd': 1, 'single_completion_cap_usd': .20, 'calls': scoped,
              'cost_usd': sum(row['accounted'] for row in scoped) / 1e6,
              'unresolved': [row['id'] for row in scoped if row['state'] not in ('usage_recorded', 'rejected_unbilled')],
              'window': {'from_inclusive': start.isoformat(), 'through_inclusive': end.isoformat(),
                         'start_authority': 'Owner-ruling commit 32518e4; no paid work preceded it in this closeout.'},
              'reservation_journal': counts(window), 'application_api_ledger': counts(app_rows),
              'pricing': 'Repository tariff applied to retained provider usage; not an invoice.',
              'limit': 'These ledgers do not establish absence of calls outside repository mechanisms.'}
    calls.write(OUT / 'spend-close.json', result)
    return result


def audit(*, as_of=None):
    """Read both ledgers across all prefixes, separating the day from this session.

    The entry commit time is a conservative lower bound, earlier than the
    master session. Earlier same-day work is counted without attributing it to
    this session. Ledger absence is not proof about activity outside the app.
    """
    from datetime import datetime, time
    import subprocess
    from zoneinfo import ZoneInfo
    from apps.pipeline.models import ApiCallRecord

    entry = json.loads((OUT / 'entry.json').read_text())
    zone = ZoneInfo(entry['timezone'])
    end = as_of or datetime.now(zone)
    if end.tzinfo is None:
        raise ValueError('Audit end needs an explicit timezone.')
    end = end.astimezone(zone)
    anchor = subprocess.check_output(['git', 'show', '-s', '--format=%cI', entry['entry_commit']],
                                     cwd=REPO, text=True).strip()
    start = datetime.fromisoformat(anchor).astimezone(zone)
    if start > end:
        raise ValueError('Audit end predates the entry commit.')
    day_start = datetime.combine(end.date(), time.min, zone)
    with spend._connect() as db:
        journal = [dict(r) for r in db.execute('SELECT * FROM calls ORDER BY started_at')]
    rows = [r for r in journal if r['operation'].startswith(PREFIX)]

    def image_attempt(row):
        model, operation = row['model'].lower(), row['operation'].lower()
        return (row.get('image_count', 0) > 0
                or any(token in model for token in ('gpt-image', 'dall-e', 'imagen', 'flux', 'stable-diffusion'))
                or any(token in operation for token in ('/image/', 'image_generation', 'image_edit'))
                or row['provider'] in ('replicate', 'higgsfield', 'stability', 'fal'))

    def allowed(row):
        return row['provider'] == 'anthropic' and row['operation'] in {PREFIX + name for name in OPERATIONS}

    def summarise(selected):
        images = [r for r in selected if image_attempt(r)]
        return {'calls': len(selected), 'image_attempts': len(images),
                'image_records': [{key: r[key] for key in ('id', 'provider', 'model', 'operation', 'started_at')}
                                  for r in images],
                'other_than_authorized_eye_or_readings': sum(not allowed(r) for r in selected)}

    # Fail on malformed timestamps rather than silently claiming a clean window.
    stamped = [(datetime.fromisoformat(r['started_at']), r) for r in journal]
    if any(stamp.tzinfo is None for stamp, _ in stamped):
        raise ValueError('Reservation journal has a timestamp without a timezone.')
    app_rows = list(ApiCallRecord.objects.filter(created_at__gte=min(start, day_start), created_at__lte=end)
                    .values('id', 'provider', 'model', 'operation', 'image_count', 'created_at'))
    for row in app_rows:
        row['started_at'] = row.pop('created_at').isoformat()
    windows = {}
    for name, lower in (('session', start), ('calendar_day', day_start)):
        reservation = summarise([r for stamp, r in stamped if lower <= stamp <= end])
        application = summarise([r for r in app_rows if lower <= datetime.fromisoformat(r['started_at']) <= end])
        windows[name] = {'from_inclusive': lower.isoformat(), 'through_inclusive': end.isoformat(),
                         'reservation_journal': reservation, 'application_api_ledger': application,
                         'zero_image_attempts_in_both_ledgers': reservation['image_attempts'] == application['image_attempts'] == 0,
                         'only_eye_and_readings_in_both_ledgers': reservation['other_than_authorized_eye_or_readings'] == application['other_than_authorized_eye_or_readings'] == 0}
    call_audit = {'schema': 'hayat_call_audit/1', 'timezone': entry['timezone'],
                  'session_lower_bound': {'source': 'entry commit committer timestamp',
                                          'commit': entry['entry_commit'], 'conservative': True},
                  **windows,
                  'method': 'Read-only audit of all operation prefixes in the reservation journal and application ApiCallRecord; attempts include failed and rejected calls. Counts remain separate to avoid double counting.',
                  'limit': 'These application ledgers do not prove absence of calls made outside the repository mechanisms.'}
    result = {'schema': 'hayat_spend/1', 'scope': PREFIX, 'cap_usd': 3, 'calls': rows,
              'cost_usd': sum(r['accounted'] for r in rows) / 1e6,
              'image_calls': sum(image_attempt(r) for r in rows),
              'only_eye_and_readings': all(allowed(r) for r in rows),
              'unresolved': [r['id'] for r in rows if r['state'] not in ('usage_recorded', 'rejected_unbilled')],
              'pricing': 'Repository tariff applied to retained provider usage; not an invoice.',
              'call_audit': call_audit}
    calls.write(OUT / 'audit.json', call_audit)
    calls.write(OUT / 'spend.json', result)
    return result
