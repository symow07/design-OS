"""Day 1 contracts. Synthetic critiques test policy, not the vision model's accuracy."""
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from django.core.files.base import ContentFile
from apps.pipeline.services.concept_quality import evaluate, image_verdict, DIMENSIONS
from apps.pipeline.tests.quality_fixtures import critique, reviewed
from apps.pipeline.services.intake_constraints import target_conflict, read_intake
from apps.pipeline.services import spend_reservation as spend
from apps.pipeline.services.cost_ledger import BudgetExceededError

GOLDEN_BAD = [
    'Pink-on-pink product name is unreadable', 'Required red accent below 6% was erased',
    'Eight bottles instead of twelve', 'Clear glass flattened to opaque ink',
    'Dropper substituted for chrome spray cap', 'Required Arabic line missing',
    'Booth output for a countertop stand brief', 'Required live text rasterized',
    'Artwork crosses the excluded seam',
    'TRACED_TEXT: required copy converted to outlines or baked into raster',
]

@pytest.mark.parametrize('failure', GOLDEN_BAD + [None])
def test_ten_golden_acceptance_contracts(failure):
    result = evaluate(critique(9, [failure] if failure else []))
    assert result['passed'] is (failure is None)
    assert result['review_status'] == ('rejected' if failure else 'accepted')

@pytest.mark.parametrize('value', [None, {}, {'passed': True, 'score': 10}, {'dimensions': {}, 'hard_failures': []}])
def test_unavailable_or_incomplete_critic_is_pending(value):
    assert evaluate(value)['review_status'] == 'review_pending'


def test_mean_and_critical_floors_cannot_be_overridden():
    data = critique(9)
    data['dimensions']['typography']['score'] = 6
    data['passed'] = True
    assert not evaluate(data)['passed']
    assert not evaluate(critique(7.9))['passed']
    data['dimensions']['typography']['score'] = 10**1000
    assert evaluate(data)['review_status'] == 'review_pending'


@pytest.mark.django_db
def test_gate_rechecks_pixels_and_never_accepts_old_boolean(client):
    from django.contrib.auth.models import User
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage
    from apps.pipeline.services.gate1_review import image_is_selectable
    owner = User.objects.create_superuser('rescue-owner', password='test')
    client.force_login(owner)
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Rescue'), task_text='30 ml serum', status='awaiting_gate_1')
    image = GeneratedImage.objects.create(task=task, direction_name='Bold', prompt_used='fixture', qa_passed=True)
    assert not image_is_selectable(image)
    assert client.post(f'/api/tasks/{task.pk}/gate1_approve/', {'image_id': image.pk}).status_code == 409
    reviewed(image)
    assert image_is_selectable(image)
    image.image_file.save('changed.png', ContentFile(b'changed after review'))
    assert not image_is_selectable(image)
    assert image_verdict(image, verify_pixels=True)['review_status'] == 'review_pending'


def test_target_conflicts_and_unimplemented_construction_stop_before_payment():
    assert target_conflict('exhibition_booth', 'Countertop display stand, 12 bottles, three steps')['error'] == 'TARGET_BRIEF_CONFLICT'
    assert target_conflict('display_stand', '12 bottles in 3 steps with holes')['error'] == 'CONSTRUCTION_UNRESOLVED'
    assert target_conflict('exhibition_booth', '3x3 exhibition booth with floor plan and storage')['error'] == 'CONSTRUCTION_UNRESOLVED'
    assert target_conflict('exhibition_booth', 'Graphics only for a 3x3 exhibition booth with floor plan supplied') is None


def test_intake_keeps_numbers_copy_and_unresolved_fields_exactly():
    values = {'dimensions': 'Ø29 × 108 mm; 180 × 150 × 300 mm', 'copy': 'BBROSE\nكريم النهار بفيتامين سي', 'count': '12: 3 × 4'}
    result = read_intake(json.dumps(values))
    assert result['fields'] == values
    assert set(result['unresolved']) == {'method', 'languages', 'material'}


def test_two_concurrent_reservations_cannot_exceed_daily_cap():
    def reserve_one(_):
        try:
            return spend.reserve('openai', 'test', 'gpt-image-2', 15)
        except BudgetExceededError:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve_one, range(2)))
    assert len([r for r in results if r]) == 1
    assert spend.totals()['today_usd_accounted'] == 15


def test_campaign_cap_applies_even_when_previous_days_are_below_limit():
    spend.reserve('openai', 'test', 'gpt-image-2', 24)
    with spend._connect() as db:
        db.execute("UPDATE calls SET day='2026-01-01', accounted=249500000")
    with pytest.raises(BudgetExceededError):
        spend.reserve('openai', 'test', 'gpt-image-2', 1)


def test_refusal_happens_before_sdk_and_timeout_retains_reservation():
    spend.reserve('openai', 'test', 'gpt-image-2', 25)
    sdk = Mock()
    with pytest.raises(BudgetExceededError):
        spend.paid_operation(sdk, provider='openai', model='gpt-image-2')
    sdk.assert_not_called()


def test_each_failed_attempt_keeps_its_own_hold():
    sdk = Mock(side_effect=TimeoutError('billing unknown'))
    for _ in range(2):
        with pytest.raises(TimeoutError):
            spend.paid_operation(sdk, provider='openai', model='gpt-image-2')
    assert spend.totals()['today_usd_accounted'] == 2
    assert spend.totals()['unresolved_calls'] == 2


def test_paid_reply_and_image_are_saved_before_downstream_failure(settings):
    import base64
    response = SimpleNamespace(data=[{'b64_json': base64.b64encode(b'paid-image-bytes').decode()}], usage={'output_tokens': 40})
    assert spend.paid_operation(lambda **_: response, provider='openai', model='gpt-image-2') is response
    root = settings.RESCUE_SPEND_ROOT
    assert len(list(root.glob('responses/*/response.json'))) == 1
    assert next(root.glob('responses/*/image-0.png')).read_bytes() == b'paid-image-bytes'
    assert spend.totals()['unresolved_calls'] == 1  # actual billing is not invented


def test_openai_image_usage_settles_at_the_published_tariff(settings):
    """Day 8 (D-D8-10): a gpt-image reply with the provider's own token counts is settled at the standard tariff."""
    import base64
    usage = {'input_tokens': 1855, 'input_tokens_details': {'image_tokens': 1536, 'text_tokens': 319},
             'output_tokens': 5488, 'total_tokens': 7343}
    response = SimpleNamespace(data=[{'b64_json': base64.b64encode(b'png').decode()}], usage=usage)
    spend.paid_operation(lambda **_: response, provider='openai', model='gpt-image-2')
    tariff = settings.OPENAI_IMAGE_PRICES['gpt-image-2']
    expected = (1536 * tariff['image_input'] + 319 * tariff['text_input'] + 5488 * tariff['image_output']) / 1_000_000
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    assert row['state'] == 'usage_recorded' and row['accounted'] == int(round(expected * 1_000_000))
    assert row['accounted'] < row['reserved']
    assert spend.totals()['unresolved_calls'] == 0
    # a model without a published tariff, or a reply without token details, keeps its reservation
    assert spend.openai_image_cost_micro('gpt-image-unknown', usage) is None
    assert spend.openai_image_cost_micro('gpt-image-2', {'output_tokens': 40}) is None


def test_cache_reads_settle_at_the_published_read_price(settings):
    """Day 8: a cache read is billed at the model's read multiplier, a cache write at 1.25x, never both at full input."""
    from anthropic.types import Message, Usage, TextBlock
    settings.CLAUDE_PRICES = dict(settings.CLAUDE_PRICES, **{'claude-opus-5-5': (0.004, 0.020)})
    settings.CLAUDE_CACHE_READ_MULTIPLIER = {'default': 0.1, 'claude-opus-5-5': 0.05}
    response = Message(id='fixture', type='message', role='assistant', model='claude-opus-5-5',
                       content=[TextBlock(type='text', text='saved')], stop_reason='end_turn',
                       usage=Usage(input_tokens=1000, output_tokens=1000, cache_creation_input_tokens=2000,
                                   cache_read_input_tokens=100000))
    spend.paid_operation(lambda **_: response, provider='anthropic', model='claude-opus-5-5', max_tokens=20)
    with spend._connect() as db:
        accounted = db.execute('SELECT accounted FROM calls').fetchone()[0]
    expected = (1000 + 1.25 * 2000 + 0.05 * 100000) / 1000 * 0.004 + 1000 / 1000 * 0.020
    assert abs(accounted - expected * 1_000_000) <= 1
    assert spend.cache_read_multiplier('unknown-model') == 0.1


def test_a_rejected_unbilled_request_is_released_and_a_timeout_keeps_its_hold(settings):
    """Day 8: a 400 the provider answers before running anything is not billed — released to 0 and kept as
    rejected_unbilled; a timeout keeps its full reservation (billing unknown)."""
    class Rejected(Exception):
        status_code = 400
    with pytest.raises(Rejected):
        spend.paid_operation(Mock(side_effect=Rejected('grammar too large')), provider='anthropic', model='test-model', max_tokens=10)
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    assert row['state'] == 'rejected_unbilled' and row['accounted'] == 0 and '400' in row['usage']
    with pytest.raises(TimeoutError):
        spend.paid_operation(Mock(side_effect=TimeoutError('no answer')), provider='anthropic', model='test-model', max_tokens=10)
    with spend._connect() as db:
        states = [r[0] for r in db.execute('SELECT state FROM calls ORDER BY started_at')]
    assert states[-1] == 'reserved'
    assert spend.rejected_status(Rejected()) == 400 and spend.rejected_status(TimeoutError()) is None


def test_usage_settlement_is_idempotent_and_never_discards_overrun(settings):
    response = SimpleNamespace(content=[{'type': 'text', 'text': 'paid output'}], usage={'input_tokens': 1000000, 'output_tokens': 1000000})
    got = spend.paid_operation(lambda **_: response, provider='anthropic', model='test-model', max_tokens=1)
    assert got is response
    assert next(settings.RESCUE_SPEND_ROOT.glob('responses/*/response.json')).exists()
    with spend._connect() as db:
        row = dict(db.execute('SELECT * FROM calls').fetchone())
    spend.settle(row['id'], {'usage': {'input_tokens': 0, 'output_tokens': 0}}, row['artifact'], provider='anthropic', model='test-model')
    with spend._connect() as db:
        assert db.execute('SELECT accounted FROM calls').fetchone()[0] == row['accounted']


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_preview_true_dpi_and_rotation(tmp_path, rotation):
    import fitz
    from PIL import Image
    from apps.ire.rasterize import pdf_to_png
    from apps.ire.pdf_raster import page_geometry, expected_dimensions
    source, output = tmp_path / 'source.pdf', tmp_path / 'preview.png'
    doc = fitz.open(); page = doc.new_page(width=144, height=216); page.set_rotation(rotation); doc.save(source); doc.close()
    assert pdf_to_png(source, output, dpi=150)
    with Image.open(output) as image:
        assert image.size == expected_dimensions(page_geometry(source), 150)
    assert not pdf_to_png(tmp_path / 'missing.pdf', output)

@pytest.mark.django_db
def test_repair_preserves_good_siblings_and_allowance_survives_restart(monkeypatch):
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage
    from apps.pipeline.agents import aria
    from apps.pipeline.services.concept_quality import image_sha256
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Repair'), task_text='Serum', status='awaiting_gate_1')
    good = reviewed(GeneratedImage.objects.create(task=task, direction_name='Good', direction_id='d1'), 9)
    bad = reviewed(GeneratedImage.objects.create(task=task, direction_name='Bad', direction_id='d2', variation_number=2), 4)
    pending = GeneratedImage.objects.create(task=task, direction_name='Pending', direction_id='d3', variation_number=3)
    before = image_sha256(good)
    selected = []
    def produce(agent):
        selected.extend(p['repair_parent_image_id'] for p in agent.prompts)
        return [reviewed(GeneratedImage.objects.create(task=task, direction_name=p['direction_name'],
                prompt_used=p['full_prompt'], variation_number=p['variation_number'],
                reference_provenance={k: p[k] for k in ('repair_attempt_id','repair_parent_image_id','repair_root_image_id')}), 4)
                for p in agent.prompts]
    monkeypatch.setattr(aria.ImageProducerAgent, 'run', produce)
    monkeypatch.setattr(aria.QAReviewerAgent, 'run', lambda agent: [])
    monkeypatch.setattr(aria.ARIAAgent, '_product_profile', lambda agent: {})
    aria.ARIAAgent(task.pk)._repair_concepts()
    good.refresh_from_db(); pending.refresh_from_db(); task.refresh_from_db()
    assert not good.superseded and image_sha256(good) == before
    assert not pending.superseded and pending.pk not in selected
    assert selected[0] == bad.pk and len(selected) == 2
    assert task.options['rescue_repair_rounds'] == 2
    aria.ARIAAgent(task.pk)._repair_concepts(force=True)
    assert len(selected) == 2


def test_nullable_anthropic_cache_usage_settles(settings):
    from anthropic.types import Message, Usage, TextBlock
    response = Message(id='fixture', type='message', role='assistant', model='claude-sonnet-4-6',
                       content=[TextBlock(type='text', text='saved')], stop_reason='end_turn',
                       usage=Usage(input_tokens=10, output_tokens=10))
    assert spend.paid_operation(lambda **_: response, provider='anthropic', model=response.model, max_tokens=20) is response
    assert spend.totals()['unresolved_calls'] == 0


def test_unreadable_contrast_repair_is_not_called_fixed():
    from apps.ire.self_check import record
    result = record([{'kind': 'contrast', 'fixed': False, 'status': 'improved', 'what': 'name still unreadable'}], [])
    assert not result['clean'] and not result['fixed']
    assert result['said'] == ['Look at: name still unreadable']


def test_paid_url_survives_archival_download_failure(settings, monkeypatch):
    from apps.pipeline.agents import image_producer
    from apps.pipeline.services import round_calls
    monkeypatch.setattr(round_calls, 'download_image_bytes', Mock(side_effect=image_producer.ImageDownloadError('temporary download failure')))
    response = SimpleNamespace(data=[{'url': 'https://example.invalid/paid.png'}], usage=None)
    assert spend.paid_operation(lambda **_: response, provider='openai', model='gpt-image-2') is response
    assert response._rescue_download_error == 'temporary download failure'
    assert 'https://example.invalid/paid.png' in next(settings.RESCUE_SPEND_ROOT.glob('responses/*/response.json')).read_text()
    with spend._connect() as db:
        assert db.execute('SELECT state FROM calls').fetchone()[0] == 'billing_unresolved'


@pytest.mark.django_db
@pytest.mark.parametrize('legacy_manual', [False, True])
def test_budget_paused_repair_reuses_saved_child_and_round(monkeypatch, legacy_manual):
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage
    from apps.pipeline.agents import aria
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Resume'), task_text='Serum', image_rerun_count=int(legacy_manual))
    parent = reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold', direction_id='d1'), 4)
    purchases = []
    def produce(agent):
        prompt = agent.prompts[0]
        old = task.images.filter(reference_provenance__repair_attempt_id=prompt['repair_attempt_id']).first()
        if old:
            return [old]
        child = reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold',
                         reference_provenance={k: prompt[k] for k in ('repair_attempt_id', 'repair_parent_image_id', 'repair_root_image_id')}), 9)
        purchases.append(child.pk)
        raise BudgetExceededError('next call refused before payment')
    monkeypatch.setattr(aria.ImageProducerAgent, 'run', produce)
    monkeypatch.setattr(aria.ARIAAgent, '_product_profile', lambda agent: {})
    with pytest.raises(BudgetExceededError):
        aria.ARIAAgent(task.pk)._repair_concepts(manual_rerun=legacy_manual)
    task.refresh_from_db()
    assert 'rescue_repair_inflight' not in task.options
    assert task.options['rescue_repair_pending']
    aria.ARIAAgent(task.pk)._repair_concepts(manual_rerun=legacy_manual)
    task.refresh_from_db(); parent.refresh_from_db()
    assert len(purchases) == 1 and parent.superseded
    assert task.options['rescue_repair_rounds'] == 1 + int(legacy_manual)
    assert task.image_rerun_count == 2 * int(legacy_manual)
    assert 'rescue_repair_pending' not in task.options


@pytest.mark.django_db
def test_duplicate_regeneration_delivery_does_not_fail_owned_job():
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, Gate1RegenerationJob
    from apps.pipeline.tasks import regenerate_gate1_references
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Duplicate'), task_text='Serum', status='awaiting_gate_1')
    job = Gate1RegenerationJob.objects.create(task=task, status=Gate1RegenerationJob.STATUS_RUNNING)
    regenerate_gate1_references.run(job.pk)
    job.refresh_from_db(); task.refresh_from_db()
    assert job.status == Gate1RegenerationJob.STATUS_RUNNING
    assert task.status == 'awaiting_gate_1'


@pytest.mark.django_db
def test_normal_worker_retry_enters_pending_repair_before_initial_generation(monkeypatch):
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, CreativeBrief
    from apps.pipeline.agents.aria import ARIAAgent
    from apps.pipeline.tests.direction_fixtures import valid_document
    from apps.pipeline.design_intent import build_design_intent
    raw = valid_document()
    doc = build_design_intent(brief={'brand':'BBROSE', 'product_name':'Serum',
        'product_category':'serum', 'design_target':'packaging'}, intent=raw['design_intent'], directions=raw['directions'])
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Entry'), task_text='Serum',
                                    options={'rescue_repair_pending': {'attempt': 'saved'}})
    CreativeBrief.objects.create(task=task, design_intent={k:v for k,v in doc.items() if k != 'directions'}, directions=doc['directions'])
    repaired, generated = Mock(), Mock(side_effect=AssertionError('must not buy initial concepts again'))
    monkeypatch.setattr(ARIAAgent, '_repair_concepts', repaired)
    monkeypatch.setattr(ARIAAgent, '_render_variations', generated)
    ARIAAgent(task.pk).run()
    repaired.assert_called_once()
    generated.assert_not_called()


@pytest.mark.django_db
def test_pending_vision_keeps_same_paid_repair_attempt(monkeypatch):
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage
    from apps.pipeline.agents import aria
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Pending eye'), task_text='Serum')
    reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold'), 4)
    attempts = []
    def produce(agent):
        prompt = agent.prompts[0]
        attempts.append(prompt['repair_attempt_id'])
        old = task.images.filter(reference_provenance__repair_attempt_id=attempts[-1]).first()
        if old:
            return [old]
        child = reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold', reference_provenance={
            k: prompt[k] for k in ('repair_attempt_id','repair_parent_image_id','repair_root_image_id')}), 9)
        child.qa_notes = ''; child.save(update_fields=['qa_notes'])
        return [child]
    monkeypatch.setattr(aria.ImageProducerAgent, 'run', produce)
    monkeypatch.setattr(aria.QAReviewerAgent, 'run', lambda agent: [])
    monkeypatch.setattr(aria.ARIAAgent, '_product_profile', lambda agent: {})
    aria.ARIAAgent(task.pk)._repair_concepts()
    aria.ARIAAgent(task.pk)._repair_concepts()
    task.refresh_from_db()
    assert len(set(attempts)) == 1 and task.images.count() == 2
    assert task.options['rescue_repair_rounds'] == 1
    assert task.options['rescue_repair_pending']


@pytest.mark.django_db
def test_shared_revision_allowance_blocks_noop_requests_and_exposes_resume(client):
    from django.contrib.auth.models import User
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask
    from apps.pipeline.services.concept_quality import repair_state
    owner = User.objects.create_superuser('limit-owner', password='test')
    client.force_login(owner)
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Limit'), task_text='Serum',
        status='awaiting_gate_1', options={'rescue_repair_rounds': 2})
    response = client.post(f'/api/tasks/{task.pk}/gate1_reject/', {'notes':'Make the name larger'})
    assert response.status_code == 409 and response.json()['code'] == 'REVISION_REVIEW_REQUIRED'
    task.refresh_from_db(); assert task.status == 'awaiting_gate_1'
    state = client.get(f'/api/tasks/{task.pk}/status/').json()['repair_allowance']
    assert state['remaining'] == 0 and not state['can_revise']
    task.options['rescue_repair_pending'] = {'attempt':'paid'}
    assert repair_state(task)['can_resume'] and not repair_state(task)['can_revise']


def test_missing_contrast_repair_verdict_is_not_success(monkeypatch):
    from apps.ire import legibility
    from apps.pipeline.services import designers_eye
    doc = SimpleNamespace(metadata={})
    monkeypatch.setattr(legibility, 'repair', lambda doc: [{'what': 'Unverified colour change'}])
    assert designers_eye._legible(doc) == []
    assert 'fixed' in doc.metadata['contrast_review_error']


def test_container_prompts_allow_restraint_and_hybrid_assets():
    from apps.pipeline.services.container_gate1 import CONTAINER_GATE1_DIRECTIVES, CONTAINER_DIRECTIONS_DIRECTIVES, CONTAINER_SYSTEM
    for prompt in (CONTAINER_GATE1_DIRECTIVES, CONTAINER_DIRECTIONS_DIRECTIVES):
        text = ' '.join(prompt.split())
        assert 'Pattern supports the name and may be absent' in text
        assert 'Restraint, clear glass and cool chrome are valid' in text
        assert 'monochrome still needs contrast' in text
        assert 'rich and layered' not in text
        assert 'ground built of two or three planes' not in text
    system = ' '.join(CONTAINER_SYSTEM.split())
    assert 'High-resolution illustration or texture is allowed when briefed' in system
    assert 'required type and the logo remain live vector artwork' in system
    assert 'raster texture' not in system


@pytest.mark.django_db
@pytest.mark.parametrize('force', [False, True])
def test_historical_exhaustion_blocks_worker_repairs(monkeypatch, force):
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage
    from apps.pipeline.agents import aria
    from apps.pipeline.services.concept_quality import repair_state
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Legacy limit'),
        task_text='Serum', image_rerun_count=2)
    reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold'), 4)
    producer = Mock(side_effect=AssertionError('exhausted task must not buy images'))
    monkeypatch.setattr(aria.ImageProducerAgent, 'run', producer)
    aria.ARIAAgent(task.pk)._repair_concepts(force=force)
    task.refresh_from_db()
    producer.assert_not_called()
    assert task.images.count() == 1 and not task.options.get('rescue_repair_pending')
    assert repair_state(task)['remaining'] == 0


@pytest.mark.django_db
def test_one_historical_attempt_leaves_only_one_automatic_round(monkeypatch):
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage
    from apps.pipeline.agents import aria
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Legacy round'),
        task_text='Serum', image_rerun_count=1)
    reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold'), 4)
    purchases = []
    def produce(agent):
        prompt = agent.prompts[0]
        child = reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold',
            reference_provenance={k: prompt[k] for k in ('repair_attempt_id', 'repair_parent_image_id', 'repair_root_image_id')}), 4)
        purchases.append(child.pk)
        return [child]
    monkeypatch.setattr(aria.ImageProducerAgent, 'run', produce)
    monkeypatch.setattr(aria.ARIAAgent, '_product_profile', lambda agent: {})
    aria.ARIAAgent(task.pk)._repair_concepts()
    aria.ARIAAgent(task.pk)._repair_concepts()
    task.refresh_from_db()
    assert len(purchases) == 1 and task.options['rescue_repair_rounds'] == 2
    assert task.image_rerun_count == 1


@pytest.mark.django_db
def test_last_manual_rerun_is_claimed_once_in_worker(client, monkeypatch):
    from django.contrib.auth.models import User
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, GeneratedImage
    from apps.pipeline.agents import aria
    from apps.pipeline import tasks
    owner = User.objects.create_superuser('last-round', password='test')
    client.force_login(owner)
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Last round'),
        task_text='Serum', status='awaiting_gate_1', image_rerun_count=1)
    reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold'), 4)
    dispatch = Mock()
    monkeypatch.setattr(tasks.rerun_aria_images, 'delay', dispatch)
    url = f'/api/tasks/{task.pk}/rerun_images/'
    assert client.post(url).status_code == 200
    task.refresh_from_db()
    assert task.status == 'queued' and task.image_rerun_count == 1
    assert not task.options.get('rescue_repair_rounds')
    assert client.post(url).status_code == 409
    dispatch.assert_called_once_with(task.pk)
    purchases = []
    def produce(agent):
        prompt = agent.prompts[0]
        child = reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold',
            reference_provenance={k: prompt[k] for k in ('repair_attempt_id', 'repair_parent_image_id', 'repair_root_image_id')}), 9)
        purchases.append(child.pk)
        return [child]
    monkeypatch.setattr(aria.ImageProducerAgent, 'run', produce)
    monkeypatch.setattr(aria.ARIAAgent, '_product_profile', lambda agent: {})
    aria.ARIAAgent(task.pk).rerun_images()
    task.refresh_from_db()
    assert len(purchases) == 1 and task.image_rerun_count == 2
    assert task.options['rescue_repair_rounds'] == 2
    assert client.post(url).status_code == 409


@pytest.mark.django_db
def test_reference_refresh_hold_blocks_admission_and_queued_delivery(client, monkeypatch, settings):
    from django.contrib.auth.models import User
    from django.urls import reverse
    from apps.core.models import Brand
    from apps.pipeline.models import DesignTask, Gate1RegenerationJob, GeneratedImage
    from apps.pipeline.agents import aria
    from apps.pipeline.services import gate1_regeneration as refresh
    from apps.pipeline import tasks
    owner = User.objects.create_superuser('refresh-hold', password='test')
    client.force_login(owner)
    task = DesignTask.objects.create(brand=Brand.objects.create(name='Reference hold'),
        task_text='Clear serum chrome spray', status='awaiting_gate_1', image_rerun_count=1)
    original = reviewed(GeneratedImage.objects.create(task=task, direction_name='Bold'), 9)
    dispatch = Mock()
    producer = Mock(side_effect=AssertionError('paused refresh must not buy concepts'))
    monkeypatch.setattr(tasks.regenerate_gate1_references, 'delay', dispatch)
    monkeypatch.setattr(aria.ARIAAgent, '_regenerate_gate1_body', producer)
    with pytest.raises(refresh.GateRegenerationError, match='Reference refresh is paused'):
        refresh.request_gate1_regeneration(task, owner)
    dispatch.assert_not_called()
    assert not task.regeneration_jobs.exists()
    settings.GATE1_REGENERATION_MODE = 'live'
    url = reverse('dashboard:gate1_regeneration_confirm', kwargs={'task_id': task.pk})
    for method in (client.get, client.post):
        response = method(url)
        assert response.status_code == 409
        assert b'Reference refresh is paused' in response.content
    job = Gate1RegenerationJob.objects.create(task=task, status='queued')
    aria.ARIAAgent(task.pk).regenerate_gate1_with_references(job_id=job.pk)
    task.refresh_from_db(); job.refresh_from_db(); original.refresh_from_db()
    producer.assert_not_called()
    assert job.status == 'failed' and 'Reference refresh is paused' in job.error
    assert task.status == 'awaiting_gate_1' and task.image_rerun_count == 1
    assert not task.options.get('rescue_repair_rounds') and not original.superseded
