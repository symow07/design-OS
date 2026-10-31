"""Fixture-only queue/state tests: the app starts, marks and picks; jobs do the rest."""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import uuid

import pytest
from apps.pipeline.services.round_calls import scoped_spend
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from apps.pipeline.models import Round, RoundStep
from apps.pipeline.services import round_flow as flow


@pytest.fixture
def queued(tmp_path, settings, monkeypatch):
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    pending = []
    monkeypatch.setattr(flow, '_enqueue', pending.append)
    return pending


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user(username='round-owner')


def fixture_step(name, context):
    ids = [f'A{i}' for i in range(1, 9)]
    if name == 'seeds':
        flow.write_json(context.root / 'critic-calibration.json', {'marks': {}, 'picks': []})
    if name == 'pairwise':
        return {'order': ids}
    if name == 'sketches':
        return {'candidates': {key: {'id': key} for key in ids}}
    if name == 'forks':
        return {'candidates': {}}
    if name == 'pick_page':
        return {'order': ids[:6], 'candidates': {key: {'id': key} for key in ids[:6]}}
    if name == 'marks_fallback':
        return {'marks': [{'id': key, 'preserve': 'A visible fragment'} for key in ids[:3]],
                'source': {'kind': 'jury timeout fallback'}}
    return {'fixture_step': name}


def drain(pending):
    while pending:
        flow.run_step_job(pending.pop(0))


@pytest.mark.django_db(transaction=True)
def test_broker_failures_are_reportable_once_per_app_attempt(owner, monkeypatch, tmp_path, settings):
    from apps.pipeline import tasks
    settings.ROUND_ARTIFACT_ROOT = tmp_path / 'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path / 'spend'
    def unavailable(step_id):
        raise RuntimeError('fixture broker unavailable')
    monkeypatch.setattr(tasks.run_creative_round_step, 'delay', unavailable)
    record = flow.create_round(designer_brief(), owner, uuid.uuid4().hex)
    record.refresh_from_db()
    job = record.steps.get(name='research')
    assert record.state == job.state == 'failed'
    assert len(job.history) == 1 and job.history[0]['kind'] == 'queue_delivery'
    flow._enqueue(job.pk)
    job.refresh_from_db()
    assert len(job.history) == 1
    flow.retry_round(record.pk, owner)
    job.refresh_from_db()
    assert [event['attempt'] for event in job.history] == [0, 1]
    reportable = [{'step': item.name, **event} for item in record.steps.all() for event in item.history]
    assert len(reportable) == 2
    assert all(event['step'] == 'research' and 'fixture broker unavailable' in event['error'] for event in reportable)


@pytest.mark.django_db(transaction=True)
def test_unknown_new_round_schema_is_rejected_before_queue(queued, owner):
    brief = designer_brief()
    brief['schema'] = 'product_stand_picture/999'
    # [the owner's goal of 2026-10-29] only the designer flow starts a round: an unknown schema, the retired
    # twenty-design brief and the retired whole-object brief are each refused in words before anything is queued
    from apps.pipeline.services.round_designer import gloss_brief
    for refused in (brief, gloss_brief(), {'schema': 'round_product/1', 'name': 'Lip gloss — whole-object round', 'product_type': 'lip_gloss'}):
        with pytest.raises(ValueError, match='A round starts only from the designer brief'):
            flow.create_round(refused, owner, uuid.uuid4().hex)
    assert not queued and not Round.objects.exists()


def designer_brief():
    from apps.pipeline.services.round_designer import DESIGNER_FLOW, gloss_brief
    return dict(gloss_brief(), flow=DESIGNER_FLOW)


SENTINEL = 'RESEARCH-SENTINEL-NEVER-TO-THE-IMAGE-MODEL'
WEB_SENTINEL = 'WEB-TAKEAWAY-SENTINEL'
LIBRARY_SENTINEL = 'LIBRARY-CAPTION-SENTINEL'
SEARCHED_URL = 'https://example.com/gloss-launches'


def _research_payload():
    line = 'Clear acrylic bodies read as colour first'
    return {'category': 'Lip gloss at a beauty counter', 'references': [SENTINEL, line],
            **{key: [line, 'Gold caps carry quiet marks'] for key in ('launches', 'materials', 'finishes', 'colour', 'type', 'avoid')},
            'sources': [{'url': SEARCHED_URL + '/', 'takeaway': WEB_SENTINEL + ' clear walls lead the shelf'},
                        {'url': 'https://never-returned.example/page', 'takeaway': 'A source the search never gave'}]}


TAVILY_KEY = 'tvly-fixture-key-never-written'


def _tavily_response(query):
    """A stubbed Tavily answer: one page (and a picture, which must never be kept), with its credit."""
    class Response:
        status_code = 200
        headers = {'x-request-id': 'tavily-fixture'}
        body = {'results': [{'url': SEARCHED_URL, 'title': 'Gloss launches', 'score': 0.9, 'published_date': '2026-09-01',
                             'content': WEB_SENTINEL + ' snippet for ' + query, 'images': ['https://example.com/pic.png']}],
                'images': ['https://example.com/pic.png'], 'usage': {'credits': 1}, 'request_id': 'tv-1'}
        content = json.dumps(body).encode()

        def json(self):
            return self.body
    return Response()


def _designer_reply(prompt):
    """Deterministic provider replies for the designer flow, chosen by the call's own prompt."""
    if prompt.startswith('You are a senior packaging'):
        payload = _research_payload()
        if 'Web search is unavailable for this round' in prompt:
            payload['sources'] = []
        return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(payload)}],
                'usage': {'input_tokens': 5000, 'output_tokens': 900}}
    elif prompt.startswith('Plan three mood boards'):
        second = 'THE OWNER REJECTED' in prompt
        payload = {'boards': [{'id': key, 'idea': f'{"Second" if second else "First"} {key} idea of light through clear walls',
                               'link': 'because the liquid shows its colour', 'type': 'A narrow high-contrast serif',
                               'motif': 'A ' + key + ' facet line', 'texture': 'Fine frosted grain',
                               'palette': [{'name': 'Rose glass', 'hex': '#c9707a', 'role': 'liquid'},
                                           {'name': 'Warm gold', 'hex': '#B8925A', 'role': 'cap'},
                                           {'name': 'Ink', 'hex': '#1F1A1C', 'role': 'type'},
                                           {'name': 'Paper', 'hex': '#F4EFEA', 'role': 'ground'}],
                               'materials': ['Clear acrylic', 'Rigid paperboard'], 'finishes': ['Hot foil', 'Soft-touch'],
                               'library': ['L1', 'L3', 'L99'],
                               # L3 is a house design and L99 does not exist: neither may become a picture.
                               'references': ['L1', 'L2', 'L3', 'L99'] if key == 'bold' else []}
                              for key in ('bold', 'refined', 'unexpected')]}
    elif prompt.startswith('Plan three designs'):
        ids = prompt.split('with exactly the ids ')[1].split('.')[0].split(', ')
        payload = {'designs': [{'id': key, 'idea': 'The facet line runs from cap to header ' + key,
                                'composition': f'Composition {key}: the hero stands at position {index}',
                                'header': 'The faceted dial fills the header front',
                                'faces': 'The facet line runs on across the walls and the back',
                                'bottle': 'The facet line printed on the clear body, a window left open; foil on the cap'}
                               for index, key in enumerate(ids)]}
    elif prompt.startswith('Quickly check'):
        ids = prompt.split('shown in order: ')[1].split('.')[0].split(', ')
        payload = {'designs': {key: {'banned': {'ok': True, 'note': 'No banned motif'},
                                     'words': {'ok': key != ids[0], 'note': 'No letters in the art'},
                                     'faces': {'ok': True, 'note': 'Every printed face is painted'},
                                     'upright': {'ok': True, 'note': 'Every motif stands upright when folded'},
                                     'bottle': {'ok': True, 'note': 'A facet print on the clear body'}} for key in ids[1:]}}
    else:
        raise AssertionError('Unexpected designer prompt: ' + prompt[:80])
    return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(payload)}],
            'usage': {'input_tokens': 900, 'output_tokens': 700}}


def library_fixture(tmp_path, settings, monkeypatch):
    """A six-row Day 7 index with previews: two eligible house materials, a house design, a logo, a font, a quarantined row."""
    from PIL import Image
    from apps.pipeline.services import round_calls as image_guard
    from apps.pipeline.services.materials_retrieval import _hex_lab
    previews = tmp_path / 'previews'
    previews.mkdir()
    rows = []
    for char, kind, tags, colour, path, rights in (
            ('1', 'pattern', ['gold', 'acrylic', 'facet'], '#C9707A', 'materials/patterns/facets.png', {'tier': 'house'}),
            ('2', 'texture', ['clear', 'frost'], '#C8737C', 'materials/backgrounds/frost.png', {'tier': 'house'}),
            ('3', 'pattern', ['gold', 'wand'], '#B8925A', 'materials/house-designs/client-carton.png', {'tier': 'house'}),
            ('4', 'logo', ['gold', 'cap'], '#B8925A', 'materials/unknown/mark.png', {'tier': 'house'}),
            ('5', 'font', ['gold', 'gloss'], '#000000', 'materials/Fonts/a.otf', {'tier': 'GRANTED'}),
            ('6', 'pattern', ['gold', 'gloss'], '#C9707A', 'materials/unknown/b.png', {'tier': 'UNVERIFIED', 'excluded': True})):
        sha = char * 64
        Image.new('RGB', (40, 40), colour).save(previews / (sha + '.png'))
        rows.append({'sha256': sha, 'name': Path(path).name, 'paths': [path], 'kind': kind, 'tags': tags, 'style': [],
                     'subject': f'{LIBRARY_SENTINEL} {kind} {char}', 'colours': [{'hex': colour, 'lab': _hex_lab(colour), 'share': .6}],
                     'surfaces': [], 'rights': dict(rights, basis='fixture'), 'caption_source': 'day7-haiku',
                     'preview': True, 'preview_blank': False})
    index = tmp_path / 'materials-index.json'
    index.write_text(json.dumps({'schema': 'day7_materials_index/1', 'items': rows}))
    settings.MATERIALS_INDEX_PATH = str(index)
    settings.MATERIALS_PREVIEWS_ROOT = str(previews)
    settings.HOUSE_INDEX_PATH = str(tmp_path / 'no-house-index.json')
    monkeypatch.setattr(image_guard, 'denylist', lambda **kwargs: {'rejected': {}, 'web': {}})
    monkeypatch.setattr(image_guard, 'ALLOWED_ROOTS', image_guard.ALLOWED_ROOTS + (previews,))
    return previews


@pytest.fixture
def designer(queued, owner, monkeypatch, settings, tmp_path):
    """The real queue and paid boundary with deterministic fake providers and a fixture library; $0."""
    import base64
    from io import BytesIO
    from types import SimpleNamespace
    from PIL import Image
    from apps.pipeline.services import round_designer, round_designer as round_ideas_brief
    settings.IMAGE_MODEL = 'gpt-image-2'
    from apps.pipeline.services import web_research_tavily
    previews = library_fixture(tmp_path, settings, monkeypatch)
    sent = {'text': [], 'images': [], 'references': [], 'requests': [], 'tavily': []}
    settings.WEB_SEARCH_API_KEY = TAVILY_KEY
    settings.TAVILY_USD_PER_CREDIT = 0.008

    def tavily(url, *, json, headers, timeout):
        sent['tavily'].append(json)
        return sent['tavily_reply'](json['query'])

    sent['tavily_reply'] = _tavily_response
    monkeypatch.setattr(web_research_tavily.requests, 'post', tavily)

    def create(**kwargs):
        prompt = kwargs['messages'][0]['content'][-1]['text']
        sent['text'].append(prompt)
        sent['requests'].append(kwargs)
        return _designer_reply(prompt)

    def picture():
        output = BytesIO()
        Image.new('RGB', (1536, 1024), (len(sent['images']) * 9, 80, 60)).save(output, format='PNG')
        return {'data': [{'b64_json': base64.b64encode(output.getvalue()).decode()}],
                'usage': {'input_tokens': 700, 'output_tokens': 5488,
                          'input_tokens_details': {'image_tokens': 0, 'text_tokens': 700}}}

    def generate(**kwargs):
        sent['images'].append(kwargs['prompt'])
        sent['references'].append([])
        return picture()

    def edit(*, image, mask=None, stream=False, partial_images=0, **kwargs):
        sent['images'].append(kwargs['prompt'])
        sent['references'].append([Path(handle.name) for handle in image])
        if not stream:
            return picture()
        template = Image.open(image[0]).convert('RGBA')       # a flat design: the die's printed faces painted
        image[0].seek(0)
        painted = Image.new('RGB', template.size, (40, 60, 110 + len(sent['images'])))
        painted.paste(template.convert('RGB'), mask=template.getchannel('A'))
        output = BytesIO()
        painted.save(output, format='PNG')
        b64 = base64.b64encode(output.getvalue()).decode()
        return [{'type': 'image_edit.partial_image', 'partial_image_index': 0, 'b64_json': b64[:64]},
                {'type': 'image_edit.completed', 'b64_json': b64, 'usage': picture()['usage']}]

    original = round_designer.DesignerContext.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
        self.image_client = SimpleNamespace(images=SimpleNamespace(generate=generate, edit=edit))

    monkeypatch.setattr(round_designer.DesignerContext, '__init__', init)
    brief = dict(round_ideas_brief.gloss_brief(), flow=round_ideas_brief.DESIGNER_FLOW)
    return {'brief': brief, 'pending': queued, 'sent': sent, 'previews': previews}


@pytest.mark.django_db(transaction=True)
def test_designer_flow_runs_from_start_to_the_frozen_handoff_with_one_redo_per_pick(designer, owner, monkeypatch):
    from apps.pipeline.services import round_designer, round_files_gate as round_files_job, spend_reservation as spend
    from apps.pipeline.services.round_calls import scoped_spend
    from apps.pipeline.services.round_designer import gloss_brief, normalize_ideas_brief, printed_copy
    data, sent = designer, designer['sent']
    record = flow.create_round(data['brief'], owner, uuid.uuid4().hex)
    assert record.product_brief['flow'] == 'designer/1' and normalize_ideas_brief(gloss_brief()) == gloss_brief()
    assert record.current_step == 'research' and record.budget_usd == 2          # the owner's $2.00 per round
    assert record.artifacts == {'cost_rules': 'two-dollars/2026-10-29',
                                'face_rules': 'measured-holds+medium-faces/2026-10-29'}
    # this test walks the whole flow with "None of these" at both picks and fake replies billed at high-quality token
    # counts (twelve pictures, past $2.00); the cap itself is tested on its own (test_round_calls)
    type(record).objects.filter(pk=record.pk).update(budget_usd=10)
    record.refresh_from_db()
    assert flow.steps_for(record) == round_designer.DESIGNER_STEPS
    assert [row['name'] for row in flow.summary(record)['steps']] == list(round_designer.DESIGNER_STEPS)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick' and record.current_step == 'board_pick'
    boards = record.artifacts['boards']
    assert boards['order'] == ['bold', 'refined', 'unexpected'] and len(boards['files']) == 3
    assert boards['taste_used'] == 0 and boards['candidates']['bold']['palette'][0]['hex'] == '#C9707A'
    root = flow.round_root(record)
    request = json.loads((root / 'research' / 'notes-call.request.json').read_text())
    assert 'tools' not in request and request['images'] == []
    assert not any('tools' in body for body in sent['requests'])  # No Anthropic web search tool anywhere.
    # The stubbed Tavily search: six queries of the product type and topic words, no picture asked for or kept.
    assert [body['query'] for body in sent['tavily']] == [row['query'] for row in round_designer.search_queries(record.product_brief, 2026)]
    assert all(body['include_images'] is False for body in sent['tavily'])
    assert not any(word in body['query'].lower() for body in sent['tavily'] for word in ('bbrose', 'rose glass', 'ملمع'))
    research = record.artifacts['research']
    assert research['search_provider'] == 'tavily' and research['web_search'] == 'used'
    assert [row['url'] for row in research['sources']] == [SEARCHED_URL] and research['unverified_sources'] == 1
    assert [row['status'] for row in research['searches']] == ['complete'] * 6
    assert SEARCHED_URL in sent['text'][0] and WEB_SENTINEL in sent['text'][0] and 'pic.png' not in sent['text'][0]
    with spend._connect() as db:
        searches = [dict(row) for row in db.execute('SELECT state,accounted FROM calls WHERE operation=?',
                                                     (f'round/{record.slug}/research/search',))]
    assert searches == [{'state': 'usage_recorded', 'accounted': 8000}] * 6  # $0.008 each, inside the round's cap.
    assert not any(TAVILY_KEY in path.read_text(errors='ignore') for path in root.rglob('*') if path.is_file())
    # The fixture library: house-tier matches with previews; only eligible materials may become pictures.
    matches = research['library']['matches']
    assert [row['sha256'][0] for row in matches] == ['1', '2', '3', '4'] and [row['id'] for row in matches] == ['L1', 'L2', 'L3', 'L4']
    assert [row['may_reference'] for row in matches] == [True, True, False, False]
    assert 'house design' in matches[2]['why_words_only'] and 'logo' in matches[3]['why_words_only']
    bold = boards['candidates']['bold']
    assert bold['library'] == ['L1', 'L3'] and bold['references'] == ['L1', 'L2']
    assert bold['references_not_taken'] == ['L3', 'L99'] and boards['candidates']['refined']['reference_inputs'] == []
    assert [row['sha256'] for row in bold['reference_inputs']] == [matches[0]['preview_sha256'], matches[1]['preview_sha256']]
    assert [path.name for path in sent['references'][0]] == ['1' * 64 + '.png', '2' * 64 + '.png']
    assert 'house-library samples' in sent['images'][0] and 'house-library samples' not in sent['images'][1]
    assert WEB_SENTINEL in sent['text'][1] and LIBRARY_SENTINEL in sent['text'][1] and SEARCHED_URL not in sent['text'][1]
    # None of these, once: three new boards answer the owner's line.
    flow.none_of_these(record.pk, 'boards', 'Too quiet; I want contrast', owner)
    with pytest.raises(ValueError, match='once per pick'):
        flow.none_of_these(record.pk, 'boards', 'Another line', owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick' and record.artifacts['boards']['generation'] == 2
    assert record.artifacts['rejected_boards']['boards']['generation'] == 1
    assert 'Too quiet; I want contrast' in sent['text'][2] and record.artifacts['boards']['redo']
    with pytest.raises(ValueError, match='once per pick'):
        flow.none_of_these(record.pk, 'boards', 'Too quiet again', owner)
    with pytest.raises(ValueError, match='three boards'):
        flow.submit_board_pick(record.pk, 'missing', '', owner)
    flow.submit_board_pick(record.pk, 'unexpected', '', owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_pick' and record.artifacts['board_pick']['id'] == 'unexpected', record.error_message
    first = record.artifacts['pick_page']
    assert first['order'] == ['D1', 'D2', 'D3'] and first['flow'] == 'designer/1'
    findings = first['candidates']['D1']['findings']
    assert [row['ok'] for row in findings] == [None] * 5  # Missing reading: a finding; only a "No" removes (2026-10-29).
    assert [row['ok'] for row in first['candidates']['D2']['findings']] == [True] * 5
    check = json.loads((root / 'designs' / 'g1' / 'check-call.json').read_text())
    canvas = record.artifacts['designs']['candidates']['D1']['size_px']
    view = [1152, 768] if canvas[0] > canvas[1] else [768, 1152]
    # Reading copies of each flat die, its folded drawing and its bottle (2026-10-29); originals untouched.
    assert [item['px'] for item in check['images']][::3] == [view] * 3 and len(check['images']) == 9
    assert all(item['px'] in ([768, 512], [512, 768]) for index, item in enumerate(check['images']) if index % 3)
    # The die first: solved from the brief before any design, its template the input of every design.
    die = record.artifacts['designs']['die']
    assert json.loads((root / die['stand']).read_text())['record']['schema'] == 'stand_template/1'
    d1 = record.artifacts['designs']['candidates']['D1']
    assert d1['proof']['outside']['differing_from_template'] == 0 and d1['folded'] and d1['loaded']
    assert first['contract'] == 'flat_die_design/1' and first['candidates']['D1']['die_line'].startswith('Die match: 0 of')
    flow.none_of_these(record.pk, 'designs', 'The three stands look alike', owner)
    drain(data['pending'])
    record.refresh_from_db()
    page = record.artifacts['pick_page']
    assert record.state == 'awaiting_pick' and page['order'] == ['D4', 'D5', 'D6'] and page['generation'] == 2
    with pytest.raises(ValueError, match='once per pick'):
        flow.none_of_these(record.pk, 'designs', 'Again', owner)
    with pytest.raises(ValueError, match='final page'):
        flow.submit_pick(record.pk, 'D1', 'An earlier design', owner)
    flow.submit_pick(record.pk, 'D5', 'The header carries the cap’s facet', owner)
    drain(data['pending'])
    record.refresh_from_db()
    assert record.state == 'complete' and record.steps.filter(state='complete').count() == 6
    handoff = json.loads((root / 'handoff.json').read_text())
    assert handoff['schema'] == 'flat_die_handoff/1' and handoff['id'] == 'D5'
    assert handoff['picture'] == 'designs/g2/D5/flat.png' and handoff['reason'] == record.pick['reason']
    from apps.pipeline.services import round_files_gate as round_files_flow
    from apps.pipeline import tasks
    files_pending = []
    monkeypatch.setattr(tasks.run_round_files, 'delay', files_pending.append)
    build = round_files_flow.start(record.pk, owner)                  # the flat pick starts its files (2026-10-29)
    assert build.inputs['flat_pick'] == {'painting': 'designs/g2/D5/painting.json', 'die': 'die/stand.json'}
    # Research words never reached the image model; designs keep the frozen format.
    # 2 × 3 boards, 2 × 3 designs and, since 2026-10-29, each design's bottle on its net: 18 pictures
    assert len(sent['images']) == 18 and any(SENTINEL in prompt for prompt in sent['text'])
    for prompt in sent['images']:
        for marker in (SENTINEL, WEB_SENTINEL, LIBRARY_SENTINEL, SEARCHED_URL, 'RESEARCH', 'example.com'):
            assert marker not in prompt
    # Library pictures go only to the bold boards; a design is the die's template with the picked board as its style.
    assert [bool(paths) for paths in sent['references']] == [True, False, False, True, False, False] + [True] * 12
    assert all(path.parent == data['previews'] for paths in sent['references'][:6] for path in paths)
    for paths in sent['references'][6::2]:                 # each design: its die's template, the picked board
        assert [path.name for path in paths] == ['template.png', 'raw.png'] and paths[1].parent.parent.name == 'g2'
    for paths in sent['references'][7::2]:                 # its bottle: the net's template, the design's own painting
        assert [path.name for path in paths] == ['template.png', 'flat.png'] and paths[0].parent.name == 'bottle'
    for index, prompt in enumerate(sent['images'][6:]):
        assert prompt.startswith('Image 1 is a flat die' if index % 2 == 0 else 'Image 1 is a flat net')
        assert round_designer.COPY_START not in prompt
        assert 'BBROSE' not in prompt and 'Rose Glass' not in prompt and 'No letters, numbers or words' in prompt
    spend = scoped_spend(record)
    assert spend['image_calls'] == 18 and spend['reserved_usd'] == 0 and spend['accounted_usd'] < 10
    assert not (flow.round_root(record).parent / 'BREAKS.md').exists()
    # Taste memory: the next round's boards are guided by these picks and lines, and say so.
    following = flow.create_round(data['brief'], owner, uuid.uuid4().hex)
    drain(data['pending'])
    following.refresh_from_db()
    taste = json.loads((flow.round_root(following) / 'taste.json').read_text())['entries']
    assert [row['kind'] for row in taste] == ['board', 'none_of_these', 'none_of_these', 'design']
    assert taste[-1]['reason'] == record.pick['reason'] and following.artifacts['boards']['taste_used'] == 4
    assert 'THE OWNER’S PAST PICKS' in sent['text'][-1] and 'The three stands look alike' in sent['text'][-1]
    # the owner's $2 rules hold for the whole round, picks and "None of these" included (2026-10-29)
    record.refresh_from_db()
    from apps.pipeline.services.round_calls import COST_RULES, LIGHT_TEXT_MODEL, SKETCH_QUALITY
    assert record.artifacts['cost_rules'] == COST_RULES
    root = flow.round_root(record)
    assert json.loads((root / 'research' / 'notes-call.request.json').read_text())['model'] == LIGHT_TEXT_MODEL
    sketches = [json.loads(path.read_text()) for path in (root / 'designs').rglob('image-call.request.json')]
    boards = [json.loads(path.read_text()) for path in (root / 'boards').rglob('image-call.request.json')]
    assert sketches and boards and {r['quality'] for r in sketches + boards} == {SKETCH_QUALITY}


@pytest.mark.django_db(transaction=True)
def test_designer_break_is_logged_and_owner_retry_continues(designer, owner, monkeypatch):
    replies, valid_reply = [], _designer_reply

    def broken_once(prompt):
        if prompt.startswith('You are a senior packaging') and not replies:
            replies.append('broken')
            return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{"category": ""}'}],
                    'usage': {'input_tokens': 900, 'output_tokens': 70}}
        return valid_reply(prompt)

    monkeypatch.setitem(globals(), '_designer_reply', broken_once)
    record = flow.create_round(designer['brief'], owner, uuid.uuid4().hex)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'failed' and record.current_step == 'research'
    breaks = (flow.round_root(record).parent / 'BREAKS.md').read_text()
    assert f'{record.slug} — research' in breaks and 'Research needs its category' in breaks
    # the owner's ruling of 2026-10-29: the first Retry checks the same paid reply again at $0 — our check still refuses
    # it — and only the next Retry buys a new reply
    calls = scoped_spend(record)['calls']
    flow.retry_round(record.pk, owner)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'failed' and scoped_spend(record)['calls'] == calls, record.error_message
    flow.retry_round(record.pk, owner)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick', record.error_message
    assert scoped_spend(record)['calls'] > calls


@pytest.mark.django_db
def test_designer_library_matches_house_previews_by_words_and_colours(settings, monkeypatch, tmp_path):
    from apps.pipeline.services import round_designer, round_designer as round_ideas_brief
    previews = library_fixture(tmp_path, settings, monkeypatch)
    brief = round_ideas_brief.gloss_brief()
    library = round_designer.library_matches(brief)
    assert 'gloss' in library['words'] and 'square' not in library['words']
    assert library['colours'] == ['#C9707A', '#8E4A5C', '#C2553A']
    matches = library['matches']
    assert [row['sha256'][0] for row in matches] == ['1', '2', '3', '4']  # No font, nothing quarantined.
    assert all(Path(row['preview_path']).parent == previews and len(row['preview_sha256']) == 64 for row in matches)
    assert [row['may_reference'] for row in matches] == [True, True, False, False]
    # The real guard decides at research time: a preview it refuses stays words only, with its reason.
    from apps.pipeline.services import round_calls as image_guard
    monkeypatch.setattr(image_guard, 'denylist', lambda **kwargs: {'rejected': {matches[1]['preview_sha256']: 'a made design'}, 'web': {}})
    refused = round_designer.library_matches(brief)['matches']
    assert refused[1]['may_reference'] is False and 'D-D8-2' in refused[1]['why_words_only']


class _Refused(Exception):
    """A provider 403 as the SDK raises it: unbilled, carrying its status code."""
    status_code = 403


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('failure', ['http', 'no_key'])
def test_designer_tavily_failure_carries_on_with_library_and_knowledge_and_says_so(designer, owner, settings, failure):
    from django.test import Client

    class Down:
        status_code, headers, content = 503, {}, b'{}'

        def json(self):
            return {}
    if failure == 'http':
        designer['sent']['tavily_reply'] = lambda query: Down()
    else:
        settings.WEB_SEARCH_API_KEY = ''
    record = flow.create_round(designer['brief'], owner, uuid.uuid4().hex)
    drain(designer['pending'])
    record.refresh_from_db()
    research = record.artifacts['research']
    assert record.state == 'awaiting_board_pick' and research['web_search'] == 'unavailable'
    assert research['sources'] == [] and research['library']['matches'] and [row['status'] for row in research['searches']] == ['failed'] * 6
    assert 'Web search is unavailable for this round' in designer['sent']['text'][0]
    assert not any('tools' in body for body in designer['sent']['requests'])
    owner.is_superuser = True
    owner.save()
    page = Client()
    page.force_login(owner)
    html = page.get(f'/dashboard/rounds/{record.pk}/research/', HTTP_HOST='127.0.0.1', secure=True).content.decode()
    assert 'Web search unavailable' in html and 'no web source for this round' in html


@pytest.mark.django_db(transaction=True)
def test_designer_research_refused_by_the_api_stops_in_words_and_retry_does_not_search_twice(designer, owner, monkeypatch):
    valid_reply = _designer_reply

    def refused(prompt):
        if prompt.startswith('You are a senior packaging'):
            raise _Refused('Error code: 403 - Request not allowed')
        return valid_reply(prompt)

    monkeypatch.setitem(globals(), '_designer_reply', refused)
    record = flow.create_round(designer['brief'], owner, uuid.uuid4().hex)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'failed' and 'VPN' in record.error_message and '403' in record.error_message
    assert 'Request not allowed' in (flow.round_root(record).parent / 'BREAKS.md').read_text()
    monkeypatch.setitem(globals(), '_designer_reply', valid_reply)  # The network is back.
    flow.retry_round(record.pk, owner)
    drain(designer['pending'])
    record.refresh_from_db()
    assert record.state == 'awaiting_board_pick' and record.artifacts['research']['web_search'] == 'used'
    assert len(designer['sent']['tavily']) == 6  # The saved searches are read again, never bought twice.


# --- the owner's round-4 faults (2026-10-29) ------------------------------------------------------------------------

ROUND_4_LINES = ('Millefleur tapestry: a doe wandering through dense, woven blooms. No roses, petals or arches: use fig, '
                 'ember, wildflowers and leaves instead. Keep a clear window so the gloss colour shows through.',
                 'D2: three woven bloom bands, one per shade. Replace every rose with fig, ember or wildflowers (roses '
                 'are banned). Decorate the bottle as well.')


def test_one_banned_list_from_the_brief_the_standing_list_and_the_owner_s_own_lines():
    """The owner's standing list (roses, petals, arches, lips, kisses, drips, splashes, honey, bees), the brief's own and
    each motif a reason line bans, one entry per motif; the scan reads words, so a shade called Rose Glass, the
    product's "Lip gloss", a rosette or an "archaic" serif is never a banned motif, and "arched" or "honeycomb" is."""
    from apps.pipeline.services import round_designer as rd
    from apps.pipeline.services.round_designer import gloss_brief
    assert rd.owner_bans(ROUND_4_LINES) == ['roses', 'petals', 'arches', 'rose']
    assert rd.owner_bans(['No gold, no text.', 'not flat colour blocks, single hallmarks or plain frosted windows']) == [
        'gold', 'text']
    banned = rd.banned_motifs(gloss_brief(), ROUND_4_LINES + ('Without butterflies.',))
    assert set(rd.HOUSE_BANNED) <= set(banned) and 'butterflies' in banned and 'rose' not in banned
    allowed = ['Lip gloss', 'Rose Glass']
    for text, seen in (('Banded figs, rosettes, roses and a framed leaping deer; no banned motifs.', ['roses']),
                       ('Lip gloss in Rose Glass with a rose gold cap', []), ('Calligraphic, slightly archaic serif', []),
                       ('an arched header', ['arches']), ('a honeycomb lattice', ['honey']),
                       ('five-petal wildflowers', []), ('scattered petals', ['petals']), ('a bumblebee', ['bees'])):
        assert [word for word in rd.banned_seen(text, banned, allowed) if word in rd.HOUSE_BANNED] == seen, text


@pytest.mark.parametrize('text, expected', [
    ('Only fans, sunbursts and stepped frames; no roses, petals, arches, lips, drips or bees.', []),
    ('Stepped ziggurat frames and sunbursts, not arches; no banned motifs.', []),
    ('Neither roses nor petals.', []),
    ('Only deco frames and fans; no roses, petals, arches, lips, drips, honey or bees seen.', []),
    ('No roses or petals visible.', []),
    ('No roses, petals or arches; bees decorate the side.', ['bees']),
    ('No roses or petals, but an arched header is present.', ['arches']),
    ('No roses. Honeycomb bands decorate it.', ['honey']),
    ('Roses; no banned motifs.', ['roses']),
    ('Not only roses.', ['roses']),
    ('Not without roses.', ['roses']),
    ('Not free of roses.', ['roses']),
    ('No roses, bees decorate the side.', ['roses', 'bees']),
])
def test_banned_motif_reading_preserves_negation_and_positive_assertions(text, expected):
    from apps.pipeline.services import round_designer as rd
    assert rd.banned_seen(text, list(rd.HOUSE_BANNED)) == expected


@pytest.mark.parametrize('positive_field', [None, 'motifs', 'idea', 'bottle'])
def test_a_negative_check_note_cannot_hide_another_fields_positive_motif(positive_field):
    from apps.pipeline.services import round_designer as rd
    row = {'motifs': ['sunbursts'], **{check: {'ok': True, 'note': 'Fine'} for check, _ in rd.CHECKS}}
    row['banned']['note'] = 'No roses, petals or arches'
    source = {'idea': 'Sunbursts', 'bottle': 'Gold print on clear glass', 'bottle_net': 'bottle.png'}
    if positive_field == 'motifs':
        row['motifs'].append('roses')
    elif positive_field:
        source[positive_field] = 'Roses printed on the surface'
    findings = rd._findings({'designs': {'D4': row}}, ['D4'], {'D4': source}, list(rd.HOUSE_BANNED))['D4']
    assert findings[0]['ok'] is (positive_field is None)
    if positive_field:
        assert findings[0]['seen'] == ['roses']


def test_a_design_that_shows_a_banned_motif_an_unpainted_face_or_a_plain_bottle_fails_whatever_the_reading_says():
    """Round 4: the check said "ok" beside "roses" (D1, D2) and D3 reached the page with half-painted walls. The words
    decide: a banned motif named in the reading or the design's own lines fails "banned"; a face under the reliable-crop
    coverage fails "faces"; no painted bottle, or a bottle line naming no print, engraving or foil, fails "bottle"."""
    from apps.pipeline.services import round_designer as rd
    ids = ['D1', 'D2', 'D3']
    payload = {'designs': {key: {'motifs': ['figs', 'deer'], **{check: {'ok': True, 'note': 'Fine'} for check, _ in rd.CHECKS}}
                           for key in ids}}
    payload['designs']['D2']['banned'] = {'ok': True, 'note': 'Banded figs, rosettes, roses; no banned motifs.'}
    full = {'front panel': 1.0, 'left side': 0.94, 'right side': 0.94}
    sources = {'D1': {'idea': 'A doe walks the stand', 'bottle': 'A woven band printed on the clear body',
                      'bottle_net': 'x.png', 'proof': {'coverage': full}},
               'D2': {'idea': 'Three bloom registers', 'bottle': 'Foil on the cap', 'bottle_net': 'x.png',
                      'proof': {'coverage': full}},
               'D3': {'idea': 'A doe under a fig tree', 'bottle': 'The gloss shows', 'bottle_net': 'x.png',
                      'proof': {'coverage': dict(full, **{'left side': 0.5134})}}}
    findings = rd._findings(payload, ids, sources, list(rd.HOUSE_BANNED), ['Lip gloss', 'Rose Glass'])
    assert rd._failed(findings['D1']) == []
    failed = {key: [row['check'] for row in rd._failed(findings[key])] for key in ids}
    assert failed == {'D1': [], 'D2': ['banned'], 'D3': ['faces', 'bottle']}
    assert findings['D2'][0]['note'].startswith('Shows roses, banned.')
    assert 'left side 51% painted' in findings['D3'][2]['note']
    del sources['D1']['bottle_net']
    assert [row['check'] for row in rd._failed(rd._findings(payload, ids, sources, [], [])['D1'])] == ['bottle']


@pytest.mark.parametrize('mode', ['default', 'extra', 'budget_stop'])
def test_extra_check_repairs_are_round_scoped_resumable_and_keep_budget_stops(tmp_path, monkeypatch, mode):
    from types import SimpleNamespace
    from apps.pipeline.services import round_designer as rd
    from apps.pipeline.services.cost_ledger import BudgetExceededError

    candidates = {}
    for key in ('D4', 'D5', 'D6'):
        source = {'id': key, **{line: 'Fixture design' for line in rd.DESIGN_LINES}, 'continuity': {},
                  'proof': {'outside': {'differing_from_template': 0, 'pixels': 1},
                            'registration': {'best_shift_px': [0, 0]},
                            'pdf': {layer: {'max_mm': 0} for layer in ('CUT', 'CREASE', 'ARTWORK')}}}
        for role in (*rd.FLAT_VIEWS, 'flat'):
            source[role], source[role + '_sha256'] = f'{key}/{role}.png', 'fixture-pin'
        candidates[key] = source
    made = {'generation': 2, 'board': 'bold', 'order': list(candidates), 'candidates': candidates,
            'die': {'sheet': 'sheet.png', 'sheet_sha256': 'fixture-pin'}}
    artifacts = {'designs': made, 'image_attempts_limited_by_budget': mode != 'default'}
    ctx = SimpleNamespace(root=tmp_path, round=SimpleNamespace(artifacts=artifacts), brief={})
    flow.write_json(tmp_path / 'designs/g2/designs.json', made)
    flow.write_json(tmp_path / 'board-pick.json', {'id': 'bold'})
    monkeypatch.setattr(rd, 'generation', lambda *args: 2)
    monkeypatch.setattr(rd, 'round_banned', lambda *args, **kwargs: [])
    monkeypatch.setattr(rd, 'taste_bans', lambda *args: [])
    monkeypatch.setattr(rd, 'motif_allowed', lambda *args: [])
    monkeypatch.setattr(rd, 'die_first', lambda *args: ({}, {}))
    monkeypatch.setattr(rd, 'design_rules', lambda *args: '')
    checks, repairs = [], []

    def check(context, folder, operation, sources, banned, allowed, name):
        checks.append(name)
        return {key: [{'check': 'faces', 'label': 'Every printed face painted', 'note': 'Fixture coverage',
                       'ok': key != 'D5' or operation.endswith('/redraw-2')}] for key in sources}

    def paint(context, number, row, picked, setup, geometry, out, **kwargs):
        repairs.append((row['id'], out.name, kwargs['suffix']))
        if mode == 'budget_stop' and out.name == 'redraw-2':
            raise BudgetExceededError('fixture dollar cap')
        return dict(candidates[row['id']], picture=str(out.relative_to(tmp_path) / 'view.png'))

    monkeypatch.setattr(rd, '_check', check)
    monkeypatch.setattr(rd, '_paint_design', paint)
    if mode == 'budget_stop':
        with pytest.raises(BudgetExceededError, match='dollar cap'):
            rd.pick_page(ctx)
        assert not (tmp_path / 'publication.json').exists()
    else:
        result = rd.pick_page(ctx)
        assert result['order'] == (['D4', 'D6'] if mode == 'default' else ['D4', 'D5', 'D6'])
        assert list(result['dropped']) == (['D5'] if mode == 'default' else [])
    assert repairs == ([('D5', 'redraw', '/redraw')] +
                       ([] if mode == 'default' else [('D5', 'redraw-2', '/redraw-2')]))
    assert checks[:2] == ['check-call.json', 'check-redraw-call.json']
    if mode == 'extra':
        assert checks[2] == 'check-redraw-2-call.json'


def test_taste_memory_keeps_every_none_of_these_line_and_every_banned_motif_for_the_next_round(owner, monkeypatch, tmp_path):
    """The owner, 2026-10-29: taste memory stores every "None of these" reason and every banned motif from the reason
    lines, and the next round's first boards avoid them; a rejected round is never read."""
    from apps.pipeline.services import round_designer as rd
    from apps.pipeline.services.round_designer import gloss_brief
    monkeypatch.setattr(flow, 'round_root', lambda record: tmp_path / record.slug)
    past = Round.objects.create(slug='past-round', request_key='k' * 64, product_brief=gloss_brief(), created_by=owner,
                                state='complete', artifacts={'board_choice': {'reason': ROUND_4_LINES[0]},
                                                             'redo': {'boards': {'line': 'Too basic; no honey.'}}},
                                pick={'id': 'D2', 'reason': ROUND_4_LINES[1]})
    (tmp_path / past.slug / 'boards' / 'g2').mkdir(parents=True)
    (tmp_path / past.slug / 'boards' / 'g2' / 'redo.json').write_text(json.dumps({'line': 'The first line: no bees.'}))
    Round.objects.create(slug='rejected-round', request_key='r' * 64, product_brief=gloss_brief(), created_by=owner,
                         artifacts={'rejected': {'at': 'x'}, 'board_choice': {'reason': 'No butterflies.'}})
    later = Round.objects.create(slug='later-round', request_key='l' * 64, product_brief=gloss_brief(), created_by=owner)
    entries = rd.taste_entries(owner.pk, later.pk)
    assert [row['reason'] for row in entries if row['kind'] == 'none_of_these'] == ['The first line: no bees.',
                                                                                    'Too basic; no honey.']
    assert rd.taste_banned(owner.pk, later.pk) == ['bees', 'honey', 'roses', 'petals', 'arches', 'rose']
    assert 'butterflies' not in rd.taste_banned(owner.pk, later.pk)
    words = rd.boards_prompt(gloss_brief(), {'category': '', 'sources': [], **{key: [] for key in rd.RESEARCH_LISTS}},
                             entries, banned=rd.banned_motifs(gloss_brief(), extra=rd.taste_banned(owner.pk, later.pk)))
    assert 'BANNED MOTIFS (the owner\'s hard rule, above every other line)' in words and '"roses"' in words


def test_an_image_account_with_no_credits_is_said_in_words_and_no_other_face_is_sent(owner):
    """Round 4: OpenAI refused five faces with "credit_balance_exhausted" (429, billed nothing); the page and the top
    bar said "could not be drawn this time". The refusal is named, and once met no other face's call is sent."""
    from apps.pipeline.services import round_files_gate as gate
    error = ("RateLimitError: Error code: 429 - {'error': {'message': 'You have no credits remaining.', 'type': "
             "'insufficient_quota', 'code': 'credit_balance_exhausted'}}")
    assert gate.out_of_credits(error) and gate.plain_error(error) == gate.NO_CREDITS_WORDS
    assert gate.out_of_credits('Not sent: ' + error) and not gate.out_of_credits('RateLimitError: slow down')
    assert 'Add credits to the OpenAI account, then press Redraw' in gate.NO_CREDITS_WORDS


def test_a_read_only_publication_record_is_history_not_a_stalled_design(owner):
    """Needs attention 2 (round 4): task 158, HAYAT's read-only master publication, made queued by its page (now in
    archive/) and never meant to run, counted as "never started". Its own marker folds it."""
    from types import SimpleNamespace
    from apps.dashboard import board
    task = SimpleNamespace(pk=10_158, options={'publication_only': True, 'spend_held': True}, project_id=None,
                           project=None, created_at=None)
    assert board.fold_of(task) == 'publication record'
    assert board.FOLD_GROUP_WORDS['publication record'] == 'Read-only publication records'
