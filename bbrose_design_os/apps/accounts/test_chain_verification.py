"""verify_decision_chain — one tamper per finding class (DIP-1A-5C).

On the real (empty) chain the verifier trivially returns VALID, which proves almost
nothing. Real coverage is: append a small chain, break exactly ONE dimension via raw SQL
(or a crafted signed event), and assert the SPECIFIC classification fires — fatal ones fail
the command, warnings do not. Verification writes nothing.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import override_settings
from django.utils import timezone

from . import attestation as A
from . import authz_policy as authz
from . import chain_verification as V
from . import role_services as RS
from .authorization import (
    AUTHZ_SNAPSHOT_FIELDS,
    AUTHZ_SNAPSHOT_SCHEMA,
    authorize_actor,
    build_authorization_snapshot,
)
from .decision_chain import append_decision
from .models import (
    GRANT_AUTHORIZED_SERVICE,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from .security import signing

pytestmark = pytest.mark.django_db
User = get_user_model()
DAY = timezone.timedelta(days=1)
ACTION = authz.CONFIRM_DESIGN_QUALITY
_seq = 0


def reviewer(role=authz.DESIGN_REVIEWER):
    global _seq
    _seq += 1
    u = User.objects.create_user(username=f"cv{_seq}", password="x")
    ReviewerProfile.objects.create(user=u, reviewer_enabled=True)
    g = User.objects.create_user(username=f"cvg{_seq}", password="x")
    ReviewerRoleAssignment(
        user=u, role=role, granted_at=timezone.now(), expires_at=timezone.now() + 30 * DAY,
        grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=g, grant_reason="t").save()
    return u


def append_plain(payload=None):
    return append_decision(user=reviewer(), action=ACTION,
                           payload=payload if payload is not None else {"n": 1})


def append_attestation():
    return A.record_attestation(
        user=reviewer(authz.DESIGN_REVIEWER), subject_type="CanonicalMaster",
        subject_id="cm-1", decision_type="d", decision_version="1",
        attestation_category=A.CATEGORY_TECHNICAL_AND_BRAND, normalized_scope={},
        evidence_refs=["e"], review_expiry=timezone.now() + 30 * DAY)


def append_role_lifecycle_chain():
    """Exercise every protected role lifecycle producer without crafted events."""
    admin = reviewer(authz.BRAND_ADMIN)

    role_target = User.objects.create_user(username="cv-role-target", password="x")
    ReviewerProfile.objects.create(user=role_target, reviewer_enabled=True)
    grant_event, assignment = RS.grant_reviewer_role(
        actor=admin, target_user=role_target, role=authz.DESIGN_REVIEWER,
        expires_at=timezone.now() + 30 * DAY, reason="verification fixture")
    revoke_event, _ = RS.revoke_reviewer_role(
        actor=admin, assignment=assignment, reason="verification fixture")

    profile_target = User.objects.create_user(username="cv-profile-target", password="x")
    enable_event, _ = RS.enable_reviewer_profile(
        actor=admin, target_user=profile_target, reason="verification fixture")
    disable_event, _ = RS.disable_reviewer_profile(
        actor=admin, target_user=profile_target, reason="verification fixture")
    return grant_event, revoke_event, enable_event, disable_event


def append_signed_snapshot_event(*, changes=None, remove=None):
    """Append a validly signed event with a canonical or deliberately malformed snapshot.

    Crafted events are used only for defensive verifier branches. The defect regression
    above always uses the real role services.
    """
    user = reviewer()
    evaluated_at = timezone.now()
    result = authorize_actor(user, ACTION, at=evaluated_at)
    snapshot = build_authorization_snapshot(user, result, evaluated_at)
    if changes:
        snapshot.update(changes)
    if remove:
        snapshot.pop(remove)
    return append_decision(
        user=user, action=ACTION, payload={"authz_snapshot": snapshot})


def _raw(sql, params=None):
    with connection.cursor() as c:
        c.execute(sql, params or [])


# === healthy / empty ============================================================
def test_empty_chain_is_valid():
    r = V.verify_decision_chain()
    assert r.ok and r.status == "VALID" and r.total_events == 0


def test_healthy_chain_is_valid_with_only_identity_warnings():
    append_attestation()
    append_plain()
    r = V.verify_decision_chain()
    assert r.ok and not r.fatal
    # the attestation carries a snapshot -> identity-state warning; plain event has none
    assert all(w.code in (A.IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY,) for w in r.warnings)


def test_real_role_lifecycle_events_pass_complete_chain_verification():
    events = append_role_lifecycle_chain()
    assert tuple(ev.action for ev in events) == (
        authz.GRANT_REVIEWER_ROLE,
        authz.REVOKE_REVIEWER_ROLE,
        authz.ENABLE_REVIEWER_PROFILE,
        authz.DISABLE_REVIEWER_PROFILE,
    )

    report = V.verify_decision_chain()

    assert report.ok, [finding.as_dict() for finding in report.fatal]
    assert not any(finding.code == V.INVALID for finding in report.fatal)
    call_command("verify_decision_chain")


@pytest.mark.parametrize("action", (
    authz.GRANT_REVIEWER_ROLE,
    authz.REVOKE_REVIEWER_ROLE,
    authz.ENABLE_REVIEWER_PROFILE,
    authz.DISABLE_REVIEWER_PROFILE,
))
def test_each_valid_role_lifecycle_snapshot_passes_full_verification(action):
    events = append_role_lifecycle_chain()
    event = next(ev for ev in events if ev.action == action)
    snapshot = event.payload["authz_snapshot"]

    assert snapshot["snapshot_schema"] == AUTHZ_SNAPSHOT_SCHEMA
    assert set(snapshot) == AUTHZ_SNAPSHOT_FIELDS
    assert snapshot["actor_id"] == event.actor_id
    assert snapshot["role_used"] == event.role_used
    assert snapshot["action"] == event.action
    assert snapshot["subject_type"] == event.subject_type
    assert snapshot["subject_id"] == event.subject_id

    report = V.verify_decision_chain()
    assert report.ok, [finding.as_dict() for finding in report.fatal]
    assert not any(w.code == V.ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE
                   for w in report.warnings)


def test_mixed_role_lifecycle_and_attestation_chain_passes_full_verification():
    append_role_lifecycle_chain()
    append_attestation()

    report = V.verify_decision_chain()

    assert report.ok, [finding.as_dict() for finding in report.fatal]
    assert report.total_events == 5
    assert not any(w.code == V.ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE
                   for w in report.warnings)


# === fatal: crypto / chain integrity ============================================
def test_payload_tamper_is_chain_invalid_and_fails():
    append_plain()
    _raw("UPDATE accounts_decisionevent SET payload = '{\"n\": 999}'")
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.CHAIN_INVALID for f in r.fatal)


def test_hmac_tamper_is_chain_invalid():
    append_plain()
    _raw("UPDATE accounts_decisionevent SET hmac_signature = 'deadbeef'")
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.CHAIN_INVALID for f in r.fatal)


def test_middle_event_linkage_tamper_is_chain_invalid():
    for _ in range(3):
        append_plain()
    _raw("UPDATE accounts_decisionevent SET previous_event_hash = 'nope' "
         "WHERE sequence_number = 2")
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.CHAIN_INVALID for f in r.fatal)


def test_deleted_row_is_chain_invalid():
    append_plain()
    append_plain()
    _raw("DELETE FROM accounts_decisionevent WHERE sequence_number = 2")
    r = V.verify_decision_chain()
    assert not r.ok


def test_head_signature_tamper_is_chain_invalid():
    append_plain()
    _raw("UPDATE accounts_decisionchainhead SET head_signature = 'forged' WHERE id = 1")
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.CHAIN_INVALID for f in r.fatal)


# === fatal: key unavailable =====================================================
def test_unknown_signing_key_is_key_unavailable():
    append_plain()
    _raw("UPDATE accounts_decisionevent SET signing_key_id = 'ghost'")
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.KEY_UNAVAILABLE for f in r.fatal)


# === fatal: snapshot disagrees with envelope (internally contradictory signed) ===
def test_snapshot_envelope_mismatch_is_invalid():
    # craft a validly-SIGNED event whose authz_snapshot names a different actor than the
    # envelope. append_decision signs whatever payload we give (authz_snapshot is not one
    # of ITS reserved keys), so this passes the HMAC but is internally contradictory.
    append_signed_snapshot_event(changes={"actor_id": 999999})
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.INVALID for f in r.fatal)


def test_snapshot_tamper_is_rejected_by_crypto_before_semantics():
    ev = append_signed_snapshot_event()
    _raw("UPDATE accounts_decisionevent SET payload = jsonb_set(payload, "
         "'{authz_snapshot,actor_id}', '999999') WHERE id = %s", [ev.id])
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.CHAIN_INVALID for f in r.fatal)


@pytest.mark.parametrize(("changes", "remove"), (
    pytest.param(None, "actor_id", id="missing-required-field"),
    pytest.param({"snapshot_schema": "authz_snapshot/9.9"}, None,
                 id="wrong-snapshot-version"),
    pytest.param({"actor_id": 999999}, None, id="actor-mismatch"),
    pytest.param({"role_used": authz.BRAND_ADMIN}, None, id="role-mismatch"),
    pytest.param({"action": authz.REVIEW_EVIDENCE}, None, id="action-mismatch"),
))
def test_signed_malformed_snapshot_is_invalid(changes, remove):
    append_signed_snapshot_event(changes=changes, remove=remove)
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.INVALID for f in r.fatal)


# === fatal: signed role_used does not authorize the action under the pinned policy ===
def test_signed_role_not_authorizing_action_is_role_history_invalid(monkeypatch):
    ev = append_attestation()          # signed event with a consistent snapshot
    # simulate the pinned policy no longer granting this role the action
    monkeypatch.setitem(authz.POLICY, ev.action, ())
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.ROLE_HISTORY_INVALID for f in r.fatal)


# === policy version ==============================================================
def test_policy_version_tamper_is_caught_by_the_hmac_first():
    # a downgrade can't be smuggled past the MAC: editing the signed snapshot's
    # policy_version changes the payload, so the HMAC fails (CHAIN_INVALID) BEFORE the
    # POLICY_REVIEW_REQUIRED branch is ever consulted.
    ev = append_attestation()
    _raw("UPDATE accounts_decisionevent SET payload = jsonb_set(payload, "
         "'{authz_snapshot,policy_version}', '\"authz/0.9\"') WHERE id = %s", [ev.id])
    r = V.verify_decision_chain()
    assert not r.ok and any(f.code == V.CHAIN_INVALID for f in r.fatal)


def test_unknown_policy_version_warning_via_a_signed_event():
    append_signed_snapshot_event(changes={"policy_version": "authz/0.9"})
    r = V.verify_decision_chain()
    assert r.ok      # a warning, not fatal
    assert any(w.code == A.POLICY_REVIEW_REQUIRED for w in r.warnings)


# === warning: live rows do not corroborate the signed snapshot ==================
def test_assignment_row_mutation_is_a_warning_naming_the_source():
    ev = append_attestation()
    # push the actor's assignment grant to AFTER the event -> live rows disagree with the
    # signed snapshot. This is an out-of-chain mutation; it must WARN, not fail.
    _raw("UPDATE accounts_reviewerroleassignment SET granted_at = created_at + interval "
         "'10 days', expires_at = created_at + interval '40 days' WHERE user_id = %s",
         [ev.actor_id])
    r = V.verify_decision_chain()
    assert r.ok      # NOT fatal — an unsigned-table edit cannot deny verification
    assert any(w.code == V.ROLE_ASSIGNMENT_HISTORY_UNVERIFIABLE for w in r.warnings)


# === warning: attestation ineffective ===========================================
def test_revoked_attestation_is_a_warning():
    ev = append_attestation()
    admin = reviewer(authz.BRAND_ADMIN)
    A.record_attestation_lifecycle(user=admin, target_event=ev,
                                   lifecycle_kind=A.LIFECYCLE_REVOKED, reason="x")
    r = V.verify_decision_chain()
    assert r.ok
    assert any(w.code == V.ATTESTATION_INEFFECTIVE for w in r.warnings)


# === bounded mode never claims full validity ====================================
def test_bounded_mode_is_diagnostic_never_bare_valid():
    append_plain()
    append_plain()
    r = V.verify_decision_chain(limit=1)
    assert r.mode == "bounded" and r.status.startswith("DIAGNOSTIC")
    assert r.head_checked is False and r.verified_events == 1


# === command: exit codes + read-only ============================================
@override_settings()
def test_command_exits_nonzero_on_fatal():
    append_plain()
    _raw("UPDATE accounts_decisionevent SET payload = '{\"n\": 2}'")
    with pytest.raises(SystemExit) as e:
        call_command("verify_decision_chain")
    assert e.value.code == 1


def test_command_json_on_healthy_chain_is_zero_exit():
    append_plain()
    call_command("verify_decision_chain", "--format", "json")   # no SystemExit


def test_verification_writes_nothing():
    append_attestation()
    append_plain()
    n = DecisionEvent.objects.count()
    V.verify_decision_chain()
    V.verify_decision_chain(limit=1)
    assert DecisionEvent.objects.count() == n


# === key unavailable via registry (retired key removed) =========================
def test_missing_registry_key_fails_closed():
    append_plain()
    with override_settings(
            DECISION_EVENT_HMAC_KEYS='{"other":"11111111111111111111111111111111"}',
            DECISION_EVENT_ACTIVE_KEY_ID="other"):
        signing.reset_registry()
        try:
            r = V.verify_decision_chain()
            assert not r.ok and any(f.code == V.KEY_UNAVAILABLE for f in r.fatal)
        finally:
            signing.reset_registry()
