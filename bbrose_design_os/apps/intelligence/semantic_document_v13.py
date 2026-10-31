"""Human-enriched semantic documents — DIP-1C-5B
(`intelligence_semantic_document/1.3`). **Defined and locally previewable only.**

DIP-1C-5A measured the ceiling of schema 1.2 honestly: the corpus records item *kind*,
dataset and a handful of machine labels, and essentially nothing about what a design *looks
like*. Confidence-gated semantic rescue could not fix that, because no ranker recovers
information the documents never contained. Schema 1.3 is the channel through which the
missing information can arrive — from a signed human review, never from generation.

**1.3 = 1.2 plus one thing.** Every 1.2 channel, phrase vocabulary and boundary rule is
reused verbatim from `semantic_document_v12`; 1.3 adds `human_semantic_metadata_terms`,
rendered from PROJECTED `human_semantic_metadata/1.0` bundles and marked
`VERIFIED_HUMAN_ASSERTION`. With zero reviewed items, a 1.3 document is *byte-identical in
embedding text* to its 1.2 document — the schema adds a capability, not content.

**Not activated.** 1.3 is not a build target for an external index: no embeddings are
rebuilt, no generation is published, and the published generation stays `e88b1468`
(schema 1.2). Its only sanctioned use today is the local, offline quality preview
(`preview_v13`), which runs against fixture bundles so the effect can be measured before
anyone authorises a transfer.
"""
from __future__ import annotations

from .human_semantic_metadata import METADATA_ASSERTION_DOMAIN, bundle_embedding_terms
from .semantic_document import SemanticDocumentError, _bounded, _classify_value, _walk
from .semantic_document_v12 import (
    CHANNELS as CHANNELS_V1_2,
    METADATA_FIELDS,
    PROV_HUMAN,
    build_channels as build_channels_v12,
    embedding_text_hash,
    render_embedding_text as render_embedding_text_v12,
)
from .semantic_document_v12 import _dataset_identifier

DOCUMENT_SCHEMA_V1_3 = "intelligence_semantic_document/1.3"

HUMAN_METADATA_CHANNEL = "human_semantic_metadata_terms"
# order matters: the human channel renders LAST, so a 1.3 document with no human metadata
# produces embedding text identical to its 1.2 counterpart.
CHANNELS = CHANNELS_V1_2 + (HUMAN_METADATA_CHANNEL,)
INCLUDED_FIELDS_V1_3 = ("metadata", "channels", "embedding_text", "embedding_text_hash")

_MAX_HUMAN_TERMS = 24


class SemanticDocumentV13Error(SemanticDocumentError):
    pass


def render_metadata_term(term: str) -> str:
    """`SOFT_PINK` → `soft pink`. UNKNOWN is dropped: an explicit "we do not know" is not
    topical evidence and must not become embedding text."""
    text = " ".join(str(term).replace("_", " ").split()).lower()
    if not text or text in {"unknown", "unknown brand", "no dominant motif"}:
        return ""
    return text


def human_metadata_terms(bundle) -> list:
    """The controlled terms of one signed bundle, rendered for embedding. Reviewer notes are
    excluded upstream by `bundle_embedding_terms` and never reach here."""
    if not isinstance(bundle, dict):
        return []
    terms, seen = [], set()
    for raw in bundle_embedding_terms(bundle):
        rendered = _bounded(render_metadata_term(raw))
        if not rendered or rendered in seen or _classify_value(rendered):
            continue
        seen.add(rendered)
        terms.append({"term": rendered, "provenance": PROV_HUMAN})
    return terms[:_MAX_HUMAN_TERMS]


def build_channels(item, *, facts_by_item, machine_by_item, human_by_item,
                   metadata_by_item=None):
    channels = dict(build_channels_v12(
        item, facts_by_item=facts_by_item, machine_by_item=machine_by_item,
        human_by_item=human_by_item))
    bundle = (metadata_by_item or {}).get(str(item.pk))
    channels[HUMAN_METADATA_CHANNEL] = human_metadata_terms(bundle) if bundle else []
    return channels


def render_embedding_text(channels) -> str:
    """Same renderer as 1.2, extended by the trailing human channel."""
    base = render_embedding_text_v12(channels)
    seen = {phrase.lower() for phrase in base.split(". ") if phrase}
    parts = [base] if base else []
    for entry in channels.get(HUMAN_METADATA_CHANNEL, ()):
        phrase = " ".join(str(entry["term"]).split())
        if phrase and phrase.lower() not in seen:
            seen.add(phrase.lower())
            parts.append(phrase)
    return ". ".join(parts)


def build_semantic_document_v13(item, *, facts_by_item=None, machine_by_item=None,
                                human_by_item=None, metadata_by_item=None) -> dict:
    channels = build_channels(
        item, facts_by_item=facts_by_item or {}, machine_by_item=machine_by_item or {},
        human_by_item=human_by_item or {}, metadata_by_item=metadata_by_item or {})
    text = render_embedding_text(channels)
    document = {
        "schema_version": DOCUMENT_SCHEMA_V1_3,
        "metadata": {
            "corpus_item_id": str(item.pk),
            "external_key": _bounded(item.external_key),
            "item_kind": item.item_kind,
            "dataset_identifier": _dataset_identifier(item),
        },
        "channels": channels,
        "embedding_text": text,
        "embedding_text_hash": embedding_text_hash(text),
    }
    _assert_within_boundary_v13(document)
    return document


def _assert_within_boundary_v13(document):
    unexpected = set(document) - ({"schema_version"} | set(INCLUDED_FIELDS_V1_3))
    if unexpected:
        raise SemanticDocumentV13Error(
            f"semantic document has unexpected fields: {sorted(unexpected)}")
    unexpected_meta = set(document["metadata"]) - set(METADATA_FIELDS)
    if unexpected_meta:
        raise SemanticDocumentV13Error(
            f"metadata has unexpected fields: {sorted(unexpected_meta)}")
    unexpected_channels = set(document["channels"]) - set(CHANNELS)
    if unexpected_channels:
        raise SemanticDocumentV13Error(
            f"unexpected channels: {sorted(unexpected_channels)}")
    for entry in document["channels"].get(HUMAN_METADATA_CHANNEL, ()):
        if entry.get("provenance") != PROV_HUMAN:
            raise SemanticDocumentV13Error(
                "human metadata terms must be marked VERIFIED_HUMAN_ASSERTION")
    findings = []
    _walk(document, "", findings)
    if findings:
        located = ", ".join(f"{field}={code}" for field, code in findings)
        raise SemanticDocumentV13Error(
            f"prohibited value in semantic document at {located}", code=findings[0][1])


def published_metadata_bundles():
    """`{corpus_item_id: bundle}` from the PUBLISHED projection only.

    Reads the projection, never the raw event chain: an unpublished or superseded bundle has
    no effect on documents, exactly like every other human assertion.
    """
    from .models import CorpusItem, HumanAssertionProjection
    from .projection_reader import read_published_assertions
    item_ids = set(HumanAssertionProjection.objects.filter(
        assertion_domain=METADATA_ASSERTION_DOMAIN).values_list(
        "corpus_item_id", flat=True))
    bundles = {}
    for item in CorpusItem.objects.filter(pk__in=item_ids):
        result = read_published_assertions(item)
        if result.state != "CURRENT":
            continue
        current = (result.current_by_domain or {}).get(METADATA_ASSERTION_DOMAIN)
        if isinstance(current, dict) and isinstance(current.get("normalized_value"), dict):
            bundles[str(item.pk)] = current["normalized_value"]
    return bundles
