"""Review packets, campaign report, and coverage gaps — DIP-1B-5B.

The claims worth defending: packets are bounded and leak no absolute path, machine output
stays visibly non-authoritative, governance is read-only, nothing infers approval or rights,
the report never blends corpus with campaign or emits a single approval percentage, and none
of it writes anything.
"""
from __future__ import annotations

import pytest

from apps.accounts.models import DecisionEvent

from . import campaign_report as CR
from . import review_packet as RP
from . import review_readiness as RR
from .dataset_identifiers import (
    DIP0C2_ASSET_CANDIDATE_DATASET, DIP1B_CURATED_ASSET_EXPANSION_DATASET,
)
from .models import (
    EvidenceReference, HumanAssertionProjection, OperationalPermissionProjection,
    SourceLocationObservation,
)
from .test_review_campaign import asset, brand, historical, palette

pytestmark = pytest.mark.django_db


def _evidence_for(rc, *, locator=None):
    from .models import DesignAssetProfile
    profile = DesignAssetProfile.objects.filter(corpus_item=rc.corpus_item).first()
    artifact = profile.primary_source_artifact
    return EvidenceReference.objects.create(
        corpus_item=rc.corpus_item, source_artifact=artifact,
        evidence_kind="SOURCE_FILE",
        locator=locator or {"path": "a/b/c.ai"},
        locator_schema_version="source_file/1.0", observed_value="",
        evidence_hash="e" * 64)


# === packet shape ===============================================================
def test_packet_schema_and_canonical_identities():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    p = RP.build_review_packet(rc)
    assert p["schema_version"] == "review_packet/1.0"
    assert p["corpus_item_id"] == str(rc.corpus_item_id)
    assert p["review_candidate_id"] == str(rc.pk)
    assert p["wave"] == "WAVE_2A_ORIGINAL_C2_DESIGN_ASSETS"
    assert p["dataset_identifier"] == DIP0C2_ASSET_CANDIDATE_DATASET


def test_packet_is_deterministic_and_writes_nothing():
    rc = brand()
    before = (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
              OperationalPermissionProjection.objects.count())
    assert RP.build_review_packet(rc) == RP.build_review_packet(rc)
    assert (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            OperationalPermissionProjection.objects.count()) == before


def test_packet_never_emits_an_unrestricted_absolute_path():
    """No location_kind promises an absolute path, so this is defence in depth: an importer
    writing an absolute path under a kind that claims REPOSITORY_RELATIVE must still never
    leak a real filesystem location to a reviewer."""
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    ev = _evidence_for(rc)
    SourceLocationObservation.objects.create(
        source_artifact=ev.source_artifact,
        observed_location="/Users/secret/materials/private.ai",   # absolute — must not leak
        location_kind="REPOSITORY_RELATIVE", availability_state="AVAILABLE")
    p = RP.build_review_packet(rc)
    locations = p["source_location_observations"]
    assert locations and locations[0]["observed_location"] == RP.REDACTED_LOCATION
    assert "/Users/secret" not in repr(p)


def test_packet_carries_source_hashes_and_bounded_evidence_locators():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    ev = _evidence_for(rc)
    p = RP.build_review_packet(rc)
    assert p["source_hashes"] == [ev.source_artifact.sha256]
    assert p["evidence_references"][0]["evidence_reference_id"] == str(ev.pk)
    assert p["evidence_references"][0]["locator_schema_version"] == "source_file/1.0"


def test_packet_keeps_machine_output_non_authoritative_and_separate_from_humans():
    rc = brand()
    p = RP.build_review_packet(rc)
    assert all(m["authoritative"] is False for m in p["machine_classifications"])
    assert "projection_state" in p["human_assertions"]      # human state is its own section


def test_packet_governance_is_read_only_and_permission_is_denied():
    rc = brand()
    p = RP.build_review_packet(rc)
    assert p["governance"]["read_only"] is True
    assert p["implies_governance_selection"] is False
    assert p["grants_operational_permission"] is False
    assert all(r["allowed"] is False for r in p["operational_permissions"])


def test_packet_states_no_approval_or_rights_inference():
    for rc in (historical(), asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET), palette()):
        p = RP.build_review_packet(rc)
        assert p["implies_approval"] is False
        assert p["implies_rights_clearance"] is False


def test_packet_rejects_a_candidate_outside_the_frozen_campaign():
    from .models import CorpusItem, ReviewCandidate
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key="asset:orphan:1")
    rc = ReviewCandidate.objects.create(
        corpus_item=item, review_type=ReviewCandidate.ReviewType.DESIGN_ASSET,
        priority=1, review_manifest_id="dip1b_review_manifest/1.0")
    with pytest.raises(Exception):
        RP.build_review_packet(rc)      # no DesignAssetProfile -> no lineage -> refused


# === question sets: questions only ==============================================
@pytest.mark.parametrize("factory,review_type", [
    (historical, "HISTORICAL_MEMORY"), (brand, "BRAND_IDENTITY"),
    (palette, "PALETTE_OBSERVATION"),
])
def test_question_sets_are_bounded_and_unanswered(factory, review_type):
    p = RP.build_review_packet(factory())
    questions = p["required_human_questions"]
    assert questions == list(RP.QUESTION_SETS[review_type])
    # the packet asks; it never answers
    assert all(isinstance(q, str) for q in questions)


def test_prohibited_inference_warnings_are_present():
    p = RP.build_review_packet(asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET))
    w = p["prohibited_inference_warnings"]
    assert "REVIEW_READINESS_IS_NOT_APPROVAL_OR_OPERATIONAL_PERMISSION" in w
    assert "MATCHING_HASH_DOES_NOT_TRANSFER_RIGHTS" in w
    assert "NEARBY_LICENCE_EVIDENCE_DOES_NOT_CLEAR_RIGHTS" in w


def test_brand_packet_warns_that_technical_evidence_is_not_identity():
    w = RP.build_review_packet(brand())["prohibited_inference_warnings"]
    assert "TECHNICAL_EVIDENCE_IS_NOT_BRAND_IDENTITY" in w
    assert "A_BBROSE_LABEL_IS_NOT_CONFIRMED_BBROSE_OWNERSHIP" in w


# === campaign report ============================================================
def test_report_separates_corpus_from_campaign_and_has_no_blended_percentage():
    historical()
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)
    r = CR.build_campaign_report()
    assert set(r["corpus"]) & set(r["campaign"]) == set()      # two distinct populations
    assert r["combined_approval_percentage"] is None
    assert "in_active_campaign" in r["progress_axes"]
    assert r["campaign"]["total_review_candidates"] == 3
    assert r["corpus"]["design_assets"] == 2


def test_report_counts_curated_rights_unreviewed_corpus_wide():
    asset(DIP1B_CURATED_ASSET_EXPANSION_DATASET)       # in campaign
    r = CR.build_campaign_report()
    assert r["corpus"]["curated_assets_rights_unreviewed"] == 1
    assert r["campaign"]["curated_assets_in_campaign"] == 1
    assert r["rights_evidence_counts"].get(RR.RIGHTS_UNREVIEWED, 0) >= 1


def test_report_progress_axes_are_separate_not_substitutable():
    historical()
    axes = CR.build_campaign_report()["progress_axes"]
    for key in ("imported_corpus_items", "in_active_campaign", "review_tasks_completed",
                "human_classified", "governance_selected", "operationally_permitted"):
        assert key in axes
    assert axes["governance_selected"] == 0
    assert axes["operationally_permitted"] == 0


def test_report_authority_counts_stay_zero_and_report_writes_nothing():
    historical()
    brand()
    before = (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
              OperationalPermissionProjection.objects.count())
    r = CR.build_campaign_report()
    assert r["authority_counts"]["signed_decision_events"] == 0
    assert r["authority_counts"]["human_assertion_projections"] == 0
    assert r["authority_counts"]["governance_selections"] == 0
    assert (DecisionEvent.objects.count(), HumanAssertionProjection.objects.count(),
            OperationalPermissionProjection.objects.count()) == before


def test_review_required_integrity_is_not_reported_as_hash_mismatch():
    """The resolver's REVIEW_REQUIRED means "a human must look" — not "the hashes
    disagree". Readiness must not upgrade a reason code into a finding the authority gate
    never made, even though DECLARED_HASH_MISMATCH appears among the reason codes."""
    from .evidence_integrity import REVIEW_REQUIRED as RESOLVER_REVIEW_REQUIRED
    assert RR._INTEGRITY_MAP[RESOLVER_REVIEW_REQUIRED] == RR.INTEG_REVIEW_REQUIRED
    assert RR._INTEGRITY_MAP[RESOLVER_REVIEW_REQUIRED] != RR.INTEG_HASH_MISMATCH
    # every distinct resolver status keeps a distinct readiness state
    assert len(set(RR._INTEGRITY_MAP.values())) == len(RR._INTEGRITY_MAP)


def test_imported_corpus_axis_counts_every_item_including_brand_and_palette():
    """Summing profile tables would omit brand/palette entirely and under-report the
    corpus. The axis must count the corpus itself."""
    from .models import CorpusItem
    historical()
    asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    brand()
    palette()
    axes = CR.build_campaign_report()["progress_axes"]
    assert axes["imported_corpus_items"] == CorpusItem.objects.count() == 4


# === hair-care gap ==============================================================
def test_hair_care_gap_is_deterministic_stable_and_non_blocking():
    a, b = CR.hair_care_coverage_gap(), CR.hair_care_coverage_gap()
    assert a == b
    assert a["gap_id"] == CR.HAIR_CARE_GAP_ID
    assert a["missing_product_family"] == "HAIR_CARE"
    assert a["blocking"] is False and a["blocks_other_waves"] is False


def test_hair_care_gap_does_not_block_unrelated_candidates():
    rc = asset(DIP0C2_ASSET_CANDIDATE_DATASET)
    assert CR.hair_care_coverage_gap()["blocking"] is False
    assert RR.assess_readiness(rc).overall != RR.BLOCKED_BY_INTEGRITY
    assert CR.hair_care_coverage_gap() in CR.build_campaign_report()["coverage_gaps"]
