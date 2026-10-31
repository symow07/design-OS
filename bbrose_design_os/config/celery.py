import os

from celery import Celery
from celery.signals import worker_ready

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("bbrose_design_os")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_ready.connect
def _log_worker_revision(**_kwargs):
    """Stamp the code revision at worker boot (Phase 2A-6C-CORR §8) so a
    stale worker is visible in its own log without process forensics.

    Written to stderr (celery redirects it to the worker log) AND the celery
    logger, so the stamp survives whatever logging config is in force."""
    import logging
    import sys

    from apps.pipeline.services.revision import current_revision
    rev = current_revision()
    print(f"ARIA worker ready on code revision {rev}", file=sys.stderr, flush=True)
    logging.getLogger("celery").warning("ARIA worker ready on code revision %s", rev)

