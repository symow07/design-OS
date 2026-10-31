"""The owner's Round 1 mark and pick page; no approval action."""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .fidelity_views import member
from apps.pipeline.services import round_balm_page


@login_required
@require_GET
def balm(request):
    member(request.user)
    try:record=round_balm_page.load()
    except (ValueError,OSError,KeyError,TypeError):
        record={'state':'unavailable','cards':[],'history':[]}
    return render(request,'dashboard/round_balm.html',{'round':record})


@login_required
@require_GET
def artifact(request,role):
    member(request.user)
    try:data,mime=round_balm_page.checked_bytes(role)
    except (ValueError,OSError,KeyError,TypeError):raise Http404
    response=HttpResponse(data,content_type=mime)
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response
