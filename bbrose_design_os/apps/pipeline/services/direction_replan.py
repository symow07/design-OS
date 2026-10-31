"""Safe replacement of an unselected direction set (Phase 2A-6D).

Task #50 reached the direction pause with a set the user rejected on
CONTENT grounds. Replacing it must not lose the audit trail, duplicate
briefs, or slide into rendering:

  * the current design_intent + directions are archived VERBATIM to
    AgentLog.payload (the observability channel — never a second brief);
  * the brief's active set is cleared, so ARIA's durable routing replans
    from scratch (a brief with no directions is "nothing yet");
  * the corrective feedback rides task.gate_1_notes — the same revision
    channel the legacy Gate-1 reject path uses — and reaches the Creative
    Director as revision_feedback;
  * the task is requeued; planning ends at awaiting_direction_selection
    with zero Prompt Engineer and zero image calls, like any planning run.

Refuses when a direction is already selected (switching after selection is
a separately designed workflow) or when any image exists.
"""
from __future__ import annotations

from django.db import transaction

REPLAN_ARCHIVE_ACTION = "Direction set archived for replan"

#: Stable refusal codes.
REPLAN_NOT_PAUSED = "REPLAN_NOT_PAUSED"
REPLAN_ALREADY_SELECTED = "REPLAN_ALREADY_SELECTED"
REPLAN_HAS_RENDERS = "REPLAN_HAS_RENDERS"


class ReplanError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@transaction.atomic
def replan_design_directions(task, user, feedback: str) -> dict:
    """Archive the active direction set and requeue planning with feedback.

    Returns {"archived_log_id", "queued"}. Enqueues via on_commit, so only a
    committed replan generates.
    """
    from apps.pipeline.models import AgentLog, CreativeBrief, DesignTask

    task = DesignTask.objects.select_for_update().get(pk=task.pk)
    brief = (CreativeBrief.objects.select_for_update()
             .filter(task=task).first())

    if task.status != "awaiting_direction_selection" or brief is None:
        raise ReplanError(
            REPLAN_NOT_PAUSED,
            f"replan requires awaiting_direction_selection with a persisted "
            f"plan; task is {task.status!r}")
    if brief.selected_direction_id:
        raise ReplanError(
            REPLAN_ALREADY_SELECTED,
            "a direction is already selected — switching after selection is "
            "a separate workflow, not a replan")
    if task.images.exists():
        raise ReplanError(
            REPLAN_HAS_RENDERS,
            "rendered concepts exist — replanning would orphan them; this "
            "state should be unreachable while paused")

    archive = AgentLog.objects.create(
        task=task, agent_name="ARIA", actor=user,
        action=REPLAN_ARCHIVE_ACTION,
        payload={
            "design_intent": brief.design_intent,
            "directions": brief.directions,
            "reason": (feedback or "")[:2000],
            "archived_direction_ids": [
                d.get("direction_id") for d in (brief.directions or [])
                if isinstance(d, dict)],
        },
        level="warning",
    )

    brief.design_intent = {}
    brief.directions = []
    brief.selected_direction_id = ""
    brief.direction_selected_at = None
    brief.save(update_fields=["design_intent", "directions",
                              "selected_direction_id", "direction_selected_at"])

    task.gate_1_notes = (feedback or "").strip()
    task.status = "queued"
    task.error_message = ""
    task.save(update_fields=["gate_1_notes", "status", "error_message"])

    def _enqueue():
        from apps.pipeline.tasks import run_aria_pipeline
        run_aria_pipeline.delay(task.pk)

    transaction.on_commit(_enqueue)
    return {"archived_log_id": archive.pk, "queued": True}


__all__ = ["replan_design_directions", "ReplanError",
           "REPLAN_ARCHIVE_ACTION", "REPLAN_NOT_PAUSED",
           "REPLAN_ALREADY_SELECTED", "REPLAN_HAS_RENDERS"]
