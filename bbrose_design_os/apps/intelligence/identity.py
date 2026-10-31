"""Deterministic semantic identity for imported DesignAsset candidates."""
from __future__ import annotations

import copy
import hashlib
import json

C2_DATASET_ID = "dip0c2_asset_candidate_pilot/1.0"
CURATED_EXPANSION_DATASET_ID = "dip1b_curated_asset_expansion/1.0"
SUPPORTED_ASSET_IDENTITY_DATASETS = frozenset({
    C2_DATASET_ID, CURATED_EXPANSION_DATASET_ID,
})
ASSET_IDENTITY_VERSION = "design_asset_identity/1.0"
IDENTITY_ALIAS_PROVENANCE = "CORPUS_IDENTITY_RECONCILIATION"


class CandidateIdentityError(ValueError):
    pass


def _canonical_hash(value) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def semantic_candidate_payload(candidate: dict) -> dict:
    """Return the complete candidate minus acquisition-only C2 context.

    C2 candidate ids intentionally ignore logical path and the earlier inventory label.
    Those values remain evidence/provenance, but do not create another candidate boundary.
    """
    payload = copy.deepcopy(candidate)
    source = payload.get("source_file")
    if isinstance(source, dict):
        source.pop("relative_path", None)
    payload.pop("inventory_category_original", None)
    payload.pop("classification_override", None)
    return payload


def semantic_candidate_fingerprint(candidate: dict) -> str:
    return _canonical_hash(semantic_candidate_payload(candidate))


def semantic_asset_external_key(dataset_id: str, candidate_key: str) -> str:
    if dataset_id not in SUPPORTED_ASSET_IDENTITY_DATASETS:
        raise CandidateIdentityError("asset dataset has no approved identity rules")
    if not candidate_key or len(candidate_key) > 64:
        raise CandidateIdentityError("candidate key is missing or unbounded")
    return f"asset:{dataset_id}:{candidate_key}"


def evidence_identity_hash(*, item_id, source_hash, kind, schema, locator, observed=""):
    return _canonical_hash({
        "item": str(item_id),
        "source": source_hash,
        "kind": kind,
        "schema": schema,
        "locator": locator,
        "observed": str(observed),
    })


def asset_fact_identity_hash(*, fact_type, value, evidence_hash):
    return _canonical_hash({
        "type": fact_type,
        "value": value,
        "origin_evidence_hash": evidence_hash,
    })


def asset_classification_identity_hash(
        *, classification_type, label, confidence, explanation, evidence_hash):
    return _canonical_hash({
        "type": classification_type,
        "label": str(label),
        "confidence": round(float(confidence or 0), 4),
        "explanation": explanation,
        "origin_evidence_hash": evidence_hash,
    })


def resolve_design_asset_subject(dataset_id: str, candidate_key: str):
    """Resolve exactly one future signed-decision subject, or fail closed."""
    from .models import DesignAssetProfile

    profiles = list(DesignAssetProfile.objects.select_related("corpus_item").filter(
        dataset_identifier=dataset_id,
        candidate_source_key=candidate_key,
    )[:2])
    if len(profiles) != 1:
        raise CandidateIdentityError(
            f"candidate identity resolved to {len(profiles)} subjects; require exactly one"
        )
    return profiles[0].corpus_item
