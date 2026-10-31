"""DIP-1B-3 review workflow and signed human-intelligence assertions."""
from __future__ import annotations

import dataclasses
import uuid

from django.db import transaction
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.authorization import (
    authorize_actor, build_authorization_snapshot,
)
from apps.accounts.decision_chain import append_decision, verify_chain, verify_event
from apps.accounts.models import DecisionEvent
from apps.accounts.security import key_epochs
from apps.accounts.security import canonical

from .identity import (
    IDENTITY_ALIAS_PROVENANCE, SUPPORTED_ASSET_IDENTITY_DATASETS,
    resolve_design_asset_subject,
)
from .evidence_integrity import evaluate_evidence_integrity
from .models import (
    CorpusItem, EvidenceReference, MachineClassification, ProvenanceRecord,
    ReviewCandidate,
)

ASSERTION_SCHEMA = "intelligence_assertion/1.0"
EVIDENCE_ASSESSMENT_SCHEMA = "intelligence_evidence_assessment/1.0"
CURRENT_ASSERTION_SCHEMA = "current_intelligence_assertions/1.0"
SUBJECT_TYPE = "CorpusItem"
EVIDENCE_ASSESSMENTS = frozenset({
    "EVIDENCE_SUFFICIENT", "EVIDENCE_INSUFFICIENT", "CLARIFICATION_REQUIRED",
})
CLASSIFICATION_FIELDS = frozenset({
    "corpus_item_uuid", "review_candidate_uuid", "classification_domain",
    "classification_label", "normalized_value", "explanation",
    "evidence_reference_ids", "machine_classification_ids",
})
CORRECTION_FIELDS = CLASSIFICATION_FIELDS | {"supersedes_event_id"}
EVIDENCE_FIELDS = frozenset({
    "corpus_item_uuid", "review_candidate_uuid", "assessment", "explanation",
    "evidence_reference_ids",
})
RESERVED_REQUEST_FIELDS = frozenset({
    "actor", "actor_id", "role", "role_used", "active_roles", "authorizing_roles",
    "authorization_snapshot", "authz_snapshot", "sequence_number",
    "previous_event_hash", "content_hash", "hmac_signature", "hmac", "event_id",
    "signing_key_id", "signature_algorithm", "policy_id", "policy_version",
    "created_at", "timestamp", "supersedes_event", "supersedes_event_id",
})

DOMAIN_SCHEMAS = {
    ReviewCandidate.ReviewType.HISTORICAL_MEMORY: (
        "historical_memory", frozenset({
            "REFERENCE_MEMORY", "STYLE_SIGNAL", "ARCHIVAL_CONTEXT", "OUT_OF_SCOPE",
        }), frozenset({authz.DESIGN_REVIEWER, authz.BRAND_ADMIN})),
    ReviewCandidate.ReviewType.DESIGN_ASSET: (
        "design_asset_type", frozenset({
            "LOGO_CANDIDATE", "PACKAGING_CANDIDATE", "PRODUCT_GRAPHIC",
            "REFERENCE_MATERIAL", "OTHER_DESIGN_ASSET",
        }), frozenset({authz.DESIGN_REVIEWER, authz.BRAND_ADMIN})),
    ReviewCandidate.ReviewType.FONT_TECHNICAL: (
        "font_technical_suitability", frozenset({
            "SUITABLE_FOR_REVIEW", "NEEDS_TECHNICAL_REVIEW",
            "UNSUITABLE_TECHNICAL",
        }), frozenset({authz.DESIGN_REVIEWER})),
    ReviewCandidate.ReviewType.BRAND_IDENTITY: (
        "brand_identity_candidate", frozenset({
            "BBROSE_CANDIDATE", "RELATED_BRAND_CANDIDATE", "UNRESOLVED",
        }), frozenset({authz.BRAND_ADMIN, authz.BUSINESS_OWNER})),
    ReviewCandidate.ReviewType.PALETTE_OBSERVATION: (
        "palette_observation", frozenset({
            "OBSERVED_BRAND_PALETTE", "REFERENCE_PALETTE", "UNRESOLVED",
        }), frozenset({authz.BRAND_ADMIN, authz.DESIGN_REVIEWER})),
}

SIGNED_ACTIONS = frozenset({
    authz.RECORD_INTELLIGENCE_CLASSIFICATION,
    authz.CORRECT_INTELLIGENCE_CLASSIFICATION,
    authz.RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT,
    authz.REQUEST_INTELLIGENCE_CLARIFICATION,
})
CLASSIFICATION_ACTIONS = frozenset({
    authz.RECORD_INTELLIGENCE_CLASSIFICATION,
    authz.CORRECT_INTELLIGENCE_CLASSIFICATION,
})


class ReviewServiceError(RuntimeError):
    pass


class ReviewAuthorizationDenied(ReviewServiceError):
    pass


class ReviewConflict(ReviewServiceError):
    pass


class AssertionValidationError(ReviewServiceError):
    pass


def _subject(item):
    return SUBJECT_TYPE, str(item.pk)


def _authorize(user, action, item):
    result = authorize_actor(user, action, subject=_subject(item))
    if not result.allowed:
        raise ReviewAuthorizationDenied(f"not authorized: {result.reason_code}")
    return result


def _ensure_exact_fields(payload, expected):
    if not isinstance(payload, dict):
        raise AssertionValidationError("request payload must be an object")
    supplied = set(payload)
    reserved = supplied & RESERVED_REQUEST_FIELDS
    # supersedes_event_id is a caller field only for the correction contract.
    if expected is CORRECTION_FIELDS:
        reserved.discard("supersedes_event_id")
    if reserved:
        raise AssertionValidationError(
            f"request may not supply server-derived fields: {sorted(reserved)}")
    missing = expected - supplied
    unknown = supplied - expected
    if missing or unknown:
        raise AssertionValidationError(
            f"request fields are not exact; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}")


def _uuid(value, label):
    try:
        parsed = uuid.UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise AssertionValidationError(f"{label} is not a UUID") from exc
    if str(parsed) != value:
        raise AssertionValidationError(f"{label} is not canonical")
    return parsed


def _canonical_item(item_id):
    legacy = ProvenanceRecord.objects.filter(
        provenance_type=IDENTITY_ALIAS_PROVENANCE,
        normalized_machine_interpretation__legacy_corpus_item_id=str(item_id),
    ).exists()
    if legacy:
        raise AssertionValidationError("deprecated corpus UUIDs cannot be event subjects")
    item = CorpusItem.objects.filter(pk=item_id).first()
    if item is None:
        raise AssertionValidationError("canonical corpus item does not exist")
    if item.item_kind == CorpusItem.Kind.DESIGN_ASSET:
        profile = getattr(item, "design_asset_profile", None)
        if (profile is None or profile.dataset_identifier
                not in SUPPORTED_ASSET_IDENTITY_DATASETS):
            raise AssertionValidationError(
                "design-asset subject is outside approved dataset identity")
        resolved = resolve_design_asset_subject(
            profile.dataset_identifier, profile.candidate_source_key)
        if resolved.pk != item.pk:
            raise AssertionValidationError("design-asset subject is not canonical")
    return item


def _task_from_payload(payload, *, lock=False):
    item_id = _uuid(payload["corpus_item_uuid"], "corpus_item_uuid")
    candidate_id = _uuid(payload["review_candidate_uuid"], "review_candidate_uuid")
    item = _canonical_item(item_id)
    # Lock only the workflow row; nullable assignee joins cannot be FOR UPDATE targets on
    # PostgreSQL and the actor identity is already available as assigned_to_id.
    queryset = ReviewCandidate.objects.select_related("corpus_item")
    if lock:
        queryset = queryset.select_for_update()
    candidate = queryset.filter(pk=candidate_id).first()
    if candidate is None or candidate.corpus_item_id != item.pk:
        raise AssertionValidationError("review candidate does not match the corpus item")
    return item, candidate


def _bounded_text(value, label, maximum, *, required=True):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise AssertionValidationError(f"{label} must be a bounded string")
    return value.strip()


def _canonical_json(value):
    if not isinstance(value, (dict, list)):
        raise AssertionValidationError("normalized_value must be a JSON object or list")
    try:
        raw = canonical.canonical_bytes(value)
    except canonical.CanonicalizationError as exc:
        raise AssertionValidationError("normalized_value is not canonical JSON") from exc
    if len(raw) > 8192:
        raise AssertionValidationError("normalized_value exceeds 8192 bytes")
    return value


def _id_list(value, label, *, allow_empty):
    if not isinstance(value, list) or (not allow_empty and not value) or len(value) > 128:
        raise AssertionValidationError(f"{label} must be a bounded list")
    parsed = [_uuid(raw, label) for raw in value]
    if len(parsed) != len(set(parsed)):
        raise AssertionValidationError(f"{label} contains duplicates")
    return parsed


def _evidence_payload(item, identifiers):
    rows = list(EvidenceReference.objects.select_related("source_artifact").filter(
        pk__in=identifiers, corpus_item=item, is_test_only=False).order_by("pk"))
    if len(rows) != len(identifiers):
        raise AssertionValidationError(
            "all evidence references must be non-test evidence for the same corpus item")
    by_id = {row.pk: row for row in rows}
    return [{
        "evidence_reference_id": str(by_id[identifier].pk),
        "evidence_hash": by_id[identifier].evidence_hash,
        "source_artifact_id": str(by_id[identifier].source_artifact_id),
        "source_sha256": by_id[identifier].source_artifact.sha256,
    } for identifier in identifiers]


def _machine_ids(item, identifiers):
    count = MachineClassification.objects.filter(
        pk__in=identifiers, corpus_item=item).count()
    if count != len(identifiers):
        raise AssertionValidationError(
            "all machine classifications must belong to the same corpus item")
    return [str(identifier) for identifier in identifiers]


def _classification_contract(payload, *, correction=False):
    _ensure_exact_fields(payload, CORRECTION_FIELDS if correction else CLASSIFICATION_FIELDS)
    item, candidate = _task_from_payload(payload, lock=True)
    domain, labels, roles = DOMAIN_SCHEMAS[candidate.review_type]
    if payload["classification_domain"] != domain:
        raise AssertionValidationError("classification domain does not match review type")
    if payload["classification_label"] not in labels:
        raise AssertionValidationError("classification label is outside the domain schema")
    normalized = _canonical_json(payload["normalized_value"])
    explanation = _bounded_text(payload["explanation"], "explanation", 4000)
    evidence_ids = _id_list(
        payload["evidence_reference_ids"], "evidence_reference_ids", allow_empty=False)
    evidence_rows = list(EvidenceReference.objects.select_related("source_artifact").filter(
        pk__in=evidence_ids, corpus_item=item, is_test_only=False))
    integrity = evaluate_evidence_integrity(item, evidence_rows)
    if integrity.blocks_evidence_dependent_claims:
        raise AssertionValidationError(
            "evidence integrity is unresolved; evidence-dependent classification "
            "is unavailable")
    machine_ids = _id_list(
        payload["machine_classification_ids"], "machine_classification_ids",
        allow_empty=True)
    return (
        item, candidate, domain, roles, normalized, explanation,
        _evidence_payload(item, evidence_ids), _machine_ids(item, machine_ids),
    )


def _signed_payload(*, action, user, item, candidate, domain, label, normalized,
                    explanation, evidence, machine_ids):
    at = timezone.now()
    result = _authorize(user, action, item)
    _, _, domain_roles = DOMAIN_SCHEMAS[candidate.review_type]
    if result.role_used not in domain_roles:
        raise ReviewAuthorizationDenied(
            f"role {result.role_used} is not authorized for {candidate.review_type}")
    return {
        "assertion_schema": ASSERTION_SCHEMA,
        "corpus_item_id": str(item.pk),
        "review_candidate_id": str(candidate.pk),
        "classification_domain": domain,
        "asserted_label": label,
        "normalized_value": normalized,
        "explanation": explanation,
        "evidence_reference_ids": [row["evidence_reference_id"] for row in evidence],
        "evidence_source_hashes": [
            {
                "evidence_reference_id": row["evidence_reference_id"],
                "evidence_hash": row["evidence_hash"],
                "source_artifact_id": row["source_artifact_id"],
                "source_sha256": row["source_sha256"],
            }
            for row in evidence
        ],
        "machine_classification_ids": machine_ids,
        "policy_id": authz.POLICY_ID,
        "policy_version": authz.POLICY_VERSION,
        "authz_snapshot": build_authorization_snapshot(user, result, at),
    }


@transaction.atomic
def claim_review_candidate(*, user, candidate_id):
    candidate = ReviewCandidate.objects.select_for_update().select_related(
        "corpus_item").get(pk=candidate_id)
    _authorize(user, authz.CLAIM_INTELLIGENCE_REVIEW, candidate.corpus_item)
    if candidate.assigned_to_id == user.pk:
        if candidate.workflow_status == ReviewCandidate.Status.NEEDS_INFORMATION:
            candidate.workflow_status = ReviewCandidate.Status.CLAIMED
            candidate.save(update_fields=("workflow_status", "updated_at"))
        return candidate
    if candidate.assigned_to_id is not None:
        raise ReviewConflict("review candidate is already assigned; stealing is forbidden")
    if candidate.workflow_status not in (
            ReviewCandidate.Status.OPEN, ReviewCandidate.Status.NEEDS_INFORMATION):
        raise ReviewConflict("review candidate is not claimable")
    candidate.assigned_to = user
    candidate.assigned_at = timezone.now()
    candidate.workflow_status = ReviewCandidate.Status.CLAIMED
    candidate.save(update_fields=(
        "assigned_to", "assigned_at", "workflow_status", "updated_at"))
    return candidate


@transaction.atomic
def release_review_candidate(*, user, candidate_id):
    candidate = ReviewCandidate.objects.select_for_update().select_related(
        "corpus_item").get(pk=candidate_id)
    _authorize(user, authz.CLAIM_INTELLIGENCE_REVIEW, candidate.corpus_item)
    if candidate.assigned_to_id != user.pk:
        raise ReviewConflict("only the current assignee may release a review candidate")
    if candidate.workflow_status == ReviewCandidate.Status.COMPLETED:
        raise ReviewConflict("a completed review candidate cannot be released")
    candidate.assigned_to = None
    candidate.assigned_at = None
    candidate.workflow_status = ReviewCandidate.Status.OPEN
    candidate.save(update_fields=(
        "assigned_to", "assigned_at", "workflow_status", "updated_at"))
    return candidate


@transaction.atomic
def record_intelligence_classification(*, user, payload):
    (item, candidate, domain, _, normalized, explanation,
     evidence, machine_ids) = _classification_contract(payload)
    if (candidate.assigned_to_id != user.pk
            or candidate.workflow_status != ReviewCandidate.Status.CLAIMED):
        raise ReviewConflict("classification requires a review claimed by the actor")
    signed_payload = _signed_payload(
        action=authz.RECORD_INTELLIGENCE_CLASSIFICATION, user=user, item=item,
        candidate=candidate, domain=domain, label=payload["classification_label"],
        normalized=normalized, explanation=explanation, evidence=evidence,
        machine_ids=machine_ids)
    event = append_decision(
        user=user, action=authz.RECORD_INTELLIGENCE_CLASSIFICATION,
        subject=_subject(item), payload=signed_payload)
    candidate.workflow_status = ReviewCandidate.Status.COMPLETED
    candidate.save(update_fields=("workflow_status", "updated_at"))
    return event


@transaction.atomic
def correct_intelligence_classification(*, user, payload):
    (item, candidate, domain, _, normalized, explanation,
     evidence, machine_ids) = _classification_contract(payload, correction=True)
    prior = DecisionEvent.objects.filter(event_id=payload["supersedes_event_id"]).first()
    if (prior is None or prior.action not in CLASSIFICATION_ACTIONS
            or prior.subject_type != SUBJECT_TYPE or prior.subject_id != str(item.pk)
            or prior.payload.get("classification_domain") != domain
            or prior.payload.get("review_candidate_id") != str(candidate.pk)):
        raise AssertionValidationError(
            "correction must reference a prior classification for the same item/domain")
    current = read_current_assertions(item)
    domain_current = current.current_by_domain.get(domain)
    if current.state == "REVIEW_REQUIRED" or domain_current is None:
        raise AssertionValidationError("current classification cannot be established")
    if domain_current.event_id != prior.event_id:
        raise AssertionValidationError("correction must supersede the current assertion")
    signed_payload = _signed_payload(
        action=authz.CORRECT_INTELLIGENCE_CLASSIFICATION, user=user, item=item,
        candidate=candidate, domain=domain, label=payload["classification_label"],
        normalized=normalized, explanation=explanation, evidence=evidence,
        machine_ids=machine_ids)
    event = append_decision(
        user=user, action=authz.CORRECT_INTELLIGENCE_CLASSIFICATION,
        subject=_subject(item), payload=signed_payload, supersedes=prior)
    candidate.workflow_status = ReviewCandidate.Status.COMPLETED
    candidate.save(update_fields=("workflow_status", "updated_at"))
    return event


@transaction.atomic
def record_intelligence_evidence_assessment(*, user, payload):
    _ensure_exact_fields(payload, EVIDENCE_FIELDS)
    item, candidate = _task_from_payload(payload, lock=True)
    assessment = payload["assessment"]
    if assessment not in EVIDENCE_ASSESSMENTS:
        raise AssertionValidationError("evidence assessment is outside the schema")
    if (candidate.assigned_to_id != user.pk
            or candidate.workflow_status != ReviewCandidate.Status.CLAIMED):
        raise ReviewConflict("evidence assessment requires a review claimed by the actor")
    explanation = _bounded_text(payload["explanation"], "explanation", 4000)
    evidence_ids = _id_list(
        payload["evidence_reference_ids"], "evidence_reference_ids", allow_empty=False)
    evidence_rows = list(EvidenceReference.objects.select_related("source_artifact").filter(
        pk__in=evidence_ids, corpus_item=item, is_test_only=False))
    integrity = evaluate_evidence_integrity(item, evidence_rows)
    if (assessment == "EVIDENCE_SUFFICIENT"
            and integrity.blocks_evidence_dependent_claims):
        raise AssertionValidationError(
            "evidence integrity is unresolved; EVIDENCE_SUFFICIENT is unavailable")
    action = (authz.REQUEST_INTELLIGENCE_CLARIFICATION
              if assessment == "CLARIFICATION_REQUIRED"
              else authz.RECORD_INTELLIGENCE_EVIDENCE_ASSESSMENT)
    at = timezone.now()
    result = _authorize(user, action, item)
    event_payload = {
        "intelligence_evidence_assessment_schema": EVIDENCE_ASSESSMENT_SCHEMA,
        "corpus_item_id": str(item.pk),
        "review_candidate_id": str(candidate.pk),
        "assessment": assessment,
        "explanation": explanation,
        "evidence_references": _evidence_payload(item, evidence_ids),
        "authority_effect": "NONE",
        "policy_id": authz.POLICY_ID,
        "policy_version": authz.POLICY_VERSION,
        "authz_snapshot": build_authorization_snapshot(user, result, at),
    }
    event = append_decision(
        user=user, action=action, subject=_subject(item), payload=event_payload)
    if assessment in {"EVIDENCE_INSUFFICIENT", "CLARIFICATION_REQUIRED"}:
        candidate.workflow_status = ReviewCandidate.Status.NEEDS_INFORMATION
        candidate.save(update_fields=("workflow_status", "updated_at"))
    return event


@dataclasses.dataclass(frozen=True)
class AssertionHistoryEntry:
    event_id: str
    sequence_number: int
    action: str
    domain: str
    label: str
    effective: bool
    actor_id: int
    role_used: str
    created_at: object
    payload: dict


@dataclasses.dataclass(frozen=True)
class CurrentAssertionResult:
    schema: str
    state: str
    reason: str
    current_by_domain: dict[str, AssertionHistoryEntry]
    history: tuple[AssertionHistoryEntry, ...]


def _reader_failure(reason):
    return CurrentAssertionResult(
        schema=CURRENT_ASSERTION_SCHEMA, state="REVIEW_REQUIRED", reason=reason,
        current_by_domain={}, history=())


def read_current_assertions(item):
    """Temporary verified reader. It never writes or projects operational authority."""
    if not isinstance(item, CorpusItem) or item.pk is None:
        return _reader_failure("CANONICAL_ITEM_REQUIRED")
    chain = verify_chain()
    if not chain.ok:
        return _reader_failure("DECISION_CHAIN_INVALID")
    try:
        if _canonical_item(item.pk).pk != item.pk:
            return _reader_failure("CANONICAL_ITEM_REQUIRED")
    except AssertionValidationError:
        return _reader_failure("CANONICAL_ITEM_REQUIRED")
    events = list(DecisionEvent.objects.filter(
        subject_type=SUBJECT_TYPE, subject_id=str(item.pk),
        action__in=SIGNED_ACTIONS).order_by("sequence_number"))
    classifications = []
    superseded_pks = set()
    for event in events:
        ok, problems = verify_event(event)
        if not ok:
            if problems and all(key_epochs.is_legacy_problem(p)
                                for p in problems):
                return _reader_failure(
                    key_epochs.CORPUS_AUTHORIZATION_REAFFIRMATION_REQUIRED)
            return _reader_failure("EVENT_SIGNATURE_INVALID")
        payload = event.payload if isinstance(event.payload, dict) else {}
        if event.action in CLASSIFICATION_ACTIONS:
            if payload.get("assertion_schema") != ASSERTION_SCHEMA:
                return _reader_failure("ASSERTION_SCHEMA_INVALID")
            try:
                candidate = ReviewCandidate.objects.get(
                    pk=payload.get("review_candidate_id"), corpus_item=item)
            except (ReviewCandidate.DoesNotExist, ValueError, TypeError):
                return _reader_failure("ASSERTION_SUBJECT_NOT_CANONICAL")
            expected_domain = DOMAIN_SCHEMAS[candidate.review_type][0]
            if (payload.get("corpus_item_id") != str(item.pk)
                    or payload.get("classification_domain") != expected_domain):
                return _reader_failure("ASSERTION_SUBJECT_NOT_CANONICAL")
            classifications.append(event)
            if event.supersedes_event_id is not None:
                superseded_pks.add(event.supersedes_event_id)
        elif payload.get("intelligence_evidence_assessment_schema") \
                != EVIDENCE_ASSESSMENT_SCHEMA:
            return _reader_failure("EVIDENCE_ASSESSMENT_SCHEMA_INVALID")
    classification_ids = {event.pk for event in classifications}
    history = tuple(AssertionHistoryEntry(
        event_id=event.event_id, sequence_number=event.sequence_number,
        action=event.action,
        domain=(event.payload["classification_domain"]
                if event.pk in classification_ids else "evidence_assessment"),
        label=(event.payload["asserted_label"]
               if event.pk in classification_ids else event.payload["assessment"]),
        effective=(event.pk not in superseded_pks
                   if event.pk in classification_ids else True),
        actor_id=event.actor_id, role_used=event.role_used,
        created_at=event.created_at, payload=event.payload,
    ) for event in events)
    current = {}
    for entry in history:
        if entry.action in CLASSIFICATION_ACTIONS and entry.effective:
            prior = current.get(entry.domain)
            if prior is not None:
                return _reader_failure("MULTIPLE_CURRENT_ASSERTIONS")
            current[entry.domain] = entry
    return CurrentAssertionResult(
        schema=CURRENT_ASSERTION_SCHEMA,
        state="CURRENT" if current else "NONE",
        reason="VERIFIED_SIGNED_HISTORY" if current else "NO_SIGNED_CLASSIFICATION",
        current_by_domain=current, history=history)
