import uuid

from django.conf import settings
from django.db import models


class TemplateType(models.TextChoices):
    STRAIGHT_TUCK_END_CARTON = "straight_tuck_end_carton", "Straight Tuck-End Carton"
    # Milestone 12.1 — provisional styles (no measured reference file yet).
    REVERSE_TUCK_END_CARTON = "reverse_tuck_end_carton", "Reverse Tuck-End Carton"
    TUCK_TOP_AUTO_BOTTOM_CARTON = "tuck_top_auto_bottom_carton", "Tuck-Top Auto-Bottom Carton"
    # DECISION-018 side-seam parametric archetype, version 1.0 preset in
    # apps/dielines/geometry/side_seam.py.
    SKYNTE_FOUNDATION_TUCK_CARTON = "skynte_foundation_tuck_carton", "Skynte Foundation Tuck Carton (side-seam)"
    # C1 reconciliation: these two were registered and renderable but
    # not enumerable, so some code paths could reach them and others
    # could not. A registry/enum agreement test now pins the two lists
    # together.
    ECMA_A20_20_01_01_STE_CARTON = "ecma_a20_20_01_01_ste_carton", "ECMA A20.20.01.01 STE Carton"
    REFERENCE_OPPOSED_TUCK_CARTON = "reference_opposed_tuck_carton", "Reference Opposed Tuck Carton"
    # D-D13-3 (CURRENT_DECISIONS.md, Day 13): the family counter display, registered 0.1 ⟪PROVISIONAL⟫ (never
    # production); solved by apps/dielines/geometry/counter_tray_header.py, not by the carton engine.
    COUNTER_TRAY_HEADER = "counter_tray_header", "Counter Tray with Header (provisional)"


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
    # Milestone 10.1 (audit H4): object-level authorization. Nullable because
    # agent-created jobs pre-date user ownership (roles arrive in Phase 11).
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dieline_jobs",
    )
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
    # Phase 2A-6 (section 4): the durable structural decision for this job —
    # WHICH template was chosen, at which version, from what evidence, with
    # which parameters, and whether a human confirmed it. DielineJob already
    # owns dieline specifications (template_type + input_json), so the
    # structural choice belongs here rather than in a new model; one additive
    # JSONField keeps the migration to a single ADD COLUMN.
    #
    # Shape (see services.structure_selection.build_structure_record):
    #   {template_id, template_version, parameters, source, confidence,
    #    reasons, assumptions, geometry_hash, confirmed_by, confirmed_at,
    #    dimension_reconciliation, generic_accepted}
    # Empty dict = a legacy job that predates the structural contract; those
    # keep their historical behavior and are never retro-confirmed.
    structure_selection = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list)
    svg_output_path = models.CharField(max_length=500, blank=True)
    ai_output_path = models.CharField(max_length=500, blank=True)
    pdf_output_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"DielineJob {self.id} ({self.template_type} / {self.scenario})"
