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


