import uuid

import apps.intelligence.models
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0005_bootstrapstate"),
        ("intelligence", "0003_review_candidates"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntelligenceProjectionGeneration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("projector_identifier", models.CharField(max_length=127)),
                ("projector_version", models.CharField(max_length=64)),
                ("projection_schema_version", models.CharField(max_length=64)),
                ("source_chain_head_hash", models.CharField(blank=True, default="",
                                                             max_length=64)),
                ("source_terminal_sequence", models.PositiveBigIntegerField(default=0)),
                ("projection_output_hash", models.CharField(blank=True, default="",
                                                             max_length=64)),
                ("status", models.CharField(choices=[
                    ("BUILDING", "Building"), ("VALIDATED", "Validated"),
                    ("PUBLISHED", "Published"), ("FAILED", "Failed"),
                    ("SUPERSEDED", "Superseded")], default="BUILDING", max_length=16)),
                ("evaluation_timestamp", models.DateTimeField()),
                ("started_at", models.DateTimeField(default=timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("event_count_examined", models.PositiveBigIntegerField(default=0)),
                ("projected_item_count", models.PositiveBigIntegerField(default=0)),
                ("warning_count", models.PositiveBigIntegerField(default=0)),
                ("failure_count", models.PositiveBigIntegerField(default=0)),
                ("failure_summary", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="HumanAssertionProjection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("assertion_domain", models.CharField(max_length=64)),
                ("effective_state", models.CharField(choices=[
                    ("ASSERTED", "Asserted"),
                    ("EVIDENCE_SUFFICIENT", "Evidence Sufficient"),
                    ("EVIDENCE_INSUFFICIENT", "Evidence Insufficient"),
                    ("CLARIFICATION_REQUIRED", "Clarification Required"),
                    ("SUPERSEDED", "Superseded"),
                    ("REVIEW_REQUIRED", "Review Required"),
                    ("INVALID", "Invalid")], max_length=32)),
                ("asserted_label", models.CharField(blank=True, max_length=255)),
                ("normalized_value", models.JSONField(blank=True, default=dict,
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("explanation_summary", models.CharField(blank=True, max_length=1000)),
                ("source_sequence_number", models.PositiveBigIntegerField(blank=True,
                                                                           null=True)),
                ("source_policy_id", models.CharField(blank=True, max_length=127)),
                ("source_policy_version", models.CharField(blank=True, max_length=64)),
                ("source_role", models.CharField(blank=True, max_length=32)),
                ("evidence_assessment", models.CharField(choices=[
                    ("NONE", "None"),
                    ("EVIDENCE_SUFFICIENT", "Evidence Sufficient"),
                    ("EVIDENCE_INSUFFICIENT", "Evidence Insufficient"),
                    ("CLARIFICATION_REQUIRED", "Clarification Required"),
                    ("REVIEW_REQUIRED", "Review Required")], default="NONE",
                    max_length=32)),
                ("projection_metadata", models.JSONField(blank=True, default=dict,
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("effective_from", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("warning_codes", models.JSONField(blank=True, default=list,
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("corpus_item", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="human_assertion_projections", to="intelligence.corpusitem")),
                ("projection_generation", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="assertion_projections",
                    to="intelligence.intelligenceprojectiongeneration")),
                ("source_decision_event", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="human_assertion_projections", to="accounts.decisionevent")),
                ("source_reviewer", models.ForeignKey(blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="human_assertion_projections", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ProjectionPublicationState",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False,
                                                         primary_key=True, serialize=False)),
                ("published_chain_head_hash", models.CharField(blank=True, default="",
                                                                max_length=64)),
                ("published_terminal_sequence", models.PositiveBigIntegerField(default=0)),
                ("projector_identifier", models.CharField(max_length=127)),
                ("projector_version", models.CharField(max_length=64)),
                ("projection_schema_version", models.CharField(max_length=64)),
                ("published_at", models.DateTimeField()),
                ("current_generation", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="publication_state",
                    to="intelligence.intelligenceprojectiongeneration")),
            ],
        ),
        migrations.AddConstraint(
            model_name="intelligenceprojectiongeneration",
            constraint=models.CheckConstraint(check=models.Q(
                ("status__in", ("BUILDING", "VALIDATED", "PUBLISHED", "FAILED",
                                 "SUPERSEDED"))), name="intel_proj_gen_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="intelligenceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("source_chain_head_hash", ""), ("source_terminal_sequence", 0))
                | (models.Q(("source_terminal_sequence__gt", 0))
                   & models.Q(("source_chain_head_hash__regex", "^[0-9a-f]{64}$")))),
                name="intel_proj_gen_checkpoint_valid"),
        ),
        migrations.AddConstraint(
            model_name="intelligenceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("projection_output_hash", ""))
                | models.Q(("projection_output_hash__regex", "^[0-9a-f]{64}$"))),
                name="intel_proj_gen_output_hash_valid"),
        ),
        migrations.AddConstraint(
            model_name="intelligenceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("completed_at__isnull", True))
                | models.Q(("completed_at__gte", models.F("started_at")))),
                name="intel_proj_gen_time_order"),
        ),
        migrations.AddConstraint(
            model_name="intelligenceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("published_at__isnull", True),
                         ("status__in", ("BUILDING", "VALIDATED")))
                | models.Q(("published_at__isnull", False),
                           ("status__in", ("PUBLISHED", "SUPERSEDED")))
                | models.Q(("published_at__isnull", True), ("status", "FAILED"))),
                name="intel_proj_gen_publish_state"),
        ),
        migrations.AddIndex(
            model_name="intelligenceprojectiongeneration",
            index=models.Index(fields=["status", "started_at"],
                               name="intel_proj_gen_status_idx"),
        ),
        migrations.AddIndex(
            model_name="intelligenceprojectiongeneration",
            index=models.Index(fields=["source_terminal_sequence", "source_chain_head_hash"],
                               name="intel_proj_gen_checkpoint_idx"),
        ),
        migrations.AddConstraint(
            model_name="humanassertionprojection",
            constraint=models.CheckConstraint(check=models.Q(("effective_state__in", (
                "ASSERTED", "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT",
                "CLARIFICATION_REQUIRED", "SUPERSEDED", "REVIEW_REQUIRED", "INVALID"))),
                name="intel_assert_proj_state_valid"),
        ),
        migrations.AddConstraint(
            model_name="humanassertionprojection",
            constraint=models.CheckConstraint(check=models.Q(("evidence_assessment__in", (
                "NONE", "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT",
                "CLARIFICATION_REQUIRED", "REVIEW_REQUIRED"))),
                name="intel_assert_proj_evidence_valid"),
        ),
        migrations.AddConstraint(
            model_name="humanassertionprojection",
            constraint=models.CheckConstraint(check=(
                models.Q(("source_sequence_number__isnull", True))
                | models.Q(("source_sequence_number__gt", 0))),
                name="intel_assert_proj_sequence_valid"),
        ),
        migrations.AddConstraint(
            model_name="humanassertionprojection",
            constraint=models.CheckConstraint(check=(
                ~models.Q(("effective_state__in", (
                    "ASSERTED", "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT",
                    "CLARIFICATION_REQUIRED", "SUPERSEDED")))
                | (models.Q(("source_decision_event__isnull", False))
                   & models.Q(("source_sequence_number__isnull", False))
                   & models.Q(("effective_from__isnull", False)))),
                name="intel_assert_proj_source_required"),
        ),
        migrations.AddConstraint(
            model_name="humanassertionprojection",
            constraint=models.CheckConstraint(check=(
                models.Q(("expires_at__isnull", True))
                | models.Q(("effective_from__isnull", False))),
                name="intel_assert_proj_expiry_has_start"),
        ),
        migrations.AddConstraint(
            model_name="humanassertionprojection",
            constraint=models.CheckConstraint(check=(
                models.Q(("expires_at__isnull", True))
                | models.Q(("expires_at__gte", models.F("effective_from")))),
                name="intel_assert_proj_time_order"),
        ),
        migrations.AddConstraint(
            model_name="humanassertionprojection",
            constraint=models.UniqueConstraint(
                fields=("projection_generation", "corpus_item", "assertion_domain"),
                name="intel_assert_proj_gen_item_domain_uniq"),
        ),
        migrations.AddIndex(
            model_name="humanassertionprojection",
            index=models.Index(fields=["projection_generation", "corpus_item",
                                       "assertion_domain"],
                               name="intel_assert_proj_lookup_idx"),
        ),
        migrations.AddIndex(
            model_name="humanassertionprojection",
            index=models.Index(fields=["corpus_item", "assertion_domain", "effective_state"],
                               name="intel_assert_item_state_idx"),
        ),
        migrations.AddConstraint(
            model_name="projectionpublicationstate",
            constraint=models.CheckConstraint(check=models.Q(("id", 1)),
                                              name="intel_proj_pub_singleton"),
        ),
        migrations.AddConstraint(
            model_name="projectionpublicationstate",
            constraint=models.CheckConstraint(check=(
                models.Q(("published_chain_head_hash", ""),
                         ("published_terminal_sequence", 0))
                | (models.Q(("published_terminal_sequence__gt", 0))
                   & models.Q(("published_chain_head_hash__regex", "^[0-9a-f]{64}$")))),
                name="intel_proj_pub_checkpoint_valid"),
        ),
    ]
