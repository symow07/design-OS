"""Archived with the retired picture-tracing path (docs/rounds/reuse-plan.md); moved from apps/pipeline/tests/test_round_calls.py, not collected."""

@pytest.fixture
def files_detail_case(tmp_path):
    """Fake durable context; paid-boundary tests live with AttemptContext itself."""
    import numpy as np
    from apps.pipeline.services import round_files_detail as detail
    root = tmp_path/'detail-worker'; root.mkdir()
    yy, xx = np.indices((240, 320))
    pixels = np.stack((80+xx//3, 40+yy//2, 90+(xx+yy)//5), axis=2).astype(np.uint8)
    source = root/'source.png'; Image.fromarray(pixels).save(source)
    provider = Mock()
    provider.side_effect = lambda target, size: Path(target).read_bytes()
    case = SimpleNamespace(root=root, source=source, digest=detail.sha(source),
        panels={'body_front': [10, 10, 60, 230], 'stand_header': [80, 20, 300, 120]}, provider=provider)
    def context():
        ctx = SimpleNamespace(root=root, new_calls=0)
        def image_call(operation, prompt, folder, *, target, mask, size):
            folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
            output = folder/'image-call.json'
            if output.exists():
                return json.loads(output.read_text())
            if ctx.new_calls:
                raise YieldRound()
            ctx.new_calls += 1
            identity = {'model': 'gpt-image-2', 'quality': 'high', 'size': size, 'operation': operation,
                'prompt': prompt, 'input_sha256': detail.sha(target), 'mask_sha256': detail.sha(mask)}
            (folder/'image-call.request.json').write_text(json.dumps(identity))
            data = provider(target, size)
            (folder/'image-call.response.json').write_text(json.dumps({'data': [{'b64_json': base64.b64encode(data).decode()}]}))
            (folder/'raw.png').write_bytes(data)
            record = dict(identity, status='complete', output_sha256=detail.sha(folder/'raw.png'),
                reservation_id=operation, cost_usd=0, billing_state='usage_recorded')
            output.write_text(json.dumps(record))
            return record
        ctx.image_call = Mock(side_effect=image_call)
        return ctx
    case.context = context
    return case


@pytest.mark.parametrize('changed', [False, True])
def test_files_detail_compares_original_crop_and_retains_exact_lanczos_fallback(files_detail_case, changed):
    import cv2
    import numpy as np
    from apps.pipeline.services import round_files_detail as detail
    case = files_detail_case; original = case.source.read_bytes()
    if changed:
        def changed_reply(target, size):
            output = BytesIO(); Image.new('RGB', tuple(map(int, size.split('x'))), '#1234FF').save(output, format='PNG')
            return output.getvalue()
        case.provider.side_effect = changed_reply
    ctx = case.context()
    result = detail.detail_panel(ctx, 'body_front', case.source, case.panels['body_front'], case.root/'detail', expected_source_sha256=case.digest)
    folder = case.root/'detail/body_front'
    assert result['accepted'] is not changed
    assert result['selected'] == ('upscale.png' if changed else 'candidate.png')
    baseline = cv2.resize(np.asarray(Image.open(folder/'crop.png')), None, fx=2, fy=2, interpolation=cv2.INTER_LANCZOS4)
    assert np.array_equal(np.asarray(Image.open(folder/'upscale.png')), baseline)
    assert result['reference_px'] == [50, 220] and result['candidate_px'][1] == 1504
    assert result['reference_sha256'] == detail.sha(folder/'crop.png')
    assert result['candidate_sha256'] == detail.sha(folder/'candidate.png')
    assert all((folder/name).exists() for name in result['pins'])
    assert case.source.read_bytes() == original and case.provider.call_count == 1
    before = {path: path.read_bytes() for path in folder.rglob('*') if path.is_file()}
    replay = case.context()
    assert detail.detail_panel(replay, 'body_front', case.source, case.panels['body_front'], case.root/'detail', expected_source_sha256=case.digest) == result
    replay.image_call.assert_not_called()
    assert case.provider.call_count == 1 and all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize('failure', ['colour', 'structure'])
def test_files_detail_each_preservation_threshold_independently_refuses_changed_pixels(failure):
    import numpy as np
    from apps.pipeline.services.round_files_detail import compare_crop
    reference = Image.new('RGB', (48, 48), (128, 128, 128))
    if failure == 'colour':
        candidate = Image.new('RGB', reference.size, (148, 148, 148))
    else:
        yy, xx = np.indices((48, 48)); values = (126+4*((xx+yy)%2)).astype(np.uint8)
        candidate = Image.fromarray(np.repeat(values[..., None], 3, axis=2))
    measured = compare_crop(reference, candidate)
    assert measured['accepted'] is False
    if failure == 'colour':
        assert measured['de00_mean'] > 1.5 and measured['ssim'] >= .97
    else:
        assert measured['de00_mean'] <= 1.5 and measured['ssim'] < .97


def test_files_detail_letterboxes_only_own_crop_and_yields_before_second_provider_call(files_detail_case):
    import numpy as np
    from apps.pipeline.services import round_files_detail as detail
    case = files_detail_case; first = case.context()
    with pytest.raises(YieldRound):
        detail.run_details(first, case.source, case.panels, case.root/'detail', expected_source_sha256=case.digest)
    assert case.provider.call_count == first.new_calls == 1
    result = detail.run_details(case.context(), case.source, case.panels, case.root/'detail', expected_source_sha256=case.digest)
    assert set(result['panels']) == {'body_front', 'stand_header'} and case.provider.call_count == 2
    for panel, record in result['panels'].items():
        folder = case.root/'detail'/panel
        target = Image.open(folder/'input.png'); alpha = np.asarray(Image.open(folder/'mask.png'))[..., 3]
        dimensions = (1024, 1536) if panel == 'body_front' else (1536, 1024)
        assert target.size == dimensions and alpha.shape == dimensions[::-1]
        x0, y0, x1, y1 = record['identity']['full_canvas_box_px']
        expected = np.full(alpha.shape, 255, np.uint8); expected[y0:y1, x0:x1] = 0
        assert np.array_equal(alpha, expected)
        assert min(x0, y0, dimensions[0]-x1, dimensions[1]-y1) >= 16
        call = json.loads((folder/'call/image-call.json').read_text())
        assert call['operation'] == 'detail/'+panel and call['model'] == 'gpt-image-2' and call['quality'] == 'high'


@pytest.mark.parametrize('damage', ['source', 'crop', 'input.png', 'mask.png', 'call/image-call.request.json',
    'call/image-call.response.json', 'call/raw.png', 'candidate.png', 'comparison.json', 'decision'])
def test_files_detail_replay_refuses_changed_evidence_without_new_provider_call(files_detail_case, damage):
    from apps.pipeline.services import round_files_detail as detail
    case = files_detail_case; out = case.root/'detail'; panel = 'body_front'; box = case.panels[panel]
    detail.detail_panel(case.context(), panel, case.source, box, out, expected_source_sha256=case.digest)
    if damage == 'source':
        case.source.write_bytes(b'changed')
    elif damage == 'crop':
        box = [11, 10, 60, 230]
    elif damage == 'decision':
        path = out/panel/'detail.json'; record = json.loads(path.read_text()); record['accepted'] = not record['accepted']
        path.write_text(json.dumps(record))
    else:
        (out/panel/damage).write_bytes(b'changed')
    replay = case.context()
    with pytest.raises(ValueError, match='changed|cannot change|differs'):
        detail.detail_panel(replay, panel, case.source, box, out, expected_source_sha256=case.digest)
    replay.image_call.assert_not_called()
    assert case.provider.call_count == 1


def test_files_detail_interrupted_measurement_reuses_complete_paid_reply(files_detail_case, monkeypatch):
    from apps.pipeline.services import round_files_detail as detail
    case = files_detail_case; ctx = case.context(); out = case.root/'detail'
    with monkeypatch.context() as stopped:
        stopped.setattr(detail, 'compare_crop', Mock(side_effect=OSError('fixture interrupted comparison')))
        with pytest.raises(OSError, match='interrupted comparison'):
            detail.detail_panel(ctx, 'body_front', case.source, case.panels['body_front'], out, expected_source_sha256=case.digest)
    saved = {path: path.read_bytes() for path in (out/'body_front/call').iterdir()}
    result = detail.detail_panel(case.context(), 'body_front', case.source, case.panels['body_front'], out, expected_source_sha256=case.digest)
    assert result['accepted'] and case.provider.call_count == 1
    assert all(path.read_bytes() == data for path, data in saved.items())


def test_files_detail_budget_refusal_cannot_create_acceptance_or_change_source(files_detail_case):
    from apps.pipeline.services import round_files_detail as detail
    case = files_detail_case; ctx = case.context(); source = case.source.read_bytes()
    ctx.image_call = Mock(side_effect=BudgetExceededError('fixture $4 cap'))
    with pytest.raises(BudgetExceededError):
        detail.detail_panel(ctx, 'body_front', case.source, case.panels['body_front'], case.root/'detail', expected_source_sha256=case.digest)
    assert case.source.read_bytes() == source and not (case.root/'detail/body_front/detail.json').exists()
    assert not (case.root/'detail/body_front/comparison.json').exists()
    case.provider.assert_not_called()


@pytest.fixture
def files_detail_paid_case(context, files_detail_case, monkeypatch, settings):
    from apps.pipeline.services import round_files_attempt as attempt, round_files_detail as detail
    # Authority/claim transitions have their own job fixtures. Keep the actual
    # AttemptContext path restrictions, reservation, provider and settlement here.
    monkeypatch.setattr(attempt, 'claim', lambda ctx: {'authority': {'budget_usd': 4, 'maximum_image_calls': 2}})
    measured_panels = {panel: list(box) for panel, box in files_detail_case.panels.items()}
    monkeypatch.setattr(attempt, 'checked_inspection', lambda ctx: {
        'panels': {panel: {'crop_px': list(box)} for panel, box in measured_panels.items()}})
    settings.IMAGE_MODEL = 'gpt-image-2'
    build = SimpleNamespace(round=context.round, inputs={'brief': {}, 'picture_sha256': files_detail_case.digest})
    edit = Mock()
    def echoed(**kwargs):
        data = kwargs['image'][0].read()
        return image_reply(item={'b64_json': base64.b64encode(data).decode()})
    edit.side_effect = echoed
    client = SimpleNamespace(images=SimpleNamespace(edit=edit))
    def fresh(owner_attempt=0):
        return attempt.AttemptContext(build, SimpleNamespace(attempts=owner_attempt), image_client=client, native=False)
    ctx = fresh(); ctx.root.mkdir(parents=True, exist_ok=True)
    source = ctx.root/'source.png'; source.write_bytes(files_detail_case.source.read_bytes())
    return SimpleNamespace(ctx=ctx, fresh=fresh, edit=edit, source=source, build=build,
        digest=detail.sha(source), panels=files_detail_case.panels, out=attempt.folder(build)/'details')


def test_files_detail_real_context_two_edits_use_own_oriented_input_and_disjoint_budget(files_detail_paid_case):
    from apps.pipeline.services import round_files_attempt as attempt, round_files_detail as detail
    case = files_detail_paid_case
    with pytest.raises(YieldRound):
        detail.run_details(case.ctx, case.source, case.panels, case.out, expected_source_sha256=case.digest)
    result = detail.run_details(case.fresh(), case.source, case.panels, case.out, expected_source_sha256=case.digest)
    assert len(result['panels']) == case.edit.call_count == 2
    assert [call.kwargs['size'] for call in case.edit.call_args_list] == ['1024x1536', '1536x1024']
    for call in case.edit.call_args_list:
        assert call.kwargs['model'] == 'gpt-image-2' and call.kwargs['quality'] == 'high' and call.kwargs['n'] == 1
        assert len(call.kwargs['image']) == 1 and call.kwargs['mask'].name.endswith('/mask.png')
    ledger = attempt.scoped_spend(case.build)
    assert ledger['calls'] == 2 and ledger['budget_usd'] == 4 and ledger['held_usd'] == 0
    assert ledger['actual_usd'] > 0 and scoped_spend(case.build.round)['calls'] == 0
    assert detail.run_details(case.fresh(1), case.source, case.panels, case.out, expected_source_sha256=case.digest) == result
    assert case.edit.call_count == 2 and attempt.scoped_spend(case.build) == ledger


@pytest.mark.parametrize('failure', ['raw_checkpoint', 'download'])
def test_files_detail_real_context_local_recovery_never_rebuys_saved_reply(files_detail_paid_case, monkeypatch, failure):
    from apps.pipeline.agents import image_producer
    from apps.pipeline.services import round_files_attempt as attempt, round_files_detail as detail, round_flow as flow
    case = files_detail_paid_case
    if failure == 'download':
        def url_reply(**kwargs):
            case.paid_bytes = kwargs['image'][0].read()
            return image_reply(item={'url': 'https://fixture.invalid/paid-detail.png'})
        case.edit.side_effect = url_reply
    with monkeypatch.context() as stopped:
        if failure == 'raw_checkpoint':
            original = flow.commit_artifacts
            def crash(record, message):
                if message == 'master raw edit retained':
                    raise OSError('fixture raw checkpoint interrupted')
                return original(record, message)
            stopped.setattr(flow, 'commit_artifacts', crash)
        else:
            stopped.setattr(image_producer, 'download_image_bytes', Mock(side_effect=TimeoutError('fixture download interrupted')))
        with pytest.raises(OSError, match='fixture'):
            detail.detail_panel(case.ctx, 'body_front', case.source, case.panels['body_front'], case.out, expected_source_sha256=case.digest)
    call = case.out/'body_front/call'
    retained = {p: p.read_bytes() for p in call.glob('*.json')}
    assert not (call/'image-call.json').exists()
    if failure == 'download':
        monkeypatch.setattr(image_producer, 'download_image_bytes', Mock(return_value=case.paid_bytes))
    result = detail.detail_panel(case.fresh(1), 'body_front', case.source, case.panels['body_front'], case.out, expected_source_sha256=case.digest)
    assert result['accepted'] and case.edit.call_count == 1
    assert attempt.scoped_spend(case.build)['calls'] == 1 and attempt.scoped_spend(case.build)['held_usd'] == 0
    assert all(p.read_bytes() == data for p, data in retained.items())


def test_files_detail_real_context_unknown_outcome_holds_dollar_without_repurchase(files_detail_paid_case):
    from apps.pipeline.services import round_files_attempt as attempt, round_files_detail as detail
    case = files_detail_paid_case; case.edit.side_effect = TimeoutError('fixture unknown provider outcome')
    with pytest.raises(TimeoutError):
        detail.detail_panel(case.ctx, 'body_front', case.source, case.panels['body_front'], case.out, expected_source_sha256=case.digest)
    with pytest.raises(ValueError, match='outcome is unknown'):
        detail.detail_panel(case.fresh(1), 'body_front', case.source, case.panels['body_front'], case.out, expected_source_sha256=case.digest)
    assert case.edit.call_count == 1
    assert attempt.scoped_spend(case.build)['held_usd'] == 1 and attempt.scoped_spend(case.build)['calls'] == 1


@pytest.mark.parametrize('limit', ['dollars', 'image_attempts'])
def test_files_detail_real_context_refuses_dollar_or_image_cap_before_provider(files_detail_paid_case, limit):
    from apps.pipeline.services import round_files_detail as detail
    case = files_detail_paid_case
    if limit == 'dollars':
        spend.reserve('anthropic', case.ctx.prefix+'historical', 'fixture', 3.01)
    else:
        for index in range(2):
            spend.reserve('openai', case.ctx.prefix+'image/historical-'+str(index), 'fixture', .1)
    with pytest.raises(BudgetExceededError):
        detail.detail_panel(case.ctx, 'body_front', case.source, case.panels['body_front'], case.out, expected_source_sha256=case.digest)
    case.edit.assert_not_called()
    assert not (case.out/'body_front/call/image-call.request.json').exists()


@pytest.mark.parametrize('mismatch', ['source', 'crop'])
def test_files_detail_real_context_binds_paid_canvas_to_authorized_picture_and_measured_crop(files_detail_paid_case, mismatch):
    from apps.pipeline.services import round_files_attempt as attempt, round_files_detail as detail
    case = files_detail_paid_case; folder = case.out/'body_front'
    detail._prepare(folder, 'body_front', case.source, case.panels['body_front'], case.digest)
    prepared = folder/'prepared.json'; record = json.loads(prepared.read_text())
    if mismatch == 'source':
        record['identity']['source_sha256'] = '0'*64
    else:
        record['identity']['crop_px'][0] += 1
    prepared.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='bind the unchanged picked picture and measured crop'):
        case.ctx.image_call('detail/body_front', detail.PROMPT, folder/'call',
            target=folder/'input.png', mask=folder/'mask.png', size='1024x1536')
    case.edit.assert_not_called()
    assert attempt.scoped_spend(case.build)['calls'] == 0
    assert not (folder/'call/image-call.request.json').exists()
