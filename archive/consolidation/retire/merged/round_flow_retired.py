"""round_flow's retired kinds, archived by the owner's goal of 2026-10-29 ("Retire the history pages (Round 1/1B/1C/2,
Day 4–6 masters)"): the twenty-design kind (Round 2, round_ideas) and the whole-object kind (Rounds 1 and 2:
round_steps, round_sheet, round_product, round_report, the r2-gloss repair, the marks and their deadline).

Each block below is copied whole from bbrose_design_os/apps/pipeline/services/round_flow.py as it stood at 49ac763
(lines given). The first group left round_flow entirely; the second is the original text of the functions that
stayed, rewritten for the designer kind alone. Kept as text, not imported by anything."""

# ---- removed from round_flow ----

# round_flow.py:25-26
STEPS = ('seeds', 'sheet', 'sketches', 'checks', 'readings', 'coarse', 'pairwise',
         'marks', 'forks', 'final_pairwise', 'pick_page', 'pick')


# round_flow.py:27-27
REPAIR_ID = 'gloss-panel-material-v2'


# round_flow.py:28-28
REPAIR_ARCHIVE = 'repair-history/' + REPAIR_ID


# round_flow.py:31-34
def is_ideas_round(record):
    """Only the stored new-intake schema selects the ideas-only workflow."""
    from .round_designer import is_ideas_brief
    return is_ideas_brief(record.product_brief)


# round_flow.py:53-65
def repair_authorization(record):
    """Only the owner's one named repair adds twenty replacement image attempts."""
    authorization = getattr(record, 'artifacts', {}).get('repair_authorization')
    if (record.slug == 'r2-gloss' and isinstance(authorization, dict)
            and authorization.get('id') == REPAIR_ID
            and authorization.get('additional_image_attempts') == 20
            and authorization.get('image_attempt_limit') == 46
            and authorization.get('budget_usd') == 25
            and authorization.get('source') == 'owner app retry'
            and isinstance(authorization.get('user_id'), int)
            and authorization.get('authorized_at')):
        return authorization
    return None


# round_flow.py:68-80
def repair_plan(record):
    """Preview the authorized repair without changing state or writing artifacts."""
    from .round_sheet import needs_repair
    if (record.slug != 'r2-gloss' or record.state != 'failed'
            or 'repair_authorization' in record.artifacts
            or record.current_step not in STEPS[2:]
            or 'seeds' not in record.artifacts or 'sheet' not in record.artifacts
            or record.artifacts['sheet'].get('schema') != 'round_sheet/1'):
        return None
    if not needs_repair(record.artifacts['sheet'], record.product_brief):
        return None
    return {'id': REPAIR_ID, 'restart_step': 'sketches', 'budget_usd': 25,
            'additional_image_attempts': 20, 'image_attempt_limit': 46}


# round_flow.py:173-183
def _schedule_marks(round_id, deadline):
    from apps.pipeline.tasks import round_marks_deadline
    # Eager tests explicitly drive their clock; eager execution must not collapse 60 minutes.
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return
    try:
        round_marks_deadline.apply_async(args=[round_id], eta=deadline)
    except Exception as exc:
        reason = f'Marks timer delivery failed: {type(exc).__name__}: {exc}'
        job = RoundStep.objects.get(round_id=round_id, name='marks')
        _dispatch_failure(job.pk, reason, 'marks_timer_delivery', 'waiting')


# round_flow.py:338-350
def _repair_path(root, relative):
    """Manifest paths are canonical relative paths without any symlink component."""
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('Repair archive manifest contains an invalid artifact path.')
    parts = relative.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('Repair archive manifest contains an invalid artifact path.')
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Repair archive cannot follow a symlink.')
    return path


# round_flow.py:353-387
def _repair_moves(root, manifest, authorization):
    """Validate the entire snapshot before the first rename, including on resume."""
    if manifest['schema'] != 'round_repair_archive/1' or manifest['authorization'] != authorization:
        raise ValueError('Repair archive belongs to another authorization.')
    seen, moves = set(), []
    brief_checked = False
    for item in manifest['files']:
        original = item['original']
        if original in seen or item['archived'] != REPAIR_ARCHIVE + '/' + original:
            raise ValueError('Repair archive paths are duplicated or mapped incorrectly.')
        seen.add(original)
        source = _repair_path(root, original)
        destination = _repair_path(root, item['archived'])
        retained = source
        if destination.exists():
            retained = destination
        else:
            moves.append((source, destination))
        if not retained.is_file() or hashlib.sha256(retained.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('An original or archived repair artifact changed.')
        if original == 'brief.json':
            if json.loads(retained.read_text()) != authorization['original_brief']:
                raise ValueError('The archived brief differs from the authorized original brief.')
            brief_checked = True
    if not brief_checked:
        raise ValueError('Repair archive must retain the authorized original brief.')
    for item in manifest['preserved_files']:
        original = item['original']
        if original in seen:
            raise ValueError('Preserved repair evidence is duplicated or also scheduled to move.')
        seen.add(original)
        path = _repair_path(root, original)
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('The original seeds or their paid evidence changed during repair.')
    return moves


# round_flow.py:390-429
def _archive_repair(context, authorization):
    """Move the obsolete generation once, retaining every paid record verbatim."""
    root = context.root.resolve()
    if hashlib.sha256(json.dumps(authorization['original_brief'], sort_keys=True).encode()).hexdigest() != authorization['old_brief_sha256']:
        raise ValueError('The authorized original brief changed before repair.')
    manifest_path = _repair_path(root, REPAIR_ARCHIVE + '/manifest.json')
    existing = manifest_path.exists()
    if existing:
        manifest = json.loads(manifest_path.read_text())
    else:
        paths = set()
        for pattern in ('brief.json', 'sheet.*', 'sheet-*.png', 'sheet-verification.json',
                        'eligibility.json', 'forks.json', 'cut.json', 'final-order.json',
                        'publication.json', 'budget-plan.json', 'critic-calibration.json',
                        'marks.json', 'pick.json'):
            paths.update(root.glob(pattern))
        for directory in ('sketches', 'developments', 'jury'):
            paths.update(path for path in (root / directory).rglob('*') if path.is_file())
        paths.update(root / 'steps' / (step + '.json') for step in STEPS[1:]
                     if (root / 'steps' / (step + '.json')).exists())
        files = []
        for path in sorted(paths):
            relative = str(path.relative_to(root))
            path = _repair_path(root, relative)
            files.append({'original': relative, 'archived': REPAIR_ARCHIVE + '/' + relative,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        preserved = sorted(set(root.glob('seeds*.json')) | set((root / 'call-history').rglob('seeds-call.*json'))
                           | {root / 'steps' / 'seeds.json'})
        manifest = {'schema': 'round_repair_archive/1', 'authorization': authorization,
                    'files': files, 'preserved_files': [
                        {'original': str(path.relative_to(root)),
                         'sha256': hashlib.sha256(_repair_path(root, str(path.relative_to(root))).read_bytes()).hexdigest()}
                        for path in preserved if path.is_file()]}
    moves = _repair_moves(root, manifest, authorization)
    if not existing:
        write_json(manifest_path, manifest)
    for source, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
    return manifest


# round_flow.py:432-463
def _prepare_repair(context, job):
    """The first owner-requeued sketches delivery rebuilds its engine prerequisite."""
    authorization = repair_authorization(context.round)
    if job.name != 'sketches' or authorization is None or authorization.get('prepared_at'):
        return
    from .round_product import repair_missing_body_right
    from .round_sheet import build
    _archive_repair(context, authorization)
    repaired = repair_missing_body_right(authorization['original_brief'])
    context.brief = repaired
    write_json(context.root / 'brief.json', repaired)
    sheet = build(repaired, context.root)
    old_calibration = context.root / REPAIR_ARCHIVE / 'critic-calibration.json'
    if old_calibration.exists():
        calibration = json.loads(old_calibration.read_text())
        calibration.update(marks=[], picks=[], departures=[])
        write_json(context.root / 'critic-calibration.json', calibration)
    write_json(context.root / 'steps' / 'sheet.json', sheet)
    prepared = dict(authorization, prepared_at=timezone.now().isoformat(),
                    manifest=REPAIR_ARCHIVE + '/manifest.json',
                    manifest_sha256=hashlib.sha256((context.root / REPAIR_ARCHIVE / 'manifest.json').read_bytes()).hexdigest())
    write_json(context.root / 'repair-authorization.json', prepared)
    commit_artifacts(context.round, 'owner repair archived; twelve-panel sheet rebuilt')
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=context.round.pk)
        record.product_brief = repaired
        record.artifacts = dict(record.artifacts, sheet=sheet, repair_authorization=prepared)
        record.save()
        RoundStep.objects.filter(round=record, name='sheet').update(
            state='complete', result=sheet, error='', finished_at=timezone.now())
    context.round.product_brief = repaired
    context.round.artifacts = record.artifacts


# round_flow.py:581-607
def submit_marks(round_id, rows, user):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 3:
        raise ValueError('Mark one to three candidates.')
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        _owner(record, user)
        if is_ideas_round(record):
            raise ValueError('This round goes directly from its twenty designs to your pick.')
        if record.state != 'awaiting_marks':
            if record.marks and record.marks['marks'] == rows:
                transaction.on_commit(lambda: recover_dispatch(record))
                return record
            raise ValueError('The round is not waiting for marks.')
        order = record.artifacts['pairwise']['order']
        ids = [r['id'] for r in rows]
        if len(set(ids)) != len(ids) or any(k not in order for k in ids):
            raise ValueError('Marks must name distinct displayed candidates.')
        if any(not isinstance(r.get('preserve'), str) or not r['preserve'].strip() or '\n' in r['preserve'].strip() for r in rows):
            raise ValueError('Each mark needs one preservation line.')
        record.marks = {'marks': rows, 'source': {'kind': 'owner app', 'user_id': user.pk}, 'recorded_at': timezone.now().isoformat()}
        record.state = 'queued'
        record.save()
        job = record.steps.get(name='marks')
        job.state = 'queued'
        job.save()
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


# round_flow.py:610-626
def marks_deadline(round_id, now=None):
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        if is_ideas_round(record):
            return False
        if record.state != 'awaiting_marks' or record.marks:
            return False
        current = timezone.now() if now is None else now
        if record.marks_due_at is None or current < record.marks_due_at:
            return False
        record.state = 'queued'
        record.save()
        job = record.steps.get(name='marks')
        job.state = 'queued'
        job.save()
        transaction.on_commit(lambda: _enqueue(job.pk))
    return True


# ---- the original text of the functions rewritten for the designer kind ----

# round_flow.py:43-50
def steps_for(record):
    if is_designer_round(record):
        from .round_designer import DESIGNER_STEPS
        return DESIGNER_STEPS
    if is_ideas_round(record):
        from .round_ideas import IDEAS_STEPS
        return IDEAS_STEPS
    return STEPS


# round_flow.py:142-161
def _dispatch_failure(step_id, reason, kind, expected_state):
    """Keep broker failures in the same reportable history as worker failures."""
    identity = RoundStep.objects.only('round_id').get(pk=step_id)
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=identity.round_id)
        job = RoundStep.objects.select_for_update().get(pk=step_id)
        if job.state != expected_state or record.current_step != job.name:
            return False
        event = {'at': timezone.now().isoformat(), 'error': reason, 'attempt': job.attempts, 'kind': kind}
        if not any(item.get('kind') == kind and item['attempt'] == job.attempts for item in job.history):
            job.history = list(job.history) + [event]
        job.state = 'failed'
        job.error = reason
        job.save(update_fields=['state', 'error', 'history', 'updated_at'])
        record.state = 'failed'
        record.error_message = reason
        record.save(update_fields=['state', 'error_message', 'updated_at'])
    if is_ideas_round(record):
        _retain_failure_evidence(record, job, job.history)
    return True


# round_flow.py:186-197
def recover_dispatch(record, *, reschedule_marks=False):
    """App GET/redelivery repairs a committed outbox item whose broker publish was lost."""
    record.refresh_from_db()
    if record.state == 'queued':
        job = record.steps.filter(name=record.current_step, state='queued').first()
        if job is not None:
            _enqueue(job.pk)
    elif record.state == 'awaiting_marks' and record.marks_due_at is not None:
        if record.marks_due_at <= timezone.now():
            marks_deadline(record.pk)
        elif reschedule_marks:
            _schedule_marks(record.pk, record.marks_due_at)


# round_flow.py:200-238
def create_round(brief, user, request_key):
    from .round_product import normalize_brief
    from .round_designer import is_designer_brief, is_ideas_brief, normalize_ideas_brief
    if not user.is_authenticated:
        raise PermissionDenied('Sign in to start a round.')
    if not isinstance(request_key, str) or not 8 <= len(request_key) <= 64:
        raise ValueError('Start needs its form identity.')
    ideas = is_ideas_brief(brief)
    if ideas:
        normalized = normalize_ideas_brief(brief)
    else:
        if isinstance(brief, dict) and 'schema' in brief and brief['schema'] != 'round_product/1':
            raise ValueError('Unknown round brief schema.')
        normalized = normalize_brief(brief)
    with transaction.atomic():
        # Serialize duplicate form submissions before choosing the unique round slug.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        previous = Round.objects.filter(request_key=request_key).first()
        if previous is not None:
            _owner(previous, user)
            if previous.product_brief != normalized:
                raise ValueError('This Start identity already belongs to a different brief.')
            transaction.on_commit(lambda: recover_dispatch(previous))
            return previous
        stem = slugify(normalized['name'])[:65]
        if not stem:
            stem = 'product'
        slug = f'{stem}-{uuid.uuid4().hex[:10]}'
        if not ideas and normalized.get('product_type') == 'lip_gloss' and not Round.objects.filter(slug='r2-gloss').exists():
            slug = 'r2-gloss'
        first = 'research' if is_designer_brief(normalized) else 'seeds'
        if ideas:
            record = Round.objects.create(slug=slug, request_key=request_key, product_brief=normalized,
                                          created_by=user, budget_usd=10, current_step=first)
        else:
            record = Round.objects.create(slug=slug, request_key=request_key, product_brief=normalized, created_by=user)
        job = RoundStep.objects.create(round=record, name=first, position=0)
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


# round_flow.py:241-260
def _next_locked(record, completed):
    sequence = steps_for(record)
    index = sequence.index(completed)
    if completed == 'pick':
        record.state = 'complete'
        record.current_step = 'pick'
        record.save()
        return
    next_name = sequence[index + 1]
    waiting = next_name in ('marks', 'board_pick', 'pick')
    job, _ = RoundStep.objects.get_or_create(round=record, name=next_name,
        defaults={'position': index + 1, 'state': 'waiting' if waiting else 'queued'})
    record.current_step = next_name
    record.state = f'awaiting_{next_name}' if waiting else 'queued'
    record.error_message = ''
    if next_name == 'marks':
        record.marks_due_at = timezone.now() + timedelta(minutes=60)
        transaction.on_commit(lambda: _schedule_marks(record.pk, record.marks_due_at))
    record.save()
    return None if waiting else job.pk


# round_flow.py:282-291
def _retain_failure_evidence(record, job, history):
    """Keep secondary evidence errors separate from the already-recorded step failure."""
    if is_ideas_round(record):
        return _retain_ideas_failure(record, job, history)
    try:
        write_json(round_root(record) / 'failures' / f'{job.name}-{job.attempts}-{job.dispatches}.json', history[-1])
        commit_artifacts(record, f'{job.name} failed; evidence retained')
    except Exception as evidence_exc:
        history[-1]['evidence_error'] = f'{type(evidence_exc).__name__}: {evidence_exc}'
        RoundStep.objects.filter(pk=job.pk).update(history=history)


# round_flow.py:466-578
def run_step_job(step_id):
    """One bounded worker delivery, resumable after process loss or duplicate delivery."""
    job = RoundStep.objects.select_related('round').get(pk=step_id)
    if job.state == 'complete':
        recover_dispatch(job.round, reschedule_marks=True)
        if job.name == 'pick' and job.round.state == 'complete' and not is_ideas_round(job.round):
            from .round_report import tag_if_requested
            tag_if_requested(job.round)
        return {'status': 'complete'}
    next_step_id = None
    outcome = {'status': 'queued'}
    with _job_lock(job.round) as owned:
        if not owned:
            return {'status': 'already_running'}
        with transaction.atomic():
            job = RoundStep.objects.select_for_update().select_related('round').get(pk=step_id)
            record = Round.objects.select_for_update().get(pk=job.round_id)
            if job.state not in ('queued', 'running') or record.current_step != job.name:
                return {'status': job.state}
            if not is_ideas_round(record) and job.name == 'marks' and not record.marks:
                if record.marks_due_at is None:
                    raise ValueError('Marks have no published deadline.')
                if timezone.now() < record.marks_due_at:
                    job.state = 'waiting'
                    job.save()
                    record.state = 'awaiting_marks'
                    record.save()
                    transaction.on_commit(lambda: _schedule_marks(record.pk, record.marks_due_at))
                    return {'status': 'awaiting_marks'}
            job.state = 'running'
            job.dispatches += 1
            if job.started_at is None:
                job.started_at = timezone.now()
            job.save()
            record.state = 'running'
            record.save()
        try:
            if is_ideas_round(record):
                from .round_ideas import IdeasContext
                if is_designer_round(record):
                    from .round_designer import DesignerContext as IdeasContext, run_step, finalize_pick
                else:
                    from .round_ideas import run_step, finalize_pick
                if job.name not in steps_for(record):
                    raise ValueError('This step is outside the ideas-only workflow.')
                for prior in record.steps.all():
                    if prior.history:
                        record_break(record, prior, prior.history[-1]['error'])
                context = IdeasContext(record, job)
                context.root.mkdir(parents=True, exist_ok=True)
                write_json(context.root / 'brief.json', record.product_brief)
                if job.name == 'pick':
                    if not record.pick:
                        raise ValueError('An owner decision is required.')
                    write_json(context.root / 'pick.json', record.pick)
                    result = finalize_pick(context)
                else:
                    result = run_step(context, job.name)
            else:
                from .round_calls import RoundContext
                from .round_steps import run_step, _calibration
                context = RoundContext(record, job)
                context.root.mkdir(parents=True, exist_ok=True)
                _prepare_repair(context, job)
                write_json(context.root / 'brief.json', record.product_brief)
                context.prepare_budget_plan(job.name)
                if job.name in ('marks', 'pick'):
                    result = record.marks if job.name == 'marks' else record.pick
                    if job.name == 'marks' and not result:
                        result = run_step('marks_fallback', context)
                        result['source'] = dict(result['source'], notice_deadline=record.marks_due_at.isoformat())
                        result['recorded_at'] = timezone.now().isoformat()
                        record.marks = result
                    if not result:
                        raise ValueError('An owner decision is required.')
                    write_json(context.root / f'{job.name}.json', result)
                    if job.name == 'marks':
                        _calibration(context, marks=result)
                    else:
                        _calibration(context, picks=[result], pick_status='recorded')
                        from .round_report import finalize
                        finalize(context, result)
                else:
                    result = run_step(job.name, context)
            write_json(context.root / 'steps' / f'{job.name}.json', result)
            commit_artifacts(record, f'{job.name} complete')
            with transaction.atomic():
                current = Round.objects.select_for_update().get(pk=record.pk)
                if job.name == 'marks':
                    current.marks = result
                current.artifacts = dict(current.artifacts, **{job.name: result})
                job.state = 'complete'
                job.result = result
                job.error = ''
                job.finished_at = timezone.now()
                job.save()
                # Enqueue only after releasing the filesystem claim, including eager fixtures.
                current.save()
                next_step_id = _next_locked(current, job.name)
            if job.name == 'pick' and not is_ideas_round(current):
                from .round_report import tag_if_requested
                tag_if_requested(current)
            outcome = {'status': 'complete', 'step': job.name}
        except YieldRound:
            outcome = _continue_step(record, job)
            if outcome['status'] == 'failed':
                return outcome
            next_step_id = step_id
        except Exception as exc:
            return _record_step_failure(record, job, exc)
    if next_step_id is not None:
        _enqueue(next_step_id)
    return outcome


# round_flow.py:629-656
def submit_pick(round_id, candidate, reason, user, merge=None):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Your pick needs a reason.')
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        _owner(record, user)
        if is_ideas_round(record) and merge is not None:
            raise ValueError('Choose one original design; this round does not merge candidates.')
        if record.state != 'awaiting_pick':
            if record.pick and record.pick['id'] == candidate and record.pick['reason'] == reason.strip() and record.pick['merge'] == merge:
                transaction.on_commit(lambda: recover_dispatch(record))
                return record
            raise ValueError('The round is not waiting for a pick.')
        page = record.artifacts['pick_page']
        if candidate not in page['order']:
            raise ValueError('Pick one candidate from the final page.')
        if merge is not None:
            all_ids = set(record.artifacts['sketches']['candidates']) | set(record.artifacts['forks']['candidates'])
            if not isinstance(merge, dict) or set(merge) != {'candidate', 'element'} or merge['candidate'] == candidate or merge['candidate'] not in all_ids or not isinstance(merge['element'], str) or not merge['element'].strip():
                raise ValueError('A merge names one other candidate and one element for day two.')
        record.pick = {'id': candidate, 'reason': reason.strip(), 'merge': merge, 'source': {'kind': 'owner app', 'user_id': user.pk}, 'recorded_at': timezone.now().isoformat()}
        record.state = 'queued'
        record.save()
        job = record.steps.get(name='pick')
        job.state = 'queued'
        job.save()
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


# round_flow.py:735-770
def retry_round(round_id, user):
    with transaction.atomic():
        record = Round.objects.select_for_update().get(pk=round_id)
        _owner(record, user)
        if record.state != 'failed':
            raise ValueError('Only a failed step can be retried.')
        plan = None if is_ideas_round(record) else repair_plan(record)
        if plan is not None:
            previous_steps = list(record.steps.select_for_update().values(
                'name', 'position', 'state', 'attempts', 'dispatches', 'result', 'error', 'history'))
            authorization = dict(plan, source='owner app retry', user_id=user.pk,
                authorized_at=timezone.now().isoformat(), original_brief=record.product_brief,
                old_brief_sha256=hashlib.sha256(json.dumps(record.product_brief, sort_keys=True).encode()).hexdigest(),
                previous_artifacts=record.artifacts, previous_steps=previous_steps)
            record.artifacts = {'seeds': record.artifacts['seeds'], 'repair_authorization': authorization}
            record.budget_usd = 25
            record.current_step = 'sketches'
            record.marks, record.pick, record.marks_due_at = {}, {}, None
            for prior in record.steps.select_for_update().exclude(name='seeds'):
                prior.state = 'waiting' if prior.name in ('marks', 'pick') else 'queued'
                prior.result, prior.error = {}, ''
                prior.started_at = prior.finished_at = None
                prior.history = list(prior.history) + [{'at': authorization['authorized_at'],
                    'attempt': prior.attempts, 'kind': 'owner_repair',
                    'error': 'Owner authorized replacement sheet and sketches; original results archived.'}]
                prior.save()
        job = record.steps.select_for_update().get(name=record.current_step)
        job.state = 'queued'
        job.attempts += 1
        job.error = ''
        job.save()
        record.state = 'queued'
        record.error_message = ''
        record.save()
        transaction.on_commit(lambda: _enqueue(job.pk))
    return record


# round_flow.py:773-799
def summary(record):
    from .round_calls import scoped_spend
    if is_ideas_round(record):
        labels = {'seeds': 'Finding twenty ideas', 'designs': 'Making twenty designs',
                  'pairwise': 'Comparing every pair', 'pick_page': 'Showing the top three',
                  'pick': 'Your pick'}
        image_limit = 40
        if is_designer_round(record):
            from .round_designer import DesignerContext
            labels = {'research': 'Researching the category', 'boards': 'Making three mood boards',
                      'board_pick': 'Your board', 'designs': 'Drawing three designs',
                      'pick_page': 'Checking the designs', 'pick': 'Your pick'}
            image_limit = DesignerContext.image_attempt_cap
        saved = {row['name']: row for row in record.steps.values('name', 'state', 'attempts', 'error')}
        progress = []
        for name in steps_for(record):
            row = saved[name] if name in saved else {'name': name, 'state': 'waiting', 'attempts': 0, 'error': ''}
            progress.append(dict(row, label=labels[name]))
        spend = scoped_spend(record)
        spend['image_attempt_limit'] = image_limit
        return {'state': record.state, 'current_step': record.current_step,
                'current_step_label': labels[record.current_step], 'error': record.error_message,
                'steps': progress, 'spend': spend,
                'repair_plan': None, 'repair_authorization': None}
    return {'state': record.state, 'current_step': record.current_step, 'error': record.error_message,
            'steps': list(record.steps.values('name', 'state', 'attempts', 'error')), 'spend': scoped_spend(record),
            'repair_plan': repair_plan(record), 'repair_authorization': repair_authorization(record)}
