import uuid

import apps.intelligence.models
from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_bootstrapstate"),
        ("intelligence", "0004_human_assertion_projections"),
    ]

    operations = [
        migrations.CreateModel(
            name="GovernanceProjectionGeneration",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("projector_identifier", models.CharField(max_length=127)),
                ("projector_version", models.CharField(max_length=64)),
                ("projection_schema_version", models.CharField(max_length=64)),
                ("source_chain_head_hash", models.CharField(
                    blank=True, default="", max_length=64)),
                ("source_terminal_sequence", models.PositiveBigIntegerField(default=0)),
                ("projection_output_hash", models.CharField(
                    blank=True, default="", max_length=64)),
                ("status", models.CharField(choices=[
                    ("BUILDING", "Building"), ("VALIDATED", "Validated"),
                    ("PUBLISHED", "Published"), ("FAILED", "Failed"),
                    ("SUPERSEDED", "Superseded")], default="BUILDING", max_length=16)),
                ("evaluation_timestamp", models.DateTimeField()),
                ("started_at", models.DateTimeField(default=timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("event_count_examined", models.PositiveBigIntegerField(default=0)),
                ("projected_decision_count", models.PositiveBigIntegerField(default=0)),
                ("projection_row_count", models.PositiveBigIntegerField(default=0)),
                ("warning_count", models.PositiveBigIntegerField(default=0)),
                ("failure_count", models.PositiveBigIntegerField(default=0)),
                ("failure_summary", models.TextField(blank=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="GovernanceDecisionProjection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False,
                                        primary_key=True, serialize=False)),
                ("governance_type", models.CharField(choices=[
                    ("CANONICAL_BRAND_ASSET", "Canonical Brand Asset"),
                    ("PRIMARY_BRAND_PALETTE", "Primary Brand Palette")], max_length=32)),
                ("normalized_scope", models.JSONField(
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("governance_scope_hash", models.CharField(max_length=64)),
                ("effective_state", models.CharField(choices=[
                    ("ACTIVE", "Active"), ("REVOKED", "Revoked"),
                    ("SUPERSEDED", "Superseded"),
                    ("REVIEW_REQUIRED", "Review Required"), ("INVALID", "Invalid"),
                    ("EVIDENCE_INTEGRITY_BLOCKED", "Evidence Integrity Blocked")],
                    max_length=32)),
                ("source_sequence_number", models.PositiveBigIntegerField()),
                ("attestation_event_ids", models.JSONField(
                    default=list,
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("source_policy_id", models.CharField(max_length=127)),
                ("source_policy_version", models.CharField(max_length=64)),
                ("warning_codes", models.JSONField(
                    blank=True, default=list,
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("projection_metadata", models.JSONField(
                    blank=True, default=dict,
                    validators=[apps.intelligence.models._validate_bounded_json])),
                ("effective_from", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("projection_generation", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="decision_projections",
                    to="intelligence.governanceprojectiongeneration")),
                ("selected_corpus_item", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="governance_decision_projections",
                    to="intelligence.corpusitem")),
                ("source_final_decision_event", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="governance_decision_projections",
                    to="accounts.decisionevent")),
            ],
        ),
        migrations.CreateModel(
            name="GovernanceProjectionPublicationState",
            fields=[
                ("id", models.PositiveSmallIntegerField(
                    default=1, editable=False, primary_key=True, serialize=False)),
                ("published_chain_head_hash", models.CharField(
                    blank=True, default="", max_length=64)),
                ("published_terminal_sequence", models.PositiveBigIntegerField(default=0)),
                ("projector_identifier", models.CharField(max_length=127)),
                ("projector_version", models.CharField(max_length=64)),
                ("projection_schema_version", models.CharField(max_length=64)),
                ("published_at", models.DateTimeField()),
                ("current_generation", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="publication_state",
                    to="intelligence.governanceprojectiongeneration")),
            ],
        ),
        migrations.AddConstraint(
            model_name="governanceprojectiongeneration",
            constraint=models.CheckConstraint(check=models.Q(
                ("status__in", ("BUILDING", "VALIDATED", "PUBLISHED", "FAILED",
                                "SUPERSEDED"))), name="intel_gov_gen_status_valid"),
        ),
        migrations.AddConstraint(
            model_name="governanceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("source_chain_head_hash", ""),
                         ("source_terminal_sequence", 0))
                | (models.Q(("source_terminal_sequence__gt", 0))
                   & models.Q(("source_chain_head_hash__regex", "^[0-9a-f]{64}$")))),
                name="intel_gov_gen_checkpoint_valid"),
        ),
        migrations.AddConstraint(
            model_name="governanceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("projection_output_hash", ""))
                | models.Q(("projection_output_hash__regex", "^[0-9a-f]{64}$"))),
                name="intel_gov_gen_output_hash_valid"),
        ),
        migrations.AddConstraint(
            model_name="governanceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("event_count_examined__gte", 0))
                & models.Q(("projected_decision_count__gte", 0))
                & models.Q(("projection_row_count__gte", 0))
                & models.Q(("warning_count__gte", 0))
                & models.Q(("failure_count__gte", 0))),
                name="intel_gov_gen_counts_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="governanceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("completed_at__isnull", True))
                | models.Q(("completed_at__gte", models.F("started_at")))),
                name="intel_gov_gen_time_order"),
        ),
        migrations.AddConstraint(
            model_name="governanceprojectiongeneration",
            constraint=models.CheckConstraint(check=(
                models.Q(("published_at__isnull", True),
                         ("status__in", ("BUILDING", "VALIDATED")))
                | models.Q(("published_at__isnull", False),
                           ("status__in", ("PUBLISHED", "SUPERSEDED")))
                | models.Q(("published_at__isnull", True), ("status", "FAILED"))),
                name="intel_gov_gen_publish_state"),
        ),
        migrations.AddIndex(
            model_name="governanceprojectiongeneration",
            index=models.Index(fields=["status", "started_at"],
                               name="intel_gov_gen_status_idx"),
        ),
        migrations.AddIndex(
            model_name="governanceprojectiongeneration",
            index=models.Index(fields=["source_terminal_sequence",
                                       "source_chain_head_hash"],
                               name="intel_gov_gen_checkpoint_idx"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.CheckConstraint(check=models.Q(("governance_type__in", (
                "CANONICAL_BRAND_ASSET", "PRIMARY_BRAND_PALETTE"))),
                name="intel_gov_proj_type_valid"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.CheckConstraint(check=models.Q(("effective_state__in", (
                "ACTIVE", "REVOKED", "SUPERSEDED", "REVIEW_REQUIRED", "INVALID",
                "EVIDENCE_INTEGRITY_BLOCKED"))), name="intel_gov_proj_state_valid"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.CheckConstraint(check=models.Q(
                ("governance_scope_hash__regex", "^[0-9a-f]{64}$")),
                name="intel_gov_proj_scope_hash_valid"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.CheckConstraint(check=models.Q(
                ("source_sequence_number__gt", 0)),
                name="intel_gov_proj_sequence_valid"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.CheckConstraint(check=(
                ~models.Q(("effective_state", "ACTIVE"))
                | (models.Q(("source_final_decision_event__isnull", False))
                   & models.Q(("source_sequence_number__gt", 0))
                   & models.Q(("effective_from__isnull", False)))),
                name="intel_gov_proj_active_source"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.CheckConstraint(check=(
                models.Q(("revoked_at__isnull", True))
                | models.Q(("revoked_at__gte", models.F("effective_from")))),
                name="intel_gov_proj_revoked_order"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.UniqueConstraint(
                fields=("projection_generation", "source_final_decision_event"),
                name="intel_gov_proj_gen_event_uniq"),
        ),
        migrations.AddConstraint(
            model_name="governancedecisionprojection",
            constraint=models.UniqueConstraint(
                condition=models.Q(("effective_state", "ACTIVE")),
                fields=("projection_generation", "governance_type",
                        "governance_scope_hash"),
                name="intel_gov_proj_one_active_scope"),
        ),
        migrations.AddIndex(
            model_name="governancedecisionprojection",
            index=models.Index(fields=["projection_generation", "governance_type",
                                       "governance_scope_hash", "effective_state"],
                               name="intel_gov_proj_scope_idx"),
        ),
        migrations.AddIndex(
            model_name="governancedecisionprojection",
            index=models.Index(fields=["selected_corpus_item", "effective_state"],
                               name="intel_gov_proj_item_state_idx"),
        ),
        migrations.AddConstraint(
            model_name="governanceprojectionpublicationstate",
            constraint=models.CheckConstraint(check=models.Q(("id", 1)),
                                               name="intel_gov_pub_singleton"),
        ),
        migrations.AddConstraint(
            model_name="governanceprojectionpublicationstate",
            constraint=models.CheckConstraint(check=(
                models.Q(("published_chain_head_hash", ""),
                         ("published_terminal_sequence", 0))
                | (models.Q(("published_terminal_sequence__gt", 0))
                   & models.Q(("published_chain_head_hash__regex", "^[0-9a-f]{64}$")))),
                name="intel_gov_pub_checkpoint_valid"),
        ),
    ]
