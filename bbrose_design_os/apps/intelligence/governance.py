"""Evidence-gated, dual-control brand and palette governance (DIP-1B-4B).

This module is the only write boundary for governance attestations, final selections,
replacements, and revocations.  Governance identifies a selected candidate for a strict
scope.  It never creates or implies an operational permission.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
import uuid

from django.db import transaction
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts.attestation import (
    AttestationDenied,
    AttestationError,
    CATEGORY_COLOR_AND_BRAND,
    CATEGORY_RIGHTS_AND_OWNERSHIP,
    CATEGORY_RIGHTS_AND_USE,
    CATEGORY_TECHNICAL_AND_BRAND,
    binding_hash,
    record_attestation,
    validate_dual_control,
)
from apps.accounts.authorization import (
    _best_effort_record,
    authorize_actor,
    build_authorization_snapshot,
    record_authorization,
)
from apps.accounts.decision_chain import append_decision, verify_event
from apps.accounts.models import DecisionChainHead, DecisionEvent
from apps.accounts.security import canonical

from .evidence_integrity import VERIFIED, evaluate_evidence_integrity
from .evidence_readiness import governance_category_dimension_ready
from .identity import IDENTITY_ALIAS_PROVENANCE
from .models import (
    BrandCandidateProfile,
    CorpusItem,
    EvidenceReference,
    ProvenanceRecord,
)

GOVERNANCE_SCOPE_SCHEMA = "intelligence_governance_scope/1.0"
GOVERNANCE_ATTESTATION_SCHEMA = "intelligence_governance_attestation/1.0"
GOVERNANCE_DECISION_SCHEMA = "intelligence_governance_decision/1.0"
GOVERNANCE_REVOCATION_SCHEMA = "intelligence_governance_revocation/1.0"
GOVERNANCE_DECISION_VERSION = "intelligence_governance_decision/1.0"

CANONICAL_BRAND_ASSET = "CANONICAL_BRAND_ASSET"
PRIMARY_BRAND_PALETTE = "PRIMARY_BRAND_PALETTE"
GOVERNANCE_TYPES = frozenset({CANONICAL_BRAND_ASSET, PRIMARY_BRAND_PALETTE})

GLOBAL_WORDMARK = "GLOBAL_WORDMARK"
GLOBAL_PRIMARY_LOGO = "GLOBAL_PRIMARY_LOGO"
GLOBAL_PRIMARY_PALETTE = "GLOBAL_PRIMARY_PALETTE"
PRODUCT_FAMILY = "PRODUCT_FAMILY"
MARKET = "MARKET"
MEDIA_APPLICATION = "MEDIA_APPLICATION"

CANONICAL_SCOPE_TYPES = frozenset({
    GLOBAL_WORDMARK, GLOBAL_PRIMARY_LOGO, PRODUCT_FAMILY, MARKET, MEDIA_APPLICATION,
})
PALETTE_SCOPE_TYPES = frozenset({
    GLOBAL_PRIMARY_PALETTE, PRODUCT_FAMILY, MARKET, MEDIA_APPLICATION,
})
SCOPE_IDENTIFIER_FIELDS = {
    PRODUCT_FAMILY: "product_family_id",
    MARKET: "market_id",
    MEDIA_APPLICATION: "media_application_id",
}
GLOBAL_SCOPE_TYPES = frozenset({
    GLOBAL_WORDMARK, GLOBAL_PRIMARY_LOGO, GLOBAL_PRIMARY_PALETTE,
})

REQUIRED_ATTESTATION_CATEGORIES = {
    CANONICAL_BRAND_ASSET: (
        CATEGORY_TECHNICAL_AND_BRAND, CATEGORY_RIGHTS_AND_OWNERSHIP),
    PRIMARY_BRAND_PALETTE: (
        CATEGORY_COLOR_AND_BRAND, CATEGORY_RIGHTS_AND_USE),
}
FINALIZE_ACTION = {
    CANONICAL_BRAND_ASSET: authz.FINALIZE_CANONICAL_BRAND_ASSET,
    PRIMARY_BRAND_PALETTE: authz.FINALIZE_PRIMARY_BRAND_PALETTE,
}
REVOKE_ACTION = {
    CANONICAL_BRAND_ASSET: authz.REVOKE_CANONICAL_BRAND_ASSET,
    PRIMARY_BRAND_PALETTE: authz.REVOKE_PRIMARY_BRAND_PALETTE,
}
FINALIZE_ACTIONS = frozenset(FINALIZE_ACTION.values())
REVOKE_ACTIONS = frozenset(REVOKE_ACTION.values())
SUPPORTED_GOVERNANCE_ACTIONS = FINALIZE_ACTIONS | REVOKE_ACTIONS

GOVERNANCE_SUBJECT_TYPE = "GovernanceScope"
AUTHORITY_EFFECT_NONE = "NONE"
_IDENTIFIER_RE = re.compile(r"\A[A-Z0-9][A-Z0-9_-]{0,63}\Z")
_EVIDENCE_SOURCE_FIELDS = frozenset({
    "evidence_reference_id", "evidence_hash", "source_artifact_id", "source_sha256",
})
_FINAL_PAYLOAD_FIELDS = frozenset({
    "governance_decision_schema", "governance_type", "selected_corpus_item_id",
    "normalized_scope", "governance_scope_hash", "decision_version",
    "decision_scope_hash", "attestation_event_ids", "attestation_content_hashes",
    "evidence_sources", "evidence_integrity_summary", "supersedes_final_event_id",
    "authority_effect", "policy_id", "policy_version", "authz_snapshot",
})
_REVOCATION_PAYLOAD_FIELDS = frozenset({
    "governance_revocation_schema", "governance_type", "selected_corpus_item_id",
    "normalized_scope", "governance_scope_hash", "decision_version",
    "revoked_final_event_id", "revoked_final_content_hash", "reason",
    "authority_effect", "policy_id", "policy_version", "authz_snapshot",
})
_ATTESTATION_EXTRA_FIELDS = frozenset({
    "governance_attestation_schema", "selected_corpus_item_id", "evidence_sources",
    "evidence_integrity_summary", "authority_effect",
})
_INTEGRITY_SUMMARY_FIELDS = frozenset({
    "status", "classification", "reason_codes", "affected_source_artifact_ids",
    "expected_hashes", "observed_hashes", "verified_source_version_ids",
    "unresolved_source_version_ids", "evaluation_timestamp", "grants_authority",
})


class GovernanceError(RuntimeError):
    """Base fail-closed governance error."""


class GovernanceValidationError(GovernanceError):
    """The requested candidate, scope, evidence, or signed payload is invalid."""


class GovernanceEligibilityError(GovernanceError):
    """The canonical evidence-integrity resolver did not return fully VERIFIED."""


class GovernanceAuthorizationDenied(GovernanceError):
    """The authenticated actor is not authorized for this governance action."""


class GovernanceConflict(GovernanceError):
    """The request conflicts with current append-only governance history."""


def _canonical_uuid(value, label="UUID") -> uuid.UUID:
    raw = str(value)
    try:
        parsed = uuid.UUID(raw)
    except (TypeError, ValueError, AttributeError) as exc:
        raise GovernanceValidationError(f"{label} is invalid") from exc
    if str(parsed) != raw:
        raise GovernanceValidationError(f"{label} must use canonical UUID form")
    return parsed


def _governance_type(value) -> str:
    if value not in GOVERNANCE_TYPES:
        raise GovernanceValidationError("unknown governance_type")
    return value


def normalize_governance_scope(governance_type: str, raw_scope: dict) -> dict:
    """Return the one canonical representation of a supported governance scope."""
    governance_type = _governance_type(governance_type)
    if not isinstance(raw_scope, dict):
        raise GovernanceValidationError("scope must be an object")
    if "scope_type" not in raw_scope or not isinstance(raw_scope["scope_type"], str):
        raise GovernanceValidationError("scope_type is required; GLOBAL is never inferred")
    scope_type = unicodedata.normalize("NFKC", raw_scope["scope_type"]).strip().upper()
    allowed = (CANONICAL_SCOPE_TYPES if governance_type == CANONICAL_BRAND_ASSET
               else PALETTE_SCOPE_TYPES)
    if scope_type not in allowed:
        raise GovernanceValidationError("scope_type is not allowed for governance_type")
    expected = {"scope_type"}
    identifier_field = SCOPE_IDENTIFIER_FIELDS.get(scope_type)
    if identifier_field:
        expected.add(identifier_field)
    # A normalized document may be fed back through the validator by the projector.
    if "scope_schema" in raw_scope:
        expected.add("scope_schema")
        if raw_scope.get("scope_schema") != GOVERNANCE_SCOPE_SCHEMA:
            raise GovernanceValidationError("unsupported governance scope schema")
    if set(raw_scope) != expected:
        raise GovernanceValidationError(
            f"scope fields are invalid; expected {sorted(expected)}")
    normalized = {
        "scope_schema": GOVERNANCE_SCOPE_SCHEMA,
        "scope_type": scope_type,
    }
    if scope_type in GLOBAL_SCOPE_TYPES:
        return normalized
    identifier = raw_scope.get(identifier_field)
    if not isinstance(identifier, str):
        raise GovernanceValidationError(f"{identifier_field} is required")
    identifier = unicodedata.normalize("NFKC", identifier).strip().upper()
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise GovernanceValidationError(
            f"{identifier_field} must be a bounded canonical identifier")
    normalized[identifier_field] = identifier
    return normalized


def governance_scope_hash(governance_type: str, normalized_scope: dict) -> str:
    normalized = normalize_governance_scope(governance_type, normalized_scope)
    return canonical.content_hash({
        "scope_schema": GOVERNANCE_SCOPE_SCHEMA,
        "governance_type": governance_type,
        "normalized_scope": normalized,
    })


def _is_redirected_identity(item_id: uuid.UUID) -> bool:
    return ProvenanceRecord.objects.filter(
        provenance_type=IDENTITY_ALIAS_PROVENANCE,
        normalized_machine_interpretation__legacy_corpus_item_id=str(item_id),
    ).exists()


def resolve_governance_candidate(corpus_item_id, governance_type: str) -> CorpusItem:
    """Resolve one active canonical item identity, rejecting aliases and kind drift."""
    governance_type = _governance_type(governance_type)
    item_id = _canonical_uuid(corpus_item_id, "corpus_item_id")
    if _is_redirected_identity(item_id):
        raise GovernanceValidationError("redirected or deprecated CorpusItem identity")
    item = CorpusItem.objects.filter(pk=item_id).first()
    if item is None:
        raise GovernanceValidationError("CorpusItem does not exist")
    if item.lifecycle_state != CorpusItem.Lifecycle.ACTIVE:
        raise GovernanceValidationError("retired or quarantined CorpusItem is ineligible")
    profile = BrandCandidateProfile.objects.filter(corpus_item=item).first()
    if profile is None:
        raise GovernanceValidationError("candidate has no brand/palette profile")
    if governance_type == CANONICAL_BRAND_ASSET:
        if (item.item_kind != CorpusItem.Kind.BRAND_ASSET
                or profile.candidate_kind == BrandCandidateProfile.CandidateKind.PALETTE):
            raise GovernanceValidationError("candidate is not a canonical brand asset")
    elif (item.item_kind != CorpusItem.Kind.BRAND_PALETTE
          or profile.candidate_kind != BrandCandidateProfile.CandidateKind.PALETTE):
        raise GovernanceValidationError("candidate is not a primary palette candidate")
    return item


def _evidence_sources(item: CorpusItem, evidence_reference_ids) -> tuple[list, list[dict]]:
    if (not isinstance(evidence_reference_ids, (list, tuple))
            or not evidence_reference_ids or len(evidence_reference_ids) > 128):
        raise GovernanceValidationError("one to 128 evidence_reference_ids are required")
    ids = [_canonical_uuid(value, "evidence_reference_id")
           for value in evidence_reference_ids]
    if len(ids) != len(set(ids)):
        raise GovernanceValidationError("evidence_reference_ids must be unique")
    ids = sorted(ids, key=str)
    references = list(EvidenceReference.objects.select_related("source_artifact").filter(
        pk__in=ids, corpus_item=item, is_test_only=False))
    by_id = {row.pk: row for row in references}
    if set(by_id) != set(ids):
        raise GovernanceValidationError(
            "evidence references must belong to the selected item and be non-test-only")
    ordered = [by_id[value] for value in ids]
    sources = [{
        "evidence_reference_id": str(row.pk),
        "evidence_hash": row.evidence_hash,
        "source_artifact_id": str(row.source_artifact_id),
        "source_sha256": row.source_artifact.sha256,
    } for row in ordered]
    return ordered, sources


def _evidence_tokens(sources: list[dict]) -> tuple[str, ...]:
    tokens = []
    for source in sources:
        if not isinstance(source, dict) or set(source) != _EVIDENCE_SOURCE_FIELDS:
            raise GovernanceValidationError("evidence source binding schema is invalid")
        tokens.append(canonical.canonical_bytes(source).decode("utf-8"))
    if len(tokens) != len(set(tokens)):
        raise GovernanceValidationError("evidence source bindings must be unique")
    return tuple(sorted(tokens))


def _integrity_summary(result) -> dict:
    return {
        "status": result.status,
        "classification": result.classification,
        "reason_codes": list(result.reason_codes),
        "affected_source_artifact_ids": list(result.affected_source_artifact_ids),
        "expected_hashes": list(result.expected_hashes),
        "observed_hashes": list(result.observed_hashes),
        "verified_source_version_ids": [
            row.version_id for row in result.verified_source_versions],
        "unresolved_source_version_ids": [
            row.version_id for row in result.unresolved_source_versions],
        "evaluation_timestamp": result.evaluation_timestamp,
        "grants_authority": False,
    }


def _validate_integrity_summary(summary, sources):
    if not isinstance(summary, dict) or set(summary) != _INTEGRITY_SUMMARY_FIELDS:
        raise GovernanceValidationError("evidence-integrity summary schema is invalid")
    if (summary.get("status") != VERIFIED
            or summary.get("classification") != VERIFIED
            or summary.get("grants_authority") is not False
            or summary.get("reason_codes") != []
            or summary.get("affected_source_artifact_ids") != []
            or summary.get("unresolved_source_version_ids") != []
            or not isinstance(summary.get("evaluation_timestamp"), str)
            or not isinstance(summary.get("verified_source_version_ids"), list)
            or not summary.get("verified_source_version_ids")):
        raise GovernanceValidationError(
            "signed governance evidence-integrity summary was not fully VERIFIED")
    source_hashes = {row["source_sha256"] for row in sources}
    expected_hashes = summary.get("expected_hashes")
    observed_hashes = summary.get("observed_hashes")
    if (not isinstance(expected_hashes, list)
            or expected_hashes != sorted(set(expected_hashes))
            or not isinstance(observed_hashes, list)
            or observed_hashes != sorted(set(observed_hashes))
            or not source_hashes.issubset(expected_hashes)
            or not source_hashes.issubset(observed_hashes)):
        raise GovernanceValidationError(
            "evidence-integrity summary does not bind selected source hashes")
    try:
        parsed = dt.datetime.fromisoformat(
            summary["evaluation_timestamp"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise GovernanceValidationError(
            "evidence-integrity evaluation timestamp is invalid") from exc
    if not timezone.is_aware(parsed):
        raise GovernanceValidationError(
            "evidence-integrity evaluation timestamp must be aware")
    return summary


def verify_governance_evidence(item: CorpusItem, references, *, evaluated_at=None):
    """Run the canonical resolver and require complete coverage of selected sources."""
    result = evaluate_evidence_integrity(
        item, references, evaluated_at=evaluated_at)
    selected_ids = {str(row.source_artifact_id) for row in references}
    verified_ids = {
        artifact_id
        for version in result.verified_source_versions
        for artifact_id in version.source_artifact_ids
    }
    if (result.status != VERIFIED or result.unresolved_source_versions
            or not selected_ids.issubset(verified_ids)):
        reasons = ",".join(result.reason_codes) or "UNRESOLVED_MIXED_EVIDENCE"
        raise GovernanceEligibilityError(
            f"EVIDENCE_INTEGRITY_NOT_VERIFIED:{result.status}:{reasons}")
    return result


def _authorize_or_deny(user, action, subject, endpoint):
    result = authorize_actor(user, action, subject=subject)
    if not result.allowed:
        _best_effort_record(result, None, endpoint, "SERVICE")
        raise GovernanceAuthorizationDenied(f"{action}:{result.reason_code}")
    return result


def _require_evidence_dimensions(item, categories):
    if any(governance_category_dimension_ready(item, category) is False
           for category in categories):
        raise GovernanceEligibilityError(
            "EVIDENCE_DIMENSION_NOT_READY: technical evidence does not establish "
            "brand identity, palette authority, ownership, or rights")


def record_governance_attestation(
        *, user, corpus_item_id, governance_type, raw_scope, attestation_category,
        evidence_reference_ids, review_expiry, valid_from=None) -> DecisionEvent:
    """Append exactly one evidence-gated governance attestation."""
    governance_type = _governance_type(governance_type)
    required = REQUIRED_ATTESTATION_CATEGORIES[governance_type]
    if attestation_category not in required:
        raise GovernanceValidationError(
            "attestation_category is not valid for this governance_type")
    item = resolve_governance_candidate(corpus_item_id, governance_type)
    normalized_scope = normalize_governance_scope(governance_type, raw_scope)
    references, sources = _evidence_sources(item, evidence_reference_ids)
    _require_evidence_dimensions(item, (attestation_category,))
    integrity = verify_governance_evidence(item, references)
    if not isinstance(review_expiry, dt.datetime) or not timezone.is_aware(review_expiry):
        raise GovernanceValidationError("review_expiry must be an aware datetime")
    extras = {
        "governance_attestation_schema": GOVERNANCE_ATTESTATION_SCHEMA,
        "selected_corpus_item_id": str(item.pk),
        "evidence_sources": sources,
        "evidence_integrity_summary": _integrity_summary(integrity),
        "authority_effect": AUTHORITY_EFFECT_NONE,
    }
    try:
        return record_attestation(
            user=user, subject_type="CorpusItem", subject_id=str(item.pk),
            decision_type=governance_type, decision_version=GOVERNANCE_DECISION_VERSION,
            attestation_category=attestation_category,
            normalized_scope=normalized_scope, evidence_refs=_evidence_tokens(sources),
            review_expiry=review_expiry, valid_from=valid_from, payload_extras=extras)
    except AttestationDenied as exc:
        raise GovernanceAuthorizationDenied(str(exc)) from exc
    except AttestationError as exc:
        raise GovernanceValidationError(str(exc)) from exc


def _exact_mapping(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        raise GovernanceValidationError(f"{label} schema is invalid")


def _attestation_evidence(event: DecisionEvent) -> tuple[list[dict], tuple[str, ...]]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    for field in _ATTESTATION_EXTRA_FIELDS:
        if field not in payload:
            raise GovernanceValidationError("governance attestation payload is incomplete")
    if (payload.get("governance_attestation_schema") != GOVERNANCE_ATTESTATION_SCHEMA
            or payload.get("authority_effect") != AUTHORITY_EFFECT_NONE):
        raise GovernanceValidationError("unsupported governance attestation schema")
    sources = payload.get("evidence_sources")
    if not isinstance(sources, list) or not sources:
        raise GovernanceValidationError("governance attestation evidence is missing")
    tokens = _evidence_tokens(sources)
    _validate_integrity_summary(payload.get("evidence_integrity_summary"), sources)
    if sorted(payload.get("evidence_refs") or []) != list(tokens):
        raise GovernanceValidationError("governance attestation evidence binding mismatch")
    expected = binding_hash(
        subject_type=event.subject_type, subject_id=event.subject_id,
        decision_type=payload.get("decision_type"),
        decision_version=payload.get("decision_version"),
        normalized_scope=payload.get("normalized_scope"), evidence_refs=tokens,
        contradiction_present=payload.get("contradiction_present"),
    )
    if expected != payload.get("decision_scope_hash"):
        raise GovernanceValidationError("attestation decision binding does not recompute")
    return sources, tokens


def validate_governance_attestations(
        item: CorpusItem, governance_type: str, normalized_scope: dict,
        attestation_a: DecisionEvent, attestation_b: DecisionEvent, *, at=None):
    """Apply the existing dual-control validator plus governance-specific bindings."""
    at = at or timezone.now()
    result = validate_dual_control(attestation_a, attestation_b, at=at)
    if not result.valid:
        raise GovernanceValidationError(
            "dual-control attestations are invalid: " + "; ".join(result.reasons))
    expected_categories = set(REQUIRED_ATTESTATION_CATEGORIES[governance_type])
    categories = {
        attestation_a.payload.get("attestation_category"),
        attestation_b.payload.get("attestation_category"),
    }
    if categories != expected_categories:
        raise GovernanceValidationError("wrong attestation category pair")
    for event in (attestation_a, attestation_b):
        if (event.subject_type != "CorpusItem" or event.subject_id != str(item.pk)
                or event.payload.get("selected_corpus_item_id") != str(item.pk)
                or event.payload.get("decision_type") != governance_type
                or event.payload.get("decision_version") != GOVERNANCE_DECISION_VERSION
                or event.payload.get("normalized_scope") != normalized_scope):
            raise GovernanceValidationError(
                "attestation item, type, version, or scope does not match")
        if not verify_event(event)[0]:
            raise GovernanceValidationError("attestation event signature is invalid")
    sources_a, tokens_a = _attestation_evidence(attestation_a)
    sources_b, tokens_b = _attestation_evidence(attestation_b)
    if sources_a != sources_b or tokens_a != tokens_b:
        raise GovernanceValidationError("attestation evidence bindings differ")
    return result, sources_a


def _events_by_id(values) -> tuple[DecisionEvent, DecisionEvent]:
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        raise GovernanceValidationError("exactly two attestation_event_ids are required")
    raw = [str(value) for value in values]
    if len(set(raw)) != 2 or any(not value or len(value) > 64 for value in raw):
        raise GovernanceValidationError("attestation_event_ids are invalid")
    events = {row.event_id: row for row in DecisionEvent.objects.filter(event_id__in=raw)}
    if set(events) != set(raw):
        raise GovernanceValidationError("attestation event does not exist")
    return events[raw[0]], events[raw[1]]


def _final_payload(event: DecisionEvent) -> dict:
    payload = event.payload if isinstance(event.payload, dict) else None
    _exact_mapping(payload, _FINAL_PAYLOAD_FIELDS, "final governance payload")
    if payload["governance_decision_schema"] != GOVERNANCE_DECISION_SCHEMA:
        raise GovernanceValidationError("unsupported final governance schema")
    return payload


def _current_final_events(governance_type: str, scope_hash: str) -> list[DecisionEvent]:
    finals = list(DecisionEvent.objects.filter(
        action=FINALIZE_ACTION[governance_type], subject_type=GOVERNANCE_SUBJECT_TYPE,
        subject_id=scope_hash).order_by("sequence_number"))
    superseded = {row.supersedes_event_id for row in finals
                  if row.supersedes_event_id is not None}
    revoked_ids = set(DecisionEvent.objects.filter(
        action=REVOKE_ACTION[governance_type], subject_type=GOVERNANCE_SUBJECT_TYPE,
        subject_id=scope_hash).values_list("payload__revoked_final_event_id", flat=True))
    return [row for row in finals
            if row.pk not in superseded and row.event_id not in revoked_ids]


def _resolve_supersession(governance_type, scope_hash, supersedes_final_event_id):
    active = _current_final_events(governance_type, scope_hash)
    if supersedes_final_event_id in (None, ""):
        if active:
            raise GovernanceConflict(
                "an effective selection exists; replacement must explicitly supersede it")
        return None
    target = DecisionEvent.objects.filter(
        event_id=str(supersedes_final_event_id)).first()
    if target is None or target not in active:
        raise GovernanceConflict("supersession target is not the one current selection")
    payload = _final_payload(target)
    if (payload.get("governance_type") != governance_type
            or payload.get("governance_scope_hash") != scope_hash):
        raise GovernanceConflict("cross-type or cross-scope supersession is forbidden")
    return target


def finalize_governance_decision(
        *, user, corpus_item_id, governance_type, raw_scope, attestation_event_ids,
        supersedes_final_event_id=None) -> DecisionEvent:
    """Append one final selection after complete evidence and dual-control validation."""
    governance_type = _governance_type(governance_type)
    item = resolve_governance_candidate(corpus_item_id, governance_type)
    _require_evidence_dimensions(
        item, REQUIRED_ATTESTATION_CATEGORIES[governance_type])
    normalized_scope = normalize_governance_scope(governance_type, raw_scope)
    scope_hash = governance_scope_hash(governance_type, normalized_scope)
    subject = (GOVERNANCE_SUBJECT_TYPE, scope_hash)
    action = FINALIZE_ACTION[governance_type]
    endpoint = "intelligence.governance.finalize_governance_decision"
    result = _authorize_or_deny(user, action, subject, endpoint)
    event_a, event_b = _events_by_id(attestation_event_ids)

    with transaction.atomic():
        # Serialize the read/check/append boundary for the global signed chain. This keeps
        # two concurrent finalizations from both observing an empty effective scope.
        DecisionChainHead.objects.select_for_update().get(pk=1)
        now = timezone.now()
        _dual, sources = validate_governance_attestations(
            item, governance_type, normalized_scope, event_a, event_b, at=now)
        references, current_sources = _evidence_sources(
            item, [row["evidence_reference_id"] for row in sources])
        if current_sources != sources:
            raise GovernanceValidationError("persisted evidence hashes changed")
        integrity = verify_governance_evidence(item, references, evaluated_at=now)
        prior = _resolve_supersession(
            governance_type, scope_hash, supersedes_final_event_id)
        by_category = {
            event.payload["attestation_category"]: event for event in (event_a, event_b)}
        ordered_events = [by_category[category]
                          for category in REQUIRED_ATTESTATION_CATEGORIES[governance_type]]
        decision_scope_hash = ordered_events[0].payload["decision_scope_hash"]
        snapshot = build_authorization_snapshot(user, result, now)
        payload = {
            "governance_decision_schema": GOVERNANCE_DECISION_SCHEMA,
            "governance_type": governance_type,
            "selected_corpus_item_id": str(item.pk),
            "normalized_scope": normalized_scope,
            "governance_scope_hash": scope_hash,
            "decision_version": GOVERNANCE_DECISION_VERSION,
            "decision_scope_hash": decision_scope_hash,
            "attestation_event_ids": [row.event_id for row in ordered_events],
            "attestation_content_hashes": [{
                "event_id": row.event_id, "content_hash": row.content_hash,
            } for row in ordered_events],
            "evidence_sources": sources,
            "evidence_integrity_summary": _integrity_summary(integrity),
            "supersedes_final_event_id": prior.event_id if prior else None,
            "authority_effect": AUTHORITY_EFFECT_NONE,
            "policy_id": snapshot["policy_id"],
            "policy_version": snapshot["policy_version"],
            "authz_snapshot": snapshot,
        }
        event = append_decision(
            user=user, action=action, subject=subject, payload=payload,
            supersedes=prior)
        if event.role_used != result.role_used:
            raise GovernanceValidationError("role_used skew during finalization")
        record_authorization(
            result, request=None, endpoint=endpoint, method="SERVICE",
            metadata={"event_id": event.event_id, "governance_type": governance_type,
                      "governance_scope_hash": scope_hash})
    return event


def _bounded_reason(value) -> str:
    if not isinstance(value, str):
        raise GovernanceValidationError("revocation reason is required")
    value = unicodedata.normalize("NFKC", value).strip()
    if not value or len(value) > 1000:
        raise GovernanceValidationError("revocation reason must be 1 to 1000 characters")
    return value


def revoke_governance_decision(*, user, final_event_id, reason) -> DecisionEvent:
    """Append one signed revocation referencing the exact final event; edit nothing."""
    target = DecisionEvent.objects.filter(event_id=str(final_event_id)).first()
    if target is None:
        raise GovernanceValidationError("final governance event does not exist")
    payload = _final_payload(target)
    governance_type = _governance_type(payload["governance_type"])
    if target.action != FINALIZE_ACTION[governance_type]:
        raise GovernanceValidationError("target is not a final governance event")
    scope_hash = payload["governance_scope_hash"]
    normalized_scope = normalize_governance_scope(
        governance_type, payload["normalized_scope"])
    if (governance_scope_hash(governance_type, normalized_scope) != scope_hash
            or target.subject_type != GOVERNANCE_SUBJECT_TYPE
            or target.subject_id != scope_hash):
        raise GovernanceValidationError("target governance scope binding is invalid")
    reason = _bounded_reason(reason)
    subject = (GOVERNANCE_SUBJECT_TYPE, scope_hash)
    action = REVOKE_ACTION[governance_type]
    endpoint = "intelligence.governance.revoke_governance_decision"
    result = _authorize_or_deny(user, action, subject, endpoint)

    with transaction.atomic():
        DecisionChainHead.objects.select_for_update().get(pk=1)
        if target not in _current_final_events(governance_type, scope_hash):
            raise GovernanceConflict("only the current final decision may be revoked")
        now = timezone.now()
        snapshot = build_authorization_snapshot(user, result, now)
        revocation_payload = {
            "governance_revocation_schema": GOVERNANCE_REVOCATION_SCHEMA,
            "governance_type": governance_type,
            "selected_corpus_item_id": payload["selected_corpus_item_id"],
            "normalized_scope": normalized_scope,
            "governance_scope_hash": scope_hash,
            "decision_version": GOVERNANCE_DECISION_VERSION,
            "revoked_final_event_id": target.event_id,
            "revoked_final_content_hash": target.content_hash,
            "reason": reason,
            "authority_effect": AUTHORITY_EFFECT_NONE,
            "policy_id": snapshot["policy_id"],
            "policy_version": snapshot["policy_version"],
            "authz_snapshot": snapshot,
        }
        event = append_decision(
            user=user, action=action, subject=subject, payload=revocation_payload)
        if event.role_used != result.role_used:
            raise GovernanceValidationError("role_used skew during revocation")
        record_authorization(
            result, request=None, endpoint=endpoint, method="SERVICE",
            metadata={"event_id": event.event_id, "revoked": target.event_id})
    return event


def governance_event_history(item: CorpusItem) -> dict:
    """Read-only signed history used by candidate pages; no projection authority."""
    item_id = str(item.pk)
    attestations = list(DecisionEvent.objects.filter(
        subject_type="CorpusItem", subject_id=item_id,
        payload__governance_attestation_schema=GOVERNANCE_ATTESTATION_SCHEMA,
    ).order_by("sequence_number"))
    finals = list(DecisionEvent.objects.filter(
        action__in=FINALIZE_ACTIONS,
        payload__selected_corpus_item_id=item_id,
    ).order_by("sequence_number"))
    final_ids = [event.event_id for event in finals]
    revocations = list(DecisionEvent.objects.filter(
        action__in=REVOKE_ACTIONS,
        payload__revoked_final_event_id__in=final_ids,
    ).order_by("sequence_number")) if final_ids else []
    return {
        "attestations": tuple(attestations),
        "finals": tuple(finals),
        "revocations": tuple(revocations),
    }


__all__ = [
    "GOVERNANCE_SCOPE_SCHEMA", "GOVERNANCE_ATTESTATION_SCHEMA",
    "GOVERNANCE_DECISION_SCHEMA", "GOVERNANCE_REVOCATION_SCHEMA",
    "GOVERNANCE_DECISION_VERSION", "CANONICAL_BRAND_ASSET",
    "PRIMARY_BRAND_PALETTE", "GOVERNANCE_TYPES", "GLOBAL_WORDMARK",
    "GLOBAL_PRIMARY_LOGO", "GLOBAL_PRIMARY_PALETTE", "PRODUCT_FAMILY", "MARKET",
    "MEDIA_APPLICATION", "CANONICAL_SCOPE_TYPES", "PALETTE_SCOPE_TYPES",
    "REQUIRED_ATTESTATION_CATEGORIES", "FINALIZE_ACTION", "REVOKE_ACTION",
    "FINALIZE_ACTIONS", "REVOKE_ACTIONS", "SUPPORTED_GOVERNANCE_ACTIONS",
    "GOVERNANCE_SUBJECT_TYPE", "GovernanceError", "GovernanceValidationError",
    "GovernanceEligibilityError", "GovernanceAuthorizationDenied",
    "GovernanceConflict", "normalize_governance_scope", "governance_scope_hash",
    "resolve_governance_candidate", "verify_governance_evidence",
    "record_governance_attestation", "validate_governance_attestations",
    "finalize_governance_decision", "revoke_governance_decision",
    "governance_event_history",
]
