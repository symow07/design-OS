"""Authenticated dual control + historical authorization (DIP-1A-5B).

Records and validates attestations only — no activation. Actor/role/snapshot are derived
internally; reserved request fields are rejected; dual control requires two DISTINCT
authenticated users over an IDENTICAL binding; historical role validity is evaluated at the
event timestamp; expiry/revocation/supersession/quarantine fail closed; reading writes
nothing.
"""
from __future__ import annotations

import inspect

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from . import attestation as A
from . import authz_policy as authz
from .models import (
    GRANT_AUTHORIZED_SERVICE,
    DecisionEvent,
    ReviewerProfile,
    ReviewerRoleAssignment,
)

pytestmark = pytest.mark.django_db
User = get_user_model()
DAY = timezone.timedelta(days=1)
_seq = 0

# a fixed decision binding shared by complementary attestations
DEC = dict(subject_type="CanonicalMaster", subject_id="cm-1",
           decision_type="canonical_master_approval", decision_version="1",
           normalized_scope={"markets": ["EU"]}, evidence_refs=["ev-1", "ev-2"])


def reviewer(*roles):
    global _seq
    _seq += 1
    u = User.objects.create_user(username=f"rv{_seq}", password="x")
    ReviewerProfile.objects.create(user=u, reviewer_enabled=True)
    for role in roles:
        g = User.objects.create_user(username=f"g{_seq}-{role}", password="x")
        ReviewerRoleAssignment(
            user=u, role=role, granted_at=timezone.now(),
            expires_at=timezone.now() + 30 * DAY, grant_source=GRANT_AUTHORIZED_SERVICE,
            granted_by=g, grant_reason="t").save()
    return u


def attest(user, category, **ov):
    kw = dict(DEC, attestation_category=category,
              review_expiry=timezone.now() + 30 * DAY)
    kw.update(ov)
    return A.record_attestation(user=user, **kw)


def _raw(sql, params=None):
    with connection.cursor() as c:
        c.execute(sql, params or [])


# === internal derivation & reserved-field rejection =============================
def test_record_attestation_derives_actor_role_and_snapshot():
    u = reviewer(authz.DESIGN_REVIEWER)
    ev = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND)
    assert ev.actor_id == u.pk and ev.role_used == authz.DESIGN_REVIEWER
    snap = ev.payload["authz_snapshot"]
    assert snap["actor_id"] == u.pk and snap["role_used"] == authz.DESIGN_REVIEWER
    assert snap["policy_version"] == authz.POLICY_VERSION and snap["user_is_active"] is True


def test_record_attestation_signature_has_no_actor_or_role_param():
    params = set(inspect.signature(A.record_attestation).parameters)
    assert "actor_id" not in params and "role_used" not in params
    assert "authorization_snapshot" not in params and "decision_scope_hash" not in params


@pytest.mark.parametrize("field", ["actor_id", "role_used", "authz_snapshot",
                                   "content_hash", "decision_scope_hash", "policy_version"])
def test_reserved_or_managed_payload_fields_are_rejected(field):
    u = reviewer(authz.DESIGN_REVIEWER)
    with pytest.raises(A.AttestationError):
        attest(u, A.CATEGORY_TECHNICAL_AND_BRAND, payload_extras={field: "sneaky"})


# === authorization ==============================================================
def test_unauthorized_role_for_a_category_is_denied():
    from .authorization import _best_effort_record  # noqa: F401 (ensures import path)
    u = reviewer(authz.DESIGN_REVIEWER)              # cannot attest RIGHTS_AND_OWNERSHIP
    with pytest.raises(A.AttestationDenied):
        attest(u, A.CATEGORY_RIGHTS_AND_OWNERSHIP)
    from .models import AuthorizationAudit
    assert AuthorizationAudit.objects.filter(result="DENIED").exists()


def test_system_admin_substantive_attestation_fails():
    u = reviewer(authz.SYSTEM_ADMIN)
    with pytest.raises(A.AttestationDenied):
        attest(u, A.CATEGORY_RIGHTS_AND_OWNERSHIP)


# === binding hash ===============================================================
def test_binding_hash_is_service_computed_and_deterministic():
    h1 = A.binding_hash(subject_type="S", subject_id="1", decision_type="d",
                        decision_version="1", normalized_scope={"a": 1},
                        evidence_refs=["b", "a"], contradiction_present=False)
    h2 = A.binding_hash(subject_type="S", subject_id="1", decision_type="d",
                        decision_version="1", normalized_scope={"a": 1},
                        evidence_refs=["a", "b"], contradiction_present=False)
    assert h1 == h2 and len(h1) == 64          # evidence order-independent, hashed


# === dual control ===============================================================
def _pair():
    a = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    b = attest(reviewer(authz.LEGAL_REVIEWER), A.CATEGORY_RIGHTS_AND_OWNERSHIP)
    return a, b


def test_two_distinct_authorized_users_satisfy_dual_control():
    a, b = _pair()
    r = A.validate_dual_control(a, b)
    assert r.valid, r.reasons


def test_same_user_cannot_satisfy_both_halves():
    u = reviewer(authz.DESIGN_REVIEWER, authz.LEGAL_REVIEWER)
    a = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND)
    b = attest(u, A.CATEGORY_RIGHTS_AND_OWNERSHIP)
    r = A.validate_dual_control(a, b)
    assert not r.valid and any("same authenticated user" in x for x in r.reasons)


def test_non_complementary_categories_fail():
    a = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    # a COLOR_AND_BRAND is not complementary to TECHNICAL_AND_BRAND
    b = attest(reviewer(authz.BRAND_ADMIN), A.CATEGORY_COLOR_AND_BRAND)
    r = A.validate_dual_control(a, b)
    assert not r.valid and any("complementary" in x for x in r.reasons)


@pytest.mark.parametrize("override", [
    {"subject_id": "cm-2"}, {"decision_type": "other"}, {"decision_version": "2"},
    {"normalized_scope": {"markets": ["US"]}},   # changes the binding hash
])
def test_mismatched_decision_binding_fails(override):
    a = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    b = attest(reviewer(authz.LEGAL_REVIEWER), A.CATEGORY_RIGHTS_AND_OWNERSHIP, **override)
    r = A.validate_dual_control(a, b)
    assert not r.valid


def test_palette_complementary_pair_is_valid():
    a = attest(reviewer(authz.BRAND_ADMIN), A.CATEGORY_COLOR_AND_BRAND)
    b = attest(reviewer(authz.LEGAL_REVIEWER), A.CATEGORY_RIGHTS_AND_USE)
    assert A.validate_dual_control(a, b).valid


# === expiry (computed, fail closed, no background task) =========================
def test_expired_attestation_fails_without_any_event():
    u = reviewer(authz.DESIGN_REVIEWER)
    ev = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND,
                review_expiry=timezone.now() + 2 * DAY)
    # evaluate AT a time past expiry — no expiry event is appended
    future = timezone.now() + 3 * DAY
    es = A.effective_attestation_state(ev, at=future)
    assert not es.effective and es.status == "EXPIRED"


# === lifecycle invalidation =====================================================
@pytest.mark.parametrize("kind,status", [
    (A.LIFECYCLE_REVOKED, A.LIFECYCLE_REVOKED),
    (A.LIFECYCLE_SUPERSEDED, A.LIFECYCLE_SUPERSEDED),
    (A.LIFECYCLE_QUARANTINED, A.LIFECYCLE_QUARANTINED),
])
def test_lifecycle_event_invalidates_attestation(kind, status):
    ev = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    admin = reviewer(authz.BRAND_ADMIN)          # may revoke/quarantine/require re-review
    A.record_attestation_lifecycle(user=admin, target_event=ev, lifecycle_kind=kind,
                                   reason="incident")
    es = A.effective_attestation_state(ev)
    assert not es.effective and es.status == status


def test_lifecycle_uses_signed_payload_reference_not_the_supersedes_fk():
    ev = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    admin = reviewer(authz.BRAND_ADMIN)
    life = A.record_attestation_lifecycle(user=admin, target_event=ev,
                                          lifecycle_kind=A.LIFECYCLE_REVOKED, reason="x")
    assert life.supersedes_event_id is None                       # not the FK
    assert life.payload["invalidates_event_id"] == ev.event_id    # signed reference


def test_revoked_attestation_breaks_dual_control():
    a, b = _pair()
    admin = reviewer(authz.BRAND_ADMIN)
    A.record_attestation_lifecycle(user=admin, target_event=a,
                                   lifecycle_kind=A.LIFECYCLE_REVOKED, reason="x")
    assert not A.validate_dual_control(a, b).valid


# === historical role validity ===================================================
def test_later_role_revocation_does_not_invalidate_a_previously_valid_event():
    u = reviewer(authz.DESIGN_REVIEWER)
    ev = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND)
    # revoke the actor's role NOW (after the event) — historical validity is unchanged
    ReviewerRoleAssignment.objects.filter(user=u).update(
        revoked_at=timezone.now(), revoked_by=u, revocation_reason="left")
    hv = A.historical_role_validity(ev)
    assert hv.valid, hv.reasons


def test_role_not_yet_granted_at_event_time_fails():
    u = reviewer(authz.DESIGN_REVIEWER)
    ev = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND)
    _raw("UPDATE accounts_reviewerroleassignment SET granted_at = created_at + interval "
         "'10 days' WHERE user_id = %s", [u.pk])
    _raw("UPDATE accounts_reviewerroleassignment SET expires_at = granted_at + interval "
         "'30 days' WHERE user_id = %s", [u.pk])
    assert not A.historical_role_validity(ev).valid


def test_role_expired_at_event_time_fails():
    u = reviewer(authz.DESIGN_REVIEWER)
    ev = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND)
    _raw("UPDATE accounts_reviewerroleassignment SET granted_at = created_at - interval "
         "'40 days', expires_at = created_at - interval '1 day' WHERE user_id = %s",
         [u.pk])
    assert not A.historical_role_validity(ev).valid


def test_role_already_revoked_at_event_time_fails():
    u = reviewer(authz.DESIGN_REVIEWER)
    revoker = User.objects.create_user(username="rv-past", password="x")
    ev = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND)
    _raw("UPDATE accounts_reviewerroleassignment SET granted_at = created_at - interval "
         "'10 days', revoked_at = created_at - interval '1 day', revoked_by_id = %s, "
         "revocation_reason = 'x' WHERE user_id = %s", [revoker.pk, u.pk])
    assert not A.historical_role_validity(ev).valid


def test_historical_validity_reports_identity_state_limitation():
    ev = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    hv = A.historical_role_validity(ev)
    assert A.IDENTITY_STATE_HISTORY_SNAPSHOT_ONLY in hv.warnings


def test_current_is_active_change_does_not_rewrite_the_snapshot():
    u = reviewer(authz.DESIGN_REVIEWER)
    ev = attest(u, A.CATEGORY_TECHNICAL_AND_BRAND)
    u.is_active = False
    u.save()
    # the SIGNED snapshot preserves the append-time observation
    assert ev.payload["authz_snapshot"]["user_is_active"] is True


# === policy versioning ==========================================================
def test_unknown_policy_version_returns_policy_review_required():
    ev = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    _raw("UPDATE accounts_decisionevent SET payload = jsonb_set(payload, "
         "'{authz_snapshot,policy_version}', '\"authz/0.9\"') WHERE id = %s", [ev.id])
    ev.refresh_from_db()
    hv = A.historical_role_validity(ev)
    assert not hv.valid and A.POLICY_REVIEW_REQUIRED in hv.reasons


# === tamper + chain validity ====================================================
def test_tampered_snapshot_fails_chain_verification():
    ev = attest(reviewer(authz.DESIGN_REVIEWER), A.CATEGORY_TECHNICAL_AND_BRAND)
    _raw("UPDATE accounts_decisionevent SET payload = jsonb_set(payload, "
         "'{authz_snapshot,role_used}', '\"BRAND_ADMIN\"') WHERE id = %s", [ev.id])
    ev.refresh_from_db()
    es = A.effective_attestation_state(ev)
    assert not es.effective and es.status == "CHAIN_INVALID"


# === read-only guarantee ========================================================
def test_dual_control_and_read_model_write_nothing():
    a, b = _pair()
    n = DecisionEvent.objects.count()
    A.validate_dual_control(a, b)
    A.effective_attestation_state(a)
    A.historical_role_validity(a)
    assert DecisionEvent.objects.count() == n     # zero writes


# === contradiction ==============================================================
def test_unacknowledged_contradiction_is_refused():
    u = reviewer(authz.DESIGN_REVIEWER)
    with pytest.raises(A.AttestationError):
        attest(u, A.CATEGORY_TECHNICAL_AND_BRAND, contradiction_present=True,
               contradiction_acknowledged=False)


# === no activation surface ======================================================
def test_no_activation_or_permission_surface():
    import apps.accounts.attestation as mod
    text = open(mod.__file__).read()
    for forbidden in ("retrieval", "automatic_use", "grant_permission(", "activate(",
                      "def approve", "production_use"):
        assert forbidden not in text, f"1A-5B must not introduce {forbidden!r}"
