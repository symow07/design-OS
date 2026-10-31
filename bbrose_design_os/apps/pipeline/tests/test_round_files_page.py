"""Owner page and download boundaries, using local manifests and no dispatches."""
import hashlib
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from apps.pipeline.models import Round, RoundMaster
from apps.pipeline.services import round_files_gate as flow, round_flow
from apps.pipeline.services.round_designer import DESIGNER_FLOW, gloss_brief


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated(settings, tmp_path, monkeypatch):
    settings.SECURE_SSL_REDIRECT = False
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    calls = {'queue': [], 'recover': []}
    monkeypatch.setattr(round_flow, '_enqueue', lambda pk: calls['queue'].append(pk))
    monkeypatch.setattr(round_flow, 'recover_dispatch', lambda record: None)
    monkeypatch.setattr(flow, 'enqueue', lambda pk: calls['queue'].append(pk))
    monkeypatch.setattr(flow, 'recover', lambda build: calls['recover'].append(build.pk))
    return calls


@pytest.fixture
def owner():
    return get_user_model().objects.create_superuser(
        username='files-owner', email='files@example.invalid', password='fixture-password')


@pytest.fixture
def client(owner):
    client = Client()
    client.force_login(owner)
    return client


@pytest.fixture
def record(owner):
    return Round.objects.create(slug='files-' + uuid4().hex, request_key=uuid4().hex,
        product_brief=dict(gloss_brief(), flow=DESIGNER_FLOW), created_by=owner, state='complete', current_step='pick',
        pick={'id': 'C2', 'reason': 'The one picture I chose'}, budget_usd=10)


def make_build(record, state='failed', names=None):
    """A build before its faces exist; ``names``: an older build's own steps (the face path's carried an eye)."""
    steps = {name: {'state': 'waiting', 'attempts': 0, 'dispatches': 0, 'history': [], 'result': {}}
             for name in names or flow.STEPS}
    steps['read']['state'] = state
    return RoundMaster.objects.create(round=record, inputs={'schema': flow.FILES_SCHEMA},
        current_step='read', steps=steps, state=state, budget_usd=10)


def preview(build, *, verdict='pass', download=False):
    root = flow.root(build)
    root.mkdir(parents=True, exist_ok=True)
    names = ['source.png', 'drawing.png']
    cards = []
    for name in ('Bottle', 'Cap', 'Stand'):
        crop, built = name.lower() + '-crop.png', name.lower() + '-built.png'
        names.extend((crop, built))
        cards.append({'label': name, 'crop': crop, 'built': built})
    if download:
        names += ['files.zip', 'README.md']
    pins = {}
    for name in names:
        data = ('fixture bytes: ' + name).encode()
        (root / name).write_bytes(data)
        pins[name] = hashlib.sha256(data).hexdigest()
    result = {'picture': 'source.png', 'drawing': 'drawing.png', 'cards': cards, 'files': pins,
              'eye': {'verdict': verdict, 'findings': ['The picked layout is preserved.']},
              'spend': {'actual_usd': 0.47}}
    if download:
        result['download'] = 'files.zip'
    return result


def test_build_button_starts_only_after_pick_and_links_to_existing_build(client, record, isolated):
    url = reverse('dashboard:product_round', args=[record.pk])
    record.state = 'awaiting_pick'
    record.save()
    assert b'Build the files' not in client.get(url).content
    record.state = 'complete'
    record.save()
    page = client.get(url)
    assert b'Build the files' in page.content and b'Spend limit: $10' in page.content
    assert b'Build the master' not in page.content
    make_build(record)
    page = client.get(url)
    assert b'View your files' in page.content and b'Build the files' not in page.content
    assert not isolated['queue']


def test_start_and_retry_are_owner_post_actions(client, record, owner, monkeypatch, isolated):
    started, retried = [], []
    monkeypatch.setattr(flow, 'start', lambda pk, user: started.append((pk, user.pk)))
    monkeypatch.setattr(flow, 'retry', lambda pk, user: retried.append((pk, user.pk)))
    start = reverse('dashboard:product_round_files_start', args=[record.pk])
    retry = reverse('dashboard:product_round_files_retry', args=[record.pk])
    assert client.get(start).status_code == 405
    assert client.post(start).status_code == 302
    make_build(record)
    assert client.get(retry).status_code == 405
    response = client.post(retry)
    assert response.status_code == 302 and response.url == reverse('dashboard:product_round_files', args=[record.pk])
    assert started == retried == [(record.pk, owner.pk)]
    assert not isolated['queue']


def test_new_start_refuses_a_legacy_round_without_dispatch(client, record, isolated):
    record.product_brief = {'schema': 'round_product/1', 'name': 'Lip gloss — whole-object round', 'product_type': 'lip_gloss'}
    record.save()
    response = client.post(reverse('dashboard:product_round_files_start', args=[record.pk]))
    assert response.status_code == 400 and not RoundMaster.objects.exists()
    assert not isolated['queue']


def test_progress_and_retry_use_plain_words_and_keep_internal_errors_out(client, record, isolated):
    build = make_build(record)
    build.error = 'engine_code EXAMPLE_INTERNAL_VALUE'
    build.save()
    page = client.get(reverse('dashboard:product_round_files', args=[record.pk]))
    html = page.content.decode()
    assert page.status_code == 200 and 'Retry' in html
    assert 'Reading your picture' in html and 'Making your files' in html
    assert 'engine_code' not in html and 'EXAMPLE_INTERNAL_VALUE' not in html
    assert 'http-equiv="refresh"' not in html
    assert isolated['recover'] == [build.pk] and not isolated['queue']
    build.state = 'running'
    build.save()
    assert b'http-equiv="refresh"' in client.get(reverse('dashboard:product_round_files', args=[record.pk])).content


def test_failed_eye_preview_overrides_saved_files_preview_without_a_download(client, record):
    build = make_build(record, names=flow.FACE_PATH_STEPS)
    build.steps['files']['result'] = {'preview': preview(build)}
    failed = preview(build, verdict='needs_repair')
    failed['eye']['findings'] = ['Move the cap lettering back to the picked position.']
    build.steps['eye']['result'] = {'preview': failed}
    build.save()
    page = client.get(reverse('dashboard:product_round_files', args=[record.pk]))
    html = page.content.decode()
    assert len(page.context['saved_cards']) == 3
    assert 'Move the cap lettering back' in html and 'passed the designer' not in html
    assert 'Your picked picture' in html and 'Built drawing' in html
    assert html.count('<img ') == 8 and '>Download<' not in html
    assert 'Spent $0.4700 of $10.00' in html


def test_completed_publication_has_one_download_and_three_comparisons(client, record):
    build = make_build(record, 'complete')
    build.publication = preview(build, download=True)
    build.save()
    page = client.get(reverse('dashboard:product_round_files', args=[record.pk]))
    html = page.content.decode()
    assert html.count('>Download<') == 1 and html.count('<img ') == 8
    assert 'Your files passed the designer' in html
    url = reverse('dashboard:product_round_files_download', args=[record.pk, 'files.zip'])
    response = client.get(url)
    assert response.status_code == 200 and response.content == b'fixture bytes: files.zip'
    assert response['Content-Disposition'] == 'attachment; filename="files.zip"'
    assert response['Cache-Control'] == 'private, no-store'
    assert response['X-Content-Type-Options'] == 'nosniff'


def test_preview_files_need_a_manifest_and_exact_unchanged_bytes(client, record):
    build = make_build(record)
    build.steps['files']['result'] = {'preview': preview(build)}
    build.save()
    url = reverse('dashboard:product_round_files_download', args=[record.pk, 'source.png'])
    assert client.get(url).status_code == 200
    (flow.root(build) / 'source.png').write_bytes(b'edited after publication')
    assert client.get(url).status_code == 404
    (flow.root(build) / 'secret.json').write_text('{}')
    assert client.get(reverse('dashboard:product_round_files_download', args=[record.pk, 'secret.json'])).status_code == 404


def test_a_pinned_symlink_cannot_leave_the_build_folder(client, record, tmp_path):
    build = make_build(record)
    published = preview(build)
    outside = tmp_path / 'outside.png'
    outside.write_bytes(b'outside fixture')
    (flow.root(build) / 'escape.png').symlink_to(outside)
    published['files']['escape.png'] = hashlib.sha256(outside.read_bytes()).hexdigest()
    build.publication = published
    build.save()
    assert client.get(reverse('dashboard:product_round_files_download', args=[record.pk, 'escape.png'])).status_code == 404


def test_a_manifest_cannot_offer_the_zip_before_completion(client, record):
    build = make_build(record)
    build.steps['files']['result'] = {'preview': preview(build, download=True)}
    build.save()
    assert b'>Download<' not in client.get(reverse('dashboard:product_round_files', args=[record.pk])).content
    assert client.get(reverse('dashboard:product_round_files_download', args=[record.pk, 'files.zip'])).status_code == 404


def test_foreign_owner_cannot_start_view_retry_or_download(record, monkeypatch, isolated):
    build = make_build(record)
    build.publication = preview(build)
    build.save()
    other = get_user_model().objects.create_user(username='files-stranger', password='fixture-password')
    other.groups.add(Group.objects.get_or_create(name='Design Team')[0])
    client = Client()
    client.force_login(other)
    started, retried = [], []
    monkeypatch.setattr(flow, 'start', lambda *args: started.append(args))
    monkeypatch.setattr(flow, 'retry', lambda *args: retried.append(args))
    for name in ('product_round_files_start', 'product_round_files_retry'):
        assert client.post(reverse('dashboard:' + name, args=[record.pk])).status_code == 403
    assert client.get(reverse('dashboard:product_round_files', args=[record.pk])).status_code == 403
    assert client.get(reverse('dashboard:product_round_files_download', args=[record.pk, 'source.png'])).status_code == 403
    assert not started and not retried and not isolated['recover'] and not isolated['queue']


def test_a_build_of_another_contract_cannot_dispatch_through_the_files_pages(client, record, monkeypatch, isolated):
    # [2026-10-29] the master pages, the other contract's, retired; the files pages still refuse any build not theirs
    build = make_build(record)
    build.inputs = {}
    build.save()
    for name, method, args in (
            ('product_round_files', 'get', [record.pk]),
            ('product_round_files_retry', 'post', [record.pk]),
            ('product_round_files_download', 'get', [record.pk, 'source.png'])):
        assert getattr(client, method)(reverse('dashboard:' + name, args=args)).status_code == 404
    assert not isolated['recover'] and not isolated['queue']


def test_retry_failure_keeps_the_page_and_its_saved_preview(client, record, monkeypatch):
    build = make_build(record)
    build.steps['files']['result'] = {'preview': preview(build)}
    build.save()
    def refuse(*_args):
        raise ValueError('There is no failed files step to retry.')
    monkeypatch.setattr(flow, 'retry', refuse)
    page = client.post(reverse('dashboard:product_round_files_retry', args=[record.pk]))
    assert page.status_code == 400 and b'There is no failed files step to retry.' in page.content
    assert len(page.context['saved_cards']) == 3
