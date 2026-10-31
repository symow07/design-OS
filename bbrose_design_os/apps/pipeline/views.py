from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from django.core.files.storage import default_storage
from django.core.exceptions import SuspiciousOperation
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import clean_sku
from .models import (AgentLog, CreativeBrief, DesignTask, GateDecision,
                     GeneratedImage, PackagingOutput)
from .permissions import (IsDesigner, IsReviewer, IsTeamMember,
                          IsWebReferenceReviewer)
from apps.core.models import Brand, Product, Campaign


def _resolve_brand(request):
    """Resolve the brand for task creation (Milestone 11.2 / audit H3).

    Explicit ``brand_id`` wins. Without one: the sole brand when exactly one
    exists, otherwise a 400 — never a nondeterministic ``.first()``.
    Returns (brand, error_response).
    """
    brand_id = request.data.get('brand_id')
    if brand_id:
        try:
            return Brand.objects.get(id=int(brand_id)), None
        except (Brand.DoesNotExist, TypeError, ValueError):
            return None, Response({'error': 'Unknown brand_id'},
                                  status=status.HTTP_400_BAD_REQUEST)

    brands = list(Brand.objects.order_by('id')[:2])
    if not brands:
        return None, Response(
            {'error': 'No brand configured. Run seed_bbrose first.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(brands) > 1:
        return None, Response(
            {'error': 'Multiple brands exist — brand_id is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return brands[0], None


class TaskCreateView(APIView):
    """POST /api/tasks/create/ — Designers (and Admins) create tasks."""
    permission_classes = [IsAuthenticated, IsDesigner]

    def post(self, request):
        task_text = request.data.get('task_text', '').strip()
        if not task_text:
            return Response({'error': 'task_text is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Milestone 8.7: don't enqueue into a black hole — when not in eager
        # mode, require at least one live Celery worker before accepting work.
        from apps.core.health import worker_available
        if not worker_available():
            return Response(
                {'error': 'pipeline worker offline'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Milestone 12.2: block new work once the rolling 24h AI spend hits the
        # daily cap (429). Existing tasks keep running to completion.
        from apps.pipeline.services.cost_ledger import daily_budget_exceeded
        if daily_budget_exceeded():
            return Response(
                # §BH55 Phase 3: the refusal's own clock in words — it said "try again tomorrow" of a rolling window
                {'error': 'Spending paused: the $25 Shanghai calendar-day or $250 rescue budget is fully reserved. Saved work is retained.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        brand, error = _resolve_brand(request)
        if error:
            return error

        # Product/campaign must belong to the selected brand (Milestone 11.2):
        # a cross-brand pair is a client error, not a silent mismatch.
        product = None
        product_id = request.data.get('product_id')
        if product_id:
            try:
                product = Product.objects.filter(id=int(product_id), brand=brand).first()
            except (TypeError, ValueError):
                product = None
            if product is None:
                return Response(
                    {'error': 'product_id does not belong to the selected brand'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        campaign = None
        campaign_id = request.data.get('campaign_id')
        if campaign_id:
            try:
                campaign = Campaign.objects.filter(id=int(campaign_id), brand=brand).first()
            except (TypeError, ValueError):
                campaign = None
            if campaign is None:
                return Response(
                    {'error': 'campaign_id does not belong to the selected brand'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Design Target (Phase B4): which target the shared pipeline produces.
        # Omitted/blank → packaging (the default), so existing clients are
        # unchanged. Only active targets may be selected.
        from apps.pipeline.targets import DesignTarget, get_target
        from apps.pipeline.targets.composite import (
            create_composite_project,
            is_composite,
        )
        design_target = request.data.get('design_target')
        if not design_target:
            return Response({'error': 'Choose Product, Display or Carton before starting.'}, status=400)
        if design_target not in DesignTarget.values:
            return Response({'error': 'unknown design_target'},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.pipeline.services.intake_constraints import read_intake, target_conflict
        try:
            intake = read_intake(request.data.get('intake'))
        except (ValueError, TypeError) as exc:
            return Response({'error': str(exc)}, status=400)
        original_brief = task_text
        if intake['fields']:
            task_text += '\n\nConfirmed intake (blank fields unresolved):\n' + '\n'.join(
                f"{key}: {value}" for key, value in intake['fields'].items() if value.strip())
        conflict = target_conflict(design_target, task_text)
        if conflict:
            return Response(conflict, status=409)
        # §BH70(2): a palette is started, never refused at the door — as a Product Container of the Compact / Palette
        # form, its concept made first (targets/palette.py, STARTS_AS). It was refused here with what the dedicated
        # palette engine needs, before any paid work (§BH55 Phase 2)
        if design_target == DesignTarget.PALETTE.value:
            from apps.pipeline.targets import palette as _palette
            design_target = _palette.STARTS_AS
            task_text = task_text + _palette.STARTS_WITH_FORM_HINT
        # [the owner's answer of 2026-09-27 to the §BH70 report's fourth question: "when a brief says "gloss" without
        # saying which, ask me: wand vial or squeeze tube." Asked here, before anything is created or spent, for the
        # two targets that design the product itself; his choice comes back on the brief as its container hint]
        # [his goal of 2026-10-06, item 1: "the Container type I choose ALWAYS wins. Then my brief's own words. Never a
        # guess from picture readings or word order."] the same door asks when his brief's own words name two forms and
        # he chose none — and, the executor's extension his to veto, when the Container type he chose is not the form
        # his brief's words name (design 120: Jar chosen, "squeeze tube" written), his choice first; a carton's brief
        # is asked only the first, its form being the product's inside it
        if design_target in (DesignTarget.PRODUCT_CONTAINER.value, DesignTarget.COMPLETE_PRODUCT.value,
                             DesignTarget.PACKAGING.value):
            from apps.pipeline.targets.container import FORM_QUESTION, form_question
            asked = form_question("%s %s" % (getattr(product, "product_type", "") or "", task_text),
                                  confirmed=str(request.data.get('form_confirmed') or '').lower() in ('true', '1'))
            if asked and (design_target != DesignTarget.PACKAGING.value or asked["error"] == FORM_QUESTION):
                return Response(asked, status=status.HTTP_409_CONFLICT)

        # §BH69(2): the owner's inspiration pictures, refused by name BEFORE anything is created — a picture the reader
        # can open, at most six; a Complete Product carries them on its first stage
        from apps.pipeline import references as refs
        from apps.pipeline.services import inspiration
        pictures = request.FILES.getlist(inspiration.KIND)
        if pictures:
            checked = refs.validate_all([(inspiration.KIND, pictures)], {inspiration.KIND})
            refused = ("" if checked.ok else "; ".join(r.message for r in checked.rejections)) or \
                inspiration.refusal_for(checked.accepted)
            if refused:
                return Response({'error': 'INSPIRATION_PICTURES_REFUSED', 'words': refused},
                                status=status.HTTP_400_BAD_REQUEST)
        # [his final goal, 2026-10-05, B1 and B3] his inside and sticker references, refused by name the same way before
        # anything exists
        from apps.pipeline.services import inside_read
        kept_pictures = {}
        for kind_, code in ((inside_read.KIND, 'INSIDE_PICTURES_REFUSED'),
                            (inside_read.STICKER_KIND, 'STICKER_PICTURES_REFUSED')):
            sent = request.FILES.getlist(kind_)
            if not sent:
                continue
            checked_ = refs.validate_all([(kind_, sent)], {kind_})
            refused = ("" if checked_.ok else "; ".join(r.message for r in checked_.rejections)) or \
                _picture_refusal(checked_.accepted, kind_)
            if refused:
                return Response({'error': code, 'words': refused}, status=status.HTTP_400_BAD_REQUEST)
            kept_pictures[kind_] = checked_

        # [His goal after the pitch page, 2026-10-15, B (9): "Run each from brief to final files with no manual fixes:
        # pick the trend-led concept automatically."] the pitch run, asked by its one tick beside Start — every step
        # that waits on a person taken by the system itself, stopping at Gate 2 (apps/pipeline/autopilot.py)
        from apps.pipeline import autopilot
        pitch_run = autopilot.asked(request.data.get('autopilot'))

        # Composite target (Phase C): create a DesignProject + its first-stage
        # child (Complete Product → Product Container). No orchestration yet
        # (C1). Single-target creation below is unchanged.
        if is_composite(design_target):
            # 2C-1 §12: composite readiness preflight guards creation — no
            # provider call is made; precise blockers refuse with 409.
            from apps.pipeline.targets.composite import (
                complete_product_preflight)
            preflight = complete_product_preflight()
            if preflight['result'] != 'READY_FOR_LIVE_PILOT':
                return Response({'error': 'COMPOSITE_DEPENDENCY_NOT_READY',
                                 'preflight': preflight},
                                status=status.HTTP_409_CONFLICT)
            project, task = create_composite_project(
                brand=brand, product=product, brief=task_text,
                created_by=request.user, target=design_target)
            # [His goal after the pitch page, 2026-10-15, B (9)] the pitch run asked at Start: kept on the first stage
            # before its run is enqueued, and on the project so its next stage is one too (composite._spawn_stage)
            task.options = dict(task.options or {}, intake=intake, original_brief=original_brief)
            task.save(update_fields=['options'])
            if pitch_run:
                task.options = dict(task.options or {}, **{autopilot.OPTION: autopilot.new_record()})
                task.save(update_fields=['options'])
            # §3: persist the creation contract on the project record
            import hashlib as _hl
            meta = dict(project.metadata or {})
            meta['creation'] = {
                'recipe': design_target,
                'recipe_version': '1.0',
                'stage_order': [lab for lab, _ in
                                __import__('apps.pipeline.targets.composite',
                                           fromlist=['recipe']
                                           ).recipe(design_target)],
                'product_id': getattr(product, 'id', None),
                'brand_id': brand.id,
                'created_by': request.user.username,
                'configuration_hash': _hl.sha256(
                    f'{design_target}|{brand.id}|'
                    f'{getattr(product, "id", "")}|{task_text}'.encode()
                ).hexdigest(),
                'preflight': preflight}
            if pitch_run:
                meta[autopilot.OPTION] = True
            # [his answers after 122 was redrawn, (1)] his optional SKU, kept on the project so each piece reads it
            sku = clean_sku(request.data.get('sku'))
            if sku:
                meta['sku'] = sku
                task.sku = sku
                task.save(update_fields=['sku'])
            project.metadata = meta
            project.save(update_fields=['metadata'])
            if pictures:                              # §BH69(2): kept with its first stage, read before it plans
                _store_inspiration(task, checked.accepted)
            for kind_, checked_ in kept_pictures.items():   # [his final goal, B1, B3] kept until the carton's stage
                _store_inspiration(task, checked_.accepted, kind=kind_)
            from .tasks import run_aria_pipeline
            run_aria_pipeline.delay(task.id)
            return Response(
                {'task_id': task.id, 'project_id': project.id,
                 'status': task.status},
                status=status.HTTP_201_CREATED)

        if get_target(design_target).name != design_target:
            return Response(
                {'error': f'design_target "{design_target}" is not active yet'},
                status=status.HTTP_400_BAD_REQUEST)
        # §BH55 Phase 2: a target that cannot yet design is NAMED with what it needs and refused here — before any
        # paid work — never accepted and failed after Gate 1
        needs = getattr(get_target(design_target), 'needs', '')
        if needs:
            return Response(
                {'error': f'{DesignTarget(design_target).label} cannot be designed yet — it needs {needs}.',
                 'code': 'TARGET_NEEDS', 'needs': needs},
                status=status.HTTP_400_BAD_REQUEST)

        # Reference uploads (B4b-1). EVERY file is validated BEFORE anything
        # is written, because accepting the good ones and dropping a sibling
        # would leave the user with a task they believe has five references
        # and which actually has four. The task and its references are one
        # creation operation.
        from django.db import transaction

        from apps.pipeline.models import TaskReference
        valid_kinds = {k for k, _ in TaskReference.REF_KINDS}
        pairs = [(k, request.FILES.getlist(k)) for k in sorted(valid_kinds)]
        outcome = refs.validate_all(pairs, valid_kinds)
        if not outcome.ok:
            # nothing created, nothing stored, nothing enqueued — and the
            # user's typing comes back with the refusal
            return Response(
                refs.error_payload(outcome, {
                    'task_text': task_text,
                    'design_target': design_target,
                    'product_id': request.data.get('product_id') or None,
                }),
                status=status.HTTP_400_BAD_REQUEST)

        # Storage writes survive a database rollback, so the paths written by
        # this operation are tracked and removed by hand if it fails.
        written = []
        try:
            with transaction.atomic():
                task = DesignTask.objects.create(
                    brand=brand,
                    product=product,
                    campaign=campaign,
                    task_text=task_text,
                    design_target=design_target,
                    status='queued',
                    created_by=request.user,
                    sku=clean_sku(request.data.get('sku')),     # [his answers after 122 was redrawn, (1)] optional
                    # [His goal after the pitch page, 2026-10-15, B (9)] the pitch run, with its Start time
                    options=dict({autopilot.OPTION: autopilot.new_record()} if pitch_run else {}, intake=intake, original_brief=original_brief),
                )
                for a in outcome.accepted:
                    ref = TaskReference(
                        task=task, kind=a.category,
                        original_filename=a.original_filename,
                        media_type=a.media_type, file_size=a.file_size,
                        ordering=a.ordering, source='USER_UPLOAD',
                        status='REFERENCE_ONLY',
                        sha256=_fingerprint(a.upload) if a.category in (inspiration.KIND,) + inside_read.KINDS else '')
                    # storage identity is generated, never the supplied name,
                    # so a traversal attempt cannot influence the location
                    ref.image.save(refs.stored_name(a.extension), a.upload,
                                   save=False)
                    written.append(ref.image.name)
                    ref.save()
                # §BH69(2): the reads made on the start page for these pictures become this design's own spend
                inspiration.attach(task, task.references.filter(kind=inspiration.KIND))
                # enqueue only after the transaction actually commits
                transaction.on_commit(
                    lambda tid=task.id: _enqueue_pipeline(tid))
        except Exception:
            for name in written:
                try:
                    default_storage.delete(name)
                except Exception:
                    pass
            return Response(
                {'error': refs.STORAGE_FAILED,
                 'message': 'The task could not be created. No files were '
                            'kept.',
                 'task_created': False, 'references_created': 0},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'task_id': task.id, 'status': task.status}, status=status.HTTP_201_CREATED)


def _failure_words(failure: dict) -> str | None:
    """[His goal of 2026-10-13, (1).] A production validation's failure in words: its check's own words where they are
    written, else the validator's own detail of it (its words, never its code)."""
    from apps.dashboard.words import check_words
    words = check_words(failure.get('code'))
    detail = str(failure.get('detail') or failure.get('message') or '').strip()
    if words:
        return words + ((' — ' + detail) if detail else '')
    return detail or None


def _gate2_problems_payload(task, quality):
    """[His goal of 2026-10-13, (1).] What stands beside Approve at Gate 2, in words — ``[{"code", "words"}]`` — and
    whether Approve itself is refused (his acceptance not given, or no drawing): ``{"kept", "refused"}``; None away from
    Gate 2."""
    if task.status != 'awaiting_gate_2':
        return None
    output = task.current_output()
    if output is None:
        return None
    from apps.dashboard.owner_channel import preview_sha256 as _preview_sha256
    from apps.pipeline.gate2_problems import gate2_problems
    spec = output.spec_sheet or {}
    container = (task.design_target == 'product_container' or spec.get('backend') == 'container'
                 or spec.get('container_reconstruction'))
    try:
        got = gate2_problems(task, output, preview_sha256=_preview_sha256(output)[0] if container else None,
                             quality=quality)
    except Exception:  # noqa: BLE001 — the page reads it; the approval reads it again and decides
        return None
    refusal = got['refusal'] or {}
    return {'kept': got['kept'], 'refused': [str(c) for c in refusal.get('failures') or []]
            or ([refusal['error']] if refusal.get('error') else [])}


def _acceptance_warnings(task, quality):
    """§BH71 (0a): every check not measured yet on this design, in words, one line per kind — the visual-quality
    check's unmeasured axes and the production readiness's warnings for a container, the unmeasured copy for a
    carton or an artwork piece. [] when there is none."""
    from apps.dashboard.words import acceptance_warning_rows, vq_axis_warning_words
    rows = [{'code': w.get('code') or '', 'words': vq_axis_warning_words(w.get('axis'))}
            for w in ((quality or {}).get('acceptance_warnings') or [])]
    output = task.current_output()          # the output the page shows
    spec = (output.spec_sheet if output else None) or {}
    codes = []
    if spec.get('container_reconstruction'):
        from apps.ire.container_production_readiness import build_readiness
        codes = build_readiness(spec).get('acceptance_warnings') or []
    else:
        from apps.ire.compose import FRONT_COPY_UNMEASURED, FRONT_TYPE_KEY
        from apps.ire.compose_artwork import COPY_UNMEASURED
        codes = [c for c in ((spec.get(FRONT_TYPE_KEY) or {}).get('codes') or [])
                 + ((spec.get('artwork_record/1.0') or {}).get('codes') or [])
                 if str(c).startswith((FRONT_COPY_UNMEASURED, COPY_UNMEASURED))]
        # [his review of 119, 2026-10-05, point 6: "The rest is translation: show it as 'Not confirmed yet' beside
        # Approve until I confirm it."]
        from apps.pipeline.targets.packaging import translation_codes
        codes += translation_codes(spec)
    # [his answer of 2026-09-29 to the §BH71 report, (4)] each row says its kind, so the page can say words nobody has
    # confirmed apart from checks with no measurement
    from apps.ire.container_production_readiness import UNCONFIRMED_WARNINGS
    # [his last goal before the pitch, 2026-10-16, Step 1 (2): "One verdict: the designer's eye result replaces "Not
    # measured yet" when it has run; never both, never contradicting."] where the eye looked at the drawing beside its
    # concept, its verdict stands for the checks with no measurement: each is kept, said as the eye's ("eye")
    from apps.pipeline.services.designers_eye import SCHEMA as EYE_SCHEMA
    looked = ((spec.get(EYE_SCHEMA) or {}).get('state') in ('PASS', 'DIFFERS'))
    unmeasured = "eye" if looked else "unmeasured"
    out = [dict(r, kind="unconfirmed" if r["code"] in UNCONFIRMED_WARNINGS else unmeasured)
           for r in rows + acceptance_warning_rows(codes)]
    # [his review of 119, 2026-10-05, point 6] the translations' row carries their words and the way to confirm them
    from apps.pipeline.targets.packaging import LANGUAGE_NAMES, TRANSLATION_UNCONFIRMED, label_translations
    for r in out:
        if r["code"] == TRANSLATION_UNCONFIRMED:
            r["confirm"] = "translations"
            r["detail"] = [{"language": LANGUAGE_NAMES.get(lang, lang), "field": field.replace("_", " "), "words": w}
                           for lang, fields in label_translations(spec).items() for field, w in fields.items()]
    return out


def _design_acceptance(task, user):
    from apps.dashboard.owner_channel import design_acceptance_payload
    return design_acceptance_payload(task, user)


def _confirmation_provenance(output, user):
    """[B1, the clean-up of 2026-10-04] Who confirmed the shape on the output's record, said to this viewer — the
    owner known as the design's acceptance knows him (``explorations.owner_refusal``, OWNER_ACCOUNT); None where no
    confirmation is on it (``shape_reconfirmation.confirmation_provenance``)."""
    confirmation = ((output.spec_sheet or {}) if output is not None else {}).get('container_confirmation')
    if not confirmation:
        return None
    from apps.dashboard import explorations
    from apps.pipeline.services.shape_reconfirmation import confirmation_provenance
    name = user.get_username() if getattr(user, 'is_authenticated', False) else ''
    return confirmation_provenance(confirmation, viewer=name,
                                   viewer_is_owner=bool(name) and explorations.owner_refusal(user) is None)



def _picture_refusal(accepted, kind) -> str:
    """Why uploads cannot be pictures of ``kind`` — his inspiration pictures (§BH69(2)), or [his final goal, B1] his
    inside references: a picture the reader can open, at most six a design; "" when they can."""
    from apps.pipeline.services import inspiration
    pictures = [a for a in accepted if a.category == kind]
    if len(pictures) > inspiration.MAX_PICTURES:
        return "A design takes at most %d pictures here." % inspiration.MAX_PICTURES
    odd = [a.original_filename for a in pictures if a.media_type not in inspiration.RASTER_TYPES]
    if odd:
        return "%s cannot be read as a picture — use a PNG, JPEG or WEBP." % ", ".join(odd)
    return ""


def _fingerprint(upload) -> str:
    """The sha256 of an uploaded file, read once and rewound — how an inspiration picture's reading is found."""
    import hashlib
    upload.seek(0)
    digest = hashlib.sha256(upload.read()).hexdigest()
    upload.seek(0)
    return digest


def _store_inspiration(task, accepted, kind=None) -> None:
    """§BH69(2): a Complete Product's inspiration pictures, kept with its first stage like any design's — [his final
    goal, B1] and its inside references (``kind``), handed to its carton's stage."""
    from apps.pipeline import references as refs
    from apps.pipeline.models import TaskReference
    from apps.pipeline.services import inspiration
    kind = kind or inspiration.KIND
    for a in accepted:
        ref = TaskReference(task=task, kind=kind, original_filename=a.original_filename,
                            media_type=a.media_type, file_size=a.file_size, ordering=a.ordering,
                            source='USER_UPLOAD', status='REFERENCE_ONLY', sha256=_fingerprint(a.upload))
        ref.image.save(refs.stored_name(a.extension), a.upload, save=False)
        ref.save()
    inspiration.attach(task, task.references.filter(kind=inspiration.KIND))


class InspirationReadView(APIView):
    """POST /api/inspiration/read/ — §BH69(2): ONE inspiration picture read into words on the start page, before a design
    exists, so the owner sees what it took before he starts. Refused by name: not a picture the reader can open, the
    daily spend cap, no key. A picture read before is answered from its stored reading and costs nothing; a new read is
    on the ledger, unbound until the design it was made for is started."""
    permission_classes = [IsAuthenticated, IsDesigner]

    def post(self, request):
        from apps.pipeline import references as refs
        from apps.pipeline.services import inspiration
        files = request.FILES.getlist("picture")
        if len(files) != 1:
            return Response({'error': 'INSPIRATION_ONE_PICTURE', 'words': 'Send one picture at a time.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # [his final goal, 2026-10-05, B1 and B3] an inside reference is read the same way, for its pattern and style; a
        # sticker reference for its shape, fill and border
        from apps.pipeline.services import inside_read
        kind = request.data.get('kind') or inspiration.KIND
        if kind not in (inspiration.KIND,) + inside_read.KINDS:
            return Response({'error': 'PICTURE_KIND_UNKNOWN', 'words': 'This box takes no such picture.'},
                            status=status.HTTP_400_BAD_REQUEST)
        checked = refs.validate_all([(kind, files)], {kind})
        refused = ("" if checked.ok else "; ".join(r.message for r in checked.rejections)) or \
            _picture_refusal(checked.accepted, kind)
        if refused:
            return Response({'error': 'INSPIRATION_PICTURE_REFUSED', 'words': refused},
                            status=status.HTTP_400_BAD_REQUEST)
        data = files[0].read()
        try:
            if kind in inside_read.KINDS:
                row, spent = inside_read.read_picture(data, user=request.user, kind=kind)
                return Response(inside_read.payload(row, spent=spent))
            row, spent = inspiration.read(data, user=request.user)
        except inspiration.InspirationReadRefused as refusal:
            return Response({'error': refusal.code, 'words': refusal.words},
                            status=status.HTTP_429_TOO_MANY_REQUESTS if refusal.code == 'DAILY_BUDGET_EXCEEDED'
                            else status.HTTP_409_CONFLICT)
        except Exception:  # noqa: BLE001 — the reading service failed; nothing was stored, the page says so
            import logging
            logging.getLogger(__name__).exception("inspiration read failed")
            return Response({'error': 'INSPIRATION_READ_FAILED',
                             'words': 'The picture could not be read just now — try it again.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response(inspiration.payload(row, spent=spent))


class TaskInspirationView(APIView):
    """POST /api/tasks/<task_id>/inspiration/ — §BH69(2), "an upload box ... on a design's Adjust panel": ONE inspiration
    picture added to a design where its Adjust panel shows, read at once into words against the design — its spend the
    design's own, inside its cap — and kept with it only once it has been read. Refused by name, before any read: an
    account that did not start the design (staff excepted: the accounts its file is served to, task_reference_file), a
    design whose Adjust panel is not shown, a seventh picture, a picture it keeps already, a design that has spent its
    cap — and every refusal the start page's read has."""
    permission_classes = [IsAuthenticated, IsDesigner]

    def post(self, request, task_id):
        from apps.pipeline import references as refs
        from apps.pipeline.models import InspirationReading, TaskReference
        from apps.pipeline.services import cost_ledger, inspiration
        task = get_object_or_404(DesignTask, id=task_id)
        user = request.user
        if task.created_by_id and task.created_by_id != user.id and not (user.is_staff or user.is_superuser):
            return Response({'error': 'INSPIRATION_NOT_YOURS',
                             'words': 'A picture is added to a design by the person who started it.'},
                            status=status.HTTP_403_FORBIDDEN)
        if task.status not in inspiration.ADD_STATUSES:
            return Response({'error': 'INSPIRATION_NOT_ON_THIS_STEP',
                             'words': 'A picture is added to a design on its Adjust panel, which shows at its review.'},
                            status=status.HTTP_409_CONFLICT)
        files = request.FILES.getlist("picture")
        if len(files) != 1:
            return Response({'error': 'INSPIRATION_ONE_PICTURE', 'words': 'Send one picture at a time.'},
                            status=status.HTTP_400_BAD_REQUEST)
        kept = task.references.filter(kind=inspiration.KIND)
        checked = refs.validate_all([(inspiration.KIND, files)], {inspiration.KIND})
        refused = ("" if checked.ok else "; ".join(r.message for r in checked.rejections)) or \
            inspiration.refusal_for(checked.accepted)
        if not refused and kept.count() >= inspiration.MAX_PICTURES:
            refused = "A design takes at most %d inspiration pictures." % inspiration.MAX_PICTURES
        if refused:
            return Response({'error': 'INSPIRATION_PICTURE_REFUSED', 'words': refused},
                            status=status.HTTP_400_BAD_REQUEST)
        picture = checked.accepted[0]
        digest = _fingerprint(picture.upload)
        if kept.filter(sha256=digest).exists():
            return Response({'error': 'INSPIRATION_KEPT_ALREADY', 'words': 'This design keeps this picture already.'},
                            status=status.HTTP_409_CONFLICT)
        try:
            cost_ledger.check_task_budget(task)
        except cost_ledger.BudgetExceededError:
            return Response({'error': 'TASK_BUDGET_EXCEEDED',
                             'words': 'This design has spent its cap, so the picture was not read.'},
                            status=status.HTTP_409_CONFLICT)
        over_cap = False
        try:
            row, spent = inspiration.read(picture.upload.read(), task=task, user=user)
        except inspiration.InspirationReadRefused as refusal:
            return Response({'error': refusal.code, 'words': refusal.words},
                            status=status.HTTP_429_TOO_MANY_REQUESTS if refusal.code == 'DAILY_BUDGET_EXCEEDED'
                            else status.HTTP_409_CONFLICT)
        except cost_ledger.BudgetExceededError:     # read and paid for, and it took the design past its cap: kept
            row = InspirationReading.objects.filter(sha256=digest).first()
            if row is None:
                return Response({'error': 'SPENDING_PAUSED', 'words': 'The rescue budget cannot reserve this read. Nothing was purchased.'}, status=409)
            spent, over_cap = True, True
        except Exception:  # noqa: BLE001 — the reading service failed; nothing was kept, the page says so
            import logging
            logging.getLogger(__name__).exception("inspiration read failed")
            return Response({'error': 'INSPIRATION_READ_FAILED',
                             'words': 'The picture could not be read just now — try it again.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        picture.upload.seek(0)
        last = kept.order_by('-ordering').values_list('ordering', flat=True).first()
        ref = TaskReference(task=task, kind=inspiration.KIND, original_filename=picture.original_filename,
                            media_type=picture.media_type, file_size=picture.file_size,
                            ordering=0 if last is None else last + 1, source='USER_UPLOAD', status='REFERENCE_ONLY',
                            sha256=digest)
        ref.image.save(refs.stored_name(picture.extension), picture.upload, save=False)
        ref.save()
        AgentLog.objects.create(task=task, agent_name='ARIA', actor=user, level='info',
                                action=f'An inspiration picture was added by {user.username} on the Adjust panel — '
                                       'read into words and kept with the design')
        return Response(dict(inspiration.payload(row, spent=spent), reference_id=ref.pk,
                             url=f'/api/tasks/{task.pk}/references/{ref.pk}/',
                             left=inspiration.MAX_PICTURES - kept.count(),
                             over_cap=('Reading it took this design past its cap.' if over_cap else '')))


class TaskStatusView(APIView):
    """GET /api/tasks/<task_id>/status/"""
    permission_classes = [IsAuthenticated, IsTeamMember]

    def get(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        from apps.pipeline.services.authored_master import is_authored
        if is_authored(task):
            from apps.pipeline.services.authored_master import RETIRED_PAGE
            return Response({"id": task.pk, "status": task.status, "authoring_backend": task.options["authoring_backend"],
                             "creative_acceptance": "review_pending", "production_ready": False,
                             "revision": task.options.get("current_revision"),
                             "page_url": None, "page": RETIRED_PAGE})
        logs = task.logs.order_by('-timestamp')[:20]
        # Current set by default; the full history (superseded images from
        # earlier passes) is available behind ?include_superseded=1
        # (Milestone 11.3).
        include_superseded = request.query_params.get('include_superseded') in ('1', 'true', 'yes')
        images = task.images.all() if include_superseded else task.images.filter(superseded=False)
        packaging = task.current_output()

        from .serializers import (
            AgentLogSerializer, CreativeBriefSerializer, GateDecisionSerializer,
            GeneratedImageSerializer, PackagingOutputSerializer,
        )
        from apps.pipeline.services.cost_ledger import task_cost_usd as _task_cost_usd
        from apps.pipeline.spend_estimates import measured_costs as _measured_costs
        from django.conf import settings as _settings
        from apps.pipeline.services.panel_info import build_panel_info
        from apps.pipeline.review_board import build_review_board
        from apps.pipeline.targets.composite import build_project_summary
        from apps.pipeline.services.reconstruction_status import (
            build_container_gate2_readiness,
            build_container_reconstruction_result,
            build_container_reconstruction_status,
        )
        from apps.pipeline.services.visual_quality_gate import (
            evaluate_container_visual_quality,
        )
        # VQR-2A: evaluated once per request; None unless a container
        # reconstruction is cleanly COMPLETED (worker failures and
        # inconsistent records are never evaluated as visual results).
        container_quality = evaluate_container_visual_quality(task)
        from apps.pipeline.targets.ui import container_profile_editor_config
        from apps.pipeline.live_views import where_of
        from apps.dashboard.words import alike_words as _alike_words
        from .serializers import DesignTaskSerializer as _DesignTaskSerializer
        _map_stop = _DesignTaskSerializer().get_gate_1_map_stop
        from apps.dashboard.words import drawing_stop_reasons as _drawing_stop_reasons
        from apps.dashboard.words import stop_words as _stop_words
        from apps.pipeline.step_times import stalled as _stalled
        from apps.pipeline.step_times import working_step
        from apps.pipeline.services.concept_quality import summary as concept_quality_summary, repair_state
        brief = CreativeBrief.objects.filter(task=task).first()
        # UI-2B-1: this endpoint is POLLED for live lifecycle state — a
        # browser memory-cache hit would silently freeze the status view, so
        # caching is forbidden explicitly (found via Playwright: Chromium
        # served repeated identical GETs from memory cache).
        response = Response({
            'id': task.id,
            'status': task.status,
            'task_text': task.task_text,
            'concept_quality': concept_quality_summary(task.images.filter(superseded=False)),
            # Phase 2A-5-CORR-2: the dashboard polls THIS endpoint, and the
            # direction-selection panel reads brief.design_intent + directions
            # from it — the DRF task serializer alone never reaches the UI.
            'brief': CreativeBriefSerializer(brief).data if brief else None,
            'product_name': task.product.name if task.product else None,
            'created_by': task.created_by.username if task.created_by else None,
            'assigned_to': task.assigned_to.username if task.assigned_to else None,
            'logs': AgentLogSerializer(logs, many=True).data,
            # §BH54(k) 1: the feed says how many rows exist beyond the twenty it is sent; the badge has read
            # `cost_usd` since Milestone 12.2 and this payload never carried it; and what a click costs is
            # said before the click, measured on the ledger (apps/pipeline/spend_estimates.py)
            'logs_total': task.logs.count(),
            'cost_usd': float(_task_cost_usd(task)),
            'spend_estimates': _measured_costs(),
            'images': GeneratedImageSerializer(images, many=True, context={'request': request}).data,
            'packaging_output': PackagingOutputSerializer(packaging).data if packaging else None,
            'gate_decisions': GateDecisionSerializer(task.gate_decisions.all(), many=True).data,
            'gate_1_notes': task.gate_1_notes,
            'gate_2_notes': task.gate_2_notes,
            'image_rerun_count': task.image_rerun_count,
            'repair_allowance': repair_state(task),
            # §BH55 Phase 3: the server's own re-run limit, which the page counted as two; and the design's target,
            # which the step line reads (a carton has a size step, a printed piece none)
            'image_rerun_cap': _settings.MAX_REVISION_PASSES,
            'design_target': task.design_target,
            # §BH55 Phase 3: whether the carton is sized from the product's record — the concepts step says what using a
            # concept will spend, and a product with no size on record is estimated from the concept, a paid call
            'size_from_record': bool(task.product and task.product.width_mm and task.product.depth_mm
                                     and task.product.height_mm),
            'error_message': task.error_message,
            # 2A-6E-CORR-5 §8: the UI must state when a regeneration attempt
            # failed BEFORE image generation, so historical images are never
            # presented as new output of the failed job.
            'latest_regeneration_job': (lambda job: {
                'id': job.pk, 'status': job.status, 'error': job.error,
                'created_at': job.created_at, 'finished_at': job.finished_at,
            } if job else None)(task.regeneration_jobs.first()),
            # Info-panel defaults (2026-07-06): prefill for the dimension
            # gate's editable "printed information" section.
            'panel_info': build_panel_info(task),
            # Design Review Board (RB1, 2026-07-08): structured approval data;
            # additive — existing keys above are untouched. The UI board shell
            # (RB2) renders the six sections from this payload.
            'review_board': build_review_board(task, request=request).model_dump(),
            # [his goal of 2026-10-06, item 2] the step it works on, with its measured rough time, and the version of
            # this screen the open page compares the design's where-it-stands with (live_views.where_of)
            'working_step': working_step(task),
            # [his second test blocker on design 123, 2026-10-09, (2)] whether it has stopped moving — the page offers
            # Resume only then
            # [his goal of 2026-10-13, (3): "'Resume this design / Not moving?' appears ONLY when the design has truly
            # stopped … Never while it's working, waiting for me, or done."] said for every state, True only then
            'stalled': _stalled(task),
            # [his test findings on design 121, 2026-10-07, item 3] why it stopped, in words, with every status — the
            # page that was open when it stopped reads it here, never the record's own text
            'stop_words': _stop_words(task) if task.status == 'failed' else '',
            # [his answers after 122 was redrawn, 2026-10-08, (1)] the design's SKU, and whether it is its product
            # record's (then it stands) or his to give at Gate 2
            'sku': task.sku_on_record(),
            'sku_from_product': bool(task.product_id and str(getattr(task.product, 'product_id', '') or '').strip()),
            # [his test blocker on design 122 at reconstruction, 2026-10-08, item 3] why the last drawing stopped, each
            # reason in words — every step that shows a drawing's stop reads it here, never the record's codes alone
            # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010),
            # (4): "the "couldn't be drawn" note reaches the design page"] the concept a drawing stopped at, why, each
            # part and his options, while the design waits at Gate 1 — the page has rendered it since his finding on
            # 119, and this payload, the one the page polls, never carried it (DesignTaskSerializer only)
            'gate_1_map_stop': _map_stop(task),
            'drawing_stop_words': _drawing_stop_reasons(
                (packaging.spec_sheet or {}).get('generation_error') if packaging else '', task),
            # [his test blocker on design 123, 2026-10-09, (2)] three shown though a check still found them too alike
            # after its one retry — the note beside them, in words; [] for every other design
            'gate_1_alike_words': _alike_words(task),
            'watch': where_of(task),
            # Confirm Profile UI-1 (§19): the versioned editor configuration —
            # choices, ranges, defaults, creation hints, gate eligibility.
            # Product Container only; other targets carry None so no profile
            # vocabulary leaks into their boards. Reading it mutates nothing.
            'container_profile_editor': (
                container_profile_editor_config(task)
                if task.design_target == 'product_container' else None),
            # UI-2B-1: derived, read-only reconstruction snapshot — None for
            # other targets and for unconfirmed profiles, so no lifecycle
            # vocabulary leaks where it does not apply.
            'container_reconstruction_status':
                build_container_reconstruction_status(task),
            # UI-2B-2A: the COMPLETED-only result contract (roles, safe
            # metadata, authorized-endpoint links); None everywhere else.
            'container_reconstruction_result':
                build_container_reconstruction_result(task),
            # VQR-6: the ONE Gate-2 readiness authority — every result
            # surface and the Gate-2 backend consume this, never FileField
            # truthiness. VQR-2A: readiness now also requires the fail-closed
            # visual quality gate; the full gate report ships beside it so
            # the UI can render every required axis honestly.
            'container_gate2_readiness':
                build_container_gate2_readiness(
                    task, quality=container_quality),
            'container_visual_quality_gate': container_quality,
            # §BH71 (0a), the owner's goal of 2026-09-28: what is not measured yet, in words — shown beside Approve,
            # never a reason it is refused and never marked passed
            'acceptance_warnings': _acceptance_warnings(task, container_quality),
            # [his goal of 2026-10-13, (1)] every check the design stands at Gate 2 without passing, in words, beside
            # Approve — kept with his approval, never a refusal of it
            'gate2_problems': _gate2_problems_payload(task, container_quality),
            # §BH71 PART 2: the design's trend board — its pictures, ticks, refusals, searches and cost; None without one
            'trend_board': _trend_board_payload(task),
            # §BH55 Phase 1: his decision on the design — the preview's sha256
            # (from its bytes), whether the viewer is the owner, his acts
            'design_acceptance': _design_acceptance(task, request.user),
            # [B1, the clean-up of 2026-10-04] who confirmed the shape on its record, said to this viewer — the
            # badge read "Confirmed by a person" whoever confirmed it, the executor on his word included
            'container_confirmation_provenance': _confirmation_provenance(packaging, request.user),
            # Composite coordinator read-model (C3, 2026-07-09): recipe ⋈ children
            # for the stage breadcrumb / navigation / project-completed summary.
            # None for single-target tasks → UI renders nothing new (parity).
            'project': (build_project_summary(task.project, request=request)
                        if task.project_id else None),
            # [His goal after the pitch page, 2026-10-15, B (10) and (11)] the pitch run: each step the system took by
            # itself, any stop in words, Start → final files, and whether it is taking the step the design waits at
            # (the page then shows one line in place of the step's form); None for every other design
            'autopilot': _autopilot_payload(task),
        })
        response['Cache-Control'] = 'no-store'
        return response


def _autopilot_payload(task):
    from apps.pipeline.autopilot import status_payload
    return status_payload(task)


GATE_CONFLICT = {'error': 'Task is not awaiting this gate'}


def _daily_cap_refusal():
    """§BH54(b) (k) 5, OWNER RULED 2026-09-19: "a re-run is a spend, so it … checks the daily cap like every other
    spend. The retry view running no cap check is a defect; fix it here." The check task creation has run since
    Milestone 12.2, in its own words: 429 once the rolling 24 h AI spend reaches MAX_COST_PER_DAY. Asked by the retry
    view and the re-run doors (three until the clean-up of 2026-10-04 left the image re-run alone), BEFORE any
    transition, log row or dispatch. NOT every door that dispatches paid
    work asks it — measured 2026-09-19: the Gate-1 revision and the direction selection do not. Reported, not
    changed here: he ordered the re-run's check."""
    from apps.pipeline.services.cost_ledger import daily_budget_exceeded
    if daily_budget_exceeded():
        return Response(
            # §BH55 Phase 3: the refusal's own clock in words — it said "try again tomorrow" of a rolling window
            {'error': 'daily AI budget exceeded — the last 24 hours have spent the daily cap; paid work can '
                      'start again once that spend falls under it (Status shows it)'},
            status=status.HTTP_429_TOO_MANY_REQUESTS)
    return None


def _pre_2a_refusal(task):
    """THE CLEAN-UP OF 2026-10-04 (E8, on the owner's approved list): the pre-2A run path — a brief with directions
    and no planned design intent — was removed with the "rerun prompts" and "rerun creative" doors. A door that would
    run such a design again refuses it BY NAME here: 409, the code in its own field and the reason in plain words,
    asked BEFORE any transition, log row, dispatch or spend. `ARIAAgent.run` fails one that reaches it anyway with the
    same code."""
    from apps.pipeline.agents.aria import PRE_2A_BRIEF_RETIRED, PRE_2A_BRIEF_RETIRED_WORDS, pre_2a_brief
    if pre_2a_brief(task):
        return Response({'error': PRE_2A_BRIEF_RETIRED_WORDS, 'code': PRE_2A_BRIEF_RETIRED},
                        status=status.HTTP_409_CONFLICT)
    return None


def _transition(task_id, from_status, **updates):
    """Atomic conditional state transition (Milestone 8.3 / audit C3).

    UPDATE ... WHERE status=<from_status> so two concurrent approvals can't
    both win: exactly one caller sees 1 row updated (and may enqueue Celery
    work); the loser sees 0 and must return 409 Conflict.
    """
    return DesignTask.objects.filter(id=task_id, status=from_status).update(**updates)


def _record_decision(task, gate, decision, user, notes=''):
    """Write the immutable audit-trail row for a human gate decision
    (Milestone 11.1). Called only by the transition winner."""
    return GateDecision.objects.create(
        task=task, gate=gate, decision=decision,
        notes=notes or '', decided_by=user,
    )


def select_design_direction(task, user, direction_id):
    """Phase 2A-4 selection service: bind the STABLE direction id, then resume.

    Returns (payload, http_status). Selection is idempotent — repeating the same
    choice reports the existing selection and enqueues nothing; choosing a
    different direction after one is bound fails DIRECTION_ALREADY_SELECTED
    (changing course after rendering begins needs a separately designed restart
    workflow). Only the id crosses the trust boundary: a request cannot supply a
    direction object, a prompt, DIP references, target guidance, or an actor.
    """
    from django.db import transaction
    from django.utils import timezone as dj_timezone

    from apps.pipeline.design_intent import (
        DesignIntentError, validate_design_intent_document,
    )

    if not isinstance(direction_id, str) or not direction_id.strip():
        return {'error': 'direction_id (the stable direction id) is required'}, 400
    direction_id = direction_id.strip()

    with transaction.atomic():
        locked_task = DesignTask.objects.select_for_update().get(id=task.id)
        brief = CreativeBrief.objects.select_for_update().filter(
            task=locked_task).first()
        if brief is None or not brief.design_intent:
            return {'error': 'this task has no direction plan to select from'}, 409

        # idempotency first: the same accepted choice is simply reported back
        if brief.selected_direction_id:
            if brief.selected_direction_id == direction_id:
                return {'status': locked_task.status,
                        'selected_direction_id': brief.selected_direction_id,
                        'direction_selected_at': brief.direction_selected_at,
                        'message': 'Direction already selected.'}, 200
            return {'error': 'DIRECTION_ALREADY_SELECTED',
                    'selected_direction_id': brief.selected_direction_id}, 409
        if locked_task.status != 'awaiting_direction_selection':
            return {'error': 'Task is not awaiting direction selection'}, 409

        document = {**brief.design_intent, 'directions': brief.directions}
        try:
            validate_design_intent_document(document)
        except DesignIntentError as exc:
            return {'error': f'persisted direction plan is invalid ({exc.code}); '
                             'selection refused'}, 409
        matches = [d for d in brief.directions
                   if d.get('direction_id') == direction_id]
        if len(matches) != 1:
            return {'error': f'unknown direction_id {direction_id!r}; selection '
                             'binds to the stable direction id, never a list '
                             'index'}, 400

        brief.selected_direction_id = direction_id
        brief.direction_selected_at = dj_timezone.now()
        brief.save(update_fields=['selected_direction_id', 'direction_selected_at'])
        # 2C-2C-CORR-1 §9: selection may enqueue generation ONLY when every
        # generation prerequisite exists (variation spec, approved reference
        # context + influence plan, budget, prohibited-use contract). A
        # dashboard click can no longer race ahead of the Gate-1
        # configuration. Non-composite tasks are always ready — task #51 and
        # every legacy task keep their behavior byte-for-byte.
        from apps.pipeline.services import gate1_checkpoint as ckpt
        ready, missing = ckpt.generation_prerequisites(locked_task)
        ckpt.record_prerequisites(locked_task, ready, missing)
        if not ready:
            locked_task.status = ckpt.HOLD_STATUS
            locked_task.save(update_fields=['status'])
            AgentLog.objects.create(
                task=locked_task, agent_name='ARIA',
                action=f"Direction '{matches[0].get('name', '')}' "
                       f"({direction_id}) selected — HELD: Gate-1 "
                       "generation configuration incomplete",
                payload={'selected_direction_id': direction_id,
                         'state': 'AWAITING_GATE1_GENERATION_CONFIGURATION',
                         'missing_prerequisites': missing},
                actor=user,
            )
            return {'status': ckpt.HOLD_STATUS,
                    'selected_direction_id': direction_id,
                    'missing_prerequisites': missing,
                    'message': 'Direction selected. Generation is held '
                               'until the Gate-1 configuration is complete '
                               '(no provider call was made).'}, 200
        locked_task.status = 'queued'
        locked_task.save(update_fields=['status'])
        AgentLog.objects.create(
            task=locked_task, agent_name='ARIA',
            action=f"Direction '{matches[0].get('name', '')}' ({direction_id}) "
                   "selected — rendering three variations next",
            payload={'selected_direction_id': direction_id,
                     'design_intent_schema': document.get('schema_version', '')},
            actor=user,
        )

        def _enqueue():
            from .tasks import run_aria_pipeline
            run_aria_pipeline.delay(task.id)
        transaction.on_commit(_enqueue)

    return {'status': 'queued', 'selected_direction_id': direction_id,
            'message': 'Direction selected. Rendering three variations.'}, 200


class SelectDirectionView(APIView):
    """POST /api/tasks/<task_id>/select_direction/ — Reviewer/Admin only.

    The pre-render creative-planning choice. NOT Gate 1: the user picks a
    reasoning direction here, and later picks a rendered concept at Gate 1.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        payload, http_status = select_design_direction(
            task, request.user, request.data.get('direction_id'))
        return Response(payload, status=http_status)


class Gate1ApproveView(APIView):
    """POST /api/tasks/<task_id>/gate1_approve/ — Reviewer/Admin only."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        image_id = request.data.get('image_id')
        if not image_id:
            return Response({'error': 'image_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Ownership check: the image must belong to THIS task.
        image = get_object_or_404(GeneratedImage, id=image_id, task=task)

        # Selectability guard (2B-3V §7): a Gate-1 set rejected before human
        # selection (e.g. unapproved reference grounding / variation contract
        # not preserved) is preserved for audit but can never be approved. The
        # task is NOT globally failed — it stays reviewable at awaiting_gate_1.
        from apps.pipeline.services.gate1_review import (
            GATE1_IMAGE_REJECTED_UNSELECTABLE, image_is_selectable)
        if not image_is_selectable(image):
            return Response(
                {'error': image.user_rejection_label
                          or 'This concept needs a complete passing review before approval.',
                 'code': GATE1_IMAGE_REJECTED_UNSELECTABLE},
                status=status.HTTP_409_CONFLICT)

        # Atomic transition BEFORE enqueueing: only the winner enqueues, and in
        # eager mode (resume runs inline) the resume's advance isn't clobbered.
        # gate_1_notes are cleared on approval (Milestone 11.3 / audit H10) —
        # the rejection history lives in GateDecision, so stale feedback can no
        # longer poison later re-runs.
        # [his test blocker on design 122, 2026-10-07, item 4: "draw this concept from the template"] his own choice,
        # kept on the concept before the design moves on: the drawing then follows the form's own layout
        from_template = bool(request.data.get('from_template'))
        if not _transition(task.id, 'awaiting_gate_1',
                           status='gate_1_approved', gate_1_notes=''):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
        if from_template:
            from django.utils import timezone as dj_timezone

            from apps.pipeline.targets.container.readable import FROM_TEMPLATE_KEY
            prov = dict(image.reference_provenance or {})
            prov[FROM_TEMPLATE_KEY] = {"by": request.user.username, "at": dj_timezone.now().isoformat()}
            image.reference_provenance = prov
            image.save(update_fields=['reference_provenance'])
        # [his final goal, 2026-10-05, B4: "He picks a picture."] the picture he picks names the direction the design
        # goes on in — bound by the picture's own direction id where no direction was chosen before it
        if image.direction_id:
            from django.utils import timezone as dj_timezone
            CreativeBrief.objects.filter(task=task, selected_direction_id='').update(
                selected_direction_id=image.direction_id, direction_selected_at=dj_timezone.now())

        _record_decision(task, 'gate_1', 'approve', request.user,
                         notes=(request.data.get('notes') or '').strip())

        from .tasks import resume_aria_gate1
        resume_aria_gate1.delay(task.id, image_id)
        task.refresh_from_db()

        return Response({'status': task.status, 'message': 'Gate 1 approved. Generating packaging output.'})


def _revision_refusal(task, *, allow_resume=False):
    from apps.pipeline.services.concept_quality import repair_state
    state = repair_state(task)
    if state['can_revise'] or (allow_resume and state['can_resume']):
        return None
    return Response({'error': state['reason'], 'code': 'REVISION_REVIEW_REQUIRED'}, status=status.HTTP_409_CONFLICT)


class ConceptRedrawView(APIView):
    """POST /api/tasks/<task_id>/concept_redraw/ ``{"image_id"}`` — [his test blocker on design 122, 2026-10-07, item 4:
    "redraw for $X ... each with a button"] a concept that cannot be drawn yet, redrawn once more on a plain contrasting
    backdrop and checked again, by his button; what it costs is said beside the button. Refused by name for a concept
    the check did not find undrawable, or a design not at Gate 1."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from apps.pipeline.services.concept_design_map import MAP_STOP_KEY
        from apps.pipeline.targets.container.readable import CHECK_KEY, NOT_DRAWABLE
        task = get_object_or_404(DesignTask, id=task_id)
        image = get_object_or_404(GeneratedImage, id=request.data.get('image_id'), task=task)
        prov = image.reference_provenance or {}
        # a concept the check found undrawable, or one his finding on design 119 stopped at approval for its picture
        if (prov.get(CHECK_KEY) or {}).get('state') != NOT_DRAWABLE and not (prov.get(MAP_STOP_KEY) or {}).get('concept'):
            return Response({'error': 'This concept can be drawn already — it needs no redraw.',
                             'code': 'CONCEPT_REDRAW_NOT_OPEN'},
                            status=status.HTTP_409_CONFLICT)
        refusal = _revision_refusal(task)
        if refusal is not None:
            return refusal
        if not _transition(task.id, 'awaiting_gate_1', status='running'):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
        AgentLog.objects.create(
            task=task, agent_name='ARIA', actor=request.user,
            action=f"Concept redraw requested by {request.user.username} — '{image.direction_name}'",
        )
        from .tasks import redraw_concept
        redraw_concept.delay(task.id, image.pk)
        task.refresh_from_db()
        return Response({'status': task.status, 'message': 'Redrawing the concept so it can be drawn.'})


class Gate1RejectView(APIView):
    """POST /api/tasks/<task_id>/gate1_reject/ — Reviewer/Admin only."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        notes = request.data.get('notes', '').strip()
        if not notes:
            return Response({'error': 'notes are required when rejecting'}, status=status.HTTP_400_BAD_REQUEST)

        refusal = _pre_2a_refusal(task)                  # the clean-up of 2026-10-04 (E8): before the decision row
        if refusal is not None:
            return refusal
        refusal = _revision_refusal(task)
        if refusal is not None:
            return refusal
        if not _transition(task.id, 'awaiting_gate_1', status='queued', gate_1_notes=notes):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)

        _record_decision(task, 'gate_1', 'reject', request.user, notes=notes)
        AgentLog.objects.create(
            task=task, agent_name='ARIA', actor=request.user,
            action=f'Gate 1 rejected by {request.user.username} — revision requested. Notes: {notes}',
        )

        from .tasks import run_aria_pipeline
        run_aria_pipeline.delay(task.id)
        task.refresh_from_db()

        return Response({'status': task.status, 'message': 'Sent back to ARIA with revision notes.'})


def _forbidden_panel_texts(task) -> tuple[str, ...]:
    """Strings that must never print on consumer panels: the task title /
    brief instruction text. The product name is exempt — it belongs there."""
    tt = (task.task_text or '').strip()
    if not tt:
        return ()
    pname = (getattr(getattr(task, 'product', None), 'name', '') or '').strip().lower()
    out = []
    for cand in {tt, tt.splitlines()[0].strip()}:
        if cand and len(cand) >= 12 and cand.lower() != pname:
            out.append(cand)
    return tuple(out)


class Gate2ApproveView(APIView):
    """POST /api/tasks/<task_id>/gate2_approve/ — Reviewer/Admin only."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        from apps.pipeline.services.authored_master import is_authored
        if is_authored(task):
            return Response({"error": "This authored master still needs independent creative and supplier review.",
                             "code": "HYBRID_REVIEW_PENDING"}, status=status.HTTP_409_CONFLICT)
        packaging_output_id = request.data.get('packaging_output_id')
        if not packaging_output_id:
            return Response({'error': 'packaging_output_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Ownership check (audit C3): the output must belong to THIS task —
        # a cross-task or bogus id is a 404, never a stranded task.
        output = get_object_or_404(PackagingOutput, id=packaging_output_id, task=task)

        # VQR-6: Gate 2 consults the ONE readiness authority. Client hiding
        # is presentation; THIS is the enforcement — a direct POST against
        # an inconsistent, unavailable or technical-intervention result is
        # refused before any decision, state or handoff work.
        vq_warned = []
        if task.design_target == 'product_container':
            from apps.pipeline.services.reconstruction_status import (
                build_container_gate2_readiness)
            readiness = build_container_gate2_readiness(task)
            # §BH71 (0a): its unmeasured axes are warnings beside Approve, kept with the verdict saved below
            vq_warned = list(((readiness or {}).get('visual_quality') or {}).get('acceptance_warnings') or [])
        # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design ... the problem is shown
        # beside Approve in plain words."] ONE reading of what stands beside Approve (gate2_problems): an approval is
        # refused only where his own acceptance of this drawing is not given or there is no drawing to approve; every
        # check that held Gate 2 until then — a visual-quality failure, a readiness section's codes, a stale verdict, an
        # artwork piece's codes, a die that does not fold, a label, a front's copy, a die outside its domain — is kept
        # with his approval, each in words
        from apps.dashboard.owner_channel import preview_sha256 as _preview_sha256
        from apps.pipeline.gate2_problems import KEPT_KEY, gate2_problems
        _picture = _preview_sha256(output)[0] if (task.design_target == 'product_container'
                                                   or (output.spec_sheet or {}).get('backend') == 'container'
                                                   or (output.spec_sheet or {}).get('container_reconstruction')) \
            else None
        problems = gate2_problems(task, output, preview_sha256=_picture)

        # DIP-2A-5-DIE-4 — machine production-readiness gate. Strict outputs
        # (spec_sheet.production_validation == "strict", set by the corrected
        # dieline pipeline) cannot be approved while any production failure
        # stands; there is deliberately no override flag.
        spec = output.spec_sheet or {}
        validation = spec.get('production_validation')
        # 2B-3D: CONTAINER Gate-2 enforcement. Approval refuses while any
        # production-readiness section carries codes AND — decisively — while
        # HUMAN DESIGN ACCEPTANCE is not an explicit recorded acceptance: a
        # human visual rejection or an unreviewed reconstruction blocks with
        # HUMAN_VISUAL_ACCEPTANCE_REQUIRED. Automated fidelity reports can
        # never override a human rejection. No override flag exists.
        if problems['verdict'] is not None:
            verdict = problems['verdict']
            if vq_warned:       # §BH71 (0a): the visual-quality check's unmeasured axes, kept with the verdict
                verdict['visual_quality_warnings'] = vq_warned
            spec[  # persist the verdict either way — the report is auditable
                'container_production_readiness/1.0'] = verdict
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])
        if problems['refusal'] is not None:
            return Response(problems['refusal'], status=status.HTTP_409_CONFLICT)
        kept = list(problems['kept'])
        if validation == 'standard':
            # Phase 2A-6 §11: the generalized validator — structural, artwork,
            # content and colour/output families, each with its own codes, plus
            # the §12 editability report. No override exists.
            from apps.dielines.validators.production import evaluate_production
            from apps.pipeline.services.print_data import (
                build_print_record,
                forbidden_copy_strings,
            )
            print_data = spec.get('print_data') or {}
            record = build_print_record(
                print_data.get('values') or spec.get('panel_info') or {},
                verified_keys=print_data.get('verified_keys') or (),
                not_applicable=print_data.get('not_applicable') or (),
            )
            report = evaluate_production(
                output,
                expected_template=spec.get('required_template'),
                print_record=record,
                forbidden_panel_texts=forbidden_copy_strings(task),
            )
            if not report.ready:            # [his goal of 2026-10-13, (1)] kept with his approval, said
                from apps.pipeline.gate2_problems import _row
                kept += [_row(f.get('code'), _failure_words(f)) if isinstance(f, dict) else _row(f)
                         for f in report.failures]
        elif validation == 'strict':
            # Phase 2A-5 (task #47) validator, kept for outputs produced by
            # the correction command before the generalized path existed.
            from apps.dielines.validators.production_readiness import (
                evaluate_production_readiness,
            )
            report = evaluate_production_readiness(
                output,
                expected_template=spec.get('required_template'),
                forbidden_panel_texts=_forbidden_panel_texts(task),
            )
            if not report.ready:            # [his goal of 2026-10-13, (1)] kept with his approval, said
                from apps.pipeline.gate2_problems import _row
                kept += [_row(f.get('code'), _failure_words(f)) if isinstance(f, dict) else _row(f)
                         for f in report.failures]

        # gate_2_notes cleared on approval; history lives in GateDecision.
        if not _transition(task.id, 'awaiting_gate_2',
                           status='gate_2_approved', gate_2_notes=''):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
        # [his goal of 2026-10-13, (1)] every check that stood beside Approve, kept with the approval in its words
        # [his last goal before the pitch, 2026-10-16, Step 1 (1)] the rows added here said as the page says them: the
        # system's own notes one sentence, every code kept (gate2_problems._merged)
        from apps.pipeline.gate2_problems import _merged
        kept = list(problems['kept']) + _merged(kept[len(problems['kept']):])
        spec[KEPT_KEY] = kept
        output.spec_sheet = spec
        output.save(update_fields=['spec_sheet'])
        if not (spec.get('backend') == 'container' or spec.get('container_reconstruction')):
            # [his review of 119, 2026-10-05, point 6; §BH71 (0a)] what stood beside Approve — the checks not measured
            # and the words not confirmed — kept with the approval, as a container's are
            spec['acceptance_warnings_at_approval'] = [{k: r[k] for k in ('code', 'words', 'kind')}
                                                       for r in _acceptance_warnings(task, None)]
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])

        _record_decision(task, 'gate_2', 'approve', request.user,
                         notes=(request.data.get('notes') or '').strip())

        from .tasks import resume_aria_gate2
        resume_aria_gate2.delay(task.id, packaging_output_id)
        task.refresh_from_db()

        return Response({'status': task.status, 'message': 'Gate 2 approved. Generating spec sheet PDF.'})


def _reject_artwork_to_gate_1(task, user, notes):
    """§BH55 Phase 2: an artwork design is composed from the concept approved at Gate 1 and has no dimension gate,
    so a revision goes back to Gate 1 — approve another of its concepts, or reject Gate 1 for new ones. The next
    approval composes the task's one output again; the design rejected here stays on its record."""
    if not _transition(task.id, 'awaiting_gate_2', status='awaiting_gate_1', gate_2_notes=notes):
        return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
    task.refresh_from_db()
    _record_decision(task, 'gate_2', 'reject', user, notes=notes)
    GeneratedImage.objects.filter(task=task, is_approved=True).update(is_approved=False)
    output = task.current_output()
    if output is not None:
        spec = output.spec_sheet or {}
        spec['gate_2_revision_note'] = notes
        output.spec_sheet = spec
        output.save(update_fields=['spec_sheet'])
    AgentLog.objects.create(
        task=task, agent_name='ARIA', actor=user, level='info',
        action=f'Gate 2 revision requested by {user.username} — back to Gate 1 to choose a concept. '
               f'Notes: {notes}')
    return Response({'status': task.status,
                     'message': 'Sent back to Gate 1: approve another concept, or reject Gate 1 for new ones.'})


class ConfirmTranslationsView(APIView):
    """POST /api/tasks/<task_id>/confirm_translations/ — Reviewer/Admin only. [His review of 119, 2026-10-05, point 6:
    "The rest is translation: show it as 'Not confirmed yet' beside Approve until I confirm it."] Records that a person
    confirmed the label's translations as they stand — who, when, and a hash of exactly those words — so the warning
    beside Approve closes, and opens again if the words change."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from django.utils import timezone

        from apps.pipeline.targets.packaging import (TRANSLATIONS_CONFIRMED_KEY, label_translations,
                                                     translations_sha256)
        task = get_object_or_404(DesignTask, id=task_id)
        output = task.current_output()                # the output the page shows
        spec = (output.spec_sheet if output else None) or {}
        words = label_translations(spec)
        if not words:
            return Response({'error': 'NO_TRANSLATIONS', 'message': 'This design carries no translations.'},
                            status=status.HTTP_400_BAD_REQUEST)
        spec[TRANSLATIONS_CONFIRMED_KEY] = {"by": request.user.username, "at": timezone.now().isoformat(),
                                            "languages": sorted(words), "sha256": translations_sha256(words)}
        output.spec_sheet = spec
        output.save(update_fields=['spec_sheet'])
        AgentLog.objects.create(task=task, agent_name='ARIA', actor=request.user, level='info',
                                action=f'The label\'s translations ({", ".join(sorted(words))}) confirmed by '
                                       f'{request.user.username}')
        return Response({'status': 'confirmed', TRANSLATIONS_CONFIRMED_KEY: spec[TRANSLATIONS_CONFIRMED_KEY]})


class DesignSkuView(APIView):
    """POST /api/tasks/<task_id>/sku/ — Reviewer/Admin only. [His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "a design started from a brief may be approved without an SKU. \"SKU missing\" shows as a production note, never a block. Add an optional SKU field on New design and at Gate 2 so I can fill it in any time."] The SKU he types for a design
    with no product record, at any time: kept on the design and on its project, so every piece of it reads it, and
    written onto each piece's drawing record at once, so its print data counts it now and its next drawing prints it;
    empty clears it. A design whose product record carries its SKU keeps that one, and says so."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        if task.product_id and str(getattr(task.product, 'product_id', '') or '').strip():
            return Response({'error': 'SKU_FROM_PRODUCT_RECORD',
                             'words': 'This design\'s SKU is its product record\'s, %s — change it there.'
                                      % task.product.product_id}, status=status.HTTP_409_CONFLICT)
        sku = clean_sku(request.data.get('sku'))
        pieces = list(task.project.tasks.all()) if task.project_id else [task]
        for piece in pieces:
            piece.sku = sku
            piece.save(update_fields=['sku'])
            for output in piece.packaging_outputs.all():
                spec = output.spec_sheet or {}
                if spec.get('backend') == 'container' or 'sku' in spec:
                    spec['sku'] = piece.sku_on_record()
                    output.spec_sheet = spec
                    output.save(update_fields=['spec_sheet'])
        if task.project_id:
            meta = dict(task.project.metadata or {})
            meta['sku'] = sku
            task.project.metadata = meta
            task.project.save(update_fields=['metadata'])
        AgentLog.objects.create(task=task, agent_name='ARIA', actor=request.user, level='info',
                                action=(f'SKU set to {sku} by {request.user.username}' if sku
                                        else f'SKU cleared by {request.user.username}'))
        return Response({'sku': sku, 'words': ('Saved — SKU %s. It is printed the next time the design is drawn.' % sku
                                               if sku else 'Cleared — this design has no SKU now.')})


class Gate2RejectView(APIView):
    """POST /api/tasks/<task_id>/gate2_reject/ — Reviewer/Admin only.

    Send a rejected dieline back to the dimension gate so the user can adjust
    the carton and regenerate. Mirrors Gate1RejectView: notes are required and
    are surfaced both in the log and on the dimension form for the next pass.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        notes = request.data.get('notes', '').strip()
        if not notes:
            return Response({'error': 'notes are required when rejecting'},
                            status=status.HTTP_400_BAD_REQUEST)

        from apps.pipeline.targets.artwork import is_artwork_target
        if is_artwork_target(task.design_target):          # §BH55 Phase 2: artwork has no dimension gate
            return _reject_artwork_to_gate_1(task, request.user, notes)
        if not _transition(task.id, 'awaiting_gate_2',
                           status='awaiting_dimensions', gate_2_notes=notes):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
        task.refresh_from_db()

        _record_decision(task, 'gate_2', 'reject', request.user, notes=notes)

        # Surface the revision note on the dieline output so the dimension gate
        # can show it next to the form on the next pass.
        output = task.packaging_outputs.filter(dieline_job__isnull=False).order_by('-pk').first()   # [his review of
        # 127-132, C] the newest, as every door reads it (``DesignTask.current_output``) — a carton drawn again from Gate 1
        # was confirmed on its first output and drawn there, its new one left empty
        if output:
            spec = output.spec_sheet or {}
            spec['gate_2_revision_note'] = notes
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])

        AgentLog.objects.create(
            task=task, agent_name='ARIA', actor=request.user,
            action=f'Gate 2 revision requested by {request.user.username} — back to dimensions. Notes: {notes}',
            level='info',
        )

        return Response({'status': task.status,
                         'message': 'Sent back to the dimension gate with revision notes.'})


class ConfirmDimensionsView(APIView):
    """POST /api/tasks/<task_id>/confirm_dimensions/

    The dimension gate (dieline backend). Validates the confirmed carton
    dimensions, then runs the deterministic geometry + SVG/AI export.
    Body: {"dimensions": {width_mm, depth_mm, height_mm,
                          bleed_mm?, safe_margin_mm?, glue_tab_mm?}}
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        output = task.packaging_outputs.filter(dieline_job__isnull=False).order_by('-pk').first()   # [his review of
        # 127-132, C] the newest, as every door reads it (``DesignTask.current_output``) — a carton drawn again from Gate 1
        # was confirmed on its first output and drawn there, its new one left empty
        if not output:
            return Response(
                {'error': 'No dieline job for this task. Re-run from Gate 1.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dims = request.data.get('dimensions') or {}
        try:
            confirmed = {
                'width_mm': float(dims['width_mm']),
                'depth_mm': float(dims['depth_mm']),
                'height_mm': float(dims['height_mm']),
                'bleed_mm': float(dims.get('bleed_mm', 3.0)),
                'safe_margin_mm': float(dims.get('safe_margin_mm', 4.0)),
                'glue_tab_mm': float(dims.get('glue_tab_mm', 10.0)),
                # Hardening 2026-07-04 (audit C5): board-thickness compensation
                # is confirmable at the gate. The UI sends it checked by
                # default; the schema default stays False so the locked
                # reference regression is untouched.
                'board_thickness_mm': float(dims.get('board_thickness_mm', 0.35)),
                'thickness_compensation': bool(dims.get('thickness_compensation', False)),
            }
            # Phase 2A-6A: the STRUCTURAL fields the standard path needs. The
            # gate used to build a fixed six-key dict, so an explicitly chosen
            # template and the customer's supplied inner/outer dimension sets
            # were silently dropped before reaching ARIA — selection could
            # never see a user choice, and reconciliation fell back to
            # model-derived inner/outer, which would mask a real discrepancy.
            # [his goal of 2026-10-13, (2)] how the box is seen, from its own proposal — never from the page
            if ((output.spec_sheet or {}).get('estimated_dimensions') or {}).get('orientation') == 'flat':
                confirmed['orientation'] = 'flat'
            template = (dims.get('template') or '').strip()
            if template:
                confirmed['template'] = template
            if dims.get('template_version'):
                confirmed['template_version'] = str(dims['template_version']).strip()
            if dims.get('generic_accepted'):
                confirmed['generic_accepted'] = True
            for key in ('inner_mm', 'outer_mm'):
                supplied = dims.get(key)
                if supplied is None:
                    continue
                triplet = [float(v) for v in supplied]
                if len(triplet) != 3:
                    raise ValueError(f'{key} needs exactly three values')
                confirmed[key] = triplet
        except (KeyError, TypeError, ValueError):
            return Response(
                {'error': 'width_mm, depth_mm and height_mm are required numbers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # [his final goal, 2026-10-05, B1: "At the size step he chooses per design: as referenced (default), solid
        # colour, or plain."] what the carton's inside prints — refused by name when it is none of the three
        from apps.ire.inside_print import DEFAULT_MODE as _INSIDE_DEFAULT, MODES as _INSIDE_MODES
        inside = str(request.data.get('inside_print') or dims.get('inside_print') or _INSIDE_DEFAULT)
        if inside not in _INSIDE_MODES:
            return Response({'error': 'INSIDE_PRINT_UNKNOWN',
                             'words': 'The inside prints as referenced, as one solid colour, or plain.'},
                            status=status.HTTP_400_BAD_REQUEST)
        confirmed['inside_print'] = inside
        # [his final goal, 2026-10-05, B3: "THE BACK INFO IS A STICKER, his choice at the size step."]
        from apps.ire.back_info import DEFAULT_MODE as _BACK_DEFAULT, MODES as _BACK_MODES
        back = str(request.data.get('back_info') or dims.get('back_info') or _BACK_DEFAULT)
        if back not in _BACK_MODES:
            return Response({'error': 'BACK_INFO_UNKNOWN',
                             'words': "The back's information is a sticker, printed on the panel, or a custom sticker."},
                            status=status.HTTP_400_BAD_REQUEST)
        confirmed['back_info'] = back

        # [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (6):
        # "Flag impossible sizes at the size step"] a size the carton cannot be made at for its product refused, in
        # words — the page flags it as he types (SizeFlagsView); a size far larger than it needs is said there, never
        # refused
        from apps.pipeline.agents.dieline_agent import size_flags
        impossible = [f for f in size_flags(task, confirmed) if f['level'] == 'impossible']

        # Validate ranges/structural rules up front so the user gets an
        # immediate, specific error instead of a failed pipeline run.
        from pydantic import ValidationError
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.pipeline.agents.dieline_agent import TEMPLATE_TYPE
        try:
            DielineInputJSON(
                # Validate against the template the user actually chose: the
                # structural rules (H > W, D/W ratio) are per template, so
                # validating everything as generic STE could accept or reject
                # the wrong thing (Phase 2A-6A).
                template=confirmed.get('template', TEMPLATE_TYPE),
                template_version=confirmed.get('template_version'),
                unit='mm',
                dimensions={k: confirmed[k] for k in ('width_mm', 'depth_mm', 'height_mm')},
                print_settings={'bleed_mm': confirmed['bleed_mm'],
                                'safe_margin_mm': confirmed['safe_margin_mm']},
                construction={
                    'glue_tab_mm': confirmed['glue_tab_mm'],
                    'board_thickness_mm': confirmed['board_thickness_mm'],
                    'thickness_compensation': confirmed['thickness_compensation'],
                },
                metadata={'product_name': 'validation', 'product_type': 'carton'},
            )
        except ValidationError as exc:
            # pydantic v2 error dicts carry non-JSON-serializable objects in
            # ctx (the raised ValueError itself) — passing exc.errors()
            # straight through 500'd the response and the UI showed a bare
            # "Generation failed" instead of the actual rule (2026-07-07).
            details = [
                {'loc': list(e.get('loc') or ()), 'msg': str(e.get('msg', ''))}
                for e in exc.errors(include_url=False)
            ]
            return Response(
                {'error': 'Invalid dimensions', 'details': details,
                 **({'words': '; '.join(f['words'] for f in impossible)} if impossible else {})},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if impossible:
            # [his test findings on design 123, (6)] a carton the die makes, too small for the product it holds
            return Response({'error': 'SIZE_IMPOSSIBLE', 'words': '; '.join(f['words'] for f in impossible),
                             'flags': impossible}, status=status.HTTP_400_BAD_REQUEST)

        if not _transition(task.id, 'awaiting_dimensions', status='generating_dieline'):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)

        _record_decision(
            task, 'dimension', 'approve', request.user,
            notes=(f"Confirmed {confirmed['width_mm']} × {confirmed['depth_mm']} × "
                   f"{confirmed['height_mm']} mm (bleed {confirmed['bleed_mm']}, "
                   f"safe {confirmed['safe_margin_mm']}, glue {confirmed['glue_tab_mm']})"),
        )

        # [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (7): "The
        # concept check and drawing check use the confirmed size once known."] his size kept on the output as he
        # confirms it — before the drawing's check can stop it (123's 57 x 37 x 123 was kept only in the log and the
        # stop's words) — and shown again at the size step, his own values over the proposal
        from apps.pipeline.targets.container import keep_confirmed_size
        keep_confirmed_size(output, confirmed)

        # Info-panel override (2026-07-06): the dimension gate's "printed
        # information" section — reviewer-edited description/ingredients/
        # barcode/etc. Sanitized + merged over Product/Brand defaults in ARIA.
        panel_info = request.data.get('panel_info')
        if not isinstance(panel_info, dict):
            panel_info = None

        from .tasks import resume_aria_dimensions
        resume_aria_dimensions.delay(task.id, output.id, confirmed, panel_info)
        task.refresh_from_db()

        return Response({'status': task.status, 'message': 'Dimensions confirmed. Generating dieline.'})


class SizeFlagsView(APIView):
    """POST /api/tasks/<task_id>/size_flags/ — [his test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md,
    transcribed at cbdf721), (6): "Flag impossible sizes at the size step (I typed 1123 mm for a 120 mm product; it
    accepted it)."] The sizes typed at the size step, flagged as he types — each side the carton cannot be made at for
    its product, or far larger than it needs, in words (``dieline_agent.size_flags``). Nothing is saved."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from apps.pipeline.agents.dieline_agent import size_flags
        task = get_object_or_404(DesignTask, id=task_id)
        dims = request.data.get('dimensions') if isinstance(request.data.get('dimensions'), dict) else {}
        return Response({'flags': size_flags(task, dims)})


class LabelOfferView(APIView):
    """POST /api/tasks/<task_id>/label_offer/ — [his final goal, 2026-10-05, C5: "Only if it still doesn't fit, STOP and
    offer: a wider carton, the info printed on the inside, or fewer languages."] His choice of a stopped label's offers,
    each as the design's record measured and drew it: ``{"offer": "fewer_languages", "languages": [...]}`` — refused by
    name for an offer not on the record or a design whose label is not stopped. [His second goal of 2026-10-06, item 1;
    his correction of 2026-10-07] "info_inside" and "wider" are refused: the info is never printed inside, and the
    carton is never widened for text. The design is made again with his choice, nothing paid: the English unchanged keeps its
    translations; the choice is kept with the size it is made at."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from apps.ire.compose import BACK_COPY_KEY, LABEL_DOES_NOT_FIT
        from apps.pipeline.services.panel_info import PANEL_INFO_KEYS
        task = get_object_or_404(DesignTask, id=task_id)
        if task.design_target == 'product_container':
            return self._container(request, task)
        output = task.packaging_outputs.filter(dieline_job__isnull=False).order_by('-pk').first()
        spec = dict(output.spec_sheet or {}) if output else {}
        record = spec.get(BACK_COPY_KEY) or {}
        offers = record.get('offers') or {}
        if output is None or LABEL_DOES_NOT_FIT not in (record.get('codes') or []):
            return Response({'error': 'LABEL_OFFER_NOT_OPEN', 'words': "This design's label is not waiting on a choice."},
                            status=status.HTTP_409_CONFLICT)
        offer = request.data.get('offer')
        confirmed = dict(spec.get('confirmed_dimensions') or {})
        # [his correction of 2026-10-07: "Never widen the carton for text"] a wider carton is refused as unknown
        if offer == 'fewer_languages' and list(request.data.get('languages') or []) in (offers.get('fewer_languages')
                                                                                            or []):
            confirmed['label_languages'] = list(request.data.get('languages'))
            said = 'the label in %s' % ' and '.join({'en': 'English', 'es': 'Spanish', 'ar': 'Arabic'}[x]
                                                   for x in confirmed['label_languages'])
        else:
            return Response({'error': 'LABEL_OFFER_UNKNOWN', 'words': 'That is not one of the offers on the record.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not _transition(task.id, 'awaiting_gate_2', status='generating_dieline'):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
        _record_decision(task, 'dimension', 'approve', request.user,
                         notes="His choice of the label's offers: %s." % said)
        info = spec.get('panel_info') or {}
        override = {k: v for k, v in info.items() if k in PANEL_INFO_KEYS and isinstance(v, str)}
        from .tasks import resume_aria_dimensions
        resume_aria_dimensions.delay(task.id, output.id, confirmed, override)
        task.refresh_from_db()
        return Response({'status': task.status, 'message': 'Making the design with %s.' % said})


def _container_offer(view, request, task):
    """[His final goal, 2026-10-05, C5c] His choice of a stopped container back's offers — ``{"offer":
    "fewer_languages", "languages": [...]}``, as the record measured and drew it; the container is made again with it from
    the profile he confirmed, nothing paid (his English unchanged keeps its translations)."""
    from apps.pipeline.targets.container import (CONTAINER_LABEL_LANGUAGES_KEY, CONTAINER_LABEL_OFFERS_KEY,
                                                 confirmed_profile_of)
    output = task.packaging_outputs.order_by('-pk').first()
    spec = dict(output.spec_sheet or {}) if output else {}
    offers = spec.get(CONTAINER_LABEL_OFFERS_KEY) or []
    if not offers:
        return Response({'error': 'LABEL_OFFER_NOT_OPEN', 'words': "This design's label is not waiting on a choice."},
                        status=status.HTTP_409_CONFLICT)
    languages = list(request.data.get('languages') or [])
    if request.data.get('offer') != 'fewer_languages' or languages not in [o.get('languages') for o in offers]:
        return Response({'error': 'LABEL_OFFER_UNKNOWN', 'words': 'That is not one of the offers on the record.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if not _transition(task.id, 'awaiting_gate_2', status='generating_dieline'):
        return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
    said = 'the back in %s' % ' and '.join({'en': 'English', 'es': 'Spanish', 'ar': 'Arabic'}[x] for x in languages)
    spec[CONTAINER_LABEL_LANGUAGES_KEY] = languages
    output.spec_sheet = spec
    output.save(update_fields=['spec_sheet'])
    _record_decision(task, 'container_profile', 'approve', request.user,
                     notes="His choice of the back's offers: %s." % said)
    from .tasks import resume_aria_container_profile
    resume_aria_container_profile.delay(task.id, output.id, confirmed_profile_of(spec))
    task.refresh_from_db()
    return Response({'status': task.status, 'message': 'Making the design with %s.' % said})


LabelOfferView._container = _container_offer


class PrintDataView(APIView):
    """GET/POST /api/tasks/<task_id>/print_data/ — Reviewer/Admin only.

    Phase 2A-6B §1/§6: the bounded printed-information entry and review
    screen. GET returns every contract field with its current value and
    verification state plus the incident/recovery report; POST stores an
    entered record and returns its snapshot hash for confirmation.

    Nothing legal or formula-shaped is ever prefilled, and no value is
    accepted for a field outside the print-data contract.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request, task_id):
        from apps.pipeline.services.print_data_recovery import (
            entry_screen,
            recovery_report,
        )
        task = get_object_or_404(DesignTask, id=task_id)
        return Response({
            'entry': entry_screen(task).to_dict(),
            'recovery': recovery_report(task),
        })

    def post(self, request, task_id):
        from apps.pipeline.services.print_data_recovery import (
            entry_screen,
            save_print_data,
        )
        task = get_object_or_404(DesignTask, id=task_id)
        values = request.data.get('values')
        if not isinstance(values, dict):
            return Response({'error': 'values must be an object'},
                            status=status.HTTP_400_BAD_REQUEST)
        translations = request.data.get('translations')
        if translations is not None and not isinstance(translations, dict):
            return Response({'error': 'translations must be an object'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            saved = save_print_data(
                task, values,
                verified_keys=request.data.get('verified_keys'),
                translations=translations)
        except ValueError as exc:
            return Response({'error': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        AgentLog.objects.create(
            task=task, agent_name='Dieline', actor=request.user,
            action=(f"Printed information entered by {request.user.username} "
                    f"(snapshot {saved['snapshot_hash'][:12]}…)"),
            level='info')
        return Response({
            'snapshot_hash': saved['snapshot_hash'],
            'entry': entry_screen(task).to_dict(),
        })


class TrendPickView(APIView):
    """POST /api/tasks/<task_id>/trends/<pick_id>/ {"used": true|false} — §BH71 PART 2, the owner's goal of 2026-09-28:
    "They are used by default; I can untick any I dislike in one click." One picture of the design's trend board
    ticked or unticked, under the board's lock, while the board takes ticks — before its directions are made. After
    that, or for a card that feeds nothing, a 409 in words."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id, pick_id):
        from apps.pipeline.models import TrendBoard, TrendPick
        from apps.pipeline.services import trend_board
        task = get_object_or_404(DesignTask, id=task_id)
        used = request.data.get("used")
        if not isinstance(used, bool):
            return Response({"error": "TREND_TICK_NOT_A_TICK", "words": "Say whether the picture is used: true or false."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            pick = trend_board.toggle(task, pick_id, used, request.user)
        except (TrendBoard.DoesNotExist, TrendPick.DoesNotExist):
            return Response({"error": "TREND_PICK_NOT_FOUND", "words": "This design's trend board has no such picture."},
                            status=status.HTTP_404_NOT_FOUND)
        except trend_board.TrendBoardClosed as closed:
            return Response({"error": "TREND_BOARD_CLOSED", "words": closed.words}, status=status.HTTP_409_CONFLICT)
        return Response({"pick": pick.pk, "used": pick.used})


class TrendContinueView(APIView):
    """POST /api/tasks/<task_id>/trends/continue/ — "Make the directions now": the ticks snapshotted under the board's
    lock and the design moved on, compare-and-set, so one press (or the window's close) wins; a 409 in words when the
    design is not waiting at its trends."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from apps.pipeline.services import trend_board
        get_object_or_404(DesignTask, id=task_id)
        if not trend_board.proceed(task_id, trend_board.BY_HIS_CLICK, request.user):
            return Response({"error": "TREND_BOARD_CLOSED",
                             "words": "The directions are already being made with the pictures as they were ticked."},
                            status=status.HTTP_409_CONFLICT)
        return Response({"queued": True})


class TrendThumbnailView(APIView):
    """GET /api/tasks/<task_id>/trends/<pick_id>/thumbnail/ — a trend picture's thumbnail, served from quarantine on the
    site's own origin (the page's content policy admits no other) to the people who may see the design; its path is
    never shown, and a path outside the quarantine is refused."""
    permission_classes = [IsAuthenticated, IsTeamMember]

    def get(self, request, task_id, pick_id):
        from pathlib import Path

        from django.http import FileResponse, Http404

        from apps.pipeline.models import TrendPick
        from apps.pipeline.services import web_research as wr
        pick = get_object_or_404(TrendPick, pk=pick_id, board__task_id=task_id, kind=TrendPick.PICTURE)
        if not pick.thumb_path:
            raise Http404("no thumbnail")
        # [his goal of 2026-10-10, item 3: "show nothing rather than junk"] a picture left out, or never read, is never
        # served — the board does not show it, and its address does not either
        if pick.unread_reason:
            raise Http404("not shown")
        root = Path(wr.gateway_config()["quarantine_root"]).resolve()
        path = Path(pick.thumb_path).resolve()
        if not str(path).startswith(str(root) + "/") or not path.is_file():
            raise Http404("no thumbnail")
        response = FileResponse(open(path, "rb"), content_type="image/png")
        response["Cache-Control"] = "private, max-age=3600"
        return response


def _trend_board_payload(task):
    from apps.pipeline.services import trend_board
    return trend_board.payload(task)


class LearnShapeView(APIView):
    """POST /api/tasks/<task_id>/learn_shape/ — §BH71 PART 3, the owner's goal of 2026-09-28: "When a concept shows a
    shape the system doesn't know, it says so and offers to learn it." Learns the lid shape this design's approved
    concept shows (``services.learned_shapes.learn``) — a reviewer's one click at the shape step, before the shape is
    confirmed — and re-proposes this design's shape with it. Refuses by name, writing nothing, otherwise."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from apps.pipeline.services import learned_shapes
        task = get_object_or_404(DesignTask, id=task_id)
        if task.design_target != "product_container" or task.status != "awaiting_container_profile":
            return Response({"error": learned_shapes.NOT_LEARNABLE,
                             "detail": ["a shape is learned at a design's shape step, before it is confirmed"]},
                            status=status.HTTP_409_CONFLICT)
        try:
            row, created = learned_shapes.learn(task, request.user)
        except learned_shapes.NotLearnable as exc:
            return Response({"error": exc.code, "detail": [exc.reason]}, status=status.HTTP_409_CONFLICT)
        return Response({"learned": {"form": row.form, "kind": row.kind, "variant": learned_shapes.variant_key(row.kind),
                                     "label": row.label, "new": created}})


def _clean_container_profile(profile: dict, archetype: str) -> dict:
    """The shape step's payload, its values typed — the one reading the confirm door and the print areas' proposal
    share (his test day finding 2, 2026-09-29: moved out of ConfirmContainerProfileView unchanged)."""
    clean = {'archetype': archetype}
    for key in ('variant', 'cap_style'):
        if profile.get(key):
            clean[key] = str(profile[key])[:40]
    for key in ('height_mm', 'width_mm', 'depth_mm', 'neck_ratio',
                'cap_width_mm', 'cap_depth_mm', 'cap_height_mm'):
        if profile.get(key) is not None:
            clean[key] = float(profile[key])
    return clean


def _concept_sized(task, spec: dict, archetype: str, clean: dict) -> dict:
    """``clean`` with the height the concept's proportion gives where the form's own starting size gave way to it
    (``concept_proportion_size``) — else as it came."""
    from apps.pipeline.targets.container import concept_proportion_size
    _w, _h, _why = concept_proportion_size(archetype, clean.get('width_mm'), clean.get('height_mm'),
                                           spec.get('container_outline_trace/1.0'), getattr(task, 'task_text', ''))
    return dict(clean, height_mm=_h) if _why is not None else clean


def _container_profile_record(task, spec: dict, archetype: str, profile: dict, clean: dict) -> dict:
    """The profile record the confirm door writes for this payload — built here once, so the print areas the shape
    step is shown are proposed from exactly the record the door will confirm (his test day finding 2, 2026-09-29:
    moved out of ConfirmContainerProfileView unchanged; §BH64(b)'s one source for the numbers)."""
    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.targets.container import concept_proportion_size
    # [His goal after the pitch page, 2026-10-15, A (3): "131 drawn landscape when the concept is portrait"] the form's
    # own starting size, confirmed as it opened, gives way to the concept's proportion — a size his brief declares, or
    # one anybody chose, stands (``concept_proportion_size``); the print areas are proposed for the size it gives
    _w, _h, _why = concept_proportion_size(archetype, clean.get('width_mm'), clean.get('height_mm'),
                                           spec.get('container_outline_trace/1.0'), getattr(task, 'task_text', ''))
    if _why is not None:
        clean = dict(clean, height_mm=_h)
    base = spec.get(cc.PROFILE_SCHEMA) or cc.build_inferred_profile(
        archetype, str(profile.get('variant', '')))
    # 2B-3V UI correction §2: product-record dimensions (incl. depth) are
    # seeded AS RECORDED before the user's review is merged, so a known
    # depth is never silently absent from the contract.
    if task.product is not None:
        base = cc.merge_product_record_dims(base, task.product)
    # promote the reviewed values (concept authority, not manufacturer)
    user_values = {
        'archetype': archetype,
        'variant': str(profile.get('variant', '')) or None,
        'body_width_mm': clean.get('width_mm'),
        'body_depth_mm': clean.get('depth_mm'),
        'body_height_mm': clean.get('height_mm'),
        'neck_ratio': clean.get('neck_ratio'),
        'cap_type': clean.get('cap_style'),
        # provisional cap dimensions (task #51 correction item 1) — the
        # user bounding the optional cap surface for its cap zone
        'cap_width_mm': clean.get('cap_width_mm'),
        'cap_depth_mm': clean.get('cap_depth_mm'),
        'cap_height_mm': clean.get('cap_height_mm'),
    }
    # §2/§5: a value the user left EXACTLY as the product record supplied
    # keeps its PRODUCT_RECORD source — user promotion applies only to
    # actual edits (never a silent source downgrade to USER_VISUAL).
    for name in ('body_width_mm', 'body_depth_mm', 'body_height_mm'):
        recorded = ((base.get('fields') or {}).get(name) or {})
        if (recorded.get('source') == cc.SRC_PRODUCT_RECORD
                and user_values.get(name) is not None
                and float(user_values[name]) == float(recorded.get('value'))):
            user_values[name] = None
    return cc.merge_user_profile(
        base, {k: v for k, v in user_values.items() if v is not None})


class ProposeContainerZonesView(APIView):
    """POST /api/tasks/<task_id>/propose_container_zones/ — the print areas the shape step shows for the sizes it
    shows. [His test day finding 2, 2026-09-29: he set design 117's tube to 180 x 50 mm and the areas beside it stayed
    those proposed from the contract's fallback 100 x 50.] Body: {"profile": …} exactly as the confirm door takes it,
    validated as the door validates it, its record built by the door's own `_container_profile_record`, and the
    proposal returned with each area's hash. Reads only: nothing is written and no state moves."""
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.targets.container import SUPPORTED_ARCHETYPES
        from apps.pipeline.targets.ui import validate_container_profile_payload
        task = get_object_or_404(DesignTask, id=task_id)
        output = task.current_output()
        spec = (output.spec_sheet or {}) if output is not None else {}
        if (task.design_target != 'product_container' or task.status != 'awaiting_container_profile'
                or output is None or spec.get('container_confirmation')):
            return Response({'error': 'PROPOSAL_NOT_AT_THE_SHAPE_STEP',
                             'detail': ['print areas are proposed at a design\'s shape step, before it is confirmed']},
                            status=status.HTTP_409_CONFLICT)
        profile = request.data.get('profile')
        if not isinstance(profile, dict):
            return Response({'error': 'profile must be an object.'}, status=status.HTTP_400_BAD_REQUEST)
        archetype = str(profile.get('archetype') or '').lower()
        if archetype not in SUPPORTED_ARCHETYPES:
            return Response({'error': f'archetype must be one of {list(SUPPORTED_ARCHETYPES)}'},
                            status=status.HTTP_400_BAD_REQUEST)
        problems = validate_container_profile_payload(profile)
        if problems:
            return Response({'error': 'PROFILE_VALIDATION_FAILED', 'detail': problems},
                            status=status.HTTP_400_BAD_REQUEST)
        record = _container_profile_record(task, spec, archetype, profile,
                                           _clean_container_profile(profile, archetype))
        from apps.pipeline.targets.container import proposal_for
        zones = proposal_for(record, spec, output)                 # [his yes of 2026-09-30: from the concept's map]
        for zone in zones:
            zone['zone_hash'] = cc.zone_hash(zone)
        return Response({'zones': zones, 'profile_hash': record['profile_hash']})


#: [his test day finding 2, 2026-09-29: the confirm door's refusal of print areas proposed for other sizes, in words]
ZONES_FOR_OTHER_SIZES_WORDS = ("These print areas were worked out for other sizes. They are shown again for the sizes "
                               "you set — check each one and confirm again. Nothing was saved.")


class ConfirmContainerProfileView(APIView):
    """POST /api/tasks/<task_id>/confirm_container_profile/

    The container target's confirm gate (its answer to ConfirmDimensionsView).
    Validates the confirmed container profile, then reconstructs the editable
    concept sheet. Body: {"profile": {archetype, variant, height_mm, width_mm,
    neck_ratio, cap_style}}.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from apps.pipeline.targets.container import SUPPORTED_ARCHETYPES

        task = get_object_or_404(DesignTask, id=task_id)
        output = task.current_output()
        if not output:
            return Response({'error': 'No container output for this task.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # UI-2A §9: the design target is a hard precondition — a Packaging or
        # Complete Product task must never acquire container-profile records,
        # not even rejected-proposal writes.
        if task.design_target != 'product_container':
            return Response(
                {'error': 'PROFILE_CONFIRMATION_NOT_APPLICABLE',
                 'detail': ['container-profile confirmation applies only to '
                            'Product Container tasks.']},
                status=status.HTTP_409_CONFLICT)

        profile = request.data.get('profile') or {}
        if not isinstance(profile, dict):
            return Response({'error': 'profile must be an object.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # §BH64(c)/§BH61(a): NO DEFAULT. A payload that omitted the
        # archetype became a bottle here, inside a `.get()` default where a
        # search for archetype literals could not see it. Absent is absent.
        archetype = str(profile.get('archetype') or '').lower()
        # AND REMOVING IT EXPOSED WHAT THE DEFAULT WAS CARRYING. An EMPTY body
        # is the documented idempotent RESUME (§2/§6 below, "or the empty
        # resume body"), which names no form because it proposes none — and it
        # was reaching this check and passing it only because the `.get()`
        # invented a bottle, which the mismatch loop below then skipped unread.
        # A resume was being validated as a fresh confirmation of a bottle. An
        # empty body is carried to the resume branch only when there is a
        # confirmation to resume; anything that submits a profile must name its
        # form, and a body that submits nothing with nothing to resume is not a
        # confirmation of anything.
        resuming = (not profile
                    and bool((output.spec_sheet or {}).get(
                        'container_confirmation')))
        if not resuming and archetype not in SUPPORTED_ARCHETYPES:
            # §BH61(a): the stop says which value was missing, not only what
            # the accepted ones are.
            from apps.pipeline.targets.container import archetypes as _declared
            return Response(
                {'error': f'archetype must be one of {list(SUPPORTED_ARCHETYPES)}',
                 'detail': [str(_declared.ArchetypeUnresolved(
                     ["the confirmation payload"],
                     value=profile.get('archetype')))]},
                status=status.HTTP_400_BAD_REQUEST)
        # UI-2A §9: STRICT validation of every provided value — junk numerics
        # were previously ignored; now a bad value is a refusal that creates
        # nothing. Ranges/compatibility come from the one editor catalog.
        from apps.pipeline.targets.ui import (
            PROFILE_AUTHORITY, validate_container_profile_payload)
        problems = validate_container_profile_payload(profile)
        if problems:
            return Response(
                {'error': 'PROFILE_VALIDATION_FAILED', 'detail': problems},
                status=status.HTTP_400_BAD_REQUEST)
        clean = _clean_container_profile(profile, archetype)

        # --- 2B-1 versioned profile + decoration-zone confirmation ---------
        from apps.pipeline.services import container_contract as cc
        spec = output.spec_sheet or {}

        # --- idempotent resume (2B-3V resume-correction §2/§6) --------------
        # A combined confirmation that is already persisted is AUTHORITATIVE:
        # a repeated POST never re-merges, re-hashes, re-records a decision or
        # calls a provider — it resumes reconstruction from the persisted
        # state, exactly once per failure cycle.
        if spec.get('container_confirmation'):
            # UI-2A §10: the confirmed decision is immutable through this
            # endpoint. A DIFFERENT profile is refused with a stable code;
            # only an identical replay (or the empty resume body) may pass
            # through to the idempotent resume below.
            confirmed_rec_now = spec.get(cc.PROFILE_SCHEMA) or {}
            fields_now = confirmed_rec_now.get('fields') or {}

            def _confirmed_value(key):
                mapping = {'cap_style': 'cap_type',
                           'height_mm': 'body_height_mm',
                           'width_mm': 'body_width_mm',
                           'depth_mm': 'body_depth_mm'}
                if key == 'archetype':
                    return confirmed_rec_now.get('archetype')
                if key == 'variant':
                    return (confirmed_rec_now.get('variant')
                            or (fields_now.get('variant') or {}).get('value'))
                return (fields_now.get(mapping.get(key, key)) or {}).get('value')

            mismatches = []
            for key in ('archetype', 'variant', 'cap_style', 'height_mm',
                        'width_mm', 'depth_mm', 'neck_ratio'):
                if key not in profile or profile.get(key) in (None, ''):
                    continue
                confirmed_v = _confirmed_value(key)
                submitted_v = clean.get(key)
                if confirmed_v is None:
                    continue
                try:
                    same = float(submitted_v) == float(confirmed_v)
                except (TypeError, ValueError):
                    same = str(submitted_v) == str(confirmed_v)
                if not same:
                    mismatches.append(key)
            if mismatches:
                return Response(
                    {'error': 'PROFILE_ALREADY_CONFIRMED',
                     'detail': [f'{k} differs from the confirmed profile'
                                for k in mismatches],
                     'combined_hash':
                         spec['container_confirmation']['combined_hash']},
                    status=status.HTTP_409_CONFLICT)

            resume = spec.get('container_resume') or {}

            # UI-2B-2B: retry is REUSE of the persisted decision. The
            # server-side eligibility (same derivation the status payload
            # exposes) is authoritative here — a rendered button is never
            # trusted.
            from apps.pipeline.services import reconstruction_status as rst
            snapshot = rst.build_container_reconstruction_status(task) or {}
            retry_block = snapshot.get('retry') or {}

            confirmed_rec = spec.get(cc.PROFILE_SCHEMA) or {}
            fields = confirmed_rec.get('fields') or {}

            def _fv(name):
                return (fields.get(name) or {}).get('value')

            def _confirmed_clean():
                return {k: v for k, v in {
                    'archetype': confirmed_rec.get('archetype') or archetype,
                    'variant': confirmed_rec.get('variant') or None,
                    'cap_style': _fv('cap_type'),
                    'height_mm': _fv('body_height_mm'),
                    'width_mm': _fv('body_width_mm'),
                    'depth_mm': _fv('body_depth_mm'),
                    'neck_ratio': _fv('neck_ratio'),
                }.items() if v is not None}

            def _dispatch_and_respond(retry_reason=None,
                                      message='Confirmed profile + zones '
                                              'unchanged. Reconstruction '
                                              'resumed.'):
                """Dispatch the persisted decision once, persist the resume
                identity + retry lineage, answer honestly on queue failure.
                Previous failure evidence is retained in
                container_retry_history — never deleted (§7/§17)."""
                import datetime as _dt

                from apps.pipeline.models import AgentLog
                from .tasks import resume_aria_container_profile
                now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
                try:
                    async_result = resume_aria_container_profile.delay(
                        task.id, output.id, _confirmed_clean())
                except Exception:  # noqa: BLE001 — broker down etc.
                    output.refresh_from_db()
                    fspec = output.spec_sheet or {}
                    fspec['generation_error'] = rst.DISPATCH_FAILED
                    output.spec_sheet = fspec
                    output.save(update_fields=['spec_sheet'])
                    return Response({
                        'ok': False, 'task_id': task.id,
                        'error': rst.DISPATCH_FAILED,
                        'message': 'The retry was accepted but the '
                                   'reconstruction job could not be queued. '
                                   'Retry again when the queue recovers.'},
                        status=status.HTTP_502_BAD_GATEWAY)
                output.refresh_from_db()
                nspec = output.spec_sheet or {}
                nspec['container_resume'] = {
                    'celery_task_id': str(getattr(async_result, 'id', '')),
                    'requested_at': now_iso,
                    'requested_by': request.user.username,
                    'kind': 'IDEMPOTENT_RESUME_FROM_PERSISTED_CONFIRMATION',
                    **({'retry_reason': retry_reason} if retry_reason
                       else {}),
                }
                nspec.pop('generation_error', None)
                output.spec_sheet = nspec
                output.save(update_fields=['spec_sheet'])
                if retry_reason:
                    AgentLog.objects.create(
                        task=task, agent_name='ARIA', actor=request.user,
                        action=('ARIA: owner retry dispatched — another '
                                'reconstruction attempt of the confirmed '
                                'profile was queued'),
                        payload={'retry_reason': retry_reason,
                                 'gate_decision_id':
                                     retry_block.get(
                                         'existing_gate_decision_id'),
                                 'profile_hash': retry_block.get(
                                     'confirmed_profile_hash')})
                task.refresh_from_db()
                return Response({
                    'ok': True, 'task_id': task.id,
                    'replayed': retry_reason is None,
                    **({'retry_reason': retry_reason} if retry_reason
                       else {}),
                    'status': task.status,
                    'combined_hash':
                        spec['container_confirmation']['combined_hash'],
                    'resume': nspec['container_resume'],
                    'message': message})

            def _record_retry_history(previous):
                history = list(spec.get('container_retry_history') or [])
                import datetime as _dt
                history.append({
                    'at': _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    'by': request.user.username,
                    'previous_failure': previous,
                    'gate_decision_id':
                        retry_block.get('existing_gate_decision_id'),
                    'profile_hash':
                        retry_block.get('confirmed_profile_hash'),
                })
                spec['container_retry_history'] = history

            if task.status == 'generating_dieline':
                if (spec.get('generation_error') == rst.DISPATCH_FAILED
                        and retry_block.get('eligible')):
                    # §14 exactly-once redispatch: the persisted failure
                    # marker is the compare-and-set token — a concurrent
                    # retry that already cleared it becomes a replay
                    from django.db import transaction as _txn
                    from apps.pipeline.models import PackagingOutput
                    with _txn.atomic():
                        locked = (PackagingOutput.objects
                                  .select_for_update().get(pk=output.pk))
                        lspec = locked.spec_sheet or {}
                        if lspec.get('generation_error') != rst.DISPATCH_FAILED:
                            return Response({
                                'ok': True, 'task_id': task.id,
                                'replayed': True, 'status': task.status,
                                'combined_hash': spec[
                                    'container_confirmation']['combined_hash'],
                                'resume': lspec.get('container_resume') or {},
                                'message': 'A retry was already accepted.'})
                        spec = lspec
                        _record_retry_history(rst.DISPATCH_FAILED)
                        spec.pop('generation_error', None)
                        locked.spec_sheet = spec
                        locked.save(update_fields=['spec_sheet'])
                    output.refresh_from_db()
                    return _dispatch_and_respond(
                        retry_reason=rst.DISPATCH_FAILED,
                        message='Retry accepted — reconstruction queued '
                                'again for the confirmed profile.')
                return Response({
                    'ok': True, 'task_id': task.id, 'replayed': True,
                    'status': task.status,
                    'combined_hash': spec['container_confirmation']['combined_hash'],
                    'resume': resume,
                    'message': 'Reconstruction is already running.'})

            if task.status in ('awaiting_gate_2', 'gate_2_approved',
                               'completed'):
                # a clean completion or an unsafe record is NEVER retryable
                # through this door
                if (retry_block.get('eligible') and retry_block.get(
                        'reason_code') == rst.RETRYABLE_INCONSISTENCY):
                    if not _transition(task.id, task.status,
                                       status='generating_dieline'):
                        return Response(GATE_CONFLICT,
                                        status=status.HTTP_409_CONFLICT)
                    _record_retry_history('INCONSISTENT_COMPLETION')
                    output.spec_sheet = spec
                    output.save(update_fields=['spec_sheet'])
                    return _dispatch_and_respond(
                        retry_reason=rst.RETRYABLE_INCONSISTENCY,
                        message='Retry accepted — the inconsistent result '
                                'is being rebuilt from the confirmed '
                                'profile.')
                # §BH54(d): a STALE, not-yet-accepted result is re-derived from
                # the SAME confirmed profile; its fresh checks decide
                if (retry_block.get('eligible') and retry_block.get(
                        'reason_code') == rst.STALE_REDERIVATION
                        and task.status == 'awaiting_gate_2'):
                    if not _transition(task.id, task.status,
                                       status='generating_dieline'):
                        return Response(GATE_CONFLICT,
                                        status=status.HTTP_409_CONFLICT)
                    _record_retry_history(rst.STALE_REDERIVATION)
                    output.spec_sheet = spec
                    output.save(update_fields=['spec_sheet'])
                    return _dispatch_and_respond(
                        retry_reason=rst.STALE_REDERIVATION,
                        message='Re-derivation accepted — the stale result '
                                'is being rebuilt from the confirmed '
                                'profile; its fresh checks decide.')
                return Response(
                    {'error': 'RETRY_NOT_ELIGIBLE',
                     'detail': [retry_block.get('recovery')
                                or retry_block.get('reason_code')
                                or 'reconstruction is not in a retryable '
                                   'state']},
                    status=status.HTTP_409_CONFLICT)

            was_failure = spec.get('generation_error')
            if not _transition(task.id, 'awaiting_container_profile',
                               status='generating_dieline'):
                return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
            if was_failure:
                _record_retry_history(str(was_failure)[:200])
                output.spec_sheet = spec
                output.save(update_fields=['spec_sheet'])
            return _dispatch_and_respond(
                retry_reason=(rst.WORKER_FAILED if was_failure else None))

        # UI-2A §9: an UNCONFIRMED task must actually be at the profile gate —
        # any other state is refused before a single proposal byte is written.
        if task.status != 'awaiting_container_profile':
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)

        # [his review of 127-132, 2026-10-15, C (3): "the product outline matches the concept"] the size the design is
        # drawn at is the one its record confirms — the concept's proportion where the form's starting size gave way
        # (131 was handed on at its starting 110 x 95 while its record held 123.8)
        clean = _concept_sized(task, spec, archetype, clean)
        record = _container_profile_record(task, spec, archetype, profile, clean)
        # zones: incoming (with per-zone user_confirmation_state) else the
        # persisted PROPOSED set — a proposal is never authority (§12). Reject
        # a malformed payload rather than 500 (§16 boundary).
        incoming = request.data.get('zones')
        if incoming is not None and not isinstance(incoming, list):
            return Response({'error': 'zones must be a list.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if isinstance(incoming, list):
            if not all(isinstance(z, dict) for z in incoming):
                return Response({'error': 'each zone must be an object.'},
                                status=status.HTTP_400_BAD_REQUEST)
            zones = incoming
        else:
            zones = (spec.get(cc.ZONES_SCHEMA) or {}).get('zones') or []
        # §AA WI-R — the spelling is checked HERE, before anything reads the
        # zones, because this is where a zone actually enters: `zones` above is
        # a request body. A zone that names its parent surface `surface` is
        # refused as a malformed payload (§16 boundary: 400, never a 500 from
        # the accessor deeper in), so the one spelling cannot be persisted.
        misspelled = [p for p in (cc.zone_surface_problem(z) for z in zones)
                      if p is not None]
        if misspelled:
            return Response({'error': 'zone surface key not recognised.',
                             'detail': misspelled},
                            status=status.HTTP_400_BAD_REQUEST)
        # Re-derive an UNKNOWN zone curvature from the MERGED profile's
        # surface geometry (task #51 correction item 4): a cap zone stays
        # UNKNOWN (→ projection-review refusal) until the user's provisional
        # cap dimensions bound the surface — then it resolves deterministically
        # server-side, never by client assertion.
        merged_geom = cc.surface_geometry(record)
        for z in zones:
            if (z.get('curvature_type') == cc.CURVATURE_UNKNOWN
                    and cc.zone_surface(z) in merged_geom):
                derived = merged_geom[cc.zone_surface(z)]['curvature']
                if derived != cc.CURVATURE_UNKNOWN:
                    z['curvature_type'] = derived
                    z['zone_hash'] = cc.zone_hash(z)
        for z in zones:
            if 'zone_hash' not in z:
                z['zone_hash'] = cc.zone_hash(z)

        # §BH64(b) THE DOOR. A zone set's numbers are about one profile's
        # surfaces. When the set on this record was not derived from the
        # profile now being confirmed AND no longer fits it, the two disagree
        # and the machine does not pick between them:
        #   · a set still standing as the pipeline's PROPOSAL is re-derived
        #     from the profile about to be written, and the substitution is
        #     named in the refusal (§12 — a proposal is never authority);
        #   · a set a human CONFIRMED is refused BY NAME and nothing at all is
        #     written, because then two human acts disagree and only a human
        #     may settle it.
        # The refusal goes HERE, at the door, before the first write (§BH61(b)).
        _stored_zone_block = spec.get(cc.ZONES_SCHEMA)
        from apps.pipeline.targets.container import proposal_for as _proposal_for
        _proposal = _proposal_for(record, spec, output)          # [his yes of 2026-09-30: from the concept's map]
        # [his test blocker on design 122 at the shape step, 2026-10-08] the areas a refusal hands back carry their own
        # hashes, as every proposal the page is given does — without them the page took every area for a changed one
        # and cleared every tick he had set
        for _z in _proposal:
            _z['zone_hash'] = cc.zone_hash(_z)
        stranded = cc.zone_profile_divergence(_stored_zone_block, zones, record, proposal=_proposal)
        rederived, rederived_from = False, None
        if stranded:
            if any(z.get("user_confirmation_state") == cc.ZONE_USER_CONFIRMED
                   for z in zones):
                return Response(
                    {'error': cc.ZONE_PROFILE_DIVERGED,
                     # his test day finding 2, 2026-09-29: said in words where the page shows a refusal's reason
                     'reason': ZONES_FOR_OTHER_SIZES_WORDS,
                     'detail': stranded + [
                         'these zones were confirmed against a different '
                         'container profile. Confirm the proposal returned '
                         'with this refusal, or restore the dimensions the '
                         'zones were drawn for — nothing has been saved.'],
                     'profile_hash': cc.profile_hash(record),
                     'zone_set_profile_hash':
                         (_stored_zone_block or {}).get('profile_hash'),
                     'zones': _proposal},                                                  # §BH71 (0b)
                    status=status.HTTP_409_CONFLICT)
            # §BH64(b) follow-up: a block written before that commit carries NO
            # `profile_hash`, so guarding the notice on "is not None" silenced it
            # for precisely the blocks that could not say where they came from —
            # the live §BH60 run re-derived output 69 correctly and told nobody.
            # Whether a substitution happened is its own fact, not the presence
            # of a hash.
            rederived = True
            rederived_from = ((_stored_zone_block or {}).get('profile_hash')
                              or cc.ZONE_SET_UNSTAMPED)
            zones = _proposal                                                            # §BH71 (0b)

        code = cc.evaluate_confirmation(record, zones)
        if code is not None:
            # refuse WITHOUT transitioning; surface proposals + the specific
            # §11 validator codes so the Review Board can show which zone
            # failed and why (§13).
            proposals = zones or _proposal                                               # §BH71 (0b)
            if code == cc.PROFILE_CONFIRMATION_REQUIRED:
                detail = cc.profile_is_confirmable(record)
            else:
                detail = cc.validate_zone_set(zones, record) if zones else []
            # keep the set-level state honest against the per-zone states: a
            # user who confirmed zones that then failed sees REVIEW_REQUIRED,
            # not a stale PROPOSED, under the pending-review reason (§13).
            set_state = ("REVIEW_REQUIRED" if any(
                z.get("user_confirmation_state") == cc.ZONE_USER_CONFIRMED
                for z in proposals) else "PROPOSED")
            _exclusions = (spec.get(cc.ZONES_SCHEMA) or {}).get('exclusions')
            spec[cc.PROFILE_SCHEMA] = record
            # §BH64(b): the pair is written by the one writer, so what is
            # stored beside this profile always says it was derived from it.
            spec[cc.ZONES_SCHEMA] = cc.zone_set_record(
                proposals, record, confirmation_state=set_state,
                **({"exclusions": _exclusions} if _exclusions else {}))
            spec['generation_error'] = code
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])
            body = {'error': code, 'detail': detail,
                    'profile_hash': record['profile_hash'],
                    'zones': proposals}
            if rederived:
                # §BH64(b): nothing changes under the user unannounced.
                body['zone_set_rederived'] = {
                    'reason': cc.ZONE_PROFILE_DIVERGED,
                    'was_derived_from': rederived_from,
                    'now_derived_from': record['profile_hash'],
                    'detail': stranded}
            return Response(body, status=status.HTTP_409_CONFLICT)

        # §BH70(1) and his §BD(b), "A clipped brand name never ships": a name that cannot be set across this form's
        # front at the size a name prints is stopped HERE, in words — after every refusal of the contract itself, and
        # before the confirmation writes a byte or anything is drawn.
        from apps.pipeline.targets.container import map_sets_the_name, name_fits_front
        from apps.pipeline.targets.container.silhouettes import ContainerProfile as _Profile
        _confirmed = {n: ((record.get('fields') or {}).get(n) or {}).get('value')
                      for n in ('variant', 'cap_type', 'body_height_mm', 'body_width_mm')}
        _stop = name_fits_front(
            _Profile(archetype=archetype, variant=_confirmed['variant'] or record.get('variant') or None,
                     cap_style=_confirmed['cap_type'],
                     height_mm=float(_confirmed['body_height_mm']) if _confirmed['body_height_mm'] else None,
                     width_mm=float(_confirmed['body_width_mm']) if _confirmed['body_width_mm'] else None),
            spec.get('product_name', ''),
            map_sets_name=map_sets_the_name(spec, output))   # [his go of 2026-10-02: the map sets a vial's name]
        if _stop:
            return Response({'error': _stop['code'], 'reason': _stop['reason'],
                             'detail': [f"{_stop['word']!r} needs {_stop['word_mm']} mm at {_stop['size_pt']:g} pt; "
                                        f"the front is {_stop['front_mm']} mm"]},
                            status=status.HTTP_400_BAD_REQUEST)

        # confirmed: persist records + hashes, THEN transition + enqueue (§9)
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['confirmation_state'] = 'CONFIRMED'
        record['confirmed_at'] = now
        record['confirmed_by'] = request.user.username
        combined = cc.combined_confirmation_hash(record, zones)
        _exclusions = (spec.get(cc.ZONES_SCHEMA) or {}).get('exclusions')
        spec[cc.PROFILE_SCHEMA] = record
        spec[cc.ZONES_SCHEMA] = cc.zone_set_record(
            zones, record, confirmation_state="CONFIRMED",
            confirmed_by=request.user.username, confirmed_at=now,
            # 2C-2E §7: a zone the human EXCLUDED stays excluded through
            # confirmation — the record survives the rebuild
            **({"exclusions": _exclusions} if _exclusions else {}))
        spec['container_confirmation'] = {
            "combined_hash": combined, "confirmed_at": now,
            "confirmed_by": request.user.username,
            # UI-2A §4/§11: the profile's authority level travels with the
            # decision — concept reconstruction input, never supplier geometry
            "authority": PROFILE_AUTHORITY}

        # UI-2A §12: profile persistence, lineage decisions, the state
        # transition and the GateDecision commit or roll back TOGETHER —
        # a database failure leaves no partial gate, and the worker is
        # dispatched only after this block has committed.
        from django.db import transaction as _txn

        class _GateConflict(Exception):
            pass

        try:
            with _txn.atomic():
                spec.pop('generation_error', None)
                output.spec_sheet = spec
                output.save(update_fields=['spec_sheet'])

                # 2C-2E §8: on the selected-concept path the six explicit
                # human confirmation decisions persist with the full selection
                # lineage (contract hash, signed selection event, confirmed
                # hashes). They authorize reconstruction to the Gate-2 review
                # and nothing beyond.
                from apps.pipeline.services import (
                    selected_concept_contract as scc)
                _project = getattr(task, 'project', None)
                if _project is not None and (
                        (_project.metadata or {}).get(scc.META_KEY)):
                    scc.record_confirmation_decisions(
                        output, _project, actor=request.user, now_iso=now,
                        profile_hash=record['profile_hash'],
                        zone_set_hash=cc.zone_set_hash(zones),
                        combined_hash=combined)

                if not _transition(task.id, 'awaiting_container_profile',
                                   status='generating_dieline'):
                    raise _GateConflict()
                gate_decision = _record_decision(
                    task, 'container_profile', 'approve', request.user,
                    notes=f"Confirmed {archetype} + {len(zones)} zones "
                          f"(hash {combined[:12]}) — "
                          f"{cc.PROFILE_SCHEMA} profile "
                          f"{record['profile_hash'][:12]}, "
                          f"authority {PROFILE_AUTHORITY}")
        except _GateConflict:
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)

        # dispatch strictly AFTER the commit above: a queue failure now can
        # roll nothing back — the accepted gate survives, the failure is
        # recorded as the existing actionable task-failure state, and a retry
        # rides the idempotent resume path without a second GateDecision.
        from .tasks import resume_aria_container_profile
        try:
            async_result = resume_aria_container_profile.delay(
                task.id, output.id, clean)
        except Exception:  # noqa: BLE001 — broker down, serialization, …
            output.refresh_from_db()
            spec = output.spec_sheet or {}
            spec['generation_error'] = 'RECONSTRUCTION_DISPATCH_FAILED'
            output.spec_sheet = spec
            output.save(update_fields=['spec_sheet'])
            task.refresh_from_db()
            return Response({
                'ok': True, 'task_id': task.id,
                'gate_decision_id': gate_decision.id,
                'status': task.status, 'combined_hash': combined,
                'authority': PROFILE_AUTHORITY,
                'reconstruction': 'DISPATCH_FAILED',
                'message': 'Profile confirmed and recorded, but the '
                           'reconstruction job could not be queued. Use '
                           'Resume to dispatch it again.'})
        # §3: the resume identity is persisted + returned so the UI and the
        # audit trail can see queued/running/failed/complete instead of a
        # silently-vanishing job. 2C-2E: re-read the spec first — in EAGER
        # mode the resume already ran inline and persisted the full
        # reconstruction; writing the stale in-memory spec would clobber it.
        output.refresh_from_db()
        spec = output.spec_sheet or {}
        spec['container_resume'] = {
            'celery_task_id': str(getattr(async_result, 'id', '')),
            'requested_at': now,
            'requested_by': request.user.username,
            'kind': 'INITIAL_CONFIRMATION',
        }
        output.spec_sheet = spec
        output.save(update_fields=['spec_sheet'])
        task.refresh_from_db()
        return Response({'ok': True, 'task_id': task.id,
                         'gate_decision_id': gate_decision.id,
                         'status': task.status, 'combined_hash': combined,
                         'authority': PROFILE_AUTHORITY,
                         'resume': spec['container_resume'],
                         'message': 'Container profile + zones confirmed. '
                                    'Reconstructing.'})


class ReconstructionArtifactView(APIView):
    """GET /api/tasks/<task_id>/reconstruction-artifact/<role>/ (UI-2B-2A).

    The ONE authorized door to the reconstructed result artifacts. Role (not
    path) selects the artifact: 'ai' is the editable SOURCE OF TRUTH and is
    always served as an attachment with a fixed content type — never inline,
    even though the container .ai is technically PDF-based; 'png' is the
    preview and may render inline (?download=1 switches disposition only).
    Everything else — wrong target, unconfirmed task, unknown role, missing
    object, a stored name escaping the artifact root — is the standard
    non-leaking 404. Serving mutates nothing.
    """
    permission_classes = [IsAuthenticated, IsTeamMember]

    ROLES = {"ai": "design_preview_ai", "png": "design_preview"}

    def get(self, request, task_id, role):
        import os

        from django.core.files.storage import default_storage
        from django.http import FileResponse, Http404

        from apps.pipeline.services.reconstruction_status import (
            ARTIFACT_MEDIA_TYPES,
            build_container_reconstruction_status,
        )

        field_name = self.ROLES.get(role)
        if field_name is None:
            raise Http404
        task = get_object_or_404(DesignTask, id=task_id)
        # applicability rides the SAME derivation the status payload uses —
        # only a confirmed Product Container task with its gate decision may
        # expose reconstruction artifacts at all
        if build_container_reconstruction_status(task) is None:
            raise Http404
        output = task.current_output()
        filefield = getattr(output, field_name)
        if not filefield:
            raise Http404
        name = filefield.name or ""
        root = os.path.realpath(default_storage.path("dielines"))
        try:
            full = os.path.realpath(default_storage.path(name))
        except (ValueError, SuspiciousOperation):
            raise Http404
        if not (full == root or full.startswith(root + os.sep)):
            raise Http404
        if not os.path.exists(full):
            raise Http404
        as_attachment = (role == "ai"
                         or request.GET.get("download") == "1")
        return FileResponse(
            open(full, "rb"),
            content_type=ARTIFACT_MEDIA_TYPES[role],
            as_attachment=as_attachment,
            filename=os.path.basename(name))


class TaskRetryView(APIView):
    """POST /api/tasks/<task_id>/retry/ — recover a failed OR stuck task.

    Milestone 8.2: a crash mid-resume used to strand tasks in intermediate
    statuses with no recovery from the UI. Each retryable status resumes from
    the correct step rather than restarting from scratch:

      failed             → full pipeline re-run (queued) — a design started before
                           directions were planned is refused by name (its old
                           path was removed in the clean-up of 2026-10-04)
      gate_1_approved    → re-run the post-Gate-1 step with the approved image
                           (or back to Gate 1 if no image was approved yet)
      generating_dieline → back to the dimension gate for re-confirmation
                           (confirmed dims are only persisted on success)
      gate_2_approved    → re-run finalization on the packaging output
    """
    permission_classes = [IsAuthenticated]

    RETRYABLE = ('failed', 'gate_1_approved', 'generating_dieline',
                 'gate_2_approved', 'awaiting_gate1_generation_configuration')
    #: the retries that re-queue PAID work (the full pipeline, the post-Gate-1 step, a released generation); the other
    #: two return the task to a gate or finish locally and spend nothing
    SPENDS = ('failed', 'gate_1_approved', 'awaiting_gate1_generation_configuration')

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        current = task.status
        if current not in self.RETRYABLE:
            return Response(
                {'error': f'Task in status "{current}" cannot be retried.'},
                status=status.HTTP_409_CONFLICT,
            )
        if current in ('failed', 'awaiting_gate1_generation_configuration'):    # the two that run the pipeline again
            refusal = _pre_2a_refusal(task)              # the clean-up of 2026-10-04 (E8): by name, nothing moves
            if refusal is not None:
                return refusal
        # [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010)] a
        # step still working is never run again beside itself: 123's Garden Wrap, resumed 14 s into its step, read its
        # map twice — refused in words, nothing moved, until its log has been quiet past its measured time
        from apps.pipeline.step_times import stalled as _stalled
        if current in ('gate_1_approved', 'generating_dieline', 'gate_2_approved') and not _stalled(task):
            return Response({'error': 'It is still working on this step — nothing was started again. If it stops '
                                      'moving, Resume appears here.', 'code': 'STILL_WORKING'},
                            status=status.HTTP_409_CONFLICT)
        if current in self.SPENDS:                       # §BH54(b) (k) 5: before any transition, log row or dispatch
            refusal = _daily_cap_refusal()
            if refusal is not None:
                return refusal
        # 2C-2C-CORR-1 §9: a configuration hold releases only when every
        # generation prerequisite now exists — the gate cannot be bypassed
        # by retrying.
        if current == 'awaiting_gate1_generation_configuration':
            from apps.pipeline.services import gate1_checkpoint as ckpt
            ready, missing = ckpt.generation_prerequisites(task)
            ckpt.record_prerequisites(task, ready, missing)
            if not ready:
                return Response(
                    {'error': 'AWAITING_GATE1_GENERATION_CONFIGURATION',
                     'missing_prerequisites': missing},
                    status=status.HTTP_409_CONFLICT)
            from .tasks import run_aria_pipeline as _rap
            if not _transition(task.id,
                               'awaiting_gate1_generation_configuration',
                               status='queued', error_message=''):
                return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
            AgentLog.objects.create(
                task=task, agent_name='ARIA', actor=request.user,
                action='Gate-1 generation released — prerequisites complete')
            _rap.delay(task.id)
            return Response({'status': 'queued',
                             'message': 'Generation prerequisites complete — '
                                        'task requeued.'})

        from .tasks import run_aria_pipeline, resume_aria_gate1, resume_aria_gate2

        # Audit trail: retries are human-triggered — record who asked
        # (Milestone 11.1).
        AgentLog.objects.create(
            task=task, agent_name='ARIA', actor=request.user,
            action=f'Retry requested by {request.user.username} from status "{current}"',
        )

        if current == 'failed':
            if not _transition(task.id, 'failed', status='queued', error_message=''):
                return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
            run_aria_pipeline.delay(task.id)
            message = 'Task requeued.'

        elif current == 'gate_1_approved':
            image = task.images.filter(is_approved=True).order_by('-created_at').first()
            if image:
                resume_aria_gate1.delay(task.id, image.id)
                message = 'Resuming the post-Gate-1 step.'
            else:
                # Crashed before the approval was recorded — re-approve at Gate 1.
                if not _transition(task.id, 'gate_1_approved', status='awaiting_gate_1'):
                    return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
                message = 'No approved image recorded — please approve again at Gate 1.'

        elif current == 'generating_dieline':
            if not _transition(task.id, 'generating_dieline', status='awaiting_dimensions'):
                return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
            message = 'Back at the dimension gate — re-confirm dimensions to regenerate.'

        else:  # gate_2_approved
            output = task.packaging_outputs.order_by('-created_at').first()
            if not output:
                if not _transition(task.id, 'gate_2_approved', status='awaiting_gate_2'):
                    return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)
                message = 'No packaging output recorded — please approve again at Gate 2.'
            else:
                resume_aria_gate2.delay(task.id, output.id)
                message = 'Resuming finalization.'

        task.refresh_from_db()
        return Response({'status': task.status, 'message': message})


class ImageRedownloadView(APIView):
    """POST /api/images/<image_id>/redownload/ — re-fetch a generated image
    whose local download failed (Milestone 8.6)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, image_id):
        image = get_object_or_404(GeneratedImage, id=image_id)
        if not image.image_url:
            return Response({'error': 'No source URL recorded for this image.'},
                            status=status.HTTP_400_BAD_REQUEST)

        from django.core.files.base import ContentFile
        from .services.round_calls import download_image_bytes
        from .services.pipeline_errors import ImageDownloadError

        try:
            content = download_image_bytes(image.image_url)
        except ImageDownloadError as e:
            return Response(
                {'error': f'Redownload failed: {e}. The source URL may have '
                          f'expired — request a revision at Gate 1 to regenerate.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        image.image_file.save(
            f"task_{image.task_id}_img_{image.id}.png", ContentFile(content), save=False,
        )
        image.download_failed = False
        image.save()

        from .serializers import GeneratedImageSerializer
        return Response(GeneratedImageSerializer(image, context={'request': request}).data)


class ImagePromptUpdateView(APIView):
    """POST /api/images/<image_id>/update_prompt/ — edit a generation prompt
    ahead of an image-only rerun (Milestone 11.3 "Edit & re-run").

    Prompts live on GeneratedImage.prompt_used (there is no separate
    ImagePrompt table); editing is only allowed while the task sits at Gate 1
    and only on current (non-superseded) images.
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, image_id):
        image = get_object_or_404(GeneratedImage, id=image_id)
        prompt = (request.data.get('prompt') or '').strip()
        if not prompt:
            return Response({'error': 'prompt is required'}, status=status.HTTP_400_BAD_REQUEST)
        if image.task.status != 'awaiting_gate_1':
            return Response(
                {'error': 'Prompts can only be edited while the task is awaiting Gate 1.'},
                status=status.HTTP_409_CONFLICT,
            )
        if image.superseded:
            return Response(
                {'error': 'This image is superseded — edit a current image instead.'},
                status=status.HTTP_409_CONFLICT,
            )

        image.prompt_used = prompt
        image.save(update_fields=['prompt_used'])
        AgentLog.objects.create(
            task=image.task, agent_name='ARIA', actor=request.user,
            action=f'Prompt for "{image.direction_name}" edited by {request.user.username}',
        )
        return Response({'id': image.id, 'prompt_used': image.prompt_used})


class RerunImagesView(APIView):
    """POST /api/tasks/<task_id>/rerun_images/ — regenerate images ONLY, from
    the current (possibly edited) prompts. Creative Director and Prompt
    Engineer are skipped. Guarded by the existing revision cap
    (aria.MAX_REVISION_PASSES) so manual reruns can't burn unbounded spend
    (Milestone 11.3).
    """
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        task = get_object_or_404(DesignTask, id=task_id)
        refusal = _daily_cap_refusal()                   # §BH54(b) (k) 5: a re-run is a spend
        if refusal is not None:
            return refusal
        refusal = _revision_refusal(task, allow_resume=True)
        if refusal is not None:
            return refusal
        if not task.images.filter(superseded=False).exists():
            return Response({'error': 'No current images to regenerate from.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not _transition(task.id, 'awaiting_gate_1', status='queued'):
            return Response(GATE_CONFLICT, status=status.HTTP_409_CONFLICT)

        AgentLog.objects.create(
            task=task, agent_name='ARIA', actor=request.user,
            action=f'Image-only rerun requested by {request.user.username}',
        )
        from .tasks import rerun_aria_images
        rerun_aria_images.delay(task.id)
        task.refresh_from_db()
        return Response({'status': task.status,
                         'message': 'Regenerating images from the current prompts.'})


class TaskListPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class TaskListView(ListAPIView):
    """GET /api/tasks/ — paginated (25/page) with status/brand/owner filters
    (Milestone 13.2). Returns the DRF envelope {count,next,previous,results}."""
    permission_classes = [IsAuthenticated, IsTeamMember]
    pagination_class = TaskListPagination

    def get_serializer_class(self):
        from .serializers import TaskListItemSerializer
        return TaskListItemSerializer

    def get_queryset(self):
        qs = DesignTask.objects.select_related('product', 'created_by').order_by('-created_at')
        p = self.request.query_params
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('brand'):
            qs = qs.filter(brand_id=p['brand'])
        if p.get('owner'):
            qs = qs.filter(created_by__username=p['owner'])
        return qs


class SpecSheetDownloadView(APIView):
    """GET /api/tasks/<task_id>/download_spec/ — return the spec-sheet PDF."""
    permission_classes = [IsAuthenticated, IsTeamMember]

    def get(self, request, task_id):
        import os
        from django.http import FileResponse, Http404
        task = get_object_or_404(DesignTask, id=task_id)
        output = task.packaging_outputs.filter(is_final_approved=True).first()
        if not output:
            raise Http404('No approved packaging output for this task')
        if not output.spec_pdf:
            from apps.pipeline.services.spec_sheet import generate_spec_sheet
            generate_spec_sheet(output)
            output.refresh_from_db()
        return FileResponse(
            output.spec_pdf.open('rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=os.path.basename(output.spec_pdf.name),
        )


class ConceptReferenceCandidatesView(APIView):
    """GET /api/tasks/<task_id>/concept_references/ — the material-reference
    selection screen's data (Phase 2A-6E §4).

    Builds/refreshes a bounded candidate set deterministically (no provider
    call) and returns every candidate with its provenance and permission
    state. NOTHING is approved here — approval is the separate POST and is
    always a human action.
    """
    permission_classes = [IsAuthenticated, IsTeamMember]

    def get(self, request, task_id):
        from apps.pipeline.serializers import ConceptReferenceSerializer
        from apps.pipeline.services.concept_references import build_candidates

        task = get_object_or_404(DesignTask, id=task_id)
        # [his goal of 2026-10-06, item 13: "shows only references that match the brief, not unrelated stock"] the
        # candidates this brief matches now, and any he approved — a row offered under the old matching (design 120's
        # sixteen, on "and", "for", "bbrose", and the face powders every design was offered) is not shown again
        current = {r.pk for r in build_candidates(task)}
        rows = [r for r in task.concept_references.all()
                if r.pk in current or r.permission_status == r.PERMISSION_APPROVED]
        plan = getattr(task, 'concept_influence_plan', None)
        return Response({
            'task': task.id,
            'candidates': ConceptReferenceSerializer(
                rows, many=True, context={'request': request}).data,
            'approved_ids': [r.pk for r in rows
                             if r.permission_status ==
                             r.PERMISSION_APPROVED],
            'influence_plan_hash': plan.plan_hash if plan else None,
            'select_between': [2, 4],
        })


class ConceptReferenceApproveView(APIView):
    """POST /api/tasks/<task_id>/concept_references/approve/ {"ids": [...]}
    — the human concept-reference approval (2–4 items). Grants
    USER_APPROVED_FOR_CONCEPT_REFERENCE for THIS task only; never production
    use. Builds material_influence_plan/1.0."""
    permission_classes = [IsAuthenticated, IsTeamMember]

    def post(self, request, task_id):
        from apps.pipeline.services.concept_references import (
            ConceptReferenceError, approve_concept_references)

        task = get_object_or_404(DesignTask, id=task_id)
        # §3 contract (2A-6E-CORR-1): the material screen lives at Gate 1 —
        # approving references for a task in any other state is a stale or
        # misdirected request and refuses with a stable code.
        if task.status != 'awaiting_gate_1':
            return Response(
                {'error': f'Concept-reference approval requires '
                          f'awaiting_gate_1; task is "{task.status}".',
                 'code': 'TASK_STATE_REJECTED'},
                status=status.HTTP_409_CONFLICT)
        try:
            result = approve_concept_references(
                task, request.user, request.data.get('ids') or [])
        except ConceptReferenceError as exc:
            return Response({'error': str(exc), 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        AgentLog.objects.create(
            task=task, agent_name='ARIA', actor=request.user,
            action=(f"Concept references approved by "
                    f"{request.user.username}: "
                    f"{result['approved_ids']} (concept reference only — "
                    f"no production use granted)"),
            payload=result,
        )
        # §3 item 8: return the current per-reference states, so a client
        # can verify persistence instead of inferring it from a 200.
        result['statuses'] = {
            row.pk: row.permission_status
            for row in task.concept_references.all()}
        return Response(result)


class ConceptReferenceThumbnailView(APIView):
    """GET /api/concept_references/<pk>/thumbnail/ — stream a candidate's
    displayable file (read-only; bounded to the candidate's declared root)."""
    permission_classes = [IsAuthenticated, IsTeamMember]

    def get(self, request, reference_id):
        import mimetypes
        from django.http import FileResponse, Http404
        from apps.pipeline.models import ConceptReference
        from apps.pipeline.services.concept_references import (
            reference_file_path)

        row = get_object_or_404(ConceptReference, pk=reference_id)
        path = reference_file_path(row)
        if not path.exists():
            raise Http404('reference file missing')
        # native .ai sources are rendered to a cached PNG preview — the raw
        # source never streams to the browser (2A-6E-CORR-8 §6)
        if path.suffix.lower() in ('.ai', '.pdf'):
            from apps.pipeline.services.ai_style_profile import (
                render_ai_thumbnail)
            thumb = render_ai_thumbnail(
                path, row.library_item_id.replace(':', '_'))
            if thumb is None:
                raise Http404('preview unavailable for this source')
            return FileResponse(open(thumb, 'rb'), content_type='image/png')
        content_type = mimetypes.guess_type(str(path))[0] or 'image/png'
        return FileResponse(open(path, 'rb'), content_type=content_type)


class GenerateHandoffView(APIView):
    """POST /api/tasks/<task_id>/generate_handoff/ — explicitly build the
    native Illustrator handoff package (Phase 2A-8 §14). Never automatic,
    never a replacement for the preview deliverables."""
    permission_classes = [IsAuthenticated, IsReviewer]

    def post(self, request, task_id):
        from apps.pipeline.services.native_handoff import (
            HandoffError, generate_container_native_handoff,
            generate_native_handoff)
        task = get_object_or_404(DesignTask, id=task_id)
        # 2B-4: Product Container targets build the container package from
        # the persisted native reconstruction — explicit, never automatic.
        if task.design_target == 'product_container':
            output = task.current_output()
            if output is None:
                return Response({'error': 'no container output'},
                                status=status.HTTP_409_CONFLICT)
            # VQR-6: the handoff package derives from the editable AI —
            # it must never generate from a merely-truthy FieldFile, a PNG
            # alone, or a technical-intervention state. VQR-2A: an available
            # AI alone is still not enough — handoff readiness additionally
            # requires the visual quality gate to PASS [§BH71 (0a): no measured FAIL]; a failed
            # reconstruction is inspection-only, never a handoff source.
            from apps.pipeline.services.reconstruction_status import (
                build_container_gate2_readiness)
            readiness = build_container_gate2_readiness(task)
            if readiness is None or not readiness.get('handoff_ready'):
                return Response(
                    {'error': 'GATE_2_NOT_READY',
                     'reason_code': (readiness or {}).get('reason_code')
                     or 'RECONSTRUCTION_CONTRACT_MISSING',
                     'visual_quality':
                         (readiness or {}).get('visual_quality')},
                    status=status.HTTP_409_CONFLICT)
            try:
                handoff = generate_container_native_handoff(
                    output, request.user,
                    run_illustrator=bool(request.data.get('run_illustrator')))
            except HandoffError as exc:
                return Response({'error': str(exc), 'code': exc.code},
                                status=status.HTTP_409_CONFLICT)
            return Response(handoff)
        output = task.packaging_outputs.filter(
            dieline_job__isnull=False).order_by("-pk").first()
        if output is None:
            return Response({'error': 'no packaging output with a composed '
                                      'dieline job'},
                            status=status.HTTP_409_CONFLICT)
        try:
            handoff = generate_native_handoff(
                output, request.user,
                run_illustrator=bool(request.data.get('run_illustrator')))
        except HandoffError as exc:
            return Response({'error': str(exc), 'code': exc.code},
                            status=status.HTTP_409_CONFLICT)
        return Response(handoff)


class WebResearchSessionView(APIView):
    """GET /api/web-research/sessions/<session_id>/ — §17 review payload:
    grouped result cards + session summary. Reviewer/Admin or an active
    temporary web-reference reviewer grant."""
    permission_classes = [IsAuthenticated, IsWebReferenceReviewer]

    @staticmethod
    def _strip_paths(value):
        """Quarantine paths never leave the server — recursively drop any
        *path key from payload dicts (§10)."""
        if isinstance(value, dict):
            return {k: WebResearchSessionView._strip_paths(v)
                    for k, v in value.items()
                    if not k.endswith(("path", "pdf", "png", "json"))
                    or k.endswith("_url")}
        if isinstance(value, list):
            return [WebResearchSessionView._strip_paths(v) for v in value]
        return value

    def get(self, request, session_id):
        from apps.pipeline.models import WebResearchSession
        session = get_object_or_404(WebResearchSession, id=session_id)
        groups = {"exact": [], "analog": [], "inspiration": [], "image": []}
        fact_candidates, blocked_sources = [], []
        for s in session.sources.all().order_by("-match_score"):
            card = {
                "source_id": s.id, "title": s.title, "domain": s.domain,
                "url": s.original_url, "resolved_url": s.resolved_url,
                "source_tier": s.source_tier,
                "classification": s.classification,
                "match_score": s.match_score, "facts": s.facts,
                "rights_state": s.rights_state,
                "access_policy_state": s.access_policy_result,
                "robots_result": s.robots_result,
                "http_status": s.http_status, "mime_type": s.mime_type,
                "byte_count": s.byte_count,
                # thumbnails serve only after reference_view_permission —
                # a quarantined byte is not a viewable byte (§14 default-deny)
                "thumbnail_available": bool(
                    s.quarantine_path and s.mime_type.startswith("image/")
                    and s.reference_view_permission),
                "human_review_state": s.human_review_state,
                "provider_input_permission": s.provider_input_permission,
                "warnings": self._strip_paths(s.extraction_warnings),
                "retrieved_at": s.retrieved_at.isoformat(),
                # served ONLY while reference-view is granted; quarantine
                # paths themselves are never exposed
                "thumbnail_url": (
                    f"/api/web-research/sources/{s.id}/thumbnail/"
                    if (s.quarantine_path and s.reference_view_permission
                        and s.mime_type.startswith("image/")) else None),
            }
            groups.setdefault(s.classification, []).append(card)
            fact_candidates.extend(
                {**f, "source_id": s.id} for f in s.facts)
            if s.access_policy_result.startswith(("robots_disallowed",
                                                  "fetch_blocked",
                                                  "pdf_cap")) or \
                    s.human_review_state == "REJECTED":
                blocked_sources.append({
                    "source_id": s.id, "url": s.original_url,
                    "reason": s.access_policy_result or "REJECTED",
                    "human_review_state": s.human_review_state})
        return Response({
            "session_id": session.id, "status": session.status,
            "product_identity": session.product_identity,
            "queries": session.queries,
            "summary": self._strip_paths(session.summary),
            "session_hash": session.session_hash, "groups": groups,
            "fact_candidates": fact_candidates,
            "conflicts": session.summary.get("conflicting_facts", []),
            "blocked_or_rejected": blocked_sources,
            # curated shortlist (groups A-D) once curation has run
            "shortlist": self._strip_paths(
                session.summary.get("curation"))})


class WebSourceDecisionView(APIView):
    """POST /api/web-research/sources/<source_id>/decision/ — §17 explicit,
    independent human decisions. Provider-input approval is SEPARATE from
    reference approval; bulk artwork-reuse enablement does not exist."""
    permission_classes = [IsAuthenticated, IsWebReferenceReviewer]

    DECISIONS = {
        "approve_exact": {"human_review_state": "APPROVED_EXACT",
                          "reference_view_permission": True},
        "approve_analog": {"human_review_state": "APPROVED_ANALOG",
                           "reference_view_permission": True},
        "approve_inspiration": {"human_review_state": "APPROVED_INSPIRATION",
                                "reference_view_permission": True},
        "approve_fact_source": {"human_review_state": "APPROVED_FACT_SOURCE",
                                "fact_source_permission": True},
        "approve_provider_input": {"provider_input_permission": True},
        # reference-view ONLY: lets the human SEE the quarantined bytes in
        # the authenticated UI; classification stays undecided and every
        # other permission stays false
        "approve_reference_view": {"reference_view_permission": True},
        "reject": {"human_review_state": "REJECTED",
                   "reference_view_permission": False},
        "needs_verification": {"human_review_state": "NEEDS_VERIFICATION"},
    }

    def post(self, request, source_id):
        from apps.pipeline.models import WebSourceRecord
        source = get_object_or_404(WebSourceRecord, id=source_id)
        decision = str(request.data.get("decision") or "")
        changes = self.DECISIONS.get(decision)
        if changes is None:
            return Response({"error": "unknown decision",
                             "allowed": sorted(self.DECISIONS)},
                            status=status.HTTP_400_BAD_REQUEST)
        if decision == "approve_provider_input" and \
                source.human_review_state.startswith(("UNREVIEWED",
                                                      "REJECTED")):
            return Response(
                {"error": "WEB_PROVIDER_INPUT_APPROVAL_REQUIRED",
                 "detail": "approve the source as a reference first — "
                           "provider input is a separate, second decision"},
                status=status.HTTP_409_CONFLICT)
        update_fields = list(changes)
        for field, value in changes.items():
            setattr(source, field, value)
        reason = str(request.data.get("reason") or "").strip()
        if decision == "reject" and reason:
            source.extraction_warnings.append(
                {"kind": "rejection_reason", "value": reason[:200]})
            update_fields.append("extraction_warnings")
        source.save(update_fields=update_fields)
        return Response({"source_id": source.id,
                         "human_review_state": source.human_review_state,
                         "reference_view_permission":
                             source.reference_view_permission,
                         "provider_input_permission":
                             source.provider_input_permission})


class WebResearchVisualReviewFileView(APIView):
    """GET /api/web-research/sessions/<id>/visual-review[-corr1]/<kind>/ —
    the generated human-review contact sheet (pdf | png | json). Serves only
    manifest-recorded files; quarantine paths are never exposed."""
    permission_classes = [IsAuthenticated, IsWebReferenceReviewer]
    manifest_key = "visual_review"

    def get(self, request, session_id, kind):
        from pathlib import Path

        from django.http import FileResponse, Http404

        from apps.pipeline.models import WebResearchSession
        session = get_object_or_404(WebResearchSession, id=session_id)
        manifest = (session.summary or {}).get(self.manifest_key) or {}
        content_types = {"pdf": "application/pdf", "png": "image/png",
                         "json": "application/json"}
        if kind not in content_types or not manifest.get(kind):
            raise Http404("no visual-review artifact of that kind")
        path = Path(manifest[kind])
        if not path.is_file():
            raise Http404("visual-review artifact missing")
        return FileResponse(
            open(path, "rb"), content_type=content_types[kind],
            as_attachment=True, filename=path.name)


class WebSourceThumbnailView(APIView):
    """GET /api/web-research/sources/<source_id>/thumbnail/ — the quarantined
    image bytes, served ONLY while the human has granted reference-view
    permission on this source. Never lists or exposes quarantine paths."""
    permission_classes = [IsAuthenticated, IsWebReferenceReviewer]

    def get(self, request, source_id):
        from pathlib import Path

        from django.http import FileResponse, Http404

        from apps.pipeline.models import WebSourceRecord
        source = get_object_or_404(WebSourceRecord, id=source_id)
        if not (source.reference_view_permission and source.quarantine_path
                and source.mime_type.startswith("image/")):
            raise Http404("no viewable image for this source")
        path = Path(source.quarantine_path)
        if not path.is_file():
            raise Http404("no viewable image for this source")
        return FileResponse(open(path, "rb"),
                            content_type=source.mime_type)


def _enqueue_pipeline(task_id):
    """Dispatch after commit, so a task whose references failed never runs."""
    from .tasks import run_aria_pipeline
    run_aria_pipeline.delay(task_id)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def task_reference_file(request, task_id, reference_id):
    """Serve a reference to someone entitled to see it.

    MEDIA_URL would hand the file to anyone who can guess the stored name, so
    references are served here instead. The reference must belong to the task
    in the URL, and the resolved path must stay inside the reference root — a
    row whose stored name was tampered with cannot be used to read something
    else. An unauthorised request gets the project's ordinary 404: whether
    another user's file exists is not something to leak.
    """
    import os

    from django.core.files.storage import default_storage
    from django.http import FileResponse, Http404

    from apps.pipeline import references as refs
    from apps.pipeline.models import TaskReference

    ref = TaskReference.objects.filter(
        id=reference_id, task_id=task_id).select_related("task").first()
    if ref is None:
        raise Http404
    task = ref.task
    owner = task.created_by_id
    if owner and owner != request.user.id and not (
            request.user.is_superuser or request.user.is_staff):
        raise Http404

    name = ref.image.name or ""
    root = os.path.realpath(default_storage.path(refs.STORAGE_ROOT))
    try:
        full = os.path.realpath(default_storage.path(name))
    except (ValueError, SuspiciousOperation):
        raise Http404
    if not (full == root or full.startswith(root + os.sep)):
        raise Http404
    if not os.path.exists(full):
        raise Http404

    download = ref.original_filename or os.path.basename(name)
    # B4b-3A §8: ?download=1 switches ONLY the disposition — inline view vs
    # attachment with the safe original filename. It selects nothing else;
    # the file served is always the one the task/reference pair resolves to.
    as_attachment = request.GET.get("download") == "1"
    return FileResponse(
        open(full, "rb"),
        content_type=ref.media_type or "application/octet-stream",
        as_attachment=as_attachment, filename=refs.sanitise_filename(download))


class DrawingViewsView(APIView):
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (6): "SEE THE DESIGN ON THE PAGE".] The design's drawings
    for the page's viewer: each page of its drawing and each named part of its first, in words, with the pictures'
    addresses (``drawing_views.views_for``)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        from .drawing_views import views_for
        task = get_object_or_404(DesignTask, id=task_id)
        return Response({"views": views_for(task)})


class DrawingPictureView(APIView):
    """[His goal of 2026-10-13, (6).] One page of the design's drawing — or the part of it ``box`` names (mm) — as a
    picture ``w`` px wide, made from the drawing itself and kept once made."""
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id, page):
        from django.http import FileResponse, Http404

        from .drawing_views import MAIN_PX, picture
        task = get_object_or_404(DesignTask, id=task_id)
        try:
            width = int(request.query_params.get("w") or MAIN_PX)
            box = [float(v) for v in request.query_params["box"].split(",")] if request.query_params.get("box") else None
        except (TypeError, ValueError):
            raise Http404("not a view of this drawing")
        if box is not None and len(box) != 4:
            raise Http404("not a view of this drawing")
        path = picture(task, int(page), width, box)
        if path is None:
            raise Http404("no such view of this drawing")
        return FileResponse(open(path, "rb"), content_type="image/png")
