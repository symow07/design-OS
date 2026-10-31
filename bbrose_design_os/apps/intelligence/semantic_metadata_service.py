"""Signed human semantic-metadata service — DIP-1C-5B.

Reuses the DIP-1B-3 signing primitives (`authorize_actor`, `build_authorization_snapshot`,
`append_decision`, evidence-ownership validation, the reserved-field guard, signed
supersession) but is **CorpusItem-centric**: it never reads or writes a `ReviewCandidate`.

That decoupling is deliberate. `record_intelligence_classification` requires a *claimed*
candidate and flips it to COMPLETED; routing metadata through that path would silently move
the frozen 90-item campaign's completion metric. A descriptive-metadata bundle describes an
item, so it attaches to the item, uses its own projection domain, and leaves the campaign
untouched.

Nothing here grants authority: the event's action is forbidden to SYSTEM_ADMIN, the payload
carries no permission, and the bundle vocabulary makes ownership/canonical claims
unexpressible.
"""
from __future__ import annotations

from django.db import transaction

from apps.accounts import authz_policy as authz
from apps.accounts.authorization import authorize_actor, build_authorization_snapshot
from apps.accounts.decision_chain import append_decision, verify_event
from apps.accounts.models import DecisionEvent
from django.utils import timezone

from .human_semantic_metadata import (
    METADATA_ASSERTION_DOMAIN, METADATA_SCHEMA, MetadataBundleError,
    build_metadata_bundle,
)
from .models import CorpusItem, EvidenceReference
from .review_services import (
    AssertionValidationError, ReviewAuthorizationDenied, RESERVED_REQUEST_FIELDS,
    SUBJECT_TYPE,
)
from .semantic_metadata_scope import is_in_scope

METADATA_REQUEST_FIELDS = frozenset({
    "corpus_item_uuid", "bundle", "evidence_reference_ids", "review_scope_id",
})
METADATA_CORRECTION_FIELDS = METADATA_REQUEST_FIELDS | {"supersedes_event_id"}
REVIEW_SCOPE_ID = "dip1c_semantic_metadata_review_scope/1.0"


def _subject(item):
    return SUBJECT_TYPE, str(item.pk)


def _ensure_exact_fields(payload, expected):
    if not isinstance(payload, dict):
        raise AssertionValidationError("request payload must be an object")
    supplied = set(payload)
    reserved = supplied & RESERVED_REQUEST_FIELDS
    if expected is METADATA_CORRECTION_FIELDS:
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


def _canonical_item(item_id):
    try:
        return CorpusItem.objects.get(pk=item_id)
    except (CorpusItem.DoesNotExist, ValueError, TypeError):
        raise AssertionValidationError("unknown corpus item") from None


def _evidence_payload(item, identifiers):
    if not isinstance(identifiers, list):
        raise AssertionValidationError("evidence_reference_ids must be a list")
    if not identifiers:
        # A descriptor without evidence is unprojectable (the projector requires a non-empty
        # evidence list) and unreviewable. Refuse it here, not downstream.
        raise AssertionValidationError(
            "at least one evidence reference is required")
    rows = list(EvidenceReference.objects.select_related("source_artifact").filter(
        pk__in=identifiers, corpus_item=item, is_test_only=False).order_by("pk"))
    if len(rows) != len(set(identifiers)):
        raise AssertionValidationError(
            "all evidence references must be non-test evidence for the same corpus item")
    return [{
        "evidence_reference_id": str(r.pk),
        "evidence_hash": r.evidence_hash,
        "source_artifact_id": str(r.source_artifact_id),
        "source_sha256": r.source_artifact.sha256,
    } for r in rows]


def _authorize(user, action, item):
    result = authorize_actor(user, action, subject=_subject(item))
    if not result.allowed:
        raise ReviewAuthorizationDenied(f"not authorized: {result.reason_code}")
    return result


def _signed_metadata_payload(*, action, user, item, bundle, evidence):
    at = timezone.now()
    result = _authorize(user, action, item)
    payload = {
        "assertion_schema": METADATA_SCHEMA,
        "assertion_domain": METADATA_ASSERTION_DOMAIN,
        "corpus_item_id": str(item.pk),
        "review_scope_id": REVIEW_SCOPE_ID,
        "metadata_bundle": bundle,
        "evidence_reference_ids": [row["evidence_reference_id"] for row in evidence],
        "evidence_source_hashes": evidence,
        "policy_id": authz.POLICY_ID,
        "policy_version": authz.POLICY_VERSION,
        "authz_snapshot": build_authorization_snapshot(user, result, at),
    }
    # Supersession is recorded on the signed event's own `supersedes_event` link, never as a
    # payload key — the chain forbids it, so there is exactly one source of truth.
    return payload


def _validated_bundle(raw_bundle):
    try:
        return build_metadata_bundle(raw_bundle if isinstance(raw_bundle, dict) else {})
    except MetadataBundleError as exc:
        raise AssertionValidationError(f"metadata bundle rejected: {exc}") from exc


@transaction.atomic
def record_human_semantic_metadata(*, user, payload):
    """Append one signed metadata bundle for a corpus item. Touches no ReviewCandidate."""
    _ensure_exact_fields(payload, METADATA_REQUEST_FIELDS)
    if payload.get("review_scope_id") != REVIEW_SCOPE_ID:
        raise AssertionValidationError("review_scope_id does not match the pilot scope")
    item = _canonical_item(payload["corpus_item_uuid"])
    if not is_in_scope(item):
        raise AssertionValidationError("corpus item is not in the metadata review scope")
    # DIP-1C-5C-CORR-3: a second independent record would create two active bundles for
    # one item. If a prior metadata event is still effective, the only honest next step is
    # a signed correction — enforced HERE, not only in the template, so a crafted POST
    # cannot bypass the correction workflow.
    from .metadata_history import (
        CORRECTION_ACTION_REQUIRED, resolve_effective_assertion_from_verified_history,
    )
    resolved = resolve_effective_assertion_from_verified_history(item)
    if resolved.has_effective:
        raise AssertionValidationError(
            f"{CORRECTION_ACTION_REQUIRED}: metadata event {resolved.event.event_id} is "
            "already effective for this item; submit a correction instead")
    if resolved.state == "REVIEW_REQUIRED":
        raise AssertionValidationError(
            f"REVIEW_REQUIRED: {resolved.reason}; no new metadata event may be recorded "
            "while the signed history is unresolved")
    if resolved.state == "INVALID":
        raise AssertionValidationError(f"chain not usable: {resolved.reason}")
    bundle = _validated_bundle(payload.get("bundle"))
    evidence = _evidence_payload(item, payload["evidence_reference_ids"])
    signed = _signed_metadata_payload(
        action=authz.RECORD_HUMAN_SEMANTIC_METADATA, user=user, item=item,
        bundle=bundle, evidence=evidence)
    return append_decision(
        user=user, action=authz.RECORD_HUMAN_SEMANTIC_METADATA,
        subject=_subject(item), payload=signed)


@transaction.atomic
def correct_human_semantic_metadata(*, user, payload):
    """Supersede a prior metadata bundle with a new signed one. The prior event is
    preserved; supersession is same-item, same-domain only."""
    _ensure_exact_fields(payload, METADATA_CORRECTION_FIELDS)
    if payload.get("review_scope_id") != REVIEW_SCOPE_ID:
        raise AssertionValidationError("review_scope_id does not match the pilot scope")
    item = _canonical_item(payload["corpus_item_uuid"])
    if not is_in_scope(item):
        raise AssertionValidationError("corpus item is not in the metadata review scope")
    # DIP-1C-5C-CORR-4: an ordinary correction has ONE parent, so correcting one of several
    # active events leaves the others active and resolves nothing. While history is
    # ambiguous only the dedicated resolution service may act.
    from .metadata_history import (
        REVIEW_REQUIRED as HISTORY_REVIEW_REQUIRED,
        resolve_effective_assertion_from_verified_history,
    )
    history = resolve_effective_assertion_from_verified_history(item)
    if history.state == HISTORY_REVIEW_REQUIRED:
        raise AssertionValidationError(
            f"REVIEW_REQUIRED: {history.reason}; a single-parent correction cannot resolve "
            "ambiguous metadata history — use the conflict-resolution workflow")
    # Lock the target row first: a concurrent correction of the SAME event blocks here
    # until the first commits, then sees the supersession below and fails closed. Without
    # this, both would read an unsuperseded target and both would append.
    prior = DecisionEvent.objects.select_for_update().filter(
        event_id=payload["supersedes_event_id"]).first()
    if (prior is None
            or prior.action not in (authz.RECORD_HUMAN_SEMANTIC_METADATA,
                                    authz.CORRECT_HUMAN_SEMANTIC_METADATA)
            or (prior.payload or {}).get("corpus_item_id") != str(item.pk)
            or (prior.payload or {}).get("assertion_domain")
            != METADATA_ASSERTION_DOMAIN):
        # no cross-item and no cross-domain supersession
        raise AssertionValidationError(
            "supersedes_event_id must reference a prior metadata event for this item")
    if DecisionEvent.objects.filter(supersedes_event=prior).exists():
        raise AssertionValidationError(
            "SUPERSESSION_TARGET_ALREADY_SUPERSEDED: this metadata event has already been "
            "corrected; reload and correct the current event instead")
    bundle = _validated_bundle(payload.get("bundle"))
    evidence = _evidence_payload(item, payload["evidence_reference_ids"])
    signed = _signed_metadata_payload(
        action=authz.CORRECT_HUMAN_SEMANTIC_METADATA, user=user, item=item,
        bundle=bundle, evidence=evidence)
    return append_decision(
        user=user, action=authz.CORRECT_HUMAN_SEMANTIC_METADATA,
        subject=_subject(item), payload=signed, supersedes=prior)


# =================================================================================
# DIP-1C-5C-CORR-4: conflict resolution
# =================================================================================
RESOLUTION_REQUEST_FIELDS = frozenset({
    "corpus_item_uuid", "bundle", "evidence_reference_ids", "review_scope_id",
    "resolved_event_ids", "resolution_reason", "incident_type", "reviewer_explanation",
})


@transaction.atomic
def resolve_human_semantic_metadata_conflict(*, user, payload):
    """Reduce SEVERAL active metadata events to one effective bundle, in one signed event.

    Why this exists rather than two corrections: supersession has a single parent, so
    correcting each duplicate separately leaves one active correction per duplicate and
    resolves nothing. This event names the whole active set it invalidates.

    Every prior event is preserved. Nothing is edited or deleted, and the resolution is
    refused unless the set it names is *exactly* the set the verified history reports
    active — a partial resolution would silently leave a conflict behind.
    """
    from .human_semantic_metadata import (
        INCIDENT_TYPES, MAX_EXPLANATION_LENGTH, RESOLUTION_REASONS, RESOLUTION_SCHEMA,
        bundle_hash,
    )
    from .metadata_history import (
        REVIEW_REQUIRED, resolve_effective_assertion_from_verified_history,
    )
    _ensure_exact_fields(payload, RESOLUTION_REQUEST_FIELDS)
    if payload.get("review_scope_id") != REVIEW_SCOPE_ID:
        raise AssertionValidationError("review_scope_id does not match the pilot scope")
    if payload.get("resolution_reason") not in RESOLUTION_REASONS:
        raise AssertionValidationError("unsupported resolution_reason")
    if payload.get("incident_type") not in INCIDENT_TYPES:
        raise AssertionValidationError("unsupported incident_type")
    explanation = (payload.get("reviewer_explanation") or "").strip()
    if not explanation:
        raise AssertionValidationError("a resolution must record a reviewer explanation")
    if len(explanation) > MAX_EXPLANATION_LENGTH:
        raise AssertionValidationError("reviewer_explanation is too long")

    item = _canonical_item(payload["corpus_item_uuid"])
    if not is_in_scope(item):
        raise AssertionValidationError("corpus item is not in the metadata review scope")

    requested = payload.get("resolved_event_ids")
    if not isinstance(requested, list) or not requested:
        raise AssertionValidationError("resolved_event_ids must be a non-empty list")
    if len(set(requested)) != len(requested):
        raise AssertionValidationError("resolved_event_ids contains duplicates")

    # Lock the referenced rows in deterministic sequence order, then re-read the active set
    # UNDER the locks — a concurrent resolution blocks here and loses the recheck below.
    locked = list(DecisionEvent.objects.select_for_update().filter(
        event_id__in=requested).order_by("sequence_number"))
    if len(locked) != len(requested):
        raise AssertionValidationError(
            "resolved_event_ids references an event that does not exist")

    resolved = resolve_effective_assertion_from_verified_history(item)
    if resolved.state != REVIEW_REQUIRED or resolved.reason != (
            "MULTIPLE_ACTIVE_METADATA_EVENTS"):
        raise AssertionValidationError(
            f"no multi-event metadata conflict to resolve (history is {resolved.state}: "
            f"{resolved.reason})")
    active_ids = set(resolved.active_event_ids)
    if set(requested) != active_ids:
        # a partial or padded set would leave the conflict in place, or invalidate an
        # event the reviewer never saw
        raise AssertionValidationError(
            "resolved_event_ids must be exactly the currently active metadata events "
            f"({sorted(active_ids)})")

    for event in locked:
        ok, _problems = verify_event(event)
        event_payload = event.payload if isinstance(event.payload, dict) else {}
        if not ok:
            raise AssertionValidationError("a referenced event does not verify")
        if event_payload.get("corpus_item_id") != str(item.pk):
            raise AssertionValidationError("a referenced event belongs to another item")
        if event_payload.get("assertion_domain") != METADATA_ASSERTION_DOMAIN:
            raise AssertionValidationError("a referenced event is in another domain")
        if event_payload.get("assertion_schema") != METADATA_SCHEMA:
            raise AssertionValidationError("a referenced event uses another schema")

    bundle = _validated_bundle(payload.get("bundle"))
    evidence = _evidence_payload(item, payload["evidence_reference_ids"])
    action = authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT
    at = timezone.now()
    result = _authorize(user, action, item)
    signed = {
        "resolution_schema": RESOLUTION_SCHEMA,
        "corpus_item_id": str(item.pk),
        "metadata_domain": METADATA_ASSERTION_DOMAIN,
        "metadata_schema": METADATA_SCHEMA,
        "resolved_event_ids": sorted(requested),
        "resolved_event_sequence_numbers": sorted(e.sequence_number for e in locked),
        "prior_bundle_hashes": {
            e.event_id: bundle_hash((e.payload or {}).get("metadata_bundle") or {})
            for e in sorted(locked, key=lambda e: e.event_id)},
        "final_metadata_bundle": bundle,
        "final_evidence_reference_ids": [
            row["evidence_reference_id"] for row in evidence],
        "final_source_hashes": evidence,
        "resolution_reason": payload["resolution_reason"],
        "incident_type": payload["incident_type"],
        "reviewer_explanation": explanation,
        "policy_id": authz.POLICY_ID,
        "policy_version": authz.POLICY_VERSION,
        "authz_snapshot": build_authorization_snapshot(user, result, at),
    }
    return append_decision(
        user=user, action=action, subject=_subject(item), payload=signed)
