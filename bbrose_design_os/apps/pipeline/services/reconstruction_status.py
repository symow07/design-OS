"""Container reconstruction status — one derived, read-only snapshot (UI-2B-1).

``container_reconstruction_status/1.0`` normalizes the EXISTING lifecycle
records — task status, ``container_resume`` dispatch identity,
``generation_error``, the worker's persisted AgentLog milestones and the
recorded artifacts — into four owner-facing coarse states. Nothing here
mutates, enqueues, retries or calls a provider; nothing fine-grained is
invented (the worker persists no phase records, so ``phase`` is honestly
null and progress is indeterminate), and an inconsistent record set is
reported as RECONSTRUCTION_STATUS_INCONSISTENT rather than smoothed over.

No filesystem path, storage key, provider response or traceback text may
enter the payload: the stored failure message is scrubbed of path-like
tokens and bounded before exposure.
"""
from __future__ import annotations

import re

from django.core.exceptions import SuspiciousOperation

STATUS_SCHEMA = "container_reconstruction_status/1.0"

QUEUED = "QUEUED"
RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
INCONSISTENT = "RECONSTRUCTION_STATUS_INCONSISTENT"

RECONSTRUCTION_FAILED = "RECONSTRUCTION_FAILED"
DISPATCH_FAILED = "RECONSTRUCTION_DISPATCH_FAILED"

#: statuses that mean reconstruction finished and the flow moved on
_POST_RECONSTRUCTION_STATUSES = ("awaiting_gate_2", "gate_2_approved",
                                 "completed")

#: persisted worker milestones (AgentLog action substrings) — real evidence,
#: written by resume_after_container_profile, never inferred from time
_START_MARK = "reconstructing container .ai"
_DONE_MARK = "reached Gate 2"

#: active states poll at this cadence; the client clamps to its own bounds
POLL_AFTER_MS = 5000

_PATHY = re.compile(r"(/[\w.\-]+){2,}")


def _safe_message(text: str, limit: int = 300) -> str:
    """The stored failure message with path-like tokens removed and length
    bounded — a worker exception string may embed absolute paths."""
    cleaned = _PATHY.sub("[path removed]", str(text or ""))
    return cleaned[:limit]


def build_container_reconstruction_status(task):
    """The authoritative snapshot for ``task``, or None when not applicable
    (wrong target, no confirmed profile, no gate decision) — None keeps the
    payload silent instead of leaking lifecycle vocabulary to other targets.
    """
    if task.design_target != "product_container":
        return None
    output = task.current_output()
    if output is None:
        return None
    spec = output.spec_sheet or {}
    confirmation = spec.get("container_confirmation")
    if not confirmation:
        return None
    from apps.pipeline.models import AgentLog, GateDecision
    decision = (GateDecision.objects
                .filter(task=task, gate="container_profile",
                        decision="approve")
                .order_by("-decided_at")
                .first())
    if decision is None:
        return None

    record = spec.get("container_profile/1.0") or {}
    resume = spec.get("container_resume") or {}
    error_text = spec.get("generation_error") or ""
    if not error_text and task.status == "failed":
        error_text = task.error_message or "reconstruction failed"

    start_log = (AgentLog.objects
                 .filter(task=task, agent_name="ARIA",
                         action__contains=_START_MARK)
                 .order_by("-timestamp").first())
    done_log = (AgentLog.objects
                .filter(task=task, agent_name="ARIA",
                        action__contains=_DONE_MARK)
                .order_by("-timestamp").first())

    ai_available = bool(output.design_preview_ai)
    if ai_available:
        try:
            output.design_preview_ai.size          # storage stat, no bytes
        except (OSError, ValueError, SuspiciousOperation):
            ai_available = False
    png_available = bool(output.design_preview)

    error = None
    finished_at = None
    started_at = start_log.timestamp.isoformat() if start_log else None

    if error_text:
        lifecycle = FAILED
        code = (DISPATCH_FAILED if error_text == DISPATCH_FAILED
                else RECONSTRUCTION_FAILED)
        # [his test blocker on design 122 at reconstruction, 2026-10-08, item 3: "The stop reason must be shown in plain
        # words on the page, never only codes in a fold."] each reason in words beside its record
        from apps.dashboard.words import drawing_stop_reasons
        error = {"code": code, "message": _safe_message(error_text), "reasons": drawing_stop_reasons(error_text, task)}
        finished_at = task.updated_at.isoformat() if task.updated_at else None
    elif task.status in _POST_RECONSTRUCTION_STATUSES:
        if ai_available:
            lifecycle = COMPLETED
            # [found on his re-confirmed 117, 2026-10-01] the drawing marks the design waiting at its review a moment
            # before it writes its done line: a done line older than this drawing's start is the drawing before it
            # ("finished 30 Sept, 20:04" under a drawing started 1 Oct, 17:51) — never this one's finish
            if done_log and start_log and done_log.timestamp < start_log.timestamp:
                done_log = None
            finished_at = (done_log.timestamp.isoformat() if done_log
                           else (task.updated_at.isoformat()
                                 if task.updated_at else None))
        else:
            # a success state without the required output is not success
            lifecycle = INCONSISTENT
    elif task.status == "generating_dieline":
        if not resume:
            lifecycle = INCONSISTENT
        elif start_log and (not resume.get("requested_at")
                            or started_at >= resume["requested_at"]):
            lifecycle = RUNNING
        else:
            lifecycle = QUEUED
    elif task.status == "awaiting_container_profile":
        # confirmed but back at the gate with no recorded error: a state the
        # records cannot explain — say so instead of inventing one
        lifecycle = INCONSISTENT
    else:
        lifecycle = INCONSISTENT

    terminal = lifecycle in (COMPLETED, FAILED)
    attempts = AgentLog.objects.filter(
        task=task, agent_name="ARIA",
        action__contains=_START_MARK).count()

    return {
        "schema": STATUS_SCHEMA,
        "task_id": task.id,
        "design_target": task.design_target,
        "gate_decision_id": decision.id,
        "profile_schema": record.get("schema_version",
                                     "container_profile/1.0"),
        "profile_authority": confirmation.get(
            "authority", "HUMAN_CONFIRMED_CONCEPT_ONLY"),
        "profile_hash": record.get("profile_hash", ""),
        "task_state": task.status,
        "lifecycle_state": lifecycle,
        # the worker persists no phase records — null, never fabricated
        "phase": None,
        "attempt": attempts,
        "dispatch_status": ("DISPATCH_FAILED"
                            if error and error["code"] == DISPATCH_FAILED
                            else resume.get("kind") or "NOT_DISPATCHED"),
        "queued_at": resume.get("requested_at"),
        "started_at": started_at if lifecycle in (RUNNING, COMPLETED, FAILED)
        else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at
        else None,
        "finished_at": finished_at if terminal else None,
        "error": error,
        "artifacts": {"ai": {"available": ai_available},
                      "png": {"available": png_available}},
        "terminal": terminal,
        "poll_after_ms": POLL_AFTER_MS,
        "retry": _retry_block(task, output, spec, lifecycle, error,
                              decision, record, attempts),
    }


# ---------------------------------------------------------------------------
# result contract (UI-2B-2A) — derived, read-only, COMPLETED-only
# ---------------------------------------------------------------------------

RESULT_SCHEMA = "container_reconstruction_result/1.0"

AI_ROLE = "AI_SOURCE_OF_TRUTH"
PNG_ROLE = "PNG_PREVIEW_ONLY"

#: media types the artifact endpoint may serve, fixed by role — a stored
#: object never chooses its own content type
ARTIFACT_MEDIA_TYPES = {"ai": "application/illustrator", "png": "image/png"}


def _artifact_entry(filefield, *, role, kind, task_id, created_at):
    """Safe metadata for one result artifact: basename, role, size via a
    storage stat, and the authorized endpoint path. Never a storage key,
    FileField URL or byte."""
    import os
    available = bool(filefield)
    entry = {
        "role": role,
        "available": available,
        "media_type": ARTIFACT_MEDIA_TYPES[kind],
        "filename": (os.path.basename(filefield.name) if available else None),
        "file_size": None,
        "sha256": None,          # not persisted by the reconstruction
        "created_at": created_at,
        "validation_state": None,
        "downloadable": available,
        "download_url": (f"/api/tasks/{task_id}/reconstruction-artifact/"
                         f"{kind}/?download=1" if available else None),
    }
    if available:
        try:
            entry["file_size"] = filefield.size
        except (OSError, ValueError, SuspiciousOperation):
            entry["available"] = False
            entry["downloadable"] = False
            entry["download_url"] = None
    if kind == "png":
        entry["previewable"] = entry["available"]
        entry["preview_url"] = (
            f"/api/tasks/{task_id}/reconstruction-artifact/png/"
            if entry["available"] else None)
        entry["openable"] = entry["available"]
    else:
        entry["previewable"] = False
        entry["openable"] = False
    return entry


def build_container_reconstruction_result(task):
    """The COMPLETED-only result contract, or None. Anything other than a
    clean completion (per the status snapshot, which already demands the
    recorded .ai) yields None — QUEUED/RUNNING/FAILED/inconsistent tasks keep
    their UI-2B-1 presentations and no success is ever fabricated."""
    status = build_container_reconstruction_status(task)
    if not status or status["lifecycle_state"] != COMPLETED:
        return None
    output = task.current_output()
    spec = output.spec_sheet or {}
    fidelity = spec.get("container_fidelity_report") or {}
    validation_state = ("RECORDED" if fidelity else "NOT_RECORDED")

    ai = _artifact_entry(output.design_preview_ai, role=AI_ROLE, kind="ai",
                         task_id=task.id,
                         created_at=status.get("finished_at"))
    png = _artifact_entry(output.design_preview, role=PNG_ROLE, kind="png",
                          task_id=task.id,
                          created_at=status.get("finished_at"))
    ai["validation_state"] = validation_state
    png["validation_state"] = validation_state
    if not ai["available"]:
        # the status snapshot required the .ai; losing it between the two
        # reads is an inconsistency, not a presentable result
        return None
    return {
        "schema": RESULT_SCHEMA,
        "task_id": task.id,
        "gate_decision_id": status["gate_decision_id"],
        "profile_schema": status["profile_schema"],
        "profile_authority": status["profile_authority"],
        "profile_hash": status["profile_hash"],
        "lifecycle_state": COMPLETED,
        "artifacts": {"ai": ai, "png": png},
    }


# ---------------------------------------------------------------------------
# retry eligibility (UI-2B-2B) — derived, server-authoritative, read-only
# ---------------------------------------------------------------------------

RETRY_ACTION = "RESUME_EXISTING_CONFIRMED_PROFILE"

WORKER_FAILED = "RECONSTRUCTION_WORKER_FAILED"
RETRYABLE_INCONSISTENCY = "RETRYABLE_RECONSTRUCTION_INCONSISTENCY"
#: §BH54(d): "a STALE spec is re-derived before it can be accepted and the re-derivation decides" — the re-derivation
#: is a reconstruction of the SAME confirmed profile, offered only while the result awaits Gate 2 (an accepted
#: design is never rebuilt through this door)
STALE_REDERIVATION = "STALE_SPEC_REDERIVATION"
TECHNICAL_INTERVENTION = "TECHNICAL_INTERVENTION_REQUIRED"
ARTIFACT_INVALID = "RECONSTRUCTION_ARTIFACT_INVALID"


def _ai_record_is_tampered(output) -> bool:
    """True when the persisted .ai record names a path OUTSIDE the artifact
    root — an unsafe record that must never be retried away automatically."""
    import os

    from django.core.files.storage import default_storage
    name = (output.design_preview_ai.name or "") if output.design_preview_ai         else ""
    if not name:
        return False
    try:
        root = os.path.realpath(default_storage.path("dielines"))
        full = os.path.realpath(default_storage.path(name))
    except Exception:  # noqa: BLE001 — unresolvable path IS the tamper signal
        return True
    return not (full == root or full.startswith(root + os.sep))


def _retry_block(task, output, spec, lifecycle, error, decision, record,
                 attempts):
    """One authoritative answer to "may the owner retry, and why". Retry is
    REUSE of the existing confirmed decision — never a reconfirmation — so
    eligibility exists only for the failure classes the resume contract can
    recover, and never while an attempt is active or after clean success."""
    block = {
        "eligible": False,
        "reason_code": None,
        "requires_owner_confirmation": True,
        "active_attempt": lifecycle in (QUEUED, RUNNING),
        "existing_gate_decision_id": decision.id,
        "confirmed_profile_hash": record.get("profile_hash", ""),
        "attempts_so_far": attempts,
        "action": RETRY_ACTION,
    }
    if lifecycle in (QUEUED, RUNNING):
        return block
    if lifecycle == COMPLETED:
        # §BH54(d): a clean completion stays non-retryable — unless its spec is STALE and not yet accepted
        if task.status == "awaiting_gate_2":
            from apps.ire.container_production_readiness import spec_staleness
            stale = spec_staleness(spec or {})
            if stale["stale"]:
                block["eligible"] = True
                block["reason_code"] = STALE_REDERIVATION
                block["checks_predate"] = [i["since"] for i in stale["checks_predate"]]
        return block
    if lifecycle == FAILED and error:
        block["eligible"] = True
        block["reason_code"] = (DISPATCH_FAILED
                                if error["code"] == DISPATCH_FAILED
                                else WORKER_FAILED)
        return block
    if lifecycle == INCONSISTENT:
        if _ai_record_is_tampered(output):
            # unsafe record: adjudication first, never an automatic retry
            block["reason_code"] = ARTIFACT_INVALID
            block["recovery"] = TECHNICAL_INTERVENTION
            return block
        if task.status in _POST_RECONSTRUCTION_STATUSES:
            # success state without its required output — a re-run of the
            # SAME confirmed profile can rebuild the artifacts
            block["eligible"] = True
            block["reason_code"] = RETRYABLE_INCONSISTENCY
            return block
        # e.g. generating_dieline without a resume identity: the records
        # cannot explain themselves — a human looks first
        block["reason_code"] = INCONSISTENT
        block["recovery"] = TECHNICAL_INTERVENTION
        return block
    return block


# ---------------------------------------------------------------------------
# Gate-2 readiness (VQR-6) — ONE derived answer to "may Gate 2 proceed"
# ---------------------------------------------------------------------------

GATE_2_NOT_READY = "GATE_2_NOT_READY"
VISUAL_QUALITY_GATE_FAILED = "VISUAL_QUALITY_GATE_FAILED"


def build_container_gate2_readiness(task, quality=...):
    """The single Gate-2 readiness authority for a container task, or None
    when the task has no confirmed reconstruction contract (other targets,
    unconfirmed profiles). Derived STRICTLY from the status and result
    contracts — a truthy FileField is never proof of an available,
    authorized or valid artifact.

    PNG availability alone can never make Gate 2 ready; an optional missing
    PNG with a valid AI does not block it.

    VQR-2A: an available AI file alone is not enough either. Gate-2,
    handoff and owner-review readiness additionally require the fail-closed
    visual quality gate to PASS [§BH71 (0a): to have no measured FAIL — an
    unmeasured axis is a warning beside Approve]. Failure precedence (§10):

        1. TECHNICAL_INTERVENTION_REQUIRED
        2. artifact authority (lifecycle / result availability)
        3. VISUAL_QUALITY_GATE_FAILED
        4. clean completed result
    """
    from apps.pipeline.services.visual_quality_gate import (
        evaluate_container_visual_quality,
    )
    status = build_container_reconstruction_status(task)
    if status is None:
        return None
    result = build_container_reconstruction_result(task)
    retry = status.get("retry") or {}
    technical = retry.get("recovery") == TECHNICAL_INTERVENTION
    ai_authoritative = bool(result
                            and result["artifacts"]["ai"]["available"])
    # PNG availability comes from the STATUS artifacts: the result contract
    # is deliberately None in exactly the states (inconsistent, failed)
    # where "PNG exists but can never make Gate 2 ready" must be sayable.
    png_available = bool(status["artifacts"]["png"]["available"])
    artifact_ready = (status["lifecycle_state"] == COMPLETED
                      and result is not None
                      and ai_authoritative
                      and not technical)
    # Visual quality is evaluated only for a cleanly completed lifecycle —
    # a worker failure stays a worker failure and a tampered record stays
    # technical intervention; neither is a "visual result" (§10/§11).
    # A caller that already evaluated (the status view) may pass the report
    # in to avoid re-reading artifact bytes; Ellipsis means "not provided".
    if quality is Ellipsis:
        quality = (evaluate_container_visual_quality(task)
                   if artifact_ready else None)
    elif not artifact_ready:
        quality = None
    # §BH71 (0a): an unmeasured axis is a warning beside Approve — only a measured FAIL keeps Approve hidden
    quality_passed = bool(quality and quality["overall"] != "FAIL")
    ready = artifact_ready and quality_passed
    if ready:
        reason = None
    elif technical:
        reason = TECHNICAL_INTERVENTION
    elif status["lifecycle_state"] != COMPLETED:
        reason = status["lifecycle_state"]
    elif not artifact_ready:
        reason = "RESULT_UNAVAILABLE"
    else:
        reason = VISUAL_QUALITY_GATE_FAILED
    return {
        "ready": ready,
        "reason_code": reason,
        "lifecycle_state": status["lifecycle_state"],
        "ai_authoritative": ai_authoritative,
        "png_preview_available": png_available,
        "technical_intervention_required": technical,
        # VQR-2A: handoff needs the authoritative AI AND visual quality;
        # owner review needs visual quality. Artifacts stay accessible for
        # technical inspection even when quality fails (§8).
        "handoff_ready": ready,
        "owner_review_ready": ready,
        "visual_quality": (None if quality is None else {
            "overall": quality["overall"],
            "status": quality["status"],
            "blocking_codes": [f["code"]
                               for f in quality["blocking_findings"]],
            "acceptance_warnings": [f["code"] for f in quality.get("acceptance_warnings") or []],
        }),
        "inspection_only": artifact_ready and not quality_passed,
    }
