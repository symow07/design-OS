"""Bounded review packets and human question sets — DIP-1B-5B (`review_packet/1.0`).

A packet is everything a human reviewer needs to judge one campaign candidate, and nothing
more. It is **deterministic, read-only and bounded**: it never serves source binaries, never
emits an unrestricted absolute filesystem path, and never carries an inferred approval,
rights clearance, governance selection, or permission.

The packet keeps MACHINE state and HUMAN state visibly apart — machine classifications are
labelled non-authoritative, and the question sets are *questions only*. The system never
supplies a substantive human answer; that is the reviewer's job, and it arrives as a signed
DecisionEvent, not as a packet field.
"""
from __future__ import annotations

from .evidence_integrity import EvidenceIntegrityResolver
from .governance_reader import read_published_governance
from .locator_schemas import _WINDOWS_ABSOLUTE
from .models import (
    EvidenceReference, MachineClassification, ObservedFact,
    OperationalPermissionProjection, ProvenanceRecord, SourceLocationObservation,
)
from .permissions import evaluate_operational_permission
from .projection_reader import read_published_assertions
from .review_campaign import campaign_entry_for
from .review_readiness import assess_readiness

PACKET_SCHEMA = "review_packet/1.0"
REDACTED_LOCATION = "REDACTED_UNRESTRICTED_PATH"

# --- question sets: questions ONLY, never answers ---------------------------------
QUESTION_SETS = {
    "HISTORICAL_MEMORY": (
        "product_family", "design_role", "layout_patterns", "typography_hierarchy",
        "color_relationships", "reference_memory_suitability", "copying_risk",
        "obsolete_brand_risk"),
    "DESIGN_ASSET": (
        "asset_category", "extraction_quality", "vector_raster_suitability",
        "collection_relationship", "provenance_completeness", "rights_review_requirement",
        "reference_only_versus_technically_reusable"),
    "FONT_TECHNICAL": (
        "family_identity", "style_category", "script_coverage",
        "weight_and_width_suitability", "bbrose_suitability", "licence_evidence_state",
        "system_demo_trial_suspicion"),
    "BRAND_IDENTITY": (
        "visible_brand_identity", "bbrose_third_party_or_unknown",
        "master_composition_lockup_or_unrelated_graphic", "vector_master_suitability",
        "missing_evidence"),
    "PALETTE_OBSERVATION": (
        "observed_colors", "parse_completeness", "authoritative_bbrose_evidence",
        "candidate_only_suitability", "blockers_before_governance_review"),
}

# --- what a reviewer must NOT infer from this packet ------------------------------
_UNIVERSAL_WARNINGS = (
    "REVIEW_READINESS_IS_NOT_APPROVAL_OR_OPERATIONAL_PERMISSION",
    "MACHINE_CLASSIFICATION_IS_NOT_HUMAN_TRUTH",
    "TECHNICAL_QUALITY_IS_NOT_RIGHTS_CLEARANCE",
    "MATCHING_HASH_DOES_NOT_TRANSFER_RIGHTS",
    "FILE_LOCATION_DOES_NOT_ESTABLISH_OWNERSHIP_OR_IDENTITY",
)
_TYPE_WARNINGS = {
    "BRAND_IDENTITY": (
        "TECHNICAL_EVIDENCE_IS_NOT_BRAND_IDENTITY",
        "A_BBROSE_LABEL_IS_NOT_CONFIRMED_BBROSE_OWNERSHIP",
        "CANDIDATE_IS_NOT_CANONICAL",),
    "PALETTE_OBSERVATION": (
        "TECHNICAL_PARSE_IS_NOT_PALETTE_AUTHORITY",
        "CANDIDATE_IS_NOT_THE_PRIMARY_PALETTE",),
    "DESIGN_ASSET": (
        "NEARBY_LICENCE_EVIDENCE_DOES_NOT_CLEAR_RIGHTS",
        "A_SIBLING_ACQUISITION_CONCLUSION_DOES_NOT_TRANSFER",),
    "HISTORICAL_MEMORY": (
        "REFERENCE_MEMORY_IS_NOT_A_REUSE_LICENCE",),
    "FONT_TECHNICAL": (
        "POSSESSION_IS_NOT_A_LICENCE",),
}


def _bounded_location(value: str) -> str:
    """Never emit an unrestricted absolute path; logical locators pass through."""
    text = (value or "")[:255]
    if text.startswith("/") or _WINDOWS_ABSOLUTE.match(text):
        return REDACTED_LOCATION
    return text


def _questions_for(review_type) -> tuple[str, ...]:
    return QUESTION_SETS.get(review_type, ())


def _warnings_for(review_type) -> tuple[str, ...]:
    return _UNIVERSAL_WARNINGS + _TYPE_WARNINGS.get(review_type, ())


def _evidence(item):
    rows = EvidenceReference.objects.select_related("source_artifact").filter(
        corpus_item=item).order_by("evidence_hash")
    return [{
        "evidence_reference_id": str(r.pk),
        "evidence_kind": r.evidence_kind,
        "locator": r.locator,                       # already schema-validated + bounded
        "locator_schema_version": r.locator_schema_version,
        "evidence_hash": r.evidence_hash,
        "source_sha256": r.source_artifact.sha256,
        "is_test_only": r.is_test_only,
    } for r in rows]


def _source_locations(item):
    artifact_ids = list(EvidenceReference.objects.filter(
        corpus_item=item).values_list("source_artifact_id", flat=True))
    rows = SourceLocationObservation.objects.select_related("source_artifact").filter(
        source_artifact_id__in=artifact_ids).order_by("observed_at", "id")
    return [{
        "source_sha256": r.source_artifact.sha256,
        "location_kind": r.location_kind,
        "observed_location": _bounded_location(r.observed_location),
        "availability_state": r.availability_state,
    } for r in rows]


def _facts(item):
    return [{
        "fact_type": f.fact_type, "value_schema_version": f.value_schema_version,
        "normalized_value": f.normalized_value, "fact_hash": f.fact_hash,
        "importer": f"{f.importer_identifier}/{f.importer_version}",
    } for f in ObservedFact.objects.filter(corpus_item=item).order_by("fact_hash")]


def _machine(item):
    """Machine output — explicitly non-authoritative."""
    return [{
        "classification_type": m.classification_type, "label": m.label,
        "confidence": float(m.confidence) if m.confidence is not None else None,
        "classifier": f"{m.classifier_identifier}/{m.classifier_version}",
        "classification_hash": m.classification_hash,
        "authoritative": False,
    } for m in MachineClassification.objects.filter(
        corpus_item=item).order_by("classification_hash")]


def _provenance(item):
    return [{
        "provenance_type": p.provenance_type,
        "source_organization": p.source_organization,
        "source_package": p.source_package,
        "acquisition_reference": _bounded_location(p.acquisition_reference),
        "observed_licence_file_reference": _bounded_location(
            p.observed_licence_file_reference),
        # a licence file merely OBSERVED nearby is evidence, never permission
        "licence_reference_is_evidence_not_permission": True,
        "machine_interpretation": p.normalized_machine_interpretation,
    } for p in ProvenanceRecord.objects.filter(
        corpus_item=item).order_by("provenance_type", "id")]


def _permissions(item):
    results = []
    for permission_type in OperationalPermissionProjection.Permission.values:
        r = evaluate_operational_permission(item, permission_type)
        # direct attribute access, not getattr-with-default: a future rename must fail
        # loudly rather than silently report every permission as denied-for-no-reason
        results.append({"permission_type": permission_type,
                        "allowed": r.allowed,
                        "reason_code": r.reason_code})
    return results


def build_review_packet(candidate, *, entry=None) -> dict:
    """One bounded, deterministic, read-only packet. Writes nothing."""
    item = candidate.corpus_item
    entry = entry if entry is not None else campaign_entry_for(candidate)
    if entry is None:
        raise ValueError(
            f"ReviewCandidate {candidate.pk} is not a member of the frozen campaign scope")

    integrity = EvidenceIntegrityResolver().evaluate(item)
    readiness = assess_readiness(candidate, wave=entry["wave"], integrity=integrity)
    assertions = read_published_assertions(item)
    governance = read_published_governance(item)

    return {
        "schema_version": PACKET_SCHEMA,
        # canonical identity only
        "corpus_item_id": str(item.pk),
        "review_candidate_id": str(candidate.pk),
        "external_key": item.external_key,
        "item_kind": item.item_kind,
        "review_type": candidate.review_type,
        "dataset_identifier": entry["dataset_identifier"],
        "wave": entry["wave"],
        "selection_reason": entry["selection_reason"],
        "business_priority": entry["business_priority"],
        "workflow_status": candidate.workflow_status,
        # evidence (bounded)
        "source_hashes": sorted({e["source_sha256"] for e in _evidence(item)}),
        "source_location_observations": _source_locations(item),
        "evidence_references": _evidence(item),
        "observed_facts": _facts(item),
        # machine vs human, kept apart
        "machine_classifications": _machine(item),
        "provenance_records": _provenance(item),
        "human_assertions": {
            "projection_state": assertions.state,
            "reason": assertions.reason,
        },
        # integrity + readiness
        "evidence_integrity": {
            "status": integrity.status,
            "reason_codes": list(integrity.reason_codes),
            "blocks_evidence_dependent_claims": bool(
                integrity.blocks_evidence_dependent_claims),
            "warning_message": integrity.warning_message,
        },
        "review_readiness": readiness.as_dict(),
        # governance is READ-ONLY here; 5B never creates or rebuilds it
        "governance": {
            "state": governance.state,
            "reason": governance.reason,
            "read_only": True,
        },
        "operational_permissions": _permissions(item),
        # the human's job
        "required_human_questions": list(_questions_for(candidate.review_type)),
        "prohibited_inference_warnings": list(_warnings_for(candidate.review_type)),
        "blocker_codes": list(readiness.blocker_codes),
        "recommended_next_action": readiness.recommended_next_action,
        # stated, never assumed
        "implies_approval": False,
        "implies_rights_clearance": False,
        "implies_governance_selection": False,
        "grants_operational_permission": False,
    }
