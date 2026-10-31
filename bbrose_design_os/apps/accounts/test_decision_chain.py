"""Signed decision-event chain — append, idempotency, append-only, verification (1A-4).

Correctness is checked against reality: tamper tests mutate rows with raw SQL (bypassing
the ORM guards) and assert the read-only verifier catches it; the signed timestamp is
proven identical to the stored one; key rotation is exercised with real retired keys.
Concurrency lives in test_decision_chain_concurrency.py (a TransactionTestCase).
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.utils import timezone

from . import authz_policy as authz
from .authorization import authorize_actor
from .decision_chain import (
    AuthorizationDenied,
    ChainInconsistent,
    IdempotencyConflict,
    SupersessionError,
    append_decision,
    verify_chain,
)
from .models import (
    ChainWriteViolation,
    DecisionChainHead,
    DecisionEvent,
    GRANT_AUTHORIZED_SERVICE,
    ReviewerProfile,
    ReviewerRoleAssignment,
)
from .security import signing

pytestmark = pytest.mark.django_db
User = get_user_model()
ACTION = authz.CONFIRM_DESIGN_QUALITY
ROLE = authz.DESIGN_REVIEWER
_seq = 0


def reviewer(role=ROLE, *, enabled=True):
    global _seq
    _seq += 1
    u = User.objects.create_user(username=f"cu{_seq}", password="x")
    ReviewerProfile.objects.create(user=u, reviewer_enabled=enabled)
    if role is not None:
        g = User.objects.create_user(username=f"cg{_seq}", password="x")
        ReviewerRoleAssignment(
            user=u, role=role, granted_at=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(days=30),
            grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=g,
            grant_reason="t").save()
    return u


def authed(action=ACTION, role=ROLE, subject=None):
    """Return (user, AuthorizationResult). The result is only for tests to inspect — the
    append service does NOT accept it; it authorizes internally and derives role_used."""
    u = reviewer(role)
    res = authorize_actor(u, action, subject=subject)
    assert res.allowed
    return u, res


def do_append(u, res=None, *, action=ACTION, payload=None, subject=None,
              event_id=None, supersedes=None):
    # `res` is accepted positionally for the `do_append(*authed())` idiom but is IGNORED —
    # the service derives role_used itself. action defaults to ACTION (what authed grants).
    return append_decision(
        user=u, action=res.action if res is not None else action,
        payload=payload if payload is not None else {"note": "ok"},
        subject=subject, event_id=event_id, supersedes=supersedes)


# === genesis =====================================================================
def test_genesis_head_exists_and_verifies_empty():
    head = DecisionChainHead.objects.get(pk=1)
    assert head.is_genesis and head.event_count == 0
    assert head.terminal_event_hash is None and head.head_signature == ""
    r = verify_chain()
    assert r.ok and r.event_count == 0 and r.problems == ()


# === single append ===============================================================
def test_first_append_links_to_null_and_signs_head():
    u, res = authed()
    ev = do_append(u, res)
    assert ev.sequence_number == 1
    assert ev.previous_event_hash is None            # matches the frozen golden vector
    assert ev.content_hash and ev.hmac_signature and ev.signing_key_id
    head = DecisionChainHead.objects.get(pk=1)
    assert not head.is_genesis and head.event_count == 1
    assert head.terminal_event_hash == ev.content_hash and head.head_signature
    assert verify_chain().ok


def test_second_append_links_to_first():
    u, res = authed()
    e1 = do_append(u, res)
    u2, res2 = authed()
    e2 = do_append(u2, res2)
    assert e2.sequence_number == 2
    assert e2.previous_event_hash == e1.content_hash
    assert verify_chain().ok


def test_signed_timestamp_equals_stored_timestamp():
    u, res = authed()
    ev = do_append(u, res)
    from .decision_chain import _rebuild_event_doc
    from .security import canonical
    # if the stored created_at differed from the signed one, this hash would not match
    assert canonical.content_hash(_rebuild_event_doc(ev)) == ev.content_hash


# === direct-write guards =========================================================
def test_direct_create_is_blocked():
    u, res = authed()
    with pytest.raises(ChainWriteViolation):
        DecisionEvent.objects.create(
            sequence_number=1, event_id="x", actor=u, role_used=ROLE, action=ACTION,
            content_hash="h", hmac_signature="s", signing_key_id="k",
            created_at=timezone.now())


def test_plain_save_without_token_is_blocked():
    u, res = authed()
    ev = do_append(u, res)
    ev.role_used = authz.BRAND_ADMIN
    with pytest.raises(ChainWriteViolation):
        ev.save()


def test_update_delete_bulk_are_blocked():
    u, res = authed()
    do_append(u, res)
    with pytest.raises(ChainWriteViolation):
        DecisionEvent.objects.all().update(action="x")
    with pytest.raises(ChainWriteViolation):
        DecisionEvent.objects.all().delete()
    with pytest.raises(ChainWriteViolation):
        DecisionEvent.objects.bulk_create([])


def test_head_cannot_be_saved_or_created_without_token():
    head = DecisionChainHead.objects.get(pk=1)
    with pytest.raises(ChainWriteViolation):
        head.save()
    with pytest.raises(ChainWriteViolation):
        DecisionChainHead.objects.create(id=2, chain_id="other")


# === idempotency =================================================================
def test_identical_retry_returns_same_event():
    u, res = authed()
    e1 = do_append(u, res, event_id="evt-1", payload={"n": 1})
    e2 = do_append(u, res, event_id="evt-1", payload={"n": 1})
    assert e1.pk == e2.pk
    assert DecisionEvent.objects.count() == 1


def test_same_event_id_different_content_conflicts():
    u, res = authed()
    do_append(u, res, event_id="evt-1", payload={"n": 1})
    with pytest.raises(IdempotencyConflict):
        do_append(u, res, event_id="evt-1", payload={"n": 2})


def test_absent_event_id_is_generated():
    u, res = authed()
    ev = do_append(u, res, event_id=None)
    assert ev.event_id and len(ev.event_id) >= 16


# === authorization is internal; role_used is DERIVED (Correction 2) ==============
def test_append_authorizes_internally_and_denies_a_revoked_actor():
    u = reviewer(ROLE)
    a = ReviewerRoleAssignment.objects.get(user=u, role=ROLE)
    a.revoked_at = timezone.now()
    a.revoked_by = User.objects.create_user(username="revoker", password="x")
    a.revocation_reason = "gone"
    a.save()
    with pytest.raises(AuthorizationDenied):
        append_decision(user=u, action=ACTION, payload={})
    assert DecisionEvent.objects.count() == 0        # nothing appended


def test_append_denies_actor_without_the_role():
    u = reviewer(authz.OBSERVER)                      # OBSERVER cannot CONFIRM_DESIGN_QUALITY
    with pytest.raises(AuthorizationDenied):
        append_decision(user=u, action=ACTION, payload={})
    assert DecisionEvent.objects.count() == 0


def test_append_signature_has_no_role_used_or_authorization_param():
    import inspect
    params = set(inspect.signature(append_decision).parameters)
    assert "role_used" not in params and "authorization" not in params


def test_stored_role_used_is_the_canonical_derived_role_not_caller_supplied():
    # An actor holding BOTH a specialist and the broad admin role: policy derives the
    # least-privileged specialist, and the caller has no way to force the broader one.
    u = reviewer(authz.DESIGN_REVIEWER)
    g = User.objects.create_user(username="g-extra-role", password="x")
    ReviewerRoleAssignment(
        user=u, role=authz.BRAND_ADMIN, granted_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
        grant_source=GRANT_AUTHORIZED_SERVICE, granted_by=g, grant_reason="t").save()
    ev = append_decision(user=u, action=ACTION, payload={})
    # CONFIRM_DESIGN_QUALITY: DESIGN_REVIEWER is narrower than BRAND_ADMIN -> derived
    assert ev.role_used == authz.DESIGN_REVIEWER
    assert ev.role_used == authorize_actor(u, ACTION).role_used   # canonical decision


def test_a_role_in_the_payload_cannot_influence_signed_content():
    # role_used is a reserved (signed-envelope) key, so it cannot even ride in the payload.
    u = reviewer(ROLE)
    with pytest.raises(Exception):
        append_decision(user=u, action=ACTION,
                        payload={"role_used": authz.BRAND_ADMIN})


# === payload hygiene =============================================================
def test_reserved_payload_keys_are_refused():
    u, res = authed()
    with pytest.raises(Exception):
        do_append(u, res, payload={"content_hash": "sneaky"})


# === verifier detects tampering (raw SQL bypasses the ORM guards) ================
def _raw(sql, params=None):
    with connection.cursor() as c:
        c.execute(sql, params or [])


def test_verify_detects_mutated_payload():
    u, res = authed()
    do_append(u, res)
    _raw("UPDATE accounts_decisionevent SET payload = '{\"note\": \"TAMPERED\"}'")
    r = verify_chain()
    assert not r.ok and any("content hash" in p for p in r.problems)


def test_verify_detects_mutated_hmac():
    u, res = authed()
    do_append(u, res)
    _raw("UPDATE accounts_decisionevent SET hmac_signature = 'deadbeef'")
    r = verify_chain()
    assert not r.ok and any("HMAC" in p for p in r.problems)


def test_hmac_catches_payload_tamper_even_with_recomputed_content_hash():
    # content_hash needs no key, so an attacker can recompute it to match a tampered
    # payload. The HMAC (which DOES need the key) is the real control — prove it fires.
    u, res = authed()
    ev = do_append(u, res, payload={"v": 1})
    _raw("UPDATE accounts_decisionevent SET payload = '{\"v\": 999}'")
    ev.refresh_from_db()
    from .decision_chain import _rebuild_event_doc
    from .security import canonical
    forged_hash = canonical.content_hash(_rebuild_event_doc(ev))
    _raw("UPDATE accounts_decisionevent SET content_hash = %s", [forged_hash])
    r = verify_chain()
    assert not r.ok and any("HMAC" in p for p in r.problems)


def test_verify_detects_deleted_row():
    u, res = authed()
    do_append(u, res)
    do_append(*authed())
    _raw("DELETE FROM accounts_decisionevent WHERE sequence_number = 2")
    r = verify_chain()
    assert not r.ok


def test_verify_detects_head_tamper():
    u, res = authed()
    do_append(u, res)
    _raw("UPDATE accounts_decisionchainhead SET terminal_event_hash = 'nope' WHERE id=1")
    r = verify_chain()
    assert not r.ok


# === v2: signed supersession + signature algorithm ==============================
def test_supersession_is_signed_and_survives_verification():
    u, res = authed()
    e1 = do_append(u, res, payload={"v": 1})
    e2 = do_append(*authed(), payload={"v": 2}, supersedes=e1)
    assert e2.supersedes_event_id == e1.id
    # the signed envelope carries the referenced event's stable event_id
    from .decision_chain import _rebuild_event_doc
    assert _rebuild_event_doc(e2)["supersedes_event_id"] == e1.event_id
    assert verify_chain().ok


def test_verify_detects_repointed_supersession_reference():
    u, res = authed()
    e1 = do_append(u, res, payload={"v": 1})
    do_append(*authed(), payload={"v": 2})                       # e2, no supersedes
    e3 = do_append(*authed(), payload={"v": 3}, supersedes=e1)
    # repoint e3's supersession from e1 to e2 via raw SQL — the signed id no longer matches
    _raw("UPDATE accounts_decisionevent SET supersedes_event_id = "
         "(SELECT id FROM accounts_decisionevent WHERE sequence_number=2) "
         "WHERE id = %s", [e3.id])
    r = verify_chain()
    assert not r.ok and any("content hash" in p for p in r.problems)


def test_verify_detects_invalid_signature_algorithm():
    u, res = authed()
    do_append(u, res)
    _raw("UPDATE accounts_decisionevent SET signature_algorithm = 'MD5'")
    r = verify_chain()
    assert not r.ok and any("algorithm" in p or "content hash" in p for p in r.problems)


def test_append_refuses_forward_or_cross_subject_supersession():
    u, res = authed(subject=("FontFace", "a"))
    e1 = do_append(u, res, subject=("FontFace", "a"))
    # different subject -> supersession refused
    with pytest.raises(SupersessionError):
        do_append(*authed(subject=("FontFace", "b")), subject=("FontFace", "b"),
                  supersedes=e1)


def test_append_refuses_cross_action_supersession():
    # e1 is a CONFIRM_DESIGN_QUALITY decision; a REQUIRE_RE_REVIEW event may not supersede
    # it — a correction stays within the same decision domain (action).
    u, res = authed(action=authz.CONFIRM_DESIGN_QUALITY)
    e1 = do_append(u, res)
    u2 = reviewer(authz.DESIGN_REVIEWER)             # DESIGN_REVIEWER may require re-review
    with pytest.raises(SupersessionError):
        append_decision(user=u2, action=authz.REQUIRE_RE_REVIEW, payload={},
                        supersedes=e1)


# === append fails closed on an already-inconsistent chain (spec §6) =============
# Distinct from verify_chain: the append path must REFUSE to extend a broken chain. Each
# case corrupts a committed chain via raw SQL, then asserts append raises and writes nothing.
def _append_must_refuse(u2, res2):
    before = DecisionEvent.objects.count()
    with pytest.raises(ChainInconsistent):
        do_append(u2, res2)
    assert DecisionEvent.objects.count() == before      # nothing appended


def test_append_refuses_on_tampered_head_signature():
    do_append(*authed())
    _raw("UPDATE accounts_decisionchainhead SET head_signature = 'forged' WHERE id=1")
    _append_must_refuse(*authed())


def test_append_refuses_on_event_count_mismatch():
    do_append(*authed())
    _raw("UPDATE accounts_decisionchainhead SET event_count = 99 WHERE id=1")
    _append_must_refuse(*authed())


def test_append_refuses_on_terminal_hash_mismatch():
    do_append(*authed())
    _raw("UPDATE accounts_decisionchainhead SET terminal_event_hash = 'nope' WHERE id=1")
    _append_must_refuse(*authed())


def test_append_refuses_when_terminal_row_deleted():
    do_append(*authed())
    do_append(*authed())
    _raw("DELETE FROM accounts_decisionevent WHERE sequence_number = 2")
    _append_must_refuse(*authed())


def test_append_refuses_on_unknown_signing_key():
    do_append(*authed())
    _raw("UPDATE accounts_decisionevent SET signing_key_id = 'ghost-key'")
    _append_must_refuse(*authed())


# === correction appends, never overwrites =======================================
def test_supersede_appends_without_mutating_the_original():
    u, res = authed()
    e1 = do_append(u, res, payload={"v": 1})
    orig = (e1.content_hash, e1.hmac_signature, e1.payload, e1.sequence_number)
    u2, res2 = authed()
    e2 = do_append(u2, res2, payload={"v": 2}, supersedes=e1)
    e1.refresh_from_db()
    assert (e1.content_hash, e1.hmac_signature, e1.payload,
            e1.sequence_number) == orig          # byte-for-byte unchanged
    assert e2.supersedes_event_id == e1.id
    assert verify_chain().ok


def test_authorization_audit_is_not_related_to_the_decision_chain():
    from django.apps import apps as django_apps
    audit = django_apps.get_model("accounts", "AuthorizationAudit")
    related = {f.related_model for f in audit._meta.get_fields() if f.is_relation}
    assert DecisionEvent not in related and DecisionChainHead not in related


# === key rotation ================================================================
@override_settings(
    DECISION_EVENT_HMAC_KEYS='{"k1":"11111111111111111111111111111111"}',
    DECISION_EVENT_ACTIVE_KEY_ID="k1")
def test_rotation_keeps_history_verifiable():
    signing.reset_registry()
    try:
        u, res = authed()
        e1 = do_append(u, res)
        assert e1.signing_key_id == "k1"
        # rotate: k2 active, k1 retained for verification only
        with override_settings(
            DECISION_EVENT_HMAC_KEYS='{"k1":"11111111111111111111111111111111",'
                                     '"k2":"22222222222222222222222222222222"}',
            DECISION_EVENT_ACTIVE_KEY_ID="k2"):
            signing.reset_registry()
            u2, res2 = authed()
            e2 = do_append(u2, res2)
            assert e2.signing_key_id == "k2"          # new events use the active key
            assert e1.signing_key_id == "k1"          # history retains its key
            assert verify_chain().ok                  # both verify
    finally:
        signing.reset_registry()


# === still-absent gates ==========================================================
def test_no_approval_permission_or_retrieval_surface():
    import apps.accounts.decision_chain as mod
    text = open(mod.__file__).read()
    for forbidden in ("retrieval", "automatic_use", "grant_permission(",
                      "approve_", "activate"):
        assert forbidden not in text, f"1A-4 must not introduce {forbidden!r}"
