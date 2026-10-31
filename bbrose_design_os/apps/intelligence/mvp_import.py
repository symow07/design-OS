"""Idempotent, bounded persistence for the validated DIP-1B MVP manifest."""
from __future__ import annotations

import collections
import re
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path

from django.db import transaction

from apps.accounts.models import DecisionEvent

from .identity import (
    ASSET_IDENTITY_VERSION, CandidateIdentityError, asset_classification_identity_hash,
    asset_fact_identity_hash, evidence_identity_hash, semantic_asset_external_key,
)
from .import_services import finalize_import_batch, record_import_attempt, record_source_version
from .manifest import (
    IMPORTER_IDENTIFIER, IMPORTER_VERSION, PreparedEntry, PreparedManifest, canonical_hash,
    prepare_manifest,
)
from .models import (
    BrandCandidateProfile, CorpusItem, DesignAssetProfile, DesignUnit, EvidenceReference,
    FontFaceProfile, HistoricalDesignProfile, ImportBatch, ImportRecord,
    MachineClassification, ObservedFact, OperationalPermissionProjection, ProvenanceRecord,
    SourceArtifact, SourceLocationObservation,
)

REFERENCE_POLICY = HistoricalDesignProfile.REFERENCE_MEMORY_ONLY
_UNIT_NUMBER = re.compile(r"-u(\d+)$")


def _aware_modified(path: Path):
    return datetime.fromtimestamp(path.stat().st_mtime, tz=dt_timezone.utc)


def _source_values(prepared: PreparedEntry):
    entry = prepared.declaration
    source = entry["source"]
    return {
        "source_identifier": f"{source['root']}:{source['path']}",
        "source_location": f"{source['root']}:{source['path']}",
        "source_type": source["source_type"],
        "media_type": source.get("media_type", ""),
        "sha256": source["sha256"],
        "byte_size": prepared.source_path.stat().st_size,
        "source_modified_at": _aware_modified(prepared.source_path),
        "parser_identifier": entry["parser_identifier"],
        "parser_version": entry["parser_version"],
        "source_schema_version": entry["source_schema_version"],
        "availability_state": SourceArtifact.Availability.AVAILABLE,
    }


def _record_artifact(prepared):
    values = _source_values(prepared)
    # SHA-256 is content identity across relocations and exact duplicates. The first
    # logical identifier remains on SourceArtifact; every newly observed locator is kept
    # separately and conveys no rights to another item.
    artifact = SourceArtifact.objects.filter(sha256=values["sha256"]).order_by(
        "first_observed_at", "id").first()
    if artifact:
        return artifact, False
    return record_source_version(**values)


def _record_location(prepared, artifact, import_record):
    entry = prepared.declaration
    source = entry["source"]
    location = f"{source['root']}:{source['path']}"
    return SourceLocationObservation.objects.get_or_create(
        source_artifact=artifact,
        location_kind=SourceLocationObservation.Kind.CONFIGURED_ROOT_RELATIVE,
        observed_location=location,
        defaults={
            "observed_by_import_record": import_record,
            "availability_state": SourceLocationObservation.Availability.AVAILABLE,
            "location_metadata": {
                "root": source["root"],
                "stable_source_key": entry["stable_source_key"],
            },
        },
    )


def _record_attempt(batch, key, record_hash, prepared, artifact, corpus_item=None,
                    details=None):
    entry = prepared.declaration
    reconciliation = {"dataset_id": entry["dataset_id"]}
    reconciliation.update(details or {})
    row, _ = record_import_attempt(
        import_batch=batch,
        stable_source_record_key=key,
        source_record_hash=record_hash,
        parser_version=entry["parser_version"],
        source_schema_version=entry["source_schema_version"],
        source_artifact=artifact,
        corpus_item=corpus_item,
        reconciliation_details=reconciliation,
    )
    return row


def _evidence(item, artifact, *, kind, schema, locator, observed=""):
    evidence_hash = evidence_identity_hash(
        item_id=item.pk, source_hash=artifact.sha256, kind=kind,
        schema=schema, locator=locator, observed=observed,
    )
    existing = EvidenceReference.objects.filter(
        corpus_item=item, source_artifact=artifact, evidence_hash=evidence_hash).first()
    if existing:
        return existing
    return EvidenceReference.objects.create(
        corpus_item=item, source_artifact=artifact, evidence_kind=kind,
        locator_schema_version=schema, locator=locator,
        observed_value=str(observed)[:2000], evidence_hash=evidence_hash,
        is_test_only=False,
    )


def _provenance(item, artifact, prepared, evidence_type):
    dataset_id = prepared.declaration["dataset_id"]
    reference = f"{dataset_id}:{prepared.declaration['stable_source_key']}"
    row = ProvenanceRecord.objects.filter(
        corpus_item=item, source_artifact=artifact, provenance_type=evidence_type,
        acquisition_reference=reference).first()
    if row:
        return row
    return ProvenanceRecord.objects.create(
        corpus_item=item, source_artifact=artifact, provenance_type=evidence_type,
        source_package=dataset_id,
        acquisition_reference=reference,
        normalized_machine_interpretation={
            "candidate_evidence_only": True,
            "operational_permission_inferred": False,
        },
    )


def _fact(item, artifact, evidence, fact_type, value, prepared, raw_value="",
          origin_scoped=False):
    fact_hash = (asset_fact_identity_hash(
        fact_type=fact_type, value=value, evidence_hash=evidence.evidence_hash,
    ) if origin_scoped else canonical_hash({"type": fact_type, "value": value}))
    row = ObservedFact.objects.filter(
        corpus_item=item, fact_type=fact_type, source_artifact=artifact,
        fact_hash=fact_hash).first()
    if row:
        return row
    return ObservedFact.objects.create(
        corpus_item=item, fact_type=fact_type, normalized_value=value,
        raw_value=str(raw_value)[:4000], value_schema_version="observed_fact/1.0",
        source_artifact=artifact, evidence_reference=evidence,
        importer_identifier=IMPORTER_IDENTIFIER, importer_version=IMPORTER_VERSION,
        fact_hash=fact_hash,
    )


def _classification(item, artifact, evidence, classification_type, label, confidence,
                    explanation, prepared, origin_scoped=False):
    value = {
        "type": classification_type, "label": str(label),
        "confidence": round(float(confidence or 0), 4), "explanation": explanation,
    }
    classification_hash = (asset_classification_identity_hash(
        classification_type=classification_type, label=value["label"],
        confidence=value["confidence"], explanation=value["explanation"],
        evidence_hash=evidence.evidence_hash,
    ) if origin_scoped else canonical_hash(value))
    row = MachineClassification.objects.filter(
        corpus_item=item, classification_type=classification_type,
        source_artifact=artifact, classification_hash=classification_hash).first()
    if row:
        return row
    return MachineClassification.objects.create(
        corpus_item=item, classification_type=classification_type,
        label=str(label)[:255], confidence=Decimal(str(value["confidence"])),
        classifier_identifier=prepared.declaration["parser_identifier"],
        classifier_version=prepared.declaration["parser_version"],
        classification_schema_version="machine_classification/1.0",
        source_artifact=artifact, evidence_reference=evidence,
        structured_explanation=explanation or {},
        classification_hash=classification_hash,
    )


def _item(kind, external_key):
    return CorpusItem.objects.get_or_create(item_kind=kind, external_key=external_key)[0]


def _historical(batch, prepared, rows, artifact):
    entry = prepared.declaration
    item = _item(CorpusItem.Kind.HISTORICAL_DESIGN,
                 f"historical:{entry['stable_source_key']}")
    pages = sorted({int(row.get("page") or 0) for row in rows})
    evidence = _evidence(
        item, artifact, kind="SOURCE_FILE", schema="source_file/1.0",
        locator={"path": entry["source"]["path"]}, observed=artifact.sha256)
    _provenance(item, artifact, prepared, "DIP0_HISTORICAL_MEMORY_IMPORT")
    profile, _ = HistoricalDesignProfile.objects.get_or_create(
        corpus_item=item,
        defaults={
            "primary_source_artifact": artifact,
            "display_title": entry["display_label"],
            "page_artboard_count": len(pages),
            "extracted_design_unit_count": len(rows),
            "audit_status": HistoricalDesignProfile.AuditStatus.MACHINE_AUDITED,
            "historical_period_observed": entry["metadata"].get("historical_period", ""),
            "product_family_machine_label": "",
            "reference_memory_policy": REFERENCE_POLICY,
        },
    )
    _fact(item, artifact, evidence, "HISTORICAL_SOURCE_SUMMARY", {
        "page_artboard_count": len(pages), "design_unit_count": len(rows),
        "source_sha256": artifact.sha256, "reference_memory_only": True,
    }, prepared)
    attempts = [_record_attempt(
        batch, f"historical:{entry['stable_source_key']}", canonical_hash(rows),
        prepared, artifact, item,
        {"design_unit_count": len(rows), "reference_memory_only": True})]
    for fallback_ordinal, row in enumerate(rows):
        unit_key = str(row["unit_id"])
        page = int(row.get("page") or 0)
        unit_evidence = _evidence(
            item, artifact, kind="FILE_PAGE_UNIT", schema="file_page/1.0",
            locator={"page": page, "unit_key": unit_key}, observed=unit_key)
        bbox = row.get("bbox_pt") or []
        geometry = (None, None, None, None)
        if len(bbox) == 4 and all(isinstance(v, (int, float)) and v >= 0 for v in bbox):
            geometry = (bbox[0], bbox[1], max(0, bbox[2] - bbox[0]),
                        max(0, bbox[3] - bbox[1]))
        match = _UNIT_NUMBER.search(unit_key)
        ordinal = int(match.group(1)) if match else fallback_ordinal
        extraction = row.get("segmentation_status") or "REVIEW_REQUIRED"
        extraction = {
            "AUTO_CONFIDENT": DesignUnit.ExtractionStatus.AUTO_CONFIDENT,
            "AUTO_LOW_CONFIDENCE": DesignUnit.ExtractionStatus.AUTO_LOW_CONFIDENCE,
            "UNAVAILABLE": DesignUnit.ExtractionStatus.UNAVAILABLE,
        }.get(extraction, DesignUnit.ExtractionStatus.REVIEW_REQUIRED)
        DesignUnit.objects.get_or_create(
            historical_design_profile=profile, stable_unit_key=unit_key,
            defaults={
                "unit_type": row.get("candidate_type", DesignUnit.UnitType.UNKNOWN),
                "ordinal": ordinal, "source_page_artboard": page,
                "geometry_x": geometry[0], "geometry_y": geometry[1],
                "geometry_width": geometry[2], "geometry_height": geometry[3],
                "technical_summary": "; ".join(row.get("machine_review_reasons", []))[:2000],
                "extraction_status": extraction, "source_artifact": artifact,
                "evidence_reference": unit_evidence,
            },
        )
        _fact(item, artifact, unit_evidence, "HISTORICAL_UNIT_TECHNICAL", {
            "unit_key": unit_key,
            "vector_count": max(0, int(row.get("vector_count") or 0)),
            "raster_count": max(0, int(row.get("raster_count") or 0)),
            "whitespace_ratio": row.get("whitespace_ratio"),
            "colour_classes": row.get("colour_classes") or {},
        }, prepared)
        _classification(
            item, artifact, unit_evidence, "DESIGN_UNIT_TYPE",
            row.get("candidate_type", "UNKNOWN"), row.get("candidate_confidence") or 0,
            {"unit_key": unit_key, "machine_generated": True}, prepared)
        attempts.append(_record_attempt(
            batch, f"design-unit:{unit_key}", canonical_hash(row), prepared, artifact, item,
            {"reference_memory_only": True}))
    return attempts


def _asset_kind(candidate):
    value = (candidate.get("asset_type", {}).get("value")
             or candidate.get("inventory_category_original") or "UNKNOWN").upper()
    if "LOGO" in value:
        return DesignAssetProfile.CandidateKind.LOGO_CANDIDATE
    for token in ("MOTIF", "BACKGROUND", "ILLUSTRATION", "PATTERN", "PHOTO"):
        if token in value:
            return token
    return DesignAssetProfile.CandidateKind.UNKNOWN


def _representation(candidate):
    source = candidate.get("source_file", {})
    fmt = str(source.get("format", "")).lower()
    if fmt in (".ai", ".eps", ".svg", ".pdf"):
        return DesignAssetProfile.Representation.VECTOR
    if fmt in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        return DesignAssetProfile.Representation.RASTER
    return DesignAssetProfile.Representation.UNKNOWN


def _asset(batch, prepared, candidate, record_hash, candidate_index, artifact):
    candidate_id = str(candidate["candidate_id"])
    source_entry_key = prepared.declaration["stable_source_key"]
    dataset_id = prepared.declaration["dataset_id"]
    profiles = list(DesignAssetProfile.objects.select_related("corpus_item").filter(
        dataset_identifier=dataset_id, candidate_source_key=candidate_id,
    )[:2])
    if len(profiles) > 1:
        raise CandidateIdentityError(
            f"candidate {candidate_id!r} has ambiguous persisted subjects; "
            "run the bounded identity reconciliation"
        )
    existing_profile = profiles[0] if profiles else None
    item = (existing_profile.corpus_item if existing_profile else _item(
        CorpusItem.Kind.DESIGN_ASSET,
        semantic_asset_external_key(dataset_id, candidate_id),
    ))
    page = int(candidate.get("page_or_artboard") or 0)
    evidence = _evidence(
        item, artifact, kind="C2_ASSET_CANDIDATE_RECORD",
        schema="json_path/1.0",
        locator={
            "path": prepared.declaration["data_source"]["source"]["path"],
            "segments": prepared.declaration["data_source"]["locator"]["value"][
                "segments"] + [candidate_index],
        }, observed=candidate_id)
    _provenance(item, artifact, prepared, "DIP0_ASSET_CANDIDATE_IMPORT")
    readiness = candidate.get("A_technical_readiness", {}).get(
        "value", DesignAssetProfile.Readiness.REVIEW_REQUIRED)
    if readiness not in DesignAssetProfile.Readiness.values:
        readiness = DesignAssetProfile.Readiness.REVIEW_REQUIRED
    collection = candidate.get("collection") or {}
    bbox = candidate.get("bbox_pt") or candidate.get("bbox_px") or []
    profile, _ = DesignAssetProfile.objects.get_or_create(
        corpus_item=item,
        defaults={
            "primary_source_artifact": artifact,
            "candidate_source_key": candidate_id,
            "source_manifest_entry_key": source_entry_key,
            "dataset_identifier": dataset_id,
            "candidate_asset_kind": _asset_kind(candidate),
            "representation_state": _representation(candidate),
            "technical_readiness": readiness,
            "extraction_state": str(candidate.get("segmentation", {}).get(
                "status", "REVIEW_REQUIRED"))[:32],
            "collection_family_label": str(collection.get("parent_source") or "")[:255],
            "dimensions_media": {
                "bounds": bbox[:4] if isinstance(bbox, list) else [],
                "bounds_unit": "pt" if candidate.get("bbox_pt") else "px",
                "page_artboard": page,
            },
            "is_test_only": False,
        },
    )
    canonical_source_entry = min(profile.source_manifest_entry_key, source_entry_key)
    if profile.source_manifest_entry_key != canonical_source_entry:
        profile.source_manifest_entry_key = canonical_source_entry
        profile.save(update_fields=("source_manifest_entry_key",))
    _fact(item, artifact, evidence, "ASSET_TECHNICAL_OBSERVATION", {
        "candidate_id": candidate_id, "technical_readiness": readiness,
        "extraction_state": candidate.get("segmentation", {}).get("status"),
        "representation": _representation(candidate),
        "bounds": bbox[:4] if isinstance(bbox, list) else [],
        "dataset_id": dataset_id,
    }, prepared, origin_scoped=True)
    asset_type = candidate.get("asset_type") or {}
    _classification(
        item, artifact, evidence, "ASSET_CANDIDATE_TYPE",
        asset_type.get("value") or "UNKNOWN_ASSET_TYPE",
        candidate.get("isolated_candidate_confidence") or 0,
        {"tier": asset_type.get("tier", "HEURISTIC"), "machine_generated": True},
        prepared, origin_scoped=True)
    return _record_attempt(
        batch, f"asset-candidate:{source_entry_key}:{candidate_id}", record_hash,
        prepared, artifact, item,
        {"candidate_review_only": True, "c2_candidate_key": candidate_id,
         "originating_record_locator": evidence.locator,
         "semantic_identity_version": ASSET_IDENTITY_VERSION,
         "semantic_external_key": item.external_key})


def _font(batch, prepared, face, artifact):
    machine = face["machine"]
    group = prepared.declaration["metadata"]["curated_group_id"]
    item = _item(CorpusItem.Kind.FONT, f"font:{group}")
    face_index = int(machine.get("collection_index") or 0)
    evidence = _evidence(
        item, artifact, kind="FONT_FACE", schema="font_face/1.0",
        locator={"face_index": face_index, "face_id": machine["face_id"]},
        observed=machine.get("postscript_name") or machine["face_id"])
    _provenance(item, artifact, prepared, "DIP0_FONT_CANDIDATE_IMPORT")
    evidence_state = (FontFaceProfile.EvidenceState.PRESENT_UNREVIEWED
                      if machine.get("license_evidence_mentioning_fonts")
                      else FontFaceProfile.EvidenceState.ABSENT)
    health = machine.get("technical_health")
    suitability = (FontFaceProfile.Suitability.HEALTHY if health == "HEALTHY"
                   else FontFaceProfile.Suitability.TECHNICAL_CAVEAT)
    FontFaceProfile.objects.get_or_create(
        corpus_item=item,
        defaults={
            "primary_source_artifact": artifact, "face_index": face_index,
            "family_name": str(prepared.declaration["metadata"].get("family")
                               or machine.get("preferred_family")
                               or machine.get("fallback_family") or "Unknown")[:255],
            "subfamily": str(machine.get("subfamily") or "")[:255],
            "postscript_name": str(machine.get("postscript_name") or "")[:255],
            "weight": machine.get("weight_class"),
            "width": str(machine.get("width_class") or "")[:32],
            "italic": bool(machine.get("italic")),
            "variable_axes": machine.get("variable_axes") or [],
            "script_coverage": machine.get("script_coverage") or {},
            "suspected_system_copy": machine.get("system_font_suspicion")
            not in (None, "NO_SYSTEM_FONT_EVIDENCE"),
            "evidence_state": evidence_state,
            "technical_suitability_state": suitability,
        },
    )
    _fact(item, artifact, evidence, "FONT_TECHNICAL_OBSERVATION", {
        "face_id": machine["face_id"], "glyph_count": machine.get("glyph_count"),
        "technical_health": health, "scripts": machine.get("scripts") or [],
        "variable": bool(machine.get("is_variable")),
        "evidence_present_unreviewed": evidence_state
        == FontFaceProfile.EvidenceState.PRESENT_UNREVIEWED,
    }, prepared)
    _classification(
        item, artifact, evidence, "FONT_CURATED_STARTER_CANDIDATE",
        "CURATED_STARTER_CANDIDATE", 0.5,
        {"curated_group_id": group, "machine_generated": True,
         "not_a_licence_or_usage_conclusion": True}, prepared)
    return _record_attempt(
        batch, f"font-candidate:{group}", canonical_hash(face), prepared, artifact, item,
        {"technical_candidate_only": True})


def _brand_kind(candidate):
    filename = str(candidate.get("filename") or "").upper()
    if "LOGO" in filename:
        return BrandCandidateProfile.CandidateKind.LOGO
    if candidate.get("brand_master_candidate"):
        return BrandCandidateProfile.CandidateKind.WORDMARK
    if str(candidate.get("format", "")).lower() == ".ase":
        return BrandCandidateProfile.CandidateKind.PALETTE
    return BrandCandidateProfile.CandidateKind.BRAND_GRAPHIC


def _brand_representation(candidate):
    value = str(candidate.get("vector_or_raster") or "").upper()
    return value if value in BrandCandidateProfile.Representation.values \
        else BrandCandidateProfile.Representation.UNKNOWN


def _brand(batch, prepared, candidate, artifact):
    key = prepared.declaration["stable_source_key"]
    item = _item(CorpusItem.Kind.BRAND_ASSET, f"brand:{key}")
    evidence = _evidence(
        item, artifact, kind="SOURCE_FILE", schema="source_file/1.0",
        locator={"path": prepared.declaration["source"]["path"]},
        observed=artifact.sha256)
    _provenance(item, artifact, prepared, "DIP0_BRAND_CANDIDATE_IMPORT")
    detected_third_party = candidate.get("detected_third_party_brand", {}).get("value")
    brand_label = (candidate.get("brand_name", {}).get("value")
                   or detected_third_party or "")
    warning = (BrandCandidateProfile.Warning.THIRD_PARTY_OR_UNCONFIRMED
               if detected_third_party or not brand_label
               else BrandCandidateProfile.Warning.REQUIRES_REVIEW)
    BrandCandidateProfile.objects.get_or_create(
        corpus_item=item,
        defaults={
            "primary_source_artifact": artifact,
            "candidate_kind": _brand_kind(candidate),
            "observed_brand_label": str(brand_label)[:255],
            "technical_format": str(candidate.get("format") or "UNKNOWN")[:32],
            "representation_state": _brand_representation(candidate),
            "observed_candidate_data": {
                "page_count": candidate.get("page_count"),
                "path_count": candidate.get("path_count"),
                "raster_coverage": candidate.get("raster_coverage"),
                "spot_colors": (candidate.get("spot_colors") or [])[:32],
            },
            "warning_state": warning,
            "candidate_status": BrandCandidateProfile.Status.UNCONFIRMED,
        },
    )
    _fact(item, artifact, evidence, "BRAND_ASSET_TECHNICAL_OBSERVATION", {
        "format": candidate.get("format"), "page_count": candidate.get("page_count"),
        "path_count": candidate.get("path_count"),
        "representation": _brand_representation(candidate),
    }, prepared)
    _classification(
        item, artifact, evidence, "OBSERVED_BRAND_LABEL", brand_label or "UNKNOWN",
        candidate.get("brand_name", {}).get("confidence") or 0,
        {"third_party_or_unconfirmed": warning
         == BrandCandidateProfile.Warning.THIRD_PARTY_OR_UNCONFIRMED,
         "machine_generated": True}, prepared)
    return _record_attempt(
        batch, f"brand-candidate:{key}", canonical_hash(candidate), prepared, artifact, item,
        {"candidate_only": True})


def _palette(batch, prepared, palette, artifact):
    key = prepared.declaration["stable_source_key"]
    item = _item(CorpusItem.Kind.BRAND_PALETTE, f"palette:{key}")
    evidence = _evidence(
        item, artifact, kind="SOURCE_FILE", schema="source_file/1.0",
        locator={"path": prepared.declaration["source"]["path"]},
        observed=artifact.sha256)
    _provenance(item, artifact, prepared, "DIP0_PALETTE_CANDIDATE_IMPORT")
    technical = palette.get("palette") or {}
    BrandCandidateProfile.objects.get_or_create(
        corpus_item=item,
        defaults={
            "primary_source_artifact": artifact,
            "candidate_kind": BrandCandidateProfile.CandidateKind.PALETTE,
            "observed_brand_label": "Pantone 3519 C",
            "technical_format": str(technical.get("format") or "ASE")[:32],
            "representation_state": BrandCandidateProfile.Representation.UNKNOWN,
            "observed_candidate_data": {
                "parse_status": technical.get("parse_status"),
                "swatch_count": technical.get("swatch_count"),
                "color_models": technical.get("color_models") or [],
                "parser_warnings": technical.get("parser_warnings") or [],
            },
            "warning_state": BrandCandidateProfile.Warning.PARTIAL_PARSE,
            "candidate_status": BrandCandidateProfile.Status.REVIEW_REQUIRED,
        },
    )
    _fact(item, artifact, evidence, "PALETTE_TECHNICAL_OBSERVATION", {
        "format": technical.get("format"), "parse_status": technical.get("parse_status"),
        "swatch_count": technical.get("swatch_count"),
        "fallback_used": bool(technical.get("fallback_used")),
        "non_authoritative": True,
    }, prepared)
    _classification(
        item, artifact, evidence, "PALETTE_PARSE_STATUS",
        technical.get("parse_status") or "UNKNOWN", 0.5,
        {"partial_non_authoritative_parse": True, "machine_generated": True}, prepared)
    return _record_attempt(
        batch, f"palette-candidate:{key}", canonical_hash(palette), prepared, artifact, item,
        {"candidate_only": True, "palette_unapproved": True})


def _batch_counts(records):
    disposition = collections.Counter(row.disposition for row in records)
    return {
        "total_records": len(records),
        "imported_records": disposition[ImportRecord.Disposition.CREATED],
        "unchanged_records": disposition[ImportRecord.Disposition.UNCHANGED],
        "changed_records": disposition[ImportRecord.Disposition.NEW_VERSION],
        "skipped_records": disposition[ImportRecord.Disposition.SKIPPED],
        "quarantined_records": disposition[ImportRecord.Disposition.QUARANTINED],
        "failed_records": disposition[ImportRecord.Disposition.FAILED],
    }


def import_prepared_manifest(prepared: PreparedManifest, *, fail_record_key=None):
    before_decisions = DecisionEvent.objects.count()
    before_allowed = OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).count()
    batch = ImportBatch.objects.create(
        importer_identifier=IMPORTER_IDENTIFIER, importer_version=IMPORTER_VERSION,
        configuration_hash=canonical_hash({
            "schema": prepared.document["schema_version"], "mode": "bounded_mvp"}),
        source_manifest_hash=prepared.manifest_hash,
        scope={"manifest_id": prepared.document["manifest_id"],
               "expected_counts": prepared.actual_counts,
               "datasets": prepared.document["datasets"]},
    )
    records = []
    artifacts = {}
    failures = []

    for prepared_entry in prepared.entries:
        entry = prepared_entry.declaration
        key = f"source:{entry['stable_source_key']}"
        try:
            with transaction.atomic():
                if fail_record_key == key:
                    raise RuntimeError("injected bounded test failure")
                artifact, _ = _record_artifact(prepared_entry)
                record = _record_attempt(
                    batch, key, canonical_hash(entry), prepared_entry, artifact,
                    details={"source_declaration": True})
                _record_location(prepared_entry, artifact, record)
                if entry["record_type"] == "SOURCE_AUDIT_EVIDENCE":
                    reference = f"{entry['dataset_id']}:{entry['stable_source_key']}"
                    if not ProvenanceRecord.objects.filter(
                            source_artifact=artifact, corpus_item__isnull=True,
                            provenance_type="DIP0C1_SOURCE_AUDIT_EVIDENCE",
                            acquisition_reference=reference).exists():
                        ProvenanceRecord.objects.create(
                            source_artifact=artifact,
                            provenance_type="DIP0C1_SOURCE_AUDIT_EVIDENCE",
                            source_package=entry["dataset_id"],
                            acquisition_reference=reference,
                            normalized_machine_interpretation={
                                "frozen_source_audit": True,
                                "candidate_list_authority": False,
                                "overlap_lineage_only": True,
                            },
                        )
                artifacts[entry["stable_source_key"]] = artifact
                records.append(record)
        except Exception as exc:  # noqa: BLE001 - isolate each bounded source record
            failures.append(f"{key}:{type(exc).__name__}"[:200])

    domain_calls = []
    for entry, rows in prepared.domain_records["historical"]:
        domain_calls.append((f"historical:{entry.declaration['stable_source_key']}",
                             _historical, (entry, rows)))
    for entry, candidate, record_hash, candidate_index in prepared.domain_records["assets"]:
        domain_calls.append((
            f"asset-candidate:{entry.declaration['stable_source_key']}:{candidate['candidate_id']}",
                             _asset, (entry, candidate, record_hash, candidate_index)))
    for entry, face in prepared.domain_records["fonts"]:
        domain_calls.append((f"font-candidate:{entry.declaration['metadata']['curated_group_id']}",
                             _font, (entry, face)))
    for entry, candidate in prepared.domain_records["brands"]:
        domain_calls.append((f"brand-candidate:{entry.declaration['stable_source_key']}",
                             _brand, (entry, candidate)))
    for entry, palette in prepared.domain_records["palettes"]:
        domain_calls.append((f"palette-candidate:{entry.declaration['stable_source_key']}",
                             _palette, (entry, palette)))

    for key, handler, args in domain_calls:
        prepared_entry = args[0]
        artifact = artifacts.get(prepared_entry.declaration["stable_source_key"])
        if artifact is None:
            failures.append(f"{key}:SOURCE_UNAVAILABLE"[:200])
            continue
        try:
            with transaction.atomic():
                if fail_record_key == key:
                    raise RuntimeError("injected bounded test failure")
                result = handler(batch, *args, artifact)
                records.extend(result if isinstance(result, list) else [result])
        except Exception as exc:  # noqa: BLE001 - preserve all prior successful records
            failures.append(f"{key}:{type(exc).__name__}"[:200])

    after_decisions = DecisionEvent.objects.count()
    after_allowed = OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).count()
    if after_decisions != before_decisions or after_allowed != before_allowed:
        failures.append("AUTHORITY_INVARIANT_CHANGED")
    counts = _batch_counts(records)
    counts["failed_records"] += len(failures)
    counts["total_records"] += len(failures)
    status = (ImportBatch.Status.COMPLETED_WITH_ERRORS if failures
              else ImportBatch.Status.COMPLETED)
    batch = finalize_import_batch(
        batch, status=status, counts=counts, failure_summary=";".join(failures)[:4000])
    return {
        "batch": batch, "counts": prepared.actual_counts,
        "import_records": counts,
        "decision_events_before": before_decisions,
        "decision_events_after": after_decisions,
        "allowed_before": before_allowed, "allowed_after": after_allowed,
        "failures": tuple(failures),
    }


def run_import(manifest_path, *, apply=False, fail_record_key=None):
    prepared = prepare_manifest(manifest_path)
    preview = {
        "mode": "apply" if apply else "dry-run",
        "manifest_schema": prepared.document["schema_version"],
        "manifest_id": prepared.document["manifest_id"],
        "manifest_hash": prepared.manifest_hash,
        "counts": prepared.actual_counts,
    }
    if not apply:
        return preview
    preview.update(import_prepared_manifest(prepared, fail_record_key=fail_record_key))
    return preview
