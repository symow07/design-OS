"""Validation and bounded loading for the versioned DIP-1B MVP manifest."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

from .dataset_identifiers import DIP0C2_ASSET_CANDIDATE_DATASET
from .identity import semantic_candidate_fingerprint
from .locator_schemas import normalize_locator, normalize_relative_path

MANIFEST_SCHEMA = "dip1b_mvp_manifest/1.0"
MANIFEST_ID = "dip1b_mvp_manifest/1.0"
IMPORTER_IDENTIFIER = "bbrose.intelligence.import_dip0_mvp"
IMPORTER_VERSION = "1.0"
RECORD_TYPES = frozenset({
    "HISTORICAL_DESIGN", "SOURCE_AUDIT_EVIDENCE", "ASSET_SOURCE",
    "FONT_CANDIDATE", "BRAND_CANDIDATE", "PALETTE_CANDIDATE",
})
DATASET_C1 = "dip0c1_reusable_source_audit/1.0"
DATASET_C2 = DIP0C2_ASSET_CANDIDATE_DATASET
SOURCE_TYPES = frozenset({"FILE", "JSON", "JSONL", "ARCHIVE", "FONT", "OTHER"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST_BYTES = 2_000_000
MAX_ENTRIES = 256
OFFICIAL_EXPECTED_COUNTS = {
    "historical_designs": 14,
    "design_units": 173,
    "c1_overlap_audit_records": 10,
    "c2_manifest_entries": 20,
    "c2_unique_sources": 19,
    "c2_content_identities": 18,
    "asset_candidates": 48,
    "semantic_asset_candidates": 47,
    "font_candidates": 34,
    "brand_candidates": 21,
    "palette_candidates": 1,
}
_FORBIDDEN_PATH_MARKERS = (
    "examples_test_only", "test_ledger", "synthetic_approval", "/tests/",
)


class ManifestError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class PreparedEntry:
    declaration: dict
    source_path: Path
    data_path: Path | None
    data: object | None


@dataclasses.dataclass(frozen=True)
class PreparedManifest:
    path: Path
    document: dict
    manifest_hash: str
    entries: tuple[PreparedEntry, ...]
    domain_records: dict
    actual_counts: dict


def canonical_hash(value) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _exact_keys(value, allowed, required, label):
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown or missing:
        raise ManifestError(
            f"{label} keys invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")


def _bounded_string(value, label, maximum=512):
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ManifestError(f"{label} must be a non-empty string <= {maximum} chars")
    return value


def _configured_root(root_name):
    roots = getattr(settings, "INTELLIGENCE_SOURCE_ROOTS", {})
    if root_name not in roots:
        raise ManifestError(f"source root {root_name!r} is not configured")
    root = Path(roots[root_name]).resolve()
    return root


def resolve_source(reference, *, label):
    _exact_keys(reference, {"root", "path", "sha256", "source_type", "media_type"},
                {"root", "path", "sha256", "source_type"}, label)
    root_name = _bounded_string(reference["root"], f"{label}.root", 64)
    try:
        relative = normalize_relative_path(reference["path"])
    except ValidationError as exc:
        raise ManifestError(f"{label}.path is invalid") from exc
    lowered = f"/{relative.lower()}/"
    if any(marker in lowered for marker in _FORBIDDEN_PATH_MARKERS):
        raise ManifestError(f"{label}.path is test-only or synthetic")
    expected_hash = reference["sha256"]
    if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
        raise ManifestError(f"{label}.sha256 must be lowercase SHA-256")
    if reference["source_type"] not in SOURCE_TYPES:
        raise ManifestError(f"{label}.source_type is unknown")
    if "media_type" in reference:
        _bounded_string(reference["media_type"], f"{label}.media_type", 127)

    root = _configured_root(root_name)
    allowed = getattr(settings, "INTELLIGENCE_ALLOWED_SOURCE_PREFIXES", {}).get(root_name)
    if allowed:
        allowed_paths = tuple(normalize_relative_path(p) for p in allowed)
        if not any(relative == p or relative.startswith(f"{p}/") for p in allowed_paths):
            raise ManifestError(f"{label}.path is outside allowed source prefixes")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ManifestError(f"{label}.path escapes its configured root") from exc
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        path = resolve_material_file(path, repo_root=root)   # mapping only: observed_hash below is the check
    except MaterialPathError as exc:
        raise ManifestError(f'{label}.path migration invalid') from exc
    if not path.is_file():
        raise ManifestError(f"{label}.path is unavailable")
    observed_hash = file_sha256(path)
    if observed_hash != expected_hash:
        raise ManifestError(
            f"{label}.sha256 does not match source bytes "
            f"(expected={expected_hash}, observed={observed_hash})")
    return path


def _load_data(reference, index):
    _exact_keys(reference, {"source", "locator"}, {"source", "locator"},
                f"entries[{index}].data_source")
    path = resolve_source(reference["source"], label=f"entries[{index}].data_source.source")
    locator = reference["locator"]
    _exact_keys(locator, {"schema_version", "value"}, {"schema_version", "value"},
                f"entries[{index}].data_source.locator")
    try:
        normalized = normalize_locator(locator["schema_version"], locator["value"])
    except ValidationError as exc:
        raise ManifestError(f"entries[{index}].data_source.locator is invalid") from exc
    if locator["schema_version"] != "json_path/1.0":
        raise ManifestError("MVP data sources must use json_path/1.0")
    if normalized["path"] != reference["source"]["path"]:
        raise ManifestError("data locator path must identify its declared data source")
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    for segment in normalized["segments"]:
        try:
            value = value[segment]
        except (KeyError, IndexError, TypeError) as exc:
            raise ManifestError(f"entries[{index}] data locator does not resolve") from exc
    return path, value


def _validate_entry(entry, index):
    _exact_keys(
        entry,
        {"stable_source_key", "dataset_id", "record_type", "source", "source_schema_version",
         "parser_identifier", "parser_version", "display_label", "test_only_state",
         "data_source", "metadata"},
        {"stable_source_key", "dataset_id", "record_type", "source", "source_schema_version",
         "parser_identifier", "parser_version", "display_label", "test_only_state",
         "metadata"},
        f"entries[{index}]",
    )
    _bounded_string(entry["stable_source_key"], f"entries[{index}].stable_source_key")
    _bounded_string(entry["dataset_id"], f"entries[{index}].dataset_id", 127)
    if entry["record_type"] not in RECORD_TYPES:
        raise ManifestError(f"entries[{index}].record_type is unknown")
    for key, maximum in (("source_schema_version", 64), ("parser_identifier", 127),
                         ("parser_version", 64), ("display_label", 255)):
        _bounded_string(entry[key], f"entries[{index}].{key}", maximum)
    if entry["test_only_state"] != "NON_TEST_SOURCE":
        raise ManifestError(f"entries[{index}] is test-only and must not be imported")
    if not isinstance(entry["metadata"], dict):
        raise ManifestError(f"entries[{index}].metadata must be an object")
    if len(json.dumps(entry["metadata"], ensure_ascii=False)) > 8192:
        raise ManifestError(f"entries[{index}].metadata is too large")


def _prepare_domain_records(entries):
    historical = []
    assets = {}
    semantic_assets = {}
    fonts = []
    brands = []
    palettes = []
    for prepared in entries:
        entry = prepared.declaration
        record_type = entry["record_type"]
        source = entry["source"]
        if record_type == "HISTORICAL_DESIGN":
            if not isinstance(prepared.data, list):
                raise ManifestError("historical data locator must resolve to a row list")
            rows = [row for row in prepared.data
                    if isinstance(row, dict) and row.get("file") == source["path"]]
            if not rows:
                raise ManifestError(f"historical source {entry['stable_source_key']} has no units")
            historical.append((prepared, rows))
        elif record_type == "SOURCE_AUDIT_EVIDENCE":
            audit = prepared.data
            if (not isinstance(audit, dict)
                    or audit.get("relative_path") != source["path"]):
                raise ManifestError("C1 source-audit identity disagrees with manifest")
            if entry["dataset_id"] != DATASET_C1:
                raise ManifestError("source-audit evidence must retain the C1 dataset id")
        elif record_type == "ASSET_SOURCE":
            if entry["dataset_id"] != DATASET_C2:
                raise ManifestError("asset candidates must retain the C2 dataset id")
            if prepared.data is None:
                continue
            if not isinstance(prepared.data, list):
                raise ManifestError("asset data locator must resolve to a candidate list")
            for candidate_index, candidate in enumerate(prepared.data):
                if not isinstance(candidate, dict) or not candidate.get("candidate_id"):
                    raise ManifestError("asset candidate is missing its stable candidate_id")
                raw_source = candidate.get("source_file", {})
                if (raw_source.get("relative_path") != source["path"]
                        or raw_source.get("sha256") != source["sha256"]):
                    raise ManifestError("asset candidate source identity disagrees with manifest")
                candidate_key = str(candidate["candidate_id"])
                key = f"{source['path']}:{candidate_key}"
                content_hash = canonical_hash(candidate)
                prior = assets.get(key)
                if prior and prior[2] != content_hash:
                    raise ManifestError(
                        f"candidate key {candidate_key!r} conflicts within one source")
                assets[key] = (prepared, candidate, content_hash, candidate_index)
                semantic_fingerprint = semantic_candidate_fingerprint(candidate)
                prior_semantic = semantic_assets.get(candidate_key)
                if prior_semantic and prior_semantic != semantic_fingerprint:
                    raise ManifestError(
                        f"frozen candidate key {candidate_key!r} has ambiguous boundaries")
                semantic_assets[candidate_key] = semantic_fingerprint
        elif record_type == "FONT_CANDIDATE":
            face = prepared.data
            machine = face.get("machine") if isinstance(face, dict) else None
            if (not isinstance(machine, dict)
                    or machine.get("source_path") != source["path"]
                    or machine.get("file_sha256") != source["sha256"]):
                raise ManifestError("font face source identity disagrees with manifest")
            fonts.append((prepared, face))
        elif record_type == "BRAND_CANDIDATE":
            candidate = prepared.data
            if not isinstance(candidate, dict) or candidate.get("relative_path") != source["path"]:
                raise ManifestError("brand candidate source identity disagrees with manifest")
            brands.append((prepared, candidate))
        elif record_type == "PALETTE_CANDIDATE":
            palette = prepared.data
            raw_source = palette.get("source") if isinstance(palette, dict) else None
            if (not isinstance(raw_source, dict) or raw_source.get("path") != source["path"]
                    or raw_source.get("sha256") != source["sha256"]):
                raise ManifestError("palette source identity disagrees with manifest")
            palettes.append((prepared, palette))
    return {
        "historical": historical,
        "assets": list(assets.values()),
        "semantic_asset_keys": frozenset(semantic_assets),
        "fonts": fonts,
        "brands": brands,
        "palettes": palettes,
    }


def prepare_manifest(path) -> PreparedManifest:
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ManifestError("manifest is missing or exceeds the bounded size")
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError("manifest is not valid UTF-8 JSON") from exc
    _exact_keys(document, {"schema_version", "manifest_id", "importer", "datasets",
                           "expected_counts", "entries", "notes"},
                {"schema_version", "manifest_id", "importer", "datasets",
                 "expected_counts", "entries"},
                "manifest")
    if document["schema_version"] != MANIFEST_SCHEMA:
        raise ManifestError(f"unknown manifest schema {document['schema_version']!r}")
    _bounded_string(document["manifest_id"], "manifest_id", 127)
    is_official_manifest = document["manifest_id"] == MANIFEST_ID
    if (not is_official_manifest
            and not getattr(settings, "INTELLIGENCE_ALLOW_TEST_MANIFESTS", False)):
        raise ManifestError(f"unknown manifest {document['manifest_id']!r}")
    _exact_keys(document["importer"], {"identifier", "version"},
                {"identifier", "version"}, "importer")
    if document["importer"] != {"identifier": IMPORTER_IDENTIFIER,
                                "version": IMPORTER_VERSION}:
        raise ManifestError("manifest importer identity/version is unsupported")
    if (not isinstance(document["datasets"], dict)
            or document["datasets"].get(DATASET_C1)
            != {"semantic_role": "FROZEN_TECHNICAL_SOURCE_AUDIT"}
            or document["datasets"].get(DATASET_C2)
            != {"semantic_role": "AUTHORITATIVE_ASSET_CANDIDATE_PILOT"}
            or any(not isinstance(dataset_id, str)
                   or not isinstance(value, dict)
                   or set(value) != {"semantic_role"}
                   or not isinstance(value["semantic_role"], str)
                   for dataset_id, value in document["datasets"].items())):
        raise ManifestError("manifest dataset identities or semantic roles are invalid")
    if not isinstance(document["entries"], list) or not 1 <= len(document["entries"]) <= MAX_ENTRIES:
        raise ManifestError(f"entries must contain 1 to {MAX_ENTRIES} records")
    if not isinstance(document["expected_counts"], dict) or any(
            isinstance(v, bool) or not isinstance(v, int) or v < 0
            for v in document["expected_counts"].values()):
        raise ManifestError("expected_counts must contain nonnegative integers")

    prepared = []
    keys = {}
    for index, entry in enumerate(document["entries"]):
        _validate_entry(entry, index)
        if entry["dataset_id"] not in document["datasets"]:
            raise ManifestError(f"entries[{index}] references an undeclared dataset")
        key = entry["stable_source_key"]
        fingerprint = canonical_hash(entry)
        if key in keys:
            qualifier = "conflicting content" if keys[key] != fingerprint else "duplicate entry"
            raise ManifestError(f"stable source key {key!r} has {qualifier}")
        keys[key] = fingerprint
        source_path = resolve_source(entry["source"], label=f"entries[{index}].source")
        data_path = data = None
        if "data_source" in entry:
            data_path, data = _load_data(entry["data_source"], index)
        prepared.append(PreparedEntry(entry, source_path, data_path, data))

    domain = _prepare_domain_records(prepared)
    c2_entries = [e for e in prepared if e.declaration["dataset_id"] == DATASET_C2]
    c2_paths = {e.declaration["source"]["path"] for e in c2_entries}
    c2_hashes = {e.declaration["source"]["sha256"] for e in c2_entries}
    c1_paths = {
        e.declaration["source"]["path"] for e in prepared
        if e.declaration["dataset_id"] == DATASET_C1
    }
    actual = {
        "historical_designs": len(domain["historical"]),
        "design_units": sum(len(rows) for _, rows in domain["historical"]),
        "c1_overlap_audit_records": sum(
            e.declaration["record_type"] == "SOURCE_AUDIT_EVIDENCE" for e in prepared),
        "c2_manifest_entries": len(c2_entries),
        "c2_unique_sources": len(c2_paths),
        "c2_content_identities": len(c2_hashes),
        "asset_candidates": len(domain["assets"]),
        "semantic_asset_candidates": len(domain["semantic_asset_keys"]),
        "font_candidates": len(domain["fonts"]),
        "brand_candidates": len(domain["brands"]),
        "palette_candidates": len(domain["palettes"]),
    }
    if document["expected_counts"] != actual:
        raise ManifestError(
            f"pilot count discrepancy: expected={document['expected_counts']}, actual={actual}")
    if is_official_manifest and actual != OFFICIAL_EXPECTED_COUNTS:
        raise ManifestError(
            f"authoritative MVP counts changed: required={OFFICIAL_EXPECTED_COUNTS}, "
            f"actual={actual}")
    if is_official_manifest and (
            len(c1_paths) != 10 or not c1_paths.issubset(c2_paths)
            or len(c2_paths - c1_paths) != 9):
        raise ManifestError(
            "C1/C2 overlap changed; require 10 shared and 9 C2-only logical sources")
    return PreparedManifest(
        path=path, document=document, manifest_hash=hashlib.sha256(raw).hexdigest(),
        entries=tuple(prepared), domain_records=domain, actual_counts=actual)
