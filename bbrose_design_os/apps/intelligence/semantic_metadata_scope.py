"""Bounded human semantic-metadata review scope — DIP-1C-5B
(`dip1c_semantic_metadata_review_scope/1.0`).

A deterministic, hash-stable subset of the existing curated corpus for the first human
descriptive-metadata pilot. It selects CANONICAL CorpusItem identities only — it creates no
CorpusItem and no ReviewCandidate, and excludes test-only and deprecated identities. The
selection is a pure function of the corpus, so the scope hash is reproducible.

Target: 20 historical designs · 20 design assets (10 C2 + 10 curated) · 10 fonts ·
5 brand/palette candidates = 55, chosen to cover the benchmark query categories and the
item types whose semantic documents are currently sparse.
"""
from __future__ import annotations

import hashlib
import json

from .dataset_identifiers import (
    DIP0C2_ASSET_CANDIDATE_DATASET, DIP1B_CURATED_ASSET_EXPANSION_DATASET,
)
from .models import (
    BrandCandidateProfile, CorpusItem, DesignAssetProfile, EvidenceReference,
    FontFaceProfile, HistoricalDesignProfile,
)

SCOPE_SCHEMA = "dip1c_semantic_metadata_review_scope/1.0"

TARGET = {
    "historical": 20,
    "c2_assets": 10,
    "curated_assets": 10,
    "fonts": 10,
    "brand_palette": 5,
}
TARGET_TOTAL = sum(TARGET.values())


def _test_only_ids():
    ids = set(DesignAssetProfile.objects.filter(
        is_test_only=True).values_list("corpus_item_id", flat=True))
    ids |= set(EvidenceReference.objects.filter(
        is_test_only=True).values_list("corpus_item_id", flat=True))
    return ids


def _active(qs):
    return qs.filter(
        corpus_item__lifecycle_state=CorpusItem.Lifecycle.ACTIVE).exclude(
        corpus_item__external_key="")


def _pick(profile_qs, key_field, n, exclude_ids):
    """Deterministic pick: order by external_key, take the first n eligible."""
    rows = _active(profile_qs).select_related("corpus_item").order_by(
        "corpus_item__external_key")
    out = []
    for row in rows:
        item = row.corpus_item
        if item.pk in exclude_ids:
            continue
        out.append(item)
        if len(out) >= n:
            break
    return out


def select_scope_items():
    """The canonical items in the scope, grouped by segment. Deterministic."""
    exclude = _test_only_ids()
    historical = _pick(HistoricalDesignProfile.objects, "corpus_item__external_key",
                       TARGET["historical"], exclude)
    c2 = _pick(DesignAssetProfile.objects.filter(
        dataset_identifier=DIP0C2_ASSET_CANDIDATE_DATASET),
        "corpus_item__external_key", TARGET["c2_assets"], exclude)
    curated = _pick(DesignAssetProfile.objects.filter(
        dataset_identifier=DIP1B_CURATED_ASSET_EXPANSION_DATASET),
        "corpus_item__external_key", TARGET["curated_assets"], exclude)
    fonts = _pick(FontFaceProfile.objects, "corpus_item__external_key",
                  TARGET["fonts"], exclude)
    brand = _pick(BrandCandidateProfile.objects, "corpus_item__external_key",
                  TARGET["brand_palette"], exclude)
    return {"historical": historical, "c2_assets": c2, "curated_assets": curated,
            "fonts": fonts, "brand_palette": brand}


def build_scope_document():
    """Deterministic scope document (no timestamp), hash-stable."""
    segments = select_scope_items()
    entries = []
    for segment, items in segments.items():
        for item in items:
            entries.append({
                "corpus_item_id": str(item.pk),
                "external_key": item.external_key,
                "item_kind": item.item_kind,
                "segment": segment,
            })
    entries.sort(key=lambda e: e["corpus_item_id"])
    return {
        "schema_version": SCOPE_SCHEMA,
        "target": dict(TARGET),
        "target_total": TARGET_TOTAL,
        "segment_counts": {s: len(items) for s, items in segments.items()},
        "actual_total": len(entries),
        "entries": entries,
    }


def _canonical_bytes(document) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def scope_hash(document=None) -> str:
    return hashlib.sha256(
        _canonical_bytes(document or build_scope_document())).hexdigest()


def scope_item_ids():
    return {e["corpus_item_id"] for e in build_scope_document()["entries"]}


def is_in_scope(corpus_item) -> bool:
    return str(corpus_item.pk) in scope_item_ids()
