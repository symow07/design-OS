"""Deterministic governance projection with shadow build and atomic publication."""
from __future__ import annotations

import dataclasses
import datetime as dt

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.authorization import AUTHZ_SNAPSHOT_FIELDS, AUTHZ_SNAPSHOT_SCHEMA
from apps.accounts.chain_verification import _snapshot_contract_error
from apps.accounts.decision_chain import verify_chain, verify_event
from apps.accounts.models import DECISION_EVENT_SCHEMA, DecisionChainHead, DecisionEvent
from apps.accounts.security import canonical

from .governance import (
    AUTHORITY_EFFECT_NONE,
    FINALIZE_ACTION,
    FINALIZE_ACTIONS,
    GOVERNANCE_DECISION_SCHEMA,
    GOVERNANCE_DECISION_VERSION,
    GOVERNANCE_REVOCATION_SCHEMA,
    GOVERNANCE_SUBJECT_TYPE,
    GOVERNANCE_TYPES,
    REQUIRED_ATTESTATION_CATEGORIES,
    REVOKE_ACTION,
    REVOKE_ACTIONS,
    GovernanceEligibilityError,
    GovernanceValidationError,
    _evidence_sources,
    _evidence_tokens,
    _validate_integrity_summary,
    governance_scope_hash,
    normalize_governance_scope,
    resolve_governance_candidate,
    validate_governance_attestations,
    verify_governance_evidence,
)
from .models import (
    _GOVERNANCE_PROJECTION_WRITE_TOKEN,
    GovernanceDecisionProjection,
    GovernanceProjectionGeneration,
    GovernanceProjectionPublicationState,
)

PROJECTOR_IDENTIFIER = "bbrose.intelligence.governance_projector"
PROJECTOR_VERSION = "1.0"
PROJECTION_SCHEMA_VERSION = "intelligence_governance_projection/1.0"
GENESIS_EVALUATION_TIMESTAMP = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)

FINAL_PAYLOAD_FIELDS = frozenset({
    "governance_decision_schema", "governance_type", "selected_corpus_item_id",
    "normalized_scope", "governance_scope_hash", "decision_version",
    "decision_scope_hash", "attestation_event_ids", "attestation_content_hashes",
    "evidence_sources", "evidence_integrity_summary", "supersedes_final_event_id",
    "authority_effect", "policy_id", "policy_version", "authz_snapshot",
})
REVOCATION_PAYLOAD_FIELDS = frozenset({
    "governance_revocation_schema", "governance_type", "selected_corpus_item_id",
    "normalized_scope", "governance_scope_hash", "decision_version",
    "revoked_final_event_id", "revoked_final_content_hash", "reason",
    "authority_effect", "policy_id", "policy_version", "authz_snapshot",
})
ATTESTATION_HASH_FIELDS = frozenset({"event_id", "content_hash"})


class GovernanceProjectionError(RuntimeError):
    code = "GOVERNANCE_PROJECTION_ERROR"

    def __init__(self, code=None):
        self.code = code or self.code
        super().__init__(self.code)


class GovernanceProjectionVerificationError(GovernanceProjectionError):
    code = "GOVERNANCE_PROJECTION_VERIFICATION_FAILED"


class GovernanceProjectionValidationError(GovernanceProjectionError):
    code = "GOVERNANCE_PROJECTION_VALIDATION_FAILED"


class GovernanceProjectionPublicationError(GovernanceProjectionError):
    code = "GOVERNANCE_PROJECTION_PUBLICATION_FAILED"


@dataclasses.dataclass(frozen=True)
class ParsedFinal:
    event: DecisionEvent
    item: object
    governance_type: str
    normalized_scope: dict
    scope_hash: str
    attestation_event_ids: tuple[str, ...]
    policy_id: str
    policy_version: str
    evidence_status: str
    evidence_reasons: tuple[str, ...]
    review_required: bool
    review_reasons: tuple[str, ...]

    @property
    def key(self):
        return self.governance_type, self.scope_hash


@dataclasses.dataclass(frozen=True)
class ParsedRevocation:
    event: DecisionEvent
    target_event_id: str
    governance_type: str
    normalized_scope: dict
    scope_hash: str


@dataclasses.dataclass(frozen=True)
class GovernanceRowSpec:
    governance_type: str
    normalized_scope: dict
    governance_scope_hash: str
    selected_corpus_item_id: str
    effective_state: str
    source_final_event_pk: int
    source_final_event_id: str
    source_sequence_number: int
    attestation_event_ids: tuple[str, ...]
    source_policy_id: str
    source_policy_version: str
    warning_codes: tuple[str, ...]
    projection_metadata: dict
    effective_from: object
    revoked_at: object | None

    def logical_document(self):
        return {
            "governance_type": self.governance_type,
            "normalized_scope": self.normalized_scope,
            "governance_scope_hash": self.governance_scope_hash,
            "selected_corpus_item_id": self.selected_corpus_item_id,
            "effective_state": self.effective_state,
            "source_final_event_id": self.source_final_event_id,
            "source_sequence_number": self.source_sequence_number,
            "attestation_event_ids": list(self.attestation_event_ids),
            "source_policy_id": self.source_policy_id,
            "source_policy_version": self.source_policy_version,
            "warning_codes": list(self.warning_codes),
            "projection_metadata": self.projection_metadata,
            "effective_from": self.effective_from.isoformat(),
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


@dataclasses.dataclass(frozen=True)
class GovernanceProjectionBuild:
    chain_head_hash: str
    terminal_sequence: int
    event_count: int
    evaluation_timestamp: object
    rows: tuple[GovernanceRowSpec, ...]
    projected_decision_count: int
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
            "projected_decision_count": self.projected_decision_count,
            "projection_row_count": len(self.rows),
            "warning_count": self.warning_count,
            "projection_output_hash": self.output_hash,
            "evaluation_timestamp": self.evaluation_timestamp.isoformat(),
        }


def _fail_validation(code):
    raise GovernanceProjectionValidationError(code)


def _exact_fields(value, fields, code):
    if not isinstance(value, dict) or set(value) != fields:
        _fail_validation(code)


def _verify_snapshot(event, payload):
    snapshot = payload.get("authz_snapshot")
    if (not isinstance(snapshot, dict)
            or snapshot.get("snapshot_schema") != AUTHZ_SNAPSHOT_SCHEMA
            or set(snapshot) != AUTHZ_SNAPSHOT_FIELDS):
        _fail_validation("GOVERNANCE_AUTHORIZATION_SNAPSHOT_SCHEMA_INVALID")
    if _snapshot_contract_error(event, snapshot):
        _fail_validation("GOVERNANCE_AUTHORIZATION_SNAPSHOT_INVALID")
    if (snapshot.get("actor_id") != event.actor_id
            or snapshot.get("role_used") != event.role_used
            or snapshot.get("action") != event.action
            or snapshot.get("subject_type") != event.subject_type
            or snapshot.get("subject_id") != event.subject_id):
        _fail_validation("GOVERNANCE_AUTHORIZATION_SNAPSHOT_ENVELOPE_MISMATCH")
    version = snapshot.get("policy_version")
    policy = authz.policy_for_version(version)
    if policy is None:
        raise GovernanceProjectionVerificationError(
            "UNSUPPORTED_GOVERNANCE_POLICY_VERSION")
    expected_roles = list(authz.authorizing_roles_for_version(
        version, event.action, snapshot["active_roles"]))
    expected_role = authz.select_role_used_for_version(
        version, event.action, snapshot["active_roles"])
    if (snapshot["authorizing_roles"] != expected_roles
            or event.role_used != expected_role
            or event.role_used not in policy.get(event.action, ())):
        _fail_validation("GOVERNANCE_AUTHORIZATION_POLICY_BINDING_INVALID")
    if (payload.get("policy_id") != snapshot.get("policy_id")
            or payload.get("policy_version") != version):
        _fail_validation("GOVERNANCE_POLICY_PAYLOAD_MISMATCH")
    return snapshot


def _verified_supported_event(event):
    if event.schema_version != DECISION_EVENT_SCHEMA:
        raise GovernanceProjectionVerificationError(
            "UNSUPPORTED_DECISION_EVENT_SCHEMA")
    ok, _problems = verify_event(event)
    if not ok:
        raise GovernanceProjectionVerificationError(
            "GOVERNANCE_EVENT_SIGNATURE_INVALID")


def _parse_final(event, evaluation_at):
    _verified_supported_event(event)
    payload = event.payload
    _exact_fields(payload, FINAL_PAYLOAD_FIELDS, "GOVERNANCE_FINAL_PAYLOAD_SCHEMA_INVALID")
    if payload.get("governance_decision_schema") != GOVERNANCE_DECISION_SCHEMA:
        raise GovernanceProjectionVerificationError(
            "UNSUPPORTED_GOVERNANCE_DECISION_SCHEMA")
    governance_type = payload.get("governance_type")
    if (governance_type not in GOVERNANCE_TYPES
            or event.action != FINALIZE_ACTION.get(governance_type)):
        _fail_validation("GOVERNANCE_FINAL_ACTION_TYPE_MISMATCH")
    if (payload.get("decision_version") != GOVERNANCE_DECISION_VERSION
            or payload.get("authority_effect") != AUTHORITY_EFFECT_NONE):
        _fail_validation("GOVERNANCE_FINAL_VERSION_OR_AUTHORITY_INVALID")
    try:
        normalized_scope = normalize_governance_scope(
            governance_type, payload.get("normalized_scope"))
        scope_hash = governance_scope_hash(governance_type, normalized_scope)
        item = resolve_governance_candidate(
            payload.get("selected_corpus_item_id"), governance_type)
    except GovernanceValidationError as exc:
        raise GovernanceProjectionValidationError(
            "GOVERNANCE_FINAL_SUBJECT_OR_SCOPE_INVALID") from exc
    if (payload.get("normalized_scope") != normalized_scope
            or payload.get("governance_scope_hash") != scope_hash
            or event.subject_type != GOVERNANCE_SUBJECT_TYPE
            or event.subject_id != scope_hash):
        _fail_validation("GOVERNANCE_FINAL_SCOPE_BINDING_INVALID")
    _verify_snapshot(event, payload)

    expected_supersedes = (
        event.supersedes_event.event_id if event.supersedes_event_id else None)
    if payload.get("supersedes_final_event_id") != expected_supersedes:
        _fail_validation("GOVERNANCE_FINAL_SUPERSESSION_BINDING_INVALID")
    if event.supersedes_event_id:
        prior = event.supersedes_event
        if (prior.action != event.action or prior.subject_type != event.subject_type
                or prior.subject_id != event.subject_id
                or prior.sequence_number >= event.sequence_number):
            _fail_validation("GOVERNANCE_FINAL_SUPERSESSION_INVALID")

    event_ids = payload.get("attestation_event_ids")
    hashes = payload.get("attestation_content_hashes")
    if (not isinstance(event_ids, list) or len(event_ids) != 2
            or len(set(event_ids)) != 2 or not isinstance(hashes, list)
            or len(hashes) != 2):
        _fail_validation("GOVERNANCE_FINAL_ATTESTATION_BINDING_INVALID")
    attestations = {
        row.event_id: row for row in DecisionEvent.objects.filter(event_id__in=event_ids)}
    if set(attestations) != set(event_ids):
        _fail_validation("GOVERNANCE_FINAL_ATTESTATION_MISSING")
    for entry, event_id in zip(hashes, event_ids):
        _exact_fields(
            entry, ATTESTATION_HASH_FIELDS,
            "GOVERNANCE_FINAL_ATTESTATION_HASH_SCHEMA_INVALID")
        if (entry.get("event_id") != event_id
                or entry.get("content_hash") != attestations[event_id].content_hash):
            _fail_validation("GOVERNANCE_FINAL_ATTESTATION_HASH_MISMATCH")
    ordered = [attestations[event_id] for event_id in event_ids]
    expected_order = list(REQUIRED_ATTESTATION_CATEGORIES[governance_type])
    if [row.payload.get("attestation_category") for row in ordered] != expected_order:
        _fail_validation("GOVERNANCE_FINAL_ATTESTATION_ORDER_INVALID")
    try:
        _result, sources = validate_governance_attestations(
            item, governance_type, normalized_scope, ordered[0], ordered[1],
            at=event.created_at)
    except GovernanceValidationError as exc:
        raise GovernanceProjectionValidationError(
            "GOVERNANCE_FINAL_ATTESTATIONS_INVALID_AT_FINALIZATION") from exc
    if payload.get("decision_scope_hash") != ordered[0].payload.get(
            "decision_scope_hash"):
        _fail_validation("GOVERNANCE_FINAL_DECISION_BINDING_MISMATCH")
    if payload.get("evidence_sources") != sources:
        _fail_validation("GOVERNANCE_FINAL_EVIDENCE_BINDING_MISMATCH")
    try:
        _validate_integrity_summary(
            payload.get("evidence_integrity_summary"), sources)
    except GovernanceValidationError as exc:
        raise GovernanceProjectionValidationError(
            "GOVERNANCE_FINAL_INTEGRITY_SUMMARY_INVALID") from exc
    try:
        references, current_sources = _evidence_sources(
            item, [row["evidence_reference_id"] for row in sources])
        if current_sources != sources:
            _fail_validation("GOVERNANCE_FINAL_PERSISTED_EVIDENCE_MISMATCH")
        _evidence_tokens(sources)
    except GovernanceValidationError as exc:
        raise GovernanceProjectionValidationError(
            "GOVERNANCE_FINAL_EVIDENCE_SCHEMA_INVALID") from exc

    evidence_status = "VERIFIED"
    evidence_reasons = ()
    try:
        verify_governance_evidence(item, references, evaluated_at=evaluation_at)
    except GovernanceEligibilityError as exc:
        evidence_status = "EVIDENCE_INTEGRITY_BLOCKED"
        evidence_reasons = (str(exc),)

    review_required = False
    review_reasons = ()
    try:
        validate_governance_attestations(
            item, governance_type, normalized_scope, ordered[0], ordered[1],
            at=evaluation_at)
    except GovernanceValidationError as exc:
        review_required = True
        review_reasons = ("ATTESTATION_REVIEW_REQUIRED", str(exc))
    return ParsedFinal(
        event=event, item=item, governance_type=governance_type,
        normalized_scope=normalized_scope, scope_hash=scope_hash,
        attestation_event_ids=tuple(event_ids), policy_id=payload["policy_id"],
        policy_version=payload["policy_version"], evidence_status=evidence_status,
        evidence_reasons=evidence_reasons, review_required=review_required,
        review_reasons=review_reasons)


def _parse_revocation(event, finals_by_event_id):
    _verified_supported_event(event)
    payload = event.payload
    _exact_fields(
        payload, REVOCATION_PAYLOAD_FIELDS,
        "GOVERNANCE_REVOCATION_PAYLOAD_SCHEMA_INVALID")
    if payload.get("governance_revocation_schema") != GOVERNANCE_REVOCATION_SCHEMA:
        raise GovernanceProjectionVerificationError(
            "UNSUPPORTED_GOVERNANCE_REVOCATION_SCHEMA")
    governance_type = payload.get("governance_type")
    if (governance_type not in GOVERNANCE_TYPES
            or event.action != REVOKE_ACTION.get(governance_type)):
        _fail_validation("GOVERNANCE_REVOCATION_ACTION_TYPE_MISMATCH")
    if (payload.get("decision_version") != GOVERNANCE_DECISION_VERSION
            or payload.get("authority_effect") != AUTHORITY_EFFECT_NONE
            or event.supersedes_event_id is not None):
        _fail_validation("GOVERNANCE_REVOCATION_VERSION_OR_AUTHORITY_INVALID")
    try:
        normalized_scope = normalize_governance_scope(
            governance_type, payload.get("normalized_scope"))
        scope_hash = governance_scope_hash(governance_type, normalized_scope)
    except GovernanceValidationError as exc:
        raise GovernanceProjectionValidationError(
            "GOVERNANCE_REVOCATION_SCOPE_INVALID") from exc
    if (payload.get("normalized_scope") != normalized_scope
            or payload.get("governance_scope_hash") != scope_hash
            or event.subject_type != GOVERNANCE_SUBJECT_TYPE
            or event.subject_id != scope_hash):
        _fail_validation("GOVERNANCE_REVOCATION_SCOPE_BINDING_INVALID")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        _fail_validation("GOVERNANCE_REVOCATION_REASON_INVALID")
    _verify_snapshot(event, payload)
    target = finals_by_event_id.get(payload.get("revoked_final_event_id"))
    if target is None:
        _fail_validation("GOVERNANCE_REVOCATION_TARGET_MISSING")
    if (payload.get("revoked_final_content_hash") != target.event.content_hash
            or target.governance_type != governance_type
            or target.scope_hash != scope_hash
            or payload.get("selected_corpus_item_id") != str(target.item.pk)
            or target.event.sequence_number >= event.sequence_number):
        _fail_validation("GOVERNANCE_REVOCATION_TARGET_BINDING_INVALID")
    return ParsedRevocation(
        event=event, target_event_id=target.event.event_id,
        governance_type=governance_type, normalized_scope=normalized_scope,
        scope_hash=scope_hash)


def _reduce_rows(finals, revocations):
    finals_by_pk = {row.event.pk: row for row in finals}
    final_by_event_id = {row.event.event_id: row for row in finals}
    superseded_by = {}
    for row in finals:
        if row.event.supersedes_event_id is None:
            continue
        prior = finals_by_pk.get(row.event.supersedes_event_id)
        if (prior is None or prior.key != row.key
                or prior.event.sequence_number >= row.event.sequence_number):
            _fail_validation("GOVERNANCE_REPLACEMENT_TARGET_INVALID")
        if prior.event.pk in superseded_by:
            _fail_validation("GOVERNANCE_REPLACEMENT_BRANCH_CONFLICT")
        superseded_by[prior.event.pk] = row.event

    revoked_by = {}
    for revocation in revocations:
        target = final_by_event_id[revocation.target_event_id]
        if target.event.pk in superseded_by:
            _fail_validation("GOVERNANCE_REVOCATION_TARGET_ALREADY_SUPERSEDED")
        if target.event.pk in revoked_by:
            _fail_validation("GOVERNANCE_DUPLICATE_REVOCATION")
        revoked_by[target.event.pk] = revocation.event

    grouped = {}
    for row in finals:
        grouped.setdefault(row.key, []).append(row)
    output = []
    for key in sorted(grouped):
        history = sorted(grouped[key], key=lambda value: value.event.sequence_number)
        current = [row for row in history
                   if row.event.pk not in superseded_by
                   and row.event.pk not in revoked_by]
        conflict = len(current) > 1
        for row in history:
            warnings = []
            metadata = {
                "decision_scope_hash": row.event.payload["decision_scope_hash"],
                "evidence_integrity_status": row.evidence_status,
                "evidence_integrity_reason_codes": list(row.evidence_reasons),
                "attestation_review_reasons": list(row.review_reasons),
                "superseded_by_event_id": None,
                "revocation_event_id": None,
            }
            revoked_at = None
            if row.event.pk in superseded_by:
                state = GovernanceDecisionProjection.EffectiveState.SUPERSEDED
                metadata["superseded_by_event_id"] = superseded_by[
                    row.event.pk].event_id
            elif row.event.pk in revoked_by:
                state = GovernanceDecisionProjection.EffectiveState.REVOKED
                revocation = revoked_by[row.event.pk]
                metadata["revocation_event_id"] = revocation.event_id
                revoked_at = revocation.created_at
            elif row.evidence_status == "EVIDENCE_INTEGRITY_BLOCKED":
                state = GovernanceDecisionProjection.EffectiveState.EVIDENCE_INTEGRITY_BLOCKED
                warnings.append("EVIDENCE_INTEGRITY_BLOCKED")
            elif conflict:
                state = GovernanceDecisionProjection.EffectiveState.REVIEW_REQUIRED
                warnings.append("ACTIVE_GOVERNANCE_CONFLICT")
            elif row.review_required:
                state = GovernanceDecisionProjection.EffectiveState.REVIEW_REQUIRED
                warnings.append("ATTESTATION_REVIEW_REQUIRED")
            else:
                state = GovernanceDecisionProjection.EffectiveState.ACTIVE
            output.append(GovernanceRowSpec(
                governance_type=row.governance_type,
                normalized_scope=row.normalized_scope,
                governance_scope_hash=row.scope_hash,
                selected_corpus_item_id=str(row.item.pk), effective_state=state,
                source_final_event_pk=row.event.pk,
                source_final_event_id=row.event.event_id,
                source_sequence_number=row.event.sequence_number,
                attestation_event_ids=row.attestation_event_ids,
                source_policy_id=row.policy_id,
                source_policy_version=row.policy_version,
                warning_codes=tuple(warnings), projection_metadata=metadata,
                effective_from=row.event.created_at, revoked_at=revoked_at))
    active_keys = [
        (row.governance_type, row.governance_scope_hash) for row in output
        if row.effective_state == GovernanceDecisionProjection.EffectiveState.ACTIVE]
    if len(active_keys) != len(set(active_keys)):
        _fail_validation("MULTIPLE_ACTIVE_GOVERNANCE_SELECTIONS")
    return output


def _output_hash(rows):
    return canonical.content_hash({
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "projection_rows": [row.logical_document() for row in rows],
    })


def _head_checkpoint():
    try:
        head = DecisionChainHead.objects.get(pk=1)
    except DecisionChainHead.DoesNotExist as exc:
        raise GovernanceProjectionVerificationError(
            "DECISION_CHAIN_HEAD_MISSING") from exc
    return head.terminal_event_hash or "", head.terminal_sequence_number


def build_governance_projection(*, evaluation_at=None):
    chain = verify_chain()
    if not chain.ok:
        raise GovernanceProjectionVerificationError("DECISION_CHAIN_INVALID")
    head_hash, terminal_sequence = _head_checkpoint()
    events = list(DecisionEvent.objects.select_related(
        "actor", "supersedes_event").order_by("sequence_number"))
    evaluation_at = evaluation_at or (
        events[-1].created_at if events else GENESIS_EVALUATION_TIMESTAMP)
    if not timezone.is_aware(evaluation_at):
        raise GovernanceProjectionValidationError(
            "EVALUATION_TIMESTAMP_MUST_BE_AWARE")
    finals = [_parse_final(event, evaluation_at) for event in events
              if event.action in FINALIZE_ACTIONS]
    by_event_id = {row.event.event_id: row for row in finals}
    revocations = [_parse_revocation(event, by_event_id) for event in events
                   if event.action in REVOKE_ACTIONS]
    rows = tuple(sorted(
        _reduce_rows(finals, revocations),
        key=lambda row: (
            row.governance_type, row.governance_scope_hash,
            row.source_sequence_number, row.source_final_event_id)))
    return GovernanceProjectionBuild(
        chain_head_hash=head_hash, terminal_sequence=terminal_sequence,
        event_count=len(events), evaluation_timestamp=evaluation_at, rows=rows,
        projected_decision_count=len(finals),
        warning_count=sum(len(row.warning_codes) for row in rows),
        output_hash=_output_hash(rows))


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
        "projected_decision_count": build.projected_decision_count,
        "projection_row_count": len(build.rows),
        "warning_count": build.warning_count,
    }


def _persist_rows(generation, build):
    rows = [GovernanceDecisionProjection(
        projection_generation=generation,
        governance_type=spec.governance_type,
        normalized_scope=spec.normalized_scope,
        governance_scope_hash=spec.governance_scope_hash,
        selected_corpus_item_id=spec.selected_corpus_item_id,
        effective_state=spec.effective_state,
        source_final_decision_event_id=spec.source_final_event_pk,
        source_sequence_number=spec.source_sequence_number,
        attestation_event_ids=list(spec.attestation_event_ids),
        source_policy_id=spec.source_policy_id,
        source_policy_version=spec.source_policy_version,
        warning_codes=list(spec.warning_codes),
        projection_metadata=spec.projection_metadata,
        effective_from=spec.effective_from, revoked_at=spec.revoked_at,
    ) for spec in build.rows]
    GovernanceDecisionProjection.objects.bulk_create(rows)
    if generation.decision_projections.count() != len(build.rows):
        raise GovernanceProjectionValidationError(
            "GOVERNANCE_PROJECTION_ROW_COUNT_MISMATCH")


def _mark_failed(generation, error):
    safe_code = error.code if isinstance(error, GovernanceProjectionError) \
        else "INTERNAL_GOVERNANCE_PROJECTOR_ERROR"
    GovernanceProjectionGeneration.objects.filter(pk=generation.pk).update(
        status=GovernanceProjectionGeneration.Status.FAILED,
        completed_at=timezone.now(), failure_count=1, failure_summary=safe_code)


def _published_matches(build):
    state = GovernanceProjectionPublicationState.objects.select_related(
        "current_generation").filter(pk=1).first()
    if state is None:
        return None
    generation = state.current_generation
    if (generation.status == GovernanceProjectionGeneration.Status.PUBLISHED
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
        raise GovernanceProjectionPublicationError(
            "CHAIN_CHANGED_BEFORE_GOVERNANCE_PUBLICATION")
    if expected_chain_head is not None and current_hash != expected_chain_head:
        raise GovernanceProjectionPublicationError("EXPECTED_CHAIN_HEAD_MISMATCH")
    publication = GovernanceProjectionPublicationState.objects.select_for_update().filter(
        pk=1).first()
    now = timezone.now()
    if publication is not None:
        prior = publication.current_generation
        if prior.pk != generation.pk:
            GovernanceProjectionGeneration.objects.filter(
                pk=prior.pk,
                status=GovernanceProjectionGeneration.Status.PUBLISHED).update(
                    status=GovernanceProjectionGeneration.Status.SUPERSEDED)
        publication.current_generation = generation
        publication.published_chain_head_hash = build.chain_head_hash
        publication.published_terminal_sequence = build.terminal_sequence
        publication.projector_identifier = PROJECTOR_IDENTIFIER
        publication.projector_version = PROJECTOR_VERSION
        publication.projection_schema_version = PROJECTION_SCHEMA_VERSION
        publication.published_at = now
        publication.save(
            _governance_projection_write_token=_GOVERNANCE_PROJECTION_WRITE_TOKEN)
    else:
        try:
            publication = GovernanceProjectionPublicationState(
                id=1, current_generation=generation,
                published_chain_head_hash=build.chain_head_hash,
                published_terminal_sequence=build.terminal_sequence,
                projector_identifier=PROJECTOR_IDENTIFIER,
                projector_version=PROJECTOR_VERSION,
                projection_schema_version=PROJECTION_SCHEMA_VERSION,
                published_at=now)
            publication.save(
                _governance_projection_write_token=(
                    _GOVERNANCE_PROJECTION_WRITE_TOKEN),
                force_insert=True)
        except IntegrityError as exc:
            raise GovernanceProjectionPublicationError(
                "GOVERNANCE_PUBLICATION_SINGLETON_RACE") from exc
    generation.status = GovernanceProjectionGeneration.Status.PUBLISHED
    generation.published_at = now
    generation.completed_at = now
    generation.save(
        _governance_projection_write_token=_GOVERNANCE_PROJECTION_WRITE_TOKEN,
        update_fields=("status", "published_at", "completed_at"))


def _expected_hash(value):
    if value is None:
        return None
    if value == "GENESIS":
        return ""
    if (not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)):
        raise GovernanceProjectionValidationError(
            "EXPECTED_CHAIN_HEAD_INVALID")
    return value


def rebuild_governance_projections(
        *, apply=False, evaluation_at=None, expected_chain_head=None):
    expected_chain_head = _expected_hash(expected_chain_head)
    generation = None
    if not apply:
        build = build_governance_projection(evaluation_at=evaluation_at)
        if (expected_chain_head is not None
                and build.chain_head_hash != expected_chain_head):
            raise GovernanceProjectionVerificationError(
                "EXPECTED_CHAIN_HEAD_MISMATCH")
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
    generation = GovernanceProjectionGeneration.objects.create(
        projector_identifier=PROJECTOR_IDENTIFIER,
        projector_version=PROJECTOR_VERSION,
        projection_schema_version=PROJECTION_SCHEMA_VERSION,
        source_chain_head_hash=checkpoint_hash,
        source_terminal_sequence=checkpoint_sequence,
        evaluation_timestamp=seed_evaluation,
        status=GovernanceProjectionGeneration.Status.BUILDING)
    try:
        build = build_governance_projection(evaluation_at=evaluation_at)
        if (build.chain_head_hash != checkpoint_hash
                or build.terminal_sequence != checkpoint_sequence):
            raise GovernanceProjectionVerificationError(
                "CHAIN_CHANGED_DURING_GOVERNANCE_BUILD")
        if (expected_chain_head is not None
                and build.chain_head_hash != expected_chain_head):
            raise GovernanceProjectionVerificationError(
                "EXPECTED_CHAIN_HEAD_MISMATCH")
        existing = _published_matches(build)
        if existing is not None:
            generation.delete()
            report = build.as_report()
            report.update({
                "mode": "apply", "published": False, "idempotent": True,
                "generation_id": str(existing.pk), "rows_created": 0,
            })
            return report
        GovernanceProjectionGeneration.objects.filter(pk=generation.pk).update(
            **_generation_values(build))
        generation.refresh_from_db()
        _persist_rows(generation, build)
        generation.status = GovernanceProjectionGeneration.Status.VALIDATED
        generation.save(
            _governance_projection_write_token=_GOVERNANCE_PROJECTION_WRITE_TOKEN,
            update_fields=("status",))
        _publish(generation, build, expected_chain_head)
        report = build.as_report()
        report.update({
            "mode": "apply", "published": True, "idempotent": False,
            "generation_id": str(generation.pk), "rows_created": len(build.rows),
        })
        return report
    except Exception as exc:
        if generation.pk and GovernanceProjectionGeneration.objects.filter(
                pk=generation.pk).exists():
            _mark_failed(generation, exc)
        raise


__all__ = [
    "PROJECTOR_IDENTIFIER", "PROJECTOR_VERSION", "PROJECTION_SCHEMA_VERSION",
    "GENESIS_EVALUATION_TIMESTAMP", "GovernanceProjectionError",
    "GovernanceProjectionVerificationError", "GovernanceProjectionValidationError",
    "GovernanceProjectionPublicationError", "GovernanceRowSpec",
    "GovernanceProjectionBuild", "build_governance_projection",
    "rebuild_governance_projections",
]
