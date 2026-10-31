"""Bounded, append-only importer for the DIP-1B-5A curated expansion."""
from __future__ import annotations

import collections
import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import DecisionEvent

from .curated_expansion import (
    GENERATOR_IDENTIFIER, GENERATOR_VERSION, MANIFEST_ID,
    canonical_bytes, validate_curated_expansion_manifest,
)
from .dataset_identifiers import DIP1B_CURATED_ASSET_EXPANSION_DATASET
from .identity import evidence_identity_hash, semantic_asset_external_key
from .import_services import finalize_import_batch, record_import_attempt
from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, HistoricalDesignProfile,
    ImportBatch, ImportRecord, MachineClassification, ObservedFact,
    OperationalPermissionProjection, ProvenanceRecord, SourceArtifact,
    SourceLocationObservation,
)

IMPORTER_IDENTIFIER = "bbrose.intelligence.import_curated_expansion"
IMPORTER_VERSION = "1.0"
CONFIGURATION_HASH = hashlib.sha256(canonical_bytes({
    "manifest_id": MANIFEST_ID, "mode": "bounded_curated_expansion",
    "reference_policy": "REFERENCE_MEMORY_ONLY", "authority_effect": "NONE",
})).hexdigest()


class CuratedExpansionImportError(RuntimeError):
    pass


def _authority_counts():
    return {
        "decision_events": DecisionEvent.objects.count(),
        "allowed_permissions": OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
    }


def _completed_batch(manifest_hash):
    return ImportBatch.objects.filter(
        importer_identifier=IMPORTER_IDENTIFIER, importer_version=IMPORTER_VERSION,
        configuration_hash=CONFIGURATION_HASH, source_manifest_hash=manifest_hash,
        status=ImportBatch.Status.COMPLETED,
    ).order_by("started_at", "id").first()


def _artifact(entry):
    source = entry["source"]
    artifact = SourceArtifact.objects.filter(sha256=source["sha256"]).order_by(
        "first_observed_at", "id").first()
    if artifact:
        return artifact, False
    from apps.ire.materials_paths import resolve_material_file
    # The committed path stays the artifact's identity; the Day 6 migration manifest says where the bytes live now.
    path = resolve_material_file(Path(settings.BASE_DIR).parent / source["path"], repo_root=Path(settings.BASE_DIR).parent)
    parser = entry.get("technical", {}).get("parser_identifier") or GENERATOR_IDENTIFIER
    parser_version = entry.get("technical", {}).get("parser_version") or GENERATOR_VERSION
    return SourceArtifact.objects.create(
        source_identifier=f"repository:{source['path']}",
        source_location=f"repository:{source['path']}",
        source_type=source["source_type"], media_type=source["media_type"],
        sha256=source["sha256"], byte_size=path.stat().st_size,
        source_modified_at=datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.get_current_timezone()),
        parser_identifier=parser, parser_version=parser_version,
        source_schema_version=entry["dataset_id"],
        availability_state=SourceArtifact.Availability.AVAILABLE,
    ), True


def _attempt(batch, entry, key, record_hash, artifact, item=None, details=None):
    row, _ = record_import_attempt(
        import_batch=batch, stable_source_record_key=key,
        source_record_hash=record_hash, source_artifact=artifact, corpus_item=item,
        parser_version=IMPORTER_VERSION, source_schema_version=entry["dataset_id"],
        reconciliation_details={
            "dataset_id": entry["dataset_id"], "manifest_id": MANIFEST_ID,
            "manifest_entry_key": entry["stable_source_key"],
            "authority_effect": "NONE", **(details or {}),
        },
    )
    return row


def _evidence(item, artifact, entry):
    locator = entry["evidence_locator"]["value"]
    kind = ("CURATED_HISTORICAL_SOURCE" if entry["record_type"]
            == "HISTORICAL_DESIGN" else "CURATED_DESIGN_ASSET_SOURCE")
    evidence_hash = evidence_identity_hash(
        item_id=item.pk, source_hash=artifact.sha256, kind=kind,
        schema="source_file/1.0", locator=locator, observed=artifact.sha256)
    return EvidenceReference.objects.get_or_create(
        corpus_item=item, source_artifact=artifact, evidence_hash=evidence_hash,
        defaults={
            "evidence_kind": kind, "locator_schema_version": "source_file/1.0",
            "locator": locator, "observed_value": artifact.sha256,
            "is_test_only": False,
        },
    )[0]


def _provenance(item, artifact, entry):
    return ProvenanceRecord.objects.get_or_create(
        corpus_item=item, source_artifact=artifact,
        provenance_type="DIP1B5A_CURATED_EXPANSION",
        acquisition_reference=f"{MANIFEST_ID}:{entry['stable_source_key']}",
        defaults={
            "source_package": entry["dataset_id"],
            "normalized_machine_interpretation": {
                "curated_manifest_membership": True,
                "reference_memory_only": entry["record_type"] == "HISTORICAL_DESIGN",
                "third_party_rights_unreviewed": entry["record_type"]
                == "DESIGN_ASSET_CANDIDATE",
                "operational_permission_inferred": False,
            },
        },
    )[0]


def _fact(item, artifact, evidence, entry, fact_type, value):
    fact_hash = hashlib.sha256(canonical_bytes({
        "type": fact_type, "value": value, "evidence": evidence.evidence_hash,
    })).hexdigest()
    return ObservedFact.objects.get_or_create(
        corpus_item=item, fact_type=fact_type, source_artifact=artifact,
        fact_hash=fact_hash,
        defaults={
            "normalized_value": value, "value_schema_version": "observed_fact/1.0",
            "evidence_reference": evidence, "importer_identifier": IMPORTER_IDENTIFIER,
            "importer_version": IMPORTER_VERSION,
        },
    )[0]


def _classification(item, artifact, evidence, entry, type_, label, confidence):
    explanation = {
        "manifest_id": MANIFEST_ID, "selection": entry["selection"],
        "machine_generated": True, "authority_effect": "NONE",
    }
    classification_hash = hashlib.sha256(canonical_bytes({
        "type": type_, "label": label, "confidence": confidence,
        "explanation": explanation, "evidence": evidence.evidence_hash,
    })).hexdigest()
    return MachineClassification.objects.get_or_create(
        corpus_item=item, classification_type=type_, source_artifact=artifact,
        classification_hash=classification_hash,
        defaults={
            "label": label, "confidence": Decimal(str(confidence)),
            "classifier_identifier": GENERATOR_IDENTIFIER,
            "classifier_version": GENERATOR_VERSION,
            "classification_schema_version": "machine_classification/1.0",
            "evidence_reference": evidence, "structured_explanation": explanation,
        },
    )[0]


def _historical(batch, artifact, entry):
    external_key = f"historical:{entry['stable_source_key']}"
    item, created = CorpusItem.objects.get_or_create(
        item_kind=CorpusItem.Kind.HISTORICAL_DESIGN, external_key=external_key)
    if not created and item.item_kind != CorpusItem.Kind.HISTORICAL_DESIGN:
        raise CuratedExpansionImportError("historical semantic identity collision")
    evidence = _evidence(item, artifact, entry)
    _provenance(item, artifact, entry)
    profile, profile_created = HistoricalDesignProfile.objects.get_or_create(
        corpus_item=item,
        defaults={
            "primary_source_artifact": artifact,
            "display_title": Path(entry["source"]["path"]).name,
            "page_artboard_count": entry["technical"]["page_count"],
            "extracted_design_unit_count": 0,
            "audit_status": HistoricalDesignProfile.AuditStatus.REVIEW_REQUIRED,
            "historical_period_observed": entry["selection"]["era"],
            "product_family_machine_label": entry["selection"]["product_family"],
            "reference_memory_policy": HistoricalDesignProfile.REFERENCE_MEMORY_ONLY,
        },
    )
    if not profile_created and profile.primary_source_artifact_id != artifact.pk:
        raise CuratedExpansionImportError("historical profile source identity changed")
    _fact(item, artifact, evidence, entry, "CURATED_HISTORICAL_REFERENCE", {
        "manifest_id": MANIFEST_ID, "reference_memory_only": True,
        "audit_status": "REVIEW_REQUIRED", "page_count": 1,
        "selection": entry["selection"],
    })
    _classification(
        item, artifact, evidence, entry, "HISTORICAL_PRODUCT_FAMILY",
        entry["selection"]["product_family"],
        entry["technical"]["machine_classification_confidence"])
    return _attempt(
        batch, entry, f"historical:{entry['stable_source_key']}",
        hashlib.sha256(canonical_bytes(entry)).hexdigest(),
        artifact, item, {"reference_memory_only": True})


def _asset(batch, artifact, entry):
    dataset = entry["dataset_id"]
    candidate_key = entry["candidate_key"]
    external_key = semantic_asset_external_key(dataset, candidate_key)
    item, _ = CorpusItem.objects.get_or_create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key=external_key)
    evidence = _evidence(item, artifact, entry)
    _provenance(item, artifact, entry)
    profile, profile_created = DesignAssetProfile.objects.get_or_create(
        corpus_item=item,
        defaults={
            "primary_source_artifact": artifact, "candidate_source_key": candidate_key,
            "source_manifest_entry_key": entry["stable_source_key"],
            "dataset_identifier": DIP1B_CURATED_ASSET_EXPANSION_DATASET,
            "candidate_asset_kind": entry["selection"]["asset_kind"],
            "representation_state": DesignAssetProfile.Representation.VECTOR,
            "technical_readiness": (
                DesignAssetProfile.Readiness.TECHNICALLY_USABLE_WITH_CAVEATS),
            "extraction_state": "WHOLE_SOURCE_ISOLATED",
            "collection_family_label": Path(entry["source"]["path"]).parent.name[:255],
            "dimensions_media": {"whole_source": True, "bounds": []},
            "is_test_only": False,
        },
    )
    if (not profile_created
            and (profile.dataset_identifier != dataset
                 or profile.candidate_source_key != candidate_key
                 or profile.primary_source_artifact_id != artifact.pk)):
        raise CuratedExpansionImportError("design-asset profile identity changed")
    _fact(item, artifact, evidence, entry, "CURATED_ASSET_TECHNICAL_OBSERVATION", {
        "manifest_id": MANIFEST_ID, "dataset_id": dataset,
        "candidate_key": candidate_key, "representation": "VECTOR",
        "technical_readiness": "TECHNICALLY_USABLE_WITH_CAVEATS",
        "extraction_state": "WHOLE_SOURCE_ISOLATED",
        "rights_warning": "THIRD_PARTY_RIGHTS_UNREVIEWED",
    })
    _classification(
        item, artifact, evidence, entry, "CURATED_ASSET_KIND",
        entry["selection"]["asset_kind"], 0.7)
    return _attempt(
        batch, entry, f"asset-candidate:{candidate_key}",
        hashlib.sha256(canonical_bytes(entry)).hexdigest(),
        artifact, item, {"candidate_key": candidate_key,
                         "rights_warning": "THIRD_PARTY_RIGHTS_UNREVIEWED"})


def _count_records(records, failures):
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


def run_curated_expansion_import(*, apply=False, fail_record_key=None):
    prepared = validate_curated_expansion_manifest()
    entries = prepared["document"]["entries"]
    manifest_hash = prepared["sha256"]
    hashes = {row["source"]["sha256"] for row in entries}
    existing_artifacts = SourceArtifact.objects.filter(sha256__in=hashes).count()
    existing = _completed_batch(manifest_hash)
    before = _authority_counts()
    report = {
        "mode": "apply" if apply else "dry-run", "manifest_id": MANIFEST_ID,
        "manifest_hash": manifest_hash, "manifest_entries": 59,
        "logical_sources": 59, "physical_source_artifacts": len(hashes),
        "frozen_input_records": 59, "semantic_corpus_items": 59,
        "historical_designs": 6, "design_assets": 53, "fonts": 0,
        "created_records": 0, "unchanged_records": 59 if existing else 0,
        "would_create_records": 0 if existing else 118,
        "new_source_versions": 0 if existing else len(hashes) - existing_artifacts,
        "quarantined_records": 0, "failed_records": 0, "excluded_records": 0,
        "existing_completed_batch": str(existing.pk) if existing else None,
        "decision_events_created": 0, "allowed_permissions_created": 0,
    }
    if not apply or existing:
        return report
    batch = ImportBatch.objects.create(
        importer_identifier=IMPORTER_IDENTIFIER, importer_version=IMPORTER_VERSION,
        configuration_hash=CONFIGURATION_HASH, source_manifest_hash=manifest_hash,
        scope={"manifest_id": MANIFEST_ID, "historical": 6, "assets": 53,
               "authority_effect": "NONE"},
    )
    records = []
    failures = []
    created_artifacts = 0
    for entry in entries:
        key = entry["stable_source_key"]
        try:
            with transaction.atomic():
                if fail_record_key == key:
                    raise RuntimeError("injected bounded test failure")
                artifact, artifact_created = _artifact(entry)
                source_record = _attempt(
                    batch, entry, f"source:{key}",
                    hashlib.sha256(canonical_bytes(entry["source"])).hexdigest(),
                    artifact, details={"source_declaration": True})
                SourceLocationObservation.objects.get_or_create(
                    source_artifact=artifact,
                    location_kind=SourceLocationObservation.Kind.REPOSITORY_RELATIVE,
                    observed_location=f"repository:{entry['source']['path']}",
                    defaults={
                        "observed_by_import_record": source_record,
                        "availability_state": (
                            SourceLocationObservation.Availability.AVAILABLE),
                        "location_metadata": {"root": "repository",
                                              "manifest_entry_key": key},
                    },
                )
                domain = (_historical if entry["record_type"] == "HISTORICAL_DESIGN"
                          else _asset)(batch, artifact, entry)
                records.extend((source_record, domain))
                created_artifacts += int(artifact_created)
        except Exception as exc:  # noqa: BLE001 - per-entry partial-failure boundary
            failures.append(f"{key}:{type(exc).__name__}"[:200])
    after = _authority_counts()
    if after != before:
        failures.append("AUTHORITY_INVARIANT_CHANGED")
    counts = _count_records(records, failures)
    batch = finalize_import_batch(
        batch,
        status=(ImportBatch.Status.COMPLETED_WITH_ERRORS if failures
                else ImportBatch.Status.COMPLETED),
        counts=counts, failure_summary=";".join(failures)[:4000])
    report.update({
        "batch_id": str(batch.pk), "created_records": counts["imported_records"],
        "unchanged_records": counts["unchanged_records"],
        "new_source_versions": created_artifacts,
        "failed_records": counts["failed_records"], "failures": failures,
        "decision_events_created": after["decision_events"] - before["decision_events"],
        "allowed_permissions_created": (
            after["allowed_permissions"] - before["allowed_permissions"]),
    })
    return report
