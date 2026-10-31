import logging

from celery import shared_task
from celery.exceptions import Retry

logger = logging.getLogger(__name__)

# the chain's own tasks live in round_tasks (2026-10-29); imported here so Celery's autodiscovery registers them
from apps.pipeline.round_tasks import report_worker_revision, run_creative_round_step, run_round_files  # noqa: E402,F401


def _mark_task_failed(task_id, exc):
    """Final fail-safe (Milestone 8.2): when Celery retries are exhausted the
    task is marked failed with the reason recorded — never re-raised into the
    void, so nothing strands in an intermediate status."""
    try:
        from apps.pipeline.models import AgentLog, DesignTask

        reason = f"Pipeline worker error after retries: {exc}"
        DesignTask.objects.filter(id=task_id).update(
            status='failed', error_message=reason,
        )
        AgentLog.objects.create(
            task_id=task_id, agent_name='ARIA',
            action=f'ARIA: pipeline failed — {reason}', level='error',
        )
    except Exception:  # noqa: BLE001 — a fail-safe must never raise
        logger.exception("Could not mark task %s as failed", task_id)


def _run_stage(celery_task, task_id, stage_fn, stage_name):
    """Run one pipeline stage with retry + terminal fail-safe."""
    try:
        stage_fn()
    except Exception as exc:  # noqa: BLE001
        logger.error("%s failed for task %s: %s", stage_name, task_id, exc)
        try:
            raise celery_task.retry(exc=exc)
        except Retry:
            raise  # a retry was scheduled — let Celery handle it
        except Exception as final_exc:  # noqa: BLE001 — retries exhausted
            _mark_task_failed(task_id, final_exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def run_aria_pipeline(self, task_id):
    from apps.pipeline.agents.aria import ARIAAgent
    _run_stage(self, task_id, lambda: ARIAAgent(task_id).run(), "ARIA pipeline")


@shared_task(name="apps.pipeline.tasks.close_trend_review")
def close_trend_review(task_id):
    """§BH71 PART 2: a trend board's review window closes — the design moves on with the pictures as they are ticked,
    unless he pressed on first (apps/pipeline/services/trend_board.py close_if_due). A close that finds the design
    moved on already does nothing."""
    from apps.pipeline.services import trend_board
    trend_board.close_if_due(task_id)


@shared_task(name="apps.pipeline.tasks.autopilot_step")
def autopilot_step(task_id, seen_status=None, seen_at=None):
    """[His goal after the pitch page, 2026-10-15, B (9): "Run each from brief to final files with no manual fixes"] the
    pitch run takes the step its design waits at, as the step's button would (apps/pipeline/autopilot.py ``drive``);
    ``seen_status`` and ``seen_at`` are the status that woke it and when — the time the final files were made, at Gate 2.
    It never raises: an error is said in the design's log and kept as a stop."""
    from apps.pipeline import autopilot
    autopilot.drive(task_id, seen_at)


@shared_task(bind=True, max_retries=1)
def resume_aria_gate1(self, task_id, image_id):
    from apps.pipeline.agents.aria import ARIAAgent
    _run_stage(
        self, task_id,
        lambda: ARIAAgent(task_id).resume_after_gate_1(image_id),
        "Gate 1 resume",
    )


@shared_task(bind=True, max_retries=1)
def redraw_concept(self, task_id, image_id):
    """[His test blocker on design 122, 2026-10-07, item 4] one concept redrawn by his button, checked, back at Gate 1."""
    from apps.pipeline.agents.aria import ARIAAgent
    _run_stage(self, task_id, lambda: ARIAAgent(task_id).redraw_concept(image_id), "Concept redraw")


@shared_task(bind=True, max_retries=1)
def rerun_aria_images(self, task_id):
    """Milestone 11.3 — image-only rerun (Creative Director + Prompt Engineer
    skipped)."""
    from apps.pipeline.agents.aria import ARIAAgent
    _run_stage(
        self, task_id,
        lambda: ARIAAgent(task_id).rerun_images(),
        "Image rerun",
    )


@shared_task(bind=True, max_retries=1)
def regenerate_gate1_references(self, job_id):
    """2A-6E: reference-grounded Gate-1 regeneration — same selected
    direction, user-approved concept references, no Creative Director.
    2A-6E-CORR-2: bound to a Gate1RegenerationJob; whatever happens, the
    job never stays 'running' after this task returns — a crash-safe
    failure is reflected on the pollable job."""
    from django.utils import timezone
    from apps.pipeline.agents.aria import ARIAAgent
    from apps.pipeline.models import Gate1RegenerationJob

    job = Gate1RegenerationJob.objects.filter(pk=job_id).first()
    if job is None:
        return
    agent = ARIAAgent(job.task_id)
    _run_stage(
        self, job.task_id,
        lambda: agent.regenerate_gate1_with_references(job_id=job.pk),
        "Reference-grounded Gate-1 regeneration",
    )
    job.refresh_from_db()
    if getattr(agent, "regeneration_owned", False) and job.status in Gate1RegenerationJob.ACTIVE_STATUSES:
        task = job.task
        job.status = Gate1RegenerationJob.STATUS_FAILED
        job.error = (task.error_message
                     or "regeneration ended without completing")
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])


@shared_task(bind=True, max_retries=1)
def resume_aria_dimensions(self, task_id, packaging_output_id, confirmed_dims,
                           panel_info=None):
    from apps.pipeline.agents.aria import ARIAAgent
    _run_stage(
        self, task_id,
        lambda: ARIAAgent(task_id).resume_after_dimensions(
            packaging_output_id, confirmed_dims, panel_info_override=panel_info),
        "Dimension resume",
    )


@shared_task(bind=True, max_retries=1)
def resume_aria_container_profile(self, task_id, packaging_output_id, confirmed_profile):
    from apps.pipeline.agents.aria import ARIAAgent
    _run_stage(
        self, task_id,
        lambda: ARIAAgent(task_id).resume_after_container_profile(
            packaging_output_id, confirmed_profile),
        "Container profile resume",
    )


@shared_task(bind=True, max_retries=1)
def resume_aria_gate2(self, task_id, packaging_output_id):
    from apps.pipeline.agents.aria import ARIAAgent
    _run_stage(
        self, task_id,
        lambda: ARIAAgent(task_id).resume_after_gate_2(packaging_output_id),
        "Gate 2 resume",
    )
