from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.decision_chain import append_decision
from apps.accounts.models import (
    GRANT_AUTHORIZED_SERVICE, DecisionChainHead, DecisionEvent, ReviewerProfile,
    ReviewerRoleAssignment)
from apps.core.models import Brand, ColorSystem, DesignReference, MaterialSystem

from .import_services import record_import_attempt, record_source_version
from .legacy_signals import LEGACY_SIGNAL_NON_AUTHORITATIVE, characterize_legacy_signals
from .models import (
    CorpusItem, EvidenceReference, ImportBatch, ImportRecord,
    OperationalPermissionProjection as Projection, ProvenanceRecord, SourceArtifact)
from .permissions import PERMISSION_PROJECTION_VERSION, evaluate_operational_permission

pytestmark = pytest.mark.django_db
H1 = "1" * 64
H2 = "2" * 64


def item():
    return CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET, external_key="asset:1")


def artifact(**overrides):
    values = dict(source_identifier="inventory:a", source_location="/old/a.ai",
                  source_type=SourceArtifact.SourceType.FILE,
                  media_type="application/postscript", sha256=H1, byte_size=10,
                  parser_identifier="dip0", parser_version="1",
                  source_schema_version="1")
    values.update(overrides)
    return SourceArtifact.objects.create(**values)


def batch(name="b"):
    return ImportBatch.objects.create(
        importer_identifier="dip1b-test", importer_version="1",
        configuration_hash=H1, source_manifest_hash=H2, scope={"name": name})


def test_corpus_item_is_identity_not_mutable_authority():
    names = {f.name for f in CorpusItem._meta.fields}
    for forbidden in ("approved", "canonical", "licensed", "owned", "retrieval_enabled",
                      "automatic_use_enabled"):
        assert forbidden not in names


def test_source_path_is_not_content_identity_and_changed_hash_versions():
    first, created = record_source_version(
        source_identifier="s", source_location="/a", source_type="FILE", sha256=H1,
        parser_identifier="p", parser_version="1", source_schema_version="1")
    same, created_again = record_source_version(
        source_identifier="s", source_location="/moved", source_type="FILE", sha256=H1,
        parser_identifier="p", parser_version="1", source_schema_version="1")
    changed, changed_created = record_source_version(
        source_identifier="s", source_location="/moved", source_type="FILE", sha256=H2,
        parser_identifier="p", parser_version="1", source_schema_version="1")
    assert created and not created_again and same.pk == first.pk
    assert changed_created and changed.supersedes_source_artifact_id == first.pk
    assert first.content_identity == same.content_identity and changed.content_identity != H1


def test_evidence_and_provenance_preserve_source_without_granting_rights():
    old = artifact()
    ref = EvidenceReference.objects.create(
        corpus_item=item(), source_artifact=old, evidence_kind="JSON_RECORD",
        locator={"record_id": "17", "field": "sha256"}, locator_schema_version="1",
        observed_value=H1, evidence_hash=H2)
    artifact(source_identifier="inventory:a", source_location="/new/a.ai", sha256=H2,
             supersedes_source_artifact=old)
    assert ref.source_artifact_id == old.pk
    fields = {f.name for f in ProvenanceRecord._meta.fields}
    assert not fields.intersection({"licensed", "owned", "approved", "production"})
    ProvenanceRecord.objects.create(
        source_artifact=old, provenance_type="NEARBY_LICENCE_FILE",
        raw_statement="licence.txt was nearby",
        normalized_machine_interpretation={"possible_match": True}, confidence="0.5")
    assert Projection.objects.count() == 0


def test_import_idempotency_versioning_and_failure_preserve_prior():
    source = artifact()
    corpus = item()
    first, made = record_import_attempt(
        import_batch=batch("1"), stable_source_record_key="r1", source_record_hash=H1,
        parser_version="1", source_schema_version="1", source_artifact=source,
        corpus_item=corpus)
    retry, made_retry = record_import_attempt(
        import_batch=first.import_batch, stable_source_record_key="r1",
        source_record_hash=H1, parser_version="1", source_schema_version="1")
    unchanged, _ = record_import_attempt(
        import_batch=batch("2"), stable_source_record_key="r1", source_record_hash=H1,
        parser_version="1", source_schema_version="1")
    changed, _ = record_import_attempt(
        import_batch=batch("3"), stable_source_record_key="r1", source_record_hash=H2,
        parser_version="1", source_schema_version="1")
    failed, _ = record_import_attempt(
        import_batch=batch("4"), stable_source_record_key="r1", source_record_hash="3" * 64,
        parser_version="1", source_schema_version="1",
        disposition=ImportRecord.Disposition.FAILED)
    assert made and not made_retry and retry.pk == first.pk
    assert unchanged.disposition == "UNCHANGED" and unchanged.corpus_item_id == corpus.pk
    assert changed.disposition == "NEW_VERSION" and changed.prior_import_record_id == unchanged.pk
    assert failed.disposition == "FAILED" and first.corpus_item_id == corpus.pk
    assert DecisionEvent.objects.count() == 0 and Projection.objects.count() == 0


@pytest.mark.parametrize("state", (
    Projection.State.DENIED, Projection.State.QUARANTINED,
    Projection.State.REVIEW_REQUIRED, Projection.State.EXPIRED))
def test_default_deny_states(state):
    corpus = item()
    assert not evaluate_operational_permission(corpus, Projection.Permission.RETRIEVAL).allowed
    p = Projection.objects.create(
        corpus_item=corpus, permission_type=Projection.Permission.RETRIEVAL,
        effective_state=state, projection_version=PERMISSION_PROJECTION_VERSION,
        reason_code="test")
    assert not evaluate_operational_permission(corpus, Projection.Permission.RETRIEVAL).allowed
    p.effective_state = Projection.State.ALLOWED
    p.expires_at = timezone.now() - timezone.timedelta(seconds=1)
    p.save()
    assert not evaluate_operational_permission(corpus, Projection.Permission.RETRIEVAL).allowed


def test_unknown_permission_and_unverified_allowed_projection_deny():
    corpus = item()
    assert not evaluate_operational_permission(corpus, "UNKNOWN").allowed
    scoped = evaluate_operational_permission(
        corpus, Projection.Permission.RETRIEVAL, scope=("UNREGISTERED", "x"))
    assert not scoped.allowed and scoped.reason_code == "UNKNOWN_SCOPE"
    Projection.objects.create(
        corpus_item=corpus, permission_type=Projection.Permission.EXPORT,
        effective_state=Projection.State.ALLOWED,
        projection_version=PERMISSION_PROJECTION_VERSION, reason_code="direct edit")
    result = evaluate_operational_permission(corpus, Projection.Permission.EXPORT)
    assert not result.allowed and result.reason_code == "UNVERIFIED_PROJECTION_CHECKPOINT"


def test_automatic_use_requires_separate_retrieval_permission():
    User = get_user_model()
    user = User.objects.create_user(username="intel-granter", password="x")
    granter = User.objects.create_user(username="intel-bootstrap", password="x")
    ReviewerProfile.objects.create(user=user, reviewer_enabled=True)
    role = next(r for r in authz.ROLES if r in authz.POLICY[authz.GRANT_PERMISSION])
    ReviewerRoleAssignment(
        user=user, role=role, granted_by=granter, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=1),
        grant_source=GRANT_AUTHORIZED_SERVICE, grant_reason="test").save()
    corpus = item()
    ev = append_decision(
        user=user, action=authz.GRANT_PERMISSION,
        payload={"corpus_item_id": str(corpus.pk), "permission_type": "AUTOMATIC_USE",
                 "scope_type": "", "scope_id": ""},
        subject=("CorpusItem", str(corpus.pk)))
    head = DecisionChainHead.objects.get(pk=1)
    Projection.objects.create(
        corpus_item=corpus, permission_type=Projection.Permission.AUTOMATIC_USE,
        effective_state=Projection.State.ALLOWED, source_decision_event=ev,
        source_sequence_number=ev.sequence_number,
        projected_chain_head_hash=head.terminal_event_hash,
        projection_version=PERMISSION_PROJECTION_VERSION, reason_code="projected")
    result = evaluate_operational_permission(corpus, Projection.Permission.AUTOMATIC_USE)
    assert not result.allowed and result.reason_code == "AUTOMATIC_USE_REQUIRES_RETRIEVAL"


@override_settings(BRAND_LOGO_PATH="/tmp/intelligence-present-logo.png")
def test_legacy_signals_and_status_changes_are_non_authoritative(tmp_path):
    brand = Brand.objects.create(name="B", master_brief="m")
    DesignReference.objects.create(name="r", image_path="r.png", active=True)
    ColorSystem.objects.create(brand=brand, name="c", system_id="c", palette=[],
                               image_generation_context="", status="canonical")
    MaterialSystem.objects.create(brand=brand, name="m", material_id="m", properties={},
                                  prompt_descriptors="", status="approved")
    signals = characterize_legacy_signals()
    assert signals and all(s.reason_code == LEGACY_SIGNAL_NON_AUTHORITATIVE for s in signals)
    DesignReference.objects.update(active=False)
    ColorSystem.objects.update(status="canonical")
    MaterialSystem.objects.update(status="approved")
    assert Projection.objects.count() == 0 and DecisionEvent.objects.count() == 0


def test_no_allowed_projection_seeded_and_no_forbidden_consumer_modules():
    assert Projection.objects.filter(effective_state=Projection.State.ALLOWED).count() == 0
    import apps.intelligence as package
    from pathlib import Path
    text = "\n".join(p.read_text() for p in Path(package.__path__[0]).glob("*.py")
                     if not p.name.startswith("test_"))
    # `semantic_search` was forbidden here while semantic retrieval was out of scope. That
    # premise was superseded by explicit approval: DIP-1C-1 (a748f7a) built the semantic
    # index and DIP-1C-2 added interactive reviewer semantic search. The remaining tokens
    # guard capabilities that are STILL excluded — similarity recommendations, a vector
    # store, and automatic asset selection for generation — and stay forbidden.
    for forbidden in ("recommendation_rank", "vector_search",
                      "retrieve_assets_for_generation"):
        assert forbidden not in text
