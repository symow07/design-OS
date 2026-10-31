"""§BH52(b) SLICE 1 — HISTORY pages. Read-only, server-rendered, reached from the dashboard's navigation.

Every view here is GET-only behind the login the dashboard already uses. None carries the audit-writing
enforcement, none links a control that decides, approves, rejects or spends, and none calls a GET that writes.
The data comes from apps/dashboard/history.py, which reads rows and never writes one.
"""
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.pipeline.models import DesignProject, DesignTask

from apps.dashboard.words import target_words

from . import exploration_render, explorations, history

_PARAMS = ("q", "target", "status", "product", "from", "to", "renders", "rejections", "order", "mine", "brand")


def _params(request):
    return {k: request.GET.get(k, "") for k in _PARAMS}


#: the states a designer finds a design by, in the board's own words
STATE_FILTERS = (("waiting", "Waiting for you"), ("attention", "Needs attention"), ("working", "Working on it"),
                 ("stuck", "Can't move on here"), ("tried_again", "Tried again"), ("finished", "Finished"))
#: a tile's tag where its state, not its next step, says it (a waiting design's tag is its next step)
STATE_TAGS = {"attention": "Needs attention", "stuck": "Can't move on here", "working": "Working on it",
              "finished": "Finished", "tried_again": "Tried again"}
#: a state's tag in the one set of tag colours (static/css/bbrose.css .tag)
TAG_CLASS = {"working": "run", "waiting": "wait", "attention": "attn", "stuck": "still", "finished": "done",
             "tried_again": "still", "folded": "line"}


#: what a Designs tile is found by over the rounds (the owner's goal of 2026-10-29): its words, where it stands, its dates,
#: the order and whether this account started it (an admin sees every round) — the old tasks' kind, product, brand,
#: record state, renders, rejections and test fold went with them
ROUND_PARAMS = ("q", "from", "to", "order", "mine")
ROUND_STATE_FILTERS = tuple(row for row in STATE_FILTERS if row[0] != "tried_again")


def _day(value):
    from datetime import date
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None                                   # a date the record cannot hold is left out, never a fault


@login_required
@require_GET
def history_index(request):
    """DESIGNS — C's (his pick of the executor's options, a691f56: "starting a design, the library and history are
    C's"): every design, newest first, by month, each a tile saying where it stands and opening its own page, found by
    its words or where it stands, and — folded — by date or order. Since the owner's goal of 2026-10-29 ("Keep Home,
    Designs and Library, switched to the chain engines") the designs are the chain's rounds, classified as Home
    classifies them (apps/dashboard/views.py, round_card); a retired round is not a design here (the round list says
    what it was), and the old tasks keep their record pages under /history/tasks/ and /designs/<id>/."""
    import json

    from apps.dashboard.views import STATE_ICON, round_card, your_rounds
    params = {k: (request.GET.get(k) or "").strip()[:120] for k in ROUND_PARAMS}
    state = request.GET.get("state") or ""
    words = params["q"].lower()
    start, end = _day(params["from"]), _day(params["to"])
    view = []
    for record in your_rounds(request.user):
        c = round_card(record)
        if c["state"] == "folded" or (state and c["state"] != state):
            continue
        if params["mine"] == "1" and record.created_by_id != request.user.pk:
            continue
        if words and words not in json.dumps(record.product_brief, ensure_ascii=False).lower():
            continue
        day = record.created_at.date()
        if (start and day < start) or (end and day > end):
            continue
        c = dict(c, url=c["page_url"], tag_class=TAG_CLASS.get(c["state"], "line"),
                 tag=c["action"] if c["state"] == "waiting" else STATE_TAGS.get(c["state"]) or c["action"])
        view.append(c)
    if params["order"] == "oldest":
        view.reverse()
    months, by = [], {}
    for c in view:
        key = c["created"].strftime("%B %Y")
        if key not in by:
            by[key] = {"month": key, "tiles": []}
            months.append(by[key])
        by[key]["tiles"].append(c)
    return render(request, "dashboard/history/list.html", dict(
        section="tasks", months=months, shown=len(view), q=params["q"], params=params, order=params["order"],
        state=state, state_filters=ROUND_STATE_FILTERS, state_icon=STATE_ICON,
        more_open=any(params[k] for k in ("from", "to", "order"))))


@login_required
@require_GET
def history_task(request, task_id):
    task = get_object_or_404(DesignTask.objects.select_related("product", "brand", "project"), pk=task_id)
    # §BH54(i): the owner sees the task's explorations; another account sees the refusal by name, never the pictures
    refusal = explorations.owner_refusal(request.user)
    return render(request, "dashboard/history/task.html",
                  dict(history.task_view(task, request.user), section="tasks",
                       explorations=[] if refusal else explorations.for_task(task.pk),
                       explorations_refusal=refusal,
                       # [2026-09-25, (d) "No engine codes on screen": each refusal in words, its own sentence folded]
                       explorations_refusal_words=_exploration_refusal_words(refusal) if refusal else "",
                       # §BH54(k): the loop's control — the owner's alone, and only where a render can be made
                       explore={} if refusal else _explore_offer(task),
                       # §BH69(2): "Uploaded pictures are kept with the design so I can see them later"
                       inspiration=_inspiration_record(request, task)))


def _inspiration_record(request, task) -> dict:
    """A design's inspiration pictures on its record, as its own page draws them — never with the box that adds one."""
    from apps.dashboard.views import _inspiration_kept
    return _inspiration_kept(request, task, {})


def _explore_offer(task) -> dict:
    """The loop's control on the record page, and why not in the design page's Adjust words where it cannot render."""
    offer = exploration_render.explorable(task)
    if offer.get("reason"):
        from apps.dashboard.views import _refusal_words
        offer = dict(offer, reason_words=_refusal_words(offer["reason"]))
    return offer


def _exploration_refusal_words(refusal: str) -> str:
    """Why this account sees no exploration, in words (explorations.owner_refusal's codes)."""
    if refusal.startswith(explorations.EXPLORATIONS_OWNER_UNSET):
        return "No owner account is named on this machine, so no exploration is shown to anyone."
    return "Explorations are shown to the owner's account alone — this account does not see them."


@login_required
@require_GET
def history_projects(request):
    return render(request, "dashboard/history/projects.html",
                  {"projects": DesignProject.objects.order_by("-created_at"), "section": "projects"})


@login_required
@require_GET
def history_project(request, project_id):
    project = get_object_or_404(DesignProject, pk=project_id)
    return render(request, "dashboard/history/project.html", dict(history.project_view(project), section="projects"))


@login_required
@require_GET
def history_dieline_jobs(request):
    return render(request, "dashboard/history/dieline_jobs.html", {"jobs": history.dieline_jobs(), "section": "jobs"})


@login_required
@require_GET
def history_concepts(request):
    params = _params(request)
    return render(request, "dashboard/history/concepts.html",
                  {"images": history.concept_grid(params), "params": params, "section": "concepts",
                   "targets": [(t, target_words(t))            # §BH55 Phase 3: what each design is, in words
                               for t in sorted(set(DesignTask.objects.values_list("design_target", flat=True)))]})


# §BH52(b): the explorations of (a), in history as explorations — read from the store outside every governed root,
# each picture served only while its record carries the one exploration status and claims no state.
# §BH54(i): served to the owner account only — the refusal, by name, comes before any store byte is read.

@login_required
@require_GET
def history_explorations(request):
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    return render(request, "dashboard/history/explorations.html",
                  {"studies": explorations.studies(), "status": explorations.EXPLORATION_STATUS,
                   "outside": explorations.store_is_outside_governed_roots(), "section": "explorations"})


@login_required
@require_GET
def history_exploration_study(request, study):
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    found = explorations.study(study) if explorations.store_is_outside_governed_roots() else None
    if found is None:
        raise Http404(study)
    return render(request, "dashboard/history/exploration_study.html",
                  {"study": found, "status": explorations.EXPLORATION_STATUS, "section": "explorations"})


@login_required
@require_GET
def history_exploration_picture(request, study, picture):
    refusal = explorations.owner_refusal(request.user)
    if refusal:
        return HttpResponseForbidden(refusal, content_type="text/plain; charset=utf-8")
    path = explorations.picture_file(study, picture)
    if path is None:
        raise Http404(picture)
    return FileResponse(open(path, "rb"), content_type="image/png")
