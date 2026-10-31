"""Bounded review expansion for DIP-1B-5A; preserves existing workflow rows."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.conf import settings

from apps.accounts.models import DecisionEvent

from .brand_evidence import DATASET_ID as BRAND_EVIDENCE_DATASET_ID
from .curated_expansion import MANIFEST_ID as EXPANSION_MANIFEST_ID
from .evidence_readiness import EVIDENCE_KIND
from .models import (
    CorpusItem, OperationalPermissionProjection, ReviewCandidate,
)

MANIFEST_ID = "dip1b_curated_review_manifest/1.0"
MANIFEST_SCHEMA = MANIFEST_ID
DEFAULT_MANIFEST_PATH = (
    Path(settings.BASE_DIR).parent
    / "docs/design_intelligence/dip1/dip1b_curated_review_manifest_1_0.json")
ASSET_DATASET_ID = "dip1b_curated_asset_expansion/1.0"


class CuratedReviewError(ValueError):
    pass


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def build_curated_review_manifest():
    entries = []
    for index in range(6):
        entries.append({
            "external_key": f"historical:dip1b-exp-historical:{index:02d}",
            "item_kind": "HISTORICAL_DESIGN", "review_type": "HISTORICAL_MEMORY",
            "priority": 72,
            "selection_reason": "ALL_ADDED_HISTORICAL_REFERENCE_MEMORY",
            "required_manifest_membership": EXPANSION_MANIFEST_ID,
        })
    for index in range(24):
        entries.append({
            "external_key": (
                f"asset:{ASSET_DATASET_ID}:dip1b-exp-asset:{index:03d}"),
            "item_kind": "DESIGN_ASSET", "review_type": "DESIGN_ASSET",
            "priority": 65,
            "selection_reason": "STRONG_CURATED_VECTOR_CANDIDATE",
            "required_manifest_membership": EXPANSION_MANIFEST_ID,
        })
    for index in range(21):
        entries.append({
            "external_key": f"brand:dip0c3-brand:{index:02d}",
            "item_kind": "BRAND_ASSET", "review_type": "BRAND_IDENTITY",
            "priority": 85,
            "selection_reason": "DETERMINISTIC_TECHNICAL_EVIDENCE_MATERIALLY_IMPROVED",
            "required_manifest_membership": "dip1b_brand_evidence_manifest/2.0",
        })
    document = {
        "schema_version": MANIFEST_SCHEMA, "manifest_id": MANIFEST_ID,
        "expected_counts": {
            "total": 51, "historical_memory": 6,
            "design_assets": 24, "brand_identity": 21,
        },
        "selection_scope": {
            "all_added_historical": True,
            "strongest_added_assets": 24,
            "only_materially_improved_brand_candidates": True,
            "fonts_added": 0, "workflow_reset_authorized": False,
            "authority_effect": "NONE",
        },
        "entries": entries,
    }
    raw = canonical_bytes(document)
    return document, raw, hashlib.sha256(raw).hexdigest()


def validate_curated_review_manifest(path=DEFAULT_MANIFEST_PATH):
    expected, expected_raw, expected_hash = build_curated_review_manifest()
    try:
        raw = Path(path).read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CuratedReviewError("curated review manifest is unavailable") from exc
    if raw != expected_raw or document != expected:
        raise CuratedReviewError("curated review manifest is not deterministic")
    if len({row["external_key"] for row in document["entries"]}) != 51:
        raise CuratedReviewError("curated review manifest identities are not unique")
    return document, expected_hash


def _authority_counts():
    return {
        "decision_events": DecisionEvent.objects.count(),
        "allowed_permissions": OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
    }


def _prepare_entries(document):
    prepared = []
    for entry in document["entries"]:
        items = list(CorpusItem.objects.filter(
            external_key=entry["external_key"]).order_by("id")[:2])
        if len(items) != 1 or items[0].item_kind != entry["item_kind"]:
            raise CuratedReviewError(
                f"review item is unavailable or mismatched: {entry['external_key']}")
        item = items[0]
        if not item.evidence_references.filter(is_test_only=False).exists():
            raise CuratedReviewError("review item has no non-test evidence")
        membership = entry["required_manifest_membership"]
        if not item.import_records.filter(
                reconciliation_details__manifest_id=membership).exists():
            raise CuratedReviewError(
                f"required manifest membership is absent: {entry['external_key']}")
        if (membership == "dip1b_brand_evidence_manifest/2.0"
                and not item.evidence_references.filter(
                    evidence_kind=EVIDENCE_KIND,
                    source_artifact__source_schema_version=BRAND_EVIDENCE_DATASET_ID,
                    is_test_only=False).exists()):
            raise CuratedReviewError("brand evidence did not materially improve")
        prepared.append((entry, item))
    return prepared


def import_curated_review_candidates(*, apply=False):
    document, manifest_hash = validate_curated_review_manifest()
    prepared = _prepare_entries(document)
    before = _authority_counts()
    created = 0
    unchanged = 0
    would_create = 0
    for entry, item in prepared:
        existing = ReviewCandidate.objects.filter(
            corpus_item=item, review_type=entry["review_type"]).order_by(
                "created_at", "id").first()
        if existing:
            unchanged += 1
            continue
        would_create += 1
        if apply:
            latest_batch = item.import_records.order_by("-created_at").values_list(
                "import_batch_id", flat=True).first()
            ReviewCandidate.objects.create(
                corpus_item=item, review_type=entry["review_type"],
                workflow_status=ReviewCandidate.Status.OPEN,
                priority=entry["priority"], source_import_batch_id=latest_batch,
                review_manifest_id=MANIFEST_ID,
                machine_confidence_summary={
                    "schema": "machine_confidence_summary/1.0",
                    "selection_reason": entry["selection_reason"],
                    "classification_count": item.machine_classifications.count(),
                    "manifest_id": MANIFEST_ID,
                },
            )
            created += 1
    after = _authority_counts()
    if after != before:
        raise CuratedReviewError("review import changed an authority table")
    return {
        "mode": "apply" if apply else "dry-run", "manifest_id": MANIFEST_ID,
        "manifest_hash": manifest_hash, "manifest_entries": 51,
        "historical_memory": 6, "design_assets": 24, "brand_identity": 21,
        "would_create": would_create, "created": created, "unchanged": unchanged,
        "decision_events_created": 0, "allowed_permissions_created": 0,
    }
