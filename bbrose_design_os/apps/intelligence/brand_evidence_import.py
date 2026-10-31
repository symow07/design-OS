"""Append-only reconciliation of the deterministic DIP-1B brand evidence."""
from __future__ import annotations

import collections
from datetime import datetime
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import DecisionEvent

from .brand_evidence import (
    DATASET_ID, DATASET_SCHEMA, DEFAULT_DATASET_PATH,
    GENERATOR_IDENTIFIER, GENERATOR_VERSION, canonical_hash, sha256_file,
    validate_committed_brand_evidence_bundle,
)
from .identity import evidence_identity_hash
from .import_services import finalize_import_batch, record_import_attempt
from .models import (
    CorpusItem, EvidenceReference, ImportBatch, ImportRecord, ObservedFact,
    OperationalPermissionProjection, ProvenanceRecord, SourceArtifact,
    SourceLocationObservation,
)

IMPORTER_IDENTIFIER = "bbrose.intelligence.import_brand_evidence"
IMPORTER_VERSION = "2.0"
CONFIGURATION_HASH = canonical_hash({
    "dataset_id": DATASET_ID,
    "mode": "append_only_candidate_evidence_reconciliation",
    "authority_effect": "NONE",
})
DATASET_RELATIVE_PATH = "docs/design_intelligence/dip1/dip1b_brand_evidence_2_0.json"


class BrandEvidenceImportError(RuntimeError):
    pass


def _authority_counts():
    return {
        "decision_events": DecisionEvent.objects.count(),
        "allowed_permissions": OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
    }


def _completed_batch(manifest_hash):
    return ImportBatch.objects.filter(
        importer_identifier=IMPORTER_IDENTIFIER,
        importer_version=IMPORTER_VERSION,
        source_manifest_hash=manifest_hash,
        configuration_hash=CONFIGURATION_HASH,
        status=ImportBatch.Status.COMPLETED,
    ).order_by("started_at", "id").first()


def _preflight_candidate_bindings(records):
    for record in records:
        stable_key = record["stable_candidate_key"]
        items = list(CorpusItem.objects.filter(
            external_key=f"brand:{stable_key}").values_list("pk", flat=True)[:2])
        if len(items) != 1:
            raise BrandEvidenceImportError(
                f"expected one preserved candidate identity for {stable_key}")
        if not ImportRecord.objects.filter(
                corpus_item_id=items[0],
                source_record_hash=record["preserved_import_record_hash"]).exists():
            raise BrandEvidenceImportError(
                f"preserved ImportRecord binding is absent for {stable_key}")


def _artifact(bundle):
    dataset_hash = bundle["dataset_sha256"]
    artifact = SourceArtifact.objects.filter(sha256=dataset_hash).order_by(
        "first_observed_at", "id").first()
    if artifact:
        return artifact, False
    dataset_path = Path(DEFAULT_DATASET_PATH)
    return SourceArtifact.objects.create(
        source_identifier=f"repository:{DATASET_RELATIVE_PATH}",
        source_location=f"repository:{DATASET_RELATIVE_PATH}",
        source_type=SourceArtifact.SourceType.JSON,
        media_type="application/json",
        sha256=dataset_hash,
        byte_size=len(bundle["dataset_bytes"]),
        source_modified_at=datetime.fromtimestamp(
            dataset_path.stat().st_mtime, tz=timezone.get_current_timezone()),
        parser_identifier=GENERATOR_IDENTIFIER,
        parser_version=GENERATOR_VERSION,
        source_schema_version=DATASET_SCHEMA,
        availability_state=SourceArtifact.Availability.AVAILABLE,
    ), True


def _record(batch, *, key, record_hash, artifact, item=None, details=None):
    row, _ = record_import_attempt(
        import_batch=batch, stable_source_record_key=key,
        source_record_hash=record_hash, parser_version=IMPORTER_VERSION,
        source_schema_version=DATASET_SCHEMA, source_artifact=artifact,
        corpus_item=item, reconciliation_details={
            "dataset_id": DATASET_ID,
            "manifest_id": "dip1b_brand_evidence_manifest/2.0",
            "authority_effect": "NONE",
            **(details or {}),
        },
    )
    return row


def _evidence(item, artifact, record, index):
    locator = {"path": DATASET_RELATIVE_PATH, "segments": ["records", index]}
    evidence_hash = evidence_identity_hash(
        item_id=item.pk, source_hash=artifact.sha256,
        kind="DETERMINISTIC_BRAND_EVIDENCE_RECORD", schema="json_path/1.0",
        locator=locator, observed=record["canonical_record_hash"],
    )
    return EvidenceReference.objects.get_or_create(
        corpus_item=item, source_artifact=artifact, evidence_hash=evidence_hash,
        defaults={
            "evidence_kind": "DETERMINISTIC_BRAND_EVIDENCE_RECORD",
            "locator_schema_version": "json_path/1.0", "locator": locator,
            "observed_value": record["canonical_record_hash"], "is_test_only": False,
        },
    )[0]


def _reconcile_record(batch, artifact, record, index):
    stable_key = record["stable_candidate_key"]
    items = list(CorpusItem.objects.filter(
        external_key=f"brand:{stable_key}").order_by("id")[:2])
    if len(items) != 1:
        raise BrandEvidenceImportError(
            f"expected one preserved candidate identity for {stable_key}")
    item = items[0]
    if not ImportRecord.objects.filter(
            corpus_item=item,
            source_record_hash=record["preserved_import_record_hash"]).exists():
        raise BrandEvidenceImportError(
            f"preserved ImportRecord binding is absent for {stable_key}")
    evidence = _evidence(item, artifact, record, index)
    ProvenanceRecord.objects.get_or_create(
        corpus_item=item, source_artifact=artifact,
        provenance_type="DIP1B5A_DETERMINISTIC_BRAND_EVIDENCE",
        acquisition_reference=f"{DATASET_ID}:{stable_key}",
        defaults={
            "source_package": DATASET_ID,
            "normalized_machine_interpretation": {
                "technical_evidence_only": True,
                "preserves_prior_evidence": True,
                "ownership_or_rights_inferred": False,
                "canonical_or_palette_status_inferred": False,
                "operational_permission_inferred": False,
            },
        },
    )
    fact_value = {
        "dataset_id": DATASET_ID,
        "canonical_record_hash": record["canonical_record_hash"],
        "technical_evidence_ready": True,
        "brand_identity_evidence_ready": False,
        "rights_evidence_ready": False,
        "palette_authority_evidence_ready": False,
        "governance_ready": False,
        "authority_effect": "NONE",
    }
    fact_hash = canonical_hash({"type": "EVIDENCE_READINESS_DIMENSIONS",
                                "value": fact_value})
    ObservedFact.objects.get_or_create(
        corpus_item=item, fact_type="EVIDENCE_READINESS_DIMENSIONS",
        source_artifact=artifact, fact_hash=fact_hash,
        defaults={
            "normalized_value": fact_value, "raw_value": "",
            "value_schema_version": "evidence_readiness/1.0",
            "evidence_reference": evidence,
            "importer_identifier": IMPORTER_IDENTIFIER,
            "importer_version": IMPORTER_VERSION,
        },
    )
    return _record(
        batch, key=f"brand-evidence:{stable_key}",
        record_hash=record["canonical_record_hash"], artifact=artifact, item=item,
        details={
            "stable_candidate_key": stable_key,
            "preserved_import_record_hash": record["preserved_import_record_hash"],
            "evidence_reference_id": str(evidence.pk),
        },
    )


def _counts(records, failures):
    dispositions = collections.Counter(row.disposition for row in records)
    return {
        "total_records": len(records) + len(failures),
        "imported_records": dispositions[ImportRecord.Disposition.CREATED],
        "unchanged_records": dispositions[ImportRecord.Disposition.UNCHANGED],
        "changed_records": dispositions[ImportRecord.Disposition.NEW_VERSION],
        "skipped_records": dispositions[ImportRecord.Disposition.SKIPPED],
        "quarantined_records": dispositions[ImportRecord.Disposition.QUARANTINED],
        "failed_records": dispositions[ImportRecord.Disposition.FAILED] + len(failures),
    }


def run_brand_evidence_import(*, apply=False, fail_record_key=None):
    bundle = validate_committed_brand_evidence_bundle()
    if sha256_file(Path(DEFAULT_DATASET_PATH)) != bundle["dataset_sha256"]:
        raise BrandEvidenceImportError("dataset changed during validation")
    manifest_hash = bundle["manifest_sha256"]
    _preflight_candidate_bindings(bundle["dataset"]["records"])
    existing = _completed_batch(manifest_hash)
    before = _authority_counts()
    report = {
        "mode": "apply" if apply else "dry-run", "dataset_id": DATASET_ID,
        "manifest_entries": 1, "logical_sources": 21,
        "physical_source_artifacts": 1, "frozen_input_records": 21,
        "semantic_corpus_items": 21, "manifest_hash": manifest_hash,
        "dataset_hash": bundle["dataset_sha256"],
        "existing_completed_batch": str(existing.pk) if existing else None,
        "created_records": 0, "unchanged_records": 21 if existing else 0,
        "would_create_records": 0 if existing else 22,
        "new_source_versions": 0, "quarantined_records": 0,
        "failed_records": 0, "excluded_records": 0,
        "decision_events_created": 0, "allowed_permissions_created": 0,
    }
    if not apply or existing:
        return report
    batch = ImportBatch.objects.create(
        importer_identifier=IMPORTER_IDENTIFIER, importer_version=IMPORTER_VERSION,
        configuration_hash=CONFIGURATION_HASH, source_manifest_hash=manifest_hash,
        scope={"dataset_id": DATASET_ID, "record_count": 21,
               "authority_effect": "NONE"},
    )
    artifact, artifact_created = _artifact(bundle)
    source_record = _record(
        batch, key="source:dip1b-brand-evidence-v2",
        record_hash=canonical_hash(bundle["manifest"]["dataset"]), artifact=artifact,
        details={"source_declaration": True},
    )
    SourceLocationObservation.objects.get_or_create(
        source_artifact=artifact,
        location_kind=SourceLocationObservation.Kind.REPOSITORY_RELATIVE,
        observed_location=f"repository:{DATASET_RELATIVE_PATH}",
        defaults={
            "observed_by_import_record": source_record,
            "availability_state": SourceLocationObservation.Availability.AVAILABLE,
            "location_metadata": {"root": "repository", "dataset_id": DATASET_ID},
        },
    )
    records = [source_record]
    failures = []
    for index, record in enumerate(bundle["dataset"]["records"]):
        key = f"brand-evidence:{record['stable_candidate_key']}"
        try:
            with transaction.atomic():
                if fail_record_key == key:
                    raise RuntimeError("injected bounded test failure")
                records.append(_reconcile_record(batch, artifact, record, index))
        except Exception as exc:  # noqa: BLE001 - bounded per-record isolation
            failures.append(f"{key}:{type(exc).__name__}"[:200])
    after = _authority_counts()
    if after != before:
        failures.append("AUTHORITY_INVARIANT_CHANGED")
    counts = _counts(records, failures)
    batch = finalize_import_batch(
        batch,
        status=(ImportBatch.Status.COMPLETED_WITH_ERRORS if failures
                else ImportBatch.Status.COMPLETED),
        counts=counts, failure_summary=";".join(failures)[:4000],
    )
    report.update({
        "batch_id": str(batch.pk),
        "created_records": counts["imported_records"],
        "unchanged_records": counts["unchanged_records"],
        "new_source_versions": int(artifact_created),
        "failed_records": counts["failed_records"],
        "failures": failures,
        "decision_events_created": after["decision_events"] - before["decision_events"],
        "allowed_permissions_created": (
            after["allowed_permissions"] - before["allowed_permissions"]),
    })
    return report
