"""Local, offline schema-1.3 quality preview — DIP-1C-5B.

Answers one question before anyone spends a transfer authorization: **would human
descriptive metadata actually change the documents?** It compares two states over the real
corpus:

* **State A** — the corpus as it is today: zero human semantic metadata. By construction the
  1.3 embedding text must equal the 1.2 embedding text for every item.
* **State B** — the same corpus with FIXTURE bundles supplied in memory. Nothing is written:
  the bundles are passed as a map, never recorded as decision events, so no fabricated human
  assertion can enter the operational database or the signed chain.

The preview reports document-level structure only (term counts, distinct-text counts,
duplicate collapse). It computes **no embeddings, contacts no provider and publishes no
generation** — measuring retrieval quality requires a real reviewed corpus and a separately
authorized build.
"""
from __future__ import annotations

from .semantic_corpus import _bulk_maps, _indexable_items
from .semantic_document_v12 import build_semantic_document_v12
from .semantic_document_v13 import (
    DOCUMENT_SCHEMA_V1_3, HUMAN_METADATA_CHANNEL, build_semantic_document_v13,
    published_metadata_bundles,
)

PREVIEW_SCHEMA = "dip1c_semantic_metadata_preview/1.0"


def _stats(documents):
    texts = [document["embedding_text"] for document in documents]
    non_empty = [text for text in texts if text.strip()]
    human_terms = sum(
        len(document["channels"].get(HUMAN_METADATA_CHANNEL, ()))
        for document in documents)
    return {
        "document_count": len(documents),
        "distinct_embedding_texts": len(set(texts)),
        "empty_embedding_texts": len(texts) - len(non_empty),
        "duplicate_documents": len(texts) - len(set(texts)),
        "mean_terms_per_document": (
            round(sum(len(text.split(". ")) for text in non_empty) / len(non_empty), 3)
            if non_empty else 0.0),
        "human_metadata_terms": human_terms,
        "items_with_human_metadata": sum(
            1 for document in documents
            if document["channels"].get(HUMAN_METADATA_CHANNEL)),
    }


def build_preview(*, fixture_bundles=None):
    """Compare state A (as-is) with state B (in-memory fixture bundles). Read-only."""
    items = _indexable_items()
    facts, machine, human = _bulk_maps()
    live_bundles = published_metadata_bundles()

    v12 = [build_semantic_document_v12(
        item, facts_by_item=facts, machine_by_item=machine, human_by_item=human)
        for item in items]
    state_a = [build_semantic_document_v13(
        item, facts_by_item=facts, machine_by_item=machine, human_by_item=human,
        metadata_by_item=live_bundles) for item in items]

    identical = sum(
        1 for left, right in zip(v12, state_a)
        if left["embedding_text"] == right["embedding_text"])
    preview = {
        "preview_schema": PREVIEW_SCHEMA,
        "document_schema_version": DOCUMENT_SCHEMA_V1_3,
        "published_metadata_item_count": len(live_bundles),
        "state_a_matches_schema_1_2": identical == len(items),
        "state_a_identical_text_count": identical,
        "state_a": _stats(state_a),
        "state_b": None,
        "embeddings_computed": 0,
        "external_transfer": "NONE",
    }
    if fixture_bundles:
        merged = dict(live_bundles)
        merged.update(fixture_bundles)
        state_b = [build_semantic_document_v13(
            item, facts_by_item=facts, machine_by_item=machine, human_by_item=human,
            metadata_by_item=merged) for item in items]
        preview["state_b"] = _stats(state_b)
        preview["state_b_fixture_item_count"] = len(fixture_bundles)
        preview["distinct_text_delta"] = (
            preview["state_b"]["distinct_embedding_texts"]
            - preview["state_a"]["distinct_embedding_texts"])
    return preview
