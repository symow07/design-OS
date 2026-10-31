"""Archived with the retired picture-tracing path (docs/rounds/reuse-plan.md); moved from apps/pipeline/tests/test_round_files_page.py, not collected."""

@pytest.mark.parametrize('bundle_ready', [False, True])
def test_active_second_build_names_its_stop_and_labels_the_older_preview(
        client, record, isolated, monkeypatch, bundle_ready):
    from apps.pipeline.services import round_files_attempt as attempt
    from apps.pipeline.services.round_flow import write_json
    build = make_build(record)
    build.current_step = 'eye'
    build.error = 'ValueError: Fixture preparation interrupted'
    build.steps['eye']['result'] = {'verdict': 'needs_attention', 'revision': 2,
        'looks': [{}, {}, {}], 'preview': preview(build, verdict='needs_attention')}
    build.save()
    folder = attempt.folder(build)
    write_json(folder/'claim.json', {'authority': {'first_revision': 3}})
    for name in ('body_front', 'stand_header'):
        write_json(folder/'details'/name/'detail.json', {'accepted': False})
    if bundle_ready:
        write_json(folder/'bundle.json', {})
    monkeypatch.setattr(attempt, 'available', lambda build: True)
    monkeypatch.setattr(attempt, 'scoped_spend', lambda build: {'actual_usd': .35})
    page = client.get(reverse('dashboard:product_round_files', args=[record.pk]))
    html = page.content.decode()
    expected = 'Making your files' if bundle_ready else 'Fitting the gold lines and building the stand'
    assert page.status_code == 200
    assert page.context['attempt_started'] and not page.context['attempt_ready']
    assert not page.context['progress']
    assert [row['label'] for row in page.context['attempt_progress']
            if row['state'] == 'Needs attention'] == [expected]
    assert 'The pictures and review below are from your previous build.' in html
    assert 'ready to retry. It has a separate' not in html
    assert 'Second build: spent $0.3500 of $4.00.' in html
    assert '>Retry</button>' in html and '>Download<' not in html
    assert not isolated['queue'] and not isolated['legacy']


@pytest.mark.parametrize('status', ['incomplete', 'validation_failed', 'complete'])
def test_second_build_review_progress_does_not_hide_a_failed_review(record, status):
    from apps.pipeline.services import round_files_attempt as attempt
    from apps.pipeline.services.round_flow import write_json
    build = make_build(record)
    folder = attempt.folder(build)
    write_json(folder/'claim.json', {'authority': {'first_revision': 3}})
    for name in ('details/body_front/detail.json', 'details/stand_header/detail.json',
                 'bundle.json', '../../revisions/3/outputs.json'):
        write_json(folder/name, {})
    write_json(folder/'review/eye-1.json', {'status': status})
    if status == 'complete':
        build.steps['eye']['result'] = {'attempt': 2, 'verdict': 'needs_attention', 'looks': [{}]}
    progress = attempt.progress(build)
    assert [row['label'] for row in progress if row['state'] == 'Needs attention'] == ['Designer’s first look']
    assert progress[-1] == {'label': 'Preparing your download', 'state': 'Waiting'}


def review_stop(record, looks=2, *, kind='designer review'):
    build = make_build(record)
    verdict = {'verdict': 'needs_attention', 'findings': ['The tray still differs from the picked picture.'], 'repair': None}
    build.current_step = 'eye'
    build.steps['read']['state'] = 'complete'
    build.error = 'ValueError: The designer’s review needs attention: ' + verdict['findings'][0]
    build.steps['eye'].update(state='failed', result=dict(verdict, looks=[dict(verdict) for _ in range(looks)],
        revision=looks-1, preview=preview(build, verdict='needs_attention')),
        history=[{'kind': kind, 'error': build.error, 'step': 'eye', 'attempt': 0, 'dispatch': 1}])
    build.save()
    return build


@pytest.mark.parametrize('looks,authorized,exhausted', [(2, False, True), (2, True, False), (3, False, True), (3, True, True)])
@pytest.mark.parametrize('kind', ['designer review', 'worker'])
def test_completed_review_limit_controls_both_button_and_retry_endpoint(
        client, record, isolated, monkeypatch, django_capture_on_commit_callbacks, looks, authorized, exhausted, kind):
    from apps.pipeline.services import round_files_extension
    monkeypatch.setattr(round_files_extension, 'extension_available', lambda build: authorized)
    build = review_stop(record, looks, kind=kind)
    page = client.get(reverse('dashboard:product_round_files', args=[record.pk]))
    assert page.context['review_exhausted'] is exhausted
    assert (b'>Retry</button>' in page.content) is not exhausted
    assert (b'The reviews are complete' in page.content) is exhausted
    assert b'>Download<' not in page.content
    previous_steps, previous_error = build.steps, build.error
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(reverse('dashboard:product_round_files_retry', args=[record.pk]))
    build.refresh_from_db()
    if exhausted:
        assert response.status_code == 400
        assert b'The authorized reviews are complete.' in response.content
        assert b'>Retry</button>' not in response.content
        assert build.state == 'failed' and build.steps == previous_steps and build.error == previous_error
        assert not isolated['queue']
    else:
        assert response.status_code == 302 and build.state == 'queued'
        assert build.steps['eye']['attempts'] == 1 and build.error == ''
        assert isolated['queue'] == [build.pk]


@pytest.mark.parametrize('case', ['one_look', 'interrupted_repair', 'interrupted_export', 'interrupted_publish'])
def test_incomplete_execution_keeps_retry_even_with_an_older_attention_verdict(
        client, record, isolated, monkeypatch, django_capture_on_commit_callbacks, case):
    from apps.pipeline.services import round_files_extension
    def no_extension_needed(_build):
        raise AssertionError('A transient execution failure must not consult the extra-review authorization')
    monkeypatch.setattr(round_files_extension, 'extension_available', no_extension_needed)
    build = review_stop(record, looks=1 if case == 'one_look' else 2)
    if case != 'one_look':
        build.error = 'RuntimeError: Fixture execution interrupted'
        build.current_step = {'interrupted_repair': 'eye', 'interrupted_export': 'files', 'interrupted_publish': 'publish'}[case]
        step = build.steps[build.current_step]
        step['state'] = 'failed'
        step['history'].append({'kind': 'worker', 'error': build.error, 'step': build.current_step, 'attempt': 0, 'dispatch': 2})
        build.save()
    page = client.get(reverse('dashboard:product_round_files', args=[record.pk]))
    assert not page.context['review_exhausted'] and b'>Retry</button>' in page.content
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(reverse('dashboard:product_round_files_retry', args=[record.pk]))
    build.refresh_from_db()
    assert response.status_code == 302 and build.state == 'queued'
    assert build.steps[build.current_step]['attempts'] == 1
    assert isolated['queue'] == [build.pk]


@pytest.mark.parametrize('damage', ['invalid_schema', 'missing_field', 'wrong_type'])
def test_invalid_extension_policy_keeps_get_and_post_terminal_without_dispatch(
        client, record, isolated, monkeypatch, django_capture_on_commit_callbacks, damage):
    from apps.pipeline.services import round_files_extension
    build = review_stop(record)
    invalid = {'invalid_schema': {'schema': 'invalid'},
               'missing_field': {'schema': 'owner_files_extension/1'}, 'wrong_type': []}[damage]
    monkeypatch.setattr(round_files_extension, 'policy', lambda: {'repair_extensions': {record.slug: invalid}})
    original_steps, original_error = build.steps, build.error
    page = client.get(reverse('dashboard:product_round_files', args=[record.pk]))
    assert page.status_code == 200 and page.context['review_exhausted']
    assert b'The reviews are complete' in page.content
    assert b'>Retry</button>' not in page.content and b'>Download<' not in page.content
    with django_capture_on_commit_callbacks(execute=True):
        refused = client.post(reverse('dashboard:product_round_files_retry', args=[record.pk]))
    assert refused.status_code == 400 and b'The authorized reviews are complete.' in refused.content
    assert b'>Retry</button>' not in refused.content
    build.refresh_from_db()
    assert build.state == 'failed' and build.steps == original_steps and build.error == original_error
    assert not isolated['queue']
