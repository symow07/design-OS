from __future__ import annotations

import json
import uuid
from collections import Counter

from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from apps.accounts import authz_policy as authz
from apps.accounts.attestation import CATEGORY_ACTION
from apps.accounts.authorization import authorize_actor, require_reviewer_action
from apps.accounts.models import DecisionEvent
from .evidence_integrity import EvidenceIntegrityResolver
from .artwork_preview import (
    PREVIEW_CONTENT_TYPE, PreviewError, preview_cards, render_preview,
)
from .evidence_labels import labelled_evidence
from .evidence_readiness import evidence_readiness
from .governance import (
    CANONICAL_BRAND_ASSET, CANONICAL_SCOPE_TYPES, FINALIZE_ACTION,
    PALETTE_SCOPE_TYPES, PRIMARY_BRAND_PALETTE,
    REQUIRED_ATTESTATION_CATEGORIES, REVOKE_ACTION, SCOPE_IDENTIFIER_FIELDS,
    GovernanceAuthorizationDenied, GovernanceError, finalize_governance_decision,
    record_governance_attestation, revoke_governance_decision,
)
from .governance_reader import read_published_governance
from .legacy_signals import LEGACY_SIGNAL_NON_AUTHORITATIVE
from .identity import IDENTITY_ALIAS_PROVENANCE
from .models import (
    BrandCandidateProfile, CorpusItem, DesignAssetProfile, EvidenceReference,
    FontFaceProfile,
    HistoricalDesignProfile, ImportBatch, OperationalPermissionProjection,
    ProvenanceRecord, ReviewCandidate,
)
from .permissions import evaluate_operational_permission
from .process_revision import process_revision_banner
from .projection_reader import (
    published_projection_statuses, read_published_assertions,
)
from .review_campaign import (
    WAVES, CampaignScopeError, campaign_entries_by_candidate,
)
from .review_packet import build_review_packet
from .review_readiness import (
    OVERALL_STATES, READINESS_BLOCKERS, assess_readiness,
)
from .search_contract import (
    CORPUS_SCOPE, DATASET_IDENTIFIERS, INTEGRITY_STATES, ITEM_KINDS, RANK_HYBRID,
    RANK_SEMANTIC, RANKINGS, RIGHTS_STATES, SEARCH_MODES, SEARCH_SCOPES,
    TECHNICAL_STATES, SearchContractError, build_search_query,
)
from .search_service import execute_search
from .semantic_index import STATUS_CURRENT, index_status
from .semantic_query import (
    GENERAL_CONCEPT, SEMANTIC_FACETS, SemanticQueryError, build_semantic_query,
    encode_semantic_query,
)
from .review_services import (
    DOMAIN_SCHEMAS, AssertionValidationError, ReviewAuthorizationDenied,
    ReviewConflict, claim_review_candidate, correct_intelligence_classification,
    record_intelligence_classification,
    record_intelligence_evidence_assessment, release_review_candidate,
)
from .human_semantic_metadata import (
    METADATA_ASSERTION_DOMAIN, VOCABULARY_FIELDS, VOCABULARY_VERSION,
)
from .metadata_history import (
    INVALID as HISTORY_INVALID, REVIEW_REQUIRED as HISTORY_REVIEW_REQUIRED,
    resolve_effective_assertion_from_verified_history,
)
from .semantic_metadata_scope import is_in_scope
from .semantic_metadata_service import (
    REVIEW_SCOPE_ID, correct_human_semantic_metadata, record_human_semantic_metadata,
    resolve_human_semantic_metadata_conflict,
)

SEARCH_MAX = 100
PAGE_SIZE = 50


def _base_queryset():
    return (CorpusItem.objects.select_related(
        "historical_design_profile", "design_asset_profile", "font_face_profile",
        "brand_candidate_profile")
        .prefetch_related(
            "evidence_references__source_artifact", "provenance_records",
            "observed_facts__evidence_reference", "machine_classifications",
            "import_records__import_batch", "permission_projections"))


def _display(item):
    if hasattr(item, "historical_design_profile"):
        return item.historical_design_profile.display_title
    if hasattr(item, "font_face_profile"):
        return item.font_face_profile.family_name
    if hasattr(item, "brand_candidate_profile"):
        return (item.brand_candidate_profile.observed_brand_label
                or item.brand_candidate_profile.get_candidate_kind_display())
    if hasattr(item, "design_asset_profile"):
        return item.design_asset_profile.candidate_source_key
    return item.external_key


def _readiness(item):
    if hasattr(item, "historical_design_profile"):
        return item.historical_design_profile.audit_status
    if hasattr(item, "design_asset_profile"):
        return item.design_asset_profile.technical_readiness
    if hasattr(item, "font_face_profile"):
        return item.font_face_profile.technical_suitability_state
    if hasattr(item, "brand_candidate_profile"):
        return item.brand_candidate_profile.candidate_status
    return ""


def _candidate_type(item):
    if hasattr(item, "design_asset_profile"):
        return item.design_asset_profile.candidate_asset_kind
    if hasattr(item, "brand_candidate_profile"):
        return item.brand_candidate_profile.candidate_kind
    return ""


def _item_governance_type(item):
    profile = getattr(item, "brand_candidate_profile", None)
    if profile is None:
        return None
    if item.item_kind == CorpusItem.Kind.BRAND_PALETTE:
        return PRIMARY_BRAND_PALETTE
    if item.item_kind == CorpusItem.Kind.BRAND_ASSET:
        return CANONICAL_BRAND_ASSET
    return None


def _governance_context(request, item, integrity, readiness, *, controls=False):
    governance_type = _item_governance_type(item)
    if governance_type is None:
        return None
    published = read_published_governance(item)
    required = REQUIRED_ATTESTATION_CATEGORIES[governance_type]
    subject = ("CorpusItem", str(item.pk))
    can_attest = {
        category: (
            readiness["governance_ready"]
            and authorize_actor(
                request.user, CATEGORY_ACTION[category], subject=subject).allowed)
        for category in required
    }
    can_finalize = (
        controls and readiness["governance_ready"]
        and authorize_actor(
            request.user, FINALIZE_ACTION[governance_type], subject=subject).allowed)
    can_revoke = (
        controls and authorize_actor(
            request.user, REVOKE_ACTION[governance_type], subject=subject).allowed)
    return {
        "governance_type": governance_type,
        "required_categories": required,
        "scope_types": sorted(
            CANONICAL_SCOPE_TYPES if governance_type == CANONICAL_BRAND_ASSET
            else PALETTE_SCOPE_TYPES),
        "integrity": integrity,
        "published": published,
        "controls_available": controls and readiness["governance_ready"],
        "eligibility_reasons": readiness["governance_eligibility_reasons"],
        "can_attest": can_attest,
        "can_finalize": can_finalize,
        "can_revoke": can_revoke,
    }


@require_GET
@require_reviewer_action(authz.REVIEW_EVIDENCE)
def corpus_list(request):
    search = request.GET.get("q", "").strip()
    source = request.GET.get("source", "").strip()
    if len(search) > SEARCH_MAX or len(source) > SEARCH_MAX:
        return HttpResponseBadRequest("search and source filters are limited to 100 chars")
    queryset = _base_queryset().order_by("item_kind", "external_key")
    kind = request.GET.get("kind", "")
    if kind:
        if kind not in CorpusItem.Kind.values:
            return HttpResponseBadRequest("unknown item kind")
        queryset = queryset.filter(item_kind=kind)
    if search:
        queryset = queryset.filter(
            Q(external_key__icontains=search)
            | Q(historical_design_profile__display_title__icontains=search)
            | Q(font_face_profile__family_name__icontains=search)
            | Q(font_face_profile__postscript_name__icontains=search)
            | Q(brand_candidate_profile__observed_brand_label__icontains=search)
            | Q(design_asset_profile__candidate_source_key__icontains=search))
    if source:
        queryset = queryset.filter(
            Q(evidence_references__source_artifact__source_identifier__icontains=source)
            | Q(evidence_references__source_artifact__sha256__istartswith=source)
            | Q(import_records__stable_source_record_key__icontains=source))
    batch = request.GET.get("batch", "")
    if batch:
        try:
            batch_id = uuid.UUID(batch)
        except ValueError:
            return HttpResponseBadRequest("invalid import batch")
        queryset = queryset.filter(import_records__import_batch_id=batch_id)
    readiness = request.GET.get("readiness", "")
    if readiness:
        queryset = queryset.filter(
            Q(historical_design_profile__audit_status=readiness)
            | Q(design_asset_profile__technical_readiness=readiness)
            | Q(font_face_profile__technical_suitability_state=readiness)
            | Q(brand_candidate_profile__candidate_status=readiness))
    candidate_type = request.GET.get("candidate_type", "")
    if candidate_type:
        queryset = queryset.filter(
            Q(design_asset_profile__candidate_asset_kind=candidate_type)
            | Q(brand_candidate_profile__candidate_kind=candidate_type))
    queryset = queryset.distinct()
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("page"))
    projection_statuses = published_projection_statuses(page.object_list)
    integrity_resolver = EvidenceIntegrityResolver()
    for item in page.object_list:
        item.browser_display = _display(item)
        item.browser_readiness = _readiness(item)
        item.browser_candidate_type = _candidate_type(item)
        item.browser_projection_status = projection_statuses[item.pk]
        item.browser_permission = evaluate_operational_permission(
            item, OperationalPermissionProjection.Permission.RETRIEVAL,
        )
        item.browser_hashes = sorted({e.source_artifact.sha256
                                      for e in item.evidence_references.all()})
        integrity = integrity_resolver.evaluate(item)
        item.browser_integrity_warning = (
            integrity if integrity.blocks_evidence_dependent_claims else None)
    return render(request, "intelligence/corpus_list.html", {
        "page": page,
        "kinds": CorpusItem.Kind.choices,
        "batches": ImportBatch.objects.order_by("-started_at")[:50],
        "readiness_values": sorted(set(
            HistoricalDesignProfile.AuditStatus.values
            + DesignAssetProfile.Readiness.values
            + FontFaceProfile.Suitability.values
            + BrandCandidateProfile.Status.values)),
        "candidate_types": sorted(set(
            DesignAssetProfile.CandidateKind.values
            + BrandCandidateProfile.CandidateKind.values)),
        "filters": request.GET,
    })


@require_GET
@require_reviewer_action(
    authz.REVIEW_EVIDENCE,
    subject_resolver=lambda request, item_id: ("CorpusItem", str(item_id)),
)
def corpus_detail(request, item_id):
    item = _base_queryset().filter(pk=item_id).first()
    if item is None:
        alias = ProvenanceRecord.objects.select_related("corpus_item").filter(
            provenance_type=IDENTITY_ALIAS_PROVENANCE,
            acquisition_reference=f"legacy-corpus-item:{item_id}",
            corpus_item__isnull=False,
        ).first()
        if alias:
            return redirect(
                "intelligence:corpus-detail", item_id=alias.corpus_item_id,
                permanent=True,
            )
        raise Http404("corpus item not found")
    assertion_result = read_published_assertions(item)
    permission_results = [
        evaluate_operational_permission(item, permission_type)
        for permission_type in OperationalPermissionProjection.Permission.values
    ]
    integrity = EvidenceIntegrityResolver().evaluate(item)
    readiness = evidence_readiness(item, integrity)
    integrity_warning = integrity if integrity.blocks_evidence_dependent_claims else None
    return render(request, "intelligence/corpus_detail.html", {
        "item": item,
        "display_label": _display(item),
        "assertion_result": assertion_result,
        "permission_results": permission_results,
        "legacy_signal_label": LEGACY_SIGNAL_NON_AUTHORITATIVE,
        "integrity_warning": integrity_warning,
        "evidence_readiness": readiness,
        "governance": _governance_context(request, item, integrity, readiness),
    })


def _review_subject(request, candidate_id, **extra):
    """The authorization subject is always the candidate's CorpusItem. Extra view kwargs
    (e.g. an evidence id on the preview route) never influence it."""
    item_id = ReviewCandidate.objects.filter(pk=candidate_id).values_list(
        "corpus_item_id", flat=True).first()
    return "CorpusItem", str(item_id or candidate_id)


def _review_queryset():
    return (ReviewCandidate.objects.select_related(
        "corpus_item", "assigned_to", "source_import_batch",
        "corpus_item__historical_design_profile",
        "corpus_item__design_asset_profile", "corpus_item__font_face_profile",
        "corpus_item__brand_candidate_profile")
        .prefetch_related(
            "corpus_item__evidence_references__source_artifact",
            "corpus_item__machine_classifications",
            "corpus_item__observed_facts"))


# The machine candidate-kind vocabulary, derived from the models so it cannot drift.
# It spans two profile tables and is a MACHINE LABEL: a display filter only. It never
# feeds wave assignment or readiness — lineage decides those. (The live corpus proves the
# point: two brand rows are machine-labelled PALETTE, but only one is palette lineage.)
def _machine_candidate_kinds():
    return tuple(sorted(
        {c[0] for c in DesignAssetProfile._meta.get_field(
            "candidate_asset_kind").choices}
        | {c[0] for c in BrandCandidateProfile._meta.get_field(
            "candidate_kind").choices}))


def _candidate_kind_by_item():
    kinds = {}
    for item_id, kind in DesignAssetProfile.objects.values_list(
            "corpus_item_id", "candidate_asset_kind"):
        kinds[item_id] = kind
    for item_id, kind in BrandCandidateProfile.objects.values_list(
            "corpus_item_id", "candidate_kind"):
        kinds[item_id] = kind
    return kinds


def _semantic_index_context():
    """What the UI must show about the published index. Read-only; no external call."""
    status, generation = index_status()
    return {
        "status": status,
        "generation_id": str(generation.pk) if generation else "",
        "provider": generation.provider if generation else "",
        "model_identifier": generation.model_identifier if generation else "",
        "corpus_manifest_hash": generation.corpus_manifest_hash if generation else "",
        "vector_dimension": generation.vector_dimension if generation else None,
        "available": generation is not None and status == STATUS_CURRENT,
    }


@require_GET
@require_reviewer_action(authz.VIEW_INTELLIGENCE_REVIEW_QUEUE)
def intelligence_search(request):
    """Internal reviewer candidate search. Read-only; grants nothing.

    Reuses the canonical review-access authorization action — this is not a second
    reviewer identity system. Being able to search candidates never implies operational
    retrieval: the operational modes below apply the permission gate and locally return
    nothing, which is the correct fail-closed result.
    """
    raw = {
        "query": request.GET.get("query", ""),
        "mode": request.GET.get("mode", ""),
        "scope": request.GET.get("scope", ""),
        "order_by": request.GET.get("order_by", ""),
        "ranking": request.GET.get("ranking", ""),
        "limit": request.GET.get("limit", ""),
        "page": request.GET.get("page", ""),
    }
    for field, param in (
            ("item_kinds", "item_kind"), ("dataset_identifiers", "dataset_identifier"),
            ("waves", "wave"), ("review_types", "review_type"),
            ("readiness_states", "readiness"), ("blocker_codes", "blocker"),
            ("integrity_states", "integrity"), ("rights_states", "rights"),
            ("technical_states", "technical")):
        values = [v for v in request.GET.getlist(param) if v]
        if values:
            raw[field] = values
    raw = {k: v for k, v in raw.items() if v not in ("", None)}
    try:
        query = build_search_query(raw)
    except SearchContractError as exc:
        # refuse an unhonourable query rather than quietly returning a different one
        return HttpResponseBadRequest(str(exc))
    results = execute_search(query)
    return render(request, "intelligence/search.html", {
        "search": results,
        "query": query,
        "filters": request.GET,
        "modes": SEARCH_MODES,
        "scopes": SEARCH_SCOPES,
        "item_kinds": ITEM_KINDS,
        "dataset_identifiers": DATASET_IDENTIFIERS,
        "waves": WAVES,
        "readiness_states": OVERALL_STATES,
        "readiness_blockers": READINESS_BLOCKERS,
        "integrity_states": INTEGRITY_STATES,
        "rights_states": RIGHTS_STATES,
        "technical_states": TECHNICAL_STATES,
        "rankings": RANKINGS,
        "facets": SEMANTIC_FACETS,
        "semantic_index": _semantic_index_context(),
        "posted": False,
    })


@require_POST
@require_reviewer_action(authz.VIEW_INTELLIGENCE_REVIEW_QUEUE)
def intelligence_semantic_search(request):
    """Interactive semantic/hybrid search — DIP-1C-2. POST-only, CSRF-protected.

    This is the ONLY view that can cause an outbound provider call, and it does so only
    after per-request consent. It is deliberately a separate endpoint: `/search/` stays
    strictly GET-only and performs no external call, so merely loading a page or applying
    filters can never transmit anything.

    Actor identity is server-derived from the session via the canonical authorization
    action; a role, actor, or authority claim in the request body is never read.
    """
    ranking = request.POST.get("ranking", RANK_SEMANTIC)
    if ranking not in (RANK_SEMANTIC, RANK_HYBRID):
        return HttpResponseBadRequest("semantic search requires ranking SEMANTIC or HYBRID")
    raw = {
        "query_text": request.POST.get("query_text", ""),
        "facet": request.POST.get("facet", "") or GENERAL_CONCEPT,
        "scope": request.POST.get("scope", "") or CORPUS_SCOPE,
        "limit": request.POST.get("limit", "") or 25,
        "generation_id": request.POST.get("generation_id", ""),
        "expected_corpus_hash": request.POST.get("expected_corpus_hash", ""),
        "confirm_external_query_transfer": request.POST.get(
            "confirm_external_query_transfer", ""),
    }
    for field, param in (("item_kinds", "item_kind"),
                         ("dataset_identifiers", "dataset_identifier")):
        values = [v for v in request.POST.getlist(param) if v]
        if values:
            raw[field] = values
    raw = {k: v for k, v in raw.items() if v not in ("", None)}
    try:
        semantic_query = build_semantic_query(raw)
    except SemanticQueryError as exc:
        return HttpResponseBadRequest(str(exc))

    # every precondition is checked before any external call; each failure is a bounded code
    embedding = encode_semantic_query(semantic_query)
    results, failure = None, embedding.failure_code
    if embedding.ok:
        search_query = build_search_query({
            "query": semantic_query.query_text,
            "ranking": ranking,
            "scope": semantic_query.scope,
            "limit": semantic_query.limit,
            "item_kinds": list(semantic_query.item_kinds) or None,
            "dataset_identifiers": list(semantic_query.dataset_identifiers) or None,
            "allow_lexical_fallback": False,   # a consented semantic request is not lexical
        })
        results = execute_search(search_query, query_vector=embedding.vector)
    return render(request, "intelligence/search.html", {
        "search": results,
        "semantic_failure_code": failure,
        "semantic_query": semantic_query,
        "posted": True,
        "filters": {},
        "modes": SEARCH_MODES,
        "scopes": SEARCH_SCOPES,
        "item_kinds": ITEM_KINDS,
        "dataset_identifiers": DATASET_IDENTIFIERS,
        "waves": WAVES,
        "readiness_states": OVERALL_STATES,
        "readiness_blockers": READINESS_BLOCKERS,
        "integrity_states": INTEGRITY_STATES,
        "rights_states": RIGHTS_STATES,
        "technical_states": TECHNICAL_STATES,
        "rankings": RANKINGS,
        "facets": SEMANTIC_FACETS,
        "semantic_index": _semantic_index_context(),
    })


@require_GET
@require_reviewer_action(authz.VIEW_INTELLIGENCE_REVIEW_QUEUE)
def review_queue(request):
    base = _review_queryset().order_by("-priority", "created_at")
    queryset = base
    status = request.GET.get("status", "")
    review_type = request.GET.get("review_type", "")
    assignment = request.GET.get("assignment", "")
    wave = request.GET.get("wave", "")
    readiness_state = request.GET.get("readiness", "")
    blocker = request.GET.get("blocker", "")
    integrity_state = request.GET.get("integrity", "")
    reviewer = request.GET.get("reviewer", "")
    candidate_kind = request.GET.get("candidate_kind", "")
    if status:
        if status not in ReviewCandidate.Status.values:
            return HttpResponseBadRequest("unknown workflow status")
        queryset = queryset.filter(workflow_status=status)
    if review_type:
        if review_type not in ReviewCandidate.ReviewType.values:
            return HttpResponseBadRequest("unknown review type")
        queryset = queryset.filter(review_type=review_type)
    if assignment == "mine":
        queryset = queryset.filter(assigned_to=request.user)
    elif assignment == "unassigned":
        queryset = queryset.filter(assigned_to__isnull=True)
    elif assignment:
        return HttpResponseBadRequest("unknown assignment filter")
    if reviewer:
        if len(reviewer) > 150:
            return HttpResponseBadRequest("reviewer filter is limited to 150 chars")
        queryset = queryset.filter(assigned_to__username=reviewer)
    # every filter validates against a bounded vocabulary: an unknown value is refused,
    # never silently ignored (a silently-dropped filter would show a reviewer a wider set
    # than they believe they are looking at)
    if wave and wave not in WAVES:
        return HttpResponseBadRequest("unknown campaign wave")
    if readiness_state and readiness_state not in OVERALL_STATES:
        return HttpResponseBadRequest("unknown readiness state")
    if blocker and blocker not in READINESS_BLOCKERS:
        return HttpResponseBadRequest("unknown blocker code")
    if candidate_kind and candidate_kind not in _machine_candidate_kinds():
        return HttpResponseBadRequest("unknown machine candidate kind")

    # Campaign membership is coordination metadata, and it fails closed: if the frozen
    # scope cannot be built (a retired or duplicated subject), we refuse to imply
    # membership rather than render a queue that quietly misstates the campaign.
    try:
        entries = campaign_entries_by_candidate()
        scope_error = ""
    except CampaignScopeError as exc:
        entries, scope_error = {}, str(exc)

    integrity_resolver = EvidenceIntegrityResolver()
    kinds = _candidate_kind_by_item()
    selected_ids = set(queryset.values_list("pk", flat=True))
    rows, counts, unreadable = [], Counter(), 0
    # Readiness is computed over the WHOLE queue, not the filtered set: the progress
    # summary below is a stable denominator that does not move when a reviewer narrows
    # their view. Filters change which cards you see, never how much work exists.
    for candidate in base:
        entry = entries.get(str(candidate.pk))
        integrity = integrity_resolver.evaluate(candidate.corpus_item)
        try:
            readiness = assess_readiness(
                candidate, wave=entry["wave"] if entry else None, integrity=integrity)
        except CampaignScopeError:
            # a candidate with no resolvable lineage: fail closed and count it as
            # unreadable rather than 500 the queue or invent a wave for it
            unreadable += 1
            continue
        counts[readiness.overall] += 1
        if candidate.pk not in selected_ids:
            continue
        if wave and (entry is None or entry["wave"] != wave):
            continue
        if readiness_state and readiness.overall != readiness_state:
            continue
        if blocker and blocker not in readiness.blocker_codes:
            continue
        if integrity_state and readiness.integrity != integrity_state:
            continue
        item_kind = kinds.get(candidate.corpus_item_id, "")
        if candidate_kind and item_kind != candidate_kind:
            continue
        candidate.review_display = _display(candidate.corpus_item)
        candidate.integrity_warning = (
            integrity if integrity.blocks_evidence_dependent_claims else None)
        candidate.readiness = readiness
        candidate.campaign_entry = entry
        candidate.machine_candidate_kind = item_kind
        rows.append(candidate)

    # deterministic: ties broken by primary key, so the same state always yields the same
    # order and the same "next" recommendation
    rows.sort(key=lambda c: (-c.priority, c.created_at, str(c.pk)))
    completed = base.filter(
        workflow_status=ReviewCandidate.Status.COMPLETED).count()
    total = base.count()
    # a recommendation of what to pick up next — never a claim, never an assignment
    next_candidate = next(
        (c for c in rows
         if c.workflow_status == ReviewCandidate.Status.OPEN
         and c.assigned_to_id is None), None)
    page = Paginator(rows, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "intelligence/review_queue.html", {
        "page": page,
        "statuses": ReviewCandidate.Status.choices,
        "review_types": ReviewCandidate.ReviewType.choices,
        "filters": request.GET,
        "waves": WAVES,
        "readiness_states": OVERALL_STATES,
        "readiness_blockers": READINESS_BLOCKERS,
        "machine_candidate_kinds": _machine_candidate_kinds(),
        "campaign_scope_error": scope_error,
        "unreadable_candidates": unreadable,
        "readiness_counts": dict(sorted(counts.items())),
        "review_tasks_completed": completed,
        "review_tasks_remaining": total - completed,
        "review_tasks_total": total,
        "next_candidate": next_candidate,
    })


@require_GET
@require_reviewer_action(
    authz.VIEW_INTELLIGENCE_REVIEW_QUEUE, subject_resolver=_review_subject)
def review_detail(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    item = candidate.corpus_item
    assertion_result = read_published_assertions(item)
    permission_results = [
        evaluate_operational_permission(item, permission_type)
        for permission_type in OperationalPermissionProjection.Permission.values
    ]
    domain, labels, _ = DOMAIN_SCHEMAS[candidate.review_type]
    integrity = EvidenceIntegrityResolver().evaluate(item)
    readiness = evidence_readiness(item, integrity)
    review_evidence = list(item.evidence_references.select_related(
        "source_artifact").filter(is_test_only=False).order_by("pk"))
    integrity_warning = integrity if integrity.blocks_evidence_dependent_claims else None
    # The bounded review packet. Read-only and non-fatal: a candidate outside the frozen
    # campaign is still reviewable through the existing workflow, it simply has no
    # campaign packet — so absence is reported, never faked.
    try:
        packet = build_review_packet(candidate)
        packet_error = ""
    except (ValueError, CampaignScopeError) as exc:
        packet, packet_error = None, str(exc)
    return render(request, "intelligence/review_detail.html", {
        "candidate": candidate,
        "item": item,
        "display_label": _display(item),
        "domain": domain,
        "labels": sorted(labels),
        "assertion_result": assertion_result,
        "permission_results": permission_results,
        "integrity_warning": integrity_warning,
        # NB: `evidence_readiness` (brand rights/identity dimensions) and `review_readiness`
        # (campaign coordination) are different things and must not be conflated
        "evidence_readiness": readiness,
        "review_packet": packet,
        "review_packet_error": packet_error,
        "review_readiness": packet["review_readiness"] if packet else None,
        "governance": _governance_context(
            request, item, integrity, readiness, controls=True),
        "semantic_metadata": _semantic_metadata_context(item, assertion_result),
        "process_revision": process_revision_banner(),
        # DIP-1C-5C-CORR-1: ONE labelled list for every evidence selector on this page, so
        # no form can drift back to a label that cannot distinguish two references.
        "labelled_evidence": labelled_evidence(review_evidence),
        # DIP-1C-6A: visual evidence. Status only — rendering happens per-image, so a slow
        # or failing source never blocks the page or hides the technical evidence.
        "visual_evidence": _visual_evidence(review_evidence),
    })


def _visual_evidence(references):
    """Preview cards keyed to the SAME references the selectors render, so a reviewer can
    match a picture to a checkbox."""
    cards = {card["evidence_reference_id"]: card for card in preview_cards(references)}
    return [{**cards[str(reference.pk)], "label": label, "reference": reference}
            for reference, label in labelled_evidence(references)]


def _semantic_metadata_context(item, assertion_result):
    """DIP-1C-5B reviewer-form context. Descriptive only — it carries no permission, no
    governance control, and no authority state.

    DIP-1C-5C-CORR-3: the correction target comes from the PUBLISHED projection when it is
    current, and otherwise from verified signed history. A stale read projection must never
    prevent correcting an event that demonstrably exists in the chain — and must never let
    the record form reappear and deepen the conflict.
    """
    current = (assertion_result.current_by_domain or {}).get(METADATA_ASSERTION_DOMAIN)
    history = [entry for entry in assertion_result.history
               if entry["domain"] == METADATA_ASSERTION_DOMAIN]
    references = list(EvidenceReference.objects.filter(
        corpus_item=item, is_test_only=False
    ).select_related("source_artifact").order_by("pk"))

    target_event_id = (current or {}).get("event_id", "")
    bundle = (current or {}).get("normalized_value") or {}
    resolved_from_history = False
    review_required_reason = ""
    conflict = None
    if assertion_result.state != "CURRENT":
        resolved = resolve_effective_assertion_from_verified_history(item)
        if resolved.has_effective:
            payload = resolved.event.payload
            target_event_id = resolved.event.event_id
            bundle = payload.get("metadata_bundle") or {}
            resolved_from_history = True
        elif resolved.state in (HISTORY_REVIEW_REQUIRED, HISTORY_INVALID):
            review_required_reason = resolved.reason
            conflict = _conflict_context(resolved, references)

    if conflict and conflict["bundles_identical"]:
        bundle = conflict["prefill_bundle"]
    selected = set(bundle_evidence_ids(target_event_id))
    return {
        "in_scope": is_in_scope(item),
        "review_scope_id": REVIEW_SCOPE_ID,
        "vocabulary_version": VOCABULARY_VERSION,
        "vocabulary_fields": [
            (field, [(term, term in (bundle.get(field) or [])) for term in terms])
            for field, terms in sorted(VOCABULARY_FIELDS.items())],
        "current": current,
        "current_event_id": target_event_id,
        "resolved_from_history": resolved_from_history,
        "review_required_reason": review_required_reason,
        "conflict": conflict,
        "prefill_notes": bundle.get("reviewer_notes", ""),
        "prefill_synonyms": "\n".join(bundle.get("search_synonyms") or []),
        "history": history,
        "evidence_references": [
            (reference, label, str(reference.pk) in selected)
            for reference, label in labelled_evidence(references)],
    }


def _conflict_context(resolved, references):
    """DIP-1C-5C-CORR-4: the multi-event conflict surface.

    Prefills the bundle ONLY when every active bundle is logically identical — otherwise a
    human must choose, and the form shows each active bundle rather than silently picking
    one. Evidence is always explicitly selectable: in the incident that motivated this, the
    duplicates agreed on descriptors and were both wrong about evidence.
    """
    if resolved.reason != "MULTIPLE_ACTIVE_METADATA_EVENTS" or not resolved.active_events:
        return None
    from .human_semantic_metadata import bundle_hash
    active = []
    bundles = []
    for event in resolved.active_events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        event_bundle = payload.get("metadata_bundle") or {}
        bundles.append(bundle_hash(event_bundle))
        active.append({
            "event_id": event.event_id,
            "sequence_number": event.sequence_number,
            "action": event.action,
            "created_at": event.created_at,
            "actor": event.actor.get_username() if event.actor else "",
            "role_used": event.role_used,
            "bundle": event_bundle,
            "evidence": [
                (reference, label)
                for reference, label in labelled_evidence(references)
                if str(reference.pk) in (payload.get("evidence_reference_ids") or [])],
        })
    identical = len(set(bundles)) == 1
    return {
        "active": active,
        "active_event_ids": [entry["event_id"] for entry in active],
        "bundles_identical": identical,
        "prefill_bundle": active[0]["bundle"] if identical else {},
        "resolution_reason": "DUPLICATE_ACTIVE_EVENTS_FROM_STALE_APPLICATION_PROCESS",
        "incident_type": "STALE_SERVER_DUPLICATE_RECORD_RECOVERY",
    }


def bundle_evidence_ids(event_id):
    """Evidence cited by the correction target, so the form can preselect exactly what the
    prior event cited rather than making the reviewer rebuild it from memory."""
    if not event_id:
        return ()
    event = DecisionEvent.objects.filter(event_id=event_id).first()
    if event is None or not isinstance(event.payload, dict):
        return ()
    return tuple(event.payload.get("evidence_reference_ids") or ())


def _semantic_metadata_payload(request, candidate):
    """Build the bundle from the controlled form. Any field the contract does not define is
    simply never read — and the service refuses unknown fields regardless."""
    bundle = {
        field: request.POST.getlist(f"metadata_{field}")
        for field in VOCABULARY_FIELDS
    }
    bundle["search_synonyms"] = [
        line for line in request.POST.get("metadata_search_synonyms", "").splitlines()
        if line.strip()]
    bundle["reviewer_notes"] = request.POST.get("metadata_reviewer_notes", "")
    return {
        "corpus_item_uuid": str(candidate.corpus_item_id),
        "bundle": bundle,
        "evidence_reference_ids": request.POST.getlist("evidence_reference_ids"),
        "review_scope_id": request.POST.get("review_scope_id", ""),
    }


@require_POST
@require_reviewer_action(
    authz.RECORD_HUMAN_SEMANTIC_METADATA, subject_resolver=_review_subject)
def review_record_semantic_metadata(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        record_human_semantic_metadata(
            user=request.user,
            payload=_semantic_metadata_payload(request, candidate))
    except (AssertionValidationError, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_POST
@require_reviewer_action(
    authz.CORRECT_HUMAN_SEMANTIC_METADATA, subject_resolver=_review_subject)
def review_correct_semantic_metadata(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        payload = _semantic_metadata_payload(request, candidate)
        payload["supersedes_event_id"] = request.POST.get("supersedes_event_id", "")
        correct_human_semantic_metadata(user=request.user, payload=payload)
    except (AssertionValidationError, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_GET
@require_reviewer_action(authz.REVIEW_EVIDENCE, subject_resolver=_review_subject)
def review_evidence_preview(request, candidate_id, evidence_id):
    """Stream ONE generated PNG for one evidence reference of this candidate.

    Read-only in every sense: it writes no event, projection, permission or candidate state,
    and it never touches the source. The original bytes are never served — only a rendered
    preview — and the evidence reference must belong to *this* candidate's item, so a
    reference id from elsewhere cannot be used to reach an unrelated source.
    """
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    reference = EvidenceReference.objects.select_related("source_artifact").filter(
        pk=evidence_id, corpus_item=candidate.corpus_item, is_test_only=False).first()
    if reference is None:
        raise Http404("evidence reference not found for this candidate")
    try:
        payload, _identity = render_preview(reference)
    except PreviewError as exc:
        # a status, never a path or a stack trace
        return HttpResponse(exc.status, status=422, content_type="text/plain")
    response = HttpResponse(payload, content_type=PREVIEW_CONTENT_TYPE)
    response["Content-Length"] = str(len(payload))
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=300"
    response["Referrer-Policy"] = "no-referrer"
    return response


@require_POST
@require_reviewer_action(
    authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT, subject_resolver=_review_subject)
def review_resolve_semantic_metadata_conflict(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        payload = _semantic_metadata_payload(request, candidate)
        payload.update({
            "resolved_event_ids": request.POST.getlist("resolved_event_ids"),
            "resolution_reason": request.POST.get("resolution_reason", ""),
            "incident_type": request.POST.get("incident_type", ""),
            "reviewer_explanation": request.POST.get("reviewer_explanation", ""),
        })
        resolve_human_semantic_metadata_conflict(user=request.user, payload=payload)
    except (AssertionValidationError, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


def _review_bad_request(exc):
    return HttpResponseBadRequest(str(exc))


def _governance_error(exc):
    if isinstance(exc, GovernanceAuthorizationDenied):
        raise PermissionDenied(str(exc))
    return HttpResponseBadRequest(str(exc))


def _governance_scope_from_post(request):
    scope_type = request.POST.get("scope_type", "")
    raw = {"scope_type": scope_type}
    identifier_field = SCOPE_IDENTIFIER_FIELDS.get(scope_type.strip().upper())
    if identifier_field:
        raw[identifier_field] = request.POST.get("scope_identifier", "")
    elif request.POST.get("scope_identifier", "").strip():
        raise GovernanceError(
            "scope_identifier is not permitted for this scope_type")
    return raw


def _strict_governance_post(request, allowed):
    supplied = set(request.POST) - {"csrfmiddlewaretoken"}
    unexpected = supplied - set(allowed)
    if unexpected:
        raise GovernanceError(
            f"unexpected governance form fields: {sorted(unexpected)}")


@require_POST
def governance_attest(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        _strict_governance_post(request, {
            "governance_type", "scope_type", "scope_identifier",
            "attestation_category", "evidence_reference_ids", "review_expiry",
        })
        review_expiry = parse_datetime(request.POST.get("review_expiry", ""))
        if review_expiry is None or not timezone.is_aware(review_expiry):
            raise GovernanceError("review_expiry must be aware ISO-8601")
        record_governance_attestation(
            user=request.user, corpus_item_id=str(candidate.corpus_item_id),
            governance_type=request.POST.get("governance_type", ""),
            raw_scope=_governance_scope_from_post(request),
            attestation_category=request.POST.get("attestation_category", ""),
            evidence_reference_ids=request.POST.getlist("evidence_reference_ids"),
            review_expiry=review_expiry)
    except GovernanceError as exc:
        return _governance_error(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_POST
def governance_finalize(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        _strict_governance_post(request, {
            "governance_type", "scope_type", "scope_identifier",
            "attestation_event_ids", "supersedes_final_event_id",
        })
        finalize_governance_decision(
            user=request.user, corpus_item_id=str(candidate.corpus_item_id),
            governance_type=request.POST.get("governance_type", ""),
            raw_scope=_governance_scope_from_post(request),
            attestation_event_ids=request.POST.getlist("attestation_event_ids"),
            supersedes_final_event_id=(
                request.POST.get("supersedes_final_event_id") or None))
    except GovernanceError as exc:
        return _governance_error(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_POST
def governance_revoke(request, candidate_id, event_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        _strict_governance_post(request, {"reason"})
        target = DecisionEvent.objects.filter(event_id=event_id).first()
        if (target is None or not isinstance(target.payload, dict)
                or target.payload.get("selected_corpus_item_id")
                != str(candidate.corpus_item_id)):
            raise GovernanceError("revocation target does not belong to candidate")
        revoke_governance_decision(
            user=request.user, final_event_id=event_id,
            reason=request.POST.get("reason", ""))
    except GovernanceError as exc:
        return _governance_error(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_POST
@require_reviewer_action(
    authz.CLAIM_INTELLIGENCE_REVIEW, subject_resolver=_review_subject)
def review_claim(request, candidate_id):
    try:
        claim_review_candidate(user=request.user, candidate_id=candidate_id)
    except (ReviewCandidate.DoesNotExist, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_POST
@require_reviewer_action(
    authz.CLAIM_INTELLIGENCE_REVIEW, subject_resolver=_review_subject)
def review_release(request, candidate_id):
    try:
        release_review_candidate(user=request.user, candidate_id=candidate_id)
    except (ReviewCandidate.DoesNotExist, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


def _classification_form_payload(request, candidate):
    try:
        normalized = json.loads(request.POST.get("normalized_value", "{}"))
    except json.JSONDecodeError as exc:
        raise AssertionValidationError("normalized_value is not valid JSON") from exc
    return {
        "corpus_item_uuid": str(candidate.corpus_item_id),
        "review_candidate_uuid": str(candidate.pk),
        "classification_domain": request.POST.get("classification_domain", ""),
        "classification_label": request.POST.get("classification_label", ""),
        "normalized_value": normalized,
        "explanation": request.POST.get("explanation", ""),
        "evidence_reference_ids": request.POST.getlist("evidence_reference_ids"),
        "machine_classification_ids": request.POST.getlist(
            "machine_classification_ids"),
    }


@require_POST
@require_reviewer_action(
    authz.RECORD_INTELLIGENCE_CLASSIFICATION, subject_resolver=_review_subject)
def review_classify(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        record_intelligence_classification(
            user=request.user, payload=_classification_form_payload(request, candidate))
    except (AssertionValidationError, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_POST
@require_reviewer_action(
    authz.CORRECT_INTELLIGENCE_CLASSIFICATION, subject_resolver=_review_subject)
def review_correct(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        payload = _classification_form_payload(request, candidate)
        payload["supersedes_event_id"] = request.POST.get("supersedes_event_id", "")
        correct_intelligence_classification(user=request.user, payload=payload)
    except (AssertionValidationError, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


def _assessment_payload(request, candidate, assessment=None):
    return {
        "corpus_item_uuid": str(candidate.corpus_item_id),
        "review_candidate_uuid": str(candidate.pk),
        "assessment": assessment or request.POST.get("assessment", ""),
        "explanation": request.POST.get("explanation", ""),
        "evidence_reference_ids": request.POST.getlist("evidence_reference_ids"),
    }


@require_POST
@require_reviewer_action(
    authz.RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT,
    subject_resolver=_review_subject)
def review_assess_evidence(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        record_intelligence_evidence_assessment(
            user=request.user, payload=_assessment_payload(request, candidate))
    except (AssertionValidationError, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)


@require_POST
@require_reviewer_action(
    authz.REQUEST_INTELLIGENCE_CLARIFICATION, subject_resolver=_review_subject)
def review_request_clarification(request, candidate_id):
    candidate = _review_queryset().filter(pk=candidate_id).first()
    if candidate is None:
        raise Http404("review candidate not found")
    try:
        record_intelligence_evidence_assessment(
            user=request.user,
            payload=_assessment_payload(
                request, candidate, assessment="CLARIFICATION_REQUIRED"))
    except (AssertionValidationError, ReviewConflict,
            ReviewAuthorizationDenied) as exc:
        return _review_bad_request(exc)
    return redirect("intelligence:review-detail", candidate_id=candidate_id)
