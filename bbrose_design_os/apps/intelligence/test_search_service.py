"""Search service, retrieval readiness, and report — DIP-1B-6.

The claims defended: reviewer visibility is not a permission and never implies one;
operational modes fail closed to empty; the permission gate is not duplicated; campaign and
corpus scopes stay distinct; legacy signals grant nothing and never rank; nothing writes.
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import search_contract as SC
from .dataset_identifiers import (
    DIP0C2_ASSET_CANDIDATE_DATASET, DIP1B_CURATED_ASSET_EXPANSION_DATASET,
)
from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, GovernanceDecisionProjection,
    HumanAssertionProjection, OperationalPermissionProjection, SourceLocationObservation,
)
from .retrieval_readiness import evaluate_retrieval_readiness
from .search_report import build_retrieval_readiness_report
from .search_service import execute_search
from .test_review_campaign import asset, brand, historical, palette

pytestmark = pytest.mark.django_db


def _run(**raw):
    return execute_search(SC.build_search_query(raw))


def _authority_counts():
    return (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            GovernanceDecisionProjection.objects.count(),
            OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count())


# === retrieval readiness: fail-closed core ======================================
def test_readiness_returns_zero_operational_permission_and_writes_nothing():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    before = _authority_counts()
    r = evaluate_retrieval_readiness(rc.corpus_item)
    assert r.candidate_review_visible is True       # a human may review it
    assert r.retrieval_allowed is False             # ... but nothing more
    assert r.automatic_use_allowed is False
    assert r.export_allowed is False and r.production_allowed is False
    assert r.permission_reason_codes["RETRIEVAL"] == "PROJECTION_ABSENT"
    assert _authority_counts() == before


def test_reviewer_visibility_is_not_a_permission():
    """Zero permission projections exist; if visibility were the VISIBLE_IN_REVIEWER_SEARCH
    permission, nothing would be searchable. Visibility must be identity, not permission."""
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    assert not OperationalPermissionProjection.objects.exists()
    assert evaluate_retrieval_readiness(rc.corpus_item).candidate_review_visible is True


def test_retired_subject_is_withheld_not_visible():
    rc = historical()
    CorpusItem.objects.filter(pk=rc.corpus_item_id).update(
        lifecycle_state=CorpusItem.Lifecycle.RETIRED)
    r = evaluate_retrieval_readiness(
        CorpusItem.objects.get(pk=rc.corpus_item_id))
    assert r.candidate_review_visible is False
    assert "SUBJECT_NOT_ACTIVE" in r.identity_blockers


# === search modes ===============================================================
def test_reviewer_mode_shows_blocked_items_operational_modes_return_empty():
    brand()                                          # rights + identity blocked
    reviewer = _run(mode=SC.REVIEWER_CANDIDATE_SEARCH)
    assert reviewer["total_results"] >= 1
    assert _run(mode=SC.OPERATIONAL_RETRIEVAL)["total_results"] == 0
    assert _run(mode=SC.AUTOMATIC_USE)["total_results"] == 0


def test_reviewer_access_does_not_imply_retrieval():
    rc = asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    result = _run(mode=SC.REVIEWER_CANDIDATE_SEARCH)
    row = next(r for r in result["results"] if r["corpus_item_id"] == str(rc.corpus_item_id))
    assert row["retrieval"]["allowed"] is False
    assert row["automatic_use"]["allowed"] is False


def test_allowed_row_without_valid_event_still_denies_retrieval():
    """A raw ALLOWED projection with no verifiable DecisionEvent must not surface in the
    operational mode — authority comes from the gate, not the row's state column."""
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    OperationalPermissionProjection.objects.create(
        corpus_item=rc.corpus_item,
        permission_type=OperationalPermissionProjection.Permission.RETRIEVAL,
        effective_state=OperationalPermissionProjection.State.ALLOWED,
        source_decision_event=None, source_sequence_number=0,
        projected_chain_head_hash="f" * 64,      # valid shape, but not the real chain head
        projection_version="operational_permission/1.0", reason_code="TEST")
    assert evaluate_retrieval_readiness(rc.corpus_item).retrieval_allowed is False
    assert _run(mode=SC.OPERATIONAL_RETRIEVAL)["total_results"] == 0


def test_quarantined_permission_denies_retrieval():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    OperationalPermissionProjection.objects.create(
        corpus_item=rc.corpus_item,
        permission_type=OperationalPermissionProjection.Permission.RETRIEVAL,
        effective_state=OperationalPermissionProjection.State.QUARANTINED,
        source_decision_event=None, source_sequence_number=0,
        projected_chain_head_hash=None,
        projection_version="operational_permission/1.0", reason_code="TEST")
    r = evaluate_retrieval_readiness(rc.corpus_item)
    assert r.retrieval_allowed is False
    assert r.permission_reason_codes["RETRIEVAL"] == "STATE_QUARANTINED"


def test_expired_permission_denies_retrieval():
    from django.utils import timezone
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    OperationalPermissionProjection.objects.create(
        corpus_item=rc.corpus_item,
        permission_type=OperationalPermissionProjection.Permission.RETRIEVAL,
        effective_state=OperationalPermissionProjection.State.ALLOWED,
        source_decision_event=None, source_sequence_number=0,
        projected_chain_head_hash=None,
        expires_at=timezone.now() - timezone.timedelta(days=1),
        projection_version="operational_permission/1.0", reason_code="TEST")
    r = evaluate_retrieval_readiness(rc.corpus_item)
    assert r.retrieval_allowed is False
    assert r.permission_reason_codes["RETRIEVAL"] == "PERMISSION_EXPIRED"


# === campaign vs corpus scope ===================================================
def test_campaign_and_corpus_scopes_are_distinct_documented_populations():
    historical()
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    campaign = _run(scope=SC.CAMPAIGN_SCOPE, limit=100)
    corpus = _run(scope=SC.CORPUS_SCOPE, limit=100)
    assert {r["campaign_membership"] for r in campaign["results"]} == {SC.IN_CAMPAIGN}
    memberships = {r["campaign_membership"] for r in corpus["results"]}
    assert SC.IN_CAMPAIGN in memberships


def test_test_only_records_are_excluded():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    DesignAssetProfile.objects.filter(corpus_item=rc.corpus_item).update(
        is_test_only=True)
    result = _run(mode=SC.REVIEWER_CANDIDATE_SEARCH)
    assert result["test_only_excluded_count"] == 1
    assert all(r["corpus_item_id"] != str(rc.corpus_item_id)
               for r in result["results"])


# === result contract ============================================================
def test_result_never_leaks_absolute_path_and_marks_legacy_non_authoritative():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    profile = DesignAssetProfile.objects.get(corpus_item=rc.corpus_item)
    EvidenceReference.objects.create(
        corpus_item=rc.corpus_item, source_artifact=profile.primary_source_artifact,
        evidence_kind="SOURCE_FILE", locator={"path": "a/b.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="a" * 64)
    SourceLocationObservation.objects.create(
        source_artifact=profile.primary_source_artifact,
        observed_location="/Users/secret/materials/x.ai",
        location_kind="REPOSITORY_RELATIVE", availability_state="AVAILABLE")
    result = _run(query="", mode=SC.REVIEWER_CANDIDATE_SEARCH)
    assert "/Users/secret" not in repr(result)
    assert all(r["legacy_signals"]["affects_ranking"] is False
               for r in result["results"])
    assert all(r["legacy_signals"]["grants"] == "NOTHING" for r in result["results"])


def test_a_legacy_active_reference_grants_no_intelligence_retrieval():
    """A legacy DesignReference marked active is a separate, non-authoritative system: it
    must not make any intelligence corpus item retrievable or automatically usable."""
    from apps.core.models import DesignReference
    DesignReference.objects.create(
        name="legacy-active", image_path="x/y.png", source_file="x/y.ai",
        category="c", product_type="p", summary="s", active=True)
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    r = evaluate_retrieval_readiness(rc.corpus_item)
    assert r.retrieval_allowed is False        # legacy active grants nothing here
    assert r.automatic_use_allowed is False
    result = _run(mode=SC.OPERATIONAL_RETRIEVAL)
    assert result["total_results"] == 0


def test_deterministic_repeat_search():
    for _ in range(3):
        asset(DIP0C2_ASSET_CANDIDATE_DATASET)
        brand()
    a = _run(query="brand")
    b = _run(query="brand")
    assert [r["corpus_item_id"] for r in a["results"]] == [
        r["corpus_item_id"] for r in b["results"]]


def test_search_writes_nothing():
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    before = _authority_counts()
    for mode in SC.SEARCH_MODES:
        _run(mode=mode)
    assert _authority_counts() == before


# === report =====================================================================
def test_report_separates_populations_and_has_no_combined_percentage():
    historical()
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    r = build_retrieval_readiness_report()
    assert r["combined_readiness_percentage"] is None
    assert r["discoverable_for_review"] == 3
    assert r["eligible_for_retrieval"] == 0
    assert r["eligible_for_automatic_use"] == 0
    assert r["eligible_for_export"] == 0
    assert r["eligible_for_production"] == 0
    # discoverable and retrievable are different numbers, never merged
    assert r["discoverable_for_review"] != r["eligible_for_retrieval"]


def test_report_curated_rights_unreviewed_is_corpus_wide_by_lineage():
    """Every curated acquisition is rights-unreviewed by lineage, whether or not it has a
    review candidate. A curated asset outside the campaign is not thereby cleared."""
    from .models import CorpusItem, DesignAssetProfile, SourceArtifact
    # a curated asset with NO ReviewCandidate — outside any campaign
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key="asset:curated:orphan")
    art = SourceArtifact.objects.create(
        source_identifier="s-orphan", source_location="logical:orphan",
        source_type=SourceArtifact.SourceType.FILE, sha256="c" * 64,
        parser_identifier="t", parser_version="1", source_schema_version="t/1.0")
    DesignAssetProfile.objects.create(
        corpus_item=item, primary_source_artifact=art, candidate_source_key="ko",
        source_manifest_entry_key="mo",
        dataset_identifier=DIP1B_CURATED_ASSET_EXPANSION_DATASET,
        candidate_asset_kind="MOTIF", representation_state="VECTOR",
        technical_readiness="TECHNICALLY_READY", extraction_state="CLEAN")
    asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)      # a curated asset WITH a candidate
    r = build_retrieval_readiness_report()
    # corpus-wide counts by lineage (2), campaign-only is strictly smaller (1)
    assert r["curated_rights_unreviewed_corpus_wide"] == 2
    assert r["rights_unreviewed_in_campaign"] == 1
    assert (r["curated_rights_unreviewed_corpus_wide"]
            > r["rights_unreviewed_in_campaign"])


def test_report_writes_nothing():
    brand()
    palette()
    before = _authority_counts()
    build_retrieval_readiness_report()
    assert _authority_counts() == before
