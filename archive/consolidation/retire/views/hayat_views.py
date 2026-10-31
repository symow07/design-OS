"""The owner's HAYAT master: a read-only comparison with its picked sketch."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.pipeline.services import hayat_master_page
from .fidelity_views import member


@login_required
@require_GET
def master(request):
    member(request.user)
    try:
        record = hayat_master_page.load()
    except ValueError as exc:
        raise Http404(str(exc)) from exc
    return render(request, "dashboard/hayat_master.html", {"master": record})
