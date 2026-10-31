"""Strict, bounded DIP-1B-3 review-task manifest loader."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from .identity import IDENTITY_ALIAS_PROVENANCE
from .locator_schemas import normalize_relative_path
from .models import CorpusItem, ProvenanceRecord, ReviewCandidate

MANIFEST_SCHEMA = "dip1b_review_manifest/1.0"
MANIFEST_ID = "dip1b_review_manifest/1.0"
DEFAULT_MANIFEST = (
    Path(settings.BASE_DIR).parent
    / "docs/design_intelligence/dip1/dip1b_review_manifest_1_0.json"
)
MAX_BYTES = 256_000
MAX_ENTRIES = 64
EXPECTED_ITEM_KINDS = {
    ReviewCandidate.ReviewType.HISTORICAL_MEMORY: CorpusItem.Kind.HISTORICAL_DESIGN,
    ReviewCandidate.ReviewType.DESIGN_ASSET: CorpusItem.Kind.DESIGN_ASSET,
    ReviewCandidate.ReviewType.FONT_TECHNICAL: CorpusItem.Kind.FONT,
    ReviewCandidate.ReviewType.BRAND_IDENTITY: CorpusItem.Kind.BRAND_ASSET,
    ReviewCandidate.ReviewType.PALETTE_OBSERVATION: CorpusItem.Kind.BRAND_PALETTE,
}
FORBIDDEN_SOURCE_MARKERS = (
    "examples_test_only", "test_ledger", "synthetic_approval", "/tests/",
)


class ReviewManifestError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class PreparedReviewManifest:
    path: Path
    manifest_hash: str
    entries: tuple[dict, ...]
    counts: dict[str, int]


def _exact_keys(value, allowed, required, label):
    if not isinstance(value, dict):
        raise ReviewManifestError(f"{label} must be an object")
    missing = set(required) - set(value)
    unknown = set(value) - set(allowed)
    if missing or unknown:
        raise ReviewManifestError(
            f"{label} keys invalid; missing={sorted(missing)}, unknown={sorted(unknown)}")


def _canonical_hash(value):
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _assert_bounded_source(artifact, label):
    try:
        root_name, relative_raw = artifact.source_identifier.split(":", 1)
    except ValueError as exc:
        raise ReviewManifestError(f"{label} source identity has no configured root") from exc
    roots = getattr(settings, "INTELLIGENCE_SOURCE_ROOTS", {})
    if root_name not in roots:
        raise ReviewManifestError(f"{label} source root is not configured")
    try:
        relative = normalize_relative_path(relative_raw)
    except ValidationError as exc:
        raise ReviewManifestError(f"{label} source path is invalid") from exc
    prefixes = tuple(
        normalize_relative_path(prefix)
        for prefix in getattr(settings, "INTELLIGENCE_ALLOWED_SOURCE_PREFIXES", {}).get(
            root_name, ()))
    if not prefixes or not any(
            relative == prefix or relative.startswith(f"{prefix}/")
            for prefix in prefixes):
        raise ReviewManifestError(f"{label} source path is outside allowed prefixes")
    root = Path(roots[root_name]).resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ReviewManifestError(f"{label} source path escapes its configured root") from exc
    lowered = f"/{relative.lower()}/"
    if any(marker in lowered for marker in FORBIDDEN_SOURCE_MARKERS):
        raise ReviewManifestError(f"{label} resolves to a test-only source")


def prepare_review_manifest(path=DEFAULT_MANIFEST):
    path = Path(path).resolve()
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ReviewManifestError("review manifest is missing or exceeds the size bound")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewManifestError("review manifest is not valid JSON") from exc
    _exact_keys(
        document, {"schema", "manifest_id", "expected_counts", "entries"},
        {"schema", "manifest_id", "expected_counts", "entries"}, "manifest")
    if document["schema"] != MANIFEST_SCHEMA or document["manifest_id"] != MANIFEST_ID:
        raise ReviewManifestError("review manifest schema/id is not supported")
    entries = document["entries"]
    if not isinstance(entries, list) or not entries or len(entries) > MAX_ENTRIES:
        raise ReviewManifestError("review manifest entries are empty or exceed the bound")
    expected = document["expected_counts"]
    _exact_keys(expected, {"total", "by_review_type"}, {"total", "by_review_type"},
                "expected_counts")
    if set(expected["by_review_type"]) != set(EXPECTED_ITEM_KINDS):
        raise ReviewManifestError("expected review-type vocabulary is not exact")

    seen_ids = set()
    seen_keys = set()
    counts = {key: 0 for key in EXPECTED_ITEM_KINDS}
    prepared = []
    for index, entry in enumerate(entries):
        label = f"entries[{index}]"
        _exact_keys(entry, {
            "corpus_item_uuid", "external_key", "item_kind", "review_type",
            "priority", "due_at", "selection_reason",
        }, {
            "corpus_item_uuid", "external_key", "item_kind", "review_type",
            "priority", "due_at", "selection_reason",
        }, label)
        try:
            item_id = uuid.UUID(entry["corpus_item_uuid"])
        except (TypeError, ValueError, AttributeError) as exc:
            raise ReviewManifestError(f"{label}.corpus_item_uuid is invalid") from exc
        if str(item_id) != entry["corpus_item_uuid"]:
            raise ReviewManifestError(f"{label}.corpus_item_uuid is not canonical")
        if item_id in seen_ids or entry["external_key"] in seen_keys:
            raise ReviewManifestError("review manifest contains a duplicate item/key")
        seen_ids.add(item_id)
        seen_keys.add(entry["external_key"])
        review_type = entry["review_type"]
        if review_type not in EXPECTED_ITEM_KINDS:
            raise ReviewManifestError(f"{label}.review_type is unknown")
        if entry["item_kind"] != EXPECTED_ITEM_KINDS[review_type]:
            raise ReviewManifestError(f"{label} review type does not match item kind")
        if (type(entry["priority"]) is not int
                or not 1 <= entry["priority"] <= 100):
            raise ReviewManifestError(f"{label}.priority must be 1..100")
        if entry["due_at"] is not None:
            raise ReviewManifestError("version 1.0 does not accept manifest-derived due dates")
        if (not isinstance(entry["external_key"], str)
                or not entry["external_key"] or len(entry["external_key"]) > 255
                or not isinstance(entry["selection_reason"], str)
                or not entry["selection_reason"]
                or len(entry["selection_reason"]) > 255):
            raise ReviewManifestError(f"{label} contains an invalid bounded string")

        if ProvenanceRecord.objects.filter(
            provenance_type=IDENTITY_ALIAS_PROVENANCE,
            normalized_machine_interpretation__legacy_corpus_item_id=str(item_id),
        ).exists():
            raise ReviewManifestError(f"{label} names a deprecated corpus UUID")
        item = CorpusItem.objects.filter(pk=item_id).first()
        if item is None:
            raise ReviewManifestError(f"{label} names an item outside the corpus")
        if (item.external_key != entry["external_key"]
                or item.item_kind != entry["item_kind"]):
            raise ReviewManifestError(f"{label} item identity disagrees with the corpus")
        evidence = list(item.evidence_references.select_related("source_artifact"))
        if not evidence:
            raise ReviewManifestError(f"{label} has no source evidence")
        if any(reference.is_test_only for reference in evidence):
            raise ReviewManifestError(f"{label} has test-only evidence")
        profile = getattr(item, "design_asset_profile", None)
        if profile is not None and profile.is_test_only:
            raise ReviewManifestError(f"{label} names a test-only corpus profile")
        for reference in evidence:
            _assert_bounded_source(reference.source_artifact, label)
        counts[review_type] += 1
        prepared.append({**entry, "corpus_item": item})

    if expected["total"] != len(prepared) or expected["by_review_type"] != counts:
        raise ReviewManifestError(
            f"exact-count reconciliation failed: expected={expected}, "
            f"actual={{'total': {len(prepared)}, 'by_review_type': {counts}}}")
    return PreparedReviewManifest(
        path=path, manifest_hash=_canonical_hash(document), entries=tuple(prepared),
        counts=counts)


def _machine_summary(item, reason):
    rows = list(item.machine_classifications.order_by("classification_type", "pk"))
    confidences = [float(row.confidence) for row in rows]
    return {
        "schema": "machine_confidence_summary/1.0",
        "classification_count": len(rows),
        "classification_types": sorted({row.classification_type for row in rows}),
        "confidence_min": min(confidences) if confidences else None,
        "confidence_max": max(confidences) if confidences else None,
        "selection_reason": reason,
    }


@transaction.atomic
def import_review_candidates(path=DEFAULT_MANIFEST, *, apply=False):
    prepared = prepare_review_manifest(path)
    proposed = []
    created = 0
    unchanged = 0
    for entry in prepared.entries:
        item = entry["corpus_item"]
        summary = _machine_summary(item, entry["selection_reason"])
        latest_batch_id = (item.import_records.order_by("-created_at")
                           .values_list("import_batch_id", flat=True).first())
        values = {
            "corpus_item": item,
            "review_type": entry["review_type"],
            "workflow_status": ReviewCandidate.Status.OPEN,
            "priority": entry["priority"],
            "assigned_to": None,
            "assigned_at": None,
            "due_at": None,
            "source_import_batch_id": latest_batch_id,
            "review_manifest_id": MANIFEST_ID,
            "machine_confidence_summary": summary,
        }
        existing = ReviewCandidate.objects.filter(
            corpus_item=item, review_type=entry["review_type"],
            review_manifest_id=MANIFEST_ID).first()
        if existing is None:
            proposed.append(values)
            if apply:
                ReviewCandidate.objects.create(**values)
                created += 1
        else:
            immutable = {
                "priority": existing.priority,
                "source_import_batch_id": existing.source_import_batch_id,
                "machine_confidence_summary": existing.machine_confidence_summary,
            }
            expected_immutable = {key: values[key] for key in immutable}
            if immutable != expected_immutable:
                raise ReviewManifestError(
                    f"existing review candidate {existing.pk} disagrees with manifest")
            unchanged += 1
    if not apply:
        transaction.set_rollback(True)
    return {
        "mode": "apply" if apply else "dry-run",
        "manifest_id": MANIFEST_ID,
        "manifest_hash": prepared.manifest_hash,
        "manifest_entries": len(prepared.entries),
        "counts_by_review_type": prepared.counts,
        "would_create": len(proposed),
        "created": created,
        "unchanged": unchanged,
        "decision_events_created": 0,
        "operational_permissions_created": 0,
    }
