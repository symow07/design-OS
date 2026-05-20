from django.contrib import admin
from .models import DielineTemplate, DielineJob


@admin.register(DielineTemplate)
class DielineTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "template_type", "default_bleed_mm", "default_safe_margin_mm", "default_glue_tab_mm", "created_at")
    search_fields = ("name", "template_type", "description")


@admin.register(DielineJob)
class DielineJobAdmin(admin.ModelAdmin):
    list_display = ("id", "template_type", "scenario", "validation_status", "product", "created_at")
    search_fields = ("id", "template_type", "scenario", "validation_status")
