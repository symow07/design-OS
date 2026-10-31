"""Bounded search contract — DIP-1B-6 (`intelligence_search/1.0`).

A search query is a **closed vocabulary**, not an expression language. Every field is
validated against a known set derived from the models and the readiness contract; anything
unrecognised is **rejected, never ignored**. A silently-dropped filter would show a
reviewer a different corpus than the one they believe they are looking at, and a
silently-accepted field name is the seam through which query injection arrives.

There is deliberately no free-form filter, no field-name parameter, no ordering
expression, and no unbounded limit.
"""
from __future__ import annotations

import dataclasses

from .dataset_identifiers import SUPPORTED_DESIGN_ASSET_DATASET_IDENTIFIERS
from .models import CorpusItem, ReviewCandidate
from .review_campaign import WAVES
from .review_readiness import OVERALL_STATES, READINESS_BLOCKERS

SEARCH_SCHEMA = "intelligence_search/1.0"

# --- search modes ---------------------------------------------------------------
# Three different questions. They are never the same question.
REVIEWER_CANDIDATE_SEARCH = "REVIEWER_CANDIDATE_SEARCH"
OPERATIONAL_RETRIEVAL = "OPERATIONAL_RETRIEVAL"
AUTOMATIC_USE = "AUTOMATIC_USE"
SEARCH_MODES = (REVIEWER_CANDIDATE_SEARCH, OPERATIONAL_RETRIEVAL, AUTOMATIC_USE)

# --- scopes ---------------------------------------------------------------------
CAMPAIGN_SCOPE = "CAMPAIGN"
CORPUS_SCOPE = "CORPUS"
SEARCH_SCOPES = (CAMPAIGN_SCOPE, CORPUS_SCOPE)

# --- campaign membership tags ---------------------------------------------------
IN_CAMPAIGN = "IN_CAMPAIGN"
OUTSIDE_CAMPAIGN = "OUTSIDE_CAMPAIGN"
WITHHELD_IDENTITY = "WITHHELD_IDENTITY"
TEST_ONLY_EXCLUDED = "TEST_ONLY_EXCLUDED"
MEMBERSHIP_TAGS = (IN_CAMPAIGN, OUTSIDE_CAMPAIGN, WITHHELD_IDENTITY, TEST_ONLY_EXCLUDED)

# --- bounded vocabularies (derived, so they cannot drift from the models) --------
ITEM_KINDS = tuple(CorpusItem.Kind.values)
REVIEW_TYPES = tuple(ReviewCandidate.ReviewType.values)
DATASET_IDENTIFIERS = tuple(SUPPORTED_DESIGN_ASSET_DATASET_IDENTIFIERS)
READINESS_STATES = tuple(OVERALL_STATES)
BLOCKER_CODES = tuple(READINESS_BLOCKERS)
INTEGRITY_STATES = (
    "VERIFIED", "PARTIAL", "HASH_MISMATCH", "STALE_SOURCE", "UNVERIFIED_SOURCE",
    "CONFLICTING", "REVIEW_REQUIRED")
RIGHTS_STATES = (
    "UNREVIEWED", "EVIDENCE_PRESENT", "EVIDENCE_MISSING", "CONFLICTING",
    "NOT_APPLICABLE")
TECHNICAL_STATES = ("COMPLETE", "PARTIAL", "MISSING", "CONFLICTING")

ORDER_BY_SCORE = "SCORE_THEN_IDENTITY"
ORDER_BY_IDENTITY = "IDENTITY"
ORDERINGS = (ORDER_BY_SCORE, ORDER_BY_IDENTITY)

# ranking channel — DIP-1C-1. LEXICAL preserves DIP-1B-6 exactly; SEMANTIC and HYBRID
# engage the published embedding index and are honoured only when one is available.
RANK_LEXICAL = "LEXICAL"
RANK_SEMANTIC = "SEMANTIC"
RANK_HYBRID = "HYBRID"
RANKINGS = (RANK_LEXICAL, RANK_SEMANTIC, RANK_HYBRID)

MAX_QUERY_LENGTH = 200
MAX_LIMIT = 100
DEFAULT_LIMIT = 25
MAX_LABEL_LENGTH = 100

_ALLOWED_FIELDS = frozenset({
    "query", "mode", "scope", "item_kinds", "dataset_identifiers", "waves",
    "review_types", "readiness_states", "blocker_codes", "integrity_states",
    "rights_states", "technical_states", "product_family_labels",
    "candidate_labels", "limit", "page", "order_by",
    # DIP-1C-1
    "ranking", "allow_lexical_fallback",
})


class SearchContractError(ValueError):
    """A query that cannot be honoured exactly as written is refused, never approximated."""


@dataclasses.dataclass(frozen=True)
class SearchQuery:
    schema_version: str
    query: str
    mode: str
    scope: str
    item_kinds: tuple[str, ...]
    dataset_identifiers: tuple[str, ...]
    waves: tuple[str, ...]
    review_types: tuple[str, ...]
    readiness_states: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    integrity_states: tuple[str, ...]
    rights_states: tuple[str, ...]
    technical_states: tuple[str, ...]
    product_family_labels: tuple[str, ...]
    candidate_labels: tuple[str, ...]
    limit: int
    page: int
    order_by: str
    ranking: str
    allow_lexical_fallback: bool

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _text(value, field, *, max_length):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SearchContractError(f"{field} must be text")
    text = value.strip()
    if len(text) > max_length:
        raise SearchContractError(
            f"{field} is limited to {max_length} characters")
    return text


def _bounded_list(values, allowed, field):
    """Normalised, de-duplicated, sorted — so the same request always means the same
    query, and an unknown member is refused rather than dropped."""
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise SearchContractError(f"{field} must be a list")
    normalized = []
    for value in values:
        if not isinstance(value, str):
            raise SearchContractError(f"{field} entries must be text")
        candidate = value.strip()
        if not candidate:
            continue
        if candidate not in allowed:
            raise SearchContractError(f"unsupported {field} value {candidate!r}")
        normalized.append(candidate)
    return tuple(sorted(set(normalized)))


def _free_labels(values, field):
    """Labels are matched, never interpreted: bounded text only, no field names."""
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set, frozenset)):
        raise SearchContractError(f"{field} must be a list")
    normalized = []
    for value in values:
        if not isinstance(value, str):
            raise SearchContractError(f"{field} entries must be text")
        label = value.strip()
        if not label:
            continue
        if len(label) > MAX_LABEL_LENGTH:
            raise SearchContractError(
                f"{field} entries are limited to {MAX_LABEL_LENGTH} characters")
        normalized.append(label)
    return tuple(sorted(set(normalized)))


def _positive_int(value, field, *, default, maximum):
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise SearchContractError(f"{field} must be an integer") from None
    if number < 1:
        raise SearchContractError(f"{field} must be at least 1")
    if number > maximum:
        # an unbounded limit is a denial-of-service and an exfiltration surface
        raise SearchContractError(f"{field} may not exceed {maximum}")
    return number


def build_search_query(raw: dict | None = None) -> SearchQuery:
    """Validate an untrusted request into a bounded query, or refuse it."""
    raw = dict(raw or {})
    unknown = set(raw) - _ALLOWED_FIELDS
    if unknown:
        # no arbitrary field names, no SQL fragments, no JSON filter objects
        raise SearchContractError(f"unsupported search fields: {sorted(unknown)}")

    mode = _text(raw.get("mode"), "mode", max_length=64) or REVIEWER_CANDIDATE_SEARCH
    if mode not in SEARCH_MODES:
        raise SearchContractError(f"unsupported search mode {mode!r}")
    scope = _text(raw.get("scope"), "scope", max_length=32) or CORPUS_SCOPE
    if scope not in SEARCH_SCOPES:
        raise SearchContractError(f"unsupported search scope {scope!r}")
    order_by = _text(raw.get("order_by"), "order_by", max_length=64) or ORDER_BY_SCORE
    if order_by not in ORDERINGS:
        raise SearchContractError(f"unsupported ordering {order_by!r}")
    ranking = _text(raw.get("ranking"), "ranking", max_length=16) or RANK_LEXICAL
    if ranking not in RANKINGS:
        raise SearchContractError(f"unsupported ranking {ranking!r}")
    fallback = raw.get("allow_lexical_fallback", True)
    if not isinstance(fallback, bool):
        raise SearchContractError("allow_lexical_fallback must be a boolean")

    return SearchQuery(
        schema_version=SEARCH_SCHEMA,
        query=_text(raw.get("query"), "query", max_length=MAX_QUERY_LENGTH),
        mode=mode,
        scope=scope,
        item_kinds=_bounded_list(raw.get("item_kinds"), ITEM_KINDS, "item_kinds"),
        dataset_identifiers=_bounded_list(
            raw.get("dataset_identifiers"), DATASET_IDENTIFIERS, "dataset_identifiers"),
        waves=_bounded_list(raw.get("waves"), WAVES, "waves"),
        review_types=_bounded_list(
            raw.get("review_types"), REVIEW_TYPES, "review_types"),
        readiness_states=_bounded_list(
            raw.get("readiness_states"), READINESS_STATES, "readiness_states"),
        blocker_codes=_bounded_list(
            raw.get("blocker_codes"), BLOCKER_CODES, "blocker_codes"),
        integrity_states=_bounded_list(
            raw.get("integrity_states"), INTEGRITY_STATES, "integrity_states"),
        rights_states=_bounded_list(
            raw.get("rights_states"), RIGHTS_STATES, "rights_states"),
        technical_states=_bounded_list(
            raw.get("technical_states"), TECHNICAL_STATES, "technical_states"),
        product_family_labels=_free_labels(
            raw.get("product_family_labels"), "product_family_labels"),
        candidate_labels=_free_labels(raw.get("candidate_labels"), "candidate_labels"),
        limit=_positive_int(raw.get("limit"), "limit",
                            default=DEFAULT_LIMIT, maximum=MAX_LIMIT),
        page=_positive_int(raw.get("page"), "page", default=1, maximum=10_000),
        order_by=order_by,
        ranking=ranking,
        allow_lexical_fallback=fallback,
    )
