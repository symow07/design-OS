import uuid

import apps.intelligence.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("intelligence", "0002_corpus_browser_foundation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewCandidate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("review_type", models.CharField(choices=[
                    ("HISTORICAL_MEMORY", "Historical Memory"),
                    ("DESIGN_ASSET", "Design Asset"),
                    ("FONT_TECHNICAL", "Font Technical"),
                    ("BRAND_IDENTITY", "Brand Identity"),
                    ("PALETTE_OBSERVATION", "Palette Observation"),
                ], max_length=32)),
                ("workflow_status", models.CharField(choices=[
                    ("OPEN", "Open"), ("CLAIMED", "Claimed"),
                    ("NEEDS_INFORMATION", "Needs Information"),
                    ("COMPLETED", "Completed"),
                    ("CLOSED_NO_DECISION", "Closed No Decision"),
                ], default="OPEN", max_length=24)),
                ("priority", models.PositiveSmallIntegerField(default=50)),
                ("assigned_at", models.DateTimeField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("review_manifest_id", models.CharField(max_length=127)),
                ("machine_confidence_summary", models.JSONField(
                    blank=True, default=dict,
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="intelligence_review_candidates",
                    to=settings.AUTH_USER_MODEL)),
                ("corpus_item", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="review_candidates", to="intelligence.corpusitem")),
                ("source_import_batch", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="review_candidates", to="intelligence.importbatch")),
            ],
        ),
        migrations.AddConstraint(
            model_name="reviewcandidate",
            constraint=models.CheckConstraint(check=models.Q(
                ("review_type__in", (
                    "HISTORICAL_MEMORY", "DESIGN_ASSET", "FONT_TECHNICAL",
                    "BRAND_IDENTITY", "PALETTE_OBSERVATION"))),
                name="intel_review_type_valid"),
        ),
        migrations.AddConstraint(
            model_name="reviewcandidate",
            constraint=models.CheckConstraint(check=models.Q(
                ("workflow_status__in", (
                    "OPEN", "CLAIMED", "NEEDS_INFORMATION", "COMPLETED",
                    "CLOSED_NO_DECISION"))), name="intel_review_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="reviewcandidate",
            constraint=models.CheckConstraint(
                check=models.Q(("priority__gte", 1), ("priority__lte", 100)),
                name="intel_review_priority_range"),
        ),
        migrations.AddConstraint(
            model_name="reviewcandidate",
            constraint=models.CheckConstraint(check=(
                models.Q(("assigned_at__isnull", True), ("assigned_to__isnull", True))
                | models.Q(("assigned_at__isnull", False),
                           ("assigned_to__isnull", False))),
                name="intel_review_assignment_pair"),
        ),
        migrations.AddConstraint(
            model_name="reviewcandidate",
            constraint=models.CheckConstraint(check=(
                ~models.Q(("workflow_status", "CLAIMED"))
                | models.Q(("assigned_to__isnull", False))),
                name="intel_review_claimed_assigned"),
        ),
        migrations.AddConstraint(
            model_name="reviewcandidate",
            constraint=models.UniqueConstraint(
                fields=("corpus_item", "review_type", "review_manifest_id"),
                name="intel_review_item_type_manifest_uniq"),
        ),
        migrations.AddIndex(
            model_name="reviewcandidate",
            index=models.Index(fields=["workflow_status", "review_type", "priority"],
                               name="intel_review_queue_idx"),
        ),
        migrations.AddIndex(
            model_name="reviewcandidate",
            index=models.Index(fields=["assigned_to", "workflow_status"],
                               name="intel_review_assignee_idx"),
        ),
    ]
