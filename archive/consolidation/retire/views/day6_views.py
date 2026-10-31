"""Authenticated, hash-checked Day 6 review: D1 mapped onto the real stand. No selection or approval mutation."""
import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from .fidelity_views import member
from . import day5_views
from apps.pipeline.services import day5_master as dm, fidelity_master as fm

TABS = ('presentation', 'surfaces', 'render', 'cut', 'device', 'library', 'history')
INLINE = ('image/png', 'application/pdf', 'image/svg+xml')


def root():
    return Path(settings.BASE_DIR).parent / 'docs/audit/day-6'


def checked_record():
    folder = root(); record = json.loads((folder / 'publication.json').read_text())
    spec = json.loads((folder.parent / 'day-5/master/design-spec.json').read_text()); dm.validate_spec(spec)
    if fm.digest(spec) != record['product_spec_hash']: raise ValueError('Product pin changed.')
    if fm.fa.sha(folder / record['assembly_source']) != record['assembly_sha256']: raise ValueError('Assembly changed.')
    bindings = record['downloads']['surface-bindings']
    if fm.fa.sha(folder / bindings['path']) != bindings['sha256']: raise ValueError('Surface bindings changed.')
    pick = record['downloads']['owner-pick']
    if fm.fa.sha(folder / pick['path']) != record['owner_pick']['image_sha256']: raise ValueError('The owner’s pick changed.')
    return record


def links_of(record):
    return {role.replace('-', '_'): reverse('dashboard:day6_file', args=[role]) for role in record['downloads']}


def context(request, tab):
    member(request.user)
    if not getattr(settings, 'HYBRID_BOTTLE_ENABLED', False): raise Http404
    try: record = checked_record()
    except (ValueError, KeyError, OSError): raise Http404
    if tab not in TABS: raise Http404
    links = links_of(record)
    sections = {}
    for role, item in record['downloads'].items():
        sections.setdefault(item['section'], []).append({'role': role, 'words': item['words'], 'url': links[role.replace('-', '_')]})
    pending = {}
    for item in record['pending']:
        pending.setdefault(item['section'], []).append(item)
    surfaces = []
    for s in record['surfaces']:
        files = [{'kind': kind, 'url': links[role.replace('-', '_')]} for kind, role in s['roles'].items() if role in record['downloads']]
        fidelity = s['fidelity'] if isinstance(s['fidelity'], dict) else {'summary': s['fidelity']}
        surfaces.append(dict(s, files=files, fidelity_rows=[(k, v) for k, v in fidelity.items() if not isinstance(v, (dict, list))]))
    totals = record['library_totals']
    inventory = totals['inventory'] if isinstance(totals, dict) and isinstance(totals.get('inventory'), dict) else {}
    return {'tab': tab, 'tabs': TABS, 'record': record, 'links': links, 'sections': sections, 'pending': pending, 'surfaces': surfaces,
            'library_rows': [(k, v) for k, v in inventory.items() if not isinstance(v, (dict, list))],
            'library_kinds': sorted((inventory.get('by_kind') or {}).items()) if isinstance(inventory.get('by_kind'), dict) else [],
            'revision4': record['bottle_revision_4']}


@login_required
@require_GET
def master(request, kind='stand'):
    return render(request, 'dashboard/day6_master.html', context(request, request.GET.get('tab', 'presentation')))


@login_required
@require_GET
def serum(request):
    """Day 5's revision-3 serum page, with the Day 6 revision-4 sheet in its review history (never pinned)."""
    data = day5_views.context(request, 'serum')
    try:
        record = checked_record(); links = links_of(record); r4 = record['bottle_revision_4']
        data['revision4'] = ({'pending': True} if not r4 or 'revision_4_sheet' not in links else
                             {'url': links['revision_4_sheet'], 'fidelity': r4['fidelity'], 'traced_text': r4['traced_text'], 'critic': r4['critic'], 'pending': False})
    except (ValueError, KeyError, OSError):
        data['revision4'] = {'pending': True}
    return render(request, 'dashboard/day5_master.html', data)


@login_required
@require_GET
def artifact(request, role):
    member(request.user)
    if not getattr(settings, 'HYBRID_BOTTLE_ENABLED', False): raise Http404
    try:
        record = checked_record(); item = record['downloads'][role]
        path = (root() / item['path']).resolve()
        if not path.is_relative_to(root().parent.resolve()) or fm.fa.sha(path) != item['sha256']: raise Http404
    except (ValueError, KeyError, OSError): raise Http404
    return FileResponse(path.open('rb'), content_type=item['mime'], as_attachment=item['mime'] not in INLINE, filename=path.name)
