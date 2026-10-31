"""Discriminative semantic documents — DIP-1C-4A (`intelligence_semantic_document/1.2`).

Schemas 1.0 and 1.1 are left **literally unchanged** in `semantic_document.py` for historical
generations; 1.2 lives here and supersedes them.

**Why 1.2 exists.** The DIP-1C-3 pilot measured schema 1.1 and found the vectors encode item
*kind*, not topic: within-kind cosine 0.70–0.88 against 0.595 across kinds, with 19 documents
sharing byte-identical text (9 brand assets at cosine 1.000). Documents averaged 6.7 unique
tokens, and 145 of 176 had at most one distinctive token. The cause was structural — every
document was dominated by shared schema/workflow boilerplate
(`HISTORICAL_DESIGN … CURATED_HISTORICAL_REFERENCE … READY_FOR_CLASSIFICATION`), drowning the
single token that actually distinguished it. No ranker weight can separate vectors that are
near-identical by construction.

**The 1.2 contract: metadata and embedding text are separate.**

* **Identity/filter metadata** — canonical UUID, external key, item kind, dataset identifier.
  Used for filtering, joining and audit. It **never** enters the embedding text.
* **Embedding text** — topical, differentiating evidence only, rendered from existing bounded
  facts through a frozen phrase vocabulary.

**What 1.2 must not do.** It renders existing facts into readable phrases; it does not invent
facts. Nothing here may claim an item is luxury, floral, minimal, feminine or geometric
unless an actual observation, classification or verified human assertion says so — the
DIP-1C-3 pilot showed semantic similarity happily manufacturing those concepts, and the
honest absence must survive. Phrases are never derived from filenames, paths, directory names
or archive names.

**Expect exact-duplicate text to RISE, and that is correct.** Stripping the hex `external_key`
and SKU `display_label` — identifiers, not topic — makes items whose only differentiator was
that identifier byte-identical. Given the metadata that exists, those items *are* topically
identical; saying so is honest. Re-adding a hash "for uniqueness", or padding with generic
adjectives, would reintroduce exactly the noise this schema removes. Exact-identity lookup is
the search planner's job, not the embedding's.
"""
from __future__ import annotations

import hashlib
import json

from .semantic_document import (
    INCLUDED_FIELDS_V1_0,  # noqa: F401  (kept importable: 1.0 stays frozen and referenced)
    NON_SCRIPT_TOKENS,
    PRODUCT_FAMILY_CLASSIFICATION_TYPE,
    PRODUCT_FAMILY_CONFLICT,
    PRODUCT_FAMILY_VOCABULARY,
    SCRIPT_VOCABULARY,
    SemanticDocumentError,
    _bounded,
    _classify_value,
    _walk,
)

DOCUMENT_SCHEMA_V1_2 = "intelligence_semantic_document/1.2"

# --- what a 1.2 document may carry ----------------------------------------------
METADATA_FIELDS = ("corpus_item_id", "external_key", "item_kind", "dataset_identifier")
INCLUDED_FIELDS_V1_2 = ("metadata", "channels", "embedding_text", "embedding_text_hash")

# --- provenance markers: machine and human never share an unlabelled source ------
PROV_TECHNICAL = "TECHNICAL_OBSERVATION"
PROV_MACHINE = "MACHINE_CLASSIFICATION"
PROV_HUMAN = "VERIFIED_HUMAN_ASSERTION"

# --- embedding channels, in deterministic order ----------------------------------
CHANNELS = (
    "item_type_terms",
    "product_family_terms",
    "asset_category_terms",
    "design_style_terms",
    "font_family_terms",
    "font_style_terms",
    "script_coverage_terms",
    "verified_human_terms",
    "bounded_machine_terms",
)

# --- frozen controlled phrase vocabulary -----------------------------------------
# A presentation of existing facts, not the creation of new ones. Frozen: a phrase change
# alters embedding text and therefore requires a new schema version and generation.
ITEM_TYPE_PHRASES = {
    "HISTORICAL_DESIGN": "historical cosmetics packaging design",
    "DESIGN_ASSET": "cosmetics design asset",
    "FONT": "font typeface",
    "BRAND_ASSET": "brand or logo candidate",
    "BRAND_PALETTE": "color palette candidate",
    "PRODUCT_FAMILY": "product family reference",
    "BRAND_RULE": "brand rule reference",
}

PRODUCT_FAMILY_PHRASES = {
    "LIP_COLOUR": "lip color, lipstick, or lip gloss packaging",
    "EYE_COLOUR": "eye color or eyeshadow packaging",
    "CONCEALER": "concealer and complexion packaging",
    "COMPLEXION": "foundation, face powder, or complexion packaging",
    "MAKEUP_COMPACT": "makeup compact packaging",
    "PRIMER_SKINCARE": "primer or skincare packaging",
}

SCRIPT_PHRASES = {
    "LATIN": "font with Latin script coverage",
    "ARABIC": "font with Arabic script coverage",
    "CYRILLIC": "font with Cyrillic script coverage",
    "GREEK": "font with Greek script coverage",
    "HEBREW": "font with Hebrew script coverage",
    "CJK": "font with Chinese, Japanese, or Korean script coverage",
    "HANGUL": "font with Hangul script coverage",
    "DEVANAGARI": "font with Devanagari script coverage",
    "THAI": "font with Thai script coverage",
}

# asset categories — the machine's candidate_asset_kind, rendered. UNKNOWN yields NO phrase:
# an unknown asset has no topical evidence, and inventing one would be fabrication.
ASSET_CATEGORY_PHRASES = {
    "MOTIF": "decorative motif graphic",
    "PATTERN": "repeating surface pattern",
    "BACKGROUND": "background texture or backdrop",
    "ILLUSTRATION": "illustration artwork",
    "LOGO_CANDIDATE": "logo mark candidate",
    "PHOTO": "photographic image",
}

BRAND_KIND_PHRASES = {
    "LOGO": "logo mark",
    "WORDMARK": "brand wordmark",
    "BRAND_GRAPHIC": "brand graphic element",
    "PALETTE": "color palette",
    "LOCKUP": "brand lockup composition",
}

# machine classification labels worth rendering as topical evidence. Workflow/enum labels
# (READY_FOR_CLASSIFICATION, EVIDENCE_READINESS_DIMENSIONS, …) are deliberately absent.
MACHINE_LABEL_PHRASES = {
    "SURFACE_ARTWORK": "printed surface artwork",
    "DIELINE_CANDIDATE": "packaging dieline structure",
    "PRODUCT_PHOTO": "product photograph",
    "COLOR_PALETTE_STRIP": "color palette strip",
    "SPEC_TABLE": "specification table",
    "TECHNICAL_NOTES": "technical production notes",
    "LEGAL_TEXT": "legal or regulatory text",
    "BARCODE": "barcode",
}

# observed brand labels are identity evidence, rendered as-is only when safe and bounded
BRAND_LABEL_PHRASES = {
    "BBROSE": "BBROSE brand candidate",
    "ATC": "ATC third-party brand candidate",
    "JOJIA": "JOJIA third-party brand candidate",
}

# Concepts the corpus records NOTHING about. The DIP-1C-3 pilot showed semantic similarity
# happily manufacturing these (Q09 luxury, Q10 minimal, Q12 geometric returned ten confident
# results over a corpus that describes none of them). Named here so tests can assert that
# *our controlled vocabulary* never introduces one.
#
# The invariant is about what WE assert, not about what an item is named. A font whose
# recorded family name is "gobold bold" carries the word "bold" through `font_family_terms`
# — that is the item's own name, an existing fact, not a claim we manufactured. Enriching
# every design with generic cosmetics adjectives to lift benchmark scores is what this
# forbids.
UNSUPPORTED_CONCEPTS = (
    "luxury", "elegant", "minimal", "floral", "feminine", "geometric", "premium",
    "delicate",
)

# the vocabularies WE author — none may contain an unsupported concept
CONTROLLED_VOCABULARIES = (
    "ITEM_TYPE_PHRASES", "PRODUCT_FAMILY_PHRASES", "SCRIPT_PHRASES",
    "ASSET_CATEGORY_PHRASES", "BRAND_KIND_PHRASES", "MACHINE_LABEL_PHRASES",
    "BRAND_LABEL_PHRASES",
)

_MAX_TERMS_PER_CHANNEL = 12


class SemanticDocumentV12Error(SemanticDocumentError):
    pass


def _term(text, provenance):
    return {"term": text, "provenance": provenance}


def _font_style_terms(font):
    """Font style rendered from ACTUAL recorded fields — weight, italic — never inferred
    from the family name.

    Name-token inference was tried and rejected: `'bold' in 'gobold'` fires on the brand
    name *gobold*, which asserts a weight the font never claimed. More fundamentally, the
    corpus does not record whether a face is serif or sans (DIP-0C4a: style tags are
    heuristic, family-level and human-reviewable), so deriving "serif typeface" from a name
    containing "serif" would be a claim, not a fact. The family name itself is already in
    `font_family_terms`, so a query for a serif-named face can still match it — honestly,
    by its name, without us asserting its anatomy.

    The one name-derived exception is demo/trial, matched on a word boundary: a demo
    distribution is a licensing suspicion the corpus already treats as a flag, and it is
    rendered as a suspicion, never as a licence finding.
    """
    import re
    if font is None:
        return []
    terms = []
    weight = getattr(font, "weight", None)
    if isinstance(weight, int):
        if weight >= 600:
            terms.append(_term("bold weight typeface", PROV_TECHNICAL))
        elif weight <= 300:
            terms.append(_term("light weight typeface", PROV_TECHNICAL))
    if getattr(font, "italic", False):
        terms.append(_term("italic typeface", PROV_TECHNICAL))
    name = (getattr(font, "family_name", "") or "").lower()
    if re.search(r"\b(demo|trial)\b", name):
        terms.append(_term("demo or trial font distribution", PROV_TECHNICAL))
    return terms


def build_channels(item, *, facts_by_item, machine_by_item, human_by_item):
    """Topical channels for one item, from pre-loaded bulk data. No per-item queries."""
    item_id = str(item.pk)
    channels = {name: [] for name in CHANNELS}

    # --- item type -------------------------------------------------------------
    phrase = ITEM_TYPE_PHRASES.get(item.item_kind)
    if phrase:
        channels["item_type_terms"].append(_term(phrase, PROV_TECHNICAL))

    # --- product family (machine) ---------------------------------------------
    families = set()
    historical = getattr(item, "historical_design_profile", None)
    if historical is not None and (historical.product_family_machine_label or "").strip():
        families.add(historical.product_family_machine_label.strip().lower())
    for classification_type, label in machine_by_item.get(item_id, ()):
        if classification_type == PRODUCT_FAMILY_CLASSIFICATION_TYPE and (label or "").strip():
            families.add(label.strip().lower())
    normalized = set()
    for raw in families:
        if _classify_value(raw):
            continue                      # a path-like value can never become a family
        mapped = PRODUCT_FAMILY_VOCABULARY.get(raw)
        if mapped:
            normalized.add(mapped)
    for family in sorted(normalized):
        rendered = PRODUCT_FAMILY_PHRASES.get(family)
        if rendered:
            channels["product_family_terms"].append(_term(rendered, PROV_MACHINE))
    if len(normalized) > 1:
        # disagreement stays visible rather than being silently resolved
        channels["product_family_terms"].append(
            _term(PRODUCT_FAMILY_CONFLICT.lower().replace("_", " "), PROV_MACHINE))

    # --- asset category (machine) ---------------------------------------------
    asset = getattr(item, "design_asset_profile", None)
    if asset is not None:
        rendered = ASSET_CATEGORY_PHRASES.get(asset.candidate_asset_kind)
        if rendered:                      # UNKNOWN deliberately yields nothing
            channels["asset_category_terms"].append(_term(rendered, PROV_MACHINE))

    # --- brand candidate (machine) --------------------------------------------
    brand = getattr(item, "brand_candidate_profile", None)
    if brand is not None:
        rendered = BRAND_KIND_PHRASES.get(brand.candidate_kind)
        if rendered:
            channels["asset_category_terms"].append(_term(rendered, PROV_MACHINE))
        label = (brand.observed_brand_label or "").strip().upper()
        rendered_label = BRAND_LABEL_PHRASES.get(label)
        if rendered_label:
            channels["bounded_machine_terms"].append(_term(rendered_label, PROV_MACHINE))

    # --- font family + style + scripts ----------------------------------------
    font = getattr(item, "font_face_profile", None)
    if font is not None:
        family_name = _bounded(font.family_name or "")
        # a font family name IS topical (`almarai`, `gobold`) — unlike a hex key or SKU —
        # so it stays, but only when it is safe
        if family_name and not _classify_value(family_name):
            channels["font_family_terms"].append(_term(family_name, PROV_TECHNICAL))
        channels["font_style_terms"].extend(_font_style_terms(font))
        coverage = font.script_coverage
        tokens = list(coverage.keys()) if isinstance(coverage, dict) else list(coverage or [])
        scripts = set()
        for token in tokens:
            key = str(token).strip().lower()
            if not key or key in NON_SCRIPT_TOKENS:
                continue
            mapped = SCRIPT_VOCABULARY.get(key)
            if mapped:
                scripts.add(mapped)
        for script in sorted(scripts):
            rendered = SCRIPT_PHRASES.get(script)
            if rendered:
                channels["script_coverage_terms"].append(_term(rendered, PROV_TECHNICAL))

    # --- bounded machine labels ------------------------------------------------
    for classification_type, label in sorted(machine_by_item.get(item_id, ())):
        rendered = MACHINE_LABEL_PHRASES.get(label)
        if rendered:
            channels["bounded_machine_terms"].append(_term(rendered, PROV_MACHINE))

    # --- verified human assertions --------------------------------------------
    for label in sorted(human_by_item.get(item_id, ())):
        safe = _bounded(label)
        if safe and not _classify_value(safe):
            channels["verified_human_terms"].append(_term(safe, PROV_HUMAN))

    # dedupe within a channel, keep deterministic order, bound the size
    for name, terms in channels.items():
        seen, unique = set(), []
        for entry in terms:
            if entry["term"] in seen:
                continue
            seen.add(entry["term"])
            unique.append(entry)
        channels[name] = unique[:_MAX_TERMS_PER_CHANNEL]
    return channels


def render_embedding_text(channels) -> str:
    """Deterministic embedding text: channel order fixed, phrases deduplicated across the
    whole text, whitespace normalized, empty channels omitted. No term is repeated to
    simulate weighting, and no prompt-like prose is added."""
    seen, parts = set(), []
    for name in CHANNELS:
        for entry in channels.get(name, ()):
            phrase = " ".join(str(entry["term"]).split())
            if phrase and phrase.lower() not in seen:
                seen.add(phrase.lower())
                parts.append(phrase)
    return ". ".join(parts)


def embedding_text_hash(text) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_hash_v12(document) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _dataset_identifier(item):
    profile = getattr(item, "design_asset_profile", None)
    return profile.dataset_identifier if profile is not None else ""


def build_semantic_document_v12(item, *, facts_by_item=None, machine_by_item=None,
                                human_by_item=None) -> dict:
    """One schema-1.2 document. Pure given the pre-loaded maps; no per-item queries."""
    facts_by_item = facts_by_item or {}
    machine_by_item = machine_by_item or {}
    human_by_item = human_by_item or {}
    channels = build_channels(item, facts_by_item=facts_by_item,
                              machine_by_item=machine_by_item,
                              human_by_item=human_by_item)
    text = render_embedding_text(channels)
    document = {
        "schema_version": DOCUMENT_SCHEMA_V1_2,
        # identity/filter metadata — NEVER enters the embedding text
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
    _assert_within_boundary_v12(document)
    return document


def _assert_within_boundary_v12(document):
    """Fail closed on an unexpected field or ANY prohibited value, anywhere."""
    unexpected = set(document) - ({"schema_version"} | set(INCLUDED_FIELDS_V1_2))
    if unexpected:
        raise SemanticDocumentV12Error(
            f"semantic document has unexpected fields: {sorted(unexpected)}")
    unexpected_meta = set(document["metadata"]) - set(METADATA_FIELDS)
    if unexpected_meta:
        raise SemanticDocumentV12Error(
            f"metadata has unexpected fields: {sorted(unexpected_meta)}")
    unexpected_channels = set(document["channels"]) - set(CHANNELS)
    if unexpected_channels:
        raise SemanticDocumentV12Error(
            f"unexpected channels: {sorted(unexpected_channels)}")
    findings = []
    _walk(document, "", findings)
    if findings:
        located = ", ".join(f"{field}={code}" for field, code in findings)
        raise SemanticDocumentV12Error(
            f"prohibited value in semantic document at {located}",
            code=findings[0][1])
