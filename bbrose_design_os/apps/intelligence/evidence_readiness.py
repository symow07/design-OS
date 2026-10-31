"""Read-only, separate evidence-readiness dimensions for DIP-1B-5A."""
from __future__ import annotations

from .brand_evidence import DATASET_ID, validate_committed_brand_evidence_bundle
from .evidence_integrity import EvidenceIntegrityResolver, VERIFIED
from .models import EvidenceReference, ImportRecord, ProvenanceRecord

EVIDENCE_KIND = "DETERMINISTIC_BRAND_EVIDENCE_RECORD"
PROVENANCE_TYPE = "DIP1B5A_DETERMINISTIC_BRAND_EVIDENCE"


def evidence_readiness(item, integrity=None):
    """Return capability dimensions without converting evidence into authority."""
    integrity = integrity or EvidenceIntegrityResolver().evaluate(item)
    references = list(EvidenceReference.objects.select_related(
        "source_artifact").filter(
            corpus_item=item, evidence_kind=EVIDENCE_KIND, is_test_only=False))
    provenance_present = ProvenanceRecord.objects.filter(
        corpus_item=item, provenance_type=PROVENANCE_TYPE,
        source_package=DATASET_ID).exists()
    technical_ready = False
    if len(references) == 1 and provenance_present:
        bundle = validate_committed_brand_evidence_bundle()
        selected = EvidenceIntegrityResolver().evaluate(item, references)
        technical_ready = (
            selected.status == VERIFIED
            and references[0].source_artifact.sha256 == bundle["dataset_sha256"]
            and references[0].source_artifact.source_schema_version == DATASET_ID
        )
    dimensioned = bool(references or provenance_present)
    if technical_ready and integrity.status != VERIFIED:
        overall = "PARTIALLY_VERIFIED"
    elif technical_ready:
        overall = VERIFIED
    else:
        overall = integrity.status
    manifest_memberships = sorted({
        row.reconciliation_details.get("manifest_id")
        for row in ImportRecord.objects.filter(corpus_item=item)
        if row.reconciliation_details.get("manifest_id")
    })
    source_versions = [{
        "dataset_id": DATASET_ID,
        "schema_version": row.source_artifact.source_schema_version,
        "source_artifact_id": str(row.source_artifact_id),
        "sha256": row.source_artifact.sha256,
        "evidence_reference_id": str(row.pk),
        "status": VERIFIED if technical_ready else "UNVERIFIED_SOURCE_VERSION",
    } for row in references]
    dimensions = (
        {"name": "TECHNICAL_EVIDENCE_READY", "ready": technical_ready,
         "reason": ("DETERMINISTIC_SOURCE_RECORD_VERIFIED" if technical_ready
                    else "DETERMINISTIC_SOURCE_RECORD_NOT_VERIFIED")},
        {"name": "BRAND_IDENTITY_EVIDENCE_READY", "ready": False,
         "reason": "NO_AUTHORITATIVE_BRAND_IDENTITY_EVIDENCE"},
        {"name": "RIGHTS_EVIDENCE_READY", "ready": False,
         "reason": "NO_OWNERSHIP_OR_LICENCE_EVIDENCE"},
        {"name": "PALETTE_AUTHORITY_EVIDENCE_READY", "ready": False,
         "reason": "TECHNICAL_PARSE_IS_NOT_PALETTE_AUTHORITY"},
        {"name": "GOVERNANCE_READY",
         "ready": (integrity.status == VERIFIED if not dimensioned else False),
         "reason": ("LEGACY_INTEGRITY_GATE" if not dimensioned
                    else "IDENTITY_RIGHTS_OR_PALETTE_AUTHORITY_MISSING")},
    )
    return {
        "dimensioned": dimensioned,
        "overall_status": overall,
        "dimensions": dimensions,
        "technical_evidence_ready": technical_ready,
        "review_eligible": (technical_ready if dimensioned
                            else integrity.status == VERIFIED),
        "governance_ready": (integrity.status == VERIFIED if not dimensioned else False),
        "governance_eligibility_reasons": (
            () if not dimensioned and integrity.status == VERIFIED else tuple(
                row["reason"] for row in dimensions if not row["ready"])),
        "dataset_versions": source_versions,
        "manifest_memberships": manifest_memberships,
        "operational_permission_granted": False,
    }


def governance_category_dimension_ready(item, category):
    """Return None for legacy subjects; dimension readiness for reconciled subjects."""
    if not ProvenanceRecord.objects.filter(
            corpus_item=item, provenance_type=PROVENANCE_TYPE,
            source_package=DATASET_ID).exists():
        return None
    # Existing governance categories are deliberately composite. Technical evidence
    # alone cannot satisfy technical+brand, color+brand, or either rights category.
    return False
