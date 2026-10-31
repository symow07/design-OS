"""Controlled query embedding — DIP-1C-2 (`intelligence_semantic_query/1.0`).

The **only** path by which a reviewer's query text may leave this machine, and the first
outbound call in the intelligence line that originates from a web request. It is therefore
gated hard:

* Consent is **per request**. Accepting the offline document-index build is never standing
  consent for arbitrary future queries; `confirm_external_query_transfer` must be true on
  every single call, is unchecked by default, and can never be inferred from a prior GET.
* Only the **query document** is sent — the reviewer's normalized phrase and a bounded facet
  label. Corpus records are NOT re-sent per query; those were embedded once, offline.
* Every precondition is checked **before** the call, so a rejected request never reaches the
  provider, and each failure has its own bounded, non-secret code.

Nothing here is persisted: no raw query, no vector, no history row, no analytics, no
DecisionEvent. The vector is returned for immediate similarity computation and discarded.
"""
from __future__ import annotations

import dataclasses
import math
import re
import unicodedata

from .search_contract import (
    CORPUS_SCOPE, DATASET_IDENTIFIERS, ITEM_KINDS, MAX_LIMIT, SEARCH_SCOPES,
)
from .semantic_encoder import (
    OPENAI_MODEL, OPENAI_PROVIDER, EncoderConfigurationError, get_encoder,
)
from .semantic_index import STATUS_CURRENT, index_status

QUERY_SCHEMA = "intelligence_semantic_query/1.0"

# --- bounded semantic facets ----------------------------------------------------
GENERAL_CONCEPT = "GENERAL_CONCEPT"
PRODUCT_CATEGORY = "PRODUCT_CATEGORY"
DESIGN_STYLE = "DESIGN_STYLE"
ASSET_METADATA = "ASSET_METADATA"
FONT_METADATA = "FONT_METADATA"
SEMANTIC_FACETS = (GENERAL_CONCEPT, PRODUCT_CATEGORY, DESIGN_STYLE, ASSET_METADATA,
                   FONT_METADATA)

# --- bounded, non-secret failure codes ------------------------------------------
SEMANTIC_INDEX_UNAVAILABLE = "SEMANTIC_INDEX_UNAVAILABLE"
SEMANTIC_INDEX_STALE = "SEMANTIC_INDEX_STALE"
EXTERNAL_TRANSFER_NOT_CONFIRMED = "EXTERNAL_TRANSFER_NOT_CONFIRMED"
PROVIDER_CONFIGURATION_MISSING = "PROVIDER_CONFIGURATION_MISSING"
MODEL_MISMATCH = "MODEL_MISMATCH"
DIMENSION_MISMATCH = "DIMENSION_MISMATCH"
PROVIDER_ERROR = "PROVIDER_ERROR"
GENERATION_MISMATCH = "GENERATION_MISMATCH"
CORPUS_HASH_MISMATCH = "CORPUS_HASH_MISMATCH"

MAX_QUERY_CHARS = 200
MAX_QUERY_TOKENS = 40

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PATHLIKE = re.compile(r"(^|\s)(/|~/|[A-Za-z]:\\)|\.\./")


class SemanticQueryError(ValueError):
    """A query that cannot be honoured within the boundary is refused, never trimmed."""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


@dataclasses.dataclass(frozen=True)
class SemanticQuery:
    schema_version: str
    query_text: str
    facet: str
    item_kinds: tuple[str, ...]
    dataset_identifiers: tuple[str, ...]
    scope: str
    limit: int
    generation_id: str
    expected_corpus_hash: str
    external_transfer_confirmed: bool

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)

    def transmitted_payload(self) -> dict:
        """EXACTLY what leaves this machine. Nothing else is ever sent."""
        return {"query_text": self.query_text, "facet": self.facet}

    def transmitted_text(self) -> str:
        return f"{self.facet}: {self.query_text}" if self.facet else self.query_text


def _normalize(text):
    if not isinstance(text, str):
        raise SemanticQueryError("query must be text")
    normalized = unicodedata.normalize("NFKC", text).strip()
    normalized = " ".join(normalized.split())
    if _CONTROL.search(normalized):
        raise SemanticQueryError("query contains control characters")
    if _PATHLIKE.search(normalized):
        # a filesystem path is never a legitimate semantic phrase and must not be sent
        raise SemanticQueryError("query looks like a filesystem path")
    if not normalized:
        raise SemanticQueryError("query is empty after normalization")
    if len(normalized) > MAX_QUERY_CHARS:
        raise SemanticQueryError(f"query exceeds {MAX_QUERY_CHARS} characters")
    if len(normalized.split()) > MAX_QUERY_TOKENS:
        raise SemanticQueryError(f"query exceeds {MAX_QUERY_TOKENS} tokens")
    return normalized


def _bounded_list(values, allowed, field):
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise SemanticQueryError(f"{field} must be a list")
    out = []
    for value in values:
        if not isinstance(value, str):
            raise SemanticQueryError(f"{field} entries must be text")
        candidate = value.strip()
        if not candidate:
            continue
        if candidate not in allowed:
            raise SemanticQueryError(f"unsupported {field} value {candidate!r}")
        out.append(candidate)
    return tuple(sorted(set(out)))


_ALLOWED_FIELDS = frozenset({
    "query_text", "facet", "item_kinds", "dataset_identifiers", "scope", "limit",
    "generation_id", "expected_corpus_hash", "confirm_external_query_transfer",
})


def build_semantic_query(raw: dict | None = None) -> SemanticQuery:
    """Validate an untrusted request into a bounded query, or refuse it."""
    raw = dict(raw or {})
    unknown = set(raw) - _ALLOWED_FIELDS
    if unknown:
        raise SemanticQueryError(f"unsupported query fields: {sorted(unknown)}")

    facet = (raw.get("facet") or GENERAL_CONCEPT)
    if not isinstance(facet, str) or facet not in SEMANTIC_FACETS:
        raise SemanticQueryError(f"unsupported semantic facet {facet!r}")
    scope = (raw.get("scope") or CORPUS_SCOPE)
    if scope not in SEARCH_SCOPES:
        raise SemanticQueryError(f"unsupported scope {scope!r}")

    # NB: an explicit None/"" check, not `or 25` — 0 is falsy, so `or` would silently
    # turn an invalid limit=0 into the default instead of refusing it
    limit = raw.get("limit")
    limit = 25 if limit in (None, "") else limit
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise SemanticQueryError("limit must be an integer") from None
    if limit < 1 or limit > MAX_LIMIT:
        raise SemanticQueryError(f"limit must be between 1 and {MAX_LIMIT}")

    # consent is explicit and per-request: anything but a real True is a refusal
    confirmed = raw.get("confirm_external_query_transfer")
    confirmed = confirmed is True or confirmed in ("true", "True", "on", "1")

    return SemanticQuery(
        schema_version=QUERY_SCHEMA,
        query_text=_normalize(raw.get("query_text")),
        facet=facet,
        item_kinds=_bounded_list(raw.get("item_kinds"), ITEM_KINDS, "item_kinds"),
        dataset_identifiers=_bounded_list(
            raw.get("dataset_identifiers"), DATASET_IDENTIFIERS, "dataset_identifiers"),
        scope=scope,
        limit=limit,
        generation_id=str(raw.get("generation_id") or "")[:64],
        expected_corpus_hash=str(raw.get("expected_corpus_hash") or "")[:64],
        external_transfer_confirmed=bool(confirmed),
    )


@dataclasses.dataclass(frozen=True)
class QueryEmbeddingResult:
    ok: bool
    vector: list | None
    failure_code: str
    generation_id: str | None
    provider: str
    model_identifier: str
    dimension: int | None
    # bounded, non-sensitive metadata only — never the raw query or the vector
    query_char_count: int


def _fail(code, query=None, generation=None):
    return QueryEmbeddingResult(
        ok=False, vector=None, failure_code=code,
        generation_id=str(generation.pk) if generation else None,
        provider=generation.provider if generation else "",
        model_identifier=generation.model_identifier if generation else "",
        dimension=generation.vector_dimension if generation else None,
        query_char_count=len(query.query_text) if query else 0)


def encode_semantic_query(query: SemanticQuery) -> QueryEmbeddingResult:
    """Embed a reviewer's query for immediate similarity use, or refuse.

    Every gate below runs BEFORE any external call, so a rejected request never reaches the
    provider. The raw query and the returned vector are never persisted or logged.
    """
    # 1. a current published production index must exist
    status, generation = index_status()
    if generation is None:
        return _fail(SEMANTIC_INDEX_UNAVAILABLE, query)
    # 2. stale fails closed BEFORE embedding — never rank a fresh query against stale docs
    if status != STATUS_CURRENT:
        return _fail(SEMANTIC_INDEX_STALE, query, generation)
    # 3-4. provider/model compatibility: a vector from another provider or model is not
    # comparable to these document vectors, so refuse rather than produce nonsense
    if generation.provider != OPENAI_PROVIDER:
        return _fail(MODEL_MISMATCH, query, generation)
    if generation.model_identifier != OPENAI_MODEL:
        return _fail(MODEL_MISMATCH, query, generation)
    # 5. caller's expectations must match the live index, when supplied
    if query.generation_id and query.generation_id != str(generation.pk):
        return _fail(GENERATION_MISMATCH, query, generation)
    if (query.expected_corpus_hash
            and query.expected_corpus_hash != generation.corpus_manifest_hash):
        return _fail(CORPUS_HASH_MISMATCH, query, generation)
    # 6. explicit per-request consent
    if not query.external_transfer_confirmed:
        return _fail(EXTERNAL_TRANSFER_NOT_CONFIRMED, query, generation)

    # 7. construct the encoder (also refuses without confirmation / on a missing key,
    # without inspecting or printing the key)
    try:
        encoder = get_encoder(OPENAI_PROVIDER, external_transfer_confirmed=True)
    except EncoderConfigurationError:
        return _fail(PROVIDER_CONFIGURATION_MISSING, query, generation)

    # 8. the only external call in the whole request
    try:
        vector = encoder.encode([query.transmitted_text()])[0]
    except Exception:
        # bounded code only — never surface a raw provider response
        return _fail(PROVIDER_ERROR, query, generation)

    # 9. validate what came back before it can touch ranking
    if not isinstance(vector, (list, tuple)) or len(vector) != generation.vector_dimension:
        return _fail(DIMENSION_MISMATCH, query, generation)
    if not all(isinstance(c, (int, float)) and not isinstance(c, bool)
               and math.isfinite(c) for c in vector):
        return _fail(PROVIDER_ERROR, query, generation)

    return QueryEmbeddingResult(
        ok=True, vector=[float(c) for c in vector], failure_code="",
        generation_id=str(generation.pk), provider=generation.provider,
        model_identifier=generation.model_identifier,
        dimension=generation.vector_dimension,
        query_char_count=len(query.query_text))
