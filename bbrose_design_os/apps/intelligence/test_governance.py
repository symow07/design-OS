from __future__ import annotations

import inspect
import uuid

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
import pytest

from apps.accounts import authz_policy as authz
from apps.accounts.attestation import (
    CATEGORY_COLOR_AND_BRAND,
    CATEGORY_RIGHTS_AND_OWNERSHIP,
    CATEGORY_RIGHTS_AND_USE,
    CATEGORY_TECHNICAL_AND_BRAND,
)
from apps.accounts.decision_chain import verify_chain
from apps.accounts.models import (
    GRANT_TEST_FIXTURE,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from apps.accounts.security import signing

from .governance import (
    CANONICAL_BRAND_ASSET,
    GLOBAL_PRIMARY_LOGO,
    GLOBAL_PRIMARY_PALETTE,
    GLOBAL_WORDMARK,
    GOVERNANCE_ATTESTATION_SCHEMA,
    GOVERNANCE_DECISION_SCHEMA,
    GOVERNANCE_SCOPE_SCHEMA,
    MARKET,
    PRIMARY_BRAND_PALETTE,
    PRODUCT_FAMILY,
    GovernanceAuthorizationDenied,
    GovernanceConflict,
    GovernanceValidationError,
    finalize_governance_decision,
    normalize_governance_scope,
    record_governance_attestation,
    resolve_governance_candidate,
    revoke_governance_decision,
)
from .models import (
    BrandCandidateProfile,
    CorpusItem,
    EvidenceReference,
    OperationalPermissionProjection,
    ProvenanceRecord,
    ReviewCandidate,
    SourceArtifact,
)
from .permissions import evaluate_operational_permission

pytestmark = pytest.mark.django_db
User = get_user_model()
KEY = "4" * 32
DAY = timezone.timedelta(days=1)


@pytest.fixture(autouse=True)
def _governance_signing(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"governance-test": KEY}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "governance-test"
    signing.reset_registry()
    yield
    signing.reset_registry()


def reviewer(*roles, username=None):
    username = username or f"governance-reviewer-{User.objects.count()}"
    granter = User.objects.create_user(username=f"grant-{username}")
    user = User.objects.create_user(username=username)
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    now = timezone.now()
    for role in roles:
        ReviewerRoleAssignment.objects.create(
            user=user, role=role, granted_by=granter, granted_at=now,
            expires_at=now + 30 * DAY, grant_source=GRANT_TEST_FIXTURE,
            grant_reason="DIP-1B-4B test fixture")
    return user


def candidate(*, palette=False, external_key=None):
    index = CorpusItem.objects.count()
    external_key = external_key or f"governance:{'palette' if palette else 'brand'}:{index}"
    item = CorpusItem.objects.create(
        item_kind=(CorpusItem.Kind.BRAND_PALETTE if palette
                   else CorpusItem.Kind.BRAND_ASSET),
        external_key=external_key)
    artifact = SourceArtifact.objects.create(
        source_identifier=f"source:{external_key}",
        source_location=f"logical:{external_key}",
        source_type=SourceArtifact.SourceType.FILE,
        sha256=f"{(index % 9) + 1}" * 64,
        parser_identifier="governance.test", parser_version="1.0",
        source_schema_version="governance_test_source/1.0")
    evidence = EvidenceReference.objects.create(
        corpus_item=item, source_artifact=artifact, evidence_kind="SOURCE_FILE",
        locator={"path": f"fixtures/governance-{index}.ai"},
        locator_schema_version="source_file/1.0", evidence_hash="a" * 64)
    BrandCandidateProfile.objects.create(
        corpus_item=item, primary_source_artifact=artifact,
        candidate_kind=(BrandCandidateProfile.CandidateKind.PALETTE if palette
                        else BrandCandidateProfile.CandidateKind.LOGO),
        observed_brand_label="BBROSE", technical_format="ASE" if palette else "AI",
        representation_state=BrandCandidateProfile.Representation.UNKNOWN,
        observed_candidate_data={},
        warning_state=BrandCandidateProfile.Warning.REQUIRES_REVIEW,
        candidate_status=BrandCandidateProfile.Status.UNCONFIRMED)
    review = ReviewCandidate.objects.create(
        corpus_item=item,
        review_type=(ReviewCandidate.ReviewType.PALETTE_OBSERVATION if palette
                     else ReviewCandidate.ReviewType.BRAND_IDENTITY),
        review_manifest_id="dip1b4b-test/1.0", machine_confidence_summary={})
    return item, review, evidence


def pair(item, evidence, *, palette=False, scope=None, same_user=False,
         expiry=None):
    governance_type = PRIMARY_BRAND_PALETTE if palette else CANONICAL_BRAND_ASSET
    scope = scope or ({"scope_type": GLOBAL_PRIMARY_PALETTE} if palette else {
        "scope_type": GLOBAL_PRIMARY_LOGO})
    categories = ((CATEGORY_COLOR_AND_BRAND, CATEGORY_RIGHTS_AND_USE) if palette else (
        CATEGORY_TECHNICAL_AND_BRAND, CATEGORY_RIGHTS_AND_OWNERSHIP))
    if same_user:
        first_user = second_user = reviewer(
            authz.DESIGN_REVIEWER, authz.LEGAL_REVIEWER)
    else:
        first_user = reviewer(authz.DESIGN_REVIEWER)
        second_user = reviewer(authz.LEGAL_REVIEWER)
    kwargs = {
        "corpus_item_id": str(item.pk), "governance_type": governance_type,
        "raw_scope": scope, "evidence_reference_ids": [str(evidence.pk)],
        "review_expiry": expiry or timezone.now() + 10 * DAY,
    }
    first = record_governance_attestation(
        user=first_user, attestation_category=categories[0], **kwargs)
    second = record_governance_attestation(
        user=second_user, attestation_category=categories[1], **kwargs)
    return first, second


def finalize(item, evidence, *, palette=False, scope=None, supersedes=None):
    governance_type = PRIMARY_BRAND_PALETTE if palette else CANONICAL_BRAND_ASSET
    scope = scope or ({"scope_type": GLOBAL_PRIMARY_PALETTE} if palette else {
        "scope_type": GLOBAL_PRIMARY_LOGO})
    attestations = pair(item, evidence, palette=palette, scope=scope)
    finalizer = reviewer(authz.BRAND_ADMIN)
    event = finalize_governance_decision(
        user=finalizer, corpus_item_id=str(item.pk), governance_type=governance_type,
        raw_scope=scope,
        attestation_event_ids=[row.event_id for row in attestations],
        supersedes_final_event_id=supersedes)
    return event, attestations, finalizer


def assert_no_operational_permissions(item):
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()
    for permission in (
            OperationalPermissionProjection.Permission.RETRIEVAL,
            OperationalPermissionProjection.Permission.AUTOMATIC_USE,
            OperationalPermissionProjection.Permission.EXPORT,
            OperationalPermissionProjection.Permission.PRODUCTION):
        assert not evaluate_operational_permission(item, permission).allowed


def test_scope_vocabulary_is_strict_versioned_and_deterministic():
    assert normalize_governance_scope(CANONICAL_BRAND_ASSET, {
        "scope_type": " global_wordmark "}) == {
            "scope_schema": GOVERNANCE_SCOPE_SCHEMA,
            "scope_type": GLOBAL_WORDMARK,
        }
    assert normalize_governance_scope(CANONICAL_BRAND_ASSET, {
        "scope_type": PRODUCT_FAMILY, "product_family_id": " rose-care "}) == {
            "scope_schema": GOVERNANCE_SCOPE_SCHEMA,
            "scope_type": PRODUCT_FAMILY, "product_family_id": "ROSE-CARE",
        }
    assert normalize_governance_scope(PRIMARY_BRAND_PALETTE, {
        "scope_type": MARKET, "market_id": " cn "})["market_id"] == "CN"
    with pytest.raises(GovernanceValidationError, match="never inferred"):
        normalize_governance_scope(CANONICAL_BRAND_ASSET, {})
    with pytest.raises(GovernanceValidationError):
        normalize_governance_scope(CANONICAL_BRAND_ASSET, {
            "scope_type": "ARBITRARY_FREEFORM"})
    with pytest.raises(GovernanceValidationError):
        normalize_governance_scope(CANONICAL_BRAND_ASSET, {
            "scope_type": PRODUCT_FAMILY})
    with pytest.raises(GovernanceValidationError):
        normalize_governance_scope(PRIMARY_BRAND_PALETTE, {
            "scope_type": GLOBAL_PRIMARY_LOGO})


def test_attestation_service_has_no_caller_authority_or_integrity_override():
    parameters = set(inspect.signature(record_governance_attestation).parameters)
    assert not parameters.intersection({
        "actor_id", "role_used", "authorization_snapshot", "authz_snapshot",
        "integrity_status", "decision_scope_hash",
    })


def test_test_only_evidence_is_ineligible_before_any_event_append():
    item, _review, evidence = candidate()
    evidence.is_test_only = True
    evidence.save(update_fields=("is_test_only",))
    with pytest.raises(GovernanceValidationError, match="non-test-only"):
        record_governance_attestation(
            user=reviewer(authz.DESIGN_REVIEWER), corpus_item_id=str(item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_category=CATEGORY_TECHNICAL_AND_BRAND,
            evidence_reference_ids=[str(evidence.pk)],
            review_expiry=timezone.now() + DAY)
    assert DecisionEvent.objects.count() == 0


def test_verified_candidate_dual_control_and_canonical_final_append_exactly_one_event():
    item, _review, evidence = candidate()
    first, second = pair(item, evidence)
    before = DecisionEvent.objects.count()
    finalizer = reviewer(authz.BRAND_ADMIN)
    event = finalize_governance_decision(
        user=finalizer, corpus_item_id=str(item.pk),
        governance_type=CANONICAL_BRAND_ASSET,
        raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
        attestation_event_ids=[first.event_id, second.event_id])
    assert DecisionEvent.objects.count() == before + 1
    assert event.action == authz.FINALIZE_CANONICAL_BRAND_ASSET
    assert event.actor == finalizer and event.role_used == authz.BRAND_ADMIN
    assert event.payload["governance_decision_schema"] == GOVERNANCE_DECISION_SCHEMA
    assert event.payload["selected_corpus_item_id"] == str(item.pk)
    assert event.payload["authority_effect"] == "NONE"
    assert event.payload["authz_snapshot"]["policy_version"] == "authz/1.4"
    assert event.payload["attestation_event_ids"] == [first.event_id, second.event_id]
    assert verify_chain().ok
    assert_no_operational_permissions(item)


def test_valid_palette_final_uses_palette_pair_and_grants_nothing():
    item, _review, evidence = candidate(palette=True)
    event, attestations, _finalizer = finalize(item, evidence, palette=True)
    assert event.action == authz.FINALIZE_PRIMARY_BRAND_PALETTE
    assert [row.payload["attestation_category"] for row in attestations] == [
        CATEGORY_COLOR_AND_BRAND, CATEGORY_RIGHTS_AND_USE]
    assert_no_operational_permissions(item)


def test_same_actor_wrong_binding_expiry_and_scope_mismatch_fail_closed():
    item, _review, evidence = candidate()
    same = pair(item, evidence, same_user=True)
    finalizer = reviewer(authz.BRAND_ADMIN)
    with pytest.raises(GovernanceValidationError, match="same authenticated user"):
        finalize_governance_decision(
            user=finalizer, corpus_item_id=str(item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_event_ids=[row.event_id for row in same])

    other_item, _other_review, other_evidence = candidate()
    first = record_governance_attestation(
        user=reviewer(authz.DESIGN_REVIEWER), corpus_item_id=str(other_item.pk),
        governance_type=CANONICAL_BRAND_ASSET,
        raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
        attestation_category=CATEGORY_TECHNICAL_AND_BRAND,
        evidence_reference_ids=[str(other_evidence.pk)],
        review_expiry=timezone.now() + DAY)
    second = record_governance_attestation(
        user=reviewer(authz.LEGAL_REVIEWER), corpus_item_id=str(other_item.pk),
        governance_type=CANONICAL_BRAND_ASSET,
        raw_scope={"scope_type": GLOBAL_WORDMARK},
        attestation_category=CATEGORY_RIGHTS_AND_OWNERSHIP,
        evidence_reference_ids=[str(other_evidence.pk)],
        review_expiry=timezone.now() + DAY)
    with pytest.raises(GovernanceValidationError, match="decision_scope_hash differs"):
        finalize_governance_decision(
            user=finalizer, corpus_item_id=str(other_item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_event_ids=[first.event_id, second.event_id])

def test_expired_attestation_and_wrong_category_are_rejected_without_final_event():
    item, _review, evidence = candidate()
    now = timezone.now()
    common = {
        "corpus_item_id": str(item.pk),
        "governance_type": CANONICAL_BRAND_ASSET,
        "raw_scope": {"scope_type": GLOBAL_PRIMARY_LOGO},
        "evidence_reference_ids": [str(evidence.pk)],
        "valid_from": now - 2 * DAY,
        "review_expiry": now - DAY,
    }
    first = record_governance_attestation(
        user=reviewer(authz.DESIGN_REVIEWER),
        attestation_category=CATEGORY_TECHNICAL_AND_BRAND, **common)
    second = record_governance_attestation(
        user=reviewer(authz.LEGAL_REVIEWER),
        attestation_category=CATEGORY_RIGHTS_AND_OWNERSHIP, **common)
    count = DecisionEvent.objects.count()
    with pytest.raises(GovernanceValidationError, match="EXPIRED"):
        finalize_governance_decision(
            user=reviewer(authz.BRAND_ADMIN), corpus_item_id=str(item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_event_ids=[first.event_id, second.event_id])
    assert DecisionEvent.objects.count() == count
    with pytest.raises(GovernanceValidationError, match="not valid"):
        record_governance_attestation(
            user=reviewer(authz.DESIGN_REVIEWER), corpus_item_id=str(item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_category=CATEGORY_COLOR_AND_BRAND,
            evidence_reference_ids=[str(evidence.pk)],
            review_expiry=timezone.now() + DAY)


def test_system_admin_cannot_attest_or_finalize_but_can_only_reduce():
    item, _review, evidence = candidate()
    with pytest.raises(GovernanceAuthorizationDenied):
        record_governance_attestation(
            user=reviewer(authz.SYSTEM_ADMIN), corpus_item_id=str(item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_category=CATEGORY_TECHNICAL_AND_BRAND,
            evidence_reference_ids=[str(evidence.pk)],
            review_expiry=timezone.now() + DAY)
    first, second = pair(item, evidence)
    with pytest.raises(GovernanceAuthorizationDenied):
        finalize_governance_decision(
            user=reviewer(authz.SYSTEM_ADMIN), corpus_item_id=str(item.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_PRIMARY_LOGO},
            attestation_event_ids=[first.event_id, second.event_id])


def test_redirected_identity_and_cross_scope_replacement_are_rejected():
    item, _review, evidence = candidate()
    legacy_id = uuid.uuid4()
    ProvenanceRecord.objects.create(
        corpus_item=item, source_artifact=evidence.source_artifact,
        provenance_type="CORPUS_IDENTITY_RECONCILIATION",
        normalized_machine_interpretation={
            "legacy_corpus_item_id": str(legacy_id),
            "canonical_corpus_item_id": str(item.pk),
        })
    with pytest.raises(GovernanceValidationError, match="redirected or deprecated"):
        resolve_governance_candidate(str(legacy_id), CANONICAL_BRAND_ASSET)
    first, _pair, _finalizer = finalize(item, evidence)
    replacement, _review2, evidence2 = candidate()
    replacement_attestations = pair(
        replacement, evidence2, scope={"scope_type": GLOBAL_WORDMARK})
    with pytest.raises(GovernanceConflict):
        finalize_governance_decision(
            user=reviewer(authz.BRAND_ADMIN), corpus_item_id=str(replacement.pk),
            governance_type=CANONICAL_BRAND_ASSET,
            raw_scope={"scope_type": GLOBAL_WORDMARK},
            attestation_event_ids=[row.event_id for row in replacement_attestations],
            supersedes_final_event_id=first.event_id)


def test_replacement_and_revocation_are_append_only_and_exactly_bound():
    first_item, _review1, first_evidence = candidate()
    first, _attestations, _finalizer = finalize(first_item, first_evidence)
    second_item, _review2, second_evidence = candidate()
    second, _second_attestations, _second_finalizer = finalize(
        second_item, second_evidence, supersedes=first.event_id)
    assert second.supersedes_event == first
    assert second.payload["supersedes_final_event_id"] == first.event_id
    original_hash = second.content_hash
    revocation = revoke_governance_decision(
        user=reviewer(authz.SYSTEM_ADMIN), final_event_id=second.event_id,
        reason="Emergency withdrawal pending brand review.")
    second.refresh_from_db()
    assert second.content_hash == original_hash
    assert revocation.payload["revoked_final_event_id"] == second.event_id
    assert revocation.payload["revoked_final_content_hash"] == second.content_hash
    assert revocation.supersedes_event_id is None
    with pytest.raises(GovernanceConflict):
        revoke_governance_decision(
            user=reviewer(authz.BRAND_ADMIN), final_event_id=second.event_id,
            reason="Duplicate revocation")
    assert_no_operational_permissions(first_item)
    assert_no_operational_permissions(second_item)


def test_governance_ui_is_separate_post_only_and_csrf_protected():
    item, review, evidence = candidate()
    user = reviewer(authz.DESIGN_REVIEWER)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    detail_url = reverse("intelligence:review-detail", args=[review.pk])
    detail = client.get(detail_url, secure=True)
    assert detail.status_code == 200
    assert b"CANONICAL OR PRIMARY GOVERNANCE STATUS DOES NOT AUTHORIZE OPERATIONAL USE" \
        in detail.content
    assert b"TECHNICAL_AND_BRAND" in detail.content
    assert b"OPERATIONAL PERMISSION" in detail.content
    attest_url = reverse("intelligence:governance-attest", args=[review.pk])
    assert client.get(attest_url, secure=True).status_code == 405
    data = {
        "governance_type": CANONICAL_BRAND_ASSET,
        "scope_type": GLOBAL_PRIMARY_LOGO,
        "scope_identifier": "not-allowed-for-global",
        "attestation_category": CATEGORY_TECHNICAL_AND_BRAND,
        "evidence_reference_ids": str(evidence.pk),
        "review_expiry": (timezone.now() + DAY).isoformat(),
    }
    assert client.post(attest_url, data, secure=True).status_code == 403
    token = client.cookies["csrftoken"].value
    response = client.post(
        attest_url, data, secure=True, HTTP_X_CSRFTOKEN=token,
        HTTP_REFERER=f"https://testserver{detail_url}")
    assert response.status_code == 400
    assert DecisionEvent.objects.count() == 0
    data["scope_identifier"] = ""
    response = client.post(
        attest_url, data, secure=True, HTTP_X_CSRFTOKEN=token,
        HTTP_REFERER=f"https://testserver{detail_url}")
    assert response.status_code == 302
    assert DecisionEvent.objects.get().payload[
        "governance_attestation_schema"] == GOVERNANCE_ATTESTATION_SCHEMA
    assert_no_operational_permissions(item)
