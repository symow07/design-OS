"""Decision-event key epochs — the formal record of LOST signing keys.

When signing key material is confirmed unrecoverable (an incident, declared by
a human, never inferred), events signed under that key enter a third integrity
state: not VERIFIED (authenticity cannot be established) and not TAMPERED
(there is no evidence of modification) but UNVERIFIABLE_DUE_TO_LOST_KEY_MATERIAL.

Consequences, enforced by the verification layers that consult this registry:

* the events remain immutable and auditable — payload, signature and key id
  are preserved exactly as persisted;
* they can never automatically authorize a new action (`verify_event` stays
  fail-closed for them);
* chain-level verification reports them as classified legacy notices instead
  of failing the whole chain — otherwise one lost key would permanently brick
  every unrelated projection and no reaffirmed decision could ever restore
  authority;
* content-hash or linkage mismatches on a legacy event are still FATAL:
  lost-key status never absorbs tamper evidence;
* equivalent authority must be reaffirmed by a NEW signed decision under the
  active epoch (see the reaffirmation packet).

This module holds no key material — only identifiers and incident metadata.
"""
from __future__ import annotations

#: integrity state of an event whose signing key material is formally lost
LEGACY_STATE = "UNVERIFIABLE_DUE_TO_LOST_KEY_MATERIAL"
#: finding/status code used by verification layers for that state
LEGACY_SIGNATURE_UNVERIFIABLE = "LEGACY_SIGNATURE_UNVERIFIABLE"
#: stable blockers surfaced where a legacy event previously carried authority
LEGACY_DECISION_REAFFIRMATION_REQUIRED = "LEGACY_DECISION_REAFFIRMATION_REQUIRED"
REVIEWER_ROLE_REAFFIRMATION_REQUIRED = "REVIEWER_ROLE_REAFFIRMATION_REQUIRED"
CORPUS_AUTHORIZATION_REAFFIRMATION_REQUIRED = (
    "CORPUS_AUTHORIZATION_REAFFIRMATION_REQUIRED")

INCIDENT_SCHEMA = "decision_event_key_loss_incident/1.0"

#: key ids whose material is confirmed unrecoverable. Additive only — an id
#: is never removed once declared lost (that would silently re-trust
#: signatures nobody can check). Values are incident metadata, NEVER keys.
LOST_KEY_INCIDENTS: dict[str, dict] = {
    "dip1c-dev-key-1": {
        "schema_version": INCIDENT_SCHEMA,
        "incident_id": "DEKEYLOSS-2026-07-25-001",
        "declared_on": "2026-07-25",
        "environment": "LOCAL_DEVELOPMENT (bbrose_design_os dev database)",
        "affected_event_sequence_numbers": [1, 2, 3],
        "classification": [
            "DECISION_EVENT_ORIGINAL_KEY_MATERIAL_UNRECOVERABLE",
            "LEGACY_DECISION_SIGNATURE_UNVERIFIABLE",
            "DECISION_EVENT_KEY_EPOCH_RESET_REQUIRED",
        ],
        "record": "docs/security/decision_event_key_loss_incident.json",
    },
}


def is_lost_key_id(key_id: str) -> bool:
    return key_id in LOST_KEY_INCIDENTS


def incident_for(key_id: str) -> dict | None:
    return LOST_KEY_INCIDENTS.get(key_id)


def legacy_problem(key_id: str, *, what: str = "event") -> str:
    """The classified problem string for a lost-key signature. Verification
    layers recognise the LEGACY_STATE marker and downgrade chain-level
    severity; event-level authority stays fail-closed."""
    inc = LOST_KEY_INCIDENTS[key_id]
    return (f"{LEGACY_STATE}: {what} signed under lost key epoch "
            f"(incident {inc['incident_id']}) — HMAC authenticity cannot be "
            f"established; a new signed decision must reaffirm any authority")


def is_legacy_problem(problem: str) -> bool:
    return LEGACY_STATE in problem


__all__ = [
    "LEGACY_STATE", "LEGACY_SIGNATURE_UNVERIFIABLE",
    "LEGACY_DECISION_REAFFIRMATION_REQUIRED",
    "REVIEWER_ROLE_REAFFIRMATION_REQUIRED",
    "CORPUS_AUTHORIZATION_REAFFIRMATION_REQUIRED",
    "INCIDENT_SCHEMA", "LOST_KEY_INCIDENTS",
    "is_lost_key_id", "incident_for", "legacy_problem", "is_legacy_problem",
]
