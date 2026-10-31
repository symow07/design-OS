"""Celery tasks of the retired round kinds and pages, archived by the owner's goal of 2026-10-29. Each block is copied
whole from bbrose_design_os/apps/pipeline/tasks.py as it stood at 49ac763. Kept as text, not imported by anything."""

# tasks.py:178-181 — the whole-object kind's marks deadline (round_flow.marks_deadline, archived with it)
@shared_task(name='apps.pipeline.tasks.round_marks_deadline')
def round_marks_deadline(round_id):
    from apps.pipeline.services.round_flow import marks_deadline
    return marks_deadline(round_id)


# tasks.py:184-187 — the Round 1B/1C master pages' worker job (round_master_flow)
@shared_task(name='apps.pipeline.tasks.run_round_master', acks_late=True, reject_on_worker_lost=True)
def run_round_master(build_id):
    from apps.pipeline.services.round_master_flow import run
    return run(build_id)
