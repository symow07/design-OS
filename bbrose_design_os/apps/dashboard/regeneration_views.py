"""Browser-independent Gate-1 regeneration control (Phase 2A-6E-CORR-4).

Three rounds of client-side fixes could not make the regeneration click work
in the user's actual browser. The essential workflow is now standard
server-rendered HTML — it works with JavaScript completely disabled:

    GET  /dashboard/tasks/<id>/gate1-regeneration/confirm/   confirmation page
    POST /dashboard/tasks/<id>/gate1-regeneration/confirm/   confirmed action
    GET  /dashboard/tasks/<id>/gate1-regeneration/jobs/<id>/ status page

The GET validates everything and renders the confirmation (zero provider
calls, no job). The POST re-validates against CURRENT database state — the
browser's hidden fields are never authority; they travel inside a signed,
expiring confirmation token that must still MATCH the database at submit
time. Dry-run mode (GATE1_REGENERATION_MODE=dry_run, the active default)
renders DRY_RUN_ACCEPTED server-side and creates nothing; live mode creates
or reuses THE ONE active job (POST/Redirect/GET) and the status page
refreshes with a plain link. Every failure renders a visible error page with
a stable code — never a blank page, never the console.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.pipeline.models import (
    AgentLog,
    ConceptReference,
    CreativeBrief,
    DesignTask,
    Gate1RegenerationJob,
)
from apps.pipeline.permissions import ROLE_ADMIN, ROLE_REVIEWER, user_has_role
from apps.pipeline.services.gate1_regeneration import VARIATION_IDENTITIES

_TOKEN_SALT = "gate1-regeneration-confirm"
_TOKEN_MAX_AGE = 900          # 15 minutes

#: §7 variation descriptions rendered on the confirmation page.
VARIATION_DESCRIPTIONS = (
    ("A — Editorial Panel", "asymmetric secondary color panel with a "
     "controlled micro-pattern; blush / ivory / rose-gold; ~15% coverage"),
    ("B — Layered Type Field", "layered product typography over one tonal "
     "block; contour or radiance system; ~15-20% coverage"),
    ("C — Powder Constellation", "corner-led powder-particle constellation "
     "with selective panel continuation; peach / mint / warm ivory; "
     "~15-20% coverage"),
)


# [the owner's answer to the UI directions of 2026-09-25: these pages are in the one shell and say themselves in words —
# his goal's (d), "Plain words everywhere. No engine codes on screen." Each stable code keeps its page; its words are
# what the page says, the code and the record's own sentence folded under "What the record says".]
#: each refusal's code, in the words the page says
REGEN_WORDS = {
    "TASK_STATE_REJECTED": "This design is not at choosing its concept, so its concepts cannot be drawn again now.",
    "SELECTED_DIRECTION_MISSING": "No direction is chosen for this design yet — choose one first.",
    "APPROVED_REFERENCES_MISSING": "At least two approved references are needed — approve them on the design's page "
                                   "first.",
    "INFLUENCE_PLAN_NOT_FOUND": "The approved references have not been read into a plan yet — approve them on the "
                                "design's page first.",
    "REFERENCE_FILE_MISSING": "A reference you approved is missing from this machine, so drawing would fail.",
    "AUTHORIZATION_REJECTED": "Only a reviewer or an admin may draw a design's concepts again.",
    "DRY_RUN_VALIDATION_FAILED": "This confirmation has run out, or no longer matches the design — open the page "
                                 "again.",
    "REFERENCE_APPROVAL_CHANGED": "The references approved for this design changed after the page was opened — look "
                                  "again and confirm.",
    "INFLUENCE_PLAN_HASH_MISMATCH": "What the references were read into changed after the page was opened — look "
                                    "again and confirm.",
}
#: a drawing job's state, in words
JOB_WORDS = {"queued": "Waiting its turn", "running": "Being drawn", "completed": "Drawn",
             "failed": "Not drawn"}


class RegenerationValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _validate(task):
    """The full regeneration contract against CURRENT database state.
    Returns (direction_id, approved_rows, plan). Raises with a stable code."""
    if task.status != "awaiting_gate_1":
        raise RegenerationValidationError(
            "TASK_STATE_REJECTED",
            f"Task #{task.pk} is '{task.status}' — regeneration requires "
            f"awaiting_gate_1.")
    brief = CreativeBrief.objects.filter(task=task).first()
    direction_id = (brief.selected_direction_id or "") if brief else ""
    if not direction_id:
        raise RegenerationValidationError(
            "SELECTED_DIRECTION_MISSING",
            "No direction is selected for this task.")
    approved = list(ConceptReference.objects.filter(
        task=task,
        permission_status=ConceptReference.PERMISSION_APPROVED)
        .order_by("pk"))
    if len(approved) < 2:
        raise RegenerationValidationError(
            "APPROVED_REFERENCES_MISSING",
            f"{len(approved)} approved concept reference(s); at least 2 are "
            "required. Approve references on the dashboard first.")
    plan = getattr(task, "concept_influence_plan", None)
    if plan is None:
        raise RegenerationValidationError(
            "INFLUENCE_PLAN_NOT_FOUND",
            "No influence plan exists — approve references first.")
    from apps.pipeline.services.concept_references import reference_file_path
    missing = [row.pk for row in approved
               if not reference_file_path(row).exists()]
    if missing:
        raise RegenerationValidationError(
            "REFERENCE_FILE_MISSING",
            f"Approved reference file(s) missing on disk for id(s) "
            f"{missing} — regeneration would fail.")
    return direction_id, approved, plan


def _direction_name(task, direction_id):
    brief = CreativeBrief.objects.filter(task=task).first()
    if brief:
        for direction in (brief.directions or []):
            if direction.get("direction_id") == direction_id:
                return direction.get("name", direction_id)
    return direction_id


def _token_payload(user, task, direction_id, approved, plan):
    return {"u": user.pk, "t": task.pk, "d": direction_id,
            "r": sorted(row.pk for row in approved), "p": plan.plan_hash}


def _reviewer_required(request):
    if not user_has_role(request.user, ROLE_REVIEWER, ROLE_ADMIN):
        return render(request, "dashboard/gate1_regeneration_error.html", {
            "code": "AUTHORIZATION_REJECTED",
            "message": "Only Reviewers or Admins may run Gate-1 "
                       "regeneration.",
            "words": REGEN_WORDS["AUTHORIZATION_REJECTED"],
            "task_id": None,
        }, status=403)
    return None


def _error(request, task, exc, status=409):
    return render(request, "dashboard/gate1_regeneration_error.html", {
        "code": exc.code, "message": str(exc), "task_id": task.pk,
        "words": REGEN_WORDS.get(exc.code, str(exc)),
    }, status=status)


@login_required
def gate1_regeneration_confirm(request, task_id):
    """GET: the server-rendered confirmation page. POST: the confirmed
    action. Both work with JavaScript disabled."""
    denied = _reviewer_required(request)
    if denied:
        return denied
    task = get_object_or_404(DesignTask, pk=task_id)
    mode = getattr(settings, "GATE1_REGENERATION_MODE", "dry_run")
    if mode == "live":
        from apps.pipeline.services.gate1_regeneration import (
            GateRegenerationError, ensure_reference_refresh_enabled)
        try:
            ensure_reference_refresh_enabled()
        except GateRegenerationError as exc:
            return _error(request, task, RegenerationValidationError(exc.code, str(exc)))

    active = (Gate1RegenerationJob.objects
              .filter(task=task,
                      status__in=Gate1RegenerationJob.ACTIVE_STATUSES)
              .first())

    if request.method == "GET":
        if active is not None:
            return redirect("dashboard:gate1_regeneration_status",
                            task_id=task.pk, job_id=active.pk)
        try:
            direction_id, approved, plan = _validate(task)
        except RegenerationValidationError as exc:
            return _error(request, task, exc)
        token = signing.dumps(
            _token_payload(request.user, task, direction_id, approved, plan),
            salt=_TOKEN_SALT)
        # §8: a previously failed attempt is shown with its exact error, and
        # this page IS the reviewable retry — submitting starts a NEW job.
        last_failed = (Gate1RegenerationJob.objects
                       .filter(task=task,
                               status=Gate1RegenerationJob.STATUS_FAILED)
                       .order_by("-id").first())
        return render(request, "dashboard/gate1_regeneration_confirm.html", {
            "task": task,
            "direction_id": direction_id,
            "direction_name": _direction_name(task, direction_id),
            "approved": approved,
            "plan_hash": plan.plan_hash,
            "variations": VARIATION_DESCRIPTIONS,
            "mode": mode,
            "token": token,
            "last_failed_job": last_failed,
        })

    # ---- POST: re-validate everything against the database ----------------
    if active is not None:
        # idempotency: a resubmitted/reloaded form reuses the active job
        return redirect("dashboard:gate1_regeneration_status",
                        task_id=task.pk, job_id=active.pk)
    try:
        direction_id, approved, plan = _validate(task)
    except RegenerationValidationError as exc:
        return _error(request, task, exc)
    try:
        payload = signing.loads(request.POST.get("confirmation_token", ""),
                                salt=_TOKEN_SALT, max_age=_TOKEN_MAX_AGE)
    except signing.BadSignature:
        return _error(request, task, RegenerationValidationError(
            "DRY_RUN_VALIDATION_FAILED",
            "The confirmation token is missing, invalid or expired — "
            "reopen the confirmation page."), status=400)
    current = _token_payload(request.user, task, direction_id, approved, plan)
    if payload.get("r") != current["r"]:
        return _error(request, task, RegenerationValidationError(
            "REFERENCE_APPROVAL_CHANGED",
            "The approved reference set changed after the confirmation page "
            "was opened — review and confirm again."))
    if payload.get("p") != current["p"]:
        return _error(request, task, RegenerationValidationError(
            "INFLUENCE_PLAN_HASH_MISMATCH",
            "The influence plan changed after the confirmation page was "
            "opened — review and confirm again."))
    if payload.get("d") != current["d"] or payload.get("t") != task.pk \
            or payload.get("u") != request.user.pk:
        return _error(request, task, RegenerationValidationError(
            "DRY_RUN_VALIDATION_FAILED",
            "The confirmation does not match the current task state — "
            "reopen the confirmation page."))

    if mode != "live":
        diagnostic_id = uuid.uuid4().hex[:12]
        AgentLog.objects.create(
            task=task, agent_name="ARIA", actor=request.user,
            action=(f"Dry-run regeneration diagnostic {diagnostic_id} "
                    f"accepted for {request.user.username} via the "
                    f"server-rendered confirmation — no job, no provider "
                    f"call"),
            payload={"diagnostic_request_id": diagnostic_id,
                     "reference_ids": current["r"],
                     "influence_plan_hash": plan.plan_hash,
                     "direction_id": direction_id,
                     "variation_identities": VARIATION_IDENTITIES},
        )
        return render(request,
                      "dashboard/gate1_regeneration_dry_run.html", {
                          "task": task,
                          "diagnostic_id": diagnostic_id,
                          "direction_id": direction_id,
                          "direction_name": _direction_name(task,
                                                            direction_id),
                          "approved_ids": current["r"],
                          "plan_hash": plan.plan_hash,
                          "variations": VARIATION_DESCRIPTIONS,
                          "timestamp": timezone.now(),
                      })

    # live mode: exactly one job, enqueue once, POST/Redirect/GET
    from apps.pipeline.services.gate1_regeneration import (
        GateRegenerationError, request_gate1_regeneration)
    try:
        result = request_gate1_regeneration(task, request.user)
    except GateRegenerationError as exc:
        return _error(request, task, RegenerationValidationError(
            exc.code, str(exc)))
    return redirect("dashboard:gate1_regeneration_status",
                    task_id=task.pk, job_id=result["job_id"])


@login_required
def gate1_regeneration_status(request, task_id, job_id):
    """Server-rendered job status with a plain refresh link — no JavaScript
    required."""
    denied = _reviewer_required(request)
    if denied:
        return denied
    task = get_object_or_404(DesignTask, pk=task_id)
    job = get_object_or_404(Gate1RegenerationJob, pk=job_id, task=task)
    return render(request, "dashboard/gate1_regeneration_status.html", {
        "task": task, "job": job, "now": timezone.now(), "job_words": JOB_WORDS.get(job.status, job.status),
    })
