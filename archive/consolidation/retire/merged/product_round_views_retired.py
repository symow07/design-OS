"""The round pages' parts for the retired round kinds, archived by the owner's goal of 2026-10-29. Each block is
copied whole from bbrose_design_os/apps/dashboard/product_round_views.py as it stood at 49ac763. Kept as text."""

# the whole-object kind's marks action (route rounds/<pk>/marks/)
@login_required
@require_POST
def marks(request,pk):
    record=owned(request,pk)
    if is_ideas_brief(record.product_brief):
        return bad_action(request,record,ValueError('Choose one of the finished ideas and give your reason.'))
    rows=[]
    for slot in range(3):
        ident=request.POST.get('candidate_'+str(slot),'').strip()
        preserve=request.POST.get('preserve_'+str(slot),'').strip()
        if ident or preserve:rows.append({'id':ident,'preserve':preserve})
    try:round_flow.submit_marks(record.pk,rows,request.user)
    except ValueError as exc:return bad_action(request,record,exc)
    return redirect('dashboard:product_round',pk=pk)


# page_context before the cut (it served all three kinds)
def page_context(record,error=''):
    summary=round_flow.summary(record)
    ideas=is_ideas_brief(record.product_brief)
    record.display_state=STATE_LABELS.get(record.state,record.state)
    try:published=publication(record)
    except (OSError,ValueError,TypeError):
        published={};error=error or 'The published artwork changed or is unavailable. Its file pins must match before it can be shown.'
    cards=[]
    candidates=published.get('candidates',{})
    if isinstance(candidates,list): candidates={row['id']:row for row in candidates}
    for ident in published.get('order',[]):
        item=dict(candidates.get(ident,{}) or {},id=ident)
        reading=item.get('reading') or {}
        item['words']=item.get('idea','') if ideas else (reading.get('idea_in_ten_words','') if isinstance(reading,dict) else reading)
        for role in ('picture','drawing','folded','loaded'):
            if item.get(role):item[role+'_url']=reverse('dashboard:product_round_file',args=[record.pk,item[role]])
        cards.append(item)
    merge_candidates=[] if ideas else sorted(set((record.artifacts.get('sketches') or {}).get('candidates',{})) | set((record.artifacts.get('forks') or {}).get('candidates',{})))
    build = getattr(record, 'master_build', None) if ideas and record.state == 'complete' else None
    files_build = build if build is not None and build.inputs.get('schema') == 'picked_picture_files/1' else None
    designer=designer_context(record,cards) if is_designer_brief(record.product_brief) else {}
    return {**designer,'round':record,'summary':summary,'cards':cards,'error':error,'merge_candidates':merge_candidates,
            'files_build':files_build,'can_build_files':ideas and record.state == 'complete' and build is None and not round_files_gate.flat_pick(record),
            'flat_pick_waits':round_files_gate.FLAT_PICK_WAITS if ideas and record.state == 'complete' and build is None and round_files_gate.flat_pick(record) else '',
            'final_pool':published.get('pool_summary'),
            'is_marks':not ideas and record.state=='awaiting_marks','is_pick':record.state=='awaiting_pick',
            'refresh':record.state in ('queued','running'), 'mark_slots':range(3),
            'brief_pretty':json.dumps(record.product_brief,ensure_ascii=False,indent=2)}


# the Round 1B/1C master pages (routes rounds/<pk>/master/build/, master/, master/retry/, master/files/…), retired with them
def master_context(record, build, error=''):
    from apps.pipeline.services import round_master_flow
    context = {'round': record, 'build': build, 'progress': round_master_flow.progress(build),
               'error': error, 'refresh': build.state in ('queued', 'running')}
    publication = build.publication or build.steps['eye']['result'].get('preview') or build.steps['files']['result'].get('preview') or {}
    cards = []
    def url(relative):
        return reverse('dashboard:product_round_master_file', args=[record.pk, relative])
    if publication:
        for panel in publication['panels']:
            card = dict(panel, sketch_url=url(panel['sketch']), master_url=url(panel['master']))
            card['proofs'] = [dict(proof, url=url(proof['file'])) for proof in panel['clear_proofs']]
            cards.append(card)
        context.update(cards=cards, eye=publication['eye'], spend=publication['spend'],
            download_url=url(publication['download']) if 'download' in publication else '', png_url=url('flat-pngs.zip'),
            pdf_url=url('actual-size.pdf'), report_url=url('README.md'),
            carton_url=url('files/carton.png') if 'files/carton.png' in publication['files'] else '',
            leaflet_url=url('files/leaflet.png'))
    return context


@login_required
@require_POST
def master_start(request, pk):
    from apps.pipeline.services import round_master_flow
    record = owned(request, pk)
    if is_ideas_brief(record.product_brief):
        return bad_action(request, record, ValueError('This round ends with your idea choice.'))
    try:
        round_master_flow.start(record.pk, request.user)
    except ValueError as exc:
        return bad_action(request, record, exc)
    return redirect('dashboard:product_round_master', pk=pk)


@login_required
@require_GET
def master(request, pk):
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_master_flow
    record = owned(request, pk)
    build = get_object_or_404(RoundMaster, round=record)
    if is_ideas_brief(record.product_brief) or build.inputs.get('schema') == 'picked_picture_files/1':
        raise Http404
    round_master_flow.recover(build)
    build.refresh_from_db()
    return render(request, 'dashboard/product_round_master.html', master_context(record, build))


@login_required
@require_POST
def master_retry(request, pk):
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_master_flow
    record = owned(request, pk)
    build = get_object_or_404(RoundMaster, round=record)
    if is_ideas_brief(record.product_brief) or build.inputs.get('schema') == 'picked_picture_files/1':
        raise Http404
    try:
        round_master_flow.retry(record.pk, request.user)
    except ValueError as exc:
        build = get_object_or_404(RoundMaster, round=record)
        return render(request, 'dashboard/product_round_master.html', master_context(record, build, str(exc)), status=400)
    return redirect('dashboard:product_round_master', pk=pk)


@login_required
@require_GET
def master_artifact(request, pk, relative):
    from apps.pipeline.models import RoundMaster
    from apps.pipeline.services import round_master_flow
    record = owned(request, pk)
    build = get_object_or_404(RoundMaster, round=record)
    if is_ideas_brief(record.product_brief) or build.inputs.get('schema') == 'picked_picture_files/1':
        raise Http404
    try:
        publication=build.publication or build.steps['eye']['result'].get('preview') or build.steps['files']['result'].get('preview') or {}
        pin = publication['files'][relative]
        root = round_master_flow.root(build).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or path == root:
            raise ValueError('Outside master')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pin:
            raise ValueError('Published file changed')
    except (OSError, ValueError, TypeError, KeyError):
        raise Http404
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    response = HttpResponse(data, content_type=mime)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    if path.suffix not in ('.png', '.pdf'):
        response['Content-Disposition'] = 'attachment; filename="' + path.name.replace('"', '') + '"'
    return response
