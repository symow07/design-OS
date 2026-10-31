"""DECISION-EVENT HUMAN REAFFIRMATION CEREMONY — incident DEKEYLOSS-2026-07-25-001.

Executes the three human decisions recorded in the reaffirmation packet:

* sequence 1 (reviewer bootstrap grant)  → ``NO_LONGER_REQUIRED`` — a signed
  epoch-2 closure event; the assignment is revoked and the sole-purpose
  profile disabled. No reviewer authority is recreated; superuser authority
  is untouched (it never came from the chain).
* sequences 2 and 3 (semantic metadata) → ``SUPERSEDE`` — one epoch-2
  replacement per legacy event, preserving the exact bounded semantic
  meaning, superseding its specific original.

Originals are never modified, re-signed, or presented as new. Replacements
never grant operational-use permissions (§3 — those stay with their own
human-governed decisions). The whole ceremony is idempotent: a second run
reconciles against the existing closure/replacements and writes nothing.
"""
from __future__ import annotations

import json

from django.db import transaction
from django.utils import timezone

from . import bootstrap_registry as reg
from .bootstrap_environment import classify_environment
from .decision_chain import (
    _BOOTSTRAP_APPEND_TOKEN,
    append_bootstrap_closure_event,
    append_decision,
    event_integrity_state,
)
from .models import (
    GRANT_BOOTSTRAP_SINGLE_OPERATOR,
    RESULT_ALLOWED,
    AuthorizationAudit,
    BootstrapState,
    DecisionChainHead,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from .security import key_epochs

REAFFIRMATION_SCHEMA = "decision_event_reaffirmation/1.0"
PACKET_PATH = "docs/security/decision_event_reaffirmation_packet.json"
CEREMONY_ENDPOINT = "cli:decision_event_reaffirmation_ceremony"

CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED = (
    "CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED")


class ReaffirmationError(RuntimeError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def _legacy_grant_event():
    return DecisionEvent.objects.filter(
        action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE).order_by(
        "sequence_number").first()


def _legacy_metadata_events():
    from apps.accounts import authz_policy as authz
    return list(DecisionEvent.objects.filter(
        action=authz.RECORD_HUMAN_SEMANTIC_METADATA).order_by(
        "sequence_number"))


def _require_legacy(event, what):
    state = event_integrity_state(event)
    if state != key_epochs.LEGACY_STATE:
        raise ReaffirmationError(
            "LEGACY_STATE_REQUIRED",
            f"{what} (seq {event.sequence_number}) is {state}, not a "
            "lost-epoch legacy event — this ceremony applies to nothing else")
    return event


def _existing_replacement(legacy_event):
    return DecisionEvent.objects.filter(
        supersedes_event=legacy_event,
        payload__reaffirmation__schema=REAFFIRMATION_SCHEMA).first()


# --- §2 applicability — checked BEFORE anything is appended ----------------------

def check_metadata_applicability(legacy_event) -> dict:
    """Verify the preserved payload still applies to the same corpus item.
    Raises ReaffirmationError(CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED)
    on any ambiguity — nothing is guessed."""
    from apps.intelligence.human_semantic_metadata import build_metadata_bundle
    from apps.intelligence.semantic_metadata_service import (
        _canonical_item,
        _evidence_payload,
    )

    payload = legacy_event.payload if isinstance(legacy_event.payload,
                                                 dict) else {}

    def _blocked(detail):
        raise ReaffirmationError(
            CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED,
            f"seq {legacy_event.sequence_number}: {detail}")

    item_id = payload.get("corpus_item_id")
    if not item_id or legacy_event.subject_id != item_id:
        _blocked("payload item does not match the signed subject")
    try:
        item = _canonical_item(item_id)
    except Exception as exc:  # noqa: BLE001 — any resolution failure blocks
        _blocked(f"corpus item cannot be canonically resolved ({exc})")
    if str(item.pk) != item_id:
        _blocked("corpus item identity has changed (non-canonical)")

    # the semantic bundle must still validate under the CURRENT vocabulary,
    # unchanged — a normalisation drift would silently reinterpret it
    bundle = payload.get("metadata_bundle")
    try:
        revalidated = build_metadata_bundle(bundle)
    except Exception as exc:  # noqa: BLE001
        _blocked(f"preserved bundle no longer validates ({exc})")
    if revalidated != bundle:
        _blocked("preserved bundle normalises differently today — human "
                 "review required, no silent reinterpretation")

    # evidence identity: the referenced evidence rows must still exist and
    # hash exactly as the signed payload recorded
    try:
        evidence_now = _evidence_payload(
            item, payload.get("evidence_reference_ids"))
    except Exception as exc:  # noqa: BLE001
        _blocked(f"evidence references no longer resolve ({exc})")
    if evidence_now != payload.get("evidence_source_hashes"):
        _blocked("evidence hashes or bounded corpus identity changed")

    # the assertion must not conflict with newer reviewed metadata: these
    # legacy events must still be the LAST metadata events for the item
    # (anything newer that is not a reaffirmation replacement blocks)
    newer = DecisionEvent.objects.filter(
        subject_type=legacy_event.subject_type, subject_id=item_id,
        sequence_number__gt=legacy_event.sequence_number).exclude(
        payload__reaffirmation__schema=REAFFIRMATION_SCHEMA)
    from apps.accounts import authz_policy as authz
    newer = [e for e in newer
             if e.action in (authz.RECORD_HUMAN_SEMANTIC_METADATA,
                             authz.CORRECT_HUMAN_SEMANTIC_METADATA,
                             authz.RESOLVE_HUMAN_SEMANTIC_METADATA_CONFLICT)
             and event_integrity_state(e) != key_epochs.LEGACY_STATE]
    if newer:
        _blocked("newer reviewed metadata exists for this item")

    # §3 boundary: a semantic bundle carries no operational-use permission
    permission_ish = {k for k in (bundle or {})
                      if "permission" in k or "authority" in k
                      or "license" in k or "licence" in k}
    if permission_ish:
        _blocked(f"bundle carries permission-like keys {sorted(permission_ish)}")
    return {"item": item, "bundle": bundle,
            "evidence_ids": payload.get("evidence_reference_ids")}


# --- §2 replacements --------------------------------------------------------------

def supersede_legacy_metadata_event(*, actor, legacy_event) -> DecisionEvent:
    """One epoch-2 replacement for ONE legacy assertion. Idempotent."""
    from apps.intelligence.semantic_metadata_service import (
        _evidence_payload,
        _signed_metadata_payload,
        _subject,
    )
    from apps.accounts import authz_policy as authz

    _require_legacy(legacy_event, "metadata event")
    existing = _existing_replacement(legacy_event)
    if existing is not None:
        return existing
    if DecisionEvent.objects.filter(supersedes_event=legacy_event).exists():
        raise ReaffirmationError(
            CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED,
            f"seq {legacy_event.sequence_number} is already superseded by a "
            "non-reaffirmation event")
    applicability = check_metadata_applicability(legacy_event)
    item = applicability["item"]
    evidence = _evidence_payload(item, applicability["evidence_ids"])
    signed = _signed_metadata_payload(
        action=authz.CORRECT_HUMAN_SEMANTIC_METADATA, user=actor, item=item,
        bundle=applicability["bundle"], evidence=evidence)
    incident = key_epochs.incident_for(legacy_event.signing_key_id) or {}
    signed["reaffirmation"] = {
        "schema": REAFFIRMATION_SCHEMA,
        "incident_id": incident.get("incident_id"),
        "human_decision": "SUPERSEDE",
        "legacy_event_id": legacy_event.event_id,
        "legacy_sequence_number": legacy_event.sequence_number,
        "legacy_integrity_state": key_epochs.LEGACY_STATE,
        "statement": "reaffirmed replacement of a lost-epoch assertion — the "
                     "original is preserved for audit and restored authority "
                     "covers ONLY the original bounded semantic claims",
    }
    return append_decision(
        user=actor, action=authz.CORRECT_HUMAN_SEMANTIC_METADATA,
        subject=_subject(item), payload=signed, supersedes=legacy_event)


# --- §1 closure --------------------------------------------------------------------

def close_legacy_reviewer_grant(*, actor) -> DecisionEvent:
    """The NO_LONGER_REQUIRED closure of the lost-epoch bootstrap grant.
    Revokes the assignment, disables the sole-purpose profile, and appends
    the signed closure event — one transaction, idempotent."""
    grant = _legacy_grant_event()
    if grant is None:
        raise ReaffirmationError("NO_BOOTSTRAP_GRANT_EVENT")
    _require_legacy(grant, "bootstrap grant")
    existing = DecisionEvent.objects.filter(
        action=reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE).first()
    if existing is not None:
        return existing
    if not actor.is_superuser or not actor.is_active:
        raise ReaffirmationError("ACTOR_NOT_SUPERUSER_OR_INACTIVE")
    classification, environment_evidence = classify_environment()

    with transaction.atomic():
        User = type(actor)
        user = User.objects.select_for_update().get(pk=actor.pk)
        assignment = ReviewerRoleAssignment.objects.select_for_update().filter(
            grant_source=GRANT_BOOTSTRAP_SINGLE_OPERATOR).first()
        if assignment is None:
            raise ReaffirmationError("NO_SINGLE_OPERATOR_ASSIGNMENT")
        if assignment.revoked_at is not None:
            raise ReaffirmationError(
                "ASSIGNMENT_ALREADY_REVOKED",
                "revoked outside this ceremony — human review required")
        head = DecisionChainHead.objects.select_for_update().get(pk=1)
        BootstrapState.objects.select_for_update().get(pk=1)  # order lock

        now = timezone.now()
        reason = ("DECISION-EVENT KEY EPOCH RESET — human decision "
                  "NO_LONGER_REQUIRED (incident DEKEYLOSS-2026-07-25-001): "
                  "an unverifiable lost-epoch grant may not remain "
                  "operational until expiry")
        assignment.revoked_at = now
        assignment.revoked_by = user
        assignment.revocation_reason = reason
        assignment.save()

        profile = ReviewerProfile.objects.select_for_update().filter(
            user=assignment.user).first()
        others = ReviewerRoleAssignment.objects.filter(
            user=assignment.user, revoked_at__isnull=True).exclude(
            pk=assignment.pk)
        profile_disabled = False
        if profile is not None and profile.reviewer_enabled and \
                not others.exists():
            profile.reviewer_enabled = False
            profile.save()
            profile_disabled = True

        incident = key_epochs.incident_for(grant.signing_key_id) or {}
        payload = {
            "bootstrap_schema": reg.CLOSURE_CEREMONY_SCHEMA,
            "single_operator": True,
            "dual_control": False,
            "actor_user_id": user.pk,
            "target_user_id": user.pk,
            "legacy_predecessor_event_id": grant.event_id,
            "legacy_integrity_state": key_epochs.LEGACY_STATE,
            "incident_id": incident.get("incident_id"),
            "human_decision": reg.CLOSURE_HUMAN_DECISION,
            "revoked_assignment_id": assignment.pk,
            "revoked_role": assignment.role,
            "revoked_at": now.isoformat(),
            "reason": reason,
            "profile_disabled": profile_disabled,
            "environment_classification": classification,
            "environment_evidence": environment_evidence,
            "account_control_basis": reg.CLOSURE_ACCOUNT_CONTROL_BASIS,
            "observed_user_is_active": bool(user.is_active),
            "observed_user_is_superuser": bool(user.is_superuser),
            "authorization_basis": reg.CLOSURE_AUTHORIZATION_BASIS,
            "statements": list(reg.CLOSURE_REQUIRED_STATEMENTS),
        }
        event = append_bootstrap_closure_event(
            capability=_BOOTSTRAP_APPEND_TOKEN, user=user, payload=payload,
            head=head, now=now)
        AuthorizationAudit.objects.create(
            user=user, action=reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE,
            subject_type="User", subject_id=str(user.pk),
            result=RESULT_ALLOWED, reason_code="AUTHORIZED",
            active_roles=[], authorizing_roles=[],
            role_used=reg.BOOTSTRAP_OPERATOR,
            selection_rule="SINGLE_OPERATOR_REAFFIRMATION_CLOSURE",
            endpoint=CEREMONY_ENDPOINT, request_method="",
            metadata={
                "severity": "CRITICAL",
                "ceremony": reg.CLOSURE_CEREMONY_SCHEMA,
                "incident_id": incident.get("incident_id"),
                "human_decision": reg.CLOSURE_HUMAN_DECISION,
                "legacy_predecessor_event_id": grant.event_id,
                "decision_event_id": event.event_id,
                "revoked_assignment_id": assignment.pk,
                "profile_disabled": profile_disabled,
            })
        return event


# --- the whole ceremony -------------------------------------------------------------

def perform_reaffirmation_ceremony(*, actor, packet_path: str = PACKET_PATH
                                   ) -> dict:
    """Order matters: the metadata replacements are appended FIRST (they are
    authorized by the still-active DESIGN_REVIEWER assignment), the closure
    LAST (it removes that assignment). Idempotent end to end."""
    metadata_events = _legacy_metadata_events()
    if len(metadata_events) != 2:
        raise ReaffirmationError(
            CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED,
            f"expected exactly 2 legacy metadata events, found "
            f"{len(metadata_events)}")
    for ev in metadata_events:                     # validate BOTH up front
        if _existing_replacement(ev) is None:
            _require_legacy(ev, "metadata event")
            check_metadata_applicability(ev)

    replacements = [
        supersede_legacy_metadata_event(actor=actor, legacy_event=ev)
        for ev in metadata_events]
    closure = close_legacy_reviewer_grant(actor=actor)

    lineage = [{
        "legacy_event_id": _legacy_grant_event().event_id,
        "legacy_sequence_number": 1,
        "human_decision": reg.CLOSURE_HUMAN_DECISION,
        "relationship": "CLOSED_BY",
        "closure_event_id": closure.event_id,
        "actor_user_id": closure.actor_id,
        "timestamp": closure.created_at.isoformat(),
        "key_epoch": closure.signing_key_id,
        "legacy_integrity_state": event_integrity_state(_legacy_grant_event()),
        "new_event_integrity_state": event_integrity_state(closure),
    }] + [{
        "legacy_event_id": ev.event_id,
        "legacy_sequence_number": ev.sequence_number,
        "human_decision": "SUPERSEDE",
        "relationship": "SUPERSEDED_BY",
        "replacement_event_id": rep.event_id,
        "actor_user_id": rep.actor_id,
        "timestamp": rep.created_at.isoformat(),
        "key_epoch": rep.signing_key_id,
        "legacy_integrity_state": event_integrity_state(ev),
        "new_event_integrity_state": event_integrity_state(rep),
    } for ev, rep in zip(metadata_events, replacements)]

    result = {"closure_event_id": closure.event_id,
              "replacement_event_ids": [r.event_id for r in replacements],
              "lineage": lineage}
    _update_packet(packet_path, result)
    return result


def _update_packet(path, result) -> None:
    try:
        with open(path, encoding="utf-8") as fh:
            packet = json.load(fh)
    except OSError:
        return                                      # packet is documentation
    outcomes = {1: reg.CLOSURE_HUMAN_DECISION, 2: "SUPERSEDED",
                3: "SUPERSEDED"}
    for decision in packet.get("decisions", []):
        seq = decision.get("sequence_number")
        decision["human_decision"] = outcomes.get(seq)
        for entry in result["lineage"]:
            if entry["legacy_sequence_number"] == seq:
                decision["lineage"] = entry
    packet["status"] = "COMPLETE"
    packet["completed_on"] = timezone.now().isoformat()
    packet["closure_event_id"] = result["closure_event_id"]
    packet["replacement_event_ids"] = result["replacement_event_ids"]
    packet["remaining_blockers"] = [
        "MULTIPLE_ACTIVE_METADATA_EVENTS — the corpus item returns to its "
        "pre-incident posture (two active assertions); resolving that fork "
        "is the ordinary conflict-resolution workflow, not this ceremony"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(packet, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


__all__ = [
    "REAFFIRMATION_SCHEMA", "PACKET_PATH",
    "CORPUS_REAFFIRMATION_PAYLOAD_REVIEW_REQUIRED", "ReaffirmationError",
    "check_metadata_applicability", "supersede_legacy_metadata_event",
    "close_legacy_reviewer_grant", "perform_reaffirmation_ceremony",
]
