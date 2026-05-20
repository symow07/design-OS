import uuid
from django.db import models


class TemplateType(models.TextChoices):
    STRAIGHT_TUCK_END_CARTON = "straight_tuck_end_carton", "Straight Tuck-End Carton"


class ValidationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VALID = "valid", "Valid"
    INVALID = "invalid", "Invalid"


class Scenario(models.TextChoices):
    A = "A", "A"
    B = "B", "B"


class DielineTemplate(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=120)
    template_type = models.CharField(max_length=60, choices=TemplateType.choices)
    description = models.TextField(blank=True)
    default_bleed_mm = models.DecimalField(max_digits=5, decimal_places=2, default=3.0)
    default_safe_margin_mm = models.DecimalField(max_digits=5, decimal_places=2, default=4.0)
    default_glue_tab_mm = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DielineJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        "core.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dieline_jobs",
    )
    template_type = models.CharField(max_length=60, choices=TemplateType.choices)
    scenario = models.CharField(max_length=1, choices=Scenario.choices)
    input_json = models.JSONField()
    extraction_result = models.JSONField(null=True, blank=True)
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    warnings = models.JSONField(default=list)
    svg_output_path = models.CharField(max_length=500, blank=True)
    ai_output_path = models.CharField(max_length=500, blank=True)
    pdf_output_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"DielineJob {self.id} ({self.template_type} / {self.scenario})"
