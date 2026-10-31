"""Owner-only pages for the queued picture-to-files build."""
import hashlib
import mimetypes
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.pipeline.services.round_calls import round_costs
from apps.pipeline.models import RoundMaster
from apps.pipeline.services import round_files_gate as gate
from apps.pipeline.services.round_files_gate import scoped_spend
from apps.pipeline.services.round_designer import is_designer_brief
from .product_round_views import bad_action, owned


def files_build(record):
    build = get_object_or_404(RoundMaster, round=record)
    if not is_designer_brief(record.product_brief) or build.inputs.get('schema') != gate.FILES_SCHEMA:
        raise Http404
    return build


def publication(build):
    """Only a manifest retained in the database can authorize an artifact: the gate's pins (the picture, each face's
    current crop and preview, the made files), or a retired build's saved publication."""
    if gate.is_gate(build):
        made = build.publication if build.state == 'complete' else {}
        return dict(made, files=gate.pins(build))
    if build.publication:
        return build.publication
    for name in ('eye', 'files'):
        preview = (build.steps.get(name, {}).get('result') or {}).get('preview')
        if preview:
            return preview
    return {}


def face_cards(record, build, url):
    """One card per face: the picture's crop, the built face, the eye's notes (advice), its state and its buttons."""
    sizes = gate.die_sizes(build)
    cards = []
    for key, row in gate.board(build).items():
        entry = gate.current(row) or {}
        eye = entry.get('eye') or {}
        size_changed = bool(entry.get('size_mm')) and entry['size_mm'] != sizes[key]
        cards.append({
            'key': key, 'label': row['label'], 'state': row['state'], 'state_label': gate.LABELS[row['state']],
            'n': entry.get('n'), 'source': entry.get('source', ''), 'crop_url': url(entry.get('reference')),
            'flat': entry.get('source') in ('flat', 'repainted'),
            'built_url': url(entry.get('preview')), 'eye': eye, 'suggested': row.get('suggested', ''),
            'size_changed': size_changed, 'error': gate.plain_error(row.get('error') or entry.get('preview_error', '')),
            'note': entry.get('note', ''), 'note_withheld': entry.get('note_withheld'),
            'words_lost': entry.get('words_lost'), 'system_why': (entry.get('eye') or {}).get('why', '') if entry.get('source') == 'wrap' else '',
            'can_accept': (row['state'] == 'drawn' and bool(entry.get('preview')) and not size_changed
                           and build.current_step == 'faces'),
            'can_redraw': (row['state'] in ('drawn', 'accepted', 'failed')
                           and not (build.current_step == 'files' and build.state in ('queued', 'running'))),
            'note_max': gate.faces.NOTE_MAX})
    return cards


def page_context(record, build, error=''):
    published = publication(build)
    pins = published.get('files', {})

    def url(relative):
        if not isinstance(relative, str) or relative not in pins:
            return ''
        return reverse('dashboard:product_round_files_download', args=[record.pk, relative])

    download = url(published.get('download')) if build.state == 'complete' else ''
    retired = 'faces' not in build.steps
    on_gate = gate.is_gate(build)
    cards = face_cards(record, build, url) if on_gate else []
    if gate.flow.rejected(record):                        # history: shown as it stands, no action offered
        for card in cards:
            card.update(can_accept=False, can_redraw=False)
    flat = gate.flat_page(build) if on_gate else None
    die_sheets = gate.die_page(build) if on_gate else None
    further_shade = gate.shade_page(record) if on_gate else None
    if die_sheets:
        die_sheets.update(die_url=url(die_sheets['die_png']), fold_url=url(die_sheets['fold_png']), assembly_url=url(die_sheets['assembly_png']), nest_url=url(die_sheets['nest_png']),
                          files=[dict(row, url=url(row['path'])) for row in die_sheets['files']])
    if flat:
        flat.update(view_url=url(flat.get('view')), sheet_url=url(flat.get('sheet')), folded_url=url(flat.get('folded')),
                    loaded_url=url(flat.get('loaded')), panel_folded_url=url(flat.get('panel_folded')),
                    panel_loaded_url=url(flat.get('panel_loaded')), three_quarter_url=url(flat.get('three_quarter')),
                    ground_rows=(flat.get('rules') or {}).get('ground_rows', []))
        if flat.get('pieces'):
            flat.update(pieces_layers=[dict(row, url=url(row['png'])) for row in flat['pieces']['layers']],
                        pieces_library=[dict(row, url=url(row['png'])) for row in flat['pieces']['library']],
                        pieces_seams=[dict(row, url=url(row['picture'])) for row in flat['pieces']['seams']['creases']],
                        pieces_checks=list(flat['pieces']['checks'].values()),
                        pieces_illustrator=[dict(item, shots=[dict(shot, url=url(shot['png'])) for shot in item['shots']])
                                            for item in (flat['pieces'].get('illustrator') or {}).get('files', [])])
        if flat.get('proof_sheet') and 'pdf' in flat['proof_sheet']:
            flat.update(proof_pdf_url=url(flat['proof_sheet']['pdf']), proof_png_url=url(flat['proof_sheet']['png']))
    # a build from before the gate keeps its saved comparison cards and the eye's words, read-only
    saved = [] if on_gate else [dict(card, crop_url=url(card.get('crop')), built_url=url(card.get('built')))
                                for card in published.get('cards', [])]
    return {'round': record, 'build': build, 'progress': gate.progress(build),
            'refresh': build.state in ('queued', 'running'), 'error': error, 'retired': retired, 'gate': on_gate,
            'cards': cards, 'saved_cards': saved, 'flat': flat, 'die_sheets': die_sheets, 'further_shade': further_shade, 'eye': None if on_gate else published.get('eye'),
            'all_accepted': on_gate and gate.ready(build), 'can_accept_all': sum(card['can_accept'] for card in cards),
            'can_make': on_gate and build.state == 'awaiting' and gate.ready(build) and not gate.flow.rejected(record),
            'picture_url': url(published.get('picture') or 'source.png'),
            'drawing_url': url(published.get('drawing')), 'download_url': download,
            'spend': scoped_spend(build) if on_gate else dict(published.get('spend') or {}, budget_usd=float(build.budget_usd))
                     if published.get('spend') else None,
            'reading_notes': gate.reading_notes(build),
            'report_url': url('README.md') if download else '',
            'rejected': gate.flow.rejected_words(record) if gate.flow.rejected(record) else '',
            'costs': round_costs(record, {key: face['label'] for key, face in gate.faces.FACES.items()})}


@login_required
@require_POST
def start(request, pk):
    record = owned(request, pk)
    try:
        gate.start(record.pk, request.user)
    except ValueError as exc:
        return bad_action(request, record, exc)
    return redirect('dashboard:product_round_files', pk=pk)


@login_required
@require_GET
def detail(request, pk):
    record = owned(request, pk)
    build = files_build(record)
    gate.recover(build)
    build.refresh_from_db()
    return render(request, 'dashboard/product_round_files.html', page_context(record, build))


@login_required
@require_POST
def retry(request, pk):
    record = owned(request, pk)
    build = files_build(record)
    try:
        gate.retry(record.pk, request.user)
    except ValueError as exc:
        build.refresh_from_db()
        return render(request, 'dashboard/product_round_files.html',
                      page_context(record, build, str(exc)), status=400)
    return redirect('dashboard:product_round_files', pk=pk)


def _gate_action(request, pk, act):
    record = owned(request, pk)
    build = files_build(record)
    try:
        act(record)
    except (ValueError, KeyError) as exc:
        build.refresh_from_db()
        return render(request, 'dashboard/product_round_files.html', page_context(record, build, str(exc)), status=400)
    return redirect('dashboard:product_round_files', pk=pk)


@login_required
@require_POST
def accept_face(request, pk, key):
    try:
        n = int(request.POST.get('drawing', ''))
    except ValueError:
        n = -1
    return _gate_action(request, pk, lambda record: gate.accept(record.pk, request.user, key, n))


@login_required
@require_POST
def accept_all(request, pk):
    return _gate_action(request, pk, lambda record: gate.accept_all(record.pk, request.user))


@login_required
@require_POST
def redraw_face(request, pk, key):
    return _gate_action(request, pk, lambda record: gate.redraw(record.pk, request.user, key,
                                                                request.POST.get('note', '')))


@login_required
@require_POST
def make_files(request, pk):
    return _gate_action(request, pk, lambda record: gate.make_files(record.pk, request.user))


@login_required
@require_GET
def artifact(request, pk, relative):
    record = owned(request, pk)
    build = files_build(record)
    try:
        published = publication(build)
        pin = published['files'][relative]
        if not isinstance(pin, str) or len(pin) != 64:
            raise ValueError('File is not published')
        if relative == published.get('download') and build.state != 'complete':
            raise ValueError('The download is not ready')
        root = Path(gate.root(build)).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError('File is outside this build')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pin:
            raise ValueError('File changed after publication')
    except (OSError, ValueError, TypeError, KeyError):
        raise Http404
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    response = HttpResponse(data, content_type=mime)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    if mime not in ('image/png', 'image/jpeg', 'application/pdf'):
        response['Content-Disposition'] = 'attachment; filename="' + path.name.replace('"', '') + '"'
    return response
