"""Real generic media steps with deterministic fake providers, no design inputs."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw

from apps.pipeline.services import round_product as product
from apps.pipeline.services import round_sheet as sheet
from apps.pipeline.services import round_steps as steps
from apps.pipeline.services import round_balm_sheet
from apps.pipeline.services.round_balm_calls import write, sha
from apps.pipeline.services.whole_object_check import COPY_KEYS


class FakeContext:
    """Calls emit only fixture records under pytest's isolated temporary root."""
    def __init__(self, root, brief=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.brief = product.normalize_brief(brief or product.lip_gloss_brief())
        self.round = SimpleNamespace(marks={})
        self.image_calls = []
        self.text_calls = []

    def text_call(self, operation, prompt, destination, **kwargs):
        destination = Path(destination)
        if destination.exists():
            return steps.read(destination)
        self.text_calls.append((operation, prompt, kwargs))
        payload = fake_payload(operation, prompt, self.root)
        result = {'payload': payload, 'status': 'complete', 'accounted_usd': 0}
        write(destination, result)
        return result

    def image_call(self, operation, prompt, destination, **kwargs):
        self.image_calls.append((operation, prompt, kwargs))
        destination.mkdir(parents=True, exist_ok=True)
        # Deliberately modifies protected pixels too: the real compositing
        # path, not this fake, must enforce the owner's preservation contract.
        image = Image.new('RGBA', (1536, 1024), (len(self.image_calls)*7 % 255, 50, 90, 255))
        image.save(destination/'raw.png')
        return {'status': 'complete', 'fixture': True, 'accounted_usd': 0}

    def reject_result(self, destination, reason):
        result = steps.read(destination)
        result.update(status='validation_failed', validation_error=reason)
        write(destination, result)


def typed_gloss_brief():
    brief = product.lip_gloss_brief()
    return product.classify_intake(brief, {key: product.DEFAULT_COPY_ROLES[key] for key in brief['copy']})


def test_content_roles_are_complete_explicit_and_do_not_upgrade_legacy_briefs():
    legacy = product.normalize_brief(product.lip_gloss_brief())
    assert not product.typed_content(legacy)
    assert 'content_roles' not in legacy and 'prompt_contract' not in legacy
    typed = typed_gloss_brief()
    assert set(typed['content_roles']) == set(product.content_fields(typed))
    assert product.normalize_brief(typed) == typed
    assert 'copy.collection' not in product.printed_copy(typed)
    assert product.printed_copy(typed)['shades.0.name'] == 'Rose Glass'
    assert 'shades.1.name' not in product.printed_copy(typed) and 'shades.2.name' not in product.printed_copy(typed)
    for change in ('missing', 'unknown', 'bad_role', 'geometry_as_copy', 'bad_contract'):
        broken = json.loads(json.dumps(typed))
        if change == 'missing':
            del broken['content_roles']['copy.leaflet']
        elif change == 'unknown':
            broken['content_roles']['copy.undeclared'] = 'COPY'
        elif change == 'bad_role':
            broken['content_roles']['copy.leaflet'] = 'INFER'
        elif change == 'geometry_as_copy':
            broken['content_roles']['dimensions_mm.width'] = 'COPY'
        else:
            broken['prompt_contract'] = 'unknown'
        with pytest.raises(ValueError):
            product.normalize_brief(broken)
    assert 'prompt_contract' not in product.legacy_balm_brief()


def assert_only_typed_copy_is_quoted(prompt, brief):
    import re
    before, rest = prompt.split(steps.COPY_START)
    block, after = rest.split(steps.COPY_END)
    expected = product.printed_copy(brief)
    actual = {line.split(': ', 1)[0]: json.loads(line.split(': ', 1)[1])
              for line in block.strip().splitlines()}
    assert actual == expected
    assert not re.search(r'["“”‘’\u00ab\u00bb]', before + after)
    for path, value in product.content_fields(brief).items():
        if brief['content_roles'][path] == 'INSTRUCTION' and isinstance(value, str) and len(value) > 15:
            assert json.dumps(value, ensure_ascii=False) not in block


def test_each_clear_body_face_has_its_own_print_and_clear_instruction():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='typed-round-prompt-') as folder:
        ctx = FakeContext(folder, typed_gloss_brief())
        sheet.build(ctx.brief, ctx.root)
        seed = {'seed': 'A “quoted directive” that must never become lettering',
                'link': 'because a lip gloss reveals colour', 'opaque_zones': []}
        prompt = steps._image_words(ctx, seed)
        assert_only_typed_copy_is_quoted(prompt, ctx.brief)
        print_lines = []
        for key in steps.BODY_IDS:
            line = next(line for line in prompt.splitlines() if line.startswith(key+' — PRINT:'))
            print_lines.append(line.split(' — PRINT:', 1)[1])
            clear = next(line for line in prompt.splitlines() if line.startswith(key+' — STAYS CLEAR:'))
            assert '#C9707A' in clear and 'liquid must be visible' in clear
            assert 'Printable interior=' in line
        assert len(set(print_lines)) == 4
        assert 'not the same stripe/logo on every side' in prompt
        assert 'An original collection name' in prompt
        assert 'Full EN / ES / AR drafts' in prompt
        assert 'Only COPY values are quoted lettering' in prompt


def measured_fixture_faces(root, picture):
    """Diagnostic for synthetic ink masks, not optical transparency or model quality."""
    record = steps.read(root/'sheet.json')
    image = Image.open(picture).convert('RGB')
    shade = np.array(tuple(bytes.fromhex(record['shade']['hex'][1:])))
    masks, faces = {}, {}
    for key in steps.BODY_IDS:
        crop = np.asarray(image.crop(record['panels'][key]['printable_box_px']))
        ink = np.any(crop != shade, axis=2)
        print_share = float(ink.mean())
        clear_share = float((~ink).mean())
        masks[key] = np.asarray(Image.fromarray(ink.astype('uint8')*255).resize((64, 256), Image.Resampling.NEAREST)) > 0
        faces[key] = {'partly_clear': print_share >= .01 and clear_share >= .20,
                      'liquid_visible': clear_share >= .20,
                      'evidence': f'Fixture printable interior: ink {print_share:.4f}, unchanged liquid {clear_share:.4f}.',
                      'print_share': print_share, 'unchanged_liquid_share': clear_share}
    differences = [float(np.mean(masks[a] != masks[b])) for a, b in steps.combinations(steps.BODY_IDS, 2)]
    return {'distinct': min(differences) > .03, 'identical_on_all_four': max(differences) <= .03,
            'comparison_evidence': 'Synthetic interior ink-mask differences; shared protected edges excluded.',
            'faces': faces, 'pairwise_ink_mask_difference': differences}


class TypedImageFixture(FakeContext):
    def image_call(self, operation, prompt, destination, **kwargs):
        self.image_calls.append((operation, prompt, kwargs))
        destination.mkdir(parents=True, exist_ok=True)
        # Draw deterministic raw fixture pixels, then let the real compositor
        # enforce masks. Four injected defects test that edges do not count.
        image = Image.open(self.root/'sheet.png').convert('RGBA')
        draw = ImageDraw.Draw(image)
        panels = steps.read(self.root/'sheet.json')['panels']
        key = operation.removeprefix('image/')
        defect = key if '/' not in key else ''
        for index, name in enumerate(steps.BODY_IDS):
            x0, y0, x1, y1 = panels[name]['printable_box_px']
            w, h = x1-x0, y1-y0
            fill = '#173B46'
            if defect == 'D5' or (defect == 'D3' and index == 2):
                draw.rectangle((x0, y0, x1-1, y1-1), fill=fill)
            elif defect == 'D4' and index == 3:
                continue
            elif defect == 'D2' or index == 0:
                draw.rectangle((x0+w//5, y0+h//6, x0+4*w//5, y0+h//3), fill=fill)
            elif index == 1:
                draw.rectangle((x0+w//8, y0+2*h//3, x0+3*w//8, y0+5*h//6), fill=fill)
                draw.rectangle((x0+5*w//8, y0+h//2, x0+7*w//8, y0+2*h//3), fill=fill)
            elif index == 2:
                draw.line((x0+w//4, y0+h//5, x0+3*w//4, y0+h//2, x0+w//3, y0+4*h//5), fill=fill, width=max(3,w//10))
            else:
                for row in (1, 3, 5, 7):
                    draw.rectangle((x0+2*w//5, y0+row*h//9, x0+4*w//5, y0+(row+1)*h//9), fill=fill)
        image.save(destination/'raw.png')
        return {'status': 'complete', 'fixture': True, 'accounted_usd': 0}

    def text_call(self, operation, prompt, destination, **kwargs):
        if not operation.startswith('check/'):
            return super().text_call(operation, prompt, destination, **kwargs)
        self.text_calls.append((operation, prompt, kwargs))
        key = operation.removeprefix('check/')
        payload = fake_payload(operation, prompt, self.root)
        payload['copy_presence'] = dict.fromkeys(product.printed_copy(self.brief), 'present')
        payload['instruction_text_printed'] = []
        payload['body_face_audit'] = measured_fixture_faces(self.root, steps._candidate_dir(self, key)/'picture.png')
        result = {'payload': payload, 'status': 'complete', 'accounted_usd': 0}
        write(destination, result)
        return result


def test_typed_twenty_fixture_sketches_measure_distinct_partly_clear_faces(tmp_path):
    ctx = TypedImageFixture(tmp_path, typed_gloss_brief())
    for step in ('seeds', 'sheet', 'sketches', 'checks'):
        result = steps.run_step(step, ctx)
    summary = result['body_face_summary']
    assert summary['assessed'] == 20
    assert summary['distinct_partly_clear'] == 16 and summary['share'] == .8
    assert len(result['eligible']) == 20, 'Material observations remain jury findings, not disqualifications.'
    assert not result['results']['D2']['body_face_audit']['distinct']
    assert not result['results']['D3']['body_face_audit']['faces']['body_left']['liquid_visible']
    assert not result['results']['D4']['body_face_audit']['faces']['body_right']['partly_clear']
    assert not result['results']['D5']['body_face_audit']['distinct_partly_clear']
    assert any('body faces identical on all four sides' in v for v in result['results']['D2']['findings'])
    assert any('liquid not visible' in v for v in result['results']['D3']['findings'])
    for _, prompt, _ in ctx.image_calls:
        assert_only_typed_copy_is_quoted(prompt, ctx.brief)
    for operation, prompt, _ in ctx.text_calls:
        if operation.startswith('check/'):
            assert 'instruction_text_printed' in prompt and 'body_face_audit' in prompt
            assert 'copy.leaflet' not in prompt.split('COPY KEYS: ', 1)[1].split('\n', 1)[0]
    report = {'schema': 'typed_round_fixture_measurement/1', 'provider_calls': 0, 'spend_usd': 0,
              'summary': summary, 'positive_controls': 16, 'injected_defects': ['D2','D3','D4','D5'],
              'method': 'Compare ink and unchanged shade pixels inside each printable interior, excluding protected borders; compare six pairs on a common diagnostic grid.',
              'limitation': 'Deterministic fixture retention and diagnostic coverage, not model compliance or optical transparency.',
              'candidates': {key: {'body_face_audit': value['body_face_audit'], 'findings': value['findings'],
                  'picture_sha256': sha(ctx.root/'sketches'/key/'picture.png')} for key, value in result['results'].items()}}
    write(ctx.root/'fixture-measurement.json', report)


def test_typed_sketch_fork_and_direct_edit_never_quote_instruction_fields(tmp_path):
    ctx = TypedImageFixture(tmp_path, typed_gloss_brief())
    for step in ('seeds', 'sheet', 'sketches', 'checks', 'readings'):
        steps.run_step(step, ctx)
    ctx.round.marks = {'marks': [{'id': 'A1', 'preserve': 'Keep the "visible interval" on body_front'}]}
    write(ctx.root/'marks.json', ctx.round.marks)
    steps.run_step('forks', ctx)
    prompt = steps._image_words(ctx) + '\nINSTRUCTION: do not print "a quoted editing directive".'
    steps._edit(ctx, 'D5/B', prompt, parent=ctx.root/'sketches/D5/picture.png', mask=ctx.root/'sheet-mask.png')
    assert any(operation.count('/') == 2 for operation, _, _ in ctx.image_calls)
    assert len(ctx.image_calls) == 23
    for operation, words, _ in ctx.image_calls:
        assert_only_typed_copy_is_quoted(words, ctx.brief)
    calls_before = len(ctx.image_calls)
    bad = prompt.replace('copy.brand: "BBROSE"', 'copy.brand: "An original collection name"')
    with pytest.raises(ValueError, match='explicitly typed COPY'):
        steps._edit(ctx, 'D4/B', bad, parent=ctx.root/'sketches/D4/picture.png')
    assert len(ctx.image_calls) == calls_before


def test_instruction_leakage_finding_is_preserved_for_jury_without_disqualification(tmp_path):
    ctx = TypedImageFixture(tmp_path, typed_gloss_brief())
    for step in ('seeds', 'sheet', 'sketches', 'checks', 'readings'):
        steps.run_step(step, ctx)
    panels = steps.read(ctx.root/'sheet.json')['panels']
    checked = steps.read(ctx.root/'sketches/A1/whole-object-call.json')['payload']
    checked['instruction_text_printed'] = ['front prints AN ORIGINAL COLLECTION from the naming direction']
    result = steps._inspection_decision(checked, {'qualifies': True}, panels, {},
        copy_keys=tuple(product.printed_copy(ctx.brief)), content_contract=True, body_ids=steps.BODY_IDS)
    assert result['eligible'] and result['reasons'] == []
    assert 'instruction text printed: front prints AN ORIGINAL COLLECTION from the naming direction' in result['findings']
    write(ctx.root/'sketches/A1/whole-object.json', result)
    assert 'instruction text printed' in steps._jury_images(ctx, ['A1'])[0][0]


def test_typed_check_prices_added_instructions_before_reservation(tmp_path, settings, monkeypatch):
    from apps.dashboard.product_round_forms import forms_for, product_brief
    from apps.pipeline.services import round_calls
    from apps.pipeline.tests.test_product_round_page import form_data
    data = form_data()
    for index in range(12):
        data[f'panels-{index}-decoration'] = 'a' * 1000
    data.update(audience='b' * 2000, bar='c' * 2000)
    form, panels, shades = forms_for(data)
    assert form.is_valid() and panels.is_valid() and shades.is_valid()
    ctx = TypedImageFixture(tmp_path/'budget-fixture', product_brief(form, panels, shades))
    steps.seeds(ctx)
    sheet.build(ctx.brief, ctx.root)
    seed = steps.read(ctx.root/'seeds.json')['seeds'][0]
    steps._edit(ctx, 'A1', steps._image_words(ctx, seed))
    steps._check(ctx, 'A1')
    operation, prompt, kwargs = ctx.text_calls[-1]
    settings.ROUND_ARTIFACT_ROOT = tmp_path
    paid = round_calls.RoundContext(SimpleNamespace(slug='budget-fixture', product_brief=ctx.brief))
    class BeforeReservation(Exception):
        pass
    observed = []
    def stop_before_reservation(*args, **request):
        observed.append(request['estimate'])
        raise BeforeReservation
    monkeypatch.setattr(paid, '_request', stop_before_reservation)
    with pytest.raises(BeforeReservation):
        paid.text_call(operation, prompt, ctx.root/'preflight.json', **kwargs)
    assert .50 < observed[0] <= kwargs['ceiling']
    assert not (ctx.root/'preflight.request.json').exists()


@pytest.mark.parametrize('finding', ['generic', 'different design', 'quiet', 'material', 'opaque', 'copy'])
def test_round_material_copy_and_design_findings_do_not_disqualify(tmp_path, finding):
    ctx = FakeContext(tmp_path)
    panels = sheet.build(ctx.brief, tmp_path)['panels']
    payload = fake_payload('check/A1', '', tmp_path)
    if finding in {'generic', 'different design', 'quiet'}:
        payload['panels']['body_front']['state'] = finding
    elif finding == 'material':
        payload['material_issues'] = ['body_front hides the liquid; cap_front is painted blue.']
    elif finding == 'opaque':
        payload['undeclared_opaque_zones'] = ['body_front has an undeclared opaque wrap.']
    else:
        payload['copy_presence']['product_ar'] = 'absent'
    result = steps._inspection_decision(payload, {'qualifies': True}, panels, {})
    assert result['eligible'] and result['reasons'] == []
    assert len(result['findings']) == 1


@pytest.mark.parametrize('failure', ['missing', 'blank', 'banned', 'aspect'])
def test_only_round_hard_failures_disqualify(tmp_path, failure):
    ctx = FakeContext(tmp_path)
    panels = sheet.build(ctx.brief, tmp_path)['panels']
    payload = fake_payload('check/A1', '', tmp_path)
    if failure in {'missing', 'blank'}:
        payload['panels']['body_right']['state'] = failure
        # A critic's after-the-fact explanation is not a prior blank declaration.
        payload['panels']['body_right']['explained_by'] = 'The critic calls this intentional.'
    elif failure == 'banned':
        payload['banned_motifs'] = ['body_right carries a literal rose flower.']
    result = steps._inspection_decision(payload, {'qualifies': failure != 'aspect'}, panels, {})
    assert not result['eligible'] and len(result['reasons']) == 1
    assert result['findings'] == []


def test_declared_blank_and_engine_reserved_caps_are_eligible_but_never_missing(tmp_path):
    brief = product.lip_gloss_brief()
    brief['panels'][3]['blank_reason'] = 'Unprinted face reveals the liquid.'
    ctx = FakeContext(tmp_path, brief)
    panels = sheet.build(ctx.brief, tmp_path)['panels']
    declared = steps._declared_blanks(ctx, panels)
    assert {'body_right', 'cap_front', 'cap_top'} <= set(declared)
    payload = fake_payload('check/A1', '', tmp_path)
    for key in declared:
        payload['panels'][key]['state'] = 'blank'
    result = steps._inspection_decision(payload, {'qualifies': True}, panels, declared)
    assert result['eligible'] and len(result['findings']) == len(declared)
    payload['panels']['cap_front']['state'] = 'missing'
    assert not steps._inspection_decision(payload, {'qualifies': True}, panels, declared)['eligible']


def test_jurors_receive_material_and_copy_findings_with_the_candidate_images(tmp_path):
    ctx = FakeContext(tmp_path)
    panels = sheet.build(ctx.brief, tmp_path)['panels']
    payload = fake_payload('check/A1', '', tmp_path)
    payload['material_issues'] = ['body_front hides the liquid.']
    payload['copy_presence']['product_ar'] = 'absent'
    dest = tmp_path/'sketches/A1'
    write(dest/'whole-object.json', steps._inspection_decision(payload, {'qualifies': True}, panels, {}))
    write(dest/'blind.json', fake_payload('blind/A1', '', tmp_path))
    caption, picture = steps._jury_images(ctx, ['A1'])[0]
    assert picture == dest/'picture.png'
    assert 'body_front hides the liquid.' in caption
    assert 'copy: product_ar: absent' in caption
    assert 'not automatic disqualifications' in caption


@pytest.mark.parametrize('second', [
    'Gold curves wrap the clear bottle like a continuous ribbon',
    'A gold curve wraps around the rose body like a ribbon',
])
def test_readings_step_finishes_after_one_reserved_length_reask(tmp_path, settings, second):
    from unittest.mock import Mock
    from apps.pipeline.services.round_calls import RoundContext, scoped_spend
    settings.ROUND_ARTIFACT_ROOT = tmp_path/'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path/'spend'
    record = SimpleNamespace(pk=999, slug='fixture', product_brief=product.lip_gloss_brief(), budget_usd=25)
    ctx = RoundContext(record, SimpleNamespace(attempts=0))
    sheet.build(ctx.brief, ctx.root)
    dest = ctx.root/'sketches/A1'
    dest.mkdir(parents=True)
    Image.new('RGB', (1536, 1024), 'white').save(dest/'picture.png')
    write(ctx.root/'eligibility.json', {'eligible': ['A1'], 'disqualified': []})
    original = 'A gold curve wraps around the rose body like a ribbon'
    def response(idea):
        payload = fake_payload('blind/A1', '', ctx.root)
        payload['idea_in_ten_words'] = idea
        return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(payload)}],
                'usage': {'input_tokens': 100, 'output_tokens': 100}}
    create = Mock(side_effect=[response(original), response(second)])
    ctx.text_client = SimpleNamespace(messages=SimpleNamespace(create=create))
    result = steps.run_step('readings', ctx)
    reading = result['readings']['A1']
    assert reading['idea_in_ten_words'] == second
    assert reading['over_length'] is (len(second.split()) > 10)
    assert reading['word_count'] == len(second.split()) and reading['length_reasked']
    assert steps.read(dest/'blind.json') == reading
    assert steps.read(dest/'blind-call.json')['status'] == 'complete'
    assert not (ctx.root/'call-validation.jsonl').exists()
    assert create.call_count == 2 and scoped_spend(record)['calls'] == 1
    assert 'exactly ten words' in create.call_args_list[1].kwargs['messages'][0]['content'][-1]['text']
    assert scoped_spend(record)['reserved_usd'] == 0
    replay = RoundContext(record, ctx.job, text_client=ctx.text_client)
    assert steps.run_step('readings', replay) == result
    assert create.call_count == 2


def fake_payload(operation, prompt, root):
    if operation == 'seeds':
        return {'seeds': [{'id': f'{f}{i}', 'family': family, 'seed': f'Stillness {f}{i} in one engraved interval',
                           'link': 'because a lip gloss reveals colour'}
                          for f, family in steps.FAMILIES.items() for i in range(1, 6)]}
    panels = steps.read(root/'sheet.json')['panels']
    if operation.startswith('check/'):
        return {'panels': {p: {'state': 'present', 'evidence': 'A continuous fixture interval', 'explained_by': ''} for p in panels},
                'copy_presence': {k: 'present' for k in COPY_KEYS}, 'banned_motifs': [],
                'material_issues': [], 'opaque_zones': [], 'undeclared_opaque_zones': [], 'object_relationship': 'The interval repeats.'}
    if operation.startswith('blind/'):
        proof = next(p for p in panels if p not in ('front', 'body_front', 'cap_front'))
        return {'idea_in_ten_words': 'Colour measures the interval between gestures', 'proof_panel': proof,
                'proof': 'The interval returns on the other face.', 'preserve': 'The central interval on '+proof}
    if operation.startswith('coarse/'):
        ids = prompt.split('IDs: ')[-1].split(', ')
        return {'order': ids, 'reasons': {k: 'A related face proves its product gesture.' for k in ids},
                'appeal': {k: {'answer': 'uncertain', 'reason': 'Fixture only.'} for k in ids}}
    if operation.startswith('pairwise/'):
        pairs = json.loads(prompt.split('Pairs: ')[-1])
        ids = {k for pair in pairs for k in pair}
        return {'pairs': [{'pair': pair, 'winner': pair[0], 'relationship': 'The other face proves its product gesture.'} for pair in pairs],
                'appeal': {k: {'answer': 'uncertain', 'reason': 'Fixture only.'} for k in ids}}
    if operation.startswith('fragment/'):
        x0, y0, x1, y1 = next(iter(panels.values()))['box_px']
        return {'polygons_px': [[[x0+3, y0+3], [x1-3, y0+3], [x1-3, y0+20], [x0+3, y0+20]]],
                'evidence': 'Visible central interval.', 'intents': {'A': 'The interval binds every panel.', 'B': 'The interval splits the object into opposing halves.'}}
    raise AssertionError('Unexpected fake operation '+operation)


def test_gloss_twelve_panels_common_scale_and_material_grounds(tmp_path):
    brief = product.lip_gloss_brief()
    record = sheet.build(brief, tmp_path)
    proof = sheet.verify(tmp_path)
    assert proof['passes'], proof
    assert proof['panel_count'] == 12
    assert record['schema'] == sheet.SCHEMA == 'round_sheet/2'
    assert list(record['panels']) == record['panel_order'] == [panel['id'] for panel in brief['panels']]
    assert record['panels']['body_front']['mm'] == [15, 70]
    assert record['panels']['cap_front']['mm'] == [15, 30]
    assert record['panels']['cap_top']['mm'] == [15, 15]
    assert record['panels']['front']['mm'] == pytest.approx([16.45, 102.45])
    assert record['panels']['back']['mm'] == pytest.approx([16.45, 103.35])
    assert record['panels']['body_back']['ground_hex'] == '#C9707A'
    assert record['panels']['cap_top']['ground_hex'] == '#CDAA50'
    mask = np.asarray(Image.open(tmp_path/'sheet-mask.png'))[..., 3]
    assert np.all(mask[:25] == 255)
    for key in ('cap_front', 'cap_top'):
        panel = record['panels'][key]
        assert panel['reserved_reason'] and panel['printable_box_px'] is None
        x0, y0, x1, y1 = panel['box_px']
        assert np.all(mask[y0:y1, x0:x1] == 255)
    for key in ('body_front', 'body_back', 'body_left', 'body_right'):
        panel = record['panels'][key]
        assert panel['wall_mm'] == 2.5 and panel['liquid_width_mm'] == 10
        x0, y0, x1, y1 = panel['liquid_box_px']
        assert (x1-x0)/record['px_per_mm'] == pytest.approx(10, abs=.2)


def test_generic_panels_are_not_inferred_from_product_name(tmp_path):
    brief = product.lip_gloss_brief()
    brief.update(name='Other product', shape='', panels=[{'id': 'a_panel', 'width_mm': 25, 'height_mm': 42},
                                             {'id': 'another', 'width_mm': 15, 'height_mm': 33}])
    record = sheet.build(brief, tmp_path)
    assert list(record['panels']) == ['a_panel', 'another']
    assert sheet.verify(tmp_path)['passes']


def test_missing_gloss_face_requires_explicit_brief_repair():
    brief = product.lip_gloss_brief()
    brief['panels'] = [panel for panel in brief['panels'] if panel['id'] != 'body_right']
    left = next(panel for panel in brief['panels'] if panel['id'] == 'body_left')
    left.update(width_mm=16, decoration='Supplied hot foil', blank_reason='Left face intentionally rests.')
    original = json.loads(json.dumps(brief))
    with pytest.raises(ValueError, match='missing: body_right'):
        product.normalize_brief(brief)
    repaired = product.repair_missing_body_right(brief)
    assert brief == original
    right = next(panel for panel in repaired['panels'] if panel['id'] == 'body_right')
    assert right['width_mm'] == 16 and right['decoration'] == 'Supplied hot foil'
    assert 'blank_reason' not in right
    assert [panel['id'] for panel in repaired['panels']] == [panel['id'] for panel in product.lip_gloss_brief()['panels']]
    assert product.repair_missing_body_right(repaired) == repaired
    broken = product.lip_gloss_brief()
    broken['panels'] = [panel for panel in broken['panels'] if panel['id'] != 'cap_top']
    with pytest.raises(ValueError, match='missing: cap_top'):
        product.repair_missing_body_right(broken)


def test_panel_blank_declaration_is_explicit_nonempty_text():
    brief = product.lip_gloss_brief()
    assert all('blank_reason' not in panel for panel in product.normalize_brief(brief)['panels'])
    brief['panels'][0]['blank_reason'] = '  The neighbouring face carries the action.  '
    assert product.normalize_brief(brief)['panels'][0]['blank_reason'] == 'The neighbouring face carries the action.'
    for invalid in ('', '   ', None, 7):
        brief['panels'][0]['blank_reason'] = invalid
        with pytest.raises(ValueError, match='nonempty text reason'):
            product.normalize_brief(brief)


def test_sheet_refuses_missing_resolved_panel_and_old_contract(tmp_path, monkeypatch):
    brief = product.lip_gloss_brief()
    original = sheet.engine_panels
    def omit_right(value):
        panels, coords = original(value)
        return [panel for panel in panels if panel['id'] != 'body_right'], coords
    with monkeypatch.context() as patch:
        patch.setattr(sheet, 'engine_panels', omit_right)
        with pytest.raises(ValueError, match='exact ordered brief panel set'):
            sheet.build(brief, tmp_path)
    assert not (tmp_path/'sheet.json').exists()
    current = sheet.build(brief, tmp_path)
    assert not sheet.needs_repair(current, brief)
    assert not sheet.needs_repair(json.loads(json.dumps(current, sort_keys=True)), brief)
    old = json.loads(json.dumps(current))
    old['schema'] = 'round_sheet/1'
    write(tmp_path/'sheet.json', old)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    assert sheet.needs_repair(old, brief)
    with pytest.raises(ValueError, match='authorized archive and rebuild'):
        sheet.build(brief, tmp_path)
    assert before == {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    current['panels'].pop('body_right')
    write(tmp_path/'sheet.json', current)
    assert sheet.needs_repair(current, brief)
    assert 'panel set differs from ordered brief contract' in sheet.verify(tmp_path)['errors']


def test_material_mask_keeps_gold_clear_walls_highlights_and_liquid_edges(tmp_path):
    record = sheet.build(product.lip_gloss_brief(), tmp_path)
    before = np.asarray(Image.open(tmp_path/'sheet.png').convert('RGBA'))
    raw = tmp_path/'fixture-painted-everywhere.png'
    Image.new('RGBA', sheet.SIZE, '#173CEB').save(raw)
    output = tmp_path/'fixture-protected.png'
    round_balm_sheet.protected_edit(tmp_path/'sheet.png', raw, tmp_path/'sheet-mask.png', output)
    after = np.asarray(Image.open(output).convert('RGBA'))
    for key, panel in record['panels'].items():
        x0, y0, x1, y1 = panel['box_px']
        if panel['surface'] == 'gold_metal':
            assert np.array_equal(before[y0:y1, x0:x1], after[y0:y1, x0:x1]), key
            assert np.unique(before[y0:y1, x0:x1, :3].reshape(-1, 3), axis=0).shape[0] > 5
        elif panel['surface'] == 'clear_acrylic':
            a, b, c, d = panel['printable_box_px']
            editable = np.zeros((y1-y0, x1-x0), dtype=bool)
            editable[b-y0:d-y0, a-x0:c-x0] = True
            assert np.array_equal(before[y0:y1, x0:x1][~editable], after[y0:y1, x0:x1][~editable]), key
            assert np.all(after[(b+d)//2, (a+c)//2, :3] == [23, 60, 235])
            lx0, ly0, lx1, ly1 = panel['liquid_box_px']
            assert np.all(after[(ly0+ly1)//2, lx0, :3] == [201, 112, 122])
            for a, b, c, d in panel['protected_highlight_boxes_px']:
                assert np.array_equal(before[b:d, a:c], after[b:d, a:c]), key


def test_legacy_nine_panel_sheet_replays_historical_paid_v1_blank_bytes(tmp_path):
    source = round_balm_sheet.REPO/'docs/rounds/r1-balm'
    result = sheet.build(product.legacy_balm_brief(), tmp_path)
    assert result['schema'] == 'r1_balm_sheet/1'
    for name, digest in sheet.LEGACY_BLANK_PINS.items():
        assert sha(tmp_path/name) == digest
        assert (tmp_path/name).read_bytes() == (source/name).read_bytes()


def test_legacy_nine_panel_v2_reproduces_current_generator_bytes(tmp_path):
    old, new = tmp_path/'old', tmp_path/'new'
    round_balm_sheet.build(old)
    sheet.build(product.legacy_balm_brief(version=2), new)
    for path in old.iterdir():
        assert path.read_bytes() == (new/path.name).read_bytes(), path.name


def test_fake_fixture_runs_all_media_steps_to_six_without_hand_steps(tmp_path):
    ctx = FakeContext(tmp_path)
    for step in ('seeds', 'sheet', 'sketches', 'checks', 'readings', 'coarse', 'pairwise'):
        steps.run_step(step, ctx)
    assert len(ctx.image_calls) == 20
    publication = steps.read(tmp_path/'publication.json')
    assert len(publication['order']) == 8
    marks = steps.run_step('marks_fallback', ctx)
    write(tmp_path/'marks.json', marks)  # Same payload the marks worker persists.
    for step in ('forks', 'final_pairwise', 'pick_page'):
        result = steps.run_step(step, ctx)
    assert len(ctx.image_calls) == 26
    assert len(result['order']) == 6
    assert result['state'] == 'pick'
    assert all(sha(tmp_path/path) == digest for path, digest in result['files'].items())
    for mark in marks['marks']:
        for fork in ('A', 'B'):
            assert steps.read(tmp_path/'developments'/mark['id']/fork/'fragment-proof.json')['byte_identical']
    # Resuming a completed image stage must not purchase or redraw anything.
    steps.run_step('sketches', ctx)
    assert len(ctx.image_calls) == 26
    for operation, prompt, args in ctx.text_calls:
        if operation.startswith(('coarse/', 'pairwise/')):
            assert 'could it sit on any box?' in prompt
            assert 'Seed:' not in prompt
    assert all('liquid colour #C9707A' in p for _, p, _ in ctx.image_calls)


def test_seed_without_product_truth_link_is_not_sketchable(tmp_path):
    ctx = FakeContext(tmp_path)
    original = ctx.text_call
    def missing_link(*args, **kwargs):
        result = original(*args, **kwargs)
        result['payload']['seeds'][0]['link'] = ''
        return result
    ctx.text_call = missing_link
    with pytest.raises(ValueError, match='product-truth link'):
        steps.run_step('seeds', ctx)
    assert not (tmp_path/'seeds.json').exists()
    assert not ctx.image_calls


def test_final_pool_never_backfills_unmarked_sketches(tmp_path, monkeypatch):
    ctx = FakeContext(tmp_path)
    write(tmp_path/'marks.json', {'marks': [{'id': 'A1', 'preserve': 'interval'}]})
    write(tmp_path/'forks.json', {'results': {'A1/A': {'eligible': True},
        'A1/B': {'eligible': False, 'reasons': ['top_end: blank']}, 'A2/A': {'eligible': True}}})
    write(tmp_path/'cut.json', {'order': ['A1', 'A2', 'A3', 'A4', 'A5', 'B1', 'B2', 'B3']})
    write(tmp_path/'critic-calibration.json', {})
    monkeypatch.setattr(steps, '_pairwise', lambda ctx, ids, stage, rank_sum: {'order': ids})
    result = steps.final_pairwise(ctx)
    assert result['order'] == result['pool'] == ['A1', 'A1/A']
    assert result['added_cut_survivors'] == []
    assert result['pool_summary']['excluded_forks'] == {'A1/B': ['top_end: blank']}
    assert 'Showing all 2' in result['pool_summary']['shortfall_reason']


@pytest.mark.parametrize('extra_panel', [False, True], ids=['actual-ten-noncap', 'eleven-noncap'])
def test_fork_mask_covers_every_noncap_panel_minus_only_the_fragment(tmp_path, extra_panel):
    brief = product.lip_gloss_brief()
    if extra_panel:
        brief['panels'].insert(4, {'id': 'fixture_aux_print', 'label': 'Fixture auxiliary print',
            'surface': 'other', 'width_mm': 15, 'height_mm': 20})
    ctx = FakeContext(tmp_path, brief)
    contract = sheet.build(ctx.brief, tmp_path)
    parent = tmp_path/'sketches/A1/picture.png'; parent.parent.mkdir(parents=True)
    Image.open(tmp_path/'sheet.png').save(parent)
    panels = contract['panels']
    polygons = []
    for key in ('body_front', 'top_end'):
        x0, y0, x1, y1 = panels[key]['printable_box_px']
        polygons.append([[x0+3, y0+3], [x0+(x1-x0)//3, y0+3],
                         [x0+(x1-x0)//3, y0+(y1-y0)//3], [x0+3, y0+(y1-y0)//3]])
    x0, y0, x1, y1 = panels['body_right']['box_px']
    polygons.append([[x0, y0], [x1-1, y0], [x1-1, y1-1], [x0, y1-1]])
    original_call = ctx.text_call
    def localize(operation, prompt, destination, **kwargs):
        result = original_call(operation, prompt, destination, **kwargs)
        result['payload']['polygons_px'] = polygons
        write(destination, result)
        return result
    ctx.text_call = localize
    mark = {'id': 'A1', 'preserve': 'The front fragment, the small top-end mark and the entire right face'}
    fragment = steps._fragment(ctx, mark)
    path = tmp_path/'developments/A1/fragment-mask.png'
    base = np.asarray(Image.open(tmp_path/'sheet-mask.png'))[..., 3] == 0
    polygon_image = Image.new('1', tuple(contract['size_px']))
    draw = ImageDraw.Draw(polygon_image)
    for polygon in polygons:
        draw.polygon([tuple(point) for point in polygon], fill=1)
    protected = np.asarray(polygon_image)
    expected = base & ~protected
    actual = np.asarray(Image.open(path))[..., 3] == 0
    assert np.array_equal(actual, expected), 'No panel pixels outside the fragment may close.'
    noncap = [key for key, panel in panels.items() if panel['surface'] != 'gold_metal']
    assert len(noncap) == (11 if extra_panel else 10)
    for key in noncap:
        x0, y0, x1, y1 = panels[key]['box_px']
        assert actual[y0:y1, x0:x1].any() == (key != 'body_right'), key
        assert np.array_equal(actual[y0:y1, x0:x1], expected[y0:y1, x0:x1]), key
    assert set(fragment['panel_coverage']) == set(panels)
    for key in ('top_end', 'bottom_end'):
        assert fragment['panel_coverage'][key]['fork_editable_pixels'] > 0
    steps._edit(ctx, 'A1/A', 'Fixture complete object edit', parent=parent, mask=path)
    before = np.asarray(Image.open(parent))
    after = np.asarray(Image.open(tmp_path/'developments/A1/A/picture.png'))
    assert np.array_equal(before[~actual], after[~actual]), 'Gold, walls, guides and owner fragments remain byte-identical.'
    assert np.all(np.any(before[actual] != after[actual], axis=1)), 'Every open pixel accepts the hostile fixture edit.'
    write(tmp_path/'break7-fixture-summary.json', {'noncap_panels': noncap, 'coverage': fragment['panel_coverage'],
        'mask_sha256': sha(path), 'exact_base_minus_fragment': True, 'protected_pixels_unchanged': True,
        'provider_calls': 0, 'spend_usd': 0})
    # A changed mask cannot hide behind a correspondingly changed mask digest.
    changed = Image.open(path).convert('RGBA'); changed_draw = ImageDraw.Draw(changed)
    x0, y0, x1, y1 = panels['bottom_end']['box_px']
    changed_draw.rectangle((x0, y0, x1-1, y1-1), fill='white'); changed.save(path)
    fragment['mask_sha256'] = sha(path)
    write(path.with_name('fragment.json'), fragment)
    count = len(ctx.text_calls)
    with pytest.raises(ValueError, match='coverage changed'):
        steps._fragment(ctx, mark)
    assert len(ctx.text_calls) == count


def test_closed_engine_end_panel_is_detected_before_fork_localization(tmp_path):
    ctx = FakeContext(tmp_path)
    contract = sheet.build(ctx.brief, tmp_path)
    path = tmp_path/'sheet-mask.png'
    image = Image.open(path).convert('RGBA'); draw = ImageDraw.Draw(image)
    x0, y0, x1, y1 = contract['panels']['bottom_end']['box_px']
    draw.rectangle((x0, y0, x1-1, y1-1), fill='white'); image.save(path)
    contract['sha256']['sheet-mask.png'] = sha(path)
    write(tmp_path/'sheet.json', contract)
    assert sheet.verify(tmp_path)['passes'], 'Historical sheet verification checked bounds and pins, not panel editability.'
    with pytest.raises(ValueError, match='open every non-gold panel: bottom_end'):
        steps._fragment(ctx, {'id': 'A1', 'preserve': 'A fixture fragment'})
    assert not ctx.text_calls and not ctx.image_calls


@pytest.mark.parametrize('parents', [0, 1, 3])
def test_final_pool_handles_empty_singleton_and_nine_without_padding(tmp_path, monkeypatch, parents):
    ctx = FakeContext(tmp_path)
    marks = [{'id': key, 'preserve': 'interval'} for key in ('A1', 'A2', 'A3')[:parents]]
    results = {mark['id']+'/'+fork: {'eligible': parents == 3, 'reasons': ['top_end: blank'] if parents == 1 else []}
               for mark in marks for fork in ('A', 'B')}
    write(tmp_path/'marks.json', {'marks': marks})
    write(tmp_path/'forks.json', {'results': results})
    write(tmp_path/'critic-calibration.json', {})
    # No cut.json: final ranking must not consult the unmarked pool at all.
    if not parents:
        with pytest.raises(ValueError, match='at least one marked parent'):
            steps.final_pairwise(ctx)
        assert not (tmp_path/'final-order.json').exists() and not ctx.text_calls
        return
    if parents == 3:
        observed = []
        monkeypatch.setattr(steps, '_pairwise', lambda ctx, ids, stage, rank_sum:
            (observed.extend(ids) or {'order': list(reversed(ids))}))
    result = steps.final_pairwise(ctx)
    if parents == 1:
        assert result['order'] == ['A1'] and result['batches'] == [] and not ctx.text_calls
        assert 'Showing all 1' in result['pool_summary']['shortfall_reason']
    else:
        assert len(observed) == len(result['full_order']) == 9
        assert result['order'] == result['full_order'][:6]
        assert result['pool_summary']['shortfall_reason'] == ''


def test_three_disqualified_forks_publish_only_three_marked_family_candidates(tmp_path):
    ctx = FakeContext(tmp_path)
    for step in ('seeds', 'sheet', 'sketches', 'checks', 'readings', 'coarse', 'pairwise'):
        steps.run_step(step, ctx)
    write(tmp_path/'marks.json', {'marks': [{'id': key, 'preserve': 'The central interval on body_back'} for key in ('A1', 'A2')]})
    original = ctx.text_call
    def disqualify_blank_ends(operation, prompt, destination, **kwargs):
        result = original(operation, prompt, destination, **kwargs)
        if operation in ('check/A1/A', 'check/A1/B', 'check/A2/B'):
            result['payload']['panels']['top_end'].update(state='blank', evidence='Undeclared blank end.')
            write(destination, result)
        return result
    ctx.text_call = disqualify_blank_ends
    steps.forks(ctx)
    ranked = steps.final_pairwise(ctx)
    published = steps.pick_page(ctx)
    assert set(published['order']) == {'A1', 'A2', 'A2/A'}
    assert len(ranked['pool_summary']['excluded_forks']) == 3
    assert published['pool_summary'] == ranked['pool_summary']
    assert 'Showing all 3' in published['pool_summary']['shortfall_reason']
    assert 'Forks disqualified: 3' in published['pool_summary']['shortfall_reason']
    assert all(sha(tmp_path/path) == digest for path, digest in published['files'].items())
    for operation, prompt, kwargs in ctx.text_calls:
        if operation.startswith('pairwise/final/'):
            assert {caption.split(':', 1)[0] for caption, _ in kwargs['images']} <= {'A1', 'A2', 'A2/A'}
    write(tmp_path/'break8-fixture-summary.json', {'pool': ranked['pool'], 'shown': published['order'],
        'summary': published['pool_summary'], 'provider_calls': 0, 'spend_usd': 0})


def test_duplicate_panels_and_invalid_hex_refused_before_provider():
    brief = product.lip_gloss_brief(); brief['shades'][0]['hex'] = 'rose'
    with pytest.raises(ValueError, match='RRGGBB'):
        product.normalize_brief(brief)
    brief = product.lip_gloss_brief(); brief['panels'][1]['id'] = 'body_front'
    with pytest.raises(ValueError, match='distinct'):
        product.normalize_brief(brief)


def test_opaque_zones_require_preregistered_material_exception(tmp_path):
    ctx = FakeContext(tmp_path)
    steps.run_step('sheet', ctx)
    seed = {'seed': 'Quiet colour, one concealed interval', 'link': 'because a lip gloss reveals colour'}
    assert 'Preregistered deliberate opaque zones: []' in steps._image_words(ctx, seed)
    seed['opaque_zones'] = [{'panel': 'body_left', 'zone': 'small lower strip', 'reason': 'Hides one interval until the bottle turns'}]
    words = steps._image_words(ctx, seed)
    assert 'small lower strip' in words
    assert 'all other clear material stays visible' in words


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('overlong_blind_twice', [False, True])
def test_app_worker_actual_steps_and_reserved_fake_providers_reach_pick(tmp_path, settings, monkeypatch, overlong_blind_twice):
    """Start/marks/pick are app actions; all artifacts originate in queued jobs."""
    import base64
    import io
    import uuid
    from django.contrib.auth import get_user_model
    from apps.pipeline.services import round_calls, round_flow as flow, round_report, spend_reservation as spend

    settings.ROUND_ARTIFACT_ROOT = tmp_path/'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path/'spend'
    pending, requests, images = [], [], []
    monkeypatch.setattr(flow, '_enqueue', pending.append)
    root = settings.ROUND_ARTIFACT_ROOT/'r2-gloss'
    root.mkdir(parents=True)
    probe = (flow.REPO/'docs/rounds/r2-gloss/probe.md').read_text()
    probe_gaps = [line[2:] for line in probe.splitlines() if line.startswith('- ')]
    assert len(probe_gaps) == 13
    (root/'probe.md').write_text(probe)
    if overlong_blind_twice:
        (root/'BREAKS.md').write_text('# Build findings\n\n| ID | Step | Finding |\n| --- | --- | --- |\n| B99 | image audit | Fixture missing-fork journal regression. |\n')
    blind_calls = 0
    disqualified_fork = 'A1/B' if overlong_blind_twice else None
    def text_create(**kwargs):
        nonlocal blind_calls
        assert kwargs['thinking'] == {'type': 'adaptive'}
        prompt = kwargs['messages'][0]['content'][-1]['text']
        requests.append(prompt)
        if 'Exactly twenty seeds' in prompt:
            operation = 'seeds'
        elif 'Classify every panel' in prompt:
            operation = 'check/fixture'
        elif prompt.startswith('What idea'):
            operation = 'blind/fixture'
        elif prompt.startswith('Locate precisely'):
            operation = 'fragment/fixture'
        elif 'Order every candidate' in prompt:
            operation = 'coarse/fixture'
        elif 'Choose exactly one winner per pair' in prompt:
            operation = 'pairwise/fixture'
        else:
            raise AssertionError('Unrecognized real worker prompt')
        effort = 'low' if operation.startswith(('check/', 'blind/')) else 'medium'
        assert kwargs['output_config'] == {'effort': effort}
        assert kwargs['max_tokens'] == (8192 if effort == 'low' else 16384)
        payload = fake_payload(operation, prompt, root)
        if operation.startswith('check/') and disqualified_fork and kwargs['messages'][0]['content'][0]['text'].startswith(disqualified_fork+' '):
            payload['banned_motifs'] = ['front carries a literal rose flower.']
        if operation.startswith('blind/'):
            blind_calls += 1
            if overlong_blind_twice and blind_calls in (2, 3):
                payload['idea_in_ten_words'] = 'one two three four five six seven eight nine ten eleven'
        return {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(payload)}],
                'usage': {'input_tokens': 100, 'output_tokens': 100}}
    def image_edit(**kwargs):
        images.append(kwargs['prompt'])
        output = io.BytesIO()
        Image.new('RGBA', (1536, 1024), (30+len(images), 80, 110, 255)).save(output, format='PNG')
        return {'data': [{'b64_json': base64.b64encode(output.getvalue()).decode()}],
                'usage': {'input_tokens': 100, 'output_tokens': 100,
                          'input_tokens_details': {'image_tokens': 20, 'text_tokens': 80}}}
    text_client = SimpleNamespace(messages=SimpleNamespace(create=text_create))
    image_client = SimpleNamespace(images=SimpleNamespace(edit=image_edit))
    original_context = round_calls.RoundContext
    def context(record, job):
        return original_context(record, job, text_client=text_client, image_client=image_client)
    monkeypatch.setattr(round_calls, 'RoundContext', context)
    owner = get_user_model().objects.create_user(username='real-round-fixture-owner')
    record = flow.create_round(product.lip_gloss_brief(), owner, uuid.uuid4().hex)
    dispatches = 0
    def drain():
        nonlocal dispatches
        while pending:
            before = len(requests)+len(images)
            before_calls = round_calls.scoped_spend(record)['calls']
            result = flow.run_step_job(pending.pop(0))
            dispatches += 1
            assert result['status'] != 'failed', result
            # One new reservation per delivery may contain bounded text retries.
            assert round_calls.scoped_spend(record)['calls'] - before_calls <= 1
            assert len(requests)+len(images)-before <= 3
            assert dispatches < 180
    drain()
    record.refresh_from_db()
    assert record.state == 'awaiting_marks' and len(images) == 20
    reading = steps.read(root/'sketches/A2/blind.json')
    assert reading['over_length'] is overlong_blind_twice
    assert reading['length_reasked'] is overlong_blind_twice
    if overlong_blind_twice:
        assert reading['idea_in_ten_words'] == 'one two three four five six seven eight nine ten eleven'
        assert reading['word_count'] == 11
        assert not (root/'call-validation.jsonl').exists()
        assert 'Reading format: over length' in steps._jury_images(context(record, None), ['A2'])[0][0]
    assert len(record.artifacts['pairwise']['publication']['order']) == 8
    marked = record.artifacts['pairwise']['order'][:3]
    flow.submit_marks(record.pk, [{'id': key, 'preserve': 'The central interval on body_back'} for key in marked], owner)
    drain()
    record.refresh_from_db()
    assert record.state == 'awaiting_pick' and not record.pick
    assert len(images) == 26
    # Measured from pre-repair 850419f with persisted JSONB key order:
    # versioned intake must not change existing brief/sketch/check identities.
    # Break 7 separately adds all-panel guidance to newly localized forks.
    import hashlib
    assert 'prompt_contract' not in record.product_brief and marked[0] == 'A1'
    legacy = {'brief': json.dumps(record.product_brief, sort_keys=True), 'sketch': images[0],
              'check': next(p for p in requests if p.startswith('Inspect the COMPLETE '))}
    assert {key: hashlib.sha256(value.encode()).hexdigest() for key, value in legacy.items()} == {
        'brief': 'ebc796c2bd997a3b6a22aed3c59774433a0a3b59577e52f29ebbcb7914c2d398',
        'sketch': 'e3d0bc43eadb4f9caf28a28111239d5d81373ad12220e5155c446dc2b167507b',
        'check': '358850e5e84744d178f4a02db05158a4e74de19c215df143320c7541df604666',
    }
    assert all('carton top_end and bottom_end' in words for words in images[20:])
    publication = record.artifacts['pick_page']
    assert len(publication['order']) == 6
    assert all(sha(root/path) == digest for path, digest in publication['files'].items())
    with spend._connect() as db:
        billed = [dict(row) for row in db.execute('SELECT * FROM calls')]
    assert len(billed) == len(images)+len(requests)-int(overlong_blind_twice)
    assert all(row['state'] == 'usage_recorded' for row in billed)
    assert sum(row['accounted'] for row in billed) < 22_000_000
    assert sum(row['provider'] == 'openai' for row in billed) == 26
    assert blind_calls == 26+int(overlong_blind_twice)-int(disqualified_fork is not None)
    flow.submit_pick(record.pk, publication['order'][0], 'A complete product idea.', owner)
    drain()
    record.refresh_from_db()
    assert record.state == 'complete'
    assert record.steps.filter(state='complete').count() == len(flow.STEPS)
    assert (root/'pick.json').is_file()
    # Closeout is generated by the pick worker, not supplied by this fixture.
    report = (root/'README.md').read_text()
    assert len(report.splitlines()) <= 80
    assert report.index('**The system test**') < report.index('**The round**')
    assert 'Probe: 13 gaps recorded' in report
    assert report.count('- Probe gap: ') == 13
    for gap in probe_gaps:
        quoted = ' '.join(gap.split()).replace('|', '\\|')
        assert '- Probe gap: '+quoted in report
        assert report.index('- Probe gap: '+quoted) < report.index('**The round**')
    assert 'Runtime breaks: 0;' in report
    assert ('Build findings: 1; steps: image audit.' if overlong_blind_twice else 'Build findings: 0; steps: none.') in report
    assert 'no step was run by hand' in report
    assert f'Owner pick: **{publication["order"][0]}** — A complete product idea.' in report
    assert 'Twenty seeds and product-truth links:' in report
    if disqualified_fork:
        assert 'Disqualified: A1/B: banned motif:' in report
        assert 'front carries a literal rose flower' in report
        assert disqualified_fork not in record.artifacts['final_pairwise']['pool']
        assert disqualified_fork not in publication['order']
    else:
        assert 'Disqualified: none.' in report
    audit = steps.read(root/'image-input-audit.json')
    assert audit['passes'] and audit['originals'] == 20 and audit['forks'] == 6
    assert audit['paid_image_attempts'] == audit['successful_image_edits'] == audit['limit'] == 26
    assert len(audit['attempts']) == 26 and all(row['inputs_match'] for row in audit['attempts'])
    assert {row['reservation_id'] for row in audit['attempts']} == {row['id'] for row in billed if row['provider'] == 'openai'}
    handoff = steps.read(root/'handoff.json')
    assert handoff['pick'] == record.pick and handoff['day_two_started'] is False
    assert handoff['candidate'] == publication['candidates'][record.pick['id']]
    assert handoff['detail_pass']['delta_e00_mean_max'] == 1.5
    assert handoff['detail_pass']['ssim_min'] == .97
    assert handoff['detail_pass']['otherwise'] == 'Retain the 2× plate.'
    settled = steps.read(root/'spend.json')
    assert settled['reserved_usd'] == 0
    assert settled['actual_usd'] == pytest.approx(sum(row['accounted'] for row in billed)/1e6)
    assert settled['accounted_usd'] == settled['actual_usd'] < 22

    # Negative controls touch only this temporary fixture and restore exact bytes
    # before the next audit; no changed record can pass as a clean request.
    audit_context = original_context(record, text_client=text_client, image_client=image_client)
    request_path = root/'sketches/A1/image-call.request.json'
    original_request = request_path.read_bytes()
    try:
        altered = json.loads(original_request)
        altered['prompt'] += '\nUnreserved alteration.'
        write(request_path, altered)
        with pytest.raises(ValueError, match='identity'):
            round_report.image_audit(audit_context)
    finally:
        request_path.write_bytes(original_request)
    journal = root/'image-calls.jsonl'
    original_journal = journal.read_bytes()
    try:
        journal.write_bytes(original_journal+original_journal.splitlines(keepends=True)[0])
        with pytest.raises(ValueError, match='journal'):
            round_report.image_audit(audit_context)
    finally:
        journal.write_bytes(original_journal)
    original_rows = [json.loads(line) for line in original_journal.splitlines()]
    missing_fork = next(row['reservation_id'] for row in original_rows if row['operation'].count('/') == 2)
    try:
        remaining = [row for row in original_rows if row['reservation_id'] != missing_fork]
        journal.write_text(''.join(json.dumps(row)+'\n' for row in remaining))
        with pytest.raises(ValueError, match='journal.*incomplete'):
            round_report.image_audit(audit_context)
    finally:
        journal.write_bytes(original_journal)
    for field, replacement in [('operation', 'image/D5/B'), ('request_sha256', '0'*64), ('inputs', [])]:
        try:
            altered_rows = json.loads(json.dumps(original_rows))
            altered_rows[-1][field] = replacement
            journal.write_text(''.join(json.dumps(row)+'\n' for row in altered_rows))
            with pytest.raises(ValueError, match='journal (operation|identity)'):
                round_report.image_audit(audit_context)
        finally:
            journal.write_bytes(original_journal)
    sheet_path = root/'sheet.png'
    original_sheet = sheet_path.read_bytes()
    try:
        sheet_path.write_bytes(b'Fixture-only changed input bytes')
        with pytest.raises(ValueError, match='input pin changed'):
            round_report.image_audit(audit_context)
    finally:
        sheet_path.write_bytes(original_sheet)
    assert round_report.image_audit(audit_context) == audit

    # A known settled, unusable reply has a durable failed outcome rather than
    # a completed-edit journal row. Its archived request must still be audited.
    failed_row = next(row for row in original_rows if row['reservation_id'] == missing_fork)
    completed_path = root/failed_row['payload_file']
    request_path = completed_path.with_name('image-call.request.json')
    saved = {path: path.read_bytes() for path in (completed_path, request_path)}
    archive = completed_path.parent/'call-history'/('image-call-'+missing_fork)
    archive.mkdir(parents=True)
    try:
        for path in saved:
            path.rename(archive/path.name)
        failed = steps.read(archive/'image-call.json')
        failed.update(status='validation_failed', validation_error='Fixture provider returned an unusable image.')
        write(archive/'image-call.json', failed)
        journal.write_text(''.join(json.dumps(row)+'\n' for row in original_rows if row['reservation_id'] != missing_fork))
        archived_audit = round_report.image_audit(audit_context)
        assert archived_audit['paid_image_attempts'] == 26
        assert archived_audit['successful_image_edits'] == 25 and archived_audit['forks'] == 5
        retained = next(row for row in archived_audit['attempts'] if row['reservation_id'] == missing_fork)
        assert retained['outcome_status'] == 'validation_failed'
        assert '/call-history/' in retained['request']
    finally:
        for path, data in saved.items():
            path.write_bytes(data)
            (archive/path.name).unlink()
        archive.rmdir()
        journal.write_bytes(original_journal)
    assert round_report.image_audit(audit_context) == audit


def test_interrupted_sheet_and_derived_image_json_resume_without_repurchase(tmp_path, settings, monkeypatch):
    """A partial temporary JSON never becomes a recovery marker or a paid retry."""
    import base64
    import io
    from unittest.mock import Mock
    from apps.pipeline.services import round_calls, round_flow, spend_reservation as spend
    settings.ROUND_ARTIFACT_ROOT = tmp_path/'rounds'
    settings.RESCUE_SPEND_ROOT = tmp_path/'spend'
    record = SimpleNamespace(pk=999, slug='atomic-fixture', product_brief=product.normalize_brief(product.lip_gloss_brief()), budget_usd=22)
    output = io.BytesIO()
    Image.new('RGBA', (1536, 1024), (70, 80, 90, 255)).save(output, format='PNG')
    create = Mock(return_value={'data': [{'b64_json': base64.b64encode(output.getvalue()).decode()}],
        'usage': {'output_tokens': 100, 'input_tokens_details': {'image_tokens': 20, 'text_tokens': 80}}})
    client = SimpleNamespace(images=SimpleNamespace(edit=create))
    context = round_calls.RoundContext(record, image_client=client)
    original_dump = round_flow.json.dump
    def interrupted_writer(filename):
        def dump(payload, stream, *args, **kwargs):
            if Path(stream.name).name.startswith(filename+'.'):
                stream.write('{"partial":')
                stream.flush()
                raise OSError('Fixture interruption during derived JSON')
            return original_dump(payload, stream, *args, **kwargs)
        return dump
    with monkeypatch.context() as patch:
        patch.setattr(round_flow.json, 'dump', interrupted_writer('sheet.json'))
        with pytest.raises(OSError, match='Fixture interruption'):
            sheet.build(context.brief, context.root)
    assert not (context.root/'sheet.json').exists()
    assert list(context.root.glob('sheet.json.*.tmp'))
    sheet.build(context.brief, context.root)
    assert sheet.verify(context.root)['passes']
    seed = {'seed': 'A quiet interval reveals colour', 'link': 'because a lip gloss reveals colour'}
    words = steps._image_words(context, seed)
    dest = context.root/'sketches/A1'
    with monkeypatch.context() as patch:
        patch.setattr(round_flow.json, 'dump', interrupted_writer('result.json'))
        with pytest.raises(OSError, match='Fixture interruption'):
            steps._edit(context, 'A1', words)
    assert create.call_count == 1
    assert steps.read(dest/'image-call.json')['status'] == 'complete'
    assert (dest/'raw.png').exists() and not (dest/'result.json').exists()
    assert list(dest.glob('result.json.*.tmp'))
    resumed = round_calls.RoundContext(record, image_client=client)
    result = steps._edit(resumed, 'A1', words)
    assert create.call_count == 1 and result['output_sha256'] == sha(dest/'picture.png')
    assert steps.read(dest/'crop.json')['qualifies']
    with spend._connect() as db:
        rows = [dict(row) for row in db.execute('SELECT * FROM calls')]
    assert len(rows) == 1 and rows[0]['state'] == 'usage_recorded'


def test_round_tag_is_idempotent_and_cannot_move_to_another_pick(tmp_path, settings, monkeypatch):
    """Mock all Git calls; neither a repository tag nor the real Git lock is used."""
    from apps.pipeline.services import round_report
    settings.ROUND_COMMIT_ARTIFACTS = True
    root = tmp_path/'docs/rounds/r2-gloss'
    root.mkdir(parents=True)
    (tmp_path/'.git').mkdir()
    write(root/'image-input-audit.json', {'passes': True})
    record = SimpleNamespace(slug='r2-gloss', state='complete', pick={'id': 'A1', 'reason': 'Fixture choice'})
    commands, locks = [], []
    tagged = {'pick': None}
    def git_run(command, **kwargs):
        commands.append(command)
        assert kwargs['cwd'] == tmp_path
        if command[1] == 'show':
            return SimpleNamespace(returncode=0 if tagged['pick'] else 1,
                                   stdout=json.dumps(tagged['pick']) if tagged['pick'] else '')
        if command[1] == 'rev-parse':
            return SimpleNamespace(returncode=0 if tagged['pick'] else 1)
        assert command[:3] == ['git', 'tag', '-a']
        tagged['pick'] = dict(record.pick)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(round_report, 'REPO', tmp_path)
    monkeypatch.setattr(round_report, 'round_root', lambda item: root)
    monkeypatch.setattr(round_report, 'sys', SimpleNamespace(modules={}))
    monkeypatch.setattr(round_report, 'subprocess', SimpleNamespace(run=git_run))
    monkeypatch.setattr(round_report, 'fcntl', SimpleNamespace(LOCK_EX=2, flock=lambda fd, mode: locks.append(mode)))
    round_report.tag_if_requested(record)
    round_report.tag_if_requested(record)
    assert sum(command[1] == 'tag' for command in commands) == 1
    assert locks == [2, 2]
    record.pick = {'id': 'A2', 'reason': 'Different fixture choice'}
    with pytest.raises(ValueError, match='different pick'):
        round_report.tag_if_requested(record)
    assert sum(command[1] == 'tag' for command in commands) == 1
    assert tagged['pick']['id'] == 'A1' and locks == [2, 2, 2]


@pytest.fixture
def repaired_image_report_context(tmp_path, settings, monkeypatch):
    """Two generations, a paid invalid old attempt, and unchanged old log pointers."""
    import hashlib
    from apps.pipeline.services import round_calls as image_guard, round_flow, spend_reservation
    settings.RESCUE_SPEND_ROOT = tmp_path/'spend'
    root = tmp_path/'r2-gloss'
    root.mkdir()
    logo = tmp_path/'approved-logo.png'
    logo.write_bytes(b'Pinned fixture logo')
    monkeypatch.setattr(image_guard, 'APPROVED_LOGO', (str(logo), sha(logo)))
    authorization = {'id': round_flow.REPAIR_ID, 'source': 'owner app retry', 'user_id': 1,
        'authorized_at': '2026-10-26T12:00:00+00:00', 'additional_image_attempts': 20,
        'image_attempt_limit': 46, 'budget_usd': 25, 'original_brief': {'name': 'Fixture gloss'},
        'old_brief_sha256': 'fixture-brief-pin', 'previous_artifacts': {}, 'previous_steps': []}
    record = SimpleNamespace(slug='r2-gloss', artifacts={}, budget_usd=25)
    context = SimpleNamespace(root=root, round=record, prefix='round/r2-gloss/', brief={'name': 'Fixture gloss'})
    write(root/'seeds.json', {'seeds': [{'id': family+str(n), 'seed': 'Fixture seed', 'link': 'because a gloss reveals colour'}
                                     for family in 'ABCD' for n in range(1, 6)]})
    journal = root/'image-calls.jsonl'
    journal.touch()

    def generation(name, forks, failed=False):
        (root/'sheet.png').write_bytes((name+' sheet').encode())
        (root/'sheet-mask.png').write_bytes((name+' mask').encode())
        for family in 'ABCD':
            for n in range(1, 6):
                destination = root/'sketches'/(family+str(n))
                destination.mkdir(parents=True, exist_ok=True)
                (destination/'picture.png').write_bytes((name+' '+family+str(n)).encode())
        operations = [f'image/{family}{n}' for family in 'ABCD' for n in range(1, 6)] + forks
        if failed:
            operations += ['image/B1/B']
        for index, operation in enumerate(operations):
            parts = operation.split('/')
            parent = parts[1]
            fork = parts[2] if len(parts) == 3 else None
            destination = root/'developments'/parent/fork if fork else root/'sketches'/parent
            if failed and index == len(operations)-1:
                destination = destination/'call-history'/'image-call-invalid'
            destination.mkdir(parents=True, exist_ok=True)
            target = root/'sketches'/parent/'picture.png' if fork else root/'sheet.png'
            mask = root/'developments'/parent/'fragment-mask.png' if fork else root/'sheet-mask.png'
            if fork:
                mask.parent.mkdir(parents=True, exist_ok=True)
                mask.write_bytes((name+' fragment '+parent).encode())
            sources = [target, logo] + ([root/'sheet.png'] if fork else [])
            identity = {'model': 'gpt-image-2', 'quality': 'high', 'size': '1536x1024',
                'prompt': name+' '+operation, 'inputs': [{'path': str(path), 'sha256': sha(path)} for path in sources],
                'mask': {'path': str(mask), 'sha256': sha(mask)}}
            digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            ident = f'{name}-{index}'
            request = dict(identity, reservation_id=ident, request_sha256=digest)
            outcome = dict(request, status='complete', output_sha256=hashlib.sha256(ident.encode()).hexdigest())
            if failed and index == len(operations)-1:
                outcome.update(status='validation_failed', validation_error='Fixture invalid image reply.')
            write(destination/'image-call.request.json', request)
            write(destination/'image-call.json', outcome)
            with spend_reservation._connect() as db:
                db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (ident, '2026-10-26', 'openai', context.prefix+operation, 'gpt-image-2', None,
                     10000, 10000, 'usage_recorded', None, '{}', digest, 'fixture', 'fixture'))
            if outcome['status'] == 'complete':
                entry = dict(outcome, operation=operation,
                    payload_file=str((destination/'image-call.json').relative_to(root)),
                    billing_state='usage_recorded', accounted_usd=.01)
                with journal.open('a') as stream:
                    stream.write(json.dumps(entry)+'\n')

    generation('original', ['image/A1/A'], failed=True)
    original_journal = journal.read_bytes()
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and path not in {journal, root/'seeds.json'}:
            relative = str(path.relative_to(root))
            files.append({'original': relative, 'archived': round_flow.REPAIR_ARCHIVE+'/'+relative, 'sha256': sha(path)})
    manifest = {'schema': 'round_repair_archive/1', 'authorization': authorization,
        'files': files, 'preserved_files': [{'original': 'seeds.json', 'sha256': sha(root/'seeds.json')}]}
    manifest_path = root/round_flow.REPAIR_ARCHIVE/'manifest.json'
    write(manifest_path, manifest)
    for item in files:
        destination = root/item['archived']
        destination.parent.mkdir(parents=True, exist_ok=True)
        (root/item['original']).rename(destination)
    prepared = dict(authorization, prepared_at='2026-10-26T12:01:00+00:00',
                    manifest=str(manifest_path.relative_to(root)), manifest_sha256=sha(manifest_path))
    record.artifacts['repair_authorization'] = prepared
    write(root/'repair-authorization.json', prepared)
    generation('repair', ['image/A1/A', 'image/A1/B', 'image/B1/A', 'image/B1/B'])
    context.original_journal = original_journal
    return context


def test_repaired_image_report_audits_both_generations_and_preserves_journal(repaired_image_report_context):
    from apps.pipeline.services import round_report, round_flow
    context = repaired_image_report_context
    journal = context.root/'image-calls.jsonl'
    before = journal.read_bytes()
    audit = round_report.image_audit(context)
    assert journal.read_bytes() == before and before.startswith(context.original_journal)
    assert audit['passes'] and audit['paid_image_attempts'] == audit['limit'] == 46
    assert audit['successful_image_edits'] == 45 and audit['originals'] == 20 and audit['forks'] == 4
    assert audit['generations'] == [
        {'id': 'original', 'active': False, 'image_attempts': 22, 'successful_image_edits': 21, 'originals': 20, 'forks': 1},
        {'id': round_flow.REPAIR_ID, 'active': True, 'image_attempts': 24, 'successful_image_edits': 24, 'originals': 20, 'forks': 4}]
    failed = [item for item in audit['attempts'] if item['outcome_status'] == 'validation_failed']
    assert len(failed) == 1 and failed[0]['generation'] == 'original'
    assert failed[0]['request'].startswith(round_flow.REPAIR_ARCHIVE+'/')
    assert round_report.image_audit(context) == audit


@pytest.mark.parametrize('damage, message', [
    ('old_input', 'archived repair artifact'),
    ('old_failed_outcome', 'archived repair artifact'),
    ('preserved_seeds', 'preserved seeds'),
    ('manifest', 'manifest is missing or changed'),
    ('unmanifested', 'unmanifested'),
    ('old_journal_pointer', 'journal operation or outcome pointer'),
    ('wrong_authorization', 'no exact owner authorization'),
    ('wrong_product', 'no exact owner authorization'),
])
def test_repaired_image_report_rejects_history_tampering(repaired_image_report_context, damage, message):
    from apps.pipeline.services import round_report, round_flow
    context = repaired_image_report_context
    root = context.root
    archive = root/round_flow.REPAIR_ARCHIVE
    if damage == 'old_input':
        (archive/'sheet.png').write_bytes(b'Changed old input bytes')
    elif damage == 'old_failed_outcome':
        (archive/'developments/B1/B/call-history/image-call-invalid/image-call.json').unlink()
    elif damage == 'preserved_seeds':
        (root/'seeds.json').write_bytes(b'Changed original seeds')
    elif damage == 'manifest':
        with (archive/'manifest.json').open('a') as stream:
            stream.write('\n')
    elif damage == 'unmanifested':
        (archive/'unexpected.json').write_text('{}')
    elif damage == 'old_journal_pointer':
        rows = [json.loads(line) for line in (root/'image-calls.jsonl').read_text().splitlines()]
        rows[0]['payload_file'] = round_flow.REPAIR_ARCHIVE+'/'+rows[0]['payload_file']
        (root/'image-calls.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    elif damage == 'wrong_authorization':
        context.round.artifacts['repair_authorization']['additional_image_attempts'] = 21
    else:
        context.round.slug = 'another-product'
    with pytest.raises(ValueError, match=message):
        round_report.image_audit(context)


def test_repaired_image_report_requires_twenty_current_sketches(repaired_image_report_context):
    from apps.pipeline.services import round_report, spend_reservation
    context = repaired_image_report_context
    root = context.root
    outcome_path = root/'sketches/D5/image-call.json'
    ident = steps.read(outcome_path)['reservation_id']
    outcome_path.unlink()
    outcome_path.with_name('image-call.request.json').unlink()
    journal = root/'image-calls.jsonl'
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    journal.write_text(''.join(json.dumps(row)+'\n' for row in rows if row['reservation_id'] != ident))
    with spend_reservation._connect() as db:
        db.execute('DELETE FROM calls WHERE id=?', (ident,))
    with pytest.raises(ValueError, match='Twenty completed original sketches.*active generation'):
        round_report.image_audit(context)


def test_repaired_image_report_rejects_second_completion_within_generation(repaired_image_report_context):
    from apps.pipeline.services import round_report, spend_reservation
    context = repaired_image_report_context
    root = context.root
    # Convert a second completed fork to the first fork's operation without
    # exceeding 46 attempts. Both use the exact same parent and mask inputs.
    duplicate = root/'developments/A1/B/image-call.json'
    ident = steps.read(duplicate)['reservation_id']
    journal = root/'image-calls.jsonl'
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    next(row for row in rows if row['reservation_id'] == ident)['operation'] = 'image/A1/A'
    journal.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with spend_reservation._connect() as db:
        db.execute('UPDATE calls SET operation=? WHERE id=?', (context.prefix+'image/A1/A', ident))
    with pytest.raises(ValueError, match='more than one completion.*generation'):
        round_report.image_audit(context)


def test_repaired_image_report_retains_hard_total_attempt_limit(repaired_image_report_context):
    from apps.pipeline.services import round_report, spend_reservation
    context = repaired_image_report_context
    source = context.root/'sketches/A1/image-call.request.json'
    request = steps.read(source)
    original_id = request['reservation_id']
    request['reservation_id'] = 'fixture-excess-attempt'
    destination = source.parent/'call-history'/'excess'
    write(destination/'image-call.request.json', request)
    write(destination/'image-call.json', dict(request, status='validation_failed', validation_error='Fixture invalid image reply.'))
    with spend_reservation._connect() as db:
        db.execute('INSERT INTO calls SELECT ?,day,provider,operation,model,task_id,reserved,accounted,state,artifact,usage,request_hash,started_at,settled_at FROM calls WHERE id=?',
                   (request['reservation_id'], original_id))
    with pytest.raises(ValueError, match='46-call ledger limit'):
        round_report.image_audit(context)


def test_repaired_close_report_shows_full_spend_and_archived_generation(repaired_image_report_context):
    from apps.pipeline.services import round_flow, round_report
    context = repaired_image_report_context
    root = context.root
    context.round.steps = SimpleNamespace(order_by=lambda field: [
        SimpleNamespace(name='seeds', history=[], attempts=0),
        SimpleNamespace(name='coarse', history=[{'at': 'fixture', 'error': 'Fewer than eight eligible sketches.'},
            {'at': 'repair', 'kind': 'owner_repair', 'error': 'Owner authorized replacement sheet and sketches.'}], attempts=1)])
    write(root/'eligibility.json', {'results': {}})
    write(root/'cut.json', {'order': ['A1']})
    write(root/'marks.json', {'source': {'kind': 'owner app'}, 'marks': [{'id': 'A1', 'preserve': 'Keep the interval.'}]})
    write(root/'forks.json', {'results': {}, 'candidates': ['A1/A', 'A1/B', 'B1/A', 'B1/B']})
    write(root/'final-order.json', {'pool': ['A1'], 'pool_rule': 'Fixture eligible pool.', 'full_order': ['A1'], 'order': ['A1']})
    write(root/'publication.json', {'candidates': {'A1': {'source': 'Fixture crops'}}})
    write(root/'jury/coarse/result.json', {'shortlist': ['A1']})
    pick = {'id': 'A1', 'reason': 'Fixture owner choice.', 'merge': None}
    original_journal = (root/'image-calls.jsonl').read_bytes()
    report = round_report.finalize(context, pick)
    text = (root/'README.md').read_text()
    assert report['report_lines'] <= 80
    assert 'Spend: $0.460000 of $25.00; outstanding holds $0.000000.' in text
    assert '46 attempts, 45 completed edits; allowed input pins pass; limit 46.' in text
    assert 'original 22 image attempts and 21 completed edits remain pinned' in text
    assert 'active generation 24 attempts and 24 completed edits' in text
    assert round_flow.REPAIR_ARCHIVE+'/manifest.json' in text
    assert 'Runtime breaks: 1; steps: coarse.' in text
    assert 'owner_repair' not in (root/'BREAKS.md').read_text()
    assert 'Owner authorized replacement' not in (root/'BREAKS.md').read_text()
    assert (root/'image-calls.jsonl').read_bytes() == original_journal

# Day two: these are emitted-file/media checks; no provider or live round is used.
def test_master_detail_accepts_identity_and_rejects_a_changed_panel():
    from PIL import Image
    import numpy as np
    from apps.pipeline.services.round_master_art import fidelity
    rng=np.random.default_rng(5)
    reference=Image.fromarray(rng.integers(30,220,(80,60,3),dtype=np.uint8))
    identical=fidelity(reference,reference)
    assert identical['accepted'] and identical['de00_mean']==0 and identical['ssim']==1
    changed=fidelity(reference,Image.new('RGB',reference.size,'white'))
    assert not changed['accepted'] and changed['de00_mean']>1.5 and changed['ssim']<.97


def test_master_clear_plate_has_no_liquid_pink_and_keeps_open_print(tmp_path):
    from PIL import Image
    import numpy as np
    from apps.pipeline.services.round_master_art import clear_separation
    source=Image.new('RGB',(100,100),'#C9707A')
    a=np.asarray(source).copy();a[30:40,30:40]=[255,255,255]
    plate,record=clear_separation(Image.fromarray(a),{'liquid':'#C9707A',
        'sheet':{'box_px':[0,0,100,100],'printable_box_px':[10,10,90,90]}})
    out=np.asarray(plate)
    assert (out[...,:3]==255).all()
    assert out[50,50,3]==0 and out[35,35,3]==255 and out[0,0,3]==0
    assert not record['liquid_is_printed'] and record['clear_pixel_share']>.95


def test_master_live_arabic_spaces_and_mixed_scripts_fit_at_declared_size(tmp_path):
    from apps.pipeline.services import round_master_art as art,round_master_files as mf
    surface=mf.Surface([80,50],'Fixture',[3,3,77,47])
    art.add_copy(surface,{'field':'copy.product','text':'ملمع شفاه','color':'#101010'},[10,10,60,14],fixed_size=10)
    art.add_copy(surface,{'field':'copy.batch','text':'Batch / التشغيلة','color':'#101010'},[10,22,70,26],fixed_size=8)
    rows=list(surface.rows)
    assert all(8<=r['size_pt']<=10 for r in rows)
    assert all(3<=r['ink_box_mm'][0]<r['ink_box_mm'][2]<=77 for r in rows)
    assert len([r for r in rows if r['copy']=='ملمع شفاه'])==1
    path=tmp_path/'mixed.ai';result=surface.save(path)
    measured=art.measured_file(path,rows,result['elements'],safe=[[3,3,77,47]])
    assert measured['measurements']['printed_character_inventory']['complete']
    assert measured['measurements']['latin_uses_latin_face']
    assert {r['name'] for r in measured['layers']}==set(mf.LAYERS)
    assert all(r['embedded'] for r in measured['fonts'])


def test_master_blank_cap_reopens_all_six_pdf_layers_without_fake_text(tmp_path):
    from apps.pipeline.services import round_master_art as art,round_master_files as mf
    s=mf.Surface([21,36],'Blank gold cap',[3,3,18,33]);s.rect([3,3,18,33],layer='die')
    path=tmp_path/'cap.ai';s.save(path)
    rec=art.measured_file(path,[],[],safe=[[3,3,18,33]])
    assert len(rec['layers'])==6 and rec['live_glyph_count']==0
    assert rec['checks']['die_guides_locked_nonprinting']
    assert rec['measurements']['printed_character_inventory']['complete']


def test_master_layout_rejects_instruction_and_malformed_text(tmp_path,monkeypatch):
    from apps.pipeline.services.round_master_art import validate_layout
    import copy
    plan={'panels':{'face':{'text':[{'field':'copy.product','text':'Lip Gloss','box':[.1,.1,.9,.2],'color':'#111111'}],
                          'erase':[],'marks':[],'geometry':[],'notes':''}}}
    allowed={'copy.product':'Lip Gloss'}
    assert validate_layout(plan,['face'],allowed)==plan
    bad=copy.deepcopy(plan);bad['panels']['face']['text'][0]['text']='Full drafts and warnings; day two.'
    with pytest.raises(ValueError):validate_layout(bad,['face'],allowed)
    bad=copy.deepcopy(plan);bad['panels']['face']['text'][0]['text']=123
    with pytest.raises(ValueError):validate_layout(bad,['face'],allowed)
    with pytest.raises(ValueError):validate_layout({'panels':['face']},['face'],allowed)
    from apps.pipeline.services import round_master_art as art
    bilingual={'panels':{'face':dict(plan['panels']['face'],text=[
        {'field':'copy.product','text':words,'box':[.1,.1+i*.2,.9,.2+i*.2],'color':'#111111'}
        for i,words in enumerate(('Lip Gloss','ملمع شفاه'))])}}
    ctx=SimpleNamespace(root=tmp_path,build=SimpleNamespace(inputs={'copy':{'copy.product':'Lip Gloss / ملمع شفاه'},
        'panels':[{'id':'face','surface':'clear_acrylic'}]}),text_call=lambda *a,**kw:{'payload':bilingual},reject_result=lambda *a:None)
    monkeypatch.setattr(art,'panel_records',lambda ctx:[{'id':'face','exact_mm':[15,70]}])
    assert art.layout(ctx)['panels']==['face']
    bilingual['panels']['face']['text'].pop()
    with pytest.raises(ValueError,match='Required COPY missing'):art.layout(ctx)
    ctx.build.inputs['copy']['copy.product']='A/B'
    bilingual['panels']['face']['text'][0]['text']='A'
    with pytest.raises(ValueError,match='Required COPY missing'):art.layout(ctx)


def test_master_emblem_crop_contains_the_whole_approved_path(tmp_path):
    import fitz
    from apps.pipeline.services.round_master_art import approved_emblem
    path=approved_emblem(tmp_path)
    with fitz.open(path) as svg:
        with fitz.open(stream=svg.convert_to_pdf(),filetype='pdf') as pdf:
            for drawing in pdf[0].get_drawings():
                assert pdf[0].rect.x0-.01<=drawing['rect'].x0
                assert drawing['rect'].x1<=pdf[0].rect.x1+.01
                assert pdf[0].rect.y0-.01<=drawing['rect'].y0
                assert drawing['rect'].y1<=pdf[0].rect.y1+.01


def test_master_eye_repair_resumes_revision_one_and_binds_its_input(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from apps.pipeline.services import round_master_art as art,round_flow as flow
    ctx=SimpleNamespace(root=tmp_path,build=SimpleNamespace(inputs={'copy':{}}))
    (tmp_path/'files').mkdir()
    for name in ('face','leaflet'):flow.write_json(tmp_path/'files'/(name+'.json'),{'measurements':{}})
    flow.write_json(tmp_path/'allowed-differences.json',[])
    flow.write_json(tmp_path/'leaflet-copy.json',{'missing_inputs':[]})
    monkeypatch.setattr(art,'objects',lambda ctx:{'body':['face']})
    monkeypatch.setattr(art,'eye_images',lambda *a:[])
    monkeypatch.setattr(art,'preview',lambda *a:{})
    binding=['before'];monkeypatch.setattr(art,'eye_binding',lambda *a:binding[0])
    applied=[]
    def repair(ctx,kind,ids,actions):
        marker=tmp_path/'repairs'/kind/'intent.json'
        if not marker.exists():flow.write_json(marker,{'repair':actions});applied.append(kind)
        binding[0]='after'
    monkeypatch.setattr(art,'apply_eye_repair',repair)
    requests=[];yielded=[False]
    def text(op,prompt,dest,**kwargs):
        requests.append(op)
        if op=='eye/body/r0':return {'payload':{'verdict':'fail','reason':'small type issue','allowed_differences':[],'issues':[],
            'repair':[{'kind':'type_box','panel':'face','index':0,'box':[.1,.1,.2,.2]}]}}
        if op=='eye/body/r1' and not yielded[0]:yielded[0]=True;raise flow.YieldRound()
        return {'payload':{'verdict':'pass','reason':'Complete verdict','allowed_differences':[],'issues':[],'repair':[]}}
    ctx.text_call=text
    with pytest.raises(flow.YieldRound):art.eye(ctx)
    result=art.eye(ctx)
    assert result['accepted'] and requests.count('eye/body/r0')==1 and applied==['body']
    assert result['objects']['body']['repairs_used']==1
    binding[0]='tampered'
    with pytest.raises(ValueError,match='changed after'):art.eye(ctx)


def test_master_failed_eye_cannot_publish_or_make_download(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from apps.pipeline.services import round_master_art as art,round_calls as calls,round_flow as flow
    ctx=SimpleNamespace(root=tmp_path,build=SimpleNamespace(budget_usd=15))
    monkeypatch.setattr(calls,'master_scoped_spend',lambda build:{'held_usd':0,'accounted_usd':0})
    flow.write_json(tmp_path/'eye.json',{'accepted':False,'objects':{}});flow.write_json(tmp_path/'jury.json',{'record':'Retained'})
    with pytest.raises(ValueError,match='did not accept'):art.publish(ctx)
    assert not (tmp_path/'master-ai.zip').exists()


class IdeasFixture:
    """The real ideas stages with synthetic pixels and deterministic jury replies."""
    def __init__(self, root, brief=None):
        from apps.pipeline.services.round_designer import gloss_brief
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.brief = brief or gloss_brief()
        self.round = SimpleNamespace(pk=81, artifacts={}, pick={})
        self.image_calls, self.text_calls = [], []
        self.jury_transform = None

    def text_call(self, operation, prompt, destination, **kwargs):
        from apps.pipeline.services import round_ideas as ideas
        if destination.exists():
            return ideas.read(destination)
        self.text_calls.append((operation, prompt, kwargs))
        if operation == 'seeds':
            payload = {'seeds': [{'id': key, 'family': ideas.FAMILIES[key[0]],
                        'seed': 'A distinct fixture direction ' + key,
                        'link': 'Because the product reveals colour'} for key in ideas.IDS]}
        else:
            pairs = json.loads(prompt.split('\nPAIRS: ')[1])
            shown = json.loads(prompt.split('\nSHOWN: ')[1].split('\n')[0])
            if '\nNOTE_IDS: ' in prompt:
                shown = json.loads(prompt.split('\nNOTE_IDS: ')[1].split('\n')[0])
            payload = {'pairs': [{'pair': pair, 'winner': min(pair),
                        'relationship': 'The product and stand share a visible rhythm.'} for pair in pairs],
                       'ideas': {key: 'A visible shared rhythm ' + key for key in shown}}
            if self.jury_transform is not None:
                self.jury_transform(operation, payload)
        result = {'payload': payload, 'status': 'complete'}
        write(destination, result)
        return result

    def design_image_call(self, operation, prompt, output):
        from apps.pipeline.services import round_ideas as ideas
        path = output / 'image-call.json'
        if path.exists():
            return ideas.read(path)
        self.image_calls.append((operation, prompt))
        output.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (1536, 1024), (len(self.image_calls) * 7, 90, 50)).save(output / 'raw.png')
        result = {'status': 'complete', 'output_sha256': sha(output / 'raw.png')}
        write(path, result)
        return result

    def reject_result(self, path, reason):
        result = json.loads(path.read_text())
        result.update(status='validation_failed', validation_error=reason)
        write(path, result)


def test_ideas_contract_generic_gloss_palette_and_unknown_measurements():
    from apps.pipeline.services.round_designer import SCHEMA, gloss_brief, normalize_ideas_brief, printed_copy
    gloss = gloss_brief()
    assert gloss['stand']['count'] == 12 and gloss['stand']['provisional']
    assert gloss['measurements_provisional'] and gloss['dimensions_mm']['cap_height'] == 30
    palette = normalize_ideas_brief({'schema': SCHEMA, 'name': 'Pressed palette', 'product_type': 'Palette',
        'material': 'Metal case', 'stand': {'count': 6}, 'copy': {'brand': 'BBROSE', 'product': 'Colour'},
        'panels': [{'id': 'do-not-use'}], 'copy_instruction': 'NEVER PRINT THIS',
        'content_roles': {'material': 'COPY'}, 'truths': ['A hinged compact holds pressed powder.']})
    assert palette['dimensions_mm'] == {} and palette['stand']['dimensions_mm'] == {}
    assert 'panels' not in palette and 'content_roles' not in palette
    assert printed_copy(palette) == {'brand': 'BBROSE', 'product': 'Colour', 'shade_names': []}
    for brief in (gloss, palette):
        assert normalize_ideas_brief(brief) == brief
    for number in (-1, 0, float('nan'), float('inf'), True):
        with pytest.raises(ValueError, match='positive'):
            normalize_ideas_brief(dict(palette, dimensions_mm={'width': number}))


def test_ideas_twenty_originals_all_pairs_top_three_and_unchanged_handoff(tmp_path):
    from collections import Counter
    from itertools import combinations
    from apps.pipeline.services import round_ideas as ideas
    ctx = IdeasFixture(tmp_path)
    ideas.run_step(ctx, 'seeds')
    sources = ideas.run_step(ctx, 'designs')
    before = {key: _path.read_bytes() for key in ideas.IDS for _path in [ideas._picture(ctx, key)]}
    assert len(ctx.image_calls) == 20 and sources['order'] == list(ideas.IDS)
    assert not any((tmp_path / name).exists() for name in ('sheet.png', 'sheet-mask.png', 'panels', 'developments'))
    for operation, prompt in ctx.image_calls:
        block = prompt.split(ideas.COPY_START)[1].split(ideas.COPY_END)[0]
        assert json.loads(block) == {'brand': 'BBROSE', 'product': 'Lip Gloss / ملمع شفاه',
                                    'shade_names': ['Rose Glass', 'Fig Nectar', 'Ember Glow']}
        assert 'at least HALF the picture height' in prompt
        assert 'liquid is visible' in prompt and '#C9707A' in prompt and 'gold square cap' in prompt
        assert 'sheet-mask' not in prompt
    ranking = ideas.run_step(ctx, 'pairwise')
    assert set(ranking['order']) == set(ideas.IDS) and len(ranking['order']) == 20
    expected = {frozenset(pair) for pair in combinations(ideas.IDS, 2)}
    for juror in ('J1', 'J2'):
        pairs = ranking['pairs'][juror]
        assert len(pairs) == 190 and {frozenset(row['pair']) for row in pairs} == expected
        assert set(Counter(key for row in pairs for key in row['pair']).values()) == {19}
    page = ideas.run_step(ctx, 'pick_page')
    assert page['order'] == ranking['order'][:3] and len(page['candidates']) == len(page['files']) == 3
    assert all('jury/' not in path for path in page['files'])
    assert len(ctx.text_calls) == 11  # One seed call plus five batches for each juror.
    # Replay every paid stage from durable fixtures; no new provider calls.
    ideas.run_step(ctx, 'seeds'); ideas.run_step(ctx, 'designs'); ideas.run_step(ctx, 'pairwise')
    assert len(ctx.image_calls) == 20 and len(ctx.text_calls) == 11
    assert all(ideas._picture(ctx, key).read_bytes() == data for key, data in before.items())
    ctx.round.artifacts['pick_page'] = page
    ctx.round.pick = {'id': page['order'][0], 'reason': 'The product and stand share one idea.', 'merge': None}
    handoff = ideas.finalize_pick(ctx)
    assert handoff['picture_sha256'] == sha(tmp_path / handoff['picture'])
    assert (tmp_path / handoff['picture']).read_bytes() == before[handoff['id']]
    assert ideas.finalize_pick(ctx) == handoff
    ctx.round.pick['reason'] = 'Changed after sealing'
    with pytest.raises(ValueError, match='sealed owner pick changed'):
        ideas.finalize_pick(ctx)


def test_ideas_jury_refuses_missing_pair_and_changed_original(tmp_path):
    from apps.pipeline.services import round_ideas as ideas
    ctx = IdeasFixture(tmp_path)
    ideas.seeds(ctx); ideas.designs(ctx); ideas.pairwise(ctx)
    result = ideas.read(tmp_path / 'jury/result.json')
    result['pairs']['J2'].pop()
    write(tmp_path / 'jury/result.json', result)
    with pytest.raises(ValueError, match='Missing pairs'):
        ideas.pick_page(ctx)
    ideas.pairwise(ctx)
    ideas._picture(ctx, 'A1').write_bytes(b'changed original')
    with pytest.raises(ValueError, match='original full-size picture changed'):
        ideas.pick_page(ctx)
    with pytest.raises(ValueError, match='original full-size picture changed'):
        ideas.pairwise(ctx)


def test_ideas_jury_invalid_reply_requires_owner_retry_and_pins_plan(tmp_path):
    from apps.pipeline.services import round_ideas as ideas
    ctx = IdeasFixture(tmp_path)
    ideas.seeds(ctx); ideas.designs(ctx)
    def invalid_winner(operation, payload):
        payload['pairs'][0]['winner'] = 'UNKNOWN'
    ctx.jury_transform = invalid_winner
    destination = tmp_path / 'jury/J1-1.json'
    with pytest.raises(ValueError, match='winner'):
        ideas.pairwise(ctx)
    assert ideas.read(destination)['status'] == 'validation_failed'
    plan = ideas.read(tmp_path / 'jury/plan.json')
    plan['batches'][0].pop()
    write(tmp_path / 'jury/plan.json', plan)
    with pytest.raises(ValueError, match='comparison plan changed'):
        ideas.pairwise(ctx)


def test_ideas_breaks_replay_each_event_once(tmp_path, settings):
    from apps.pipeline.services import round_flow as flow
    from apps.pipeline.services import round_ideas as ideas
    settings.ROUND_ARTIFACT_ROOT = tmp_path
    round_record = SimpleNamespace(pk=15, slug='new-product-fixture')
    job = SimpleNamespace(pk=22, attempts=1, name='designs', history=[
        {'at': 'first', 'error': 'Fixture timeout', 'attempt': 0},
        {'at': 'second', 'error': 'Fixture invalid reply', 'attempt': 1}])
    flow.record_break(round_record, job, job.history[-1]['error'])
    flow.record_break(round_record, job, job.history[-1]['error'])
    record = (tmp_path / 'BREAKS.md').read_text()
    assert record.count('## ') == 2 and record.count('Fixture timeout') == 1
    assert 'owner presses Retry in the app' in record


def test_ideas_jury_length_is_recorded_without_rejecting_complete_pairs(tmp_path):
    from apps.pipeline.services import round_ideas as ideas
    ctx = IdeasFixture(tmp_path)
    ideas.seeds(ctx); ideas.designs(ctx)
    note = ' '.join(['visible'] * 21)
    def long_note(operation, payload):
        if operation == 'pairwise/ideas/J1/1':
            payload['ideas']['A1'] = note
    ctx.jury_transform = long_note
    ideas.pairwise(ctx)
    calls = len(ctx.text_calls)
    result = ideas.pairwise(ctx)
    assert len(ctx.text_calls) == calls
    assert result['ideas']['J1']['A1'] == note
    assert result['length_observations']['advisory_only']
    assert result['length_observations']['words']['J1']['A1'] == 21
    assert len(result['pairs']['J1']) == len(result['pairs']['J2']) == 190
    assert ideas.pick_page(ctx)['candidates']['A1']['idea'] == note
    # A line break is a real structural failure, unlike the advisory word target.
    invalid = IdeasFixture(tmp_path / 'invalid-note')
    ideas.seeds(invalid); ideas.designs(invalid)
    def multiline_note(operation, payload):
        payload['ideas']['A1'] = 'First line\rSecond line'
    invalid.jury_transform = multiline_note
    with pytest.raises(ValueError, match='one plain line'):
        ideas.pairwise(invalid)
    destination = invalid.root / 'jury/J1-1.json'
    assert ideas.read(destination)['status'] == 'validation_failed'


def test_ideas_jury_missing_only_completion_preserves_all_twenty_originals(tmp_path):
    from apps.pipeline.services import round_ideas as ideas
    ctx = IdeasFixture(tmp_path)
    ideas.seeds(ctx); ideas.designs(ctx)
    before = {key: sha(ideas._picture(ctx, key)) for key in ideas.IDS}
    def omit_one(operation, payload):
        if operation == 'pairwise/ideas/J1/3':
            payload['pairs'] = [row for row in payload['pairs'] if row['pair'] != ['C5', 'D5']]
    ctx.jury_transform = omit_one
    ranking = ideas.pairwise(ctx)
    supplements = [call for call in ctx.text_calls if '/completion-' in call[0]]
    assert len(supplements) == 1
    operation, prompt, kwargs = supplements[0]
    assert operation == 'pairwise/ideas/J1/3/completion-1-1'
    assert json.loads(prompt.split('\nPAIRS: ')[1]) == [['C5', 'D5']]
    assert [key for key, path in kwargs['images']] == ['C5', 'D5']
    original = ideas.read(tmp_path / 'jury/J1-3.json')['payload']['pairs']
    assert len(original) == 44
    assert all(row in ranking['pairs']['J1'] for row in original)
    assert len(ranking['pairs']['J1']) == len(ranking['pairs']['J2']) == 190
    assert len(ctx.image_calls) == 20 and len(ctx.text_calls) == 12
    assert {key: sha(ideas._picture(ctx, key)) for key in ideas.IDS} == before
    page = ideas.pick_page(ctx)
    assert len(page['order']) == 3 and page['order'] == ranking['order'][:3]
    assert ideas.pairwise(ctx) == ranking
    assert len(ctx.image_calls) == 20 and len(ctx.text_calls) == 12
