"""Retrieval-readiness reporting — DIP-1B-6 (`retrieval_readiness_report/1.0`).

Reports five **different and non-substitutable** populations:

    discoverable for review → eligible for retrieval → eligible for automatic use
                            → eligible for export → eligible for production

These are not stages of one percentage. An item discoverable for review is not "80% of the
way" to production; it is simply visible to a human. Collapsing them into a single
readiness number would imply that review progress is use eligibility. It is not — so this
report has no combined figure, by design.

Read-only: writes nothing, grants nothing.
"""
from __future__ import annotations

from collections import Counter

from .governance_reader import read_published_governance
from .dataset_identifiers import DIP1B_CURATED_ASSET_EXPANSION_DATASET
from .models import (
    CorpusItem, DesignAssetProfile, GovernanceDecisionProjection,
    OperationalPermissionProjection as Projection,
)
from .retrieval_readiness import evaluate_retrieval_readiness
from .review_campaign import CampaignScopeError, campaign_entries_by_candidate
from .review_readiness import assess_readiness
from .search_service import _candidate_for, _dataset_identifier, _is_test_only

REPORT_SCHEMA = "retrieval_readiness_report/1.0"


def _projection_health(at=None):
    """Stale and invalid projections counted from the projections themselves."""
    from apps.accounts.models import DecisionChainHead
    head = DecisionChainHead.objects.filter(pk=1).first()
    current = (head.terminal_event_hash or None) if head else None
    stale = invalid = 0
    for projection in Projection.objects.all():
        if projection.source_decision_event_id is None:
            invalid += 1
            continue
        if projection.projected_chain_head_hash != current:
            stale += 1
    return stale, invalid


def build_retrieval_readiness_report(*, at=None) -> dict:
    try:
        entries = campaign_entries_by_candidate()
        scope_error = ""
    except CampaignScopeError as exc:
        entries, scope_error = {}, str(exc)

    counts = Counter()
    by_kind = Counter()
    by_dataset = Counter()

    for item in CorpusItem.objects.select_related(
            "historical_design_profile", "design_asset_profile",
            "font_face_profile", "brand_candidate_profile"):
        readiness = evaluate_retrieval_readiness(item, at=at)
        if _is_test_only(item):
            counts["test_only_excluded"] += 1
            continue
        if not readiness.candidate_review_visible:
            counts["withheld_identity"] += 1
            continue

        counts["reviewer_search_visible"] += 1
        by_kind[item.item_kind] += 1
        dataset = _dataset_identifier(item)
        if dataset:
            by_dataset[dataset] += 1

        candidate = _candidate_for(item)
        entry = entries.get(str(candidate.pk)) if candidate else None
        counts["campaign_visible" if entry else "outside_campaign_visible"] += 1

        if readiness.evidence_integrity_blockers:
            counts["blocked_by_integrity"] += 1
        if candidate is not None:
            try:
                review = assess_readiness(
                    candidate, wave=entry["wave"] if entry else None)
                if review.rights_evidence == "UNREVIEWED":
                    counts["rights_unreviewed_in_campaign"] += 1
            except CampaignScopeError:
                counts["unreadable_lineage"] += 1

        if read_published_governance(item).state == "ACTIVE":
            counts["governance_selected"] += 1

        # the four operational questions, counted separately — never merged
        for key, allowed in (("retrieval_allowed", readiness.retrieval_allowed),
                             ("automatic_use_allowed", readiness.automatic_use_allowed),
                             ("export_allowed", readiness.export_allowed),
                             ("production_allowed", readiness.production_allowed)):
            if allowed:
                counts[key] += 1

    stale, invalid = _projection_health(at=at)
    return {
        "schema_version": REPORT_SCHEMA,
        "canonical_imported_corpus": CorpusItem.objects.count(),
        # five separate populations, in escalating authority — never one percentage
        "discoverable_for_review": counts["reviewer_search_visible"],
        "eligible_for_retrieval": counts["retrieval_allowed"],
        "eligible_for_automatic_use": counts["automatic_use_allowed"],
        "eligible_for_export": counts["export_allowed"],
        "eligible_for_production": counts["production_allowed"],
        "campaign_visible": counts["campaign_visible"],
        "outside_campaign_visible": counts["outside_campaign_visible"],
        "withheld_identity": counts["withheld_identity"],
        "test_only_excluded": counts["test_only_excluded"],
        "blocked_by_integrity": counts["blocked_by_integrity"],
        # the corpus-wide hard block: EVERY curated acquisition is rights-unreviewed by
        # lineage, in the campaign or not. Counted from lineage, not from having a review
        # candidate — a curated asset outside the campaign is not thereby cleared.
        "curated_rights_unreviewed_corpus_wide": DesignAssetProfile.objects.filter(
            dataset_identifier=DIP1B_CURATED_ASSET_EXPANSION_DATASET).count(),
        # the strictly smaller in-campaign figure, named so it can never be read as the
        # corpus-wide number
        "rights_unreviewed_in_campaign": counts["rights_unreviewed_in_campaign"],
        "governance_selected": counts["governance_selected"],
        "unreadable_lineage": counts["unreadable_lineage"],
        "stale_permission_projections": stale,
        "invalid_permission_projections": invalid,
        "counts_by_item_kind": dict(sorted(by_kind.items())),
        "counts_by_dataset_lineage": dict(sorted(by_dataset.items())),
        "governance_decision_projections": GovernanceDecisionProjection.objects.count(),
        "design_asset_profiles": DesignAssetProfile.objects.count(),
        "campaign_scope_error": scope_error,
        # intentionally absent: see the module docstring
        "combined_readiness_percentage": None,
    }
