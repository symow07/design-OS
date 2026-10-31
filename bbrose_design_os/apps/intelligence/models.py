from __future__ import annotations

import json
import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .dataset_identifiers import SUPPORTED_DESIGN_ASSET_DATASET_IDENTIFIERS

SHA256_RE = r"^[0-9a-f]{64}$"
_LOCATOR_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_PROJECTION_WRITE_TOKEN = object()
_GOVERNANCE_PROJECTION_WRITE_TOKEN = object()


def _validate_locator(value, depth=0):
    if depth > 8:
        raise ValidationError("locator nesting exceeds 8 levels")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not _LOCATOR_KEY.fullmatch(key):
                raise ValidationError("locator keys must be bounded identifiers")
            _validate_locator(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _validate_locator(child, depth + 1)
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValidationError("locator contains an unsupported value")
    if depth == 0:
        if not isinstance(value, dict):
            raise ValidationError("locator must be a structured object")
        if len(json.dumps(value, sort_keys=True, separators=(",", ":"))) > 8192:
            raise ValidationError("locator exceeds 8192 bytes")


def _validate_bounded_json(value):
    if not isinstance(value, (dict, list)):
        raise ValidationError("value must be a structured object or list")
    wrapper = value if isinstance(value, dict) else {"items": value}
    _validate_locator(wrapper)


def _validate_embedding_vector(vector, expected_dimension):
    """A stored embedding is a numeric array only: exact dimension, finite floats, no NaN
    and no Infinity. Non-finite values corrupt cosine similarity silently, so they are
    refused at persistence rather than discovered at read time."""
    import math
    if not isinstance(vector, list) or not vector:
        raise ValidationError("embedding vector must be a non-empty list")
    if len(vector) != expected_dimension:
        raise ValidationError(
            f"embedding dimension {len(vector)} != expected {expected_dimension}")
    for component in vector:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise ValidationError("embedding components must be numbers")
        if not math.isfinite(component):
            raise ValidationError("embedding components must be finite (no NaN/Infinity)")


class CorpusItem(models.Model):
    class Kind(models.TextChoices):
        HISTORICAL_DESIGN = "HISTORICAL_DESIGN"
        DESIGN_ASSET = "DESIGN_ASSET"
        FONT = "FONT"
        BRAND_ASSET = "BRAND_ASSET"
        BRAND_PALETTE = "BRAND_PALETTE"
        PRODUCT_FAMILY = "PRODUCT_FAMILY"
        BRAND_RULE = "BRAND_RULE"

    class Lifecycle(models.TextChoices):
        ACTIVE = "ACTIVE"
        RETIRED = "RETIRED"
        QUARANTINED = "QUARANTINED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_kind = models.CharField(max_length=32, choices=Kind.choices)
    external_key = models.CharField(max_length=255)
    lifecycle_state = models.CharField(
        max_length=16, choices=Lifecycle.choices, default=Lifecycle.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(item_kind__in=(
                "HISTORICAL_DESIGN", "DESIGN_ASSET", "FONT", "BRAND_ASSET",
                "BRAND_PALETTE", "PRODUCT_FAMILY", "BRAND_RULE")),
                                   name="intel_item_kind_valid"),
            models.CheckConstraint(check=Q(lifecycle_state__in=(
                "ACTIVE", "RETIRED", "QUARANTINED")),
                                   name="intel_item_lifecycle_valid"),
            models.UniqueConstraint(
                fields=("item_kind", "external_key"), name="intel_item_kind_ext_key_uniq"),
        ]
        indexes = [models.Index(fields=("item_kind", "external_key"),
                                name="intel_item_kind_key_idx")]


class SourceArtifact(models.Model):
    class SourceType(models.TextChoices):
        FILE = "FILE"
        JSON = "JSON"
        JSONL = "JSONL"
        ARCHIVE = "ARCHIVE"
        FONT = "FONT"
        OTHER = "OTHER"

    class Availability(models.TextChoices):
        AVAILABLE = "AVAILABLE"
        MISSING = "MISSING"
        ARCHIVED = "ARCHIVED"
        UNKNOWN = "UNKNOWN"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_identifier = models.CharField(max_length=255)
    source_location = models.TextField()
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    media_type = models.CharField(max_length=127, blank=True)
    sha256 = models.CharField(max_length=64)
    byte_size = models.BigIntegerField(null=True, blank=True)
    source_modified_at = models.DateTimeField(null=True, blank=True)
    parser_identifier = models.CharField(max_length=127)
    parser_version = models.CharField(max_length=64)
    source_schema_version = models.CharField(max_length=64)
    first_observed_at = models.DateTimeField(default=timezone.now)
    imported_at = models.DateTimeField(default=timezone.now)
    supersedes_source_artifact = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="superseded_by")
    availability_state = models.CharField(
        max_length=16, choices=Availability.choices, default=Availability.UNKNOWN)

    @property
    def content_identity(self):
        return self.sha256

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(source_type__in=(
                "FILE", "JSON", "JSONL", "ARCHIVE", "FONT", "OTHER")),
                                   name="intel_source_type_valid"),
            models.CheckConstraint(check=Q(availability_state__in=(
                "AVAILABLE", "MISSING", "ARCHIVED", "UNKNOWN")),
                                   name="intel_source_availability_valid"),
            models.CheckConstraint(check=Q(sha256__regex=SHA256_RE),
                                   name="intel_source_sha256_valid"),
            models.CheckConstraint(check=Q(byte_size__isnull=True) | Q(byte_size__gte=0),
                                   name="intel_source_size_nonnegative"),
            models.CheckConstraint(
                check=~Q(supersedes_source_artifact=F("id")),
                name="intel_source_not_self_supersede"),
            models.UniqueConstraint(fields=("source_identifier", "sha256"),
                                    name="intel_source_identifier_hash_uniq"),
        ]
        indexes = [
            models.Index(fields=("sha256", "source_identifier"),
                         name="intel_source_hash_id_idx"),
        ]


class EvidenceReference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.PROTECT, related_name="evidence_references")
    source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="evidence_references")
    evidence_kind = models.CharField(max_length=64)
    locator = models.JSONField(validators=[_validate_locator])
    locator_schema_version = models.CharField(max_length=64)
    observed_value = models.TextField(blank=True)
    evidence_hash = models.CharField(max_length=64)
    is_test_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        from .locator_schemas import normalize_locator
        self.locator = normalize_locator(self.locator_schema_version, self.locator)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [models.CheckConstraint(
            check=Q(evidence_hash__regex=SHA256_RE), name="intel_evidence_hash_valid")]
        indexes = [models.Index(fields=("corpus_item", "source_artifact"),
                                name="intel_evidence_item_src_idx")]


class ProvenanceRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_item = models.ForeignKey(
        CorpusItem, null=True, blank=True, on_delete=models.PROTECT,
        related_name="provenance_records")
    source_artifact = models.ForeignKey(
        SourceArtifact, null=True, blank=True, on_delete=models.PROTECT,
        related_name="provenance_records")
    provenance_type = models.CharField(max_length=64)
    source_organization = models.CharField(max_length=255, blank=True)
    source_package = models.CharField(max_length=255, blank=True)
    acquisition_reference = models.CharField(max_length=255, blank=True)
    observed_licence_file_reference = models.CharField(max_length=255, blank=True)
    acquisition_timestamp = models.DateTimeField(null=True, blank=True)
    raw_statement = models.TextField(blank=True)
    normalized_machine_interpretation = models.JSONField(default=dict, blank=True)
    confidence = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(corpus_item__isnull=False) | Q(source_artifact__isnull=False),
                name="intel_provenance_has_subject"),
            models.CheckConstraint(
                check=Q(confidence__isnull=True) | (Q(confidence__gte=0) & Q(confidence__lte=1)),
                name="intel_provenance_confidence_range"),
        ]


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        RUNNING = "RUNNING"
        COMPLETED = "COMPLETED"
        COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    importer_identifier = models.CharField(max_length=127)
    importer_version = models.CharField(max_length=64)
    configuration_hash = models.CharField(max_length=64)
    source_manifest_hash = models.CharField(max_length=64)
    scope = models.JSONField(default=dict)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_records = models.PositiveBigIntegerField(default=0)
    imported_records = models.PositiveBigIntegerField(default=0)
    unchanged_records = models.PositiveBigIntegerField(default=0)
    changed_records = models.PositiveBigIntegerField(default=0)
    skipped_records = models.PositiveBigIntegerField(default=0)
    quarantined_records = models.PositiveBigIntegerField(default=0)
    failed_records = models.PositiveBigIntegerField(default=0)
    failure_summary = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(status__in=(
                "RUNNING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED")),
                                   name="intel_batch_status_valid"),
            models.CheckConstraint(check=Q(configuration_hash__regex=SHA256_RE),
                                   name="intel_batch_config_hash_valid"),
            models.CheckConstraint(check=Q(source_manifest_hash__regex=SHA256_RE),
                                   name="intel_batch_manifest_hash_valid"),
            models.CheckConstraint(
                check=Q(completed_at__isnull=True) | Q(completed_at__gte=F("started_at")),
                name="intel_batch_time_order"),
        ]
        indexes = [models.Index(
            fields=("status", "started_at"), name="intel_batch_open_failed_idx",
            condition=Q(status__in=("RUNNING", "FAILED")))]


class ImportRecord(models.Model):
    class Disposition(models.TextChoices):
        CREATED = "CREATED"
        UNCHANGED = "UNCHANGED"
        NEW_VERSION = "NEW_VERSION"
        SKIPPED = "SKIPPED"
        QUARANTINED = "QUARANTINED"
        FAILED = "FAILED"
        OUT_OF_SCOPE = "OUT_OF_SCOPE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    import_batch = models.ForeignKey(
        ImportBatch, on_delete=models.PROTECT, related_name="records")
    stable_source_record_key = models.CharField(max_length=512)
    source_record_hash = models.CharField(max_length=64)
    source_artifact = models.ForeignKey(
        SourceArtifact, null=True, blank=True, on_delete=models.PROTECT,
        related_name="import_records")
    corpus_item = models.ForeignKey(
        CorpusItem, null=True, blank=True, on_delete=models.PROTECT,
        related_name="import_records")
    disposition = models.CharField(max_length=16, choices=Disposition.choices)
    prior_import_record = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="later_records")
    parser_version = models.CharField(max_length=64)
    source_schema_version = models.CharField(max_length=64)
    reconciliation_details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(disposition__in=(
                "CREATED", "UNCHANGED", "NEW_VERSION", "SKIPPED", "QUARANTINED",
                "FAILED", "OUT_OF_SCOPE")),
                                   name="intel_record_disposition_valid"),
            models.CheckConstraint(check=Q(source_record_hash__regex=SHA256_RE),
                                   name="intel_record_hash_valid"),
            models.CheckConstraint(check=~Q(prior_import_record=F("id")),
                                   name="intel_record_not_self_prior"),
            models.UniqueConstraint(fields=("import_batch", "stable_source_record_key"),
                                    name="intel_record_batch_key_uniq"),
        ]
        indexes = [models.Index(
            fields=("stable_source_record_key", "source_record_hash", "disposition"),
            name="intel_record_key_hash_disp_idx")]


class ReviewCandidate(models.Model):
    """Workflow coordination only; human conclusions live in signed DecisionEvents."""

    class ReviewType(models.TextChoices):
        HISTORICAL_MEMORY = "HISTORICAL_MEMORY"
        DESIGN_ASSET = "DESIGN_ASSET"
        FONT_TECHNICAL = "FONT_TECHNICAL"
        BRAND_IDENTITY = "BRAND_IDENTITY"
        PALETTE_OBSERVATION = "PALETTE_OBSERVATION"

    class Status(models.TextChoices):
        OPEN = "OPEN"
        CLAIMED = "CLAIMED"
        NEEDS_INFORMATION = "NEEDS_INFORMATION"
        COMPLETED = "COMPLETED"
        CLOSED_NO_DECISION = "CLOSED_NO_DECISION"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.PROTECT, related_name="review_candidates")
    review_type = models.CharField(max_length=32, choices=ReviewType.choices)
    workflow_status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.OPEN)
    priority = models.PositiveSmallIntegerField(default=50)
    assigned_to = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.PROTECT,
        related_name="intelligence_review_candidates")
    assigned_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    source_import_batch = models.ForeignKey(
        ImportBatch, null=True, blank=True, on_delete=models.PROTECT,
        related_name="review_candidates")
    review_manifest_id = models.CharField(max_length=127)
    machine_confidence_summary = models.JSONField(
        default=dict, blank=True, validators=[_validate_bounded_json])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(review_type__in=(
                    "HISTORICAL_MEMORY", "DESIGN_ASSET", "FONT_TECHNICAL",
                    "BRAND_IDENTITY", "PALETTE_OBSERVATION")),
                name="intel_review_type_valid"),
            models.CheckConstraint(
                check=Q(workflow_status__in=(
                    "OPEN", "CLAIMED", "NEEDS_INFORMATION", "COMPLETED",
                    "CLOSED_NO_DECISION")), name="intel_review_status_valid"),
            models.CheckConstraint(
                check=Q(priority__gte=1) & Q(priority__lte=100),
                name="intel_review_priority_range"),
            models.CheckConstraint(
                check=(Q(assigned_to__isnull=True, assigned_at__isnull=True)
                       | Q(assigned_to__isnull=False, assigned_at__isnull=False)),
                name="intel_review_assignment_pair"),
            models.CheckConstraint(
                check=~Q(workflow_status="CLAIMED") | Q(assigned_to__isnull=False),
                name="intel_review_claimed_assigned"),
            models.UniqueConstraint(
                fields=("corpus_item", "review_type", "review_manifest_id"),
                name="intel_review_item_type_manifest_uniq"),
        ]
        indexes = [
            models.Index(
                fields=("workflow_status", "review_type", "priority"),
                name="intel_review_queue_idx"),
            models.Index(
                fields=("assigned_to", "workflow_status"),
                name="intel_review_assignee_idx"),
        ]


class IntelligenceProjectionGeneration(models.Model):
    class Status(models.TextChoices):
        BUILDING = "BUILDING"
        VALIDATED = "VALIDATED"
        PUBLISHED = "PUBLISHED"
        FAILED = "FAILED"
        SUPERSEDED = "SUPERSEDED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projector_identifier = models.CharField(max_length=127)
    projector_version = models.CharField(max_length=64)
    projection_schema_version = models.CharField(max_length=64)
    source_chain_head_hash = models.CharField(max_length=64, blank=True, default="")
    source_terminal_sequence = models.PositiveBigIntegerField(default=0)
    projection_output_hash = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.BUILDING)
    evaluation_timestamp = models.DateTimeField()
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    event_count_examined = models.PositiveBigIntegerField(default=0)
    projected_item_count = models.PositiveBigIntegerField(default=0)
    warning_count = models.PositiveBigIntegerField(default=0)
    failure_count = models.PositiveBigIntegerField(default=0)
    failure_summary = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        write_token = kwargs.pop("_projection_write_token", None)
        if (self._state.adding and self.status != self.Status.BUILDING
                and write_token is not _PROJECTION_WRITE_TOKEN):
            raise ValidationError(
                "only the projector service may create a completed generation")
        if (not self._state.adding
                and write_token is not _PROJECTION_WRITE_TOKEN):
            raise ValidationError(
                "projection generation transitions are projector-service managed")
        if not self._state.adding:
            prior = type(self).objects.filter(pk=self.pk).values(
                "completed_at", "status").first()
            if (prior and prior["completed_at"] is not None
                    and not (
                        prior["status"] == self.Status.PUBLISHED
                        and self.status == self.Status.SUPERSEDED
                        and write_token is _PROJECTION_WRITE_TOKEN)):
                raise ValidationError(
                    "completed projection generations are immutable; lifecycle changes "
                    "are owned by the atomic projector publication service")
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(status__in=(
                "BUILDING", "VALIDATED", "PUBLISHED", "FAILED", "SUPERSEDED")),
                name="intel_proj_gen_status_valid"),
            models.CheckConstraint(
                check=(Q(source_terminal_sequence=0, source_chain_head_hash="")
                       | (Q(source_terminal_sequence__gt=0)
                          & Q(source_chain_head_hash__regex=SHA256_RE))),
                name="intel_proj_gen_checkpoint_valid"),
            models.CheckConstraint(
                check=Q(projection_output_hash="")
                | Q(projection_output_hash__regex=SHA256_RE),
                name="intel_proj_gen_output_hash_valid"),
            models.CheckConstraint(
                check=Q(completed_at__isnull=True) | Q(completed_at__gte=F("started_at")),
                name="intel_proj_gen_time_order"),
            models.CheckConstraint(
                check=(Q(status__in=("BUILDING", "VALIDATED"), published_at__isnull=True)
                       | Q(status__in=("PUBLISHED", "SUPERSEDED"),
                           published_at__isnull=False)
                       | Q(status="FAILED", published_at__isnull=True)),
                name="intel_proj_gen_publish_state"),
        ]
        indexes = [
            models.Index(fields=("status", "started_at"), name="intel_proj_gen_status_idx"),
            models.Index(
                fields=("source_terminal_sequence", "source_chain_head_hash"),
                name="intel_proj_gen_checkpoint_idx"),
        ]


class _ImmutableProjectionRowQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(
            "human assertion projections are immutable; rebuild a generation")

    def delete(self):
        raise ValidationError(
            "human assertion projections are immutable historical records")


class HumanAssertionProjection(models.Model):
    class EffectiveState(models.TextChoices):
        ASSERTED = "ASSERTED"
        EVIDENCE_SUFFICIENT = "EVIDENCE_SUFFICIENT"
        EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
        CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
        SUPERSEDED = "SUPERSEDED"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"
        INVALID = "INVALID"

    class EvidenceAssessment(models.TextChoices):
        NONE = "NONE"
        EVIDENCE_SUFFICIENT = "EVIDENCE_SUFFICIENT"
        EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
        CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projection_generation = models.ForeignKey(
        IntelligenceProjectionGeneration, on_delete=models.PROTECT,
        related_name="assertion_projections")
    corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.PROTECT, related_name="human_assertion_projections")
    assertion_domain = models.CharField(max_length=64)
    effective_state = models.CharField(max_length=32, choices=EffectiveState.choices)
    asserted_label = models.CharField(max_length=255, blank=True)
    normalized_value = models.JSONField(
        default=dict, blank=True, validators=[_validate_bounded_json])
    explanation_summary = models.CharField(max_length=1000, blank=True)
    source_decision_event = models.ForeignKey(
        "accounts.DecisionEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="human_assertion_projections")
    source_sequence_number = models.PositiveBigIntegerField(null=True, blank=True)
    source_policy_id = models.CharField(max_length=127, blank=True)
    source_policy_version = models.CharField(max_length=64, blank=True)
    source_reviewer = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.PROTECT,
        related_name="human_assertion_projections")
    source_role = models.CharField(max_length=32, blank=True)
    evidence_assessment = models.CharField(
        max_length=32, choices=EvidenceAssessment.choices, default=EvidenceAssessment.NONE)
    projection_metadata = models.JSONField(
        default=dict, blank=True, validators=[_validate_bounded_json])
    effective_from = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    warning_codes = models.JSONField(
        default=list, blank=True, validators=[_validate_bounded_json])
    created_at = models.DateTimeField(auto_now_add=True)

    objects = _ImmutableProjectionRowQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "human assertion projections are immutable derived rows; rebuild a "
                "generation instead of editing a row")
        generation_status = IntelligenceProjectionGeneration.objects.filter(
            pk=self.projection_generation_id).values_list("status", flat=True).first()
        if generation_status != IntelligenceProjectionGeneration.Status.BUILDING:
            raise ValidationError(
                "projection rows may be created only inside an unpublished build")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "human assertion projections are immutable historical records")

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(effective_state__in=(
                "ASSERTED", "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT",
                "CLARIFICATION_REQUIRED", "SUPERSEDED", "REVIEW_REQUIRED", "INVALID")),
                name="intel_assert_proj_state_valid"),
            models.CheckConstraint(check=Q(evidence_assessment__in=(
                "NONE", "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT",
                "CLARIFICATION_REQUIRED", "REVIEW_REQUIRED")),
                name="intel_assert_proj_evidence_valid"),
            models.CheckConstraint(
                check=Q(source_sequence_number__isnull=True)
                | Q(source_sequence_number__gt=0),
                name="intel_assert_proj_sequence_valid"),
            models.CheckConstraint(
                check=(~Q(effective_state__in=(
                    "ASSERTED", "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT",
                    "CLARIFICATION_REQUIRED", "SUPERSEDED"))
                       | (Q(source_decision_event__isnull=False)
                          & Q(source_sequence_number__isnull=False)
                          & Q(effective_from__isnull=False))),
                name="intel_assert_proj_source_required"),
            models.CheckConstraint(
                check=Q(expires_at__isnull=True) | Q(effective_from__isnull=False),
                name="intel_assert_proj_expiry_has_start"),
            models.CheckConstraint(
                check=Q(expires_at__isnull=True) | Q(expires_at__gte=F("effective_from")),
                name="intel_assert_proj_time_order"),
            models.UniqueConstraint(
                fields=("projection_generation", "corpus_item", "assertion_domain"),
                name="intel_assert_proj_gen_item_domain_uniq"),
        ]
        indexes = [
            models.Index(
                fields=("projection_generation", "corpus_item", "assertion_domain"),
                name="intel_assert_proj_lookup_idx"),
            models.Index(
                fields=("corpus_item", "assertion_domain", "effective_state"),
                name="intel_assert_item_state_idx"),
        ]


class _PublicationStateQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(
            "publication authority is managed only by the atomic projector service")

    def delete(self):
        raise ValidationError("the projection publication singleton is permanent")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError(
            "publication authority is managed only by the atomic projector service")


class ProjectionPublicationState(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    current_generation = models.OneToOneField(
        IntelligenceProjectionGeneration, on_delete=models.PROTECT,
        related_name="publication_state")
    published_chain_head_hash = models.CharField(max_length=64, blank=True, default="")
    published_terminal_sequence = models.PositiveBigIntegerField(default=0)
    projector_identifier = models.CharField(max_length=127)
    projector_version = models.CharField(max_length=64)
    projection_schema_version = models.CharField(max_length=64)
    published_at = models.DateTimeField()

    objects = _PublicationStateQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if kwargs.pop("_projection_write_token", None) is not _PROJECTION_WRITE_TOKEN:
            raise ValidationError(
                "publication authority is managed only by the atomic projector service")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("the projection publication singleton is permanent")

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(id=1), name="intel_proj_pub_singleton"),
            models.CheckConstraint(
                check=(Q(published_terminal_sequence=0, published_chain_head_hash="")
                       | (Q(published_terminal_sequence__gt=0)
                          & Q(published_chain_head_hash__regex=SHA256_RE))),
                name="intel_proj_pub_checkpoint_valid"),
        ]


class GovernanceProjectionGeneration(models.Model):
    """Immutable lifecycle record for one shadow-built governance projection."""

    class Status(models.TextChoices):
        BUILDING = "BUILDING"
        VALIDATED = "VALIDATED"
        PUBLISHED = "PUBLISHED"
        FAILED = "FAILED"
        SUPERSEDED = "SUPERSEDED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projector_identifier = models.CharField(max_length=127)
    projector_version = models.CharField(max_length=64)
    projection_schema_version = models.CharField(max_length=64)
    source_chain_head_hash = models.CharField(max_length=64, blank=True, default="")
    source_terminal_sequence = models.PositiveBigIntegerField(default=0)
    projection_output_hash = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.BUILDING)
    evaluation_timestamp = models.DateTimeField()
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    event_count_examined = models.PositiveBigIntegerField(default=0)
    projected_decision_count = models.PositiveBigIntegerField(default=0)
    projection_row_count = models.PositiveBigIntegerField(default=0)
    warning_count = models.PositiveBigIntegerField(default=0)
    failure_count = models.PositiveBigIntegerField(default=0)
    failure_summary = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        write_token = kwargs.pop("_governance_projection_write_token", None)
        if (self._state.adding and self.status != self.Status.BUILDING
                and write_token is not _GOVERNANCE_PROJECTION_WRITE_TOKEN):
            raise ValidationError(
                "only the governance projector may create a completed generation")
        if (not self._state.adding
                and write_token is not _GOVERNANCE_PROJECTION_WRITE_TOKEN):
            raise ValidationError(
                "governance generation transitions are projector-service managed")
        if not self._state.adding:
            prior = type(self).objects.filter(pk=self.pk).values(
                "completed_at", "status").first()
            if (prior and prior["completed_at"] is not None
                    and not (prior["status"] == self.Status.PUBLISHED
                             and self.status == self.Status.SUPERSEDED
                             and write_token is _GOVERNANCE_PROJECTION_WRITE_TOKEN)):
                raise ValidationError(
                    "completed governance generations are immutable")
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(status__in=(
                "BUILDING", "VALIDATED", "PUBLISHED", "FAILED", "SUPERSEDED")),
                name="intel_gov_gen_status_valid"),
            models.CheckConstraint(
                check=(Q(source_terminal_sequence=0, source_chain_head_hash="")
                       | (Q(source_terminal_sequence__gt=0)
                          & Q(source_chain_head_hash__regex=SHA256_RE))),
                name="intel_gov_gen_checkpoint_valid"),
            models.CheckConstraint(
                check=Q(projection_output_hash="")
                | Q(projection_output_hash__regex=SHA256_RE),
                name="intel_gov_gen_output_hash_valid"),
            models.CheckConstraint(
                check=(Q(event_count_examined__gte=0)
                       & Q(projected_decision_count__gte=0)
                       & Q(projection_row_count__gte=0)
                       & Q(warning_count__gte=0)
                       & Q(failure_count__gte=0)),
                name="intel_gov_gen_counts_nonnegative"),
            models.CheckConstraint(
                check=Q(completed_at__isnull=True) | Q(completed_at__gte=F("started_at")),
                name="intel_gov_gen_time_order"),
            models.CheckConstraint(
                check=(Q(status__in=("BUILDING", "VALIDATED"), published_at__isnull=True)
                       | Q(status__in=("PUBLISHED", "SUPERSEDED"),
                           published_at__isnull=False)
                       | Q(status="FAILED", published_at__isnull=True)),
                name="intel_gov_gen_publish_state"),
        ]
        indexes = [
            models.Index(fields=("status", "started_at"), name="intel_gov_gen_status_idx"),
            models.Index(
                fields=("source_terminal_sequence", "source_chain_head_hash"),
                name="intel_gov_gen_checkpoint_idx"),
        ]


class _ImmutableGovernanceProjectionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(
            "governance projections are immutable; rebuild a generation")

    def delete(self):
        raise ValidationError("governance projections are immutable historical records")


class GovernanceDecisionProjection(models.Model):
    class GovernanceType(models.TextChoices):
        CANONICAL_BRAND_ASSET = "CANONICAL_BRAND_ASSET"
        PRIMARY_BRAND_PALETTE = "PRIMARY_BRAND_PALETTE"

    class EffectiveState(models.TextChoices):
        ACTIVE = "ACTIVE"
        REVOKED = "REVOKED"
        SUPERSEDED = "SUPERSEDED"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"
        INVALID = "INVALID"
        EVIDENCE_INTEGRITY_BLOCKED = "EVIDENCE_INTEGRITY_BLOCKED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projection_generation = models.ForeignKey(
        GovernanceProjectionGeneration, on_delete=models.PROTECT,
        related_name="decision_projections")
    governance_type = models.CharField(max_length=32, choices=GovernanceType.choices)
    normalized_scope = models.JSONField(validators=[_validate_bounded_json])
    governance_scope_hash = models.CharField(max_length=64)
    selected_corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.PROTECT,
        related_name="governance_decision_projections")
    effective_state = models.CharField(max_length=32, choices=EffectiveState.choices)
    source_final_decision_event = models.ForeignKey(
        "accounts.DecisionEvent", on_delete=models.PROTECT,
        related_name="governance_decision_projections")
    source_sequence_number = models.PositiveBigIntegerField()
    attestation_event_ids = models.JSONField(
        default=list, validators=[_validate_bounded_json])
    source_policy_id = models.CharField(max_length=127)
    source_policy_version = models.CharField(max_length=64)
    warning_codes = models.JSONField(
        default=list, blank=True, validators=[_validate_bounded_json])
    projection_metadata = models.JSONField(
        default=dict, blank=True, validators=[_validate_bounded_json])
    effective_from = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = _ImmutableGovernanceProjectionQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                "governance projections are immutable derived rows")
        status = GovernanceProjectionGeneration.objects.filter(
            pk=self.projection_generation_id).values_list("status", flat=True).first()
        if status != GovernanceProjectionGeneration.Status.BUILDING:
            raise ValidationError(
                "governance rows may be created only inside an unpublished build")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("governance projections are immutable historical records")

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(governance_type__in=(
                "CANONICAL_BRAND_ASSET", "PRIMARY_BRAND_PALETTE")),
                name="intel_gov_proj_type_valid"),
            models.CheckConstraint(check=Q(effective_state__in=(
                "ACTIVE", "REVOKED", "SUPERSEDED", "REVIEW_REQUIRED", "INVALID",
                "EVIDENCE_INTEGRITY_BLOCKED")),
                name="intel_gov_proj_state_valid"),
            models.CheckConstraint(
                check=Q(governance_scope_hash__regex=SHA256_RE),
                name="intel_gov_proj_scope_hash_valid"),
            models.CheckConstraint(
                check=Q(source_sequence_number__gt=0),
                name="intel_gov_proj_sequence_valid"),
            models.CheckConstraint(
                check=~Q(effective_state="ACTIVE")
                | (Q(source_final_decision_event__isnull=False)
                   & Q(source_sequence_number__gt=0)
                   & Q(effective_from__isnull=False)),
                name="intel_gov_proj_active_source"),
            models.CheckConstraint(
                check=Q(revoked_at__isnull=True) | Q(revoked_at__gte=F("effective_from")),
                name="intel_gov_proj_revoked_order"),
            models.UniqueConstraint(
                fields=("projection_generation", "source_final_decision_event"),
                name="intel_gov_proj_gen_event_uniq"),
            models.UniqueConstraint(
                fields=("projection_generation", "governance_type",
                        "governance_scope_hash"), condition=Q(effective_state="ACTIVE"),
                name="intel_gov_proj_one_active_scope"),
        ]
        indexes = [
            models.Index(
                fields=("projection_generation", "governance_type",
                        "governance_scope_hash", "effective_state"),
                name="intel_gov_proj_scope_idx"),
            models.Index(
                fields=("selected_corpus_item", "effective_state"),
                name="intel_gov_proj_item_state_idx"),
        ]


class _GovernancePublicationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(
            "governance publication is managed only by the projector service")

    def delete(self):
        raise ValidationError("the governance publication singleton is permanent")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError(
            "governance publication is managed only by the projector service")


class GovernanceProjectionPublicationState(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    current_generation = models.OneToOneField(
        GovernanceProjectionGeneration, on_delete=models.PROTECT,
        related_name="publication_state")
    published_chain_head_hash = models.CharField(max_length=64, blank=True, default="")
    published_terminal_sequence = models.PositiveBigIntegerField(default=0)
    projector_identifier = models.CharField(max_length=127)
    projector_version = models.CharField(max_length=64)
    projection_schema_version = models.CharField(max_length=64)
    published_at = models.DateTimeField()

    objects = _GovernancePublicationQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if kwargs.pop("_governance_projection_write_token", None) \
                is not _GOVERNANCE_PROJECTION_WRITE_TOKEN:
            raise ValidationError(
                "governance publication is managed only by the projector service")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("the governance publication singleton is permanent")

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(id=1), name="intel_gov_pub_singleton"),
            models.CheckConstraint(
                check=(Q(published_terminal_sequence=0, published_chain_head_hash="")
                       | (Q(published_terminal_sequence__gt=0)
                          & Q(published_chain_head_hash__regex=SHA256_RE))),
                name="intel_gov_pub_checkpoint_valid"),
        ]


class OperationalPermissionProjection(models.Model):
    class Permission(models.TextChoices):
        VISIBLE_IN_REVIEWER_SEARCH = "VISIBLE_IN_REVIEWER_SEARCH"
        RETRIEVAL = "RETRIEVAL"
        AUTOMATIC_USE = "AUTOMATIC_USE"
        EXPORT = "EXPORT"
        PRODUCTION = "PRODUCTION"

    class State(models.TextChoices):
        DENIED = "DENIED"
        ALLOWED = "ALLOWED"
        QUARANTINED = "QUARANTINED"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"
        EXPIRED = "EXPIRED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.PROTECT, related_name="permission_projections")
    permission_type = models.CharField(max_length=32, choices=Permission.choices)
    scope_type = models.CharField(max_length=64, blank=True, default="")
    scope_id = models.CharField(max_length=255, blank=True, default="")
    effective_state = models.CharField(
        max_length=20, choices=State.choices, default=State.DENIED)
    source_decision_event = models.ForeignKey(
        "accounts.DecisionEvent", null=True, blank=True, on_delete=models.PROTECT,
        related_name="operational_permission_projections")
    source_sequence_number = models.PositiveBigIntegerField(null=True, blank=True)
    projected_chain_head_hash = models.CharField(max_length=64, null=True, blank=True)
    projection_version = models.CharField(max_length=64)
    reason_code = models.CharField(max_length=64)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(permission_type__in=(
                "VISIBLE_IN_REVIEWER_SEARCH", "RETRIEVAL", "AUTOMATIC_USE", "EXPORT",
                "PRODUCTION")),
                                   name="intel_permission_type_valid"),
            models.CheckConstraint(check=Q(effective_state__in=(
                "DENIED", "ALLOWED", "QUARANTINED", "REVIEW_REQUIRED", "EXPIRED")),
                                   name="intel_permission_state_valid"),
            models.CheckConstraint(
                check=Q(projected_chain_head_hash__isnull=True)
                | Q(projected_chain_head_hash__regex=SHA256_RE),
                name="intel_permission_head_hash_valid"),
            models.UniqueConstraint(
                fields=("corpus_item", "permission_type", "scope_type", "scope_id"),
                name="intel_permission_item_type_scope_uniq"),
        ]
        indexes = [models.Index(
            fields=("corpus_item", "permission_type", "scope_type", "scope_id",
                    "effective_state"), name="intel_permission_lookup_idx")]


class SourceLocationObservation(models.Model):
    class Kind(models.TextChoices):
        REPOSITORY_RELATIVE = "REPOSITORY_RELATIVE"
        CONFIGURED_ROOT_RELATIVE = "CONFIGURED_ROOT_RELATIVE"
        ARCHIVE_MEMBER = "ARCHIVE_MEMBER"
        LOGICAL = "LOGICAL"

    class Availability(models.TextChoices):
        AVAILABLE = "AVAILABLE"
        MISSING = "MISSING"
        ARCHIVED = "ARCHIVED"
        UNKNOWN = "UNKNOWN"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="location_observations")
    observed_location = models.CharField(max_length=1024)
    location_kind = models.CharField(max_length=32, choices=Kind.choices)
    observed_at = models.DateTimeField(default=timezone.now)
    observed_by_import_record = models.ForeignKey(
        ImportRecord, null=True, blank=True, on_delete=models.PROTECT,
        related_name="source_location_observations")
    availability_state = models.CharField(
        max_length=16, choices=Availability.choices, default=Availability.UNKNOWN)
    location_metadata = models.JSONField(default=dict, blank=True,
                                         validators=[_validate_locator])
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(location_kind__in=(
                "REPOSITORY_RELATIVE", "CONFIGURED_ROOT_RELATIVE", "ARCHIVE_MEMBER",
                "LOGICAL")), name="intel_location_kind_valid"),
            models.CheckConstraint(check=Q(availability_state__in=(
                "AVAILABLE", "MISSING", "ARCHIVED", "UNKNOWN")),
                                   name="intel_location_avail_valid"),
            models.UniqueConstraint(
                fields=("source_artifact", "location_kind", "observed_location"),
                name="intel_location_artifact_path_uniq"),
        ]
        indexes = [models.Index(
            fields=("source_artifact", "observed_at"), name="intel_location_history_idx")]


class ObservedFact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.PROTECT, related_name="observed_facts")
    fact_type = models.CharField(max_length=64)
    normalized_value = models.JSONField(validators=[_validate_locator])
    raw_value = models.TextField(blank=True)
    value_schema_version = models.CharField(max_length=64)
    source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="observed_facts")
    evidence_reference = models.ForeignKey(
        EvidenceReference, null=True, blank=True, on_delete=models.PROTECT,
        related_name="observed_facts")
    importer_identifier = models.CharField(max_length=127)
    importer_version = models.CharField(max_length=64)
    fact_hash = models.CharField(max_length=64)
    observed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(fact_hash__regex=SHA256_RE),
                                   name="intel_fact_hash_valid"),
            models.UniqueConstraint(
                fields=("corpus_item", "fact_type", "source_artifact", "fact_hash"),
                name="intel_fact_item_type_src_hash_uniq"),
        ]
        indexes = [models.Index(
            fields=("corpus_item", "fact_type", "created_at"),
            name="intel_fact_item_type_idx")]


class MachineClassification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.PROTECT, related_name="machine_classifications")
    classification_type = models.CharField(max_length=64)
    label = models.CharField(max_length=255)
    confidence = models.DecimalField(max_digits=5, decimal_places=4)
    classifier_identifier = models.CharField(max_length=127)
    classifier_version = models.CharField(max_length=64)
    classification_schema_version = models.CharField(max_length=64)
    source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="machine_classifications")
    evidence_reference = models.ForeignKey(
        EvidenceReference, null=True, blank=True, on_delete=models.PROTECT,
        related_name="machine_classifications")
    structured_explanation = models.JSONField(default=dict, blank=True,
                                              validators=[_validate_locator])
    classification_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(confidence__gte=0) & Q(confidence__lte=1),
                name="intel_class_confidence_range"),
            models.CheckConstraint(check=Q(classification_hash__regex=SHA256_RE),
                                   name="intel_class_hash_valid"),
            models.UniqueConstraint(
                fields=("corpus_item", "classification_type", "source_artifact",
                        "classification_hash"),
                name="intel_class_item_type_src_hash_uniq"),
        ]
        indexes = [models.Index(
            fields=("corpus_item", "classification_type", "created_at"),
            name="intel_class_item_type_idx")]


class HistoricalDesignProfile(models.Model):
    class AuditStatus(models.TextChoices):
        MACHINE_AUDITED = "MACHINE_AUDITED"
        PARTIAL = "PARTIAL"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"

    REFERENCE_MEMORY_ONLY = "REFERENCE_MEMORY_ONLY"

    corpus_item = models.OneToOneField(
        CorpusItem, primary_key=True, on_delete=models.PROTECT,
        related_name="historical_design_profile")
    primary_source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="historical_design_profiles")
    display_title = models.CharField(max_length=255)
    page_artboard_count = models.PositiveIntegerField(default=0)
    extracted_design_unit_count = models.PositiveIntegerField(default=0)
    audit_status = models.CharField(max_length=24, choices=AuditStatus.choices)
    historical_period_observed = models.CharField(max_length=127, blank=True)
    product_family_machine_label = models.CharField(max_length=127, blank=True)
    reference_memory_policy = models.CharField(
        max_length=32, default=REFERENCE_MEMORY_ONLY, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(page_artboard_count__lte=100000),
                                   name="intel_hist_page_count_bounded"),
            models.CheckConstraint(check=Q(extracted_design_unit_count__lte=1000000),
                                   name="intel_hist_unit_count_bounded"),
            models.CheckConstraint(check=Q(audit_status__in=(
                "MACHINE_AUDITED", "PARTIAL", "REVIEW_REQUIRED")),
                                   name="intel_hist_audit_status_valid"),
            models.CheckConstraint(check=Q(reference_memory_policy="REFERENCE_MEMORY_ONLY"),
                                   name="intel_hist_reference_only"),
        ]


class DesignUnit(models.Model):
    class UnitType(models.TextChoices):
        SURFACE_ARTWORK = "SURFACE_ARTWORK"
        TECHNICAL_NOTES = "TECHNICAL_NOTES"
        PRODUCT_PHOTO = "PRODUCT_PHOTO"
        DIELINE_CANDIDATE = "DIELINE_CANDIDATE"
        SPEC_TABLE = "SPEC_TABLE"
        LEGAL_TEXT = "LEGAL_TEXT"
        UNKNOWN = "UNKNOWN"
        COLOR_PALETTE_STRIP = "COLOR_PALETTE_STRIP"
        BARCODE = "BARCODE"

    class ExtractionStatus(models.TextChoices):
        AUTO_CONFIDENT = "AUTO_CONFIDENT"
        AUTO_LOW_CONFIDENCE = "AUTO_LOW_CONFIDENCE"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"
        UNAVAILABLE = "UNAVAILABLE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    historical_design_profile = models.ForeignKey(
        HistoricalDesignProfile, on_delete=models.PROTECT, related_name="design_units")
    stable_unit_key = models.CharField(max_length=255)
    unit_type = models.CharField(max_length=32, choices=UnitType.choices)
    ordinal = models.PositiveIntegerField()
    source_page_artboard = models.PositiveIntegerField(null=True, blank=True)
    geometry_x = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    geometry_y = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    geometry_width = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True)
    geometry_height = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True)
    technical_summary = models.TextField(blank=True)
    extraction_status = models.CharField(max_length=24, choices=ExtractionStatus.choices)
    source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="design_units")
    evidence_reference = models.ForeignKey(
        EvidenceReference, on_delete=models.PROTECT, related_name="design_units")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(unit_type__in=(
                "SURFACE_ARTWORK", "TECHNICAL_NOTES", "PRODUCT_PHOTO",
                "DIELINE_CANDIDATE", "SPEC_TABLE", "LEGAL_TEXT", "UNKNOWN",
                "COLOR_PALETTE_STRIP", "BARCODE")), name="intel_unit_type_valid"),
            models.CheckConstraint(check=Q(extraction_status__in=(
                "AUTO_CONFIDENT", "AUTO_LOW_CONFIDENCE", "REVIEW_REQUIRED",
                "UNAVAILABLE")), name="intel_unit_extract_valid"),
            models.CheckConstraint(check=Q(ordinal__lte=1000000),
                                   name="intel_unit_ordinal_bounded"),
            models.CheckConstraint(
                check=Q(source_page_artboard__isnull=True)
                | Q(source_page_artboard__lte=100000),
                name="intel_unit_page_bounded"),
            models.CheckConstraint(
                check=(Q(geometry_x__isnull=True) | Q(geometry_x__gte=0))
                & (Q(geometry_y__isnull=True) | Q(geometry_y__gte=0))
                & (Q(geometry_width__isnull=True) | Q(geometry_width__gte=0))
                & (Q(geometry_height__isnull=True) | Q(geometry_height__gte=0)),
                name="intel_unit_geometry_nonnegative"),
            models.UniqueConstraint(
                fields=("historical_design_profile", "stable_unit_key"),
                name="intel_unit_profile_key_uniq"),
        ]
        indexes = [models.Index(
            fields=("historical_design_profile", "ordinal"),
            name="intel_unit_profile_ordinal_idx")]


class DesignAssetProfile(models.Model):
    class CandidateKind(models.TextChoices):
        MOTIF = "MOTIF"
        BACKGROUND = "BACKGROUND"
        ILLUSTRATION = "ILLUSTRATION"
        LOGO_CANDIDATE = "LOGO_CANDIDATE"
        PATTERN = "PATTERN"
        PHOTO = "PHOTO"
        UNKNOWN = "UNKNOWN"

    class Representation(models.TextChoices):
        VECTOR = "VECTOR"
        RASTER = "RASTER"
        MIXED = "MIXED"
        UNKNOWN = "UNKNOWN"

    class Readiness(models.TextChoices):
        TECHNICALLY_READY = "TECHNICALLY_READY"
        TECHNICALLY_USABLE_WITH_CAVEATS = "TECHNICALLY_USABLE_WITH_CAVEATS"
        NEEDS_VECTOR_RECONSTRUCTION = "NEEDS_VECTOR_RECONSTRUCTION"
        REFERENCE_ONLY = "REFERENCE_ONLY"
        NEEDS_CLEANUP = "NEEDS_CLEANUP"
        HEADER_ONLY_PARTIAL = "HEADER_ONLY_PARTIAL"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"

    corpus_item = models.OneToOneField(
        CorpusItem, primary_key=True, on_delete=models.PROTECT,
        related_name="design_asset_profile")
    primary_source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="design_asset_profiles")
    candidate_source_key = models.CharField(max_length=64)
    source_manifest_entry_key = models.CharField(max_length=255)
    dataset_identifier = models.CharField(max_length=127)
    candidate_asset_kind = models.CharField(max_length=24, choices=CandidateKind.choices)
    representation_state = models.CharField(max_length=16, choices=Representation.choices)
    technical_readiness = models.CharField(max_length=40, choices=Readiness.choices)
    extraction_state = models.CharField(max_length=32)
    collection_family_label = models.CharField(max_length=255, blank=True)
    dimensions_media = models.JSONField(default=dict, blank=True,
                                        validators=[_validate_locator])
    is_test_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(
                    dataset_identifier__in=SUPPORTED_DESIGN_ASSET_DATASET_IDENTIFIERS),
                name="intel_asset_dataset_supported"),
            models.CheckConstraint(check=Q(candidate_asset_kind__in=(
                "MOTIF", "BACKGROUND", "ILLUSTRATION", "LOGO_CANDIDATE", "PATTERN",
                "PHOTO", "UNKNOWN")), name="intel_asset_kind_valid"),
            models.CheckConstraint(check=Q(representation_state__in=(
                "VECTOR", "RASTER", "MIXED", "UNKNOWN")),
                                   name="intel_asset_repr_valid"),
            models.CheckConstraint(check=Q(technical_readiness__in=(
                "TECHNICALLY_READY", "TECHNICALLY_USABLE_WITH_CAVEATS",
                "NEEDS_VECTOR_RECONSTRUCTION", "REFERENCE_ONLY", "NEEDS_CLEANUP",
                "HEADER_ONLY_PARTIAL", "REVIEW_REQUIRED")),
                                   name="intel_asset_readiness_valid"),
        ]


class FontFaceProfile(models.Model):
    class EvidenceState(models.TextChoices):
        UNREVIEWED = "UNREVIEWED"
        PRESENT_UNREVIEWED = "PRESENT_UNREVIEWED"
        ABSENT = "ABSENT"
        CONFLICT = "CONFLICT"

    class Suitability(models.TextChoices):
        HEALTHY = "HEALTHY"
        TECHNICAL_CAVEAT = "TECHNICAL_CAVEAT"
        UNSUPPORTED = "UNSUPPORTED"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"

    corpus_item = models.OneToOneField(
        CorpusItem, primary_key=True, on_delete=models.PROTECT,
        related_name="font_face_profile")
    primary_source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="font_face_profiles")
    face_index = models.PositiveIntegerField(default=0)
    family_name = models.CharField(max_length=255)
    subfamily = models.CharField(max_length=255, blank=True)
    postscript_name = models.CharField(max_length=255, blank=True)
    weight = models.PositiveIntegerField(null=True, blank=True)
    width = models.CharField(max_length=32, blank=True)
    italic = models.BooleanField(default=False)
    variable_axes = models.JSONField(
        default=list, blank=True, validators=[_validate_bounded_json])
    script_coverage = models.JSONField(default=dict, blank=True,
                                       validators=[_validate_locator])
    suspected_system_copy = models.BooleanField(default=False)
    evidence_state = models.CharField(max_length=24, choices=EvidenceState.choices)
    technical_suitability_state = models.CharField(
        max_length=24, choices=Suitability.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(face_index__lte=65535),
                                   name="intel_font_face_index_bounded"),
            models.CheckConstraint(
                check=Q(weight__isnull=True) | (Q(weight__gte=1) & Q(weight__lte=1000)),
                name="intel_font_weight_bounded"),
            models.CheckConstraint(check=Q(evidence_state__in=(
                "UNREVIEWED", "PRESENT_UNREVIEWED", "ABSENT", "CONFLICT")),
                                   name="intel_font_evidence_valid"),
            models.CheckConstraint(check=Q(technical_suitability_state__in=(
                "HEALTHY", "TECHNICAL_CAVEAT", "UNSUPPORTED", "REVIEW_REQUIRED")),
                                   name="intel_font_suitability_valid"),
            models.UniqueConstraint(
                fields=("primary_source_artifact", "face_index"),
                name="intel_font_source_face_uniq"),
        ]


class BrandCandidateProfile(models.Model):
    class CandidateKind(models.TextChoices):
        LOGO = "LOGO"
        WORDMARK = "WORDMARK"
        BRAND_GRAPHIC = "BRAND_GRAPHIC"
        PALETTE = "PALETTE"
        LOCKUP = "LOCKUP"
        UNKNOWN_BRAND_ASSET = "UNKNOWN_BRAND_ASSET"

    class Representation(models.TextChoices):
        VECTOR = "VECTOR"
        RASTER = "RASTER"
        MIXED = "MIXED"
        UNKNOWN = "UNKNOWN"

    class Warning(models.TextChoices):
        NONE_OBSERVED = "NONE_OBSERVED"
        REQUIRES_REVIEW = "REQUIRES_REVIEW"
        THIRD_PARTY_OR_UNCONFIRMED = "THIRD_PARTY_OR_UNCONFIRMED"
        PARTIAL_PARSE = "PARTIAL_PARSE"

    class Status(models.TextChoices):
        CANDIDATE = "CANDIDATE"
        UNCONFIRMED = "UNCONFIRMED"
        REVIEW_REQUIRED = "REVIEW_REQUIRED"

    corpus_item = models.OneToOneField(
        CorpusItem, primary_key=True, on_delete=models.PROTECT,
        related_name="brand_candidate_profile")
    primary_source_artifact = models.ForeignKey(
        SourceArtifact, on_delete=models.PROTECT, related_name="brand_candidate_profiles")
    candidate_kind = models.CharField(max_length=24, choices=CandidateKind.choices)
    observed_brand_label = models.CharField(max_length=255, blank=True)
    technical_format = models.CharField(max_length=32)
    representation_state = models.CharField(max_length=16, choices=Representation.choices)
    observed_candidate_data = models.JSONField(default=dict, blank=True,
                                               validators=[_validate_locator])
    warning_state = models.CharField(max_length=32, choices=Warning.choices)
    candidate_status = models.CharField(max_length=24, choices=Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(candidate_kind__in=(
                "LOGO", "WORDMARK", "BRAND_GRAPHIC", "PALETTE", "LOCKUP",
                "UNKNOWN_BRAND_ASSET")), name="intel_brand_kind_valid"),
            models.CheckConstraint(check=Q(representation_state__in=(
                "VECTOR", "RASTER", "MIXED", "UNKNOWN")),
                                   name="intel_brand_repr_valid"),
            models.CheckConstraint(check=Q(warning_state__in=(
                "NONE_OBSERVED", "REQUIRES_REVIEW", "THIRD_PARTY_OR_UNCONFIRMED",
                "PARTIAL_PARSE")), name="intel_brand_warning_valid"),
            models.CheckConstraint(check=Q(candidate_status__in=(
                "CANDIDATE", "UNCONFIRMED", "REVIEW_REQUIRED")),
                                   name="intel_brand_status_valid"),
        ]


# === DIP-1C-1 semantic index (derived, rebuildable search data — grants no authority) ===
# These three tables are the ONLY new schema in DIP-1C-1. They hold embedding vectors and
# index-build metadata. An embedding is derived search data: it is never authority, never a
# permission, and is deliberately kept out of OperationalPermissionProjection and CorpusItem.
# Storage is a bounded Phase-1 MVP — a numeric JSON array, cosine similarity computed in
# numpy at read time. It is NOT the final large-scale vector architecture; a later slice may
# migrate to pgvector without changing the semantic-document, generation-identity,
# document-hash, provider/model, or hybrid-search contracts.
class SemanticIndexGeneration(models.Model):
    class Status(models.TextChoices):
        BUILDING = "BUILDING"
        BUILT = "BUILT"
        PUBLISHED = "PUBLISHED"
        FAILED = "FAILED"
        SUPERSEDED = "SUPERSEDED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # provider/model/encoder identity is pinned per generation: vectors from different
    # providers, models, dimensions, document schemas, or encoder versions never mix
    encoder_identifier = models.CharField(max_length=64)
    encoder_version = models.CharField(max_length=64)
    provider = models.CharField(max_length=32)
    model_identifier = models.CharField(max_length=128)
    document_schema_version = models.CharField(max_length=64)
    index_schema_version = models.CharField(max_length=64)
    vector_dimension = models.PositiveIntegerField()
    corpus_manifest_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=Status.choices,
                              default=Status.BUILDING)
    # a test-encoder generation is visibly marked and can never become the production
    # publication (enforced in the publish path, not merely by convention)
    is_test_encoder = models.BooleanField(default=False)
    document_count = models.PositiveIntegerField(default=0)
    embedded_count = models.PositiveIntegerField(default=0)
    request_count = models.PositiveIntegerField(default=0)
    invoked_by = models.CharField(max_length=150, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    # never contains a key or a transmitted document — validated on save
    failure_summary = models.TextField(blank=True, default="")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(corpus_manifest_hash__regex=SHA256_RE),
                name="intel_semindex_corpus_hash_valid"),
            models.CheckConstraint(
                check=Q(vector_dimension__gt=0),
                name="intel_semindex_dim_positive"),
        ]
        indexes = [models.Index(fields=("status", "provider", "model_identifier"),
                                name="intel_semindex_status_idx")]


class SemanticDocumentEmbedding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    generation = models.ForeignKey(
        SemanticIndexGeneration, on_delete=models.CASCADE, related_name="embeddings")
    corpus_item = models.ForeignKey(
        CorpusItem, on_delete=models.CASCADE, related_name="semantic_embeddings")
    document_hash = models.CharField(max_length=64)
    vector_hash = models.CharField(max_length=64)
    vector_dimension = models.PositiveIntegerField()
    # a numeric array only: finite floats, exact dimension, validated before persistence
    vector = models.JSONField()
    provider = models.CharField(max_length=32)
    model_identifier = models.CharField(max_length=128)
    encoder_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        _validate_embedding_vector(self.vector, self.vector_dimension)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(check=Q(document_hash__regex=SHA256_RE),
                                   name="intel_semdoc_dochash_valid"),
            models.CheckConstraint(check=Q(vector_hash__regex=SHA256_RE),
                                   name="intel_semdoc_vechash_valid"),
            models.UniqueConstraint(fields=("generation", "corpus_item"),
                                    name="intel_semdoc_generation_item_uniq"),
        ]
        indexes = [models.Index(fields=("generation", "corpus_item"),
                                name="intel_semdoc_lookup_idx")]


class SemanticIndexPublicationState(models.Model):
    """Singleton (pk=1): the one currently published production generation, if any."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    current_generation = models.ForeignKey(
        SemanticIndexGeneration, on_delete=models.PROTECT, null=True, blank=True,
        related_name="+")
    corpus_manifest_hash = models.CharField(max_length=64, blank=True, default="")
    provider = models.CharField(max_length=32, blank=True, default="")
    model_identifier = models.CharField(max_length=128, blank=True, default="")
    encoder_version = models.CharField(max_length=64, blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            # `id`, not `pk`: a Q(pk=...) check constraint does not resolve during
            # Django's full_clean() constraint validation
            models.CheckConstraint(check=Q(id=1),
                                   name="intel_sempub_singleton"),
        ]
