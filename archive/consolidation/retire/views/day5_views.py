"""Authenticated, hash-checked Day5 review. No selection or approval mutation."""
import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse,Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from .fidelity_views import member
from apps.pipeline.services import day5_master as dm,fidelity_master as fm

def root():
    return Path(settings.BASE_DIR).parent/'docs/audit/day-5'

def checked_record():
    folder=root();record=json.loads((folder/'publication.json').read_text())
    spec=json.loads((folder/'master/design-spec.json').read_text());dm.validate_spec(spec)
    if fm.digest(spec)!=record['product_spec_hash']:raise ValueError('Product pin changed.')
    assembly=folder.parent/'day-4/stand-family/assembly-spec.json'
    if fm.fa.sha(assembly)!=record['assembly_sha256']:raise ValueError('Assembly changed.')
    # Scores and eligibility are bound to the actual saved picture and review.
    for row in record['candidates']:
        for key in ('image','critic'):
            path=folder/row[key]
            if fm.fa.sha(path)!=row[key+'_sha256']:raise ValueError('Concept review changed.')
        review=json.loads((folder/row['critic']).read_text())
        if review['image_sha256']!=row['image_sha256']:raise ValueError('Critic belongs to another image.')
        from apps.pipeline.services.concept_quality import evaluate
        accepted=evaluate(review['payload'])['review_status']=='accepted'
        if row['eligible']!=(accepted and not row['human_hard_failures']):raise ValueError('Candidate eligibility changed.')
    return record

def context(request,kind):
    """The checked Day 5 page, as a context; Day 6's serum page (day6_views.serum) adds its history entry to it."""
    member(request.user)
    if not getattr(settings,'HYBRID_BOTTLE_ENABLED',False):raise Http404
    try:record=checked_record()
    except (ValueError,KeyError,OSError):raise Http404
    tab=request.GET.get('tab','presentation')
    if tab not in ('presentation','artwork','construction'):raise Http404
    urls={key:reverse('dashboard:day5_file',args=[key]) for key in record['downloads']}
    choices=[];history=[]
    for row in record['candidates']:
        item=dict(row,url=urls[row['id']])
        (choices if row['eligible'] else history).append(item)
    return {'stand':kind=='stand','tab':tab,'record':record,'urls':urls,'choices':choices,'history':history}

@login_required
@require_GET
def master(request,kind='serum'):
    return render(request,'dashboard/day5_master.html',context(request,kind))

@login_required
@require_GET
def artifact(request,role):
    member(request.user)
    if not getattr(settings,'HYBRID_BOTTLE_ENABLED',False):raise Http404
    try:
        record=checked_record();item=record['downloads'][role]
        path=(root()/item['path']).resolve()
        if not path.is_relative_to(root().resolve()) or fm.fa.sha(path)!=item['sha256']:raise Http404
    except (ValueError,KeyError,OSError):raise Http404
    return FileResponse(path.open('rb'),content_type=item['mime'],as_attachment=item['mime'] not in ('image/png','application/pdf'),filename=path.name)
