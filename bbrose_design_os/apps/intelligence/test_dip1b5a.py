import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.models import DecisionEvent
from apps.accounts.models import (
    GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)

from .brand_evidence import (
    DATASET_ID, ORIGIN_DATASET_ID, validate_committed_brand_evidence_bundle,
)
from .brand_evidence_import import run_brand_evidence_import
from .curated_expansion import (
    build_curated_expansion_manifest, validate_curated_expansion_manifest,
)
from .curated_expansion_import import run_curated_expansion_import
from .curated_review import (
    build_curated_review_manifest, import_curated_review_candidates,
)
from .evidence_integrity import EvidenceIntegrityResolver, VERIFIED
from .evidence_readiness import evidence_readiness, governance_category_dimension_ready
from .models import (
    BrandCandidateProfile, CorpusItem, DesignAssetProfile, EvidenceReference,
    HistoricalDesignProfile,
    ImportBatch, ImportRecord, OperationalPermissionProjection, ReviewCandidate,
    SourceArtifact,
)

pytestmark = pytest.mark.django_db


def _source(identifier="fixture", digest="a" * 64):
    return SourceArtifact.objects.create(
        source_identifier=identifier, source_location=f"repository:{identifier}",
        source_type=SourceArtifact.SourceType.FILE, sha256=digest,
        parser_identifier="fixture", parser_version="1.0",
        source_schema_version="fixture/1.0",
        availability_state=SourceArtifact.Availability.AVAILABLE,
    )


def _preserved_brand_candidates():
    bundle = validate_committed_brand_evidence_bundle()
    artifact = _source()
    batch = ImportBatch.objects.create(
        importer_identifier="fixture.accepted", importer_version="1.0",
        configuration_hash="b" * 64, source_manifest_hash="c" * 64,
        scope={}, status=ImportBatch.Status.COMPLETED,
    )
    items = []
    for index, record in enumerate(bundle["dataset"]["records"]):
        key = record["stable_candidate_key"]
        item = CorpusItem.objects.create(
            item_kind=CorpusItem.Kind.BRAND_ASSET, external_key=f"brand:{key}")
        ImportRecord.objects.create(
            import_batch=batch, stable_source_record_key=f"brand-candidate:{key}",
            source_record_hash=record["preserved_import_record_hash"],
            source_artifact=artifact, corpus_item=item,
            disposition=ImportRecord.Disposition.CREATED,
            parser_version="1.0", source_schema_version=ORIGIN_DATASET_ID,
            reconciliation_details={"dataset_id": ORIGIN_DATASET_ID},
        )
        EvidenceReference.objects.create(
            corpus_item=item, source_artifact=artifact, evidence_kind="SOURCE_FILE",
            locator={"path": record["source_input"]["path"]},
            locator_schema_version="source_file/1.0",
            observed_value=artifact.sha256,
            evidence_hash=f"{index + 1:064x}", is_test_only=False,
        )
        items.append(item)
    return items


def _authority_counts():
    return (
        DecisionEvent.objects.count(),
        OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
    )


def test_versioned_manifests_are_deterministic_and_exact():
    expansion, expansion_raw, expansion_hash = build_curated_expansion_manifest()
    expansion_prepared = validate_curated_expansion_manifest()
    assert expansion_prepared["document"] == expansion
    assert expansion_prepared["raw"] == expansion_raw
    assert expansion_prepared["sha256"] == expansion_hash
    assert len(expansion_prepared["historical"]) == 6
    assert len(expansion_prepared["assets"]) == 53
    review, review_raw, review_hash = build_curated_review_manifest()
    assert len(review["entries"]) == 51
    assert review["expected_counts"] == {
        "total": 51, "historical_memory": 6,
        "design_assets": 24, "brand_identity": 21,
    }
    assert len(review_raw) > 0 and len(review_hash) == 64


def test_bounded_imports_partial_retry_idempotency_and_separate_readiness():
    brand_items = _preserved_brand_candidates()
    authority_before = _authority_counts()
    counts_before = {
        "artifacts": SourceArtifact.objects.count(),
        "batches": ImportBatch.objects.count(),
        "records": ImportRecord.objects.count(),
        "evidence": EvidenceReference.objects.count(),
    }
    preview = run_brand_evidence_import()
    assert preview["semantic_corpus_items"] == 21
    assert preview["would_create_records"] == 22
    assert counts_before == {
        "artifacts": SourceArtifact.objects.count(),
        "batches": ImportBatch.objects.count(),
        "records": ImportRecord.objects.count(),
        "evidence": EvidenceReference.objects.count(),
    }
    applied = run_brand_evidence_import(apply=True)
    assert applied["failed_records"] == 0
    assert applied["created_records"] == 22
    after_brand = (
        SourceArtifact.objects.count(), ImportBatch.objects.count(),
        ImportRecord.objects.count(), EvidenceReference.objects.count(),
    )
    repeated = run_brand_evidence_import(apply=True)
    assert repeated["existing_completed_batch"] == applied["batch_id"]
    assert after_brand == (
        SourceArtifact.objects.count(), ImportBatch.objects.count(),
        ImportRecord.objects.count(), EvidenceReference.objects.count(),
    )
    first = brand_items[0]
    readiness = evidence_readiness(first)
    assert readiness["overall_status"] == "PARTIALLY_VERIFIED"
    assert readiness["technical_evidence_ready"] is True
    assert readiness["governance_ready"] is False
    assert governance_category_dimension_ready(first, "TECHNICAL_AND_BRAND") is False
    reference = first.evidence_references.get(
        evidence_kind="DETERMINISTIC_BRAND_EVIDENCE_RECORD")
    assert EvidenceIntegrityResolver().evaluate(first, [reference]).status == VERIFIED
    assert first.evidence_references.exclude(pk=reference.pk).count() == 1

    expansion_before = (
        CorpusItem.objects.count(), DesignAssetProfile.objects.count(),
        HistoricalDesignProfile.objects.count(), ImportBatch.objects.count(),
    )
    expansion_preview = run_curated_expansion_import()
    assert expansion_preview["manifest_entries"] == 59
    assert expansion_preview["physical_source_artifacts"] == 59
    assert expansion_before == (
        CorpusItem.objects.count(), DesignAssetProfile.objects.count(),
        HistoricalDesignProfile.objects.count(), ImportBatch.objects.count(),
    )
    partial = run_curated_expansion_import(
        apply=True, fail_record_key="dip1b-exp-historical:00")
    assert partial["failed_records"] == 1
    assert DesignAssetProfile.objects.filter(
        dataset_identifier="dip1b_curated_asset_expansion/1.0").count() == 53
    assert HistoricalDesignProfile.objects.filter(
        corpus_item__external_key__startswith="historical:dip1b-exp-").count() == 5
    retry = run_curated_expansion_import(apply=True)
    assert retry["failed_records"] == 0
    assert HistoricalDesignProfile.objects.filter(
        corpus_item__external_key__startswith="historical:dip1b-exp-").count() == 6
    expansion_after = (
        CorpusItem.objects.count(), DesignAssetProfile.objects.count(),
        HistoricalDesignProfile.objects.count(), ImportBatch.objects.count(),
        ImportRecord.objects.count(),
    )
    repeated_expansion = run_curated_expansion_import(apply=True)
    assert repeated_expansion["existing_completed_batch"] == retry["batch_id"]
    assert expansion_after == (
        CorpusItem.objects.count(), DesignAssetProfile.objects.count(),
        HistoricalDesignProfile.objects.count(), ImportBatch.objects.count(),
        ImportRecord.objects.count(),
    )

    preserved_review_ids = []
    for item in brand_items[:7]:
        candidate = ReviewCandidate.objects.create(
            corpus_item=item, review_type=ReviewCandidate.ReviewType.BRAND_IDENTITY,
            workflow_status=ReviewCandidate.Status.NEEDS_INFORMATION,
            priority=77, review_manifest_id="dip1b_review_manifest/1.0",
            machine_confidence_summary={"preserved": True},
        )
        preserved_review_ids.append(candidate.pk)
    review_preview = import_curated_review_candidates()
    assert review_preview["manifest_entries"] == 51
    assert review_preview["unchanged"] == 7
    assert review_preview["would_create"] == 44
    review_applied = import_curated_review_candidates(apply=True)
    assert review_applied["created"] == 44
    assert list(ReviewCandidate.objects.filter(
        pk__in=preserved_review_ids).values_list(
            "workflow_status", flat=True)) == [
                ReviewCandidate.Status.NEEDS_INFORMATION] * 7
    assert import_curated_review_candidates(apply=True)["created"] == 0
    assert _authority_counts() == authority_before
    assert DesignAssetProfile.objects.filter(
        dataset_identifier="dip1b_curated_asset_expansion/1.0").count() == 53
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()
    assert DATASET_ID == "dip1b_brand_evidence/2.0"


def test_browser_displays_versions_dimensions_and_denied_permission(client):
    items = _preserved_brand_candidates()
    item = items[0]
    source = item.evidence_references.first().source_artifact
    BrandCandidateProfile.objects.create(
        corpus_item=item, primary_source_artifact=source,
        candidate_kind=BrandCandidateProfile.CandidateKind.WORDMARK,
        observed_brand_label="BBROSE candidate", technical_format="PDF",
        representation_state=BrandCandidateProfile.Representation.VECTOR,
        observed_candidate_data={},
        warning_state=BrandCandidateProfile.Warning.REQUIRES_REVIEW,
        candidate_status=BrandCandidateProfile.Status.REVIEW_REQUIRED,
    )
    run_brand_evidence_import(apply=True)
    User = get_user_model()
    granter = User.objects.create_user(username="dip1b5a-browser-granter")
    user = User.objects.create_user(username="dip1b5a-browser-reviewer")
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=authz.DESIGN_REVIEWER, granted_by=granter,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="DIP-1B-5A browser fixture",
    )
    client.force_login(user)
    before = _authority_counts()
    response = client.get(
        reverse("intelligence:corpus-detail", args=[item.pk]), secure=True)
    assert response.status_code == 200
    # [the owner's goal of 2026-09-25, (c) "One clean visual system": the reviewer's pages are in the one shell]
    assert b'class="bar"' in response.content and b"intelligence.css" not in response.content
    for expected in (
        b"dip1b_brand_evidence/2.0", b"PARTIALLY_VERIFIED",
        b"TECHNICAL_EVIDENCE_READY", b"BRAND_IDENTITY_EVIDENCE_READY",
        b"RIGHTS_EVIDENCE_READY", b"PALETTE_AUTHORITY_EVIDENCE_READY",
        b"GOVERNANCE_READY", b"IDENTITY_RIGHTS_OR_PALETTE_AUTHORITY_MISSING",
        b"OPERATIONAL PERMISSION", b"DENIED",
    ):
        assert expected in response.content
    assert _authority_counts() == before
