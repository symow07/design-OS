"""Worker-written close report and input audit; no provider or manual round step."""
import hashlib
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys

from django.conf import settings

from . import round_calls as image_guard, spend_reservation
from .round_calls import image_call_limit, scoped_spend
from .round_flow import REPAIR_ARCHIVE, REPAIR_ID, REPO, repair_authorization, round_root, write_json


def _read(path):
    return json.loads(Path(path).read_text())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _line(value):
    return ' '.join(str(value).split()).replace('|', '\\|')


def _repair_archive(context):
    """Verify the immutable generation before resolving any historical pin."""
    root = context.root.resolve()
    authorization = repair_authorization(context.round)
    archive = root/REPAIR_ARCHIVE
    history_files = {path for path in (root/'repair-history').rglob('*') if path.is_file()}
    if authorization is None:
        if history_files:
            raise ValueError('Repair history has no exact owner authorization.')
        return {}, None
    manifest_path = archive/'manifest.json'
    if (not authorization.get('prepared_at')
            or authorization.get('manifest') != REPAIR_ARCHIVE+'/manifest.json'
            or not manifest_path.is_file()
            or _sha(manifest_path) != authorization.get('manifest_sha256')):
        raise ValueError('The authorized repair manifest is missing or changed.')
    if _read(root/'repair-authorization.json') != authorization:
        raise ValueError('The saved repair authorization differs from the round.')
    manifest = _read(manifest_path)
    snapshot = {key: value for key, value in authorization.items()
                if key not in {'prepared_at', 'manifest', 'manifest_sha256'}}
    if manifest['schema'] != 'round_repair_archive/1' or manifest['authorization'] != snapshot:
        raise ValueError('The repair archive does not match its owner authorization.')
    archived, preserved = {}, set()
    for item in manifest['files']:
        relative = Path(item['original'])
        target = root/item['archived']
        if (relative.is_absolute() or '..' in relative.parts or relative == Path('.')
                or str(relative) != item['original'] or relative.parts[0] == 'repair-history'
                or item['original'] in archived
                or item['archived'] != REPAIR_ARCHIVE+'/'+item['original']
                or target.is_symlink() or not target.resolve().is_relative_to(archive)
                or not target.is_file() or _sha(target) != item['sha256']):
            raise ValueError('An archived repair artifact is missing, duplicated or changed.')
        archived[item['original']] = target
    if history_files != set(archived.values()) | {manifest_path}:
        raise ValueError('Repair history contains unmanifested or missing artifacts.')
    for item in manifest['preserved_files']:
        relative = Path(item['original'])
        source = root/relative
        if (relative.is_absolute() or '..' in relative.parts or relative == Path('.')
                or str(relative) != item['original'] or item['original'] in preserved
                or item['original'] in archived or source.is_symlink()
                or not source.resolve().is_relative_to(root)
                or not source.is_file() or _sha(source) != item['sha256']):
            raise ValueError('The preserved seeds or their paid evidence changed after repair.')
        preserved.add(item['original'])
    if 'seeds.json' not in preserved:
        raise ValueError('Repair history must pin the preserved original seeds.')
    return archived, {'id': REPAIR_ID, 'manifest': authorization['manifest'],
                      'manifest_sha256': authorization['manifest_sha256'],
                      'archived_files': len(archived), 'preserved_files': len(preserved)}


def image_audit(context):
    """Every reserved image attempt, including archived failed attempts, is audited."""
    root = context.root.resolve()
    prefix = context.prefix
    archived, repair = _repair_archive(context)
    original_paths = {path: original for original, path in archived.items()}
    active_generation = REPAIR_ID if repair else 'original'
    limit = image_call_limit(context.round)
    with spend_reservation._connect() as db:
        rows = [dict(row) for row in db.execute(
            'SELECT * FROM calls WHERE substr(operation,1,?)=?', (len(prefix), prefix))]
    image_rows = {row['id']: row for row in rows if row['provider'] == 'openai'}
    requests, completed, outcome_paths = {}, {}, set()
    approved_path, approved_sha = image_guard.APPROVED_LOGO
    approved = Path(approved_path).resolve()
    inspected = []
    for path in sorted(root.rglob('image-call.request.json')):
        historical = path in original_paths
        generation = 'original' if historical else active_generation
        request = _read(path)
        ident = request['reservation_id']
        if ident in requests or ident not in image_rows:
            raise ValueError('An image reservation is duplicated or absent from the ledger.')
        requests[ident] = request
        row = image_rows[ident]
        identity = {key: request[key] for key in ('model', 'quality', 'size', 'prompt', 'inputs', 'mask')}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        if digest != request['request_sha256'] or digest != row['request_hash']:
            raise ValueError('Image request identity does not match its pre-call reservation.')
        operation = row['operation'][len(prefix):]
        match = re.fullmatch(r'image/([ABCD][1-5])(?:/([AB]))?', operation)
        if match is None or request['model'] != 'gpt-image-2' or request['quality'] != 'high':
            raise ValueError('Image audit found an unauthorized operation or model.')
        parent, fork = match.groups()
        target = root/'sketches'/parent/'picture.png' if fork else root/'sheet.png'
        expected = [target, approved] + ([root/'sheet.png'] if fork else [])
        expected_mask = root/'developments'/parent/'fragment-mask.png' if fork else root/'sheet-mask.png'
        inputs = request['inputs']
        if [Path(item['path']).resolve() for item in inputs] != expected:
            raise ValueError('Image audit found an input outside the sheet, logo and own fork parent.')
        if Path(request['mask']['path']).resolve() != expected_mask:
            raise ValueError('Image audit found an unauthorized mask.')
        for item in inputs + [request['mask']]:
            source = Path(item['path']).resolve()
            if source != approved and not source.is_relative_to(root):
                raise ValueError('Image input escaped this round.')
            if historical and source != approved:
                original = str(source.relative_to(root))
                if original not in archived:
                    raise ValueError('A historical image input is missing from the repair manifest.')
                source = archived[original]
            if _sha(source) != item['sha256']:
                raise ValueError('An image input pin changed after its call.')
        if _sha(approved) != approved_sha:
            raise ValueError('Approved logo pin changed.')
        outcome_path = path.with_name('image-call.json')
        outcome_status = 'rejected_unbilled'
        if outcome_path.exists():
            outcome_paths.add(outcome_path)
            outcome = _read(outcome_path)
            if outcome['reservation_id'] != ident or outcome['request_sha256'] != digest:
                raise ValueError('Image call outcome does not match its request and reservation.')
            if any(outcome[key] != identity[key] for key in identity):
                raise ValueError('Image call outcome identity differs from its reserved request.')
            outcome_status = outcome['status']
            if outcome_status not in ('complete', 'validation_failed'):
                raise ValueError('Image call outcome has no recognized completed or failed status.')
            if outcome_status == 'complete':
                completed[ident] = {'record': outcome, 'operation': operation,
                                    'generation': generation,
                                    'path': original_paths[outcome_path] if historical else str(outcome_path.relative_to(root))}
            elif not outcome.get('validation_error'):
                raise ValueError('A failed image outcome must retain its validation reason.')
        elif row['state'] != 'rejected_unbilled':
            raise ValueError('A paid image attempt is missing its durable outcome record.')
        inspected.append({'operation': operation, 'reservation_id': ident,
                          'generation': generation,
                          'request': str(path.relative_to(root)), 'billing_state': row['state'],
                          'outcome_status': outcome_status,
                          'inputs_match': True, 'accounted_usd': row['accounted']/1e6})
    if set(requests) != set(image_rows) or len(image_rows) > limit:
        raise ValueError(f'Image attempt audit does not reconcile with the {limit}-call ledger limit.')
    if set(root.rglob('image-call.json')) != outcome_paths:
        raise ValueError('An image call outcome has no corresponding request and reservation.')
    log = root/'image-calls.jsonl'
    successful = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    ids = [row['reservation_id'] for row in successful]
    if len(ids) != len(set(ids)) or set(ids) != set(completed):
        raise ValueError('The paid image journal is duplicated or incomplete.')
    for item in successful:
        ident = item['reservation_id']
        finished = completed[ident]
        outcome = finished['record']
        request = requests[ident]
        if item['status'] != 'complete' or item['operation'] != finished['operation'] or item['payload_file'] != finished['path']:
            raise ValueError('Image journal operation or outcome pointer does not match the completed call.')
        if item['request_sha256'] != request['request_sha256'] or any(item[key] != request[key] for key in ('model', 'quality', 'size', 'prompt', 'inputs', 'mask')):
            raise ValueError('Image journal identity differs from its request and reservation.')
        if item['output_sha256'] != outcome['output_sha256'] or item['billing_state'] != image_rows[ident]['state'] or item['accounted_usd'] != image_rows[ident]['accounted']/1e6:
            raise ValueError('Image journal output or billing differs from its completed call and ledger.')
    if len({(item['generation'], item['operation']) for item in completed.values()}) != len(successful):
        raise ValueError('The image journal contains more than one completion for an operation in a generation.')
    active = [item for item in completed.values() if item['generation'] == active_generation]
    originals = {item['operation'] for item in active if re.fullmatch(r'image/[ABCD][1-5]', item['operation'])}
    if originals != {f'image/{family}{n}' for family in 'ABCD' for n in range(1, 6)}:
        raise ValueError('Twenty completed original sketches are required in the active generation.')
    if any(row['state'] not in ('usage_recorded', 'rejected_unbilled') for row in image_rows.values()):
        raise ValueError('An image attempt has unresolved billing.')
    generations = []
    for name in (['original', REPAIR_ID] if repair else ['original']):
        attempts = [item for item in inspected if item['generation'] == name]
        edits = [item for item in completed.values() if item['generation'] == name]
        initial = sum(bool(re.fullmatch(r'image/[ABCD][1-5]', item['operation'])) for item in edits)
        generations.append({'id': name, 'active': name == active_generation,
                            'image_attempts': len(attempts), 'successful_image_edits': len(edits),
                            'originals': initial, 'forks': len(edits)-initial})
    return {'schema': 'round_image_input_audit/1', 'passes': True,
            'paid_image_attempts': len(image_rows), 'successful_image_edits': len(successful),
            'originals': 20, 'forks': len(active)-20, 'limit': limit,
            'active_generation': active_generation, 'generations': generations, 'repair': repair,
            'allowed_inputs': 'Engine sheet, its mask, approved logo; own parent and fragment mask for a fork.',
            'attempts': inspected}


def finalize(context, pick):
    """Called by the pick job before its artifact commit and closing tag."""
    root = context.root
    audit = image_audit(context)
    spend = scoped_spend(context.round)
    if spend['reserved_usd'] or spend['accounted_usd'] > float(context.round.budget_usd):
        raise ValueError('Round spend must be settled within its budget before close.')
    write_json(root/'image-input-audit.json', audit)
    write_json(root/'spend.json', spend)
    seeds = _read(root/'seeds.json')['seeds']
    eligibility = _read(root/'eligibility.json')
    cut = _read(root/'cut.json')['order']
    marks = _read(root/'marks.json')
    forks = _read(root/'forks.json')
    final = _read(root/'final-order.json')
    publication = _read(root/'publication.json')
    selected = publication['candidates'][pick['id']]
    write_json(root/'handoff.json', {'schema': 'round_day_two_handoff/1', 'pick': pick,
        'candidate': selected, 'day_two_started': False,
        'detail_pass': {'after_pick': True, 'source': 'Each own panel crop plus its mask at full sheet resolution.',
                        'delta_e00_mean_max': 1.5, 'ssim_min': .97, 'otherwise': 'Retain the 2× plate.'}})
    jobs = list(context.round.steps.order_by('position'))
    breaks = [{'step': job.name, **event} for job in jobs for event in job.history
              if event.get('kind') != 'owner_repair']
    untouched = [job.name for job in jobs if not job.history and job.attempts == 0]
    probe = root/'probe.md'
    gaps = [line[2:] for line in probe.read_text().splitlines() if line.startswith('- ')] if probe.exists() else []
    breaks_path = root/'BREAKS.md'
    if not breaks_path.exists():
        breaks_path.write_text('# Round breaks\n\nWorker failure evidence is retained under `failures/`; fixes and their commits are appended here.\n\n')
    if breaks:
        existing = breaks_path.read_text()
        with breaks_path.open('a') as stream:
            for event in breaks:
                marker = f'<!-- worker-failure:{event["step"]}:{event["at"]} -->'
                if marker not in existing:
                    stream.write(f'\n{marker}\n- {_line(event["step"])}: {_line(event["error"])}. Fix/commit: see appended builder record.\n')
    build_steps = re.findall(r'^\|\s*B\d+\s*\|\s*([^|]+?)\s*\|', breaks_path.read_text(), re.MULTILINE)
    checked = {**eligibility['results'], **forks['results']}
    disqualified = [key+': '+', '.join(row['reasons']) for key, row in checked.items() if not row['eligible']]
    lines = [f'# {_line(context.brief["name"])} — app round', '',
        '**The system test**',
        f'Probe: {len(gaps)} gaps recorded in [probe.md](probe.md).' if probe.exists() else 'Probe: no probe record supplied for this round.',
        'Built: product briefs and panel sheets; queued durable jobs; spend reservations and one bounded text retry; owner marks, timed fallback, app retry and pick.',
        f'Build findings: {len(build_steps)}; steps: '+(', '.join(sorted({_line(step) for step in build_steps})) if build_steps else 'none')+'. See [BREAKS.md](BREAKS.md).',
        f'Runtime breaks: {len(breaks)}; steps: '+(', '.join(sorted({row['step'] for row in breaks})) if breaks else 'none')+'. See [BREAKS.md](BREAKS.md).',
        f'Steps requiring no repair/requeue: {len(untouched)}/{len(jobs)}. Worker deliveries resume saved results; no step was run by hand.',
        'Fixture verification and full-suite evidence are in [evidence/](evidence/); this report is written by the worker after the owner pick.']
    lines += ['- Probe gap: '+_line(gap) for gap in gaps]
    lines += ['', '**The round**', 'Twenty seeds and product-truth links:']
    lines += [f'- {row["id"]}: {_line(row["seed"])} — {_line(row["link"])}' for row in seeds]
    lines += ['Disqualified: '+('; '.join(_line(value) for value in disqualified) if disqualified else 'none')+'.',
        'Coarse shortlist: '+', '.join(_read(root/'jury/coarse/result.json')['shortlist'])+'.',
        'Eight for marks: '+', '.join(cut)+'.',
        'Marks source: '+_line(marks['source']['kind'])+'.']
    lines += ['- '+row['id']+': '+_line(row['preserve']) for row in marks['marks']]
    lines += ['Forks: '+', '.join(forks['candidates'])+'.',
        'Final pool: '+', '.join(final['pool'])+'. '+_line(final['pool_rule']),
        'Final order: '+', '.join(final['full_order'])+'.',
        f'Candidates shown ({len(final["order"])}): '+', '.join(final['order'])+'.',
        'Owner pick: **'+_line(pick['id'])+'** — '+_line(pick['reason']),
        'Optional day-two merge: '+(_line(pick['merge']) if pick['merge'] else 'none')+'.',
        f'Spend: ${spend["actual_usd"]:.6f} of ${float(context.round.budget_usd):.2f}; outstanding holds ${spend["reserved_usd"]:.6f}.',
        f'Image audit: {audit["paid_image_attempts"]} attempts, {audit["successful_image_edits"]} completed edits; allowed input pins pass; limit {audit["limit"]}.',
        'No scores, caps or anchors; purchase appeal is recorded separately. All comparisons and readings remain in their original records.',
        'Day two remains separate: own-crop detail edits require ΔE00 mean ≤1.5 and SSIM ≥0.97, otherwise the 2× plate stays.',
        'Round 1 files and pages remain preserved; its closeout stays open.']
    if audit['repair']:
        historical, active = audit['generations']
        lines.insert(-3, f'Owner repair: original {historical["image_attempts"]} image attempts and {historical["successful_image_edits"]} completed edits remain pinned in [{REPAIR_ID}]({audit["repair"]["manifest"]}); active generation {active["image_attempts"]} attempts and {active["successful_image_edits"]} completed edits; original seeds and append-only paid journals retained.')
    if len(lines) > 80:
        raise ValueError('Round report exceeds the owner’s 80-line limit.')
    (root/'README.md').write_text('\n'.join(lines)+'\n')
    return {'image_audit': audit, 'spend': spend, 'report_lines': len(lines)}


def tag_if_requested(record):
    """Only this owner's named Round 2 tag is authorized; fixtures never tag."""
    if 'pytest' in sys.modules or not getattr(settings, 'ROUND_COMMIT_ARTIFACTS', True):
        return
    if record.slug != 'r2-gloss' or record.state != 'complete' or not record.pick:
        return
    with (REPO / '.git/round-artifacts.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _tag_locked(record)


def _tag_locked(record):
    """The same Git lock covers artifact commits and the check/create pair."""
    root = round_root(record)
    if not _read(root/'image-input-audit.json')['passes']:
        raise ValueError('The round image audit has not passed.')
    tag = 'round-2-gloss-a'
    found = subprocess.run(['git', 'show', f'{tag}:{root.relative_to(REPO)}/pick.json'],
                           cwd=REPO, capture_output=True, text=True)
    if found.returncode == 0:
        if json.loads(found.stdout) != record.pick:
            raise ValueError('The closing tag already belongs to a different pick; it will not move.')
        return
    exists = subprocess.run(['git', 'rev-parse', '--verify', 'refs/tags/'+tag], cwd=REPO, capture_output=True)
    if exists.returncode == 0:
        raise ValueError('The closing tag exists without this pick; it will not move.')
    subprocess.run(['git', 'tag', '-a', tag, '-m', 'Round 2 lip gloss: owner app pick recorded; input audit passed'],
                   cwd=REPO, check=True, capture_output=True)
