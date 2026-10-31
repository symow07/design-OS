"""§BH54(k) SLICE 2 — THE DESIGN LOOP's views.

History's pages stay GET-only (apps/dashboard/history_views.py). The loop lives here: the page that shows the knobs and
the pictures side by side at full size (a GET that reads the store), and its one control — a POST that renders
an EXPLORATION of a task — the owner's alone (§BH54(i)), spending nothing, writing the exploration store and nothing the
gate reads (apps/dashboard/exploration_render.py). It decides nothing, approves nothing, rejects nothing: a picture to
look at, never a state. A render that cannot be made is refused by name and writes nothing.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.pipeline.models import DesignTask

from . import exploration_render, explorations


def _wants_json(request) -> bool:
    """[The owner's answer to the UI directions of 2026-09-25: the design page is C's — "pick an element and try colours
    and faces from a library that stays open".] That page asks for its answer as JSON (`Accept: application/json`) and
    stays where it is; every other caller is redirected exactly as before."""
    return "application/json" in (request.headers.get("Accept") or "")


@login_required
@require_POST
def exploration_render_view(request, task_id):
    as_json = _wants_json(request)
    refusal = explorations.owner_refusal(request.user)             # §BH54(i): before any byte is read or drawn
    if refusal:
        if as_json:
            return JsonResponse({"refused": refusal.split(":", 1)[0], "why": refusal}, status=403)
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    task = get_object_or_404(DesignTask.objects.select_related("product", "brand"), pk=task_id)
    try:
        knobs = exploration_render.parse_knobs(request.POST)
        slug, picture = exploration_render.render(task, request.user, knobs=knobs)
    except exploration_render.RenderRefused as exc:
        if as_json:
            return JsonResponse({"refused": exc.code, "why": str(exc)}, status=409)
        return HttpResponse(str(exc), status=409, content_type="text/plain; charset=utf-8")
    if as_json:                                                     # the picture's own record, through the one reader
        shown = next((p for p in (explorations.study(slug) or {}).get("pictures") or [] if p["picture"] == picture), {})
        record = shown.get("record") or {}
        return JsonResponse({"study": slug, "picture": picture,
                             "url": "/dashboard/history/explorations/%s/%s.png" % (slug, picture),
                             "what_changed": record.get("what_changed"),
                             "codes": exploration_render.picture_codes(record)})
    if request.POST.get("from_loop"):                               # back to the loop, the new picture beside the first
        first = (explorations.study(slug) or {}).get("pictures") or []
        show = [p["picture"] for p in first[:1] if p["picture"] != picture] + [picture]
        return redirect("/dashboard/history/tasks/%d/loop/?study=%s&%s#%s" % (
            task.pk, slug, "&".join("show=" + s for s in show), picture))
    return redirect("/dashboard/history/explorations/%s/#%s" % (slug, picture))


@login_required
@require_POST
def exploration_accept_view(request, task_id):
    """§BH54(b) (k) 3: ACCEPT OR REJECT BY EYE — the owner's act alone. His identity is the signed-in owner account,
    the time is the server's clock at the click, the sha256 is the one the page showed him, re-hashed against the
    picture's bytes before anything is written. Every refusal is by name and writes nothing."""
    from django.utils import timezone

    from . import owner_channel
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    task = get_object_or_404(DesignTask, pk=task_id)
    study, picture = request.POST.get("study", ""), request.POST.get("picture", "")
    try:
        owner_channel.record_acceptance(
            user=request.user, decided_at=timezone.now(), task=task, study=study, picture=picture,
            picture_sha256=request.POST.get("picture_sha256", ""), decision=request.POST.get("decision", ""),
            note=request.POST.get("note", ""))
    except owner_channel.ChannelRefused as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain; charset=utf-8")
    return redirect("/dashboard/history/tasks/%d/loop/?study=%s&show=%s#acts" % (task.pk, study, picture))


def _typed_copy(post) -> dict:
    """The words a form carries, per piece, as typed — but for the line ends a browser rewrites on submission (CRLF → LF)
    and the blank space around them. Never cut: the copy channel has no character limit (§W1(d))."""
    typed = {}
    for piece in exploration_render.COPY_PIECES:
        raw = str(post.get("copy_" + piece.lower().replace(" ", "_"), ""))
        text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
        if text:
            typed[piece] = text
    return typed


def _back_zone_typed(post) -> dict:
    fields = {k: post.get(k, "") for k in ("back_x", "back_y", "back_width", "back_height")}
    return exploration_render.parse_knobs(fields).get("back_zone") or {}


@login_required
@require_POST
def copy_room_view(request, task_id):
    """§BH54(b) (k) 4: "each piece's room shown as I type." A POST because the words can be long and do not belong in a
    URL; it MEASURES and writes nothing — no row, no store byte."""
    from . import copy_room
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    task = get_object_or_404(DesignTask.objects.select_related("product"), pk=task_id)
    try:
        zone = _back_zone_typed(request.POST)
    except exploration_render.RenderRefused as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain; charset=utf-8")
    return JsonResponse(copy_room.rooms(task, _typed_copy(request.POST), zone))


@login_required
@require_POST
def copy_save_view(request, task_id):
    """§BH54(b) (k) 4: THE COPY CHANNEL's door. Two steps, both his: the first POST SHOWS him exactly the words, their
    sha256 and their room — an over-room piece warned of, never refused — and writes nothing; the second, his click on
    that page, lands them: his account, the server's time at that click, the sha256 the page showed him, re-hashed
    against the words before anything is written. All the pieces of one click land together or none does."""
    from django.db import transaction
    from django.utils import timezone

    from . import copy_room, owner_channel
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    task = get_object_or_404(DesignTask.objects.select_related("product"), pk=task_id)
    typed = _typed_copy(request.POST)
    try:
        if not typed:
            raise owner_channel.ChannelRefused(owner_channel.COPY_REFUSED_NO_WORDS, "no piece was given any words",
                                               owner_channel.COPY_CITE)
        if not request.POST.get("confirm"):
            rooms = copy_room.rooms(task, typed)
            return render(request, "dashboard/history/copy_confirm.html", {
                "task": task, "section": "explorations", "rooms": rooms,
                "pieces": [{"piece": piece, "name": "copy_" + piece.lower().replace(" ", "_"),
                            "sha_name": "sha256_" + piece.lower().replace(" ", "_"), "text": text,
                            "sha256": owner_channel.words_sha256(text), "characters": len(text),
                            "room": (rooms.get("pieces") or {}).get(piece)} for piece, text in typed.items()]})
        now = timezone.now()
        with transaction.atomic():
            for piece, text in typed.items():
                owner_channel.record_copy(
                    user=request.user, typed_at=now, product=task.product, piece=piece, text=text,
                    text_sha256=request.POST.get("sha256_" + piece.lower().replace(" ", "_"), ""))
    except owner_channel.ChannelRefused as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain; charset=utf-8")
    return redirect("/dashboard/history/tasks/%d/loop/#words" % task.pk)


@login_required
@require_GET
def exploration_loop_view(request, task_id):
    """§BH54(k) 2: the knobs, and the pictures side by side at full size. The owner's alone; reads the store."""
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    task = get_object_or_404(DesignTask.objects.select_related("product", "brand"), pk=task_id)
    try:
        standing, cannot = exploration_render.standing_values(task), ""
    except exploration_render.RenderRefused as exc:
        standing, cannot = {}, str(exc)
    prefix = "t%d-loop-" % task.pk
    mine = [s for s in explorations.for_task(task.pk) if s["slug"].startswith(prefix) and not s["refused"]]
    mine.sort(key=lambda s: s["slug"])
    wanted = request.GET.get("study", "")
    study = next((s for s in mine if s["slug"] == wanted), mine[-1] if mine else None)
    pictures = [p for p in (study or {}).get("pictures", []) if not p["refused"]]
    ids = [i for i in request.GET.getlist("show") if any(p["picture"] == i for p in pictures)]
    if not ids:                                                      # the first picture beside the newest
        ids = list(dict.fromkeys([p["picture"] for p in pictures[:1]] + [p["picture"] for p in pictures[-1:]]))
    shown = [dict(p, codes=(p["record"].get("codes_on_the_drawing") or {}).get("front_copy", [])
                  + (p["record"].get("codes_on_the_drawing") or {}).get("back_panel", [])
                  + list(p["record"].get("zone_contract_findings") or []))
             for i in ids for p in pictures if p["picture"] == i]
    source = next((p["record"].get("knobs") or {} for p in pictures if p["picture"] == request.GET.get("from")), {})
    size = "fit" if request.GET.get("size") == "fit" else "full"
    looks = source.get("appearance") or {}
    drafts = source.get("draft_copy") or {}
    from . import copy_room, owner_channel
    # §BH54(b) (k) 4: each piece's room as the page is served (loop.js re-measures as he types), and his words
    rooms = {} if cannot else copy_room.rooms(task, drafts, source.get("back_zone"))
    words = owner_channel.copy_for(task.product)                     # re-verified on this read
    return render(request, "dashboard/history/loop.html", {
        "rooms": rooms, "words": list(words.values()),
        "acts": owner_channel.acts_for(task),                        # §BH54(b) (k) 3: re-verified on this read
        "task": task, "section": "explorations", "status": explorations.EXPLORATION_STATUS, "refusal": cannot,
        # the refusal in the words the design page's Adjust says it in; the loop's own sentence folded beneath
        "refusal_words": _loop_refusal_words(cannot) if cannot else "",
        "standing": standing, "filled": source, "study": study, "shown": shown, "shown_ids": ids, "size": size,
        "size_label": "full size" if size == "full" else "the row's width",
        "earlier": [s["slug"] for s in mine if study and s["slug"] != study["slug"]],
        "appearance": [{"name": f, "label": f.replace("_", " "), "low": lo, "high": hi, "filled": looks.get(f),
                        "standing": (standing.get("appearance") or {}).get(f)}
                       for f, (lo, hi) in exploration_render.APPEARANCE_RANGES.items()],
        "copy": [{"piece": piece, "name": "copy_" + piece.lower().replace(" ", "_"), "filled": drafts.get(piece),
                  "written": words.get(piece), "room": (rooms.get("pieces") or {}).get(piece),
                  "placeholder": (" ".join(words[piece]["text"].split())[:300]
                                  if piece in words and not words[piece]["void"] else
                                  "CONTENT_VERIFICATION_REQUIRED — unwritten; the words are yours to type, here")}
                 for piece in exploration_render.COPY_PIECES]})


@login_required
@require_POST
def design_accept_view(request, task_id):
    """§BH55 Phase 1: HIS ACCEPTANCE OF A GOVERNED DESIGN — the owner's act alone, from the Gate 2 panel. His identity is
    the signed-in owner account, the time is the server's clock at the click, the sha256 is the one the panel showed him,
    re-hashed against the preview's bytes before anything is written. Answers JSON; every refusal is by name and writes
    nothing."""
    from django.utils import timezone

    from apps.ire.container_production_readiness import build_readiness
    from apps.pipeline.models import PackagingOutput

    from . import owner_channel
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    task = get_object_or_404(DesignTask, pk=task_id)
    raw = str(request.POST.get("output_id") or "").strip()
    output = PackagingOutput.objects.filter(pk=int(raw), task=task).first() if raw.isdigit() else None
    try:
        act = owner_channel.record_design_acceptance(
            user=request.user, decided_at=timezone.now(), task=task, output=output,
            preview_sha256_given=request.POST.get("preview_sha256", ""), decision=request.POST.get("decision", ""),
            note=request.POST.get("note", ""))
    except owner_channel.ChannelRefused as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain; charset=utf-8")
    # said plainly, what the act does and does not do: the stage COMPLETES at Gate 2, which reads production readiness
    blocking = build_readiness(dict(act.output.spec_sheet or {})).get("blocking_codes") or [] \
        if (act.output.spec_sheet or {}).get("container_reconstruction") else []
    return JsonResponse({
        "decision": act.decision, "decided_by": act.decided_by.get_username(), "decided_at": act.decided_at.isoformat(),
        "preview_sha256": act.preview_sha256, "act_id": act.pk,
        "next": ("Your decision is recorded — your account, the time and the picture's sha256. "
                 + (("The stage completes at Gate 2, which production readiness still refuses (%d codes); the project "
                     "does not move to its next stage until that is resolved." % len(blocking))
                    if act.decision == "ACCEPTED" and blocking else ""))})


def _loop_refusal_words(text: str) -> str:
    """The loop's refusal in the words the design page's Adjust says it in (apps/dashboard/views.py)."""
    from apps.dashboard.views import _refusal_words
    return _refusal_words(text)
