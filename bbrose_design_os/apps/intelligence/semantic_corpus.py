"""Bulk corpus snapshot for semantic documents — DIP-1C-4A.

The DIP-1C-3 pilot measured ~8.7 s per semantic search, of which ~3.6 s was
`index_status()` rebuilding all 176 semantic documents **on every request** — each item
running its own readiness, governance and assertion queries. That is an N+1 defect, not a
provider cost.

This module builds the whole corpus in **one deterministic batch** with bulk-loaded data:
a bounded number of queries regardless of corpus size, reused within a request, and
constructed exactly once.

Staleness is **not weakened**. Schema 1.2 keeps readiness, blockers, permissions and
campaign state out of the embedding text, so the manifest hashes the embedding text plus
the canonical id set. That makes staleness *exact with respect to what is actually
embedded*: membership changes flip the hash via the id set, and embedded-content changes
flip it via the text hash. A readiness transition no longer marks the index stale — and it
should not, because readiness is not embedded. This is a correction of the staleness
contract, not a relaxation of it.
"""
from __future__ import annotations

import hashlib

from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, HumanAssertionProjection,
    MachineClassification, ObservedFact,
)
from .semantic_document_v12 import (
    DOCUMENT_SCHEMA_V1_2, build_semantic_document_v12,
)

CORPUS_SNAPSHOT_SCHEMA = "intelligence_semantic_corpus_snapshot/1.0"


def _indexable_items():
    """Reviewer-discoverable canonical items: active, stable-keyed, not test-only.
    Bulk-loaded — one query per relation, never per item."""
    test_only = set(DesignAssetProfile.objects.filter(
        is_test_only=True).values_list("corpus_item_id", flat=True))
    test_only |= set(EvidenceReference.objects.filter(
        is_test_only=True).values_list("corpus_item_id", flat=True))
    items = []
    for item in CorpusItem.objects.filter(
            lifecycle_state=CorpusItem.Lifecycle.ACTIVE).select_related(
            "historical_design_profile", "design_asset_profile",
            "font_face_profile", "brand_candidate_profile").order_by("id"):
        if item.pk in test_only or not (item.external_key or "").strip():
            continue
        items.append(item)
    return items


def _bulk_maps():
    """All per-item evidence in a bounded number of queries."""
    facts_by_item = {}
    for item_id, fact_type in ObservedFact.objects.values_list(
            "corpus_item_id", "fact_type"):
        facts_by_item.setdefault(str(item_id), set()).add(fact_type)

    machine_by_item = {}
    for item_id, ctype, label in MachineClassification.objects.values_list(
            "corpus_item_id", "classification_type", "label"):
        machine_by_item.setdefault(str(item_id), set()).add((ctype, label))

    # Verified human assertions go through the projection reader (the authority), but ONLY
    # for items that actually have a projection. With none present that is zero reader
    # calls — exact, and bounded by the number of real assertions rather than corpus size.
    human_by_item = {}
    with_projections = set(HumanAssertionProjection.objects.values_list(
        "corpus_item_id", flat=True))
    if with_projections:
        from .projection_reader import read_published_assertions
        for item in CorpusItem.objects.filter(pk__in=with_projections):
            result = read_published_assertions(item)
            labels = {c.get("label", "") for c in
                      (result.current_by_domain or {}).values() if isinstance(c, dict)}
            human_by_item[str(item.pk)] = {label for label in labels if label}
    return facts_by_item, machine_by_item, human_by_item


class CorpusSnapshot:
    """One deterministic build of every indexable semantic document.

    Construct once per request and reuse. Nothing here writes.
    """

    def __init__(self):
        self.items = _indexable_items()
        facts, machine, human = _bulk_maps()
        self.documents = [
            (item, build_semantic_document_v12(
                item, facts_by_item=facts, machine_by_item=machine,
                human_by_item=human))
            for item in self.items
        ]

    @property
    def document_count(self):
        return len(self.documents)

    def manifest_hash(self) -> str:
        """Hash the canonical id set + each document's EMBEDDING TEXT.

        Exact with respect to what is embedded: an added/removed item changes the id set,
        and any change to embedded content changes the text hash. Readiness/blocker/
        permission churn correctly does not, because none of it is embedded.
        """
        hasher = hashlib.sha256()
        hasher.update(DOCUMENT_SCHEMA_V1_2.encode())
        for item, document in sorted(self.documents, key=lambda pair: str(pair[0].pk)):
            hasher.update(str(item.pk).encode())
            hasher.update(document["embedding_text_hash"].encode())
        return hasher.hexdigest()

    def texts(self):
        return [document["embedding_text"] for _, document in self.documents]


def build_corpus_snapshot() -> CorpusSnapshot:
    return CorpusSnapshot()
