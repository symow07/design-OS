import copy

import pytest

from .brand_evidence import (
    C3_CONFIGURATION_SHA256,
    DATASET_ID,
    EXCLUDED_EXECUTION_FIELDS,
    FROZEN_MVP_MANIFEST_SHA256,
    ORIGIN_DATASET_ID,
    TECHNICAL_FIELDS,
    BrandEvidenceError,
    build_brand_evidence_bundle,
)


def _technical(path, value="READY", timestamp="2026-01-01T00:00:00Z"):
    row = {key: None for key in TECHNICAL_FIELDS}
    row.update({
        "relative_path": path,
        "filename": path.rsplit("/", 1)[-1],
        "source_package": path.rsplit("/", 1)[0],
        "format": ".eps",
        "dip0a_classification": "REUSABLE_VECTOR_ASSET",
        "parser": "test/1.0",
        "vector_or_raster": "vector",
        "technical_readiness": {
            "value": value, "extracted_at": timestamp,
            "runtime_path": "/tmp/volatile",
        },
        "capability_limitations": [],
        "queue_i_membership": {"in_queue_i": False, "candidates": []},
    })
    return row


def _inputs(tmp_path):
    paths = ["materials/a.eps", "materials/b.eps"]
    entries = []
    provenance = []
    for index, relative in enumerate(paths):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"source-{index}".encode())
        import hashlib
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        stable = f"dip0c3-brand:{index:02d}"
        entries.append({
            "stable_source_key": stable,
            "dataset_id": ORIGIN_DATASET_ID,
            "record_type": "BRAND_CANDIDATE",
            "source": {
                "root": "repository", "path": relative, "sha256": source_hash,
                "source_type": "FILE",
            },
            "data_source": {"locator": {
                "schema_version": "json_path/1.0",
                "value": {
                    "path": "var/design_intelligence/audits/dip0c/c3a/brand_candidates.json",
                    "segments": [index],
                },
            }},
        })
        provenance.append({
            "stable_source_key": stable, "dataset_id": ORIGIN_DATASET_ID,
            "source_record_hash": str(index + 1) * 64,
        })
    # Production requires 21 records; repeat distinct sources/keys for the fixture.
    for index in range(2, 21):
        relative = f"materials/source-{index}.eps"
        path = tmp_path / relative
        path.write_bytes(f"source-{index}".encode())
        import hashlib
        stable = f"dip0c3-brand:{index:02d}"
        entries.append({
            "stable_source_key": stable, "dataset_id": ORIGIN_DATASET_ID,
            "record_type": "BRAND_CANDIDATE",
            "source": {"root": "repository", "path": relative,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "source_type": "FILE"},
            "data_source": {"locator": {"schema_version": "json_path/1.0",
                "value": {"path": "var/design_intelligence/audits/dip0c/c3a/brand_candidates.json",
                          "segments": [index]}}},
        })
        provenance.append({"stable_source_key": stable, "dataset_id": ORIGIN_DATASET_ID,
                           "source_record_hash": f"{index + 1:064x}"[-64:]})
    rows = [_technical(entry["source"]["path"]) for entry in entries]
    frozen = {"schema_version": "dip1b_mvp_manifest/1.0",
              "manifest_id": "dip1b_mvp_manifest/1.0", "entries": entries}
    return rows, frozen, provenance


def _build(tmp_path, rows, frozen, provenance):
    return build_brand_evidence_bundle(
        c3a_document=rows, frozen_manifest=frozen,
        configuration_bytes=b"configuration",
        preserved_import_records=provenance, repository_root=tmp_path,
    )


def test_identical_inputs_timestamp_and_record_order_are_deterministic(
        tmp_path, monkeypatch):
    rows, frozen, provenance = _inputs(tmp_path)
    import apps.intelligence.brand_evidence as module
    import hashlib
    monkeypatch.setattr(
        module, "C3_CONFIGURATION_SHA256",
        hashlib.sha256(b"configuration").hexdigest())
    first = _build(tmp_path, rows, frozen, provenance)
    second_rows = list(reversed(copy.deepcopy(rows)))
    for row in second_rows:
        row["technical_readiness"]["extracted_at"] = "2099-12-31T23:59:59Z"
        row["technical_readiness"]["hostname"] = "another-host"
    second = _build(tmp_path, second_rows, frozen, list(reversed(provenance)))
    assert first.dataset_bytes == second.dataset_bytes
    assert first.dataset_sha256 == second.dataset_sha256
    assert first.manifest_bytes == second.manifest_bytes
    assert first.dataset_document["dataset_id"] == DATASET_ID
    assert first.manifest_document["source_input_count"] == 21
    assert first.manifest_document["physical_content_identity_count"] == 21
    projected_records = first.dataset_document["records"]
    serialized_records = str(projected_records)
    assert not any(
        field in serialized_records for field in EXCLUDED_EXECUTION_FIELDS)


def test_changed_semantic_content_changes_canonical_hash(tmp_path, monkeypatch):
    rows, frozen, provenance = _inputs(tmp_path)
    import apps.intelligence.brand_evidence as module
    import hashlib
    monkeypatch.setattr(
        module, "C3_CONFIGURATION_SHA256",
        hashlib.sha256(b"configuration").hexdigest())
    first = _build(tmp_path, rows, frozen, provenance)
    changed = copy.deepcopy(rows)
    changed[0]["technical_readiness"]["value"] = "CHANGED"
    second = _build(tmp_path, changed, frozen, provenance)
    assert first.dataset_sha256 != second.dataset_sha256
    assert first.manifest_sha256 != second.manifest_sha256


def test_optional_technical_fields_can_be_explicitly_unavailable(
        tmp_path, monkeypatch):
    rows, frozen, provenance = _inputs(tmp_path)
    import apps.intelligence.brand_evidence as module
    import hashlib
    monkeypatch.setattr(
        module, "C3_CONFIGURATION_SHA256",
        hashlib.sha256(b"configuration").hexdigest())
    del rows[0]["technical_readiness"]
    bundle = _build(tmp_path, rows, frozen, provenance)
    first = bundle.dataset_document["records"][0]
    assert first["technical_evidence"]["technical_readiness"] is None
    assert "technical_readiness" in first["unavailable_technical_fields"]


def test_wrong_pinned_configuration_fails_closed(tmp_path):
    rows, frozen, provenance = _inputs(tmp_path)
    assert len(C3_CONFIGURATION_SHA256) == 64
    assert len(FROZEN_MVP_MANIFEST_SHA256) == 64
    with pytest.raises(BrandEvidenceError, match="configuration hash"):
        _build(tmp_path, rows, frozen, provenance)
