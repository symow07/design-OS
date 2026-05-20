import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def run_aria_pipeline(self, task_id):
    try:
        from apps.pipeline.agents.aria import ARIAAgent
        agent = ARIAAgent(task_id)
        agent.run()
    except Exception as exc:
        logger.error(f"ARIA pipeline failed for task {task_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1)
def resume_aria_gate1(self, task_id, image_id):
    try:
        from apps.pipeline.agents.aria import ARIAAgent
        agent = ARIAAgent(task_id)
        agent.resume_after_gate_1(image_id)
    except Exception as exc:
        logger.error(f"Gate 1 resume failed for task {task_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1)
def resume_aria_dimensions(self, task_id, packaging_output_id, confirmed_dims):
    try:
        from apps.pipeline.agents.aria import ARIAAgent
        agent = ARIAAgent(task_id)
        agent.resume_after_dimensions(packaging_output_id, confirmed_dims)
    except Exception as exc:
        logger.error(f"Dimension resume failed for task {task_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1)
def resume_aria_gate2(self, task_id, packaging_output_id):
    try:
        from apps.pipeline.agents.aria import ARIAAgent
        agent = ARIAAgent(task_id)
        agent.resume_after_gate_2(packaging_output_id)
    except Exception as exc:
        logger.error(f"Gate 2 resume failed for task {task_id}: {exc}")
        raise self.retry(exc=exc)
