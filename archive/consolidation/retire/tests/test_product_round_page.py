"""App entry, owner decisions and pinned artwork; fixtures never call providers."""
import hashlib
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from apps.pipeline.models import Round, RoundStep
from apps.pipeline.services import round_flow, round_product
from apps.dashboard.product_round_forms import forms_for, initial_values, product_brief
from apps.dashboard import product_ideas_forms
from apps.pipeline.services import round_designer as round_ideas_brief

pytestmark=pytest.mark.django_db


@pytest.fixture(autouse=True)
def local_http(settings):
    settings.SECURE_SSL_REDIRECT=False



@pytest.fixture
def owner():
    return get_user_model().objects.create_superuser(username='round-owner',email='round@example.invalid',password='fixture-password')


@pytest.fixture
def client(owner):
    client=Client();client.force_login(owner);return client


@pytest.fixture
def isolated(settings,tmp_path,monkeypatch):
    settings.ROUND_ARTIFACT_ROOT=tmp_path/'rounds'
    monkeypatch.setattr(round_flow,'_enqueue',lambda step_id:None)
    monkeypatch.setattr(round_flow,'_schedule_marks',lambda *a:None)
    return tmp_path/'rounds'


def form_data():
    brief=round_product.lip_gloss_brief()
    data=initial_values(brief)
    data['request_key']=str(uuid4())
    for prefix,rows in [('panels',brief['panels']),('shades',brief['shades'])]:
        data[prefix+'-TOTAL_FORMS']=str(len(rows));data[prefix+'-INITIAL_FORMS']=str(len(rows))
        for i,row in enumerate(rows):
            for key,value in row.items():data[f'{prefix}-{i}-{key}']=str(value)
    return data


def ideas_form_data():
    brief = round_ideas_brief.gloss_brief()
    data = product_ideas_forms.initial_values(brief)
    data['request_key'] = str(uuid4())
    rows = brief['shades']
    data.update({'shades-TOTAL_FORMS': str(len(rows)), 'shades-INITIAL_FORMS': str(len(rows))})
    for index, row in enumerate(rows):
        for key, value in row.items():
            data[f'shades-{index}-{key}'] = value
    return data


def planted(owner,isolated,state='awaiting_marks'):
    record=Round.objects.create(slug='fixture-gloss',request_key=str(uuid4()),created_by=owner,
        product_brief=round_product.lip_gloss_brief(),state=state,current_step='marks' if state=='awaiting_marks' else 'pick')
    root=round_flow.round_root(record);root.mkdir(parents=True)
    rel='sketches/A1/picture.png';path=root/rel;path.parent.mkdir(parents=True);path.write_bytes(b'fixture image bytes')
    pub={'order':['A1'],'candidates':{'A1':{'id':'A1','picture':rel,'reading':{'idea_in_ten_words':'The wand reveals the frame'}}},'files':{rel:hashlib.sha256(path.read_bytes()).hexdigest()}}
    record.artifacts={'pairwise':pub}
    if state=='awaiting_pick':record.artifacts['pick_page']=pub
    record.save()
    return record,path


def test_intake_get_does_not_create_round_and_exposes_owner_defaults(client,isolated,monkeypatch):
    queued=[]
    monkeypatch.setattr(round_flow,'_enqueue',queued.append)
    response=client.get(reverse('dashboard:round_new'))
    assert response.status_code==200
    assert not Round.objects.exists() and not RoundStep.objects.exists() and not queued and not isolated.exists()
    for words in ('Start a new design','Rose Glass','#C9707A','Colour hex','Materials and closure','Measurements are provisional','$10'):
        assert words in response.content.decode()
    form=response.context['form']
    assert form.initial['stand_count']==12 and form.initial['stand_width']==110
    assert form.initial['stand_depth']==85 and form.initial['stand_height']==160
    assert form.initial['stand_board_thickness']==1.5
    assert form.initial['stand_columns']==4 and form.initial['stand_rows']==3
    assert not any(form.fields[key].required for key in ('width','depth','height','cap_height','diameter'))
    assert not set(form.fields)&{'collection','leaflet','net','back_en','back_es','back_ar','inci','ean','batch'}
    assert not any(key.endswith('_role') for key in form.fields)
    assert 'panels' not in response.context


def test_structured_intake_preserves_twelve_panels_material_copy_and_hex():
    form,panels,shades=forms_for(form_data())
    assert form.is_valid(),form.errors
    assert panels.is_valid(),panels.errors
    assert shades.is_valid(),shades.errors
    brief=product_brief(form,panels,shades)
    assert len(brief['panels'])==12
    assert brief['dimensions_mm']['height']==100
    assert 'doe-foot' in brief['material']
    assert brief['copy']['collection'] and brief['copy']['leaflet']
    assert brief['shades'][0]['hex']=='#C9707A'
    assert brief['prompt_contract'] == round_product.PROMPT_CONTRACT
    assert set(brief['content_roles']) == set(round_product.content_fields(brief))
    assert brief['content_roles']['copy.leaflet'] == 'INSTRUCTION'
    assert brief['content_roles']['copy.collection'] == 'INSTRUCTION'
    assert brief['content_roles']['copy.inci'] == 'INSTRUCTION'
    assert brief['content_roles']['copy.product'] == 'COPY'
    assert brief['content_roles']['shades.0.name'] == 'COPY'


def test_intake_printed_name_and_ingredients_require_explicit_copy_treatment(client):
    data = form_data()
    data.update(collection='CLEAR INTERVAL', collection_role='COPY', inci='Ingredients: fixture only', inci_role='COPY')
    form, panels, shades = forms_for(data)
    assert form.is_valid() and panels.is_valid() and shades.is_valid()
    brief = product_brief(form, panels, shades)
    copy = round_product.printed_copy(brief)
    assert copy['copy.collection'] == 'CLEAR INTERVAL' and copy['copy.inci'] == 'Ingredients: fixture only'
    assert 'copy.leaflet' not in copy and 'copy.ean' not in copy and 'copy.required' not in copy
    assert brief['content_roles']['copy.required'] == 'COPY'
    response = client.get(reverse('dashboard:round_new'))
    html = response.content.decode()
    assert 'COPY · print these words verbatim' not in html
    assert 'INSTRUCTION · guide the design, never print' not in html
    assert 'Only the brand, product words, and shade names are lettering.' in html
    assert 'An idea may rename the shades' not in html


def test_intake_requires_role_for_each_copy_or_instruction_field():
    data = form_data()
    data.pop('leaflet_role')
    form, _, _ = forms_for(data)
    assert not form.is_valid() and 'leaflet_role' in form.errors
    data['leaflet_role'] = 'PRINT_IF_CONVENIENT'
    assert not forms_for(data)[0].is_valid()


def test_blank_extra_rows_are_ignored():
    data=form_data();data['panels-TOTAL_FORMS']='14';data['shades-TOTAL_FORMS']='4'
    for i in (12,13):data[f'panels-{i}-surface']='clear_acrylic'
    form,panels,shades=forms_for(data)
    assert form.is_valid() and panels.is_valid() and shades.is_valid(),(form.errors,panels.errors,shades.errors)
    assert len(product_brief(form,panels,shades)['panels'])==12


def test_legacy_intake_cannot_drop_a_required_body_face():
    data=form_data()
    data['panels-3-DELETE']='on'
    form,panels,shades=forms_for(data)
    assert form.is_valid() and panels.is_valid() and shades.is_valid()
    with pytest.raises(ValueError,match='body_right'):
        product_brief(form,panels,shades)


def test_intake_retains_an_explicit_blank_panel_declaration():
    data=form_data();data['panels-3-blank_reason']='An unprinted face reveals the liquid shade.'
    form,panels,shades=forms_for(data)
    assert form.is_valid() and panels.is_valid() and shades.is_valid()
    brief=product_brief(form,panels,shades)
    assert brief['panels'][3]['blank_reason']=='An unprinted face reveals the liquid shade.'


def test_start_idempotency_and_no_round_for_bad_hex(client,isolated):
    data=ideas_form_data();bad=dict(data);bad['shades-0-hex']='rose'
    response=client.post(reverse('dashboard:round_new'),bad)
    assert response.status_code==400 and not Round.objects.exists()
    first=client.post(reverse('dashboard:round_new'),data)
    assert first.status_code==302,first.content.decode()[:1000]
    second=client.post(reverse('dashboard:round_new'),data)
    assert second.status_code==302 and first.url==second.url
    assert Round.objects.count()==1
    assert not isolated.exists(), 'Only the queued worker may write round artifacts'


def test_new_design_starts_the_designer_flow_and_the_classic_page_is_kept_unlinked(client,isolated,monkeypatch):
    queued=[]
    monkeypatch.setattr(round_flow,'_enqueue',queued.append)
    response=client.get(reverse('dashboard:new'))
    html=response.content.decode()
    assert response.status_code==200 and response.templates[0].name=='dashboard/product_round_new.html'
    estimate=response.context['estimate']
    for key in ('research_usd','boards_usd','designs_usd'):
        assert 0<estimate[key]<estimate['first_pass_usd']
    # Holds per stage are upper bounds; with web research and reference pictures their sum passes the $10 ceiling,
    # which refuses any call that would cross it, and the page says so.
    assert estimate['first_pass_usd']<estimate['cap_usd']==10<estimate['most_usd']
    for words in ('Research','Six Tavily web searches','house library','Three mood boards','Three designs','None of these',
                  'Round ceiling: $10','up to $','never spends past it'):
        assert words in html
    assert not Round.objects.exists() and not queued
    for words in ('What are you designing?','target-chip','Open the display stand'):
        assert words not in html
    shell=client.get(reverse('dashboard:index')).content.decode()
    assert 'href="/dashboard/new/"' in shell and '/dashboard/new/classic/' not in shell
    classic=client.get(reverse('dashboard:new_classic'))
    assert classic.status_code==200 and 'What are you designing?' in classic.content.decode()
    assert client.get(reverse('dashboard:new')+'?brief=amethyst light').context['form'].initial['bar']=='amethyst light'
    data=ideas_form_data()
    first=client.post(reverse('dashboard:new'),data)
    record=Round.objects.get()
    assert first.status_code==302 and first.url==reverse('dashboard:product_round',args=[record.pk])
    assert record.product_brief['flow']=='designer/1' and record.current_step=='research' and record.budget_usd==10
    assert list(record.steps.values_list('name','state'))==[('research','queued')]
    assert not isolated.exists()


def designer_round(owner,isolated,state):
    """A designer round as its worker leaves it, with pinned board and design pictures."""
    brief=dict(round_ideas_brief.gloss_brief(),flow=round_ideas_brief.DESIGNER_FLOW)
    record=Round.objects.create(slug='fixture-designer',request_key=str(uuid4()),created_by=owner,product_brief=brief,
        state=state,current_step='board_pick' if state=='awaiting_board_pick' else 'pick',budget_usd=10)
    root=round_flow.round_root(record)
    def picture(relative):
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('png '+relative).encode())
        return hashlib.sha256(path.read_bytes()).hexdigest()
    candidates,files={},{}
    for ident in ('bold','refined','unexpected'):
        relative=f'boards/g1/{ident}/raw.png';files[relative]=picture(relative)
        candidates[ident]={'id':ident,'idea':'A '+ident+' board idea','link':'because the liquid shows','picture':relative,
            'picture_sha256':files[relative],'palette':[{'name':'Rose glass','hex':'#C9707A','role':'liquid'}],
            'materials':['Clear acrylic'],'finishes':['Hot foil'],'type':'A narrow serif','motif':'A facet','texture':'Frost'}
    record.artifacts={'boards':{'generation':1,'order':list(candidates),'candidates':candidates,'files':files,'taste_used':2}}
    if state!='awaiting_board_pick':
        record.artifacts['board_pick']={'id':'refined','reason':'Quiet and rich','board':candidates['refined']}
        designs,pins={},{}
        for ident in ('D1','D2','D3'):
            relative=f'designs/g1/{ident}/raw.png';pins[relative]=picture(relative)
            designs[ident]={'id':ident,'picture':relative,'picture_sha256':pins[relative],'idea':'Design idea '+ident,
                'composition':'Composition '+ident,'findings':[{'check':'truth','label':'Product truth visible','ok':True,'note':'Liquid shows'},
                    {'check':'banned','label':'Banned motifs absent','ok':False,'note':'A drip appears'},
                    {'check':'copy','label':'Copy present','ok':None,'note':'The check gave no reading for this.'}]}
        record.artifacts['pick_page']={'order':list(designs),'candidates':designs,'files':pins}
    record.save()
    from apps.pipeline.services.round_designer import DESIGNER_STEPS
    current=DESIGNER_STEPS.index(record.current_step)
    for position,name in enumerate(DESIGNER_STEPS):
        RoundStep.objects.create(round=record,name=name,position=position,
                                 state='complete' if position<current else 'waiting' if position==current else 'queued')
    return record


def test_designer_board_pick_page_shows_live_swatches_pinned_boards_and_one_redo(client,owner,isolated,monkeypatch,
                                                                                django_capture_on_commit_callbacks):
    record=designer_round(owner,isolated,'awaiting_board_pick')
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    html=response.content.decode()
    assert response.templates[0].name=='dashboard/product_designer_round.html'
    for words in ('Three mood boards','Based on your past picks','A bold board idea','Bold','Refined','Unexpected',
                  'fill="#C9707A"','#C9707A','Design from this board','Make three new boards','Waiting for your board'):
        assert words in html
    for ident in ('bold','refined','unexpected'):
        url=reverse('dashboard:product_round_file',args=[record.pk,f'boards/g1/{ident}/raw.png'])
        assert html.count('<img src="'+url+'"')==1
        assert client.get(url).content==(round_flow.round_root(record)/f'boards/g1/{ident}/raw.png').read_bytes()
    assert client.get(reverse('dashboard:product_round_file',args=[record.pk,'research.json'])).status_code==404
    calls=[]
    monkeypatch.setattr(round_flow,'_enqueue',calls.append)
    assert client.post(reverse('dashboard:product_round_board',args=[record.pk]),{'board':'nope'}).status_code==400
    with django_capture_on_commit_callbacks(execute=True):
        response=client.post(reverse('dashboard:product_round_none',args=[record.pk]),{'stage':'boards','line':'Too quiet'})
    assert response.status_code==302 and calls==[record.steps.get(name='boards').pk]
    assert record.steps.get(name='boards').state=='queued' and record.steps.get(name='board_pick').state=='waiting'
    record.refresh_from_db()
    assert record.state=='queued' and record.current_step=='boards' and record.artifacts['redo']['boards']['line']=='Too quiet'
    assert 'boards' not in record.artifacts and record.artifacts['rejected_boards']['boards']['generation']==1


def test_designer_design_pick_page_shows_findings_beside_each_design(client,owner,isolated):
    record=designer_round(owner,isolated,'awaiting_pick')
    html=client.get(reverse('dashboard:product_round',args=[record.pk])).content.decode()
    for words in ('Your board · Refined','Quiet and rich','Three designs','Product truth visible','Banned motifs absent',
                  'A drip appears','Not read','Record my pick','Draw three new designs','never removes one'):
        assert words in html
    assert 'Make three new boards' not in html and 'Design from this board' not in html
    for ident in ('D1','D2','D3'):
        assert client.get(reverse('dashboard:product_round_file',args=[record.pk,f'designs/g1/{ident}/raw.png'])).status_code==200
    record.artifacts['redo']={'designs':{'line':'Used once'}};record.save()
    html=client.get(reverse('dashboard:product_round',args=[record.pk])).content.decode()
    assert 'Draw three new designs' not in html and 'Used once' in html
    assert client.post(reverse('dashboard:product_round_none',args=[record.pk]),{'stage':'designs','line':'Again'}).status_code==400


def test_marks_page_has_forms_and_pinned_images(client,owner,isolated):
    record,path=planted(owner,isolated)
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    assert response.status_code==200
    text=response.content.decode()
    assert 'What must survive' in text and 'Save my marks' in text
    assert 'http-equiv="refresh"' not in text
    url=reverse('dashboard:product_round_file',args=[record.pk,'sketches/A1/picture.png'])
    assert client.get(url).content==path.read_bytes()
    path.write_bytes(b'changed')
    assert client.get(url).status_code==404


@pytest.mark.parametrize('count', [1, 3])
def test_short_final_page_shows_actual_count_and_explains_missing_places(client, owner, isolated, count):
    record, _ = planted(owner, isolated, state='awaiting_pick')
    pub = record.artifacts['pick_page']
    card = pub['candidates']['A1']
    ids = ['A1', 'A2', 'A2/A'][:count]
    pub['order'] = ids
    pub['candidates'] = {key: dict(card, id=key) for key in ids}
    reason = f'Showing all {count} available candidates from the marked parents and their eligible forks. Forks disqualified: 3.'
    pub['pool_summary'] = {'available': count, 'shortfall_reason': reason}
    record.save(update_fields=['artifacts'])
    response = client.get(reverse('dashboard:product_round', args=[record.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert f'{count} final candidate' in html and reason in html
    assert 'The final six' not in html and 'ordered pair by pair' not in html
    assert 'This page waits for your pick' in html
    assert [card['id'] for card in response.context['cards']] == ids


@pytest.mark.parametrize('state', ['awaiting_marks', 'awaiting_pick'])
@pytest.mark.parametrize('metadata, text, expected_label', [
    ({'word_count': 12, 'over_length': True, 'length_reasked': True},
     'One two three four five six seven eight nine ten eleven twelve', True),
    ({'word_count': 5, 'over_length': False, 'length_reasked': False},
     'The wand reveals the frame', False),
    ({}, 'The wand reveals the frame', False),
], ids=['over-length', 'within-limit', 'earlier-record'])
def test_candidate_card_labels_only_flagged_readings(client, owner, isolated, state, metadata, text, expected_label):
    record, _ = planted(owner, isolated, state=state)
    for publication in record.artifacts.values():
        publication['candidates']['A1']['reading'] = {'idea_in_ten_words': text, **metadata}
    record.save(update_fields=['artifacts'])
    response = client.get(reverse('dashboard:product_round', args=[record.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert text in content, 'The provider reading must remain unedited on the owner page.'
    assert ('<strong>over length</strong>' in content) is expected_label


def test_foreign_owner_and_path_escape_refused(owner,isolated):
    record,path=planted(owner,isolated)
    other=get_user_model().objects.create_user(username='other',password='fixture')
    other.groups.add(Group.objects.get_or_create(name='Designer')[0])
    client=Client();client.force_login(other)
    assert client.get(reverse('dashboard:product_round',args=[record.pk])).status_code==403
    assert client.post(reverse('dashboard:product_round_marks',args=[record.pk]),{}).status_code==403
    client.force_login(owner)
    record.artifacts['pairwise']['files']['../../outside.png']='0'*64;record.save()
    assert client.get(reverse('dashboard:product_round_file',args=[record.pk,'../../outside.png'])).status_code==404


def test_csrf_required_for_start_and_decisions(owner,isolated):
    client=Client(enforce_csrf_checks=True);client.force_login(owner)
    assert client.post(reverse('dashboard:round_new'),form_data()).status_code==403
    record,path=planted(owner,isolated)
    assert client.post(reverse('dashboard:product_round_marks',args=[record.pk]),{}).status_code==403
    assert client.post(reverse('dashboard:product_round_pick',args=[record.pk]),{}).status_code==403


def test_decision_posts_go_through_round_service(client,owner,isolated,monkeypatch):
    record,path=planted(owner,isolated)
    calls=[]
    monkeypatch.setattr(round_flow,'submit_marks',lambda *args:calls.append(args))
    response=client.post(reverse('dashboard:product_round_marks',args=[record.pk]),{'candidate_0':'A1','preserve_0':'The cap line'})
    assert response.status_code==302 and calls[0][1]==[{'id':'A1','preserve':'The cap line'}]
    monkeypatch.setattr(round_flow,'submit_pick',lambda *args,**kwargs:calls.append((args,kwargs)))
    response=client.post(reverse('dashboard:product_round_pick',args=[record.pk]),{'candidate':'A1','reason':'The object proves it','merge_candidate':'B2','merge_element':'rim'})
    assert response.status_code==302 and calls[-1][1]['merge']=={'candidate':'B2','element':'rim'}


def test_failed_step_has_app_retry_and_running_refresh(client,owner,isolated,monkeypatch):
    record,path=planted(owner,isolated,state='failed')
    record.error_message='Fixture truncation';record.save()
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    assert b'Retry failed step' in response.content
    calls=[];monkeypatch.setattr(round_flow,'retry_round',lambda *args:calls.append(args))
    assert client.post(reverse('dashboard:product_round_retry',args=[record.pk])).status_code==302
    assert calls[0][0]==record.pk
    record.state='running';record.save()
    assert b'http-equiv="refresh"' in client.get(reverse('dashboard:product_round',args=[record.pk])).content


def test_real_marks_post_requires_displayed_id_and_one_line(client,owner,isolated):
    record,path=planted(owner,isolated)
    RoundStep.objects.create(round=record,name='marks',position=7,state='waiting')
    url=reverse('dashboard:product_round_marks',args=[record.pk])
    for data in ({},{'candidate_0':'foreign','preserve_0':'Keep it'}, {'candidate_0':'A1','preserve_0':'Two\nlines'}):
        assert client.post(url,data).status_code==400
        record.refresh_from_db();assert not record.marks
    assert client.post(url,{'candidate_0':'A1','preserve_0':'The cap line'}).status_code==302
    record.refresh_from_db()
    assert record.state=='queued' and record.marks['source']['user_id']==owner.pk


def test_real_pick_post_requires_reason_and_valid_optional_merge(client,owner,isolated):
    record,path=planted(owner,isolated,state='awaiting_pick')
    record.artifacts.update(sketches={'candidates':{'A1':{},'B2':{}}},forks={'candidates':{}});record.save()
    RoundStep.objects.create(round=record,name='pick',position=11,state='waiting')
    url=reverse('dashboard:product_round_pick',args=[record.pk])
    assert client.post(url,{'candidate':'A1'}).status_code==400
    assert client.post(url,{'candidate':'A1','reason':'Reason','merge_candidate':'A1','merge_element':'rim'}).status_code==400
    assert client.post(url,{'candidate':'A1','reason':'The object proves it','merge_candidate':'B2','merge_element':'rim'}).status_code==302
    record.refresh_from_db()
    assert record.pick['id']=='A1' and record.pick['merge']=={'candidate':'B2','element':'rim'}
    assert record.state=='queued'


def test_page_separates_settled_spend_from_outstanding_holds(client,owner,isolated,monkeypatch):
    record,path=planted(owner,isolated)
    monkeypatch.setattr(round_flow,'summary',lambda record:{'steps':[],'spend':{'actual_usd':.20,'reserved_usd':.30,'accounted_usd':.50,'budget_usd':22}})
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    assert b'Spent $0.20' in response.content and b'held $0.30' in response.content
    assert b'Spent $0.50' not in response.content


def test_page_recovers_committed_queue_only_after_ownership_check(client,owner,isolated,monkeypatch):
    record,path=planted(owner,isolated)
    recovered=[]
    monkeypatch.setattr(round_flow,'recover_dispatch',lambda row:recovered.append(row.pk))
    assert client.get(reverse('dashboard:product_round',args=[record.pk])).status_code==200
    assert recovered==[record.pk]


def test_shell_and_pulse_include_only_owned_active_rounds(client,owner,isolated,monkeypatch):
    from apps.dashboard import board,context_processors
    other=get_user_model().objects.create_user(username='foreign-round-shell')
    for state in ('awaiting_marks','awaiting_pick','queued','running','failed','complete'):
        Round.objects.create(slug='own-'+state,request_key=str(uuid4()),created_by=owner,
                             product_brief={'name':'Own '+state},state=state)
        Round.objects.create(slug='foreign-'+state,request_key=str(uuid4()),created_by=other,
                             product_brief={'name':'Foreign '+state},state=state)
    pills=context_processors.pills(cards=[],user=owner)
    assert {p['key']:p['count'] for p in pills}=={'run':2,'wait':2,'attn':1}
    assert all(c['title'].startswith('Own ') for p in pills for c in p['cards'])
    monkeypatch.setattr(board,'counts',lambda:{board.WORKING:3,board.WAITING:4,board.ATTENTION:5})
    pulse=client.get(reverse('dashboard:pulse')).json()
    assert pulse['counts']=={'run':5,'wait':6,'attn':6}
    response=client.get(reverse('dashboard:round_list'))
    assert b'>Rounds</a>' in response.content
    assert b'Your rounds' in response.content


def test_master_button_owner_boundary_and_preview_file_pins(client,owner,isolated,monkeypatch):
    from apps.pipeline.services import round_master_flow as mf
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services.round_master_flow import STEPS
    record=Round.objects.create(slug='master-page',request_key=uuid4().hex,product_brief=round_product.lip_gloss_brief(),
        created_by=owner,state='complete',current_step='pick',pick={'id':'C5','reason':'fixture'})
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    assert b'Build the master' in response.content
    steps={name:{'state':'waiting','attempts':0,'dispatches':0,'history':[],'result':{}} for name in STEPS}
    steps['panels']['state']='failed'
    build=RoundMaster.objects.create(round=record,state='failed',steps=steps)
    page=client.get(reverse('dashboard:product_round_master',args=[record.pk]))
    assert b'Retry' in page.content and b'Preparing panels' in page.content
    assert b'Build the master' not in client.get(reverse('dashboard:product_round',args=[record.pk])).content
    pending=[];monkeypatch.setattr(mf,'enqueue',pending.append)
    assert client.get(reverse('dashboard:product_round_master_retry',args=[record.pk])).status_code==405
    stranger=get_user_model().objects.create_user(username='master-stranger',password='fixture')
    from django.contrib.auth.models import Group
    stranger.groups.add(Group.objects.get_or_create(name='Design Team')[0])
    outsider=Client();outsider.force_login(stranger)
    assert outsider.post(reverse('dashboard:product_round_master_retry',args=[record.pk])).status_code==403
    folder=mf.root(build);folder.mkdir(parents=True)
    path=folder/'proof.png';path.write_bytes(b'fixture proof')
    build.publication={'files':{'proof.png':hashlib.sha256(path.read_bytes()).hexdigest()}};build.save()
    url=reverse('dashboard:product_round_master_file',args=[record.pk,'proof.png'])
    assert client.get(url).status_code==200
    path.write_bytes(b'tampered');assert client.get(url).status_code==404
    assert client.get(reverse('dashboard:product_round_master_file',args=[record.pk,'secret.json'])).status_code==404
    assert not pending


@pytest.mark.parametrize('product_type', ['Lip gloss', 'Eye palette'])
def test_ideas_intake_accepts_optional_dimensions_and_keeps_copy_whitelist(product_type):
    data=ideas_form_data()
    data.update(name=product_type,product_type=product_type,shape='An owner described shape',
                width='',depth='',height='',cap_height='',diameter='',
                stand_width='',stand_depth='',stand_height='',stand_board_thickness='',
                stand_columns='',stand_rows='',collection='PRINT THIS INSTRUCTION',
                collection_role='COPY',leaflet='DO NOT PRINT',panels='forged panel inventory')
    form,shades=product_ideas_forms.forms_for(data)
    assert form.is_valid() and shades.is_valid(),(form.errors,shades.errors)
    brief=product_ideas_forms.product_brief(form,shades)
    assert round_ideas_brief.is_ideas_brief(brief)
    assert brief['dimensions_mm']=={} and brief['stand']['dimensions_mm']=={}
    assert brief['stand']['count']==12 and brief['measurements_provisional']
    assert set(brief['copy'])=={'brand','product'}
    assert not set(brief)&{'panels','carton','leaflet','content_roles'}
    assert 'PRINT THIS INSTRUCTION' not in str(round_ideas_brief.printed_copy(brief))


def test_ideas_blank_preset_is_generic_and_still_waits_for_start(client,isolated):
    response=client.get(reverse('dashboard:round_new')+'?preset=blank')
    assert response.status_code==200
    form=response.context['form']
    assert form.initial['name']=='' and form.initial['stand_count']==12
    assert not form.initial.get('width') and not form.initial.get('stand_width')
    assert not hasattr(form.fields['product_type'],'choices')
    assert not Round.objects.exists() and not RoundStep.objects.exists() and not isolated.exists()


def test_ideas_page_shows_original_top_three_and_only_owner_pick(client,owner,isolated,monkeypatch):
    record,path=planted(owner,isolated,state='awaiting_pick')
    record.product_brief=round_ideas_brief.gloss_brief()
    pins={};candidates={}
    for index in range(3):
        ident='I'+str(index+1);relative='sketches/'+ident+'/picture.png'
        picture=round_flow.round_root(record)/relative
        picture.parent.mkdir(parents=True,exist_ok=True);picture.write_bytes(('original '+ident).encode())
        pins[relative]=hashlib.sha256(picture.read_bytes()).hexdigest()
        candidates[ident]={'id':ident,'picture':relative,'idea':'Original product and stand idea '+str(index+1)}
    record.artifacts={'pick_page':{'order':list(candidates),'candidates':candidates,'files':pins}}
    record.save()
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    html=response.content.decode()
    assert response.templates[0].name=='dashboard/product_ideas_round.html'
    assert [card['id'] for card in response.context['cards']]==list(candidates)
    for card in candidates.values():
        assert card['idea'] in html
        url=reverse('dashboard:product_round_file',args=[record.pk,card['picture']])
        assert html.count('<img src="'+url+'"')==1
        assert client.get(url).content==(round_flow.round_root(record)/card['picture']).read_bytes()
    assert 'name="reason"' in html and 'Record my pick' in html
    for forbidden in ('merge_candidate','merge_element','Save my marks','Build the master','whole-object sheet','product drawing'):
        assert forbidden not in html
    # The old endpoints cannot introduce a development or manufacturing step into this mode.
    calls=[]
    monkeypatch.setattr(round_flow,'submit_marks',lambda *args:calls.append(args))
    assert client.post(reverse('dashboard:product_round_marks',args=[record.pk]),{}).status_code==400
    assert client.post(reverse('dashboard:product_round_pick',args=[record.pk]),
        {'candidate':'I1','reason':'One idea','merge_candidate':'I2','merge_element':'anything'}).status_code==400
    record.state='complete';record.pick={'id':'I1','reason':'The product and stand share one idea'};record.save()
    from apps.pipeline.services import round_master_flow
    monkeypatch.setattr(round_master_flow,'start',lambda *args:calls.append(args))
    response=client.post(reverse('dashboard:product_round_master_start',args=[record.pk]))
    assert response.status_code==400 and not calls
    assert b'Build the master' not in client.get(reverse('dashboard:product_round',args=[record.pk])).content


def test_designer_research_page_shows_sources_takeaways_previews_and_the_boards_that_used_them(client,owner,isolated):
    record=designer_round(owner,isolated,'awaiting_board_pick')
    sha='1'*64
    record.artifacts['research']={'category':'Lip gloss at a counter','references':['Clear walls lead'],'launches':['A recent clear launch'],
        'materials':['Acrylic'],'finishes':['Foil'],'colour':['Rose'],'type':['Serif'],'avoid':['Drips'],'web_search':'used',
        'searches':[{'topic':'category','query':'lip gloss packaging and counter display design','status':'complete','results':5},
                    {'topic':'launches','query':'new lip gloss launches 2026','status':'failed','results':0,'error':'tavily HTTP 503'}],
        'sources':[{'url':'https://example.com/launch','title':'A launch','takeaway':'Clear walls lead the shelf'},
                   {'url':'javascript:alert(1)','title':'Planted','takeaway':'Never a link'}],'unverified_sources':1,
        'library':{'words':['gloss','acrylic'],'colours':['#C9707A'],'matches':[
            {'id':'L1','sha256':sha,'name':'facets.png','kind':'pattern','subject':'A gold facet pattern','tags':[],'style':[],
             'colours':['#C9707A'],'may_reference':True,'why_words_only':''},
            {'id':'L2','sha256':'2'*64,'name':'mark.png','kind':'logo','subject':'A mark','tags':[],'style':[],
             'colours':['#B8925A'],'may_reference':False,'why_words_only':'words only — a logo'}]}}
    boards=record.artifacts['boards']
    boards['candidates']['bold'].update(library=['L1','L2'],reference_inputs=[{'id':'L1','sha256':'f'*64,'library_sha256':sha}])
    record.save()
    html=client.get(reverse('dashboard:product_round_research',args=[record.pk])).content.decode()
    for words in ('Web sources','Clear walls lead the shelf','href="https://example.com/launch"','Tavily web search (2 searches)',
                  '“lip gloss packaging and counter display design” — 5 pages','“new lip gloss launches 2026” — failed',
                  '1 named source left out','Recent launches','A recent clear launch','House library matches',
                  'May be a reference picture','Words only — a logo','Used by Bold · its picture','Used by Bold · words',
                  reverse('dashboard:material_preview',args=[sha])):
        assert words in html, words
    assert 'href="javascript:' not in html and 'Never a link' in html
    assert reverse('dashboard:product_round_research',args=[record.pk]) in client.get(reverse('dashboard:product_round',args=[record.pk])).content.decode()
    legacy=Round.objects.create(slug='fixture-legacy',request_key=str(uuid4()),created_by=owner,product_brief=round_ideas_brief.gloss_brief())
    assert client.get(reverse('dashboard:product_round_research',args=[legacy.pk])).status_code==404
