from __future__ import annotations

import json

import pytest
from django.urls import reverse

from apps.accounts.models import DecisionEvent

from .asset_identity_reconciliation import reconcile_asset_identity
from .identity import (
    C2_DATASET_ID, IDENTITY_ALIAS_PROVENANCE, CandidateIdentityError,
    evidence_identity_hash, resolve_design_asset_subject, semantic_asset_external_key,
)
from .manifest import ManifestError, canonical_hash, prepare_manifest
from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, ImportRecord,
    MachineClassification, ObservedFact, OperationalPermissionProjection,
    ProvenanceRecord, SourceArtifact,
)
from .mvp_import import run_import
from .test_browser import _reviewer
from .test_manifest_import import _candidate, _document, _sha, _source, _write

pytestmark = pytest.mark.django_db
CANDIDATE_KEY = "same-frozen-c2-key"


def _duplicate_manifest(tmp_path, settings, *, reverse=False):
    settings.INTELLIGENCE_ALLOW_TEST_MANIFESTS = True
    settings.INTELLIGENCE_SOURCE_ROOTS = {"fixture": tmp_path}
    settings.INTELLIGENCE_ALLOWED_SOURCE_PREFIXES = {
        "fixture": ("sources", "audits"),
    }
    entries = []
    for suffix in ("a", "b"):
        source_path = f"sources/{suffix}/same.eps"
        source = tmp_path / source_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"same-whole-file-eps-candidate")
        digest = _sha(source)
        audit_path = f"audits/{suffix}.json"
        audit = tmp_path / audit_path
        _write(audit, {"candidates": [
            _candidate(source_path, digest, candidate_id=CANDIDATE_KEY,
                       readiness="HEADER_ONLY_PARTIAL"),
        ]})
        entries.append({
            "stable_source_key": f"source-{suffix}",
            "dataset_id": C2_DATASET_ID,
            "record_type": "ASSET_SOURCE",
            "source": _source(source_path, digest),
            "source_schema_version": "assetcandidate/1.0",
            "parser_identifier": "fixture.c2",
            "parser_version": "1.0",
            "display_label": f"same-{suffix}.eps",
            "test_only_state": "NON_TEST_SOURCE",
            "data_source": {
                "source": _source(audit_path, _sha(audit), "JSON"),
                "locator": {
                    "schema_version": "json_path/1.0",
                    "value": {"path": audit_path, "segments": ["candidates"]},
                },
            },
            "metadata": {"pilot_role": f"origin-{suffix}"},
        })
    if reverse:
        entries.reverse()
    manifest = tmp_path / "manifest.json"
    _write(manifest, _document(entries, semantic_count=1))
    return manifest, entries


def test_duplicate_origin_order_and_reimport_keep_one_stable_semantic_subject(
        tmp_path, settings):
    manifest, entries = _duplicate_manifest(tmp_path, settings, reverse=True)
    first = run_import(manifest, apply=True)
    profile = DesignAssetProfile.objects.get()
    original_uuid = profile.corpus_item_id
    original_url = reverse("intelligence:corpus-detail", args=[original_uuid])

    assert first["counts"]["asset_candidates"] == 2
    assert first["counts"]["semantic_asset_candidates"] == 1
    assert DesignAssetProfile.objects.count() == 1
    assert SourceArtifact.objects.count() == 1
    assert EvidenceReference.objects.count() == 2
    assert ProvenanceRecord.objects.filter(
        provenance_type="DIP0_ASSET_CANDIDATE_IMPORT").count() == 2
    assert ImportRecord.objects.filter(
        stable_source_record_key__startswith="asset-candidate:").count() == 2
    assert ObservedFact.objects.count() == 2
    assert MachineClassification.objects.count() == 2
    assert profile.source_manifest_entry_key == "source-a"
    assert profile.corpus_item.external_key == semantic_asset_external_key(
        C2_DATASET_ID, CANDIDATE_KEY)
    assert "#" not in profile.corpus_item.external_key

    _write(manifest, _document(list(reversed(entries)), semantic_count=1))
    second = run_import(manifest, apply=True)
    profile.refresh_from_db()

    assert second["failures"] == ()
    assert profile.corpus_item_id == original_uuid
    assert reverse("intelligence:corpus-detail", args=[profile.corpus_item_id]) \
        == original_url
    assert DesignAssetProfile.objects.count() == 1
    assert EvidenceReference.objects.count() == 2
    assert SourceArtifact.objects.count() == 1


def test_future_decision_subject_resolution_fails_closed_on_ambiguity(
        tmp_path, settings):
    manifest, _ = _duplicate_manifest(tmp_path, settings)
    run_import(manifest, apply=True)
    profile = DesignAssetProfile.objects.get()
    second_item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET,
        external_key="legacy-ambiguous-subject",
    )
    DesignAssetProfile.objects.create(
        corpus_item=second_item,
        primary_source_artifact=profile.primary_source_artifact,
        candidate_source_key=CANDIDATE_KEY,
        source_manifest_entry_key="source-b",
        dataset_identifier=C2_DATASET_ID,
        candidate_asset_kind=profile.candidate_asset_kind,
        representation_state=profile.representation_state,
        technical_readiness=profile.technical_readiness,
        extraction_state=profile.extraction_state,
        collection_family_label=profile.collection_family_label,
        dimensions_media=profile.dimensions_media,
        is_test_only=False,
    )

    with pytest.raises(CandidateIdentityError, match="require exactly one"):
        resolve_design_asset_subject(C2_DATASET_ID, CANDIDATE_KEY)


def test_same_frozen_key_with_different_candidate_boundary_is_rejected(
        tmp_path, settings):
    manifest, _ = _duplicate_manifest(tmp_path, settings)
    document = json.loads(manifest.read_text())
    audit = tmp_path / "audits/b.json"
    audit_document = json.loads(audit.read_text())
    audit_document["candidates"][0]["bbox_pt"] = [0, 0, 999, 999]
    _write(audit, audit_document)
    entry = next(row for row in document["entries"]
                 if row["stable_source_key"] == "source-b")
    entry["data_source"]["source"]["sha256"] = _sha(audit)
    _write(manifest, document)

    with pytest.raises(ManifestError, match="ambiguous boundaries"):
        prepare_manifest(manifest)


def test_controlled_case_a_reconciliation_preserves_lineage_and_legacy_url(
        tmp_path, settings, client):
    manifest, _ = _duplicate_manifest(tmp_path, settings)
    run_import(manifest, apply=True)
    winner = DesignAssetProfile.objects.select_related("corpus_item").get()
    canonical_uuid = winner.corpus_item_id
    winner.corpus_item.external_key = f"asset:source-a:{CANDIDATE_KEY}"
    winner.corpus_item.save(update_fields=("external_key", "updated_at"))

    loser_item = CorpusItem.objects.create(
        item_kind=CorpusItem.Kind.DESIGN_ASSET,
        external_key=f"asset:source-b:{CANDIDATE_KEY}",
    )
    DesignAssetProfile.objects.create(
        corpus_item=loser_item,
        primary_source_artifact=winner.primary_source_artifact,
        candidate_source_key=CANDIDATE_KEY,
        source_manifest_entry_key="source-b",
        dataset_identifier=C2_DATASET_ID,
        candidate_asset_kind=winner.candidate_asset_kind,
        representation_state=winner.representation_state,
        technical_readiness=winner.technical_readiness,
        extraction_state=winner.extraction_state,
        collection_family_label=winner.collection_family_label,
        dimensions_media=winner.dimensions_media,
        is_test_only=False,
    )
    legacy_uuid = loser_item.pk

    loser_evidence = EvidenceReference.objects.get(locator__path="audits/b.json")
    loser_evidence.corpus_item = loser_item
    loser_evidence.evidence_hash = evidence_identity_hash(
        item_id=loser_item.pk,
        source_hash=loser_evidence.source_artifact.sha256,
        kind=loser_evidence.evidence_kind,
        schema=loser_evidence.locator_schema_version,
        locator=loser_evidence.locator,
        observed=loser_evidence.observed_value,
    )
    loser_evidence.save(update_fields=("corpus_item", "evidence_hash"))
    loser_fact = ObservedFact.objects.get(evidence_reference=loser_evidence)
    loser_fact.corpus_item = loser_item
    loser_fact.fact_hash = canonical_hash({
        "type": loser_fact.fact_type, "value": loser_fact.normalized_value,
    })
    loser_fact.save(update_fields=("corpus_item", "fact_hash"))
    loser_classification = MachineClassification.objects.get(
        evidence_reference=loser_evidence)
    loser_classification.corpus_item = loser_item
    loser_classification.classification_hash = canonical_hash({
        "type": loser_classification.classification_type,
        "label": loser_classification.label,
        "confidence": round(float(loser_classification.confidence), 4),
        "explanation": loser_classification.structured_explanation,
    })
    loser_classification.save(update_fields=("corpus_item", "classification_hash"))
    ProvenanceRecord.objects.filter(
        acquisition_reference__endswith=":source-b").update(corpus_item=loser_item)
    ImportRecord.objects.filter(
        stable_source_record_key__startswith="asset-candidate:source-b:").update(
            corpus_item=loser_item)

    evidence_ids = set(EvidenceReference.objects.values_list("pk", flat=True))
    fact_ids = set(ObservedFact.objects.values_list("pk", flat=True))
    classification_ids = set(MachineClassification.objects.values_list("pk", flat=True))
    origin_import_ids = set(ImportRecord.objects.filter(
        stable_source_record_key__startswith="asset-candidate:").values_list(
            "pk", flat=True))
    plan = reconcile_asset_identity(manifest)

    assert plan["frozen_candidate_records"] == 2
    assert plan["semantic_candidates"] == 1
    assert plan["physical_source_artifacts"] == 1
    assert plan["profiles_before"] == 2 and plan["profiles_after"] == 1
    assert plan["subjects_merged"] == 1

    result = reconcile_asset_identity(manifest, apply=True)
    winner.refresh_from_db()

    assert result["decision_events_before"] == result["decision_events_after"] == 0
    assert result["allowed_before"] == result["allowed_after"] == 0
    assert DesignAssetProfile.objects.count() == 1
    assert winner.corpus_item_id == canonical_uuid
    assert winner.corpus_item.external_key == semantic_asset_external_key(
        C2_DATASET_ID, CANDIDATE_KEY)
    assert not CorpusItem.objects.filter(pk=legacy_uuid).exists()
    assert set(EvidenceReference.objects.values_list("pk", flat=True)) == evidence_ids
    assert set(ObservedFact.objects.values_list("pk", flat=True)) == fact_ids
    assert set(MachineClassification.objects.values_list("pk", flat=True)) \
        == classification_ids
    assert origin_import_ids.issubset(set(ImportRecord.objects.filter(
        corpus_item_id=canonical_uuid).values_list("pk", flat=True)))
    assert ProvenanceRecord.objects.filter(
        corpus_item_id=canonical_uuid,
        provenance_type="DIP0_ASSET_CANDIDATE_IMPORT",
    ).count() == 2
    assert ProvenanceRecord.objects.filter(
        corpus_item_id=canonical_uuid,
        provenance_type=IDENTITY_ALIAS_PROVENANCE,
        acquisition_reference=f"legacy-corpus-item:{legacy_uuid}",
    ).exists()
    assert resolve_design_asset_subject(C2_DATASET_ID, CANDIDATE_KEY).pk \
        == canonical_uuid
    assert DecisionEvent.objects.count() == 0
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()

    client.force_login(_reviewer())
    legacy_response = client.get(
        reverse("intelligence:corpus-detail", args=[legacy_uuid]))
    assert legacy_response.status_code == 301
    assert legacy_response.url == reverse(
        "intelligence:corpus-detail", args=[canonical_uuid])
    assert client.get(legacy_response.url).status_code == 200

    repeated = reconcile_asset_identity(manifest, apply=True)
    assert repeated["batch_id"] is None
    assert resolve_design_asset_subject(C2_DATASET_ID, CANDIDATE_KEY).pk \
        == canonical_uuid
