"""The owner enters, marks, picks and retries a round in the app."""
import hashlib
import json
import mimetypes
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.pipeline.services.round_calls import round_costs
from apps.pipeline.services.round_files_faces import FACES
from apps.pipeline.models import Round
from apps.pipeline.permissions import ALL_ROLES, user_has_role
from apps.pipeline.services import round_files_gate, round_flow
from apps.pipeline.services.round_designer import DESIGNER_FLOW, gloss_brief, is_designer_brief
from .product_ideas_forms import forms_for, product_brief


def member(user):
    # from fidelity_views (the Day 4 page, retired 2026-10-29), unchanged
    if not user_has_role(user,*ALL_ROLES):raise PermissionDenied


STATE_LABELS={'queued':'Queued','running':'Working','awaiting_marks':'Waiting for your marks','awaiting_board_pick':'Waiting for your board','awaiting_pick':'Waiting for your pick','failed':'Needs attention','complete':'Pick recorded'}
DIRECTION_LABELS={'bold':'Bold','refined':'Refined','unexpected':'Unexpected'}


def owned(request,pk):
    member(request.user)
    record=get_object_or_404(Round,pk=pk)
    if record.created_by_id != request.user.pk and not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    return record


def publication(record):
    """Only publication records carried by the database authorize files."""
    if not is_designer_brief(record.product_brief):return {}   # a retired round publishes nothing here
    artifacts=record.artifacts or {}
    for key in ('pick_page',):
        value=artifacts.get(key) or {}
        if value.get('candidates') and value.get('files'):
            return value
        rel=value.get('publication')
        if isinstance(rel,dict) and rel.get('candidates') and rel.get('files'):
            return rel
        pin=value.get('publication_sha256')
        if rel and pin:
            root=round_flow.round_root(record).resolve()
            path=(root/rel).resolve()
            if not path.is_relative_to(root): raise ValueError('Publication escaped round folder')
            data=path.read_bytes()
            if hashlib.sha256(data).hexdigest()!=pin: raise ValueError('Publication pin changed')
            return json.loads(data)
    return {}


def board_publication(record):
    """The designer flow's current boards, served only while their pins match."""
    value=(record.artifacts or {}).get('boards') or {}
    return value if is_designer_brief(record.product_brief) and value.get('candidates') and value.get('files') else {}


def research_context(record):
    """The research page: web sources with their takeaways; library matches with previews and the boards that used them."""
    from urllib.parse import urlsplit
    artifacts=record.artifacts or {}
    notes=artifacts.get('research') or {}
    passes=[('',artifacts.get('boards') or {})]+[('earlier ',(artifacts.get('rejected_boards') or {}).get('boards') or {})]
    used={}
    for prefix,boards in passes:
        for ident in boards.get('order',[]):
            board=boards['candidates'][ident];label=prefix+DIRECTION_LABELS.get(ident,ident)
            pictures={item['id'] for item in board.get('reference_inputs',[])}
            for key in board.get('library',[])+sorted(pictures-set(board.get('library',[]))):
                used.setdefault(key,[]).append(label+(' · its picture' if key in pictures else ' · words'))
    matches=[]
    for row in (notes.get('library') or {}).get('matches',[]):
        matches.append(dict(row,used_by=used.get(row['id'],[]),
                            preview_url=reverse('dashboard:material_preview',args=[row['sha256']])))
    sources=[dict(row,link=urlsplit(row['url']).scheme in ('http','https')) for row in notes.get('sources',[])]
    lists=[(label,notes.get(key,[])) for key,label in (('references','The category'),('launches','Recent launches'),
           ('materials','Materials'),('finishes','Finishes'),('colour','Colour'),('type','Type'),('avoid','What to avoid'))]
    return {'round':record,'notes':notes,'sources':sources,'matches':matches,'lists':lists}


def designer_context(record,cards):
    artifacts=record.artifacts or {}
    boards=board_publication(record)
    rows=[]
    for ident in boards.get('order',[]):
        item=dict(boards['candidates'][ident])
        item['label']=DIRECTION_LABELS.get(ident,ident)
        item['picture_url']=reverse('dashboard:product_round_file',args=[record.pk,item['picture']])
        rows.append(item)
    picked=artifacts.get('board_pick') or {}
    redo=artifacts.get('redo') or {}
    return {'boards':rows,'board_pick':picked,
            'picked_board':next((row for row in rows if row['id']==picked.get('id')),None),
            'taste_used':boards.get('taste_used',0),'redo':redo,
            'is_board_pick':record.state=='awaiting_board_pick',
            'can_redo_boards':record.state=='awaiting_board_pick' and 'boards' not in redo,
            'can_redo_designs':record.state=='awaiting_pick' and 'designs' not in redo}


def page_context(record,error=''):
    summary=round_flow.summary(record)
    record.display_state=STATE_LABELS.get(record.state,record.state)
    try:published=publication(record)
    except (OSError,ValueError,TypeError):
        published={};error=error or 'The published artwork changed or is unavailable. Its file pins must match before it can be shown.'
    cards=[]
    candidates=published.get('candidates',{})
    if isinstance(candidates,list): candidates={row['id']:row for row in candidates}
    for ident in published.get('order',[]):
        item=dict(candidates.get(ident,{}) or {},id=ident)
        item['words']=item.get('idea','')
        for role in ('picture','drawing','folded','loaded'):
            if item.get(role):item[role+'_url']=reverse('dashboard:product_round_file',args=[record.pk,item[role]])
        cards.append(item)
    build = getattr(record, 'master_build', None) if record.state == 'complete' else None
    files_build = build if build is not None and build.inputs.get('schema') == 'picked_picture_files/1' else None
    dropped=[row for _key,row in sorted((published.get('dropped') or {}).items())]
    return {**designer_context(record,cards),'round':record,'summary':summary,'cards':cards,'error':error,'dropped':dropped,
            'files_build':files_build,'can_build_files':record.state == 'complete' and build is None and not round_flow.rejected(record),
            'final_pool':published.get('pool_summary'),
            'is_pick':record.state=='awaiting_pick',
            'refresh':record.state in ('queued','running'),
            'brief_pretty':json.dumps(record.product_brief,ensure_ascii=False,indent=2),
            'rejected':round_flow.rejected_words(record) if round_flow.rejected(record) else '',
            'costs':round_costs(record,{key:face['label'] for key,face in FACES.items()})}


def retired_context(record,error=''):
    """A retired round answers in words: what it was and where its records are; no action."""
    record.display_state='Retired'
    return {'round':record,'summary':round_flow.summary(record),'retired':round_flow.retired_words(record),'error':error}


@login_required
@require_GET
def index(request):
    member(request.user)
    records=Round.objects.order_by('-created_at')
    if not (request.user.is_staff or request.user.is_superuser):records=records.filter(created_by=request.user)
    records=list(records[:100])
    for record in records:
        retired=round_flow.is_retired_round(record)
        record.display_state='Retired' if retired else STATE_LABELS.get(record.state,record.state)
        if round_flow.rejected(record):record.display_state='Rejected'
        record.retired=round_flow.retired_words(record) if retired else ''
    return render(request,'dashboard/product_round_list.html',{'rounds':records})


def start_estimate(user,brief=None):
    """Upper bounds from the reservations' own formulas, with this owner's taste memory, before Start."""
    from apps.pipeline.services import round_designer
    taste=round_designer.taste_entries(user.pk)
    return dict(round_designer.spend_estimate(brief or gloss_brief(),taste),taste=len(taste))


@login_required
@require_http_methods(['GET','POST'])
def new(request):
    """NEW DESIGN — the designer flow (the owner, 2026-10-27): brief, research, three boards, three designs, a pick."""
    member(request.user)
    words=' '.join(request.GET.get('brief','').split())
    form,shades=forms_for(request.POST if request.method=='POST' else None,
                          generic=request.GET.get('preset')=='blank',words=words)
    brief=None
    if request.method=='POST':
        checks=(form.is_valid(),shades.is_valid())
        if all(checks):
            try:
                brief=product_brief(form,shades,flow=DESIGNER_FLOW)
                record=round_flow.create_round(brief,request.user,str(form.cleaned_data['request_key']))
            except ValueError as exc:form.add_error(None,str(exc));brief=None
            else:return redirect('dashboard:product_round',pk=record.pk)
    return render(request,'dashboard/product_round_new.html',
                  {'form':form,'shades':shades,'estimate':start_estimate(request.user,brief),'stand_cards':stand_cards(),
                   'stand_preview':stand_preview_for(form.data if form.is_bound else {key:form.get_initial_for_field(field,key) for key,field in form.fields.items()})},
                  status=400 if request.method=='POST' else 200)


def stand_cards():
    from apps.dielines.geometry.stand_types import all_types
    return [{'id':row['id'],'label':row['label'],'line':row['one_line'],'working':row.get('status')=='working',
             'drawing':'img/stands/%s.svg'%row['id']} for row in all_types()]


def _number(data,key):
    try:value=float(data.get(key) or 0)
    except (TypeError,ValueError):return 0.0
    return value if value>0 else 0.0


def stand_preview_for(data):
    """What the engine would build for what the form holds now: the type it suggests, the closed size, and each change from the sizes given.
    Solved from the rules, at $0; a form that cannot be solved yet says so in words."""
    from apps.dielines.geometry import counter_display,stand_templates,stand_types
    count=int(_number(data,'stand_count')) or 12
    rows,columns=int(_number(data,'stand_rows')),int(_number(data,'stand_columns'))
    height=_number(data,'height') or 100.0
    picked=data.get('stand_type') or ''
    if picked not in {row['id'] for row in stand_types.buildable()}:
        picked=''
    suggestion=stand_types.suggest(count=count,rows=rows or None,product_height_mm=height)
    chosen=picked or suggestion['type']
    width=_number(data,'width') or _number(data,'diameter') or 15.0
    brief={'dimensions_mm':{'width':width,'depth':_number(data,'depth') or width,'height':height,'cap_height':_number(data,'cap_height') or None},
           'stand':{'count':count,'layout':{key:value for key,value in (('rows',rows),('columns',columns)) if value},
                    'dimensions_mm':{key:_number(data,'stand_'+key) for key in ('width','depth','height','board_thickness') if _number(data,'stand_'+key)}}}
    out={'suggested':suggestion['type'],'suggested_label':stand_types.label(suggestion['type']),'why':suggestion['why'],'type':chosen,'label':stand_types.label(chosen)}
    try:
        layout=counter_display.stand_layout(brief,None)
        result=counter_display.solve_template_stand(brief,chosen)
    except (ValueError,ZeroDivisionError) as exc:
        return dict(out,ok=False,words=str(exc))
    report=result['qualification']
    return dict(out,ok=True,passed=report['passed'],rows=layout['rows'],columns=layout['columns'],count=layout['count'],closed=result['dimensions_mm'],
                changes=result['dimension_adjustments'],bar_mm=report['sightlines']['face_bar_mm'])


@login_required
@require_GET
def stand_preview(request):
    """New design's live answer: the suggested type and the solved size for the sizes as typed."""
    member(request.user)
    return JsonResponse(stand_preview_for(request.GET))


def round_template(record):
    return 'dashboard/product_designer_round.html' if is_designer_brief(record.product_brief) else 'dashboard/product_round_retired.html'


def round_context(record,error=''):
    return page_context(record,error) if is_designer_brief(record.product_brief) else retired_context(record,error)


@login_required
@require_GET
def detail(request,pk):
    record=owned(request,pk)
    round_flow.recover_dispatch(record)
    record.refresh_from_db()
    return render(request,round_template(record),round_context(record))


def bad_action(request,record,exc):
    record.refresh_from_db()
    return render(request,round_template(record),round_context(record,str(exc)),status=400)


@login_required
@require_POST
def pick(request,pk):
    record=owned(request,pk)
    ident=request.POST.get('candidate','').strip()
    reason=request.POST.get('reason','').strip()
    merge_candidate=request.POST.get('merge_candidate','').strip()
    merge_element=request.POST.get('merge_element','').strip()
    merge={'candidate':merge_candidate,'element':merge_element} if merge_candidate or merge_element else None
    if merge:
        return bad_action(request,record,ValueError('Choose one original idea.'))
    try:round_flow.submit_pick(record.pk,ident,reason,request.user,merge=merge or None)
    except ValueError as exc:return bad_action(request,record,exc)
    return redirect('dashboard:product_round',pk=pk)


@login_required
@require_GET
def research(request,pk):
    record=owned(request,pk)
    if not is_designer_brief(record.product_brief):raise Http404
    return render(request,'dashboard/product_designer_research.html',research_context(record))


@login_required
@require_POST
def board(request,pk):
    record=owned(request,pk)
    try:round_flow.submit_board_pick(record.pk,request.POST.get('board','').strip(),request.POST.get('reason',''),request.user)
    except ValueError as exc:return bad_action(request,record,exc)
    return redirect('dashboard:product_round',pk=pk)


@login_required
@require_POST
def none_of_these(request,pk):
    record=owned(request,pk)
    try:round_flow.none_of_these(record.pk,request.POST.get('stage','').strip(),request.POST.get('line',''),request.user)
    except ValueError as exc:return bad_action(request,record,exc)
    return redirect('dashboard:product_round',pk=pk)


@login_required
@require_POST
def retry(request,pk):
    record=owned(request,pk)
    try:round_flow.retry_round(record.pk,request.user)
    except ValueError as exc:return bad_action(request,record,exc)
    return redirect('dashboard:product_round',pk=pk)


@login_required
@require_GET
def artifact(request,pk,relative):
    record=owned(request,pk)
    try:
        published=publication(record)
        pins=dict(board_publication(record).get('files',{}),**published.get('files',{}))
        pin=pins.get(relative)
        if not isinstance(pin,str) or len(pin)!=64:raise ValueError('File is not published')
        root=Path(round_flow.round_root(record)).resolve()
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or path==root:raise ValueError('Outside round')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=pin:raise ValueError('File pin changed')
    except (OSError,ValueError,TypeError,KeyError):raise Http404
    mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    response=HttpResponse(data,content_type=mime)
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    if mime not in ('image/png','image/jpeg','application/pdf'):
        response['Content-Disposition']='attachment; filename="'+path.name.replace('"','')+'"'
    return response
