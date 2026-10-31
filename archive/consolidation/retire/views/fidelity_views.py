"""Checked revision-2 review pages; no mutation or approval endpoint."""
import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse,Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from apps.pipeline.permissions import ALL_ROLES,user_has_role
from apps.pipeline.services import fidelity_master as fm
from apps.ire.identity_sightlines import validate_model

FILES={
 'concept':('master/concept-reference.png','image/png'),
 'projection':('master/projected-master.png','image/png'),
 'flat':('master/artwork.png','image/png'),
 'comparison':('master/comparison-at-100-percent-page-1.png','image/png'),
 'proof':('master/comparison-at-100-percent.pdf','application/pdf'),
 'presentation':('stand-family/presentation-page-1.png','image/png'),
 'stand-proof':('stand-family/presentation.pdf','application/pdf'),
 'construction':('stand-family/construction.pdf','application/pdf'),
 '144':('stand-144/construction.pdf','application/pdf'),
 '146':('stand-146/construction.pdf','application/pdf'),
 'stagger':('stand-family-stagger/construction.pdf','application/pdf'),
 'preflight':('master/preflight.json','application/json'),
 'package':('day4-review-package.zip','application/zip'),
}

def root():return Path(settings.BASE_DIR).parent/'docs/audit/day-4'

def checked_record():
    folder=root();record=json.loads((folder/'publication.json').read_text());spec=json.loads((folder/'master/design-spec.json').read_text())
    fm.validate_spec(spec,record['product_spec_hash'])
    model=json.loads((folder/'stand-family/assembly-spec.json').read_text());validate_model(model)
    if model['product_spec_hash']!=record['product_spec_hash'] or fm.digest(model)!=record['assembly_spec_hash']:raise ValueError('Assembly pin changed.')
    return record

def member(user):
    if not user_has_role(user,*ALL_ROLES):raise PermissionDenied

@login_required
@require_GET
def master(request,kind='serum'):
    member(request.user)
    if not getattr(settings,'HYBRID_BOTTLE_ENABLED',False):raise Http404
    try:record=checked_record()
    except (ValueError,KeyError,OSError):raise Http404
    urls={key:reverse('dashboard:fidelity_file',args=[key]) for key in FILES}
    tab=request.GET.get('tab','presentation')
    if tab not in ('presentation','artwork','construction'):raise Http404
    return render(request,'dashboard/fidelity_master.html',{'kind':kind,'stand':kind=='stand','tab':tab,'urls':urls,'record':record})

@login_required
@require_GET
def artifact(request,role):
    member(request.user)
    if role not in FILES:raise Http404
    relative,mime=FILES[role];path=root()/relative
    try:
        record=checked_record()
        if fm.fa.sha(path)!=record['files'].get(relative):raise Http404
    except (ValueError,KeyError,OSError):raise Http404
    return FileResponse(path.open('rb'),content_type=mime,as_attachment=mime not in ('image/png','application/pdf'),filename=path.name)
