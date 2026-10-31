"""Semantic index build + publication lifecycle — DIP-1C-1.

Builds happen in **shadow**: a new `SemanticIndexGeneration` is created, embeddings are
written under it, and only a fully validated build is published atomically into the
singleton `SemanticIndexPublicationState`. A failed or partial build never replaces a
previously published generation, and a **test-encoder generation can never become the
production publication**.

Building writes only these three derived tables. It creates zero DecisionEvents, zero
projections, zero permissions — an embedding is search data, not authority.

Nothing here calls an external provider on its own: it embeds whatever the caller's encoder
produces. The external boundary and the human-consent gate live in the management command.
"""
from __future__ import annotations

import hashlib

from django.db import transaction
from django.utils import timezone

from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, SemanticDocumentEmbedding,
    SemanticIndexGeneration, SemanticIndexPublicationState,
)
from .semantic_document import (
    SemanticDocumentError, build_semantic_document, document_hash,
)
from .semantic_encoder import TEST_ENCODER_PROVIDER
from .semantic_similarity import cosine_similarity

INDEX_SCHEMA = "intelligence_semantic_index/1.0"

# index availability, as the search layer reports it
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_CURRENT = "CURRENT"
STATUS_STALE = "STALE"


class SemanticIndexError(RuntimeError):
    pass


def _indexable_items():
    """Reviewer-discoverable canonical items: active identity, not test-only. Deprecated
    and test-only records are excluded from the index entirely."""
    test_only_ids = set(DesignAssetProfile.objects.filter(
        is_test_only=True).values_list("corpus_item_id", flat=True))
    test_only_ids |= set(EvidenceReference.objects.filter(
        is_test_only=True).values_list("corpus_item_id", flat=True))
    items = []
    for item in CorpusItem.objects.filter(
            lifecycle_state=CorpusItem.Lifecycle.ACTIVE).select_related(
            "historical_design_profile", "design_asset_profile",
            "font_face_profile", "brand_candidate_profile").order_by("id"):
        if item.pk in test_only_ids or not (item.external_key or "").strip():
            continue
        items.append(item)
    return items


def _manifest_hash_for(docs) -> str:
    hasher = hashlib.sha256()
    for item, document in sorted(docs, key=lambda pair: str(pair[0].pk)):
        hasher.update(str(item.pk).encode())
        hasher.update(document_hash(document).encode())
    return hasher.hexdigest()


def corpus_manifest_hash(items=None) -> str:
    """A stable hash of the INDEXED corpus and each item's semantic document. Changes
    whenever indexed content changes — the basis of staleness detection.

    Boundary-excluded items are not hashed: they are not in the index, so they must not
    affect its identity. Like `build_semantic_documents`, this skips rather than crashes.
    """
    items = _indexable_items() if items is None else items
    docs = []
    for item in items:
        try:
            docs.append((item, build_semantic_document(item)))
        except SemanticDocumentError:
            continue
    return _manifest_hash_for(docs)


def build_semantic_documents(*, with_exclusions=False):
    """The bounded documents for the indexable corpus, plus the manifest hash.

    A document that cannot be built inside the value boundary is **excluded with a reason**,
    never crashed over and never sanitized into passing. (DIP-1C-1-CORR-1: six historical
    designs carry a source filename as their only display title — e.g. `LG5505唇彩.ai` — and
    a source filename may not be transmitted. Excluding them costs their semantic
    discoverability, which is the honest price of the boundary; a safe human-reviewed title
    would restore it.)
    """
    items = _indexable_items()
    docs, exclusions = [], []
    for item in items:
        try:
            docs.append((item, build_semantic_document(item)))
        except SemanticDocumentError as exc:
            # record WHERE and WHY, never the prohibited value
            exclusions.append({"corpus_item_id": str(item.pk),
                               "external_key": item.external_key,
                               "item_kind": item.item_kind,
                               "reason_code": getattr(exc, "code", "") or "BOUNDARY_REFUSED",
                               "detail": str(exc)})
    manifest = _manifest_hash_for(docs)
    if with_exclusions:
        return docs, manifest, exclusions
    return docs, manifest


def build_generation(encoder, *, document_schema_version=None, invoked_by="",
                     published=False):
    """Build a shadow generation with the given encoder at a DECLARED document schema.

    The schema is selected explicitly and routed through the versioned builder registry —
    never inferred from an accidental import. `published=True` is honoured ONLY for a real
    (non-test) encoder that passes full validation; a test-encoder build can never publish.
    """
    from .semantic_builders import DEFAULT_BUILD_SCHEMA, build_semantic_corpus
    document_schema_version = document_schema_version or DEFAULT_BUILD_SCHEMA
    built = build_semantic_corpus(document_schema_version=document_schema_version)
    generation = SemanticIndexGeneration.objects.create(
        encoder_identifier=encoder.encoder_identifier,
        encoder_version=encoder.encoder_version,
        provider=encoder.provider,
        model_identifier=encoder.model_identifier,
        document_schema_version=document_schema_version,
        index_schema_version=INDEX_SCHEMA,
        vector_dimension=encoder.dimension,
        corpus_manifest_hash=built.corpus_hash(),
        status=SemanticIndexGeneration.Status.BUILDING,
        is_test_encoder=bool(encoder.is_test_encoder),
        invoked_by=(invoked_by or "")[:150],
        document_count=built.document_count,
    )
    try:
        texts = built.texts()
        vectors = encoder.encode(texts)
        if len(vectors) != len(built.entries):
            raise SemanticIndexError("encoder returned wrong vector count")
        embedded = 0
        for entry, vector in zip(built.entries, vectors):
            if len(vector) != encoder.dimension:
                raise SemanticIndexError(
                    f"vector dimension {len(vector)} != {encoder.dimension}")
            SemanticDocumentEmbedding.objects.create(
                generation=generation, corpus_item=entry.corpus_item,
                # the row binds to the SELECTED schema's document-content hash (which for
                # 1.2 transitively commits the embedding-text hash the v12 doc embeds)
                document_hash=entry.document_content_hash,
                vector_hash=_vector_hash(vector),
                vector_dimension=encoder.dimension,
                vector=[float(x) for x in vector],
                provider=encoder.provider,
                model_identifier=encoder.model_identifier,
                encoder_version=encoder.encoder_version)
            embedded += 1
        generation.embedded_count = embedded
        generation.request_count = len(texts)
        generation.status = SemanticIndexGeneration.Status.BUILT
        generation.completed_at = timezone.now()
        generation.save()
    except Exception as exc:
        generation.status = SemanticIndexGeneration.Status.FAILED
        generation.completed_at = timezone.now()
        # never store a key or a transmitted document in the failure summary
        generation.failure_summary = _safe_summary(exc)
        generation.save()
        raise

    if published:
        publish_generation(generation)
    return generation


def _vector_hash(vector):
    from .semantic_encoder import vector_hash
    return vector_hash(vector)


def _safe_summary(exc) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return text[:500]


def publish_generation(generation):
    """Atomically make `generation` the current production publication.

    Refuses a test-encoder generation, a non-OpenAI provider, an unbuilt generation, or a
    build whose corpus hash no longer matches the live corpus. A failed/partial build never
    replaces a valid published generation.
    """
    if generation.is_test_encoder or generation.provider == TEST_ENCODER_PROVIDER:
        raise SemanticIndexError(
            "a test-encoder generation can never become the production publication")
    if generation.provider != "openai":
        raise SemanticIndexError(
            "only an OpenAI production generation may be published")
    if generation.status != SemanticIndexGeneration.Status.BUILT:
        raise SemanticIndexError("only a fully BUILT generation may be published")
    if generation.embedded_count != generation.document_count:
        raise SemanticIndexError("generation did not embed every document")
    # recompute with the generation's OWN schema — never a hardcoded builder — so a 1.2
    # generation is validated against a 1.2 recompute, not a 1.1 one
    from .semantic_builders import corpus_hash_for_schema
    live_hash = corpus_hash_for_schema(generation.document_schema_version)
    if generation.corpus_manifest_hash != live_hash:
        raise SemanticIndexError(
            "corpus changed since build; refusing to publish a stale generation")

    now = timezone.now()
    with transaction.atomic():
        state, _ = SemanticIndexPublicationState.objects.get_or_create(pk=1)
        previous = state.current_generation
        if previous and previous.pk != generation.pk:
            SemanticIndexGeneration.objects.filter(pk=previous.pk).update(
                status=SemanticIndexGeneration.Status.SUPERSEDED)
        generation.status = SemanticIndexGeneration.Status.PUBLISHED
        generation.published_at = now
        generation.save()
        state.current_generation = generation
        state.corpus_manifest_hash = generation.corpus_manifest_hash
        state.provider = generation.provider
        state.model_identifier = generation.model_identifier
        state.encoder_version = generation.encoder_version
        state.published_at = now
        state.save()
    return generation


def published_generation():
    state = SemanticIndexPublicationState.objects.filter(pk=1).first()
    return state.current_generation if state else None


def index_status():
    """UNAVAILABLE (no published generation), CURRENT, or STALE (corpus changed).

    Staleness is recomputed with the published generation's OWN document schema, so the
    schema-1.1 pilot is checked against a 1.1 recompute and a 1.2 generation against a 1.2
    recompute — a global default could otherwise false-stale the pilot.
    """
    generation = published_generation()
    if generation is None:
        return STATUS_UNAVAILABLE, None
    from .semantic_builders import corpus_hash_for_schema
    if generation.corpus_manifest_hash != corpus_hash_for_schema(
            generation.document_schema_version):
        return STATUS_STALE, generation
    return STATUS_CURRENT, generation


def load_published_vectors():
    """(corpus_item_id -> vector) for the currently published generation, or {}."""
    generation = published_generation()
    if generation is None:
        return {}, None
    rows = SemanticDocumentEmbedding.objects.filter(
        generation=generation).values_list("corpus_item_id", "vector")
    return {str(item_id): vector for item_id, vector in rows}, generation


def semantic_scores(query_vector):
    """corpus_item_id -> cosine score against the published index. {} if unavailable."""
    vectors, generation = load_published_vectors()
    if not vectors:
        return {}, generation
    return ({item_id: cosine_similarity(query_vector, vector)
             for item_id, vector in vectors.items()}, generation)
