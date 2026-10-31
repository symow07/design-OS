"""Day 13 §2e — the creativity check's page (``/dashboard/creativity/``): the sheet and its nine files under their K
names only, the owner's ranking written once, and the map opened on the page only after it.

The state is ``apps.pipeline.services.day13_creativity_page``'s; these views show it and pass his words in. While the map
is sealed the template is handed the K names and the door's addresses and nothing else of the map. The files door
re-hashes each file against the map's pin on every request and serves it under its label's name (a changed or unknown
file is a 404, never a 500). Writing the ranking is the owner's act alone and takes two steps, as the copy channel's:
the first POST shows him exactly the words and their sha256 and writes nothing; the second, his click on that page, writes
them once."""
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import explorations
from .fidelity_views import member
from apps.pipeline.services import day13_creativity_page as creativity

TEMPLATE = 'dashboard/day13_creativity.html'
NOT_THE_OWNER = "Only the owner's account writes the ranking on this page."


def _context(request, **extra):
    said = creativity.state()
    context = {'state': said['state'], 'ready': said['state'] == creativity.READY, 'why': None,
               'is_owner': explorations.owner_refusal(request.user) is None,
               'max_characters': creativity.MAX_CHARACTERS}
    if said['state'] in (creativity.CHANGED, creativity.UNREADABLE):
        context['why'] = said['why']
    if context['ready']:
        context.update(seal=said['seal'], sheet_url=reverse('dashboard:creativity_file', args=[creativity.SHEET]),
                       tiles=[{'label': label, 'url': reverse('dashboard:creativity_file', args=[label])}
                              for label in said['labels']])
        if said['seal'] == creativity.HELD:
            context['why'] = said['why']
        if said['seal'] == creativity.OPEN:                 # only now does anything of the map reach the template
            context.update(ranking=said['ranking'], map=said['map'])
    context.update(extra)
    return context


@login_required
@require_GET
def creativity_check(request):
    member(request.user)
    return render(request, TEMPLATE, _context(request))


@login_required
@require_GET
def creativity_file(request, label):
    """One of the nine files or the sheet, served under its label's name only while its bytes are the map's pin."""
    member(request.user)
    try:
        path, name = creativity.checked_file(label)
    except (ValueError, KeyError, TypeError, AttributeError, OSError, creativity.Changed):   # never a 500
        raise Http404
    return FileResponse(path.open('rb'), content_type=creativity.MIME, filename=name)


@login_required
@require_POST
def creativity_ranking(request):
    """The owner's ranking: the first POST shows the words and their sha256 and writes nothing; the second (``confirm``,
    with the sha256 the page showed) writes them once. A second ranking is refused politely and the first stays."""
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(NOT_THE_OWNER, content_type='text/plain; charset=utf-8')
    text = request.POST.get('ranking')
    try:
        if not request.POST.get('confirm'):
            words, sha256 = creativity.prepared(text)
            return render(request, TEMPLATE, _context(request, confirm={'words': words, 'sha256': sha256}, typed=words))
        creativity.write(request.user.get_username(), text, request.POST.get('sha256'))
    except (creativity.NotReady, creativity.AlreadyWritten) as refused:
        return render(request, TEMPLATE, _context(request, refused=str(refused)), status=409)
    except creativity.Refused as refused:
        return render(request, TEMPLATE, _context(request, refused=str(refused), typed=text), status=400)
    return redirect(reverse('dashboard:creativity_check') + '#map')
