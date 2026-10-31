from __future__ import annotations

import hashlib
import json

import pytest

from apps.accounts.models import DecisionEvent

from .evidence_integrity import CORRECTION_ID, EvidenceIntegrityResolver
from .manifest import DATASET_C1, DATASET_C2, ManifestError, prepare_manifest
from .models import (
    BrandCandidateProfile, CorpusItem, DesignAssetProfile, DesignUnit, FontFaceProfile,
    HistoricalDesignProfile, ImportBatch, ImportRecord, OperationalPermissionProjection,
    ProvenanceRecord, SourceArtifact, SourceLocationObservation,
)
from .mvp_import import run_import

pytestmark = pytest.mark.django_db


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def _candidate(path, source_hash, candidate_id="candidate-1", readiness="TECHNICALLY_READY"):
    return {
        "schema": "assetcandidate/1.0", "candidate_id": candidate_id,
        "source_file": {"relative_path": path, "sha256": source_hash,
                        "format": ".ai", "kind": "pdf_backed"},
        "page_or_artboard": 0,
        "segmentation": {"method": "VECTOR_GEOMETRY", "status": "SEGMENTED",
                         "confidence": 0.7},
        "bbox_pt": [1, 2, 11, 22],
        "asset_type": {"value": "MOTIF", "tier": "HEURISTIC"},
        "isolated_candidate_confidence": 0.4,
        "collection": {"is_member": False},
        "A_technical_readiness": {"value": readiness},
        "inventory_category_original": "MOTIF",
    }


def _source(path, digest, source_type="FILE"):
    return {"root": "fixture", "path": path, "sha256": digest,
            "source_type": source_type, "media_type": "application/octet-stream"}


def _document(entries, *, counts=None, semantic_count=None):
    counts = counts or {
        "historical_designs": 0, "design_units": 0, "c1_overlap_audit_records": 0,
        "c2_manifest_entries": len(entries),
        "c2_unique_sources": len({e["source"]["path"] for e in entries}),
        "c2_content_identities": len({e["source"]["sha256"] for e in entries}),
        "asset_candidates": len(entries),
        "semantic_asset_candidates": (semantic_count
                                      if semantic_count is not None else len(entries)),
        "font_candidates": 0,
        "brand_candidates": 0, "palette_candidates": 0,
    }
    return {
        "schema_version": "dip1b_mvp_manifest/1.0", "manifest_id": "fixture/1.0",
        "importer": {"identifier": "bbrose.intelligence.import_dip0_mvp",
                     "version": "1.0"},
        "datasets": {
            DATASET_C1: {"semantic_role": "FROZEN_TECHNICAL_SOURCE_AUDIT"},
            DATASET_C2: {"semantic_role": "AUTHORITATIVE_ASSET_CANDIDATE_PILOT"},
        },
        "expected_counts": counts, "entries": entries,
    }


def _fixture_manifest(tmp_path, settings, *, readiness="TECHNICALLY_READY"):
    settings.INTELLIGENCE_ALLOW_TEST_MANIFESTS = True
    settings.INTELLIGENCE_SOURCE_ROOTS = {"fixture": tmp_path}
    settings.INTELLIGENCE_ALLOWED_SOURCE_PREFIXES = {
        "fixture": ("sources", "audits")}
    raw = tmp_path / "sources/a.ai"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(b"frozen-vector-source")
    raw_hash = _sha(raw)
    audit = tmp_path / "audits/a.json"
    _write(audit, {"candidates": [
        _candidate("sources/a.ai", raw_hash, readiness=readiness)]})
    entry = {
        "stable_source_key": "c2-source-1", "dataset_id": DATASET_C2,
        "record_type": "ASSET_SOURCE",
        "source": _source("sources/a.ai", raw_hash),
        "source_schema_version": "assetcandidate/1.0",
        "parser_identifier": "fixture.c2", "parser_version": "1.0",
        "display_label": "a.ai", "test_only_state": "NON_TEST_SOURCE",
        "data_source": {
            "source": _source("audits/a.json", _sha(audit), "JSON"),
            "locator": {"schema_version": "json_path/1.0",
                        "value": {"path": "audits/a.json", "segments": ["candidates"]}},
        },
        "metadata": {"pilot_role": "fixture"},
    }
    manifest = tmp_path / "manifest.json"
    _write(manifest, _document([entry]))
    return manifest, raw, audit


def test_manifest_validation_dry_run_and_guards(tmp_path, settings):
    manifest, raw, _ = _fixture_manifest(tmp_path, settings)
    before = raw.read_bytes()
    result = run_import(manifest)
    assert result["mode"] == "dry-run" and result["counts"]["asset_candidates"] == 1
    assert ImportBatch.objects.count() == 0 and SourceArtifact.objects.count() == 0
    assert raw.read_bytes() == before

    document = json.loads(manifest.read_text())
    document["schema_version"] = "unknown/9"
    _write(manifest, document)
    with pytest.raises(ManifestError, match="unknown manifest schema"):
        prepare_manifest(manifest)

    document["schema_version"] = "dip1b_mvp_manifest/1.0"
    document["manifest_id"] = "unknown/1.0"
    settings.INTELLIGENCE_ALLOW_TEST_MANIFESTS = False
    _write(manifest, document)
    with pytest.raises(ManifestError, match="unknown manifest"):
        prepare_manifest(manifest)


def test_manifest_rejects_hash_mismatch_test_only_and_path_escape(tmp_path, settings):
    manifest, _, _ = _fixture_manifest(tmp_path, settings)
    document = json.loads(manifest.read_text())
    document["entries"][0]["source"]["sha256"] = "0" * 64
    _write(manifest, document)
    with pytest.raises(ManifestError, match="does not match"):
        prepare_manifest(manifest)

    manifest, _, _ = _fixture_manifest(tmp_path, settings)
    document = json.loads(manifest.read_text())
    document["entries"][0]["test_only_state"] = "TEST_ONLY"
    _write(manifest, document)
    with pytest.raises(ManifestError, match="test-only"):
        prepare_manifest(manifest)

    manifest, _, _ = _fixture_manifest(tmp_path, settings)
    document = json.loads(manifest.read_text())
    document["entries"][0]["source"]["path"] = "../outside.ai"
    _write(manifest, document)
    with pytest.raises(ManifestError, match="path is invalid"):
        prepare_manifest(manifest)


def test_apply_and_identical_reimport_are_idempotent_and_create_no_authority(
        tmp_path, settings):
    manifest, _, _ = _fixture_manifest(tmp_path, settings)
    first = run_import(manifest, apply=True)
    assert first["failures"] == ()
    assert first["decision_events_before"] == first["decision_events_after"] == 0
    assert first["allowed_before"] == first["allowed_after"] == 0
    assert SourceArtifact.objects.count() == 1
    assert DesignAssetProfile.objects.count() == 1
    assert ImportBatch.objects.count() == 1

    second = run_import(manifest, apply=True)
    assert second["failures"] == ()
    assert SourceArtifact.objects.count() == 1
    assert DesignAssetProfile.objects.count() == 1
    assert SourceLocationObservation.objects.count() == 1
    assert second["import_records"]["unchanged_records"] == 2
    assert DecisionEvent.objects.count() == 0
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()


def test_changed_record_appends_import_version_and_partial_failure_preserves_prior(
        tmp_path, settings):
    manifest, _, audit = _fixture_manifest(tmp_path, settings)
    run_import(manifest, apply=True)
    prior = ImportRecord.objects.get(stable_source_record_key__startswith="asset-candidate:")

    document = json.loads(manifest.read_text())
    data = json.loads(audit.read_text())
    data["candidates"][0]["A_technical_readiness"]["value"] = "NEEDS_CLEANUP"
    _write(audit, data)
    document["entries"][0]["data_source"]["source"]["sha256"] = _sha(audit)
    _write(manifest, document)
    changed = run_import(manifest, apply=True)
    later = ImportRecord.objects.filter(
        stable_source_record_key=prior.stable_source_record_key).latest("created_at")
    assert changed["failures"] == ()
    assert later.disposition == ImportRecord.Disposition.NEW_VERSION
    assert later.prior_import_record_id == prior.pk

    failed = run_import(
        manifest, apply=True, fail_record_key=prior.stable_source_record_key)
    assert failed["failures"] and DesignAssetProfile.objects.count() == 1
    assert ImportRecord.objects.filter(pk=later.pk).exists()


def test_relocated_identical_candidate_has_one_subject_and_two_origin_histories(
        tmp_path, settings):
    settings.INTELLIGENCE_ALLOW_TEST_MANIFESTS = True
    settings.INTELLIGENCE_SOURCE_ROOTS = {"fixture": tmp_path}
    settings.INTELLIGENCE_ALLOWED_SOURCE_PREFIXES = {
        "fixture": ("sources", "audits")}
    raw_a = tmp_path / "sources/a.ai"
    raw_b = tmp_path / "sources/moved/a.ai"
    raw_a.parent.mkdir(parents=True)
    raw_b.parent.mkdir(parents=True)
    raw_a.write_bytes(b"identical")
    raw_b.write_bytes(b"identical")
    digest = _sha(raw_a)
    entries = []
    for index, path in enumerate(("sources/a.ai", "sources/moved/a.ai")):
        audit_path = f"audits/{index}.json"
        audit = tmp_path / audit_path
        _write(audit, {"candidates": [_candidate(path, digest, "same-c2-key")]})
        entries.append({
            "stable_source_key": f"source-{index}", "dataset_id": DATASET_C2,
            "record_type": "ASSET_SOURCE", "source": _source(path, digest),
            "source_schema_version": "assetcandidate/1.0",
            "parser_identifier": "fixture", "parser_version": "1",
            "display_label": path, "test_only_state": "NON_TEST_SOURCE",
            "data_source": {"source": _source(audit_path, _sha(audit), "JSON"),
                            "locator": {"schema_version": "json_path/1.0",
                                        "value": {"path": audit_path,
                                                  "segments": ["candidates"]}}},
            "metadata": {},
        })
    manifest = tmp_path / "manifest.json"
    _write(manifest, _document(entries, semantic_count=1))
    result = run_import(manifest, apply=True)
    assert not result["failures"]
    assert SourceArtifact.objects.count() == 1
    assert SourceLocationObservation.objects.count() == 2
    assert DesignAssetProfile.objects.count() == 1
    assert ProvenanceRecord.objects.filter(
        provenance_type="DIP0_ASSET_CANDIDATE_IMPORT").count() == 2
    assert ImportRecord.objects.filter(
        stable_source_record_key__startswith="asset-candidate:").count() == 2
    assert {p.candidate_source_key for p in DesignAssetProfile.objects.all()} == {
        "same-c2-key"}


def test_candidate_models_carry_no_human_or_legal_authority_fields():
    fields = {f.name for f in DesignAssetProfile._meta.fields}
    assert not fields.intersection({
        "approved", "licensed", "owned", "retrieval_allowed", "automatic_use_allowed"})
    assert DecisionEvent.objects.count() == 0


def test_frozen_production_manifest_persists_exact_bounded_corpus_or_fails_closed(settings):
    manifest = (settings.BASE_DIR.parent / "docs/design_intelligence/dip1"
                / "dip1b_mvp_manifest_1_0.json")
    integrity = EvidenceIntegrityResolver(manifest_path=manifest).inspect_policy(CORRECTION_ID)
    if integrity.blocks_evidence_dependent_claims:
        with pytest.raises(ManifestError) as caught:
            prepare_manifest(manifest)
        version = integrity.unresolved_source_versions[0]
        if version.observed_sha256:
            assert version.expected_sha256 in str(caught.value)
            assert version.observed_sha256 in str(caught.value)
        else:
            assert "unavailable" in str(caught.value)
        assert CorpusItem.objects.count() == 0
        assert DecisionEvent.objects.count() == 0
        assert OperationalPermissionProjection.objects.count() == 0
        return
    prepared = prepare_manifest(manifest)
    c1_entries = [
        entry.declaration for entry in prepared.entries
        if entry.declaration["dataset_id"] == DATASET_C1
    ]
    assert len(c1_entries) == 10
    assert {
        entry["data_source"]["source"]["path"] for entry in c1_entries
    } == {"docs/design_intelligence/dip0c/pilot_manifest.json"}
    result = run_import(manifest, apply=True)
    assert result["failures"] == ()
    assert result["counts"] == {
        "historical_designs": 14, "design_units": 173,
        "c1_overlap_audit_records": 10, "c2_manifest_entries": 20,
        "c2_unique_sources": 19, "c2_content_identities": 18,
        "asset_candidates": 48, "semantic_asset_candidates": 47,
        "font_candidates": 34,
        "brand_candidates": 21, "palette_candidates": 1,
    }
    assert CorpusItem.objects.count() == 117
    assert HistoricalDesignProfile.objects.count() == 14
    assert DesignUnit.objects.count() == 173
    assert DesignAssetProfile.objects.count() == 47
    assert DesignAssetProfile.objects.values(
        "primary_source_artifact_id").distinct().count() == 18
    assert DesignAssetProfile.objects.values(
        "candidate_source_key").distinct().count() == 47
    assert FontFaceProfile.objects.count() == 34
    assert BrandCandidateProfile.objects.count() == 22
    assert ProvenanceRecord.objects.filter(
        corpus_item__isnull=True,
        provenance_type="DIP0C1_SOURCE_AUDIT_EVIDENCE").count() == 10
    assert all(
        evidence.locator_schema_version == "json_path/1.0"
        for profile in DesignAssetProfile.objects.all()
        for evidence in profile.corpus_item.evidence_references.all())
    assert DecisionEvent.objects.count() == 0
    assert not OperationalPermissionProjection.objects.filter(
        effective_state=OperationalPermissionProjection.State.ALLOWED).exists()
