from django.contrib import admin

from .models import (
    AgentLog,
    ApiCallRecord,
    BatchRun,
    CreativeBrief,
    DesignTask,
    GateDecision,
    GeneratedImage,
    Notification,
    NotificationPreference,
    PackagingOutput,
)


@admin.register(BatchRun)
class BatchRunAdmin(admin.ModelAdmin):
    list_display = ("id", "brand", "campaign", "created_by", "created_at")
    list_filter = ("brand", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "kind", "task", "is_read", "created_at")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("recipient__username", "message")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "in_app", "email")


@admin.register(ApiCallRecord)
class ApiCallRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id", "task", "provider", "model", "operation",
        "input_tokens", "output_tokens", "image_count", "cost_usd", "created_at",
    )
    list_filter = ("provider", "model", "created_at")
    search_fields = ("operation", "task__task_text")


@admin.register(DesignTask)
class DesignTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "brand", "product", "campaign", "status",
                    "created_by", "assigned_to", "created_at")
    list_filter = ("status", "brand", "created_at")
    search_fields = ("task_text", "gate_1_notes", "gate_2_notes")


@admin.register(GateDecision)
class GateDecisionAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "gate", "decision", "decided_by", "decided_at")
    list_filter = ("gate", "decision", "decided_at")
    search_fields = ("notes", "task__task_text")


@admin.register(AgentLog)
class AgentLogAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "agent_name", "level", "timestamp")
    list_filter = ("level", "agent_name", "timestamp")
    search_fields = ("agent_name", "action")


@admin.register(CreativeBrief)
class CreativeBriefAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "created_at")
    search_fields = ("task__task_text",)


@admin.register(GeneratedImage)
class GeneratedImageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "task",
        "direction_name",
        "variation_number",
        "qa_passed",
        "is_approved",
        "created_at",
    )
    list_filter = ("qa_passed", "is_approved", "created_at")
    search_fields = ("direction_name", "prompt_used", "qa_notes")


@admin.register(PackagingOutput)
class PackagingOutputAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "approved_image", "is_final_approved", "created_at")
    list_filter = ("is_final_approved", "created_at")
    search_fields = ("task__task_text",)
