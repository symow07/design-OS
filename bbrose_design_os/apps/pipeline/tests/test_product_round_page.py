"""App entry, owner decisions and pinned artwork; fixtures never call providers."""
import hashlib
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from apps.pipeline.models import Round, RoundStep
from apps.pipeline.services import round_flow
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
    return tmp_path/'rounds'


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
        product_brief={'schema': 'round_product/1', 'name': 'Lip gloss — whole-object round', 'product_type': 'lip_gloss'},state=state,current_step='marks' if state=='awaiting_marks' else 'pick')
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
    for words in ('Start a new design','Rose Glass','#C9707A','Colour hex','Materials and closure','Measurements are provisional','$2.00'):
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
    # the owner's ruling of 2026-10-29: one round, brief to Make my files, at most $2.00 all in — the page shows what it
    # is expected to cost before Start and the hard cap; the holds are upper bounds that settle to the real cost
    # measured from real costs (the owner, 2026-10-29): $2.48 with every face at high, back under the cap with the
    # header and the bottle at high and the other faces at medium — and the files at high would be about twice
    assert estimate['cap_usd']==2.0 and estimate['expected_usd']<2.0 and not estimate['over_cap']
    assert estimate['files_all_high_usd'] > 1.8 * estimate['expected']['files'] and 'above the $2.00 cap' not in html
    assert estimate['expected_usd']==round(sum(estimate['expected'].values()),2) and estimate['files_usd']>0
    for words in ('Research','Six Tavily web searches','house library','Three mood boards','Three designs','None of these',
                  'Your files','Hard cap: $2.00','about $%.2f, and never more than $2.00' % estimate['expected_usd'],
                  'is never made','medium quality','one sheet of','bottle painted on its own net',
                  'each painted alone and reused on every face','a vector the engine draws'):
        assert words in html, words
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
    assert record.product_brief['flow']=='designer/1' and record.current_step=='research' and record.budget_usd==2
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
                  'A drip appears','Not read','Record my pick','Draw three new designs','is painted once more; if it still fails, it is not shown'):
        assert words in html
    assert 'Make three new boards' not in html and 'Design from this board' not in html
    for ident in ('D1','D2','D3'):
        assert client.get(reverse('dashboard:product_round_file',args=[record.pk,f'designs/g1/{ident}/raw.png'])).status_code==200
    record.artifacts['redo']={'designs':{'line':'Used once'}};record.save()
    html=client.get(reverse('dashboard:product_round',args=[record.pk])).content.decode()
    assert 'Draw three new designs' not in html and 'Used once' in html
    assert client.post(reverse('dashboard:product_round_none',args=[record.pk]),{'stage':'designs','line':'Again'}).status_code==400


def test_foreign_owner_and_path_escape_refused(owner,isolated):
    record=designer_round(owner,isolated,'awaiting_pick')
    other=get_user_model().objects.create_user(username='other',password='fixture')
    other.groups.add(Group.objects.get_or_create(name='Designer')[0])
    client=Client();client.force_login(other)
    assert client.get(reverse('dashboard:product_round',args=[record.pk])).status_code==403
    assert client.post(reverse('dashboard:product_round_pick',args=[record.pk]),{}).status_code==403
    client.force_login(owner)
    record.artifacts['pick_page']['files']['../../outside.png']='0'*64;record.save()
    assert client.get(reverse('dashboard:product_round_file',args=[record.pk,'../../outside.png'])).status_code==404


def test_decision_posts_go_through_round_service(client,owner,isolated,monkeypatch):
    record=designer_round(owner,isolated,'awaiting_pick')
    calls=[]
    monkeypatch.setattr(round_flow,'submit_pick',lambda *args,**kwargs:calls.append((args,kwargs)))
    response=client.post(reverse('dashboard:product_round_pick',args=[record.pk]),{'candidate':'D2','reason':'The object proves it'})
    assert response.status_code==302 and calls[-1][0][1:3]==('D2','The object proves it') and calls[-1][1]['merge'] is None
    # a design is picked whole: a merge is refused on the page, before the service
    response=client.post(reverse('dashboard:product_round_pick',args=[record.pk]),{'candidate':'D2','reason':'Reason','merge_candidate':'D1','merge_element':'rim'})
    assert response.status_code==400 and len(calls)==1


def test_failed_step_has_app_retry_and_running_refresh(client,owner,isolated,monkeypatch):
    record=designer_round(owner,isolated,'awaiting_pick')
    record.state='failed';record.error_message='Fixture truncation';record.save()
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    assert b'This step needs attention' in response.content and b'Retry</button>' in response.content
    calls=[];monkeypatch.setattr(round_flow,'retry_round',lambda *args:calls.append(args))
    assert client.post(reverse('dashboard:product_round_retry',args=[record.pk])).status_code==302
    assert calls[0][0]==record.pk
    record.state='running';record.save()
    assert b'http-equiv="refresh"' in client.get(reverse('dashboard:product_round',args=[record.pk])).content


def test_page_separates_settled_spend_from_outstanding_holds(client,owner,isolated,monkeypatch):
    record=designer_round(owner,isolated,'awaiting_pick')
    monkeypatch.setattr(round_flow,'summary',lambda record:{'steps':[],'spend':{'actual_usd':.20,'reserved_usd':.30,'accounted_usd':.50,'budget_usd':22}})
    response=client.get(reverse('dashboard:product_round',args=[record.pk]))
    assert b'Spent $0.20' in response.content and b'held $0.30' in response.content
    assert b'Spent $0.50' not in response.content


def test_page_recovers_committed_queue_only_after_ownership_check(client,owner,isolated,monkeypatch):
    record=designer_round(owner,isolated,'awaiting_pick')
    recovered=[]
    monkeypatch.setattr(round_flow,'recover_dispatch',lambda row:recovered.append(row.pk))
    assert client.get(reverse('dashboard:product_round',args=[record.pk])).status_code==200
    assert recovered==[record.pk]


def test_shell_and_pulse_include_only_owned_active_rounds(client,owner,isolated,monkeypatch):
    # [the owner's goal of 2026-10-29] the bar classifies rounds as Home does (dashboard.views.round_card): rounds of the
    # designer flow; a picked round with no files build waits for its owner's "Build the files"; a retired round is none
    from apps.dashboard import board,context_processors
    other=get_user_model().objects.create_user(username='foreign-round-shell')
    for state in ('awaiting_marks','awaiting_pick','queued','running','failed','complete'):
        for user,who in ((owner,'Own '),(other,'Foreign ')):
            Round.objects.create(slug=who.strip().lower()+'-'+state,request_key=str(uuid4()),created_by=user,state=state,
                                 product_brief=dict(round_ideas_brief.gloss_brief(),flow=round_ideas_brief.DESIGNER_FLOW,
                                                    name=who+state),current_step='pick')
    Round.objects.create(slug='own-retired',request_key=str(uuid4()),created_by=owner,state='failed',
                         product_brief={'name':'Own retired'})
    pills=context_processors.pills(cards=[],user=owner)
    assert {p['key']:p['count'] for p in pills}=={'run':2,'wait':3,'attn':1}
    assert all(c['title'].startswith('Own ') and c['title']!='Own retired' for p in pills for c in p['cards'])
    monkeypatch.setattr(board,'counts',lambda:{board.WORKING:3,board.WAITING:4,board.ATTENTION:5})
    pulse=client.get(reverse('dashboard:pulse')).json()
    assert pulse['counts']=={'run':5,'wait':7,'attn':6}
    response=client.get(reverse('dashboard:round_list'))
    assert b'>Rounds</a>' in response.content
    assert b'Your rounds' in response.content


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


def test_a_retired_round_answers_in_words_on_the_list_and_its_page_and_takes_no_action(client,owner,isolated,monkeypatch):
    """The owner's goal of 2026-10-29: the twenty-design and whole-object rounds retired; a round of either kind still
    in the database is listed and opens, says where its records are, offers nothing, and an action changes nothing."""
    record,path=planted(owner,isolated,state='awaiting_pick')
    words=f'This round ran on the retired pipeline; its records stay in docs/rounds/{record.slug}/.'
    listed=client.get(reverse('dashboard:round_list'))
    assert listed.status_code==200 and words.encode() in listed.content and b'Retired' in listed.content
    enqueued=[]
    monkeypatch.setattr(round_flow,'_enqueue',enqueued.append)
    page=client.get(reverse('dashboard:product_round',args=[record.pk]))
    assert page.status_code==200 and words.encode() in page.content
    assert b'<form' not in page.content.split(b'<main',1)[-1].split(b'</main>',1)[0]
    before=(record.state,record.pick,record.artifacts)
    for name,data in (('dashboard:product_round_pick',{'candidate':'A1','reason':'The object proves it'}),
                      ('dashboard:product_round_retry',{})):
        response=client.post(reverse(name,args=[record.pk]),data)
        assert response.status_code==400 and words.encode() in response.content
    record.refresh_from_db()
    assert (record.state,record.pick,record.artifacts)==before and enqueued==[]
    assert client.get(reverse('dashboard:product_round_file',args=[record.pk,'sketches/A1/picture.png'])).status_code==404


def test_new_design_shows_the_stand_types_the_engine_builds_and_what_it_will_build(client,isolated):
    from pathlib import Path
    from django.conf import settings
    from apps.dielines.geometry.stand_types import buildable
    response=client.get(reverse('dashboard:round_new'))
    body=response.content.decode()
    assert response.status_code==200
    from django.utils.html import escape
    for row in buildable():
        assert row['label'] in body and escape(row['one_line']) in body and 'img/stands/%s.svg'%row['id'] in body
        assert (Path(settings.BASE_DIR)/'static/img/stands'/(row['id']+'.svg')).exists()
    assert 'Floor stand (FSDU)' in body and 'not built yet' in body
    assert response.context['stand_preview']['suggested'] in {row['id'] for row in buildable()}
    assert 'The engine suggests' in body and 'name="stand_type"' in body and 'It will build:' in body


def test_the_stand_preview_answers_with_its_suggestion_size_and_changes(client,isolated):
    url=reverse('dashboard:round_new_stand')
    reply=client.get(url,{'stand_count':12,'stand_rows':3,'stand_columns':4,'width':15,'depth':15,'height':100,'cap_height':30,'stand_width':110,'stand_depth':85,'stand_height':160}).json()
    assert reply['ok'] and reply['suggested']=='flat_tray_testers' and reply['type']=='flat_tray_testers' and reply['passed']
    assert reply['closed']['width']==110 and reply['closed']['height']==160
    assert any(row['dimension']=='depth' and row['from_mm']==85 for row in reply['changes'])
    chosen=client.get(url,{'stand_count':4,'stand_rows':1,'stand_columns':4,'width':15,'height':100,'cap_height':30,'stand_type':'tester_unit'}).json()
    assert chosen['type']=='tester_unit' and chosen['ok'] and chosen['passed']
    broken=client.get(url,{'stand_count':12,'stand_rows':5,'stand_columns':5,'width':15,'height':100}).json()
    assert not broken['ok'] and broken['words']


def test_the_chosen_stand_type_rides_in_the_brief_and_the_die_comes_from_it(client,isolated,monkeypatch):
    from apps.dashboard import product_round_views as views
    made={}
    def create(brief,user,key):
        made.update(brief)
        raise ValueError('stop here')
    monkeypatch.setattr(views.round_flow,'create_round',create)
    data=ideas_form_data()
    client.post(reverse('dashboard:round_new'),dict(data,stand_type='slanted_front'))
    assert made['stand']['type']=='slanted_front'
    made.clear()
    client.post(reverse('dashboard:round_new'),data)
    assert made['stand']['type'] in ('flat_tray_testers','counter_tray_header','stepped_tiered','slanted_front')
    made.clear()
    response=client.post(reverse('dashboard:round_new'),dict(data,stand_type='no_such_stand'))
    assert response.status_code==400 and not made
