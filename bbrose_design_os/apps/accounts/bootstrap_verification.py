"""Dedicated verification for the single-operator bootstrap event —
DIP-1A-BOOTSTRAP-CORR-2.

The ordinary verifier asks: did a recognised role, held at the time, authorize this action
under the pinned policy, and does a canonical `authz_snapshot` prove it? None of that is
honestly answerable at genesis bootstrap — the operator held no role, by definition.

So the bootstrap event gets its **own** verifier rather than a relaxation of the general
one. Nothing here makes role or snapshot checks optional for ordinary events: this module
is reached only for `bootstrap_initial_reviewer_role`, and it is *stricter* than the general
path, because everything the general path would have inferred from a role must instead be
proven against the payload, the assignment row and the bootstrap state.

It also polices the boundary in the other direction: the `BOOTSTRAP_OPERATOR` sentinel on
any other action, and a fabricated `authz_snapshot` on this one, are both fatal.
"""
from __future__ import annotations

from . import authz_policy as authz
from . import bootstrap_registry as reg
from .bootstrap_environment import EnvironmentClassificationError  # noqa: F401 (documented)
from .models import (
    GRANT_BOOTSTRAP_SINGLE_OPERATOR, BootstrapState, DecisionEvent,
    ReviewerProfile, ReviewerRoleAssignment,
)

#: Fatal code used when the chain and the database disagree about the ceremony.
BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN = "BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN"
BOOTSTRAP_EVENT_INVALID = "BOOTSTRAP_EVENT_INVALID"
BOOTSTRAP_SENTINEL_MISUSED = "BOOTSTRAP_SENTINEL_MISUSED"


def verify_bootstrap_event(event) -> list[str]:
    """Return a list of problems for one bootstrap event. Empty means verified.

    Crypto (signature, content hash, linkage, head) is already established by the general
    chain verifier before this runs; this establishes the ceremony's *semantics*.
    """
    problems: list[str] = []
    payload = event.payload if isinstance(event.payload, dict) else {}

    if event.action == reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE:
        return _verify_closure_event(event, payload)
    if event.action == reg.TEMPORARY_WEB_REVIEWER_GRANT:
        return _verify_temp_grant_event(event, payload)
    if event.action == reg.PIPELINE_CONTAINER_CONCEPT_SELECT:
        return _verify_concept_select_event(event, payload)

    # --- envelope -----------------------------------------------------------------
    if event.action != reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE:
        return [f"{BOOTSTRAP_EVENT_INVALID}: not a bootstrap action"]
    if event.role_used != reg.BOOTSTRAP_OPERATOR:
        problems.append("bootstrap event does not use the BOOTSTRAP_OPERATOR sentinel")
    if reg.BOOTSTRAP_OPERATOR in authz.ROLES:
        # a future edit that turned the sentinel into a real role would silently make this
        # event look role-authorized; refuse to verify in that world
        problems.append("BOOTSTRAP_OPERATOR has become a real role — sentinel compromised")
    if event.subject_type != "User" or event.subject_id != str(event.actor_id):
        problems.append("bootstrap subject is not the acting user")
    if "authz_snapshot" in payload:
        problems.append("bootstrap event carries a fabricated authorization snapshot")
    if set(payload) != reg.CEREMONY_PAYLOAD_FIELDS:
        problems.append("bootstrap payload fields are not exact")
        return problems                      # the rest would read absent keys as failures

    # --- ceremony semantics -------------------------------------------------------
    if payload["bootstrap_schema"] != reg.BOOTSTRAP_CEREMONY_SCHEMA:
        problems.append("unsupported bootstrap ceremony schema")
    if payload["single_operator"] is not True:
        problems.append("single_operator is not true")
    if payload["dual_control"] is not False:
        problems.append("dual_control is not false")
    if payload["actor_user_id"] != payload["target_user_id"]:
        problems.append("actor and target differ — not a single-operator ceremony")
    if payload["actor_user_id"] != event.actor_id:
        problems.append("payload actor does not match the signed actor")
    if payload["granted_role"] not in reg.ALLOWED_BOOTSTRAP_ROLES:
        problems.append(f"granted role {payload['granted_role']!r} is not permitted")
    if payload["environment_classification"] != reg.ENVIRONMENT_LOCAL_DEVELOPMENT:
        problems.append("environment classification is not LOCAL_DEVELOPMENT")
    if payload["account_control_basis"] != reg.ACCOUNT_CONTROL_PASSWORD_CHALLENGE:
        problems.append("account-control basis is not the approved password challenge")
    if payload["authorization_basis"] != reg.AUTHORIZATION_BASIS:
        problems.append("authorization basis is not the approved bootstrap basis")
    if payload["observed_user_is_active"] is not True:
        problems.append("operator was not observed active")
    if payload["observed_user_is_superuser"] is not True:
        problems.append("operator was not observed to be a superuser")
    if payload["prior_bootstrap_state"].get("closed") is not False:
        problems.append("prior bootstrap state was not open")
    if payload["resulting_bootstrap_state"].get("closed") is not True:
        problems.append("resulting bootstrap state is not closed")

    problems += _verify_expiry(payload)
    problems += _verify_assignment(event, payload)
    problems += _verify_state(event)
    return problems


def _verify_expiry(payload):
    from django.utils.dateparse import parse_datetime
    granted = parse_datetime(payload["granted_at"] or "")
    expires = parse_datetime(payload["expires_at"] or "")
    if granted is None or expires is None:
        return ["ceremony timestamps are not parseable"]
    if expires <= granted:
        return ["ceremony expiry is not after the grant"]
    if (expires - granted).days > reg.MAX_EXPIRY_DAYS:
        return [f"ceremony expiry exceeds {reg.MAX_EXPIRY_DAYS} days"]
    return []


def _verify_assignment(event, payload):
    """The signed event and the (unsigned) assignment row must agree in every field that
    matters. A mismatch means the row was mutated out of chain."""
    rows = list(ReviewerRoleAssignment.objects.filter(
        user_id=payload["target_user_id"], role=payload["granted_role"],
        grant_source=GRANT_BOOTSTRAP_SINGLE_OPERATOR))
    if not rows:
        return [f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: signed ceremony event exists "
                "but no single-operator role assignment does"]
    if len(rows) > 1:
        return [f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: multiple single-operator "
                "assignments exist"]
    row = rows[0]
    problems = []
    if row.granted_by_id != payload["actor_user_id"]:
        problems.append("assignment granter does not match the ceremony actor")
    if row.granted_at.isoformat() != payload["granted_at"]:
        problems.append("assignment granted_at does not match the signed event")
    if row.expires_at.isoformat() != payload["expires_at"]:
        problems.append("assignment expiry does not match the signed event")
    if row.grant_reason != payload["reason"]:
        problems.append("assignment reason does not match the signed event")
    profile = ReviewerProfile.objects.filter(user_id=payload["target_user_id"]).first()
    if profile is None or not profile.reviewer_enabled:
        problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: no enabled reviewer "
                        "profile for the ceremony target")
    return [f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: {p}" for p in problems]


def _verify_state(event):
    state = BootstrapState.objects.filter(pk=1).first()
    if state is None:
        return [f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: no bootstrap state row"]
    problems = []
    if not state.closed:
        problems.append("bootstrap is open despite a completed ceremony")
    if state.closed_by_event_id != event.pk:
        problems.append("closure is not anchored to this ceremony event")
    if state.break_glass_count != 0:
        problems.append("break_glass_count is not zero after the ceremony")
    return [f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: {p}" for p in problems]


def _verify_closure_event(event, payload) -> list[str]:
    """KEY EPOCH RESET closure — de-escalation of a lost-epoch bootstrap grant.

    Everything the closure claims must agree with the database: the grant it
    references, the revoked assignment row, the profile state and the four
    signed non-reaffirmation statements. It can prove only the REMOVAL of
    authority; nothing here can make a closure grant anything.
    """
    from .security import key_epochs

    problems: list[str] = []
    if event.role_used != reg.BOOTSTRAP_OPERATOR:
        problems.append("closure event does not use the BOOTSTRAP_OPERATOR sentinel")
    if event.subject_type != "User" or event.subject_id != str(event.actor_id):
        problems.append("closure subject is not the acting user")
    if "authz_snapshot" in payload:
        problems.append("closure event carries a fabricated authorization snapshot")
    if set(payload) != reg.CLOSURE_PAYLOAD_FIELDS:
        problems.append("closure payload fields are not exact")
        return [f"{BOOTSTRAP_EVENT_INVALID}: {p}" for p in problems]

    if payload["bootstrap_schema"] != reg.CLOSURE_CEREMONY_SCHEMA:
        problems.append("unsupported closure ceremony schema")
    if payload["single_operator"] is not True:
        problems.append("single_operator is not true")
    if payload["dual_control"] is not False:
        problems.append("dual_control is not false")
    if payload["actor_user_id"] != payload["target_user_id"]:
        problems.append("actor and target differ — not a single-operator closure")
    if payload["actor_user_id"] != event.actor_id:
        problems.append("payload actor does not match the signed actor")
    if payload["human_decision"] != reg.CLOSURE_HUMAN_DECISION:
        problems.append("closure human decision is not NO_LONGER_REQUIRED")
    if payload["environment_classification"] != reg.ENVIRONMENT_LOCAL_DEVELOPMENT:
        problems.append("environment classification is not LOCAL_DEVELOPMENT")
    if payload["account_control_basis"] != reg.CLOSURE_ACCOUNT_CONTROL_BASIS:
        problems.append("account-control basis is not the approved closure basis")
    if payload["authorization_basis"] != reg.CLOSURE_AUTHORIZATION_BASIS:
        problems.append("authorization basis is not the approved closure basis")
    if payload["observed_user_is_active"] is not True:
        problems.append("operator was not observed active")
    if payload["observed_user_is_superuser"] is not True:
        problems.append("operator was not observed to be a superuser")
    if tuple(payload["statements"]) != reg.CLOSURE_REQUIRED_STATEMENTS:
        problems.append("closure statements are not the required non-reaffirmation set")
    if payload["legacy_integrity_state"] != key_epochs.LEGACY_STATE:
        problems.append("closure does not record the legacy integrity state")

    predecessor = DecisionEvent.objects.filter(
        event_id=payload["legacy_predecessor_event_id"]).first()
    if predecessor is None or predecessor.action != reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE:
        problems.append("legacy predecessor is not the bootstrap grant ceremony event")
    elif not key_epochs.is_lost_key_id(predecessor.signing_key_id):
        problems.append("legacy predecessor is not signed under a declared lost epoch")
    else:
        incident = key_epochs.incident_for(predecessor.signing_key_id) or {}
        if payload["incident_id"] != incident.get("incident_id"):
            problems.append("closure incident id does not match the declared incident")

    row = ReviewerRoleAssignment.objects.filter(
        pk=payload["revoked_assignment_id"],
        grant_source=GRANT_BOOTSTRAP_SINGLE_OPERATOR).first()
    if row is None:
        problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: closure names "
                        "an assignment that does not exist")
    else:
        if row.revoked_at is None:
            problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: closure "
                            "event exists but the assignment is not revoked")
        elif row.revoked_at.isoformat() != payload["revoked_at"]:
            problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: assignment "
                            "revocation time does not match the signed closure")
        if row.role != payload["revoked_role"]:
            problems.append("closure names a different role than the assignment")
        if row.revoked_by_id != payload["actor_user_id"]:
            problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: assignment "
                            "revoker does not match the closure actor")
        profile = ReviewerProfile.objects.filter(user_id=row.user_id).first()
        profile_disabled = profile is not None and not profile.reviewer_enabled
        if bool(payload["profile_disabled"]) != profile_disabled:
            problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: profile "
                            "state does not match the signed closure")
    return [p if p.startswith(BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN)
            else f"{BOOTSTRAP_EVENT_INVALID}: {p}" for p in problems]


def _verify_temp_grant_event(event, payload) -> list[str]:
    """Owner-authorized temporary WEB_REFERENCE_REVIEWER grant — everything
    the event claims must agree with the assignment row and the bounded
    contract: the role, the ≤14-day window, the capability inventory, the
    three non-authority statements and the reaffirmation lineage."""
    from datetime import timedelta

    from django.utils.dateparse import parse_datetime

    problems: list[str] = []
    if event.role_used != reg.BOOTSTRAP_OPERATOR:
        problems.append("grant event does not use the BOOTSTRAP_OPERATOR sentinel")
    if event.subject_type != "User" or event.subject_id != str(event.actor_id):
        problems.append("grant subject is not the acting user")
    if "authz_snapshot" in payload:
        problems.append("grant event carries a fabricated authorization snapshot")
    if set(payload) != reg.TEMP_GRANT_PAYLOAD_FIELDS:
        problems.append("grant payload fields are not exact")
        return [f"{BOOTSTRAP_EVENT_INVALID}: {p}" for p in problems]

    if payload["bootstrap_schema"] != reg.TEMP_GRANT_SCHEMA:
        problems.append("unsupported grant ceremony schema")
    if payload["single_operator"] is not True or payload["dual_control"] is not False:
        problems.append("grant is not a single-operator, non-dual-control ceremony")
    if payload["actor_user_id"] != payload["target_user_id"] or \
            payload["actor_user_id"] != event.actor_id:
        problems.append("grant actor/target do not match the signed actor")
    if payload["granted_role"] not in reg.TEMP_GRANT_ALLOWED_ROLES:
        problems.append("grant names a role this ceremony may never grant")
    if payload["purpose"] != reg.TEMP_GRANT_PURPOSE:
        problems.append("grant purpose is not the approved bounded purpose")
    if payload["authorization_basis"] != reg.TEMP_GRANT_AUTHORIZATION_BASIS:
        problems.append("authorization basis is not the owner-authorized basis")
    if payload["account_control_basis"] != reg.TEMP_GRANT_ACCOUNT_CONTROL_BASIS:
        problems.append("account-control basis is not the approved basis")
    if payload["environment_classification"] != reg.ENVIRONMENT_LOCAL_DEVELOPMENT:
        problems.append("environment classification is not LOCAL_DEVELOPMENT")
    if payload["observed_user_is_active"] is not True or \
            payload["observed_user_is_superuser"] is not True:
        problems.append("operator was not observed active and superuser")
    if tuple(payload["capability_inventory"]) != reg.TEMP_GRANT_CAPABILITIES:
        problems.append("capability inventory is not the bounded approved set")
    if tuple(payload["statements"]) != reg.TEMP_GRANT_REQUIRED_STATEMENTS:
        problems.append("grant statements are not the required non-authority set")

    granted = parse_datetime(payload["granted_at"] or "")
    expires = parse_datetime(payload["expires_at"] or "")
    if granted is None or expires is None or expires <= granted:
        problems.append("grant window timestamps are invalid")
    elif (expires - granted) > timedelta(days=reg.TEMP_GRANT_MAX_DAYS):
        problems.append(f"grant exceeds {reg.TEMP_GRANT_MAX_DAYS} days")

    closure = DecisionEvent.objects.filter(
        event_id=payload["reaffirmation_closure_event_id"]).first()
    if closure is None or closure.action != reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE:
        problems.append("grant does not reference the reaffirmation closure event")
    elif payload["incident_id"] != (closure.payload or {}).get("incident_id"):
        problems.append("grant incident id does not match the closure's incident")

    from .models import GRANT_OWNER_TEMPORARY_WEB_REVIEW
    row = ReviewerRoleAssignment.objects.filter(
        pk=payload["assignment_id"],
        grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW).first()
    if row is None:
        problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: grant names "
                        "an assignment that does not exist")
    else:
        if row.role != payload["granted_role"]:
            problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: assignment "
                            "role does not match the signed grant")
        if row.user_id != payload["target_user_id"]:
            problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: assignment "
                            "user does not match the signed grant")
        if row.granted_at.isoformat() != payload["granted_at"] or \
                row.expires_at.isoformat() != payload["expires_at"]:
            problems.append(f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: assignment "
                            "window does not match the signed grant")
    return [p if p.startswith(BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN)
            else f"{BOOTSTRAP_EVENT_INVALID}: {p}" for p in problems]


def verify_bootstrap_consistency() -> list[str]:
    """Whole-database consistency between the chain and the bootstrap state.

    Catches the directions a per-event check cannot: an assignment with no event, a closure
    anchored to an unrelated action, or more than one ceremony.

    **Limitation, stated rather than papered over:** a complete restore of both the database
    and the chain head to a pre-ceremony snapshot is indistinguishable from a environment
    that never ran the ceremony. No in-database mechanism can detect that; only an external
    anchor could, and there is none.
    """
    problems: list[str] = []
    events = list(DecisionEvent.objects.filter(
        action=reg.BOOTSTRAP_INITIAL_REVIEWER_ROLE).order_by("sequence_number"))
    state = BootstrapState.objects.filter(pk=1).first()
    assignments = list(ReviewerRoleAssignment.objects.filter(
        grant_source=GRANT_BOOTSTRAP_SINGLE_OPERATOR))

    if len(events) > 1:
        problems.append("more than one single-operator bootstrap event exists")
    if assignments and not events:
        problems.append("a single-operator assignment exists with no signed ceremony event")
    if events and state is not None:
        if not state.closed:
            problems.append("a ceremony event exists but bootstrap state is open")
        if state.closed_by_event_id != events[0].pk:
            problems.append("bootstrap closure is not anchored to the ceremony event")
    if state is not None and state.closed_by_event_id and not events:
        anchor = DecisionEvent.objects.filter(pk=state.closed_by_event_id).first()
        if anchor is not None and reg.is_bootstrap_event(anchor):
            problems.append("closure anchors a ceremony event that no longer exists")

    # TEMPORARY WEB-REFERENCE REVIEW grants: every owner-temporary assignment
    # must be anchored to exactly one signed grant ceremony event.
    from .models import GRANT_OWNER_TEMPORARY_WEB_REVIEW
    temp_grants = list(DecisionEvent.objects.filter(
        action=reg.TEMPORARY_WEB_REVIEWER_GRANT))
    named = {(e.payload or {}).get("assignment_id") for e in temp_grants}
    for a in ReviewerRoleAssignment.objects.filter(
            grant_source=GRANT_OWNER_TEMPORARY_WEB_REVIEW):
        if a.pk not in named:
            problems.append("an owner-temporary web-review assignment exists "
                            "with no signed grant ceremony event")
    if len(named) != len(temp_grants):
        problems.append("two temporary web-review grant events name the same "
                        "assignment")

    # KEY EPOCH RESET closures: at most one, only alongside the grant it
    # closes, and the assignment it names must actually be revoked.
    closures = list(DecisionEvent.objects.filter(
        action=reg.BOOTSTRAP_REVIEWER_ROLE_CLOSURE).order_by("sequence_number"))
    if len(closures) > 1:
        problems.append("more than one bootstrap closure event exists")
    if closures and not events:
        problems.append("a bootstrap closure exists with no grant ceremony event")
    if closures and assignments:
        if any(a.revoked_at is None for a in assignments):
            problems.append("a bootstrap closure exists but the single-operator "
                            "assignment is not revoked")
    return [f"{BOOTSTRAP_STATE_INCONSISTENT_WITH_CHAIN}: {p}" for p in problems]


def _verify_concept_select_event(event, payload) -> list[str]:
    """Owner-authorized pipeline concept-selection RECORD (2C-2D-CORR-2 §3).

    Everything the event claims must agree with the live pipeline records:
    the GateDecision it lineages to, the hashed metadata decision record,
    the visual contract, and the selected/unselected images. The event must
    also sign its own powerlessness: the exact non-authorization list and
    the record-not-recreate statements.
    """
    problems: list[str] = []
    if event.role_used != reg.BOOTSTRAP_OPERATOR:
        problems.append("selection event does not use the BOOTSTRAP_OPERATOR sentinel")
    if reg.PIPELINE_CONTAINER_CONCEPT_SELECT in authz.ACTIONS:
        problems.append("pipeline.container_concept.select has become a "
                        "policy action — the record must never be "
                        "role-authorizable")
    if set(payload) != reg.CONCEPT_SELECT_PAYLOAD_FIELDS:
        problems.append("concept-selection payload fields are not exact")
        return problems
    if payload["bootstrap_schema"] != reg.CONCEPT_SELECT_SCHEMA:
        problems.append("unsupported concept-selection ceremony schema")
    if payload["decision_code"] != reg.CONCEPT_SELECT_DECISION_CODE:
        problems.append("decision code is not SELECT_CONTAINER_CONCEPT")
    if payload["single_operator"] is not True:
        problems.append("single_operator is not true")
    if payload["dual_control"] is not False:
        problems.append("dual_control is not false")
    if payload["actor_user_id"] != event.actor_id:
        problems.append("payload actor does not match the signed actor")
    if event.subject_type != "DesignTask" or \
            event.subject_id != str(payload["task_id"]):
        problems.append("subject is not the selected task")
    if payload["signing_epoch"] != event.signing_key_id:
        problems.append("payload signing epoch does not match the signed key id")
    if tuple(payload["statements"]) != reg.CONCEPT_SELECT_REQUIRED_STATEMENTS:
        problems.append("required statements are not exact")
    if tuple(payload["non_authorizations"]) != \
            reg.CONCEPT_SELECT_NON_AUTHORIZATIONS:
        problems.append("non-authorization list is not exact")
    if payload["authorization_basis"] != reg.CONCEPT_SELECT_AUTHORIZATION_BASIS:
        problems.append("authorization basis is not the approved ceremony basis")

    # --- live pipeline record agreement (lazy import: accounts must not
    # hard-depend on pipeline; a missing app fails closed as a problem) ----
    try:
        from apps.pipeline.models import DesignProject, GateDecision, GeneratedImage
        from apps.pipeline.services import selected_concept_contract as scc
    except Exception:  # noqa: BLE001 — verification must never crash
        return problems + ["pipeline records unavailable for verification"]

    gd = GateDecision.objects.filter(pk=payload["gate_decision_id"]).first()
    if gd is None:
        problems.append("referenced GateDecision does not exist")
    else:
        if gd.gate != "gate_1" or gd.decision != "approve":
            problems.append("referenced GateDecision is not a gate_1 approval")
        if str(gd.task_id) != str(payload["task_id"]):
            problems.append("referenced GateDecision belongs to a different task")

    project = DesignProject.objects.filter(pk=payload["project_id"]).first()
    meta = (project.metadata or {}) if project else {}
    record = meta.get(scc.SELECTION_META_KEY) or {}
    if record.get("record_hash") != payload["metadata_decision_record_hash"]:
        problems.append("metadata decision record hash does not match the "
                        "project record")
    contract = meta.get(scc.META_KEY) or {}
    if contract.get("contract_hash") != payload["visual_contract_hash"]:
        problems.append("visual contract hash does not match the project record")

    img = GeneratedImage.objects.filter(pk=payload["selected_image_id"]).first()
    if img is None:
        problems.append("selected image does not exist")
    else:
        prov = img.reference_provenance or {}
        if prov.get("variation_identity") != \
                payload["selected_variation_identity"]:
            problems.append("selected variation identity does not match the image")
        if str(img.task_id) != str(payload["task_id"]):
            problems.append("selected image belongs to a different task")
    for u in payload["unselected"] or []:
        alt = GeneratedImage.objects.filter(pk=u.get("image_id")).first()
        if alt is None:
            problems.append(f"unselected image {u.get('image_id')} missing — "
                            "alternatives must stay preserved")
        elif alt.is_approved:
            problems.append(f"unselected image {alt.pk} is approved — "
                            "selection integrity violated")
    return problems


def sentinel_misuse_problems(event) -> list[str]:
    """The sentinel is valid on exactly one action. Anywhere else it is an attempt to make
    an ordinary event look unauthorizable-by-design."""
    if (event.role_used == reg.BOOTSTRAP_OPERATOR
            and not reg.is_bootstrap_event(event)):
        return [f"{BOOTSTRAP_SENTINEL_MISUSED}: BOOTSTRAP_OPERATOR used on action "
                f"{event.action!r}"]
    return []
