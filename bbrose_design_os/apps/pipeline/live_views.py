"""Live updates (Milestone 13.2).

* ``task_events`` — a Server-Sent Events stream of status changes + new
  AgentLog rows for one task. A StreamingHttpResponse generator polling the DB
  once a second is the simplest thing that works with the current sync
  gunicorn + Postgres deploy (no extra broker). It closes as soon as the task
  leaves a "working" status (a gate/terminal state), so a worker is only held
  while ARIA is actively running; the client reopens it on the next run.
* [``stats`` — the old dashboard brain panel's cached status counts at
  /api/stats/ — left with that panel in the clean-up of 2026-10-04.]
"""
from __future__ import annotations

import json
import time

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse

from apps.pipeline.models import DesignTask

# Statuses where ARIA is actively working — THE list: static/js/api.js's WORKING_STATUSES is held equal to it by a test
# (apps/pipeline/tests/test_live_moves_on.py). The stream stays open while the task is in one of these; anything else is
# a gate or terminal state the human must act on, so the stream settles + closes.
# [His goal of 2026-10-06, item 2: "Today I had to refresh to see the trend pictures and thought it was still working."]
# The trend review is one: its window closes by itself, and the page's list has carried it since §BH71 PART 2 — this one
# did not, so the stream settled at the trend board and nothing told the page when the window closed.
WORKING_STATUSES = (
    "running", "queued", "awaiting_trend_review", "gate_1_approved", "generating_dieline", "gate_2_approved",
)
_WORKING_STATUSES = set(WORKING_STATUSES)
_SSE_MAX_SECONDS = 300
_SSE_POLL_SECONDS = 1.0
_PING_EVERY = 15   # loop iterations between visible ping events (~15s)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _event_stream(task_id, last_log_id, max_seconds=_SSE_MAX_SECONDS,
                  poll_seconds=_SSE_POLL_SECONDS):
    """Generator yielding SSE frames. Extracted so tests can drive it directly
    (a task already in a settled state yields status + settled and returns,
    without blocking)."""
    last_status = None
    deadline = time.monotonic() + max_seconds
    # Real `ping` events (not SSE comments): EventSource JS cannot observe
    # comment heartbeats, so the client's stall watchdog needs a visible event
    # to know the stream is alive behind buffering proxies (hardening
    # 2026-07-04). Emitted every _PING_EVERY loop iterations (~15s).
    ping_countdown = 0
    yield ": connected\n\n"
    yield _sse("ping", {"t": int(time.time())})
    while time.monotonic() < deadline:
        # NB: the connection is deliberately kept for the life of the stream
        # (we query every second); do not close_old_connections() here — it
        # would drop the connection this request is using.
        task = DesignTask.objects.filter(id=task_id).only("id", "status").first()
        if task is None:
            yield _sse("error", {"detail": "task not found"})
            return
        if task.status != last_status:
            last_status = task.status
            yield _sse("status", {"status": task.status})
        new_logs = (
            DesignTask.objects.get(id=task_id).logs
            .filter(id__gt=last_log_id).order_by("id")
            .values("id", "agent_name", "action", "level")
        )
        for lg in new_logs:
            last_log_id = lg["id"]
            yield _sse("log", lg)
        if last_status not in _WORKING_STATUSES:
            # Gate or terminal state — the client refetches full state and the
            # stream closes; it reopens when the next working phase begins.
            yield _sse("settled", {"status": last_status})
            return
        ping_countdown -= 1
        if ping_countdown <= 0:
            yield _sse("ping", {"t": int(time.time())})
            ping_countdown = _PING_EVERY
        time.sleep(poll_seconds)


def _team_member_required(request):
    """403 JsonResponse for roleless accounts (hardening 2026-07-04) — the
    function-view mirror of the DRF IsTeamMember permission."""
    from apps.pipeline.permissions import ALL_ROLES, user_has_role
    if not user_has_role(request.user, *ALL_ROLES):
        return JsonResponse(
            {"error": "Your account has no role — ask an admin to add you "
                      "to a team role."},
            status=403,
        )
    return None


@login_required
def task_events(request, task_id):
    denied = _team_member_required(request)
    if denied:
        return denied
    last_log_id = int(request.GET.get("last_log_id", 0) or 0)
    response = StreamingHttpResponse(
        _event_stream(task_id, last_log_id),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"   # disable nginx buffering
    return response


def where_of(task) -> dict:
    """[His goal of 2026-10-06, item 2: "When a step finishes in the background ... the open design page switches to
    the next screen on its own, without me pressing refresh."] What an open page needs to know it must move on, cheaply:
    the design's status, a version of what its screen shows — its status, its current pictures, its latest output and
    that output's drawing — and, for a stage of a Complete Product, the stage after it once there is one. The page
    holds the version it drew (``TaskStatusView`` carries the same) and redraws when it changes; a version moved by his
    own clicks (a tick, a note) is not here, so nothing he is typing is redrawn away."""
    output = task.packaging_outputs.order_by("-id").only("id", "design_preview").first()
    pictures = task.images.filter(superseded=False).count()
    version = "%s|%d|%s|%s" % (task.status, pictures, output.pk if output else "",
                               (output.design_preview.name or "") if output else "")
    later = None
    if task.project_id:
        later = (DesignTask.objects.filter(project_id=task.project_id, pk__gt=task.pk).order_by("pk")
                 .values_list("pk", flat=True).first())
    return {"status": task.status, "version": version, "next_task_id": later}


@login_required
def task_where(request, task_id):
    """``where_of`` for one design, as the open page asks it while the design waits at a step of his."""
    denied = _team_member_required(request)
    if denied:
        return denied
    task = DesignTask.objects.filter(id=task_id).first()
    if task is None:
        return JsonResponse({"error": "task not found"}, status=404)
    response = JsonResponse(where_of(task))
    response["Cache-Control"] = "no-store"
    return response
