"""Status-change → notification signals (Milestone 12.4).

A DesignTask transitioning INTO a notify-worthy status fans out notifications.
The old status is stashed in pre_save (fetched fresh from the DB) so we only
fire on an actual change, never on unrelated ``save(update_fields=...)`` calls.
QuerySet.update() bypasses signals, but the awaiting_*/failed/completed
statuses are all set via ARIA's ``task.save()``, so every real transition is
covered.
"""
from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.pipeline.models import NOTIFICATION_KINDS, DesignTask

_NOTIFY_STATUSES = {kind for kind, _ in NOTIFICATION_KINDS}


@receiver(pre_save, sender=DesignTask)
def _stash_old_status(sender, instance, **kwargs):
    if instance.pk:
        instance._old_status = (
            sender.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )
    else:
        instance._old_status = None


@receiver(post_save, sender=DesignTask)
def _notify_on_status_change(sender, instance, created, **kwargs):
    new_status = instance.status
    old_status = getattr(instance, "_old_status", None)
    if new_status in _NOTIFY_STATUSES and new_status != old_status:
        from apps.pipeline.notifications import notify_task_status
        notify_task_status(instance, new_status)


@receiver(post_save, sender=DesignTask)
def _autopilot_on_status_change(sender, instance, created, **kwargs):
    """[His goal after the pitch page, 2026-10-15, B (9)] a pitch-run design that changed status is handed to the pitch
    run (``apps/pipeline/autopilot.py``, ``watch``) — on an actual change only, so a save of its options never wakes it."""
    if instance.status != getattr(instance, "_old_status", None):
        from apps.pipeline import autopilot
        autopilot.watch(instance)
