"""Notification dispatch (Milestone 12.4).

Turns a task status change into in-app Notification rows and outbound email,
honouring each recipient's NotificationPreference. Recipients:

  * every step that waits on a person (§BH55 Phase 3: the three gates, the direction step, the container's shape,
    the structure step, the design intent, a held generation)
    → the task's owner + assignee AND every Reviewer/Admin (they can act on it)
  * failed / completed → the task's owner + assignee

Dispatch is best-effort: a mail backend error must never break the pipeline
transition that triggered it.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail

from apps.dashboard.words import status_words
from apps.pipeline.models import NOTIFICATION_KINDS, Notification, NotificationPreference
from apps.pipeline.permissions import ROLE_ADMIN, ROLE_REVIEWER

logger = logging.getLogger("apps.pipeline")

# §BH55 Phase 3: every step that waits on a person is one a reviewer may act on — the three gates were, and the
# direction step, the container's shape, the structure step, the design intent and a held generation were not
_GATE_KINDS = {kind for kind, _ in NOTIFICATION_KINDS if kind.startswith("awaiting")}

# §BH55 Phase 3: what the bell and the email say, in the words the list reads (apps/dashboard/words.py) — they read
# "Task #53 is awaiting Gate 1 review"; now "Design #53: choose a concept", for every kind the record allows
_MESSAGES = {kind: "Design #{id}: " + status_words(kind).lower() for kind, _ in NOTIFICATION_KINDS}


def get_prefs(user) -> NotificationPreference:
    prefs, _ = NotificationPreference.objects.get_or_create(user=user)
    return prefs


def _role_users(*roles):
    return User.objects.filter(groups__name__in=roles, is_active=True).distinct()


def _recipients(task, kind):
    users = set()
    for u in (task.created_by, task.assigned_to):
        if u is not None:
            users.add(u)
    if kind in _GATE_KINDS:
        users.update(_role_users(ROLE_REVIEWER, ROLE_ADMIN))
    return users


def notify_task_status(task, kind):
    """Fan out one status event to all recipients. Returns the created
    Notification rows (in-app), skipping recipients who muted that channel."""
    if kind not in _MESSAGES:
        return []
    message = _MESSAGES[kind].format(id=task.id)
    created = []
    email_targets = []
    for user in _recipients(task, kind):
        prefs = get_prefs(user)
        if prefs.in_app:
            created.append(Notification.objects.create(
                recipient=user, task=task, kind=kind, message=message,
            ))
        if prefs.email and user.email:
            email_targets.append(user.email)

    if email_targets:
        _send_email(task, kind, message, email_targets)
    return created


def _send_email(task, kind, message, recipients):
    # §BH55 Phase 3: the design's own address — "/dashboard/?task=<id>" opened the home and no design
    link = f"{settings.NOTIFICATION_BASE_URL}/dashboard/designs/{task.id}/"
    try:
        send_mail(
            subject=f"[BBROSE Design OS] {message}",
            message=f"{message}\n\nOpen the design: {link}\n",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=sorted(set(recipients)),
            fail_silently=False,
        )
    except Exception:  # pragma: no cover - email must not break the pipeline
        logger.exception("notification email failed for task %s (%s)", task.id, kind)
