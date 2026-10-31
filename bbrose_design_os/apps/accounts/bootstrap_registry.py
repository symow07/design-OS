"""Bootstrap-event registry — DIP-1A-BOOTSTRAP-CORR-2.

A **separate** registry, deliberately not `authz.ACTIONS`. The single-operator bootstrap
action must never be authorizable by any role, so it is not in the ordinary policy at all:
`authorize_actor` rejects it with `ACTION_UNKNOWN`, and `append_decision` rejects it in
`_validate_event_inputs`. Its only producer is the dedicated ceremony append path.

This module is a set of constants and two predicates. It is **not** a second authorization
system: nothing here decides that anyone may do anything. The ceremony's right to act comes
from a password challenge against a local superuser account plus a one-shot environment
gate, and the resulting event says so in its own payload rather than borrowing the language
of role authorization.
"""
from __future__ import annotations

BOOTSTRAP_INITIAL_REVIEWER_ROLE = "bootstrap_initial_reviewer_role"
#: KEY EPOCH RESET (DEKEYLOSS-2026-07-25-001): the single-operator CLOSURE of a
#: bootstrap grant whose signing key epoch is formally lost. De-escalation only
#: — it can revoke the ceremony grant, never create or widen authority.
BOOTSTRAP_REVIEWER_ROLE_CLOSURE = "bootstrap_reviewer_role_closure"
#: TEMPORARY WEB-REFERENCE REVIEW (owner-authorized, 2026-07-25): the bounded
#: 14-day WEB_REFERENCE_REVIEWER grant for web-source curation after the key
#: epoch reset. Endpoint authority only — the role authorizes no chain action.
TEMPORARY_WEB_REVIEWER_GRANT = "temporary_web_reference_reviewer_grant"
#: Every action this registry knows: the one grant ceremony, its one closure,
#: and the owner-authorized temporary web-review grant. Additions land here
#: deliberately, each with its own verifier — never through a default.
BOOTSTRAP_EVENT_ACTIONS = frozenset({
    BOOTSTRAP_INITIAL_REVIEWER_ROLE, BOOTSTRAP_REVIEWER_ROLE_CLOSURE,
    TEMPORARY_WEB_REVIEWER_GRANT,
    # 2C-2D-CORR-2: owner-authorized pipeline concept-selection record
    # (constants defined at the bottom of this module)
    "pipeline.container_concept.select"})

#: `role_used` for a bootstrap event. NOT a member of `authz.ROLES` — a reader who sees it
#: knows immediately that no role authorized this event, because no such role exists.
BOOTSTRAP_OPERATOR = "BOOTSTRAP_OPERATOR"

BOOTSTRAP_CEREMONY_SCHEMA = "bootstrap/single_operator_initial_reviewer/1.0"

#: How the operator proved control of the account. A username argument proves nothing; this
#: names the actual challenge that was performed.
ACCOUNT_CONTROL_PASSWORD_CHALLENGE = "DJANGO_PASSWORD_CHALLENGE_LOCAL_CLI"
#: What stood in for a role-policy decision. Stated plainly rather than disguised as one.
AUTHORIZATION_BASIS = "SUPERUSER_LOCAL_BOOTSTRAP_NOT_ROLE_POLICY"

ENVIRONMENT_LOCAL_DEVELOPMENT = "LOCAL_DEVELOPMENT"

#: An allow-list of exactly one role. A role added to `authz.ROLES` in future cannot enter
#: the ceremony by default — it would have to be added here deliberately.
ALLOWED_BOOTSTRAP_ROLES = ("DESIGN_REVIEWER",)
MAX_EXPIRY_DAYS = 30
MAX_REASON_LENGTH = 500

#: Every payload key a ceremony event carries — exactly, no more and no less.
CEREMONY_PAYLOAD_FIELDS = frozenset({
    "bootstrap_schema", "single_operator", "dual_control",
    "actor_user_id", "target_user_id", "granted_role", "granted_at", "expires_at",
    "reason", "environment_classification", "environment_evidence",
    "account_control_basis", "observed_user_is_active", "observed_user_is_superuser",
    "prior_reviewer_profile_state", "resulting_reviewer_profile_state",
    "prior_bootstrap_state", "resulting_bootstrap_state", "authorization_basis",
})

# --- closure ceremony (DECISION-EVENT KEY EPOCH RESET) ---------------------------
CLOSURE_CEREMONY_SCHEMA = "bootstrap/single_operator_reviewer_closure/1.0"
#: The closure is de-escalation performed on an explicit human mandate; no
#: interactive password challenge runs, and the basis says so plainly.
CLOSURE_ACCOUNT_CONTROL_BASIS = "LOCAL_OPERATOR_MANDATE_DEESCALATION_ONLY"
CLOSURE_AUTHORIZATION_BASIS = (
    "SUPERUSER_LOCAL_REAFFIRMATION_CLOSURE_NOT_ROLE_POLICY")
#: The one human decision a closure may express.
CLOSURE_HUMAN_DECISION = "NO_LONGER_REQUIRED"

CLOSURE_PAYLOAD_FIELDS = frozenset({
    "bootstrap_schema", "single_operator", "dual_control",
    "actor_user_id", "target_user_id",
    "legacy_predecessor_event_id", "legacy_integrity_state", "incident_id",
    "human_decision", "revoked_assignment_id", "revoked_role", "revoked_at",
    "reason", "profile_disabled",
    "environment_classification", "environment_evidence",
    "account_control_basis", "observed_user_is_active",
    "observed_user_is_superuser", "authorization_basis", "statements",
})

#: The four statements every closure must sign, verbatim (§1 of the ceremony
#: mandate). A closure that says anything else does not verify.
CLOSURE_REQUIRED_STATEMENTS = (
    "the original role grant is not reaffirmed",
    "the legacy event remains preserved for audit",
    "no equivalent reviewer-role authority is recreated",
    "the decision does not alter the administrator's independent superuser "
    "authority",
)

# --- temporary web-reference reviewer grant --------------------------------------
TEMP_GRANT_SCHEMA = "temporary_web_reference_reviewer_grant/1.0"
TEMP_GRANT_AUTHORIZATION_BASIS = "OWNER_AUTHORIZED_TEMPORARY_REVIEWER_GRANT"
TEMP_GRANT_ACCOUNT_CONTROL_BASIS = "LOCAL_OPERATOR_OWNER_MANDATE"
TEMP_GRANT_PURPOSE = "WEB_REFERENCE_REVIEW_AND_COMPLETE_PRODUCT_PILOT"
TEMP_GRANT_MAX_DAYS = 14
#: the ONLY role this ceremony may grant — never DESIGN_REVIEWER, never
#: anything that authorizes a decision-chain action
TEMP_GRANT_ALLOWED_ROLES = ("WEB_REFERENCE_REVIEWER",)

TEMP_GRANT_PAYLOAD_FIELDS = frozenset({
    "bootstrap_schema", "single_operator", "dual_control",
    "actor_user_id", "target_user_id", "granted_role", "purpose",
    "granted_at", "expires_at", "reason", "assignment_id",
    "capability_inventory", "statements", "revocation_mechanism",
    "incident_id", "reaffirmation_closure_event_id",
    "environment_classification", "environment_evidence",
    "account_control_basis", "observed_user_is_active",
    "observed_user_is_superuser", "authorization_basis",
})

#: the bounded capability inventory the grant signs — exactly the §1 allow
#: list of the owner's mandate, nothing more
TEMP_GRANT_CAPABILITIES = (
    "view_quarantined_web_reference_candidates",
    "approve_reference_view_permission",
    "classify_source_physical_analog",
    "classify_source_visual_inspiration",
    "classify_source_fact_source",
    "classify_source_exact_product_reference_where_genuinely_applicable",
    "reject_source",
    "mark_source_needs_verification",
    "approve_provider_input_after_valid_reference_classification",
    "record_final_web_reference_packet_decision",
    "record_complete_product_pilot_creation_authorization_when_owner_provides_it",
)

TEMP_GRANT_REQUIRED_STATEMENTS = (
    "the legacy reviewer grant remains closed",
    "this grant does not authorize corpus metadata fork resolution",
    "this grant does not authorize artwork reuse, production authority or "
    "Design Memory",
)


# --- owner-authorized pipeline concept selection (2C-2D-CORR-2) -------------------
#: chain-grade RECORD of an existing human Gate-1 concept selection. The event
#: grants NOTHING: it is not in authz.ACTIONS, no role authorizes it, and its
#: payload states its non-authorizations explicitly. It exists because the
#: selected concept will control profile generation, reconstruction, stage
#: handoff and later Packaging — that lineage deserves a signature.
PIPELINE_CONTAINER_CONCEPT_SELECT = "pipeline.container_concept.select"
CONCEPT_SELECT_SCHEMA = "pipeline_container_concept_selection/1.0"
CONCEPT_SELECT_AUTHORIZATION_BASIS = (
    "OWNER_AUTHORIZED_PIPELINE_SELECTION_CEREMONY")
CONCEPT_SELECT_ACCOUNT_CONTROL_BASIS = "LOCAL_OPERATOR_OWNER_MANDATE"
CONCEPT_SELECT_DECISION_CODE = "SELECT_CONTAINER_CONCEPT"

CONCEPT_SELECT_PAYLOAD_FIELDS = frozenset({
    "bootstrap_schema", "single_operator", "dual_control",
    "actor_user_id", "decision_code", "project_id", "task_id",
    "design_target", "selected_direction_id", "selected_direction_name",
    "selected_image_id", "selected_variation_identity", "unselected",
    "gate_decision_id", "gate_decision_decided_at",
    "metadata_decision_record_hash", "visual_contract_schema",
    "visual_contract_hash", "human_decided_at", "recorded_at",
    "signing_epoch", "statements", "non_authorizations",
    "authorization_basis", "account_control_basis",
    "environment_classification", "environment_evidence",
    "observed_user_is_active", "observed_user_is_superuser",
})

CONCEPT_SELECT_REQUIRED_STATEMENTS = (
    "this event records the existing human decision and does not recreate "
    "or alter it",
    "the referenced GateDecision, metadata decision record and visual "
    "contract remain the authoritative originals, unchanged",
)

#: everything this event can NEVER authorize — signed into the payload
CONCEPT_SELECT_NON_AUTHORIZATIONS = (
    "profile_confirmation", "zone_confirmation", "native_reconstruction",
    "human_design_acceptance", "gate_2", "packaging_creation",
    "production_authority",
)


def is_bootstrap_action(action: str) -> bool:
    return action in BOOTSTRAP_EVENT_ACTIONS


def is_bootstrap_event(event) -> bool:
    return is_bootstrap_action(getattr(event, "action", ""))
