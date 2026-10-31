"""Signed human semantic-metadata contract — DIP-1C-5B (`human_semantic_metadata/1.0`).

Reviewer-authored, bounded, controlled-vocabulary descriptors that can later enrich semantic
documents (schema 1.3). DIP-1C-5A found the corpus lacks the descriptive content semantics
needs; this is how that content arrives — **from a real human review, never machine-invented**.

Hard boundaries this contract enforces:
* Every field is a controlled vocabulary or tightly bounded value. No arbitrary free-form tag
  arrays; reviewer notes are bounded text and never enter embedding text.
* A descriptor **describes**; it grants nothing — not canonical status, ownership, licence,
  rights, retrieval, automatic use, export, or production. Rights/ownership stay with
  governance and are unexpressible here.
* Brand descriptors are **observational only**: "BBROSE label observed but unconfirmed",
  never "official logo / canonical master / owned by BBROSE".
* No value may be a filesystem path or filename (reuses the semantic-document value walker).
"""
from __future__ import annotations


def _classify_value(term):
    """The semantic-document path/filename detector, imported lazily: `semantic_document`
    reaches the projector, and the projector imports this contract."""
    from .semantic_document import _classify_value as classify
    return classify(term)



METADATA_SCHEMA = "human_semantic_metadata/1.0"
METADATA_ASSERTION_DOMAIN = "human_semantic_metadata"
VOCABULARY_VERSION = "human_semantic_vocabulary/1.0"

# --- frozen controlled vocabularies ---------------------------------------------
PRODUCT_FAMILY = frozenset({
    "SKINCARE", "HAIR_CARE", "LIP_COLOUR", "LIP_GLOSS", "LIP_BALM", "EYE_COLOUR",
    "MASCARA", "EYELINER", "BROW", "COMPLEXION", "FOUNDATION", "CONCEALER",
    "FACE_POWDER", "BLUSH", "HIGHLIGHTER", "CONTOUR", "PRIMER", "NAIL", "FRAGRANCE",
    "MULTI_PRODUCT", "UNKNOWN",
})
DESIGN_STYLE = frozenset({
    "MINIMAL", "LUXURY", "MODERN", "CLASSIC", "VINTAGE", "BOLD", "SOFT", "ELEGANT",
    "PLAYFUL", "EDITORIAL", "NATURAL", "CLINICAL", "GLAMOROUS", "GEOMETRIC",
    "ILLUSTRATIVE", "TYPOGRAPHIC", "UNKNOWN",
})
MOTIF = frozenset({
    "FLORAL", "LEAF_BOTANICAL", "FRUIT", "ABSTRACT", "GEOMETRIC", "LINE_ART", "STARS",
    "HEARTS", "BUTTERFLY", "ANIMAL", "WATER", "TEXTURE", "NO_DOMINANT_MOTIF", "UNKNOWN",
})
VISUAL_MOOD = frozenset({
    "FEMININE", "MASCULINE", "NEUTRAL", "SOFT", "ENERGETIC", "ROMANTIC",
    "SOPHISTICATED", "YOUTHFUL", "PROFESSIONAL", "PREMIUM", "FRESH", "DRAMATIC",
    "UNKNOWN",
})
COLOR_CHARACTERISTICS = frozenset({
    "SOFT_PINK", "NUDE", "GOLD", "SILVER", "PASTEL", "BRIGHT", "DARK", "MONOCHROME",
    "HIGH_CONTRAST", "LOW_CONTRAST", "WARM", "COOL", "MULTICOLOR", "UNKNOWN",
})
LAYOUT_OR_FORMAT = frozenset({
    "PRODUCT_PACKAGING", "CARTON", "LABEL", "DISPLAY", "GIFT_SET", "PRODUCT_CONTAINER",
    "PALETTE", "POSTER", "SOCIAL_MEDIA", "PATTERN", "ICON", "BACKGROUND",
    "DECORATIVE_ELEMENT", "FONT", "UNKNOWN",
})
FONT_STYLE = frozenset({
    "SERIF", "SANS_SERIF", "SCRIPT", "DISPLAY", "GEOMETRIC", "HUMANIST", "CONDENSED",
    "EXPANDED", "BOLD", "LIGHT", "ELEGANT", "PLAYFUL", "EDITORIAL", "ARABIC_DISPLAY",
    "CJK_DISPLAY", "UNKNOWN",
})
SCRIPT_SUITABILITY = frozenset({
    "LATIN", "ARABIC", "CYRILLIC", "GREEK", "HEBREW", "CJK", "HANGUL", "DEVANAGARI",
    "THAI", "UNKNOWN",
})
# brand descriptors are OBSERVATIONAL only — ownership/canonical status is unexpressible
BRAND_OBSERVATION = frozenset({
    "VISIBLE_WORDMARK", "COMPOSITION_LOCKUP", "PALETTE_LIKE_GRAPHIC",
    "UNKNOWN_BRAND", "BBROSE_LABEL_OBSERVED_UNCONFIRMED", "THIRD_PARTY_LABEL_OBSERVED",
})

_VOCAB_FIELDS = {
    "product_families": PRODUCT_FAMILY,
    "design_styles": DESIGN_STYLE,
    "motifs": MOTIF,
    "visual_moods": VISUAL_MOOD,
    "color_characteristics": COLOR_CHARACTERISTICS,
    "layout_or_format_types": LAYOUT_OR_FORMAT,
    "font_styles": FONT_STYLE,
    "script_suitability": SCRIPT_SUITABILITY,
    "brand_observations": BRAND_OBSERVATION,
}
# the public view of the controlled vocabularies: `{field: sorted terms}`, for rendering the
# reviewer form. A form is built FROM the contract, so an unlisted term is never offerable.
VOCABULARY_FIELDS = {
    field: tuple(sorted(vocab)) for field, vocab in _VOCAB_FIELDS.items()
}
VOCABULARY_FIELDS["asset_categories"] = tuple(sorted(LAYOUT_OR_FORMAT))

# free-text search synonyms: bounded, path-checked, never a tag dump
_MAX_SYNONYMS = 12
_MAX_SYNONYM_LEN = 40
_MAX_TERMS_PER_FIELD = 12
_MAX_NOTE_LEN = 2000

# values a descriptor may NEVER assert — ownership/authority live in governance, not here
FORBIDDEN_BRAND_CLAIMS = frozenset({
    "OFFICIAL_LOGO", "CANONICAL_MASTER", "OWNED_BY_BBROSE", "APPROVED", "CANONICAL",
    "LICENSED", "OFFICIAL",
})

METADATA_FIELDS = (
    "product_families", "design_styles", "motifs", "visual_moods",
    "color_characteristics", "layout_or_format_types", "asset_categories",
    "font_styles", "script_suitability", "brand_observations", "search_synonyms",
    "reviewer_notes",
)


class MetadataBundleError(ValueError):
    """A bundle that is not within the controlled contract is refused, never trimmed."""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


def _bounded_vocab_list(values, allowed, field):
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise MetadataBundleError(f"{field} must be a list", code="FIELD_NOT_A_LIST")
    out = []
    for v in values:
        if not isinstance(v, str):
            raise MetadataBundleError(f"{field} entries must be text", code="ENTRY_NOT_TEXT")
        term = v.strip().upper()
        if term in FORBIDDEN_BRAND_CLAIMS:
            raise MetadataBundleError(
                f"{field} may not assert ownership/authority ({term})",
                code="FORBIDDEN_AUTHORITY_CLAIM")
        if term not in allowed:
            raise MetadataBundleError(
                f"unsupported {field} value {term!r}", code="UNSUPPORTED_VOCABULARY")
        out.append(term)
    if len(out) > _MAX_TERMS_PER_FIELD:
        raise MetadataBundleError(f"{field} exceeds {_MAX_TERMS_PER_FIELD} terms",
                                  code="TOO_MANY_TERMS")
    # deduped, deterministic
    return sorted(set(out))


def _synonyms(values):
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise MetadataBundleError("search_synonyms must be a list", code="FIELD_NOT_A_LIST")
    out = []
    for v in values:
        if not isinstance(v, str):
            raise MetadataBundleError("search_synonyms entries must be text",
                                      code="ENTRY_NOT_TEXT")
        term = " ".join(v.strip().split())
        if not term:
            continue
        if len(term) > _MAX_SYNONYM_LEN:
            raise MetadataBundleError("search_synonyms entry too long",
                                      code="SYNONYM_TOO_LONG")
        if _classify_value(term):
            raise MetadataBundleError("search_synonyms may not be a path/filename",
                                      code="PROHIBITED_VALUE")
        out.append(term)
    if len(out) > _MAX_SYNONYMS:
        raise MetadataBundleError(f"search_synonyms exceeds {_MAX_SYNONYMS}",
                                  code="TOO_MANY_SYNONYMS")
    return sorted(set(out))


def build_metadata_bundle(raw: dict) -> dict:
    """Validate an untrusted bundle into the bounded `human_semantic_metadata/1.0` shape,
    or refuse it. Deterministic; contains only controlled terms."""
    if not isinstance(raw, dict):
        raise MetadataBundleError("bundle must be an object", code="BUNDLE_NOT_OBJECT")
    # Idempotent by contract: a already-built bundle must re-validate unchanged, because the
    # projector defensively re-runs this over the signed payload. A version stamp that does
    # not match the frozen contract is refused, never silently upgraded.
    allowed_input = set(METADATA_FIELDS) | {
        "asset_categories", "schema_version", "vocabulary_version"}
    unknown = set(raw) - allowed_input
    if unknown:
        raise MetadataBundleError(f"unsupported bundle fields: {sorted(unknown)}",
                                  code="UNSUPPORTED_FIELD")
    if raw.get("schema_version", METADATA_SCHEMA) != METADATA_SCHEMA:
        raise MetadataBundleError("unsupported bundle schema_version",
                                  code="UNSUPPORTED_BUNDLE_SCHEMA")
    if raw.get("vocabulary_version", VOCABULARY_VERSION) != VOCABULARY_VERSION:
        raise MetadataBundleError("unsupported bundle vocabulary_version",
                                  code="UNSUPPORTED_VOCABULARY_VERSION")

    bundle = {"schema_version": METADATA_SCHEMA, "vocabulary_version": VOCABULARY_VERSION}
    for field, vocab in _VOCAB_FIELDS.items():
        bundle[field] = _bounded_vocab_list(raw.get(field), vocab, field)
    # asset_categories reuses the layout/format vocabulary (bounded)
    bundle["asset_categories"] = _bounded_vocab_list(
        raw.get("asset_categories"), LAYOUT_OR_FORMAT, "asset_categories")
    bundle["search_synonyms"] = _synonyms(raw.get("search_synonyms"))

    note = raw.get("reviewer_notes") or ""
    if not isinstance(note, str):
        raise MetadataBundleError("reviewer_notes must be text", code="NOTE_NOT_TEXT")
    note = note.strip()[:_MAX_NOTE_LEN]
    if note and _classify_value(note.split()[0]):
        raise MetadataBundleError("reviewer_notes may not begin with a path",
                                  code="PROHIBITED_VALUE")
    bundle["reviewer_notes"] = note

    if not _has_any_descriptor(bundle):
        raise MetadataBundleError("bundle carries no descriptor", code="EMPTY_BUNDLE")
    return bundle


def _has_any_descriptor(bundle) -> bool:
    return any(bundle.get(f) for f in _VOCAB_FIELDS) or bool(
        bundle.get("asset_categories")) or bool(bundle.get("search_synonyms"))


def bundle_embedding_terms(bundle) -> list[str]:
    """The controlled terms that MAY enter a future semantic document (schema 1.3), each a
    VERIFIED_HUMAN_ASSERTION. Reviewer notes are deliberately excluded — they are context
    for humans, not embedding text."""
    terms = []
    for field in _VOCAB_FIELDS:
        terms.extend(bundle.get(field, ()))
    terms.extend(bundle.get("asset_categories", ()))
    terms.extend(bundle.get("search_synonyms", ()))
    return sorted(set(terms))


# --- DIP-1C-5C-CORR-4: conflict resolution ---------------------------------------
#: One signed event that reduces SEVERAL active metadata events to one effective bundle.
#: Distinct from a correction, which has exactly one parent — with a single-parent model,
#: correcting each duplicate separately leaves one active event per correction and resolves
#: nothing.
RESOLUTION_SCHEMA = "human_semantic_metadata_conflict_resolution/1.0"

RESOLUTION_REASONS = (
    "DUPLICATE_ACTIVE_EVENTS_FROM_STALE_APPLICATION_PROCESS",
    "DUPLICATE_ACTIVE_EVENTS_FROM_CONCURRENT_SUBMISSION",
    "DIVERGENT_ACTIVE_BUNDLES_REQUIRING_HUMAN_JUDGEMENT",
)
INCIDENT_TYPES = (
    "STALE_SERVER_DUPLICATE_RECORD_RECOVERY",
    "CONCURRENT_DUPLICATE_RECORD_RECOVERY",
    "DIVERGENT_METADATA_RECOVERY",
)
MAX_EXPLANATION_LENGTH = 2000

RESOLUTION_PAYLOAD_FIELDS = frozenset({
    "resolution_schema", "corpus_item_id", "metadata_domain", "metadata_schema",
    "resolved_event_ids", "resolved_event_sequence_numbers", "prior_bundle_hashes",
    "final_metadata_bundle", "final_evidence_reference_ids", "final_source_hashes",
    "resolution_reason", "incident_type", "reviewer_explanation",
    "policy_id", "policy_version", "authz_snapshot",
})


def bundle_hash(bundle) -> str:
    """Stable identity for a bundle, so a resolution records exactly what it superseded."""
    import hashlib
    import json
    return hashlib.sha256(json.dumps(
        bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
