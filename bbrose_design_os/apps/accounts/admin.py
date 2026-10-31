"""Read-only admin for reviewer identity (DIP-1A-2).

These rows are security evidence: who could decide what, and when. The admin **shows**
them and never edits them. Granting, revoking and enabling happen through audited,
authorized services (the bootstrap command for the first seed; DIP-1A-5 for the rest) —
never by hand-editing a row in a form that keeps no record of who changed it or why. So
add/change/delete are all disabled and every field is read-only.
"""
from __future__ import annotations

from django.contrib import admin

from .models import (
    AuthorizationAudit,
    BootstrapState,
    DecisionChainHead,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)


class _ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False       # view via the changelist/detail, but never save

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReviewerProfile)
class ReviewerProfileAdmin(_ReadOnlyAdmin):
    list_display = ("user", "display_name", "reviewer_enabled", "organization",
                    "updated_at")
    list_filter = ("reviewer_enabled",)
    search_fields = ("user__username", "display_name", "organization")


@admin.register(ReviewerRoleAssignment)
class ReviewerRoleAssignmentAdmin(_ReadOnlyAdmin):
    list_display = ("user", "role", "grant_source", "granted_at", "expires_at",
                    "revoked_at", "granted_by")
    list_filter = ("role", "grant_source")
    search_fields = ("user__username", "role")
    date_hierarchy = "granted_at"


@admin.register(AuthorizationAudit)
class AuthorizationAuditAdmin(_ReadOnlyAdmin):
    # Append-only evidence: view only, never edit or delete (the model refuses both, and
    # this admin does not offer them).
    list_display = ("created_at", "result", "action", "user", "reason_code",
                    "role_used", "endpoint")
    list_filter = ("result", "reason_code", "action")
    search_fields = ("user__username", "action", "reason_code", "correlation_id")
    date_hierarchy = "created_at"


@admin.register(DecisionEvent)
class DecisionEventAdmin(_ReadOnlyAdmin):
    # Signed, immutable chain links: view only. Editing here is impossible anyway (the
    # model has no non-token write path), but the admin also refuses add/change/delete.
    list_display = ("sequence_number", "action", "actor", "role_used", "event_id",
                    "signing_key_id", "created_at")
    list_filter = ("action", "role_used", "signing_key_id")
    search_fields = ("event_id", "action", "actor__username", "subject_id")
    ordering = ("sequence_number",)


@admin.register(DecisionChainHead)
class DecisionChainHeadAdmin(_ReadOnlyAdmin):
    list_display = ("chain_id", "terminal_sequence_number", "event_count",
                    "signing_key_id", "updated_at")


@admin.register(BootstrapState)
class BootstrapStateAdmin(_ReadOnlyAdmin):
    list_display = ("closed", "closed_at", "closed_by_event", "break_glass_count",
                    "updated_at")
