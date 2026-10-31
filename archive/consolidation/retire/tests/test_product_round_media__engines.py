"""Real generic media steps with deterministic fake providers, no design inputs."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw

from apps.pipeline.services import round_product as product
from apps.pipeline.services import round_balm_sheet
from apps.pipeline.services.round_balm_calls import write, sha
from apps.pipeline.services.whole_object_check import COPY_KEYS


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


def test_duplicate_panels_and_invalid_hex_refused_before_provider():
    brief = product.lip_gloss_brief(); brief['shades'][0]['hex'] = 'rose'
    with pytest.raises(ValueError, match='RRGGBB'):
        product.normalize_brief(brief)
    brief = product.lip_gloss_brief(); brief['panels'][1]['id'] = 'body_front'
    with pytest.raises(ValueError, match='distinct'):
        product.normalize_brief(brief)


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


