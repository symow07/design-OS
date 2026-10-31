from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.models import (
    DecisionEvent, GRANT_TEST_FIXTURE, ReviewerProfile, ReviewerRoleAssignment,
)
from apps.accounts.security import signing

from .evidence_integrity import (
    CORRECTION_ID, DEFAULT_MANIFEST, DEFAULT_REGISTRY, REVIEW_REQUIRED,
    STALE_GENERATED_OUTPUT, STALE_IGNORED_OUTPUT, UNRESOLVED, VERIFIED,
    EvidenceIntegrityResolver, evaluate_evidence_integrity,
    reconcile_brand_candidate_integrity,
)
from .manifest import ManifestError, resolve_source
from .governance import (
    CANONICAL_BRAND_ASSET, GLOBAL_PRIMARY_LOGO,
    GovernanceEligibilityError, record_governance_attestation,
)
from apps.accounts.attestation import CATEGORY_TECHNICAL_AND_BRAND
from .models import (
    BrandCandidateProfile, CorpusItem, EvidenceReference, ImportBatch, ImportRecord,
    HumanAssertionProjection, OperationalPermissionProjection,
    ProjectionPublicationState, ReviewCandidate, SourceArtifact,
)
from .projection import ProjectionValidationError, build_projection
from .review_services import (
    AssertionValidationError, claim_review_candidate,
    record_intelligence_classification, record_intelligence_evidence_assessment,
)

pytestmark = pytest.mark.django_db
User = get_user_model()
KEY = "7" * 32
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_DOCUMENT = json.loads(Path(DEFAULT_MANIFEST).read_text(encoding="utf-8"))
REGISTRY_DOCUMENT = json.loads(Path(DEFAULT_REGISTRY).read_text(encoding="utf-8"))
POLICY = next(row for row in REGISTRY_DOCUMENT["policies"]
              if row["correction_id"] == CORRECTION_ID)
SELECTOR = POLICY["manifest_selector"]
DATASET_ID = SELECTOR["dataset_id"]
EXPECTED_SHA256 = SELECTOR["expected_sha256"]
BRAND_ENTRY = next(row for row in MANIFEST_DOCUMENT["entries"]
                   if row.get("dataset_id") == DATASET_ID)
SOURCE_PATH = BRAND_ENTRY["data_source"]["source"]["path"]
ACCEPTED_IMPORT_MANIFEST_SHA256 = POLICY["root_of_trust"][
    "accepted_import_manifest_sha256"]
OBSERVED_SHA256 = next(
    row["sha256"] for row in POLICY["recognized_non_authoritative_versions"]
    if row["observation_id"] == "dip1b_data_corr_1_current_observation")


@pytest.fixture(autouse=True)
def _mismatched_source(tmp_path, settings):
    root = tmp_path / "repository"
    source = root / SOURCE_PATH
    source.parent.mkdir(parents=True)
    source.write_bytes((REPOSITORY_ROOT / SOURCE_PATH).read_bytes())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == OBSERVED_SHA256
    settings.INTELLIGENCE_SOURCE_ROOTS = {
        **settings.INTELLIGENCE_SOURCE_ROOTS, "repository": root,
    }
    settings.INTELLIGENCE_ALLOWED_SOURCE_PREFIXES = {
        **settings.INTELLIGENCE_ALLOWED_SOURCE_PREFIXES,
        "repository": ("var/design_intelligence/audits/dip0c",),
    }
    settings.DECISION_EVENT_HMAC_KEYS = {"integrity-test": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "integrity-test"
    signing.reset_registry()
    yield source
    signing.reset_registry()


def _reviewer(username="brand-integrity-reviewer"):
    granter = User.objects.create_user(username=f"grant-{username}")
    user = User.objects.create_user(username=username)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    ReviewerRoleAssignment.objects.create(
        user=user, role=authz.BRAND_ADMIN, granted_by=granter,
        granted_at=timezone.now(), expires_at=timezone.now() + timezone.timedelta(days=2),
        grant_source=GRANT_TEST_FIXTURE, grant_reason="evidence integrity test")
    return user


def _brand_candidate(*, affected=True, suffix="00"):
    external_key = f"brand:dip0c3-brand:{suffix}" if affected else f"brand:unrelated:{suffix}"
    item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.BRAND_ASSET, external_key=external_key)
    artifact = SourceArtifact.objects.create(
        source_identifier=f"physical:{suffix}:{affected}",
        source_location=f"repository:materials/{suffix}.ai",
        source_type=SourceArtifact.SourceType.FILE, sha256=("a" if affected else "d") * 64,
        parser_identifier="dip0c.brand", parser_version="0.1.0",
        source_schema_version="dip0c_brand_candidate/1.0")
    evidence = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=artifact, evidence_kind="SOURCE_FILE",
        locator={"path": f"materials/{suffix}.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="b" * 64)
    BrandCandidateProfile.objects.create(
        corpus_item=item, primary_source_artifact=artifact,
        candidate_kind=BrandCandidateProfile.CandidateKind.LOGO,
        observed_brand_label="BBROSE", technical_format=".ai",
        representation_state=BrandCandidateProfile.Representation.VECTOR,
        observed_candidate_data={},
        warning_state=BrandCandidateProfile.Warning.REQUIRES_REVIEW,
        candidate_status=BrandCandidateProfile.Status.UNCONFIRMED)
    batch = ImportBatch.objects.create(
        importer_identifier="bbrose.intelligence.import_dip0_mvp", importer_version="1.0",
        configuration_hash="c" * 64,
        source_manifest_hash=ACCEPTED_IMPORT_MANIFEST_SHA256, scope={})
    if affected:
        ImportRecord.objects.create(
            import_batch=batch,
            stable_source_record_key=f"brand-candidate:dip0c3-brand:{suffix}",
            source_record_hash="e" * 64, source_artifact=artifact, corpus_item=item,
            disposition=ImportRecord.Disposition.CREATED, parser_version="0.1.0",
            source_schema_version="dip0c_brand_candidate/1.0",
            reconciliation_details={"dataset_id": DATASET_ID, "candidate_only": True})
    candidate = ReviewCandidate.objects.create(
        corpus_item=item, review_type=ReviewCandidate.ReviewType.BRAND_IDENTITY,
        priority=75, source_import_batch=batch,
        review_manifest_id="dip1b_review_manifest/1.0", machine_confidence_summary={})
    return item, candidate, evidence, artifact


def _assessment_payload(item, candidate, evidence, assessment):
    return {
        "corpus_item_uuid": str(item.pk),
        "review_candidate_uuid": str(candidate.pk),
        "assessment": assessment,
        "explanation": "The exact source identity was checked.",
        "evidence_reference_ids": [str(evidence.pk)],
    }


def test_full_hash_mismatch_is_stale_ignored_output_and_path_does_not_override_identity(
        _mismatched_source):
    status = EvidenceIntegrityResolver().inspect_policy(CORRECTION_ID)
    version = status.unresolved_source_versions[0]
    assert status.classification == STALE_IGNORED_OUTPUT
    assert status.status == REVIEW_REQUIRED
    assert version.status == STALE_GENERATED_OUTPUT
    assert "DECLARED_HASH_MISMATCH" in version.reason_codes
    assert len(version.stable_source_keys) == 21
    assert version.expected_sha256 == EXPECTED_SHA256
    assert version.observed_sha256 == hashlib.sha256(
        _mismatched_source.read_bytes()).hexdigest() == OBSERVED_SHA256
    assert version.locator["path"] == SOURCE_PATH


def test_stale_output_classification_is_deterministic():
    classifications = {
        EvidenceIntegrityResolver(evaluated_at="2026-07-16T08:27:13Z")
        .inspect_policy(CORRECTION_ID).classification
        for _ in range(3)
    }
    assert classifications == {STALE_IGNORED_OUTPUT}


def test_observed_and_expected_full_hashes_are_reproduced_in_memory(_mismatched_source):
    rows = json.loads(_mismatched_source.read_text(encoding="utf-8"))
    assert len(rows) == 21
    observed = json.dumps(rows, ensure_ascii=False, indent=2).encode()
    assert len(observed) == 101488
    assert hashlib.sha256(observed).hexdigest() == OBSERVED_SHA256
    accepted_timestamps = {
        0: "2026-07-16T04:23:25+00:00",
        1: "2026-07-16T04:23:28+00:00",
        **{index: "2026-07-16T04:23:30+00:00" for index in range(2, 9)},
        9: "2026-07-16T04:23:31+00:00",
        10: "2026-07-16T04:23:31+00:00",
        15: "2026-07-16T04:23:31+00:00",
        16: "2026-07-16T04:23:31+00:00",
        17: "2026-07-16T04:23:32+00:00",
        18: "2026-07-16T04:23:32+00:00",
    }

    def replace_extraction_timestamp(value, timestamp):
        if isinstance(value, dict):
            if "extracted_at" in value:
                value["extracted_at"] = timestamp
            for child in value.values():
                replace_extraction_timestamp(child, timestamp)
        elif isinstance(value, list):
            for child in value:
                replace_extraction_timestamp(child, timestamp)

    for index, timestamp in accepted_timestamps.items():
        replace_extraction_timestamp(rows[index], timestamp)
    reconstructed = json.dumps(rows, ensure_ascii=False, indent=2).encode()
    assert len(reconstructed) == 101488
    assert hashlib.sha256(reconstructed).hexdigest() == EXPECTED_SHA256


def test_importer_rejects_unexpected_brand_source_bytes_with_both_hashes(
        _mismatched_source):
    observed = hashlib.sha256(_mismatched_source.read_bytes()).hexdigest()
    with pytest.raises(ManifestError) as caught:
        resolve_source({
            "root": "repository", "path": SOURCE_PATH, "sha256": EXPECTED_SHA256,
            "source_type": "JSON", "media_type": "application/json",
        }, label="brand.data_source")
    message = str(caught.value)
    assert EXPECTED_SHA256 in message and observed in message


def test_integrity_inspection_rewrites_neither_frozen_manifest_nor_observed_output(
        _mismatched_source):
    manifest_before = Path(DEFAULT_MANIFEST).read_bytes()
    source_before = _mismatched_source.read_bytes()
    EvidenceIntegrityResolver().inspect_policy(CORRECTION_ID)
    assert Path(DEFAULT_MANIFEST).read_bytes() == manifest_before
    assert _mismatched_source.read_bytes() == source_before


def test_invalid_versioned_declaration_fails_closed_as_unresolved(tmp_path):
    declaration = tmp_path / "invalid.json"
    declaration.write_text(json.dumps({"entries": []}), encoding="utf-8")
    status = EvidenceIntegrityResolver(manifest_path=declaration).inspect_policy(CORRECTION_ID)
    assert status.classification == UNRESOLVED
    assert "FROZEN_EVIDENCE_DECLARATION_UNRESOLVED" in status.reason_codes


def test_read_only_reconciliation_is_idempotent_and_source_versions_are_immutable():
    item, candidate, _, artifact = _brand_candidate()
    ImportRecord.objects.create(
        import_batch=candidate.source_import_batch,
        stable_source_record_key="source:dip0c3-brand:00",
        source_record_hash="9" * 64, source_artifact=artifact,
        disposition=ImportRecord.Disposition.CREATED, parser_version="0.1.0",
        source_schema_version="dip0c_brand_candidate/1.0",
        reconciliation_details={"dataset_id": DATASET_ID,
                                "source_declaration": True})
    before = {
        "artifact": SourceArtifact.objects.get(pk=artifact.pk).sha256,
        "imports": list(ImportRecord.objects.values_list(
            "pk", "source_record_hash", "disposition")),
    }
    first = reconcile_brand_candidate_integrity()
    second = reconcile_brand_candidate_integrity()
    assert first == second
    assert first["database"]["affected_candidate_items"] == 1
    assert first["database"]["latest_candidate_records"] == 1
    assert first["database"]["accepted_candidate_records"] == 1
    assert first["database"]["source_declaration_record_versions"] == 1
    assert first["database"]["linked_import_record_versions"] == 2
    assert first["database"]["accepted_source_declaration_records"] == 1
    assert len(first["dependencies"][0]["import_records"]) == 2
    assert first["database_changed"] is False
    assert first["authority"]["affected_decision_events"] == 0
    assert first["authority"]["affected_human_assertion_projections"] == 0
    assert first["authority"]["affected_allowed_permissions"] == 0
    assert first["projection_publication_before"] == first["projection_publication_after"]
    assert SourceArtifact.objects.get(pk=artifact.pk).sha256 == before["artifact"]
    assert list(ImportRecord.objects.values_list(
        "pk", "source_record_hash", "disposition")) == before["imports"]
    assert item and DecisionEvent.objects.count() == 0
    assert OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).count() == 0


def test_reconciliation_command_repeats_exactly_without_writes():
    _brand_candidate()
    outputs = []
    for _ in range(2):
        stream = io.StringIO()
        call_command("reconcile_dip1b_brand_candidate_hash", "--json", stdout=stream)
        outputs.append(json.loads(stream.getvalue()))
    assert outputs[0] == outputs[1]
    assert outputs[0]["database_changed"] is False
    assert DecisionEvent.objects.count() == 0


def test_browser_surfaces_review_required_hash_warning_for_affected_candidate():
    item, candidate, _, _ = _brand_candidate()
    reviewer = _reviewer()
    client = Client()
    client.force_login(reviewer)
    for url in (
            reverse("intelligence:corpus-detail", args=[item.pk]),
            reverse("intelligence:review-detail", args=[candidate.pk])):
        response = client.get(url, secure=True)
        assert response.status_code == 200
        assert b"STALE_IGNORED_OUTPUT" in response.content
        assert b"REVIEW REQUIRED" in response.content
        assert EXPECTED_SHA256.encode() in response.content
        assert OBSERVED_SHA256.encode() in response.content
        assert b"Machine classifications are non-authoritative" in response.content
        assert b"Operational permissions remain denied" in response.content


def test_affected_evidence_sufficient_and_classification_fail_before_event_append():
    item, candidate, evidence, _ = _brand_candidate()
    reviewer = _reviewer()
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    with pytest.raises(AssertionValidationError, match="EVIDENCE_SUFFICIENT"):
        record_intelligence_evidence_assessment(
            user=reviewer,
            payload=_assessment_payload(item, candidate, evidence, "EVIDENCE_SUFFICIENT"))
    with pytest.raises(AssertionValidationError, match="evidence integrity"):
        record_intelligence_classification(user=reviewer, payload={
            "corpus_item_uuid": str(item.pk),
            "review_candidate_uuid": str(candidate.pk),
            "classification_domain": "brand_identity_candidate",
            "classification_label": "BBROSE_CANDIDATE",
            "normalized_value": {"brand": "BBROSE"},
            "explanation": "Observed wordmark evidence.",
            "evidence_reference_ids": [str(evidence.pk)],
            "machine_classification_ids": [],
        })
    assert DecisionEvent.objects.count() == 0
    assert OperationalPermissionProjection.objects.count() == 0


def test_current_21_candidate_source_scope_remains_governance_blocked():
    item, candidate, evidence, _ = _brand_candidate()
    reviewer = _reviewer("blocked-governance-reviewer")
    result = evaluate_evidence_integrity(item, [evidence])
    assert len(EvidenceIntegrityResolver().inspect_policy(
        CORRECTION_ID).unresolved_source_versions[0].stable_source_keys) == 21
    assert result.status == REVIEW_REQUIRED
    before = DecisionEvent.objects.count()
    with pytest.raises(GovernanceEligibilityError, match="NOT_VERIFIED"):
        record_governance_attestation(
            user=reviewer, corpus_item_id=str(item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_category=CATEGORY_TECHNICAL_AND_BRAND,
            evidence_reference_ids=[str(evidence.pk)],
            review_expiry=timezone.now() + timezone.timedelta(days=1))
    assert DecisionEvent.objects.count() == before
    client = Client()
    client.force_login(reviewer)
    response = client.get(
        reverse("intelligence:review-detail", args=[candidate.pk]), secure=True)
    assert response.status_code == 200
    assert b"DUAL-CONTROL GOVERNANCE" in response.content
    assert b"Governance attestation and finalization are unavailable" in response.content
    assert b"Append signed governance attestation" not in response.content


@pytest.mark.parametrize("assessment", [
    "EVIDENCE_INSUFFICIENT", "CLARIFICATION_REQUIRED",
])
def test_affected_insufficient_and_clarification_assessments_remain_available(assessment):
    item, candidate, evidence, _ = _brand_candidate(suffix=assessment.lower())
    reviewer = _reviewer(f"reviewer-{assessment.lower()}")
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    event = record_intelligence_evidence_assessment(
        user=reviewer,
        payload=_assessment_payload(item, candidate, evidence, assessment))
    assert event.payload["assessment"] == assessment
    assert event.payload["authority_effect"] == "NONE"
    assert OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).count() == 0


def test_general_resolver_does_not_let_verified_physical_evidence_cure_data_mismatch():
    item, _, evidence, artifact = _brand_candidate()
    result = evaluate_evidence_integrity(item, [evidence])
    assert result.status == REVIEW_REQUIRED
    assert result.classification == STALE_IGNORED_OUTPUT
    assert str(artifact.pk) in result.affected_source_artifact_ids
    assert any(row.source_role == "EVIDENCE_REFERENCE"
               for row in result.verified_source_versions)
    assert any(row.source_role == "DATA_SOURCE"
               for row in result.unresolved_source_versions)
    assert result.grants_authority is False


def test_general_resolver_keeps_unrelated_persisted_evidence_verified():
    item, _, evidence, artifact = _brand_candidate(affected=False, suffix="general")
    result = evaluate_evidence_integrity(item, [evidence])
    assert result.status == VERIFIED
    assert result.classification == VERIFIED
    assert result.affected_source_artifact_ids == ()
    assert result.expected_hashes == (artifact.sha256,)
    assert result.grants_authority is False


def test_policy_matching_is_content_driven_not_filename_driven(
        _mismatched_source, tmp_path, settings):
    manifest = json.loads(Path(DEFAULT_MANIFEST).read_text(encoding="utf-8"))
    alternate_path = "var/design_intelligence/audits/dip0c/alternate/candidates.json"
    alternate_source = Path(settings.INTELLIGENCE_SOURCE_ROOTS["repository"]) / alternate_path
    alternate_source.parent.mkdir(parents=True)
    alternate_source.write_bytes(_mismatched_source.read_bytes())
    for entry in manifest["entries"]:
        data_source = entry.get("data_source") or {}
        source = data_source.get("source") or {}
        if source.get("sha256") == EXPECTED_SHA256:
            source["path"] = alternate_path
            data_source["locator"]["value"]["path"] = alternate_path
    manifest_path = tmp_path / "renamed-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    registry = json.loads(Path(DEFAULT_REGISTRY).read_text(encoding="utf-8"))
    registry["policies"][0]["root_of_trust"]["current_frozen_manifest_sha256"] = (
        hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    result = EvidenceIntegrityResolver(
        manifest_path=manifest_path, registry_path=registry_path,
    ).inspect_policy(CORRECTION_ID)
    assert result.classification == STALE_IGNORED_OUTPUT
    assert result.unresolved_source_versions[0].locator["path"] == alternate_path


def test_unrelated_candidate_remains_usable_for_evidence_assessment():
    item, candidate, evidence, _ = _brand_candidate(affected=False, suffix="other")
    reviewer = _reviewer("unrelated-brand-reviewer")
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    event = record_intelligence_evidence_assessment(
        user=reviewer,
        payload=_assessment_payload(item, candidate, evidence, "EVIDENCE_SUFFICIENT"))
    assert event.payload["assessment"] == "EVIDENCE_SUFFICIENT"
    assert event.payload["authority_effect"] == "NONE"
    assert OperationalPermissionProjection.objects.count() == 0


def test_projector_fails_closed_if_signed_sufficient_evidence_becomes_affected():
    item, candidate, evidence, artifact = _brand_candidate(
        affected=False, suffix="projector")
    reviewer = _reviewer("projector-brand-reviewer")
    claim_review_candidate(user=reviewer, candidate_id=candidate.pk)
    record_intelligence_evidence_assessment(
        user=reviewer,
        payload=_assessment_payload(item, candidate, evidence, "EVIDENCE_SUFFICIENT"))
    ImportRecord.objects.create(
        import_batch=candidate.source_import_batch,
        stable_source_record_key="brand-candidate:dip0c3-brand:00",
        source_record_hash="f" * 64, source_artifact=artifact, corpus_item=item,
        disposition=ImportRecord.Disposition.CREATED, parser_version="0.1.0",
        source_schema_version="dip0c_brand_candidate/1.0",
        reconciliation_details={"dataset_id": DATASET_ID, "candidate_only": True})
    with pytest.raises(ProjectionValidationError, match="INTEGRITY_UNRESOLVED"):
        build_projection()
    assert OperationalPermissionProjection.objects.count() == 0


def test_reconciliation_preserves_projection_publication_and_all_projection_rows():
    _brand_candidate()
    publication_before = list(ProjectionPublicationState.objects.values())
    projection_before = list(HumanAssertionProjection.objects.values())
    report = reconcile_brand_candidate_integrity()
    assert report["projection_publication_before"] == report["projection_publication_after"]
    assert list(ProjectionPublicationState.objects.values()) == publication_before
    assert list(HumanAssertionProjection.objects.values()) == projection_before
    assert report["database_changed"] is False
