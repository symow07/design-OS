"""Deterministic C3a successor evidence for DIP-1B-5A.

The frozen C3a declaration and the ignored generator output remain historical inputs.
This module projects only technical, semantically relevant fields into a new schema and
never treats the projection as ownership, rights, canonical status, or permission.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from pathlib import Path

from django.conf import settings

from .locator_schemas import normalize_relative_path

DATASET_ID = "dip1b_brand_evidence/2.0"
DATASET_SCHEMA = "dip1b_brand_evidence/2.0"
MANIFEST_ID = "dip1b_brand_evidence_manifest/2.0"
MANIFEST_SCHEMA = "dip1b_brand_evidence_manifest/2.0"
GENERATOR_IDENTIFIER = "bbrose.intelligence.brand_evidence"
GENERATOR_VERSION = "2.0"
CANONICALIZATION_IDENTIFIER = "bbrose.intelligence.brand_evidence.canonical_json"
CANONICALIZATION_VERSION = "1.0"
ORIGIN_DATASET_ID = "dip0c3_brand_candidates/1.0"

ORIGINAL_FROZEN_EXPECTED_SHA256 = (
    "dfccbad26e98744e78d606fec85a301a9d3d2357ff17cf8ece5fcbe7a2d9e62b")
STALE_IGNORED_OUTPUT_SHA256 = (
    "b4a891debabebdb721b919fa793264c5e8c2e671f5e2d5f3e5218e284d2f5cbf")
FROZEN_MVP_MANIFEST_SHA256 = (
    "7dbb22815265c0dc790e74003840fb861299beddd020179094f36129f86186aa")
C3_CONFIGURATION_SHA256 = (
    "9dde40cf679fab5e388626b4d9ef9782536915f28a25adbc172abc2f81787d68")
ACCEPTED_IMPORT_MANIFEST_SHA256 = (
    "824434857fced5bae40d7786f3ef372a1b7ba524f72d9e9ab961eb65ce096692")

DEFAULT_C3A_OUTPUT = (
    Path(settings.BASE_DIR).parent
    / "var/design_intelligence/audits/dip0c/c3a/brand_candidates.json")
DEFAULT_FROZEN_MANIFEST = (
    Path(settings.BASE_DIR).parent
    / "docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json")
DEFAULT_CONFIGURATION = (
    Path(settings.BASE_DIR).parent
    / "docs/design_intelligence/dip0c/c3_pilot_manifest.json")
DEFAULT_DATASET_PATH = (
    Path(settings.BASE_DIR).parent
    / "docs/design_intelligence/dip1/dip1b_brand_evidence_2_0.json")
DEFAULT_MANIFEST_PATH = (
    Path(settings.BASE_DIR).parent
    / "docs/design_intelligence/dip1/dip1b_brand_evidence_manifest_2_0.json")

TECHNICAL_FIELDS = frozenset({
    "relative_path", "filename", "source_package", "format", "dip0a_classification",
    "queue_i_membership", "parser", "vector_or_raster", "page_count",
    "bounding_box_mm", "path_count", "raster_coverage", "embedded_image_count",
    "live_text_present", "live_text_spans", "outlined_wordmark_likelihood",
    "fonts_detected", "transparency", "gradients", "spot_colors",
    "process_colors_count", "editability", "technical_readiness", "brand_name",
    "detected_third_party_brand", "isolated_logo_likelihood",
    "raster_heavy_composition", "name_and_folder_evidence", "capability_limitations",
    "classification_override", "brand_master_candidate",
})
REQUIRED_TECHNICAL_FIELDS = frozenset({
    "relative_path", "filename", "source_package", "format",
    "dip0a_classification", "queue_i_membership", "parser",
    "vector_or_raster", "brand_name", "isolated_logo_likelihood",
    "name_and_folder_evidence", "capability_limitations",
    "classification_override", "brand_master_candidate",
})
EXCLUDED_EXECUTION_FIELDS = frozenset({
    "extracted_at", "runtime_timestamp", "runtime_path", "temporary_path",
    "temporary_directory", "host", "hostname",
})


class BrandEvidenceError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class BrandEvidenceBundle:
    dataset_document: dict
    dataset_bytes: bytes
    dataset_sha256: str
    manifest_document: dict
    manifest_bytes: bytes
    manifest_sha256: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value) -> bytes:
    try:
        return (json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BrandEvidenceError("canonical evidence contains unsupported JSON") from exc


def canonical_hash(value) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _load_json(path: Path, label: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrandEvidenceError(f"{label} is unavailable or invalid") from exc


def _semantic_value(value):
    if isinstance(value, dict):
        return {
            key: _semantic_value(child)
            for key, child in sorted(value.items())
            if key not in EXCLUDED_EXECUTION_FIELDS
        }
    if isinstance(value, list):
        return [_semantic_value(child) for child in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise BrandEvidenceError("technical evidence contains an unsupported value")


def _technical_projection(record: dict) -> dict:
    if not isinstance(record, dict):
        raise BrandEvidenceError("C3a record must be an object")
    missing = REQUIRED_TECHNICAL_FIELDS - set(record)
    if missing:
        raise BrandEvidenceError(f"C3a record is missing required technical fields: "
                                 f"{sorted(missing)}")
    return {
        key: _semantic_value(record.get(key))
        for key in sorted(TECHNICAL_FIELDS)
    }


def _brand_entries(frozen_manifest: dict) -> tuple[dict, ...]:
    if (frozen_manifest.get("schema_version") != "dip1b_mvp_manifest/1.0"
            or frozen_manifest.get("manifest_id") != "dip1b_mvp_manifest/1.0"):
        raise BrandEvidenceError("frozen MVP manifest identity is invalid")
    entries = tuple(entry for entry in frozen_manifest.get("entries", ()) if (
        isinstance(entry, dict)
        and entry.get("dataset_id") == ORIGIN_DATASET_ID
        and entry.get("record_type") == "BRAND_CANDIDATE"
    ))
    if len(entries) != 21:
        raise BrandEvidenceError("expected exactly 21 frozen C3a brand entries")
    return entries


def _migrated(path: Path, repository_root: Path, relative: str) -> Path:
    """The committed relative path stays the record's identity; the Day 6 manifest locates the bytes."""
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        return resolve_material_file(path, repo_root=repository_root)
    except MaterialPathError as exc:
        raise BrandEvidenceError(f"source-input migration invalid: {relative}") from exc


def _validate_source_input(entry: dict, repository_root: Path) -> dict:
    source = entry.get("source")
    if not isinstance(source, dict) or set(source) not in (
            {"root", "path", "sha256", "source_type"},
            {"root", "path", "sha256", "source_type", "media_type"}):
        raise BrandEvidenceError("frozen C3a source declaration is invalid")
    if source.get("root") != "repository":
        raise BrandEvidenceError("C3a source must use the repository root")
    relative = normalize_relative_path(source.get("path"))
    if not relative.startswith("materials/"):
        raise BrandEvidenceError("C3a physical source is outside materials")
    path = (repository_root / relative).resolve()
    try:
        path.relative_to(repository_root.resolve())
    except ValueError as exc:
        raise BrandEvidenceError("C3a physical source escapes repository root") from exc
    path = _migrated(path, repository_root, relative)
    if not path.is_file() or sha256_file(path) != source.get("sha256"):
        raise BrandEvidenceError(f"C3a physical source hash mismatch: {relative}")
    return {
        "root": "repository", "path": relative, "sha256": source["sha256"],
        "source_type": source["source_type"],
        **({"media_type": source["media_type"]} if source.get("media_type") else {}),
    }


def build_brand_evidence_bundle(
        *, c3a_document, frozen_manifest, configuration_bytes: bytes,
        preserved_import_records, repository_root: Path,
        frozen_manifest_bytes: bytes | None = None) -> BrandEvidenceBundle:
    """Build canonical dataset and binding manifest from explicit preserved inputs."""
    if not isinstance(c3a_document, list) or len(c3a_document) != 21:
        raise BrandEvidenceError("C3a input must contain exactly 21 records")
    if sha256_bytes(configuration_bytes) != C3_CONFIGURATION_SHA256:
        raise BrandEvidenceError("C3a configuration hash is not the pinned version")
    if (frozen_manifest_bytes is not None
            and sha256_bytes(frozen_manifest_bytes) != FROZEN_MVP_MANIFEST_SHA256):
        raise BrandEvidenceError("frozen MVP manifest hash is not the pinned version")
    entries = _brand_entries(frozen_manifest)
    records_by_path = {}
    for record in c3a_document:
        if not isinstance(record, dict) or not isinstance(record.get("relative_path"), str):
            raise BrandEvidenceError("C3a record has no relative_path identity")
        relative = normalize_relative_path(record["relative_path"])
        if relative in records_by_path:
            raise BrandEvidenceError("C3a record paths are not unique")
        records_by_path[relative] = record
    provenance = {
        row["stable_source_key"]: row for row in preserved_import_records
        if isinstance(row, dict) and isinstance(row.get("stable_source_key"), str)
    }
    if len(provenance) != 21:
        raise BrandEvidenceError("expected 21 unique preserved ImportRecord identities")

    canonical_records = []
    source_inputs = {}
    record_bindings = []
    for entry in sorted(entries, key=lambda row: row["stable_source_key"]):
        stable_key = entry["stable_source_key"]
        source = _validate_source_input(entry, Path(repository_root))
        source_inputs[(source["path"], source["sha256"])] = source
        record = records_by_path.get(source["path"])
        if record is None:
            raise BrandEvidenceError(f"C3a record missing for {stable_key}")
        preserved = provenance.get(stable_key)
        if (not preserved
                or preserved.get("dataset_id") != ORIGIN_DATASET_ID
                or preserved.get("source_record_hash") is None
                or len(str(preserved["source_record_hash"])) != 64):
            raise BrandEvidenceError(f"preserved ImportRecord invalid for {stable_key}")
        data_source = entry.get("data_source") or {}
        locator = data_source.get("locator") or {}
        locator_value = locator.get("value") or {}
        if (locator.get("schema_version") != "json_path/1.0"
                or locator_value.get("path")
                != "var/design_intelligence/audits/dip0c/c3a/brand_candidates.json"
                or not isinstance(locator_value.get("segments"), list)):
            raise BrandEvidenceError("frozen C3a record locator is invalid")
        canonical_record = {
            "stable_candidate_key": stable_key,
            "originating_dataset_id": ORIGIN_DATASET_ID,
            "originating_record_locator": {
                "schema_version": "json_path/1.0",
                "path": locator_value["path"],
                "segments": locator_value["segments"],
            },
            "preserved_import_record_hash": preserved["source_record_hash"],
            "source_input": source,
            "technical_evidence": _technical_projection(record),
            "unavailable_technical_fields": sorted(TECHNICAL_FIELDS - set(record)),
            "authority_boundary": {
                "ownership_proven": False,
                "rights_proven": False,
                "canonical_status_proven": False,
                "operational_permission_granted": False,
            },
        }
        record_hash = canonical_hash(canonical_record)
        canonical_record["canonical_record_hash"] = record_hash
        canonical_records.append(canonical_record)
        record_bindings.append({
            "stable_candidate_key": stable_key,
            "preserved_import_record_hash": preserved["source_record_hash"],
            "canonical_record_hash": record_hash,
            "source_sha256": source["sha256"],
        })
    if set(records_by_path) != {row["source_input"]["path"] for row in canonical_records}:
        raise BrandEvidenceError("C3a input contains records outside the frozen 21-entry scope")

    dataset_document = {
        "schema_version": DATASET_SCHEMA,
        "dataset_id": DATASET_ID,
        "generator": {
            "identifier": GENERATOR_IDENTIFIER, "version": GENERATOR_VERSION,
        },
        "canonicalization": {
            "identifier": CANONICALIZATION_IDENTIFIER,
            "version": CANONICALIZATION_VERSION,
            "serialization": "UTF8_SORTED_KEYS_COMPACT_JSON_TRAILING_LF",
            "record_order": "STABLE_CANDIDATE_KEY_ASCENDING",
            "excluded_execution_fields": sorted(EXCLUDED_EXECUTION_FIELDS),
        },
        "configuration": {
            "path": "docs/design_intelligence/dip0c/c3_pilot_manifest.json",
            "sha256": C3_CONFIGURATION_SHA256,
        },
        "frozen_lineage": {
            "originating_dataset_id": ORIGIN_DATASET_ID,
            "frozen_manifest_id": "dip1b_mvp_manifest/1.0",
            "frozen_manifest_sha256": FROZEN_MVP_MANIFEST_SHA256,
            "original_frozen_expected_sha256": ORIGINAL_FROZEN_EXPECTED_SHA256,
            "expected_historical_bytes_recovered": False,
        },
        "record_count": len(canonical_records),
        "records": canonical_records,
        "authority_effect": "NONE",
    }
    dataset_bytes = canonical_json_bytes(dataset_document)
    dataset_sha256 = sha256_bytes(dataset_bytes)
    unique_sources = sorted(source_inputs.values(), key=lambda row: (row["path"], row["sha256"]))
    manifest_document = {
        "schema_version": MANIFEST_SCHEMA,
        "manifest_id": MANIFEST_ID,
        "dataset": {
            "dataset_id": DATASET_ID,
            "schema_version": DATASET_SCHEMA,
            "path": "docs/design_intelligence/dip1/dip1b_brand_evidence_2_0.json",
            "sha256": dataset_sha256,
            "byte_size": len(dataset_bytes),
            "record_count": len(canonical_records),
        },
        "generator": {
            "identifier": GENERATOR_IDENTIFIER, "version": GENERATOR_VERSION,
        },
        "canonicalization": {
            "identifier": CANONICALIZATION_IDENTIFIER,
            "version": CANONICALIZATION_VERSION,
        },
        "configuration": {
            "path": "docs/design_intelligence/dip0c/c3_pilot_manifest.json",
            "sha256": C3_CONFIGURATION_SHA256,
        },
        "frozen_lineage": {
            "originating_dataset_id": ORIGIN_DATASET_ID,
            "frozen_manifest_sha256": FROZEN_MVP_MANIFEST_SHA256,
            "accepted_import_manifest_sha256": ACCEPTED_IMPORT_MANIFEST_SHA256,
            "original_frozen_expected_sha256": ORIGINAL_FROZEN_EXPECTED_SHA256,
            "stale_ignored_output_sha256": STALE_IGNORED_OUTPUT_SHA256,
            "new_dataset_is_distinct_version": True,
            "old_bytes_recovered": False,
        },
        "source_input_count": len(unique_sources),
        "physical_content_identity_count": len({
            row["sha256"] for row in unique_sources
        }),
        "source_inputs": unique_sources,
        "record_bindings": record_bindings,
        "authority_boundary": {
            "technical_evidence_only": True,
            "ownership_or_rights_inferred": False,
            "canonical_or_palette_status_inferred": False,
            "operational_permission_granted": False,
        },
    }
    manifest_bytes = canonical_json_bytes(manifest_document)
    return BrandEvidenceBundle(
        dataset_document=dataset_document,
        dataset_bytes=dataset_bytes,
        dataset_sha256=dataset_sha256,
        manifest_document=manifest_document,
        manifest_bytes=manifest_bytes,
        manifest_sha256=sha256_bytes(manifest_bytes),
    )


def build_default_bundle(preserved_import_records) -> BrandEvidenceBundle:
    c3a_path = Path(DEFAULT_C3A_OUTPUT)
    frozen_path = Path(DEFAULT_FROZEN_MANIFEST)
    configuration_path = Path(DEFAULT_CONFIGURATION)
    return build_brand_evidence_bundle(
        c3a_document=_load_json(c3a_path, "C3a ignored output"),
        frozen_manifest=_load_json(frozen_path, "frozen MVP manifest"),
        frozen_manifest_bytes=frozen_path.read_bytes(),
        configuration_bytes=configuration_path.read_bytes(),
        preserved_import_records=preserved_import_records,
        repository_root=Path(settings.BASE_DIR).parent,
    )


def validate_committed_brand_evidence_bundle(
        dataset_path=DEFAULT_DATASET_PATH, manifest_path=DEFAULT_MANIFEST_PATH):
    dataset_path = Path(dataset_path)
    manifest_path = Path(manifest_path)
    dataset_bytes = dataset_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    try:
        dataset = json.loads(dataset_bytes)
        manifest = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrandEvidenceError("committed brand-evidence bundle is invalid") from exc
    if (dataset.get("schema_version") != DATASET_SCHEMA
            or dataset.get("dataset_id") != DATASET_ID
            or manifest.get("schema_version") != MANIFEST_SCHEMA
            or manifest.get("manifest_id") != MANIFEST_ID
            or manifest.get("dataset", {}).get("sha256") != sha256_bytes(dataset_bytes)
            or manifest.get("dataset", {}).get("byte_size") != len(dataset_bytes)
            or manifest.get("dataset", {}).get("record_count") != 21
            or dataset.get("record_count") != 21
            or canonical_json_bytes(dataset) != dataset_bytes
            or canonical_json_bytes(manifest) != manifest_bytes):
        raise BrandEvidenceError("committed brand-evidence bundle binding is invalid")
    records = dataset.get("records")
    if (not isinstance(records, list) or len(records) != 21
            or records != sorted(records, key=lambda row: row["stable_candidate_key"])):
        raise BrandEvidenceError("committed brand-evidence records are invalid")
    for row in records:
        recorded_hash = row.get("canonical_record_hash")
        body = {key: value for key, value in row.items()
                if key != "canonical_record_hash"}
        if recorded_hash != canonical_hash(body):
            raise BrandEvidenceError("committed canonical record hash is invalid")
    source_inputs = manifest.get("source_inputs")
    bindings = manifest.get("record_bindings")
    if (not isinstance(source_inputs, list)
            or manifest.get("source_input_count") != 21
            or manifest.get("physical_content_identity_count") != 20
            or len(source_inputs) != 21
            or len({row.get("sha256") for row in source_inputs}) != 20
            or not isinstance(bindings, list) or len(bindings) != 21
            or manifest.get("dataset", {}).get("dataset_id") != DATASET_ID
            or manifest.get("dataset", {}).get("schema_version") != DATASET_SCHEMA
            or manifest.get("authority_boundary", {}).get(
                "technical_evidence_only") is not True
            or manifest.get("authority_boundary", {}).get(
                "operational_permission_granted") is not False):
        raise BrandEvidenceError("committed brand-evidence manifest scope is invalid")
    expected_bindings = [{
        "stable_candidate_key": row["stable_candidate_key"],
        "preserved_import_record_hash": row["preserved_import_record_hash"],
        "canonical_record_hash": row["canonical_record_hash"],
        "source_sha256": row["source_input"]["sha256"],
    } for row in records]
    if bindings != expected_bindings:
        raise BrandEvidenceError("committed brand-evidence record bindings are invalid")
    repository_root = Path(settings.BASE_DIR).parent.resolve()
    for source in source_inputs:
        if (not isinstance(source, dict) or source.get("root") != "repository"
                or not isinstance(source.get("sha256"), str)):
            raise BrandEvidenceError("committed source-input binding is invalid")
        relative = normalize_relative_path(source.get("path"))
        path = (repository_root / relative).resolve()
        try:
            path.relative_to(repository_root)
        except ValueError as exc:
            raise BrandEvidenceError("committed source input escapes repository") from exc
        path = _migrated(path, repository_root, relative)
        if not path.is_file() or sha256_file(path) != source["sha256"]:
            raise BrandEvidenceError(f"committed source-input hash mismatch: {relative}")
    return {
        "dataset": dataset,
        "manifest": manifest,
        "dataset_bytes": dataset_bytes,
        "manifest_bytes": manifest_bytes,
        "dataset_sha256": sha256_bytes(dataset_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
    }
