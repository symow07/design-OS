"""Versioned semantic-document builder registry — DIP-1C-4A-CORR-1.

The executable index-build pipeline used to reach schema 1.1 by an *accidental import*
(`semantic_index` imported `semantic_document`), so a "schema-1.2 build" silently produced
schema 1.1. This module is the single dispatch boundary: the pipeline now selects a
**declared** document schema, each supported version resolves to its ONE canonical frozen
builder, and an unknown version fails closed.

There is exactly one builder per schema — 1.2 delegates to the committed
`semantic_corpus.CorpusSnapshot` / `build_semantic_document_v12` verbatim (reusing its single
bulk batch, so the bounded-query win is preserved), and 1.1 delegates to the frozen
`semantic_index` document functions. Neither is reimplemented here.

Three aggregate hashes are exposed, with one meaning each (never one label for two meanings):

* **corpus_hash** — the staleness/authorization value. Its formula is schema-specific and
  matches exactly what is already stored, so historical generations never go false-stale:
  1.1 = Σ over sorted(id, document_content_hash); 1.2 = CorpusSnapshot.manifest_hash()
  (= schema ‖ Σ over sorted(id, embedding_text_hash)).
* **embedding_text_manifest_hash** — Σ over sorted(id, embedding_text_hash). For schema 1.2
  this **coincides with corpus_hash by construction** (both key on the embedding-text
  hashes); reported as the same value, not a second invented label.
* **document_content_manifest_hash** — Σ over sorted(id, full-document-content-hash). The
  genuinely distinct aggregate: it covers the whole document (metadata + channels), not only
  the transmitted text.
"""
from __future__ import annotations

import dataclasses
import hashlib

from .semantic_document import (
    DOCUMENT_SCHEMA_V1_0, DOCUMENT_SCHEMA_V1_1,
)
from .semantic_document_v12 import DOCUMENT_SCHEMA_V1_2
from .semantic_document_v13 import DOCUMENT_SCHEMA_V1_3

SUPPORTED_BUILD_SCHEMAS = (DOCUMENT_SCHEMA_V1_1, DOCUMENT_SCHEMA_V1_2)
# 1.0 is frozen for historical inspection only; it is never a build target here.
HISTORICAL_SCHEMAS = (DOCUMENT_SCHEMA_V1_0,)
# DIP-1C-5B defined schema 1.3 (human-enriched documents) but deliberately did NOT register a
# builder: an index build is an external-transfer event, and 1.3 has nothing to add until a
# real human review has recorded bundles. It is previewable offline via
# `semantic_metadata_preview`, and requesting it here fails closed like any unknown schema.
DEFINED_NOT_BUILDABLE_SCHEMAS = (DOCUMENT_SCHEMA_V1_3,)
DEFAULT_BUILD_SCHEMA = DOCUMENT_SCHEMA_V1_1


class SemanticBuilderError(RuntimeError):
    """An unknown or unbuildable document schema. Fails closed."""


@dataclasses.dataclass(frozen=True)
class BuiltDocument:
    corpus_item: object
    document: dict
    embedding_text: str
    document_content_hash: str
    embedding_text_hash: str


class BuiltCorpus:
    """The result of building the whole indexable corpus at one declared schema.

    `corpus_hash` is passed in from the schema's own canonical function so it is byte-for-byte
    what the pipeline already stored for that schema.
    """

    def __init__(self, schema_version, entries, exclusions, corpus_hash):
        self.schema_version = schema_version
        self.entries = entries
        self.exclusions = exclusions
        self._corpus_hash = corpus_hash

    @property
    def document_count(self):
        return len(self.entries)

    @property
    def excluded_count(self):
        return len(self.exclusions)

    def texts(self):
        return [e.embedding_text for e in self.entries]

    def corpus_hash(self) -> str:
        return self._corpus_hash

    def embedding_text_manifest_hash(self) -> str:
        hasher = hashlib.sha256()
        for entry in sorted(self.entries, key=lambda e: str(e.corpus_item.pk)):
            hasher.update(str(entry.corpus_item.pk).encode())
            hasher.update(entry.embedding_text_hash.encode())
        return hasher.hexdigest()

    def document_content_manifest_hash(self) -> str:
        hasher = hashlib.sha256()
        for entry in sorted(self.entries, key=lambda e: str(e.corpus_item.pk)):
            hasher.update(str(entry.corpus_item.pk).encode())
            hasher.update(entry.document_content_hash.encode())
        return hasher.hexdigest()


def _build_v11() -> BuiltCorpus:
    from .semantic_document import document_hash, semantic_text
    from .semantic_index import build_semantic_documents
    docs, corpus_hash, exclusions = build_semantic_documents(with_exclusions=True)
    entries = []
    for item, document in docs:
        text = semantic_text(document)
        entries.append(BuiltDocument(
            corpus_item=item, document=document, embedding_text=text,
            document_content_hash=document_hash(document),
            embedding_text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()))
    return BuiltCorpus(DOCUMENT_SCHEMA_V1_1, entries, exclusions, corpus_hash)


def _build_v12() -> BuiltCorpus:
    from .semantic_corpus import build_corpus_snapshot
    from .semantic_document_v12 import document_hash_v12
    snapshot = build_corpus_snapshot()          # the one canonical 1.2 builder, one batch
    entries = []
    for item, document in snapshot.documents:
        entries.append(BuiltDocument(
            corpus_item=item, document=document,
            embedding_text=document["embedding_text"],
            document_content_hash=document_hash_v12(document),
            embedding_text_hash=document["embedding_text_hash"]))
    # corpus_hash comes from the snapshot's own canonical function, unchanged
    return BuiltCorpus(DOCUMENT_SCHEMA_V1_2, entries, exclusions=[],
                       corpus_hash=snapshot.manifest_hash())


_BUILDERS = {
    DOCUMENT_SCHEMA_V1_1: _build_v11,
    DOCUMENT_SCHEMA_V1_2: _build_v12,
}


def build_semantic_corpus(*, document_schema_version) -> BuiltCorpus:
    """Resolve a declared schema to its canonical builder, or fail closed."""
    builder = _BUILDERS.get(document_schema_version)
    if builder is None:
        raise SemanticBuilderError(
            f"unsupported build document schema {document_schema_version!r}; "
            f"supported: {sorted(SUPPORTED_BUILD_SCHEMAS)}")
    return builder()


def corpus_hash_for_schema(document_schema_version) -> str:
    return build_semantic_corpus(
        document_schema_version=document_schema_version).corpus_hash()


def build_manifest(*, document_schema_version, provider, model_identifier,
                   vector_dimension, index_schema_version) -> dict:
    """A deterministic, non-sensitive manifest for exact preflight comparison.

    Full 64-char hashes; NO embedding texts, paths, filenames, locators, vectors, secrets,
    or provider responses.
    """
    from .review_campaign import build_campaign_scope, campaign_scope_hash
    built = build_semantic_corpus(document_schema_version=document_schema_version)
    scope = build_campaign_scope()
    corpus_hash = built.corpus_hash()
    embedding_manifest = built.embedding_text_manifest_hash()
    config = hashlib.sha256("|".join([
        document_schema_version, provider, model_identifier, str(vector_dimension),
        index_schema_version]).encode()).hexdigest()
    return {
        "manifest_schema": "intelligence_semantic_manifest/1.0",
        "document_schema_version": document_schema_version,
        "index_schema_version": index_schema_version,
        "provider": provider,
        "model_identifier": model_identifier,
        "vector_dimension": vector_dimension,
        "document_count": built.document_count,
        "excluded_count": built.excluded_count,
        "exclusions": built.exclusions,
        # THE authorization/staleness value. Schema-specific formula matching what is
        # stored: 1.2 = sha(schema ‖ Σ(id, embedding_text_hash)); 1.1 = Σ(id, doc_hash).
        "corpus_hash": corpus_hash,
        # the raw aggregate of embedding-text hashes, WITHOUT the schema prefix. For 1.2 it
        # is corpus_hash's input pre-namespacing — a genuinely distinct value, so it is
        # reported separately and the relationship is stated, never conflated.
        "embedding_text_manifest_hash": embedding_manifest,
        "embedding_text_manifest_relationship": (
            "EQUALS_CORPUS_HASH" if embedding_manifest == corpus_hash
            else "CORPUS_HASH_IS_SCHEMA_PREFIXED_OVER_THIS"),
        # the genuinely separate aggregate: whole document (metadata + channels), not text
        "document_content_manifest_hash": built.document_content_manifest_hash(),
        "generation_config_hash": config,
        "document_hashes": {
            str(e.corpus_item.pk): {
                "document_content_hash": e.document_content_hash,
                "embedding_text_hash": e.embedding_text_hash,
            } for e in sorted(built.entries, key=lambda e: str(e.corpus_item.pk))},
        "campaign_hash": campaign_scope_hash(scope),
        "campaign_partition": list(scope["wave_counts"].values()),
    }
