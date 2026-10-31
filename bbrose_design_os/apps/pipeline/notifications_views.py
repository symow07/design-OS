"""Notification & preference API for the dashboard bell menu (Milestone 12.4)."""
from __future__ import annotations

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pipeline.models import Notification
from apps.pipeline.notifications import get_prefs


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "task", "kind", "message", "is_read", "created_at"]


class NotificationListView(APIView):
    """GET /api/notifications/ — the current user's recent notifications and
    unread count for the bell menu."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user)
        unread = qs.filter(is_read=False).count()
        recent = qs[:30]
        return Response({
            "unread_count": unread,
            "notifications": NotificationSerializer(recent, many=True).data,
        })


class NotificationMarkReadView(APIView):
    """POST /api/notifications/mark_read/ — mark one (``id``) or all read."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        qs = Notification.objects.filter(recipient=request.user, is_read=False)
        note_id = request.data.get("id")
        if note_id is not None:
            qs = qs.filter(id=note_id)
        updated = qs.update(is_read=True)
        return Response({"marked_read": updated})


class NotificationPreferenceView(APIView):
    """GET / PUT /api/notifications/preferences/ — per-user channel prefs."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prefs = get_prefs(request.user)
        return Response({"in_app": prefs.in_app, "email": prefs.email})

    def put(self, request):
        prefs = get_prefs(request.user)
        changed = []
        for field in ("in_app", "email"):
            if field in request.data:
                setattr(prefs, field, bool(request.data[field]))
                changed.append(field)
        if changed:
            prefs.save(update_fields=changed)
        return Response({"in_app": prefs.in_app, "email": prefs.email})
