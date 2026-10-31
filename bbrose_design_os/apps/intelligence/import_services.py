from django.db import transaction
from django.utils import timezone

from .models import ImportBatch, ImportRecord, SourceArtifact


@transaction.atomic
def finalize_import_batch(batch, *, status, counts, failure_summary=""):
    """Close a RUNNING batch exactly once; callers cannot reopen terminal history."""
    if status not in (
            ImportBatch.Status.COMPLETED,
            ImportBatch.Status.COMPLETED_WITH_ERRORS,
            ImportBatch.Status.FAILED):
        raise ValueError("invalid terminal import status")
    locked = ImportBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status != ImportBatch.Status.RUNNING:
        raise ValueError("only a RUNNING import batch may be finalized")
    count_fields = (
        "total_records", "imported_records", "unchanged_records", "changed_records",
        "skipped_records", "quarantined_records", "failed_records")
    if set(counts) != set(count_fields) or any(
            type(counts[name]) is not int or counts[name] < 0 for name in count_fields):
        raise ValueError("all non-negative import counts are required")
    for name in count_fields:
        setattr(locked, name, counts[name])
    locked.status = status
    locked.completed_at = timezone.now()
    locked.failure_summary = failure_summary
    locked.save()
    return locked


@transaction.atomic
def record_source_version(**values):
    """Return the identical logical/content version or append a changed-hash version."""
    source_identifier = values["source_identifier"]
    sha256 = values["sha256"]
    existing = SourceArtifact.objects.filter(
        source_identifier=source_identifier, sha256=sha256).first()
    if existing:
        return existing, False
    prior = SourceArtifact.objects.filter(
        source_identifier=source_identifier).order_by("-imported_at", "-id").first()
    return SourceArtifact.objects.create(
        supersedes_source_artifact=prior, **values), True


@transaction.atomic
def record_import_attempt(*, import_batch, stable_source_record_key, source_record_hash,
                          parser_version, source_schema_version, disposition=None,
                          source_artifact=None, corpus_item=None, reconciliation_details=None):
    existing = ImportRecord.objects.filter(
        import_batch=import_batch,
        stable_source_record_key=stable_source_record_key).first()
    if existing:
        if existing.source_record_hash != source_record_hash:
            raise ValueError("stable key already recorded with different content in this batch")
        return existing, False

    prior = (ImportRecord.objects.filter(
        import_batch__importer_identifier=import_batch.importer_identifier,
        stable_source_record_key=stable_source_record_key)
        .exclude(disposition=ImportRecord.Disposition.FAILED)
        .order_by("-created_at").first())
    if disposition is None:
        if prior is None:
            disposition = ImportRecord.Disposition.CREATED
        elif prior.source_record_hash == source_record_hash:
            disposition = ImportRecord.Disposition.UNCHANGED
        else:
            disposition = ImportRecord.Disposition.NEW_VERSION
    if prior and prior.source_record_hash == source_record_hash:
        source_artifact = source_artifact or prior.source_artifact
        corpus_item = corpus_item or prior.corpus_item
    row = ImportRecord.objects.create(
        import_batch=import_batch, stable_source_record_key=stable_source_record_key,
        source_record_hash=source_record_hash, source_artifact=source_artifact,
        corpus_item=corpus_item, disposition=disposition, prior_import_record=prior,
        parser_version=parser_version, source_schema_version=source_schema_version,
        reconciliation_details=reconciliation_details or {})
    return row, True
