from django.contrib import admin

from .models import (
    AgentLog,
    CreativeBrief,
    DesignTask,
    GeneratedImage,
    PackagingOutput,
)


@admin.register(DesignTask)
class DesignTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "brand", "product", "campaign", "status", "created_at")
    list_filter = ("status", "brand", "created_at")
    search_fields = ("task_text", "gate_1_notes", "gate_2_notes")


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
