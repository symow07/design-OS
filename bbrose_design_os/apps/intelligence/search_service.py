"""Read-only reviewer search — DIP-1B-6.

Executes a validated `intelligence_search/1.0` query with the
`intelligence_lexical_ranker/1.0` profile and assembles bounded results.

The whole point of this module is a separation it must never blur:

* **REVIEWER_CANDIDATE_SEARCH** — an authorized human may examine this candidate,
  including items blocked by rights, identity or integrity (their blockers are shown).
  This mode asserts nothing about operational eligibility.
* **OPERATIONAL_RETRIEVAL** — only items with a currently valid RETRIEVAL permission.
* **AUTOMATIC_USE** — only items with an independently valid AUTOMATIC_USE permission.

Being reviewable is not being retrievable, and being retrievable is not being usable by a
machine. Every allow/deny comes from `evaluate_retrieval_readiness`, which wraps the
canonical permission gate; this module never decides authority itself.

Search writes nothing: no decision, no projection, no candidate update, no access
timestamp.
"""
from __future__ import annotations

from django.urls import reverse

from .governance_reader import read_published_governance
from .hybrid_ranker import HYBRID_RANKER_VERSION, blended_score, merge_reasons
from .lexical_ranker import RANKER_VERSION, score_item
from .legacy_signals import LEGACY_SIGNAL_NON_AUTHORITATIVE
from .semantic_encoder import get_encoder
from .semantic_index import index_status, semantic_scores
from .models import (
    CorpusItem, EvidenceReference,
    MachineClassification, ObservedFact,
    ReviewCandidate,
)
from .projection_reader import read_published_assertions
from .retrieval_readiness import evaluate_retrieval_readiness
from .review_campaign import CampaignScopeError, campaign_entries_by_candidate
from .review_packet import REDACTED_LOCATION, _bounded_location
from .review_readiness import assess_readiness
from .search_contract import (
    AUTOMATIC_USE, CAMPAIGN_SCOPE, IN_CAMPAIGN, OPERATIONAL_RETRIEVAL,
    OUTSIDE_CAMPAIGN, RANK_HYBRID, RANK_LEXICAL, RANK_SEMANTIC,
    REVIEWER_CANDIDATE_SEARCH, SEARCH_SCHEMA, TEST_ONLY_EXCLUDED,
    WITHHELD_IDENTITY, ORDER_BY_IDENTITY,
)

RESULT_SCHEMA = "intelligence_search_result/1.0"

# what a result must never let a reader conclude
W_NOT_APPROVAL = "CANDIDATE_SEARCH_DOES_NOT_AUTHORIZE_OPERATIONAL_USE"
W_RIGHTS = "RIGHTS_UNREVIEWED_NOT_CLEARED_FOR_USE"
W_IDENTITY = "IDENTITY_UNCONFIRMED_NOT_A_BBROSE_ASSET"
W_INTEGRITY = "EVIDENCE_INTEGRITY_UNRESOLVED"
W_MACHINE = "MACHINE_CLASSIFICATION_IS_NOT_HUMAN_TRUTH"


def _display(item):
    for attr, field in (("historical_design_profile", "display_title"),
                        ("font_face_profile", "family_name"),
                        ("design_asset_profile", "candidate_source_key")):
        profile = getattr(item, attr, None)
        if profile is not None:
            return getattr(profile, field) or item.external_key
    brand = getattr(item, "brand_candidate_profile", None)
    if brand is not None:
        return brand.observed_brand_label or brand.get_candidate_kind_display()
    return item.external_key


def _dataset_identifier(item):
    profile = getattr(item, "design_asset_profile", None)
    return profile.dataset_identifier if profile is not None else ""


def _product_family_label(item):
    profile = getattr(item, "historical_design_profile", None)
    # a machine label: matched, never treated as verification
    return profile.product_family_machine_label if profile is not None else ""


def _technical_label(item):
    for attr, field in (("design_asset_profile", "technical_readiness"),
                        ("font_face_profile", "technical_suitability_state"),
                        ("historical_design_profile", "audit_status")):
        profile = getattr(item, attr, None)
        if profile is not None:
            return getattr(profile, field) or ""
    return ""


def _is_test_only(item):
    profile = getattr(item, "design_asset_profile", None)
    if profile is not None and profile.is_test_only:
        return True
    return EvidenceReference.objects.filter(
        corpus_item=item, is_test_only=True).exists()


def _membership(item, entry, readiness):
    """Every result states its relationship to the frozen campaign — never blended."""
    if _is_test_only(item):
        return TEST_ONLY_EXCLUDED
    if not readiness.candidate_review_visible:
        return WITHHELD_IDENTITY
    return IN_CAMPAIGN if entry else OUTSIDE_CAMPAIGN


def _warnings(review_readiness, retrieval):
    warnings = [W_NOT_APPROVAL, W_MACHINE]
    if review_readiness is not None:
        if review_readiness.rights_evidence == "UNREVIEWED":
            warnings.append(W_RIGHTS)
        if review_readiness.identity_evidence in ("UNVERIFIED", "PARTIALLY_VERIFIED",
                                                  "CONFLICTING"):
            warnings.append(W_IDENTITY)
    if retrieval.evidence_integrity_blockers:
        warnings.append(W_INTEGRITY)
    return tuple(warnings)


def _labels(item):
    facts = list(ObservedFact.objects.filter(corpus_item=item).values_list(
        "fact_type", flat=True))
    machine = list(MachineClassification.objects.filter(
        corpus_item=item).values_list("label", flat=True))
    return facts, machine


def _source_hash_summary(item):
    hashes = sorted({
        h for h in EvidenceReference.objects.filter(
            corpus_item=item).values_list("source_artifact__sha256", flat=True) if h})
    return {"source_hash_count": len(hashes), "source_hashes": hashes[:8]}


def _candidate_for(item):
    return ReviewCandidate.objects.filter(corpus_item=item).order_by("created_at").first()


def _base_queryset():
    return CorpusItem.objects.select_related(
        "historical_design_profile", "design_asset_profile", "font_face_profile",
        "brand_candidate_profile")


def _legacy_signal_note():
    # legacy signals are shown as diagnostics only; they never rank or grant
    return {"classification": LEGACY_SIGNAL_NON_AUTHORITATIVE,
            "grants": "NOTHING",
            "affects_ranking": False}


def _semantic_unavailable_result(query, idx_status):
    """A SEMANTIC-only request with no usable index and fallback disabled: fail clearly,
    never silently return lexical results dressed as semantic."""
    return {
        "schema_version": SEARCH_SCHEMA,
        "result_schema_version": RESULT_SCHEMA,
        "ranker_version": RANKER_VERSION,
        "hybrid_ranker_version": HYBRID_RANKER_VERSION,
        "ranking_is_semantic": False,
        "ranking_requested": query.ranking,
        "ranking_engaged": "NONE",
        "semantic_index_status": idx_status,
        "result_label": "SEMANTIC_UNAVAILABLE",
        "semantic_generation_id": None,
        "mode": query.mode,
        "scope": query.scope,
        "query": query.as_dict(),
        "total_results": 0,
        "page": query.page,
        "limit": query.limit,
        "results": [],
        "withheld_identity_count": 0,
        "test_only_excluded_count": 0,
        "campaign_scope_error": "",
        "redacted_location_marker": REDACTED_LOCATION,
        "grants_operational_permission": False,
        "implies_approval": False,
        "implies_rights_clearance": False,
        "semantic_unavailable_reason": (
            "no published semantic index and lexical fallback not permitted by the request"),
    }


def _semantic_channel(query, query_vector=None):
    """Resolve the semantic scoring channel for this query WITHOUT any external call.

    `query_vector` is the DIP-1C-2 seam: when a consented, POST-only, externally-embedded
    query vector is supplied by `encode_semantic_query`, it is scored directly here. Ranking
    stays a pure function — the external call lives entirely in the query-embedding service,
    never in this module. When it is absent (every GET), behaviour is exactly DIP-1C-1's.

    The query is embedded with the *published generation's* encoder. The OpenAI encoder
    refuses to construct without an explicit external-transfer confirmation — which a search
    request never carries — so a browser semantic query against an OpenAI index cannot call
    out: it simply reports the index unusable-for-query and the caller falls back to lexical.
    A stub-encoder index (tests) embeds the query locally and engages normally.

    Returns (scores_by_id, engaged, index_status, generation).
    """
    if query.ranking == RANK_LEXICAL:
        return {}, False, "LEXICAL_ONLY", None
    status, generation = index_status()
    if generation is None:
        return {}, False, status, None            # UNAVAILABLE — no published index
    if query_vector is not None:
        # a pre-embedded, consented query vector (DIP-1C-2 POST path). No call happens here.
        if len(query_vector) != generation.vector_dimension:
            return {}, False, status, generation
        return semantic_scores(query_vector)[0], True, status, generation
    try:
        encoder = get_encoder(generation.provider)   # external_transfer_confirmed=False
        embedded = encoder.encode([query.query or ""])[0]
        if len(embedded) != generation.vector_dimension:
            return {}, False, status, generation
        scores, _ = semantic_scores(embedded)
    except Exception:
        # cannot embed the query without an external call, or any other issue → fail closed
        return {}, False, status, generation
    return scores, True, status, generation


def execute_search(query, *, at=None, query_vector=None) -> dict:
    """Run a validated SearchQuery. Read-only: writes nothing, grants nothing.

    `query_vector` (DIP-1C-2) carries an already-embedded, consent-gated query from the
    POST path. Ranking here is pure — it never calls a provider.
    """
    try:
        entries = campaign_entries_by_candidate()
        scope_error = ""
    except CampaignScopeError as exc:
        entries, scope_error = {}, str(exc)

    semantic_by_id, semantic_engaged, idx_status, generation = _semantic_channel(
        query, query_vector=query_vector)
    # a SEMANTIC-only request with no usable index and no fallback fails clearly
    if (query.ranking == RANK_SEMANTIC and not semantic_engaged
            and not query.allow_lexical_fallback):
        return _semantic_unavailable_result(query, idx_status)

    items = _base_queryset()
    if query.item_kinds:
        items = items.filter(item_kind__in=query.item_kinds)

    rows, withheld, test_only_excluded = [], 0, 0
    for item in items:
        retrieval = evaluate_retrieval_readiness(item, at=at)
        candidate = _candidate_for(item)
        entry = entries.get(str(candidate.pk)) if candidate else None

        review_readiness = None
        if candidate is not None:
            try:
                review_readiness = assess_readiness(
                    candidate, wave=entry["wave"] if entry else None)
            except CampaignScopeError:
                review_readiness = None

        membership = _membership(item, entry, retrieval)
        if membership == TEST_ONLY_EXCLUDED:
            test_only_excluded += 1
            continue                       # test records are never search results
        if membership == WITHHELD_IDENTITY:
            withheld += 1
            continue                       # unresolvable identity is withheld, not guessed
        if query.scope == CAMPAIGN_SCOPE and entry is None:
            continue

        dataset = _dataset_identifier(item)
        if query.dataset_identifiers and dataset not in query.dataset_identifiers:
            continue
        if query.waves and (entry is None or entry["wave"] not in query.waves):
            continue
        if query.review_types and (
                candidate is None or candidate.review_type not in query.review_types):
            continue
        if query.readiness_states and (
                review_readiness is None
                or review_readiness.overall not in query.readiness_states):
            continue
        if query.blocker_codes and (
                review_readiness is None
                or not set(query.blocker_codes) & set(review_readiness.blocker_codes)):
            continue
        if query.integrity_states and (
                review_readiness is None
                or review_readiness.integrity not in query.integrity_states):
            continue
        if query.rights_states and (
                review_readiness is None
                or review_readiness.rights_evidence not in query.rights_states):
            continue
        if query.technical_states and (
                review_readiness is None
                or review_readiness.technical_evidence not in query.technical_states):
            continue
        if query.product_family_labels and (
                _product_family_label(item) not in query.product_family_labels):
            continue

        fact_labels, machine_labels = _labels(item)
        assertions = read_published_assertions(item)
        human_labels = [
            current.get("label", "") for current in
            (assertions.current_by_domain or {}).values()
            if isinstance(current, dict)]
        if query.candidate_labels and not (
                set(query.candidate_labels) & set(machine_labels + human_labels)):
            continue

        display = _display(item)
        score = score_item(
            query.query, external_key=item.external_key, display_label=display,
            fact_labels=fact_labels, machine_labels=machine_labels,
            human_labels=human_labels)
        semantic_score = (
            semantic_by_id.get(str(item.pk)) if semantic_engaged else None)
        # what counts as a match depends on the ranking channel. LEXICAL is DIP-1B-6
        # exactly; SEMANTIC matches on a semantic score; HYBRID matches on either.
        if query.ranking == RANK_SEMANTIC:
            matched = semantic_score is not None
        elif query.ranking == RANK_HYBRID:
            matched = score.matched or semantic_score is not None
        else:
            matched = score.matched
        if not matched:
            continue

        # SEMANTIC orders on the semantic score ALONE (ranker 1.1); the lexical score is
        # still reported below as a diagnostic but must not shift semantic-only ordering.
        blended = blended_score(
            score.score, semantic_score, use_semantic=semantic_engaged,
            rank_mode=query.ranking)
        reasons = merge_reasons(
            score.reasons, semantic_score, use_semantic=semantic_engaged)

        # Mode is a hard gate, applied AFTER matching so reviewer mode can still show a
        # blocked item with its blockers, while operational modes exclude it entirely.
        # Semantic similarity NEVER bypasses this — it is only ordering.
        if query.mode == OPERATIONAL_RETRIEVAL and not retrieval.retrieval_allowed:
            continue
        if query.mode == AUTOMATIC_USE and not retrieval.automatic_use_allowed:
            continue

        governance = read_published_governance(item)
        rows.append({
            "corpus_item_id": str(item.pk),
            "external_key": item.external_key,
            "item_kind": item.item_kind,
            "display_label": display,
            "dataset_identifier": dataset,
            # lexical and semantic scores reported SEPARATELY; the blend is only ordering
            "match_score": blended,
            "final_hybrid_score": blended,
            "lexical_score": score.score,
            "semantic_score": semantic_score,
            "match_reasons": reasons,
            "campaign_membership": membership,
            "wave": entry["wave"] if entry else "",
            "readiness_state": review_readiness.overall if review_readiness else "",
            "blocker_codes": list(
                review_readiness.blocker_codes) if review_readiness else [],
            "rights_state": review_readiness.rights_evidence if review_readiness else "",
            "identity_state": (
                review_readiness.identity_evidence if review_readiness else ""),
            "evidence_integrity_state": (
                review_readiness.integrity if review_readiness else ""),
            "technical_state": _technical_label(item),
            "human_assertion_status": assertions.state,
            "governance_status": governance.state,
            # the two operational questions, answered separately and independently
            "retrieval": {
                "allowed": retrieval.retrieval_allowed,
                "reason_code": retrieval.permission_reason_codes["RETRIEVAL"]},
            "automatic_use": {
                "allowed": retrieval.automatic_use_allowed,
                "reason_code": retrieval.permission_reason_codes["AUTOMATIC_USE"]},
            "permission_reason_codes": dict(retrieval.permission_reason_codes),
            "source_hash_summary": _source_hash_summary(item),
            "detail_url": reverse("intelligence:corpus-detail", args=[item.pk]),
            "legacy_signals": _legacy_signal_note(),
            "prohibited_use_warnings": list(_warnings(review_readiness, retrieval)),
            # deterministic order: blended score desc, then canonical UUID
            "_sort": ((str(item.pk),) if query.order_by == ORDER_BY_IDENTITY
                      else (-blended, str(item.pk))),
        })

    rows.sort(key=lambda r: r["_sort"])
    for row in rows:
        row.pop("_sort")
    total = len(rows)
    start = (query.page - 1) * query.limit
    page_rows = rows[start:start + query.limit]

    ranking_engaged = RANK_HYBRID if (
        semantic_engaged and query.ranking == RANK_HYBRID) else (
        RANK_SEMANTIC if semantic_engaged else RANK_LEXICAL)
    return {
        "schema_version": SEARCH_SCHEMA,
        "result_schema_version": RESULT_SCHEMA,
        "ranker_version": RANKER_VERSION,
        "hybrid_ranker_version": HYBRID_RANKER_VERSION,
        # honest about what actually ran: true only when a real semantic channel engaged
        "ranking_is_semantic": semantic_engaged,
        "ranking_requested": query.ranking,
        "ranking_engaged": ranking_engaged,
        "semantic_index_status": idx_status,
        # a lexical result that was ASKED to be semantic is labelled, never mislabelled
        "result_label": ("LEXICAL_ONLY"
                         if query.ranking != RANK_LEXICAL and not semantic_engaged
                         else ranking_engaged),
        "semantic_generation_id": str(generation.pk) if generation else None,
        "mode": query.mode,
        "scope": query.scope,
        "query": query.as_dict(),
        "total_results": total,
        "page": query.page,
        "limit": query.limit,
        "results": page_rows,
        "withheld_identity_count": withheld,
        "test_only_excluded_count": test_only_excluded,
        "campaign_scope_error": scope_error,
        "redacted_location_marker": REDACTED_LOCATION,
        # stated, never assumed
        "grants_operational_permission": False,
        "implies_approval": False,
        "implies_rights_clearance": False,
    }


__all__ = [
    "RESULT_SCHEMA", "execute_search", "_bounded_location",
    "REVIEWER_CANDIDATE_SEARCH",
]
