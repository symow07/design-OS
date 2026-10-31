"""Health checks for /healthz and the pipeline worker guard (Milestone 8.7).

Two run modes:
  eager      — CELERY_TASK_ALWAYS_EAGER=True: tasks run in-process, so only
               the DB is checked and celery reports "eager".
  worker     — tasks enqueue to Redis; Redis connectivity and a live worker
               (celery inspect ping, short timeout) are both required.
"""
import logging

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

PING_TIMEOUT = 2.0  # seconds — keep /healthz fast


def check_db():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return "ok"
    except Exception as exc:  # noqa: BLE001 — a probe must never raise
        return f"error: {exc}"


def check_redis():
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=PING_TIMEOUT,
            socket_timeout=PING_TIMEOUT,
        )
        client.ping()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def migration_state():
    """Measured migration state, as a string that carries its own reason.

    Same contract as check_db() above — a measurement never raises, and a
    failure says what failed. Returns exactly one of:

        "ok"                                 no unapplied migrations
        "unapplied: N (app.name, app.name)"  drift, with the migrations NAMED
        "unknown: <exc>"                     the state could not be read

    §AY0(d): the three states are distinct because their remedies are
    opposite. `manage.py migrate` fixes the second and does nothing for the
    third. A caller that collapses them into one boolean is telling its user
    to run the wrong command.

    Naming the migrations rather than the app labels is the point of the
    function. Django's own startup notice
    (BaseCommand.check_migrations, called by runserver) says only
    "app(s): pipeline" — with 31 pipeline migrations on disk that does not
    identify which one is missing, and identifying it is the whole content
    of the incident this measurement exists for.

    DELIBERATELY NOT ADDED TO run_health_checks(), AND THAT REFUSAL IS THE
    LOAD-BEARING PART (§AY0(e)). /healthz marks the service unhealthy when
    ANY check value is not "ok"/"eager" and returns 503
    (apps/core/views.py:38-39). Wiring migration state into it would pull a
    service OUT OF ROTATION during precisely the rolling deploy where the
    new code is live and `migrate` has not run yet — converting a drift
    notice into an outage. Migration drift is a correctness signal for
    whoever is about to trust the schema, not a liveness signal. Callers
    with a reason to care ask for it explicitly; there is exactly one
    surface today (the composite pilot preflight) and it asks.
    """
    try:
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception as exc:  # noqa: BLE001 — a probe must never raise
        return f"unknown: {exc}"
    if not plan:
        return "ok"
    names = ", ".join(f"{m.app_label}.{m.name}" for m, _ in plan[:5])
    return (f"unapplied: {len(plan)} ({names}"
            + (", …)" if len(plan) > 5 else ")"))


def ping_workers(timeout=PING_TIMEOUT):
    """Celery inspect ping response dict, or None if no worker answered."""
    try:
        from config.celery import app

        return app.control.inspect(timeout=timeout).ping() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Celery worker ping failed: %s", exc)
        return None


def worker_available():
    """True when enqueued tasks can actually run: eager mode, or at least one
    worker responds to ping. Used by task creation to avoid enqueueing into a
    black hole."""
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return True
    return ping_workers() is not None


def run_health_checks():
    checks = {"db": check_db()}
    if settings.CELERY_TASK_ALWAYS_EAGER:
        checks["celery"] = "eager"
    else:
        checks["redis"] = check_redis()
        pong = ping_workers()
        checks["celery"] = "ok" if pong else "error: no worker responded to ping"
    return checks
