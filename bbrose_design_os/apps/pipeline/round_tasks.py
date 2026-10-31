"""The chain's worker tasks (the owner's goal of 2026-10-29: the worker moved onto the chain before the old engines
retire): the worker's revision probe, one bounded round job, and one files build delivery. Their names stay those of
apps.pipeline.tasks, where Celery's autodiscovery registers them; nothing here imports the old ARIA pipeline."""
from celery import shared_task


@shared_task(name="apps.pipeline.tasks.report_worker_revision")
def report_worker_revision():
    """Return the code revision the WORKER is running (Phase 2A-6C-CORR §8).

    A health/version probe: enqueue it and read the result to learn the live
    worker's revision, so a web/worker mismatch (a stale worker) is
    detectable operationally instead of by process-start forensics. Pure
    read, no side effects, no external call."""
    from apps.pipeline.services.revision import current_revision
    return current_revision()


@shared_task(name='apps.pipeline.tasks.run_creative_round_step', acks_late=True, reject_on_worker_lost=True)
def run_creative_round_step(step_id):
    """A bounded round job: at most one new paid logical call per delivery."""
    from apps.pipeline.services.round_flow import run_step_job
    return run_step_job(step_id)


@shared_task(name='apps.pipeline.tasks.run_round_files', acks_late=True, reject_on_worker_lost=True)
def run_round_files(build_id):
    from apps.pipeline.services.round_files_gate import run
    return run(build_id)
