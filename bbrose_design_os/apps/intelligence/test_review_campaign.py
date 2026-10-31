"""Curated review campaign + deterministic readiness — DIP-1B-5B.

The real 90-task campaign lives in the operational database; these unit tests build a
representative fixture and prove the LOGIC that could otherwise quietly launder authority:
waves follow dataset lineage (never a machine label), rights are never inferred, brand
identity stays unconfirmed, integrity blocks only what it affects, and none of it writes
anything. The frozen 90/20/14/24/10/22 contract is enforced by
`verify_campaign_partition` (exercised here against a known-wrong partition, and against
the live corpus by the campaign report).
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import review_campaign as RC
from . import review_readiness as RR
from .dataset_identifiers import (
    DIP0C2_ASSET_CANDIDATE_DATASET, DIP1B_CURATED_ASSET_EXPANSION_DATASET,
)
from .models import (
    BrandCandidateProfile, CorpusItem, DesignAssetProfile, HumanAssertionProjection,
    OperationalPermissionProjection, ReviewCandidate, SourceArtifact,
)

pytestmark = pytest.mark.django_db
_n = 0


def _artifact():
    global _n
    _n += 1
    return SourceArtifact.objects.create(
        source_identifier=f"source-{_n}", source_location=f"logical:test:{_n}",
        source_type=SourceArtifact.SourceType.FILE, sha256=f"{_n:064x}",
        parser_identifier="test", parser_version="1", source_schema_version="test/1.0")


def _item(kind, key):
    return CorpusItem.objects.create(item_kind=kind, external_key=key)


def _rc(item, review_type, priority=50):
    return ReviewCandidate.objects.create(
        corpus_item=item, review_type=review_type, priority=priority,
        review_manifest_id="dip1b_review_manifest/1.0")




def historical():
    global _n
    _n += 1
    it = _item(CorpusItem.Kind.HISTORICAL_DESIGN, f"historical:test:{_n}")
    return _rc(it, ReviewCandidate.ReviewType.HISTORICAL_MEMORY)


def asset(dataset):
    global _n
    _n += 1
    it = _item(CorpusItem.Kind.DESIGN_ASSET, f"asset:{dataset}:test:{_n}")
    DesignAssetProfile.objects.create(
        corpus_item=it, primary_source_artifact=_artifact(),
        candidate_source_key=f"k{_n}", source_manifest_entry_key=f"m{_n}",
        dataset_identifier=dataset, candidate_asset_kind="MOTIF",
        representation_state="VECTOR", technical_readiness="TECHNICALLY_READY",
        extraction_state="CLEAN")
    return _rc(it, ReviewCandidate.ReviewType.DESIGN_ASSET)


def brand(kind="LOGO", key=None):
    global _n
    _n += 1
    it = _item(CorpusItem.Kind.BRAND_ASSET, key or f"brand:dip0c3-brand:{_n:02d}")
    BrandCandidateProfile.objects.create(
        corpus_item=it, primary_source_artifact=_artifact(), candidate_kind=kind,
        technical_format="AI", representation_state="VECTOR",
        warning_state="THIRD_PARTY_OR_UNCONFIRMED", candidate_status="UNCONFIRMED")
    return _rc(it, ReviewCandidate.ReviewType.BRAND_IDENTITY, priority=85)


def palette():
    global _n
    _n += 1
    it = _item(CorpusItem.Kind.BRAND_PALETTE, f"palette:dip0c3-palette:test-{_n}")
    BrandCandidateProfile.objects.create(
        corpus_item=it, primary_source_artifact=_artifact(), candidate_kind="PALETTE",
        technical_format="ASE", representation_state="UNKNOWN",
        warning_state="PARTIAL_PARSE", candidate_status="REVIEW_REQUIRED")
    return _rc(it, ReviewCandidate.ReviewType.PALETTE_OBSERVATION)


# === wave assignment: LINEAGE, never machine kind ================================
def test_waves_follow_review_type_and_dataset_lineage():
    historical()
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    brand()
    palette()
    doc = RC.build_campaign_scope()
    by_wave = {e["wave"]: e for e in doc["entries"]}
    assert doc["wave_counts"] == {
        RC.WAVE_1: 1, RC.WAVE_2A: 1, RC.WAVE_2B: 1, RC.WAVE_3: 0, RC.WAVE_4: 2}
    assert by_wave[RC.WAVE_2A]["dataset_identifier"] == DIP0C2_ASSET_CANDIDATE_DATASET
    assert by_wave[RC.WAVE_2B]["dataset_identifier"] == (
        DIP1B_CURATED_ASSET_EXPANSION_DATASET)


def test_brand_lineage_candidate_machine_labelled_palette_stays_wave4_brand():
    """A machine label must never redefine dataset identity or campaign group."""
    rc = brand(kind="PALETTE", key="brand:dip0c3-brand:14")   # PALETTE *kind*, brand lineage
    entry = RC.campaign_entry_for(rc)
    assert entry["wave"] == RC.WAVE_4
    assert entry["review_type"] == ReviewCandidate.ReviewType.BRAND_IDENTITY
    assert entry["external_key"].startswith("brand:")         # lineage wins


def test_every_candidate_belongs_to_exactly_one_wave():
    for _ in range(2):
        historical()
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    entries = RC.build_campaign_scope()["entries"]
    ids = [e["review_candidate_id"] for e in entries]
    assert len(ids) == len(set(ids)) == 4
    assert all(e["wave"] in RC.WAVES for e in entries)


# === determinism / idempotency ==================================================
def test_scope_document_and_hash_are_stable_and_carry_no_timestamp():
    historical()
    asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    a, b = RC.build_campaign_scope(), RC.build_campaign_scope()
    assert a == b
    assert RC.campaign_scope_hash(a) == RC.campaign_scope_hash(b)
    assert "generated_at" not in a and "generated_at" not in repr(a)


def test_entries_carry_the_required_scope_fields():
    historical()
    e = RC.build_campaign_scope()["entries"][0]
    for field in ("review_candidate_id", "corpus_item_id", "external_key", "review_type",
                  "dataset_identifier", "wave", "selection_reason", "business_priority",
                  "known_risk_codes", "recommended_reviewer_discipline",
                  "required_human_outputs"):
        assert field in e, field


# === fail-closed identity contract ==============================================
def test_deprecated_or_retired_subject_is_rejected():
    rc = historical()
    CorpusItem.objects.filter(pk=rc.corpus_item_id).update(
        lifecycle_state=CorpusItem.Lifecycle.RETIRED)
    with pytest.raises(RC.CampaignScopeError):
        RC.build_campaign_scope()


def test_duplicate_active_subject_is_rejected():
    """The DB already blocks a same-manifest duplicate; the campaign must also refuse a
    second active subject arriving via a DIFFERENT manifest."""
    rc = historical()
    ReviewCandidate.objects.create(
        corpus_item=rc.corpus_item, review_type=ReviewCandidate.ReviewType.HISTORICAL_MEMORY,
        priority=50, review_manifest_id="dip1b_curated_review_manifest/1.0")
    with pytest.raises(RC.CampaignScopeError):
        RC.build_campaign_scope()


def test_frozen_partition_contract_rejects_a_wrong_partition():
    historical()
    doc = RC.build_campaign_scope()
    with pytest.raises(RC.CampaignScopeError):
        RC.verify_campaign_partition(doc)          # 1 != the frozen 90
    RC.verify_campaign_partition(doc, expected={
        RC.WAVE_1: 1, RC.WAVE_2A: 0, RC.WAVE_2B: 0, RC.WAVE_3: 0, RC.WAVE_4: 0})


def test_campaign_creates_nothing():
    historical()
    brand()
    before = (CorpusItem.objects.count(), ReviewCandidate.objects.count(),
              DecisionEvent.objects.count(),
              OperationalPermissionProjection.objects.count())
    RC.build_campaign_scope()
    RC.campaign_scope_hash()
    assert (CorpusItem.objects.count(), ReviewCandidate.objects.count(),
            DecisionEvent.objects.count(),
            OperationalPermissionProjection.objects.count()) == before


# === readiness: the authority-laundering guards =================================
def test_readiness_is_deterministic_and_writes_nothing():
    rc = asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    before = (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
              OperationalPermissionProjection.objects.count())
    assert RR.assess_readiness(rc).as_dict() == RR.assess_readiness(rc).as_dict()
    assert (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            OperationalPermissionProjection.objects.count()) == before


def test_curated_asset_is_rights_unreviewed_regardless_of_technical_state():
    """Technical quality is not rights. Rights attach to provenance and acquisition, so a
    TECHNICALLY_READY curated asset is still rights-unreviewed."""
    rc = asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    assert DesignAssetProfile.objects.get(
        corpus_item=rc.corpus_item).technical_readiness == "TECHNICALLY_READY"
    r = RR.assess_readiness(rc)
    assert r.rights_evidence == RR.RIGHTS_UNREVIEWED
    assert RR.B_RIGHTS in r.blocker_codes
    assert r.implies_rights_clearance is False


def test_duplicate_hash_never_transfers_rights_between_acquisitions():
    """A C2 asset and a curated asset sharing bytes do NOT share a rights conclusion."""
    shared = _artifact()
    c2 = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    curated = asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    DesignAssetProfile.objects.filter(corpus_item=c2.corpus_item).update(
        primary_source_artifact=shared)
    DesignAssetProfile.objects.filter(corpus_item=curated.corpus_item).update(
        primary_source_artifact=shared)
    assert RR.assess_readiness(curated).rights_evidence == RR.RIGHTS_UNREVIEWED


def test_brand_candidate_identity_stays_unconfirmed():
    rc = brand()
    r = RR.assess_readiness(rc)
    assert r.identity_evidence in (RR.ID_PARTIALLY_VERIFIED, RR.ID_UNVERIFIED)
    assert RR.B_IDENTITY in r.blocker_codes
    assert r.rights_evidence == RR.RIGHTS_UNREVIEWED


def test_palette_candidate_is_rights_and_identity_blocked():
    r = RR.assess_readiness(palette())
    assert r.rights_evidence == RR.RIGHTS_UNREVIEWED
    assert RR.B_IDENTITY in r.blocker_codes


def test_historical_memory_rights_are_not_applicable_not_cleared():
    r = RR.assess_readiness(historical())
    assert r.rights_evidence == RR.RIGHTS_NOT_APPLICABLE   # reference memory, not reuse
    assert RR.B_RIGHTS not in r.blocker_codes
    assert r.implies_rights_clearance is False


def test_readiness_never_reports_approval_or_permission():
    for rc in (historical(), asset(DIP0C2_ASSET_CANDIDATE_DATASET), brand(), palette()):
        r = RR.assess_readiness(rc)
        assert r.implies_approval is False
        assert r.implies_rights_clearance is False
        assert r.operational_permission_granted is False


def test_blocker_ordering_is_normalised():
    for rc in (asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET), brand(), palette()):
        codes = RR.assess_readiness(rc).blocker_codes
        assert list(codes) == [c for c in RR._BLOCKER_ORDER if c in codes]
