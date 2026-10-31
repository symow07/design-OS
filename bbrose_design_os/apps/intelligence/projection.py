"""Deterministic DIP-1B-4A human-assertion projection and atomic publication."""
from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.authorization import AUTHZ_SNAPSHOT_FIELDS, AUTHZ_SNAPSHOT_SCHEMA
from apps.accounts.chain_verification import _snapshot_contract_error
from apps.accounts.decision_chain import verify_chain, verify_event
from apps.accounts.models import DECISION_EVENT_SCHEMA, DecisionChainHead, DecisionEvent
from apps.accounts.security import canonical

from .identity import (
    C2_DATASET_ID, IDENTITY_ALIAS_PROVENANCE, CandidateIdentityError,
    resolve_design_asset_subject,
)
from .evidence_integrity import evaluate_evidence_integrity
from .models import (
    _PROJECTION_WRITE_TOKEN, CorpusItem, EvidenceReference, HumanAssertionProjection,
    IntelligenceProjectionGeneration, ProjectionPublicationState, ProvenanceRecord,
    ReviewCandidate,
)
from .review_services import (
    ASSERTION_SCHEMA, DOMAIN_SCHEMAS, EVIDENCE_ASSESSMENT_SCHEMA,
)
from .human_semantic_metadata import (
    METADATA_ASSERTION_DOMAIN, METADATA_SCHEMA, RESOLUTION_SCHEMA, MetadataBundleError,
    build_metadata_bundle,
)

PROJECTOR_IDENTIFIER = "bbrose.intelligence.human_assertion_projector"
PROJECTOR_VERSION = "1.0"
PROJECTION_SCHEMA_VERSION = "human_assertion_projection/1.0"
EVIDENCE_DOMAIN = "evidence_assessment"
GENESIS_EVALUATION_TIMESTAMP = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)

CLASSIFICATION_ACTIONS = frozenset({
    authz.RECORD_INTELLIGENCE_CLASSIFICATION,
    authz.CORRECT_INTELLIGENCE_CLASSIFICATION,
})
EVIDENCE_ACTIONS = frozenset({
    authz.RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT,
    authz.REQUEST_INTELLIGENCE_CLARIFICATION,
})
# DIP-1C-5B: human semantic-metadata bundles. Same signed-event + supersession machinery,
# their own projection domain, and they touch no ReviewCandidate.
METADATA_ACTIONS = frozenset({
    authz.RECORD_HUMAN_SEMANTIC_METADATA,
    authz.CORRECT_HUMAN_SEMANTIC_METADATA,
})
# DIP-1C-5C-CORR-4: one signed event that invalidates a SET of prior metadata events.
# Deliberately its own action: only this one may carry `resolved_event_ids`, so multi-event
# invalidation can never be reached from an ordinary record or correction.
RESOLUTION_ACTIONS = frozenset({authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT})
SUPPORTED_ACTIONS = (CLASSIFICATION_ACTIONS | EVIDENCE_ACTIONS
                     | METADATA_ACTIONS | RESOLUTION_ACTIONS)
INTELLIGENCE_ACTIONS = frozenset({
    authz.VIEW_INTELLIGENCE_REVIEW_QUEUE,
    authz.CLAIM_INTELLIGENCE_REVIEW,
    *SUPPORTED_ACTIONS,
})

CLASSIFICATION_PAYLOAD_FIELDS = frozenset({
    "assertion_schema", "corpus_item_id", "review_candidate_id",
    "classification_domain", "asserted_label", "normalized_value", "explanation",
    "evidence_reference_ids", "evidence_source_hashes", "machine_classification_ids",
    "policy_id", "policy_version", "authz_snapshot",
})
EVIDENCE_PAYLOAD_FIELDS = frozenset({
    "intelligence_evidence_assessment_schema", "corpus_item_id",
    "review_candidate_id", "assessment", "explanation", "evidence_references",
    "authority_effect", "policy_id", "policy_version", "authz_snapshot",
})
EVIDENCE_SOURCE_FIELDS = frozenset({
    "evidence_reference_id", "evidence_hash", "source_artifact_id", "source_sha256",
})
DOMAIN_LABELS = {
    domain: labels for domain, labels, _roles in DOMAIN_SCHEMAS.values()
}


class ProjectionError(RuntimeError):
    code = "PROJECTION_ERROR"

    def __init__(self, code=None):
        self.code = code or self.code
        super().__init__(self.code)


class ProjectionVerificationError(ProjectionError):
    code = "PROJECTION_VERIFICATION_FAILED"


class ProjectionValidationError(ProjectionError):
    code = "PROJECTION_VALIDATION_FAILED"


class ProjectionPublicationError(ProjectionError):
    code = "PROJECTION_PUBLICATION_FAILED"


@dataclasses.dataclass(frozen=True)
class ProjectionRowSpec:
    corpus_item_id: str
    assertion_domain: str
    effective_state: str
    asserted_label: str
    normalized_value: object
    explanation_summary: str
    source_event_pk: int | None
    source_event_id: str
    source_sequence_number: int | None
    source_policy_id: str
    source_policy_version: str
    source_reviewer_id: int | None
    source_role: str
    evidence_assessment: str
    projection_metadata: dict
    effective_from: object | None
    expires_at: object | None
    warning_codes: tuple[str, ...]

    def logical_document(self):
        return {
            "corpus_item_id": self.corpus_item_id,
            "assertion_domain": self.assertion_domain,
            "effective_state": self.effective_state,
            "asserted_label": self.asserted_label,
            "normalized_value": self.normalized_value,
            "explanation_summary": self.explanation_summary,
            "source_event_id": self.source_event_id,
            "source_sequence_number": self.source_sequence_number,
            "source_policy_id": self.source_policy_id,
            "source_policy_version": self.source_policy_version,
            "source_reviewer_id": self.source_reviewer_id,
            "source_role": self.source_role,
            "evidence_assessment": self.evidence_assessment,
            "projection_metadata": self.projection_metadata,
            "effective_from": (
                self.effective_from.isoformat() if self.effective_from else None),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "warning_codes": list(self.warning_codes),
        }


@dataclasses.dataclass(frozen=True)
class ProjectionBuild:
    chain_head_hash: str
    terminal_sequence: int
    event_count: int
    evaluation_timestamp: object
    rows: tuple[ProjectionRowSpec, ...]
    projected_item_count: int
    warning_count: int
    output_hash: str

    def as_report(self):
        return {
            "projector_identifier": PROJECTOR_IDENTIFIER,
            "projector_version": PROJECTOR_VERSION,
            "projection_schema_version": PROJECTION_SCHEMA_VERSION,
            "source_chain_head_hash": self.chain_head_hash,
            "source_terminal_sequence": self.terminal_sequence,
            "event_count_examined": self.event_count,
            "projected_item_count": self.projected_item_count,
            "projection_row_count": len(self.rows),
            "warning_count": self.warning_count,
            "projection_output_hash": self.output_hash,
            "evaluation_timestamp": self.evaluation_timestamp.isoformat(),
        }


def _exact_fields(value, expected, code):
    if not isinstance(value, dict) or set(value) != expected:
        raise ProjectionValidationError(code)


def _bounded_text(value, maximum, code, *, allow_blank=False):
    if (not isinstance(value, str) or len(value) > maximum
            or (not allow_blank and not value.strip())):
        raise ProjectionValidationError(code)
    return value.strip()


def _canonical_uuid(value, code):
    try:
        parsed = uuid.UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProjectionValidationError(code) from exc
    if str(parsed) != value:
        raise ProjectionValidationError(code)
    return parsed


def _canonical_json(value, code):
    if not isinstance(value, (dict, list)):
        raise ProjectionValidationError(code)
    try:
        encoded = canonical.canonical_bytes({"value": value})
    except canonical.CanonicalizationError as exc:
        raise ProjectionValidationError(code) from exc
    if len(encoded) > 8192:
        raise ProjectionValidationError(code)
    return value


def _resolve_canonical_item(event, payload):
    if event.subject_type != "CorpusItem":
        raise ProjectionValidationError("ASSERTION_SUBJECT_TYPE_INVALID")
    item_id = _canonical_uuid(event.subject_id, "ASSERTION_SUBJECT_UUID_INVALID")
    if payload.get("corpus_item_id") != str(item_id):
        raise ProjectionValidationError("ASSERTION_SUBJECT_PAYLOAD_MISMATCH")
    if ProvenanceRecord.objects.filter(
        provenance_type=IDENTITY_ALIAS_PROVENANCE,
        normalized_machine_interpretation__legacy_corpus_item_id=str(item_id),
    ).exists():
        raise ProjectionValidationError("ASSERTION_SUBJECT_DEPRECATED")
    item = CorpusItem.objects.filter(pk=item_id).first()
    if item is None:
        raise ProjectionValidationError("ASSERTION_SUBJECT_MISSING")
    if item.item_kind == CorpusItem.Kind.DESIGN_ASSET:
        profile = getattr(item, "design_asset_profile", None)
        if profile is None or profile.dataset_identifier != C2_DATASET_ID:
            raise ProjectionValidationError("ASSERTION_DESIGN_IDENTITY_INVALID")
        try:
            resolved = resolve_design_asset_subject(
                profile.dataset_identifier, profile.candidate_source_key)
        except CandidateIdentityError as exc:
            raise ProjectionValidationError(
                "ASSERTION_DESIGN_IDENTITY_AMBIGUOUS") from exc
        if resolved.pk != item.pk:
            raise ProjectionValidationError("ASSERTION_DESIGN_IDENTITY_AMBIGUOUS")
    return item


def _verify_authorization_snapshot(event, payload):
    snap = payload.get("authz_snapshot")
    if not isinstance(snap, dict):
        raise ProjectionValidationError("AUTHORIZATION_SNAPSHOT_MISSING")
    # Defend the exact snapshot contract locally as well as through the existing verifier.
    if snap.get("snapshot_schema") != AUTHZ_SNAPSHOT_SCHEMA \
            or set(snap) != AUTHZ_SNAPSHOT_FIELDS:
        raise ProjectionValidationError("AUTHORIZATION_SNAPSHOT_SCHEMA_INVALID")
    contract_error = _snapshot_contract_error(event, snap)
    if contract_error:
        raise ProjectionValidationError("AUTHORIZATION_SNAPSHOT_INVALID")
    if (snap.get("actor_id") != event.actor_id
            or snap.get("role_used") != event.role_used
            or snap.get("action") != event.action
            or snap.get("subject_type") != event.subject_type
            or snap.get("subject_id") != event.subject_id):
        raise ProjectionValidationError("AUTHORIZATION_SNAPSHOT_ENVELOPE_MISMATCH")
    policy_version = snap.get("policy_version")
    policy = authz.policy_for_version(policy_version)
    if policy is None:
        raise ProjectionVerificationError("UNSUPPORTED_POLICY_VERSION")
    expected_authorizing = list(authz.authorizing_roles_for_version(
        policy_version, event.action, snap["active_roles"]))
    expected_role = authz.select_role_used_for_version(
        policy_version, event.action, snap["active_roles"])
    if (snap.get("authorizing_roles") != expected_authorizing
            or event.role_used != expected_role
            or event.role_used not in policy.get(event.action, ())):
        raise ProjectionValidationError("AUTHORIZATION_POLICY_BINDING_INVALID")
    if (payload.get("policy_id") != snap.get("policy_id")
            or payload.get("policy_version") != policy_version):
        raise ProjectionValidationError("ASSERTION_POLICY_PAYLOAD_MISMATCH")
    return snap


def _review_candidate(item, payload):
    candidate_id = _canonical_uuid(
        payload.get("review_candidate_id"), "REVIEW_CANDIDATE_UUID_INVALID")
    candidate = ReviewCandidate.objects.filter(
        pk=candidate_id, corpus_item=item).first()
    if candidate is None:
        raise ProjectionValidationError("REVIEW_CANDIDATE_SUBJECT_MISMATCH")
    return candidate


def _normalize_id_list(value, code, *, allow_empty=False):
    if (not isinstance(value, list) or len(value) > 128
            or (not allow_empty and not value)):
        raise ProjectionValidationError(code)
    parsed = [_canonical_uuid(raw, code) for raw in value]
    if len(parsed) != len(set(parsed)):
        raise ProjectionValidationError(code)
    return tuple(sorted(parsed, key=str))


def _verify_evidence(item, evidence_ids, source_rows, code):
    if not isinstance(source_rows, list) or len(source_rows) != len(evidence_ids):
        raise ProjectionValidationError(code)
    supplied = {}
    for source in source_rows:
        _exact_fields(source, EVIDENCE_SOURCE_FIELDS, code)
        evidence_id = _canonical_uuid(source["evidence_reference_id"], code)
        if evidence_id in supplied:
            raise ProjectionValidationError(code)
        supplied[evidence_id] = source
    if set(supplied) != set(evidence_ids):
        raise ProjectionValidationError(code)
    references = list(EvidenceReference.objects.select_related("source_artifact").filter(
        pk__in=evidence_ids, corpus_item=item, is_test_only=False))
    if len(references) != len(evidence_ids):
        raise ProjectionValidationError("ASSERTION_EVIDENCE_OWNERSHIP_INVALID")
    by_id = {row.pk: row for row in references}
    normalized = []
    for evidence_id in evidence_ids:
        row = by_id[evidence_id]
        source = supplied[evidence_id]
        if (source["evidence_hash"] != row.evidence_hash
                or source["source_artifact_id"] != str(row.source_artifact_id)
                or source["source_sha256"] != row.source_artifact.sha256):
            raise ProjectionValidationError("ASSERTION_EVIDENCE_HASH_MISMATCH")
        normalized.append({
            "evidence_reference_id": str(evidence_id),
            "evidence_hash": row.evidence_hash,
            "source_artifact_id": str(row.source_artifact_id),
            "source_sha256": row.source_artifact.sha256,
        })
    return normalized


def _classification_event(event):
    if event.schema_version != DECISION_EVENT_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_DECISION_EVENT_SCHEMA")
    payload = event.payload
    _exact_fields(payload, CLASSIFICATION_PAYLOAD_FIELDS,
                  "ASSERTION_PAYLOAD_SCHEMA_INVALID")
    if payload.get("assertion_schema") != ASSERTION_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_ASSERTION_SCHEMA")
    item = _resolve_canonical_item(event, payload)
    if evaluate_evidence_integrity(item).blocks_evidence_dependent_claims:
        raise ProjectionValidationError("EVIDENCE_SOURCE_INTEGRITY_UNRESOLVED")
    candidate = _review_candidate(item, payload)
    domain = _bounded_text(
        payload.get("classification_domain"), 64, "ASSERTION_DOMAIN_INVALID")
    labels = DOMAIN_LABELS.get(domain)
    if labels is None:
        raise ProjectionValidationError("ASSERTION_DOMAIN_SCHEMA_INVALID")
    label = _bounded_text(payload.get("asserted_label"), 255, "ASSERTION_LABEL_INVALID")
    if label not in labels:
        raise ProjectionValidationError("ASSERTION_LABEL_SCHEMA_INVALID")
    normalized_value = _canonical_json(
        payload.get("normalized_value"), "ASSERTION_NORMALIZED_VALUE_INVALID")
    explanation = _bounded_text(
        payload.get("explanation"), 4000, "ASSERTION_EXPLANATION_INVALID")
    evidence_ids = _normalize_id_list(
        payload.get("evidence_reference_ids"), "ASSERTION_EVIDENCE_IDS_INVALID")
    evidence = _verify_evidence(
        item, evidence_ids, payload.get("evidence_source_hashes"),
        "ASSERTION_EVIDENCE_SCHEMA_INVALID")
    _normalize_id_list(
        payload.get("machine_classification_ids"), "ASSERTION_MACHINE_IDS_INVALID",
        allow_empty=True)
    _verify_authorization_snapshot(event, payload)
    return {
        "event": event,
        "item": item,
        "candidate": candidate,
        "domain": domain,
        "label": label,
        "normalized_value": normalized_value,
        "explanation": explanation,
        "evidence": evidence,
    }


def _evidence_event(event):
    if event.schema_version != DECISION_EVENT_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_DECISION_EVENT_SCHEMA")
    payload = event.payload
    _exact_fields(payload, EVIDENCE_PAYLOAD_FIELDS,
                  "EVIDENCE_ASSESSMENT_PAYLOAD_SCHEMA_INVALID")
    if payload.get("intelligence_evidence_assessment_schema") \
            != EVIDENCE_ASSESSMENT_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_EVIDENCE_ASSESSMENT_SCHEMA")
    item = _resolve_canonical_item(event, payload)
    _review_candidate(item, payload)
    assessment = payload.get("assessment")
    if assessment not in {
            "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT",
            "CLARIFICATION_REQUIRED"}:
        raise ProjectionValidationError("EVIDENCE_ASSESSMENT_VALUE_INVALID")
    if (assessment == "EVIDENCE_SUFFICIENT"
            and evaluate_evidence_integrity(item).blocks_evidence_dependent_claims):
        raise ProjectionValidationError("EVIDENCE_SOURCE_INTEGRITY_UNRESOLVED")
    if ((event.action == authz.REQUEST_INTELLIGENCE_CLARIFICATION)
            != (assessment == "CLARIFICATION_REQUIRED")):
        raise ProjectionValidationError("EVIDENCE_ASSESSMENT_ACTION_MISMATCH")
    if payload.get("authority_effect") != "NONE":
        raise ProjectionValidationError("EVIDENCE_ASSESSMENT_AUTHORITY_INVALID")
    explanation = _bounded_text(
        payload.get("explanation"), 4000, "EVIDENCE_EXPLANATION_INVALID")
    raw_sources = payload.get("evidence_references")
    if not isinstance(raw_sources, list):
        raise ProjectionValidationError("EVIDENCE_ASSESSMENT_EVIDENCE_INVALID")
    ids = _normalize_id_list(
        [row.get("evidence_reference_id") if isinstance(row, dict) else None
         for row in raw_sources], "EVIDENCE_ASSESSMENT_EVIDENCE_INVALID")
    evidence = _verify_evidence(
        item, ids, raw_sources, "EVIDENCE_ASSESSMENT_EVIDENCE_INVALID")
    _verify_authorization_snapshot(event, payload)
    return {
        "event": event,
        "item": item,
        "assessment": assessment,
        "explanation": explanation,
        "evidence": evidence,
    }


def _source_fields(event):
    snap = event.payload["authz_snapshot"]
    return {
        "source_event_pk": event.pk,
        "source_event_id": event.event_id,
        "source_sequence_number": event.sequence_number,
        "source_policy_id": snap["policy_id"],
        "source_policy_version": snap["policy_version"],
        "source_reviewer_id": event.actor_id,
        "source_role": event.role_used,
        "effective_from": event.created_at,
    }


METADATA_PAYLOAD_FIELDS = frozenset({
    "assertion_schema", "assertion_domain", "corpus_item_id", "review_scope_id",
    "metadata_bundle", "evidence_reference_ids", "evidence_source_hashes",
    "policy_id", "policy_version", "authz_snapshot",
})
METADATA_CORRECTION_PAYLOAD_FIELDS = METADATA_PAYLOAD_FIELDS


def _metadata_event(event):
    """Parse a signed human-semantic-metadata event into a projection row. Re-validates the
    bundle defensively — the projector trusts nothing, it re-checks."""
    if event.schema_version != DECISION_EVENT_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_DECISION_EVENT_SCHEMA")
    payload = event.payload
    expected = (METADATA_CORRECTION_PAYLOAD_FIELDS
                if event.action == authz.CORRECT_HUMAN_SEMANTIC_METADATA
                else METADATA_PAYLOAD_FIELDS)
    _exact_fields(payload, expected, "METADATA_PAYLOAD_SCHEMA_INVALID")
    if payload.get("assertion_schema") != METADATA_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_METADATA_SCHEMA")
    if payload.get("assertion_domain") != METADATA_ASSERTION_DOMAIN:
        raise ProjectionValidationError("METADATA_DOMAIN_INVALID")
    item = _resolve_canonical_item(event, payload)
    if evaluate_evidence_integrity(item).blocks_evidence_dependent_claims:
        raise ProjectionValidationError("EVIDENCE_SOURCE_INTEGRITY_UNRESOLVED")
    try:
        bundle = build_metadata_bundle(payload.get("metadata_bundle") or {})
    except MetadataBundleError as exc:
        raise ProjectionValidationError("METADATA_BUNDLE_INVALID") from exc
    evidence_ids = _normalize_id_list(
        payload.get("evidence_reference_ids"), "METADATA_EVIDENCE_IDS_INVALID")
    evidence = _verify_evidence(
        item, evidence_ids, payload.get("evidence_source_hashes"),
        "METADATA_EVIDENCE_SCHEMA_INVALID")
    _verify_authorization_snapshot(event, payload)
    return {
        "event": event, "item": item, "candidate": None,
        "domain": METADATA_ASSERTION_DOMAIN, "label": "",
        "normalized_value": bundle,
        "explanation": (bundle.get("reviewer_notes") or "")[:4000],
        "evidence": evidence,
    }


RESOLUTION_PAYLOAD_FIELDS = frozenset({
    "resolution_schema", "corpus_item_id", "metadata_domain", "metadata_schema",
    "resolved_event_ids", "resolved_event_sequence_numbers", "prior_bundle_hashes",
    "final_metadata_bundle", "final_evidence_reference_ids", "final_source_hashes",
    "resolution_reason", "incident_type", "reviewer_explanation",
    "policy_id", "policy_version", "authz_snapshot",
})


def _resolution_event(event):
    """Parse a signed conflict-resolution event. Defensive re-validation, like every other
    projected event: the projector trusts the signature for authenticity, never for
    correctness of shape."""
    if event.schema_version != DECISION_EVENT_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_DECISION_EVENT_SCHEMA")
    payload = event.payload
    _exact_fields(payload, RESOLUTION_PAYLOAD_FIELDS, "RESOLUTION_PAYLOAD_SCHEMA_INVALID")
    if payload.get("resolution_schema") != RESOLUTION_SCHEMA:
        raise ProjectionVerificationError("UNSUPPORTED_RESOLUTION_SCHEMA")
    if payload.get("metadata_domain") != METADATA_ASSERTION_DOMAIN:
        raise ProjectionValidationError("METADATA_DOMAIN_INVALID")
    if payload.get("metadata_schema") != METADATA_SCHEMA:
        raise ProjectionValidationError("METADATA_SCHEMA_INVALID")
    item = _resolve_canonical_item(event, payload)
    if evaluate_evidence_integrity(item).blocks_evidence_dependent_claims:
        raise ProjectionValidationError("EVIDENCE_SOURCE_INTEGRITY_UNRESOLVED")
    resolved_ids = payload.get("resolved_event_ids")
    if (not isinstance(resolved_ids, list) or not resolved_ids
            or len(set(resolved_ids)) != len(resolved_ids)):
        raise ProjectionValidationError("RESOLVED_EVENT_IDS_INVALID")
    try:
        bundle = build_metadata_bundle(payload.get("final_metadata_bundle") or {})
    except MetadataBundleError as exc:
        raise ProjectionValidationError("METADATA_BUNDLE_INVALID") from exc
    evidence_ids = _normalize_id_list(
        payload.get("final_evidence_reference_ids"), "METADATA_EVIDENCE_IDS_INVALID")
    evidence = _verify_evidence(
        item, evidence_ids, payload.get("final_source_hashes"),
        "METADATA_EVIDENCE_SCHEMA_INVALID")
    _verify_authorization_snapshot(event, payload)
    return {
        "event": event, "item": item, "candidate": None,
        "domain": METADATA_ASSERTION_DOMAIN, "label": "",
        "normalized_value": bundle,
        "explanation": (payload.get("reviewer_explanation") or "")[:4000],
        "evidence": evidence, "resolved_event_ids": tuple(resolved_ids),
    }


def _metadata_rows(metadata):
    """Metadata supersession: single-parent corrections PLUS multi-parent resolutions.

    Kept separate from `_classification_rows` because only metadata has the multi-event
    form — generalising the classification path would make set-invalidation reachable from
    a domain that has no such contract.
    """
    grouped = {}
    by_pk = {row["event"].pk: row for row in metadata}
    by_event_id = {row["event"].event_id: row for row in metadata}
    superseded = set()
    for row in metadata:
        event = row["event"]
        if event.action in RESOLUTION_ACTIONS:
            for event_id in row["resolved_event_ids"]:
                target = by_event_id.get(event_id)
                if target is None:
                    raise ProjectionValidationError("RESOLUTION_TARGET_UNSUPPORTED")
                if target["event"].sequence_number >= event.sequence_number:
                    raise ProjectionValidationError("RESOLUTION_FORWARD_REFERENCE")
                if target["item"].pk != row["item"].pk:
                    raise ProjectionValidationError("RESOLUTION_SUBJECT_MISMATCH")
                if target["event"].pk in superseded:
                    raise ProjectionValidationError("RESOLUTION_TARGET_ALREADY_RESOLVED")
                superseded.add(target["event"].pk)
        elif event.action == authz.CORRECT_HUMAN_SEMANTIC_METADATA:
            prior = by_pk.get(event.supersedes_event_id)
            if prior is None:
                raise ProjectionValidationError("CORRECTION_TARGET_UNSUPPORTED")
            if prior["event"].sequence_number >= event.sequence_number:
                raise ProjectionValidationError("CORRECTION_FORWARD_REFERENCE")
            if (prior["item"].pk != row["item"].pk
                    or prior["domain"] != row["domain"]):
                raise ProjectionValidationError("CORRECTION_SUBJECT_DOMAIN_MISMATCH")
            superseded.add(prior["event"].pk)
        elif event.supersedes_event_id is not None:
            raise ProjectionValidationError("RECORD_ASSERTION_CANNOT_SUPERSEDE")
        grouped.setdefault((str(row["item"].pk), row["domain"]), []).append(row)
    return _rows_from_grouped(grouped, superseded)


def _classification_rows(classifications,
                         *, correction_action=authz.CORRECT_INTELLIGENCE_CLASSIFICATION):
    grouped = {}
    by_pk = {row["event"].pk: row for row in classifications}
    superseded = set()
    for row in classifications:
        event = row["event"]
        if event.action == correction_action:
            prior = by_pk.get(event.supersedes_event_id)
            if prior is None:
                raise ProjectionValidationError("CORRECTION_TARGET_UNSUPPORTED")
            if prior["event"].sequence_number >= event.sequence_number:
                raise ProjectionValidationError("CORRECTION_FORWARD_REFERENCE")
            if (prior["item"].pk != row["item"].pk
                    or prior["domain"] != row["domain"]):
                raise ProjectionValidationError("CORRECTION_SUBJECT_DOMAIN_MISMATCH")
            superseded.add(prior["event"].pk)
        elif event.supersedes_event_id is not None:
            raise ProjectionValidationError("RECORD_ASSERTION_CANNOT_SUPERSEDE")
        key = str(row["item"].pk), row["domain"]
        grouped.setdefault(key, []).append(row)
    return _rows_from_grouped(grouped, superseded)


def _rows_from_grouped(grouped, superseded):
    output = []
    for key in sorted(grouped):
        history = sorted(grouped[key], key=lambda row: row["event"].sequence_number)
        active = [row for row in history if row["event"].pk not in superseded]
        item_id, domain = key
        history_ids = [row["event"].event_id for row in history]
        if len(active) != 1:
            output.append(ProjectionRowSpec(
                corpus_item_id=item_id, assertion_domain=domain,
                effective_state=HumanAssertionProjection.EffectiveState.REVIEW_REQUIRED,
                asserted_label="", normalized_value={}, explanation_summary="",
                source_event_pk=None, source_event_id="", source_sequence_number=None,
                source_policy_id="", source_policy_version="", source_reviewer_id=None,
                source_role="",
                evidence_assessment=HumanAssertionProjection.EvidenceAssessment.NONE,
                projection_metadata={
                    "history_event_ids": history_ids,
                    "active_event_ids": [row["event"].event_id for row in active],
                }, effective_from=None, expires_at=None,
                warning_codes=("ACTIVE_ASSERTION_CONFLICT",)))
            continue
        current = active[0]
        event = current["event"]
        source = _source_fields(event)
        output.append(ProjectionRowSpec(
            corpus_item_id=item_id, assertion_domain=domain,
            effective_state=HumanAssertionProjection.EffectiveState.ASSERTED,
            asserted_label=current["label"],
            normalized_value=current["normalized_value"],
            explanation_summary=current["explanation"][:1000],
            evidence_assessment=HumanAssertionProjection.EvidenceAssessment.NONE,
            projection_metadata={
                "evidence_sources": current["evidence"],
                "history_event_ids": history_ids,
                "superseded_event_ids": [
                    row["event"].event_id for row in history
                    if row["event"].pk in superseded],
            }, expires_at=None, warning_codes=(), **source))
    return output


def _evidence_rows(assessments):
    grouped = {}
    for row in assessments:
        grouped.setdefault(str(row["item"].pk), []).append(row)
    output = []
    for item_id in sorted(grouped):
        history = sorted(
            grouped[item_id], key=lambda row: row["event"].sequence_number)
        current = history[-1]
        event = current["event"]
        assessment = current["assessment"]
        source = _source_fields(event)
        warnings = ("PRIOR_EVIDENCE_ASSESSMENTS",) if len(history) > 1 else ()
        output.append(ProjectionRowSpec(
            corpus_item_id=item_id, assertion_domain=EVIDENCE_DOMAIN,
            effective_state=assessment, asserted_label="", normalized_value={},
            explanation_summary=current["explanation"][:1000],
            evidence_assessment=assessment,
            projection_metadata={
                "evidence_sources": current["evidence"],
                "history_event_ids": [row["event"].event_id for row in history],
            }, expires_at=None, warning_codes=warnings, **source))
    return output


def _logical_output_hash(rows):
    document = {
        "projector_identifier": PROJECTOR_IDENTIFIER,
        "projector_version": PROJECTOR_VERSION,
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "projection_rows": [row.logical_document() for row in rows],
    }
    return canonical.content_hash(document)


def _head_checkpoint():
    try:
        head = DecisionChainHead.objects.get(pk=1)
    except DecisionChainHead.DoesNotExist as exc:
        raise ProjectionVerificationError("DECISION_CHAIN_HEAD_MISSING") from exc
    return head.terminal_event_hash or "", head.terminal_sequence_number


def build_projection(*, evaluation_at=None):
    chain = verify_chain()
    if not chain.ok:
        raise ProjectionVerificationError("DECISION_CHAIN_INVALID")
    head_hash, terminal_sequence = _head_checkpoint()
    events = list(DecisionEvent.objects.select_related("actor").order_by("sequence_number"))
    evaluation_at = evaluation_at or (
        events[-1].created_at if events else GENESIS_EVALUATION_TIMESTAMP)
    if not timezone.is_aware(evaluation_at):
        raise ProjectionValidationError("EVALUATION_TIMESTAMP_MUST_BE_AWARE")
    classifications = []
    assessments = []
    metadata = []
    for event in events:
        if event.action in INTELLIGENCE_ACTIONS and event.action not in SUPPORTED_ACTIONS:
            raise ProjectionValidationError("UNSUPPORTED_INTELLIGENCE_EVENT_ACTION")
        if event.action not in SUPPORTED_ACTIONS:
            continue
        ok, _ = verify_event(event)
        if not ok:
            raise ProjectionVerificationError("SUPPORTED_EVENT_SIGNATURE_INVALID")
        if event.action in CLASSIFICATION_ACTIONS:
            classifications.append(_classification_event(event))
        elif event.action in METADATA_ACTIONS:
            metadata.append(_metadata_event(event))
        elif event.action in RESOLUTION_ACTIONS:
            metadata.append(_resolution_event(event))
        else:
            assessments.append(_evidence_event(event))
    rows = tuple(sorted(
        _classification_rows(classifications)
        + _metadata_rows(metadata)
        + _evidence_rows(assessments),
        key=lambda row: (row.corpus_item_id, row.assertion_domain)))
    return ProjectionBuild(
        chain_head_hash=head_hash, terminal_sequence=terminal_sequence,
        event_count=len(events), evaluation_timestamp=evaluation_at, rows=rows,
        projected_item_count=len({row.corpus_item_id for row in rows}),
        warning_count=sum(len(row.warning_codes) for row in rows),
        output_hash=_logical_output_hash(rows))


def _generation_values(build):
    return {
        "projector_identifier": PROJECTOR_IDENTIFIER,
        "projector_version": PROJECTOR_VERSION,
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "source_chain_head_hash": build.chain_head_hash,
        "source_terminal_sequence": build.terminal_sequence,
        "projection_output_hash": build.output_hash,
        "evaluation_timestamp": build.evaluation_timestamp,
        "event_count_examined": build.event_count,
        "projected_item_count": build.projected_item_count,
        "warning_count": build.warning_count,
    }


def _persist_rows(generation, build):
    rows = [HumanAssertionProjection(
        projection_generation=generation, corpus_item_id=spec.corpus_item_id,
        assertion_domain=spec.assertion_domain, effective_state=spec.effective_state,
        asserted_label=spec.asserted_label, normalized_value=spec.normalized_value,
        explanation_summary=spec.explanation_summary,
        source_decision_event_id=spec.source_event_pk,
        source_sequence_number=spec.source_sequence_number,
        source_policy_id=spec.source_policy_id,
        source_policy_version=spec.source_policy_version,
        source_reviewer_id=spec.source_reviewer_id, source_role=spec.source_role,
        evidence_assessment=spec.evidence_assessment,
        projection_metadata=spec.projection_metadata, effective_from=spec.effective_from,
        expires_at=spec.expires_at, warning_codes=list(spec.warning_codes),
    ) for spec in build.rows]
    HumanAssertionProjection.objects.bulk_create(rows)
    if generation.assertion_projections.count() != len(build.rows):
        raise ProjectionValidationError("PROJECTION_ROW_COUNT_MISMATCH")


def _mark_failed(generation, error):
    safe_code = error.code if isinstance(error, ProjectionError) \
        else "INTERNAL_PROJECTOR_ERROR"
    IntelligenceProjectionGeneration.objects.filter(pk=generation.pk).update(
        status=IntelligenceProjectionGeneration.Status.FAILED,
        completed_at=timezone.now(), failure_count=1, failure_summary=safe_code)


def _published_matches(build):
    state = ProjectionPublicationState.objects.select_related("current_generation").filter(
        pk=1).first()
    if state is None:
        return None
    generation = state.current_generation
    if (generation.status == IntelligenceProjectionGeneration.Status.PUBLISHED
            and generation.projector_identifier == PROJECTOR_IDENTIFIER
            and generation.projector_version == PROJECTOR_VERSION
            and generation.projection_schema_version == PROJECTION_SCHEMA_VERSION
            and generation.source_chain_head_hash == build.chain_head_hash
            and generation.source_terminal_sequence == build.terminal_sequence
            and generation.projection_output_hash == build.output_hash
            and generation.evaluation_timestamp == build.evaluation_timestamp):
        return generation
    return None


@transaction.atomic
def _publish(generation, build, expected_chain_head):
    head = DecisionChainHead.objects.select_for_update().get(pk=1)
    current_hash = head.terminal_event_hash or ""
    if (current_hash != build.chain_head_hash
            or head.terminal_sequence_number != build.terminal_sequence):
        raise ProjectionPublicationError("CHAIN_CHANGED_BEFORE_PUBLICATION")
    if expected_chain_head is not None and current_hash != expected_chain_head:
        raise ProjectionPublicationError("EXPECTED_CHAIN_HEAD_MISMATCH")
    publication = ProjectionPublicationState.objects.select_for_update().filter(pk=1).first()
    now = timezone.now()
    if publication is not None:
        prior = publication.current_generation
        if prior.pk != generation.pk:
            IntelligenceProjectionGeneration.objects.filter(
                pk=prior.pk,
                status=IntelligenceProjectionGeneration.Status.PUBLISHED).update(
                    status=IntelligenceProjectionGeneration.Status.SUPERSEDED)
        publication.current_generation = generation
        publication.published_chain_head_hash = build.chain_head_hash
        publication.published_terminal_sequence = build.terminal_sequence
        publication.projector_identifier = PROJECTOR_IDENTIFIER
        publication.projector_version = PROJECTOR_VERSION
        publication.projection_schema_version = PROJECTION_SCHEMA_VERSION
        publication.published_at = now
        publication.save(_projection_write_token=_PROJECTION_WRITE_TOKEN)
    else:
        try:
            publication = ProjectionPublicationState(
                id=1, current_generation=generation,
                published_chain_head_hash=build.chain_head_hash,
                published_terminal_sequence=build.terminal_sequence,
                projector_identifier=PROJECTOR_IDENTIFIER,
                projector_version=PROJECTOR_VERSION,
                projection_schema_version=PROJECTION_SCHEMA_VERSION, published_at=now)
            publication.save(
                _projection_write_token=_PROJECTION_WRITE_TOKEN, force_insert=True)
        except IntegrityError as exc:
            raise ProjectionPublicationError("PUBLICATION_SINGLETON_RACE") from exc
    generation.status = IntelligenceProjectionGeneration.Status.PUBLISHED
    generation.published_at = now
    generation.completed_at = now
    generation.save(
        _projection_write_token=_PROJECTION_WRITE_TOKEN,
        update_fields=("status", "published_at", "completed_at"))


def _expected_hash(value):
    if value is None:
        return None
    if value == "GENESIS":
        return ""
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise ProjectionValidationError("EXPECTED_CHAIN_HEAD_INVALID")
    return value


def rebuild_assertion_projections(*, apply=False, evaluation_at=None,
                                  expected_chain_head=None):
    expected_chain_head = _expected_hash(expected_chain_head)
    generation = None
    if not apply:
        build = build_projection(evaluation_at=evaluation_at)
        if (expected_chain_head is not None
                and build.chain_head_hash != expected_chain_head):
            raise ProjectionVerificationError("EXPECTED_CHAIN_HEAD_MISMATCH")
        existing = _published_matches(build)
        report = build.as_report()
        report.update({
            "mode": "dry-run", "would_publish": existing is None,
            "idempotent": existing is not None,
            "published_generation_id": str(existing.pk) if existing else None,
        })
        return report

    checkpoint_hash, checkpoint_sequence = _head_checkpoint()
    seed_evaluation = evaluation_at or GENESIS_EVALUATION_TIMESTAMP
    generation = IntelligenceProjectionGeneration.objects.create(
        projector_identifier=PROJECTOR_IDENTIFIER, projector_version=PROJECTOR_VERSION,
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
        source_chain_head_hash=checkpoint_hash,
        source_terminal_sequence=checkpoint_sequence,
        evaluation_timestamp=seed_evaluation,
        status=IntelligenceProjectionGeneration.Status.BUILDING)
    try:
        build = build_projection(evaluation_at=evaluation_at)
        if (build.chain_head_hash != checkpoint_hash
                or build.terminal_sequence != checkpoint_sequence):
            raise ProjectionVerificationError("CHAIN_CHANGED_DURING_BUILD")
        if (expected_chain_head is not None
                and build.chain_head_hash != expected_chain_head):
            raise ProjectionVerificationError("EXPECTED_CHAIN_HEAD_MISMATCH")
        existing = _published_matches(build)
        if existing is not None:
            generation.delete()
            report = build.as_report()
            report.update({
                "mode": "apply", "published": False, "idempotent": True,
                "generation_id": str(existing.pk), "rows_created": 0,
            })
            return report
        values = _generation_values(build)
        IntelligenceProjectionGeneration.objects.filter(pk=generation.pk).update(**values)
        generation.refresh_from_db()
        _persist_rows(generation, build)
        generation.status = IntelligenceProjectionGeneration.Status.VALIDATED
        generation.save(
            _projection_write_token=_PROJECTION_WRITE_TOKEN,
            update_fields=("status",))
        _publish(generation, build, expected_chain_head)
        report = build.as_report()
        report.update({
            "mode": "apply", "published": True, "idempotent": False,
            "generation_id": str(generation.pk), "rows_created": len(build.rows),
        })
        return report
    except Exception as exc:
        if generation.pk and IntelligenceProjectionGeneration.objects.filter(
                pk=generation.pk).exists():
            _mark_failed(generation, exc)
        raise
